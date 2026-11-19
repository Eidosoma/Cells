import Mathlib.Algebra.BigOperators.Group.Finset.Piecewise
import Mathlib.Algebra.BigOperators.Group.Finset.Sigma
import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Data.Real.Basic

/-! # Accounting for oriented transfers

An edge carries one signed amount or amount rate from its sender to its receiver.
The same owner can appear on any number of edges. Summing over a region cancels
internal transfers and yields the signed exchange with the rest of the graph.
-/

namespace CellsProofs.Accounting

open scoped BigOperators

variable {Node Edge : Type*} [DecidableEq Node] [Fintype Edge]

/-- One species' credits minus debits at a node. A blocked edge has zero flux. -/
noncomputable def nodeChange (sender receiver : Edge → Node) (flux : Edge → ℝ) (node : Node) : ℝ :=
  ∑ edge, ((if receiver edge = node then flux edge else 0) -
    (if sender edge = node then flux edge else 0))

/-- Reorienting any subset of edges preserves every node's credit or debit when
each reoriented edge also reverses its signed flux. -/
theorem nodeChange_reorient (flip : Edge → Bool) (sender receiver : Edge → Node)
    (flux : Edge → ℝ) (node : Node) :
    nodeChange (fun e => if flip e then receiver e else sender e)
      (fun e => if flip e then sender e else receiver e)
      (fun e => if flip e then -flux e else flux e) node =
      nodeChange sender receiver flux node := by
  unfold nodeChange
  apply Finset.sum_congr rfl
  intro edge _
  cases h : flip edge with
  | false => simp [h]
  | true =>
    by_cases hs : sender edge = node <;> by_cases hr : receiver edge = node <;> simp [h, hs, hr]

/-- An internal edge contributes zero to this sum. An entering edge contributes its
flux, and a leaving edge contributes its negative. -/
theorem region_balance (region : Finset Node) (sender receiver : Edge → Node) (flux : Edge → ℝ) :
    ∑ node ∈ region, nodeChange sender receiver flux node =
      ∑ edge, ((if receiver edge ∈ region then flux edge else 0) -
        (if sender edge ∈ region then flux edge else 0)) := by
  unfold nodeChange
  rw [Finset.sum_comm]
  apply Finset.sum_congr rfl
  intro edge _
  simp [Finset.sum_sub_distrib]

/-- Internal transfers conserve each species on the whole finite graph. -/
theorem total_balance [Fintype Node] (sender receiver : Edge → Node) (flux : Edge → ℝ) :
    ∑ node, nodeChange sender receiver flux node = 0 := by
  simpa using region_balance Finset.univ sender receiver flux

/-- Per-species charge weights (valence × Faraday's constant × mol/fmol) give
charge balance even when different ions carry charge of opposite signs. -/
theorem charge_balance [Fintype Node] {Ion : Type*} [Fintype Ion]
    (chargePerAmount : Ion → ℝ) (sender receiver : Edge → Node) (flux : Ion → Edge → ℝ) :
    ∑ node, ∑ ion, chargePerAmount ion * nodeChange sender receiver (flux ion) node = 0 := by
  rw [Finset.sum_comm]
  apply Finset.sum_eq_zero
  intro ion _
  rw [← Finset.mul_sum, total_balance, mul_zero]

end CellsProofs.Accounting
