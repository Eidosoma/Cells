<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# The proposed two-gate junction constrains its decay amplitudes

At fixed voltage, multiplying two independent relaxing gate factors gives a plateau P and terms at the fast rate, the slow rate and their sum. Their signed amplitudes satisfy P × A_mixed = A_fast × A_slow. With a nonzero plateau, measuring the fast and slow amplitudes determines the mixed amplitude.

## Assumptions

- Each gate relaxes exponentially toward its own fixed plateau. Junction conductance is proportional to the product of the two factors with a common time origin.
- The reported conductance can be divided by a common reference. Any additive background has been removed. Interpreting the three amplitudes separately requires distinct positive gate rates and a trace that resolves them.

## Lean proof

**Proved**

- [CellsProofs.Transport.JunctionGate.series_clamp_expansion](../CellsProofs/Transport/JunctionGate.lean#L112)
- [CellsProofs.Transport.JunctionGate.series_amplitudes](../CellsProofs/Transport/JunctionGate.lean#L122)

Proof sources [FR-30 product of independent gate factors at constant voltage](../../docs/JUNCTION_TWO_RELAXATION_DESIGN.md#L174)

## Numerical comparison

**Open.** FR-30 is a proposed extension to resolved_pump_tissue@3. A numerical comparison requires its two-gate implementation.

## Biological evidence

**Open.** Plateau and amplitudes at the fast, slow and summed rates in the same wild-type Cx43 conductance trace at a fixed voltage.

In wild-type rat Cx43 oocyte pairs, a −100 mV step gave fast and slow fitted time constants of 417 ± 175 ms and 7.06 ± 1.28 s, with a fast-to-slow amplitude ratio of 3. Figure 3 shows the voltage series for six pairs (mean ± SEM). The two-component fit leaves the mixed amplitude open. [Revilla et al., Fig. 3 and p. 1377](https://doi.org/10.1016/S0006-3495(99)76986-9)

**Unit** conductance normalized to a common reference

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
