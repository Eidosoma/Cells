<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Rosenbrock reaction steps preserve closed material inventories

A weighted sum of species amounts that balances each reaction is preserved by every exact Rosenbrock stage solve, by the accepted endpoint and throughout the Rodas4 dense polynomial used to locate crossings.

## Assumptions

- The field is differentiable near the starting state. The inventory is linear and each stoichiometric change balances it at every stage. The fixed Jacobian is the derivative of that field, the scalar shift is nonzero and the stage equations are solved exactly.
- The inventory covers a closed reaction interval. Reservoir transfers, boundary events and changes of representation require their own bookkeeping.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.RosenbrockInventory.weighted_sum_zero](../CellsProofs/Chemistry/RosenbrockInventory.lean#L19)
- [CellsProofs.Chemistry.RosenbrockInventory.jacobian_zero](../CellsProofs/Chemistry/RosenbrockInventory.lean#L25)
- [CellsProofs.Chemistry.RosenbrockInventory.stages_zero](../CellsProofs/Chemistry/RosenbrockInventory.lean#L33)
- [CellsProofs.Chemistry.RosenbrockInventory.step_inventory](../CellsProofs/Chemistry/RosenbrockInventory.lean#L49)
- [CellsProofs.Chemistry.RosenbrockInventory.dense_inventory](../CellsProofs/Chemistry/RosenbrockInventory.lean#L56)

Direct proof subject `cells.assembly_representation.rate_equations@1`

Proof sources [Imported Mathlib chain rule for Fréchet derivatives](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Calculus/FDeriv/Comp.lean#L86) · [Imported Mathlib derivative of a continuous linear map](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Calculus/FDeriv/Linear.lean#L57) · [Imported Mathlib uniqueness of the derivative](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Calculus/FDeriv/Basic.lean#L491)

## Numerical comparison

**Checked.** In a closed A + B ⇌ C run, A+C and B+C started at 11,000 and 3,000 molecule units. The first accepted endpoint matched the first saved row bit for bit. All six stages and five dense samples preserved both totals within float64 rounding. Across 64 accepted steps the four saved observations had a maximum relative drift of 9.10 × 10⁻¹⁶ against the native 10⁻¹² tolerance. The unweighted molecule count changed by 653.29.

**Engine** `cells.assembly_lineages@2`, `cells.rate_equations@1`, `cells.ideal_mixing@1`, `cells.stochastic_mass_action@1`

[Shifted stage equations and dense polynomial](https://github.com/Eidosoma/Cells/blob/4944314d4d8b77c6a42ce1441503ac3e51de9dcb/src/cells/numerics/rosenbrock_dense.py#L123) · [Reaction field and finite material accounts](https://github.com/Eidosoma/Cells/blob/4944314d4d8b77c6a42ce1441503ac3e51de9dcb/src/cells/models/assembly_lineages_v2/rate_equations.py#L927) · [Compiled step with the forward-mode Jacobian](https://github.com/Eidosoma/Cells/blob/4944314d4d8b77c6a42ce1441503ac3e51de9dcb/src/cells/models/assembly_lineages_v2/rate_equations.py#L1105) · [Accepted steps and observation stops](https://github.com/Eidosoma/Cells/blob/4944314d4d8b77c6a42ce1441503ac3e51de9dcb/src/cells/models/assembly_lineages_v2/rate_equations.py#L1428) · [Saved material-inventory check](https://github.com/Eidosoma/Cells/blob/4944314d4d8b77c6a42ce1441503ac3e51de9dcb/src/cells/models/assembly_lineages_v2/rate_equations.py#L1866) · [Public assembly run dispatch](https://github.com/Eidosoma/Cells/blob/4944314d4d8b77c6a42ce1441503ac3e51de9dcb/src/cells/models/assembly_lineages_v2/runner.py#L602) · [Native record writer](https://github.com/Eidosoma/Cells/blob/4944314d4d8b77c6a42ce1441503ac3e51de9dcb/src/cells/models/assembly_lineages_v2/records.py#L874) · [Finite single-pool world](https://github.com/Eidosoma/Cells/blob/4944314d4d8b77c6a42ce1441503ac3e51de9dcb/tests/unit/test_assembly_lineages_v2_rate_equations.py#L50) · [Native reaction and experiment definitions](https://github.com/Eidosoma/Cells/blob/4944314d4d8b77c6a42ce1441503ac3e51de9dcb/tests/assembly_lineage_v2_fixtures.py#L80) · [Registered mass-action rate limit](https://github.com/Eidosoma/Cells/blob/4944314d4d8b77c6a42ce1441503ac3e51de9dcb/src/cells/models/assembly_lineages_v2/mass_action.py) · [Linear inventories through the stage equations](https://github.com/Eidosoma/Cells/blob/a4f8c8276421e20668781f71536fb356c0abb679/lean/CellsProofs/Chemistry/RosenbrockInventory.lean) · [Reversible sugar-pair world](https://github.com/Eidosoma/Cells/blob/a4f8c8276421e20668781f71536fb356c0abb679/lean/checks/rate_equation_flux.py#L35) · [Rabbit-muscle PGI concentration recovery](https://github.com/Eidosoma/Cells/blob/a4f8c8276421e20668781f71536fb356c0abb679/lean/checks/data/kahana1960_pgi_recovery.json) · [Extract concentrations and independent kinetic ratio](https://github.com/Eidosoma/Cells/blob/a4f8c8276421e20668781f71536fb356c0abb679/lean/checks/data/pgi_flux_direction.json) · [Pinned Mathlib dependency](https://github.com/Eidosoma/Cells/blob/a4f8c8276421e20668781f71536fb356c0abb679/lean/lake-manifest.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/a4f8c8276421e20668781f71536fb356c0abb679/lean/checks/rosenbrock_inventory.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/a4f8c8276421e20668781f71536fb356c0abb679/lean/PROGRESS.md#rosenbrock-reaction-inventory)

[Tested engine 4944314d4d8b](https://github.com/Eidosoma/Cells/commit/4944314d4d8b77c6a42ce1441503ac3e51de9dcb) · [Evidence checkpoint a4f8c8276421](https://github.com/Eidosoma/Cells/commit/a4f8c8276421e20668781f71536fb356c0abb679)

## Biological evidence

**Not assessable.** Total soluble glucose-6-phosphate and fructose-6-phosphate during their reversible interconversion.

- [G6P and F6P alone form a closed measured inventory throughout these enzyme assays.](../WET_LAB_EVIDENCE.md#pair-pgi-pair-closure) · Comparison unresolved

A partially purified enzyme preparation recovered approximately the starting total. One cell-extract time course lost 22.29% of the measured pair. Recovery uncertainty and the disposition of material outside the pair are unresolved.

**Unit** mM

### kahana1960_pgi_recovery

Partially purified rabbit-muscle PGI at 30 °C and pH 8.0. Cells starts at the positive 15-minute pair and advances 900 s. Its conserved total is independent of the kinetic parameters. Table II, experiment B, 0, 15 and 30 minutes. Figure 3 describes the assay conditions. [Kahana et al. (1960), Table II, experiment B](https://doi.org/10.1016/S0021-9258(18)64594-6)

- **Evidence role** descriptive
- **Observed** 2.505 mM
- **Predicted** 2.5 mM

The concentrations share a sequential absorbance assay. The paper reports rounded concentrations without a replicate uncertainty for their sum.

The measured totals were 2.500, 2.500 and 2.505 mM. The final value exceeds the closed-pair prediction by 0.005 mM (0.2%). [Dataset manifest](../checks/data/kahana1960_pgi_recovery.json) · [Comparison verdict](../PROGRESS.md#rosenbrock-reaction-inventory)

### eicher2012_pgi_direction

The same two E. coli K-12 extract courses at 25 °C and pH 7.2 also supply the reaction-direction comparison. Here the observable is the sum of both sugars. Unsmoothed PGI worksheet, F4:H4 to F33:H33 and K4:M4 to K29:M29. [Eicher et al. (2012), Fig. 5 and PGI worksheet](https://doi.org/10.3390/metabo2040818)

- **Evidence role** descriptive

The workbook gives no pointwise uncertainty or covariance. Neither course measures material outside the soluble pair.

Dataset 2 fell from 6.8872 to 5.3523 mM (−22.29%). Dataset 3 rose from 9.5845 to 9.6838 mM (+1.04%). Conservation of the two measured sugars in the extract is unresolved. [Dataset manifest](../checks/data/pgi_flux_direction.json) · [Comparison verdict](../PROGRESS.md#rosenbrock-reaction-inventory)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
