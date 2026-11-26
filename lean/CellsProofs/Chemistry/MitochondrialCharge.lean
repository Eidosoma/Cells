import CellsProofs.Chemistry.MitochondrialCycles
import Mathlib.Algebra.BigOperators.Group.Finset.Sigma
import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Tactic.FieldSimp

/-! # Matrix and intermembrane-space row charge in MT-1b

Amounts are concentrations times compartment water volume. Boundary extents are
positive inward. Reaction extents, including reverse cycles, are signed.
-/

namespace CellsProofs.Chemistry.MitochondrialCharge

open Finset MitochondrialCycles
open scoped BigOperators

/-- Every signed combination of the seven declared inner-membrane cycles preserves total charge. -/
theorem cycles_cancel {ι : Type*} (steps : Finset ι) (cycle : ι → Cycle) (extent : ι → ℝ) :
    ∑ i ∈ steps, extent i * (change (cycle i) matrixCharge + change (cycle i) outerCharge) = 0 := by
  apply sum_eq_zero
  intro i _
  obtain ⟨hp, hn⟩ := charge_on_each_side (cycle i)
  simp [hp, hn]

def inventory {ι : Type*} (rows : Finset ι) (wN wP : ℝ) (z n p : ι → ℝ) : ℝ :=
  ∑ i ∈ rows, z i * (wN * n i + wP * p i)

/-- The inner reactions can transform individual species. Their combined charge change is zero.
Only the net charge imported across the outer boundary can change this inventory. -/
theorem inventory_change {ι : Type*} (rows : Finset ι) (wN wP : ℝ) (z n p n' p' : ι → ℝ)
    (internal outer : ι → ℝ)
    (amounts : ∀ i ∈ rows, wN * (n' i - n i) + wP * (p' i - p i) = internal i + outer i)
    (chargeClosed : ∑ i ∈ rows, z i * internal i = 0) :
    inventory rows wN wP z n' p' - inventory rows wN wP z n p = ∑ i ∈ rows, z i * outer i := by
  unfold inventory
  rw [← sum_sub_distrib]
  calc
    _ = ∑ i ∈ rows, (z i * internal i + z i * outer i) := by
      apply sum_congr rfl
      intro i hi
      rw [← mul_add, ← amounts i hi]
      ring
    _ = _ := by rw [sum_add_distrib, chargeClosed, zero_add]

/-- The freely moving ions may carry nonzero opposing charges even at zero total current. -/
theorem conserved_iff {before after incoming : ℝ} (balance : after - before = incoming) :
    after = before ↔ incoming = 0 := by rw [← balance, sub_eq_zero]

/-- Open-circuit potential on one passive face, in units RT/F. The electrical coefficient is
positive when a permeant charged form has positive weight. -/
theorem zero_current_iff {ι : Type*} (forms : Finset ι) (weight z logRatio : ι → ℝ) (v : ℝ)
    (conducting : 0 < ∑ i ∈ forms, weight i * (z i)^2) :
    (∑ i ∈ forms, z i * weight i * (logRatio i + z i * v)) = 0 ↔
      v = -(∑ i ∈ forms, z i * weight i * logRatio i) / (∑ i ∈ forms, weight i * (z i)^2) := by
  have expand (i : ι) : z i * weight i * (logRatio i + z i * v) =
      z i * weight i * logRatio i + weight i * (z i)^2 * v := by ring
  simp_rw [expand]
  rw [sum_add_distrib, ← sum_mul, eq_div_iff conducting.ne', mul_comm v]
  constructor <;> intro h <;> linarith

/-- Fixing matrix charge alone leaves the initial combined inventory free to vary with IMS
charge. Two states with the same matrix charge and different IMS charge have different totals. -/
theorem anchor_ne {matrix ims₁ ims₂ : ℝ} (different : ims₁ ≠ ims₂) :
    matrix + ims₁ ≠ matrix + ims₂ := by simpa using different

/-- A moving base form carries its bound ligands. Weighting each form's flux by its
charge agrees with booking the base row once and the signed ligand totals separately. -/
theorem form_flux_charge {ι κ : Type*} (forms : Finset ι) (ligands : Finset κ)
    (baseCharge : ℝ) (charge : κ → ℝ) (bound : ι → κ → ℝ) (flux : ι → ℝ) :
    (∑ f ∈ forms, (baseCharge + ∑ l ∈ ligands, charge l * bound f l) * flux f) =
      baseCharge * (∑ f ∈ forms, flux f) +
        ∑ l ∈ ligands, charge l * ∑ f ∈ forms, bound f l * flux f := by
  simp_rw [add_mul, Finset.sum_mul, mul_assoc, Finset.sum_add_distrib, Finset.mul_sum]
  exact congrArg (_ + ·) Finset.sum_comm

end CellsProofs.Chemistry.MitochondrialCharge
