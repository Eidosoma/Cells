<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A positive endpoint determines one neutral-label survival exponent

With nonnegative old stock and gross arrivals, every positive endpoint up to their sum has exactly one nonnegative loss exponent. At that exponent the label amounts are nonnegative, sum to the endpoint and give shares that sum to one. An occupied pool receiving no arrivals keeps its shares.

## Assumptions

- One well-mixed physical pool has a common constant per-molecule loss rate and constant arrival rates per label during the step. The dimensionless exponent is the loss rate times the step duration.
- Initial shares are nonnegative, include all material, and sum to one. Gross arrivals into each label are nonnegative. At zero loss all old material and all arrivals survive.
- The inferred exponent describes one step in exact arithmetic. A completely empty pool cannot identify a rate. Inferring a rate over multiple steps with varying loss or arrivals is a separate problem.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.ArrivalSurvival.no_loss](../CellsProofs/Chemistry/ArrivalSurvival.lean#L24)
- [CellsProofs.Chemistry.ArrivalSurvival.phi_pos](../CellsProofs/Chemistry/ArrivalSurvival.lean#L27)
- [CellsProofs.Chemistry.ArrivalSurvival.endAmount_decreases](../CellsProofs/Chemistry/ArrivalSurvival.lean#L58)
- [CellsProofs.Chemistry.ArrivalSurvival.survival_exponent_unique](../CellsProofs/Chemistry/ArrivalSurvival.lean#L80)
- [CellsProofs.Chemistry.ArrivalSurvival.labelAmount_nonneg](../CellsProofs/Chemistry/ArrivalSurvival.lean#L98)
- [CellsProofs.Chemistry.ArrivalSurvival.empty_label](../CellsProofs/Chemistry/ArrivalSurvival.lean#L102)
- [CellsProofs.Chemistry.ArrivalSurvival.no_arrivals](../CellsProofs/Chemistry/ArrivalSurvival.lean#L104)
- [CellsProofs.Chemistry.ArrivalSurvival.sum_labelAmounts](../CellsProofs/Chemistry/ArrivalSurvival.lean#L109)
- [CellsProofs.Chemistry.ArrivalSurvival.sum_normalized](../CellsProofs/Chemistry/ArrivalSurvival.lean#L116)

Direct proof subject `cells.operator.neutral_arrival_labels@1`

Proof sources [Mathlib strict convexity of the exponential, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Convex/SpecificFunctions/Basic.lean#L37) · [Mathlib's strictly ordered secant slopes, specialized to exponential arrival survival](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Convex/Slope.lean#L290) · [Mathlib continuity of the derivative-extended secant at zero, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Calculus/DSlope.lean#L107) · [Mathlib intermediate value theorem, imported to establish existence](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Topology/Order/IntermediateValue.lean#L478)

Uses [Neutral arrival-time cohorts share one physical loss rate](fr42-cohort-shares.md)

## Numerical comparison

**Checked.** NumPy and CPU JAX recovered eight constructed exponents from 0 to 1,000 within 2 × 10⁻¹⁴ absolute plus 2 × 10⁻¹³ relative tolerance. The largest absolute share error was 1.11 × 10⁻¹⁶. An empty-row control kept its stored shares. Seven cell-cohort observations in the compiled world agreed with the constant-rate integral within 2.78 × 10⁻¹⁷ fmol.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.neutral_arrival_labels@1`, `cells.local_species_reactions@1`, `cells.scheduled_species_turnover@1`

[Finite-step bisection, allocation and empty-row handling](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/src/cells/numerics/label_shares.py#L64) · [Label declarations, schedules and share update](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/src/cells/operators/species_labels.py) · [Composite half-step calls the label owner](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/src/cells/models/pump_composite.py#L1752) · [One-way reaction reports](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/src/cells/operators/species_reactions.py#L1692) · [Turnover reports](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/src/cells/operators/species_turnover.py#L611) · [Summation along the label axis](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/src/cells/numerics/species_sums.py) · [Compiled twin worlds, window integrals and tolerances](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/tests/unit/test_neutral_arrival_labels.py#L465) · [Composite tissue and production/clearance fixture](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/validation/tissue/secreted_species_fixtures.py) · [Reaction fixture and schedules](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/validation/tissue/species_reactions_fixtures.py) · [Exact endpoint and normalized label amounts](https://github.com/Eidosoma/Cells/blob/7e41a441b51b5a84ec57febb04b1e7a8f801674d/lean/CellsProofs/Chemistry/ArrivalSurvival.lean) · [Quadratic cohort and blank reference](https://github.com/Eidosoma/Cells/blob/7e41a441b51b5a84ec57febb04b1e7a8f801674d/lean/CellsProofs/Chemistry/ArrivalCohort.lean) · [Paired Actn1 isotope signals and GEO sample accessions](https://github.com/Eidosoma/Cells/blob/7e41a441b51b5a84ec57febb04b1e7a8f801674d/lean/checks/data/jovanovic2015_actn1.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/7e41a441b51b5a84ec57febb04b1e7a8f801674d/lean/checks/arrival_survival.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/7e41a441b51b5a84ec57febb04b1e7a8f801674d/lean/PROGRESS.md#fr42-neutral-survival)

[Tested engine 73afa19b5ddc](https://github.com/Eidosoma/Cells/commit/73afa19b5ddcb50405280d6d46207a25c41fec24) · [Evidence checkpoint 7e41a441b51b](https://github.com/Eidosoma/Cells/commit/7e41a441b51b5a84ec57febb04b1e7a8f801674d)

## Biological evidence

**Open.** Independent gross arrivals, physical pool amounts at the two step endpoints, and survivor amounts for each labelled cohort under a common constant loss rate.

**Unit** Amount per cohort and physical pool in a shared unit

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
