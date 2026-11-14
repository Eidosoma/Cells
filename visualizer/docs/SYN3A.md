# Syn3A in the viewer: the organism, its proteins, and what the note says

**Status: made by the visualizer session, 14 November 2026, for the user and the lead.**
The user asked to "put another agent on SOTA_SYN3A.md", for "a switch for syn3a as well
... then of course we will have to switch off multi-cell", and to "start a proteint
catalog for this one as well". This note says what was made for the viewer, which of the
note's claims were checked, and how sure each part is. Numbers are as built on
14 November 2026; the build prints them again.

| | |
| --- | --- |
| The species file | `data/species/syn3a.json`, in the form `schema/SPECIES.md` fixes (10 KB) |
| Its side of the protein atlas | `data/proteins/atlases/syn3a.json`, in the form `schema/SPECIES_ATLAS.md` fixes (38 KB) |
| The start of its protein catalogue | `data/proteins/syn3a/proteins.tsv` (455 proteins, 110 KB) and its `README.md` |
| The tool | `tools/build_syn3a_atlas.py`: `fetch` uses the network, `build` does not |
| The check | `node --test tests/syn3a_atlas.test.mjs` |
| The downloads | `/mnt/datasets/Cells/syn3a/`, one folder per source with a `MANIFEST.json`. Six folders are this tool's (78 files, 3.5 MB); three are the lead's evidence audit's and are only read |
| The analysis | `/mnt/workspaces/Cells/visualizer-syn3a-proteins-20261114-01`: the log of 83 requests, the record of the files a build read with their hashes, and built copies |

## Answer

**The viewer's data on Syn3A is made, and nothing in it claims a model.** The species
file gives the organism two levels, molecules and one cell, so the multi-cell levels are
off for it. Its state is `proposed`: a note proposes it, support in the engine is being
worked on (D171), and nothing of it is in the engine. The project's record holds an
evidence audit and a proposal, in which no engine model ran.

**"452 against 455" is settled: both are right.** The genome record GenBank CP016816.2
holds 455 protein products. 452 were kept from *Mycoplasma mycoides*; 3 were added for
genetic manipulation (tetM and the yeast genes HIS3 and MET14). The 2019 paper's own
table sets the 3 apart. The catalogue freezes that record and lists all 455, flagged.

**It has none of the machines the protein atlas draws.** Every one of the 43 units with
named candidates is a machine of animal cells, and none was found among its 455 proteins.
No ion channel of any family was found at all. What moves its ions is listed instead:
an ATP synthase, two P-type ATPases, a potassium uptake system and its sugar transporter.

**Two of the note's numbers need a correction.** The proteomics saw 427 of the 452 kept
proteins, not 428: the 428th is the added marker tetM. And the paper's Table 1 and its
supplementary file differ by one gene on essentiality.

## What the user's note says, claim by claim

The note came through an assistant, so nothing was taken from it on trust. The lead's
evidence audit (`/mnt/workspaces/Cells/syn3a-20261114-01`) checks its datasets claim by
claim; this table covers what the viewer's data uses, and says where it adds to the audit.

