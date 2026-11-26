# Cells visualizer

A 3D viewer for Cells: the architecture, the proteins it models, and replays of its
experiments.

It is tooling, asked for by the user on 14 November 2026. It reads a checkout and saved
run outputs, and it is never imported by the engine (D006, D154). It settles the open
viewer-technology item O006: three.js with web components, no framework.

**Audience:** the team, investors, other scientists and the public. Every part therefore
has a plain-language line first and the technical detail after it.

## What it shows

One data file, the scene, drawn through six lenses, each under a tab, in this order (the tabs' titles and their order were decided on 17 November 2026):

| Tab | What you see |
| --- | --- |
| **Scope** (the Cell view) | What Cells can simulate, drawn where it happens: one cell opened by a flat cut (after the README's biology map), the sheet of cells around it, and two placeholder outlines for the scales nothing simulates yet: a planarian's brain and the whole worm. The scales are nested, so zooming out leads from tissue into organ into organism: the sheet lies on the worm's head, above its brain. The sheet stands for skin-like tissue, a single layer of cells lying over the brain, and the cell is one cell of that layer, drawn with its neighbours (the user, 14 November 2026). The cell is flat-sided, as a cell packed in a layer is (the user, the same day: "make the cell shape be a bit more like planerian skin cell"); the shape is the picture's choice, since the engine gives a cell a volume and a membrane area and no shape, and it is not a model of a planarian's skin cell. It is placed on the worm for the scales only and is not the worm's tissue; the brain's own cells, neurons and glia, are not modelled. Zoom is continuous from molecules to organism, with a scale bar. **The species list sets the levels, the shapes and what the cell holds:** Human, Mouse, Frog, Planarian and Fruit fly under Animals; Syn3A, M. pneumoniae and E. coli under Bacteria; Thale cress under Plants. A single-celled species ends at its cell; the outlines of organs and bodies (the planarian's brain and worm, the human's heart and body, the mouse's ear and the mouse, the frog's hind foot and the frog, the fly's wing and the fly, the cress's leaf and rosette) are placeholders. The cell has a resting look, with a switch back to the plain picture |
| **Machines** | A catalogue of the molecular machines of the species shown (`schema/MACHINE_CATALOGUE.md`), in trays on a bench by what they do. A machine with a published size is a simple shape at that size, all at one scale with a 100 nm bar; one with no size in hand is a card. The flagellar motor is drawn from its own file, an outline among the others, its parts and subunits when chosen. Each panel says what names the machine, how many and how big with their sources, the proteins its species' data marks with it, and what Cells models of it only as the record says (the ATP synthase: planned, first, D209; the rest: no model yet, FR-13). On the animals' benches the eukaryotic ribosome and five units of the law inventory (the sodium pump, SERCA, the IP3 receptor, Kv1.2 and the gap-junction channel) are drawn to scale from the viewer's own measure of a structure, of the species' own organism or another, and each panel says whose structure it is; the ATP synthase, chosen, stands in a thin slab where its ring stands, an illustration. Eight species' benches hold the machines their dossiers name (`schema/MACHINE_DOSSIERS.md`; the planarian's, Syn3A's and M. pneumoniae's proteins as candidates by family, never called parts), each bench a file beside the page read when it is shown (the page carries the catalogue's core), each with its proteins by tier, its count from an open paper where one gives it, and a door from each chain to its protein in the Protein atlas and back; the human's proteasome, mitochondrial ATP synthase, three RNA polymerases, complex I, mitochondrial ribosome and CMG helicase are measured, and its nuclear pore stays a card. A kind's panel lists the forms the Complex Portal curates for it (for the human, E. coli, the mouse and the fruit fly): each entry with its name, its Complex Portal page, how many proteins it holds and how many of the machine's parts, its stoichiometry where it gives one, and its evidence in the portal's own term (an inferred entry says so first); a form is never a machine of its own. The vault, a particle whose job has not been found, stands in a group of its own, in a tray at the back of the human's, the mouse's and the planarian's benches (behind the units' tray, where its large shape hides nothing): by the Complex Portal's record (the human), by UniProt's reviewed entries with the evidence of each sentence (the mouse), or as a candidate by its family (the planarian), each said in its own words; its size and shape are the viewer's own of a human vault (PDB 9MXV), and a bioRxiv preprint (not peer reviewed) on prokaryotic vaults is cited by its numbers and their places, with no prokaryotic vault shown. Every measured machine and unit (E. coli's six, the mycoplasmas' ribosomes at E. coli's, the human's nine, the animals' 80S and five units) offers a fourth level, Shape: the viewer's own smooth surface of each chain (`schema/MACHINE_SHAPES.md`, drawn by `src/lenses/machine_shape.js` as one mesh), a press on a surface choosing its chain. A part or chain chosen in a machine is lit in the page's accent. Behind each bench of a species whose cell has organelles stands a shelf of them at the same one scale, the small ones (a mitochondrion, a lysosome, a vesicle) on a plank of their own between the bench and the shelf: each drawn with the Cell view's model of it where there is one (the nucleus, the endoplasmic reticulum, the Golgi apparatus, the mitochondrion, a centriole, the thale cress's chloroplast), else with a simple model of its own, an illustration (a lysosome, a peroxisome and an autophagosome cut open over their lumens, a COPI vesicle with knobs for its coat, an endocytic vesicle with short tubules, a lipid droplet), each at a size its panel gives with its source, a measurement in one cell type or a general figure (the human's nucleus, centriole and endocytic vesicle are drawn on measurements the project's files cite and the page does not show), and a card where no size is in hand, which says what was looked for; a scale rail travels between the bench, the small organelles' plank and the shelf, each power of ten in the same time, the scale bar following, and a loupe holds a machine beside an organelle of the shelf, at its true size and magnified by a factor written on its frame. A measured machine's parts are its sub-assemblies, drawn as their chains, each part in one colour; the opening view frames the shapes, and while one is chosen the rest of the bench is faint. The law inventory's membrane units stand in a tray of their own, as the Protein atlas lists them; a unit's panel says which of its laws an active model declares. All of it is illustration |
| **Proteins** (the Protein atlas) | The units of Cells' law inventory, set in the membranes where their laws act: channels, pumps and transporters in the plasma membrane, junction channels between two cells, and the ER and mitochondrial units inside. Each links to its engine part and out to the public atlases. A unit's panel opens each of its laws an active model declares in the Laws library; of each other law it says, with no door, what the law-port inventory of 17 November 2026 marks it (D211: to port as is, to fold into the cardiac lane's planned laws, or not a port), or, where that inventory has no row for it, that the engine's declarations do not list it. For the species shown it gives the gene products that would make each unit (Human and Planarian today), and it shows every species' own proteins on shelves: each protein by its side of a membrane, as families that open where there are thousands |
| **Engine** | The simulator as a stack of layers, from the machines it runs on up to the experiments. References stand outside the stack, because the engine never contains them. The plan's gates climb beside it |
| **Laws** | Each family has a pod and each catalogue piece a star. Highlight a model to see its members, or choose a piece and fly along a labelled connection to its requirement, field or model. The breadcrumbs return you to any earlier stop. A two-model matrix shows shared and exclusive pieces and how each is declared. The Scope view links through explicitly mapped protein units. The bridge and shelf layouts are available through `lawLayout=atlas` and `lawLayout=shelves`. See [the Laws library](schema/LAWS_LIBRARY.md). |
| **Experiments** | A saved run replayed: the sheet of cells coloured by membrane voltage, a timeline to play and scrub, each cell replacement marked as it happens, and the class the experiment's own summary recorded for the run. Quantity layers draw onto it what cannot be seen: voltage as height, the drops across junctions, the push and pull on each ion, the charge on a membrane, what flows, where energy is dissipated, a secreted signal. Shown only when replays have been made |

Selecting a part that belongs to another lens takes you there: a protein unit's connection
opens the engine part that holds its law, and that part lists the units it holds laws for.
A part's id of a view's own (`laws:…`) opens that view from any other, so
`select=laws:kir2p1_mh2@1` works without `lens=`.

A view can also stand on a page of its own (`node tools/build_view_page.mjs <view>`):
the Laws library and the origin-of-life view each have such a page beside their place
here.

**About and the first visit** (the owner, 20 November 2026). The bar's About button, after
List, and the name Cells in its corner open About in the side panel's place (a sheet on a
phone): what the page is, in words taken from the repository's README, the site's
description and the map's caveat, each view as a door, the source code in a new tab, the
credit line ("Made by Eidosoma."), and what the page knows of itself (the map's stamp; on
the site, its release). The words are written once, in `data/site/about.json`, which the
page carries in its scene as `about` (`src/ui/about.js`); what names anyone is its
`credit` alone. `#about` in the address opens it, in the artifact's frame too. On a first
visit a line under the bar says what the page is, with About, the source code and a close
button; closed, it stays closed in that browser. On a window 760 px or wider it stands in
the first band under the bar that covers no card, control or note and none of the view's
names (it keeps from a name the clearance a name keeps from a card); elsewhere, and on
every phone, it waits out of sight. Every check is a first visit (each run has a new
browser profile), so the line stands in their pictures where it finds room.

Three things are encoded, and kept apart:

- **Status**: qualified or judged, implemented and guarded, established, designed, planned,
  failed, external reference. The first two follow the plan's four levels (D156). Where
  colour shows the kind of part, every part is drawn whole, whatever its status (the user,
  16 November 2026: "in the default mode show it all in the coolest possible way");
  "Colour: Status" shows what is not built as grey sketches. In the engine
  lens colour shows status too. In the cell lens colour shows the kind of part by default
  (purple nucleus, orange mitochondria), and the dot beside each name shows its status;
  the "Colour" switch turns the cell to status colours.
- **Representation** says how the engine treats a capability: simulated, modelled in
  aggregate, prescribed, or illustration only. Shapes that stand for modelled populations
  (channels, pumps) are illustrations and are labelled so.
- **Size mode** (cell lens): "Schematic" enlarges parts and shows few, so each can be
  seen. "To scale" draws sizes and numbers nearer a real cell; see below.

Rules the map keeps, so it can be shown outside the team:

- It states no status the record does not state. The shared-state entities and the plan's
  gates carry the plan's own words, not an inferred status.
- Every status has a source and, where the record gives one, a date.
- Everything drawn is bound to a part of the scene or is neutral grey illustration. One
  exception, by the user's decision of 16 November 2026: chloroplasts are green, as they
  are in life, where the cell is coloured by kind. They are still scenery, their panel
  says so, and they are neutral where colour shows status.
- The nucleus, the Golgi apparatus and the ribosomes are parts of the map of their own,
  planned, by the user's decision of 16 November 2026 (`docs/CELL_STRUCTURES.md`):
  nothing of them is in the engine, each panel says so, and none is called simulated.
  "Regulatory circuits" is drawn at the cell's DNA, as the separate small model it is,
  and no longer names the nucleus. Choosing a structure offers a door into the Protein
  atlas where the species' own proteins can show its set.
- Where the Golgi stands follows the cell (the user, 17 November 2026, choosing option B
  of the review of "the position and scale of the golgi v. er and nucleaus";
  `docs/CELL_STRUCTURES.md`): in an animal cell beside the nucleus, round a centrosome,
  with the ER in two arms either side of it; in a plant cell, many small stacks in the
  thin cytoplasm by the membrane, with no ribbon and no centrosome. Their distances and
  counts are the picture's choice. The centrosome is scenery, and its panel says so.
- The cell picture carries the README's caveat: capabilities vary by model, and
  whole-cell integration is ongoing. The legend's "Runs together in" filter shows which
  parts run together in one model today.

## The protein atlas

The atlas shows Cells' own law inventory (stage 2 of `docs/PROTEIN_CATALOGUE_PLAN.md`): 49
functional units, the 80 engine laws that act on them, and their 93 candidate gene
products. It is not content from the Human Protein Atlas or any other public atlas. It
links out to UniProt, the RCSB PDB, the AlphaFold DB and the Human Protein Atlas.

**48 of the 49 units are drawn.** The engineered protein cage, and the capability of
protein assembly with it, are left out of the picture for now (the user, 15 November
2026: "leave those out of the viz for now as they are out of character with the rest
which are all real or planned things"). A flag in each overlay does it (`left_out`), the
page lists what is left out and why, and removing the flag puts the cage back. The
engine parts that implement it stay on the Engine view, which maps the code.

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

A unit is a machine that a law acts on, so it has no species. The units drawn, their
laws, their mapping and their shapes are the engine's and stay the same whichever species
is shown. What changes is the gene products that would make each unit in that species,
and how sure that is. Nothing here says the engine models a species' protein.

- **The species list** is the page's one Species control, a drop-down in which the
  species stand under the headings their files give (`group`: Animals, Bacteria, Plants).
  It is
  in the bar on a wide window, and in the view's card on a narrow one or when the bar is
  full. The page opens on the species
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
- **Two facts per product, kept apart** (`schema/SPECIES_ATLAS.md`, since 16 November
  2026):
  - *How it was found:* by the signature of a family that makes the machine; only by the
    signature of a family that goes with it, such as a beta subunit or a regulator; named
    in a publication; or by a similarity search, which no species uses yet.
  - *What its record is:* a UniProtKB entry reviewed by a curator, one annotated
    automatically, or a gene model or a genome record's protein with no UniProtKB entry.

  A product found by its family's signature or by similarity is called a candidate,
  never an established counterpart, whatever its entry: a reviewed entry says how the
  entry was written, not that the protein does a unit's work. One found only by an
  accessory family's signature is a candidate for no machine's own work, and on the
  shelves it is drawn plain, not in the unit's shape. The card counts the two facts apart.

**The planarian atlas** is of *Schmidtea mediterranea*, the planarian the databases know
best. It has an entry for all 49 units:

| Finding | Units | |
| --- | --- | --- |
| Found | 38 | gene products of the same family |
| A different family | 3 | the gap junctions: planarians build them from innexins, not connexins |
| Nothing found | 2 | Kir2.1 and NKCC |
| Nothing to look for | 6 | lumped properties, a default current, a configured slot and the designed cage |

The cage's entry stays in the file, is held to the contract like the others, and is not
carried into the scene while the cage is left out.

It lists 204 gene products. Four are named in a publication; 168 are candidates found by
the signature of a family that makes the machine, and 32 carry only the signature of a
family that goes with one (beta subunits, regulators), in UniProt's entries and in the
gene models of one genome annotation. Nothing is called an ortholog. Its sources are UniProt, WormBase ParaSite,
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

**The planarian's own scan** (18 to 19 November 2026). The 18,882 proteins of the open set
were scanned again with InterProScan 5.78-109.0, with the member databases whose terms
allow it (`docs/PLANARIAN_ATLAS.md`, "The planarian's own scan"): all ten ran on every
protein, and 4,466 proteins gain 5,103 InterPro entries that their own column lacks.
`tools/read_planarian_scan.py` reads the scan's outputs into
`data/proteins/planarian/interproscan_added.tsv` (the entries each line gains, each with
the databases that found it) and `interproscan.json` (the scan's record: each database's
release, terms and citation, and how many proteins its pass ran on); the table's own
column is unchanged. The planarian's machine dossiers count the added entries as carried,
and call a family "not in the table" by the scan only where a database run on every
protein has a signature in it (`schema/MACHINE_DOSSIERS.md`): no part of its machines is
left as "cannot tell" (60 were), and myosin II has candidates and stands on its bench.
On 19 November 2026 it was decided that the shelves take the scan's added entries: their
filing reads them beside the table's own column, so 3,147 of the 18,882 proteins stand on
another shelf and 2,650 have a family they lacked ("No family assigned" holds 7,371, from
10,021). A member filed by what the scan added says so in its panel, with the databases
whose signatures reached it (PANTHER for most; CDD and NCBIfam named with their terms),
and those databases are sources of the shelves' file (`schema/SPECIES_PROTEINS.md`, "A
species' own scan"). Sides, districts and the atlas's candidates for Cells' law units
still read the column alone; a unit's panel leads to the families its candidates are now
filed under. CDD, which states no terms, stands by the decision of 18 November 2026 and is
held in a register of the licence test; NCBIfam is under a share-alike licence.

## Species

The user, 14 November 2026: "for the visualization we must be able to switch species that
will change the different levels", "we want a switch for syn3a as well ... then of course
we will have to switch off multi-cell", and "the cell chapes, organ shape and body shape
must bve configurable as well based on our different species as we add them".

- **One species for the whole page.** It sets the levels of the Cell view, the
  shape drawn at each, which capabilities have a place in the cell, and the species' side
  of the protein atlas. The Engine and Experiments views do not depend on it.
- **A species is added with files alone:** `data/species/<id>.json` (`schema/SPECIES.md`),
  with outlines for an organ or a body under `data/species/shapes/`
  (`schema/SPECIES_SHAPES.md`). The viewer holds no drawing of any species; a test checks
  that no module names one.
- **What Cells models of an entry is said on the page,** in one ladder of words
  (`schema/ENTRIES.md`): "Generic cell", "Proposed, not modelled", "Planned, not modelled",
  "Designed, not modelled" and "Modelled", each met only by tracked files of the engine's main
  or the viewer's own notes. Human, Mouse, Frog, Planarian, Fruit fly and Thale cress are `generic`:
  Cells models a generic cell and sheet, and the species lends names or outlines (no plant cell
  is modelled, and thale cress's card says so; the mouse's card adds D155's planned comparison
  of heart muscle cells; the human's, that its first cell type, a ventricular heart cell, is
  designed and not built, its design note on main proposed with its choices decided by D184).
  JCVI-syn3A is `planned`: D173 adopted it as the minimal-cell track, and nothing of it is
  built. Mycoplasma pneumoniae and E. coli are `proposed`. For all three, the picture shows
  where Cells' capabilities would have a place.
- **Model systems stand in the same switch,** under headings of their own
  (`schema/MODEL_SYSTEMS.md`). A model system is a model, not an organism. GARD, under "Origin
  of life", is the first (`data/models/gard.json`; designed, not modelled, D192). Choosing one
  shows it in the first tab's place, with its own levels on the rail. The Protein atlas keeps
  the species last shown, and says why. A model system's view is mounted through
  `src/ui/entry_views.js` and `src/ui/model_views.js`; until one is registered for its kind,
  its card says what it is. The address names any entry: `entry=gard` or `entry=syn3a`
  (`species=` and `atlas=` still work), and `cell=<type>` names a cell type of a species, once a
  species has more than one.
- **GARD has a view of its own here** (`src/lenses/lineage.js`, registered by
  `src/lenses/lineage_entry.js`): a protocell of lipids in water, playing a marked example.
  See "Origin of life" below.
  This is the viewer's switch; the engine has no organism switch.
- **Each species' own proteins** stand on shelves in the protein atlas
  (`schema/SPECIES_PROTEINS.md`, `data/proteins/<species>/shelves.json`), in one format for
  every species (the user, 15 November 2026: "let's have all the shelfs simmilar format
  inside outside for syn3a and all of them"): a shelf is a membrane, with what is outside
  standing on it, what spans it standing in it, and what is inside on glass below; what
  has no known side is set apart, never placed by guess. Syn3A (455) and M. pneumoniae
  (688) have one marker for each protein. The planarian's 18,882 stand as families that
  open (the user: "we should show them all but maybe cool expandable protein families"):
  a family of five or more has its own marker, the smaller ones of a district and side are
  gathered in one ringed marker, and "No family assigned" stands in parts in the same way.
  A protein with a `unit` that would make that machine is drawn as that unit. One that the
  species' atlas lists with the unit only by the signature of a family that goes with the
  machine, such as a beta subunit or a regulator, is a plain grey marker, and its panel
  says how the atlas found it and that it goes with the machine (`found_by`,
  `schema/SPECIES_PROTEINS.md`, since 16 November 2026). Every other protein is a plain
  marker, and the page says it is listed with no unit of Cells' law inventory. The card's switch moves between "Cells' 48 units"
  and "Its N proteins": Syn3A and M. pneumoniae open on their own proteins, the planarian
  on the machines.
- **Colour says the side** (the user, 16 November 2026, choosing the atlas's look: colour by
  membrane side, a trail, a search, a map). A species' own proteins are coloured by the
  side of each one's own membrane: beyond it, in it, enclosed by it (a family by the side
  where most of its members sit); what has no known side is hollow and grey. "Colour" at
  the head of the legend also shows how each side is known, essentiality where the
  species states it, and Cells' law inventory (one hue for what makes a unit of that
  inventory). Each shelf's own words name its sides. A gathering takes its side's own colour
  and is told by its dashed ring and its name.
- **Finding your way.** A trail above the picture says where you are (species, shelf,
  side, family, protein); each step goes back to it, and its arrow and Escape go back one
  level. A search in the trail finds a protein by gene, name or identifier, also in a
  family not yet opened, from a names file beside a large catalogue's members
  (`names.json`, written by the page builder, one more published file each: 0.3 to
  2.7 MB). A map of the stack at the right edge brings a shelf near.
- **The human's entries that only go with a machine** (auxiliary subunits, the sodium
  pump's beta subunits, the uniplex's regulators, the pump's FXYD regulators: 27) are
  drawn plain and say so, in the inventory's own words (`inventory_roles`).
- **A cell with several membranes has several shelves, stacked.** The human's 20,414
  reviewed proteins (UniProt's reference proteome), and the mouse's 21,872 and the fruit
  fly's 13,814, one for
  each gene, stand on six: the cell membrane, the endoplasmic reticulum's, the
  mitochondrial inner membrane, the nuclear envelope, other membranes, and "a membrane,
  not told which". E. coli's 4,403 stand on three: its inner membrane, its outer
  membrane, and a membrane not told which; what is free in the space between the two
  membranes stands on the inner one's shelf, on its outside. A family has one line on
  each shelf where it has members,
  and a protein for which no membrane is stated stands apart. "Show by" picks out a set
  of a species' proteins: for E. coli its chemotaxis proteins, and the assemblies a
  protein is part of (the flagellum, the chemoreceptor array, the ribosome).
  `docs/HUMAN_PROTEOME.md`, `docs/MOUSE.md`, `docs/ECOLI.md`, `docs/FRUITFLY.md` and
  `docs/XENOPUS.md` give each one's method and counts.
- **The frog, *Xenopus laevis*** (19 November 2026, `docs/XENOPUS.md`): 35,004 proteins of
  UniProt's reference proteome on the same six shelves. Its genes stand on two sets of
  chromosomes, L and S, and both copies of a gene are shown, each as its own protein; where
  a gene has a reviewed entry, its 1,425 unreviewed twins in UniProt's gene-by-gene set are
  not shown, and the reviewed entry names them, so that the search finds it by them; 476
  genes still stand twice with unreviewed entries only. Each protein's panel gives the copy
  of its gene and its chromosome, from UniProt's proteome component. Its gene names are
  UniProt's, which name Xenbase's nomenclature as their source; Xenbase is named on its
  shelves as read through UniProt, and nothing else of it is used. Placeholder names that
  embed Xenbase's number for a gene (304 gene names, 49 protein names) are not written:
  such a protein is shown and found by its accession (decided on 19 November 2026, the
  choice left to the viewer's coordinator). The adult is drawn, from one open paper's means
  for laboratory females; it has no bench of machines yet. It is the largest catalogue:
  its members are cut 6,000 to a file (6 files), and its shelves and members have bounds
  of their own (`data/proteins/overlay.json`, `shelves.limits`).
- **A species may carry life stages** (`schema/SPECIES_STAGES.md`, 19 November 2026): its
  stages in order, each stating only what differs from its file, with its sources, or
  named and not drawn; and the spans between them. In Scope they stand as a strip at the
  foot of the picture, the page's one timeline: a press on a drawn stage shows the species
  at it, by the viewer's own plain change (one picture held, an empty picture, the other
  held), which says that it is an illustration and not a run. Play shows only where a
  saved run fills a span; playing the plain change is built and switched off
  (`PLAIN_CHANGE_PLAYS` in `src/lenses/cell.js`). The strip's axis is the stages' order,
  never a clock. The reader is `src/scene/life_stages.js`; the build reads a block through
  it (`tools/lib/species.py`, through node); `tools/check_stages.mjs` checks it on a
  made-up species. **The frog is the first species with stages:** its fertilised egg
  (NF 1, a sphere 1.2 mm across, drawn with a generic cell's parts, which its picture
  says) and its adult are drawn; NF 2, 3, 35-36 and 66 are named and not drawn, since no
  size of them is in hand under usable terms (`docs/XENOPUS.md`, "Its life stages"). The
  frog opens on its fertilised egg (decided on 19 November 2026); its adult is a press
  away on the strip, and its address names it (`stage=adult`). Its egg alone gives a word
  of its own for what Cells models of it, "Planned, not modelled", with its record; every
  other stage takes the species' own word.
- **A plant cell is drawn from the same files.** Thale cress has 27,368 proteins, one for
  each gene, on nine shelves (`docs/THALECRESS.md`): a plant cell adds the plastid
  envelope, the thylakoid membrane and the vacuole's membrane. Its cell is a box with a
  wall, a large vacuole that presses the other parts to the side, and chloroplasts
  against the membrane; its sheet is packed in squares, which is the picture's choice
  (the sheets Cells has run are joined in sixes). The vacuole, the chloroplasts and the
  wall are scenery: nothing in the engine stands behind them.
- **A species can be held back** by naming it under `species_held` in the map's overlay,
  where the viewer cannot yet draw what its cell needs: its files stay and are checked,
  and the scene carries nothing of it. Thale cress was held so until a plant cell could
  be drawn; no species is held today.
- **Threads and hairs are a general part** (`cell.parts.appendages` in `schema/SPECIES.md`;
  the user, 15 November 2026: "lets draw flagella, pili as a general feature"). E. coli
  draws 3 of its 1 to 5 flagella and 120 of its 200 to 500 pili, and the picture says how
  many of how many. The foot of a flagellum can be chosen (from close by: seen whole, the
  cell's feet are a few pixels wide): its panel opens the Protein atlas on the 34 proteins
  of the species' flagellum, and offers "Look closer". A further kind of thread or
  organelle is one small function in `src/lenses/cell_scenery.js`.
- **A machine can be looked at closer** (`schema/MACHINES.md`; the user, 16 November 2026:
  "look closer sounds good"). "Look closer" in a foot's panel, or the machine's stop on
  the scale rail between the molecules and one cell, flies to a foot (the one chosen, else
  the one that faces the camera most). The cell fades out and the machine fades in, drawn
  from its own file (`data/machines/<species>.<machine>.json`, published beside the page)
  at its true size, upright, at one of three levels of detail (Outline, Parts, Subunits).
  Every part can be chosen. Its panel names its proteins, gives each of its numbers with
  what it rests on (a saved sentence and the organism it names; an entry of the Protein
  Data Bank and the organism its record states; or the picture's choice), and opens the
  Protein atlas on just those proteins. E. coli's flagellar motor is the first: most of
  its ring sizes were measured in Salmonella, and its panels say so. **Cells has no model
  of the motor**, and the picture says so for as long as it shows.
- **The motor turns as its flux** (`schema/QUANTITY_LAYERS.md`, rule 13; the user: "motor,
  yes it should turn at real life speeds at flux ... except if we slow down the flux"). It
  turns at real-life speed, about 150 turns a second, counter-clockwise seen from outside
  the cell, as in a run. That rate is the picture's choice within the 100 to 200 a second
  one paper gives for a swimming cell, which names no species; the top speed, 300, is said
  beside it. At that speed its marks are drawn smeared round, as the eye would see them,
  with an arrowhead for the way. The legend's Speed slider slows it (a thousand times at
  its middle, a million at three quarters), and then its marks turn. It stands when the
  address opens the view
  (`machine=flagellar-motor`), on a page opened still, and for a visitor who asks for less
  motion.
- **Licence classes.** Every source in a data file states its licence and its class:
  permissive, non-commercial, or no stated terms. A data file holds no value from a source
  that is not permissive (the user's rule, D173); such a source is a pointer in words.
  `tests/licence_classes.test.mjs` holds every file under `data/` to this. Where an open
  database reports a value that a restricted tool computed, the value may stay (the
  user's ruling of 15 November 2026, D178, for every species): "a value stands on the
  terms of the database it was read from, and the tool behind it is named and counted".
  The test keeps the register of those tools for each species. Nothing is downloaded
  from a restricted source itself; a source with no stated terms, or a kind of tool not
  seen before, goes to the user first.
- **Rough edges:** the human heart and body are quick placeholders; the mouse's ears are laid flat, so
  that the sheet, which the viewer draws level, can lie on one; M. pneumoniae is drawn
  as a plain rod, since the shape list cannot yet narrow one end for its attachment
  organelle; to scale, thale cress's wall reaches past its neighbours' membranes, because
  the neighbouring cells are drawn closer than two walls would let them stand.

## Experiment replays

The Experiments tab opens on a landing of cards that shows everything Cells has run, in
four bands, each card with its standing in the record's words (the user chose the layout
on 18 November 2026; the site's first entry is Scope, as before). A visitor first sees the
first band, the three examples to start with; every later band stands folded behind its own
control (19 November 2026):

| Band | Cards | What stands in it |
| --- | --- | --- |
| Examples to start with | 3 | The tumour tissue (the gap-junction work: the line, the ladder, the sheet and the networks, 50 runs; "Development work, not judged (D138)" first on it), the assembly (the engine's two development runs of the model system, in its own view), and **A vesicle’s life** (two development runs showing growth and shear division in one vesicle and threshold lysis in another) |
| Judged under a registered protocol | 19 | Everything the record has judged under a registered protocol, experiment or qualification, passed or failed, side by side, each card with its own level from the Engine map: E07-v1 (38 judged runs; its answer: the disc did not renew), the judged acceptances of FR-1, FR-3, FR-4, FR-5, FR-6 (two) and FR-10, FR-7's first closed loop (its comparison F4 against R-loop, both arms and its persistence rows; F3's comparison is queued), the morphogenesis gates MG0, MG0c and MG1 (its failed first run beside the pass), the secreted-species qualification D150, cell division, the BETSE parity ladder (rung 1's failed first run beside the passes), osmotic water and volume, cell replacement, the composite on the L4 (Implemented and guarded: its judged run's Q7 failed and stands), fixed points, and projective stepping (Failed qualification) |
| Development runs | 6 | The turnover pre-screen (21 runs), the secreted-species run and the planarian loop (1 each), the origin-of-life laws (six rows against references, landed for development and not judged), and the heredity pilot W1 and the conduction probe (the map states no level for either, and each card says so first) |
| Invented numbers | 1 | A test sheet of the viewer's own: no engine ran |

What is designed or planned and has not run is on the Engine map, and the landing says so
in one line, a press away from it.

- **Folded bands.** The first band of the cards' file stands open, drawn large; every
  later band stands folded under its head (its label, its words and its count) behind one
  button in the file's words (`bands[].control`: "Show qualifications and judged runs" 19,
  "Show development runs" 6, "Show the test sheet of invented numbers" 1; a band without
  words gets a plain control from its label). The rule is the band's place in the file,
  never its id. A press shows its cards under its head, and a second folds them. A folded
  band's cards are not drawn, not reached by the keyboard and not fetched. A card asked
  for (its detail's address, the List, the way back from its view) opens its band. The
  bands a visitor opened are kept in the browser's own storage for their next visit;
  where storage is refused the first band alone opens. On a window 1,100 px wide or more
  the cards leave the List room beside them, as they leave the panel room.
- **Three kinds of card.** A replay's card opens the view that exists for it, by rule (a
  model system's entry opens its own view; an experiment whose entry names a part opens
  that part; any other its opening run), and in that view "All experiments", under the bar
  at the left, leads back to the landing where it was left. A standing with no replay
  gives what it asked, its standing, each judged run's count of its own checks, its day
  and its scope line, and its sources. The origin-of-life laws are rows: each with its
  claim, its reference and its result. A standing's card, the rows' card and any card's
  "more" open its detail in the panel: the record's sentences, the scope lines whole,
  every count with its day, the sources as links at their revisions, and a door to its
  part on the Engine map.
- **Every word of a standing is read, never typed.** `tools/build_cards.py` makes
  `data/replays/cards.json` from the Engine map's overlay (a part's status, date, words
  and sources, so the map and the landing cannot say two things), the catalogue's overlay
  and selection, the model-system entries, and the record: the judged runs' own verdict
  files (counts, days, revisions) and `PROGRESS.md` and the notes at a named revision of
  main. What it reads from the record is kept with its file and field in
  `data/replays/cards.readings.json`; what is typed (titles, questions, bands, locators)
  is `data/replays/cards.source.json`. `schema/EXPERIMENT_CARDS.md` is the contract.
  ```bash
  python3 tools/build_cards.py --check     # in npm test: tracked files only
  python3 tools/build_cards.py --gather --evidence /mnt/workspaces/Cells --repo <engine checkout> --revision HEAD
  ```
  The gathering runs again when the record moves, when a locator changes, or when the map
  is merged forward. For a map-only refresh, omit `--revision HEAD`. That keeps the
  experiment record pinned and checks the newer map against `origin/main`.
- **Every judged entry of the record is placed.** The gathering lists every entry of
  `PROGRESS.md`'s runs that reports a judged run or a registered qualification; each is on
  a card or in the source file's `entries_left_out` with its reason, and a test holds it.
- **Passed and failed both show**, each verdict as it is, never summed. Where the record
  gives no count, or words a count otherwise than the run's file, the card shows none.
  Where the map states no level for a card's part (the tumour tissue, the heredity pilot,
  the conduction probe), the card carries none and says first what the work is.
- **Stills.** `tools/make_stills.mjs` pictures each replay card's opening view in both
  themes into `data/replays/stills/`, with `stills.json` (card, address, size, checksum,
  the page's revision, the renderer); each card's `replay.still` names them.
- **Addresses.** `lens=experiments` (or `#experiments`) opens the landing.
  `lens=experiments&select=card:<id>` opens a card's detail where the page is opened
  directly; a published artifact's frame passes only `#name`, so a detail has no shareable
  link there. Every address that worked before (`run=`, `select=run:`, `part=`,
  `example=`) opens its view without the landing.
- **What each address fetches.** The landing fetches `cards.json`, the cards' faces (what
  a card's face says, and what the List and the search read), and, as it opens, the featured
  cards' stills; a later band's stills only once it is shown and they come near the
  screen: no run and no model. The cards whole (`cards.details.json`, one file for every
  card, written by `tools/build_cards.py` beside the faces) are fetched the first time a
  card's detail is asked for, and once (20 November 2026: the faces are 67 kB, the whole
  187 kB). The site's first entry fetches nothing of the landing's. A
  card's view fetches its own run and the parts its opening view shows, and no other run.
  `fetches` (`tools/check_fetches.mjs`) holds each address to
  `tools/references/fetches.json`, with a bound in bytes.

A replay draws what a run saved, and nothing else.

- **The class and the readouts are the run's own.** Each replay shows the class the
  experiment's summary recorded and the values in the run's outcome file, under the
  experiment's own names. A readout the run marks as supplementary says so. The viewer
  computes no verdict.
- **Positions are the run's own where it gives them, and derived where it does not.** A
  run view that prescribes where its cells stand (`space.representation: "prescribed"`) is
  drawn there, every junction a line between its two cells, and no outside node is given a
  tile of the viewer's. A run that saves which cells are joined but no coordinates is laid
  out as the hexagonal lattice its junctions define: the replay is marked as derived and
  lists each derived piece, and rotation and handedness are arbitrary.
- **Checking an experiment package** (19 November 2026; `docs/EXPERIMENT_PACKAGE.md`, decided
  by the owner that day; round one of two). `python3 -I tools/check_package.py FOLDER` checks
  a run folder before the viewer reads it: its manifest (`experiment_package.json`,
  `cells.experiment_package@1`; the contract is `schema/EXPERIMENT_PACKAGE.md`, the schema
  file `schema/experiment_package.schema.json`, written by the tool), every package's view and
  the arrays it names, the sidecars, refused picks and summary, and then the adapter's own
  reading of each package. It writes nothing; exit 0 means the adapter reads it, 1 lists every
  problem with its code, 2 is a wrong call (`--json` for the report as JSON, `--codes` for
  every code). A folder with no manifest, as every folder written so far, is read as the
  adapter reads one today, and the report gives the manifest it would need. Where a run folder
  holds `experiment_package.json`, `npm run adapt:runs` takes its arms, sidecars and refused
  picks from it, and packages the folder to the same bytes as without one. The manifest's
  names and rules are as the engine's lead, who keeps the specification, settled them on 20
  November 2026: among them, the manifest's copies of the engine's revision, snapshot and
  clean tree are held to each view and to each run's own `run.json`, and sidecars are named in
  the order they are played. The adapter's own reading stays inside a run's folder too: a name
  that leaves it, and a link, are refused. Not yet: the adapter does not run the whole check
  itself before it packages, nothing acts on a package's visibility or licence, and the
  portable play package is the next round.
- **Run data is not in git.** `tools/adapt_run.py` reads the frozen run folders and writes
  one file per run under `out/runs/` (0.2 to 0.9 MB each), which is git-ignored.
  Only the adapter, the labels in `data/replays/` and a small synthetic fixture are committed
  (the user, 14 November 2026). The published page carries the runs the landing lists as
  files beside it, with `cards.json` and the cards' stills (`stills/`), which it fetches
  only when the landing first opens and, for a still, only when it comes near the screen.
  A run is loaded when it is first shown.
- **The format is the viewer's side of D154.** `schema/RUN_VIEW.md` fixes it. When the
  engine writes its own view file, the adapter is replaced and the view stays.

**The original two examples** were the page's whole list from Version 27 (17
November 2026; the user chose them for the page) until the landing: the gap-junction work
(its networks of a linear model, after Grodstein, Mathews and Levin (2026): 30 runs of the
engine, 16 in the Norton form and 14 as the preprint writes the model; and its tumour
tissue, below), and the GARD assembly (the engine's two development runs of the model
system, played in the tab's place).

- **What the page lists and publishes** is the cards' `listing`
  (`data/replays/cards.json`): the export publishes those experiments' runs, their parts
  and the runs the scene names (the planarian's loop, which the Cell view's flux reads),
  and the catalogue's overlay says nothing of listing. Its `doors` name the model systems'
  entries (GARD and the Cells vesicles, each with its own levels and clock). 112 runs are packaged in all, and all are published.
- **A run's parts.** A run's records for the quantity layers are in files of their own
  beside it, each under 1 MB, fetched when a layer is switched on. In the published page
  the parts of each run of an experiment whose overlay entry says `parts_together`
  (E07-v1, the turnover pre-screen, the linear networks, the secreted-species run and the
  test sheet, since 18 November 2026) are one file for the run, two where one would reach
  1 MB, fetched when the first of them is asked for. The export writes those files; the
  runs folder keeps one file a part. An address fetches only the run it shows, and the
  view keeps the four runs shown last.
- **A run's card** heads with what its experiment is ("Experiment", "Development run" or
  "Invented numbers") and its name, with its parts' doors, its runs, its chart and its
  words under it. On the landing a card keeps two facts of the record apart: its standing
  and its answer. A judged experiment whose answer is no is shown as exactly that. Each
  run says how it ended.
- **The run shown first** is the one the entry names (`opens.run`, an arm's name: Figure
  5a's seven-cell network), or the experiment's first run where it names none or that arm
  is not packaged. The runs stand at the card's head, under the experiment's name: a few
  are rows to press, many are a list to choose from, grouped by the sweep that holds them.
- **A quantity the experiment states** (a file beside the run, `schema/RUN_VIEW.md`)
  colours the cells where the entry opens its runs on it (`opens.record`), in its own unit,
  never converted, and is said to be the experiment's own and not a field of the engine.
- **Where an arm's files name no disc,** it is taken as the cells above the experiment's D
  threshold at the first record, and the replay says so.
- **Held back:** the W1 heredity pilot adapts (two runs), but the view draws every event
  as a replacement and the pilot's events are a cue in many cells at once. W1 stands on
  the landing as a card with no replay.
- **Runs written by the engine's own run-view writer** (`cells.run_view@1`, on main since
  050aa741, 16 November 2026) are kept small under `tests/engine-views/`, as fixtures for
  the adapter: eight small worlds written by main's writer at 89bd2ffb (`run-view-89bd2ffb/`,
  after the core seams pass's format items of d64fb664: kinds as words with the law under
  `laws`, each carried species with its own flux, a field reference only with its `unstated`
  entry, and a channel set's `factors`), the five before them at 050aa741 and b5d3faf0
  (`run-view-050aa741/`, `run-view-b5d3faf0/`), all made by `tools/make_engine_view_fixture.sh`
  through the engine's `scripts/run_detached.sh`; three as the development branch's fd008813
  wrote them (`run-view-fd008813/`); and the interim planarian loop as the writers at d7a11d5b
  and b08af640 wrote it from execution snapshots (copied from the engine's lead). The format
  keeps its name, so the adapter reads the older and the newer shape side by side, and every
  older view packages exactly as before (on 19 November 2026 all 585 run files were remade
  with the changed adapter, each the same bytes). What no small world shows is planted on
  copies of them from `tests/fixtures/run-view-made-up/`, which is made up and says so.
- **The planarian loop** (`planarian-loop`) is a development run of the engine with no
  verdict: FR-11's first looping run, one 2 s period of a subthreshold current train into
  the centre of seven planarian heredity cells, packaged to loop. It is listed under
  Development runs and shows no result. It is the first run on the page that the engine's
  own writer wrote.
- **Speed.** The timeline's speed lists the steps a run is offered, each in words. Every
  run is offered slowed a million, a thousand or four times, true speed, and four times
  faster; 15, 60 and 240 times faster are offered where the run still lasts five seconds
  of watching. A run under two minutes opens at true speed; a longer one at 60 times, or
  at 15 times where 60 is not offered. What flows keeps the replay's clock and is drawn by its speed as in the Cell view: at
  true speed and faster a stream as wide as its rate, slowed packets and then single
  beads, chevrons for the way; paused, everything stands.
- **A sweep's chart.** Where an experiment's summary (`cells.experiment_summary@1`, a file
  beside its runs that the overlay names) states a sweep (a parameter, its arms and each
  arm's readouts), the replay shows it as a chart: in a card of its own at the right of a
  wide window, and first in the experiment's card on a phone. The parameter runs along it
  (on a log scale where the values ask for one, said on the axis), each readout is a line
  of points, the arm shown is marked, and the experiment's own reference is drawn as dashed
  rings in the summary's words. Each arm is a button: a press, or Enter, shows that arm's
  run, and an arm with no packaged run says so. "The numbers as a table" gives the same
  numbers. Nothing is computed from them and no word judges them. `schema/RUN_VIEW.md` ("A
  sweep's chart") states the least a summary must hold; the adapter refuses one that holds
  less, with the reason. The gap-junction example states seven (Figures 3b, 5b, 5a and 8
  in the Norton form; 3b, 5b and 8 as written); the sweeps' card lists them, and choosing
  one shows a run of it: the run shown where that is one of its arms, else its first arm
  with a run. Checks also hold the chart on a made-up summary
  (`tests/engine-views/sweep-made-up/`).
- **The gap-junction example's tumour tissue** (added on 17 November 2026, redrawn on 18
  November; development work, not judged). Its card on the landing opens on it: the
  example's entry names the part (`opens.part`, one field: the sheet, Cells' own tissue of
  hexagons, since the user asked for it on 19 November 2026; the line until then), and an address that
  names a run, a record, layers, `part=` or `example=` opens its view without the landing.
  `src/lenses/tissue_line.js` draws each run's cells from straight above as the
  Experiments view draws a run's (`src/layers/sheet.js`), standing where its view places
  them, coloured by the miR200 minus Zeb mRNA its driver states beside the run
  (`criterion.json`) on a scale broken at the criterion's two thresholds, the tumour
  outlined (`tumor_cells`, as the summary states them), three dots in each cell for the
  switch's three concentrations as stated (µM), and between neighbours the junction, with
  what its route carried as the page's beads. The names are measured first and the
  tissues laid out to the room around them, so that no name meets another or lies on a
  cell. The line (`part=gap-junction-tissue-line`, `runs/dense-01/viewer`: D = 0, x2/2, x2
  and 2 x2, recorded densely) stands with each arm's whole run as a map beside it (left
  out on a phone), and a small door to the sheet. The sheet
  (`part=gap-junction-tissue-sheet`, `runs/sheet-01/viewer`, 9 by 9 cells, three to a
  row) is Cells' extension, not part of the replication: its caption says so in full over
  it, the words over the sheets say once that x2 is the line's threshold and what the
  dashed line between two sheets is (where its record places its own threshold), and the
  line stands under it, smaller, as the record the threshold comes from (folded away when
  every arm is in view). The clock follows the driver's stated changes
  (`src/replay/tissue_play.js`): each is held 2.2 s and named by its cell, the hours
  between pass fast, a play takes about a minute, and the timeline's marks are the
  changes, with the previous and next ones a press away; with less motion nothing plays
  by itself. A pressed cell is ringed and named with its state, and its panel charts it.
  The card opens on "What you are looking at": press play, then the note's own sentences,
  each linked to its source. The switch of the chosen cell (by default the tumour's edge
  cell of an arm in front) draws every saved record in the plane of its stated miR200 and
  Zeb mRNA, with the criterion's two lines and its three bands named; on a wide window it
  stands under the tissues where the room allows. The walk (`runs/ladder-01/viewer`, the
  ladder, with the line's four arms: fourteen couplings) gives for each coupling how many
  of the tumour's cells end E and the first record with every cell E, as the note's tables
  give them (`tissue.walk.points` in the overlay, held to the packaged states by a test),
  x2 marked; no run is fetched to draw it, and a point pressed brings its run into the
  line's rows. With every sheet in view the line keeps its x2 arm beside them. Under
  1024 px, where the bar's stamp is hidden or cut, the line's picture says "Development
  work, not judged." itself. The note's question stands as the line's head line on the
  picture where the room allows. A chosen cell's chart reads its own run's record at the
  clock (`src/replay/trace_reading.js`), the view's clock being the union of the runs'
  times.
  Only the arms in view and only what the picture draws are fetched (the voltages, gates
  and amounts are in files of their own). Checks: `node tools/check_tissue.mjs`
  (`CASE=wide|phone|reduced|play|sheet|layout`) and `tests/tissue_packages.test.mjs` (each
  packaged value's band is the driver's state; the transfers run down the gradient).
- **A development run and the test sheet of invented numbers stand apart** from the
  experiments, each in its own band of the landing: the engine's first run made for the
  viewer (one cell that secretes a species; no verdict), and a test sheet with invented
  numbers for the layers that no saved run feeds yet. The word "example" belongs to the
  landing's first band alone; the test sheet is "Invented numbers" wherever a visitor
  reads. See "Quantity layers".

To make them all (the second call adds the test sheet, from the fixture the run-fixture
tool writes):

```bash
npm run adapt:runs -- --evidence /mnt/workspaces/Cells
npm run adapt:runs -- --experiment example-sheet --root tests/fixtures/run-example --run invented-numbers
```

`data/replays/selection.json` lists the runs per experiment, and
`data/replays/overlay.json` holds each experiment's labels, plain lines and what it found,
with the record's line and its source.

## Quantity layers

The user, 15 November 2026: "explore how we can visually represent "invisible" things,
like electrostatic forces, voltage gradients … we want this modular and extendible and
connect to the Engine"; and of the ten ideas shown: "Lets do them all except wait with 8.
9. and 10." `schema/QUANTITY_LAYERS.md` fixes the rules, and
`docs/INVISIBLE_QUANTITIES.md` has the ideas.

- **A layer draws one quantity onto something the viewer already shows, from numbers a
  run saved.** A layer is a few lines of data (`data/layers/layers.json`), and a mark is
  one small module (`src/layers/marks/`). A new quantity with a known mark is data alone.
- **Never physics of the viewer's own.** A layer's numbers are a saved record, or one of
  four declared derivations (a difference, a rate, a charge, the two terms of the
  electrochemical potential), each shown as worked out by the viewer, with its inputs.
- **One layer on each visual channel,** and always a legend: the unit, the scale and
  what stands behind the numbers.

| Layer | Shows | On |
| --- | --- | --- |
| Membrane voltage | each cell's voltage as colour, and as height | the sheet |
| Voltage drops | the voltage across each junction, and how far its gate is open | the sheet's junctions |
| Coupling | each junction's own number as the run saves it (its conductance where it saves one, else its gate), as the width of a line joining its two cells: full width fully open, a faint hairline shut. A chosen cell's panel lists each of its junctions with its number | the sheet's junctions, or the cells of a small world |
| Push and pull on ions | for each ion, the push of its concentration difference, the pull of the voltage, and their sum | a close-up of a chosen cell's membrane |
| Membrane charge | the charge a stated piece of membrane holds | the same close-up |
| Transfers | what crosses each border, as beads: one bead is a stated number of molecules; the beads keep the replay's clock, which the timeline slows or makes faster, and what one bead stands for follows the speed | the sheet, or the tiles of a small world |
| Ion traffic | beads through a cell's channel populations, its pump and the membrane itself | the close-up |
| Energy dissipated | the rate of each dissipated-energy ledger, as a glow | borders, and spots on the cell |
| Secreted species | the amount of the run's secreted species, as a fog | cells, and the spaces outside them |

- **What a run did not save is said.** A layer that a run cannot feed is listed, switched
  off, with the reason.
- **A direction is declared, never guessed.** A run with the engine's own `view.json`
  beside its files is packaged from that view alone. A run without one is packaged with
  the viewer's table for the tissue family, whose convention the engine's side confirmed
  on 15 November 2026. The legend says which of the two stands behind a direction.
- **Two runs feed the newer layers today.** The engine's first development run for the
  viewer feeds the secreted species, the transfers and the glow. A test sheet of
  invented numbers, marked as such on the picture and in the legend ("Invented numbers ·
  no run of Cells' engine"), feeds ion traffic and a sheet's transfers until a saved run
  of a sheet carries those totals.
- **Flux in the Cell view** (published 16 November 2026). A Flux switch in the Cell
  view's legend, off as the page opens; a part shows its flux alone when the visitor
  chooses it; beads with bloom. A species with no run of its own shows illustration,
  marked "Illustration: not a run", of the form "direction only": pumps and secreted
  signals go the way the engine's own laws say (cited in `data/layers/flux.json`),
  channels, junctions and water are drawn both ways with none claimed, and fuel draws
  nothing. No textbook direction is drawn. At rest nothing flows. The cell's own drops, signals and close-up ions move as they always did: the
  picture's own motion, not a measured flow, as the legend says beside the switch; they
  hold still while any flux shows.
- **The planarian's own run** (17 November 2026). The planarian's cell type names its
  looping run (`cell_type.loop`): the engine's first, FR-11's interim planarian loop, a
  development run of the engine, not judged. The Cell view fetches it from the page's
  catalogue of runs and draws from it what the planarian's cell can show: its channels,
  its pump, its membrane itself and its six junctions, each from the run's own totals.
  The picture says what the run is, that it loops every 2 s of the cell's time, what is
  drawn (at true speed, streams as wide as their rates, with the widest's rate in ions a
  second; slowed, what one packet or bead stands for), and that the cell is the run's lumped
  `cell_3` under a prescribed current: not a measurement of a living cell. Water, secreted
  signals and fuel are not drawn from it, each with its reason. No illustration stands in
  while the run is on its way or cannot be had.
- **Speed is a slider, and slowing down is seen** (the user, 17 November 2026: "the speed
  does not change the anymation of the beads and arrows in flux"; "nice visual effects to
  show the speed at full speed, you wont see any individual ions"; "make the speed a slider
  with those two points 1/1000 and 1/...at 2/4 and 3/4"). The slider in the Flux legend
  slows what flows, from true speed to ten million times slower, marked at a thousandfold
  (half way) and a millionfold (three quarters). At true speed each lane is a glowing
  stream as wide as its rate, with no bead to count; slowed, it resolves into packets and
  then into single beads, fewer and slower the more it is slowed, each standing for a
  stated number of ions (1, 2 or 5 times a power of ten, never under one). Chevrons along
  each lane show the way it flows: each one flat, see-through mark a little paler than
  its lane, without a glow, so that it is not taken for an ion (the user, 17 November
  2026, of the first chevrons: they had a gap in them and were mixed up with ions); they
  stand where nothing may move. It is the same
  control that slows the flagellar motor. A looping run and the motor stop at true speed:
  nothing runs faster than life there. The address takes `slow=` (for example
  `slow=1000`). On the planarian's busiest lane, measured in the page: 1.0 packet a second
  crossing in 2.6 s at a thousandfold, 0.5 beads a second crossing in 4.1 s at a
  millionfold; before, every speed showed about 5 beads a second crossing in 1.6 s.
- **Not built yet:** the field between cells, the tension web and the wavefront.
  `docs/ENGINE_NEEDS_FOR_QUANTITY_LAYERS.md` lists what the layers ask of the engine,
  with the lead's answers.

## Origin of life

Choose **Cells vesicles** in the **Origin of life** group of the Scope switch, or open
`?entry=origin-vesicles`. The first replay follows amphiphile exchange and one daughter through shear divisions.
The second follows the osmotic lumen to threshold lysis. Its **Last intact state** and **Released state**
buttons show two observations at the same recorded time. **Plot** switches between footprint, intact lumen volume and tension. The **Membrane** and **Molecule** levels magnify
the illustrated bilayer and its molecular reference. The readout gives the run's own species, counts,
footprint, volume and tension. Both replays carry their development standing.

**Replay shear division** shows the membrane neck narrowing, the two daughters separating and
the labelled daughter that carries on. On **Membrane**, **Molecule traffic** lists the recorded
routes and their totals. Choose a route to jump to an event, then step through its arrivals or departures.
In the lysis replay, L1 leaves the membrane, L2 joins and leaves, and G crosses both ways between
pool and lumen. The link to the separate GARD replay opens a protocell with a recorded catalytic
matrix. Pick an interior arrow or expand **Catalytic strengths** to read its direction and coefficient.

GARD's assembly has a view of its own (`src/lenses/lineage.js`), on this page since 17
November 2026: choosing "GARD assembly" under "Origin of life" in the switch, or
`entry=gard` in the address, shows it in the first tab's place (`src/lenses/
lineage_entry.js` registers it through `src/ui/entry_views.js`). It also stands alone on
a page of its own (`node tools/build_view_page.mjs lineage`). The user asked for it as "a
new 'species' type", and to make it "visually amazing": "lets simulate the self assembly
of the lipids (visuall for now but maybe law later), and the different chemicals seeping
in and out, and the split"; and of the example: "yes lets play the marked example".

- **What is drawn.** A protocell in water (the user, 17 November 2026, of two slides of
  their own: "something that has the lipid assembly then small molecules moving in and
  out"): a closed shell of the run's lipids, a lipid for each molecule, whose head's form
  and colour say its type, heads to the water outside and inside, its near side
  see-through. First the founder gathers from the water. Then the run's molecules are seen
  moving in and out all the time it plays, at every speed: each one drawn coming in is a
  join of the run, each one going out a leave (one in N where the pace is high, and the
  legend says N). Inside, a lit network shows which of the types it holds speeds which,
  from the run's own table. At a fission the shell draws in at its waist into two
  protocells. Micelle and Cluster, the two earlier packings, stay on the card.
- **What comes from the run, and what is the picture's own.** The run gives which type
  joins or leaves and in what order, the composition, each fission and how it divides the
  molecules, the table of catalysis behind the lit links, and the supply's mix. Everything
  else is the picture's own: the shell and its glassy faces, how a lipid looks, moves and
  packs, the paths in and out, how often a molecule is drawn in flight, where the
  network's points stand, the water and every size. No law of Cells computes how the
  lipids move and pack, and the picture says so. The network never pulses with a join:
  the run does not record what helped one.
- **One timeline** counts fissions, molecule by molecule at its slow end. The levels are
  Molecules (the table of catalysis), One assembly, Population (not drawn yet) and
  Lineages.
- **It plays what GARD's entry names.** Since 17 November 2026, evening, that is the
  engine's own pair of runs (below). Before, and still in the checks, it played a scene
  of invented numbers once the first assembly has gathered,
  marked so at every level, on the picture, in the legend and in the bar: "Invented
  numbers · no run of Cells' engine". It stands still for a visitor who asks
  for less motion. The view opens on the protocell everywhere, on a phone and with less
  motion too (the user first had the cluster there, then left the choice to the
  coordinator on 17 November 2026); any of the three packings can be chosen on the card.
  Of the example the
  form of its law is named and no more ("the preprint's single-event form"): what the
  engine's decision says a form is for is said only of a real run of the engine.
- **When GARD's entry names runs of the engine** (`kind: development`), the view plays them
  instead of the example: two runs of one world, one of each form of the law, side by
  side under one clock on a wide screen, the engine's passive law (the pair-consistent
  form) first and the comparison model (the preprint's single-event form, D192) beside
  it, and one at a time with a switch on a phone. The mark says "Development run of the
  engine, not judged", the revision and the engine's model, and each run's panel gives
  every line the run states of its law's check and its ledger as the run writes it, with
  no gloss. `tools/adapt_assembly_run.py` writes those run files from the engine's run
  folders (`cells.assembly_lineages.run@1`) with the viewer's own reader (no numpy, no
  engine import, no interface ID held as a literal); going to new runs is a run of it,
  the entry's `runs` and the scene. Since 17 November 2026, evening, the entry names the
  engine's final pair (the set the engine's lead named final at GARD's merge into main,
  `1f9863ce`; its standing is read from the set's own `roles.json`): two files of about
  135 KB under `data/origin/`. Held by checks on a check-only scene made from the engine's
  set where that folder is at hand (the scenarios are skipped, and say so, where it is
  not); the example of invented numbers stays as the checks' own scene. Not right yet: the
  wide pair runs at about 55 frames a second with the page's cards shown (16.7 ms
  between frames with them hidden; the drawing's own frame is 6 to 7 ms); with a panel
  open the left run goes partly under the left card; the page of its own has no switch.
- **On the page** its levels are on the rail, its clock is the page's timeline (counting
  fissions; the space bar plays and pauses), and its card has the packing (Protocell,
  Micelle or Cluster) and the Composition and Similarity selects (on a phone, in the card its folded line opens).
  While it is shown, the bar's words stand on a fade of the page's own ground, at every
  width (no blur; it costs no frame: 16.7 ms between frames with it and without, by
  turns, at 1400 by 900 and 400 by 800). `entry=gard&scale=lineage`
  (the level, with no panel opened), `select=assembly:fission:<run>:<k>` and `play=1`
  work from the address; `time=` is not carried to it yet. The Cell view opened after it is the Cell view opened alone, and it
  comes back whole from a lost graphics process. Its checks are `tools/check_origin.mjs`
  (wide, dark, a short window, a phone, the address, and the pair of forms on a
  check-only scene that no page carries).
- **Frames** (the project's graphics card through Vulkan, 17 November 2026): every level
  holds 16.7 ms between frames at 1400 by 900 and at 400 by 800; a frame's own work is 2
  to 4 ms wide. Contact shade is used only at the Molecules level: at Lineages it cost
  about 1.5 ms and dropped the page just under 60 frames a second. The protocell, playing
  at half a fission a second: 16.6 to 16.7 ms between frames at both sizes, a frame's own
  work 3.8 to 4.2 ms (the micelle's 3.4 to 3.7 ms), 18 draw calls and 121,748 triangles
  at 1400 by 900; a test holds one protocell to 21 draws and 142,000 triangles.
- **GARD's status.** Its entry reads "Modelled", for comparison only (D197), since 17
  November 2026, evening: both parts of its build are on main (`PROGRESS.md`, "GARD's G1,
  part 2, on main"), and the engine's declarations list the stochastic assembly family
  `cells.assembly_lineages@1` with GARD's three laws and two lineage operators
  (`data/engine/declarations.json`, written at main `93fc8c2c`, the map's revision; they
  did so at `a16b2571`, `79d23cd5`, `b5d3faf0`, `4dda2285` and `1ca5eada` too). Declared is not qualified: its runs are
  development runs, not judged, and the page says so on every picture of them. The Engine
  map's part for GARD reads "Implemented and guarded" since the map's review at `4dda2285`,
  on its tests on main, with its standing first: development runs, not judged (D192,
  D197). Until
  that evening the entry read "Designed, not modelled" (`docs/GARD_DESIGN.md`, D192) and
  the page played a marked example. Cells' own origin-of-life engine, with
  laws from physical chemistry, is designed, its first choices settled by D199
  (`docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md`); its first laws (OL1, `cells.assembly_lineages@2`)
  landed on main on 18 November 2026, for development and not judged (`PROGRESS.md`), and
  the engine map draws them. The engine builds both forms of GARD's
  catalysis, and the view shows them side by side only for two real runs of the engine of
  one world (`schema/ASSEMBLY_RUN.md`); the user: "yes we'll wait for the real runs but
  great to have everything ready".

## The cell's resting look

The user chose it from a page of options (`docs/FLUX_AND_LOOK.md`, 15 November 2026).
Seven effects are on in the Cell view: studio reflections, filmic light, soft
translucency, contact shade, surface texture, a slow drift of the crowd, and a shimmer
on the membrane. The other three views are unchanged.

- **It is decoration, and says nothing.** Nothing in it moves with a direction, it stops
  while a layer shows motion, and it stops for a visitor who asks for reduced motion
  (`schema/QUANTITY_LAYERS.md`, rule 12).
- **A switch** ("Look": Rich or Plain) turns it off, and `look=plain` in the address
  opens the page without it. A device that cannot keep the picture moving smoothly sheds
  the costly effects in steps, and the page says which.
- **The glow of flux** is drawn against the depth the contact shade has already worked
  out, so the cell's parts are drawn once, not twice, while beads shine; the picture is
  the same to the pixel. In the plain look the glow still draws the parts in front of the
  beads itself. With the planarian's run and its glow in the rich look, a frame's own
  work on the project's graphics card (through Vulkan) was measured both ways by turns in
  one page, three times each, on a quiet machine (17 November 2026): 12.2 ms against
  14.1 ms with the parts drawn twice at 1400 by 900 (245 draw calls against 324), and
  8.7 ms against 9.9 ms in a window of a phone's size (400 by 800), where 60 frames a
  second hold either way. The card's own time hardly changes (4.8 ms against 4.9): what
  is saved is the page's work in sending the calls. An earlier single pair (12.6 ms
  against 20.1) was taken while other work ran and overstated the saving. A real phone
  was not measured.

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
| Endoplasmic reticulum | thin sheets close together, running on from the nuclear envelope, in two arms either side of the Golgi (in a plant cell, on the nucleus's inner side), and tubules through the cell | four thick ribbons, in the same arms |
| Ribosomes | free, in strings on a messenger, and on the rough endoplasmic reticulum: dots | two-subunit beads |
| Golgi apparatus | an animal cell: a ribbon of four stacks of six curved cisternae, each about 1.2 µm across, beside the nucleus round the centrosome, about 0.4 µm from the envelope; a plant cell: 40 small stacks in the thin cytoplasm by the membrane | an animal cell: one stack of five, its cis face about 1 µm from the envelope; a plant cell: 14 small stacks, enlarged |
| Centrosome | an animal cell only: two barrels of nine rods at right angles, 0.5 µm long, between the nucleus and the Golgi: scenery | the same, 0.9 µm long |
| Trafficking vesicles | eight: three from the point of the ER nearest the Golgi to its cis face, four from its trans face to the membrane, and one that meets it; their number and size are the picture's choice | the same |
| Membrane | a fine line (5 nm is far below one pixel) | a thick beaded band |
| Channels, pumps, junction channels | thousands of dots; shapes about 10 nm across in the close-up | a few blocks set in the membrane |
| ATP, ions, small molecules | dots and haze | a few beads and clusters |
| Space between cells | 40 nm wide, far below one pixel: a dotted line round the cut edge, and dots where three cells meet | a 0.9 µm gap with a few ions in it |
| Neighbouring cells | six faint glass cells against the cell's sides, 40 nm away, standing where the sheet's own cells stand: scenery | the same, 0.9 µm away |
| Cut-away top, and the plate under the layer | a dashed outline of the outer face that the cut removes, and a lined plate where a flatworm's skin rests on a basement membrane, which Cells does not model: scenery | the same |
| Layer beyond the sheet | five rings of cell outlines, fading: scenery | the same |
| Organ outline | a planarian's brain with its two nerve cords, drawn about 0.9 mm long: a placeholder, sizes indicative | the same |
| Organism outline | a planarian flatworm, drawn 10 mm long and 1.3 mm wide: a placeholder, sizes indicative | the same |

In "To scale" the close-up of the membrane is to scale as well: a bilayer about 4.5 nm
thick, a channel about 9 nm across, and a 10 nm scale bar. For comparison, the cells of
the E07 sheet are about 11 µm across by their declared volume (0.75 pL).

**A bacterium has both size modes**, by one rule for every cell: to scale, a part's size is
worked out in nanometres from the cell's own size, and drawn as a shape where it covers two
pixels at the cell's stop and as dots where it covers less. A cell 20 µm across draws every
molecule as dots; a bacterium draws its membranes, membrane proteins and ribosomes as
themselves (E. coli's stop holds about 2.4 nm a pixel, Syn3A's 0.75).

| Part | Drawn to scale as | In schematic mode |
| --- | --- | --- |
| Cell | its shape and size from its file | the same |
| Membrane | a band of its thickness at the cut: E. coli's 5.84 nm (Matias and others 2003), elsewhere a textbook 4.5 nm | the schematic band: about 5 times in E. coli, twice in Syn3A, near its size in M. pneumoniae |
| Wall and outer membrane (E. coli) | at the widths one paper measured: the wall's middle 15.4 nm and the outer membrane's 27.3 nm out, each a clear shell with a band of its thickness at the cut | clear shells 17.5 and 37.5 nm out, the picture's choice |
| Channels and pumps | the close-up's shapes: a channel 7.4 nm across and 10 nm long, a pump 8.4 nm across, one size each for the shapes, their spacing and the words; on the skin, rings and low domes as wide; how many is the picture's choice | a few, enlarged as the membrane is |
| Ribosomes | as measured: each subunit the ellipsoid of the same spread as its atoms, from the viewer's own measure of E. coli's ribosome (PDB 7K00; the whole 26 by 21 by 17 nm; 5MDZ within 1.2 nm), Syn3A and M. pneumoniae at E. coli's; 60% of the file's count, those below the cut | enlarged as the membrane's proteins are (about 6 times in E. coli, 2.4 in Syn3A, 1.2 in M. pneumoniae), so fewer, as many as fill the same share of the cell (19, 22 and 106); one stated value draws them at their own size instead |
| Crowd of proteins | Syn3A and M. pneumoniae: marks about 5 nm across, only in a slab 10 nm deep under the cut, at the density the file's count gives (Syn3A 2,709, M. pneumoniae 7,649); E. coli: none, since its sources disagree a hundredfold | none |
| Chromosome | a fine line in the same slab, the share of its length (0.34 nm a base pair) that the slab holds | a thread whose width and length are the picture's choice; its panel says what share it shows |
| Ions, fuel, small molecules | dots, each standing for many | enlarged beads |
| Close-up | true proportions along the cell's curve; no channel where the species has none; E. coli's whole envelope; the cut's band gives way to it, so the membrane is drawn once | the schematic close-up |

The crowd and the chromosome stand only in the slab because drawn whole they would hide the
cell: Syn3A's 77,028 protein molecules would cover its cut face more than six times over. The
card says in one short line what the mode shown draws, with a link, "What each mode draws", to
the cell's own panel, which says it in full for both modes; and the scale bar keeps "small
parts enlarged" in the schematic picture at every distance.

E. coli's envelope widths are numbers from two papers that are free to read but not open
access (Matias and others 2003; Berry and others 2010 for the larger spacing its fact
names), used with their citations under the user's rulings on such papers (D186 and D201 on
main). Taking the widths between the membranes' facing surfaces is the viewer's reading, and
the fact says so. The cell's to-scale envelope and the flagellar motor's closer view keep
different spacings for now (27.3 nm and 31 nm between the membranes' middles), each naming
the other.

The bacteria's molecular machines keep their place in each file but are left out of the
picture for now (the user, 17 November 2026): the barrel drawn for them stood among the
largest things in so small a cell. Each species' panel says so under "Left out of the
picture for now". The animal and plant cells keep theirs.

## Run it

```bash
cd visualizer
npm install                 # three.js 0.170.0 and esbuild, both pinned
npm run extract             # read the main checkout (or --repo PATH, or the one CELLS_ENGINE_REPO names), write data/architecture/architecture.scene.json
npm run import:proteins -- --inventory PATH/law_inventory_v2.json   # only when the inventory changes
python3 -I tools/extract_law_port.py --inventory PATH/inventory.json  # only when the law-port inventory (D211) changes
npm run serve               # http://127.0.0.1:4173/  (add -- --offline to load three.js locally)
npm test                    # the whole sweep: every test, every time (what a hand-over and a gate mean by "npm test, exit 0"); no browser needed
npm run test:quick          # the same files, with the rebuilds from saved downloads skipped where they passed before on the
                            # same inputs (tests/lib/test_cache.mjs; records in out/test-cache or CELLS_TEST_CACHE;
                            # CELLS_TEST_FORCE=1 runs them all); each skip says so, and the sweep's last lines count them
npm run check:input         # real clicks, drags and wheel in headless Chrome (picking, the cut-away, zoom, the atlas, its species sides and its links)
npm run check:species       # real clicks on the species switch: each species' levels, cell and wording, in every view; CASE=model: a model system in the switch, through every tab and back
npm run check:shelves       # real clicks on a species' own proteins: a marker, a family opening, closing, the legend and the list; the trail, the search, the map, the colours as drawn, a gathering, the cost of a frame, the doors (syn3a by default; planarian, nofiles, human, ecoli; stack holds any species with several shelves to its own file, SPECIES=thalecress by default; twins: a reviewed entry found by the twin of its gene that is not shown, SPECIES=xenopus)
npm run check:layers        # real clicks on a replay's quantity layers (zero, switch, closeup; flow and example for the newer layers)
                            # flow: RUN=secreted-species-dev-run--secreted-species-dev-run REFERENCE=tools/references/secreted-species-dev-run-0.4.json
                            # holds the page to numbers worked out from the run's own arrays (tools/reference_flow.py); example: RUN=example-sheet--invented-numbers
npm run check:look          # the Cell view's look: each effect, the switch, and the other views unchanged; `loss`: every view after a lost graphics process
npm run check:flux          # flux in the Cell view: nothing flows as the page opens, a chosen part, the switch (THEME, WIDTH and HEIGHT, SPECIES, MOVING=1, ADDRESS=1 set the case)
npm run check:origin        # the origin-of-life view on the page: playing, the levels, the timeline, the card, the legend's note (CASE=main|phone|address|pair)
npm run check:laws          # Laws star atlas and flight (CASE=stars|stars-phone), bridges (atlas|atlas-phone), shelves and other entrances (main|address|phone|gone|text)
npm run check:machine       # a machine's closer view: Look closer, the turn and its speed, a part's panel and door, the way back (CASE=main|address|reduced; WIDTH, HEIGHT, THEME, FRAMES=1)
npm run check:all           # every real-click check once, four at a time, with a table of what passed and summary.json (--only PATTERN, --jobs N, --out DIR, --list)
node tools/check_names.mjs --dirs BEFORE AFTER NAME...   # whether two runs of a scenario held the same checks (numbers set aside)
npm run serve -- --no-proteins   # the page as it is when the species' own proteins are not published beside it
npm run shot -- --out /tmp/shot.png --query "lens=engine&select=num.imex" --theme dark
npm run adapt:runs -- --evidence PATH   # make the replays under out/runs/ (not committed); PATH holds the evidence folders
npm run export              # out/cells-architecture.html, the page as an artifact wants it, and the list of run files to publish beside it
npm run stage -- --new out/publish-vN --old out/publish-vM   # the export laid out as the artifact is, and the uploads of what changed since the last publish
```

From another machine, forward the port (`ssh -L 4173:127.0.0.1:4173 host`) or open the
published artifact. `npm run export -- --standalone` writes one complete HTML file that
opens straight from disk.

The preview server sends a content policy close to the artifact frame's, so a load that
would be blocked when published is reported in the terminal while developing.

Every check that starts Chrome takes a place first (`tools/lib/browser_lock.mjs`). A place
is a share of the processors set aside for browser runs, whole cores: `CELLS_BROWSER_CPU`
names them (a list as `taskset` takes one; cores 12 to 15 with both their threads,
`12-15,28-31`, unless set) and `CELLS_BROWSER_SLOTS` says how many browsers run at once
(four unless set: one core each). A run beyond that waits its turn. Each run has its
profile on disk and not in memory-backed `/tmp`. On the project's machine the look check
takes 162 s on one core, 85 s on two and 49 s on four, so a suite goes fastest with four
browsers side by side, and one check alone goes fastest with all four cores
(`CELLS_BROWSER_SLOTS=1`). Chrome's software renderer pins its own
worker threads to the first processors by number, whatever the run is allowed, so the
lock looks at every thread of what a run started once a second and puts a process with a
thread elsewhere back. (A scope bound to a processor would hold them at once; it needs
the cpuset controller, which a user's session is not given on this machine.)

**Times and waits in the click checks** (19 November 2026). A check that holds a time (a
frame's or an update's milliseconds) is a measure (`tools/lib/measures.mjs`): its value and
bound go into the scenario's log and `summary.json`. Beside other browsers a measure over its
bound sends its scenario to the alone phase, run again after the others, where the bound is
held as a check; `summary.json`'s `sent_alone` gives both values. A count of work (draw
calls, triangles, files, bytes) is never a measure. The tissue, junctions and layers checks
wait on the page's own word (`viewer.busy()`, `src/core/busy.js`, through
`tools/lib/page_waits.mjs`), not on a fixed time; a pause left there is a window a check
watches over, and says so. The other check tools still pause by the clock.

**On the graphics card, where it is free.** The tools ask Chrome for the software
renderer. A run may draw on the machine's graphics card instead by starting Chrome
through `tools/chrome_gpu.sh`, which no tool needs changing for:
`CHROME=$PWD/tools/chrome_gpu.sh npm run check:all` (add `CELLS_GPU_LOG=FILE` and each
browser writes there which renderer it took). The engine's work on the card comes first,
by the rule its lead gave on 16 November 2026: each browser holds the engine's own lock
file shared for as long as it lives, so an engine job waits for the browsers to end and
none starts while a job holds the card; none starts while the engine's reservation flag
exists or another process is on the card. In each of those cases the wrapper starts
Chrome on the software renderer, as it was asked to. A run's record says which renderer
it used, and one gate or one before-and-after pair of pictures never mixes the two.

- **Through Vulkan, not OpenGL.** The wrapper reaches the card through ANGLE's Vulkan back
  end. Through its OpenGL back end (`CELLS_GPU_WAY=egl`) this machine's card now and then
  drew a wrong picture of a still page: after a frame with bloom, 18 of 40 pictures had
  holes where small solid parts are, though what the frame draws on the way (the solids'
  facing, the shade) was the same to the last count. Through Vulkan 40 of 40 were the
  picture at rest, as in software. The fault is that back end's on this machine, not the
  page's, and a check that compares pictures is not run through it.
- **A lost context.** Through Vulkan a fresh browser's first WebGL context is lost and
  restored about five seconds after it starts. Until 16 November 2026 the page then came
  back about a quarter darker, without its surroundings to reflect, and three of four
  look checks on the card had run on that picture (they compare pictures within one page,
  so they passed). The page now makes its surroundings again when a context comes back,
  as it must on a phone that puts the page away, and the look check loses a context on
  purpose to hold it, in software as on the card.
- **A lost graphics process** is more than a lost context, and it is what really happens
  to that first page (and to any visitor whose driver restarts): every 2D canvas comes
  back blank, also one that was asked to stay off the card, and three.js sends a texture
  again from the picture it holds. Until 17 November 2026 four textures were painted
  through a canvas and kept as the canvas: the Protein atlas's membranes then lost their
  beads and showed what lies under them, the Engine view lost its shade and its signs,
  the Cell view its dots, until the page was loaded again (Version 11 and earlier). A
  painted texture is now kept as its pixels (`src/core/painted.js`); a test holds that no
  other file makes a texture from a canvas, and `check_look.mjs loss` makes every view,
  loses the process once and holds each picture against the one before, to the last
  count in software and within one part in a million on the card (11 of 11 both ways on
  the mended code; 71 s on the card, about five minutes in software). On the code before
  the mend it fails for the same four pictures both ways (the Cell view, both sides of the
  Protein atlas, the Engine view): the fault was never the card's. Found by losing the
  process on purpose in every view; the lost-context check alone had not shown it. The
  two explainer pages that draw in 3D with textures of their own (Flux and Look; the Laws
  library's options) still paint them through canvases: they are records of decisions and
  are not kept up.
- **Compared with software on the whole suite** (16 November 2026, one clean copy of
  9e3e5538): 33 scenarios and 600 checks passed in software and through Vulkan, with the
  same count in every scenario. In software 32 scenarios passed in the full run; the
  thirty-third timed out at opening while other jobs shared the processors, and passed
  alone on a second run in 51 s, as it had earlier in the day. The suite took 62 minutes
  in software, two scenarios at a time, and 2.1 minutes on the card, four at a time.
- **From that revision a gate may run on the card through Vulkan,** and its record says
  so. The look check compares two pictures of a still page to the last count in software,
  and within one part in a million on a card.

## How it is built

```
checkout (src/, docs/) ──tools/extract_architecture.py──┐
data/architecture/overlay.json (curated, sourced) ──────┤
law inventory ──import──▶ data/proteins/ (snapshot) ────┼─▶ scene JSON ─▶ <cells-viewer> ─┬─▶ npm run serve
run outputs ──adapters (next)── run view ───────────────┘                                 └─▶ npm run export ─▶ artifact
```

| Path | Holds |
| --- | --- |
| `tools/extract_architecture.py`, `tools/lib/static_eval.py` | The extractor. Standard library only; parses source with `ast` and never imports `cells`. Since 17 November 2026 it takes the engine's operators (the composite's, and a family's own), laws, kinds and models from the engine's declarations manifest (`data/engine/declarations.json`, `cells.declarations@3`), and refuses one of another major, one written at another revision than the checkout read, or one from a tree with changes (`tests/engine_declarations.test.mjs`). From the source it still reads the files, their sizes and imports, the plan's gates and the shared-state table, which the manifest does not hold; each model module's `MODEL_ID`, only to place a declared model on its part; and four things of an operator that the manifest does not hold apart: `RK4`, `ACCEPTS_WRITES`, and which of its `provides` and `controls` are view fields and multiplied availabilities |
| `data/architecture/overlay.json` | The curated layer: layers, statuses with sources and dates, plain lines, planned parts, the capability map. Each part names the engine files it holds by pattern; the first part whose pattern matches a file takes it, so the catch-all parts stand last. It was last reviewed entry by entry against the record on 16 November 2026, after the landing of the engine's rework, at main 3b7f1cff |
| `data/architecture/architecture.scene.json` | The generated scene (committed, so changes show in diffs) |
| `tools/import_protein_inventory.py` | Makes the slim snapshot of the law inventory. It leaves out machine paths, Xenbase identifiers and every field the view does not show |
| `tools/lib/protein_atlas.py` | Turns the snapshot into the atlas's parts, and checks every law record against the checkout |
| `tools/adapt_run.py` | Turns a saved run folder into a replay file. Standard library only; reads the frozen evidence and never writes there |
| `tools/check_package.py` | Checks an experiment package (a run folder, with or without its manifest) before the viewer reads it, and says every problem with its code. Standard library only; it writes nothing and runs nothing from a package |
| `data/replays/` | For each experiment: labels, plain lines and what the record says it found, and the runs chosen for the page. (Not `data/runs/`: the repository ignores every folder of that name) |
| `docs/` | Reviews written for the lead: `PROTEIN_ATLAS_REVIEW.md` |
| `src/replay/`, `src/lenses/replay.js`, `src/ui/timeline.js` | Loading a replay, the Experiments view and its timeline |
| `data/proteins/` | `inventory.snapshot.json` (generated, do not edit), `overlay.json` (districts, plain lines and the shape drawn for each kind of unit) and the sources notice |
| `schema/RUN_VIEW.md` | What a run saves so it can be replayed (the consumer side of D154), and how the engine's own `view.json` is read |
| `schema/QUANTITY_LAYERS.md`, `data/layers/`, `src/layers/` | The quantity layers: their rules, their declarations, and the code (records, derivations, one module for each mark) |
| `schema/SPECIES*.md`, `data/species/`, `tools/lib/species.py` | What a species file holds, the shapes and parts the viewer can draw, and the reader that checks them |
| `tools/build_*_atlas.py`, `data/proteins/<species>/` | Each species' own proteins, rebuilt from saved public downloads that stay outside git |
| `src/core/look.js`, `passes.js`, `environment.js` | The Cell view's resting look and the finishing passes |
| `src/scene/model.js` | The scene format's reader and its structural checks |
| `tools/lib/npy_reader.py` | Reads a run's `.npz` and `.npy` without numpy: little-endian numbers and booleans, and since 17 November 2026 little-endian fixed-width text (`<U`), which the engine's relationship tables use for their ids; text in another byte order is refused, never misread (`tests/npy_reader.test.mjs`; the patch came from the engine's side, at the lead's offer) |
| `tools/build_view_page.mjs`, `src/standalone/` | A page that holds one view standing alone (the Laws library, the origin-of-life view): `node tools/build_view_page.mjs <view> --out FILE`. A view needs a mount module and a page file there; the page says on itself that it is a preview |
| `src/core/` | Stage (renderer, camera, picking), camera control, labels, theme, status materials |
| `src/lenses/` | `stack.js` (engine), `cell.js` and `cell_parts.js` (cell and scales), `proteins.js` and `protein_parts.js` (protein atlas) |
| `src/ui/` | `<cells-viewer>` and its parts: panel, legend, list |
| `src/page.html`, `src/page.css` | The page and its colour tokens, light and dark |
| `tools/lib/build_page.mjs`, `serve.mjs`, `export_page.mjs`, `screenshot.mjs` | One page builder for every delivery mode |
| `tests/`, `tools/check_input.mjs` | Browser-free checks, and a real-input check driven through Chrome's DevTools protocol |

Each group of the scene belongs to one lens, so the scene says where a part is shown.

**What comes from the code** and so cannot drift: the files in each part and their sizes,
which part uses which (imports), the plan's gates and the shared-state table; and, from the
engine's declarations manifest, the registered operators with their contract declarations
(requires, writes, provides, reads, conflicts) and the laws, kinds and models the engine
declares. A model identifier the manifest lists only among the older families is not drawn.
Every engine file belongs to exactly one part; the extractor warns if one does not. A module that declares two operators (an operator's next version beside it) stays the part of the first the manifest lists; each operator's panel quotes its own class's docstring. Code under `src/cells/legacy/` is left out of the map (the user, 17 November
2026: "no legacy code, it will be removed"; the engine's D196, decided the same day: older
code is a reference until the modular engine has learned from it, then it is dropped). A part whose files all
stand there is not drawn, a part with files of both kinds shows its active files, and the
build counts them apart ("262 of 262 engine files placed, 321 left out as legacy code").
The map's patterns are carried through the engine's source moves from the engine's own path
tables (`scripts/moves/*-table.json`), with a check that every file stands in the part it
stood in before (`tools/move_paths.py check`, which names a package file the move dissolved
as gone).

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

The visualizer session publishes its own artifacts (the user, 14 November 2026). An artifact
can be updated only from the account that published it, so the page may stand at more than
one link over time: `artifacts.json` records every link it has had and what each holds.
Nothing a publish needs is kept with a link or an account. The page and every file beside
it are made again from this folder (the run files from the frozen evidence, below), so the
page can be published to any link, or to a new one (the user, 18 November 2026).

1. In a clean copy of the branch's head, with the run files in place (`out/runs/`; "From a
   fresh checkout" below says how they are remade): `npm test`, then `npm run export`. It writes
   `out/cells-architecture.html` and `out/cells-architecture.files.json`, the list of the
   files to publish beside it: the runs (`runs/`), the species' own proteins
   (`proteins/<species>/`), the catalogue, the machines' shapes, the assembly's files, and
   the landing's cards and stills (`cards.json`, `stills/`). The files that hold a run's
   parts together are written by the export into `out/cells-architecture.runs/`. On 19
   November 2026 (Version 50) that is 467 files (169 MB with the page): 341 of 112 runs,
   78 of proteins, 22 shapes, 8 of the catalogue, 2 of the assembly, 1 machine, the cards
   and 14 stills.
2. `npm run stage -- --new out/publish-NAME` lays the export out as the artifact is, in a
   folder that is kept as the record of what was published, and writes the list of each
   upload (`tools/stage_publish.py`). A publish takes at most 255 files and 64 MB, and one
   version holds at most 511 files and 256 MB, so a full set goes up in several publishes
   to the same link; a later publish keeps the files it does not send.
   - To a link this folder published to last: add `--old` with the folder staged then, and
     only what changed is sent.
   - To a link whose staged folder is not at hand, or to a link first published long ago:
     save the Artifact tool's listing of the link's files, give it with `--remote`, and add
     `--remove`: every file is sent, and the first upload removes by name what the link
     still holds and the page no longer lists. Files published before and no longer
     listed stay on the artifact until they are removed by name, and count toward its 511.
   - `--remove` with `--old` does the same for a link this folder published to last. The
     removals always go up first, and no upload adds more new files than the link has room
     for before its own removals count, so the link never passes 511 files while the
     uploads land (Version 43 added 200 files to a link that held 360 and dropped 101).
   - A staged folder holds the page, its files and the staging's own `upload-N.json`, and
     nothing else: anything more would be read as published and no longer listed.
   - To a new link: nothing more; record the link in `artifacts.json`.
3. Publish the staged page to the link, one upload after another, with the staged folder as
   the uploads' root.
4. Read the page back from the link and compare it with the staged page (the service wraps
   it in a short head and tail of its own), list the link's files against the staged
   folder, and record the version in `artifacts.json`: its date, the engine revision the
   map reads, the gate it rests on, and what was looked at.
5. Tag the commit that records the version, `viewer-vNN` (an annotated tag; `viewer-v48`
   is the first, 19 November 2026), and push the tag. Before the publish, the staged page is
   also searched for a path of the build's machine (`/home/`, `/mnt/`, `/Users/`): the build
   refuses to write one, and the page-build test holds it.

**A site of its own.** The page will also be served at `cells.eidosoma.ai`, beside the
artifact. `docs/HOSTING_AND_API.md` (19 November 2026) reviews how, and how an API for the
page's data could come in stages; its section 9 records what the owner then decided: the site
is served from a container on a machine of the project's own, set up by the owner; releases
are marked by these tags; the site serves three.js and the fonts itself; and the API's only
user, for now, is the viewer. A tag marks the code and the record, not a folder that can be
rebuilt from the repository alone (the run files are made from the frozen evidence, below).
A site release is made from the same staged folder, which it only reads (section 10 of that
document):

- `node tools/stage_site.mjs --staged out/publish-vNN --site SITE --id vNN --compress --files out/cells-architecture.files.json`
  writes `SITE/r/vNN/` once: the page wrapped, its `root.html`, the files, three.js and the
  fonts (`vendor/fonts/`), `release.json` and compressed copies;
- `node tools/check_site.mjs --site SITE --id vNN` holds that a visit asks no other host;
- `node tools/stage_site.mjs --site SITE --id vNN --release` moves the pointer;
- the release is recorded in `artifacts.json` and the commit tagged, then `--retain 3 --remove`.

Each release's pages carry the site's own head: the About words' title and description,
`https://cells.eidosoma.ai/` as canonical (the one place `tools/stage_site.mjs` states the
site's address), link-preview tags with `share.jpg` (the tracked `data/site/share.jpg`, the
page's own scene with no words, made by `tools/make_share.mjs`), and structured data for the
site and its source code, whose one name is the credit's organisation (the site's
publisher, the code's author). Ahead of the page stands the About text as HTML for a reader
with no script (the source code linked, its licence not). A visitor with script does not
see it while the page loads (the owner's choice, 20 November 2026): a cover of the page's
own background, light or dark from the first paint, holds one ring in the window's middle
(still, slowly fading, where less motion is asked for) and a status that says the 3D map is
loading; the page puts the cover and the text away once it has drawn. If it has not drawn
in 20 seconds, the cover lets the About words through by its sheet alone, and the page
still puts them away when it draws. A reader with no script gets the words at once and no
cover (a style inside `<noscript>`); the site adds no script. Each release also holds `robots.txt` (every reader may read everything; `/r/` is
never closed), `sitemap.xml` and `llms.txt` (the site for an agent: the words, the views,
the cards with their levels and verdicts, the release's files by format, the contracts,
the source), which `--release` puts at the site's root with the pointer. The staging
refuses a page whose About words are not the tracked file's.

`deploy/` holds an example of the server's container; the owner sets the machine up.

A page published without the proteins' files draws the atlas as before and says that the
species' own proteins could not be loaded.

Published pages load three.js from cdnjs, the preferred host of the artifact frame's
allowlist; everything else is inside the page.

### From a fresh checkout

Everything that makes the page is in this folder on the branch `visualizer`, except two
things that are remade: `node_modules/`, and the replay files under `out/runs/`, which
stay out of git (112 runs in 585 files, 111 MB, on 19 November 2026; the export publishes
all 112 runs, in 341 files).

1. `npm install`
2. `npm run adapt:runs -- --evidence /mnt/workspaces/Cells` remakes `out/runs/` from the
   frozen evidence folders that `data/replays/selection.json` names, and
   `npm run adapt:runs -- --experiment example-sheet --root tests/fixtures/run-example --run invented-numbers`
   adds the sheet of invented numbers. Skip both when `out/runs/` is still on disk. On 18
   November 2026 the two calls remade all 585 files in under a minute, each one byte for
   byte the file the page was published from; on 19 November, for the landing, they did so
   again, and two files differ from those by design (`index.json` and the test sheet's
   run, whose words changed). What they need outside this folder is the
   engine's frozen evidence, which the repository does not hold.
3. `npm run extract -- --strict && npm test`. The extractor reads the main checkout, so
   the map states the revision main is at. A strict build fails where that revision is
   on no remote branch as last fetched (a commit not yet pushed, or amended before it
   was), so that the map never states a revision others cannot find. It also reads the
   engine's declarations manifest, `data/engine/declarations.json`, which must have been
   written at that same revision from a clean tree (`data/engine/README.md` says how); one of
   another revision is refused (`--declarations` names another file).
   The map's statuses are reviewed by hand at one revision of main. Once main has moved
   past it, build against a checkout of the reviewed revision (`--repo PATH`), so that the
   statuses and the stamp agree, until the map is reviewed again. The map was reviewed at
   main 3b7f1cff on 16 November 2026, again that evening at 050aa741, late that evening at
   1d86a192, on 17 November at df2b910b, after D188's first move at 6a5d509f, at 76846486
   the same day (main's changes were docs only), after seam F at f3b3f526, and with GARD's
   first part at 95de49de, after the combined landing at 7538b0cd, where it first read the
   engine's declarations manifest, with GARD's second part at a16b2571, and on 18 November at
   79d23cd5, after D198's retire batch and the feature-request lane's judged acceptances, and
   at b5d3faf0, after D188's second move and the landing of the origin-of-life engine's first
   laws, at 4dda2285, after the core-seams pass's first landings (seam F's laws as
   modules among them), on 19 November at 1ca5eada, after seams A, C and D, FR-2's first
   version and FR-8's stage 0, and on 20 November at 93fc8c2c, after FR-7's first closed loop,
   the step-doubled energy check and the mitochondria work's groundwork. V54 reads
   `cbe54031` (22 November). Its Engine map places all 292 active engine files across 274
   parts and 1,118 relations. One-gene expression and RNA release link to their declared
   operator in Laws. The measurement reader has its own entry. The respiration and gap
   junction entries show which comparisons their laws have undergone.
4. The real-click checks in headless Chrome: `npm run check:all` runs every scenario of
   `check:input`, `check:species`, `check:shelves`, `check:layers`, `check:look`,
   `check:flux`, `check:machine` and `check:laws` once, four at a time, and writes a log
   for each and `summary.json`. A scenario that holds a time bound (what a frame costs:
   `shelves-frame`) runs alone, after the others: beside three other browsers its measure
   says more of them than of the page. Each
   check says at its end whether the page's own font had arrived: with the stand-in, words
   run longer and cards stand taller, and a miss is read against that. `fetches` exports
   the page as the landing's cards list it and holds what each address fetches beside the
   page to `tools/references/fetches.json`; `landing-wide`, `landing-720`,
   `landing-phone`, `landing-narrow` and `landing-retry` hold the landing
   (`tools/check_landing.mjs`).
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
The branch was merged into main that day and is merged again from time to time, so it is
never rewritten: it is brought level with `git merge main`, and nothing is force-pushed.

## Next

1. **Events that are not replacements.** The W1 pilot's cue needs its own drawing; its
   two runs already adapt.
2. **More of each run.** The quantity layers show the junction gates and the amounts
   behind the push and pull on each ion, from files beside the run. The osmotic term is
   saved and not yet shown. The pilot's 70-minute arms need a smaller number type or
   fewer records to fit.
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

- **Flux speed.** An illustration (a species with no run) keeps beads at one pace. The
  slider's end, ten million times slower, makes a planarian bead two ions. The slider
  does not settle on its marks: let go one step (about a pixel) off its middle, it is
  slowed 930 or 1,150 times, and says so. `slow=` is read from the address and not
  written back to it. Where lanes crowd, the chevrons are drawn small to fit, and at a
  thousandfold they are faint beside the packets. A lane's direction is shown by chevrons
  along the lane: shown a comparison of four ways on 17 November 2026 (those chevrons, a
  tapered trail, an arrowhead at the lane's end, chevrons drawn in the stream), the user
  kept the chevrons for now. The other three stay in the code (`STYLES` in
  `src/layers/marks/flow.js`).
- **Flux in a bacterium drawn to scale.** Its beads and lanes are sized in pixels at the
  cell's stop, as that layout sizes its drops and signals, so that they can be seen; they
  are not to scale there, and the picture's words say what is drawn. Close to the
  membrane the cell's lanes are not drawn, and the picture says "Seen at the cell's stop:
  not drawn this close to the membrane". The suite runs E. coli and Syn3A at both stops.
- **The protocell.** With 40 to 80 molecules, each drawn as one lipid, only about a fifth
  to a quarter of each face is heads: the glassy faces, the picture's own, carry the
  shell. The composition ring crosses the protocell's equator. See-through overlaps are
  not sorted, and can look slightly uneven near the rim. The daughter that is let go
  stays about 2 s, so at half a fission a second one is nearly always on screen. On a
  phone at a fission the picture's line still touches the lower daughter. Its frame times
  were measured on the project's graphics card in a phone-sized window, not on a phone.
- The species' own proteins need the 3D stage: the no-WebGL list has the machines only.
- The List lists a family's members once it is open; the search in the trail finds them
  before.
- A mark that is a number (Syn3A's estimated copies in a cell) is a fact in the panel; it
  is not drawn.
- The molecular scale is one membrane patch with one channel and one pump.
- The planarian and its brain are sketches with indicative sizes. An open paper gives intact
  animals of the laboratory strain as 1 to 14 mm long (Lu and others 2025, CC BY 4.0); the
  width, the thickness and the brain's size are the picture's choice, so the outlines are
  of a planarian in general and the page labels both as placeholders. The
  protein atlas does name one, *Schmidtea mediterranea*, because its entries come from
  that species' database records.
- A species atlas repeats a family's candidates on every unit of that family (68 innexin
  candidates on each of three units), which makes the scene about twice as large. The
  no-WebGL list has no species switch.
- The shared table of families gives one signature for the sodium channels' beta
  subunits, IPR027098 (InterPro's "Sodium channel subunit beta-1/beta-3"). IPR000920
  ("Myelin P0 protein-related"), given beside it until 16 November 2026, swept in `Mpz`,
  `Mpzl1` to `Mpzl3`, `Jaml` and `Vsig1` in the mouse, and is no longer used. The beta-2
  and beta-4 subunits (`Scn2b`, `Scn4b`) carry only IPR000920 and immunoglobulin-like
  signatures, so a search by signature cannot tell them from those relatives: they are not
  listed, and each sodium channel unit's note names them and says why (`docs/MOUSE.md`).
- The protein atlas is as current as its inventory (12 November 2026). A law added to the
  engine since then is not in it; the extractor only checks that the recorded laws still
  exist, and the scene says that the inventory no longer covers every law. The landing of
  16 November 2026 added laws it has no unit for, a proton pump, an ATP-driven
  transporter and a proton leak among them. Its shapes are schematic, and where an
  auxiliary subunit sits is textbook knowledge, not a field of the inventory.
- The atlas's colours (sides, how known, essentiality) pass the palette check as tokens
  (`tests/palette.test.mjs`) and as drawn on the graphics card (`check_shelves.mjs
  colours`): every side stands at least 3 : 1 against the page in both themes. Colour is
  never the only cue: position and form say the side too. The ramps were sampled as drawn
  on Syn3A only.
- On a phone (a window under 760 px) the picture comes first: the bar keeps to one row
  (where its words would not fit, its switches tighten and the page's name is put out of
  sight, still read out); the Protein atlas's, the Laws library's and a model system's cards fold to one line that
  a press opens (a model system's line names it, with the rail's button beside it, or under
  it where the two would meet); opened, the origin-of-life view's card gives its switch,
  its word, its packing and its Composition and Similarity selects, and opening the
  legend folds it again; the example's mark finds its place clear of an opened card or
  rail, playing or still; the hint gives way to a timeline; the atlas's caveat stands at
  the head of its legend; its trail never cuts a word (the steps in its middle, the count
  and the words at a step's end give way first); and the map of the stack says a shelf's
  name when its bar is pressed. Two overlaps are meant: the open legend lies over the map
  (and over a timeline), and the opened search over the folded card's line. Not right
  there yet: at 360 by 780 the opened origin card covers the picture's line "No law of
  Cells computes…" until it is folded (the example's mark stands in the opened card); at
  exactly 760 px the cards do not fold; under 360 px the bar wraps to two rows; on a wide
  window the hint still shows through a timeline. Not a pixel of
  a window 760 px wide or more changed but the bar's band while the origin view is shown
  (13 wide pictures of the other views compared before and after with the canvas hidden,
  the cards and words to the pixel).
- "To scale" sizes are generic textbook values, as the table above says. No capability's
  dots are counted from a model's actual abundances yet; that would be a good use of the
  run view once replays exist.
- Statuses are as of the date in the top bar; the map does not update itself.
- In the plant cell a few of the Golgi's small stacks fall on the floor and the far
  walls and show only through the glass; the label points at the first, beside the
  nucleus. A cell's proportions (the review's option C: a larger animal nucleus, tighter
  cisternae, a smaller plant nucleus, a plant's ER as a network by the membrane) are not
  built: they need cited numbers first.
- With the engine's older code left out of the map, seven parts are no longer drawn in the
  Engine view (cell removal, membrane redistribution, fuel and mitochondria, injury and
  resealing, the charged-surface backend, the finite and spatial exterior, calcium and
  chemistry). Three capabilities' only engine code stands there (energy and mitochondria,
  calcium, the older families' injury law): the Cell view gives them the record's status
  all the same, since that code is in use until its replacement lands (the user: "we will
  replace all the legacy code with new code before removing those"). Thirteen of the
  protein inventory's 81 law records point into that code, and five units (U37, U38, U45,
  U46, U47) link to no engine part meanwhile.
- A model system's stand-in card (shown while its run file is read, or where it fails to
  load) is no longer seen by a browser check, since GARD's own view is registered: its
  words for a failed load are held by unit tests only (`tests/entries_page.test.mjs`).
- The checks' pictures are drawn by software WebGL or on the project machine's one graphics
  card, as each run's record says.
- The Laws library is read from the engine's declarations manifest written at main 93fc8c2c:
  61 pieces and 11 models. It is read again when a new manifest is copied in. The manifest
  states no level and no page yet, so the wall shows none; the 13 laws named in design notes
  are checked against their notes at that revision. The atlas's units that name no declared
  law (33 of 48) stay in the atlas; their laws, and U07's undeclared one, say what the law-port
  inventory of 17 November 2026 marks them (D211), and the table is made again only when that inventory changes. Seven
  of its rows' laws are declared since 1ca5eada, and their units open them through a door. The
  14 laws on the other 15 units that the inventory has no row for say that the declarations
  do not list them. At rest on a wide
  screen the model families' names are small; they read once a case is chosen.
- The Laws library's card scrolls beside its legend on a wide window under about 1000 px
  tall. The room it keeps clear on
  the left is worked out when a panel opens or closes, so it goes stale when a window is
  resized across 760 px. A model's box on the Engine view holds frames, not pieces, and
  has no door into the library.
- Frame rates are measured only on that card (an NVIDIA L4; 16 November 2026, a window of
  1400 by 900). A frame's own work, the page's handler with the card's drawing in it, took
  7.6 ms for E. coli's cell, 3.6 ms for its motor turning, and 11 ms for the planarian's
  cell in the rich look (6 ms in the plain one): room to spare at 60 frames a second.
  The frames themselves came at 60 a second through ANGLE's OpenGL back end, and at 22 to
  30 through its Vulkan back end while a card lay over the moving picture. The cause there
  was the cards' backdrop blur, made anew every frame for a backdrop that showed through
  by 6%. On the Laws library's preview with its panel open, on a quiet machine, the frames
  came 33 ms apart with the blur and 16.5 without; on the map's page, while other jobs
  shared the processors, 33 to 48 ms with it and 19 to 44 without, lower in six of eight
  pairs. It was removed that evening. So a frame rate read in a check says more of the
  browser and its back end than of the page's cost; the handler's time is the page's. Nothing is
  measured on a phone or a laptop; `frames=1` in the address shows a small readout of the
  frames the visitor's own device draws.
- A machine's closer view draws simple shapes from published sizes, not structures: no
  shape is taken from the Protein Data Bank yet. Of its sizes, many are the picture's
  choice (each says so), and those read from the Protein Data Bank's entries are the
  agent's own reading of the coordinates, not checked against the papers behind them.
- The machine is drawn upright at the foot it stands at, whatever way the foot faces: the
  cell is faded out while it shows, so the two are never seen together whole. A foot is
  hard to press while the cell is seen whole (it is a few pixels wide, under its thread);
  the machine's stop on the scale rail is the easy way in. Escape leaves the closer view
  only while the keyboard's focus is inside the viewer. On a phone the picture's statement
  may find no room beside the open sheet; the sheet then carries it.
- Slowed a thousand times, each of the motor's marks is sharp where a frame takes under
  0.83 s; at Subunits the rings' 34 like marks are sharp throughout at 60 frames a second
  and partly swept at 30. A device that draws a frame in more than 2 s turns the motor
  slower than life (the stage counts so long a frame as a tenth of a second). The rule
  never lets a mark jump (`schema/QUANTITY_LAYERS.md`, rule 13).
- On a phone the scale rail folds behind one button under the bar, and while a panel is
  open the view's card folds behind another; the legend's title and the look's switch then
  stand on the panel's top edge. The open legend is tall there and scrolls; a card that
  scrolls inside itself shows a shade along the edge that has more beyond it.
- On a phone every control is at least 44 px in its smaller dimension in the states that
  were measured (16 November 2026): the Cell view at rest and with its legend, rail, card
  or a panel open; a replay with its speed list and a cell's panel; the atlas's card. Not
  measured: links inside a panel's text, the List, the Engine view, and the atlas's shelves
  with a family open. The names on the picture are smaller (about 18 px); the List gives
  every part as a row to press.
- A name on the picture is not drawn where a card lies over it or where the window's edge
  would cut it, so a small window shows fewer names than a large one, and the List has
  them all. The chosen part's name is always drawn, and may stand over a card in a wide
  window; in a replay on a phone with a cell chosen it can stand under the timeline.
- On a phone the closed choosers of the experiment and the run show only the start of a
  long name (a press opens the list with every name whole); an opened run card over a
  panel covers the replay's statement of what a bead stands for until it is closed; and
  in Syn3A's shelves the caveat lies over the name of the set-apart group.
- Established (slate) and landed (blue) differ mainly in saturation. The four status hues
  pass the colour-blindness checks on both backgrounds; slate is a neutral and is not part
  of that check, so the panel and the list always name the status in words.
- The page has run locally under an approximation of the artifact frame's policy. A check
  inside the real frame is by eye.
- A capability marked qualified cites the pass it rests on, but a line-by-line review of
  each claim against the record is still owed before the map is shared outside the team.
