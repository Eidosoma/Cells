# The engine table: the contract

This is the contract between the builder, whose exporter writes the table, and the judge, whose reader parses it.
Both read only this folder. The contract is what this file says. A key the judge needs that is not here is asked for
through the lead and added by a dated change, never taken from the other side's code. Extra keys are allowed and
ignored.

## 1. Files

- `table/table_W5.json`, `table/table_W5-exact.json`, `table/table_W6.json` and `table/SHA256SUMS` (one line per
  file: the sha256, two spaces, the name). The retry's go in `table-retry/` (`table_W5-retry.json`,
  `table_W6-retry.json`, only the families that are owed). A table that has no registered run is absent, not empty.
- A table whose sha256 is missing from its folder's `SHA256SUMS`, or departs from it, is refused: every run in it is
  refused. An absent `SHA256SUMS` is recorded and flagged and refuses nothing by itself.
- The lead records each file's sha256 before any reference value is read (the protocol's §6).
- The exporter writes **nothing that needs a second run:** no difference, ratio, estimate or error against a
  reference. The judge forms those.
- **The order of entries and keys is not a contract.** Runs are matched by name. Floats are JSON numbers (shortest
  round-trip form). NaN and infinity never occur.

## 2. Top-level keys, all required

| Key | Type |
| --- | --- |
| `kind` | the string `fr43 part 3 co-writers engine table, version 1` |
| `arm` | integer 1 (W5), 2 (W5-exact) or 3 (W6) |
| `runs` | object: run name to entry |
| `missing` | list of run names for which no record was found |
| `units` | object: `{"amount": "fmol", "volume": "pL", "time": "s"}` |

A run in neither `runs` nor `missing` is missing. Matching is by name. The same run name does not occur in two
tables.

## 3. A run's entry: one shape for every run

Every entry holds all of these keys. A completed run's `refusal` is null. A refused run keeps the rows and events it
has (any list may be short, and the series and `events` lists may be empty).

| Key | Type and meaning |
| --- | --- |
| `status` | `"completed"` or `"refused"` |
| `world`, `first`, `copy` | string, string, integer: the registered world, which writer is declared first, and the copy |
| `step_s`, `steps` | number, integer (`steps` is recorded, and flagged if it differs from the grid) |
| `variant` | string or null: the registered variant (`restart`, `second halves in declared order`), else null |
| `seed` | integer |
| `t` | list of numbers: the sample times of the rows, in `samples_s` order |
| `series` | object: READOUTS.md's names to lists, each as long as `t`: `n_S_c`, `n_S_o`, `n_X`, `n_Y`, `n_W`, `xi_1`, `xi_2`, `moved` in W5 and W5-exact; `n_R_c`, `n_R_o`, `made`, `lost`, `moved` in W6. The resumed run of a restart carries the samples at and after its checkpoint |
| `events` | object: `{"time_s": [...], "channel": [...], "counts_after": [[...], ...], "first_index": 0}`, parallel lists of one site's events in order of time. `channel` is the declared channel id (a string). `counts_after` holds the counts after the event in the declared order of the unit states (free, active), as integers. `first_index` is the index (from 0, over the whole run) of the first listed event: 0 in a run that starts at t = 0, and in a resumed run the number of events before the checkpoint |
| `events_total` | integer: the engine's own cumulative count of the site's events, at the end of the run |
| `trace_capacity` | integer: the number of events the engine's trace records. A run whose `events_total` exceeds it (the trace was truncated) is refused, with kind `harness` |
| `integer_ledger` | list of integers, one per sample: Σ_k w_k n_k, and the total after each event is not listed (the judge forms it from `counts_after`) |
| `samples_echo` | the list of the registered sample times the engine was asked to observe |
| `operators` | list of strings: the composite's declared operator IDs, **in declared order** (the strings note's) |
| `inputs` | the world's block in `inputs.json` with exactly the keys of `inputs.json`'s `echo` (below), numbers as the engine parsed and ran them, plus the run's `seed`, `step_s`, `first` and `copy`, read back from **the definition the engine parsed and ran**, never a copy of this folder's numbers |
| `definition` | the engine's own declaration, as run (recorded, never judged) |
| `checks` | the engine's own ledgers and checks at the end (recorded) |
| `pools_at_event` | the engine's own rows at the events, where it records them, else null (recorded, never judged) |
| `restart` | null, or `{"time_s", "step_index", "through"}` (the checkpoint's time, and how it was saved) |
| `host_patch` | null, or `{"id", "change"}` on the Lie plant's runs |
| `refusal` | null, or `{"kind", "message", "time_s"}`: the message as the engine raised it |
| `source` | `engine_revision`, `checkout_dirty` (boolean), `snapshot`, `snapshot_patch_sha256`, `python`, `numpy`, `scipy`, `jax`, `blas_threads` (integer), `machine`: strings but those marked |
| `record`, `record_sha256` | the run's own record file, and 64 hex digits |

- A number is a JSON number, a boolean a JSON boolean, an integer a JSON integer (a float with no fraction is
  accepted where an integer is asked, but not a string). `null` stands only where this table says so.
- **A completed run carries every key above,** with every listed series of its world and `events` complete:
  `events_total` equals the number of listed events plus `first_index`, and a listed event's `counts_after` follows
  its channel.
- **An `events` time** is the engine's own recorded time (its trace's clock), not a difference, in the run's own
  time from t = 0, in s.
- **Series times** are the sample times, in `t`, whose values are in `series`. A listed time must be one of the
  registered `samples_s` (or, in a restart, from its checkpoint on).
- **`moved`** is the population's own cumulative account of the transfer, from its own accumulator, positive from
  the cell to the node: not the node's row difference. `xi_1`, `xi_2`, `made`, `lost` are the writers' own
  cumulative accounts, as READOUTS.md §1 defines and signs them, read from the engine's accumulators and not formed
  from rows.

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
  index and how the state was saved. Its rows and `events` are those after the checkpoint (`t` from that sample on,
  and `events` from the next event on with its `first_index`).

## 5. The format sample

- **What it is:** the builder's own table code, run on **invented** worlds (none of this folder's numbers), with
  every number replaced by a meaningless one of the same type. It covers a completed run of each world and each kind
  of variant, a refused run of each kind, a stopped run, a restart, a Lie plant, and the retry folder.
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
