# The rehearsal of Part 2: invented worlds and the reference side

`PART2.md` section 15 registers a rehearsal of Part 2's comparison on invented worlds. This folder holds its
reference side, as `../rehearsal/` holds Part 1's: the worlds, the runs of the frozen legacy snapshot on them, and
the files that the judge reads. A rehearsal is evidence for the harness and the bounds. It is none for or against a
consumer. Nothing here is a registered number, and no registered world was run. The spec was read at the criteria's
commit 74e3b8fd.

**Three outcomes are meant at the consumers' level. None of them is a defect of the rehearsal:**

| Consumer | Made to be | Why |
| --- | --- | --- |
| `plasma_calcium` | **inconclusive, by design** | `inv_thin`'s store voltage is small, so a home entry of it is not tested (reason `power`). Its three refused runs are in this consumer too (reason `refused`) |
| `gated_calcium` | **a fail, by design** | `inv_stop` is a judged run that the engine's own check stops (class D). Nothing else in this consumer is meant to fail |
| the other six | able to pass | Honest families, a restart and engine plants alone |

## Files

| File | What it holds |
| --- | --- |
| `inputs_rehearsal_part2.json` | The worlds and runs, in `inputs_part2.json`'s schema, with `p`, `scales`, `amount_refs`, `closure_share`, `closure_terms_V`, `closure_terms`, and in one world `fuel_standard_mu_RT` |
| `legacy_rehearsal_part2.json` | The legacy side's classes, the captured steps and step counts, and the pins of the capture |
| `reference_paths_rehearsal_part2.json` | The event paths of the two invented pools, made by the snapshot's own pool code alone |
| `margins_rehearsal_part2.json`, `plants_manifest_rehearsal_part2.json` | The invented power and structural plants: distances, ratios, margins and provenance |
| `profile_rehearsal_part2.json` | What the judge needs to read the rehearsal, in a **proposed** shape (below) |
| `make_inputs2.py` | The generator: the worlds, their blocks, the legacy definitions and the runs |
| `rules2.py` | `PART2.md` section 8 in standard-library arithmetic: scales, references, closures |
| `exclusions2.py`, `checks2.py`, `verify2.py` | The checks: no number of either part; the grid, the ratios, the offsets, the fuel, the definitions; the files against each other |
| `plant_driver2.py`, `pool_paths2.py` | The planted runs and the pools alone |
| `legacy_arrays2.py`, `reference2.py`, `make_profile2.py` | The legacy arrays by `PART2.md` section 6.1's names; the reference files; the profile |
| `estimate2.py` | This runner's own estimate of the classes and of the stop's residual (no engine run) |

Part 1's modules in `../rehearsal/` are reused: its scales and grid rule, its pool and plant helpers, its reader of the
windows. None of this imports the builder's code or the judge's. `estimate2.py`, `pool_paths2.py`, the planted runs and
`checks2.py definitions` read the frozen snapshot by PYTHONPATH. The rest is standard library and numpy.

## Regenerate

Set `S` to the frozen snapshot `/mnt/workspaces/Cells/legacy-captures-20261125/snapshot-76a498ae`, `B` to a new scratch
folder under `/mnt/workspaces/Cells/`, `R` to this folder, `P` to `/mnt/workspaces/Cells/venv-cpu/bin/python` and `SPEC` to
the spec folder, or a copy of it at the criteria's commit. Every engine run has `PYTHONPATH=$S/src:$S`,
`JAX_PLATFORMS=cpu`, `JAX_ENABLE_X64=1`, `JAX_ENABLE_COMPILATION_CACHE=false` and one thread, and jobs over a minute go
through `scripts/run_detached.sh` with a memory cap.

