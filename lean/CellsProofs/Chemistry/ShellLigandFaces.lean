import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Logic.Relation

/-! # Ligand access to a sealed shell

A place is a free pool or a wall species. Its weight counts copies of one
selected ligand moiety. Each event lists all consumed and produced counts.
A possible transfer connects any consumed and produced places carrying that
moiety, including during binding or release of a different ligand. -/

namespace CellsProofs.Chemistry.ShellLigandFaces

variable {Place Event : Type*}

/-- Possible transfer of the selected ligand during one directed event. -/
def Carries (copies : Place → ℕ) (take give : Event → Place → ℕ) (src dst : Place) : Prop :=
  ∃ r, 0 < copies src * take r src ∧ 0 < copies dst * give r dst

/-- One event consumes available molecules and adds its products. -/
def Fires (take give : Event → Place → ℕ) (before after : Place → ℕ) : Prop :=
  ∃ r, (∀ p, take r p ≤ before p) ∧ ∀ p, after p = before p - take r p + give r p

/-- A face assignment respected by each transfer is respected along every finite path. -/
theorem face_along_path (copies : Place → ℕ) (take give : Event → Place → ℕ)
    (inner : Place → Bool)
    (admitted : ∀ i j, Carries copies take give i j → inner i = inner j)
    {src dst : Place} (path : Relation.ReflTransGen (Carries copies take give) src dst) :
    inner src = inner dst :=
  Relation.reflTransGen_minimal (r' := fun i j => inner i = inner j)
    (fun _ => rfl) (fun _ _ _ h₁ h₂ => h₁.trans h₂) admitted path

variable [Fintype Place] (copies : Place → ℕ) (take give : Event → Place → ℕ)
    (balanced : ∀ r, ∑ p, copies p * take r p = ∑ p, copies p * give r p)

include balanced

private theorem one_step_origin {before after : Place → ℕ} (step : Fires take give before after)
    (dst : Place) (occupied : 0 < copies dst * after dst) :
    ∃ src, 0 < copies src * before src ∧ Relation.ReflTransGen (Carries copies take give) src dst := by
  by_cases stays : 0 < copies dst * before dst
  · exact ⟨dst, stays, .refl⟩
  obtain ⟨r, enabled, update⟩ := step
  have weight : copies dst ≠ 0 := by
    intro h
    simp [h] at occupied
  have empty : before dst = 0 := (Nat.mul_eq_zero.mp (Nat.eq_zero_of_not_pos stays)).resolve_left weight
  have produced : 0 < copies dst * give r dst := by
    simpa [update dst, empty] using occupied
  have consumed : 0 < ∑ p, copies p * take r p := by
    rw [balanced r]
    exact produced.trans_le (Finset.single_le_sum (fun p _ => Nat.zero_le (copies p * give r p))
      (Finset.mem_univ dst))
  obtain ⟨src, used⟩ : ∃ src, 0 < copies src * take r src := by
    by_contra missing
    have zero : ∀ p, copies p * take r p = 0 :=
      fun p => Nat.eq_zero_of_not_pos (fun positive => missing ⟨p, positive⟩)
    simp [zero] at consumed
  exact ⟨src, used.trans_le (Nat.mul_le_mul_left _ (enabled src)), .single ⟨r, used, produced⟩⟩

/-- Occupied copies have an initially occupied origin connected by a possible transfer path. -/
theorem possible_origin {start stop : Place → ℕ} (history : Relation.ReflTransGen (Fires take give) start stop) :
    ∀ dst, 0 < copies dst * stop dst →
      ∃ src, 0 < copies src * start src ∧ Relation.ReflTransGen (Carries copies take give) src dst := by
  induction history with
  | refl => exact fun dst h => ⟨dst, h, .refl⟩
  | tail _ step ih =>
    intro dst h
    obtain ⟨mid, hm, edge⟩ := one_step_origin copies take give balanced step dst h
    obtain ⟨src, hs, path⟩ := ih mid hm
    exact ⟨src, hs, path.trans edge⟩

/-- A lumen that starts empty stays empty if all inner-accessible places start free of the
selected moiety and every event preserves its face. This includes initially bound ligand. -/
theorem sealed_lumen (inner : Place → Bool) (lumen : Place) (freeLigand : 0 < copies lumen)
    (onInside : inner lumen = true)
    (admitted : ∀ i j, Carries copies take give i j → inner i = inner j)
    {start stop : Place → ℕ} (initial : ∀ p, inner p = true → copies p * start p = 0)
    (history : Relation.ReflTransGen (Fires take give) start stop) : stop lumen = 0 := by
  by_contra occupied
  obtain ⟨src, present, path⟩ := possible_origin copies take give balanced history lumen
    (Nat.mul_pos freeLigand (Nat.pos_of_ne_zero occupied))
  have onFace := face_along_path copies take give inner admitted path
  have empty := initial src (onFace.trans onInside)
  omega

end CellsProofs.Chemistry.ShellLigandFaces
