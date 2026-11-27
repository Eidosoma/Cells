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

- One file a measure, never one a chain: `data/catalogue/shapes/<name>.json`, committed, with the
  same name as the measure it is drawn in. That is a file in `data/catalogue/measures/` (for
  example `human.complex-i.json`, or `animals.ribosome.json`, which every animal species' ribosome
  draws); E. coli's ribosome's one record is the species files', `data/measures/ecoli.ribosome.json`.
  Each file is at most 250,000 bytes (the budget below), far under the 1 MB the user set for
  checked-in data.
- A shape file for every machine and unit the catalogue measures (22 since 19 November 2026, with the vault's; 21 since 18 November 2026; the
  list is under "How each file is made"). A unit of the law inventory (the sodium pump, SERCA)
  draws its measure's shape as a machine does.
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
`--frame-to` as its measure. Since 18 November 2026 every file is made with `--measure`, which
reads those options from the measure's own record, so a shape cannot be made in another frame.

## What a consumer may rely on

- Every mesh and every tone is closed: each edge is met by triangles turned both ways, as often
  one way as the other. Every triangle faces out. A few triangles may have no area (three
  vertices in a line); they keep the surface closed.
- A chain's surface holds its residues' own volume to within 2%, with what was dropped of it. A
  machine's parts hold the whole's residues' own volume between them to within 2%: each part is
  the share of the whole's solid where its cloud is the greater, so a part holds about, not
  exactly, its own residues' volume (E. coli's ribosome's small subunit 93%, its large one 105%).
- A surface's middle lies inside its measured ellipsoid. A thin chain's volume gathers where its
  residues pack, so its middle may stand well off the ellipsoid's centre: up to about a fifth of
  the chain's length for the ATP synthases' subunit b (5.2 nm of 28 nm in the human one).
- Neighbouring parts meet at one shared face: the vertices of the faces each has inside are the
  same places. A part's two tones fill it, each inside it or on it.
