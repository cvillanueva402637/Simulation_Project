"""
=============================================================================
  SIMULATION ENGINE — Arena-Style Discrete-Event Simulation using SimPy
=============================================================================
  This is the CORE engine.  It mirrors Arena's flowchart logic:

    ┌─────────┐   ┌────────┐   ┌───────┐   ┌──────────┐   ┌─────────┐
    │ CREATE  │──▶│ ASSIGN │──▶│ MATCH │──▶│ CROSSMATCH│──▶│TRANSPORT│
    │ Kidney  │   │ Attribs│   │ Decide│   │  Process  │   │ Process │
    └─────────┘   └────────┘   └───────┘   └──────────┘   └─────────┘
                                   │                             │
                                   │ No Match                    ▼
                                   ▼                       ┌──────────┐
                              ┌─────────┐                  │ SURGERY  │
                              │ DISPOSE │                  │ Process  │
                              │ Expired │                  └──────────┘
                              └─────────┘                       │
                                                                ▼
    ┌─────────┐                                           ┌──────────┐
    │ CREATE  │  (patients enter waitlist independently)   │ DISPOSE  │
    │ Patient │                                           │ Success/ │
    └─────────┘                                           │ Failure  │
                                                          └──────────┘
=============================================================================
"""

import random
import math
import simpy
from typing import Optional

from config import (
    KIDNEY_ARRIVAL_RATE, PATIENT_ARRIVAL_RATE, LIVING_DONOR_RATE,
    MAX_COLD_ISCHEMIA_TIME, IDEAL_COLD_ISCHEMIA,
    BLOOD_COMPATIBILITY, HLA_MATCH_THRESHOLD,
    NUM_OPERATING_ROOMS, NUM_SURGICAL_TEAMS,
    NUM_TRANSPORT_VEHICLES, NUM_CROSSMATCH_LABS,
    CROSSMATCH_TIME, TRANSPORT_TIME, SURGERY_PREP_TIME,
    SURGERY_TIME, RECOVERY_TIME, DISTANCE_ZONES,
    BASE_SUCCESS_RATE, HLA_BONUS_PER_MATCH,
    COLD_ISCHEMIA_PENALTY, MIN_SUCCESS_RATE,
    PATIENT_DEATH_RATE, PATIENT_TRANSFER_RATE,
    WARM_UP_PERIOD, REPORT_INTERVAL, URGENCY_LEVELS,
)
from entities import KidneyOrgan, Patient, hla_match_score, is_blood_compatible
from statistics_collector import StatisticsCollector


def triangular(rng: random.Random, params: tuple) -> float:
    """Sample from a triangular distribution (min, mode, max)."""
    lo, mode, hi = params
    return rng.triangular(lo, hi, mode)


