# JCVI-syn3A as Cells' minimal-cell track: evidence audit and proposal

Status: **proposed, 14 November 2026.** This note is an assessment, not a design or a protocol.
It adds no engine code, no run and no acceptance.
- **Source:** the user's research brief, `docs/SOTA_SYN3A.md` (untracked in the main checkout).
  Its links carry chatbot tracking tags, so every claim and link was treated as a lead and checked
  at the primary source.
- **Builds on** [the review of the 4D whole-cell paper](PAPER_REVIEW_WHOLE_CELL_MINIMAL_CELL.md),
  which it does not repeat, and on the [protein catalogue plan](PROTEIN_CATALOGUE_PLAN.md).
- **Evidence:** [/mnt/workspaces/Cells/syn3a-20261114-01](/mnt/workspaces/Cells/syn3a-20261114-01/HANDOFF.md).
  It holds the machine-readable inventory (`syn3a_evidence_inventory.json`), the access log and
  the scripts.
- **Data:** `/mnt/datasets/Cells/syn3a/<source-id>/`, one folder per source, each with a
  `MANIFEST.json` giving every file's URL, retrieval time, size and SHA-256.

**S** marks our own arithmetic or inference.

## 0. Verdict

- **Syn3A is a defensible first whole-cell organism, but the public evidence is thinner than the
  brief implies.**
  - The Pelletier 2021 division deposit does not resolve. The paper's own DOI returns "not found"
    everywhere.
  - The 2026 reconstituted-membrane Zenodo archive holds molecular dynamics only. The wet-lab
    permeability data sit in the journal's Source Data workbook.
  - The 2024 lipid-diet paper used the labelled derivative Syn3A-mCherry. It measured
    permeability and osmotic lysis only across lipid-chirality diets, and it attributes those
    differences to lipid–protein interactions, not to bilayer properties.
  - The gene counts hold, but two protein lists are in use: 452 native protein-coding genes in
    Breuer et al. 2019, or 455 in GenBank CP016816.2, which adds three engineered marker genes
    (*tetM*, *HIS3*, *MET14*). A model must freeze one (§2).
- **Stage 2 is the right first milestone,** in a corrected form (§5).
  - It uses the stopped-flow vesicle data of Presutti et al. 2026.
  - Its judged content is an engine-run prediction of a held-out mixture's shrink and swell
    trace. Interpolating that mixture's coefficients alone cannot discriminate, as §5.2 shows.
  - Calibrating on an external data set from the same assay would make the stronger test.
  - It claims nothing about living cells.
- **The first milestone needs general engine features, none of them specific to Syn3A** (D144):
  - passive permeation of neutral solutes across a membrane patch (new);
  - water composed with neutral inventory species (D150 version 1.1);
  - the queued D148 bound term for neutral species on membranes.

  A probe that needs none of these is expected to run on the engine as it is. Whether the inner
  model admits a vesicle with no channels and no pumps is the probe's first check (§5.3).
- **Later stages each name a general feature Cells lacks:**
  - membrane failure under tension (Stage 3);
  - metabolism at scale, and fuel that reactions make and spend (Stage 4);
  - shape mechanics and a constriction machinery law (Stage 5).
- **The 4D whole-cell model stays a reference.** A comparison with its saved outputs is proposed,
  not done (D138). Only a 288 MB member of its 12 GB archive would be needed (§7).

## 1. The evidence audit (Stage 1)

Categories follow the brief's §6 table and are assigned relative to the declared target,
JCVI-syn3A with genome CP016816.2. A labelled derivative (Syn3A-mCherry, Syn3B) is its own strain
record, so for this target it counts as a related strain. Sizes are as reported by the
repositories. Full records are in the inventory JSON.

