import Mathlib.Algebra.BigOperators.Group.Finset.Basic
import Mathlib.Algebra.Order.BigOperators.Ring.Finset
import Mathlib.Algebra.Order.Field.Basic
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Ring

/-! # Release-time windows and reuse of a neutral label (FR-42, FR-38) -/

namespace CellsProofs.Chemistry.ArrivalWindow

open scoped BigOperators

/-- A release at the start of a step is marked in precisely the half-open windows containing it. -/
def marked (start stop tick : ℕ) (released : ℝ) : ℝ :=
  if start ≤ tick ∧ tick < stop then released else 0

theorem at_start {a b : ℕ} (h : a < b) (x : ℝ) : marked a b a x = x := by simp [marked, h]
theorem at_end (a b : ℕ) (x : ℝ) : marked a b b x = 0 := by simp [marked]

/-- Adjacent windows neither omit nor double-count the release at their shared endpoint. -/
theorem adjacent {a b c : ℕ} (hab : a ≤ b) (hbc : b ≤ c) (t : ℕ) (x : ℝ) :
    marked a c t x = marked a b t x + marked b c t x := by
  unfold marked
  split_ifs <;> first | omega | simp

/-- Amount at boundary n, before arrivals at n. Arrivals at the previous boundary and
older survivors experience the same survival factor over the following interval. -/
noncomputable def follow (keep arrivals : ℕ → ℝ) (initial : ℝ) : ℕ → ℝ
  | 0 => initial
  | n + 1 => (follow keep arrivals initial n + arrivals n) * keep n

/-- At common survival factors, reusing a label adds the separately tracked surviving amounts. -/
theorem add_histories (keep first second : ℕ → ℝ) (x y : ℝ) (n : ℕ) :
    follow keep (fun i => first i + second i) (x + y) n =
      follow keep first x n + follow keep second y n := by
  induction n with
  | zero => rfl
  | succ n ih => simp only [follow, ih]; ring

theorem reuse (keep first second : ℕ → ℝ) (old : ℝ) (n : ℕ) :
    follow keep (fun i => first i + second i) old n =
      follow keep first old n + follow keep second 0 n := by
  simpa using add_histories keep first second old 0 n

theorem chase_only (keep : ℕ → ℝ) (closed : ℝ) (n : ℕ) :
    follow keep (fun _ => 0) closed n = closed * ∏ i ∈ Finset.range n, keep i := by
  induction n with
  | zero => simp [follow]
  | succ n ih => simp [follow, ih, Finset.prod_range_succ, mul_assoc]

/-- The denominator is the original cohort alive at close. An empty denominator has no fraction. -/
noncomputable def chaseFraction (closed later : ℝ) : Option ℝ :=
  if closed = 0 then none else some (later / closed)

theorem chase_fraction (keep : ℕ → ℝ) {closed : ℝ} (occupied : closed ≠ 0) (n : ℕ) :
    chaseFraction closed (follow keep (fun _ => 0) closed n) =
      some (∏ i ∈ Finset.range n, keep i) := by
  simp [chaseFraction, occupied, chase_only, mul_div_cancel_left₀]

theorem empty_fraction (later : ℝ) : chaseFraction 0 later = none := by simp [chaseFraction]

/-- Ten releases at step 1, four at the excluded endpoint 2, and two at step 3 when the
label is used again. One untracked pool may already contain older material. -/
theorem release_example :
    let released : ℕ → ℝ := fun i => if i = 1 then 10 else if i = 2 then 4 else if i = 3 then 2 else 0
    let keep : ℕ → ℝ := fun i => if i = 1 then 4/5 else if i = 2 then 3/4 else if i = 3 then 1/2 else 1
    let first := fun i => marked 1 2 i (released i)
    let again := fun i => marked 3 4 i (released i)
    follow keep first 0 1 = 0 ∧ follow keep first 0 2 = 8 ∧ follow keep first 0 3 = 6 ∧
    chaseFraction (follow keep first 0 2) (follow keep first 0 3) = some (3/4) ∧
    follow keep first 0 4 = 3 ∧ follow keep again 0 4 = 1 ∧
    follow keep (fun i => first i + again i) 0 4 = 4 := by
  norm_num [follow, marked, chaseFraction]

/-- Absolute errors on the two measured counts bound the residual against a fixed survival factor. -/
theorem count_residual_le {atClose atSample trueClose rate closeError sampleError : ℝ}
    (hr : 0 ≤ rate) (hc : |atClose - trueClose| ≤ closeError)
    (hs : |atSample - trueClose * rate| ≤ sampleError) :
    |atSample - rate * atClose| ≤ sampleError + rate * closeError := by
  calc
    |atSample - rate * atClose| =
        |(atSample - trueClose * rate) + rate * (trueClose - atClose)| := by
            congr 1
            ring
    _ ≤ |atSample - trueClose * rate| + |rate * (trueClose - atClose)| := abs_add_le _ _
    _ = |atSample - trueClose * rate| + rate * |atClose - trueClose| := by
          rw [abs_mul, abs_of_nonneg hr, abs_sub_comm trueClose atClose]
    _ ≤ sampleError + rate * closeError := add_le_add hs (mul_le_mul_of_nonneg_left hc hr)

/-- With a positive measured count at close, testing the counts and testing the ratio agree. -/
theorem ratio_residual_iff {atClose atSample rate bound : ℝ} (hc : 0 < atClose) :
    |atSample / atClose - rate| ≤ bound / atClose ↔ |atSample - rate * atClose| ≤ bound := by
  have quotient : (atSample - rate * atClose) / atClose = atSample / atClose - rate := by
    rw [sub_div, mul_div_cancel_right₀ _ hc.ne']
  rw [← quotient, abs_div, abs_of_pos hc, div_le_div_iff_of_pos_right hc]

/-- The window cohort experiences each chase survival factor once. The numerical bound
requires two actual bounds on count errors, in the same amount units as both counts. -/
theorem chase_ratio_error {keep : ℕ → ℝ} (n : ℕ) {trueClose atClose atSample eClose eSample : ℝ}
    (hkeep : ∀ i ∈ Finset.range n, 0 ≤ keep i) (hpos : 0 < atClose)
    (hc : |atClose - trueClose| ≤ eClose)
    (hs : |atSample - follow keep (fun _ => 0) trueClose n| ≤ eSample) :
    |atSample / atClose - ∏ i ∈ Finset.range n, keep i| ≤
      (eSample + (∏ i ∈ Finset.range n, keep i) * eClose) / atClose := by
  rw [chase_only] at hs
  exact (ratio_residual_iff hpos).2 (count_residual_le (Finset.prod_nonneg hkeep) hc hs)

end CellsProofs.Chemistry.ArrivalWindow
