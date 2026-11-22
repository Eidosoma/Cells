import Mathlib.Algebra.BigOperators.Group.Finset.Basic
import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Ring

/-! # Machine and residue balances during templated polymerisation

Boundary zero carries initiation. For j < m, boundary j+1 is the exit from stage j;
boundary m releases a complete product and returns its machine. The extents can be
the SSPRK(3,3) weighted fluxes of any accepted half-step.
-/

namespace CellsProofs.Chemistry.Polymerisation

open scoped BigOperators
open Finset

def stageChange (flow : ℕ → ℝ) (j : ℕ) : ℝ := flow j - flow (j + 1)

/-- Internal stage transfers cancel from the number of engaged machines. -/
theorem engaged_change (m : ℕ) (flow : ℕ → ℝ) :
    ∑ j ∈ range m, stageChange flow j = flow 0 - flow m := by
  induction m with
  | zero => simp
  | succ m ih => rw [sum_range_succ, ih, stageChange]; ring

/-- A stage-j complex holds j lots of r residues. A release carries all m lots. -/
theorem transit_change (m : ℕ) (r : ℝ) (flow : ℕ → ℝ) :
    (∑ j ∈ range m, (j : ℝ) * r * stageChange flow j) + (m : ℝ) * r * flow m =
      r * ∑ j ∈ range m, flow (j + 1) := by
  induction m with
  | zero => simp
  | succ m ih =>
    rw [sum_range_succ, sum_range_succ, Nat.cast_succ, stageChange]
    linarith only [ih]

/-- Any finite set of chains may use the same pool; each can have its own number of stages. -/
theorem pool_step {ι : Type*} (chains : Finset ι) (m : ι → ℕ) (c flow : ι → ℕ → ℝ) (free : ℝ) :
    (free + ∑ i ∈ chains, (flow i (m i) - flow i 0)) +
      (∑ i ∈ chains, ∑ j ∈ range (m i), (c i j + stageChange (flow i) j)) =
    free + ∑ i ∈ chains, ∑ j ∈ range (m i), c i j := by
  simp only [sum_add_distrib, engaged_change, sum_sub_distrib]
  ring

/-- Updating the saved counters and stage occupancies preserves the old residue residual,
including a half-step starting with chains already in transit. Here L = m*r. -/
theorem residue_step (m : ℕ) (r exits released : ℝ) (c flow : ℕ → ℝ) :
    r * (exits + ∑ j ∈ range m, flow (j + 1)) -
      (∑ j ∈ range m, (j : ℝ) * r * (c j + stageChange flow j)) -
      (m : ℝ) * r * (released + flow m) =
    r * exits - (∑ j ∈ range m, (j : ℝ) * r * c j) - (m : ℝ) * r * released := by
  simp only [mul_add, sum_add_distrib]
  linarith only [transit_change m r flow]

end CellsProofs.Chemistry.Polymerisation
