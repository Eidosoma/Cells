import CellsProofs.Tissue.RestrictedLumen
import Mathlib.InformationTheory.KullbackLeibler.KLFun

namespace CellsProofs.Checks

open Tissue.RestrictedLumen (phi)

/-- Both laws use the same ideal mixing term at a dimensionless concentration ratio. -/
theorem phi_eq_klFun (r : ℝ) : phi r = InformationTheory.klFun r := by
  unfold phi InformationTheory.klFun
  ring

theorem mixing_term_sign {r : ℝ} (hr : 0 ≤ r) : 0 ≤ phi r ∧ (phi r = 0 ↔ r = 1) := by
  rw [phi_eq_klFun]
  exact ⟨InformationTheory.klFun_nonneg hr, InformationTheory.klFun_eq_zero_iff hr⟩

#print axioms mixing_term_sign

end CellsProofs.Checks
