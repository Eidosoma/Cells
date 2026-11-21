import CellsProofs.Chemistry.BindingResponse

/-! Uniqueness of a finite binding equilibrium with prescribed ligand and binder totals. -/

namespace CellsProofs.Chemistry.BindingEquilibrium

open BindingEnsemble BindingResponse
open scoped BigOperators Matrix

noncomputable section

variable {L B : Type*} [Fintype L] [Fintype B] {F : B → Type*} [∀ b, Fintype (F b)]

/-- Free concentration plus the signed bound equivalents in each ligand row, in mM. -/
def total (T : B → ℝ) (logBeta : (b : B) → F b → ℝ) (n : (b : B) → F b → L → ℤ)
    (u : L → ℝ) (j : L) : ℝ :=
  Real.exp (u j) + ∑ b, T b * mean (fun i => logWeight (logBeta b i) (n b i) u)
    (fun i => (n b i j : ℝ))

private theorem logWeight_line (a : ℝ) (n : L → ℤ) (u v : L → ℝ) (t : ℝ) :
    logWeight a n (fun j => u j + t * v j) = logWeight a n u + t * ∑ j, (n j : ℝ) * v j := by
  simp [logWeight, mul_add, Finset.sum_add_distrib, Finset.mul_sum, mul_left_comm, add_assoc]

private theorem mean_sum_mul {I : Type*} [Fintype I] (a : I → ℝ) (n : I → L → ℝ) (v : L → ℝ) :
    mean a (fun i => ∑ k, n i k * v k) = ∑ k, mean a (fun i => n i k) * v k := by
  simp only [mean, Finset.mul_sum, Finset.sum_mul, mul_assoc]
  exact Finset.sum_comm

private theorem covariance_direction {I : Type*} [Fintype I] (a g : I → ℝ) (n : I → L → ℝ)
    (v : L → ℝ) :
    mean a (fun i => g i * ∑ k, n i k * v k) - mean a g * mean a (fun i => ∑ k, n i k * v k) =
      ∑ k, (mean a (fun i => g i * n i k) - mean a g * mean a (fun i => n i k)) * v k := by
  simp_rw [Finset.mul_sum, ← mul_assoc, mean_sum_mul]
  simp only [Finset.mul_sum, Finset.sum_sub_distrib, sub_mul, mul_assoc]

variable [DecidableEq L]

private theorem response_mulVec (x : L → ℝ) (T : B → ℝ) (a : (b : B) → F b → ℝ)
    (n : (b : B) → F b → L → ℝ) (v : L → ℝ) (j : L) :
    (response x T a n *ᵥ v) j = x j * v j + ∑ b, T b *
      (mean (a b) (fun i => n b i j * ∑ k, n b i k * v k) -
        mean (a b) (fun i => n b i j) * mean (a b) (fun i => ∑ k, n b i k * v k)) := by
  rw [response, Matrix.add_mulVec, Pi.add_apply, Matrix.mulVec_diagonal]
  congr 1
  simp only [Matrix.mulVec, dotProduct, Matrix.sum_apply, Finset.sum_mul]
  rw [Finset.sum_comm]
  apply Finset.sum_congr rfl
  intro b _
  rw [covariance_direction, Finset.mul_sum]
  simp only [binderResponse, mul_assoc]

variable [∀ b, Nonempty (F b)]

/-- When several log concentrations change at once, the whole response matrix acts on the
change vector. This differentiates the same total used in the conservation residual. -/
theorem total_hasDerivAt_line (T : B → ℝ) (logBeta : (b : B) → F b → ℝ)
    (n : (b : B) → F b → L → ℤ) (u v : L → ℝ) (t : ℝ) (j : L) :
    let w := fun k => u k + t * v k
    HasDerivAt (fun s => total T logBeta n (fun k => u k + s * v k) j)
      ((response (fun k => Real.exp (w k)) T (fun b i => logWeight (logBeta b i) (n b i) w)
        (fun b i k => (n b i k : ℝ)) *ᵥ v) j) t := by
  dsimp only
  have free : HasDerivAt (fun s => Real.exp (u j + s * v j))
      (Real.exp (u j + t * v j) * v j) t := by
    simpa using (((hasDerivAt_id t).mul_const (v j)).const_add (u j)).exp
  have bound := HasDerivAt.sum (u := Finset.univ) (fun b _ =>
    (hasDerivAt_mean (fun i => logWeight (logBeta b i) (n b i) u)
      (fun i => ∑ k, (n b i k : ℝ) * v k) (fun i => (n b i j : ℝ)) t).const_mul (T b))
  simpa only [total, response_mulVec, logWeight_line] using free.add bound

