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
| The shelves | `data/proteins/planarian/shelves.json` (the families, 640 KB) and `shelf_members.tsv` (every protein's family, side and basis, 859 KB), in the form `schema/SPECIES_PROTEINS.md` fixes; see "The shelves" below |
| The own scan | `data/proteins/planarian/interproscan_added.tsv` and `interproscan.json`: the InterPro entries a new scan of all 18,882 proteins added to the lines, and its record (18 November 2026); the machine dossiers read them, and since 19 November 2026 so does the shelves' filing; see "The planarian's own scan" below |
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

**Products by how they were found, and by their records.** The units list 592 product
entries, because units of one family share their candidates. They are 204 different
products. Since 16 November 2026 each product says the two apart (`found_by` and `entry`,
`schema/SPECIES_ATLAS.md`); before, one word mixed them.

| How it was found (`found_by`) | Products | What they are |
| --- | --- | --- |
| named in a publication | 4 | smedinx-11; scna-1, scna-2, scna-3 |
| family signature, of a family that makes the machine | 168 | candidates by family: 10 UniProtKB entries, each joined to a gene model, and 158 gene models |
| accessory signature, only of a family that goes with the machine | 32 | gene models of beta subunits, alpha-2/delta subunits, regulators and the like: no candidates for the machine's own work |
| similarity search | 0 | None was run |

On the shelves (second round, 16 November 2026) the 32 found only by an accessory family's
signature are drawn as plain grey markers, not in the unit's shape or the units' tone, and
each one's panel says how the atlas found it and that it goes with the machine (`found_by`
in `shelves.json`). The table's signature of the sodium channels' beta subunits is now
IPR027098 alone; no planarian sequence carries it, as none carried the two before.

| Their records (`entry`) | Products |
| --- | --- |
| UniProtKB entries, annotated automatically | 14 (the 4 named and the 10 found by signature) |
| Gene models of the genome annotation, with no UniProtKB entry | 190 |
| UniProtKB entries reviewed by a curator | 0 |

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

## The planarian's own scan (InterProScan, 18 November 2026)

**What it is.** The table's `interpro` column holds what each line's own source gave it:
WormBase ParaSite's older scan for the gene models (its highest entry is IPR049704) and
UniProt's current one for its entries. Where a machine's family is numbered above the gene
models' scan, the machine dossiers could only say "cannot tell". So all 18,882 proteins were
scanned again, with InterProScan 5.78-109.0 (EMBL-EBI; Apache License 2.0), run on the
project's own machine with its service of precalculated matches switched off, so that no
sequence was sent anywhere. The sequences were joined to the table one to one before the run,
every length equal. The scan was approved on 18 November 2026.

**What was run, and what was left out.** Three passes over six chunks of the table (3,200
proteins each, the last 2,882): the first pass ran Pfam, SFLD, HAMAP, CATH-Gene3D, NCBIfam,
AntiFam, CDD and Coils; PRINTS ran apart, because one of its jobs needs about 1.5 GB; PANTHER
ran apart. Left out, each for its terms as its provider states them: PROSITE and SMART (not
free to commercial users), SUPERFAMILY (a registration with its staff), PIRSF and PIRSR (PIR
asks commercial users to inform it and report yearly), MobiDB-lite (it bundles a program under
an academic licence agreement), FunFam (not needed), and SignalP, TMHMM and Phobius (vendors'
licences). The pages read are saved with the datasets, in
`planarian/terms-interproscan-member-databases`, whose MANIFEST's note gives each decision; the
programs each analysis calls were read for their licences too, and none is for academic use
only. The matches are the tool's own, with its own cutoffs: nothing is filtered.

**The two files.** Both are written by `tools/read_planarian_scan.py`; the table's own column
is never changed.

