import CellsProofs.Chemistry.ShellLigandFaces
import Mathlib.Tactic.DeriveFintype

/-! Exact FR-46 controls for two ligand moieties and one wall scaffold. -/

namespace CellsProofs.Checks.ShellLigandFaces

open CellsProofs.Chemistry.ShellLigandFaces
open Relation (ReflTransGen)

#print axioms face_along_path
#print axioms possible_origin
#print axioms sealed_lumen

inductive Place | xPool | xLumen | yLumen | r | a | c | d | b deriving DecidableEq, Fintype
inductive Event | bindX | bindY | rearrange | releaseX deriving DecidableEq, Fintype
inductive Moiety | x | y | scaffold deriving DecidableEq, Fintype

-- X_out + R → A, Y_in + A → C, C → D, D → X_in + B.
private def take : Event → Place → ℕ
  | .bindX, .xPool | .bindX, .r | .bindY, .yLumen | .bindY, .a
  | .rearrange, .c | .releaseX, .d => 1
  | _, _ => 0

private def give : Event → Place → ℕ
  | .bindX, .a | .bindY, .c | .rearrange, .d | .releaseX, .xLumen | .releaseX, .b => 1
  | _, _ => 0

private def copies : Moiety → Place → ℕ
  | .x, .xPool | .x, .xLumen | .x, .a | .x, .c | .x, .d => 1
  | .y, .yLumen | .y, .c | .y, .d | .y, .b => 1
  | .scaffold, .r | .scaffold, .a | .scaffold, .c | .scaffold, .d | .scaffold, .b => 1
  | _, _ => 0

private theorem material_balance : ∀ m r, ∑ p, copies m p * take r p = ∑ p, copies m p * give r p := by
  decide

private def founder : Place → ℕ
  | .xPool | .yLumen | .r => 1
  | _ => 0

private def fire (s : Place → ℕ) (r : Event) : Place → ℕ := fun p => s p - take r p + give r p

private theorem enabled (s : Place → ℕ) (r : Event) (h : ∀ p, take r p ≤ s p) :
    Fires take give s (fire s r) := ⟨r, h, fun _ => rfl⟩

private def afterBinding := fire (fire founder .bindX) .bindY
private def finalState := fire (fire afterBinding .rearrange) .releaseX

private theorem history : ReflTransGen (Fires take give) founder finalState :=
  ((((ReflTransGen.single (enabled founder .bindX (by decide))).tail
    (enabled _ .bindY (by decide))).tail (enabled afterBinding .rearrange (by decide))).tail
    (enabled _ .releaseX (by decide)))

example : founder .xLumen = 0 ∧ finalState .xLumen = 1 ∧ finalState .xPool = 0 ∧ finalState .b = 1 := by
  decide

-- The one copy of X has an outer origin even though the second event binds Y.
example : ReflTransGen (Carries (copies .x) take give) .xPool .xLumen := by
  obtain ⟨src, present, path⟩ := possible_origin (copies .x) take give (material_balance .x)
    history .xLumen (by decide)
  have onlyPool : ∀ p, 0 < copies .x p * founder p → p = .xPool := by decide
  exact onlyPool src present ▸ path

private def inner : Place → Bool
  | .xLumen | .yLumen | .c | .d | .b => true
  | _ => false

private theorem other_events_respect_x : ∀ r i j, r ≠ Event.bindY →
    0 < copies .x i * take r i → 0 < copies .x j * give r j → inner i = inner j := by decide

example : 0 < copies .x .a * take .bindY .a ∧ 0 < copies .x .c * give .bindY .c ∧
    inner .a ≠ inner .c := by decide

-- Keeping the same-face isomerization C → D and removing the crossing event seals the lumen.
private abbrev SameFaceEvent := { r : Event // r ≠ .bindY }

example {stop : Place → ℕ} (h : ReflTransGen
    (Fires (fun r : SameFaceEvent => take r.val) (fun r : SameFaceEvent => give r.val)) founder stop) :
    stop .xLumen = 0 := by
  apply sealed_lumen (copies .x) _ _ (fun r : SameFaceEvent => material_balance .x r.val) inner
    .xLumen (by decide) rfl ?_ (by decide) h
  intro i j edge
  obtain ⟨r, hi, hj⟩ := edge
  exact other_events_respect_x r.val i j r.property hi hj

-- A preloaded inner complex releases X even when the initial free lumen count is zero.
private def preload : Place → ℕ | .d => 1 | _ => 0

example : preload .xLumen = 0 ∧ Fires take give preload (fire preload .releaseX) ∧
    (fire preload .releaseX) .xLumen = 1 := ⟨rfl, enabled _ _ (by decide), rfl⟩

end CellsProofs.Checks.ShellLigandFaces
