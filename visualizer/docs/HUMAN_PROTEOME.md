# The human proteome on the atlas's shelves: what is drawn, where each protein stands, and how sure that is

**Status: made by the visualizer session, 15 November 2026, for the user and the lead.**
The user, of the species' own proteins on shelves: "let's have all the shelfs simmilar
format inside outside for syn3a and all of them - humans have a 100k ones so let's maybe
think about that last", and "we should show them all but maybe cool expandable protein
families, same for humans". This note says what was made, how many proteins are in and
out, how each gets its shelf and side, and what could not be determined. Numbers are as
built on 15 November 2026; the build prints them again.

| | |
| --- | --- |
| The proteins on the shelves | `data/proteins/human/shelves.json`, in the form `schema/SPECIES_PROTEINS.md` fixes (758 KB) |
| The table of proteins | `data/proteins/human/proteins.tsv` (20,414 proteins, 2.1 MB) and its `README.md` |
| The tool | `tools/build_human_atlas.py`: `fetch` uses the network, `build` and `members` do not |
| The check | `node --test tests/human_atlas.test.mjs` (14 tests) |
| The downloads | `/mnt/datasets/Cells/human/`, one folder per source with a `MANIFEST.json`. Six folders are this tool's (29 files, 45 MB). The pages of terms of the rule systems and programs behind UniProt's statements are the ones the other species' tools saved, read where they are; the other folders there were not read |
| The analysis | `/mnt/workspaces/Cells/visualizer-human-proteome-20261115-01`: what the build counted, the members' files as cut, and the same catalogue built with a line for every family |

This is the viewer's reference data. It is not the engine's protein catalogue, and it
says nothing about what the engine models: a protein here is tied to the law inventory
only where the inventory itself names its accession.

## Answer

**20,414 proteins are drawn, one for each reviewed human entry of UniProt.** That is one
canonical protein for each curated entry of the human reference proteome, close to one
for each of its 20,652 genes.

**The "100k" counts more than that, and nothing of it is hidden.** The reviewed entries
describe 22,131 further isoforms, so 42,545 sequences in all; each protein carries the
number its entry describes. The proteome also holds 243,472 unreviewed entries, which
are computer-annotated sequences, most of them other or partial sequences of the same
genes: 263,886 entries in all. The unreviewed ones are not listed. A hundred thousand
is about what one gets by counting every distinct sequence a gene can give; one marker
each for those would draw the same protein several times.

**Where a protein stands is what its curated entry states first.** 15,336 of the 20,414
have a side that the entry's own words give, 430 a side read from the entry's membrane
segments or signal peptide, and 4,648 have none: 1,624 of those are on a shelf with the
side not known, and 3,024 are on no shelf at all, because their entries state no place.

**Every protein is shown, in one of three ways.** 2,784 families that have two members
or more hold 11,760 proteins, in 4,473 lines: one line for each shelf that holds members
of a family. 5,164 proteins are the only human member of their family. 3,490 have no
family and are filed under a wider grouping.

## What is in, and what is out

| | Count | In the files |
| --- | ---: | --- |
| Reviewed entries of the reference proteome UP000005640 | 20,414 | Each is a protein of the table and a member of one line |
| Further isoforms those entries describe | 22,131 | A count on each protein (`isoforms`); 42,545 sequences with the canonical ones |
| Unreviewed entries of the proteome | 243,472 | Not listed |
| Entries of the proteome in all | 263,886 | For 20,652 genes |

UniProt release 2026_04. Of the 20,414, 18,653 have evidence at protein level, 634 at
transcript level, 538 are inferred from homology, 79 are predicted and 510 are
uncertain: each carries its level (`seen`). 17,348 state a place and 3,066 state none.

## The shelves, and the proteins on each

