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
| Where each of those proteins sits | `data/proteins/syn3a/shelves.json`, in the form `schema/SPECIES_PROTEINS.md` fixes (105 KB), added on 15 November 2026 |
| The tool | `tools/build_syn3a_atlas.py`: `fetch` uses the network, `build` does not |
| The check | `node --test tests/syn3a_atlas.test.mjs` |
| The downloads | `/mnt/datasets/Cells/syn3a/`, one folder per source with a `MANIFEST.json`. Seven folders are this tool's (83 files, 3.7 MB); three are the lead's evidence audit's and are only read |
| The analysis | `/mnt/workspaces/Cells/visualizer-syn3a-proteins-20261114-01`: the log of 88 requests, the record of the files a build read with their hashes, and built copies |

## Answer

**The viewer's data on Syn3A is made, and nothing in it claims a model.** The species
file gives the organism two levels, molecules and one cell, so the multi-cell levels are
off for it. Its state is `proposed`: it is the project's minimal-cell track (D173), and
nothing of it is in the engine. The project's record holds an evidence audit, capability
probes of the engine as it stands, and a proposed first milestone, with no engine code
written for it and nothing accepted.

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
| JCVI-syn3.0 has 438 protein types | **Confirmed:** its record has 438 coding sequences and 473 genes | GenBank CP014940.1. The paper that made the strain (Hutchison and others 2016) states no open licence and is not used |
| *M. genitalium* about 480; *M. pneumoniae* about 700; *E. coli* over 4,000 | **Confirmed second-hand:** the 2019 paper gives 482, 688 and 4,637 coding genes | Breuer and others 2019 |
| The 2019 proteomics detected 428 of the 452, about 95% | **Corrected.** The table holds 428 proteins. Tied to locus tags, 427 are among the 452 (94%) and one is the added marker tetM, which the table itself names "tetracycline resistance ribosomal protection protein Tet(M)". The lead's audit and note count the 428 and call the claim confirmed; this adds which they are | Supplementary file 5, joined to the record by identical sequence |
| A single membrane and no cell wall | **Confirmed** | Breuer and others 2019; Gilbert and others 2021 |
| It depends on nutrients and lipids from the medium | **Confirmed:** a rich, not fully defined medium; the reconstruction needs four lipid components imported, cholesterol among them | Breuer and others 2019 |
| Seven genes, with ftsZ and sepF, restore regular division | **Confirmed from open sources.** The 2019 paper says that 19 genes were added to JCVI-syn3.0 to make this strain, ftsZ and sepF among them, which restored a consistent shape; an open review reports that seven of the 19 are needed together for normal division. The paper that found it (Pelletier and others 2021) states no open licence: it is named as the place to read, and nothing is taken from it | Breuer and others 2019; Zhang and others 2023, a review (both CC BY 4.0) |
| Proteomics deposit PXD008159 / MSV000081687 | **Confirmed:** the record is titled JCVI_Syn3A, hosted by MassIVE | ProteomeXchange record |
| Tomograms EMPIAR-10685 and 10686; contact maps at 10.4121/14333618 | **Confirmed** in the paper's data statement; the deposits are in the lead's audit | Gilbert and others 2021 |
| The 2022 model set promoter strengths from protein abundances | **Confirmed** in the paper, which is under a non-commercial licence: said here, and in no data file | Thornburg and others 2022 (CC BY-NC-ND 4.0) |
| The 2026 model: a cell cycle of about 100 minutes | **Confirmed** from the abstract; the paper itself was not read | Thornburg and others 2026, abstract (its bibliographic record names CC BY) |
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
| Energy | ATP from fermenting sugar; in the 2019 reconstruction of its metabolism, central metabolism is the only source of ATP | Breuer and others 2019. Thornburg and others 2022 is named as a place to read more |
| Division | ftsZ and sepF are among 19 genes added to JCVI-syn3.0 to make this strain, which gave it back a regular shape; seven of the 19 are needed together for normal division | Breuer and others 2019; Zhang and others 2023, a review that reports the seven. Pelletier and others 2021 is named as the place to read the experiments |

The drawing's numbers are a sphere 0.4 µm across, one membrane, no wall, no nucleus, a
chromosome of 543 thousand base pairs and 500 ribosomes. The width and the ribosome count
are round numbers for the smaller measured cell, and the level's note says so.

**Two more numbers, cited here only.** The 2022 paper has 93 kinds of membrane protein
making up roughly 9,000 of the 77,000 protein molecules, and its model takes 187 RNA
polymerases. The paper is under a non-commercial licence (CC BY-NC-ND 4.0): these
numbers are in no data file and may not be drawn from.

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

