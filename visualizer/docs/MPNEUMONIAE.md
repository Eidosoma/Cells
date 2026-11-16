# M. pneumoniae in the viewer: the organism, its proteins, and what the note says

**Status: made by the visualizer session, 15 November 2026, for the user and the lead.**
The user: "M. pneumoniae - we are also adding this next as species and get an agent on
their proteint catalog as well 700 proteint". This note says what was made for the viewer,
which of the claims in the user's note (`docs/SOTA_SYN3A.md`, section 5) were checked, and
how sure each part is. Numbers are as built on 15 November 2026; the build prints them
again.

| | |
| --- | --- |
| The species file | `data/species/mpneumoniae.json`, in the form `schema/SPECIES.md` fixes (13 KB) |
| Its side of the protein atlas | `data/proteins/atlases/mpneumoniae.json`, in the form `schema/SPECIES_ATLAS.md` fixes (38 KB) |
| Its protein catalogue | `data/proteins/mpneumoniae/proteins.tsv` (688 proteins, 163 KB) and its `README.md` |
| Its proteins on the shelves | `data/proteins/mpneumoniae/shelves.json`, in the form `schema/SPECIES_PROTEINS.md` fixes (111 KB) |
| The tool | `tools/build_mpneumoniae_atlas.py`: `fetch` uses the network, `build` does not |
| The check | `node --test tests/mpneumoniae_atlas.test.mjs` (27 tests) |
| The downloads | `/mnt/datasets/Cells/mpneumoniae/`, one folder per source with a `MANIFEST.json`. Eight folders are this tool's (85 files, 6.6 MB). The three others there (`maier2011-msb`, `wodke2013-msb`, `chen2016-nar`) are the lead's audit's and were not read |
| The analysis | `/mnt/workspaces/Cells/visualizer-mpneumoniae-proteins-20261115-01`: the log of 85 requests, the record of the files a build read with their hashes, the tool as run and built copies |

## Answer

**The catalogue has 688 proteins, and that is the count to freeze.** It is the genome
record GenBank U00089.2 of strain M129, as its authors re-annotated it in 2000. Its locus
tags, MPN_001 to MPN_688, are the numbers that the papers on this organism use. "About
700" is right as a round number, and the sources give seven different counts, from 677 to
724; the table below says what each one counts.

**It is far better annotated than Syn3A.** UniProt holds a reviewed, curated entry for 687
of the 688 proteins. A 2015 paper under an open licence gives every gene a class and a
measured essentiality. So the catalogue carries curated names, a level of evidence and
essentiality for every line.

**Its measured protein amounts are not in the catalogue.** They exist (Maier and others
2011), under a non-commercial licence, so nothing of them is in any data file. The
species file gives the total of protein molecules in a cell and the copies of the
ribosomal proteins from an open paper instead (Weber and others 2023, CC BY 4.0).

**It has none of the machines the protein atlas draws.** None of the 43 units with named
candidates was found among its 688 proteins, and no ion channel of any family searched.
One channel-like protein was found, the glycerol facilitator GlpF, which Syn3A lacks.

**On the shelves, 398 of the 688 proteins are placed and 290 are not.** 51 sit outside
the membrane, 113 in it and 234 inside. The 290 have no stated place, no prediction and
no function that settles it; they are not placed by guess.

**The shape list cannot draw this cell honestly.** It is drawn as a rod, and the species
file says that the real cell narrows at one end into its attachment organelle.

## What the user's note says, claim by claim

The note came through an assistant, so nothing was taken from it on trust. This table
covers its claims about this organism. The lead's audit of the organism had begun and had
no findings to read when this was made.

