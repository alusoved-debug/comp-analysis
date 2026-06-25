"""
Reliability Analyzer – Flask web application.
Dual analysis: Manufacturer data (internal FIT database) + MIL-STD-217F Notice 2.
"""

import os
import io
import json
import logging
import traceback
import pandas as pd
from flask import (Flask, render_template, request,
                   jsonify, send_file, session)
from werkzeug.utils import secure_filename

from mil217.calculator  import calculate_component, detect_component_type
from mil217.constants   import ENVIRONMENTS, ENVIRONMENTS_HE, QUALITY_LEVELS
from mil217.mfr_database import lookup_mfr_fit
from report.generator   import generate_comparison_report

logging.basicConfig(level=logging.INFO,
                    format='%(levelname)s %(name)s: %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXT = {'csv', 'xlsx', 'xls'}


# ─── helpers ────────────────────────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


def parse_bom(filepath: str) -> pd.DataFrame:
    """Load BOM (CSV or Excel) into a normalised DataFrame."""
    ext = filepath.rsplit('.', 1)[1].lower()
    if ext == 'csv':
        try:
            df = pd.read_csv(filepath, encoding='utf-8-sig')
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, encoding='cp1255')
    else:
        df = pd.read_excel(filepath)

    # Normalise column names
    df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]

    col_map = {
        # RefDes variants
        'ref':              'ref_des',
        'refdes':           'ref_des',
        'reference':        'ref_des',
        'reference_designator': 'ref_des',
        'ref_designator':   'ref_des',
        # Part number variants
        'part':             'part_number',
        'part_no':          'part_number',
        'part_no.':         'part_number',
        'pn':               'part_number',
        'mfg_part_no.':     'part_number',
        'mfg_part_no':      'part_number',
        'mfr_part_no':      'part_number',
        'mfr_pn':           'part_number',
        'catalog':          'catalog',
        # Manufacturer
        'mfr':              'manufacturer',
        'mfg':              'manufacturer',
        'manufacturer':     'manufacturer',
        # Description
        'desc':             'description',
        'component':        'description',
        # Quantity
        'qty':              'quantity',
        'quan.':            'quantity',
        'quan':             'quantity',
        'count':            'quantity',
        'amount':           'quantity',
        # Component type
        'type':             'comp_type',
        'component_type':   'comp_type',
        # Package / value
        'package':          'package',
        'footprint':        'package',
        'value':            'value',
    }
    df.rename(columns=col_map, inplace=True)

    # Ensure required columns exist with defaults
    for col in ['ref_des', 'part_number', 'manufacturer',
                'description', 'quantity', 'comp_type', 'value', 'package']:
        if col not in df.columns:
            df[col] = '' if col != 'quantity' else 1

    # Convert quantity to integer
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(1).astype(int)

    # Drop rows that are completely empty (header-only rows, etc.)
    data_cols = ['part_number', 'manufacturer', 'description']
    df = df[df[data_cols].apply(
        lambda r: r.astype(str).str.strip().ne('').any(), axis=1
    )]

    # If ref_des column was missing or all empty, auto-generate
    ref_col_empty = (
        df['ref_des'].astype(str).str.strip().eq('').all() or
        df['ref_des'].isna().all()
    )
    if ref_col_empty:
        df['ref_des'] = [f'COMP_{i+1}' for i in range(len(df))]

    df.reset_index(drop=True, inplace=True)
    return df


