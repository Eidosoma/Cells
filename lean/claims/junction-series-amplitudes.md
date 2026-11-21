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

Proof sources [FR-30 product of independent gate factors at constant voltage](../../docs/JUNCTION_TWO_RELAXATION_DESIGN.md#L174) · [Constant-voltage step and product conductance](../../src/cells/laws/junctions/junction_series_gates.py#L134)

## Numerical comparison

**Checked.** Across all four gate-kind pairings, five clamp voltages and six times, the compiled conductance and two route factors agreed with the scalar calculation within 2.23 × 10⁻¹⁶. This tests the FR-30 module directly. Its integration and registration in the tissue host are pending.

**Engine** `junction_series_gates@1`

[Two gate types, exact clamp and route factors](https://github.com/Eidosoma/Cells/blob/d74f519d40b9a9f7488b94b489c6dc4dd865504c/src/cells/laws/junctions/junction_series_gates.py) · [Threshold gate rates](https://github.com/Eidosoma/Cells/blob/d74f519d40b9a9f7488b94b489c6dc4dd865504c/src/cells/laws/junctions/junction_voltage_relaxation.py#L41) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/lean/checks/junction_series_gates.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/lean/PROGRESS.md#nov21-features)

[Tested engine d74f519d40b9](https://github.com/Eidosoma/Cells/commit/d74f519d40b9a9f7488b94b489c6dc4dd865504c) · [Evidence checkpoint ceeca19816ac](https://github.com/Eidosoma/Cells/commit/ceeca19816acd761ab68379d67bb0f7426366a1c)

## Biological evidence

**Open.** Plateau and amplitudes at the fast, slow and summed rates in the same wild-type Cx43 conductance trace at a fixed voltage.

In wild-type rat Cx43 oocyte pairs, a −100 mV step gave fast and slow fitted time constants of 417 ± 175 ms and 7.06 ± 1.28 s, with a fast-to-slow amplitude ratio of 3. Figure 3 shows the voltage series for six pairs (mean ± SEM). The two-component fit leaves the mixed amplitude open. [Revilla et al., Fig. 3 and p. 1377](https://doi.org/10.1016/S0006-3495(99)76986-9)

**Unit** conductance normalized to a common reference

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
