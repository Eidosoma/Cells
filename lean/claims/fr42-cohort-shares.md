<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Neutral arrival-time cohorts share one physical loss rate

Allocating one well-mixed population’s loss among cohorts in proportion to their amounts preserves the total loss, the total after one step, and readouts evaluated on those pooled totals. For quadratic loss, a tracked cohort and the difference from an independently evolved blank can give different answers.

## Assumptions

- The finite inventory includes the unlabelled remainder. The physical rate J(N) is computed once on the total N, with J(0) = 0. A cohort of size n receives J(N)·n/N for an occupied pool and zero for an empty pool.
- The step identity uses a common step size. Applying the readout identity to energy or heat requires the engine to evaluate these quantities from the physical pool.
- The exact example starts with two old units and one new unit, with no further arrivals, and uses N′ = −N². The comparison blank begins with only the two old units.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.ArrivalCohort.empty_label](../CellsProofs/Chemistry/ArrivalCohort.lean#L18)
- [CellsProofs.Chemistry.ArrivalCohort.sum_shares](../CellsProofs/Chemistry/ArrivalCohort.lean#L21)
- [CellsProofs.Chemistry.ArrivalCohort.step_total](../CellsProofs/Chemistry/ArrivalCohort.lean#L34)
- [CellsProofs.Chemistry.ArrivalCohort.pooled_readout](../CellsProofs/Chemistry/ArrivalCohort.lean#L44)
- [CellsProofs.Chemistry.ArrivalCohort.quadratic_share](../CellsProofs/Chemistry/ArrivalCohort.lean#L52)
- [CellsProofs.Chemistry.ArrivalCohort.remaining_initial](../CellsProofs/Chemistry/ArrivalCohort.lean#L63)
- [CellsProofs.Chemistry.ArrivalCohort.remaining_derivative](../CellsProofs/Chemistry/ArrivalCohort.lean#L67)
- [CellsProofs.Chemistry.ArrivalCohort.quadratic_example](../CellsProofs/Chemistry/ArrivalCohort.lean#L78)

Proof sources [FR-42 design requirement](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/docs/FEATURE_REQUESTS.md#fr-42--neutral-arrival-time-labels-that-leave-the-dynamics-unchanged) · [D289 adopts share vectors on the physical population](https://github.com/Eidosoma/Cells/blob/4e944a5634adafe1944235e540c6a7f0e564a144/docs/DECISIONS.md#d289-fr-42-is-built-as-option-a-labels-as-share-vectors-on-the-physical-row) · [FR-38 erratum B on class rows and the blank](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/docs/TEMPLATED_POLYMERISATION_LAWS.md#913-erratum-b-the-label-rows-are-not-neutral-labels) · [Mathlib division of a finite sum, imported for the cohort balance](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Field.lean#L22) · [Mathlib quotient derivative, imported for the survivor curve](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Calculus/Deriv/Inv.lean#L143)

## Numerical comparison

**Open.** At time one the new cohort contains 1/4 unit, one third of the 3/4-unit pool. Blank subtraction gives 1/12 unit. An FR-42 engine replay is pending, including window endpoints, cohort reuse and physical energy accounting. FR-38 registration waits for the share-based labels under D288.

## Biological evidence

**Open.** The surviving amount from an identified arrival cohort together with the physical pool total under the same loss conditions.

**Unit** Amount per cohort and total pool amount

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
