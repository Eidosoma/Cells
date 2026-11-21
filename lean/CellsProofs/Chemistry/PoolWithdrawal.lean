import CellsProofs.Chemistry.LineageFission
import Mathlib.Algebra.Order.Floor.Semiring

/-! # Counts in a partial withdrawal from one well-mixed pool place -/

namespace CellsProofs.Chemistry.PoolWithdrawal

open LineageFission (trialAverage)

/-- Count the withdrawn molecules for any assignment, including correlated draws. -/
theorem inventory (n buffer capacity : ℕ) (leaves : Fin n → Bool)
    (room : n + buffer ≤ capacity) :
    let k := (Finset.univ.filter fun i => leaves i = true).card
    k ≤ n ∧ (n - k + buffer) + k = n + buffer ∧ n - k + buffer ≤ capacity := by
  have bound := Finset.card_le_card (Finset.filter_subset (fun i => leaves i = true) Finset.univ)
  simp only [Finset.card_univ, Fintype.card_fin] at bound
  dsimp
  omega

/-- The engine compares midpoints (m + 1/2) / bins strictly to the requested fraction. -/
noncomputable def midpoint (bins m : ℕ) : ℝ := ((m : ℝ) + 1 / 2) / bins

noncomputable def cutoff (bins : ℕ) (f : ℝ) : ℕ := ⌈(bins : ℝ) * f - 1 / 2⌉₊

/-- The exact single-molecule probability under equiprobable word indices. -/
noncomputable def probability (bins : ℕ) (f : ℝ) : ℝ := (cutoff bins f : ℝ) / bins

theorem accepted_words {bins : ℕ} (hb : 0 < bins) {f : ℝ} (hf : f ≤ 1) :
    (Finset.range bins).filter (fun m => midpoint bins m < f) = Finset.range (cutoff bins f) := by
  have pos : (0 : ℝ) < bins := by exact_mod_cast hb
  have cap : cutoff bins f ≤ bins := Nat.ceil_le.mpr (by nlinarith)
  ext m
  simp only [Finset.mem_filter, Finset.mem_range, midpoint, div_lt_iff₀ pos]
  constructor
  · rintro ⟨_, h⟩
    exact Nat.lt_ceil.mpr (by linarith)
  · intro h
    exact ⟨lt_of_lt_of_le h cap, by linarith [Nat.lt_ceil.mp h]⟩

/-- The maximum error is half a bin, including at a midpoint where the strict tie stays. -/
theorem probability_error {bins : ℕ} (hb : 0 < bins) {f : ℝ} (hf : 0 ≤ f) :
    |probability bins f - f| ≤ (1 / 2 : ℝ) / bins := by
  have pos : (0 : ℝ) < bins := by exact_mod_cast hb
  have low := Nat.le_ceil ((bins : ℝ) * f - 1 / 2)
  have high : (cutoff bins f : ℝ) ≤ bins * f + 1 / 2 := by
    by_cases h : 0 ≤ (bins : ℝ) * f - 1 / 2
    · have := Nat.ceil_lt_add_one h
      unfold cutoff
      linarith
    · rw [cutoff, Nat.ceil_eq_zero.mpr (le_of_not_ge h), Nat.cast_zero]
      positivity
  have diff : probability bins f - f = ((cutoff bins f : ℝ) - f * bins) / bins := by
    unfold probability
    field_simp
    ring
  rw [diff, abs_div, abs_of_pos pos, div_le_div_iff_of_pos_right pos, abs_le]
  change (bins : ℝ) * f - 1 / 2 ≤ (cutoff bins f : ℝ) at low
  constructor <;> linarith

theorem probability_on_grid {bins : ℕ} (hb : 0 < bins) (k : ℕ) :
    probability bins (k / (bins : ℝ)) = k / (bins : ℝ) := by
  have pos : (0 : ℝ) < bins := by exact_mod_cast hb
  have prod : (bins : ℝ) * (k / (bins : ℝ)) = k := by field_simp
  unfold probability cutoff
  rw [prod]
  congr 2
  cases k with
  | zero => norm_num
  | succ k =>
    apply (Nat.ceil_eq_iff (Nat.succ_ne_zero k)).mpr
    simp only [Nat.succ_sub_one, Nat.cast_succ]
    constructor <;> linarith

