# JCVI-syn3A as Cells' minimal-cell track: evidence audit, probes and first milestone

> **Legacy cleanup (25 November 2026, D386).** Paths under `src/cells/legacy/` and the older model
> IDs named below left the engine. The tag `pre-cleanup-2026-11-25` keeps them.

Status: **the track was adopted on 14 November 2026 (D173).**
- **This revision (15 November)** adds the five follow-up steps D173 named:
  - the search for the missing division data;
  - the check of D150's exchange;
  - the Frallicciardi 2022 audit;
  - probe P0 and its follow-ups;
  - the scale of the metabolism stage.

  It also adds the *M. pneumoniae* audit (D173, amended).
- **A third pass (15 November, after the merge at baf09d0)** does five things:
  - restates the passive contract in ARCHITECTURE.md's corrected wording (§5.3);
  - finds two closed pairs on main by probe (§5.4);
  - narrows the first milestone to numerical judged content (§6);
  - opens the Wodke files and names one measured perturbation (§9.3);
  - records the Moger-Reischer data and the Frallicciardi reuse terms.
- **A licence follow-up (15 November, after D173's licence decision)** maps every place a
  milestone or stage rests on non-commercial data, or on data with no stated terms, and names
  permissive alternatives where they exist (§3.1).
- **No engine code was written.** The probes ran the engine from a frozen snapshot of main as a
  capability check only. Nothing here is an acceptance.
- **Source:** the user's research brief, `docs/SOTA_SYN3A.md` (untracked in the main checkout).
  Every claim and link in it was treated as a lead and checked at the primary source.
- **Builds on:**
  - [the 4D whole-cell paper review](PAPER_REVIEW_WHOLE_CELL_MINIMAL_CELL.md);
  - the [protein catalogue plan](PROTEIN_CATALOGUE_PLAN.md);
  - [ARCHITECTURE.md's modular core](ARCHITECTURE.md) (D172, D174).
- **Evidence:** [/mnt/workspaces/Cells/syn3a-20261114-01](/mnt/workspaces/Cells/syn3a-20261114-01/HANDOFF.md).
  It holds:
  - the inventories (`syn3a_evidence_inventory.json`, `mpneumoniae_evidence_inventory.json`);
  - the probe criteria, scripts and results (`p0/`);
  - the access log.
- **Data:** `/mnt/datasets/Cells/syn3a/<source-id>/` and `/mnt/datasets/Cells/mpneumoniae/<source-id>/`,
  one folder per source. Each folder's `MANIFEST.json` gives every file's URL, retrieval time,
  size and SHA-256.
  - Seven other folders under `syn3a/` come from other agents: six from the visualizer's Syn3A
    agent, and `biopython-185-protparam`. They are left untouched and are not counted here.

**S** marks our own arithmetic or inference.

## 0. Verdict

- **Syn3A stays a defensible first whole-cell organism, but its public evidence is thin.**
  - **The division data:** Pelletier 2021's division deposit is in no public source checked. Its
    DOI looks reserved but never published (§1.1).
  - **The reconstituted-membrane archive:** the 2026 Zenodo archive holds molecular dynamics only.
  - **The lipid-diet study:** it used a tagged strain. It measured permeability and lysis only
    across chirality diets, which its authors attribute to lipid–protein interactions.
  - **The two protein lists:** 452 native genes, or 455 with three engineered markers. A model must
    freeze one.
- **The vesicle physics already runs in the engine, as a probe (§5).**
  - **Admission:** a vesicle with no channels and no pumps is admitted under water@1, starting
    from the stepped state.
  - **Accuracy:** its shrinkage matches the closed form at second order, to between 1e-8 and
    3e-7 relative at the finest step, depending on the world.
  - **A permeant neutral row:** a row on the inner model's own constant-field route (valence 0, so
    Fick's law) gives the shrinkage and the start of recovery over the 2 s run, within 6e-8 of an
    independent two-variable reference. No run went on to full recovery.
  - **What fails:** a start from a trace concentration is refused by the energy ledger. The
    experiment's own start (no glycerol in the lumen) is such a start, so **S2-M1 cannot be judged
    on today's engine.** A declared start at 1e-4 of the bath runs, at an osmotic bias of about
    4e-5 (**S**), but it is a workaround.
- **Exchange is a driven route, not passive permeation, as D174 records.** It books signed work
  and no heat; that verdict is on paper, from its contract.
- **A closed pair exists on main today (§5.4).** One cell and one finite outside node, with no
  reservoir and no water, is admitted.
  - There the constant-field route at valence 0 passes the corrected passive test from resolved
    starts:
    - material conserved to 1.5e-16;
    - zero flux at equal potential;
    - exact reversal;
    - dissipation equal to the free-energy decrease to 1.1e-6, with no work.
  - Only a trace start fails.
  - The held-bath vesicle runs are not that test. They show the coupled behaviour and a total
    balance that closes with the reservoir's work (§5.3).
- **The generic passive law that D174 expects in D172's round has a kernel already.** The law must
  add:
  - exact free-energy booking as heat;
  - finding 3's valence-0 bound term;
  - a trace policy.
- **The first milestone, narrowed (§6):** its judged content is numerical. The passive contract,
  then water coupling, at vesicle scale, against references written by a separate agent.
  - Calibration and the glycerol arm on the Frallicciardi 2022 traces are reported only. That
    holds unless a check registered beforehand catches a planted error with margin, as MG0c's
    controls do.
  - The reasons: within-trace fitting, a thin margin, and the authors' own refits.
  - Syn3A-lipid vesicles are analysis only, in the workspace, because Presutti 2026 is
    non-commercial and has no permissive measured alternative. There is no living-cell claim.
  - **Licences (§3.1):** the judged content depends on no external data. The Frallicciardi raw
    traces have no stated terms, so their arms publish summary statistics and verdicts only.
- ***M. pneumoniae* is richer in measured physiology, and should lead an energy, transport and pH
  stage tied to FR-4 (§9).**
  - It has measured protein turnover, and absolute mRNA and protein copy numbers under several
    perturbations.
  - It has numeric pH-challenge data and a 158 h lactate and glucose time course with a
    rebuffered arm (opened from the .xls files). Acetate, pH and protein time courses are
    figures only.
  - Rebuffering a stalled, acidified culture is one measured perturbation that FR-4 and
    finite fuel could predict without a growth model (§9.3). Its biomass is a declared input,
    so the prediction is relative to the unbuffered arm.
  - Its integrated database is offline, and most of its "1,748 data sets" are growth curves.
  - **Licences (§3.1):** its three main sources are non-commercial, so under D173 they serve
    analysis only.
    - CC BY counterparts exist for protein abundance (Weber et al. 2023, 528 proteins) and
      turnover (Burgos et al. 2020, 488 proteins).
    - None was found for the rebuffering perturbation. A judged Stage 4a on it would therefore
      rest on non-commercial data, which needs the user's decision.
- **Metabolism is 10 to 100 times beyond today's 16-species cap, and gene expression is
  low-copy** (§4.3). Stage 4 needs both F8 (metabolism at scale) and F11 (a stochastic regime).

## 1. The evidence audit (Stage 1)

**How categories are assigned.**
- They follow the brief's §6 table.
- They are relative to the declared target, JCVI-syn3A with genome CP016816.2.
- A labelled derivative (Syn3A-mCherry, Syn3B) is its own strain record. For this target it counts
  as a related strain.
- Full records are in the inventory JSON.

| Resource | Identifier and status | Contents, size, licence | Strain, medium, temperature, assay | Category | Downloaded |
| --- | --- | --- | --- | --- | --- |
| Proteomics (Breuer et al. 2019, *eLife* 8:e36842) | PXD008159 = MSV000081687. Hosted by MassIVE; the PRIDE API returns 404 | 21 files, 9.03 GB: 8 Thermo raw (2.69 GB), 9 mzML (6.30 GB), a PSM mzTab (21 MB). CC0 | Syn3A; SP4 with horse serum in place of FBS; 37 °C; log, early-plateau and plateau phases, 3 biological replicates each; TMT LC-MS3 | Measured: 428 proteins' relative abundances. Inferred: absolute copies, scaled by an assumed protein mass fraction | mzTab, parameters, statistics; the paper's supplementary files 1–11 (1.6 MB, CC BY) |
| Division and morphology (Pelletier et al. 2021, *Cell* 184:2430) | Mendeley 10.17632/rwg6sdz4rf.1, as the paper gives it. **Not found anywhere public** (§1.1) | Declared: source data and code for Figs 1D, 4D and 5E (area histograms), and chemostat videos. The *Cell* article's own supplement holds Table S1 and Videos S1–S4 | syn1.0, syn3.0, syn3A and syn3.0 with gene subsets; SP4 with FBS; time-lapse microscopy in microfluidic chemostats | Measured per strain, but unreachable | Records of the lookups |
| Cryo-ET (Gilbert et al. 2021, *Front. Mol. Biosci.* 8:644133) | EMPIAR-10685 and -10686 (EMD-23660, -23661) | 6.5 and 6.4 GB: one raw tilt series and its frames per entry, one cell each | Syn3A; SP4 with KnockOut serum replacement (SP4-KO); 37 °C; mid-log | Measured: boundary and ribosomes, in cells flattened to about 160 nm by blotting. Inferred: the spherical reconstruction and chromosome paths | Entry metadata |
| 3C (same paper) | 4TU 10.4121/14333618 | One processed `.hic` contact map, 866 KB (MD5 verified). CC0 | Syn3A; SP4-KO; 37 °C; stationary phase; NlaIII 3C-seq | Measured | Yes |
| Evolution and expression (Sandberg et al. 2023, *iScience* 26:107500) | GEO GSE205017; reads under PRJNA843075 | 13 processed per-sample tables (90 KB), the genome and its GFF3. Paper CC BY-NC-ND | Syn3A ancestor and clones from 10 lineages after about 400 generations; SP4-KO; 37 °C; log phase | Measured. Each evolved clone is its own strain record | Yes, with Table S1 (mutations) |
| Lipid diets: lipidomics (Justice et al. 2024, *Nat. Commun.* 15:9679) | Zenodo 10.5281/zenodo.13817894 is the concept DOI; the record is 13817895 | One workbook, 38 KB, byte-identical to the article's Supplementary Data 3. CC BY. Raw files never deposited (the provider's restriction) | *M. mycoides* on three diets; **Syn3A-mCherry on diether PC + cholesterol only**; 37 °C; 3 biological replicates | Related strain (Syn3A-mCherry) | Yes |
| Lipid diets: TEM | BioStudies S-BSST1651 | One zip, 514 MB. CC0 | Syn3A-mCherry on FBS, POPC and diether PC diets | Related strain | Study metadata |
| Lipid diets: journal files | Source Data (5.9 MB), Supplementary Data 1–3, SI (26 MB) | Numeric values for Figs 2–6. CC BY | Growth as a phenol-red acidification rate; propidium iodide lysis after shock into water; fluorescein diacetate (FDA) uptake | Related strain. The FDA coefficient is inferred, from a slope and an assumed area per lipid | Yes |
| Replication (Thornburg et al. 2026, *Cell* 189:2582) | BioProject PRJNA1257452 | 9 MiSeq runs, 3.8 GB of reads | Syn3A-mCherry; SP4; 5, 9 and 21 h, 3 replicates each. The 5 h runs were released on 17 November 2025, after bioRxiv v1 | Related strain. The ori:ter ratio is inferred | Run metadata |
| Reconstituted membranes: archive (Presutti et al. 2026, *Nat. Commun.*) | Zenodo 10.5281/zenodo.20613506 (concept 20613505) | One zip, 590 MB, 2.5 GB unpacked. **Martini 3 MD only.** CC BY | Coarse-grained bilayers and vesicles, 0–80% cholesterol, 293 K and 310 K | Another simulator | Record, listing and 20 small members, by range requests |
| Reconstituted membranes: journal files | Source Data (343 KB), SI (22 MB) | Glycerol traces numeric. The KCl and ribose traces and the DLS size distributions are images only. **Article CC BY-NC-ND** | Synthetic vesicles of three five-lipid mixtures; 20 °C; stopped-flow calcein assay for water, glycerol and D-ribose; Langmuir monolayers; cryo-TEM | Reconstituted (traces). The coefficients are fitted | Yes |
| Reconstituted membranes, same assay (Frallicciardi et al. 2022, *Nat. Commun.* 13:1605) | The paper's source-data repository, 91 files, about 4.2 MB; MD on Zenodo 10.5281/zenodo.6010416 | Raw stopped-flow traces: time plus 6–9 acquisitions, 1,000–3,000 points over 20–60 s, for KCl (water), formate, lactate and, on DOPC, POPC and DPPC, glycerol. One exemplary DLS distribution per composition. Paper CC BY; **the repository has no licence file** | Calcein-loaded vesicles of DOPC, POPC, DPPC, a chain-length series and sterol series; 20 °C; about 300 mOsm/kg after mixing | Reconstituted (traces); fitted (coefficients) | 16 data files (1.1 MB) and the SI (1.5 MB, with the per-trace fits of Table 6); the MD archive not downloaded |
| The 4D model | Repository `Luthey-Schulten-Lab/Minimal_Cell_4DWCM`; Zenodo 15579158 is the concept DOI of record 15579159 | Zip of 12.0 GB: frozen code, inputs, 50 count-and-flux CSVs (302 MB), 4 trajectories (11.7 GB). Zenodo CC BY; **no licence file in the repository** | — | Another simulator | Metadata and listing; nothing cloned or run |
| Genome | GenBank CP016816.2, updated 12 April 2018 | Feature table | — | Measured (annotation) | Yes |

### 1.1 The missing division data: every place checked

**The search.** It used public sources only, with no contact with authors (D173), on 14–15
November 2026. The paper's DOI for its source data, analysis code and extra videos (Figs 1D, 4D,
5E) is 10.17632/rwg6sdz4rf.1.

