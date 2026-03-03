"""
=============================================================================
  VISUALIZATION — Arena-Style Dashboard & Output Plots
=============================================================================
  Generates publication-quality charts mirroring Arena's output reports:
    - Entity flow diagram (Arena flowchart)
    - Queue length over time
    - Resource utilization bar charts
    - Organ cold ischemia distribution
    - Patient wait time distribution
    - Organ utilization pie chart
    - Time-series dashboard
=============================================================================
"""

import os
import matplotlib
matplotlib.use("Agg")  # non-interactive backend for file output

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import numpy as np
from statistics_collector import StatisticsCollector


# ─── Color Palette ──────────────────────────────────────────────────────
COLORS = {
    "primary":    "#2196F3",
    "success":    "#4CAF50",
    "danger":     "#F44336",
    "warning":    "#FF9800",
    "info":       "#00BCD4",
    "purple":     "#9C27B0",
    "dark":       "#37474F",
    "light_bg":   "#F5F5F5",
    "grid":       "#E0E0E0",
}


def setup_style():
    """Set up a clean, professional chart style."""
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": COLORS["light_bg"],
        "axes.grid": True,
        "grid.alpha": 0.3,
        "grid.color": COLORS["grid"],
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.labelsize": 10,
    })


def generate_all_plots(stats: StatisticsCollector, output_dir: str,
                       sim_duration: float, run_id: int = 0):
    """Generate all Arena-style output plots."""
    setup_style()
    os.makedirs(output_dir, exist_ok=True)

    _plot_dashboard(stats, output_dir, sim_duration, run_id)
    _plot_queue_timeseries(stats, output_dir, run_id)
    _plot_resource_utilization(stats, output_dir, sim_duration, run_id)
    _plot_organ_outcomes_pie(stats, output_dir, run_id)
    _plot_cold_ischemia_histogram(stats, output_dir, run_id)
    _plot_wait_time_histogram(stats, output_dir, run_id)
    _plot_quality_at_transplant(stats, output_dir, run_id)
    _plot_hla_match_distribution(stats, output_dir, run_id)
    _plot_arena_flowchart(output_dir)

    print(f"  All plots saved to: {output_dir}/")


# ─── 1. Main Dashboard ─────────────────────────────────────────────────

