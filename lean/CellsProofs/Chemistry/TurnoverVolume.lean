import Mathlib.Analysis.Calculus.Deriv.Inv
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Ring

/-! Amounts and volumes in two samples, or along a differentiable trajectory.
These readout identities do not prescribe how a biological source or sink responds to swelling. -/

namespace CellsProofs.Chemistry.TurnoverVolume

/-- Concentration change separates into a net amount change and dilution of the initial pool. -/
theorem endpoint_change (n₀ n₁ : ℝ) {v₀ v₁ : ℝ} (h₀ : 0 < v₀) (h₁ : 0 < v₁) :
    n₁ / v₁ - n₀ / v₀ = (n₁ - n₀) / v₁ - (n₀ / v₀) * ((v₁ - v₀) / v₁) := by
  field_simp [h₀.ne', h₁.ne']
  ring

/-- Gross production and loss enter the concentration slope only through their difference. -/
theorem concentration_rate {amount volume : ℝ → ℝ} {t made lost waterRate : ℝ}
    (hn : HasDerivAt amount (made - lost) t) (hv : HasDerivAt volume waterRate t)
    (pos : 0 < volume t) :
    HasDerivAt (fun s => amount s / volume s)
      ((made - lost) / volume t - (amount t / volume t) * (waterRate / volume t)) t := by
  convert hn.div hv pos.ne' using 1
  field_simp [pos.ne']
  ring

end CellsProofs.Chemistry.TurnoverVolume
