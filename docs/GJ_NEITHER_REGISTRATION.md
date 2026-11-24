# GJ-N1: the "neither" threshold comparison (registration)

**Status: proposed for registration, 23 November 2026, for the lead.** Docs and validation only, with
no src change. Branch `gj-registrations` from main db54d0f5. It is to be tagged before any judged run.
The proposed tag is `gj-neither-registered-2026-11-23`.

**Two geometries, registered differently (D219):**
- **The 1D line is not blind.** Its threshold was already seen in `neither-02`, and these conditions
  were written after (§9).
- **The 2D field is a true pre-registration.** No 25 × 25 world has run past 16 s (§9).

**One question is open, for the lead: the field's compute (§8).** On today's engine the field takes
about 0.17 s a step, so its search needs about 400 CPU-hours. Its critical path is the bracket's
upper end, at about five days. The line needs about 8 CPU-hours.

**Sources.**
- The preprint, bioRxiv doi:[10.64898/2026.09.02.748840](https://doi.org/10.64898/2026.09.02.748840),
  v1: the EMT switch (Figure 2, Methods), the junctions and the search for the smallest normalizing
  diffusion constant (Tables 1-2). It prints the "neither" value only for its 3D field (Table 1,
  1.1e-15 m²/s).
- BITSEY at b2cb370 (gitlab.com/grodstein/bitsey). Its numbers are used under D208 and none of its
  code is copied. It gives the switch's constants (`cancer_GJ_sims/GRN_miRNA.py`) and the protocol
  (`cancer_GJ_sims/zombie.py`: `zombie_tumor_isolate`, `find_min_Kd_tumorFix`, `binSearch`,
  `set_corner_tumor`, `disconnected_sim`, `healthy_snapped_rows`).
- D219: the "neither" threshold comparison is approved as judged, under a registered protocol with
  code-blind references:
  - successful refinement and a predeclared convergence condition are part of the verdict, and the
    ratio alone is not the judge;
  - the historical log is named with the uncertainty about its producing revision;
  - a pinned BITSEY run is an additional reference.
- The development work: [GAP_JUNCTION_CANCER_REPLICATION.md](GAP_JUNCTION_CANCER_REPLICATION.md) §7.

**What is registered.** The tag holds these files, read byte for byte as tagged:
- this document, the authority;
- `validation/gap_junction_tissue/neither.py`, the driver that makes the judged runs. The field
  (`tissue("field")`), its criterion (`criterion`, `row_spreads`) and its first points
  (`first_points`) are new in this registration;
- `validation/gap_junction_tissue/neither_judge.py`, its arithmetic and the comparison's reader;
- `validation/gap_junction_tissue/neither_rule.json`, every number, as `neither_judge.py rule`
  writes it;
- `validation/gap_junction_tissue/references/spec/neither.json`, what the references read: the
  model, the geometries, the criterion, the search and the interface, with no run's or log's value
  (`neither_judge.py spec`);
- `validation/gap_junction_tissue/bitsey_run.py` and `bitsey_log.py`: the pinned BITSEY runner and
  the reader of BITSEY's logs;
- `tests/unit/test_gap_junction_neither_judge.py`: the field's geometry and criterion, the reader
  and every plant, on synthetic inputs (0.6 s, no world compiled).

**Engine models (AGENTS.md).**
- `resolved_pump_composite@1` over `resolved_pump_tissue@3`, in the species-only world of the
  secreted-species fixtures (ions at the bath's composition with zero permeability).
- `local_species_reactions@1`: the switch, in each cell.
- The passive-routes kind's `passive_neutral_permeation@1`: miR200 alone, on each junction, with
  P A = G_GJ. There are no routes at D = 0.
- `junction_voltage_relaxation@1` pinned open, the
  `resolved_capacitor_components_current_continuity@1` closure, and
  `imex_ars222_face_electromigration@1` with `capacitive_reduction_gauged_damped_newton@2`.

**The engine under test.** Each judged search is fresh, from a clean execution snapshot of the tag's
revision, at the tag's src (main db54d0f5). A src change before a run, such as a faster path for
the field, needs an amendment tagged before that run.

## 1. The claim

With the EMT switch in every cell and miR200 crossing junctions as a neutral species, the engine
finds the smallest junction diffusion constant D at which healthy tissue normalizes a corner tumor
within 20,000 s. It does so on BITSEY's 1 × 1 × 25 line and 1 × 25 × 25 field, by BITSEY's own
criterion, bracket and tolerance. Its threshold agrees with an independent integration of the same
equations, within the width of the two searches' brackets and the engine's step term.

**Why a neutral miRNA is BITSEY's model here.** In BITSEY's "no tricks" condition every cell has the
same voltage, so the miRNA's valence −1 drift vanishes and its junction flux is Fick's (§7.1 of the
replication note).

## 2. The model

These are all the equations the references need. The constants are in `neither_rule.json`
(`model`).
- **Species per cell**, in scaled units (one unit is 1 µM in the engine's world), with time in
  seconds: u (miR200, total), m (Zeb mRNA, total) and z (ZEB protein).
- **The switch.** BITSEY's GRN_miRNA.py at b2cb370, with Snail = 72 folded in and ITERATE = False,
  so the binding uses total miR200:
  - du/dt = 4.2 H(z; 100/9, 3, 0.1) − 0.05 u + (junction terms);
  - dm/dt = (55/24) H(z; 25/9, 2, 15) − 0.5 m;
  - dz/dt = (1/6) m Σ_{i=0..6} C(6,i) l_i X^i/(1 + X)^6 − 0.1 z, with X = u/40 and
    l = (1, 0.5, 0.2, 0.02, 0.02, 0.02, 0.02);
  - H(z; K, n, λ) = (1 + λ (z/K)^n)/(1 + (z/K)^n).
- **Junctions.** u only. A junction between cells a and b moves G (u_a − u_b) from a to b.
  - G = D × 4π r²/L_GJ, with r = 5 µm and L_GJ = 100 nm.
  - G/V_cell = 3D/(r L_GJ) = 6 × 10¹² D per second.
- **Seeds.**
  - Tumor cells: u = 1e-6, m = 100, z = 100.
  - Healthy cells: u = 100, m = 1e-6, z = 1e-6.
  - BITSEY seeds 0 where these are 1e-6, because the engine needs positive amounts.
- **The stages.**
  - Stage 1: one tumor cell and one healthy cell, uncoupled, for 500 s from the seeds, computed once.
  - Stage 2: every tumor cell starts at stage 1's tumor end state and every healthy cell at its
    healthy one. It runs coupled for 20,000 s, its clock starting at 0.

## 3. The geometries

| | The line | The field |
| --- | --- | --- |
| BITSEY's field | 1 × 1 × 25 | 1 × 25 × 25 |
| Cells | c0..c24 along z | c{y}_{z}, y and z in 0..24 (index 25y + z) |
| Tumor | z < 6 | y < 6 and z < 6: the 6 × 6 block at the corner (`set_corner_tumor(6)`) |
| Junctions | c_k to c_(k+1), 24 | one per pair one lattice step apart (`setup_GJ_3D(allow_diag=False)`), 1,200 |
| Field nodes | 26 | 626, within the field solver's 2,048 |
| A row (`healthy_snapped_rows`) | each cell alone | the 25 cells of one z |

## 4. The criterion, the bracket and the search

- **Normalized** (BITSEY's `healthy_snapped_rows`, line 519), at the end of stage 2:
  - every cell has u > m + 2;
  - every row's Zeb mRNA spread, max m − min m over its cells, is at most 2.
  - The spread is taken over the first two lattice axes for each last-axis index, so a row is the
    cells of one z. On the line the spread condition is empty.
- **The bracket:** D in [0, 1e-13] m²/s, BITSEY's.
  - Both ends are run. D = 0 must not normalize and D = 1e-13 must.
  - If either end fails, the geometry fails; the bracket is never widened.
- **Stopping:** narrow until hi ≤ 1.001 lo, as BITSEY's `binSearch` does, and report x2 = hi.
  - hi is the smallest normalizing D found.
  - lo is the largest D below hi that does not normalize.
- **Placement:** one point per CPU, in parallel.
  - The first points are the bracket's two ends and dyadic points 1e-13/2^k: k from 1 on the line,
    as `neither-02` ran it, and from 4 on the field.
  - k = 4 is the largest such point that runs at the base step. It keeps the field's first points
    off reduced steps (`first_points`).
  - Whenever a point finishes, its worker takes a new point inside the current bracket (`place`).
  - The placement changes which points run, not where the threshold is: under monotone outcomes,
    every converged bracket contains it.
- **The step.**
  - Per point: dt = 1/8 s, halved until dt × 2 × (neighbours) × G/V ≤ 0.04 (`neither.step`), with 2
    neighbours on the line and 4 on the field.
  - Stage 1 runs at the shape's finest coupled step: 1/64 s on the line, 1/128 s on the field.

## 5. The verdict

Each geometry is judged by three conditions:
- **R, refinement:** the search converged, every point ran (none refused by the engine), the
  outcomes are monotone in D, and both bracket ends are as required.
- **C, the convergence condition:** the final bracket's two ends, rerun at half their step, keep
  their outcomes.
  - The threshold at dt/2 then lies in the same bracket.
  - At the scheme's second order, the limit dt → 0 lies within w/3 of it, where w = hi − lo.
- **A, agreement:** Cells' interval [lo − w/3, hi + w/3] and the code-blind reference's bracket
  overlap. The reference's bracket must hold at a ten-fold tighter tolerance (§6).

**Verdicts per geometry:**
- **failed:** a point refused, a bracket end wrong, or A failing with R and C passed;
- **inconclusive:** the outcomes are not monotone, or C fails after its retry;
- **not assessable:** the references did not compute that geometry;
- **passed:** otherwise.

**Overall** (D308's precedence): any failed geometry makes the comparison failed; else any
inconclusive geometry makes it inconclusive; else any geometry not assessable makes it not
assessable; else it is passed.

**No ratio alone judges (D219).** The ratio of thresholds is reported.

**The retry.**
- If C fails, the whole search runs once more at half the step rule, with its own C at a quarter.
  If that C fails too, the geometry is inconclusive.
  - **The tagged driver cannot make it yet:** `neither.py`'s search has no step option.
  - A retry therefore needs a tagged amendment, before it runs, that adds that option (D308).
- A run that the harness stops (memory, runtime limit, machine fault) is rerun once from the same
  snapshot.
- An engine refusal is a result, never rerun.

**The planted failures**, shown by arithmetic through the reader and judge (the test file). A planted
field search would cost hundreds of CPU-hours.

| ID | What | Must |
| --- | --- | --- |
| P-A1 | a reference bracket 1% above Cells' interval | fail A |
| P-A2 | a reference bracket outside Cells' bracket but inside its w/3 | pass: the margin is the stated w/3 |
| P-R1 | a refused point | fail the geometry |
| P-R2 | non-monotone outcomes | make the geometry inconclusive |
| P-C1 | a half-step rerun that flips an end | make the geometry inconclusive |
| P-I1 | a reference bracket wider than 1.001 | be refused before any comparison |
| P-I2 | a reference whose ends flip at the tighter tolerance | be refused |
| P-I3 | a reference echoing a different constant (g_u = 4.0) | be refused |

## 6. The references

**The code-blind reference.** A separate agent integrates §2's equations on §3's geometries,
independently, from the preprint and `references/spec/neither.json` alone. It never sees Cells'
code, runs, the replication note, PROGRESS.md or this document's disclosures, nor BITSEY's code or
logs.
- It finds the threshold by §4's criterion, bracket and stopping rule.
- It checks its bracket's two ends again at a ten-fold tighter tolerance.
- It writes `validation/gap_junction_tissue/references/interface/neither.json`; the keys are in
  `neither_rule.json` (`interface`):
  - the model's constants and seeds, echoed as read;
  - stage 1's end states;
  - per geometry: the bracket, every point (D, outcome, epithelial count, least margin, largest
    row spread), the tighter check and the method.

**The reader** (`read_interface`) refuses:
- an echoed constant that differs by more than 1e-12 relative;
- a bracket wider than 1.001;
- outcomes that are not monotone;
- bracket ends other than required;
- ends that change at the tighter tolerance.

**BITSEY: reported with every verdict, never judged. This is proposed, for the lead's ruling
before the tag.** D219 calls a pinned run "an additional reference". This registration reports it
beside the verdict and does not judge by it, for the reason given below. If the lead rules that it
is judged, the band must be set here before the tag. There are two sources.
- **The historical logs**, saved at b2cb370 in `cancer_GJ_sims/results_miRNA/`. Their sha256 is in
  the rule.
  - `tumor_isolate_1D_V1M`: bracket [7.171630859375e-15, 7.177734375e-15] at full precision.
  - `tumor_isolate_2D_V1M`: bracket [1.8859863281250003e-15, 1.8875122070312503e-15].
- **Their producing revision is uncertain.**
  - Both print their result as "Final NR=0: ...", the format of 04225e4 (20 May 2026). b2cb370 prints
    "0. Final underexp=0.3: ...".
  - The 1D log's search is titled "lowest Kd that fixes a 1-spot", which no committed revision from
    04225e4 on prints.
  - Between 04225e4 and b2cb370, `GRN_miRNA.py` and `sim.py` differ only in comments and one
    equivalent expression. `zombie.py`'s protocol code changed.
- **The pinned run**, BITSEY unmodified at b2cb370, out of process, in
  `/mnt/workspaces/Cells/venv-bitsey`, by `bitsey_run.py`.
  - Only argv, the environment and stdin are chosen.
  - The command is `zombie.py zombie_tumor_isolate 1 1 25 0 0 1` for the line and
    `... 1 25 25 0 0 1` for the field. The field's run stops once its first search, the "no
    tricks" one, has printed its result.
  - Its log is read by `bitsey_log.py`.
- **The licence:** none at b2cb370 or at the newest head (7e4fb45d, 22 November 2026). Seven tracked
  files point to a LICENSE that does not exist. The user's D208 was ruled knowing this.
- **What is reported** for each source:
  - its bracket at full precision, from the `Now doing Kd=` lines;
  - whether it overlaps Cells' interval;
  - the ratio of the thresholds;
  - the outcomes at the points both evaluated.
- **Why not judged.** BITSEY integrates by explicit adaptive Euler, with each step's change capped
  at 0.1%. That scheme's effect on a threshold has no a priori bound. The code-blind reference
  measures it, and if A passes, agreement with BITSEY within that measured deviation follows.

## 7. How the judged runs are made and judged

1. **The line**, from a clean execution snapshot of the tag, one point per CPU:
   `python -B validation/gap_junction_tissue/neither.py OUT --cpus LIST --shape line`.
2. **The field**, once its compute is assigned (§8): the same with `--shape field`.
3. **The judgement**, once the references' tag exists:
   `python -m validation.gap_junction_tissue.neither_judge judge --line OUT_LINE [--field OUT_FIELD] --interface DIR --bitsey-line LOGS --bitsey-field LOGS --out verdict.json`.

## 8. The compute budget (D219), measured

**The cost probe** `/mnt/workspaces/Cells/gap-junction-20261123/probes/field-cost-01` ran on one CPU
on today's engine:
- **The field:** 0.16-0.19 s a step, with or without routes. It used 32- and 16-step windows (64
  exceeds the runner's 2 GB trace budget) and 1.3 GB. The driver's field windows are 32 steps
  (`FIELD_WINDOW_STEPS`).
- **The line:** 3.4 ms a step.
- **The first window's compile:** 72-77 s.

**The line:** about as `neither-02`, 37 points and about 8 CPU-hours. The upper end's 1.28 million
steps, 72 minutes, are the critical path. On four light CPUs it takes about 2-3 hours.

**The field:**
- a point at the base step (1/8 s, 160,000 steps) takes 7-8.5 hours;
- the bracket's upper end (1/128 s, 2.56 million steps) takes 4.7-5.6 days;
- the whole search with its convergence check takes about 350-410 CPU-hours.

This does not fit the light CPUs. **The field runs when the lead assigns compute,** or after an
amendment tagged before it runs. Options for the lead:
- **(i) As registered:** the critical path is about five days.
- **(ii) An amendment that drops the upper end's run.** The bracket's top would then be its largest
  normalizing ladder point. This saves about 120 CPU-hours and the five days, at the cost of one
  monotonicity check that BITSEY's protocol runs.
- **(iii) A faster engine path for this world**, from the numerics owner. The per-step cost does not
  come from the routes.

## 9. What is not blind

**The line:**
- The registrant's development search `neither-02` (from 1f4c740a, 17 November) converged at
  x2 = 7.177734375e-15 m²/s, bracket [7.176208496e-15, 7.177734375e-15], over 37 points. Its
  half-step check passed.
- `neither-01`, `picks-01`/`-02`, `dense-01` and `ladder-01` ran the line at many D values.
- BITSEY's 1D log and its whole bisection were read.
- These conditions were written after. The judged run repeats the search fresh from the tag.

**The field.** No 25 × 25 world has run past 16 s. Seen before this registration:
- BITSEY's whole 2D bisection in its saved log, bracket 1.886e-15 to 1.888e-15;
- `sheet-01`, a different world (9 × 9, a central 3 × 3 tumor, 2,000 s), whose threshold lay between
  9.0e-16 and 1.8e-15;
- `field-parse-01`, a parse with no integration;
- the cost probe `field-cost-01`: D = 1e-13 for 1.5 s and D = 0 for 16 s. Every tumor cell was still
  mesenchymal and every healthy cell epithelial (589 of 625), which cannot show a threshold.

**Smokes of the registered code paths**, from this branch (`probes/smoke-registered-01`), at
horizons too short to show anything:
- one field point, D = 1e-13 for 0.25 s;
- a field search and a line search at 0.25 s and 2 s, which stop at their upper ends because nothing
  normalizes that soon.

They show the field's windows (32 steps), the search's stage 1 and its stop rule.

**The pinned BITSEY field run** started after this registration's first commit (b3f20a26). Its
result is reported, never judged.
- Before the final commit, its first five outcomes were seen: D = 0 not normalized, and 1e-13,
  5e-14, 2.5e-14 and 1.25e-14 normalized, as in the historical log.
- Nothing in this registration was set from them.

## Amendment 1: the field's engine and field solver (draft, 23 November 2026, for the lead)

**Status.** A draft for the lead's tag. It is written before any field point has run, and it changes
nothing for the line. The user chose a faster path for the field (D317): bit-identical fixes plus a
sparse node-space solve, the latter as FR-17's first stage. The registration's engine paragraph
requires an amendment, tagged before the run, for any src change before a run. This is that
amendment.

**1. The engine under test, for the field.**
- **The run's source:** a clean execution snapshot of main at or after the landing of the sparse
  solver's qualification, and so at or after d6d42b46 (tag gj-fieldpath-merged-2026-11-23).
- **d6d42b46's two fixes are bitwise identical under D148, so they change no registered number.**
  - local_species_reactions@1 evaluates its Hill factors at the declared slots only, one branch
    each.
  - surface_pump_v3.crossing_junctions halves its union-find's paths.
  - The evidence:
    - the D148 guard: scalar runs with device checks, windowed runs and vector-window and batch
      cohorts are physically identical on the reactions operator's crossrev worlds and on GJ-N1's
      switch worlds, among them the 25 × 25 field at D = 0 and at 1e-13;
    - G1, 113 of 113 identical;
    - FR's bitwise set;
    - crossrev changed only in program text and one new binding
      (`/mnt/workspaces/Cells/gj-fieldpath-20261123/`).

**2. The field's field solver.**
- **The field runs with** `execution.field_solver = sparse_capacitive_reduction_gauged_damped_newton@1`
  (docs/FIELD_SOLVER_INTERFACE_DESIGN.md §8), once that ID is qualified as §8.5 lists. Today it runs
  with `capacitive_reduction_gauged_damped_newton@2`.
- **The driver:** neither.py's field worlds (`coupled_world` and stage 1's `uncoupled_world` for
  `shape="field"`) set that ID. The line keeps @2, as it ran.
- **The code is tagged with this amendment.** The change lands with the solver, as a reader that
  exists at its tag (D308).

**3. What must hold before any field point runs.**
- The solver is qualified against @2 (§8.5) on GJ-N1's field worlds, among others: a few windows at
  D = 0 and at 1e-13, with state fields within the ledger tolerances.
- Its bitwise status on these diagonal reductions is measured and reported.
  - If it is bitwise identical to @2 there, the field's numbers are those @2 would give, by
    construction.
  - If it is not, the agreement found is recorded, and the verdict's convergence condition C (the
    final bracket's ends at half step) still bounds the threshold's sensitivity to the integration.
- The tier gate, G1 and FR's set pass at the solver's landing.

**4. Unchanged:** the model, the geometry, the criterion, the bracket, the search and its tolerance,
the step rule (dt × rate ≤ 0.04), the windows (32 steps), stage 1, the verdict (R, C, A), the
references' specification, and BITSEY's role (reported, never judged).

**5. The cost, re-estimated from measured steps** (one CPU, process CPU time, from
`/mnt/workspaces/Cells/gap-junction-20261123/probes/field-profile-01/`):
- **The windowed field step today, after d6d42b46:** 0.075 s with routes and 0.071 s at D = 0, against
  0.142 s and 0.114 s before. The search would take about 160 CPU-hours, with its upper end at about
  2.2 days.
- **With the sparse solve** (about 33 ms less a step): about 42-45 ms a step. The search would take
  about 90 CPU-hours, with its upper end (2.56 million steps) at about 30 h.
- **Where it runs:** a gate lane under its lock, one point per CPU, as the lead assigns. The
  critical path is the upper end.

**6. The line's engine, for the record.**
- **The judged line search ran from main 23593267** (`/mnt/workspaces/Cells/gap-junction-20261123/
  judged/snapshot-23593267`), as the lead directed: "a clean frozen snapshot of main at or after
  130cd928".
- **Its src differs from the tag's** (db54d0f5) in `src/cells/models/assembly_lineages_v2/
  rate_equations.py` alone. The GJ worlds do not run that model
  (`judged/snapshot-diff-from-tag.txt`).
- **It started at 19:19 UTC on 23 November,** before this amendment, under no src change that GJ-N1's
  worlds run.

## Amendment 2: the field runs on CPUs (draft, 24 November 2026, for the lead)

**Status.** A draft for the lead's tag, written before any field point has run. It changes nothing
for the line. The user's decision of D330 was to qualify the device row checks on the GPU and then
run the field's longest points on the L4, with a tagged amendment fixing in advance which points run
where. That qualification closed as failed (D336), so this amendment keeps every field point on CPUs.

**1. Where the field runs.**
- **No field point runs on a GPU.** neither.py's field definitions declare the CPU backend
  (`execution.backend = "cpu"`).
- **On one CPU outside the gate lanes, from launch:** stage 1, the bracket's upper end (D = 1e-13 at
  h = 1/128 s, the critical path) and its half-step rerun if C needs it. The CPU is assigned by the
  lead (CPU 13, the user's approval, 24 November), with its hyperthread sibling (CPU 29) held idle,
  and the run record names it (search.json's `upper_cpu`, each point's `cpus`).
- **On a gate lane, under its lock, one point per CPU, as amendment 1 places them:** the base-step
  points, the bisection's rounds and C's half-step reruns of the points that ran there. The search
  takes the lane's lock only before its first lane point, and releases it once no lane point runs or
  waits, so it never holds the lane while it waits for the upper end alone.
- **Not before a set time:** the lane's first point, and so its lock request, waits until the
  `--lane-after` time (UTC). flock is not fair, and a lane taken between daytime gates would be held
  for about 10 h while gates and other batches queue. The lead launches the search soon after this
  amendment's tag, so the upper end's critical path starts at once, with `--lane-after` set to
  20:00 UTC, so the bisection runs overnight. search.json records the value.
- **The driver,** tagged with this amendment (D308): `--upper-cpu N` runs stage 1, the upper end and
  its half-step rerun in a pool of their own pinned to CPU N, started at launch; `--lane-lock PATH`
  takes and releases the lane's lock as above; `--lane-after TIME` holds the lane's first point until
  that UTC time. search.json records all three. Every record keeps its format; the upper end's is
  appended to points.jsonl as any point's. tests/unit/test_gap_junction_neither_judge.py checks the
  placement, the time and the lock with stand-in points (no world compiled, 0.5 s), and smokes on
  the line (2 s, not blind) put the upper end and the lane points on their CPUs, held the lane until
  its time, and released the lock.
- **Placement changes time, not results.** On the CPU a second process repeats every window by
  bytes (D330's CPU baseline: 8 of 8 windows, and 37 of 37 arrays of the final state), so a point's
  record does not depend on the CPU or the lane it ran on.

**2. The pairs the judge compares stay on one device.**
- C's pairs (each final bracket end at h and at h/2), the final bracket's two ends and every point
  that R reads run on CPUs, from one execution snapshot.
- XLA's CPU backend is deterministic, so a rerun of a point reproduces its record exactly. No tie
  rule is needed, and R is read on one device.

**3. The cost, from measured steps** (the sparse field solver on the production path, with device
row checks, on one CPU; D330):
- **Per step:** 32.0 ms at D = 1e-13 and 28.3 ms at D = 0 on a core whose sibling is idle; about
  1.2 to 1.6 times that when both siblings run, as on a gate lane run one point per CPU.
- **The upper end** (2.56 million steps): about 23 h on its whole core (CPU 13), against 27 to 36 h
  on a shared one. It is the critical path. Its half-step rerun (5.12 million steps, about 45 h there)
  runs only if the upper end ends as a final bracket end.
- **A base-step point** (1/8 s, 160,000 steps): 1.3 to 2.3 h; its half-step rerun 2.8 to 4.6 h.
- **The whole search:** about 70 to 115 CPU thread-hours (amendment 1 estimated about 90).

**4. D330, for the reader of the verdict.**
- On the L4, with XLA's deterministic ops, host and device mode agreed by bytes (G1), and two new
  processes reproduced every window (G6).
- G2 failed: in the first window the device read the global material ledger at 0.715 of its bound
  and the host 0.202, a spread of 0.514 against the declared bound of 0.291 and its cap of 0.4.
- The engine refuses GPU device mode on the scalar path (`row_checks.admit`, D187), and from D336's
  landing the vector path refuses the composite on a GPU (`vector_windows.refuse_unqualified_gpu`).
  The record: D336 and docs/WINDOW_DEVICE_CHECKS_DESIGN.md §10.

**5. Unchanged:** the model, the geometry, the criterion, the bracket, the search and its tolerance,
the step rule (dt × rate ≤ 0.04), the windows (32 steps), stage 1, the verdict (R, C, A), the
references' specification, BITSEY's role, and amendment 1.
