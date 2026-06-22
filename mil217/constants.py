"""
MIL-STD-217F Notice 2 Constants and Pi-Factor Tables
All failure rates are in failures / 10^6 hours
"""
import math

# ─────────────────────────────────────────────
#  ENVIRONMENT CODES  (human-readable labels)
# ─────────────────────────────────────────────
ENVIRONMENTS = {
    'GB':  'Ground, Benign',
    'GF':  'Ground, Fixed',
    'GM':  'Ground, Mobile',
    'NS':  'Naval, Sheltered',
    'NU':  'Naval, Unsheltered',
    'AIF': 'Airborne, Inhabited Fighter',
    'AUF': 'Airborne, Uninhabited Fighter',
    'AIC': 'Airborne, Inhabited Cargo',
    'ARW': 'Airborne, Rotary Wing',
    'SF':  'Space, Flight',
    'MF':  'Missile, Flight',
    'ML':  'Missile, Launch',
    'CL':  'Cannon, Launch',
}

ENVIRONMENTS_HE = {
    'GB':  'קרקעי, שגרתי',
    'GF':  'קרקעי, קבוע',
    'GM':  'קרקעי, נייד',
    'NS':  'ימי, מוגן',
    'NU':  'ימי, חשוף',
    'AIF': 'אווירי, מיושב, לוחם',
    'AUF': 'אווירי, בלתי מיושב, לוחם',
    'AIC': 'אווירי, מיושב, מ貨',
    'ARW': 'אווירי, כנף סיבובית',
    'SF':  'חלל',
    'MF':  'טיל, טיסה',
    'ML':  'טיל, שיגור',
    'CL':  'תותח, שיגור',
}

QUALITY_LEVELS = {
    'S':   'Space / JANTXV (S)',
    'B':   'Established Reliability B (0.1%)',
    'B-1': 'Established Reliability B-1 (0.5%)',
    'B-2': 'Established Reliability B-2 (1%)',
    'B-3': 'Established Reliability B-3 (2%)',
    'C':   'Commercial / Plastic (C)',
}

# ─────────────────────────────────────────────
#  TABLE 5.1-3  π_E  –  Integrated Circuits
# ─────────────────────────────────────────────
PI_E_IC = {
    'GB': 0.38, 'GF': 1.0,  'GM': 12,
    'NS': 8.0,  'NU': 12,   'AIF': 6.0,
    'AUF': 5.0, 'AIC': 4.0, 'ARW': 8.0,
    'SF': 0.5,  'MF': 16,   'ML': 3.0,
    'CL': 480,
}

# TABLE 5.1-4  π_Q  –  Integrated Circuits
PI_Q_IC = {
    'S': 0.25, 'B': 1.0, 'B-1': 2.0,
    'B-2': 5.0, 'B-3': 8.0, 'C': 14,
}

# TABLE 5.1-5  π_L  –  IC Learning Factor (years in production)
PI_L_IC = {
    '<0.5': 2.0, '0.5-2': 1.0, '>2': 0.5,
}

# TABLE 5.1-1  C_1  –  Digital IC complexity (gate equivalent count)
# key = (min_gates, max_gates), value = C_1
C1_DIGITAL = [
    (1,      100,    0.010),
    (101,    300,    0.021),
    (301,    1000,   0.042),
    (1001,   3000,   0.084),
    (3001,   10000,  0.170),
    (10001,  30000,  0.340),
    (30001,  60000,  0.680),
    (60001,  float('inf'), 1.36),
]

# TABLE 5.1-2  C_2  –  Package / pin-count factor
# key = number of pins, value = C_2
def get_c2(n_pins):
    """Return C_2 based on number of IC pins."""
    if n_pins < 1:
        n_pins = 1
    return 2.8e-4 * (n_pins ** 1.08)   # approximation from MIL-217F

def get_c1(gate_count):
    """Return C_1 based on gate-equivalent count."""
    for lo, hi, c1 in C1_DIGITAL:
        if lo <= gate_count <= hi:
            return c1
    return 1.36

