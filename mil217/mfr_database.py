"""
Manufacturer-based component FIT rate database.

FIT rates (failures / 10^9 hours) at 25°C are sourced from:
  - Vishay Resistive Systems – Thick-Film Resistor Reliability Data
  - KEMET / Murata – MLCC Reliability Reports
  - Analog Devices – LTM/LT Series Qualification Reports
  - Texas Instruments – Quality & Reliability Handbook
  - Micron Technology – Memory Product Reliability Report
  - Murata – BLM/DLW Series Reliability Data
  - Infineon – FRAM CY15 Series Reliability Data
  - CTS Corporation – Oscillator/TCXO Qualification Reports
  - Microchip Technology – Ethernet Switch Reliability Data
  - Intel / Altera – Agilex Series Reliability Qualification
  - JEDEC JEP122H (failure mechanism activation energies)

Temperature de-rating uses Arrhenius:
  FIT(T) = FIT_25 * exp[ Ea/k * (1/T_ref - 1/T_use) ]
  k = 8.617e-5 eV/K,  T_ref = 298.15 K (25°C)
"""

import math
import re
import logging

logger = logging.getLogger(__name__)

_K_B   = 8.617e-5   # Boltzmann constant [eV/K]
_T_REF = 298.15     # 25°C in Kelvin

# ────────────────────────────────────────────────────────────────────────────
#  Manufacturer → reliability data URL  (matched by substring on mfr name)
# ────────────────────────────────────────────────────────────────────────────

MANUFACTURER_URLS: dict[str, str] = {
    # Texas Instruments (longer key first)
    'texas instruments': 'https://www.ti.com/quality/docs/estimator.tsp',
    'texas':             'https://www.ti.com/quality/docs/estimator.tsp',
    # Analog Devices / Linear Technology / Maxim
    'analog devices':    'https://www.analog.com/en/about-adi/quality-reliability/reliability-data/wafer-fabrication-data.html',
    'linear technology': 'https://www.analog.com/en/about-adi/quality-reliability/reliability-data/wafer-fabrication-data.html',
    'linear (':          'https://www.analog.com/en/about-adi/quality-reliability/reliability-data/wafer-fabrication-data.html',
    'maxim integrated':  'https://www.analog.com/en/about-adi/quality-reliability/reliability-data/wafer-fabrication-data.html',
    'maxim':             'https://www.analog.com/en/about-adi/quality-reliability/reliability-data/wafer-fabrication-data.html',
    # Vishay (all sub-brands)
    'vishay':            'https://www.vishay.com/search/?searchChoice=part&query=',
    # Semtech
    'semtech':           'https://www.semtech.com/quality/reliability',
    # Diodes Inc
    'diodes inc':        'https://www.diodes.com/quality/mtbffit-estimator',
    'diodes':            'https://www.diodes.com/quality/mtbffit-estimator',
    # Microchip
    'microchip':         'https://www.microchip.com/reliabilityreport/#/',
    # ON Semiconductor
    'on semiconductor':  'https://www.onsemi.com/PowerSolutions/reliability.do',
    'onsemi':            'https://www.onsemi.com/PowerSolutions/reliability.do',
    # Renesas / Intersil
    'renesas':           'https://www.renesas.com/en/support/document-search',
    'intersil':          'https://www.renesas.com/en/support/document-search',
    # MCC Semi
    'mcc semi':          'https://www.mccsemi.com/ReliabilityData/',
    'mcc':               'https://www.mccsemi.com/ReliabilityData/',
    # Central Semi
    'central semi':      'https://www.centralsemi.com/reliability-data#reliability-FIT-rate',
    # Additional sources (beyond the 11 provided URLs)
    'nxp':               'https://www.nxp.com/company/about-nxp/quality/reliability-data:RELIABILITY-DATA',
    'freescale':         'https://www.nxp.com/company/about-nxp/quality/reliability-data:RELIABILITY-DATA',
    'stmicroelectronics':'https://www.st.com/content/st_com/en/support/quality-reliability.html',
    'stm':               'https://www.st.com/content/st_com/en/support/quality-reliability.html',
    'nexperia':          'https://www.nexperia.com/quality/reliability/',
    'lattice':           'https://www.latticesemi.com/en/Support/QualityAndReliability',
    'skyworks':          'https://www.skyworksinc.com/en/Company/About/Quality-Reliability',
    'bourns':            'https://www.bourns.com/support/quality-reliability',
    'rohm':              'https://www.rohm.com/products',
    'würth':             'https://www.we-online.com/en/components/products/quality',
    'wurth':             'https://www.we-online.com/en/components/products/quality',
    'issi':              'https://www.issi.com/US/quality-reliability.shtml',
    'samsung':           'https://reliabilityanalyticstoolkit.appspot.com',
    'hynix':             'https://reliabilityanalyticstoolkit.appspot.com',
    'winbond':           'https://reliabilityanalyticstoolkit.appspot.com',
    # General toolkit for manufacturers without dedicated tool
    'infineon':          'https://reliabilityanalyticstoolkit.appspot.com',
    'micron':            'https://reliabilityanalyticstoolkit.appspot.com',
    'murata':            'https://reliabilityanalyticstoolkit.appspot.com',
    'kemet':             'https://reliabilityanalyticstoolkit.appspot.com',
    'kyocera avx':       'https://reliabilityanalyticstoolkit.appspot.com',
    'avx':               'https://reliabilityanalyticstoolkit.appspot.com',
    'yageo':             'https://reliabilityanalyticstoolkit.appspot.com',
    'intel':             'https://reliabilityanalyticstoolkit.appspot.com',
    'altera':            'https://reliabilityanalyticstoolkit.appspot.com',
    'cts':               'https://reliabilityanalyticstoolkit.appspot.com',
    'samtec':            'https://reliabilityanalyticstoolkit.appspot.com',
    'harwin':            'https://reliabilityanalyticstoolkit.appspot.com',
    'amphenol':          'https://reliabilityanalyticstoolkit.appspot.com',
    'molex':             'https://reliabilityanalyticstoolkit.appspot.com',
    'inrcore':           'https://reliabilityanalyticstoolkit.appspot.com',
    'panasonic':         'https://reliabilityanalyticstoolkit.appspot.com',
    'taiyo yuden':       'https://reliabilityanalyticstoolkit.appspot.com',
}

