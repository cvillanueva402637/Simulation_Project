# Kidney Transplant Logistics & Perishable Queueing Simulation

> **Arena-style discrete-event simulation built in Python using SimPy**

## Project Overview

This simulation models the **kidney transplant supply chain** — from deceased/living donor organ procurement through matching, transportation, crossmatch testing, and surgical transplantation. It explicitly models **organ perishability** (cold ischemia time) and uses a **UNOS-style priority allocation** system.

The project is designed to mirror **Arena Simulation Software** concepts:

| Arena Concept | Python Equivalent |
|---|---|
| Create Module | `_create_kidney_arrivals()`, `_create_patient_arrivals()` |
| Assign Module | Entity attribute assignment in `KidneyOrgan.generate()` |
| Process Module (Seize-Delay-Release) | SimPy `resource.request()` + `env.timeout()` |
| Decide Module | `_find_best_match()`, viability checks |
| Queue / Hold | `self.waitlist`, `self.organ_pool` |
| Dispose Module | `_dispose_kidney()`, transplant completion |
| Resources | `simpy.Resource` (OR, Teams, Transport, Labs) |
| Tally Statistics | `TallyStat` (observation-based) |
| Time-Persistent Statistics | `TimePersistentStat` (time-weighted) |
| Counter Statistics | `CounterStat` |
| Replications | Multiple independent runs with different seeds |
| Warm-Up Period | Statistics discarded during first 30 days |
| Output Reports | Arena-style tabular reports + confidence intervals |

## System Flow (Arena Flowchart)

```
   KIDNEY PATH:
   ┌────────┐   ┌────────┐   ┌───────┐   ┌───────────┐   ┌──────────┐   ┌──────────┐   ┌─────────┐
   │ CREATE │──▶│ ASSIGN │──▶│ MATCH │──▶│CROSSMATCH │──▶│TRANSPORT │──▶│ SURGERY  │──▶│ DISPOSE │
   │ Kidney │   │BT/HLA  │   │Decide │   │  Process   │   │ Process  │   │ Process  │   │Success/ │
   │Arrivals│   │Zone    │   │       │   │  (Lab)     │   │(Vehicle) │   │(OR+Team) │   │Failure  │
   └────────┘   └────────┘   └───┬───┘   └──────┬────┘   └────┬─────┘   └──────────┘   └─────────┘
                                  │ No           │ Fail        │ Expired
                                  ▼              ▼             ▼
                             ┌─────────┐   ┌─────────┐   ┌─────────┐
                             │  HOLD   │   │ DISPOSE │   │ DISPOSE │
                             │Organ Pool│  │XM Fail  │   │ Expired │
                             └─────────┘   └─────────┘   └─────────┘

   PATIENT PATH:
   ┌────────┐   ┌────────┐   ┌──────────┐   ┌────────┐
   │ CREATE │──▶│ ASSIGN │──▶│  QUEUE   │──▶│ATTRITION│──▶ Death/Transfer
   │Patient │   │BT/HLA  │   │ Waitlist │   │ Decide  │
   │Arrivals│   │Urgency │   │(Priority)│   │         │
   └────────┘   └────────┘   └──────────┘   └────────┘
```

## Key Model Features

### Perishable Queueing
- **Cold ischemia clock** starts at organ harvest (max 36 hours)
- **Exponential quality decay**: Q(t) = e^(-0.05·t)
- Organs that exceed cold ischemia time are **disposed as expired**
- Quality at transplant affects **graft success probability**

### UNOS-Style Allocation
- **ABO blood-type compatibility** matrix
- **6-antigen HLA matching** with minimum threshold
- **Panel Reactive Antibody (PRA)** affects crossmatch probability
- **Priority score** = urgency weight × 10 + wait days × 0.5 + PRA bonus

### Resources (Arena Seize-Delay-Release)
- **Operating Rooms** (4) — shared between surgeries
- **Surgical Teams** (5) — required simultaneously with OR
- **Transport Vehicles** (3) — helicopters/vans for organ transport
- **Crossmatch Labs** (2) — HLA crossmatch testing

