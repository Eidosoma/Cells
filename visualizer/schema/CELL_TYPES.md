# Cell types: a cell of a species, as a file of its own

Status: **proposed for the viewer, 16 November 2026**. The user chose option B of
`docs/CELL_TYPES_DESIGN.md`, and its "Decided" section settles the details. This note is the
contract that note's step 5 asks for. The shared rules (ids, the `modelled` ladder, citations,
sources, the switch, the address) are in `ENTRIES.md`. The reader is `tools/lib/entries.py`. The
scene and the page do not read these files yet.

A cell type is a cell of a species. **Every species has at least one:** the cell its own `cell`
block describes (`SPECIES.md`), with the name its top-level `cell_type` gives it, or `cell` where
it gives none. A species with more than one names the others in `cell_types`, each in a file of
its own.

## File

`data/cells/<species>.<id>.json`. There is none yet: the first will be the human's ventricular
cell, when the user's order of work reaches it. The repository's only examples are test
fixtures, under `tests/entries-fixtures/cells/`.

```json
{
  "format": "cells.visualizer.cell_type@1",
  "species": "brightfin",
  "id": "ciliated",
  "label": "Ciliated cell",
  "order": 20,
  "plain": "One or two sentences on what the cell is.",
  "modelled": {"state": "planned", "text": "...", "record": [{"path": "docs/DECISIONS.md", "where": "D999"}]},
  "levels": [
    {"id": "cell", "shape": {"kind": "capsule", "length_um": 30, "across_um": 8}, "note": "..."},
    {"id": "tissue", "shape": {"kind": "cell sheet", "rings": 3}, "note": "..."}
  ],
  "parts": {"membranes": 1, "wall": false, "nucleus": true},
  "capabilities": {"cap.channels": {"place": "present", "state": "planned", "says": "...", "record": [{"path": "docs/DECISIONS.md", "where": "D999"}]}},
  "engine": {"definition": null, "parameter_set": null, "says": "No definition yet.", "provisional": true},
  "loop": null,
  "proteins": null,
  "facts": [],
  "sources": {}
}
```

## Rules

- **`species` and `id`** match the file's name. The species exists and lists the type in its
  `cell_types`.
  - A type that it does not list is remarked on and is not shown.
  - A type with a breach (or one in a loop of `extends`, or one that extends a type the species
    does not have) is warned of and left out alone. Its species stays, with its other types.
- **`modelled`** follows `ENTRIES.md`: one word of the ladder, with its record. A cell type of a
  file of its own is never `generic`; only a species' own cell is. The rule decided for cell types
  holds: a cell type whose design note is not a tracked file of main is at most `planned`, and it
  is `designed` once that note is a tracked file of main.
  - **The human's ventricular cell meets `designed` now.** Its design note,
    `docs/HUMAN_CARDIAC_LAWS_DESIGN.md`, became a tracked file of main on 16 November 2026 (main
    at `3b7f1cff` holds it, entered at `349f5483`, status "PROPOSED").
  - D183 and D184 decide it, and its code is not on main. Its file, when made, gives `designed`
    with `"design": "docs/HUMAN_CARDIAC_LAWS_DESIGN.md"`.
- **`levels`** give the type's own `cell` and `tissue` levels, each with a shape as
  `SPECIES_SHAPES.md` sets it out, and framing as `SPECIES.md` does.
  - A level left out is the parent's, or the species' own.
  - The species keeps its `organ` and `organism`. A cell type does not give them.
  - A shape kind the viewer does not draw is warned of, as for a species. So a new kind (a
    flat-ended cylinder, a chain of cells) needs a drawing first.
- **`parts`** take the vocabulary of `cell.parts` in `SPECIES_SHAPES.md`. A part the viewer does
  not know is a warning.
- **`capabilities`** are keyed by the map's ids, as in a species file, with `place` (`present` or
  `absent`, `why` for absent) and `note`.
  - A capability may also give its word in this type: `state`, one word of the ladder, with
    `says` and `record`, and `design` or `model` where its word asks for them. It stands for what Cells models of that capability in this cell. The
    panel shows it as "in this cell", beside the capability's own status from the map.
  - The ladder's rule holds here too: a design note on a development branch moves no word.
- **`extends`** names another type of the same species: one with a file, or the species' own.
  - Every field the variant leaves out is its parent's. Its own `id`, `label`, `order`,
    `modelled` and `differs` are never taken from the parent.
  - `differs` is then required: `{"in": "parameters" or "structures", "says", "record"}`. A
    variant that differs in parameters only is drawn the same as its parent, and the panel says so.
  - A chain of `extends` may not loop.
  - The epicardial and M cells of the human get no file and no row (the "Decided" section): one
    sourced sentence in the endocardial cell's panel says that they will differ in parameters
    only. `extends` is exercised by a test fixture.
- **`engine`** (optional, every field optional) is the binding to the engine. No field may hold
  an id that the engine's record does not give.

  **The lead's provisional answers of 16 November 2026, as the coordinator passed them on, are
  labelled provisional.** The record of main does not hold them:
  - **A cell type is read as an engine *definition*:** a declared structure, plus a cited
    parameter set under `validation/`, with a stable id. The cardiac design note puts the human
    cell there.
  - So `definition` is that stable id, `structure` the laws and kinds it declares, and
    `parameter_set` the parameter set's id. `models` and `operators` are the engine models and
    operators its runs name. `says` is a plain sentence.
  - `provisional: true` marks the block for as long as these answers are provisional. While it
    stands, the panel says that the binding is the lead's provisional reading.
- **`loop`** (optional) is the id of the type's looping run among the packaged replays. It moves
  here from `SPECIES.md`'s `cell.loop`, which the present reader refuses.
  - The species' own type gives it in `cell_type.loop`.
  - **Provisional:** a `cell_type` label beside `species` in a looping run's block (`view.loop`,
    `RUN_VIEW.md`) has been passed to the run view's owner as an optional field. Where a run
    gives it, the page holds it equal to the type; where a run does not, the type's `loop` alone
    names the run.
- **`proteins`** (optional): `{"mark", "value", "sources"}`, the set of the species' own proteins
  that this type holds, picked out by a mark of `SPECIES_PROTEINS.md`.
  - It is given only where a permissive source gives the set.
  - Getting such a source needs the user's approval first (README, "Next").
  - None is given today.
- **`facts`, `sources`, `notes` and `plain`** are as in a species file, held to the same licence
  classes.

## The species' own type

A species file with no `cell_type` is read as having one cell type:
- its id is `cell`;
- its label is "Generic cell" where the species is `generic`, and "Its cell" otherwise;
- its levels are the species' `cell` and `tissue` levels;
- its parts, capabilities and facts are the `cell` block's;
- its `modelled` is the species'.

So every species file of today is read unchanged. The only addition is the cell-type block its
entry carries in the scene.