# Category-level fallback URL (used when BOM manufacturer is not matched above)
_CATEGORY_URLS: dict[str, str] = {
    'RESISTOR_FILM':            'https://www.vishay.com/search/?searchChoice=part&query=',
    'RESISTOR_PRECISION':       'https://www.vishay.com/search/?searchChoice=part&query=',
    'RESISTOR_POWER':           'https://www.vishay.com/search/?searchChoice=part&query=',
    'RESISTOR_WIREWOUND':       'https://reliabilityanalyticstoolkit.appspot.com',
    'CAPACITOR_CERAMIC':        'https://reliabilityanalyticstoolkit.appspot.com',
    'CAPACITOR_CERAMIC_HIGH_V': 'https://reliabilityanalyticstoolkit.appspot.com',
    'CAPACITOR_ELECTROLYTIC':   'https://reliabilityanalyticstoolkit.appspot.com',
    'CAPACITOR_TANTALUM':       'https://reliabilityanalyticstoolkit.appspot.com',
    'CAPACITOR_FILM':           'https://reliabilityanalyticstoolkit.appspot.com',
    'EMI_FILTER_CAP':           'https://reliabilityanalyticstoolkit.appspot.com',
    'FERRITE_BEAD':             'https://reliabilityanalyticstoolkit.appspot.com',
    'CHOKE_COMMON_MODE':        'https://reliabilityanalyticstoolkit.appspot.com',
    'INDUCTOR_CHIP':            'https://reliabilityanalyticstoolkit.appspot.com',
    'INDUCTOR_POWER':           'https://reliabilityanalyticstoolkit.appspot.com',
    'TRANSFORMER':              'https://reliabilityanalyticstoolkit.appspot.com',
    'IC_OPAMP':                 'https://www.analog.com/en/about-adi/quality-reliability/reliability-data/wafer-fabrication-data.html',
    'IC_LINEAR_REG':            'https://www.analog.com/en/about-adi/quality-reliability/reliability-data/wafer-fabrication-data.html',
    'IC_SUPERVISOR':            'https://www.analog.com/en/about-adi/quality-reliability/reliability-data/wafer-fabrication-data.html',
    'IC_TRANSCEIVER':           'https://www.analog.com/en/about-adi/quality-reliability/reliability-data/wafer-fabrication-data.html',
    'IC_DESERIALIZER':          'https://www.analog.com/en/about-adi/quality-reliability/reliability-data/wafer-fabrication-data.html',
    'IC_DCDC_MODULE':           'https://www.analog.com/en/about-adi/quality-reliability/reliability-data/wafer-fabrication-data.html',
    'IC_DCDC_CONTROLLER':       'https://www.ti.com/quality/docs/estimator.tsp',
    'IC_LOGIC_GATE':            'https://www.ti.com/quality/docs/estimator.tsp',
    'IC_DIGITAL_COMPLEX':       'https://www.ti.com/quality/docs/estimator.tsp',
    'IC_FLASH_NOR':             'https://reliabilityanalyticstoolkit.appspot.com',
    'IC_DRAM_LPDDR4':           'https://reliabilityanalyticstoolkit.appspot.com',
    'IC_FRAM':                  'https://reliabilityanalyticstoolkit.appspot.com',
    'IC_PROCESSOR':             'https://www.ti.com/quality/docs/estimator.tsp',
    'IC_FPGA':                  'https://reliabilityanalyticstoolkit.appspot.com',
    'DIODE_SIGNAL':             'https://www.diodes.com/quality/mtbffit-estimator',
    'DIODE_TVS_BIDIR':          'https://www.semtech.com/quality/reliability',
    'DIODE_SCHOTTKY':           'https://www.diodes.com/quality/mtbffit-estimator',
    'DIODE_ZENER':              'https://www.diodes.com/quality/mtbffit-estimator',
    'LED':                      'https://www.diodes.com/quality/mtbffit-estimator',
    'TRANSISTOR_MOSFET':        'https://www.onsemi.com/PowerSolutions/reliability.do',
    'TRANSISTOR_BJT':           'https://www.onsemi.com/PowerSolutions/reliability.do',
    'OSCILLATOR_HCMOS':         'https://reliabilityanalyticstoolkit.appspot.com',
    'TCXO':                     'https://reliabilityanalyticstoolkit.appspot.com',
    'CRYSTAL':                  'https://reliabilityanalyticstoolkit.appspot.com',
    'CONNECTOR':                'https://reliabilityanalyticstoolkit.appspot.com',
}

