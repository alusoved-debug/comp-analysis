"""
MIL-STD-217F Notice 2 – Failure Rate Calculator
Returns λ_p in failures / 10^6 hours for each component.
"""
from .constants import (
    PI_E_IC, PI_Q_IC, PI_L_IC, get_c1, get_c2,
    PI_E_TRANSISTOR, PI_Q_TRANSISTOR, LAMBDA_B_BJT, LAMBDA_B_MOSFET,
    PI_E_DIODE, PI_Q_DIODE, LAMBDA_B_DIODE,
    PI_E_RESISTOR, PI_Q_RESISTOR, LAMBDA_B_RESISTOR, get_pi_r_resistor,
    PI_E_CAPACITOR, PI_Q_CAPACITOR, LAMBDA_B_CAPACITOR, get_pi_cv_capacitor,
    PI_E_INDUCTOR, PI_Q_INDUCTOR, LAMBDA_B_INDUCTOR,
    PI_E_CONNECTOR, PI_Q_CONNECTOR, LAMBDA_B_CONNECTOR,
    PI_E_CRYSTAL, PI_Q_CRYSTAL, LAMBDA_B_CRYSTAL,
    EA_IC, EA_TRANSISTOR, EA_DIODE, EA_RESISTOR, EA_CAPACITOR,
    EA_INDUCTOR, EA_CRYSTAL,
    pi_temperature,
)

# ─── helpers ────────────────────────────────────────────────────────────────

def _env(env_code, table):
    return table.get(env_code, table.get('GF', 1.0))

def _qual(quality_code, table):
    return table.get(quality_code, table.get('C', 10))


# ─── IC (Monolithic Digital / Linear) ───────────────────────────────────────

def calc_ic(t_junction_c, env_code, quality_code,
            gate_count=1000, n_pins=16,
            years_in_production='>2', source_data=None):
    """
    MIL-217F Section 5.1 – Monolithic IC
    Returns (lambda_p, details_dict)
    """
    C1  = get_c1(gate_count)
    C2  = get_c2(n_pins)
    piT = pi_temperature(t_junction_c, EA_IC, scale=0.1)
    piE = _env(env_code,    PI_E_IC)
    piQ = _qual(quality_code, PI_Q_IC)
    piL = PI_L_IC.get(years_in_production, 0.5)

    lambda_p = (C1 * piT + C2 * piE) * piQ * piL

    details = {
        'model':   'MIL-217F §5.1 Monolithic IC',
        'C1':       round(C1, 5),
        'C2':       round(C2, 5),
        'piT':      round(piT, 4),
        'piE':      piE,
        'piQ':      piQ,
        'piL':      piL,
        'lambda_b': round(C1 * piT + C2 * piE, 6),
    }
    return round(lambda_p, 6), details


# ─── Transistor ─────────────────────────────────────────────────────────────

def calc_transistor(t_junction_c, env_code, quality_code,
                    transistor_type='BJT', power_w=0.25,
                    stress_ratio=0.5, source_data=None):
    """
    MIL-217F Section 6 – Discrete Transistor
    """
    if power_w <= 0.5:
        pw = 'low'
    elif power_w <= 1.0:
        pw = 'mid'
    else:
        pw = 'high'

    if transistor_type.upper() in ('MOSFET', 'FET', 'JFET', 'NMOS', 'PMOS'):
        lambda_b = LAMBDA_B_MOSFET[pw]
    else:
        lambda_b = LAMBDA_B_BJT.get((pw, False), 0.00074)

    piT = pi_temperature(t_junction_c, EA_TRANSISTOR)
    piE = _env(env_code,    PI_E_TRANSISTOR)
    piQ = _qual(quality_code, PI_Q_TRANSISTOR)
    piA = 1.5 if power_w > 1.0 else 1.0      # application factor
    piS = max(0.1, stress_ratio ** 2.66)       # stress ratio factor

    lambda_p = lambda_b * piT * piA * piS * piQ * piE

    details = {
        'model':    'MIL-217F §6 Transistor',
        'lambda_b': round(lambda_b, 6),
        'piT':      round(piT, 4),
        'piE':      piE,
        'piQ':      piQ,
        'piA':      piA,
        'piS':      round(piS, 4),
    }
    return round(lambda_p, 6), details


