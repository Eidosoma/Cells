# Stage S3: the cleft egg against R-full (plan for review)

**Status: draft for the lead's review (13 November). Nothing runs before approval.** Design:
[cell-division design](CELL_DIVISION_DESIGN.md) §4.2, §5, §7, §8.4 and §9; S2 built the
membrane state and insertion ([v2 design](PUMP_COMPOSITE_V2_DESIGN.md) §3).

**Purpose.** S3 runs the engine's one-cell Xenopus egg, with its furrow and restricted
cleft, under J1's registered definition, and compares it with R-full on J1's state and
on the trajectory. It qualifies the engine against the registered independent reference;
it is not a J1 verdict against the data. That verdict was made on R-full on 12 November
(J1 fails within the declared ranges), and the J1 cleft-model choice is the user's.

**Engine models run.** `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with:
- `membrane_entity_state@1` (S2);
- `scheduled_membrane_insertion@1` (S2): the furrow patch opens at 420 s with
  A_on = 10⁻⁹ m² and grows at r = (A_J1 − A_on)/(1800 s − 420 s), continuing after J1;
- `restricted_cleft_lumen@1` (new in S3, below): the lumen volume w A_new / 2, filled
  with bath fluid as it grows;
- `electrode_current_injection@1` (§4): dLB74's pulse train throughout, booked at the view
  since this round (S3 prerequisite (b)).

Field nodes: cytosol, cleft and bath, 3 (the cap is 64).

## 1. What S3 builds

**The lumen operator, `restricted_cleft_lumen@1`** (division design §4.2). R-full's lumen:
volume w A_new / 2, filled at bath composition as it grows, with no water flow.
- State: the filled volume, the supplied amounts and their reservoir work.
- View: the cleft's `extracellular_volume` from the filled volume. The volume is state,
  not w A / 2 itself, so amounts and volume always agree. It reads `membrane_area`
  (`VIEW_READS`, from the membrane state).
- Split part, exact half-steps: fill to w A / 2 at the current area. The added fluid
  carries c_bath ΔV of each species.
  - It is booked as supply from the bath: the cleft's amounts, the bath's
    `reservoir_supplied`, and the work μ_b Δn in `reservoir_work_pJ`, as @3's own supply
    books it.
  - The energy ledger gets the dilution term at the view volume, water's expression.
  - Fluid added between the last insertion half-step and the end of the step lags by
    half a step, a splitting error covered by the step study.
- Refusals:
  - a lumen node that is not a finite onset node;
  - an onset volume that differs from w A_on / 2, or another provider of that volume;
  - a lumen facing more than one onset patch (later work).
  - Insertion's onset rule ("an onset node's volume must be its declared anchor") admits
    this operator, whose volume at onset is the anchor.
- Guards, as S2's:
  - a tier-1 smoke test: the fill's amounts, every ledger closing, and a zero-growth
    world idle bitwise;
  - compiled: restart across the onset, vmap, and the composition without growth equal
    to S2's.

**The engine definition** (`validation/division/cleft_egg_engine.py`). It is built from
R-full's own `Egg` (`cleft_egg_reference.build` with the record's P_old and A/L), as
`injection_rm1.py` builds the uncleaved egg.
- A `compare` action checks every field against R-full's build: compositions on the
  activity basis, areas, capacitances, permeabilities per area, the access (A/L × D_s,
  log-mean law), w, the onset and schedule, the pulses and their carriers, and the
  temperature.
- Actions `study`, `reference` and `judge` follow `injection_rm1.py`. The judge refuses
  an unregistered protocol or a source outside a clean execution snapshot.

## 2. The prerequisites from S2 ((a) and (b) done and guarded on 13 November; (c) open)

- **(b) Injection at the view.** With a field-input provider, the composite passes the view
  to injection's half-steps (`BOOKS_AT_VIEW`). Injection then books the clamps' plate
  charges and the capacitor energy change at the view. Without a provider the call and the
  arithmetic are unchanged.
  - Guards: the two-clamp analytic image charge after insertion; every ledger closing; the
    declared booking shown to leave the electrode ledger open; a crossrev world set of
    injection (the heredity cell and the Rm1 egg) against the previous revision.
- **(a) The onset energy.** The onset opens the furrow uncharged with the lumen at bath
  composition, which is R-full's convention. The access then charges the patch to about
  Vm and dissipates ½ C_on Vm², whatever its resistance. That is the physics: charging an
  uncharged patch through a resistor.
  - At the egg's access (0.94 µS from A/L = 1.54 × 10⁻⁶ m), the time constant
    C_on / G_acc is 6.6 µs, so no admitted step resolves it. Booking the charge as an event
    would be the τ → 0 limit, wrong for a slow access. So neither is done.
  - The unbooked part is bounded by ½ C_on Vm² = ½ × 6.2 pF × (9.95 mV)² = 3.1 × 10⁻⁴ pJ.
    The engine's host energy bound at 420 s, measured on the uncleaved Rm1 egg, is
    4.5 × 10³ pJ, so the unbooked part is 7 × 10⁻⁸ of it.
  - The continuing insertion perturbs the cleft by ½ ΔC Vm² = 1.5 × 10⁻⁷ pJ per 0.5 ms step,
    0.43 pJ to J1 (R-full's values: composite-v2-20261112-01/s3-prereq).
  - Guards: one coarse step leaves exactly that heat unbooked; resolved steps (0.1 µs at
    a 5 µs access) book it in the access; a small world whose energy bound cannot cover
    it is refused. The numbers above are checked with R-full's functions before the
    plan is final.

- **(c) Found while measuring (a), open: an electrode-ledger drift at egg scale.** The
  uncleaved Rm1 egg with its two pulses, run to 420 s, fails the host electrode ledger.
  - The residual is 8.4 × 10⁻¹⁷ C, 5 times its bound. From the step where the Na
    increment crosses 2¹⁶ fmol, it drifts by exactly half an ulp of the charge terms per
    step (7.0 × 10⁻²² C).
  - With the electrode at zero current, or without it, the residual is exactly 0. The
    pulses seed it by leaving a third species, Cl, with a nonzero increment.
  - The hypothesis (v2 design §3): @3's IMEX electrode increment stops telescoping bit
    for bit. If so, the fix or a justified allowance is in `surface_pump*.py` and needs
    the lead's approval.
  - That is S3's first task, before the lumen operator.

## 3. Numerics and cost

- **Solver: IMEX ARS(2,2,2).** RK4 is not used for egg-length runs: @3's RK4 electrode
  rounding failed the static cleft egg's electrode ledger on long runs (S0b).
- **Step: at most 0.5 ms (an estimate, verified first on the built definition).** @3's
  explicit-rate bound refuses 1 ms at the full new membrane (dt × rate = 1.145, S0b). R5
  takes the area at the 2100 s horizon with only C_old + C_on as capacitance, which scales
  that to about 0.9 of the bound at 0.5 ms. The study then runs 0.5, 0.25 and 0.125 ms.
  If 0.5 ms is refused, it runs 0.25, 0.125 and 0.0625 ms, and its cost doubles.
  - From R-full's J1 state, the static cleft egg agreed with R-full to 3 × 10⁻¹⁰,
    10⁻¹¹ and 2 × 10⁻¹² V at those steps (S0b).
- **Cost** (one CPU core, vector windows with device checks):
  - the 35-min uncleaved egg ran at 0.11 ms per step at 1 ms (S0b smoke), and S2
    measured +15% for insertion on 3 nodes;
  - 2100 s at 0.25 ms is 8.4 × 10⁶ steps, about 15–25 min;
  - the study (0.5, 0.25, 0.125 ms) is about 1–1.5 h;
  - R-full's J1 run takes minutes (170 s in the record's last search).

## 4. The registered comparison (protocol draft; values after the development runs)

**Quantities**, from the pulse protocol as `rm_definition` defines them, in engine and
reference alike:

| # | Quantity | Definition | R-full (record) |
| --- | --- | --- | --- |
| Q1 | Em at J1 | V at the front edge of pulse 180 (1800 s) | −12.79494 mV |
| Q2 | Rm at J1 | Pair (179, 180) | 488.000 kΩ (the A/L calibration target) |
| Q3 | Rm1 (reported, not judged) | Pair (0, 1), before the onset | 852.000 kΩ |
| Q4 | Em trajectory | V at the front edge of every pulse, 0 to 210; maximum difference | – |
| Q5 | Lumen K and Na at J1 | mM, activity basis | about 29 and 21 mM |

**Reference.** R-full under the registered defaults (Radau, rtol 10⁻¹⁰), at the record's
calibration (P_old = 6.161 × 10⁻¹⁰ m/s, A/L = 1.5406 × 10⁻⁶ m), recomputed for each
quantity from the registered commit.

**Tolerance per quantity: 3 × (engine step term + reference term)**, the rule Rm1's
registered protocol uses:
- engine step term: |Q(dt_j) − Q(dt_j / 2)| at the judged step dt_j = 0.25 ms, with the observed
  order checked (about 2 for ARS(2,2,2));
- reference term: the largest |ΔQ| of R-full against rtol 10⁻⁸, BDF at rtol 10⁻¹⁰ and
  LSODA, plus the activation area 10⁻¹⁰ m², as J1's `reference_numerics` registers it.
  For Em at J1 this term is 0.18 µV in the band record;
- Q4's terms are maxima over the samples.

**Verdict.** The comparison passes when every |engine − R-full| is within its tolerance.
A failure is recorded and diagnosed, never retuned.

**Judged run.** Once, on CPU, from a clean snapshot of main after registration. The
protocol records the judged step and the commit.

**Stop rule** (before registration): stop and report if the study shows no convergence
(observed order far from 2), or if the energy ledger fails at an admitted step. An
implicit membrane–cleft term would then be a new solver version (division design §5.4).

## 5. Order of work (CPU 4, through run_detached)

1. Prerequisite (c): the electrode-ledger drift at egg scale, the hypothesis verified
   and the fix or allowance approved and built (a 420 s run reproduces it in 1 min).
2. The lumen operator and its guards.
3. The engine definition, and `compare` against R-full's build.
4. Development runs: the step study, and R-full's reference term per quantity.
5. The registration draft, to the lead: references, terms, tolerances, judged step.
6. The judged run, once.

## 6. Choices (decided by the lead, 13 November)

- **The judged step is 0.25 ms.** The step study's terms are taken at 0.25 against
  0.125 ms.
- **Q5, lumen K and Na at J1, is judged.** The lumen operator is S3's new physics.
- **Q3, Rm1, is reported only.** It was judged on the uncleaved egg in injection's
  acceptance.
- The back-loaded schedule (an in-band J1 member) is out of S3's comparison; the default
  schedule only.
