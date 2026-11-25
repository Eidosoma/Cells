# The engine table: the contract

This is the contract between the builder, whose exporter writes the table, and the judge, whose reader parses it.
**Both read only this folder, with three exceptions:** the strings note (the protocol's §5: the operators' IDs), the
protocol's hashes and tags (the record of what was hashed), and the registration tag's revision (compared with
`source.engine_revision`). The contract is what this file says. A key the judge needs that is not here is asked for
through the lead and added by a dated change, never taken from the other side's code. Extra keys are allowed and
ignored.

## 1. Files

- `table/table_W5.json`, `table/table_W5-exact.json`, `table/table_W6.json` and `table/SHA256SUMS` (one line per
  file: the sha256, two spaces, the name). The retry's go in `table-retry/` (`table_W5-retry.json`,
  `table_W6-retry.json`, only for owed families, with a `SHA256SUMS` of its own). A table that has no registered run
  is absent, not empty.
- A table whose sha256 departs from its line in its folder's `SHA256SUMS`, has no line in that file, departs from
  the lead's record, or is one of the format sample's (§5) is refused: every run in it is refused and nothing of it
  is judged (CRITERIA.md §4). An absent `SHA256SUMS` is recorded and flagged, and refuses nothing by itself.
- The lead records each file's sha256 before the judge opens a table (the protocol's §5, step 8).
- The exporter writes **nothing that needs a second run:** no difference, ratio, estimate or error against a
  reference. The judge forms those.
- **The order of entries and keys is not a contract.** Runs are matched by name. Floats are JSON numbers (shortest
  round-trip form). NaN and infinity never occur.

## 2. Top-level keys, all required

| Key | Type |
| --- | --- |
| `kind` | the string `fr43 part 3 co-writers engine table, version 2` |
| `arm` | integer 1 (W5), 2 (W5-exact) or 3 (W6) |
| `runs` | object: run name to entry |
| `missing` | list of run names for which no record was found |
| `units` | object: `{"amount": "fmol", "volume": "pL", "time": "s"}` |

A run in neither `runs` nor `missing` is missing. Matching is by name. The same run name does not occur in two
tables. The series keys are the world's (§3): those are required, no other world's is asked for, and an extra one is
ignored.

## 3. A run's entry: one shape for every run

Every entry holds all of these keys. A completed run's `refusal` is null. A refused run keeps the rows and events it
has (any list may be short; in a run refused at parse `t`, the world's series, `integer_ledger` and the three lists
of `events` are empty).

| Key | Type and meaning |
| --- | --- |
| `status` | `"completed"` or `"refused"` |
| `world`, `first`, `copy` | string, string, integer: the registered world, which writer is declared first, and the copy |
| `step_s`, `steps` | number, integer (`steps` is recorded, and flagged if it differs from the grid) |
| `variant` | string or null: the registered variant (`restart`, `second halves in declared order`), else null |
| `seed` | integer |
| `t` | list of numbers: the sample times of the rows, in `samples_s` order. A completed judged run holds every registered sample time |
| `series` | object: the world's names to lists, each as long as `t`. W5 and W5-exact: `n_S_c`, `n_S_o`, `n_X`, `n_Y`, `n_W`, `xi_1`, `xi_2`, `moved`. W6: `n_R_c`, `n_R_o`, `n_N`, `n_M`, `n_Pi`, `free`, `engaged`, `transit`, `inits`, `exits`, `made`, `lost`, `moved`. A resumed run carries the samples at and after its checkpoint |
| `events` | object: `{"time_s": [...], "channel": [...], "counts_after": [[...], ...], "first_index": 0}`, parallel lists of one site's events in order of time. `channel` is the declared channel id. `counts_after` holds the counts after the event in the declared order of the unit states (free, active), as integers. `first_index` is the index (from 0, over the whole run) of the first listed event: 0 in a run that starts at t = 0, and in a resumed run the number of events before the checkpoint |
| `events_total` | integer: the engine's own cumulative count of the site's events over the whole run. It equals `first_index` plus the number of listed events |
| `trace_capacity` | integer: the number of events the engine's trace records. A run whose `events_total` exceeds it (a truncated trace) is refused, with kind `harness` |
| `integer_ledger` | list of integers, one per sample of `t`: Σ_k w_k n_k. The total after each event is not listed (the judge forms it from `counts_after`) |
| `samples_echo` | the list of the sample times the engine was asked to observe |
| `operators` | list of strings: the composite's declared operator IDs, **in declared order** (the strings note's) |
| `inputs` | the world's block in `inputs.json` with exactly the keys of `inputs.json`'s `echo`, numbers as the engine parsed and ran them, plus the run's `seed`, `step_s`, `first` and `copy`, read back from **the definition the engine parsed and ran**, never a copy of this folder's numbers. `read` (and every optional key) may be null or absent, which are equal. A run refused before its definition was parsed holds null here and in `definition`, and an empty list in `operators` (only such a run; a null in a completed run is a fault) |
| `definition` | the engine's own declaration, as run (recorded, never judged) |
| `checks` | the engine's own ledgers and checks at the end (recorded) |
| `pools_at_event` | the engine's own rows at the events, where it records them, else null (recorded, never judged) |
| `restart` | null, or `{"time_s", "step_index", "through"}` (the checkpoint's time, its step, how it was saved) |
| `host_patch` | null, or `{"id", "change"}` on the Lie plant's runs |
| `refusal` | null, or `{"kind", "message", "time_s"}`: the message as the engine raised it |
| `source` | `engine_revision`, `checkout_dirty` (boolean), `snapshot`, `snapshot_patch_sha256`, `python`, `numpy`, `scipy`, `jax`, `blas_threads` (integer), `machine`: strings but those marked |
| `record`, `record_sha256` | the run's own record file, and 64 hex digits |

- A number is a JSON number, a boolean a JSON boolean, an integer a JSON integer (a float with no fraction is
  accepted where an integer is asked, but not a string). `null` stands only where this table says so.
- **A completed run carries every key above**, with every series of its world as long as `t`, and `events` complete.
- **An `events` time** is the engine's own recorded time (its trace's clock), not a difference, in the run's own
  time from t = 0, in s.