def _plot_dashboard(stats: StatisticsCollector, out_dir: str,
                    sim_duration: float, run_id: int):
    """Arena-style summary dashboard with 6 panels."""
    fig = plt.figure(figsize=(18, 12))
    fig.suptitle("Kidney Transplant Simulation — Arena-Style Dashboard\n"
                 f"Run #{run_id}  |  Duration: {sim_duration/24:.0f} days",
                 fontsize=14, fontweight="bold", y=0.98)
    gs = GridSpec(3, 3, figure=fig, hspace=0.35, wspace=0.3)

    snaps = stats.snapshots
    if not snaps:
        plt.savefig(os.path.join(out_dir, f"dashboard_run{run_id}.png"), dpi=150,
                    bbox_inches="tight")
        plt.close()
        return

    days = [s["time_days"] for s in snaps]

    # Panel 1: Waitlist Length
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(days, [s["waitlist_length"] for s in snaps],
             color=COLORS["primary"], linewidth=1.5)
    ax1.fill_between(days, [s["waitlist_length"] for s in snaps],
                     alpha=0.15, color=COLORS["primary"])
    ax1.set_title("Patient Waitlist Length")
    ax1.set_xlabel("Day")
    ax1.set_ylabel("Patients")

    # Panel 2: Organ Pool Size
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(days, [s["organ_pool_size"] for s in snaps],
             color=COLORS["warning"], linewidth=1.5)
    ax2.fill_between(days, [s["organ_pool_size"] for s in snaps],
                     alpha=0.15, color=COLORS["warning"])
    ax2.set_title("Available Organ Pool")
    ax2.set_xlabel("Day")
    ax2.set_ylabel("Organs")

    # Panel 3: OR Utilization
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.plot(days, [s["or_utilization_pct"] for s in snaps],
             color=COLORS["success"], linewidth=1.5)
    ax3.set_ylim(0, 105)
    ax3.axhline(y=80, color=COLORS["danger"], linestyle="--", alpha=0.5, label="80% target")
    ax3.set_title("OR Utilization (%)")
    ax3.set_xlabel("Day")
    ax3.set_ylabel("% Utilized")
    ax3.legend(fontsize=8)

    # Panel 4: Cumulative Transplants
    ax4 = fig.add_subplot(gs[1, 0])
    ax4.plot(days, [s["transplants_so_far"] for s in snaps],
             color=COLORS["success"], linewidth=2, label="Transplants")
    ax4.plot(days, [s["organs_expired_so_far"] for s in snaps],
             color=COLORS["danger"], linewidth=2, label="Expired")
    ax4.set_title("Cumulative Outcomes")
    ax4.set_xlabel("Day")
    ax4.set_ylabel("Count")
    ax4.legend(fontsize=8)

    # Panel 5: Counter Summary (bar chart)
    ax5 = fig.add_subplot(gs[1, 1:])
    labels = ["Arrived", "Transplants", "Expired", "No Match",
              "Failed", "Died Wait", "Transferred"]
    values = [
        stats.total_kidneys_arrived.value,
        stats.successful_transplants.value,
        stats.organs_expired.value,
        stats.organs_no_match.value,
        stats.failed_transplants.value,
        stats.patients_died_waiting.value,
        stats.patients_transferred.value,
    ]
    bar_colors = [COLORS["primary"], COLORS["success"], COLORS["danger"],
                  COLORS["warning"], COLORS["purple"], COLORS["dark"],
                  COLORS["info"]]
    bars = ax5.bar(labels, values, color=bar_colors, edgecolor="white")
    ax5.set_title("Event Counters")
    for bar, val in zip(bars, values):
        ax5.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 1,
                 str(val), ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax5.tick_params(axis="x", rotation=30)

    # Panel 6: Key Metrics Text Box
    ax6 = fig.add_subplot(gs[2, :])
    ax6.axis("off")

    total_k = stats.total_kidneys_arrived.value or 1
    util_rate = stats.successful_transplants.value / total_k * 100
    waste_rate = stats.organs_expired.value / total_k * 100
    avg_wait = stats.patient_wait_time_days.mean
    avg_cit = stats.organ_cold_ischemia_time.mean
    avg_quality = stats.organ_quality_at_transplant.mean

    text = (
        f"╔══════════════════════════════════════════════════════════════════╗\n"
        f"║  KEY PERFORMANCE INDICATORS                                     ║\n"
        f"╠══════════════════════════════════════════════════════════════════╣\n"
        f"║  Organ Utilization Rate:    {util_rate:6.1f}%                          ║\n"
        f"║  Organ Waste Rate:          {waste_rate:6.1f}%                          ║\n"
        f"║  Avg Patient Wait:          {avg_wait:6.1f} days                       ║\n"
        f"║  Avg Cold Ischemia Time:    {avg_cit:6.1f} hours                      ║\n"
        f"║  Avg Quality at Transplant: {avg_quality:6.3f}                          ║\n"
        f"╚══════════════════════════════════════════════════════════════════╝"
    )
    ax6.text(0.5, 0.5, text, transform=ax6.transAxes, fontsize=11,
             verticalalignment="center", horizontalalignment="center",
             fontfamily="monospace",
             bbox=dict(boxstyle="round,pad=0.5", facecolor=COLORS["light_bg"],
                       edgecolor=COLORS["dark"]))

    plt.savefig(os.path.join(out_dir, f"dashboard_run{run_id}.png"), dpi=150,
                bbox_inches="tight")
    plt.close()


# ─── 2. Queue Time-Series ──────────────────────────────────────────────

def _plot_queue_timeseries(stats: StatisticsCollector, out_dir: str, run_id: int):
    """Waitlist and organ pool over simulation time."""
    snaps = stats.snapshots
    if not snaps:
        return

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    fig.suptitle("Queue Lengths Over Time (Arena Time-Persistent)", fontweight="bold")

    days = [s["time_days"] for s in snaps]

    ax1.plot(days, [s["waitlist_length"] for s in snaps],
             color=COLORS["primary"], linewidth=1)
    ax1.fill_between(days, [s["waitlist_length"] for s in snaps],
                     alpha=0.2, color=COLORS["primary"])
    ax1.set_ylabel("Waitlist Length")
    ax1.set_title("Patient Waitlist Queue")

    ax2.plot(days, [s["organ_pool_size"] for s in snaps],
             color=COLORS["warning"], linewidth=1)
    ax2.fill_between(days, [s["organ_pool_size"] for s in snaps],
                     alpha=0.2, color=COLORS["warning"])
    ax2.set_ylabel("Organ Pool Size")
    ax2.set_xlabel("Simulation Day")
    ax2.set_title("Available Organ Pool Queue")

    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"queue_timeseries_run{run_id}.png"), dpi=150,
                bbox_inches="tight")
    plt.close()