class KidneyTransplantSimulation:
    """
    Main simulation class — the Arena "Model".
    
    Contains all SimPy processes (Arena modules) and resources.
    """

    def __init__(self, env: simpy.Environment, rng: random.Random,
                 stats: StatisticsCollector, run_id: int = 0, verbose: bool = False):
        self.env = env
        self.rng = rng
        self.stats = stats
        self.run_id = run_id
        self.verbose = verbose

        # ── Arena Resources ──
        self.operating_rooms     = simpy.Resource(env, capacity=NUM_OPERATING_ROOMS)
        self.surgical_teams      = simpy.Resource(env, capacity=NUM_SURGICAL_TEAMS)
        self.transport_vehicles  = simpy.Resource(env, capacity=NUM_TRANSPORT_VEHICLES)
        self.crossmatch_labs     = simpy.Resource(env, capacity=NUM_CROSSMATCH_LABS)

        # ── Queues (Arena Hold / Queue modules) ──
        self.waitlist: list[Patient] = []       # patient waitlist (priority queue)
        self.organ_pool: list[KidneyOrgan] = [] # available organs waiting for match

        # ── Entity counters ──
        self.kidney_counter = 0
        self.patient_counter = 0

        # ── Start all Arena "Create" module processes ──
        self.env.process(self._create_kidney_arrivals())
        self.env.process(self._create_patient_arrivals())
        self.env.process(self._create_living_donor_arrivals())
        self.env.process(self._patient_attrition_process())
        self.env.process(self._organ_expiry_checker())
        self.env.process(self._periodic_reporter())

    # ===================================================================
    #  CREATE MODULES — Entity Generation
    # ===================================================================

    def _create_kidney_arrivals(self):
        """
        Arena CREATE Module: Deceased Donor Kidney Arrivals
        Inter-arrival time: Exponential(1/KIDNEY_ARRIVAL_RATE)
        """
        while True:
            inter_arrival = self.rng.expovariate(KIDNEY_ARRIVAL_RATE)
            yield self.env.timeout(inter_arrival)

            self.kidney_counter += 1
            kidney = KidneyOrgan.generate(
                entity_id=self.kidney_counter,
                sim_time=self.env.now,
                rng=self.rng,
                donor_type="Deceased"
            )

            if self.env.now >= WARM_UP_PERIOD:
                self.stats.total_kidneys_arrived.increment()

            self._log(f"[CREATE] Kidney #{kidney.entity_id} arrived "
                      f"(Type {kidney.blood_type}, Donor: {kidney.donor_type})")

            # Enter the matching flowchart
            self.env.process(self._kidney_flowchart(kidney))

    def _create_patient_arrivals(self):
        """
        Arena CREATE Module: Patient Arrivals to Waitlist
        Inter-arrival time: Exponential(1/PATIENT_ARRIVAL_RATE)
        """
        while True:
            inter_arrival = self.rng.expovariate(PATIENT_ARRIVAL_RATE)
            yield self.env.timeout(inter_arrival)

            self.patient_counter += 1
            patient = Patient.generate(
                entity_id=self.patient_counter,
                sim_time=self.env.now,
                rng=self.rng,
            )

            if self.env.now >= WARM_UP_PERIOD:
                self.stats.total_patients_arrived.increment()

            self._log(f"[CREATE] Patient #{patient.entity_id} joined waitlist "
                      f"(Type {patient.blood_type}, Urgency: {patient.urgency})")

            # Add to waitlist
            self.waitlist.append(patient)
            self._update_queue_stats()

            # Check if any available organ can match this new patient
            self._try_match_from_pool()

    def _create_living_donor_arrivals(self):
        """
        Arena CREATE Module: Living Donor Kidney Arrivals (pre-scheduled)
        These bypass the matching queue — they come with a specific recipient.
        """
        while True:
            inter_arrival = self.rng.expovariate(LIVING_DONOR_RATE)
            yield self.env.timeout(inter_arrival)

            self.kidney_counter += 1
            kidney = KidneyOrgan.generate(
                entity_id=self.kidney_counter,
                sim_time=self.env.now,
                rng=self.rng,
                donor_type="Living"
            )

            if self.env.now >= WARM_UP_PERIOD:
                self.stats.total_kidneys_arrived.increment()
                self.stats.living_donor_transplants.increment()

            self._log(f"[CREATE] Living Donor Kidney #{kidney.entity_id} arrived")

            # Living donor: skip matching, go straight to crossmatch + surgery
            # Create a synthetic matched patient
            self.patient_counter += 1
            patient = Patient.generate(
                entity_id=self.patient_counter,
                sim_time=self.env.now,
                rng=self.rng,
            )
            patient.blood_type = kidney.blood_type  # guaranteed compatible
            patient.urgency = "High"

            if self.env.now >= WARM_UP_PERIOD:
                self.stats.total_patients_arrived.increment()

            kidney.matched_patient = patient
            patient.matched_kidney = kidney
            kidney.status = "Matched"
            patient.status = "Matched"
            kidney.time_matched = self.env.now
            patient.time_matched = self.env.now

            self.env.process(self._transplant_process(kidney, patient))

    # ===================================================================
    #  KIDNEY FLOWCHART — Main organ processing logic
    # ===================================================================

    def _kidney_flowchart(self, kidney: KidneyOrgan):
        """
        Arena Flowchart for a deceased-donor kidney:
          ASSIGN → DECIDE (match?) → PROCESS (crossmatch, transport, surgery) → DISPOSE
        """
        # ── ASSIGN Module: Determine transport zone ──
        kidney.zone = self._assign_transport_zone()
        self._log(f"[ASSIGN] Kidney #{kidney.entity_id} zone = {kidney.zone}")

        # ── DECIDE Module: Try to find a compatible patient ──
        matched_patient = self._find_best_match(kidney)

        if matched_patient is None:
            # No immediate match — add to organ pool and wait
            self.organ_pool.append(kidney)
            kidney.status = "In Pool"
            self._update_queue_stats()
            self._log(f"[DECIDE] Kidney #{kidney.entity_id} → No match, entering organ pool")
            return  # organ stays in pool; expiry checker will handle timeout

        # ── Match found! ──
        self._execute_match(kidney, matched_patient)
        yield self.env.process(self._transplant_process(kidney, matched_patient))

    def _try_match_from_pool(self):
        """When a new patient arrives, check if any pooled organ matches."""
        if not self.organ_pool or not self.waitlist:
            return

        matched_pairs = []
        for kidney in list(self.organ_pool):
            if not kidney.is_viable(self.env.now):
                continue
            patient = self._find_best_match(kidney)
            if patient:
                matched_pairs.append((kidney, patient))

        for kidney, patient in matched_pairs:
            if kidney in self.organ_pool:
                self.organ_pool.remove(kidney)
            self._execute_match(kidney, patient)
            self.env.process(self._transplant_process(kidney, patient))
            self._update_queue_stats()

    # ===================================================================
    #  MATCHING LOGIC — Arena DECIDE Module
    # ===================================================================

    def _find_best_match(self, kidney: KidneyOrgan) -> Optional[Patient]:
        """
        Arena DECIDE Module: Find best compatible patient on waitlist.
        Uses UNOS-style allocation: blood compatibility → HLA → priority score.
        """
        candidates = []
        for patient in self.waitlist:
            if not patient.is_active:
                continue
            # Blood type compatibility check
            if not is_blood_compatible(kidney.blood_type, patient.blood_type):
                continue
            # HLA matching
            hla = hla_match_score(kidney, patient)
            if hla < HLA_MATCH_THRESHOLD:
                continue
            # PRA-based crossmatch probability (high PRA → might fail virtual crossmatch)
            if patient.pra > 80 and self.rng.random() < (patient.pra / 200.0):
                continue  # virtual crossmatch fail
            score = patient.priority_score(self.env.now) + hla * 2
            candidates.append((score, patient, hla))

        if not candidates:
            return None

        # Sort by score (highest first)
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def _execute_match(self, kidney: KidneyOrgan, patient: Patient):
        """Record a match between kidney and patient."""
        kidney.matched_patient = patient
        patient.matched_kidney = kidney
        kidney.status = "Matched"
        patient.status = "Matched"
        kidney.time_matched = self.env.now
        patient.time_matched = self.env.now
        patient.is_active = False

        if patient in self.waitlist:
            self.waitlist.remove(patient)

        self._log(f"[MATCH] Kidney #{kidney.entity_id} <-> Patient #{patient.entity_id} "
                  f"(HLA={hla_match_score(kidney, patient)})")

    # ===================================================================
    #  TRANSPLANT PROCESS — Arena PROCESS Modules (Seize-Delay-Release)
    # ===================================================================

    def _transplant_process(self, kidney: KidneyOrgan, patient: Patient):
        """
        Arena PROCESS chain:
          1. Crossmatch Lab (Seize lab, Delay, Release)
          2. Transport (Seize vehicle, Delay, Release)  
          3. Viability Check (Decide — still viable?)
          4. Surgery (Seize OR + Team, Delay, Release)
          5. Outcome (Decide — success or rejection?)
          6. Dispose
        """
        now = self.env.now
        in_warm = now >= WARM_UP_PERIOD

        # ── PROCESS 1: Crossmatch Testing ──
        kidney.status = "Crossmatch Testing"
        self._log(f"[PROCESS] Kidney #{kidney.entity_id} → Crossmatch Lab queue")

        with self.crossmatch_labs.request() as req:
            yield req
            self._update_resource_stats()
            cm_time = triangular(self.rng, CROSSMATCH_TIME)
            yield self.env.timeout(cm_time)
            if in_warm:
                self.stats.crossmatch_time.record(cm_time)

        self._update_resource_stats()
        self._log(f"[PROCESS] Kidney #{kidney.entity_id} — Crossmatch done ({cm_time:.1f}h)")

        # ── DECIDE: Crossmatch result (simplified) ──
        crossmatch_fail_prob = 0.05 + (patient.pra / 500.0) if patient else 0.05
        if self.rng.random() < crossmatch_fail_prob:
            kidney.status = "Crossmatch Failed"
            kidney.disposed_reason = "Positive Crossmatch"
            if in_warm:
                self.stats.organs_no_match.increment()
            self._log(f"[DECIDE] Kidney #{kidney.entity_id} — Crossmatch POSITIVE → Dispose")
            self._dispose_kidney(kidney, "Crossmatch Failed")
            return

        # ── PROCESS 2: Organ Transport ──
        kidney.status = "In Transport"
        zone_info = DISTANCE_ZONES[kidney.zone]
        transport_params = zone_info["time_range"]

        self._log(f"[PROCESS] Kidney #{kidney.entity_id} → Transport ({kidney.zone})")

        with self.transport_vehicles.request() as req:
            yield req
            self._update_resource_stats()
            t_time = triangular(self.rng, transport_params)
            yield self.env.timeout(t_time)
            if in_warm:
                self.stats.transport_time.record(t_time)

        self._update_resource_stats()
        self._log(f"[PROCESS] Kidney #{kidney.entity_id} — Transported ({t_time:.1f}h)")

        # ── DECIDE: Viability check after transport ──
        if not kidney.is_viable(self.env.now):
            kidney.status = "Expired"
            kidney.disposed_reason = "Cold Ischemia Exceeded"
            if in_warm:
                self.stats.organs_expired.increment()
                cit = kidney.cold_ischemia_elapsed(self.env.now)
                self.stats.organ_cold_ischemia_time.record(cit)
            self._log(f"[DECIDE] Kidney #{kidney.entity_id} — EXPIRED during transport!")
            self._dispose_kidney(kidney, "Expired")
            # Patient goes back to waitlist
            if patient:
                patient.is_active = True
                patient.status = "Waiting"
                patient.matched_kidney = None
                self.waitlist.append(patient)
                self._update_queue_stats()
            return

        # ── PROCESS 3: Surgery Preparation ──
        kidney.status = "Surgery Prep"
        self._log(f"[PROCESS] Kidney #{kidney.entity_id} → Surgery prep")
        prep_time = triangular(self.rng, SURGERY_PREP_TIME)
        yield self.env.timeout(prep_time)

        # ── DECIDE: Final viability check before surgery ──
        if not kidney.is_viable(self.env.now):
            kidney.status = "Expired"
            kidney.disposed_reason = "Expired During Prep"
            if in_warm:
                self.stats.organs_expired.increment()
                cit = kidney.cold_ischemia_elapsed(self.env.now)
                self.stats.organ_cold_ischemia_time.record(cit)
            self._log(f"[DECIDE] Kidney #{kidney.entity_id} — EXPIRED during prep!")
            self._dispose_kidney(kidney, "Expired")
            if patient:
                patient.is_active = True
                patient.status = "Waiting"
                patient.matched_kidney = None
                self.waitlist.append(patient)
                self._update_queue_stats()
            return

        # ── PROCESS 4: Surgery (Seize OR + Surgical Team, Delay, Release) ──
        kidney.status = "In Surgery"
        self._log(f"[PROCESS] Kidney #{kidney.entity_id} → OR queue")

        with self.operating_rooms.request() as or_req, \
             self.surgical_teams.request() as team_req:
            yield or_req & team_req
            self._update_resource_stats()

            s_time = triangular(self.rng, SURGERY_TIME)
            yield self.env.timeout(s_time)

            if in_warm:
                self.stats.surgery_duration.record(s_time)

        self._update_resource_stats()

        # Record cold ischemia at transplant
        cit = kidney.cold_ischemia_elapsed(self.env.now)
        quality = kidney.current_quality(self.env.now)
        if in_warm:
            self.stats.organ_cold_ischemia_time.record(cit)
            self.stats.organ_quality_at_transplant.record(quality)

        self._log(f"[PROCESS] Kidney #{kidney.entity_id} — Surgery complete "
                  f"(CIT={cit:.1f}h, Quality={quality:.2f})")

        # ── DECIDE: Transplant outcome ──
        hla = hla_match_score(kidney, patient) if patient else 3
        success_prob = (BASE_SUCCESS_RATE
                        + HLA_BONUS_PER_MATCH * hla
                        - COLD_ISCHEMIA_PENALTY * cit)
        success_prob = max(MIN_SUCCESS_RATE, min(1.0, success_prob))

        if self.rng.random() < success_prob:
            # ── DISPOSE: Successful Transplant ──
            kidney.status = "Transplanted"
            patient.status = "Transplanted"
            kidney.time_exit_system = self.env.now
            patient.time_exit_system = self.env.now

            if in_warm:
                self.stats.successful_transplants.increment()
                wait = patient.time_matched - patient.time_on_list
                self.stats.patient_wait_time.record(wait)
                self.stats.patient_wait_time_days.record(wait / 24.0)
                self.stats.total_system_time_organ.record(self.env.now - kidney.harvest_time)
                self.stats.hla_match_scores.record(hla)
                self.stats.patient_priority_scores.record(
                    patient.priority_score(patient.time_matched))

            self._log(f"[DISPOSE] [OK] Kidney #{kidney.entity_id} -> Patient #{patient.entity_id} "
                      f"SUCCESSFUL TRANSPLANT (prob={success_prob:.2f})")
        else:
            # ── DISPOSE: Failed Transplant (Rejection) ──
            kidney.status = "Rejected"
            patient.status = "Waiting"
            kidney.disposed_reason = "Graft Rejection"
            kidney.time_exit_system = self.env.now

            if in_warm:
                self.stats.failed_transplants.increment()

            # Patient returns to waitlist
            if patient:
                patient.is_active = True
                patient.matched_kidney = None
                self.waitlist.append(patient)
                self._update_queue_stats()

            self._log(f"[DISPOSE] [FAIL] Kidney #{kidney.entity_id} -> GRAFT REJECTION "
                      f"(prob={success_prob:.2f})")

    # ===================================================================
    #  BACKGROUND PROCESSES
    # ===================================================================

    def _organ_expiry_checker(self):
        """
        Arena DECIDE Module (continuous): Remove expired organs from pool.
        Runs every hour to check organ viability.
        """
        while True:
            yield self.env.timeout(1.0)  # check every hour
            expired = [k for k in self.organ_pool if not k.is_viable(self.env.now)]
            for kidney in expired:
                self.organ_pool.remove(kidney)
                kidney.status = "Expired"
                kidney.disposed_reason = "Cold Ischemia (In Pool)"
                kidney.time_exit_system = self.env.now
                if self.env.now >= WARM_UP_PERIOD:
                    self.stats.organs_expired.increment()
                    cit = kidney.cold_ischemia_elapsed(self.env.now)
                    self.stats.organ_cold_ischemia_time.record(cit)
                self._log(f"[EXPIRE] Kidney #{kidney.entity_id} expired in pool "
                          f"(CIT={kidney.cold_ischemia_elapsed(self.env.now):.1f}h)")
            if expired:
                self._update_queue_stats()

    def _patient_attrition_process(self):
        """
        Arena DECIDE Module: Patients die or transfer while waiting.
        Runs every hour.
        """
        while True:
            yield self.env.timeout(1.0)
            removals = []
            for patient in self.waitlist:
                if not patient.is_active:
                    continue
                # Death while waiting
                if self.rng.random() < PATIENT_DEATH_RATE:
                    patient.status = "Died Waiting"
                    patient.is_active = False
                    patient.time_exit_system = self.env.now
                    removals.append(patient)
                    if self.env.now >= WARM_UP_PERIOD:
                        self.stats.patients_died_waiting.increment()
                    self._log(f"[ATTRITION] Patient #{patient.entity_id} died on waitlist")
                # Transfer out
                elif self.rng.random() < PATIENT_TRANSFER_RATE:
                    patient.status = "Transferred"
                    patient.is_active = False
                    patient.time_exit_system = self.env.now
                    removals.append(patient)
                    if self.env.now >= WARM_UP_PERIOD:
                        self.stats.patients_transferred.increment()
                    self._log(f"[ATTRITION] Patient #{patient.entity_id} transferred out")

            for p in removals:
                if p in self.waitlist:
                    self.waitlist.remove(p)
            if removals:
                self._update_queue_stats()

    def _periodic_reporter(self):
        """Snapshot statistics at regular intervals for time-series plots."""
        while True:
            yield self.env.timeout(REPORT_INTERVAL)
            if self.env.now >= WARM_UP_PERIOD:
                or_busy = self.operating_rooms.count
                or_total = self.operating_rooms.capacity
                self.stats.take_snapshot(
                    sim_time=self.env.now,
                    waitlist_len=len([p for p in self.waitlist if p.is_active]),
                    organ_pool_len=len(self.organ_pool),
                    or_busy=or_busy,
                    or_total=or_total,
                )

    # ===================================================================
    #  HELPER METHODS
    # ===================================================================

    def _assign_transport_zone(self) -> str:
        """Arena ASSIGN Module: Determine transport distance zone."""
        r = self.rng.random()
        cumulative = 0.0
        for zone, info in DISTANCE_ZONES.items():
            cumulative += info["prob"]
            if r <= cumulative:
                return zone
        return "Local"

    def _update_queue_stats(self):
        """Update time-persistent queue statistics."""
        active_waitlist = len([p for p in self.waitlist if p.is_active])
        self.stats.waitlist_length.update(self.env.now, active_waitlist)
        self.stats.organ_pool_size.update(self.env.now, len(self.organ_pool))

    def _update_resource_stats(self):
        """Update resource utilization statistics."""
        self.stats.or_utilization.update(
            self.env.now,
            self.operating_rooms.count / self.operating_rooms.capacity
        )
        self.stats.transport_utilization.update(
            self.env.now,
            self.transport_vehicles.count / self.transport_vehicles.capacity
        )
        self.stats.surgical_team_utilization.update(
            self.env.now,
            self.surgical_teams.count / self.surgical_teams.capacity
        )
        self.stats.crossmatch_lab_utilization.update(
            self.env.now,
            self.crossmatch_labs.count / self.crossmatch_labs.capacity
        )

    def _dispose_kidney(self, kidney: KidneyOrgan, reason: str):
        """Arena DISPOSE Module: Remove kidney from system."""
        kidney.time_exit_system = self.env.now
        kidney.disposed_reason = reason
        self._log(f"[DISPOSE] Kidney #{kidney.entity_id} disposed: {reason}")

    def _log(self, msg: str):
        """Print log message if verbose."""
        if self.verbose:
            day = self.env.now / 24.0
            print(f"  [Day {day:7.1f}] {msg}")
