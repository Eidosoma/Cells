# Protein identity and atlas data in Cells: path

Status: **path started, design not begun** (11 November 2026). Source:
[SOTA_REVIEW_PROTEIN_ATLAS.md](SOTA_REVIEW_PROTEIN_ATLAS.md), user-supplied.

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

## What the review gives

The review surveys the counts and the main resources. Like the GRN and division
notes, it is search-sourced and still to be verified.
- **Counts:** about 20,000 protein-coding genes (GENCODE release 50 lists 19,442) and
  172,117 annotated translations. Proteoforms may number in the millions.
- **Resources:**
  - the [Human Protein Atlas](https://www.proteinatlas.org/) (tissue, cell type,
    subcellular location, structure, interactions; RNA and protein measures differ);
  - [UniProt](https://www.uniprot.org/) (sequence, isoforms, modifications, function);
  - the [RCSB PDB](https://www.rcsb.org/) (experimental structures, including
    assemblies);
  - the [AlphaFold DB](https://alphafold.ebi.ac.uk/) (predicted structures with
    confidence);
  - [Reactome](https://reactome.org/) (curated pathways).
- **Completeness:** the 2025 Human Proteome Project report gives confident protein
  evidence for about 94% of 19,435 genes; function is a separate, open goal.
  Structures are not complete descriptions: proteins change shape, have disordered
  regions and work in assemblies.
- **Worked example:** connexin 43 (GJA1).
  - Its gap-junction channel in PDB 7Z22 contains 12 copies (two rings of six).
  - A 2026 entry, PDB 9RKX, shows Cx43 junctions in their cellular setting.
  - Counting proteins and counting molecular machines are different things.

[SCIENTIFIC_BASIS.md](SCIENTIFIC_BASIS.md) already cites the Human Protein Atlas,
with the right caveat: separate measured staining and proteomics from inferred
expression.

## What the engine models today (identities to verify)

The engine's laws act on **functional units** (an assembled channel, a pump, a
junction channel), not on single gene products. Most channel laws take BETSE
v1.5.0's coefficient sets. Where those coefficients came from, and from which
organism, still needs recording for each one.

This is a **partial first pass**, from a name search of the specs. Not yet listed:
- the calcium pumps;
- ER calcium and IP3 release;
- calcium-activated potassium channels;
- `kcc_reversible_tanh@1`;
- the T- and N-type CaV laws;
- the mitochondrial processes.

Stage 2 makes the full list.

| Engine law (examples) | Functional unit | Likely gene products (to verify) | Note |
| --- | --- | --- | --- |
| `nav1p2_m3h_regularized@1` | NaV1.2 channel | SCN2A (α), plus β subunits | BETSE coefficients |
| `kir2p1_mh2@1` | Kir2.1 channel | KCNJ2 (tetramer) | BETSE coefficients |
| `kv1p5_mh@1` and Kv1 family | Kv1.5 channel | KCNA5 (tetramer) | BETSE coefficients |
| HCN1/2/4 laws | HCN channels | HCN1, HCN2, HCN4 (tetramers) | BETSE coefficients |
| `cav1p2_m2h@1`, CaV laws | CaV1.2 and others | CACNA1C and auxiliary subunits | BETSE coefficients |
| Pump laws (for example `nak_atp_mass_action_positive@1`) | Na⁺/K⁺-ATPase | Generic: 3 Na⁺ out and 2 K⁺ in per cycle, not isoform-specific. Candidate products ATP1A1–4 with ATP1B1–3 (αβ, optional FXYD) | Assigning an isoform would be a new claim |
| `k_anion_symport_mass_action@1` | KCC-type K⁺–anion symport (1:1, a Cl-like anion; capacity set from red cells) | Generic KCC-type. Candidate products SLC12A4–7 (KCC1–4) | Mass-action law, volume-activated; isoform not assigned |
| `junction_voltage_relaxation@1` | Gap-junction channel | Generic | Its source says **no connexin catalog or biological fit is implied**. Labelling it "Cx43" would be a new claim, not a relabel |
| Leak laws | Background conductances | Unassigned | Not protein-specific |
| Capsid assembly ([CAPSID_ASSEMBLY.md](CAPSID_ASSEMBLY.md)) | Protein cage | Prescribed contact graph | The first D140 assembly case |

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

## Licences (to check before copying any values)

Read each resource's terms, and Cells' own licence, before copying data into the
public repository. Some may be share-alike, the Human Protein Atlas in particular,
which would bind redistributed data. Storing accessions, links and our own cited
statements avoids most of the question. Bulk copying of atlas data is not planned.

## Stages

1. **Verify the facts carried over:**
   - the GENCODE release 50 counts;
   - the proteome-project figure;
   - PDB 7Z22 and 9RKX (one is dated 2026);
   - each resource's licence.
2. **Inventory and mapping.** For every functional unit the engine models: gene
   products with accessions and isoforms, stoichiometry, the source model and its
   organism, and the law and parameter set that represent it.
   - **Worked case: the connexin channel.** Cx43 (GJA1) and 7Z22's 12-mer. The
     engine's junction law stays "generic gap-junction channel" until a
     connexin-specific law is cited and qualified.
3. **Design note** (D142), after the cell-division design note is reviewed, so the
   two agree on membrane domains:
   - the entity and its fields;
   - the stoichiometry link;
   - evidence records;
   - the hook into membrane-domain populations;
   - bitwise-off checks.
4. **Implementation:** catalogue schema, loader and tests.
   - It comes with the first engine model that consumes it, for example abundance as
     state in the division or trafficking work.
   - A metadata-only catalogue would run no engine model, so under AGENTS.md it
     counts as tooling and needs the user's explicit approval on its own.
5. **Data tooling** (ingesting from the UniProt or Human Protein Atlas APIs). This is
   tooling and needs the user's approval.

## Non-goals

- A proteome-wide import.
- Protein folding (D140).
- Training models on atlas data.
- Inferring abundance or kinetics from expression levels.
