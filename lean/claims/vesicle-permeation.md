<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Neutral solute entry scales with area and spherical washout with inverse radius

The inward molecular rate equals permeability times area times outside number density. In an ideal lumen of fixed volume the exit rate per molecule is permeability times area divided by volume. On a sphere this predicts the first-order washout rate at a second radius from one calibration.

## Assumptions

- External density and permeability are fixed for the forward-area comparison. A neutral molecule crosses between the bath and lumen without changing the footprint.
- The outward concentration law assumes equal solution standard potentials, a well-mixed fixed volume and ideal solute with no extra energy change. A maintained solute-free exterior gives the exponential washout equation for the mean count.
- For the liposome assay, use the study’s inner radius for both area and volume, a 4 nm bilayer thickness and a common permeability between sizes. The compiled readout is the initial exit rate divided by molecule count.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.VesicleExchange.size_scaling](../CellsProofs/Chemistry/VesicleExchange.lean#L23)
- [CellsProofs.Chemistry.VesicleExchange.pair_balance](../CellsProofs/Chemistry/VesicleExchange.lean#L60)
- [CellsProofs.Chemistry.VesicleExchange.fixed_volume_drift](../CellsProofs/Chemistry/VesicleExchange.lean#L80)
- [CellsProofs.Chemistry.VesicleExchange.spherical_clearance](../CellsProofs/Chemistry/VesicleExchange.lean#L88)
- [CellsProofs.Chemistry.VesicleExchange.transfer_clearance](../CellsProofs/Chemistry/VesicleExchange.lean#L96)
- [CellsProofs.Chemistry.VesicleExchange.washout_derivative](../CellsProofs/Chemistry/VesicleExchange.lean#L103)

Direct proof subject `cells.membrane_permeation@1`

Uses [Lipid insertion scales with membrane area and diffusion-limited capture scales with radius](vesicle-phase-exchange.md) · [Bilayer area is half the sum of the molecular footprints in its two leaflets](bilayer-footprint.md) · [Production and first-order clearance preserve a positive pool and account for gross turnover](scheduled-species-turnover.md)

## Numerical comparison

**Checked.** Doubling radius quadrupled molecular entry under both lipid-encounter conventions. The compiled exit rate per molecule at counts 1, 7 and 14 was 1.7500 s⁻¹ at the calibration radius and 1.2971 s⁻¹ at the second radius. All rate controls agreed with their independent calculations within 2 × 10⁻¹³ relative error.

**Engine** `cells.assembly_lineages@2`, `cells.phase_exchange@1`, `cells.membrane_permeation@1`, `cells.bilayer_geometry@1`, `cells.ideal_mixing@1`

[Directional activities and geometric factor](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/exchange.py) · [Area or radius on the common footprint](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/kernel.py) · [assembly lineage v2 fixtures](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/tests/assembly_lineage_v2_fixtures.py) · [test assembly lineages v2 geometry](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/tests/unit/test_assembly_lineages_v2_geometry.py) · [vesicle exchange measurements](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/data/vesicle_exchange_measurements.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/vesicle_exchange.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/PROGRESS.md#ol5-six-replays)

[Tested engine 329e9e395ac1](https://github.com/Eidosoma/Cells/commit/329e9e395ac117998657a21eb827192d34314107) · [Evidence checkpoint ad1f96418722](https://github.com/Eidosoma/Cells/commit/ad1f96418722d25876b38b5a5f38996512d6a32c)

**Engine** `cells.assembly_lineages@2`, `cells.phase_exchange@1`, `cells.membrane_permeation@1`, `cells.bilayer_geometry@1`, `cells.ideal_mixing@1`

[Directional activities and geometric factor](https://github.com/Eidosoma/Cells/blob/3d3d9641932a52852727df7e4722e15ded245766/src/cells/models/assembly_lineages_v2/exchange.py#L42) · [Area or radius on the common footprint](https://github.com/Eidosoma/Cells/blob/3d3d9641932a52852727df7e4722e15ded245766/src/cells/models/assembly_lineages_v2/kernel.py#L327) · [Bidirectional engine rates](https://github.com/Eidosoma/Cells/blob/3d3d9641932a52852727df7e4722e15ded245766/src/cells/models/assembly_lineages_v2/kernel.py#L367) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/19de00d9a76a27fd064f1e643be28db630d48423/lean/checks/vesicle_exchange.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/19de00d9a76a27fd064f1e643be28db630d48423/lean/PROGRESS.md#vesicle-phase-exchange)

[Tested engine 3d3d9641932a](https://github.com/Eidosoma/Cells/commit/3d3d9641932a52852727df7e4722e15ded245766) · [Evidence checkpoint 19de00d9a76a](https://github.com/Eidosoma/Cells/commit/19de00d9a76a27fd064f1e643be28db630d48423)

**Engine** `cells.assembly_lineages@2`, `cells.membrane_permeation@1`, `cells.bilayer_geometry@1`, `cells.ideal_mixing@1`

[Permeation into the lumen](https://github.com/Eidosoma/Cells/blob/3d3d9641932a52852727df7e4722e15ded245766/src/cells/models/assembly_lineages_v2/permeation.py#L8) · [Reverse propensity and energy adjustment](https://github.com/Eidosoma/Cells/blob/3d3d9641932a52852727df7e4722e15ded245766/src/cells/models/assembly_lineages_v2/kernel.py#L289) · [Physical area of the bilayer](https://github.com/Eidosoma/Cells/blob/3d3d9641932a52852727df7e4722e15ded245766/src/cells/models/assembly_lineages_v2/geometry.py#L245) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/19de00d9a76a27fd064f1e643be28db630d48423/lean/checks/vesicle_exchange.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/19de00d9a76a27fd064f1e643be28db630d48423/lean/PROGRESS.md#vesicle-permeation)

[Tested engine 3d3d9641932a](https://github.com/Eidosoma/Cells/commit/3d3d9641932a52852727df7e4722e15ded245766) · [Evidence checkpoint 19de00d9a76a](https://github.com/Eidosoma/Cells/commit/19de00d9a76a27fd064f1e643be28db630d48423)

## Biological evidence

**Open.** Neutral-solute washout rate in fixed-size liposomes, and inward molecular uptake as a function of membrane area.

- [Urea crosses a protein-free POPC membrane down its concentration gradient, with comparable apparent permeability in influx and efflux assays.](../WET_LAB_EVIDENCE.md#pair-popc-urea-permeability) · Supported by both studies

**Unit** s⁻¹

### branden2010_urea_permeability@1

Protein-free tethered POPC liposomes, mean diameter about 71 nm, 22 °C. Fig. 3A and Passive diffusion results. [Brändén et al. (2010), Fig. 3A](https://doi.org/10.1016/j.bpj.2010.03.059)

- **Evidence role** descriptive

Uncertainty reported on the fitted rate. The article converts rate to permeability using the size and bilayer thickness.

The fitted efflux rate of 1.23 ± 0.06 s⁻¹ gave a permeability of 1.29 × 10⁻⁶ cm/s at 22 °C. [Dataset manifest](../checks/data/paired_wet_lab_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-wet-lab-evidence)

### peterlin2012_urea_permeability@1

Individual giant POPC vesicles exposed to external urea. Permeability inferred from swelling. Fig. 6a and Results §V. [Peterlin et al. (2012), Fig. 6a](https://doi.org/10.1039/C1SM06670F)

- **Evidence role** descriptive

The ± convention and assay temperature are unspecified here. The authors distinguish variation between vesicles from the uncertainty of individual fits.

The reported urea permeability was 0.013 ± 0.001 µm/s at 0.10 and 0.20 M. [Dataset manifest](../checks/data/paired_wet_lab_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-wet-lab-evidence)

### branden2010_glycerol_radius@1

Glycerol washed out of tethered POPC liposomes at 22 °C. Surface plasmon resonance tracked the change of internal concentration. Figure 3A and the accompanying results report the size-specific rates and the bilayer thickness. [Brändén et al. (2010), Fig. 3A and passive diffusion results](https://doi.org/10.1016/j.bpj.2010.03.059)

- **Evidence role** held out from fitting
- **Fit** 71 nm outer diameter, washout 1.75 ± 0.02 s⁻¹
- **Evaluation** 93 nm outer diameter
- **Observed** 1.46 s⁻¹
- **Predicted** 1.2971 s⁻¹

The smaller group reports ±0.02 s⁻¹ (n = 7). The 93 nm repeat has no published uncertainty or trace. Its exact concentration series is unspecified.

The larger liposomes emptied more slowly. Calibration at the smaller size underpredicts their rate by 0.163 s⁻¹. The uncertainty of the size transfer remains open. [Dataset manifest](../checks/data/vesicle_exchange_measurements.json) · [Comparison verdict](../PROGRESS.md#vesicle-permeation)

### peterlin2012_urea_size@1

Individual POPC vesicles stretched in the same 0.1 M urea bath. Swelling estimates net entry if water equilibrates rapidly and trapped sucrose is retained. Three unarrowed traces in Figure 2a, from 20 to 80 s after each radius minimum. [Peterlin et al. (2012), Fig. 2a](https://doi.org/10.1039/C1SM06670F)

- **Evidence role** descriptive

Moving either radius reading by ±0.10 µm gives ranges of 10.7–19.5, 15.9–32.1 and 25.6–47.3 fmol/s from smallest to largest. These describe figure resolution. Temperature and per-trace uncertainty were unreported.

For radii 31.80, 43.66 and 50.44 µm, inferred uptake was 15.1, 24.0 and 36.4 fmol/s. The largest/smallest uptake ratio was 2.41 and the compiled forward-area ratio was 2.52. The measured optical quantity was radius. [Dataset manifest](../checks/data/vesicle_exchange_measurements.json) · [Comparison verdict](../PROGRESS.md#vesicle-permeation)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
