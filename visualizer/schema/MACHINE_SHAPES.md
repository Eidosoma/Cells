# A machine's shape: `cells.visualizer.machine-shape@1`

A machine measured from a Protein Data Bank entry is drawn as ellipsoids at three levels
(Outline, Parts, Subunits), from the viewer's own measure (`tools/measure_particle.py`, kept in
`data/catalogue/measures/`). On 17 November 2026 the user agreed to a fourth, finer level,
**Shape**: a smooth, low-resolution surface for each chain, worked out by the viewer from the
same coordinates; a machine whose chains are too many to tell apart (a ribosome) is drawn as one
solid for each of its parts, the parts meeting at a shared face. This contract says what a shape
file holds, where it lives and is published, how its surfaces map to the parts and chains the
catalogue already names, what the page must say of it, and how a view draws it. A shape is an
illustration: no atom and no ribbon is drawn, and nothing of an entry is copied into the tree but
numbers the viewer worked out itself.

## Where the files are

- One file a machine, never one a chain: `data/catalogue/shapes/<species>.<machine>.json`,
  committed, the same name as the machine's measure in `data/catalogue/measures/` (for example
  `ecoli.atp-synthase.json`; the ribosome's one record is the species files', `data/measures/ecoli.ribosome.json`). Each is under 400 KB (the budget below), far under the 1 MB the
  user set for checked-in data.
- Published beside the page at **`shapes/<species>.<machine>.json`**: the exporter lists every
  such file (`tools/lib/build_page.mjs`, `shapeFiles`), the local server serves it at that path,
  and staging takes it with the page's other files. A view fetches it by that path, as it fetches
  a machine's file (`loadBeside`).
- A machine with no shape file is left as it is: the view offers its three ellipsoid levels and
  no Shape level.

## What a file holds

```json
{
 "format": "cells.visualizer.machine-shape@1",
 "tool": "tools/shape_particle.py",
 "definition": "each chain as the closed surface that holds its own volume (0.135 nm³ for each amino acid, 0.32 nm³ for each nucleotide) in a cloud where each residue is spread as a Gaussian 1 nm wide, on a grid 1 nm apart; of a surface in pieces, its largest and every piece of at least 5% of its volume are kept, smaller ones dropped (listed under dropped)",
 "illustration": "The viewer's own surface of the entry's coordinates, an illustration: ...",
 "parameters": {"width_nm": 1.0, "grid_nm": 1.0, "reach_widths": 3.0, "volume_nm3": {"protein": 0.135, "nucleic": 0.32}, "stands_for": {"protein": ["CA"], "nucleic": ["P", "C4'"]}, "by": "chains", "piece_share": 0.05},
 "entry": "6OQR", "title": "...", "method": "ELECTRON MICROSCOPY", "resolution_A": "3.1",
 "left_out": [],
 "frame": "the measuring tool's frame: origin at the centre of the whole's atoms; y from the part ring's centre to the part head's; ...",
 "unit_nm": 0.01,
 "counts": {"meshes": 22, "vertices": 4718, "triangles": 9348},
 "dropped": [],
 "meshes": [
  {"id": "chain-W", "chain": "W", "entity": "1", "description": "ATP synthase subunit delta", "part": "peripheral-stalk", "kind": "protein", "residues": 173, "vertices": [-297, 897, -143, ...], "triangles": [...]}
 ]
}
```

A machine drawn by its parts (the ribosome, `--ribosome`) holds one solid a part, and its two tones
beside the meshes:

```json
{
 "definition": "each part as one solid: the closed surface that holds its residues' own volume (...), protein and nucleic acid together, in a cloud where each residue is spread as a Gaussian 1.6 nm wide weighted by its volume, on a grid 1.6 nm apart; ...; for two tones, that solid divided where the nucleic acid's share of the cloud is the greater and where the protein's is (under tones, each inside the solid or on it)",
 "counts": {"meshes": 2, "vertices": 2422, "triangles": 4836, "tones": {"meshes": 4, "vertices": 3976, "triangles": 7900}},
 "meshes": [
  {"id": "part-small", "part": "small", "kind": "nucleoprotein", "outer": 1688, "residues": 3916, "vertices": [...], "triangles": [...]},
  {"id": "part-large", "part": "large", "kind": "nucleoprotein", "outer": 2396, "residues": 6022, "vertices": [...], "triangles": [...]}
 ],
 "tones": [
  {"id": "part-small-nucleic", "within": "part-small", "part": "small", "kind": "nucleic", "residues": 1508, "outer": 1306, "vertices": [...], "triangles": [...]},
  {"id": "part-small-protein", "within": "part-small", "part": "small", "kind": "protein", "residues": 2408, "outer": 714, "vertices": [...], "triangles": [...]},
  ...
 ]
}
```

