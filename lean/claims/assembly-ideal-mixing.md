<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Whole-molecule counts set the ideal mixing cost of membrane entry

For a membrane with N molecules and a molecules of the incoming species, the activity for adding one molecule relative to its standard state is (a + 1)/(N + 1 − c). A finite source pool also contributes its count and standard concentration to the transfer energy.

## Assumptions

- The ideal term uses log factorials of integer counts. The measure offset c is 0 or 1. For N ≥ c the activity formula applies directly. The first insertion into an empty membrane has only the entering species’ standard energy.
- The equilibrium experiment measures bulk activity relative to cholesterol crystals. The ideal bulk curve is A = s x with one fitted reference-state scale s and cholesterol mole fraction x.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.AssemblyMixing.site_add](../CellsProofs/Chemistry/AssemblyMixing.lean#L20)
- [CellsProofs.Chemistry.AssemblyMixing.measure_shift](../CellsProofs/Chemistry/AssemblyMixing.lean#L29)
- [CellsProofs.Chemistry.AssemblyMixing.ideal_insert](../CellsProofs/Chemistry/AssemblyMixing.lean#L48)
- [CellsProofs.Chemistry.AssemblyMixing.ideal_insertion_activity](../CellsProofs/Chemistry/AssemblyMixing.lean#L56)
- [CellsProofs.Chemistry.AssemblyMixing.ideal_activity_error](../CellsProofs/Chemistry/AssemblyMixing.lean#L65)
- [CellsProofs.Chemistry.AssemblyMixing.first_insertion](../CellsProofs/Chemistry/AssemblyMixing.lean#L71)
- [CellsProofs.Chemistry.AssemblyMixing.ideal_transfer](../CellsProofs/Chemistry/AssemblyMixing.lean#L81)

Direct proof subject `cells.ideal_mixing@1`

## Numerical comparison

**Checked.** Both registered measures agreed with exact-factorial state weights on 592 compositions in the ideal-only world, within 2.14 × 10⁻¹⁴ kBT. Reference rates and independent ledger replay passed. At equal A and B counts with N = 6 the insertion activities were 4/7 and 4/6.

**Engine** `cells.assembly_lineages@2`, `cells.ideal_mixing@1`, `cells.regular_mixing@1`, `cells.stochastic_mass_action@1`, `cells.transition_state_factor@1`

[Ideal free energy and step increment](https://github.com/Eidosoma/Cells/blob/1e77a8876cc28e23e9ffed443e62c465b6f8fe3c/src/cells/models/assembly_lineages_v2/ideal_mixing.py#L64) · [Cached pair-energy update](https://github.com/Eidosoma/Cells/blob/1e77a8876cc28e23e9ffed443e62c465b6f8fe3c/src/cells/models/assembly_lineages_v2/regular_mixing.py#L95) · [Reverse-rate composition](https://github.com/Eidosoma/Cells/blob/1e77a8876cc28e23e9ffed443e62c465b6f8fe3c/src/cells/models/assembly_lineages_v2/kernel.py#L254) · [Registered seven-step world](https://github.com/Eidosoma/Cells/blob/1e77a8876cc28e23e9ffed443e62c465b6f8fe3c/validation/ool/references/designs/ol1_wa.world.json) · [Exact reference weight and energy](https://github.com/Eidosoma/Cells/blob/1e77a8876cc28e23e9ffed443e62c465b6f8fe3c/validation/ool/references/laws.py#L168) · [Independent edge identity](https://github.com/Eidosoma/Cells/blob/1e77a8876cc28e23e9ffed443e62c465b6f8fe3c/validation/ool/references/detailed_balance.py#L155) · [Independent event ledger](https://github.com/Eidosoma/Cells/blob/1e77a8876cc28e23e9ffed443e62c465b6f8fe3c/validation/ool/references/ledger.py#L85) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/2c18459cbac3a33f58551194340afe2b2c565b5a/lean/checks/assembly_mixing.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/2c18459cbac3a33f58551194340afe2b2c565b5a/lean/PROGRESS.md#19-november-2026--ideal-and-regular-assembly-mixing)

[Tested engine 1e77a8876cc2](https://github.com/Eidosoma/Cells/commit/1e77a8876cc28e23e9ffed443e62c465b6f8fe3c) · [Evidence checkpoint 2c18459cbac3](https://github.com/Eidosoma/Cells/commit/2c18459cbac3a33f58551194340afe2b2c565b5a)

## Biological evidence

**Open.** Equilibrium cholesterol activity as a function of membrane mole fraction.

**Unit** dimensionless activity relative to crystalline cholesterol

### shaw2023_dopc_cholesterol_activity@1

Protein-free DOPC/cholesterol large unilamellar vesicles equilibrated with methyl-beta-cyclodextrin at room temperature. Activity 1 refers to crystalline cholesterol. Table S1, printed page 13, gives the 25 DOPC readings and both 68% confidence half-widths. [Shaw et al. (2023), Fig. 2A and Table S1](https://doi.org/10.1016/j.bpj.2023.02.009)

- **Evidence role** descriptive
- **Evaluation** Leave one of 23 distinct cholesterol compositions out at a time. Keep repeated readings at the same composition together.

Activity and mole fraction come from the same fit and share a calibration across samples. The published marginal intervals omit their covariance. The comparison also reports sensitivity to weighting by both intervals.

Holding out each composition in turn gave a root-mean-square activity error of 0.0953. At 45.6 mol% the ideal prediction was 0.791 and the measured activity was 0.45 ± 0.02. This bulk series leaves the finite-count convention open. [Dataset manifest](../checks/data/shaw2023_dopc.json) · [Comparison verdict](../PROGRESS.md#19-november-2026--ideal-and-regular-assembly-mixing)

### parker2004_dopc_crystal_onset@1

Hydrated DOPC/cholesterol samples equilibrated at 23 °C. Optical microscopy detected cholesterol monohydrate. Figure 3 and its accompanying microscopy results give a crystal-onset mole fraction of 0.66 ± 0.02 across three series. [Parker et al. (2004), Fig. 3](https://doi.org/10.1016/S0006-3495(04)74221-6)

- **Evidence role** held out from fitting
- **Fit** Shaw Table S1 DOPC activity curve
- **Evaluation** Parker Fig. 3 crystal-onset composition

The ±0.02 in composition has no stated confidence level. At equilibrium with the same solid chemical potential, onset corresponds to activity 1. Shaw did not characterize its crystal polymorph.

At the independently measured crystal onset (66 ± 2 mol%), the fixed fit predicts activity 1.119. The expected value is 1 if the crystal references match. [Dataset manifest](../checks/data/parker2004_dopc_saturation.json) · [Comparison verdict](../PROGRESS.md#19-november-2026--ideal-and-regular-assembly-mixing)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
