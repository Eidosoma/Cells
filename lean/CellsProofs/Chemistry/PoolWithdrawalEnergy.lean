import CellsProofs.Chemistry.AssemblyMixing
import CellsProofs.Chemistry.PoolWithdrawal
import Mathlib.Probability.ProbabilityMassFunction.Binomial

/-! # Discrete energy of withdrawing a sample and adding a buffer to a finite pool -/

namespace CellsProofs.Chemistry.PoolWithdrawalEnergy

open AssemblyMixing (site)
open ReservoirExchange (logFactorial)
open LineageFission (trialAverage)
open PoolWithdrawal (wordAverage probability word_average_eq_trials)

noncomputable section

/-- Binomial weight for selecting k molecules and leaving r in the other volume. -/
def mass (f : ℝ) (r k : ℕ) : ℝ := ((r + k).choose k : ℝ) * f ^ k * (1 - f) ^ r

/-- Recover Mathlib's normalized finite probability mass at the actual count. -/
theorem binomial_mass (p : ENNReal) (hp : p ≤ 1) (r k : ℕ) :
    ((PMF.binomial p hp (r + k)) ⟨k, by omega⟩).toReal = mass p.toReal r k := by
  let i : Fin (r + k + 1) := ⟨k, by omega⟩
  change ((PMF.binomial p hp (r + k)) i).toReal = _
  rw [PMF.binomial_apply]
  simp [mass, i, ENNReal.toReal_mul, ENNReal.toReal_pow, ENNReal.toReal_sub_of_le hp,
    mul_comm, mul_assoc, mul_left_comm]

private theorem mass_pos {f : ℝ} (h₀ : 0 < f) (h₁ : f < 1) (r k : ℕ) : 0 < mass f r k := by
  have h : 0 < ((r + k).choose k : ℝ) := by exact_mod_cast Nat.choose_pos (Nat.le_add_left k r)
  exact mul_pos (mul_pos h (pow_pos h₀ _)) (pow_pos (sub_pos.mpr h₁) _)

private theorem mass_le_one {f : ℝ} (h₀ : 0 ≤ f) (h₁ : f ≤ 1) (r k : ℕ) : mass f r k ≤ 1 := by
  have hp : ENNReal.ofReal f ≤ 1 := by simpa using ENNReal.ofReal_le_ofReal h₁
  have h := (PMF.binomial (ENNReal.ofReal f) hp (r + k)).coe_le_one (⟨k, by omega⟩ : Fin (r+k+1))
  simpa only [binomial_mass, ENNReal.toReal_ofReal h₀, ENNReal.toReal_one]
    using ENNReal.toReal_mono ENNReal.one_ne_top h

/-- The standard potential includes the concentration scale at the full pool volume.
Energies here and in the booking are in units of k_BT. -/
def freeEnergy (μ g : ℝ) (n : ℕ) : ℝ := site μ n - n * Real.log g

private theorem log_choose (r k : ℕ) :
    Real.log ((r + k).choose k : ℝ) + logFactorial r + logFactorial k = logFactorial (r + k) := by
  have prod : ((r + k).choose k : ℝ) * r.factorial * k.factorial = (r + k).factorial := by
    exact_mod_cast Nat.add_choose_mul_factorial_mul_factorial r k
  have choose_ne : ((r + k).choose k : ℝ) ≠ 0 := by
    exact_mod_cast (Nat.choose_pos (Nat.le_add_left k r)).ne'
  have h := congrArg Real.log prod
  rw [Real.log_mul (mul_ne_zero choose_ne (by positivity)) (by positivity),
    Real.log_mul choose_ne (by positivity)] at h
  exact h

