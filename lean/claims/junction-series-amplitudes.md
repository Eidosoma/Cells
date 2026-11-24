<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Two independent junction gates constrain the decay amplitudes

At fixed voltage, multiplying two independent relaxing gate factors gives a plateau P and terms at the fast rate, the slow rate and their sum. Their signed amplitudes satisfy P × A_mixed = A_fast × A_slow. With a nonzero plateau, measuring the fast and slow amplitudes determines the mixed amplitude.

## Assumptions

- Each gate relaxes exponentially toward its own fixed plateau. Junction conductance is proportional to the product of the two factors with a common time origin.
- The reported conductance can be divided by a common reference. Any additive background has been removed. Interpreting the three amplitudes separately requires distinct positive gate rates and a trace that resolves them.

## Lean proof

**Proved**

- [CellsProofs.Transport.JunctionGate.series_clamp_expansion](../CellsProofs/Transport/JunctionGate.lean#L112)
- [CellsProofs.Transport.JunctionGate.series_amplitudes](../CellsProofs/Transport/JunctionGate.lean#L122)

Direct proof subject `cells.junction_series_gates@1`

Proof sources [FR-30 product of independent gate factors at constant voltage](../../docs/JUNCTION_TWO_RELAXATION_DESIGN.md#L174) · [Constant-voltage step and product conductance](../../src/cells/laws/junctions/junction_series_gates.py#L134) · [Physlib two-state partition function, imported in the optional single-gate equilibrium check](https://github.com/leanprover-community/physlib/blob/559b0e14bd87896d4ee536a536a8fb65e83b77cc/PhysLean/StatisticalMechanics/CanonicalEnsemble/TwoState.lean#L33-L37) · [Physlib postulate used by the optional check, a positive Boltzmann constant in the chosen units](https://github.com/leanprover-community/physlib/blob/559b0e14bd87896d4ee536a536a8fb65e83b77cc/PhysLean/StatisticalMechanics/BoltzmannConstant.lean#L22-L30) · [Cells specialization for one gate with dimensionless open-state energy gap](../checks/physlib/JunctionEquilibrium.lean) · [Engine steady open fraction before residual conductance](../../src/cells/laws/junctions/junction_series_gates.py#L79)

## Numerical comparison

**Checked.** Across four gate-kind pairings, five clamp voltages and six times, the compiled conductance and two route factors agreed with the independent calculation within 2.23 × 10⁻¹⁶. All 11 engine tests passed after registration, including the two-cell ionic trajectory and the comparison to one gate with the second pinned open. The tissue host admits the law for development runs.

**Engine** `junction_series_gates@1`

[Two gate types, exact clamp and route factors](https://github.com/Eidosoma/Cells/blob/d74f519d40b9a9f7488b94b489c6dc4dd865504c/src/cells/laws/junctions/junction_series_gates.py) · [Threshold gate rates](https://github.com/Eidosoma/Cells/blob/d74f519d40b9a9f7488b94b489c6dc4dd865504c/src/cells/laws/junctions/junction_voltage_relaxation.py#L41) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/lean/checks/junction_series_gates.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/lean/PROGRESS.md#nov21-features)

[Tested engine d74f519d40b9](https://github.com/Eidosoma/Cells/commit/d74f519d40b9a9f7488b94b489c6dc4dd865504c) · [Evidence checkpoint ceeca19816ac](https://github.com/Eidosoma/Cells/commit/ceeca19816acd761ab68379d67bb0f7426366a1c)

**Engine** `resolved_pump_tissue@3`, `junction_series_gates@1`

[Registered two-gate declaration, clamp rates and route factors](https://github.com/Eidosoma/Cells/blob/4532479c017977c67449995684657066225501d5/src/cells/laws/junctions/junction_series_gates.py) · [Threshold gate rates](https://github.com/Eidosoma/Cells/blob/4532479c017977c67449995684657066225501d5/src/cells/laws/junctions/junction_voltage_relaxation.py#L41) · [Registration in the tissue model table](https://github.com/Eidosoma/Cells/blob/4532479c017977c67449995684657066225501d5/src/cells/registry/model_table.py#L84) · [Tissue inner-law table and gate admission](https://github.com/Eidosoma/Cells/blob/4532479c017977c67449995684657066225501d5/src/cells/models/inner_laws.py#L106) · [Normal host run, admission and pinned-gate comparisons](https://github.com/Eidosoma/Cells/blob/4532479c017977c67449995684657066225501d5/tests/unit/test_junction_series_gates.py#L244-L400) · [Two-gate expansion and amplitude identity](https://github.com/Eidosoma/Cells/blob/aa41cf5bf36b28125bb471a6cedf3be8756264ed/lean/CellsProofs/Transport/JunctionGate.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/aa41cf5bf36b28125bb471a6cedf3be8756264ed/lean/checks/junction_series_gates.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/aa41cf5bf36b28125bb471a6cedf3be8756264ed/lean/PROGRESS.md#nov21-registered-series-and-withdrawal)

[Tested engine 4532479c0179](https://github.com/Eidosoma/Cells/commit/4532479c017977c67449995684657066225501d5) · [Evidence checkpoint aa41cf5bf36b](https://github.com/Eidosoma/Cells/commit/aa41cf5bf36b28125bb471a6cedf3be8756264ed)

## Biological evidence

**Open.** Plateau and amplitudes at the fast, slow and summed rates in the same wild-type Cx43 conductance trace at a fixed voltage.

- [For two independent Cx43 gates in series, the measured plateau times the mixed amplitude equals the product of the fast and slow amplitudes at fixed voltage.](../WET_LAB_EVIDENCE.md#pair-cx43-series-mixed-amplitude) · Comparison unresolved

In wild-type rat Cx43 oocyte pairs, a −100 mV step gave fast and slow fitted time constants of 417 ± 175 ms and 7.06 ± 1.28 s, with a fast-to-slow amplitude ratio of 3. Figure 3 shows the voltage series for six pairs (mean ± SEM). The two-component fit leaves the mixed amplitude open. An independent untagged Cx43 series also resolved large fast and small slow amplitudes. Both studies fitted two decays, leaving the predicted mixed amplitude unmeasured. [Revilla et al., Fig. 3 and p. 1377](https://doi.org/10.1016/S0006-3495(99)76986-9)

**Unit** conductance normalized to a common reference

### revilla1999_cx43_kinetics@1

Paired Xenopus oocytes. Untagged rat Cx43 on both sides. Same publication as the registered Cx43 steady-conductance fits. Figure 3A–C and Results, wild-type rat Cx43 homotypic junctions [Revilla, Castro and Barrio (1999), Fig. 3A–B](https://doi.org/10.1016/S0006-3495(99)76986-9)

- **Evidence role** descriptive

Reported rounded ratio. The paper presents kinetic and conductance series from six pairs. No separate sampling interval for this amplitude ratio.

At −100 mV, fitted fast and slow times were 417 ± 175 ms and 7.06 ± 1.28 s. The fast-to-slow amplitude ratio was 3. The fitted model contains two decay terms. [Dataset manifest](../checks/data/membrane_physiology_pairs.json) · [Comparison verdict](../PROGRESS.md#paired-membrane-physiology)

### desplantez2011_cx43_kinetics@1

Homotypic untagged Cx43 in paired HeLa cells, dual whole-cell clamp at 22–25 °C. The fast and slow contributions are fractions of the initial decaying component. Results on current deactivation and Table 3, wt-Cx43/wt-Cx43 row [Desplantez et al. (2011), Table 3](https://doi.org/10.1007/s00232-011-9352-z)

- **Evidence role** descriptive

Table 3 reports mean ± SEM across seven pairs. The WT fast time-constant comparison in their Fig. 5 and Table 2 reuses their 2004 series. The authors describe slow time constants as difficult to estimate.

At 110 mV the untagged pairs gave initial fast and slow fractions of 80.0 ± 3.8% and 20.0 ± 3.8%. The fitted components share a normalization. There is no separately measured term at the sum of the fast and slow rates. [Dataset manifest](../checks/data/membrane_physiology_pairs.json) · [Comparison verdict](../PROGRESS.md#paired-membrane-physiology)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
