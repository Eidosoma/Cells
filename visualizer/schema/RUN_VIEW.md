# Run view: what a run saves so that it can be visualised

Status: **draft from the visualizer side, 14 November 2026**, for the lead's design note
under D154. Names here are proposals; the engine-side note fixes the final file and field
names, and the viewer adapts. **From 15 November 2026 the engine's own run-view writer
exists** (on a branch, with a worked example). Where its view and the proposals below
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
was shown on a worked example on 15 November 2026, made from the development run of one
cell that secretes a species. It conforms to most of this note. Where it differs, by
design, the viewer reads what the writer gives:

- **Two time bases.** `time` is `{"unit": "s", "bases": [...]}`, each base
  `{"id", "array", "says", "files": [{"file", "rows": [from, to]}]}`: the state's rows
  (`accepted`) and the observed rows (`observation`), each with the files that hold it and
  the rows in each file. Every record names its `base`. There is no `time.file` and no
  `time.array`.
- **A record's file comes from its base, and it has no label.** A record has `id` (its
  array's name), `field` (the engine's name for the quantity), `array`, `base`, `axes` over
  sets (the species among them), `set`, `unit`, `layer` and `owner`. What the page calls a
  field is the viewer's own catalogue of names.
- **Padding slots are null, and cells carry lifetimes.** A set's `ids` holds null for a slot
  that has no entity, and every array keeps a column for it. `cell.lifetimes` gives, for
  each cell, null or its birth and its retirement (either may be null).
- **Signs name roles.** `sign` is `{"says", "from", "to", "confirmed"}`, with `from` and
  `to` the roles of the record's set: `inside` and `outside` for a membrane patch and what
  lies on one, `sender` and `receiver` for a junction or a face, `exterior` and `node` for
  an outside node. A positive value goes from `from` to `to`. The proposals above, and the
  viewer's older packages, say `first` and `second`, or `cell` and `outside node`; the
  viewer reads both sets of words.
- **Constants have no label and no set.** A constant has `id`, `unit`, `axes`, `values`,
  `from` and `says`; the set it lies on is the one its values run along, beside the species.
- **Added by the writer:** `constants`; `unstated` (`[{"id", "what", "why"}]`: what the
  view does not state, with the reason); `recording` (`{"mode", "subset"}`: whether only
  some fields, elements or rows were recorded); a layer's `owner` beside its
  representation, which is never null; a record's `writers` and `note`; and for a total
  either `"monotone": "non-decreasing"` or `resets`.
- **A total that restarts.** A dissipated-energy ledger only grows (`monotone`), except
  where an operator retires a slot: the retired slot's history moves into that operator's
  own record, and the ledger restarts at nought on that slot. Such a record carries
  `"resets": {"by": [laws], "says": "..."}` in place of `monotone`. No rate is taken across
  a reset (`schema/QUANTITY_LAYERS.md`, rule 1): the events of the layers that those laws
  own say when it happens, and at which cell.
- **More about the sets.** `species.valence`, and `species.species` (each species'
  identity, and the operator that declares it); `outside.reservoir` (the held baths); a
  membrane set that `holds` "membrane patch", with each patch's `laws`, `pumps` (null, or
  `{"id", "law_id", "per_cycle": [{"role", "species", "count"}], "per_cycle_sign":
  "inward-positive"}`) and `calcium_pumps`; an operator's own sets (`exchange_route`, which
  `holds` "exchange route", lies on its membrane and names its `owner`); and the sets
  `node`, `world`, `gate` and `floating_component`.
- **Events name entities by id** (`"at": {"cell": "cell_0"}`), and a cell's birth and its
  retirement are events.
- **No positions without a builder.** `space` is null and each set's `geometry` is null
  where the caller gave no geometry, and `unstated` says so.

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
publishes the runs knows every file without opening one.

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

### A run written by the engine's shared output path

The adapter `standard-history` reads a run folder that the engine's own writers made
(`cells.io.write_run`, or `cells.window_io.write_windowed_run`): `resolved_config.json`
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
- **Refused:** a view that records a subset (`recording.subset`), which the adapter does
  not read yet; a view whose files, arrays, rows or shapes are not as it says; an example
  (`example.json`) with a view beside it.

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
