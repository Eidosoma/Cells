import CellsProofs.Chemistry.Stoichiometry
import Mathlib.Tactic.DeriveFintype

/-! # Closed enzyme binding and catalysis

The enzyme fixture of `cells.operator.local_species_reactions@1` has two reactions at one cell,
`E + S ⇌ C` and `C → E + P`. The complex carries one enzyme unit and one
substrate unit. The product retains the substrate unit.
-/

namespace CellsProofs.Chemistry.Enzyme

open scoped BigOperators

inductive Species | E | S | C | P deriving DecidableEq, Fintype
inductive Reaction | binding | catalysis deriving DecidableEq, Fintype

/-- Signed coefficients in the forward directions written above. -/
def net : Reaction → Species → ℤ
  | .binding, .E | .binding, .S | .catalysis, .C => -1
  | .binding, .C | .catalysis, .E | .catalysis, .P => 1
  | .binding, .P | .catalysis, .S => 0

def enzymeUnits : Species → ℤ
  | .E | .C => 1
  | .S | .P => 0

def substrateUnits : Species → ℤ
  | .S | .C | .P => 1
  | .E => 0

/-- Binding and catalysis preserve the amount of free plus bound enzyme, E + C. -/
theorem enzyme_conserved (extent : Reaction → ℝ) (amount : Species → ℝ) :
    inventory enzymeUnits (afterReactions net extent amount) = inventory enzymeUnits amount := by
  apply inventory_after_reactions
  intro r
  cases r <;> decide

/-- Free substrate, bound substrate and product together carry S + C + P substrate units. -/
theorem substrate_conserved (extent : Reaction → ℝ) (amount : Species → ℝ) :
    inventory substrateUnits (afterReactions net extent amount) =
      inventory substrateUnits amount := by
  apply inventory_after_reactions
  intro r
  cases r <;> decide

/-- The faulty catalytic column C → P loses one enzyme unit per event and balances substrate. -/
theorem missing_enzyme_balance :
    let damaged := Function.update (net .catalysis) .E 0
    (∑ s, enzymeUnits s * damaged s) = -1 ∧ (∑ s, substrateUnits s * damaged s) = 0 := by
  decide

end CellsProofs.Chemistry.Enzyme