| Where | What was tried | Result |
| --- | --- | --- |
| doi.org | The DOI with .1, .2 and .3, unversioned, and in upper case; the handle API | "DOI Not Found"; handle responseCode 100 |
| DataCite | The DOI, versioned and not; the string "rwg6sdz4rf"; title and creator queries (minimal cell, syn3, Pelletier, Strychalski) | 404; 0 hits; 119 records, none the deposit |
| Mendeley Data | Public API (dataset, versions, files); OAI-PMH GetRecord | 404; "idDoesNotExist" |
| Internet Archive | The dataset page and the DOI | No capture |
| Zenodo, Figshare, Dryad | Three, two and two searches by title, terms and authors | None |
| Repository hosts, NIST's public data repository | Two searches each | None |
| The *Cell* article's supplement (Elsevier's CDN) | mmc1 to mmc12 | Table S1 (29.8 KB) and Videos S1–S4 (1.1–4.2 MB, mp4). No source data for the histograms |
| bioRxiv v1 supplement | The supplementary page | Six SI movies (AVI) only |
| MIT DSpace 1721.1/146068 | The record | The preprint PDF only (CC BY-NC-ND) |
| JCVI's publication page | The page | No data links |
| Works citing the paper (OpenAlex, 149) | Titles about minimal-cell division or shape | None reuses the measurements |

**Reading.** The DOI was most likely reserved and never published (**S**): there is no
registration anywhere and no archive capture.

**Not searched**, so the user's side need not assume it was covered:
- Mendeley Data's own site search (a script-driven page, not attempted);
- the NIST and MIT lab web pages;
- the authors' personal accounts on code hosts;
- general dataset search engines.

**Related public data found on the way:**
- **Moger-Reischer et al. 2023, "Evolution of a minimal cell."** *Nature* 620:122, PMC10396959,
  CC BY; data on figshare 10.6084/m9.figshare.23119985, CC BY.
  - It evolved JCVI-syn3B and the non-minimal JCVI-syn1.0 for 2,000 generations.
  - The non-minimal cell's size rose 80% while the minimal cell's did not, which the authors
    trace to epistatic *ftsZ* mutations.
  - The deposit holds cell size (699 MB), FtsZ (390 MB), growth curves (8 MB) and fitness
    (176 MB).
  - Recorded in the inventory as related-strain evidence for Stage 5, metadata only
    (`/mnt/datasets/Cells/syn3a/figshare-23119985/`). The data files are not downloaded.
- **The Syn3B FtsZ:mCherry plasmid record,** Mendeley 10.17632/x59cx6ns2h. This is the 4D
  paper's imaging strain; the record holds no images.
- **The 2022 model's ori/quarter/terminus qPCR,** Mendeley 10.17632/nprw2h5tx6.
- **A defined-lipid-diet preprint** (bioRxiv 10.1101/2024.10.04.616688), a Stage 3 lead, not
  audited.

## 2. The brief's claims, checked

