# The mouse in the viewer: the skin-like cell, the whole reference proteome, and how sure its places are

**Status: made by the visualizer session, 16 November 2026, for the user and the lead.**
The user: "Our of the model organims that have the best calibration data I think we should
probably also add the mouse add another agent for that, same skin cell". The coordinator's
reading, and so this note's: the laboratory mouse (*Mus musculus*) joins the species list
under Animals; its cell is the cell the planarian has, one cell of a sheet that stands for
skin-like tissue; and its catalogue is the whole reference proteome, as the user chose for
the fruit fly ("so yes, on whole reference proteome"), taken as the default for the mouse.
**Nothing of the mouse is in the engine.** Cells models a generic cell and a sheet of such
cells; the mouse lends them its proteins' names and two placeholder outlines.

Numbers are as built on 16 November 2026; the build prints them again.

| | |
| --- | --- |
| The species file | `data/species/mouse.json` (6 KB), with outlines in `data/species/shapes/mouse.json` (5 KB) |
| Its side of the atlas | `data/proteins/atlases/mouse.json`: an entry for each of the 49 units (246 KB) |
| Its own proteins | `data/proteins/mouse/`: `shelves.json` (741 KB), `proteins.tsv` (2.3 MB), `README.md` |
| The tool | `tools/build_mouse_atlas.py`: `fetch`, `build`, `members`. Standard library only |
| The test | `tests/mouse_atlas.test.mjs` |
| The downloads | `/mnt/datasets/Cells/mouse/`, three folders, each with a `MANIFEST.json` |
| The analysis | `/mnt/workspaces/Cells/visualizer-mouse-20261116-01/`: what the build counted, the searches, the checks of near misses |

## What Cells models of it, in the record's words

- **`modelled` is `generic`,** as for the human, the planarian and the fly: "Cells models a
  generic cell and a sheet of such cells, not this animal."
- **What the record says of the mouse.** `docs/DECISIONS.md` names it twice, and a proposal
  names it once more:
  - Decision D155, point 5 (14 November 2026), on the work on excitable tissue: "a generic
    cell for qualification, mouse for the first comparison, human second". The design note it
    points to (`docs/EXCITABLE_TISSUE_DESIGN.md`, section 7.2) is about heart muscle cells and
    their currents.
  - Decision D184, point 6 (16 November 2026), on the human's heart laws: "the mouse's
    expectation is unchanged": D167's expectation, which for the mouse means its currents are
    first matched to the old catalogue's channel laws (the design note, section 3.3), while the
    human's heart laws are new.
  - The free-energy-principle track's proposal (`docs/FEP_TRACK_PROPOSAL.md`: "proposed,
    future; not scheduled", and on hold by D179) names the mouse for one of its stages: "the
    islet (human target, mouse data)".
- **The species file says only D155's line:** that the record names the mouse for a planned
  comparison of heart muscle cells, and that nothing of it is built yet. That last rests on
  the design note's own status ("It contains no code"), on the lead's acceptance of it for
  the generic cell's work only, and on no mention of the mouse in the engine's code
  (`src/`) or in `PROGRESS.md` on main, read on 16 November 2026. It is not about skin, the
  record names no model of a mouse, and the card does not call the mouse a planned organism.

## The cell, the sheet and the outlines

- **Five levels,** as the planarian has: molecules, one cell, tissue, organ (the ear), whole
  mouse.
- **The cell and the sheet are the planarian's.** The same flat-sided cell, six sides, about
  20 µm across, and the same sheet of 127 cells, standing for skin-like tissue. The words
  are the mouse's own: the cell "is not a model of a mouse's skin cell"; the sheet "is not
  the mouse's skin". The planarian's note on a flatworm's skin resting on a basement
  membrane is not carried over: the plate under the layer is called scenery, and nothing is
  said of a mouse's skin that no source read here states.
