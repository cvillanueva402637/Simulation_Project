"""
=============================================================================
  KIDNEY TRANSPLANT LOGISTICS & PERISHABLE QUEUEING SIMULATION
  Configuration Parameters
=============================================================================
  Arena-Style Discrete-Event Simulation in Python (SimPy)
=============================================================================
"""

# ─── Simulation Control ────────────────────────────────────────────────
SIM_DURATION          = 365 * 24          # hours  (1 year)
NUM_REPLICATIONS      = 10                # number of independent runs
WARM_UP_PERIOD        = 30 * 24           # hours  (30-day warm-up, stats discarded)
RANDOM_SEED_BASE      = 42                # base seed for reproducibility

# ─── Entity Arrival Rates ──────────────────────────────────────────────
# Kidney donor arrivals (deceased donors)
KIDNEY_ARRIVAL_RATE   = 1 / 8.0           # kidneys per hour (~3 per day)

# Patient arrivals to waitlist
PATIENT_ARRIVAL_RATE  = 1 / 4.0           # patients per hour (~6 per day)

# Living donor arrivals (pre-scheduled, lower rate)
LIVING_DONOR_RATE     = 1 / 48.0          # ~0.5 per day

# ─── Organ Perishability (Cold Ischemia Time) ──────────────────────────
MAX_COLD_ISCHEMIA_TIME = 36.0             # hours - absolute max viability
IDEAL_COLD_ISCHEMIA    = 24.0             # hours - ideal transplant window
# Quality decay model: Q(t) = exp(-decay_rate * t)
QUALITY_DECAY_RATE     = 0.05             # per hour

# ─── Blood Type Distribution (US Population) ───────────────────────────
BLOOD_TYPE_DIST = {
    "O":  0.44,
    "A":  0.42,
    "B":  0.10,
    "AB": 0.04,
}

# Blood type compatibility matrix (donor → recipient)
BLOOD_COMPATIBILITY = {
    "O":  ["O", "A", "B", "AB"],     # universal donor
    "A":  ["A", "AB"],
    "B":  ["B", "AB"],
    "AB": ["AB"],                      # can only give to AB
}

# ─── HLA Matching ──────────────────────────────────────────────────────
NUM_HLA_ANTIGENS      = 6                 # standard 6-antigen match
HLA_MATCH_THRESHOLD   = 0                 # minimum antigens matched to proceed

# ─── Patient Priority / Urgency ────────────────────────────────────────
# UNOS-style urgency levels
URGENCY_LEVELS = {
    "Critical":  {"weight": 4, "prob": 0.10},
    "High":      {"weight": 3, "prob": 0.25},
    "Medium":    {"weight": 2, "prob": 0.40},
    "Low":       {"weight": 1, "prob": 0.25},
}

# ─── Resources ─────────────────────────────────────────────────────────
NUM_OPERATING_ROOMS   = 4                 # OR capacity
NUM_SURGICAL_TEAMS    = 5                 # surgical team capacity
NUM_TRANSPORT_VEHICLES = 3                # organ transport vehicles (helicopters/vans)
NUM_CROSSMATCH_LABS   = 2                 # crossmatch testing labs

# ─── Process Times (hours) — Triangular distributions (min, mode, max)──
CROSSMATCH_TIME       = (1.0, 2.0, 4.0)    # lab crossmatch testing
TRANSPORT_TIME        = (0.5, 2.0, 6.0)    # organ transport
SURGERY_PREP_TIME     = (0.5, 1.0, 2.0)    # pre-surgery preparation
SURGERY_TIME          = (2.0, 3.5, 6.0)    # actual transplant surgery
RECOVERY_TIME         = (12.0, 24.0, 48.0) # post-surgery recovery (ties up OR)

# ─── Transport Distance Zones ──────────────────────────────────────────
DISTANCE_ZONES = {
    "Local":    {"prob": 0.40, "time_range": (0.5, 1.0, 2.0)},
    "Regional": {"prob": 0.35, "time_range": (1.5, 3.0, 5.0)},
    "National": {"prob": 0.25, "time_range": (3.0, 5.0, 8.0)},
}

# ─── Graft Outcome Probabilities ──────────────────────────────────────
BASE_SUCCESS_RATE     = 0.95              # base transplant success rate
HLA_BONUS_PER_MATCH   = 0.005            # additional success per HLA match
COLD_ISCHEMIA_PENALTY  = 0.01            # reduction per hour of cold ischemia
MIN_SUCCESS_RATE       = 0.70             # floor for success probability

# ─── Patient Attrition (while waiting) ─────────────────────────────────
PATIENT_DEATH_RATE     = 0.0001           # per hour while on waitlist
PATIENT_TRANSFER_RATE  = 0.00005          # per hour (leaves system)

# ─── Animation / Reporting ─────────────────────────────────────────────
REPORT_INTERVAL       = 24                # hours between status snapshots
ANIMATION_SPEED       = 1.0               # time scaling for visual output
