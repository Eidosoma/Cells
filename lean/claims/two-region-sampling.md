<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A two-region sample represents the chamber under proportional withdrawal or equal concentrations

A finite draw has the chamber’s mean concentration exactly when the starting concentrations match or each region contributes the same fraction of its own volume. If region A is richer, drawing a larger fraction of A enriches the sample. Collected tracer and the dye left in each region account for the initial inventories and refill.

## Assumptions

- There are two internally well-mixed regions of positive volume, and the total drawn volume is positive. Each local draw lies between zero and its available volume. A zero local draw has no event.
- Each draw uses the pre-refill concentration, with no concurrent transport. The amount-above-background example uses a common background for the two initial regions and the refill. The local draw volumes and initial mixing are declared.

## Lean proof

**Proved**

- [CellsProofs.Tissue.RegionalSampling.inventory](../CellsProofs/Tissue/RegionalSampling.lean#L22)
- [CellsProofs.Tissue.RegionalSampling.excess_and_refill](../CellsProofs/Tissue/RegionalSampling.lean#L33)
- [CellsProofs.Tissue.RegionalSampling.concentration_bias](../CellsProofs/Tissue/RegionalSampling.lean#L43)
- [CellsProofs.Tissue.RegionalSampling.representative_iff](../CellsProofs/Tissue/RegionalSampling.lean#L52)
- [CellsProofs.Tissue.RegionalSampling.enrichment_iff](../CellsProofs/Tissue/RegionalSampling.lean#L61)

Direct proof subject `cells.scheduled_compartment_wash@1`

Proof sources [Cells single-region wash inventory, summed across a finite set](../CellsProofs/Tissue/CompartmentWash.lean#L16) · [Mathlib fraction equality for nonzero denominators, imported for the two-region criterion](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/GroupWithZero/Units/Basic.lean#L426-L427)

Uses [A partial wash dilutes free tracer and preserves its inventory](compartment-wash.md)

## Numerical comparison

**Checked.** The three compiled 100 pL draws collected 8, 5 and 6.5 fmol above background. The corresponding regional remainders were (0, 2), (2.5, 2.5) and (2, 1.5) fmol within rounding. The compiled local inventories closed at all three recorded times in every case.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.scheduled_compartment_wash@1`

[Pre-refill sample, refill and amount update](https://github.com/Eidosoma/Cells/blob/ee0b8106406eb26e57ab1b0c34e16ed6c3f83a2b/src/cells/operators/wash_schedule.py#L415-L494) · [FR-37 two-region worlds and public runner](https://github.com/Eidosoma/Cells/blob/ee0b8106406eb26e57ab1b0c34e16ed6c3f83a2b/validation/sampling/uneven_draw.py) · [Well-mixed wash fixture](https://github.com/Eidosoma/Cells/blob/ee0b8106406eb26e57ab1b0c34e16ed6c3f83a2b/validation/tissue/wash_schedule_fixtures.py#L30-L37) · [Finite-node tissue fixture](https://github.com/Eidosoma/Cells/blob/ee0b8106406eb26e57ab1b0c34e16ed6c3f83a2b/validation/tissue/secreted_species_fixtures.py#L92) · [Regional collection and remainder regression](https://github.com/Eidosoma/Cells/blob/ee0b8106406eb26e57ab1b0c34e16ed6c3f83a2b/tests/unit/test_wash_schedule.py#L527) · [Regional sampling proof](https://github.com/Eidosoma/Cells/blob/9a39ed6f20c95e17809b594a9800a41633d8c552/lean/CellsProofs/Tissue/RegionalSampling.lean) · [Single-region inventory proof](https://github.com/Eidosoma/Cells/blob/9a39ed6f20c95e17809b594a9800a41633d8c552/lean/CellsProofs/Tissue/CompartmentWash.lean) · [Two-outlet dye measurement](https://github.com/Eidosoma/Cells/blob/9a39ed6f20c95e17809b594a9800a41633d8c552/lean/checks/data/johnson2006_branch_dye.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/9a39ed6f20c95e17809b594a9800a41633d8c552/lean/checks/regional_sampling.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/9a39ed6f20c95e17809b594a9800a41633d8c552/lean/PROGRESS.md#fr37-regional-sampling)

[Tested engine ee0b8106406e](https://github.com/Eidosoma/Cells/commit/ee0b8106406eb26e57ab1b0c34e16ed6c3f83a2b) · [Evidence checkpoint 9a39ed6f20c9](https://github.com/Eidosoma/Cells/commit/9a39ed6f20c95e17809b594a9800a41633d8c552)

## Biological evidence

**Open.** Collected dye and both post-draw regional amounts in a finite vessel with measured source concentrations and draw volumes.

**Unit** Fraction of stock dye concentration

### johnson2006_branch_dye

Equal rates of 1 g/L Rhodamine dye solution and distilled water fed a rough-walled glass fracture replica. The researchers measured each outlet flow and dye concentration. Methods paragraph 19 and continuous flow test 1, paragraph 33 and Figure 5a. [Johnson, Brown and Stockman (2006), Journal of Geophysical Research](https://doi.org/10.1029/2005JB004087)

- **Evidence role** descriptive

The authors give rounded values for the half-flow case. Those values carry no reported concentration error bar.

At equal outlet flow the two branches measured about 75% and 25% of stock concentration. This supports enrichment in a physical flow system. The regional remainders after a finite draw remain unmeasured. [Dataset manifest](../checks/data/johnson2006_branch_dye.json) · [Comparison verdict](../PROGRESS.md#fr37-regional-sampling)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
