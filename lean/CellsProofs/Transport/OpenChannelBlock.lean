import CellsProofs.Chemistry.SingleSiteBinding
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Analysis.Calculus.Deriv.Add
import Mathlib.Analysis.Calculus.Deriv.Inv
import Mathlib.Analysis.SpecialFunctions.ExpDeriv
import Mathlib.Tactic.Ring

/-! The equilibrium blocker in FR-51. Concentrations use mM and reference voltage uses V.
Each signed exponent coefficient includes the side, charge sign and thermal factor.
Weights and the blocker concentration are held fixed when differentiating. -/

namespace CellsProofs.Transport.OpenChannelBlock

open CellsProofs.Chemistry.SingleSite (occupancy)

noncomputable section

structure Mode where
  weight : ℝ
  k0 : ℝ
  perVolt : ℝ

def dissociation (m : Mode) (v : ℝ) : ℝ := m.k0 * Real.exp (m.perVolt * v)

/-- The engine forms the free fraction directly, including under strong block. -/
def free (c k : ℝ) : ℝ := k / (c + k)

private theorem dissociation_pos (m : Mode) (hk : 0 < m.k0) (v : ℝ) :
    0 < dissociation m v := mul_pos hk (Real.exp_pos _)

theorem mode_hasDerivAt (m : Mode) {c : ℝ} (hc : 0 ≤ c) (hk : 0 < m.k0) (v : ℝ) :
    HasDerivAt (fun x => free c (dissociation m x))
      (m.perVolt * (occupancy c (dissociation m v) * free c (dissociation m v))) v := by
  have he : HasDerivAt (fun x : ℝ => m.perVolt * x) m.perVolt v := by
    simpa using (hasDerivAt_id v).const_mul m.perVolt
  have hd : HasDerivAt (dissociation m) (dissociation m v * m.perVolt) v := by
    simpa [dissociation, mul_assoc] using he.exp.const_mul m.k0
  have hpos := add_pos_of_nonneg_of_pos hc (dissociation_pos m hk v)
  convert hd.div (hd.const_add c) hpos.ne' using 1
  dsimp [free, occupancy]
  rw [add_comm (dissociation m v) c]
  field_simp [hpos.ne']
  ring

variable {ι : Type*} [Fintype ι]

def unblocked (m : ι → Mode) (c v : ℝ) : ℝ :=
  (∑ i, (m i).weight * free c (dissociation (m i) v)) / ∑ i, (m i).weight

def slopeBound (m : ι → Mode) (c v : ℝ) : ℝ :=
  (∑ i, (m i).weight * |(m i).perVolt| *
    (occupancy c (dissociation (m i) v) * free c (dissociation (m i) v))) / ∑ i, (m i).weight

/-- Normalization uses the actual sum of weights, which need only be positive. -/
theorem unblocked_mem_unit (m : ι → Mode) {c : ℝ} (hc : 0 ≤ c)
    (hk : ∀ i, 0 < (m i).k0) (hw : ∀ i, 0 ≤ (m i).weight)
    (hs : 0 < ∑ i, (m i).weight) (v : ℝ) : unblocked m c v ∈ Set.Icc 0 1 := by
  have hfree (i : ι) : free c (dissociation (m i) v) ∈ Set.Icc 0 1 := by
    have hp := dissociation_pos (m i) (hk i) v
    have hd := add_pos_of_nonneg_of_pos hc hp
    exact ⟨div_nonneg hp.le hd.le, (div_le_one hd).2 (le_add_of_nonneg_left hc)⟩
  refine ⟨div_nonneg (Finset.sum_nonneg (fun i _ => mul_nonneg (hw i) (hfree i).1)) hs.le, ?_⟩
  apply (div_le_one hs).2
  exact Finset.sum_le_sum fun i _ => by
    simpa using mul_le_mul_of_nonneg_left (hfree i).2 (hw i)

theorem zero_blocker (m : ι → Mode) (hk : ∀ i, 0 < (m i).k0)
    (hs : 0 < ∑ i, (m i).weight) (v : ℝ) :
    unblocked m 0 v = 1 ∧ slopeBound m 0 v = 0 := by
  have h (i : ι) := (dissociation_pos (m i) (hk i) v).ne'
  simp [unblocked, slopeBound, free, occupancy, h, hs.ne']

theorem unblocked_hasDerivAt (m : ι → Mode) {c : ℝ} (hc : 0 ≤ c)
    (hk : ∀ i, 0 < (m i).k0) (v : ℝ) :
    HasDerivAt (unblocked m c)
      ((∑ i, (m i).weight * ((m i).perVolt *
        (occupancy c (dissociation (m i) v) * free c (dissociation (m i) v)))) /
        ∑ i, (m i).weight) v := by
  exact (HasDerivAt.sum fun i _ => (mode_hasDerivAt (m i) hc (hk i) v).const_mul
    (m i).weight).div_const _

/-- Pointwise bound used by the voltage and concentration terms on a channel population. -/
theorem abs_deriv_le_slopeBound (m : ι → Mode) {c : ℝ} (hc : 0 ≤ c)
    (hk : ∀ i, 0 < (m i).k0) (hw : ∀ i, 0 ≤ (m i).weight)
    (hs : 0 < ∑ i, (m i).weight) (v : ℝ) : |deriv (unblocked m c) v| ≤ slopeBound m c v := by
  rw [(unblocked_hasDerivAt m hc hk v).deriv, abs_div, abs_of_pos hs]
  apply div_le_div_of_nonneg_right _ hs.le
  apply (Finset.abs_sum_le_sum_abs _ _).trans
  apply Finset.sum_le_sum
  intro i _
  have hp := (dissociation_pos (m i) (hk i) v).le
  have ho : 0 ≤ occupancy c (dissociation (m i) v) := div_nonneg hc (add_nonneg hp hc)
  have hf : 0 ≤ free c (dissociation (m i) v) := div_nonneg hp (add_nonneg hc hp)
  simp [abs_mul, abs_of_nonneg (hw i), abs_of_nonneg ho, abs_of_nonneg hf, mul_assoc]

/-- A declared blocker has one side and one charge sign. Its mode slopes have a common
sign, so their contributions cannot cancel and the fraction bound is attained. -/
theorem abs_deriv_eq_slopeBound_of_common_sign (m : ι → Mode) {c : ℝ} (hc : 0 ≤ c)
    (hk : ∀ i, 0 < (m i).k0) (hw : ∀ i, 0 ≤ (m i).weight)
    (hs : 0 < ∑ i, (m i).weight) (v : ℝ)
    (side : (∀ i, 0 ≤ (m i).perVolt) ∨ (∀ i, (m i).perVolt ≤ 0)) :
    |deriv (unblocked m c) v| = slopeBound m c v := by
  rw [(unblocked_hasDerivAt m hc hk v).deriv, abs_div, abs_of_pos hs]
  unfold slopeBound
  congr 1
  have hp (i : ι) : 0 ≤ occupancy c (dissociation (m i) v) * free c (dissociation (m i) v) := by
    have hk' := (dissociation_pos (m i) (hk i) v).le
    exact mul_nonneg (div_nonneg hc (add_nonneg hk' hc)) (div_nonneg hk' (add_nonneg hc hk'))
  rcases side with h | h
  · rw [abs_of_nonneg (Finset.sum_nonneg fun i _ => mul_nonneg (hw i) (mul_nonneg (h i) (hp i)))]
    simp only [abs_of_nonneg (h _), mul_assoc]
  · rw [abs_of_nonpos (Finset.sum_nonpos fun i _ =>
        mul_nonpos_of_nonneg_of_nonpos (hw i) (mul_nonpos_of_nonpos_of_nonneg (h i) (hp i))),
        ← Finset.sum_neg_distrib]
    apply Finset.sum_congr rfl
    intro i _
    rw [abs_of_nonpos (h i)]
    ring

/-- The stage bound for blocked current assumes a valid bound `g` for the free current's
own derivative. With concentrations fixed, a reversal reference is a constant voltage offset. -/
theorem current_slope_bound (m : ι → Mode) {c : ℝ} (hc : 0 ≤ c) (hk : ∀ i, 0 < (m i).k0)
    (hw : ∀ i, 0 ≤ (m i).weight) (hs : 0 < ∑ i, (m i).weight)
    (current : ℝ → ℝ) (e v d g : ℝ) (hi : HasDerivAt current d v) (hg : |d| ≤ g) :
    |deriv (fun x => unblocked m c (x - e) * current x) v| ≤
      unblocked m c (v - e) * g + |current v| * slopeBound m c (v - e) := by
  have hu := (unblocked_hasDerivAt m hc hk (v - e)).differentiableAt.hasDerivAt
  have ht : HasDerivAt (fun x : ℝ => x - e) 1 v := (hasDerivAt_id v).sub_const e
  have hd : HasDerivAt (fun x => unblocked m c (x - e)) (deriv (unblocked m c) (v - e)) v := by
    simpa [Function.comp_def] using hu.comp v ht
  rw [(hd.mul hi).deriv]
  have hn := (unblocked_mem_unit m hc hk hw hs (v - e)).1
  calc
    _ ≤ |deriv (unblocked m c) (v - e) * current v| + |unblocked m c (v - e) * d| := abs_add_le _ _
    _ ≤ slopeBound m c (v - e) * |current v| + unblocked m c (v - e) * g := by
      rw [abs_mul, abs_mul, abs_of_nonneg hn]
      exact add_le_add
        (mul_le_mul_of_nonneg_right (abs_deriv_le_slopeBound m hc hk hw hs _) (abs_nonneg _))
        (mul_le_mul_of_nonneg_left hg hn)
    _ = _ := by ring

end

end CellsProofs.Transport.OpenChannelBlock
