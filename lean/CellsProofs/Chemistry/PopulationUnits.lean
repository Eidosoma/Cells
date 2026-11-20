import CellsProofs.Chemistry.SpeciesTurnover
import Mathlib.Algebra.BigOperators.Ring.Finset

/-! # From precursor molecules to functional units on a membrane

Amounts of precursor are in fmol. Pools, surface populations and the removal
ledger are in functional units. All fluxes in the material identities are
amounts moved over one interval.
-/

namespace CellsProofs.Chemistry.PopulationUnits

noncomputable section

open SpeciesTurnover (survival)

/-- Routes on one precursor and cell share its first-order consumption. -/
def consumed (amount rate total time : ℝ) : ℝ :=
  amount * (rate / total) * (1 - survival total time)

theorem shared_consumption {Route : Type*} [Fintype Route] (rate : Route → ℝ) (amount time : ℝ) :
    (∑ i, consumed amount (rate i) (∑ j, rate j) time) =
      amount * (1 - survival (∑ j, rate j) time) := by
  let total := ∑ j, rate j
  change (∑ i, consumed amount (rate i) total time) = amount * (1 - survival total time)
  by_cases h : total = 0
  · simp [consumed, h, survival]
  · simp only [consumed, div_eq_mul_inv, ← Finset.sum_mul, ← Finset.mul_sum]
    change amount * (total * total⁻¹) * _ = _
    rw [mul_inv_cancel₀ h, mul_one]

/-- A chain of any length, including zero pools for direct insertion. Edge zero
is assembly from the precursor and edge m is insertion into the surface. -/
theorem pool_balance (m : ℕ) (old moved : ℕ → ℝ) :
    (∑ j ∈ Finset.range m, (old j + moved j - moved (j + 1))) + moved m =
      (∑ j ∈ Finset.range m, old j) + moved 0 := by
  induction m with
  | zero => simp
  | succ m ih =>
    simp only [Finset.sum_range_succ]
    linarith

/-- Every initial or newly assembled unit is in transit, on the membrane or
in the sink. The sink also receives removal of pre-existing surface units. -/
theorem precursor_to_sink (m : ℕ) (old moved : ℕ → ℝ) (surface removed consumedFmol : ℝ)
    (moleculesPerFmol stoich : ℝ) (hs : stoich ≠ 0)
    (assembly : moved 0 = moleculesPerFmol / stoich * consumedFmol) :
    stoich * ((∑ j ∈ Finset.range m, (old j + moved j - moved (j + 1))) +
        (surface + moved m - removed) + removed - ((∑ j ∈ Finset.range m, old j) + surface)) =
      moleculesPerFmol * consumedFmol := by
  have net := pool_balance m old moved
  have h : (∑ j ∈ Finset.range m, (old j + moved j - moved (j + 1))) +
      (surface + moved m - removed) + removed - ((∑ j ∈ Finset.range m, old j) + surface) =
        moved 0 := by linarith
  rw [h, assembly]
  field_simp

/-- Routes can require different numbers of precursor molecules per functional unit.
Weighting each chain's net gain by its own stoichiometry recovers the group's consumption. -/
theorem mixed_stoichiometry {Route : Type*} [Fintype Route] (rate stoich gain : Route → ℝ)
    (amount time moleculesPerFmol : ℝ)
    (book : ∀ i, stoich i * gain i =
      moleculesPerFmol * consumed amount (rate i) (∑ j, rate j) time) :
    (∑ i, stoich i * gain i) = moleculesPerFmol * (amount * (1 - survival (∑ j, rate j) time)) := by
  simp_rw [book]
  rw [← Finset.mul_sum, shared_consumption]

/-- Multiplication of surviving fractions over successive intervals. -/
theorem cohort_survival (rate t u : ℝ) :
    survival rate (t + u) = survival rate t * survival rate u := by
  unfold SpeciesTurnover.survival
  rw [mul_add, neg_add, Real.exp_add]

