import Mathlib.Algebra.Order.Round
import Mathlib.Data.Real.Archimedean
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Ring

/-! Rounding a fixed background in fmol, then reading its charge in coulombs. -/

namespace CellsProofs.Tissue.ChargeAnchor

/-- Either nearest-grid tie choice is within half the local spacing. -/
theorem nearest_grid_error {x stored spacing : ℝ} (hs : 0 < spacing)
    (nearest : ∀ j : ℤ, |x - stored| ≤ |x - spacing * j|) :
    |x - stored| ≤ spacing / 2 := by
  let j := round (x / spacing)
  calc
    |x - stored| ≤ |x - spacing * j| := nearest j
    _ = spacing * |x / spacing - j| := by
      rw [← abs_of_pos hs, ← abs_mul, abs_of_pos hs, mul_sub, mul_div_cancel₀ _ hs.ne']
    _ ≤ spacing * (1 / 2) := mul_le_mul_of_nonneg_left (abs_sub_round _) hs.le
    _ = spacing / 2 := by ring

/-- Both passes use the same stored ionic products, whose exact sum is `ions`.
    An offset `defect` in the fixed background is in fmol. The final difference is in C. -/
theorem residual_error {k anchor ions defect quotient ionicSum fixed net charge residual : ℝ}
    {eDiv eIons eFixed eNet eCharge eResidual : ℝ} (hk : 0 < k)
    (hDiv : |quotient - anchor / k| ≤ eDiv)
    (hIons : |ionicSum - ions| ≤ eIons)
    (hFixed : |fixed - (quotient - ionicSum + defect)| ≤ eFixed)
    (hNet : |net - (fixed + ions)| ≤ eNet)
    (hCharge : |charge - k * net| ≤ eCharge)
    (hResidual : |residual - (charge - anchor)| ≤ eResidual) :
    |residual - k * defect| ≤ k * (eDiv + eIons + eFixed + eNet) + eCharge + eResidual := by
  have hn : |net - (anchor / k + defect)| ≤ eDiv + eIons + eFixed + eNet := by
    simp only [abs_le] at hDiv hIons hFixed hNet ⊢
    constructor <;> linarith
  have h := mul_le_mul_of_nonneg_left hn hk.le
  rw [← abs_of_pos hk, ← abs_mul, abs_of_pos hk, mul_sub, mul_add, mul_div_cancel₀ _ hk.ne'] at h
  simp only [abs_le] at h hCharge hResidual ⊢
  constructor <;> linarith

/-- A closed tolerance at least as large as the arithmetic error admits a balanced input. -/
theorem balanced_admitted {residual budget floor : ℝ} (h : |residual - 0| ≤ budget) :
    |residual| ≤ max floor budget :=
  (by simpa using h : |residual| ≤ budget).trans (le_max_right _ _)

/-- A true mismatch larger than tolerance plus arithmetic error is always detected. -/
theorem defect_refused {residual mismatch budget tolerance : ℝ}
    (h : |residual - mismatch| ≤ budget) (separated : tolerance + budget < |mismatch|) :
    tolerance < |residual| := by
  have triangle := abs_sub_le mismatch residual 0
  rw [sub_zero, sub_zero, abs_sub_comm mismatch residual] at triangle
  linarith

/-- At the midpoint between adjacent backgrounds, either choice leaves the same charge error. -/
theorem midpoint_residual {k spacing ions fixed : ℝ} (hk : 0 ≤ k) (hs : 0 ≤ spacing)
    (tie : fixed = -ions ∨ fixed = -ions + spacing) :
    |k * (fixed + ions) - k * (spacing / 2)| = k * (spacing / 2) := by
  rcases tie with rfl | rfl
  · rw [neg_add_cancel, mul_zero, zero_sub, abs_neg, abs_of_nonneg (by positivity)]
  · rw [show -ions + spacing + ions = spacing by ring,
        show k * spacing - k * (spacing / 2) = k * (spacing / 2) by ring,
        abs_of_nonneg (by positivity)]

/-- At inventories between 2²⁰ and 2²¹ fmol the binary64 spacing is 2⁻³² fmol.
    Even half of it exceeds the original 10⁻²⁰ C tolerance at the Cells charge conversion. -/
theorem midpoint_exceeds_floor {k : ℝ} (hk : 9 / 10 ^ 11 ≤ k) :
    1 / 10 ^ 20 < k * ((1 / 2 ^ 32) / 2) := by
  norm_num at hk ⊢
  linarith

end CellsProofs.Tissue.ChargeAnchor
