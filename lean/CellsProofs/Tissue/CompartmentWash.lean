import CellsProofs.Tissue.RestrictedLumen
import Mathlib.Algebra.BigOperators.Field
import Mathlib.Algebra.BigOperators.Group.Finset.Piecewise
import Mathlib.Logic.Function.Iterate
import Mathlib.Tactic.Ring

/-! The instantaneous exchange at a fixed-volume finite node (FR-27).
Amounts use one common unit. Bound ligand is held during the event. -/

namespace CellsProofs.Tissue.CompartmentWash

open RestrictedLumen (phi phi_nonneg)

noncomputable def afterWash (fraction amount bufferAmount : ℝ) : ℝ :=
  (1 - fraction) * amount + fraction * bufferAmount

/-- Adding the collected liquid and subtracting the supply recovers the whole inventory. -/
theorem inventory (f n b bound : ℝ) :
    afterWash f n b + bound + f * n - f * b = n + bound := by
  unfold afterWash
  ring

/-- At the compartment's own ion concentration the wash preserves inventory and the
collected and supplied amounts agree for every fraction in exact arithmetic. -/
theorem same_concentration_ion (f n : ℝ) {v : ℝ} (hv : 0 < v) :
    afterWash f n (v * (n / v)) = n ∧ f * (v * (n / v)) = f * n := by
  have hb : v * (n / v) = n := by rw [mul_comm, div_mul_cancel₀ _ hv.ne']
  rw [hb]
  exact ⟨by unfold afterWash; ring, rfl⟩

/-- Every admitted fraction leaves a positive free amount, including a whole wash. -/
theorem positive {f n b : ℝ} (hf : 0 < f) (hfull : f ≤ 1) (hn : 0 < n) (hb : 0 < b) :
    0 < afterWash f n b := by
  exact add_pos_of_nonneg_of_pos (mul_nonneg (sub_nonneg.mpr hfull) hn.le) (mul_pos hf hb)

theorem whole (n b : ℝ) : afterWash 1 n b = b := by simp [afterWash]

/-- Per exchanged neutral species, with free concentrations `c` and `b` in mM,
volume in pL and `rt` in pJ/fmol. This is the ideal isothermal heat in pJ. -/
noncomputable def mixingHeat (rt volume f c b : ℝ) : ℝ :=
  let m := afterWash f c b
  rt * volume * m * ((1 - f) * phi (c / m) + f * phi (b / m))

theorem mixingHeat_nonneg {rt volume f c b : ℝ} (hrt : 0 ≤ rt) (hv : 0 < volume)
    (hf : 0 < f) (hfull : f ≤ 1) (hc : 0 < c) (hb : 0 < b) :
    0 ≤ mixingHeat rt volume f c b := by
  have hm := positive hf hfull hc hb
  exact mul_nonneg (mul_nonneg (mul_nonneg hrt hv.le) hm.le)
    (add_nonneg (mul_nonneg (sub_nonneg.mpr hfull) (phi_nonneg (div_pos hc hm)))
      (mul_nonneg hf.le (phi_nonneg (div_pos hb hm))))

/-- Replacing the entire liquid leaves no retained liquid to mix with the buffer. -/
theorem whole_mixing_heat (rt volume c : ℝ) {b : ℝ} (hb : 0 < b) :
    mixingHeat rt volume 1 c b = 0 := by
  simp [mixingHeat, whole, hb.ne', phi]

/-- Successive identical washes with no intervening flux or binding relax to the buffer level. -/
theorem repeated (f n b : ℝ) (k : ℕ) :
    (fun x => afterWash f x b)^[k] n = b + (1 - f) ^ k * (n - b) := by
  induction k with
  | zero => simp only [Function.iterate_zero_apply, pow_zero, one_mul]; ring
  | succ k ih =>
    rw [Function.iterate_succ_apply', ih, pow_succ]
    unfold afterWash
    ring

section Labels

variable {ι : Type*} [DecidableEq ι]

/-- Amount left in label `i` after a sample of size `r` and an unlabelled supply `a`.
`s` is this label's share of the starting pool of size `n`. All amounts use one unit. -/
noncomputable def labelAmount (base i : ι) (n r a s : ℝ) : ℝ :=
  (n - r) * s + (if i = base then a else 0)

/-- The engine normalizes occupied pools and keeps the previous share when the pool is empty. -/
noncomputable def labelShare (base i : ι) (n r a s : ℝ) : ℝ :=
  if 0 < n - r + a then labelAmount base i n r a s / (n - r + a) else s

/-- Summing the amounts used by the normalizer recovers the physical post-wash amount. -/
theorem label_total [Fintype ι] (base : ι) (n r a : ℝ) (s : ι → ℝ)
    (hs : ∑ i, s i = 1) :
    ∑ i, labelAmount base i n r a (s i) = n - r + a := by
  simp [labelAmount, Finset.sum_add_distrib, ← Finset.mul_sum, hs]

/-- The amount still in each label plus its collected sample equals its start plus its refill.
This includes full removal with no refill, when the remaining physical amount is zero. -/
theorem label_inventory (base i : ι) (n r a s : ℝ) (hr : r ≤ n) (ha : 0 ≤ a) :
    (n - r + a) * labelShare base i n r a s + r * s =
      n * s + (if i = base then a else 0) := by
  by_cases ht : 0 < n - r + a
  · rw [labelShare, if_pos ht, mul_comm _ (_ / _), div_mul_cancel₀ _ ht.ne']
    unfold labelAmount
    ring
  · have hrn : r = n := by linarith
    have haz : a = 0 := by linarith
    subst r
    subst a
    simp

/-- The normalized shares sum to one, including an empty pool's retained bookkeeping shares. -/
theorem label_shares_sum [Fintype ι] (base : ι) (n r a : ℝ) (s : ι → ℝ)
    (hs : ∑ i, s i = 1) :
    ∑ i, labelShare base i n r a (s i) = 1 := by
  by_cases ht : 0 < n - r + a
  · simp only [labelShare, if_pos ht, ← Finset.sum_div]
    rw [label_total base n r a s hs, div_self ht.ne']
  · simpa only [labelShare, if_neg ht] using hs

/-- A complete exchange with positive supply puts all material in the base label. -/
theorem whole_label_share (base i : ι) (n s : ℝ) {a : ℝ} (ha : 0 < a) :
    labelShare base i n n a s = if i = base then 1 else 0 := by
  by_cases h : i = base <;> simp [labelShare, labelAmount, h, ha, ha.ne']

/-- When nothing is exchanged every label keeps its previous share. -/
theorem unchanged_label_share (base i : ι) (n s : ℝ) :
    labelShare base i n 0 0 s = s := by
  by_cases hn : 0 < n
  · simp [labelShare, labelAmount, hn, mul_comm n s, hn.ne']
  · simp [labelShare, hn]

/-- For a carrier at the same concentration in the pool and refill, an old tracer
share is diluted by the retained volume fraction. -/
theorem dilution_of_nonbase {base i : ι} (hi : i ≠ base) {n : ℝ} (hn : 0 < n) (f s : ℝ) :
    labelShare base i n (f * n) (f * n) s = (1 - f) * s := by
  simp only [labelShare, sub_add_cancel, if_pos hn, labelAmount, if_neg hi, add_zero]
  apply (div_eq_iff hn.ne').2
  ring

end Labels

end CellsProofs.Tissue.CompartmentWash
