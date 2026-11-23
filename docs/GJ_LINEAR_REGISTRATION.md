# GJ-L1: the linear model's registered comparison (registration)

**Status: proposed for registration, 23 November 2026, for the lead.** Docs and validation only, with
no src change. Branch `gj-registrations` from main db54d0f5. It is to be tagged before any judged run.
The proposed tag is `gj-linear-registered-2026-11-23`.

**Sources.**
- The preprint: J. Grodstein, J. Mathews and M. Levin, bioRxiv
  doi:[10.64898/2026.09.02.748840](https://doi.org/10.64898/2026.09.02.748840), version 1, CC-BY 4.0:
  equations 1-2, the appendix, Figures 3, 5, 7 and 8.
- The user's approval (D219, 18 November 2026): the linear model's numerical qualification is a
  judged comparison under a registered protocol with code-blind references. Figure 8 is judged
  against independently derived physical balances, and the printed recursion's discrepancy is kept
  as a finding.
- D308: a registration names a reader that exists at its tag.
- The development work: [GAP_JUNCTION_CANCER_REPLICATION.md](GAP_JUNCTION_CANCER_REPLICATION.md) §4.

**What is registered.** The tag holds these files, read byte for byte as tagged:
- this document, which is the authority;
- `validation/gap_junction_tissue/linear_judge.py`, its arithmetic and the comparison's reader:
  - the registered networks and arms;
  - the error terms as functions;
  - the table, built from the engine's run alone;
  - the reader of the references' interface, which refuses a mismatch;
  - the judge, the plants' rows and the reported findings;
- `validation/gap_junction_tissue/linear_rule.json`, every number, as `linear_judge.py rule` writes it;
- `validation/gap_junction_tissue/references/spec/linear.json`, what the references read: the model,
  the networks and the interface, with no run's value (`linear_judge.py spec`);
- `validation/gap_junction_tissue/run.py` and `worlds.py`, the driver that makes the judged run;
- `tests/unit/test_gap_junction_linear_judge.py`, the reader and every reader-level plant on
  synthetic inputs (1.7 s, no world compiled).

**Engine models (AGENTS.md).**
- **The Norton form:** `resolved_pump_tissue@3`, with `constant_field@1` membranes and junctions for
  one neutral species and held reservoirs.
- **The form as written:** `resolved_pump_composite@1` over @3, with `local_species_reactions@1` (a
  zeroth-order source and a first-order decay in each cell) and the passive-routes kind's
  `passive_neutral_permeation@1` on junctions and on the probes' patches.
- **Both:** `junction_voltage_relaxation@1` pinned open, the
  `resolved_capacitor_components_current_continuity@1` closure, and
  `imex_ars222_face_electromigration@1` with `capacitive_reduction_gauged_damped_newton@2`.

**The engine under test.** The judged run is fresh, from a clean execution snapshot of the tag's
revision (validation/source_snapshot.py), at the tag's src (main db54d0f5). It records the revision
and the snapshot. A src fix after any reading needs an amendment, tagged before the rerun, and the
first verdicts stay in the record.

## 1. The claim

The engine's two forms of the preprint's linear model reach the steady states that the model's own
balances define, within tolerances derived from stated error terms:
- each cell's steady [mR] in Figure 3b's two cells, Figure 5b's lumped pair and Figure 5a's drawn
  network, over a range of junction conductances;
- the Norton conductance and the intercept of straight chains of 1 to 5 and 10 cells (Figure 8),
  against independently derived physical balances.

It qualifies, against analytic references:
- @3's neutral permeant species on its own membrane and junction routes (the Norton form);
- the passive routes' neutral law beside reactions on a junction host, with its O(dt²) split
  (the form as written).

Not claimed: the preprint's tissue simulations (Tables 1-3), its EMT switch, or any charged
species.

## 2. The model and its two forms

The preprint's linear cell (equation 1) has generation i_gen0 = K_dec mR_UL and decay K_dec. With
G_eq = V K_dec, its steady state is [mR] = mR_UL − i_exit / G_eq. Junctions carry
G_GJ ([mR]_a − [mR]_b) (Fick; the model has no drift).
- **The Norton form** gives each cell a membrane of conductance P A = V K_dec to a reservoir held at
  mR_UL. Both forms give V dc/dt = G_eq (mR_UL − c) − outflows, term for term. Its steady state is
  the fixed point of an explicit scheme on a linear system, which no step error moves.
- **The form as written** has the source and the decay in each cell, split about @3's step
  (Strang's split of the reactions' SSPRK(3,3) halves about ARS(2,2,2)). Its fixed point moves by
  O(dt²).

Declared values (not the preprint's, which reports this model in ratios only):
- radius 5 µm;
- K_dec = 0.05 /s;
- a horizon T = 600 s, 30 slowest-mode time constants;
- S = 10 s, the window of the steady check and of the probe's ledger.

One preprint unit of [mR] is 1 mM in the Norton form and 1 µM as written. Conductances are in units
of one cell's G_eq,1 = V_cell K_dec.

**The step rule** (worlds.step): dt = 1/4 s, halved until dt × @3's explicit rate ≤ 0.04. The rate is
2 max_i Σ P A / V_i. The bound comes from @3's energy check (FR-18), not from stability.

## 3. The arms

Every network's declaration (cells, unloaded values, sizes, junctions, probes) is in
`linear_rule.json` (`networks`). Its arms (`arms`) carry each one's step.

| Figure | Network | Norton arms | As-written arms |
| --- | --- | --- | --- |
| 3b | two equal cells, unloaded 5 and 10, G_GJ = g G_eq | g = 0.5, 1, 2, 5, 10, 50 | g = 0.5, 1, 2, 5, 10 |
| 5b | cell A (unloaded 10) and cell B, 4/3 its size (unloaded 5) | g = 1, 10, 50 | g = 1, 10 |
| 5a | the drawn network: A with two backup cells at 10, B with three at 5 | g = 1, 10, 50 | g = 1, and 10 through the windowed path |
| 8 | a straight chain of n cells at G_GJ = G_eq,1, unloaded 1, its end cell loaded by a probe (G_probe = G_eq,1) to a reservoir held at 0.5 and, in a second arm, at 2 | n = 1, 2, 3, 4, 5, 10, both loads | the same |
| planted | Figure 3b at g = 1 with every junction ×1.01 (P-N1, P-W1) | `control-planted` | `aw-control-planted` |

That makes 25 Norton arms and 22 as-written arms. Every cell starts at its unloaded value.
- The Norton arms run at the step rule's dt.
- The as-written arms run at dt, dt/2 and dt/4.
- Figure 5a at 10 G_eq as written runs through the windowed execution (`cells.execution.windows`)
  at all three steps. Its record is written by `cells.records.window_io.write_windowed_run`. The
  full trace would need 2.6 GB at its step against the runner's 2 GB.
- As-written arms at 50 G_eq are left out by name. Their step (1/512 s for Figure 5a) would make the
  triple about 2 million steps.

## 4. What is judged, and the error terms

**The quantities, each relative to its reference:**
- each cell's steady concentration at the judged step, read from the engine's own amounts and
  volumes;
- for each chain and form: the Norton conductance G_eq,n / G_eq,1 and the intercept, from the two
  loads' (exit flux, port concentration) points. The exit flux is the probe's own ledger over the
  last S, so G = (i₂ − i₁)/(c₁ − c₂) and the intercept is c₁ + i₁/G.

**The error terms** (functions in `linear_judge.py`; each from the declaration and the engine's own
run, never from a reference value):
- **Transient:** A e^(−K_dec T) × 1.01.
  - A = √(N V_max/V_min) ρ, with ρ = (max − min)/min over the arm's unloaded and held values.
  - Every mode decays at least at K_dec: the Norton matrix dominates K_dec V.
  - The scheme's per-step factor exceeds e^(−x) by at most x³/6, hence the factor 1.01.
  - At T = 600 s this is 9e-14 to 3e-13.
- **Rounding of the state at the fixed point:** 4u (ρ/(K_dec dt) + (1 + G_max)(1 + ρ) + 1).
  - u = 2⁻⁵³. G_max is the largest summed junction and probe conductance of a cell, in units of
    its own G_eq.
  - Each step's rounding is damped by at least K_dec dt per step.
  - This is 4e-14 to 5e-12.
- **The ledger's rounding:** 2u N (T/S), for N steps.
  - Each step's transfer is added into a running total that reaches T/S times the window's
    transfer, and the window is a difference of two such totals.
  - This is 3e-11 to 4e-9.
- **The reference's own accuracy:** each value's declared `accuracy_rel`, at most 1e-13. It is
  added to that value's tolerance.

**The Norton form**, judged at dt:
- **Concentrations:** the floor F_N (transient + rounding), F_N = 2, is 3.4e-13 to 1.0e-11 per arm.
  The tolerance is the floor plus the reference's accuracy.
- **Steady:** the largest relative change over the last S must be within the floor.
- **The ledger:** the probe's exit flux from its own ledger against G_probe (c − held), from the
  same run. The bound is F_N × ledger + 2 (c/|c − held|) × floor. This check is internal to the
  engine; no reference enters it.
- **Chains:** G and the intercept carry the first-order propagation of the concentrations' floor
  and the fluxes' bound through the two-load formulas (`two_load`).

**The form as written**, judged at dt/4. This is FR-25's rule (validation/gene_regulation/registration.py):
- **The estimate:** est = max over cells |c(dt/2) − c(dt/4)| / |c(dt/4)| / (2^p − 1), with p = 2
  declared (Strang's split; above).
- **The tolerance:** max(F_W est, floor) + accuracy. F_W = 3 is Roache's factor of safety for two
  grids at an assumed order, as in FR-25. The floor is the Norton floor at dt/4.
- **The order check:** q = log₂(max|c(dt) − c(dt/2)| / max|c(dt/2) − c(dt/4)|) must lie in
  [p − 0.5, 3.5] = [1.5, 3.5]. Otherwise the arm is inconclusive.
  - 3.5 is SSPRK(3,3)'s order plus the margin, the highest order in the scheme.
  - Where F_W est ≤ floor, the arm is judged at the floor and its order is not checked.
- **Steady:** each of the three runs is steady within its own floor.
- **Chains:** G and the intercept at each step, by the same rule, with the Norton propagation as
  their floor.
- The probe's ledger as written moves with the split by O(dt²). It is reported, not judged.

**The plants' power.** P-N1 moves cell A by 8.3e-4 and cell B by 6.6e-4: about 1e9 times its floor,
and over 100 times any as-written tolerance the development runs suggest.

## 5. Verdicts, retry and precedence

- **An arm** is:
  - inconclusive if its order falls outside the window;
  - else failed if any judged quantity exceeds its tolerance, if its steady or ledger check fails,
    or if the engine refused any of its runs;
  - else passed.
- **A chain** takes the same verdicts over G and the intercept.
- **The comparison** (FR-25's precedence, D308): any failed arm or chain makes it failed; else any
  inconclusive one makes it inconclusive; else it is passed.
- **The plants:** both engine plants (P-N1, P-W1) must fail by their gap: each must run, and its gap
  must exceed its tolerance. A plant that passes, is missing, is refused or is inconclusive makes
  the verdict "instrument not validated", whatever the other arms show.
- **The retry, once, inconclusive as-written arms only:** a finer triple, dt/2, dt/4 and dt/8,
  judged at dt/8 under the same rule. Nothing else is retried.
  - **The tagged driver cannot make it yet.** `run.py` takes the triple from the step rule's dt
    and runs every arm.
  - A retry therefore needs a tagged amendment, before it runs, that adds the option (the finer
    base step, and the inconclusive arms alone). This is D308's rule applied to the driver.
  - A run that the harness stops (memory, runtime limit, machine fault) is rerun once from the same
    snapshot.
  - An engine refusal is a result, never rerun.

## 6. The planted failures

| ID | Where | What | Must |
| --- | --- | --- | --- |
| P-N1 | the judged run (`control-planted`) | Norton Figure 3b at g = 1, every junction ×1.01, against the unperturbed reference | fail, by about 1e9 times its tolerance |
| P-W1 | the judged run (`aw-control-planted`) | the same as written, every junction route ×1.01, with its own triple | fail, 8.3e-4 against a tolerance below 1e-5 |
| P-R1 | reader, synthetic | a reference concentration raised by 1e-9 of itself | fail its Norton arm |
| P-R2 | reader, synthetic | the printed recursion read as Figure 7's resistance form as Figure 8's reference | fail at n ≥ 3 (31% at n = 3) and pass at n = 1 and 2, where the two agree |
| P-R3 | reader, synthetic | an echoed declaration with the unloaded values swapped | be refused before any comparison |
| P-R4 | reader, synthetic | a registered network missing from the interface | be refused, never passed |
| P-O1 | judge, synthetic | as written, a step-independent bias of 1e-5 with a second-order error | fail: its order is 2, but its gap exceeds 3 est |
| P-O2 | judge, synthetic | as written, first-order convergence | be inconclusive: order 1 lies outside [1.5, 3.5] |

The test file runs P-R1 to P-O2 at the tag, on synthetic inputs alone. It also shows that the
retry replaces an inconclusive arm.

## 7. The references and their interface

**They are code-blind.** A separate agent writes them from the preprint and
`references/spec/linear.json` alone. It never sees Cells' code (`src/`, the rest of
`validation/gap_junction_tissue/`), its runs, the replication note or PROGRESS.md.

**Their interface** is `validation/gap_junction_tissue/references/interface/linear.json`. Its keys
are in `linear_rule.json` (`interface`):
- `networks`: one entry per registered network, with:
  - its `declaration` echoed as read;
  - `concentrations`, each cell's steady state by cell id, in the preprint's units;
  - `accuracy_rel`;
  - `method`.
- `chains`: G_eq,n / G_eq,1 and the intercept for n = 1, 2, 3, 4, 5 and 10, from the physical
  balances.
- `limits`: Figure 3b's and Figure 5b's limits as G_GJ grows, and the chain's as n grows.
- `printed_recursion`: the appendix's recursion, taken literally and read as Figure 7's resistance
  form, at G_GJ = G_eq,1.

**The reader** (`read_interface`) refuses, before any comparison:
- a wrong format;
- a missing network or chain;
- an echoed declaration that differs from the rule's by more than 1e-12 relative;
- a missing or non-finite value;
- an `accuracy_rel` above 1e-13.

Cells are matched by id, never by position. `structure` prints the interface's keys and types,
never a value.

## 8. Reported, never judged

**Publication targets.** The references' values against the preprint's printed and read values.
A value agrees when it lies within half a unit of its last printed digit:
- Figure 3b's 6.67 and 8.33 at G_GJ = G_eq (read);
- Figure 3b's limit, 7.5 (the text's equal weights);
- Figure 5's caption, 7.15.
  - Against the lumped model's limit 50/7 = 7.142857 the difference is 0.0071, outside the
    half-unit 0.005.
  - This is registered as a known discrepancy: the caption's rounding or reading.

**Findings, kept as in D219.**
- The text says cell B is 1.5x cell A; the caption and the drawn network say 1.33x.
- Equation 2's printed second line.
- The appendix's recursion.
  - Taken literally, its right side is a resistance.
  - Read as Figure 7's resistance form, it is 31%, 72% and 117% above the physical balance at
    n = 3, 4 and 5.

## 9. How the judged run is made and judged

1. **The run:** from a clean execution snapshot of the tag, on one CPU:
   `python -B validation/gap_junction_tissue/run.py OUT figure3 figure5 figure8 control aswritten`.
   - From the development timings (dev-04 ran dt and dt/2 in 46 minutes) and the triple's extra
     cost, this is about 2 CPU-hours. On a light CPU shared with other jobs it is several hours.
   - Each arm's trace stays within the runner's 2 GB budget. The process's peak was 3.5 GB in the
     20 s smoke, which compiled every arm's world in one process, so run it under an 8 GB cap.
   - The smoke's unit reached its 90-minute cap during the last chain's triple, a limit of the
     harness. Its table read all 47 arms and 12 chains; 45 and 11 were complete, and the as-written
     chain path ran for n = 1 to 5.
   - The judged run takes the registered 600 s horizon. `--end` shortens it for smoke runs only.
2. **The table**, from the engine alone, before any reference is read:
   `python -m validation.gap_junction_tissue.linear_judge table OUT --out table.json`.
3. **The judgement**, once the references' tag exists:
   `python -m validation.gap_junction_tissue.linear_judge judge table.json --interface DIR --out verdict.json`.

## 10. What is not blind

- **The development runs.** The registrant ran smoke-01 and dev-01 to dev-06 (17-18 November) and
  read their values:
  - Norton concentrations within 2.7e-14 of the registrant's own dense solve;
  - ledgers within 5.8e-13;
  - as written, within 1.0e-5 at dt and 2.5e-6 at dt/2, with orders 2.00 to 2.01.
- **No tolerance is set from them.** Each is a stated error term's.
  - Each Norton development value lies inside its arm's derived tolerance, by 70 to 370 times.
  - The as-written development errors fall fourfold per halving. At that rate the dt/4 error is
    about a third of its F_W est.
- **The references.** Their values are not known to the registrant beyond the closed forms that the
  preprint itself implies: equation 2, Figure 5's 50/7 and the chain's golden-ratio limit.
- **What the references read holds no run's value.** The test checks this for the development
  values.
- **A smoke of the registered code paths, at a 20 s horizon.**
  - The run was `run.py ... --end 20` from this branch (`probes/smoke-registered-01`): every
    registered arm, the triple, the windowed Figure 5a at 10 G_eq with its record, and the table
    built from its output.
  - **A correction to eb1c2f00's message, which said every arm was flagged not steady.** Most arms
    are far from steady at 20 s, but not all.
    - Every cell starts at its unloaded value, so in a network without a probe the uniform mode
      has no amplitude.
    - What remains decays at least at K_dec (1 + 2g) in Figure 3b, and at K_dec (1 + 1.75 g) in
      Figure 5b.
    - So four arms were at or within a few times 1e-9 of their fixed points: Figure 3b and
      Figure 5b at 10 and 50 G_eq.
    - Two of them, `figure3-g50` and `figure5-lumped-g50`, passed the steady check.
    - For the as-written `aw-figure3-g10` and `aw-figure5-lumped-g10`, the smoke's table printed
      their dt/4 tolerance (3 est, 7.3e-7 for each) and their observed orders (2.013 and 2.011).
      Those are in effect the judged triple's values for these two arms.
  - **What was not seen.** No engine concentration was compared with any reference, and no
    tolerance is set from the smoke. Every other arm was far from its fixed point.