```
$P $R/make_inputs2.py write                        # inputs_rehearsal_part2.json
$P $R/exclusions2.py $SPEC; $P $R/checks2.py $SPEC # no engine: no number of either part, the grid, the rules
$P $R/checks2.py definitions                       # the snapshot's parser, no run: every block against its parse
$P $R/make_inputs2.py origin $B/origin $S [WORLD ...]
$P $R/../rehearsal/parse_check.py $B/origin        # the snapshot's parser, no run
validation/legacy_port/capture.sh $S $B/origin $B/science --set science    # the honest legacy runs
$P $R/plant_driver2.py plan $B/origin $B/plan.json
$P $R/plant_driver2.py all $B/plan.json $B/plants --cpus 12,13,14,15,28,29,30,31
$P $R/pool_paths2.py run $B/pools.npz; $P $R/pool_paths2.py near $B/pools.npz
$P $R/reference2.py classes $B/science $R/legacy_rehearsal_part2.json
$P $R/reference2.py identities $B/science
$P $R/reference2.py paths $B/pools.npz $B/science $R/reference_paths_rehearsal_part2.json
$P $R/reference2.py margins $B/science $B/plants $R/margins_rehearsal_part2.json
$P $R/plant_driver2.py manifest $B/plan.json $B/plants $R/plants_manifest_rehearsal_part2.json
$P $R/make_profile2.py write; $P $R/verify2.py $B
$P $R/estimate2.py; $P $R/estimate2.py --stop inv_stop
```

## The worlds

Steps in µs. The legacy steps h, h/2 and h/4 are the candidate's h1, h2 and h3, as the captured ones are in Part 2
(`inv_stop` has its own). Cells are `cell_0` and `cell_1`, membranes `membrane_0` on, channels `channel_0` on and
calcium channels `calcium_channel_0` on, in the order of the cells. Regions are `bath` (the gauge, and the one that the
cells face), `cleft` and `rim`, so every world has two free field offsets. The chemical rows and the reactions have the
captured names, since the readouts are named by them.

| World | Consumer | Cells | Steps, and the retry's | Horizon (s) | What it is for |
| --- | --- | --- | --- | --- | --- |
| `inv_spatial` | `spatial_calcium` | 2 | 16, 8, 4; 2 | 0.01568 | the two-cell cluster with a store each, a gated junction that carries Ca, Ca on its faces |
| `inv_plasma` | `plasma_calcium` | 2 | 16, 8, 4; 2 | 0.01568 | the plasma pump and the exchanger; its store capacitor is six times the others' |
| `inv_gated` | `gated_calcium` | 2 | 16, 8, 4; 2 | 0.01568 | the calcium channel |
| `inv_ip3` | `ip3_calcium` | 2 | 16, 8, 4; 2 | 0.01568 | IP3 and its Hill read; the restart and the release plants |
| `inv_single` | `spatial_calcium` | 1 | 48, 24, 12; 6 | 0.01248 | one cell with one store; the order resolved in its window |
| `inv_amounts` | `spatial_calcium` | 2 | 20, 10, 5; 2.5 | 0.0122 | amounts as large against s as the registered ones, and more |
| `inv_slow` | `plasma_calcium` | 2 | 1.2, 0.6, 0.3; 0.15 | 0.001248 | at rounding |
| `inv_thin` | `plasma_calcium` | 2 | 14, 7, 3.5; 1.75 | 0.0105 | a thin store voltage |
| `inv_capacitor` | `plasma_calcium` | 2 | 15, 7.5, 3.75; 1.875 | 0.0102 | a big store capacitor (48 times the others') |
| `inv_fuel` | `gated_calcium` | 1 | 18, 9, 4.5; 2.25 | 0.0108 | fuel potentials large against their difference |
| `inv_stop` | `gated_calcium` | 1 | 40, one run | 0.00464 | the stop; legacy at 4, 2 and 1 µs |
| `inv_cluster_spatial`, `_plasma`, `_gated`, `_ip3` | `cluster_<kind>_calcium` | 2 | their child's | 0.01568 | two pools a world, two seed indices, worlds 0 and 1 |

- **The worlds' numbers** are drawn once by a seeded generator about a round centre, and rounded to four digits (`make_inputs2.py`,
  `calcium`). The inputs file holds them.
- **The compared rows** are a fine grid (the first steps, at h1) and a coarse one, 69 to 229 rows a world. Every declared time is on
  the grid of all four steps and of the legacy steps (within 2 ε t), and every horizon is the steps' product bit for bit.
