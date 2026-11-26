import CellsProofs.Transport.OpenChannelBlock
import CellsProofs.Transport.ProtonLeak
import Mathlib.Analysis.SpecialFunctions.Log.Deriv

/-! FR-51's material bound at fixed membrane voltage and gate state. The signed thermal
voltage is RT/(zF), the two concentrations are in mM, and positive flux is outwards. -/

namespace CellsProofs.Transport.BlockMaterialSlope

open OpenChannelBlock
noncomputable section

variable {ι : Type*} [Fintype ι]

def drive (thermal voltage ci co : ℝ) : ℝ :=
  voltage - thermal * (Real.log co - Real.log ci)

theorem drive_outside {co : ℝ} (ho : 0 < co) (thermal voltage ci : ℝ) :
    HasDerivAt (drive thermal voltage ci) (-thermal / co) co := by
  convert ((((Real.hasDerivAt_log ho.ne').sub_const (Real.log ci)).const_mul thermal).const_sub
    voltage) using 1
  simp [drive, div_eq_mul_inv]

theorem drive_inside {ci : ℝ} (hi : 0 < ci) (thermal voltage co : ℝ) :
    HasDerivAt (fun s => drive thermal voltage s co) (thermal / ci) ci := by
  convert ((((Real.hasDerivAt_log hi.ne').const_sub (Real.log co)).const_mul thermal).const_sub
    voltage) using 1
  simp [drive, div_eq_mul_inv]

def blockedFlux (m : ι → Mode) (blocker scale thermal voltage ci co : ℝ) : ℝ :=
  unblocked m blocker (drive thermal voltage ci co) *
    constantFieldFlux seriesFactor scale thermal⁻¹ ci co voltage

private theorem product_bound (m : ι → Mode) {c : ℝ} (hc : 0 ≤ c)
    (hk : ∀ i, 0 < (m i).k0) (hw : ∀ i, 0 ≤ (m i).weight)
    (hs : 0 < ∑ i, (m i).weight) {ref flux : ℝ → ℝ} {s r d : ℝ}
    (hr : HasDerivAt ref r s) (hf : HasDerivAt flux d s) :
    |deriv (fun y => unblocked m c (ref y) * flux y) s| ≤
      unblocked m c (ref s) * |d| + |flux s| * slopeBound m c (ref s) * |r| := by
  have hu := (unblocked_hasDerivAt m hc hk (ref s)).differentiableAt.hasDerivAt
  have h : HasDerivAt (fun y => unblocked m c (ref y))
      (deriv (unblocked m c) (ref s) * r) s := hu.comp s hr
  rw [(h.mul hf).deriv]
  have nonneg := (unblocked_mem_unit m hc hk hw hs (ref s)).1
  refine (abs_add_le _ _).trans ?_
  rw [abs_mul, abs_mul, abs_mul, abs_of_nonneg nonneg]
  have bound := mul_le_mul_of_nonneg_right
    (mul_le_mul_of_nonneg_right (abs_deriv_le_slopeBound m hc hk hw hs (ref s)) (abs_nonneg r))
    (abs_nonneg (flux s))
  exact (add_le_add_right bound _).trans_eq (by ring)

variable (m : ι → Mode) {c scale thermal voltage ci co : ℝ}
    (hc : 0 ≤ c) (hk : ∀ i, 0 < (m i).k0) (hw : ∀ i, 0 ≤ (m i).weight)
    (hs : 0 < ∑ i, (m i).weight) (hscale : 0 ≤ scale)

include hc hk hw hs hscale

/-- Outside concentration enters both outward free flux and the voltage reference. -/
theorem outside_concentration_bound (ho : 0 < co) :
    |deriv (blockedFlux m c scale thermal voltage ci) co| ≤
      unblocked m c (drive thermal voltage ci co) * (scale * seriesFactor.eval (thermal⁻¹ * voltage)) +
      |constantFieldFlux seriesFactor scale thermal⁻¹ ci co voltage| *
        slopeBound m c (drive thermal voltage ci co) * (|thermal| / co) := by
  let b := seriesFactor.eval (thermal⁻¹ * voltage)
  have hf : HasDerivAt (fun s => constantFieldFlux seriesFactor scale thermal⁻¹ ci s voltage)
      (-(scale * b)) co := by
    simpa [constantFieldFlux, b] using
      ((((hasDerivAt_id co).mul_const b).const_sub
        (ci * seriesFactor.eval (-(thermal⁻¹ * voltage)))).const_mul scale)
  simpa [blockedFlux, b, abs_div, abs_of_pos ho, abs_of_nonneg hscale,
    abs_of_pos (ProtonLeak.series_pos _), abs_mul] using
    product_bound m hc hk hw hs (drive_outside ho thermal voltage ci) hf

/-- The inside derivative has the opposite drive sign and uses B(-zFV/RT) for free flux. -/
theorem inside_concentration_bound (hi : 0 < ci) :
    |deriv (fun s => blockedFlux m c scale thermal voltage s co) ci| ≤
      unblocked m c (drive thermal voltage ci co) * (scale * seriesFactor.eval (-(thermal⁻¹ * voltage))) +
      |constantFieldFlux seriesFactor scale thermal⁻¹ ci co voltage| *
        slopeBound m c (drive thermal voltage ci co) * (|thermal| / ci) := by
  let b := seriesFactor.eval (-(thermal⁻¹ * voltage))
  have hf : HasDerivAt (fun s => constantFieldFlux seriesFactor scale thermal⁻¹ s co voltage)
      (scale * b) ci := by
    simpa [constantFieldFlux, b] using
      ((((hasDerivAt_id ci).mul_const b).sub_const
        (co * seriesFactor.eval (thermal⁻¹ * voltage))).const_mul scale)
  simpa [blockedFlux, b, abs_div, abs_of_pos hi, abs_of_nonneg hscale,
    abs_of_pos (ProtonLeak.series_pos _), abs_mul] using
    product_bound m hc hk hw hs (drive_inside hi thermal voltage co) hf

end

end CellsProofs.Transport.BlockMaterialSlope