# ─── 3. Resource Utilization ───────────────────────────────────────────

def _plot_resource_utilization(stats: StatisticsCollector, out_dir: str,
                               sim_duration: float, run_id: int):
    """Arena-style resource utilization bar chart."""
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_title("Resource Utilization (Arena Time-Weighted Average)", fontweight="bold")

    resources = {
        "Operating\nRooms": stats.or_utilization.time_weighted_average(sim_duration),
        "Surgical\nTeams": stats.surgical_team_utilization.time_weighted_average(sim_duration),
        "Transport\nVehicles": stats.transport_utilization.time_weighted_average(sim_duration),
        "Crossmatch\nLabs": stats.crossmatch_lab_utilization.time_weighted_average(sim_duration),
    }

    names = list(resources.keys())
    vals = [v * 100 for v in resources.values()]
    bar_colors = [COLORS["success"] if v < 70 else
                  COLORS["warning"] if v < 90 else
                  COLORS["danger"] for v in vals]

    bars = ax.bar(names, vals, color=bar_colors, edgecolor="white", width=0.5)
    ax.set_ylim(0, 110)
    ax.set_ylabel("Utilization (%)")
    ax.axhline(y=80, color=COLORS["danger"], linestyle="--", alpha=0.5, label="80% target")
    ax.legend()

    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 1,
                f"{val:.1f}%", ha="center", va="bottom", fontweight="bold")

    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"resource_utilization_run{run_id}.png"), dpi=150,
                bbox_inches="tight")
    plt.close()


# ─── 4. Organ Outcomes Pie Chart ───────────────────────────────────────

def _plot_organ_outcomes_pie(stats: StatisticsCollector, out_dir: str, run_id: int):
    """Pie chart showing organ disposition."""
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_title("Organ Disposition Summary", fontweight="bold", fontsize=14)

    labels = ["Transplanted", "Expired", "No Match", "Crossmatch\nFailed",
              "Graft Rejection"]
    sizes = [
        stats.successful_transplants.value,
        stats.organs_expired.value,
        stats.organs_no_match.value,
        max(0, stats.total_kidneys_arrived.value
            - stats.successful_transplants.value
            - stats.organs_expired.value
            - stats.organs_no_match.value
            - stats.failed_transplants.value),
        stats.failed_transplants.value,
    ]

    # Remove zero slices
    non_zero = [(l, s) for l, s in zip(labels, sizes) if s > 0]
    if not non_zero:
        plt.close()
        return
    labels, sizes = zip(*non_zero)

    colors = [COLORS["success"], COLORS["danger"], COLORS["warning"],
              COLORS["purple"], COLORS["dark"]][:len(labels)]

    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, autopct="%1.1f%%",
        colors=colors, startangle=90, pctdistance=0.8,
        wedgeprops=dict(edgecolor="white", linewidth=2)
    )
    for t in autotexts:
        t.set_fontweight("bold")
        t.set_fontsize(11)

    centre_circle = plt.Circle((0, 0), 0.55, fc="white")
    ax.add_artist(centre_circle)
    total = sum(sizes)
    ax.text(0, 0, f"Total\n{total}", ha="center", va="center",
            fontsize=14, fontweight="bold")

    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"organ_outcomes_run{run_id}.png"), dpi=150,
                bbox_inches="tight")
    plt.close()


# ─── 5. Cold Ischemia Time Histogram ───────────────────────────────────

def _plot_cold_ischemia_histogram(stats: StatisticsCollector, out_dir: str, run_id: int):
    """Distribution of cold ischemia times."""
    vals = stats.organ_cold_ischemia_time.values
    if not vals:
        return

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_title("Cold Ischemia Time Distribution", fontweight="bold")

    ax.hist(vals, bins=30, color=COLORS["info"], edgecolor="white", alpha=0.8)
    ax.axvline(x=24, color=COLORS["warning"], linestyle="--", linewidth=2,
               label="Ideal limit (24h)")
    ax.axvline(x=36, color=COLORS["danger"], linestyle="--", linewidth=2,
               label="Max viable (36h)")
    ax.axvline(x=np.mean(vals), color=COLORS["dark"], linestyle="-", linewidth=2,
               label=f"Mean ({np.mean(vals):.1f}h)")

    ax.set_xlabel("Cold Ischemia Time (hours)")
    ax.set_ylabel("Frequency")
    ax.legend()

    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"cold_ischemia_dist_run{run_id}.png"), dpi=150,
                bbox_inches="tight")
    plt.close()


