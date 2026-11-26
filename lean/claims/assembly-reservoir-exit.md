<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Molecule entry scales with reservoir activity and assembly size, and exit with species count

For species i, each molecule in an assembly adds kᵢ to its exit rate. Entry occurs at kᵢθᵢN, where θᵢ = Kᵢρᵢ and N is total size. Balancing every species’ entry and exit at a nonempty state requires Σθᵢ = 1. With a common positive leave constant, the mean-field fractions are stationary at xᵢ = θᵢ/Σθⱼ during growth. Unequal leave constants can move the fractions away from those proportions.

## Assumptions

- The well-mixed assembly has finitely many species with integer counts. The transfer constants Kᵢ, held activities ρᵢ and leave constants kᵢ are positive. Exchange has no catalytic multiplier and time is nominal.
- A species’ instantaneous net rate is its entry rate minus its exit rate at the same state. The mean-field fraction derivative uses these rates for the count derivatives and requires N > 0.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.ReservoirExchange.leave_increment](../CellsProofs/Chemistry/ReservoirExchange.lean#L24)
- [CellsProofs.Chemistry.ReservoirExchange.join_scaling](../CellsProofs/Chemistry/ReservoirExchange.lean#L27)
- [CellsProofs.Chemistry.ReservoirExchange.boundary_rates](../CellsProofs/Chemistry/ReservoirExchange.lean#L35)
- [CellsProofs.Chemistry.ReservoirExchange.balance_requires_normalization](../CellsProofs/Chemistry/ReservoirExchange.lean#L44)
- [CellsProofs.Chemistry.ReservoirExchange.common_rate_fraction_drift](../CellsProofs/Chemistry/ReservoirExchange.lean#L60)
- [CellsProofs.Chemistry.ReservoirExchange.unequal_rates_fraction_example](../CellsProofs/Chemistry/ReservoirExchange.lean#L79)

Direct proof subject `cells.exchange.reservoir_exchange@1`

Proof sources [Mathlib quotient rule used for the mean-field fraction](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Calculus/Deriv/Inv.lean#L143)

## Numerical comparison

**Checked.** Compiled rates agreed with rational reference values across all 165 three-species compositions through size eight. Doubling one species’ held activity doubled its entry and preserved the other rates. At equal counts (1, 1) and θ = (1, 1), the first fraction’s mean-field derivative was zero with leave constants (1, 1) and −¼ per nominal time unit with (1, 2).

**Engine** `cells.assembly_lineages@1`, `cells.reservoir_exchange@1`

**Operators** `cells.size_threshold_fission@1`, `cells.daughter_continuation@1`

[Uncatalyzed entry and exit rates](https://github.com/Eidosoma/Cells/blob/6c648d846fa5c92644986fd967dd403757234b26/src/cells/models/assembly_lineages/exchange.py#L108) · [Transfer constants and held activities](https://github.com/Eidosoma/Cells/blob/6c648d846fa5c92644986fd967dd403757234b26/src/cells/models/assembly_lineages/model.py#L47) · [Event booking and the reverse rate](https://github.com/Eidosoma/Cells/blob/6c648d846fa5c92644986fd967dd403757234b26/src/cells/models/assembly_lineages/kernel.py#L299) · [Log weight and empty-state convention](https://github.com/Eidosoma/Cells/blob/6c648d846fa5c92644986fd967dd403757234b26/src/cells/models/assembly_lineages/ledger.py#L83) · [Compiled rates by composition](https://github.com/Eidosoma/Cells/blob/6c648d846fa5c92644986fd967dd403757234b26/validation/assembly_lineages/probes.py#L210) · [Independent scalar event replay](https://github.com/Eidosoma/Cells/blob/6c648d846fa5c92644986fd967dd403757234b26/src/cells/models/assembly_lineages/reference.py#L46) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/713ef3b4bedb2c1f184d46d968262af92f115e3b/lean/checks/reservoir_exchange.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/713ef3b4bedb2c1f184d46d968262af92f115e3b/lean/PROGRESS.md#19-november-2026--assembly-reservoir-exchange)

[Tested engine 6c648d846fa5](https://github.com/Eidosoma/Cells/commit/6c648d846fa5c92644986fd967dd403757234b26) · [Evidence checkpoint 713ef3b4bedb](https://github.com/Eidosoma/Cells/commit/713ef3b4bedb2c1f184d46d968262af92f115e3b)

## Biological evidence

**Open.** Loss of accessible lipid during washout and uptake of a specified lipid as free monomer activity and individual vesicle size vary.

Accessible fluorescent lipid washed out of 310 protein-free vesicles at 0.0108 ± 0.0045 s⁻¹ (24 °C, mean ± SD). The retained fraction was 49.5 ± 8.5%. In a separate sterol assay, adding more equal-sized vesicles increased transfer at 25 °C. The insertion constant fitted at 35 °C was (6.4 ± 0.6) × 10⁷ M⁻¹ s⁻¹ per molar vesicles. Individual vesicle size, free monomer activity and the Cells time scale remain open. [Veit et al., Fig. 2 and Extended Data Fig. 2](https://doi.org/10.1038/s41594-026-01821-8) · [Estronca et al., Fig. 2 and Table 1](https://pmc.ncbi.nlm.nih.gov/articles/PMC2098731/)

**Unit** s⁻¹ for washout, M⁻¹ s⁻¹ per molar vesicles for the insertion constant

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
