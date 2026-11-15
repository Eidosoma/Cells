# The human's own proteins, for the atlas's shelves

Made by `tools/build_human_atlas.py` on 2026-11-15 from saved downloads; the same bytes every
time. The form is fixed in `schema/SPECIES_PROTEINS.md`. This is the viewer's reference
data. It is not the engine's protein catalogue and it says nothing about the engine: a
protein here is tied to the law inventory only where the inventory itself names its
accession.

| File | Holds |
| --- | --- |
| `shelves.json` | The shelves, the families' lines on them, and how every side was read |
| `proteins.tsv` | One line for each protein, in the order the lines read them |
| `README.md` | This note |

## What is in, and what is out

- **In: 20,414 proteins.** One for each reviewed entry (Swiss-Prot) of UniProt's human
  reference proteome UP000005640, release 2026_04: the entry's canonical sequence.
- **As a count: 22,131 further isoforms.** The entries describe 42,545 sequences in
  all; each protein carries how many its entry describes (`isoforms`). An isoform is not
  a marker of its own.
- **Out: 243,472 unreviewed entries.** The proteome holds 263,886 entries for
  20,652 genes. The unreviewed ones are computer-annotated sequences, most of them other
  or partial sequences of the same genes; none is listed here.
- **No sequences** are kept, and nothing is taken from the Human Protein Atlas: it is
  kept for a link only.

## The shelves

A shelf is a membrane, and a protein sits outside it, in it or inside it. Curators state
where most of these proteins are, so the human has several shelves, and a protein stands
where its entry first places it.

| Shelf | Membrane | Proteins | Outside | In | Inside | Side not known | Families' lines | Lone | No family |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cell` | Cell membrane | 8,986 | 1,890 | 2,448 | 4,097 | 551 | 1,728 | 2,075 | 1,208 |
| `er` | Endoplasmic reticulum membrane | 832 | 11 | 608 | 126 | 87 | 252 | 261 | 91 |
| `mito` | Mitochondrial inner membrane | 889 | 42 | 187 | 224 | 436 | 193 | 484 | 62 |
| `nucleus` | Nuclear envelope | 4,111 | 0 | 52 | 4,017 | 42 | 752 | 1,074 | 952 |
| `other` | Other membranes | 1,245 | 81 | 633 | 110 | 421 | 398 | 325 | 154 |
| `membrane` | A membrane, not told which | 1,327 | 50 | 1,179 | 11 | 87 | 426 | 320 | 205 |
| | On no shelf | 3,024 | 0 | 0 | 0 | 3,024 | 724 | 625 | 818 |

- **`other`** stands for the cell's remaining membranes together: those of the Golgi
  apparatus, endosomes, lysosomes, peroxisomes and vesicles, and the mitochondrion's outer
  membrane. Each protein there names its compartment in its mark `where`. By the
  compartment of the statement that decided: Golgi apparatus 456, vesicle 207, endosome 194, lysosome 160, mitochondrion outer membrane 101, peroxisome 63, lipid droplet 16, Endoplasmic reticulum-Golgi intermediate compartment 16, cytoplasmic granule 13, melanosome 10, preautophagosomal structure 8, vacuole 1.
  The Golgi apparatus is the one that could be a shelf of its own; it is left here because
  it holds about half of what the smallest shelf holds.
- **`membrane`** is for a membrane that is not named: 1,274 proteins whose entry says
  only "Membrane" (or the endomembrane system), and 53 with no stated place whose
  entry carries a membrane-spanning segment (7) or a signal peptide (46). Its
  "outside" is the side away from the cytoplasm: outside the cell, or within a compartment.
- **Side not known** on a shelf: the entry states the membrane or the compartment and
  not the side. The protein counts for that shelf and is drawn apart beside it.
- **On no shelf**: 3,024 proteins. Their entries state no place of the cell and carry no
  membrane-spanning segment and no signal peptide. Nothing is placed by guess.

