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
| The proteins it names | `data/proteins/planarian/reference_proteins.tsv` (229 proteins: the 227 it names and 2 joined to them; 35 KB) and its `README.md` |
| The tool | `tools/build_planarian_atlas.py`: `fetch` uses the network, `build` does not |
| The check | `node --test tests/planarian_atlas.test.mjs` |
| The evidence | `/mnt/workspaces/Cells/visualizer-planarian-proteins-20261114-01` (65 MB): 179 requests on record, one of them a refusal, and every response that came back |

## Answer

**The library of about 10,000 proteins was found and could not be imported.** It is the
spectral library of Ying and others (2025). Its list of proteins is not in the study's
public deposits, and the paper reserves all rights. Nothing was put in its place. The
details are in the next section.

**The atlas itself is complete: all 49 units have an entry.** For 38 units, planarian
gene products of the same family were found; for 3 the planarian uses a different
family; for 2 nothing was found; for 6 there is nothing to look for. Almost every product is a candidate
found by a sequence signature, not an established counterpart.

**The answers are drawn from gene predictions, and say so.** UniProt holds 1,588 entries
for the species and only four curated ones, none of a family the atlas draws. So the
candidates come from the 17,294 predicted proteins of one genome annotation. Only the
227 proteins the atlas names, and 2 joined to them, are in the repository.

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

Other proteomics of the species exists and was not examined: five MassIVE datasets of
2025 and 2026 from another group (MSV000098119, MSV000098120, MSV000099716, MSV000100775
and MSV000102685). None is the library the user named.

### Other catalogues that were sized

None of these is about 10,000 proteins, and none was imported as "the catalogue".

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
  connexin 45 or connexin 40 to name. Source: "connexins are exclusive of chordates"
  (Abascal and Zardoya 2013, doi:10.1016/j.bbamem.2012.02.007); a planarian innexin
  gap-junction gene, smedinx-11 (Oviedo and Levin 2007, doi:10.1242/dev.006635). In
  support: 68 gene models carry the innexin signature and none the connexin one; no
  flatworm entry in UniProtKB carries the connexin signature, and 21 human ones do.
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
  `extra`. Source: Beane and others (2013), doi:10.1242/dev.086900.
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
- **The whole table of predicted proteins is not in the repository.** It was not asked
  for. The build writes it on request (`--full-table FILE`: 18,882 lines, 2.2 MB), and a
  copy is with the evidence under `built/`.
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

## What a whole-proteome catalogue would take

Two different things go by that name.

- **The predicted proteome.** The build can write its base: 17,294 gene models with
  lengths and signatures. A catalogue proper would add the sequences (33,445 predicted
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

## How to rebuild

```bash
python3 tools/build_planarian_atlas.py fetch --evidence DIR   # network: about 5 minutes, 64 MB
python3 tools/build_planarian_atlas.py build --evidence DIR   # offline: about 45 seconds
node --test tests/planarian_atlas.test.mjs                    # set PLANARIAN_EVIDENCE=DIR elsewhere
```

`fetch` asks only what is not yet saved, waits and asks again when a service is busy, and
records each request in `DIR/requests.json`. `build` reads only `DIR` and the inventory
snapshot and writes the same bytes every time; the test rebuilds and compares. Add
`--full-table FILE` to `build` for the whole table of predicted proteins and entries.
The families, the units' notes and the claims about papers are tables at the top of the
tool; the numbers in the notes are read from the evidence.

The committed atlas was built by the tool as committed in `714cde36`, from the saved
responses. The evidence folder's `inputs/` holds the tool and a provenance note as they
were at the first build, with the tool still untracked and before the fourth finding
was renamed. The note names revision `6102c0fa`. That revision is `543bab87` on this
branch today: the same files but for one README passage, in a history that was later
reworded. That build differs from the committed one in the six units listed above as
`nothing to look for`, and in nothing else. The folder itself was left as it was.
