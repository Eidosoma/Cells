import Mathlib.Analysis.SpecialFunctions.Log.Basic
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith

/-! # One ligand binding to one site at equilibrium

Bobbin et al., doi:10.1039/D3DD00077J, derive the Langmuir fraction from equal
association and dissociation rates. This Lean 4 proof uses free ligand in mM
and the dissociation constant of the one-step case of `cells.binding.rapid_binding@1`.
Upstream theorem: `langmuir_single_site_kinetic_derivation`, ATOMS Lab,
`LeanChemicalTheories` revision 00841fedb86c0af282f515eda7e83a525a42e048.
-/

namespace CellsProofs.Chemistry.SingleSite

/-- Fraction of sites occupied at free ligand concentration `c` and dissociation constant `kd`. -/
noncomputable def occupancy (c kd : ℝ) : ℝ := c / (kd + c)

theorem occupancy_from_rates {c free bound onRate offRate : ℝ}
    (hc : 0 ≤ c) (hsites : 0 < free + bound) (hon : 0 < onRate) (hoff : 0 < offRate)
    (balance : onRate * c * free = offRate * bound) :
    bound / (free + bound) = occupancy c (offRate / onRate) := by
  apply (div_eq_div_iff hsites.ne' (add_pos_of_pos_of_nonneg (div_pos hoff hon) hc).ne').2
  field_simp [hon.ne']
  nlinarith only [balance]

/-- The two forms have log weights zero and log(c) − log(kd) in the mM frame. -/
theorem occupancy_from_log_weights {c kd : ℝ} (hc : 0 < c) (hk : 0 < kd) :
    let weight := Real.exp (Real.log c - Real.log kd)
    weight / (1 + weight) = occupancy c kd := by
  dsimp only
  rw [Real.exp_sub, Real.exp_log hc, Real.exp_log hk]
  apply (div_eq_div_iff (by positivity : 0 < 1 + c / kd).ne' (add_pos hk hc).ne').2
  field_simp

end CellsProofs.Chemistry.SingleSite
