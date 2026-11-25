# The engine table: the contract

This is the contract between the builders, whose exporter writes the table, and the judge, whose reader parses it. Both read this folder alone. A key that the judge needs
and that is not here is asked for through the lead and added by a dated change, never taken from the other side's code. **Extra keys are allowed, recorded and ignored.**

## 1. Files

- `table/table_<consumer>.json`, consumers `jupiter`, `cell`, `base`, `integrated` (Part 1) and, in Part 2, `PART2.md` §4's. One file per consumer. `table/SHA256SUMS`: one line per file, the sha256, two spaces, the name.
- `table-retry/table_<consumer>.json` and its `SHA256SUMS`, with the judge's `retry_owed.json`. `table-rehearsal/table_<consumer>.json` and its `SHA256SUMS`.
- **A table whose sha256 is missing from its folder's `SHA256SUMS`, or departs from it, is refused,** with every run in it. An absent `SHA256SUMS` is recorded and flagged and refuses nothing by itself.
- The lead records the sha256 of every file before any reference is read.
- **A duplicate key anywhere refuses the file.** JSON is read with NaN and Infinity allowed. A non-finite number in a judged leaf leaves its entry not formed, and one in a recorded leaf is flagged.
- **The exporter forms nothing that needs two runs:** no difference, ratio, estimate or extrapolation. The judge forms those.

## 2. Top-level keys, all required

| Key | Type |
| --- | --- |
| `kind` | the string `ensemble-reexpression engine table, version 1` |
| `part` | integer 1 or 2 |
| `consumer` | string |
| `runs` | object: run name to entry |
| `missing` | list of run names for which no record was found |
| `units` | `{"amount": "fmol", "energy": "pJ", "potential": "V", "time": "s"}` |

Matching is by name, never by position or key order. A run in neither `runs` nor `missing`, over the tables of a consumer together, is missing.

## 3. A run's entry: one shape for every run

Every entry holds all of these keys. A key that a kind of run does not use holds `null`, or `{}` or `[]` where the type says so.

