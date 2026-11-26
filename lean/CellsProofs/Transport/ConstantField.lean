import Mathlib.Data.Complex.Exponential

/-! # Constant-field junction transport

Cells' `cells.route.constant_field@1` uses the Goldman–Hodgkin–Katz flux from sender to receiver.
Concentrations are in mM, voltage is sender potential minus receiver potential in V,
and flux is in fmol/s. The same proofs apply to the analytic Bernoulli factor
and the engine's near-zero series, both interpreted over the reals.
-/

namespace CellsProofs.Transport

noncomputable section

/-- The zero-voltage value is the only property of the evaluation method needed here. -/
structure NormalizedFactor where
  eval : ℝ → ℝ
  eval_zero : eval 0 = 1

/-- Analytic Bernoulli factor with its removable singularity filled in. -/
def analyticFactor : NormalizedFactor where
  eval x := if x = 0 then 1 else x / (Real.exp x - 1)
  eval_zero := by simp

/-- The two selected branches of the Cells evaluator, in real arithmetic. -/
def seriesFactor : NormalizedFactor where
  eval x := if |x| < (1 / 10000 : ℝ) then
    1 - x / 2 + x ^ 2 / 12 - x ^ 4 / 720
  else x / (Real.exp x - 1)
  eval_zero := by norm_num

/-- `scale` is area × permeability × opening divided by mol/fmol.
`voltageFactor` is zF/(RT), including the signed ionic valence. -/
def constantFieldFlux (factor : NormalizedFactor) (scale voltageFactor sender receiver voltage : ℝ) :
    ℝ :=
  let x := voltageFactor * voltage
  scale * (sender * factor.eval (-x) - receiver * factor.eval x)

/-- Reversing both endpoints and the voltage convention reverses the signed flux. -/
theorem flux_reverse (factor : NormalizedFactor) (scale voltageFactor sender receiver voltage : ℝ) :
    constantFieldFlux factor scale voltageFactor receiver sender (-voltage) =
      -constantFieldFlux factor scale voltageFactor sender receiver voltage := by
  simp only [constantFieldFlux, mul_neg, neg_neg]
  symm
  rw [← mul_neg, neg_sub]

theorem flux_zero_voltage (factor : NormalizedFactor) (scale voltageFactor sender receiver : ℝ) :
    constantFieldFlux factor scale voltageFactor sender receiver 0 = scale * (sender - receiver) := by
  simp [constantFieldFlux, factor.eval_zero]

/-- An open, permeable route at equal potentials carries this species down its gradient. -/
theorem flux_down_gradient (factor : NormalizedFactor) (scale voltageFactor sender receiver : ℝ)
    (openRoute : 0 < scale) (gradient : receiver < sender) :
    0 < constantFieldFlux factor scale voltageFactor sender receiver 0 := by
  rw [flux_zero_voltage]
  exact mul_pos openRoute (sub_pos.mpr gradient)

theorem flux_blocked (factor : NormalizedFactor) (voltageFactor sender receiver voltage : ℝ) :
    constantFieldFlux factor 0 voltageFactor sender receiver voltage = 0 := by
  simp [constantFieldFlux]

end

end CellsProofs.Transport
