import Mathlib.Algebra.BigOperators.Field
import Mathlib.Analysis.Calculus.DSlope
import Mathlib.Analysis.Convex.Slope
import Mathlib.Analysis.Convex.SpecificFunctions.Basic
import Mathlib.Analysis.SpecialFunctions.ExpDeriv
import Mathlib.Topology.Order.IntermediateValue
import Mathlib.Tactic.Linarith

/-! # Survival of neutral labels over one physical step (FR-42) -/

namespace CellsProofs.Chemistry.ArrivalSurvival

open Filter Set
open scoped Topology

noncomputable section

/-- Fraction of a constant inflow still present at the end of a step with loss exponent `u`. -/
def phi (u : ℝ) : ℝ := if u = 0 then 1 else (1 - Real.exp (-u)) / u

/-- Total after the step, given the starting amount and gross arrivals during the step. -/
def endAmount (old arrived u : ℝ) : ℝ := old * Real.exp (-u) + arrived * phi u

theorem no_loss (old arrived : ℝ) : endAmount old arrived 0 = old + arrived := by
  simp [endAmount, phi]

theorem phi_pos {u : ℝ} (hu : 0 ≤ u) : 0 < phi u := by
  rcases hu.eq_or_lt with h | h
  · simp [← h, phi]
  · rw [phi, if_neg h.ne']
    exact div_pos (sub_pos.mpr (Real.exp_lt_one_iff.mpr (neg_lt_zero.mpr h))) h

private theorem phi_continuous : Continuous phi := by
  have he : Continuous (dslope Real.exp 0) := continuous_iff_continuousOn_univ.2 <|
    (continuousOn_dslope univ_mem).2 ⟨Real.continuous_exp.continuousOn, Real.differentiableAt_exp⟩
  have hf : phi = fun u => dslope Real.exp 0 (-u) := by
    funext u
    by_cases hz : u = 0
    · simp [hz, phi, Real.deriv_exp]
    · rw [phi, if_neg hz, dslope_of_ne _ (neg_ne_zero.mpr hz), slope_def_field]
      simp [sub_eq_add_neg, div_eq_mul_inv]
      ring
  rw [hf]
  exact he.comp continuous_neg

private theorem phi_decreases {u v : ℝ} (hu : 0 ≤ u) (h : u < v) : phi v < phi u := by
  have hv := hu.trans_lt h
  by_cases hz : u = 0
  · subst u
    simp only [phi, if_pos, if_neg hv.ne']
    apply (div_lt_iff₀ hv).2
    linarith [Real.add_one_lt_exp (neg_ne_zero.mpr hv.ne')]
  · have hp := lt_of_le_of_ne hu (Ne.symm hz)
    have secant := strictConvexOn_exp.secant_strict_mono_aux3 (mem_univ (-v))
      (mem_univ (0 : ℝ)) (neg_lt_neg h) (neg_neg_of_pos hp)
    simpa [phi, hz, hv.ne'] using secant

theorem endAmount_decreases {old arrived : ℝ} (ho : 0 ≤ old) (ha : 0 ≤ arrived)
    (total : 0 < old + arrived) : StrictAntiOn (endAmount old arrived) (Ici 0) := by
  intro u hu v _ huv
  have he := Real.exp_lt_exp.mpr (neg_lt_neg huv)
  have hp := phi_decreases hu huv
  by_cases hold : 0 < old
  · exact add_lt_add_of_lt_of_le (mul_lt_mul_of_pos_left he hold) (mul_le_mul_of_nonneg_left hp.le ha)
  · exact add_lt_add_of_le_of_lt (mul_le_mul_of_nonneg_left he.le ho)
      (mul_lt_mul_of_pos_left hp (by linarith))

private theorem endAmount_tends_to_zero (old arrived : ℝ) :
    Tendsto (endAmount old arrived) atTop (𝓝 0) := by
  have he := Real.tendsto_exp_neg_atTop_nhds_zero
  have hp : Tendsto phi atTop (𝓝 0) := by
    have ht := ((tendsto_const_nhds (x := (1 : ℝ))).sub he).mul tendsto_inv_atTop_zero
    apply (show Tendsto _ _ (𝓝 (0 : ℝ)) by simpa using ht).congr'
    filter_upwards [eventually_gt_atTop (0 : ℝ)] with u hu
    simp [phi, hu.ne', div_eq_mul_inv]
  simpa [endAmount] using (he.const_mul old).add (hp.const_mul arrived)

/-- Each positive endpoint up to the supply has exactly one nonnegative exponent.
At the upper endpoint the exponent is zero. A completely empty pool cannot identify a rate. -/
theorem survival_exponent_unique {old arrived target : ℝ} (ho : 0 ≤ old) (ha : 0 ≤ arrived)
    (ht : 0 < target) (hs : target ≤ old + arrived) :
    ∃! u : ℝ, 0 ≤ u ∧ endAmount old arrived u = target := by
  obtain ⟨b, hb, hbt⟩ := ((eventually_ge_atTop (0 : ℝ)).and
    ((endAmount_tends_to_zero old arrived).eventually_lt_const ht)).exists
  have hc : Continuous (endAmount old arrived) :=
    (continuous_const.mul (Real.continuous_exp.comp continuous_neg)).add
      (continuous_const.mul phi_continuous)
  obtain ⟨u, hu, hut⟩ := intermediate_value_Icc' hb hc.continuousOn
    (show target ∈ Icc (endAmount old arrived b) (endAmount old arrived 0) from
      ⟨hbt.le, (no_loss old arrived).symm ▸ hs⟩)
  refine ⟨u, ⟨hu.1, hut⟩, ?_⟩
  intro v hv
  exact (endAmount_decreases ho ha (ht.trans_le hs)).injOn hv.1 hu.1 (hv.2.trans hut.symm)

/-- Old members survive the entire step. Each label's arrivals use their mean survival. -/
def labelAmount (old share gained u : ℝ) : ℝ := old * Real.exp (-u) * share + gained * phi u

theorem labelAmount_nonneg {old share gained u : ℝ} (ho : 0 ≤ old) (hs : 0 ≤ share)
    (hg : 0 ≤ gained) (hu : 0 ≤ u) : 0 ≤ labelAmount old share gained u :=
  add_nonneg (mul_nonneg (mul_nonneg ho (Real.exp_pos _).le) hs) (mul_nonneg hg (phi_pos hu).le)

theorem empty_label (old u : ℝ) : labelAmount old 0 0 u = 0 := by simp [labelAmount]

theorem no_arrivals {old : ℝ} (ho : 0 < old) (share u : ℝ) :
    labelAmount old share 0 u / endAmount old 0 u = share := by
  simp only [labelAmount, endAmount, zero_mul, add_zero]
  exact mul_div_cancel_left₀ _ (mul_pos ho (Real.exp_pos _)).ne'

theorem sum_labelAmounts {ι : Type*} (labels : Finset ι) (shares gained : ι → ℝ)
    (old u : ℝ) (hs : ∑ i ∈ labels, shares i = 1) :
    ∑ i ∈ labels, labelAmount old (shares i) (gained i) u =
      endAmount old (∑ i ∈ labels, gained i) u := by
  simp only [labelAmount, endAmount, Finset.sum_add_distrib, ← Finset.mul_sum, ← Finset.sum_mul,
    hs, mul_one]

theorem sum_normalized {ι : Type*} (labels : Finset ι) (shares gained : ι → ℝ)
    (old u target : ℝ) (hs : ∑ i ∈ labels, shares i = 1) (ht : 0 < target)
    (fit : endAmount old (∑ i ∈ labels, gained i) u = target) :
    ∑ i ∈ labels, labelAmount old (shares i) (gained i) u / target = 1 := by
  rw [← Finset.sum_div, sum_labelAmounts labels shares gained old u hs, fit, div_self ht.ne']

end

end CellsProofs.Chemistry.ArrivalSurvival