/-- The change on separating an ideal pool into volumes 1−f and f is the negative
log binomial mass at the physical volume fraction. All linear standard terms cancel. -/
theorem partition_cost (μ : ℝ) {f : ℝ} (h₀ : 0 < f) (h₁ : f < 1) (r k : ℕ) :
    freeEnergy μ (1 - f) r + freeEnergy μ f k - freeEnergy μ 1 (r + k) =
      -Real.log (mass f r k) := by
  have hc : ((r + k).choose k : ℝ) ≠ 0 := by
    exact_mod_cast (Nat.choose_pos (Nat.le_add_left k r)).ne'
  have hr := (sub_pos.mpr h₁).ne'
  rw [mass, Real.log_mul (mul_ne_zero hc (pow_ne_zero _ h₀.ne')) (pow_ne_zero _ hr),
    Real.log_mul hc (pow_ne_zero _ h₀.ne'), Real.log_pow, Real.log_pow]
  simp only [freeEnergy, site, Real.log_one, mul_zero, sub_zero, Nat.cast_add]
  nlinarith [log_choose r k]

variable {S : Type*} [Fintype S]

def poolEnergy (μ : S → ℝ) (g : ℝ) (counts : S → ℕ) : ℝ :=
  ∑ i, freeEnergy (μ i) g (counts i)

structure Booking where
  poolLoss : ℝ
  sampleEnergy : ℝ
  splitSurprisal : ℝ
  bufferWork : ℝ
  mixingHeat : ℝ

/-- r is the surviving pool, k the withdrawn sample and b the supplied buffer per place. -/
def book (μ : S → ℝ) (f : ℝ) (r k b : S → ℕ) : Booking :=
  let before := poolEnergy μ 1 (r + k)
  let kept := poolEnergy μ (1 - f) r
  let sample := poolEnergy μ f k
  let work := poolEnergy μ f b
  let after := poolEnergy μ 1 (r + b)
  ⟨before - kept, sample, kept + sample - before, work, kept + work - after⟩

theorem energy_balance (μ : S → ℝ) (f : ℝ) (r k b : S → ℕ) :
    let e := book μ f r k b
    poolEnergy μ 1 (r + b) - poolEnergy μ 1 (r + k) = e.bufferWork - e.poolLoss - e.mixingHeat ∧
      e.poolLoss = e.sampleEnergy - e.splitSurprisal := by
  dsimp only [book]
  constructor <;> ring

private theorem pool_partition (μ : S → ℝ) {f : ℝ} (h₀ : 0 < f) (h₁ : f < 1) (r k : S → ℕ) :
    poolEnergy μ (1 - f) r + poolEnergy μ f k - poolEnergy μ 1 (r + k) =
      ∑ i, -Real.log (mass f (r i) (k i)) := by
  unfold poolEnergy
  rw [← Finset.sum_add_distrib, ← Finset.sum_sub_distrib]
  exact Finset.sum_congr rfl fun i _ => partition_cost (μ i) h₀ h₁ (r i) (k i)

/-- The split uses the withdrawn counts. The later heat uses the buffer counts. -/
theorem binomial_bookings (μ : S → ℝ) {f : ℝ} (h₀ : 0 < f) (h₁ : f < 1) (r k b : S → ℕ) :
    let e := book μ f r k b
    e.splitSurprisal = ∑ i, -Real.log (mass f (r i) (k i)) ∧
      e.mixingHeat = ∑ i, -Real.log (mass f (r i) (b i)) :=
  ⟨pool_partition μ h₀ h₁ r k, pool_partition μ h₀ h₁ r b⟩

theorem nonnegative_heat_and_split (μ : S → ℝ) {f : ℝ} (h₀ : 0 < f) (h₁ : f < 1) (r k b : S → ℕ) :
    0 ≤ (book μ f r k b).mixingHeat ∧ 0 ≤ (book μ f r k b).splitSurprisal := by
  obtain ⟨split, heat⟩ := binomial_bookings μ h₀ h₁ r k b
  have nonneg (x y : ℕ) : 0 ≤ -Real.log (mass f x y) :=
    neg_nonneg.mpr (Real.log_nonpos (mass_pos h₀ h₁ x y).le (mass_le_one h₀.le h₁.le x y))
  rw [heat, split]
  exact ⟨Finset.sum_nonneg fun _ _ => nonneg _ _, Finset.sum_nonneg fun _ _ => nonneg _ _⟩

/-- With a tracer-free buffer, each retained molecule contributes −log(1−f) to the heat. -/
theorem tracer_free_heat (μ : S → ℝ) {f : ℝ} (h₀ : 0 < f) (h₁ : f < 1) (r k : S → ℕ) :
    (book μ f r k 0).mixingHeat = (∑ i, (r i : ℝ)) * (-Real.log (1 - f)) := by
  rw [(binomial_bookings μ h₀ h₁ r k 0).2, Finset.sum_mul]
  apply Finset.sum_congr rfl
  intro i _
  simp [mass, Real.log_pow]

/-- Mean contribution of one tracer place with zero supplied tracer. For every reachable count
k, the observable is the per-place heat from `tracer_free_heat`. -/
theorem mean_tracer_free_heat {bins : ℕ} (hb : 0 < bins) {f : ℝ} (hf : f < 1) (n : ℕ) :
    wordAverage bins f n (fun k => ((n : ℝ) - k) * (-Real.log (1 - f))) =
      n * (1 - probability bins f) * (-Real.log (1 - f)) := by
  let q := probability bins f
  have scale (m : ℕ) (g : ℕ → ℝ) (c : ℝ) :
      trialAverage q m (fun k => g k * c) = trialAverage q m g * c := by
    induction m generalizing g with
    | zero => rfl
    | succ m ih =>
      simp only [trialAverage]
      rw [ih g, ih (fun k => g (k + 1))]
      ring
  rw [word_average_eq_trials hb hf.le n, scale n (fun k => (n : ℝ) - k)]
  have retained := (PoolWithdrawal.pool_moments q n 0).1
  simpa using congrArg (fun t => t * (-Real.log (1 - f))) retained

private theorem trial_zero (p : ℝ) (n : ℕ) : trialAverage p n (fun _ => 0) = 0 := by
  induction n with
  | zero => rfl
  | succ n ih => simp [trialAverage, ih]

private theorem count_mass (p : ℝ) (n k : ℕ) :
    trialAverage p n (fun j => if j = k then 1 else 0) =
      (n.choose k : ℝ) * p ^ k * (1 - p) ^ (n - k) := by
  induction n generalizing k with
  | zero => cases k <;> simp [trialAverage]
  | succ n ih =>
    cases k with
    | zero =>
      simp [trialAverage, ih, trial_zero, pow_succ]
      ring
    | succ k =>
      simp only [trialAverage, Nat.succ.injEq, ih, Nat.choose_succ_succ, Nat.cast_add,
        Nat.succ_sub_succ_eq_sub, pow_succ p]
      by_cases h : k < n
      · have d : n - k = (n - (k + 1)) + 1 := by omega
        rw [d, pow_succ]
        ring
      · rw [Nat.choose_eq_zero_of_lt (show n < k + 1 by omega)]
        push_cast
        ring

/-- Probability of the actual count under independent uniform word indices. -/
theorem sampled_count_mass {bins : ℕ} (hb : 0 < bins) {f : ℝ} (hf : f ≤ 1) (r k : ℕ) :
    wordAverage bins f (r + k) (fun j => if j = k then 1 else 0) =
      mass (probability bins f) r k := by
  rw [word_average_eq_trials hb hf, count_mass, Nat.add_sub_cancel_right]
  rfl

/-- For an attainable outcome, the difference between the physical split energy and the
negative log sampler probability is the log likelihood ratio. This includes deterministic draws. -/
theorem sampled_score_gap (μ : ℝ) {bins : ℕ} (hb : 0 < bins) {f : ℝ} (h₀ : 0 < f) (h₁ : f < 1)
    (r k : ℕ) (reachable : 0 < mass (probability bins f) r k) :
    let sampled := wordAverage bins f (r + k) (fun j => if j = k then 1 else 0)
    (freeEnergy μ (1 - f) r + freeEnergy μ f k - freeEnergy μ 1 (r + k)) - (-Real.log sampled) =
      Real.log (sampled / mass f r k) := by
  dsimp only
  rw [sampled_count_mass hb h₁.le, partition_cost μ h₀ h₁, Real.log_div reachable.ne' (mass_pos h₀ h₁ r k).ne']
  ring

private theorem last_probability {bins : ℕ} (hb : 0 < bins) :
    probability bins (1 - (1 / 2) / bins) = ((bins : ℝ) - 1) / bins := by
  have hpos : (0 : ℝ) < bins := by exact_mod_cast hb
  have cut : (bins : ℝ) * (1 - (1 / 2) / bins) - 1 / 2 = ((bins - 1 : ℕ) : ℝ) := by
    rw [Nat.cast_sub hb, Nat.cast_one]
    field_simp
    ring
  rw [probability, PoolWithdrawal.cutoff, cut, Nat.ceil_natCast, Nat.cast_sub hb, Nat.cast_one]

/-- At the largest midpoint the expected tracer-free heat is twice the ideal-volume mean. -/
theorem last_midpoint_mean_heat {bins : ℕ} (hb : 0 < bins) (n : ℕ) :
    let f : ℝ := 1 - (1 / 2) / bins
    wordAverage bins f n (fun k => ((n : ℝ) - k) * (-Real.log (1 - f))) =
      2 * (n * (1 - f) * (-Real.log (1 - f))) := by
  have hpos : (0 : ℝ) < bins := by exact_mod_cast hb
  have hf : (1 - (1 / 2) / bins : ℝ) < 1 := sub_lt_self _ (by positivity)
  dsimp only
  rw [mean_tracer_free_heat hb hf, last_probability hb]
  have retention : 1 - ((bins : ℝ) - 1) / bins = 2 * (1 - (1 - (1 / 2) / bins)) := by
    field_simp
  rw [retention]
  ring

/-- At the last midpoint, the strict comparison keeps the last word. A single retained
molecule has twice its nominal retention probability and an exact log-two score gap. -/
theorem last_midpoint_gap (μ : ℝ) {bins : ℕ} (hb : 0 < bins) :
    let f : ℝ := 1 - (1 / 2) / bins
    let sampled := wordAverage bins f 1 (fun j => if j = 0 then 1 else 0)
    (freeEnergy μ (1 - f) 1 + freeEnergy μ f 0 - freeEnergy μ 1 1) - (-Real.log sampled) =
      Real.log 2 := by
  let f : ℝ := 1 - (1 / 2) / bins
  have hpos : (0 : ℝ) < bins := by exact_mod_cast hb
  have hone : (1 : ℝ) ≤ bins := by exact_mod_cast hb
  have half : 0 < (1 / 2 : ℝ) / bins := by positivity
  have small : (1 / 2 : ℝ) / bins < 1 := (div_lt_iff₀ hpos).mpr (by linarith)
  have hf₀ : 0 < f := by dsimp [f]; linarith
  have hf₁ : f < 1 := by dsimp [f]; linarith
  have q : probability bins f = ((bins : ℝ) - 1) / bins := last_probability hb
  have chance : mass (probability bins f) 1 0 = 1 / (bins : ℝ) := by
    simp [mass, q]
    field_simp
  have nominal : mass f 1 0 = (1 / 2 : ℝ) / bins := by simp [mass, f]
  have h := sampled_score_gap μ hb hf₀ hf₁ 1 0 (by rw [chance]; positivity)
  dsimp only at h
  have ratio : (1 / (bins : ℝ)) / ((1 / 2) / bins) = 2 := by field_simp
  exact h.trans (by rw [sampled_count_mass hb hf₁.le 1 0, chance, nominal, ratio])

end

end CellsProofs.Chemistry.PoolWithdrawalEnergy
