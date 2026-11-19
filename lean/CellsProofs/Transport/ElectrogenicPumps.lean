import CellsProofs.Transport.ATPCycle
import Mathlib.Tactic.Ring

/-! # Sodium–potassium and calcium pump charge

The ratios are ln(inside activity / outside activity), fuel is the free-energy
change of ATP hydrolysis in units of RT, and ψ = F(V_inside − V_outside)/(RT).
Positive cycles hydrolyse ATP. The calcium law transports calcium alone.
-/

namespace CellsProofs.Transport.ElectrogenicPumps

open CellsProofs.Transport.ATPCycle

noncomputable section

def nakEnergy (fuel naRatio kRatio ψ : ℝ) : ℝ :=
  fuel - 3 * (naRatio + ψ) + 2 * (kRatio + ψ)

def calciumEnergy (fuel caRatio ψ : ℝ) : ℝ :=
  fuel - (caRatio + 2 * ψ)

theorem nak_stall_iff (logForward fuel naRatio kRatio ψ : ℝ) :
    flux true logForward (nakEnergy fuel naRatio kRatio ψ) = 0 ↔
      ψ = fuel - 3 * naRatio + 2 * kRatio := by
  rw [stall_iff, nakEnergy]
  constructor <;> intro h <;> linarith only [h]

theorem calcium_stall_iff (logForward fuel caRatio ψ : ℝ) :
    flux true logForward (calciumEnergy fuel caRatio ψ) = 0 ↔
      ψ = (fuel - caRatio) / 2 := by
  rw [stall_iff, calciumEnergy]
  constructor <;> intro h <;> linarith only [h]

theorem nak_forward_iff (logForward fuel naRatio kRatio ψ : ℝ) :
    0 < flux true logForward (nakEnergy fuel naRatio kRatio ψ) ↔
      fuel - 3 * naRatio + 2 * kRatio < ψ := by
  rw [forward_iff, nakEnergy]
  constructor <;> intro h <;> linarith only [h]

theorem calcium_forward_iff (logForward fuel caRatio ψ : ℝ) :
    0 < flux true logForward (calciumEnergy fuel caRatio ψ) ↔
      (fuel - caRatio) / 2 < ψ := by
  rw [forward_iff, calciumEnergy]
  constructor <;> intro h <;> linarith only [h]

/-- Valence-weighted outward ion flux: 3 Na out, 2 K in, 1 divalent Ca out. -/
def outwardCharge (jNaK jCa : ℝ) : ℝ :=
  3 * jNaK - 2 * jNaK + 2 * jCa

theorem charge_per_cycle (jNaK jCa : ℝ) :
    outwardCharge jNaK jCa = jNaK + 2 * jCa := by unfold outwardCharge; ring

theorem voltage_work (nakFuel caFuel naRatio kRatio caRatio ψ jNaK jCa : ℝ) :
    jNaK * (nakEnergy nakFuel naRatio kRatio ψ - nakEnergy nakFuel naRatio kRatio 0) +
      jCa * (calciumEnergy caFuel caRatio ψ - calciumEnergy caFuel caRatio 0) =
      -ψ * outwardCharge jNaK jCa := by
  unfold nakEnergy calciumEnergy outwardCharge
  ring

theorem zero_current_iff (jNaK jCa : ℝ) :
    outwardCharge jNaK jCa = 0 ↔ jNaK = -2 * jCa := by
  rw [charge_per_cycle]
  constructor <;> intro h <;> linarith only [h]

end

end CellsProofs.Transport.ElectrogenicPumps
