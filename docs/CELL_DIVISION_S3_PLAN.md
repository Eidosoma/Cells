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
  - **The fill's energy budget** (as built; accepted by the lead, 13 November). With @3's free
    energy at the view, G(n, V) = RT Σ_s n_s (ln(n_s / V) − 1), a fill dV with dn_s = c_b,s dV
    changes G by dG = G(n + dn, V + dV) − G(n, V). The bath gives up W = Σ μ_b dn − Π_b dV:
    its solutes' work, booked as @3 books its supply, and the volume work of its fluid at its
    osmotic pressure Π_b = RT Σ c_b (the water law's bath water work at ψ_b = −Π_b). Their
    difference, written with c' = (n + dn) / (V + dV) and φ(y) = y ln y − y + 1,
    H = W − dG = RT Σ_s c'_s [V φ(c_s / c'_s) + dV φ(c_b,s / c'_s)] ≥ 0, is a Jensen gap, zero
    at bath composition: the mixing heat of bath fluid entering a lumen of another
    composition. So
    dG = Σ μ_b dn − Π_b dV − H.
    - Booked: −Π_b dV in the declared work field `lumen_fluid_work_pJ`, H in the declared heat
      field `lumen_fill_dissipated_energy_pJ`. The dilution term −RT N ln(V / V_on) brings @3's
      chemical term on the declared volume to G at the view.
    - Without the last two terms the ledger misses RT c_tot dV per fill even at bath
      composition: 3.26 × 10⁵ pJ by J1, against an IMEX bound of about 2 × 10³ pJ.
    - Guards: an IMEX energy bound (2 × 10⁻³ of flows of order 10⁶ pJ in the egg) cannot see
      an error in these terms. They are guarded by the NumPy mixing-gap test (H against
      W − dG written out independently, to 10⁻⁹) and by an RK4 run, whose energy bound has no
      solver tolerance (it closes below 10⁻¹² pJ).
  - Fluid added between the last insertion half-step and the end of the step lags by
    half a step, a splitting error covered by the step study. The dynamics see the midpoint
    area and volume; at a saved row the volume trails the area by w r h / 2 (9 × 10⁻⁸ of the
    lumen at J1 at 0.25 ms).
  - **The observer** (the lead's ruling, 13 November): at saved times the lumen is read filled
    to its patch's area, (n + c_b (T − ΔV)) / (V_on + T) with T = w (A − A_on) / 2, which is
    R-full's lumen (volume w A / 2 exactly). It is written in the fill's own operations, so it
    equals a NumPy fill of the saved row to that area bitwise (tested). Q5 is defined through
    it; the dynamics are unchanged.
- Refusals:
  - a lumen node that is not a finite onset node;
  - an onset volume that differs from w A_on / 2, or another provider of that volume;
  - a lumen facing more than one onset patch (later work).
  - As built, also: a lumen faced by no patch; a source that is not a held bath, or not
    electroneutral (the lumen has no background-charge state, so a bath's background could not
    enter with its fluid); a shrinking fill, and a volume above its area's.
  - Insertion's onset rule ("an onset node's volume must be its declared anchor") admits
    this operator, whose volume at onset is the anchor.
- Guards, as S2's:
  - a tier-1 smoke test: the fill's amounts, every ledger closing, and a zero-growth
    world idle bitwise;
  - compiled: restart across the onset, vmap, and the composition without growth equal
    to S2's.
  - Owed by S5: a padded-slot test of the lumen (S2 has one for insertion; the first
    partition pads its slots).

**The engine definition** (`validation/division/cleft_egg_engine.py`). It is built from
R-full's own `Egg` (`cleft_egg_reference.build` with the record's P_old and A/L), as
`injection_rm1.py` builds the uncleaved egg.
- A `compare` action checks every field against R-full's build: compositions on the
  activity basis, areas, capacitances, permeabilities per area, the access (A/L × D_s,
  log-mean law), w, the onset and schedule, the pulses and their carriers, and the
  temperature.
- Actions `study`, `reference` and `judge` follow `injection_rm1.py`. The judge refuses
  an unregistered protocol or a source outside a clean execution snapshot.

## 2. The prerequisites from S2 ((a) and (b) done and guarded on 13 November; (c) pinned down, its fix awaiting approval)

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

- **(c) Found while measuring (a), and pinned down: an electrode-ledger drift at egg
  scale** (v2 design §3).
  - The uncleaved Rm1 egg with its two pulses, run to 420 s, fails the host electrode
    ledger by 8.4 × 10⁻¹⁷ C, 5 times its bound.
  - The cause: the compiled step sums a state's species charges in two orders, one at a
    step's end and one at the next step's start. XLA leaves the order of a reduce
    unspecified. The two orders differ by the rounding of Cl's small term at Na's ulp,
    so the electrode increments stop telescoping.
  - Written as explicit adds in species order, the sum closes the ledger exactly at
    420 s, and every other field stays bitwise identical.
  - The fix is in `surface_tissue.capacitor_change`: explicit adds, plus an optimization
    barrier on the device. It is branch work, approved 13 November but not landed.
  - Its D148 guard leaves every forward run bitwise identical (58 worlds, four programs).
  - The stop rule triggered all the same. W2's stationary judge moves 43 registered
    step-map consistency numbers by about 10⁻¹⁴ relative, through the Jacobian that
    automatic differentiation takes. Its verdicts are unchanged.
  - Option 3 drops the barrier and keeps the explicit adds. It was registered before its
    runs, and its outcome is A under that rule.
    - W1's and W2's step-map numbers are unchanged, the egg's ledger is exact, and the
      forward subset is identical.
    - The rule exempts ledger diagnostics. W1's and Rm1's electrode and global-charge
      ratios moved, and the lead rules on that exemption.
  - It lands alone, after the hold decision at the L4 gap. S3's egg runs wait for it on
    main (v2 design §3).

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
| Q5 | Lumen K and Na at J1 | mM, activity basis; the engine's observer reads the lumen filled to the area at 1800 s (§1) | about 29 and 21 mM |

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

1. Prerequisite (c): the approved fix to the electrode-ledger drift, built with its guards
   (a 420 s run reproduces the drift in 40 s).
2. The lumen operator and its guards. Built and accepted 13 November
   (`src/cells/models/operators/restricted_lumen.py`).
3. The engine definition, and `compare` against R-full's build. Built 13 November
   (`validation/division/cleft_egg_engine.py`): 30 fields, 26 exactly R-full's, 2 within
   10⁻¹², 2 declared (the cytosol charge anchor's egg-scale granularity). Then, approved the
   same day: a bounded ledger probe of the definition through the onset plus 10⁵ steps at
   0.25 ms (no Q quantity), and the study, reference and judge actions, written without
   running them, with the protocol drafted as PROPOSED
   (`validation/division/cleft_egg_protocol.json`).
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
