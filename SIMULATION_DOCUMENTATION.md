# Kidney Transplant Logistics & Perishable Queueing Simulation
## Full Project Documentation
### Arena-Style Discrete-Event Simulation | Python + SimPy
---

&nbsp;

## 1. Introduction

Modeling and Simulation (M&S) is a disciplined technique used to represent, analyze, and
understand the behavior of complex real-world systems without disrupting or experimenting on
actual operations. By constructing a mathematical and logical representation of a system and
driving it forward through time, practitioners can observe how the system responds to different
conditions, resource configurations, and policy choices — all at a fraction of the cost and risk
of physical experimentation. Simulation is especially powerful in high-stakes service systems
where entities are perishable, demand is stochastic, resources are finite and shared, and the
consequences of failure are severe.

Discrete-Event Simulation (DES), in particular, is a method in which the system is modeled as a
sequence of instantaneous events that change state over time. Between events, the system is
assumed to be unchanged. This paradigm is well-suited to queueing and service systems — such as
hospital operations — where entities (patients, organs) arrive, wait for resources, receive
service, and depart. Tools like Rockwell Arena Simulation Software are the industry standard for
DES in industrial engineering and health systems research. This project replicates Arena's
architectural concepts (Create, Assign, Decide, Process, Hold, Dispose modules) using Python and
the SimPy library.

This project focuses on simulating the **kidney transplant logistics supply chain** — a
system defined by perishable resources, probabilistic biological compatibility, life-and-death
outcomes, and chronic supply-demand imbalance. Specifically, it models the end-to-end pipeline
from deceased donor organ procurement through crossmatch laboratory testing, organ transport,
and transplant surgery, while simultaneously tracking a waitlist of patients competing for a
scarce resource. The simulation provides quantitative performance metrics — transplant rates,
organ waste, patient waiting times, and resource utilization — across 10 independent replications
to support statistically rigorous, evidence-based policy analysis.

---

&nbsp;

## 2. Problem Description

Every year in the United States, thousands of transplantable kidneys are discarded — not because
willing recipients do not exist, but because the logistics of matching, testing, transporting,
and scheduling surgery cannot keep pace with the narrow biological window in which a donor kidney
remains viable. As of 2023, the nonuse (discard) rate for deceased donor kidneys reached
**27.9%**, up from 26.6% in 2022 and from roughly 18–20% just a decade ago (Lentine et al.,
2025). This means that approximately **3,500 to 3,800 donated kidneys** are discarded
annually in the U.S. — while over 100,000 patients remain on the national transplant waitlist
(McKenney et al., 2024; Mohan et al., 2018).

The effects of this failure are catastrophic at the individual level and systemic at the
population level. Patients who cannot receive a transplant in time deteriorate on dialysis,
experience a sharply elevated mortality risk, and consume disproportionate healthcare resources.
Research identifies several addressable root causes:

- **No Recipient Located in Time** — Allocation and matching delays account for up to 60% of
  discard reasons in some analyses (McKenney et al., 2024). When a compatible recipient cannot
  be identified and prepared before cold ischemia time expires, a viable organ is wasted.
- **Cold Ischemia Time Accumulation** — The longer a kidney remains without blood supply, the
  greater the risk of functional decline. Each hour spent in matching queues, awaiting lab
  results, or waiting for transport compounds this risk (Friedewald et al., 2023).
- **Biopsy and Clinical Findings** — The most frequently recorded clinical reason for discard,
  accounting for ~38.2% of cases (Mohan et al., 2018). Logistical delays increase the likelihood
  that borderline organs are ultimately rejected.
- **High-Risk Donor Organs** — Kidneys with a Kidney Donor Profile Index (KDPI) ≥ 85% have
  non-utilization rates exceeding 50–60% (Friedewald et al., 2023; Lentine et al., 2025).

Because a substantial share of discards is attributable to logistical and allocation
inefficiencies — not irreversible organ failure — there is a meaningful opportunity to reduce
waste through better resource planning and process design. However, the transplant pipeline is a
complex stochastic system: arrival rates are random, matching is probabilistic, resources are
shared and finite, and the cost of failure is a human life. Decision-makers (hospital
administrators, transplant coordinators, policymakers) cannot afford to experiment with real
systems. A simulation approach is therefore required to analyze this system's behavior and
evaluate potential improvements before committing to costly or irreversible real-world changes.

---

&nbsp;

## 3. Objectives

The objectives of this simulation study are:

