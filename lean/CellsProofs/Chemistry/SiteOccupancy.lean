import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Ring

/-! # The site occupancy half-step

One SSPRK(3,3) increment is h times a stage rate. Cells bounds h times
each total outgoing rate coefficient by 1/2 at each stage.
-/

namespace CellsProofs.Chemistry.SiteOccupancy

/-- The incremental loss is relative to the available amount at this stage. -/
def Guard (amount delta : ℝ) : Prop :=
  ∃ loss gain : ℝ, loss ≤ 1 / 2 ∧ 0 ≤ gain ∧ delta = gain - loss * amount

/-- Binding at rate a per free site, release at b and internalisation at u. -/
theorem site_guards {h r s a b u : ℝ} (hh : 0 ≤ h) (hr : 0 ≤ r) (hs : 0 ≤ s)
    (ha : 0 ≤ a) (hbu : 0 ≤ b + u) (hfree : h * a ≤ 1 / 2)
    (hbound : h * (b + u) ≤ 1 / 2) :
    Guard r (-(h * (a * r - b * s - u * s))) ∧ Guard s (h * (a * r - b * s - u * s)) := by
  constructor
  · exact ⟨h * a, h * ((b + u) * s), hfree, mul_nonneg hh (mul_nonneg hbu hs), by ring⟩
  · exact ⟨h * (b + u), h * (a * r), hbound, mul_nonneg hh (mul_nonneg ha hr), by ring⟩

/-- Both populations consume the same pool. Their rate coefficients add
before the guard is tested. Release and any incoming cargo contribute to gain. -/
theorem shared_pool_guard {h n k₁ k₂ gain : ℝ} (hh : 0 ≤ h) (hg : 0 ≤ gain)
    (hload : h * (k₁ + k₂) ≤ 1 / 2) :
    Guard n (h * (gain - k₁ * n - k₂ * n)) :=
  ⟨h * (k₁ + k₂), h * gain, hload, mul_nonneg hh hg, by ring⟩

private theorem euler_lower {y d : ℝ} (hy : 0 ≤ y) (hg : Guard y d) :
    y / 2 ≤ y + d := by
  obtain ⟨l, g, hl, hp, rfl⟩ := hg
  linarith [mul_le_mul_of_nonneg_right hl hy]

/-- These are the second evaluation point, third evaluation point and final
booking in the engine's increment form. A positive starting pool stays
strictly positive, including when its two populations compete for ligand. -/
theorem ssprk_bounds {y d₁ d₂ d₃ : ℝ} (hy : 0 ≤ y)
    (h₁ : Guard y d₁) (h₂ : Guard (y + d₁) d₂)
    (h₃ : Guard (y + (d₁ + d₂) / 4) d₃) :
    y / 2 ≤ y + d₁ ∧ 13 * y / 16 ≤ y + (d₁ + d₂) / 4 ∧
      29 * y / 48 ≤ y + (d₁ + d₂ + 4 * d₃) / 6 := by
  have e₁ := euler_lower hy h₁
  have e₂ := euler_lower (by linarith : 0 ≤ y + d₁) h₂
  have e₃ := euler_lower (by linarith : 0 ≤ y + (d₁ + d₂) / 4) h₃
  exact ⟨e₁, by linarith, by linarith⟩

/-- Apply the stage conditions to a coupled network. Production at a stage
may depend on every pool and site being nonnegative. Only the initial state
needs an independent sign assumption. -/
theorem network_step {ι : Type*} (y d₁ d₂ d₃ : ι → ℝ) (hy : ∀ i, 0 ≤ y i)
    (h₁ : ∀ i, Guard (y i) (d₁ i))
    (h₂ : (∀ i, 0 ≤ y i + d₁ i) → ∀ i, Guard (y i + d₁ i) (d₂ i))
    (h₃ : (∀ i, 0 ≤ y i + (d₁ i + d₂ i) / 4) →
      ∀ i, Guard (y i + (d₁ i + d₂ i) / 4) (d₃ i)) :
    ∀ i, 29 * y i / 48 ≤ y i + (d₁ i + d₂ i + 4 * d₃ i) / 6 := by
  have stage₂ (i : ι) : 0 ≤ y i + d₁ i := by linarith [hy i, euler_lower (hy i) (h₁ i)]
  have stage₃ (i : ι) : 0 ≤ y i + (d₁ i + d₂ i) / 4 := by
    linarith [hy i, stage₂ i, euler_lower (stage₂ i) (h₂ stage₂ i)]
  exact fun i => (ssprk_bounds (hy i) (h₁ i) (h₂ stage₂ i) (h₃ stage₃ i)).2.2

/-- Free and bound sites use opposite increments at each evaluation.
After the full update both counts are nonnegative and sum to capacity. -/
theorem site_capacity_step {r b cap d₁ d₂ d₃ : ℝ}
    (hr : 0 ≤ r) (hb : 0 ≤ b) (hc : r + b = cap)
    (r₁ : Guard r (-d₁)) (r₂ : Guard (r - d₁) (-d₂))
    (r₃ : Guard (r - (d₁ + d₂) / 4) (-d₃))
    (b₁ : Guard b d₁) (b₂ : Guard (b + d₁) d₂) (b₃ : Guard (b + (d₁ + d₂) / 4) d₃) :
    let db := (d₁ + d₂ + 4 * d₃) / 6
    0 ≤ r - db ∧ 0 ≤ b + db ∧ (r - db) + (b + db) = cap := by
  dsimp only
  have s₁ : r + -d₁ = r - d₁ := by ring
  have s₂ : r + (-d₁ + -d₂) / 4 = r - (d₁ + d₂) / 4 := by ring
  have rf := (ssprk_bounds hr r₁ (s₁ ▸ r₂) (s₂ ▸ r₃)).2.2
  have bf := (ssprk_bounds hb b₁ b₂ b₃).2.2
  exact ⟨by linarith, by linarith, by linarith⟩

end CellsProofs.Chemistry.SiteOccupancy
