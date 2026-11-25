# The judge of Part 1

**What it is.** The reader and the scorer of `spec/` (`ensemble-reexpression-v1`, Part 1), with `spec/AMENDMENT-1-2026-11-25.md` and the lead's rulings of 25 November on the judge's questions (Amendment 2). It imports nothing of the engine: the standard library and numpy.
It was written from the spec folder, the protocol, the captures and the planted legacy arrays alone. Its author has read no engine source, no test, no builder's branch, no candidate, and no table of a candidate. None existed. The builders' format sample (invented worlds, meaningless numbers) was read after the reader was written (§6).

## 1. Files

| File | What it does |
| --- | --- |
| `constants.py`, `strictjson.py` | The contract's names and numbers. JSON with duplicate keys refused, NaN and Infinity read |
| `registration.py` | The spec's data files as worlds, entries, families, runs, plants; the strings note; a rehearsal's profile |
| `legacy.py` | The captures and the planted runs. Every file is checked against a pinned sha256 before it is used |
| `rules.py` | The scales, `amount_refs` and closures by rule, from a world's block |
| `bands.py`, `identities.py` | The estimates, bands and order rule; the balances, the capacitor, the energy identity, the exposure |
| `table.py` | The tables: files, hashes, the echo, provenance, what a run is, what its rows hold |
| `c0.py` | C0 |
| `scoring.py` | Stage 1 (power), stage 2 (scores, plants, the retry, verdicts) |
| `fabricate.py`, `plants.py` | The judge's own honest tables, and JP1 to JP24 |
| `structure.py` | The structure-only mode, for the format sample |
| `__main__.py`, `test_judge.py` | The commands, and the tests |

## 2. The method

- **Entries follow from the data.** A world's class S entries are its `scales` keys (but `energy_identity`, and a zero scale is a class E zero), over the times of READOUTS section 3. C0 checks that the counts are the published ones (`jupiter` 50, `cell` 480, `base` 800, `integrated` 9, and so on).
- **The captures** are read by READOUTS section 2's indices, in the order of the captured definition's lists, which C0 compares with the inputs'. Windows are joined with the earlier one owning the shared row.
- **A run** is first read for what it is (file, presence, echo, provenance, refusal or stop, copy guard), then for what its rows hold. A run whose echo stands is judged on what it holds, whatever else is wrong with it.
- **Stage 1** reads the tables' rows, the inputs, the strings note and C0's record. C0's record holds U_l and max |L₃|, so stage 1 opens no capture. It writes `power.json`: every entry's d₁, d₂, q, class, U_c, β with and without e_store, planted distance, whether it is tested, the mechanisms, and the copy guard's comparison (a).
- **Stage 2** starts only from `power.json`'s recorded sha256. It forms stage 1 again from the same tables and refuses unless the two are equal, value by value. Then it forms the differences.
- **Nothing is overwritten.** Every output is a new file, and the command fails where it exists.

## 3. The commands of the campaign, in order

`J` is `nice taskset -c <cpus> /mnt/workspaces/Cells/venv-cpu/bin/python -m validation.ensemble_reexpression.judge`, from the checkout's root. `T` is the folder `table/`, `R` is `table-retry/`, `O` is a new output folder. Exit 0: done (for `c0`, `selftest`, `plants` and `structure`, without a fault). Exit 1: a fault. Exit 2: refused, out of order or a pinned file that changed.

| | Command | Opens | Writes |
| --- | --- | --- | --- |
| 1 | `J hash --tables T --out O/hashes.json` | The bytes of `T/table_*.json` and `T/SHA256SUMS`. Nothing is parsed | `hashes.json` |
| 2 | `J c0 --tables-record O/hashes.json --out O/c0.json` | The spec's data files and texts, the captures and the planted runs they name. **No table** (the record's bytes are hashed) | `c0.json` |
| 3 | `J stage1 --tables T --tables-record O/hashes.json --strings validation/ensemble_reexpression/registered_strings.json --c0 O/c0.json --out O/power.json` | The tables (which must be the recorded ones), the strings note, the spec's data files, `c0.json`. **No capture, no planted run** | `power.json` |
| 4 | The lead records the sha256 of `O/power.json` | | |
| 5 | `J stage2` with stage 1's options, `--power O/power.json --power-sha256 <hex> --out O/judged` | The same, `power.json`, and **now** the captures and the planted runs | `record.json`, `retry_owed.json`, `verdict.json` |
| 6 | The lead records the sha256 of `retry_owed.json`. If `runs` is empty, there is no retry | | |
| 7 | `J hash --tables R --out O/hashes-retry.json` | The retry tables' bytes | `hashes-retry.json` |
| 8 | `J retry-stage1` with stage 1's options, `--power O/power.json --power-sha256 <hex> --record O/judged/record.json --owed O/judged/retry_owed.json --owed-sha256 <hex> --retry-tables R --retry-record O/hashes-retry.json --out O/power-retry.json` | Both folders of tables, the note, the first pass's files. **No capture** | `power-retry.json` |
| 9 | The lead records the sha256 of `O/power-retry.json` | | |
| 10 | `J retry-stage2` with those options, `--power-retry O/power-retry.json --power-retry-sha256 <hex> --out O/judged-retry` | The same, and the captures and the planted runs | `record.json`, `verdict.json` (final) |
| 11 | `J plants` with stage 1's options, `--out O/plants.json` (any time after 5) | The tables, the captures and the planted runs | `plants.json`: JP1 to JP24 on altered copies of the registered tables |