# ─── Diode ──────────────────────────────────────────────────────────────────

def calc_diode(t_junction_c, env_code, quality_code,
               diode_type='signal', stress_ratio=0.5, source_data=None):
    """MIL-217F Section 7 – Diode"""
    lambda_b = LAMBDA_B_DIODE.get(diode_type.lower(), 0.0040)
    piT  = pi_temperature(t_junction_c, EA_DIODE)
    piE  = _env(env_code,    PI_E_DIODE)
    piQ  = _qual(quality_code, PI_Q_DIODE)
    piS  = stress_ratio ** 2.43
    piC  = 1.0       # construction complexity; 1.0 = standard

    lambda_p = lambda_b * piT * piS * piC * piQ * piE

    details = {
        'model':    'MIL-217F §7 Diode',
        'lambda_b': round(lambda_b, 6),
        'piT':      round(piT, 4),
        'piE':      piE,
        'piQ':      piQ,
        'piS':      round(piS, 4),
        'piC':      piC,
    }
    return round(lambda_p, 6), details


# ─── Resistor ───────────────────────────────────────────────────────────────

def calc_resistor(t_ambient_c, env_code, quality_code,
                  resistor_type='film', resistance_ohms=10000,
                  stress_ratio=0.5, source_data=None):
    """MIL-217F Section 9 – Fixed Resistor"""
    lambda_b = LAMBDA_B_RESISTOR.get(resistor_type.lower(), LAMBDA_B_RESISTOR['film'])
    piT  = pi_temperature(t_ambient_c, EA_RESISTOR)
    piR  = get_pi_r_resistor(resistance_ohms)
    piE  = _env(env_code,    PI_E_RESISTOR)
    piQ  = _qual(quality_code, PI_Q_RESISTOR)

    lambda_p = lambda_b * piT * piR * piQ * piE

    details = {
        'model':    'MIL-217F §9 Resistor',
        'lambda_b': round(lambda_b, 6),
        'piT':      round(piT, 4),
        'piR':      piR,
        'piE':      piE,
        'piQ':      piQ,
    }
    return round(lambda_p, 6), details


# ─── Capacitor ──────────────────────────────────────────────────────────────

def calc_capacitor(t_ambient_c, env_code, quality_code,
                   cap_type='ceramic', capacitance_uf=0.1,
                   stress_ratio=0.5, source_data=None):
    """MIL-217F Section 10 – Capacitor"""
    lambda_b = LAMBDA_B_CAPACITOR.get(cap_type.lower(), LAMBDA_B_CAPACITOR['ceramic'])
    piT  = pi_temperature(t_ambient_c, EA_CAPACITOR)
    piCV = get_pi_cv_capacitor(max(capacitance_uf, 1e-6))
    piE  = _env(env_code,    PI_E_CAPACITOR)
    piQ  = _qual(quality_code, PI_Q_CAPACITOR)
    piSR = stress_ratio ** 3.0   # voltage stress factor

    lambda_p = lambda_b * piCV * piQ * piE * piT * (1 + piSR)

    details = {
        'model':    'MIL-217F §10 Capacitor',
        'lambda_b': round(lambda_b, 6),
        'piCV':     round(piCV, 4),
        'piT':      round(piT, 4),
        'piE':      piE,
        'piQ':      piQ,
    }
    return round(lambda_p, 6), details


# ─── Inductor / Transformer ──────────────────────────────────────────────────