### Process Times (Triangular Distributions)
| Process | Min | Mode | Max |
|---|---|---|---|
| Crossmatch Testing | 1.0h | 2.0h | 4.0h |
| Transport (Local) | 0.5h | 1.0h | 2.0h |
| Transport (Regional) | 1.5h | 3.0h | 5.0h |
| Transport (National) | 3.0h | 5.0h | 8.0h |
| Surgery | 2.0h | 3.5h | 6.0h |

## File Structure

```
Simulation_Final/
├── main.py                  # Entry point — run simulation
├── config.py                # All parameters (Arena "Run Setup")
├── entities.py              # Entity definitions (Kidney, Patient)
├── simulation.py            # Core engine (Arena flowchart modules)
├── statistics_collector.py  # Statistics (Tally, Time-Persistent, Counter)
├── visualization.py         # Arena-style dashboards and plots
├── requirements.txt         # Python dependencies
├── README.md                # This file
└── output/                  # Generated reports and plots
    ├── report_run1.txt
    ├── dashboard_run1.png
    ├── arena_flowchart.png
    ├── queue_timeseries_run1.png
    ├── resource_utilization_run1.png
    ├── organ_outcomes_run1.png
    ├── cold_ischemia_dist_run1.png
    ├── wait_time_dist_run1.png
    ├── quality_dist_run1.png
    ├── hla_match_dist_run1.png
    ├── across_replications_report.txt
    └── replication_comparison.png
```

## Installation & Running

```bash
# Install dependencies
pip install -r requirements.txt

# Run with defaults (10 replications)
python main.py

# Run 5 replications with verbose event logging
python main.py --reps 5 --verbose

# Single replication, verbose, custom duration (180 days)
python main.py --reps 1 --verbose --duration 4320

# Run without generating plots (faster)
python main.py --no-plots
```

## Output

### Text Reports (Arena-Style)
Each replication generates a tabular report with:
- **Counter statistics** — totals for each event type
- **Tally statistics** — mean, std dev, min, max, 95% CI
- **Time-persistent statistics** — time-weighted averages
- **Across-replication summary** — confidence intervals for key metrics

### Visualizations
- **Dashboard** — 6-panel overview of all key metrics
- **Arena Flowchart** — visual model logic diagram
- **Queue time-series** — waitlist and organ pool over time
- **Resource utilization** — bar chart with 80% target line
- **Organ outcomes** — donut chart (transplanted / expired / etc.)
- **Histograms** — cold ischemia, wait times, quality, HLA scores
- **Replication comparison** — box plots across runs

## Configuration

All parameters are in `config.py`. Key settings:

| Parameter | Default | Description |
|---|---|---|
| `SIM_DURATION` | 8,760 hrs (1 year) | Total simulation time |
| `NUM_REPLICATIONS` | 10 | Independent runs |
| `WARM_UP_PERIOD` | 720 hrs (30 days) | Statistics collection starts after |
| `KIDNEY_ARRIVAL_RATE` | 1/8 per hr (~3/day) | Deceased donor arrival rate |
| `PATIENT_ARRIVAL_RATE` | 1/4 per hr (~6/day) | Patient arrival rate |
| `MAX_COLD_ISCHEMIA_TIME` | 36 hrs | Organ viability window |
| `NUM_OPERATING_ROOMS` | 4 | OR capacity |

## Arena Equivalence Notes

This simulation faithfully replicates Arena's modeling paradigm:

1. **Entities** flow through a **flowchart** of modules
2. **Resources** are seized, used (delayed), and released
3. **Queues** form when resources are busy
4. **Decide modules** route entities based on conditions
5. **Statistics** are collected automatically (tally, time-persistent, counter)
6. **Warm-up period** ensures steady-state analysis
7. **Multiple replications** with different random seeds provide confidence intervals
8. **Triangular distributions** are used for process times (Arena default)
9. **Exponential inter-arrival times** model Poisson arrivals
