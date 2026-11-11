# First heredity experiment on Cells physics (E07-v1 design)

Design of 8 November 2026, not yet run; user choices are recorded in [D133](DECISIONS.md). The structured design, cost model and
single-cell pre-screens are in
`/mnt/workspaces/Cells/heredity-design-20261108-01/` (`design.json`,
`prescreen-03…06.json`). Experiment definitions live in
[Experiments](EXPERIMENTS.md); status in [Progress](../PROGRESS.md).

## Why this experiment

*Plastic Heredity* asks two things about an acquired state, a change a cell picks
up from its surroundings rather than from its genes:
1. **Does it last?** Once the signal that caused it is gone, does the cell keep it?
2. **Does it outlive the cells that hold it?** When those cells die and are
   replaced by new ones, does the state pass on?

E07-v1 tests both in one simulated tissue, under the same physics. The plan:
1. **Write.** A brief signal switches a small disc of cells from their resting
   voltage (H) to a depolarised voltage (D).
2. **Release.** The signal stops. Does the disc stay D?
3. **Replace.** The disc's cells are replaced one by one with fresh resting cells.
   Does the D pattern survive once none of the original cells is left?

Experiments that test only one of the questions on their own are listed in
[Experiments](EXPERIMENTS.md) (E03 for lasting, E05 for passing on).

It runs in three pre-registered stages:
- **A, write and retain:** the write and release steps, plus a check for hidden
  differences between cells that look the same (E03 and E04 in
  [Experiments](EXPERIMENTS.md)).
- **B, renewal:** scripted replacement of the disc's cells (E05 and E07).
- **C, history:** restarts from saved stage A and B states, comparing cells that
  look alike but got there by different histories (the E04 extension).

E06 and the BITSEY-geometry E04 need the nominal-clock regulatory graph and stay
on the BITSEY track.

## Where the design stands (11 November 2026)

Not yet run. Development runs since 8 November changed several assumptions
behind the protocol below, so the protocol is due to be revised with the user
before any judged run. Details and evidence are in [Progress](../PROGRESS.md).

**Retention.**
- **The cue works.** In the full tissue, a brief Na-leak cue writes a D disc
  within 0.4 s (pilot W1).
- **Fresh discs hold.** On a simplified sheet, cue-written 37-cell discs held
  for 70 min at couplings ×0.3, ×0.6 and ×1. A 19-cell disc held at ×0.3 and
  ×0.6 but was lost after 16.5 min at ×1.
- **Earlier limits were too pessimistic.** Pre-screen 7 started from fully loaded
  D cells, and its coupling limits should not be used for cue-written discs.

**Renewal.**
- **No supported rule has passed.** With newcomers fully coupled on arrival, the
  disc erodes. A rule that kept the departing cell's junction state renewed one
  large disc, but it has no biological basis and is excluded (D139).
- **The literature rule is untested.** In it, newcomers arrive uncoupled and form
  junctions over tens of minutes. It has not been run under turnover yet. It
  needs the cell-replacement model, which is in qualification.
- **Rates may need rethinking.** At 2–20 %/min, newcomers live only 5–50 min,
  about as long as junction formation takes. The replacement rates may need to be
  set relative to that time.
- **B1 needs strengthening.** One turnover is not a steady state: under the
  excluded rule a disc passed B1 after one turnover and collapsed in the second.

**Volume.**
- **Water and volume are now in the engine** (D133 had deferred them), so the
  fixed-volume cap below can be revisited.
- **With water,** a D cell swells, to about 1.76× its volume without regulation
  and 1.1–1.5× with K–Cl cotransport.
- **Water runs on fresh discs** are in progress.

**Cost.**
- **On the L4,** a batched world-step costs 2.28 ms at 256 worlds, or 4.0–4.5 ms
  with observers. Tier 1 is therefore about 4,100–7,200 L4 GPU-hours, against
  the 560–840 estimated below.
- **GH200 throughput is unmeasured.**

**Engine gaps from the build plan.**

| Gap | Status |
| --- | --- |
| G1 channel populations and G1b parity | Done |
| G4 batched worlds | Done |
| G2 carrier replacement | Built; qualification in progress |
| G6 gate-rate control | Not built |

## What the pre-screen found (single-cell, design inputs only)

- BETSE's default world is far from its slow steady state. In a fixed volume it
  drifts towards −6 mV, 239 mM K⁺ and 493 mOsm, with time constants of 0.34 s,
  204 s and 3.7 h. Its fast Vm, −23.3 mV, matches BETSE's −23.32 mV. Any
  heredity run therefore needs a prepared stationary state.