- To model the kidney transplant logistics pipeline as an Arena-style Discrete-Event Simulation
  using Python (SimPy), replicating the structural logic of Create, Assign, Decide, Process,
  Hold, and Dispose modules.
- To represent organ perishability through a continuous cold ischemia clock and an exponential
  quality decay function Q(t) = e^(−0.05·t), with a hard 36-hour viability deadline.
- To implement a UNOS-style organ–patient matching algorithm incorporating ABO blood type
  compatibility, 6-antigen HLA matching, Panel Reactive Antibody (PRA) sensitization screening,
  and a composite urgency/wait-time priority score.
- To model resource contention across four shared hospital resources — Crossmatch Laboratories,
  Transport Vehicles, Operating Rooms, and Surgical Teams — and measure their utilization under
  realistic demand conditions.
- To quantify key system performance indicators: organ utilization rate, organ waste rate, average
  patient wait time, average cold ischemia time at transplant, waitlist length, and resource
  utilization.
- To run 10 independent replications with distinct random seeds and produce 95% confidence
  intervals on all output metrics, providing statistically rigorous estimates of system
  performance.
- To enable "what-if" scenario analysis by allowing users to adjust resource capacities, arrival
  rates, and matching parameters through a GUI, supporting evidence-based policy recommendations.

---

&nbsp;

## 4. System Description

The system represents a single kidney transplant center that receives deceased-donor and
living-donor kidneys and maintains a waitlist of patients requiring transplantation. Two classes
of entities flow through the system simultaneously and interact through a central matching
mechanism.

**Donor kidneys** enter the system when a deceased donor organ becomes available for procurement.
Each kidney carries a biologically specific profile — blood type, HLA antigen set, and transport
origin zone — and begins accumulating cold ischemia time from the moment of harvest. The kidney
is immediately evaluated for a compatible waitlisted patient. If a match is found, it proceeds
through a sequential pipeline of crossmatch laboratory testing, physical transport to the surgical
facility, pre-operative preparation, and transplant surgery. At each stage, the kidney competes
with other organs for shared resources. If any resource is busy, the organ waits in a queue while
its viability window continues to shrink. If the cold ischemia time limit is exceeded at any
checkpoint, the organ is discarded as expired. If no compatible patient is found at all, the
kidney enters an organ pool and waits — still subject to the ischemia clock — until either a
newly arriving patient triggers a match or the organ expires.

**Waitlisted patients** enter the system continuously, representing individuals who have been
evaluated and listed for kidney transplantation. Each patient carries a biological profile (blood
type, HLA antigens, PRA sensitization score), a UNOS-style urgency classification (Critical,
High, Medium, Low), and a composite priority score that increases with wait time. Patients remain
in a priority queue, updated dynamically, until a compatible kidney becomes available. While
waiting, patients face background hourly attrition: a small probability of death and a small
probability of transfer to another center, both modeled as continuous stochastic processes.

**Living donor kidneys** represent a special case: pre-scheduled transplants with a
guaranteed-compatible recipient. These bypass the matching queue entirely and proceed directly to
crossmatch testing and surgery, sharing the same laboratory, transport, and operating room
resources as deceased-donor cases.

The system operates continuously (24 hours a day, 365 days a year) and is governed by
first-come, highest-priority-first matching logic. All inter-arrival times and service durations
are stochastically distributed, and the simulation is run for one full year (8,760 hours) with a
30-day warm-up period to reach steady-state conditions before statistics are collected.

---

&nbsp;

## 5. Model Design

The simulation model is designed using 20 Arena-equivalent modules organized into three parallel
entity paths that interact through the shared matching and resource systems. The following
describes each module and the logical flow of entities.

### Modules Used

