# The run view: one record that makes every run visualizable (design)

**Status: proposed, 14 November 2026, for the lead's review (the architecture block's item 4,
D154).** Docs only. No engine code is added or changed by this note; the declarations and the
writer it proposes are `src/` work that waits for the lead's word.

D154 asks that every experiment can eventually be visualized, through one run-view record that
every run writes beside its definition by one shared output path, never one per driver. The
record holds geometry, identity, record metadata, events, a representation per layer and a scale.
It is not fields in the definition, so definitions, bindings and crossrev stay unchanged. The
viewer is a read-only consumer.

**The consumer's draft.** The visualizer drafted the schema it reads, `cells.run_view@1`
(`visualizer/schema/RUN_VIEW.md` on branch `visualizer`, read here as a reference only). This
note keeps its file and field names and answers its four open points (§6). Its packaged replay
(`cells.visualizer.replay@1`: base64 payloads, catalogue, curated outcomes) stays the viewer's own.

**Engine models it runs (AGENTS.md):** the milestone that builds the writer exercises
`resolved_pump_composite@1` over `resolved_pump_tissue@3` on two worlds: a static heredity sheet,
and S5's compact partition world with a birth and a division (§5).

## 1. What the view is

- **One JSON file per run, `view.json`,** beside the run's definition: `resolved_config.json` in
  the engine's output paths, `definition.json` where a driver writes its own. A batch writes one
  per world, beside that world's definition.
- **Format `cells.run_view@1`,** with the draft's top-level fields: `run`, `time`, `space`,
  `layers`, `sets`, `records` and `events`.
- **Small.** It holds metadata, identity and geometry. Arrays stay in the run's own files, which
  each record names by file and array; nothing is copied.
- **Derived, never fed back.** It is built from the definition, the registered models' and
  operators' declarations, the run's saved files and two inputs from the caller: run labels and
  geometry. Writing it changes no result, and nothing reads it back into a run.
- **Written before the manifest,** so the manifest's checksums (`files_sha256`) cover it.
- **Deterministic.** The same run gives the same bytes: sorted keys, no host paths and no
  timestamps beyond the run's own.

## 2. Where each part comes from

| Part | Source | New declaration |
| --- | --- | --- |
| `run` | The caller: experiment, arm, seed and the source revision it records. The engine: the engine models (model ID; for a composite, inner and ordered operator IDs, as the manifest's `composition`) | None |
| `time` | The run's time bases, each named with its file and array: `trajectory.npz` has two, `accepted_times` (the state's rows) and `observation_times` (the observed columns), and the window files have their own. Each record names its base | None |
| `sets` | The definition's entities in slot order: cells, membranes, junctions, channels, outside nodes and faces, then each operator's own (electrodes, lumens, divisions, routes). Slots past the declared entities are padding, listed as null | The writer maps the declared axis names to sets. @3's own `STATE_AXES` use `cell_slot`, `membrane_slot`, `extracellular_slot`, `face_slot`, `edge_slot`, `channel_slot`, `gate` and `species`; operators add their own (`division_slot`, `exchange_route`, `reaction_route`, `regulatory_slot`), which map to their sets |
| `sets[].lifetimes` | `living_intervals`, already in the operator contract: each cell's birth and retirement. Today only the partition implements it. Replacement keeps the slot and changes its occupant, which the view gives as events and the `generation` record | None |
| `sets[].geometry` | The world's builder, passed to the writer by the caller (§4) | A `ViewGeometry` value; absent, the geometry is null |
| `space` | The geometry's unit and dimensions | With the geometry |
| `records` | Every array of the record file, with its axes and unit | Units and observation axes (§3) |
| `layers` | The inner model's declared layers, and each operator's (by default one per law, §3) | `VIEW_LAYERS` (§3) |
| `events` | Each operator's schedule and lifetimes (by default, §3) | `view_events` (§3) |

## 3. What models and operators declare (D142)

The view is assembled from declarations, so a new operator brings its part of the view with it,
as it brings its ledgers. Every addition is host-side and read only at write time; defaults keep
every program, binding and checkpoint unchanged. D172 makes the one inner model modular in place;
that changes where the inner model's declarations below live (with its modules), not what they
say.

- **Units.** Each model declares `UNITS`, field to unit, for its state and observation fields.
  Most names already carry their unit (`_V`, `_C`, `_A`, `_pJ`, `_pJ_s`, `_fmol_s`, `_pL`,
  `_m2`, `_F`, `_s`, `_mM`); a suffix rule covers them, and the table names the rest
  (`amount_increment`: fmol; `transferred`: fmol; `gate`: 1). A test fails when any field of the
  composite family resolves to no unit.
- **Observation axes.** `OBSERVATION_AXES` for the observation fields, as `STATE_AXES` gives the
  state's (for example `membrane_voltage_V`: membrane; `amount`: species, cell).
- **Layers.** `VIEW_LAYERS`: `{id, label, representation}`, the representation one of
  `simulated`, `modelled`, `prescribed` or null (the draft allows null). The inner model declares
  its own (for @3: membrane and ions simulated, channel populations modelled). The contract's
  default gives each operator one layer named by its law, with representation null. Each record's
  layer is its owner's, which the composition's field map already names (state owners,
  observation owner chains).
