# The run view: one record that makes every run visualizable (design)

**Status: proposed, 14 November 2026, for the lead's review (the architecture block's item 4,
D154); revised 15 November for D174's requirement (§1).** Docs only. No engine code is added or
changed by this note. The declarations and the writer it proposes are `src/` work: the operator
contract's view interface (`VIEW_LAYERS`, `view_events`) reached main with D172's round on 16
November, and the operators' declarations and the writer merged into main the same evening
(050aa741; [current plan](CURRENT_PLAN.md)).

D154 asks that every experiment can eventually be visualized, through one run-view record that
every run writes beside its definition by one shared output path, never one per driver. The
record holds geometry, identity, record metadata, events, a representation per layer and a scale.
It is not fields in the definition, so definitions, bindings and crossrev stay unchanged. The
viewer is a read-only consumer.

**The consumer's draft.** The visualizer drafted the schema it reads, `cells.run_view@1`
(`visualizer/schema/RUN_VIEW.md`, on main since the visualizer's merges, read here as a reference
only). This
note keeps its file and field names and answers its four open points (§6). Its packaged replay
(`cells.visualizer.replay@1`: base64 payloads, catalogue, curated outcomes) stays the viewer's own.

**Engine models it runs (AGENTS.md):** the milestone that builds the writer exercises
`resolved_pump_composite@1` over `resolved_pump_tissue@3` on two worlds: a static heredity sheet,
and S5's compact partition world with a birth and a division (§5).

## 1. What the view is

**What it must expose (D174).** Every entity identity, every unit, every event, the model scope
and every representation, so that the viewer reconstructs no meaning from driver conventions:
- **identity:** every column of every recorded array names its entity (or is padding), and every
  axis maps to a set, species included;
- **units:** every recorded array, every geometry and the time bases;
- **events:** each with its time, kind and the ids of the entities it acts on;
- **model scope:** the engine models that ran (composite, inner and ordered operator IDs, with
  versions), the layer and owner of every record, and the scale;
- **representation:** of every layer, and of the geometry (a builder's static layout is
  prescribed, never simulated).

