<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Changing molecular area units preserves the exact vesicle rupture decision

When molecular areas and the physical floor are preserved, two choices of area quantum give identical physical area, capped volume, tension and strict rupture verdict for the same post-event counts. A vesicle that has survived a fixed threshold stays intact under that rule while every subsequent check sees no higher tension.

## Assumptions

- Only the area unit and all associated integer weights and floor are rescaled. Solute count, temperature, bath, physical area and rupture threshold remain fixed.
- The synthetic founder has five membrane lipids and four trapped osmoles. The only possible first event detaches one lipid. The comparison observes the outcome of that event.
- The hold argument fixes each vesicle's threshold through time. The survival measurements track the same cohort after an applied tension is established.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.Vesicle.refinement_outcome](../CellsProofs/Chemistry/Vesicle.lean#L171)
- [CellsProofs.Chemistry.Vesicle.no_new_rupture](../CellsProofs/Chemistry/Vesicle.lean#L184)
- [CellsProofs.Chemistry.Vesicle.fixed_survival_error](../CellsProofs/Chemistry/Vesicle.lean#L190)

Direct proof subject `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`

Uses [Bilayer area is half the sum of the molecular footprints in its two leaflets](bilayer-footprint.md) · [Membrane area caps the volume that minimizes a vesicle’s osmotic free energy](osmotic-vesicle-volume.md)

## Numerical comparison

**Checked.** The repaired tension calculation matched the independent reference in all eight compiled decisions. Both 60 and 1,920 area quanta gave rupture just below 0.0008412963098275772 N/m and survival just above it, including offsets of about 3 × 10⁻¹⁸ N/m. The older comparisons preserve the disagreement that led to the repair.

**Engine** `cells.assembly_lineages@2`, `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`, `cells.ideal_mixing@1`, `cells.phase_exchange@1`, `cells.membrane_permeation@1`

[Repaired tension at the cap](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/lumen.py) · [Tension test at each event](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/kernel.py) · [Volume and tension in the run record](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/runner.py) · [assembly lineage v2 fixtures](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/tests/assembly_lineage_v2_fixtures.py) · [test assembly lineages v2 lumen](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/tests/unit/test_assembly_lineages_v2_lumen.py) · [kucerka2011 popc](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/data/kucerka2011_popc.json) · [wolfisberg2025 vesicle](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/data/wolfisberg2025_vesicle.json) · [shibly2016 swelling](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/data/shibly2016_swelling.json) · [vesicle rupture holds](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/data/vesicle_rupture_holds.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/vesicle.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/PROGRESS.md#ol5-six-replays)

[Tested engine 329e9e395ac1](https://github.com/Eidosoma/Cells/commit/329e9e395ac117998657a21eb827192d34314107) · [Evidence checkpoint ad1f96418722](https://github.com/Eidosoma/Cells/commit/ad1f96418722d25876b38b5a5f38996512d6a32c)

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

- [A single, time-independent critical tension determines when a pure DOPC vesicle ruptures on a hold or ramp.](../WET_LAB_EVIDENCE.md#pair-dopc-rupture-time-history) · Challenged by both studies

Under strong hypotonic swelling, three pores resealed successively in the same vesicle, each within one second. This measures a surviving-vesicle outcome relevant to FR-39. The assembly rule books terminal lysis once per lineage. [Oglęcka et al., Figure 5](https://elifesciences.org/articles/03695/figures#fig5)

**Unit** mN/m, seconds, fraction intact and inverse seconds

### evans2003_dopc_tension_ramps@1

Micropipette aspiration of giant DOPC vesicles with a sustained linear tension ramp until rupture. Fig. 3, middle column, experimental DOPC histograms, p. 268. Fig. 4 compares peak rupture tensions. [Evans and Heinrich (2003), Figs. 3–4](https://doi.org/10.1016/S1631-0705(03)00044-6)

- **Evidence role** descriptive

Intervals describe the high-count parts of the plotted histograms and carry no confidence interpretation. The overlaid theoretical curves were excluded.

The faster tension ramp shifted the distribution of rupture tensions upward in independently measured DOPC vesicles. This constrains application of a fixed rupture threshold; a tension ramp cannot establish the hazard at constant tension. [Dataset manifest](../checks/data/paired_wet_lab_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-transport-and-membrane-measurements)

### karal2015_dopc_tension_series@1

Survival during constant aspiration tension was fitted in pure DOPC vesicles. Two temperature columns have fitted first-rupture rates at 7.0, 7.5 and 8.0 mN/m. Figure 2a, journal page 081103-3. [Karal and Yamazaki (2015), Fig. 2a](https://doi.org/10.1063/1.4930108)

- **Evidence role** descriptive

Three independent experiments per setting, each with 20 vesicles. The plotted bars are standard errors across experiments. The linked data contain the digitized log rates and bar caps.

At about 25 °C the three rates were 0.00263, 0.00556 and 0.0153 s⁻¹. At about 32 °C they were 0.00423, 0.00813 and 0.0230 s⁻¹. These are targets for the proposed FR-31 time-dependent rupture law. [Dataset manifest](../checks/data/karal2015_rupture_rates.json) · [Comparison verdict](../PROGRESS.md#vesicle-and-translation-evidence)

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
