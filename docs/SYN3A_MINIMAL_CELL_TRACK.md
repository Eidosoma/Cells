# JCVI-syn3A as Cells' minimal-cell track: evidence audit, probes and first milestone

Status: **the track was adopted on 14 November 2026 (D173).**
- **This revision (15 November)** adds the five follow-up steps D173 named:
  - the search for the missing division data;
  - the check of D150's exchange;
  - the Frallicciardi 2022 audit;
  - probe P0 and its follow-ups;
  - the scale of the metabolism stage.

  It also adds the *M. pneumoniae* audit (D173, amended).
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
  - Six other folders under `syn3a/` belong to the visualizer's Syn3A agent. They are left
    untouched and are not counted here.

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
  - **Accuracy:** its shrinkage matches the closed form to 1e-8 relative, at second order.
  - **A permeant neutral row:** a row on the inner model's own constant-field route (valence 0, so
    Fick's law) gives the full shrink-and-swell, within 6e-8 of an independent two-variable
    reference.
  - **What fails:** a start from a trace concentration is refused by the energy ledger.
- **Exchange is a driven route, not passive permeation, as D174 records.** It books signed work
  and no heat.
  - The constant-field route meets the passive contract's items in the probe, except for its
    energy booking from a trace start.
  - So the generic passive law that D174 expects in D172's round has a kernel already. The law
    must add:
    - exact free-energy booking as heat;
    - finding 3's valence-0 bound term;
    - a trace policy.
- **The first milestone, concretely (§6):** neutral solute and water across protein-free vesicle
  membranes. Its claims are kept apart:
  - numerical verification;
  - calibration on the impermeant traces;
  - a held-out prediction of the permeant traces on the same membranes, using the Frallicciardi
    2022 data, which are numeric, public and from the same assay;
  - then Syn3A-lipid vesicles as an application, with no living-cell claim.
- ***M. pneumoniae* is richer in measured physiology, and should lead an energy, transport and pH
  stage tied to FR-4 (§9).**
  - It has measured protein turnover, absolute mRNA and protein copy numbers under several
    perturbations, and glucose, lactate, acetate and medium-pH time courses.
  - Its integrated database is offline, and most of its "1,748 data sets" are growth curves.
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
| Reconstituted membranes, same assay (Frallicciardi et al. 2022, *Nat. Commun.* 13:1605) | The paper's source-data repository, 91 files, about 4.2 MB; MD on Zenodo 10.5281/zenodo.6010416 | Raw stopped-flow traces: time plus 6–9 acquisitions, 1,000–3,000 points over 20–60 s, for KCl (water), formate, lactate and, on DOPC, POPC and DPPC, glycerol. One exemplary DLS distribution per composition. Paper CC BY; **the repository has no licence file** | Calcein-loaded vesicles of DOPC, POPC, DPPC, a chain-length series and sterol series; 20 °C; about 300 mOsm/kg after mixing | Reconstituted (traces); fitted (coefficients) | 16 files, 1.1 MB (§6.2); the MD archive not downloaded |
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

**Related public data found on the way:**
- **Moger-Reischer et al. 2023, "Evolution of a minimal cell."** Figshare
  10.6084/m9.figshare.23119985, CC BY. Cell size (699 MB), FtsZ (390 MB), growth curves (8 MB)
  and fitness (176 MB) for JCVI-syn3B and syn1.0. This is related-strain evidence for Stage 5;
  not downloaded.
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

- **Syn3A:** 80 MB in 18 source folders (the earlier 17 plus the Frallicciardi subset).
- ***M. pneumoniae*:** 4.4 MB in 3 folders (§9).
- **How the files were handled.** Every file was only streamed to disk and hashed. Workbooks were
  read as XML with the standard library, and nothing downloaded was executed.
- **Awaiting approval:** the 4D model's outputs, at the metabolism stage (D138, D173). No source
  exceeds 20 GB.
- **Not downloaded, under the brief's rules:** raw spectra, raw tomograms, raw reads.
- **Not downloaded, optional:**
  - the TEM zip (0.51 GB);
  - the two MD archives;
  - the Moger-Reischer data (1.3 GB);
  - the Frallicciardi weak-acid traces, which are kept for FR-4's case (§6.4).

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
  Fig. 3b and the inventory JSON; that article is CC BY-NC-ND, so its table is not copied here.
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
  water it gives the full shrink-and-swell. It fails from a trace start.
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