| File | What it holds |
| --- | --- |
| `data/proteins/planarian/interproscan_added.tsv` | One line for each protein that the scan gives an InterPro entry its own column lacks: the entries, each with the databases whose signatures reached it (`IPR000001:Pfam,CDD`) |
| `data/proteins/planarian/interproscan.json` | The scan's record: the tool and its release, the days of the run (from the outputs), every file read with its SHA-256; for each database its release as the outputs state it, its terms and class, how many of the 18,882 proteins its pass ran on, its matches, the proteins it matched, the signatures and entries it reached and the matches with no entry; the entries confirmed, added and not found (by cause); what each database could see; the check of the tool's entry list against the run; the entries dropped because the dossiers' InterPro release does not hold them |

A chunk counts only when both of its outputs exist and its pass's log says it ended with exit
0, and the outputs' JSON lists every protein of its input, matched or not; so the record's own
count of proteins for each database says how much of the scan it rests on. An entry the
dossiers' InterPro release (111.0) does not hold is dropped and counted. Coils and AntiFam have
no InterPro entries and are kept as counts only. Every added entry keeps the databases that
found it, so that the entries NCBIfam alone or CDD alone found can be counted or taken out
without a new scan.

**How the machine dossiers read it: two rules side by side.** A dossier looks for each part of
a human machine by its narrowest InterPro families (`schema/MACHINE_DOSSIERS.md`). The scan's
entries count as carried by the line they were found on. They are kept out of the number rule
on purpose: if they were merged into the lines, the highest entry each group carries would jump
past the families that only a database the scan did not run could show, and those would be
called "not in the table", which would be false.

| | The number rule (the table's own column) | The database rule (the scan) |
| --- | --- | --- |
| What it reads | For each group of lines (gene models, UniProtKB entries), the highest entry its own column carries | For each database run, how many of the proteins its pass ran on, and the Family entries in which the tool's own entry list has a signature of it |
| "not in the table" where | no line carries the family, and it is numbered at or below the highest entry that every group carries | no line carries the family (in its own column or by an added entry), the number rule cannot place it, a database that was run has a signature in it, and that database's pass ran on all 18,882 proteins |
| Otherwise | the nearest broader Family that some line carries ("broader"), else "cannot tell" | the same |

Each dossier says which rule placed a family: the families whose level rests on the scan are
listed with the databases they rest on, beside the count of family rows whose level the scan
changed, the candidates found only by added entries (each says so in its row) and the
candidates of the number rule alone that the scan's rule no longer gives. A family the scan
shows absent, where a broader family stood in before, loses that broader family's candidates:
the scan could see the family itself, on every protein, and no protein carries it.

**How the shelves read it.** On 19 November 2026 it was decided that the shelves take the
scan's added entries. Since then a protein's signatures, for its filing alone, are those of the
table's own column and the entries the scan added to its line; the rule is unchanged (the
narrowest family, then the deepest, then the one fewer proteins are in, then the first by
accession; else a superfamily, else the two other parts of "No family assigned"). The side of a
protein and its basis, the districts and the places named for a family read the column alone,
as before: the user's decision was put as filing by family. The two rules side by side:

| | Before 19 November 2026 | Since |
| --- | --- | --- |
| A protein's family, or its part of "No family assigned" | the table's own column | the column and the scan's added entries |
| Its side and the basis of it (where places are read) | the column | the column |
| Its district, and a family's district and named places | the column | the column |
| What a placement says it rests on | the column, as for every protein | a member filed by an entry the scan added carries the mark `scan`, the databases whose signatures reached that entry, and its panel says so with the tool's release and the days of the run |

What it changed, counted by the build against the filing by the column alone, and checked
protein by protein against the members' table before it: 3,147 proteins stand on another shelf
than before. 3,117 of them gained an entry and are filed by what the scan added (3,056 under a
family, 7 under a superfamily, 54 that had no signature and now carry only the scan's domain,
repeat or site entries). 2,650 left "No family assigned" (10,021 before, 7,371 now), none entered
it, and 61 moved between its parts. 30 gained nothing: each is a UniProtKB entry that carries two
unrelated families of its own, and the rule's second step (the family fewer proteins are in) now
counts what the scan added to other lines; 18 of them are settled by the accession, 12 by size.
Proteins filed among several unrelated families: 221 before, 972 now. The placements rest on
PANTHER 3,031, Pfam 77, CDD 8, CATH-Gene3D 7 and NCBIfam 3 (a placement may rest on two); on CDD
alone 7, on NCBIfam alone 2. Had the rest read the added entries too, no side and no basis would
change, none of the 795 proteins not placed would be placed, 112 proteins would fall in another
district (31 families) and the places named for 6 families would change. The scan agrees with
what the report of its reader (`report`, below) predicted for the shelves, to the protein.

