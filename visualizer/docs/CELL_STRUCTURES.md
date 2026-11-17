# The cell's structures in the Cell view

The nucleus, the Golgi apparatus and the ribosomes are parts of the Cell view of their own
since 16 November 2026. This note says why, and what each part's status rests on. The map's
entries for them (`cap.nucleus`, `cap.golgi`, `cap.ribosomes` in
`data/architecture/overlay.json`) cite it as their source.

## The user's decision

The user was shown that nothing in the engine is a nucleus, a Golgi or a ribosome today, and
said on 16 November 2026:

> "So we will have nucleus, Golgi, ribosomes modeled to some extend, not protein folding
> level (yet) so we should assume those are going to be in there soon, so make them 1st
> class items but still you can sort and view what is done and what is not yet done, we have
> selectors for that, but in the default mode show it all in the coolest possible way"

The same day the user agreed that the label "Regulatory circuits" moves off the nucleus onto
the genome, worded as a separate small model, and that choosing a structure opens the
proteins known to be in it in the Protein atlas ("yes").

## What follows on the page

- **Each is a part like any other.** It can be chosen, has a name with its status dot, a
  panel, a line in the list, and a place in the legend's counts.
- **Drawn whole in the default colouring.** With "Colour: Biology" every part of the cell is
  drawn whole, whatever its status. The dot beside each name, the legend's counts and its
  filter, and "Colour: Status" show what is built and what is not; with "Colour: Status" a
  part that is not built is a grey sketch, as before.
- **A door into the Protein atlas** where the species' own proteins can show the set: the
  shelf of the nuclear envelope, the endoplasmic reticulum or the mitochondrial inner
  membrane, for a species with those shelves; the ribosome's proteins, for a species whose
  file marks them. Where a species' data cannot show the set, there is no door.

## What each status rests on

| Part | Status | Rests on |
| --- | --- | --- |
| Nucleus | Planned | The user's decision above. Nothing of the nucleus is in the engine: no compartment, no envelope, no transport through its pores |
| Golgi apparatus | Planned | The user's decision above. The roadmap's item 9 (`docs/ROADMAP.md`) plans membrane trafficking through the endoplasmic reticulum, the Golgi and vesicles, and leaves the Golgi's own structure out of its scope; it is not started |
| Ribosomes | Planned | The user's decision above. Nothing of protein synthesis is in the engine |
| Regulatory circuits | Established, as before | The repository's README, "What Cells can do": isolated regulatory circuits and a bounded two-cell regulatory and ionic model. It is a separate small model that runs on its own and does not model the nucleus; it is drawn at the cell's DNA, the chromatin inside the nucleus or the free chromosome of a cell without one |
| Membrane trafficking | Planned, as before | The roadmap's item 9. It is drawn as the vesicles between the endoplasmic reticulum, the Golgi and the membrane, now that the Golgi is a part of its own |

"Planned" is the map's word for what is named in the plan or the roadmap, or decided by the
user, and not started. None of these three parts is called established, simulated or
qualified anywhere on the page; their representation is "Illustration only".

## Where a cell has them

What a cell holds comes from its species' file (`schema/SPECIES.md`, `cell.parts`), and the
viewer reads nothing else for it:

- a cell with `nucleus: true` has a nucleus; one without has none, and its chromosome lies
  free in the cytoplasm (`chromosome_kbp`);
- a cell has a Golgi where `organelles` lists `golgi`, or, where `organelles` is not given,
  where it has a nucleus;
- every cell has ribosomes. Where the file gives `ribosomes` (a count), that count is drawn,
  or a stated part of it; where it gives none, the number drawn is the picture's choice, and
  the panel says so. Where it gives `ribosome` (a measured shape: the three bacteria, since 17
  November 2026), each is drawn as its two subunits, each the ellipsoid of the same spread as
  its atoms, from the viewer's own measure of a PDB entry (`tools/measure_particle.py`). In
  the schematic picture they are enlarged as the membrane's proteins are, and fewer are drawn
  (`cell_layout.js`, `RIBOSOME_RULES`). A large cell's ribosomes are as they were.

A part a cell does not hold is listed under the species' "Not in this organism", with the
reason read from `cell.parts`.

## What the picture chooses

Sizes and counts come from the species' file where it gives them. The rest is the picture's
choice and the panel says so: in a generic animal cell the nucleus is drawn 6 µm across in a
cell about 18 µm across, the Golgi as a stack of five or six cisternae, and in the schematic
picture the ribosomes are enlarged, as every small part is.

## Where the Golgi stands

The user chose this on 17 November 2026 from a review of where the Golgi, the ER and the nucleus
stand ("B as you recommend"). Before, the Golgi stood about 6 µm from the nucleus, beyond the
ER. Now it stands as a cell's does. Its distances and counts are still the picture's choice, and
no number from a paper stands behind them:

- **An animal cell** (a cell with a nucleus and no large vacuole). The Golgi stands beside the
  nucleus, toward the cell's middle, round the centrosome. Enlarged, it is one stack whose cis
  face is about 1 µm from the envelope. To scale, it is a ribbon of four stacks, each about
  1.2 µm across, about 0.4 µm from the envelope. The rough ER lies in two arms, one each side of
  the Golgi, and each runs on from the envelope.
- **The centrosome is scenery.** Cells models none, so it is drawn in the neutral glass of scenery
  with no status, and its panel says so. It is two short barrels at right angles, between the
  nucleus and the Golgi.
- **A plant cell** (a cell with a large vacuole). Its Golgi is many small stacks spread through
  the thin cytoplasm by the membrane, with no ribbon and no centrosome: 14 where parts are
  enlarged, and 40 to scale, each about 1.2 µm across. The first stands beside the nucleus, where
  the carriers from the ER reach it. The ER is as before, on the nucleus's inner side.
- **However many stacks there are, they are one shared geometry**: each level of cisterna is one
  mesh, and the rims and the buds are one instanced mesh each. A frame draws as many of them as
  for one stack. `tests/cell_structures.test.mjs` holds a ceiling on what the cell's parts draw.
- **The carriers of membrane trafficking** leave from the point of the ER nearest the Golgi's cis
  face, and go from its trans face to the membrane.