| Resource | Identifier and status | Contents, size, licence | Strain, medium, temperature, assay | Category | Downloaded |
| --- | --- | --- | --- | --- | --- |
| Proteomics (Breuer et al. 2019, *eLife* 8:e36842) | PXD008159 = MSV000081687. Hosted by MassIVE; the PRIDE API returns 404 | 21 files, 9.03 GB: 8 Thermo raw (2.69 GB), 9 mzML (6.30 GB), a PSM mzTab (21 MB). CC0 | Syn3A; SP4 with horse serum in place of FBS; 37 °C; log, early-plateau and plateau phases, 3 biological replicates each; TMT LC-MS3 | Measured: 428 proteins' relative abundances. Inferred: absolute copies, scaled by an assumed protein mass fraction | mzTab, parameters, statistics; the paper's supplementary files 1–11 (1.6 MB, CC BY) |
| Division and morphology (Pelletier et al. 2021, *Cell* 184:2430) | Mendeley 10.17632/rwg6sdz4rf.1, as the paper gives it. **Does not resolve:** doi.org "DOI Not Found", no DataCite record, Mendeley API 404 | Declared: source data and code for Figs 1D, 4D and 5E, and chemostat videos | syn1.0, syn3.0, syn3A and syn3.0 with gene subsets; SP4 with FBS; time-lapse microscopy in microfluidic chemostats | Measured per strain, but unreachable | Records of the failed lookups |
| Cryo-ET (Gilbert et al. 2021, *Front. Mol. Biosci.* 8:644133) | EMPIAR-10685 and -10686 (EMD-23660, -23661) | 6.5 and 6.4 GB: one raw tilt series and its frames per entry, one cell each | Syn3A; SP4 with KnockOut serum replacement (SP4-KO); 37 °C; mid-log | Measured: boundary and ribosomes, in cells flattened to about 160 nm by blotting. Inferred: the spherical reconstruction and chromosome paths | Entry metadata |
| 3C (same paper) | 4TU 10.4121/14333618 | One processed `.hic` contact map, 866 KB (MD5 verified). CC0 | Syn3A; SP4-KO; 37 °C; stationary phase; NlaIII 3C-seq | Measured | Yes |
| Evolution and expression (Sandberg et al. 2023, *iScience* 26:107500) | GEO GSE205017; reads under PRJNA843075 | 13 processed per-sample tables (90 KB), the genome and its GFF3. Paper CC BY-NC-ND | Syn3A ancestor and clones from 10 lineages after about 400 generations; SP4-KO; 37 °C; log phase | Measured. Each evolved clone is its own strain record | Yes, with Table S1 (mutations) |
| Lipid diets: lipidomics (Justice et al. 2024, *Nat. Commun.* 15:9679) | Zenodo 10.5281/zenodo.13817894 is the concept DOI; the record is 13817895 | One workbook, 38 KB, byte-identical to the article's Supplementary Data 3. CC BY. Raw files never deposited (the provider's restriction, as the brief says) | *M. mycoides* on three diets; **Syn3A-mCherry on diether PC + cholesterol only**; 37 °C; 3 biological replicates | Related strain (Syn3A-mCherry) | Yes |
| Lipid diets: TEM | BioStudies S-BSST1651 | One zip, 514 MB. CC0 | Syn3A-mCherry on FBS, POPC and diether PC diets | Related strain | Study metadata |
| Lipid diets: journal files | Source Data (5.9 MB), Supplementary Data 1–3, SI (26 MB) | Numeric values for Figs 2–6. CC BY | Growth as a phenol-red acidification rate; propidium iodide lysis after shock into water; fluorescein diacetate (FDA) uptake | Related strain. The FDA coefficient is inferred, from a slope and an assumed area per lipid | Yes |
| Replication (Thornburg et al. 2026, *Cell* 189:2582) | BioProject PRJNA1257452 | 9 MiSeq runs, 3.8 GB of reads | Syn3A-mCherry; SP4; 5, 9 and 21 h, 3 replicates each. The 5 h runs were released on 17 November 2025, after bioRxiv v1 | Related strain. The ori:ter ratio is inferred | Run metadata |
| Reconstituted membranes: archive (Presutti et al. 2026, *Nat. Commun.*) | Zenodo 10.5281/zenodo.20613506 (concept 20613505) | One zip, 590 MB, 2.5 GB unpacked. **Martini 3 MD only:** systems, scripts, processed MD outputs. CC BY | Coarse-grained bilayers and vesicles, 0–80% cholesterol, 293 K and 310 K | Another simulator | Record, listing and 20 small members (READMEs, summary tables), by range requests |
| Reconstituted membranes: journal files | Source Data (343 KB), SI (22 MB) | Glycerol traces numeric. The KCl and ribose traces and the DLS size distributions are images only. **Article CC BY-NC-ND** | Synthetic vesicles of three five-lipid mixtures; 20 °C; stopped-flow calcein assay for water, glycerol and D-ribose; Langmuir monolayers; cryo-TEM | Reconstituted (traces). The permeability coefficients are fitted | Yes |
| The 4D model | GitHub `Luthey-Schulten-Lab/Minimal_Cell_4DWCM`; Zenodo 15579158 is the concept DOI of record 15579159 | Zip of 12.0 GB: frozen code, inputs, 50 count-and-flux CSVs (302 MB), 4 trajectories (11.7 GB). Zenodo CC BY; **no licence file in the repository** | — | Another simulator | Metadata, file tree and listing; nothing cloned or run |
| Genome | GenBank CP016816.2, updated 12 April 2018 | Feature table | — | Measured (annotation) | Yes |

