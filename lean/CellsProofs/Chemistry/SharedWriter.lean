import Mathlib.Algebra.BigOperators.Group.Finset.Basic
import Mathlib.Analysis.SpecialFunctions.Log.Basic
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Ring

/-! # A finite inventory shared by two split-step writers (FR-43)

The counters below are signed amounts produced minus consumed by each writer.
Their values can already be nonzero at restart. Volume is in pL and stock in fmol.
-/

namespace CellsProofs.Chemistry.SharedWriter

open Finset
open scoped BigOperators

theorem split_balance {before mid after a b : ℝ}
    (first : mid - before = a) (second : after - mid = b) : after - before = a + b := by
  linarith

/-- The same calculation covers a complete trace and a tail with nonzero initial books. -/
theorem window_balance (stock bookA bookB : ℕ → ℝ) (start steps : ℕ)
    (booked : ∀ i < steps, stock (start + (i + 1)) - stock (start + i) =
      (bookA (start + (i + 1)) - bookA (start + i)) +
      (bookB (start + (i + 1)) - bookB (start + i))) :
    stock (start + steps) - stock start =
      (bookA (start + steps) - bookA start) + (bookB (start + steps) - bookB start) := by
  have telescope (f : ℕ → ℝ) :
      (∑ i ∈ range steps, (f (start + (i + 1)) - f (start + i))) =
        f (start + steps) - f start := by
    simpa using sum_range_sub (fun i => f (start + i)) steps
  rw [← telescope stock, ← telescope bookA, ← telescope bookB, ← sum_add_distrib]
  exact sum_congr rfl fun i hi => booked i (mem_range.mp hi)

/-- A measured reserve used only by writer B can also identify writer A's contribution. -/
theorem separate_writers {stockChange reserveChange bookA bookB sign : ℝ}
    (total : stockChange = bookA + bookB) (reserve : bookB = sign * reserveChange) :
    bookA = stockChange - sign * reserveChange := by
  rw [← reserve, total]
  ring

/-- The standard-potential part of the two bookings, using the registry value for this row. -/
theorem shared_standard_energy (mu before mid after : ℝ) :
    mu * (mid - before) + mu * (after - mid) = mu * (after - before) := by ring

/-- With amounts and controls held fixed, the two diagnostic rates each have form a / V. -/
theorem volume_rate_distinguishes {a v w : ℝ} (ha : a ≠ 0) (hv : 0 < v) (hw : 0 < w) :
    a / v = a / w ↔ v = w := by
  rw [div_eq_div_iff hv.ne' hw.ne']
  constructor
  · intro h
    exact (mul_left_cancel₀ ha h).symm
  · rintro rfl
    rfl

/-- The ideal mixing contribution divided by RT, with a common reference concentration. -/
noncomputable def ideal (n v : ℝ) : ℝ := n * (Real.log (n / v) - 1)

/-- Signed error in a reaction's free-energy change when evaluated at the old volume.
The standard-potential terms cancel between the two volume choices. -/
theorem stale_volume_energy {old new v0 v : ℝ} (ho : 0 < old) (hn : 0 < new)
    (h0 : 0 < v0) (hv : 0 < v) :
    (ideal new v0 - ideal old v0) - (ideal new v - ideal old v) =
      (new - old) * Real.log (v / v0) := by
  simp only [ideal, Real.log_div hn.ne' h0.ne', Real.log_div ho.ne' h0.ne',
    Real.log_div hn.ne' hv.ne', Real.log_div ho.ne' hv.ne', Real.log_div hv.ne' h0.ne']
  ring

end CellsProofs.Chemistry.SharedWriter
