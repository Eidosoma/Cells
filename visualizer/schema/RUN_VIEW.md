# Run view: what a run saves so that it can be visualised

Status: **draft from the visualizer side, 14 November 2026**, for the lead's design note
under D154. Names here are proposals; the engine-side note fixes the final file and field
names, and the viewer adapts. **From 15 November 2026 the engine's own run-view writer
exists** (first on a development branch, with a worked example; on main since 050aa741, 16 November 2026). Where its view and the proposals below
differ, the writer's view stands, and the viewer reads it as written: see "The engine's
view".

D154 requires that every experiment can eventually be visualised through one run-view
output, written by one shared run-output path. This note says what the viewer needs from
that output, and why.

## Principles

1. **The viewer reads saved files only.** It never imports the engine or a driver (D006).
2. **Nothing is implied by position.** Every recorded array says which entity each column
   is. Today `records.npz` has `vm` with shape (623, 127) and the reader must know that
   column 5 is `cell_5`.
3. **Geometry is saved, not rebuilt.** Cell positions live only in a driver's `sheet()`
   builder today. The viewer must not re-run a driver to find them.
4. **Units are stated** for every coordinate and every record.
5. **The run declares how each layer is represented:** simulated, modelled in aggregate, or
   prescribed. The viewer draws illustrative machinery only for layers declared as modelled,
   and marks it as illustration.
6. **The view file is small.** It holds metadata and geometry and points at arrays in the
   run's existing files. It copies no large array.
7. **The format is versioned,** like every other Cells identifier.

## Proposed shape

One JSON file beside `definition.json` (proposed name `view.json`):

```json
{
  "format": "cells.run_view@1",
  "run": {
    "experiment": "e07-v1",
    "arm": "a-donor-central-k1-d37-s0.6",
    "seed": 1,
    "engine_models": ["resolved_pump_replacement@1"],
    "revision": "4465b48"
  },
  "time": {"unit": "s", "file": "records.npz", "array": "t"},
  "space": {"unit": "um", "dimensions": 2},
  "layers": [
    {"id": "membrane", "label": "Membrane voltage and ions", "representation": "simulated"},
    {"id": "channels", "label": "Channel populations", "representation": "modelled"},
    {"id": "replacement", "label": "Cell replacement", "representation": "prescribed"}
  ],
  "sets": [
    {
      "id": "cell", "scale": "cell",
      "ids": ["cell_0", "cell_1"],
      "geometry": {"kind": "polygons", "vertices": [[0.0, 0.0]], "faces": [[0, 1, 2, 3, 4, 5]]}
    },
    {
      "id": "junction", "scale": "cell",
      "ids": ["junction_0"],
      "geometry": {"kind": "links", "between": "cell", "ends": [[0, 8]]}
    }
  ],
  "records": [
    {"id": "vm", "label": "Membrane voltage", "unit": "V", "set": "cell", "layer": "membrane",
     "file": "records.npz", "array": "vm", "axes": ["time", "cell"]},
    {"id": "conc", "label": "Concentration", "unit": "mM", "set": "cell", "layer": "membrane",
     "file": "records.npz", "array": "conc", "axes": ["time", "species", "cell"],
     "species": ["Na", "K", "M"]},
    {"id": "junction_abundance", "label": "Junction abundance", "unit": "1", "set": "junction",
     "layer": "replacement", "file": "records.npz", "array": "abundance",
     "axes": ["time", "junction"]}
  ],
  "events": [
    {"time": 9.45, "kind": "replacement", "layer": "replacement",
     "at": {"cell": "cell_108"}, "from": {"cell": "cell_107"}, "label": "n0"}
  ]
}
```

## Fields

| Field | Needed for | Notes |
| --- | --- | --- |
| `run` | The replay's title and provenance | Experiment, arm, seed, the engine models it ran and the revision. AGENTS.md already asks every milestone to name its engine models |
| `time` | The timeline | Unit and the array that holds the record times |
| `space` | Placing geometry | Unit and 2 or 3 dimensions |
| `layers[].representation` | Honest drawing | `simulated`, `modelled` or `prescribed` |
| `sets[]` | Identity | One per kind of entity: cells, membranes, junctions, channels, extracellular nodes, vertices. `ids` gives the order used by every array on that set |
| `sets[].scale` | Zoom levels | `molecule`, `cell`, `tissue`, `organ` or `organism` |
| `sets[].geometry` | Drawing | See the kinds below |
| `records[]` | Colour, height and charts | Each names its file, array, axes, unit, set and layer |
| `events[]` | Markers and animation | Time, kind, the entities involved and a label |

**Geometry kinds.** Each is the least the viewer needs to draw that set.

| Kind | Fields | Used by |
| --- | --- | --- |
| `points` | `centres`, optional `radius` | Cells known only by position; extracellular nodes |
| `polygons` | `vertices`, `faces` | Cells in a sheet; the vertex model |
| `links` | `between`, `ends` | Junctions and contacts between entities of another set |
| `on` | `set`, `index` | Channels and pumps on a membrane; patches on a cell |
| `spheres` | `centres`, `radius` | The egg and its daughters in division |

**Geometry that changes** (vertex mechanics, growth, division) is a record whose `role` is
`geometry`, for example `{"role": "geometry", "set": "cell", "what": "vertices",
"array": "position", "axes": ["time", "vertex", "xy"], "unit": "um"}`. Topology that changes
(division, removal) is a list of events plus a per-record activity mask.

## What existing runs lack

Checked on E07-v1's judged run (`definition.json`, `records.npz`, `plan.json`):

| Need | Today | Gap |
| --- | --- | --- |
| Identity | `definition.json` lists cells, membranes, junctions and channels in array order | Order is implied; fine for an adapter |
| Topology | Junctions name their `sender` and `receiver` | None |
| Geometry | Only areas and volumes | **No coordinates** |
| Records | `records.npz`: `t`, `vm`, `conc`, `osm`, `abundance`, `gate`, `generation` | No units or axes written down; no kind, no sign and no owner; no species for the rows of `conc` (the adapter checks them against the definition at the first record); `osm` is not packaged, since no layer reads it |
| Events | `definition.json` `replacement_events`, `plan.json` `events` | None |
| Representation | Not stated | Missing |

## Until the engine writes this

The visualizer keeps adapters under `visualizer/tools/` that build the same structure from
an existing run directory and mark it `"derived": true`, with a line saying how each missing
piece was derived. For E07-v1 the sheet is a regular hexagonal sheet, so positions are
derived from the saved junction topology. Adapters read saved files only.

## The engine's view

