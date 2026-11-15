# E. coli in the viewer: the organism, its proteins, and what is not yet drawn

**Status: made by the visualizer session, 15 November 2026, for the user and the lead.**
The user: "look into adding e. coli and their proteins, it's now on the list for lead as
well". The project's record adds *Escherichia coli* K-12 as a **data-only organism**
(decision D179, 15 November 2026), for a proposed track whose first stage is bacterial
chemotaxis in a well-mixed cell. The track is on hold. **Nothing of E. coli is in the
engine:** no organism definition, no model, no run. The viewer shows it as proposed,
never as modelled.

Numbers are as built on 15 November 2026; the build prints them again.

| | |
| --- | --- |
| The species file | `data/species/ecoli.json`, in the form `schema/SPECIES.md` fixes (15 KB) |
| Its side of the atlas | `data/proteins/atlases/ecoli.json`: an entry for each of the 49 units (42 KB) |
| Its own proteins | `data/proteins/ecoli/`: `shelves.json` (143 KB), `proteins.tsv` (514 KB), `README.md` |
| The tool | `tools/build_ecoli_atlas.py`: `fetch`, `build`, `members`. Standard library only |
| The test | `tests/ecoli_atlas.test.mjs` |
| The downloads | `/mnt/datasets/Cells/ecoli/`, four folders, each with a `MANIFEST.json` |
| The analysis | `/mnt/workspaces/Cells/visualizer-ecoli-20261115-01/`: what the build counted |

## The strain and its proteome

- **Strain K-12.** UniProt's reference proteome UP000000625 (release 2026_04), taxon 83333.
  The genome record is GenBank U00096.3, of substrain MG1655: one circle of 4,641,652 base
  pairs. The proteome is of the same genome assembly.
- **4,403 proteins, every one with a reviewed entry**, for 4,403 genes. No entry of the
  proteome is unreviewed, so nothing is left out. Eleven entries describe a second or
  third form of their protein (4,415 sequences in all); one marker stands for each entry.
- **Only half state where they are.** 2,174 entries state a place in the cell; 2,229 do
  not. Of those, 106 carry a signal peptide and stand beyond the inner membrane; the
  other 2,123 stand on no shelf. Nothing is placed by guess.

## The shelves

The cell has two membranes, so it has a shelf for each, and a third for a membrane the
entry does not name.

| Shelf | Proteins | Outside | In | Inside | Side not known |
| --- | ---: | ---: | ---: | ---: | ---: |
| Cell inner membrane | 1,969 | 200 | 917 | 744 | 108 |
| Cell outer membrane | 137 | 37 | 43 | 10 | 47 |
| A membrane, not told which | 174 | 144 | 26 | 0 | 4 |
| On no shelf | 2,123 | | | | 2,123 |

- **How each side is known.** Stated by the entry: 1,958 (982 in, 754 inside, 222
  outside). Read from a feature of the entry, a signal peptide or a membrane-spanning
  segment: 163 (159 outside, 4 in). Not known: 2,282.
- **What stands behind the stated places:** an experiment for 778, a curator's inference
  for 609, no evidence given for 521 (older curated statements), a rule for 150, likeness
  to another protein for 116.

### The space between the two membranes

The contract had one case of a space between two membranes, the mitochondrion's. The
periplasm is the same case, and the file follows it:

- A protein **free in the periplasm** (or in the wall, which lies there) stands on the
  inner membrane's shelf, on its **outside**: 177.
- A protein **held at the inner membrane and facing the periplasm** stands there too, on
  the inner shelf's outside: 23.
- A protein **held at the outer membrane and facing the periplasm** stands on the outer
  membrane's shelf, on its **inside**: 10.
- A protein known only to lie **beyond the inner membrane** stands on the outside of the
  shelf of a membrane that is not named: 144.

The sentence proposed for the contract is under "Changes to the contracts" below.

### Three readings that are this file's own

Each is said in the file, with its count.

