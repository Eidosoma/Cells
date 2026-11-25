# The rehearsal: invented worlds and the reference side

`SPEC.md` section 8 of the spec folder registers a rehearsal of the comparison on invented worlds. This
folder holds its reference side: the worlds, the runs of the frozen legacy snapshot on them, and the files
that the judge reads. A rehearsal is evidence for the harness and the bounds. It is none for or against a
consumer. A bound that an honest invented run misses is a defect, and is corrected only by `CRITERIA.md`
section 10. Nothing here is a registered number, and no registered world was run.

**Files.**

| File | What it holds |
| --- | --- |
| `inputs_rehearsal.json` | The worlds and runs, in `inputs.json`'s schema, with `p`, `scales`, `amount_refs` and `closure_terms_V` |
| `legacy_rehearsal.json` | The legacy side's classes, the captured steps and step counts, and the pins of the capture sets |
| `reference_paths_rehearsal.json` | The event paths of the invented pools, made by the snapshot's own pool code alone |
| `margins_rehearsal.json`, `plants_manifest_rehearsal.json` | The invented power and structural plants: distances, ratios, margins and provenance |
| `profile_rehearsal.json` | What the judge needs to read the rehearsal, in its own shape |
| `make_inputs.py` | The generator: one table of invented numbers (`WORLDS`), the blocks, the legacy definitions and the runs |
| `rules.py`, `estimate.py`, `closure.py` | SPEC section 5 and 6 in standard-library arithmetic; the order and energy estimates; what the closure term leaves out |
| `exclusions.py`, `checks.py`, `parse_check.py`, `verify.py` | The checks: no number of the spec folder; the grid, the ratios, the definitions; the parse in the snapshot; the files against each other |
| `plant_driver.py`, `pool_paths.py` | The planted runs and the pools alone |
| `legacy_arrays.py`, `reference.py`, `make_profile.py` | The legacy arrays by READOUTS' names; the reference files; the profile |

Standard library and numpy only. None of it imports the engine, the builder's code or the judge's. The
legacy runs read the snapshot by PYTHONPATH.

## Regenerate

Set `S` to the frozen snapshot `/mnt/workspaces/Cells/legacy-captures-20261125/snapshot-76a498ae`, `B` to a new
scratch folder under `/mnt/workspaces/Cells/`, `R` to this folder and `P` to `/mnt/workspaces/Cells/venv-cpu/bin/python`.
Every engine run has `PYTHONPATH=$S/src:$S`, `JAX_PLATFORMS=cpu`, `JAX_ENABLE_X64=1`,
`JAX_ENABLE_COMPILATION_CACHE=false`, one thread, and the CPUs 6, 7, 22 and 23 under `nice`. Jobs over a minute
go through `scripts/run_detached.sh` with a memory cap.

```
$P $R/make_inputs.py write                            # inputs_rehearsal.json
$P $R/exclusions.py; $P $R/checks.py                  # no engine: no number of the folder, the grid, the ratios
$P $R/make_inputs.py origin $B/origin $S [WORLD ...]  # the definitions, the job list and the manifest of capture.sh
$P $R/parse_check.py $B/origin                        # the snapshot's parser, no run
validation/legacy_port/capture.sh $S $B/origin $B/science --set science   # the honest legacy runs, one process each
$P $R/pool_paths.py all $B/pools                      # the pools alone, and one rate x 1.01 at a time
$P $R/plant_driver.py plan $B/origin:$B/origin-cross $B/plan.json
$P $R/plant_driver.py all $B/plan.json $B/plants --cpus 6,7,22,23
$P $R/reference.py classes $B/science:$B/science-cross $R/legacy_rehearsal.json
$P $R/reference.py identities $B/science:$B/science-cross
$P $R/reference.py paths $B/pools/pools.npz $B/science:$B/science-cross $R/reference_paths_rehearsal.json
$P $R/reference.py margins $B/science:$B/science-cross $B/plants $B/pools $R/margins_rehearsal.json
$P $R/reference.py pool-runs $B/pools /tmp/pool_runs.json
$P $R/plant_driver.py manifest $B/plan.json $B/plants /tmp/pool_runs.json $R/plants_manifest_rehearsal.json
$P $R/make_profile.py write; $P $R/verify.py $B
```

