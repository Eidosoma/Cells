import Mathlib.Algebra.Order.Group.Unbundled.Int
import Mathlib.Algebra.Order.Ring.Abs
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.NormNum

/-! # Exponent margins of the GARD v2 row guard -/

namespace CellsProofs.Chemistry.GardRange

/-- If an operation has the documented six-row-maximum bound, the parser's strict exponent
guard places its magnitude below the largest finite binary64 value. -/
theorem upper_margin {m x : ℝ} (guard : m < 2^1020) (bound : |x| ≤ 6 * m) :
    |x| < (2^53 - 1) * 2^971 := by
  calc
    |x| ≤ 6 * m := bound
    _ < 6 * 2^1020 := mul_lt_mul_of_pos_left guard (by norm_num)
    _ < (2^53 - 1) * 2^971 := by norm_num

/-- Every nonzero integer multiple of an admitted tick has at least the magnitude of that tick.
At a tick of 2⁻¹⁰²² this excludes subnormal cache words. -/
theorem grid_floor {tick : ℝ} (positive : 0 < tick) {k : ℤ} (nonzero : k ≠ 0) :
    tick ≤ |(k : ℝ) * tick| := by
  have h : (1 : ℝ) ≤ |(k : ℝ)| := by exact_mod_cast Int.one_le_abs nonzero
  rw [abs_mul, abs_of_pos positive]
  simpa using mul_le_mul_of_nonneg_right h positive.le

end CellsProofs.Chemistry.GardRange
