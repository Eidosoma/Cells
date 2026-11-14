# Run view: what a run saves so that it can be visualised

Status: **draft from the visualizer side, 14 November 2026**, for the lead's design note
under D154. Names here are proposals; the engine-side note fixes the final file and field
names, and the viewer adapts.

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
| Records | `records.npz`: `t`, `vm`, `conc`, `osm`, `abundance`, `gate`, `generation` | No units or axes written down |
| Events | `definition.json` `replacement_events`, `plan.json` `events` | None |
| Representation | Not stated | Missing |

## Until the engine writes this

The visualizer keeps adapters under `visualizer/tools/` that build the same structure from
an existing run directory and mark it `"derived": true`, with a line saying how each missing
piece was derived. For E07-v1 the sheet is a regular hexagonal sheet, so positions are
derived from the saved junction topology. Adapters read saved files only.

## Open points for the engine-side note

- The file's name and whether it is one file per run or one per experiment with per-run parts.
- Whether geometry goes in the view file or in an array file it points at (large tissues).
- How an operator declares its layer and representation, so the view file is assembled from
  declarations and not written by each driver.
- Record names: the viewer can use the engine's readout names directly if they are stable.
