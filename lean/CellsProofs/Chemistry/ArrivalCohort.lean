import Mathlib.Algebra.BigOperators.Field
import Mathlib.Analysis.Calculus.Deriv.Add
import Mathlib.Analysis.Calculus.Deriv.Inv
import Mathlib.Analysis.Calculus.Deriv.Mul
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Ring

/-! # Passive arrival-time cohorts of a well-mixed physical population (FR-42) -/

namespace CellsProofs.Chemistry.ArrivalCohort

noncomputable section

/-- An occupied pool allocates its one physical loss by amount. An empty pool allocates zero. -/
def share (amount total loss : ℝ) : ℝ := if total = 0 then 0 else loss * amount / total

theorem empty_label (total loss : ℝ) : share 0 total loss = 0 := by simp [share]

/-- Labels, including the unlabelled remainder, account for the whole physical loss. -/
theorem sum_shares {ι : Type*} (labels : Finset ι) (amount : ι → ℝ)
    (loss : ℝ → ℝ) (empty : loss 0 = 0) :
    let total := ∑ i ∈ labels, amount i
    ∑ i ∈ labels, share (amount i) total (loss total) = loss total := by
  dsimp only
  by_cases h : (∑ i ∈ labels, amount i) = 0
  · simp [share, h, empty]
  · simp only [share, h, if_false]
    rw [← Finset.sum_div, ← Finset.mul_sum]
    exact mul_div_cancel_right₀ _ h

/-- Removing each share for one step gives the same total as removing the physical loss once.
This is an accounting identity for the specified step size. -/
theorem step_total {ι : Type*} (labels : Finset ι) (amount : ι → ℝ)
    (loss : ℝ → ℝ) (empty : loss 0 = 0) (dt : ℝ) :
    let total := ∑ i ∈ labels, amount i
    ∑ i ∈ labels, (amount i - dt * share (amount i) total (loss total)) =
      total - dt * loss total := by
  dsimp only
  rw [Finset.sum_sub_distrib, ← Finset.mul_sum, sum_shares labels amount loss empty]

/-- Any readout evaluated on just the physical totals before and after this step agrees
after grouping the labels. This assumption matters for energy and heat. -/
theorem pooled_readout {ι α : Type*} (labels : Finset ι) (amount : ι → ℝ)
    (loss : ℝ → ℝ) (empty : loss 0 = 0) (dt : ℝ) (readout : ℝ → ℝ → α) :
    let total := ∑ i ∈ labels, amount i
    readout total (∑ i ∈ labels, (amount i - dt * share (amount i) total (loss total))) =
      readout total (total - dt * loss total) :=
  congrArg (readout (∑ i ∈ labels, amount i)) (step_total labels amount loss empty dt)

/-- A quadratic loss on the physical pool gives each label a per-unit loss rate of N. -/
theorem quadratic_share (total amount : ℝ) : share amount total (total^2) = total * amount := by
  by_cases h : total = 0
  · simp [share, h]
  · simp only [share, h, if_false]
    apply (div_eq_iff h).2
    ring

/-- Amount still present from an initial cohort of size b in a pool starting at a,
under quadratic physical loss and with no further arrivals. -/
def remaining (a b t : ℝ) : ℝ := b / (1 + a * t)

theorem remaining_initial (a b : ℝ) : remaining a b 0 = b := by simp [remaining]

/-- The survivor curve solves n' = -N n. Setting b = a gives the physical N' = -N².
The denominator is positive throughout the physical domain a,t ≥ 0. -/
theorem remaining_derivative {a b t : ℝ} (h : 1 + a * t ≠ 0) :
    HasDerivAt (remaining a b) (-(remaining a a t) * remaining a b t) t := by
  have hd : HasDerivAt (fun x : ℝ => 1 + a * x) a t := by
    simpa using (hasDerivAt_const t (1 : ℝ)).add ((hasDerivAt_id t).const_mul a)
  convert (hasDerivAt_const t b).div hd h using 1
  dsimp [remaining]
  field_simp [h]
  ring

/-- At one time unit the labelled survivor and the difference from an independent blank
are distinct observables. Computing losses separately also changes the initial rate. -/
theorem quadratic_example :
    (3 : ℝ)^2 = 9 ∧ (2 : ℝ)^2 + 1^2 = 5 ∧
    remaining 3 3 1 = 3/4 ∧ remaining 3 1 1 = 1/4 ∧
    remaining 2 2 1 = 2/3 ∧ remaining 3 3 1 - remaining 2 2 1 = 1/12 := by
  norm_num [remaining]

end

end CellsProofs.Chemistry.ArrivalCohort
