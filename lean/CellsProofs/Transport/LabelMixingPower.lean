import CellsProofs.Transport.LabelDiffusion

/-! # Diffusion power for labels of the same neutral tracer

For a Fick face the positive common scale includes mobility, RT and the unit
conversion. The accepted IMEX step uses its own fluxes and predicted weights.
-/
namespace CellsProofs.Transport.LabelMixingPower

open scoped BigOperators
open Real
noncomputable section

def power (scale a b : ℝ) : ℝ := scale * ((a - b) * (log a - log b))

/-- Face power in pJ/s on the equal-concentration and logarithmic-quotient branches. -/
theorem neutral_face_power {a b rt : ℝ} (h : LabelDiffusion.exactBranch a b)
    (hrt : 0 < rt) (factor voltage : ℝ) :
    (1 / 1000 : ℝ) * (Face.flux factor rt 0 a b voltage * Face.drop rt 0 a b voltage) =
      power ((1 / 1000) * (factor / (1 / 10 ^ 15)) * rt) a b := by
  rw [LabelDiffusion.neutral_face_eq_fick h.1 h.2.1 hrt factor voltage h.2.2]
  unfold LabelDiffusion.fick Face.drop power
  ring

/-- One summand of a relative entropy of the normalized label fractions. -/
def divergenceTerm (p q : ℝ) : ℝ := p * (q / p - 1 - log (q / p))

private theorem divergence_formula {p q : ℝ} (hp : 0 < p) (hq : 0 < q) :
    divergenceTerm p q = p * (log p - log q) + q - p := by
  rw [divergenceTerm, log_div hq.ne' hp.ne']
  field_simp
  ring

private theorem divergence_nonneg {p q : ℝ} (hp : 0 < p) (hq : 0 < q) :
    0 ≤ divergenceTerm p q :=
  mul_nonneg hp.le (sub_nonneg.mpr (log_le_sub_one_of_pos (div_pos hq hp)))

