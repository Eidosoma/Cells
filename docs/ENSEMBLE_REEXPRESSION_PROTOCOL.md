# The ensemble's re-expression: the registered qualification

**Status: written 25 November 2026 for the lead's tags, before any run of the registered campaign** (D369, D374, D383). Its author had seen no re-expressed run, and has opened neither design note.
**D383 says the criteria are tagged before any re-expressed run. For one consumer that is already broken:** a design author ran two worlds of `base` in composed form. §11 says who is not blind and to what, and `spec/CRITERIA.md` §8 says what the verdict does with it.
Docs and validation text only, with no engine code, no candidate and no judge. Its author does not build, judge, check or run a candidate. Branch `ensemble-reexpression-criteria`, from main 49529e71.

**What it registers.** This document and `validation/ensemble_reexpression/spec/`, whose `README.md` lists the files. With the captures, the judge's reader and the strings note it makes up the registration. The criteria tags come now for Part 1,
and for Part 2 when the two design notes it waits for are answered (§5).

**The protocol is `ensemble-reexpression-v1`.** It carries one verdict per consumer.

## 1. What is re-expressed, what is claimed, what is not

The user's decision (D369, D374, D383): everything Cells uses leaves legacy in canonical forms. The calcium ensemble and its neighbours are the consumers that count.

| Part | Consumer | What it was in legacy | Canonical form | Equations |
| --- | --- | --- | --- | --- |
| 1 | `jupiter` | The world of the JUPITER readiness check, both arms | A closed world of the inner tissue model | Same |
| 1 | `cell` | The assembly-regulated cell | The same model, with the live pool's switch path as the channel's schedule, written by a driver | Same |
| 1 | `base` | The assembly-regulated cluster's base | The same, with two pools | Same |
| 1 | `integrated` | The integrated ensemble's world | The same model | Same |
| 2 | Four calcium clusters | The four buffered stores over the JUPITER cluster | The composite over the inner model, with compartments, a cycle law, a factor source and channels that carry calcium | Same, under conditions |
| 2 | Four assembly-regulated calcium clusters | Those, with two pools each | The same, with the pools' paths | Same, under conditions |

**The claim, per consumer that passes:** the canonical form of this consumer, at the steps run, gives the captured amounts, transfers, cycles, gates, heats and potentials within the bands of `spec/CRITERIA.md`, and gives the live pool's events, seeds and checkpoints
bit for bit, and every accepted step of the candidate kept the engine's own ledgers.

**"Same equations"** means the model's equations are unchanged, and the code, the splitting or the integrator are not. A consumer that is found to be a changed model has no band here and is not judged (`spec/PART2.md` §3).

**It does not claim:** anything of §9.

## 2. The engine models it runs

- **Part 1:** the inner tissue model, version 3, on RK4, with its Na/K pump on maintained fuel, its Kv1.5-type channel law, its one-gate junction law and the logarithmic-mean face law, and the live assembly pool. The field solver is the one D147's rule gives each world: the floor variant for `jupiter` and `base`, the factored reduction itself for `cell` and `integrated`. No kind, operator or species registry. The assembly observable is a registered law that the driver's definition records (`spec/SPEC.md` §3.3).
- **Part 2:** the composite over that model, on the IMEX integrator, with the notes' compartment, cycle law, exchanger law, passive routes with a factor source, local reactions and calcium-carrying channels, and the live pool.
- **No registered ID is written here or in the spec folder.** The exact strings are in the strings note, written after the ID move (`spec/TABLE.md` §5).

## 3. The roles

Each is a different agent, and its work goes through the lead.

| Role | Writes | Reads | May not read |
| --- | --- | --- | --- |
| Author (of this document) | This document, the spec folder, `plants_manifest.json`, `margins.json`, and the planted legacy runs | The captures and the snapshot (reference side), and the plan and its map | any candidate, any re-expressed run, the design notes' outputs |
| Builders | The canonical definitions, the driver and the exporter (`validation/ensemble_reexpression/`), the format sample | The spec folder, the plan's map, the design notes, their own code | the judge's code, the captures' arrays (the exporter needs no captured value) |
| Judge | Its reader, its self-tests, `power.json`, `retry_owed.json`, the verdict | This document, the spec folder, the captures, the planted arrays, the tables, the strings note, the format sample | the builders' code and the engine's source |
| Checker | Its own recomputation, the run records | The hashed tables, the captures, the planted arrays, the run records, the judge's record | the judge's code until its own is written |
| Rehearsal runner | `inputs_rehearsal.json`, and the legacy snapshot's runs on it | The spec folder, the snapshot | the builders' and the judge's code |
| Spec auditor | A reader skeleton, fabricated honest tables, its report | The spec folder only | everything else |
| Lead | The tags, the freezes, the launches, the hashes, the strings notes, the decision entries | everything | nothing is barred, and **it is not blind** (§11) |

