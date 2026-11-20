import CellsProofs.Tissue.BathSchedule

/-! # Filling a restricted extracellular cleft from a held bath

Volumes are in pL and concentrations in fmol/pL (mM). Each unit of new volume
brings the source's composition. Heat and chemical work are per species and
`rt` includes the conversion to pJ/fmol.
-/

namespace CellsProofs.Tissue.RestrictedLumen

noncomputable section

def mixed (v d c b : ℝ) := (v * c + d * b) / (v + d)

variable {v d c b : ℝ}

theorem material_balance (hv : 0 < v) (hd : 0 ≤ d) (c b : ℝ) :
    (v + d) * mixed v d c b = v * c + d * b := by
  unfold mixed
  field_simp [(add_pos_of_pos_of_nonneg hv hd).ne']

theorem mixed_pos (hv : 0 < v) (hd : 0 ≤ d) (hc : 0 < c) (hb : 0 < b) :
    0 < mixed v d c b :=
  div_pos (add_pos_of_pos_of_nonneg (mul_pos hv hc) (mul_nonneg hd hb.le))
    (add_pos_of_pos_of_nonneg hv hd)

/-- The tracer's excess above the bath is diluted in proportion to the retained volume. -/
theorem dilution (hv : 0 < v) (hd : 0 ≤ d) (c b : ℝ) :
    mixed v d c b - b = v / (v + d) * (c - b) := by
  unfold mixed
  field_simp [(add_pos_of_pos_of_nonneg hv hd).ne']
  ring

theorem mixed_bounds (hv : 0 < v) (hd : 0 ≤ d) (c b : ℝ) :
    min c b ≤ mixed v d c b ∧ mixed v d c b ≤ max c b := by
  have hvol := add_pos_of_pos_of_nonneg hv hd
  unfold mixed
  constructor
  · apply (le_div_iff₀ hvol).mpr
    rw [mul_add]
    exact add_le_add (by simpa [mul_comm] using mul_le_mul_of_nonneg_left (min_le_left c b) hv.le)
      (by simpa [mul_comm] using mul_le_mul_of_nonneg_left (min_le_right c b) hd)
  · apply (div_le_iff₀ hvol).mpr
    rw [mul_add]
    exact add_le_add (by simpa [mul_comm] using mul_le_mul_of_nonneg_left (le_max_left c b) hv.le)
      (by simpa [mul_comm] using mul_le_mul_of_nonneg_left (le_max_right c b) hd)

/-- Includes a saved observation filled to the current area after a partial booked fill. -/
theorem fills_compose {d₁ : ℝ} (hv : 0 < v) (h₁ : 0 ≤ d₁) (d₂ c b : ℝ) :
    mixed (v + d₁) d₂ (mixed v d₁ c b) b = mixed v (d₁ + d₂) c b := by
  change ((v + d₁) * mixed v d₁ c b + d₂ * b) / _ = (v * c + (d₁ + d₂) * b) / _
  rw [material_balance hv h₁, add_mul, add_assoc, add_assoc]

/-- When both daughter areas and their onset references inherit the same split,
the sum over the two live patches gives the parent's original volume increment. -/
theorem split_volume (w f area onset : ℝ) :
    w * ((f * area - f * onset) + ((1 - f) * area - (1 - f) * onset)) / 2 =
      w * (area - onset) / 2 := by ring

def phi (x : ℝ) := x * Real.log x - x + 1

theorem phi_nonneg (hx : 0 < c) : 0 ≤ phi c := by
  have h := mul_le_mul_of_nonneg_left (Real.one_sub_inv_le_log_of_pos hx) hx.le
  rw [mul_sub, mul_one, mul_inv_cancel₀ hx.ne'] at h
  unfold phi
  linarith

private theorem phi_pos (hx : 0 < c) (hne : c ≠ 1) : 0 < phi c := by
  have h := Real.log_lt_sub_one_of_pos (inv_pos.mpr hx) (inv_ne_one.mpr hne)
  rw [Real.log_inv] at h
  have h' := mul_lt_mul_of_pos_left h hx
  rw [mul_sub, mul_one, mul_inv_cancel₀ hx.ne', mul_neg] at h'
  unfold phi
  linarith

/-- Both residuals passed to log1p have strictly positive one-plus-residuals over the reals. -/
theorem residual_ratios (hv : 0 < v) (hd : 0 ≤ d) (hc : 0 < c) (hb : 0 < b) :
    1 + d * (c - b) / ((v + d) * mixed v d c b) = c / mixed v d c b ∧
    1 + v * (b - c) / ((v + d) * mixed v d c b) = b / mixed v d c b := by
  have hm := material_balance hv hd c b
  have hp := (mixed_pos hv hd hc hb).ne'
  have hvol := (add_pos_of_pos_of_nonneg hv hd).ne'
  constructor <;> field_simp [hp, hvol] <;> linear_combination (mixed v d c b) * hm

def heat (v d c b : ℝ) :=
  let m := mixed v d c b
  m * (v * phi (c / m) + d * phi (b / m))

theorem heat_nonneg (hv : 0 < v) (hd : 0 ≤ d) (hc : 0 < c) (hb : 0 < b) :
    0 ≤ heat v d c b := by
  have hm := mixed_pos hv hd hc hb
  exact mul_nonneg hm.le (add_nonneg (mul_nonneg hv.le (phi_nonneg (div_pos hc hm)))
    (mul_nonneg hd (phi_nonneg (div_pos hb hm))))

theorem heat_pos (hv : 0 < v) (hd : 0 < d) (hc : 0 < c) (hb : 0 < b) (hne : c ≠ b) :
    0 < heat v d c b := by
  have hm := mixed_pos hv hd.le hc hb
  have different : b / mixed v d c b ≠ 1 := by
    intro h
    have eq := (div_eq_one_iff_eq hm.ne').mp h
    have bal := material_balance hv hd.le c b
    rw [← eq, add_mul] at bal
    exact hne ((mul_left_cancel₀ hv.ne' (add_right_cancel bal)).symm)
  exact mul_pos hm (add_pos_of_nonneg_of_pos (mul_nonneg hv.le (phi_nonneg (div_pos hc hm)))
    (mul_pos hd (phi_pos (div_pos hb hm) different)))

theorem heat_same (hv : 0 < v) (hd : 0 ≤ d) (hb : 0 < b) : heat v d b b = 0 := by
  have hm : mixed v d b b = b := sub_eq_zero.mp (by simpa using dilution hv hd b b)
  simp [heat, hm, div_self hb.ne', phi]

private theorem phi_scale {a m : ℝ} (ha : 0 < a) (hm : 0 < m) :
    m * phi (a / m) = a * Real.log a - a * Real.log m - a + m := by
  unfold phi
  rw [Real.log_div ha.ne' hm.ne']
  field_simp [hm.ne']
  ring

/-- The entropy formula can also be evaluated from the three endpoint concentrations. -/
theorem heat_entropy (hv : 0 < v) (hd : 0 ≤ d) (hc : 0 < c) (hb : 0 < b) :
    heat v d c b = v * c * Real.log c + d * b * Real.log b -
      (v * c + d * b) * Real.log (mixed v d c b) := by
  let m := mixed v d c b
  have hm : 0 < m := mixed_pos hv hd hc hb
  calc
    heat v d c b = v * (m * phi (c / m)) + d * (m * phi (b / m)) := by unfold heat; dsimp [m]; ring
    _ = _ := by
      rw [phi_scale hc hm, phi_scale hb hm]
      change _ = _ - _ * Real.log m
      linear_combination material_balance hv hd c b

/-- Chemical supply work plus pressure work equals the tissue energy change plus mixing heat. -/
theorem energy_booking (rt : ℝ) (hv : 0 < v) (hd : 0 ≤ d) (hc : 0 < c) (hb : 0 < b) :
    rt * d * b * Real.log b - rt * d * b =
      BathSchedule.energy rt (v + d) (v * c + d * b) - BathSchedule.energy rt v (v * c) +
      rt * heat v d c b := by
  rw [heat_entropy hv hd hc hb]
  unfold BathSchedule.energy mixed
  rw [mul_div_cancel_left₀ _ hv.ne']
  ring

end

end CellsProofs.Tissue.RestrictedLumen