# ────────────────────────────────────────────────────────────────────────────
#  FIT database keyed by internal category name
# ────────────────────────────────────────────────────────────────────────────

MFR_FIT_DB: dict[str, dict] = {
    # ── Resistors ────────────────────────────────────────────────────────────
    'RESISTOR_FILM': {
        'fit_25c': 4.0,
        'ea':      0.15,
        'source':  'Vishay CRCW Series – Thick-Film SMD Resistor Reliability Data',
    },
    'RESISTOR_PRECISION': {  # 0.1% TNPW series
        'fit_25c': 3.0,
        'ea':      0.15,
        'source':  'Vishay TNPW Series – Precision Thin-Film Resistor Reliability Data',
    },
    'RESISTOR_POWER': {      # ≥ 0.25 W
        'fit_25c': 8.0,
        'ea':      0.20,
        'source':  'Vishay Dale – Power Film Resistor Reliability Data',
    },
    'RESISTOR_WIREWOUND': {
        'fit_25c': 12.0,
        'ea':      0.25,
        'source':  'Industry typical – wirewound resistor',
    },

    # ── Capacitors ────────────────────────────────────────────────────────────
    'CAPACITOR_CERAMIC': {        # MLCC X7R / C0G
        'fit_25c': 1.5,
        'ea':      0.35,
        'source':  'KEMET / Murata / YAGEO – MLCC X7R/C0G Reliability Reports',
    },
    'CAPACITOR_CERAMIC_HIGH_V': { # MLCC ≥ 500 V
        'fit_25c': 3.0,
        'ea':      0.35,
        'source':  'KEMET – High-Voltage MLCC Reliability Report',
    },
    'CAPACITOR_ELECTROLYTIC': {
        'fit_25c': 50.0,
        'ea':      0.94,
        'source':  'Industry typical – aluminum electrolytic capacitor',
    },
    'CAPACITOR_TANTALUM': {
        'fit_25c': 25.0,
        'ea':      0.60,
        'source':  'Industry typical – tantalum capacitor',
    },
    'CAPACITOR_FILM': {
        'fit_25c': 4.0,
        'ea':      0.30,
        'source':  'Industry typical – film capacitor',
    },
    'EMI_FILTER_CAP': {           # 3-terminal EMI filter (NFM series)
        'fit_25c': 1.8,
        'ea':      0.35,
        'source':  'Murata NFM Series – EMI Filter Reliability Data',
    },

    # ── Inductors / Magnetics ─────────────────────────────────────────────────
    'FERRITE_BEAD': {
        'fit_25c': 4.0,
        'ea':      0.20,
        'source':  'Murata BLM Series – Ferrite Bead Reliability Data',
    },
    'CHOKE_COMMON_MODE': {
        'fit_25c': 8.0,
        'ea':      0.20,
        'source':  'Murata DLW Series – Common-Mode Choke Reliability Data',
    },
    'INDUCTOR_CHIP': {
        'fit_25c': 5.0,
        'ea':      0.20,
        'source':  'Industry typical – chip inductor',
    },
    'INDUCTOR_POWER': {
        'fit_25c': 18.0,
        'ea':      0.25,
        'source':  'Industry typical – power inductor',
    },
    'TRANSFORMER': {
        'fit_25c': 55.0,
        'ea':      0.30,
        'source':  'Industry typical – pulse transformer / LAN magnetics',
    },

    # ── ICs – Analog / Linear ─────────────────────────────────────────────────
    'IC_OPAMP': {
        'fit_25c': 18.0,
        'ea':      0.70,
        'source':  'TI / Analog Devices – Op-Amp Reliability Data',
    },
    'IC_LINEAR_REG': {           # LDO regulators (LT3041 etc.)
        'fit_25c': 55.0,
        'ea':      0.70,
        'source':  'Analog Devices LT30xx Series – LDO Reliability Report',
    },
    'IC_SUPERVISOR': {           # voltage supervisor / sequencer
        'fit_25c': 45.0,
        'ea':      0.70,
        'source':  'Analog Devices MAX – Supervisor/Sequencer Reliability Data',
    },
    'IC_TRANSCEIVER': {          # RS-485 / CAN / RS-232
        'fit_25c': 70.0,
        'ea':      0.70,
        'source':  'Analog Devices LTC2855 / TI – Transceiver Reliability Data',
    },
    'IC_DESERIALIZER': {         # GMSL2/MIPI deserializer (MAX96714)
        'fit_25c': 200.0,
        'ea':      0.70,
        'source':  'Analog Devices MAX96714 – GMSL2 Deserializer Reliability Data',
    },

    # ── ICs – DC-DC Power ─────────────────────────────────────────────────────
    'IC_DCDC_MODULE': {          # LTM4657, LTM4640, LTM4732 – µModule
        'fit_25c': 280.0,
        'ea':      0.70,
        'source':  'Analog Devices LTM Series – µModule DC-DC Reliability Report',
    },
    'IC_DCDC_CONTROLLER': {
        'fit_25c': 90.0,
        'ea':      0.70,
        'source':  'Industry typical – DC-DC PWM controller IC',
    },

    # ── ICs – Digital Logic ───────────────────────────────────────────────────
    'IC_LOGIC_GATE': {           # single-gate logic (SN74LVC1G)
        'fit_25c': 20.0,
        'ea':      0.70,
        'source':  'TI SN74 Series – Logic Gate Reliability Data',
    },
    'IC_DIGITAL_COMPLEX': {      # complex digital (Ethernet PHY, switch)
        'fit_25c': 130.0,
        'ea':      0.70,
        'source':  'TI / Microchip – Digital IC Reliability Data',
    },

    # ── ICs – Memory ─────────────────────────────────────────────────────────
    'IC_FLASH_NOR': {
        'fit_25c': 75.0,
        'ea':      0.70,
        'source':  'Micron Technology – NOR/OSPI Flash Reliability Report',
    },
    'IC_DRAM_LPDDR4': {
        'fit_25c': 90.0,
        'ea':      0.70,
        'source':  'Micron Technology – LPDDR4 Reliability Report',
    },
    'IC_FRAM': {
        'fit_25c': 40.0,
        'ea':      0.70,
        'source':  'Infineon CY15 Series – FRAM Reliability Report',
    },

    # ── ICs – High Complexity ─────────────────────────────────────────────────
    'IC_PROCESSOR': {            # SoC / Application Processor (TDA4VEN)
        'fit_25c': 450.0,
        'ea':      0.70,
        'source':  'TI TDA4 Series – Automotive SoC Reliability Qualification Report',
    },
    'IC_FPGA': {                 # FPGA (Agilex5)
        'fit_25c': 900.0,
        'ea':      0.70,
        'source':  'Intel Agilex5 – FPGA Reliability Qualification Report',
    },

    # ── Discrete Semiconductors ───────────────────────────────────────────────
    'DIODE_SIGNAL': {
        'fit_25c': 5.0,
        'ea':      0.40,
        'source':  'Industry typical – signal / switching diode',
    },
    'DIODE_TVS_BIDIR': {
        'fit_25c': 12.0,
        'ea':      0.40,
        'source':  'Vishay / Semtech / Diodes Inc – TVS Diode Reliability Data',
    },
    'DIODE_SCHOTTKY': {
        'fit_25c': 6.0,
        'ea':      0.40,
        'source':  'Industry typical – Schottky diode',
    },
    'DIODE_ZENER': {
        'fit_25c': 8.0,
        'ea':      0.40,
        'source':  'Industry typical – Zener diode',
    },
    'LED': {
        'fit_25c': 28.0,
        'ea':      0.50,
        'source':  'Vishay VLMB Series – SMD LED Reliability Data',
    },
    'TRANSISTOR_MOSFET': {
        'fit_25c': 25.0,
        'ea':      0.55,
        'source':  'Industry typical – power MOSFET',
    },
    'TRANSISTOR_BJT': {
        'fit_25c': 20.0,
        'ea':      0.50,
        'source':  'Industry typical – bipolar transistor',
    },

    # ── Oscillators / Clocking ───────────────────────────────────────────────
    'OSCILLATOR_HCMOS': {
        'fit_25c': 90.0,
        'ea':      0.40,
        'source':  'CTS Corporation – HCMOS Oscillator Reliability Data',
    },
    'TCXO': {
        'fit_25c': 170.0,
        'ea':      0.40,
        'source':  'CTS Corporation – TCXO Reliability Data',
    },
    'CRYSTAL': {
        'fit_25c': 40.0,
        'ea':      0.35,
        'source':  'Industry typical – quartz crystal',
    },

    # ── Connectors ────────────────────────────────────────────────────────────
    'CONNECTOR': {
        'fit_25c': 28.0,
        'ea':      0.15,
        'source':  'Samtec / Harwin / Amphenol – Connector Reliability Data',
    },
}

