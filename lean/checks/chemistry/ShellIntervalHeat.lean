import CellsProofs.Chemistry.ShellIntervalHeat

namespace CellsProofs.Checks.ShellIntervalHeat

open CellsProofs.Chemistry.ShellIntervalHeat
open CellsProofs.Chemistry.ShellWashRecovery (exterior recovery_curve)

#print axioms site_continuous
#print axioms site_zero
#print axioms shell_rate_balance
#print axioms energy_derivative
#print axioms energy_antitone
#print axioms postwash_heat_nonneg
#print axioms impermeable_heat
#print axioms one_molecule_bias

noncomputable section

-- With equal rates, two retained tracers give half a molecule outside at this time.
example : exterior 1 1 0 2 (Real.log 2 / 2) = 1 / 2 := by
  rw [recovery_curve _ _ _ _ (by norm_num)]
  rw [show (1 + 1) * (Real.log 2 / 2) = Real.log 2 by ring, Real.exp_neg,
    Real.exp_log (by norm_num)]
  norm_num

private def correct := energy 0 0 2 0 - energy 0 0 2 (1/2)
private def planted := site 0 1 + site 0 2 - energy 0 0 2 (1/2)

private theorem correct_value : correct = 4 * Real.log 2 - 3 / 2 * Real.log 3 := by
  unfold correct energy site CellsProofs.Chemistry.ReleaseEnergy.ideal
  norm_num only
  rw [Real.log_div (by norm_num : (3 : ℝ) ≠ 0) (by norm_num : (2 : ℝ) ≠ 0),
    Real.log_div (by norm_num : (1 : ℝ) ≠ 0) (by norm_num : (2 : ℝ) ≠ 0)]
  simp only [Real.log_one, zero_sub, zero_mul, mul_zero, sub_zero, zero_add, add_zero]
  ring

-- Both answers are strictly positive, but the planted one is exactly one k_BT low.
example : 0 < planted ∧ correct - planted = 1 := by
  have bias : planted - correct = -1 := by
    simpa [planted, correct] using one_molecule_bias 0 0 2 (1/2)
  have bound : 2 < Real.log (256 / 27) := by
    have lower := Real.one_sub_inv_le_log_of_pos (by norm_num : (0 : ℝ) < 5/4)
    have cmp := Real.log_lt_log (by norm_num : (0 : ℝ) < (5/4 : ℝ)^10)
      (by norm_num : (5/4 : ℝ)^10 < 256/27)
    rw [Real.log_pow] at cmp
    norm_num only [Nat.cast_ofNat, inv_div, sub_div', one_mul, Nat.reduceMul] at lower cmp
    linarith
  rw [Real.log_div (by norm_num) (by norm_num),
    show (256 : ℝ) = 2^8 by norm_num, show (27 : ℝ) = 3^3 by norm_num,
    Real.log_pow, Real.log_pow] at bound
  norm_num only [Nat.cast_ofNat] at bound
  constructor <;> linarith [correct_value]

-- The registered substitution includes the standard-potential and volume terms.
-- For coefficient one the wrong term happens to be zero as well.
example (b total finish : ℝ) :
    (site (-2) 1 + site b total - energy (-2) b total finish) -
      (energy (-2) b total 0 - energy (-2) b total finish) = -3 ∧
    (site 1 1 + site b total - energy 1 b total finish) =
      (energy 1 b total 0 - energy 1 b total finish) := by
  constructor
  · exact (one_molecule_bias (-2) b total finish).trans (by norm_num)
  · linarith [one_molecule_bias 1 b total finish]

end

end CellsProofs.Checks.ShellIntervalHeat