**Before the campaign:** `J selftest --out O/selftest.json` (C0, the fabricated tables, JP1 to JP24; about a minute), `J structure --tables <sample>/table --retry-tables <sample>/table-retry` (the format sample, TABLE section 7), and the tests:
`PYTHONPATH=src:. JAX_ENABLE_X64=1 /mnt/workspaces/Cells/venv-cpu/bin/python -m pytest -q -p no:cacheprovider validation/ensemble_reexpression/judge/test_judge.py` (159 rows, about 40 s of one core on a busy machine; they read the captures, compile nothing, and skip where no capture is).
**They were tried on faults of the code:** some ninety one-line changes of the judge's own code, each in a scratch copy, were run against them. Those that survived were either equivalent (a check that another one repeats) or led to a stronger test (§6).

`J fabricate --out O/fab` writes the honest tables of the judge's own with their `SHA256SUMS` and a strings note. They are marked as fabricated and no engine ran.

**What the record holds** (for the checker): every file's sha256 (tables, note, `c0.json`, `power.json`, the spec, every capture and planted file opened), every run's state with every cause and flag, every entry (consumer, family, run that owns it, readout, class, statistic, band, ratio, where it lies, d₁, d₂, q, the order's class, U_c, the planted distance, tested or not, the outcome), every plant (its registered distance, its band, its margin, its score),
the counts formed beside the expected and the published ones, the mechanisms and the first home that tests each, what the retry is owed, the steps that a pass covers, the four places where nothing is judged with what lies in each, and the verdicts with every reason. `base` has its two sets with their members. The entries of `base s0 pool` are marked.
A first pass's verdict is marked as not final where a retry is owed.

## 4. The readings

Where the text left something open, this is what the code does. **[ruled]** is the lead's ruling of 25 November (Amendment 2, which the criteria's author writes). The others are the judge's own.

