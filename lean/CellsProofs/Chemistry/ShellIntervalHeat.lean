import CellsProofs.Chemistry.ReleaseEnergy
import CellsProofs.Chemistry.ShellWashRecovery

/-! # Dissipated free energy between washes of a prescribed shell

The two well-mixed places share one conserved tracer. Each coefficient is the
standard potential in units of RT minus the log of the reference molecule count.
The deterministic ledger books a drop in free energy of the mean counts in k_BT. -/

namespace CellsProofs.Chemistry.ShellIntervalHeat

open ShellWashRecovery (exterior flux exterior_derivative)

noncomputable section

def site (coeff n : ℝ) : ℝ := n * coeff + ReleaseEnergy.ideal n

def energy (outside inside total pool : ℝ) : ℝ :=
  site outside pool + site inside (total - pool)

theorem site_continuous (coeff : ℝ) : Continuous (site coeff) :=
  (continuous_id.mul continuous_const).add (Real.continuous_mul_log.sub continuous_id)

@[simp] theorem site_zero (coeff : ℝ) : site coeff 0 = 0 := by
  simp [site, ReleaseEnergy.ideal]

/-- X = N_A V c₀ at each place. A positive common permeability-area factor supplies the
same rate scale when both volumes are expressed as reference molecule counts. -/
theorem shell_rate_balance {scale poolX lumenX : ℝ} (hs : 0 < scale)
    (hp : 0 < poolX) (hl : 0 < lumenX) (μp μl : ℝ) :
    Real.log (scale / poolX) - Real.log (scale * Real.exp (μl - μp) / lumenX) =
      (μp - Real.log poolX) - (μl - Real.log lumenX) := by
  rw [Real.log_div hs.ne' hp.ne',
    Real.log_div (mul_pos hs (Real.exp_pos _)).ne' hl.ne',
    Real.log_mul hs.ne' (Real.exp_pos _).ne', Real.log_exp]
  ring

