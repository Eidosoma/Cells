# Species: what changes when the viewer's species changes

Status: **fixed for the viewer, 14 November 2026**, so that the species' data and the
switch can be built side by side. The user, the same day: "for the visualization we must
be able to switch species that will change the different levels", and of the minimal cell
JCVI-syn3A: "we want a switch for syn3a as well ... then of course we will have to switch
off multi-cell, but start a proteint catalog for this one as well". And: "the cell
chapes, organ shape and body shape must bve configurable as well based on our different
species as we add them".

The viewer shows one species at a time, in every view that depends on a species. A
species file says which levels the species has, the shape drawn at each, which of Cells'
capabilities have a place in its cell, and what Cells models of it. The species' side of
the protein atlas (`SPECIES_ATLAS.md`) is a separate file with the same id.

**A species is added with files alone.** Its levels and its shapes are data: the viewer
builds every cell, organ and body from the parameters a species file gives, and holds no
drawing that belongs to one species.

This is the viewer's data. The engine has no species switch, and a species file never
says the engine models an organism unless the project's record says so.

## File

`data/species/<species id>.json`

```json
{
  "format": "cells.visualizer.species@1",
  "id": "syn3a",
  "label": "Syn3A",
  "organism": "JCVI-syn3A",
  "taxon": 2144189,
  "plain": "One or two sentences on the organism and why it is here.",
  "order": 30,
  "default": false,
  "made": "2026-11-14",
  "modelled": {
    "state": "proposed",
    "text": "What Cells models of this species, in one or two plain sentences."
  },
  "levels": [
    {"id": "molecules"},
    {"id": "cell", "label": "One cell", "shape": {"kind": "sphere", "across_um": 0.4}, "note": "A sentence shown at this level.", "sources": ["key"]}
  ],
  "no_further_levels": "A single-celled organism: it forms no tissue, organ or body.",
  "cell": {
    "facts": [
      {"label": "Diameter", "value": "about 400 nm", "sources": ["key"]}
    ],
    "parts": {"membranes": 1, "wall": false, "nucleus": false, "chromosome_kbp": 543, "ribosomes": 500},
    "capabilities": {
      "cap.calcium": {"place": "absent", "why": "It has no endoplasmic reticulum."},
      "cap.circuits": {"place": "present", "note": "At the chromosome: there is no nucleus."}
    }
  },
  "sources": {
    "key": {"text": "Authors (year) Title. Journal.", "doi": "10.0000/example", "licence": "CC BY 4.0", "accessed": "2026-11-14"}
  }
}
```

## Rules

- **`levels`** run from small to large. Their ids come from the fixed list `molecules`,
  `cell`, `tissue`, `organ`, `organism`. A species lists only the levels it has;
  `molecules` and `cell` are required. A species without `tissue`, `organ` or `organism`
  gives `no_further_levels`, the sentence the view shows where those levels would be.
- **`shape`** gives the shape drawn at a level as a kind and its parameters, with sizes
  in micrometres. The kinds and what each takes are set out in `SPECIES_SHAPES.md`. For a
  cell they are at least:
  - `sphere`: `across_um`;
  - `capsule`: `length_um`, `across_um`;
  - `prism`: `sides`, `across_um` between opposite sides, `height_um`, and how round the
    corners are.

  A tissue is a sheet of the species' own cells. An organ and a body are outlines: a
  silhouette, a thickness and the inner features to draw, as named curves in the file or
  in a shape file beside it. A kind or a parameter the viewer does not know is a warning,
  so a strict build fails. The `molecules` level needs no shape.
- **`label`** on a level is its name in the view, such as "Brain" for an organ. Left out,
  the level's general name is used.
- **`default`** is true on exactly one species: the one the page opens on. **`order`**
  places the species in the switch, ascending.
- **`modelled.state`** is one of:
  - `generic`: Cells models a generic cell or tissue; this species lends it names or
    outlines. The text says which.
  - `proposed`: a proposal to model this organism exists; nothing of it is in the engine.
  - `modelled`: the project's record says a registered model of this organism exists.
    The text cites the record. No species has this state today.
- **`cell.capabilities`** is keyed by the map's capability ids (`cap.…`). A capability
  that is left out has a place in this cell. `absent` needs `why`; `present` may carry a
  `note` where the place differs from an animal cell's. A capability has a place when the
  organism has the structure or the process it concerns. That says nothing about whether
  Cells has a model of this organism; `modelled` says that.
- **`cell.parts`** says what the cell holds, from a fixed list the viewer can draw:
  how many membranes, a wall or none, a nucleus or none, the organelles of an animal
  cell, a chromosome and its length, a count of ribosomes. `SPECIES_SHAPES.md` gives the
  list. A part the viewer does not know is a warning.
- **Every number has a basis.** A size or a count in `shape` or `parts` is either a fact
  with a source in `cell.facts`, or it is said in the level's `note` to be the picture's
  choice.
- **`cell.facts`** are what the species' card lists: a label, a value with its unit, and
  the keys of its sources.
- **`sources`** are keyed. Each has `text` and a `doi` or a `url`, and the day it was
  read. Numbers and short quotations may be taken from any source that is read; anything
  more is copied only from a source whose terms allow it, and `licence` then states them.
- The file holds no machine path and no host name.

## In the scene

The builder reads every file in `data/species/` and puts them, ordered, into the scene's
`species` list. A breach of this contract is a warning. The viewer keeps one species for
the whole page: the levels of the Cell and scales view, the cell drawn, and the species'
side of the protein atlas all follow it.
