import Mathlib.Data.Matrix.Mul
import Mathlib.Analysis.SpecialFunctions.Pow.Real

/-! # Equilibrium constants around passive reaction cycles

At one site, `cells.operator.local_species_reactions@1` uses products minus reactants for
each column and one standard potential μ°/(RT) per species. Activities use
the same standard concentration throughout. -/

namespace CellsProofs.Chemistry.ReactionCycles

open Matrix

/-- At zero affinity the product-to-reactant activity quotient is exp(−ΔG°/RT).
The two log sums are the logarithms of the activity monomials in the passive rate. -/
theorem zero_affinity_iff_quotient (logReactants logProducts delta : ℝ) :
    logReactants - (logProducts + delta) = 0 ↔
      Real.exp logProducts / Real.exp logReactants = Real.exp (-delta) := by
  rw [← Real.exp_sub, Real.exp_eq_exp, sub_eq_zero, sub_eq_iff_eq_add, neg_add_eq_sub,
    eq_sub_iff_add_eq, eq_comm]

variable {Species Reaction : Type*} [Fintype Species] [Fintype Reaction]

/-- Dimensionless standard reaction energies, one per stoichiometric column. -/
noncomputable def standardEnergy (net : Matrix Species Reaction ℤ) (mu : Species → ℝ) :
    Reaction → ℝ :=
  mu ᵥ* net.map (Int.castRingHom ℝ)

/-- When all species return to their starting amounts, the signed extents
weight the standard reaction energies to zero, for any shared species potentials. -/
theorem cycle_energy_sum (net : Matrix Species Reaction ℤ) (mu : Species → ℝ)
    (extent : Reaction → ℝ) (closed : net.map (Int.castRingHom ℝ) *ᵥ extent = 0) :
    ∑ r, standardEnergy net mu r * extent r = 0 := by
  change (mu ᵥ* net.map (Int.castRingHom ℝ)) ⬝ᵥ extent = 0
  rw [← Matrix.dotProduct_mulVec, closed, dotProduct_zero]

/-- Wegscheider's product for signed integer traversals of the passive routes.
A negative count takes the reciprocal of that route's equilibrium constant. -/
theorem wegscheider_product (net : Matrix Species Reaction ℤ) (mu : Species → ℝ)
    (turns : Reaction → ℤ) (closed : net *ᵥ turns = 0) :
    (∏ r, Real.exp (-standardEnergy net mu r) ^ turns r) = 1 := by
  let cast := Int.castRingHom ℝ
  have realClosed : net.map cast *ᵥ (cast ∘ turns) = 0 := by
    funext s
    rw [← cast.map_mulVec, closed]
    exact cast.map_zero
  have energy : ∑ r, standardEnergy net mu r * (turns r : ℝ) = 0 :=
    cycle_energy_sum net mu (cast ∘ turns) realClosed
  calc
    _ = Real.exp (∑ r, -(standardEnergy net mu r * (turns r : ℝ))) := by
      rw [Real.exp_sum]
      simp only [← neg_mul, Real.exp_mul, Real.rpow_intCast]
    _ = 1 := by rw [Finset.sum_neg_distrib, energy, neg_zero, Real.exp_zero]

/-- Adding an independent energy offset to one route leaves its signed extent
times the offset as the residual around an otherwise closed cycle. -/
theorem cycle_energy_one_offset [DecidableEq Reaction] (net : Matrix Species Reaction ℤ)
    (mu : Species → ℝ) (extent : Reaction → ℝ) (closed : net.map (Int.castRingHom ℝ) *ᵥ extent = 0)
    (route : Reaction) (offset : ℝ) :
    (∑ r, (standardEnergy net mu r + if r = route then offset else 0) * extent r) =
      offset * extent route := by
  simp [add_mul, Finset.sum_add_distrib, cycle_energy_sum net mu extent closed, ite_mul]

end CellsProofs.Chemistry.ReactionCycles
