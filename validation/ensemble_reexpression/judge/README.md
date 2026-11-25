# The judge of Part 1

**What it is.** The reader and the scorer of `spec/` (`ensemble-reexpression-v1`, Part 1), with Amendments 1 and 2 (`ensemble-reexpression-criteria-part1-amendment-2-2026-11-25`, c8fdf306). It imports nothing of the engine: the standard library and numpy.
It was written from the spec folder, the protocol, the captures and the planted legacy arrays alone. Its author has read no engine source, no test, no builder's branch, no candidate, and no table of a candidate. None existed. The builders' format sample (invented worlds, meaningless numbers) was read after the reader was written, and the rehearsal's tables (invented worlds too) after that (§6). No table of a registered run has been read.

## 1. Files

| File | What it does |
| --- | --- |
| `constants.py`, `strictjson.py` | The contract's names and numbers. JSON with duplicate keys refused, NaN and Infinity read |
| `registration.py` | The spec's data files as worlds, entries, families, runs, plants; the strings note; a rehearsal's profile |
| `legacy.py` | The captures and the planted runs. Every file is checked against a pinned sha256 before it is used |
| `rules.py` | The scales, `amount_refs` and closures by rule, from a world's block |
| `bands.py`, `identities.py` | The estimates, bands and order rule; the balances, the capacitor, the energy identity, the exposure |
| `table.py` | The tables: files, hashes, the echo, provenance, what a run is, what its rows hold |
| `settlements.py` | The settlements' file: what the checker settled (section 6) |
| `c0.py` | C0 |
| `scoring.py` | Stage 1 (power), stage 2 (scores, plants, the retry, verdicts) |
| `fabricate.py`, `plants.py` | The judge's own honest tables, and JP1 to JP27 |
| `structure.py` | The structure-only mode, for the format sample |
| `__main__.py`, `test_judge.py` | The commands, and the tests |

## 2. The method

- **Entries follow from the data.** A world's class S entries are its `scales` keys (but `energy_identity`, and a zero scale is a class E zero), over the times of READOUTS section 3. C0 checks that the counts are the published ones (`jupiter` 50, `cell` 480, `base` 800, `integrated` 9, and so on).
- **The captures** are read by READOUTS section 2's indices, in the order of the captured definition's lists, which C0 compares with the inputs'. Windows are joined with the earlier one owning the shared row.
- **A run** is first read for what it is (file, presence, echo, provenance, refusal or stop, copy guard), then for what its rows hold. A run whose echo stands is judged on what it holds, whatever else is wrong with it.
- **Stage 1** reads the tables' rows, the inputs, the strings note and C0's record. C0's record holds U_l and max |L₃|, so stage 1 opens no capture. It writes `power.json`: every entry's d₁, d₂, q, class, U_c, β with and without e_store, planted distance, whether it is tested, the mechanisms, and the copy guard's comparison (a).
- **Stage 2** starts only from `power.json`'s recorded sha256. It forms stage 1 again from the same tables and refuses unless the two are equal, value by value. Then it forms the differences.
- **A flag that the checker settles** (Amendment 2, item 5 (a) and readings 12 and 24) leaves its entries at best inconclusive. Section 6 says how it is settled. **Pending** is a state of a verdict: nothing but unsettled flags keeps it from a pass. It is written as `inconclusive`, with `state: pending`, and is never shown as a pass.
- **For the lead** the record lists what is an engine finding: a completed second pass of a stop (item 8 (a)), and how a support run that a check stopped differs on the rows that it holds (reading 13).
- **Nothing is overwritten.** Every output is a new file, and the command fails where it exists.

## 3. The commands of the campaign, in order

`J` is `nice taskset -c <cpus> /mnt/workspaces/Cells/venv-cpu/bin/python -m validation.ensemble_reexpression.judge`, from the checkout's root. `T` is the folder `table/`, `R` is `table-retry/`, `O` is a new output folder. Exit 0: done (for `c0`, `selftest`, `plants` and `structure`, without a fault). Exit 1: a fault. Exit 2: refused, out of order or a pinned file that changed.

| | Command | Opens | Writes |
| --- | --- | --- | --- |
| 1 | `J hash --tables T --out O/hashes.json` | The bytes of `T/table_*.json` and `T/SHA256SUMS`. Nothing is parsed | `hashes.json` |
| 2 | `J c0 --tables-record O/hashes.json --out O/c0.json` | The spec's data files and texts, the captures and the planted runs they name. **No table** (the record's bytes are hashed) | `c0.json` |
| 3 | `J stage1 --tables T --tables-record O/hashes.json --strings validation/ensemble_reexpression/registered_strings.json --c0 O/c0.json --out O/power.json` | The tables (which must be the recorded ones), the strings note, the spec's data files, `c0.json`. **No capture, no planted run** | `power.json` |
| 4 | The lead records the sha256 of `O/power.json` | | |
| 5 | `J stage2` with stage 1's options, `--power O/power.json --power-sha256 <hex> --out O/judged` | The same, `power.json`, and **now** the captures and the planted runs | `record.json`, `verdict.json`, and `retry_owed.json` unless a refusal by the copy guard waits for the checker (reading 28) |
| 5b | Where a flag or the copy guard's refusal is settled: `J stage2` again, with `--settlements FILE --settlements-sha256 <hex> --settled-record O/judged/record.json --out O/settled` | The same, and the settlements | The same three, and `retry_owed.json` once |
| 6 | The lead records the sha256 of `retry_owed.json`. If `runs` is empty, there is no retry | | |
| 7 | `J hash --tables R --out O/hashes-retry.json` | The retry tables' bytes | `hashes-retry.json` |
| 8 | `J retry-stage1` with stage 1's options, `--power O/power.json --power-sha256 <hex> --record O/judged/record.json --owed O/judged/retry_owed.json --owed-sha256 <hex> --retry-tables R --retry-record O/hashes-retry.json --out O/power-retry.json` | Both folders of tables, the note, the first pass's files. **No capture** | `power-retry.json` |
| 9 | The lead records the sha256 of `O/power-retry.json` | | |
| 10 | `J retry-stage2` with those options, `--power-retry O/power-retry.json --power-retry-sha256 <hex> --out O/judged-retry`, and the three options of 5b where something is settled | The same, and the captures and the planted runs | `record.json`, `verdict.json` (final) |
| 11 | `J plants` with stage 1's options, `--out O/plants.json` (any time after 5), and `--retry-tables R --retry-record O/hashes-retry.json` where there is a retry | The tables, the captures and the planted runs | `plants.json`: JP1 to JP27 on altered copies of the registered tables. JP26 needs a retry run of `integrated`, and is not formed without one |

