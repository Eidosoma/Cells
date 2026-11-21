import Mathlib.Analysis.SpecialFunctions.Log.Basic
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Ring

/-! # Voltage-dependent gap-junction conductance

The shift s is |V_sender − V_receiver| minus the threshold, in volts. The two
rates are in inverse seconds. m is the residual conductance fraction.
-/

namespace CellsProofs.Transport.JunctionGate

noncomputable section

def opening (s : ℝ) : ℝ := 1.3 * Real.exp (-77 * s)

def closing (s : ℝ) : ℝ := 20 / (1 + Real.exp (-(Real.log 0.065 + 140 * s)))

def speed (s : ℝ) : ℝ := opening s + closing s

def target (s m : ℝ) : ℝ := (opening s + closing s * m) / speed s

/-- The engine's constant-voltage update for an intrinsic conductance g. -/
def advance (g s m t : ℝ) : ℝ := g + (target s m - g) * (1 - Real.exp (-(speed s) * t))

private theorem opening_pos (s : ℝ) : 0 < opening s := by unfold opening; positivity
private theorem closing_pos (s : ℝ) : 0 < closing s := by unfold closing; positivity
private theorem speed_pos (s : ℝ) : 0 < speed s := add_pos (opening_pos s) (closing_pos s)

theorem target_bounds (s : ℝ) {m : ℝ} (hm : m ≤ 1) : target s m ∈ Set.Icc m 1 := by
  constructor
  · apply (le_div_iff₀ (speed_pos s)).mpr
    unfold speed
    nlinarith only [mul_nonneg (opening_pos s).le (sub_nonneg.mpr hm)]
  · apply (div_le_iff₀ (speed_pos s)).mpr
    unfold speed
    nlinarith only [mul_nonneg (closing_pos s).le (sub_nonneg.mpr hm)]

/-- At fixed threshold, a larger voltage magnitude lowers the equilibrium conductance. -/
theorem target_decreases {s u m : ℝ} (hs : s < u) (hm : m < 1) : target u m < target s m := by
  have ha : opening u < opening s :=
    mul_lt_mul_of_pos_left (Real.exp_lt_exp.mpr (by linarith)) (by norm_num)
  have he : Real.exp (-(Real.log 0.065 + 140 * u)) < Real.exp (-(Real.log 0.065 + 140 * s)) :=
    Real.exp_lt_exp.mpr (by linarith)
  have hb : closing s < closing u := by
    unfold closing
    apply (div_lt_div_iff₀ (by positivity) (by positivity)).mpr
    linarith only [he]
  have hab : opening u * closing s < opening s * closing u :=
    (mul_lt_mul_of_pos_right ha (closing_pos s)).trans (mul_lt_mul_of_pos_left hb (opening_pos s))
  apply (div_lt_div_iff₀ (speed_pos u) (speed_pos s)).mpr
  unfold speed
  nlinarith only [mul_pos (sub_pos.mpr hm) (sub_pos.mpr hab)]

theorem rhs_eq_relaxation (g s m : ℝ) :
    opening s * (1 - g) - closing s * (g - m) = speed s * (target s m - g) := by
  have h := (div_mul_cancel₀ (opening s + closing s * m) (speed_pos s).ne')
  change target s m * speed s = _ at h
  unfold speed at h ⊢
  linarith only [h]

theorem clamp_residual (g s m t : ℝ) :
    advance g s m t - target s m = (g - target s m) * Real.exp (-(speed s) * t) := by
  unfold advance
  ring

/-- Three equally spaced samples of the deviation from the steady conductance. -/
theorem single_decay_samples (g s m t : ℝ) :
    (g - target s m) * (advance g s m (t + t) - target s m) =
      (advance g s m t - target s m) ^ 2 := by
  rw [clamp_residual, clamp_residual, mul_add, Real.exp_add]
  ring

/-- For two decays with positive amplitudes and different one-interval factors,
the same three-sample equality is strictly violated. -/
theorem two_decay_samples {a b r q : ℝ} (ha : 0 < a) (hb : 0 < b) (hne : r ≠ q) :
    (a * r + b * q) ^ 2 < (a + b) * (a * r ^ 2 + b * q ^ 2) := by
  have h := mul_pos (mul_pos ha hb) (sq_pos_of_ne_zero (sub_ne_zero.mpr hne))
  nlinarith only [h]

theorem clamp_bounds {g m t : ℝ} (s : ℝ) (hg : g ∈ Set.Icc m 1) (ht : 0 ≤ t) :
    advance g s m t ∈ Set.Icc m 1 := by
  have hq := target_bounds s (hg.1.trans hg.2)
  let w := Real.exp (-(speed s) * t)
  have hw : 0 ≤ w := (Real.exp_pos _).le
  have hw' : 0 ≤ 1 - w := sub_nonneg.mpr (Real.exp_le_one_iff.mpr
    (mul_nonpos_of_nonpos_of_nonneg (neg_nonpos.mpr (speed_pos s).le) ht))
  change m ≤ g + (target s m - g) * (1 - w) ∧ g + (target s m - g) * (1 - w) ≤ 1
  constructor
  · nlinarith only [mul_nonneg (sub_nonneg.mpr hg.1) hw, mul_nonneg (sub_nonneg.mpr hq.1) hw']
  · nlinarith only [mul_nonneg (sub_nonneg.mpr hg.2) hw, mul_nonneg (sub_nonneg.mpr hq.2) hw']

theorem clamp_add (g s m t u : ℝ) :
    advance (advance g s m t) s m u = advance g s m (t + u) := by
  simp only [advance, mul_add, Real.exp_add]
  ring

theorem clamp_polarity (g v threshold m t : ℝ) :
    advance g (|-v| - threshold) m t = advance g (|v| - threshold) m t := by rw [abs_neg]

/-- A common prediction at opposite voltages misses at least one observed value by
half their separation. This applies to the clamped gate by `clamp_polarity`. -/
theorem polarity_error_bound (negative positive predicted : ℝ) :
    |negative - positive| / 2 ≤ max |negative - predicted| |predicted - positive| := by
  have h := abs_sub_le negative predicted positive
  have hn := le_max_left |negative - predicted| |predicted - positive|
  have hp := le_max_right |negative - predicted| |predicted - positive|
  linarith

/-- FR-30 proposes multiplying two independent gate factors at fixed voltage.
Each delta is the initial factor minus its steady value. -/
theorem series_clamp_expansion (fast slow deltaFast deltaSlow kFast kSlow t : ℝ) :
    (fast + deltaFast * Real.exp (-kFast * t)) * (slow + deltaSlow * Real.exp (-kSlow * t)) =
      fast * slow + deltaFast * slow * Real.exp (-kFast * t) +
        fast * deltaSlow * Real.exp (-kSlow * t) +
        deltaFast * deltaSlow * Real.exp (-(kFast + kSlow) * t) := by
  rw [show -(kFast + kSlow) * t = -kFast * t + -kSlow * t by ring, Real.exp_add]
  ring

/-- The plateau times the mixed amplitude equals the product of the fast and slow
amplitudes, even after a common normalization of the conductance trace. -/
theorem series_amplitudes (fast slow deltaFast deltaSlow gain : ℝ) :
    (gain * (fast * slow)) * (gain * (deltaFast * deltaSlow)) =
      (gain * (deltaFast * slow)) * (gain * (fast * deltaSlow)) := by ring

end

end CellsProofs.Transport.JunctionGate
