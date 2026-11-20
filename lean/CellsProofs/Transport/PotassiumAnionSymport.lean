import Mathlib.Analysis.SpecialFunctions.ExpDeriv
import Mathlib.Analysis.SpecialFunctions.Log.Basic
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Ring

/-! # Volume-activated, electroneutral potassium–anion symport

Positive cycles carry one potassium and one monovalent anion out of the cell.
The rate scale is capacity times availability times the volume factor.
`inside` and `outside` are the two concentration products in mM².
-/

namespace CellsProofs.Transport.PotassiumAnionSymport

noncomputable section

def volumeFactor (volume setVolume steepness : ℝ) : ℝ :=
  Real.exp ((volume - setVolume) / (steepness * setVolume))

theorem fractional_volume_response {setVolume steepness : ℝ} (hv : 0 < setVolume)
    (hs : 0 < steepness) (fraction : ℝ) :
    volumeFactor ((1 + fraction) * setVolume) setVolume steepness =
      Real.exp (fraction / steepness) := by
  unfold volumeFactor
  congr 1
  field_simp [hv.ne', hs.ne']
  ring

def cycles (scale inside outside : ℝ) : ℝ := scale * (inside - outside)

theorem outward_iff {scale : ℝ} (active : 0 < scale) (inside outside : ℝ) :
    0 < cycles scale inside outside ↔ outside < inside := by
  rw [cycles, mul_pos_iff_of_pos_left active, sub_pos]

theorem stall_iff {scale : ℝ} (active : 0 < scale) (inside outside : ℝ) :
    cycles scale inside outside = 0 ↔ inside = outside := by
  rw [cycles, mul_eq_zero, or_iff_right active.ne', sub_eq_zero]

/-- The normalized external cation concentration at reversal has unit slope
against the inside/outside anion ratio when concentrations stand for activities. -/
theorem normalized_reversal {scale ki ao : ℝ} (active : 0 < scale) (hk : 0 < ki)
    (ha : 0 < ao) (ai ko : ℝ) :
    cycles scale (ki * ai) (ko * ao) = 0 ↔ ko / ki = ai / ao := by
  rw [stall_iff active, div_eq_div_iff hk.ne' ha.ne', mul_comm ai ki]
  exact eq_comm

def affinity (rt inside outside : ℝ) : ℝ := rt * Real.log (inside / outside)

/-- Opposite electrical work terms cancel for the two monovalent ions.
The equivalent sum of logs also avoids forming a concentration-product ratio. -/
theorem electrochemical_sum {ki ai ko ao : ℝ} (hk : 0 < ki) (ha : 0 < ai)
    (hk' : 0 < ko) (ha' : 0 < ao) (rt electrical : ℝ) :
    affinity rt (ki * ai) (ko * ao) =
      (rt * (Real.log ki - Real.log ko) + electrical) +
      (rt * (Real.log ai - Real.log ao) - electrical) := by
  rw [affinity, Real.log_div (mul_pos hk ha).ne' (mul_pos hk' ha').ne',
    Real.log_mul hk.ne' ha.ne', Real.log_mul hk'.ne' ha'.ne']
  ring

theorem heat_nonneg {scale rt inside outside : ℝ} (hk : 0 ≤ scale) (ht : 0 ≤ rt)
    (hi : 0 < inside) (ho : 0 < outside) :
    0 ≤ cycles scale inside outside * affinity rt inside outside / 1000 := by
  rw [cycles, affinity, Real.log_div hi.ne' ho.ne']
  apply div_nonneg _ (by norm_num)
  rcases le_total outside inside with h | h
  · exact mul_nonneg (mul_nonneg hk (sub_nonneg.mpr h))
      (mul_nonneg ht (sub_nonneg.mpr (Real.log_le_log ho h)))
  · exact mul_nonneg_of_nonpos_of_nonpos (mul_nonpos_of_nonneg_of_nonpos hk (sub_nonpos.mpr h))
      (mul_nonpos_of_nonneg_of_nonpos ht (sub_nonpos.mpr (Real.log_le_log hi h)))

/-- Booking the same outward extent for K and A conserves each inventory
and preserves the local monovalent charge difference on both sides. -/
theorem pair_inventories (ki ai ko ao j : ℝ) :
    ((ki - j) + (ko + j) = ki + ko) ∧ ((ai - j) + (ao + j) = ai + ao) ∧
    ((ki - j) - (ai - j) = ki - ai) ∧ ((ko + j) - (ao + j) = ko - ao) := by
  refine ⟨?_, ?_, ?_, ?_⟩ <;> ring

/-- q is the transferred amount. The linear coefficient includes both finite
compartments. Unequal fixed volumes also contribute a quadratic term. -/
theorem finite_volume_drive (ki ai ko ao q vi vo : ℝ) :
    (ki - q / vi) * (ai - q / vi) - (ko + q / vo) * (ao + q / vo) =
      ki * ai - ko * ao - q * ((ki + ai) / vi + (ko + ao) / vo) +
        q ^ 2 * ((1 / vi) ^ 2 - (1 / vo) ^ 2) := by ring

/-- With equal fixed volumes, a transfer changing each concentration by x
changes the driving product difference by an exactly linear amount. -/
theorem equal_volume_drive (ki ai ko ao x : ℝ) :
    (ki - x) * (ai - x) - (ko + x) * (ao + x) =
      ki * ai - ko * ao - (ki + ai + ko + ao) * x := by ring

/-- Closed-pair concentration change in mM. Here r is the rate scale divided
by the common volume, s the sum of the four initial concentrations and d the
initial product difference. -/
def concentrationChange (r s d t : ℝ) : ℝ :=
  d / s * (1 - Real.exp (-(r * s) * t))

theorem change_initial (r s d : ℝ) : concentrationChange r s d 0 = 0 := by
  simp [concentrationChange]

theorem change_outward {r s d t : ℝ} (hr : 0 < r) (hs : 0 < s) (hd : 0 < d)
    (ht : 0 < t) : 0 < concentrationChange r s d t := by
  exact mul_pos (div_pos hd hs) (sub_pos.mpr (Real.exp_lt_one_iff.mpr
    (mul_neg_of_neg_of_pos (neg_lt_zero.mpr (mul_pos hr hs)) ht)))

theorem change_solves_rate (r d t : ℝ) {s : ℝ} (hs : 0 < s) :
    HasDerivAt (concentrationChange r s d)
      (r * (d - s * concentrationChange r s d t)) t := by
  have e := ((hasDerivAt_id t).const_mul (-(r * s))).exp
  convert (((hasDerivAt_const t (1 : ℝ)).sub e).const_mul (d / s)) using 1
  simp only [concentrationChange, id_eq, mul_one, zero_sub]
  field_simp [hs.ne']
  ring

/-- The explicit ARS(2,2,2) stages use a first slope j and a second slope
j − λ γ h j on the closed pair. Their weights satisfy (1−δ) γ = 1/2. -/
theorem explicit_step (h j rate γ δ : ℝ) (order : (1 - δ) * γ = 1 / 2) :
    h * (δ * j + (1 - δ) * (j - rate * (γ * h * j))) =
      h * j * (1 - h * rate / 2) := by
  calc
    _ = h * j * (1 - h * rate * ((1 - δ) * γ)) := by ring
    _ = _ := by rw [order]; ring

theorem step_points_inward {h j rate : ℝ} (ht : 0 < h) (hj : 0 < j) (hz : 2 < h * rate) :
    h * j * (1 - h * rate / 2) < 0 := by
  exact mul_neg_of_pos_of_neg (mul_pos ht hj) (by linarith)

end

end CellsProofs.Transport.PotassiumAnionSymport