- **Membrane voltage is "present".** The 2019 reconstruction of the cell's metabolism has
  the ATP synthase push protons out, against a passive leak of protons inwards; that is
  a model's reading. No source read here measured the voltage of this strain. The lead's review notes that the 2026
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

Not in it: sequences, simulated counts from any model, structures, and the 3 pseudogenes
and 38 RNA genes. Where a protein sits is in `shelves.json`, described next.

## The shelves: where each protein sits

Shown that none of the atlas's 49 units exists in this organism, the user asked for its
own proteins on shelves: "yes, let's have all the shelfs simmilar format inside outside
for syn3a and all of them". `data/proteins/syn3a/shelves.json` is the data for that, in
the form `schema/SPECIES_PROTEINS.md` fixes. For each of the 455 proteins it gives the side
of the cell membrane it sits on, how that is known, and its district. The drawing is not
made yet. `unit` is empty throughout: the atlas found none of its units here.

| Side | Proteins | Stated | Predicted | By function |
| --- | --- | --- | --- | --- |
| Outside, anchored to the membrane's outer face | 13 | 0 | 13 | 0 |
| In the membrane, spanning it | 86 | 0 | 86 | 0 |
| Inside, free or attached to the inner face | 352 | 6 | 326 | 20 |
| Not known: nothing settles it | 4 | | | |

**No established prediction exists for these sequences, so the reading is the tool's
own.** UniProt's archive holds family signatures on them and no membrane-spanning
stretches. No UniProtKB entry of any organism with one of these exact sequences gives one
either. The file says so with every predicted side.

- **In the membrane:** a stretch of 19 residues whose mean hydropathy on Kyte and
  Doolittle's scale is 1.6 or more and which holds no charged residue, or 2.2 or more with
  at most one.
  - The window of 19 and the 1.6 are the usual reading of that scale; Paulet and others
    (2011, CC BY 2.0) state it.
  - The conditions on charged residues are this tool's. They were set against this
    organism's own proteins, so the checks below are not independent of them.
- **Outside:** PROSITE's lipoprotein signature (PS51257, as UniProt's archive gives it)
  from the first residue to a cysteine, with a hydrophobic stretch before the cysteine.
  The lipoproteins of mycoplasmas are bound to the membrane and exposed on the cell's
  surface (Christodoulides and others 2018, a review under CC BY 4.0). That is said of
  mycoplasmas in general and was not measured in this strain.
- **Inside:** no such stretch and no lipid anchor. This includes proteins attached to the
  membrane's inner face, such as the ATP-binding parts of transporters and the outer part
  of the ATP synthase.
- **Stated (6):** elongation factors Tu and P, initiation factors 1 and 3, guanylate
  kinase and the acyl-carrier-protein synthase. A reviewed UniProtKB entry of *Mycoplasma
  capricolum* or *Mycoplasma mycoides* SC with exactly the same sequence says "Cytoplasm".
  - That is a statement about the other organism, and the file names the entry.
  - None rests on an experiment: five are made by a family rule and one by similarity.
  - Such an entry also says that the spermidine importer's ATP-binding protein (potA) is
    at the cell membrane as a peripheral protein, without saying which face. The reading
    places it inside, and it is marked as at the membrane.
- **By function (20):** the sequence has a hydrophobic stretch, but the 2019 paper's class
  leaves no doubt that the protein works inside the cell: translation, transcription, the
  upkeep of DNA, sugar breakdown, the pentose phosphate pathway or nucleotide metabolism.
  Function is never used to place a transport protein.

**How the reading fares against what is known.**

- **Proteins that work inside the cell:** of 224 in the classes just named, 20 have a
  stretch at 1.6 or more, which the usual reading alone would call membrane-spanning. With
  the condition on charged residues the tool reads 1 of them so, lactate dehydrogenase.
- **Proteins named as membrane-spanning:** all 13 that the annotation calls a permease are
  read as membrane-spanning.
- **Stated places:** the reading agrees with all 6.
- **The lipoprotein signature** matches 15 sequences, and 14 are kept.
  - 13 are placed outside. One (locus 0338) also has a stretch at its far end and is
    placed in the membrane.
  - The fifteenth is ribosomal protein L32, which has no hydrophobic stretch before the
    cysteine. UniProt's automatic annotation makes the same mark on the same protein in
    another mycoplasma (unreviewed entry A0AAQ3DPT5); it is set aside here.
- **Known shortfalls:** a stretch that holds charged residues is not read, so the count of
  stretches falls short for some proteins. The lipoprotein signal peptidase and the ATP
  synthase's c subunit are each read with one. The translocon's SecE is caught only by
  the second condition.

