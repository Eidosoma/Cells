import Mathlib.Algebra.BigOperators.Group.Finset.Sigma
import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Data.Real.Basic
import Mathlib.Analysis.SpecialFunctions.Exp
import Mathlib.Tactic.Linarith

/-! # RNA attributed to one producer across an occupant replacement (FR-38)

A producer is fixed by cell, generation and chain. The two fate rows and the terminal
hold leave with the old occupant. Each extensive counter runs across all generations.
-/

namespace CellsProofs.Chemistry.ProducerReplacement

open Finset
open scoped BigOperators

/-- A generation owns the increment above the cumulative value at its birth. -/
def sinceBirth (birth total : ℝ) : ℝ := total - birth

theorem at_birth (total : ℝ) : sinceBirth total total = 0 := sub_self _

/-- Every completed lifetime and the current, possibly unfinished one cover the counter once. -/
theorem generation_totals (boundary : ℕ → ℝ) (n : ℕ) (now : ℝ) :
    (∑ g ∈ range n, sinceBirth (boundary g) (boundary (g + 1))) +
      sinceBirth (boundary n) now = sinceBirth (boundary 0) now := by
  simp only [sinceBirth, sum_range_sub]
  linarith

/-- Combine the hold and fate balances for one producer from birth to just before
replacement. At replacement the final stocks enter the removal records. The degradation
terms account for RNA already lost during this producer's life. -/
theorem generation_balance {F : Type*} (fates : Finset F) (holdAtBirth arrivals finalHold : ℝ)
    (atBirth detached finalStock degraded : F → ℝ)
    (hold : holdAtBirth + arrivals = finalHold + ∑ f ∈ fates, detached f)
    (row : ∀ f ∈ fates, atBirth f + detached f = finalStock f + degraded f) :
    holdAtBirth + arrivals + ∑ f ∈ fates, atBirth f =
      finalHold + (∑ f ∈ fates, finalStock f) + ∑ f ∈ fates, degraded f := by
  have rows := sum_congr rfl row
  simp only [sum_add_distrib] at rows
  linarith

/-- A single label's departing amount, using the stocks and shares just before the event. -/
noncomputable def removedByLabel {P L : Type*} (pools : Finset P) (stock : P → ℝ)
    (share : P → L → ℝ) (label : L) : ℝ := ∑ p ∈ pools, stock p * share p label

/-- Booking the rows and the hold with their respective owners counts each pool once
for each label, regardless of the order of the two event reports. -/
theorem disjoint_removals {P L : Type*} [DecidableEq P] (rows holds : Finset P)
    (distinct : Disjoint rows holds) (stock : P → ℝ) (share : P → L → ℝ) (label : L) :
    removedByLabel (rows ∪ holds) stock share label =
      removedByLabel rows stock share label + removedByLabel holds stock share label :=
  sum_union distinct

/-- Normalized shares distribute the full physical removal across its labels. -/
theorem removal_total {P L : Type*} (pools : Finset P) (labels : Finset L)
    (stock : P → ℝ) (share : P → L → ℝ) (normalized : ∀ p ∈ pools, ∑ l ∈ labels, share p l = 1) :
    ∑ l ∈ labels, removedByLabel pools stock share l = ∑ p ∈ pools, stock p := by
  unfold removedByLabel
  rw [sum_comm]
  apply sum_congr rfl
  intro p hp
  rw [← mul_sum, normalized p hp, mul_one]

/-- A newcomer's label with zero share before replacement receives zero departing RNA. -/
theorem absent_at_removal {P L : Type*} (pools : Finset P) (stock : P → ℝ)
    (share : P → L → ℝ) (label : L) (absent : ∀ p ∈ pools, share p label = 0) :
    removedByLabel pools stock share label = 0 := by
  apply sum_eq_zero
  intro p hp
  rw [absent p hp, mul_zero]

/-- One producer label on both sides of a reversible export. Each gross leg moves the
same labelled amount out of its source and into its destination. Extracellular loss
and material booked at replacement remain separate in the combined balance. -/
theorem cell_node_balance {inside outside inside' outside' made removed lostIn lostOut
    forward backward inShare outShare : ℝ}
    (cell : inside' = inside + made - removed - lostIn - forward * inShare + backward * outShare)
    (node : outside' = outside + forward * inShare - backward * outShare - lostOut) :
    inside' + outside' + removed + lostIn + lostOut = inside + outside + made := by
  linarith only [cell, node]

/-- The new occupant starts with none of the old label. Its only input of that
label is the corresponding share of each gross backward transfer. Loss and
re-export can only reduce the amount still inside. -/
theorem old_stock_le_returned (stock back share outflow : ℕ → ℝ) (birth : stock 0 = 0)
    (step : ∀ k, stock (k + 1) = stock k + back k * share k - outflow k)
    (gross : ∀ k, 0 ≤ back k) (fraction : ∀ k, share k ≤ 1)
    (leaves : ∀ k, 0 ≤ outflow k) (n : ℕ) :
    stock n ≤ ∑ k ∈ range n, back k := by
  induction n with
  | zero => simp [birth]
  | succ n ih =>
    rw [step n, sum_range_succ]
    have single : back n * share n ≤ back n := by
      simpa using mul_le_mul_of_nonneg_left (fraction n) (gross n)
    linarith [leaves n]

/-- Two equal pulses within the same unsampled export interval give the same total
export, but give distinct outside stocks at a later observation under first-order loss. -/
theorem earlier_pulse_retains_less {q k first last observed : ℝ} (quantity : 0 < q)
    (decay : 0 < k) (order : first < last) :
    q * Real.exp (-k * (observed - first)) < q * Real.exp (-k * (observed - last)) := by
  apply mul_lt_mul_of_pos_left _ quantity
  apply Real.exp_lt_exp.mpr
  linarith only [mul_pos decay (sub_pos.mpr order)]

end CellsProofs.Chemistry.ProducerReplacement