| Claim | Status | Source read |
| --- | --- | --- |
| About 700 encoded protein types | **Roughly right; six counts exist.** The frozen record has 688 | See "The counts" below |
| "Foundational studies use approximately 689–690" | **689 confirmed:** "a single, small chromosome of only 816 394 base pairs, encoding 689 proteins". 690 was not seen | Wodke and others 2013 (non-commercial: said in this note only) |
| A 2016 study assembled 1,748 consistently generated multiomics datasets | **Confirmed:** "1748 consistently generated '-omics' data sets", 1,680 of them published before and 68 new. It is under a non-commercial licence | Chen and others 2016 |
| The 2011 paper measures RNA abundance, protein abundance and protein turnover under different conditions | **Confirmed** from its abstract and text. It is under a non-commercial licence | Maier and others 2011 |
| The 2013 paper combines measured growth, glucose use, products and responses to pH | **Confirmed:** it fits "experimentally measured glucose consumption, protein production, as well as ... lactate and acetate secretion", and analyses growth at different pH | Wodke and others 2013 (non-commercial) |
| Its figures for ATP spent on maintenance or proton pumping are the model's, not measurements | **Confirmed:** the share of 57 to 80% for the ATP synthase rests on the model, a measured copy number and rates from other organisms | Wodke and others 2013 (non-commercial: the share is said in this note only) |
| A September 2026 *Cell* paper reports 140 structural maps from native and antibiotic-treated cells | **Confirmed** from the abstract: "to resolve 140 maps". Published 25 September 2026, doi:10.1016/j.cell.2026.08.054. The paper is not open | Dobbs and others 2026, abstract (no stated terms: said in this note only) |
| EMD-53631 is a map of a large ribosomal subunit during its making, in native cells | **Confirmed:** "Map of M. pneumoniae 50S mid biogenesis in native cells", released 23 September 2026 | The EMDB entry |
| Rich measurements of interactions and cellular structures | **Confirmed in part:** a 2009 screen found 62 complexes of one protein and 116 of several | Kühner and others 2009, abstract (no stated terms: said in this note only) |
| *M. genitalium*'s 86 gene-disruption strains; *E. coli*'s proteomics | **Not checked:** other organisms | |

## The counts

| Count | Whose | What it counts |
| --- | --- | --- |
| 677 | Himmelreich and others 1996 (no stated terms: in this note only) | the reading frames predicted when the genome was sequenced |
| 688 | GenBank U00089.2; Dandekar and others 2000 (no stated terms) | the re-annotation, which by the paper's abstract added 12 and dismissed one. **Frozen here**, from the record |
| 687 | Parrott and others 2016, a review (CC BY) | "687 genes", said of the genome as it was first sequenced |
| 689 | Wodke and others 2013 (non-commercial: in this note only) | "encoding 689 proteins", citing the two papers above; which gene makes the difference was not traced |
| 694 | Lluch-Senar and others 2015 | their re-annotation, 32 of them reading frames under 100 residues. Their table lists 49 lettered additions beside the 688 numbered genes |
| 686 | UniProt, release 2026_04 | reviewed entries: two fragments of one gene (MPN_304, MPN_305) share an entry, and MPN_441 has none |
| 724 | NCBI RefSeq NC_000912.1 | the coding sequences that NCBI's own pipeline finds in the same genome today |

The data files give four of these counts, each from a permissive source: 688, 687, 694
and 686, with RefSeq's 724 in the README. The counts of 1996 and 2013 are in this note
only. The record was frozen because the literature is keyed to it. The lettered additions of
the 2015 paper are not in the catalogue: the record has no such genes, and they have no
protein identifiers to tie to.

## The organism as the viewer will draw it

| Fact | Value | Source, all permissive |
| --- | --- | --- |
| Shape and size | A thin cell 1 to 2 µm long and 0.1 to 0.2 µm wide, of changeable shape; "about 2 µm long"; a volume of 0.075 µm³ | Parrott and others 2016 (a review, citing a review of 2004); Nakane and others 2015; Weber and others 2023 |
| Attachment organelle | A membrane protrusion at one pole, 250 to 300 nm long, with an internal core. It carries the adhesins and leads the cell when it glides | Nakane and others 2021; Nakane and others 2015 |
| Envelope | A cell membrane stiffened by sterols; no cell wall; one membrane, by UniProt's entries, which name the cell membrane and no outer one | Parrott and others 2016; Nakane and others 2015; UniProt |
| Inside | A small prokaryote, among the smallest organisms that copy themselves; no nucleus | Li and others 2021; Gaspari and others 2020; the genome record's lineage |
| Chromosome | One circle of 816,394 base pairs | GenBank |
| Ribosomes | About 300 in a cell: the ribosomal proteins at a median of 300 copies, by mass spectrometry | Weber and others 2023, measured in strain M129 |
| Proteins | About 120,000 molecules in a cell, the sum over 528 kinds measured, three quarters of all | Weber and others 2023 |
| Doubling time | About 8 hours in rich medium; 17.6 hours measured in a serum-free medium | Weber and others 2023; Gaspari and others 2020 |
| Energy | ATP from fermenting glucose, with lactate and acetate as end products; mycoplasmas lack the citric acid cycle | Gaspari and others 2020; Awadh and others 2021; Li and others 2021 |
| Food | Glucose as the main fuel; no amino acids, vitamins or lipids of its own making | Gaspari and others 2020; Awadh and others 2021 |
| Division | In two, by binary fission. The attachment organelle is duplicated first and takes part in the division | Parrott and others 2016; Nakane and others 2021 |
| Movement | Glides on surfaces, attachment organelle first, at up to 1 µm a second | Nakane and others 2015 |

