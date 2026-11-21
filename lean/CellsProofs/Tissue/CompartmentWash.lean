import Mathlib.Data.Real.Basic
import Mathlib.Logic.Function.Iterate
import Mathlib.Tactic.Ring

/-! The instantaneous exchange at a fixed-volume finite node (FR-27).
Amounts use one common unit. Bound ligand is held during the event. -/

namespace CellsProofs.Tissue.CompartmentWash

noncomputable def afterWash (fraction amount bufferAmount : ℝ) : ℝ :=
  (1 - fraction) * amount + fraction * bufferAmount

/-- Adding the collected liquid and subtracting the supply recovers the whole inventory. -/
theorem inventory (f n b bound : ℝ) :
    afterWash f n b + bound + f * n - f * b = n + bound := by
  unfold afterWash
  ring

/-- Every admitted fraction leaves a positive free amount, including a whole wash. -/
theorem positive {f n b : ℝ} (hf : 0 < f) (hfull : f ≤ 1) (hn : 0 < n) (hb : 0 < b) :
    0 < afterWash f n b := by
  exact add_pos_of_nonneg_of_pos (mul_nonneg (sub_nonneg.mpr hfull) hn.le) (mul_pos hf hb)

theorem whole (n b : ℝ) : afterWash 1 n b = b := by simp [afterWash]

/-- Successive identical washes with no intervening flux or binding relax to the buffer level. -/
theorem repeated (f n b : ℝ) (k : ℕ) :
    (fun x => afterWash f x b)^[k] n = b + (1 - f) ^ k * (n - b) := by
  induction k with
  | zero => simp only [Function.iterate_zero_apply, pow_zero, one_mul]; ring
  | succ k ih =>
    rw [Function.iterate_succ_apply', ih, pow_succ]
    unfold afterWash
    ring

end CellsProofs.Tissue.CompartmentWash
