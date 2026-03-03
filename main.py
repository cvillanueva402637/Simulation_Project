"""
=============================================================================
  MAIN RUNNER — Kidney Transplant Simulation
=============================================================================
  Entry point for the simulation. Mirrors Arena's "Run > Setup" dialog:
    - Configure replications
    - Set simulation duration
    - Run warm-up + data collection
    - Generate reports and plots
=============================================================================

  Usage:
    python main.py                     # Default: 10 replications, quiet
    python main.py --reps 5            # 5 replications
    python main.py --verbose           # Print event log
    python main.py --reps 1 --verbose  # Single run with full log

=============================================================================
"""

import argparse
import os
import sys
import time
import random
import simpy

from config import SIM_DURATION, NUM_REPLICATIONS, RANDOM_SEED_BASE, WARM_UP_PERIOD
from simulation import KidneyTransplantSimulation
from statistics_collector import StatisticsCollector, ReplicationCollector
from visualization import generate_all_plots, plot_replication_comparison


def run_single_replication(run_id: int, seed: int,
                            verbose: bool = False) -> StatisticsCollector:
    """
    Execute one replication of the simulation.
    Equivalent to one "Run" in Arena.
    """
    print(f"\n{'─'*60}")
    print(f"  REPLICATION {run_id}  |  Seed: {seed}")
    print(f"  Duration: {SIM_DURATION:.0f} hrs ({SIM_DURATION/24:.0f} days)  "
          f"|  Warm-up: {WARM_UP_PERIOD:.0f} hrs ({WARM_UP_PERIOD/24:.0f} days)")
    print(f"{'─'*60}")

    # Create SimPy environment (Arena's simulation clock)
    env = simpy.Environment()
    rng = random.Random(seed)
    stats = StatisticsCollector()

    # Build and run the model
    model = KidneyTransplantSimulation(
        env=env, rng=rng, stats=stats, run_id=run_id, verbose=verbose
    )

    start_wall = time.time()
    env.run(until=SIM_DURATION)
    elapsed = time.time() - start_wall

    print(f"  Completed in {elapsed:.1f}s wall-clock time")
    print(f"  Events simulated: {SIM_DURATION/24:.0f} days of hospital operations")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Kidney Transplant Logistics & Perishable Queueing Simulation"
    )
    parser.add_argument("--reps", type=int, default=NUM_REPLICATIONS,
                        help=f"Number of replications (default: {NUM_REPLICATIONS})")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print detailed event log")
    parser.add_argument("--duration", type=float, default=None,
                        help="Override simulation duration in hours")
    parser.add_argument("--output", type=str, default="output",
                        help="Output directory for reports and plots")
    parser.add_argument("--no-plots", action="store_true",
                        help="Skip generating plots")
    args = parser.parse_args()

    # ── Override duration if specified ──
    if args.duration:
        import config
        config.SIM_DURATION = args.duration

    output_dir = os.path.join(os.path.dirname(__file__), args.output)
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("  KIDNEY TRANSPLANT LOGISTICS &")
    print("  PERISHABLE QUEUEING SIMULATION")
    print("  Arena-Style Discrete-Event Simulation (Python/SimPy)")
    print("=" * 60)
    print(f"  Replications:   {args.reps}")
    print(f"  Duration:       {SIM_DURATION:.0f} hours ({SIM_DURATION/24:.0f} days)")
    print(f"  Warm-up:        {WARM_UP_PERIOD:.0f} hours ({WARM_UP_PERIOD/24:.0f} days)")
    print(f"  Output:         {output_dir}")
    print("=" * 60)

    # ── Run all replications ──
    rep_collector = ReplicationCollector()
    all_stats = []

    for rep in range(1, args.reps + 1):
        seed = RANDOM_SEED_BASE + rep * 1000
        stats = run_single_replication(run_id=rep, seed=seed, verbose=args.verbose)
        all_stats.append(stats)
        rep_collector.add_replication(stats, SIM_DURATION)

        # Print single-run report
        report = stats.generate_report(SIM_DURATION)
        print(report)

        # Save report to file
        report_path = os.path.join(output_dir, f"report_run{rep}.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        # Generate plots for each replication
        if not args.no_plots:
            generate_all_plots(stats, output_dir, SIM_DURATION, run_id=rep)

    # ── Cross-Replication Summary ──
    print("\n")
    cross_report = rep_collector.across_replications_report()
    print(cross_report)

    cross_path = os.path.join(output_dir, "across_replications_report.txt")
    with open(cross_path, "w", encoding="utf-8") as f:
        f.write(cross_report)

    # ── Cross-replication comparison plot ──
    if not args.no_plots and len(rep_collector.rep_results) > 1:
        plot_replication_comparison(rep_collector.rep_results, output_dir)

    print(f"\n  All outputs saved to: {output_dir}/")
    print("  Simulation complete.\n")


if __name__ == "__main__":
    main()