Every fact rests on permissive sources alone, as of 15 November 2026. The papers that
once stood behind some of them, and are now only named as places to read, are in the
section "What rests on non-commercial or unlicensed sources".

**The drawing.** `{"kind": "capsule", "length_um": 2, "across_um": 0.2}`, with one
membrane, no wall, no nucleus, a chromosome of 816 thousand base pairs and 300 ribosomes.
The length and width are the upper ends of the ranges. A rod of that size holds 0.06 µm³,
near the one volume a paper gives. **The ribosome count was 150 until 15 November 2026,**
from a paper under a non-commercial licence; it is now the 300 that an open paper
measured, which doubles the ribosomes the picture shows.

**What the shape list lacks.** No kind can show a cell that narrows at one end. The
attachment organelle is what marks this organism, and its proteins have a mark of their
own on the shelves. A `capsule` would need two more parameters, the length and the width
of a narrower end; the length has a source here (250 to 300 nm), the width has none.

## Which capabilities have a place in it

Of the map's 21 capabilities, 9 are marked absent, 11 present with a note, and cell
chemistry is left out, which means it has a place.

- **Absent because it is a single cell:** gap junctions, gene regulation in tissue, cell
  replacement, mechanics, cell sheets.
- **Absent because it is a bacterium with one membrane:** calcium and the ER,
  mitochondria, Golgi and trafficking.
- **Ion channels: absent.** None of 40 unit signatures and none of seven bacterial channel
  signatures is on any of its 688 proteins, though other mollicutes carry the bacterial
  ones. An eighth, the family of water and glycerol channels, finds the glycerol
  facilitator GlpF, which is not an ion channel.
- **Three placements are judgement, and their notes say so:** membrane voltage (no source
  read measured it), injury and repair (no source), secreted signals (lactate and acetate
  release).

## The protein atlas: none of the 49 units

| Finding | Units |
| --- | --- |
| Found | 0 |
| A different family | 0 |
| Nothing found | 43 |
| Nothing to look for | 6 |

Each of the 43 notes gives the signatures asked, what the same search finds among all
mollicutes, and that the unit's human candidates carry them. Under `extra` are nine of
the organism's own membrane machines: four subunits of the ATP synthase, its one P-type
ATPase, the two parts of a potassium uptake system, the glucose transporter and GlpF.
All nine are listed as `reviewed entry`: each has a curated UniProtKB entry of this
strain. Their notes say that the functions are assigned from sequence and were not
measured in this organism.

## The catalogue

One line for each of the 688 protein products of GenBank U00089.2, with 14 columns. The
README beside it explains each one.

- **From the record:** locus tag, gene, product, length, protein identifier.
- **From UniProt (CC BY 4.0):** accession, curated name, the length of the curated
  sequence, UniProt's level of evidence that the protein exists, the archive identifier
  and the family signatures.
- **From Lluch-Senar and others 2015 (CC BY 4.0):** the paper's class of the gene, and
  its essentiality at the paper's two thresholds. Essentiality is **measured**, by
  transposon mutagenesis in this strain: 342 essential, 91 fitness, 159 non-essential and
  96 non-essential with repeated sequence, at the stringent threshold.
- **UniProt's level of evidence:** 137 at protein level, 3 at transcript level, 385
  inferred from homology, 143 predicted, 19 uncertain.

## The shelves: where each protein sits

The user: "let's have all the shelfs simmilar format inside outside for syn3a and all of
them". `shelves.json` has one shelf, the cell membrane, and one line for each protein.

| Side | Proteins | Basis | Proteins |
| --- | --- | --- | --- |
| outside | 51 | stated | 134 |
| in | 113 | predicted | 174 |
| inside | 234 | by function | 90 |
| not known | 290 | none | 290 |

**What was relied on.** Every placement comes from the protein's reviewed UniProtKB
entry.