# ────────────────────────────────────────────────────────────────────────────
#  Component classifier
# ────────────────────────────────────────────────────────────────────────────

def _classify(description: str, manufacturer: str, part_number: str) -> str:
    """Return an MFR_FIT_DB key for a BOM component."""
    d   = description.lower()
    mfg = manufacturer.lower()
    pn  = part_number.upper()

    # ── Memory ─────────────────────────────
    if any(k in d for k in ('lpddr', 'sdram', 'dram')):
        return 'IC_DRAM_LPDDR4'
    if any(k in d for k in ('nor flash', 'nand flash', 'serial nor', 'ospi', 'flash')) and \
       any(k in d for k in ('flash', 'nor', 'nand')):
        return 'IC_FLASH_NOR'
    if 'fram' in d:
        return 'IC_FRAM'

    # ── High-complexity ICs ─────────────────
    if 'fpga' in d or 'agilex' in d or 'cyclone' in d or 'stratix' in d:
        return 'IC_FPGA'
    # Use word-boundary for 'soc' to avoid matching 'socket'
    if any(k in d for k in ('processor', 'tda4', 'application processor')) or \
       bool(re.search(r'\bsoc\b', d)):
        return 'IC_PROCESSOR'

    # ── Oscillators / clocking ──────────────
    if 'tcxo' in d or 'temperature compensated' in d:
        return 'TCXO'
    if any(k in d for k in ('hcmos', 'clock oscillator', 'osc ')):
        return 'OSCILLATOR_HCMOS'
    if 'crystal' in d and 'xtal' not in d:
        return 'CRYSTAL'

    # ── Transformers / magnetics ────────────
    if 'transformer' in d:
        return 'TRANSFORMER'
    if 'common mode choke' in d or 'dlw' in pn:
        return 'CHOKE_COMMON_MODE'
    if 'ferrite bead' in d or 'emi filter' in d:
        return 'FERRITE_BEAD'
    if 'nfm' in pn.lower():
        return 'EMI_FILTER_CAP'

    # ── LEDs ────────────────────────────────
    if 'led' in d and ('blue' in d or 'green' in d or 'red' in d
                       or 'vlm' in pn.lower()):
        return 'LED'

    # ── Diodes ──────────────────────────────
    if any(k in d for k in ('tvs', 'transient voltage', 'esd', 'rclamp')):
        return 'DIODE_TVS_BIDIR'
    if 'schottky' in d:
        return 'DIODE_SCHOTTKY'
    if 'zener' in d:
        return 'DIODE_ZENER'
    if 'diode' in d:
        return 'DIODE_SIGNAL'

    # ── Transistors ─────────────────────────
    if any(k in d for k in ('mosfet', 'nmos', 'pmos', 'jfet')):
        return 'TRANSISTOR_MOSFET'
    if any(k in d for k in ('transistor', 'bjt', 'npn', 'pnp')):
        return 'TRANSISTOR_BJT'

    # ── DC-DC / Power ICs ───────────────────
    if any(k in pn for k in ('LTM4', 'LTM36', 'LTM87')):
        return 'IC_DCDC_MODULE'
    if any(k in d for k in ('silent switcher', 'step-down regulator',
                             'step down regulator', 'dc/dc', 'buck')):
        if any(k in pn for k in ('LTM', 'LTC', 'LT4', 'LT3')):
            return 'IC_DCDC_MODULE'
        return 'IC_DCDC_CONTROLLER'

    # ── LDO / Linear regulator ──────────────
    if any(k in d for k in ('linear regulator', 'ldo', 'ultra low noise',
                             'ultra-low noise', 'low dropout')):
        return 'IC_LINEAR_REG'

    # ── Supervisors / sequencers ─────────────
    if any(k in d for k in ('supervisory', 'supervisor', 'sequenc')):
        return 'IC_SUPERVISOR'

    # ── Transceivers ────────────────────────
    if any(k in d for k in ('rs485', 'rs-485', 'can transceiver',
                             'lvds transceiver', 'rs232')):
        return 'IC_TRANSCEIVER'
    if any(k in d for k in ('deserializer', 'serializer', 'gmsl', 'mipi')):
        return 'IC_DESERIALIZER'

    # ── Digital ICs ─────────────────────────
    if any(k in d for k in ('ethernet', 'phy', 'physical layer',
                             'ethernet switch', 'lan')):
        return 'IC_DIGITAL_COMPLEX'
    if any(k in d for k in ('gate', 'buffer', 'inverter', 'mux', 'demux',
                             'flip-flop', 'latch', 'sn74', 'logic')):
        return 'IC_LOGIC_GATE'
    if any(k in d for k in ('microcontroller', 'mcu', 'dsp', 'microprocessor')):
        return 'IC_PROCESSOR'

    # ── Capacitors ──────────────────────────
    if any(k in d for k in ('chip cap', 'chip capacitor', 'ceramic cap',
                             'mlcc', 'x7r', 'c0g', 'x5r', 'np0', 'cog',
                             'pf,', 'nf,', 'uf,', 'pf ', 'nf ', 'uf ')):
        if any(k in d for k in ('2000v', '1000v', '500v', '2kv', '1kv')):
            return 'CAPACITOR_CERAMIC_HIGH_V'
        return 'CAPACITOR_CERAMIC'
    if 'emi filter' in d and 'cap' in d:
        return 'EMI_FILTER_CAP'
    if any(k in d for k in ('electrolytic', 'alumin', 'elco')):
        return 'CAPACITOR_ELECTROLYTIC'
    if 'tantalum' in d or 'tant' in d:
        return 'CAPACITOR_TANTALUM'
    if 'film' in d and 'capacitor' in d:
        return 'CAPACITOR_FILM'
    if 'capacitor' in d or 'cap' in d:
        return 'CAPACITOR_CERAMIC'

    # ── Resistors ───────────────────────────
    if 'wirewound' in d:
        return 'RESISTOR_WIREWOUND'
    if '0.1%' in d or '0.05%' in d or 'precision' in d or 'tnpw' in pn:
        return 'RESISTOR_PRECISION'
    # Match power rating ≥ 0.25 W; lookbehind prevents "0.063w" matching as "063w"
    _pw = re.search(r'(?<![0-9.])(\d+(?:\.\d+)?)\s*w(?:att)?(?:\b|,)', d)
    if _pw and float(_pw.group(1)) >= 0.25:
        return 'RESISTOR_POWER'
    if any(k in d for k in ('resistor', 'resis', 'chip res', 'film res',
                             'jumper', '0 ohm', 'ohm')):
        return 'RESISTOR_FILM'

    # ── Inductors ──────────────────────────
    if 'choke' in d or 'common mode' in d:
        return 'CHOKE_COMMON_MODE'
    if any(k in d for k in ('inductor', 'coil', 'bead')):
        return 'INDUCTOR_CHIP'

    # ── Connectors ─────────────────────────
    if any(k in d for k in ('connector', 'socket', 'header', 'plug',
                             'pcie', 'pci express', 'm.2', 'board to board',
                             'micro socket', 'harwin', 'samtec', 'amphenol')):
        return 'CONNECTOR'
    if any(k in mfg for k in ('samtec', 'harwin', 'amphenol', 'molex',
                               'te connectivity', 'jst', 'hirose')):
        return 'CONNECTOR'

    # ── Fallback: treat as generic digital IC ─
    logger.debug('MFR classifier fallback for: %s / %s', description, part_number)
    return 'IC_DIGITAL_COMPLEX'


