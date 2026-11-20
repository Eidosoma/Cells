import Mathlib.Data.Complex.Exponential
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Ring

/-! # The exponential channel-gate stage on the tissue model

The rate is the mean of the two endpoint inverse time constants. The two
targets may differ. The lag weight includes the engine's small-step series.
-/

namespace CellsProofs.Transport.ChannelStep

noncomputable section

def lag (z : ℝ) : ℝ :=
  if z < 1 / 1000 then z * (1 / 2 - z * (1 / 6 - z * (1 / 24 - z / 120)))
  else (Real.exp (-z) - 1 + z) / z

def advance (g a b z : ℝ) : ℝ :=
  g + (a - g) * (1 - Real.exp (-z)) + (b - a) * lag z

/-- The weights on the start and end targets are both nonnegative. -/
theorem lag_bounds {z : ℝ} (hz : 0 ≤ z) : 0 ≤ lag z ∧ lag z ≤ 1 - Real.exp (-z) := by
  have he : (1 + z) * Real.exp (-z) ≤ 1 := by
    rw [Real.exp_neg, ← div_eq_mul_inv]
    exact (div_le_one (Real.exp_pos z)).mpr (by linarith [Real.add_one_le_exp z])
  unfold lag
  split_ifs with small
  · have hz1 : z ≤ 1 := by linarith
    have p : 0 ≤ z * (1 / 24 - z / 120) :=
      mul_nonneg hz (by linarith)
    have q : z * (1 / 24 - z / 120) ≤ 1 / 24 := by
      nlinarith only [sq_nonneg z, hz1]
    have r : 0 ≤ z * (1 / 6 - z * (1 / 24 - z / 120)) :=
      mul_nonneg hz (by linarith)
    have s : z * (1 / 6 - z * (1 / 24 - z / 120)) ≤ 1 / 6 := by
      nlinarith only [mul_nonneg hz p, hz1]
    have lower : z / 2 ≤ 1 - Real.exp (-z) := by
      by_cases half : Real.exp (-z) ≤ 1 / 2
      · linarith
      · nlinarith only [he, mul_nonneg hz (sub_nonneg.mpr (le_of_not_ge half))]
    exact ⟨mul_nonneg hz (by linarith), by nlinarith only [mul_nonneg hz r, lower]⟩
  · have hp : 0 < z := by linarith
    refine ⟨div_nonneg (by linarith [Real.add_one_le_exp (-z)]) hp.le, ?_⟩
    apply (div_le_iff₀ hp).mpr
    linarith only [show Real.exp (-z) + z * Real.exp (-z) ≤ 1 by linarith only [he]]

/-- A stage with admissible endpoints preserves the gate interval for any nonnegative duration. -/
theorem stage_bounds {g a b dt ta tb : ℝ}
    (hg : g ∈ Set.Icc 0 1) (ha : a ∈ Set.Icc 0 1) (hb : b ∈ Set.Icc 0 1)
    (ht : 0 ≤ dt) (hta : 0 < ta) (htb : 0 < tb) :
    advance g a b (dt / 2 * (1 / ta + 1 / tb)) ∈ Set.Icc 0 1 := by
  let z := dt / 2 * (1 / ta + 1 / tb)
  have hz : 0 ≤ z := by dsimp [z]; positivity
  obtain ⟨hl, hu⟩ := lag_bounds hz
  have he := (Real.exp_pos (-z)).le
  have hw := sub_nonneg.mpr hu
  change advance g a b z ∈ Set.Icc 0 1
  unfold advance
  constructor
  · nlinarith only [mul_nonneg hg.1 he, mul_nonneg ha.1 hw, mul_nonneg hb.1 hl]
  · nlinarith only [mul_nonneg (sub_nonneg.mpr hg.2) he, mul_nonneg (sub_nonneg.mpr ha.2) hw,
      mul_nonneg (sub_nonneg.mpr hb.2) hl]

/-- At a held target the gate's residual is exactly the original residual times exp(−z). -/
theorem clamped_residual (g a z : ℝ) :
    advance g a a z - a = (g - a) * Real.exp (-z) := by unfold advance; ring

end

end CellsProofs.Transport.ChannelStep
