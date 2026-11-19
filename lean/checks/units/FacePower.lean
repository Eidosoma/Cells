import DimensionalAnalysis.Dimensions
import CellsProofs.Transport.LogMeanFace

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

#print axioms face_power_dimension
#print axioms CellsProofs.Transport.Face.power_in_pJ_per_s

end CellsProofs.Checks
