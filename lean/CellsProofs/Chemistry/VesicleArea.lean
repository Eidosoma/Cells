import Mathlib.Analysis.Convex.Jensen
import Mathlib.Analysis.Convex.SpecificFunctions.Basic
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Ring

/-! # Vesicle survival at a common integrated hazard per unit area (FR-31) -/

namespace CellsProofs.Chemistry.VesicleArea

open scoped BigOperators

noncomputable section

/-- For constant area and a common per-area hazard, exposure is its integral over time. -/
def survival (exposure area : ℝ) : ℝ := Real.exp (area * (-exposure))

/-- Survival evaluated at the mean area is a lower bound for population survival. -/
theorem at_mean_le {ι : Type*} (s : Finset ι) (w area : ι → ℝ) (q : ℝ)
    (hw : ∀ i ∈ s, 0 ≤ w i) (hn : ∑ i ∈ s, w i = 1) :
    survival q (∑ i ∈ s, w i * area i) ≤ ∑ i ∈ s, w i * survival q (area i) := by
  have h := convexOn_exp.map_sum_le (p := fun i => area i * (-q)) hw hn
    (fun i _ => Set.mem_univ _)
  simpa only [survival, smul_eq_mul, Finset.sum_mul, mul_assoc] using h

/-- With positive exposure, different areas in a population of positive weights give a strict gap. -/
theorem at_mean_lt {ι : Type*} (s : Finset ι) (w area : ι → ℝ) {q : ℝ} (hq : 0 < q)
    (hw : ∀ i ∈ s, 0 < w i) (hn : ∑ i ∈ s, w i = 1)
    (diff : ∃ i ∈ s, ∃ k ∈ s, area i ≠ area k) :
    survival q (∑ i ∈ s, w i * area i) < ∑ i ∈ s, w i * survival q (area i) := by
  obtain ⟨i, hi, k, hk, hik⟩ := diff
  have different : area i * (-q) ≠ area k * (-q) :=
    fun h => hik (mul_right_cancel₀ (neg_ne_zero.mpr hq.ne') h)
  have h := strictConvexOn_exp.map_sum_lt (p := fun j => area j * (-q)) hw hn
    (fun j _ => Set.mem_univ _) ⟨i, hi, k, hk, different⟩
  simpa only [survival, smul_eq_mul, Finset.sum_mul, mul_assoc] using h

/-- Linear interpolation of survival at the two endpoints of an area range. -/
def chord (q lo hi a : ℝ) : ℝ :=
  survival q lo + (a - lo) * ((survival q hi - survival q lo) / (hi - lo))

/-- A population placed at the two endpoints attains the upper bound at any allowed mean. -/
theorem endpoint_mixture {lo hi a : ℝ} (q : ℝ) (gap : lo < hi) (left : lo ≤ a) (right : a ≤ hi) :
    let l := (hi - a) / (hi - lo)
    let h := (a - lo) / (hi - lo)
    0 ≤ l ∧ 0 ≤ h ∧ l + h = 1 ∧ l * lo + h * hi = a ∧
      l * survival q lo + h * survival q hi = chord q lo hi a := by
  have d : 0 < hi - lo := sub_pos.mpr gap
  refine ⟨div_nonneg (sub_nonneg.mpr right) d.le, div_nonneg (sub_nonneg.mpr left) d.le,
    ?_, ?_, ?_⟩
  · field_simp [d.ne']
  · field_simp [d.ne']; ring
  · unfold chord; field_simp [d.ne']; ring

theorem le_chord {lo hi a : ℝ} (q : ℝ) (gap : lo < hi) (left : lo ≤ a) (right : a ≤ hi) :
    survival q a ≤ chord q lo hi a := by
  obtain ⟨hl, hh, weights, mean, bound⟩ := endpoint_mixture q gap left right
  have atPoint : (hi - a) / (hi - lo) * (lo * -q) + (a - lo) / (hi - lo) * (hi * -q) =
      a * -q := by rw [← mul_assoc, ← mul_assoc, ← add_mul, mean]
  have h := convexOn_exp.2 (Set.mem_univ (lo * -q)) (Set.mem_univ (hi * -q)) hl hh weights
  simp only [smul_eq_mul, atPoint] at h
  calc
    survival q a ≤ (hi - a) / (hi - lo) * survival q lo +
        (a - lo) / (hi - lo) * survival q hi := h
    _ = chord q lo hi a := bound

/-- Given a hard area range and its mean for the same weighted cohort, the chord at the mean
bounds its survival from above. The weights refer to the population at the start of the hold. -/
theorem population_le_chord {ι : Type*} (s : Finset ι) (w area : ι → ℝ) (q : ℝ)
    {lo hi : ℝ} (gap : lo < hi) (hw : ∀ i ∈ s, 0 ≤ w i) (hn : ∑ i ∈ s, w i = 1)
    (range : ∀ i ∈ s, lo ≤ area i ∧ area i ≤ hi) :
    ∑ i ∈ s, w i * survival q (area i) ≤ chord q lo hi (∑ i ∈ s, w i * area i) := by
  calc
    _ ≤ ∑ i ∈ s, w i * chord q lo hi (area i) := Finset.sum_le_sum fun i hi' =>
      mul_le_mul_of_nonneg_left (le_chord q gap (range i hi').1 (range i hi').2) (hw i hi')
    _ = _ := by
      simp only [chord, sub_mul, mul_add, mul_sub, ← mul_assoc, Finset.sum_add_distrib,
        Finset.sum_sub_distrib, ← Finset.sum_mul, hn, one_mul]

/-- A zero-width range specifies a single area. -/
theorem one_area {ι : Type*} (s : Finset ι) (w : ι → ℝ) (q area : ℝ)
    (hn : ∑ i ∈ s, w i = 1) : ∑ i ∈ s, w i * survival q area = survival q area := by
  rw [← Finset.sum_mul, hn, one_mul]

end

end CellsProofs.Chemistry.VesicleArea
