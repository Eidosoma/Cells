import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Analysis.SpecialFunctions.Pow.Real
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Positivity
import Mathlib.Tactic.Ring

/-! # Cell-owned compartments and scheduled membrane retrieval and recycling -/
namespace CellsProofs.Tissue.MembraneTrafficking
noncomputable section

/-- Cytosol and each finite compartment are grouped by the declared owner. Absolute
amounts are measured once, irrespective of which array stores the compartment. -/
def ownerAmount {Cell Node : Type*} [Fintype Node] [DecidableEq Cell]
    (owner : Node → Cell) (cytosol : Cell → ℝ) (inside : Node → ℝ) (c : Cell) : ℝ :=
  cytosol c + ∑ j, if owner j = c then inside j else 0

theorem sum_owners {Cell Node : Type*} [Fintype Cell] [Fintype Node] [DecidableEq Cell]
    (owner : Node → Cell) (cytosol : Cell → ℝ) (inside : Node → ℝ) :
    (∑ c, ownerAmount owner cytosol inside c) = (∑ c, cytosol c) + ∑ j, inside j := by
  simp only [ownerAmount, Finset.sum_add_distrib]
  congr 1
  rw [Finset.sum_comm]
  simp

/-- The lumen is the outside plate of its sole bounding capacitor. -/
theorem lumen_potential {cap charge owner lumen : ℝ} (hc : 0 < cap)
    (plate : charge = -cap * (owner - lumen)) : lumen = owner + charge / cap := by
  rw [plate]
  field_simp
  ring

/-- The net free charge of the lumen sets the sign of its voltage relative to the owner. -/
theorem lumen_above_owner {cap charge owner lumen : ℝ} (hc : 0 < cap)
    (plate : charge = -cap * (owner - lumen)) : owner < lumen ↔ 0 < charge := by
  rw [lumen_potential hc plate]
  simpa using (div_pos_iff_of_pos_right hc : 0 < charge / cap ↔ 0 < charge)

/-- Area and capacitance both use the same signed two-patch booking. -/
theorem patch_balance (source target move : ℝ) :
    (source - move) + (target + move) = source + target := by ring

theorem remaining_specific_capacitance (cap : ℝ) {area move : ℝ}
    (ha : 0 < area) (hm : move < area) :
    (cap - cap * (move / area)) / (area - move) = cap / area := by
  have h := (sub_pos.mpr hm).ne'
  field_simp
  ring

/-- A source retains a power of its remaining area fraction. -/
def retained (count ratio enrichment : ℝ) : ℝ := count * ratio ^ enrichment

theorem retained_bounds {count ratio enrichment : ℝ} (hn : 0 < count)
    (hr : 0 < ratio) (h₁ : ratio ≤ 1) (he : 0 ≤ enrichment) :
    0 < retained count ratio enrichment ∧ retained count ratio enrichment ≤ count := by
  exact ⟨mul_pos hn (Real.rpow_pos_of_pos hr _),
    mul_le_of_le_one_right hn.le (Real.rpow_le_one hr.le h₁ he)⟩

theorem same_direction_stages (n e : ℝ) {r s : ℝ} (hr : 0 ≤ r) (hs : 0 ≤ s) :
    retained (retained n r e) s e = retained n (r * s) e := by
  simp [retained, Real.mul_rpow hr hs, mul_assoc]

theorem surface_and_pool (surface pool remaining : ℝ) :
    remaining + (pool + (surface - remaining)) = surface + pool := by ring

/-- After retrieving area d and returning the same area from a uniformly mixed
pool, the retrieved cohort still has members inside if the pool had seed area B. -/
theorem round_trip_pool (n seed d : ℝ) {area : ℝ} (ha : 0 < area) :
    retained (n - retained n ((area - d) / area) 1) (seed / (seed + d)) 1 =
      n * (d / area) * (seed / (seed + d)) := by
  simp only [retained, Real.rpow_one]
  have h : n - n * ((area - d) / area) = n * (d / area) := by
    field_simp
    ring
  rw [h]

theorem round_trip_pool_pos {n area seed d : ℝ} (hn : 0 < n) (ha : 0 < area)
    (hb : 0 < seed) (hd : 0 < d) :
    0 < retained (n - retained n ((area - d) / area) 1) (seed / (seed + d)) 1 := by
  rw [round_trip_pool _ _ _ ha]
  positivity

end
end CellsProofs.Tissue.MembraneTrafficking