The two capture sets (`origin`, `origin-cross`) differ in the world that they hold: `inv_cross` came after the lead's
addition of 25 November. Every world's definitions are its own origin's, and the first set was made before it.

To extend it (Part 2's rehearsal): add a world to `WORLDS` in `make_inputs.py`, its kind to the legacy writer
`legacy()` if it is a new one, its readouts to `legacy_arrays.py`, and its plants to `plant_driver.py`'s table.

## The worlds

Steps in µs. The legacy steps are h, h/2 and h/4 of the frozen snapshot's runs. Names in the block: cells `cell_0`
on, membranes `membrane_0` on and channels `channel_0` on, in the order of the cells. Regions are `bath` (the gauge,
and the one that the cells face, but in `inv_cross`), `cleft` and `rim`.

| World | Consumer | Legacy family and steps | Candidate's steps | Horizon (s) |
| --- | --- | --- | --- | --- |
| `inv_cluster` | `jupiter` | spatial_extracellular@2: 72, 36, 18 | 24, 12, 6 | 0.014112 |
| `inv_release` | `jupiter` | the same | 24, 12, 6 | 0.014112 |
| `inv_bound` | `jupiter` | 75, 37.5, 18.75 | 25, 12.5, 6.25 | 0.01635 |
| `inv_cross` | `jupiter` | spatial_extracellular@3: 64, 32, 16 | 16, 8, 4 | 0.014464 |
| `inv_amounts` | `jupiter` | 80, 40, 20 | 20, 10, 5 | 0.01264 |
| `inv_junctions` | `integrated` | finite_extracellular@3: 80, 40, 20 | 80, 40, 20 | 0.01736 |
| `inv_imex` | `integrated` | 96, 48, 24 (RK4) | 96, 48, 24 (IMEX, p = 2) | 0.01104 |
| `inv_offgrid` | `integrated` | 80, 40, 20 | 80, one run | 0.01128 |
| `inv_stop` | `integrated` | 20, 10, 5 | 80, one run | 0.00888 |
| `inv_default_omitted`, `inv_default_written` | `integrated` | 80, 40, 20 | 80, 40, 20 | 0.00936, 0.00952 |
| `inv_cell` | `cell` | finite_extracellular@2: 80, 40, 20 | 20, 10, 5 | 0.01648 |
| `inv_base` | `base` | spatial_extracellular@2: 60, 30, 15 | 20, 10, 5 | 0.01548 |

`inv_cell` has one pool of 16 worlds, and `inv_base` two pools of 6 worlds. Two seeds each, the judged ionic world IDs 0 to 3 of
each seed. The seeds are 70120435 and 70120441 (`inv_cell`), and 70321533 and 70421533 with stream 0 and the same plus 1 with
stream 1 (`inv_base`). Families `inv_cell s0 w2` and `inv_cell s1 w0` have no event: two honest families with one constant schedule.

## Which run is which item of SPEC section 8

| Item | World or run |
| --- | --- |
| The two-cell cluster with a pump schedule and free offsets, h1 at the bound | `inv_bound`, the three runs at 25, 12.5 and 6.25 µs (the exception of SPEC section 8; used in this family alone) |
| The same world with another schedule (JP3) | `inv_cluster` (constant) and `inv_release` (the pumps off and on), one world but for the schedule, at the same steps |
| One-cell and two-pool assembly worlds (class E, path, schedule, restart) | `inv_cell` and `inv_base`: the pool runs `inv_* s0 pool` and `s1 pool`, the ionic families, `inv_* s0 pool restart` |
| A small cluster of gated junctions with a schedule | `inv_junctions` (five cells, six junctions, natural order not the order of text: `junction_1, 2, 9, 10, 11, 12`) |
| Amounts as large against s as the registered ones, fixed charges off the electroneutral rule | `inv_amounts`: `amount_refs/scales` at least 7.1e4 (`n_out_K`) to 8.1e5, against 4.3e4 (`n_cell`), 6.3e4 (`n_out`), 2.5e4 (`voltage`) and 4.7e4 (`energy_identity`). Its fixed charges miss their rule by 1.0e-24 to 2.7e-24 C |
| A family on the IMEX integrator, p = 2, resolved | `inv_imex`. Orders by arithmetic (`estimate.py`), not by a run: 2.04 in every entry, d1 at least 58 times theta |
| One restart | Ionic: `inv_cluster h=2.4e-05 restart` (0.007056 s), `inv_junctions h=8e-05 restart` (0.00776 s), `inv_cell s1 w1 h=2e-05 restart` (0.00824 s), `inv_base s0 w2 h=2e-05 restart` (0.00774 s). Pool: `inv_cell s0 pool restart` (0.00744 s), `inv_base s0 pool restart` (0.00666 s) |
| One refusal of each kind | `inv_junctions refused definition` (an unknown junction law, declared change), `refused domain` (150 K, declared change), `refused harness` (`--max-seconds 0.05`, no change) |
| A stop by the engine's own check | `inv_stop h=8e-05`: RK4 leaves an energy residual of 1.5e-6 pJ in the row at 0.00472 s by arithmetic, 76 times the inner model's 2e-8 pJ |
| A declared change off the grid (`off_grid_change`) | `inv_offgrid h=8e-05`: the junction's schedule changes at 0.0041234 s, 51.54 steps of 80 µs. Made with `--off-grid` |
| A change one unit in the last place off its k h | The junction schedules' change at 0.01304 s in `inv_junctions`: k h is 0.013040000000000001 at 80, 40 and 20 µs |
| A schedule that writes out a default that the other party omits | `inv_default_omitted` (the block omits the leak schedules and a junction's, all 1 throughout; an exporter writes them out) and `inv_default_written` (the block writes out the pump's [[0.0, 1.0]] for membranes whose pump is null, and a junction schedule with a repeated value) |
| One run of each kind whose `steps`, `t` and restart follow section 4 | The families above, with the restarts |
| The two-set rule | `inv_base s0 w0` and `inv_base s0 w1` are marked not blind (`not_blind`, and `not_blind_pool_runs`) |
| The closure term's four omissions (the lead's addition of 25 November) | `inv_cross`, and the table below |
| The engine plants | `inv_cluster plant channel` (`inv_EP1`, declared change), `inv_release plant channel` (`EP1`, by variant), `inv_base plant swapped` (`inv_EP2`, declared change) and `inv_base plant swapped by variant` (`EP2`), each at its family's h3 |

