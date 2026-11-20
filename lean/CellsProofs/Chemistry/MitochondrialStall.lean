import CellsProofs.Chemistry.MitochondrialCycles
import CellsProofs.Transport.ATPCycle
import Mathlib.Algebra.GeomSum

/-! # Stall, reversal and heat in the seven mitochondrial cycles

`x = ΔG/(RT)` is the free energy of a complete forward turnover. The forward
kinetic prefactor can depend on free concentrations and voltage at each state.
Complexes III and IV use an exponent for a fraction of a turnover.
-/
namespace CellsProofs.Chemistry.MitochondrialStall

open MitochondrialCycles
open CellsProofs.Transport

noncomputable section

def share : Cycle → ℕ
  | .complexIII => 2
  | .complexIV => 4
  | _ => 1

theorem share_pos (c : Cycle) : 0 < share c := by cases c <;> decide

/-- The denominator in the compiled forward prefactor. -/
def weight (n : ℕ) (x : ℝ) : ℝ := ∑ i ∈ Finset.range n, Real.exp (x / n) ^ i

theorem weight_pos {n : ℕ} (hn : 0 < n) (x : ℝ) : 0 < weight n x :=
  Finset.sum_pos (fun i _ => pow_pos (Real.exp_pos _) i) ⟨0, Finset.mem_range.mpr hn⟩

def rate (c : Cycle) (enabled : Bool) (logK x : ℝ) : ℝ :=
  ATPCycle.flux enabled (logK - Real.log (weight (share c) x)) x

theorem rate_disabled (c : Cycle) (logK x : ℝ) : rate c false logK x = 0 := rfl

/-- The complete-turn implementation recovers the source exponent, including at stall. -/
theorem rate_eq_fractional (c : Cycle) (logK x : ℝ) :
    rate c true logK x = Real.exp logK * (1 - Real.exp (x / share c)) := by
  have hn : (share c : ℝ) ≠ 0 := by exact_mod_cast (share_pos c).ne'
  have hw := weight_pos (share_pos c) x
  have hpow : Real.exp (x / share c) ^ share c = Real.exp x := by
    rw [← Real.exp_nat_mul]
    congr 1
    field_simp
  have hsum := geom_sum_mul_neg (Real.exp (x / share c)) (share c)
  rw [hpow] at hsum
  change weight (share c) x * _ = _ at hsum
  rw [rate, ATPCycle.flux_eq_mass_action, Real.exp_sub, Real.exp_log hw,
    ← hsum]
  field_simp
  ring

theorem direction (c : Cycle) (logK x : ℝ) :
    (0 < rate c true logK x ↔ x < 0) ∧ (rate c true logK x < 0 ↔ 0 < x) ∧
    (rate c true logK x = 0 ↔ x = 0) :=
  ⟨ATPCycle.forward_iff _ _, ATPCycle.reverse_iff _ _, ATPCycle.stall_iff _ _⟩

/-- Chemical potentials in units of RT include the standard potential and log activity
of each free species. The dimensionless voltage is F (φ_N − φ_P)/(RT). -/
def energy (c : Cycle) (μ : Row → ℝ) (ψ : ℝ) : ℝ := change c μ - chargePerTurn c * ψ

theorem voltage_stall (c : Cycle) (hq : chargePerTurn c ≠ 0) (logK ψ : ℝ) (μ : Row → ℝ) :
    rate c true logK (energy c μ ψ) = 0 ↔ ψ = change c μ / chargePerTurn c := by
  rw [(direction ..).2.2, energy, sub_eq_zero, eq_div_iff hq, mul_comm ψ, eq_comm]

theorem neutral_stall (c : Cycle) (hq : chargePerTurn c = 0) (logK ψ : ℝ) (μ : Row → ℝ) :
    rate c true logK (energy c μ ψ) = 0 ↔ change c μ = 0 := by
  simp only [(direction ..).2.2, energy, hq, zero_mul, sub_zero]

theorem neutral_carrier_stalls (logK ψ : ℝ) (μ : Row → ℝ) :
    (rate .phosphate true logK (energy .phosphate μ ψ) = 0 ↔
      μ .piP - μ .piN = 2 * (μ .hN - μ .hP)) ∧
    (rate .potassium true logK (energy .potassium μ ψ) = 0 ↔
      μ .kP - μ .kN = μ .hP - μ .hN) := by
  rw [neutral_stall .phosphate rfl, neutral_stall .potassium rfl]
  simp only [change]
  constructor <;> constructor <;> intro h <;> linarith

/-- At fixed matrix pH, voltage and other free activities, a change in the log
ATP load is offset by three times the change in log P-side proton activity. -/
theorem synthase_load_shift (μ : Row → ℝ) (ψ atp adp pi gradient : ℝ) :
    energy .synthase (fun r => μ r + atp * count .atpN r + adp * count .adpN r +
      pi * count .piN r + gradient * count .hP r) ψ =
      energy .synthase μ ψ + (atp - adp - pi) - 3 * gradient := by
  simp +decide [energy, change, count]
  ring

/-- Instantaneous heat in pJ/s for a cycle rate in fmol/s and RT in J/mol. -/
def heat (c : Cycle) (enabled : Bool) (rt logK x : ℝ) : ℝ :=
  -(rt / 1000) * rate c enabled logK x * x

theorem heat_nonneg (c : Cycle) (enabled : Bool) {rt : ℝ} (hrt : 0 ≤ rt) (logK x : ℝ) :
    0 ≤ heat c enabled rt logK x :=
  ATPCycle.heat_nonneg enabled _ x hrt

theorem heat_zero_iff (c : Cycle) (enabled : Bool) {rt : ℝ} (hrt : 0 < rt) (logK x : ℝ) :
    heat c enabled rt logK x = 0 ↔ enabled = false ∨ x = 0 := by
  cases enabled with
  | false => simp [heat, rate, ATPCycle.flux_disabled]
  | true => simp [heat, hrt.ne', (direction c logK x).2.2]

end
end CellsProofs.Chemistry.MitochondrialStall
