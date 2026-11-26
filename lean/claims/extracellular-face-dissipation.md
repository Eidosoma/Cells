<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Passive extracellular face transport dissipates energy

Each ion’s signed flux multiplied by its electrochemical potential drop is nonnegative. Summing the contributions over all ions gives nonnegative instantaneous face power.

## Assumptions

- Endpoint concentrations and RT are positive. Each ion has a nonnegative face coefficient. Power is evaluated at a single state.

## Lean proof

**Proved**

- [CellsProofs.Transport.Face.dissipation_nonneg](../CellsProofs/Transport/LogMeanFace.lean#L102)
- [CellsProofs.Transport.Face.power_in_pJ_per_s](../CellsProofs/Transport/LogMeanFace.lean#L111)
- [CellsProofs.Transport.Face.face_power_nonneg](../CellsProofs/Transport/LogMeanFace.lean#L116)

Direct proof subject `cells.route.logmean_electrodiffusion@1`

Proof sources [Dimensional algebra used by the optional check](https://github.com/ATOMSLab/LeanDimensionalAnalysis/tree/de263eed945693058ef2b8a1fa56c2ec5642ea7a/DimensionalAnalysis) · [Cells dimensional check](../checks/units/FacePower.lean) · [SI prefixes](https://www.bipm.org/en/measurement-units/si-prefixes)

Uses [Extracellular face flux follows the electrochemical potential drop](extracellular-face-direction.md)

## Numerical comparison

**Checked.** Face power agreed with the scalar reference across eleven CPU cases. Reversing a resolved flux and its endpoint bookings preserved the total material rate and gave −4.52 × 10⁻⁵ pJ/s, failing the direction and power checks.

**Engine** `resolved_pump_tissue@3`, `logmean_electrodiffusion@1`

[Face law](https://github.com/Eidosoma/Cells/blob/c9549dfc553ce2e9cce5d05160c24b1879e3077b/src/cells/laws/routes/logmean_electrodiffusion.py#L13) · [Piecewise logarithmic mean](https://github.com/Eidosoma/Cells/blob/c9549dfc553ce2e9cce5d05160c24b1879e3077b/src/cells/numerics/extracellular_field.py#L48) · [Force, flux and power](https://github.com/Eidosoma/Cells/blob/c9549dfc553ce2e9cce5d05160c24b1879e3077b/src/cells/numerics/surface_transport.py#L292) · [Independent scalar calculation](https://github.com/Eidosoma/Cells/blob/c9549dfc553ce2e9cce5d05160c24b1879e3077b/validation/tissue/surface_reference.py#L98) · [Numerical tolerances](https://github.com/Eidosoma/Cells/blob/c9549dfc553ce2e9cce5d05160c24b1879e3077b/validation/tissue/surface_protocol.json#L27) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/0c2e9f962480f430c2383bb1dddf97477f434335/lean/checks/logmean_face.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/0c2e9f962480f430c2383bb1dddf97477f434335/lean/PROGRESS.md#19-november-2026--extracellular-face-electrodiffusion)

[Tested engine c9549dfc553c](https://github.com/Eidosoma/Cells/commit/c9549dfc553ce2e9cce5d05160c24b1879e3077b) · [Evidence checkpoint 0c2e9f962480](https://github.com/Eidosoma/Cells/commit/0c2e9f962480f430c2383bb1dddf97477f434335)

## Biological evidence

**Open.** Instantaneous energy loss inferred from species-resolved fluxes and measured electrochemical potential differences across an extracellular interface.

Trout gill epithelia supplied two-way sodium tracer flux and voltage measurements. Active transport contributed to the measured flux, so passive heat production cannot be inferred from these data alone. [Galvez et al., Fig. 3 and Tables 1–2](https://www.zoology.ubc.ca/~woodcm/Woodblog/wp-content/uploads/2016/07/Galvez-et-al.-2008-In-Vitro-Cell.pdf)

**Unit** pJ/s

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