- Kir2.1 alone never gives bistability. A NaV1.2 window current with Kir2.1 and
  Na leak scaled ×0.2–0.32 does, on both fast and slow time scales, within
  BETSE's own default-network ranges. Example states: H at −79.6 mV and D at
  −21.5 mV, with an unstable point near −39 mV.
- D cells load K⁺ and anions in a fixed volume: about +9% osmolarity after 1 h
  and +15% after 2 h. D residence is capped near 70 min unless water and volume
  are added.
- Voltage-gated junctions act in 0.05–0.4 s and close to about 0.1 at
  |Vj| ≥ 55 mV, so written domains may self-insulate.

## Protocol (draft of 8 November, to be revised before registration)

| Element | Specification |
| --- | --- |
| World | About 225 cells (~825 nodes), BETSE coefficients plus the heredity parameter set, 10–20% per-world heterogeneity; arms of a world share one preparation (paired) |
| Sequence | Preparation to stationarity; 5 min baseline; cue of Na leak ×10 on a 7-, 19- or 37-cell disc for 2 s to 5 min; 60 min retention |
| Replacement (B) | Oldest carriers first at 2, 6 or 20%/min for 50 min. Each newcomer is reset to an isolated-H template with a material, charge and energy ledger, a new carrier ID and a lineage entry |
| Challenges | NaV block of 50% or 80% for 30 s |
| Controls | No cue; sham (bitwise identical); NaV block; Kir block; frozen junction gate; boundary cut; global junction block; same-state, isolated and outside newcomers; replacement without a write |
| Criteria | A1: some arm retains in ≥90% of worlds while NaV-blocked retains in ≤5%. B1: Jaccard ≥0.8 through full founder turnover in ≥80% of worlds. C1: matched pairs differ in erasure (paired CI excludes 0) |
| Validity gates | Spontaneous D in ≤1/32 worlds; osmotic excess flagged above 10%, censored above 15% |
| Numerics | Ledger, charge and energy bounds; dt study 4 to 0.25 ms; spatial refinement on a 61-cell world; 3 h drift; bitwise restart (compilation cache off); CPU, L4 and GH200 agreement |

Stage 0 runs before any of this. It is a fading-memory pilot on the qualified
`resolved_pump_tissue@1`: a 60 s pump block in a 19-cell disc with a no-cue
control. It measures decay, background drift and the real cost per step.

## Ensemble and JUPITER cost

32 paired worlds per arm, 21 + 16 + 8 arms, at dt 1 ms (3.6e6 steps per model
hour). Tier 1 is 1,786 world-hours. The measured anchor is 9.17 ms per step on
the L4 for one world, execution only; per-step host checks raise it to about
50 ms.

| Execution | Tier-1 GPU-hours |
| --- | --- |
| Today's sequential `lax.map` | about 12,500 (infeasible) |
| 64-world `vmap` batches (assumed 30 ms per batch step) | about 840 |
| 256-world batches (assumed) | about 560 |

Tier 2 adds precision, an expression carrier, noise and confirmatory seeds, for
4,150–6,230 GPU-hours. Tiers 1 and 2 total about 7,100, within the production
share of the 10,000-hour allocation. Batched worlds with on-device checks are on
the critical path to JUPITER.

## Build plan (about 25–35 developer-days)

| Gap | Work | Effort |
| --- | --- | --- |
| G1 | Channel populations (NaV1.2, Kir2.1, Kv1.5) in the IMEX pump family, with stiff-gate handling; merges with the Kv1.5 version and parity rung 4 | 5–7 d |
| G1b | BETSE parity rung 4, plus a write/release reference | 2–3 d |
| G2 | Carrier replacement operation with ledgers and lineage | 3–5 d |
| G3 | Heterogeneous worlds | 3–4 d |
| G4 | Batched worlds (`vmap`) with device-side diagnostics | 5–8 d |
| G5 | Experiment driver, observers and pre-registration | 4–6 d |
| G6 | Junction gate-rate control | 1 d |
| G9 | Hour-scale qualification | 1–2 d plus detached runs |

An expression carrier (Ca/CaV plus a slow regulator, checked against BETSE's
default network) is a parallel Stage D of 12–20 days.

## Risks

- Fixed-volume realism.
- Tissue bistability may differ from the single-cell map.
- Bistability is chosen through parameters, so the result shows sufficiency,
  not spontaneous memory.
- Scripted replacement is not autonomous renewal.
- Tier 1 has no noise.
- Batched throughput is unmeasured.
- NaV gates are stiff.
- Parameters are uncalibrated defaults.
- Junction self-insulation may stop newcomers from converting; the frozen-gate
  and coupling arms test this.