| Shelf | Membrane | Proteins | Outside | In | Inside | Side not known |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `cell` | Cell membrane | 8,986 | 1,890 | 2,448 | 4,097 | 551 |
| `er` | Endoplasmic reticulum membrane | 832 | 11 | 608 | 126 | 87 |
| `mito` | Mitochondrial inner membrane | 889 | 42 | 187 | 224 | 436 |
| `nucleus` | Nuclear envelope | 4,111 | 0 | 52 | 4,017 | 42 |
| `other` | Other membranes | 1,245 | 81 | 633 | 110 | 421 |
| `membrane` | A membrane, not told which | 1,327 | 50 | 1,179 | 11 | 87 |
| | On no shelf | 3,024 | | | | 3,024 |
| | All | 20,414 | 2,074 | 5,107 | 8,585 | 4,648 |

- **`other`** holds 1,245 proteins: Golgi apparatus 456, vesicles 207, endosomes 194,
  lysosomes 160, the mitochondrion's outer membrane 101, peroxisomes 63, and six
  smaller places 64. **No further shelf was added.** The Golgi apparatus is the one
  candidate: with 456 proteins it would be about half the size of the smallest shelf
  (the endoplasmic reticulum, 832). That is not plain enough to decide alone; it is one
  line of the tool's table to give it a shelf.
- **`membrane`**, the shelf of a membrane that is not named, holds 1,327: (a) 1,274
  whose entry says only "Membrane" or "Endomembrane system", and (b) 53 with no stated
  place of the cell, 7 of them with a membrane-spanning segment and 46 with a signal
  peptide and none. Group (b) is small because UniProt's curators write "Membrane" in
  nearly every entry to which they give a segment. Group (a) is what makes the shelf
  worth having: 17 of the inventory's own channel and pump entries are on it.
- **The mitochondrion is half unplaced.** 436 of its 889 proteins have no side. For 356
  the statement that decides is "Mitochondrion" with no part of it named, and for 46 it
  is "Mitochondrion membrane", which UniProt uses when it is not known whether the inner
  or the outer one is meant.

## How a protein gets its shelf and side

The table that maps UniProt's places to shelves is at the top of the tool, 53 lines. It
is applied to UniProt's own vocabulary of places (`subcell.txt`): a term that has no
line takes the line of the terms it is a kind of, else of the term before it in
UniProt's own path for it, else of the terms it is a part of. The entries state 241
different places, and 200 of them decide for at least one protein; `shelves.json` lists
all of them with the shelf each resolves to (`places`). The build stops at a place it
cannot resolve, and at one that two lines claim.

The rules, in the order they are tried, with the proteins each places:

| Rule | Basis | Proteins | What it reads |
| --- | --- | ---: | --- |
| place | stated | 9,827 | The place is itself on one side: within a compartment, or beyond a membrane |
| spans | stated | 4,968 | The entry states that the protein spans the membrane |
| face | stated | 345 | The entry states which face of the membrane it is on |
| anchor | stated | 116 | A GPI anchor with no face stated: on the face away from the cytoplasm |
| later part | stated | 80 | The first place names no side; a later statement names a part of it and gives the side |
| segment | predicted | 112 | The membrane or compartment is stated, not the side; the entry carries a membrane-spanning segment |
| signal | predicted | 265 | The same, with a signal peptide and no segment: the side away from the cytoplasm |
| no place: segment | predicted | 7 | No place stated; a segment: in a membrane that is not named |
| no place: signal | predicted | 46 | No place stated; a signal peptide and no segment: beyond a membrane that is not named |
| side not stated | none | 1,624 | The membrane or compartment is stated and nothing settles the side |
| no place | none | 3,024 | No place stated and nothing predicted: on no shelf |

What was decided, and why:

- **The first stated place decides** (the contract). The others are kept in order in
  the mark `also`. For 59 proteins the first place is within a compartment or beyond a
  membrane although the entry carries membrane-spanning segments: a receptor whose entry
  lists "Cytoplasm" first stands inside. They are left where the first statement puts
  them.
