import Mathlib.Analysis.SpecialFunctions.Log.NegMulLog
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Ring

/-! # Free energy from completion to RNA release

The terminal hold and each product fate have the same standard energy per RNA.
Only the receiving row has a concentration-dependent energy. Its capacity here
is volume times the standard concentration, in the same units as the amount.
-/

namespace CellsProofs.Chemistry.ReleaseEnergy

open Finset
open scoped BigOperators
noncomputable section

def ideal (x : ℝ) : ℝ := x * Real.log x - x

def rowEnergy (rt cap n : ℝ) : ℝ := rt * cap * ideal (n / cap)

/-- Per-molecule change in the concentration term, including an unchanged fate row. -/
def slope (rt cap a b : ℝ) : ℝ :=
  if a = b then rt * Real.log (a / cap) else (rowEnergy rt cap b - rowEnergy rt cap a) / (b - a)

def heat (rt cap a b detached : ℝ) : ℝ := -(detached * slope rt cap a b)

theorem ideal_antitone : AntitoneOn ideal (Set.Ioc 0 1) := by
  have hd (x : ℝ) (hx : 0 < x) : HasDerivAt ideal (Real.log x) x := by
    simpa [ideal] using (Real.hasDerivAt_mul_log hx.ne').sub (hasDerivAt_id x)
  apply antitoneOn_of_hasDerivWithinAt_nonpos (f' := Real.log) (convex_Ioc 0 1)
  · exact fun x hx => (hd x hx.1).continuousAt.continuousWithinAt
  · exact fun x hx => (hd x (interior_subset hx).1).hasDerivWithinAt
  · exact fun x hx => Real.log_nonpos (interior_subset hx).1.le (interior_subset hx).2

theorem slope_change (rt cap a b : ℝ) :
    slope rt cap a b * (b - a) = rowEnergy rt cap b - rowEnergy rt cap a := by
  by_cases h : a = b
  · simp [h]
  · simp [slope, h, sub_ne_zero.mpr (Ne.symm h)]

/-- Both endpoint concentrations lie in the active release domain. The net row move can have
either sign because degradation may draw from the same row during a release. -/
theorem slope_nonpos {rt cap a b : ℝ} (hrt : 0 ≤ rt) (hc : 0 < cap)
    (ha : a ∈ Set.Ioc 0 cap) (hb : b ∈ Set.Ioc 0 cap) : slope rt cap a b ≤ 0 := by
  have norm {n : ℝ} (hn : n ∈ Set.Ioc 0 cap) : n / cap ∈ Set.Ioc 0 1 :=
    ⟨div_pos hn.1 hc, (div_le_one hc).mpr hn.2⟩
  have dec {u v : ℝ} (hu : u ∈ Set.Ioc 0 cap) (hv : v ∈ Set.Ioc 0 cap) (h : u ≤ v) :
      rowEnergy rt cap v ≤ rowEnergy rt cap u :=
    mul_le_mul_of_nonneg_left (ideal_antitone (norm hu) (norm hv) (div_le_div_of_nonneg_right h hc.le))
      (mul_nonneg hrt hc.le)
  rcases lt_trichotomy a b with h | h | h
  · simpa [slope, h.ne] using div_nonpos_of_nonpos_of_nonneg (sub_nonpos.mpr (dec ha hb h.le))
      (sub_nonneg.mpr h.le)
  · simpa [slope, h] using mul_nonpos_of_nonneg_of_nonpos hrt
      (Real.log_nonpos (norm hb).1.le (norm hb).2)
  · simpa [slope, h.ne'] using div_nonpos_of_nonneg_of_nonpos (sub_nonneg.mpr (dec hb ha h.le))
      (sub_nonpos.mpr h.le)

/-- Each nonnegative detachment extent books nonnegative heat in the release domain. -/
theorem heat_nonneg {rt cap a b q : ℝ} (hrt : 0 ≤ rt) (hc : 0 < cap)
    (ha : a ∈ Set.Ioc 0 cap) (hb : b ∈ Set.Ioc 0 cap) (hq : 0 ≤ q) :
    0 ≤ heat rt cap a b q := neg_nonneg.mpr (mul_nonpos_of_nonneg_of_nonpos hq (slope_nonpos hrt hc ha hb))

/-- An inactive fate has zero release heat even when another route changes its amount. -/
theorem zero_release (rt cap a b : ℝ) : heat rt cap a b 0 = 0 := by simp [heat]

theorem split_heat_nonneg {rt cap a b x y p q : ℝ} (hrt : 0 ≤ rt) (hc : 0 < cap)
    (ha : a ∈ Set.Ioc 0 cap) (hb : b ∈ Set.Ioc 0 cap) (hx : x ∈ Set.Ioc 0 cap)
    (hy : y ∈ Set.Ioc 0 cap) (hp : p ∈ Set.Icc 0 1) (hq : 0 ≤ q) :
    0 ≤ heat rt cap a b (p * q) ∧ 0 ≤ heat rt cap x y ((1 - p) * q) :=
  ⟨heat_nonneg hrt hc ha hb (mul_nonneg hp.1 hq),
   heat_nonneg hrt hc hx hy (mul_nonneg (sub_nonneg.mpr hp.2) hq)⟩

/-- The total energy change and the heats of synthesis, detachment and degradation sum to zero.
`standard` is the common energy per held or free RNA. `chainRest` and `lossProducts` are the
changes outside the hold and fate rows due to synthesis and degradation, respectively. -/
theorem booking_balance {ι : Type*} (rows : Finset ι) (rt cap standard arrivals chainRest lossProducts : ℝ)
    (a b released lost : ι → ℝ) (update : ∀ i ∈ rows, b i - a i = released i - lost i) :
    chainRest + standard * (arrivals - ∑ i ∈ rows, released i) +
      (∑ i ∈ rows, (standard * (b i - a i) + (rowEnergy rt cap (b i) - rowEnergy rt cap (a i)))) +
      lossProducts - (chainRest + standard * arrivals) +
      (∑ i ∈ rows, heat rt cap (a i) (b i) (released i)) -
      (lossProducts - ∑ i ∈ rows, (standard + slope rt cap (a i) (b i)) * lost i) = 0 := by
  have one (i : ι) (hi : i ∈ rows) :
      standard * (b i - a i) + (rowEnergy rt cap (b i) - rowEnergy rt cap (a i)) =
      standard * released i - (standard + slope rt cap (a i) (b i)) * lost i -
        heat rt cap (a i) (b i) (released i) := by
    rw [← slope_change, update i hi]
    unfold heat
    ring
  rw [sum_congr rfl one]
  simp only [sum_sub_distrib, ← mul_sum]
  ring

end
end CellsProofs.Chemistry.ReleaseEnergy
