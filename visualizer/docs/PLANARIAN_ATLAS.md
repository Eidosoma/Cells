# The planarian side of the protein atlas

**Status: made by the visualizer session, 14 November 2026, for the lead and the user.**
The user asked for "a full catalogue of Planerian proteins" and then, of the catalogue
meant, that "Recent mass-spectrometry-based proteomic studies of the planarian Schmidtea
mediterranea have established a spectral library covering approximately 10,000 proteins."
This note says what was made, what could not be, and how sure each part is. Numbers are
as built on 14 November 2026; the build prints them again.

| | |
| --- | --- |
| The atlas | `data/proteins/atlases/planarian.json`, in the form `schema/SPECIES_ATLAS.md` fixes (283 KB) |
| The open set, whole | `data/proteins/planarian/predicted_proteins.tsv` (18,882 proteins: 17,294 gene models and 1,588 UniProtKB entries; 2.2 MB, no sequences), brought in by the user's decision of 14 November 2026 |
| The proteins the atlas names | `data/proteins/planarian/reference_proteins.tsv` (229 proteins: the 227 it names and 2 joined to them; 35 KB) and the folder's `README.md` |
| The shelves | `data/proteins/planarian/shelves.json` (the families, 541 KB) and `shelf_members.tsv` (every protein's family, side and basis, 860 KB), in the form `schema/SPECIES_PROTEINS.md` fixes; see "The shelves" below |
| The tool | `tools/build_planarian_atlas.py`: `fetch` uses the network, `build` and `members` do not |
| The check | `node --test tests/planarian_atlas.test.mjs` |
| The evidence | `/mnt/workspaces/Cells/visualizer-planarian-proteins-20261114-01` (65 MB): 179 requests on record, one of them a refusal, and every response that came back |

## Answer

**The library of about 10,000 proteins was found and could not be imported.** It is the
spectral library of Ying and others (2025). Its list of proteins is not in the study's
public deposits, and the paper reserves all rights. The details are in the next section.

**The open set was brought in whole in the meantime.** Offered that set until the
library's list can be had with permission, the user chose it on 14 November 2026: the
18,882 proteins on open record for the species, in
`data/proteins/planarian/predicted_proteins.tsv`. They are predicted from the genome and
from transcripts, not measured. The table is not the library and does not stand in for
it.

**The atlas itself is complete: all 49 units have an entry.** For 38 units, planarian
gene products of the same family were found; for 3 the planarian uses a different
family; for 2 nothing was found; for 6 there is nothing to look for. Almost every product is a candidate
found by a sequence signature, not an established counterpart.

**The answers are drawn from gene predictions, and say so.** UniProt holds 1,588 entries
for the species and only four curated ones, none of a family the atlas draws. So the
candidates come from the 17,294 predicted proteins of one genome annotation. The 227
proteins the atlas names, and 2 joined to them, are also listed apart, in
`reference_proteins.tsv`.

## The library of about 10,000 proteins

| | |
| --- | --- |
| The study | Ying Y, Xiong YZ, Pan X, Zhang Q, Chen J, Zhao Y, Cai X, Yi X, Zhu Y, Guo T, Lei K (2025) Proteomics-based multi-omics identifies the roadmap of transcription-translation-protein dynamics in planarian regeneration. Dev Cell 60:3527-3543.e5. doi:10.1016/j.devcel.2025.08.015, PubMed 40961932 |
| What it reports | Its abstract: "establishing a spectral library covering ∼10,000 proteins" of *Schmidtea mediterranea* |
| Its deposits | ProteomeXchange PXD042308 (iProX IPX0006394000): 813 instrument files and 6 other files. ProteomeXchange PXD059861 (iProX IPX0010799000): 32 instrument files. GEO GSE232894: the study's RNA sequencing |
| Terms of the paper | "© 2025 Elsevier Inc. All rights are reserved, including those for text and data mining, AI training, and similar technologies." Not open access |
| Terms of the deposits | iProX's data licence puts datasets submitted since 23 March 2023 under CC0. The same page limits what is taken from its site to personal use. Both clauses are saved |

**What is missing is the list itself.** The six files of the deposit that are not
instrument files were read: they are run lists and sample sheets, the longest 414 rows.
A search of Europe PMC's preprints and of the data repositories that DataCite indexes
(Zenodo, Mendeley Data, figshare and MassIVE among them) found no preprint and no other
record of the library. The paper's page, where its supplementary tables are listed,
answered the tool with HTTP 403. Had it answered, the paper's terms would still forbid a
copy.

**Which reference its identifiers use is not stated** in any record that was read. The
study's RNA-sequencing table is indexed by 36,035 identifiers that begin `SMED3`. That
suggests the reference; it does not show it.

**An import needs one of two things.** Either the authors' or the publisher's
permission, or a deposit of the library under an open licence. Or a new protein list
derived from the 813 instrument files, which are open: that is a mass-spectrometry
reanalysis against a protein reference, not a download.

The project does not contact authors (the user's rule, recorded in D173 on 14 November
2026), so the first route waits for the list to appear in a public source under terms
that allow a copy. A table the user already holds can be read from
`/mnt/workspaces/Cells/visualizer-planarian-library/`; under the paper's present terms it
stays outside this public repository.

Other proteomics of the species exists and was not examined: five MassIVE datasets of
2025 and 2026 from another group (MSV000098119, MSV000098120, MSV000099716, MSV000100775
and MSV000102685). None is the library the user named.

### Other catalogues that were sized

None of these is about 10,000 proteins, and none is the library. The open set now in the
repository is the first of them and, of the third, the 17,294 gene models of haplotype 1
that have a predicted protein.

| What | Size | Terms |
| --- | --- | --- |
| UniProtKB entries of the species | 1,588 (4 reviewed) | CC BY 4.0 |
| UniProt's archive of the species' sequences (UniParc) | 98,660, from three annotation sets and the sequence databases | CC BY 4.0 |
| WormBase ParaSite gene models | 21,392 and 21,310 coding genes (the two haplotypes of the 2022 annotation); 29,850 (the 2014 annotation) | No restriction stated; citation asked |
| NCBI protein records of the species | 1,704 | Not read; only counted |
| PlanMine | Not sized by this tool | Its front page states no licence or terms of use |

## What the atlas is, and is not

It answers one question for each unit the protein atlas draws: which planarian gene
products would make that machine, how each was found, and how sure that is.

- It is the viewer's reference data. It is not the engine's protein catalogue, whose
  design belongs to the lead, and nothing in `src/cells` reads it.
- It makes no claim about the engine. The laws are the same for every species.
- It is not a proteome. `extra` holds seven proteins that bear on what is drawn.
- It calls nothing an ortholog. No similarity search against another species was run.

## The species, and why

*Schmidtea mediterranea* (taxon 79327). UniProt holds 1,588 entries for it, 4 of them
reviewed. That is more than half of the 2,784 it holds for all planarians (the order
Tricladida); among the others, *Dugesia japonica* has 499. UniProt holds a proteome for
no planarian. WormBase ParaSite holds a chromosome-scale genome assembly of
*S. mediterranea* with gene models; Ivanković and others (2024) describe the assembly.

## Method, step by step

1. **Licences first.** Each source's terms were read and saved before anything was
   copied. The build stops if a saved page no longer says what the files state.
2. **The family of each unit comes from its own human candidates.** The InterPro
   signatures those candidates carry were read from UniProt, and one or two that mark the
   family were chosen. The build checks that the unit's candidates carry them.
3. **Curated entries first.** UniProt's four reviewed entries of the species are a
   coactivator, an esterase and two PIWI proteins. None is used.
4. **Named in a publication.** A planarian protein counts as named only where the saved
   abstract, or the saved open-access text, of the paper uses the name, and the entry is
   tied to that paper. Four products pass: smedinx-11 and scna-1, scna-2, scna-3. UniProt
   calls the first only "Innexin"; its sequence record (DQ851133) belongs to the paper and
   carries the name, spelt smedxin-11.
5. **Family signature.** Unreviewed UniProtKB entries of the species that carry the
   signature, and gene models that carry it. A gene model carries a signature if the
   genome annotation's own InterPro matches say so, or if one of its predicted proteins
   is, letter for letter, a sequence that carries it in UniProt's archive. The second
   route matters because the annotation's matches are older than some signatures. The
   product names the predicted protein that carries the signature and gives its length.
6. **One product for one sequence.** A UniProtKB sequence and a gene model are given as
   one product when at least 80% of the sequence's 8-residue words occur in the model's
   predicted protein and no other gene reaches half of that share. 1,288 of the 1,588
   entries join a gene model this way.
7. **A control for every zero.** Where a signature found nothing, it was also asked of
   all 98,660 planarian sequences in UniProt's archive, of the UniProtKB entries of all
   flatworms, and of reviewed human entries. The unit's note gives what came back.
8. **Doubt is written on the product.** If the signature sits on a shorter alternative
   protein of a gene and not on its longest, or the gene model matches a UniProtKB entry
   that lacks the signature, the product's evidence note says so.

The gene models are those of WormBase ParaSite release 19: assembly schMedS3 haplotype 1,
strain S2F19, annotation version 2022-10. It lists 21,392 coding genes; 17,294 have a
predicted protein, and those are the ones searched.

## Counts

**Units by finding**

| Finding | Units | Which |
| --- | --- | --- |
| found | 38 | U01 to U17, U20 to U33, U39 to U44, U47 |
| different family | 3 | U36, U37, U38 (gap junctions) |
| none found | 2 | U19 (Kir2.1), U45 (NKCC) |
| nothing to look for | 6 | U18, U34, U35, U46, U48, U49 |

**Products by evidence.** The units list 592 product entries, because units of one
family share their candidates. They are 204 different products.

| Evidence | Products | What they are |
| --- | --- | --- |
| reviewed entry | 0 | |
| named in a publication | 4 | smedinx-11; scna-1, scna-2, scna-3 |
| family signature | 200 | 10 UniProtKB entries, each joined to a gene model, and 190 gene models |
| similarity search | 0 | None was run |

**Gene models by family**

| Family | Gene models | Units |
| --- | --- | --- |
| Sodium channel pore subunit | 3 | U01 to U04 |
| Kv1, Kv2, Kv3, Kv4 potassium channels | 14, 1, 23, 4 | U05 to U17 |
| Kv-beta subunit | 2 | U05 to U10 |
| HCN-type channels | 7 | U20 to U23 |
| Calcium channel pore subunits: L-type, T-type, neither | 2, 2, 4 | U24 to U32 |
| Calcium channel beta, alpha-2/delta | 3, 5 | U24 to U30 |
| BK, SK channels; BK beta | 9, 9; 6 | U33 |
| Innexins | 68 | U36 to U38 |
| Pump alpha (sodium-potassium or proton-potassium), beta | 5, 13 | U39 |
| Plasma-membrane and SERCA-type calcium pumps | 6, 3 | U40, U41 |
| Sodium-calcium exchangers | 5 | U42 |
| Inositol trisphosphate, ryanodine receptors | 2, 1 | U43 |
| Potassium-chloride cotransporter | 1 | U44 |
| Uniporter pore (MCU), MICU | 1, 3 | U47 |

## Where planarians differ

Each line is what a reader outside the field needs, then what it rests on.

- **Gap junctions are built from innexins, not connexins.** The channel between two
  cells does the same job, but its protein is of another family, so there is no planarian
  connexin 45 or connexin 40 to name. Source: 68 gene models carry the innexin signature
  and none the connexin one; no flatworm entry in UniProtKB carries the connexin
  signature, and 21 human ones do. One planarian innexin has a sequence record of its
  own, smedinx-11. Two papers say more and are named as places to read: Abascal and
  Zardoya 2013 (doi:10.1016/j.bbamem.2012.02.007), on which animals have each family, and
  Oviedo and Levin 2007 (doi:10.1242/dev.006635), on that innexin. Neither states an
  open licence, so the atlas says nothing from them; until 15 November 2026 its note
  rested on their abstracts.
- **No inward-rectifier potassium channel was found.** Nothing in the planarian carries
  the signature of the family Kir2.1 belongs to. Source: three signatures of the family
  find no planarian sequence, and find 21 entries of other flatworms and 16 human ones.
  This is an absence in these sources, not proof of absence in the animal.
- **The helper subunits of vertebrate sodium channels and pumps were not found.** No
  planarian sequence carries the signatures of the sodium channel beta subunits or of the
  FXYD regulators. Source: the same search, which finds 10 and 8 human entries. No
  flatworm entry carries the FXYD signature.
- **One pump was described as a proton-potassium pump.** It shares its signature with the
  sodium-potassium pump's alpha subunit, so it is kept out of that unit and listed under
  `extra`. Source: its sequence record JX174182, which names it. The paper that reports
  it (Beane and others 2013, doi:10.1242/dev.086900) states no open licence: it is cited
  for the name, and its findings are not repeated in the atlas.
- **A channel with the HCN signature was published as a cyclic-nucleotide-gated channel.**
  The two are related kinds of channel; the signature says one and the name the other.
  Source: Roberts-Galbraith and others (2016), doi:10.7554/elife.17002, who call it CNG1.
- **Families are larger than the units suggest.** 68 innexin and 23 Kv3 gene models
  stand against 3 and 4 units. Nothing here says which of them a unit would stand for.

## What could not be determined

- **Which planarian protein corresponds to which human one.** Signatures place a protein
  in a family, not opposite a named human protein. That needs a similarity search and a
  tree, and neither was made.
- **Whether a gene model is a real, whole protein.** Models are predictions from one
  haplotype. Innexin models run from 106 to 491 residues; the short ones may be fragments.
- **Two candidates are doubtful, and say so.** One MICU candidate (h1SMcG0010573) carries
  the signature only on a short alternative protein; its longest protein matches an entry
  submitted as slc25a-9, a mitochondrial carrier. The one Kv2 gene model carries the
  signature only on its shorter protein.
- **The sodium-potassium-chloride cotransporter (U45).** Its signature finds no entry of
  any flatworm and only 2 human ones, so it may not recognise flatworm forms. Five gene
  models carry the wider family's signature; whether one is this transporter is not known.
- **Which pump is which.** Five gene models carry the alpha signature shared by
  sodium-potassium and proton-potassium pumps. Nothing here separates them.
- **Where a protein sits.** Nothing here says which calcium pump or exchanger works at
  the outer membrane and which at an internal store.
- **Two names taken on trust.** Two innexin entries (H9CXU2, I1ZIL2) cite papers that were
  not open to read, so they are listed by signature, not as named.
- **The EMRE regulator of the uniporter.** No gene model of this haplotype carries its
  signature; two planarian sequences from other annotation sets do.
- **Whether the gene models are the published ones.** WormBase ParaSite's page of the
  annotation names no paper. That it is the annotation of Ivanković and others (2024) is
  inferred: the assembly has the paper's name, the second haplotype has 21,310 coding
  genes in both, and the first has 21,392 here against the paper's 21,401.
- **The 4,098 gene models without a predicted protein** were not searched, nor were
  haplotype 2 and the older annotation.

## Decisions the lead or the user may want to change

- **U47 is `found`, though the unit is a lumped leak.** The inventory lists the calcium
  uniporter's proteins as the unit's candidates, and gene models carry their signatures.
  If every lumped unit should read `nothing to look for`, this one changes.
- **Six units are `nothing to look for`:** U18, U34, U35, U46, U48 and U49. The inventory
  names no natural gene product for them: three are lumped properties, one a default
  shape of current, one a slot that each configuration fills, and one a designed protein.
  The contract's fourth word was first `not a protein`, which was false for the last
  three, and the designed cage stood under `none found` although nothing was searched.
  The coordinating session changed the word when the atlas and the switch were put
  together (14 November 2026).
- **The whole open set is in the repository,** by the user's decision of 14 November 2026:
  `predicted_proteins.tsv`, 18,882 proteins in 2.2 MB, without sequences. It is, byte for
  byte, the table the first build left with the evidence under `built/`.
- **A link for gene models.** The viewer opens a gene model's own page at WormBase
  ParaSite, from a link template in `data/proteins/overlay.json`, keyed
  `wormbaseparasite`:
  `https://parasite.wormbase.org/Schmidtea_mediterranea_s2f19h1prjna885486/Gene/Summary?g={id}`
  (checked for one gene on 14 November 2026).

## Sources and terms

| Source | What is taken | Terms |
| --- | --- | --- |
| UniProt, release 2026_04 | The species' UniProtKB entries; which archived sequences carry each signature; the human candidates' signatures; control counts | CC BY 4.0 |
| WormBase ParaSite, release 19 | Gene-model identifiers, predicted proteins' identifiers and lengths, and the InterPro matches on them | No restriction stated: "Ensembl imposes no restrictions on access to, or use of, the data provided". It asks that a genome's paper and the database be cited, asks users of an unpublished genome to tell its owners before a large-scale analysis, and warns of third-party constraints. The paper taken to describe this genome is CC BY 4.0 |
| InterPro, release 111.0 | The name and type of each signature entry | CC0 1.0 |
| European Nucleotide Archive | The accession and title of two sequence records, read to tie an entry to the name its paper uses | Free and unrestricted: "no use restrictions or licensing requirements will be included in any sequence data records" |
| Europe PMC | Bibliographic facts of the cited papers | Facts only. Abstracts and open-access texts were read to check names and are not copied |

Read and not copied: the paper and tables of the library of about 10,000 proteins (all
rights reserved); PlanMine, whose front page states no licence or terms of use, only how
to cite it. Xenbase is not used at all.

## What rests on non-commercial or unlicensed sources

The project's rule (D173, 15 November 2026) sorts every source into three classes.
**Permissive** (CC BY, CC0, or a plain statement that no restriction is placed): values
and derived data may enter the repository, with attribution. **Non-commercial** (any
CC BY-NC licence): analysis only. **No stated terms**: nothing enters. A data file here
holds no value and no statement from a source of the last two classes; such a source is
named as a pointer. A note may cite a single value from one, with its class beside it.

**The tables, the atlas and the shelves are built from permissive sources alone:** UniProt
(CC BY 4.0), WormBase ParaSite (no restriction stated), InterPro (CC0), the Gene Ontology
(CC BY 4.0), the nucleotide archive's records, and three papers under CC BY that name
genes (Cowles and others 2014, Vu and others 2015, Roberts-Galbraith and others 2016).
Each source carries its `class` in the files.

**Papers whose terms do not allow a copy are named, and nothing of their findings is
said.** Each has its class on its citation in the atlas:

| Paper | Class | How the atlas names it | What changed on 15 November 2026 |
| --- | --- | --- | --- |
| Oviedo and Levin 2007 | no stated terms | For the name smedinx-11, which the sequence record DQ851133 carries; and as a place to read, in the gap-junction notes | The notes no longer say from its abstract that the gene has been described as a gap-junction gene |
| Abascal and Zardoya 2013 | no stated terms | As a place to read, in the gap-junction notes | The notes no longer say from its abstract that connexins are known only from chordates; they rest on the signatures |
| Beane and others 2013 | no stated terms | For the proton-potassium pump, which the sequence record JX174182 names | Its findings on voltage and head size were taken out of the pump's entry |
| Arenas and others 2017 | no stated terms (an author manuscript, free to read, with no open licence) | For TRPA1, a name the UniProtKB entry carries | Its findings on heat and irritants were taken out of the channel's entry |
| Wagner and others 2012 | no stated terms | UniProtKB entries of innexins cite it; the atlas repeats that | Nothing |
| Wenemoser and others 2012 | no stated terms | A UniProtKB entry of an innexin cites it; the atlas repeats that | Nothing |
| Ying and others 2025 | no stated terms (all rights reserved) | As the library that was not imported | The size of its library is no longer in the atlas or the README. It is said in this note, where the paper's terms are said beside it |
| Howe and others 2017 | non-commercial (CC BY-NC-ND) | The citation that WormBase ParaSite asks for | Nothing: the data are the database's, under its own terms, and nothing is taken from the paper |
| Rozanski and others 2019 | non-commercial (CC BY-NC) | The citation of PlanMine, in the README | Nothing: PlanMine was read and nothing was taken |

**Values cited in this note only:** that the library covers about 10,000 proteins (Ying
and others 2025, all rights reserved).

**Not settled: predictors run by others.** The shelves take membrane-spanning helices and
signal peptides as WormBase ParaSite and UniProt give them out, under those databases'
terms. The databases ran third-party predictors to make them (TMHMM and SignalP at
WormBase ParaSite; Phobius, SignalP and others at UniProt). The predictors' own licences
were not read for this note. If a predictor's terms reach its output, these placements
depend on them; that is for the coordinator and the user to settle.

## What a whole-proteome catalogue would take

Two different things go by that name.

- **The predicted proteome.** Its base is in the repository now: 17,294 gene models with
  lengths and signatures, and the species' 1,588 UniProtKB entries. A catalogue proper
  would add the sequences (33,445 predicted
  proteins with their alternative forms, about 6 MB compressed), the second haplotype,
  current signatures for every model, and names. Names need a similarity search against
  curated proteins of other species: a few CPU-hours, and the first use of the
  contract's `similarity search`. It would also need a table between this annotation's
  identifiers and the ones planarian papers use (SMESG, dd_Smed, SMED3). PlanMine offers
  such look-ups, and its front page states no terms.
- **The measured proteome.** That is the library above. It needs permission, or a
  reanalysis of the open instrument files: tens of gigabytes to fetch and a
  mass-spectrometry search pipeline to run.

Joining either to the engine's protein catalogue is for the lead: that catalogue's
design has not begun.

## The shelves: every protein in a family, on a side of a membrane

**Added on 15 November 2026.** Told that 18,882 proteins were too many to read as one
marker each, the user said: "we should show them all but maybe cool expandable protein
families, same for humans". So every protein of `predicted_proteins.tsv` is now given
one family, a side of a membrane and how that side is known, in the form
`schema/SPECIES_PROTEINS.md` fixes for large catalogues. This is data only; the drawing
comes later.

**Everything here is a prediction on a predicted protein.** Two of the 18,882 sides are
stated by a curated entry, and those by similarity to another species. Nothing says that
the animal makes a protein, where it was seen, or which of the cell's membranes it is in.

### What was made

| File | What it holds | Size |
| --- | --- | --- |
| `shelves.json` | 3,457 families and the 509 parts of "No family assigned", each with its side, its district, how many members sit on each side, and where its members are to be read | 541 KB |
| `shelf_members.tsv` | One line for each of the 18,882 proteins: what it is filed under, its side, the basis, the helices and signal peptide predicted, and the atlas's units it is a candidate for | 860 KB |

Together they add 1.40 MB. No existing file changed its bytes except the folder's
generated README.

### One family for each protein

A family is an InterPro entry of the type Family (release 111.0). A protein is filed
under the narrowest family among its signatures: one that is not a broader kind of
another it carries, by InterPro's own tree of entries.

- 7,231 proteins carry one family and 1,630 carry several. For all but 221 of those,
  the tree leaves one narrowest family.
- For the 221, several unrelated families remain. A rule chooses: the deepest in the
  tree, then the one fewest proteins of this catalogue are in, then the first by
  accession. The rule is the tool's and is stated in the file.
- **10,021 proteins (53%) carry no family signature.** They are kept, under "No family
  assigned" (next).

| Members | Families | Their proteins |
| --- | ---: | ---: |
| 1 | 2,153 | 2,153 |
| 2 to 4 | 977 | 2,433 |
| 5 to 9 | 213 | 1,399 |
| 10 to 49 | 104 | 1,779 |
| 50 or more | 10 | 1,097 |
| All | 3,457 | 8,861 |

The largest are the rhodopsin-like G protein-coupled receptors (415), the major
facilitator superfamily (122), alpha tubulin (98), the small GTPases (89), the epithelial
sodium channels (85) and the innexins (70).

### The proteins with no family

Asked whether a broader grouping would be honest and useful, the answer taken here is yes
for superfamilies, as parts of "No family assigned" and never as families:

- **507 parts are InterPro superfamilies** (entries of the type Homologous superfamily: a
  wider grouping, by shared structure). They hold 5,247 proteins. A protein with several
  superfamilies (2,091 proteins) goes under the one fewest proteins of this catalogue
  carry. The largest are the protein kinase-like domain superfamily (283), TRAF-like
  (181) and the ankyrin repeat-containing domain superfamily (177).
- **887 proteins** carry only a domain, repeat or site signature. No grouping of them was
  made: a protein has as many domains as it has, and none stands for it.
- **3,887 proteins carry no signature of any kind.** Nothing in these sources says what
  they are.

The families' list holds families only, so a reader who wants InterPro families alone
loses nothing. If the superfamily parts are not wanted, the three kinds can be shown as
one pile.

### The side of each protein

| | In a membrane | Beyond one | Inside the cell | Not placed |
| --- | ---: | ---: | ---: | ---: |
| 17,294 gene models, predicted | 4,749 | 1,033 | 10,784 | |
| gene models, by function | | 1 | 62 | |
| gene models, not placed | | | | 665 |
| 1,588 UniProtKB entries, predicted | 611 | 139 | 249 | |
| entries, by function | 24 | 44 | 389 | |
| entries, stated | | 1 | 1 | |
| entries, not placed | | | | 130 |
| **All 18,882** | **5,384** | **1,218** | **11,485** | **795** |

- **Gene models.** WormBase ParaSite ran TMHMM (membrane-spanning helices) and SignalP
  (signal peptides) on the predicted proteins of this annotation and gives the results in
  its BioMart: 8,270 predicted proteins of 5,113 genes have a helix, and 3,533 have a
  signal peptide. The gene's longest predicted protein is read, the one the catalogue
  gives the length of.
  - One helix or more and no signal peptide, or two or more with one: in a membrane.
  - A signal peptide and no helix: beyond a membrane.
  - Neither, on a model that begins with methionine: inside the cell.
- **This tool's own reading, in one case.** 604 models have one helix and a signal
  peptide, and TMHMM can take a signal peptide for a helix. BioMart gives no positions,
  so the sequence is read: a stretch of 19 residues of which 12 or more are hydrophobic
  (A, F, I, L, M, V, W), starting at residue 36 or later, is taken for a
  membrane-spanning stretch (531 models, in a membrane); such a stretch only before that
  is taken for the signal peptide (68, beyond one); 5 have no such stretch and are not
  placed. The rule is this tool's and takes no published scale.
- **UniProtKB entries.** The membrane-spanning segments and signal peptides that
  UniProt's automatic annotation gives the entry (Phobius and SignalP, with some rules).
  Where nothing is predicted, the subcellular location UniProt's rules give it is used,
  and called "by function". The two "stated" are reviewed entries, by similarity.
- **Not placed: 795.** 660 gene models do not begin with methionine and have nothing
  predicted, so a signal peptide may be missing with their beginning; 5 are the ones
  above; 130 entries are fragments that lack their beginning. Where the Gene Ontology
  terms of such a protein name a place that leaves no real doubt (the nucleus, the
  ribosome, the cytoskeleton, the cytosol, the mitochondrion, the cilium, or outside the
  cell), that is used: 63 gene models.

**How the predictions fare.** 783 UniProtKB entries are whole copies of a gene model's
protein, and UniProt places them with other predictors. Where both are placed, the two
agree on 741 of 779 (95%). The disagreements: 15 where the gene model is in a membrane
and the entry is not, 11 the other way, and 12 between inside and beyond. Of the 24 pairs
that this tool's own reading settled, 21 agree; the rule's two numbers (12 of 19) were
set while looking at those pairs, so that is not an independent test of it.

**Limits that the file states.**
- **Which membrane is not predicted.** A predicted helix says that a protein spans a
  membrane, not which. So there is one shelf, "the cell's membranes, not told apart", and
  "beyond a membrane" covers both the outside of the cell and the inside of its
  compartments. An animal cell's several shelves cannot be told apart from these
  predictions.
- **A hint at the place.** Where the Gene Ontology terms of at least half of a family's
  placed members name a place in the cell, the family carries it (`where`): 887 families,
  most often the nucleus (368), the plasma membrane (123) and the mitochondrion (92). It
  is an annotation carried by signatures, not a prediction for these proteins.
- **Helices only.** TMHMM predicts helices. A membrane protein built as a barrel is
  missed: the family of the mitochondrial porin comes out inside the cell.
- **Truncated models.** 1,138 gene models do not begin with methionine.
- **An older run of the signatures.** A gene model's signatures are those WormBase
  ParaSite computed for its release, read under the names and types of InterPro 111.0;
  55 of them are no longer InterPro entries. A current run on the same sequences would
  find families for some of the 10,021 that have none here.

### Districts

A protein's Gene Ontology terms are those InterPro maps to any of its signatures and
those UniProt gives a UniProtKB entry; a gene model takes also the terms of the entries
joined to it. With every broader term, the protein falls in the first district, in the
order below, one of whose terms it carries. A family's members are one kind of protein,
so a family stands where most of its classed members fall. A part of "No family
assigned" is a looser grouping and stands in a district only if more than half of all
its members fall there. The choice of the terms and their order is the viewer's.

| District | Families | Their proteins | With 5 members or more |
| --- | ---: | ---: | ---: |
| Channels | 66 | 545 | 24 |
| Transporters and pumps | 141 | 856 | 48 |
| Receptors and signalling | 156 | 1,083 | 34 |
| DNA, RNA and making proteins | 789 | 1,533 | 55 |
| Protein folding, change, sorting and breakdown | 320 | 701 | 31 |
| Cytoskeleton, movement and adhesion | 133 | 482 | 15 |
| Enzymes and metabolism | 593 | 1,329 | 45 |
| Other functions | 588 | 1,225 | 44 |
| Not classed by function | 671 | 1,107 | 31 |

The file gives each district's terms. Two things to know:
- **InterPro's own mapping alone was too thin.** It gives the innexins no term at all,
  and the sodium:neurotransmitter symporters only "membrane". With the terms of every
  signature a protein carries, and UniProt's terms for the entries, the innexins stand
  among the channels and the symporters among the transporters.
- **The sorting is by terms, not by judgement.** The small GTPases stand under "Enzymes
  and metabolism" because their terms are GTP binding and hydrolysis, and the actins are
  not classed. 7,231 of the 18,882 proteins carry no term of their own.

### Tied to the atlas

- 29 families hold the atlas's candidate products, for 41 of the inventory's units, and
  carry those units' ids (`units`). Each of the 204 products carries its units in the
  members' table.
- **Every family that holds a membrane-spanning product comes out in a membrane,** as the
  atlas draws those units: the sodium, potassium and calcium channels, the innexins, the
  pumps and the exchangers. The build stops if one does not.
- **Three families come out inside the cell, and should:** the calcium channels' beta
  subunit and the potassium channels' beta subunit, which sit on the channel's inner
  face, and the mitochondrial uniporter's regulator MICU, which is not in the membrane.
- 9 products have no family: 5 alpha-2/delta gene models, 2 HCN-like models, 1 innexin
  and 1 calcium-activated potassium channel. Eight carry only domain or superfamily
  signatures; one carries none in this annotation, and the atlas found it through
  UniProt's archive. They sit under "No family assigned" with their units.

### Sizes the drawing will meet, and a proposal

- 3,457 families, of which 2,153 have one member. 327 have five or more and hold 4,275
  proteins; 114 have ten or more and hold 2,876.
- "No family assigned" has 10,021 proteins: 107 superfamily parts of ten or more hold
  4,140; 154 superfamily parts have one member; the two other parts hold 887 and 3,887.
- 271 families have members on more than one side, and each member keeps its own side.
  In 34 families of five or more, the largest side holds less than 70%.

**Proposal.** A family of five or more gets a marker of its own: 327 markers over nine
districts, between 15 and 55 in each. The 3,130 smaller families (4,586 proteins) are
gathered by district and side into one marker, "smaller families", which opens to the
list of its families, each of which opens to its members. "No family assigned" is shown
the same way: the larger superfamilies as markers, the rest gathered, and the two other
parts as two markers. Every protein stays within three openings, and none is hidden.

**How members are read.** The members' table is in the members' order: the families as
`shelves.json` lists them (by district, then size), then the parts. For the page they
are cut into 9 files of at most 2,000 members, a family never split; the part with no
signature is 3,887 and has a file of its own. Each family gives its file and its place
there. `python3 tools/build_planarian_atlas.py members --out DIR` writes the files (2.7
MB in all); they are not kept in the repository.

### What the contract lacked

`schema/SPECIES_PROTEINS.md` needed four things this data has, all declared in the file:
- `units` and `where` as further family columns;
- parts within `no_family`, each with its own file and place, because 10,021 members do
  not fit one file of a few thousand;
- a member's `unit` as a list, because a protein can be a candidate for several units of
  one family;
- a word for the shelf of an animal whose membranes the data cannot tell apart.

### What would change for human

Human is to be done last, the same way. What follows is from general knowledge of the
sources and was not fetched; each figure is to be read from the source when it is.

- **Source.** UniProt's human reference proteome, under CC BY 4.0: about 20,000 reviewed
  entries, one for each protein-coding gene, and several times that when unreviewed
  entries and isoforms are counted, which is where a figure near 100,000 comes from.
  Families from InterPro (CC0), by the same rule.
- **Sides would mostly be stated.** Most reviewed human entries state a subcellular
  location and a topology, curated. So the basis would be "stated" for most, and several
  shelves could be told apart: the cell membrane, the endoplasmic reticulum, the
  mitochondrion's membranes, the nucleus.
- **Size.** With one line for each reviewed entry, the members' table stays near 1 MB and
  this form holds. With every entry it would pass 3 MB: then the reviewed set goes in the
  repository and the rest is built outside it, or members are kept by family only.
- **Not to be copied.** The Human Protein Atlas's tables are outside what this
  repository copies today; where a protein was measured would be linked, not copied.

## How to rebuild

```bash
python3 tools/build_planarian_atlas.py fetch --evidence DIR --datasets DATA   # network: about 6 minutes, 64 MB and 38 MB
python3 tools/build_planarian_atlas.py build --evidence DIR --datasets DATA   # offline: about 45 seconds
python3 tools/build_planarian_atlas.py members --out OUT                      # the shelves' member files, from the tables in the repository
node --test tests/planarian_atlas.test.mjs                                    # set PLANARIAN_EVIDENCE=DIR and PLANARIAN_DATASETS=DATA elsewhere
```

`fetch` asks only what is not yet saved, waits and asks again when a service is busy, and
records each request: the atlas's and the catalogue's in `DIR/requests.json`, the
shelves' in the `MANIFEST.json` of each source's folder under `DATA`
(`/mnt/datasets/Cells/planarian/` on this machine: `wbps-biomart-smedh1prjna885486`,
`interpro-hierarchy-and-go`, `geneontology-go-basic`, `uniprot-smed-topology`). `build`
reads only `DIR`, `DATA` and the inventory snapshot, checks each dataset file against the
SHA-256 its MANIFEST gives, and writes the same bytes every time; the test rebuilds and
compares.
The families, the units' notes and the claims about papers are tables at the top of the
tool; the numbers in the notes are read from the evidence.

The committed atlas was first built by the tool as committed in `714cde36`, from the saved
responses, and the tool as it stands rebuilds the same bytes. The evidence folder's `inputs/` holds the tool and a provenance note as they
were at the first build, with the tool still untracked and before the fourth finding
was renamed. The note names revision `6102c0fa`. That revision is `543bab87` on this
branch today: the same files but for one README passage, in a history that was later
reworded. That build differs from the committed one in the six units listed above as
`nothing to look for`, and in nothing else. The folder itself was left as it was.