The four kinds of run in the rehearsal and their count: 84 judged runs (15 `jupiter`, 26 `cell`, 26 `base`, 17 `integrated`), 6 support
runs (restarts), 4 plant runs: 94. The refused, stopped and off-grid runs have no family (`family` null), as they are not three runs of one world.
All of them are in consumer `integrated`, so that `jupiter`, `cell` and `base` hold honest runs, their restarts and their plants alone.

**How the builder makes the two special ones first** (its README): `one "inv_offgrid h=8e-05" --off-grid` and
`one "inv_junctions refused harness" --max-seconds 0.05`, then `all`.

## What the closure term leaves out, and which world shows it

SPEC section 6 derives e_close from a potential error of 2.13e-12 V* at a free offset and of 2e-12 V* at a node's charge, and from the
share of a flux that such an error moves. The criteria's author says that four things are not in it. The table is arithmetic on
declared values (`closure.py table`), with the field solver's constants as the snapshot declares them (absolute charge 3e-25 C,
relative 2e-12, absolute current 1e-23 A, relative 2e-12, Newton target 0.01). It is a share of what SPEC section 6 counts, not a measured
error. The columns:

- **ATOL:** the engine's absolute charge tolerance at the smallest capacitor, over 2e-12 V*;
- **RTOL:** its relative tolerance at the largest potential, over the same;
- **current:** the inner model's Newton target on the smallest incident conductance, over 2.13e-12 V*;
- **gate:** the gate's error over the run that a potential error of 2e-12 V* at each of a junction's two membranes makes, as a share of 4e-12 of the gate;
- **heat:** the second factor of a heat (J times the error of its driving force, both membranes' errors at a junction), over 2e-12 of the heat's scale;
- **|J|/gross:** the largest share of a route's net flux in its gross one.

```
world                     ATOL      RTOL   current      gate      heat |J|/gross
inv_cluster               0.34      0.44   3.5e-07      0.39     0.093      0.41
inv_release               0.34      0.44   3.5e-07      0.39     0.093      0.41
inv_bound                 0.42      0.47   4.8e-07      0.41     0.051      0.43
inv_cross                    3       0.5      0.98      0.27      0.73      0.46
inv_amounts               0.51      0.24    0.0023      0.27     0.063      0.28
inv_junctions             0.47       0.2         0         1      0.28      0.18
inv_imex                   0.4      0.22         0      0.54      0.21      0.16
inv_offgrid               0.41      0.18         0      0.79      0.12     0.079
inv_stop                  0.46      0.21         0      0.56      0.34      0.22
inv_default_omitted       0.42       0.2         0      0.57      0.17      0.11
inv_default_written       0.45      0.19         0      0.62      0.17      0.11
inv_cell                  0.12       0.6         0         0     0.055      0.53
inv_base                  0.35      0.45   3.7e-07      0.39     0.094      0.42
```

| What | World that shows it |
| --- | --- |
| A gated junction between two capacitor components with free offsets: a junction's two membranes, and the gate, enter the closure | `inv_cross` alone. Each of its three cells faces a region of its own, so each capacitor is a component. `gap_0` and `gap_1` read the absolute potentials of two cells, and the two regions that are not the gauge float. Its legacy family is spatial_extracellular@3, which the frozen snapshot holds beside the Part 1 families and whose state arrays have the same names; its return-current solve is the junction-aware one |
| A heat's second factor large | `inv_cross`, `gap_0`: its voltage is 0.110 V, so the second factor is 0.73 of 2e-12 of the heat's scale (the largest of the worlds). Next, `inv_stop` (0.34) |
| The charge tolerance at its largest share, free offsets, large capacitances against small currents | `inv_cross`: one capacitor is 4.2e-13 F (absolute tolerance 3.0 times the 2e-12 V* that SPEC counts), another 5.0e-11 F, currents about 1e-15 A (the absolute part is all of the current rule), and the Newton target admits 0.98 of the 2.13e-12 V* at the offsets |
| The gate path | The junctions in `integrated`: up to 1.0 (`inv_junctions`, `junction_10`) of 4e-12 of the gate. In `inv_cross`, `gap_1` is near its threshold (0.27) |

**What I cannot show:** a solver that stops at its tolerance. Legacy's own Newton ended at a normalized residual of at most 8e-8 of its rule (its
target is 1e-2 of that rule) in every row I looked at of `inv_cross`, so an honest run sits at rounding, and a miss would need two codes' errors to add.