**One candidate source not in the brief.** Frallicciardi et al. 2022 (*Nat. Commun.* 13:1605,
CC BY) used the same assay, by the same group, at 20 °C. It covers simpler mixtures (POPC,
DOPC and DPPC with cholesterol or ergosterol), and its experimental source data are in a
public repository. Only its data statement was read (§5.5).

## 2. The brief's claims, checked

| Claim | Verdict | Primary evidence |
| --- | --- | --- |
| Syn3A has 452 protein-coding genes, 493 genes and 543 kbp | **Confirmed, with the lists reconciled** | Breuer et al. 2019's gene table (supplementary file 3): 452 coding sequences + 38 RNA genes + 3 pseudogenes = 493; three engineered features (*HIS3*, *tetM*, *MET14*) are listed apart. GenBank CP016816.2: 543,379 bp; 455 intact coding sequences, which are those 452 plus the three markers; 3 pseudogenes; 38 RNA genes. The brief's "newer papers use 455" matches GenBank. A model must say whether the markers, which are expressed, are in scope |
| syn3.0 has 438 protein-coding genes | Confirmed | Breuer et al. 2019, citing Hutchison et al. 2016: 531 kbp, 473 genes (438 protein, 35 RNA) |
| 428 of 452 proteins detected by proteomics | **Confirmed independently** | Table 1 of the paper; its supplementary file 5 has 428 distinct accessions with abundances (counted here). Absolute counts are scaled, not measured |
| The 2024 paper measured growth, membrane composition, permeability and osmotic sensitivity in living Syn3A | **Corrected** | See §4.2: a labelled strain; growth is a metabolic index; composition deposited for one Syn3A diet; permeability and lysis only across chirality diets; the authors attribute those changes to lipid–protein interactions |
| Raw lipidomics were withheld for proprietary reasons | Confirmed | The paper's data availability statement |
| The 2026 paper measured water and osmolyte permeability and physical properties of reconstituted Syn3A-like membranes | **Confirmed, with corrections** | Three synthetic five-lipid mixtures at 20 °C; water, glycerol and D-ribose. The Zenodo archive is MD only; the article is CC BY-NC-ND, not CC BY |
| The 4D model used about 15,000 A100 GPU-hours | **Confirmed against bioRxiv v1 only** | v1 (Fig. 1, p. 10), the only preprint version, as read in the earlier review. The *Cell* version is unreadable here and its abstract gives no compute figure |
| The 4D model has no kinetic FtsZ division model | **Confirmed against bioRxiv v1 only** | FtsZ particles without polymerisation or midplane localisation; division imposed as two overlapping spheres (v1 pp. 6, 56–58) |
| Pelletier data, code and videos are on Mendeley | **Corrected: cited but unresolvable** | The paper gives 10.17632/rwg6sdz4rf.1; all lookups fail (14 November 2026) |
| Seven genes, including *ftsZ* and *sepF*, restore a parental-like phenotype | Confirmed | Seven of the 19 genes are required together: *ftsZ*, *sepF*, a hydrolase and four membrane-associated proteins of unknown function |

## 3. What was downloaded, and what waits

- **Downloaded:** 79 MB in 17 source folders under `/mnt/datasets/Cells/syn3a/`. Every file was
  only streamed to disk and hashed. Workbooks were read as XML with the standard library; nothing
  was opened by an application or executed.
  - Stage 2: `presutti2026-natcommun` (Source Data, SI, Reporting Summary) and `zenodo-20613506`
    (MD record, listing and summary tables).
  - Stage 3: `justice2024-natcommun` (Source Data, Supplementary Data 1–3, SI) and
    `zenodo-13817895` (lipidomics).
  - Others: proteomics results, eLife supplements, the GEO processed files, the iScience table,
    the 3C map, the genome record, and metadata for EMPIAR, BioStudies, the BioProject and the 4D
    model.
- **Awaiting approval:** the 4D model's outputs, under D138 (§7). No source exceeds 20 GB.
- **Not downloaded, under the brief's rules:** raw spectra (9.0 GB), raw tomograms (12.9 GB), raw
  reads (3.8 GB and the unsized PRJNA843075).
