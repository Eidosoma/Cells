# Cells visualizer

A 3D viewer for Cells: the architecture, the proteins it models, and replays of its
experiments.

It is tooling, asked for by the user on 14 November 2026. It reads a checkout and saved
run outputs, and it is never imported by the engine (D006, D154). It settles the open
viewer-technology item O006: three.js with web components, no framework.

**Audience:** the team, investors, other scientists and the public. Every part therefore
has a plain-language line first and the technical detail after it.

## What it shows

One data file, the scene, drawn through four lenses, in this order:

| Lens | What you see |
| --- | --- |
| **Cell and scales** | What Cells can simulate, drawn where it happens: one cell opened by a flat cut (after the README's biology map), the sheet of cells around it, and two placeholder outlines for the scales nothing simulates yet: a planarian's brain and the whole worm. The scales are nested, so zooming out leads from tissue into organ into organism: the sheet lies on the worm's head, above its brain. The sheet stands for skin-like tissue, a single layer of cells lying over the brain, and the cell is one cell of that layer, drawn with its neighbours (the user, 14 November 2026). The cell is flat-sided, as a cell packed in a layer is (the user, the same day: "make the cell shape be a bit more like planerian skin cell"); the shape is the picture's choice, since the engine gives a cell a volume and a membrane area and no shape, and it is not a model of a planarian's skin cell. It is placed on the worm for the scales only and is not the worm's tissue; the brain's own cells, neurons and glia, are not modelled. Zoom is continuous from molecules to organism, with a scale bar. **The Species switch sets the levels, the shapes and what the cell holds:** Human, Planarian, Syn3A and M. pneumoniae today. A single-celled species ends at its cell; the human's heart and body, like the planarian's brain and worm, are placeholder outlines |
| **Protein atlas** | The molecular machines Cells models, set in the membranes where their laws act: channels, pumps and transporters in the plasma membrane, junction channels between two cells, and the ER, mitochondrial and cage units inside. Each links to its engine part and out to the public atlases. A Species switch shows, for another species, the gene products that would make each machine: Human and Planarian today |
| **Experiments** | A saved run replayed: the sheet of cells coloured by membrane voltage, a timeline to play and scrub, each cell replacement marked as it happens, and the class the experiment's own summary recorded for the run. Shown only when replays have been made |
| **Engine** | The simulator as a stack of layers, from the machines it runs on up to the experiments. References stand outside the stack, because the engine never contains them. The plan's gates climb beside it |

Selecting a part that belongs to another lens takes you there: a protein unit's connection
opens the engine part that holds its law, and that part lists the units it holds laws for.

Three things are encoded, and kept apart:

- **Status**: qualified or judged, implemented and guarded, established, designed, planned,
  failed, external reference. The first two follow the plan's four levels (D156). Built parts are solid; parts not built are sketches. In the engine
  lens colour shows status too. In the cell lens colour shows the kind of part by default
  (purple nucleus, orange mitochondria), and the dot beside each name shows its status;
  the "Colour" switch turns the cell to status colours.
- **Representation** says how the engine treats a capability: simulated, modelled in
  aggregate, prescribed, or illustration only. Shapes that stand for modelled populations
  (channels, pumps, protein cages) are illustrations and are labelled so.
- **Size mode** (cell lens): "Schematic" enlarges parts and shows few, so each can be
  seen. "To scale" draws sizes and numbers nearer a real cell; see below.

Rules the map keeps, so it can be shown outside the team:

- It states no status the record does not state. The shared-state entities and the plan's
  gates carry the plan's own words, not an inferred status.
- Every status has a source and, where the record gives one, a date.
- Everything drawn is bound to a part of the scene or is neutral grey illustration.
- The cell picture carries the README's caveat: capabilities vary by model, and
  whole-cell integration is ongoing. The legend's "Runs together in" filter shows which
  parts run together in one model today.

## The protein atlas

The atlas shows Cells' own law inventory (stage 2 of `docs/PROTEIN_CATALOGUE_PLAN.md`): 49
functional units, the 80 engine laws that act on them, and their 93 candidate gene
products. It is not content from the Human Protein Atlas or any other public atlas. It
links out to UniProt, the RCSB PDB, the AlphaFold DB and the Human Protein Atlas.

It keeps the inventory's own vocabulary, apart from the engine's statuses:

| Mapping | Means | Drawn as |
| --- | --- | --- |
| **Assigned in source** | The law, its documents or its cited source names the protein | A solid blue assembly, from the stated subunit counts |
| **Candidate** | The law models a named native current; the gene mapping is the inventory's inference | The candidate's assembly, clear |
| **Generic** | The law is generic, phenomenological or manufactured | A plain grey stand-in with no subunits |

- **A generic law stays generic.** The sodium-potassium pump and the generic junction
  channel are grey stand-ins, and their products are listed as candidates only. A test
  checks that no generic unit is drawn with subunits.
- **"Assigned" records a label.** Each law also carries the kind of evidence behind it
  (expressed isoform, native current, neuron model, and so on). The legend's second block
  filters by it, and the panel states it per law.
- **Every shape is schematic.** It is drawn from counts the inventory states, such as four
  subunits or two rings of six, and the extractor warns if a drawn shape disagrees with the
  stated stoichiometry. Nothing is a measured structure, and nothing is to scale.
- **The inventory has its own date.** It was made on 12 November 2026 at engine `fec863f`.
  The extractor checks every law record against the checkout it reads, and applies one
  recorded rename (`emt_mirna_pair@1`). The view states both revisions.

The data is a slim snapshot of the inventory, made by `tools/import_protein_inventory.py`
from the evidence folder. It is a snapshot, not a catalogue: the catalogue's design (stage 3
of the plan) has not begun and belongs to the engine. See `data/proteins/README.md` for the
sources and licences.

