<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Restoring both respiratory carriers fixes the turnover ratio and outward charge

For signed extents of mitochondrial complexes I, III and IV, restoring reduced quinone and reduced cytochrome c fixes their turnover in the ratio 2:2:1. Two NADH and one oxygen then give twenty outward charge equivalents, with every intermediate redox carrier restored.

## Assumptions

- N is the matrix and P the intermembrane space. The tracked species use the registered base forms, with explicit protons. Water is implicit.
- The complete-chain ratio assumes no other source or sink for the two intermediate carriers. The per-cycle identities hold for arbitrary signed extents, including a transient.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.MitochondrialCycles.charge_on_each_side](../CellsProofs/Chemistry/MitochondrialCycles.lean#L62)
- [CellsProofs.Chemistry.MitochondrialCycles.carrier_balance_iff](../CellsProofs/Chemistry/MitochondrialCycles.lean#L72)
- [CellsProofs.Chemistry.MitochondrialCycles.respiratory_net](../CellsProofs/Chemistry/MitochondrialCycles.lean#L84)

Direct proof subject `cells.cycle.nadh_ubiquinone_proton_cycle@1`, `cells.cycle.ubiquinol_cytochrome_c_proton_cycle@1`, `cells.cycle.cytochrome_c_oxygen_proton_cycle@1`

Uses [Balanced reactions preserve a weighted inventory](reaction-inventory.md)

## Numerical comparison

**Checked.** All seven registered columns were checked against independently written material balances. Per forward turnover the respiratory complexes added 4, 2 and 8 net charges on P, while each added four explicit P protons. In two checked steps of a finite-matrix/lumen world, the redox, adenine and phosphate changes matched predictions from the measured extents within 8.28 × 10⁻²⁵ fmol.

**Engine** `resolved_pump_tissue@3`, `cells.nadh_ubiquinone_proton_cycle@1`, `cells.ubiquinol_cytochrome_c_proton_cycle@1`, `cells.cytochrome_c_oxygen_proton_cycle@1`, `cells.proton_coupled_atp_synthesis_cycle@1`, `cells.electrogenic_nucleotide_exchange@1`, `cells.phosphate_proton_symport@1`, `cells.potassium_proton_exchange@1`, `cells.rapid_binding@1`

[Complex I](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/laws/cycles/nadh_ubiquinone_proton_cycle.py#L20) · [Complex III](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/laws/cycles/ubiquinol_cytochrome_c_proton_cycle.py#L35) · [Complex IV](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/laws/cycles/cytochrome_c_oxygen_proton_cycle.py#L37) · [ATP synthesis](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/laws/cycles/proton_coupled_atp_synthesis_cycle.py#L35) · [Nucleotide exchange](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/laws/cycles/electrogenic_nucleotide_exchange.py#L34) · [Phosphate import](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/laws/cycles/phosphate_proton_symport.py#L28) · [Potassium–proton exchange](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/laws/cycles/potassium_proton_exchange.py#L16) · [Material ledger by species and side](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/kinds/transporter.py#L2128) · [Matrix and lumen fixture](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/tests/unit/test_mito_cycle_laws.py#L63) · [Independent registered component comparisons](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/validation/mitochondria/component_comparison.py#L1) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/84e3078e3fa0f2a010192e4459abc72eee120b92/lean/checks/mitochondrial_cycles.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/84e3078e3fa0f2a010192e4459abc72eee120b92/lean/PROGRESS.md#mitochondrial-cycle-accounting)

[Tested engine 2ae89b5e2cd1](https://github.com/Eidosoma/Cells/commit/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007) · [Evidence checkpoint 84e3078e3fa0](https://github.com/Eidosoma/Cells/commit/84e3078e3fa0f2a010192e4459abc72eee120b92)

**Engine** `resolved_pump_tissue@3`, `cells.nadh_ubiquinone_proton_cycle@1`, `cells.ubiquinol_cytochrome_c_proton_cycle@1`, `cells.cytochrome_c_oxygen_proton_cycle@1`, `cells.proton_coupled_atp_synthesis_cycle@1`, `cells.electrogenic_nucleotide_exchange@1`, `cells.phosphate_proton_symport@1`, `cells.potassium_proton_exchange@1`, `cells.rapid_binding@1`

[Complex I](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/cycles/nadh_ubiquinone_proton_cycle.py#L20) · [Complex III](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/cycles/ubiquinol_cytochrome_c_proton_cycle.py#L35) · [Complex IV](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/cycles/cytochrome_c_oxygen_proton_cycle.py#L37) · [ATP synthesis](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/cycles/proton_coupled_atp_synthesis_cycle.py#L35) · [Nucleotide exchange](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/cycles/electrogenic_nucleotide_exchange.py#L34) · [Phosphate import](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/cycles/phosphate_proton_symport.py#L28) · [Potassium–proton exchange](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/cycles/potassium_proton_exchange.py#L16) · [Material ledger by species and side](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/kinds/transporter.py#L2128) · [Matrix and lumen fixture](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/tests/unit/test_mito_cycle_laws.py#L85) · [Independent stoichiometry by cycle and side](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/lean/checks/mitochondrial_cycles.py#L20) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/lean/checks/mitochondrial_cycles.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/lean/PROGRESS.md#mitochondrial-kinase-supply)

[Tested engine 0d3f300a5d1c](https://github.com/Eidosoma/Cells/commit/0d3f300a5d1c09bf0ad3c557d151879f441425b1) · [Evidence checkpoint 0d3f300a5d1c](https://github.com/Eidosoma/Cells/commit/0d3f300a5d1c09bf0ad3c557d151879f441425b1)

## Biological evidence

**Open.** Protons transported per NADH, including correction for proton consumption by quinone reduction, and net charge transport during a carrier-balanced respiratory sequence.

- [Forward bovine complex I translocates about four protons per pair of electrons.](../WET_LAB_EVIDENCE.md#pair-complex-i-protons) · Supported by both studies

**Unit** H⁺ per NADH or two electrons, charge equivalents per O₂

### galkin1999_complex_i@1

NADH-driven quinone reduction in inside-out bovine heart submitochondrial particles. Fig. 2, right panel, and the scalar-proton correction in Eq. 3. [Galkin et al. (1999), Fig. 2 and Eq. 3](https://doi.org/10.1016/S0014-5793(99)00575-X)

- **Evidence role** descriptive

The authors report 4.00 ± 0.05, estimated from initial rates after correcting for one proton consumed by quinone reduction.

The observed 4.00 ± 0.05 transported protons per two electrons agrees with the four on P per forward complex I turnover. The full three-complex charge balance needs additional measurements. [Dataset manifest](../checks/data/mitochondrial_stoichiometry.json) · [Comparison verdict](../PROGRESS.md#mitochondrial-cycle-accounting)

### jones2017_complex_i@1

Four bovine heart submitochondrial preparations. The three comparisons match ATP synthesis rates to approximate equal proton leak. Bovine estimates in Table 3 derived from the paired flux measurements in Fig. 3. [Jones et al. (2017), Table 3 and Fig. 3](https://doi.org/10.1074/jbc.M116.771899)

- **Evidence role** descriptive

Reported propagated errors. All three comparisons use the same four preparations.

The estimates were 4.21 ± 0.15, 4.10 ± 0.17 and 4.02 ± 0.19 H⁺/2e⁻. They support a value near four for complex I. They do not directly measure the three-complex net charge. [Dataset manifest](../checks/data/mitochondrial_stoichiometry.json) · [Comparison verdict](../PROGRESS.md#mitochondrial-cycle-accounting)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
