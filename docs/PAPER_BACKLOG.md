# Paper backlog

Papers the user has asked us to test or model in Cells, each with its own review
and plan. Order is the lead's, per D137 and D138.

| Paper | What it offers Cells | Plan | Status | Next step |
| --- | --- | --- | --- | --- |
| Cortés-Poza 2026, [*A hybrid mathematical framework for morphogenesis and regeneration*](https://doi.org/10.1007/s00285-026-02459-2), *J. Math. Biol.* 93:43 | Bistable bioelectric layer with adaptive junctions and slow memory; nucleation, coupling and switching thresholds; regeneration claims | [CORTES_POZA_2026_TEST_PLAN.md](CORTES_POZA_2026_TEST_PLAN.md) | Phase 0 done (11 November): with the paper's own definitions and the review's corrections, the reproduced effects also appear in a plain bistable chain (limits in the plan) | Phase 1 in Cells, after the junction-heat fix lands |
| Deb et al. 2026, [*Multiscale Modeling of Embryonic Morphogenesis from Fertilization to Organogenesis*](https://doi.org/10.1038/s41540-026-00788-y), *npj Syst. Biol. Appl.* 12:156 | Benchmark systems and validation evidence for the vertex-mechanics ladder | [DEB_2026_MORPHOGENESIS_REVIEW_PLAN.md](DEB_2026_MORPHOGENESIS_REVIEW_PLAN.md) | Additions to MG1 accepted (D138); MG1 design started 11 November | Recoil and tension-inference checks join MG1's pre-registered acceptance |
| Shin et al. 2025, [*Attractor Landscape Analysis Reveals a Reversion Switch in the Transition of Colorectal Tumorigenesis*](https://doi.org/10.1002/advs.202412503), *Adv. Sci.* 12:e2412503 | Attractor-landscape measures; the reversion question | [SHIN_2025_REVERT_PLAN.md](SHIN_2025_REVERT_PLAN.md) | Backlog; the published rules (Tables S1–S3) were obtained and the network enumerated (31 fixed points; YY1+MYC removes the cancer states) | GEO sample list, then ask the user to approve the reproduction |
| GRN wet-lab validations (seven models: yeast cell cycle, Drosophila gap genes and segment polarity, Arabidopsis flower, human haematopoiesis, iPSC reprogramming) | Benchmarks for the planned gene-regulation layer; the inherited-record question | [GRN_WETLAB_VALIDATION.md](GRN_WETLAB_VALIDATION.md) | Logged, not started | Verify claims; first case likely the yeast cell cycle |
| Arc Institute Virtual Cell Initiative data (Challenge 2025 knockdowns in H1 cells, Tahoe-100M drug responses, scBaseCount; CC0) | Held-out perturbation tests for the future gene-regulation layer; not for current engine models | [GRN_WETLAB_VALIDATION.md#data-sources](GRN_WETLAB_VALIDATION.md#data-sources) | Logged, not started | Confirm test data are public; map targets to candidate network nodes |
| Washizu et al. 2026, [*Partial reprogramming reveals lineage-specific uncoupling of rejuvenation, function, and recoverability in human cells*](https://doi.org/10.64898/2026.11.09.764947), bioRxiv v1 (CC BY-NC-ND) | A write–clear–challenge protocol for cue experiments (depth as a measured state, verified cue clearance, mark and function scored separately); a cross-lineage TOX perturbation set as a second-tier gene-regulation benchmark. No bioelectricity, water, division or mechanics | [PAPER_REVIEW_PARTIAL_REPROGRAMMING.md](PAPER_REVIEW_PARTIAL_REPROGRAMMING.md) | Reviewed 13 November; no engine feature, and the data and code are embargoed until peer-reviewed publication | Ask the user whether the revised E07-v1 adopts the three protocol rules; keep the perturbation test behind the wet-lab-validated GRNs |
| GZMK and tissue ageing (five papers: [Kannangara 2026](https://doi.org/10.1016/j.immuni.2026.10.013), [Sucharov 2026](https://doi.org/10.1016/j.immuni.2026.04.014), [Terekhova 2026](https://doi.org/10.1016/j.immuni.2026.09.012), [Donado 2025](https://doi.org/10.1038/s41586-025-08713-9), [Joeckel 2017](https://doi.org/10.1038/icb.2017.35)) | A secreted-protease ageing axis: motivation for extracellular secreted species, enzyme catalysis, a cell-state layer and an ECM entity. No bioelectric result and no kinetic constant in any of them | [PAPER_REVIEW_GZMK_AGEING.md](PAPER_REVIEW_GZMK_AGEING.md) | Reviewed 13 November 2026; not started. Far beyond the current gates; 22–24 months is ~6e10 steps at 1 ms | The user's call: keep as reading notes, or promote general secreted-species transport in the D136 queue behind the molecular loop |

The overall order is set against the engine-feature queue (D136), currently:

1. water and volume (qualified and on main, 11 November);
2. cell replacement (G2: protocol registered; tolerances being pinned);
3. Cortés-Poza Phase 0 (done);
4. MG1 (judged run failed 52/57; being diagnosed);
5. Cortés-Poza Phase 1 (unblocked: the junction-heat fix and the frozen-composition comparison are both in; next free slot);
6. the gene-regulation layer (heredity Stage D, parity P8);
7. REVERT reproduction.