## Numbers that coincide with the spec folder's, and why each must

`exclusions.py` compares every declared number of `inputs_rehearsal.json` and every legacy step with those of `inputs.json` and
`inputs_part2.json`, by kind (volumes, amounts, permeabilities, rates, seeds, times, steps, geometry), to 1e-12 relative. What is the same:

- **298.15 K** in every world with a channel: the channel law admits that temperature and no other. The worlds without a channel have others.
- **25, 12.5 and 6.25 µs** in `inv_bound` only: h1 is the channel law's stated bound (the exception that SPEC section 8 names), and its two halves.
- **The pump's -3 and +2, the valences, and 0 and 1** as schedule levels: the laws', not a world's.
- **The pool's graph:** the node numbers and bonds are the graph's. The initial nodes, rates and volumes differ. `world_id_start` is 0, and the harness
  fields (`event_chunk_size`, `recording`, `max_output_bytes`, `max_wall_seconds`) are the captured ones, as the criteria say they are not compared.
- **`closure_terms_V`:** the contract's number for `phi_out` (4.3e-12 V*), since every world with free offsets keeps the same or smaller geometry
  factors than SPEC section 6's 2.01 and 0.53 (`checks.py` prints them: at most 2.0097 and 0.5234).

## Readings

1. "No step of this folder is used, with one exception" covers the whole family at the bound (h1, h2 and h3), and no other family.
2. The steps of the legacy runs are none of the folder's either.
3. "One whose schedule writes out a default that the other party omits" has two worlds, one for each direction.
4. A run of a world that is not three runs of a family (off the grid, stop, refused) has `family` null and role `judged`.
5. The restarts are ionic ones in all four kinds and pool ones in the assembly kinds, since a restart's `steps` takes an addition for the events of `cell` and `base`.
6. `inv_release` gives JP3 its other schedule at the same steps; `inv_bound` is not used for it, so the exception is used in one family.
7. The structural plants' named entries are PLANTS section 4's, in the first world that has the mechanism: ST1 to ST5 in `inv_cluster`, ST8 in
   `inv_release`, ST9 in `inv_junctions`, ST6 and ST10 in `inv_base` (world 2 of seed 0, whose two paths differ and which is blind), ST7 and ST10 in `inv_cell` (world 1 of seed 0).
