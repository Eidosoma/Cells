import CellsProofs.Chemistry.PoolWithdrawalEnergy
import Mathlib.Analysis.SpecificLimits.Basic

/-! # Heat of refilling a finite ideal pool at its original concentration -/

namespace CellsProofs.Chemistry.MatchedBuffer

open PoolWithdrawalEnergy (mass)
open PoolWithdrawal (probability wordAverage)
open Filter
open scoped Topology

noncomputable section

private theorem positive_mass {f : ℝ} (h₀ : 0 < f) (h₁ : f < 1) (r k : ℕ) :
    0 < mass f r k := by
  have h : 0 < ((r + k).choose k : ℝ) := by exact_mod_cast Nat.choose_pos (Nat.le_add_left k r)
  exact mul_pos (mul_pos h (pow_pos h₀ _)) (pow_pos (sub_pos.mpr h₁) _)

/-- With the remaining count fixed, compare the probabilities for adjacent supplied counts. -/
private theorem next_mass (r j : ℕ) (f : ℝ) :
    mass f r (j + 1) * (j + 1 : ℝ) = mass f r j * (f * (r + j + 1)) := by
  have c : ((r : ℝ) + j + 1) * ((r + j).choose j : ℝ) =
      (((r + j + 1).choose (j + 1)) : ℝ) * (j + 1 : ℝ) := by
    exact_mod_cast Nat.succ_mul_choose_eq (r + j) j
  simp only [mass, ← Nat.add_assoc, pow_succ f]
  linear_combination (f ^ j * f * (1 - f) ^ r) * c.symm