private theorem divergence_zero {p q : ℝ} (hp : 0 < p) (hq : 0 < q) :
    divergenceTerm p q = 0 ↔ p = q := by
  constructor
  · intro h
    by_contra different
    have hratio : q / p ≠ 1 := fun e => different ((div_eq_one_iff_eq hp.ne').mp e).symm
    exact (mul_pos hp (sub_pos.mpr (log_lt_sub_one_of_pos (div_pos hq hp) hratio))).ne' h
  · rintro rfl
    simp [divergenceTerm, hp.ne']

def mixing (a b p q : ℝ) : ℝ := a * divergenceTerm p q + b * divergenceTerm q p

private theorem mixing_nonneg {a b p q : ℝ} (ha : 0 < a) (hb : 0 < b)
    (hp : 0 < p) (hq : 0 < q) : 0 ≤ mixing a b p q :=
  add_nonneg (mul_nonneg ha.le (divergence_nonneg hp hq))
    (mul_nonneg hb.le (divergence_nonneg hq hp))

private theorem mixing_zero {a b p q : ℝ} (ha : 0 < a) (hb : 0 < b)
    (hp : 0 < p) (hq : 0 < q) : mixing a b p q = 0 ↔ p = q := by
  constructor
  · intro h
    apply (divergence_zero hp hq).mp
    have first := divergence_nonneg hp hq
    have second := mul_nonneg hb.le (divergence_nonneg hq hp)
    unfold mixing at h
    nlinarith
  · rintro rfl
    simp [mixing, (divergence_zero hp hp).2 rfl]

/-- a and b are total concentrations. p and q are each side's fractions of each label. -/
theorem power_difference {ι : Type*} (s : Finset ι) {a b : ℝ} (ha : 0 < a) (hb : 0 < b)
    (scale : ℝ) (p q : ι → ℝ) (hp : ∀ i ∈ s, 0 < p i) (hq : ∀ i ∈ s, 0 < q i)
    (psum : ∑ i ∈ s, p i = 1) (qsum : ∑ i ∈ s, q i = 1) :
    (∑ i ∈ s, power scale (a * p i) (b * q i)) - power scale a b =
      scale * ∑ i ∈ s, mixing a b (p i) (q i) := by
  have row (i) (hi : i ∈ s) :
      (a * p i - b * q i) * (log (a * p i) - log (b * q i)) =
      (a * p i - b * q i) * (log a - log b) + mixing a b (p i) (q i) +
        (a - b) * (p i - q i) := by
    rw [log_mul ha.ne' (hp i hi).ne', log_mul hb.ne' (hq i hi).ne', mixing,
      divergence_formula (hp i hi) (hq i hi), divergence_formula (hq i hi) (hp i hi)]
    ring
  simp only [power, ← Finset.mul_sum]
  rw [Finset.sum_congr rfl row]
  simp only [Finset.sum_add_distrib, ← Finset.sum_mul, Finset.sum_sub_distrib, ← Finset.mul_sum,
    psum, qsum, mul_one, sub_self, mul_zero, add_zero]
  ring

/-- Resolving labels increases or preserves ideal face power. Equality characterizes identical
label fractions on the two sides, even if their total concentrations differ. -/
theorem power_order_and_equality {ι : Type*} (s : Finset ι) {a b scale : ℝ}
    (ha : 0 < a) (hb : 0 < b) (hs : 0 < scale) (p q : ι → ℝ)
    (hp : ∀ i ∈ s, 0 < p i) (hq : ∀ i ∈ s, 0 < q i)
    (psum : ∑ i ∈ s, p i = 1) (qsum : ∑ i ∈ s, q i = 1) :
    power scale a b ≤ ∑ i ∈ s, power scale (a * p i) (b * q i) ∧
    ((∑ i ∈ s, power scale (a * p i) (b * q i)) = power scale a b ↔
      ∀ i ∈ s, p i = q i) := by
  have hn (i) (hi : i ∈ s) := mixing_nonneg ha hb (hp i hi) (hq i hi)
  have gap := power_difference s ha hb scale p q hp hq psum qsum
  constructor
  · linarith [mul_nonneg hs.le (Finset.sum_nonneg hn)]
  · rw [← sub_eq_zero, gap, mul_eq_zero, or_iff_right hs.ne', Finset.sum_eq_zero_iff_of_nonneg hn]
    exact forall₂_congr fun i hi => mixing_zero ha hb (hp i hi) (hq i hi)

/-- In the accepted step dt times RT and the unit conversion multiply a sum of J²/W.
Among positive-weight rows, zero booked heat requires every applied mean flux to vanish. -/
theorem booking_zero_iff {ι : Type*} (s : Finset ι) {scale : ℝ} (hs : 0 < scale)
    (flux weight : ι → ℝ) (hw : ∀ i ∈ s, 0 < weight i) :
    scale * (∑ i ∈ s, (flux i) ^ 2 / weight i) = 0 ↔ ∀ i ∈ s, flux i = 0 := by
  rw [mul_eq_zero, or_iff_right hs.ne', Finset.sum_eq_zero_iff_of_nonneg
    fun i hi => div_nonneg (sq_nonneg (flux i)) (hw i hi).le]
  apply forall₂_congr
  intro i hi
  simp [div_eq_zero_iff, (hw i hi).ne']

/-- The reduction in J²/W when combining two rows using their *summed weights*.
An unsplit simulation predicts its own weight from its concentrations. -/
theorem booking_difference_two {w v : ℝ} (hw : 0 < w) (hv : 0 < v) (j k : ℝ) :
    j ^ 2 / w + k ^ 2 / v - (j + k) ^ 2 / (w + v) =
    (v * j - w * k) ^ 2 / (w * v * (w + v)) := by
  field_simp [hw.ne', hv.ne', (add_pos hw hv).ne']
  ring

end
end CellsProofs.Transport.LabelMixingPower