def calc_inductor(t_ambient_c, env_code, quality_code,
                  inductor_type='chip', source_data=None):
    """MIL-217F Section 11 – Inductor"""
    lambda_b = LAMBDA_B_INDUCTOR.get(inductor_type.lower(), LAMBDA_B_INDUCTOR['chip'])
    piT  = pi_temperature(t_ambient_c, EA_INDUCTOR)
    piE  = _env(env_code,    PI_E_INDUCTOR)
    piQ  = _qual(quality_code, PI_Q_INDUCTOR)

    lambda_p = lambda_b * piT * piQ * piE

    details = {
        'model':    'MIL-217F §11 Inductor',
        'lambda_b': round(lambda_b, 6),
        'piT':      round(piT, 4),
        'piE':      piE,
        'piQ':      piQ,
    }
    return round(lambda_p, 6), details


# ─── Connector ──────────────────────────────────────────────────────────────

def calc_connector(t_ambient_c, env_code, quality_code,
                   n_contacts=10, source_data=None):
    """MIL-217F Section 15 – Connector"""
    lambda_b = LAMBDA_B_CONNECTOR * max(n_contacts, 1)
    piT  = pi_temperature(t_ambient_c, EA_INDUCTOR)   # low Ea
    piE  = _env(env_code,    PI_E_CONNECTOR)
    piQ  = _qual(quality_code, PI_Q_CONNECTOR)
    piP  = max(1, n_contacts) ** 0.51   # pin count factor

    lambda_p = lambda_b * piE * piQ * piP

    details = {
        'model':    'MIL-217F §15 Connector',
        'lambda_b': round(lambda_b, 6),
        'piE':      piE,
        'piQ':      piQ,
        'piP':      round(piP, 3),
        'n_contacts': n_contacts,
    }
    return round(lambda_p, 6), details


# ─── Crystal Oscillator ──────────────────────────────────────────────────────

def calc_crystal(t_ambient_c, env_code, quality_code, source_data=None):
    """MIL-217F Section 18 – Crystal Oscillator"""
    lambda_b = LAMBDA_B_CRYSTAL
    piE  = _env(env_code,    PI_E_CRYSTAL)
    piQ  = _qual(quality_code, PI_Q_CRYSTAL)
    piT  = pi_temperature(t_ambient_c, EA_CRYSTAL)

    lambda_p = lambda_b * piT * piQ * piE

    details = {
        'model':    'MIL-217F §18 Crystal',
        'lambda_b': round(lambda_b, 6),
        'piT':      round(piT, 4),
        'piE':      piE,
        'piQ':      piQ,
    }
    return round(lambda_p, 6), details


# ─── Dispatch by component type ──────────────────────────────────────────────

COMP_TYPE_ALIASES = {
    'ic':          'IC',
    'u':           'IC',
    'mcu':         'IC',
    'mpu':         'IC',
    'dsp':         'IC',
    'fpga':        'IC',
    'cpld':        'IC',
    'op-amp':      'IC',
    'opamp':       'IC',
    'regulator':   'IC',
    'voltage reg': 'IC',
    'transistor':  'TRANSISTOR',
    'q':           'TRANSISTOR',
    'mosfet':      'TRANSISTOR',
    'bjt':         'TRANSISTOR',
    'jfet':        'TRANSISTOR',
    'fet':         'TRANSISTOR',
    'diode':       'DIODE',
    'd':           'DIODE',
    'zener':       'DIODE',
    'schottky':    'DIODE',
    'led':         'DIODE',
    'tvs':         'DIODE',
    'resistor':    'RESISTOR',
    'r':           'RESISTOR',
    'res':         'RESISTOR',
    'capacitor':   'CAPACITOR',
    'c':           'CAPACITOR',
    'cap':         'CAPACITOR',
    'inductor':    'INDUCTOR',
    'l':           'INDUCTOR',
    'transformer': 'INDUCTOR',
    'fl':          'INDUCTOR',
    'fb':          'INDUCTOR',  # ferrite bead
    'connector':   'CONNECTOR',
    'j':           'CONNECTOR',
    'p':           'CONNECTOR',
    'crystal':     'CRYSTAL',
    'xtal':        'CRYSTAL',
    'y':           'CRYSTAL',
    'x':           'CRYSTAL',
    'oscillator':  'CRYSTAL',
}

