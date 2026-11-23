import CellsProofs.Transport.ConstantField
import Mathlib.Analysis.SpecialFunctions.Log.Basic
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Ring

/-! # Passive proton leak

The engine reads the free proton concentrations in mM. Positive flux is inward.
With voltage measured inside minus outside, `x = F V / (R T)` and the inward
electrochemical drive is in units of `R T`.
-/

namespace CellsProofs.Transport.ProtonLeak

noncomputable section

def inward (factor : NormalizedFactor) (scale hIn hOut x : ℝ) : ℝ :=
  constantFieldFlux factor scale 1 hOut hIn (-x)

def drive (hIn hOut x : ℝ) : ℝ := Real.log hOut - Real.log hIn - x

private theorem inward_formula (factor : NormalizedFactor) (scale hIn hOut x : ℝ) :
    inward factor scale hIn hOut x =
      scale * (hOut * factor.eval x - hIn * factor.eval (-x)) := by
  simp [inward, constantFieldFlux]

theorem analytic_pos (x : ℝ) : 0 < analyticFactor.eval x := by
  rcases lt_trichotomy x 0 with hx | rfl | hx
  · simpa [analyticFactor, hx.ne] using
      div_pos_of_neg_of_neg hx (sub_neg.mpr (Real.exp_lt_one_iff.mpr hx))
  · simp [NormalizedFactor.eval_zero]
  · simpa [analyticFactor, hx.ne'] using
      div_pos hx (sub_pos.mpr (Real.one_lt_exp_iff.mpr hx))

theorem analytic_reverse (x : ℝ) :
    analyticFactor.eval (-x) = Real.exp x * analyticFactor.eval x := by
  by_cases hx : x = 0
  · simp [hx]
  have he : Real.exp x ≠ 1 := fun h => hx ((Real.exp_eq_one_iff x).mp h)
  have hn : Real.exp (-x) - 1 ≠ 0 :=
    sub_ne_zero.mpr (fun h => (neg_ne_zero.mpr hx) ((Real.exp_eq_one_iff (-x)).mp h))
  rw [Real.exp_neg] at hn
  simp only [analyticFactor, if_neg hx, if_neg (neg_ne_zero.mpr hx), Real.exp_neg]
  rw [div_eq_iff hn]
  field_simp [sub_ne_zero.mpr he, (Real.exp_pos x).ne']
  ring

private theorem regular_factor {x : ℝ} (regular : 1 / 10000 ≤ |x|) :
    seriesFactor.eval x = analyticFactor.eval x := by
  have hx : x ≠ 0 := by
    rintro rfl
    norm_num at regular
  simp only [seriesFactor, analyticFactor, if_neg (not_lt.mpr regular), if_neg hx]

theorem series_pos (x : ℝ) : 0 < seriesFactor.eval x := by
  by_cases small : |x| < 1 / 10000
  · simp only [seriesFactor, if_pos small]
    obtain ⟨lo, hi⟩ := abs_lt.mp (lt_trans small (by norm_num : (1 : ℝ) / 10000 < 1))
    have sq : x ^ 2 < 1 := by nlinarith [mul_pos (sub_pos.mpr hi) (by linarith : 0 < 1 + x)]
    have fourth : x ^ 4 ≤ 1 := by
      nlinarith [mul_nonneg (sub_nonneg.mpr sq.le) (by nlinarith [sq_nonneg x] : 0 ≤ 1 + x ^ 2)]
    nlinarith [sq_nonneg x]
  · rw [regular_factor (le_of_not_gt small)]
    exact analytic_pos x

/-- Across both evaluator branches, this factorization gives the sign and the
exact outside concentration at reversal for an open route. -/
theorem series_flux (scale hIn hOut x : ℝ) :
    inward seriesFactor scale hIn hOut x = scale * seriesFactor.eval x *
      (hOut - hIn * (seriesFactor.eval (-x) / seriesFactor.eval x)) := by
  rw [inward_formula]
  field_simp [(series_pos x).ne']
  ring

theorem series_inward_iff {scale : ℝ} (hs : 0 < scale) (hIn hOut x : ℝ) :
    0 < inward seriesFactor scale hIn hOut x ↔
      hIn * (seriesFactor.eval (-x) / seriesFactor.eval x) < hOut := by
  rw [series_flux, mul_pos_iff_of_pos_left (mul_pos hs (series_pos x)), sub_pos]

/-- At zero and on the regular branch the selected real-arithmetic evaluator
gives the analytic flux, including the two switching points. -/
theorem series_eq_analytic {x : ℝ} (region : x = 0 ∨ 1 / 10000 ≤ |x|) (scale hIn hOut : ℝ) :
    inward seriesFactor scale hIn hOut x = inward analyticFactor scale hIn hOut x := by
  rcases region with rfl | regular
  · simp [inward_formula, NormalizedFactor.eval_zero]
  · have other : 1 / 10000 ≤ |-x| := by rwa [abs_neg]
    simp only [inward_formula, regular_factor regular, regular_factor other]

private theorem analytic_flux (scale hIn hOut x : ℝ) :
    inward analyticFactor scale hIn hOut x =
      scale * analyticFactor.eval x * (hOut - hIn * Real.exp x) := by
  rw [inward_formula, analytic_reverse]
  ring

private theorem drive_log {hIn : ℝ} (hi : 0 < hIn) (hOut x : ℝ) :
    drive hIn hOut x = Real.log hOut - Real.log (hIn * Real.exp x) := by
  rw [drive, Real.log_mul hi.ne' (Real.exp_pos x).ne', Real.log_exp]
  ring

theorem analytic_inward_iff {scale hIn hOut : ℝ} (hs : 0 < scale) (hi : 0 < hIn)
    (ho : 0 < hOut) (x : ℝ) :
    0 < inward analyticFactor scale hIn hOut x ↔ 0 < drive hIn hOut x := by
  rw [analytic_flux, mul_pos_iff_of_pos_left (mul_pos hs (analytic_pos x)), sub_pos,
    drive_log hi, sub_pos, Real.log_lt_log_iff (mul_pos hi (Real.exp_pos x)) ho]

theorem analytic_equilibrium_iff {scale : ℝ} (hs : 0 < scale) (hIn hOut x : ℝ) :
    inward analyticFactor scale hIn hOut x = 0 ↔ hOut = hIn * Real.exp x := by
  rw [analytic_flux, mul_eq_zero, or_iff_right (mul_pos hs (analytic_pos x)).ne', sub_eq_zero]

/-- The inside-minus-outside voltage at reversal, in volts when RT is J/mol and F is C/mol. -/
theorem reversal_voltage_iff {scale hIn hOut rt faraday : ℝ} (hs : 0 < scale) (hi : 0 < hIn)
    (ho : 0 < hOut) (hrt : 0 < rt) (hf : 0 < faraday) (voltage : ℝ) :
    inward analyticFactor scale hIn hOut (faraday * voltage / rt) = 0 ↔
      voltage = rt / faraday * (Real.log hOut - Real.log hIn) := by
  rw [analytic_equilibrium_iff hs,
    ← Real.log_injOn_pos.eq_iff ho (mul_pos hi (Real.exp_pos _)),
    Real.log_mul hi.ne' (Real.exp_pos _).ne', Real.log_exp]
  constructor <;> intro h <;> field_simp [hrt.ne', hf.ne'] at h ⊢ <;> linarith

/-- Instantaneous heat in pJ/s for an available or blocked passive route. -/
theorem analytic_heat_nonneg {scale rt hIn hOut : ℝ} (hs : 0 ≤ scale) (hrt : 0 < rt)
    (hi : 0 < hIn) (ho : 0 < hOut) (x : ℝ) :
    0 ≤ (1 / 1000 : ℝ) * rt * inward analyticFactor scale hIn hOut x * drive hIn hOut x := by
  rw [analytic_flux, drive_log hi]
  have hbase := mul_nonneg hs (analytic_pos x).le
  have hcoeff : 0 ≤ (1 / 1000 : ℝ) * rt := by positivity
  have href := mul_pos hi (Real.exp_pos x)
  rcases le_total (hIn * Real.exp x) hOut with h | h
  · exact mul_nonneg (mul_nonneg hcoeff (mul_nonneg hbase (sub_nonneg.mpr h)))
      (sub_nonneg.mpr (Real.log_le_log href h))
  · exact mul_nonneg_of_nonpos_of_nonpos
      (mul_nonpos_of_nonneg_of_nonpos hcoeff (mul_nonpos_of_nonneg_of_nonpos hbase (sub_nonpos.mpr h)))
      (sub_nonpos.mpr (Real.log_le_log ho h))

/-- Changing only the outside free proton concentration has an exact linear effect
on inward flux at fixed voltage, inside concentration and route opening. -/
theorem outside_change (factor : NormalizedFactor) (scale hIn h₁ h₂ x : ℝ) :
    inward factor scale hIn h₂ x - inward factor scale hIn h₁ x =
      scale * factor.eval x * (h₂ - h₁) := by
  simp only [inward_formula]
  ring

/-- For the engine's Bernoulli factor an open patch strictly distinguishes two outside readings. -/
theorem strictMono_outside {scale : ℝ} (hs : 0 < scale) (hIn x : ℝ) :
    StrictMono (fun hOut => inward seriesFactor scale hIn hOut x) := by
  intro a b h
  apply sub_pos.mp
  rw [outside_change]
  exact mul_pos (mul_pos hs (series_pos x)) (sub_pos.mpr h)

end

end CellsProofs.Transport.ProtonLeak