### Species atlases

The user, 14 November 2026: "start an agent to create a full catalogue of Planerian
proteins - then another one to be able to switch between Human and Planerian (later
others) atlases".

A unit is a machine that a law acts on, so it has no species. The 49 units drawn, their
laws, their mapping and their shapes are the engine's and stay the same whichever species
is shown. What changes is the gene products that would make each machine in that species,
and how sure that is. Nothing here says the engine models a species' protein.

- **The switch** is the page's one Species control: in the bar on a wide window, in the
  view's card on a narrow one or when the bar is full. The page opens on the species
  whose file says `default` (the planarian). `species=<id>` in the address sets it,
  `atlas=` is another name for it, and `finding=` sets the legend's species filter. An
  atlas that found nothing for more than a quarter of the units is drawn quietly: those
  units faint, with no rings.
- **One file per species:** `data/proteins/atlases/<species>.json`, in the form
  `schema/SPECIES_ATLAS.md` fixes. The extractor reads every file there (`--atlases DIR`
  for another folder) and checks it against the contract; a strict build fails on a
  breach. A further species needs a file and no new code.
- **Four findings** per unit: found, a different family, nothing found, nothing to look
  for. A ring on the membrane marks a unit where the species differs: unbroken for a
  different family, broken for nothing found. The legend's "In this species" block
  filters by finding.
- **Four kinds of evidence** per product: reviewed entry, named in a publication, family
  signature, similarity search. A product found by signature or similarity is called a
  candidate, never an established counterpart.

**The planarian atlas** is of *Schmidtea mediterranea*, the planarian the databases know
best. It has an entry for all 49 units:

| Finding | Units | |
| --- | --- | --- |
| Found | 38 | gene products of the same family |
| A different family | 3 | the gap junctions: planarians build them from innexins, not connexins |
| Nothing found | 2 | Kir2.1 and NKCC |
| Nothing to look for | 6 | lumped properties, a default current, a configured slot and the designed cage |

It lists 204 gene products. Four are named in a publication; the other 200 are candidates
found by a family signature, in UniProt's entries and in the gene models of one genome
annotation. Nothing is called an ortholog. Its sources are UniProt, WormBase ParaSite,
InterPro, the European Nucleotide Archive and Europe PMC, each with its terms stated in
the file. `tools/build_planarian_atlas.py` rebuilds it, byte for byte, from the responses
saved in `/mnt/workspaces/Cells/visualizer-planarian-proteins-20261114-01`, which stay
outside git. `docs/PLANARIAN_ATLAS.md` gives the method, the counts, where planarians
differ and what could not be determined.

