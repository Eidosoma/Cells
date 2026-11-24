import CellsProofs.Chemistry.BindingEnsemble
import Mathlib.Analysis.Calculus.Deriv.Inv
import Mathlib.Analysis.Calculus.Deriv.MeanValue
import Mathlib.Analysis.SpecialFunctions.ExpDeriv
import Mathlib.Data.Real.StarOrdered
import Mathlib.LinearAlgebra.Matrix.PosDef

/-! Equilibrium response to a change in free log concentration, at fixed binder totals. -/

namespace CellsProofs.Chemistry.BindingResponse

open BindingEnsemble
open scoped BigOperators Matrix

noncomputable section

variable {F : Type*} [Fintype F] [Nonempty F]

/-- Average over the chemically present forms of one binder. -/
def mean (a g : F → ℝ) : ℝ := ∑ i, fraction a i * g i

private theorem partition_pos (a : F → ℝ) : 0 < ∑ i, Real.exp (a i) :=
  Finset.sum_pos (fun i _ => Real.exp_pos (a i)) Finset.univ_nonempty

private theorem fraction_sum (a : F → ℝ) : ∑ i, fraction a i = 1 := by
  simp [fraction, ← Finset.sum_div, (partition_pos a).ne']

omit [Nonempty F] in
private theorem mean_quotient (a g : F → ℝ) :
    mean a g = (∑ i, Real.exp (a i) * g i) / ∑ i, Real.exp (a i) := by
  simp only [mean, fraction, div_mul_eq_mul_div, Finset.sum_div]

/-- The raw moment used by the engine equals the weighted product of centered counts. -/
theorem covariance_eq_centered (a g h : F → ℝ) :
    mean a (fun i => g i * h i) - mean a g * mean a h =
      ∑ i, fraction a i * (g i - mean a g) * (h i - mean a h) := by
  have term (i : F) : fraction a i * (g i - mean a g) * (h i - mean a h) =
      fraction a i * (g i * h i) - fraction a i * g i * mean a h -
        fraction a i * h i * mean a g + fraction a i * (mean a g * mean a h) := by ring
  simp_rw [term]
  rw [Finset.sum_add_distrib, Finset.sum_sub_distrib, Finset.sum_sub_distrib]
  simp only [← Finset.sum_mul, fraction_sum, one_mul]
  unfold mean
  ring

/-- Along affine log weights, the derivative of a mean is its covariance with the slope. -/
theorem hasDerivAt_mean (a q g : F → ℝ) (t : ℝ) :
    let w := fun i => a i + t * q i
    HasDerivAt (fun s => mean (fun i => a i + s * q i) g)
      (mean w (fun i => g i * q i) - mean w g * mean w q) t := by
  dsimp only
  have weight (i : F) : HasDerivAt (fun s => Real.exp (a i + s * q i))
      (Real.exp (a i + t * q i) * q i) t := by
    simpa using (((hasDerivAt_id t).mul_const (q i)).const_add (a i)).exp
  have den := HasDerivAt.sum (u := Finset.univ) (fun i _ => weight i)
  have num := HasDerivAt.sum (u := Finset.univ) (fun i _ => (weight i).mul_const (g i))
  simp_rw [mean_quotient]
  convert num.div den (partition_pos (fun i => a i + t * q i)).ne' using 1
  have swap (i : F) : Real.exp (a i + t * q i) * q i * g i =
      Real.exp (a i + t * q i) * (g i * q i) := by ring
  simp_rw [swap]
  field_simp
  ring

variable {B L : Type*} [Fintype B] [Fintype L] {Forms : B → Type*}
  [∀ b, Fintype (Forms b)] [∀ b, Nonempty (Forms b)]

/-- Total of a ligand when its free log concentration is `t`. The intercepts include the
fixed activities of the other ligands. Counts relative to the base form can have either sign. -/
def totalAlong (T : B → ℝ) (a n : (b : B) → Forms b → ℝ) (t : ℝ) : ℝ :=
  Real.exp t + ∑ b, T b * mean (fun i => a b i + t * n b i) (n b)

/-- The self response is strictly positive, even when a form releases a ligand. -/
theorem totalAlong_strictMono (T : B → ℝ) (hT : ∀ b, 0 ≤ T b)
    (a n : (b : B) → Forms b → ℝ) : StrictMono (totalAlong T a n) := by
  apply strictMono_of_deriv_pos
  intro t
  have d := (Real.hasDerivAt_exp t).add (HasDerivAt.sum (u := Finset.univ)
    (fun b _ => (hasDerivAt_mean (a b) (n b) (n b) t).const_mul (T b)))
  rw [show deriv (totalAlong T a n) t = _ from d.deriv]
  apply add_pos_of_pos_of_nonneg (Real.exp_pos _)
  apply Finset.sum_nonneg
  intro b _
  apply mul_nonneg (hT b)
  rw [covariance_eq_centered]
  apply Finset.sum_nonneg
  intro i _
  rw [mul_assoc]
  exact mul_nonneg (div_nonneg (Real.exp_pos _).le (partition_pos _).le) (mul_self_nonneg _)

/-- On the physical domain, increasing free concentration strictly increases its own total. -/
theorem total_strictMonoOn_free (T : B → ℝ) (hT : ∀ b, 0 ≤ T b)
    (a n : (b : B) → Forms b → ℝ) :
    StrictMonoOn (fun x => totalAlong T a n (Real.log x)) (Set.Ioi 0) :=
  fun _ hx _ hy hxy => totalAlong_strictMono T hT a n (Real.strictMonoOn_log hx hy hxy)

variable [DecidableEq L]

/-- Changing a single log concentration gives the affine form weights used in the derivative. -/
theorem logWeight_perturb (b : ℝ) (n : L → ℤ) (u : L → ℝ) (k : L) (t : ℝ) :
    logWeight b n (fun j => u j + if j = k then t else 0) = logWeight b n u + t * n k := by
  simp [logWeight, mul_add, Finset.sum_add_distrib, mul_ite, mul_comm t, add_assoc]

/-- One binder's contribution to the Jacobian of ligand totals with respect to log activities. -/
def binderResponse (T : ℝ) (a : F → ℝ) (n : F → L → ℝ) : Matrix L L ℝ := fun j k =>
  T * (mean a (fun i => n i j * n i k) - mean a (fun i => n i j) * mean a (fun i => n i k))

omit [DecidableEq L] in
private theorem binderResponse_posSemidef (T : ℝ) (hT : 0 ≤ T) (a : F → ℝ) (n : F → L → ℝ) :
    (binderResponse T a n).PosSemidef := by
  classical
  let X : Matrix F L ℝ := fun i j => n i j - mean a (fun f => n f j)
  have weights : 0 ≤ fun i => T * fraction a i := fun i =>
    mul_nonneg hT (div_nonneg (Real.exp_pos _).le (partition_pos _).le)
  convert (Matrix.PosSemidef.diagonal weights).conjTranspose_mul_mul_same X using 1
  ext j k
  rw [Matrix.mul_apply]
  simp only [binderResponse, covariance_eq_centered, Finset.mul_sum,
    Matrix.mul_diagonal, Matrix.conjTranspose_apply, star_trivial, X]
  apply Finset.sum_congr rfl
  intro i _
  ring

/-- The Hessian used by rapid binding is the free diagonal plus the binder covariances. -/
def response (x : L → ℝ) (T : B → ℝ) (a : (b : B) → Forms b → ℝ)
    (n : (b : B) → Forms b → L → ℝ) : Matrix L L ℝ :=
  Matrix.diagonal x + ∑ b, binderResponse (T b) (a b) (n b)

omit [Fintype L] in
/-- Each matrix entry differentiates the actual total of `j` when log concentration `k`
is changed by `t` from the current state. -/
theorem response_entry_hasDerivAt (x : L → ℝ) (T : B → ℝ) (a : (b : B) → Forms b → ℝ)
    (n : (b : B) → Forms b → L → ℝ) (j k : L) :
    HasDerivAt (fun t => (if j = k then x j * Real.exp t else x j) +
      ∑ b, T b * mean (fun i => a b i + t * n b i k) (fun i => n b i j))
      (response x T a n j k) 0 := by
  have free : HasDerivAt (fun t => if j = k then x j * Real.exp t else x j)
      (Matrix.diagonal x j k) 0 := by
    by_cases h : j = k
    · simpa [h] using (Real.hasDerivAt_exp 0).const_mul (x j)
    · simpa [h, Matrix.diagonal_apply] using (hasDerivAt_const (0 : ℝ) (x j))
  have bound := HasDerivAt.sum (u := Finset.univ) (fun b _ =>
    (hasDerivAt_mean (a b) (fun i => n b i k) (fun i => n b i j) 0).const_mul (T b))
  simpa [response, Matrix.sum_apply, binderResponse] using free.add bound

/-- Any finite collection of nonnegative binder totals preserves strict positive definiteness. -/
theorem response_posDef (x : L → ℝ) (hx : ∀ j, 0 < x j) (T : B → ℝ) (hT : ∀ b, 0 ≤ T b)
    (a : (b : B) → Forms b → ℝ) (n : (b : B) → Forms b → L → ℝ) :
    (response x T a n).PosDef := by
  classical
  apply (Matrix.PosDef.diagonal hx).add_posSemidef
  have psd (s : Finset B) : (∑ b ∈ s, binderResponse (T b) (a b) (n b)).PosSemidef := by
    induction s using Finset.induction_on with
    | empty => simpa using (Matrix.PosSemidef.zero : (0 : Matrix L L ℝ).PosSemidef)
    | insert b s h ih =>
      simpa [Finset.sum_insert h] using (binderResponse_posSemidef _ (hT b) (a b) (n b)).add ih
  exact psd Finset.univ

/-- The engine restricts to held ligands and fills the other coordinates with an identity.
The free activities of unheld ligands still contribute to the form weights `a`. -/
theorem masked_response_posDef (held : L → Bool) (x : L → ℝ) (hx : ∀ j, 0 < x j)
    (T : B → ℝ) (hT : ∀ b, 0 ≤ T b) (a : (b : B) → Forms b → ℝ)
    (n : (b : B) → Forms b → L → ℝ) :
    Matrix.PosDef (fun j k => if held j && held k then response x T a n j k
      else (1 : Matrix L L ℝ) j k) := by
  let d := fun j => if held j then x j else 1
  let m := fun b (i : Forms b) j => if held j then n b i j else 0
  have hd (j : L) : 0 < d j := by simp only [d]; split <;> simp [hx]
  convert response_posDef d hd T hT a m using 1
  ext j k
  cases hj : held j <;> cases hk : held k <;>
    by_cases h : j = k <;>
    simp_all [response, binderResponse, mean, Matrix.diagonal_apply, Matrix.one_apply,
      Matrix.sum_apply, d, m]

/-- At fixed binder totals and other free ligands, the increase in total concentration
is at least the increase in free concentration between any two positive doses. -/
theorem free_increment_le_total_increment (T : B → ℝ) (hT : ∀ b, 0 ≤ T b)
    (a n : (b : B) → Forms b → ℝ) {x y : ℝ} (hx : 0 < x) (hxy : x ≤ y) :
    y - x ≤ totalAlong T a n (Real.log y) - totalAlong T a n (Real.log x) := by
  have hy := hx.trans_le hxy
  have log_le := Real.strictMonoOn_log.monotoneOn hx hy hxy
  have means (b : B) : Monotone (fun t => mean (fun i => a b i + t * n b i) (n b)) := by
    apply monotone_of_deriv_nonneg
    · exact fun t => (hasDerivAt_mean (a b) (n b) (n b) t).differentiableAt
    · intro t
      rw [(hasDerivAt_mean (a b) (n b) (n b) t).deriv, covariance_eq_centered]
      apply Finset.sum_nonneg
      intro i _
      rw [mul_assoc]
      exact mul_nonneg (div_nonneg (Real.exp_pos _).le (partition_pos _).le) (mul_self_nonneg _)
  have bound := Finset.sum_le_sum (s := Finset.univ)
    (fun b _ => mul_le_mul_of_nonneg_left (means b log_le) (hT b))
  simp only [totalAlong, Real.exp_log hx, Real.exp_log hy]
  linarith

end

end CellsProofs.Chemistry.BindingResponse
