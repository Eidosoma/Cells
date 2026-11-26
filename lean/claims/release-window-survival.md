<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Marked RNA is accounted for in both release fates, including after label reuse

A detachment event marked in a half-open window belongs to exactly one of the two fates. In the continuous-amount model their gross amounts sum to the marked release even when the split changes. Each fate can have its own survival fraction. Reusing a label adds the survivors of both windows, and the chase fraction uses the original cohort alive at window close.

## Assumptions

- Time is indexed by step boundaries. In the exact event example a molecule is marked on detachment and experiences the following interval’s survival factor. Sampling is before any new releases at that sample boundary.
- Every member of the same physical pool experiences the same survival factor in each interval. For a physical chase each factor is in [0,1]. A reused label receives new material from nonoverlapping windows.
- A zero denominator gives an undefined chase fraction. A host readout with only interval totals assumes a within-interval arrival profile. The synthetic counter comparison uses uniform arrivals and constant per-molecule loss.
- Gross release is nonnegative. The durable fraction p lies in [0,1] and can vary by step. The short-lived fraction is 1 − p. Each fate has a survival fraction in [0,1].

## Lean proof

**Proved**

- [CellsProofs.Chemistry.ArrivalWindow.at_start](../CellsProofs/Chemistry/ArrivalWindow.lean#L18)
- [CellsProofs.Chemistry.ArrivalWindow.at_end](../CellsProofs/Chemistry/ArrivalWindow.lean#L19)
- [CellsProofs.Chemistry.ArrivalWindow.adjacent](../CellsProofs/Chemistry/ArrivalWindow.lean#L22)
- [CellsProofs.Chemistry.ArrivalWindow.add_histories](../CellsProofs/Chemistry/ArrivalWindow.lean#L34)
- [CellsProofs.Chemistry.ArrivalWindow.reuse](../CellsProofs/Chemistry/ArrivalWindow.lean#L41)
- [CellsProofs.Chemistry.ArrivalWindow.chase_only](../CellsProofs/Chemistry/ArrivalWindow.lean#L46)
- [CellsProofs.Chemistry.ArrivalWindow.chase_fraction](../CellsProofs/Chemistry/ArrivalWindow.lean#L56)
- [CellsProofs.Chemistry.ArrivalWindow.empty_fraction](../CellsProofs/Chemistry/ArrivalWindow.lean#L61)
- [CellsProofs.Chemistry.ArrivalWindow.release_example](../CellsProofs/Chemistry/ArrivalWindow.lean#L65)
- [CellsProofs.Chemistry.MarkedRelease.event_partition](../CellsProofs/Chemistry/MarkedRelease.lean#L12)
- [CellsProofs.Chemistry.MarkedRelease.marked_fates](../CellsProofs/Chemistry/MarkedRelease.lean#L20)
- [CellsProofs.Chemistry.MarkedRelease.survivors_bounded](../CellsProofs/Chemistry/MarkedRelease.lean#L34)

Direct proof subject `cells.operator.templated_polymerisation@1`, `cells.operator.neutral_arrival_labels@1`

Proof sources [Mathlib product over the successor range, imported for survival across a chase](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Basic.lean#L503) · [FR-42 boundary and reuse requirements](https://github.com/Eidosoma/Cells/blob/57cf9a4ed0b68454232a3c531c14e1b725853955/docs/FEATURE_REQUESTS.md#fr-42--neutral-arrival-time-labels-that-leave-the-dynamics-unchanged) · [FR-38 clarification of release, survivors and the chase denominator](https://github.com/Eidosoma/Cells/blob/57cf9a4ed0b68454232a3c531c14e1b725853955/docs/FEATURE_REQUESTS.md#fr-38--rna-release-from-its-template-into-two-pools-with-different-lifetimes) · [Mathlib finite partition into a predicate and its complement, imported for individual events](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Basic.lean#L117-L124) · [Cells uses neutral RNA shares to mark at release](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/docs/TEMPLATED_POLYMERISATION_LAWS.md#914-erratum-c-route-1-on-shares)

Uses [Neutral arrival-time cohorts share one physical loss rate](fr42-cohort-shares.md) · [A positive endpoint determines one neutral-label survival exponent](fr42-survival-exponent.md)

## Numerical comparison

**Checked.** Across three compiled RNA runs all 39 physical readouts matched bit for bit. The two marked intervals released 1.02212491320 × 10⁻¹⁰ fmol into the two fates. Reusing a label reproduced the sum of the two separately marked cohorts to within 1.30 × 10⁻²⁶ fmol. The counter reconstruction’s maximum relative error for the short-lived fate was 4.80 × 10⁻⁸ on a two-second output grid and 2.93 × 10⁻⁹ on a half-second grid. The independent point-release example retained 6 of 8 at chase. The separate FR-42 tissue comparison checked the same window semantics with production and clearance. This window comparison followed the same producer throughout. A separate [producer replacement and restart comparison](producer-replacement-rna.md) follows both generations on the development engine.

**Reference calculation**

[Half-open windows and within-run label reuse](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/docs/FEATURE_REQUESTS.md#fr-42--neutral-arrival-time-labels-that-leave-the-dynamics-unchanged) · [FR-38 release-marking and chase denominator](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/docs/FEATURE_REQUESTS.md#fr-38--rna-release-from-its-template-into-two-pools-with-different-lifetimes) · [Point-arrival recurrence and survival of the original cohort](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/CellsProofs/Chemistry/ArrivalWindow.lean) · [Host calculation for uniformly spread arrivals](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/validation/gene_regulation/cohort.py#L139) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/checks/arrival_windows.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/PROGRESS.md#fr38-marked-fates)

[Evidence checkpoint 4404a1b3cd88](https://github.com/Eidosoma/Cells/commit/4404a1b3cd889ba7a9a75f18df0cdf479898cd73)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.templated_polymerisation@1`, `cells.neutral_arrival_labels@1`

[Compiled state collection](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/engine_run.py#L178) · [R1, marking schedules and R1S](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/worlds.py#L520) · [Run horizon and grid](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/kernel.py#L35) · [Compiled window execution](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/src/cells/execution/windows.py) · [Release extents and their label reports](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/src/cells/operators/templated_polymerisation.py#L1565) · [Neutral label and pool update](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/src/cells/operators/species_labels.py#L506) · [Survival and transfer of neutral shares](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/src/cells/numerics/label_shares.py#L64) · [Composite applies the reporters' half-steps](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/src/cells/models/pump_composite.py#L1752) · [Fate readouts and counters](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/engine_run.py#L429) · [Exported RNA and hold amounts by label](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/engine_run.py#L317) · [Independent window integral and grid comparison](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/release_check.py#L112) · [Cohort from unlabelled counters](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/cohort.py#L139) · [Sheet constants and the copy unit](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/sheet_check.py) · [Marked detachment and survival bounds](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/CellsProofs/Chemistry/MarkedRelease.lean) · [Half-open windows and reuse](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/CellsProofs/Chemistry/ArrivalWindow.lean) · [Exact neutral shares](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/CellsProofs/Chemistry/ArrivalSurvival.lean) · [Two published RNA time courses and denominators](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/checks/data/rna_chase_observables.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/checks/arrival_windows.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/PROGRESS.md#fr38-marked-fates)

[Tested engine 947ff262c7fb](https://github.com/Eidosoma/Cells/commit/947ff262c7fba53b53b32a7c44394e84be3fa897) · [Evidence checkpoint 4404a1b3cd88](https://github.com/Eidosoma/Cells/commit/4404a1b3cd889ba7a9a75f18df0cdf479898cd73)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.templated_polymerisation@1`, `cells.neutral_arrival_labels@1`

[Compiled state collection](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/engine_run.py#L178) · [R1, marking schedules and R1S](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/worlds.py#L520) · [Run horizon and grid](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/kernel.py#L35) · [Compiled window execution](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/src/cells/execution/windows.py) · [Release extents and their label reports](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/src/cells/operators/templated_polymerisation.py#L1565) · [Neutral label and pool update](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/src/cells/operators/species_labels.py#L506) · [Survival and transfer of neutral shares](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/src/cells/numerics/label_shares.py#L64) · [Composite applies the reporters' half-steps](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/src/cells/models/pump_composite.py#L1752) · [Zero-loss eligibility and export](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/engine_run.py#L284) · [Physical release counters](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/engine_run.py#L429) · [Cell-local selection of production and loss counters](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/cohort.py#L305) · [Survivors from the exported counters](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/cohort.py#L139) · [Exact lossless gain](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/CellsProofs/Chemistry/TerminalRelease.lean) · [Window-marked detachment](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/CellsProofs/Chemistry/MarkedRelease.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/checks/terminal_release.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/PROGRESS.md#fr38-marked-fates)

[Tested engine 947ff262c7fb](https://github.com/Eidosoma/Cells/commit/947ff262c7fba53b53b32a7c44394e84be3fa897) · [Evidence checkpoint 4404a1b3cd88](https://github.com/Eidosoma/Cells/commit/4404a1b3cd889ba7a9a75f18df0cdf479898cd73)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.neutral_arrival_labels@1`, `cells.local_species_reactions@1`, `cells.scheduled_species_turnover@1`

[Finite-step bisection, allocation and empty-row handling](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/src/cells/numerics/label_shares.py#L64) · [Label declarations, schedules and share update](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/src/cells/operators/species_labels.py) · [Composite half-step calls the label owner](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/src/cells/models/pump_composite.py#L1752) · [One-way reaction reports](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/src/cells/operators/species_reactions.py#L1692) · [Turnover reports](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/src/cells/operators/species_turnover.py#L611) · [Summation along the label axis](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/src/cells/numerics/species_sums.py) · [Compiled twin worlds, window integrals and tolerances](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/tests/unit/test_neutral_arrival_labels.py#L465) · [Composite tissue and production/clearance fixture](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/validation/tissue/secreted_species_fixtures.py) · [Reaction fixture and schedules](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/validation/tissue/species_reactions_fixtures.py) · [Exact endpoint and normalized label amounts](https://github.com/Eidosoma/Cells/blob/7e41a441b51b5a84ec57febb04b1e7a8f801674d/lean/CellsProofs/Chemistry/ArrivalSurvival.lean) · [Quadratic cohort and blank reference](https://github.com/Eidosoma/Cells/blob/7e41a441b51b5a84ec57febb04b1e7a8f801674d/lean/CellsProofs/Chemistry/ArrivalCohort.lean) · [Paired Actn1 isotope signals and GEO sample accessions](https://github.com/Eidosoma/Cells/blob/7e41a441b51b5a84ec57febb04b1e7a8f801674d/lean/checks/data/jovanovic2015_actn1.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/7e41a441b51b5a84ec57febb04b1e7a8f801674d/lean/checks/arrival_survival.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/7e41a441b51b5a84ec57febb04b1e7a8f801674d/lean/PROGRESS.md#fr42-neutral-survival)

[Tested engine 73afa19b5ddc](https://github.com/Eidosoma/Cells/commit/73afa19b5ddcb50405280d6d46207a25c41fec24) · [Evidence checkpoint 7e41a441b51b](https://github.com/Eidosoma/Cells/commit/7e41a441b51b5a84ec57febb04b1e7a8f801674d)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.templated_polymerisation@1`

[One-way release from the template hold into the scheduled class and fate](https://github.com/Eidosoma/Cells/blob/57cf9a4ed0b68454232a3c531c14e1b725853955/src/cells/operators/templated_polymerisation.py#L1201-L1224) · [Template hold and release classes in the R1 world](https://github.com/Eidosoma/Cells/blob/57cf9a4ed0b68454232a3c531c14e1b725853955/validation/gene_regulation/worlds.py#L519-L558) · [Schedule controls on the engine grid](https://github.com/Eidosoma/Cells/blob/57cf9a4ed0b68454232a3c531c14e1b725853955/src/cells/definitions/pump_composite_spec.py#L258) · [Public windowed engine execution](https://github.com/Eidosoma/Cells/blob/57cf9a4ed0b68454232a3c531c14e1b725853955/src/cells/execution/windows.py) · [Compiled collection and class-specific release counters](https://github.com/Eidosoma/Cells/blob/57cf9a4ed0b68454232a3c531c14e1b725853955/validation/gene_regulation/engine_run.py#L393-L411) · [Observation horizon and grid of the starting fixture](https://github.com/Eidosoma/Cells/blob/57cf9a4ed0b68454232a3c531c14e1b725853955/validation/gene_regulation/kernel.py#L28-L36) · [Fate export and release-counter selection](https://github.com/Eidosoma/Cells/blob/57cf9a4ed0b68454232a3c531c14e1b725853955/validation/gene_regulation/cohort.py#L240-L310) · [Exact release-window and chase identities](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/lean/CellsProofs/Chemistry/ArrivalWindow.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/lean/checks/arrival_windows.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/lean/PROGRESS.md#fr42-release-windows)

[Tested engine 57cf9a4ed0b6](https://github.com/Eidosoma/Cells/commit/57cf9a4ed0b68454232a3c531c14e1b725853955) · [Evidence checkpoint e4b729acf7e7](https://github.com/Eidosoma/Cells/commit/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2)

## Biological evidence

**Open.** Cohort membership requires the time of release from the template and survival of the same molecules to a later sample.

- [Removing the extracellular labelled nucleotide precursor immediately ends incorporation of the old label into newly made RNA.](../WET_LAB_EVIDENCE.md#pair-rna-label-washout-tail) · Challenged by both studies

Bellecourt et al. measured detachment among terminator-length RNAs. Ntini et al. measured chromatin association after a synthesis pulse, and Tutucci et al. counted yeast RNA during mitosis. A direct survival comparison still requires marking RNA at detachment and measuring the same cohort at window close and during chase.

**Unit** Fraction (0–1)

### bellecourt-2019-hisl-release

In vitro bacterial transcription. The assay distinguished released terminator-length RNA and template-associated terminator-length RNA. The chase followed labelling of nascent RNA. Figure 5A and accompanying Results, with the time course in Figure S5 [Bellecourt et al. (2019), Journal of Molecular Biology 431, 696–713](https://doi.org/10.1016/j.jmb.2019.01.003)

- **Evidence role** descriptive
- **Observed** 0.94 Fraction (0–1)

The study reports ±0.02 for the wild-type release fraction under reducing conditions. Figure 5A pools the 120, 240 and 480 s samples.

This measures population detachment. Individual completion-to-release delays and later survival of the same released cohort remain unmeasured. [Dataset manifest](../checks/data/bellecourt2019_rna_release.json) · [Comparison verdict](../PROGRESS.md#fr42-release-windows)

### ntini-2023-actb-chromatin

After an eight-minute synthesis pulse in MCF-7 cells, RNA was measured in chromatin and nucleoplasmic fractions at 0, 5, 10, 15 and 20 minutes. Figure 1, GEO GSE218726 and the authors’ transcript table, ACTB row ENSG00000075624.14. [Ntini et al. (2023), Cell Systems 14, 906–922.e6](https://doi.org/10.1016/j.cels.2023.09.005)

- **Evidence role** descriptive

The transcript table gives a point estimate for this row.

ACTB’s fitted chromatin-association half-time was 3.35 min. Each denominator pools the two recovered nuclear fractions. Relating these fractions to survival after detachment would require the size and subsequent fate of a cohort marked at release. [Dataset manifest](../checks/data/rna_chase_observables.json) · [Comparison verdict](../PROGRESS.md#fr38-marked-fates)

### tutucci-2018-ash1-mitosis

Endogenously tagged ASH1 RNA spots were counted per cell in 21 yeast cells every two minutes, with times aligned to anaphase onset. Figure 6b–c. The group estimate comes from panel c. [Tutucci et al. (2018), Nature Methods 15, 81–89](https://doi.org/10.1038/nmeth.4502)

- **Evidence role** descriptive

The authors report ±2.8 min with the 6.1 min value. The type of uncertainty is unspecified.

The mitotic decline in detected ASH1 spots had a reported half-life of 6.1 min. A per-cell count gives a population decay timescale. The release time and subsequent survival of a detachment-marked cohort remain unmeasured. [Dataset manifest](../checks/data/rna_chase_observables.json) · [Comparison verdict](../PROGRESS.md#fr38-marked-fates)

### pendleton2018_rna_wash

New reporter RNA was assayed after removal of extracellular 4-thiouridine. Fig. 2A and Supplementary Fig. S2. [Pendleton et al. (2018)](https://rnajournal.cshlp.org/content/24/6/778.full)

- **Evidence role** descriptive

Timing is specific to this preparation. Intracellular nucleotide-triphosphate concentration was not measured.

Incorporation continued after medium exchange and became negligible after about one hour. [Dataset manifest](../checks/data/paired_preparation_controls.json) · [Comparison verdict](../PROGRESS.md#preparation-evidence-review)

### gasser2020_dual_label

Sequencing distinguished old-label-only and double-labelled transcripts during a metabolic-label switch. Fig. 5A–B, incorporation following the label switch. [Gasser et al. (2020)](https://doi.org/10.1002/anie.201916272)

- **Evidence role** descriptive

The increased cumulative signal over that interval does not give the instantaneous incorporation rate at its endpoint.

Old-label-only transcript signal increased during the first two hours after the switch. The result supports continued incorporation during this window. [Dataset manifest](../checks/data/paired_preparation_controls.json) · [Comparison verdict](../PROGRESS.md#preparation-evidence-review)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