def _infer_mil217_meta(row: pd.Series) -> dict:
    """Extract component metadata for MIL-217F models from a BOM row."""
    import re
    desc  = str(row.get('description', '')).lower()
    value = str(row.get('value',       '')).lower()
    pkg   = str(row.get('package',     '')).upper()

    meta = {}

    # ── IC gate count / pin count ──────────────────────────
    if any(k in desc for k in ('fpga', 'cpld', 'agilex', 'cyclone')):
        meta['gate_count'] = 500_000
        meta['n_pins']     = 512
    elif any(k in desc for k in ('processor', 'soc', 'tda4')):
        meta['gate_count'] = 100_000
        meta['n_pins']     = 256
    elif any(k in desc for k in ('mcu', 'microcontroller', 'dsp')):
        meta['gate_count'] = 30_000
        meta['n_pins']     = 64
    elif any(k in desc for k in ('op-amp', 'opamp', 'amplifier')):
        meta['gate_count'] = 100
        meta['n_pins']     = 8
    elif any(k in desc for k in ('ldo', 'regulator', 'linear regulator')):
        meta['gate_count'] = 500
        meta['n_pins']     = 8
    else:
        meta['gate_count'] = 2_000
        meta['n_pins']     = 16

    # Package pin count override
    for m in ['LQFP', 'QFP', 'BGA', 'QFN', 'LGA', 'VPBGA']:
        if m in pkg:
            nums = re.findall(r'\d+', pkg)
            if nums:
                meta['n_pins'] = int(nums[0])
                break
    for m in ['DIP', 'SOIC', 'SSOP', 'TSSOP', 'SOP', 'UDFN', 'DFN', 'TQFN']:
        if m in pkg:
            nums = re.findall(r'\d+', pkg)
            if nums:
                meta['n_pins'] = int(nums[0])
                break

    # ── Transistor type ────────────────────────────────────
    if any(k in desc for k in ('mosfet', 'nmos', 'pmos')):
        meta['transistor_type'] = 'MOSFET'
    else:
        meta['transistor_type'] = 'BJT'
    meta['power_w'] = 0.25

    # ── Diode type ─────────────────────────────────────────
    if 'zener' in desc:
        meta['diode_type'] = 'zener'
    elif 'schottky' in desc:
        meta['diode_type'] = 'schottky'
    elif 'led' in desc:
        meta['diode_type'] = 'led'
    elif any(k in desc for k in ('tvs', 'transient')):
        meta['diode_type'] = 'tvs'
    else:
        meta['diode_type'] = 'signal'

    # ── Resistor type ──────────────────────────────────────
    if 'wirewound' in desc:
        meta['resistor_type'] = 'wirewound'
    elif 'carbon' in desc:
        meta['resistor_type'] = 'carbon'
    else:
        meta['resistor_type'] = 'film'

    # Parse resistance value from description
    rv = re.search(r'(\d+\.?\d*)\s*([kmgKMG]?)\s*[Ωo]?(?:hm)?', desc)
    if rv:
        num  = float(rv.group(1))
        mult = {'k': 1e3, 'm': 1e6, 'g': 1e9,
                'K': 1e3, 'M': 1e6, 'G': 1e9}.get(rv.group(2), 1.0)
        meta['resistance_ohms'] = num * mult
    else:
        meta['resistance_ohms'] = 10_000

    # ── Capacitor type ─────────────────────────────────────
    if any(k in desc for k in ('electrolytic', 'elco', 'alum')):
        meta['cap_type'] = 'electrolytic'
    elif any(k in desc for k in ('tantalum', 'tant')):
        meta['cap_type'] = 'tantalum'
    elif 'film' in desc and 'cap' in desc:
        meta['cap_type'] = 'film'
    elif 'mica' in desc:
        meta['cap_type'] = 'mica'
    else:
        meta['cap_type'] = 'ceramic'

    # Parse capacitance from description (e.g. "0.1uF", "10nF", "220pF")
    cv = re.search(r'(\d+\.?\d*)\s*([nuμpNUP]?[fF])', desc)
    if not cv:
        cv = re.search(r'(\d+\.?\d*)\s*([nuμpNUP]?[fF])', value)
    if cv:
        num  = float(cv.group(1))
        unit = cv.group(2).lower()
        if unit.startswith('n'):
            meta['capacitance_uf'] = num / 1000
        elif unit.startswith('p'):
            meta['capacitance_uf'] = num / 1_000_000
        elif unit.startswith('u') or unit.startswith('μ'):
            meta['capacitance_uf'] = num
        else:
            meta['capacitance_uf'] = num / 1000
    else:
        meta['capacitance_uf'] = 0.1

    # ── Inductor type ──────────────────────────────────────
    if 'transformer' in desc:
        meta['inductor_type'] = 'transformer'
    else:
        meta['inductor_type'] = 'chip'

    # ── Connector contacts ─────────────────────────────────
    nc = re.search(r'(\d+)\s*[Pp](?:in|ole|os)', desc)
    meta['n_contacts'] = int(nc.group(1)) if nc else 10

    meta['years_in_production'] = '>2'
    meta['theta_ja']  = 0
    meta['power_mw']  = 0
    return meta


# ─── Dual analysis ──────────────────────────────────────────────────────────