**A bioelectric prior from relatives.** For mycoplasma membranes, published measurements give:
- a proton-motive force of 70–130 mV and energy-dependent volume regulation in *M. gallisepticum*
  (Rottem, Linker and Wilson 1981, *J. Bacteriol.* 145:1299);
- about −80 mV by carbocyanine dyes, with K⁺ and Na⁺ diffusion potentials (Schummer and Schiefer
  1983, a review).

A value of about −85 mV with an internal pH 0.5 above the medium is reported for *M. mycoides
capri*, Syn3A's parent. Its primary paper was not verified.

### 4.3 Stage 4: metabolism, protein inventory and growth

**Data:**
- **Breuer et al. 2019:**
  - 428 quantified proteins;
  - transposon essentiality;
  - a reconstruction of 338 reactions and 304 metabolites;
  - a 105 min doubling time in SP4.
- the evolution study;
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
| 10-fold step | Runs. The vesicle shrinks to 0.675 V0 and recovers. Volume within **6.1e-8** of an independent two-variable reference |
| 100-fold and 10⁴-fold steps | Run. Energy residual 6.9e-8 and 3.3e-4 relative, the latter 16% of the 2e-3 tolerance |
| Reversed gradient (lumen 120, bath 12 mM) | Runs. The G amount falls (efflux); in the forward case it rises |
| Heat | The membrane heat is positive and monotone in every run |

### 5.3 The passive contract (D174), applied

| Item | Exchange (paired first-order routes; from its contract and documented booking, not run) | Constant-field route at valence 0 (probe) |
| --- | --- | --- |
| Zero net flux at equal chemical potential | Only with rate constants tied to the declared volume | **Yes** (no-gradient run) |
| Reversal with the driving force | Yes | **Yes** (reversed run) |
| Conserved material | Yes | **Yes** (balance errors 0) |
| Zero external work | **No:** books signed supplied work | **Yes:** books membrane heat only |
| Dissipation equal to the free-energy decrease | **No:** books no heat | **Within the ledger tolerance** from resolved starts. The residual grows with the start ratio (1.6e-8 at 10×, 3.3e-4 at 10⁴×), and a trace start is refused |
| Composes with water and held baths | Refused | Yes |

**Conclusion.** A generic passive law is needed in D172's round, as D174 expects. It can declare
the constant-field kernel at valence 0 under its own ID and contract. It must book the exact
free-energy change of each step as heat, as D150's exchange stages book theirs as work, so that
trace starts are admitted. It must also carry finding 3's bound term.

The probe found no need for a separate operator, and no need for D150 version 1.1 for this case:
water already counts inner-model species rows. D150 version 1.1 is still needed wherever D150's
own operators meet water.

## 6. The first milestone: S2-M1, neutral solute and water across protein-free vesicles

### 6.1 Claims, kept apart (D174)

| Kind | What | Data | Judged? |
| --- | --- | --- | --- |
| Numerical verification | The passive law and water against closed forms and an independent reference written blind: the five contract items at fixed volume, then shrink-and-swell with water, with dt refinement. A trace start is included | None | Yes, numerically |
| Calibration | Per membrane (POPC, DOPC, DPPC): P_w and K_SV fitted on the KCl traces with the exemplary DLS distribution; P_gly fitted on a late window of the glycerol trace only (t > 20 water time constants). The published coefficients reproduced as a consistency check | Frallicciardi 2022 | No: reported as calibration |
| Protein-free vesicle prediction, held out | On the same membranes: each glycerol trace's early, water-dominated window (time to minimum, depth, residuals against the acquisitions' spread), with nothing refit. This is a different osmolyte and gradient on the same membrane. **S:** glycerol relaxes about 30–40 times more slowly than water in the fluid and Syn3A-lipid membranes, so the windows separate; DPPC is checked when calibrated | Frallicciardi 2022 | **Yes, the milestone's judged claim** |
| Syn3A-lipid application | The three Syn3A-lipid mixtures' glycerol traces, early window. The published P_w is an input. K_SV and the size prior are transferred from the same-lab calibration, an assumption the held-out arm tests first. Mixture-to-mixture interpolation is reported only as a consistency check, since it passes by hand | Presutti 2026 | Yes, labelled as transferred calibration |
| Held-out living-cell prediction | None. The public data allow none at this stage. Stage 3's lysis needs F5 | — | — |

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
  - the round's passive law, with exact booking and finding 3's term;
  - water@1 qualified at vesicle scale (P0 is the development evidence);
  - an independent reference written blind;
  - a PROPOSED protocol registered before one judged run.
