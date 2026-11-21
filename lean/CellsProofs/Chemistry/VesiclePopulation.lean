import CellsProofs.Chemistry.SharedPool
import CellsProofs.Chemistry.Vesicle

/-! # Molecular and free-energy accounts at serial transfer and vesicle fission -/

namespace CellsProofs.Chemistry.VesiclePopulation

open scoped BigOperators

variable {Slot : Type*} [Fintype Slot]

/-- The amount retained in each slot, for any realized sample of the population. -/
def retained {A : Type*} [Zero A] (keep : Slot → Bool) (x : Slot → A) (i : Slot) :=
  if keep i then x i else 0

theorem partition_slots {A : Type*} [AddCommMonoid A] (keep : Slot → Bool) (x : Slot → A) :
    (∑ i, retained keep x i) + (∑ i, retained (fun j => !keep j) x i) = ∑ i, x i := by
  rw [← Finset.sum_add_distrib]
  apply Finset.sum_congr rfl
  intro i _
  cases h : keep i <;> simp [retained, h]

def transfer (keep : Slot → Bool) (fresh : ℕ) (s : SharedPool.State Slot) :
    SharedPool.State Slot := ⟨fresh, retained keep s.slots⟩

/-- For each species, the spent bath and removed vesicles account for everything exported. -/
theorem transfer_inventory (keep : Slot → Bool) (fresh : ℕ) (s : SharedPool.State Slot) :
    SharedPool.inventory (transfer keep fresh s) +
      (s.pool + ∑ i, retained (fun j => !keep j) s.slots i) = SharedPool.inventory s + fresh := by
  simp only [transfer, SharedPool.inventory, ReservoirExchange.size]
  have := partition_slots keep s.slots
  omega

omit [Fintype Slot] in
/-- Across successive washes, a vesicle's cargo survives exactly when it is kept both times. -/
theorem successive_transfers (a b : Slot → Bool) (u v : ℕ) (s : SharedPool.State Slot) :
    transfer b v (transfer a u s) = transfer (fun i => a i && b i) v s := by
  unfold transfer
  congr 1
  funext i
  cases ha : a i <;> cases hb : b i <;> simp [retained, ha, hb]

/-- Replace the bath and discard whole vesicles, booking their signed free energies. -/
theorem transfer_free_energy (keep : Slot → Bool) (f : Slot → ℝ) (old fresh : ℝ) :
    (fresh + ∑ i, retained keep f i) - (old + ∑ i, f i) =
      fresh - (old + ∑ i, retained (fun j => !keep j) f i) := by
  linarith [partition_slots keep f]

variable {M D S : Type*} [Fintype M] [Fintype D] [DecidableEq D] [DecidableEq S]

def parentCount (species : M → S) (s : S) : ℕ := ∑ m, if species m = s then 1 else 0

/-- Each individual membrane or lumen molecule has one destination in an accepted split. -/
def daughterCount (species : M → S) (dest : M → D) (d : D) (s : S) : ℕ :=
  ∑ m, if species m = s ∧ dest m = d then 1 else 0

theorem split_inventory (species : M → S) (dest : M → D) (s : S) :
    ∑ d, daughterCount species dest d s = parentCount species s := by
  unfold daughterCount parentCount
  rw [Finset.sum_comm]
  apply Finset.sum_congr rfl
  intro m _
  by_cases h : species m = s <;> simp [h]

/-- A continued lineage and its discarded siblings jointly contain the parent's inventory. -/
theorem followed_and_siblings (species : M → S) (dest : M → D) (follow : D) (s : S) :
    (∑ d ∈ Finset.univ.erase follow, daughterCount species dest d s) +
      daughterCount species dest follow s = parentCount species s := by
  rw [Finset.sum_erase_add _ _ (Finset.mem_univ follow), split_inventory]

/-- Conservation extends to heterogeneous integer footprints of membrane species. -/
theorem split_footprint [Fintype S] (species : M → S) (dest : M → D) (weight : S → ℕ) :
    ∑ d, Vesicle.footprint (daughterCount species dest d) weight =
      Vesicle.footprint (parentCount species) weight := by
  unfold Vesicle.footprint
  rw [Finset.sum_comm]
  simp_rw [← Finset.sum_mul, split_inventory]

/-- If the parent has too little membrane to supply every daughter's floor, every
partition must fail the floor test, even with heterogeneous lipid footprints. -/
theorem insufficient_footprint [Fintype S] (species : M → S) (dest : M → D) (weight : S → ℕ)
    (floor : ℕ) (small : Vesicle.footprint (parentCount species) weight < Fintype.card D * floor) :
    ∃ d, Vesicle.footprint (daughterCount species dest d) weight < floor := by
  by_contra! large
  have h : (∑ _ : D, floor) ≤ ∑ d, Vesicle.footprint (daughterCount species dest d) weight :=
    Finset.sum_le_sum (fun d _ => large d)
  rw [split_footprint] at h
  simp only [Finset.sum_const, Finset.card_univ, nsmul_eq_mul] at h
  exact (not_lt_of_ge h) small

