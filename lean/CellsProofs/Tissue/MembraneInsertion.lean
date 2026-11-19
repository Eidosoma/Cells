import Mathlib.Algebra.BigOperators.Group.Finset.Sigma
import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Ring

/-! # Capacitor heat when uncharged membrane is inserted

Capacitances are in F and voltages in V. Each free node keeps its charge and
each held node keeps its potential. The incidence of a patch is +1 at its
inside node and −1 at its outside node.
-/

namespace CellsProofs.Tissue.MembraneInsertion

open scoped BigOperators

variable {Node Patch : Type*} [Fintype Node] [Fintype Patch]

noncomputable section

/-- The same electrical work summed over nodes or over oriented patches. -/
theorem node_patch_work (inc : Node → Patch → ℝ) (dPhi : Node → ℝ) (charge : Patch → ℝ) :
    (∑ i, dPhi i * ∑ k, inc i k * charge k) =
      ∑ k, (∑ i, inc i k * dPhi i) * charge k := by
  simp only [Finset.sum_mul, Finset.mul_sum]
  rw [Finset.sum_comm]
  simp only [mul_left_comm, mul_assoc, mul_comm]

/-- A held node keeps its potential. A free node keeps its net charge.
Consequently the product of patch voltage and plate-charge changes sums to zero. -/
theorem fixed_node_balance (inc : Node → Patch → ℝ) (dPhi : Node → ℝ) (plateChange : Patch → ℝ)
    (boundary : ∀ i, dPhi i = 0 ∨ ∑ k, inc i k * plateChange k = 0) :
    ∑ k, (∑ i, inc i k * dPhi i) * plateChange k = 0 := by
  rw [← node_patch_work]
  exact Finset.sum_eq_zero (fun i _ => mul_eq_zero.mpr (boundary i))

/-- First-order insertion energy plus the field-solve correction, in pJ.
The correction uses patch work by `node_patch_work`. -/
def heat (dc v dv : Patch → ℝ) : ℝ :=
  (10 ^ 12 / 2) * ((∑ k, dc k * v k ^ 2) + ∑ k, dc k * v k * dv k)

/-- The change of plate charge is dC V + (C + dC) dV. At fixed node charges
and held potentials, the two-term heat is a sum of nonnegative energies. -/
theorem heat_eq_squares (c dc v dv : Patch → ℝ)
    (balance : ∑ k, dv k * (dc k * v k + (c k + dc k) * dv k) = 0) :
    heat dc v dv = (10 ^ 12 / 2) * ∑ k, (c k * dv k ^ 2 + dc k * (v k + dv k) ^ 2) := by
  have split : ∀ k, c k * dv k ^ 2 + dc k * (v k + dv k) ^ 2 =
      dc k * v k ^ 2 + dc k * v k * dv k + dv k * (dc k * v k + (c k + dc k) * dv k) := by
    intro k
    ring
  simp only [heat, split, Finset.sum_add_distrib, balance, add_zero]

theorem heat_nonneg (inc : Node → Patch → ℝ) (dPhi : Node → ℝ) (c dc v dv : Patch → ℝ)
    (hc : ∀ k, 0 ≤ c k) (hdc : ∀ k, 0 ≤ dc k)
    (voltage : ∀ k, (∑ i, inc i k * dPhi i) = dv k)
    (boundary : ∀ i, dPhi i = 0 ∨
      ∑ k, inc i k * (dc k * v k + (c k + dc k) * dv k) = 0) :
    0 ≤ heat dc v dv := by
  have balance := fixed_node_balance inc dPhi (fun k => dc k * v k + (c k + dc k) * dv k) boundary
  simp only [voltage] at balance
  rw [heat_eq_squares c dc v dv balance]
  exact mul_nonneg (by norm_num) (Finset.sum_nonneg (fun k _ =>
    add_nonneg (mul_nonneg (hc k) (sq_nonneg _)) (mul_nonneg (hdc k) (sq_nonneg _))))

/-- Both operators allocate total heat in proportion to each patch's first-order energy. -/
theorem share_nonneg {first totalFirst totalHeat : ℝ} (hf : 0 ≤ first) (hh : 0 ≤ totalHeat) :
    0 ≤ first * (if 0 < totalFirst then totalHeat / totalFirst else 0) := by
  split_ifs with h
  · exact mul_nonneg hf (div_nonneg hh h.le)
  · simp

/-- One patch against a held bath. The field solve gives dV = −dC V / (C + dC). -/
theorem one_patch_heat {c dc : ℝ} (hc : 0 < c) (hdc : 0 ≤ dc) (v : ℝ) :
    (10 ^ 12 / 2) * (dc * v ^ 2 + (-(dc * v) / (c + dc)) * (dc * v)) =
      (10 ^ 12 / 2) * c * (dc / (c + dc)) * v ^ 2 := by
  field_simp [(add_pos_of_pos_of_nonneg hc hdc).ne']
  ring

/-- The sole held bath supplies zero image charge during this fixed-charge insertion. -/
theorem one_patch_image_zero {c dc : ℝ} (hc : 0 < c) (hdc : 0 ≤ dc) (v : ℝ) :
    -((c + dc) * (-(dc * v) / (c + dc)) + dc * v) = 0 := by
  field_simp [(add_pos_of_pos_of_nonneg hc hdc).ne']
  ring

end

end CellsProofs.Tissue.MembraneInsertion
