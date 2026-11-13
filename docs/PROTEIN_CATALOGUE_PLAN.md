# Protein identity and atlas data in Cells: path

Status: **stages 1 and 2 done, design not begun** (12 November 2026). Source:
[SOTA_REVIEW_PROTEIN_ATLAS.md](SOTA_REVIEW_PROTEIN_ATLAS.md), user-supplied.
Evidence: `/mnt/workspaces/Cells/protein-catalogue-20261111-01/`
(`stage1_verification.md`, `law_inventory_v2.json`, saved sources and lookup inputs).

**What "design this in" is taken to mean (the user can redirect this).** Cells gets a
small, curated, versioned **molecular catalogue**. It gives each protein population
the engine models a stable identity, linked to the public atlases:
- the gene products and their accessions;
- assembly stoichiometry;
- where the protein occurs (organism, cell type, membrane or organelle);
- structures and pathways;
- where each engine parameter came from.

The catalogue is metadata. It does not change the physics. It is not a
proteome-wide import, not AI training, and not protein folding, which D140 skips.

## What the review gives (verified in stage 1)

The review surveys the counts and the main resources. Stage 1 checked its facts at
the primary sources; corrections are marked.
- **Counts:** about 20,000 protein-coding genes. GENCODE release 50 (June 2026) lists
  19,442 (readthrough genes excluded) and 172,117 distinct translations. Proteoforms
  may number in the millions.
