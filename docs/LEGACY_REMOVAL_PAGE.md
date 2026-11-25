# The legacy cleanup: one question, and what goes

25 November 2026. Seven minutes to read, and three for section 1, the question. Basis of each number: **(m)** measured, **(r)** read in the code, **(e)** estimated,
**(reader)** measured by the independent reader of the retiring rows. The lists behind this page are `removal_list.tsv` (one row per file) and `open_rows.tsv` (one line per test function), in `validation/legacy_port/` on branch `legacy-removal-list`.

**In one sentence.** All of `src/cells/legacy` goes in one deletion, with everything that only served it. What you use comes back in the engine's own forms. The old code, its runs and its captures stay at the tag
`pre-cleanup-2026-11-25` and in `/mnt/workspaces/Cells/legacy-captures-20261125`.

**What you have approved (25 November, D386 and after):** the losses in section 6, the two things that your earlier decisions held, and the optional batch. **One question is left.**

## 1. The question: may these test rows retire?

**Almost none of these tests run today.** 193 test IDs would retire instead of being rewritten. **176 of them are in eight files that already fail to import on the cleanup branch,** and eight more are already out of their file (m). Nine can still be collected there: four of these fail, four need a GPU and were not run, and one passes (m).
So "keep them until the campaign's verdicts" would keep text and not tests. They run at the tag, and only there.

You decided that what is used leaves legacy in canonical forms, and that holds: the worlds are rebuilt, and the registered campaign judges them. This question is about the **test rows** on the old forms of those worlds. The list had said "rewritten" for 17 test files, with 372 IDs.
Each test function was read against what stays. A reader who had not seen that work read them again, planted 124 faults of its own, and found no claim about live code that only a retiring row holds. It found claims that **no** row holds, and four rows that need not go. All of that is in the numbers below.