- **Which statement is the entry's.** 16,853 entries state a place for the protein as a
  whole, and that is read first; 155 of them also state one for the canonical isoform,
  which is not read. So basigin, one of the inventory's entries, stands in "another
  membrane": its entry's statement for the protein as a whole is "Melanosome", and the
  cell membrane is stated for its isoforms. 376 state one only for named forms, the canonical isoform among them, and that
  one is read. 119 state one only for other forms (a processed chain, another isoform):
  the first is read and the form is named in the mark `of`. 44 comments on where a
  protein is during an infection are not read; one entry lists a virus particle before
  the endoplasmic reticulum for that reason. 11 entries state only a place that is not
  of the cell (a virus particle): they are treated as stating none.
- **A stated membrane plus a segment in the entry makes "in"** (112 proteins, basis
  `predicted`). It applies where one membrane is meant: the stated place is a membrane
  with no word on spanning, or a compartment that one membrane bounds (the endoplasmic
  reticulum, the Golgi apparatus, a lysosome, a vesicle), or a structure at one membrane
  (a cell junction, the nuclear envelope). It does not apply where the entry says the
  protein is peripheral or lipid-anchored, in the mitochondrion (two membranes, on two
  shelves), in a lipid droplet (a single layer that nothing spans), or in a region of
  the cell that holds other membranes (a cilium, a dendrite, a synapse).
- **A signal peptide with no segment puts a protein on the side away from the
  cytoplasm** (265 proteins): outside the cell for the cell membrane, within the
  compartment for the endoplasmic reticulum and the compartments of the secretory
  pathway. UniProt's own page says of signal peptides that they are found in proteins
  "destined to be either secreted/extracellular/periplasmic/etc., retained in the lumen
  of the endoplasmic reticulum, of the lysosome or of any other organelle along the
  secretory pathway". **This rule goes beyond what was asked for**, which was the segment
  rule; it is counted apart so that it can be struck: its 265 proteins would then be
  "side not stated".
- **A GPI anchor with no face stated** (116) is read as the face away from the
  cytoplasm. UniProt's page on lipid anchors: "the addition of a GPI-anchor may serve to
  anchor extracellular proteins to the outer face of the plasma membrane".
- **Chromosomes are placed inside the nucleus** (54 proteins by "Chromosome", 18 by its
  parts). The vocabulary does not say so: it is this file's reading, true except while a
  cell divides.
- **Not settled, and left not known.** 270 proteins that an entry calls peripheral and
  118 it calls lipid-anchored, with no face stated. UniProt's page says that
  myristoylation, palmitoylation and prenylation hold proteins at "the inner face of the
  plasma membrane"; reading the kind of lipid from each entry would place most of the
  118. It was not done.