1. **An extra entity [ruled]** (SPEC 2.4, "a key that `inputs.json` does not hold is recorded, and refuses nothing"): in the echoed `inputs` alone, a cell, region, membrane, channel, junction, face or species that the registered block does not have is a departing echo. So is an ID in `controls`, `switch_list` or `pool_seeds` that is no entity of the block, and an extra pool of a pool run. A key inside an entity stays recorded. **Extra series and keys elsewhere refuse nothing:** `phi_out` of `base`, a series of no world, an entity of a series that the world does not have, a key of an entry.
2. **JP14 [ruled]** shifts h₂ and not h₁, whose rows the restart is compared with.
3. **Not tested and inconclusive by order [ruled]** (CRITERIA 4.5, 8): it stays inconclusive by order and owes the retry. An untested entry that is unresolved or resolved and inside β counts for neither side.
4. **Plants [ruled]** (CRITERIA 6): one not caught and one unscorable entry make a plant not caught. A plant run that is refused with its rows there: caught becomes unscorable, not caught stays. A departing echo of a plant run, and EP2 whose switch list, schedule or seeds depart, is unscorable before the equality with the honest run is read.
5. **A retry run's class E entries [ruled]** are judged, and a miss fails (CRITERIA 7 names R and D). They are owned by the retry run and counted as expected.
6. **`variant` [ruled]** is flagged where it departs, and refuses nothing.
7. **A file that is not the contract's [ruled]** (TABLE 2): `kind`, `part`, `consumer`, `units`, `runs` or `missing` absent or departing refuses it whole.
8. **What C0 does not open [ruled]:** the independent scalar reference (SPEC 7) and the two outputs of `pool_plants`, which lie outside the planted folder. C0's record says so.
9. **No declaration [ruled, Amendment 2 item 7]:** a refused run with empty `inputs`, `strings` and `declared_strings` is a departing echo as well as a refusal, and nothing of it is judged.
10. **The off-grid switch** (Amendment 1, item 6): `off_grid: true` in a registered run's entry refuses it, kind `harness`, and its rows are judged. Absent or false is off.
11. **The printed margins of an assembly entry** (`margins.json`, "assembly: the smallest over the worlds of seed 0"): they are the smallest distance over the band with the largest U_l of the eight worlds. This forms every printed number at four digits. The smallest margin by world differs from it in the fourth digit at two entries, and C0 notes them. A margin decides nothing.
12. **The capacitor's times** (READOUTS 5): the potential times in `jupiter` and `integrated`, `summary_times_s` in `cell` and `base` ("the times of the identities"). Time 0 is not a separate test there.
13. **Partial runs** (CRITERIA 5, "judged on the rows it holds"): a run that is refused for any cause but its echo, or stopped, has its balances, its zeros and its restart entries formed on the compared times that it holds. A miss there is a fail. Without one, an entry that lacks a row is not formed, so nothing passes on fewer times. A run that is neither refused nor stopped follows "a missing or doubled row: not formed" to the letter.
14. **A refused pool run** whose path is a beginning of the reference path: its path and exposure are not formed. Any other difference is a fail.
15. **A stopped run that holds every row** has its S entries formed as well ("its rows are judged for R and E"). It fails by D in any case.
16. **D** (CRITERIA 4.4, 5) is not formed for a run that is refused without a stop. A `status` of completed beside a refusal of kind `check` is a stop.
17. **`steps`** is compared with its range for a completed run alone (a refused run has fewer by its nature). A missing or mistyped one is outside its range.
18. **A refusal that has no kind of the contract** is a status fault, and is read as `harness`.
19. **The copy guard** (CRITERIA 5) needs every class S row at every compared time in both, so a partial run is not compared. (a) compares judged runs and the retry's, (b) those and the plant runs. A support run is in neither, since it equals its judged run by its own criterion. In `base` the rows of `channel_K` at `summary_times_s` are among the class S rows.
20. **A run in two places.** Named in `runs` and in `missing`: judged and flagged. In another consumer's table: ignored there, and missing from its own.
21. **A shared `record_sha256`** is looked for over every entry of every table that is read, unlisted runs among them.
22. **Leaves that are lists by key** (`switch_list` by channel, `path` by world): a key that is left out is a missing leaf, so the entry is not formed, even where the list would be empty. **A channel left out of `controls.channel`** is the default schedule [[0, 1]] (SPEC 2.4), and fails where the path has a change.
23. **`initial_bond_indices`** left out on one side refuses nothing: its default needs the graph, which the judge does not have.
24. **A judged leaf** of a row is its value at a compared time. A bad value at another row is flagged. A list that is not as long as `t` is mistyped.
25. **A restart** whose `restart.time_s` is not the registered one has its entries not formed. Its path is compared at events strictly after that time. The support run's own seed is flagged where it departs, and is no entry (READOUTS 3 counts 20 per cell). A passing entry is flagged "restart to confirm": the checker confirms it, and the verdict stands only with that.
26. **A structural zero** is read at every row of the run, and needs every compared time.
27. **Power** reads the four-digit ratios of `margins.json` with max |L₃| at full precision. "2 U_c is the larger part of β" is 2 U_c > β − 2 U_c.
28. **The retry** (CRITERIA 7, "a refused or stopped run takes no retry"): a family of which any run is refused for any cause, missing or stopped takes none. An entry judged again is owned by the retry run, and a plant's named entry is scored with its last triple.
29. **The sets of `base`:** each set needs its own mechanisms tested by its own families. The pool runs, the support run and the plants count in both.
30. **An order-2 world** (the rehearsal): its balances, capacitor and energy identity are formed and reported, and not judged.
31. **An energy identity that is not finite on finite rows** (an amount at or below zero) is not formed. The entries that read the amount fail.
32. **Flagged and not refused:** another `cpu_model` than the captures', a first time that is not 0, an unsorted `declared_strings`, a recorded leaf that is missing, mistyped or not finite, a pool run's `t` or `rows` that is not empty.
33. **Empty strings** in `source` count as missing.
34. **A membrane without a pump [ruled]** in a world that has pumps (none is registered): `pump`, `heat_pump` and `work_pump` are read on the membranes that have one. Zero rows of the others are accepted, and a row of theirs that is not zero is flagged.
35. **A second pass [ruled, provisional]** (Amendment 2, item 7): `second_pass_completed: true` in the table's `refusal` is flagged to the checker and refuses nothing. Any other key of a `refusal` beyond the contract's three is flagged too.
36. **The format sample's** refused run without a declaration has empty `definition` and `checks` [ruled], and its refused runs all have empty `checks`. An empty one is flagged in a completed run alone.