| Module | Type | Description |
|---|---|---|
| 1 | CREATE | Deceased Donor Kidney Arrivals — Exponential(1/8 hr⁻¹), ~3/day |
| 2 | CREATE | Patient Arrivals to Waitlist — Exponential(1/4 hr⁻¹), ~6/day |
| 3 | CREATE | Living Donor Kidney Arrivals — Exponential(1/48 hr⁻¹), ~0.5/day |
| 4 | ASSIGN | Kidney Attributes — Blood type, HLA profile, transport zone |
| 5 | ASSIGN | Patient Attributes — Blood type, HLA, urgency, age, PRA score |
| 6 | DECIDE | UNOS-Style Organ–Patient Matching (ABO → HLA → PRA → Priority Score) |
| 7 | HOLD/QUEUE | Patient Waitlist — Dynamic Priority Queue |
| 8 | HOLD/QUEUE | Organ Pool — Holding area with hourly expiry checks |
| 9 | PROCESS | Crossmatch Testing — Seize Lab → Triangular(1.0, 2.0, 4.0) hrs → Release |
| 10 | PROCESS | Organ Transport — Seize Vehicle → Zone-dependent delay → Release |
| 11 | PROCESS | Surgery Preparation — Delay only: Triangular(0.5, 1.0, 2.0) hrs |
| 12 | PROCESS | Transplant Surgery — Seize OR + Team → Triangular(2.0, 3.5, 6.0) hrs → Release both |
| 13 | DECIDE | Transplant Outcome — Probabilistic graft success vs. rejection |
| 14 | DECIDE | Patient Attrition — Hourly death (0.0001/hr) and transfer (0.00005/hr) |
| 15 | DECIDE | Organ Expiry Checker — Hourly scan; removes organs exceeding 36 hrs CIT |
| 16 | DISPOSE | Successful Transplant — Records CIT, quality, wait time, HLA score |
| 17 | DISPOSE | Organ Expired — Records cold ischemia time at expiry |
| 18 | DISPOSE | Crossmatch Failed — Incompatible physical crossmatch result |
| 19 | DISPOSE | Graft Rejection — Failed surgery; patient returned to waitlist |
| 20 | DISPOSE | Patient Died / Transferred — Waitlist attrition exits |

### Flow of Entities

**Path A — Deceased Donor Kidney:**
```
Create (Kidney) → Assign (Attributes)
  → Decide: Match Found?
       ├── YES → Process (Crossmatch Lab)
       │           → Decide: Crossmatch Pass?
       │                ├── YES → Process (Transport)
       │                │          → Decide: Still Viable?
       │                │               ├── YES → Process (Surgery Prep)
       │                │               │          → Decide: Still Viable?
       │                │               │               ├── YES → Process (Surgery)
       │                │               │               │          → Decide: Graft Success?
       │                │               │               │               ├── YES → Dispose (Transplanted)
       │                │               │               │               └── NO  → Dispose (Rejection)
       │                │               │               └── NO  → Dispose (Expired)
       │                │               └── NO  → Dispose (Expired)
       │                └── NO  → Dispose (Crossmatch Failed)
       └── NO  → Hold (Organ Pool) → Hourly Check → Dispose (Expired) if CIT > 36 hrs
```

**Path B — Patient:**
```
Create (Patient) → Assign (Attributes)
  → Queue (Priority Waitlist)
  → Hourly Attrition Check:
       ├── Death     → Dispose (Died on Waitlist)
       ├── Transfer  → Dispose (Transferred Out)
       └── Survives  → Continue waiting → [When matched] → joins Path A pipeline
```

**Path C — Living Donor (Fast-Track):**
```
Create (Living Kidney + Recipient) → Assign (Guaranteed Compatible)
  → Process (Crossmatch Lab) → Process (Transport)
  → Process (Surgery) → Decide (Graft Success?)
       ├── YES → Dispose (Transplanted)
       └── NO  → Dispose (Rejection)
```

### Matching Algorithm (Module 6)

The UNOS-style matching decision applies three sequential filters:
1. **ABO Blood Type Compatibility** — Standard compatibility matrix (e.g., Type O is universal donor; Type AB can only donate to AB recipients).
2. **HLA Antigen Scoring** — Count of matching antigens (out of 6) between donor and recipient.
3. **Virtual Crossmatch (PRA)** — Patients with PRA > 80% carry a failure probability of PRA/200.

Among all passing candidates, the composite priority score is used to select the best match:

$$\text{Score} = (\text{Urgency Weight} \times 10) + (\text{Wait Days} \times 0.5) + (\text{HLA Matches} \times 2)$$

### Transplant Outcome Model (Module 13)

Surgery outcome is probabilistically determined by:

$$P(\text{Success}) = 0.95 + (0.005 \times \text{HLA Matches}) - (0.01 \times \text{CIT Hours})$$

Bounded to the interval [0.70, 1.00].

---

&nbsp;

## 6. Assumptions

The following assumptions were made to scope and simplify the model while preserving the integrity of the core dynamics:

- **Arrival processes** — Deceased donor kidney arrivals, patient arrivals, and living donor arrivals all follow independent Exponential distributions, consistent with standard Poisson arrival assumptions used in queueing theory.
- **Service time distributions** — All process delays (crossmatch testing, transport, surgery preparation, surgery) follow Triangular distributions parameterized by (minimum, mode, maximum), which is appropriate when empirical data is limited but expert estimates of extremes and most likely values are available.
- **Single transplant center** — The model represents one facility. There is no inter-center organ sharing or geographic routing beyond abstract Local/Regional/National transport zone categories.
- **Quality decay** — The cold ischemia decay Q(t) = e^(−0.05·t) is deterministic and identical for all organ types. No distinction between older and younger donor kidneys is modeled.
- **HLA matching threshold** — All levels of HLA match (0 through 6 antigens) are accepted for transplantation; a higher match simply improves the priority score and success probability.
- **First-priority, first-served** — Patients are served in priority-score order, not strictly FIFO. Wait time contributes to the priority score, ensuring longer-waiting patients are eventually prioritized.
- **No organ re-offering** — If a crossmatch fails or an organ expires during transport, it is disposed and not re-offered to the next compatible patient. This conservatively overestimates organ waste.
- **Fixed resource capacities** — Operating room, surgical team, transport vehicle, and laboratory capacities are constant throughout the simulation run. No shift schedules, breakdowns, or overtime are modeled.
- **Patient health homogeneity** — Patient success probability is determined by HLA match quality and cold ischemia time only. Comorbidities such as diabetes or cardiovascular disease are not included.
- **Living donor bypass** — All living donor kidneys arrive with a guaranteed-compatible, pre-identified recipient and bypass the matching queue entirely, consistent with real-world living donor protocols.
- **No financial modeling** — No cost per operating room hour, transport cost, or insurance variables are included.
- **Warm-up period** — A 30-day warm-up period is applied at the start of each replication. Statistics collected during warm-up are discarded to ensure steady-state conditions before data collection begins.

---

&nbsp;

## 7. Simulation Setup

The simulation is configured as follows:

| Parameter | Value |
|---|---|
| Simulation Duration | 8,760 hours (365 days / 1 year) |
| Warm-up Period | 720 hours (30 days) — statistics discarded during this period |
| Number of Replications | 10 independent runs |
| Random Seed Base | 42 (seeds per replication: 1042, 2042, …, 10042) |
| Deceased Kidney Arrival Rate | Exponential, mean 8 hrs (≈3/day) |
| Patient Arrival Rate | Exponential, mean 4 hrs (≈6/day) |
| Living Donor Rate | Exponential, mean 48 hrs (≈0.5/day) |
| Cold Ischemia Limit | 36 hours (hard viability deadline) |
| Operating Rooms | 4 |
| Surgical Teams | 5 |
| Transport Vehicles | 3 |
| Crossmatch Laboratories | 2 |

**Performance measures collected:**

- **Counter Statistics** — Total entities of each type processed (kidneys arrived, patients arrived, successful transplants, rejections, organs expired, no-match organs, waitlist deaths, transfers, living donor transplants)
- **Tally (Observation) Statistics** — Averages and distributions of: patient wait time (hrs and days), cold ischemia time at transplant, organ quality score at transplant, surgery duration, transport time, crossmatch test time, HLA match score, and patient priority score at match — with standard deviations, minima, maxima, and 95% confidence intervals
- **Time-Persistent (Time-Weighted) Statistics** — Time-averaged values of: waitlist length, organ pool size, and utilization of each of the four resources

All outputs are reported per replication and aggregated across replications using the Arena Half-Width Report format. Reports and plots are saved to the `/output/` directory.

---

&nbsp;

## 8. Results & Analysis

### 8.1 Single Replication Results (Representative Run — Replication 5)

The statistics below are drawn from the GUI live-stats readout for one representative replication:

| Metric | Value |
|---|---|
| Kidneys Arrived | 1,253 |
| Patients Arrived | 2,197 |
| Successful Transplants | 895 |
| Failed Transplants (Rejection) | 162 |
| Organs Expired (Ischemia) | 2 |
| Organs — No Compatible Match | 192 |
| Patients Died on Waitlist | 381 |
| Patients Transferred Out | 147 |
| Waitlist Length (end of run) | 665 |
| Available Organ Pool Size (end of run) | 0 |

**Resource Utilization:**

| Resource | Utilization |
|---|---|
| Operating Rooms | 12.6% |
| Surgical Teams | 10.1% |
| Transport Vehicles | 11.5% |
| Crossmatch Laboratories | 18.0% |

**Key Performance Indicators:**

