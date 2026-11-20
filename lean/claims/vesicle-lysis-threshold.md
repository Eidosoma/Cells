<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Changing molecular area units preserves the exact vesicle rupture decision

When molecular areas and the physical floor are preserved, two choices of area quantum give identical physical area, capped volume, tension and strict rupture verdict for the same post-event counts.

## Assumptions

- Only the area unit and all associated integer weights and floor are rescaled. Solute count, temperature, bath, physical area and rupture threshold remain fixed.
- The synthetic founder has five membrane lipids and four trapped osmoles. The only possible first event detaches one lipid. The comparison observes the outcome of that event.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.Vesicle.refinement_outcome](../CellsProofs/Chemistry/Vesicle.lean#L165)

Direct proof subject `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`

Uses [Bilayer area is half the sum of the molecular footprints in its two leaflets](bilayer-footprint.md) · [Membrane area caps the volume that minimizes a vesicle’s osmotic free energy](osmotic-vesicle-volume.md)

## Numerical comparison

**Failed.** The first event has reference tension 0.0008412963098275772 N/m. At thresholds about 3 × 10⁻¹⁸ N/m below and above it, the 60-quanta representation ruptured both times and the equivalent 1,920-quanta representation remained intact both times. Both matched the reference at thresholds 1% away. Computing physical area first recovered both close decisions in float64.

**Engine** `cells.assembly_lineages@2`, `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`, `cells.ideal_mixing@1`, `cells.phase_exchange@1`

[Logarithmic spherical volume coefficient](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/lumen.py#L86) · [Pressure and tension from the logarithmic sphere volume](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/lumen.py#L164) · [Strict compiled lysis test](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/kernel.py#L340) · [Lifecycle decision after the event](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/kernel.py#L516) · [Material release and energy booking](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/runner.py#L472) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/b2dea374a2d2bcba5c6eb860dd7e42bd263e628c/lean/checks/vesicle.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/b2dea374a2d2bcba5c6eb860dd7e42bd263e628c/lean/PROGRESS.md#vesicle-lysis-threshold)

[Tested engine 9d03bd2bd907](https://github.com/Eidosoma/Cells/commit/9d03bd2bd907a3c48bb43679b8e05c392df9adac) · [Evidence checkpoint b2dea374a2d2](https://github.com/Eidosoma/Cells/commit/b2dea374a2d2bcba5c6eb860dd7e42bd263e628c)

## Biological evidence

**Open.** Rupture at known membrane area, trapped solute and bath conditions. The dependence on the numerical area unit is assessed by rerunning an identical physical state.

**Unit** N/m

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