## 5. The rehearsal's profile

A rehearsal is read with `--profile FILE` (and `--spec` the rehearsal's folder). The file has the keys of `PART1` in `registration.py`:

```json
{"names": {"inputs": "inputs_rehearsal.json", "legacy": "legacy_rehearsal.json", "paths": "reference_paths_rehearsal.json",
           "margins": "margins_rehearsal.json", "manifest": "plants_manifest_rehearsal.json"},
 "captures": {"inv_cluster": {"set": "captures", "kind": "windows", "folder": "runs/inv_cluster-{step}"},
              "inv_cell": {"set": "captures", "kind": "assembly", "folder": "runs/inv_cell-{step}-s{seed}", "summaries": "result"},
              "inv_pools": {"set": "captures", "kind": "assembly", "folder": "runs/inv_pools-{step}-s{seed}", "summaries": "ticks"}},
 "engine_plants": {"EP1": {"change": [], "named": ["channel_K"], "planted_run": "<a run of the plants manifest>",
                           "distance": {"world": "inv_cluster", "entry": "channel_K", "power_plant": "channel"}}},
 "not_blind": {}, "not_blind_pool_runs": [], "notes": {}, "counts": {}, "runs": 0,
 "off_grid_runs": ["<the one named run made with the switch on>"],
 "plant_targets": {"ionic": "<a family>", "other_schedule": "<a family of the same world, another schedule>", "junctions": "<a family>",
                   "restart": "<a support run>", "engine_plant": "<a plant run>", "pool": "<a pool run with no restart>",
                   "pool_path": ["<a pool run>", "<cell>", "<world ID whose last event changes nothing>"],
                   "not_blind": "<an assembly family>", "assembly": "<another assembly family>"}}
```

- **`captures`:** `{step}` is `h`, `h2` or `h4`, `{seed}` the seed index. `set` names a block of the legacy file that holds `root`, `science` and `science_manifest_sha256`, as `legacy_part1.json`'s do. That manifest's `files` gives every file's sha256. `cpu_model` is read from the block `captures`. `summaries` is `result` (`result.json`: `final_voltage_V` by world) or `ticks` (`observations/tick-<7 digits>.json` at 0 and at each of `summary_times_s`, with `cell_ids` and `channel_ids`).
- **`engine_plants`:** a plant run's `variant` is its key. `distance` is a power plant's ratio times the entry's `largest`, or `{"world", "entry", "structural": "<plant>"}`. `change` may stay empty where the run's `declared_change` holds it. Its `path` begins inside the ionic block.
- **`margins_rehearsal.json`** needs, per world, `entries.<readout>.ratio` for every class S entry, `mechanisms` with a home each, and `structural` (it may be empty) in `margins.json`'s form. `legacy_rehearsal.json` needs `captured_steps_s` per world. Its `entries` may be left out.
- **C0 leaves out, for a rehearsal,** what is Part 1's alone: the run list, the literal blocks, the captured definitions, the pins of the snapshot, the controls, the margins' re-formation, the mechanism list and the published numbers.
- **`judge_plants/`** (SPEC section 8): `fabricate --profile FILE --out <folder>` makes the honest tables from the rehearsal's `runs/`, always the same ones. None is committed, and the registered ones are made in the same way for `selftest`.
- **An ionic assembly world with more than one summary time** has an entry `channel_<x>_summary`, as `base` does.

## 6. What the judge's own plants say

On the honest fabricated tables (every registered run, 214): the four consumers pass, the eleven structural plants and both engine plants are caught, and JP1 to JP24 score as PLANTS section 6 states (JP14 as ruled, at h₂; as first written it did not, since the restart's class E entry failed by rule). This is evidence about the judge and none about a candidate.

**The format sample** (TABLE section 7; the lead's copy of 25 November, from b707a24d's tree) parses with no fault in the structure-only mode: the files and their sums by the registered reader, every key and type to the leaf, and the registered readers run on its rows, potentials, arrays, paths, schedules and block.
No number of it was used. TABLE, READOUTS and Amendment 1 were enough to read it, with Amendment 2's item 7 for a refused run without a declaration.

## 7. Not done

- The independent scalar reference and the pool plants' two outputs (reading 8). The author's runs of 25 November are the evidence for them.
- The snapshot of `integrated_capture` lies outside the captures' root. Its recorded manifest sha256 is compared, and no file of it is opened.
- What only the checker can do: that a restart reloaded a checkpoint, that the engine checked every accepted row, the fingerprint of the composed file, and that the off-grid switch was off.
- The rehearsal: its files did not exist when this was written. Its mode was run on the registered files under a profile alone.
- Part 2.