| Claim | Verdict | Primary evidence |
| --- | --- | --- |
| Syn3A has 452 protein-coding genes, 493 genes and 543 kbp | **Confirmed, with the lists reconciled** | Breuer et al. 2019's gene table: 452 coding sequences + 38 RNA genes + 3 pseudogenes = 493, with three engineered features (*HIS3*, *tetM*, *MET14*) listed apart. GenBank CP016816.2: 543,379 bp; 455 intact coding sequences (those 452 plus the markers). A model must say whether the expressed markers are in scope |
| syn3.0 has 438 protein-coding genes | Confirmed | Breuer et al. 2019, citing Hutchison et al. 2016 |
| 428 of 452 proteins detected by proteomics | **Confirmed independently** | Table 1; supplementary file 5 has 428 distinct accessions (counted here). Absolute counts are scaled, not measured |
| The 2024 paper measured growth, membrane composition, permeability and osmotic sensitivity in living Syn3A | **Corrected** | §4.2: a labelled strain; growth is a metabolic index; composition deposited for one Syn3A diet; permeability and lysis only across chirality diets |
| Raw lipidomics were withheld for proprietary reasons | Confirmed | The paper's data statement |
| The 2026 paper measured water and osmolyte permeability of reconstituted Syn3A-like membranes | **Confirmed, with corrections** | Three synthetic mixtures at 20 °C. The Zenodo archive is MD only; the article is CC BY-NC-ND |
| The 4D model used about 15,000 A100 GPU-hours | **Confirmed against bioRxiv v1 only** | v1 Fig. 1 and p. 10, the only preprint version. The *Cell* version is unreadable here |
| The 4D model has no kinetic FtsZ division model | **Confirmed against bioRxiv v1 only** | v1 pp. 6, 56–58 |
| Pelletier data, code and videos are on Mendeley | **Corrected: not found anywhere public** | §1.1 |
| Seven genes, including *ftsZ* and *sepF*, restore a parental-like phenotype | Confirmed | The paper's abstract and summary |
| *M. pneumoniae* has 1,748 consistently generated multi-omics data sets | **Confirmed, with a correction** | Chen et al. 2016 (*NAR* 44:1192), Table S1: 1,300 are growth curves at various nutrient concentrations, and about 450 are omics data sets. The integrated database, MyMpn, is offline (§9) |
| A 2026 *Cell* paper reports 140 in-cell maps; EMD-53631 is one | Confirmed | Dobbs, Jensen and Mahamid 2026 (PMID 42790420). EMD-53631: strain M129-B7, 254 tomograms, released 23 September 2026 |

## 3. What was downloaded, and what waits

- **Syn3A:** 82 MB in 19 source folders: the earlier 17, the Frallicciardi subset with its CC BY
  SI, and the Moger-Reischer metadata.
- ***M. pneumoniae*:** 4.4 MB in 3 folders (§9).
- **How the files were handled.**
  - Every file was only streamed to disk and hashed. Nothing downloaded was executed.
  - Workbooks were read with standard-library readers, `.xlsx` as XML and `.xls` (BIFF8) by
    `scripts/xls_dump.py`.
- **The Frallicciardi traces' reuse terms.**
  - The paper's data statement names its source-data repository for the experimental
    measurements and states no separate reuse terms.
  - The article and its SI are CC BY 4.0, but the repository has no licence file.
  - So the milestone fetches them by manifest and checksum at run time, and no trace or plot
    of one enters the public repository.
- **The non-commercial sources,** under the user's decision of 15 November (D173):
  - The sources: Presutti, Sandberg, and the *M. pneumoniae* papers (Maier, Wodke, Chen, and
    MyMpn).
  - They serve analysis only. Nothing from them is committed or redistributed: no table,
    trace or plot.
  - Judged or published results rest on permissively licensed data where possible.
- **Awaiting approval:** the 4D model's outputs, at the metabolism stage (D138, D173). No source
  exceeds 20 GB.
- **Not downloaded, under the brief's rules:** raw spectra, raw tomograms, raw reads.
- **Not downloaded, optional:**
  - the TEM zip (0.51 GB);
  - the two MD archives;
  - the Moger-Reischer data (1.3 GB);
  - the Frallicciardi weak-acid traces, which are kept for FR-4's case (§6.4).

### 3.1 Licences: what each milestone and stage rests on (D173)

**Three classes.**
- **Permissive** (CC BY, CC0): values, tables and derived plots may enter the repository, with
  attribution.
- **Non-commercial** (CC BY-NC, -NC-SA, -NC-ND): analysis only.
  - No table, trace or plot from these sources enters the repository. Individual values may be
    cited, as D173 agreed.
  - Judged or published results use a permissive source wherever one exists.
- **No stated terms** (a deposit with no licence file, although its article is open):
  - fetched by manifest and checksum at run time;
  - no trace or plot enters the repository, though summary statistics and verdicts may.

| Where | Source | Class | Use under D173 | Permissive alternative | What the alternative does not cover |
| --- | --- | --- | --- | --- | --- |
| S2-M1, judged content (§6.1) | None. Its scale values are round numbers or come from CC BY sources | — | Judged | Not needed | — |
| The probes' scale values (§5) | Presutti 2026: Pf of Mixtures 1 and 3, Mixture 1's glycerol permeability, and the DLS radius range | Non-commercial | Cited single values in development probes, which D173 allows. Nothing judged rests on them | The CC BY Frallicciardi SI's water and glycerol coefficients for DOPC, POPC and DPPC | Syn3A-lipid mixtures |
| S2-M1, calibration and glycerol arm (§6.1); the weak-acid case (§6.4) | Frallicciardi 2022's raw traces and DLS files (its GitHub repository) | No stated terms. The article and SI are CC BY | Reported as summary statistics and verdicts only. If the glycerol arm became judged, it would rest on these files, which are not permissive | The CC BY SI's coefficients (Supplementary Tables 1–5) and exemplary fit parameters (Table 6), and the traces as drawn in the CC BY figures | The raw acquisitions. The CC BY code record (Zenodo 5176264) holds seven MATLAB scripts and no data |
| S2-M1, Syn3A-lipid arm (§6.1) | Presutti 2026's Source Data | Non-commercial (CC BY-NC-ND) | **Analysis only, in the workspace,** outside the published record | None measured | The same work's MD archive is CC BY but is another simulator's evidence. Frallicciardi's POPC–cholesterol water series has no stated terms |
| §4.1's coefficient ranges | Presutti 2026, Fig. 3b | Non-commercial | Cited as orders of magnitude; the table is not copied | None | — |
| Stage 4 (Syn3A), the evolution study (§4.3) | Sandberg 2023: the article's tables (Table S1, mutations); processed expression tables on GEO | Non-commercial (CC BY-NC-ND) for the article; GEO's terms not checked | Analysis only | Moger-Reischer 2023 (CC BY; figshare CC BY), held as metadata | Syn3B, a related strain: growth, fitness, cell size and FtsZ, but no expression data |
| Stage 4a (*M. pneumoniae*): the rebuffering perturbation and the pH challenge (§9.3) | Wodke 2013, Fig. 4A–C source data | Non-commercial (CC BY-NC-SA 3.0) | Analysis only. A judged Stage 4a on this perturbation needs the user's decision | **None found** in five topic queries of Europe PMC (15 November), top hits screened by title | The nearest permissive observables are phenol-red growth-index curves for strain M129 (Gaspari et al. 2020; Burgos et al. 2023; figures only). They depend on growth, so they need a growth model, and they have no rebuffering step |
| Stage 4a's medium (§9.3) | Yus 2009's defined medium | Not obtained | — | Leads for a serum-free recipe only. Burgos et al. 2023 (CC BY) tabulates complete serum-free formulations for M129, semi-defined (CMRL-1066 and yeastolate). Gaspari et al. 2020 (CC BY) gives the semi-defined MCMyco | Fig. 4's experiments used rich medium with horse serum (Hayflick, by name for Fig. 4A–B) |
| Protein abundance (§9.2) | Maier 2011: 413 proteins | Non-commercial (CC BY-NC-SA 3.0) | Analysis only | **Weber et al. 2023** (*Mol. Syst. Biol.* 19:e11301, CC BY 4.0): copies per cell of 528 proteins at 48 h. 73 reference proteins are anchored by labelled peptides, and the rest are calibrated to them (PRIDE PXD035159) | Maier's perturbation proteomes and time course |
| Protein turnover, the closed-loop test (§9.3) | Maier 2011: 231 proteins | Non-commercial | Analysis only | **Burgos et al. 2020** (*Mol. Syst. Biol.* 16:e9530, CC BY 4.0): SILAC pulse-chase fits for 488 proteins in exponential phase, in Hayflick (PRIDE PXD016386). Many fitted rates sit at the dilution rate, so those half-lives are long and poorly resolved | As above |
| The osmotic response (§9.1) | Maier 2011, the 0.5 M NaCl proteome | Non-commercial | Analysis only | None found | — |
| The 1,748 data sets (§2, §9.1) | Chen 2016's workbook; MyMpn | Non-commercial (CC BY-NC 4.0) | Cited for the count only; no milestone rests on them | The underlying deposits (ArrayExpress, PRIDE), under each archive's terms (not checked) | — |

**About the alternatives.**
- Each article's licence was read from its full text (CC BY 4.0). The deposits' own licences
  were not checked, and none of their data files was opened.
- The counts stay separate: Weber's 528 proteins with copies and Burgos's 488 turnover fits,
  apart from Maier's 413 and 231.
- One on-topic preprint is not permissive: the 2022 study of *M. pneumoniae*'s central carbon
  metabolism (bioRxiv 10.1101/2022.08.08.503180, CC BY-NC). No published version was found
  under its title.