**Before the campaign:** `J selftest --out O/selftest.json` (C0, the fabricated tables, JP1 to JP27; about a minute), `J structure --tables <sample>/table --retry-tables <sample>/table-retry` (the format sample, TABLE section 7), and the tests:
`PYTHONPATH=src:. JAX_ENABLE_X64=1 /mnt/workspaces/Cells/venv-cpu/bin/python -m pytest -q -p no:cacheprovider validation/ensemble_reexpression/judge/test_judge.py` (225 rows, about 60 s of one idle core and twice that on a busy machine; they read the captures, compile nothing, and skip where no capture is).
**They were tried on faults of the code:** some hundred one-line changes of the judge's own code, each in a scratch copy, were run against them. Eight survived at first: one was equivalent (a check that another one repeats), and the others led to stronger tests. Amendment 2's code was tried in the same way, with the outcome in section 9. **And on faults of a table:** two thousand random faults of a leaf raised nothing in the stages, and no judged leaf changed unseen.

`J fabricate --out O/fab` writes the honest tables of the judge's own with their `SHA256SUMS` and a strings note. They are marked as fabricated and no engine ran. None is kept (Amendment 2, item 9.5): the program gives the same bytes each time, each table says that it is fabricated, and `selftest` records the sha256 of each table as it was made and used.

