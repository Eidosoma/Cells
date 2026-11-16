# Species shapes: the kinds, their parameters and the parts of a cell

Status: **companion to `SPECIES.md`, 14 November 2026.** `SPECIES.md` fixes what a species
file holds. This note fixes what the viewer can build from it: the kinds of shape, what
each takes, and the parts a cell may hold. The user: "the cell chapes, organ shape and
body shape must bve configurable as well based on our different species as we add them".

The viewer holds no drawing that belongs to one species. Every cell, sheet, organ and
body is built from the parameters below. A kind, a parameter or a part that is not in
this note is a warning when the scene is built, so a strict build fails.

All sizes are in micrometres. Angles are in radians.

## A cell: `levels[cell].shape`

| Kind | Takes | What is drawn |
| --- | --- | --- |
| `sphere` | `across_um` | A round cell |
| `capsule` | `length_um`, `across_um`; `tip_um`, optional, the width of its narrow end | A rod with round ends, lying on its side. With `tip_um` it narrows evenly from its full width at one end to that width at the other, round all along: a club |
| `prism` | `sides` (3 to 12); `across_um` between opposite sides, or `radius_um` from the centre to a corner; `height_um`; `corner_um`, how round the upright edges are; `edge_um`, how round the edges of the outer face and the base are | A flat-sided cell, as one packed in a layer |

`corner_um` and `edge_um` may be left out; the viewer then rounds the edges a little.

A cell that keeps its width and then narrows into a short tip of its own length (a flask)
is not a kind yet: `tip_um` narrows the whole cell, so such a cell is given as a plain
`capsule` and its note says what the shape cannot show.

The viewer opens every cell with one flat cut and lays its contents out on the cut face.
Where the cut lies, how parts are spread and the "Schematic" enlargement are the viewer's
own, the same for every species. A cell under 2 µm across is drawn in one size mode only:
at that size its molecules are large enough to see, so the picture is already near scale.

A cell of a species that has a tissue level is drawn as one cell of a layer, with its
neighbours round it, side against side (four for a four-sided `prism`, six for any other
cell), and a thin plate under the layer, as scenery. A cell of a species without one
stands alone.

The `molecules` level is the same for every species: a stretch of the cell's membrane,
seen close, with a channel in it. Where a species marks ion channels `absent`, the
close-up shows a pump, and says in the species' words that no channel has a place there.

## What a cell holds: `cell.parts`

| Part | Value | Drawn as |
| --- | --- | --- |
| `membranes` | 1 or 2 | The cell membrane; a second one is an outer shell, as scenery |
| `wall` | true or false | A wall outside the membrane, as scenery |
| `nucleus` | true or false | A nucleus with its double envelope, its pores, a nucleolus and chromatin. It is a part of the map (planned; the user, 16 November 2026, `docs/CELL_STRUCTURES.md`) |
| `organelles` | a list from `er`, `golgi`, `mitochondria`, `chloroplasts`, `vacuole` | The organelles the cell holds. The first three are an animal cell's: left out, a cell with a nucleus has those three and a cell without one has none. `chloroplasts` and `vacuole` (one large central vacuole) are a plant cell's, and are named only where the file lists them. Both are scenery: a chloroplast is a lens against the inside of the membrane; the vacuole takes the cell's own shape and presses the other parts to the side. The vacuole is neutral glass. A chloroplast is green, as it is in life, where the cell is coloured by kind (the user, 16 November 2026: the one piece of scenery with a colour of its own), and neutral where colour shows status, since green there says "qualified" |
| `organelle_sizes` | keyed by organelle: `count`, `volume_fl`, `across_um`, `share`, `sources` | How many of an organelle the cell holds and how large each is, or what share of the cell's volume it fills (above 0, at most 1). Each a number or a range of two, with the keys of its sources; each number is also a fact of the species' card. `chloroplasts` are drawn from `count` and `across_um`, and the picture says how many of how many; the `vacuole` from `share`, in both size modes |
| `wall_nm` | a thickness in nanometres, or a range of two | How thick the wall is, for a cell with a wall. To scale the wall stands that far outside the cell membrane; in the schematic picture it is enlarged |
| `chromosome_kbp` | a length in thousands of base pairs | A chromosome lying free in the cell. Only for a cell without a nucleus |
| `ribosomes` | a count | Ribosomes, a part of the map (planned; the user, 16 November 2026). Where the count is given, the share of it that lies in the part of the cell kept below the picture's cut is drawn (300 of Syn3A's 500), and the panel says how many of how many; where none is given, the number drawn is the picture's choice and the panel says so. Every cell has them |
| `appendages` | a list, as `SPECIES.md` sets out | Threads and hairs that stand out from the cell (a flagellum, a pilus), as scenery; each may name the machine at its foot. A piece of scenery that the species' file describes can be chosen: its panel says that it is scenery and gives the file's numbers with their sources |

A capability is drawn where its structure is. Marked `absent` in `cell.capabilities`, it
is not drawn and the species' card lists it with its `why`. A capability that is present
but whose structure the cell does not hold (calcium stores without `er`, say) cannot be
drawn; the build remarks on it.

## A tissue: `levels[tissue].shape`

| Kind | Takes | What is drawn |
| --- | --- | --- |
| `cell sheet` | `rings`, how many rings of cells lie round the middle one (6 gives 127 cells packed in sixes, or 13 by 13 packed in squares); `beyond`, optional, a list of `[ring, strength]` out to which the layer goes on as faint outlines | A single layer of the species' own cells, packed side against side, each as wide and as tall as the cell |

The sheet stands for the one Cells simulates. It is packed as the cell's sides ask, so
that its cells stand side against side: in squares for a four-sided cell, in sixes for
any other. The sheets Cells has run are joined in sixes; where a sheet is drawn in
squares, that packing is the picture's choice, and the level's note says so.