## How a protein gets its shelf and side

The rules, in the order they are tried:

| Rule | Basis | Proteins | What it reads |
| --- | --- | ---: | --- |
| place | stated | 9,827 | The place itself is on one side: within a compartment, or beyond a membrane. |
| spans | stated | 4,968 | The entry states that the protein spans the membrane (single-pass or multi-pass). |
| face | stated | 345 | The entry states which face of the membrane the protein is on. |
| anchor | stated | 116 | The entry states a GPI anchor and no face: such an anchor holds a protein on the face away from the cytoplasm. |
| later part | stated | 80 | The first place names no side, and a later statement of the same entry names a part of that place and gives the side. |
| segment | predicted | 112 | The entry states the membrane or the compartment and not the side, and it carries a membrane-spanning segment: in the membrane. |
| signal | predicted | 265 | The entry states the membrane or the compartment and not the side, and it carries a signal peptide and no membrane-spanning segment: on the side away from the cytoplasm. |
| no place: segment | predicted | 7 | No place of the cell is stated, and the entry carries a membrane-spanning segment: in a membrane, not told which. |
| no place: signal | predicted | 46 | No place of the cell is stated, and the entry carries a signal peptide and no segment: beyond a membrane, outside the cell or within a compartment. |
| side not stated | none | 1,624 | The entry states the membrane or the compartment, and nothing in it settles the side. |
| no place | none | 3,024 | No place of the cell is stated and nothing is predicted: on no shelf. |

- **Which statement is read.** 16,853 entries state a place for the protein as a whole;
  376 state one only for named forms, the canonical isoform among them, and that one
  is read; 119 state one only for other named forms (a processed chain, another
  isoform), and the first is read, with the form named in the mark `of`. 44 comments
  on where a protein is during an infection are not read. 11 entries state only a
  place that is not of the cell (a virus particle).
- **The first place decides.** The other statements are kept, in order, in the mark
  `also`. For 59 proteins the first place is within a compartment or beyond a
  membrane while the entry also carries membrane-spanning segments: they stand where the
  first statement puts them.
- **What stands behind the deciding statement** (`evidence`): 8,243 an experiment,
  3,297 likeness to another protein, 2,788 a curator's inference or an author's
  statement, 488 a sequence model or a family rule, 2,521 with no evidence code
  (older curated statements).
- **The two feature rules** (430 proteins) read the entry's membrane-spanning segments
  and signal peptide. UniProt's curators annotate those from experiments, from likeness
  and from prediction; its own help pages name the predictors (TMHMM, Memsat, Phobius
  and a hydrophobic moment plot for the segments; Phobius, Predotar, SignalP and TargetP
  for the signal peptides). A segment is used only where one membrane is meant: not for
  the mitochondrion, whose two membranes are on different shelves, nor for a region of
  the cell that holds other membranes.
- **Spanning is often a prediction too.** Of the 4,968 proteins placed in a membrane
  because the entry states that they span it, the statement itself rests on a sequence
  analysis for 1,451, on a curator's inference for 1,096, on likeness for 592, on
  an experiment for 836, and carries no code for 993. ("A sequence analysis" here counts
  the few that a family rule gives.) The basis is "stated" because the curated entry
  states it.

### The table

Every place an entry states is a term of UniProt's vocabulary (`subcell.txt`). The tool
gives these terms a shelf and says what each names against the shelf's membrane; every
other term takes the line of the terms it is a kind of, else of the term before it in
UniProt's own path for it, else of the terms it is a part of. A term that names a
membrane and resolves to a compartment or a region is that place's membrane.