Whatever the view cannot state is refused at the writer or by a test, never left for the viewer
to infer.

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
| `run` | The caller: experiment, arm, seed and the source revision it records. The engine: the model scope, that is the engine models (model ID; for a composite, inner and ordered operator IDs, as the manifest's `composition`) and the scale | None |
| `time` | The run's time bases, each named with its file and array: `trajectory.npz` has two, `accepted_times` (the state's rows) and `observation_times` (the observed columns), and the window files have their own. Each record names its base | None |
| `sets` | The definition's entities in slot order: cells, membranes, junctions, channels, outside nodes and faces, then each operator's own (electrodes, lumens, divisions, routes). Slots past the declared entities are padding, listed as null | The writer maps the declared axis names to sets. @3's own `STATE_AXES` use `cell_slot`, `membrane_slot`, `extracellular_slot`, `face_slot`, `edge_slot`, `channel_slot`, `gate` and `species`; operators add their own (`division_slot`, `exchange_route`, `reaction_route`, `regulatory_slot`), which map to their sets |
| `sets[].lifetimes` | `living_intervals`, already in the operator contract: each cell's birth and retirement. Today only the partition implements it. Replacement keeps the slot and changes its occupant, which the view gives as events and the `generation` record | None |
| `sets[].geometry` | The world's builder, passed to the writer by the caller (§4), with its unit and its representation (a static layout is prescribed) | A `ViewGeometry` value; absent, the geometry is null and the view says so |
| `space` | The geometry's unit and dimensions | With the geometry |
| `records` | Every array of the record file, with its axes and unit | Units and observation axes (§3) |
| `layers` | The inner model's and each operator's declared layers, with their representations; each record's layer is its owner's (the composition's field map) | `VIEW_LAYERS` (§3) |
| `events` | Each event operator's declared events, with entity ids; births and retirements from `living_intervals` | `view_events` (§3) |

## 3. What models and operators declare (D142)

The view is assembled from declarations, so a new operator brings its part of the view with it,
as it brings its ledgers. Every addition is host-side and read only at write time, so none
changes a program, a binding or a checkpoint. D172 makes the one inner model modular in place;
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
  `simulated`, `modelled` or `prescribed`. The inner model declares its own (for @3: membrane and
  ions simulated, channel populations modelled), and so does every registered operator (for
  example replacement, partition, insertion and the bath schedule prescribed; water simulated).
  There is no default: a test fails for a registered operator without the declaration, as the
  composition matrix's test fails for an untagged refusal. Each record's layer is its owner's,
  which the composition's field map already names (state owners, observation owner chains).
- **Events.** A contract method `view_events(spec, declaration, schedule)`, returning
  `{time, kind, layer, at, from, label}` entries with entities by id. Births and retirements come
  from `living_intervals`, which the contract already has, so S5's division (the parent's
  retirement and the daughters' births) needs nothing more. Every operator with an event map or
  a schedule declares its own: replacement (slot, donor, carrier), insertion (onset patches and
  nodes), the bath schedule (baths and doses), injection (current changes, its electrode's cell)
  and the coupling operator (switches and writes, with their cells). A test fails for an event
  operator without it, so no event reaches the view without its entities.
- **The cost:** one declaration in every registered operator's file, and `view_events` in the
  event operators'. Those files have owners (S5's, D152's, the coupling operator's, the bath
  schedule's); the lead coordinates them (§10).

**As built (16 November 2026).** The operator contract carries these declarations
(`operators/contract.py`, "The run view"): `VIEW_LAYERS`, `view_events` (the default gives
the births and retirements of `living_intervals`, each at `{"cell": id}`), `view_sets(spec,
declaration)` for an operator's own axes, `OBSERVATION_AXES`, `UNITS`, `RECORD_KINDS`,
`ORIENTATION` and `RECORD_LAYERS`, checked at registration against the operator's own fields
(and `RECORD_DIAGNOSTICS` and `RECORD_REFERENCES`, for a looping package's closure). The inner
model declares its own in the same forms: `resolved_pump_tissue@3`'s view declarations, with
`RECORD_NOTES` and its record roles, each structure's with its kinds' folded in
(`models/surface_pump_v3.view_declarations`; the kinds' `VIEW_AXIS_SETS` and `view_sets`). The
writer reads them from the inner object and keeps no table of its own (the interim one went
when they reached main, a2af3899).

## 4. The writer

- **One module, `cells/records/run_view.py`:** `view(spec, record_files, *, run=None, geometry=None)`
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
  with its axes and sets; an axis with no set; an id that is not the definition's; geometry for an
  unknown set, with the wrong count, or without its unit or representation; a record without a
  unit or a layer; an operator in the composition without its layer declaration.

## 5. The milestone and its checks

- **A static world:** a heredity sheet run through `io.write_run`, with the builder's geometry.
  Every named array exists with its stated shape; ids and order are the definition's; layers and
  units resolve; the bytes repeat.
- **A birth and a division:** S5's compact partition world (`tests/partition_fixtures.py`),
  through the windowed path. The parent's slot retires and the daughters' slots are born at the
  division (lifetimes from `living_intervals`), and the events from `living_intervals` name the
  parent and both daughters. The test imports partition sources only, never a J1 source (the J2 bright line).
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
  is never null (the draft allows null in the replay; the engine always states it, §3).

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

## 9. Door S's merged view at observation (route B; the lead, 16 November 2026)

The visualizer's request 5, answered (a): a view field a layer reads is a record wherever the
composition changes it, and a constant of the definition otherwise.

- **What counts as changed:** each provider's fields (the field map's provider, or its chain of
  changes in merge order) and, with any closer, every activity mask and the padded view fields
  (`extracellular_amount_reference`, `initial_cell_charge_C`), since `close()` propagates closure
  and pads closed slots. Before this, the writer stated those masks and the initial charge as
  constants in a division world, which was wrong.
- **What is saved:** with `view=` only, an array `view_<field>` per changed field beside the
  observation base (in `trajectory.npz`, or in each chunk). It is re-formed at write time by the
  composite's own host view function, the call `observe_history` makes for that row, from the
  run's bound layout and the observed state; so it is the view the host observer formed for the
  row's saved readouts, bitwise (the tests capture the observer's views and compare), not the
  device step's own formation. The recording subset's cadence and elements apply to it.
- **Refused at write time:** a field of the table that no change declares but that differs from
  its bound value at an observed row; an operator that replaces a column named like a state field.
- **Not covered, and stated as unstated with the reason:** a run already on disk (`write_view`:
  its manifest's checksums cover its payload) and a run that saved no observed rows.
- **Event rows** (`time.event_rows`): an event acts at the start of the step that leaves its time,
  so the row saved at that time holds the state before it and the next row the state after it
  (shown on S5's division and on a bath dose).
- **Why not the composite's own columns (route A):** new observation columns would change every
  such composition's outputs, its field map and manifests; the results baseline's comparison takes
  the union of array names, so the bitwise gate would fail on them.
- **After D172's landing (the cleaner variant):** the composite declares its changed set in one
  method of `pump_composite.py`, and the writer reads that instead of the adapter's tables
  (`MASK_FIELDS`, `PADDED_FIELDS`), a stopgap named as such in the code until then.

**Additions to `cells.run_view@1` as built (16 November 2026),** from door S and the visualizer's
reading of the worked example (its eleven items):
- **`view_<field>` records** on the observation base: the merged view (above).
- **`roles` on every set with ends** (`{role: what it is}`): the inner sets' from the writer, an
  operator's from its `view_sets`. A flow's `sign` names two of them as `from` and `to`; a
  difference (a voltage) gives `difference` with `plus` and `minus` instead (plus less minus).
  The voltages' were read from the code and said so (`source`); @3's own declarations now state
  them, `confirmed` by the core's owner.
- **Per-entity facts on an operator's sets:** `carries` (species), `direction` and `kinds`
  (words), `at` (`{set id: entity id}`); a set may describe entities no field has as an axis
  (turnover's routes). A label such as "secreted" stays the reader's, from these facts.
- **`resets.mask`:** the mask whose closing marks the slots that restart.
- **`time.event_rows`:** the row saved at an event's time holds the state before it.
- **`run.id`** (a caller label), **`run.end`** (status, time, step) and **`run.source`** (the
  running engine's revision and dirty flag, from its execution snapshot's record, where a shared
  path writes the view; unstated with the reason otherwise). A view written later by
  `write_view` therefore differs from the run's own in its source.
- **`loop`** (optional; FR-11, [LOOPING_REPLAY_DESIGN](LOOPING_REPLAY_DESIGN.md) §3): a looping
  package's block, written only when the run's observed rows close within its tolerance.
- **`diagnostic` and `reference` on records:** the owner's `RECORD_DIAGNOSTICS` (a residual of
  the step's own check) and `RECORD_REFERENCES` (stored as an increment over a fixed reference,
  stated as a named constant of the view, or the merged view's record under door S).

**The lead's rulings on these (16 November 2026):** the voltages' plus and minus are to be stated
in the core's own @3 declarations (core-next), and until then the view's `source` citing the code
stays; no "secreted" label (the facts are stated, the label is the reader's); `run.source` from
the execution snapshot's own record is AGENTS.md's provenance, with no source-file hashes in the
view; `resets.mask` as worded, with a junction fixture to cover it and the junction voltage on data;
a later `write_view` view names no engine source and says why.

## 10. For the lead

1. **Geometry from the builders** (§4, §7): accepted for version 1?
2. **One view per world in a batch,** beside that world's definition?
3. **Drivers' own record files:** described through `write_view` (§4), or out of version 1's
   scope until those drivers move to the shared paths?
4. **The `src/` work:** the declarations of §3, the writer and its four call sites. They are
   host-only and change no program, so crossrev stays identical. Version 1 would be one
   milestone after MG0c's `src/` hold, with tier 1 and tier 2. The inner model's declarations
   could come with D172's restructure round, and the contract's `view_events`, the operators'
   declarations, the writer and its call sites before it.
5. **Operators' declarations** (§3): every registered operator's layer, and the event operators'
   `view_events`, are needed for the view to state every representation and every event's
   entities (D174). They touch files with other owners: in version 1, coordinated by the lead, or
   in each owner's next milestone with the view refusing worlds whose operators lack them?