def detect_component_type(ref_des: str, description: str = '') -> str:
    """Infer canonical component type from reference designator and description."""
    import re
    prefix = ''
    for ch in ref_des.upper():
        if ch.isalpha():
            prefix += ch
        else:
            break
    prefix = prefix.strip().lower()

    # Description matching: only use keywords ≥ 3 chars to avoid false
    # substring hits (e.g. 'ic' inside 'ceramic', 'r' inside 'resistor').
    # Match against whole words only.
    desc_lower = (description or '').lower()
    desc_words = set(re.findall(r'[a-z]+', desc_lower))
    for kw, ctype in COMP_TYPE_ALIASES.items():
        if len(kw) < 3:
            continue
        # exact word match or contained multi-word phrase
        if kw in desc_words or (len(kw) > 4 and kw in desc_lower):
            return ctype

    # Fall back to RefDes prefix (exact match; 1–2 char keys live here)
    return COMP_TYPE_ALIASES.get(prefix, 'IC')


def calculate_component(comp_type: str, conditions: dict,
                         component_meta: dict, source_data=None):
    """
    Main entry point.
    conditions keys: t_ambient, env_code, quality, stress_ratio
    component_meta: gate_count, n_pins, resistance, capacitance, etc.
    Returns (lambda_p_per_1M_hrs, details_dict)
    """
    t  = conditions.get('t_ambient', 40.0)
    tj = t + component_meta.get('theta_ja', 0) * component_meta.get('power_mw', 0) / 1000
    env = conditions.get('env_code', 'GF')
    q   = conditions.get('quality',  'C')
    sr  = conditions.get('stress_ratio', 0.5)

    ct = comp_type.upper()

    if ct == 'IC':
        return calc_ic(
            t_junction_c   = tj,
            env_code       = env,
            quality_code   = q,
            gate_count     = component_meta.get('gate_count', 1000),
            n_pins         = component_meta.get('n_pins', 16),
            years_in_production = component_meta.get('years_in_production', '>2'),
            source_data    = source_data,
        )
    elif ct == 'TRANSISTOR':
        return calc_transistor(
            t_junction_c   = tj,
            env_code       = env,
            quality_code   = q,
            transistor_type= component_meta.get('transistor_type', 'BJT'),
            power_w        = component_meta.get('power_w', 0.25),
            stress_ratio   = sr,
            source_data    = source_data,
        )
    elif ct == 'DIODE':
        return calc_diode(
            t_junction_c   = tj,
            env_code       = env,
            quality_code   = q,
            diode_type     = component_meta.get('diode_type', 'signal'),
            stress_ratio   = sr,
            source_data    = source_data,
        )
    elif ct == 'RESISTOR':
        return calc_resistor(
            t_ambient_c    = t,
            env_code       = env,
            quality_code   = q,
            resistor_type  = component_meta.get('resistor_type', 'film'),
            resistance_ohms= component_meta.get('resistance_ohms', 10000),
            stress_ratio   = sr,
            source_data    = source_data,
        )
    elif ct == 'CAPACITOR':
        return calc_capacitor(
            t_ambient_c    = t,
            env_code       = env,
            quality_code   = q,
            cap_type       = component_meta.get('cap_type', 'ceramic'),
            capacitance_uf = component_meta.get('capacitance_uf', 0.1),
            stress_ratio   = sr,
            source_data    = source_data,
        )
    elif ct == 'INDUCTOR':
        return calc_inductor(
            t_ambient_c    = t,
            env_code       = env,
            quality_code   = q,
            inductor_type  = component_meta.get('inductor_type', 'chip'),
            source_data    = source_data,
        )
    elif ct == 'CONNECTOR':
        return calc_connector(
            t_ambient_c    = t,
            env_code       = env,
            quality_code   = q,
            n_contacts     = component_meta.get('n_contacts', 10),
            source_data    = source_data,
        )
    elif ct == 'CRYSTAL':
        return calc_crystal(
            t_ambient_c    = t,
            env_code       = env,
            quality_code   = q,
            source_data    = source_data,
        )
    else:
        # Unknown: use IC model as fallback
        return calc_ic(tj, env, q, source_data=source_data)