| Term | Shelf | What it names |
| --- | --- | --- |
| Cell membrane | `cell` | membrane |
| Clathrin-coated pit | `cell` | membrane |
| Cytoplasm | `cell` | inside |
| Cornified envelope | `cell` | inside |
| Secreted | `cell` | outside |
| Extracellular vesicle | `cell` | outside |
| Extracellular vesicle membrane | `cell` | outside |
| Cell surface | `cell` | whole |
| Cell junction | `cell` | whole |
| Cell projection | `cell` | region |
| Synapse | `cell` | region |
| Midbody | `cell` | region |
| Cleavage furrow | `cell` | region |
| Perikaryon | `cell` | region |
| Photoreceptor inner segment | `cell` | region |
| Cell tip | `cell` | region |
| Nucleus | `nucleus` | inside |
| Chromosome | `nucleus` | inside |
| Nucleus envelope | `nucleus` | whole |
| Nuclear pore complex | `nucleus` | whole |
| Endoplasmic reticulum | `er` | whole |
| Endoplasmic reticulum lumen | `er` | inside |
| Sarcoplasmic reticulum | `er` | whole |
| Sarcoplasmic reticulum lumen | `er` | inside |
| Mitochondrion | `mito` | region |
| Mitochondrion envelope | `mito` | region |
| Mitochondrion membrane | `mito` | region |
| Mitochondrion inner membrane | `mito` | membrane |
| Mitochondrion matrix | `mito` | inside |
| Mitochondrion intermembrane space | `mito` | outside |
| Mitochondrion outer membrane | `other` | membrane |
| Golgi apparatus | `other` | whole |
| Golgi apparatus lumen | `other` | inside |
| Endosome | `other` | whole |
| Endosome lumen | `other` | inside |
| Lysosome | `other` | whole |
| Lysosome lumen | `other` | inside |
| Peroxisome | `other` | whole |
| Peroxisome matrix | `other` | inside |
| Vesicle | `other` | whole |
| Cytoplasmic vesicle lumen | `other` | inside |
| Melanosome | `other` | whole |
| Vacuole | `other` | whole |
| Cytoplasmic granule | `other` | whole |
| Cytoplasmic granule lumen | `other` | inside |
| Preautophagosomal structure | `other` | whole |
| Endoplasmic reticulum-Golgi intermediate compartment | `other` | whole |
| Endoplasmic reticulum-Golgi intermediate compartment lumen | `other` | inside |
| Lipid droplet | `other` | region |
| Membrane | `membrane` | membrane |
| Endomembrane system | `membrane` | membrane |
| Virion | | elsewhere |
| Target membrane | | elsewhere |

What a term names: **membrane**, the shelf's membrane, or a part of it; **inside**, what the membrane encloses; **outside**, what lies beyond the membrane; **whole**, a compartment that one membrane bounds, or a structure at the membrane, with no part or face named; **region**, a region with more than one membrane, or none; **elsewhere**, not a place of the cell.

The places that decide most often (200 different ones decide for at least one
protein; `shelves.json` lists all 241 that the entries state, under `places`):

| Place, in UniProt's words | Shelf | What it names | Proteins |
| --- | --- | --- | ---: |
| Nucleus | `nucleus` | inside | 3,553 |
| Cell membrane | `cell` | membrane | 2,775 |
| Cytoplasm | `cell` | inside | 2,665 |
| Secreted | `cell` | outside | 1,359 |
| Membrane | `membrane` | membrane | 1,232 |
| Endoplasmic reticulum membrane | `er` | membrane | 643 |
| Cytoplasm, cytosol | `cell` | inside | 423 |
| Mitochondrion | `mito` | region | 356 |
| Cytoplasm, cytoskeleton | `cell` | inside | 317 |
| Mitochondrion inner membrane | `mito` | membrane | 283 |
| Golgi apparatus membrane | `other` | membrane | 261 |
| Nucleus, nucleolus | `nucleus` | inside | 227 |
| Secreted, extracellular space, extracellular matrix | `cell` | outside | 183 |
| Mitochondrion matrix | `mito` | inside | 162 |
| Cytoplasm, cytoskeleton, microtubule organizing center, centrosome | `cell` | inside | 133 |
| Apical cell membrane | `cell` | membrane | 110 |
| Mitochondrion outer membrane | `other` | membrane | 101 |
| Lysosome membrane | `other` | membrane | 88 |
| Cytoplasm, cytoskeleton, cilium axoneme | `cell` | inside | 77 |
| Endoplasmic reticulum | `er` | whole | 74 |
| Cytoplasm, perinuclear region | `cell` | inside | 74 |
| Nucleus, nucleoplasm | `nucleus` | inside | 65 |
| Lysosome | `other` | whole | 64 |
| Endoplasmic reticulum lumen | `er` | inside | 61 |