8. `voltage` takes the plant that moves it most of its world (PLANTS section 2), and `phi_out` the face's K diffusivity.
9. An assembly world's ratio and margin are the smallest over the judged world IDs 0 to 3 of seed 0 (Part 1 has eight).

## Not done, not checked

- **No run of a candidate.** I ran no builder's code and read no candidate output. Whether `inv_amounts` passes every entry, whether the IMEX family is resolved in the
  engine, whether the stop is the engine's, and whether the exporter reads a block with an omitted default are for the builder's runs to show.
- **The IMEX orders and the stop's energy residual are estimates** by `estimate.py`'s own arithmetic (its explicit tableau, with no face and no channel in the world).
  They are not measurements of a candidate.
- **A parse-only check with my own writing of the blocks:** every world at each of its candidate's steps (35 pairs) was written as a definition of the snapshot's
  inner model (version 3) and parsed by the snapshot's parser and step checks. All parse, at the channel law's bound too, with the one split (`inv_offgrid`) and the one snap
  (`inv_junctions`) that are meant. No run was made. The builder's generator is another thing, and the snapshot's live code is not the branch head's.
- **The captured arrays, the judge's code and the builder's code were not read.** The legacy runs' arrays were read only for the files of this folder, through READOUTS' names.
- **The closure shares** are arithmetic on declared values (above). No honest run was found to sit near a tolerance.
- **Class E on another machine** is as in the protocol: the pool paths were made on the captures' CPU model (`legacy_rehearsal.json` `captures.cpu_model`).
- **The reference identities** were checked on the legacy runs at h/4 (`reference.py identities`): every balance is at most 5e-4 of its bound and the energy identity at
  most 9e-3 of its (the resolved RK4 runs of `inv_imex`), with U_c = 0 and e_store 0.

## What the judge needs: the profile

`profile_rehearsal.json` is in the judge's own shape (its README, section 5), formed by `make_profile.py` and checked against the inputs file.

- **Folders.** `captures` gives each world its set, its kind (`windows` or `assembly`), its folder pattern and, for an assembly world, where
  its summaries are: `result` (`result.json`, `final_voltage_V` by world) for `inv_cell`, `ticks` (`observations/tick-<7 digits>.json` at 0 and at each of
  `summary_times_s`) for `inv_base`. `{step}` is `h`, `h2` or `h4`, `{seed}` the seed index. A set is a block of
  `legacy_rehearsal.json` with `root`, `science` and `science_manifest_sha256`: `captures` for every world but one, and
  `captures_cross` for `inv_cross`, which was made in a second set. Both sets' `MANIFEST.json` gives every file's sha256. The run folders are `<root>/<science>/runs/<job>`.
