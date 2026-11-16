# The fruit fly in the viewer: the whole reference proteome, and how sure its places are

**Status: made by the visualizer session, 15 November 2026, for the user and the lead.**
The user: "When the e.Coli is done then add two more serially, Fruit fly and Thale cress",
and, asked whether the fly's catalogue should be the reviewed entries alone: "so yes, on
whole reference proteome". **Nothing of the fly is in the engine.** Cells models a generic
cell and a sheet of such cells; the fly lends them its proteins' names and two placeholder
outlines.

Numbers are as built on 15 November 2026; the build prints them again.

| | |
| --- | --- |
| The species file | `data/species/fruitfly.json` (5 KB), with outlines in `data/species/shapes/fruitfly.json` (3 KB) |
| Its side of the atlas | `data/proteins/atlases/fruitfly.json`: an entry for each of the 49 units (89 KB) |
| Its own proteins | `data/proteins/fruitfly/`: `shelves.json` (403 KB), `proteins.tsv` (1.4 MB), `README.md` |
| The tool | `tools/build_fruitfly_atlas.py`: `fetch`, `build`, `members`. Standard library only |
| The test | `tests/fruitfly_atlas.test.mjs` |
| The downloads | `/mnt/datasets/Cells/fruitfly/`, one folder with a `MANIFEST.json` |
| The analysis | `/mnt/workspaces/Cells/visualizer-fruitfly-20261115-01/`: what the build counted |

## The proteome, and what one marker stands for

- **UniProt's reference proteome UP000000803** (release 2026_04), *Drosophila
  melanogaster*, taxon 7227: **21,941 entries for 13,814 genes.** 3,885 entries are
  reviewed, written by a curator; 18,056 are unreviewed, annotated automatically.
- **One marker for each gene: 13,814 proteins.** The protein shown is the one that
  UniProt's own gene-by-gene set of the proteome gives for the gene (its "one protein per
  gene" file). 3,850 of them have a reviewed entry and 9,964 an unreviewed one. A mark,
  `reviewed`, says which.
- **The other 8,127 entries are further forms of the same genes.** They are not markers.
  Each protein counts its gene's entries in the mark `entries`, by the FlyBase gene that
  UniProt gives each entry: 10,436 genes have one entry, 2,140 two, and 295 six or more.
  6,791 of the further entries are tied to a shown gene in this way; 1,329 shown proteins
  carry no FlyBase gene in UniProt, and count one.
- **`predicted` is false.** These are proteins of record with their own entries, not gene
  models. That says nothing about how sure their places are: the next section does.

## How sure the places are

This is where the fly differs from the human. The human's 20,414 proteins are all
curated. Of the fly's 13,814, a curator wrote 3,850.

| What stands behind the protein's place | Reviewed entries | Unreviewed entries |
| --- | ---: | ---: |
| Stated, on an experiment | 1,094 | 0 |
| Stated, by likeness to another protein | 632 | 0 |
| Stated, by a curator's inference | 432 | 0 |
| Stated, with no evidence given | 318 | 0 |
| Stated, by a rule | 176 | 3,120 |
| Predicted from a segment or a signal peptide | 91 | 2,552 |
| Not known | 1,107 | 4,292 |

- **An experiment stands behind 1,094 places of 13,814:** 8 in 100. All are in reviewed
  entries.
- **No curator wrote an unreviewed entry.** What it states is stated by one of UniProt's
  rule systems, so its `evidence` is `rule` and its basis `stated`: 3,120 proteins. What
  is read from a predicted segment or signal is `predicted`: 2,552. The rest, 4,292, is
  not known.
- **In all:** stated 5,772, predicted 2,643, not known 5,399.
- One reviewed statement is marked as taken over from another database by a curator; it
  is counted with the curators' inferences.

## The shelves

The human's six, unchanged: the fly's entries use 180 places of UniProt's vocabulary, and
the human's table has a line for every one.

| Shelf | Proteins | Outside | In | Inside | Side not known |
| --- | ---: | ---: | ---: | ---: | ---: |
| Cell membrane | 2,712 | 683 | 601 | 1,231 | 197 |
| Endoplasmic reticulum | 358 | 5 | 202 | 53 | 98 |
| Mitochondrion | 511 | 21 | 120 | 83 | 287 |
| Nucleus | 1,692 | 1 | 18 | 1,649 | 24 |
| Other membranes | 371 | 29 | 169 | 22 | 151 |
| A membrane, not told which | 3,577 | 1,884 | 1,641 | 3 | 49 |
| On no shelf | 4,593 | | | | 4,593 |

