import CellsProofs.Chemistry.ShellEquilibrium

open CellsProofs.Chemistry.ShellEquilibrium
open CellsProofs.Chemistry.PoolWithdrawalEnergy (mass)

-- An undeclared lumen uses the solution potential, including a nonzero one.
example (solution : ℝ) : lumenFraction solution solution = 1 / 2 := by
  norm_num [lumenFraction]

-- With a solution potential of log 2 and an absolute lumen potential of log 4,
-- the true gap is log 2. Reading the lumen value as the gap gives log 4.
private theorem correct_fraction :
    lumenFraction (Real.log 2) (Real.log 2 + Real.log 2) = 1 / 3 := by
  norm_num [lumenFraction, Real.exp_log (by norm_num : (0 : ℝ) < 2)]

example : lumenFraction 0 (Real.log 2 + Real.log 2) = 1 / 5 := by
  norm_num [lumenFraction, Real.exp_add, Real.exp_log (by norm_num : (0 : ℝ) < 2)]

-- Reversing the same gap puts two thirds inside.
example : lumenFraction (Real.log 2 + Real.log 2) (Real.log 2) = 2 / 3 := by
  calc
    _ = lumenFraction (Real.log 2) 0 := by
      simpa only [zero_add] using common_shift (Real.log 2) 0 (Real.log 2)
    _ = _ := by norm_num [lumenFraction, Real.exp_neg, Real.exp_log (by norm_num : (0 : ℝ) < 2)]

-- When the pool is empty of tracer as well, the single allowed count has mass one.
example (solution lumen : ℝ) : ((countLaw solution lumen 0) 0).toReal = 1 := by
  rw [count_mass]
  simp [mass]

-- Check all occupancies, including both endpoints, for two conserved molecules.
example :
    let π := countLaw (Real.log 2) (Real.log 2 + Real.log 2) 2
    (π 0).toReal = 4 / 9 ∧ (π 1).toReal = 4 / 9 ∧ (π 2).toReal = 1 / 9 := by
  dsimp only
  simp only [count_mass, correct_fraction, mass]
  norm_num [Nat.choose]

-- For the same preparation, mean concentrations have ratio one half.
example {n : ℕ} (hn : 0 < n) :
    let m := meanInside (Real.log 2) (Real.log 2 + Real.log 2) n
    m / (n - m) = 1 / 2 := by
  dsimp only
  rw [mean_concentration_ratio _ _ hn]
  norm_num [Real.exp_neg, Real.exp_log (by norm_num : (0 : ℝ) < 2)]

#print axioms common_shift
#print axioms inside_outside_odds
#print axioms countLaw_normalized
#print axioms count_mass
#print axioms detailed_balance
#print axioms stationary
#print axioms mean_inside_count
#print axioms mean_concentration_ratio