- **Engine plants.** The four plant runs, keyed by their `variant`: `inv_EP1` and `inv_EP2` carry `declared_change` in `inputs_rehearsal.json` (its `path` begins inside the world's
  ionic block), and `EP1` and `EP2` carry none, so the builder's own variant path is run and the profile's `change` is the judge's. All name `channel_K`. The
  registered distances are in `margins_rehearsal.json`: EP1's is `PW-channel`'s ratio times the largest `channel_K` of the control of its world, EP2's is
  ST6's at world 2 (`margins_rehearsal.json` `worlds.inv_base.structural`). They are 5.3e-8 fmol (`inv_EP1`, `inv_cluster`), 5.6e-8 fmol (`EP1`, `inv_release`) and
  2.0e-6 fmol (`inv_EP2` and `EP2`, `inv_base` seed 0, world 2), every one above 2 β by orders of magnitude.
- **Two sets of `base`.** `not_blind` marks `inv_base s0 w0` and `inv_base s0 w1`, and `not_blind_pool_runs` the pool run of their seed, as Part 1 marks `base`'s.
- **Targets** of the judge's plants: `plant_targets` names the runs and families.

## The legacy runs and their provenance

All from the frozen snapshot `snapshot-76a498ae`, one process each, cold (no compilation cache), one thread, on the captures' CPU model. The tool is
`validation/legacy_port` (`capture.sh` and `capture_worlds.py`), the one that made Part 1's captures; its sha256 is the captures' own.

| Runs | Folder (under the scratch folder `ensemble-rehearsal-20261125`) | Count |
| --- | --- | --- |
| The honest runs of 12 worlds | `science/runs/<world>-{h,h2,h4}` and `-s{0,1}` for the assembly worlds. Origin `origin` (generator at 9dcdce26) | 42 |
| The honest runs of `inv_cross` | `science-cross/runs/inv_cross-{h,h2,h4}`. Origin `origin-cross` (generator at b094d873) | 3 |
| The planted runs and the controls | `plants/<name>/`: `definition.json`, `run/`, `plant.json`. Plan `plan.json` | 89 (13 controls, 63 power, 13 structural) |
| The pools alone | `pools-r2/pools.npz` (declared) and `pools-<rate>.npz` (each rate x 1.01) | 5 files, 6 pools each |

- Every control equals the honest run at h/4 bit for bit (every array), as `reference.py margins` checks before it writes a margin. So the planted runs are compared with runs of the same definitions.
- **Two structural plants are refused by legacy's own ledgers at their first attempt** (ST1 and ST4), as in Part 1, and their second run has those two ledgers off and the domain checks on. Both are in the manifest.
- The 19 pool arrays are bit-identical between the pools alone and the coupled runs at h, h/2 and h/4, for every world, cell and seed. The exposures agree exactly with the captured ones.
- **Every legacy entry is unresolved or resolved inside its window**: 481 unresolved and 18 resolved (the nine of `inv_imex`, eight of `inv_stop`, and `gate_m` of `inv_cross`). None is mixed or outside its window.
- The manifests' sha256 are in `legacy_rehearsal.json` (`science_manifest_sha256`, one for each set), and the planted runs' and the pools' in `plants_manifest_rehearsal.json`. `verify.py` checks all of them against the files.
- Earlier trials are kept beside them (`draft-origin`, `draft-pools*.npz`, `try-cross*`, `plants-try`, `pools`). Nothing in the committed files comes from them; the first pool runs in `pools` have the arrays of `pools-r2`.
- The planted runs' `driver_sha256` is `plant_driver.py` at 5260e203. Its docstrings were wrapped afterwards for the linter, and its code is the same.
