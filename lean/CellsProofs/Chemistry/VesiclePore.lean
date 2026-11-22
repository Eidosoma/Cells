import CellsProofs.Chemistry.VesicleArea
import Mathlib.Analysis.Calculus.Deriv.MeanValue
import Mathlib.Analysis.SpecialFunctions.Log.Deriv
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Positivity

/-! # Pore nucleation under one constant tension in assembly lineages

`activation` is E_A/R in kelvin. `scale` is π Γ²/k_B in kelvin times tension.
The barrier and the hold's work in units of k_BT are both (scale / σ) / T.
All logarithms use the numerical values in the engine's declared SI units. -/

namespace CellsProofs.Chemistry.VesiclePore

noncomputable section

def logPerArea (σ logNu activation scale T : ℝ) : ℝ :=
  logNu + (1/2) * Real.log σ - (3/2) * Real.log T - activation / T - (scale / σ) / T

def logRate (area σ logNu activation scale T : ℝ) : ℝ :=
  Real.log area + logPerArea σ logNu activation scale T

/-- The rate used by the clock supplies the common per-area hazard in the survival bound. -/
theorem rate_eq_area_mul {area : ℝ} (ha : 0 < area) (σ logNu activation scale T : ℝ) :
    Real.exp (logRate area σ logNu activation scale T) =
      area * Real.exp (logPerArea σ logNu activation scale T) := by
  rw [logRate, Real.exp_add, Real.exp_log ha]

theorem hold_survival {area : ℝ} (ha : 0 < area) (σ logNu activation scale T duration : ℝ) :
    Real.exp (-(Real.exp (logRate area σ logNu activation scale T) * duration)) =
      VesicleArea.survival (Real.exp (logPerArea σ logNu activation scale T) * duration) area := by
  rw [rate_eq_area_mul ha, VesicleArea.survival]
  congr 1
  ring