**What stands behind the deciding statement** (`evidence`), for the 17,337 proteins
that have one: an experiment 8,243, likeness to another protein 3,297, a curator's
inference or an author's statement 2,788, a sequence model or a family rule 488, and no
evidence code 2,521 (statements older than UniProt's evidence codes).

**"Stated" is not "measured".** Of the 4,968 proteins said to span a membrane, the
statement rests on a sequence analysis or a family rule for 1,451, on a curator's
inference for 1,096, on likeness for 592 and on an experiment for 836; 993 carry no code. The basis is
`stated` because the curated entry states it; the mark `evidence` is of the place.

## Families that open, proteins on their own, and no family

A family is an InterPro entry of the type Family (InterPro 111.0, the release of the
planarian's file), chosen by the planarian's rule: the narrowest family among the
InterPro entries UniProt gives the protein. So a family has the same id and name in
both species: 3,207 of the planarian's 3,457 families are among the human's 7,948, and
1,331 of them have lines here (the others are families of one in the human).

| | Families or parts | Proteins |
| --- | ---: | ---: |
| Families of two or more | 2,784 | 11,760 |
| Families of one | 5,164 | 5,164 |
| No family: under a superfamily | 351 | 2,476 |
| No family: a domain, repeat or site only | | 440 |
| No family: no signature at all | | 574 |

- **Sizes.** 5,164 families have one human member, 2,205 have two to four, 579 have five
  or more, 183 have ten or more and 7 have fifty or more. The largest are the olfactory
  receptors (348), the variable chains of antibodies (86) and the chymotrypsin family of
  peptidases (65).
- **A family has one line for each shelf that holds members of it**: 4,473 lines for the
  2,784 families. 439 lines hold five proteins or more, 2,072 hold two to four and 1,962
  hold one.
- **Of the 579 families of five or more, 184 have fewer than five on every shelf.**
  Drawn by the size of the line, a third of the larger families would be seen only
  inside a gathering of small ones. Each line therefore carries the family's members in
  all (`total`), so that the drawing can give a line its own marker by the size of its
  family: 1,223 lines belong to families of five or more.
- **A family of one has no line.** Its protein is listed under `lone`, in 160 parts, one
  for each shelf, district and side, and names its family in its mark `family`. This is
  the one place where the files go beyond the contract as it stood, and it was forced by
  size: see the next section.

## The size of the file, and the one choice it forced

The contract keeps a species' file under 1 MB. Neither layout that was foreseen fits:

| Layout | Lines of families | Size of `shelves.json` | The folder |
| --- | ---: | ---: | ---: |
| A line for every family on each shelf (built, kept beside the analysis) | 9,637 | 1.40 MB | 3.39 MB |
| One line for each family, with its counts by shelf (its lines measured, not built) | 7,948 | about 1.35 MB | |
| As built: a line on each shelf for a family of two or more; the families of one listed together | 4,473, and 160 parts | 0.76 MB | 2.92 MB |

Half the bytes of the first two are the 5,164 families of one: each would be a line that
says of a single protein what the protein's own line says. A family of one does not
open, so it was given no line. Nothing is lost: each such protein is in the table, is
drawn (in the part of its shelf, district and side), and names its family. The choice is
one constant of the tool (`LONE_UP_TO`); with 0 it builds the first layout, which is
kept beside the analysis for comparison.

## Districts

The nine districts, their Gene Ontology terms and their order are the planarian's, so
that the two species can be compared. A protein's terms are those InterPro maps to its
signatures and those UniProt gives its entry.

| District | Proteins by their own terms |
| --- | ---: |
| Channels | 481 |
| Transporters and pumps | 986 |
| Receptors and signalling | 4,649 |
| DNA, RNA and making proteins | 4,925 |
| Protein folding, change, sorting and breakdown | 1,876 |
| Cytoskeleton, movement and adhesion | 1,850 |
| Enzymes and metabolism | 1,717 |
| Other functions | 2,996 |
| Not classed by function | 934 |

**Where this fits the human badly.** The planarian's proteins carry few terms, so the
first district that matches is nearly the only one. Human entries are annotated richly:
8,688 proteins carry the terms of two districts or more, and the order of the list
decides. "Receptors and signalling" comes third and takes 4,649 proteins, a quarter of
the proteome, because "signal transduction" is given to kinases, adaptors and
transcription factors alike: 1,093 proteins that are also in "DNA, RNA and making
proteins" stand under signalling. "Enzymes and metabolism" comes last and keeps 1,717,
though far more human proteins are enzymes. "Other functions" holds 2,996, the immune
system's proteins among them. A district list made for the human would name immunity
and would split signalling; that is a choice for the drawing, and it would break the
comparison with the planarian.

## Tied to the atlas

The inventory's candidate products name 93 human entries, for 43 of its 49 units. All 93
are proteins of this catalogue, each with its units' ids, and the lines that hold them
carry the ids too. None is missing.

- 84 of the 93 are in a membrane: 55 in the cell membrane, 17 in a membrane that is not
  named, 8 in the endoplasmic reticulum's, 2 in the mitochondrion's inner membrane, 1 in
  the nuclear envelope and 1 in another membrane.
- 8 are not, and should not be: the beta subunits of calcium channels (3) and of
  potassium channels (3) are inside the cell, and two parts of the mitochondrial
  uniporter lie between the mitochondrion's membranes.
- 1 is on no shelf: a fourth beta subunit of calcium channels (CACNB4), whose entry
  states no place.
- 2 have no family and stand in a part of `no_family`.

## What could not be determined

- **Which side**, for 1,624 proteins on a shelf, and **any place at all**, for 3,024.
  Nothing is placed by guess. The planarian's rule would call a protein with no segment
  and no signal "inside"; it was not used, because for a curated proteome the absence of
  a statement is not a prediction.
- **Which mitochondrial membrane**, for the 46 proteins of "Mitochondrion membrane", and
  which part of the mitochondrion for 356 more.
- **Which membrane**, for the 1,327 proteins of the shelf `membrane`.
- **The face**, for 388 peripheral and lipid-anchored proteins.
- **Whether a protein that is "stated" to span a membrane was seen to**: the entries
  give the kind of evidence, and for 1,451 of 4,968 it is a sequence analysis or a rule.
- **Where the same protein is at other times.** Only the first stated place decides; a
  protein that moves between the cytoplasm and the nucleus stands in one of them.

## Sources and terms

| Source | Its terms, as read at its own page | What was taken |
| --- | --- | --- |
| UniProt, release 2026_04 | "We have chosen to apply the Creative Commons Attribution 4.0 International (CC BY 4.0) License to all copyrightable parts of our databases" | Each entry's name, gene, length, level of evidence, stated places with their evidence, segments, signal peptide and isoforms, its InterPro entries and Gene Ontology terms; the vocabulary of places |
| InterPro 111.0 | "freely available under CC0 1.0 Universal" | The type and name of each entry, the tree of entries, and their Gene Ontology terms |
| Gene Ontology, 2026-07-26 | "licensed under the Creative Commons Attribution 4.0 Unported License" | The names of terms and the links between them |
| Human Protein Atlas | "licensed under the Creative Commons Attribution 4.0 International License for all copyrightable parts of our database. Data subject to third-party constraints may also be included" | Nothing. It is kept for a link only |

Each page was saved beside the downloads, and the build checks the sentence in the saved
page before it uses anything. **The Human Protein Atlas** states CC BY 4.0 for its own
data, with a warning that data of third parties in it may carry other terms. Nothing was
taken from it, as decided; its own measured locations could be read under its terms if
that is wanted later, which is a decision for the user. **The page does not link to it
yet**: the link patterns (`data/proteins/overlay.json`) hold none for the human. A search
of the Atlas by accession answers with the one gene (checked once, for P04637), so a
pattern by accession would work, beside one for the UniProt entry.

## What rests on non-commercial or unlicensed sources

The project's rule (D173, 15 November 2026) sorts every source into three classes.
**Permissive** (CC BY, CC0, or a plain statement that no restriction is placed): values
and derived data may enter the repository, with attribution. **Non-commercial** (any
CC BY-NC licence, or a program given out for academic use only): analysis only.
**No stated terms** (none stated, or terms that could not be read): nothing enters.

**Nothing in the data files is taken from a source of the last two classes.** Every
value was read in UniProt, InterPro or the Gene Ontology. But some of what UniProt's
entries state was computed by rule systems and programs of other owners, which have
terms of their own. The shelves name each as a source in its own right, with
`through: UniProt`, and count what rests on it. Their pages of terms were read and saved
on 15 November 2026 by the tools of the other species; this tool reads those copies
(`/mnt/datasets/Cells/mpneumoniae/terms-upstream-tools`,
`/mnt/datasets/Cells/syn3a/terms-prosite`,
`/mnt/datasets/Cells/planarian/terms-upstream-tools`) and checks the sentences in them.
It added one page, of a program the others do not have: the predictor of GPI anchors.
Nothing else was downloaded from any of them, and no program was run.

Two kinds of dependence are counted, by UniProt's evidence codes and rule identifiers.
**Read here from a feature**: the side has the basis `predicted`, and the entry gives the
segment or the signal peptide by sequence analysis alone. **Behind a curator's
statement**: the entry states the place, the spanning, the face or the anchor, and names
only a rule or a sequence analysis as what stands behind that statement. A protein is
counted once for each owner it rests on.

| Tool or rule system | Its own terms, as read | Class | Read through | Placements that rest on it alone | Read here from a feature | Behind a curator's statement |
| --- | --- | --- | --- | ---: | --- | --- |
| PROSITE (its rules, ProRule) | CC BY-NC-ND 4.0; "Commercial users are asked to pay a yearly license fee" | Non-commercial | UniProt | 289 | 1, from segments a rule gives | 281 by the statement of place that decides the shelf (44 rules; PRU00108 for 71, PRU00981 for 36, PRU00187 for 35); 11 by the statement of spanning |
| HAMAP (family rules) | CC BY 4.0 | Permissive | UniProt | 54 | 2, from segments a rule gives | 39 by the statement of place (37 rules); 14 by the statement of spanning; 4 by the stated face |
| TMHMM | Academic licence of DTU Health Tech: free to publicly funded institutions for internal research; any other user must obtain a commercial licence. A licence of the program | Non-commercial | UniProt | 1,533 | 103, of the 119 read from segments | 1,429 said to span a membrane on a sequence analysis; 148 whose stated place rests on a sequence analysis in an entry with such segments (a "Membrane" inferred from predicted segments) |
| Phobius | For academic users only: private study, education or nonprofit research. Terms of the program | Non-commercial | UniProt | 1,533 and 256 | Those counted under TMHMM and SignalP | Those counted under TMHMM and SignalP |
| SignalP | Academic licence of DTU Health Tech, as TMHMM's | Non-commercial | UniProt | 256 | 249, of the 311 read from a signal peptide | 7 whose stated place rests on a sequence analysis in an entry with such a signal and no such segment |
| TargetP | Academic licence of DTU Health Tech, as TMHMM's | Non-commercial | UniProt | 256 | Those counted under SignalP | Those counted under SignalP |
| Memsat | Terms not read: UniProt names it without a version or an address | No stated terms | UniProt | 1,533 | Those counted under TMHMM | Those counted under TMHMM |
| Predotar | Terms not read: its page answers a program with a check for a browser | No stated terms | UniProt | 256 | Those counted under SignalP | Those counted under SignalP |
| big-PI | No open licence stated: the predictor's own page gives no terms of use | No stated terms | UniProt | 4 | None | 4 by a GPI anchor that the entry states on a sequence analysis |

- **The four methods are not told apart.** UniProt keeps a segment or a signal that at
  least two of its methods find and does not say which found it, so TMHMM, Memsat and
  Phobius share one count, and SignalP, TargetP, Predotar and Phobius another. The
  fourth method for segments, the hydrophobic moment plot of Eisenberg and coworkers, is
  a published method; UniProt's page names no program for it.
- **Of UniProt's own.** 2 statements of spanning rest on a rule of UniProt's own rule
  base (RuleBase), and 13 stated places rest on a sequence analysis in entries that carry
  no predicted segment or signal peptide, for which UniProt names no program.
- **What the counts leave out.** A statement that names a rule or a sequence analysis
  beside an experiment, a likeness or a curator's own inference is counted as resting on
  those, not on the tool.
- **Two kinds of terms.** PROSITE's terms are of the database, of which its rules are
  part; the licences of TMHMM, SignalP and TargetP and the terms of Phobius are of the
  programs, say who may run them and say nothing of predictions made with them, and it
  was UniProt that ran them.
- **The user's ruling (15 November 2026): such values may stay.** A value stands on the
  terms of the database it was read from, here UniProt's, and the tool behind it is named
  and counted. These are the dependences the other species' files name, and one more, the
  predictor of GPI anchors. The test of the licence classes keeps the register of the
  ones that are not permissive, under each species, so that a new one is noticed and put
  to the user before it is listed. Every placement is in the files, whatever it rests on:
  nothing was dropped.

## How to rebuild

    python3 tools/build_human_atlas.py fetch --datasets DATA
    python3 tools/build_human_atlas.py build --datasets DATA
    python3 tools/build_human_atlas.py members --out OUT

`fetch` is the only step that uses the network: 29 requests to UniProt, InterPro, the
Gene Ontology and five pages of terms, each saved as it came with its address, time and
SHA-256. `build` reads only those, the inventory snapshot and the pages of terms that the
other species' tools saved (`--terms`, by default the folder above `DATA`), and writes
the same bytes every time. `members` cuts the 11 files the page publishes beside it from the two files
of the repository.
