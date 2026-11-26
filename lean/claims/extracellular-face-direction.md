<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Extracellular face flux follows the electrochemical potential drop

Reversing the endpoints and voltage reverses the signed flux. A positive face coefficient gives positive flux exactly when the sender’s electrochemical potential is higher. At equilibrium the flux is zero, including when the concentration and electrical drives cancel.

## Assumptions

- Both endpoint concentrations and RT are positive. The two orientations use the same ion, temperature, geometry and diffusivity.
- The proof evaluates the two log-ratio branches and the fourth-degree small-gradient mean in exact real arithmetic. The force uses the difference of the endpoint logs.

## Lean proof

**Proved**

- [CellsProofs.Transport.Face.stableLogRatio_eq](../CellsProofs/Transport/LogMeanFace.lean#L28)
- [CellsProofs.Transport.Face.mean_swap](../CellsProofs/Transport/LogMeanFace.lean#L55)
- [CellsProofs.Transport.Face.mean_pos](../CellsProofs/Transport/LogMeanFace.lean#L62)
- [CellsProofs.Transport.Face.flux_reverse](../CellsProofs/Transport/LogMeanFace.lean#L87)
- [CellsProofs.Transport.Face.flux_at_equilibrium](../CellsProofs/Transport/LogMeanFace.lean#L93)
- [CellsProofs.Transport.Face.flux_pos_iff](../CellsProofs/Transport/LogMeanFace.lean#L97)

Direct proof subject `cells.route.logmean_electrodiffusion@1`

## Numerical comparison

**Checked.** Opposing voltage reversed a resolved concentration-driven flux. At zero voltage, 100.00000000000001 and 100 mM gave zero CPU flux versus 1.42 × 10⁻¹⁸ fmol/s in the scalar reference. The absolute tolerance was 3 × 10⁻¹² fmol/s. Across 60 tissue flux observations, the largest absolute discrepancy was 1.50 × 10⁻¹⁷ fmol/s.

**Engine** `resolved_pump_tissue@3`, `logmean_electrodiffusion@1`

[Face law](https://github.com/Eidosoma/Cells/blob/c9549dfc553ce2e9cce5d05160c24b1879e3077b/src/cells/laws/routes/logmean_electrodiffusion.py#L13) · [Piecewise logarithmic mean](https://github.com/Eidosoma/Cells/blob/c9549dfc553ce2e9cce5d05160c24b1879e3077b/src/cells/numerics/extracellular_field.py#L48) · [Force, flux and power](https://github.com/Eidosoma/Cells/blob/c9549dfc553ce2e9cce5d05160c24b1879e3077b/src/cells/numerics/surface_transport.py#L292) · [Independent scalar calculation](https://github.com/Eidosoma/Cells/blob/c9549dfc553ce2e9cce5d05160c24b1879e3077b/validation/tissue/surface_reference.py#L98) · [Numerical tolerances](https://github.com/Eidosoma/Cells/blob/c9549dfc553ce2e9cce5d05160c24b1879e3077b/validation/tissue/surface_protocol.json#L27) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/0c2e9f962480f430c2383bb1dddf97477f434335/lean/checks/logmean_face.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/0c2e9f962480f430c2383bb1dddf97477f434335/lean/PROGRESS.md#19-november-2026--extracellular-face-electrodiffusion)

[Tested engine c9549dfc553c](https://github.com/Eidosoma/Cells/commit/c9549dfc553ce2e9cce5d05160c24b1879e3077b) · [Evidence checkpoint 0c2e9f962480](https://github.com/Eidosoma/Cells/commit/0c2e9f962480f430c2383bb1dddf97477f434335)

## Biological evidence

**Open.** Species-resolved ion transfer rate between two extracellular compartments, with measured concentrations at both endpoints and their voltage difference.

Diluting NaCl on opposite sides of a claudin-2 pore shifted its current-reversal voltage in opposite directions. Reversal of an individual ion’s net flux remains unmeasured. [Weber et al., Fig. 6A–B](https://elifesciences.org/articles/09906)

**Unit** fmol/s

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
