import Mathlib.Analysis.SpecialFunctions.ExpDeriv
import Mathlib.Analysis.SpecialFunctions.Log.Basic
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Positivity
import Mathlib.Tactic.Ring

/-! # Production and first-order clearance in one well-mixed pool

Over one constant-rate interval, `P` is the total production in amount per
time and `k` is the summed clearance rate per time. The engine accumulates
gross production `P * h` and gross clearance separately for a duration `h`.
-/

namespace CellsProofs.Chemistry.SpeciesTurnover

noncomputable section

def survival (k h : ℝ) : ℝ := Real.exp (-(k * h))

/-- Effective time for which newly produced material remains in the pool. -/
def exposure (k h : ℝ) : ℝ := if k = 0 then h else (1 - survival k h) / k

def amount (n P k h : ℝ) : ℝ := n * survival k h + P * exposure k h

def cleared (n P k h : ℝ) : ℝ := n * (1 - survival k h) + P * (h - exposure k h)

theorem initial_amount (n P k : ℝ) : amount n P k 0 = n := by
  simp [amount, survival, exposure]

theorem zero_clearance (n P h : ℝ) :
    amount n P 0 h = n + P * h ∧ cleared n P 0 h = 0 := by
  simp [amount, cleared, exposure, survival]

theorem exposure_bounds {k h : ℝ} (hk : 0 ≤ k) (hh : 0 ≤ h) :
    0 ≤ exposure k h ∧ exposure k h ≤ h := by
  by_cases h0 : k = 0
  · simp [exposure, h0, hh]
  have kp := lt_of_le_of_ne hk (Ne.symm h0)
  have es : survival k h ≤ 1 := Real.exp_le_one_iff.mpr (neg_nonpos.mpr (mul_nonneg hk hh))
  simp only [exposure, if_neg h0]
  refine ⟨div_nonneg (sub_nonneg.mpr es) hk, (div_le_iff₀ kp).mpr ?_⟩
  unfold survival
  linarith [Real.add_one_le_exp (-(k * h)), mul_comm k h]

theorem amount_pos {n P k h : ℝ} (hn : 0 < n) (hp : 0 ≤ P) (hk : 0 ≤ k) (hh : 0 ≤ h) :
    0 < amount n P k h :=
  add_pos_of_pos_of_nonneg (mul_pos hn (Real.exp_pos _))
    (mul_nonneg hp (exposure_bounds hk hh).1)

theorem gross_nonneg {n P k h : ℝ} (hn : 0 ≤ n) (hp : 0 ≤ P) (hk : 0 ≤ k) (hh : 0 ≤ h) :
    0 ≤ P * h ∧ 0 ≤ cleared n P k h := by
  have es : survival k h ≤ 1 := Real.exp_le_one_iff.mpr (neg_nonpos.mpr (mul_nonneg hk hh))
  exact ⟨mul_nonneg hp hh, add_nonneg (mul_nonneg hn (sub_nonneg.mpr es))
    (mul_nonneg hp (sub_nonneg.mpr (exposure_bounds hk hh).2))⟩

theorem gross_balance (n P k h : ℝ) :
    amount n P k h = n + (P * h - cleared n P k h) := by
  unfold amount cleared
  ring

/-- With a positive clearance rate the net move can be evaluated directly. -/
theorem net_change (n P h : ℝ) {k : ℝ} (hk : k ≠ 0) :
    amount n P k h - n = (P / k - n) * (1 - survival k h) := by
  simp only [amount, exposure, if_neg hk, div_eq_mul_inv]
  ring

theorem equilibrium_offset (n P h : ℝ) {k : ℝ} (hk : k ≠ 0) :
    amount n P k h - P / k = (n - P / k) * survival k h := by
  simp only [amount, exposure, if_neg hk, div_eq_mul_inv]
  ring

theorem amount_derivative (n P k t : ℝ) :
    HasDerivAt (amount n P k) (P - k * amount n P k t) t := by
  by_cases hk : k = 0
  · subst k
    have repr : amount n P 0 = fun h => n + P * h := funext (fun h => (zero_clearance n P h).1)
    rw [repr]
    simpa using ((hasDerivAt_id t).const_mul P).const_add n
  have repr : amount n P k = fun h => P / k + (n - P / k) * Real.exp (-(k * h)) := by
    funext h
    change amount n P k h = P / k + (n - P / k) * survival k h
    linarith only [equilibrium_offset n P h hk]
  rw [repr]
  have hd := (((hasDerivAt_id t).const_mul k).neg.exp).const_mul (n - P / k)
  convert (hasDerivAt_const t (P / k)).add hd using 1
  field_simp
  ring

theorem steady_turnover (n k h : ℝ) :
    amount n (k * n) k h = n ∧ cleared n (k * n) k h = (k * n) * h := by
  by_cases hk : k = 0
  · simp [hk, amount, cleared, exposure, survival]
  have eq := equilibrium_offset n (k * n) h hk
  simp only [mul_div_cancel_left₀ n hk, sub_self, zero_mul, sub_eq_zero] at eq
  exact ⟨eq, by linarith only [eq, gross_balance n (k * n) k h]⟩

/-- Subdividing a constant schedule preserves both the amount and its cumulative clearance. -/
theorem compose_stages (n P k a b : ℝ) :
    amount (amount n P k a) P k b = amount n P k (a + b) ∧
    cleared n P k a + cleared (amount n P k a) P k b = cleared n P k (a + b) := by
  have es : survival k (a + b) = survival k a * survival k b := by
    simp [survival, mul_add, Real.exp_add, mul_comm]
  have ea : amount (amount n P k a) P k b = amount n P k (a + b) := by
    by_cases hk : k = 0
    · simp [hk, amount, exposure, survival]; ring
    simp only [amount, exposure, if_neg hk, es, div_eq_mul_inv]
    ring
  exact ⟨ea, by linarith only [ea, gross_balance n P k a,
    gross_balance (amount n P k a) P k b, gross_balance n P k (a + b), mul_add P a b]⟩

/-- Two otherwise identical pools retain this fraction of their initial difference. -/
theorem cohort_survival (n m P k h : ℝ) :
    amount n P k h - amount m P k h = (n - m) * survival k h := by
  unfold amount
  ring

theorem half_life (n : ℝ) {k : ℝ} (hk : 0 < k) :
    amount n 0 k (Real.log 2 / k) = n / 2 := by
  have time : k * (Real.log 2 / k) = Real.log 2 := by field_simp
  simp only [amount, zero_mul, add_zero, survival, time]
  rw [Real.exp_neg, Real.exp_log (by norm_num : (0 : ℝ) < 2), div_eq_mul_inv]

end

end CellsProofs.Chemistry.SpeciesTurnover
