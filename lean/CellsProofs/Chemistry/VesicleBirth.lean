import CellsProofs.Chemistry.VesicleRelease

/-! # Reconstructing a shear event's pool when a daughter ruptures at birth -/

namespace CellsProofs.Chemistry.VesicleRelease

variable {Daughter Place Pool : Type*} [DecidableEq Pool]

/-- The retained daughters that rupture contribute their source places, tagged by daughter.
In a population all daughters are retained. A single lineage retains only its followed daughter. -/
def birthCargo (daughters : List Daughter) (releases : Daughter → Bool)
    (places : Daughter → List Place) : List (Daughter × Place) :=
  daughters.flatMap fun d => if releases d then (places d).map (d, ·) else []

/-- The receipts at one pool place sum those of the selected daughters, even when their
source places share that destination. A daughter sent to the sink contributes zero. -/
theorem birth_receipts (daughters : List Daughter) (releases : Daughter → Bool)
    (places : Daughter → List Place) (dest : Place → Pool) (amount : Daughter → Place → ℕ)
    (p : Pool) :
    returned (birthCargo daughters releases places) (fun x => dest x.2)
        (fun x => amount x.1 x.2) p =
      (daughters.map fun d => if releases d then returned (places d) dest (amount d) p else 0).sum := by
  induction daughters with
  | nil => simp [birthCargo, returned]
  | cons d ds ih =>
    cases h : releases d <;>
      simpa [birthCargo, returned, h, List.map_append, List.sum_append, Function.comp_def] using ih

/-- Starting at the split, book each selected molecule as in R9. The finite receipt can be
subtracted from the final population pool without underflow. A held pool's signed supply can
be recovered by adding its receipt. Reading the single-lineage pool forward gives the same ledger. -/
theorem birth_pool_reconstruction (daughters : List Daughter) (releases : Daughter → Bool)
    (places : Daughter → List Place) (dest : Place → Pool) (amount : Daughter → Place → ℕ)
    (held : Pool → Bool) (before : Pool → Account) (p : Pool) :
    let receipt := (daughters.map fun d =>
      if releases d then returned (places d) dest (amount d) p else 0).sum
    let after := (birthCargo daughters releases places).foldl
      (fun s x => book held (dest x.2) (amount x.1 x.2) s) before
    let finite := if held p then 0 else receipt
    let reservoir : ℤ := if held p then (receipt : ℤ) else 0
    (after p).count = (before p).count + finite ∧
      finite ≤ (after p).count ∧ (after p).count - finite = (before p).count ∧
      (after p).supplied = (before p).supplied - reservoir ∧
      (after p).supplied + reservoir = (before p).supplied := by
  dsimp only
  obtain ⟨hc, hs⟩ := release_ledger (birthCargo daughters releases places)
    (fun x => dest x.2) (fun x => amount x.1 x.2) held before p
  rw [birth_receipts] at hc hs
  exact ⟨hc, by omega, by omega, hs, by omega⟩

end CellsProofs.Chemistry.VesicleRelease
