import CellsProofs.Chemistry.PoolWithdrawal
import CellsProofs.Chemistry.SpeciesTurnover
import Mathlib.Analysis.ODE.Gronwall

/-! # Tracer recovery in a finite exterior pool after a wash

Entry moves a molecule from the exterior to the lumen. Exit moves it back.
Both per-molecule rates are constant between washes. Removed tracer never
returns. The mean counts may therefore sum to less than the initial loading. -/

namespace CellsProofs.Chemistry.ShellWashRecovery

noncomputable section

/-- Net gain of the exterior pool, in molecules per second. -/
def flux (entry leave pool lumen : ℝ) : ℝ := leave * lumen - entry * pool

/-- Sum the two-state forward equation for each tracer's exterior probability.
The remaining probability may include tracer removed by earlier washes. -/
theorem mean_flux {I : Type*} [Fintype I] (entry leave : ℝ) (pool lumen : I → ℝ → ℝ)
    {s : Set ℝ} {t : ℝ}
    (moves : ∀ i, HasDerivWithinAt (pool i) (flux entry leave (pool i t) (lumen i t)) s t) :
    HasDerivWithinAt (fun u => ∑ i, pool i u)
      (flux entry leave (∑ i, pool i t) (∑ i, lumen i t)) s t := by
  simpa only [flux, Finset.mul_sum, Finset.sum_sub_distrib] using
    (HasDerivWithinAt.sum (u := Finset.univ) (fun i _ => moves i))

/-- Exterior mean at elapsed time t, starting with mean counts pool and lumen. -/
def exterior (entry leave pool lumen : ℝ) : ℝ → ℝ :=
  SpeciesTurnover.amount pool (leave * (pool + lumen)) (entry + leave)

/-- The complement of the exterior mean supplies the returning tracer in the finite bath. -/
theorem exterior_derivative (entry leave pool lumen t : ℝ) :
    HasDerivAt (exterior entry leave pool lumen)
      (flux entry leave (exterior entry leave pool lumen t)
        (pool + lumen - exterior entry leave pool lumen t)) t := by
  unfold exterior flux
  convert SpeciesTurnover.amount_derivative pool (leave * (pool + lumen)) (entry + leave) t
    using 1
  ring

/-- The first-order flux and the post-wash initial count determine the entire interval.
Right derivatives allow a jump from the previous interval at time zero. -/
theorem unique_on_interval (entry leave pool lumen T : ℝ) (x : ℝ → ℝ)
    (continuous : ContinuousOn x (Set.Icc 0 T)) (start : x 0 = pool)
    (moves : ∀ t ∈ Set.Ico 0 T,
      HasDerivWithinAt x (flux entry leave (x t) (pool + lumen - x t)) (Set.Ici t) t) :
    Set.EqOn x (exterior entry leave pool lumen) (Set.Icc 0 T) := by
  have lip : LipschitzWith ‖entry + leave‖₊ (fun z => flux entry leave z (pool + lumen - z)) := by
    apply LipschitzWith.of_dist_le_mul
    intro a b
    simp only [Real.dist_eq, coe_nnnorm, Real.norm_eq_abs]
    rw [show flux entry leave a (pool + lumen - a) - flux entry leave b (pool + lumen - b) =
      -((entry + leave) * (a - b)) by unfold flux; ring, abs_neg, abs_mul]
  exact ODE_solution_unique (v := fun _ z => flux entry leave z (pool + lumen - z))
    (fun _ => lip) continuous moves
    (fun t _ => (exterior_derivative entry leave pool lumen t).continuousAt.continuousWithinAt)
    (fun t _ => (exterior_derivative entry leave pool lumen t).hasDerivWithinAt)
    (start.trans (SpeciesTurnover.initial_amount _ _ _).symm)