- **Not downloaded, optional:** the TEM zip (0.51 GB) and the MD archive (0.59 GB). Neither is
  needed for the first milestone.

## 4. Stage by stage

### 4.1 Stage 2: reconstituted-membrane transport

**What the data measure.**
- Calcein-loaded vesicles, extruded at 200 nm, in 100 mM potassium phosphate, are mixed 1:1
  with an osmolyte at 20 °C.
- Water leaves first, the vesicles shrink and calcein self-quenches. A permeant osmolyte then
  enters and restores the volume.
- The authors fit a vesicle ODE to each averaged trace. The ODE takes DLS size distributions as
  input. They fit the water coefficient on the impermeant KCl step and fix it for the permeant
  steps, fitting the solute coefficient and a Stern–Volmer constant per trace.
- The authors note that multilamellar vesicles bias absolute values low.

**The three mixtures** (cholesterol : sphingomyelin : cardiolipin : POPC : DOPG, mol%) are
60:18:16:4:2, which mimics Syn3A's measured lipidome, then 40:18:16:24:2 and 20:18:16:44:2.

**The coefficients,** in round orders of magnitude:
- water 10⁻³ to 10⁻² cm/s;
- glycerol 10⁻⁷ to 10⁻⁶;
- D-ribose 10⁻⁹ to 10⁻⁸.

Each falls as cholesterol rises, with n = 3 per value.

**Where the values are.** The exact values are in the article's Fig. 3b and in the inventory JSON.
The article is CC BY-NC-ND, so its table is not reproduced here (§11, question 8). The glycerol
traces behind the fits are numeric in the Source Data, from 2 ms to 200 s with s.d.

**What Cells already has.**
- **The composite** `resolved_pump_composite@1` over its inner model, with held baths and finite
  nodes.
- **Water:** `ideal_osmosis_linear_compliance_water@1`. Flow is A·Lp·Δψ, with ideal van 't Hoff
  osmotic pressure and a linear volume compliance.
  - The water coefficient Pf maps to Lp through the molar volume of water.
  - The law needs effective osmolarities in place of activities. 100 mM potassium phosphate
    measures about 190 mosmol/kg, well below its ideal ion count.
- **The bath schedule** `scheduled_bath_composition@1` (FR-10).
- **Batched worlds,** for a vesicle size distribution. The size averaging and the calcein
  observation model belong in a validation driver.

**What is missing, as general features.**
- **F1, passive permeation of neutral solutes across a membrane patch.** Inventory species have
  zero membrane permeability today (`inventory_species.py`). The law would be bidirectional,
  J = P·A·(c_out − c_in), with an optional reflection coefficient, booked heat and conserved
  amounts.
  - It is general: glycerol, urea, ribose, drugs, metabolic wastes, gases.
  - D150's exchange routes are one-way and refuse a patch on a held bath, so either exchange grows
    a passive route or a new law is written. The design note should decide.
- **F2, water with neutral species,** which D150 version 1.1 is to provide. Today water and the
  species operators are refused together.
- **F3, the D148 bound term for neutral species on membranes,** already queued (D152).
- **F4, door W, an anisosmotic bath step.** It is already scheduled for E07-v2's osmotic
  challenge. A world that starts out of osmotic equilibrium avoids it (§5.3).

**Organism-specific data and parameters.** The three compositions, the buffers and their
measured osmolalities, the permeability table, the traces, the size distributions (images
only), and 20 °C.

### 4.2 Stage 3: living-cell responses on lipid diets

**What the data measure** (Justice et al. 2024; all at 37 °C in modified SP4 with phenol red;
lipids on delipidated BSA).

| Readout | Diets with Syn3A-mCherry data | How it is measured |
| --- | --- | --- |
| Growth | POPC, diether PC (Fig. 4a); POPC, enantiomeric POPC, racemic (Fig. 5c) | Rate of phenol-red acidification, by a logistic fit. A metabolic index, not a cell count; OD600 in the SI |
| Lipidome | Diether PC + cholesterol only (over 99 mol% two lipids) | Lipotype shotgun MS, 3 biological replicates |
| Morphology | FBS, POPC, diether PC | TEM: internal vesicles rise from about 15% to nearly 40%; size semi-quantitative |
| Lysis after hypo-osmotic shock | Chirality diets only: lysed fraction about 0.60, 0.76 and 0.90 | Propidium iodide after 30 min in water, against a boiled control; 3 × 3 replicates |
| Permeability | Chirality diets only: about 3.1, 3.6 and 5.2 × 10⁻⁶ cm/s | FDA uptake, by Fick's law with an area from a lipid phosphate assay and an assumed 45.1 Å² per POPC–cholesterol pair |

