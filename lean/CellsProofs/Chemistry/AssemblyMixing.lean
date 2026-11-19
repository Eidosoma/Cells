import CellsProofs.Chemistry.ReservoirExchange
import Mathlib.Data.Matrix.Mul

/-! # Discrete ideal and regular mixing in the assembly membrane

Energies and chemical potentials are in units of k_BT. The engine counts whole
molecules. The binary chemical potential is also given for continuous amounts.
-/

namespace CellsProofs.Chemistry.AssemblyMixing

open CellsProofs.Chemistry.ReservoirExchange Matrix

noncomputable section

variable {S : Type*} [Fintype S]

def site (μ : ℝ) (n : ℕ) : ℝ := n * μ + logFactorial n

theorem site_add (μ : ℝ) (n : ℕ) :
    site μ (n + 1) - site μ n = μ + Real.log ((n : ℝ) + 1) := by
  simp only [site, Nat.cast_add_one, logFactorial_succ]
  ring

def idealMembrane (c : ℕ) (μ : S → ℝ) (n : S → ℕ) : ℝ :=
  (∑ j, site (μ j) (n j)) - logFactorial (size n - c)

/-- At positive N the two registered measures differ by ln N. -/
theorem measure_shift (μ : S → ℝ) (n : S → ℕ) (hN : 0 < size n) :
    idealMembrane 1 μ n - idealMembrane 0 μ n = Real.log (size n : ℝ) := by
  obtain ⟨m, hm⟩ := Nat.exists_eq_succ_of_ne_zero hN.ne'
  simp [idealMembrane, hm, logFactorial_succ]

variable [DecidableEq S]

private theorem site_sum_add (μ : S → ℝ) (n : S → ℕ) (i : S) :
    (∑ j, site (μ j) (addOne n i j)) =
      (∑ j, site (μ j) (n j)) + (μ i + Real.log ((n i : ℝ) + 1)) := by
  have term (j) : site (μ j) (addOne n i j) = site (μ j) (n j) +
      if j = i then μ i + Real.log ((n i : ℝ) + 1) else 0 := by
    by_cases h : j = i
    · subst j
      simp [addOne, sub_eq_iff_eq_add.mp (site_add (μ i) (n i)), add_comm]
    · simp [addOne, h]
  simp_rw [term]
  simp [Finset.sum_add_distrib]

theorem ideal_insert (c : ℕ) (μ : S → ℝ) (n : S → ℕ) (i : S) (hc : c ≤ size n) :
    idealMembrane c μ (addOne n i) - idealMembrane c μ n =
      μ i + Real.log ((n i : ℝ) + 1) - Real.log (((size n - c : ℕ) : ℝ) + 1) := by
  have hn : size n + 1 - c = (size n - c) + 1 := by omega
  simp only [idealMembrane, site_sum_add, size_addOne, hn, logFactorial_succ]
  ring

/-- Activity relative to the membrane standard state for adding one molecule. -/
theorem ideal_insertion_activity (c : ℕ) (μ : S → ℝ) (n : S → ℕ) (i : S) (hc : c ≤ size n) :
    Real.exp (idealMembrane c μ (addOne n i) - idealMembrane c μ n - μ i) =
      ((n i : ℝ) + 1) / (((size n - c : ℕ) : ℝ) + 1) := by
  rw [ideal_insert c μ n i hc]
  have cancel (x y z : ℝ) : x + y - z - x = y - z := by ring
  rw [cancel, Real.exp_sub, Real.exp_log (by positivity), Real.exp_log (by positivity)]

/-- For the multinomial measure, the one-molecule activity approaches the mole fraction
as the total grows at fixed composition. The displayed error is exact. -/
theorem ideal_activity_error (a b : ℝ) (hN : 0 < a + b) :
    (a + 1) / (a + b + 1) - a / (a + b) = b / ((a + b) * (a + b + 1)) := by
  field_simp [hN.ne', (by linarith : 0 < a + b + 1).ne']
  ring

