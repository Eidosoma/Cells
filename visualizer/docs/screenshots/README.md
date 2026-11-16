# Screenshots of the viewer

Pictures of the Cells visualizer for the project's README and other documents. Each is
1600 by 1000 pixels, WebP, taken in headless Chrome from the `visualizer` branch on
16 November 2026, with the page's own fonts loaded. They show the page as a visitor sees
it, with nothing added. The first four were taken at `dc566524`; the human's cell at
`fe6f1fb5` and E. coli's at `e7cbe990`.

| File | What it shows | Where its numbers come from |
| --- | --- | --- |
| `replay-e07v1-voltage-as-height.webp` | A replay of the judged experiment E07-v1 at 19 min 30 s, after 146 of its 291 cell replacements: a sheet of 127 cells in which each cell stands as high as its membrane voltage, wedges mark the voltage drops across junctions, and the outline is the disc written at the start. The record's verdict stands beside it: judged, the disc did not renew | The run's own saved records (run `a-donor-fast-k1-d37-s1.0`, seed 5, of the judged execution of 13 November 2026). The junction drops are worked out by the viewer from the saved voltages, and the page says so |
| `replay-development-run-flows.webp` | The engine's first run made for the viewer, at 0.4 s: one cell that makes a species and releases it into a small space outside, which leaks to a held bath. The tiles are coloured by the amount of the species, beads show what crosses each border (one bead is 50,000 molecules), and a glow shows where energy is dissipated | A development run with no verdict, written by the engine's shared output path on 15 November 2026. The rates are means between two saved records, worked out by the viewer from the run's saved totals |
| `cell-view-flux-illustration.webp` | The Cell view with flux switched on, for the generic cell under the planarian's names. The beads are an illustration, and the picture says so: "Illustration: not a run", directions only | No run stands behind the beads. Pumps go the way the engine's own law declarations say; channels, junctions and water are drawn both ways with none claimed |
| `protein-atlas-human-shelves.webp` | The human's own proteins in the Protein atlas: 20,414 proteins on six stacked shelves, a shelf for each membrane, with families that open | The reviewed entries of UniProt's human reference proteome, release 2026_04 (CC BY 4.0); a protein's place is what its entry states |
| `cell-view-human-structures.webp` | The Cell view under the human's names: the generic cell that Cells models, cut open and drawn as one of a layer. The nucleus is opened like a globe, to show its double envelope, its pores, its chromatin and its nucleolus; round it lie the endoplasmic reticulum, the Golgi apparatus, ribosomes and mitochondria. Each name carries the dot of its status: the nucleus, the Golgi apparatus and the ribosomes are planned parts, illustration only, with nothing of them in the engine yet. No human cell type is modelled; the heart and the body are placeholder outlines | The engine map, whose statuses come from the project's record, and the species' file. The shapes, sizes and counts of the structures are the picture's choice, and each panel says so |
| `cell-view-ecoli.webp` | The Cell view of *E. coli*: a rod-shaped bacterium about 1 by 2 µm, cut open, with its two membranes and the wall between them, 3 of its 1 to 5 flagella, 120 of its 200 to 500 fimbriae, its ribosomes and its free chromosome. *E. coli* is proposed, not modelled: nothing of it is in the engine, and the picture shows where the capabilities of Cells would have a place in it. The page says so on the picture and in the top bar | The species' own file: sizes and counts read from open papers and from UniProt, each with its source (`docs/ECOLI.md`). Flagella, fimbriae, the wall and the chromosome are scenery; where the picture chose a number, the part's panel says so |

To take them again: the picture aids of `tools/check_layers.mjs` (`picture`),
`tools/check_cellflux.mjs`, `tools/check_look.mjs` and `tools/check_shelves.mjs`
(`pictures`) write a frame once the page has settled. Wait for the page's own fonts
before the frame is taken: a font whose load has failed is not tried again by the
browser, so give the page a fresh copy of its font stylesheet link and load the faces
again until both families are in. The tools write PNG or JPEG; these were written as
WebP by asking the browser for that format.