/-- After a complete exterior replacement only initially retained lumen tracer can reappear. -/
theorem recovery_curve (entry leave lumen t : ℝ) (active : entry + leave ≠ 0) :
    exterior entry leave 0 lumen t =
      leave * lumen / (entry + leave) * (1 - Real.exp (-((entry + leave) * t))) := by
  simp only [exterior, SpeciesTurnover.amount, SpeciesTurnover.exposure, if_neg active,
    SpeciesTurnover.survival, zero_mul, zero_add]
  ring

/-- At the wash the fresh exterior is empty and its right derivative is the exit rate times
the retained lumen mean. -/
theorem initial_recovery (entry leave lumen : ℝ) :
    exterior entry leave 0 lumen 0 = 0 ∧
    HasDerivWithinAt (exterior entry leave 0 lumen) (leave * lumen) (Set.Ici 0) 0 := by
  have h : exterior entry leave 0 lumen 0 = 0 := SpeciesTurnover.initial_amount _ _ _
  refine ⟨h, ?_⟩
  simpa [flux, h] using
    (exterior_derivative entry leave 0 lumen 0).hasDerivWithinAt (s := Set.Ici 0)

/-- Positive retained tracer reappears at every positive time and stays below its limiting
exterior count during each finite wash-free interval. -/
theorem recovery_bounds {entry leave lumen t : ℝ} (hin : 0 ≤ entry) (hout : 0 < leave)
    (retained : 0 < lumen) (elapsed : 0 < t) :
    0 < exterior entry leave 0 lumen t ∧
    exterior entry leave 0 lumen t < leave * lumen / (entry + leave) := by
  have total := add_pos_of_nonneg_of_pos hin hout
  have scale := div_pos (mul_pos hout retained) total
  rw [recovery_curve _ _ _ _ total.ne']
  have decay : Real.exp (-((entry + leave) * t)) < 1 :=
    Real.exp_lt_one_iff.mpr (neg_neg_of_pos (mul_pos total elapsed))
  exact ⟨mul_pos scale (sub_pos.mpr decay), mul_lt_of_lt_one_right scale
    (sub_lt_self _ (Real.exp_pos _))⟩

/-- On the engine's word grid, the next withdrawal removes f times the exterior mean.
Condition on each possible pre-withdrawal count, then average over the ensemble. -/
theorem withdrawal_mean {S : Type*} [Fintype S] (weight : S → ℝ) (count : S → ℕ)
    {bins : ℕ} (positive : 0 < bins) (j : ℕ) (inRange : j ≤ bins) :
    ∑ i, weight i * PoolWithdrawal.wordAverage bins (j / (bins : ℝ)) (count i) (fun k => (k : ℝ)) =
      (j / (bins : ℝ)) * ∑ i, weight i * (count i : ℝ) := by
  have cap : (j : ℝ) / bins ≤ 1 := (div_le_one (by exact_mod_cast positive)).mpr
    (by exact_mod_cast inRange)
  have each (n : ℕ) := (PoolWithdrawal.withdrawn_moments positive cap n).1
  rw [Finset.mul_sum]
  apply Finset.sum_congr rfl
  intro i _
  rw [each, PoolWithdrawal.probability_on_grid positive j]
  ring

/-- A later withdrawal samples the exterior tracer that has returned since replacement.
The formula allows different counts in different realizations of the same experiment. -/
theorem removed_after_recovery {S : Type*} [Fintype S] (weight : S → ℝ) (count : S → ℕ)
    {bins : ℕ} (positive : 0 < bins) (j : ℕ) (inRange : j ≤ bins)
    (entry leave lumen t : ℝ) (active : entry + leave ≠ 0)
    (exteriorMean : ∑ i, weight i * (count i : ℝ) = exterior entry leave 0 lumen t) :
    ∑ i, weight i * PoolWithdrawal.wordAverage bins (j / (bins : ℝ)) (count i) (fun k => (k : ℝ)) =
      (j / (bins : ℝ)) * (leave * lumen / (entry + leave) *
        (1 - Real.exp (-((entry + leave) * t)))) := by
  rw [withdrawal_mean weight count positive j inRange, exteriorMean, recovery_curve _ _ _ _ active]

end

end CellsProofs.Chemistry.ShellWashRecovery