**Against the literature.** Here 86 proteins span the membrane and 13 are anchored on it,
99 together; 89 of them were seen in the proteomics, with an estimated 7,685 of the
77,028 copies. The 2022 whole-cell model has 93 membrane proteins making up roughly 9,000
of the 77,000, and does not say how they were told; that paper is under a non-commercial
licence, so its numbers are said in this note only and are in no data file. The two
counts are close but need not be of the same proteins: no list of the model's was copied
or compared.

**Districts** are the 2019 paper's secondary functional class, in its own words: 14 of
them. Its tertiary class is kept with each protein for laying a district out.

| District | Proteins | Outside | In | Inside | Not known |
| --- | --- | --- | --- | --- | --- |
| Translation | 134 | 0 | 0 | 134 | 0 |
| No Kegg ortholog (function unclear) | 83 | 10 | 32 | 38 | 3 |
| Membrane Transport | 57 | 3 | 34 | 20 | 0 |
| Central Carbon Metabolism | 48 | 0 | 0 | 47 | 1 |
| DNA Maintenance | 38 | 0 | 0 | 38 | 0 |
| Biosynthesis | 32 | 0 | 8 | 24 | 0 |
| Folding, Sorting and Degradation | 25 | 0 | 8 | 17 | 0 |
| Transcription | 15 | 0 | 0 | 15 | 0 |
| Kegg ortholog defined (function unclear) | 8 | 0 | 2 | 6 | 0 |
| Cell Growth, Energy Metabolism, Other Enzymes | 4 each | 0 | 1, 0, 1 | 3, 4, 3 | 0 |
| Defense | 2 | 0 | 0 | 2 | 0 |
| Drug resistance (the added tetM) | 1 | 0 | 0 | 1 | 0 |

**Marks** kept with each protein: essentiality and whether it was seen in the proteomics
(both measured); the estimated copies; the three proteins added for manipulation; the
finer class; the number of stretches read; the lipid anchor; what stands behind a stated
side; and an assembly where the
record's product name gives it outright: 52 ribosomal proteins, the 8 subunits of the ATP
synthase and 5 of RNA polymerase. No other assembly is marked, because no source read
names its members without inference.

**What is not known.**

- **Four proteins are not placed:** loci 0286, 0326 and 0373, of unknown function, and
  the uncharacterized kinase 0495. Each has a hydrophobic stretch that holds charged
  residues, and nothing settles its side.
- **Six of the 86 membrane calls rest on one stretch at the very start of the protein.**
  That may be an export signal that is cut off, and the protein would then sit outside.
  They are marked.
- **No topology:** not which end of a membrane protein faces out, and not which face a
  protein inside is attached to.

**Terms.** Everything copied into the file comes from a source with open terms: GenBank
(NCBI states no restriction), the 2019 paper (CC BY 4.0), UniProt (CC BY 4.0), and
Biopython 1.85 for the scale's 20 values (Biopython License Agreement or BSD 3-Clause).
Two open papers stand behind two statements: Paulet and others 2011 (CC BY 2.0) for the
usual reading of the scale, and Christodoulides and others 2018 (CC BY 4.0) for where the
lipoproteins of mycoplasmas sit. PROSITE's profile itself is not copied, only where
UniProt reports that it matches; PROSITE's own terms are non-commercial, and the file
says so. Four papers are named as places to read and nothing is taken from them: Kyte
and Doolittle 1982 and Chambaud and others 1999 (no stated terms), L'Hernault and
Arduengo 1992 (CC BY-NC-SA) and the 2022 whole-cell paper (CC BY-NC-ND). Nothing is from
the 4D model's repository or archive.

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
| Zhang and others 2023, *Bioengineering (Basel)* 10:271, a review | That seven of the 19 added genes are needed together for normal division | CC BY 4.0 |
| Paulet and others 2011, *BMC Bioinformatics* 12:135 | The usual reading of the hydropathy scale | CC BY 2.0 |
| Christodoulides and others 2018, *Front Microbiol* 9:1682, a review | That mycoplasmas' lipoproteins are bound to the membrane and exposed on the surface | CC BY 4.0 |
| Biopython 1.85 | The 20 values of the hydropathy scale | Biopython License Agreement or BSD 3-Clause |
| Europe PMC | Bibliographic records | Facts only |

Each of these is permissive. The sources that are not, and what stands where they once
stood, are in the section "What rests on non-commercial or unlicensed sources".

Read and not copied: the 2022 paper; the 2026 paper and the archive of
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

## What rests on non-commercial or unlicensed sources

The project's rule (D173, 15 November 2026) sorts every source into three classes.
**Permissive** (CC BY, CC0, or a plain statement that no restriction is placed): values
and derived data may enter the repository, with attribution. **Non-commercial** (any
CC BY-NC licence): analysis only. **No stated terms**: nothing enters. A data file here
holds no value and no statement from a source of the last two classes; such a source is
named as a pointer, with what is to be read there. A note may cite a single value from
one, with its class beside it.

