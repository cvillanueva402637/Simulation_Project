"""
=============================================================================
  STATISTICS COLLECTOR — Arena-Style Output Statistics
=============================================================================
  Mirrors Arena's built-in statistic collection:
    - Tally (observation) statistics
    - Time-persistent (time-weighted) statistics
    - Counter statistics
    - Output reports
=============================================================================
"""

import math
import statistics as pystats
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TallyStat:
    """Arena Tally Statistic — observation-based (e.g., wait times)."""
    name: str
    values: list[float] = field(default_factory=list)

    def record(self, value: float):
        self.values.append(value)

    @property
    def count(self) -> int:
        return len(self.values)

    @property
    def mean(self) -> float:
        return pystats.mean(self.values) if self.values else 0.0

    @property
    def std_dev(self) -> float:
        return pystats.stdev(self.values) if len(self.values) > 1 else 0.0

    @property
    def minimum(self) -> float:
        return min(self.values) if self.values else 0.0

    @property
    def maximum(self) -> float:
        return max(self.values) if self.values else 0.0

    @property
    def median(self) -> float:
        return pystats.median(self.values) if self.values else 0.0

    def confidence_interval(self, confidence: float = 0.95) -> tuple[float, float]:
        """Compute CI using t-distribution approximation."""
        if len(self.values) < 2:
            return (self.mean, self.mean)
        n = len(self.values)
        se = self.std_dev / math.sqrt(n)
        # z-approx for large n
        z = 1.96 if confidence == 0.95 else 2.576
        return (self.mean - z * se, self.mean + z * se)

    def summary(self) -> dict:
        lo, hi = self.confidence_interval()
        return {
            "Statistic": self.name,
            "Count": self.count,
            "Mean": round(self.mean, 3),
            "StdDev": round(self.std_dev, 3),
            "Min": round(self.minimum, 3),
            "Median": round(self.median, 3),
            "Max": round(self.maximum, 3),
            "95% CI Low": round(lo, 3),
            "95% CI High": round(hi, 3),
        }


@dataclass
class TimePersistentStat:
    """Arena Time-Persistent Statistic — time-weighted (e.g., queue length)."""
    name: str
    _history: list[tuple[float, float]] = field(default_factory=list)  # (time, value)
    _current_value: float = 0.0

    def update(self, time: float, value: float):
        self._history.append((time, value))
        self._current_value = value

    @property
    def current(self) -> float:
        return self._current_value

    def time_weighted_average(self, end_time: Optional[float] = None) -> float:
        """Compute the time-weighted average."""
        if len(self._history) < 2:
            return self._current_value
        total_time = 0.0
        weighted_sum = 0.0
        for i in range(len(self._history) - 1):
            t1, v1 = self._history[i]
            t2, _ = self._history[i + 1]
            dt = t2 - t1
            weighted_sum += v1 * dt
            total_time += dt
        # Last interval to end_time
        if end_time and self._history:
            t_last, v_last = self._history[-1]
            dt = end_time - t_last
            if dt > 0:
                weighted_sum += v_last * dt
                total_time += dt
        return weighted_sum / total_time if total_time > 0 else 0.0

    @property
    def maximum(self) -> float:
        return max(v for _, v in self._history) if self._history else 0.0

    def history_points(self) -> list[tuple[float, float]]:
        return list(self._history)

    def summary(self, end_time: float = 0) -> dict:
        return {
            "Statistic": self.name,
            "Time-Avg": round(self.time_weighted_average(end_time), 3),
            "Current": round(self._current_value, 3),
            "Maximum": round(self.maximum, 3),
            "Observations": len(self._history),
        }


@dataclass
class CounterStat:
    """Arena Counter Statistic — simple event counter."""
    name: str
    value: int = 0

    def increment(self, amount: int = 1):
        self.value += amount

    def summary(self) -> dict:
        return {"Statistic": self.name, "Count": self.value}


# ─── Main Statistics Collector ──────────────────────────────────────────

