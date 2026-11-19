import CellsProofs.Chemistry.ReservoirExchange

/-! # GARD multipliers on adjacent assembly compositions

Both registered comparison laws use the row of β belonging to the moving species.
The passive rule removes that molecule before evaluating the reverse multiplier.
-/

namespace CellsProofs.Chemistry.GardCatalysis

open CellsProofs.Chemistry.ReservoirExchange

noncomputable section

variable {S : Type*} [Fintype S] [DecidableEq S]

def weighted (w : S → ℝ) (n : S → ℕ) : ℝ := ∑ j, w j * n j

def factor (β : S → S → ℝ) (n : S → ℕ) (i : S) : ℝ :=
  if size n = 0 then 1 else 1 + weighted (β i) n / size n

def pairLeave (β : S → S → ℝ) (m : S → ℕ) (i : S) : ℝ :=
  if 1 < size m ∧ 0 < m i then 1 + (weighted (β i) m - β i i) / (size m - 1 : ℝ) else 1

theorem weighted_addOne (w : S → ℝ) (n : S → ℕ) (i : S) :
    weighted w (addOne n i) = weighted w n + w i := by
  classical
  simp [weighted, addOne, mul_add, mul_ite, Finset.sum_add_distrib]

omit [DecidableEq S] in
theorem factor_pos (β : S → S → ℝ) (hβ : ∀ i j, 0 ≤ β i j) (n : S → ℕ) (i : S) :
    0 < factor β n i := by
  have hw : 0 ≤ weighted (β i) n :=
    Finset.sum_nonneg fun j _ => mul_nonneg (hβ i j) (Nat.cast_nonneg _)
  unfold factor
  split <;> positivity

/-- Removing the joining molecule restores each remaining catalyst's original contribution. -/
theorem pair_reverse_factor (β : S → S → ℝ) (n : S → ℕ) (i : S) :
    pairLeave β (addOne n i) i = factor β n i := by
  by_cases h : size n = 0
  · simp [pairLeave, factor, size_addOne, h]
  · have hs : 1 < size n + 1 := by omega
    have hi : 0 < addOne n i i := by simp [addOne]
    simp [pairLeave, factor, size_addOne, weighted_addOne, hs, hi, h]

/-- For a singleton, the two registered exit factors are 1 and 1 + βᵢᵢ. -/
theorem singleton_factors (β : S → S → ℝ) (i : S) :
    pairLeave β (addOne (fun _ => 0) i) i = 1 ∧
      factor β (addOne (fun _ => 0) i) i = 1 + β i i := by
  rw [pair_reverse_factor]
  simp only [factor, size_addOne, weighted_addOne]
  simp [size, weighted]

private theorem heat_with_factors (k : ℝ) (θ : S → ℝ) (n : S → ℕ) (i : S) (g h : ℝ)
    (hk : 0 < k) (hθ : 0 < θ i) (hN : 0 < size n) (hg : 0 < g) (hh : 0 < h) :
    Real.log (joinRate k (θ i) (size n) * g) - Real.log (leaveRate k (n i + 1) * h) =
      logWeight θ (addOne n i) - logWeight θ n + (Real.log g - Real.log h) := by
  have hj : 0 < joinRate k (θ i) (size n) := by unfold joinRate; positivity
  have hl : 0 < leaveRate k (n i + 1) := by unfold leaveRate; positivity
  rw [Real.log_mul hj.ne' hg.ne', Real.log_mul hl.ne' hh.ne', ← join_heat k θ n i hk hθ hN]
  ring

theorem pair_heat (β : S → S → ℝ) (hβ : ∀ i j, 0 ≤ β i j) (k : ℝ) (θ : S → ℝ)
    (n : S → ℕ) (i : S) (hk : 0 < k) (hθ : 0 < θ i) (hN : 0 < size n) :
    Real.log (joinRate k (θ i) (size n) * factor β n i) -
        Real.log (leaveRate k (n i + 1) * pairLeave β (addOne n i) i) =
      logWeight θ (addOne n i) - logWeight θ n := by
  rw [pair_reverse_factor]
  simpa using heat_with_factors k θ n i _ _ hk hθ hN (factor_pos β hβ n i) (factor_pos β hβ n i)