- **Resources:**
  - the [Human Protein Atlas](https://www.proteinatlas.org/) (tissue, cell type,
    subcellular location, structure, interactions; RNA and protein measures differ).
    Version 26.0 shows AlphaFold-generated structures for 19,904 proteins with 83,795
    isoforms (clarified: 19,904 counts proteins; the isoforms are extra);
  - [UniProt](https://www.uniprot.org/) (sequence, isoforms, modifications, function);
  - the [RCSB PDB](https://www.rcsb.org/) (experimental structures, including
    assemblies);
  - the [AlphaFold DB](https://alphafold.ebi.ac.uk/) (predicted structures with
    confidence);
  - [Reactome](https://reactome.org/) (curated pathways).
- **Completeness:** the 2025 Human Proteome Project report (J Proteome Res, February
  2026) detects 93.6% (about 94%) of a 19,435-protein reference set. That set is built
  on GENCODE v48, so it is not the release-50 count. Function is a separate, open goal.
  Structures are not complete descriptions: proteins change shape, have disordered
  regions and work in assemblies.
- **Worked example:** connexin 43 (GJA1, UniProt P17302).
  - PDB 7Z22's assembly is 12 copies of Cx43 with D6 symmetry: two hexameric
    hemichannels. It is recombinant Cx43 in nanodiscs, and only about half of each
    chain is modelled; the C-terminal domain is missing.
  - PDB 9RKX was released in April 2026. Corrected scope: the entry is one 12-mer (7Z22
    fitted as a rigid body) in a 14 A in situ map from HEK293 cells. The plaque
    lattice is in the paper and its EM map, not in the PDB model.
  - Counting proteins and counting molecular machines are different things.

[SCIENTIFIC_BASIS.md](SCIENTIFIC_BASIS.md) already cites the Human Protein Atlas,
with the right caveat: separate measured staining and proteomics from inferred
expression.

## What the engine models today (stage 2 inventory)

The engine's laws act on **functional units** (an assembled channel, a pump, a
junction channel), not on single gene products. The full inventory is
`/mnt/workspaces/Cells/protein-catalogue-20261111-01/law_inventory_v2.json`
(`cells.protein_catalogue.law_inventory@2`, source fec863f). For every law it records
the file and docstring, the unit, candidate products with human and Xenopus laevis
UniProt accessions and isoforms, the assembly and its source, the coefficient source
with the published model behind it, the kind of evidence, the parameter set, and a
status. It accounts for every row of the first pass. A census buckets all 778
versioned identifiers in `src/cells`, so none is left unreviewed.

**Counts.**
- 80 laws: 78 with ID constants, and two functions of the nominal `emt_mirna_pair@1`
  profile.
- One assembly model.
- 49 functional units.
- Laws by status: 41 assigned in source, 7 candidate, 32 generic.
- The 41 assigned laws by evidence:
  - 12 expressed isoforms;
  - 6 with the isoform named only in the cited title;
  - 4 native currents;
  - 2 neuron models;
  - 12 Morris-Lecar reductions;
  - 5 whose BETSE citation gives no detail.
- 93 candidate genes, 81 of them with a Xenopus laevis UniProt entry. Auxiliary
  subunits are listed as whole families, because no source pairs them.

**Status.**
- **Assigned in source:** the law, its docs or its cited source names the product.
- **Candidate:** the law models a named native current or channel class, and the
  gene mapping is our inference.
- **Generic:** the law is deliberately generic, phenomenological or manufactured.
  Products are listed as candidates only.

| Functional unit | Engine laws | Products (human UniProt) | Assembly (source) | Coefficients from | Status |
| --- | --- | --- | --- | --- | --- |
| NaV1.2, NaV1.3, NaV1.6 | `nav1p2_m3h_regularized@1`, `nav1p3_m3h_regularized@1`, `nav1p6_persistent_m@1`, `nav_ml_instantaneous@1` | SCN2A Q99250, SCN3A Q9NY46, SCN8A Q9UQD0; beta SCN1B-SCN4B | 1 alpha + beta (PDB 6J8E) | BETSE; NaV1.2 from rat neocortical neurons (Hamill 1991, a native current) | assigned (label) |
| Native neuronal Na | `navrat1/2/3_m3h_regularized@1` | SCN1A, SCN2A, SCN3A, SCN8A (inference) | as above | BETSE; rat neocortex (Huguenard 1988), thalamocortical model (McCormick 1992) | candidate |
| Kv1.1-Kv1.6 | `kv1p1_mh2@1`, `kv1p2_mh@1` ... `kv1p6_mh@1`, `kv1p5_mh@1`, three Kv1 Morris-Lecar laws | KCNA1-KCNA6 (KCNA5 P22460); KCNAB1-3 | 4 alpha + 4 beta (PDB 2A79, rat) | BETSE; mostly cloned channels, e.g. human Kv1.5 in Xenopus oocytes (Philipson 1991) | assigned |
| Kv2.1-2.2, Kv3.1-3.4 | `kv2p1_mh@1`, `kv2p2_mh@1`, `kv2p1_ml_dynamic_m@1`, `kv3p1_m@1`, `kv3p2_m2@1`, `kv3p3_m2h_long_tau@1`, `kv3p4_mh@1` | KCNB1-2, KCNC1-4 | 4 alpha (UniProt; PDB 7PHH) | BETSE | assigned |
| Fast A-type K | `k_fast_mh@1` | KCND2, KCND3 (inference) | 4 alpha + KChIP | BETSE; rat L5 pyramidal neurons (Korngreen & Sakmann 2000) | candidate |
| Kir2.1 | `kir2p1_mh2@1`, `kir_ml_instantaneous@1` | KCNJ2 P63252 | 4 alpha (PDB 7ZDZ) | BETSE (Makary 2005) | assigned |
| HCN1, HCN2, HCN4 | `hcn1_m@1`, `hcn2_m@1`, `hcn4_m@1`, `hcn2_camp_m@1`, `hcn4_camp_m@1`, two HCN Morris-Lecar laws | HCN1 O60741, HCN2 Q9UL51, HCN4 Q9Y3Q4 | 4 alpha (PDB 5U6O; 7NP3 rabbit) | BETSE (Moosmang 2001) | assigned |
| HVA CaV1.2, 1.3, 2.1, 2.2, 2.3 | `cav1p2_m2h@1`, `cav1p3_m2h@1`, `cav2p1_m@1`, `cav2p2_m2h_regularized@1`, `cav2p3_mh@1`, three CaV Morris-Lecar laws | CACNA1C Q13936, CACNA1D, CACNA1A, CACNA1B, CACNA1E; CACNB1-4, CACNA2D1-4 | alpha1 + beta + alpha2delta, 1:1:1 (PDB 7MIY) | BETSE; mostly native currents (mouse motoneurons, CA3 neurons, cat retinal ganglion cells) | assigned (label) |
| T-type CaV3.1, 3.3 | `cav3p1_mh_piecewise_tau_m@1`, `cav3p3_mh@1`, `cav_t_ml_instantaneous@1` | CACNA1G O43497, CACNA1I Q9P0X4 | alpha1 alone (PDB 6KZO) | BETSE (Traboulsie 2007, expressed) | assigned |
| Native L-type and HVA Ca | `ca_l2_m2h@1`, `ca_l3_shift15_m2h@1`, `cav_g_m2h_regularized@1` | CACNA1C, CACNA1D (others for Cav_G; inference) | as HVA | BETSE, modified Avery 1996; Reuveni 1993 | candidate |
| Ca-activated K | `cagpotassium_numeric_mM_scale@1` | KCNMA1 Q12791 (cited model) or KCNN1-3 (BETSE label) | BK: 4 alpha (PDB 6V38) | BETSE legacy function; Cox, Cui & Aldrich 1997 (BK clone mslo) | generic: BETSE says "SK" but cites a BK model |
| Leaks, defaults, lumped permeabilities | six always-open leaks, `hcn_leak_open@1`, `kv_ml1_dynamic_m@1`, `constant_field@1`, `neutral_mobile_leak@1`, `ideal_osmosis_linear_compliance_water@1` | none | none | BETSE leak classes; constant-field flux; ideal osmosis | generic |
| Gap-junction channel | `junction_voltage_relaxation@1`, `symmetric_opposing_relaxation@1`, `delayed_first_order_junction_formation@1` | connexins as candidates, e.g. GJA1 P17302 | 2 connexons x 6 (PDB 7Z22) | BETSE rates from axolotl blastomeres (Harris 1983), no connexin identified; synthetic gate; cited plaque studies | generic |
| Cx45/Cx45, Cx40/Cx37 channels | gate tables of `junction_flux()` in the nominal `emt_mirna_pair@1` profile | GJC1 P36383; GJA5 P36382 + GJA4 P35212 | 2 x 6 | Chen-Izu et al. 2001 Table 1 (values match exactly) | assigned in source |
| Na+/K+-ATPase | `nak_atp_mass_action_positive@1`, `nak_atp_affinity_tanh@1`, nominal profile pump | ATP1A1-4 (ATP1A1 P05023), ATP1B1-3, FXYD | alpha:beta:FXYD 1:1:1 (PDB 7E1Z); 3 Na out, 2 K in | BETSE pump form; BETSE's default Km values carry an uncited "alpha1" comment | generic |
| PMCA | `plasma_calcium_pump_positive@1`, `ca_atp_mass_action_positive@1`, `finite_atp_pmca_positive@1` | ATP2B1-4 (ATP2B1 P20020); NPTN, BSG | 1:1 with neuroplastin (PDB 6A69); 1 Ca per ATP | BETSE | generic |
| ER Ca pump | `er_calcium_pump_positive@1`, `finite_atp_er_1ca_positive@1` | ATP2A1-3 (ATP2A2 P16615) | monomer (PDB 1SU4, rabbit); the law moves 1 Ca, SERCA moves 2 | BETSE | generic |
| NCX | `ncx_3na_1ca_symmetric_barrier@1` | SLC8A1-3 (SLC8A1 P32418) | monomer (PDB 8SGJ); 3 Na : 1 Ca | synthetic; Hilgemann 1992 for 3:1 | generic |
| ER Ca release (IP3R-like) | `er_calcium_release@1`, `ip3_er_release@1` | ITPR1-3 (ITPR1 Q14643); RYR1-3 | tetramer (PDB 6DQJ) | BETSE ER channel; synthetic values | generic |
| KCC, NKCC | `kcc_reversible_tanh@1`, `k_anion_symport_mass_action@1`, `nkcc_reversible_tanh@1` | SLC12A4-7 (SLC12A4 Q9UP95); SLC12A2 P55011, SLC12A1 | homodimer (PDB 6KKR, 6PZT); 1 K : 1 Cl; 1 Na : 1 K : 2 Cl | manufactured; red-cell data for the volume-activated law (Lew 1991) | generic |
| Declared transporter | `cell_zone_transporter@1`, `electroneutral_symport_reversible_tanh@1` | per configuration | per route | BETSE transporter-network equations; manufactured kernel | generic |
| Mitochondrial permeability | `mitochondrial_passive_continuous_si@1` | none (MCU complex only as a future candidate) | MCU uniplex 4:4:1:1 (PDB 6WDN) | BETSE component | generic |
| Protein cage (D140) | `capsid_graph@1`, `finite_bond_assembly@1` (models) | engineered mi3 cage, no natural gene | 20 trimers ([CAPSID_ASSEMBLY.md](CAPSID_ASSEMBLY.md)) | Asor et al. 2026 | assigned (designed protein) |

**Rule kept: a generic law stays generic.**
- The pump law is a generic 3 Na out / 2 K in Na+/K+-ATPase, not an isoform.
- `junction_voltage_relaxation@1` implies no connexin catalogue or biological fit.
- Labelling either with a product is a new claim, so products are listed only as
  candidates.

**Findings that matter for the design.**
- **"Assigned in source" usually means a BETSE label.** Several isoform-named laws
  rest on native-current data, for example NaV1.2, CaV1.2, CaV1.3 and CaV2.2. BETSE
  labels the same Carlin et al. model CaV1.2 in one class and CaV1.3 in another. The
  catalogue must record the label and the kind of evidence separately: expressed
  isoform, native current or model.
- **Xenopus coverage is uneven.** A gene-name search found no Xenopus laevis UniProt
  entry for twelve candidate genes, among them HCN2, HCN4, SCN2A, SCN8A and ITPR3.
- **The only connexin-assigned junction law is a compatibility profile.** It belongs
  to the nominal `emt_mirna_pair@1` profile (Cx45/Cx45 and Cx40/Cx37). There is
  none for Cx43.
- **Abundance as state already exists in two places.** The mobile leak and Na+/K+-ATPase
  populations (`resolved_redistribution@1/@2`) hold membrane amounts per patch, and
  junction formation acts on channel abundance. These are natural first consumers of
  a catalogue reference.

### Worked case: the connexin channel

- **Assembly:** connexon = 6 x Cx43 and channel = 2 connexons, from PDB 7Z22 (12 x
  P17302, D6) and UniProt's subunit note.
- **Products:** human GJA1 is P17302. Xenopus laevis has P16863 (gja1, reviewed) and
  A0A1L8G2N0 (gja1.S).
- **The engine law stays generic.** `junction_voltage_relaxation@1` comes from
  BETSE's rates, which cite axolotl blastomere junctions (Harris, Spray and Bennett
  1983) with no connexin identified.