| KPI | Value |
|---|---|
| Organ Utilization Rate | 71.4% |
| Organ Waste Rate | 0.2% |
| Average Patient Wait Time | 67.8 days |
| Average Cold Ischemia Time | 10.2 hours |
| Average Organ Quality at Transplant | 0.606 |

### 8.2 Across-Replication Summary (10 Replications — 95% Confidence Intervals)

| Metric | Mean | Std Dev | 95% Confidence Interval |
|---|---|---|---|
| Organ Utilization Rate (%) | 72.12 | 0.78 | [71.64, 72.61] |
| Organ Waste Rate (%) | 0.02 | 0.05 | [−0.02, 0.05] |
| Average Wait Time (days) | 76.46 | 5.34 | [73.15, 79.77] |
| Average Cold Ischemia Time (hrs) | 10.04 | 0.08 | [9.99, 10.09] |
| Average Quality at Transplant | 0.61 | 0.00 | [0.61, 0.61] |
| Total Successful Transplants | 843 | 35.44 | [821.03, 864.97] |
| Total Organs Expired | 0.20 | 0.63 | [−0.19, 0.59] |
| Average Waitlist Length | 428.79 | 25.00 | [413.29, 444.28] |
| Average OR Utilization | 0.12 | 0.00 | [0.11, 0.12] |

### 8.3 Interpretation of Results

**Supply-Demand Imbalance is the Primary Driver of Poor Outcomes.**
Across all replications, approximately 2,200 patients per year compete for roughly 1,200 deceased-donor kidneys — a demand-to-supply ratio of approximately 1.75:1. Even under ideal logistics conditions, the system structurally cannot transplant all patients who need kidneys. The 381 waitlist deaths and 665-patient end-of-run backlog are direct, unavoidable consequences of this imbalance — not of logistical failures.

**Logistics Performance is Excellent.**
Organ waste from cold ischemia expiry is near-zero (mean 0.02%, CI virtually at zero), and the average cold ischemia time at transplant (10.04 hours) is well within the 36-hour biological limit, leaving a comfortable safety margin of ~26 hours. The logistics pipeline — crossmatch testing, transport, and surgery — is operating efficiently and is not the primary cause of organ loss.

**Resource Utilization Confirms Infrastructure is Not the Bottleneck.**
All four resources are significantly underutilized: Operating Rooms at 12%, Surgical Teams at 10%, Transport Vehicles at 11.5%, and Crossmatch Labs at 18%. The highest-utilized resource, the crossmatch laboratory, processes every incoming organ regardless of match outcome, which explains its relatively higher load. Critically, this means that **doubling OR capacity or adding surgical teams would have zero impact on transplant volume** — the system is starved of organs, not of the infrastructure to process them.

**No-Match Rate Represents a Structural Biological Barrier.**
Approximately 192 organs per run (≈15.3% of arrivals) find no compatible patient at all, due to blood type incompatibility and PRA-based crossmatch exclusions. These are not logistical failures; they reflect the biological constraints of transplant medicine. This metric is also conservatively overstated by the model because the no-organ-re-offering assumption prevents a discarded organ from being re-evaluated for other candidates.

**Average Wait Time is Clinically Significant.**
Patients who successfully receive a transplant wait an average of 76.46 days (95% CI: 73.15 – 79.77 days). This two-and-a-half-month delay, while shorter than real-world national averages, still represents a meaningful period of health risk and disease progression on dialysis. The wide confidence interval (6+ days) also indicates substantial variability in individual patient experiences.

**Organ Quality is Well-Preserved.**
The average quality score at transplant of 0.61 (on a scale of 0 to 1) means organs are being transplanted at approximately 61% of peak viability. Given that the average CIT is ~10 hours, Q(10) = e^(−0.05 × 10) ≈ 0.607, this is entirely consistent with the decay model and reflects that organs are reaching the OR well before significant quality degradation occurs.

---

&nbsp;

## 9. Recommendations

Based on the simulation results, the following recommendations are made for system improvement and further investigation:

**1. Focus on Organ Supply, Not Infrastructure Capacity**
Since all four resources (ORs, surgical teams, transport vehicles, labs) are operating well below full capacity, investment in additional hospital infrastructure would yield no improvement in transplant volume. Policy efforts should focus instead on increasing the supply of donor organs — through expanded deceased-donor consent programs, increased living donor recruitment, and paired kidney exchange networks.