# ─────────────────────────────────────────────
#  TRANSISTORS  (Table 6.1 Bipolar, 6.2 MOSFET)
# ─────────────────────────────────────────────
# π_E for transistors
PI_E_TRANSISTOR = {
    'GB': 0.20, 'GF': 1.0,  'GM': 12,
    'NS': 8.0,  'NU': 12,   'AIF': 5.0,
    'AUF': 4.0, 'AIC': 3.0, 'ARW': 8.0,
    'SF': 0.5,  'MF': 16,   'ML': 3.0,
    'CL': 360,
}

# π_Q transistors
PI_Q_TRANSISTOR = {
    'S': 0.7, 'B': 1.0, 'B-1': 2.4,
    'B-2': 5.5, 'B-3': 8.0, 'C': 19,
}

# λ_b base failure rate for BJT (Table 6.1) at 25°C junction
# key = (power_watts_max, is_high_freq), value = lambda_b
LAMBDA_B_BJT = {
    ('low', False): 0.00074,   # ≤ 0.5 W, low freq
    ('low', True):  0.00074,
    ('mid', False): 0.0012,    # 0.5–1 W
    ('mid', True):  0.0012,
    ('high', False): 0.0060,   # > 1 W
    ('high', True):  0.0060,
}

# λ_b for MOSFET (Table 6.2)
LAMBDA_B_MOSFET = {
    'low':  0.012,
    'mid':  0.012,
    'high': 0.012,
}

# ─────────────────────────────────────────────
#  DIODES  (Table 7.x)
# ─────────────────────────────────────────────
PI_E_DIODE = {
    'GB': 0.27, 'GF': 1.0,  'GM': 11,
    'NS': 7.0,  'NU': 11,   'AIF': 5.0,
    'AUF': 4.0, 'AIC': 3.0, 'ARW': 8.0,
    'SF': 0.5,  'MF': 16,   'ML': 3.0,
    'CL': 360,
}

PI_Q_DIODE = {
    'S': 0.7, 'B': 1.0, 'B-1': 2.4,
    'B-2': 5.5, 'B-3': 8.0, 'C': 19,
}

# λ_b diode types at 25°C
LAMBDA_B_DIODE = {
    'signal':     0.0040,
    'rectifier':  0.0040,
    'zener':      0.0040,
    'schottky':   0.0040,
    'led':        0.0040,
}

# ─────────────────────────────────────────────
#  RESISTORS  (Table 9.x)
# ─────────────────────────────────────────────
PI_E_RESISTOR = {
    'GB': 0.20, 'GF': 1.0,  'GM': 11,
    'NS': 7.0,  'NU': 11,   'AIF': 5.0,
    'AUF': 4.0, 'AIC': 3.0, 'ARW': 8.0,
    'SF': 0.5,  'MF': 16,   'ML': 3.0,
    'CL': 360,
}

PI_Q_RESISTOR = {
    'S': 0.030, 'B': 0.10, 'B-1': 0.30,
    'B-2': 1.0, 'B-3': 3.0, 'C': 10,
}

# λ_b for film resistors (Table 9.2) at reference conditions
LAMBDA_B_RESISTOR = {
    'film':        0.00006,
    'carbon':      0.00033,
    'wirewound':   0.00048,
    'chip':        0.00006,   # same as film
    'network':     0.00006,
}

# π_R resistance factor (Table 9.2-3)
def get_pi_r_resistor(ohms):
    """Resistance pi-factor for film/chip resistors."""
    if ohms <= 100_000:
        return 1.0
    elif ohms <= 1_000_000:
        return 1.1
    elif ohms <= 10_000_000:
        return 1.6
    else:
        return 2.5

# ─────────────────────────────────────────────
#  CAPACITORS  (Table 10.x)
# ─────────────────────────────────────────────
PI_E_CAPACITOR = {
    'GB': 0.40, 'GF': 1.0,  'GM': 10,
    'NS': 7.0,  'NU': 10,   'AIF': 5.0,
    'AUF': 4.0, 'AIC': 3.0, 'ARW': 8.0,
    'SF': 0.5,  'MF': 16,   'ML': 3.0,
    'CL': 320,
}

