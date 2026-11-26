import Mathlib.Analysis.SpecialFunctions.Log.Basic
import Mathlib.Algebra.BigOperators.Group.Finset.Basic
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Ring

/-! # Extracellular face transport

The `cells.route.logmean_electrodiffusion@1` surface kernel uses two positive concentrations,
sender minus receiver voltage, and a nonnegative face coefficient. All formulas
here use real arithmetic. The mean uses the engine's two thresholds and its
fourth-degree polynomial. The force uses the difference of the concentration logs.
-/

namespace CellsProofs.Transport.Face

noncomputable section

private def ratio (a b : ℝ) := (a - b) / (a + b)

/-- For |r| < 1/2 the kernel evaluates 2 atanh(r), whose real logarithmic form
is log((1 + r)/(1 - r)). Outside that branch it subtracts the two logs. -/
def stableLogRatio (a b : ℝ) : ℝ :=
  let r := ratio a b
  if |r| < 1 / 2 then Real.log ((1 + r) / (1 - r)) else Real.log a - Real.log b

theorem stableLogRatio_eq {a b : ℝ} (ha : 0 < a) (hb : 0 < b) :
    stableLogRatio a b = Real.log a - Real.log b := by
  simp only [stableLogRatio]
  split
  · have hsum : a + b ≠ 0 := (add_pos ha hb).ne'
    have hden : 1 - ratio a b = 2 * b / (a + b) := by
      unfold ratio
      field_simp
      ring
    rw [hden]
    have hquot : (1 + ratio a b) / (2 * b / (a + b)) = a / b := by
      unfold ratio
      field_simp
      ring
    rw [hquot, Real.log_div ha.ne' hb.ne']
  · rfl

private def series (r : ℝ) := 1 - r ^ 2 / 3 - 4 * (r ^ 2) ^ 2 / 45

def mean (a b : ℝ) : ℝ :=
  let r := ratio a b
  if |r| < 1 / 10000 then (a + b) / 2 * series r else (a - b) / stableLogRatio a b

private theorem ratio_swap (a b : ℝ) : ratio b a = -(ratio a b) := by
  unfold ratio
  rw [add_comm b a, ← neg_div, neg_sub]

theorem mean_swap {a b : ℝ} (ha : 0 < a) (hb : 0 < b) : mean b a = mean a b := by
  simp only [mean, ratio_swap a b, abs_neg, series, neg_sq, add_comm b a,
    stableLogRatio_eq ha hb, stableLogRatio_eq hb ha]
  split
  · rfl
  · rw [← neg_sub a b, ← neg_sub (Real.log a) (Real.log b), neg_div_neg_eq]

theorem mean_pos {a b : ℝ} (ha : 0 < a) (hb : 0 < b) : 0 < mean a b := by
  simp only [mean]
  split
  next h =>
    have hsq : (ratio a b) ^ 2 < 1 :=
      (sq_lt_one_iff_abs_lt_one _).2 (lt_trans h (by norm_num))
    have hfourth : ((ratio a b) ^ 2) ^ 2 < 1 :=
      (sq_lt_one_iff₀ (sq_nonneg _)).2 hsq
    apply mul_pos (half_pos (add_pos ha hb))
    unfold series
    linarith
  next h =>
    rw [stableLogRatio_eq ha hb]
    rcases lt_trichotomy a b with hab | rfl | hba
    · exact div_pos_of_neg_of_neg (sub_neg.mpr hab) (sub_neg.mpr (Real.log_lt_log ha hab))
    · norm_num [ratio] at h
    · exact div_pos (sub_pos.mpr hba) (sub_pos.mpr (Real.log_lt_log hb hba))

/-- rt is RT, charge is zF, and voltage is the sender minus receiver potential. -/
def drop (rt charge a b voltage : ℝ) := rt * (Real.log a - Real.log b) + charge * voltage

/-- Flux in fmol/s, with 10⁻¹⁵ mol per fmol. -/
def flux (factor rt charge a b voltage : ℝ) : ℝ :=
  (factor * mean a b / (rt * (1 / 10 ^ 15))) * drop rt charge a b voltage

theorem flux_reverse {a b : ℝ} (ha : 0 < a) (hb : 0 < b) (factor rt charge voltage : ℝ) :
    flux factor rt charge b a (-voltage) = -flux factor rt charge a b voltage := by
  unfold flux drop
  rw [mean_swap ha hb]
  ring

theorem flux_at_equilibrium {factor rt charge a b voltage : ℝ}
    (h : drop rt charge a b voltage = 0) : flux factor rt charge a b voltage = 0 := by
  simp [flux, h]

theorem flux_pos_iff {factor rt charge a b voltage : ℝ}
    (hf : 0 < factor) (ht : 0 < rt) (ha : 0 < a) (hb : 0 < b) :
    0 < flux factor rt charge a b voltage ↔ 0 < drop rt charge a b voltage := by
  exact mul_pos_iff_of_pos_left (div_pos (mul_pos hf (mean_pos ha hb)) (mul_pos ht (by norm_num)))

theorem dissipation_nonneg {factor rt charge a b voltage : ℝ}
    (hf : 0 ≤ factor) (ht : 0 < rt) (ha : 0 < a) (hb : 0 < b) :
    0 ≤ flux factor rt charge a b voltage * drop rt charge a b voltage := by
  unfold flux
  rw [mul_assoc, ← sq]
  exact mul_nonneg (div_nonneg (mul_nonneg hf (mean_pos ha hb).le)
    (mul_pos ht (by norm_num)).le) (sq_nonneg _)

/-- Convert flux from fmol/s to mol/s and power from J/s to pJ/s. -/
theorem power_in_pJ_per_s (fluxFmolPerS dropJPerMol : ℝ) :
    (fluxFmolPerS / 10 ^ 15 * dropJPerMol) * 10 ^ 12 =
      (1 / 1000 : ℝ) * (fluxFmolPerS * dropJPerMol) := by ring

/-- The reported face power in pJ/s sums the species contributions and converts units. -/
theorem face_power_nonneg {Ion : Type*} (ions : Finset Ion) (factor charge a b : Ion → ℝ)
    {rt voltage : ℝ} (ht : 0 < rt) (hf : ∀ i ∈ ions, 0 ≤ factor i)
    (ha : ∀ i ∈ ions, 0 < a i) (hb : ∀ i ∈ ions, 0 < b i) :
    0 ≤ (1 / 1000 : ℝ) * ∑ i ∈ ions,
      flux (factor i) rt (charge i) (a i) (b i) voltage * drop rt (charge i) (a i) (b i) voltage :=
  mul_nonneg (by norm_num) (Finset.sum_nonneg fun i hi =>
    dissipation_nonneg (hf i hi) ht (ha i hi) (hb i hi))

end

end CellsProofs.Transport.Face
