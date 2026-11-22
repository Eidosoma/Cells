import CellsProofs.Tissue.RestrictedLumen
import CellsProofs.Transport.LabelMixingPower
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

/-- Relative entropy of normalized label fractions in the neutral face power decomposition. -/
theorem label_divergence_eq_klFun {p q : ℝ} (hp : 0 < p) (hq : 0 < q) :
    Transport.LabelMixingPower.divergenceTerm p q = q * InformationTheory.klFun (p / q) := by
  rw [Transport.LabelMixingPower.divergenceTerm, InformationTheory.klFun_apply,
    Real.log_div hq.ne' hp.ne', Real.log_div hp.ne' hq.ne']
  field_simp
  ring

#print axioms label_divergence_eq_klFun

end CellsProofs.Checks
