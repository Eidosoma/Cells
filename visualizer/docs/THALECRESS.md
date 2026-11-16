# Thale cress in the viewer: a plant cell's shelves and parts, as data

**Status: made by the visualizer session, 15 November 2026, for the user and the lead.**
The user: "When the e.Coli is done then add two more serially, Fruit fly and Thale cress",
and of what a plant needs: "add features as needed to suport plants as well in the
vizialization that should be modular anyway". This note covers the data and the proposed
contract text. **The drawing of a plant cell's parts does not exist yet, so the species
must not be published before it does:** the cell view would draw an animal cell's
organelles in a box and nothing of the chloroplasts or the vacuole.

**Nothing of the plant is in the engine,** and the project's record names no model of it.

Numbers are as built on 15 November 2026; the build prints them again.

| | |
| --- | --- |
| The species file | `data/species/thalecress.json` (8 KB), with outlines in `data/species/shapes/thalecress.json` (5 KB) |
| Its side of the atlas | `data/proteins/atlases/thalecress.json`: an entry for each of the 49 units (26 KB) |
| Its own proteins | `data/proteins/thalecress/`: `shelves.json` (709 KB), `proteins.tsv` (2.7 MB), `README.md` |
| The tool | `tools/build_thalecress_atlas.py`: `fetch`, `build`, `members`. Standard library only |
| The test | `tests/thalecress_atlas.test.mjs` |
| The downloads | `/mnt/datasets/Cells/thalecress/`, two folders, each with a `MANIFEST.json` |
| The analysis | `/mnt/workspaces/Cells/visualizer-thalecress-20261115-01/`: what the build counted |

## The proteome, and what one marker stands for

- **UniProt's reference proteome UP000006548** (release 2026_04), *Arabidopsis thaliana*,
  taxon 3702: **39,144 entries for 27,368 genes.** 16,217 entries are reviewed and 22,927
  unreviewed.
- **One marker for each gene: 27,368 proteins,** by UniProt's own gene-by-gene set, as for
  the fruit fly. 16,212 have a reviewed entry and 11,156 an unreviewed one; the mark
  `reviewed` says which.
- **The numbers do not argue otherwise.** The other 11,776 entries are further forms of
  the same genes, counted in the mark `entries` by the Araport gene UniProt gives each
  entry. Unlike the fly, most markers here are curated: 59 in 100.

## How sure the places are

| What stands behind the protein's place | Reviewed entries | Unreviewed entries |
| --- | ---: | ---: |
| Stated, on an experiment | 3,315 | 0 |
| Stated, by likeness to another protein | 2,571 | 0 |
| Stated, by a curator's inference | 2,709 | 0 |
| Stated, with no evidence given | 485 | 0 |
| Stated, by a rule | 1,039 | 1,712 |
| Predicted from a segment or a signal peptide | 385 | 1,624 |
| Not known | 5,708 | 7,820 |

- In all: stated 11,831, predicted 2,009, not known 13,528. An experiment stands behind
  3,315 places of 27,368: 12 in 100.

## A plant cell's shelves

Nine shelves: the animal cell's six, and three for membranes an animal cell lacks.

| Shelf | Proteins | Outside | In | Inside | Side not known |
| --- | ---: | ---: | ---: | ---: | ---: |
| Cell membrane | 4,598 | 1,712 | 807 | 1,795 | 284 |
| Endoplasmic reticulum | 554 | 3 | 423 | 81 | 47 |
| Mitochondrion | 837 | 25 | 135 | 99 | 578 |
| **Plastid envelope** | 1,251 | 3 | 200 | 248 | 800 |
| **Thylakoid membrane** | 214 | 14 | 106 | 59 | 35 |
| **Vacuole membrane** | 198 | 0 | 108 | 54 | 36 |
| Nucleus | 3,794 | 0 | 25 | 3,717 | 52 |
| Other membranes | 831 | 23 | 474 | 13 | 321 |
| A membrane, not told which | 3,809 | 1,057 | 2,644 | 15 | 93 |
| On no shelf | 11,282 | | | | 11,282 |

- **Which membranes have a shelf of their own, and why.** The plastid: 1,251 proteins
  state a place in it, more than the mitochondrion's 837. The thylakoid membrane, inside
  the plastid: 214, and it is a membrane of its own with a space of its own (its lumen).
  The vacuole's membrane: 198. Each is read as one membrane. The Golgi, endosomes,
  peroxisomes and the rest stay on "Other membranes", as for the animal cells.
