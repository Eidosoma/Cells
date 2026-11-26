import CellsProofs.Chemistry.Polymerisation

/-! # Inventories across completion and detachment (FR-38)

A completed chain enters a terminal hold. A chain's machine returns to its pool
at completion or at detachment, according to the chain's declared policy.
All flows denote extents over the same update.
-/

namespace CellsProofs.Chemistry.TerminalRelease

open Finset Polymerisation
open scoped BigOperators

def machineReturn (held : Bool) (completion detachment : ℝ) : ℝ :=
  if held then detachment else completion

def heldMachines (held : Bool) (stock : ℝ) : ℝ := if held then stock else 0

/-- Free machines, stage occupancies and machine-bearing holds close over a shared pool. -/
theorem pool_step {ι : Type*} (chains : Finset ι) (m : ι → ℕ) (held : ι → Bool)
    (stage flow : ι → ℕ → ℝ) (stock detach : ι → ℝ) (free : ℝ) :
    (free + ∑ i ∈ chains, (machineReturn (held i) (flow i (m i)) (detach i) - flow i 0)) +
      (∑ i ∈ chains, ((∑ j ∈ range (m i), (stage i j + stageChange (flow i) j)) +
        heldMachines (held i) (stock i + flow i (m i) - detach i))) =
    free + ∑ i ∈ chains, ((∑ j ∈ range (m i), stage i j) + heldMachines (held i) (stock i)) := by
  rw [add_assoc, ← sum_add_distrib]
  apply congrArg (free + ·)
  apply sum_congr rfl
  intro i _
  simp only [sum_add_distrib, engaged_change]
  cases held i <;> simp [machineReturn, heldMachines] <;> ring

/-- Each class detaches into two fates. The split can change between updates. -/
theorem fate_sum {ι : Type*} (classes : Finset ι) (out : ι → ℝ) (p : ℝ) :
    (∑ i ∈ classes, out i * p) + (∑ i ∈ classes, out i * (1 - p)) = ∑ i ∈ classes, out i := by
  rw [← sum_add_distrib]
  apply sum_congr rfl
  intro i _
  ring

/-- An initially populated hold plus subsequent completions accounts for all detachments. -/
theorem hold_step (initial completed stock detached incoming out : ℝ) :
    initial + (completed + incoming) - (stock + incoming - out) - (detached + out) =
      initial + completed - stock - detached := by ring

/-- The stage residue balance extends through a terminal hold to cumulative physical detachments. -/
theorem residue_step (m : ℕ) (r exits stock detached out : ℝ) (stage flow : ℕ → ℝ) :
    r * (exits + ∑ j ∈ range m, flow (j + 1)) -
      (∑ j ∈ range m, (j : ℝ) * r * (stage j + stageChange flow j)) -
      (m : ℝ) * r * ((stock + flow m - out) + (detached + out)) =
    r * exits - (∑ j ∈ range m, (j : ℝ) * r * stage j) - (m : ℝ) * r * (stock + detached) := by
  have balance : (stock + flow m - out) + (detached + out) = (stock + detached) + flow m := by ring
  rw [balance]
  exact Polymerisation.residue_step m r exits (stock + detached) stage flow

/-- A fate row gains its physical detachments net of the recorded loss. -/
theorem fate_balance_step (amount initial released lost incoming loss : ℝ) :
    (amount + incoming - loss) - initial - (released + incoming) + (lost + loss) =
      amount - initial - released + lost := by ring

/-- With the initial balance and an established zero cumulative loss, the pool gain is the release. -/
theorem lossless_gain (amount initial released lost : ℝ)
    (balance : amount - initial - released + lost = 0) (zeroLoss : lost = 0) :
    amount - initial = released := by linarith

/-- A replacement after the update exports every unfinished residue and the surviving hold.
The newcomer starts with empty stages and hold, and the cumulative counters keep their values. -/
theorem replacement_residue_step (m : ℕ) (r exits stock detached out removed : ℝ)
    (stage flow : ℕ → ℝ) :
    r * (exits + ∑ j ∈ range m, flow (j + 1)) - (m : ℝ) * r * (detached + out) -
      (removed + (∑ j ∈ range m, (j : ℝ) * r * (stage j + stageChange flow j)) +
        (m : ℝ) * r * (stock + flow m - out)) =
    r * exits - (∑ j ∈ range m, (j : ℝ) * r * stage j) -
      (m : ℝ) * r * (stock + detached) - removed := by
  linarith only [residue_step m r exits stock detached out stage flow]

/-- The exported row energy includes each row's standard term. Unfinished and held residues
carry their own standard energy. This endpoint balance assigns zero heat to an exchange. -/
theorem replacement_energy {S : Type*} (rows : Finset S) (potential incoming outgoing : S → ℝ)
    (mixIn mixOut residue transit length hold : ℝ) :
    (mixIn - mixOut + ∑ s ∈ rows, potential s * (incoming s - outgoing s)) -
        residue * (transit + length * hold) +
      ((mixOut + ∑ s ∈ rows, potential s * outgoing s) + residue * (transit + length * hold)) -
      (mixIn + ∑ s ∈ rows, potential s * incoming s) = 0 := by
  simp only [mul_sub, sum_sub_distrib]
  ring

/-- Sum complete generations and the two partial intervals using the same counter reading
at each boundary. Applies separately to arrivals, detachments, removals and losses. -/
theorem generation_counter (atBirth : ℕ → ℝ) (n : ℕ) (first last : ℝ) :
    (atBirth 0 - first) + (∑ i ∈ range n, (atBirth (i + 1) - atBirth i)) +
      (last - atBirth n) = last - first := by
  rw [Finset.sum_range_sub]
  ring

end CellsProofs.Chemistry.TerminalRelease
