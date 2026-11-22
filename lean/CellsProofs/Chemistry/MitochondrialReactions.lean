import CellsProofs.Transport.ATPCycle
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Ring

/-! Two reactions confined to one side of the mitochondrial inner membrane.
Concentrations in binding ratios use a common unit. Chemical potentials in the
supply bookkeeping use energy per unit amount. -/

namespace CellsProofs.Chemistry.MitochondrialReactions

open CellsProofs.Transport

noncomputable section

/-- A signed extent of 2 ADP ⇌ ATP + AMP preserves adenylates, phosphate groups
and the charge of the Mg-free base forms on the P side. -/
theorem kinase_inventories (adp atp amp extent : ℝ) :
    (adp - 2 * extent) + (atp + extent) + (amp + extent) = adp + atp + amp ∧
    2 * (adp - 2 * extent) + 3 * (atp + extent) + (amp + extent) = 2 * adp + 3 * atp + amp ∧
    -3 * (adp - 2 * extent) - 4 * (atp + extent) - 2 * (amp + extent) =
      -3 * adp - 4 * atp - 2 * amp := by
  refine ⟨by ring, by ring, by ring⟩

/-- The enabled one-mode kernel reduces to the reversible mass-action rate on
free nucleotides. Scale includes the population capacity and the Mg factor. -/
theorem kinase_free_flux {scale base adp atp amp : ℝ}
    (hs : 0 < scale) (hb : 0 < base) (hd : 0 < adp) (ht : 0 < atp) (hm : 0 < amp) :
    ATPCycle.flux true (Real.log (scale * base * adp ^ 2))
        (Real.log (atp * amp / (base * adp ^ 2))) =
      scale * (base * adp ^ 2 - amp * atp) := by
  rw [ATPCycle.flux_eq_mass_action, Real.exp_log (by positivity), Real.exp_log (by positivity)]
  field_simp
  ring

/-- Apparent equilibrium constant on total ATP and ADP. AMP has one form.
Here a and d are the Mg dissociation constants of ATP and ADP respectively. -/
def apparentK (base m a d : ℝ) : ℝ := base * (1 + m / a) / (1 + m / d) ^ 2

theorem kinase_rate_on_totals (capacity base adp atp amp : ℝ) {m a d : ℝ}
    (hm : 0 ≤ m) (hd : 0 < d) :
    capacity * (1 + m / a) * (base * adp ^ 2 - amp * atp) =
      capacity * (apparentK base m a d * (adp * (1 + m / d)) ^ 2 -
        amp * (atp * (1 + m / a))) := by
  have h : 0 < 1 + m / d := by positivity
  unfold apparentK
  field_simp [h.ne']
  ring

/-- At m = d − 2a the apparent constant reaches its maximum. The exact gap
contains the square of the distance in free Mg from that peak. -/
theorem kinase_peak_gap (base : ℝ) {m a d : ℝ} (hm : 0 ≤ m) (ha : 0 < a) (had : 2 * a ≤ d) :
    apparentK base (d - 2 * a) a d - apparentK base m a d =
      base * d ^ 2 * (m - (d - 2 * a)) ^ 2 / (4 * a * (d - a) * (d + m) ^ 2) := by
  have hd : 0 < d := by linarith
  have hpeak : 0 ≤ d - 2 * a := by linarith
  have hp : 0 < d - a := by linarith
  have hsum : 0 < d + m := by linarith
  have h₁ : 0 < 1 + (d - 2 * a) / d := by positivity
  have h₂ : 0 < 1 + m / d := by positivity
  unfold apparentK
  field_simp [ha.ne', hd.ne', hp.ne', hsum.ne', h₁.ne', h₂.ne']
  ring

theorem kinase_peak_bound {base m a d : ℝ} (hb : 0 ≤ base) (hm : 0 ≤ m)
    (ha : 0 < a) (had : 2 * a ≤ d) :
    apparentK base m a d ≤ apparentK base (d - 2 * a) a d := by
  rw [← sub_nonneg, kinase_peak_gap base hm ha had]
  have hp : 0 < d - a := by linarith
  positivity

/-- At the declared zero standard drive at proton concentration href, the
matrix NADH/NAD stall ratio depends on free H and the held S_red/S_ox ratio. -/
theorem supply_stall (logForward : ℝ) {ratio h held href : ℝ}
    (hr : 0 < ratio) (hh : 0 < h) (hs : 0 < held) (h₀ : 0 < href) :
    ATPCycle.flux true logForward (Real.log (ratio * h / (held * href))) = 0 ↔
      ratio = held * href / h := by
  rw [ATPCycle.stall_iff, eq_div_iff hh.ne']
  have hp := mul_pos hs h₀
  constructor
  · intro he
    have hx := congrArg Real.exp he
    rw [Real.exp_log (by positivity), Real.exp_zero, div_eq_iff hp.ne', one_mul] at hx
    exact hx
  · intro hx
    rw [hx, div_self hp.ne', Real.log_one]

/-- The externally held pair supplies heat plus the chemical work delivered
to the three material rows NAD, NADH and H. The identity also holds in reverse. -/
theorem supply_work (rate reduced oxidized nad nadh proton : ℝ) :
    -rate * (oxidized - reduced) =
      -rate * (oxidized - reduced + nadh + proton - nad) + rate * (nadh + proton - nad) := by
  ring

end
end CellsProofs.Chemistry.MitochondrialReactions
