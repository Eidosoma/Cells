import CellsProofs.Chemistry.LineageFission
import Mathlib.Order.Interval.Finset.Nat

/-! # Independent segregation of integer units at membrane-patch division

Unit indices run through each state's occupied interval in declaration order. The
daughter counts below describe one realized block of draws. They require no probability model.
-/

namespace CellsProofs.Tissue.IntegerSegregation

open Finset
open scoped BigOperators

variable {α : Type*} [LinearOrder α]

/-- First index of state `k` in a parent site's packed array of units. -/
def offset (count : ℕ → ℕ) (k : ℕ) : ℕ := ∑ j ∈ range k, count j

def occupied (count : ℕ → ℕ) (k : ℕ) : Finset ℕ :=
  Ico (offset count k) (offset count (k + 1))

def firstUnits (count : ℕ → ℕ) (draw : ℕ → α) (f : α) (k : ℕ) : Finset ℕ :=
  (occupied count k).filter (fun i => draw i < f)

def secondUnits (count : ℕ → ℕ) (draw : ℕ → α) (f : α) (k : ℕ) : Finset ℕ :=
  (occupied count k).filter (fun i => ¬ draw i < f)

/-- Masking the complete draw block as in the kernel selects exactly the occupied winners. -/
theorem block_mask (count : ℕ → ℕ) (draw : ℕ → α) (f : α) {k K width : ℕ}
    (hk : k < K) (fits : offset count K ≤ width) :
    (range width).filter (fun i => offset count k ≤ i ∧ i < offset count (k + 1) ∧ draw i < f) =
      firstUnits count draw f k := by
  have bound : offset count (k + 1) ≤ offset count K :=
    sum_le_sum_of_subset_of_nonneg (range_mono hk) (fun _ _ _ => Nat.zero_le _)
  ext i
  simp only [firstUnits, occupied, mem_filter, mem_range, mem_Ico]
  constructor
  · rintro ⟨_, lower, upper, win⟩
    exact ⟨⟨lower, upper⟩, win⟩
  · rintro ⟨⟨lower, upper⟩, win⟩
    exact ⟨lt_of_lt_of_le upper (bound.trans fits), lower, upper, win⟩

/-- Strict comparison assigns a tie to the second daughter. -/
theorem second_membership (count : ℕ → ℕ) (draw : ℕ → α) (f : α) (k i : ℕ) :
    i ∈ secondUnits count draw f k ↔
      (offset count k ≤ i ∧ i < offset count (k + 1)) ∧ f ≤ draw i := by
  simp [secondUnits, occupied]

/-- The exact complement has the size the engine computes by natural subtraction. -/
theorem state_counts (count : ℕ → ℕ) (draw : ℕ → α) (f : α) (k : ℕ) :
    let a := (firstUnits count draw f k).card
    let b := (secondUnits count draw f k).card
    a + b = count k ∧ count k - a = b := by
  have total := filter_card_add_filter_neg_card_eq_card
    (s := occupied count k) (fun i => draw i < f)
  have size : (occupied count k).card = count k := by
    simp [occupied, offset, sum_range_succ]
  rw [size] at total
  change _ + _ = _ ∧ _ - _ = _
  change (firstUnits count draw f k).card + (secondUnits count draw f k).card = count k at total
  exact ⟨total, by omega⟩

/-- Weighting state counts by their declared number of subunits keeps the whole parent inventory. -/
theorem weighted_inventory (count weight : ℕ → ℕ) (draw : ℕ → α) (f : α) (K : ℕ) :
    (∑ k ∈ range K, weight k * (firstUnits count draw f k).card) +
      (∑ k ∈ range K, weight k * (secondUnits count draw f k).card) =
      ∑ k ∈ range K, weight k * count k := by
  rw [← sum_add_distrib]
  exact sum_congr rfl fun k _ => by rw [← Nat.mul_add, (state_counts count draw f k).1]

/-- The debit retires the parent. Its signed entry and both credits sum to zero per state. -/
theorem retirement_ledger (count : ℕ → ℕ) (draw : ℕ → α) (f : α) (k : ℕ) :
    let parent : ℤ := count k
    let a : ℤ := (firstUnits count draw f k).card
    let b : ℤ := (secondUnits count draw f k).card
    parent + (-parent) = 0 ∧ -parent + a + b = 0 := by
  have h := (state_counts count draw f k).1
  dsimp only
  omega

/-- Mean absolute sister-count difference with independent units and one common probability. -/
noncomputable def meanDifference (n : ℕ) (p : ℝ) : ℝ :=
  Chemistry.LineageFission.trialAverage p n (fun k => |(2 : ℝ) * k - n|)

theorem two_unit_difference (p : ℝ) :
    meanDifference 2 p = 1 + 4 * (p - 1 / 2) ^ 2 := by
  norm_num [meanDifference, Chemistry.LineageFission.trialAverage]
  ring

/-- Changing the common allocation probability cannot lower the four-unit mean below 1.5. -/
theorem four_unit_difference {p : ℝ} (hp : 0 ≤ p) (hle : p ≤ 1) :
    meanDifference 4 p = 3 / 2 + (p - 1 / 2) ^ 2 * (10 + 8 * p * (1 - p)) ∧
      3 / 2 ≤ meanDifference 4 p := by
  have formula : meanDifference 4 p = 3 / 2 + (p - 1 / 2) ^ 2 * (10 + 8 * p * (1 - p)) := by
    norm_num [meanDifference, Chemistry.LineageFission.trialAverage]
    ring
  have hq : 0 ≤ 1 - p := sub_nonneg.mpr hle
  exact ⟨formula, formula ▸ le_add_of_nonneg_right (by positivity)⟩

end CellsProofs.Tissue.IntegerSegregation
