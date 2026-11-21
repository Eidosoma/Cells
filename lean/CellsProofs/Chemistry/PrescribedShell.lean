import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Ring

/-! Propensity of a prescribed shell and its gate on the pair's common state (FR-21). -/

namespace CellsProofs.Chemistry.PrescribedShell

open scoped BigOperators
noncomputable section

variable {Species : Type*}

/-- Counts are taken only over the declared gate forms. An absent gate leaves the rate alone. -/
def gateMean (forms : Finset Species) (count : Species → ℕ) (weight : Species → ℝ) : ℝ :=
  let n := ∑ i ∈ forms, count i
  if n = 0 then 1 else (∑ i ∈ forms, (count i : ℝ) * weight i) / n

theorem gate_unchanged (forms : Finset Species) {a b : Species → ℕ} (weight : Species → ℝ)
    (same : ∀ i ∈ forms, a i = b i) : gateMean forms a weight = gateMean forms b weight := by
  have total : (∑ i ∈ forms, a i) = ∑ i ∈ forms, b i := Finset.sum_congr rfl same
  have weighted : (∑ i ∈ forms, (a i : ℝ) * weight i) = ∑ i ∈ forms, (b i : ℝ) * weight i :=
    Finset.sum_congr rfl (fun i hi => by rw [same i hi])
  simp only [gateMean, total, weighted]

theorem absent_gate (forms : Finset Species) (count : Species → ℕ) (weight : Species → ℝ)
    (empty : ∀ i ∈ forms, count i = 0) : gateMean forms count weight = 1 := by
  simp [gateMean, Finset.sum_eq_zero empty]

def rate (permeability area density activity gate : ℝ) :=
  permeability * area * density * activity * gate

/-- A fixed area–permeability product fixes entry and exit separately, at their own activities. -/
theorem same_conductance {p₁ a₁ p₂ a₂ : ℝ} (same : p₁ * a₁ = p₂ * a₂)
    (density outside inside gate : ℝ) :
    rate p₁ a₁ density outside gate = rate p₂ a₂ density outside gate ∧
    rate p₁ a₁ density inside gate = rate p₂ a₂ density inside gate := by simp [rate, same]

/-- A gate on the common state scales both rates and preserves their activity ratio. -/
theorem paired_rates (p area density outside inside gate : ℝ) :
    rate p area density outside gate * inside = rate p area density inside gate * outside := by
  unfold rate
  ring

end
end CellsProofs.Chemistry.PrescribedShell