The engine's run-view writer (`cells.run_view@1`: one `view.json` beside a run's files)
**is on main since `050aa741` (16 November 2026):** `src/cells/records/run_view.py`
(`src/cells/run_view.py` until the engine's second source move, D188, which left the format as it
was; the five worlds kept from before and after it are the same files), with its format
in `docs/RUN_VIEW_DESIGN.md` (§3, §4 and §9) and the loop's in `docs/LOOPING_REPLAY_DESIGN.md`
(§2 and §3). It grew on the development branch `run-view-d154`, which main merged without a
rebase, so the branch's revisions cited here (`fd008813`, `d7a11d5b`, `b08af640`) stay as they
are, and main holds them. The writer and both notes at main's `050aa741` are the same as at
`b08af640`, so everything said here of `b08af640` holds for main's writer; the runs written
with it stay what they are, development runs with no verdict. The adapter reads the writer at
`fd008813`, at `d7a11d5b` (the loop block and a record's `diagnostic` and `reference`) and at
`b08af640` and `050aa741`. At `b08af640` the writer drops its
interim table of @3's fields and takes the engine's own view declarations and record roles
(@3's `UNITS`, `OBSERVATION_AXES`, `RECORD_KINDS`, `ORIENTATION`, `RECORD_LAYERS`,
`VIEW_LAYERS`, `RECORD_NOTES`, `RECORD_DIAGNOSTICS` and `RECORD_REFERENCES`, folded with its
kinds'); the items below say what that changes. It was first shown on 15 November 2026, on a
worked example made from the development run of one cell that secretes a species, and its
format grew on 16 November. The adapter reads every shape. Each addition is read only where a
view gives its key, so a view of an earlier shape is packaged exactly as before. Kept as
fixtures (`tests/engine-views/`): small runs that the writer wrote at `fd008813` (three
worlds), at main's `050aa741` (five) and at main's `b5d3faf0` (the same five after the engine's
second source move: the same files but for the label the script plants, and packaged alike,
as `tests/adapt_run_layouts.test.mjs` holds), made by `tools/make_engine_view_fixture.sh`; and the
interim planarian loop, a development run with no verdict, as the writers at `d7a11d5b` and
`b08af640` wrote it from execution snapshots (copied from the engine's lead's folder). The
`b08af640` one is packaged for the page as a development run (`data/replays`, experiment
`planarian-loop`). The interim shape (`fd008813`, `d7a11d5b`) is kept beside the new one:
reading it costs no code of its own. The engine has three format follow-ups queued (its
lead, 16 November 2026): `kinds` to hold words with a law's ID under a key of its own; a
statement of what `carries` means; a reference constant written only where a record names
one. Until they land the adapter reads past them as below. The writer
conforms to most of this note. Where it differs, by design, the viewer reads what the writer
gives:

- **Two time bases.** `time` is `{"unit": "s", "bases": [...]}`, each base
  `{"id", "array", "says", "files": [{"file", "rows": [from, to]}]}`: the state's rows
  (`accepted`) and the observed rows (`observation`), each with the files that hold it and
  the rows in each file. Every record names its `base`. There is no `time.file` and no
  `time.array`. `time.event_rows` (16 November) is the writer's sentence on which state a
  record saved at an event's time holds: the state before the event, the next record the
  state after it. The adapter carries the sentence as written (`view.time.event_rows`) and
  derives no word from it.
- **A record's file comes from its base, and it has no label.** A record has `id` (its
  array's name), `field` (the engine's name for the quantity), `array`, `base`, `axes` over
  sets (the species among them), `set`, `unit`, `layer` and `owner`. What the page calls a
  field is the viewer's own catalogue of names.
- **Padding slots are null, and cells carry lifetimes.** A set's `ids` holds null for a slot
  that has no entity, and every array keeps a column for it. `cell.lifetimes` gives, for
  each cell, null or its birth and its retirement (either may be null).
- **Signs name roles, and each set states its roles.** From 16 November every set with
  ends gives `roles`, `{role: what it is}`: `inside` and `outside` for a membrane patch and
  what lies on one, `sender` and `receiver` for a junction or a face, `exterior` and `node`
  for an outside node. A flow's `sign` is `{"says", "from", "to", "confirmed"}`, with `from`
  and `to` two roles of the record's set: a positive value goes from `from` to `to`. The
  proposals above, and the viewer's older packages, say `first` and `second`, or `cell` and
  `outside node`; the viewer reads both sets of words. The 15 November shape gives no
  `roles`, and its signs are read as written. The adapter carries each set's `roles`, and
  refuses a sign that names what are not two roles of its set. From `b08af640` the signs are @3's own declarations, `confirmed` by the
  core's owner from the code, and the flux rates (`membrane_flux_fmol_s` and the others) carry
  the signs of their totals; the page packages none of the rates.
- **A voltage is a difference** (16 November). In place of `sign` a voltage's record gives
  `difference`, `{"says", "plus", "minus", "source"}`: the value is plus less minus, two
  roles of its set, so it is positive when `plus` is the higher. At `fd008813` the
  membrane's voltage is its cell's potential less its outside node's and a junction's its
  sender's less its receiver's, and `source` says that both are read from the code, for the
  core's owner to confirm. From `b08af640` the same
  differences are @3's own declarations and carry `confirmed` in place of `source` ("the
  core's owner, from the code (core-next, 16 November 2026)"). The adapter carries `difference` as written and gives the
  record the page's `sign`: the view's `says`, its `source` or `confirmed` (whichever the
  view gives) as written, and `high`, the end the page calls the higher, from the role
  `plus` (`inside` and `outside` as they are; a link's `sender` as `first`, its `receiver`
  as `second`: on the interim planarian loop's twelve junctions the saved voltage is the
  sender's potential less the receiver's at every row, bit for bit).
  Where a role has no such word the record gets no sign, and the page draws no direction
  for it. A record with both `sign` and `difference`, or a difference that does not name
  two roles of its set, is refused.
- **Constants have no label and no set.** A constant has `id`, `unit`, `axes`, `values`,
  `from` and `says`; the set it lies on is the one its values run along, beside the species.
  A flag (true or false) is no number a layer reads, and is left out.
- **What the composition changes is a record, not a constant** (door S, 16 November). A view
  field that an operator provides, or that closure changes (every activity mask, and the
  padded fields), is saved as its merged view at each observed row: a record whose `id` and
  `array` are `view_<field>` and whose `field` is the field's own name, on the base
  `observation`. The adapter packages those that a layer reads by the field's name
  (`volume`, `extracellular_volume`, `membrane_area`, `membrane_capacitance`) under that
  name, with `array` naming the merged view; the derivation names the others, which are not
  packaged. A field that a view states both as a constant and as a merged view is refused.
- **Added by the writer:** (from `b08af640`, so in main's writer, it
  refuses a field of the inner model that its declarations give no unit, axes or layer, and
  lists one they give no kind under `unstated`, as `kind`, with the reason) `constants`; `unstated` (`[{"id", "what", "why"}]`: what the
  view does not state, with the reason); `recording` (`{"mode", "subset"}`: whether only
  some fields, elements or rows were recorded); a layer's `owner` beside its
  representation, which is never null; a record's `writers` and `note`; and for a total
  either `"monotone": "non-decreasing"` or `resets`.
- **A total that restarts.** A dissipated-energy ledger only grows (`monotone`), except
  where an operator retires a slot: the retired slot's history moves into that operator's
  own record, and the ledger restarts at nought on that slot. Such a record carries
  `"resets": {"by": [laws], "says": "...", "mask": "..."}` in place of `monotone`. `mask`
  (16 November) names the activity mask of the record's set (`membrane_active`, say): the
  slots that restart are those where that mask closes at the event, as its merged view
  `view_<mask>` shows where the run saved one. The adapter carries `resets` whole, and
  refuses a `mask` that is no name. No rate is taken across a reset
  (`schema/QUANTITY_LAYERS.md`, rule 1): the events of the layers that those laws own say
  when it happens, and the page traces each entity to its cell, as before.
- **More about the sets.** `species.valence`, and `species.species` (each species'
  identity, and the operator that declares it); `outside.reservoir` (the held baths); a
  membrane set that `holds` "membrane patch", with each patch's `laws`, `pumps` (null, or
  `{"id", "law_id", "per_cycle": [{"role", "species", "count"}], "per_cycle_sign":
  "inward-positive"}`) and `calcium_pumps`; an operator's own sets (`exchange_route`, which
  `holds` "exchange route", lies on its membrane and names its `owner`); and the sets
  `node`, `world`, `gate` and `floating_component`.
