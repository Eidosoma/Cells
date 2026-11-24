<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# The lumen tracer count has a binomial equilibrium in a prescribed shell

Let Δ be the lumen standard potential minus the solution standard potential, both in units of RT. With N molecules and equal volumes, the binomial distribution with lumen probability p = 1/(1 + exp Δ) is normalized and satisfies detailed balance at every adjacent count. It is stationary in continuous time. The mean lumen count is Np. For N > 0 the ratio of mean inside to mean outside concentration is exp(−Δ).

## Assumptions

- A single conserved neutral tracer moves between a finite solution pool and a prescribed lumen of the same fixed positive volume. The only events changing its counts are single-molecule crossings. Both places use the same temperature and standard concentration.
- At lumen count k the total entry rate is h(N−k). From k+1 the exit rate back to k is h(k+1) exp Δ. The common per-molecule rate h comes from permeability, area, volume and a fixed wall gate. A positive h permits crossings in both directions.
- The expectation is over the count at equilibrium in physical time. Each count has the probability assigned by the normalized distribution, including the endpoints at zero and N.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.ShellEquilibrium.common_shift](../CellsProofs/Chemistry/ShellEquilibrium.lean#L24)
- [CellsProofs.Chemistry.ShellEquilibrium.inside_outside_odds](../CellsProofs/Chemistry/ShellEquilibrium.lean#L33)
- [CellsProofs.Chemistry.ShellEquilibrium.countLaw_normalized](../CellsProofs/Chemistry/ShellEquilibrium.lean#L44)
- [CellsProofs.Chemistry.ShellEquilibrium.count_mass](../CellsProofs/Chemistry/ShellEquilibrium.lean#L49)
- [CellsProofs.Chemistry.ShellEquilibrium.detailed_balance](../CellsProofs/Chemistry/ShellEquilibrium.lean#L77)
- [CellsProofs.Chemistry.ShellEquilibrium.stationary](../CellsProofs/Chemistry/ShellEquilibrium.lean#L88)
- [CellsProofs.Chemistry.ShellEquilibrium.mean_inside_count](../CellsProofs/Chemistry/ShellEquilibrium.lean#L104)
- [CellsProofs.Chemistry.ShellEquilibrium.mean_concentration_ratio](../CellsProofs/Chemistry/ShellEquilibrium.lean#L132)

Direct proof subject `cells.prescribed_shell@1`, `cells.shell_permeation@1`

Proof sources [D323 absolute potentials, exit factor and scope](https://github.com/Eidosoma/Cells/blob/9eb9890a91ad6049be9b2e5a1bfae7b383a464eb/docs/DECISIONS.md#L10193-L10201) · [Cells shell geometry and reverse rate](https://github.com/Eidosoma/Cells/blob/9eb9890a91ad6049be9b2e5a1bfae7b383a464eb/src/cells/models/assembly_lineages_v2/kernel.py#L279-L298) · [Mathlib binomial probability mass function, imported and specialized to the lumen count](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Probability/ProbabilityMassFunction/Binomial.lean#L23-L56) · [Mathlib adjacent binomial coefficient recurrence, imported for detailed balance](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Data/Nat/Choose/Basic.lean#L204-L212) · [Cells real-valued point mass, reused from the pool-withdrawal proof](../CellsProofs/Chemistry/PoolWithdrawalEnergy.lean#L16) · [Exact occupancy and potential-convention checks](../checks/chemistry/ShellEquilibrium.lean)

Uses [Shell entry and exit depend on conductance and the gate’s own forms](prescribed-shell-rates.md)

## Numerical comparison

**Checked.** The frozen development engine at 61d823be matched the reference binomial probabilities within 10⁻¹² for 12 tracers at Δ = ln 2, equal potentials and the undeclared default. Its CPU test detected the incorrect offset interpretation and verified ledger closure from both extreme initial distributions.

**Engine** `cells.assembly_lineages@2`, `cells.prescribed_shell@1`, `cells.shell_permeation@1`

[Absolute standard potential at each phase](https://github.com/Eidosoma/Cells/blob/61d823be7e3913f44a4dd497507a8e8256151584/src/cells/models/assembly_lineages_v2/world.py#L123) · [Shell rate and exit factor](https://github.com/Eidosoma/Cells/blob/61d823be7e3913f44a4dd497507a8e8256151584/src/cells/models/assembly_lineages_v2/kernel.py#L279) · [Engine comparison driver, binomial probabilities and planted offset](https://github.com/Eidosoma/Cells/blob/61d823be7e3913f44a4dd497507a8e8256151584/tests/unit/test_assembly_lineages_v2_geometry.py#L806) · [Exact binomial law, stationarity and ratio](https://github.com/Eidosoma/Cells/blob/69176ea710e804bccf611a6f95c155631c4d16a9/lean/CellsProofs/Chemistry/ShellEquilibrium.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/69176ea710e804bccf611a6f95c155631c4d16a9/lean/checks/chemistry/ShellEquilibrium.lean) · [Recorded result](https://github.com/Eidosoma/Cells/blob/69176ea710e804bccf611a6f95c155631c4d16a9/lean/PROGRESS.md#fr48-shell-equilibrium)

[Tested engine 61d823be7e39](https://github.com/Eidosoma/Cells/commit/61d823be7e3913f44a4dd497507a8e8256151584) · [Evidence checkpoint 69176ea710e8](https://github.com/Eidosoma/Cells/commit/69176ea710e804bccf611a6f95c155631c4d16a9)

## Biological evidence

**Open.** Equilibrium counts of one conserved neutral tracer inside and outside an equal-volume compartment pair, with an independently determined transfer free energy at the same temperature.

**Unit** molecules and dimensionless concentration ratio

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
