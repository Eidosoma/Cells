import CellsProofs.Chemistry.SpeciesTurnover
import Mathlib.Algebra.BigOperators.Ring.Finset

/-! # Charge-following isopotential division and the daughters' connecting aperture -/
namespace CellsProofs.Tissue.DivisionBridge
noncomputable section

/-- The volume share is f and the first daughter takes a distinct area share of each patch. -/
def mismatch {Patch : Type*} [Fintype Patch] (f : ℝ) (a q : Patch → ℝ) : ℝ :=
  ∑ k, (a k - f) * q k

theorem daughter_charges {Patch : Type*} [Fintype Patch] (f : ℝ) (a q : Patch → ℝ) :
    f * (∑ k, q k) + mismatch f a q = (∑ k, a k * q k) ∧
    (1 - f) * (∑ k, q k) - mismatch f a q = ∑ k, (1 - a k) * q k := by
  simp only [mismatch, sub_mul, Finset.sum_sub_distrib, ← Finset.mul_sum, one_mul]
  constructor <;> ring

/-- Valence-weighting the compensating carrier amounts reproduces the exact
charge mismatch, including negatively charged carriers. -/
theorem carrier_charge {Ion : Type*} [Fintype Ion] (frac z : Ion → ℝ) (dq : ℝ) {F : ℝ}
    (hF : F ≠ 0) (hz : ∀ s, z s ≠ 0) (hs : ∑ s, frac s = 1) :
    (∑ s, (z s * F) * (frac s * dq / (z s * F))) = dq := by
  have h (s) : (z s * F) * (frac s * dq / (z s * F)) = frac s * dq := by
    field_simp [hz s, hF]
  simp only [h, ← Finset.sum_mul, hs, one_mul]

theorem species_balance (parent f carrier : ℝ) :
    (f * parent + carrier) + ((1 - f) * parent - carrier) = parent := by ring

theorem patch_voltage {areaFraction cap : ℝ} (voltage : ℝ) (hf : 0 < areaFraction) (hc : 0 < cap) :
    (areaFraction * (cap * voltage)) / (areaFraction * cap) = voltage := by
  field_simp
  ring

/-- For each species, the two daughters' ideal unmixing cost in units of RT is
nonnegative when both daughter amounts and their proportional baselines are positive. -/
theorem unmixing_nonneg {x y b c : ℝ} (hx : 0 < x) (hy : 0 < y) (hb : 0 < b) (hc : 0 < c)
    (balance : x + y = b + c) : 0 ≤ x * Real.log (x / b) + y * Real.log (y / c) := by
  have lower {n ref : ℝ} (hn : 0 < n) (hr : 0 < ref) :
      n - ref ≤ n * Real.log (n / ref) := by
    have h := mul_le_mul_of_nonneg_left (Real.log_le_sub_one_of_pos (div_pos hr hn)) hn.le
    rw [Real.log_div hr.ne' hn.ne'] at h
    rw [Real.log_div hn.ne' hr.ne']
    have ht : n * (ref / n - 1) = ref - n := by field_simp
    rw [ht] at h
    linarith
  linarith [lower hx hb, lower hy hc]

def linear (aperture speed h : ℝ) : ℝ := max 0 (aperture - speed * h)
def exponential (aperture tau h : ℝ) : ℝ := aperture * Real.exp (-(h / tau))

theorem linear_steps (a u : ℝ) {speed v : ℝ} (hs : 0 ≤ speed) (hv : 0 ≤ v) :
    linear (linear a speed u) speed v = linear a speed (u + v) := by
  have h := mul_nonneg hs hv
  simp only [linear, mul_add]
  by_cases hn : 0 ≤ a - speed * u
  · rw [max_eq_right hn, sub_sub]
  · rw [max_eq_left (le_of_not_ge hn), max_eq_left (by linarith : 0 - speed * v ≤ 0),
      max_eq_left (by linarith)]

theorem linear_closed {a tau t : ℝ} (ha : 0 ≤ a) (ht : 0 < tau) (h : tau ≤ t) :
    linear a (a / tau) t = 0 := by
  apply max_eq_left
  have hb := mul_le_mul_of_nonneg_left h (div_nonneg ha ht.le)
  rw [div_mul_cancel₀ _ ht.ne'] at hb
  linarith

theorem exponential_steps (a tau t u : ℝ) :
    exponential (exponential a tau t) tau u = exponential a tau (t + u) := by
  have h : -((t + u) / tau) = -(t / tau) + -(u / tau) := by ring
  simp only [exponential, h, Real.exp_add, mul_assoc]

theorem exponential_positive {a : ℝ} (ha : 0 < a) (tau t : ℝ) :
    0 < exponential a tau t := mul_pos ha (Real.exp_pos _)

/-- Availability scales the open junction's permeability–area product. For the
declared aperture law this leaves 2aD for each species and 2aσ for conductance. -/
theorem aperture_factor {initial : ℝ} (h : 0 < initial) (a coefficient : ℝ) :
    (a / initial) * (2 * initial * coefficient) = 2 * a * coefficient := by
  field_simp
  ring

end
end CellsProofs.Tissue.DivisionBridge
