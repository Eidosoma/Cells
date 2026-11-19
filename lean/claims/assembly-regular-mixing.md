<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Pair interactions change the energy of membrane entry with composition

Updating the symmetric pair energy equals recomputing it from all membrane counts. For A entering a binary membrane with b molecules of B and total N, the excess insertion energy is χb²/[N(N + 1)] and the bulk excess chemical potential is χ(b/N)².

## Assumptions

- The pair matrix is symmetric and counts remain in their physical domain. For the binary result the diagonal is zero, χ is the unlike-pair energy in kBT and N is positive.
- The bulk comparison treats the cholesterol/DOPC membrane as a homogeneous binary mixture at fixed temperature. It uses one composition-independent χ and a fitted scale for the cholesterol crystal reference.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.AssemblyMixing.quadratic_update](../CellsProofs/Chemistry/AssemblyMixing.lean#L94)
- [CellsProofs.Chemistry.AssemblyMixing.regular_change](../CellsProofs/Chemistry/AssemblyMixing.lean#L105)
- [CellsProofs.Chemistry.AssemblyMixing.binary_specialization](../CellsProofs/Chemistry/AssemblyMixing.lean#L115)
- [CellsProofs.Chemistry.AssemblyMixing.binary_insert](../CellsProofs/Chemistry/AssemblyMixing.lean#L121)
- [CellsProofs.Chemistry.AssemblyMixing.binary_chemical_potential](../CellsProofs/Chemistry/AssemblyMixing.lean#L128)

Direct proof subject `cells.regular_mixing@1`

Proof sources [Imported Mathlib dot-product and matrix-vector identity](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Data/Matrix/Mul.lean#L662)

Uses [Whole-molecule counts set the ideal mixing cost of membrane entry](assembly-ideal-mixing.md)

## Numerical comparison

**Checked.** Under both measures, the signed pair matrix matched the reference energy within 2.14 × 10⁻¹⁴ kBT. The reversible edge identities passed. With equal counts and χ = 1, adding A cost an extra 0.214286 kBT at N = 6 and 0.245902 at N = 60.

**Engine** `cells.assembly_lineages@2`, `cells.ideal_mixing@1`, `cells.regular_mixing@1`, `cells.stochastic_mass_action@1`, `cells.transition_state_factor@1`

[Ideal free energy and step increment](https://github.com/Eidosoma/Cells/blob/1e77a8876cc28e23e9ffed443e62c465b6f8fe3c/src/cells/models/assembly_lineages_v2/ideal_mixing.py#L64) · [Cached pair-energy update](https://github.com/Eidosoma/Cells/blob/1e77a8876cc28e23e9ffed443e62c465b6f8fe3c/src/cells/models/assembly_lineages_v2/regular_mixing.py#L95) · [Reverse-rate composition](https://github.com/Eidosoma/Cells/blob/1e77a8876cc28e23e9ffed443e62c465b6f8fe3c/src/cells/models/assembly_lineages_v2/kernel.py#L254) · [Registered seven-step world](https://github.com/Eidosoma/Cells/blob/1e77a8876cc28e23e9ffed443e62c465b6f8fe3c/validation/ool/references/designs/ol1_wa.world.json) · [Exact reference weight and energy](https://github.com/Eidosoma/Cells/blob/1e77a8876cc28e23e9ffed443e62c465b6f8fe3c/validation/ool/references/laws.py#L168) · [Independent edge identity](https://github.com/Eidosoma/Cells/blob/1e77a8876cc28e23e9ffed443e62c465b6f8fe3c/validation/ool/references/detailed_balance.py#L155) · [Independent event ledger](https://github.com/Eidosoma/Cells/blob/1e77a8876cc28e23e9ffed443e62c465b6f8fe3c/validation/ool/references/ledger.py#L85) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/2c18459cbac3a33f58551194340afe2b2c565b5a/lean/checks/assembly_mixing.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/2c18459cbac3a33f58551194340afe2b2c565b5a/lean/PROGRESS.md#19-november-2026--ideal-and-regular-assembly-mixing)

[Tested engine 1e77a8876cc2](https://github.com/Eidosoma/Cells/commit/1e77a8876cc28e23e9ffed443e62c465b6f8fe3c) · [Evidence checkpoint 2c18459cbac3](https://github.com/Eidosoma/Cells/commit/2c18459cbac3a33f58551194340afe2b2c565b5a)

## Biological evidence

**Open.** Equilibrium cholesterol activity as a function of membrane mole fraction under a binary interaction model.

**Unit** dimensionless activity relative to crystalline cholesterol

### shaw2023_dopc_cholesterol_activity@1

Protein-free DOPC/cholesterol large unilamellar vesicles equilibrated with methyl-beta-cyclodextrin at room temperature. Activity 1 refers to crystalline cholesterol. Table S1, printed page 13, gives the 25 DOPC readings and both 68% confidence half-widths. [Shaw et al. (2023), Fig. 2A and Table S1](https://doi.org/10.1016/j.bpj.2023.02.009)

- **Evidence role** descriptive
- **Evaluation** Leave one of 23 distinct cholesterol compositions out at a time. Keep repeated readings at the same composition together.

Activity and mole fraction come from the same fit and share a calibration across samples. The published marginal intervals omit their covariance. The comparison also reports sensitivity to weighting by both intervals.

The interaction term lowered the held-composition activity error from 0.0953 to 0.0782. At 45.6 mol% it predicted 0.677 against 0.45 ± 0.02. Weighting by both measured uncertainties shifted the fitted interaction from 0.75 to 1.02 kBT. [Dataset manifest](../checks/data/shaw2023_dopc.json) · [Comparison verdict](../PROGRESS.md#19-november-2026--ideal-and-regular-assembly-mixing)

### parker2004_dopc_crystal_onset@1

Hydrated DOPC/cholesterol samples equilibrated at 23 °C. Optical microscopy detected cholesterol monohydrate. Figure 3 and its accompanying microscopy results give a crystal-onset mole fraction of 0.66 ± 0.02 across three series. [Parker et al. (2004), Fig. 3](https://doi.org/10.1016/S0006-3495(04)74221-6)

- **Evidence role** held out from fitting
- **Fit** Shaw Table S1 DOPC activity curve
- **Evaluation** Parker Fig. 3 crystal-onset composition

The ±0.02 in composition has no stated confidence level. At equilibrium with the same solid chemical potential, onset corresponds to activity 1. Shaw did not characterize its crystal polymorph.

At the independently measured crystal onset (66 ± 2 mol%), the fixed fit predicts 0.804. The ideal prediction, 1.119, is closer to the expected activity of 1 if the crystal references match. [Dataset manifest](../checks/data/parker2004_dopc_saturation.json) · [Comparison verdict](../PROGRESS.md#19-november-2026--ideal-and-regular-assembly-mixing)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