- **The Hill coefficients** are 4 (activation), 3 (inhibition) and 1 (IP3), so that a swapped pair shows. The registered ones are all 2.
- **The stores' K** is the cytosol's concentration to seven digits, so that calcium's currents make the store's voltage, as in the
  registered worlds. In `inv_stop` it is 2.3 times.
- **The stores start at 0 V,** so a cell's charge is its membrane's capacitance times its initial voltage (section 2.2).
- **The pools** are two five-rings of the pool's graph, one a cell, with 3 to 8 events in every path of every seed and world (38 in
  all), and at least one change of availability. The four clusters hold the same two pools, as the registered ones hold base's.
  The closest event to a grid point or a step's middle of the four steps is 3.2e-3 of a step away.

## Which run is which item of section 15

| Item | World or run |
| --- | --- |
| One cell with one store | `inv_single` (no junction, so it has no junction entries), and `inv_fuel`, `inv_stop` |
| A two-cell cluster with a store each, free offsets, a gated junction with Ca, Ca on its faces | `inv_spatial` and the other two-cell worlds |
| The plasma pump and the exchanger; the calcium channel; IP3 and its Hill read | `inv_plasma`; `inv_gated`; `inv_ip3` |
| A two-pool cluster with at least one event in each path | all four clusters |
| A family whose order is resolved in its window | `inv_single` (estimate) |
| A family whose entries straddle θ at the first triple | `inv_spatial`, and the others at 16, 8 and 4 µs (estimate) |
| A family at rounding | `inv_slow` (estimate) |
| Fuel potentials large against their difference | `inv_fuel`: `fuel_standard_mu_RT` beside `p`, A = 2,708.9 |
| The retry run of every family, unread until `retry_owed.json` is hashed | by rule, `<family> h=<half the last step> retry`: 26 families, so 26 retry runs (the profile's `retry_step_s`) |
| Amounts as large against s | `inv_amounts`: `amount_refs/scales` 7.9e4 for `cyt_Cl` (at least 1.7e4), 43 for `store_K` (4.4), 43 to 127 for `n_out` (22), 3.3e4 for `voltage` (7.7e3), 46 for `store_voltage` (4.8). Every row's ratio is above the registered row's own. Its fixed charges miss their rule by 1.3e-24 to 3.5e-24 C, in the captured style |
| One restart | `inv_ip3 h=1.6e-05 restart`, at 0.00768 s |
| One refusal of each kind | `inv_plasma refused definition`, `refused domain`, `refused harness` |
| One run stopped by the engine's own check | `inv_stop h=4e-05` |
| EP3 and EP4 | `inv_ip3 plant release` and `inv_cluster_gated plant swapped`, each by a declared change and once more by the registered variant alone |
| The two sets of a cluster | seed index 0 is set A (`not_blind`), seed index 1 set B, which owns the cluster's plants and engine plant |
| A thin store-voltage home, and a big capacitor (the lead's addition) | `inv_thin`; `inv_capacitor`. In the clusters the store's capacitor is listed `cluster_not_tested`, as registered, and in `inv_cluster_plasma` its margin at the end is above 10 all the same, so the list and not the number decides |
| The faulty tables of JQ1 to JQ34 | the judge's, from these runs (below) |

## The runs, and what each is made to have

95 runs are listed: 90 judged, 1 support, 4 plants. The steps are the table's, and a name holds the step's `repr`.

| Run | Count | Made to have | This runner's own estimate, not a measurement |
| --- | --- | --- | --- |
| `inv_spatial h=…` (1.6e-05, 8e-06, 4e-06) | 3 | a pass, with mixed entries at the first triple, each owed the retry | 18 unresolved, 31 resolved, 7 mixed; at the retry's 35 unresolved, 2 resolved, 19 mixed |
| `inv_single h=…` (4.8e-05, 2.4e-05, 1.2e-05) | 3 | a pass, resolved in its window | 12 unresolved, 34 resolved, 4 mixed; at the retry's 16 unresolved, 31 resolved, 3 mixed |
| `inv_amounts h=…` (2e-05, 1e-05, 5e-06) | 3 | a pass in every entry | 24 unresolved, 22 resolved, 10 mixed; at the retry's 39 unresolved, 3 resolved, 14 mixed |
| `inv_plasma h=…` | 3 | a pass of its entries | 19 unresolved, 27 resolved, 14 mixed; at the retry's 40 unresolved, 3 resolved, 17 mixed |
| `inv_slow h=…` (1.2e-06, 6e-07, 3e-07) | 3 | unresolved, and within β | 60 unresolved; at the retry's 60 unresolved |
| `inv_thin h=…` (1.4e-05, 7e-06, 3.5e-06) | 3 | within β, with a home entry not tested (`power`) | 34 unresolved, 23 resolved, 3 mixed; at the retry's 46 unresolved, 4 resolved, 10 mixed |
| `inv_capacitor h=…` (1.5e-05, 7.5e-06, 3.75e-06) | 3 | a pass of its entries | 19 unresolved, 32 resolved, 9 mixed; at the retry's 35 unresolved, 4 resolved, 21 mixed |
| `inv_plasma refused definition` | 1 | refused, kind `definition` (an unknown junction law, declared change at h2) | |
| `inv_plasma refused domain` | 1 | refused, kind `domain` (151 K in `ionic` and in both stores, outside both channel laws) | |
| `inv_plasma refused harness` | 1 | refused, kind `harness` (a cell's plasma pump holds another ATP than its store pump, which section 2.1 has the generator refuse by name) | |
| `inv_gated h=…` | 3 | a pass of its entries | 17 unresolved, 33 resolved, 14 mixed; at the retry's 42 unresolved, 4 resolved, 18 mixed |
| `inv_fuel h=…` (1.8e-05, 9e-06, 4.5e-06) | 3 | a pass of its entries, not refused by its echo | 16 unresolved, 32 resolved, 10 mixed; at the retry's 31 unresolved, 6 resolved, 21 mixed |
| `inv_stop h=4e-05` | 1 | a stop (kind `check`, the energy ledger), so D fails | the energy residual is 24 times the inner model's IMEX allowance (2e-8 pJ and 2e-3 of the heats and works so far) in the first row, and above it in the first 50 |
| `inv_ip3 h=…` | 3 | a pass | 26 unresolved, 30 resolved, 12 mixed; at the retry's 48 unresolved, 5 resolved, 15 mixed |
| `inv_ip3 h=1.6e-05 restart` | 1 | equal to its judged run: 68 E entries, one per class S readout and potential | |
| `inv_ip3 plant release` (`inv_EP3`), `… by variant` (`EP3`) | 2 | caught at `store_release` | |
| `inv_cluster_<kind> s0 pool`, `s1 pool` | 8 | equal arrays, path and seed (21 E entries a cell), the exposure within its bound | |
| `inv_cluster_<kind> s{0,1} w{0,1} h=…` (1.6e-05, 8e-06, 4e-06) | 48 | a pass, set by set | as its child's |
| `inv_cluster_gated plant swapped` (`inv_EP4`), `… by variant` (`EP4`) | 2 | caught at `channel_K` and `channel_K_summary` | |
| the retry run of each of the 26 families | (by rule) | what `PART2.md` section 13 says | as above, at the retry's triple |

**Structural plants** (planted legacy runs, scored against the honest candidate): SC1, SC3b, SC4, SC5, SC6 and SC13 in
`inv_spatial`, SC7, SC8 and SC12 in `inv_plasma`, SC9 and SC10 in `inv_gated`, SC2 in `inv_ip3`, SC11 and SC14 in
`inv_cluster_gated` at seed index 1. Each is made to be caught at its named entries. SC3 is stopped by legacy's own domain check,
and SC6-stoichiometry is refused at parse, as the registered two are; neither is scored.

**What the estimates are.** `estimate2.py` integrates the snapshot's own legacy right-hand sides by an ARS(2,2,2) explicit part with
Strang halves of the reactions, the fields solved at each stage. It is not the candidate's scheme: there the faces' drift is implicit and the channels'
gates are exponential. So a count says which class an entry may have, by its truncation alone and with no rounding.

## The closures, by section 8's rule

- **`rules2.py check`** forms the four registered children's numbers from their blocks: every scale and every `amount_refs` to 2.1e-16, all 166
  `closure_terms` and the three `closure_terms_V` to the printed digits. The same code forms the rehearsal's.
- **One `closure_terms_V` over all the children of this file** (the lead's word on the text's "the largest … over the worlds"): `phi_out` 5.16e-13 V,
  `voltage` 6.8e-12 V and `store_voltage` 2.2e-11 V, from the largest of the eleven. A cluster's are its child's, without `phi_out`.
- **The free offset's error is taken at the world's own retry step** (the smallest of its four), where it is largest.
- **The row factor:** every world's own is 1.963 to 1.970, below the 2.01 of the text, and its largest conductance over its smallest sum 0.512 to 0.514. So the text's
  constants and the world's own numbers give the same closures (both were formed).
- **No closure number lies near an edge of its two figures.** None of any world changes when the gate slopes are rounded to 0.1 per V, as the text
  prints them, or the stages' errors to three digits, and none is within 1e-4 of an edge or 1e-3 of the share. A C0 difference here is a difference of rule, not of arithmetic.
- **`store_voltage`'s max |V0|** is the cells' (`PART2.md` says max |V0|, and the registered 16.02 V is 0.06 V more than the rest).
- **The gates' slopes over their domains,** per V: `gate_m` 70.718, `gate_h` 79.695, `ca_gate_m` 69.779, `ca_gate_h` 55.009, and the junction's by its own threshold and minimum.

## Numbers that coincide with the spec folder's, and why each must

`exclusions2.py` compares every declared number of `inputs_rehearsal_part2.json`, every legacy step and every retry step with those of
`inputs.json` and `inputs_part2.json` (and the captured steps of both legacy files), by kind, to 1e-12 relative. What is the same:

- **298.15 K:** both channel laws admit that temperature and no other.
- **The stoichiometries, the valences, 0, 1 and -1:** the laws', a schedule's level, an absent route, the 1 mM standard state.
- **The pool's graph:** node numbers and bonds are the graph's. The rings, rates, volumes and seeds differ. The harness fields are the captured ones, which the criteria do not compare.
- **The names:** the chemical rows, the reactions, `cytosol` and `er` are the captured labels, and no number.
- **`closure_share` and `phi_out`'s closure:** the contract's.

No step, horizon or time of either part is used, with no exception (Part 1's 25 µs exception is Part 1's).

## Readings

1. Section 15's "the captured steps" are the worlds' own h, h/2 and h/4, equal to the candidate's three steps, in `legacy_part2.json`'s layout.
2. `closure_terms_V` is literal: one number over the file's children (the lead's word).
3. `fuel_standard_mu_RT` beside `p` in `inv_fuel` tells the generator the three potentials to declare. It is no part of the block (the lead's word). No cluster holds it.
4. A one-cell world has no junction entries: a series that a world lacks is no entry.
5. The four clusters' paths stand once, under `inv_pools`, and the profile's `paths` says so for each cluster.
6. The retry's runs are not listed, as in `inputs_part2.json`.
7. A `declared_change`'s path begins at the world's block. EP3 and EP4 are each made once by a declared change and once by the registered variant alone.
8. A refused or stopped run has `family` null and role `judged`, as in Part 1's rehearsal.
9. The stores' initial voltage is 0 in every world, as section 2.2's derivation of a cell's charge has it.
10. The clusters' ratios are their child's halved, at the end (`cluster_entries_at_the_end`), with the four `_summary` rows and the two potentials at the summary times, which are all compared rows of the child.
11. The bands of the margins take U_c = 0 at the first triple's S_c and at the retry's, and U_c = θ/3 at the retry's widest (section 7.4), with each world's own step counts.

## Not done, not checked

- **No run of a candidate,** and none of the builder's, the judge's, the authors' or the auditors' files was read. Whether the honest runs pass, whether the orders
  are what the estimate says, whether the stop is the engine's energy check and the refusals have the kinds above, is for the builder's runs to show.
- **No candidate-side truth of the solves' noise** (section 15's last paragraph): the rehearsal's honest runs show it. `inv_slow` is the family at rounding for it.
- **The captured arrays were not read.** The legacy arrays read here are those of the invented worlds alone.
- **Class E on another machine** is as in the protocol.

## The legacy runs

Under way at this commit: the reference-side files come with the next one. The inputs, the profile and the run list above are final.
