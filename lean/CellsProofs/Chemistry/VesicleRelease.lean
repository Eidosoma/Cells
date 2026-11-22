import Mathlib.Algebra.BigOperators.Group.Finset.Piecewise
import Mathlib.Data.Int.Cast.Basic

/-! # Returning the contents of a ruptured vesicle to its pool places -/

namespace CellsProofs.Chemistry.VesicleRelease

variable {Place Pool : Type*} [DecidableEq Pool]

/-- Counts at one pool place and signed cumulative supply from its reservoir. -/
structure Account where
  count : ℕ
  supplied : ℤ

/-- Apply one source place's receipt to its named destination. -/
def book (held : Pool → Bool) (dest : Pool) (amount : ℕ) (s : Pool → Account) (p : Pool) :
    Account :=
  if dest = p then
    if held p then ⟨(s p).count, (s p).supplied - amount⟩
    else ⟨(s p).count + amount, (s p).supplied⟩
  else s p

/-- The release record groups the membrane and lumen amounts by pool destination. -/
def returned (places : List Place) (dest : Place → Pool) (amount : Place → ℕ) (p : Pool) : ℕ :=
  (places.map fun i => if dest i = p then amount i else 0).sum

/-- Starting with the triggering step's own state, booking the whole release in any listed order
increases a finite pool or debits a held reservoir by exactly its recorded receipt. -/
theorem release_ledger (places : List Place) (dest : Place → Pool) (amount : Place → ℕ)
    (held : Pool → Bool) (s : Pool → Account) (p : Pool) :
    let final := places.foldl (fun acc i => book held (dest i) (amount i) acc) s
    (final p).count = (s p).count + (if held p then 0 else returned places dest amount p) ∧
      (final p).supplied = (s p).supplied -
        (if held p then (returned places dest amount p : ℤ) else 0) := by
  induction places generalizing s with
  | nil => simp [returned]
  | cons i tail ih =>
    simp only [List.foldl_cons]
    obtain ⟨hc, hs⟩ := ih (book held (dest i) (amount i) s)
    by_cases hi : dest i = p <;> cases hp : held p <;>
      simp [book, returned, hi, hp] at hc hs ⊢ <;> omega

/-- If every membrane and lumen place is listed once, summing all recipients counts every
vesicle molecule once, including when several source places have the same destination. -/
theorem total_returned [Fintype Pool] (places : List Place) (dest : Place → Pool)
    (amount : Place → ℕ) :
    ∑ p, returned places dest amount p = (places.map amount).sum := by
  induction places with
  | nil => simp [returned]
  | cons i tail ih =>
    simp only [returned, List.map_cons, List.sum_cons, Finset.sum_add_distrib] at ih ⊢
    simpa using ih

end CellsProofs.Chemistry.VesicleRelease
