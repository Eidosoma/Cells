import CellsProofs.Chemistry.PoolWithdrawalEnergy

/-! # One conserved tracer across a prescribed shell

At equal, fixed lumen and solution volumes, the total entry rate is the number
outside times a common per-molecule rate. On the same edge the exit
rate uses the number inside after entry and the factor exp(μ°lumen − μ°solution).
Both standard potentials are already in units of RT. -/

namespace CellsProofs.Chemistry.ShellEquilibrium

open PoolWithdrawalEnergy (mass binomial_mass)

noncomputable section

/-- Equilibrium probability that a molecule is in the lumen. -/
def lumenFraction (solution lumen : ℝ) : ℝ := (1 + Real.exp (lumen - solution))⁻¹

theorem fraction_bounds (solution lumen : ℝ) :
    0 < lumenFraction solution lumen ∧ lumenFraction solution lumen < 1 := by
  have h : 1 < 1 + Real.exp (lumen - solution) := lt_add_of_pos_right _ (Real.exp_pos _)
  exact ⟨inv_pos.mpr (zero_lt_one.trans h), inv_lt_one_of_one_lt₀ h⟩

theorem common_shift (solution lumen shift : ℝ) :
    lumenFraction (solution + shift) (lumen + shift) = lumenFraction solution lumen := by
  simp [lumenFraction]

private theorem outside_fraction (solution lumen : ℝ) :
    1 - lumenFraction solution lumen = lumenFraction solution lumen * Real.exp (lumen - solution) := by
  unfold lumenFraction
  field_simp [show 1 + Real.exp (lumen - solution) ≠ 0 by positivity]

