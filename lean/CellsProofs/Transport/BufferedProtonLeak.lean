import CellsProofs.Chemistry.BindingEquilibrium
import CellsProofs.Transport.ProtonLeak

/-! # Free proton reads for the version-2 constant-field leak -/

namespace CellsProofs.Transport.BufferedProtonLeak

open CellsProofs.Chemistry.BindingEquilibrium CellsProofs.Transport.ProtonLeak

/-- At either endpoint a general binding closure fixes the proton read once the held
totals and unheld ligand activities are specified. This applies independently at the
two ends, which may carry different binders. Concentrations are expressed in mM. -/
theorem endpoint_read_unique {L B : Type*} [Fintype L] [DecidableEq L] [Fintype B]
    {F : B → Type*} [∀ b, Fintype (F b)] [∀ b, Nonempty (F b)]
    (T : B → ℝ) (hT : ∀ b, 0 ≤ T b) (logBeta : (b : B) → F b → ℝ)
    (n : (b : B) → F b → L → ℤ) (held : L → Bool) {u w : L → ℝ}
    (fixed : ∀ j, held j = false → u j = w j)
    (same : ∀ j, held j = true → total T logBeta n u j = total T logBeta n w j) (proton : L) :
    Real.exp (u proton) = Real.exp (w proton) := by
  rw [held_equilibrium_unique T hT logBeta n held fixed same]

/-- Inside-minus-outside reversal using the two *free* log concentrations at the
stage read. This covers zero voltage and the evaluator's regular branch. -/
theorem reversal_from_free_logs {scale rt faraday : ℝ} (hs : 0 < scale) (hrt : 0 < rt)
    (hf : 0 < faraday) (uIn uOut v : ℝ)
    (region : faraday * v / rt = 0 ∨ 1 / 10000 ≤ |faraday * v / rt|) :
    inward seriesFactor scale (Real.exp uIn) (Real.exp uOut) (faraday * v / rt) = 0 ↔
      v = rt / faraday * (uOut - uIn) := by
  rw [series_eq_analytic region, reversal_voltage_iff hs (Real.exp_pos _) (Real.exp_pos _) hrt hf,
    Real.log_exp, Real.log_exp]

end CellsProofs.Transport.BufferedProtonLeak
