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

Direct proof subject `cells.scheduled_compartment_wash@1`, `cells.site_occupancy@1`

Proof sources [Finite compartment draw and refill](../CellsProofs/Tissue/CompartmentWash.lean)

Uses [A partial wash dilutes free tracer and preserves its inventory](compartment-wash.md) · [Competing binding sites retain capacity through an SSPRK step](site-occupancy-stages.md)

## Numerical comparison

**Checked.** The FR-28 candidate collected 30 fmol from 60 free in a 100 fmol well. The wall held 10 fmol at the event and 9.97015402 fmol at the next step, 10 ms later. Both wall owners yielded identical traces. A matched buffer gave zero wall rate.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.scheduled_compartment_wash@1`, `cells.site_occupancy@1`

[Liquid sample, refill and ledgers](https://github.com/Eidosoma/Cells/blob/9917e3d9567993e1019c8caafa89f8653ee6ea9b/src/cells/operators/wash_schedule.py#L420-L501) · [Surface binding rate and sign convention](https://github.com/Eidosoma/Cells/blob/9917e3d9567993e1019c8caafa89f8653ee6ea9b/src/cells/operators/site_occupancy.py#L927-L932) · [Scheduled controls at the event](https://github.com/Eidosoma/Cells/blob/9917e3d9567993e1019c8caafa89f8653ee6ea9b/src/cells/definitions/pump_composite_spec.py#L258-L280) · [Accepted history and checkpoint](https://github.com/Eidosoma/Cells/blob/9917e3d9567993e1019c8caafa89f8653ee6ea9b/src/cells/execution/runner.py) · [Node and stand-in well fixtures](https://github.com/Eidosoma/Cells/blob/9917e3d9567993e1019c8caafa89f8653ee6ea9b/validation/tissue/wash_schedule_fixtures.py#L56-L115) · [Well geometry and initial free tracer](https://github.com/Eidosoma/Cells/blob/9917e3d9567993e1019c8caafa89f8653ee6ea9b/validation/tissue/secreted_species_fixtures.py) · [Node versus stand-in regression](https://github.com/Eidosoma/Cells/blob/9917e3d9567993e1019c8caafa89f8653ee6ea9b/tests/unit/test_wash_schedule_runs.py#L61-L93) · [Retention and subsequent release](https://github.com/Eidosoma/Cells/blob/a710e377ea87a865af46a1e6b2d7cf3574ff5aa3/lean/CellsProofs/Tissue/WallWash.lean) · [Finite-pool wash identity](https://github.com/Eidosoma/Cells/blob/a710e377ea87a865af46a1e6b2d7cf3574ff5aa3/lean/CellsProofs/Tissue/CompartmentWash.lean) · [Albumin rinse and residual measurements](https://github.com/Eidosoma/Cells/blob/a710e377ea87a865af46a1e6b2d7cf3574ff5aa3/lean/checks/data/robinson2014_wall_wash.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/a710e377ea87a865af46a1e6b2d7cf3574ff5aa3/lean/checks/wall_wash.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/a710e377ea87a865af46a1e6b2d7cf3574ff5aa3/lean/PROGRESS.md#fr28-wall-wash)

[Tested engine 9917e3d95679](https://github.com/Eidosoma/Cells/commit/9917e3d9567993e1019c8caafa89f8653ee6ea9b) · [Evidence checkpoint a710e377ea87](https://github.com/Eidosoma/Cells/commit/a710e377ea87a865af46a1e6b2d7cf3574ff5aa3)

## Biological evidence

**Open.** Tracer recovered in each wash and on the surface, with the time between dilution and measurement.

**Unit** µg in pooled liquid and ng/cm² on the disk in the experiment, fmol and fmol/s in Cells

### robinson2014_albumin_wall_wash

The authors counted labelled albumin in six successive rinses and on the final disk. A separate pH 5 endpoint yielded 8.759 µg in pooled liquid and 22.96 ng/cm² on polyethylene terephthalate (0.22%, four replicates). Supplementary Figure S3 and Tables S2 and S4, material 7. [Robinson et al. (2014), Clinica Chimica Acta](https://doi.org/10.1016/j.cca.2014.01.035)

- **Evidence role** descriptive

The rinse series has no per-rinse dwell time or error bars. The tabulated endpoint pools the starting sample, rinses and pipette tip and has no condition-specific uncertainty.

Independent recovery of tracer in liquid and on the surface is measured. The instantaneous bound fraction and the synthetic release constant remain open. [Dataset manifest](../checks/data/robinson2014_wall_wash.json) · [Comparison verdict](../PROGRESS.md#fr28-wall-wash)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
