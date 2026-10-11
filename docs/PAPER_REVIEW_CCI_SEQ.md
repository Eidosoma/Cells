**CCI-seq: relevance to Cells — reviewed 8 October 2026**

Tang, L., Tian, K., Fu, X. et al., *Resolving cell–cell interaction networks and
their molecular logic in complex tissues*, Nature Methods, published
5 October 2026. [Paper and methods](https://www.nature.com/articles/s41592-026-03237-0),
DOI: 10.1038/s41592-026-03237-0.

**Relevant: retain as a source for tissue neighbourhoods and future experimental
comparisons.** The recommendations below are proposed Cells work, not results
already reproduced in our simulator.

CCI-seq labels partially dissociated cell clumps, then obtains individual
transcriptomes while retaining clump identity. These are experimental
measurements from mouse tissues and human colorectal samples. The especially
useful kidney result is that distal convoluted tubule cells associated with
intercalated collecting-duct cells show a calcium-related program including
Trpv5 and Calb1; association with principal cells instead accompanies Scnn1g
and Slc8a1 expression. These are associations between neighbourhood and RNA,
not measured transport rates or evidence that the neighbour caused the change.
The assay spans contact and nearby co-location; shared clump membership does
not establish an electrical junction between every pair. See the paper's
Fig. 2, Discussion and Methods. [Source](https://www.nature.com/articles/s41592-026-03237-0).

**How I would use it in Cells**

| Priority | Proposed use | Connection to our implementation |
| --- | --- | --- |
| First | Import clump membership, cell annotation, sample/replicate identity and expression metadata as an observational dataset. Preserve each clump as a group, including uncertainty about its pairwise contacts. | Our [tissue model](../src/cells/models/tissue.py) requires explicit membrane/outside owners and physical junctions. Keep observational associations separate from those physical parameters. |
| First | Compare the observed organisation with shuffled cell labels and alternative contact graphs. Stratify by biological sample and check sensitivity to clump size. | Add read-only observers and input fixtures before changing the dynamics. A frequency of association must not become a permeability or conductance. |
| Next | Use kidney transport programs to choose which channel/buffer/exchanger mechanisms need development and independent calibration. | [Tissue calcium](../src/cells/models/tissue_calcium.py) already composes free/bound calcium, ER, PMCA/NCX and CaV1.2. Its synthetic buffers and CaV1.2 must not be relabelled as measured calbindin or TRPV5. Polarized epithelial surfaces and appropriate reservoirs also need separate modelling. |
| Later | Test whether an explicitly modelled neighbour signal changes a cell's transport machinery and persists after removal. | Requires a causal regulatory law, parameter evidence and a declared timescale. The present fast ionic solver does not infer these from RNA counts. |

For Plastic Heredity and How Forms Become Reconstructible, I would compare
identical starting cells under different neighbourhoods, then restore a common
environment and apply the same challenge. Separate ongoing environmental support,
persistent state and transmission to fresh recipients. This is a proposed assay; the
paper does not demonstrate renewable heredity.

For assembly, retain the existing distinction between the protein-bond graph
and the intercellular tissue graph. Our [assembly integration](../src/cells/assembly_cluster/kernel.py)
currently changes channel availability using cell-owned stochastic pools.
Neighbour-dependent protein production or assembly rates would be additional
hypotheses requiring their own material accounting and validation.

**Reusable analysis and data**

I inspected the authors' kidney interaction notebook at commit
`327725c97d82e8918d880e439d57e4133cfa93d4`. It reads `result.txt`, selects
`qc == 1`, groups by `CellID`, and uses `celltype`; expression is loaded from
`rna.h5ad`. Its association calculation normalizes pair counts within clumps
and by cell-type abundance. It also counts co-occurring clumps and performs
1,000 label permutations preserving clump sizes. These are useful observer
references. The permutation function uses Python's `random.sample`; I found
no explicit random seed in this notebook. A Cells reproduction should save
its seed and distinguish exact published calculations from any revised
statistical estimator. [Pinned notebook](https://github.com/zhangqf-lab/CCI-seq/blob/327725c97d82e8918d880e439d57e4133cfa93d4/notebook/Fig.2/03.interaction.ipynb).

The [repository](https://github.com/zhangqf-lab/CCI-seq) carries an MIT license.
Its README documents a two-base barcode difference between the RNA and index
libraries for the kit used, with a supplied mapping. Preserve the supplied
mapping if rebuilding from reads; do not join those libraries naively.

The [authors' Zenodo archive](https://zenodo.org/records/19544434) lists processed
data and source data, including `Fig.2.zip` (396 MB) for the kidney and
`SourceData.zip` (175.1 MB). It also lists GSA `PRJCA034558`, OMIX `OMIX016046`
and human processed data at GEO `GSE327054`. The archive states that human raw
reads require a research request. Archive listings were checked; those large
datasets were not downloaded or audited. Start with the kidney processed data
and verify its schema and replicate identifiers before designing a benchmark.

For GPU work, preprocess and validate the dataset on CPU, then batch independent
candidate tissue worlds using the existing scheduler. Group comparable graph
sizes and estimated runtimes to balance future four-GPU nodes; retain stable
world IDs, complete checkpoints, GPU-busy/SM-active coverage and node-time
accounting. GPU replicas are computational samples, not additional biological
replicates. No performance conclusion follows from this literature review.

**Recommended first follow-up:** a small, versioned kidney dataset adapter and
an independent reproduction of the association statistics. Only then propose
a physiological simulation benchmark with separately supported kinetics and
geometry. This review introduces no simulator changes or acceptance claims.

The article HTML, extracted text, pinned notebook/README/license and their
[source manifest](/mnt/workspaces/Cells/paper-reviews/s41592-026-03237-0/source-manifest.json)
are retained under `/mnt/workspaces/Cells/paper-reviews/s41592-026-03237-0/`.
Upstream code was inspected without executing it. Current simulation status
continues to live in [PROGRESS.md](../PROGRESS.md).
