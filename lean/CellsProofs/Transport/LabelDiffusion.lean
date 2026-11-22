import CellsProofs.Transport.LogMeanFace
import CellsProofs.Transport.NeutralPermeation
import Mathlib.Analysis.SpecialFunctions.Log.Deriv

/-! # Diffusion of a passive label family

Each row has its own concentrations and the same transport coefficient. A family
replaces the parent row. Flux is oriented from left to right. For a Cells face,
the near-equality polynomial and the electrical drift need separate treatment.
-/

namespace CellsProofs.Transport.LabelDiffusion

open scoped BigOperators
noncomputable section

def fick (scale left right : ℝ) : ℝ := scale * (left - right)

/-- A common linear diffusion coefficient commutes with summing any finite family. -/
theorem fick_sum {Label : Type*} (rows : Finset Label) (scale : ℝ) (left right : Label → ℝ) :
    ∑ i ∈ rows, fick scale (left i) (right i) =
      fick scale (∑ i ∈ rows, left i) (∑ i ∈ rows, right i) := by
  simp only [fick, ← Finset.mul_sum, Finset.sum_sub_distrib]

/-- An unchanged parent can conceal strictly positive label flux and equal return flux. -/
theorem opposing_labels {scale a b : ℝ} (hs : 0 < scale) (hab : b < a) :
    0 < fick scale a b ∧ fick scale b a = -fick scale a b ∧
      fick scale (a + b) (b + a) = 0 := by
  exact ⟨mul_pos hs (sub_pos.mpr hab), by unfold fick; ring, by unfold fick; ring⟩

/-- Neutral constant-field permeation has the same additive flux at every voltage. -/
theorem neutral_permeation_sum {Label : Type*} (rows : Finset Label) (factor : NormalizedFactor)
    (scale voltage : ℝ) (left right : Label → ℝ) :
    ∑ i ∈ rows, constantFieldFlux factor scale 0 (left i) (right i) voltage =
      constantFieldFlux factor scale 0 (∑ i ∈ rows, left i) (∑ i ∈ rows, right i) voltage := by
  simp only [Neutral.flux_eq_fick]
  exact fick_sum rows scale left right

/-- The actual face uses the logarithmic quotient outside its series threshold. -/
private theorem mean_quotient {a b : ℝ} (ha : 0 < a) (hb : 0 < b)
    (h : 1 / 10000 ≤ |(a - b) / (a + b)|) :
    Face.mean a b = (a - b) / (Real.log a - Real.log b) := by
  simp only [Face.mean]
  split
  next small => exact False.elim ((not_lt_of_ge h) small)
  next => rw [Face.stableLogRatio_eq ha hb]

/-- At equality the polynomial evaluates to one. -/
private theorem mean_same (a : ℝ) : Face.mean a a = a := by
  change (if |(a - a) / (a + a)| < 1 / 10000 then (a + a) / 2 *
    (1 - ((a - a) / (a + a)) ^ 2 / 3 - 4 * (((a - a) / (a + a)) ^ 2) ^ 2 / 45)
    else _) = a
  norm_num

/-- Exact Fick reduction of the implemented neutral face at equality or on its quotient branch. -/
theorem neutral_face_eq_fick {a b rt : ℝ} (ha : 0 < a) (hb : 0 < b) (hrt : 0 < rt)
    (factor voltage : ℝ) (branch : a = b ∨ 1 / 10000 ≤ |(a - b) / (a + b)|) :
    Face.flux factor rt 0 a b voltage = fick (factor / (1 / 10 ^ 15)) a b := by
  rcases branch with rfl | h
  · simp [Face.flux, Face.drop, fick]
  have hlog : Real.log a - Real.log b ≠ 0 := by
    intro eq
    have hab : a = b := by simpa [Real.exp_log ha, Real.exp_log hb] using congrArg Real.exp (sub_eq_zero.mp eq)
    subst b
    norm_num at h
  rw [Face.flux, mean_quotient ha hb h]
  unfold Face.drop fick
  field_simp [hrt.ne', hlog]
  ring

def exactBranch (a b : ℝ) : Prop :=
  0 < a ∧ 0 < b ∧ (a = b ∨ 1 / 10000 ≤ |(a - b) / (a + b)|)

/-- On these branches the production neutral face commutes with replacing a parent by its rows. -/
theorem neutral_face_sum {Label : Type*} (rows : Finset Label) (left right : Label → ℝ)
    {rt : ℝ} (hrt : 0 < rt) (factor voltage : ℝ)
    (onRows : ∀ i ∈ rows, exactBranch (left i) (right i))
    (onParent : exactBranch (∑ i ∈ rows, left i) (∑ i ∈ rows, right i)) :
    ∑ i ∈ rows, Face.flux factor rt 0 (left i) (right i) voltage =
      Face.flux factor rt 0 (∑ i ∈ rows, left i) (∑ i ∈ rows, right i) voltage := by
  have reduce {a b : ℝ} (h : exactBranch a b) :=
    neutral_face_eq_fick h.1 h.2.1 hrt factor voltage h.2.2
  rw [reduce onParent, ← fick_sum]
  exact Finset.sum_congr rfl fun i hi => reduce (onRows i hi)

/-- Equal total concentration at both ends. The opposing 90:10 label gradients
cancel the chemical flux, while their electrical mobilities add to less than the parent's. -/
theorem charged_opposing_ratio (factor rt charge voltage : ℝ) :
    Face.flux factor rt charge (9/10) (1/10) voltage +
        Face.flux factor rt charge (1/10) (9/10) voltage =
      ((8/5) / Real.log 9) * Face.flux factor rt charge 1 1 voltage := by
  have m : Face.mean (9/10) (1/10) = (4/5) / Real.log 9 := by
    rw [mean_quotient (by norm_num) (by norm_num) (by norm_num [abs_of_nonneg]),
      ← Real.log_div (by norm_num) (by norm_num)]
    norm_num
  simp only [Face.flux, Face.drop, Face.mean_swap (a := 9/10) (b := 1/10) (by norm_num) (by norm_num),
    m, mean_same, Real.log_one]
  ring

/-- Mathlib's strict lower bound on log(1+x) gives 8/5 < log 9 at x = 8. -/
theorem charged_ratio_bounds : 0 < (8/5) / Real.log 9 ∧ (8/5) / Real.log 9 < 1 := by
  have h := Real.lt_log_one_add_of_pos (x := (8 : ℝ)) (by norm_num)
  norm_num at h
  have hp : 0 < Real.log 9 := Real.log_pos (by norm_num)
  exact ⟨div_pos (by norm_num) hp, (div_lt_one hp).2 (by linarith)⟩

end
end CellsProofs.Transport.LabelDiffusion
