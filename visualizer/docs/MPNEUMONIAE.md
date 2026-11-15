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
700" is right as a round number, and the sources give six different counts, from 677 to
724; the table below says what each one counts.

**It is far better annotated than Syn3A.** UniProt holds a reviewed, curated entry for 687
of the 688 proteins. A 2015 paper under an open licence gives every gene a class and a
measured essentiality. So the catalogue carries curated names, a level of evidence and
essentiality for every line.

**Its measured protein amounts are not in the catalogue.** They exist (Maier and others
2011), under a non-commercial licence, so the table is cited and not copied. A few of its
numbers are in the species file.

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
| "Foundational studies use approximately 689–690" | **689 confirmed:** "a single, small chromosome of only 816 394 base pairs, encoding 689 proteins". 690 was not seen | Wodke and others 2013 |
| A 2016 study assembled 1,748 consistently generated multiomics datasets | **Confirmed:** "1748 consistently generated '-omics' data sets", 1,680 of them published before and 68 new. It is under a non-commercial licence | Chen and others 2016 |
| The 2011 paper measures RNA abundance, protein abundance and protein turnover under different conditions | **Confirmed** from its abstract and text. It is under a non-commercial licence | Maier and others 2011 |
| The 2013 paper combines measured growth, glucose use, products and responses to pH | **Confirmed:** it fits "experimentally measured glucose consumption, protein production, as well as ... lactate and acetate secretion", and analyses growth at different pH | Wodke and others 2013 |
| Its figures for ATP spent on maintenance or proton pumping are the model's, not measurements | **Confirmed:** the share of 57 to 80% for the ATP synthase rests on the model, a measured copy number and rates from other organisms | Wodke and others 2013 |
| A September 2026 *Cell* paper reports 140 structural maps from native and antibiotic-treated cells | **Confirmed** from the abstract: "to resolve 140 maps". Published 25 September 2026, doi:10.1016/j.cell.2026.08.054. The paper is not open | Dobbs and others 2026, abstract |
| EMD-53631 is a map of a large ribosomal subunit during its making, in native cells | **Confirmed:** "Map of M. pneumoniae 50S mid biogenesis in native cells", released 23 September 2026 | The EMDB entry |
| Rich measurements of interactions and cellular structures | **Confirmed in part:** a 2009 screen found 62 complexes of one protein and 116 of several | Kühner and others 2009, abstract |
| *M. genitalium*'s 86 gene-disruption strains; *E. coli*'s proteomics | **Not checked:** other organisms | |

## The counts

| Count | Whose | What it counts |
| --- | --- | --- |
| 677 | Himmelreich and others 1996 | the reading frames predicted when the genome was sequenced |
| 688 | Dandekar and others 2000; GenBank U00089.2 | the re-annotation: 12 added and one dismissed. **Frozen here** |
| 689 | Wodke and others 2013 | "encoding 689 proteins", citing the two papers above; which gene makes the difference was not traced |
| 694 | Lluch-Senar and others 2015 | their re-annotation, 32 of them reading frames under 100 residues. Their table lists 49 lettered additions beside the 688 numbered genes |
| 686 | UniProt, release 2026_04 | reviewed entries: two fragments of one gene (MPN_304, MPN_305) share an entry, and MPN_441 has none |
| 724 | NCBI RefSeq NC_000912.1 | the coding sequences that NCBI's own pipeline finds in the same genome today |

The record was frozen because the literature is keyed to it. The lettered additions of
the 2015 paper are not in the catalogue: the record has no such genes, and they have no
protein identifiers to tie to.

## The organism as the viewer will draw it

| Fact | Value | Source |
| --- | --- | --- |
| Shape and size | A thin cell 1 to 2 µm long and 0.1 to 0.2 µm wide, of changeable shape; "about 2 µm long"; a volume of 0.05 µm³ | Parrott and others 2016 (a review, citing a review of 2004); Nakane and others 2015; Maier and others 2011 |
| Attachment organelle | A membrane-bound extension at one pole, 250 to 300 nm long, with a dense core. It carries the adhesins and leads the cell when it glides | Nakane and others 2021; Hasselbring and others 2006, abstract |
| Envelope | One membrane, stiffened by sterols; no cell wall | Parrott and others 2016; Nakane and others 2015 |
| Chromosome | One circle of 816,394 base pairs | GenBank; Himmelreich and others 1996, abstract |
| Ribosomes | About 140 to 150 in a cell | Maier and others 2011, reporting tomograms of 2009. The 2009 papers were not open to read |
| Proteins | 167 copies on average among those measured, from about 2 to about 2,300 | Maier and others 2011 |
| Energy | ATP from fermenting sugar to lactate and acetate; no citric acid cycle and no working respiratory chain | Wodke and others 2013 |
| Food | Glucose as the main source of carbon and energy; no amino acid synthesis; a defined medium with 19 nutrients | Wodke and others 2013; Himmelreich and others 1996 and Yus and others 2009, abstracts |
| Division | In two. The attachment organelle is duplicated first, and gliding is needed for normal division | Parrott and others 2016; Hasselbring and others 2006, abstract |
| Movement | Glides on surfaces, attachment organelle first, at up to 1 µm a second | Nakane and others 2015 |

**The drawing.** `{"kind": "capsule", "length_um": 2, "across_um": 0.2}`, with one
membrane, no wall, no nucleus, a chromosome of 816 thousand base pairs and 150 ribosomes.
The length and width are the upper ends of the ranges. A rod of that size holds 0.06 µm³,
close to the one volume a paper gives.

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
- **Predicted (174):** the entry's location or features come from the sequence: UniProt's
  predictions of membrane-spanning segments and signal peptides, a family rule, or
  likeness to another organism's protein. The file names the predictors, in UniProt's own
  words.
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
- **The doubling time.** No open text read here states it. A reference site lists 20 hours
  and 6 hours from two sources that were not read, so the species file gives none.
- **The cell's width and its ribosome count at first hand.** The width is from a review;
  the ribosome counts are a 2011 paper's report of tomograms of 2009.
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
| Maier and others 2011; Wodke and others 2013 | Numbers and short quotations | CC BY-NC-SA 3.0: tables not copied |
| Chen and others 2016 | One number, for the note's claim | CC BY-NC 4.0: nothing else taken |
| Five papers by their abstracts (Himmelreich 1996, Dandekar 2000, Kühner 2009, Yus 2009, Hasselbring 2006), and Dobbs 2026 | Numbers and facts from the abstracts | Not open; abstracts only |
| EMDB entry EMD-53631 | Its title and release date | CC0 1.0 |

No table, trace or plot from a non-commercial or unlicensed source is in any repository
file. No whole-cell or genome-scale model was read for its files, and no author was
contacted.

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

## For the lead's agent

Decision D173 has the lead's Syn3A agent audit this organism next, for measured public
data to validate against. That audit is the lead's; this data is the viewer's. What it
adds:

- **One frozen annotation and a 688-line catalogue keyed to it,** with the six counts of
  the literature set side by side.
- **Licences read for seven papers.** The essentiality data are open (CC BY 4.0). The
  protein amounts, the energy paper's tables and the multi-omics resource are
  non-commercial, so by D173 their tables stay outside the repository.
- **Which of the map's capabilities have a place in it,** and the finding that it has no
  recognisable ion channel and one glycerol channel.
- **A side of the membrane for 398 proteins,** with the basis of each.
