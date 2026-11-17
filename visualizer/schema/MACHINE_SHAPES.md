# A machine's shape: `cells.visualizer.machine-shape@1`

A machine measured from a Protein Data Bank entry is drawn as ellipsoids at three levels
(Outline, Parts, Subunits), from the viewer's own measure (`tools/measure_particle.py`, kept in
`data/catalogue/measures/`). On 17 November 2026 the user agreed to a fourth, finer level,
**Shape**: a smooth, low-resolution surface for each chain, worked out by the viewer from the
same coordinates. This contract says what a shape file holds, where it lives and is published,
how its surfaces map to the parts and chains the catalogue already names, and what the page
must say of it. A shape is an illustration: no atom and no ribbon is drawn, and nothing of an
entry is copied into the tree but numbers the viewer worked out itself.

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
 "definition": "each chain as the closed surface that holds its own volume (0.135 nm³ for each amino acid, 0.32 nm³ for each nucleotide) in a cloud where each residue is spread as a Gaussian 1 nm wide, on a grid 1 nm apart",
 "illustration": "The viewer's own surface of the entry's coordinates, an illustration: ...",
 "parameters": {"width_nm": 1.0, "grid_nm": 1.0, "reach_widths": 3.0, "volume_nm3": {"protein": 0.135, "nucleic": 0.32}, "stands_for": {"protein": ["CA"], "nucleic": ["P", "C4'"]}, "by": "chains"},
 "entry": "6OQR", "title": "...", "method": "ELECTRON MICROSCOPY", "resolution_A": "3.1",
 "left_out": [],
 "frame": "the measuring tool's frame: origin at the centre of the whole's atoms; y from the part ring's centre to the part head's; ...",
 "unit_nm": 0.01,
 "counts": {"meshes": 22, "vertices": 4718, "triangles": 9348},
 "meshes": [
  {"id": "chain-W", "chain": "W", "entity": "1", "description": "ATP synthase subunit delta", "part": "peripheral-stalk", "kind": "protein", "residues": 173, "vertices": [-297, 897, -143, ...], "triangles": [...]}
 ]
}
```

- `assembly` stands after `entry` where the file is a biological assembly's (`1G4A`, assembly
  `1`); `left_out` lists the entities left out of the whole with `--exclude`.
- **`meshes`**, each one closed surface:
  - `id`: `chain-<author chain id>` (as the catalogue names a chain, `chain-E-2` in an
    assembly), or `part-<part>-<kind>` for a surface of a part's protein or nucleic acid.
  - `chain`, `entity`, `description`: for a chain's surface. `part`: the catalogue's id of the
    part that holds it (`head`, `large`), or null where the measure names no part.
  - `kind`: `protein` or `nucleic`, so that a ribosome's RNA and its proteins can wear two tones.
  - `residues`: how many residues it is drawn from.
  - `vertices`: flat `[x, y, z, x, y, z, ...]`, integers; each times `unit_nm` is nanometres in
    the frame. `triangles`: flat indices into the vertices, three a triangle, counter-clockwise
    seen from outside. No normals are stored: the page works them out.
- `counts`: the meshes, vertices and triangles of the whole file.

## The frame and the units

A shape is in exactly the frame and the units of the machine's measure: the same origin and axes,
in nanometres, so that a surface sits where its ellipsoid sits. A view places a mesh as it places
that measure's bodies (their `centre_nm` and `axes` are in the same frame), and moves and scales
the whole machine as it moves and scales its ellipsoids. The file's `frame` says the frame in
words: the measuring tool's, from the same entry, `--exclude`, `--part`, `--frame-from` and
`--frame-to` as its measure.

## What a consumer may rely on

- Every mesh is closed: each edge is met by triangles turned both ways, as often one way as the
  other. Every triangle faces out. A surface holds its residues' own volume to within 2%.
- A surface may be in more than one piece where a chain is thin between its domains (σ70's
  linkers, SecG where only half its sequence is modelled) or, for a part's surface, where its
  chains do not touch (a ribosome's proteins).
- **The budget**, held by `tests/machine_shapes.test.mjs`: a file under 400 KB and 20,000
  triangles; a ribosome's under 8,000. A chain's surface is a few dozen to a few hundred
  triangles, up to about 2,000 for the largest chains (RNA polymerase's β′, 1,340 residues). A
  phone draws one chosen machine at this level without trouble.
- Surfaces may overlap one another where chains pack closely: each is drawn whole.

## How meshes map to the catalogue's ids

- A chain's surface `chain-<id>` is the body the catalogue names `machine:<kind>:chain-<id>`; its
  `part` names `machine:<kind>:<part>`. At the Shape level a part is chosen through any of its
  chains' surfaces, and a part's hue is its chains' hue, as at the Subunits level.
- A part's surfaces (`part-<part>-protein`, `part-<part>-nucleic`) are the body
  `machine:<kind>:<part>`; a view may give the nucleic acid its own tone.
- A ribosome is drawn by its parts (`--ribosome`: `large` and `small`): its fifty chains are too
  many to tell apart at this resolution. The other machines are drawn by their chains. Where the
  catalogue names no chains for a machine (the translocon), its chains' surfaces map by their
  `part` alone.
- What is in neither subunit of a ribosome (7K00's tRNAs and messenger) is drawn by no surface
  and listed nowhere in the shape file; the measure lists it under its `left_out`. `--large` and
  `--small` place an entity the caller names in a subunit, as the measuring tool's two-subunit
  mode does (a human ribosome's RACK1, whose name says neither).
- A machine whose catalogue entry draws another species' measure (Syn3A's and M. pneumoniae's
  ribosomes are drawn at E. coli's, as their files say) has no shape file of its own; whether its
  Shape level shows E. coli's shape is the view's choice, and the panel says whose shape it is.

## What the panel says of a shape

At the Shape level the machine's panel says, in plain words, that the shape is the viewer's own
surface of the entry's coordinates (naming the entry, and the assembly where there is one), by the
file's `definition`, worked out by `tools/shape_particle.py`; that it is an illustration and not
the structure; and that the Protein Data Bank states no surface. The entry stands among the
machine's sources with its terms (CC0). Nothing says modelled or qualified of a machine.

## How each file is made

The definition is the same for every machine: a chain's surface at 1 nm, a part's surface at
1.6 nm. These widths were weighed on 17 November 2026 against 0.8 and 1.4 nm for a chain and 1.2
and 2.0 nm for a part, on the ATP synthase and the ribosome: they hold the budget without a pass
that simplifies the surfaces. With `DATA` the folder of E. coli's downloads (each entry with its
MANIFEST; the Protein Data Bank's files are CC0), from the visualizer's folder:

```
python3 -I tools/shape_particle.py DATA/wwpdb-ribosome/7K00.cif.gz --ribosome --out data/catalogue/shapes/ecoli.ribosome.json
python3 -I tools/shape_particle.py DATA/wwpdb-atp-synthase/6OQR.cif.gz --part head=2,6 --part central-stalk=5,4 --part peripheral-stalk=3,1 --part ring=7 --part stator-foot=8 --frame-from ring --frame-to head --out data/catalogue/shapes/ecoli.atp-synthase.json
python3 -I tools/shape_particle.py DATA/wwpdb-rna-polymerase/6P1K.cif.gz --part beta=2 --part beta-prime=3 --part alpha=1 --part omega=4 --part sigma=5 --out data/catalogue/shapes/ecoli.rna-polymerase.json
python3 -I tools/shape_particle.py DATA/wwpdb-translocon/9RBF.cif.gz --exclude LEFT_OUT --part secy=7 --part sece=8 --part secg=9 --out data/catalogue/shapes/ecoli.translocon.json
python3 -I tools/shape_particle.py DATA/wwpdb-hslv/1G4A-assembly1.cif.gz --part hslv=2 --part hslu=1 --frame-from hslv --frame-to hslu --out data/catalogue/shapes/ecoli.hslv.json
python3 -I tools/shape_particle.py DATA/wwpdb-lon/6U5Z.cif.gz --out data/catalogue/shapes/ecoli.lon.json
```

`LEFT_OUT` is the translocon measure's own `left_out` entities, comma-separated: the ribosome
and YidC that 9RBF holds beside SecYEG. The same call made twice gives the same bytes.