- **The organ is the ear,** a choice put to the user (see the hand-back). It is drawn as a
  thin rounded blade laid back flat from the head, because the viewer draws the sheet
  level and a sheet can only lie on a face that is level. A live mouse holds its ears up;
  the way the ear lies is the picture's choice. The sheet lies on the left ear, half-way
  along it, and its ring there is drawn to scale.
- **Sizes from one open paper.** Islam and others (2021, Animals 11:2162, CC BY) measured
  four house mice (*Mus musculus*) trapped in Qatar: head and body 78.5 ± 2.4 mm, tail
  85.3 ± 4.1 mm, right ear 13.3 ± 1.7 mm (its Table 2). The outlines are drawn at those
  means. Those mice were wild, not laboratory mice, so the sizes are indicative; every
  width, the height, the ear's breadth (about 11 mm) and thickness (0.3 mm), the way the ears
  lie and the tail's curve are the picture's choice. The build checks the table's cells and
  the paper's description of the measurements in the saved text before it uses them.
- **Beside the whole mouse the sheet cannot be seen,** so its ring there is drawn large
  enough to find and its note says it is not to scale, as the human's does.

## The proteome, and what one marker stands for

- **UniProt's reference proteome UP000000589** (release 2026_04), *Mus musculus*, strain
  C57BL/6J, taxon 10090: **228,903 entries for 21,872 genes.** 17,279 entries are reviewed,
  written by a curator; 211,624 are unreviewed, annotated automatically. The mouse has ten
  times the fly's entries for not twice its genes: most genes have many unreviewed entries,
  one for each form of the gene that a genome annotation gives.
- **One marker for each gene: 21,872 proteins.** The protein shown is the one that UniProt's
  own gene-by-gene set of the proteome gives for the gene. 17,221 of them have a reviewed
  entry and 4,651 an unreviewed one. A mark, `reviewed`, says which. Only 58 reviewed
  entries are not the marker of their gene.
- **The other 207,031 entries are further forms of the same genes.** They are not markers.
  Each protein counts its gene's entries in the mark `entries`, by the MGI gene that
  UniProt gives each entry: 5,199 genes have one entry, 2,303 two, and 10,727 six or more.
  206,453 of the further entries are tied to a shown gene in this way; 245 shown proteins
  carry no MGI gene in UniProt, and count one.
- **`predicted` is false.** These are proteins of record with their own entries.

## How sure the places are

The mouse stands between the human and the fly. Of its 21,872 markers a curator wrote
17,221, four in five.

| What stands behind the protein's place | Reviewed entries | Unreviewed entries |
| --- | ---: | ---: |
| Stated, on an experiment | 3,768 | 0 |
| Stated, by likeness to another protein | 6,257 | 0 |
| Stated, by a curator's inference | 1,628 | 0 |
| Stated, with no evidence given | 1,411 | 0 |
| Stated, by a rule | 389 | 2,163 |
| Predicted from a segment or a signal peptide | 378 | 538 |
| Not known | 3,390 | 1,950 |

- **An experiment stands behind 3,768 places of 21,872:** 17 in 100. All are in reviewed
  entries. Likeness to another protein stands behind 6,257.
- **No curator wrote an unreviewed entry.** What it states is stated by one of UniProt's
  rule systems, so its `evidence` is `rule` and its basis `stated`: 2,163 proteins.
- **In all:** stated 15,616, predicted 916, not known 5,340.

## The shelves

The human's six. The mouse's entries use 243 places of UniProt's vocabulary; the human's
table has a line for all but two, which the mouse's tool adds (below, "Readings that are
this file's own").

| Shelf | Proteins | Outside | In | Inside | Side not known |
| --- | ---: | ---: | ---: | ---: | ---: |
| Cell membrane | 9,457 | 1,651 | 3,363 | 3,934 | 509 |
| Endoplasmic reticulum | 867 | 11 | 603 | 143 | 110 |
| Mitochondrion | 856 | 42 | 184 | 218 | 412 |
| Nucleus | 3,798 | 0 | 50 | 3,713 | 35 |
| Other membranes | 1,237 | 78 | 631 | 124 | 404 |
| A membrane, not told which | 1,880 | 479 | 1,298 | 10 | 93 |
| On no shelf | 3,777 | | | | 3,777 |