theorem inside_outside_odds (solution lumen : ℝ) :
    lumenFraction solution lumen / (1 - lumenFraction solution lumen) =
      Real.exp (-(lumen - solution)) := by
  rw [outside_fraction, Real.exp_neg]
  field_simp [(fraction_bounds solution lumen).1.ne']

/-- Mathlib's normalized binomial PMF, indexed by the lumen count from zero to n. -/
def countLaw (solution lumen : ℝ) (n : ℕ) : PMF (Fin (n + 1)) :=
  PMF.binomial (ENNReal.ofReal (lumenFraction solution lumen))
    (ENNReal.ofReal_le_one.mpr (fraction_bounds solution lumen).2.le) n

theorem countLaw_normalized (solution lumen : ℝ) (n : ℕ) :
    ∑ k, ((countLaw solution lumen n) k).toReal = 1 := by
  rw [← ENNReal.toReal_sum (fun k _ => (countLaw solution lumen n).apply_ne_top k),
    ← tsum_fintype, PMF.tsum_coe, ENNReal.toReal_one]

theorem count_mass (solution lumen : ℝ) (n : ℕ) (k : Fin (n + 1)) :
    ((countLaw solution lumen n) k).toReal = mass (lumenFraction solution lumen) (n - ↑k) k := by
  obtain ⟨k, hk⟩ := k
  obtain ⟨r, rfl⟩ := Nat.exists_eq_add_of_le' (Nat.le_of_lt_succ hk)
  simpa only [countLaw, Nat.add_sub_cancel_right,
    ENNReal.toReal_ofReal (fraction_bounds solution lumen).1.le]
    using binomial_mass (ENNReal.ofReal (lumenFraction solution lumen))
      (ENNReal.ofReal_le_one.mpr (fraction_bounds solution lumen).2.le) r k

private theorem adjacent_mass (outside inside : ℕ) (p exitFactor rate : ℝ)
    (odds : 1 - p = p * exitFactor) :
    mass p (outside + 1) inside * ((outside + 1 : ℕ) * rate) =
      mass p outside (inside + 1) * ((inside + 1 : ℕ) * rate * exitFactor) := by
  let n := outside + inside + 1
  have left : outside + 1 + inside = n := by dsimp [n]; omega
  have right : outside + (inside + 1) = n := by dsimp [n]; omega
  have remaining : n - inside = outside + 1 := by dsimp [n]; omega
  have recurrence := Nat.choose_succ_right_eq n inside
  rw [remaining] at recurrence
  have count : (n.choose inside : ℝ) * ((outside + 1 : ℕ) : ℝ) =
      (n.choose (inside + 1) : ℝ) * ((inside + 1 : ℕ) : ℝ) := by exact_mod_cast recurrence.symm
  simp only [mass, left, right, pow_succ]
  calc
    _ = ((n.choose inside : ℝ) * ((outside + 1 : ℕ) : ℝ)) *
        (p ^ inside * (1 - p) ^ outside * (1 - p) * rate) := by ring
    _ = _ := by rw [count, odds]; ring

/-- Each entry from k to k+1 and exit back from k+1 carry equal equilibrium probability flow. -/
theorem detailed_balance (solution lumen rate : ℝ) (n : ℕ) (k : Fin n) :
    ((countLaw solution lumen n) k.castSucc).toReal * ((n - ↑k : ℕ) * rate) =
      ((countLaw solution lumen n) k.succ).toReal *
        (((k : ℕ) + 1 : ℕ) * rate * Real.exp (lumen - solution)) := by
  have remaining : n - (k : ℕ) = (n - ((k : ℕ) + 1)) + 1 := by omega
  rw [count_mass, count_mass]
  simp only [Fin.coe_castSucc, Fin.val_succ, remaining]
  exact adjacent_mass (n - ((k : ℕ) + 1)) k _ _ rate (outside_fraction solution lumen)

/-- The continuous-time generator has zero mean for every count observable.
Each term pairs the only two crossings of an edge, including the edges at the endpoints. -/
theorem stationary (solution lumen rate : ℝ) (n : ℕ) (f : Fin (n + 1) → ℝ) :
    let π := countLaw solution lumen n
    ∑ k : Fin n, ((π k.castSucc).toReal * ((n - ↑k : ℕ) * rate) * (f k.succ - f k.castSucc) +
      (π k.succ).toReal * (((k : ℕ) + 1 : ℕ) * rate * Real.exp (lumen - solution)) *
        (f k.castSucc - f k.succ)) = 0 := by
  dsimp only
  apply Finset.sum_eq_zero
  intro k _
  rw [detailed_balance]
  ring

/-- Expected lumen count at fixed total tracer count. -/
def meanInside (solution lumen : ℝ) (n : ℕ) : ℝ :=
  ∑ k : Fin (n + 1), ((countLaw solution lumen n) k).toReal * (k.val : ℝ)

/-- Summing the adjacent balance equations equates total entry and exit at equilibrium. -/
theorem mean_inside_count (solution lumen : ℝ) (n : ℕ) :
    meanInside solution lumen n = n * lumenFraction solution lumen := by
  let weight (k : Fin (n + 1)) := ((countLaw solution lumen n) k).toReal
  let exitFactor := Real.exp (lumen - solution)
  have norm : ∑ k, weight k = 1 := countLaw_normalized solution lumen n
  have balance : (∑ k : Fin (n + 1), weight k * ((n : ℝ) - (k.val : ℝ))) =
      (∑ k, weight k * (k.val : ℝ)) * exitFactor := by
    calc
      _ = ∑ k : Fin n, weight k.castSucc * ((n - k.val : ℕ) : ℝ) := by
        rw [Fin.sum_univ_castSucc]
        simp only [Fin.coe_castSucc, Fin.val_last, sub_self, mul_zero, add_zero]
        exact Finset.sum_congr rfl (fun k _ => by rw [Nat.cast_sub k.isLt.le])
      _ = (∑ k : Fin n, weight k.succ * (k.succ.val : ℝ)) * exitFactor := by
        rw [Finset.sum_mul]
        apply Finset.sum_congr rfl
        intro k _
        simpa only [weight, exitFactor, Fin.val_succ, mul_one, mul_assoc]
          using detailed_balance solution lumen 1 n k
      _ = _ := by
        rw [Fin.sum_univ_succ (fun k : Fin (n + 1) => weight k * (k.val : ℝ))]
        simp
  simp_rw [mul_sub] at balance
  rw [Finset.sum_sub_distrib, ← Finset.sum_mul, norm, one_mul] at balance
  change (∑ k, weight k * (k.val : ℝ)) = (n : ℝ) * (1 + exitFactor)⁻¹
  rw [← div_eq_mul_inv, eq_div_iff (show 1 + exitFactor ≠ 0 by dsimp [exitFactor]; positivity)]
  linarith only [balance]

/-- At equal volumes the ratio of mean concentrations equals the ratio of mean counts. -/
theorem mean_concentration_ratio (solution lumen : ℝ) {n : ℕ} (hn : 0 < n) :
    meanInside solution lumen n / (n - meanInside solution lumen n) = Real.exp (-(lumen - solution)) := by
  rw [mean_inside_count, show (n : ℝ) - n * lumenFraction solution lumen =
      n * (1 - lumenFraction solution lumen) by ring,
    mul_div_mul_left _ _ (by exact_mod_cast hn.ne' : (n : ℝ) ≠ 0)]
  exact inside_outside_odds solution lumen

end
end CellsProofs.Chemistry.ShellEquilibrium
