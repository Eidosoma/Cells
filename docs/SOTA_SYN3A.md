**For Cells, I would choose JCVI-syn3A as the first whole-cell validation organism. It has roughly 450 different protein types and an unusually useful collection of public experimental measurements.** It offers the best combination I found of a small protein repertoire, growth without a living host, and data covering molecular composition, membranes, growth, and division.

The canonical reference describes **452 protein-coding genes, 493 genes in total, and a chromosome of about 543,000 base pairs**. Some newer modeling papers use 455 proteins, so an implementation should freeze a specific annotation and protein list. [JCVI](https://www.jcvi.org/publications/essential-metabolism-minimal-cell?utm_source=chatgpt.com)

I’m interpreting “least amount of proteins” as **fewest distinct protein types**. That is different from the total number of protein molecules inside a cell: each type can have many copies.

My recommendation has two parts:

- **JCVI-syn3A as the main minimal-cell target.**
- **Mycoplasma pneumoniae as a companion organism where we need a broader range of measured mechanisms.**

## 1. The main candidates

| Organism | Approximate encoded protein types | What makes it useful | My assessment for Cells |
|---|---:|---|---|
| **JCVI-syn3.0** | **438** | Extremely small genome; can grow in rich medium without a living host. Its irregular morphology and division are themselves informative. | Best smaller comparison strain, especially for testing division defects. |
| **JCVI-syn3A** | **About 450** | More regular growth and division, quantitative proteomics, gene-essentiality experiments, imaging, membrane perturbations, and whole-cell models. | **Best primary choice.** |
| **Mycoplasma genitalium G37** | **About 480 in the classic reference annotation** | Historical whole-cell model and useful experimental gene-disruption growth data. | Valuable additional perturbation benchmark. |
| **Mycoplasma pneumoniae M129** | **About 700** | Particularly rich systems-biology measurements: RNA, protein abundance and turnover, metabolism, interactions, and cellular structures. | **Best companion when experimental coverage takes priority over the smallest protein count.** |
| **E. coli** | **More than 4,000** | Exceptionally broad experimental literature and public quantitative datasets. | Excellent for individual mechanisms, but a much larger first whole-cell target. |

These counts depend on the strain and annotation. The Syn3.0 count is reaffirmed in a 2026 paper; the classic *M. genitalium* annotation has 482 protein-coding genes, while foundational *M. pneumoniae* studies use approximately 689–690. [journals.asm.org](https://journals.asm.org/doi/full/10.1128/msphere.00077-26?utm_source=chatgpt.com)

### There are organisms with far fewer encoded proteins—but they change the problem

A 2026 study describes an insect endosymbiont, **Vidania**, with as few as **62 identified protein-coding genes**. These bacteria live within an elaborate host-dependent system, and the paper notes still smaller gene sets in complementary *Hodgkinia* lineages. They are therefore poor candidates for a simple, independently growing cell model. [nature.com](https://www.nature.com/articles/s41467-026-69238-x?utm_source=chatgpt.com)

The practical distinction is **how much biology sits outside the genome you are counting**. If essential functions are supplied by a host or another organism, a smaller genome can leave you with a more complicated simulation boundary.

For Cells, I would optimize for:

> **The smallest experimentally tractable cellular system whose dependencies we can explicitly represent.**

Syn3A is a strong answer to that question.

## 2. Why Syn3A is worth choosing over the slightly smaller Syn3.0

The main advantage is that **Syn3A gives us a more regular reference phenotype, while Syn3.0 provides an informative failure case**.

The 2021 division study compared these cells and examined which restored genes improved their morphology. It identified seven genes that jointly restored a phenotype resembling the larger parental cell, including the known division genes **ftsZ** and **sepF**. That gives us an unusually useful causal question: can a model explain how changing the molecular inventory changes division and shape? [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/33784496/?utm_source=chatgpt.com)

The molecular measurements are also substantial. The 2019 proteomics study detected **428 of the 452 reference protein types—about 95%**. That does not establish every protein’s function or kinetic behavior, but it provides a strong experimentally grounded inventory. The same work supplies transposon-based gene-essentiality measurements and a metabolic reconstruction. [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC6609329/?utm_source=chatgpt.com)

Its physical organization is attractive for Cells: mycoplasmas have **a single surrounding membrane and no cell wall**. However, they depend heavily on externally supplied nutrients and lipids. The growth medium must therefore be part of the model definition, alongside the cell itself. [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC13631282/?utm_source=chatgpt.com)

That fits the direction of Cells we have been discussing: a shared material inventory connecting transport, reactions, functional machinery, energy expenditure, growth, and division.

**Building this would still require an organism-specific model on top of Cells’ general machinery.** The protein list alone does not supply the transport laws, enzyme kinetics, assembly rules, or division mechanics.

## 3. Public wet-lab evidence we can actually build from

I found the following useful evidence families. The links identify public records or published data deposits; I have not yet downloaded and audited every underlying file.

| Evidence | What was measured | Public starting point | What it could test in Cells |
|---|---|---|---|
| **Proteomics and gene essentiality, 2019** | Protein abundances and tolerance of gene disruption. | [Breuer et al., *Essential metabolism for a minimal cell*](https://doi.org/10.7554/eLife.36842); proteomics **MSV000081687 / [PXD008159](https://proteomecentral.proteomexchange.org/cgi/GetDataset?ID=PXD008159)**. | Molecular inventories, resource allocation, and effects of removing particular functions. [elifesciences.org](https://elifesciences.org/articles/36842v1?utm_source=chatgpt.com) |
| **Division and morphology, 2021** | Cell propagation in microfluidic devices, size and shape, and genetic changes that restore division phenotypes. | [Pelletier et al.](https://doi.org/10.1016/j.cell.2021.03.008); [Mendeley data, analysis code, and videos](https://doi.org/10.17632/rwg6sdz4rf.1). | Genotype-to-phenotype predictions, division behavior, and cell-size distributions. [cba.mit.edu](https://cba.mit.edu/docs/papers/21.03.Cell.pdf?utm_source=chatgpt.com) |
| **Cell architecture and chromosome contacts, 2021** | Cryo-electron tomography, ribosome locations, and chromosome-contact measurements. | Raw images: [EMPIAR-10685](https://www.ebi.ac.uk/empiar/EMPIAR-10685/) and [EMPIAR-10686](https://www.ebi.ac.uk/empiar/EMPIAR-10686/); [3C sequencing deposit](https://doi.org/10.4121/14333618). | Spatial organization, crowding, ribosome distribution, and chromosome constraints. [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC8339304/?utm_source=chatgpt.com) |
| **Adaptation, growth, and RNA expression, 2023** | Evolved Syn3A lineages, changes in growth, mutations, and RNA expression. | [Sandberg et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC10448532/); [GEO GSE205017](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE205017), including processed expression files and links to sequencing data. | Responses to changed genotype and gene expression. [ncbi.nlm.nih.gov](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE205017\&utm_source=chatgpt.com) |
| **Living-cell membrane perturbations, 2024** | Growth on controlled lipid diets, membrane composition, permeability, and sensitivity to osmotic shock. | [Justice et al.](https://doi.org/10.1038/s41467-024-53975-y); paper source-data workbooks; [processed lipidomics](https://doi.org/10.5281/zenodo.13817894); [TEM images](https://doi.org/10.6019/S-BSST1651). | Coupling between membrane composition, transport, osmotic stability, and growth. [nature.com](https://www.nature.com/articles/s41467-024-53975-y?utm_source=chatgpt.com) |
| **DNA replication measurements associated with the 2026 whole-cell model** | DNA sequencing used to constrain chromosome replication. | [2026 Cell paper](https://doi.org/10.1016/j.cell.2026.02.009); BioProject [PRJNA1257452](https://www.ncbi.nlm.nih.gov/bioproject/PRJNA1257452). | Replication state and DNA-copy relationships. [doi.org](https://doi.org/10.1016/j.cell.2026.02.009?utm_source=chatgpt.com) |
| **Reconstituted membrane measurements, 2026** | Water and osmolyte permeability and physical properties of membranes resembling Syn3A’s lipid composition. | [Presutti et al.](https://doi.org/10.1038/s41467-026-77359-6); paper source data; [Zenodo supporting archive](https://zenodo.org/records/20613506). | Passive membrane transport and membrane biophysics at the component level. These experiments use reconstructed membranes. [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC13631282/?utm_source=chatgpt.com) |

A few details matter when turning these into benchmarks:

**The 2024 lipid experiments are particularly relevant to Cells.** They connect changes in membrane composition to several measurable outcomes in living Syn3A cells. The public processed lipidomics and source data are useful, but the authors explicitly state that the raw lipidomics instrument files were not deposited because of the provider’s proprietary restrictions. [nature.com](https://www.nature.com/articles/s41467-024-53975-y?utm_source=chatgpt.com)

**The microscopy and chromosome resources contain both observations and reconstructions.** The cell boundaries and ribosome locations come from imaging; individual modeled chromosome paths are generated configurations constrained by experiments. Those two kinds of evidence should retain separate labels. [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC8339304/?utm_source=chatgpt.com)

**Strain identity needs to travel with every measurement.** Syn3.0, Syn3A, Syn3B, parental *M. mycoides*, and labeled derivatives should have separate records. Related strains can inform a model, but combining them into a single supposedly measured cell would conceal meaningful biological differences.

## 4. There is already a serious whole-cell modeling baseline

This is another reason to choose Syn3A: we would have a substantial reference implementation and a route back to the experiments used to construct it.

The 2022 paper **[Fundamental behaviors emerge from simulations of a living minimal cell](https://doi.org/10.1016/j.cell.2021.12.025)** established an integrated dynamical model. Its parameterization illustrates an important validation issue: promoter strengths were estimated using protein-abundance measurements, so recovering those abundances is partly a consistency check on the fitted model. [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC9985924/?utm_source=chatgpt.com)

The March 2026 paper **[Bringing the genetically minimal cell to life on a computer in 4D](https://doi.org/10.1016/j.cell.2026.02.009)** extends this to spatial simulation of an approximately 100-minute cell cycle, connecting genetic processes, metabolism, growth, and division. Public resources include:

- [Minimal_Cell_4DWCM on GitHub](https://github.com/Luthey-Schulten-Lab/Minimal_Cell_4DWCM).
- [The archived code and simulation data](https://doi.org/10.5281/zenodo.15579158).

The archive includes molecular-count and flux trajectories for 50 simulated cells, plus representative spatial trajectories. Those are useful comparison outputs, with a different evidential role from the experimental datasets. [doi.org](https://doi.org/10.1016/j.cell.2026.02.009?utm_source=chatgpt.com)

The authors also identify unfinished mechanisms. In particular, a kinetic model of FtsZ-driven division remains absent, and chromosome partitioning uses an imposed geometric constraint. Their 50 spatial cell-cycle simulations required approximately **15,000 A100 GPU-hours**. [doi.org](https://doi.org/10.1016/j.cell.2026.02.009?utm_source=chatgpt.com)

For Eidosoma, that suggests a concrete contribution:

**A reusable simulation engine that connects physical accounting to biological predictions, with enough efficiency to test many conditions and perturbations.**

We can use the existing models to locate assumptions, compare implementations, and identify missing mechanisms. Biological validation would then come from experiments reserved from fitting.

The same distinction applies to protein structures and functional annotations. Even the minimal cells retain incompletely understood proteins; recent assignments often come from computational inference. A plausible structural or functional prediction is useful input, but its experimental status should remain visible. [journals.asm.org](https://journals.asm.org/doi/full/10.1128/msphere.00077-26?utm_source=chatgpt.com)

## 5. Why I would also use *M. pneumoniae*

If you prioritize **the breadth of public wet-lab evidence**, *M. pneumoniae* becomes very attractive despite its larger repertoire of about 700 proteins.

A 2016 study assembled **1,748 consistently generated multiomics datasets**, spanning RNA, proteins, interactions, modifications, metabolites, and essentiality. That number refers to datasets in an integrated resource, not 1,748 independent validation experiments, but it shows the depth of coordinated work on this organism. [academic.oup.com](https://academic.oup.com/nar/article/44/3/1192/2503077?login=false\&utm_source=chatgpt.com)

Three areas are especially useful for Cells.

### Protein production and turnover

The study **[Quantification of mRNA and protein and integration with protein turnover in a bacterium](https://doi.org/10.1038/msb.2011.38)** measures RNA abundance, protein abundance, and protein turnover under different conditions.

These are valuable for checking whether a model correctly connects molecular production, degradation, and accumulation. The study also examines abundance relationships among proteins belonging to the same complexes. [Springer Nature Link](https://link.springer.com/article/10.1038/msb.2011.38?utm_source=chatgpt.com)

For Cells’ assembly ambitions, this helps distinguish several questions:

- Are the required subunits present?
- Are their amounts compatible with the proposed complexes?
- Does the model account for synthesis and replacement?
- Does the resulting functional machinery produce the measured response?

Those questions require different evidence, even when they concern the same protein.

### Energy, transport, and pH

**[Dissecting the energy metabolism in Mycoplasma pneumoniae through genome-scale metabolic modeling](https://doi.org/10.1038/msb.2013.6)** combines measurements of growth, glucose use, metabolic products, and responses to medium pH.

This is a particularly good companion for Cells’ energy and transport work. The useful experimental targets are the measured consumption, production, and growth responses. The paper’s estimates of how much ATP goes to maintenance or proton pumping are model-derived quantities, with fitted or transferred parameters. [Springer Nature Link](https://link.springer.com/article/10.1038/msb.2013.6?utm_source=chatgpt.com)

I would preserve that distinction in the benchmark data: **measured glucose consumption** and **inferred ATP expenditure** should never become interchangeable fields.

### Molecular machinery inside real cells

A September 2026 Cell paper, **[Single-cell visual proteomics of a minimal bacterium reveals structural coordination of gene expression machineries](https://doi.org/10.1016/j.cell.2026.08.054)**, reports **140 structural maps** from native and antibiotic-perturbed *M. pneumoniae* cells, covering different states of translation machinery. [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/42790420/?utm_source=chatgpt.com)

A verified public example is **[EMD-53631](https://www.ebi.ac.uk/emdb/EMD-53631)**, a map of a ribosomal large subunit during biogenesis in native cells. The archive provides the map and experimental metadata. [ebi.ac.uk](https://www.ebi.ac.uk/emdb/EMD-53631?utm_source=chatgpt.com)

This makes *M. pneumoniae* especially useful for the molecular-assembly side of Eidosoma’s work.

### Where *M. genitalium* and *E. coli* help

*M. genitalium* offers a useful additional perturbation dataset: **experimentally measured growth rates for 86 viable single-gene disruption strains**, published in **[Accelerated discovery via a whole-cell model](https://doi.org/10.1038/nmeth.2724)**. That is attractive for testing whether a model predicts the consequences of removing a function. [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC3856890/?utm_source=chatgpt.com)

*E. coli* provides much broader condition coverage. For example, one quantitative proteomics resource measures **more than 2,300 proteins across 22 conditions**. I would use such datasets to challenge particular mechanisms once those mechanisms are represented in Cells. [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC4888949/?utm_source=chatgpt.com)

## 6. The validation program I would build for Cells

I would make Syn3A a staged biological target, starting with the mechanisms closest to the current Cells direction.

### Stage 1: Freeze the evidence and the organism definition

Create a versioned inventory containing the genome annotation, protein identities, strain, medium, temperature, growth phase, intervention, assay, and biological replicate.

Every parameter or observation should have an explicit evidence category:

| Category | How to use it |
|---|---|
| **Measured in the exact strain and condition** | Direct experimental constraint; potentially held-out validation evidence. |
| **Measured in a related strain or species** | Transferable prior with an explicit uncertainty. |
| **Measured in a reconstructed subsystem** | Evidence for that component and assay. |
| **Inferred or fitted from measurements** | Model parameter whose dependence on the fitting data must be recorded. |
| **Predicted by another simulator** | Reference output for comparing models. |

This would make it possible to answer a crucial question for any result: **which parts were measured, which were assumed, and which were predicted?**

### Stage 2: Establish membrane transport against bounded assays

Start with the reconstituted-membrane experiments, where the system boundary is relatively clear.

Use these to constrain passive transport, membrane area, volume, and concentration changes. Reserve different published conditions for evaluation where the data permit.

If an experimental permeability coefficient is supplied as an input, reproducing that same coefficient is calibration. A stronger test is whether it predicts a separately measured transport or volume response.

This stage is a manageable way to connect Cells’ physical operators to experimental measurements before introducing all the cell’s internal machinery.

### Stage 3: Connect membrane changes to living-cell responses

Move to the 2024 Syn3A lipid-diet experiments.

The interesting challenge is to explain several outcomes together:

- Permeability.
- Sensitivity to osmotic stress.
- Growth.

This requires explicit links between those outcomes. Fluorescence-based uptake needs an observation model connecting simulated molecules to the measured signal. Osmotic lysis needs a membrane-failure model; changing water volume alone does not explain rupture.

I would initially choose the subset that the implemented mechanisms can meaningfully predict, then expand the claim as the missing mechanisms are added.

### Stage 4: Add metabolism, protein inventories, and growth

Use the experimentally constrained protein inventory and metabolic reconstruction to build organism-specific transport and reaction modules.

Here the main engineering test is whether the same resources support all the processes that consume them:

- Nutrient acquisition.
- Energy production and expenditure.
- RNA and protein production.
- Functional-complex assembly.
- Membrane and biomass growth.

The acceptance criterion should include several measured responses. A correct doubling time alone can hide compensating errors in transport, synthesis, maintenance, or loss.

### Stage 5: Test division and genetic perturbations

Then use Syn3.0, Syn3A, and the published restoration strains as a more demanding challenge.

The model should explain how changes to available machinery alter cell shape and division behavior. Prescribed division remains useful for testing partition accounting, but explaining the genetic experiments requires a causal mechanism linking the altered inventory to division.

That would be a strong demonstration of the full Cells chain:

**molecular inventory → functional machinery → physiology → growth and division.**

### Keep the tissue-electrical work alongside this

A successful Syn3A model would provide evidence for specific cellular mechanisms and their coupling. Cells’ claims about gap junctions, tissue conduction, multicellular patterning, or regeneration would still need their own biological benchmarks.

I would therefore keep the current electrical validation track and add Syn3A as the minimal-cell track.

**The first substantial milestone I would set is one frozen model that explains multiple measured membrane and growth responses in held-out Syn3A conditions.** That would give Eidosoma a compact, experimentally grounded organism to build around, with a clear path from individual physical mechanisms toward a whole living cell.
