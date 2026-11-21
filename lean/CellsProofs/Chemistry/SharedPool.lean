import CellsProofs.Chemistry.ReservoirExchange

/-! # A finite pool shared by a population of vesicles -/

namespace CellsProofs.Chemistry.SharedPool

open ReservoirExchange (addOne size size_addOne)

variable {Slot : Type*} [Fintype Slot]

/-- Counts of one conserved species, with the common bath counted once. -/
structure State (Slot : Type*) where
  pool : ℕ
  slots : Slot → ℕ

def inventory (s : State Slot) := s.pool + size s.slots

/-- The successor on the donor side makes a withdrawal from an empty donor impossible.
Only one recipient changes. Either direction is an allowed count update. -/
inductive Transfer [DecidableEq Slot] : State Slot → State Slot → Prop where
  | enter (n : ℕ) (x : Slot → ℕ) (i : Slot) : Transfer ⟨n + 1, x⟩ ⟨n, addOne x i⟩
  | leave (n : ℕ) (x : Slot → ℕ) (i : Slot) : Transfer ⟨n, addOne x i⟩ ⟨n + 1, x⟩

theorem event_inventory [DecidableEq Slot] {s t : State Slot} (move : Transfer s t) :
    inventory s = inventory t := by
  cases move <;> simp only [inventory, size_addOne] <;> omega

/-- The single bath and all vesicles conserve the inventory through any finite event history. -/
theorem history_inventory [DecidableEq Slot] {s t : State Slot}
    (moves : Relation.ReflTransGen Transfer s t) : inventory s = inventory t := by
  induction moves with
  | refl => rfl
  | tail _ step ih => exact ih.trans (event_inventory step)

/-- Each active slot uses its own capture coefficient and the same bath number density.
An inactive slot can be represented by zero conductance. -/
noncomputable def uptake (conductance : ℝ) (n : ℕ) (volume : ℝ) :=
  conductance * ((n : ℝ) / volume)

theorem population_uptake (g : Slot → ℝ) (n : ℕ) (v : ℝ) :
    ∑ i, uptake (g i) n v = uptake (∑ i, g i) n v := by
  simp [uptake, Finset.sum_mul]

/-- After one vesicle takes a molecule, every other vesicle of unchanged conductance
loses exactly g/v in forward uptake rate. An empty finite bath supplies zero. -/
theorem depletion (g v : ℝ) (n : ℕ) :
    uptake g (n + 1) v - uptake g n v = g / v ∧ uptake g 0 v = 0 := by
  simp only [uptake, Nat.cast_add, Nat.cast_one, Nat.cast_zero, zero_div, mul_zero, and_true]
  ring

/-- Permuting the slots permutes their rates and leaves the world's exact total unchanged.
The pool-only channel group is added once regardless of the number of slots. -/
theorem relabel_rate (e : Slot ≃ Slot) (rate : Slot → ℝ) (poolOnly : ℝ) :
    poolOnly + ∑ i, rate (e i) = poolOnly + ∑ i, rate i := by rw [e.sum_comp]

/-- In two populations, the fractional recipient gain depends on the donor's fractional
loss, the initial amounts and any change in the material still in the common bath. -/
theorem fractional_gain {bath₀ bath₁ donor₀ donor₁ recv₀ recv₁ : ℝ}
    (hd : 0 < donor₀) (hr : 0 < recv₀)
    (balance : bath₀ + donor₀ + recv₀ = bath₁ + donor₁ + recv₁) :
    (recv₁ - recv₀) / recv₀ = donor₀ / recv₀ * ((donor₀ - donor₁) / donor₀) +
      (bath₀ - bath₁) / recv₀ := by
  have h : recv₁ - recv₀ = (donor₀ - donor₁) + (bath₀ - bath₁) := by linarith
  rw [h]
  field_simp [hd.ne', hr.ne']
  ring

end CellsProofs.Chemistry.SharedPool