**What the record holds** (for the checker): every file's sha256 (tables, note, `c0.json`, `power.json`, the spec, every capture and planted file opened), every run's state with every cause and flag, every entry (consumer, family, run that owns it, readout, class, statistic, band, ratio, where it lies, d₁, d₂, q, the order's class, U_c, the planted distance, tested or not, the outcome), every plant (its registered distance, its band, its margin, its score),
the counts formed beside the expected and the published ones, the mechanisms and the first home that tests each, what the retry is owed, the steps that a pass covers, the four places where nothing is judged with what lies in each, and the verdicts with every reason. `base` has its two sets with their members. The entries of `base s0 pool` are marked.
A first pass's verdict is marked as not final where a retry is owed.

## 4. The readings

Where the text left something open, this is what the code does. **[ruled]** is the lead's ruling, which Amendment 2 now has in its own words (items 1 to 5, 7 and 8). The others are the judge's own, which Amendment 2 (item 9) read one by one: all are confirmed but **14, 16 and 20, and 13 in one case, which are corrected here.** The readings 37 to 41 are later than its list. Section 9 gives every item and every reading beside the code.

1. **An extra entity [ruled, item 2]** (SPEC 2.4, "a key that `inputs.json` does not hold is recorded, and refuses nothing"): in the echoed `inputs` alone, a cell, region, membrane, channel, junction, face or species that the registered block does not have is a departing echo. So is an ID in `controls`, `switch_list` or `pool_seeds` that the block's own set of that kind does not hold (and not one that the block's `controls` leave out), and an extra pool of a pool run. A key inside an entity stays recorded. **Extra series and keys elsewhere refuse nothing:** `phi_out` of `base`, a series of no world, an entity of a series that the world does not have, a key of an entry.
2. **JP14 [ruled, item 1]** shifts h₂ and not h₁, whose rows the restart is compared with.
3. **Not tested and inconclusive by order [ruled, item 5 (a)]** (CRITERIA 4.5, 8): it stays inconclusive by order and owes the retry. One that is resolved outside its window and above β is flagged with its error, and what the retry's triple gives is at best inconclusive until the checker settles the flag. An untested entry that is unresolved or resolved and inside β counts for neither side.
4. **Plants [ruled, items 5 (b) to (d)]** (CRITERIA 6): one not caught and one unscorable entry make a plant not caught. A plant run that is refused with its rows there: caught becomes unscorable, not caught stays. A departing echo of a plant run, and EP2 whose switch list, schedule or seeds depart, is unscorable before the equality with the honest run is read.
5. **A retry run's class E entries [ruled, item 3]** are judged, and a miss fails (CRITERIA 7 names R and D). They are owned by the retry run and counted as expected.
6. **`variant` [ruled, item 5 (e)]** is flagged where it departs, and refuses nothing.
7. **A file that is not the contract's [ruled, item 4]** (TABLE 2): `kind`, `part`, `consumer`, `units`, `runs` or `missing` absent or departing refuses it whole.
8. **What C0 does not open (item 5 (f), in place of the withdrawn ruling):** it pins three files by their sha256 alone: the scalar reference's script (SPEC 7) at 49529e71, from the checkout and from the repository's objects, and the two outputs of `pool_plants`, where the manifest says they are. An absent one, or another sha256, is a C0 fault. C0 runs no scalar reference, and does not re-form the counts of `margins.json` `pool_plants`.
9. **No declaration [ruled, item 7 (c)]:** a refused run with empty `inputs`, `strings` and `declared_strings` is a departing echo as well as a refusal, and nothing of it is judged.
10. **The off-grid switch** (Amendment 1, item 6, and 9.1): `off_grid: true` in a registered run's entry refuses it, kind `harness`, and its rows are judged. Absent or false is off. D is not formed (reading 16).
11. **The printed margins of an assembly entry** (`margins.json`, "assembly: the smallest over the worlds of seed 0"): they are the smallest distance over the band with the largest U_l of the eight worlds. This forms every printed number at four digits. The smallest margin by world differs from it in the fourth digit at two entries, and C0 notes them. A margin decides nothing.
12. **The capacitor's times** (READOUTS 5): the potential times in `jupiter` and `integrated`, `summary_times_s` in `cell` and `base` ("the times of the identities"). Time 0 is not a separate test there. So a row of `n_cell_x` at time 0 that is not zero is flagged, and the run's capacitor is at best inconclusive until the checker settles the flag.
13. **Partial runs** (CRITERIA 5, "judged on the rows it holds"): a run that is refused for any cause but its echo, or stopped, has its balances, its zeros and its restart entries formed on the compared times that it holds. A miss there is a fail. Without one, an entry that lacks a row is not formed, so nothing passes on fewer times. A run that is neither refused nor stopped follows "a missing or doubled row: not formed" to the letter. **Corrected for a support run that a check stopped:** its rows are another path's (item 8 (b)), so its restart entries are not formed, and the differences on the rows that it holds go to the checker and to the lead. A pool's restart too.
14. **A refused pool run, corrected:** where its `status` is `refused` its path, its exposure and its 19 arrays are not formed, since the refusal cut the path. Any other difference of the path is a fail. A run whose `status` is `completed`, and which is refused for its provenance, holds its whole path: there a path that ends early fails. A pool's restart is read in the same way, where either run is cut (the judge's own extension of the same reason).
15. **A stopped run that holds every row** has its S entries formed as well ("its rows are judged for R and E"), and the record marks each as formed on a stopped run's rows. It fails by D in any case.
16. **D, corrected** (CRITERIA 4.4, 5): not formed for a refusal of kind `definition`, `domain` or `harness`. For a run that is refused for its provenance, by the copy guard or for two lists it is formed: it passes if the run completed, and fails on a stop. A `status` of completed beside a refusal of kind `check` is a stop. A run of which neither holds (a `status` of refused and no refusal) has no D.
17. **`steps`** is compared with its range for a completed run alone (a refused run has fewer by its nature). A missing or mistyped one is outside its range.
18. **A refusal that has no kind of the contract** is a status fault, and is read as `harness`.
19. **The copy guard** (CRITERIA 5) needs every class S row at every compared time in both, so a partial run is not compared. (a) compares judged runs and the retry's, (b) those and the plant runs. A support run is in neither, since it equals its judged run by its own criterion. In `base` the rows of `channel_K` at `summary_times_s` are among the class S rows.
20. **A run in two places, corrected.** Named in `runs` and in `missing`: refused, its readouts judged, and a fail stands. In another consumer's table: ignored there, and missing from its own.
21. **A shared `record_sha256`** is looked for over every entry of every table that is read, unlisted runs among them.
22. **Leaves that are lists by key** (`switch_list` by channel, `path` by world): a key that is left out is a missing leaf, so the entry is not formed, even where the list would be empty. **A channel left out of `controls.channel`** is the default schedule [[0, 1]] (SPEC 2.4), and fails where the path has a change.
23. **`initial_bond_indices`** left out on one side refuses nothing: its default needs the graph, which the judge does not have.
24. **A judged leaf** of a row is its value at a compared time. A value that is no finite number at another row of a judged series is flagged, and every judged entry that reads that series of that run is at best inconclusive until the checker settles the flag: the S entries of its family that use the run, its own balances and capacitor, and the E entries of a restart of it or by it. A recorded leaf's flag stays plain. A list that is not as long as `t` is mistyped. A plant run owns no entry, so its flag is plain.
25. **A restart** whose `restart.time_s` is not the registered one has its entries not formed. Its path is compared at events strictly after that time. The support run's own seed is flagged where it departs, and is no entry (READOUTS 3 counts 20 per cell). A passing entry is flagged "restart to confirm": the checker confirms it, and the verdict stands only with that.
26. **A structural zero** is read at every row of the run, and needs every compared time.
27. **Power** reads the four-digit ratios of `margins.json` with max |L₃| at full precision. "2 U_c is the larger part of β" is 2 U_c > β − 2 U_c.
28. **The retry** (CRITERIA 7, "a refused or stopped run takes no retry"): a family of which any run is refused for any cause, missing or stopped takes none. An entry judged again is owned by the retry run, and a plant's named entry is scored with the band and the Y* of its last triple. `retry_owed.json` is written once, and after the copy guard's refusals are settled (section 6). A run whose refusal the lead's note has lifted is no refused run.
29. **The sets of `base`:** each set needs its own mechanisms tested by its own families. The pool runs, their support run and the plants count in both. A restart of an ionic run, and its entries, are of the set that holds the family of the run that it is compared with (Part 1 registers no such restart in `base`. The rehearsal has one).
30. **An order-2 world** (the rehearsal): its balances, capacitor and energy identity are formed and reported, and not judged.
31. **An energy identity that is not finite on finite rows** (an amount at or below zero) is not formed. The entries that read the amount fail.
32. **Flagged and not refused:** another `cpu_model` than the captures', a first time that is not 0, an unsorted `declared_strings`, a recorded leaf that is missing, mistyped or not finite, a pool run's `t` or `rows` that is not empty.
33. **Empty strings** in `source` count as missing.
34. **A membrane without a pump [ruled, item 8 (d)]** in a world that has pumps (none is registered): `pump`, `heat_pump` and `work_pump` are read on the membranes that have one. Zero rows of the others are accepted, and a row of theirs that is not zero is flagged.
35. **A second pass [ruled, item 8 (a)]:** `second_pass_completed: true` of a `check` refusal is flagged to the checker, and is named for the lead: the run stays refused. The key on anything else, or with another value, is flagged. Any other key of a `refusal` beyond the contract's three is flagged too.
36. **The format sample's** refused run without a declaration has empty `definition` and `checks` [ruled, item 8 (c)], and its refused runs all have empty `checks` (9.1). An empty one is flagged in a completed run alone.
37. **A world of one run** (the rehearsal's `inv_offgrid`, `inv_stop`): C0 forms its classes, identities and padding from its captured runs, as for a family. No other run is needed for that.
38. **A printed observed order** is the judge's at two decimals (`legacy_part1.json`). In a rehearsal three digits are accepted too (`legacy_rehearsal.json` prints them).
39. **A printed `largest` of an assembly entry** is the smallest over the worlds (Part 1) or the value of the world with the smallest margin (the rehearsal's file, nine entries). C0 accepts the second, notes it, and judges nothing by it.
40. **A judge's plant's claim on a consumer's verdict** is not made where the consumer's honest verdict is not a pass, as the rehearsal's `integrated` is, by its designed faults. The plant's other claims are judged.
41. **The rehearsal's two honest families with one constant schedule** (`inv_cell s0 w2`, `s1 w0`) are equal in every row, and the copy guard does not refuse them (CRITERIA 5: families are not compared with each other).

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
 "not_blind": {"<consumer>": ["<a family>"]}, "not_blind_pool_runs": ["<a pool run>"], "notes": {}, "counts": {}, "runs": 0,
 "off_grid_runs": ["<the one named run made with the switch on>"], "off_grid_flag": "off_grid",
 "declared_change_begins_at": "ionic",
 "plant_targets": {"ionic": "<a family>", "other_schedule": "<a family of the same world, another schedule>", "junctions": "<a family>",
                   "restart": "<a support run>", "engine_plant": "<a plant run>", "pool": "<a pool run with no restart>",
                   "pool_path": ["<a pool run>", "<cell>", "<world ID whose last event changes nothing>"],
                   "not_blind": "<an assembly family>", "assembly": "<another assembly family>"}}
```

- **`captures`:** `{step}` is `h`, `h2` or `h4`, `{seed}` the seed index. `set` names a block of the legacy file that holds `root`, `science` and `science_manifest_sha256`, as `legacy_part1.json`'s do. That manifest's `files` gives every file's sha256. `cpu_model` is read from the block `captures`. `summaries` is `result` (`result.json`: `final_voltage_V` by world) or `ticks` (`observations/tick-<7 digits>.json` at 0 and at each of `summary_times_s`, with `cell_ids` and `channel_ids`).
- **`engine_plants`:** a plant run's `variant` is its key, its `family` the honest family that it was planted in, its step that family's h₃. `planted_run` is a run of the plants manifest that makes the same change on the legacy side. `distance` is a power plant's ratio times the entry's `largest`, or `{"world", "entry", "structural": "<plant>"}`.
  A run's own `declared_change` is used where it has one, and `change` otherwise. Their items are `{"path": [...], "value": v}` or `{"path": [...], "multiply": f}`, the path inside the ionic block and `"*"` for every key of a map, or `{"exchange_channels": [cell, cell]}`.
- **`off_grid_flag` and `declared_change_begins_at`** are the two that Amendment 2, item 6 adds: the key of the switch in a run's entry, and what a `declared_change` path begins at (the world's ionic block). The registered runs have no profile, so they are the names of 9.1 and Amendment 1. Left out, they are these.
- **`not_blind`** may be empty (`{}`): the consumer then has one set. `plant_targets.not_blind` is one of its families where it has some, and `plant_targets.assembly` is a family that is not among them.
- **`margins_rehearsal.json`** needs, per world, `entries.<readout>.ratio` for every class S entry, `mechanisms` with a home each, and `structural` (it may be empty) in `margins.json`'s form. `legacy_rehearsal.json` needs `captured_steps_s` per world. Its `entries` may be left out.
- **C0 leaves out, for a rehearsal,** what is Part 1's alone: the keys of the data files, the run list, the literal blocks, the captured definitions, the pins of the snapshot and the published numbers. It forms everything else (17 clauses), the controls, the margins and the mechanisms among them.
- **`judge_plants/`** (SPEC section 8): `fabricate --profile FILE --out <folder>` makes the honest tables from the rehearsal's `runs/`, always the same ones. None is committed, and the registered ones are made in the same way for `selftest`.
- **An ionic assembly world with more than one summary time** has an entry `channel_<x>_summary`, as `base` does.

## 6. Settlements

A flag that the checker settles, and a refusal by the copy guard, are listed in `record.json` and in `verdict.json` (`flags_to_settle`, each with its `id`, and `copy_guard`). The settlement's record is one JSON file, which stage 2 and the retry's stage 2 read by its recorded sha256, beside the record that it settles. A change of it is a new file.

```json
{"kind": "ensemble-reexpression settlements, version 1", "protocol": "ensemble-reexpression-v1", "part": 1,
 "flags": [
  {"flag": "<the flag's id, as the record has it>", "record_sha256": "<the record.json in which it stands>",
   "counts_as": "by the rule" or "fail" or "inconclusive",
   "checker": "<who>", "when": "<UTC, 2026-11-26T09:00:00Z>", "words": "<what was found, and why it counts so>", "evidence": ["<a path or a command>"]}],
 "copy_guard": [
  {"run": "<run>", "comparison": "a" or "b", "record_sha256": "<as above>", "outcome": "stands" or "lifted",
   "checker": "<who>", "when": "<UTC>", "words": "<what the rerun showed>", "evidence": [],
   "lead_note": null, or for a lifted one {"path": "", "sha256": "", "date": "", "words": ""}}]}
```

- **Every key is required, and no other is accepted.** A flag that the record does not hold, one settled twice, a time that is no UTC time, empty words and a record of other files are refused, and nothing is scored.
- **`counts_as`** is what the flag counts as. `by the rule` is the outcome that the entry has without the flag, so a fail by the rule stays a fail and "not tested" stays so. `fail` fails it, whatever it was. `inconclusive` leaves it inconclusive for good. An entry with several flags takes the worst of what is said.
- **Until it is settled** the entry is inconclusive, and its record has `by_rule` and `pending`. A run and a consumer list their pending flags, and the verdict's `state` is `pending` where nothing else keeps it from a pass.
- **The corner of item 5 (a)** has its flag in the first pass, and is settled for the retry's triple. In the first pass it stays inconclusive by order, and owes the retry whatever is said. Without a retry it stays inconclusive.
- **A refusal by the copy guard** that is lifted needs the lead's dated note (its path, its sha256, its date, its words). `stands` leaves the run refused. Either ends the wait for `retry_owed.json`.
- **The ids** are `<kind>; <the run, or the family of a corner>; <the series or the readout>`, with the kinds `row at time 0`, `non-finite value` and `untested outside its window`.
- **Nothing is settled by "restart to confirm"** (reading 25): the judge flags it and counts the entry, as the text has it, and the checker's word stands beside the verdict.

## 7. What the judge's own plants say

On the honest fabricated tables (every registered run, 214): the four consumers pass, the eleven structural plants and both engine plants are caught, and JP1 to JP27 score as PLANTS section 6 and Amendment 2 state (JP14 at h₂; as first written it did not, since the restart's class E entry failed by rule). Beside what a plant names, the record lists what fails by the rule: the restart's entry of `leak_K`, `heat_membrane`, `heat_junction` and `junction_K` (JP1, JP2, JP7 and JP19), and the region's balance of Na (JP26). This is evidence about the judge and none about a candidate.

**The format sample** (TABLE section 7; the lead's copy of 25 November, from b707a24d's tree) parses with no fault in the structure-only mode: the files and their sums by the registered reader, every key and type to the leaf, and the registered readers run on its rows, potentials, arrays, paths, schedules and block.
No number of it was used. TABLE, READOUTS and Amendment 1 were enough to read it, with Amendment 2's item 7 for a refused run without a declaration.

## 8. The rehearsal, 25 November

The path was run as in the campaign on the rehearsal's tables (invented worlds, 94 runs, engine revision cf6ed9e1) with `--spec` and `--profile`: hash, C0, stage 1 and its sha256, stage 2, the plants. It was run again at the committed heads: the hash record, C0, power, the retry list and the plants' scores are the same files, and the record and the verdict differ in one label alone (a judged run without a family was listed as a pool run).

- **C0** (rehearsal mode) passes in all 17 clauses (18 since Amendment 2, `counts` with nothing to check).
- **Verdicts:** `jupiter` pass, `cell` pass, `base` pass in both sets, `integrated` fail. The last fails by design: `inv_stop` is stopped by the engine's own check, and its D fails. Nothing else of any consumer fails. What is not formed is of `inv_stop` and of the three refused runs.
- **No honest run misses a bound.** The largest class S ratio is 8.6 × 10⁻³ (the order-2 family), 2.1 × 10⁻³ in an order-4 family (`inv_cross` `gate_m`). The largest class R ratio is 2.9 × 10⁻⁴ (an exposure, and 2.5 × 10⁻⁵ in a balance), and the largest energy ratio 1.6 × 10⁻⁷. Two non-home entries of `inv_cross` (`n_cell_K`, `n_out_Cl`) are not tested. No retry is owed.
- **Plants:** the four engine plants (margins 5.8 × 10⁶ to 2.4 × 10⁸) and the eleven structural plants are caught. JP1 to JP24 score as stated (25 rows). The claim on the consumer's verdict is not made for `integrated` (reading 40).
- **After Amendment 2** it was scored again, on the same tables and on a second set (engine revision c1a2dc34, every row the same double). Against the scoring at dddbdd1c the first set's outputs differ in keys that did not exist then (`state`, `pending`, `flags_to_settle`, `copy_guard`, `for_the_lead`, `runs_pending_on_a_flag`, `retry_owed_waits_on`), in C0's clause and notes on what it pins, in the plants' lists and in the hashes. No entry, run, flag or outcome moved: the corrected readings meet no run of these tables. The second set's outputs differ from the first's in hashes, and in the harness-refused run, whose `source` the builder completed (five causes and one flag fewer). **No honest run of either set is pending on a flag.** JP1 to JP25 and JP27 score as stated, and JP26 is not formed, since there is no retry run.
- **An independent script** (numpy and json alone, nothing of the judge imported) recomputed from the tables, the rehearsal's runs and the spec: the 505 class S entries, 481 planted distances and whether each is tested, 730 balances and capacitors, 6 exposures, 114 pool arrays, 248 paths, switch lists, schedules and seeds, 11400 values of the restarts and 42 series of zeros. It agrees with the record. The energy identities agree in class and outcome, and some of them differ from it by about 10⁻¹⁵ in a value, by the order of the sums. It did not cover C0, the judge's plants, the engine's plants' scores, the mechanisms, or the partial rows of `inv_stop`.
- **Four defects of the judge's own** were found by the rehearsal, before any registered run, and each has a test that fails without its fix: C0 stopped at a world that has captures and no family of three, C0 compared a printed order at two decimals alone, a restart counted in both sets of `base`, and JP10 asked for a whole K amount of an outside region, where the rehearsal's world has it in a cell. No rule, band or class changed, and the registered plant is the same.

## 9. Amendment 2, item by item

Every item and every reading of `spec/AMENDMENT-2-2026-11-25.md`, against the code of `dddbdd1c` (before) and of the head that this file belongs to (now). A number from 10 to 36 in the first column is a reading of section 4. A row of the last column is a test of `test_judge.py`, a row of one of its tables (in capitals), or a judge's plant. Readings 24 and 28 are in the amendment's list of what is weaker, with 12, 13, 14, 19 and 25.

| Item or reading | The sentence | Before | Now | The row that shows it |
| --- | --- | --- | --- | --- |
| 1 | JP14 alters h₂ | Was so, by the ruling | The same | JP14 |
| 1 | JP1, JP2, JP7 and JP19 alter h₁ too: the restart's entries fail besides, by rule, and are listed as expected | The plants were scored at what they name. What else failed was not listed, and not checked | Each lists what fails besides by rule, and checks that nothing else fails | JP1, JP2, JP7, JP19 |
| 1 | A judge's plant that the code scores otherwise stops the judge's tag | `plants` and `selftest` end with 1 | The same | Exit 1 of both commands |
| 2 | An entity that the block does not have is a departing echo: cells, regions, membranes, channels, junctions, faces, species, a pool run's cells | Was so | The same | `ECHO` (an extra cell, region, membrane, channel, junction, species), `ECHO_BASE` (a face), `test_pool_runs_echo_and_seed_provenance` (a pool run's cell), JP25 (face) |
| 2 | An ID in `controls`, `switch_list` or `pool_seeds` is extra where the block's own set of that kind does not hold it, and not where the block's `controls` leave it out | Was so: the set is the block's, and a default schedule written out is recorded | The same | `ECHO_BASE` (five, and a written-out default), `ECHO` (a schedule of no entity), `NO_FAULT` (a default schedule written out) |
| 2 | A key inside an entity, an extra series, an extra key of an entry refuse nothing | Was so | The same | JP25 (key), `test_extra_series_and_keys_refuse_nothing` |
| 3 | The retry run's own R, D and E entries are judged, it owns them, and the expected E entries grow | Was so, by the ruling | The same | `test_the_retry`, JP26 |
| 4 | A file of which one of six keys is absent or departs is refused whole, and named in the verdict | Was so for the six. An extra top-level key was not recorded | The same, and an extra top-level key is recorded (TABLE's head) | `test_files_that_are_refused_whole` (nine cases of the six keys), JP27 |
| 5 (a) | Not tested and inconclusive by order stays so, and owes the retry | Was so | The same | `test_the_corner_of_the_order_rule_is_flagged_and_the_retry_waits` |
| 5 (a) | Untested, outside its window and above β: flagged with its error, and the retry's triple is at best inconclusive until it is settled. Without a retry it stays inconclusive | It was inconclusive by order and owed the retry. It was not flagged, and the retry's triple decided alone | Flagged (`flags_to_settle`), and pending after the retry | The same test, with three settlements before and after the retry |
| 5 (b) | Any not caught entry makes a plant not caught | Was so | The same | `test_a_plant_s_worst_entry_decides` |
| 5 (c) | A plant's own run that is refused with its rows there: caught becomes unscorable, not caught stays | Was so | The same | `PLANT` (EP1 refused and caught, EP1 refused and equal) |
| 5 (d) | A plant's run with a departing echo is unscorable before its equality is read. EP2 with a departing switch list, schedule or seeds is among them | Was so | The same | `PLANT` (EP1 without its change, the same and equal, EP2 not swapped, EP2 with other seeds) |
| 5 (e) | `variant` is flagged, and refuses nothing | Was so | The same | `NO_FAULT` (variant) |
| 5 (f) | C0 pins three files by their sha256 alone, opens none, and an absent or another one is a fault | Nothing was hashed, by the withdrawn ruling | The clause `pinned_files`, and `pinned_by_sha256_alone` in the record | `test_C0_pins_three_files_and_opens_none_of_them` |
| 5 (f) | C0 does not run the scalar reference, and the counts of `margins.json` `pool_plants` are not re-formed | Was so | The same, in the record's `not_done` | The same test |
| 6 | The profile holds the folder pattern, the plants' distances, what a `declared_change` path begins at, and the switch's flag | The first two were in its shape. The last two were constants of the code | Two keys of the shape, with the amendment's values as defaults. The present rehearsal profile holds neither | `test_the_profile_names_the_switch_and_where_a_change_begins` |
| 7 (a) | `closure` and `maintained_fuel` stand among `laws`, and a pool run's `model` is the pool's own | Was so: the note's labels are read as they are listed | The same | The honest tables (the fabricated note), `ECHO` (a missing, an extra label) |
| 7 (b) | `time_s` of a `check` refusal is the first refused row's, and the run's end for a pool or a second pass that completes | A `time_s` that is no number for `check`, or a number otherwise, is flagged | The same. No value of it is judged | None: it is recorded |
| 7 (c) | Without a declaration `inputs`, `strings` and `declared_strings` are empty: refused, and a departing echo | Was so | The same | `test_a_refused_run_that_has_no_declaration` |
| 7 (d) | `pending_valid` is written as JSON booleans, and it is the only array of that type | A boolean was read in any array, and an integer in `pending_valid` | A boolean elsewhere, or a number there, is mistyped: not formed. The structure-only mode says so too | `POOL_FORM` (two), `test_structure_only` |
| 7 (e) | The two legs of a pool restart | The exporter's | The same | None |
| 8 (a) | A completed second pass: the key is there only then. Flagged, refuses nothing, and an engine finding for the lead | Flagged to the checker alone | And named in `for_the_lead`. The key on another refusal, or with another value, is flagged | `test_extra_series_and_keys_refuse_nothing` (three) |
| 8 (b) | The rows of every `check`-refused run are the second pass's | Nothing read it | Readings 13 and 15 | Below |
| 8 (c) | A refused run without a declaration may have an empty `definition` and `checks` | Was so | The same | `test_a_refused_run_that_has_no_declaration`, and `checks: {}` of three refused kinds |
| 8 (d) | A membrane without a pump | Was so | The same | `test_extra_series_and_keys_refuse_nothing` (pumps) |
| 9.1 | Every channel a key of `switch_list`, every world of `path`: a key left out is a missing leaf | Was so | The same | `POOL_FORM` (a path's world, a switch list's channel) |
| 9.1 | A channel that `controls.channel` leaves out is [[0, 1]] | Was so | The same | `POOLS` (a schedule left out) |
| 9.1, 10 | `off_grid` true in a registered run refuses it, kind `harness`, its rows judged. Absent or false is off | Was so, and its D was formed and passed | D is not formed | `test_the_off_grid_switch_refuses_a_registered_run`, `NO_FAULT` (off_grid false) |
| 9.1, 20 | Named in `runs` and in `missing`: refused, with its readouts judged | Judged and flagged, and it could pass | Refused, its D formed, a fail stands | `test_a_run_that_is_named_in_both_lists_is_refused` |
| 9.1, 33 | An empty string in `source` counts as missing | Was so | The same | `PROVENANCE` (a missing snapshot, source incomplete) |
| 9.1, 36 | The `checks` of any refused run may be empty | Was so | The same | `checks: {}` in the rows on refused runs |
| 11 | The printed margins of an assembly entry | C0 forms them with the largest U_l of the eight worlds, and notes two entries | The same, and the note is no fault (9.4) | `C0_FAULT` (a printed margin) |
| 12 | A row of `n_cell_x` at time 0 that is not zero is flagged, and the run's capacitor is at best inconclusive until it is settled | Nothing was seen of that row | Flagged (`flags_to_settle`), pending | `FLAGS` (reading 12) with three settlements, `test_what_a_flag_does_not_touch` |
| 13 | A partial run is formed on the times that it holds, and a miss is a fail | Was so | The same | `test_a_refused_run_is_judged_on_the_rows_it_holds`, `test_a_restart_equals_the_uninterrupted_run` |
| 13 | A support run that a check stopped: its restart entries are not formed, and the differences go to the checker and to the lead | They were formed on the rows that it holds, and a difference failed | Not formed, and the differences are in `flags` and in `for_the_lead`. A pool's restart too | `test_a_restart_that_a_check_stopped_is_not_formed` |
| 14 | A refused pool run: its path, its exposure and its 19 arrays are not formed where its `status` is refused. Any other difference of the path fails. Completed and refused for its provenance: a short path fails | The arrays and a whole path were formed, and a short path was not formed for a refusal of any cause | As the sentence. And a pool's restart, where either run is cut (the judge's extension of the same reason) | `test_a_refused_pool_run_is_judged_on_the_events_it_holds` |
| 15 | The S entries of a stopped run are marked as formed on its rows | They were formed and not marked | `on_a_stopped_runs_rows` | `test_the_rows_of_a_stopped_run_are_marked` |
| 16 | D is not formed for a refusal of kind `definition`, `domain` or `harness`, and is formed for provenance and the copy guard | So in the code, though its words were wider. But a registered run with the switch on (kind `harness`) had its D formed | As the sentence | `PROVENANCE` (every row), `test_the_off_grid_switch_refuses_a_registered_run` |
| 17 | `steps` of a refused run is not compared | Was so | The same | `test_a_refused_run_is_judged_on_the_rows_it_holds` (steps 49) |
| 18 | A refusal of no kind of the contract is read as `harness` | Was so | The same | `PROVENANCE` (a refusal of no kind) |
| 19 | A partial run is not compared by the copy guard | Was so | The same | `test_the_retry_list_waits_for_the_copy_guard` (partly) |
| 21 | A shared `record_sha256`: an unlisted run counts | Was so | The same | `test_runs_that_are_not_registered_are_ignored` |
| 22 | Leaves that are lists by key | Was so | The same | `POOL_FORM` |
| 23 | `initial_bond_indices` left out on one side | Was so | The same | `test_pool_runs_echo_and_seed_provenance` |
| 24 | A value of a judged series that is not finite at another time is flagged, and the run's entries of that series are at best inconclusive until it is settled | Flagged plainly, and nothing waited | Flagged (`flags_to_settle`), pending. An entry that reads the series of that run is among them, whoever owns it | `FLAGS` (five rows of reading 24) with three settlements each |
| 25 | A restart at another time is not formed, its path is read strictly after it, its seed is flagged. A passing entry waits for the checker | Was so | The same | `test_a_restart_equals_the_uninterrupted_run` |
| 26 | A structural zero: every row, and every compared time | Was so | The same | `test_structural_zeros` |
| 27 | Power takes ρ as printed. The larger part of β is more than half of it | Was so | The same | `test_power_is_read_from_the_margins` |
| 28 | A family with a refused, missing or stopped run takes no retry | Was so | The same | `test_a_refused_run_takes_no_retry` |
| 28 | `retry_owed.json` is written once. A refusal by the copy guard is settled before it is written, and one that the lead's note has lifted is no refusal | It was written at once, with the refusals standing | Not written while one waits. A lifted one refuses nothing | `test_the_retry_list_waits_for_the_copy_guard` |
| 28 | An entry judged again is owned by the retry run, and a plant is scored with the band and the Y* of its last triple | Was so | The same | `test_the_retry` |
| 29 | Each set of `base` needs its own mechanisms tested | Was so | The same | JP15, JP16 |
| 30 | An order-2 world's identities are reported | Was so | The same | `test_an_order_two_world_reports_its_identities` |
| 31 | An energy identity that is not finite is not formed, and no fail is hidden | Was so | The same | `test_an_amount_below_zero_leaves_the_identity_not_formed` |
| 32 | What is flagged and not refused | Was so | The same | `NO_FAULT` (another machine, a missing record, no definition) |
| 34, 35 | A membrane without a pump; a second pass | Items 8 (d) and 8 (a) | Items 8 (d) and 8 (a) | Above |
| 9.4 | C0's two notes: the margins (reading 11), and the published ratio of the energy identity | C0 checks neither | The same. No bound rests on them | None |
| 9.5 | The judge makes its honest tables on demand. The same bytes each time, each says that it is fabricated, and the record holds the sha256 of each as it was made and used | The program and the mark were there. `selftest` held a digest of another form of the tables | `selftest` holds the sha256 of the bytes that `fabricate` writes, and of the retry's | `test_the_fabricated_tables_are_the_same_bytes_each_time` |
| 10 | The extra-entity rule is Part 1's alone | Part 1's code | The same | None |
| 11 | JP25, JP26 and JP27 | None was there | All three. JP26 is not formed without a retry run of `integrated` | JP25 (face), JP25 (key), JP26, JP27 |

**What was tried beside the tests.** Seventy-seven one-line changes of the code that the amendment brought, each in a scratch copy, were run against the tests. Ten were not noticed at first, and each led to a stronger row. All seventy-seven are noticed now.

**The readings that the judge took beyond the text,** for the lead: (i) an extra key inside `units` refuses its file (item 4 and TABLE's head say nothing of a key inside that object, and the stricter reading was kept); (ii) `counts_as` has three values, `by the rule`, `fail` and `inconclusive`; (iii) reading 14 is applied to a pool's restart too; (iv) the entries of reading 24 are those that read the series, whoever owns them, since an S entry belongs to the run at h₃; (v) a support run's flag of reading 24 touches its restart's entries, and a plant run's flag touches nothing; (vi) a flag at the corner of item 5 (a) is settled for the retry's triple, so it changes nothing in the first pass; (vii) an amendment that this code does not name is a C0 fault, so a later one for Part 2 is best named otherwise than `AMENDMENT-*.md`.

## 10. Not done

- The independent scalar reference and the pool plants' two outputs (reading 8). The author's runs of 25 November are the evidence for them.
- The snapshot of `integrated_capture` lies outside the captures' root. Its recorded manifest sha256 is compared, and no file of it is opened.
- What only the checker can do: that a restart reloaded a checkpoint, that the engine checked every accepted row, the fingerprint of the composed file, and that the off-grid switch was off.
- The retry's commands on an owed retry: none is owed on the rehearsal's tables. They ran on altered fabricated tables (the tests).
- Part 2.