# ─── 6. Patient Wait Time Histogram ────────────────────────────────────

def _plot_wait_time_histogram(stats: StatisticsCollector, out_dir: str, run_id: int):
    """Distribution of patient wait times."""
    vals = stats.patient_wait_time_days.values
    if not vals:
        return

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_title("Patient Wait Time Distribution", fontweight="bold")

    ax.hist(vals, bins=40, color=COLORS["primary"], edgecolor="white", alpha=0.8)
    ax.axvline(x=np.mean(vals), color=COLORS["danger"], linestyle="-", linewidth=2,
               label=f"Mean ({np.mean(vals):.1f} days)")
    ax.axvline(x=np.median(vals), color=COLORS["warning"], linestyle="--", linewidth=2,
               label=f"Median ({np.median(vals):.1f} days)")

    ax.set_xlabel("Wait Time (days)")
    ax.set_ylabel("Frequency")
    ax.legend()

    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"wait_time_dist_run{run_id}.png"), dpi=150,
                bbox_inches="tight")
    plt.close()


# ─── 7. Organ Quality at Transplant ────────────────────────────────────

def _plot_quality_at_transplant(stats: StatisticsCollector, out_dir: str, run_id: int):
    """Distribution of organ quality scores at time of transplant."""
    vals = stats.organ_quality_at_transplant.values
    if not vals:
        return

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_title("Organ Quality at Transplant (Decay Model)", fontweight="bold")

    ax.hist(vals, bins=30, color=COLORS["success"], edgecolor="white", alpha=0.8)
    ax.axvline(x=np.mean(vals), color=COLORS["dark"], linestyle="-", linewidth=2,
               label=f"Mean ({np.mean(vals):.3f})")
    ax.set_xlabel("Quality Score (0 = degraded, 1 = perfect)")
    ax.set_ylabel("Frequency")
    ax.set_xlim(0, 1.05)
    ax.legend()

    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"quality_dist_run{run_id}.png"), dpi=150,
                bbox_inches="tight")
    plt.close()


# ─── 8. HLA Match Distribution ─────────────────────────────────────────

def _plot_hla_match_distribution(stats: StatisticsCollector, out_dir: str, run_id: int):
    """Bar chart of HLA match scores in successful transplants."""
    vals = stats.hla_match_scores.values
    if not vals:
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.set_title("HLA Antigen Match Scores (Successful Transplants)", fontweight="bold")

    int_vals = [int(v) for v in vals]
    bins = range(0, 8)
    counts = [int_vals.count(i) for i in range(7)]
    bar_colors = [COLORS["danger"] if i < 3 else
                  COLORS["warning"] if i < 5 else
                  COLORS["success"] for i in range(7)]
    ax.bar(range(7), counts, color=bar_colors, edgecolor="white")
    ax.set_xticks(range(7))
    ax.set_xlabel("HLA Antigens Matched (out of 6)")
    ax.set_ylabel("Count")

    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"hla_match_dist_run{run_id}.png"), dpi=150,
                bbox_inches="tight")
    plt.close()


# ─── 9. Arena-Style Flowchart ──────────────────────────────────────────

