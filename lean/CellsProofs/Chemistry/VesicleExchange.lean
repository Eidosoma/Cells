import CellsProofs.Chemistry.AssemblyKinetics
import CellsProofs.Chemistry.SpeciesTurnover
import CellsProofs.Chemistry.Vesicle

/-! # Single-molecule exchange at a vesicle membrane -/

namespace CellsProofs.Chemistry.VesicleExchange

open AssemblyKinetics (common memCount idealEnergy logEncounter standard)
open Vesicle (footprint radius sphere)

noncomputable section

/-- Entry into the lumen, or insertion into the bilayer, in molecules per second.
The density counts molecules per unit volume. -/
def areaRate (velocity area density : ℝ) := velocity * area * density

/-- Diffusion-limited capture by the sphere of equivalent area. -/
def captureRate (diffusivity area density : ℝ) := diffusivity * (4 * Real.pi * radius area) * density

/-- At equal bath density the two encounter laws respond differently to a radius change.
Scaling a radius by s multiplies the corresponding area by s². -/
theorem size_scaling (v D density a : ℝ) {s : ℝ} (hs : 0 ≤ s) :
    areaRate v (s ^ 2 * a) density = s ^ 2 * areaRate v a density ∧
    captureRate D (s ^ 2 * a) density = s * captureRate D a density := by
  have hr : radius (s ^ 2 * a) = s * radius a := by
    unfold Vesicle.radius
    rw [mul_div_assoc, Real.sqrt_mul (sq_nonneg s), Real.sqrt_sq hs]
  constructor
  · unfold areaRate
    ring
  · simp only [captureRate, hr]
    ring

variable {S : Type*} [Fintype S]

/-- The shared membrane footprint is computed at the componentwise minimum of the endpoints. -/
def commonFootprint (w : S → ℕ) (n p : S → ℕ) := footprint (common n p) w

theorem common_footprint_swap (w : S → ℕ) (n p : S → ℕ) :
    commonFootprint w p n = commonFootprint w n p := by
  simp [commonFootprint, footprint, common, Nat.min_comm]

/-- Transferring one molecule between distinct places leaves the shared footprint at the
residual inventory. Pool and lumen weights are zero when only membrane area is counted. -/
theorem transfer_footprint [DecidableEq S] (w u : S → ℕ) {i j : S} (hij : i ≠ j) :
    commonFootprint w (ReservoirExchange.addOne u i) (ReservoirExchange.addOne u j) =
      footprint u w := by
  have h : common (ReservoirExchange.addOne u i) (ReservoirExchange.addOne u j) = u := by
    funext k
    by_cases hi : k = i
    · subst k
      simp [common, ReservoirExchange.addOne, hij]
    · simp [common, ReservoirExchange.addOne, hi]
  rw [commonFootprint, h]

/-- On an enabled two-way pair, the common positive encounter coefficient drops out.
The remaining ratio is exp(initial F - final F + held-reservoir work), with the exact
discrete ideal energy and any excess-energy difference assigned to the reverse. -/
theorem pair_balance (w : S → ℕ) (extent : ℕ → ℝ) (mem : Finset S) (c : ℕ)
    (μ logX : S → ℝ) (u a b : S → ℕ) (hc : c ≤ memCount mem u)
    (active : 0 < extent (commonFootprint w (u + a) (u + b)))
    (excess : (S → ℕ) → ℝ) (heldF heldR heldStd : ℝ) :
    let n := u + a
    let p := u + b
    (extent (commonFootprint w n p) * Real.exp (logEncounter mem c logX u a + heldF)) /
      (extent (commonFootprint w p n) * Real.exp (standard μ b - standard μ a + heldStd +
        logEncounter mem c logX u b + heldR + (excess p - excess n))) =
      Real.exp ((idealEnergy mem c μ logX n + excess n) - (idealEnergy mem c μ logX p + excess p) +
        (heldF - heldR - heldStd)) := by
  dsimp only
  rw [common_footprint_swap w (u + a) (u + b), mul_div_mul_left _ _ active.ne', ← Real.exp_sub,
    AssemblyKinetics.encounter_energy mem c μ logX u a hc,
    AssemblyKinetics.encounter_energy mem c μ logX u b hc]
  congr 1
  ring

/-- In a fixed ideal lumen the exit rate is first order in the count. With a held external
density, a molecule moves in or out at the two indicated one-way rates. -/
theorem fixed_volume_drift (P a outside count v : ℝ) :
    areaRate P a outside - areaRate P a (count / v) =
      P * a * outside - (P * a / v) * count := by
  unfold areaRate
  ring

/-- On an equal-radius spherical membrane and lumen the loss rate per molecule is 3P/r.
The experimental comparison uses the study's inner-radius convention for both. -/
theorem spherical_clearance (P : ℝ) {a : ℝ} (ha : 0 < a) :
    P * a / sphere a = 3 * P / radius a := by
  have hr : 0 < radius a := Real.sqrt_pos.2 (div_pos ha (by positivity))
  unfold Vesicle.sphere
  field_simp [ha.ne', hr.ne']
  ring

/-- A single calibration at one radius determines the loss rate at another positive area. -/
theorem transfer_clearance (P : ℝ) {a b : ℝ} (ha : 0 < a) (hb : 0 < b) :
    P * b / sphere b = (P * a / sphere a) * radius a / radius b := by
  have hr : 0 < radius a := Real.sqrt_pos.2 (div_pos ha (by positivity))
  rw [spherical_clearance P ha, spherical_clearance P hb, div_mul_cancel₀ _ hr.ne']

/-- The well-mixed washout equation at fixed volume has the exponential mean count used
to interpret the experimental concentration decay. -/
theorem washout_derivative (P a v count t : ℝ) :
    HasDerivAt (fun s => count * SpeciesTurnover.survival (P * a / v) s)
      (-areaRate P a ((count * SpeciesTurnover.survival (P * a / v) t) / v)) t := by
  have hd := SpeciesTurnover.amount_derivative count 0 (P * a / v) t
  have h : SpeciesTurnover.amount count 0 (P * a / v) =
      fun s => count * SpeciesTurnover.survival (P * a / v) s := by
    funext s
    simp [SpeciesTurnover.amount]
  rw [h, zero_sub] at hd
  convert hd using 1
  unfold areaRate
  ring

end

end CellsProofs.Chemistry.VesicleExchange
