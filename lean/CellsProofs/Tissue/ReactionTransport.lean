import CellsProofs.Accounting.Transfer
import CellsProofs.Chemistry.Stoichiometry

/-! # Regional material balance under reactions and transport

The split step applies local reactions, transfers signed amounts along oriented
edges, then applies local reactions again. Each extent and transfer is an
amount integrated over its part of the step. The two halves can have different
extents. Node identities and the region are fixed during the step.
-/

namespace CellsProofs.Tissue

open scoped BigOperators

variable {Node Species Edge Reaction : Type*} [DecidableEq Node]
  [Fintype Species] [Fintype Edge] [Fintype Reaction]

/-- Count one chemical inventory over all the nodes in a region. -/
noncomputable def regionInventory (region : Finset Node) (weight : Species → ℤ)
    (amount : Node → Species → ℝ) : ℝ :=
  ∑ n ∈ region, Chemistry.inventory weight (amount n)

/-- Total weighted inflow. A transfer within the region is both a credit and a debit. -/
noncomputable def boundaryTransfer (region : Finset Node) (weight : Species → ℤ)
    (sender receiver : Edge → Node) (moved : Species → Edge → ℝ) : ℝ :=
  ∑ s, (weight s : ℝ) * ∑ e, ((if receiver e ∈ region then moved s e else 0) -
    (if sender e ∈ region then moved s e else 0))

/-- Local reactions on both sides of one transport update, in the composite's split order. -/
noncomputable def reactionTransportStep (net : Node → Reaction → Species → ℤ)
    (first last : Node → Reaction → ℝ) (sender receiver : Edge → Node)
    (moved : Species → Edge → ℝ) (amount : Node → Species → ℝ) (n : Node) : Species → ℝ :=
  Chemistry.afterReactions (net n) (last n) (fun s =>
    Chemistry.afterReactions (net n) (first n) (amount n) s +
      Accounting.nodeChange sender receiver (moved s) n)

/-- Balanced reactions within the region leave boundary transfers as the entire change
in its inventory. Reactions outside the region can have arbitrary stoichiometry. -/
theorem region_inventory_balance (region : Finset Node) (weight : Species → ℤ)
    (net : Node → Reaction → Species → ℤ) (first last : Node → Reaction → ℝ)
    (sender receiver : Edge → Node) (moved : Species → Edge → ℝ) (amount : Node → Species → ℝ)
    (balanced : ∀ n ∈ region, ∀ r, ∑ s, weight s * net n r s = 0) :
    regionInventory region weight (reactionTransportStep net first last sender receiver moved amount) =
      regionInventory region weight amount + boundaryTransfer region weight sender receiver moved := by
  unfold regionInventory
  calc
    _ = ∑ n ∈ region, (Chemistry.inventory weight (amount n) +
          ∑ s, (weight s : ℝ) * Accounting.nodeChange sender receiver (moved s) n) := by
      apply Finset.sum_congr rfl
      intro n hn
      unfold reactionTransportStep
      rw [Chemistry.inventory_after_reactions _ _ _ _ (balanced n hn)]
      calc
        _ = Chemistry.inventory weight (Chemistry.afterReactions (net n) (first n) (amount n)) +
              ∑ s, (weight s : ℝ) * Accounting.nodeChange sender receiver (moved s) n := by
          simp only [Chemistry.inventory, mul_add, Finset.sum_add_distrib]
        _ = _ := by rw [Chemistry.inventory_after_reactions _ _ _ _ (balanced n hn)]
    _ = _ := by
      rw [Finset.sum_add_distrib]
      congr 1
      rw [Finset.sum_comm]
      unfold boundaryTransfer
      apply Finset.sum_congr rfl
      intro s _
      rw [← Finset.mul_sum, Accounting.region_balance]

/-- Every edge of a closed finite graph is internal, so its total inventory is conserved. -/
theorem whole_inventory_conserved [Fintype Node] (weight : Species → ℤ)
    (net : Node → Reaction → Species → ℤ) (first last : Node → Reaction → ℝ)
    (sender receiver : Edge → Node) (moved : Species → Edge → ℝ) (amount : Node → Species → ℝ)
    (balanced : ∀ n r, ∑ s, weight s * net n r s = 0) :
    regionInventory Finset.univ weight (reactionTransportStep net first last sender receiver moved amount) =
      regionInventory Finset.univ weight amount := by
  simpa [boundaryTransfer] using region_inventory_balance Finset.univ weight net first last
    sender receiver moved amount (fun n _ => balanced n)

end CellsProofs.Tissue