Before the engine could claim a Cx43 channel, it needs:
1. a new versioned law or parameter-set identity naming the pairing (homotypic Cx43),
   not a relabel;
2. cited Cx43 values with organism, expression system and temperature:
   - steady-state Gj-Vj: Chen-Izu et al. 2001 Table 1 gives one set, from N2A cells;
   - fast and slow gating kinetics;
   - residual-state selectivity;
   - a unitary conductance, if channel counts set conductance;
3. cited evidence of which connexins Xenopus cleavage-stage blastomeres express;
4. the catalogue link (2 x 6 GJA1), with heterotypic and heteromeric channels as
   separate units;
5. channels per junction held as state, consistent with junction formation;
6. independent reference checks, comparison with the cited data within a stated
   tolerance, tier tests and bitwise-off checks, behind a D142 design note.

## What the atlases can and cannot supply

**They can supply:**
- identity (gene, isoform, accession);
- presence and location by tissue, cell type and compartment;
- partners and complex membership;
- assembly stoichiometry and geometry, for the assembly layer (D140);
- pathway membership, for the gene-regulation layer.

**They cannot supply:**
- kinetics and gating;
- single-channel conductance;
- copy number per cell, or turnover rates.

An expression level is not an abundance. Those quantities come from primary
measurements: electrophysiology, quantitative proteomics with absolute copy
numbers, and [BioNumbers](https://bionumbers.hms.harvard.edu/aboutus.aspx). Each
value keeps its own provenance.

**Organisms.** The Human Protein Atlas is human-only. Xenopus and C. elegans, the
cell-division subjects, need other sources: UniProt covers many organisms, and
Xenbase and WormBase are the model-organism databases.

## Architecture constraints (for the design note, D142)

1. **Two linked levels.** The functional unit is what the engine law acts on. Gene
   products are what atlases index. The catalogue links them through stoichiometry,
   for example connexon = 6 × Cx43 and junction channel = 2 connexons. This is the
   D140 ladder.
2. **Membrane abundance as state.** A membrane domain holds populations of identified
   functional units, each with its own abundance. The
   [cell-division design note](CELL_DIVISION_DESIGN.md) defines this: each population
   declares a `functional_unit` ID and an opaque `catalogue` reference into this
   catalogue.
3. **Physics unchanged.** Identity metadata must leave every trajectory bitwise
   unchanged.
4. **Offline and versioned.**
   - The catalogue is a small, curated, versioned file in the repository, with a
     schema and tests.
   - There is no network access at run time.
   - The "species definition" row of the ownership table on the
     [architecture page](MULTISCALE_EXECUTION_ARCHITECTURE.md) gains a reference into
     the catalogue.
5. **One catalogue, many users.** It serves the gaps already listed rather than
   opening a parallel track:
   - membrane abundance as state;
   - Golgi and membrane trafficking (roadmap item 9), which delivers units to
     membrane domains;
   - the gene-regulation layer ([GRN track](GRN_WETLAB_VALIDATION.md); Arc data are
     gene-level);
   - the assembly layer (stoichiometry and contact graphs from structures);
   - cell division (the composition of new membrane domains).
6. **Evidence kind and licence per value.**
   - Each product link records the kind of evidence: a label only, an expressed
     isoform, a native current or a model.
   - Each copied value records its source and licence.

## Licences (checked in stage 1)

Cells is MIT. Values copied into the public repository must allow commercial use, and
their attribution terms travel with them.

| Resource | Terms (12 November 2026) | Consequence |
| --- | --- | --- |
| Human Protein Atlas | CC BY 4.0, **not share-alike** (corrected) | Cite the atlas and versioned URLs. Third-party subsets keep their own terms: AlphaFold 3 models are CC BY-NC-SA; IUPHAR, TCDB and Metabolic Atlas are CC BY-SA. Do not copy those. |
| UniProt | CC BY 4.0 | Cite the UniProt release. |
| RCSB PDB | CC0 for archive and API data | Attribution to authors encouraged. |
| AlphaFold DB | CC BY 4.0 | Cite the database paper. |
| Reactome | Data CC0; illustrations CC BY 4.0 | None for data. |
| Xenbase | Research and education only; commercial use needs written permission | **Do not copy Xenbase data.** Store accessions, Xenbase IDs from UniProt cross-references, links and our own cited statements. |
| WormBase | Site refused automated reading; its papers say public domain | Read the terms by hand before the C. elegans subject uses them. |

A catalogue file holding CC BY values needs a data notice that lists the sources.
Storing accessions, links and our own cited statements avoids most of the question.
Bulk copying of atlas data is not planned.

## Stages

1. **Verify the facts carried over.** **Done** (12 November 2026),
   `stage1_verification.md`.
   - The counts stand, with releases stated.
   - HPA is CC BY.
   - 9RKX's scope is corrected.
   - Xenbase is non-commercial.
   - WormBase is unverified.
2. **Inventory and mapping.** **Done** (12 November 2026), `law_inventory_v2.json`
   and the table above.
   - It covers 80 laws and 49 functional units.
   - The connexin worked case leaves the junction law generic.
3. **Design note** (D142), after the cell-division design note is reviewed, so the
   two agree on membrane domains:
   - the entity and its fields, including the kind of evidence and the licence per
     value;
   - the stoichiometry link;
   - evidence records;
   - the hook into membrane-domain populations; the mobile pump and leak populations
     are the obvious first consumers;
   - bitwise-off checks;
   - **an abundance field** (user decision, 13 November 2026). It holds measured evidence
     with provenance: copies per assembled structure, any functional threshold, species,
     cell type, cycle state, condition, temperature, method, uncertainty and fluorophore
     artefacts. [Hirano et al. 2026](PAPER_REVIEW_KINETOCHORE_COUNTS.md) is the model
     record. Engine abundance stays state with one owner; the catalogue field is evidence.
     Stage 3 itself stays held under D145 until its slot.
4. **Implementation:** catalogue schema, loader and tests.
   - It comes with the first engine model that consumes it, for example abundance as
     state in the division or trafficking work.
   - A metadata-only catalogue would run no engine model, so under AGENTS.md it
     counts as tooling and needs the user's explicit approval on its own.
5. **Data tooling** (ingesting from the UniProt or Human Protein Atlas APIs). This is
   tooling and needs the user's approval.
   - It must skip Xenbase data and HPA's share-alike and non-commercial subsets.

## Non-goals

- A proteome-wide import.
- Protein folding (D140).
- Training models on atlas data.
- Inferring abundance or kinetics from expression levels.