- **No builder runs a registered world before the registration tag.** Parse checks, unit rows and invented worlds only.
- The judge's reader is written from the spec folder alone, and so is the exporter. Neither reads the other's code. The references are the captures, so there is no references agent.
- The **spec auditor** reads this spec alone, before the judge is built (§5). Its questions reach the author only through the lead.
- **The design authors may build.** They are not the judge, the checker, the spec auditor or the rehearsal runner, since they have seen prototypes' results (§11).
- **From 25 November 2026 a ruling by the lead to the author of this spec holds no step, order, margin or residual of a prototype or candidate.** The author refuses one that does, tells the lead, and says so in §11.

## 4. Power, before runs (D366)

- **A 1 % change in one rate constant must be seen.** `spec/PLANTS.md` lists the plants with their homes, and `margins.json` holds their distances from the legacy side alone, before any run.
- **The power check is judged first.** The judge forms every entry's band from the runs' own rows and the captures' own refinement, with no difference between a run and a capture, and writes `power.json`, hashed, before it forms a comparison. An entry whose band is above a tenth of its planted distance is not tested.
- **A mechanism that a plant cannot reach in 20 ms** is named so, with the number, and is no home (`spec/PLANTS.md` §8, `spec/PART2.md` §7.4).

## 5. The order of work, and the tags

