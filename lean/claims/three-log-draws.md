<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A short sum of logarithms prices ordered reaction draws

For a feasible number of ordered draws, summing one logarithm per draw gives the logarithm of the falling factorial. The engine's three-term mask therefore equals the log-factorial difference for every admitted reaction order.

## Assumptions

- Counts and arities are natural numbers with 0 ≤ k ≤ 3 and k ≤ n. The exact-real sum excludes every inactive term. The numerical controls also exercise infeasible sides masked by the callers.
- The isolated dilute reactant has unit concentration scale and encounter extent. The earlier catalog covers the additional membrane normalization and excess free energy.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.AssemblyKinetics.sum_log_draws](../CellsProofs/Chemistry/AssemblyKinetics.lean#L48)
- [CellsProofs.Chemistry.AssemblyKinetics.three_log_draws](../CellsProofs/Chemistry/AssemblyKinetics.lean#L61)

Direct proof subject `cells.reaction.stochastic_mass_action@1`, `cells.reaction.phase_exchange@1`

Proof sources [Mathlib descending-factorial recursion, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Data/Nat/Factorial/Basic.lean#L316) · [Existing Cells log-draw identity](../CellsProofs/Chemistry/AssemblyKinetics.lean#L33) · [Three-term calculation and feasible-side mask](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/mass_action.py#L76-L136)

Uses [Finite molecule counts set stochastic encounter rates and paired event heat](assembly-stochastic-encounter.md)

## Numerical comparison

**Checked.** Across 46 feasible count–arity pairs through 2²⁰ molecules, both backends and both direction kernels agreed with the log of the integer product to 3.55 × 10⁻¹⁵. All six infeasible pairs returned a masked direction. The earlier maximum log error was 1.20 × 10⁻⁹.

**Engine** `cells.assembly_lineages@2`, `cells.stochastic_mass_action@1`, `cells.phase_exchange@1`

[Three-term log product and mass-action direction](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/mass_action.py#L76-L136) · [Phase-exchange direction](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/exchange.py#L39-L61) · [Arity limit of three on either side](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/world.py) · [Host log-factorial table used by the earlier engine](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages/ledger.py#L77-L80) · [Log of the descending factorial and finite masked sum](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/CellsProofs/Chemistry/AssemblyKinetics.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/vesicle_events.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/PROGRESS.md#ol5-short-draws)

[Tested engine 329e9e395ac1](https://github.com/Eidosoma/Cells/commit/329e9e395ac117998657a21eb827192d34314107) · [Evidence checkpoint ad1f96418722](https://github.com/Eidosoma/Cells/commit/ad1f96418722d25876b38b5a5f38996512d6a32c)

## Biological evidence

**Open.** Counts and occupancy for a finite number of accessible reaction partners. Measured examples are recorded with the parent encounter claim.

**Unit** Log of a dimensionless count product

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