def analyse_bom_dual(df: pd.DataFrame, conditions: dict) -> list[dict]:
    """
    Run both MIL-217F and manufacturer-data analyses for every BOM row.
    Returns a list of result dicts (one per component row).
    """
    t_amb = conditions.get('t_ambient', 40.0)
    results = []

    for _, row in df.iterrows():
        ref_des  = str(row.get('ref_des',      '')).strip()
        part_num = str(row.get('part_number',  '')).strip()
        mfr      = str(row.get('manufacturer', '')).strip()
        desc     = str(row.get('description',  '')).strip()
        qty      = int(row.get('quantity', 1))
        raw_type = str(row.get('comp_type', '')).strip()

        comp_type = (detect_component_type(ref_des, desc)
                     if not raw_type else raw_type.upper())
        meta      = _infer_mil217_meta(row)

        # ── MIL-217F analysis ──────────────────────────────
        try:
            mil_lambda, mil_details = calculate_component(
                comp_type, conditions, meta, source_data=None
            )
        except Exception as exc:
            logger.warning('MIL-217F calc failed for %s: %s', ref_des, exc)
            mil_lambda  = 0.0
            mil_details = {'model': 'Error', 'error': str(exc)}

        # ── Manufacturer data analysis ─────────────────────
        try:
            mfr_data = lookup_mfr_fit(desc, mfr, part_num, t_amb)
            mfr_lambda = mfr_data['lambda_p']
        except Exception as exc:
            logger.warning('MFR lookup failed for %s: %s', ref_des, exc)
            mfr_data   = {'category': 'Unknown', 'fit_25c': 0,
                          'fit_at_t': 0, 'lambda_p': 0,
                          'source': 'Error', 't_ambient_c': t_amb}
            mfr_lambda = 0.0

        # ── Ratio: MIL-217F / Manufacturer ────────────────
        ratio = (mil_lambda / mfr_lambda) if mfr_lambda > 0 else None

        results.append({
            'ref_des':      ref_des,
            'part_number':  part_num,
            'manufacturer': mfr,
            'description':  desc,
            'comp_type':    comp_type,
            'quantity':     qty,

            # MIL-217F
            'mil217_lambda_p':     round(mil_lambda,  6),
            'mil217_lambda_total': round(mil_lambda * qty, 6),
            'mil217_details':      mil_details,

            # Manufacturer data
            'mfr_lambda_p':     round(mfr_lambda, 6),
            'mfr_lambda_total': round(mfr_lambda * qty, 6),
            'mfr_category':     mfr_data.get('category', ''),
            'mfr_fit_25c':      mfr_data.get('fit_25c',  0),
            'mfr_fit_at_t':     mfr_data.get('fit_at_t', 0),
            'mfr_source':       mfr_data.get('source',   ''),
            'mfr_url':          mfr_data.get('url',      ''),

            # Comparison
            'ratio_mil_to_mfr': round(ratio, 3) if ratio is not None else None,
        })

    return results


def _summary(results: list[dict], key_lambda: str, key_total: str) -> dict:
    """Compute MTBF summary for one analysis column."""
    total = sum(r.get(key_total, 0) for r in results)
    mtbf_h = (1e6 / total) if total > 0 else 999_999_999
    return {
        'total_lambda': round(total,          6),
        'fit_rate':     round(total * 1000,   2),
        'mtbf_hours':   round(mtbf_h,         0),
        'mtbf_years':   round(min(mtbf_h / 8760, 999_999), 2),
    }


# ─── Routes ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html',
                           environments=ENVIRONMENTS,
                           environments_he=ENVIRONMENTS_HE,
                           quality_levels=QUALITY_LEVELS)