- **A book** (`xi_1`, `xi_2`, `inits`, `exits`, `made`, `lost`, `moved`) is the writer's own cumulative account,
  from its own accumulator, as READOUTS.md §1 defines and signs it: not a row's difference. `engaged` and `transit`
  are the sums of READOUTS.md §1 over the engine's own stage complexes at the sample, and `free` is its free
  machines.
- **The restart.** A resumed run's `restart.time_s` is the registered checkpoint time (10⁻¹² relative), and its `t`
  lists every registered sample at and after the checkpoint. Its `events` list holds every event after it, and
  `first_index` is the number of events before it. One that does not is refused.

**The kinds of refusal,** set by the exporter from what the engine raised (its README lists the mapping, and the
checker confirms it): `domain` (a refusal by name of a value outside a declared domain, at parse or at run time),
`definition` (a declaration it could not read or does not support, at parse), `check` (a ledger or domain check of a
completed row failed), `harness` (anything the engine did not raise: the exporter, the driver, memory, a crash, a
truncated trace).

**Every refused, restarted and plant run uses this one shape.** There are no special tables and no key that appears
only for one kind.

## 4. The Lie plant's runs and the restart

- **A plant run** (`host_patch` not null): its `operators`, `inputs` and `definition` equal those of the honest run
  it mirrors (its run name without ` lie`), but for the patch, and its `host_patch.id` is
  `second_halves_declared_order`. It has no restart.
- **A restart run** echoes the interrupted world's `inputs`, and `restart` names the checkpoint's time, its step
  index and how the state was saved. It has no t = 0 row: its identities use the uninterrupted run's t = 0 row
  (CRITERIA.md §3.6), and it has no `start` entry.

## 5. The format sample

- **What it is:** the builder's own table code, run on **invented** worlds (none of this folder's numbers;
  `inputs_invented.json`'s), with every number replaced by a meaningless one of the same type. It covers a completed
  run of each world and each kind of variant, a refused run of each kind, a stopped run, a restart, a Lie plant, and
  the retry folder.
- **Its sha256 for each file** is recorded by the lead in a dated note in this folder before the judge's tag. The
  builder lists every key and type, to the leaf, in a README beside it.
- **The judge parses it before its tag:** it recomputes the hashes, reads every file with the same code that will
  read the registered tables, in a structure-only mode (keys, nesting and types, no number), and must find no fault,
  and reports the entry kinds found and any key or type that departs. A check that fails stops the tag.
- **A departure** of the sample from this contract is the builder's to fix. If the contract itself must change, that
  is a dated change to this file, by the author, before the judge's tag.
- **What may never be taken from it:** a number, a list length, an order of keys or entries, an equality between its
  numbers. No tolerance, scale or verdict may depend on it. A table whose sha256 is one of the sample's is refused
  in judgement.
- **At the run tag** the lead regenerates the sample at the merged head and compares it, key by key and type by
  type. A difference returns to the author, before the tag, never after.
