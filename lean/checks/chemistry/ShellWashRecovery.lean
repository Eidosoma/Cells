import CellsProofs.Chemistry.ShellWashRecovery

/-! Exact controls on a synthetic tracer population with rates 1 and 2 per second. -/

namespace CellsProofs.Checks.ShellWashRecovery

open CellsProofs.Chemistry.ShellWashRecovery

#print axioms mean_flux
#print axioms exterior_derivative
#print axioms unique_on_interval
#print axioms recovery_curve
#print axioms initial_recovery
#print axioms recovery_bounds
#print axioms withdrawal_mean
#print axioms removed_after_recovery

noncomputable section

private def τ : ℝ := Real.log 2 / 3

private theorem half_decay : Real.exp (-(3 * τ)) = 1 / 2 := by
  rw [show 3 * τ = Real.log 2 by unfold τ; ring, Real.exp_neg, Real.exp_log (by norm_num)]
  norm_num

private theorem first_read : exterior 1 2 0 9 τ = 3 := by
  rw [recovery_curve _ _ _ _ (by norm_num)]
  norm_num [half_decay]

private theorem second_read : exterior 1 2 0 9 (2 * τ) = 9 / 2 := by
  rw [recovery_curve _ _ _ _ (by norm_num)]
  norm_num only
  rw [show -(3 * (2 * τ)) = -(3 * τ) + -(3 * τ) by ring, Real.exp_add, half_decay]
  norm_num

-- The exterior starts empty after a full wash even though the right derivative is positive.
example : exterior 1 2 0 9 0 = 0 ∧
    HasDerivWithinAt (exterior 1 2 0 9) 18 (Set.Ici 0) 0 := by
  simpa only [show (2 : ℝ) * 9 = 18 by norm_num] using initial_recovery 1 2 9

-- The order of the rates matters. Two entry events per unit time and one exit give a different read.
example : exterior 2 1 0 9 τ ≠ exterior 1 2 0 9 τ := by
  rw [first_read, recovery_curve _ _ _ _ (by norm_num)]
  norm_num [half_decay]

-- No retained tracer, no exit, and a completely impermeable wall.
example (t : ℝ) : exterior 1 2 0 0 t = 0 ∧ exterior 1 0 0 9 t = 0 ∧ exterior 0 0 4 9 t = 4 := by
  simp [CellsProofs.Chemistry.ShellWashRecovery.exterior, CellsProofs.Chemistry.SpeciesTurnover.amount,
    CellsProofs.Chemistry.SpeciesTurnover.survival]

-- An ensemble concentrated equally at 0 and 9 has the second read's mean, 4.5.
-- Half-withdrawal must sample that exterior mean, giving 2.25 removed.
example : ∑ i : Bool, (1 / 2 : ℝ) * CellsProofs.Chemistry.PoolWithdrawal.wordAverage 4
    (2 / (4 : ℝ)) (if i then 9 else 0) (fun k => (k : ℝ)) = 9 / 4 := by
  have mean : ∑ i : Bool, (1 / 2 : ℝ) * ((if i then 9 else 0 : ℕ) : ℝ) =
      exterior 1 2 0 9 (2 * τ) := by
    rw [second_read]
    norm_num [Fintype.sum_bool]
  have drawn := removed_after_recovery (fun _ : Bool => 1 / 2) (fun i => if i then 9 else 0)
    (by decide : 0 < 4) 2 (by decide) 1 2 9 (2 * τ) (by norm_num) mean
  rw [← recovery_curve 1 2 9 _ (by norm_num), second_read] at drawn
  norm_num at drawn ⊢
  exact drawn

end

end CellsProofs.Checks.ShellWashRecovery