@app.route('/upload', methods=['POST'])
def upload():
    if 'bom_file' not in request.files:
        return jsonify({'error': 'לא נבחר קובץ'}), 400

    f = request.files['bom_file']
    if f.filename == '' or not allowed_file(f.filename):
        return jsonify({'error': 'סוג קובץ לא נתמך. השתמש ב-CSV או XLSX'}), 400

    filename = secure_filename(f.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    f.save(filepath)

    try:
        df      = parse_bom(filepath)
        preview = df.head(6).fillna('').to_dict(orient='records')
        columns = list(df.columns)
        session['bom_path'] = filepath
        return jsonify({'ok': True, 'rows': len(df),
                        'columns': columns, 'preview': preview})
    except Exception as exc:
        logger.error(traceback.format_exc())
        return jsonify({'error': f'שגיאה בקריאת BOM: {exc}'}), 500


@app.route('/analyse', methods=['POST'])
def analyse():
    bom_path = session.get('bom_path')
    if not bom_path or not os.path.exists(bom_path):
        return jsonify({'error': 'יש להעלות קובץ BOM תחילה'}), 400

    data = request.get_json(force=True)
    conditions = {
        't_ambient':    float(data.get('t_ambient',    40)),
        'env_code':           data.get('env_code',    'GF'),
        'quality':            data.get('quality',     'C'),
        'stress_ratio': float(data.get('stress_ratio', 0.5)),
    }

    try:
        df      = parse_bom(bom_path)
        results = analyse_bom_dual(df, conditions)
    except Exception as exc:
        logger.error(traceback.format_exc())
        return jsonify({'error': f'שגיאת חישוב: {exc}'}), 500

    mil_summary = _summary(results, 'mil217_lambda_p', 'mil217_lambda_total')
    mfr_summary = _summary(results, 'mfr_lambda_p',    'mfr_lambda_total')

    # Save to file (session cookies have a 4KB limit; dual-analysis results exceed it)
    results_path    = os.path.join(app.config['UPLOAD_FOLDER'], '_last_results.json')
    conditions_path = os.path.join(app.config['UPLOAD_FOLDER'], '_last_conditions.json')
    with open(results_path,    'w', encoding='utf-8') as f:
        json.dump(results,    f, ensure_ascii=False)
    with open(conditions_path, 'w', encoding='utf-8') as f:
        json.dump(conditions, f, ensure_ascii=False)
    session['results_path']    = results_path
    session['conditions_path'] = conditions_path

    return jsonify({
        'ok':         True,
        'results':    results,
        'mil217':     mil_summary,
        'mfr':        mfr_summary,
    })


@app.route('/report', methods=['POST'])
def report():
    results_path    = session.get('results_path')
    conditions_path = session.get('conditions_path')
    if not results_path or not os.path.exists(results_path):
        return 'אין נתוני ניתוח. אנא הפעל ניתוח תחילה.', 400

    with open(results_path,    encoding='utf-8') as f:
        results    = json.load(f)
    with open(conditions_path, encoding='utf-8') as f:
        conditions = json.load(f)

    data = request.get_json(force=True) or {}
    project_info = {
        'project_name': data.get('project_name', 'ניתוח אמינות'),
        'doc_number':   data.get('doc_number',   'REL-001'),
        'prepared_by':  data.get('prepared_by',  '—'),
        'revision':     data.get('revision',     'A'),
    }

    try:
        docx_bytes = generate_comparison_report(results, conditions, project_info)
    except Exception as exc:
        logger.error(traceback.format_exc())
        return f'שגיאה ביצירת הדוח: {exc}', 500

    return send_file(
        io.BytesIO(docx_bytes),
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        as_attachment=True,
        download_name='Reliability_Report_Comparison.docx',
    )


@app.route('/sample_bom')
def sample_bom():
    csv_content = (
        'Quan.,Description,Mfg,Mfg Part No.\n'
        '10,SMT CHIP RESISTOR 10 KOhm 1% 0.063W T&R,VISHAY RESISTIVE SYSTEMS,CRCW040210K0FKTD\n'
        '5,SMT CHIP CAPACITOR 100nF 10% 16V X7R T&R,MURATA,GRM033Z71C104KE14D\n'
        '2,DC/DC 20VIN 20A STEP-DOWN REGULATOR BGA49,ANALOG DEVICES,LTM4657IY\n'
        '1,10/100 Mbps ETHERNET PHY TRANSCEIVER,TEXAS INSTRUMENTS INC,DP83822HRHBR\n'
        '1,AGILEX5 E FPGA 656K VPBGA839,INTEL,A5EC065BB23AI6X\n'
        '4,RS485 TRANSCEIVER 3.3V,LINEAR (Analog Devices),LTC2855HDE#PBF\n'
        '12,CHIP EMI FILTER FERRITE BEAD 120 Ohm,MURATA MANUFACTURING CO. LTD,BLM15PX121SN1D\n'
        '3,SMT TRANSFORMER 10/100BASE-TX SINGLE-PORT,INRCORE,100B-1003XNL\n'
        '1,LPDDR4 SDRAM 4GB AUTOMOTIVE TFBGA200,MICRON TECHNOLOGY,MT53E1G32D2FW-046AAT:C\n'
        '2,OSC 25.0 MHz -40 to +105,CTS,625L3G25M00000\n'
        '1,SMT HCMOS CRYSTAL TCXO 40 MHz 3.3V,CTS,536EL400X2GT5\n'
        '4,DIODE TVS 440W 5.5V Bidirectional,DIODES INC,D5V0S1B2LP\n'
        '2,LED BLUE 0402 SMD,VISHAY SEMICONDUCTOR,VLMB1500-GS08\n'
        '2,CONNECTOR BOARD TO BOARD 40P 0.80MM,SAMTEC,QTE-020-05-L-D-A-K\n'
        '1,FRAM 2MBIT SPI 50MHZ 1.8V DFN8,INFINEON TECHNOLOGIES AG,CY15V102QN-50LHXI\n'
    )
    return send_file(
        io.BytesIO(csv_content.encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='sample_bom.csv',
    )


if __name__ == "__main__":
    # app.run(host="127.0.0.1", port=5050) #run locally
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=False)