**2. Target the 15% No-Match Rate Through Threshold Relaxation and Paired Exchange**
Approximately 192 organs per year find no compatible patient. Research should explore whether relaxing the HLA minimum match threshold (currently 0) or implementing desensitization protocols for high-PRA patients could reduce this rate. A sensitivity analysis scenario — reducing PRA-based crossmatch failure stringency — should be tested in the simulation to quantify the trade-off between broader matching and graft success rates.

**3. Evaluate the Impact of Adding a Third Crossmatch Laboratory**
The crossmatch laboratory is the single most-utilized resource at 18%. While 18% utilization is currently manageable, it is the first resource that would become a bottleneck if organ supply were to increase (e.g., through policy interventions). A pre-emptive simulation scenario should test whether crossmatch lab capacity constrains throughput at higher kidney arrival rates.

**4. Implement Organ Re-Offering Logic**
The current model disposes every organ after a crossmatch failure without re-offering it to the next compatible patient. Real-world UNOS protocols allow for re-listing. Adding re-offering logic to the simulation would produce more realistic (and likely lower) organ waste estimates and may reveal whether sequential matching can recover previously unmatched organs.

**5. Expand the Model to a Multi-Center Network**
The single-center design is the most restrictive limitation of the current model. A multi-center extension that models inter-facility organ sharing — with realistic geographic transport times and national waitlist prioritization — would dramatically improve the model's policy relevance and allow examination of the trade-off between local preference and national equity in organ allocation.

**6. Introduce Living Donor Program Expansion as a Scenario**
Living donor kidneys (~181 per year in the base case) bypass the matching queue entirely and proceed on a fast-track to surgery. A simulation scenario that doubles or triples the living donor arrival rate (representing aggressive outreach programs) would directly quantify how much of the waitlist could be cleared and how many waitlist deaths could be prevented per additional living donor enrolled annually.

---

&nbsp;

## 10. Conclusion

This project successfully demonstrated the construction and analysis of a full-scale Arena-style Discrete-Event Simulation of a kidney transplant logistics and perishable queueing system, implemented in Python using SimPy and wrapped in a Tkinter-based GUI that mirrors the structure and workflow of Rockwell Arena Simulation Software.

The simulation model captured all critical elements of the real-world transplant pipeline: organ perishability via continuous cold ischemia clocking and exponential quality decay, UNOS-style organ–patient matching incorporating blood type compatibility, HLA scoring, and PRA sensitization, four shared hospital resources subject to queueing contention, and stochastic patient attrition through waitlist death and transfer. The model was validated architecturally through 20 Arena-equivalent modules and run across 10 independent replications to produce statistically rigorous outputs with 95% confidence intervals.

Key findings show that the system's primary challenge is an irreducible **supply-demand imbalance** — with patient arrivals (~6/day) outpacing deceased-donor kidney arrivals (~3/day) by a factor of 1.75:1. Despite this, the logistics pipeline itself performs well: the average cold ischemia time at transplant is 10.04 hours (well within the 36-hour limit), organ waste from ischemia is essentially zero, and all hospital resources are significantly underutilized. The average patient wait time of 76.46 days and the growing waitlist (428+ patients at any given time) are structural outcomes of organ scarcity, not operational inefficiency.

These results demonstrate the immense value of discrete-event simulation as a decision-support tool in healthcare operations. Rather than conducting expensive, disruptive, or ethically questionable experiments in a live clinical setting, simulation enables planners and policymakers to explore "what-if" scenarios — such as adding transport vehicles, relaxing matching thresholds, or expanding living donor programs — and quantify their expected system-level impact before any real-world commitment is made. The model developed here provides a rigorous, extensible, and academically grounded platform for the ongoing analysis of kidney transplant supply chain logistics.

---

&nbsp;

## References

Friedewald, J. J., et al. (2023). Kidney donor profile index and discard rates for high-KDPI organs. *American Journal of Transplantation*.

Lentine, K. L., et al. (2025). OPTN/SRTR 2023 Annual Data Report: Kidney. *American Journal of Transplantation, 25*(S1).

McKenney, A. S., et al. (2024). Trends and reasons for deceased donor kidney discard in the United States. *Clinical Journal of the American Society of Nephrology*.

Mohan, S., et al. (2018). Factors leading to the discard of deceased donor kidneys in the United States. *Kidney International, 94*(1), 187–197.

---
*Document generated: March 12, 2026*
*Simulation version: Arena-Style DES | Python 3 / SimPy | 10 Replications | 365-Day Horizon*