1. **"Cell membrane" is the inner membrane, except for a lipid anchor.** UniProt's
   vocabulary says the cell membrane is "known as the cell inner membrane in prokaryotes
   with 2 membranes", so the 94 proteins whose entry says "Cell membrane" stand on the
   inner shelf. The 40 lipid-anchored ones do not: no experiment stands behind any of
   those statements (a PROSITE or HAMAP rule for 19, a curator's inference for 18, no
   evidence for 3), and where an entry does tell the membrane of a lipid-anchored protein
   it names it ("Cell inner membrane" in 16 entries, "Cell outer membrane" in 38). They
   stand on the shelf of a membrane that is not named.
2. **A signal peptide says nothing about the outer membrane.** Every protein of the
   outer membrane has crossed the inner one. So a protein stated at the outer membrane
   with its face not told keeps "side not known" (47), signal peptide or not.
3. **The flagellum's basal body is on the inner shelf, side not known** (7 proteins). Its
   rod and rings begin at the inner membrane and reach through both; the entries do not
   say which part a protein is in.

## Families and districts

- **3,014 InterPro families hold 3,810 proteins;** 593 proteins have no family. The
  families are chosen by the planarian's and the human's rule, so a family has the same
  id and name in every species.
- **Most families have one member here:** 2,606 of one, 359 of two to four, 49 of five or
  more. A bacterium has few copies of a gene. The families of one are listed under
  `lone`, in 70 parts by shelf, district and side.
- **489 lines for 408 families:** a family has a line for each shelf it has members on,
  and each line carries `total`. The proteins with no family stand in 163 lines of parts.
- **Shared with the other species:** 372 families are also in the human file, 294 in the
  planarian's, 255 in both. The largest families here are bacterial (fimbrial adherence,
  24; WalR-like regulators, 17); of the largest, the major facilitator superfamily (16)
  and the short-chain dehydrogenases (10) are shared.
- **Nine districts,** the same as the other species': channels 65, transporters and pumps
  605, receptors and signalling 74, DNA, RNA and making proteins 867, protein handling
  148, cytoskeleton and movement 68, enzymes and metabolism 1,203, other functions 552,
  not classed 228.

## Chemotaxis and the assemblies

Two marks pick out the machines of the proposed track. Both come from permissive sources.

- **`chemotaxis`**, by UniProt's keyword: 22 proteins.
  - In the inner membrane: the receptors `tsr`, `tar`, `trg`, `tap` and `aer`; the
    motor's stator `motA`, `motB`; `fliL`, `fliO`.
  - Inside, in the cytoplasm: `cheA`, `cheW`, `cheY`, `cheZ`, `cheB`; the switch
    `fliG`, `fliN`; `fliJ`.
  - In the periplasm (inner shelf, outside): the binding proteins `dppA`, `mglB`, `rbsB`.
  - At the inner membrane, side not known: `fliM`. On no shelf: `cheR`, whose entry
    states no place.
- **`complex`**, by the Gene Ontology terms UniProt gives each entry:
  - flagellum, 34: the motor and switch, the export gate, the rod, hook and filament;
  - chemoreceptor array, 6: `cheA`, `cheW`, `cheR`, `tar`, `trg`, `tsr`;
  - ribosome 59, RNA polymerase 7, ATP synthase 8.
- `tap` and `aer` are receptors by the keyword, and the Gene Ontology does not put them
  in the array. The file follows its sources and does not add them.
- **"Show by" does not reach these marks yet.** The page offers a mark to show by only
  where a species has one marker for each protein. E. coli stands in families, so the
  marks are on the members, seen when a family is opened. To let the page light the
  markers that hold a marked protein, `shelves.json` also lists every marked protein
  with its line, shelf and side (`highlights`, 136 rows). The change the shelves view
  would need is under "Changes to the contracts".

## Its side of the atlas

- **None of the 49 units is found:** 43 "none found", 6 "nothing to look for". The units
  are machines of animal cells. The search is the one the other small species use: each
  unit's family signatures, looked for among the InterPro entries of the 4,403 proteins,
  with a control count among all bacteria.
- **One near miss, and a reading of this file's own.** `yfbK` carries the family signature
  of the calcium channel's alpha-2/delta subunits (IPR051173), which go with the channel
  and form none. No protein carries the signature of a subunit that forms the channel. So
  units U24 to U30 are "none found", their notes name `yfbK`, and it is listed under
  `extra`. The rule: a unit is found only where a protein carries the signature of a
  family that makes the machine itself. No other small species met this case.
