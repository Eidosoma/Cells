import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Analysis.SpecialFunctions.Log.Basic
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Ring

/-! # Scheduled replacement at fixed tissue sites

An arrival is either a declared value or a copy of a donor's pre-event value.
An amount is in fmol, a volume in pL and an energy in pJ.
-/

namespace CellsProofs.Tissue.CellReplacement

noncomputable section

inductive Source (Site Value : Type*) where
  | template (value : Value)
  | donor (site : Site)

def incoming {Site Value : Type*} (old : Site → Value) : Source Site Value → Value
  | .template value => value
  | .donor site => old site

def afterEvent {Site Value : Type*} [DecidableEq Site] (due : Finset Site)
    (old : Site → Value) (source : Site → Source Site Value) (i : Site) : Value :=
  if i ∈ due then incoming old (source i) else old i

/-- Both sites can be due together. The receiver sees the donor before the donor is replaced. -/
theorem simultaneous_copy {Site Value : Type*} [DecidableEq Site] (due : Finset Site)
    (old : Site → Value) (source : Site → Source Site Value) {i j : Site} {v : Value}
    (hi : i ∈ due) (hj : j ∈ due) (hcopy : source i = .donor j)
    (htemplate : source j = .template v) :
    afterEvent due old source i = old j ∧ afterEvent due old source j = v := by
  simp [afterEvent, hi, hj, hcopy, htemplate, incoming]

/-- Applies separately to each species and, for v2, to cell volume. -/
theorem gross_balance {Site : Type*} [Fintype Site] [DecidableEq Site] (due : Finset Site)
    (old : Site → ℝ) (source : Site → Source Site ℝ) :
    (∑ i, afterEvent due old source i) - ∑ i, old i =
      (∑ i ∈ due, incoming old (source i)) - ∑ i ∈ due, old i := by
  rw [← Finset.sum_sub_distrib, ← Finset.sum_sub_distrib]
  have h (i : Site) : afterEvent due old source i - old i =
      if i ∈ due then incoming old (source i) - old i else 0 := by
    by_cases hi : i ∈ due <;> simp [afterEvent, hi]
  simp [h, Finset.sum_ite_mem]

/-- Valence-weighted net supply gives the signed change in cell charge. -/
theorem booked_charge {S : Type*} [Fintype S] (faraday : ℝ) (z old arrival : S → ℝ) :
    faraday * (∑ s, z s * (arrival s - old s)) =
      faraday * ((∑ s, z s * arrival s) - ∑ s, z s * old s) := by
  simp [mul_sub, Finset.sum_sub_distrib]

/-- Equal shares of field energy less electrode work book the field change exactly once. -/
theorem shared_field_energy {Site : Type*} (due : Finset Site) (hd : due.Nonempty)
    (chemical : Site → ℝ) (field electrode : ℝ) :
    (∑ i ∈ due, (chemical i + (field - electrode) / due.card)) + electrode =
      (∑ i ∈ due, chemical i) + field := by
  have hn : (due.card : ℝ) ≠ 0 := Nat.cast_ne_zero.mpr (Finset.card_ne_zero.mpr hd)
  simp only [Finset.sum_add_distrib, Finset.sum_const, nsmul_eq_mul]
  field_simp
  ring

/-- A strictly interior template stays interior when stored as an exact offset. -/
theorem template_volume_interior {v lower upper : ℝ} (ref : ℝ) (hl : lower < v) (hu : v < upper) :
    lower < ref + (v - ref) ∧ ref + (v - ref) < upper := by
  simpa [add_sub_cancel] using And.intro hl hu

/-- Copying an increment reproduces its donor's absolute volume precisely when references agree. -/
theorem donor_volume (receiverRef donorRef increment : ℝ) :
    receiverRef + increment = donorRef + increment ↔ receiverRef = donorRef := add_left_inj _

def ideal (amount volume : ℝ) : ℝ := amount * (Real.log (amount / volume) - 1)

/-- The ideal chemical term at the declared reference volume plus its osmotic correction. -/
theorem ideal_at_volume {n v ref : ℝ} (hn : 0 < n) (hv : 0 < v) (hr : 0 < ref) :
    ideal n v = ideal n ref - n * Real.log (v / ref) := by
  simp only [ideal, Real.log_div hn.ne' hv.ne', Real.log_div hn.ne' hr.ne',
    Real.log_div hv.ne' hr.ne']
  ring

/-- The composition-dependent part includes the fixed extra impermeant amount.
The elastic term can be evaluated independently at each endpoint. -/
def water (rt extra ref n v elastic : ℝ) : ℝ :=
  -rt * (n + extra) * Real.log (v / ref) + elastic

/-- Adding the water booking evaluates every tracked species at its physical volume.
The extra fixed osmoles and elastic energy are each counted once. -/
theorem physical_endpoint {S : Type*} [Fintype S] (n : S → ℝ) (hn : ∀ s, 0 < n s)
    {v ref : ℝ} (hv : 0 < v) (hr : 0 < ref) (rt extra elastic : ℝ) :
    rt * (∑ s, ideal (n s) ref) + water rt extra ref (∑ s, n s) v elastic =
      rt * (∑ s, ideal (n s) v) - rt * extra * Real.log (v / ref) + elastic := by
  simp only [water, fun s => ideal_at_volume (hn s) hv hr, Finset.sum_sub_distrib,
    ← Finset.sum_mul]
  ring

/-- The endpoint subtraction includes a term for replacing osmoles, even if volume is unchanged. -/
theorem water_jump {v₀ v₁ ref : ℝ} (h₀ : 0 < v₀) (h₁ : 0 < v₁) (hr : 0 < ref)
    (rt extra n₀ n₁ e₀ e₁ : ℝ) :
    water rt extra ref n₁ v₁ e₁ - water rt extra ref n₀ v₀ e₀ =
      -rt * (n₀ + extra) * Real.log (v₁ / v₀) -
        rt * (n₁ - n₀) * Real.log (v₁ / ref) + (e₁ - e₀) := by
  simp only [water, Real.log_div h₀.ne' hr.ne', Real.log_div h₁.ne' hr.ne',
    Real.log_div h₁.ne' h₀.ne']
  ring

theorem same_volume_water_jump (rt extra ref n₀ n₁ v e : ℝ) :
    water rt extra ref n₁ v e - water rt extra ref n₀ v e =
      -rt * (n₁ - n₀) * Real.log (v / ref) := by
  unfold water
  ring

end

end CellsProofs.Tissue.CellReplacement
