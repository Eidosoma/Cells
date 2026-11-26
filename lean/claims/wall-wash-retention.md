<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A wash collects free tracer while surface-bound tracer can release later

A finite-volume wash collects the draw fraction of the free stock and preserves each bound stock at the event. At a previously equilibrated surface, dilution initiates net release. Free, bound, collected and supplied tracer satisfy one inventory through subsequent exchange.

## Assumptions

- A well-mixed compartment is refilled to its original volume. Only free tracer is accessible to the instantaneous draw. The wall and specimen each hold a separately tracked bound stock.
- For the strict release sign, the wash fraction, association rate and vacant site amount are positive, the buffer is more dilute than the free tracer, and the pre-wash surface is in binding equilibrium. The numerical well has unit binding multiplier and no internalisation.

## Lean proof

**Proved**

- [CellsProofs.Tissue.WallWash.event_retention](../CellsProofs/Tissue/WallWash.lean#L21)
- [CellsProofs.Tissue.WallWash.inventory](../CellsProofs/Tissue/WallWash.lean#L30)
- [CellsProofs.Tissue.WallWash.whole_stock_bias](../CellsProofs/Tissue/WallWash.lean#L38)
- [CellsProofs.Tissue.WallWash.rate_after_draw](../CellsProofs/Tissue/WallWash.lean#L43)
- [CellsProofs.Tissue.WallWash.release_after_dilution](../CellsProofs/Tissue/WallWash.lean#L52)

Direct proof subject `cells.operator.scheduled_compartment_wash@1`, `cells.operator.site_occupancy@1`

Proof sources [Finite compartment draw and refill](../CellsProofs/Tissue/CompartmentWash.lean)

Uses [A partial wash dilutes free tracer and preserves its inventory](compartment-wash.md) · [Competing binding sites retain capacity through an SSPRK step](site-occupancy-stages.md)

## Numerical comparison

**Checked.** Main’s stand-in and both FR-28 wall owners collected 30 fmol from 60 free. The wall held 10 fmol at the event and 9.97015402 fmol 10 ms later. Both candidate owners yielded identical traces. A matched buffer gave zero wall rate.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.scheduled_compartment_wash@1`, `cells.site_occupancy@1`

[Liquid sample, refill and ledgers](https://github.com/Eidosoma/Cells/blob/9917e3d9567993e1019c8caafa89f8653ee6ea9b/src/cells/operators/wash_schedule.py#L420-L501) · [Surface binding rate and sign convention](https://github.com/Eidosoma/Cells/blob/9917e3d9567993e1019c8caafa89f8653ee6ea9b/src/cells/operators/site_occupancy.py#L927-L932) · [Scheduled controls at the event](https://github.com/Eidosoma/Cells/blob/9917e3d9567993e1019c8caafa89f8653ee6ea9b/src/cells/definitions/pump_composite_spec.py#L258-L280) · [Accepted history and checkpoint](https://github.com/Eidosoma/Cells/blob/9917e3d9567993e1019c8caafa89f8653ee6ea9b/src/cells/execution/runner.py) · [Node and stand-in well fixtures](https://github.com/Eidosoma/Cells/blob/9917e3d9567993e1019c8caafa89f8653ee6ea9b/validation/tissue/wash_schedule_fixtures.py#L56-L115) · [Well geometry and initial free tracer](https://github.com/Eidosoma/Cells/blob/9917e3d9567993e1019c8caafa89f8653ee6ea9b/validation/tissue/secreted_species_fixtures.py) · [Node versus stand-in regression](https://github.com/Eidosoma/Cells/blob/9917e3d9567993e1019c8caafa89f8653ee6ea9b/tests/unit/test_wash_schedule_runs.py#L61-L93) · [Retention and subsequent release](https://github.com/Eidosoma/Cells/blob/a86c914fa3e0021c8b5c6335f8c402cf264c80ba/lean/CellsProofs/Tissue/WallWash.lean) · [Finite-pool wash identity](https://github.com/Eidosoma/Cells/blob/a86c914fa3e0021c8b5c6335f8c402cf264c80ba/lean/CellsProofs/Tissue/CompartmentWash.lean) · [Albumin rinse and residual measurements](https://github.com/Eidosoma/Cells/blob/a86c914fa3e0021c8b5c6335f8c402cf264c80ba/lean/checks/data/robinson2014_wall_wash.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/a86c914fa3e0021c8b5c6335f8c402cf264c80ba/lean/checks/wall_wash.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/a86c914fa3e0021c8b5c6335f8c402cf264c80ba/lean/PROGRESS.md#fr28-wall-wash)

[Tested engine 9917e3d95679](https://github.com/Eidosoma/Cells/commit/9917e3d9567993e1019c8caafa89f8653ee6ea9b) · [Evidence checkpoint a86c914fa3e0](https://github.com/Eidosoma/Cells/commit/a86c914fa3e0021c8b5c6335f8c402cf264c80ba)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.scheduled_compartment_wash@1`, `cells.site_occupancy@1`

[Stand-in geometry and initial stocks](https://github.com/Eidosoma/Cells/blob/587ba7873ac7c3112c00639687d7d86ee186c6fd/validation/tissue/wash_schedule_fixtures.py#L55-L88) · [Gross collection and refill](https://github.com/Eidosoma/Cells/blob/587ba7873ac7c3112c00639687d7d86ee186c6fd/src/cells/operators/wash_schedule.py#L420-L501) · [Binding and release rates on main](https://github.com/Eidosoma/Cells/blob/587ba7873ac7c3112c00639687d7d86ee186c6fd/src/cells/operators/site_occupancy.py#L901-L906) · [Scheduled controls at the event](https://github.com/Eidosoma/Cells/blob/587ba7873ac7c3112c00639687d7d86ee186c6fd/src/cells/definitions/pump_composite_spec.py#L258-L280) · [Accepted history and checkpoint](https://github.com/Eidosoma/Cells/blob/587ba7873ac7c3112c00639687d7d86ee186c6fd/src/cells/execution/runner.py) · [Main well regression](https://github.com/Eidosoma/Cells/blob/587ba7873ac7c3112c00639687d7d86ee186c6fd/tests/unit/test_wash_schedule_runs.py#L26-L59) · [Wash retention and rate identities](https://github.com/Eidosoma/Cells/blob/a86c914fa3e0021c8b5c6335f8c402cf264c80ba/lean/CellsProofs/Tissue/WallWash.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/a86c914fa3e0021c8b5c6335f8c402cf264c80ba/lean/checks/wall_wash.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/a86c914fa3e0021c8b5c6335f8c402cf264c80ba/lean/PROGRESS.md#fr28-main-stand-in)

[Tested engine 587ba7873ac7](https://github.com/Eidosoma/Cells/commit/587ba7873ac7c3112c00639687d7d86ee186c6fd) · [Evidence checkpoint a86c914fa3e0](https://github.com/Eidosoma/Cells/commit/a86c914fa3e0021c8b5c6335f8c402cf264c80ba)

**Engine** `cells.assembly_lineages@2`, `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`, `cells.inward_rectifier_linear_driving_force@1`

**Operators** `cells.pool_withdrawal@1`, `cells.scheduled_compartment_wash@1`, `cells.site_occupancy@1`, `cells.scheduled_species_exchange@1`

[Bilayer area](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/assembly_lineages_v2/geometry.py#L249) · [Lumen tension and volume](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/assembly_lineages_v2/lumen.py#L265) · [Deterministic rupture decision](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/assembly_lineages_v2/kernel.py#L350) · [Bead-equivalent count withdrawal](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/assembly_lineages_v2/withdrawal.py#L150) · [Full wash at a bound wall](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/operators/wash_schedule.py#L472) · [Saturable uptake](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/operators/species_exchange.py#L335) · [Potassium reversal](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L55) · [Paired measurements](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/paired_wet_lab_measurements.json) · [Potassium changes in Müller cells](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/paired_calibration_measurements.json) · [Kir4.1 temperature and concentrations](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/tada1998_kir41.json) · [POPC molecular areas](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/leaflet_packing.json) · [First independent deflation study](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/fujiwara2014_vesicle.json) · [Survival during a tension hold](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/vesicle_rupture_holds.json) · [First bead-count groups](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/fornell2017_partition.json) · [Remaining bead counts and volume observations](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/pool_withdrawal_measurements.json) · [Bilayer area harness](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/leaflet_packing.py) · [Vesicle world](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/vesicle.py) · [Retained-osmole comparison](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/vesicle_events.py) · [Whole draw and site stocks](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/wall_wash.py) · [Pool event and count reconstruction](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/pool_withdrawal.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/paired_response_endpoints.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/PROGRESS.md#paired-law-replays)

[Tested engine 153449799f4d](https://github.com/Eidosoma/Cells/commit/153449799f4d301a34f2be58172becc4dc562806) · [Evidence checkpoint 9f27f80116ed](https://github.com/Eidosoma/Cells/commit/9f27f80116ed324e1adbbef7cddb5671d71f12f7)

## Biological evidence

**Open.** Tracer recovered in each wash and on the surface, with the time between dilution and measurement.

- [Some albumin remains associated with uncoated expanded PTFE after a wash.](../WET_LAB_EVIDENCE.md#pair-albumin-washed-eptfe) · Supported by both studies

Two independent laboratories recovered human serum albumin from washed expanded PTFE. Their measurements constrain the presence of a retained stock. A release rate requires comparable times and pre-wash bound amounts.

**Unit** mass or fraction of initially adsorbed albumin, surface mass per area, fmol and fmol/s in Cells

### robinson2014_albumin_wall_wash

The authors counted labelled albumin in six successive rinses and on the final disk. A separate pH 5 endpoint yielded 8.759 µg in pooled liquid and 22.96 ng/cm² on polyethylene terephthalate (0.22%, four replicates). Supplementary Figure S3 and Tables S2 and S4, material 7. [Robinson et al. (2014), Clinica Chimica Acta](https://doi.org/10.1016/j.cca.2014.01.035)

- **Evidence role** descriptive

The rinse series has no per-rinse dwell time or error bars. The tabulated endpoint pools the starting sample, rinses and pipette tip and has no condition-specific uncertainty.

Independent recovery of tracer in liquid and on the surface is measured. The instantaneous bound fraction and the synthetic release constant remain open. [Dataset manifest](../checks/data/robinson2014_wall_wash.json) · [Comparison verdict](../PROGRESS.md#fr28-wall-wash)

### leibner2009_hsa_eptfe@1

Radiolabelled human serum albumin on expanded PTFE. Fig. 4 and Results §3.3, radiolabel distribution in one of three adsorption experiments. [Leibner et al. (2009), Fig. 4](https://doi.org/10.1016/j.actbio.2008.11.003)

- **Evidence role** descriptive

Bound fraction of adsorbed label after PBS rinses. Mass recovery exceeded 95% for the three trials. No uncertainty for these individual fractions, and substantial between-trial variation.

Three successive rinses removed part of the adsorbed albumin. At 10 and 30 mg/mL loading, 38.5% and 50.8% of adsorbed label remained after the third rinse. [Dataset manifest](../checks/data/paired_replay_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-law-replays)

### goyama2023_hsa_eptfe@1

Human serum albumin on uncoated expanded PTFE vascular grafts. Fig. 2 and protein adsorption methods, uncoated graft controls, post-wash extracted human serum albumin. [Goyama et al. (2023), Fig. 2](https://doi.org/10.1038/s41598-023-35594-7)

- **Evidence role** descriptive

Uncoated ePTFE was water-washed before protein extraction and quantification. Reported mean and SD retain the paper’s units. The rinse effluent and pre-wash bound mass were unmeasured.

Extraction after washing recovered 1.47 ± 1.36 µg/m² (reported mean ± SD, seven specimens). The different wash media and measurements preclude a common rate. [Dataset manifest](../checks/data/paired_replay_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-law-replays)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
