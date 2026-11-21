import CellsProofs.Chemistry.BindingEnsemble
import PhysLean.StatisticalMechanics.CanonicalEnsemble.Finite
import Mathlib.Tactic.FieldSimp

namespace CellsProofs.Checks.BindingEnsemble

open CellsProofs.Chemistry.BindingEnsemble MeasureTheory

variable {F : Type} [Fintype F] [MeasurableSpace F] [MeasurableSingletonClass F]

/-- At the chosen reservoir conditions each dimensionless log weight gives an effective
energy in the units used by Physlib. Counting measure counts each declared state once. -/
noncomputable def ensemble (a : F → ℝ) (T : Temperature) : CanonicalEnsemble F where
  energy := fun i => -a i / (T.β : ℝ)
  energy_measurable := measurable_of_finite _
  μ := Measure.count

instance (a : F → ℝ) (T : Temperature) : CanonicalEnsemble.IsFinite (ensemble a T) :=
  ⟨rfl⟩

/-- A choice of common energy zero has no effect on the result for an existing ensemble. -/
theorem canonical_fraction_of_energy (C : CanonicalEnsemble F) [CanonicalEnsemble.IsFinite C]
    (T : Temperature) (a : F → ℝ) (s : ℝ) (h : ∀ i, -(T.β : ℝ) * C.energy i = a i - s)
    (f : F) : C.probability T f = fraction a f := by
  rw [CanonicalEnsemble.probability, CanonicalEnsemble.partitionFunction_of_fintype]
  simp_rw [h]
  exact fraction_shift a f s

/-- The finite canonical law gives the Cells probability for every binding form and every
signed ligand-count vector at fixed positive inverse temperature and fixed free activities. -/
theorem canonical_binding_fraction {L : Type} [Fintype L] (logBeta : F → ℝ)
    (counts : F → L → ℤ) (u : L → ℝ) (T : Temperature) (hT : 0 < (T.β : ℝ)) (f : F) :
    let a := fun i => logWeight (logBeta i) (counts i) u
    (ensemble a T).probability T f = fraction a f := by
  let a := fun i => logWeight (logBeta i) (counts i) u
  change (ensemble a T).probability T f = fraction a f
  have boltzmann (i : F) : -(T.β : ℝ) * (ensemble a T).energy i = a i := by
    change -(T.β : ℝ) * (-a i / (T.β : ℝ)) = a i
    field_simp [hT.ne']
  exact canonical_fraction_of_energy (ensemble a T) T a 0 (by simpa using boltzmann) f

#print axioms canonical_fraction_of_energy
#print axioms canonical_binding_fraction

end CellsProofs.Checks.BindingEnsemble
