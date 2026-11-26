import CellsProofs.Chemistry.ArrivalWindow

/-! # Accounting for a marked RNA at detachment (FR-38) -/

namespace CellsProofs.Chemistry.MarkedRelease

open Finset ArrivalWindow
open scoped BigOperators

/-- An event labelled at detachment belongs to one of the two complementary fates.
Use unit weight to count molecules, or the amount carried by each disjoint event. -/
theorem event_partition {ι : Type*} (cohort : Finset ι) (durable : ι → Prop)
    [DecidablePred durable] (amount : ι → ℝ) :
    (∑ i ∈ cohort.filter durable, amount i) +
      (∑ i ∈ cohort.filter (fun i => ¬ durable i), amount i) = ∑ i ∈ cohort, amount i :=
  sum_filter_add_sum_filter_not cohort durable amount

/-- In the continuous-amount engine a marked step sends p of its gross detachment to the
durable fate and 1 − p to the short-lived fate. The fraction may change at every step. -/
theorem marked_fates (steps : Finset ℕ) (start stop : ℕ) (released p : ℕ → ℝ) :
    (∑ t ∈ steps, marked start stop t (released t * p t)) +
      (∑ t ∈ steps, marked start stop t (released t * (1 - p t))) =
      ∑ t ∈ steps, marked start stop t (released t) := by
  rw [← sum_add_distrib]
  apply sum_congr rfl
  intro t _
  by_cases h : start ≤ t ∧ t < stop
  · simp only [marked, if_pos h]
    ring
  · simp [marked, h]

/-- A later observation applies each fate's own survival fraction. The sum surviving
from this release is between zero and the original gross marked amount. -/
theorem survivors_bounded {q p d s : ℝ} (hq : 0 ≤ q) (hp : p ∈ Set.Icc 0 1)
    (hd : d ∈ Set.Icc 0 1) (hs : s ∈ Set.Icc 0 1) :
    q * p * d + q * (1 - p) * s ∈ Set.Icc 0 q := by
  have durable := mul_nonneg hq hp.1
  have short := mul_nonneg hq (sub_nonneg.mpr hp.2)
  refine ⟨add_nonneg (mul_nonneg durable hd.1) (mul_nonneg short hs.1), ?_⟩
  calc q * p * d + q * (1 - p) * s
       ≤ q * p + q * (1 - p) :=
         add_le_add (mul_le_of_le_one_right durable hd.2) (mul_le_of_le_one_right short hs.2)
     _ = q := by ring

end CellsProofs.Chemistry.MarkedRelease
