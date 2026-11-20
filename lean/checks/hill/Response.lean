import HillSelection
import Mathlib.Tactic.FieldSimp

/-! Response of a Cells activating or inhibiting Hill factor in exact real
arithmetic. The upstream functions use a power of x/K. The Cells helper takes
the log of concentration and evaluates exp(−logaddexp(0, ±z)). -/

namespace CellsProofs.Checks.Hill

open GRN.Dynamics

noncomputable def factor (active : Bool) (K n x : ℝ) : ℝ :=
  let z := n * (Real.log x - Real.log K)
  Real.exp (-(Real.log (1 + Real.exp (if active then -z else z))))

theorem factors_eq_hill {K x : ℝ} (hK : 0 < K) (hx : 0 < x) (n : ℝ) :
    factor true K n x = hill 0 1 K n x ∧ factor false K n x = hill 1 0 K n x := by
  let z := n * (Real.log x - Real.log K)
  have hp : (x / K) ^ n = Real.exp z := by
    rw [Real.rpow_def_of_pos (div_pos hx hK), Real.log_div hx.ne' hK.ne', mul_comm]
  have he := Real.exp_pos z
  have hsum : 0 < 1 + Real.exp z := by positivity
  have hinv : 0 < 1 + (Real.exp z)⁻¹ := by positivity
  constructor
  · change Real.exp (-(Real.log (1 + Real.exp (-z)))) = hill 0 1 K n x
    rw [Real.exp_neg z, Real.exp_neg, Real.exp_log hinv, hill, hp, one_mul, zero_add]
    field_simp
    exact add_comm _ _
  · change Real.exp (-(Real.log (1 + Real.exp z))) = hill 1 0 K n x
    rw [Real.exp_neg, Real.exp_log hsum, hill, hp, zero_mul, add_zero, one_div]

theorem ordered_factors {K n x y : ℝ} (hK : 0 < K) (hn : 0 < n) (hx : 0 < x) (hxy : x ≤ y) :
    factor true K n x ≤ factor true K n y ∧ factor false K n y ≤ factor false K n x := by
  have hy := hx.trans_le hxy
  obtain ⟨ax, ix⟩ := factors_eq_hill hK hx n
  obtain ⟨ay, iy⟩ := factors_eq_hill hK hy n
  rw [ax, ay, ix, iy]
  exact ⟨hill_monotoneOn hK hn.le (by norm_num) hx.le hy.le hxy,
    hill_antitoneOn hK hn.le (by norm_num) hx.le hy.le hxy⟩

#print axioms factors_eq_hill
#print axioms ordered_factors

end CellsProofs.Checks.Hill
