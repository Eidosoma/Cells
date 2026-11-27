# Model systems: an entry of the switch that is a model, not an organism

Status: **proposed for the viewer, 16 November 2026**. The user's answers to the origin-of-life
note (`docs/ORIGIN_OF_LIFE.md`, "Decided", 16 November 2026) ask for it: "Origin of life" is a
new heading in the species switch, and a GARD assembly is a model system, not a species, "a new
kind of entry, with four levels of its own (Molecules, One assembly, Population, Lineages)". The
shared rules (ids, the `modelled` ladder, citations, sources, the switch, the address, the clock)
are in `ENTRIES.md`. The reader is `tools/lib/entries.py`. The scene and the page do not read
these files yet.

A model system is a model in its own right, such as a GARD assembly: integer counts of molecule
types that grow and split, with no shape, no place and no clock of real life. It is not an
organism. It has no taxon, no cell, no tissue and no organs. It has the levels of its view's kind
and a view of its own.

## File

`data/models/<id>.json`. The first is `data/models/gard.json`.

```json
{
  "format": "cells.visualizer.model_system@1",
  "id": "gard",
  "label": "GARD assembly",
  "is": "A model, not an organism",
  "plain": "What the model is, in two or three plain sentences.",
  "group": "Origin of life",
  "order": 100,
  "made": "2026-11-16",
  "modelled": {"state": "proposed", "text": "...", "record": [{"path": "visualizer/docs/ORIGIN_OF_LIFE.md", "where": "Decided"}]},
  "view": {"kind": "assembly"},
  "levels": [
    {"id": "molecules", "label": "Molecules", "shows": "..."},
    {"id": "assembly", "label": "One assembly", "shows": "..."},
    {"id": "population", "label": "Population", "shows": "...", "waits": "..."},
    {"id": "lineage", "label": "Lineages", "shows": "..."}
  ],
  "clock": {"base": "fission", "says": "..."},
  "runs": [{"file": "data/origin/example-run.json", "label": "An example of invented numbers", "kind": "example"}],
  "facts": [],
  "sources": {}
}
```

For a vesicle replay, optional `view.catalysis_entry` names a separate assembly entry with a
recorded development run. The molecular traffic and times in the vesicle replay remain those of its own world.

## Rules

- **`id`** matches the file's name, and it is not a species' id.
- **`label`, `is`, `plain`, `group`, `order` and `made` are all required.**
  - `is` is the line the switch shows where a species shows its organism.
  - `group` is its heading in the switch. A model system always stands under a heading.
- **A model system is never the page's default.** It takes no `default`, and nothing of an
  organism: no `organism`, `taxon`, `cell`, `cell_type`, `cell_types` or `no_further_levels`.
  Any of these is a breach.
- **`modelled`** follows `ENTRIES.md`. A model system may use every word but `generic`: no
  generic model stands in for it. Its record is required.
- **`view.kind`** is a word for a view the viewer has, or will have. Each kind has its own fixed
  list of levels, in order:

  | `view.kind` | Its levels, in order | Required | Their labels where the file gives none | Its runs' format |
  | --- | --- | --- | --- | --- |
  | `assembly` | `molecules`, `assembly`, `population`, `lineage` | `molecules`, `assembly` | Molecules, One assembly, Population, Lineages | `cells.visualizer.assembly_run@1` (`ASSEMBLY_RUN.md`) |
  | `vesicle` | `vesicle`, `membrane`, `molecule` | `vesicle` | Vesicle, Membrane, Molecule | `cells.visualizer.assembly_run@2` (`ASSEMBLY_RUN.md`) |
  | `physarum` | `network`, `vein` | Both levels | Plasmodium, Vein cutaway | Anatomy preview |
  | `haloferax` | `cell`, `envelope` | Both levels | Whole cell, Envelope cutaway | Anatomy preview |

The Physarum preview uses `view.protein_atlas` for the organism's protein shelves,
`view.machine_bench` for its structure bench and `view.engine_part` for its Engine catalogue
entry. It depicts a plasmodium and a cutaway and labels the geometry and flow as illustrative.
The Haloferax preview uses the same catalogue links and illustrates rod and plate forms.

  A kind not in this table is a breach, and so is a level not in its kind's list, or one out of
  order. A further kind (an RNA world, say) is a row of this table, with the view that draws it.
- **Each level** has its `id`, and may give `label`, `shows` and `waits`.
  - `shows` says in plain words what the level will show.
  - `waits` says what it waits for before it can show it, such as a run of a population.
  - A level may also give `note`, a sentence written beside the drawing, as a species' level does.
- **`clock`** is `{"base", "says"}`.
  - `base` is the word a run of the model states as its `time.base`: `fission` (or `second`).
  - `says` is the line shown before a run is loaded.

  It is a label only: the run states its own clock, and where the two differ the run's is shown
  (`ENTRIES.md`, "The clock"). The reader holds each run file the entry names to the same base.
- **`runs`** are the run files the model system opens on, the first shown first. Each is
  `{"file", "label", "kind"}`:
  - `file` is a path under the viewer's `data/`, to a file in the format of its view's runs (for
    `assembly`, `ASSEMBLY_RUN.md`);
  - `kind` is `example` (invented numbers, marked as such on the picture and in the legend),
    `development` or `experiment`.

  The reader holds each file to that format, to a `model.id` equal to the entry's id, to the
  clock's base, and to its kind: a file with an `example` block is the entry's `example`, and no
  other run is. The Experiments view lists them and opens each in the model system's own view.
  The list may be empty.
- **`facts` and `sources`** are as in a species file, held to the same licence classes
  (`ENTRIES.md`).
  - A fact states no number that its sources do not give.
  - **The file binds to no name of the engine's that is not on main.** No law, operator, record
    or kind of a proposed design note is named in it. The view's contract maps runs to records,
    and an adapter is written when the engine's first run exists.

## What the view gets, matched with the view's own contract

The assembly view's contract, `ASSEMBLY_RUN.md`, came onto disk while this one was being written.
Its section "What the lens needs from an entry" asks for five fields, and this contract gives each:

| It asks for | This contract gives |
| --- | --- |
| `id`, matched with the run's `model.id` | `id`. The reader holds each run file's `model.id` to it |
| `kind: model system`, to open its lens and not the Cell view | `kind: "model system"`, which the reader writes. **The one difference:** this contract also gives `view.kind` (`assembly`), so that a second view for another model can be added later. The assembly lens opens for `view.kind: "assembly"` |
| `levels: [{id, label}]`, ids from `molecules`, `assembly`, `population`, `lineage` | The same ids, in that order, with the labels filled in where a file gives none |
| `runs`: the run files it names, with their labels; the first is shown first | `runs: [{file, label, kind}]`. `kind` is added, so that the Experiments view can stand an example apart, as it does for the replays |
| `modelled: {state, text}`, word for word on the card | The same, with `record`, `design` and `model` beside them (`ENTRIES.md`) |

It also gives more than the lens reads today:
- `group` and `is`, for the switch;
- `plain`, `facts` and `sources`, for the card, and `notes`, sourced notes of the record shown beside its word (`ENTRIES.md`, "Notes");
- each level's `shows` and `waits`;
- `clock`, a label held to the runs' `time.base` (`fission`; `ASSEMBLY_RUN.md`, "time").

**The entry gives the words; the view draws everything.** Every shape, colour and motion is the
view's, labelled as the picture's choice where it is.