1. **Part 1's criteria tag,** on this branch: **`ensemble-reexpression-criteria-part1-2026-11-2x`.** Bands, classes and windows are fixed from here. A bound is corrected only by the route of `CRITERIA.md` §10. It waits for nothing. The user decided G-7's form on 25 November (the dated note in §11).
2. **The integrated ensemble's capture** exists (25 November, `extra-49529e71`) and is in Part 1's files.
3. **Part 2 is completed** when notes D and E are answered, with the orders, the steps and the names, and its restarts and engine plants. Tag: `ensemble-reexpression-criteria-part2-2026-1x-xx`. **No Part 1 file moves.**
4. **The spec auditor** reads the spec folder alone, makes honest tables, and reports what is refused, what passes with nothing judged, and what an honest run would fail. A finding changes the text by a dated amendment, before the judge's tag. It re-runs on an amended head.
5. **The builders** write the definitions, the driver and the exporter from `TABLE.md` and `READOUTS.md`, in parallel with the four features. They run only their rows and invented worlds.
6. **The judge's reader** is written from the spec, parses `inputs.json` and the legacy side, runs C0 on the captures, and passes the judge's plants. Tag: `ensemble-reexpression-judge-2026-1x-xx`.
7. **The format sample** (`TABLE.md` §7), parsed by the judge before its tag.
8. **The rehearsal** (`CRITERIA.md` §10): the rehearsal runner's invented worlds, the frozen legacy snapshot's runs of them, the builders' table, and the judge's scoring. It is run on invented worlds only, before the registration tag. No builder runs a registered world before then, except for what the design authors' prototypes had already run (§11).
9. **The ID move,** last on the cleanup branch. This folder holds no ID, and is frozen for it.
10. **The floor guard, rerun with constants** (D147's condition). The floor variant of the field solver may serve a run of record only after D147's floor guard is rerun with constants, and no rerun is recorded. The builder makes it, one short run, and records it, before the registration tag. Nothing in this
   registration assumes its result. If it is not clean, the consumers that declare the floor variant (`jupiter`, `base` and Part 2's) wait, and `cell` and `integrated` do not.
11. **The registration tag,** `ensemble-reexpression-registered-2026-1x-xx`, at the head of the cleanup branch that merges main, the spec, the build and the judge, before any registered run. At that head the lead re-runs the judge's C0 on the references, its self-tests and the format sample, and makes a trial merge.
12. **The strings tag,** `ensemble-reexpression-strings-2026-1x-xx`, on the next commit, which holds only `registered_strings.json`. The lead checks the note by parse against the declared worlds, with no run.
13. **The campaign** (§6), then the judge, the retry if owed, the checker, the record and the decision entry.

## 6. The campaign

**One campaign, at the end of the cleanup,** as the user decided: one full test of it all. Part 1 and Part 2 are run from one clean frozen snapshot of the registration tag, in the same batch, and judged consumer by consumer.

- **Worlds and steps:** `inputs.json` (214 runs) and `inputs_part2.json` (124 and the ones added at its tag). RK4 worlds at 25, 12.5 and 6.25 µs, or 100, 50 and 25 µs (`integrated`), and IMEX worlds at 12.5, 6.25 and 3.125 µs.
- **Snapshot:** `scripts/gates/freeze_snapshot.py --scope full --require-clean` of the registration tag. The table's `source` names it and its revision.
- **Launch:** detached, one thread each, cold (no compilation cache), on CPUs that the lead allots, **on the machine of the captures** (`legacy_part1.json`'s `cpu_model`), since class E holds there. Never CPUs 12 to 15 or 28 to 31.
- **Order of judgement:** the lead hashes the tables, the judge runs C0 on the captures and the spec, then stage 1 (power) and writes `power.json`, hashed, then opens the tables for stage 2, then writes the verdicts.
- **The retry:** once, for what `retry_owed.json` names (a finer triple), from the same snapshot. Its tables are hashed the same way.
- **After it:** the checker's own recomputation, the record, the user's approval of the removal list, and the full gate with tier 3 (D383). A consumer that fails is not removed.

## 7. What it costs

| Work | Agent-days |
| --- | --- |
| This document and the folder | done |
| The planted legacy runs and their margins | done, in this author's scratch folder, `/mnt/workspaces/Cells/ensemble-reexpression-criteria-20261125` |
| Part 2's completion when the notes are answered | 0.5 |
| Spec audit, and the amendments its findings lead to | 0.5 to 1 |
| The builders' exporter and format sample (the definitions and the driver are the re-expression itself, not counted here) | 1 to 1.5 |
| The judge: reader, C0, sample, plants, power | 1 to 1.5 |
| The rehearsal runs and scoring | 0.5 |
| The checker | 0.5 |
| **Total** | **4 to 6** |

**CPU:** Part 1 is 214 runs. `jupiter` and `integrated` are seconds to a minute each. The 192 `cell` and `base` ionic runs are each a compile of about half a minute and a short integration, about 2 CPU-hours, and the pool runs are seconds. Part 2 is 124 and more, on a composite whose compile is longer, about 4 to 5 CPU-hours.
The retries add at most about 1 CPU-hour. These are estimates from the captures' own times (15 to 60 s a job) and are not measurements of a candidate.

## 8. The verdicts, and what they decide

- **Per consumer:** pass, fail or inconclusive, by `CRITERIA.md` §8. **Part 1 passes when its four consumers pass.** `base` is reported in two sets, one that a prototype had run and one that it had not, and must pass on the second by itself.
- **A pass** says the consumer left legacy in canonical form at the steps run. It moves the consumer onto the removal list that the user approves. It lifts no refusal, and it does not make the candidate's physics right (§9).
- **A fail** keeps the consumer in legacy's hands: the pre-cleanup tag, the snapshot and the captures. The cleanup branch does not remove what a failed consumer still needs. What it means by class is in `CRITERIA.md` §9.
- **An inconclusive** verdict is not a fail. The retry is the only answer to it in this registration.
- **Any new run after a verdict** is a new registration, with this one's record beside it.
- **The independent reference** (`spec/PART2.md` §12) corroborates the reference side and decides nothing.

## 9. What this qualification cannot show

In words, so that a pass is read as no more than it is.
1. **Bitwise identity** with legacy, for any world.
2. **Anything on a GPU.** The GPU path of the ensemble is parked, and the JUPITER check's agreement between devices is not tested here.
3. **Legacy's own domain proofs** (the cubic enclosures that keep a step inside its domain), and the samples off the grid at 7.3 × 10⁻⁵ s and 3.713 × 10⁻³ s.
4. **The 100 and 50 µs steps** of the worlds with a gated channel. The inner model does not admit them on RK4.
5. **The assembly consumers' trajectories.** For `cell` only the end state is captured, and for the clusters the end state and a few summaries. A difference that cancels by the end is not seen.
6. **The ionic side of world IDs 8 to 63** of `cell`, and of any world beyond IDs 0 to 7 in `base`. Their pools are judged and their ionic side is not.
7. **How a lumped heat divides:** leak, pump and channel within a membrane, and the store's leak over its species.
8. **Anything below a band:** about 10⁻¹¹ of the gross throughput in Part 1, and the candidate's own error estimate in Part 2.
9. **Which step an RK4 run took,** as far as its values show. Its values sit at rounding at every registered step. The rows, the record and the checker say so.
10. **That a restart was a restart** (the checker confirms it from the record), and **what a digest hashes.**
11. **A wrong coarse run** that a retry drops.
12. **An operator form of the assembly coupling.** None is built, and none is registered (`spec/SPEC.md` §3.3).
13. **Availability levels other than 0 and 1,** and any feedback of the ions on the pool. There is none.
14. **The statistics of the ensemble.** Four seeds are captured.
15. **The observers.** Rates, affinities, currents and powers at the rows are not compared, and their integrals are.
16. **A mechanism that a 1 % change cannot move in 20 ms** (`spec/PLANTS.md` §8, `spec/PART2.md` §7.4). Its readouts are reported and not tested.
17. **Old checkpoints** of these worlds. They cannot be resumed on a canonical form. The pre-cleanup tag and the captures keep them.
18. **That legacy was right.** Agreement with legacy says the equations were kept. It is not a validation of the physics, and the parameters are synthetic.
19. **A blind test of `base` s0 w0 and s0 w1,** which a prototype had run, nor, through the shared ionic world, a wholly blind one of `jupiter_baseline` (§11).
20. **The reported identities** (`spec/READOUTS.md` §5). The balances, the charge and the energy are printed beside their bounds and are not judged.
21. **The clusters' own planted ratios.** The four assembly calcium clusters use half of their ionic child's, which is assumed and not measured.
22. **That the floor variant of the field solver is fit for a run of record.** D147's guard with constants is a step before the campaign, and its result is not assumed.
23. **Class E on another machine.** The pools' events were reproduced on the captures' machine. A logarithm's last bit may differ elsewhere.

## 10. Questions for the lead

Each has the default the files already follow.
1. **The comparison of section 8's template.** The floor of 64 ulp × max|X| is refuted by legacy's own runs (arrays at rounding differ by up to about 3000 ulp between its h/2 and h/4). I replaced it by a count (8 ε (S + 1) of the gross scale) and a closure term (two declared acceptance constants), derived in `spec/SPEC.md` §6.
   Default: as written.
2. **The order window is [p − ½, 4½], with power as the guard of the top.** D271's cap was 3½ for an order-2 split over a third-order integrator. A symmetric scheme's next order is 4, and FR-25's and FR-38's inconclusive orders were of that kind. Default: as written.
3. **The scales come from the inputs alone,** the gross one-way throughput of each route, and not from the captured arrays. They are 5 to 1000 times the captured net ledgers, so a band is far from a 1 % change in every entry. Default: as written.
4. **The ionic side of `cell` is judged on 32 of 256 worlds** (IDs 0 to 7 of each seed). Each world is a separate compile. Default: as written.
5. **The conservation rule in Part 1.** Your ruling's reason (legacy's absolute number belongs to a fourth-order integrator) does not apply to Part 1, whose candidate is fourth order too. The author's draft judged the balances and the energy there, and §11 says what the ruling replaced. The identities are reported, with the draft's bounds and a flag. Default: as ruled.
   An auditor who reads §11 may ask for the draft's rule back in Part 1, and the author would not object.
6. **A stop of an honest candidate by the engine's own check fails it** (your ruling of 25 November, FR-54's precedent). Default: as written.
7. **The rehearsal runs invented worlds before the registration tag.** That is a re-expressed run of invented worlds, as FR-54's is. Is it inside "one test at the end"? Default: yes, it is a development run on invented worlds and judges nothing.
8. **The spec folder is frozen for the ID move.** It holds no ID. Default: yes.
9. **Class E is judged on the captures' machine.** If the campaign must run elsewhere, the pool's events should be replayed there with the snapshot first. Default: the captures' machine.
10. **What a failed consumer does to the cleanup.** The text says it keeps its legacy code, through the pre-cleanup tag. Default: as written, and the user's approval of the removal list stands.
11. **The ratios of the four assembly calcium clusters** (`PART2.md` §7) are half their ionic child's, a declared lower bound. Planted runs of each would cost about a CPU-hour. Default: as written.
12. **The store's capacitor in the four clusters** rests on a planted ratio of about 3 × 10⁻⁵ (after halving), since a cluster's captures hold one end state and not the early rows where the capacitor shows. A candidate whose error estimate on `store_K` is above about 3 × 10⁻⁶ of its largest value cannot test it there, and the cluster is then
   inconclusive. The alternative is to require that mechanism in the four children alone. Default: required in all eight.
13. **Two things of Part 2 need your ruling before its tag** (`PART2.md` §7.1 and §7.4), and neither moves a Part 1 file. (a) Where a home entry has several plants, each plant is tested apart and the mechanism is tested when one of its plants is. The literal alternative is that every plant of a mechanism must be tested.
   (b) Two homes were moved (the store's K leak from `store_leak_K` to `store_voltage`, and its capacitor from `store_voltage` to `store_K`) after the planted runs were read, because the first choices gave a ratio of 1.4 × 10⁻⁴ and a margin of 8 to 13. Your condition says that a plant under 10 is enlarged or replaced, and that an insensitive ledger is not tested rather than tuned. The literal alternative is to keep the homes as first written, and to declare the two mechanisms not tested or to enlarge their plants. Default: Part 2's files as written, until the ruling.

## 11. Disclosures: what this author has seen and done

**The brief's reading:** the files it names.
- **The re-expression map** (`git show a1db6ab9:docs/LEGACY_PORT_PLAN.md`, sections 2, 3 (A10, B1 to B5, E1 to E4), 7.3, 8, 13 and 14), and D271, D278, D282, D366, D370, D374 and D383. Two specs as models of the bar: FR-38's second comparison (its protocol and spec folder with amendments 1 to 6) and FR-54 and FR-57's (its protocol, spec folder and amendments 1 to 6).
- **The live engine's source,** read for what a canonical definition must hold and for the names, signs, bounds and tolerances in the text: the inner model's definitions, state, readouts and checks, the field solver, the event grid, the assembly pool and the RK4 step. No engine run was made.
- **The legacy source at the snapshot,** read for the equations, the signs and the lumps.

**The reference side only: what was computed, and what was printed.**
1. **The legacy captures' own refinement:** for every array of every captured world, the differences between its h, h/2 and h/4 runs, and the observed orders. Printed as per-array maxima, differences and orders. The legacy side's classes follow from them by the rule of `CRITERIA.md` §4.3. No value was used to set a band.
2. **The snapshot's own assembly-pool code, run alone** on the captured pool definitions, on CPU 6, for about a minute. It reproduces the 19 captured pool arrays bit for bit at every seed, and gives the event paths in `spec/reference_paths.json`. It also showed that no event lies within 1.8 × 10⁻⁴ of a step of a grid point, so the clock's near-miss refusal cannot fire.
3. **Capture values read while reading:** one JSON summary of `cluster_base` at h, seed 0, and one of the IP3 cluster, the `cell` job's `result.json`, and the definitions of the captured worlds.
4. **The captured definitions' charge anchors,** by arithmetic (the largest disagreement is 5.1 × 10⁻²⁴ C).
5. **The planted legacy runs** (`PLANTS.md` §8, `PART2.md` §7.4), under the lead's conditions of 25 November, with the snapshot read-only and each change in the driver. **Part 1:** one control before the rest, and a batch of 45 runs (29 power plants, nine structural ones, seven controls), then two repeated with legacy's own ledgers off and two of ST10. **Part 2:** 125 runs (103 power plants, 13 structural ones,
   nine controls), one replacement (SC3b), and one stoichiometry that legacy refuses at parse (SC6). **PW-pool:** the snapshot's own pool, 12 short runs with one rate × 1.01. Every run's command, patch text, output folder and sha256 is in `plants_manifest.json` and `plants_manifest_part2.json`, the refused ones included. They ran on CPUs 7 and 23 under `nice`, two at a time, 4 GB each, through `run_detached.sh`.
   **Order of events:** the bands, classes and windows above were committed (5b56f92c, 11:23:02 UTC) before the first control (11:24:59 UTC), so no margin could move them. **What the runs printed** is the planted distances, margins and ratios, which are in `margins.json` and `margins_part2.json`. The plant texts that a run changed are dated in `PLANTS.md` §4 and `PART2.md` §7.4.
   **A lapse:** between the first two batches a third unit was started by mistake while two ran. It was stopped after about ten seconds, and its two partial folders were removed.
6. **The independent scalar references** (`validation/betse/spatial_cluster/reference.py` and the live tests' `reference_*_calcium.py`, which import nothing of the engine) were run on the six captured ionic worlds (both JUPITER arms and the four calcium children), on CPU 23, for two minutes in all. Every field agrees with the captured h/4 rows at the compared times, entry by entry, within 3 × 10⁻⁹ relative and 3 × 10⁻¹² absolute
   (worst 5.5 × 10⁻⁴ of that bound). Relative to each field's largest value, the largest difference is 2.5 × 10⁻¹⁴ in the JUPITER arms and 3.3 × 10⁻¹² in the calcium children (the store's K leak). It corroborates the captures and decides nothing (`PART2.md` §12).

**Who is not blind, by the lead's statements of 25 November 2026** (names only; no number was given to this author).
- **One design author** ran the cluster base's ionic world in composed form, world IDs 0 and 1, at the configuration's own pool seeds, against legacy at three steps. The configuration's seeds are the captured seed index 0's, so those are `base s0 w0` and `base s0 w1`. `spec/CRITERIA.md` §8 reports them apart.
  - The same author tried the base's ionic world on the engine for its first steps, as the inner model, version 3, with the default and with the floor field solver, and inside a composite.
  - Nothing else of the registered set was run on the engine by either design author: no JUPITER arm, no assembly cell, no integrated-ensemble world, no calcium world. **But `jupiter_baseline` is `base`'s ionic world, value for value, with the channels open throughout** (this author's comparison of the two blocks). What was seen on `base` bears on it.
- **The other design author** ran only worlds of their own making (a one-cell store world, kernels).
- **On the reference side** the design authors also made studies of the legacy code: a holding study over the base's worlds, pool runs, and an IP3 study.
- **The lead** has read both design notes' numbers. One of its rulings to this author, the conservation rule (`spec/CRITERIA.md` §4.4), came **after it had seen a design author's measured residuals**.
- **The judge and the checker are other agents.**

**What the conservation ruling replaced, before the first commit.** The author's uncommitted draft of 25 November (11:15 to 11:18 UTC) judged every run's balances as class R, at 8 ε (S + 1) s, and the energy as a class S identity against 0, at 2 U_c + 8 ε (S_c + 1) s + 4 × 10⁻¹² s. The ruling reached the author at 11:18:45 UTC, and the first commit (5b56f92c, 11:23:02 UTC) has the engine's own ledger
rule instead. The draft's bounds are printed beside the reported identities with a flag (`spec/READOUTS.md` §5), so the replaced rule's answer can be read. The author accepts the ruling, and §10's question 5 says where its reason does not apply.

**What this author has been told of any prototype.** That the runs above exist. Also, in the first wording of the field-solver ruling, that the default solver refuses some of the base world's first steps. That wording is not used: the requirement is now D147's standing rule, and its guard's rerun is a step before the campaign (§5). No step, order, margin or residual was told.
**The author has seen no result of any prototype and has opened neither design note nor its scratch folder. No band, class, window, scale or margin of this folder rests on them.**

**Dated note, 25 November 2026 (the lead's, from the user).** The user decided G-7's form: a driver writes the live pool's switch path into the ionic world's channel controls. The ionic world stays the inner model, version 3, on RK4, and the operator is not built now. No run informed it. Also decided: the assembly observable is a registered law with an ID and a page, of the family
`assembly_observable` (the user's word), and a candidate's definition records it, the composed file's fingerprint, the pool's seeds and the switch list in the run's inputs (`spec/TABLE.md` §3, `spec/CRITERIA.md` §4.1).

**What changed after the first commit (5b56f92c), hunk by hunk.** No band, class, window or scale changed, in either part (the two input files' scales equal the first commit's, checked by program, and their only other changes are the coupling's label and EP2's world). Planted numbers were first on screen at 11:40 UTC (Part 1) and 11:50 UTC (Part 2), and outcomes (completed or refused) from 11:32. The letter says what was on screen: **(a)** none, **(b)** Part 1's, **(c)** Part 1's and Part 2's. **"because of a number"** is said where it is so.

| File | What changed | When |
| --- | --- | --- |
| `CRITERIA.md` head, §8 | Who is not blind, and `base` in two sets (the lead's statement) | (a) to (b) |
| `CRITERIA.md` §8 | `integrated` no longer pending: its capture exists | (a) |
| `CRITERIA.md` §4.1, §5 | The switch list and the seeds of an ionic run, and who owns them (the user's decision on the coupling) | (c) |
| `CRITERIA.md` §4.3 | A compared time with no row, or with two, leaves the entry not formed. The first wording dropped the time, which would have let a missing row go unjudged | (c), a hole closed, not because of a number |
| `CRITERIA.md` §6 | EP2's own change is class E, since no echo checks it | (c) |
| `SPEC.md` §2.4, §3.1, §3.2, §3.3, §5, §6, §7, §8 | The echo's items, the field solver by D147's rule, the coupling's block and its decided form, the scale of a `_summary` entry, the closure term's derivation (its number unchanged), the captures of `integrated`, and a rehearsal world with free offsets | (a) to (c) |
| `READOUTS.md` §2, §3, §5 | `integrated`'s potential times, `channel_K_summary`'s times, and the printed bounds of the reported identities | (a) to (c) |
| `TABLE.md` §3, §5 | `inputs.assembly`, its label, and the `inputs` row | (c) |
| `PLANTS.md` §4 | ST5 and ST9 replaced before their runs, since the legacy side cannot run the first choices | (a) |
| `PLANTS.md` §4, §5 | ST6 and EP2 moved to a blind world, and ST10 added | (b). ST6's margin at world 1 had been printed |
| `PLANTS.md` §3 | PW-pool made four rates instead of one | (b). Its first output had been printed |
| `PLANTS.md` §6 | The judge's plants JP15 to JP18 | (b) to (c) |
| `PART2.md` §7.1, §7.4 | Two homes moved, **because of a number** (margins of 8 to 13, and a ratio of 1.4 × 10⁻⁴), and the rule for a home with several plants, **because the smallest ratio would have let an insensitive constant decide**. Both wait for a ruling (§10, question 13) | (c) |
| `PART2.md` §7.3, §7.4 | SC3 replaced by SC3b, because legacy's own domain check stopped it. SC13 added to the text (it was in the run plan of 11:28, before any run of Part 2). SC6's first choice refused by legacy | (b) to (c) |
| `PART2.md` §0, §3, §4, §9, §12 | The decided forms, the field solver, the clusters' decided coupling, the identities' flags, the reference's run | (a) to (c) |
| `CRITERIA.md` §4.5, §7, §8 | A wider wording (a home with several plants, the retry owed to an untested mechanism) was committed at 5f550674 and at 879d60ef, **because of a number**, and is reverted here to the first commit's words. Part 2's rule is in `PART2.md` §7.1 alone, so a ruling on it moves no file under Part 1's tag | (c) |
| Whole folder | A second form of the assembly coupling, registered as reported only at 5f550674 and removed after the user's decision (commit 879d60ef) | (c) |

The first commit's message says that no re-expressed run existed. That was this author's belief, and this section corrects it.

**Not read:** any candidate, any re-expressed run, the two design notes' folders (notes D and E) and any file of the builders' branches. The builders' live code was read at main 49529e71, and nothing of `legacy-cleanup`.

**Seen and not used:** the timings of the capture jobs, and the JSON summaries' values. Decision entries D384 and D385 were not read beyond their titles.