| Key | Type and meaning |
| --- | --- |
| `status` | `"completed"` or `"refused"` |
| `world` | string: `inputs.json`'s world |
| `variant` | string or null: the registered run's |
| `seed_index`, `world_id` | integers or null: the registered run's |
| `step_s` | number, or null for a pool run |
| `steps` | integer, or null for a pool run: the accepted steps of the run. For `jupiter` and `integrated` it equals end_s/step_s (a larger number means a change split a step, and the run is refused with the reason `off_grid_change`). For `cell` and `base` it is at least that and at most that plus the committed events of the world's two (or one) pool paths. **For a restart** it counts the accepted steps after the checkpoint, (end_s − the checkpoint's time)/step_s, with the same addition for `cell` and `base` |
| `t` | list of numbers: the times of `rows`, strictly increasing, the first 0, every compared time there. **For a restart** it continues its judged run's clock: the first is the checkpoint's time and not 0, and every compared time after the checkpoint is there. `[]` for a pool run, whose `rows` and `potentials` are `{}` and `potential_t` `[]` |
| `rows` | object: READOUTS §2's name to an object, entity ID to a list as long as `t` |
| `potential_t` | list of numbers: the times of `potentials`, 0 first (for `jupiter` and `integrated` the block's `potential_times_s`, for `base` and `cell` 0 and then `summary_times_s`). The voltage at 0 is the run's own V₀ (`READOUTS.md` §5). For a restart, the ones after the checkpoint |
| `potentials` | object: `voltage` and `phi_out` to entity ID to a list as long as `potential_t`. A world without one omits it |
| `pool` | null, or for a pool run an object: cell ID to `{"arrays": {<19 names>: nested lists [world, ...]}, "seed": integer, "stream_id": integer}` |
| `path` | null, or for a pool run an object: cell ID to an object, world ID (as a string) to a list of `[time, availability]`, one per committed event, in order |
| `inputs` | the world's block, read back from **the definition the engine parsed and ran**, never a copy of this folder. For an ionic run it is `inputs.json` `worlds.<w>.ionic`, with `controls.channel` the schedule the run declared. For an ionic run of `cell` or `base` it also holds `assembly` (below). For a pool run it is, per cell, `channel`, `stream_id`, `seed` and `pool` (the block of `SPEC.md` §2.5). The harness fields are in `definition` |
| `strings` | object: label to the exact string the run declared, for every label the strings note lists for that run, **and no other label** (§5) |
| `declared_strings` | list of strings, sorted: **every** registered string that the definition the engine parsed and ran declares (its model, laws, operators, kinds, solver, field solver and observable), one each. It equals the set of `strings`' values exactly, so an extra operator, kind or law is visible (§5) |
| `definition` | the engine's own declaration, as run (recorded) |
| `checks` | the engine's own ledgers and checks at the end (recorded) |
| `restart` | null, or `{"time_s", "step_index", "through"}`: the checkpoint's time, its step index and how it was saved (through a file) |
| `host_patch` | null. A run of this registration has none |
| `refusal` | null, or `{"kind", "message", "time_s"}` (§4) |
| `source` | `engine_revision`, `checkout_dirty` (boolean), `snapshot`, `snapshot_patch_sha256`, `python`, `numpy`, `jax`, `jaxlib`, `cpu_model`, `blas_threads` (integer), all strings but those marked |
| `record`, `record_sha256` | the run's own record file, and its 64 hex digits |

- **`inputs.assembly`** of an ionic run of `cell` or `base` (`SPEC.md` §3.3) holds exactly these keys, and nothing of it is optional:
  - `assembly_observable`: the label of the registered law, as the definition records it, which the strings note maps to the exact string (a departure is an echo's, `CRITERIA.md` §5);
  - `composed_file_fingerprint`: the string that the definition records for the composed file. It is recorded, and nothing is compared with it. The checker recomputes it from the composed file;
  - `pool_seeds`: cell ID to integer, the seeds of the pool run the file was composed from (class E, `CRITERIA.md` §4.1);
  - `switch_list`: channel ID to a list of `[time, availability]`, the changes that the driver wrote, in order (class E). The initial entry [0, 1] may be written or left out (`SPEC.md` §3.2).
- **The record holds the run's own name** in its content. So no two records are alike, and worlds whose pools have no event, which are honestly the same ionic solution, do not share a hash.
- **`rows` of an ionic assembly run:** `t` is 0, `summary_times_s` and `end_s`, once each, at least. Extra rows are allowed. A row at a split (an event time) is an accepted row and is not needed.
- **A completed run's `refusal` is null and a refused run's is not.** A refused run keeps the rows it has.
- **Numbers are JSON numbers.** A double is printed so that it reads back to the same double (`repr`). The bond and occupied masks are integers. `null` stands only where this table says so. There is no NaN, infinity or boolean in `rows`, `potentials` or `path`.
- **A run's `t` values** match the registered times within 10⁻¹² s.

## 4. The kinds of refusal, and what is not a refusal

| Kind | What produced it |
| --- | --- |
| `definition` | A declaration the engine could not read or does not support, at parse |
| `domain` | The engine refused, by name, a value outside a declared domain, at parse or at run time |
| `check` | The engine's own energy, material or charge check failed a completed row: a **stop** |
| `harness` | Anything the engine did not raise: the exporter, the driver, memory, a crash |

- `message` is the engine's, as raised. `time_s` is the time of the row that failed (a number for `check`, null otherwise). A refusal at parse has `t` [], `rows` {}, `potentials` {} and `time_s` null.
- **The mapping from what the engine raised to a kind is the exporter's.** Its README lists it, and the checker confirms it. A refusal is never read as a gap.
- **For a run refused at parse** the `inputs` and `definition` are the submitted declaration, and `strings` those declared.

## 5. The strings note

`validation/ensemble_reexpression/registered_strings.json`, the lead's, with its own commit and its own tag **after the registration tag and before any run** (the protocol's §5). It holds **today's IDs**: the runs are made before the ID move, so the strings are those of the registered head, and the move's table maps them afterwards. Its rehearsal counterpart exercises every match.

```json
{"kind": "ensemble-reexpression registered strings, version 1",
 "revision": "<40 hex>", "rehearsal_revision": null,
 "labels": {"inner_model": "", "rk4": "", "field_solver": "", "field_solver_floor": "", "closure": "", "constant_field": "", "kv15_mh": "",
            "nak_pump_positive": "", "maintained_fuel": "", "junction_relaxation": "", "logmean_face": "", "pool_model": "", "pool_topology": "", "assembly_observable": ""},
 "runs": {"<run name>": {"model": "<label>", "solver": "<label>", "field_solver": "<label>", "operators": [], "kinds": [], "laws": ["<labels>"], "pool": ["<labels>"], "observable": "<label or null>"}}}
```

- **`labels`** maps each label of `inputs.json`'s blocks to the exact registered string. It is written by the lead from the declared worlds, never from a table, and checked by parse before its tag. A label that Part 2 needs is added by `PART2.md` §4's table.
- **`runs`** gives, for every registered run (the retry's by the same rule as its family), **the full set of labels it declares**, with an empty list where there is none. The judge reads a run's `strings` as `labels[...]` for them, exactly, and its `declared_strings` as the set of those strings, exactly: **a missing label, an extra label and an extra string each make the run a departing echo.**
- **`revision`** is the registration tag's, which a file in the tagged commit cannot hold. `engine_revision` is compared with it (and in the rehearsal with `rehearsal_revision`).
- A typo in a note is corrected by a dated second note with its own tag, before any table is hashed, and never after.

## 6. `retry_owed.json` (the judge's)

`{"kind": "ensemble-reexpression retry owed, version 1", "part": 1, "runs": ["<name>"], "why": {"<family>": ["<readout: reason>"]}}`, the names sorted. The reasons are `order` and `power`.

## 7. The format sample, before the judge's tag

- The builders' own table code, run on **invented** worlds (none of `inputs.json`'s), with every number replaced by a meaningless one of the same type. It holds a completed run of each kind of world, a pool run, a restart, a refused run of each kind, a stopped run, an engine plant, and the retry folder.
- The builders list every key and type, to the leaf, in a README beside it. The lead records each file's sha256 in a dated note before the judge's tag.
- The judge's reader parses it with the code that will read the registered tables, in a structure-only mode, and finds no fault. A departure is the builders' to fix. A change of the contract is a dated change to this file.
- **What may never be taken from it:** a number, a length, an order of keys or entries, an equality between its numbers.