/-- For any distinct states, the total change has strictly positive projection on the joint
change in free log concentrations. Signed counts and zero binder totals are allowed. -/
theorem total_pairing_pos (T : B → ℝ) (hT : ∀ b, 0 ≤ T b) (logBeta : (b : B) → F b → ℝ)
    (n : (b : B) → F b → L → ℤ) {u w : L → ℝ} (hne : u ≠ w) :
    0 < dotProduct (w - u) (total T logBeta n w - total T logBeta n u) := by
  let v := w - u
  have hv : v ≠ 0 := sub_ne_zero.mpr (Ne.symm hne)
  have mono : StrictMono (fun s : ℝ => dotProduct v (total T logBeta n (fun j => u j + s * v j))) := by
    apply strictMono_of_deriv_pos
    intro t
    have d := HasDerivAt.sum (u := Finset.univ) (fun j _ =>
      (total_hasDerivAt_line T logBeta n u v t j).const_mul (v j))
    change 0 < deriv (fun s : ℝ => ∑ j, v j * total T logBeta n (fun k => u k + s * v k) j) t
    rw [d.deriv]
    simpa [dotProduct] using (response_posDef (fun j => Real.exp (u j + t * v j))
      (fun j => Real.exp_pos _) T hT (fun b i => logWeight (logBeta b i) (n b i) (fun k => u k + t * v k))
      (fun b i k => (n b i k : ℝ))).2 v hv
  have first : (fun j => u j + (0 : ℝ) * v j) = u := by simp
  have last : (fun j => u j + (1 : ℝ) * v j) = w := by funext j; simp [v]
  have step := mono (show (0 : ℝ) < 1 by norm_num)
  change dotProduct v (total T logBeta n (fun j => u j + 0 * v j)) <
    dotProduct v (total T logBeta n (fun j => u j + 1 * v j)) at step
  rw [first, last] at step
  rw [dotProduct_sub]
  exact sub_pos.mpr step

/-- Fix every unheld free ligand as the engine does. Agreement of the held ligand totals then
determines the entire equilibrium free vector whenever a solution exists. -/
theorem held_equilibrium_unique (T : B → ℝ) (hT : ∀ b, 0 ≤ T b) (logBeta : (b : B) → F b → ℝ)
    (n : (b : B) → F b → L → ℤ) (held : L → Bool) {u w : L → ℝ}
    (fixed : ∀ j, held j = false → u j = w j)
    (same : ∀ j, held j = true → total T logBeta n u j = total T logBeta n w j) : u = w := by
  by_contra hne
  have pos := total_pairing_pos T hT logBeta n hne
  have zero : dotProduct (w - u) (total T logBeta n w - total T logBeta n u) = 0 := by
    apply Finset.sum_eq_zero
    intro j _
    cases hj : held j
    · simp [fixed j hj]
    · simp [same j hj]
  exact (ne_of_gt pos) zero

/-- Any measured group of a binder's equilibrium forms also has one concentration. -/
theorem equilibrium_group_unique (T : B → ℝ) (hT : ∀ b, 0 ≤ T b) (logBeta : (b : B) → F b → ℝ)
    (n : (b : B) → F b → L → ℤ) (held : L → Bool) {u w : L → ℝ}
    (fixed : ∀ j, held j = false → u j = w j)
    (same : ∀ j, held j = true → total T logBeta n u j = total T logBeta n w j)
    (b : B) (forms : Finset (F b)) :
    (∑ i ∈ forms, T b * fraction (fun f => logWeight (logBeta b f) (n b f) u) i) =
      ∑ i ∈ forms, T b * fraction (fun f => logWeight (logBeta b f) (n b f) w) i := by
  rw [held_equilibrium_unique T hT logBeta n held fixed same]

/-- There is at most one positive free concentration vector at the prescribed totals. -/
theorem positive_free_unique (T : B → ℝ) (hT : ∀ b, 0 ≤ T b) (logBeta : (b : B) → F b → ℝ)
    (n : (b : B) → F b → L → ℤ) {x y : L → ℝ} (hx : ∀ j, 0 < x j) (hy : ∀ j, 0 < y j)
    (same : total T logBeta n (fun j => Real.log (x j)) = total T logBeta n (fun j => Real.log (y j))) :
    x = y := by
  have h := held_equilibrium_unique T hT logBeta n (fun _ => true) (fun _ => by simp)
    (fun j _ => congrFun same j)
  funext j
  simpa only [Real.exp_log (hx j), Real.exp_log (hy j)] using congrArg Real.exp (congrFun h j)

end

end CellsProofs.Chemistry.BindingEquilibrium