theorem first_midpoint_stays {bins : ℕ} (hb : 0 < bins) {f : ℝ}
    (h : f ≤ midpoint bins 0) : probability bins f = 0 := by
  have pos : (0 : ℝ) < bins := by exact_mod_cast hb
  simp only [midpoint, Nat.cast_zero, zero_add, le_div_iff₀ pos] at h
  have zero : cutoff bins f = 0 := Nat.ceil_eq_zero.mpr (by linarith)
  rw [probability, zero, Nat.cast_zero, zero_div]

/-- Average over one independent, equally likely midpoint word per molecule. -/
noncomputable def wordAverage (bins : ℕ) (f : ℝ) : ℕ → (ℕ → ℝ) → ℝ
  | 0, g => g 0
  | n + 1, g => (∑ m ∈ Finset.range bins, if midpoint bins m < f then
      wordAverage bins f n (fun k => g (k + 1)) else wordAverage bins f n g) / bins

/-- Any observable of the withdrawn count follows the independent Bernoulli recursion. -/
theorem word_average_eq_trials {bins : ℕ} (hb : 0 < bins) {f : ℝ} (hf : f ≤ 1)
    (n : ℕ) (g : ℕ → ℝ) :
    wordAverage bins f n g = trialAverage (probability bins f) n g := by
  have pos : (0 : ℝ) < bins := by exact_mod_cast hb
  have partition := Finset.filter_card_add_filter_neg_card_eq_card (s := Finset.range bins)
    (fun m => midpoint bins m < f)
  rw [accepted_words hb hf, Finset.card_range, Finset.card_range] at partition
  have totals : (cutoff bins f : ℝ) +
      ((Finset.range bins).filter (fun m => ¬ midpoint bins m < f)).card = bins := by
    exact_mod_cast partition
  simp only [not_lt] at totals
  induction n generalizing g with
  | zero => rfl
  | succ n ih =>
    simp only [wordAverage, trialAverage, ih, Finset.sum_ite, Finset.sum_const, nsmul_eq_mul,
      accepted_words hb hf, Finset.card_range, probability]
    field_simp
    linear_combination (trialAverage ((cutoff bins f : ℝ) / bins) n g) * totals

theorem withdrawn_moments {bins : ℕ} (hb : 0 < bins) {f : ℝ} (hf : f ≤ 1) (n : ℕ) :
    let p := probability bins f
    wordAverage bins f n (fun k => (k : ℝ)) = n * p ∧
    wordAverage bins f n (fun k => (k : ℝ) ^ 2) -
      wordAverage bins f n (fun k => (k : ℝ)) ^ 2 = n * p * (1 - p) := by
  simpa only [word_average_eq_trials hb hf] using LineageFission.binomial_moments (probability bins f) n

/-- Adding a fixed buffer to the retained pool shifts its mean and leaves the variance of
the removed count intact. On every outcome k ≤ n, the observable here is the final count. -/
theorem pool_moments (p : ℝ) (n buffer : ℕ) :
    let final := fun k : ℕ => (n : ℝ) + buffer - k
    trialAverage p n final = n * (1 - p) + buffer ∧
    trialAverage p n (fun k => final k ^ 2) - (trialAverage p n final) ^ 2 =
      n * p * (1 - p) := by
  have affine (m : ℕ) (a b c : ℝ) (g h : ℕ → ℝ) :
      trialAverage p m (fun k => a + b * g k + c * h k) =
        a + b * trialAverage p m g + c * trialAverage p m h := by
    induction m generalizing g h with
    | zero => rfl
    | succ m ih =>
      simp only [trialAverage]
      rw [ih g h, ih (fun k => g (k + 1)) (fun k => h (k + 1))]
      ring
  let a : ℝ := n + buffer
  let idCount := fun k : ℕ => (k : ℝ)
  let sq := fun k : ℕ => (k : ℝ) ^ 2
  have hm := LineageFission.binomial_moments p n
  have e₁ := affine n a (-1) 0 idCount sq
  have e₂ := affine n (a ^ 2) (-2 * a) 1 idCount sq
  have poly (k : ℕ) : (a - k) ^ 2 = a ^ 2 + (-2 * a) * idCount k + 1 * sq k := by
    dsimp [idCount, sq]
    ring
  simp only [idCount, neg_one_mul, zero_mul, add_zero, ← sub_eq_add_neg, hm.1] at e₁
  dsimp only
  change trialAverage p n (fun k => a - k) = _ ∧
    trialAverage p n (fun k => (a - k) ^ 2) - _ = _
  rw [e₁, funext poly, e₂]
  dsimp [a, idCount, sq] at *
  have second := hm.2
  rw [hm.1] at second ⊢
  constructor <;> nlinarith [second]

end CellsProofs.Chemistry.PoolWithdrawal
