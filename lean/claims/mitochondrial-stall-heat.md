<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Mitochondrial cycles reverse at zero free energy and dissipate power in either direction

Each enabled mitochondrial cycle runs forward at negative full-turn ΔG, reverses at positive ΔG and stalls at zero. The five electrogenic cycles have a stall voltage set by free activities. Phosphate uptake and K⁺/H⁺ exchange have voltage-independent stall ratios. At positive temperature, instantaneous dissipated power is positive in either direction and vanishes exactly at stall or when the population is off.

## Assumptions

- Each reaction uses the declared free species and signed charge, with N the matrix and P the intermembrane space. Free activities are positive. The dimensionless voltage is F(φ_N − φ_P)/(RT).
- An enabled population has a positive finite forward kinetic prefactor. Complex III uses a half-turn exponent and complex IV a quarter-turn exponent. ΔG refers to a full turnover in both cases.
- Heat here is the model's instantaneous chemical free-energy dissipation. Flux is in fmol/s and RT in J/mol. An assay of integrated whole-mitochondrion enthalpy measures a different observable.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.MitochondrialStall.rate_disabled](../CellsProofs/Chemistry/MitochondrialStall.lean#L34)
- [CellsProofs.Chemistry.MitochondrialStall.rate_eq_fractional](../CellsProofs/Chemistry/MitochondrialStall.lean#L37)
- [CellsProofs.Chemistry.MitochondrialStall.direction](../CellsProofs/Chemistry/MitochondrialStall.lean#L53)
- [CellsProofs.Chemistry.MitochondrialStall.voltage_stall](../CellsProofs/Chemistry/MitochondrialStall.lean#L62)
- [CellsProofs.Chemistry.MitochondrialStall.neutral_carrier_stalls](../CellsProofs/Chemistry/MitochondrialStall.lean#L70)
- [CellsProofs.Chemistry.MitochondrialStall.synthase_load_shift](../CellsProofs/Chemistry/MitochondrialStall.lean#L81)
- [CellsProofs.Chemistry.MitochondrialStall.heat_nonneg](../CellsProofs/Chemistry/MitochondrialStall.lean#L92)
- [CellsProofs.Chemistry.MitochondrialStall.heat_zero_iff](../CellsProofs/Chemistry/MitochondrialStall.lean#L96)

Direct proof subject `cells.cycle.nadh_ubiquinone_proton_cycle@1`, `cells.cycle.ubiquinol_cytochrome_c_proton_cycle@1`, `cells.cycle.cytochrome_c_oxygen_proton_cycle@1`, `cells.cycle.proton_coupled_atp_synthesis_cycle@1`, `cells.cycle.electrogenic_nucleotide_exchange@1`, `cells.cycle.phosphate_proton_symport@1`, `cells.cycle.potassium_proton_exchange@1`

Proof sources [Mathlib geometric sum used to recover the fractional exponent](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/GeomSum.lean#L239)

Uses [Free energy sets ATP-driven transport direction and stall](atp-cycle.md) · [Restoring both respiratory carriers fixes the turnover ratio and outward charge](mitochondrial-respiratory-balance.md) · [ATP synthesis and delivery return four charge equivalents in the declared three-proton model](mitochondrial-atp-delivery.md)

## Numerical comparison

**Checked.** All 49 physical settings agreed with the independent component equations on NumPy and compiled CPU JAX, including both sides of stall for all seven laws. The worst net-flux error was 3.91 × 10⁻¹⁴ of the reference forward rate. The worst residual ΔG/(RT) at a calculated stall was 2.85 × 10⁻¹⁴. The rate kernel also preserved the signs at ±2⁻⁶⁰ and returned zero at an exact zero input. The probe and the stage agreed on flux and instantaneous dissipated power.

**Engine** `resolved_pump_tissue@3`, `cells.nadh_ubiquinone_proton_cycle@1`, `cells.ubiquinol_cytochrome_c_proton_cycle@1`, `cells.cytochrome_c_oxygen_proton_cycle@1`, `cells.proton_coupled_atp_synthesis_cycle@1`, `cells.electrogenic_nucleotide_exchange@1`, `cells.phosphate_proton_symport@1`, `cells.potassium_proton_exchange@1`, `cells.rapid_binding@1`

[Full-turn affinity from free concentrations and voltage](https://github.com/Eidosoma/Cells/blob/e4b9588fdc80aa8e764e09c70a39a5b2f2db64cf/src/cells/kinds/transporter.py#L1809) · [Monomial affinity shares](https://github.com/Eidosoma/Cells/blob/e4b9588fdc80aa8e764e09c70a39a5b2f2db64cf/src/cells/laws/cycles/forms.py#L1468) · [Reversible rate near stall](https://github.com/Eidosoma/Cells/blob/e4b9588fdc80aa8e764e09c70a39a5b2f2db64cf/src/cells/laws/cycles/forms.py#L1512) · [Heat and cycle derivatives](https://github.com/Eidosoma/Cells/blob/e4b9588fdc80aa8e764e09c70a39a5b2f2db64cf/src/cells/kinds/transporter.py#L1966) · [Public cycle probe](https://github.com/Eidosoma/Cells/blob/e4b9588fdc80aa8e764e09c70a39a5b2f2db64cf/src/cells/kinds/transporter.py#L2362) · [Matrix and lumen fixture](https://github.com/Eidosoma/Cells/blob/e4b9588fdc80aa8e764e09c70a39a5b2f2db64cf/tests/unit/test_mito_cycle_laws.py#L64) · [Independent decimal component equations](https://github.com/Eidosoma/Cells/blob/e4b9588fdc80aa8e764e09c70a39a5b2f2db64cf/validation/mitochondria/appendix_check.py#L87) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/f0783ad9cb9c9f1ca581dfacee23ac8b5411268e/lean/checks/mitochondrial_stall.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/f0783ad9cb9c9f1ca581dfacee23ac8b5411268e/lean/PROGRESS.md#mitochondrial-stall-heat)

[Tested engine e4b9588fdc80](https://github.com/Eidosoma/Cells/commit/e4b9588fdc80aa8e764e09c70a39a5b2f2db64cf) · [Evidence checkpoint f0783ad9cb9c](https://github.com/Eidosoma/Cells/commit/f0783ad9cb9c9f1ca581dfacee23ac8b5411268e)

**Engine** `resolved_pump_tissue@3`, `cells.nadh_ubiquinone_proton_cycle@1`, `cells.ubiquinol_cytochrome_c_proton_cycle@1`, `cells.cytochrome_c_oxygen_proton_cycle@1`, `cells.proton_coupled_atp_synthesis_cycle@1`, `cells.electrogenic_nucleotide_exchange@1`, `cells.phosphate_proton_symport@1`, `cells.potassium_proton_exchange@1`, `cells.rapid_binding@1`

[Full-turn affinity from free concentrations and voltage](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/kinds/transporter.py#L1809) · [Monomial affinity shares](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/cycles/forms.py#L1468) · [Reversible rate near stall](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/cycles/forms.py#L1512) · [Heat and cycle derivatives](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/kinds/transporter.py#L1966) · [Public cycle probe](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/kinds/transporter.py#L2362) · [Matrix and lumen fixture](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/tests/unit/test_mito_cycle_laws.py#L85) · [Independent decimal component equations](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/validation/mitochondria/appendix_check.py#L87) · [Seven populations selected explicitly for the shared fixture](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/lean/checks/mitochondrial_cycles.py#L16) · [ATP synthase stall measurements](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/lean/checks/data/mitochondrial_stall.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/lean/checks/mitochondrial_stall.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/lean/PROGRESS.md#mitochondrial-kinase-supply)

[Tested engine 0d3f300a5d1c](https://github.com/Eidosoma/Cells/commit/0d3f300a5d1c09bf0ad3c557d151879f441425b1) · [Evidence checkpoint 0d3f300a5d1c](https://github.com/Eidosoma/Cells/commit/0d3f300a5d1c09bf0ad3c557d151879f441425b1)

## Biological evidence

**Open.** Net turnover on either side of a measured mitochondrial stall, the shift in ATP synthase stall with phosphorylation load, and dissipated power at known cycle affinity.

**Unit** turnovers per enzyme per second, pH units, H⁺/ATP, pJ/s per population

### petersen2012_yeast_stall@1

Purified yeast mitochondrial ATP synthase in proteoliposomes at an imposed 60 mV. Yeast traces in Fig. 1, corrected stall in Fig. 2, fitted coupling in Fig. 4 and all ten corrected stall entries in Table S4. [Petersen et al. (2012), Figs. 1–4 and Tables S2 and S4](https://doi.org/10.1073/pnas.1202799109)

- **Evidence role** descriptive

The example rates are fitted initial slopes. The equilibrium ΔpH was interpolated. One measured stall sets the offset for comparing shifts at the other loads. The comparison adds the reported interpolation limits and assumes the assay's concentration quotient is proportional to the free activity quotient.

ATP turnover changed sign across stall, and the inferred coupling was 2.9 ± 0.2 H⁺/ATP. The model's three protons predict a 0.745 pH-unit endpoint shift against 0.74 observed. Five of nine other entries are within the combined interpolation limits using the stall at Q = 5.79 as the reference. Four intermediate entries fall outside. [Dataset manifest](../checks/data/mitochondrial_stall.json) · [Comparison verdict](../PROGRESS.md#mitochondrial-stall-heat)

### nakamura1978_mitochondrial_heat@1

Rat liver mitochondria following aerobic ATP production and oxygen exhaustion. The anaerobic bulk heat pulse in Fig. 5b and its dependence on the initial ADP in Fig. 6. [Nakamura and Matsuoka (1978), Figs. 5b and 6](https://doi.org/10.1093/oxfordjournals.jbchem.a132117)

- **Evidence role** descriptive

The apparent enthalpy was −29 ± 7 kJ per mole of previously added ADP. The authors inferred an ATP hydrolysis contribution.

Bulk calorimetry integrates heat from the preparation. The instantaneous dissipated power of each individual mitochondrial cycle remains experimentally open. [Dataset manifest](../checks/data/mitochondrial_stall.json) · [Comparison verdict](../PROGRESS.md#mitochondrial-stall-heat)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
