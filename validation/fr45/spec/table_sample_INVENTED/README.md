# FR-45's engine table: the format sample (INVENTED)

**INVENTED.** This folder is the engine table's format sample, which `validation/fr45/spec/TABLE.md` §12.1 asks for. It
is written in that contract's shapes, on invented worlds. **No number in it belongs to FR-45, and none may be taken
from it:** no number, list length, order of keys or entries, or equality between its numbers (TABLE.md §12.1).

- **Who wrote it, and how.** It was written on 27 November 2026, before the binding tag, by the agent who made the
  contract's two dated changes of that day. That agent is not the builder and has seen no reference value. It wrote
  the sample by hand from the contract (RULINGS-2 §3, item 1). A small writer of the agent's own, outside the checkout,
  assembled the JSON from invented values. No engine code was run or read.
- **The second dated change** (RULINGS-2 §7) added the runs `INVENTED-W1p-P3~check` and `INVENTED-W6~check` [S-f],
  and made each `plant.patch` a path from the checkout's root [W-a].
- **What reads it.** The judge reads `table/table.json` in its structure-only mode, with the code that will read the
  table, before the judged run, and must find no fault. At the judged run's snapshot, the builder's exporter writes a
  table on these invented worlds, and the lead compares it with this sample, key by key and type by type
  (TABLE.md §12.1).
- **What it is not.** It is not the references' `format_sample_INVENTED.json`, which is the file the judge reads first
  (PROTOCOL:129-130).

## Files

| File | What it is |
| --- | --- |
| `table/table.json` | the sample table, laid out as TABLE.md §1 lays out the table |
| `table/SHA256SUMS` | one line: the sha256 of `table/table.json`, two spaces, `table.json` |
| `start_INVENTED-W1eq.json` | the invented file that `INVENTED-W1eq` reads its start from, at TABLE.md §3's paths: `world.populations[].initial_occupancy` by `id`, and `world.free_amounts[].n` by `ligand` and `node` |
| `README.md` | this file |

The lead records the sha256 of each file in a dated note in `validation/fr45/spec/`, with the expected-inputs file's
(TABLE.md §12.1, §12.2).

## Names

- **Runs.** Each run is named `INVENTED-` and the registered run name (TABLE.md §3) whose shape it takes, as
  `INVENTED-W1p-P8`. W4's three carry their own invented dt, as `INVENTED-W4-dt0.125`. A second run of one shape adds
  `~` and a refusal kind, as `INVENTED-W3~definition`. The judge maps a sample run to its registered shape by its name.
- **Worlds.** Each world is named `INVENTED-` and the registered world's name. The nodes (`tank`, `basin`, `lake`,
  `cask`, `cup`, `pond`, `bay`), the cell `vesicle`, the unregistered cell `husk`, the patches `vesicle_wall` and
  `husk_wall`, the ligands `X1` to `X5`, and the sets and populations are invented names.
- **The one extra key** is the top level's `INVENTED`, a string. Every comparison skips it (TABLE.md §12.1).

## Numbers

None of SPEC.md's input values appears, except the format constants that TABLE.md §12.1 lists:
- step 0, with its clock 0.0, at the start; the cumulative heat 0.0 at the start; the records 0.0 before the wash;
- `step_report.step` 1 and `limit` 0.5;
- the registered `permeabilities` 0.0, `multipliers` 1.0 and `charges` 0.

Every other number is invented and meaningless, including N_f, T, RT and the traces. The step counts of the invented
runs (`rows[].step`, `steps`, `after_step`, `state_step`, `refusal.step` and `failures[].step`) count the invented
runs' steps. They are not input values. The writer's check found no other number equal to a literal of SPEC.md's
§0 to §2.

## The runs, and what each shows