**Permissive throughout:**
- Stage 3: Justice et al. 2024 (article, Source Data and lipidomics CC BY; TEM CC0);
- Breuer et al. 2019 (CC BY; proteomics CC0);
- the 3C map (CC0);
- Moger-Reischer 2023 (CC BY);
- the 4D model's Zenodo record (CC BY, although its code repository has no licence file).

**Not classified, because their licences were not read:**
- the *Cell* articles behind Stage 4's 2022 kinetic model and Stage 5's Syn3B counts (Thornburg
  et al. 2022 and 2026);
- Pelletier 2021 and Dobbs 2026;
- the EMPIAR, SRA and GEO deposits' own terms.

**Evidence records.** Records that enter the repository with a milestone (§7) carry no value
from a non-commercial source or a source with no stated terms. They name the source file by
manifest entry and checksum, and the value is read at run time.

## 4. Stage by stage

### 4.1 Stage 2: reconstituted-membrane transport

**What the data measure.**
- Calcein-loaded vesicles, extruded at 200 nm, are mixed 1:1 with an osmolyte at 20 °C, to about
  300 mOsm/kg.
- Water leaves first and the vesicles shrink, which self-quenches calcein. A permeant osmolyte
  then enters and restores the volume.
- **The observation model** (Gabba and Poolman 2020, CC BY; Frallicciardi et al. 2022):
  - per vesicle, F/F0 = (1 + K_SV·c0)/(1 + K_SV·c(t)), with c the lumen's calcein
    concentration;
  - averaged over the DLS size distribution;
  - at constant area.

  The authors fit K_SV and P_w on the KCl trace. Then either P_o with P_w fixed (Presutti), or
  all three (Frallicciardi), on each permeant trace.
- **The values.** Syn3A-lipid coefficients span water 10⁻³ to 10⁻² cm/s, glycerol 10⁻⁷ to 10⁻⁶
  and ribose 10⁻⁹ to 10⁻⁸, each falling as cholesterol rises. Exact values are in Presutti's
  Fig. 3b and the workspace inventory. That article is non-commercial (CC BY-NC-ND; §3.1), so
  only orders of magnitude are cited here.
- **What is not public:**
  - a second osmotic gradient on the same membrane;
  - a size series;
  - the ten DLS acquisitions per condition that the fits used.

**What Cells already has** (the probes, §5).
- **The composite** over the inner model, with held baths. A cell with no channels and no pumps
  is admitted.
- **Water,** `ideal_osmosis_linear_compliance_water@1`, which counts every declared species row
  in the osmotic pressure.
- **A neutral row on the inner model's constant-field route.** At valence 0, the
  Goldman–Hodgkin–Katz flux reduces to J = P·A·(c_o − c_i), and the route books heat. Under
  water it gives the shrinkage and the start of recovery seen in the probes' 2 s runs. It fails
  from a trace start.
- **Batched worlds,** for size distributions. The observation model is driver code (validation),
  not engine physics.

**D150's exchange is not the permeation law** (D174).
- It moves a species by one-way routes and books signed supplied work with no heat.
- Paired first-order routes match Fick's law only with constants tied to the declared volume.
- It refuses held baths and water.

**What is missing, as general features.**
- **F1, the generic passive law (D172's round, as D174 expects).** Its kernel exists, in the
  constant-field flux at valence 0. The declared law must add:
  - exact free-energy booking as heat (§5.3);
  - finding 3's valence-0 bound term (already in the round's I0);
  - a trace and background policy at the definition boundary;
  - qualification with water: the architecture's "neutral solute and water in a vesicle" reuse
    case.
- **F4, door W, an anisosmotic bath step.** It is not needed while worlds start from the stepped
  state.

**Organism-specific data and parameters:**
- the lipid compositions;
- buffers and their measured osmolalities;
- traces and DLS distributions;
- 20 °C.

### 4.2 Stage 3: living-cell responses on lipid diets

**What the data measure** (Justice et al. 2024; all at 37 °C in modified SP4 with phenol red;
lipids on delipidated BSA):

| Readout | Diets with Syn3A-mCherry data | How it is measured |
| --- | --- | --- |
| Growth | POPC, diether PC (Fig. 4a); POPC, enantiomeric POPC, racemic (Fig. 5c) | Rate of phenol-red acidification, by a logistic fit. A metabolic index, not a cell count |
| Lipidome | Diether PC + cholesterol only (over 99 mol% two lipids) | Lipotype shotgun MS, 3 biological replicates |
| Morphology | FBS, POPC, diether PC | TEM: internal vesicles rise from about 15% to nearly 40% |
| Lysis after hypo-osmotic shock | Chirality diets only: lysed fraction about 0.60, 0.76 and 0.90 | Propidium iodide after 30 min in water; 3 × 3 replicates |
| Permeability | Chirality diets only: about 3.1, 3.6 and 5.2 × 10⁻⁶ cm/s | FDA uptake, by Fick's law with an assumed area per lipid |

**The caution.** The chirality effects are attributed to lipid–protein interactions, because
bilayer order is unchanged (*M. mycoides* extracts). A bilayer model is therefore not expected to
explain them. Registering that expectation makes the series a falsification control (**S**).

**What Cells already has:**
- water and volume;
- membrane state and insertion;
- replacement@2;
- batched worlds;
- `resolved_repair@1`'s prescribed injury and resealing, in an older family.

**What is missing, as general features:**
- **F5, membrane failure under tension.** Tension from pressure and radius, a critical tension or
  strain, a pore that leaks and can reseal, and lysis as a cell-fate event (FR-5, D161).
- **F6, lipid composition as membrane-domain state,** with declared composition-to-permeability
  and composition-to-mechanics laws.
- **F7, permeant reacting species,** for FDA's intracellular hydrolysis.
- **Growth as a process.**

**Organism-specific:**
- the diets;
- the cell size distribution (semi-quantitative);
- the cytoplasmic osmolarity (unmeasured; a labelled prior);
- the strain (mCherry).

**A bioelectric prior from relatives.** For mycoplasma membranes, published measurements give
(abstracts read on PubMed):
- a proton-motive force of 70–130 mV and energy-dependent volume regulation in *M. gallisepticum*
  (Rottem, Linker and Wilson 1981, *J. Bacteriol.* 145:1299; PMID 7204343);
- about −80 mV by calibrated carbocyanine dyes, with K⁺ and Na⁺ diffusion potentials (Schummer
  and Schiefer 1983, *Yale J. Biol. Med.*; PMID 6089453).

A value of about −85 mV with an internal pH 0.5 above the medium is reported for *M. mycoides
capri*, Syn3A's parent. This came from a search summary only; the primary paper was not found
or verified.

### 4.3 Stage 4: metabolism, protein inventory and growth

**Data:**
- **Breuer et al. 2019:**
  - 428 quantified proteins;
  - transposon essentiality;
  - a reconstruction of 338 reactions and 304 metabolites;
  - a 105 min doubling time in SP4.
- the evolution study (Sandberg 2023: non-commercial, analysis only; §3.1);
- the replication sequencing;
- prior models, which count as another simulator's evidence: the 2022 kinetic model and the 4D
  model.

**The hard limit.** SP4 is undefined, so uptake fluxes cannot be closed from the medium.

**The scale, against today's engine (S).**

