import CellsProofs.Tissue.RestrictedLumen
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

end CellsProofs.Tissue.CompartmentWash