- 575 proteins stand on the unnamed membrane's shelf with no stated place at all, read from
  a segment (101) or a signal peptide (474).

## Families and districts

- **7,789 InterPro families hold 17,969 proteins;** 3,903 proteins have no family. The rule
  is the planarian's and the human's, so a family has the same id and name in each.
- 5,101 families of one (listed under `lone`, in 164 parts), 2,124 of two to four, 564 of
  five or more. 4,330 lines for 2,688 families, each with `total`; 652 lines of parts for
  the proteins with no family.
- The largest: olfactory receptors (938), type 1 vomeronasal receptors (210), the variable
  parts of antibodies' light chains (166) and heavy chains (165), a second family of
  olfactory receptors (130).
- **Nine districts,** the other species' own: channels 507, transporters and pumps 982,
  receptors and signalling 5,540, DNA, RNA and making proteins 3,804, protein handling
  1,501, cytoskeleton and movement 1,690, enzymes and metabolism 1,513, other functions
  2,072, not classed 360.

## Its side of the atlas

- **43 of the 49 units are found,** and 6 have nothing to look for (lumped properties, a
  default current, a configured slot and the designed cage). None is built from another
  family and none is not found: the mouse has connexins for its gap junctions, as the
  human has. 446 products are listed over the units, 158 proteins in all: 155 with a
  reviewed entry and 3 with an unreviewed one (`Cacna1g`, `Cacna1i`, `Kcnmb3`). Each names
  its units on the shelves (`unit`).
- **Every product was found by its family's signature; the mark says whether its entry is
  curated.** The atlas's contract has four kinds of evidence, and the shared search gives a
  product with a reviewed entry the kind "reviewed entry" and one with an unreviewed entry
  "family signature", as for the fly. So the page's card says that 3 of the 158 products were
  found by signature or similarity; in truth all 158 were, and 155 of them have an entry a
  curator wrote. This is put to the user (the hand-back), since the rule is every species'.
- **By family, never by a look-alike symbol.** The inventory names its candidates by human
  genes. A mouse protein is listed only because its own entry carries the InterPro
  signature of the unit's family, the signature the build first checks the human candidates
  carry. `Kcnj2` is under Kir2.1 because it carries the inward rectifiers' signature, with
  the 14 other inward rectifiers that carry it, not because its name looks like `KCNJ2`.
  No source of orthology was read and nothing is called an ortholog, so no unit says which
  family member is the human candidate's counterpart.
