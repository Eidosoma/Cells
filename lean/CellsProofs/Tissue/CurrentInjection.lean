import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Ring

/-! # An electrode with a mixture of mobile charge carriers

In Cells, q is the signed charge in coulombs per fmol. A positive current
supplies net positive charge to the cell.
-/

namespace CellsProofs.Tissue.CurrentInjection

open scoped BigOperators

noncomputable def moved (fraction current h q : ℝ) : ℝ := fraction * current * h / q

theorem booked_charge {ι : Type*} (carriers : Finset ι) (f q : ι → ℝ) (i h : ℝ)
    (charged : ∀ s ∈ carriers, q s ≠ 0) :
    ∑ s ∈ carriers, q s * moved (f s) i h (q s) = (∑ s ∈ carriers, f s) * (i * h) := by
  rw [Finset.sum_mul]
  apply Finset.sum_congr rfl
  intro s hs
  unfold moved
  field_simp [charged s hs]
  ring

theorem pulse_charge {ι : Type*} (carriers : Finset ι) (f q : ι → ℝ) (i h : ℝ)
    (charged : ∀ s ∈ carriers, q s ≠ 0) (normalized : ∑ s ∈ carriers, f s = 1) :
    ∑ s ∈ carriers, q s * moved (f s) i h (q s) = i * h := by
  rw [booked_charge carriers f q i h charged, normalized, one_mul]

/-- The definition parser admits a tolerance on the declared sum of fractions. -/
theorem charge_error {ι : Type*} (carriers : Finset ι) (f q : ι → ℝ) (i h tol : ℝ)
    (charged : ∀ s ∈ carriers, q s ≠ 0) (accepted : |(∑ s ∈ carriers, f s) - 1| ≤ tol) :
    |(∑ s ∈ carriers, q s * moved (f s) i h (q s)) - i * h| ≤ tol * |i * h| := by
  rw [booked_charge carriers f q i h charged]
  have e : (∑ s ∈ carriers, f s) * (i * h) - i * h =
      ((∑ s ∈ carriers, f s) - 1) * (i * h) := by ring
  rw [e, abs_mul]
  exact mul_le_mul_of_nonneg_right accepted (abs_nonneg _)

/-- One clamped bath takes the opposite image charge. The source supplies
the change in chemical and capacitor energy less work supplied by the clamp. -/
theorem single_patch_work (chemical v bath dq capacitance : ℝ) (hc : capacitance ≠ 0) :
    chemical + capacitance / 2 * ((v + dq / capacitance)^2 - v^2) - bath * (-dq) =
      chemical + (v + bath) * dq + dq^2 / (2 * capacitance) := by
  field_simp [hc]
  ring

end CellsProofs.Tissue.CurrentInjection