**The caution.** Growth falls, lysis rises and FDA permeation rises together across the
chirality diets. But c-laurdan order of extract liposomes did not change (*M. mycoides* only),
and the authors attribute the effects to lipid–protein interactions. A bilayer-property model
should therefore *not* be expected to explain these three readouts. Registering that expectation
would make the chirality series a falsification control rather than a target (**S**).

**What Cells already has.**
- Water and volume.
- Membrane state and insertion (area).
- Replacement@2, which removes and adds cells with booked volumes.
- Batched worlds for size heterogeneity.
- `resolved_repair@1`'s injury and resealing law. It lives in an older family, with prescribed,
  not tension-triggered, damage (FR-5's mapping).

**What is missing, as general features.**
- **F5, membrane failure under tension.**
  - Tension from the water law's pressure and the cell's radius.
  - A critical tension or area strain.
  - A pore state that leaks contents and can reseal.
  - Lysis as a cell-fate event with booked losses.

  It would generalise `resolved_repair@1` into the composite (FR-5, D161). It is general:
  red-cell osmotic fragility is a classic independent reference, from another organism.
- **F6, lipid composition as membrane-domain state,** with uptake from the medium, and declared
  composition-to-permeability and composition-to-mechanics laws. Stage 2 first tests the rule
  statically (§5).
- **F7, permeant reacting species.** FDA is hydrolysed inside the cell, and D152 version 1
  refuses permeant reacting species.
- **Growth as a process,** which is the lifecycle gate's milestone 2.

**Organism-specific.**
- The diets and their concentrations (Supplementary Data 1).
- The cell size distribution, which is only semi-quantitative.
- The cytoplasmic osmolarity, which is not measured in any source here and would be a labelled
  prior.
- Strain identity (mCherry).

### 4.3 Stage 4: metabolism, protein inventory and growth

**Data.**
- Breuer et al. 2019:
  - 428 quantified proteins;
  - transposon essentiality;
  - a reconstruction of 338 reactions and 304 metabolites, with an FBA model in SBML;
  - a 105 min doubling time in SP4.
- The evolution study's expression and growth data.
- The replication sequencing.
- Prior models, which are other-simulator evidence: the 2022 whole-cell model and the 4D model.

**The hard limit.** The medium is undefined. SP4 contains serum or serum replacement, yeast
extract and peptones, so uptake fluxes cannot be closed from the medium's composition (Breuer
et al. and Sandberg et al. both say so).

**What Cells already has.**
- **D152's reactions** (`local_species_reactions@1`). They are capped at 16 species and refuse
  water, so they cannot dilute with growth.
- **D150's turnover and exchange.**
- **The coupling operator,** from species to availabilities.
- **Membrane-state populations** with catalogue references.
- **Site occupancy,** designed under FR-3.
- **Assembly:** `finite_bond_assembly@1`.
- **The closed molecular-to-physiology loop gate,** which asks for exactly this kind of single
  material account.

**What is missing, as general features.**
- **F8, metabolism at scale:**
  - hundreds of species and reactions;
  - sparse stoichiometry and stiff implicit integration;
  - one owner of standard potentials;
  - composition with water and partition.
- **F9, fuel that reactions make and spend** (§10).
- **F10, polymerisation laws for transcription and translation with their costs.** These belong
  to the gene-regulation layer and catalogue stage 3, both held under D145.