| Quantity | Stage 4 needs | The engine today |
| --- | --- | --- |
| Species | The 2022 kinetic model: about 148 metabolites, 452 proteins and 452 mRNAs, 29 tRNAs and their charged forms; over 7,000 reactions (Thornburg et al. 2022). The FBA reconstruction alone: 304 metabolites, 338 reactions | D152's operator: at most 16 species per world (FR-9; above 16 needs another probe). Stage 4 is 10–100× beyond it |
| Copy numbers | One molecule in a 200 nm cell is about 50 nM. Protein copies (Breuer, log phase, scaled): median about 120 per cell, 10% below 10, 46% below 100, 99% below 1,000, about 77,000 in all. mRNAs: about one per gene (the 4D model's ~400 per cell). Metabolites: about 200 copies at 10 µM, 20,000 at 1 mM | Deterministic amounts only |

**What it means.**
- Millimolar metabolism is deterministic territory.
- Gene expression, a tenth of the proteins and micromolar cofactors are not.
- So Stage 4 needs both:
  - **F8, metabolism at scale:** a sparse, stiff network operator well past 16 species, with one
    owner of each standard potential, composed with water and partition;
  - **F11, a stochastic regime:** the earlier review's rank 1 candidate. Exact stochastic
    reactions per node with keyed random streams, then a hybrid split by copy number, as the 4D
    model splits RDME, CME and ODE.

**Also missing:**
- **F9, fuel that reactions make and spend** (§11).
- **F10, polymerisation laws** for transcription and translation, held under D145.

### 4.4 Stage 5: division and genetic perturbations

**Data:**
- Pelletier et al. 2021, not found (§1.1);
- the 4D paper's counts on 1,319 fixed **Syn3B** cells;
- the Moger-Reischer Syn3B cell-size and FtsZ data (related strain);
- two cryo-ET cells.

**What Cells already has:** prescribed division (S2–S5) and the assembly layer.

**What is missing:**
- **F12,** single-cell membrane shape mechanics;
- **F13,** a constriction machinery law (FtsZ-type ring assembly, anchoring, force);
- **F14,** state-triggered division and stochastic partition of integer populations;
- chromosome segregation, which is out of scope.

## 5. The probes (capability only)

All the probes:
- ran from a frozen, clean snapshot of main (c04dc4f5), on CPU 0, through
  `scripts/run_detached.sh`;
- wrote their criteria before running, in `p0/P0*_CRITERION.md`;
- recorded their results in `p0/P0_SUMMARY.json`.

**Engine models run:** `resolved_pump_composite@1` over `resolved_pump_tissue@3` with
`ideal_osmosis_linear_compliance_water@1`, built by the engine's own `frozen_definition`.

### 5.1 P0: an impermeant osmometer vesicle

The world:
- **the vesicle:** radius 100 or 300 nm, 293.15 K, no ion permeability;
- **the solutions:** lumen 190 mosmol/L; bath 290, the stepped state after mixing to 50 mM KCl;
- **the water law:** K = P0 = 0, with Pf of the 60% and 20% cholesterol mixtures for scale.

| Check | Result |
| --- | --- |
| C1, admission | **Pass.** No pump and no channels (A1) is admitted and runs. So do a zero-capacity pump and a closed pump |
| C2, scope | water@1's qualified scope is held-bath worlds, which this is. But its qualification worlds were 0.75 pL cells with K 60 Pa and P0 40 Pa at 310 K. A 100 nm vesicle is about 1.8 × 10⁵ times smaller, with K = P0 = 0 at 293 K. So this is **development evidence**, outside the qualified scale |
| C3, stepped start | **Pass.** It is admitted without any bath schedule |
| C5, relaxation against the closed form and an independent Radau solution | **Pass.** The maximum relative volume error at dt 1, 0.5 and 0.25 ms: 2.1e-7, 5.2e-8, 1.3e-8 (100 nm); 2.3e-8 to 1.4e-9 (300 nm); 4.4e-6 to 2.7e-7 (100 nm, 20% cholesterol). The observed order is 2.00 throughout |
| C6, ledgers | **Pass.** No refusal; material balance errors 0; water ledgers at most 2e-22 pL; energy residual at most 7.7e-8 relative |
| C4, scale of floors and bounds | **Marginal** (floor between 1e-6 and 1e-3 of the guarded quantity): `material_balance_atol_fmol` (declared 1e-10 fmol) against the smallest lumen amount (4.2e-6 fmol); `VOLUME_ATOL_PL` against the volume moved (1.4e-6); `ENERGY_ATOL_PJ` against the free energy dissipated (5.7e-5). Every other floor is at or below 3e-9. For neutral trace rows the material floor must be species-scaled, as D150 does. **The water step bound:** the refusal predicted for the 20% mixture at 1 ms did not happen. The bound is evaluated at the declared and stage states, and the relaxation never reaches the 0.5 V0 bound the estimate assumed (**S**: about 35/s at equilibrium, so 0.035 at 1 ms). A 60 nm vesicle of that mixture would need 0.5 ms (**S**) |

### 5.2 P0b–P0d: a permeant neutral row (glycerol)

The world is the same vesicle with a valence-0 row G:
- membrane permeability 4.1e-9 m/s;
- bath 120 mM, the stepped state;
- lumen at various starts.

| Variant | Result |
| --- | --- |
| Lumen at a trace (1e-6 mM, a 1.2 × 10⁸-fold step), dt 0.5 or 0.05 ms, water on or off | **Refused** by the inner model's energy ledger ("Resolved pump accounting failed: energy"). With water closed too, so the route's own booking fails |
| Lumen 120 mM, no gradient | Runs; nothing moves |
| 10-fold step | Runs. The vesicle shrinks to 0.675 V0 and has begun to recover by the end of the run (0.717 V0 at 2 s). Volume within **6.1e-8** of an independent two-variable reference |
| 100-fold and 10⁴-fold steps | Run. Energy residual 6.9e-8 and 3.3e-4 relative, the latter 16% of the 2e-3 tolerance |
| Reversed gradient (lumen 120, bath 12 mM) | Runs. The G amount falls (efflux); in the forward case it rises |
| Heat | The membrane heat is positive and monotone in every run |

### 5.3 The passive contract, in ARCHITECTURE.md's corrected wording

**The acceptance** (ARCHITECTURE.md, the modular core, as corrected on main at 08ac2eb).
- **The test:** a closed, fixed-volume, two-compartment world. The law must:
  - conserve material;
  - give zero net flux at equal chemical potential;
  - reverse with the driving force;
  - dissipate the free-energy decrease with no externally supplied work.
- **In a held-bath world,** the total balance includes the declared reservoir work.
- **Composition with water** is qualified separately.

**What each run can show.**

| Item | Exchange (paired one-way routes; judged from its contract and documented booking, not run) | Constant-field route at valence 0: the vesicle runs (P0b–P0d; a held bath, mostly with water) | Constant-field route at valence 0: the closed pair (P0e T1; no reservoir, no water) |
| --- | --- | --- | --- |
| Conserved material | Yes | Yes, counting the reservoir's supply | **Yes:** the pair's total G to 1.5e-16 |
| Zero net flux at equal chemical potential | Only with rate constants tied to the declared volume | Yes | **Yes:** exactly zero |
| Reversal with the driving force | Yes | Yes | **Yes:** equal and opposite to rounding |
| Free-energy decrease dissipated, no external work | **No:** books signed supplied work and no heat | Not testable as such: the bath supplies G and books reservoir work. The total balance including that work closes within the ledger tolerance from resolved starts (residual 1.6e-8 at a 10-fold start, 3.3e-4 at 10⁴-fold) | **Yes:** the booked heat equals the exact ideal-solution decrease to 1.1e-6 relative; reservoir and electrode work are zero |
| Time course | — | Within 6.1e-8 of an independent two-variable reference (with water) | **Within 7.7e-8** of the closed form |
| A start from a trace | — | Refused by the energy ledger, with water on or off | **Refused**, the same way |
| Composition with water | Refused | Runs: development evidence for the separate water qualification | Not part of this test |

**Conclusions.**
- **The held-bath vesicle runs are not the acceptance test.** They are open systems, mostly with
  water on. They show the coupled behaviour and a total balance that closes with the reservoir's
  work.
- **The closed pair passes every item from resolved starts.** It is the acceptance test's own
  shape, run on main's inner model with no new code.
- **What is missing is one thing:** a trace start. A generic passive law in D172's round can
  declare the constant-field kernel at valence 0 under its own ID and contract. It must:
  - book each step's exact free-energy change as heat, as D150's exchange stages book theirs as
    work, so that trace starts are admitted;
  - carry finding 3's bound term;
  - declare its trace policy at the definition boundary.
- **No separate operator is needed for this case, and no D150 version 1.1:** water already counts
  inner-model species rows. D150 version 1.1 is still needed wherever D150's own operators meet
  water.

### 5.4 A closed pair exists on main today (P0e)

ARCHITECTURE.md asks first which admissible topology is closed for the test species, because
FR-1's compartments sit in worlds with a held bath. The criterion was written before the run
(`p0/P0E_CRITERION.md`).

- **T1, one cell and one finite outside node, no reservoir:**
  - **The parser.** It requires exactly one outside gauge when no reservoir is held, and admits
    this pair.
  - **The engine model run:** `resolved_pump_tissue@3` alone, with no water, so at fixed volume.
  - **The variants:**
    - equal concentrations: nothing moves;
    - 1 against 10 mM, and the reverse: equal and opposite transfers;
    - the time course within 7.7e-8 of the closed form;
    - dissipation equal to the exact free-energy decrease to 1.1e-6;
    - no work booked.
  - **A trace start** is refused like the vesicle's.
  - **So the closed passive test need not wait for FR-1.**
- **T2, two cells joined by a pinned-open junction, each facing a held bath through a membrane
  impermeant to G:** the junction route carries the same constant-field law.
  - **Admitted, and closed for G despite the held bath.** No G reached the bath, and no reservoir
    or electrode work was booked.
  - **Results identical to T1's** (same law, area, permeability, volumes and step):
    - equal concentrations: nothing moves;
    - forward and reversed transfers equal and opposite;
    - material to 1.5e-16;
    - the time course within 7.7e-8;
    - dissipation equal to the free-energy decrease to 1.1e-6.
  - **A trace start is refused.**
  - **Earlier attempts.** Two were refused at the parser by declaration errors in the probe itself:
    a missing nested `gate`, then a missing junction `law`. Both are recorded in the criterion's
    addenda (`p0/run-07-p0e-t2` is the valid run).
- **So the closed test has two topologies on main.** One has no bath at all; the other sits in a
  held-bath world, as FR-1's compartments will.

## 6. The first milestone: S2-M1, neutral solute and water across protein-free vesicles

### 6.1 Claims, kept apart (D174), with the judged content numerical

| Kind | What | Data | Judged? |
| --- | --- | --- | --- |
| Numerical verification: the passive contract | The closed, fixed-volume, two-compartment test of §5.3 at vesicle scale, against references written by a separate agent: conservation, zero flux at equal potential, reversal, dissipation equal to the free-energy decrease with no external work, and the time course. A trace start included. The topology exists on main (§5.4) | None, so no licence dependence. Its worlds take round or CC BY-sourced scale values, not the probes' Presutti values (§3.1) | **Yes: the milestone's judged content** |
| Numerical verification: water coupling | Then the same law composed with water@1 in a vesicle: shrinkage and swelling against an independent two-variable reference, with dt refinement and the held-bath total balance with its reservoir work | None; scale values as above | **Yes** |
| Calibration | Per membrane (POPC, DOPC, DPPC): P_w and the quenching parameter on the KCl traces with the exemplary DLS distribution; P_gly on a late window of the glycerol trace (t > 20 water time constants). The published coefficients reproduced | Frallicciardi 2022; raw traces with no stated terms (§3.1) | No: reported as calibration, in summary statistics |
| The glycerol arm | On the same membranes: each glycerol trace's fluorescence minimum (time and depth), with nothing refit. A permeant osmolyte at **about the same gradient** as KCl | Frallicciardi 2022; no stated terms (§3.1) | **Reported only,** in summary statistics. It becomes judged only if a check registered beforehand catches a planted error with margin, as MG0c's controls do. Reasons below |
| Syn3A-lipid vesicles | The three Syn3A-lipid mixtures' glycerol traces, with the published P_w as input. K_SV and the size prior would have to come from another membrane | Presutti 2026: **non-commercial** (§3.1) | **Analysis only, in the workspace** (D173), since no permissive measured alternative exists. Mixture-to-mixture interpolation passes by hand |
| Held-out living-cell prediction | None. The public data allow none at this stage. Stage 3's lysis needs F5 | — | — |

**Why the glycerol arm is reported only.**
- **Within-trace fitting:** P_gly comes from the same trace's late window, so the minimum is held
  out only from that window, not from the experiment.
- **The thin margin:** in the host-side check below, halving or doubling P_gly moves the predicted
  minimum by only 1.5–2.5 acquisition s.d., and the unperturbed prediction itself sits within
  1.4 s.d.
- **The authors' own refits:** K_SV varies 1.2- to 10-fold between traces of one membrane, and
  P_w differs between traces of one membrane. So the observation model is part of what the arm
  tests.

**The check that this arm can fail.** It was run host-side, not in the engine (`heldout/`).
- **The model:** a crude ensemble model fitted to the public traces, weighted by the DLS
  intensity distribution as an assumption.
- **POPC:** the glycerol minimum is 0.142 ± 0.011 deep at 0.36 ± 0.04 s (9 acquisitions). The
  KCl trace instead reaches 0.197 on a plateau after 2–3 s. So the permeant trace is not a
  replicate of the impermeant one.
- **The prediction:** with P_w and the quenching parameter from KCl, and P_gly from the late
  window only, the predicted minimum is 0.150 at 0.41 s for POPC. For DOPC it is 0.140 at
  0.28 s, against 0.121 ± 0.026 at 0.29 ± 0.03 s. Both are within 1.4 s.d.
- **The sensitivity:** halving or doubling P_gly moves the predicted minimum by 1.5–2.5 s.d. An
  impermeant solute would sit near 0.19 at 3–4 s.
- **The correction this forces:** glycerol relaxes only about 10–20 times more slowly than water
  in these fluid membranes (fitted P_gly about 3e-6 and 8e-6 cm/s), not the 30–40 times
  estimated for the Syn3A-lipid mixtures.

**What the authors' fits show** (Frallicciardi SI Table 6, exemplary fits with one DLS
distribution, CC BY).
- K_SV is refit per trace, and it varies 1.2- to 10-fold between traces of one membrane: POPC
  about 3.0 × 10⁴ for KCl and 3.0 × 10⁵ for glycerol.
