import Mathlib.Analysis.Calculus.Deriv.Inv
import Mathlib.Analysis.SpecialFunctions.ExpDeriv
import Mathlib.Analysis.SpecialFunctions.Log.Basic
import Mathlib.Analysis.SpecialFunctions.Trigonometric.Deriv
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Ring

/-! # Instantaneous inward rectification of a monovalent cation

The driving voltage u is measured from the Nernst potential. The gain in the
current includes patch availability, area and the concentration-dependent
conductance density. The current is positive outwards.
-/

namespace CellsProofs.Transport.InwardRectifier

noncomputable section

def reversal (thermal inside outside : ℝ) : ℝ := thermal * Real.log (outside / inside)

def conductance (g outside ref : ℝ) : ℝ := g * Real.sqrt (outside / ref)

def gate (w : ℝ) : ℝ := 1 / (1 + Real.exp w)

def current (gain half slope u : ℝ) : ℝ := gain * gate ((u - half) / slope) * u

theorem reversal_shift {inside a b : ℝ} (hi : 0 < inside) (ha : 0 < a) (hb : 0 < b)
    (thermal : ℝ) : reversal thermal inside b - reversal thermal inside a =
      thermal * Real.log (b / a) := by
  simp only [reversal, Real.log_div hb.ne' hi.ne', Real.log_div ha.ne' hi.ne',
    Real.log_div hb.ne' ha.ne']
  ring

theorem sqrt_scaling {b outside : ℝ} (hb : 0 ≤ b) (hc : 0 ≤ outside) (g ref : ℝ) :
    conductance g (outside * b ^ 2) ref = b * conductance g outside ref := by
  simp only [conductance, Real.sqrt_div (mul_nonneg hc (sq_nonneg b)), Real.sqrt_div hc,
    Real.sqrt_mul hc, Real.sqrt_sq hb]
  ring