- **So the lists are long where the family is large:** 20 proteins for each sodium channel
  unit (ten alpha subunits and ten carriers of the beta subunits' signatures), 11 for each
  Kv1 unit with its beta subunits, 18 for each CaV2 unit with the subunits that go with it,
  20 connexins for each gap junction. Each is a candidate by family alone.
- **A near miss, said in the unit's note: `Atp2b3`, a calcium pump of the cell membrane
  (U40).** The mouse has no reviewed entry for it. UniProt's gene-by-gene set shows it by
  the entry A0ACP0BMC4, which carries no InterPro entry yet; three other entries of the same
  gene (A2ALL9, F6SDZ9, F6ZUK9) carry the family's signature. The build finds such cases
  itself, for every unit, from every entry of the proteome: this is the only one for a
  family that makes a machine. Two more touch nothing drawn: an entry of `Slc25a12`
  carries the signature of the MICU regulators, an accessory family; and an entry tied to
  the MGI gene `Gm21985`, which has no marker of its own, carries the chloride
  cotransporters' (analysis folder, `gene_families.txt`).
- **The shared table of families sweeps in six relatives of myelin protein zero.** One of
  the two signatures the table gives for the sodium channels' beta subunits, IPR000920, is
  InterPro's "Myelin P0 protein-related". In the mouse it is carried, besides `Scn2b` and
  `Scn4b`, by `Mpz`, `Mpzl1`, `Mpzl2`, `Mpzl3`, `Jaml` and `Vsig1`, so these stand under
  U01 to U04 in the role "sodium channel beta subunits". Each product's own note names the
  signature it carries, and the beta subunits are an accessory family, which makes no unit
  found. The table is shared by every species (`tools/build_mpneumoniae_atlas.py`), so it
  is not changed here; the fly's, the planarian's and thale cress's sides of the atlas list
  no beta subunit at all.

## Sources and terms

| Source | Terms | Class | What was taken | Saved in |
| --- | --- | --- | --- | --- |
| UniProt, release 2026_04 | CC BY 4.0 | Permissive | Every entry of the proteome: names, genes, MGI genes, lengths, stated places with their evidence, segments, signals and anchors, InterPro entries and Gene Ontology terms; the proteome's record and counts; the gene-by-gene set (only the names of its entries are read) | `mouse/uniprot-mouse-reference-proteome`, with UniProt's licence page beside the data |
| InterPro 111.0 | CC0 1.0 | Permissive | Names and types of entries, the tree of entries, the mapping to Gene Ontology terms | `human/interpro-entries-tree-and-go`, read only |
| Gene Ontology, 2026-07-26 | CC BY 4.0 | Permissive | Names of terms and the links between them | `human/geneontology-go-basic`, read only |
| Islam and others 2021, Animals 11:2162 | CC BY, as its record at Europe PMC states | Permissive | Three means of its Table 2 (head and body, tail, ear) and the citation | `mouse/europepmc-open-papers` |
| MGI, Mouse Genome Informatics | CC BY 4.0 for its data and annotations, as its page states | Permissive | Nothing: linked to only. The MGI genes used are those UniProt gives its entries | `mouse/terms-mgi` (its page of terms) |

The terms of UniProt, InterPro and the Gene Ontology, and of the tools below, are the pages
the tools save; the build reads each and stops if one no longer says what was read.
UniProt's vocabulary of places and its help pages are read from the human's saved folder
(`human/uniprot-docs-and-terms`), whose release, 2026_04, the build checks against the
mouse's downloads.

## What rests on non-commercial or unlicensed sources

The project's rule (D173, 15 November 2026) sorts every source into three classes.
**Permissive** (CC BY, CC0, or a plain statement that no restriction is placed): values
and derived data may enter the repository, with attribution. **Non-commercial** (any
CC BY-NC licence, or a program given out for academic use only): analysis only.
**No stated terms**: nothing enters.

**Nothing was downloaded from a source of the last two classes, and no tool was run.**
The shelves rest on results that UniProt gives out under its own terms and that tools and
rule systems computed. By the user's ruling of 15 November 2026 (D178) such a value stands
on the terms of the database it was read from, and the tool behind it is named and
counted; the user said that this holds for every species. It is the project's rule, not a
legal opinion.

| Tool or rule system | Class | Placements that rest on it alone |
| --- | --- | --- |
| ARBA, UniProt's own rule system | Permissive (UniProt's, CC BY 4.0) | 1,993: most stated places of unreviewed entries |
| UniRule (RuleBase) and PIR's rules, UniProt's own | Permissive (UniProt's, CC BY 4.0) | 1,188 and 9 |
| HAMAP rules | Permissive (CC BY 4.0) | 98 |
| PROSITE rules (ProRule) | Non-commercial (CC BY-NC-ND 4.0) | 321 |
| SignalP | Non-commercial (academic licence) | 389 sides read from a signal peptide that an unreviewed entry gives, the program named on each; and, as one of four methods in reviewed entries, the 169 below |
| Phobius | Non-commercial (academic users only) | 136 sides read from segments that an unreviewed entry gives, the program named on each; and one of the methods behind the 1,481 and the 169 below |
| TMHMM | Non-commercial (academic licence) | One of four methods behind the predicted segments of reviewed entries: 1,481 placements. Named on no feature of an unreviewed entry |
| TargetP | Non-commercial (academic licence) | One of four methods behind the predicted signal peptides of reviewed entries: 169 placements |
| Memsat | No stated terms (terms not read) | One of the four methods for segments: the 1,481 |
| Predotar | No stated terms (terms not read) | One of the four methods for signal peptides: the 169 |
| big-PI | No stated terms (its page gives none) | 4 anchors stated on a sequence analysis alone |

- **In an unreviewed entry UniProt names the program on each feature,** so the counts for
  SignalP and Phobius there are exact. In a reviewed entry its pages name four methods and
  do not say which found a feature.
- **All eight tools that are not permissive are already in the register** of
  `tests/licence_classes.test.mjs` (the human's, the fly's and thale cress's lines name the
  same eight). The mouse's line is added with them, and brings no tool the register has not
  seen.
- **MGI is permissive and is linked to only.** Its page of terms was saved on 16 November
  2026 and states that "MGI data and annotations are licensed under a Creative Commons
  Attribution 4.0 International License (CC-BY)". Nothing else of MGI was downloaded: the
  MGI genes that tie a gene's entries together are those UniProt gives its entries.
- **No source of orthology was used,** so none is named here; whether to add one is put to
  the user (the hand-back).

## Readings that are this file's own

1. One marker for each gene, by UniProt's gene-by-gene set; the further entries a count.
2. A rule's statement in an unreviewed entry is `stated` with evidence `rule`, not
   `predicted`: the entry does state it, and the mark says no curator did.
3. UniProt's own rule systems are counted under UniProt, not as sources of their own.
4. **Two places the human's table has no line for.** "Mitosome matrix": the vocabulary
   calls a mitosome an organelle of single-celled organisms without mitochondria, so a
   mouse cell has none, and the statement is passed over; the entries of `Glyctk` (the
   reviewed one by likeness to the human's entry) then stand where their other statements
   or features put them, here on no shelf. The other reading, the mitochondrion's matrix,
   would guess what was meant. "Host cell": a place in a virus's host, passed over as
   E. coli's table passes over "Host cell membrane" (five unreviewed entries of one gene,
   by a rule).
5. `found` as the atlas's contract has it, and the near misses of the gene-by-gene set named
   in the unit's note, not listed as products.
6. The organ is the ear, laid flat; its length and the body's are one paper's means of wild
   house mice; everything else of the outlines is the picture's choice.

## What is not known

- **Which family member does a unit's work in the mouse.** Without a source of orthology
  and of expression, the atlas cannot say that `Scn2a` rather than another sodium channel
  is the NaV1.2 unit's counterpart.
- **How a laboratory mouse's sizes compare.** The outlines' lengths are of four wild house
  mice; a measurement of the reference strain, C57BL/6J, was not found in the short search
  made (searches saved in the analysis folder).
- **Whether the ear, the back's skin or the heart is the better organ** is the user's choice.

## Changes to the contracts

None, beyond a word: `schema/SPECIES_PROTEINS.md`, "A whole reference proteome", now names
the mouse beside the fruit fly.

## How to rebuild

```
python3 tools/build_mouse_atlas.py fetch --datasets DATA   # the only step that uses the network
python3 tools/build_mouse_atlas.py build --datasets DATA   # the same bytes every time
node --test tests/mouse_atlas.test.mjs                      # set MOUSE_DATASETS elsewhere
```

The build reads about 190 MB of entries and takes about a minute and a half on one core of
a busy machine, with 1.5 GB of memory at its peak. It shares
`tools/lib/proteome_shelves.py` with the human's, the fly's and thale cress's tools, and
the families asked of every species with the M. pneumoniae tool; neither was changed.
