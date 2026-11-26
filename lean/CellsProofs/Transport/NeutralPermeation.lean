import CellsProofs.Transport.ConstantField
import Mathlib.Tactic.Ring

/-! # Passive permeation of a neutral species

For `cells.route.passive_neutral_permeation@1` the sender is outside and positive flux is
inward. The scale is area × permeability × opening divided by mol/fmol. In a
closed pair a flux `j` adds `j / vIn` to the inside concentration rate and
subtracts `j / vOut` from the outside concentration rate, with volumes in pL.
-/

namespace CellsProofs.Transport.Neutral

theorem flux_eq_fick (factor : NormalizedFactor) (scale cIn cOut voltage : ℝ) :
    constantFieldFlux factor scale 0 cOut cIn voltage = scale * (cOut - cIn) := by
  simpa only [constantFieldFlux, zero_mul] using flux_zero_voltage factor scale 0 cOut cIn

theorem inward_iff (factor : NormalizedFactor) {scale : ℝ} (h : 0 < scale) (cIn cOut voltage : ℝ) :
    0 < constantFieldFlux factor scale 0 cOut cIn voltage ↔ cIn < cOut := by
  rw [flux_eq_fick, mul_pos_iff_of_pos_left h, sub_pos]

/-- With fixed positive volumes, this is d(cOut − cIn)/dt = −k (cOut − cIn). -/
theorem closed_pair_gradient_rate (factor : NormalizedFactor) (scale cIn cOut voltage vIn vOut : ℝ) :
    let j := constantFieldFlux factor scale 0 cOut cIn voltage
    (-j) / vOut - j / vIn = -(scale * (1 / vIn + 1 / vOut)) * (cOut - cIn) := by
  dsimp only
  rw [flux_eq_fick]
  ring

end CellsProofs.Transport.Neutral