- **`extra` lists 22 proteins that bear on what the atlas draws:** 15 of bacterial
  channel families (`kch`; `mscL`; `mscK`, `mscM`, `mscS`, `ybdG`, `ybiO`, `ynaI`;
  `clcA`, `clcB`, `yfeO`; `aqpZ`, `glpF`; `corA`, `zntB`), the four P-type ATPases
  (`copA`, `kdpB`, `mgtA`, `zntA`), the ATP synthase's catalytic head (`atpA`, `atpD`),
  and `yfbK`.
- `hslV` carries the signature of the proteasome's subunits; the species file says so
  under molecular machines.

## The organism as the viewer draws it

- **A rod 2.5 µm long and 1 µm across,** the picture's choice within the ranges one open
  paper gives (Volkmer and Heinemann 2011). Its second membrane and its wall are drawn
  as clear shells around the cell membrane.
- **6,800 ribosomes,** the low end of the range another open paper gives (6,800 to
  72,000 by phase of growth; Urich and others 2008), and a chromosome of 4,642 kbp.
- **Levels:** molecules and one cell. It lives as single cells.
- **Capabilities:** each of Cells' capabilities has a place in it or a reason it has
  none, in the same twenty entries as the other single cells. The channels and pumps of
  animal cells have no place; its own channels, its P-type ATPases and its ATP synthase
  do.

### What the cell view cannot draw yet

The cell view was not edited. These are what a picture of this cell lacks:

- **Flagella and fimbriae.** They are now in the species file as appendages, a general
  part of the contract (the user, 15 November 2026: "lets draw flagella, pili as a
  general feature"). The drawing is another agent's, in the cell lens, and is not there
  yet.
- **The chemoreceptor array.** The receptors and the proteins bound to them form a patch
  at the membrane. The view scatters membrane proteins evenly and has no part for a
  patch.
- **The periplasm as a place.** The two shells are drawn, but nothing stands between
  them, though 177 proteins are free there.
- **The two membranes as different.** Both shells look alike; the outer membrane's
  porins and the inner membrane's transporters are not told apart.

Each would be a general feature of the cell view (an appendage, a patch on a membrane, a
filled space between two shells), useful for any bacterium, not a part for E. coli alone.

## Appendages: flagella and fimbriae, as data

Written through the tool into `cell.parts.appendages`; each number is also a fact on the
species' card. Every source is an open paper under CC BY, saved with its record and its
full text. The build stops if a sentence it rests on is gone.

| | Flagella | Type 1 fimbriae |
| --- | --- | --- |
| `kind` | `flagellum` | `pilus` |
| How many on a cell | 1 to 5 | 200 to 500 |
| How long | 5 to 10 µm | up to 1 µm |
| How wide | 20 to 40 nm | 7 to 10 nm |
| Where | all over | all over (the picture's choice) |
| Starts at | the inner membrane | the outer membrane |

- **How many flagella.** One study of single swimming cells sorted its wild-type cells
  by the flagella each carried, from 1 to 5 (Mears and others 2014). Another paper takes
  an average of 3.4 for an E. coli cell (Schavemaker and Lynch 2022). The range written
  is the first; the average is in the fact. Larger figures were not found in a source
  read here, so none is written.
- **How long.** "Typically" 5 to 10 µm (Dvoriashyna and Lauga 2021); 7.5 µm by the one
  measurement that Schavemaker and Lynch use.
- **How wide: the sources disagree.** About 20 nm (Zhuang and Lo 2025, of bacterial
  flagella in general) and 40 nm (Dvoriashyna and Lauga 2021). The file gives 20 to
  40 nm, and its fact says that the two disagree.
- **Where.** All over the cell body (Dvoriashyna and Lauga 2021; UniProt's description
  of the organism says the same). The motor at the foot sits in the inner membrane:
  UniProt states FliF, MotA and MotB there.
- **Fimbriae.** 200 to 500 on a cell, up to 1 µm long, about 7 to 10 nm wide, standing
  out from the outer membrane: one paper's summary (Jahnke and others 2016, which worked
  with strains of MG1655). No source read here says where on the cell they stand, so
  "all over" is the picture's choice, and the level's note says so.
- **The F pilus does not belong on this cell.** It is made by the F plasmid. The strain
  as sequenced, MG1655, does not carry it: the proteome holds none of the plasmid's
  `tra` genes. One open paper describes "MG1655 F′" as a derivative "that carries the F
  conjugative plasmid and expresses F pili" (Rendueles and others 2012, PLoS Pathogens,
  CC BY; read at Europe PMC, not saved). A K-12 cell that carries F would be a later
  option of its own.