## Families that open, proteins on their own, and no family

- **Families.** A family is an InterPro entry of the type Family (InterPro 111.0), chosen
  by the rule of the planarian's file, so that a family has the same id in both: the
  narrowest family among the InterPro entries UniProt gives the protein; of several
  unrelated ones (1,495 proteins), the deepest in InterPro's tree, then the smallest
  here, then the first. 7,948 families hold 16,924 proteins. The largest are
  Olfactory receptor (348), Immunoglobulin Variable Light Chain (86) and Peptidase S1A, chymotrypsin family (65).
- **A family has a line for each shelf that holds members of it**, and one with no shelf
  for its members that are on none: 4,473 lines of 2,784 families. 439 lines hold five
  proteins or more, 2,072 hold two to four and 1,962 hold one. Each line gives the
  family's members in all (`total`): 579 families have five or more, and 184 of
  those have fewer than five on every shelf.
- **On their own.** 5,164 families have a single member in this catalogue. A family of
  one does not open, so it has no line: its protein is listed under `lone`, in 160 parts,
  one for each shelf, district and side, and names its family in its mark `family`.
  Giving each of them a line would take the file past its limit of 1 MB.
- **No family.** 3,490 proteins carry no family signature. None is dropped: they are
  listed under `no_family`, in parts, each with a line for each shelf. 351 parts are
  InterPro superfamilies, a wider grouping by shared structure, and hold 2,476; 440
  proteins carry only a domain, repeat or site signature; 574 carry no signature
  of any kind.

A line stands in a district:

| District | Families' lines | Their proteins | Lone proteins | From |
| --- | ---: | ---: | ---: | --- |
| Channels | 104 | 286 | 183 | Gene Ontology terms: channel activity (GO:0015267) |
| Transporters and pumps | 310 | 721 | 248 | Gene Ontology terms: transporter activity (GO:0005215), transmembrane transport (GO:0055085), monoatomic ion transport (GO:0006811) |
| Receptors and signalling | 1,083 | 3,517 | 942 | Gene Ontology terms: signaling receptor activity (GO:0038023), molecular transducer activity (GO:0060089), signal transduction (GO:0007165), signaling receptor binding (GO:0005102) |
| DNA, RNA and making proteins | 993 | 2,559 | 1,442 | Gene Ontology terms: gene expression (GO:0010467), DNA metabolic process (GO:0006259), DNA binding (GO:0003677), RNA binding (GO:0003723), transcription regulator activity (GO:0140110), regulation of DNA-templated transcription (GO:0006355), chromatin organization (GO:0006325), ribosome (GO:0005840), catalytic activity, acting on a nucleic acid (GO:0140640) |
| Protein folding, change, sorting and breakdown | 504 | 1,216 | 360 | Gene Ontology terms: protein folding (GO:0006457), proteolysis (GO:0006508), protein modification process (GO:0036211), protein transport (GO:0015031), vesicle-mediated transport (GO:0016192), catalytic activity, acting on a protein (GO:0140096) |
| Cytoskeleton, movement and adhesion | 382 | 1,199 | 413 | Gene Ontology terms: cytoskeleton (GO:0005856), cytoskeleton organization (GO:0007010), cytoskeletal motor activity (GO:0003774), microtubule-based movement (GO:0007018), cell adhesion (GO:0007155), extracellular matrix (GO:0031012), cilium (GO:0005929), structural molecule activity (GO:0005198) |
| Enzymes and metabolism | 456 | 963 | 533 | Gene Ontology terms: catalytic activity (GO:0003824), metabolic process (GO:0008152) |
| Other functions | 549 | 1,077 | 833 | The line's proteins carry Gene Ontology terms, and none of the districts' terms |
| Not classed by function | 92 | 222 | 210 | The line's proteins carry no Gene Ontology term |