private theorem chain {g : ℕ → ℝ} {a b : ℕ} (hab : a ≤ b)
    (step : ∀ j, a ≤ j → j < b → g j ≤ g (j + 1)) : g a ≤ g b := by
  induction b, hab using Nat.le_induction with
  | base => exact le_rfl
  | succ j hj ih =>
    exact (ih fun t ht ht' => step t ht (by omega)).trans (step j hj (by omega))

/-- At matched concentration, the probability in the heat term is at least the
probability in the split term for every realization. The comparison is at physical f. -/
theorem matched_mass {f : ℝ} (h₀ : 0 < f) (h₁ : f < 1) (r k b : ℕ)
    (matched : (b : ℝ) = ((r : ℝ) + k) * f) : mass f r k ≤ mass f r b := by
  rcases le_total k b with h | h
  · apply chain h
    intro j _ hj
    have j' : (j : ℝ) + 1 ≤ b := by exact_mod_cast hj
    have k' : (k : ℝ) ≤ b := by exact_mod_cast h
    have step : (j : ℝ) + 1 ≤ f * (r + j + 1) := by
      nlinarith [mul_nonneg (sub_nonneg.mpr j') (sub_pos.mpr h₁).le,
        mul_nonneg (sub_nonneg.mpr k') h₀.le]
    apply le_of_mul_le_mul_right _ (show (0 : ℝ) < j + 1 by positivity)
    rw [next_mass]
    exact mul_le_mul_of_nonneg_left step (positive_mass h₀ h₁ r j).le
  · apply le_of_neg_le_neg
    apply chain (g := fun j => -mass f r j) h
    intro j hj _
    apply neg_le_neg
    have j' : (b : ℝ) ≤ (j : ℝ) + 1 := by exact_mod_cast (show b ≤ j + 1 by omega)
    have k' : (b : ℝ) ≤ k := by exact_mod_cast h
    have step : f * (r + j + 1) ≤ (j : ℝ) + 1 := by
      nlinarith [mul_nonneg (sub_nonneg.mpr j') (sub_pos.mpr h₁).le,
        mul_nonneg (sub_nonneg.mpr k') h₀.le]
    apply le_of_mul_le_mul_right _ (show (0 : ℝ) < j + 1 by positivity)
    rw [next_mass]
    exact mul_le_mul_of_nonneg_left step (positive_mass h₀ h₁ r j).le

/-- Cells books the heat on the refilled pool and the split score on the withdrawn sample.
For one matched place these quantities inherit the mass comparison with the reversed sign. -/
theorem heat_le_split_score {f : ℝ} (h₀ : 0 < f) (h₁ : f < 1) (r k b : ℕ)
    (matched : (b : ℝ) = ((r : ℝ) + k) * f) :
    -Real.log (mass f r b) ≤ -Real.log (mass f r k) :=
  neg_le_neg (Real.log_le_log (positive_mass h₀ h₁ r k) (matched_mass h₀ h₁ r k b matched))

/-- With each buffer count matched, the total heat booked for the finite pool lies
between zero and the booked split score on the same receipt. -/
theorem booked_heat_bounds {S : Type*} [Fintype S] (μ : S → ℝ) {f : ℝ}
    (h₀ : 0 < f) (h₁ : f < 1) (r k b : S → ℕ)
    (matched : ∀ i, (b i : ℝ) = ((r i : ℝ) + k i) * f) :
    let e := PoolWithdrawalEnergy.book μ f r k b
    0 ≤ e.mixingHeat ∧ e.mixingHeat ≤ e.splitSurprisal := by
  refine ⟨(PoolWithdrawalEnergy.nonnegative_heat_and_split μ h₀ h₁ r k b).1, ?_⟩
  obtain ⟨split, heat⟩ := PoolWithdrawalEnergy.binomial_bookings μ h₀ h₁ r k b
  rw [heat, split]
  exact Finset.sum_le_sum fun i _ => heat_le_split_score h₀ h₁ _ _ _ (matched i)

private theorem nonneg_cost {f : ℝ} (h₀ : 0 < f) (h₁ : f < 1) (r b : ℕ) :
    0 ≤ -Real.log (mass f r b) := by
  let r' : Unit → ℕ := fun _ => r
  let b' : Unit → ℕ := fun _ => b
  have h := (PoolWithdrawalEnergy.nonnegative_heat_and_split 0 h₀ h₁ r' 0 b').1
  rw [(PoolWithdrawalEnergy.binomial_bookings 0 h₀ h₁ r' 0 b').2] at h
  simpa [r', b'] using h

private theorem normalized (n : ℕ) (f : ℝ) :
    ∑ k : Fin (n + 1), mass f (n - k) k = 1 := by
  have point (k : Fin (n + 1)) : mass f (n - k) k =
      f ^ (k : ℕ) * (1 - f) ^ (n - k.val) * n.choose k := by
    rw [mass, Nat.sub_add_cancel (show k.val ≤ n by omega)]
    ring
  simp_rw [point]
  rw [Fin.sum_univ_eq_sum_range (fun k : ℕ => f ^ k * (1 - f) ^ (n - k) * n.choose k), ← add_pow]
  simp

/-- Average the per-place heat over all possible withdrawn counts. The finite-word sampler
sets their probabilities and the physical volume fraction sets the heat of each outcome. -/
def meanHeat (bins n b : ℕ) (f : ℝ) : ℝ :=
  ∑ k : Fin (n + 1), mass (probability bins f) (n - k) k * (-Real.log (mass f (n - k) b))

theorem mean_from_word_counts {bins : ℕ} (hb : 0 < bins) {f : ℝ} (hf : f < 1) (n b : ℕ) :
    meanHeat bins n b f = ∑ k : Fin (n + 1),
      wordAverage bins f n (fun j => if j = (k : ℕ) then 1 else 0) * (-Real.log (mass f (n - k) b)) := by
  apply Finset.sum_congr rfl
  intro k _
  have h := PoolWithdrawalEnergy.sampled_count_mass hb hf.le (n - k.val) k.val
  rw [Nat.sub_add_cancel (show k.val ≤ n by omega)] at h
  rw [h]

/-- The entropy in n+1 strictly positive probabilities is bounded by log(n+1).
Apply the tangent bound for the logarithm to the uniform weight divided by each weight. -/
private theorem entropy_bound {n : ℕ} (p : Fin (n + 1) → ℝ) (hp : ∀ k, 0 < p k)
    (total : ∑ k, p k = 1) : ∑ k, p k * (-Real.log (p k)) ≤ Real.log (n + 1 : ℝ) := by
  let m : ℝ := n + 1
  have hm : 0 < m := by dsimp [m]; positivity
  have each (k) : p k * (-Real.log (p k)) ≤ p k * Real.log m + (1 / m - p k) := by
    have h := mul_le_mul_of_nonneg_left
      (Real.log_le_sub_one_of_pos (inv_pos.mpr (mul_pos hm (hp k)))) (hp k).le
    rw [Real.log_inv, Real.log_mul hm.ne' (hp k).ne'] at h
    have cancel : p k * ((m * p k)⁻¹ - 1) = 1 / m - p k := by
      field_simp [hm.ne', (hp k).ne']
      ring
    rw [cancel] at h
    linarith
  calc
    _ ≤ ∑ k, (p k * Real.log m + (1 / m - p k)) := Finset.sum_le_sum fun k _ => each k
    _ = Real.log (n + 1 : ℝ) := by
      rw [Finset.sum_add_distrib, Finset.sum_sub_distrib, ← Finset.sum_mul, total]
      simp [m, nsmul_eq_mul, hm.ne']

/-- On the exact sampling grid the mean heat is bounded by the entropy of the
withdrawn count across the n+1 possible outcomes. -/
theorem mean_le_split_entropy {bins n b : ℕ} {f : ℝ} (h₀ : 0 < f) (h₁ : f < 1)
    (matched : (b : ℝ) = n * f) (onGrid : probability bins f = f) :
    meanHeat bins n b f ≤ ∑ k : Fin (n + 1),
      mass f (n - k) k * (-Real.log (mass f (n - k) k)) := by
  unfold meanHeat
  rw [onGrid]
  apply Finset.sum_le_sum
  intro k _
  apply mul_le_mul_of_nonneg_left _ (positive_mass h₀ h₁ _ _).le
  apply heat_le_split_score h₀ h₁
  rw [← Nat.cast_add, Nat.sub_add_cancel (show k.val ≤ n by omega), matched]

/-- The expected matched heat is strictly positive for a nonempty ideal pool. The upper
bound holds for the engine sampler when its withdrawal probability equals the physical fraction. -/
theorem mean_bounds {bins n b : ℕ} {f : ℝ} (hn : 0 < n) (h₀ : 0 < f) (h₁ : f < 1)
    (matched : (b : ℝ) = n * f) (onGrid : probability bins f = f) :
    0 < meanHeat bins n b f ∧ meanHeat bins n b f ≤ Real.log (n + 1 : ℝ) := by
  let p (k : Fin (n + 1)) := mass f (n - k) k
  have hp (k) : 0 < p k := positive_mass h₀ h₁ _ _
  constructor
  · unfold meanHeat
    rw [onGrid]
    apply Finset.sum_pos' (fun k _ => mul_nonneg (hp k).le (nonneg_cost h₀ h₁ _ _))
    let last : Fin (n + 1) := ⟨n, by omega⟩
    refine ⟨last, Finset.mem_univ _, mul_pos (hp last) ?_⟩
    have hb : 0 < b := by exact_mod_cast (matched.symm ▸ mul_pos (Nat.cast_pos.mpr hn) h₀)
    have hlt : f ^ b < 1 := pow_lt_one₀ h₀.le h₁ hb.ne'
    simpa [last, mass] using neg_pos.mpr (Real.log_neg (pow_pos h₀ b) hlt)
  · exact (mean_le_split_entropy h₀ h₁ matched onGrid).trans (entropy_bound p hp (normalized n f))

theorem per_molecule_bound {bins n b : ℕ} {f : ℝ} (hn : 0 < n) (h₀ : 0 < f) (h₁ : f < 1)
    (matched : (b : ℝ) = n * f) (onGrid : probability bins f = f) :
    0 < meanHeat bins n b f / n ∧ meanHeat bins n b f / n ≤ Real.log (n + 1 : ℝ) / n := by
  obtain ⟨pos, bound⟩ := mean_bounds hn h₀ h₁ matched onGrid
  exact ⟨div_pos pos (Nat.cast_pos.mpr hn), div_le_div_of_nonneg_right bound (Nat.cast_nonneg n)⟩

/-- The matched heat per initial molecule vanishes along any sequence of admissible pool
sizes growing to infinity. Exact matching only needs to hold along that sequence. -/
theorem per_molecule_limit {bins : ℕ} {f : ℝ} (h₀ : 0 < f) (h₁ : f < 1)
    (onGrid : probability bins f = f) (sizes buffer : ℕ → ℕ)
    (grows : Tendsto sizes atTop atTop) (matched : ∀ i, (buffer i : ℝ) = sizes i * f) :
    Tendsto (fun i => meanHeat bins (sizes i) (buffer i) f / sizes i) atTop (𝓝 0) := by
  have bound : Tendsto (fun n : ℕ => Real.log (n + 1 : ℝ) / n) atTop (𝓝 0) := by
    have shifted : Tendsto (fun n : ℕ => (n : ℝ) + 1) atTop atTop :=
      tendsto_natCast_atTop_atTop.atTop_add tendsto_const_nhds
    have first := Real.isLittleO_log_id_atTop.tendsto_div_nhds_zero.comp shifted
    have second := (tendsto_const_nhds (x := (1 : ℝ))).add tendsto_one_div_atTop_nhds_zero_nat
    have prod : Tendsto (fun n : ℕ => Real.log (n + 1 : ℝ) / (n + 1) * (1 + 1 / n))
        atTop (𝓝 0) := by simpa using first.mul second
    apply prod.congr'
    filter_upwards [eventually_ge_atTop 1] with n hn
    have hn' : (0 : ℝ) < n := by exact_mod_cast hn
    field_simp [hn'.ne', (show (n : ℝ) + 1 ≠ 0 by positivity)]
  apply tendsto_of_tendsto_of_tendsto_of_le_of_le' tendsto_const_nhds (bound.comp grows)
  · filter_upwards [grows.eventually_ge_atTop 1] with i hi
    exact (per_molecule_bound hi h₀ h₁ (matched i) onGrid).1.le
  · filter_upwards [grows.eventually_ge_atTop 1] with i hi
    exact (per_molecule_bound hi h₀ h₁ (matched i) onGrid).2

end

end CellsProofs.Chemistry.MatchedBuffer
