import CellsProofs.Transport.ATPCycle
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Ring

/-! # Sodium and monovalent anion cotransport

A forward cycle brings n sodium ions and one anion from P to N. The two
logarithms are log(c_N/c_P) and ψ = F(V_N − V_P)/(RT). The host uses the
reversible factored rate from ATPCycle with its saturations on the P side.
-/

namespace CellsProofs.Transport.SodiumAnionSymport

open CellsProofs.Transport.ATPCycle

noncomputable section

def energy (n na anion ψ : ℝ) : ℝ := n * (na + ψ) + (anion - ψ)

def head (n na anion : ℝ) : ℝ := -(n * na + anion) / (n - 1)

/-- The two source-side Hill denominators set the positive forward rate. -/
theorem source_rate {k a sodium anion kNa kB : ℝ} (hk : 0 < k) (ha : 0 < a)
    (hs : 0 < sodium) (hb : 0 < anion) (hNa : 0 < kNa) (hB : 0 < kB)
    (p q : ℕ) (x : ℝ) :
    let ds := 1 + (kNa / sodium) ^ p
    let db := 1 + (kB / anion) ^ q
    flux true (Real.log k + Real.log a - Real.log ds - Real.log db) x =
      k * a / ds / db * (1 - Real.exp x) := by
  dsimp only
  rw [flux_eq_mass_action, Real.exp_sub, Real.exp_sub, Real.exp_add, Real.exp_log hk,
    Real.exp_log ha, Real.exp_log (by positivity), Real.exp_log (by positivity)]

/-- The two transported rows have charges +1 and −1, and both are conserved. -/
theorem transported_rows (n j : ℝ) :
    (n * j + -(n * j) = 0) ∧ (j + -j = 0) ∧ (n * j - j = (n - 1) * j) ∧
      (n * j + j = (n + 1) * j) := by
  constructor <;> simp [sub_mul, add_mul]

theorem electrical_work (n na anion ψ : ℝ) :
    energy n na anion ψ - energy n na anion 0 = (n - 1) * ψ := by
  unfold energy
  ring

theorem energy_relative_to_stall {n : ℝ} (hn : 1 < n) (na anion ψ : ℝ) :
    energy n na anion ψ = (n - 1) * (ψ - head n na anion) := by
  unfold energy head
  field_simp [(sub_pos.mpr hn).ne']
  ring

theorem symport_stall_iff {n : ℝ} (hn : 1 < n) (logForward na anion ψ : ℝ) :
    flux true logForward (energy n na anion ψ) = 0 ↔ ψ = head n na anion := by
  rw [stall_iff, energy_relative_to_stall hn, mul_eq_zero,
    or_iff_right (sub_pos.mpr hn).ne', sub_eq_zero]

theorem import_iff {n : ℝ} (hn : 1 < n) (logForward na anion ψ : ℝ) :
    0 < flux true logForward (energy n na anion ψ) ↔ ψ < head n na anion := by
  rw [forward_iff, energy_relative_to_stall hn]
  simpa only [mul_zero, sub_neg] using
    (mul_lt_mul_left (sub_pos.mpr hn) :
      (n - 1) * (ψ - head n na anion) < (n - 1) * 0 ↔ ψ - head n na anion < 0)

theorem export_iff {n : ℝ} (hn : 1 < n) (logForward na anion ψ : ℝ) :
    flux true logForward (energy n na anion ψ) < 0 ↔ head n na anion < ψ := by
  rw [reverse_iff, energy_relative_to_stall hn, mul_pos_iff_of_pos_left (sub_pos.mpr hn), sub_pos]

theorem neutral_rate (logForward na anion ψ : ℝ) :
    flux true logForward (energy 1 na anion ψ) = flux true logForward (na + anion) := by
  congr 1
  unfold energy
  ring

theorem capacity_scaling {k : ℝ} (hk : 0 < k) (logForward x : ℝ) :
    flux true (Real.log k + logForward) x = k * flux true logForward x := by
  simp only [flux_eq_mass_action, Real.exp_add, Real.exp_log hk, mul_assoc]

/-- Multiplying either *external* concentration by the same factor subtracts
its logarithm from the corresponding N/P log ratio. The shift comparison
survives any common attenuation of the two voltage measurements. -/
theorem external_shift_ratio {n : ℝ} (hn : 1 < n) (na anion logFactor weight : ℝ) :
    weight * (head n (na - logFactor) anion - head n na anion) =
      n * (weight * (head n na (anion - logFactor) - head n na anion)) := by
  unfold head
  field_simp [(sub_pos.mpr hn).ne']
  ring

end

end CellsProofs.Transport.SodiumAnionSymport