**The record's numbers.** The block below is written by the tool from the record
(`python3 -I tools/read_planarian_scan.py note`), and the planarian scan's test fails when it
is not the record's.

<!-- planarian-scan: begin (written by tools/read_planarian_scan.py note) -->

The record as built (2026-11-18 to 2026-11-19; 36 output files read). The full run replaces these numbers; the record's own count of proteins per database is what keeps a partial build truthful.

| Pass | Chunks counted | Databases |
| --- | --- | --- |
| `pass1` | 6 of 6 (chunk-01, chunk-02, chunk-03, chunk-04, chunk-05, chunk-06) | Pfam, SFLD, HAMAP, CATH-Gene3D, NCBIfam, AntiFam, CDD, Coils |
| `pass1-prints` | 6 of 6 (chunk-01, chunk-02, chunk-03, chunk-04, chunk-05, chunk-06) | PRINTS |
| `pass2-panther` | 6 of 6 (chunk-01, chunk-02, chunk-03, chunk-04, chunk-05, chunk-06) | PANTHER |

| Database | Release (outputs) | Proteins run on | Matches | Proteins matched | Entries reached | Matches with no entry | Added | Added by it alone |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Pfam | 38.2 | 18,882 of 18,882 | 20,990 | 13,767 | 4,686 | 846 | 1,441 | 1,421 |
| PRINTS | 42.0 | 18,882 of 18,882 | 4,472 | 3,720 | 436 | 550 | 0 | 0 |
| SFLD | 4 | 18,882 of 18,882 | 191 | 73 | 17 | 125 | 2 | 2 |
| HAMAP | 2026_01 | 18,882 of 18,882 | 297 | 288 | 219 | 0 | 0 | 0 |
| CATH-Gene3D | 4.3.0 | 18,882 of 18,882 | 24,574 | 12,493 | 977 | 10,211 | 28 | 28 |
| NCBIfam | 19.0 | 18,882 of 18,882 | 1,354 | 1,088 | 443 | 320 | 13 | 12 |
| PANTHER | 19.0 | 18,882 of 18,882 | 13,813 | 13,813 | 3,577 | 3,830 | 3,551 | 3,534 |
| CDD | 3.21 | 18,882 of 18,882 | 7,640 | 5,265 | 750 | 4,864 | 89 | 85 |
| AntiFam (counts only) | not stated | 18,882 of 18,882 | 0 | 0 |  |  |  |  |
| Coils (counts only) | 2.2.1 | 18,882 of 18,882 | 7,704 | 3,606 |  |  |  |  |

