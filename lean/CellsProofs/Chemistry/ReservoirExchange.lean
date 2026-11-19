import Mathlib.Analysis.Calculus.Deriv.Add
import Mathlib.Analysis.Calculus.Deriv.Inv
import Mathlib.Analysis.SpecialFunctions.Log.Basic
import Mathlib.Data.Nat.Factorial.Basic
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Positivity
import Mathlib.Tactic.Ring

/-! # Uncatalyzed single-molecule exchange with a held reservoir

The assembly has finitely many molecule types. For one type, `k` is its
leave-rate constant and `θ = K ρ` its transfer constant times held activity.
Time is nominal. A positive event heat is measured in units of k_BT.
-/

namespace CellsProofs.Chemistry.ReservoirExchange

noncomputable section

def joinRate (k θ : ℝ) (size : ℕ) : ℝ := k * θ * size

def leaveRate (k : ℝ) (count : ℕ) : ℝ := k * count

theorem leave_increment (k : ℝ) (n : ℕ) : leaveRate k (n + 1) - leaveRate k n = k := by
  simp [leaveRate, mul_add]

theorem join_scaling (k K ρ factor : ℝ) (N extra : ℕ) :
    joinRate k (K * (factor * ρ)) N = factor * joinRate k (K * ρ) N ∧
    joinRate k (K * ρ) (N + extra) = joinRate k (K * ρ) N + joinRate k (K * ρ) extra := by
  constructor
  · unfold joinRate
    ring
  · simp [joinRate, mul_add]

theorem boundary_rates (k θ : ℝ) : joinRate k θ 0 = 0 ∧ leaveRate k 0 = 0 := by
  simp [joinRate, leaveRate]

variable {Species : Type*} [Fintype Species]

def size (n : Species → ℕ) : ℕ := ∑ j, n j

