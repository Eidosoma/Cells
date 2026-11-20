import CellsProofs.Transport.MixedMembrane

/-! # Voltage along a fixed external sodium-plus-potassium series

The BIO-002 reference fits two voltages and extrapolates to a higher potassium
dose. The bounds below quantify over every pair in the fitting-reading box.
-/
namespace CellsProofs.Transport.ConditionedVoltage
open MixedMembrane
noncomputable section

/-- Only the external sodium and potassium concentrations change. -/
def bath (m : Membrane) (salt k : ℝ) : Membrane :=
  { m with naOut := salt - k, kOut := k }

def intercept (m : Membrane) (salt : ℝ) : ℝ :=
  (m.pNa * salt + m.pCl * m.clIn) / denominator m

def slope (m : Membrane) : ℝ := (m.pK - m.pNa) / denominator m

theorem bath_affine (m : Membrane) (salt k : ℝ) :
    numerator (bath m salt k) / denominator (bath m salt k) = intercept m salt + slope m * k := by
  simp only [intercept, slope, numerator, denominator, bath]
  ring

/-- The conditioned equation follows from zero total passive membrane current. -/
theorem reversal_iff_affine (m : Membrane) (salt k v : ℝ) {f thermal : ℝ}
    (hf : 0 < f) (ht : 0 < thermal) (hn : 0 < numerator (bath m salt k))
    (hd : 0 < denominator m) :
    total analyticFactor (bath m salt k) f (v / thermal) = 0 ↔
      v = thermal * Real.log (intercept m salt + slope m * k) := by
  rw [reversal_iff _ hf ht hn hd, bath_affine]

/-- Exponential voltage at a fraction w of the distance between the fitting doses. -/
def argument (thermal w x y : ℝ) : ℝ :=
  (1 - w) * Real.exp (x / thermal) + w * Real.exp (y / thermal)

def predict (thermal w x y : ℝ) : ℝ := thermal * Real.log (argument thermal w x y)

theorem two_point_fit {a b k₁ k₂ thermal x y : ℝ} (k : ℝ) (hk : k₁ < k₂)
    (hx : Real.exp (x / thermal) = a + b * k₁)
    (hy : Real.exp (y / thermal) = a + b * k₂) :
    argument thermal ((k - k₁) / (k₂ - k₁)) x y = a + b * k := by
  unfold argument
  rw [hx, hy]
  field_simp [(sub_pos.mpr hk).ne']
  ring

/-- Two different doses fix the intercept and slope of the transformed curve. -/
theorem coefficients_unique {a b c d k₁ k₂ : ℝ} (hk : k₁ < k₂)
    (h₁ : a + b * k₁ = c + d * k₁) (h₂ : a + b * k₂ = c + d * k₂) :
    a = c ∧ b = d := by
  have h : (b - d) * (k₂ - k₁) = 0 := by linarith
  have heq := sub_eq_zero.mp ((mul_eq_zero.mp h).resolve_right (sub_pos.mpr hk).ne')
  exact ⟨by simpa [heq] using h₁, heq⟩

/-- Beyond the second dose the first fitting voltage has a nonpositive weight
and the second a positive one. -/
private theorem argument_order {thermal w x₁ x₂ y₁ y₂ : ℝ} (ht : 0 < thermal) (hw : 1 ≤ w)
    (hx : x₁ ≤ x₂) (hy : y₁ ≤ y₂) : argument thermal w x₂ y₁ ≤ argument thermal w x₁ y₂ := by
  apply add_le_add
  · exact mul_le_mul_of_nonpos_left (Real.exp_le_exp.mpr (div_le_div_of_nonneg_right hx ht.le))
      (sub_nonpos.mpr hw)
  · exact mul_le_mul_of_nonneg_left (Real.exp_le_exp.mpr (div_le_div_of_nonneg_right hy ht.le))
      (by linarith)

theorem argument_pos_of_rising {thermal w x y : ℝ} (ht : 0 < thermal) (hw : 0 ≤ w)
    (hxy : x ≤ y) : 0 < argument thermal w x y := by
  have h := mul_le_mul_of_nonneg_left
    (Real.exp_le_exp.mpr (div_le_div_of_nonneg_right hxy ht.le)) hw
  unfold argument
  linarith [Real.exp_pos (x / thermal)]

/-- The same two corners attain the extrema of the voltage and of the change
from the first reading. The baseline in each difference is that corner's own. -/
theorem extrapolation_bounds {thermal w xₗ x xₕ yₗ y yₕ : ℝ}
    (ht : 0 < thermal) (hw : 1 ≤ w) (hx : xₗ ≤ x ∧ x ≤ xₕ) (hy : yₗ ≤ y ∧ y ≤ yₕ)
    (hpos : 0 < argument thermal w xₕ yₗ) :
    (predict thermal w xₕ yₗ ≤ predict thermal w x y ∧
      predict thermal w x y ≤ predict thermal w xₗ yₕ) ∧
    (predict thermal w xₕ yₗ - xₕ ≤ predict thermal w x y - x ∧
      predict thermal w x y - x ≤ predict thermal w xₗ yₕ - xₗ) := by
  have lo := argument_order ht hw hx.2 hy.1
  have hi := argument_order ht hw hx.1 hy.2
  have vl : predict thermal w xₕ yₗ ≤ predict thermal w x y :=
    mul_le_mul_of_nonneg_left (Real.log_le_log hpos lo) ht.le
  have vh : predict thermal w x y ≤ predict thermal w xₗ yₕ :=
    mul_le_mul_of_nonneg_left (Real.log_le_log (lt_of_lt_of_le hpos lo) hi) ht.le
  exact ⟨⟨vl, vh⟩, sub_le_sub vl hx.2, sub_le_sub vh hx.1⟩

/-- BIO-002 has equally spaced doses (5.4, 35.4, 65.4 mM) and a ±2 mV
figure-reading box on each voltage. Every fitted log argument is positive. -/
theorem c3_reading_bounds {thermal x y measured : ℝ} (ht : 0 < thermal)
    (hx : -41 ≤ x ∧ x ≤ -37) (hy : -26 ≤ y ∧ y ≤ -22)
    (hm : -20 ≤ measured ∧ measured ≤ -16) :
    let w : ℝ := (65.4 - 5.4) / (35.4 - 5.4)
    let low := predict thermal w (-37) (-26)
    let high := predict thermal w (-41) (-22)
    let pred := predict thermal w x y
    (low ≤ pred ∧ pred ≤ high) ∧
    (low - (-37) ≤ pred - x ∧ pred - x ≤ high - (-41)) ∧
    (low - (-16) ≤ pred - measured ∧ pred - measured ≤ high - (-20)) := by
  dsimp only
  have hw : (65.4 - 5.4) / (35.4 - 5.4 : ℝ) = 2 := by norm_num
  rw [hw]
  have hp : 0 < argument thermal 2 (-37) (-26) := argument_pos_of_rising ht (by norm_num)
    (by norm_num)
  obtain ⟨⟨lo, hi⟩, delta⟩ := extrapolation_bounds ht (by norm_num) hx hy hp
  exact ⟨⟨lo, hi⟩, delta, sub_le_sub lo hm.2, sub_le_sub hi hm.1⟩

end
end CellsProofs.Transport.ConditionedVoltage
