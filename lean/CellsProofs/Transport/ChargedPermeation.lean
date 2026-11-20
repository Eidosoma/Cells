import CellsProofs.Transport.ProtonLeak
import Mathlib.Analysis.Calculus.Deriv.MeanValue
import Mathlib.Analysis.Calculus.Deriv.Inv
import Mathlib.Analysis.Calculus.Deriv.Pow
import Mathlib.Analysis.SpecialFunctions.ExpDeriv

/-! # Passive constant-field permeation at signed valence

The inward particle flux uses the earlier Bernoulli evaluator with x = zFV/(RT).
The outward electrical current multiplies the inward molar rate by −zF.
-/

namespace CellsProofs.Transport.ChargedPermeation

open Filter Set
open scoped Topology
noncomputable section

/-- The Nernst reversal includes the sign of the molar charge q = zF. -/
theorem reversal_iff {scale ci co rt q : ℝ} (hs : 0 < scale) (hi : 0 < ci)
    (ho : 0 < co) (ht : 0 < rt) (hq : q ≠ 0) (v : ℝ) :
    ProtonLeak.inward analyticFactor scale ci co (q * v / rt) = 0 ↔
      v = rt / q * (Real.log co - Real.log ci) := by
  rw [ProtonLeak.analytic_equilibrium_iff hs,
    ← Real.log_injOn_pos.eq_iff ho (mul_pos hi (Real.exp_pos _)),
    Real.log_mul hi.ne' (Real.exp_pos _).ne', Real.log_exp]
  constructor <;> intro h <;> field_simp [ht.ne', hq] at h ⊢ <;> linarith

/-- Instantaneous analytic heat, including inward or outward electrical drive. -/
theorem heat_nonneg {scale ci co rt : ℝ} (hs : 0 ≤ scale) (hi : 0 < ci)
    (ho : 0 < co) (ht : 0 < rt) (q v : ℝ) :
    0 ≤ 1 / 1000 * ProtonLeak.inward analyticFactor scale ci co (q * v / rt) *
      (rt * (Real.log co - Real.log ci) - q * v) := by
  have h := ProtonLeak.analytic_heat_nonneg hs ht hi ho (q * v / rt)
  unfold ProtonLeak.drive at h
  convert h using 1
  field_simp [ht.ne']
  ring

/-- B(−x) = B(x) + x in both real-arithmetic branches of the engine. -/
theorem bernoulli_reflection (x : ℝ) : seriesFactor.eval (-x) = seriesFactor.eval x + x := by
  by_cases h : |x| < 1 / 10000
  · simp only [seriesFactor, abs_neg, if_pos h]
    ring
  · have hx : x ≠ 0 := by rintro rfl; norm_num at h
    have he : Real.exp x - 1 ≠ 0 := sub_ne_zero.mpr fun e => hx ((Real.exp_eq_one_iff x).mp e)
    have hn : (Real.exp x)⁻¹ - 1 ≠ 0 := by
      rw [← Real.exp_neg]
      exact sub_ne_zero.mpr fun e => (neg_ne_zero.mpr hx) ((Real.exp_eq_one_iff (-x)).mp e)
    simp only [seriesFactor, abs_neg, if_neg h, Real.exp_neg]
    rw [div_eq_iff hn]
    field_simp [he, (Real.exp_pos x).ne']
    ring

/-- The inward rate is affine in the two molecular amounts at fixed voltage
and volumes. The two coefficients are the signed material derivatives. -/
theorem material_response (scale ni no dni dno vi vo x : ℝ) :
    ProtonLeak.inward seriesFactor scale ((ni + dni) / vi) ((no + dno) / vo) x -
      ProtonLeak.inward seriesFactor scale (ni / vi) (no / vo) x =
        scale * seriesFactor.eval x / vo * dno - scale * seriesFactor.eval (-x) / vi * dni := by
  simp only [ProtonLeak.inward, constantFieldFlux, one_mul, neg_neg]
  ring

/-- ap is area times permeability times opening in m³/s and the concentrations
are mol/m³. This convention gives amperes directly. -/
def current (ap q rt ci co v : ℝ) : ℝ :=
  -q * ProtonLeak.inward seriesFactor ap ci co (q * v / rt)

theorem current_formula (ap q rt ci co v : ℝ) :
    current ap q rt ci co v =
      -q * ap * ((co - ci) * seriesFactor.eval (q * v / rt) - ci * (q * v / rt)) := by
  simp only [current, ProtonLeak.inward, constantFieldFlux, one_mul, neg_neg]
  rw [bernoulli_reflection]
  ring

theorem symmetric_current (ap q rt c v : ℝ) :
    current ap q rt c c v = ap * q ^ 2 / rt * c * v := by
  rw [current_formula]
  ring

private def polynomial (x : ℝ) : ℝ := 1 - x / 2 + x ^ 2 / 12 - x ^ 4 / 720

private theorem poly_deriv (x : ℝ) :
    HasDerivAt polynomial (-(1 / 2) + x / 6 - x ^ 3 / 180) x := by
  have d := hasDerivAt_id x
  convert ((((hasDerivAt_const x (1 : ℝ)).sub (d.div_const 2)).add
    ((d.pow 2).div_const 12)).sub ((d.pow 4).div_const 720)) using 1
  simp only [id_eq]
  ring

/-- The two Bernoulli slope weights lie in [0,1]. At the two switching points
the branches are selected by value and a derivative is not assumed. -/
theorem bernoulli_slope {x : ℝ} (cut : |x| ≠ 1 / 10000) :
    ∃ w : ℝ, 0 ≤ w ∧ w ≤ 1 ∧ HasDerivAt seriesFactor.eval (-w) x := by
  rcases lt_or_gt_of_ne cut with h | h
  · have low : |x| ≤ 1 := le_trans h.le (by norm_num)
    have cube : |x ^ 3| ≤ 1 := by rw [abs_pow]; exact pow_le_one₀ (abs_nonneg _) low
    have ⟨xlo, xhi⟩ := abs_le.mp low
    have ⟨clo, chi⟩ := abs_le.mp cube
    refine ⟨-(-(1 / 2) + x / 6 - x ^ 3 / 180), by linarith, by linarith, ?_⟩
    rw [neg_neg]
    apply (poly_deriv x).congr_of_eventuallyEq
    filter_upwards [(isOpen_lt continuous_abs continuous_const).mem_nhds h] with y hy
    simp only [seriesFactor, if_pos hy, polynomial]
  · have hx : x ≠ 0 := by rintro rfl; norm_num at h
    have he : Real.exp x - 1 ≠ 0 := sub_ne_zero.mpr fun e => hx ((Real.exp_eq_one_iff x).mp e)
    have denom := sq_pos_of_ne_zero he
    let d := (Real.exp x - 1 - x * Real.exp x) / (Real.exp x - 1) ^ 2
    have lo : -1 ≤ d := by
      apply (le_div_iff₀ denom).mpr
      nlinarith [mul_nonneg (Real.exp_pos x).le (sub_nonneg.mpr (Real.add_one_le_exp x))]
    have hi : d ≤ 0 := by
      apply (div_nonpos_of_nonpos_of_nonneg _ denom.le)
      have e := mul_le_mul_of_nonneg_right (Real.add_one_le_exp (-x)) (Real.exp_pos x).le
      rw [Real.exp_neg, inv_mul_cancel₀ (Real.exp_pos x).ne'] at e
      linarith
    refine ⟨-d, neg_nonneg.mpr hi, by linarith, ?_⟩
    rw [neg_neg]
    have derivative := (hasDerivAt_id x).div ((Real.hasDerivAt_exp x).sub_const 1) he
    apply (_ : HasDerivAt (fun y : ℝ => y / (Real.exp y - 1)) d x).congr_of_eventuallyEq
    · filter_upwards [(isOpen_lt continuous_const continuous_abs).mem_nhds h] with y hy
      simp only [seriesFactor, if_neg (not_lt.mpr hy.le)]
    · simpa [d] using derivative

/-- The differential conductance lies between the minimum and maximum
concentration multiplied by z²F² APm/(RT), independent of voltage. -/
theorem conductance_bounds {ap rt : ℝ} (ha : 0 ≤ ap) (ht : 0 < rt) (q ci co v : ℝ)
    (cut : |q * v / rt| ≠ 1 / 10000) :
    ∃ g : ℝ, HasDerivAt (current ap q rt ci co) g v ∧
      ap * q ^ 2 / rt * min ci co ≤ g ∧ g ≤ ap * q ^ 2 / rt * max ci co := by
  obtain ⟨w, hw, hw', db⟩ := bernoulli_slope cut
  have dx := ((hasDerivAt_id v).const_mul q).div_const rt
  have d := (((db.comp v dx).const_mul (co - ci)).sub (dx.const_mul ci)).const_mul (-q * ap)
  let gain := ap * q ^ 2 / rt
  have gain_nn : 0 ≤ gain := div_nonneg (mul_nonneg ha (sq_nonneg q)) ht.le
  refine ⟨gain * ((1 - w) * ci + w * co), ?_, ?_, ?_⟩
  · simp_rw [funext (current_formula ap q rt ci co)]
    convert d using 1
    simp only [gain, id_eq, mul_one]
    ring
  · apply mul_le_mul_of_nonneg_left _ gain_nn
    nlinarith only [mul_le_mul_of_nonneg_left (min_le_left ci co) (sub_nonneg.mpr hw'),
      mul_le_mul_of_nonneg_left (min_le_right ci co) hw]
  · apply mul_le_mul_of_nonneg_left _ gain_nn
    nlinarith only [mul_le_mul_of_nonneg_left (le_max_left ci co) (sub_nonneg.mpr hw'),
      mul_le_mul_of_nonneg_left (le_max_right ci co) hw]

/-- Same bounds for the slope between recorded voltages on an interval
contained in one evaluator branch, by the mean value theorem. -/
theorem chord_bounds {ap rt a b : ℝ} (ha : 0 ≤ ap) (ht : 0 < rt) (ab : a < b)
    (q ci co : ℝ) (branch : ∀ v ∈ Icc a b, |q * v / rt| ≠ 1 / 10000) :
    let i := current ap q rt ci co
    let g := (i b - i a) / (b - a)
    ap * q ^ 2 / rt * min ci co ≤ g ∧ g ≤ ap * q ^ 2 / rt * max ci co := by
  have bounds := fun v hv => conductance_bounds ha ht q ci co v (branch v hv)
  have diff : DifferentiableOn ℝ (current ap q rt ci co) (Icc a b) :=
    fun v hv => (bounds v hv).choose_spec.1.differentiableAt.differentiableWithinAt
  obtain ⟨v, hv, same⟩ := exists_deriv_eq_slope _ ab diff.continuousOn (diff.mono Ioo_subset_Icc_self)
  obtain ⟨g, derivAt, lo, hi⟩ := bounds v (Ioo_subset_Icc_self hv)
  rw [derivAt.deriv] at same
  dsimp only
  rw [← same]
  exact ⟨lo, hi⟩

end

end CellsProofs.Transport.ChargedPermeation