| Run | Status | What it shows (TABLE.md §12.1) |
| --- | --- | --- |
| `INVENTED-W1` | completed | a node-owned set with two ligands |
| `INVENTED-W1eq` | completed | a start read from a file (`start_INVENTED-W1eq.json`) |
| `INVENTED-W2` | completed | a wash: its one event, and its map on the wash row in both variants (W2's shape) |
| `INVENTED-W2~harness` | refused, `harness` | a run time refusal after the wash, by a time limit, with `raised` null; it keeps its rows, its event and its map entries |
| `INVENTED-W3` | completed | a three-ligand set and a one-population set at a node, and a set on a patch's inside face in a registered cell; traces; `free_sites` `"derived"` |
| `INVENTED-W3~definition` | refused at parse, `definition` | the nulls of a run refused before parse |
| `INVENTED-W4-dt0.125`, `INVENTED-W4-dt0.0625`, `INVENTED-W4-dt0.03125` | completed | one world at three steps |
| `INVENTED-W5` | refused, `stage` | W5's refused shape: `step_report` with `verdict` `"refused"`, and `max_load` the set's summed `L_R` |
| `INVENTED-W6` | completed | a set on a patch's outside face, and an unregistered cell (`husk`, `registered` false) with its traces |
| `INVENTED-W6~check` | refused, `check` | an honest run refused at run time by a host check: `book` `"host check: INVENTED ion amounts"`, with the failure in `checks` [S-f] |
| `INVENTED-W6~domain` | refused at parse, `domain` | a refusal by domain |
| `INVENTED-W7` | completed | a wash: its one event, and its map on the start and on the wash row in both variants (W7's shape) |
| `INVENTED-W7s` | completed | a one-population set (`shared` false, `free_sites` `"derived"`); the absent ligand `X2` held at its trace, `declared` false |
| `INVENTED-W1p` | completed | the honest baseline of the W1p plants |
| `INVENTED-W1p-P1` | completed | P1's shape (`rows[].amounts`) |
| `INVENTED-W1p-P2` | completed | a plant run whose `inputs_changed` is not empty: the two `k_off` crossed by declaration |
| `INVENTED-W1p-P3` | completed | P3's shape (`rows[].site_heat_pJ` and `amounts`) |
| `INVENTED-W1p-P3~check` | refused, `check` | P3's catch by refusal: `book` `"dissipation check"`, with the failure in `checks` [S-f] |
| `INVENTED-W1p-P6` | refused, `check` | a refusal by the energy ledger: `book` `"energy ledger"`, with the failure in `checks` |
| `INVENTED-W1p-P8` | refused, `check` | a refusal by its own ledger: `book` `"moiety ledger"`, with the failure in `checks` |
| `INVENTED-W1p-P9` | completed | P9's shape (`rows[].site_occupied_fraction`) |
| `INVENTED-W5-P4` | completed | W5's admitted shape: `verdict` `"admitted"`, `max_load` one population's `L_R`, the horizon's row |
| `INVENTED-W2-P5` | completed | the planted map on the wash row, both variants |
| `INVENTED-W7-P5` | completed | the planted map on the start and the wash row, both variants |
| `INVENTED-W3p-P7` | completed | P7's shape, on a world with a patch and every key of `inputs` filled |

`missing` holds `INVENTED-W3p`, so the honest W3p shape is shown only through `INVENTED-W3`'s and `INVENTED-W3p-P7`'s.

**Every key of 27 November appears:** `refusal.raised` (a string, and null in the harness refusal), `refusal.book` (all
four forms: `"moiety ledger"`, `"energy ledger"`, `"dissipation check"` and `"host check: <name>"`, and null outside
`check`) [S-f], `free_sites` (both words), `inputs.permeabilities`, `inputs.multipliers`, `inputs.charges`, among them
the absent ligand's member in `INVENTED-W7s` [S-g], `source.jax_platforms` and `source.external_modules`.

**The checks.** Every parsed run lists the same four invented checks, and the refusing one records its failure. That
uniform set is not the list of checks: the dated addendum gives each check's worlds or operators and its cadence, and
"lacks a listed check" means a check listed for the run's world (TABLE.md §4, §14.1) [S-b].

## For the builder's exporter: the invented worlds

Each run's `inputs` declares its world, so the exporter's run on it is defined. The runs that need more are these:
- `INVENTED-W1eq` reads its start from `start_INVENTED-W1eq.json`, by TABLE.md §3's paths.
- `INVENTED-W2~harness` is `INVENTED-W2` with a driver time limit that ends it during step 15.
- `INVENTED-W3~definition` is `INVENTED-W3` with a second population on `plate` binding `X1` (version 1's refusal of
  two populations of one set binding one ligand, PROTOCOL:56), with `plate_X1`'s rates and an initial occupancy of
  0.03.
- `INVENTED-W6~domain` is `INVENTED-W6` with `skin`'s initial occupancies 0.72 and 0.61, which sum above 1
  (PROTOCOL:57).
- `INVENTED-W5` is refused by the stage condition at its first step. `INVENTED-W5-P4`'s per-population load admits it.
- The plant runs carry each plant's patch, as TABLE.md §8.1 says. `INVENTED-W1p-P6` and `INVENTED-W1p-P8` show refusals
  by the energy ledger and by the plant's own moiety ledger.
- `INVENTED-W1p-P3~check` is `INVENTED-W1p-P3` refused by the dissipation check during step 4, and `INVENTED-W6~check`
  is `INVENTED-W6` refused by the host check `INVENTED ion amounts` during step 15 [S-f]. The builder produces each by a
  means of its choosing on these invented worlds, such as a check's bound tightened for this world alone.

A run whose outcome on the engine differs from the sample's (a refusal at another step, say) is a difference for the
contract's author, before the judged run (TABLE.md §12.1).

The `definition` objects, and their `checks` member that names each check's mode, are placeholders. `definition` is the
engine's own declaration in its own form, and the addendum on checks names where it records each mode
(TABLE.md §4, §14.1).

## Every key and type, to the leaf

**The path syntax.**
- `runs.<run>` is any run's entry, and `[]` any member of a list.
- `<observable>` is `n:<ligand>@<node>`, `R:<set>` or `B:<population>`.
- `<ligand>@<node>` is a record's key, and `<node>`, `<set>`, `<population>`, `<ligand>` and `<check>` are the keys of
  objects keyed by data.

**The types.** "number" is a JSON number. "integer" is a JSON integer. "or null" marks the nulls TABLE.md allows. A
non-finite value would also be written as null at a number (TABLE.md §1), but the sample has none.

| Path | Type |
| --- | --- |
| `INVENTED` | string: the sample's extra key |
| `kind` | string: `fr45 site-competition engine table, version 1` |
| `protocol` | string: `fr45-site-competition-v1` |
| `runs` | object: run name → entry |
| `missing` | list |
| `missing[]` | string: a run name |
| `units` | object, exactly TABLE.md §9's |
| `units.amount` | string: `fmol` |
| `units.volume` | string: `pL` |
| `units.concentration` | string: `mM` |
| `units.k_on` | string: `per mM per s` |
| `units.k_off` | string: `per s` |
| `units.time` | string: `s` |
| `units.heat` | string: `pJ` |
| `units.fraction` | string: `1` |
| `units.load` | string: `per s` |
| `units.copies` | string: `copies` |
| `runs.<run>` | object: TABLE.md §4's one shape |
| `runs.<run>.status` | string: `completed` or `refused` |
| `runs.<run>.world` | string |
| `runs.<run>.plant` | object, or null in an honest run |
| `runs.<run>.plant.id` | string: `P1` to `P9` |
| `runs.<run>.plant.patch` | string: a path from the checkout's root, beginning `validation/` [W-a] |
| `runs.<run>.plant.change` | string |
| `runs.<run>.plant.inputs_changed` | list |
| `runs.<run>.plant.inputs_changed[]` | string: a key path of `inputs` |
| `runs.<run>.dt_s` | number |
| `runs.<run>.steps` | integer |
| `runs.<run>.backend` | string: `numpy` or `compiled` |
| `runs.<run>.rows` | list, in step order |
| `runs.<run>.rows[]` | object |
| `runs.<run>.rows[].step` | integer |
| `runs.<run>.rows[].time_s` | number |
| `runs.<run>.rows[].amounts` | object: every observable |
| `runs.<run>.rows[].amounts.<observable>` | number (fmol) |
| `runs.<run>.rows[].records` | object: every ligand at the washed node; empty without a wash |
| `runs.<run>.rows[].records.<ligand>@<node>` | object |
| `runs.<run>.rows[].records.<ligand>@<node>.collected` | number (fmol) |
| `runs.<run>.rows[].records.<ligand>@<node>.supplied` | number (fmol) |
| `runs.<run>.rows[].site_heat_pJ` | object: every facing node |
| `runs.<run>.rows[].site_heat_pJ.<node>` | number (pJ) |
| `runs.<run>.rows[].site_occupied_fraction` | object: every population |
| `runs.<run>.rows[].site_occupied_fraction.<population>` | number |
| `runs.<run>.capacities` | object: every set |
| `runs.<run>.capacities.<set>` | number (fmol) |
| `runs.<run>.free_sites` | object: every set |
| `runs.<run>.free_sites.<set>` | string: `state` or `derived` |
| `runs.<run>.events` | list |
| `runs.<run>.events[]` | object |
| `runs.<run>.events[].kind` | string: `wash` |
| `runs.<run>.events[].operator` | string: `cells.operator.scheduled_compartment_wash@1` |
| `runs.<run>.events[].node` | string |
| `runs.<run>.events[].after_step` | integer |
| `runs.<run>.events[].time_s` | number |
| `runs.<run>.events[].collected` | object: every ligand |
| `runs.<run>.events[].collected.<ligand>` | number (fmol) |
| `runs.<run>.events[].supplied` | object: every ligand |
| `runs.<run>.events[].supplied.<ligand>` | number (fmol) |
| `runs.<run>.event_map` | list |
| `runs.<run>.event_map[]` | object |
| `runs.<run>.event_map[].state_step` | integer |
| `runs.<run>.event_map[].variant` | string: `numpy` or `compiled` |
| `runs.<run>.event_map[].node` | string |
| `runs.<run>.event_map[].fraction` | number |
| `runs.<run>.event_map[].buffer_mM` | object |
| `runs.<run>.event_map[].buffer_mM.<ligand>` | number (mM) |
| `runs.<run>.event_map[].before` | object |
| `runs.<run>.event_map[].before.amounts` | object |
| `runs.<run>.event_map[].before.amounts.<observable>` | number (fmol) |
| `runs.<run>.event_map[].before.records` | object |
| `runs.<run>.event_map[].before.records.<ligand>@<node>` | object |
| `runs.<run>.event_map[].before.records.<ligand>@<node>.collected` | number (fmol) |
| `runs.<run>.event_map[].before.records.<ligand>@<node>.supplied` | number (fmol) |
| `runs.<run>.event_map[].after` | object |
| `runs.<run>.event_map[].after.amounts` | object |
| `runs.<run>.event_map[].after.amounts.<observable>` | number (fmol) |
| `runs.<run>.event_map[].after.records` | object |
| `runs.<run>.event_map[].after.records.<ligand>@<node>` | object |
| `runs.<run>.event_map[].after.records.<ligand>@<node>.collected` | number (fmol) |
| `runs.<run>.event_map[].after.records.<ligand>@<node>.supplied` | number (fmol) |
| `runs.<run>.step_report` | object in W5's runs; else null, and null in a W5 run refused at parse |
| `runs.<run>.step_report.step` | integer: 1 |
| `runs.<run>.step_report.h_s` | number: `dt_s`/2 |
| `runs.<run>.step_report.loads` | list |
| `runs.<run>.step_report.loads[]` | object |
| `runs.<run>.step_report.loads[].kind` | string: `L_n`, `L_R` or `L_B` |
| `runs.<run>.step_report.loads[].id` | string |
| `runs.<run>.step_report.loads[].sums` | list |
| `runs.<run>.step_report.loads[].sums[]` | string: a population |
| `runs.<run>.step_report.loads[].per_s` | number (per s) |
| `runs.<run>.step_report.max_load` | object: one of `loads` |
| `runs.<run>.step_report.max_load.kind` | string |
| `runs.<run>.step_report.max_load.id` | string |
| `runs.<run>.step_report.max_load.sums` | list |
| `runs.<run>.step_report.max_load.sums[]` | string |
| `runs.<run>.step_report.max_load.per_s` | number (per s) |
| `runs.<run>.step_report.h_max_load` | number |
| `runs.<run>.step_report.limit` | number: 0.5 |
| `runs.<run>.step_report.verdict` | string: `refused` or `admitted` |
| `runs.<run>.refusal` | object, or null in a completed run |
| `runs.<run>.refusal.kind` | string: `stage`, `check`, `definition`, `domain` or `harness` |
| `runs.<run>.refusal.raised` | string, or null in a `harness` refusal that no exception ended |
| `runs.<run>.refusal.book` | string for `check` (`moiety ledger`, `energy ledger`, `dissipation check`, `host check: <name>`); else null |
| `runs.<run>.refusal.name` | string |
| `runs.<run>.refusal.message` | string |
| `runs.<run>.refusal.step` | integer, or null at parse |
| `runs.<run>.refusal.time_s` | number, or null at parse |
| `runs.<run>.checks` | object, or null before parse |
| `runs.<run>.checks.<check>` | object |
| `runs.<run>.checks.<check>.failures` | list |
| `runs.<run>.checks.<check>.failures[]` | object |
| `runs.<run>.checks.<check>.failures[].step` | integer |
| `runs.<run>.checks.<check>.failures[].message` | string |
| `runs.<run>.operators` | list, in declared order |
| `runs.<run>.operators[]` | string: an ID in today's spelling |
| `runs.<run>.inputs` | object, or null before parse |
| `runs.<run>.inputs.world` | string |
| `runs.<run>.inputs.constants` | object |
| `runs.<run>.inputs.constants.sites_per_fmol` | number |
| `runs.<run>.inputs.constants.temperature_K` | number |
| `runs.<run>.inputs.constants.RT_pJ_per_fmol` | number |
| `runs.<run>.inputs.nodes` | list |
| `runs.<run>.inputs.nodes[]` | object |
| `runs.<run>.inputs.nodes[].id` | string |
| `runs.<run>.inputs.nodes[].kind` | string: `node` or `cell` |
| `runs.<run>.inputs.nodes[].volume_pL` | number |
| `runs.<run>.inputs.nodes[].registered` | boolean |
| `runs.<run>.inputs.patches` | list |
| `runs.<run>.inputs.patches[]` | object |
| `runs.<run>.inputs.patches[].id` | string |
| `runs.<run>.inputs.patches[].inside` | string |
| `runs.<run>.inputs.patches[].outside` | string |
| `runs.<run>.inputs.ligands` | list |
| `runs.<run>.inputs.ligands[]` | string |
| `runs.<run>.inputs.free_amounts` | list |
| `runs.<run>.inputs.free_amounts[]` | object |
| `runs.<run>.inputs.free_amounts[].ligand` | string |
| `runs.<run>.inputs.free_amounts[].node` | string |
| `runs.<run>.inputs.free_amounts[].n_fmol` | number |
| `runs.<run>.inputs.free_amounts[].declared` | boolean |
| `runs.<run>.inputs.sets` | list |
| `runs.<run>.inputs.sets[]` | object |
| `runs.<run>.inputs.sets[].id` | string |
| `runs.<run>.inputs.sets[].shared` | boolean |
| `runs.<run>.inputs.sets[].owner` | string: a node or a patch |
| `runs.<run>.inputs.sets[].face` | string (`inside` or `outside`) for a patch's set; null for a node's |
| `runs.<run>.inputs.sets[].faces` | string |
| `runs.<run>.inputs.sets[].copies` | number |
| `runs.<run>.inputs.sets[].sites_per_copy` | integer |
| `runs.<run>.inputs.sets[].accessible_fraction` | number |
| `runs.<run>.inputs.populations` | list |
| `runs.<run>.inputs.populations[]` | object |
| `runs.<run>.inputs.populations[].id` | string |
| `runs.<run>.inputs.populations[].set` | string |
| `runs.<run>.inputs.populations[].ligand` | string |
| `runs.<run>.inputs.populations[].k_on` | number (per mM per s) |
| `runs.<run>.inputs.populations[].k_off` | number (per s) |
| `runs.<run>.inputs.populations[].initial_occupancy` | number |
| `runs.<run>.inputs.wash` | object, or null without a wash |
| `runs.<run>.inputs.wash.time_s` | number |
| `runs.<run>.inputs.wash.node` | string |
| `runs.<run>.inputs.wash.fraction` | number |
| `runs.<run>.inputs.wash.buffer_mM` | object |
| `runs.<run>.inputs.wash.buffer_mM.<ligand>` | number (mM) |
| `runs.<run>.inputs.permeabilities` | list |
| `runs.<run>.inputs.permeabilities[]` | object |
| `runs.<run>.inputs.permeabilities[].patch` | string |
| `runs.<run>.inputs.permeabilities[].ligand` | string |
| `runs.<run>.inputs.permeabilities[].value` | number (the engine's own unit) |
| `runs.<run>.inputs.multipliers` | list |
| `runs.<run>.inputs.multipliers[]` | object |
| `runs.<run>.inputs.multipliers[].of` | string: a population or a set |
| `runs.<run>.inputs.multipliers[].name` | string: the engine's own name |
| `runs.<run>.inputs.multipliers[].value` | number |
| `runs.<run>.inputs.charges` | object: every ligand |
| `runs.<run>.inputs.charges.<ligand>` | integer |
| `runs.<run>.inputs.dt_s` | number |
| `runs.<run>.inputs.observation_times_s` | list |
| `runs.<run>.inputs.observation_times_s[]` | number |
| `runs.<run>.inputs.horizon_s` | number |
| `runs.<run>.definition` | object, or null before parse: the engine's own form, not listed further |
| `runs.<run>.source` | object |
| `runs.<run>.source.engine_revision` | string: 40 hex digits |
| `runs.<run>.source.checkout_dirty` | boolean |
| `runs.<run>.source.snapshot` | string |
| `runs.<run>.source.snapshot_patch_sha256` | string: 64 hex digits |
| `runs.<run>.source.python` | string |
| `runs.<run>.source.numpy` | string |
| `runs.<run>.source.scipy` | string |
| `runs.<run>.source.jax` | string |
| `runs.<run>.source.jaxlib` | string |
| `runs.<run>.source.jax_enable_x64` | boolean: true |
| `runs.<run>.source.jax_platforms` | string: `cpu` |
| `runs.<run>.source.blas_threads` | integer |
| `runs.<run>.source.machine` | string |
| `runs.<run>.source.external_modules` | list |
| `runs.<run>.source.external_modules[]` | object |
| `runs.<run>.source.external_modules[].name` | string |
| `runs.<run>.source.external_modules[].identity` | string |
| `runs.<run>.source.external_modules[].frozen` | string |
| `runs.<run>.record` | string: a path relative to `table/` |
| `runs.<run>.record_sha256` | string: 64 hex digits |