| What became of the 372 | IDs |
|---|---|
| Rewritten, and run | 77 |
| Use nothing that goes, or need one word or number changed: they stay (four of them since the reader's report) | 32 |
| Left with the pump and symports work | 70 |
| **Would retire** | **193** |

| Class of the 193 | IDs | What it is |
|---|---|---|
| The older definitions' own refusals | 68 | Each refuses a field or a rule of a form that goes. The new forms refuse the same things by rows that stay (thirteen were missing and are written). **About 22 of the 68 have no counterpart, because the live form takes the input** (reader): a store at 0.2 V parses and steps, and a Hill power of 9 is accepted |
| General rows | 38 | Saving, loading, the command line, schedules, changed files: held by rows that belong to no family |
| Carried | 42 | A row that stays holds the claim, **and a planted fault of that claim makes it fail**. Most fail at their own assertion. Eleven of the named plants are caught by a ledger or a refusal of the engine's first, which is a real detection and is labelled so (`carrier_plants.tsv`); the reader's finer plants, which no ledger sees, all fail by an assertion |
| The campaign's own worlds | 9 | Judged by the registered campaign, once |
| Parked with the assembly ensembles | 27 | Commands, planning of a parked kind, sums over an ensemble, GPU agreement: parked by your earlier decision. Ten of them hold planning that other rows carry, or sums that nothing replaces |
| GPU only | 2 | No gate runs a GPU, and their tolerances are the older model's |
| Others | 7 | A tool's own row (the tool goes), one on the older kernel's two code paths, a reduction between two families that both go, three cubic proofs of the older observers, and a reference's own sampling |

**How they would go.** In a second commit, after the deletion's own and after the campaign's results. The reference's sampling row is the only one of a reference that the judge may use beside a miss, so its file stays until Part 2 is judged. If a consumer of the campaign fails or stays inconclusive, its rows come to you with it.
With them go 11 files: `test_assembly_cell.py`, `test_assembly_cluster.py`, `test_assembly_controls.py`, the four calcium tests (`er`, `gated`, `ip3`, `spatial`), one GPU test file, and three drivers (`integrated_matrix.py`, `spatial_matrix.py`, `cluster_reference.py`).
No data file loses its last reader, and no module of the engine is reached by them alone (m).

**If you say yes,** that is all. **If you say no to a class,** its rows are rewritten first, and their price is estimated then.

## 2. What no test holds afterwards

This holds whether or not you say yes, since the rows below run at the tag only.

- **Driven store worlds.** The campaign judges each driven cluster once, against the captured runs of the old engine. No test compares one with an independent reference afterwards, as the retiring rows did. New now: a pool on a store world's calcium channel conducts exactly on its path, and its restart is bit for bit.
- **The error of a driven world falls with its step.** Nothing live holds it: the order rows run undriven worlds, and Part 1 does not show it. The neighbour's answer through a junction is held, but not that its voltages meet an independent integrator (the older eight runs did, at 3e-9).
- **A batch of store worlds, run by its program.** No row compiles one (about 50 s of CPU). New now: a host row that both mapped paths give each world its own numbers. The vectorized path has no row whose worlds differ in their pump, route or condition numbers: a planted fault passes the five rows that were tried, and the rows of reactions fail on theirs (m). Two driven worlds with different schedules in one batch, and a driven world with a store in one, have none.
- **The order of a definition's lists matters now.** Another order of species, cells, patches, faces, channels, transporters, conditions, compartments, reactions or pools is another fingerprint. The older forms did not mind.
- **A pool's checkpoint from another backend is accepted.** The live one holds the packages, the flags and the Python, and no device. The older refused it. This is a follow-up after the landing, and nothing changes now.
- **A live pool's shape and clock in a checkpoint** are checked by no row. The retiring rows missed them too (reader).
- **A closed patch, a closed junction, and abundance 0.** A closed patch that still passes some of its routes fails one staying row, at any size. A closed junction that passes a hundredth, and a channel of abundance 0 that conducts as one of 1, fail none that the reader ran. Two lines that see all three are written and planted (2 s of CPU, no compile), and are not added yet.
- **On a GPU:** a saved restart, windows, and a mapped batch of an ionic world have no row; CPU and GPU agreement of driven and of store worlds has none. The two rows of the ionic GPU queue stay. They ran once on the L4 after their edit (2 pass, 305 s, m), and no gate runs a GPU.
- **`er_calcium.pump_rates` itself,** at its stall and over its availability: one row on the BETSE side holds it (`test_betse_emulator_laws.py`), and the claim leaves with that file (reader).
- **A switch and a change of one channel at one instant** are refused now; the older form put them in order.
- **Also not held:** the pinned store pump's and release gate's own functions run out of process, and that gate's six network branches; the slope of CaV1.2's kinetics by automatic differentiation; IP3's binding in the cytosol as a reaction of the store world; the older kernel's count of its own pieces; a stop asked for off the grid; the sums over an assembly ensemble's worlds; the older observers' cubic proofs.

## 3. What was written for it

Every row below was run, and fails on a planted fault at its own assertion.

| Row (branch `legacy-retiring-rows`) | Holds | Seconds of CPU | Planted, and failed by its assertion |
|---|---|---|---|
| `test_calcium_store_compiled.py`, a pool on its calcium channel | a driven store world: its path, and its restart bit for bit; it reuses the file's one program | 4.2 | the path read a step early, a closed channel that leaks, and a restart one part in 2^52 off |
| `test_batch_windows.py`, each world's own kind numbers | what both mapped paths give their one program, world by world; nothing compiles | 2.0 | every world given the first one's numbers, in each path |
| `test_composed_worlds.py`, the neighbour | its bound is 1e-6 of the answer now (it was 1e-3; honest is 3.7e-8) | none more | each patch reading a millionth of the other cell's potential |

They merge after Part 1's strings tag. The preferred form of the batch row, a staying batch whose worlds differ, does not exist: no staying mapped batch has these kinds.
Written earlier on the cleanup branch, each with its plants: a store world at equilibrium (the world without buffers), thirteen refusals of @3's parser, a saved ionic ensemble's device kind, the two parked commands, and the pool's exposure and rechunked run.
Two rows stay after the reader's report: `test_integrated_ensemble.py`'s checkpoint row (29 s of CPU, tier 3) and `test_surface_catalog_planning.py`'s one row (one word changed). Both go on the queued test review's list.

## 4. Counts

| Area | Goes |
|---|---|
| `src/cells/legacy` with its entry, and four tables of `laws/channels` | 326 files, 75,867 lines (m) |
| Tests, and their helpers | 302 of 894 files (101,495 lines), and 77 files (18,717) (m) |
| Validation drivers and references | 758 of 1,720 files, 212,182 lines (m) |
| Scripts; configurations; examples; test data | 98 of 123; 116 of 157; all 15; 7 (m) |
| Test IDs | **11,217 of 21,927**: 10,956 in files that go, 261 rows in files that stay; 615 are new (m) |

The optional batch is in these counts (165 files, 49,055 lines, 1,933 IDs). The deletion saves 2,766 of 13,784 test-seconds in tiers 1 and 2 (m), about 8.6 minutes of wall per full gate (e), and 142 of 222 tier-3 files.

| Measured on two staged trees, at 936274d6 | The deletion alone | With the second commit |
|---|---|---|
| Files removed, and edited | 1,693, and 42 | 1,704, and 48 |
| Tests that collect | 11,011 | 11,002 |
| Files that fail to import | 8 | 0 |
| Staged tree | abafa43b | 78167cf2 |

On the first tree, five rows of three staying files fail when they run, since they read what left; the second commit takes them out. On the second, the rows of the six files that the prepared retirements change and the three rows of section 3 pass (49), and two GPU rows skip (m). The guard whose list the script edits passes its 17 rows on both, and the 15 library pages pass their check (m). 129 definitions leave the gate's fingerprints, of 194. 302 rows of the tier record leave with the deletion, and 8 more with the second commit, since the gate refuses a row without a file.
Nothing that stays imports or loads what goes, `lean/` and `visualizer/` included, but for one script of the campaign's rehearsal, which runs the frozen legacy snapshot (m).

## 5. What comes back

| You use | It becomes | Needs |
|---|---|---|
| The JUPITER world, the cluster base, the assembly cell, the integrated ensemble's world | closed `resolved_pump_tissue@3` worlds, same equations | their registered runs and the judge |
| The four calcium clusters | a composite over @3, one store per cell | the same |
| The assembly commands and ensemble kinds | CPU runs, one process per world. The GPU path is parked | the same |
| The JUPITER platform check | its device part as it is; its model part is refused by name | **your choice after the cleanup:** rebuild it on the re-expressed JUPITER world, half a day (e) |
| NKCC and the generic symport | two laws on the transporter kind | nothing: in |

## 6. What is lost, as you approved

**The laws stay (D211)** in live `laws/`, each with its reference and a kernel test: 44 of 47 port as they are. `law_reference_checks.tsv` has one row for each of 134 laws and kernels (D196). Four had lost their only direct check, and each has a row beside it now.

| Lost, or not carried over | In one sentence |
|---|---|
| Cell-zone transporter (I10) | At the tag; it is BETSE's network |
| Finite ATP, ADP and phosphate pools, and the finite-fuel pumps (C2, C3, I4, I5) | Not in the engine after the cleanup, and not lost for good; row fuel for the Na/K pump is a request you may make |
| Ceilings on an ion's total (D2); lateral redistribution and mobile proteins (D5); cutting cells out (D9) | Lost until you ask |
| BETSE-facing preparation (P1) and its four commands; the refinement clock | Gone |
| GPU ensembles of assembly clusters | Parked |
| Physiology stack and REF-era BETSE drivers (D374) | Retired by you: 559 files; their protocols and reports stay |
| Live BETSE runs in four parity files | Three had not been able to start since 11 October, and one is skipped. Their closed-form rows stay (55 pass). The three parity files whose BETSE run works keep it: 16, 38 and 25 rows pass, and 64 captures are equal bit for bit (m) |
| `network_reactions@1`, `network_control_factors@1` (C3) | At the tag, as you agreed. The finite-fuel forms and their regulated kinetics have no live replacement |
| `emt_mirna_pair@1` (D149) | At the tag, as you agreed. The EMT switch runs on the live engine; the pair written the source's way does not, and it is captured |
| `source_decay@1`, `emt_mirna@1`, `passive_pair@1` (G1, G2), neutral mobile leak, mitochondrial passive (I1, I11); `verify_batch_windows_build.py` | Gone; the tests that used them run live worlds |
| `tissue-phase`, `tissue-geometry`, `tissue-profiles`, `excise`; 15 examples; 96 scripts | Removed. `assembly-cell` and `assembly-cluster` are refused by name |
| Law records in the viewer's inventory | 13 units lose one or two; U37, U38 and U47 have none left |

Nothing in use is lost in the oldest families, the baths and clusters, mitochondria, water, injury, bath schedules, barriers and membrane profiles: @3's line does the same physics.

## 7. What is open

- **Yours:** section 1; the JUPITER check's model part (section 5); and leave to remove the throwaway trees named at the end.
- **Before the deletion:** the campaign's registered runs (Part 1's criteria and Part 2's are tagged), and the rename's tool, table and note. The deletion is one commit, made from the list by a script that names the head and the list's revision. Nothing is merged before you have seen this page.
- **After the landing:** what a pool's checkpoint does with another backend; the two rows for the test review; five dead names in live laws.
- **Records stay:** 59 protocol, data and record files, the results, the notes and the decisions. 57 documents say what left, and 31 more get their note in the deletion's commit. 463 relative links into removed files break, most of them under such a note (m, at 5429a49b).
- **Not run:** no gate and no suite. The full test of the cleanup branch is the test of it.
- **Throwaway trees:** `tree-t1` and `tree-t2` (195 MB each: the two measured trees, with two commits of the measurement on no branch), `tree-retarget` and `tree-plants3` (222 MB each: where the plants run), and a shared clone of 252 KB, all under `/mnt/workspaces/Cells/legacy-removal-list-20261125`. All are measurement or planting copies, and nothing else uses them.
