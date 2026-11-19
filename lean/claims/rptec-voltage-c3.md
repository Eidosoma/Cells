<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Membrane voltage in kidney epithelial cells under condition C3

Fit a conditioned voltage equation on C1 and C2 and predict the membrane voltage under the higher-potassium C3 solution.

## Assumptions

- The reference calculation assumes fixed intracellular ion concentrations and relative permeabilities across conditions, at zero applied current and 25 °C. It omits pump and intercellular currents.

## Lean proof

**Open**

## Numerical comparison

**Checked.** The conditioned reference calculation agreed with an independent 60-digit calculation within 7.11 × 10⁻¹⁵ mV across twelve scalar checks.

**Reference calculation** `conditioned_ghk_affine_exp@1`

[Two-condition fit](https://github.com/Eidosoma/Cells/blob/a71c3f35b795114b520cca9b56fb95031aac18ba/tests/reference_conditioned_voltage.py#L76) · [Held-out prediction](https://github.com/Eidosoma/Cells/blob/a71c3f35b795114b520cca9b56fb95031aac18ba/tests/reference_conditioned_voltage.py#L103) · [Fixed BIO-002 protocol](https://github.com/Eidosoma/Cells/blob/a71c3f35b795114b520cca9b56fb95031aac18ba/configs/reference/bio002_conditioned_voltage_v1.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/a71c3f35b795114b520cca9b56fb95031aac18ba/scripts/evaluate_conditioned_voltage.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/a71c3f35b795114b520cca9b56fb95031aac18ba/reports/BIO002_CONDITIONED_VOLTAGE.md)

[Evidence checkpoint a71c3f35b795](https://github.com/Eidosoma/Cells/commit/a71c3f35b795114b520cca9b56fb95031aac18ba)

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
