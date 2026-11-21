import PhysLean.StatisticalMechanics.CanonicalEnsemble.TwoState
import Mathlib.Tactic.FieldSimp

namespace CellsProofs.Checks

/-- When the fitted gate coordinate is the dimensionless open-state energy gap,
the second state's equilibrium probability has the form used by the Cells gate. -/
theorem boltzmann_gate_equilibrium (E : ℝ) (T : Temperature) {u : ℝ}
    (hu : (T.β : ℝ) * E = u) :
    (CanonicalEnsemble.twoState E).probability T 1 = 1 / (1 + Real.exp u) := by
  rw [CanonicalEnsemble.probability, CanonicalEnsemble.twoState_energy_snd,
    CanonicalEnsemble.twoState_partitionFunction_apply_eq_one_add_exp, neg_mul, hu, Real.exp_neg]
  field_simp [Real.exp_ne_zero, (add_pos_of_pos_of_nonneg zero_lt_one (Real.exp_pos u).le).ne']
  exact add_comm _ _

#print axioms boltzmann_gate_equilibrium

end CellsProofs.Checks