- **The base.** The flagellum's entry names `{"id": "flagellar-motor", "label":
  "Flagellar motor", "mark": "complex", "value": "flagellum"}`. The mark and the value
  are those of `shelves.json`, where 34 proteins carry them; the build and the test
  check it.

## For a closer view of the motor, later

Not built. This lists what such a view would have to draw, for a later decision. It is
not a design.

| Part, as the literature names it | Proteins among the 34 marked `complex: flagellum` | Rough size or number |
| --- | --- | --- |
| MS ring, in the inner membrane; part of the rotor | `fliF` | M ring about 30 nm across, S ring about 24.5 nm |
| C ring, on the cytoplasmic face of the MS ring; the rotor's switch | `fliG`, `fliM`, `fliN` | about 45 nm across |
| Stator units, around the rotor in the inner membrane | `motA`, `motB` | about 10 units at high load; "at least 11" at the most |
| Export gate, in the inner membrane | `flhA`, `flhB`, `fliO`, `fliP`, `fliQ`, `fliR` | |
| ATPase ring, in the cytoplasm | `fliH`, `fliI`, `fliJ` | 12 FliH to 6 FliI to 1 FliJ |
| Rod, the drive shaft | `flgB`, `flgC`, `flgF`, `flgG`, `fliE` | |
| L ring and P ring | `flgH` (stated at the outer membrane), `flgI` (in the periplasm) | together about 25 nm across |
| Hook, the universal joint | `flgE`; its length control `fliK` | about 50 nm long; about 100 to 120 copies of FlgE |
| Hook-associated proteins, and the filament's cap | `flgK`, `flgL`; `fliD` | about 10 copies of FliD |
| Filament | `fliC` | about 10,000 copies of FliC; sizes as above |
| Others the Gene Ontology puts in the flagellum | `cheY`, `cheZ`, `ycgR` (a brake), `fliL`, `flhE`, `lafU` | |

- **Where the sizes and numbers come from.** The rings' widths, the stator units at
  high load, the hook's copies and the ATPase ring are from Nakamura and Minamino 2019;
  the hook's length from Zhuang and Lo 2025; the largest number of stators and the copies
  of FliJ, FliD, FlgE and FliC in one E. coli flagellum from Schavemaker and Lynch 2022.
  All three are CC BY and saved.
- **Most were measured in *Salmonella*,** whose motor the reviews treat together with
  E. coli's: the rings' widths and the hook's 120 copies are stated for Salmonella.
- **Which protein makes which part** is by the names of the UniProt entries (rod, hook,
  L-ring, P-ring, M-ring, motor switch, hook-associated, flagellin), and by Nakamura and
  Minamino for the MS ring, the C ring and the ATPase ring.
- **Open structures to draw from** (accessions and titles as the Protein Data Bank's
  records give them, read on 15 November 2026; no structure was downloaded):
  - the whole basal body: 7CGO (motor-hook complex), 7NVG (basal body), both Salmonella;
  - LP ring: 7BGL, 7CBL (Salmonella); MS ring: 6SD4 (Salmonella FliF);
  - C ring with its switch: 8UMD, 8UOX (Salmonella); FliG alone: 1LKV, 3HJL (other bacteria);
  - stator: 6YKM, 6YKP (*Campylobacter jejuni* MotAB), 6YSL (*Bacillus subtilis* MotAB);
  - hook: 6K3I (Salmonella); filament: 1UCU (Salmonella), 7SN4 (E. coli O157:H7);
  - cap: 5H5V (E. coli FliD).
- **Only two of these are of E. coli,** and none is stated to be of K-12. A picture drawn
  from them shows the motor of the family, not this strain's own.
- **The Protein Data Bank's terms were not read for this note.** They are to be read and
  saved before anything is drawn from a structure.

## Sources and terms

Every source's terms were read and saved before anything was taken.

| Source | Terms | What was taken |
| --- | --- | --- |
| UniProt, release 2026_04 | CC BY 4.0 | The reviewed entries: names, genes, loci, lengths, keywords, stated places with their evidence, segments and signal peptides, InterPro entries and Gene Ontology terms; the proteome's record; the vocabulary of places; counts |
| InterPro 111.0 | CC0 1.0 | Names and types of entries, the tree of entries, the mapping to Gene Ontology terms |
| Gene Ontology, 2026-07-26 | CC BY 4.0 | Names of terms and the links between them |
| GenBank U00096.3 | "NCBI places no restrictions on the use or distribution of the GenBank data" | The record's title, length and topology. No sequence |
| Volkmer and Heinemann 2011, PLoS One 6:e23126 | CC BY | The cell's length, width and volume |
| Urich and others 2008, PLoS One 3:e2527 | CC BY | The range of ribosomes in a cell |
| Mears and others 2014, eLife 3:e01916 | CC BY | The flagella counted on single cells |
| Schavemaker and Lynch 2022, eLife 11:e77266 | CC BY | The average number of flagella and a flagellum's length; for the note, the stators and the copies of four proteins |
| Dvoriashyna and Lauga 2021, PLoS One 16:e0254551 | CC BY | Where the flagella stand, their length, one figure for their width |
| Zhuang and Lo 2025, Biomolecules 15:170 | CC BY | The other figure for the width; for the note, the hook's length |
| Jahnke and others 2016, Molecules 21:985 | CC BY | The fimbriae's number, length and width, and the membrane they stand on |
| Nakamura and Minamino 2019, Biomolecules 9:279 | CC BY | For the note only: the motor's rings, stator units, hook and ATPase ring |

The build stops if a saved page no longer states its terms as read, or if a paper's text
no longer holds a sentence a fact rests on.

## What rests on non-commercial or unlicensed sources

The project's rule (D173, 15 November 2026) sorts every source into three classes.
**Permissive** (CC BY, CC0, or a plain statement that no restriction is placed): values
and derived data may enter the repository, with attribution. **Non-commercial** (any
CC BY-NC licence, or a program given out for academic use only): analysis only.
**No stated terms**: nothing enters.

**Nothing was downloaded from a source of the last two classes, and no tool was run.**
The shelves do rest on results that UniProt gives out under its own terms and that tools
and rule systems of other owners computed. By the user's ruling of 15 November 2026 such
a value stands on the terms of the database it was read from, and the tool behind it is
named and counted; asked whether that holds for every species, the user said "yes it
holds for this open source project". It is the project's rule, not a legal opinion.

| Tool or rule system | Class | What rests on it, read through UniProt |
| --- | --- | --- |
| PROSITE (ProRule) | Non-commercial (CC BY-NC-ND 4.0) | 66 placements: 32 by the stated place, 11 by the statement that the protein spans the membrane, 47 by a side read from a signal peptide that a rule gives |
| TMHMM | Non-commercial (academic licence) | One of four methods behind UniProt's predicted segments. 191 placements: 2 read here from such segments, 189 statements of spanning and 8 stated places that rest on a sequence analysis |
| Phobius | Non-commercial (academic users only) | One of the four methods for segments and of the four for signal peptides: the placements counted under TMHMM and SignalP |
| SignalP | Non-commercial (academic licence) | One of four methods behind UniProt's predicted signal peptides. 99 placements, all sides read here from such a signal |
| TargetP | Non-commercial (academic licence) | One of the four methods for signal peptides: the 99 counted under SignalP |
| Memsat | No stated terms (terms not read: UniProt names no version or address) | One of the four methods for segments: the 191 counted under TMHMM |
| Predotar | No stated terms (terms not read: its page asks for a browser) | One of the four methods for signal peptides: the 99 counted under SignalP |

- A protein may be counted under more than one heading, so the parts add up to more
  than the placements.
- HAMAP's rules stand behind 138 placements. HAMAP is CC BY 4.0, permissive, and needs no
  listing; the file names it all the same.
- **The tool has no switch that holds these values back.** One was planned while the
  question stood whether the rule covers this species; the user said it does, so the
  placements are brought in as the human file brings them, and a switch would only be a
  second way to build the same files.
- **All seven are already in the register** of `tests/licence_classes.test.mjs` for
  another species (M. pneumoniae's line names the same seven). E. coli brings no tool the
  register has not seen.

Two databases of this organism were read for their terms and are **pointed to only**;
nothing is taken from either:

- **EcoCyc.** No open licence: its page on downloads says that access to the data files
  requires a paid subscription. It is the curated database of this strain's genes,
  proteins, pathways and regulation.
- **STEPdb.** No stated terms: its page says all datasets are freely available for
  download and states no terms of use. It records where each protein of the strain is
  found, which is what the shelves show; it would fill many of the 2,123 places that
  UniProt does not state. It stays a pointer until its terms are known.

The two pages are saved with the downloads. Neither is a source of the data files, so
the scene does not carry them.

## Changes to the contracts

None was made. These are proposed, as exact text.

1. **`schema/SPECIES_PROTEINS.md`, the opening rule.** For "A bacterium has one shelf,
   its cell membrane." read: "A bacterium with one membrane has one shelf, its cell
   membrane; one with two has a shelf for each."
2. **The same file, under "A curated proteome", a new rule:**
   "**A cell with two membranes of its own** (a bacterium with an inner and an outer
   membrane) has the shelves `inner`, `outer` and `membrane`, in that order. The
   cytoplasm is `inside` of `inner`; what is outside the cell is `outside` of `outer`.
   Of the space between the two membranes (the periplasm, and the wall that lies in it):
   a protein free in that space stands on `inner`, side `outside`, as a protein between
   the mitochondrion's two membranes stands on `mito`; a protein held at one of the two
   membranes and facing that space stands on that membrane's shelf, on the side that
   faces it, `outside` of `inner` or `inside` of `outer`. On `membrane`, `outside` is
   whatever lies beyond the inner membrane. The file counts these apart, under
   `between`."
3. **The same file, for marks in a catalogue of families.** "A catalogue in families may
   list, under `highlights`, each protein that carries a mark whose values pick out a
   machine, with the line it stands on (`mark`, `value`, `id`, `gene`, `kind`, `under`,
   `shelf`, `side`), so that the page can offer the mark to show by and light the
   markers that hold such a protein." The shelves view's `filterable()` returns nothing
   for a catalogue in families today; it would read `highlights` there.
4. **`schema/SPECIES_ATLAS.md`, under `finding`.** "`found` asks for a family that makes
   the machine itself. A protein that carries only the signature of an accessory family
   (a regulator, a subunit that forms no channel or pump by itself) does not make a unit
   found; the note names it."
5. **The scene's limit.** Two tests hold the shelves' summary in the scene under 40,000
   characters. It is 39,037 with E. coli (E. coli's part is 8,689, the human's 10,209), so
   a sixth species will not fit. Most of each part is the sources, with every `holds`,
   `licence` and `cite` in full: 7,634 of E. coli's characters, 8,569 of the human's. The
   counts, the shelves and the file names are 1,000 to 1,600 characters a species. The
   sources stand in each species' own `shelves.json` too, which the page fetches when the
   species is shown. The scene could keep each source's `name`, `class` and `through`
   alone and read the rest there: about 10,000 characters for five species.

## How to rebuild

```
python3 tools/build_ecoli_atlas.py fetch --datasets DATA   # the only step that uses the network
python3 tools/build_ecoli_atlas.py build --datasets DATA   # the same bytes every time
node --test tests/ecoli_atlas.test.mjs                      # set ECOLI_DATASETS elsewhere
```

DATA is the folder that holds every species' downloads. The build reads, beside E. coli's
own four folders, what the other species' tools saved there: UniProt's vocabulary and
help pages, InterPro's and the Gene Ontology's files, and the terms of the tools behind
UniProt's predictions.

**One thing to know about the tool.** It does not copy the shelves' machinery: it imports
`tools/build_human_atlas.py` for the placement, the families and the districts, and
`tools/build_mpneumoniae_atlas.py` for the families asked of every species, and gives
them E. coli's own table of places. A family therefore has one id in every species by
construction. The cost is that a change to either tool can change E. coli's files; the
byte-for-byte test shows it. A shared module under `tools/lib/` would be the cleaner
home, and is a change to files that are not this note's.
