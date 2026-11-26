<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A held bath can return to its original composition after supplying solute and work to tissue

Neutral formula units preserve bath charge. Across any sequence of solution changes, net controller dose and the bath’s ideal free-energy change depend only on the endpoints. The work delivered to tissue is the sum of the signed material supplied at each interval’s bath potential. A K-selective membrane at fixed intracellular K has a reversal shift set by the ratio of the two external K concentrations.

## Assumptions

- The bath is held at fixed volume, temperature and electrical potential. Each formula unit has integer counts and zero net valence. Signed offsets specify absolute targets against the initial composition. Every resulting species concentration is positive.
- Work is per species with positive supply into the tissue. The comparison uses ideal chemical potentials and the same held electrode potential before and after each switch.
- For the voltage comparison K⁺ is the only permeant ion. Intracellular K activity stays fixed during the voltage scan and the ratio of external concentrations represents the activity ratio. The biological comparison uses differences between group means at steady bath levels.

## Lean proof

**Proved**

- [CellsProofs.Tissue.BathSchedule.target_charge](../CellsProofs/Tissue/BathSchedule.lean#L25)
- [CellsProofs.Tissue.BathSchedule.neutral_event](../CellsProofs/Tissue/BathSchedule.lean#L32)
- [CellsProofs.Tissue.BathSchedule.salt_swap](../CellsProofs/Tissue/BathSchedule.lean#L52)
- [CellsProofs.Tissue.BathSchedule.changes_telescope](../CellsProofs/Tissue/BathSchedule.lean#L62)
- [CellsProofs.Tissue.BathSchedule.energy_booking](../CellsProofs/Tissue/BathSchedule.lean#L71)
- [CellsProofs.Tissue.BathSchedule.potential_change](../CellsProofs/Tissue/BathSchedule.lean#L80)
- [CellsProofs.Tissue.BathSchedule.switch_continuous](../CellsProofs/Tissue/BathSchedule.lean#L87)
- [CellsProofs.Tissue.BathSchedule.supply_work](../CellsProofs/Tissue/BathSchedule.lean#L92)
- [CellsProofs.Tissue.BathSchedule.epoch_sum](../CellsProofs/Tissue/BathSchedule.lean#L102)
- [CellsProofs.Tissue.BathSchedule.reversal_shift](../CellsProofs/Tissue/BathSchedule.lean#L114)

Direct proof subject `cells.operator.scheduled_bath_composition@1`

Uses [Balanced reactions preserve a weighted inventory](reaction-inventory.md) · [Ion charge sets permeation reversal and bounds the current–voltage slope](charged-permeation.md)

## Numerical comparison

**Checked.** Four neutral switches under ARS(2,2,2) and RK4 returned the bath’s net dose to zero, with 1.3955 × 10⁻⁴ fmol supplied to a finite pool. The work correction retained 2.5987 × 10⁻⁴ pJ. A separate 50-digit interval sum using each solver’s actual supply agreed within 5.43 × 10⁻²⁰ pJ at all 28 observations. The continuous finite-pool reference also checked the delivered amount. A compiled salt schedule reached all four experimental K concentrations.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `cells.constant_field@1`, `cells.logmean_electrodiffusion@1`

**Operators** `cells.scheduled_bath_composition@1`

[Bath event, dose, charge and energy](https://github.com/Eidosoma/Cells/blob/94327ec434ee49f543d2b2e046c6ddb2eaa5e902/src/cells/operators/bath_schedule.py#L456) · [Reservoir work correction](https://github.com/Eidosoma/Cells/blob/94327ec434ee49f543d2b2e046c6ddb2eaa5e902/src/cells/operators/bath_schedule.py#L498) · [Constant-field membrane flux](https://github.com/Eidosoma/Cells/blob/94327ec434ee49f543d2b2e046c6ddb2eaa5e902/src/cells/laws/junctions/selective.py#L19) · [Independent continuous finite-pool solution](https://github.com/Eidosoma/Cells/blob/94327ec434ee49f543d2b2e046c6ddb2eaa5e902/validation/fr10/references/faces.py#L150) · [Independent dose and free-energy records](https://github.com/Eidosoma/Cells/blob/94327ec434ee49f543d2b2e046c6ddb2eaa5e902/validation/fr10/references/records.py#L140) · [Independent sum of reservoir work over each interval](https://github.com/Eidosoma/Cells/blob/94327ec434ee49f543d2b2e046c6ddb2eaa5e902/validation/fr10/references/records.py#L230) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/22c5bb1c30b6eb79bdcf179392853755259a57e7/lean/checks/bath_schedule.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/22c5bb1c30b6eb79bdcf179392853755259a57e7/lean/PROGRESS.md#scheduled-bath-exchange)

[Tested engine 94327ec434ee](https://github.com/Eidosoma/Cells/commit/94327ec434ee49f543d2b2e046c6ddb2eaa5e902) · [Evidence checkpoint 22c5bb1c30b6](https://github.com/Eidosoma/Cells/commit/22c5bb1c30b6eb79bdcf179392853755259a57e7)

## Biological evidence

**Open.** Shift of the K-selective current reversal when extracellular KCl replaces NaCl in equal molar amounts. Local exchange time and the bath’s chemical work are separate observables.

**Unit** mV

### randle1991_potassium@1

Whole-cell recordings in adult guinea-pig ventricular myocytes. Each endpoint is the reversal of the current induced by 100 µM cromakalim. The Cells comparison uses the midpoint temperature of 34 °C. Mean reversal potentials at 1, 2.5, 5.4 and 12 mM extracellular K⁺ from the Results. The Methods give equimolar NaCl replacement and 33–35 °C. [Randle, Oliet and Renaud (1991), p. 1796 and Fig. 3a](https://doi.org/10.1111/j.1476-5381.1991.tb09865.x)

- **Evidence role** descriptive
- **Evaluation** All three adjacent concentration shifts, with no fitted voltages
- **Excluded** Rb and Cs substitutions, Current amplitude and conductance
- **Observed** 21.4 mV
- **Predicted** 21.14 mV

At the four doses, reported means ± SEM were −131.5 ± 1.8, −104.6 ± 6.9, −87.2 ± 1.9 and −65.8 ± 2.2 mV. Clear reversals occurred in 4/9, 9/18, 12/14 and 7/9 recorded cells. The shifts compare group means. The temperature range gives +21.07 to +21.20 mV for 5.4 → 12 mM.

The displayed comparison is the 5.4 → 12 mM K⁺ step. For 1 → 2.5 and 2.5 → 5.4 mM the predicted shifts were +24.25 and +20.38 mV, against observed shifts of +26.9 and +17.4 mV. This checks the equilibrium membrane response. Bath exchange timing and reservoir work remain unmeasured in these cells. [Dataset manifest](../checks/data/randle1991_potassium.json) · [Comparison verdict](../PROGRESS.md#scheduled-bath-exchange)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