- `assembly` stands after `entry` where the file is a biological assembly's (`1G4A`, assembly
  `1`); `left_out` lists the entities left out of the whole with `--exclude`.
- **`meshes`**, each one closed surface, together the machine as it is drawn:
  - `id`: `chain-<author chain id>` (as the catalogue names a chain, `chain-E-2` in an
    assembly), or `part-<part>` for a part's solid.
  - `chain`, `entity`, `description`: for a chain's surface. `part`: the catalogue's id of the
    part that holds it (`head`, `large`), or null where the measure names no part.
  - `kind`: `protein` or `nucleic` for a chain; for a part's solid, `nucleoprotein` where it holds
    both (else the one kind it holds).
  - `residues`: how many residues it is drawn from.
  - `outer` (a part's solid, and a tone): its first `outer` triangles lie on the machine's
    outside; the rest lie on a face it shares with a neighbouring part (or the other tone), hidden
    while the whole is drawn. A view shades a vertex on the outside by the outside's faces alone,
    so that a seam between neighbours is shaded as the one surface it is.
  - `vertices`: flat `[x, y, z, x, y, z, ...]`, integers; each times `unit_nm` is nanometres in
    the frame. `triangles`: flat indices into the vertices, three a triangle, counter-clockwise
    seen from outside. No normals are stored: the page works them out.
- **`tones`** (only where a part holds protein and nucleic acid): a second set, for two tones. Each
  is a closed surface `part-<part>-nucleic` or `part-<part>-protein`, `within` the part's solid it
  divides: where the part's nucleic acid's cloud is the greater, and where its protein's is. The
  two tones of a part fill its solid and lie inside it or on it; a view draws a part either as its
  solid or as its two tones, never both.
- `counts`: the meshes, vertices and triangles of `meshes`; under `tones`, those of the tones.
- **`dropped`**: what was left out of a surface in pieces (below): for each such surface its `id`
  (`surface`), how many `pieces`, the volume they held (`volume_nm3`, and as so many residues'
  volume, `residues_volume`), how many residues' standing atoms lay inside them
  (`residues_within`), and their `chains`. Empty where nothing was dropped.

## The frame and the units

A shape is in exactly the frame and the units of the machine's measure: the same origin and axes,
in nanometres, so that a surface sits where its ellipsoid sits. A view places a mesh as it places
that measure's bodies (their `centre_nm` and `axes` are in the same frame), and moves and scales
the whole machine as it moves and scales its ellipsoids. The file's `frame` says the frame in
words: the measuring tool's, from the same entry, `--exclude`, `--part`, `--frame-from` and
`--frame-to` as its measure.

## What a consumer may rely on

- Every mesh and every tone is closed: each edge is met by triangles turned both ways, as often
  one way as the other. Every triangle faces out. A few triangles may have no area (three
  vertices in a line); they keep the surface closed.
- A chain's surface holds its residues' own volume to within 2%, with what was dropped of it. A
  machine's parts hold the whole's residues' own volume between them to within 2%: each part is
  the share of the whole's solid where its cloud is the greater, so a part holds about, not
  exactly, its own residues' volume (the ribosome's small subunit 93%, its large one 105%).
- Neighbouring parts meet at one shared face: the vertices of the faces each has inside are the
  same places. A part's two tones fill it, each inside it or on it.
- **Pieces.** A chain may be thin between its domains, so that its surface falls into pieces. The
  largest piece is kept, and every piece that holds at least 5% of the surface's volume; smaller
  slivers are dropped and listed under `dropped`. In E. coli's six files that left out a sliver
  of RNA polymerase's β (about 1 residue's volume) and of σ70 (0.1), and two of SecE's (about 1
  residue's volume together); σ70's piece of 7% (about 36 residues' volume, below the claw) is
  kept. A part's tones may be in pieces (a ribosome's proteins on its RNA).