def _plot_arena_flowchart(out_dir: str):
    """Draw the Arena-style simulation flowchart."""
    fig, ax = plt.subplots(figsize=(16, 10))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("Arena-Style Simulation Flowchart\n"
                 "Kidney Transplant Logistics & Perishable Queueing Model",
                 fontsize=14, fontweight="bold", pad=20)

    def draw_box(x, y, w, h, text, color, style="round,pad=0.3"):
        box = mpatches.FancyBboxPatch((x, y), w, h, boxstyle=style,
                                       facecolor=color, edgecolor="black",
                                       linewidth=1.5)
        ax.add_patch(box)
        ax.text(x + w/2, y + h/2, text, ha="center", va="center",
                fontsize=8, fontweight="bold", wrap=True)

    def draw_diamond(x, y, size, text):
        diamond = plt.Polygon(
            [(x, y + size/2), (x + size/2, y + size),
             (x + size, y + size/2), (x + size/2, y)],
            facecolor="#FFEB3B", edgecolor="black", linewidth=1.5
        )
        ax.add_patch(diamond)
        ax.text(x + size/2, y + size/2, text, ha="center", va="center",
                fontsize=7, fontweight="bold")

    def arrow(x1, y1, x2, y2, text=""):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", lw=1.5, color="black"))
        if text:
            mx, my = (x1+x2)/2, (y1+y2)/2
            ax.text(mx, my + 0.15, text, fontsize=7, ha="center",
                    color=COLORS["danger"], fontweight="bold")

    # ── Top Row: Kidney Path ──
    draw_box(0.3, 8.0, 1.8, 0.8, "CREATE\nKidney\nArrivals", "#C8E6C9")
    draw_box(2.8, 8.0, 1.8, 0.8, "ASSIGN\nBlood/HLA\nZone", "#B3E5FC")
    draw_diamond(5.3, 7.8, 1.2, "MATCH\nFound?")
    draw_box(7.2, 8.0, 1.8, 0.8, "PROCESS\nCrossmatch\nLab", "#FFE0B2")
    draw_diamond(9.7, 7.8, 1.2, "XMatch\nPass?")
    draw_box(11.6, 8.0, 1.8, 0.8, "PROCESS\nTransport", "#FFE0B2")
    draw_diamond(14.0, 7.8, 1.2, "Still\nViable?")

    arrow(2.1, 8.4, 2.8, 8.4)
    arrow(4.6, 8.4, 5.3, 8.4)
    arrow(6.5, 8.4, 7.2, 8.4, "Yes")
    arrow(9.0, 8.4, 9.7, 8.4)
    arrow(10.9, 8.4, 11.6, 8.4, "Yes")
    arrow(13.4, 8.4, 14.0, 8.4)

    # ── Middle Row: Surgery ──
    draw_box(11.6, 5.8, 1.8, 0.8, "PROCESS\nSurgery\n(OR+Team)", "#FFE0B2")
    draw_diamond(14.0, 5.6, 1.2, "Graft\nSuccess?")

    arrow(15.2, 8.4, 15.5, 8.4)  # viable yes continues
    # Down from viable check to surgery
    ax.annotate("", xy=(12.5, 6.6), xytext=(14.6, 7.8),
                arrowprops=dict(arrowstyle="->", lw=1.5, color="black"))
    ax.text(13.8, 7.2, "Yes", fontsize=7, color=COLORS["success"], fontweight="bold")

    arrow(13.4, 6.2, 14.0, 6.2)

    # ── Dispose boxes ──
    draw_box(5.5, 6.0, 1.5, 0.7, "HOLD\nOrgan Pool\n(Wait)", "#E1BEE7")
    draw_box(9.8, 6.0, 1.5, 0.7, "DISPOSE\nXMatch\nFailed", "#FFCDD2")
    draw_box(14.2, 4.0, 1.5, 0.7, "DISPOSE\nRejection", "#FFCDD2")
    draw_box(11.6, 4.0, 1.5, 0.7, "DISPOSE\nSuccess!", "#C8E6C9")
    draw_box(14.2, 8.8, 1.5, 0.7, "DISPOSE\nExpired", "#FFCDD2")

    # No match → pool
    ax.annotate("", xy=(6.25, 6.7), xytext=(5.9, 7.8),
                arrowprops=dict(arrowstyle="->", lw=1.5, color="black"))
    ax.text(5.5, 7.3, "No", fontsize=7, color=COLORS["danger"], fontweight="bold")

    # XMatch fail
    ax.annotate("", xy=(10.5, 6.7), xytext=(10.3, 7.8),
                arrowprops=dict(arrowstyle="->", lw=1.5, color="black"))
    ax.text(10.0, 7.3, "No", fontsize=7, color=COLORS["danger"], fontweight="bold")

    # Not viable → expired
    ax.annotate("", xy=(14.9, 8.8), xytext=(14.9, 8.2),  # directly up
                arrowprops=dict(arrowstyle="->", lw=1.5, color="black"))
    ax.text(15.2, 8.5, "No", fontsize=7, color=COLORS["danger"], fontweight="bold")

    # Graft success
    ax.annotate("", xy=(12.35, 4.7), xytext=(14.3, 5.6),
                arrowprops=dict(arrowstyle="->", lw=1.5, color="black"))
    ax.text(13.0, 5.0, "Yes", fontsize=7, color=COLORS["success"], fontweight="bold")

    # Graft rejection
    ax.annotate("", xy=(14.9, 4.7), xytext=(14.9, 5.6),
                arrowprops=dict(arrowstyle="->", lw=1.5, color="black"))
    ax.text(15.2, 5.1, "No", fontsize=7, color=COLORS["danger"], fontweight="bold")

    # ── Bottom Row: Patient Path ──
    draw_box(0.3, 2.5, 1.8, 0.8, "CREATE\nPatient\nArrivals", "#C8E6C9")
    draw_box(2.8, 2.5, 1.8, 0.8, "ASSIGN\nBlood/HLA\nUrgency", "#B3E5FC")
    draw_box(5.3, 2.5, 1.8, 0.8, "QUEUE\nWaitlist\n(Priority)", "#E1BEE7")
    draw_diamond(7.8, 2.3, 1.2, "Attrition\n?")
    draw_box(9.7, 2.5, 1.5, 0.7, "DISPOSE\nDied/\nTransfer", "#FFCDD2")

    arrow(2.1, 2.9, 2.8, 2.9)
    arrow(4.6, 2.9, 5.3, 2.9)
    arrow(7.1, 2.9, 7.8, 2.9)
    arrow(9.0, 2.9, 9.7, 2.9, "Yes")

    # Connect waitlist to organ path (dotted line to match)
    ax.annotate("", xy=(5.9, 7.8), xytext=(6.2, 3.3),
                arrowprops=dict(arrowstyle="->", lw=1.5, color=COLORS["primary"],
                               linestyle="dashed"))
    ax.text(5.2, 5.3, "Match\nAttempt", fontsize=7, color=COLORS["primary"],
            fontweight="bold", ha="center")

    # Legend
    legend_items = [
        mpatches.Patch(color="#C8E6C9", label="Create Module"),
        mpatches.Patch(color="#B3E5FC", label="Assign Module"),
        mpatches.Patch(color="#FFE0B2", label="Process Module"),
        mpatches.Patch(color="#E1BEE7", label="Queue/Hold Module"),
        mpatches.Patch(color="#FFEB3B", label="Decide Module"),
        mpatches.Patch(color="#FFCDD2", label="Dispose Module"),
    ]
    ax.legend(handles=legend_items, loc="lower left", fontsize=8,
              ncol=3, framealpha=0.9)

    plt.savefig(os.path.join(out_dir, "arena_flowchart.png"), dpi=150,
                bbox_inches="tight")
    plt.close()


