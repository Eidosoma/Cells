import Mathlib.Analysis.SpecialFunctions.Log.Basic
import Mathlib.Tactic.Linarith

/-! # Reversible ATP-driven transport

Positive cycles move cargo from N to P and consume ATP. The factored transporter
uses the log of its forward rate (capacity × availability × saturation) and
`x = ΔG/(RT)`. The two branches below write its `expm1` in real arithmetic.
-/

namespace CellsProofs.Transport.ATPCycle

noncomputable section

def flux (enabled : Bool) (logForward x : ℝ) : ℝ :=
  if enabled then
    Real.exp (logForward + max x 0) *
      (if 0 ≤ x then Real.exp (-x) - 1 else -(Real.exp x - 1))
  else 0

theorem flux_disabled (logForward x : ℝ) : flux false logForward x = 0 := rfl

theorem flux_eq_mass_action (logForward x : ℝ) :
    flux true logForward x = Real.exp logForward * (1 - Real.exp x) := by
  by_cases hx : 0 ≤ x
  · simp only [flux, if_true, if_pos hx, max_eq_left hx, Real.exp_add]
    have cancel : Real.exp x * Real.exp (-x) = 1 := by rw [← Real.exp_add]; simp
    rw [mul_assoc, mul_sub, cancel, mul_one]
  · simp [flux, hx, max_eq_right (le_of_not_ge hx), neg_sub]

theorem forward_iff (logForward x : ℝ) : 0 < flux true logForward x ↔ x < 0 := by
  rw [flux_eq_mass_action, mul_pos_iff_of_pos_left (Real.exp_pos _), sub_pos, Real.exp_lt_one_iff]

theorem reverse_iff (logForward x : ℝ) : flux true logForward x < 0 ↔ 0 < x := by
  simp [flux_eq_mass_action, mul_neg_iff, Real.exp_pos, not_lt_of_ge (Real.exp_pos logForward).le]

theorem stall_iff (logForward x : ℝ) : flux true logForward x = 0 ↔ x = 0 := by
  rw [flux_eq_mass_action, mul_eq_zero, or_iff_right (Real.exp_pos _).ne', sub_eq_zero,
    eq_comm, Real.exp_eq_one_iff]

/-- Heat in pJ/s when the flux is in fmol/s and RT in J/mol. -/
theorem heat_nonneg (enabled : Bool) (logForward x : ℝ) {rt : ℝ} (hrt : 0 ≤ rt) :
    0 ≤ -(rt / 1000) * flux enabled logForward x * x := by
  cases enabled with
  | false => simp [flux_disabled]
  | true =>
    have hc : 0 ≤ rt / 1000 := by positivity
    rcases lt_trichotomy x 0 with hx | rfl | hx
    · exact mul_nonneg_of_nonpos_of_nonpos
        (mul_nonpos_of_nonpos_of_nonneg (neg_nonpos.mpr hc) ((forward_iff _ _).mpr hx).le) hx.le
    · simp
    · exact mul_nonneg (mul_nonneg_of_nonpos_of_nonpos
        (neg_nonpos.mpr hc) ((reverse_iff _ _).mpr hx).le) hx.le

/-- Fuel free energy in units of RT, n cargo per ATP, valence z, log activity
ratio ln(a_P) − ln(a_N), and dimensionless voltage ψ = F(V_N − V_P)/(RT). -/
def deltaG (fuel n z logRatio ψ : ℝ) : ℝ := fuel + n * (logRatio - z * ψ)

theorem proton_stall_iff (logForward fuel logRatio ψ : ℝ) {n : ℝ} (hn : 0 < n) :
    flux true logForward (deltaG fuel n 1 logRatio ψ) = 0 ↔ ψ = logRatio + fuel / n := by
  rw [stall_iff, deltaG, one_mul, ← sub_eq_iff_eq_add', eq_div_iff hn.ne']
  constructor <;> intro h <;> linarith only [h]

theorem neutral_voltage_independent (enabled : Bool) (logForward fuel n logRatio ψ : ℝ) :
    flux enabled logForward (deltaG fuel n 0 logRatio ψ) =
      flux enabled logForward (fuel + n * logRatio) := by simp [deltaG]

end

end CellsProofs.Transport.ATPCycle