theorem single_heat (β : S → S → ℝ) (hβ : ∀ i j, 0 ≤ β i j) (k : ℝ) (θ : S → ℝ)
    (n : S → ℕ) (i : S) (hk : 0 < k) (hθ : 0 < θ i) (hN : 0 < size n) :
    Real.log (joinRate k (θ i) (size n) * factor β n i) -
        Real.log (leaveRate k (n i + 1) * factor β (addOne n i) i) =
      logWeight θ (addOne n i) - logWeight θ n +
        (Real.log (factor β n i) - Real.log (factor β (addOne n i) i)) :=
  heat_with_factors k θ n i _ _ hk hθ hN (factor_pos β hβ n i) (factor_pos β hβ _ i)

omit [DecidableEq S] in
/-- Rank one of the entrywise sum 1 + β gives a common composition-dependent factor. -/
theorem shifted_factor (β : S → S → ℝ) (u v : S → ℝ) (shift : ∀ i j, 1 + β i j = u i * v j)
    (n : S → ℕ) (i : S) (hN : 0 < size n) :
    factor β n i = u i * (weighted v n / size n) := by
  have row (j : S) : β i j = u i * v j - 1 := by linarith [shift i j]
  have hw : weighted (β i) n = u i * weighted v n - size n := by
    simp only [weighted, row, sub_mul, one_mul, mul_assoc, Finset.sum_sub_distrib, ← Finset.mul_sum]
    simp [size]
  rw [factor, if_neg hN.ne', hw]
  field_simp [Nat.cast_ne_zero.mpr hN.ne']

/-- The single-event extra heat is then a difference of log mean weights. It telescopes
on every cycle of nonempty states even when an individual edge has a nonzero correction. -/
theorem shifted_heat (β : S → S → ℝ) (hβ : ∀ i j, 0 ≤ β i j) (u v : S → ℝ)
    (hu : ∀ i, 0 < u i) (shift : ∀ i j, 1 + β i j = u i * v j) (k : ℝ) (θ : S → ℝ)
    (n : S → ℕ) (i : S) (hk : 0 < k) (hθ : 0 < θ i) (hN : 0 < size n) :
    let Φ := fun m => logWeight θ m - Real.log (weighted v m / size m)
    Real.log (joinRate k (θ i) (size n) * factor β n i) -
      Real.log (leaveRate k (n i + 1) * factor β (addOne n i) i) = Φ (addOne n i) - Φ n := by
  have log_factor (m : S → ℕ) (hm : 0 < size m) :
      Real.log (factor β m i) = Real.log (u i) + Real.log (weighted v m / size m) := by
    have hf := factor_pos β hβ m i
    rw [shifted_factor β u v shift m i hm] at hf ⊢
    exact Real.log_mul (hu i).ne' (right_ne_zero_of_mul hf.ne')
  dsimp only
  rw [single_heat β hβ k θ n i hk hθ hN, log_factor n hN,
    log_factor (addOne n i) (by simp [size_addOne])]
  ring

/-- Rate-product ratio on the square +A,+B,−A,−B with unit base rate constants and activities. -/
def singleSquare (β : Bool → Bool → ℝ) (n : Bool → ℕ) : ℝ :=
  let edge := fun m i => (joinRate 1 1 (size m) * factor β m i) /
    (leaveRate 1 (m i + 1) * factor β (addOne m i) i)
  edge n false * edge (addOne n false) true / (edge (addOne n true) false * edge n true)

/-- The unshifted matrix has a single nonzero entry, β_AA = 1, and is rank one. -/
theorem raw_rank_one_square :
    let u : Bool → ℝ := fun j => if j then 0 else 1
    singleSquare (fun i j => u i * u j) (fun _ => 1) = 81 / 80 := by
  norm_num [singleSquare, joinRate, leaveRate, factor, size, weighted, addOne, Fintype.sum_bool]

end

end CellsProofs.Chemistry.GardCatalysis