/-- A pulse starts in the first of two identical maturation pools. With no
surface removal its cumulative insertion is U·(1 − (1 + kt) exp(−kt)). -/
def firstPool (units rate t : ℝ) : ℝ := units * survival rate t
def secondPool (units rate t : ℝ) : ℝ := units * (rate * t) * survival rate t
def arrived (units rate t : ℝ) : ℝ := units - firstPool units rate t - secondPool units rate t

theorem pulse_at_zero (units rate : ℝ) :
    firstPool units rate 0 = units ∧ secondPool units rate 0 = 0 ∧ arrived units rate 0 = 0 := by
  simp [arrived, firstPool, secondPool, survival]

/-- The functions solve the full two-pool chain, including the flux to the surface. -/
theorem pulse_derivatives (units rate t : ℝ) :
    HasDerivAt (firstPool units rate) (-rate * firstPool units rate t) t ∧
    HasDerivAt (secondPool units rate) (rate * (firstPool units rate t - secondPool units rate t)) t ∧
    HasDerivAt (arrived units rate) (rate * secondPool units rate t) t := by
  have hs : HasDerivAt (survival rate) (survival rate t * -rate) t := by
    unfold SpeciesTurnover.survival
    convert ((hasDerivAt_id t).const_mul rate).neg.exp using 1
    simp
  have h₁ : HasDerivAt (firstPool units rate) (-rate * firstPool units rate t) t := by
    convert hs.const_mul units using 1
    simp [firstPool]
    ring
  have h₂ : HasDerivAt (secondPool units rate)
      (rate * (firstPool units rate t - secondPool units rate t)) t := by
    convert (((hasDerivAt_id t).const_mul rate).const_mul units).mul hs using 1
    simp [firstPool, secondPool]
    ring
  refine ⟨h₁, h₂, ?_⟩
  convert ((hasDerivAt_const t units).sub h₁).sub h₂ using 1
  simp [arrived]
  ring

/-- An initially filled first pool produces some surface arrival for every positive
time. Slower early appearance is compatible with a positive detection threshold. -/
theorem positive_arrival {units rate t : ℝ} (hu : 0 < units) (hk : 0 < rate) (ht : 0 < t) :
    0 < arrived units rate t := by
  have hx := mul_pos hk ht
  have hlt : (1 + rate * t) / Real.exp (rate * t) < 1 :=
    (div_lt_one (Real.exp_pos _)).mpr (by linarith [Real.add_one_lt_exp hx.ne'])
  calc
    0 < units * (1 - (1 + rate * t) / Real.exp (rate * t)) :=
      mul_pos hu (sub_pos.mpr hlt)
    _ = arrived units rate t := by
      simp only [arrived, firstPool, secondPool, survival, Real.exp_neg, div_eq_mul_inv]
      ring

/-- The abundance seen by a channel, defined from the declared area and the
change in unit count. Reference density has units of functional units per m². -/
def abundance (a₀ area₀ area density change : ℝ) : ℝ :=
  a₀ * (area₀ / area) + change / (area * density)

theorem abundance_from_units (a₀ area₀ change : ℝ) {area density : ℝ}
    (ha : 0 < area) (hd : 0 < density) :
    abundance a₀ area₀ area density change = (a₀ * area₀ * density + change) / (area * density) := by
  unfold abundance
  field_simp
  ring

/-- At fixed single-channel drive and gating, whole-patch flow counts surface units.
Area changes can alter the flow per unit area while preserving total flow. -/
theorem whole_patch_flow (a₀ area₀ change drive : ℝ) {area density : ℝ}
    (ha : 0 < area) (hd : 0 < density) :
    drive * abundance a₀ area₀ area density change * area =
      drive * (a₀ * area₀ * density + change) / density := by
  rw [abundance_from_units _ _ _ ha hd]
  field_simp
  ring

theorem empty_surface (a₀ area₀ : ℝ) {area density : ℝ} (ha : 0 < area) (hd : 0 < density) :
    abundance a₀ area₀ area density (-(a₀ * area₀ * density)) = 0 := by
  rw [abundance_from_units _ _ _ ha hd]
  simp

end

end CellsProofs.Chemistry.PopulationUnits
