<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Changing molecular area units preserves the exact vesicle rupture decision

When molecular areas and the physical floor are preserved, two choices of area quantum give identical physical area, capped volume, tension and strict rupture verdict for the same post-event counts. A vesicle that has survived a fixed threshold stays intact under that rule while every subsequent check sees no higher tension.

## Assumptions

- Only the area unit and all associated integer weights and floor are rescaled. Solute count, temperature, bath, physical area and rupture threshold remain fixed.
- The synthetic founder has five membrane lipids and four trapped osmoles. The only possible first event detaches one lipid. The comparison observes the outcome of that event.
- The hold argument fixes each vesicle's threshold through time. The survival measurements track the same cohort after an applied tension is established.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.Vesicle.refinement_outcome](../CellsProofs/Chemistry/Vesicle.lean#L165)
- [CellsProofs.Chemistry.Vesicle.no_new_rupture](../CellsProofs/Chemistry/Vesicle.lean#L178)
- [CellsProofs.Chemistry.Vesicle.fixed_survival_error](../CellsProofs/Chemistry/Vesicle.lean#L184)

Direct proof subject `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`

Uses [Bilayer area is half the sum of the molecular footprints in its two leaflets](bilayer-footprint.md) · [Membrane area caps the volume that minimizes a vesicle’s osmotic free energy](osmotic-vesicle-volume.md)

## Numerical comparison

**Checked.** The repaired tension calculation matched the independent reference in all eight compiled decisions. Both 60 and 1,920 area quanta gave rupture just below 0.0008412963098275772 N/m and survival just above it, including offsets of about 3 × 10⁻¹⁸ N/m. The older comparisons preserve the disagreement that led to the repair.

**Engine** `cells.assembly_lineages@2`, `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`, `cells.ideal_mixing@1`, `cells.phase_exchange@1`

[Repaired tension at the cap](https://github.com/Eidosoma/Cells/blob/6318b7d4f8d33251760834b6079aa27d88a81831/src/cells/models/assembly_lineages_v2/lumen.py#L170) · [Tension test at each event](https://github.com/Eidosoma/Cells/blob/6318b7d4f8d33251760834b6079aa27d88a81831/src/cells/models/assembly_lineages_v2/kernel.py#L340) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/78acb6bccc69cabbd8639a22975d87b5eabb42a2/lean/checks/vesicle.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/78acb6bccc69cabbd8639a22975d87b5eabb42a2/lean/PROGRESS.md#biological-model-review)

[Tested engine 6318b7d4f8d3](https://github.com/Eidosoma/Cells/commit/6318b7d4f8d33251760834b6079aa27d88a81831) · [Evidence checkpoint 78acb6bccc69](https://github.com/Eidosoma/Cells/commit/78acb6bccc69cabbd8639a22975d87b5eabb42a2)

**Engine** `cells.assembly_lineages@2`, `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`, `cells.ideal_mixing@1`, `cells.phase_exchange@1`

[Tension from the capped lumen](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/models/assembly_lineages_v2/lumen.py#L164) · [Strict rupture test at a state](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/models/assembly_lineages_v2/kernel.py#L340) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/84e3078e3fa0f2a010192e4459abc72eee120b92/lean/checks/vesicle.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/84e3078e3fa0f2a010192e4459abc72eee120b92/lean/PROGRESS.md#vesicle-threshold-hold)

[Tested engine 2ae89b5e2cd1](https://github.com/Eidosoma/Cells/commit/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007) · [Evidence checkpoint 84e3078e3fa0](https://github.com/Eidosoma/Cells/commit/84e3078e3fa0f2a010192e4459abc72eee120b92)

**Engine** `cells.assembly_lineages@2`, `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`, `cells.ideal_mixing@1`, `cells.phase_exchange@1`

[Logarithmic spherical volume coefficient](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/lumen.py#L86) · [Pressure and tension from the logarithmic sphere volume](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/lumen.py#L164) · [Strict compiled lysis test](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/kernel.py#L340) · [Lifecycle decision after the event](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/kernel.py#L516) · [Material release and energy booking](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/runner.py#L472) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/b2dea374a2d2bcba5c6eb860dd7e42bd263e628c/lean/checks/vesicle.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/b2dea374a2d2bcba5c6eb860dd7e42bd263e628c/lean/PROGRESS.md#vesicle-lysis-threshold)

[Tested engine 9d03bd2bd907](https://github.com/Eidosoma/Cells/commit/9d03bd2bd907a3c48bb43679b8e05c392df9adac) · [Evidence checkpoint b2dea374a2d2](https://github.com/Eidosoma/Cells/commit/b2dea374a2d2bcba5c6eb860dd7e42bd263e628c)

## Biological evidence

**Open.** Intact fraction of a vesicle cohort over time at known tension. The numerical area-unit invariance is tested on identical physical states in the engine.

**Unit** mN/m, seconds and fraction intact

### karal2015_dopc_hold@1

Pure DOPC giant unilamellar vesicles with matched sugar concentrations under a constant 8.0 mN/m aspiration tension. Time starts at the hold. Fig. 1a, open circles at 12 °C and open squares at 32 °C. [Karal and Yamazaki (2015), Fig. 1a](https://doi.org/10.1063/1.4930108)

- **Evidence role** descriptive

The published series reports 20 vesicles per temperature, but the plotted steps do not resolve those denominators. Fractions and times are approximate, and no pointwise errors are given.

At 12 °C survival fell from 0.50 at 92 s to 0.125 at 268 s. At 32 °C it fell from 0.50 at 33 s to 0.111 at 125 s. The published rupture rates were 0.0073 and 0.024 s⁻¹. Surviving vesicles continued to rupture at unchanged tension. [Dataset manifest](../checks/data/vesicle_rupture_holds.json) · [Comparison verdict](../PROGRESS.md#biological-model-review)

### shibly2016_dopc_hold@1

Pure DOPC vesicles at 25 ± 1 °C with an initial osmolarity difference of 2.8 mM, followed after osmotic equilibration. Open circles in Fig. 1B at the 4.3 mN/m aspiration setting. The results give n = 19. [Shibly et al. (2016), Fig. 1B](https://doi.org/10.1016/j.bpj.2016.09.043)

- **Evidence role** descriptive

Two time points in the same cohort, read from the plotted steps. Fig. 1B has no pointwise error bars. Osmotic tension was inferred in addition to the applied aspiration tension.

Of 19 starting vesicles, 8 remained at 40 s and 2 at 110 s. A constant survival fraction misses at least one reading by 3/19. A rupture rate of 0.0216 s⁻¹ fitted to the first count predicts 1.76 survivors at the second time in the same cohort. [Dataset manifest](../checks/data/vesicle_rupture_holds.json) · [Comparison verdict](../PROGRESS.md#biological-model-review)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