- **Stated (134):** the entry states the location on a curator's word or on an experiment
  it cites. Only 17 rest on an experiment; 117 are a curator's inference.
  - Where an entry states that a protein spans the membrane (95 proteins), the segments it
    gives are predicted ones in every case: by UniProt's sequence analysis for 87, by a
    PROSITE rule for 7 and by a HAMAP rule for 1. The statement is the curator's; what
    the curator had to go on was a prediction.
- **Predicted (174):** the entry's statement is made by a rule, by sequence analysis or
  by likeness to another organism's protein. Each is counted once:
  - 92 rest on HAMAP's family rules (83 inside, 9 in the membrane);
  - 51 rest on PROSITE's rules: 45 outside by its lipoprotein rule, and 6 in the membrane
    by three rules on the membrane parts of transporters;
  - 4 rest on UniProt's sequence analysis alone (TMHMM, Memsat, Phobius and a
    hydrophobic moment plot for segments; Phobius, Predotar, SignalP and TargetP for
    signal peptides);
  - 27 rest on likeness alone.
  The file names each tool and rule system among its sources, with its own terms; the
  section on sources below gives the table.
- **By function (90):** only two cases. 77 proteins with no stated place work on the
  ribosome, on RNA, in transcription or on the chromosome, by their keywords. 13 are
  placed at the membrane without a face, and bind ATP or GTP, make ATP or bind DNA, so
  they are on the inner face.
- **Lipoproteins are outside (48 of the 51).** A lipoprotein signal means the protein is
  exported and then held by a lipid at the outer face. That reading is the file's own;
  UniProt records the signal. The other three have an export signal and no anchor.
- **The attachment organelle is a mark, not a shelf.** 15 proteins carry
  `where: attachment organelle`: three span its membrane (the adhesins P1, P40/P90 and
  P30) and twelve are inside it.
- **Four proteins are stated on both sides,** such as the CARDS toxin, mostly inside with
  a share on the surface. They keep the side stated first and carry the mark `also`.

**Districts** are the 2015 paper's 20 classes, by its letters and its own names. They
are not the standard classes of those letters: the paper's `A` is "membrane proteins of
unknown function". Outside, 40 of the 51 are of class M.

**Marks:** essentiality (measured), UniProt's evidence at protein level (137 proteins),
how the side is known, where in the cell, and a second stated side. No amount is given.
`unit` is empty on every line.

**Where the contract did not fit, and what was done.**

- A mark's `source` is given as the name of an entry in `sources`; the contract's example
  shows the word "key".
- One side per protein cannot say "stated on both sides". The mark `also` was added.
- The four sides cannot say "at the membrane, face not stated". One such protein is
  `not known` with the mark `where: at the membrane`.
- `stated` covers both an experiment and a curator's inference. The mark `evidence`
  (experiment, curator, similarity, rule) tells them apart.
- `side_notes` has an entry for every basis, not only `predicted`.

## What could not be determined

- **Where 290 proteins sit.** 163 are named uncharacterised, 72 putative or probable, and
  55 have a plain name, mostly enzymes, with no place stated in their entry. Those enzymes
  are very likely inside. They were not placed by function, because UniProt records two
  of this organism's enzymes on its surface as well as inside.
- **The doubling time at first hand.** Two open papers state about 8 hours in rich medium
  (Weber and others 2023; Gaspari and others 2020, which cites a paper of 2009), and the
  second measured 17.6 hours in a serum-free medium. No growth curve was read.
- **The cell's width and a count of ribosomes at first hand.** The width is from a review.
  The species file's 300 is the median copy number of the ribosomal proteins, measured by
  mass spectrometry; the same paper sets it beside counts of 300 to 500 ribosomes in
  electron tomograms of other papers, whose terms do not allow a copy.
- **Whether it has a respiratory chain.** No permissive source read here says. The
  species file therefore says only that mycoplasmas lack the citric acid cycle; the paper
  that says more is under a non-commercial licence and is named as a place to read.
- **Which ion the P-type ATPase moves.** Its sequence carries the superfamily's signature
  and none of its branches'.
- **Whether the potassium uptake system works as the record names it.** UniProt's curators
  leave both proteins uncharacterised.
- **Its membrane voltage.** Not measured in any source read.
- **Whether every lipoprotein is on the surface.** The placement follows the signal.
- **Which gene makes 689 of 688.**

## Sources and terms