A protein's Gene Ontology terms are those InterPro maps to any of its signatures and
those UniProt gives its entry. The protein falls in the first district, in the order of
the table, one of whose terms it carries; a line stands where most of its classed members
fall. The districts, their terms and their order are the planarian's, so the two species
can be compared. They fit the human less well: UniProt gives nearly every human entry
terms of its own, so 8,688 proteins carry the terms of two districts or more and the
order decides between them.

## Tied to the atlas

The inventory's candidate products name 93 human entries, for 43 of its units. Every
one is a protein of this catalogue and carries its units' ids (`units`), and so do the
lines that hold them (32 lines). 2 of them have no family and stand in a part
of `no_family`.

## The marks

| Mark | What it says | Values | Note |
| --- | --- | --- | --- |
| `isoforms` | Isoforms described | a number | The canonical sequence and the other sequences its entry describes. The marker stands for the canonical one. |
| `seen` | Evidence that the protein exists | protein, transcript, homology, predicted, uncertain | UniProt's level of evidence for the entry: at protein level, at transcript level, inferred from homology, predicted, or uncertain. |
| `evidence` | What stands behind the stated place | experiment, similarity, curator, rule, not given | From UniProt's evidence codes on the statement: experiment: an experiment in a paper the entry cites; similarity: likeness to a protein of which it is known; curator: a curator's inference, or an author's statement that names no experiment; rule: a sequence model or a family rule, applied by a curator; not given: the entry gives no code, an older curated statement. Of several, the first in this order. |
| `where` | Stated place | a text | The statement that decided the shelf, in UniProt's words: the place, then the topology and the face where the entry states them. |
| `also` | Also stated | a text | The entry's other statements of place, in order and in UniProt's words. |
| `family` | Family, of which it is the only member here | a text | The InterPro family's accession and name, for a protein listed among the only members of their families. |
| `of` | Stated for | a text | The named form of the protein that the place is stated for, where the entry states none for the protein as a whole or for its canonical isoform. |

## `proteins.tsv`

20,414 lines under a header, tab-separated, in the order the lines of `shelves.json`
read them: every line of the families, then every part of `lone`, then every part of
`no_family`; within each, by gene name.

| Column | Meaning |
| --- | --- |
| `id` | The entry's UniProtKB accession |
| `gene` | Its first gene name, where it has one |
| `name` | The protein's recommended name |
| `length` | Residues of the canonical sequence |
| `isoforms` | Sequences the entry describes, the canonical one included |
| `seen` | UniProt's level of evidence that the protein exists: 1 protein, 2 transcript, 3 homology, 4 predicted, 5 uncertain |
| `under` | The InterPro family it is filed under; for a protein with no family, the part: a superfamily's accession, `other-signature` or `no-signature` |
| `shelf` | Its shelf, or empty for none |
| `side` | `outside`, `in`, `inside` or `not known` |
| `basis` | `s` stated, `p` predicted, `n` none |
| `evidence` | What stands behind the stated place: `e` experiment, `s` similarity, `c` curator, `r` rule, `n` not given; empty where no place of the cell is stated |
| `place` | The statement that decided, in UniProt's identifiers without their prefix: the place, then the topology and the face where stated, joined by a full stop (`0039.9909` is SL-0039 with SL-9909). `shelves.json` gives the words of each under `place_words` |
| `also` | The entry's other statements, written the same way, separated by commas |
| `units` | The inventory units that name this entry |
| `family` | For a protein listed under `lone`, its family's name |
| `of` | The named form the place is stated for, where it is not the protein as a whole or its canonical isoform |