| Claim | Status | Source read |
| --- | --- | --- |
| 452 protein-coding genes, 493 genes, about 543,000 base pairs | **Confirmed.** The record is 543,379 base pairs with 496 genes: 455 protein products, 3 pseudogenes, 38 RNA genes. The paper reaches 493 from the record's 498 features by leaving out 3 pseudogenes and 2 yeast genes; however the 493 is made up, 452 is the count of kept protein-coding genes | Breuer and others 2019; GenBank CP016816.2 |
| "Some newer modeling papers use 455 proteins" | **Explained:** 455 is 452 kept plus 3 added, as above | The 2019 paper's supplementary file 3 |
| JCVI-syn3.0 has 438 protein types | **Confirmed:** its record has 438 coding sequences and 473 genes | GenBank CP014940.1; Hutchison and others 2016, abstract |
| *M. genitalium* about 480; *M. pneumoniae* about 700; *E. coli* over 4,000 | **Confirmed second-hand:** the 2019 paper gives 482, 688 and 4,637 coding genes | Breuer and others 2019 |
| The 2019 proteomics detected 428 of the 452, about 95% | **Corrected.** The table holds 428 proteins. Tied to locus tags, 427 are among the 452 (94%) and one is the added marker tetM, which the table itself names "tetracycline resistance ribosomal protection protein Tet(M)". The lead's audit and note count the 428 and call the claim confirmed; this adds which they are | Supplementary file 5, joined to the record by identical sequence |
| A single membrane and no cell wall | **Confirmed** | Breuer and others 2019; Gilbert and others 2021 |
| It depends on nutrients and lipids from the medium | **Confirmed:** a rich, not fully defined medium; the reconstruction needs four lipid components imported, cholesterol among them | Breuer and others 2019 |
| Seven genes, with ftsZ and sepF, restore regular division | **Confirmed** from the abstract; the paper is not open | Pelletier and others 2021, abstract |
| Proteomics deposit PXD008159 / MSV000081687 | **Confirmed:** the record is titled JCVI_Syn3A, hosted by MassIVE | ProteomeXchange record |
| Tomograms EMPIAR-10685 and 10686; contact maps at 10.4121/14333618 | **Confirmed** in the paper's data statement; the deposits are in the lead's audit | Gilbert and others 2021 |
| The 2022 model set promoter strengths from protein abundances | **Confirmed** | Thornburg and others 2022 |
| The 2026 model: a cell cycle of about 100 minutes | **Confirmed** from the abstract | Thornburg and others 2026, abstract |
| The 2026 model: 50 cells, about 15,000 GPU-hours, no kinetic model of FtsZ | **Not re-read here.** The lead's review confirms them against the preprint | `docs/PAPER_REVIEW_WHOLE_CELL_MINIMAL_CELL.md` on main |
| The lipid-diet paper (2024), the membrane paper (2026), the adaptation paper (2023), the division study's data deposit | **Not checked here.** The lead's audit covers them, with corrections | The audit's inventory |
| The smallest known genomes (*Vidania*), and everything on *M. pneumoniae* as a companion | **Not checked:** outside this task | |

Two smaller things the sources disagree on:

- **Doubling time.** The 2019 paper measures 105 minutes and also says "about 2 hr" in
  its introduction; the 2021 tomography paper quotes it as about 110 minutes. The species
  file gives 105.
- **Essentiality.** The 2019 paper's Table 1 totals 271 essential, 113 quasi-essential
  and 68 non-essential genes. Its supplementary file, which the catalogue copies, gives
  270, 113 and 69. Which gene differs was not traced.

## The organism as the viewer will draw it

Each fact is in `cell.facts` of the species file with its source.

| Fact | Value | Source, and how sure |
| --- | --- | --- |
| Shape and size | A sphere about 400 nm across | The 2019 paper says so. Two cells in electron tomograms were 403 nm and 495 nm across (Gilbert and others 2021) |
| Envelope | One membrane, no cell wall, no periplasm | Breuer and others 2019; Gilbert and others 2021 |
| Inside | No nucleus: ribosomes spread through the whole cell, the chromosome among them | Gilbert and others 2021, tomograms of two cells |
| Chromosome | One circle of 543,379 base pairs | GenBank CP016816.2 |
| Ribosomes | About 500 in a small cell | Counted two ways in the tomograms: 503 or 684 in the smaller cell, 820 or 1,095 in the larger. The counts differ by a third |
| Proteins | About 77,000 molecules in an average cell | An estimate: measured shares of the protein signal, scaled by dry mass (Breuer and others 2019) |
| Doubling time | About 105 minutes in rich medium | Breuer and others 2019, a growth curve |
| Energy | ATP from sugar breakdown alone; no oxidative phosphorylation | Thornburg and others 2022 |
| Division | ftsZ and sepF are among seven genes needed for regular shape and division | Pelletier and others 2021, abstract |

The drawing's numbers are a sphere 0.4 µm across, one membrane, no wall, no nucleus, a
chromosome of 543 thousand base pairs and 500 ribosomes. The width and the ribosome count
are round numbers for the smaller measured cell, and the level's note says so.

**Two more numbers the drawing may want,** both from the 2022 paper and not in the species
file: 93 kinds of membrane protein make up roughly 9,000 of the 77,000 protein molecules,
and the model takes 187 RNA polymerases.

## Which capabilities have a place in it

A place means the organism has the structure or the process. It says nothing about a
model of this organism.

| Place | Capabilities |
| --- | --- |
| **Absent** (9), each with why | Ion channels; gap junctions; calcium and the ER; mitochondria; gene regulation in tissue; Golgi and trafficking; cell replacement; tissue mechanics; cell sheets |
| **Present, with a note** (11) | Membrane voltage; ion pumps; space between cells (here the growth medium); water and cell volume; fuel; regulatory circuits (at the chromosome); protein assembly; molecular machines; secreted signals; injury and repair; cell division |
| **Present as in any cell** (1) | Cell chemistry |

What each absence rests on:

- **Tissue capabilities** (five of them): it lives as single cells.
- **Internal compartments** (three): it is a bacterium with a single membrane. The 2019
  paper calls its kind "bacteria with a single membrane and no periplasmic space", and the
  tomograms show ribosomes through the whole cell.
- **Ion channels:** a search, described below. This is the one absence that is a finding
  of this work and not a textbook fact.

Three placements are judgement and are said to be:

- **Membrane voltage is "present".** The papers cite measurements of a proton gradient in
  other mycoplasmas, where the ATP synthase runs backwards and pumps protons out. No
  source read here measured it in this strain. The lead's review notes that the 2026
  model has no membrane potential; that is about the model, and this is about the cell.
- **Injury and repair is "present"** only because the place would be its membrane. No
  source read here describes it.
- **Secreted signals is "present"** for its release of lactate and acetate into the
  medium, which the 2019 reconstruction needs. Signalling between its cells was not looked
  for.

## The protein atlas: none of the 49 units

| Finding | Units | |
| --- | --- | --- |
| Found | 0 | |
| A different family | 0 | |
| Nothing found | 43 | every unit for which the inventory names candidates |
| Nothing to look for | 6 | lumped properties, a default current, a configured slot and the designed cage |

**How it was searched.** UniProtKB holds no entry of this organism. UniProt's archive
holds exactly its 455 sequences, with the family signatures on each. The 40 signatures of
the 33 families behind the units, the same ones the planarian atlas asks, were looked for
on all 455. None was found.

**The controls.** Each signature was also asked of every mollicute in UniProtKB, the
class of bacteria this organism was made from. For 38 of the 40 nothing came back there
either. Two exist in other mollicutes and not here: the plasma-membrane calcium pump's
branch (6 entries) and the BK channel's (4). The build checks that the units' human
candidates carry the signatures, so the search finds each family where it exists.

**No ion channel.** Eight further signatures were asked: the channels a bacterium could
have for potassium, chloride, magnesium, water and membrane stretch. None is on any of
the 455 proteins. Other mollicutes do carry them (from 4 to 90 entries each), so the
search would have found them. In its parent species, *Mycoplasma mycoides*, UniProtKB has
one entry with the aquaporin family's signature and one with the MgtE magnesium
channel's; whether the minimisation removed those genes was not traced.

**What it has that the inventory lacks** is under `extra`, nine proteins:

- **ATP synthase** (four of its eight subunits listed). In mycoplasmas it typically spends
  ATP to pump protons out. The inventory has no F-type ATPase.
- **Two P-type ATPases** (loci 0787 and 0879), of the superfamily of the sodium-potassium
  and calcium pumps and of another branch. Both are annotated as magnesium transporters.
  The second is named corA in the record, but carries a P-type ATPase's signatures and
  not the CorA channel's; the 2019 paper suggests it could carry calcium and uses it as
  the calcium importer.
- **A potassium uptake system** (KtrAB, loci 0685 and 0686): how it takes up potassium
  without a sodium-potassium pump or a potassium channel.
- **The glucose transporter PtsG** (locus 0779), the only annotated sugar importer.

All nine are assigned by annotation. Five are named for this organism in the 2019 paper;
four are listed by the signature on their sequence. None is a measured function in this
strain, and nothing is called an ortholog.

## The catalogue

One line for each of the 455 protein products of GenBank CP016816.2 (annotation of
12 April 2018). The record was frozen because the 2019 paper names it and keys its tables
to its locus tags, so every column can be tied to one gene.

| Column group | From | Measured, or annotation? |
| --- | --- | --- |
| Locus tag, gene, product, length, protein identifier | GenBank CP016816.2 | Annotation; 330 genes are named and 130 products begin "Uncharacterized" |
| Origin, functional class | The 2019 paper, supplementary file 3 | The paper's classification: 212 genetic information processing, 143 metabolism, 91 unclear, 6 cellular processes |
| Essentiality | The same file | Measured by transposon mutagenesis in this strain, then classified: 270 essential, 113 quasi-essential, 69 non-essential of the 452 |
| Detected, copies per cell | The 2019 paper, supplementary file 5 | Detection is measured (428). Copies are an estimate scaled to 77,028 molecules in a cell, at the first time point |
| Archive identifier, signatures, other organisms' identical entries | UniProt | Computed from the sequence. 45 proteins have a UniProtKB entry of another organism with exactly their sequence, and the column names the organism |

The proteomics table uses the protein identifiers of the record's first version
(CP016816.1). They were tied to today's locus tags by identical sequence; all 428 tied.