class StatisticsCollector:
    """
    Central statistics hub — mirrors Arena's Statistics module.
    Collects all simulation metrics for reporting.
    """

    def __init__(self):
        # ── Tally Statistics (observation-based) ──
        self.organ_cold_ischemia_time  = TallyStat("Organ Cold Ischemia Time (hrs)")
        self.organ_quality_at_transplant = TallyStat("Organ Quality at Transplant")
        self.patient_wait_time         = TallyStat("Patient Wait Time (hrs)")
        self.patient_wait_time_days    = TallyStat("Patient Wait Time (days)")
        self.surgery_duration          = TallyStat("Surgery Duration (hrs)")
        self.transport_time            = TallyStat("Transport Time (hrs)")
        self.crossmatch_time           = TallyStat("Crossmatch Test Time (hrs)")
        self.total_system_time_organ   = TallyStat("Organ Total Time in System (hrs)")
        self.hla_match_scores          = TallyStat("HLA Match Score (0-6)")
        self.patient_priority_scores   = TallyStat("Patient Priority Score at Match")

        # ── Time-Persistent Statistics (time-weighted) ──
        self.waitlist_length           = TimePersistentStat("Waitlist Length")
        self.organ_pool_size           = TimePersistentStat("Available Organ Pool Size")
        self.or_utilization            = TimePersistentStat("OR Utilization")
        self.transport_utilization     = TimePersistentStat("Transport Utilization")
        self.surgical_team_utilization = TimePersistentStat("Surgical Team Utilization")
        self.crossmatch_lab_utilization = TimePersistentStat("Crossmatch Lab Utilization")

        # ── Counter Statistics ──
        self.total_kidneys_arrived     = CounterStat("Total Kidneys Arrived")
        self.total_patients_arrived    = CounterStat("Total Patients Arrived")
        self.successful_transplants    = CounterStat("Successful Transplants")
        self.failed_transplants        = CounterStat("Failed Transplants (Rejection)")
        self.organs_expired            = CounterStat("Organs Expired (Ischemia)")
        self.organs_no_match           = CounterStat("Organs — No Compatible Match")
        self.patients_died_waiting     = CounterStat("Patients Died on Waitlist")
        self.patients_transferred      = CounterStat("Patients Transferred Out")
        self.living_donor_transplants  = CounterStat("Living Donor Transplants")

        # ── Snapshot history for time-series plots ──
        self.snapshots: list[dict] = []

    def take_snapshot(self, sim_time: float, waitlist_len: int,
                      organ_pool_len: int, or_busy: int, or_total: int):
        """Periodic snapshot for dashboard plotting."""
        self.snapshots.append({
            "time": sim_time,
            "time_days": sim_time / 24.0,
            "waitlist_length": waitlist_len,
            "organ_pool_size": organ_pool_len,
            "or_utilization_pct": (or_busy / or_total * 100) if or_total > 0 else 0,
            "transplants_so_far": self.successful_transplants.value,
            "organs_expired_so_far": self.organs_expired.value,
        })

    def generate_report(self, sim_duration: float) -> str:
        """Generate Arena-style summary report."""
        lines = []
        lines.append("=" * 78)
        lines.append("  ARENA-STYLE SIMULATION OUTPUT REPORT")
        lines.append("  Kidney Transplant Logistics & Perishable Queueing Simulation")
        lines.append("=" * 78)
        lines.append(f"  Simulation Duration: {sim_duration:.1f} hours "
                      f"({sim_duration/24:.1f} days)")
        lines.append("")

        # ── COUNTERS ──
        lines.append("─" * 78)
        lines.append("  COUNTER STATISTICS")
        lines.append("─" * 78)
        counters = [
            self.total_kidneys_arrived, self.total_patients_arrived,
            self.successful_transplants, self.failed_transplants,
            self.organs_expired, self.organs_no_match,
            self.patients_died_waiting, self.patients_transferred,
            self.living_donor_transplants,
        ]
        for c in counters:
            lines.append(f"  {c.name:<45s} {c.value:>8d}")

        # Derived rates
        total_k = self.total_kidneys_arrived.value
        if total_k > 0:
            util_rate = self.successful_transplants.value / total_k * 100
            waste_rate = self.organs_expired.value / total_k * 100
            nomatch_rate = self.organs_no_match.value / total_k * 100
            lines.append("")
            lines.append(f"  {'Organ Utilization Rate (%)':<45s} {util_rate:>8.1f}%")
            lines.append(f"  {'Organ Waste Rate (%)':<45s} {waste_rate:>8.1f}%")
            lines.append(f"  {'No-Match Rate (%)':<45s} {nomatch_rate:>8.1f}%")

        # ── TALLY STATS ──
        lines.append("")
        lines.append("─" * 78)
        lines.append("  TALLY (OBSERVATION) STATISTICS")
        lines.append("─" * 78)
        header = (f"  {'Statistic':<35s} {'Count':>6s} {'Mean':>8s} "
                  f"{'StdDev':>8s} {'Min':>8s} {'Max':>8s} {'95%CI':>18s}")
        lines.append(header)
        lines.append("  " + "-" * 95)

        tallies = [
            self.organ_cold_ischemia_time, self.organ_quality_at_transplant,
            self.patient_wait_time, self.patient_wait_time_days,
            self.surgery_duration, self.transport_time,
            self.crossmatch_time, self.total_system_time_organ,
            self.hla_match_scores, self.patient_priority_scores,
        ]
        for t in tallies:
            s = t.summary()
            ci = f"[{s['95% CI Low']:.2f}, {s['95% CI High']:.2f}]"
            lines.append(
                f"  {s['Statistic']:<35s} {s['Count']:>6d} {s['Mean']:>8.2f} "
                f"{s['StdDev']:>8.2f} {s['Min']:>8.2f} {s['Max']:>8.2f} {ci:>18s}"
            )

        # ── TIME-PERSISTENT STATS ──
        lines.append("")
        lines.append("─" * 78)
        lines.append("  TIME-PERSISTENT (TIME-WEIGHTED) STATISTICS")
        lines.append("─" * 78)
        header2 = (f"  {'Statistic':<35s} {'Time-Avg':>10s} "
                   f"{'Current':>10s} {'Maximum':>10s}")
        lines.append(header2)
        lines.append("  " + "-" * 67)

        tp_stats = [
            self.waitlist_length, self.organ_pool_size,
            self.or_utilization, self.transport_utilization,
            self.surgical_team_utilization, self.crossmatch_lab_utilization,
        ]
        for tp in tp_stats:
            s = tp.summary(sim_duration)
            lines.append(
                f"  {s['Statistic']:<35s} {s['Time-Avg']:>10.2f} "
                f"{s['Current']:>10.2f} {s['Maximum']:>10.2f}"
            )

        lines.append("")
        lines.append("=" * 78)
        lines.append("  END OF REPORT")
        lines.append("=" * 78)
        return "\n".join(lines)