- **The plastid has two levels.** Its envelope has two membranes, which stand as one
  shelf, as the contract allows where the data does not always tell them apart (133
  proteins are stated at "the chloroplast's membrane" with no word on which).
  - In either envelope membrane: 200. Free in the stroma, or within the plastid by a
    narrower word: 248 (on the inside). On the envelope's cytoplasmic face: 3.
  - Stated to be in the chloroplast with no part of it named: 800. They stand beside the
    envelope's shelf with the side not known, as a protein stated to be "in the
    mitochondrion" does for the animal cells.
  - In the thylakoid membrane: 106. In its lumen: 59. Held at the thylakoid membrane and
    facing the stroma: 14 (on the outside). At the thylakoid, side not known: 35.
- **The vacuole:** in its membrane 108, inside it 54, side not known 36.
- **The wall and the space outside.** A protein of the wall (266) or of the space outside
  the cell membrane, the apoplast (187), stands on the cell membrane's shelf, outside, as
  a secreted protein does. Its mark `where` names the wall.
- **What joins a plant's cells.** Not gap junctions: plasmodesmata, channels lined by the
  cell membrane that cross the wall (UniProt's vocabulary). 32 proteins are stated to be
  there. They stand on the cell membrane's shelf; the vocabulary files the plasmodesma
  under cell junctions, as it does a gap junction.
- **A transit peptide is not read.** It sends a protein into a plastid or a
  mitochondrion. Where a curator states such a place on a predicted transit peptide, the
  place is stated; nothing is placed here from the peptide alone.

## Families and districts

- **4,699 InterPro families hold 18,668 proteins;** 8,700 proteins have no family. 2,037
  families of one (under `lone`, 153 parts), 1,729 of two to four, 933 of five or more.
  4,110 lines for 2,662 families, each with `total`; 666 lines of parts.
- The largest: cytochromes P450 (225), a family of pentatricopeptide-repeat proteins
  (205), F-box components (165).
- **Shared with the other species,** with the same id and name: 2,626 families are also
  in the human file, 2,397 in the fly's, 2,316 in both.
- **The nine districts are the other species' own:** channels 173, transporters and
  pumps 1,215, receptors and signalling 1,711, DNA, RNA and making proteins 4,921,
  protein handling 2,355, cytoskeleton and movement 440, enzymes and metabolism 4,445,
  other functions 3,354, not classed 54. The districts' terms were chosen for animal
  cells: photosynthesis and the wall have no district of their own and fall under those
  named. A plant district would be a change to every species' file.

## Its side of the atlas

- **5 of the 49 units are found, 38 are not, 6 have nothing to look for.** 19 proteins
  are listed, all with reviewed entries.
- **Found:** the plasma-membrane calcium pumps' family (U40: ten ACA proteins), the
  store's calcium pump (U41: `ECA3`), the chloride cotransporters (U44, U45: `CCC1`), and
  the mitochondrial uniporter with its regulator (U47: `MCU1` to `MCU6`, `MICU`).
- **Not found:** every voltage-gated channel family of the inventory, the gap junctions,
  the sodium-potassium pump, the exchanger and the store's release channels.
- **No "different family" is given.** The inventory's table names a second family for
  one machine only, the innexins for gap junctions, and a plant has none. A plant does
  have channels and pumps of its own families (its proton pump `AHA1` stands in the cell
  membrane's shelf), but no unit of the inventory stands for them, and saying that a
  plant "builds the same machine from another family" would need a source for each
  machine. The units' notes say only what the search found; the gap junctions' notes add
  the plasmodesmata, from UniProt's vocabulary.

## The cell's parts, as data

`cell.parts` of the species file, each number a fact of the card with its source:

| Part | As written | From |
| --- | --- | --- |
| Wall | `"wall": true`, `"wall_nm": 150` | 150 nm thick on average |
| Chloroplasts | `organelles` names `chloroplasts`; `organelle_sizes.chloroplasts`: `count` 100, `volume_fl` 93, `across_um` 5.6 | 100 in a palisade cell, 93 fL each; 5.6 µm is the width of a sphere of that volume |
| Vacuole | `organelles` names `vacuole`; `organelle_sizes.vacuole`: `share` 0.84 | 84% of a leaf's cellular volume |
| Nucleus, ER, Golgi, mitochondria | as for an animal cell | |

All from one open paper, a quantitative atlas of the Arabidopsis leaf (Tolleter and
others 2024, Quantitative Plant Biology, CC BY), saved with its record and full text.

- **The cell is a box:** 47 µm across (the paper takes a palisade cell as a cylinder of
  radius 23.7 µm) and 45 µm high, the picture's choice of the height at which such a box
  holds the paper's 100 picolitres. An animal cell here is about 20 µm across.
- **What the cell view draws for these today: nothing.** The cell lens knows `er`,
  `golgi` and `mitochondria`; it ignores `chloroplasts`, `vacuole`, `organelle_sizes` and
  `wall_nm`. It would draw the box, a wall as a clear shell, a nucleus and an animal
  cell's organelles. That picture would be wrong for a plant, so the species waits for
  the drawing.

## Levels and outlines

- **Five levels:** molecules, one cell, tissue, leaf, whole plant. The tissue is the
  sheet Cells simulates, which stands for no tissue of the plant.
- **The organ is a leaf,** the body a rosette of eight leaves seen from above: rough
  placeholders. The leaf is 17 mm by 9 mm, the picture's choice of a blade whose area is
  near the paper's reference leaf (121 mm²). The number of leaves and the rosette's width
  are the picture's choice; the paper's three-week-old rosette has 29 leaves. No stem,
  flower or root is drawn.
- **`modelled` is `generic`,** the only state of the three that is not false: no model
  and no proposal to model the plant is on record (main names it only as a benchmark for
  gene networks). Its text says that Cells' laws name the machines of animal cells and
  that no plant cell is modelled. If a fourth state, "data only", is wanted for a species
  whose cell Cells' generic cell does not fit, that is a change to the contract.

## Sources and terms

| Source | Terms | What was taken |
| --- | --- | --- |
| UniProt, release 2026_04 | CC BY 4.0 | Every entry of the proteome with its places and their evidence, its features, its InterPro entries and Gene Ontology terms, its Araport gene; the gene-by-gene set (names of entries only); the vocabulary's words on plasmodesmata |
| InterPro 111.0 | CC0 1.0 | Names and types of entries, the tree, the mapping to Gene Ontology terms |
| Gene Ontology, 2026-07-26 | CC BY 4.0 | Names of terms and the links between them |
| Tolleter and others 2024, Quant Plant Biol | CC BY | The leaf cell's volume and width, the chloroplasts' number and volume, the vacuole's share, the wall's thickness, the leaf's area and the rosette's leaves |

## What rests on non-commercial or unlicensed sources

The project's rule (D173, 15 November 2026) sorts every source into three classes.
**Permissive** (CC BY, CC0, or a plain statement that no restriction is placed): values
and derived data may enter the repository, with attribution. **Non-commercial** (any
CC BY-NC licence, or a program given out for academic use only): analysis only.
**No stated terms**: nothing enters.

**Nothing was downloaded from a source of the last two classes, and no tool was run.**
The shelves rest on results that UniProt gives out under its own terms and that tools
and rule systems computed. By the user's ruling of 15 November 2026 such a value stands
on the terms of the database it was read from, and the tool behind it is named and
counted. It is the project's rule, not a legal opinion.

| Tool or rule system | Class | Placements that rest on it alone |
| --- | --- | --- |
| ARBA, UniRule (RuleBase) and PIR's rules, UniProt's own | Permissive (UniProt's, CC BY 4.0) | 1,818, 171 and 23 |
| HAMAP rules | Permissive (CC BY 4.0) | 88 |
| PROSITE rules (ProRule) | Non-commercial (CC BY-NC-ND 4.0) | 894 |
| SignalP | Non-commercial (academic licence) | 855 sides read from a signal peptide that an unreviewed entry gives, the program named on each; and one of four methods behind the 394 below |
| Phobius | Non-commercial (academic users only) | 767 sides read from segments that an unreviewed entry gives, the program named on each; and one of the methods behind the 854 and the 394 below |
| TMHMM | Non-commercial (academic licence) | One of four methods behind the predicted segments of reviewed entries: 854 placements |
| TargetP | Non-commercial (academic licence) | One of four methods behind the predicted signal peptides of reviewed entries: 394 placements |
| Memsat | No stated terms (terms not read) | One of the four methods for segments: the 854 |
| Predotar | No stated terms (terms not read) | One of the four methods for signal peptides: the 394 |
| big-PI | No stated terms (its page gives none) | 56 anchors stated on a sequence analysis alone |

- **All eight tools that are not permissive are already in the register** (the fly's and
  the human's lines name the same eight).
- **One tool is new and is not entered: MitoFates.** 125 places are stated by a curator
  on a sequence analysis for which the entry names no program. In 79 of them the entry's
  transit peptide is given by sequence analysis alone (63 chloroplast, 15 mitochondrion,
  1 peroxisome), and UniProt's help names three programs for predicted transit peptides:
  MitoFates, Predotar and TargetP. Predotar and TargetP are in the register; MitoFates
  is in no species' line, and its terms were not read. The file counts these 125 under
  UniProt's own entry, as the human's file does for the same kind of statement, and
  names no new source. Whether MitoFates is to be listed is the user's to say.
- **TAIR, the plant's own database, is not used and its terms were not read.** Its pages
  refused the tool (HTTP 403 on every address tried), so no class is given from them:
  No stated terms on record. Nothing is taken from TAIR; the genes that tie a gene's
  entries together are the Araport identifiers UniProt gives its entries.

## Readings that are this file's own

1. The fly's rule for the catalogue: one marker for each gene, by UniProt's set.
2. Three new shelves, and the plastid's envelope as one shelf for its two membranes.
3. A protein between the envelope's two membranes, by a stated face, is `in` the
   envelope: the shelf stands for both membranes. Four proteins stated to be in the
   space between them, with no face, have their side not known.
4. The wall, the apoplast and the plasmodesmata on the cell membrane's shelf.
5. A vacuolar protein with a signal peptide and no stated side is inside the vacuole,
   since the vacuole lies along the secretory pathway.
6. One entry states the periplasm, which a plant cell does not have; it is passed over.
7. `modelled` is `generic`; no `different family`; the cell a square box.

## Changes to the contracts

One was made, in `schema/SPECIES_SHAPES.md`, because a test holds the species reader's
words to that file: the row for `organelles` now names `chloroplasts` and `vacuole`,
and two rows were added, `organelle_sizes` and `wall_nm`. The rest is proposed.

**`schema/SPECIES_PROTEINS.md`, under "A curated proteome", a new rule:**

"**A plant cell has three shelves more:** `plastid` (the plastid's envelope), `thylakoid`
(the thylakoid membrane) and `vacuole` (the vacuole's membrane), after `mito` and before
`nucleus`. A membrane has a shelf of its own where enough proteins stand on it to be read
as one; the plant's other membranes stay on `other`.
- The plastid's envelope has two membranes, which stand as one shelf: a protein in
  either, or held between them, is `in`; the stroma is `inside`; the envelope's
  cytoplasmic face is `outside`. A protein stated to be in the plastid with no part of it
  named stands beside this shelf, side `not known`.
- The thylakoid membrane lies within the stroma: its lumen is `inside`, the stroma
  `outside`. A protein free in the stroma stands on `plastid`, side `inside`; a protein
  held at the thylakoid membrane and facing the stroma stands on `thylakoid`, side
  `outside`.
- The vacuole is `inside` of `vacuole`; its membrane's cytoplasmic face is `outside`.
- A protein of the cell wall, or of the space outside the cell membrane, stands on
  `cell`, side `outside`, with the wall in its mark `where`. A protein of the
  plasmodesmata, which join a plant's cells, stands on `cell`.
- The file counts these apart, under `plant`."

**`schema/SPECIES.md`, the rule on `cell.parts`:** for "the organelles of an animal cell"
read "the organelles it holds (an animal cell's `er`, `golgi` and `mitochondria`; a plant
cell's `chloroplasts` and `vacuole` beside them)", and add: "`organelle_sizes` gives, for
an organelle the cell holds, how many there are (`count`), how large each is (`volume_fl`,
`across_um`) or what share of the cell's volume it fills (`share`), each a number or a
range of two with the keys of its sources; `wall_nm` gives a wall's thickness. Each is a
fact of the card as well. An organelle the viewer cannot draw yet is still data: the page
says that it is not drawn."

**The species reader, `tools/lib/species.py`:** it now takes the two organelle words,
`organelle_sizes` and `wall_nm`, with their fields checked. A cell with a nucleus whose
file names no organelles still holds the animal three, not the plant's.

## How to rebuild

```
python3 tools/build_thalecress_atlas.py fetch --datasets DATA   # the only step that uses the network
python3 tools/build_thalecress_atlas.py build --datasets DATA   # the same bytes every time
node --test tests/thalecress_atlas.test.mjs                      # set THALECRESS_DATASETS elsewhere
```

Since 16 November 2026 the tool uses one shared module, `tools/lib/proteome_shelves.py`,
for the reading of entries and the catalogue, the shelves' machinery, the download step
and the papers' checks; it reads the units' families from the M. pneumoniae tool's
table. What is the plant's own stays here: the plant cell built on the animal cell, the
plasmodesma sentence, the plant's counts, its outlines and its sentences. Every file the
tool writes came out the same byte for byte after the move.