| Source | What is taken | Terms |
| --- | --- | --- |
| GenBank U00089.2 | Locus tags, genes, products, identifiers, lengths; feature counts | "NCBI places no restrictions on the use or distribution of the GenBank data"; submitters may claim rights, and this record states none |
| NCBI RefSeq NC_000912.1 | One count | The same statement |
| UniProt, release 2026_04 | The strain's reviewed entries, the archived sequences with their signatures, control counts, and three help pages that name its predictors | CC BY 4.0 |
| InterPro | The signatures' identifiers and names | CC0 1.0 |
| Lluch-Senar and others 2015, *Mol Syst Biol* 11:780, Supplementary Table S2 and text | Each gene's class and essentiality | CC BY 4.0 |
| Parrott and others 2016; Nakane and others 2015 and 2021 | Numbers and short quotations | CC BY |
| Weber and others 2023, *Mol Syst Biol* 19:e11301 | The copies of the ribosomal proteins, the total of protein molecules, the cell's volume, the doubling time | CC BY 4.0 |
| Gaspari and others 2020, *NPJ Syst Biol Appl* 6:33 | What the cell cannot make, that it ferments glucose, what its model has the ATP synthase do, the doubling times | CC BY 4.0 |
| Awadh and others 2021, *Sci Rep* 11:5650 | The end products of fermentation; that the cell imports its amino acids | CC BY 4.0 |
| Li and others 2021, *AMB Express* 11:26 | That it is a small prokaryote; that mycoplasmas lack the citric acid cycle | CC BY 4.0 |
| EMDB entry EMD-53631 | Its title and release date | CC0 1.0 |

Each of these is permissive. The sources that are not are named in the section "What
rests on non-commercial or unlicensed sources": the data files take nothing from them.
No table, trace or plot from such a source is in any repository file. Of the genome-scale
models of the organism, only the open one of 2020 was read, and no author was contacted.

## How to rebuild

```bash
python3 tools/build_mpneumoniae_atlas.py fetch --evidence DIR --datasets DATA   # network: about 2 minutes, 7 MB
python3 tools/build_mpneumoniae_atlas.py build --evidence DIR --datasets DATA   # offline: about 2 seconds
node --test tests/mpneumoniae_atlas.test.mjs                                    # set MPNEUMONIAE_EVIDENCE and MPNEUMONIAE_DATASETS elsewhere
```

`DATA` holds the downloads, one folder per source with a `MANIFEST.json`; `DIR` holds the
log of what was asked. `fetch` asks only for what is not yet there and never writes in a
folder another agent made. `build` checks every file against the SHA-256 its MANIFEST
gives, stops if a saved source no longer says what the files state, and writes the same
bytes every time; the test rebuilds and compares.

## What rests on non-commercial or unlicensed sources

The project's rule (D173, 15 November 2026) sorts every source into three classes.
**Permissive** (CC BY, CC0, or a plain statement that no restriction is placed): values
and derived data may enter the repository, with attribution. **Non-commercial** (any
CC BY-NC licence): analysis only. **No stated terms**: nothing enters. A data file here
holds no value and no statement from a source of the last two classes; such a source is
named as a pointer, with what is to be read there. A note may cite a single value from
one, with its class beside it.

**Nothing in the data files is taken from such a source.** The shelves do rest on
results that UniProt gives out and that tools and rule systems of other owners computed:
those are set out after the table, with the project's rule on them. On 15 November 2026 every source was classed, in the
files themselves (`class`), and what had rested on a paper that is not permissive was
moved or taken out:

| Source | Class | What it once gave the data files | What stands there now |
| --- | --- | --- | --- |
| Maier and others 2011 | non-commercial (CC BY-NC-SA 3.0) | The ribosome count that was drawn, the copies of a protein, the cell's volume | Weber and others 2023 (CC BY 4.0): the ribosomal proteins' median copies, the total of protein molecules, and a volume. The picture draws 300 ribosomes, not 150 |
| Wodke and others 2013 | non-commercial (CC BY-NC-SA 3.0) | The energy and food facts, a gene count, and the share of energy its model gives the ATP synthase | Gaspari and others 2020, Awadh and others 2021 and Li and others 2021 (all CC BY 4.0) for fermentation, its end products, what the cell cannot make and the citric acid cycle. The gene count, the share of energy and the statement on a respiratory chain are gone from the files |
| Chen and others 2016 | non-commercial (CC BY-NC 4.0) | Nothing in a data file | Named in the atlas's `not_copied` and the README, as not used |
| Himmelreich and others 1996 | no stated terms (free to read, no open licence) | The chromosome's length, a gene count and "no amino acid synthesis", from its abstract | GenBank for the length; Awadh and others 2021 for amino acids. Its gene count is gone from the files |
| Dandekar and others 2000 | no stated terms (free to read, no open licence) | A gene count, from its abstract | The frozen record itself |
| Kühner and others 2009 | no stated terms (not open) | A count of protein complexes, and "among the smallest", from its abstract | Gaspari and others 2020 for "among the smallest". The count of complexes is gone from the files |
| Yus and others 2009 | no stated terms (not open) | The number of nutrients in a defined medium, from its abstract | Gone from the files |
| Hasselbring and others 2006 | no stated terms (free to read, no open licence) | The attachment organelle's core and its lead in gliding, the envelope, "no nucleus", division and gliding, from its abstract | Nakane and others 2015 and 2021, Parrott and others 2016 and Li and others 2021. That gliding is needed for normal division is gone from the files; they say that the attachment organelle takes part in division |

The eight papers stay in the species file as pointers: each says what is to be read
there, and gives no value.

**What UniProt gives out that others computed.** Every placement comes from a reviewed
UniProtKB entry, and UniProt's terms are CC BY 4.0. Its licence page adds: "We cannot
provide unrestricted permission regarding the use of the data, as some data may be
covered by patents or other rights." Where an entry's statement is made by a rule or by
sequence analysis, the tool or rule system behind it has terms of its own. Each was read
at its own page on 15 November 2026 and the page was saved; nothing else was downloaded
from any of them, and no program was run. The shelves name each as a source with
`through: UniProt`.

| Tool or rule system | Its own terms, as read | Class | Read through | Placements that rest on it |
| --- | --- | --- | --- | --- |
| PROSITE (its rules, ProRule) | CC BY-NC-ND 4.0; commercial users pay a licence fee "irrespective of the method by which they access the database" | Non-commercial | UniProt | 51 predicted: 45 outside by the lipoprotein rule PRU00303, and 6 in the membrane by PRU00441, PRU00426 and PRU00427. In 10 more a curator states the place and the entry's segments, signal or lipid anchor carry one of its rules |
| HAMAP (family rules) | CC BY 4.0 | Permissive | UniProt | 92 predicted (83 inside, 9 in the membrane); 1 stated placement whose segments it gives; 9 marks "at the membrane" |
| TMHMM | Academic licence of DTU Health Tech: free to publicly funded institutions for internal research; any other user must obtain a commercial licence, and no use of the program may result in commercialization. A licence of the program: no clause speaks of predictions made with it | Non-commercial | UniProt | With Memsat, Phobius and a hydrophobic moment plot, the four methods behind the segments UniProt predicts in reviewed entries; it keeps a segment that two of them find and does not say which. 5 predicted placements in the membrane (2 of them counted under PROSITE as well), and 87 more where a curator states the place and the segments are such ones alone |
| Phobius | For academic users only: private study, education or nonprofit research. Terms of the program | Non-commercial | UniProt | One of the four for segments and one of the four for signal peptides: the placements counted under TMHMM and SignalP |
| SignalP | Academic licence of DTU Health Tech, as TMHMM's | Non-commercial | UniProt | With Phobius, Predotar and TargetP, the four methods behind the signal peptides UniProt predicts. 1 predicted placement outside, and 2 more where a curator states the place |
| TargetP | Academic licence of DTU Health Tech, as TMHMM's | Non-commercial | UniProt | Those counted under SignalP |
| Memsat | Terms not read: UniProt names it without a version or an address | No stated terms | UniProt | Those counted under TMHMM |
| Predotar | Terms not read: its page answers a program with a check for a browser | No stated terms | UniProt | Those counted under SignalP |

The fourth method for segments, the hydrophobic moment plot of Eisenberg and coworkers,
is a published method; UniProt's page names no program for it. The 27 placements by
likeness alone are the curators' own.

**Two kinds of terms.** PROSITE's terms are of the database itself, of which its rules
are part, and its page says that commercial users pay a licence fee "irrespective of the
method by which they access the database". The licences of TMHMM, SignalP and TargetP and
the terms of Phobius are of the programs: they say who may run them and say nothing of
predictions made with them, and it was UniProt that ran them. These are not the same
kind of dependence, and the counts above keep them apart.

