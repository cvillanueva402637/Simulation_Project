"""
=============================================================================
  ENTITIES — Kidney and Patient Entity Definitions
=============================================================================
  Arena Analogy:  These are the "Entities" flowing through the model.
  - KidneyOrgan:  Perishable entity with cold-ischemia clock
  - Patient:      Waitlisted entity with priority attributes
=============================================================================
"""

import math
import random
from dataclasses import dataclass, field
from typing import Optional
from config import (
    BLOOD_TYPE_DIST, NUM_HLA_ANTIGENS, URGENCY_LEVELS,
    MAX_COLD_ISCHEMIA_TIME, QUALITY_DECAY_RATE
)


def _random_blood_type(rng: random.Random) -> str:
    """Sample a blood type from the US population distribution."""
    r = rng.random()
    cumulative = 0.0
    for bt, prob in BLOOD_TYPE_DIST.items():
        cumulative += prob
        if r <= cumulative:
            return bt
    return list(BLOOD_TYPE_DIST.keys())[-1]


def _random_hla_profile(rng: random.Random) -> list[int]:
    """Generate a random HLA antigen profile (each antigen 1–20)."""
    return [rng.randint(1, 20) for _ in range(NUM_HLA_ANTIGENS)]


def _random_urgency(rng: random.Random) -> str:
    """Sample a UNOS-style urgency level."""
    r = rng.random()
    cumulative = 0.0
    for level, info in URGENCY_LEVELS.items():
        cumulative += info["prob"]
        if r <= cumulative:
            return level
    return list(URGENCY_LEVELS.keys())[-1]


# ─── Kidney Organ Entity ───────────────────────────────────────────────

@dataclass
class KidneyOrgan:
    """
    Arena Entity: Kidney organ from a deceased or living donor.
    
    Attributes mirror Arena "Assign" module variables:
      - entity_id:        Unique serial number
      - blood_type:       ABO blood group
      - hla_profile:      6-antigen HLA typing
      - donor_type:       "Deceased" or "Living"
      - harvest_time:     Simulation time when organ was procured
      - max_viable_time:  Maximum cold ischemia time (hours)
      - quality:          Current quality score [0, 1]
      - matched_patient:  Patient entity matched to (if any)
      - status:           Current state in the flowchart
      - zone:             Transport distance zone
    """
    entity_id:       int
    blood_type:      str
    hla_profile:     list[int]
    donor_type:      str             = "Deceased"
    harvest_time:    float           = 0.0
    max_viable_time: float           = MAX_COLD_ISCHEMIA_TIME
    quality:         float           = 1.0
    matched_patient: Optional[object] = None
    status:          str             = "Harvested"
    zone:            str             = "Local"
    disposed_reason: str             = ""

    # ── Arena-style tracking attributes ──
    time_enter_system: float = 0.0
    time_matched:      float = 0.0
    time_exit_system:  float = 0.0

    def current_quality(self, current_time: float) -> float:
        """Exponential quality decay model: Q(t) = exp(-λ·Δt)."""
        elapsed = current_time - self.harvest_time
        self.quality = math.exp(-QUALITY_DECAY_RATE * elapsed)
        return self.quality

    def is_viable(self, current_time: float) -> bool:
        """Check if organ is still within cold ischemia window."""
        return (current_time - self.harvest_time) < self.max_viable_time

    def cold_ischemia_elapsed(self, current_time: float) -> float:
        """Hours since harvest."""
        return current_time - self.harvest_time

    @classmethod
    def generate(cls, entity_id: int, sim_time: float,
                 rng: random.Random, donor_type: str = "Deceased"):
        """Factory: Create module analog — generate a new kidney entity."""
        return cls(
            entity_id=entity_id,
            blood_type=_random_blood_type(rng),
            hla_profile=_random_hla_profile(rng),
            donor_type=donor_type,
            harvest_time=sim_time,
            time_enter_system=sim_time,
        )


# ─── Patient Entity ────────────────────────────────────────────────────

@dataclass
class Patient:
    """
    Arena Entity: Patient on the kidney transplant waitlist.
    
    Attributes:
      - entity_id:      Unique serial number
      - blood_type:     ABO blood group
      - hla_profile:    6-antigen HLA typing
      - urgency:        UNOS urgency level
      - time_on_list:   When patient joined waitlist
      - age:            Patient age (affects priority)
      - pra:            Panel Reactive Antibody % (sensitization)
      - status:         Current state
      - is_active:      Still on waitlist?
    """
    entity_id:      int
    blood_type:     str
    hla_profile:    list[int]
    urgency:        str             = "Medium"
    time_on_list:   float           = 0.0
    age:            int             = 45
    pra:            float           = 0.0    # 0–100%, higher = harder to match
    status:         str             = "Waiting"
    is_active:      bool            = True
    matched_kidney: Optional[object] = None
    disposed_reason: str            = ""

    # ── Arena-style tracking ──
    time_enter_system: float = 0.0
    time_matched:      float = 0.0
    time_exit_system:  float = 0.0

    def priority_score(self, current_time: float) -> float:
        """
        UNOS-style composite priority score.
        Higher = more urgent.
        """
        urgency_weight = URGENCY_LEVELS[self.urgency]["weight"]
        wait_days = (current_time - self.time_on_list) / 24.0
        # Sensitized patients (high PRA) get a bonus
        pra_bonus = self.pra / 100.0
        return (urgency_weight * 10) + (wait_days * 0.5) + (pra_bonus * 5)

    @classmethod
    def generate(cls, entity_id: int, sim_time: float, rng: random.Random):
        """Factory: Create module analog — generate a new patient entity."""
        return cls(
            entity_id=entity_id,
            blood_type=_random_blood_type(rng),
            hla_profile=_random_hla_profile(rng),
            urgency=_random_urgency(rng),
            time_on_list=sim_time,
            age=rng.randint(18, 75),
            pra=rng.uniform(0, 100),
            time_enter_system=sim_time,
        )


# ─── Helper: HLA Match Score ──────────────────────────────────────────

def hla_match_score(kidney: KidneyOrgan, patient: Patient) -> int:
    """Count the number of matching HLA antigens (0–6)."""
    return sum(k == p for k, p in zip(kidney.hla_profile, patient.hla_profile))


def is_blood_compatible(donor_type: str, recipient_type: str) -> bool:
    """Check ABO blood-type compatibility."""
    from config import BLOOD_COMPATIBILITY
    return recipient_type in BLOOD_COMPATIBILITY.get(donor_type, [])
