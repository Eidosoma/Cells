import CRNT.Examples.Enzyme
import CellsProofs.Chemistry.Enzyme
import Mathlib.Tactic.NormNum
import Biosim.Proofs.Invariants
import Pythia.Frontier.Chemistry.Eyring
import CellsProofs.Chemistry.AssemblyKinetics

/-! The CRNT example separates binding and unbinding. Cells uses a signed
binding extent at a site and a second column for catalysis. -/
namespace CellsChecks.CRNTEnzyme

open CRNT.Examples.Enzyme (N Rxn)
open CellsProofs.Chemistry.Enzyme (net)

private def upstreamSpecies : CellsProofs.Chemistry.Enzyme.Species → CRNT.Examples.Enzyme.Species
  | .E => .E
  | .S => .S
  | .C => .ES
  | .P => .P

/-- Each upstream directed column has the sign and species of the Cells declaration. -/
theorem species_columns (r : Rxn) (s : CellsProofs.Chemistry.Enzyme.Species) :
    N.reactionVector r (upstreamSpecies s) =
      match r with
      | .bind => (net .binding s : ℝ)
      | .unbind => -(net .binding s : ℝ)
      | .catalyze => (net .catalysis s : ℝ) := by
  change ((CRNT.Examples.Enzyme.rxn r).target (upstreamSpecies s) : ℝ) -
    ((CRNT.Examples.Enzyme.rxn r).source (upstreamSpecies s) : ℝ) = _
  cases r <;> cases s <;>
    norm_num [upstreamSpecies, net, CRNT.Examples.Enzyme.rxn, CRNT.Examples.Enzyme.cES_sub,
      CRNT.Examples.Enzyme.cESbound, CRNT.Examples.Enzyme.cEP]

/-- At a fixed volume, converting the two concentration rates to amounts
preserves the upstream enzyme balance. One mM times one pL is one fmol. -/
theorem enzyme_amount_rate (volume_pL : ℝ) (rates : N.RateConstants)
    (c : CRNT.Concentration CRNT.Examples.Enzyme.Species) :
    volume_pL * N.massActionVectorField rates c .E +
      volume_pL * N.massActionVectorField rates c .ES = 0 := by
  rw [← mul_add, CRNT.Examples.Enzyme.total_enzyme_conserved, mul_zero]

#print axioms species_columns
#print axioms enzyme_amount_rate

end CellsChecks.CRNTEnzyme

namespace CellsChecks.CountExchange

open Biosim.Core Biosim.Proofs

/-- False is the finite pool, true is the membrane, for one chemical species. -/
noncomputable local instance : Species Bool where
  toFintype := inferInstance
  decEq := inferInstance

private noncomputable def join (rate : State Bool → NNReal) : Reaction Bool where
  inStoich := Finsupp.single false 1
  outStoich := Finsupp.single true 1
  rate := rate

private def molecules : LinInv Bool := ⟨fun _ => 1⟩

theorem one_molecule_join (rate : State Bool → NNReal) (x : State Bool)
    (h : System.enabled x (join rate)) :
    weight molecules (System.fire x (join rate) h) = weight molecules x := by
  apply fire_preserves_weight molecules x (join rate) h
  rw [conservedBy_iff]
  simp [join, molecules]

#print axioms one_molecule_join
end CellsChecks.CountExchange

namespace CellsChecks.SingleContact
open Pythia.Frontier.Chemistry CellsProofs.Chemistry.AssemblyKinetics

/-- A molar stabilization lowers the barrier from G to G - δ. The engine stores δ/(R*T). -/
theorem rate_ratio (κ kB h T R G δ : ℝ)
    (hκ : 0 < κ) (hk : 0 < kB) (hh : 0 < h) (hT : 0 < T) (hR : 0 < R) :
    eyringRate κ kB h T (G - δ) R / eyringRate κ kB h T G R =
      catalyst (fun _ : Unit => δ / (R * T))
        (CellsProofs.Chemistry.ReservoirExchange.addOne (fun _ => 0) ()) := by
  rw [single_contact]
  apply (div_eq_iff (eyringRate_pos hκ hk hh hT hR).ne').2
  have split : -(G - δ) / (R * T) = -G / (R * T) + δ / (R * T) := by ring
  unfold eyringRate
  rw [split, Real.exp_add]
  ring

#print axioms rate_ratio
end CellsChecks.SingleContact