- **What an operator states of each of its entities** (16 November): `carries` (the species
  each carries), `direction` and `kinds` (a word each, the operator's own: `export` or
  `import`, `production` or `clearance`) and `at` (`{set id: entity id}`, the entity each acts
  at), one value for each id. A set may describe entities that no record lies on (turnover's
  routes, `turnover_route`). From `b08af640` an entry
  of `carries` is one species id or a list of them, and the inner model's kinds declare sets
  of their own, owned by the inner model (the passive routes' `passive_route`, which carries a
  list for each route, names its law under `kinds` and its patch or junction under `at`). A
  list in `carries` means, in the engine's lead's words (16 November 2026), that each species
  moves through the route with its own flux, not as a coupled set: a coupled stoichiometry is
  a cycle, declared by the transporter kind. A law's ID under `kinds` is a mismatch with the
  format (`kinds` are words), queued to be fixed with the law's ID under a key of its own; the
  adapter carries `kinds` as written meanwhile, and reads no meaning into it. The
  adapter carries every such set: `carries` as the set's `species` (what the page reads for a
  route; a list stays a list) and the others as written. A list that is not one value for
  each id, a species that is not the run's, an empty list, or an entity that is not the
  view's, is refused.
- **The secreted species is the viewer's word.** The view calls no species secreted (the
  lead's ruling of 16 November). Where the operators' sets state `carries`, the package's
  `species.secreted` is the species they carry, make or clear (only an operator's sets: a
  kind's set of the inner model, such as its passive routes, is not read for it); in the 15 November shape it
  is the species whose identity an operator declares. Either way the derivation says that
  this is the viewer's reading.
- **Events name entities by id** (`"at": {"cell": "cell_0"}`), and a cell's birth and its
  retirement are events. A replay runs over its records: an event the run states outside
  their span (a looping run keeps only its last period) is not carried as an event, and the
  derivation says how many there are and when, the first and the last.
- **The run** (16 November). `run.id` is the caller's label for the run: the derivation
  names it, and the catalogue keeps its own ids. `run.end` (`{"status", "time", "step"}`) is
  how the run ended: the package's `stop` is its status, `run.end` is carried, and a view
  whose end is before its last record, or whose status is not the one in the run's
  `summary.json`, is refused. `run.source` (`{"revision", "dirty", "from"}`) is the running
  engine's revision and whether its tree was dirty, from its execution snapshot's record;
  it is the engine's one word for its revision. The package's `run.revision` is filled from
  `run.source.revision`, `run.source` is carried, and the derivation says whether the tree
  was clean or dirty. A caller's `run.revision` that names another revision is refused (a
  short form of the same one is not). Where the view states no source, `unstated` says why
  (the engine ran from a checkout or an export, not an execution snapshot, or the view was
  written later for a run on disk); a caller's `run.revision` is then carried as that
  label, and the derivation says that it is not the engine's own record of its source.
- **A builder's geometry.** `space` is null and each set's `geometry` is null where the
  caller gave no geometry, and `unstated` says so. Where the caller gave it, `space` is
  `{"unit", "dimensions", "representation", "source"}` (a builder's layout is
  `prescribed`) and the cells carry `points`, `spheres` or `polygons`. The adapter reads the
  cells' `polygons` in two dimensions: the picture stands each cell where the run puts it, in
  um, with corners that coincide (within a billionth of the drawing's extent) given one index
  so that the page finds the edge two cells share, and the derivation gives the largest
  distance so joined. The adapter's own layout of the cells is then not used, and it lays
  out no tiles of its own for the outside nodes beside them. Where the view gives no
  geometry, or another kind, the adapter lays the cells out itself and says so.
- **A recorded subset** (`recording.subset`, `{"fields", "elements", "every"}`, the run's own
  statement of what it saved; `recording.mode` says which bases it saved, `"observations"`
  for the observed rows only). `fields` are the writer's names of the fields kept (a merged
  view by its `view_<field>`), and every record of the view is of one of them; a set whose
  elements were kept gives `recorded`, the indices of those entities in its `ids`, and its
  arrays hold only their columns, in that order; the observed rows are one in every `every`,
  from the first. The adapter packages what was recorded: the replay's records are the rows
  kept, and a field saved once for each species is packaged for the recorded species only (the
  species set stays whole). Of the fields the page has a name for that the run could have
  recorded (not a ledger of an operator its composition lacks, nor a field over a set it has
  no entity of: of those, nothing is said, as for a full recording), each that the subset does
  not list is named in the derivation and listed in the package's `unstated` with the reason
  ("The run's recording subset does not list it"); nothing is packaged for it and nothing
  stands in for it, so a layer that needs it says the run did not save it. Refused: a subset
  that does not give its fields, elements and cadence; a record of a field the subset does not
  keep; a `recorded` that is not the elements the subset names, or one without them; and, for
  now, a subset of the entities of any set but the species (the page draws every entity of a
  set it shows).
- **A record's `diagnostic` and `reference`** (the roles from `d7a11d5b`; declared by @3
  itself from `b08af640`, so in main's writer). `diagnostic` says, in
  words, that the record is the residual of the engine's own check, held to its own
  tolerance, and not a quantity of the simulated world: at `b08af640` @3's
  `charge_residual_C`, `component_current_residual_A` and `energy_balance_pJ_s`. The page
  shows none of them; the derivation counts them and quotes the view's words. `reference`
  (`{"constant"}`, `{"record"}` or `{"field"}`: one id) says that the record is stored as an
  increment over a fixed reference, so its quantity is the reference plus the record: at
  `b08af640` `amount_increment` over `amount_reference` and `extracellular_amount_increment`
  over `extracellular_amount_reference`. A reference that no view field states is a named
  constant of the view (`amount_reference`, `fmol` over `["species", "cell"]`, from
  `b08af640`); one the composition changes is its merged view's record; one the run did not
  save is named as a field only. The derivation counts the records so stored. Where the run
  saved no record of a level the page reads (`amount`, `extracellular_amount`) but saved its
  increment, the adapter works the level out as the reference plus the increment, row by
  row: the record names its `reference`, its note says that the viewer worked it out from
  which constant and which record, and the derivation says so. A reference the run did not
  save cannot be added, and the level is then not packaged, with that said. A page field
  stored over a reference that the adapter does not add is not packaged. A `diagnostic` with
  no words, or a `reference` that is not one constant, record or field of the view, is
  refused.
- **The loop block** (FR-11, `docs/LOOPING_REPLAY_DESIGN.md`, on main since `050aa741`; ruled by the lead
  on 16 November 2026), written from `d7a11d5b` on: `loop: {"species", "cell_type"?, "cell",
  "period", "closes": {"within", "tolerance", "says", "zero"}, "not_measured": [{"why",
  "records"}], "follows"?}`. `cell_type` (from `0fac9d56`, so at `b08af640` and in main's writer) is the caller's word for which of the species' cell types
  the loop is of, absent for its default cell: carried as written, and refused where it is no
  word. The writer measures the closure on the saved files, as the largest change
  from the first observed row to the last over the record's own largest magnitude, for every
  observed record of kind level, amount or rate; it writes the block only when the observed
  rows span the period and the closure is within the tolerance, and only for a run that
  names its engine source (otherwise `unstated` has an item `loop` with the reason).
  `closes.zero` names the records identically zero over the loop, which are not divided by;
  `not_measured` names the records the closure leaves out, by reason (the running totals,
  which grow by design; diagnostics; records of no stated kind). The adapter checks the
  block (its cell the run's, `within` no more than `tolerance`, `period` the span of the
  replay's records as the run saved them, the records it names the view's, each step of
  `follows` a time inside the records with cells of the run) and carries it as `view.loop`,
  `zero` and `not_measured` with it, as written; otherwise the view is refused. A record not
  measured is never read as one that meets itself. The writer at `fd008813` writes no
  `loop`, and its check there refuses a top-level key it does not know.
- **Not read yet.** A subset of the entities of a set other than the species is refused. A
  builder's `points` or `spheres`, three dimensions, and the outside nodes' geometry are not
  read. The caller's labels `experiment`, `arm` and `seed` are not read: the catalogue names
  the run.

## Packaged for the viewer: `cells.visualizer.replay@1`

This part is the viewer's own and is fixed, so that the adapter and the replay view can
be built side by side (14 November 2026). It wraps a run view for a browser: metadata as
JSON and the arrays as one binary payload. Generated files are never committed.

```
out/runs/index.json          the catalogue the page embeds
out/runs/<run-id>.json       one run: its view and its arrays
```

`<run-id>` is `<experiment>--<arm>--seed<n>` in lower-case letters, digits, dots and
hyphens, for example `e07-v1--c-disconly-fast-k1-d37-s1.0--seed1`.

### One run

```json
{
  "format": "cells.visualizer.replay@1",
  "view": { "format": "cells.run_view@1", "derived": true, "...": "as above, with the rules below" },
  "payload": { "encoding": "base64", "byte_length": 524288, "data": "…" }
}
```

Rules that tighten the run view above:

- **`view.derived` and `view.derivation`.** An adapter sets `derived: true` and lists, one
  line each, how every piece the run did not save was derived.
- **`view.run`** adds to the fields above: `id` (the run id), `label` and `group` as the
  run's plan gives them, `stop`, `end_s`, `class` (the class the experiment's own summary
  records, verbatim), `judged_s`, `parameters` and `readouts`.
  - `parameters`: `[{"id", "value"}]`, the run's plan values, in the plan's names.
  - `readouts`: `[{"id", "value", "supplementary", "status"}]`, the run's outcome values in
    the outcome's names; a nested value is named with dots (`delta_J_over_records.mean`).
    `supplementary` is true only where the run's own files say so, and `status` then
    carries their words. The adapter judges nothing: it does not decide which readouts were
    judged, and a replay never computes a verdict of its own.
  - Labels for parameters, readouts and classes come from the catalogue (below), keyed by
    these ids. The adapter copies only the ids the catalogue names.