- **The budget**, held by `tests/machine_shapes.test.mjs`: a file under 400 KB and 20,000
  triangles in all; a ribosome under 8,000 drawn either way (its solids 4,836, its tones 7,900).
  A chain's surface is a few dozen to a few hundred triangles, up to about 2,000 for the largest
  chains (RNA polymerase's β′, 1,325 residues, 1,912 triangles). A phone draws one chosen
  machine at this level without trouble.
- Chains' surfaces may overlap one another where chains pack closely: each is drawn whole.

## How meshes map to the catalogue's ids

- A chain's surface `chain-<id>` is the body the catalogue names `machine:<kind>:chain-<id>`; its
  `part` names `machine:<kind>:<part>`. At the Shape level a part is chosen through any of its
  chains' surfaces, and a part's hue is its chains' hue, as at the Subunits level.
- A part's solid `part-<part>`, and each of its tones, is the body `machine:<kind>:<part>`; drawn
  in its two tones, the nucleic acid may wear its own colour.
- A ribosome is drawn by its parts (`--ribosome`: `large` and `small`): its fifty chains are too
  many to tell apart at this resolution. The other machines are drawn by their chains. Where the
  catalogue names no chains for a machine (the translocon), its chains' surfaces map by their
  `part` alone.
- What is in neither subunit of a ribosome (7K00's tRNAs and messenger) is drawn by no surface
  and listed nowhere in the shape file; the measure lists it under its `left_out`. `--large` and
  `--small` place an entity the caller names in a subunit, as the measuring tool's two-subunit
  mode does (a human ribosome's RACK1, whose name says neither).
- A machine whose catalogue entry draws another species' measure (Syn3A's and M. pneumoniae's
  ribosomes are drawn at E. coli's, as their files say) has no shape file of its own; the view
  offers it E. coli's shape, and the panel says whose shape it is. The file's `entry` is the
  measure's; the organism comes from the catalogue's size for that entry (`of`), since an entry's
  title need not name it (7K00's says "the Bacterial Ribosome").

## What the panel says of a shape

At the Shape level the machine's panel says, in plain words, that the shape is the viewer's own
surface of the entry's coordinates (naming the entry, and the assembly where there is one), by the
file's `definition`, worked out by `tools/shape_particle.py`; that it is an illustration and not
the structure; and that the Protein Data Bank states no surface. The entry stands among the
machine's sources with its terms (CC0). Where the file lists slivers under `dropped`, the panel may
say how much was left out, and of which chains. Nothing says modelled or qualified of a machine.

## How each file is made

The definition is the same for every machine: a chain's surface at 1 nm, a part's solid at
1.6 nm. These widths were weighed on 17 November 2026 against 0.8 and 1.4 nm for a chain and 1.2
and 2.0 nm for a part, on the ATP synthase and the ribosome, and the user chose them the same day:
they hold the budget without a pass that simplifies the surfaces. Later that day a part's one
solid, with its two tones, replaced its separate protein and nucleic-acid surfaces, which stood
apart so that a ribosome's subunits did not meet; and slivers came to be dropped.

How a part's solid is drawn: the whole machine's residues are spread in one cloud, each weighted
by its volume, and its level is the one at which the whole holds its own volume. Each part is the
share of that solid where its own cloud is greater than each other part's, and each tone the
share of its part where its kind's cloud is the greater. On the grid's tetrahedra each face lies
on one of these fields' zeros, clipped by the others; a vertex where several meet is worked out
once from the corners and the fields that make it, so neighbouring surfaces share it exactly.

With `DATA` the folder of E. coli's downloads (each entry with its MANIFEST; the Protein Data
Bank's files are CC0), from the visualizer's folder:

```
python3 -I tools/shape_particle.py DATA/wwpdb-ribosome/7K00.cif.gz --ribosome --out data/catalogue/shapes/ecoli.ribosome.json
python3 -I tools/shape_particle.py DATA/wwpdb-atp-synthase/6OQR.cif.gz --part head=2,6 --part central-stalk=5,4 --part peripheral-stalk=3,1 --part ring=7 --part stator-foot=8 --frame-from ring --frame-to head --out data/catalogue/shapes/ecoli.atp-synthase.json
python3 -I tools/shape_particle.py DATA/wwpdb-rna-polymerase/6P1K.cif.gz --part beta=2 --part beta-prime=3 --part alpha=1 --part omega=4 --part sigma=5 --out data/catalogue/shapes/ecoli.rna-polymerase.json
python3 -I tools/shape_particle.py DATA/wwpdb-translocon/9RBF.cif.gz --exclude LEFT_OUT --part secy=7 --part sece=8 --part secg=9 --out data/catalogue/shapes/ecoli.translocon.json
python3 -I tools/shape_particle.py DATA/wwpdb-hslv/1G4A-assembly1.cif.gz --part hslv=2 --part hslu=1 --frame-from hslv --frame-to hslu --out data/catalogue/shapes/ecoli.hslv.json
python3 -I tools/shape_particle.py DATA/wwpdb-lon/6U5Z.cif.gz --out data/catalogue/shapes/ecoli.lon.json
```

`LEFT_OUT` is the translocon measure's own `left_out` entities, comma-separated: the ribosome
and YidC that 9RBF holds beside SecYEG. The same call made twice gives the same bytes, and
`tests/machine_shapes.test.mjs` makes the six again and compares them byte for byte, where the
downloads are on the machine.

## Drawing a shape

`src/lenses/machine_shape.js` draws a shape file; a view calls it and owns nothing of the format.
- **`shapePath(species, kind, size)`** gives the path a machine's shape is published at.
  - It takes the catalogue entry's species, kind and size.
  - It uses the measure's file name where `size.from` names one, else `<species>.<kind>`.
- **`loadShape(path)`** reads the file through `loadBeside`. It resolves to
  `{ status, data, words }`:
  - `"found"`, with the data;
  - `"none"`, where no file is published for the machine;
  - `"failed"`, where one cannot be read or drawn.
  The `words` say so plainly; a machine whose status is not `"found"` keeps its ellipsoid levels
  only. A view learns that a machine has no shape only by asking: either a page for the disk carries
  its shapes inside it and not this one, or the host answers the fetch with a client error (404,
  or any 4xx).
- **`buildShape(data, { kind, perNm, colour, tones })`** builds the whole machine as **one mesh**
  (one draw), every surface in one buffer. The normals are worked out once, and each vertex has
  a colour. The call returns:
  - **`mesh`**: a `THREE.Mesh` with one material of this module's (vertex colours); a caller may
    pass its own `material`, which stays the caller's;
  - **`surfaces`**, the table of face ranges, one row a surface (in the mesh's order):
    - `first` and `last` (triangle numbers, `last` included), `firstVertex` and `vertexCount`;
    - `id`, and `part` and `chain` as page ids (`machine:<kind>:<part>`,
      `machine:<kind>:chain-<id>`, or null);
    - `partId`, `kind`, `entity`, `description`, `residues`, `within` (a tone's solid), and
      `shade`;
  - **`surfaceAt(faceIndex)`**: the row a raycast's `faceIndex` falls in, or null;
  - **`recolour(which, colour)`**: rewrites the colour of one surface's vertices (a row, its
    number or its id) to `colour`, or to the caller's function again when no colour is given; with
    no surface named, every surface. Nothing is rebuilt;
  - **`cost`**: `{ draws: 1, triangles, vertices }`;
  - **`dispose()`**: frees the geometry and this module's material, and takes the mesh from its
    parent.
- **The options of `buildShape`:**
  - `kind` is the catalogue's kind (`atp-synthase`), which makes the page ids.
  - `perNm` is the caller's units in a nanometre.
  - `colour(partId, kind, row)` returns a colour for a surface: a `THREE.Color` or anything
    `THREE.Color` takes. `shapeColours(palette, { hues })` is a default from the page's palette.
  - `tones: true` draws each part that has two tones as its tones instead of its solid.

The mesh is in the measure's frame. The Machines view draws a measured machine's ellipsoids at
`centre_nm / UNIT_NM` inside a group it stands on the tray; a shape built with
`perNm: 1 / UNIT_NM` and added to that same group sits exactly where they sit:

```js
import { shapePath, loadShape, buildShape, shapeColours } from "./machine_shape.js";

const found = await loadShape(shapePath(entry.species, entry.id, entry.size));
if (found.status !== "found") return found.words; // its ellipsoid levels only, and the panel says why
const shape = buildShape(found.data, { kind: entry.id, perNm: 1 / UNIT_NM, colour: shapeColours(stage.palette, { hues }) });
group.add(shape.mesh); // the group that holds the machine's ellipsoids, at standOffset(entry.shape)
// Choosing: the face a ray met gives the surface, and its part or chain.
const row = shape.surfaceAt(hit.faceIndex); // row.chain || row.part
shape.recolour(row, chosenColour); // lit; shape.recolour(row) puts it back
// Later: shape.dispose();
```

At this level a chosen ATP synthase costs 1 draw and 9,348 triangles; a ribosome 1 draw and
4,836 triangles (7,900 in two tones).