- **Events.** A contract method `view_events(spec, declaration, schedule)`, returning
  `{time, kind, layer, at, from, label}` entries with entities by id. The contract's default
  derives them from what every operator already declares: its `schedule_times` (kind: the law)
  and its `living_intervals` (births and retirements, with the cells by id). So S5's division
  event, the parent's retirement and the daughters' births, needs no edit to the partition.
- **Version 1 touches no operator's file.** It changes the contract (the two defaults), the inner
  model's declarations, the writer and its call sites. An operator's richer layer or events (a
  replacement's slot, donor and carrier; a dose's baths) come later from that operator's owner, in
  that operator's own milestone. That keeps S5's files, D152's, the coupling operator's and the
  bath schedule's with their owners.

## 4. The writer

- **One module, `cells/run_view.py`:** `view(spec, record_files, *, run=None, geometry=None)`
  returns the record; `write_view(directory, ...)` writes it.
- **Its callers are the shared output paths,** all four wired in version 1: `io.write_run`,
  `window_io.write_windowed_run`, `batch_io.write_batch_run` and
  `batch_window_io.write_windowed_batch`. A driver that writes its
  own record files (E07-v1's `records.npz`) calls `write_view` with a description of those arrays
  (id, axes, unit); it writes no view field itself.
- **Geometry is the caller's input.** Definitions hold no coordinates, and D154 keeps them out.
  The builders that make a world also give its geometry (the heredity sheet's hexagons; a
  division world's cells as points or spheres), and the writer checks it against the definition:
  known sets, one entry per declared entity, units stated. Static geometry is written inline in
  version 1.
- **Refusals,** with nothing written: a named array missing from its file; a shape that disagrees
  with its axes and sets; an id that is not the definition's; geometry for an unknown set or with
  the wrong count; a record without a unit.

## 5. The milestone and its checks

- **A static world:** a heredity sheet run through `io.write_run`, with the builder's geometry.
  Every named array exists with its stated shape; ids and order are the definition's; layers and
  units resolve; the bytes repeat.
- **A birth and a division:** S5's compact partition world (`tests/partition_fixtures.py`),
  through the windowed path. The parent's slot retires and the daughters' slots are born at the
  division (lifetimes from `living_intervals`), and the default events name the parent and both
  daughters. The test imports partition sources only, never a J1 source (the J2 bright line).
- **The batch paths:** a batch of two worlds writes two views, each beside its world's
  definition.
- **Unchanged:** every definition and fingerprint; crossrev identical in all seven sets of the
  da94f81 record; tier 1 and tier 2 with no changed outcome.

## 6. The draft's open points

- **File and granularity:** `view.json`, one per run (per world in a batch).
- **Geometry inline or in arrays:** inline while static and small (version 1). Large or changing
  geometry (vertex mechanics, growth) becomes a record with `role: geometry` in an array file the
  view names; the draft already describes that form.
- **Layer and representation:** declared by models and operators (§3), never by a driver.
- **Record names:** the engine's state and observation field names. They are stable within a
  model ID, since a renamed field is a model change; units come from §3.
- **Where this note departs from the draft:** `time` names several bases and each record names
  its own; `sets[].lifetimes` is new; padding slots are null in `ids`; a layer's representation
  may be null (the draft allows it in the replay, and the engine uses it for operators' default
  layers).

## 7. Options considered

| Question | Options | Recommended |
| --- | --- | --- |
| Geometry | (a) the builder's, passed by the caller; (b) positions in the definition; (c) a layout derived from topology by the writer | (a). (b) is ruled out by D154, and (c) is the viewer's work, as its adapters do today |
| Events | (a) a contract method per operator; (b) the writer reading each law's experiment keys | (a): (b) is a central switch over laws, which D142 avoids |
| Units | (a) a declared table with a suffix rule; (b) suffixes alone | (a): some fields have no suffix |
| Scope of version 1 | the composite family and the engine's shared paths, then the other families | The composite family first; others when a consumer asks |

## 8. What it does not do

- It adds no field to any definition and changes no program, binding or qualified result.
- It writes no view for runs already on disk. The visualizer's adapters keep deriving those
  (`derived: true`), as the draft says.
- It writes nothing per driver, and it adds no viewer code to the engine.
- It covers the cell scale; molecule, tissue, organ and organism stay placeholders.

## 9. For the lead

1. **Geometry from the builders** (§4, §7): accepted for version 1?
2. **One view per world in a batch,** beside that world's definition?
3. **Drivers' own record files:** described through `write_view` (§4), or out of version 1's
   scope until those drivers move to the shared paths?
4. **The `src/` work:** the declarations of §3, the writer and its four call sites. They are
   host-only and change no program, so crossrev stays identical. Version 1 would be one
   milestone after MG0c's `src/` hold, with tier 1 and tier 2. The inner model's declarations
   could come with D172's restructure round, and the contract defaults, the writer and its call
   sites before it.
5. **Operators' own layers and events** (§3): from each operator's owner after version 1, so that
   version 1 edits no operator's file?
