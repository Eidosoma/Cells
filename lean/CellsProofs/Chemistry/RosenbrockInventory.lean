import Mathlib.Analysis.Calculus.FDeriv.Comp
import Mathlib.Analysis.Calculus.FDeriv.Linear
import Mathlib.Tactic.Ring

/-! # Linear material inventories through a Rosenbrock step

A closed stoichiometric inventory annihilates every reaction change. Between events the
solver uses a fixed Jacobian, one scalar shift and only earlier stages on each right-hand side.
-/

namespace CellsProofs.Chemistry.RosenbrockInventory

open scoped BigOperators Topology

variable {V : Type*} [NormedAddCommGroup V] [NormedSpace ℝ V]
variable (L : V →L[ℝ] ℝ)

/-- Applies to reaction extents, earlier stages, and the dense-output coefficients. -/
theorem weighted_sum_zero {I : Type*} (s : Finset I) (weight : I → ℝ) (v : I → V)
    (balance : ∀ i ∈ s, L (v i) = 0) : L (∑ i ∈ s, weight i • v i) = 0 := by
  rw [map_sum]
  exact Finset.sum_eq_zero fun i hi => by simp [balance i hi]

/-- A balance near the step's start is also a left null vector of its exact Jacobian. -/
theorem jacobian_zero {f : V → V} {y : V} {J : V →L[ℝ] V}
    (derivative : HasFDerivAt f J y) (balance : (L ∘ f) =ᶠ[𝓝 y] fun _ => 0) (v : V) :
    L (J v) = 0 := by
  have zero := (L.hasFDerivAt.comp y derivative).congr_of_eventuallyEq balance.symm
  have h := zero.unique (hasFDerivAt_const (𝕜 := ℝ) (0 : ℝ) y)
  exact DFunLike.congr_fun h v

/-- In Rodas4, shift = 1/(γh), force i = f(Yᵢ), and coupling i j = Cᵢⱼ/h. -/
theorem stages_zero {n : ℕ} {shift : ℝ} (nonzero : shift ≠ 0)
    (J : V →L[ℝ] V) (stage force : ℕ → V) (coupling : ℕ → ℕ → ℝ)
    (jacobian : ∀ v, L (J v) = 0) (balanced : ∀ i < n, L (force i) = 0)
    (solve : ∀ i < n, shift • stage i - J (stage i) =
      force i + ∑ j ∈ Finset.range i, coupling i j • stage j) :
    ∀ i < n, L (stage i) = 0 := by
  intro i
  induction i using Nat.strong_induction_on with
  | h i prior =>
    intro hi
    have earlier := weighted_sum_zero L (Finset.range i) (coupling i) stage
      (fun j hj => prior j (Finset.mem_range.mp hj) (lt_trans (Finset.mem_range.mp hj) hi))
    have eq := congrArg L (solve i hi)
    rw [map_sub, map_smul, jacobian, sub_zero, map_add, balanced i hi, earlier, zero_add] at eq
    exact (mul_eq_zero.mp eq).resolve_left nonzero

theorem step_inventory {n : ℕ} (y : V) (stage : ℕ → V) (b : ℕ → ℝ)
    (balanced : ∀ i < n, L (stage i) = 0) :
    L (y + ∑ i ∈ Finset.range n, b i • stage i) = L y := by
  rw [map_add, weighted_sum_zero L _ _ _ (fun i hi => balanced i (Finset.mem_range.mp hi)),
    add_zero]

/-- The dense polynomial used for locating crossings shares the endpoint inventory. -/
theorem dense_inventory (y yNew k1 k2 : V) (θ : ℝ) (finish : L yNew = L y)
    (first : L k1 = 0) (second : L k2 = 0) :
    L ((1 - θ) • y + θ • (yNew + (1 - θ) • (k1 + θ • k2))) = L y := by
  simp only [map_add, map_smul, smul_eq_mul, finish, first, second, mul_zero, add_zero]
  ring

end CellsProofs.Chemistry.RosenbrockInventory
