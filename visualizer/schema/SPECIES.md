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
  "group": "Bacteria",
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
    "key": {"text": "Authors (year) Title. Journal.", "doi": "10.0000/example", "licence": "CC BY 4.0", "class": "permissive", "accessed": "2026-11-14"}
  }
}
```

## Rules

- **`group`** (optional) is the heading the species stands under in the page's list of
  species, in a few words: `Animals`, `Bacteria`. Species with the same heading stand
  together, the headings in the order of their first species and the species in the order
  of `order`. A species without one stands under no heading. The headings come from the
  files alone: the viewer holds no list of them.
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
- **A capability that the map keeps out of the picture.** The map's overlay may flag a
  capability with `left_out` (`data/architecture/overlay.json`; the same flag as on a
  unit of the protein atlas, `schema/SPECIES_ATLAS.md`): it is then no part of the scene,
  and the cell does not draw its structure, even as scenery. A species file may still
  name a place for it. That entry is read and held to this contract like any other, and
  is not carried into the scene; the builder says so in a remark. The file is not
  changed, so the place is there again when the flag is removed. The engine parts that
  implement the capability stay on the Engine view, which maps the code; the flag's
  `engine_note` is added to their text, so each says that it is not drawn elsewhere.
- **`cell.parts`** says what the cell holds, from a fixed list the viewer can draw:
  how many membranes, a wall or none, a nucleus or none, the organelles it holds (an
  animal cell's `er`, `golgi` and `mitochondria`; a plant cell's `chloroplasts` and
  `vacuole` beside them), a chromosome and its length, a count of ribosomes.
  `organelle_sizes` gives, for an organelle the cell holds, how many there are (`count`),
  how large each is (`volume_fl`, `across_um`) or what share of the cell's volume it fills
  (`share`), each a number or a range of two with the keys of its sources; `wall_nm` gives
  a wall's thickness. Each is a fact of the card as well. `SPECIES_SHAPES.md` gives the
  list. A part the viewer does not know is a warning.
- **Appendages are a general part** (the user, 15 November 2026: "lets draw flagella, pili
  as a general feature, and with the optoin later to soom into the motor").
  `cell.parts.appendages` is a list, and each entry describes one kind of thread or hair
  that stands out from the cell, for any species:

  ```json
  {"kind": "flagellum", "label": "Flagella", "count": [4, 10], "length_um": [5, 10],
   "width_nm": 20, "where": "all over", "from": "inner membrane",
   "base": {"id": "flagellar-motor", "label": "Flagellar motor", "mark": "complex", "value": "flagellum"},
   "sources": ["a key of the species' sources"]}
  ```

  - `kind` is a word the viewer can draw: `flagellum` (a long, wavy thread), `pilus` (a
    short, straight hair); others are added as a species needs them.
  - `count`, `length_um` and `width_nm` are a number or a range, each with a source; `where`
    says where on the cell they stand (`all over`, `one pole`, `both poles`, `one side`),
    and `from` which of the cell's membranes they start at. The poles are the two ends of
    the cell's long way.
  - **Drawn as scenery.** Nothing in the engine stands behind an appendage, so it is drawn
    in the neutral glass of scenery, and its panel says so. Of a range the middle is
    drawn. Where the count is too large to draw, a part of it is drawn (at most 12
    flagella and 120 pili, on the part of the cell that the cut keeps) and the picture
    says how many of how many. A thread far longer than the cell is drawn whole: the cell
    stays framed as it is, the picture says how long the threads are, and the camera may
    go out until the whole of them shows.
  - **It can be chosen.** Its panel gives the file's numbers with their sources, and what
    was drawn.
  - **`base`** names the machine at the foot of the appendage (a flagellum's motor), so
    that a closer view of it can be added later: its `id` and `label`, and the mark and
    value under which the species' own proteins list its parts
    (`schema/SPECIES_PROTEINS.md`, `highlights`). A base is drawn where the kind's drawing
    gives the thread a foot. Until the closer view exists, choosing the foot opens a
    panel that says what the machine is, with a door into the Protein atlas: the species'
    own proteins, with that mark's value picked out.
- **A species may be held back from the picture.** Where the viewer cannot yet draw what
  a species' cell needs, its files are kept and checked like any other, and the map's
  overlay names it under `species_held` with since when, how the page names it and why.
  The scene then carries nothing of it but one line among what is left out; taking the
  entry away brings the species in. A species is never shown with parts it does not have
  in place of the ones it has. (Thale cress was held so on 15 November 2026, until a
  plant cell's chloroplasts and vacuole could be drawn; no species is held today.)
- **Every number has a basis.** A size or a count in `shape` or `parts` is either a fact
  with a source in `cell.facts`, or it is said in the level's `note` to be the picture's
  choice.
- **`cell.facts`** are what the species' card lists: a label, a value with its unit, and
  the keys of its sources.
- **`sources`** are keyed. Each has `text` and a `doi` or a `url`, and the day it was
  read. What may be taken from a source is set by its class, in the next rule.
- **Every source has a `class`, and the file holds no value from a source that is not
  permissive** (the project's rule, D173, 15 November 2026). `class` is one of
  `permissive` (CC BY, CC0, or a plain statement that no restriction is placed on use),
  `non-commercial` (a CC BY-NC licence of any kind) and `no stated terms`; `licence`
  states the terms the class rests on, or that none is stated. Only a permissive source
  may stand behind a number, a fact, a level or a capability's words: a fact's and a
  level's `sources` name permissive sources alone, and `capability_sources`, keyed by
  capability, names the permissive sources of a capability's text. A source of another
  class is a pointer: a fact names it in `see`, its `text` says what is to be read there
  and gives no value, and nothing is taken from it. This narrows the allowance above for
  numbers and short quotations. `tests/licence_classes.test.mjs` holds every record to it.
- The file holds no machine path and no host name.

## In the scene

The builder reads every file in `data/species/` and puts them, ordered, into the scene's
`species` list. A breach of this contract is a warning. The viewer keeps one species for
the whole page: the levels of the Cell and scales view, the cell drawn, and the species'
side of the protein atlas all follow it.
