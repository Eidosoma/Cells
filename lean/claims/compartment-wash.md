<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A partial wash dilutes free tracer and preserves its inventory

For a finite well of fixed volume V, a wash of fraction f changes free amount n to (1 − f)n + f V c_buffer. Adding sampled material and subtracting supplied material recovers the original total, including bound ligand retained through the event. Repeating k equal washes multiplies the initial excess above the buffer level by (1 − f)ᵏ. For each exchanged neutral species, ideal mixing heat is nonnegative and a whole wash releases zero mixing heat.

## Assumptions

- The liquid is well mixed. Between the washes used in the repeated-wash formula there is no binding, release, synthesis or transport. The landed tissue wash refuses a gene export into the washed node and outside degradation there. A different node remains eligible when its other admission conditions hold.
- The Lean positivity result assumes 0 < f ≤ 1 and strictly positive free and buffer amounts. Float64 whole-wash storage also requires sufficient resolution at the host’s amount anchor. Version 1 exchanges ions at their own concentration.
- For the heat, the well is ideal and isothermal with positive volume and concentrations and a nonnegative thermal energy scale.

## Lean proof

**Proved**

- [CellsProofs.Tissue.CompartmentWash.inventory](../CellsProofs/Tissue/CompartmentWash.lean#L16)
- [CellsProofs.Tissue.CompartmentWash.positive](../CellsProofs/Tissue/CompartmentWash.lean#L30)
- [CellsProofs.Tissue.CompartmentWash.whole](../CellsProofs/Tissue/CompartmentWash.lean#L34)
- [CellsProofs.Tissue.CompartmentWash.repeated](../CellsProofs/Tissue/CompartmentWash.lean#L56)
- [CellsProofs.Tissue.CompartmentWash.mixingHeat_nonneg](../CellsProofs/Tissue/CompartmentWash.lean#L42)
- [CellsProofs.Tissue.CompartmentWash.whole_mixing_heat](../CellsProofs/Tissue/CompartmentWash.lean#L51)

Direct proof subject `cells.scheduled_compartment_wash@1`

Proof sources [Mathlib logarithm bound used in the default mixing-heat proof](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/SpecialFunctions/Log/Basic.lean#L293-L294) · [Mathlib klFun_nonneg and klFun_eq_zero_iff, imported in the optional comparison](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/InformationTheory/KullbackLeibler/KLFun.lean#L145-L149) · [Cells specialization of the relative-entropy formula](../checks/mixing/KLFun.lean) · [Cells wash heat computed from the retained and supplied concentrations](https://github.com/Eidosoma/Cells/blob/b06158e8a8b2044d92183e8da8d646bf56c4a12b/src/cells/operators/wash_schedule.py#L448)

## Numerical comparison

**Checked.** Four compiled tracer schedules retained ions and site fields. The maximum tracer material discrepancy was 7.11 × 10⁻¹⁵ fmol. Whole-wash runs reached 2⁻⁵⁰ of the initial amount and reproduced the documented refusal at 2⁻⁶⁰. The repaired counter check completed at fractions 1/2 and 3/7 with exact agreement for each unchanged ion. On b06158e8 and again after FR-49 landed at cd3b7b09, all 35 wash tests passed, including named same-node gene-route refusals and a separate-node admission.

**Engine** `resolved_pump_composite@1`

**Operators** `cells.scheduled_compartment_wash@1`

[Ion sample and refill](https://github.com/Eidosoma/Cells/blob/2ae9ce8e5c6b56ecab091b6167d034eb97a5520f/src/cells/operators/wash_schedule.py#L421-L436) · [Cumulative ion counters](https://github.com/Eidosoma/Cells/blob/2ae9ce8e5c6b56ecab091b6167d034eb97a5520f/src/cells/operators/wash_schedule.py#L478-L491) · [Finite well and wash definition](https://github.com/Eidosoma/Cells/blob/2ae9ce8e5c6b56ecab091b6167d034eb97a5520f/validation/tissue/wash_schedule_fixtures.py#L35-L90) · [Public runner](https://github.com/Eidosoma/Cells/blob/2ae9ce8e5c6b56ecab091b6167d034eb97a5520f/src/cells/execution/runner.py#L384) · [Public unchanged-ion regression](https://github.com/Eidosoma/Cells/blob/2ae9ce8e5c6b56ecab091b6167d034eb97a5520f/tests/unit/test_wash_schedule_runs.py#L62-L92) · [Exact wash identity](https://github.com/Eidosoma/Cells/blob/841e06cd5d0e97b449b6eb5fdfa55f4e4376da86/lean/CellsProofs/Tissue/CompartmentWash.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/841e06cd5d0e97b449b6eb5fdfa55f4e4376da86/lean/checks/compartment_wash.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/841e06cd5d0e97b449b6eb5fdfa55f4e4376da86/lean/PROGRESS.md#d272-wash-clamp-retests)

[Tested engine 2ae9ce8e5c6b](https://github.com/Eidosoma/Cells/commit/2ae9ce8e5c6b56ecab091b6167d034eb97a5520f) · [Evidence checkpoint 841e06cd5d0e](https://github.com/Eidosoma/Cells/commit/841e06cd5d0e97b449b6eb5fdfa55f4e4376da86)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.scheduled_compartment_wash@1`, `cells.site_occupancy@1`

[Sample and supply](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/src/cells/operators/wash_schedule.py#L301) · [Cumulative counter updates](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/src/cells/operators/wash_schedule.py#L364) · [Finite well and wash schedule](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/validation/tissue/wash_schedule_fixtures.py) · [Compiled scan and host acceptance](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/src/cells/execution/runner.py#L242) · [Public half-wash regression](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/tests/unit/test_wash_schedule_runs.py#L24) · [Wash theorem](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/CellsProofs/Tissue/CompartmentWash.lean) · [Fluorescein dilution inputs](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/checks/data/vloemans2024_dilution.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/checks/compartment_wash.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/PROGRESS.md#main-review-d264-d266)

[Tested engine 68ab12e7f575](https://github.com/Eidosoma/Cells/commit/68ab12e7f57552fa551b103df1393a1e095cd001) · [Evidence checkpoint be54fafbff16](https://github.com/Eidosoma/Cells/commit/be54fafbff162065063b215d4ac3e6adaf534e3a)

**Engine** `resolved_pump_tissue@3`

**Operators** `cells.scheduled_compartment_wash@1`, `cells.site_occupancy@1`

[Liquid, sample and supply](https://github.com/Eidosoma/Cells/blob/d74f519d40b9a9f7488b94b489c6dc4dd865504c/src/cells/operators/wash_schedule.py#L301) · [Host event and validity](https://github.com/Eidosoma/Cells/blob/d74f519d40b9a9f7488b94b489c6dc4dd865504c/src/cells/operators/wash_schedule.py#L325) · [Finite well with two bound populations](https://github.com/Eidosoma/Cells/blob/d74f519d40b9a9f7488b94b489c6dc4dd865504c/validation/tissue/wash_schedule_fixtures.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/lean/checks/compartment_wash.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/lean/PROGRESS.md#nov21-wash)

[Tested engine d74f519d40b9](https://github.com/Eidosoma/Cells/commit/d74f519d40b9a9f7488b94b489c6dc4dd865504c) · [Evidence checkpoint ceeca19816ac](https://github.com/Eidosoma/Cells/commit/ceeca19816acd761ab68379d67bb0f7426366a1c)

**Engine** `resolved_pump_composite@1`

**Operators** `cells.scheduled_compartment_wash@1`, `cells.templated_polymerisation@1`

[Gene destinations examined by the wash](https://github.com/Eidosoma/Cells/blob/cd3b7b09d8252f445a976f0506767f1aaf38c53d/src/cells/operators/wash_schedule.py#L372) · [Export and degradation fixture](https://github.com/Eidosoma/Cells/blob/cd3b7b09d8252f445a976f0506767f1aaf38c53d/validation/gene_regulation/worlds.py) · [Same-node refusals and separate-node control](https://github.com/Eidosoma/Cells/blob/cd3b7b09d8252f445a976f0506767f1aaf38c53d/tests/unit/test_wash_schedule.py#L167) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/73e7e9d7b639ce366d3a9e26d4b6af8b977d7b67/tests/unit/test_wash_schedule.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/73e7e9d7b639ce366d3a9e26d4b6af8b977d7b67/lean/PROGRESS.md#nov24-main-audit)

[Tested engine cd3b7b09d825](https://github.com/Eidosoma/Cells/commit/cd3b7b09d8252f445a976f0506767f1aaf38c53d) · [Evidence checkpoint 73e7e9d7b639](https://github.com/Eidosoma/Cells/commit/73e7e9d7b639ce366d3a9e26d4b6af8b977d7b67)

## Biological evidence

**Open.** Free tracer after successive known-fraction washes, together with independently measured ligand retained on the surface.

**Unit** µg/mL

### vloemans2024-dilution

Free fluorescein in PBS, successive 10 µL plugs. For the numerical row, use the measured 1.712 µg/mL starting concentration and three 80% exchanges with blank buffer. Fig. 4A–B, printed mean concentrations [Vloemans et al., Lab on a Chip (2024)](https://doi.org/10.1039/D4LC00195H)

- **Evidence role** descriptive
- **Observed** 0.02 µg/mL
- **Predicted** 0.013696 µg/mL

At least three replicates per point, with one SD drawn graphically. The comparison uses rounded printed means. The study notes wall adsorption and a limited instrument range.

The first two 80% washes measured 0.332 and 0.067 µg/mL against 0.3424 and 0.06848. The third mean was 46% above ideal dilution. The experiments address freely dissolved dye. Instantaneous bound-site retention in a biological well remains open. [Dataset manifest](../checks/data/vloemans2024_dilution.json) · [Comparison verdict](../PROGRESS.md#nov21-wash)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