private theorem site_derivative (a : ℝ) {n : ℝ} (hn : 0 < n) :
    HasDerivAt (site a) (a + Real.log n) n := by
  convert ((hasDerivAt_id n).mul_const a).add
    ((Real.hasDerivAt_mul_log hn.ne').sub (hasDerivAt_id n)) using 1
  ring

/-- Interior derivative as a flux times the log ratio of one-way fluxes.
At an empty endpoint only continuity is needed. -/
theorem energy_derivative {entry leave a b total t : ℝ} {p : ℝ → ℝ}
    (hin : 0 < entry) (hout : 0 < leave) (balance : Real.log entry - Real.log leave = a - b)
    (hp : 0 < p t) (hl : 0 < total - p t)
    (moves : HasDerivAt p (flux entry leave (p t) (total - p t)) t) :
    HasDerivAt (fun u => energy a b total (p u))
      ((leave * (total - p t) - entry * p t) *
        (Real.log (entry * p t) - Real.log (leave * (total - p t)))) t := by
  have logs : Real.log (entry * p t) - Real.log (leave * (total - p t)) =
      (a + Real.log (p t)) - (b + Real.log (total - p t)) := by
    rw [Real.log_mul hin.ne' hp.ne', Real.log_mul hout.ne' hl.ne']
    linarith
  rw [logs]
  convert ((site_derivative a hp).comp t moves).add
    ((site_derivative b hl).comp t (moves.const_sub total)) using 1
  unfold flux
  ring

private theorem interior_counts {entry leave pool lumen t : ℝ}
    (hin : 0 < entry) (hout : 0 < leave) (hp : 0 ≤ pool) (hl : 0 ≤ lumen)
    (stock : 0 < pool + lumen) (ht : 0 < t) :
    0 < exterior entry leave pool lumen t ∧
    0 < pool + lumen - exterior entry leave pool lumen t := by
  have hs := add_pos hin hout
  let d := SpeciesTurnover.survival (entry + leave) t
  have hd : 0 < d := Real.exp_pos _
  have htime : 0 < (1 - d) / (entry + leave) :=
    div_pos (sub_pos.mpr (Real.exp_lt_one_iff.mpr (neg_neg_of_pos (mul_pos hs ht)))) hs
  change 0 < pool * d + _ ∧ 0 < pool + lumen - (pool * d + _)
  simp only [SpeciesTurnover.exposure, if_neg hs.ne']
  change 0 < pool * d + leave * (pool + lumen) * ((1 - d) / (entry + leave)) ∧ _
  constructor
  · exact add_pos_of_nonneg_of_pos (mul_nonneg hp hd.le) (mul_pos (mul_pos hout stock) htime)
  · have complement : pool + lumen - (pool * d + leave * (pool + lumen) *
          ((1 - d) / (entry + leave))) =
          lumen * d + entry * (pool + lumen) * ((1 - d) / (entry + leave)) := by
      field_simp [hs.ne']
      ring
    exact complement.symm ▸ add_pos_of_nonneg_of_pos (mul_nonneg hl hd.le)
      (mul_pos (mul_pos hin stock) htime)

/-- Free energy is nonincreasing on the closed physical time domain, including
an initially empty exterior, an initially empty lumen, and no surviving tracer. -/
theorem energy_antitone {entry leave a b pool lumen : ℝ}
    (hin : 0 < entry) (hout : 0 < leave) (balance : Real.log entry - Real.log leave = a - b)
    (hp : 0 ≤ pool) (hl : 0 ≤ lumen) :
    AntitoneOn (fun t => energy a b (pool + lumen) (exterior entry leave pool lumen t))
      (Set.Ici 0) := by
  by_cases stock : pool + lumen = 0
  · have zp : pool = 0 := by linarith
    have zl : lumen = 0 := by linarith
    simp [zp, zl, ShellWashRecovery.exterior, SpeciesTurnover.amount, energy, AntitoneOn]
  have total := lt_of_le_of_ne (add_nonneg hp hl) (Ne.symm stock)
  let p := exterior entry leave pool lumen
  let l := fun t => pool + lumen - p t
  have cont : Continuous p := continuous_iff_continuousAt.mpr fun t =>
    (exterior_derivative entry leave pool lumen t).continuousAt
  apply antitoneOn_of_hasDerivWithinAt_nonpos (convex_Ici (0 : ℝ))
    (f' := fun t => (leave * l t - entry * p t) * (Real.log (entry * p t) - Real.log (leave * l t)))
  · exact (((site_continuous a).comp cont).add
      ((site_continuous b).comp (continuous_const.sub cont))).continuousOn
  · intro t ht
    rw [interior_Ici] at ht
    obtain ⟨hpt, hlt⟩ := interior_counts hin hout hp hl total ht
    exact (energy_derivative hin hout balance hpt hlt
      (exterior_derivative entry leave pool lumen t)).hasDerivWithinAt
  · intro t ht
    rw [interior_Ici] at ht
    obtain ⟨hpt, hlt⟩ := interior_counts hin hout hp hl total ht
    have x : 0 < entry * p t := mul_pos hin hpt
    have y : 0 < leave * l t := mul_pos hout hlt
    rcases le_total (entry * p t) (leave * l t) with h | h
    · exact mul_nonpos_of_nonneg_of_nonpos (sub_nonneg.mpr h) (sub_nonpos.mpr (Real.log_le_log x h))
    · exact mul_nonpos_of_nonpos_of_nonneg (sub_nonpos.mpr h) (sub_nonneg.mpr (Real.log_le_log y h))

/-- A full replacement leaves only the lumen's energy. The heat booked through a
later time on this wash-free interval is nonnegative, including at time zero. -/
theorem postwash_heat_nonneg {entry leave a b lumen t : ℝ} (hin : 0 < entry) (hout : 0 < leave)
    (balance : Real.log entry - Real.log leave = a - b) (retained : 0 ≤ lumen) (ht : 0 ≤ t) :
    0 ≤ site b lumen - energy a b lumen (exterior entry leave 0 lumen t) := by
  have h := energy_antitone hin hout balance (le_refl 0) retained
    (by simp : (0 : ℝ) ∈ Set.Ici 0) ht ht
  have start := (ShellWashRecovery.initial_recovery entry leave lumen).1
  simpa [start, energy] using sub_nonneg.mpr h

/-- A completely impermeable shell has constant counts and releases zero interval heat. -/
theorem impermeable_heat (a b pool lumen t : ℝ) :
    energy a b (pool + lumen) pool -
      energy a b (pool + lumen) (exterior 0 0 pool lumen t) = 0 := by
  simp [ShellWashRecovery.exterior, SpeciesTurnover.amount, SpeciesTurnover.survival]

/-- P9 substitutes the whole one-molecule term for the empty starting place.
When the ending counts are positive, this is the entire bias in interval heat. -/
theorem one_molecule_bias (a b total finish : ℝ) :
    (site a 1 + site b total - energy a b total finish) -
      (energy a b total 0 - energy a b total finish) = a - 1 := by
  simp [energy, site, ReleaseEnergy.ideal]
  ring

end

end CellsProofs.Chemistry.ShellIntervalHeat