class ReplicationCollector:
    """Collects summary statistics across multiple replications for CI analysis."""

    def __init__(self):
        self.rep_results: list[dict] = []

    def add_replication(self, stats: StatisticsCollector, sim_duration: float):
        total_k = stats.total_kidneys_arrived.value
        self.rep_results.append({
            "organ_utilization_rate": (stats.successful_transplants.value / total_k * 100) if total_k > 0 else 0,
            "organ_waste_rate": (stats.organs_expired.value / total_k * 100) if total_k > 0 else 0,
            "avg_wait_time_days": stats.patient_wait_time_days.mean,
            "avg_cold_ischemia": stats.organ_cold_ischemia_time.mean,
            "avg_quality_at_transplant": stats.organ_quality_at_transplant.mean,
            "total_transplants": stats.successful_transplants.value,
            "total_expired": stats.organs_expired.value,
            "avg_waitlist_length": stats.waitlist_length.time_weighted_average(sim_duration),
            "avg_or_utilization": stats.or_utilization.time_weighted_average(sim_duration),
        })

    def across_replications_report(self) -> str:
        """Generate cross-replication summary with confidence intervals."""
        if not self.rep_results:
            return "No replications collected."

        lines = []
        lines.append("=" * 78)
        lines.append("  ACROSS-REPLICATION SUMMARY (Arena Half-Width Report)")
        lines.append(f"  Number of Replications: {len(self.rep_results)}")
        lines.append("=" * 78)

        metrics = list(self.rep_results[0].keys())
        header = f"  {'Metric':<35s} {'Mean':>10s} {'StdDev':>10s} {'95% CI':>22s}"
        lines.append(header)
        lines.append("  " + "-" * 79)

        for metric in metrics:
            vals = [r[metric] for r in self.rep_results]
            avg = pystats.mean(vals)
            sd = pystats.stdev(vals) if len(vals) > 1 else 0
            n = len(vals)
            se = sd / math.sqrt(n) if n > 0 else 0
            hw = 1.96 * se
            ci_str = f"[{avg - hw:.2f}, {avg + hw:.2f}]"
            label = metric.replace("_", " ").title()
            lines.append(f"  {label:<35s} {avg:>10.2f} {sd:>10.2f} {ci_str:>22s}")

        lines.append("=" * 78)
        return "\n".join(lines)
