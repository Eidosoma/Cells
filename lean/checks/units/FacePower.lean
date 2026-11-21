import DimensionalAnalysis.Dimensions
import CellsProofs.Transport.LogMeanFace
import CellsProofs.Tissue.CurrentInjection

namespace CellsProofs.Checks

/-- Flux times molar potential has the dimension of power for any base system
with amount, time, mass and length, using the upstream dimensional algebra. -/
theorem face_power_dimension (B : Type) [HasBaseAmount B] [HasBaseTime B]
    [HasBaseMass B] [HasBaseLength B] :
    (dimension.amount B ℤ / dimension.time B ℤ) *
      (dimension.energy B ℤ / dimension.amount B ℤ) =
      dimension.energy B ℤ / dimension.time B ℤ := by
  simp only [dimension.mul_def', dimension.div_def']
  funext i
  abel

/-- Electrode charge is current times time. Voltage is power per current.
Their product has the dimension of energy in the single-patch work balance. -/
theorem charge_voltage_energy (B : Type) [HasBaseCurrent B] [HasBaseTime B]
    [HasBaseMass B] [HasBaseLength B] :
    (dimension.current B ℤ * dimension.time B ℤ) *
      ((dimension.energy B ℤ / dimension.time B ℤ) / dimension.current B ℤ) =
      dimension.energy B ℤ := by
  simp only [dimension.mul_def', dimension.div_def']
  funext i
  abel

/-- Faraday's constant is charge per amount, with charge equal to current
times time. Multiplying by an outward amount rate gives electric current. -/
theorem faraday_current_dimension (B : Type) [HasBaseCurrent B] [HasBaseTime B]
    [HasBaseAmount B] :
    ((dimension.current B ℤ * dimension.time B ℤ) / dimension.amount B ℤ) *
      (dimension.amount B ℤ / dimension.time B ℤ) = dimension.current B ℤ := by
  simp only [dimension.mul_def', dimension.div_def']
  funext i
  abel

#print axioms face_power_dimension
#print axioms charge_voltage_energy
#print axioms faraday_current_dimension
#print axioms CellsProofs.Transport.Face.power_in_pJ_per_s
#print axioms CellsProofs.Tissue.CurrentInjection.single_patch_work

end CellsProofs.Checks