/-- The empty membrane and first insertion have the same convention for both offsets. -/
theorem first_insertion (c : ℕ) (μ : S → ℝ) (i : S) :
    idealMembrane c μ (fun _ => 0) = 0 ∧
      idealMembrane c μ (addOne (fun _ => 0) i) = μ i := by
  have h : logFactorial (1 - c) = 0 := by
    cases c <;> simp [logFactorial]
  simp only [idealMembrane, site_sum_add, size_addOne]
  simp [size, site, h, logFactorial]

/-- One molecule leaves a finite dilute pool initially holding p+1 of this species.
The pool's single-site potential is its standard potential minus ln X. -/
theorem ideal_transfer (c : ℕ) (μ : S → ℝ) (n : S → ℕ) (i : S) (hc : c ≤ size n)
    (μsol logX : ℝ) (p : ℕ) :
    (idealMembrane c μ (addOne n i) + site (μsol - logX) p) -
      (idealMembrane c μ n + site (μsol - logX) (p + 1)) =
      (μ i + Real.log ((n i : ℝ) + 1) - Real.log (((size n - c : ℕ) : ℝ) + 1)) -
        (μsol - logX + Real.log ((p : ℝ) + 1)) := by
  linarith [ideal_insert c μ n i hc, site_add (μsol - logX) p]

section Regular

omit [DecidableEq S]

/-- Symmetry makes the two cross terms in the cached numerator update equal. -/
theorem quadratic_update (χ : Matrix S S ℝ) (hs : χ.transpose = χ) (n d : S → ℝ) :
    (n + d) ⬝ᵥ (χ *ᵥ (n + d)) = n ⬝ᵥ (χ *ᵥ n) + 2 * (d ⬝ᵥ (χ *ᵥ n)) + d ⬝ᵥ (χ *ᵥ d) := by
  have cross : n ⬝ᵥ (χ *ᵥ d) = d ⬝ᵥ (χ *ᵥ n) := by
    rw [dotProduct_mulVec, ← mulVec_transpose, hs, dotProduct_comm]
  simp only [mulVec_add, add_dotProduct, dotProduct_add, cross]
  ring

def regular (χ : Matrix S S ℝ) (n : S → ℝ) (N : ℝ) : ℝ := n ⬝ᵥ (χ *ᵥ n) / (2 * N)

/-- The optimized update followed by normalization is the change of the state function.
Real division at zero gives the engine's explicit empty-membrane value zero. -/
theorem regular_change (χ : Matrix S S ℝ) (hs : χ.transpose = χ) (n d : S → ℝ) (N dN : ℝ) :
    regular χ (n + d) (N + dN) - regular χ n N =
      (n ⬝ᵥ (χ *ᵥ n) + 2 * (d ⬝ᵥ (χ *ᵥ n)) + d ⬝ᵥ (χ *ᵥ d)) / (2 * (N + dN)) -
        n ⬝ᵥ (χ *ᵥ n) / (2 * N) := by
  simp only [regular, quadratic_update χ hs]

end Regular

def binary (χ a b : ℝ) : ℝ := χ * a * b / (a + b)

theorem binary_specialization (χ a b : ℝ) :
    regular (S := Bool) (fun i j => if i = j then 0 else χ)
      (fun i => if i then b else a) (a + b) = binary χ a b := by
  simp [regular, binary, dotProduct, mulVec, Fintype.sum_bool, ← div_div]
  ring

theorem binary_insert (χ a b : ℝ) (hN : 0 < a + b) :
    binary χ (a + 1) b - binary χ a b = χ * b ^ 2 / ((a + b) * (a + b + 1)) := by
  unfold binary
  field_simp [hN.ne', (by linarith : 0 < a + 1 + b).ne', (by linarith : 0 < a + b + 1).ne']
  ring

/-- At fixed amount of B, the bulk excess chemical potential of A is χ x_B². -/
theorem binary_chemical_potential (χ a b : ℝ) (hN : 0 < a + b) :
    HasDerivAt (fun t => binary χ t b) (χ * (b / (a + b)) ^ 2) a := by
  have d := (((hasDerivAt_id a).const_mul χ).mul_const b).div ((hasDerivAt_id a).add_const b) hN.ne'
  convert d using 1
  dsimp
  field_simp
  ring

end

end CellsProofs.Chemistry.AssemblyMixing