- **F11, a stochastic regime for low-copy species** (the earlier review's rank 1 candidate).

**Organism-specific.** A frozen annotation and protein list, abundances, kinetic constants
(mostly inferred, or from related organisms), and the medium.

### 4.4 Stage 5: division and genetic perturbations

**Data.**
- Pelletier et al. 2021, whose deposit is unreachable.
- The 4D paper's imaging of 1,319 fixed **Syn3B** cells (earlier review).
- Two cryo-ET cells.

**What Cells already has.** Prescribed division (S2–S5: insertion, lumen, partition, bridge
closure) and the assembly layer.

**What is missing, as general features.**
- **F12, membrane shape mechanics for a single cell:** bending and tension. MG1 is a 2-D vertex
  model for tissues.
- **F13, a constriction machinery law:** ring assembly from FtsZ-type abundance, membrane
  anchoring, and force. This is the causal link from inventory to division the brief asks for.
- **F14, state-triggered division and stochastic partition of integer populations** (the
  lifecycle gate's milestone 2).
- **Chromosome replication and segregation,** which stay out of the division plan's scope.

**Organism-specific.** Each strain's gene set, FtsZ and SepF abundances, and the morphology
statistics.

## 5. The first milestone, recommended: S2-M1

**Question.** Does one passive-transport model in the Cells engine, with nothing refit,
predict the full shrink and swell trace of a vesicle composition it was not calibrated on?

### 5.1 Engine models it runs

- `resolved_pump_composite@1` over its inner model (`resolved_pump_tissue@3` today, restructured
  in place by the user's choice).
- `ideal_osmosis_linear_compliance_water@1`.
- The new neutral-permeation law (F1; its ID is set by its design note).
- `scheduled_bath_composition@1`, if the osmotic step is scheduled rather than set as the
  starting state.

The vesicle is a cell with no channels and no pumps, in a held bath. Whether the inner model
admits that is probe P0's first check.

### 5.2 Calibration and prediction

| Arm | What | Status |
| --- | --- | --- |
| **Calibration** | The coefficients of Mixtures 1 and 3 (60% and 20% cholesterol) for water, glycerol and ribose. The observation model fitted to their glycerol traces: one Stern–Volmer constant fitted jointly to both, and a size-distribution prior for each. Effective osmolarities from the measured lumen value | Inputs. Reproducing them is calibration and is reported as such |
| **A, judged: the held-out trace** | Mixture 2's whole glycerol trace (time to minimum, depth, recovery half-time, residuals against the s.d. band), run in the engine with nothing refit | The only judged, engine-run content |
| **B, consistency only: interpolated coefficients** | Mixture 2's three coefficients from the rule below | Cannot discriminate (below) |
| **C, recommended: external calibration** | The composition rule calibrated on Frallicciardi et al. 2022 instead, predicting all three Syn3A mixtures' coefficients and traces (§5.5) | Needs that source's audit |
| **Not claimed** | Living cells, 37 °C, protein-mediated transport, lysis, absolute coefficients (the multilamellar bias) | — |

**Arm A's inputs are fixed here, before any run.**
- **The coefficients:** log P linear in cholesterol mole fraction between the calibration
  mixtures, per solute.
- **The Stern–Volmer constant:** the joint fit.
- **The size distribution:** Mixture 1's prior. The paper reports Mixtures 1 and 2 as broad,
  extending to about 600 nm, and Mixture 3 as narrower.

**Arm B already passes by hand, so it cannot discriminate.**
- Mixture 2 sits midway in cholesterol, so the rule returns the geometric means of the
  calibration values.
- For all three solutes these fall within one s.d. of the measured Mixture 2 values (**S**;
  numbers in the inventory JSON).
- Mixture 2's values were also seen during this audit.
- So arm B is reported as a consistency check only, and arm C is the real test of a composition
  rule.

### 5.3 Order

1. **P0, now, with no new feature: a probe that runs `ideal_osmosis_linear_compliance_water@1`
   in the composite.**
   - A channel-free vesicle starts out of osmotic equilibrium, in the post-mixing bath with KCl as
     the impermeant osmolyte.
   - It is compared with an independent ODE reference written separately, using the published
     water coefficients.
   - It checks admission, and the water step bound at vesicle scale. **S:** the shrink time
     constant at 100 nm radius is about 0.2 s for Mixture 1 and 0.04 s for Mixture 3, so a 1 ms
     step stays inside the 0.05 bound.
   - Starting from the post-mixing state, here and in S2-M1, also avoids FR-10's "dose from
     nothing" limit for the permeant osmolyte.
   - It is development evidence, not acceptance.
2. **The design note for F1** (D142), then F2 and F3 through their owners' queues.
3. **F1's numerical qualification:**
   - closed forms for two-compartment exchange;
   - a Kedem–Katchalsky vesicle reference written by an agent that has not read the operator code.
4. **S2-M1 itself:** a PROPOSED protocol with criteria and tolerances, then registration, then
   one judged run. The cost is CPU minutes.

### 5.4 Why this stage first

- The system boundary is clear.
- The data are numeric and public.
- The physics is already half in the engine.
- Every feature it needs is general and has other consumers: E07-v2's osmotic challenge, FR-5,
  and secreted species.

### 5.5 Arm C: the stronger held-out test

Calibrate the composition rule on Frallicciardi et al. 2022, then predict all three Syn3A
mixtures.
- **What makes it stronger:** those are different compositions and preparations, in the same
  assay at the same temperature.
- **The descriptor:** a five-lipid mixture must be placed on a rule learned from binary
  POPC–cholesterol data. Cholesterol fraction alone may not carry over, so the descriptor is
  registered before the run.
- **A disclosure:** Presutti et al. themselves compare Mixture 1's water coefficient with
  POPC at 45% cholesterol from that study.
- It needs that source's audit, which is question 4 in §11.

## 6. The evidence inventory schema

One record per measured, derived or simulated quantity. The organism definition (§9) refers to
records by ID.

| Field | Content |
| --- | --- |
| `record_id`, `source` | DOI or accession, file, sheet or figure, and the SHA-256 of the source file |
| `organism`, `strain` | Taxon; strain with its lineage and genome accession (for example syn3.0 → syn3A → Syn3A-mCherry) |
| `target_relation` | Exact, labelled derivative, parent, other species, reconstituted system, or simulator |
| `condition` | Medium with its variant (SP4 with FBS, SP4-KO, SP4 with horse serum, a lipid diet on BSA); temperature; growth phase or time; intervention |
| `assay` | Method, instrument, and the observation model needed to compare with it (Stern–Volmer for calcein, Fick's law with an assumed area for FDA) |
| `quantity` | Name, value, unit, uncertainty and its kind (s.d. or s.e.m.), n |
| `replicate` | Biological, technical and independent-experiment counts and IDs |
| `evidence_category` | One of the five in the brief's §6 table, relative to the declared target |
| `derivation` | Measured directly; computed with listed assumptions; or fitted, with the model and the data used |
| `use` | `set` (calibration), `judge` (held out) or `context`, per milestone; never both in one milestone |
| `sampling` | How a population was sampled: time-uniform, balanced growth, or a fixed phase |
| `catalogue_ref`, `licence` | Functional unit or gene product; the licence of the value's source |

**How it fits the catalogue plan.**
- It carries the plan's abundance-field provenance: species, cell type, cycle state, condition,
  temperature, method and uncertainty.
- It carries the plan's kind of evidence per product link.
- The five categories map onto the inner model's law-declaration provenance:
  - measured (exact, related or reconstituted) → `cited`, with the record;
  - inferred or fitted → `calibrated`, with its fitting records;
  - another simulator's output is never a parameter source, only a comparison.

## 7. The external whole-cell model

- **Reference only.** It is never imported or copied, and it is not run here. That holds
  whatever its licence:
  - the repository has no licence file;
  - the Zenodo record says CC BY 4.0, a conflict recorded in the earlier review;
  - odeCELL and LAMMPS are copyleft.
- **The proposal (D138), for the user's approval, not done.**
  - At Stage 4, once Cells has a metabolism model, compare against the 50 saved count-and-flux
    traces.
  - Only that 288 MB member need be fetched, by range requests.
  - The comparison would be a model-to-model check, labelled "another simulator", and never
    validation.
- **Until then** it is pure tooling, since no Cells engine model would run (AGENTS.md).

## 8. *Mycoplasma pneumoniae* as the companion

It adds measured breadth that Syn3A lacks: RNA, protein abundance and turnover across
conditions; growth, glucose use, products and pH responses; and in-cell structural maps of
translation machinery, for the assembly layer.

Its costs:
- about 690 protein-coding genes;
- a pathogen's media;
- ATP expenditures in its literature that are model-derived and must stay separate from the
  measured fluxes, as the brief says.

None of its sources was verified in this round. Recommended: audit them in a separate round with
this schema, after S2-M1.

## 9. Organism definitions in general

An organism definition supplies data, parameters and evidence for laws the engine declares. It
never declares laws itself.

| Part | Content |
| --- | --- |
| Organism and strains | Taxon, strains with lineage, genome accession and frozen annotation version, compartments (for Syn3A, one membrane and no wall) |
| Media and conditions | Named media with composition, as far as it is defined, and temperatures |
| Law-set references | IDs from the inner model's law declarations and the operators' law IDs. Kinetics are not restated |
| Parameter sets | Values bound to declared parameters, each pointing to evidence records, with the declaration's provenance (`cited` or `calibrated`) |
| Evidence inventory | The records of §6 |
| Benchmarks | Registered held-out tests naming the records they set and judge |

**Syn3A is the first instance.** The same structure takes:
- Xenopus, the division subject;
- the mouse heart case;
- planarian;
- human, through the protein atlas.

It should live as a small versioned data set with a schema and tests. It should land with its
first consuming milestone (S2-M1), since on its own it is tooling.

## 10. Fuel: what Syn3A needs from the inner model's open question

The inner-model design asks whether fuel is the inner model's pool state or inventory rows that
reactions make and spend. Its draft recommends pool state, and the question stays open while that
note is revised for the single, restructured inner model.

**Stages 2 and 3 need no fuel.**

**Stage 4 needs:**
- **fuel made by reactions:** glycolysis by substrate-level phosphorylation, and the PTS
  spending PEP;
- **fuel spent by transporters,** ABC importers among them, by macromolecular synthesis and by
  lipid and nucleotide metabolism;
- **more than ATP, ADP and Pi:** GTP, UTP, CTP, the dNTPs and PEP;
- **one owner of each standard potential;**
- **dilution by water and a split at division.**

A pool with only a phenomenological regeneration port, closed to reaction draws, water and
partition, would not meet that. Either representation can, if those doors exist.

Recommended: the fuel decision names Syn3A Stage 4 as a registered consumer, so that both notes
meet there. It is not blocking now.

## 11. Open questions for the user, with recommendations

1. **Adopt Syn3A as the minimal-cell track, beside the electrical track?**
   - **Recommended: yes,** as a staged evidence track that opens with S2-M1.
   - This also answers the earlier review's question 5 (whether a microbe should be a Cells
     subject).
   - How it ranks against D156's working order is the user's call. Its first engine work rides
     on items already queued.
2. **Approve F1's design note** (passive neutral permeation), and ask D150 version 1.1 to cover
   water with species?
   - **Recommended: yes.** Both are general, with several consumers.
3. **Run probe P0 now?**
   - **Recommended: yes.** It is light, and it runs an engine model.
   - It is expected to run on the engine as it is. Admission of a vesicle with no channels and no
     pumps is its first check.
4. **Audit Frallicciardi et al. 2022 and fetch its experimental source data,** for arm C (§5.5)?
   - **Recommended: yes.** It is small, and it turns S2-M1's composition question into a real
     held-out test.
5. **The 4D model's outputs (D138):**
   - **Recommended: defer to Stage 4.** Fetch only the 288 MB member then.
6. **Pelletier's unreachable deposit.** Cells does not contact authors.
   - **Recommended:** decide whether you want to ask the authors through your own channels.
   - Meanwhile, use the 4D paper's Syn3B imaging counts as related-strain evidence. Do not
     digitise figures as data.
7. **Strain policy.**
   - **Recommended:** Syn3A, Syn3A-mCherry, Syn3B and the evolved clones are separate records.
   - Transfer between them only as labelled related-strain priors.
8. **Licences.**
   - **Recommended:** cite values from the CC BY-NC-ND papers (Presutti, Sandberg) in evidence
     records with attribution.
   - Copy no tables, figures or text into the public repository.
   - Keep the extracted workbooks under `/mnt/datasets`.
9. **The organism definition format.**
   - **Recommended:** land it only with S2-M1, as its first consumer, not as standalone tooling.
10. ***M. pneumoniae.***
    - **Recommended:** a separate audit round after S2-M1.

## Provenance

**Read in full:**
- the brief;
- Presutti et al. 2026, with its SI text and Fig. 3;
- Justice et al. 2024 (PMC), with Fig. 5;
- Breuer et al. 2019 (PMC): the counts, the proteomics methods and Table 1;
- Sandberg et al. 2023 (PMC);
- Gilbert et al. 2021: the methods and deposits.

**Also read:**
- Pelletier et al. 2021: abstract, key resources and data statement, from the author-hosted copy
  the brief links;
- the 4D paper's published abstract (PubMed) and its bioRxiv version list;
- the inner-model design note (read-only, as the coordinator directed).

**Metadata only:** every repository record listed in §1.

**Not read:**
- the *Cell* versions of Pelletier and Thornburg;
- the M. pneumoniae sources;
- Frallicciardi's deposits.

**Access.**
- PRIDE's API returned 404 (the data are on MassIVE).
- MassIVE FTP timed out; its HTTPS download worked.
- NCBI rate-limited one request (HTTP 429); it was retried later.
- PMC's file links returned a bot page, so the publisher's static files and eLife's API were used.

**Privacy.** Every request used a generic client name. No login, no form and no contact with
authors.