- **The unnamed membrane's shelf is the largest.** An unreviewed entry often says only
  "Membrane", or states no place and carries a predicted segment or signal. 2,502 proteins
  stand there with no stated place at all.

## Families and districts

- **4,747 InterPro families hold 9,528 proteins;** 4,286 proteins have no family. The rule
  is the planarian's and the human's, so a family has the same id and name in each.
- 3,404 families of one (listed under `lone`, in 140 parts), 1,047 of two to four, 296 of
  five or more. 1,960 lines for 1,343 families, each with `total`; 509 lines of parts for
  the proteins with no family.
- The largest: chymotrypsin-family peptidases (138), a family of unknown function
  (DUF1091, 97), serine proteases of immunity and development (71), cuticle proteins (68),
  cytochromes P450 (60).
- **Nine districts,** the other species' own: channels 395, transporters and pumps 624,
  receptors and signalling 967, DNA, RNA and making proteins 2,262, protein handling
  1,261, cytoskeleton and movement 732, enzymes and metabolism 1,564, other functions
  1,379, not classed 344.

## Its side of the atlas

- **38 of the 49 units are found, 3 are built from another family, 2 are not found,**
  and 6 have nothing to look for. 54 proteins are listed, 28 with a reviewed entry and 26
  with an unreviewed one; each names its units on the shelves (`unit`).
- **`found` asks for a family that makes the machine itself.** No unit here rests on an
  accessory family alone.
- **Found, for example:** the sodium channel (`para`, `NaCP60E`), the Shaker-type
  potassium channels (`Sh`, with `Hk`), Shaw and Shal, the inward rectifiers (`Irk1` to
  `Irk3`), the HCN channel (`Ih`), the calcium channels (`Ca-alpha1D`, `cac`,
  `Ca-alpha1T`), the BK and SK channels (`slo`, `SK`), the sodium-potassium pump
  (`Atpalpha`), the calcium pumps (`PMCA`, `SERCA`), the exchanger (`Calx`), the store's
  release channels (`Itpr`, `RyR`), the chloride cotransporters (`kcc`, `Ncc69`) and the
  mitochondrial uniporter (`MCU`).
- **Another family: the gap junctions** (U36 to U38). No fly protein carries the
  connexins' signature; eight carry the innexins' (`Inx2`, `Inx3`, `Inx5`, `Inx6`, `Inx7`,
  `ogre`, `shakB`, `zpg`).
- **Not found, by signature: the Kv2 channels** (U11, U12). The fly's `Shab` is a
  voltage-gated potassium channel by its entry's name, and InterPro gives it another Kv
  family's signature, so the search does not list it. The units' notes say so. This is a
  limit of searching by signature, not a finding about the fly.
- **Several units share their products.** The six Kv1 units all list `Sh` and `Hk`: the
  family is one, and nothing here says which protein does which unit's work.

## Levels and outlines

- **Five levels,** as the human and the planarian have: molecules, one cell, tissue,
  organ, whole fly. The cell and the sheet are the generic ones Cells models.