PI_Q_CAPACITOR = {
    'S': 0.030, 'B': 0.10, 'B-1': 0.30,
    'B-2': 1.0, 'B-3': 3.0, 'C': 10,
}

# λ_b for capacitor types
LAMBDA_B_CAPACITOR = {
    'ceramic':       0.0010,
    'film':          0.0020,
    'electrolytic':  0.0040,
    'tantalum':      0.0030,
    'mica':          0.00010,
}

def get_pi_cv_capacitor(capacitance_uf):
    """Capacitance voltage pi-factor (ceramic/film)."""
    return 0.34 * (capacitance_uf ** 0.18)

# ─────────────────────────────────────────────
#  INDUCTORS / TRANSFORMERS  (Table 11.x)
# ─────────────────────────────────────────────
PI_E_INDUCTOR = {
    'GB': 0.20, 'GF': 1.0,  'GM': 12,
    'NS': 8.0,  'NU': 12,   'AIF': 6.0,
    'AUF': 5.0, 'AIC': 4.0, 'ARW': 8.0,
    'SF': 0.5,  'MF': 16,   'ML': 3.0,
    'CL': 480,
}

PI_Q_INDUCTOR = {
    'S': 0.030, 'B': 0.10, 'B-1': 0.30,
    'B-2': 1.0, 'B-3': 3.0, 'C': 10,
}

LAMBDA_B_INDUCTOR = {
    'chip':        0.0002,
    'wirewound':   0.0006,
    'transformer': 0.0010,
}

# ─────────────────────────────────────────────
#  CONNECTORS  (Table 15.x)
# ─────────────────────────────────────────────
PI_E_CONNECTOR = {
    'GB': 0.20, 'GF': 1.0,  'GM': 8.0,
    'NS': 6.0,  'NU': 8.0,  'AIF': 4.0,
    'AUF': 3.0, 'AIC': 2.0, 'ARW': 6.0,
    'SF': 0.5,  'MF': 10,   'ML': 1.0,
    'CL': 190,
}

PI_Q_CONNECTOR = {
    'S': 0.10, 'B': 0.20, 'B-1': 0.40,
    'B-2': 1.0, 'B-3': 2.0, 'C': 5.0,
}

LAMBDA_B_CONNECTOR = 0.011   # per contact, reference conditions

# ─────────────────────────────────────────────
#  CRYSTAL OSCILLATORS  (Table 18.x)
# ─────────────────────────────────────────────
PI_E_CRYSTAL = {
    'GB': 0.21, 'GF': 1.0, 'GM': 6.0,
    'NS': 5.0,  'NU': 6.0, 'AIF': 4.0,
    'AUF': 3.0, 'AIC': 2.0,'ARW': 5.0,
    'SF': 0.4,  'MF': 12,  'ML': 2.0,
    'CL': 290,
}

PI_Q_CRYSTAL = {
    'S': 1.0, 'B': 1.0, 'B-1': 2.1,
    'B-2': 3.4, 'B-3': 5.0, 'C': 10,
}

LAMBDA_B_CRYSTAL = 0.013

# ─────────────────────────────────────────────
#  PHYSICAL CONSTANTS
# ─────────────────────────────────────────────
K_BOLTZMANN = 8.617e-5   # eV / K
T_REFERENCE = 298.0      # K  (= 25°C)

# Activation energies (eV) for temperature model
EA_IC       = 0.7
EA_TRANSISTOR = 0.7
EA_DIODE    = 0.7
EA_RESISTOR = 0.15
EA_CAPACITOR = 0.15
EA_INDUCTOR  = 0.11
EA_CRYSTAL   = 0.08


def pi_temperature(t_use_c: float, ea_ev: float, scale: float = 1.0) -> float:
    """
    Arrhenius temperature factor.
    t_use_c : junction / operating temperature in Celsius
    ea_ev   : activation energy in eV
    scale   : pre-multiplier (0.1 for ICs so πT=1 at ~50°C)
    """
    t_use_k = t_use_c + 273.15
    exponent = (ea_ev / K_BOLTZMANN) * (1.0 / T_REFERENCE - 1.0 / t_use_k)
    return scale * math.exp(exponent)