/-- At matched driving voltage, the shape of the rectifier and its absolute
scale cancel from a comparison of currents at different outside concentrations. -/
theorem matched_drive {a b : ℝ} (ha : 0 < a) (hb : 0 ≤ b) (g ref half slope u : ℝ) :
    current (conductance g b ref) half slope u =
      Real.sqrt (b / a) * current (conductance g a ref) half slope u := by
  simp only [current, conductance, Real.sqrt_div hb, Real.sqrt_div ha.le]
  conv_lhs => rw [← div_mul_cancel₀ (Real.sqrt b) (Real.sqrt_pos.2 ha).ne']
  ring

/-- A change of reference concentration and its corresponding reference
conductance leaves every current, heat and slope at fixed conditions unchanged. -/
theorem reference_invariance {b outside ref : ℝ} (hb : 0 < b) (hc : 0 ≤ outside)
    (hr : 0 < ref) (g : ℝ) :
    conductance (g * b) outside (ref * b ^ 2) = conductance g outside ref := by
  simp only [conductance, Real.sqrt_div hc, Real.sqrt_mul hr.le, Real.sqrt_sq hb.le]
  field_simp [hb.ne', (Real.sqrt_pos.2 hr).ne']
  ring

theorem gate_bounds (w : ℝ) : 0 < gate w ∧ gate w < 1 := by
  unfold gate
  constructor
  · positivity
  · apply (div_lt_iff₀ (by positivity)).2
    linarith [Real.exp_pos w]

/-- Both branches of the engine evaluator give the same logistic fraction. -/
theorem gate_branches (w : ℝ) :
    let e := Real.exp (-|w|)
    (if 0 ≤ w then e / (1 + e) else 1 / (1 + e)) = gate w := by
  dsimp only
  by_cases hw : 0 ≤ w
  · rw [if_pos hw, abs_of_nonneg hw, Real.exp_neg, gate]
    field_simp [ne_of_gt (Real.exp_pos w)]
    exact add_comm _ _
  · rw [if_neg hw, abs_of_neg (lt_of_not_ge hw), neg_neg, gate]

theorem reversal_iff {gain : ℝ} (hg : 0 < gain) (half slope u : ℝ) :
    current gain half slope u = 0 ↔ u = 0 := by
  rw [current, mul_eq_zero, or_iff_right (mul_pos hg (gate_bounds _).1).ne']

theorem outward_iff {gain : ℝ} (hg : 0 < gain) (half slope u : ℝ) :
    0 < current gain half slope u ↔ 0 < u := by
  exact mul_pos_iff_of_pos_left (mul_pos hg (gate_bounds _).1)

theorem dissipation {gain : ℝ} (hg : 0 ≤ gain) (half slope u : ℝ) :
    0 ≤ current gain half slope u * u := by
  unfold current
  rw [mul_assoc, ← sq]
  exact mul_nonneg (mul_nonneg hg (gate_bounds _).1.le) (sq_nonneg u)

private theorem gate_derivative (w : ℝ) :
    HasDerivAt gate (-(gate w * (1 - gate w))) w := by
  have d := ((hasDerivAt_const w (1 : ℝ)).add (Real.hasDerivAt_exp w)).inv
    (by positivity : 1 + Real.exp w ≠ 0)
  convert d using 1
  · funext v
    simp [gate, one_div]
  · simp [gate]
    field_simp
    ring

theorem current_derivative (gain half slope u : ℝ) :
    HasDerivAt (current gain half slope)
      (gain * (gate ((u - half) / slope) -
        (u / slope) * (gate ((u - half) / slope) * (1 - gate ((u - half) / slope))))) u := by
  have d := ((gate_derivative _).comp u (((hasDerivAt_id u).sub_const half).div_const slope))
  convert ((d.const_mul gain).mul (hasDerivAt_id u)) using 1
  simp [current, Function.comp_def]
  ring

theorem negative_slope_iff {gain slope : ℝ} (hg : 0 < gain) (hs : 0 < slope) (half u : ℝ) :
    deriv (current gain half slope) u < 0 ↔ slope < u * (1 - gate ((u - half) / slope)) := by
  let q := gate ((u - half) / slope)
  have hq : 0 < q := (gate_bounds _).1
  rw [(current_derivative gain half slope u).deriv]
  change gain * (q - u / slope * (q * (1 - q))) < 0 ↔ _
  rw [show gain * (q - u / slope * (q * (1 - q))) =
    gain * q / slope * (slope - u * (1 - q)) by field_simp [hs.ne']; ring]
  have hc := div_pos (mul_pos hg hq) hs
  simpa only [mul_zero, sub_neg] using (mul_lt_mul_left hc :
    gain * q / slope * (slope - u * (1 - q)) < gain * q / slope * 0 ↔ slope - u * (1 - q) < 0)

/-- The logistic weight q(1−q) equals 1/(2+2 cosh w). The lower
bound cosh w ≥ 1+w²/2 gives |w| q(1−q) ≤ 1/4 for every voltage. -/
private theorem weighted_gate_bound (w : ℝ) : |w| * (gate w * (1 - gate w)) ≤ 1 / 4 := by
  have shape : gate w * (1 - gate w) = 1 / (2 + 2 * Real.cosh w) := by
    rw [Real.cosh_eq, Real.exp_neg]
    unfold gate
    field_simp [ne_of_gt (Real.exp_pos w)]
    ring
  have half : 0 ≤ |w| / 2 := by positivity
  have hs := Real.self_le_sinh_iff.mpr half
  have hsq := mul_self_le_mul_self half hs
  have hc := Real.cosh_two_mul (|w| / 2)
  rw [show 2 * (|w| / 2) = |w| by ring, Real.cosh_abs, Real.cosh_sq] at hc
  rw [shape, mul_one_div, div_le_div_iff₀ (by positivity) (by norm_num)]
  nlinarith only [hc, hsq, sq_nonneg (|w| - 2)]

/-- Voltage-free upper bound used by the host when choosing a time step. -/
theorem slope_bound {gain slope : ℝ} (hg : 0 ≤ gain) (hs : 0 < slope) (half u : ℝ) :
    |deriv (current gain half slope) u| ≤ gain * (5 / 4 + |half| / (4 * slope)) := by
  let w := (u - half) / slope
  let v := gate w * (1 - gate w)
  have hq := gate_bounds w
  have hv : 0 ≤ v := mul_nonneg hq.1.le (sub_nonneg.mpr hq.2.le)
  have hquarter : v ≤ 1 / 4 := by dsimp [v]; nlinarith only [sq_nonneg (gate w - 1 / 2)]
  have hu : u / slope = w + half / slope := by dsimp [w]; ring
  rw [(current_derivative gain half slope u).deriv, abs_mul, abs_of_nonneg hg]
  apply mul_le_mul_of_nonneg_left _ hg
  change |gate w - (u / slope) * v| ≤ _
  calc
    _ ≤ |gate w| + |u / slope| * v := by
      simpa [abs_mul, abs_of_nonneg hv] using abs_sub (gate w) ((u / slope) * v)
    _ ≤ 1 + (|w| + |half| / slope) * v := by
      rw [abs_of_pos hq.1, hu]
      exact add_le_add hq.2.le (mul_le_mul_of_nonneg_right
        (by simpa [abs_div, abs_of_pos hs] using abs_add_le w (half / slope)) hv)
    _ ≤ _ := by
      have hw := weighted_gate_bound w
      have hh := mul_le_mul_of_nonneg_left hquarter (div_nonneg (abs_nonneg half) hs.le)
      change |w| * v ≤ 1 / 4 at hw
      rw [add_mul, show |half| / (4 * slope) = |half| / slope * (1 / 4) by
        simp only [div_eq_mul_inv, mul_inv_rev]; ring]
      linarith only [hw, hh]

end

end CellsProofs.Transport.InwardRectifier
