"""
Component reliability data lookup.
Priority 1: Manufacturer website (TI, Analog Devices, Mouser, Digi-Key).
Priority 2: Return None → caller falls back to MIL-217F model.

Only GET requests are made; no authentication or paid data is accessed.
FIT rates or MTBF figures found in page text are extracted with regex.
"""

import re
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml',
}
TIMEOUT = 8  # seconds

# Patterns to find FIT / MTBF / λ in plain text
FIT_PATTERNS = [
    re.compile(r'(\d+[\.,]?\d*)\s*FIT', re.IGNORECASE),
    re.compile(r'FIT[:\s]+(\d+[\.,]?\d*)', re.IGNORECASE),
    re.compile(r'(\d+[\.,]?\d*)\s*failures?\s*/\s*10\^?9\s*hours?', re.IGNORECASE),
]

MTBF_PATTERNS = [
    re.compile(r'MTBF[:\s]+([\d,\.]+)\s*(hours?|hrs?)', re.IGNORECASE),
    re.compile(r'([\d,\.]+)\s*(hours?|hrs?)\s*MTBF', re.IGNORECASE),
]


def _extract_fit(text: str):
    """Return first FIT value found in text, or None."""
    for pat in FIT_PATTERNS:
        m = pat.search(text)
        if m:
            val = m.group(1).replace(',', '')
            try:
                return float(val)
            except ValueError:
                pass
    return None


def _extract_mtbf_hours(text: str):
    """Return first MTBF value (hours) found in text, or None."""
    for pat in MTBF_PATTERNS:
        m = pat.search(text)
        if m:
            val = m.group(1).replace(',', '')
            try:
                return float(val)
            except ValueError:
                pass
    return None


def _fetch_text(url: str) -> str | None:
    """Fetch URL and return visible text, or None on failure."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, 'lxml')
        for tag in soup(['script', 'style', 'nav', 'footer']):
            tag.decompose()
        return soup.get_text(separator=' ', strip=True)
    except Exception as exc:
        logger.debug('Fetch %s failed: %s', url, exc)
        return None


# ──────────────────────────────────────────────────────────────────────
#  Manufacturer-specific lookup functions
# ──────────────────────────────────────────────────────────────────────

def lookup_ti(part_number: str) -> dict | None:
    """Search Texas Instruments product page for reliability data."""
    url = f'https://www.ti.com/product/{part_number.upper()}/quality-reliability'
    text = _fetch_text(url)
    if not text:
        # fall back to main product page
        url = f'https://www.ti.com/product/{part_number.upper()}'
        text = _fetch_text(url)
    if not text:
        return None

    fit = _extract_fit(text)
    mtbf = _extract_mtbf_hours(text)

    if fit:
        return {
            'source':      'Texas Instruments (web)',
            'fit_rate':    fit,                          # failures / 10^9 hr
            'lambda_p':    fit / 1000,                  # → failures / 10^6 hr
            'mtbf_hours':  1e9 / fit if fit > 0 else None,
        }
    if mtbf:
        return {
            'source':      'Texas Instruments (web)',
            'mtbf_hours':  mtbf,
            'lambda_p':    1e6 / mtbf,                  # failures / 10^6 hr
            'fit_rate':    1e9 / mtbf,
        }
    return None


def lookup_analog(part_number: str) -> dict | None:
    """Search Analog Devices product page for reliability data."""
    pn_lower = part_number.lower()
    url = f'https://www.analog.com/en/products/{pn_lower}.html'
    text = _fetch_text(url)
    if not text:
        return None

    fit = _extract_fit(text)
    mtbf = _extract_mtbf_hours(text)

    if fit:
        return {
            'source':   'Analog Devices (web)',
            'fit_rate': fit,
            'lambda_p': fit / 1000,
            'mtbf_hours': 1e9 / fit if fit > 0 else None,
        }
    if mtbf:
        return {
            'source': 'Analog Devices (web)',
            'mtbf_hours': mtbf,
            'lambda_p': 1e6 / mtbf,
            'fit_rate': 1e9 / mtbf,
        }
    return None


def lookup_mouser(part_number: str) -> dict | None:
    """Search Mouser product page for MTBF/FIT data."""
    url = f'https://www.mouser.com/Search/Refine?Keyword={part_number}'
    text = _fetch_text(url)
    if not text:
        return None

    fit = _extract_fit(text)
    mtbf = _extract_mtbf_hours(text)

    if fit:
        return {'source': 'Mouser (web)', 'fit_rate': fit,
                'lambda_p': fit / 1000,
                'mtbf_hours': 1e9 / fit if fit > 0 else None}
    if mtbf:
        return {'source': 'Mouser (web)', 'mtbf_hours': mtbf,
                'lambda_p': 1e6 / mtbf, 'fit_rate': 1e9 / mtbf}
    return None


# ──────────────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────────────

MANUFACTURER_LOOKUP = {
    'TI':              lookup_ti,
    'TEXAS INSTRUMENTS': lookup_ti,
    'ADI':             lookup_analog,
    'ANALOG DEVICES':  lookup_analog,
    'ANALOG':          lookup_analog,
    'MAXIM':           lookup_analog,   # now part of ADI
}


def lookup_component(part_number: str,
                     manufacturer: str = '',
                     try_all: bool = True) -> dict | None:
    """
    Try manufacturer-specific lookup first, then generic lookups.
    Returns reliability dict or None if nothing found.
    """
    if not part_number:
        return None

    mfr_upper = (manufacturer or '').upper().strip()

    # Try matched manufacturer first
    func = MANUFACTURER_LOOKUP.get(mfr_upper)
    if func:
        result = func(part_number)
        if result:
            logger.info('Found %s data for %s from %s',
                        result.get('source'), part_number, mfr_upper)
            return result

    if try_all:
        # Try all manufacturer lookups in priority order
        for mfr_key, lookup_fn in MANUFACTURER_LOOKUP.items():
            if lookup_fn == func:
                continue  # already tried
            result = lookup_fn(part_number)
            if result:
                logger.info('Found data for %s via %s', part_number, mfr_key)
                return result

        # Last resort: Mouser
        result = lookup_mouser(part_number)
        if result:
            return result

    logger.debug('No web reliability data found for %s', part_number)
    return None