- **Cost:** CPU minutes per world.
- **Data in hand:** the 16-file Frallicciardi subset (1.1 MB) and Presutti's Source Data.

### 6.3 Why this design

- **It is choosing by measured perturbations.** The public data's only same-membrane perturbation
  is a second osmolyte. That is what the engine can be judged on without a composition rule
  Cells lacks.
- **It reuses an architecture case.** The vesicle is one of the architecture's named reuse cases.
- **Everything it needs is general.** The passive law also serves drugs, metabolic wastes, gases
  and FR-1's compartments.

### 6.4 The natural next case: weak acids and pH

Frallicciardi's formate and lactate traces are on the same membranes. They need proton and buffer
chemistry inside the vesicle, so they are FR-4's compartment-pH case on measured data. This also
leads toward *M. pneumoniae*'s pH stage (§9).

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
| Maier et al. 2011, *Mol. Syst. Biol.* 7:511 | 10.1038/msb.2011.38, PMC3159969; CC BY-NC-SA 3.0. MS raw data were placed on Tranche (ProteomeCommons); not checked | Strain not named in the methods; Hayflick medium as in Yus et al. 2009, attached growth; 24 h sampling over 4 days; perturbations at 96 h: **0.5 M NaCl osmotic stress**, mitomycin C, heat shock at 42 °C; a minimal-medium arm. Controls 9 replicates, perturbations duplicates | Average copies per cell of 413 proteins (anchored by labelled reference peptides; about 1.5–1.8-fold error); **turnover of 231 proteins** (SILAC chase, 1–8 days); mRNA copies per cell (tiling arrays with spike-ins; GEO); the proteome's response to each perturbation | Stochastic expression simulations | Tables S1–S8 (zip, 310 KB), SI text, model file: `maier2011-msb` |
| Wodke et al. 2013, *Mol. Syst. Biol.* 9:653 | 10.1038/msb.2013.6, PMC3658275; CC BY-NC-SA 3.0; model iJW145 (BioModels MODEL1301290000) | Rich and defined media, glucose (strain and temperature not checked in this round) | **Batch time courses:** glucose consumed, lactate and acetate secreted, protein, medium pH 7.8 → 5.5 over 4 days. **36 h at pre-set pH 5.5–8.0:** glucose used and protein made (Fig. 4A–B), and recovery after a shift back (Fig. 4C). ¹³C-glucose labelling | ATP production (about 60,000 per cell per second at 36 h), the ATPase's share (up to 57%), maintenance: FBA with fitted constraints, never to be used as measurements | Fig. 4 and SI Fig. 2–3 source data, Tables S1–S17, SI: `wodke2013-msb` (2.0 MB) |
| Chen et al. 2016, *NAR* 44:1192 | 10.1093/nar/gkw004, PMC4756857; CC BY-NC 4.0 | Consistent conditions from one group | The 1,748 data sets: **1,300 growth curves** at various nutrient concentrations (Yus et al. 2009), about 300 transcriptome data sets along growth and under stress, 57 proteome data sets along growth, interactions, modifications, turnover, metabolome (86 of 152 predicted metabolites), essentiality | — | The data workbook (Tables S1–S15) and index: `chen2016-nar` (1.9 MB) |
| MyMpn (Wodke et al. 2015, *NAR* database issue) | 10.1093/nar/gku1105, PMC4383923; CC BY-NC 4.0 | — | The integrated database: **offline** (HTTP 404 at both addresses, 15 November 2026). Each data set must be fetched from its original deposit | — | — |
| Dobbs, Jensen and Mahamid 2026, *Cell* | 10.1016/j.cell.2026.08.054, PMID 42790420; not in PMC | Strain M129-B7; native and antibiotic-perturbed cells | 140 subtomogram-average maps of translation states; EMD-53631 verified | — | Metadata only |
| Membrane, ion and osmotic data | — | — | **None found for *M. pneumoniae*** beyond the 0.5 M NaCl proteome response and the medium-pH challenge. Relatives only: §4.2's bioelectric prior | — | — |

### 9.2 Side by side

