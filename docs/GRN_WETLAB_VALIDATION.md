# Gene regulatory networks validated against wet-lab data

A track for gene regulatory network (GRN) models that have been grounded in real
experiments. Status: **logged, not started** (11 November 2026). Nothing here has
been run or verified by us yet.

## Why this track

Cells plans a gene-regulation layer coupled to tissue: heredity Stage D, BETSE
parity rung P8, and the [REVERT plan](SHIN_2025_REVERT_PLAN.md). Before that
layer carries any heredity claim, it should reproduce GRNs whose behaviour was
checked against real mutants, expression patterns and cell fates. These
published models are the candidate benchmarks.

The question that would connect this track to *Plastic Heredity* is: does a
mechanism that carries an inherited record add predictive power beyond an
ordinary calibrated GRN, especially for perturbations or conditions not used in
calibration? Matching a known attractor is not enough, because many of these
models were built from the same experiments they reproduce.

## Candidate benchmarks

Source: a literature note the user supplied on 11 November 2026. Every claim
below is as stated in that note and is still to be checked against the papers.

| Model | Type | Grounding (as stated, to verify) | Paper |
| --- | --- | --- | --- |
| Budding yeast cell cycle, 15 components (Taoma et al. 2024) | Stochastic weighted-threshold Boolean network, X_i(t+Δt) = H(ω_i0 + Σ_j ω_ij X_j(t)) | 65 regulatory coefficients adjusted by hand to mutant phenotypes, 14 parameters fitted to cell-cycle and growth data; 40 of 48 characterised mutants reproduced. That panel was used for calibration, so the 83% is not independent validation. Predictions for further multiple deletions. | [Stochastic Boolean model of normal and aberrant cell cycles in budding yeast](https://doi.org/10.1038/s41540-024-00452-3), *npj Syst. Biol. Appl.* |
| Drosophila gap genes: hunchback, Krüppel, knirps, giant (Jaeger et al. 2004; Perkins et al. 2006) | Weighted nonlinear (connectionist) and threshold-logic models | Fitted to quantitative microscopy of protein expression by position and time; both model types reproduce major features | [Reverse Engineering the Gap Gene Network of Drosophila melanogaster](https://doi.org/10.1371/journal.pcbi.0020051), *PLoS Comput. Biol.* (Jaeger 2004 still to locate) |
| Drosophila segment polarity (Albert & Othmer 2003) | Boolean, with rules from known molecular interactions | Wild-type pattern, several mutants, overexpression, correction of some perturbed starts. Not a numerical fit. | [The topology of the regulatory interactions predicts the expression pattern of the segment polarity genes in Drosophila melanogaster](https://doi.org/10.1016/S0022-5193(03)00035-3), *J. Theor. Biol.* |
| Drosophila *giant* regulation (Hoermann et al. 2016) | Quantitative models | Tested in mutant embryos; the proposed autoactivation was confirmed by mutating transcription-factor binding sites | Reference still to locate |
| Arabidopsis flower development, 15 nodes (Espinosa-Soto, Padilla-Longoria & Alvarez-Buylla 2004) | Multivalued logical network (levels 0, 1, 2) | Attractors match sepal, petal, stamen and carpel identities and many mutant patterns. The rules were built from much of the same genetics, so validation is not fully independent. | [A Gene Regulatory Network Model for Cell-Fate Determination during Arabidopsis Flower Development](https://doi.org/10.1105/tpc.104.021725), *Plant Cell* |
| Human haematopoietic stem-cell differentiation, 21-node core of about 200 (Herrera et al. 2024) | Boolean, continuous and stochastic versions | Compared with RNA-seq, gain- and loss-of-function phenotypes and cell-population frequencies; stochasticity needed for the observed plasticity | [A system-level model reveals that transcriptional stochasticity is required for hematopoietic stem cell differentiation](https://doi.org/10.1038/s41540-024-00469-8), *npj Syst. Biol. Appl.* |
| Human fibroblast to iPSC reprogramming, 276 nodes and 4,471 links (Hamaneh & Yu 2019) | Continuous weighted, steady-state based | Fitted on 35 microarray datasets, tested on 29 others | [Exploring induced pluripotency in human fibroblasts via construction, validation, and application of a gene regulatory network](https://doi.org/10.1371/journal.pone.0220742), *PLOS ONE* |

These studies show that weighted-threshold and logical architectures, related to
Wagner's abstract evolutionary networks, can describe real regulatory systems.
They do not validate properties of randomly generated Wagner networks.

## Data sources

**Arc Institute Virtual Cell Initiative**
([initiative](https://arcinstitute.org/virtual-cell-initiative),
[atlas](https://github.com/ArcInstitute/arc-virtual-cell-atlas)). Checked 11 November
2026 from Arc's own pages and the atlas README. The papers, the challenge website
and the 2026 rules were not read.

| Resource | What it is | Use for Cells |
| --- | --- | --- |
| Virtual Cell Challenge 2025 data | CRISPRi knockdowns of 300 genes in H1 human embryonic stem cells, about 1,000 cells each, single-cell RNA-seq; train, validation and test splits; CC0 | **Best fit.** Held-out knockdown responses to test a calibrated network, for example the iPSC reprogramming network, H1 being a pluripotent line. Still to check: that the test responses are public, and how many of the 300 targets are nodes of a candidate network |
| Tahoe-100M | About 100 million cells from 50 human cancer lines under about 1,100 drugs at several doses; RNA-seq; CC0 | Drug-response tests for regulatory networks. Check its line list for colorectal lines, which matter to the [REVERT plan](SHIN_2025_REVERT_PLAN.md). Its cell-cycle phase scores are inferred labels, not division dynamics |
| scBaseCount | Over 500 million cells, 21 organisms, 72 tissues; CC0 | Background expression. The species list is unread, so it is not yet known whether Xenopus or C. elegans are included |
| State model, cell-eval | A machine-learned perturbation model (weights and outputs under a non-commercial licence) and its evaluation code (licence unread) | Not used: Cells does not train models. Using State's outputs as a comparator would be a licence decision for the user |

**Limits.**
- **Snapshots only.** Each dataset is one time point of fixed cells, with no time
  course or lineage. It can test how a calibrated network responds to knockdowns,
  but neither heredity question (lasting after the cue, outliving the carriers).
- **Judge on network nodes.** The challenge scores genome-wide expression. A small
  mechanistic network must be judged on its own nodes only.
- **mRNA is only a hint for channels.** It suggests which channels, pumps and
  connexins a cell type has, but gives neither abundance nor conductance.
- **Absent:** membrane potential, imaging and embryos.

## Plan, when the track starts

1. **Verify.** Read each paper (Europe PMC for open access), confirm the claims
   above, and record the data and code that are available, with licences.
2. **Choose a first case.**
   - The yeast cell-cycle model (Taoma 2024) is the suggested start: it links
     weighted-threshold dynamics, mutant phenotypes and constrained attractors.
   - Segment polarity (Albert & Othmer 2003) is the smallest fully logical case,
     and relates to the morphogenesis track.
3. **Outside reference first.** Reproduce the published model out of process.
   Running a paper's own model is tooling, so it needs the user's approval per
   paper (D137, D138).
4. **Then in Cells.** Once the gene-regulation layer exists, implement the network
   in it as a cited, opt-in model (D136).
   - Judge it against the wet-lab observables, under a protocol registered before
     the run.
   - Keep the calibration data separate from held-out data.
5. **The heredity question:** compare an ordinary calibrated GRN with one carrying
   an inherited-record mechanism, on perturbations held out from calibration.

## Related

- [Paper backlog](PAPER_BACKLOG.md)
- [REVERT plan](SHIN_2025_REVERT_PLAN.md): attractor-landscape measures and a
  data-inferred Boolean network
- Cells' existing isolated regulatory model, `emt_mirna@1`
  ([reference](EMT_REFERENCE.md))
