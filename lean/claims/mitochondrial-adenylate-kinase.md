<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Magnesium shifts the apparent equilibrium of adenylate kinase

One signed extent of 2 ADP ⇌ ATP + AMP conserves adenylates, phosphate groups and Mg-free base-form charge. At free Mg concentration m, the total-nucleotide equilibrium quotient equals K_base (1 + m/a)/(1 + m/d)². For d ≥ 2a it reaches its maximum at m = d − 2a.

## Assumptions

- ATP and ADP each bind one Mg with positive dissociation constants a and d in the same units as m. AMP remains free. The enabled reaction reads positive free nucleotide activities and includes the ATP binding factor in its kinetic prefactor.
- The quotient is [ATP]_total [AMP]/[ADP]_total². The equilibrium formula extends to zero Mg by continuity. The engine's log-activity evaluator uses positive inputs.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.MitochondrialReactions.kinase_inventories](../CellsProofs/Chemistry/MitochondrialReactions.lean#L17)
- [CellsProofs.Chemistry.MitochondrialReactions.kinase_free_flux](../CellsProofs/Chemistry/MitochondrialReactions.lean#L26)
- [CellsProofs.Chemistry.MitochondrialReactions.kinase_rate_on_totals](../CellsProofs/Chemistry/MitochondrialReactions.lean#L39)
- [CellsProofs.Chemistry.MitochondrialReactions.kinase_peak_gap](../CellsProofs/Chemistry/MitochondrialReactions.lean#L51)
- [CellsProofs.Chemistry.MitochondrialReactions.kinase_peak_bound](../CellsProofs/Chemistry/MitochondrialReactions.lean#L64)

Direct proof subject `cells.cycle.adenylate_kinase@1`

Uses [Free energy sets ATP-driven transport direction and stall](atp-cycle.md)

## Numerical comparison

**Checked.** Across 21 Mg and nucleotide loads, the largest flux discrepancy was 7.04 × 10⁻¹⁵ of the forward rate. The three nucleotide changes followed their signed extents in two tissue steps. With the declared binding constants the predicted maximum is 1.5104 at 0.299 mM free Mg. At the 3.809 mM buffer match, omitting the Mg prefactor reduced the nonzero flux by a factor of 159.69.

**Engine** `resolved_pump_tissue@3`, `cells.adenylate_kinase@1`, `cells.held_reductant_supply@1`, `cells.rapid_binding@1`

[Adenylate kinase stoichiometry and Mg prefactor](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/cycles/adenylate_kinase.py#L51) · [Held reductant stoichiometry and phosphate prefactor](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/cycles/held_reductant_supply.py#L43) · [Free ligand and nucleotide forms](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/reactions/rapid_binding.py#L347) · [Monomial forward and reverse rates](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/cycles/forms.py#L1468) · [Material movement and held chemical work](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/kinds/transporter.py#L1956) · [Registered component rate evaluator](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/validation/mitochondria/component_comparison.py#L273) · [Finite matrix and intermembrane-space fixture](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/tests/unit/test_mito_cycle_laws.py#L85) · [Reference activities and model parameters](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/tests/unit/mito_component_center_rows.json) · [Kinase and redox measurements](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/lean/checks/data/mitochondrial_reaction_measurements.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/lean/checks/mitochondrial_reactions.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/lean/PROGRESS.md#mitochondrial-kinase-supply)

[Tested engine 0d3f300a5d1c](https://github.com/Eidosoma/Cells/commit/0d3f300a5d1c09bf0ad3c557d151879f441425b1) · [Evidence checkpoint 0d3f300a5d1c](https://github.com/Eidosoma/Cells/commit/0d3f300a5d1c09bf0ad3c557d151879f441425b1)

## Biological evidence

**Open.** Total-nucleotide equilibrium quotient as a function of free Mg in a defined preparation.

- [The apparent adenylate-kinase equilibrium quotient formed from total nucleotides depends on free Mg²⁺.](../WET_LAB_EVIDENCE.md#pair-adenylate-kinase-magnesium) · Supported by both studies

Two enzyme assays support a magnesium-dependent equilibrium. The position of the predicted maximum and its transfer to the cardiac intermembrane space remain open.

**Unit** dimensionless quotient and mM free Mg

### lawson1979_myokinase@1

pH 7.0, 38 °C, ionic strength 0.25 M. Cells uses its declared 25 °C constants. Abstract, myokinase equilibrium on total nucleotides at 0 and 1 mM free Mg. [Lawson and Veech (1979)](https://pubmed.ncbi.nlm.nih.gov/36398/)

- **Evidence role** descriptive

The abstract gives neither pointwise uncertainties nor the method for establishing zero free Mg.

The measured quotient rose from 0.391 to 1.05. The model gives 0.3890 in the zero-Mg limit and 1.1013 at 1 mM. [Dataset manifest](../checks/data/mitochondrial_reaction_measurements.json) · [Comparison verdict](../PROGRESS.md#mitochondrial-kinase-supply)

### kleczkowski1991_maize_kinase@1

Purified maize-leaf adenylate kinase. Abstract, apparent equilibrium at 1.8–1.9 mM free Mg. [Kleczkowski and Randall (1991)](https://doi.org/10.1093/jxb/42.4.537)

- **Evidence role** descriptive

The authors report ±0.10. The abstract does not specify the type of uncertainty.

The reported quotient was 0.76 ± 0.10. Cells gives 0.744–0.772 over the reported free-Mg range. [Dataset manifest](../checks/data/mitochondrial_reaction_measurements.json) · [Comparison verdict](../PROGRESS.md#mitochondrial-kinase-supply)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
