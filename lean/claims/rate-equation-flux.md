<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Deterministic reactions stall at equilibrium and dissipate free energy

An enabled reaction with positive forward factor has forward flux exactly when its reservoir-adjusted free-energy change is negative, reverse flux when positive, and zero flux at equilibrium. The instantaneous dissipation is nonnegative for every reaction and for any finite sum.

## Assumptions

- The driving force is the stoichiometric change in chemical potential minus reservoir work, in units of k_BT. The enabled forward factor is finite and nonnegative. An inactive reaction or zero forward factor has zero flux for every finite force.
- The theorem concerns the instantaneous constitutive equation over the reals. Accuracy of the time integrator, floating-point evaluation and agreement with a particular assay each require separate evidence.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.RateEquations.inactive](../CellsProofs/Chemistry/RateEquations.lean#L18)
- [CellsProofs.Chemistry.RateEquations.zero_forward](../CellsProofs/Chemistry/RateEquations.lean#L20)
- [CellsProofs.Chemistry.RateEquations.direction_and_stall](../CellsProofs/Chemistry/RateEquations.lean#L24)
- [CellsProofs.Chemistry.RateEquations.dissipation_nonneg](../CellsProofs/Chemistry/RateEquations.lean#L34)
- [CellsProofs.Chemistry.RateEquations.network_dissipation_nonneg](../CellsProofs/Chemistry/RateEquations.lean#L49)

Direct proof subject `cells.rate_equations@1`

Proof sources [Cells specializes the existing ATP-cycle sign and stall proofs](../CellsProofs/Transport/ATPCycle.lean#L31) · [Imported Mathlib exponential of the log of a positive forward factor](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/SpecialFunctions/Log/Basic.lean#L54) · [Imported Mathlib nonnegativity of a finite sum, specialized to reaction power](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/Order/BigOperators/Group/Finset.lean#L115)

Uses [Free energy sets ATP-driven transport direction and stall](atp-cycle.md)

## Numerical comparison

**Checked.** The two compiled reaction fluxes matched independent linear rates within 1.10 × 10⁻¹¹ events/s across five states, including relative changes of 10⁻⁹ on each side of exact stall. Both padded slots returned zero. At 4 mM product with a 2 mM reservoir, omitting the reservoir work reversed the predicted direction.

**Engine** `cells.assembly_lineages@2`, `cells.rate_equations@1`, `cells.ideal_mixing@1`, `cells.stochastic_mass_action@1`

[Enabled reaction flux and free energy after reservoir work](https://github.com/Eidosoma/Cells/blob/ddcf32c1050c6bda14e476b0ec22b7defa010db3/src/cells/models/assembly_lineages_v2/rate_equations.py#L614) · [Held reservoir work and step mask](https://github.com/Eidosoma/Cells/blob/ddcf32c1050c6bda14e476b0ec22b7defa010db3/src/cells/models/assembly_lineages_v2/model.py#L109) · [Reaction view at real counts](https://github.com/Eidosoma/Cells/blob/ddcf32c1050c6bda14e476b0ec22b7defa010db3/src/cells/models/assembly_lineages_v2/kernel.py#L244) · [Ideal free energy at real counts](https://github.com/Eidosoma/Cells/blob/ddcf32c1050c6bda14e476b0ec22b7defa010db3/src/cells/models/assembly_lineages_v2/ideal_mixing.py#L106) · [Mass-action rate limit](https://github.com/Eidosoma/Cells/blob/ddcf32c1050c6bda14e476b0ec22b7defa010db3/src/cells/models/assembly_lineages_v2/mass_action.py#L143) · [Parsed finite and held places](https://github.com/Eidosoma/Cells/blob/ddcf32c1050c6bda14e476b0ec22b7defa010db3/src/cells/models/assembly_lineages_v2/world.py) · [Linear reaction network and representation fixture](https://github.com/Eidosoma/Cells/blob/ddcf32c1050c6bda14e476b0ec22b7defa010db3/tests/unit/test_assembly_lineages_v2_rate_equations.py#L39) · [Native assembly definition](https://github.com/Eidosoma/Cells/blob/ddcf32c1050c6bda14e476b0ec22b7defa010db3/tests/assembly_lineage_v2_fixtures.py#L164) · [Reaction direction and dissipation in real arithmetic](https://github.com/Eidosoma/Cells/blob/59e2f460d3b8fdc0ea1da5c70719b71330bf7a4a/lean/CellsProofs/Chemistry/RateEquations.lean) · [Shared factored-flux direction lemmas](https://github.com/Eidosoma/Cells/blob/59e2f460d3b8fdc0ea1da5c70719b71330bf7a4a/lean/CellsProofs/Transport/ATPCycle.lean) · [Pinned Mathlib dependency](https://github.com/Eidosoma/Cells/blob/59e2f460d3b8fdc0ea1da5c70719b71330bf7a4a/lean/lake-manifest.json) · [PGI worksheet cells and equilibrium assay](https://github.com/Eidosoma/Cells/blob/59e2f460d3b8fdc0ea1da5c70719b71330bf7a4a/lean/checks/data/pgi_flux_direction.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/59e2f460d3b8fdc0ea1da5c70719b71330bf7a4a/lean/checks/rate_equation_flux.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/59e2f460d3b8fdc0ea1da5c70719b71330bf7a4a/lean/PROGRESS.md#rate-equation-flux)

[Tested engine ddcf32c1050c](https://github.com/Eidosoma/Cells/commit/ddcf32c1050c6bda14e476b0ec22b7defa010db3) · [Evidence checkpoint 59e2f460d3b8](https://github.com/Eidosoma/Cells/commit/59e2f460d3b8fdc0ea1da5c70719b71330bf7a4a)

## Biological evidence

**Open.** Direction of glucose-6-phosphate (G6P) and fructose-6-phosphate (F6P) conversion from opposite starting conditions, the equilibrium ratio, and dissipated heat per unit time.

- [Phosphoglucose isomerase can convert G6P to F6P or F6P to G6P, depending on the starting mixture.](../WET_LAB_EVIDENCE.md#pair-pgi-reversal) · Supported by both studies

Two extract time courses changed in the directions given by their fitted equilibrium. A separate rabbit-muscle equilibrium assay lets us compare a zero-flux ratio inferred from kinetics with a measured endpoint.

**Unit** F6P/G6P (dimensionless)

### eicher2012_pgi_direction

E. coli K-12 extract in 100 mM PIPES at pH 7.2 and 25 °C. The model uses the authors’ fitted ratio of 0.286 for these same courses. PGI worksheet, F4:H4 and F33:H33 in dataset 2, K4:M4 and K29:M29 in dataset 3. [Eicher et al. (2012), Fig. 5](https://doi.org/10.3390/metabo2040818)

- **Evidence role** calibration

The stored unsmoothed concentrations have no per-point error estimates. The two tubes share a date and nominal protocol. A common extract batch is unverified.

F6P fell by 3.787 mM in the F6P-start tube and rose by 1.172 mM in the G6P-start tube. Cells matched both net directions. The time courses leave instantaneous heat unmeasured. [Dataset manifest](../checks/data/pgi_flux_direction.json) · [Comparison verdict](../PROGRESS.md#rate-equation-flux)

### dyson1968_pgi_equilibrium

Purified rabbit-muscle enzyme at 30 °C, pH 8.5 and ionic strength 0.12. The model sets the standard-potential difference from the authors’ kinetic estimate. Table I reports kinetic and equilibrium determinations. Figure 13 describes the approaches from both sugars. [Dyson and Noltmann (1968), Table I and Fig. 13](https://doi.org/10.1016/S0021-9258(18)93559-3)

- **Evidence role** held out from fitting
- **Fit** Equilibrium ratio inferred from the forward and reverse kinetic parameters
- **Evaluation** Equilibrium composition measured in the same preparation starting from either sugar
- **Observed** 0.3 F6P/G6P (dimensionless)
- **Predicted** 0.32 F6P/G6P (dimensionless)

Table I supplies no uncertainty for the measured equilibrium ratio.

The compiled stall ratio exceeds the measured endpoint by 0.020. Statistical agreement remains unassessed. [Dataset manifest](../checks/data/pgi_flux_direction.json) · [Comparison verdict](../PROGRESS.md#rate-equation-flux)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
