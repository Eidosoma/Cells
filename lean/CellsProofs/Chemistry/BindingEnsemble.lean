import Mathlib.Algebra.BigOperators.Field
import Mathlib.Algebra.BigOperators.Group.Finset.Sigma
import Mathlib.Analysis.SpecialFunctions.Log.Basic
import Mathlib.Tactic.Ring

/-! Equilibrium form fractions at fixed free ligand activities in rapid binding. -/

namespace CellsProofs.Chemistry.BindingEnsemble

open scoped BigOperators

noncomputable section

/-- The standard binding constant and signed ligand counts use the same concentration frame
as the free ligand log concentrations. -/
def logWeight {L : Type*} [Fintype L] (logBeta : ℝ) (counts : L → ℤ) (u : L → ℝ) : ℝ :=
  logBeta + ∑ l, (counts l : ℝ) * u l

/-- The fraction of binders in one of the physically present forms. -/
def fraction {F : Type*} [Fintype F] (a : F → ℝ) (i : F) : ℝ :=
  Real.exp (a i) / ∑ j, Real.exp (a j)

/-- Subtracting log c₀ times the total ligand count from log β lets the kernel use log mM. -/
theorem logWeight_change_frame {L : Type*} [Fintype L] (b : ℝ) (n : L → ℤ)
    (u : L → ℝ) (s : ℝ) :
    logWeight (b - (∑ l, (n l : ℝ)) * s) n u = logWeight b n (fun l => u l - s) := by
  simp only [logWeight, mul_sub, Finset.sum_sub_distrib, ← Finset.sum_mul]
  ring

variable {F : Type*} [Fintype F]

private theorem sum_exp_pos {I : Type*} [Fintype I] [Nonempty I] (a : I → ℝ) :
    0 < ∑ i, Real.exp (a i) :=
  Finset.sum_pos (fun i _ => Real.exp_pos (a i)) Finset.univ_nonempty

/-- A common log-weight shift leaves every form fraction invariant. -/
theorem fraction_shift (a : F → ℝ) (i : F) (s : ℝ) :
    fraction (fun j => a j - s) i = fraction a i := by
  simp only [fraction, Real.exp_sub, ← Finset.sum_div]
  exact div_div_div_cancel_right₀ (Real.exp_ne_zero s) _ _

/-- The max-shifted log-sum-exp used by the engine computes the exact fraction. -/
theorem fraction_from_log_sum (a : F → ℝ) (i : F) (s : ℝ) :
    Real.exp (a i - (s + Real.log (∑ j, Real.exp (a j - s)))) = fraction a i := by
  letI : Nonempty F := ⟨i⟩
  rw [← sub_sub, Real.exp_sub, Real.exp_log (sum_exp_pos (fun j => a j - s))]
  exact fraction_shift a i s

/-- The probability of a registered form sums over all its microscopic states. -/
theorem fraction_grouped {M : F → Type*} [∀ i, Fintype (M i)] [∀ i, Nonempty (M i)]
    (a : (i : F) → M i → ℝ) (f : F) :
    fraction (fun i => Real.log (∑ j, Real.exp (a i j))) f =
      ∑ j : M f, fraction (fun z : Sigma M => a z.1 z.2) ⟨f, j⟩ := by
  simp only [fraction, Real.exp_log (sum_exp_pos _), ← Finset.sum_div, Fintype.sum_sigma]

/-- With a common ligand contribution, isomers can be combined once at standard activities. -/
theorem group_log_weight {I : Type*} [Fintype I] [Nonempty I] (b : I → ℝ) (w : ℝ) :
    Real.log (∑ j, Real.exp (b j + w)) = Real.log (∑ j, Real.exp (b j)) + w := by
  simp only [Real.exp_add, ← Finset.sum_mul]
  rw [Real.log_mul (sum_exp_pos b).ne' (Real.exp_ne_zero _), Real.log_exp]

/-- Dimensionless standard potential declared for a single stoichiometry in the registry. -/
def groupPotential {I : Type*} [Fintype I] (μ : I → ℝ) : ℝ :=
  -Real.log (∑ j, Real.exp (-μ j))

/-- At any fixed dimensionless ligand chemical potentials, the registered isomer group has
the summed microscopic occupancy. Each member of the group has the same ligand counts. -/
theorem binding_fraction_from_isomers {L : Type*} [Fintype L] {M : F → Type*}
    [∀ i, Fintype (M i)] [∀ i, Nonempty (M i)] (μ : (i : F) → M i → ℝ)
    (n : F → L → ℤ) (u : L → ℝ) (f : F) :
    fraction (fun i => logWeight (-groupPotential (μ i)) (n i) u) f =
      ∑ j : M f, fraction (fun z : Sigma M => logWeight (-μ z.1 z.2) (n z.1) u) ⟨f, j⟩ := by
  have collapse (i : F) : logWeight (-groupPotential (μ i)) (n i) u =
      Real.log (∑ j, Real.exp (logWeight (-μ i j) (n i) u)) := by
    simp only [logWeight, groupPotential, neg_neg, group_log_weight]
  simp_rw [collapse]
  exact fraction_grouped (fun i j => logWeight (-μ i j) (n i) u) f

/-- Each equal-energy microscopic state contributes once to the group multiplicity. -/
theorem equal_state_log_weight (I : Type*) [Fintype I] [Nonempty I] (a : ℝ) :
    Real.log (∑ _ : I, Real.exp a) = Real.log (Fintype.card I : ℝ) + a := by
  have hc : 0 < (Fintype.card I : ℝ) := Nat.cast_pos.mpr Fintype.card_pos
  simp [Real.log_mul hc.ne' (Real.exp_ne_zero a)]

end

end CellsProofs.Chemistry.BindingEnsemble