/-- With one common linear calibration and zero background, the combined tracer signal
equals the parent's at the split, before any subsequent leakage or lysis. -/
theorem split_signal (species : M → S) (dest : M → D) (tracer : S) (gain : ℝ) :
    ∑ d, gain * (daughterCount species dest d tracer : ℝ) =
      gain * (parentCount species tracer : ℝ) := by
  rw [← Finset.mul_sum, ← Nat.cast_sum, split_inventory]

/-- Shear work includes all daughters. Following one books its siblings as an outgoing sink. -/
theorem followed_free_energy (daughter : D → ℝ) (parent : ℝ) (follow : D) :
    daughter follow - parent = ((∑ d, daughter d) - parent) -
      (∑ d ∈ Finset.univ.erase follow, daughter d) := by
  rw [← Finset.sum_erase_add _ _ (Finset.mem_univ follow)]
  ring

omit [DecidableEq D] in
/-- In k daughters, a common per-vesicle closure cost contributes (k - 1) times that cost. -/
theorem closure_work (internal : D → ℝ) (parent closure : ℝ) :
    (∑ d, (internal d + closure)) - (parent + closure) =
      ((∑ d, internal d) - parent) + ((Fintype.card D : ℝ) - 1) * closure := by
  rw [Finset.sum_add_distrib]
  simp
  ring

/-- In consistent units the cubed-area gate is equivalent to fitting the parent volume
in k equal-area spherical daughters. Equality is admitted. -/
theorem volume_gate {a v k : ℝ} (ha : 0 ≤ a) (hv : 0 ≤ v) (hk : 0 < k) :
    36 * Real.pi * k * v ^ 2 ≤ a ^ 3 ↔ v ≤ Vesicle.sphere a / Real.sqrt k := by
  have hs : 0 ≤ Vesicle.sphere a := by unfold Vesicle.sphere Vesicle.radius; positivity
  have cap : 36 * Real.pi * Vesicle.sphere a ^ 2 = a ^ 3 := by
    unfold Vesicle.sphere
    linear_combination (a ^ 2) * Vesicle.radius_area ha
  rw [le_div_iff₀ (Real.sqrt_pos.2 hk), ← sq_le_sq₀ (by positivity) hs, mul_pow,
    Real.sq_sqrt hk.le]
  rw [← cap, mul_assoc, mul_comm k, mul_le_mul_left (show 0 < 36 * Real.pi by positivity)]

/-- For one finite species, a pool replacement keeps every slot. -/
def replacePool (fresh : ℕ) (s : SharedPool.State Slot) : SharedPool.State Slot :=
  transfer (fun _ => true) fresh s

omit [Fintype Slot] in
theorem replacement_state (fresh : ℕ) (s : SharedPool.State Slot) :
    replacePool fresh s = ⟨fresh, s.slots⟩ := rfl

theorem replacement_inventory (fresh : ℕ) (s : SharedPool.State Slot) :
    SharedPool.inventory (replacePool fresh s) + s.pool = SharedPool.inventory s + fresh := by
  simpa [replacePool, retained] using transfer_inventory (fun _ => true) fresh s

/-- After a tracer-free wash, every free or retained molecule in an exchange-only
history comes from the cargo that survived the wash. -/
theorem wash_history_inventory [DecidableEq Slot] {s t : SharedPool.State Slot}
    (moves : Relation.ReflTransGen SharedPool.Transfer (replacePool 0 s) t) :
    t.pool + ReservoirExchange.size t.slots = ReservoirExchange.size s.slots := by
  simpa [SharedPool.inventory, replacement_state] using (SharedPool.history_inventory moves).symm

/-- For additive bath and slot energies, signed fresh-bath work less the spent-bath
sink accounts for the entire free-energy change at an isolated replacement. -/
theorem replacement_energy (slotEnergy : Slot → ℝ) (old fresh : ℝ) :
    (fresh + ∑ i, slotEnergy i) - (old + ∑ i, slotEnergy i) = fresh - old := by
  simp

/-- A discrete ideal solute at the first count beyond a log-factorial table
loses exactly log(cap + 1) of free energy if its table index is clipped. -/
theorem replacement_capacity_gap (cap : ℕ) (linear : ℝ) :
    (((cap + 1 : ℕ) : ℝ) * linear + ReservoirExchange.logFactorial (cap + 1)) -
      (((cap + 1 : ℕ) : ℝ) * linear + ReservoirExchange.logFactorial (min (cap + 1) cap)) =
        Real.log ((cap : ℝ) + 1) := by
  rw [Nat.min_eq_right (Nat.le_succ cap), ReservoirExchange.logFactorial_succ]
  ring

end CellsProofs.Chemistry.VesiclePopulation