Not in it: sequences, simulated counts from any model, structures, where a protein sits,
and the 3 pseudogenes and 38 RNA genes.

## What could not be determined

- **Whether any of its transporters acts as a channel.** The potassium uptake protein is
  of a family related to channels. Nothing read here settles it.
- **Which ions the two P-type ATPases carry.** The annotation says magnesium; the 2019
  paper uses one for calcium, on similarity alone.
- **Its membrane voltage.** Not measured in any source read; the measurements the papers
  cite are of other mycoplasmas and were not read.
- **The cell's size at division.** Two tomogram cells are all that was read. The 2026
  model's growth from 400 to 500 nm across is in the lead's review of the preprint.
- **Protein functions.** 91 of the 452 have an unclear function by the paper's own
  classes, and every function here is annotation.
- **Copies in one cell.** The estimate is a population average at one time point.
- **Whether the NCBI link opens.** NCBI's page of a protein identifier answered this tool
  with a browser check. The identifier was looked up through NCBI's E-utilities instead,
  which return the record.

## Sources and terms

| Source | What is taken | Terms |
| --- | --- | --- |
| GenBank CP016816.2, CP016816.1 and CP014940.1 | Locus tags, names, products, identifiers, lengths; gene counts | "NCBI places no restrictions on the use or distribution of the GenBank data"; submitters may claim rights, and these records state none |
| Breuer and others 2019, *eLife* 8:e36842, with supplementary files 3 and 5 | Classes, essentiality, detection, estimated copies; numbers and gene names from the text | CC BY 4.0 |
| UniProt, release 2026_04 (UniParc and UniProtKB) | Signatures on the sequences; entries with the same sequence; control counts | CC BY 4.0 |
| InterPro | The signatures' identifiers and names | CC0 1.0 |
| Gilbert and others 2021, *Front Mol Biosci* 8:644133 | Cell radii and ribosome counts | CC BY 4.0 |
| Thornburg and others 2022, *Cell* 185:345 | Numbers and one short quotation | CC BY-NC-ND 4.0: read, nothing more copied |
| Pelletier and others 2021, *Cell* 184:2430 | The abstract's statement on the seven genes | Abstract only; the paper is not open |
| Europe PMC | Bibliographic records | Facts only |

Read and not copied: the 2022 paper beyond its numbers; the 2026 paper and the archive of
its model, which are a reference simulator's and from which nothing is taken; the
proteomics instrument files. The lead's audit downloaded the genome record, the 2019
paper's files and the proteomics record first; this tool reads those copies and holds no
second one.

## How to rebuild

```bash
python3 tools/build_syn3a_atlas.py fetch --evidence DIR --datasets DATA   # network: about 3 minutes, 4 MB
python3 tools/build_syn3a_atlas.py build --evidence DIR --datasets DATA   # offline: about 5 seconds
node --test tests/syn3a_atlas.test.mjs                                    # set SYN3A_EVIDENCE and SYN3A_DATASETS elsewhere
```

`DATA` holds the downloads, one folder per source with a `MANIFEST.json`; `DIR` holds the
log of what was asked. `fetch` asks only for what is not yet there and never writes in a
folder another agent made. `build` checks every file against the SHA-256 its MANIFEST
gives, stops if a saved source no longer says what the files state, and writes the same
bytes every time; the test rebuilds and compares. The facts, the capability table and the
units' notes are tables in the tool; the counts in them are read from the downloads.

## A Syn3A switch in the simulator

The user: "we want a switch for syn3a as well, in our simulator, then of course we will
have to switch off multi-cell".

- **In the viewer** the switch is the species: Syn3A has two levels, molecules and one
  cell, and a sentence where tissue, organ and body would be.
- **In the engine** the work is the lead's. Decision D171 gives a Syn3A minimal-cell agent
  under the lead, and D172 notes that its metabolism needs reactions that can make and
  spend fuel. On main, the lead's proposal is `docs/SYN3A_MINIMAL_CELL_TRACK.md`, which the
  progress record calls "an assessment only; no engine model ran"; its review of the 2026
  whole-cell paper is
  `docs/PAPER_REVIEW_WHOLE_CELL_MINIMAL_CELL.md`, and its evidence audit is in
  `/mnt/workspaces/Cells/syn3a-20261114-01`.
- **What this data adds for that agent:**
  - one frozen annotation and a 455-line catalogue keyed to it, with each column's source
    and terms, and the 452-against-455 question settled;
  - which of the map's 21 capabilities have a place in this organism, with the reason for
    each absence;
  - the finding that it has no recognisable ion channel, so its ion transport is pumps and
    transporters only.
