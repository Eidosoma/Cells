import CellsProofs.Transport.ATPCycle
import Mathlib.Algebra.Order.BigOperators.Group.Finset

/-! # Dissipation in deterministic assembly reactions

`deltaF` is the change in chemical potential along a reaction minus reservoir work,
in units of thermal energy. The engine evaluates `1 − exp deltaF` with `-expm1`.
-/

namespace CellsProofs.Chemistry.RateEquations

open CellsProofs.Transport
open scoped BigOperators

noncomputable def flux (enabled : Bool) (forward deltaF : ℝ) : ℝ :=
  if enabled then forward * (1 - Real.exp deltaF) else 0

theorem inactive (forward deltaF : ℝ) : flux false forward deltaF = 0 := rfl

theorem zero_forward (enabled : Bool) (deltaF : ℝ) : flux enabled 0 deltaF = 0 := by
  cases enabled <;> simp [flux]

/-- For a strictly positive forward rate, the free-energy drop determines direction and stall. -/
theorem direction_and_stall {forward : ℝ} (h : 0 < forward) (deltaF : ℝ) :
    (0 < flux true forward deltaF ↔ deltaF < 0) ∧
    (flux true forward deltaF < 0 ↔ 0 < deltaF) ∧
    (flux true forward deltaF = 0 ↔ deltaF = 0) := by
  have same : ATPCycle.flux true (Real.log forward) deltaF = flux true forward deltaF := by
    simpa only [flux, if_true, Real.exp_log h] using
      ATPCycle.flux_eq_mass_action (Real.log forward) deltaF
  rw [← same]
  exact ⟨ATPCycle.forward_iff _ _, ATPCycle.reverse_iff _ _, ATPCycle.stall_iff _ _⟩

theorem dissipation_nonneg (enabled : Bool) (forward deltaF : ℝ)
    (h : enabled = true → 0 ≤ forward) : 0 ≤ -flux enabled forward deltaF * deltaF := by
  cases enabled with
  | false => simp [inactive]
  | true =>
    rcases (h rfl).eq_or_lt with hz | hp
    · subst forward
      simp [zero_forward]
    · have hd := direction_and_stall hp deltaF
      rcases lt_trichotomy deltaF 0 with down | stall | up
      · exact mul_nonneg_of_nonpos_of_nonpos (neg_nonpos.mpr (hd.1.mpr down).le) down.le
      · simp [stall]
      · exact mul_nonneg (neg_nonneg.mpr (hd.2.1.mpr up).le) up.le

/-- Each reaction uses its own reservoir work and may be disabled independently. -/
theorem network_dissipation_nonneg {R : Type*} (reactions : Finset R)
    (enabled : R → Bool) (forward deltaF : R → ℝ)
    (h : ∀ r ∈ reactions, enabled r = true → 0 ≤ forward r) :
    0 ≤ ∑ r ∈ reactions, -flux (enabled r) (forward r) (deltaF r) * deltaF r :=
  Finset.sum_nonneg fun r hr => dissipation_nonneg _ _ _ (h r hr)

end CellsProofs.Chemistry.RateEquations