- **Pieces.** A chain may be thin between its domains, so that its surface falls into pieces. The
  largest piece is kept, and every piece that holds at least 5% of the surface's volume; smaller
  slivers are dropped and listed under `dropped`.
  - In E. coli's files that left out a sliver of RNA polymerase's β (about 1 residue's volume)
    and of σ70 (0.1), and two of SecE's (about 1 residue's volume together). σ70's piece of 7%
    (about 36 residues' volume, below the claw) is kept.
  - In the others:
    - the most dropped from one surface is 2.69 nm³ (the vault's half-vault b: 3 pieces, 19
      residues inside; the earlier 0.63 nm³ was the human mitochondrial ribosome's large subunit,
      2 residues inside);
    - the most from one file is 3.65 nm³ (the vault's two halves, 7 pieces; the IP3 receptor's four
      chains, a sliver each, drop 1.06 nm³);
    - the most residues inside a file's drops is 23, in the vault's two halves (the most in one
      chain's is 7, subunit b of the human ATP synthase, chain K, 0.49 nm³).
    - The vault (`human.vault`, since 19 November 2026) is the one file made of two solids that
      are half-vaults (each 39 chains, told apart by the side of the plane across the long axis on
      which a chain's centre lies) at 2.7 nm, the finest width in steps of 0.1 nm under the
      ceiling (9,268 triangles, 197,604 bytes; 2.6 nm gives 12,148). Its 78 chains at 3.7 nm
      (11,452 triangles, five slivers dropped, the largest 4.63 nm³) were also made and looked at:
      thin ends (its caps) fall below the surface's level at that width, and the chains read as a
      drum of spiky columns; the two halves read as a barrel in two colours meeting at its waist,
      and were kept. Its caps are open at either width.
  - A part's tones may be in pieces (a ribosome's proteins on its RNA).
  - Where a part's sliver is dropped against its neighbour, the neighbour keeps the few faces it
    had against it: a dent of a tenth of a nanometre (5 vertices, in the mitochondrial ribosome).
- **The budget**, held by `tests/machine_shapes.test.mjs`, has been this since 18 November 2026:
  - a file at most 250,000 bytes;
  - one chosen machine at most 12,000 triangles, drawn either way (its meshes, or its meshes with
    each part's tones in its solid's place). The tool refuses past either (`--most-triangles`,
    `--most-bytes`).
  - A chain's surface is a few dozen to a few hundred triangles, up to about 3,000 for the largest
    chains (the IP3 receptor's, 2,181 residues each, 2,764 triangles at most).
  - The bench may draw 40 draws and 40,000 triangles in all; a chosen machine at this level is
    one draw.
- Chains' surfaces may overlap one another where chains pack closely: each is drawn whole.

## How meshes map to the catalogue's ids

- A chain's surface `chain-<id>` is the body the catalogue names `machine:<kind>:chain-<id>`; its
  `part` names `machine:<kind>:<part>`. At the Shape level a part is chosen through any of its
  chains' surfaces, and a part's hue is its chains' hue, as at the Subunits level.
- A part's solid `part-<part>`, and each of its tones, is the body `machine:<kind>:<part>`; drawn
  in its two tones, the nucleic acid may wear its own colour.
- A unit of the law inventory has no kind. Its page id is its own (`unit.U39`), and its surfaces
  are `unit.U39:<part>` and `unit.U39:chain-<id>`.
- A ribosome is drawn by its parts (`large` and `small`): its fifty to ninety chains are too many
  to tell apart at this resolution. The other machines are drawn by their chains.
- Where the catalogue names no chains for a machine (the translocon), its chains' surfaces map by
  their `part` alone.
- Where the catalogue names no parts (complex I, the three human RNA polymerases), a surface's
  `part` is the measure's own name for its subunit (`NDUFS2`, `POLR2A`), and a view chooses it by
  its chain.
- **The rule for a ribosome** (two subunits, each one solid of all its residues, with two tones):
  - It is drawn the same way whether the measure is the two-subunit mode's (E. coli's 7K00, the
    animals' 8YOP) or the machine mode's with parts `large` and `small` (the human mitochondrial
    ribosome, 9S7C, made with `--by parts`).
  - The tones come from each residue's kind, not from the measure's parts, so the mitochondrial
    ribosome has its RNA and protein tones although its parts do not split them. Its proteins are
    the greater part of it, so in two tones it is mostly protein, its rRNA showing at the
    interface.
  - The frame differs: the mitochondrial ribosome's is the machine mode's, from the whole's centre
    to the subunits' line.
- **Where the rule does not reach,** what the measure leaves out of both subunits is drawn by no
  surface and listed nowhere in the shape file; the measure lists it under its `left_out`:
  - 7K00's tRNAs and messenger;
  - 9S7C's mitochondrial tRNA-Val, which sits in the large subunit's central protuberance, left
    out by its measure with the example messenger, tRNAs and nascent chain.
  If a measure is made again with such an entity placed (`--large`, `--small`, or a part that
  names it), `--measure` makes the shape follow it.
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

The definition is the same for every machine, and so is the setting: a chain's surface at 1 nm,
a part's solid at 1.6 nm (five large machines are coarser, below). These widths were weighed on 17 November 2026 against 0.8 and 1.4 nm for a chain and 1.2
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

**A coarser width where the setting breaks the budget.** On 18 November 2026 five machines were
too large for the budget at the setting. Each is made at the finest width that holds it, in steps
of 0.1 nm, with the grid as wide. The setting stays the default.
- The file says so: `parameters.width_nm` gives the width, `parameters.setting_width_nm` the
  setting's, and its `definition` adds "coarser than the setting's … nm, to hold the budget".
- Each next step finer broke the budget:

  | File | At the setting | Made at |
  | --- | --- | --- |
  | the human proteasome (46 chains) | 25,044 triangles | 1.5 nm; at 1.4, 12,428 |
  | complex I (45 chains) | 18,460 | 1.3 nm; at 1.2, 12,628 |
  | the IP3 receptor (four chains of 2,181 residues) | 13,092 | 1.1 nm |
  | the 80S ribosome | its tones 13,740, 397 KB | 2.0 nm; at 1.9, 254,650 bytes |
  | the mitochondrial ribosome | 331 KB | 1.8 nm; at 1.7, 287,326 bytes |

The small Physarum proteins use widths of 0.32 to 0.48 nm. Their files report the finer width and keep the same triangle and file-size ceilings. The assembly IDs and widths are recorded in the Physarum bench and the shape regeneration table in `tests/machine_shapes.test.mjs`.

**Each call** reads the measure's parts, frame and left-out entities from its record
(`--measure`). E. coli's six give the same bytes as the explicit calls they were first made with.
With `DATASETS` the folder of the downloads (each entry with its MANIFEST; the Protein Data Bank's
files are CC0), from the visualizer's folder, each file is:

```
python3 -I tools/shape_particle.py DATASETS/ENTRY --measure MEASURE [OPTIONS] --out data/catalogue/shapes/NAME
```

| `NAME` | `ENTRY` | `MEASURE` | `OPTIONS` | Triangles | Bytes |
| --- | --- | --- | --- | --- | --- |
| `ecoli.ribosome.json` | `ecoli/wwpdb-ribosome/7K00.cif.gz` | `data/measures/ecoli.ribosome.json` | | 4,836 / 7,900 in tones | 241,452 |
| `ecoli.atp-synthase.json` | `ecoli/wwpdb-atp-synthase/6OQR.cif.gz` | `data/catalogue/measures/ecoli.atp-synthase.json` | | 9,348 | 162,924 |
| `ecoli.rna-polymerase.json` | `ecoli/wwpdb-rna-polymerase/6P1K.cif.gz` | `data/catalogue/measures/ecoli.rna-polymerase.json` | | 6,112 | 111,280 |
| `ecoli.translocon.json` | `ecoli/wwpdb-translocon/9RBF.cif.gz` | `data/catalogue/measures/ecoli.translocon.json` | | 1,284 | 27,119 |
| `ecoli.hslv.json` | `ecoli/wwpdb-hslv/1G4A-assembly1.cif.gz` | `data/catalogue/measures/ecoli.hslv.json` | | 8,136 | 143,130 |
| `ecoli.lon.json` | `ecoli/wwpdb-lon/6U5Z.cif.gz` | `data/catalogue/measures/ecoli.lon.json` | | 5,512 | 99,640 |
| `human.proteasome.json` | `human/wwpdb-proteasome-g/7QYB.cif.gz` | `data/catalogue/measures/human.proteasome.json` | `--width 1.5` | 10,896 | 184,515 |
| `human.atp-synthase.json` | `human/wwpdb-atp-synthase-g/8H9T.cif.gz` | `data/catalogue/measures/human.atp-synthase.json` | | 11,280 | 197,004 |
| `human.rna-polymerase.json` | `human/wwpdb-rna-polymerase-g/6DRD.cif.gz` | `data/catalogue/measures/human.rna-polymerase.json` | | 6,392 | 112,840 |
| `human.rna-polymerase-i.json` | `human/wwpdb-rna-polymerase-i-g/7OBA.cif.gz` | `data/catalogue/measures/human.rna-polymerase-i.json` | | 7,924 | 142,201 |
| `human.rna-polymerase-iii.json` | `human/wwpdb-rna-polymerase-iii-g/7D59.cif.gz` | `data/catalogue/measures/human.rna-polymerase-iii.json` | | 9,592 | 170,765 |
| `human.complex-i.json` | `human/wwpdb-complex-i-g/9I4I.cif.gz` | `data/catalogue/measures/human.complex-i.json` | `--width 1.3` | 10,924 | 187,030 |
| `human.mitochondrial-ribosome.json` | `human/wwpdb-mitochondrial-ribosome-g/9S7C.cif.gz` | `data/catalogue/measures/human.mitochondrial-ribosome.json` | `--width 1.8 --by parts` | 4,672 / 8,256 in tones | 245,604 |
| `human.cmg-helicase.json` | `human/wwpdb-cmg-helicase-g/6XTX.cif.gz` | `data/catalogue/measures/human.cmg-helicase.json` | | 8,724 | 157,078 |
| `animals.ribosome.json` | `human/wwpdb-ribosome-80s-b/8YOP.cif.gz` | `data/catalogue/measures/animals.ribosome.json` | `--width 2.0` | 3,944 / 7,820 in tones | 220,669 |
| `animals.sodium-pump.json` | `human/wwpdb-sodium-pump/7E1Z.cif.gz` | `data/catalogue/measures/animals.sodium-pump.json` | | 2,192 | 39,905 |
| `animals.serca.json` | `human/wwpdb-serca/6LLE.cif.gz` | `data/catalogue/measures/animals.serca.json` | | 1,548 | 29,069 |
| `animals.ip3r.json` | `human/wwpdb-ip3r/6DQJ.cif.gz` | `data/catalogue/measures/animals.ip3r.json` | `--width 1.1` | 10,688 | 207,132 |
| `animals.kv1-2.json` | `human/wwpdb-kv-channel/3LUT-assembly1.cif.gz` | `data/catalogue/measures/animals.kv1-2.json` | | 5,704 | 102,250 |
| `animals.connexin-channel.json` | `human/wwpdb-gap-junction-cx43/7Z22.cif.gz` | `data/catalogue/measures/animals.connexin-channel.json` | | 5,352 | 94,064 |
| `animals.innexin-channel.json` | `planarian/wwpdb-innexin-channel/5H1R.cif.gz` | `data/catalogue/measures/animals.innexin-channel.json` | | 11,680 | 209,460 |

The same call made twice gives the same bytes. `tests/machine_shapes.test.mjs` makes every file
again, two at a time, and compares them byte for byte, wherever the downloads are on the
machine. The largest call, the 80S ribosome, takes about 13 s and 650 MB.

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
- **`buildShape(data, { kind, id, perNm, colour, tones })`** builds the whole machine as **one mesh**
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
  - `id`, given instead of `kind`, is a unit's own page id (`unit.U39`), which then makes them.
    It was added on 18 November 2026; nothing else of the interface changed.
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

For a unit, `shapePath(null, null, size)` and `buildShape(data, { id: unit.id, ... })`.

At this level a chosen machine costs 1 draw and the triangles in the table above.
- The most are the innexin channel's 11,680 and the human ATP synthase's 11,280.
- A ribosome is 3,944 to 4,836 triangles as its solids, and 7,820 to 8,256 in two tones.
- `tests/machine_shape_drawing.test.mjs` notes each machine's cost.
