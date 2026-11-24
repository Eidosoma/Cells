<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Saturable uptake from a finite pool conserves neutral solute

The saturable import route has a unique positive remaining amount for every finite nonnegative dose. The receiving cell gains the amount removed. For two simultaneous routes with the same saturation concentration, each cell receives its capacity fraction of the shared pool’s depletion.

## Assumptions

- Volume, patch area, saturation concentration and capacity stay fixed during each stage. The extracellular pool and its saturation amount are positive. The route moves a neutral species in one direction.
- The Newton bracket and residual-to-amount bound use exact real arithmetic. The CPU comparison also checks how accurately the stored float64 amounts resolve a nearly depleted pool.
- The continuous shared-pool allocation assumes the same K_M at both cells and no other sources, sinks or exchanges. The engine advances the two routes in a symmetric sequence.

## Lean proof

**Proved**

- [CellsProofs.Transport.SpeciesExchange.concentration_rate](../CellsProofs/Transport/SpeciesExchange.lean#L23)
- [CellsProofs.Transport.SpeciesExchange.primitive_rate](../CellsProofs/Transport/SpeciesExchange.lean#L30)
- [CellsProofs.Transport.SpeciesExchange.integrated_equation](../CellsProofs/Transport/SpeciesExchange.lean#L37)
- [CellsProofs.Transport.SpeciesExchange.root_bracket](../CellsProofs/Transport/SpeciesExchange.lean#L51)
- [CellsProofs.Transport.SpeciesExchange.unique_root](../CellsProofs/Transport/SpeciesExchange.lean#L72)
- [CellsProofs.Transport.SpeciesExchange.unique_remainder](../CellsProofs/Transport/SpeciesExchange.lean#L78)
- [CellsProofs.Transport.SpeciesExchange.finite_pool_booking](../CellsProofs/Transport/SpeciesExchange.lean#L92)
- [CellsProofs.Transport.SpeciesExchange.compose_stages](../CellsProofs/Transport/SpeciesExchange.lean#L106)
- [CellsProofs.Transport.SpeciesExchange.shared_pool_allocation](../CellsProofs/Transport/SpeciesExchange.lean#L114)
- [CellsProofs.Transport.SpeciesExchange.newton_bounds](../CellsProofs/Transport/SpeciesExchange.lean#L134)
- [CellsProofs.Transport.SpeciesExchange.iterate_bounds](../CellsProofs/Transport/SpeciesExchange.lean#L152)
- [CellsProofs.Transport.SpeciesExchange.amount_error_le_residual](../CellsProofs/Transport/SpeciesExchange.lean#L165)

Direct proof subject `cells.scheduled_species_exchange@1`

## Numerical comparison

**Checked.** 48 scalar cases per backend matched the independent reference. Six compiled two-cell runs conserved solute and reproduced the shared pool within 1.39 × 10⁻¹⁶ fmol. Halving the step reduced the cell allocation error by a factor of 4.01–4.06. At extreme depletion the 1 fmol anchor resolved a 6.31 × 10⁻¹⁶ fmol remainder to 5.65% and a smaller trial rounded to zero and was refused.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.scheduled_species_exchange@1`

[Newton solve in the log of the remaining fraction](https://github.com/Eidosoma/Cells/blob/b09b53f8583524a7c0b5526f3cd11ad4c33695ad/src/cells/operators/species_exchange.py#L305) · [Conservative endpoint bookings and positivity check](https://github.com/Eidosoma/Cells/blob/b09b53f8583524a7c0b5526f3cd11ad4c33695ad/src/cells/operators/species_exchange.py#L350) · [Symmetric stages by route rank](https://github.com/Eidosoma/Cells/blob/b09b53f8583524a7c0b5526f3cd11ad4c33695ad/src/cells/operators/species_exchange.py#L399) · [Independent 50-digit amount-space reference](https://github.com/Eidosoma/Cells/blob/b09b53f8583524a7c0b5526f3cd11ad4c33695ad/validation/fr1/references/forms.py#L107) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/de5b4621d8b624709302ee9d5c91f395e592ab1a/lean/checks/species_exchange.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/de5b4621d8b624709302ee9d5c91f395e592ab1a/lean/PROGRESS.md#saturable-species-exchange)

[Tested engine b09b53f85835](https://github.com/Eidosoma/Cells/commit/b09b53f8583524a7c0b5526f3cd11ad4c33695ad) · [Evidence checkpoint de5b4621d8b6](https://github.com/Eidosoma/Cells/commit/de5b4621d8b624709302ee9d5c91f395e592ab1a)

**Engine** `cells.assembly_lineages@2`, `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`, `cells.inward_rectifier_linear_driving_force@1`

**Operators** `cells.pool_withdrawal@1`, `cells.scheduled_compartment_wash@1`, `cells.site_occupancy@1`, `cells.scheduled_species_exchange@1`

[Bilayer area](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/assembly_lineages_v2/geometry.py#L249) · [Lumen tension and volume](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/assembly_lineages_v2/lumen.py#L265) · [Deterministic rupture decision](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/assembly_lineages_v2/kernel.py#L350) · [Bead-equivalent count withdrawal](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/assembly_lineages_v2/withdrawal.py#L150) · [Full wash at a bound wall](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/operators/wash_schedule.py#L472) · [Saturable uptake](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/operators/species_exchange.py#L335) · [Potassium reversal](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L55) · [Paired measurements](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/paired_wet_lab_measurements.json) · [Potassium changes in Müller cells](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/paired_calibration_measurements.json) · [Kir4.1 temperature and concentrations](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/tada1998_kir41.json) · [POPC molecular areas](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/leaflet_packing.json) · [First independent deflation study](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/fujiwara2014_vesicle.json) · [Survival during a tension hold](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/vesicle_rupture_holds.json) · [First bead-count groups](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/fornell2017_partition.json) · [Remaining bead counts and volume observations](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/pool_withdrawal_measurements.json) · [Bilayer area harness](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/leaflet_packing.py) · [Vesicle world](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/vesicle.py) · [Retained-osmole comparison](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/vesicle_events.py) · [Whole draw and site stocks](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/wall_wash.py) · [Pool event and count reconstruction](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/pool_withdrawal.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/paired_response_endpoints.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/PROGRESS.md#paired-law-replays)

[Tested engine 153449799f4d](https://github.com/Eidosoma/Cells/commit/153449799f4d301a34f2be58172becc4dc562806) · [Evidence checkpoint 9f27f80116ed](https://github.com/Eidosoma/Cells/commit/9f27f80116ed324e1adbbef7cddb5671d71f12f7)

## Biological evidence

**Open.** Initial neutral-solute uptake rate versus external concentration and a matched time course of extracellular depletion and intracellular gain.

- [Early 3-O-methylglucose influx into sugar-depleted human erythrocytes is half-saturated near 1–2 mM under cold conditions.](../WET_LAB_EVIDENCE.md#pair-cold-red-cell-sugar-affinity) · Supported by both studies
- [Initial 3-O-methylglucose influx saturates with increasing extracellular sugar in intact human erythrocytes on ice and at 15 °C.](../WET_LAB_EVIDENCE.md#pair-red-cell-sugar-saturation) · Supported by both studies

**Unit** µmol/L/min

### klepper2001_cold_red_cell_influx@1

Washed human erythrocytes, healthy adult intra-assay control, zero-trans radiolabeled 3-O-methyl-D-glucose influx. §2.4, Fig. 3B–C, Table 1 (pp. 105–108). [Klepper et al. (2001), Fig. 3B–C and Table 1](https://doi.org/10.1016/S0014-5793(01)02463-2)

- **Evidence role** descriptive

No uncertainty reported for the control Km. The larger healthy reference group in Fig. 3A is a different comparison.

The healthy control gave Kₘ 1.3 mM and maximal rate 1,275 ± 32 fmol/s per million cells (SD). It independently supports the half-saturation scale of the cold Cells calibration. Differing rate denominators limit the capacity comparison. [Dataset manifest](../checks/data/paired_wet_lab_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-wet-lab-evidence)

### batt1973_red_cell_influx@1

Two separate human blood samples, intact erythrocytes with zero trans sugar. Table V (p. 1692), influx column for 3-O-methyl-D-glucose. [Batt and Schachter (1973), Table V](https://doi.org/10.1172/JCI107350)

- **Evidence role** descriptive

Each row is a separate blood sample. Table V gives point estimates without errors.

The two influx Kₜ estimates, 5.0 and 6.1 mM at 15 °C, support saturable entry. They set a limit on transferring the cold calibration across preparations. [Dataset manifest](../checks/data/paired_wet_lab_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-wet-lab-evidence)

### sage2014_zero_trans@1

Human red cells on ice, 30 s uptake. The reported rate scale is used directly. The preparation’s effective patch area and the rate’s volume denominator are unspecified. Filled circles for 3-O-methylglucose uptake into initially sugar-depleted erythrocytes. [Sage and Carruthers (2014), Fig. 2A](https://doi.org/10.1152/ajpcell.00044.2014)

- **Evidence role** held out from fitting
- **Fit** 0.4 and 5 mM extracellular sugar
- **Evaluation** 0.1, 0.8, 1 and 3 mM extracellular sugar
- **Excluded** Sugar-preloaded exchange, Later equilibration, Dehydroascorbic acid
- **Observed** 117 µmol/L/min
- **Predicted** 108.1 µmol/L/min

The displayed 3 mM point is 117 ± 5 µmol/L/min (SE). Bars summarize three independent experiments in triplicate. The lowest-dose bar is unresolved. Estimated reading precision is ±1 µmol/L/min and ±0.02 mM.

The two-point calibration gave K_M = 1.19 mM. At 0.8, 1 and 3 mM the predicted rates were 60.7, 69.0 and 108.1 against 60 ± 4, 60 ± 8 and 117 ± 5. These comparisons test early uptake. Late depletion and two-cell allocation remain biologically open. [Dataset manifest](../checks/data/sage2014_zero_trans.json) · [Comparison verdict](../PROGRESS.md#saturable-species-exchange)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
