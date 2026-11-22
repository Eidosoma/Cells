import CellsProofs.Tissue.CompartmentWash
import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith

/-! # Drawing a tracer from two internally well-mixed regions

Volumes are in pL. A concentration in mM times a volume in pL is an amount in
fmol. Each draw uses its pre-refill concentration. Its local volume is an input.
-/

namespace CellsProofs.Tissue.RegionalSampling

open scoped BigOperators
noncomputable section

def collected (drawA drawB cA cB : ℝ) : ℝ := drawA * cA + drawB * cB

def concentration (vA vB cA cB : ℝ) : ℝ := collected vA vB cA cB / (vA + vB)

/-- Sum the existing wash identity across the regions, keeping the gross refill separate. -/
theorem inventory {Region : Type*} (regions : Finset Region) (fraction amount buffer : Region → ℝ) :
    (∑ i ∈ regions, CompartmentWash.afterWash (fraction i) (amount i) (buffer i)) +
      (∑ i ∈ regions, fraction i * amount i) =
      (∑ i ∈ regions, amount i) + ∑ i ∈ regions, fraction i * buffer i := by
  rw [← Finset.sum_add_distrib, ← Finset.sum_add_distrib]
  apply Finset.sum_congr rfl
  intro i _
  linarith only [CompartmentWash.inventory (fraction i) (amount i) (buffer i) 0]

/-- With a common starting and refill background, a draw removes exactly its
fraction of the excess tracer and leaves the complementary fraction at its node. -/
theorem excess_and_refill (f excess background : ℝ) :
    f * (excess + background) - f * background = f * excess ∧
      CompartmentWash.afterWash f (excess + background) background - background = (1 - f) * excess := by
  constructor
  · ring
  · unfold CompartmentWash.afterWash
    ring

/-- The concentration bias is the product of the concentration contrast and the
disproportionate volume drawn, divided by the sample and chamber volumes. -/
theorem concentration_bias {a b u v : ℝ} (hab : 0 < a + b) (huv : 0 < u + v) (cA cB : ℝ) :
    concentration u v cA cB - concentration a b cA cB =
      (u * b - v * a) * (cA - cB) / ((u + v) * (a + b)) := by
  unfold concentration collected
  field_simp [hab.ne', huv.ne']
  ring

/-- For two positive region volumes and a nonempty sample, a draw is representative
exactly when the regions agree in concentration or give equal fractions of their volumes. -/
theorem representative_iff {a b u v : ℝ} (ha : 0 < a) (hb : 0 < b) (huv : 0 < u + v)
    (cA cB : ℝ) :
    concentration u v cA cB = concentration a b cA cB ↔ cA = cB ∨ u / a = v / b := by
  rw [← sub_eq_zero, concentration_bias (add_pos ha hb) huv,
    div_eq_zero_iff, or_iff_left (mul_pos huv (add_pos ha hb)).ne', mul_eq_zero,
    sub_eq_zero, sub_eq_zero, div_eq_div_iff ha.ne' hb.ne', or_comm]

/-- For a richer region A the collected concentration exceeds the chamber mean
exactly when a larger fraction of A than of B is drawn. -/
theorem enrichment_iff {a b u v cA cB : ℝ} (ha : 0 < a) (hb : 0 < b)
    (huv : 0 < u + v) (hc : cB < cA) :
    concentration a b cA cB < concentration u v cA cB ↔ v / b < u / a := by
  rw [← sub_pos, concentration_bias (add_pos ha hb) huv,
    div_pos_iff_of_pos_right (mul_pos huv (add_pos ha hb)), mul_pos_iff_of_pos_right (sub_pos.mpr hc),
    sub_pos, div_lt_div_iff₀ hb ha]

end
end CellsProofs.Tissue.RegionalSampling