- Entries confirmed (a protein's own entry found again): 37,545; added: 5,103, on 4,466 proteins; added by NCBIfam alone: 12; by CDD alone: 85.
- Dropped because the dossier's InterPro release (111.0) does not hold them: 154 (28 entries).
- The table's own entries the scan did not find, on the proteins a counted pass ran on: 16,916; no database run on the protein has a signature in the entry: 13,698; one has and did not match: 3,063; not in the tool's list: 155.
- The tool's entry list against the run: 14,868 signatures compared, 0 differences, 0 not in the list.

<!-- planarian-scan: end -->

**The sources, and what they rest on.** Each database behind a value is a source of the record,
with its terms as read and its class; the tool is named as the tool.

| Source | Terms, as read | Class |
| --- | --- | --- |
| InterProScan 5.78-109.0 (EMBL-EBI) | Apache License 2.0: the tool, not a database, so it is named and not classed | |
| InterPro (which signature belongs to which entry) | CC0 1.0 | Permissive |
| Pfam, PRINTS, SFLD | CC0 1.0, by InterPro's licence page | Permissive |
| HAMAP | CC BY 4.0 | Permissive |
| CATH-Gene3D | CC BY 4.0 | Permissive |
| NCBIfam (with TIGRFAMs) | CC BY-SA 4.0, share-alike | Permissive by the classes' spelling, not by a ruling |
| PANTHER | CC BY 4.0 for its data and data products; its terms page was read in a browser on 18 November 2026, its site refusing automated reads | Permissive |
| CDD | No terms stated, on its own page or on NCBI's policies page | No stated terms; used by the decision of 18 November 2026 (next section) |
| AntiFam | CC0 1.0, by InterPro's page on AntiFam (counts only) | Permissive |

Where the saved pages give a citation (HAMAP, NCBIfam, AntiFam, and InterPro's from the
atlas's own sources), the record carries it; for Pfam, PRINTS, SFLD, CATH-Gene3D, PANTHER, CDD
and the tool itself no citation text was saved, and the record says so.

**How to make the files again.**

```bash
python3 -I tools/read_planarian_scan.py build --scan SCAN --tool TOOL --datasets DATA  # the two files and the block above
python3 -I tools/read_planarian_scan.py report --datasets DATA --out FILE              # what the added entries would change for the atlas and the shelves
python3 -I tools/gather_machines.py build --datasets DATA                              # the dossiers
python3 tools/build_catalogue.py                                                       # the benches and the catalogue
python3 tools/build_planarian_atlas.py build --evidence DIR --datasets DATA/planarian  # the shelves, whose filing reads the two files
node --test tests/planarian_scan.test.mjs tests/planarian_atlas.test.mjs
```

`SCAN` is the scan's folder (its `out/`, `logs/` and `input/`), `TOOL` the tool's unpacked
folder (its entry list is `work/kvs/idb/entries.json`), `DATA` the datasets folder. Nothing is
written in `SCAN`.

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

**The tables, the atlas and the shelves take what they hold from permissive sources
alone,** but for CDD behind 8 of the shelves' placements (below): UniProt (CC BY 4.0),
WormBase ParaSite (no restriction stated), InterPro (CC0), the Gene Ontology (CC BY 4.0), the
nucleotide archive's records, three papers under CC BY that name genes (Cowles and others
2014, Vu and others 2015, Roberts-Galbraith and others 2016), and, behind the shelves'
filing since 19 November 2026, the scan's databases. Each source carries its `class` in the
files. **But nearly every side in the shelves is a prediction that one of those databases
gives out and a program of another owner computed.** That is set out at the end of this
section.

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

**The planarian's own scan (18 November 2026).** Two of the databases behind the entries the
scan added are not plainly permissive. **NCBIfam** (with TIGRFAMs) is under CC BY-SA 4.0, a
share-alike licence: the classes count it permissive by its spelling, not by a ruling, and its
matches are named as NCBIfam's wherever they are used. **CDD**, NCBI's Conserved Domain
Database, states no terms, on its own page or on NCBI's policies page; NCBI's general sentence
on its molecular databases is not CDD's own, and CDD is not classed by it. It was decided on
18 November 2026 that a database whose provider states no terms may be used for this scan where
it is publicly available. So CDD stands, of the class no stated terms, behind entries the scan
added and behind the dossiers' values that rest on them, and the licence test keeps it in a
register of its own (`DECIDED`, by species), so that a second source of that class fails the
test and is put to the user. Every added entry keeps its databases, and the scan's record
counts the entries NCBIfam alone and CDD alone added, so that either can be taken out without a
new scan.

**The shelves since 19 November 2026.** On 19 November 2026 it was decided that the shelves
take the scan's added entries, so the scan's databases now stand behind placements on the
shelves too, each a source of `shelves.json` copied from the scan's record with its terms and
class. **PANTHER** (CC BY 4.0 for its data and data products, its terms page read in a browser
because its site refuses automated reads) stands behind 3,031 of the 3,117 placements that rest
on the scan, 3,023 of them on it alone. **NCBIfam** (CC BY-SA 4.0, share-alike) stands behind 3,
2 on it alone. **CDD** (no stated terms, by the decision of 18 November 2026) stands behind 8, 7
on it alone; the licence test holds the shelves' copy of it through the same register `DECIDED`
as the scan's record and the dossiers' copies, so a second source of that class fails there as
well. Pfam (CC0 1.0) stands behind 77 and CATH-Gene3D (CC BY 4.0) behind 7. Each such member
names the databases behind it in its panel and in the members' file, CDD and NCBIfam with their
terms.

**What the two databases give out that others computed.** The helices and signal
peptides behind the sides were predicted by programs that WormBase ParaSite and UniProt
ran. Each database says this of what it gives out:

- WormBase ParaSite's disclaimer, after "Ensembl imposes no restrictions on access to, or
  use of, the data provided", goes on: "Some of the data and software included in the
  distribution may be subject to third-party constraints. Users of the data and software
  are solely responsible for establishing the nature of and complying with any such
  restrictions." The shelves' file now quotes that sentence too.
- UniProt's licence page says: "We cannot provide unrestricted permission regarding the
  use of the data, as some data may be covered by patents or other rights."

Each tool's terms were read at its own page on 15 November 2026 and the page was saved;
nothing else was downloaded from any of them, and no program was run. The shelves name
each as a source with `through`, the database or databases its results were read in.

| Tool or rule system | Its own terms, as read | Class | Read through | Sides that rest on it |
| --- | --- | --- | --- | --- |
| TMHMM | Academic licence of DTU Health Tech: free to publicly funded institutions for internal research; any other user must obtain a commercial licence, and no use of the program may result in commercialization. A licence of the program: no clause speaks of predictions made with it | Non-commercial | WormBase ParaSite and UniProt | Gene models: all 16,566 predicted sides rest on what it and SignalP found or did not find (4,218 in a membrane by helices; 599 with one helix and a signal peptide, settled by this tool's own reading; 965 outside by a signal peptide; 10,784 inside because neither found anything). Entries: 578 in a membrane by segments that UniProt keeps where TMHMM and Phobius overlap, and 249 inside because nothing was found |
| SignalP | Academic licence of DTU Health Tech, as TMHMM's | Non-commercial | WormBase ParaSite and UniProt | The gene models counted under TMHMM; and 131 entries placed outside by a signal peptide |
| Phobius | For academic users only: private study, education or nonprofit research. Terms of the program | Non-commercial | UniProt | The entries counted under TMHMM and SignalP |
| PROSITE (its rules, ProRule) | CC BY-NC-ND 4.0; commercial users pay a licence fee "irrespective of the method by which they access the database" | Non-commercial | UniProt | 3 entries placed in a membrane by segments that carry one of its rules; 146 entries placed by function on a stated place that names one, 50 of them on no other rule |
| HAMAP (family rules) | CC BY 4.0 | Permissive | UniProt | 1 entry placed by function |
| RuleBase, ARBA and the PIR rules | No terms of their own were read: UniProt's help pages describe them as parts of its annotation pipeline, and UniProt's entries are CC BY 4.0 | Not classed separately | none: they come with UniProt's entries | 38 entries placed by a segment or a signal peptide they give; 255 placed by function on a place they state |

So 17,524 of the 17,565 predicted sides rest on the three academic programs, and 149
sides rest at least in part on PROSITE's rules. The 118 sides placed by function from
Gene Ontology terms, and the 795 not placed, rest on none of them.

**What could not be read.** WormBase ParaSite's BioMart names TMHMM and SignalP and no
version of either, and its service that lists a genome's analyses did not answer. The
licence read for each program is the one DTU Health Tech shows on its download page
today; an older version may have been given out on other words.

**Two kinds of terms.** The licences of TMHMM and SignalP and the terms of Phobius are of
the programs: they say who may run them and say nothing of predictions made with them,
and it was the two databases that ran them. PROSITE's terms are of the database itself,
of which its rules are part, and its page says that commercial users pay a licence fee
"irrespective of the method by which they access the database". These are not the same
kind of dependence.

**The project's rule (the user, 15 November 2026): a value stands on the terms of the
database it was read from, and the tool behind it is named and counted.** The
coordinating session asked the user whether placement values read from open databases
may stay, with every tool named and counted; the user answered "yes". Every side here
was read in WormBase ParaSite's or UniProt's records, which the two databases give out
under their own open terms, so each stands as its database gives it, and none was
changed.

- What was found for the ruling in the saved pages: the programs' licences cover running
  the program, and it was the databases that ran them and publish the results under their
  own terms; PROSITE belongs to the SIB Swiss Institute of Bioinformatics, which is one of
  the three institutes that make UniProt (UniProt's own "About" page, saved with the
  human data's downloads under `terms-uniprot-consortium`); and InterPro's licence page
  says of its scanning software: "The included scanning tools and signature collections
  may be under different license terms. You do not need a special license for commercial
  use but please cite the resource and relevant individual member databases".
- It is the user's ruling for this project, not a legal opinion. Nothing here says what
  any of these terms allow in law.
- Every tool stays named in the file with its own terms and its count, each such side is
  said to be predicted wherever it is shown, and the licence test keeps a register of
  them (`tests/licence_classes.test.mjs`), so that a new one is noticed and put to the
  user.

The families and districts do not rest on these programs: they come from InterPro (CC0)
and the Gene Ontology (CC BY 4.0). InterPro's entries do gather the signatures of member
databases, PROSITE among them; its licence page, quoted above, is what was read of that.
By the same rule the families stand on InterPro's terms, since they were read in its
records. The member databases behind each InterPro entry of the table's own column are not
named or counted in the files: that was not looked into. Those behind an entry the
species' own scan added are: the scan ran their signatures itself, and each placement that
rests on one names them (above).

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
| `shelves.json` | 4,232 families and the 380 parts of "No family assigned", each with its side, its district, how many members sit on each side, and where its members are to be read | 640 KB |
| `shelf_members.tsv` | One line for each of the 18,882 proteins: what it is filed under, its side, the basis, the helices and signal peptide predicted, and the atlas's units it is a candidate for | 859 KB |

Together they add 1.50 MB (1.40 MB when first made; the files grew when the filing began to
read the species' own scan, 19 November 2026, and stand about 1 KB under the 1.5 MB that
`tests/planarian_atlas.test.mjs` holds them to). No existing file changed its bytes except the
folder's generated README.

### One family for each protein

A family is an InterPro entry of the type Family (release 111.0). A protein is filed
under the narrowest family among its signatures: one that is not a broader kind of
another it carries, by InterPro's own tree of entries. Its signatures are those of the
table's own column and, since 19 November 2026, the entries the species' own scan added to
its line ("The planarian's own scan", above); the counts here are of both together.

- 9,164 proteins carry one family and 2,347 carry several (7,231 and 1,630 by the column
  alone). For all but 972 of those, the tree leaves one narrowest family (221 by the column
  alone).
- For the 972, several unrelated families remain. A rule chooses: the deepest in the
  tree, then the one fewest proteins of this catalogue are in, then the first by
  accession. The rule is the tool's and is stated in the file. For 775 of the 972, one of
  the unrelated families is one that PANTHER's signatures added: InterPro's tree mostly
  does not put a PANTHER-made family under the older family of the same proteins.
- **7,371 proteins (39%) carry no family signature** (10,021, 53%, by the column alone).
  They are kept, under "No family assigned" (next).

| Members | Families | Their proteins |
| --- | ---: | ---: |
| 1 | 2,476 | 2,476 |
| 2 to 4 | 1,258 | 3,171 |
| 5 to 9 | 328 | 2,132 |
| 10 to 49 | 160 | 2,753 |
| 50 or more | 10 | 979 |
| All | 4,232 | 11,511 |

The largest are the rhodopsin-like G protein-coupled receptors (349), alpha tubulin (98),
PANTHER's GPCR_Ligand_Interaction (94), the epithelial sodium channels (85), the innexins
(70), and the sodium:neurotransmitter symporters and PANTHER's proton-linked monocarboxylate
transporters (65 each). By the column alone the major facilitator superfamily (122) and the
small GTPases (89) were among them; the scan's narrower families took most of their members
(39 and 20 are left).

### The proteins with no family

Asked whether a broader grouping would be honest and useful, the answer taken here is yes
for superfamilies, as parts of "No family assigned" and never as families:

- **378 parts are InterPro superfamilies** (entries of the type Homologous superfamily: a
  wider grouping, by shared structure). They hold 2,949 proteins. A protein with several
  superfamilies (1,171 proteins) goes under the one fewest proteins of this catalogue
  carry. The largest are TRAF-like (179), the ankyrin repeat-containing domain superfamily
  (126) and the protein kinase-like domain superfamily (123). (By the column alone: 507
  parts holding 5,247, the protein kinase-like domain superfamily the largest at 283.)
- **671 proteins** carry only a domain, repeat or site signature (887 by the column alone;
  54 of the 671 carry only entries the scan added). No grouping of them was made: a protein
  has as many domains as it has, and none stands for it.
- **3,751 proteins carry no signature of any kind** (3,887 by the column alone): neither
  their line's own scan nor the species' own scan found one. Nothing in these sources says
  what they are.

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
  UniProt's automatic annotation gives the entry. By UniProt's own account its sequence
  analysis keeps a segment where TMHMM and Phobius overlap, and gives the signal peptide
  SignalP predicts where TMHMM or Phobius bears it out; some segments and signal peptides
  are given by its rule systems instead. Where nothing is predicted, the subcellular
  location UniProt's rules give it is used, and called "by function". The two "stated"
  are reviewed entries, by similarity.
- **What the predicted sides rest on.** Of the 17,565 predicted sides, 17,524 rest on
  what TMHMM, SignalP and Phobius found or did not find: all 16,566 of the gene models,
  and 958 of the entries. The section "What rests on non-commercial or unlicensed
  sources" gives each tool with its terms.
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
  placed members name a place in the cell, the family carries it (`where`): 903 families,
  most often the nucleus (379), the plasma membrane (120) and the mitochondrion (91). It
  is an annotation carried by signatures, not a prediction for these proteins. The terms
  are those of the table's own column: the scan's added entries are not read for places.
- **Helices only.** TMHMM predicts helices. A membrane protein built as a barrel is
  missed: the family of the mitochondrial porin comes out inside the cell.
- **Truncated models.** 1,138 gene models do not begin with methionine.
- **An older run of the signatures.** A gene model's own signatures are those WormBase
  ParaSite computed for its release, read under the names and types of InterPro 111.0;
  55 of them are no longer InterPro entries. The species' own scan, a current run on the
  same sequences, found families for 2,650 of the 10,021 that had none, and since 19
  November 2026 the filing reads it; the sides, the districts and the places do not.

### Districts

A protein's Gene Ontology terms are those InterPro maps to any of its signatures in the
table's own column (not those the species' own scan added) and those UniProt gives a
UniProtKB entry; a gene model takes also the terms of the entries joined to it. With every broader term, the protein falls in the first district, in the
order below, one of whose terms it carries. A family's members are one kind of protein,
so a family stands where most of its classed members fall. A part of "No family
assigned" is a looser grouping and stands in a district only if more than half of all
its members fall there. The choice of the terms and their order is the viewer's.

| District | Families | Their proteins | With 5 members or more |
| --- | ---: | ---: | ---: |
| Channels | 71 | 591 | 26 |
| Transporters and pumps | 150 | 893 | 55 |
| Receptors and signalling | 168 | 1,227 | 47 |
| DNA, RNA and making proteins | 861 | 1,894 | 87 |
| Protein folding, change, sorting and breakdown | 387 | 1,171 | 63 |
| Cytoskeleton, movement and adhesion | 140 | 601 | 20 |
| Enzymes and metabolism | 683 | 1,525 | 61 |
| Other functions | 830 | 1,912 | 83 |
| Not classed by function | 942 | 1,697 | 56 |

"Not classed by function" grew from 671 families: a family whose members only the scan
filed, and whose own lines carry no term, stands there (PANTHER's Blood Group
Antigen-Binding Lectin, 50 members, among them). Had the districts read the added entries
too, 112 proteins would fall in another district and 31 families would stand in another,
923 of them not classed.

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
  members' table. The products themselves, and every unit's finding, are the atlas's and
  read the table's own column; where a product is filed on the shelves follows the filing,
  so since 19 November 2026 14 products stand in another family than before (below).
- **Every family that holds a membrane-spanning product comes out in a membrane,** as the
  atlas draws those units: the sodium, potassium and calcium channels, the innexins, the
  pumps and the exchangers. The build stops if one does not.
- **Three families come out inside the cell, and should:** the calcium channels' beta
  subunit and the potassium channels' beta subunit, which sit on the channel's inner
  face, and the mitochondrial uniporter's regulator MICU, which is not in the membrane.
- 1 product has no family: an innexin gene model with only domain signatures, under "No
  family assigned" with its units. By the column alone 9 had none; the scan's entries file
  the other 8: the 5 alpha-2/delta gene models under PANTHER's Voltage-dependent calcium
  channel subunit alpha-2/delta (IPR051173, now a family with units U24 to U30), the 2
  HCN-like models under the HCN-type family IPR051413, and the calcium-activated potassium
  channel model that carried no signature at all under the BK beta subunit's IPR003930.
- 6 more products moved with nothing added, by the tie-break among the two unrelated
  families of their own: the 5 sodium-calcium exchanger entries of U42 (from IPR051171 to
  IPR004836, so IPR051171 no longer holds a product) and A0A1Z1R0Y6 of U20 to U23 (from the
  HCN-type IPR051413 to IPR003938; its own gene model is now in IPR051413).

### Sizes the drawing will meet, and a proposal

- 4,232 families, of which 2,476 have one member. 498 have five or more and hold 5,864
  proteins; 170 have ten or more and hold 3,732. (By the column alone: 3,457, 2,153, 327
  holding 4,275, 114 holding 2,876.)
- "No family assigned" has 7,371 proteins: 62 superfamily parts of ten or more hold
  2,059; 139 superfamily parts have one member; the two other parts hold 671 and 3,751.
- 409 families have members on more than one side, and each member keeps its own side.
  In 59 families of five or more, the largest side holds less than 70%.
- The page draws 599 markers at rest (473 by the column alone).

**Proposal** (as made on 15 November 2026, with that day's numbers). A family of five or more gets a marker of its own: 327 markers over nine
districts, between 15 and 55 in each. The 3,130 smaller families (4,586 proteins) are
gathered by district and side into one marker, "smaller families", which opens to the
list of its families, each of which opens to its members. "No family assigned" is shown
the same way: the larger superfamilies as markers, the rest gathered, and the two other
parts as two markers. Every protein stays within three openings, and none is hidden.

**How members are read.** The members' table is in the members' order: the families as
`shelves.json` lists them (by district, then size), then the parts. For the page they
are cut into 9 files of at most 2,000 members, a family never split; the part with no
signature is 3,751 and has a file of its own. Each family gives its file and its place
there. A member filed by what the species' own scan added carries the mark `scan`, the
databases behind it, cut from `interproscan_added.tsv` and its `under`. `python3
tools/build_planarian_atlas.py members --out DIR` writes the files (2.6 MB in all); they
are not kept in the repository.

### What the contract lacked

`schema/SPECIES_PROTEINS.md` needed four things this data has, all declared in the file:
- `units` and `where` as further family columns;
- parts within `no_family`, each with its own file and place, because 10,021 members (7,371
  since the scan) do not fit one file of a few thousand;
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