## An organ or a body: `levels[organ].shape`, `levels[organism].shape`

Both are of the one kind `outline`: lines drawn from a shape file, as a placeholder for
a scale nothing simulates.

```json
{"kind": "outline", "ref": "planarian", "parts": ["nervous system"], "context": ["body"]}
```

| Field | Meaning |
| --- | --- |
| `ref` | The shape file `data/species/shapes/<ref>.json` |
| `parts` | The names or groups of the file's parts that are this level's own. Left out: all of them |
| `context` | Parts drawn faintly round them, to show where the level lies. Left out: none |

### The shape file

```json
{
  "format": "cells.visualizer.outline@1",
  "note": "What the outline is and what its sizes rest on.",
  "tissue_on": {"at_um": [790, 147.2, 0], "clearance_um": 3},
  "parts": [
    {"name": "body", "kind": "loft", "stations": [[0, 0, 0, 0, 0]], "strength": 0.5, "edge": 1, "fill": 0.07, "pick": 20}
  ]
}
```

- **The frame.** Points are `[x, y, z]`: x runs along the body from its front, y is up, z
  is across. `tissue_on.at_um` is the point of the body's surface on which the species'
  sheet of cells lies, and `clearance_um` the gap left under the sheet. The scales are
  nested there: zooming out from the sheet leads into the organ and then the body.
- **`parts`** are drawn in the order given. Each has a `name`, may share a `group` with
  others, and has a `kind`:

| Kind | Takes | What is drawn |
| --- | --- | --- |
| `loft` | `stations`, each `[x, y, z, half_width, half_height]` along the part's middle line, with an optional sixth number (a thin flap that widens the edge) or a seventh and eighth (the direction across the part, where its middle line bends) | A body of oval section: its outline seen from above (`edge`), rings round it (`rings`), lines along it (`lines`, as turns round the section in units of π), and a faint fill (`fill`) |
| `lines` | `paths`, each `{"points": [[x, y, z]], "closed": false}` | Lines |
| `discs` | `at`, a list of points; `radius_um` | Small filled discs lying flat |

- **Strengths** run from 0 to 1: `strength` for a part's lines, `edge` for a loft's
  outline, `fill` for its fill, and `alone` for the part's lines at a level that names
  it among its own parts. `context` is `{"edge", "fill"}`: the strengths used when the
  part is another level's surroundings. Only a loft can be a level's surroundings.
- **A loft's middle line** may bend and rise: where a station gives no direction across
  the part, it is level and at right angles to the way the line runs there. So a limb or
  a vessel is a loft along its own path.
- **`rings`** is `{"from": 0.04, "to": 0.97, "step": 0.04, "points": 28}` in fractions of
  the part's length, or `{"every": 8, "first": 4, "points": 18}` in stations.
- **`pick`** is the number of sides of the unseen skin that makes the part clickable.

## How a level is framed (all optional)

A level of a species file may also give:

| Field | Meaning |
| --- | --- |
| `notes` | Sentences written beside the drawing: a list of strings, or of `{"text", "short", "at_um", "lift", "roomy"}`. `short` is the form on a narrow screen; `roomy` marks a note that is left out there |
| `centre_um` | The middle of the level in the shape file's frame. Left out: the middle of its own parts |
| `view` | `{"frame_um": [width, height], "toward_um": [x, y, z], "azimuth", "polar"}`: the stretch the camera frames, where it looks from the centre, and from which side |
| `label_um` | Where the level's name is written, from its centre |
| `sheet_mark` | `{"band", "note", "note_at_um", "roomy"}`: the ring that marks the sheet at this level, and the words beside it |
| `fade_in_um`, `fade_out_um` | The camera distances between which the level appears and gives way |

Left out, each is worked out from the sizes of the shapes, so a species needs only its
shapes to be drawn: the camera frames the level's own parts, and one level gives way to
the next between their two stops. `sheet_mark` is the exception: no ring is drawn unless
the level asks for one.

The sheet's ring is to scale where the sheet can be seen. Beside a body thousands of
times its size it could not be, so the ring is then drawn large enough to find, and the
note beside it must say that it is not to scale.

## What follows from a species without code

- The species switch lists every species, in their `order`; the page opens on the one
  that says `default`. The switch stands in the bar while the bar holds it with any
  species' statement beside it, and at the head of the view's card otherwise.
- Beside the switch stands what Cells models of the species, in the words of its
  `modelled.state`; pressing it opens all the species file says. Under the picture of a
  species whose state is `proposed`, the page says that nothing of it is in the engine.
- The scale rail has a stop for each level the species lists, under the level's `label`.
  A species with no level beyond its cell shows its `no_further_levels` sentence under
  the rail and where those levels would be, and zooming out ends at its cell.
- A capability marked `absent` is not drawn, cannot be chosen and is not in the list of
  parts; the species' own panel lists it with its `why`. A capability of a level the
  species lacks is listed there with `no_further_levels` as its reason.
- A species whose atlas found nothing for most of the units is shown quietly in the
  protein atlas: those units are drawn faint, with no ring beside each.

## Adding a species

1. `data/species/<id>.json`, as `SPECIES.md` sets out: its levels with a shape each, the
   parts of its cell, and the capabilities that have no place in it.
2. For an organ or a body, `data/species/shapes/<name>.json`.
3. Optionally its side of the protein atlas, `data/proteins/atlases/<id>.json`
   (`SPECIES_ATLAS.md`). Without one the atlas shows the units and says the species has
   no atlas yet.

Then `python3 tools/extract_architecture.py --strict`. No code changes.