| What a Cells model could be judged on | JCVI-syn3A | *M. pneumoniae* |
| --- | --- | --- |
| Protein abundance | 428 proteins, one medium, 3 phases; absolute counts scaled | 413 proteins with absolute copies anchored by reference peptides, under growth and four perturbations |
| Protein turnover | None | **231 half-lives** |
| mRNA | Relative expression of the ancestor and evolved clones | **Absolute copies per cell**, time courses and about 300 stress data sets |
| Energy, transport, pH | None measured; undefined medium | **Glucose uptake, lactate and acetate secretion, medium acidification, pH-dependent growth arrest and recovery;** a defined medium exists |
| Membrane permeability, osmotic response | **Reconstituted Syn3A-lipid vesicles; living-cell lysis and FDA uptake (tagged strain)** | 0.5 M NaCl proteome only |
| Structure | Two raw tomograms; a 3C map | **140 in-cell maps** |
| Genetics, perturbation | Essentiality; evolved lineages with growth and mutations; division genetics (data not public) | Essentiality; many perturbation transcriptomes |
| Division, morphology | Syn3B counts and cell-size data (related strain); Pelletier not public | Gliding, attached cells with an attachment organelle: a poor division subject |
| Licences | Mostly CC BY and CC0; Presutti and Sandberg CC BY-NC-ND | Mostly CC BY-NC-SA or CC BY-NC: values citable, tables not copied |
| Protein-coding genes | 452 (455 with markers) | About 690 (the brief; not re-verified) |

### 9.3 Should *M. pneumoniae* lead a stage?

**Yes: an energy, transport and pH stage (call it 4a), tied to FR-4 and finite fuel.**
- **The measured targets:**
  - glucose consumed, lactate and acetate secreted, medium pH and protein over a batch;
  - the response to pre-set medium pH;
  - recovery.
- **What it would exercise:** a held or finite medium with pH (FR-4), proton transport, secretion,
  reactions that make and spend fuel (§11), and a growth readout.
- **A rule for the data:** the paper's ATP budgets are model-derived and must stay apart from the
  measured fluxes (the brief's point).
- **Protein turnover** (Maier) is the natural test for the closed molecular-to-physiology loop.

**Syn3A should keep the lead for:**
- membrane physics (S2-M1);
- lipid-diet physiology;
- division genetics.

**Recommended:** register *M. pneumoniae* as an organism instance (§10) when Stage 4a is planned,
and audit its defined medium and the growth-curve deposits then.

## 10. Organism definitions in general

An organism definition supplies data, parameters and evidence for laws the engine declares. It
never declares laws itself.

| Part | Content |
| --- | --- |
| Organism and strains | Taxon, strains with lineage, genome accession and frozen annotation, compartments |
| Media and conditions | Named media with composition, as far as defined, and temperatures |
| Law-set references | IDs from the inner model's law declarations and the operators' law IDs. Kinetics are not restated |
| Parameter sets | Values bound to declared parameters, each pointing to evidence records, with `cited` or `calibrated` provenance |
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
Stage 4, no contact with authors, the licence rule, *M. pneumoniae* soon).

1. **S2-M1 as designed in §6:** protein-free vesicles, with claims kept apart; Frallicciardi
   2022 for the held-out arm; Syn3A-lipid vesicles as an application.
   - **Recommended: yes.** It is judged once D172's round has landed the passive law.
2. **The passive law's form,** for the inner-model note: its own ID declaring the constant-field
   kernel at valence 0, with exact booking, or a separate kernel?
   - **Recommended:** its own ID, sharing the kernel. The reuse rule allows sharing where the
     energy role matches, and the probe shows it does once booking is exact.
3. **Should *M. pneumoniae* lead an energy, transport and pH Stage 4a,** as FR-4's and the fuel
   decision's measured-data consumer?
   - **Recommended: yes.** Plan it after S2-M1, with a second audit of its defined medium and
     growth-curve deposits.
4. **The Moger-Reischer Syn3B data** (1.3 GB, CC BY), for Stage 5.
   - **Recommended: defer to Stage 5,** as related-strain evidence.
5. **The Frallicciardi repository has no licence file.**
   - **Recommended:** use it for analysis only, cite the CC BY paper, and redistribute nothing.
6. **The Pelletier data:** your side's search continues. §1.1 lists what was checked.
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
  and §5.

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
