import Mathlib.Algebra.BigOperators.Group.Finset.Sigma
import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Data.Real.Basic

/-! # Conserved inventories in a reaction network

At a single site, a reaction's column records products minus reactants as
integer coefficients. Its signed extent is an amount in fmol. A weight
counts how many units of the chosen inventory each species carries.
-/

namespace CellsProofs.Chemistry

open scoped BigOperators

variable {Species Reaction : Type*} [Fintype Species] [Fintype Reaction]

noncomputable def inventory (weight : Species → ℤ) (amount : Species → ℝ) : ℝ :=
  ∑ s, (weight s : ℝ) * amount s

noncomputable def afterReactions (net : Reaction → Species → ℤ) (extent : Reaction → ℝ)
    (amount : Species → ℝ) (s : Species) : ℝ :=
  amount s + ∑ r, (net r s : ℝ) * extent r

/-- If each reaction balances the chosen inventory in integer arithmetic,
the combined update preserves it for any signed real extents. -/
theorem inventory_after_reactions (weight : Species → ℤ) (net : Reaction → Species → ℤ)
    (extent : Reaction → ℝ) (amount : Species → ℝ)
    (balanced : ∀ r, ∑ s, weight s * net r s = 0) :
    inventory weight (afterReactions net extent amount) = inventory weight amount := by
  simp only [inventory, afterReactions, mul_add, Finset.sum_add_distrib, Finset.mul_sum,
    ← mul_assoc, add_eq_left]
  rw [Finset.sum_comm]
  apply Finset.sum_eq_zero
  intro r _
  have column : ∑ s, (weight s : ℝ) * (net r s : ℝ) = 0 := by exact_mod_cast balanced r
  rw [← Finset.sum_mul, column, zero_mul]

end CellsProofs.Chemistry