- **The organ is the wing.** A visitor knows it, and the project's record names the
  Drosophila wing disc as a long-term target of its work on how a tissue takes its shape
  (the user's decisions of 9 November 2026 on the morphogenesis plan). No wing and no
  wing disc is modelled.
- **Rough placeholders.** The fly is drawn 2.5 mm long with its wings, each 2 mm, folded
  back over its body: three rounded humps and two flat blades.
- **No size was read from a source.** Every size of the outlines is said, in the file, to
  be the picture's choice. One search for an open paper giving the fly's body and wing
  lengths found none; a later pass can source them.
- **`modelled` is `generic`,** as for the human and the planarian. The record names no
  model of the fly.

## Sources and terms

| Source | Terms | What was taken |
| --- | --- | --- |
| UniProt, release 2026_04 | CC BY 4.0 | Every entry of the proteome: names, genes, FlyBase genes, lengths, stated places with their evidence, segments, signals and anchors, InterPro entries and Gene Ontology terms; the proteome's record and counts; the gene-by-gene set (only the names of its entries are read; it holds sequences, which stay with the downloads) |
| InterPro 111.0 | CC0 1.0 | Names and types of entries, the tree of entries, the mapping to Gene Ontology terms |
| Gene Ontology, 2026-07-26 | CC BY 4.0 | Names of terms and the links between them |

The terms of UniProt, InterPro and the Gene Ontology, and of the tools below, are the
pages the other species' tools saved; the build reads each and stops if one no longer
says what was read.

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
counted; the user said that this holds for every species. It is the project's rule, not
a legal opinion.

| Tool or rule system | Class | Placements that rest on it alone |
| --- | --- | --- |
| ARBA, UniProt's own rule system | Permissive (UniProt's, CC BY 4.0) | 3,413: the stated places of unreviewed entries |
| UniRule (RuleBase) and PIR's rules, UniProt's own | Permissive (UniProt's, CC BY 4.0) | 363 and 65 |
| HAMAP rules | Permissive (CC BY 4.0) | 99 |
| PROSITE rules (ProRule) | Non-commercial (CC BY-NC-ND 4.0) | 270 |
| SignalP | Non-commercial (academic licence) | 1,799 sides read from a signal peptide that an unreviewed entry gives, the program named on each; and, as one of four methods in reviewed entries, the 61 below |
| Phobius | Non-commercial (academic users only) | 713 sides read from segments that an unreviewed entry gives, the program named on each; and one of the methods behind the 192 and the 61 below |
| TMHMM | Non-commercial (academic licence) | One of four methods behind the predicted segments of reviewed entries: 192 placements. Named on no feature of an unreviewed entry |
| TargetP | Non-commercial (academic licence) | One of four methods behind the predicted signal peptides of reviewed entries: 61 placements |
| Memsat | No stated terms (terms not read) | One of the four methods for segments: the 192 |
| Predotar | No stated terms (terms not read) | One of the four methods for signal peptides: the 61 |
| big-PI | No stated terms (its page gives none) | 4 anchors stated on a sequence analysis alone |

- **In an unreviewed entry UniProt names the program on each feature,** so the counts
  for SignalP and Phobius there are exact. In a reviewed entry its pages name four
  methods and do not say which found a feature.
- **UniProt's own systems are not sources of their own in the file.** ARBA, UniRule and
  PIR's rules are UniProt's, under its licence; the file counts them in UniProt's own
  entry. This is the file's reading of the contract's rule on a tool behind a value,
  which speaks of programs and rule systems "of another owner".
- **All eight tools that are not permissive are already in the register** of
  `tests/licence_classes.test.mjs` (the human's line names the same eight). The fly
  brings no tool the register has not seen.

**FlyBase is linked to only, and its terms could not be saved.** Nothing is taken from
it: the FlyBase genes used here are those UniProt gives its entries. Its page of licences
was read once on 15 November 2026 and stated CC BY 4.0 for its annotations and data; on
every later request FlyBase answered the tool with an empty reply, so the page is not
among the saved downloads and no class is given from it. The fetch step still asks for
it. Until it is saved, FlyBase stays a pointer: No stated terms on record.

## Readings that are this file's own

1. One marker for each gene, by UniProt's gene-by-gene set; the further entries a count.
2. A rule's statement in an unreviewed entry is `stated` with evidence `rule`, not
   `predicted`: the entry does state it, and the mark says no curator did.
3. UniProt's own rule systems are counted under UniProt, not as sources of their own.
4. The one statement a curator took over from another database counts as a curator's.
5. `found` and `different family` as the atlas's contract has them; the Kv2 units stay
   "none found" by signature, with the near miss named.
6. The organ is the wing; every size of the outlines is the picture's choice.

## Changes to the contracts

None was made. Proposed for `schema/SPECIES_PROTEINS.md`, under "A curated proteome":

"**A whole reference proteome.** Where a species' catalogue is its whole reference
proteome, reviewed and unreviewed entries together, one marker stands for each gene: the
protein that the database's own gene-by-gene set gives for it. The mark `reviewed` says
whether its entry was written by a curator, and the mark `entries` counts the proteome's
entries for its gene. A place that a rule system states in an unreviewed entry is
`stated` with the evidence `rule`. The file gives, under `curated`, how many places rest
on each kind of evidence for reviewed and for unreviewed entries apart, so that the page
can say how sure it is."

## How to rebuild

```
python3 tools/build_fruitfly_atlas.py fetch --datasets DATA   # the only step that uses the network
python3 tools/build_fruitfly_atlas.py build --datasets DATA   # the same bytes every time
node --test tests/fruitfly_atlas.test.mjs                      # set FRUITFLY_DATASETS elsewhere
```

**The shared parts are in one module** since 16 November 2026:
`tools/lib/proteome_shelves.py` holds the datasets and manifests, the vocabulary and
placement, the filing into families, the lines, the download step and the writing of the
files. This tool keeps what is the fly's own: its sources, the Shab note, its outlines,
its species and atlas files and its sentences. It still reads the families asked of
every species from the M. pneumoniae tool's table. No tool sets another's variables any
more, so several species can be built in one process; every file this tool writes came
out the same byte for byte after the move.