/-- At a nonempty state where every type's two rates balance, the held
activities weighted by their transfer constants must sum to one. -/
theorem balance_requires_normalization (k θ : Species → ℝ) (n : Species → ℕ)
    (hk : ∀ i, 0 < k i) (hN : 0 < size n)
    (balanced : ∀ i, joinRate (k i) (θ i) (size n) = leaveRate (k i) (n i)) :
    ∑ i, θ i = 1 := by
  have hi (i) : θ i * (size n : ℝ) = n i := by
    apply mul_left_cancel₀ (hk i).ne'
    simpa [joinRate, leaveRate, mul_assoc] using balanced i
  have hs : (∑ i, θ i) * (size n : ℝ) = size n := by
    rw [Finset.sum_mul]
    calc
      _ = ∑ i, (n i : ℝ) := Finset.sum_congr rfl (fun i _ => hi i)
      _ = _ := by simp [size]
  exact mul_right_cancel₀ (Nat.cast_ne_zero.mpr hN.ne') (hs.trans (one_mul _).symm)

/-- With a common leave constant, the mean-field drift of the fraction is
k (θᵢ − xᵢ ∑ θⱼ). For positive k and ∑ θⱼ its zero is at the normalized composition. -/
theorem common_rate_fraction_drift (k : ℝ) (θ : Species → ℝ) (n : Species → ℕ)
    (i : Species) (hN : 0 < size n) :
    let d := fun j => joinRate k (θ j) (size n) - leaveRate k (n j)
    (d i * (size n : ℝ) - (n i : ℝ) * ∑ j, d j) / (size n : ℝ) ^ 2 =
      k * (θ i - (n i : ℝ) / (size n : ℝ) * ∑ j, θ j) := by
  have total : (∑ j, (n j : ℝ)) = size n := by simp [size]
  have hsum : (∑ j, (joinRate k (θ j) (size n) - leaveRate k (n j))) =
      k * (size n : ℝ) * ((∑ j, θ j) - 1) := by
    simp only [joinRate, leaveRate, Finset.sum_sub_distrib, ← Finset.sum_mul, ← Finset.mul_sum,
      total]
    ring
  dsimp only
  rw [hsum]
  unfold joinRate leaveRate
  field_simp [Nat.cast_ne_zero.mpr hN.ne']
  ring

/-- Both types have θ = 1 and count one, with leave constants one and two.
The first type's fraction is already one half but has negative mean-field drift. -/
theorem unequal_rates_fraction_example {a b : ℝ → ℝ} {t : ℝ} (ha : a t = 1) (hb : b t = 1)
    (da : HasDerivAt a (joinRate 1 1 2 - leaveRate 1 1) t)
    (db : HasDerivAt b (joinRate 2 1 2 - leaveRate 2 1) t) :
    HasDerivAt (fun s => a s / (a s + b s)) (-(1 / 4 : ℝ)) t := by
  have htotal : a t + b t ≠ 0 := by norm_num [ha, hb]
  convert da.div (da.add db) htotal using 1
  norm_num [ha, hb, joinRate, leaveRate]

variable [DecidableEq Species]

def addOne (n : Species → ℕ) (i j : Species) : ℕ := n j + if j = i then 1 else 0

private theorem size_addOne (n : Species → ℕ) (i : Species) :
    size (addOne n i) = size n + 1 := by
  simp [size, addOne, Finset.sum_add_distrib]

private def logFactorial (n : ℕ) : ℝ := Real.log (n.factorial : ℝ)

private theorem logFactorial_succ (n : ℕ) :
    logFactorial (n + 1) = Real.log ((n : ℝ) + 1) + logFactorial n := by
  simp only [logFactorial, Nat.factorial_succ, Nat.cast_mul, Nat.cast_add_one]
  exact Real.log_mul (by positivity) (Nat.cast_ne_zero.mpr (Nat.factorial_ne_zero n))

private def contribution (θ : ℝ) (n : ℕ) := (n : ℝ) * Real.log θ - logFactorial n

/-- The engine's log weight, with value zero at the empty assembly. -/
def logWeight (θ : Species → ℝ) (n : Species → ℕ) : ℝ :=
  logFactorial (size n - 1) + ∑ j, contribution (θ j) (n j)

private theorem sum_addOne (θ : Species → ℝ) (n : Species → ℕ) (i : Species) :
    ∑ j, contribution (θ j) (addOne n i j) = (∑ j, contribution (θ j) (n j)) +
      (Real.log (θ i) - Real.log ((n i : ℝ) + 1)) := by
  have point (j : Species) : contribution (θ j) (addOne n i j) = contribution (θ j) (n j) +
      if j = i then Real.log (θ i) - Real.log ((n i : ℝ) + 1) else 0 := by
    by_cases h : j = i
    · subst j
      simp [addOne, contribution, logFactorial_succ]
      ring
    · simp [addOne, h]
  simp_rw [point]
  simp [Finset.sum_add_distrib]

/-- Compare a join at n to its reverse leave at n + eᵢ. The log-rate ratio
equals the change of the full finite-composition log weight. -/
theorem join_heat (k : ℝ) (θ : Species → ℝ) (n : Species → ℕ) (i : Species)
    (hk : 0 < k) (hθ : 0 < θ i) (hN : 0 < size n) :
    Real.log (joinRate k (θ i) (size n)) - Real.log (leaveRate k (n i + 1)) =
      logWeight θ (addOne n i) - logWeight θ n := by
  have hn : (size n : ℝ) ≠ 0 := Nat.cast_ne_zero.mpr hN.ne'
  have head : logFactorial (size n) = Real.log (size n : ℝ) + logFactorial (size n - 1) := by
    obtain ⟨m, hm⟩ := Nat.exists_eq_succ_of_ne_zero hN.ne'
    simp [hm, logFactorial_succ]
  simp only [logWeight, size_addOne, Nat.add_sub_cancel, sum_addOne, joinRate, leaveRate,
    Nat.cast_add_one, Real.log_mul (mul_pos hk hθ).ne' hn, Real.log_mul hk.ne' hθ.ne',
    Real.log_mul hk.ne' (by positivity : ((n i : ℝ) + 1) ≠ 0)]
  rw [head]
  ring

/-- On the same edge in the opposite direction the booked heat changes sign. -/
theorem leave_heat (k : ℝ) (θ : Species → ℝ) (n : Species → ℕ) (i : Species)
    (hk : 0 < k) (hθ : 0 < θ i) (hN : 0 < size n) :
    Real.log (leaveRate k (n i + 1)) - Real.log (joinRate k (θ i) (size n)) =
      logWeight θ n - logWeight θ (addOne n i) := by
  simpa only [neg_sub] using congrArg (fun x : ℝ => -x) (join_heat k θ n i hk hθ hN)

/-- Losing the last molecule has no reverse join from the empty state.
The terminal booking is the change of the same potential by convention. -/
theorem extinction_heat (θ : Species → ℝ) (i : Species) :
    logWeight θ (fun _ => 0) - logWeight θ (addOne (fun _ => 0) i) = -Real.log (θ i) := by
  simp only [logWeight, size_addOne, sum_addOne]
  simp [size, contribution, logFactorial]

end

end CellsProofs.Chemistry.ReservoirExchange
