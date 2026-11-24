<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Passive equilibrium constants multiply to one around a closed reaction cycle

When signed reaction extents return every species to its starting amount, their standard free-energy changes sum to zero. For signed integer traversals the product of the equilibrium constants raised to those powers is one (Wegscheider’s condition). An independent energy offset on one reaction leaves a residual equal to the offset times that reaction’s signed extent.

## Assumptions

- At one site each passive route uses the products-minus-reactants column of a finite integer stoichiometric matrix. Each species has one dimensionless standard potential μ°/(RT). All routes use the same temperature and standard concentration. The cycle balances every species, including any explicitly represented ligand.
- For positive activities, the equilibrium constant is the product-to-reactant activity quotient at zero affinity, exp(−ΔG°/RT). The Cells rate uses the reciprocal as its reverse multiplier. A negative traversal uses the reciprocal equilibrium constant. The cycle has no external work or chemostat exchange.
- The proof uses exact arithmetic and holds for any values of the shared potentials. Determining their accuracy requires independent equilibrium measurements.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.ReactionCycles.zero_affinity_iff_quotient](../CellsProofs/Chemistry/ReactionCycles.lean#L16)
- [CellsProofs.Chemistry.ReactionCycles.cycle_energy_sum](../CellsProofs/Chemistry/ReactionCycles.lean#L31)
- [CellsProofs.Chemistry.ReactionCycles.wegscheider_product](../CellsProofs/Chemistry/ReactionCycles.lean#L39)
- [CellsProofs.Chemistry.ReactionCycles.cycle_energy_one_offset](../CellsProofs/Chemistry/ReactionCycles.lean#L57)

Direct proof subject `cells.local_species_reactions@1`

Proof sources [Cells stoichiometric columns and shared species potentials](https://github.com/Eidosoma/Cells/blob/75e67d81b14d3328be0625603ffa533b6c16b075/src/cells/operators/species_reactions.py#L1035-L1056) · [Cells forward and reverse log rates and affinity](https://github.com/Eidosoma/Cells/blob/75e67d81b14d3328be0625603ffa533b6c16b075/src/cells/laws/reactions/mass_action.py#L6-L23) · [Mathlib matrix and dot product, imported for the cycle energy](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Data/Matrix/Mul.lean#L661-L665) · [Mathlib exponential of a finite sum, imported for the cycle product](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Data/Complex/Exponential.lean#L214-L216) · [Mathlib exponential and integer powers, imported for reverse traversals](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/SpecialFunctions/Pow/Real.lean#L49-L55) · [crnt-lean’s integer cycle product for paired channels, reviewed on its 4.34 pin. Cells proves the signed-route version locally](https://github.com/marpaia/crnt-lean/blob/7386777488a41efd92e6abc2bccf889fb611660e/CRNT/Equilibria/WegscheiderGenerators.lean#L99-L149) · [Cells three-route cycle, direction and energy-offset checks in Lean](../checks/chemistry/PassiveCycle.lean)

## Numerical comparison

**Open.** A compiled comparison would need the equilibrium quotients for all routes in one closed passive loop and a roundoff allowance for their product.

## Biological evidence

**Open.** Independently determined equilibrium activity quotients for all reactions in one cycle at matched temperature, pH, free Mg and ionic strength.

- [Independent equilibrium constants for all legs of one matched ATP reaction cycle give a product of one.](../WET_LAB_EVIDENCE.md#pair-atp-hydrolysis-route-closure) · Comparison unresolved

**Unit** dimensionless equilibrium quotient

### benzinger1959_glutamine

A measured glutaminase equilibrium and literature glutamine-synthetase equilibria were combined at 37 °C. pp. 405–406, calorimetric equilibrium and thermodynamic cycle. [Benzinger et al. (1959)](https://doi.org/10.1042/bj0710400)

- **Evidence role** descriptive

The quoted uncertainty belongs to the derived reaction under its stated Mg convention.

For the specific MgATP to MgADP and hydrogen phosphate reaction the inferred standard energy was −7.0 ± 0.17 kcal/mol. The synthetase leg came from other investigators. [Dataset manifest](../checks/data/paired_preparation_controls.json) · [Comparison verdict](../PROGRESS.md#preparation-evidence-review)

### guynn1973_acetyl

At pH 7.0, 38 °C and ionic strength 0.25 M the authors combined their equilibrium measurement with a prior acetyl-CoA hydrolysis energy. Combined acetate kinase and phosphate acetyltransferase equilibrium, pp. 6966–6972. [Guynn and Veech (1973)](https://pubmed.ncbi.nlm.nih.gov/4355193/)

- **Evidence role** descriptive

Free Mg and transformed nucleotide species materially change the reported standard energy.

ATP hydrolysis at 1 mM free Mg gave −31.80 kJ/mol. The ATP–citrate lyase equilibrium was derived using the ATP result. [Dataset manifest](../checks/data/paired_preparation_controls.json) · [Comparison verdict](../PROGRESS.md#preparation-evidence-review)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