**How a line's members are read.** The lines follow one another in the table: a line's
members are the next `count` lines. For the page they are cut into 11 files of at most
2,000 members: a file holds consecutive lines and a line is never split. `shelves.json`
gives each line's file and its place there (`file`, `at`). `python3
tools/build_human_atlas.py members --out DIR` writes the files; they are published
beside the page and are not kept in the repository.

## Sources and terms

| Source | Terms | Class | What was taken |
| --- | --- | --- | --- |
| UniProt 2026_04 | CC BY 4.0 | permissive | For each reviewed entry of the human reference proteome: its name, gene, length and level of evidence, the places it states with the evidence for each, its membrane-spanning segments and signal peptide, the isoforms it describes, the InterPro entries and the Gene Ontology terms UniProt gives it; and UniProt's vocabulary of places. Its own pages name the programs behind the segments and signal peptides it predicts (TMHMM, Memsat, Phobius and a hydrophobic moment plot for the segments; Phobius, Predotar, SignalP and TargetP for the signal peptides); each is a source below, with what rests on it. Of UniProt's own: 2 statements that a protein spans a membrane rest on a rule of its rule base (RuleBase), and 13 stated places rest on a sequence analysis in entries that carry no segment or signal peptide of that kind, for which it names no program |
| InterPro 111.0 | CC0 1.0 | permissive | The type and name of each entry, the tree of broader and narrower entries, and the mapping of entries to Gene Ontology terms |
| Gene Ontology releases/2026-07-26 | CC BY 4.0 | permissive | The names of terms and which term is a kind or a part of which; no term's text is copied beyond the names of the districts' terms |
| PROSITE | CC BY-NC-ND 4.0; commercial users are asked to pay a yearly licence fee | non-commercial (read through UniProt) | Nothing was downloaded from it but its statement of terms, and nothing of it is copied. Its rules (ProRule) are named in UniProt's entries as what stands behind a statement. 289 placements rest on them alone: 281 by the statement of place that decides the shelf (44 rules; most often PRU00108 for 71, PRU00981 for 36, PRU00187 for 35), 11 by the statement that the protein spans the membrane, and 1 by a side read here from segments that a rule gives. They were read in UniProt's entries. |
| HAMAP | CC BY 4.0 | permissive (read through UniProt) | Nothing was downloaded from it but its statement of terms. Its family rules are named in UniProt's entries as what stands behind a statement. 54 placements rest on them alone: 39 by the statement of place that decides the shelf (37 rules), 14 by the statement that the protein spans the membrane, 4 by the stated face, and 2 by a side read here from segments that a rule gives. |
| TMHMM | Academic licence of DTU Health Tech: free to publicly funded academic, education or research institutions for internal research, and any other user must obtain a commercial licence. It is a licence of the program: no clause speaks of predictions made with it | non-commercial (read through UniProt) | Nothing was downloaded from it but its statement of terms, and the program was not run here. One of the four methods UniProt names for the membrane-spanning segments of its reviewed entries; it keeps a segment that at least two of them find, and does not say which. 1,533 placements rest on segments that an entry gives by sequence analysis alone: 103 are read here from such segments (basis predicted; 119 are read from segments in all), and behind a curator's statement 1,429 are said to span the membrane on a sequence analysis and 148 have a stated place that rests on a sequence analysis in an entry with such segments. |
| Phobius | For academic users only: the program may be used for private study, education or nonprofit research, and other users are asked to write to its author. The terms are of the program: they do not speak of predictions made with it | non-commercial (read through UniProt) | Nothing was downloaded from it but its statement of terms, and the program was not run here. One of the four methods UniProt names for the membrane-spanning segments of its reviewed entries; it keeps a segment that at least two of them find, and does not say which; and one of the four it names for signal peptides. The placements are those counted under TMHMM (1,533) and under SignalP (256). |
| SignalP | Academic licence of DTU Health Tech: free to publicly funded academic, education or research institutions for internal research, and any other user must obtain a commercial licence. It is a licence of the program: no clause speaks of predictions made with it | non-commercial (read through UniProt) | Nothing was downloaded from it but its statement of terms, and the program was not run here. One of the four methods UniProt names for the signal peptides of its reviewed entries; it keeps a signal that at least two of them find, and does not say which. 256 placements rest on a signal peptide that an entry gives by sequence analysis alone: 249 are read here from such a signal (basis predicted; 311 are read from a signal peptide in all), and behind a curator's statement 7 have a stated place that rests on a sequence analysis in an entry with such a signal and no such segment. |
| TargetP | Academic licence of DTU Health Tech: free to publicly funded academic, education or research institutions for internal research, and any other user must obtain a commercial licence. It is a licence of the program: no clause speaks of predictions made with it | non-commercial (read through UniProt) | Nothing was downloaded from it but its statement of terms, and the program was not run here. One of the four methods UniProt names for the signal peptides of its reviewed entries; it keeps a signal that at least two of them find, and does not say which. The placements are those counted under SignalP (256). |
| Memsat | Terms not read: UniProt's help names Memsat without a version or an address, so no page of terms could be tied to the program it runs | no stated terms (read through UniProt) | Nothing was downloaded from it. One of the four methods UniProt names for the membrane-spanning segments of its reviewed entries; it keeps a segment that at least two of them find, and does not say which. The placements are those counted under TMHMM (1,533). |
| Predotar | Terms not read: the program's own page answers this tool with a check for a browser, so its terms could not be read | no stated terms (read through UniProt) | Nothing was downloaded from it. One of the four methods UniProt names for the signal peptides of its reviewed entries; it keeps a signal that at least two of them find, and does not say which. The placements are those counted under SignalP (256). |
| big-PI | No open licence stated: the predictor's own page gives no terms of use | no stated terms (read through UniProt) | Nothing was downloaded from it but its own page, and the program was not run here. The predictor that UniProt's help names for the GPI anchors it predicts. 4 placements rest on a GPI anchor that the entry states on a sequence analysis alone: such an anchor puts the protein on the face away from the cytoplasm. |

- Each source's terms were read in its own page, saved beside the downloads, before
  anything of it was used; the build checks the sentence in each saved page.
- **What UniProt's entries state by rule or by sequence analysis is named.** Each rule
  system and each program behind such statements is a source of its own, read through
  UniProt, with the placements that rest on it alone: PROSITE's rules 289, HAMAP's 54,
  the four programs UniProt names for the segments it predicts 1,533, the four for signal
  peptides 256, and the one for GPI anchors 4. Everything was read in UniProt's
  entries, which are CC BY 4.0; no file of a rule system was downloaded and no program
  was run. PROSITE's terms do not allow commercial use; TMHMM, SignalP, TargetP and
  Phobius are given out for academic use; the terms of Memsat and Predotar could not be
  read, and the page of the GPI predictor states none. `docs/HUMAN_PROTEOME.md` sets out
  both kinds of dependence for each: a side this file reads from a feature, and a
  curator's statement that itself rests on such a result.
- **The Human Protein Atlas** states that it is licensed under CC BY 4.0 for all
  copyrightable parts of its database, and warns that data of third parties in it may
  carry other terms. Nothing is taken from it: it is kept for a link from each protein,
  which the page's link patterns do not hold yet.

## Rebuild

    python3 tools/build_human_atlas.py fetch --datasets DATA
    python3 tools/build_human_atlas.py build --datasets DATA
    python3 tools/build_human_atlas.py members --out OUT

`fetch` is the only step that uses the network. `build` reads only the saved downloads
and the inventory snapshot, and checks each file against its MANIFEST.
