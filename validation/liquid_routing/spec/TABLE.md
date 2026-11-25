# The engine table: the contract

This is the contract between the builder, whose exporter writes the table, and the judge, whose reader
parses it. Both read only this folder. The contract is what this file says. A key the judge needs that is
not here is asked for through the lead and added by a dated change, never taken from the other side's
code. Extra keys are allowed and ignored.

## 1. Files

- `table/table_arm<k>.json`, k = 1 … 7, and `table/SHA256SUMS` (one line per file: the sha256, two spaces,
  the name). The retry's go in `table-retry/`, arm 6's in `table-arm6/`.
- A table whose sha256 is missing from its folder's `SHA256SUMS`, or departs from it, is refused: every
  run in it is refused. An absent `SHA256SUMS` is recorded and flagged, and refuses nothing by itself.
- The lead records each file's sha256 before any reference value is read. Phase 1's tables hold arms 1 to 5 and
  7, arm 6's alone comes from the second snapshot (`table-arm6/`), and neither re-runs the other's runs.
- The exporter writes **nothing that needs a second run:** no difference, ratio or estimate. The judge
  forms those.

## 2. Top-level keys, all required

| Key | Type |
| --- | --- |
| `kind` | the string `liquid-routing engine table, version 1` |
| `arm` | integer 1 to 7 |
| `runs` | object: run name to entry (`inputs.json`'s names; the retry's add ` retry`) |
| `missing` | list of run names for which no record was found |
| `units` | object: `{"amount": "fmol", "volume": "pL", "energy": "pJ", "time": "s"}` (of the series; a refusal's message states its own units) |

A run in neither `runs` nor `missing` is missing. Matching is by name, never by position or key order.

## 3. A run's entry: one shape for every run

Every entry holds all of these keys. A completed run's `refusal` is null. A refused run keeps the rows it
has (`t` and `series` may be short or empty).

| Key | Type and meaning |
| --- | --- |
| `status` | `"completed"` or `"refused"` |
| `world`, `heat`, `variant` | string; `"exact"` or `"default"`; string or null |
| `solver`, `heat_id` | string: the registered ID the engine ran (the new form) |
| `operators` | list of strings: the composite's declared operator IDs, sorted |
| `step_s`, `steps` | number, integer (`steps` is recorded and flagged if it differs from the grid) |
| `t` | list of numbers: the rows' times, the first 0 |
| `series` | object: READOUTS.md's names to lists, each as long as `t` |
| `events` | list, in time order; [] where the world has none. Arm 2: `{"kind": "exchange", "time_s", "node", "before", "sample", "supplied", "heat"}`, the four being `{species: number}` except `heat` (number). Arm 4: `{"kind": "delivery", "time_s", "volume", "amount", "loss", "resident", "arriving"}`, `amount` by species, the rest numbers |
| `inputs` | the world's block in `inputs.json`, without `outputs_s` and `compare_s`, read back from **the definition the engine parsed and ran**, with `step_s` added and `end_s` a number (a world whose `end_s` is `one step` is echoed with the step). Not a copy of this folder's numbers |
| `definition` | the engine's own declaration, as run (recorded) |
| `checks` | the engine's own ledgers and checks at the end (recorded) |
| `restart` | null, or `{"time_s", "step_index", "through"}` (the checkpoint's time, and how it was saved) |
| `digests` | arm 7: `{name: sha256}` of every saved array's bytes, dtype and shape; `{}` elsewhere |
| `host_patch` | null, or `{"id", "change"}` on a plant's run |
| `largest_ion_change_fmol` | number: the largest change of any ion's amount at any node or cell (recorded) |
| `refusal` | null, or `{"kind", "message", "time_s"}`: the message as the engine raised it, `time_s` the time of the row that failed (a number for `check`, null otherwise), and `kind` as below |
| `source` | `engine_revision`, `checkout_dirty` (boolean), `snapshot`, `snapshot_patch_sha256`, `python`, `numpy`, `scipy`, `jax`, `blas_threads` (integer), `machine`, all strings but those marked |
| `record`, `record_sha256` | the run's own record file, and 64 hex digits |

- A number is a JSON number. `null` stands only where this table says so. NaN and infinity do not occur.
- **An expected refusal is an entry like any other,** `refused` with kind `domain`.
- **Every series a completed run carries** has READOUTS.md's name, and each listed readout of its arm and world
  is present. A series with a short `t` belongs to a refused run.
- **Arm 1 and arm 2:** `n_T_1`, `n_T_2`, `H_face`, `transfer_T`. **Arms 3 to 6:** `n_<x>_<i>`, `V_K`,
  `supplied_<x>`, `H_<i>`, the labels in `F1L` and `F6L`, `n_L_S`, `free_sites_S` and `bound_L_S` in
  `F7`, `H_face` in arm 6. **Arm 7:** `digests` and `operators` (`series` may be empty), the runs named
  `<pair> wash` and `<pair> router`. A resumed run's `t` holds the rows it recorded.
- **`refusal.message`** for kind `check` names the ledger that failed, and states its residual and its tolerance
  by those two words, each with the ledger's own unit (CRITERIA.md §3.7's M1 lists the units).

**The kinds of refusal,** set by the exporter from what the engine raised (its README lists the mapping, and the
checker confirms it):

| Kind | What produced it |
| --- | --- |
| `domain` | The engine refused, by name, a value outside a declared domain, at parse or at run time: a throughput above its bound, a default-heat exchange outside its domain, a flow at a faced node (phase 1's snapshot) |
| `definition` | A declaration the engine could not read or does not support, at parse: a missing or malformed key, an unbalanced node, an unsupported combination |
| `check` | The engine's own energy, material or charge check failed a completed row |
| `harness` | Anything the engine did not raise: the exporter, the driver, memory, a crash |

A refusal at parse has no rows: `t` is [], `series` is {} and `time_s` is null. Otherwise a refused run is an
ordinary entry.

**Every refused, restarted, plant, twin and no-router run uses this one shape.** There are no special
tables and no key that appears only for one kind.

## 4. The format sample

- **What it is:** the builder's own table code, run on **invented** worlds (none of `inputs.json`'s volumes,
  flows, times or concentrations), with every number replaced by a meaningless one of the same type. It
  covers a completed run of each arm 1 to 7, a labelled run, a refused run of each kind, a stopped run,
  a restart, a twin, a plant and the retry folder.
- **Its sha256 for each file** is recorded by the lead in a dated note in this folder before the judge's
  tag. The builder lists every key and type, to the leaf, in a README beside it.
- **The judge parses it before its tag:** it recomputes the hashes, reads every file with the same code
  that will read the registered tables, in a structure-only mode (keys, nesting and types, no number), and
  must find no fault, and reports the entry kinds found and any key or type that departs. A check that
  fails stops the tag.
- **A departure** of the sample from this contract is the builder's to fix. If the contract itself must
  change, that is a dated change to this file, by the author, before the judge's tag.
- **What may never be taken from it:** a number, a list length, an order of keys or entries, an equality
  between its numbers. No tolerance, scale or verdict may depend on it. A table whose sha256 is one of the
  sample's is refused in judgement.
- **At the run tag** the lead regenerates the sample at the merged head and compares it, key by key and
  type by type. A difference returns to the author, before the tag, never after.