# ─── Cross-Replication Comparison Plot ──────────────────────────────────

def plot_replication_comparison(rep_results: list[dict], out_dir: str):
    """Box plots comparing metrics across replications."""
    if not rep_results:
        return

    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    fig.suptitle("Across-Replication Comparison (Arena Replication Analysis)",
                 fontweight="bold", fontsize=14)

    metrics = [
        ("organ_utilization_rate", "Organ Utilization Rate (%)", COLORS["success"]),
        ("organ_waste_rate", "Organ Waste Rate (%)", COLORS["danger"]),
        ("avg_wait_time_days", "Avg Wait Time (days)", COLORS["primary"]),
        ("avg_cold_ischemia", "Avg Cold Ischemia (hrs)", COLORS["info"]),
        ("avg_quality_at_transplant", "Avg Quality at Transplant", COLORS["warning"]),
        ("avg_or_utilization", "Avg OR Utilization", COLORS["purple"]),
    ]

    for ax, (key, title, color) in zip(axes.flat, metrics):
        vals = [r[key] for r in rep_results]
        ax.boxplot(vals, patch_artist=True,
                   boxprops=dict(facecolor=color, alpha=0.5),
                   medianprops=dict(color="black", linewidth=2))
        ax.scatter([1]*len(vals), vals, color=color, alpha=0.6, s=40, zorder=3)
        ax.set_title(title, fontsize=10)
        ax.set_xticklabels([""])

    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "replication_comparison.png"), dpi=150,
                bbox_inches="tight")
    plt.close()
