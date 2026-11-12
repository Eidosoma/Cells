**Humans have roughly 20,000 protein-coding genes, but these can produce a much larger number of distinct protein versions—potentially millions when processing and chemical modifications are included.** The exact total depends on what you count as a “different protein.” [Human Release Statistics](https://www.gencodegenes.org/human/stats_50.html?utm_source=chatgpt.com)

**Yes, there are excellent atlases of their functions and three-dimensional shapes.** The best starting point for what you’re describing is the **[Human Protein Atlas](https://www.proteinatlas.org/)**, which connects proteins to tissues, cell types, locations within cells, structures, and interactions. [proteinatlas.org](https://www.proteinatlas.org/?query=proteins\&utm_source=chatgpt.com)

## 1. How many different proteins are there?

There are three useful ways to count:

| What you count | Approximate number | What that means |
|---|---:|---|
| **Protein-coding genes** | **About 20,000** | The basic genetic instructions. GENCODE release 50 lists **19,442** under its counting conventions. |
| **Different amino-acid sequences** | **More than 100,000 annotated possibilities** | One gene can produce several versions. GENCODE release 50 lists **172,117 distinct translations**, but these are annotated sequences, **not a count of experimentally verified proteins made in a person**. |
| **Exact molecular versions, called proteoforms** | **Potentially millions; total unknown** | These include differences in sequence, cleavage, and chemical modifications such as attached phosphate or sugar groups. |

The first two figures come from the same GENCODE release. Estimates at the proteoform level remain much less certain, and a complete experimental census does not yet exist. [Human Release Statistics](https://www.gencodegenes.org/human/stats_50.html?utm_source=chatgpt.com)

### How one gene produces multiple versions

The diversity arises at several stages:

- **Alternative splicing:** cells assemble the RNA instructions in different ways, which can produce proteins with different sections.
- **Protein processing:** a newly made protein may be cut into its mature form or into several products.
- **Chemical modifications:** cells attach phosphate groups, sugars, acetyl groups, and other chemical additions. These can affect activity, location, stability, and interactions.
- **Sequence variation:** genetic differences can change the amino-acid sequence. Antibodies and T-cell receptors also gain enormous diversity through rearrangement of immune-system gene segments. [UniProt](https://www.ebi.ac.uk/training/online/courses/uniprot-exploring-protein-sequence-and-functional-info/exploring-a-uniprotkb-entry/the-entry-view/sequence-isoforms/?utm_source=chatgpt.com)

A *proteoform* means a particular molecular version defined by its sequence and modifications. A protein simply bending into another shape does not, by itself, make it a different proteoform.

Also, **these proteins are distributed across different cells, tissues, and stages of life**. A liver cell, neuron, and muscle cell do not produce identical sets or amounts of proteins; mapping those differences is a central purpose of the Human Protein Atlas. [The Human Protein Atlas](https://www.proteinatlas.org/humanproteome/tissue?utm_source=chatgpt.com)

## 2. The main atlases—and what each is best for

| What you want to know | Resource | What it provides |
|---|---|---|
| **Where is this protein in the body and inside cells?** | **[Human Protein Atlas](https://www.proteinatlas.org/)** | Tissue and cell-type profiles, microscopy images, subcellular locations, structures, and interaction information. |
| **What does this protein do?** | **[UniProt](https://www.uniprot.org/)** | Function, amino-acid sequence, variants, isoforms, modifications, interacting partners, and links to research. |
| **What does its experimentally determined 3D structure look like?** | **[RCSB Protein Data Bank](https://www.rcsb.org/)** | Structures derived from experiments, including individual proteins and molecular complexes. Its website also offers predicted models, which are labelled separately. |
| **What shape is predicted when experimental information is missing?** | **[AlphaFold Protein Structure Database](https://alphafold.ebi.ac.uk/)** | Interactive predicted structures with confidence scores. |
| **How does it participate in a larger biological process?** | **[Reactome](https://reactome.org/)** | Curated maps of reactions and pathways, linking proteins into processes such as signalling, metabolism, and gene regulation. |

These resources complement one another: UniProt acts as a protein’s reference record, the structure databases describe its geometry, and the tissue and pathway atlases place it in its biological context. [proteinatlas.org](https://www.proteinatlas.org/?query=proteins\&utm_source=chatgpt.com)

### Human Protein Atlas: the closest match to your question

Its most relevant sections are:

- **[Tissue](https://www.proteinatlas.org/humanproteome/tissue):** where proteins are expressed across organs, with tissue images and measurements.
- **[Subcellular](https://www.proteinatlas.org/humanproteome/subcellular):** whether a protein is found in the nucleus, mitochondria, membrane, cell junctions, or other cellular structures.
- **[Structure](https://www.proteinatlas.org/humanproteome/structure):** interactive three-dimensional models. The resource lists predicted structures for **19,904 human proteins and their related isoforms**.
- **[Interaction](https://www.proteinatlas.org/humanproteome/interaction):** interaction networks, predicted structures of protein partnerships, and metabolic relationships. [The Human Protein Atlas](https://www.proteinatlas.org/humanproteome/tissue?utm_source=chatgpt.com)

One detail to watch when browsing: **some charts measure RNA expression, while others measure protein directly**. The atlas includes both, and they answer related but different questions. [The Human Protein Atlas](https://www.proteinatlas.org/humanproteome/tissue?utm_source=chatgpt.com)

### For an illustrated explanation of form and function

I would also recommend **[PDB-101’s Molecule of the Month](https://pdb101.rcsb.org/motm/motm-about)**. It presents selected molecular machines through illustrations and short explanations of their structure, function, and biological importance. It is particularly useful for learning how a protein’s physical construction enables its job. [pdb101.rcsb.org](https://pdb101.rcsb.org/motm/motm-about?utm_source=chatgpt.com)

## 3. How complete is our knowledge?

**Knowing that a protein exists, knowing its shape, and knowing what it does are different achievements.**

The 2025 Human Proteome Project report, published in 2026, reported confident evidence of expression for approximately **94% of its reference set of 19,435 protein-coding genes**. That means detecting at least one protein form from those genes; it does not mean that 94% of all variants have been identified or that their functions are fully understood. The project is also pursuing the separate goal of establishing at least one function for every protein. [The Human Protein Atlas](https://www.proteinatlas.org/news/2026-02-20/the-2025-hupo-hpp-report-on-the-human-proteome?utm_source=chatgpt.com)

Similarly, a structure database is not a complete catalogue of everything a protein can do:

- **Proteins can change shape.** A channel, for example, may adopt different conformations.
- **Some regions are flexible or disordered.** They may not have one stable shape in isolation.
- **Partners matter.** A protein may function as part of a larger assembly.
- **Predictions have uncertainty.** AlphaFold’s confidence can vary along the same protein, and a model does not describe all of its possible conformations. [alphafold.ebi.ac.uk](https://www.alphafold.ebi.ac.uk/faq?utm_source=chatgpt.com)

When exploring a structure, it therefore helps to ask: **Is this experimental or predicted? Is it the whole protein? Is it shown alone or in its working assembly?**

## 4. A concrete example: a gap-junction protein

A useful protein to explore is **connexin 43**, encoded by **GJA1**. It forms channels that allow neighbouring cells to exchange ions and small molecules directly. [rcsb.org](https://www.rcsb.org/structure/7Z22?utm_source=chatgpt.com)

You can examine it at several levels:

| Level | What you can explore |
|---|---|
| **Where it occurs** | [GJA1 in the Human Protein Atlas](https://www.proteinatlas.org/ENSG00000152661-GJA1): tissue expression, cell types, and locations within cells. |
| **Its reference information** | [Connexin 43 in UniProt](https://www.uniprot.org/uniprotkb/P17302/entry): the protein’s sequence and functional annotations. |
| **Its assembled shape** | [Human connexin-43 channel, PDB 7Z22](https://www.rcsb.org/structure/7Z22): an experimentally determined structure that you can rotate in 3D. |

The assembled channel in that PDB entry contains **12 copies of connexin 43**, arranged as two opposing rings of six. This illustrates why counting proteins and counting molecular machines are different: one protein type can assemble into a larger working structure. [rcsb.org](https://www.rcsb.org/structure/7Z22?utm_source=chatgpt.com)

There is even a **[2026 structure of human connexin-43 gap junctions in their cellular setting](https://www.rcsb.org/structure/9RKX)**, showing how channels are organised into larger junctional arrays. That takes you from the shape of a protein to the architecture through which cells communicate. [rcsb.org](https://www.rcsb.org/structure/9RKX?utm_source=chatgpt.com)
