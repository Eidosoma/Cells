<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# The held reductant supply has a pH-dependent stall and balances work in either direction

The enabled supply stalls exactly when free matrix NADH/NAD equals the held reduced-to-oxidized donor ratio times the reference proton concentration divided by the free matrix proton concentration. At any signed flux, work supplied by the held pair equals the dissipated heat plus chemical work delivered to NAD, NADH and H⁺.

## Assumptions

- The matrix reaction is S_red + NAD ⇌ S_ox + NADH + H⁺. Both donor rows are held. The reaction has no charge transfer across the membrane.
- Free activities and the kinetic prefactor are positive. Cells assigns zero standard drive at its reference proton concentration of 10⁻⁷ M. Work and heat refer to instantaneous chemical power.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.MitochondrialReactions.supply_stall](../CellsProofs/Chemistry/MitochondrialReactions.lean#L73)
- [CellsProofs.Chemistry.MitochondrialReactions.supply_work](../CellsProofs/Chemistry/MitochondrialReactions.lean#L89)

Direct proof subject `cells.cycle.held_reductant_supply@1`

Uses [Free energy sets ATP-driven transport direction and stall](atp-cycle.md)

## Numerical comparison

**Checked.** Across 24 pH, phosphate and NADH loads the largest net-flux discrepancy was 1.23 × 10⁻¹⁴ of the forward rate. For a held ratio of 3.63858 the stalled NADH/NAD ratio was 4.5807 at pH 7.1 and 9.1397 at pH 7.4. The two-step tissue run kept the donor amounts fixed, recorded opposite donor receipts and moved NAD and NADH with opposite signs. Held work matched heat plus delivered chemical work within a relative tolerance of 2 × 10⁻¹² at positive and negative flux.

**Engine** `resolved_pump_tissue@3`, `cells.adenylate_kinase@1`, `cells.held_reductant_supply@1`, `cells.rapid_binding@1`

[Adenylate kinase stoichiometry and Mg prefactor](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/cycles/adenylate_kinase.py#L51) · [Held reductant stoichiometry and phosphate prefactor](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/cycles/held_reductant_supply.py#L43) · [Free ligand and nucleotide forms](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/reactions/rapid_binding.py#L347) · [Monomial forward and reverse rates](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/cycles/forms.py#L1468) · [Material movement and held chemical work](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/kinds/transporter.py#L1956) · [Registered component rate evaluator](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/validation/mitochondria/component_comparison.py#L273) · [Finite matrix and intermembrane-space fixture](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/tests/unit/test_mito_cycle_laws.py#L85) · [Reference activities and model parameters](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/tests/unit/mito_component_center_rows.json) · [Kinase and redox measurements](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/lean/checks/data/mitochondrial_reaction_measurements.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/lean/checks/mitochondrial_reactions.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/lean/PROGRESS.md#mitochondrial-kinase-supply)

[Tested engine 0d3f300a5d1c](https://github.com/Eidosoma/Cells/commit/0d3f300a5d1c09bf0ad3c557d151879f441425b1) · [Evidence checkpoint 0d3f300a5d1c](https://github.com/Eidosoma/Cells/commit/0d3f300a5d1c09bf0ad3c557d151879f441425b1)

## Biological evidence

**Open.** Dependence of the free NADH/NAD equilibrium ratio on proton activity and the reduced-to-oxidized donor ratio. The absolute stall and heat require a specified donor.

A named ketone-body donor exhibits the one-proton equilibrium dependence. The absolute stall ratio and heat for the Cells donor remain unmeasured.

**Unit** dimensionless activity ratio, M for the measured equilibrium quotient, pJ/s for the model heat

### williamson1967_hydroxybutyrate@1

The β-hydroxybutyrate/acetoacetate donor pair at 38 °C, ionic strength 0.255 M and pH 6.84–7.16. Table 3, equilibrium of D-β-hydroxybutyrate dehydrogenase. [Williamson, Lund and Krebs (1967)](https://doi.org/10.1042/bj1030514)

- **Evidence role** descriptive

SEM of 25 determinations.

The quotient [acetoacetate][NADH][H⁺]/([β-hydroxybutyrate][NAD⁺]) was (4.94 ± 0.086) × 10⁻⁹ M. This measures the proton dependence and equilibrium for this specific donor pair. [Dataset manifest](../checks/data/mitochondrial_reaction_measurements.json) · [Comparison verdict](../PROGRESS.md#mitochondrial-kinase-supply)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
