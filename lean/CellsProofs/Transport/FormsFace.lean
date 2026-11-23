import CellsProofs.Accounting.Transfer
import CellsProofs.Transport.LogMeanFace
import Mathlib.Data.Fintype.BigOperators

/-! # Transport of a binder and its ligands across extracellular faces

Each mover has one signed transfer and a coefficient for each stored row.
A binder form carries one copy of the binder and its signed ligand counts
relative to the reference form. The same projection applies to instantaneous
fluxes and integrated amounts. Positive transfer runs from sender to receiver.
-/

namespace CellsProofs.Transport.FormsFace

noncomputable section

/-- A stored row's share of all the mover transfers on one face. -/
def rowTransfer {Mover : Type*} [Fintype Mover] (count : Mover → ℤ)
    (transfer : Mover → ℝ) : ℝ := ∑ m, (count m : ℝ) * transfer m

/-- For one binder and one ligand, `none` is free ligand and `some f` is a
binder form. A free ligand contributes to its own row only. -/
theorem binder_and_ligand {Form : Type*} [Fintype Form] (count : Form → ℤ)
    (free : ℝ) (bound : Form → ℝ) :
    rowTransfer (fun m : Option Form => m.elim 0 (fun _ => 1)) (fun m => m.elim free bound) =
        ∑ f, bound f ∧
    rowTransfer (fun m : Option Form => m.elim 1 count) (fun m => m.elim free bound) =
        free + ∑ f, (count f : ℝ) * bound f := by
  simp [rowTransfer, Fintype.sum_option]

/-- Charge computed from the stored-row transfers equals charge computed
from the form valences implied by those same stoichiometric coefficients. -/
theorem charge_from_rows {Mover Row : Type*} [Fintype Mover] [Fintype Row]
    (count : Mover → Row → ℤ) (z : Row → ℝ) (transfer : Mover → ℝ) :
    ∑ r, z r * rowTransfer (fun m => count m r) transfer =
      ∑ m, (∑ r, z r * (count m r : ℝ)) * transfer m := by
  simp only [rowTransfer, Finset.mul_sum, Finset.sum_mul, mul_assoc]
  exact Finset.sum_comm

/-- Every stored row is conserved across a closed set of nodes even when
several faces share an endpoint or individual forms move in opposite directions. -/
theorem row_conservation {Mover Edge Node : Type*} [Fintype Mover] [Fintype Edge]
    [Fintype Node] [DecidableEq Node] (sender receiver : Edge → Node)
    (count : Mover → ℤ) (transfer : Edge → Mover → ℝ) :
    ∑ n, Accounting.nodeChange sender receiver (fun e => rowTransfer count (transfer e)) n = 0 :=
  Accounting.total_balance sender receiver _

/-- At zero voltage, swapped free-binder and occupied-form concentrations give
zero net binder flux at their common diffusivity. The occupied form still
carries a positive ligand flux when its sender concentration is higher. -/
theorem ligand_moves_at_zero_binder_flux {a b factor rt : ℝ} (hb : 0 < b) (hab : b < a)
    (hf : 0 < factor) (ht : 0 < rt) (bareCharge boundCharge : ℝ) :
    Face.flux factor rt bareCharge b a 0 + Face.flux factor rt boundCharge a b 0 = 0 ∧
      0 < Face.flux factor rt boundCharge a b 0 := by
  have ha := hb.trans hab
  have rev : Face.flux factor rt bareCharge b a 0 = -Face.flux factor rt boundCharge a b 0 := by
    simpa [Face.flux, Face.drop] using Face.flux_reverse ha hb factor rt boundCharge 0
  refine ⟨by rw [rev, neg_add_cancel], (Face.flux_pos_iff hf ht ha hb).2 ?_⟩
  simpa [Face.drop] using mul_pos ht (sub_pos.mpr (Real.log_lt_log hb hab))

end

end CellsProofs.Transport.FormsFace