- **`view.records[]`** describe arrays in the payload, not in the run's own files:
  `{"id", "label", "unit", "set", "layer", "axes", "dtype", "offset", "shape", "range"}`.
  - `dtype` is `float32`, `uint8`, `uint16` or `int32`, little-endian, in C order.
  - `offset` is in bytes from the start of the decoded payload and is a multiple of 4.
  - `range` is `[min, max]` over the array's finite values.
  - An optional `scale` means value = stored × scale. Such an array is `"quantised": true`
    and is for drawing only: the viewer never prints it as a recorded number.
  - The record with id `t` holds the record times in seconds (`axes: ["time"]`); `view.time`
    is `{"unit": "s", "record": "t"}`. Times need not be evenly spaced.
  - An optional `marks` lists values worth a line on the record's scale:
    `[{"value", "label"}]`, for example the voltage above which the experiment counts a cell
    as D. A mark is the experiment's own constant, read from its saved files, never chosen
    by the adapter or the viewer.
  - Records with the ids `regular` and `valid` (`uint8`, one per record time) carry the
    run's own flags when it saves them. A record that is not `valid` is never shown as data.
    For E07-v1, `regular` marks the records on the 10 s grid; the others are taken at an
    event's time and hold the state just before that event. `valid` says the field solve
    behind the record converged.
  - The records `t`, `regular` and `valid` have no `set` and no `layer`. A record may carry
    a `note`.
  - **What a quantity layer needs to know of a record** (`schema/QUANTITY_LAYERS.md`), each
    optional, and each stated only where the run's own files or the driver that wrote
    them state it; a reader says what is missing and fills nothing in:
    - `kind`: `level`, `amount`, `cumulative` or `rate`;
    - `owner`: the model, operator or law that computed it, as the run's definition names
      it;
    - `sign`, for a signed record: `{"says": "what positive means, in words"}`; for a
      level on links also `"high": "first"` or `"second"`, the end that is at the higher
      value when the record is positive; for a level on membranes `"high": "inside"` or
      `"outside"`, the side that is the higher; for a transfer `"from"` and `"to"`, the
      two ends in the order a positive amount goes. A record with no `sign` is drawn as a
      level or a size, never with a direction. Where the run's own files do not declare
      the sign and an adapter takes it from a table of its own, the sign carries `"by"`,
      which says in plain words where it comes from, and the legend repeats it. The
      adapter's table for the tissue family (`TISSUE_FIELDS` in `tools/adapt_run.py`) is
      the engine's own convention as the owner of its core confirmed it on 15 November
      2026: a positive transfer leaves the cell for its outside, or the sender for the
      receiver; pump cycles are positive inwards. It is not carried over to the older
      single-cell model, whose flux is positive from bath into cell.
      **The membrane voltage's sign is not in that table and was not confirmed.** The
      adapter reads it from each run's own files, and its `by` says so: where every cell
      has one membrane, the run's first record is at time 0, and each cell's saved
      voltage there equals the charge its definition gives the cell over the capacitance
      it gives the cell's membrane, a positive voltage means the inside is positive
      against the outside (`"high": "inside"`). Where that does not hold for every cell,
      no sign is written, and a layer that needs a direction is not offered;
    - `field` and `species`: a quantity the run saved once for each species (a
      concentration of each ion) is one record for each, all with the same `field` and
      each with its `species`, one of the ids of the set `species`. Its id is
      `<field>.<species>`;
    - `same_as`: the id of another record that is this same array, declared over another
      set. An adapter writes it where a run saved one voltage for each cell and its
      definition gives each cell exactly one membrane, in the cells' order: the record
      `membrane_voltage_V` over the membranes is then the array of `vm` over the cells,
      and no array is added. Where a cell has several membranes, or the saved voltage is
      a mean over them, no such record is written;
    - `monotone`: `"non-decreasing"` for a total since the start that only ever grows (the
      engine's ledgers of dissipated energy, which it checks element by element), in the
      engine's own word. A rate worked out from such a record is never negative. Not
      allowed on a record of another kind;
    - `resets`: `{"by": [laws], "says": "..."}` in place of `monotone`, for a total that
      restarts at nought on a slot when one of those operators retires the slot. A rate is
      not taken across such an event; a record with either word feeds the energy layer;
    - `note`: what the run's view itself notes of the record, in its own words (that the
      membrane's own total holds its passive routes only, for one);
    - `array` and `base` (and `rows`): for a run packaged from the engine's own view, the
      array the record comes from, the time base it is saved on, and, where that is not
      the replay's own base, which of its rows were taken;
    - what it lives on is its `set` (a set may say `holds`, one of the contract's words,
      where its id is not one), and how it is represented is its layer's `representation`.
  - **A record in a file of its own** carries `part`, the id of one of `view.parts`; its
    `offset` is then within that part's arrays. The record of the times is never in a part.
  - Event times keep the run's own precision, while `t` is stored in 32 bits: match the two
    with a tolerance.
- **`view.sets[]`.** Cells of a sheet use `polygons` (`vertices` as `[x, y]` in
  `view.space.unit`, `faces` as lists of vertex indices, one per cell, in the order of
  `ids`). Junctions use `links` with `ends` as pairs of indices into the named set.
  Where the run's definition lists them, three more sets say what a layer on one
  membrane needs to find its way:
  - `species`: the ids of the definition's species, in its order (`{"id": "species",
    "ids": ["Na", "K"]}`). A generic row keeps its own id;
  - `outside`: the outside nodes, `"holds": "outside node"`;
  - `membrane`: the membranes, each on its cell and facing its outside:
    `"geometry": {"kind": "on", "set": "cell", "index": [...]}` gives, for each
    membrane, the index of its cell, and `"outside": {"set": "outside", "index": [...]}`
    the index of the outside node it faces.

  What a set may say more of its entities, one value for each in the order of `ids`:
  - `species.secreted`: the ids of the species the run secretes (those its operators
    make, clear or exchange). A layer may ask for "the run's secreted species";
  - `outside.reservoir`: for each outside node, whether it is a bath held at a fixed
    composition (the engine's word; a reservoir in the definition);
  - `cell.lifetimes`: for each cell null, or its birth and its retirement;
  - **tiles for the outside nodes.** In a small world the outside nodes may have
    `polygons` of their own. They then share the cells' list of `vertices` (the same
    list, in both sets), so that the viewer finds the edge two tiles share: two tiles
    touch where a junction, a membrane or a face joins their places. The run saves no
    positions: the layout is the adapter's, the view's `derivation` says so, and the
    page draws such a tile flat, never as a cell;
  - `membrane.pumps`: for each membrane null, or its pump as the engine's view gives it:
    `{"id", "law_id", "per_cycle": [{"role": "sodium", "species": "Na", "count": -3},
    ...], "per_cycle_sign": "inward-positive"}`, what one cycle moves of each species; a
    positive count is carried into the cell;
  - `channel.species`: for each channel population, the ids of the ions it lets through;
  - `route` (`"holds": "route"`; in the engine's own view `exchange_route`, which `holds`
    "exchange route"): the routes of an operator that carries a species across a
    membrane, each on its membrane (`"geometry": {"kind": "on", "set": "membrane",
    "index": [...]}`), with `species`, the id of the species it carries, where the run's
    files say it.
- **`view.example`** (optional): `{"says": "Example: invented numbers", "made_by":
  "tools/make_run_fixture.py"}`. The run's numbers are invented (`schema/QUANTITY_LAYERS.md`,
  rule 6): no record then names a model as its owner, `run.engine_models` is empty, and
  the page keeps the words of `says` on the picture and in the legend.
- **`view.loop`** (optional): `{"species": id, "cell_type": id, "cell": id, "period": seconds, "closes":
  {"within": number, "tolerance": number, "says": text, "zero": [record ids]},
  "not_measured": [{"why": text, "records": [record ids]}], "follows": [{"time": seconds,
  "from": id, "to": id}]}`, as the engine's run-view writer gives it (FR-11, ruled by the
  lead on 16 November 2026; written from `d7a11d5b` on, and by main's writer since `050aa741`). The run is one period of a looping run of one cell of that species
  (`schema/QUANTITY_LAYERS.md`, rule 7). `species` is the species' id in `data/species/`;
  `cell_type` (optional; written from `0fac9d56`, so by main's writer) the caller's word for which of the species' cell types the loop is of, absent for
  its default cell; `cell` the cell's id in the run's set of cells; `period` the loop's length in the run's
  time, equal to the span of its records, which run from the loop's start to its closing
  record. `closes.within` is the largest relative change from the first record to the last
  of any record of kind level, amount or rate, as the writer measured it on the saved files;
  `closes.tolerance` the tolerance its caller declared (`within` is never above it);
  `closes.says` the sentence the page may show; `closes.zero` (optional) the records
  identically zero over the loop. `not_measured` (optional) names the records the closure
  leaves out, each group with the run's reason: the running totals, which grow by design,
  and which a reader differences inside the loop only; diagnostics, the residuals of the
  engine's own checks, where the run records any (declared by @3 from `b08af640`). The page
  says, for each group, how many were not
  measured, with that reason, beside the closure, and never reads one as meeting itself.
  `follows` (optional, for a cell cycle) names the cell the loop follows from a time on,
  after a division: the page says so, and reads the loop's first cell (the writer refuses
  it until the cycle is built). The run names its engine models and its revision:
  `run.revision`, which the adapter fills from `run.source.revision` (`run.source` is
  carried, with whether its tree was clean, and the page says so of a loop); the writer
  writes a loop only for a run that names its engine source. A run with `example` is never a
  loop. The first real one is the interim planarian loop, a development run with no verdict,
  written at `d7a11d5b` and again at `b08af640` with the same arrays and loop block
  (`tests/engine-views/loop-d7a11d5b/` and `loop-b08af640/`); the `b08af640` run is the page's, as the development run `planarian-loop` (`data/replays`), not judged.
- **`view.constants[]`** (optional) are named constants of the run's definition: values
  that a derivation of a quantity layer may read in place of a saved record
  (`schema/QUANTITY_LAYERS.md`, rule 1). `[{"id", "label", "unit", "set", "axes",
  "values", "from", "says"}]`: `axes` names the sets its values run along (none for one
  number, `["membrane"]` for one for each membrane, `["species", "outside"]` for one for
  each species at each outside node), `values` is nested accordingly, `from` is the file
  they were read in, and `says` gives, in plain words, why nothing in this run changes
  them. Ids are the engine's own names where it has one: `temperature` (K), `valence`,
  `volume` (pL), `membrane_capacitance` (F), `membrane_area` (m2); and
  `extracellular_concentration_mM`, each held bath's declared amounts over its declared
  volume. **A constant is stated only where the adapter knows everything the definition
  can change**, by a list of what it knows (`what_may_change` in `tools/adapt_run.py`):
  the model and its laws of replacement, every key of its cells, membranes, outsides,
  templates and replacements, and every control with what it schedules. For the turnover
  runs: a newcomer's template states the volume of the place it takes (checked equal)
  and names no capacitance and no area; a control schedules an availability only; every
  cell's outside is a held bath. Anything the adapter does not know means that no
  constant is stated.
- **`view.unstated[]`** (optional) lists what the view does not state as a constant, each
  with the reason: `[{"id", "why"}]`. A layer that needs one is then listed for the run
  with that reason.
- **`view.parts[]`** (optional) list the files that hold records of their own, so that a
  run's own file stays near 1 MB whatever its layers can show:
  `[{"id", "label", "file", "byte_length"}]`. `id` is lower-case letters, digits and
  hyphens; `file` is `runs/<run-id>.<part id>.json`, beside the run's; `byte_length` is
  the length of its decoded arrays. The file is
  `{"format": "cells.visualizer.replay_part@1", "run": "<run-id>", "part": "<part id>",
  "payload": {"encoding": "base64", "byte_length": …, "data": "…"}}`, under the same size
  limit as a run's file. The viewer fetches it when a layer that reads one of its records
  is switched on, and not before.
- **`view.surroundings`** (optional) says whether every cell's surroundings share one
  potential: `{"shared": true, "potential_V": 0.0, "says": "how the run's files state
  it"}`. Only then is the difference of two cells' membrane voltages the voltage across
  the junction between them. An adapter states it only where the run's definition does
  (each membrane's outside a held bath, all at one potential, and nothing scheduled that
  changes a bath); otherwise it is left out, and a layer that needs it is not offered.
- **`view.regions[]`** (optional) name subsets the run's plan defines:
  `[{"id", "label", "set", "indices"}]`, for example the disc of cells that start in the
  written state. The viewer may outline a region; its label comes from the catalogue.
- **`view.layers[].representation`** is `simulated`, `modelled`, `prescribed` or null. An
  adapter leaves it null when the run's files do not state it, as today's do not.
- **`view.events[]`** name entities by index: `{"time", "kind", "layer", "at": {"set": "cell",
  "index": 108}, "from": {"set": "cell", "index": 107}, "label"}`. `from` is optional.
- **No machine paths and no host names** anywhere in a generated file.

### The catalogue

```json
{
  "format": "cells.visualizer.replay_index@1",
  "experiments": [{
    "id": "e07-v1", "label": "…", "plain": "…",
    "sources": [{"path": "docs/E07_V1_DESIGN.md", "where": "…"}],
    "engine_entities": ["…ids of scene parts this experiment runs…"],
    "groups": {"control": {"label": "…", "plain": "…"}},
    "classes": [{"id": "neutral", "label": "Neutral", "description": "…"}],
    "regions": {"disc": {"label": "…", "plain": "…"}},
    "records": {"vm": {"label": "…", "plain": "…"}},
    "events": {"replacement": {"label": "…", "plain": "…"}},
    "parameters": {"s": {"label": "…", "unit": "…"}},
    "readouts": {"delta_J": {"label": "…", "plain": "…"}}
  }],
  "runs": [{
    "id": "e07-v1--…--seed1", "experiment": "e07-v1", "arm": "…", "seed": 1,
    "label": "registered seed", "group": "control", "class": "erosion", "stop": "planned end",
    "records": 318, "end_s": 2340.0, "file": "runs/e07-v1--…--seed1.json", "bytes": 700000,
    "parts": [{"id": "junction-gate", "file": "runs/e07-v1--…--seed1.junction-gate.json", "bytes": 240000}]
  }]
}
```

The `experiments` entries are curated in `data/replays/overlay.json` (labels, plain lines
and sources); the adapter copies the entry of each experiment it adapts and adds `runs`.
A record's entry may give `shown_between`, `[low, high]` in the record's own unit: the
limits its colour scale uses in every run of the experiment, so one value has one colour.
A run that reaches beyond them widens the scale.

A run's `parts` (optional) list its files of records of their own, so that whoever
publishes the runs knows every file without opening one. A published page may name, for a
part, a file that holds several of the run's parts (below).

**Parts published together: `cells.visualizer.replay_parts@1`.** The runs folder keeps a
run's own file and one file a part, as the adapter writes them; the export only reads it
(`--runs`). A published page may hold 511 files, so an experiment may say, in its entry of
`data/replays/overlay.json`, `"parts_together": true` (true or false; absent is false). The
export (`tools/export_page.mjs`, `packageParts` in `tools/lib/build_page.mjs`) then
publishes the parts of each of its runs as one file for the run, written into a folder of
the export's own beside the page (`<page's name>.runs/`) and listed beside the page at:

```
runs/<run-id>.parts.json     the run's parts, in the run's own order of parts
runs/<run-id>.parts-2.json   and on, only where one file would reach the size limit
```

```json
{"format": "cells.visualizer.replay_parts@1", "run": "<run-id>", "parts": [
  {"format": "cells.visualizer.replay_part@1", "run": "<run-id>", "part": "<part id>", "payload": {"…": "…"}}
]}
```

- Each item of `parts` is the run's part file as the adapter wrote it, word for word; no
  part is in two files, and no part's id is `parts` or `parts-<n>`.
- Each file stays under the size limit of a run's file (1 MB: `RUN_FILE_LIMIT`, the
  adapter's `LIMIT_BYTES`). Where one file would reach it, the parts go into as few files
  as hold them, kept in the run's order and cut where the largest file is the smallest
  (`cutInOrder`): an E07-v1 run's gate and three concentrations (1.30 MB) are two files of
  0.59 and 0.71 MB. A run's own file is unchanged.
- The published catalogue's line for the run names, for each such part, the file that
  holds it (`parts[].file`) and that file's size (`bytes`). The adapter leaves
  `parts_together` out of the catalogue it writes: the export reads it from the overlay.
- The page asks for one part at a time, as before (`loadPart` in `src/replay/source.js`):
  the file the catalogue names for the part is fetched once for the run, however many of
  its parts are asked for, and only the part asked for is taken in; the others' arrays wait
  in the page until they are asked for. A file that could not be fetched, or whose part
  could not be taken in, is fetched again when asked for again. An error names the file
  and the part. `validatePart` and `validateParts` (`src/replay/run.js`) check the shapes.
- A page with its runs inside it (`--inline-runs`, `--standalone`) keeps one script a part.

**Several experiments.** One catalogue holds every experiment adapted into the folder,
each with its runs; adapting one experiment leaves the others' entries and files in place.

**Development runs.** An entry may say `"development": true`: its runs are development
runs of the engine, not an experiment. The page lists them under a heading of their own
("Development runs"), apart from the experiments, with `outcome.judged` false and the
words its entry gives ("Development run, no verdict").

**Examples.** An entry may say `"example": true`: its runs have invented numbers, written
by the run-fixture tool for a layer that no saved run feeds yet. The page lists them
under "Examples", after the experiments and the development runs, with no outcome and no
class. The word comes from the run folder itself (`example.json`, which the tool writes)
and is carried into the run's view and into its line of the catalogue (`"example": true`).
The adapter refuses a run that is an example under an entry that does not say so, and a
run that is none under an entry that does: an example never stands among experiments.

**A sweep's chart.** An experiment whose summary lists arms with a parameter and readouts
carries `sweeps` in its catalogue entry, which the Experiments view draws as a small chart,
in a card of its own at the right of a wide window and first in the experiment's card on a
phone (`src/replay/sweep.js`, `src/ui/viewer.js`): the parameter along it (on a log scale
where every value is above nought and the largest is ten times the smallest or more), each
readout a line of points, each arm a point, the arm shown marked; a press on an arm shows
its run, and the same numbers stand in a table under the chart. Where the summary states
the experiment's own reference for a readout it is drawn as rings, in the summary's words.
The viewer computes nothing from the numbers and says nothing of how they compare.

The adapter writes `sweeps` from the experiment's summary and from nothing else. The
overlay's entry names the summary by a file's name in the evidence folder (`"summary":
"summary.json"`, never a path); the summary is `cells.experiment_summary@1`, and the least
it must state is:

```json
{
  "format": "cells.experiment_summary@1",
  "experiment": "an-experiment",
  "sweeps": [
    {
      "id": "figure-3",
      "label": "Junction conductance sweep",
      "plain": "optional: one sentence on what the sweep asks",
      "parameter": { "id": "g", "label": "Junction conductance", "unit": "G_eq" },
      "readouts": [
        { "id": "c_A", "label": "Concentration in cell A", "unit": "mM" },
        { "id": "c_B", "label": "Concentration in cell B", "unit": "mM" }
      ],
      "reference": { "label": "the experiment's own reference, in its words", "source": "optional: where it is stated" },
      "arms": [
        { "arm": "figure3-g0.5", "parameter": 0.5, "readouts": { "c_A": 6.25, "c_B": 8.75 }, "reference": { "c_A": 6.25, "c_B": 8.75 } }
      ]
    }
  ]
}
```

Each arm is named as its run's arm is (the run folder's name), so that the adapter can
join it to the run it packages in the same call (`run`, or `null` where none is packaged:
the chart draws the arm and says that no run of it is packaged). Every value is a finite
number in the unit named; a `reference` value is given only where the sweep names its
reference; a sweep has two arms or more. The adapter refuses a summary that does not
state these, with the reason. The catalogue's entry then holds:

```json
"sweeps": [{ "id": "figure-3", "label": "...", "parameter": {...}, "readouts": [...], "reference": {...},
             "arms": [{ "arm": "figure3-g0.5", "run": "an-experiment--figure3-g0.5", "parameter": 0.5, "readouts": {...}, "reference": {...} }] }]
```

A made-up summary of this shape is tracked for the tests (`tests/engine-views/sweep-made-up/`).

**A quantity the experiment states.** An experiment's driver may work out a quantity over
the cells itself (each cell's concentration from the run's own arrays; a criterion's
quantity) and write it beside a package. The run folder's `index.json` names the file in
the package's entry (`packages[].sidecar`: a JSON file's plain name, or a list of them);
in a run folder with no `index.json`, the experiment's overlay entry names it beside every
package (`sidecar`). The adapter reads it only there, for a run with the engine's own view,
and refuses it, with the reason, where it does not fit:

```json
{
  "format": "cells.experiment_quantity@1",
  "quantity": { "id": "concentration", "label": "the driver's own label, with its unit's line", "unit": "mM" },
  "times_s": [0.0, 2.0],
  "cells": ["A", "B"],
  "values": [[5.0, 10.0], [5.43, 9.57]]
}
```

- Every time the replay steps through must be one of `times_s` (within the time bases'
  tolerance), and `cells` must name the view's cells, each once: the adapter matches by
  name and time, and never resamples, matches by position or fills in. Every value is a
  finite number.
- The record is `stated.<quantity.id>`, over the cells, with the file's label and unit as
  given and `stated: { file, format, quantity }`. The page offers it as a Colour layer,
  writes its unit in its own sign (uM as µM) and never converts it, and says under the scale
  that it is the experiment's own quantity, stated by its driver beside the run and copied as
  stated, not a field of the engine. An experiment's overlay entry may open its runs on it
  (`opens.record`: one record, or several in the order wanted; the first the run has).
- `cells.experiment_criterion@1` is the same file with a criterion: `criterion: {
  threshold, above, below, words, source }`, or, for two thresholds, `criterion: {
  threshold, above, lower: { threshold, below }, between, words, source }` (the lower
  threshold under the upper). The scale ticks the threshold in the criterion's own words
  (one tick with "above" and "below"; or two ticks and the three words as given), reaching
  the thresholds though the values do not, and gives its `words` and `source` as given. Its
  optional `states` (one word per cell at each of its times) become the record
  `stated.<id>.state` (`words`, and a whole number per cell naming one): a chosen cell's
  panel gives the state as the driver states it, and nothing is coloured by the states.

Where an experiment's runs state one quantity in different units (two forms of one model),
its overlay entry says so in a line of its own (`units`), which the page shows by the runs
and by the sweep's chart. Made-up files of these shapes are written by
`tests/stated_quantity.test.mjs` and `tools/check_junctions.mjs`.

**A part of an example.** An entry may name the listed example it belongs to
(`"part_of": "<entry id>"`): it is not listed itself, its card's door stands in the
example's card, and a published page carries its runs with the example's
(`publishedReplays`). The gap-junction example's tumour tissue has two: the line and the
sheet (`src/lenses/tissue_line.js`, shown in the Experiments tab's place, `part=<entry id>`
in the address). The example's own entry names the part the tab opens on (`opens.part`,
one field); an address that names a run, a record, layers or a part of the runs' view
still opens the runs. A part's entry holds the record's words for the picture under
`tissue`, each set with its source:

- `says` (the lines the page may say), `ends` (each arm's end states, the record's table,
  by arm), `ends_label`, `ends_says` (whose words they are, for the card), `refused` (the
  words for a refused pick), `no_routes` (what a run with no routes is said to have) and
  `sources`;
- `caption` (words stood in full over the part's tissues on the first screen; another
  part shows a small door to this one, and its card the same words over the door),
  `place_says` (what an arm's place such as "x2/4" is against, said once over the
  tissues), `bracket` (`between`: two arms, a dashed line drawn between them; `says`: what
  the line is, said with `place_says`);
- `intro` (`title`, `first`: what to do first; `items`: the record's own sentences, each with
  its `source`; `shown`, `shown_narrow`: how many stand before the fold), `switch` (`x`, `y`:
  two stated quantities whose plane the chosen cell's records are drawn in; `cell`: the
  default `{ arm, cell }`, with `cell_says`), `walk` (`part`: a part whose couplings join
  this one's in a chart, its points pressed to bring a run into the rows; that part says
  `walk_of` and is no door of its own, and its `caution` goes with the times; `points`: one
  row of the record's tables for each coupling, `{ part, arm, end, tumor_E, every_E,
  all_E_first_s }`, with `points_says` and `points_sources`);
- `beside.every_arm_front` (the arms of the part beside that stay in view when every arm of
  this one is, with `every_arm_says`);
- `front` (the arms in view as the page opens, the picture's choice, with `front_says`;
  the card brings in the rest, fetched as they come into view) and `beside` (another part
  drawn under this one, smaller, folded away while every arm is in view: its `part`,
  `front`, `says` and `front_says`).

The tumour's cells, the species' names and each arm's place are the packages' data, not
the overlay's: the summary's sweep `tumor_cells` and `species`, each arm's `place`
(`relative_to_x2`, `side`, `source`), carried into the catalogue's sweeps, and the same
in `criterion.json`, carried on the stated record (`tumor_cells`, `species_names`,
`place`). The overlay's `sidecar` may name several files beside each package (the
criterion and the stated concentrations). A part whose picture opens on a stated quantity
has its voltages in a file of their own, and of a passive route's totals only the species
its routes carry are packaged. Its runs come from the selection's run folder: its
`index.json`, or where it has none, every package in it that holds a `view.json`, by name.
The runs in view share one clock, the union of their saved times; each shows its own
record at or before it; past the end of runs that ended before the clock, the words over them say so.

- **Refused picks.** With `"refused_picks": true` and a summary of one sweep, each folder
  beside the packages that holds `REFUSED.json` and no view is named in the catalogue entry
  (`refused_picks: [{ arm, sweep, parameter, file }]`): its arm, which must be its folder's
  name, its status, which must be `refused`, and its value of the sweep's parameter (the
  key the parameter's id names), and nothing else of the file. The page puts each in its
  place in the parameter's order, named, with nothing drawn in it.
- **The picture's choices**, said on the picture: the colour of a value on a scale broken
  at the criterion's own thresholds (one hue below, a grey between, another above), and
  time down each line's map on a logarithmic scale (a time t at log(1 + t / a two-hundredth
  of the run)) or an even one; every saved record is a band from its time to the next. The
  clock follows the driver's stated changes (`src/replay/tissue_play.js`): each time of a
  change is held 2.2 s of watching and the time between passes in a second or less. No
  state is read from a colour; a cell's state is the driver's.

### A run written by the engine's shared output path

The adapter `standard-history` reads a run folder that the engine's own writers made
(`cells.records.io.write_run`, or `cells.records.window_io.write_windowed_run`;
`cells.io` and `cells.window_io` before the engine's second source move): `resolved_config.json`
beside `trajectory.npz`, or beside `windows.jsonl` with one chunk of arrays for each
window. It takes the readouts the run observed, `observed_<field>` at `observation_times`
(the windows put end to end), and keeps the engine's own names for them: the record of
`observed_membrane_voltage_V` is `membrane_voltage_V`.

- **Where a field lies** (its axes after time), what the page calls it and its view
  layer are the adapter's table by field name (`HISTORY_FIELDS`), until the engine's run
  view declares them. Kind, unit and the sign of an amount carried are the adapter's
  table for the tissue family (`TISSUE_FIELDS`), used only for a model of that family
  (`resolved_pump_tissue@3`, `resolved_pump_composite@1`, `resolved_pump_replacement@1`);
  a model of another family gets no kind and no sign, and a unit only where a field's
  name ends in one.
- **Which entity a column is:** the arrays name none. Columns follow the definition's
  order, and an array made for more places than the run uses is cut at the definition's
  count. Sets: `cell`, `junction`, `species`, `outside`, `membrane`, and where the
  definition lists them `face` (links between outside nodes, `"holds": "face"`) and
  `channel` (on membranes, `"holds": "channel population"`).
- **A field with a row for each species** becomes one record for each (`amount.Na`).
- **Signs read from the arrays:** where each membrane's saved voltage equals, at every
  record, the saved potential of its cell less that of the outside it faces, and is not
  nought throughout, `membrane_voltage_V` gets `"high": "inside"`; where each junction's
  saved voltage equals its sender's potential less its receiver's, `junction_voltage_V`
  gets `"high": "first"`. Each `by` says it is the viewer's reading of the run's own
  arrays.
- **A voltage for a cell** (`vm`) is declared only where every cell has exactly one
  membrane, as the same array (`same_as`). Nothing is averaged.
- **Files:** `t`, `membrane_voltage_V` and `cell_potential_V` in the run's own file;
  every other field in a part of its own, cut by species where one file would pass the
  size limit.
- **Cells with no hexagonal sheet** (two cells, one cell, a chain) are drawn side by side
  in the definition's order, and the view says so.
- **Constants** follow the same rule as for every run: a composition with an operator
  the adapter does not know states none, and names the operator.
- **Owners:** where the run folder holds the engine's `manifest.json`, each record's
  owner is the one its field map names for that readout (`field_owners.observations`):
  the inner model, or an operator's law.
- **An operator's ledgers** that the adapter's table does not list
  (`turnover_produced_fmol`, `turnover_cleared_fmol`, `turnover_outside_cleared_fmol`) are
  read as totals since the start where their arrays begin at nought and never fall, and
  the view says that this is read from the arrays.
- **Exchange routes** (`scheduled_species_exchange@1`): the ledger `exchange_moved_fmol`
  has one total for each route. The run's files do not declare which way it is positive.
  The engine's convention, which its lead confirmed on 15 November 2026 from the
  operator's own code, is that a positive total has left the route's cell, for an export
  and an import route alike. The adapter gives the record that sign only where the run's
  own arrays agree: where, at every record, the amount of the route's species in that
  cell is its amount at the start, plus what was made there, less what was cleared there,
  what crossed the cell's membranes and junctions, and the routes' totals; and where the
  amounts do not add up with the totals read the other way round, or along each route's
  declared direction. Its `by` names the convention and who confirmed it, and says that
  the run's amounts agree. Where the check does not hold, the record has no sign and no
  kind, and no layer draws it with a direction.
- **Outside nodes as tiles:** where the cells and the outside nodes of a run fit a
  hexagonal lattice with a tile for each, touching wherever a junction, a membrane or a
  face joins two of them (one cell, the space it secretes into and a bath), the outside
  nodes get tiles. Where they do not (a sheet whose every cell has a bath of its own),
  they get none, and the view says so.
- **An example** is a run folder that holds `example.json` (see "Examples" above).

### A run with the engine's own view beside its files

Where a run folder holds `view.json` (`cells.run_view@1`, as the engine's writer gives
it), the adapter `standard-history` packages the run **from that view and from nothing
else**. None of its own tables is used (no kind, unit, sign or owner of its own), and
nothing is read out of the arrays' values: no sign of a voltage, no direction of an
operator's total, no "total since the start". What the view does not state stays
unstated, with the view's own reason (`unstated`), and a layer that needs it says so in
those words.

- **One time base for the replay.** The replay steps through the observed rows
  (`observation`) where the view has them, and through the state's rows otherwise;
  `view.time.base` names it and lists the other bases with their row counts. A field
  found on both bases is packaged once, from the replay's own base. A field found on the
  other base only is packaged at the rows of that base that fall exactly on the replay's
  times, and its record says so (`base`, `rows`); where a time has no such row it is not
  packaged, and the derivation says so.
- **Records** are those the page has a name for, under the engine's field name
  (`amount.Na` for a field with a row for each species). Each carries, as the view writes
  them, its unit, kind, sign, owner, layer, `monotone` or `resets`, `note` and `writers`,
  and the `array` it comes from.
- **Sets:** a slot with no name (null) is left out with its column in every array, and
  every index into that set is renumbered. `reservoir`, `valence`, `lifetimes`, `laws` and
  `pumps` are carried as written; a set a packaged record lies on (`exchange_route`) is
  carried with its geometry and owner. The cells' and the outside nodes' places are still
  the adapter's own layout where the view gives no geometry, and the derivation says so.
- **Layers** are the view's, each with its owner and its representation: the page can
  say "simulated", "modelled in aggregate" or "prescribed" of every record.
- **Constants and what is unstated** are the view's own; a flag (true or false) is no
  number a layer reads, and is left out.
- **Events** are carried with the entity's number in place of its id, each with its layer,
  so that a reader knows which operator's events restart a total.
- **The secreted species** is the species an operator of the run declares (the view names
  the operator that declares each species); the view does not itself call it secreted,
  and the derivation says that this is the viewer's reading.
- **Signs and differences.** A record's `sign` is carried as written. A voltage's
  `difference` (what it is the difference of: `plus`, `minus`, `says`), which the
  writer's present shape gives in place of a sign, is carried as written, and the record
  gets the page's `sign` from it: `says`, `high` from the role `plus`, and the view's own
  `source` or `confirmed`. Where a role has no word of the page's, the record gets no
  sign.
- **Sets carry their `roles`.** An operator's set carries `species` (the view's `carries`),
  `direction`, `kinds` and `at` as written, and is packaged even where no record lies on
  it.
- **The run** carries `source` and `end` where the view states them. `run.revision` is
  `run.source.revision`; where the view states no source it is the caller's label, and the
  derivation says that it is that and not the engine's own record of its source.
- **`view.time.event_rows`** is the run's own sentence on what a row saved at an event's
  time holds, as written.
- **Merged views** (`view_<field>`: a field an operator changes, as it stood at each
  observed row) of `volume`, `extracellular_volume`, `membrane_area` and
  `membrane_capacitance` are records under the field's name; the others are named in the
  derivation and not packaged.
- **A recorded subset** (`recording.subset`) is read: the rows the run kept, the fields it
  lists, and of a field with a row for each species the species it kept. A field the
  page would otherwise look for and the run could have recorded gets no record and is
  named as not recorded, in the run's own words; nothing stands in for it, and a total
  the run calls not measured is never read as nought.
- **Events** are kept where they lie within the records; those the run states outside its
  recorded period (a loop records one period of a longer run) are counted in the
  derivation with their times, and not shown.
- **Refused:** a view whose files, arrays, rows or shapes are not as it says; a recorded
  subset that contradicts itself, or that keeps only some entities of a set other than
  the species; an example (`example.json`) with a view beside it.

**What an experiment found** is two separate facts, both curated from the record, each
with the record's own line and a source. The viewer shows them and derives neither.

```json
"outcome": {
  "judged": true,
  "status": "Judged, 13 and 14 November 2026",
  "answer": "no",
  "label": "The disc did not renew",
  "text": "…the record's line…",
  "sources": [{"path": "PROGRESS.md", "where": "…"}]
}
```

- `judged` and `status`: whether the experiment ran under a registered protocol and was
  judged, in a few words. Development or exploratory runs are `judged: false`.
- `answer`: `yes` when the record says the thing the experiment set out to show held, or
  that every item of its protocol passed; `no` when the record says it did not; `mixed`
  when the record reports both; null when nothing is judged. `label` says it in a few
  words, and `text` gives the record's line. Where the one-word answer is a reading of a
  longer result, `text` carries the whole result.
- A judged experiment whose answer is `no` is still a judged experiment: the two facts
  are shown side by side, never merged into one "failed".

**How a run ended.** A run of the catalogue carries `stop` in the run's own words, and
`refusal` when the run's files record one. The experiment's entry may give `stops`, plain
labels keyed by those words: `{"planned end": {"label": "Ran to its planned end"}}`. A run's
`class` is optional: an experiment that records none has none, and the viewer shows none.

### How the page gets them

- The page builder puts the catalogue into the scene as `scene.replays`. The Experiments
  view is offered only when it holds at least one run.
- A run is loaded when it is first shown. The viewer looks for
  `<script type="application/json" data-replay="<run-id>">` in the page; if there is none
  it fetches the run's `file`, a URL relative to the page. The local server and the
  published artifact serve `runs/<run-id>.json` beside the page; a standalone file carries
  the runs inline.
- A part of a run is loaded when a layer first needs it: from
  `<script type="application/json" data-replay-part="<run-id>/<part id>">` in the page, or
  else from the part's `file`, beside the run's.

## Open points for the engine-side note

- The file's name and whether it is one file per run or one per experiment with per-run parts.
- Whether geometry goes in the view file or in an array file it points at (large tissues).
- How an operator declares its layer and representation, so the view file is assembled from
  declarations and not written by each driver.
- Record names: the viewer can use the engine's readout names directly if they are stable.