**The library of about 10,000 planarian proteins** that the user named (the user, 14
November 2026: "there is one catalog of 10k ones, let's get all those in just first in
your data sub folder") was found and not imported. It is the mass-spectrometry spectral
library of Ying and others (2025, doi:10.1016/j.devcel.2025.08.015). Its list of proteins
is not in the study's public deposits, and the paper reserves all rights.
`data/proteins/planarian/README.md` records what was found and what an import needs.

**The open set is in the folder in the meantime,** by the user's decision of 14 November
2026, until the library's list can be had with permission:
`data/proteins/planarian/predicted_proteins.tsv`. It holds the 18,882 proteins on open
record for the species, 17,294 gene models of one genome annotation and 1,588 UniProtKB
entries, in 2.2 MB without sequences. They are predicted from the genome and from
transcripts, not measured, and the table is not the library. The viewer does not read it.
Joining any catalogue to the engine's protein catalogue is for the user and the lead.

## Species

The user, 14 November 2026: "for the visualization we must be able to switch species that
will change the different levels", "we want a switch for syn3a as well ... then of course
we will have to switch off multi-cell", and "the cell chapes, organ shape and body shape
must bve configurable as well based on our different species as we add them".

- **One species for the whole page.** It sets the levels of the Cell and scales view, the
  shape drawn at each, which capabilities have a place in the cell, and the species' side
  of the protein atlas. The Engine and Experiments views do not depend on it.
- **A species is added with files alone:** `data/species/<id>.json` (`schema/SPECIES.md`),
  with outlines for an organ or a body under `data/species/shapes/`
  (`schema/SPECIES_SHAPES.md`). The viewer holds no drawing of any species; a test checks
  that no module names one.
- **What Cells models of a species is said on the page.** Human and Planarian are
  `generic`: Cells models a generic cell and sheet, and the species lends names or
  outlines. JCVI-syn3A and Mycoplasma pneumoniae are `proposed`: nothing of them is in the
  engine, and the picture shows where Cells' capabilities would have a place in them.
  This is the viewer's switch; the engine has no organism switch.
- **Each species' own proteins** are placed for shelves in the protein atlas
  (`schema/SPECIES_PROTEINS.md`, `data/proteins/<species>/shelves.json`): 455 for Syn3A,
  688 for M. pneumoniae, and the planarian's 18,882 as families that open. The data is
  made; the drawing is not yet.
- **Rough edges:** the human heart and body are quick placeholders; M. pneumoniae is drawn
  as a plain rod, since the shape list cannot yet narrow one end for its attachment
  organelle; a cell under 2 µm across has one size mode.

## Experiment replays

A replay draws what a run saved, and nothing else.

- **The class and the readouts are the run's own.** Each replay shows the class the
  experiment's summary recorded and the values in the run's outcome file, under the
  experiment's own names. A readout the run marks as supplementary says so. The viewer
  computes no verdict.
- **Positions are derived.** The runs save which cells are joined but no coordinates, so
  the adapter lays the sheet out as the hexagonal lattice its junctions define. The replay
  is marked as derived and lists each derived piece. Rotation and handedness are arbitrary.
- **Run data is not in git.** `tools/adapt_run.py` reads the frozen run folders and writes
  one file per run under `out/runs/` (0.2 to 0.9 MB each), which is git-ignored.
  Only the adapter, the labels in `data/replays/` and a small synthetic fixture are committed
  (the user, 14 November 2026). The published page carries the chosen runs as files beside
  it and loads one when it is first shown.
- **The format is the viewer's side of D154.** `schema/RUN_VIEW.md` fixes it. When the
  engine writes its own view file, the adapter is replaced and the view stays.

Two experiments are replayed today, 59 runs in all (34.5 MB; the largest run file is
0.87 MB, and each is loaded only when it is shown):

| Experiment | Runs | What the record says it found |
| --- | --- | --- |
| E07-v1: renewal | all 38 of its judged execution | Judged. The disc did not renew; 8 of 15 scored predictions held |
| The turnover pre-screen | the 21 arms that have an outcome | A development pre-screen, not judged |

- **An experiment selector** heads the card. Beside each experiment stand two separate
  facts from the record: whether it was judged, and what the answer was. A judged
  experiment whose answer is no is shown as exactly that. Each run says how it ended.
- **The first run shown** is of E07-v1's inheritance route, which its judged result is
  about; the control at two couplings follows.
- **Where an arm's files name no disc,** it is taken as the cells above the experiment's D
  threshold at the first record, and the replay says so.
- **Held back:** the W1 heredity pilot adapts (two runs), but the view draws every event
  as a replacement and the pilot's events are a cue in many cells at once.

To make them all:

```bash
npm run adapt:runs -- --evidence /mnt/workspaces/Cells
```

`data/replays/selection.json` lists the runs per experiment, and
`data/replays/overlay.json` holds each experiment's labels, plain lines and what it found,
with the record's line and its source.

## Sizes in the cell view

One unit is one micrometre, and the scale bar reads in real units at every zoom. The
"To scale" mode uses typical textbook values for a generic animal cell. They are orders
of magnitude, not measurements of the cells that Cells simulates, and counts are
indicative.

| Part | Drawn to scale as | In schematic mode |
| --- | --- | --- |
| Cell | six-sided, 18 µm between opposite sides and 20 µm between corners, 13 µm tall like the sheet's cells; the shape is the picture's choice | the same, 17.5 µm between sides so that the gap to each neighbour shows |
| Nucleus | 6 µm across | the same |
| Mitochondria | 120, about 0.6 µm wide and 1 to 3 µm long, some curved: a clear outer membrane with the inner folds showing (a real cell holds hundreds or more) | 9, about 2 µm wide, three cut open to show the folds |
| Endoplasmic reticulum | thin sheets close together and tubules through the cell | four thick ribbons |
| Ribosomes, vesicles | grey dots and clear bubbles: scenery, since protein synthesis and vesicles are not capabilities | grey beads and a few clear bubbles |
| Membrane | a fine line (5 nm is far below one pixel) | a thick beaded band |
| Channels, pumps, junction channels | thousands of dots; shapes about 10 nm across in the close-up | a few blocks set in the membrane |
| Protein cages, ATP, ions, small molecules | dots and haze | a few beads and clusters |
| Space between cells | 40 nm wide, far below one pixel: a dotted line round the cut edge, and dots where three cells meet | a 0.9 µm gap with a few ions in it |
| Neighbouring cells | six faint glass cells against the cell's sides, 40 nm away, standing where the sheet's own cells stand: scenery | the same, 0.9 µm away |
| Cut-away top, and the plate under the layer | a dashed outline of the outer face that the cut removes, and a lined plate where a flatworm's skin rests on a basement membrane, which Cells does not model: scenery | the same |
| Layer beyond the sheet | five rings of cell outlines, fading: scenery | the same |
| Organ outline | a planarian's brain with its two nerve cords, drawn about 0.9 mm long: a placeholder, sizes indicative | the same |
| Organism outline | a planarian flatworm, drawn 10 mm long and 1.3 mm wide: a placeholder, sizes indicative | the same |

In "To scale" the close-up of the membrane is to scale as well: a bilayer about 4.5 nm
thick, a channel about 9 nm across, and a 10 nm scale bar. For comparison, the cells of
the E07 sheet are about 11 µm across by their declared volume (0.75 pL).

## Run it

```bash
cd visualizer
npm install                 # three.js 0.170.0 and esbuild, both pinned
npm run extract             # read the main checkout, write data/architecture/architecture.scene.json
npm run import:proteins -- --inventory PATH/law_inventory_v2.json   # only when the inventory changes
npm run serve               # http://127.0.0.1:4173/  (add -- --offline to load three.js locally)
npm test                    # scene, sources, page and allowed hosts; no browser needed
npm run check:input         # real clicks, drags and wheel in headless Chrome (picking, the cut-away, zoom, the atlas, its species sides and its links)
npm run check:species       # real clicks on the species switch: each species' levels, cell and wording, in every view
npm run shot -- --out /tmp/shot.png --query "lens=engine&select=num.imex" --theme dark
npm run adapt:runs -- --evidence PATH   # make the replays under out/runs/ (not committed); PATH holds the evidence folders
npm run export              # out/cells-architecture.html, the page as an artifact wants it, and the list of run files to publish beside it
```

From another machine, forward the port (`ssh -L 4173:127.0.0.1:4173 host`) or open the
published artifact. `npm run export -- --standalone` writes one complete HTML file that
opens straight from disk.

The preview server sends a content policy close to the artifact frame's, so a load that
would be blocked when published is reported in the terminal while developing.

## How it is built

```
checkout (src/, docs/) ──tools/extract_architecture.py──┐
data/architecture/overlay.json (curated, sourced) ──────┤
law inventory ──import──▶ data/proteins/ (snapshot) ────┼─▶ scene JSON ─▶ <cells-viewer> ─┬─▶ npm run serve
run outputs ──adapters (next)── run view ───────────────┘                                 └─▶ npm run export ─▶ artifact
```

| Path | Holds |
| --- | --- |
| `tools/extract_architecture.py`, `tools/lib/static_eval.py` | The extractor. Standard library only; parses source with `ast` and never imports `cells` |
| `data/architecture/overlay.json` | The curated layer: layers, statuses with sources and dates, plain lines, planned parts, the capability map |
| `data/architecture/architecture.scene.json` | The generated scene (committed, so changes show in diffs) |
| `tools/import_protein_inventory.py` | Makes the slim snapshot of the law inventory. It leaves out machine paths, Xenbase identifiers and every field the view does not show |
| `tools/lib/protein_atlas.py` | Turns the snapshot into the atlas's parts, and checks every law record against the checkout |
| `tools/adapt_run.py` | Turns a saved run folder into a replay file. Standard library only; reads the frozen evidence and never writes there |
| `data/replays/` | For each experiment: labels, plain lines and what the record says it found, and the runs chosen for the page. (Not `data/runs/`: the repository ignores every folder of that name) |
| `docs/` | Reviews written for the lead: `PROTEIN_ATLAS_REVIEW.md` |
| `src/replay/`, `src/lenses/replay.js`, `src/ui/timeline.js` | Loading a replay, the Experiments view and its timeline |
| `data/proteins/` | `inventory.snapshot.json` (generated, do not edit), `overlay.json` (districts, plain lines and the shape drawn for each kind of unit) and the sources notice |
| `schema/RUN_VIEW.md` | Draft of what a run saves so it can be replayed (the consumer side of D154) |
| `src/scene/model.js` | The scene format's reader and its structural checks |
| `src/core/` | Stage (renderer, camera, picking), camera control, labels, theme, status materials |
| `src/lenses/` | `stack.js` (engine), `cell.js` and `cell_parts.js` (cell and scales), `proteins.js` and `protein_parts.js` (protein atlas) |
| `src/ui/` | `<cells-viewer>` and its parts: panel, legend, list |
| `src/page.html`, `src/page.css` | The page and its colour tokens, light and dark |
| `tools/lib/build_page.mjs`, `serve.mjs`, `export_page.mjs`, `screenshot.mjs` | One page builder for every delivery mode |
| `tests/`, `tools/check_input.mjs` | Browser-free checks, and a real-input check driven through Chrome's DevTools protocol |

Each group of the scene belongs to one lens, so the scene says where a part is shown.

**What comes from the code** and so cannot drift: the files in each part and their sizes,
which part uses which (imports), the registered operators with their contract declarations
(requires, writes, provides, reads, conflicts), model identifiers, the plan's gates and the
shared-state table. Every engine file belongs to exactly one part; the extractor warns if
one does not.

**What is curated** in `overlay.json`: statuses, plain-language lines, planned parts and
the capability map. When the record changes, edit the overlay, run `npm run extract` and
`npm test`, then publish.

### The viewer as a component

```html
<cells-viewer lens="cell">
  <script type="application/json">{ ...scene... }</script>
</cells-viewer>
```

It also takes `src="scene.json"` or a `scene` property. It emits `cells-ready` and
`cells-selected`. Colours and fonts come from CSS custom properties on the page (see
`src/page.css`), so the 3D scene follows the page's theme.

## Publishing

The visualizer session publishes its own artifacts (the user, 14 November 2026).
`artifacts.json` records each one's URL so that updates go to the same link.

1. `npm run extract && npm test && npm run export`
2. Publish `out/cells-architecture.html` to the URL in `artifacts.json`, with the run files
   listed in `out/cells-architecture.files.json` beside it.

Published pages load three.js from cdnjs, the preferred host of the artifact frame's
allowlist; everything else is inside the page.

### From a fresh checkout

Everything that makes the page is in this folder on the branch `visualizer`, except two
things that are remade: `node_modules/`, and the replay files under `out/runs/`, which
stay out of git (59 runs, 34 MB).

1. `npm install`
2. `npm run adapt:runs -- --evidence /mnt/workspaces/Cells` remakes `out/runs/` from the
   frozen evidence folders that `data/replays/selection.json` names. Skip it when
   `out/runs/` is still on disk.
3. `npm run extract -- --strict && npm test`. The extractor reads the main checkout, so
   the map states the revision main is at.
4. `npm run check:input` (real input in headless Chrome; several minutes)
5. `npm run export`
6. Publish `out/cells-architecture.html` with every file listed in
   `out/cells-architecture.files.json` beside it, under the same relative paths
   (`runs/<run id>.json`). A later publish keeps the files it does not send, so only
   changed runs need sending again.

An artifact can be updated only by whoever published it, or by someone its owner has
given edit access from the page's Share menu. Where that is not possible, publish a new
artifact, send every run file with its first publish, and record the new URL in
`artifacts.json`.

Work that is not yet committed stays as files in the worktree
(`.claude/worktrees/visualizer`). Only the coordinating session commits, so a file found
modified or untracked there is an agent's unreviewed output: check it against its
contract under `schema/` and run the steps above before committing it.

## Git

This folder lives on the branch `visualizer`, in its own worktree, by agreement with the
lead session on 14 November 2026. The rest of the repository is read-only for this lane.
The user merges the branch when they choose.

## Next

1. **Events that are not replacements.** The W1 pilot's cue needs its own drawing; its
   two runs already adapt.
2. **More of each run.** The concentrations, the osmotic term and the junction gates are
   saved but not yet shown, to keep a run under a megabyte. The pilot's 70-minute arms
   need a smaller number type or fewer records to fit.
3. **Other experiments**, each with its own adapter until the engine writes a view file
   per run (D154): division needs a geometry that is not a sheet and a thinning rule; the
   conduction probe needs a chain layout; the held sphere needs radial shells.

For the species atlases, what remains is the measured library of about 10,000 proteins.
The project does not contact authors (D173), so its list has to appear in a public source
under terms that allow a copy; the other route is a reanalysis of the study's open
instrument files. A table the user already holds can be read from
`/mnt/workspaces/Cells/visualizer-planarian-library/`, and stays outside this public
repository under the paper's present terms.
`docs/PLANARIAN_ATLAS.md` says what each would take.

For the protein atlas, each of these needs the user's approval first, because the plan
counts fetching from the public atlases as data tooling (stage 5):

- **Real structures:** draw the cited PDB or AlphaFold models in place of the schematic
  shapes.
- **Where each protein is found:** tissue and subcellular location from the Human Protein
  Atlas, kept apart from what the engine models.

The user on the atlas, 14 November 2026: "as we get more we can stack those glass shelfs".
Read here as: when the atlas gains units, add further membrane sheets above and below,
rather than widen one. That reading is the visualizer session's, to be confirmed.

Ideas kept for after the basics (the user, 14 November 2026):

- **Space–time block:** stack a sheet's records vertically, so a pattern that persists
  through turnover is a column and one that erodes dissolves.
- **Lineage arcs:** draw each donor-to-newcomer copy through time.
- **Architecture time-lapse:** run the extractor at each milestone tag and scrub through
  how the engine grew.
- **Path highlighting:** pick an experiment and light every model, operator and law it ran.
- **Verdicts and ledgers on replays:** judged predictions and conservation checks beside
  the timeline.
- **Illustrative machinery driven by aggregates:** molecular motors and channels animated
  from the modelled populations' values, marked as illustration.
- **Larger scales:** tissues beyond sheets, organs and whole animals, as the engine reaches
  them. The outlines are placeholders today: a planarian and its brain (the user, 14
  November 2026, in place of the first fish outline).

## Known limits

- The molecular scale is one membrane patch with one channel and one pump.
- The planarian and its brain are sketches with indicative sizes. One search gave about
  20 mm by 2 mm for a planarian, from an unreviewed preprint, and no measurement of the
  brain, so the outlines are of a planarian in general and the page labels both as placeholders. The
  protein atlas does name one, *Schmidtea mediterranea*, because its entries come from
  that species' database records.
- A species atlas repeats a family's candidates on every unit of that family (68 innexin
  candidates on each of three units), which makes the scene about twice as large. The
  no-WebGL list has no species switch.
- The protein atlas is as current as its inventory (12 November 2026). A law added to the
  engine since then is not in it; the extractor only checks that the recorded laws still
  exist. Its shapes are schematic, and where an auxiliary subunit sits is textbook
  knowledge, not a field of the inventory.
- Only one hue marks a named protein in the atlas. Six family colours could not be told
  apart under colour-vision deficiency (the palette check failed), so families are told by
  their labelled districts.
- "To scale" sizes are generic textbook values, as the table above says. No capability's
  dots are counted from a model's actual abundances yet; that would be a good use of the
  run view once replays exist.
- Statuses are as of the date in the top bar; the map does not update itself.
- Screenshots use software WebGL; performance on real hardware is not measured.
- On a phone the top of the cell view is crowded: the view switches and the scale rail both sit there.
- Established (slate) and landed (blue) differ mainly in saturation. The four status hues
  pass the colour-blindness checks on both backgrounds; slate is a neutral and is not part
  of that check, so the panel and the list always name the status in words.
- The page has run locally under an approximation of the artifact frame's policy. A check
  inside the real frame is by eye.
- A capability marked qualified cites the pass it rests on, but a line-by-line review of
  each claim against the record is still owed before the map is shared outside the team.
