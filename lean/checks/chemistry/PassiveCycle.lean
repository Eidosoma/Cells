import CellsProofs.Chemistry.ReactionCycles
import Mathlib.Data.Matrix.Notation

open Matrix CellsProofs.Chemistry.ReactionCycles

-- With product activity one, the equilibrium quotient is the inverse reactant activity.
example (delta : ℝ) : Real.exp 0 / Real.exp delta = Real.exp (-delta) :=
  (zero_affinity_iff_quotient delta 0 delta).1 (by simp)

/-! The columns are A → B, B → C and A → C. The last route runs backwards
on the closed path. All species potentials remain arbitrary. -/
private def net : Matrix (Fin 3) (Fin 3) ℤ := !![-1, 0, -1; 1, -1, 0; 0, 1, 1]
private def turns : Fin 3 → ℤ := ![2, 2, -2]

private theorem closed : net *ᵥ turns = 0 := by decide

example : net *ᵥ ![(2 : ℤ), 2, 2] ≠ 0 := by decide

example (mu : Fin 3 → ℝ) : (∏ r, Real.exp (-standardEnergy net mu r) ^ turns r) = 1 :=
  wegscheider_product net mu turns closed

example (mu : Fin 3 → ℝ) (offset : ℝ) :
    (∑ r, (standardEnergy net mu r + if r = 2 then offset else 0) * (turns r : ℝ)) =
      (-2) * offset := by
  let cast := Int.castRingHom ℝ
  have realClosed : net.map cast *ᵥ (cast ∘ turns) = 0 := by
    funext s
    rw [← cast.map_mulVec, closed]
    exact cast.map_zero
  calc
    _ = offset * (turns 2 : ℝ) := cycle_energy_one_offset net mu (cast ∘ turns) realClosed 2 offset
    _ = _ := by simp [turns, mul_comm]

#print axioms zero_affinity_iff_quotient
#print axioms cycle_energy_sum
#print axioms wegscheider_product
#print axioms cycle_energy_one_offset
