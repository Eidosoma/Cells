import Mathlib.Analysis.SpecialFunctions.Log.Deriv
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Ring

/-! # Water exchange between compliant compartments

Volumes are pL. The pressure slope is K/Vref, the intercept is P₀ − K and the
osmotic coefficient is RT times the trapped amount in fmol. Flow is positive
outward. One Pa pL is 1/1000 pJ.
-/

namespace CellsProofs.Transport.OsmoticWater

noncomputable section

structure Node where
  slope : ℝ
  intercept : ℝ
  osmotic : ℝ

def potential (p : Node) (v : ℝ) : ℝ := p.slope * v + p.intercept - p.osmotic / v

theorem declared_potential (k offset osm v : ℝ) {ref : ℝ} (hr : 0 < ref) :
    potential ⟨k / ref, offset - k, osm⟩ v =
      k * (v - ref) / ref + offset - osm / v := by
  unfold potential
  congr 1
  field_simp
  ring

/-- A primitive at fixed osmole count, up to an additive constant. -/
def energy (p : Node) (v : ℝ) : ℝ :=
  (p.slope / 2 * v ^ 2 + p.intercept * v - p.osmotic * Real.log v) / 1000

theorem energy_has_deriv (p : Node) {v : ℝ} (hv : 0 < v) :
    HasDerivAt (energy p) (potential p v / 1000) v := by
  have e := (((((hasDerivAt_id v).pow 2).const_mul (p.slope / 2)).add
    ((hasDerivAt_id v).const_mul p.intercept)).sub
    ((Real.hasDerivAt_log hv.ne').const_mul p.osmotic)).div_const 1000
  convert e using 1
  simp only [potential, id_eq, div_eq_mul_inv]
  ring

/-- The endpoint ledger uses the change in mixing energy and the exact
quadratic change of elastic energy. -/
theorem endpoint_ledger (p : Node) {v v₀ : ℝ} (hv : 0 < v) (h₀ : 0 < v₀) :
    energy p v - energy p v₀ =
      (-p.osmotic * Real.log (v / v₀) + (p.slope * v₀ + p.intercept) * (v - v₀) +
        p.slope / 2 * (v - v₀) ^ 2) / 1000 := by
  rw [Real.log_div hv.ne' h₀.ne']
  unfold energy
  ring

def secant (p : Node) (v w : ℝ) : ℝ := p.slope + p.osmotic / (v * w)

theorem potential_has_deriv (p : Node) {v : ℝ} (hv : 0 < v) :
    HasDerivAt (potential p) (p.slope + p.osmotic / v ^ 2) v := by
  have d := ((((hasDerivAt_id v).const_mul p.slope).add_const p.intercept).sub
    ((hasDerivAt_const v p.osmotic).div (hasDerivAt_id v) hv.ne'))
  convert d using 1
  simp only [id_eq, mul_one, zero_mul, zero_sub, neg_div, sub_neg_eq_add]

theorem potential_change (p : Node) {v w : ℝ} (hv : 0 < v) (hw : 0 < w) :
    potential p w - potential p v = (w - v) * secant p v w := by
  unfold potential secant
  field_simp [hv.ne', hw.ne']
  ring

def flow (g inside outside : ℝ) : ℝ := g * (inside - outside)

/-- A rapid hydrostatic step at fixed initial osmolarities changes flow in
proportion to the imposed pressure step, even with a nonzero baseline. -/
theorem pressure_step_flow (g inside outside step : ℝ) :
    flow g (inside + step) outside - flow g inside outside = g * step := by
  unfold flow
  ring

/-- Both finite compartments' free-energy rates plus irreversible heat sum to zero.
With a held bath, the outside term is the negative of the booked supply work. -/
theorem edge_power (g inside outside : ℝ) :
    let q := flow g inside outside
    inside * (-q) / 1000 + q * (inside - outside) / 1000 =
      outside * (-q) / 1000 := by
  dsimp [flow]
  ring

theorem heat_nonneg {g : ℝ} (hg : 0 ≤ g) (inside outside : ℝ) :
    0 ≤ flow g inside outside * (inside - outside) / 1000 := by
  rw [flow, mul_assoc, ← sq]
  exact div_nonneg (mul_nonneg hg (sq_nonneg _)) (by norm_num)

/-- One finite edge at frozen amounts. The Heun corrector multiplies the
first Euler transfer by a factor depending on the secants to the predictor. -/
theorem heun_transfer (i o : Node) (h g : ℝ) {vi vo : ℝ} (hi : 0 < vi) (ho : 0 < vo)
    (x : ℝ) (hx : x = h * flow g (potential i vi) (potential o vo))
    (hi' : 0 < vi - x) (ho' : 0 < vo + x) :
    h * (flow g (potential i vi) (potential o vo) +
      flow g (potential i (vi - x)) (potential o (vo + x))) / 2 =
        x * (1 - h * g * (secant i vi (vi - x) + secant o vo (vo + x)) / 2) := by
  have di := potential_change i hi hi'
  have do' := potential_change o ho ho'
  rw [show vi - x - vi = -x by ring] at di
  rw [show vo + x - vo = x by ring] at do'
  rw [sub_eq_iff_eq_add.mp di, sub_eq_iff_eq_add.mp do']
  unfold flow at *
  linear_combination hx * (-1)

/-- If the product of half-step, mobility and the two secants is below two,
the Heun transfer follows the sign of the Euler transfer in either direction. -/
theorem heun_direction (x : ℝ) {z : ℝ} (hz : z < 2) :
    (0 < x * (1 - z / 2) ↔ 0 < x) ∧ (x * (1 - z / 2) < 0 ↔ x < 0) := by
  have hf : 0 < 1 - z / 2 := by linarith
  refine ⟨mul_pos_iff_of_pos_right hf, ?_⟩
  constructor
  · intro neg
    by_contra! nonneg
    exact (not_lt_of_ge (mul_nonneg nonneg hf.le)) neg
  · exact fun neg => mul_neg_of_neg_of_pos neg hf

/-- For the fixture's declared volume window [0.5 V₀, 2 V₀], any start
volume is at most four times an admissible predictor volume. -/
theorem secant_bound (p : Node) {v w : ℝ} (hv : 0 < v) (hw : 0 < w)
    (hk : 0 ≤ p.slope) (ha : 0 ≤ p.osmotic) (window : v ≤ 4 * w) :
    secant p v w ≤ 4 * (p.slope + p.osmotic / v ^ 2) := by
  have aux : p.osmotic / (v * w) ≤ 4 * p.osmotic / v ^ 2 := by
    rw [div_le_div_iff₀ (mul_pos hv hw) (sq_pos_of_pos hv)]
    nlinarith [mul_nonneg (mul_nonneg ha hv.le) (sub_nonneg.mpr window)]
  rw [mul_div_assoc] at aux
  unfold secant
  linarith

/-- For a single finite edge in the fourfold volume window, the engine's
full-step rate test guarantees the Heun direction during its half-step. -/
theorem guarded_heun_direction (i o : Node) {vi vo wi wo h g : ℝ}
    (hi : 0 < vi) (ho : 0 < vo) (hi' : 0 < wi) (ho' : 0 < wo)
    (ki : 0 ≤ i.slope) (ko : 0 ≤ o.slope) (ai : 0 ≤ i.osmotic) (ao : 0 ≤ o.osmotic)
    (winI : vi ≤ 4 * wi) (winO : vo ≤ 4 * wo) (step : 0 ≤ h * g)
    (guard : 2 * h * g * ((i.slope + i.osmotic / vi ^ 2) + (o.slope + o.osmotic / vo ^ 2))
      ≤ 1 / 20) (x : ℝ) :
    let factor := 1 - h * g * (secant i vi wi + secant o vo wo) / 2
    (0 < x * factor ↔ 0 < x) ∧ (x * factor < 0 ↔ x < 0) := by
  apply heun_direction
  have bound := mul_le_mul_of_nonneg_left
    (add_le_add (secant_bound i hi hi' ki ai winI) (secant_bound o ho ho' ko ao winO)) step
  linarith only [bound, guard]

/-- At equilibrium, linear compliance with zero initial pressure offset
gives a quadratic for volume relative to V₀. c₀ and c are initial internal
and final external osmolarities. -/
theorem compliant_bath_stall {g y : ℝ} (hg : 0 < g) (hy : 0 < y) (k rt c₀ c : ℝ) :
    flow g (potential ⟨k, -k, rt * c₀⟩ y) (-rt * c) = 0 ↔
      k * y * (y - 1) + rt * c * y = rt * c₀ := by
  simp only [flow, potential, mul_eq_zero, hg.ne', false_or]
  constructor <;> intro h
  · field_simp [hy.ne'] at h
    linear_combination h
  · field_simp [hy.ne']
    linear_combination h

/-- With equal hydrostatic pressures, an active membrane stalls at trapped
osmoles divided by bath osmolarity. v denotes the aqueous volume. -/
theorem ideal_bath_stall {g rt c v : ℝ} (hg : 0 < g) (ht : 0 < rt)
    (hc : 0 < c) (hv : 0 < v) (n pressure : ℝ) :
    flow g (potential ⟨0, pressure, rt * n⟩ v) (pressure - rt * c) = 0 ↔ v = n / c := by
  simp only [flow, potential, zero_mul, zero_add, mul_eq_zero, hg.ne', false_or]
  rw [eq_div_iff hc.ne']
  constructor <;> intro h
  · field_simp [hv.ne'] at h
    apply mul_left_cancel₀ ht.ne'
    linear_combination h
  · field_simp [hv.ne']
    linear_combination rt * h

/-- At given volumes, one outward 1:1 K–anion extent removes two cell osmoles
and adds two outside. The resulting pressure difference includes both volumes. -/
theorem symport_drive_change (i o : Node) (rt x vi vo : ℝ) :
    potential {i with osmotic := i.osmotic - 2 * rt * x} vi -
      potential {o with osmotic := o.osmotic + 2 * rt * x} vo -
      (potential i vi - potential o vo) = 2 * rt * x * (1 / vi + 1 / vo) := by
  unfold potential
  ring

end

end CellsProofs.Transport.OsmoticWater