theorem logRate_hasDerivAt (area σ logNu activation scale : ℝ) {T : ℝ} (ht : 0 < T) :
    HasDerivAt (logRate area σ logNu activation scale)
      (activation / T^2 + (scale / σ) / T^2 - (3/2) / T) T := by
  have hT : HasDerivAt (fun t : ℝ => t) 1 T := hasDerivAt_id T
  have h1 := (hasDerivAt_const T (logNu + (1/2) * Real.log σ)).sub
    ((Real.hasDerivAt_log ht.ne').const_mul (3/2 : ℝ))
  have ha := (hasDerivAt_const T activation).div hT ht.ne'
  have hb := (hasDerivAt_const T (scale / σ)).div hT ht.ne'
  convert ((h1.sub ha).sub hb).const_add (Real.log area) using 1
  simp
  field_simp [ht.ne']
  ring

/-- The engine admits σ ≤ σβ/4, with σβ = scale/T. At fixed area and tension the
dimensionless temperature slope T · ∂log k/∂T is strictly greater than 5/2. -/
theorem temperature_slope_gt (area logNu : ℝ) {σ activation scale T : ℝ}
    (hs : 0 < σ) (ha : 0 < activation) (ht : 0 < T) (guard : σ ≤ (scale / T) / 4) :
    5/2 < T * deriv (logRate area σ logNu activation scale) T := by
  have hbar : 4 * T ≤ scale / σ := by
    apply (le_div_iff₀ hs).2
    have h := (le_div_iff₀ ht).1 ((le_div_iff₀ (by norm_num : (0 : ℝ) < 4)).1 guard)
    linarith
  rw [(logRate_hasDerivAt _ _ _ _ _ ht).deriv]
  have rearrange : T * (activation / T^2 + (scale / σ) / T^2 - (3/2) / T) =
      (activation + scale / σ) / T - 3/2 := by field_simp [ht.ne']; ring
  rw [rearrange]
  have h : (4 : ℝ) < (activation + scale / σ) / T :=
    (lt_div_iff₀ ht).2 (by linarith)
  linarith

/-- Admitting the hotter endpoint suffices for the whole positive temperature interval. -/
theorem warming_increases_rate (area logNu : ℝ) {σ activation scale cold hot : ℝ}
    (hs : 0 < σ) (ha : 0 < activation) (hb : 0 < scale)
    (hc : 0 < cold) (temps : cold < hot) (guard : σ ≤ (scale / hot) / 4) :
    Real.exp (logRate area σ logNu activation scale cold) <
      Real.exp (logRate area σ logNu activation scale hot) := by
  apply Real.exp_lt_exp.mpr
  apply strictMonoOn_of_deriv_pos (convex_Icc cold hot) _ _ (Set.left_mem_Icc.mpr temps.le)
    (Set.right_mem_Icc.mpr temps.le) temps
  · intro t ht
    exact (logRate_hasDerivAt _ _ _ _ _ (lt_of_lt_of_le hc ht.1)).continuousAt.continuousWithinAt
  · intro t ht
    have mem : t ∈ Set.Icc cold hot := interior_subset ht
    have pos := lt_of_lt_of_le hc mem.1
    have hguard : σ ≤ (scale / t) / 4 :=
      guard.trans (by gcongr; exact mem.2)
    have scaled := temperature_slope_gt area logNu hs ha pos hguard
    exact pos_of_mul_pos_right (lt_trans (by norm_num) scaled) pos.le

/-- A positive rate reaches E by an inclusive cut exactly when the integrated rate suffices.
The cut can be the earlier of the hold end and the observation horizon. -/
theorem clock_by_cut {rate : ℝ} (hk : 0 < rate) (start cut E : ℝ) :
    start + E / rate ≤ cut ↔ E ≤ rate * (cut - start) := by
  rw [add_comm, ← le_sub_iff_add_le, div_le_iff₀ hk, mul_comm]

/-- The founder's binary64 threshold exceeds the available exposure at the middle of the
three adjacent cuts in the recorded replay. Each fraction is an exact engine input. -/
theorem recorded_cut_precedes_rupture :
    let rate : ℚ := 4226696303541181 / 4503599627370496
    let threshold : ℚ := 6834050767042083 / 18014398509481984
    let cut : ℚ := 6324042017689367 / 4503599627370496
    rate * (cut - 1) < threshold := by norm_num

/-- The work σπr_c²/(k_BT) at r_c = Γ/σ is the same dimensionless barrier the clock uses. -/
theorem hold_work (lineTension : ℝ) {σ kB T : ℝ} (hs : 0 < σ) (hk : 0 < kB) (ht : 0 < T) :
    σ * Real.pi * (lineTension / σ)^2 / (kB * T) =
      ((Real.pi * lineTension^2 / kB) / σ) / T := by
  field_simp [hs.ne', hk.ne', ht.ne']
  ring

def viscosity (etaRef ref activation T : ℝ) : ℝ :=
  etaRef * (T / ref) * Real.exp (activation * (1/T - 1/ref))

def collapseRate (etaRef ref activation scale σ T : ℝ) : ℝ :=
  Real.sqrt ((scale / T) * σ) / (4 * Real.pi * viscosity etaRef ref activation T)

def logSiteDensity (logNu etaRef ref activation scale : ℝ) : ℝ :=
  Real.log (4 * Real.pi) + Real.log etaRef + logNu - activation / ref -
    (1/2) * Real.log scale - Real.log ref

/-- The free energy of the critical pore above the closed vesicle, in k_BT. -/
def openingCost (logSites work : ℝ) : ℝ := 2 * work - logSites

/-- The forward and reverse rates give the same opening heat as the paid hold work
less the pore's free energy. The reverse rate is evaluated even in a rupture-only world. -/
theorem opening_heat_eq_log_ratio (area logNu activation : ℝ) {etaRef ref scale σ T : ℝ}
    (he : 0 < etaRef) (hr : 0 < ref) (hb : 0 < scale) (hs : 0 < σ) (ht : 0 < T) :
    let work := (scale / σ) / T
    let sites := Real.log area + logSiteDensity logNu etaRef ref activation scale
    (-openingCost sites work + work) =
      logRate area σ logNu activation scale T - Real.log (collapseRate etaRef ref activation scale σ T) := by
  dsimp only
  have hvis : 0 < viscosity etaRef ref activation T := by unfold viscosity; positivity
  have hfour : 0 < 4 * Real.pi := by positivity
  rw [collapseRate, Real.log_div (Real.sqrt_pos.2 (mul_pos (div_pos hb ht) hs)).ne'
      (mul_pos hfour hvis).ne', Real.log_sqrt (mul_pos (div_pos hb ht) hs).le,
    Real.log_mul (div_pos hb ht).ne' hs.ne', Real.log_div hb.ne' ht.ne',
    Real.log_mul hfour.ne' hvis.ne', viscosity,
    Real.log_mul (mul_pos he (div_pos ht hr)).ne' (Real.exp_pos _).ne',
    Real.log_mul he.ne' (div_pos ht hr).ne', Real.log_div ht.ne' hr.ne', Real.log_exp]
  unfold openingCost logSiteDensity logRate logPerArea
  ring

/-- The open state cancels when opening and release are booked together, including signed
work from any held reservoir. -/
theorem event_heat (closed after cost work reservoir : ℝ) :
    (-cost + work) + ((closed + cost) - after + reservoir) =
      closed - after + work + reservoir := by ring

/-- Scaling the declared surface viscosity changes the two heat entries by opposite log factors. -/
theorem viscosity_heat_split {factor etaRef : ℝ} (hf : 0 < factor) (he : 0 < etaRef)
    (area logNu ref activation scale closed after work reservoir : ℝ) :
    let cost := fun eta => openingCost
      (Real.log area + logSiteDensity logNu eta ref activation scale) work
    (-cost (factor * etaRef) + work) - (-cost etaRef + work) = Real.log factor ∧
      ((closed + cost (factor * etaRef) - after + reservoir) -
        (closed + cost etaRef - after + reservoir)) = -Real.log factor := by
  dsimp [openingCost, logSiteDensity]
  rw [Real.log_mul hf.ne' he.ne']
  constructor <;> ring

end

end CellsProofs.Chemistry.VesiclePore