- The jointly fitted P_w from the glycerol trace differs from the KCl trace's by 1.6 times
  (POPC) and 3.3 times (DOPC).

**So the arm tests the observation model as much as the transport.**

**To make it judged, the protocol must register beforehand:**
- the handling of K_SV and the size weighting;
- planted errors (P_gly ×2 and ×½, a shifted P_w) with the margin by which each must be caught;
- a control that refits K_SV per trace, as the authors do.

Until then, a miss would not point at the engine.

### 6.2 Its structure

- **The representation, declared.**
  - Each vesicle is an individual compartment with continuum amounts.
  - The observable is a lumped-population average over a declared size distribution, run as
    batched worlds of about 20 radii.
- **The organism and evidence structure, instantiated with this milestone** (D174):
  - the "organism" is a synthetic vesicle system and the "strain" is its lipid composition;
  - conditions, traces, DLS distributions and coefficients become evidence records (§7);
  - the observation model is declared, with its calibrated nuisance parameters (K_SV, the size
    prior's parameters, the 2 ms dead time) as `calibrated` values.
- **The engine models it runs:**
  - `resolved_pump_composite@1` over the inner model;
  - `ideal_osmosis_linear_compliance_water@1`;
  - the generic passive law (F1), from D172's round.
- **Prerequisites:**
  - the round's passive law, with exact booking and finding 3's term. The resolved-start part of
    the contract runs on main today in the closed pair (§5.4), so references and protocol can be
    prepared now;
  - water@1 qualified at vesicle scale (P0 is the development evidence);
  - references written by a separate agent that has not read the engine code;
  - a PROPOSED protocol registered before one judged run.
- **Cost:** CPU minutes per world.
- **Data in hand, for the arms that are not judged:**
  - the 16-file Frallicciardi subset (1.1 MB). It has no stated terms, so it is fetched by
    manifest and checksum, and no trace or plot enters the public repository (§3, §3.1);
  - Presutti's Source Data, which is non-commercial: workspace analysis only.

### 6.3 Why this design

- **It judges what can be judged honestly.** The numerical contract and the water coupling have
  exact or independent references. The measured data offer only one same-membrane perturbation, a
  second permeant osmolyte at about the same gradient, with no second gradient, size series or
  repeat DLS distribution. That supports a reported arm, not a judged one, until a registered
  planted-error control shows margin.
- **Its trace-start items cannot be judged on today's engine.** A lumen without glycerol is a
  trace start, which the energy ledger refuses (§5.2, §5.4). They wait for the passive law's
  exact booking.
- **It reuses an architecture case.** The vesicle is one of the architecture's named reuse cases.
- **Everything it needs is general.** The passive law also serves drugs, metabolic wastes, gases
  and FR-1's compartments.

### 6.4 The natural next case: weak acids and pH

Frallicciardi's formate and lactate traces are on the same membranes. They need proton and buffer
chemistry inside the vesicle, so they are FR-4's compartment-pH case on measured data. This also
leads toward *M. pneumoniae*'s pH stage (§9). Those traces have no stated terms, so the same
rule applies: summary statistics and verdicts only (§3.1).

## 7. The evidence inventory schema

**One record per quantity.** The organism definition (§10) refers to records by ID.

| Field | Content |
| --- | --- |
| `record_id`, `source` | DOI or accession, file, sheet or figure, and the source file's SHA-256 |
| `organism`, `strain` | Taxon; strain with lineage and genome accession; for reconstituted systems, the composition |
| `target_relation` | Exact, labelled derivative, parent, other species, reconstituted system, or simulator |
| `condition` | Medium variant, temperature, growth phase or time, intervention |
| `assay` | Method, instrument and the observation model needed to compare (Stern–Volmer for calcein; Fick's law with an assumed area for FDA) |
| `quantity` | Name, value, unit, uncertainty and its kind, n |
| `replicate` | Biological, technical and independent-experiment counts and IDs |
| `evidence_category` | One of the brief's five, relative to the declared target |
| `derivation` | Measured; computed with listed assumptions; or fitted, with model and data |
| `claim_kind` | Numerical verification, calibration, protein-free test, or held-out living-cell prediction (D174) |
| `representation` | Continuum, lumped-population or individual-compartment (D174) |
| `use` | `set`, `judge` or `context`, per milestone; never both in one milestone |
| `sampling` | Time-uniform, balanced growth or fixed phase |
| `catalogue_ref`, `licence` | Functional unit or gene product; the licence of the value's source |

**The licence rule (D173).** A record from a non-commercial source, or a source with no stated
terms, enters the repository without its value. It holds the source file's manifest entry and
checksum, and the value is read at run time from the workspace (§3.1).

**How it fits the catalogue plan and the inner-model declarations.**
- It carries the catalogue plan's abundance provenance and kind of evidence.
- The categories map onto the inner model's provenance:
  - measured → `cited`;
  - inferred or fitted → `calibrated`;
  - a simulator's output is never a parameter source.

## 8. The external whole-cell model

- **Reference only.**
  - It is never imported, copied or run here.
  - The repository has no licence file, while Zenodo says CC BY 4.0.
  - Its dependencies odeCELL and LAMMPS are copyleft.
- **At Stage 4 (D138, D173), for the user's approval:** compare against its 50 saved
  count-and-flux traces.
  - Only that 288 MB member need be fetched, by range requests.
  - It is labelled "another simulator", never validation.

## 9. *Mycoplasma pneumoniae*: the audit, and what each organism offers

### 9.1 Audited sources

| Source | Identifier, licence | Strain, conditions | What was measured | What is inferred or simulated | Downloaded |
| --- | --- | --- | --- | --- | --- |
| Maier et al. 2011, *Mol. Syst. Biol.* 7:511 | 10.1038/msb.2011.38, PMC3159969; CC BY-NC-SA 3.0: **non-commercial, analysis only (D173).** MS raw data were placed on Tranche (ProteomeCommons); not checked | Strain not named in the methods; Hayflick medium as in Yus et al. 2009, attached growth; 24 h sampling over 4 days; perturbations at 96 h: **0.5 M NaCl osmotic stress**, mitomycin C, heat shock at 42 °C; a minimal-medium arm. Controls 9 replicates, perturbations duplicates | Average copies per cell of 413 proteins (anchored by labelled reference peptides; about 1.5–1.8-fold error); **turnover of 231 proteins** (SILAC chase, 1–8 days); mRNA copies per cell (tiling arrays with spike-ins; GEO); the proteome's response to each perturbation | Stochastic expression simulations | Tables S1–S8 (zip, 310 KB), SI text, model file: `maier2011-msb` |
| Wodke et al. 2013, *Mol. Syst. Biol.* 9:653 | 10.1038/msb.2013.6, PMC3658275; CC BY-NC-SA 3.0: **non-commercial, analysis only (D173)**; model iJW145 (BioModels MODEL1301290000) | Rich (Hayflick) and defined media, glucose (strain and temperature not checked) | **Batch time courses:** glucose consumed, lactate and acetate secreted, protein, medium pH 7.8 → 5.5 over 4 days. **The pH challenge:** after 48 h in Hayflick with glucose, 36 h at a pre-set pH (5.5–8.0 in the text; the file also has a pH 5.0 column): glucose used and protein made (Fig. 4A–B). **Rebuffering:** a batch culture brought back from about pH 6 to 7.7 with NaOH after 4 days, with glucose and lactate followed (Fig. 4C). ¹³C-glucose labelling | ATP production (about 60,000 per cell per second at 36 h), the ATPase's share (up to 57%), maintenance: FBA with fitted constraints, never to be used as measurements | Fig. 4 and SI Fig. 2–3 source data, Tables S1–S17, SI: `wodke2013-msb` (2.0 MB). **Opened (§9.3):** Fig. 4A–B and Fig. 4C are numeric. The batch time courses (SI Fig. S5) are a figure only |
| Chen et al. 2016, *NAR* 44:1192 | 10.1093/nar/gkw004, PMC4756857; CC BY-NC 4.0: **non-commercial, analysis only (D173)** | Consistent conditions from one group | The 1,748 data sets: **1,300 growth curves** at various nutrient concentrations (Yus et al. 2009), about 300 transcriptome data sets along growth and under stress, 57 proteome data sets along growth, interactions, modifications, turnover, metabolome (86 of 152 predicted metabolites), essentiality | — | The data workbook (Tables S1–S15) and index: `chen2016-nar` (1.9 MB) |
| MyMpn (Wodke et al. 2015, *NAR* database issue) | 10.1093/nar/gku1105, PMC4383923; CC BY-NC 4.0: non-commercial | — | The integrated database: **offline** (HTTP 404 at both addresses, 15 November 2026). Each data set must be fetched from its original deposit | — | — |
| Dobbs, Jensen and Mahamid 2026, *Cell* | 10.1016/j.cell.2026.08.054, PMID 42790420; not in PMC | Strain M129-B7; native and antibiotic-perturbed cells | 140 subtomogram-average maps of translation states; EMD-53631 verified | — | Metadata only |
| Membrane, ion and osmotic data | — | — | **None found for *M. pneumoniae*** beyond the 0.5 M NaCl proteome response and the medium-pH challenge. Relatives only: §4.2's bioelectric prior | — | — |

### 9.2 Side by side

| What a Cells model could be judged on | JCVI-syn3A | *M. pneumoniae* |
| --- | --- | --- |
| Protein abundance | 428 proteins, one medium, 3 phases; absolute counts scaled | 413 proteins with absolute copies anchored by reference peptides, under growth and four perturbations (Maier; non-commercial). Permissive: 528 proteins at 48 h, 73 anchored and the rest calibrated (Weber et al. 2023, CC BY) |
| Protein turnover | None | **231 half-lives** (Maier; non-commercial). Permissive: 488 SILAC pulse-chase fits (Burgos et al. 2020, CC BY) |
| mRNA | Relative expression of the ancestor and evolved clones | **Absolute copies per cell**, time courses and about 300 stress data sets |
| Energy, transport, pH | None measured; undefined medium | **Numeric:** glucose and protein against pre-set medium pH, and lactate and glucose over a 158 h batch with a rebuffered arm. Acetate, pH and protein time courses are figures only; the defined medium's recipe was not obtained. All from Wodke (non-commercial), with no permissive equivalent found |
| Membrane permeability, osmotic response | **Reconstituted Syn3A-lipid vesicles; living-cell lysis and FDA uptake (tagged strain)** | 0.5 M NaCl proteome only |
| Structure | Two raw tomograms; a 3C map | **140 in-cell maps** |
| Genetics, perturbation | Essentiality; evolved lineages with growth and mutations; division genetics (data not public) | Essentiality; many perturbation transcriptomes |
| Division, morphology | Syn3B counts and cell-size data (related strain); Pelletier not public | Gliding, attached cells with an attachment organelle: a poor division subject |
| Licences (§3.1) | Mostly CC BY and CC0. Presutti and Sandberg are non-commercial; the Frallicciardi traces have no stated terms | The main sources are non-commercial: analysis only (D173). CC BY counterparts exist for abundance and turnover, not for the pH perturbation |
| Protein-coding genes | 452 (455 with markers) | About 690 (the brief; not re-verified) |

### 9.3 Should *M. pneumoniae* lead a stage?

**Yes: an energy, transport and pH stage (call it 4a), tied to FR-4 and finite fuel.**

**What the files hold, opened (15 November).** The `.xls` files were read with a
standard-library reader, `scripts/xls_dump.py`; the same tables are in Table S17, "dataSheet".

| Data | Numeric? | What it holds |
| --- | --- | --- |
| Fig. 4A–B, the pH challenge | **Yes** | Protein (µg) and glucose (mM), mean and s.d. of triplicates. Columns: day 2, day 3, each pre-set pH from 5.0 to 8.0 (the text says 5.5–8.0), Hayflick at day 3, and rebuffered |
| Fig. 4C, rebuffering | **Yes** | Lactate and glucose (mM) at 12 time points over 0–158.5 h of one batch culture, and a rebuffered arm sampled from 96.75 h (4 shared time points). Without rebuffering, glucose consumption stalls while lactate levels off; rebuffered, both resume |
| The medium pH at rebuffering | **Stated** | From about pH 6 back to 7.7, by NaOH titration after 4 days (the methods and the Fig. 4 legend). The unbuffered arm's pH curve is plotted, but it is not in the source data |
| Batch time courses of glucose, lactic and acetic acid, and protein (SI Fig. S5) | **No** | Only a figure. Table S8 gives just the fitted sigmoid parameters, and Table S6's ATP budget is in silico |
| Medium-pH time course (7.8 to 5.5 over 4 days) | **No** | Quoted from Yus et al. 2009 |
| The defined medium | **Not obtained** | Yus et al. 2009 (*Science* 326:1263) is not in PMC, and science.org refused automated access (HTTP 403). Fig. 4A–B ran in Hayflick, a rich medium with horse serum. Leads for a serum-free recipe are in §3.1 |

**One measured perturbation the engine could predict with FR-4 and finite fuel, but no growth
model: Fig. 4C's rebuffering.**
- **The setting:** after 4 days (96.75 h) the medium has acidified to about pH 6. Soon after,
  the unbuffered culture's glucose consumption stalls, which the authors read as reversible
  metabolic stalling of a stationary population.
- **The perturbation:** rebuffering the medium from about pH 6 to 7.7.
- **The measured response:** glucose consumption and lactate secretion resume, against the
  unbuffered arm (4 shared time points to 158.5 h).
- **The model would need:**
  - the population's biomass held fixed;
  - glycolysis as reactions that make ATP (finite fuel);
  - proton-coupled lactate export and an ATPase spending ATP;
  - medium and cytosol pH with buffering (FR-4).
- **The gaps:**
  - **Biomass is not measured in this culture.** The Fig. 4C file holds only lactate and
    glucose. Fig. 4A–B comes from separate cultures: 48 h of growth, then a medium exchange.
    Fig. 4C's culture was instead a 96 h pre-culture diluted into fresh medium.
    - So biomass is a declared input.
    - The prediction is the rebuffered arm relative to the unbuffered one.
  - **The pH:** the unbuffered arm's pH curve is a figure only. So the medium pH is a declared
    input, apart from the stated rebuffering step.
- **The licence:** Wodke 2013 is non-commercial, and no permissive equivalent was found (§3.1).
  The perturbation can be analysed now. A judged Stage 4a on it needs the user's decision.

**Other rules for these data:**
- **ATP budgets:** the paper's are model-derived and stay apart from the measured fluxes.
- **Protein turnover** is the natural test for the closed molecular-to-physiology loop. Anything
  judged uses Burgos et al. 2020's 488 fits (CC BY); Maier's 231 serve analysis only.
- **The figures stay separate:**
  - Maier: 413 proteins with absolute copy numbers, and 231 with turnover rates;
  - Weber: 528 proteins with copy numbers;
  - Burgos: 488 turnover fits.
- **Licences (D173):** the three main sources are non-commercial (CC BY-NC-SA 3.0 or CC BY-NC
  4.0).
  - They serve analysis only.
  - No table, trace or plot from them enters the repository.
  - Judged results use the CC BY counterparts where they exist (§3.1).

**Syn3A should keep the lead for:**
- membrane physics (S2-M1);
- lipid-diet physiology;
- division genetics.

**Recommended:**
- Register *M. pneumoniae* as an organism instance (§10) when Stage 4a is planned, with the
  rebuffering response as its first candidate measured perturbation, subject to the licence
  decision above.
- Bind protein abundance and turnover to the CC BY sources (Weber 2023, Burgos 2020).
- For the medium, treat the CC BY serum-free formulations (§3.1) as leads. Hayflick's own
  composition stays undefined, because of its serum.

## 10. Organism definitions in general

An organism definition supplies data, parameters and evidence for laws the engine declares. It
never declares laws itself.

| Part | Content |
| --- | --- |
| Organism and strains | Taxon, strains with lineage, genome accession and frozen annotation, compartments |
| Media and conditions | Named media with composition, as far as defined, and temperatures |
| Law-set references | IDs from the inner model's law declarations and the operators' law IDs. Kinetics are not restated |
| Parameter sets | Values bound to declared parameters, each pointing to evidence records, with `cited` or `calibrated` provenance. A value from a non-commercial source, or one with no stated terms, is bound by reference only (§7) |
| Observation models | Each assay's model and its calibrated nuisance parameters |
| Evidence inventory | The records of §7 |
| Benchmarks | Registered tests naming the records they set and judge, with their claim kinds |

**The instances.**
- **The first is S2-M1's reconstituted vesicle system.** It instantiates the structure (D174).
- **Then Syn3A,** and *M. pneumoniae* at Stage 4a.
- **The same structure takes** Xenopus, the mouse heart, planarian and human.

The structure lands with its first consuming milestone, since on its own it is tooling.

## 11. Fuel: what Syn3A and *M. pneumoniae* need

**Where the two notes stand.**
- **ARCHITECTURE.md (D174) fixes the requirement and leaves the representation open:**
  - reactions make and spend fuel;
  - pumps draw from the same amounts;
  - each standard potential has one authority;
  - water and division get interfaces later.
- **The revised inner-model note recommends fuel as inventory rows** (its option F2).

**Stages 2 and 3 need no fuel. Stage 4, and *M. pneumoniae*'s Stage 4a, need:**
- fuel made by reactions: glycolysis, and the PTS spending PEP;
- fuel spent by transporters, synthesis and lipid and nucleotide metabolism;
- species beyond ATP, ADP and Pi (GTP, UTP, CTP, the dNTPs, PEP);
- one owner of each standard potential;
- dilution by water and a split at division.

Rows meet this directly, and the two notes now meet. Recommended: name both organisms' metabolic
stages as registered consumers of the fuel decision.

## 12. Open questions for the user, with recommendations

D173 answered the earlier list (the track, P0, the Frallicciardi audit, the 4D outputs at
Stage 4, no contact with authors, the licence rule, *M. pneumoniae* soon). On 15 November it
also answered the non-commercial question: analysis only.
- **What follows from that.** Anything judged on *M. pneumoniae* protein abundance or turnover
  uses the CC BY sources (Weber 2023, Burgos 2020), and Maier stays analysis only.
- **The one licence question left** is Stage 4a's acceptance (question 3).
- The advisor's defaults on the 15 November recommendations went to the user separately.

These remain:

1. **S2-M1, narrowed as in §6.**
   - Its judged content is numerical: the closed passive test, then water coupling, at vesicle
     scale, against references from a separate agent. It depends on no external data.
   - The Frallicciardi arms are reported as summary statistics and verdicts, since the raw
     traces have no stated terms.
   - The Syn3A-lipid arm becomes workspace analysis, since Presutti is non-commercial (§3.1).
   - **Recommended: yes.** The references and the protocol can be prepared now on main's closed
     pair (§5.4). The judged run follows D172's round, for the trace-start items.
2. **The passive law's form,** for the inner-model note: its own ID declaring the constant-field
   kernel at valence 0, with exact booking, or a separate kernel?
   - **Recommended:** its own ID, sharing the kernel. The closed pair shows the energy role
     already matches from resolved starts; only the trace start needs exact booking.
3. **Should *M. pneumoniae* lead an energy, transport and pH Stage 4a,** with Fig. 4C's
   rebuffering as its first measured perturbation (§9.3)?
   - **Recommended: yes**, once FR-4 and finite fuel exist.
   - **The caveat:** that culture's biomass was not measured, so it is a declared input, and the
     prediction is the rebuffered arm relative to the unbuffered one.
   - **The licence:** the perturbation rests on Wodke 2013 alone. That source is
     non-commercial, and no permissive equivalent was found (§3.1). Under D173 it can be
     analysed now.
   - A judged Stage 4a on it needs your explicit acceptance, or a permissive measurement of a
     comparable perturbation.
4. **The Pelletier data:** your side's search continues; §1.1 lists what was checked and what
   was not.
   - **Recommended:** if they surface, add them as Syn3.0 and Syn3A strain records; until then,
     use Syn3B data only as related-strain evidence.

## Provenance

**Read in full:**
- the brief;
- Presutti et al. 2026 (with SI text and Fig. 3);
- Justice et al. 2024 (with Fig. 5);
- Breuer et al. 2019 (counts, proteomics, Table 1);
- Sandberg et al. 2023;
- Gilbert et al. 2021 (methods, deposits);
- Frallicciardi et al. 2022 (methods and data statement);
- Gabba and Poolman 2020 (the model and the ensemble average);
- Maier et al. 2011 and Wodke et al. 2013 (methods and data);
- Chen et al. 2016 (Table S1).

**Also read:**
- Pelletier et al. 2021 (abstract, key resources, data statement; author-hosted copy);
- the 4D and 2026 *Cell* abstracts (PubMed);
- EMDB EMD-53631;
- the inner-model note, read-only;
- ARCHITECTURE.md's modular core (D174);
- the engine's water, exchange, inventory-species and constant-field code, read-only, for §4.1
  and §5;
- for §3.1, searched for the abundance, turnover, medium and data statements: the CC BY full
  texts of Weber et al. 2023, Burgos et al. 2020, Burgos et al. 2023 and Gaspari et al. 2020
  (Europe PMC). Also the Zenodo record of the Frallicciardi analysis code.

**Not read:**
- the *Cell* versions of Pelletier, Thornburg and Dobbs;
- the Rottem and Schummer papers beyond their records;
- the *M. mycoides* membrane-potential primary paper.

**Access notes:**
- PRIDE's API returned 404 (the data are on MassIVE).
- MassIVE FTP timed out; its HTTPS download worked. Its file list came from a third-party index of
  MassIVE.
- NCBI rate-limited one request; it was retried.
- PMC's and EMBO Press's file links returned bot pages, so the PMC open-data bucket was used.
- MyMpn was offline.

**Privacy.** Every request used a generic client name. No login, no form and no contact with
authors.