**A lipid-anchor rule of the tool's own was measured here and not adopted.** A rule on
the sequence alone, which for part of 15 November 2026 read Syn3A's lipid anchors
(`docs/SYN3A.md`), was run once, unchanged, on the 688 sequences, and compared with UniProt's own lipoprotein annotation of the same proteins.
The bar was set beforehand: adopt it if the two agree on nine in ten of the proteins
either calls. This is analysis; the protein-by-protein comparison is kept outside the
repository.

| | Proteins |
| --- | --- |
| Called by the rule | 40 |
| Called by UniProt (49 of them by PROSITE's lipoprotein rule) | 52 |
| Called by both | 39 |
| Called by the rule alone | 1 |
| Called by UniProt alone | 13 |
| Agreement: both, over either | 39 of 53, or 74% |

That is below nine in ten, so nothing in M. pneumoniae's placements was changed. Had it
been adopted, 11 of the 13 would have lost their place outside (the other 2 are placed
there on a curator's word), and PROSITE would still stand behind the 6 placements by its
other three rules. The gap is not explained and the rule was not tuned. With the ruling
below there is no need for it: it is in no build, and the rest of what was tried is in
the analysis folder `visualizer-prediction-sources-20261115-01` of the project's
workspace.

**The project's rule (the user, 15 November 2026): a value stands on the terms of the
database it was read from, and the tool behind it is named and counted.** The
coordinating session asked the user whether placement values read from open databases
may stay, with every tool named and counted; the user answered "yes". Every placement
here was read in UniProt's entries, which UniProt gives out under CC BY 4.0, so each
stands as UniProt gives it, and none was changed.

- What was found for the ruling in the saved pages: the programs' licences cover running
  the program, and it was UniProt that ran them and publishes the results under its own
  terms; PROSITE belongs to the SIB Swiss Institute of Bioinformatics, which is one of the
  three institutes that make UniProt (UniProt's own "About" page, saved with the human
  data's downloads under `terms-uniprot-consortium`).
- It is the user's ruling for this project, not a legal opinion. Nothing here says what
  any of these terms allow in law.
- Every tool stays named in the file with its own terms and its count, each such
  placement is said to be predicted wherever it is shown, and the licence test keeps a
  register of them (`tests/licence_classes.test.mjs`), so that a new one is noticed and
  put to the user.

**Values cited in this note only,** each from a source that is not permissive, with its
class beside it where it stands: the gene counts 677 (Himmelreich and others 1996, no
stated terms) and 689 (Wodke and others 2013, non-commercial); the 12 added and one
dismissed (Dandekar and others 2000, no stated terms); the share of 57 to 80% of energy
that the 2013 model gives the ATP synthase (Wodke and others 2013); the 62 and 116
complexes (Kühner and others 2009, no stated terms); the 1,748 data sets (Chen and others
2016, non-commercial); the 140 maps (Dobbs and others 2026, no stated terms).

**Relayed values.** Some statements in the files are made by a CC BY paper that relays
another: a doubling time of about 8 hours (Gaspari and others 2020, citing Yus and others
2009; Weber and others 2023 states it too); that the cell ferments glucose, lacks amino
acid synthesis and lacks the citric acid cycle (Gaspari, Awadh and Li, each citing
earlier work). Each is worded as its open source words it. The three statements on
metabolism come from papers on clinical strains or on mycoplasmas in general, not on
strain M129 alone, and the species file says so with each source.

## For the lead's agent

The lead's agent has audited this organism's public measurements (D173; section 9 of
`docs/SYN3A_MINIMAL_CELL_TRACK.md` on main, 15 November 2026) and recommends it to lead a
later stage on energy, transport and pH. That audit is the lead's; this data is the
viewer's. What it adds:

- **One frozen annotation and a 688-line catalogue keyed to it,** with the six counts of
  the literature set side by side.
- **Licences read for the papers, and a class for each.** The essentiality data are open
  (CC BY 4.0). The protein amounts, the energy paper and the multi-omics resource are
  non-commercial, so by D173 nothing of them is in the repository; four open papers
  stand in their place for what the species file says.
- **Which of the map's capabilities have a place in it,** and the finding that it has no
  recognisable ion channel and one glycerol channel.
- **A side of the membrane for 398 proteins,** with the basis of each.
