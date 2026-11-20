<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Membrane voltage in kidney epithelial cells under condition C3

In the fixed Na/K substitution series, two passive reversal voltages determine the higher-potassium C3 prediction. The assigned figure-reading intervals bound the prediction, its change from the shared C1 baseline and the signed error.

## Assumptions

- The reference calculation assumes fixed intracellular ion concentrations and relative permeabilities across conditions, at zero applied current and 25 °C. It omits pump and intercellular currents.
- External Na plus K and external Cl stay fixed. The two fitting doses are distinct. The exact C3 extrapolation has weight two, with a positive log argument throughout the assigned reading box.

## Lean proof

**Proved**

- [CellsProofs.Transport.ConditionedVoltage.bath_affine](../CellsProofs/Transport/ConditionedVoltage.lean#L21)
- [CellsProofs.Transport.ConditionedVoltage.reversal_iff_affine](../CellsProofs/Transport/ConditionedVoltage.lean#L27)
- [CellsProofs.Transport.ConditionedVoltage.two_point_fit](../CellsProofs/Transport/ConditionedVoltage.lean#L40)
- [CellsProofs.Transport.ConditionedVoltage.coefficients_unique](../CellsProofs/Transport/ConditionedVoltage.lean#L50)
- [CellsProofs.Transport.ConditionedVoltage.argument_pos_of_rising](../CellsProofs/Transport/ConditionedVoltage.lean#L67)
- [CellsProofs.Transport.ConditionedVoltage.extrapolation_bounds](../CellsProofs/Transport/ConditionedVoltage.lean#L76)
- [CellsProofs.Transport.ConditionedVoltage.c3_reading_bounds](../CellsProofs/Transport/ConditionedVoltage.lean#L93)

Uses [Three passive ions set one zero-current membrane voltage](mixed-ion-reversal.md)

## Numerical comparison

**Checked.** The fixed reference predicted −14.59 mV. All 81 sampled fit-reading pairs respected the proved corner bounds and twelve 60-digit crosschecks agreed within 7.11 × 10⁻¹⁵ mV. On three synthetic membranes with rising, flat and falling responses, the third-dose predictions agreed with the independent engine reversal within 2.05 × 10⁻¹⁴ mV.

**Reference calculation** `conditioned_ghk_affine_exp@1`

[Two-condition fit](https://github.com/Eidosoma/Cells/blob/a71c3f35b795114b520cca9b56fb95031aac18ba/tests/reference_conditioned_voltage.py#L76) · [Held-out prediction](https://github.com/Eidosoma/Cells/blob/a71c3f35b795114b520cca9b56fb95031aac18ba/tests/reference_conditioned_voltage.py#L103) · [Fixed BIO-002 protocol](https://github.com/Eidosoma/Cells/blob/a71c3f35b795114b520cca9b56fb95031aac18ba/configs/reference/bio002_conditioned_voltage_v1.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/a71c3f35b795114b520cca9b56fb95031aac18ba/scripts/evaluate_conditioned_voltage.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/a71c3f35b795114b520cca9b56fb95031aac18ba/reports/BIO002_CONDITIONED_VOLTAGE.md)

[Evidence checkpoint a71c3f35b795](https://github.com/Eidosoma/Cells/commit/a71c3f35b795114b520cca9b56fb95031aac18ba)

**Engine** `resolved_pump_tissue@3`, `cells.passive_constant_field_permeation@1`

[Individual passive fluxes](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/laws/routes/constant_field_permeation.py#L56) · [Summed membrane current](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/kinds/passive_routes.py#L550) · [Two-dose fit and reading corners](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/tests/reference_conditioned_voltage.py#L76) · [Fixture for the passive membrane routes](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/tests/unit/test_passive_routes_kind.py#L286) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/84e3078e3fa0f2a010192e4459abc72eee120b92/lean/checks/conditioned_voltage.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/84e3078e3fa0f2a010192e4459abc72eee120b92/lean/PROGRESS.md#conditioned-voltage-bounds)

[Tested engine 2ae89b5e2cd1](https://github.com/Eidosoma/Cells/commit/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007) · [Evidence checkpoint 84e3078e3fa0](https://github.com/Eidosoma/Cells/commit/84e3078e3fa0f2a010192e4459abc72eee120b92)

## Biological evidence

**Not assessable.** Whole-cell resting membrane voltage after application of extracellular solution C3.

**Unit** mV

### bonzanni2020_rptec_endpoints@1

RPTEC/TERT1 renal proximal tubule epithelial cells, whole-cell patch recording at zero applied current and 25 °C. C3 reports 20 cells across three experiments. Figure 2A–B gives the solution series. The C3 measurement is an approximate mean read from the patch-clamp results in Figure 3C. [Bonzanni et al. (2020)](https://doi.org/10.1242/bio.048553)

- **Evidence role** held out from fitting
- **Fit** C1, C2
- **Evaluation** C3
- **Excluded** C4, C5
- **Observed** -18 mV
- **Predicted** -14.59 mV

The ±2 mV bound describes the curator’s figure reading. The numerical standard error of the mean and the dependence between condition summaries are unknown.

The retrospective C3 prediction was 3.41 mV above the figure reading. The closeout records a descriptive result. Biological acceptance remains unresolved because experimental uncertainty and the recording boundary are insufficiently characterized. [Dataset manifest](../../data/biology/bonzanni2020_rptec_v1/manifest.json) · [Measurements](../../data/biology/bonzanni2020_rptec_v1/voltage_endpoints.csv) · [Comparison verdict](../../reports/bio-003-closeout.json)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