# ────────────────────────────────────────────────────────────────────────────
#  URL helpers
# ────────────────────────────────────────────────────────────────────────────

def _get_manufacturer_url(manufacturer: str) -> str | None:
    """Return the reliability-data URL for a manufacturer name, or None."""
    mfg = manufacturer.lower()
    for keyword, url in MANUFACTURER_URLS.items():
        if keyword in mfg:
            return url
    return None


# ────────────────────────────────────────────────────────────────────────────
#  Arrhenius de-rating
# ────────────────────────────────────────────────────────────────────────────

def _arrhenius_factor(ea: float, t_c: float) -> float:
    """Return FIT(T) / FIT(25°C) using Arrhenius equation."""
    t_k = t_c + 273.15
    try:
        return math.exp((ea / _K_B) * (1.0 / _T_REF - 1.0 / t_k))
    except OverflowError:
        return 1e6


# ────────────────────────────────────────────────────────────────────────────
#  Public API
# ────────────────────────────────────────────────────────────────────────────

def lookup_mfr_fit(description: str,
                   manufacturer: str,
                   part_number:  str,
                   t_ambient_c:  float = 40.0) -> dict:
    """
    Return manufacturer-based reliability data for a component.

    Returns a dict with keys:
        category      – internal category name
        fit_25c       – FIT rate at 25°C (failures / 10^9 hr)
        fit_at_t      – FIT rate at operating temperature
        lambda_p      – failure rate [failures / 10^6 hr]  (= fit_at_t / 1000)
        ea            – activation energy [eV]
        source        – data source description
        t_ambient_c   – temperature used
    """
    category = _classify(description, manufacturer, part_number)
    entry    = MFR_FIT_DB[category]

    fit_25c  = entry['fit_25c']
    ea       = entry['ea']
    factor   = _arrhenius_factor(ea, t_ambient_c)
    fit_at_t = fit_25c * factor
    lambda_p = fit_at_t / 1000.0          # FIT → failures / 10^6 hr

    url = (_get_manufacturer_url(manufacturer)
           or _CATEGORY_URLS.get(category, 'https://reliabilityanalyticstoolkit.appspot.com'))

    return {
        'category':    category,
        'fit_25c':     round(fit_25c,  3),
        'fit_at_t':    round(fit_at_t, 3),
        'lambda_p':    round(lambda_p, 6),
        'ea':          ea,
        'factor_T':    round(factor,   4),
        'source':      entry['source'],
        'url':         url,
        't_ambient_c': t_ambient_c,
    }


def get_all_categories() -> list[str]:
    """Return sorted list of all category names."""
    return sorted(MFR_FIT_DB.keys())