**Nothing in the data files rests on such a source, with one exception that is said
below.** On 15 November 2026 every source was classed, in the files themselves (`class`),
and what had rested on a source that is not permissive was moved or taken out:

| Source | Class | What it once gave | What stands there now |
| --- | --- | --- | --- |
| Thornburg and others 2022 | non-commercial (CC BY-NC-ND 4.0) | The species file's fact on energy, three capability notes and the atlas's note on the ATP synthase; the shelves' comparison with its count of membrane proteins | The energy fact and the notes rest on Breuer and others 2019 (CC BY 4.0): its reliance on fermentation, central metabolism as the only source of ATP, and the proton-pushing ATP synthase of its reconstruction. The count is no longer in a file. The paper is a pointer in the species file and the shelves |
| Pelletier and others 2021 | no stated terms (not open; its record names no licence) | The fact on division, from its abstract | Breuer and others 2019 for the 19 added genes with ftsZ and sepF, and Zhang and others 2023 (a review, CC BY 4.0) for the seven needed together. The review relays the 2021 paper's finding. The paper is a pointer in the species file |
| L'Hernault and Arduengo 1992 | non-commercial (CC BY-NC-SA 4.0) | The window of 19 residues and the level of 1.6 | Paulet and others 2011 (CC BY 2.0), which states both. The paper is a pointer in the shelves |
| Chambaud and others 1999 | no stated terms (not open) | That mycoplasmas' lipoproteins sit on the membrane's outer face, from its abstract | Christodoulides and others 2018 (a review, CC BY 4.0): bound to the membrane and exposed on the surface. The paper is a pointer in the shelves |
| Kyte and Doolittle 1982 | no stated terms (not open) | Named as the source of the hydropathy scale | The scale's 20 values were always taken from Biopython 1.85 (BSD); the shelves now name Biopython as the source and the paper as a pointer |
| Hutchison and others 2016 | no stated terms (not open) | Its abstract's gene count of JCVI-syn3.0, checked by the tool | The count is read from GenBank CP014940.1 alone. The paper is named in this note only |

**One dependence remains, and is said in the files.** The 14 lipid-anchor marks of the
shelves, and the 13 proteins placed outside by them, come from matches to a profile of
**PROSITE** (PS51257), as UniProt's archive records them under CC BY 4.0. PROSITE's own
database is distributed under CC BY-NC-ND 4.0 and asks commercial users for a licence fee
(its licence page was read and saved on 15 November 2026). Nothing was downloaded from
PROSITE and its profile is not copied, but the placements rest on its matches. The
shelves name PROSITE among their sources as non-commercial, read through UniParc, and the
mark says so. A rule on the sequence alone finds the same 14 and three false extras; it
can take the profile's place if this dependence is unwanted. That is the coordinator's
and the user's decision.

**Values cited in this note only,** each from a source that is not permissive, with its
class: the 2022 model's 93 membrane proteins, roughly 9,000 of 77,000 molecules, and its
187 RNA polymerases (Thornburg and others 2022, non-commercial).

**Relayed values.** Two statements in the files are made by a CC BY source that relays
another paper: the seven genes (Zhang and others 2023, from Pelletier and others 2021)
and the exposure of lipoproteins on the surface (Christodoulides and others 2018, a
review). Each is worded as its open source words it.

## A Syn3A switch in the simulator

The user: "we want a switch for syn3a as well, in our simulator, then of course we will
have to switch off multi-cell".

- **In the viewer** the switch is the species: Syn3A has two levels, molecules and one
  cell, and a sentence where tissue, organ and body would be.
- **In the engine** the work is the lead's. Decision D173 makes Syn3A the minimal-cell
  track beside the current work, with its first milestone fixed after a capability probe;
  D171 gives it an agent under the lead, and D172 notes that its metabolism needs reactions that can make and
  spend fuel. On main, the lead's track note is `docs/SYN3A_MINIMAL_CELL_TRACK.md`. As
  revised on 15 November 2026 it says that capability probes ran the engine from a frozen
  snapshot "as a capability check only", that "No engine code was written" and that
  "Nothing here is an acceptance". Its review of the 2026 whole-cell paper is
  `docs/PAPER_REVIEW_WHOLE_CELL_MINIMAL_CELL.md`, and its evidence audit is in
  `/mnt/workspaces/Cells/syn3a-20261114-01`.
- **What this data adds for that agent:**
  - one frozen annotation and a 455-line catalogue keyed to it, with each column's source
    and terms, and the 452-against-455 question settled;
  - which of the map's 21 capabilities have a place in this organism, with the reason for
    each absence;
  - the finding that it has no recognisable ion channel, so its ion transport is pumps and
    transporters only.
