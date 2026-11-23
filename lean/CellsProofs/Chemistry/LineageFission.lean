import CellsProofs.Chemistry.VesiclePopulation
import Mathlib.Data.Finset.Powerset

/-! # Size-triggered binary fission and the one continued lineage -/

namespace CellsProofs.Chemistry.LineageFission

variable {n k : ℕ}

/-- The occupied places in the first k ranks of the engine's stable ordering. -/
def rankedFirst (rank : Fin n ≃ Fin n) (h : k ≤ n) : Finset (Fin n) :=
  Finset.univ.map ((Fin.castLEEmb h).trans rank.symm.toEmbedding)

theorem mem_rankedFirst (rank : Fin n ≃ Fin n) (h : k ≤ n) (i : Fin n) :
    i ∈ rankedFirst rank h ↔ (rank i).val < k := by
  simp only [rankedFirst, Finset.mem_map, Finset.mem_univ, true_and]
  constructor
  · rintro ⟨j, rfl⟩
    simp
  · intro hi
    exact ⟨⟨(rank i).val, hi⟩, rank.symm_apply_apply i⟩

theorem ranked_sizes (rank : Fin n ≃ Fin n) (h : k ≤ n) :
    (rankedFirst rank h).card = k ∧ (rankedFirst rank h)ᶜ.card = n - k := by
  simp [rankedFirst, Finset.card_compl]

/-- Between splits each event moves one molecule. At the threshold either daughter
can be followed, and a daughter retaining the whole parent can divide at birth. -/
inductive SizeStep (threshold : ℕ) : ℕ → ℕ → Prop where
  | join (m : ℕ) (alive : 0 < m) (below : m < threshold) : SizeStep threshold m (m + 1)
  | leave (m : ℕ) (below : m + 1 < threshold) : SizeStep threshold (m + 1) m
  | divide (kept sibling : ℕ) (total : kept + sibling = threshold) :
      SizeStep threshold threshold kept

theorem threshold_history {threshold initial last : ℕ} (start : initial ≤ threshold)
    (history : Relation.ReflTransGen (SizeStep threshold) initial last) : last ≤ threshold := by
  induction history with
  | refl => exact start
  | tail _ step _ => cases step <;> omega

/-- This holds for either partition rule and for either daughter label. -/
theorem binary_inventory {S : Type*} [DecidableEq S]
    (species : Fin n → S) (side : Fin n → Bool) (s : S) :
    VesiclePopulation.daughterCount species side true s +
      VesiclePopulation.daughterCount species side false s = VesiclePopulation.parentCount species s := by
  simpa [Fintype.sum_bool] using VesiclePopulation.split_inventory species side s

/-- At an exact-fraction division, both daughters start below the trigger. The ranked
places also determine the two counts whose sum recovers the parent for each species. -/
theorem ranked_division {S : Type*} [DecidableEq S]
    (rank : Fin n ≃ Fin n) (species : Fin n → S) (hk : 0 < k) (hlt : k < n) :
    let kept := rankedFirst rank hlt.le
    kept.card = k ∧ keptᶜ.card = n - k ∧
      (0 < kept.card ∧ kept.card < n) ∧ (0 < keptᶜ.card ∧ keptᶜ.card < n) ∧
      ∀ s, let side := fun i => decide (i ∈ kept)
           VesiclePopulation.daughterCount species side true s +
             VesiclePopulation.daughterCount species side false s =
               VesiclePopulation.parentCount species s := by
  obtain ⟨first, second⟩ := ranked_sizes rank hlt.le
  dsimp only
  exact ⟨first, second, by omega, by omega, fun s => binary_inventory species _ s⟩

/-- Under equiprobable size-k subsets, these are the numerator and denominator
for the probability that a named daughter receives zero marked molecules. -/
theorem fixed_quota_no_marker (marked : Finset (Fin n)) (k : ℕ) :
    (((Finset.univ.powersetCard k).filter fun a : Finset (Fin n) => Disjoint a marked).card =
        (n - marked.card).choose k) ∧
      ((Finset.univ : Finset (Fin n)).powersetCard k).card = n.choose k := by
  have subsets : (Finset.univ.powersetCard k).filter (fun a => Disjoint a marked) =
      markedᶜ.powersetCard k := by
    ext a
    simp only [Finset.mem_filter, Finset.mem_powersetCard, Finset.subset_univ, true_and]
    change a.card = k ∧ Disjoint a marked ↔ a ≤ markedᶜ ∧ a.card = k
    rw [le_compl_iff_disjoint_right, and_comm]
  simp [subsets, Finset.card_powersetCard, Finset.card_compl]

/-- For independent fair assignments all subsets have equal weight. The empty-marker
frequency counts only the marked molecules, even if the parent has other material. -/
theorem fair_split_no_marker (marked : Finset (Fin n)) :
    ((Finset.univ.powerset.filter fun a : Finset (Fin n) => Disjoint a marked).card =
        2 ^ (n - marked.card)) ∧
      (Finset.univ : Finset (Fin n)).powerset.card = 2 ^ n := by
  have subsets : Finset.univ.powerset.filter (fun a => Disjoint a marked) =
      markedᶜ.powerset := by
    ext a
    simp only [Finset.mem_filter, Finset.mem_powerset, Finset.subset_univ, true_and]
    exact le_compl_iff_disjoint_right.symm
  rw [subsets]
  simp [Finset.card_compl]

/-- Sum the independent assignment weights with every marked molecule excluded from
the first daughter. For 0 ≤ p ≤ 1 this is the probability of receiving no markers. -/
theorem independent_no_marker (marked : Finset (Fin n)) (p : ℝ) :
    (∑ a ∈ (Finset.univ : Finset (Fin n)).powerset,
      (∏ i ∈ a, if i ∈ marked then 0 else p) *
      (∏ _i ∈ Finset.univ \ a, (1 - p))) = (1 - p) ^ marked.card := by
  rw [← Finset.prod_add]
  calc
    _ = ∏ i : Fin n, (if i ∈ marked then 1 - p else 1) := by
      apply Finset.prod_congr rfl
      intro i _
      split_ifs <;> ring
    _ = _ := by simp [Fintype.prod_ite_mem]

/-- Expectation of a count observable after n independent molecule assignments. -/
noncomputable def trialAverage (p : ℝ) : ℕ → (ℕ → ℝ) → ℝ
  | 0, f => f 0
  | n + 1, f => (1 - p) * trialAverage p n f + p * trialAverage p n (fun k => f (k + 1))

private theorem count_moments (p : ℝ) (n : ℕ) (a : ℝ) :
    trialAverage p n (fun k => a + k) = a + n * p ∧
    trialAverage p n (fun k => (a + k) ^ 2) = (a + n * p) ^ 2 + n * p * (1 - p) := by
  induction n generalizing a with
  | zero => simp [trialAverage]
  | succ n ih =>
    have h := ih a
    have h' := ih (a + 1)
    have shift (k : ℕ) : a + ((k + 1 : ℕ) : ℝ) = a + 1 + k := by push_cast; ring
    have m₁ := (congrArg (trialAverage p n) (funext shift)).trans h'.1
    have m₂ := (congrArg (trialAverage p n)
      (funext fun k => congrArg (fun x : ℝ => x ^ 2) (shift k))).trans h'.2
    simp only [trialAverage]
    rw [m₁, m₂, h.1, h.2, Nat.cast_succ]
    constructor <;> ring

/-- At fixed parent count n, the named daughter's mean and variance in the binomial rule. -/
theorem binomial_moments (p : ℝ) (n : ℕ) :
    trialAverage p n (fun k => (k : ℝ)) = n * p ∧
    trialAverage p n (fun k => (k : ℝ) ^ 2) -
      (trialAverage p n (fun k => (k : ℝ))) ^ 2 = n * p * (1 - p) := by
  have h := count_moments p n 0
  simp only [zero_add] at h
  rw [h.1, h.2]
  exact ⟨rfl, by ring⟩

/-- Apply the empty-daughter policy to the size of the originally selected daughter. -/
def followedSize (fallback : Bool) (picked sibling : ℕ) : ℕ :=
  if fallback && decide (picked = 0) && decide (0 < sibling) then sibling else picked

theorem nonempty_fallback (a b : ℕ) :
    0 < followedSize true a b ↔ 0 < a + b := by
  cases a <;> cases b <;> simp [followedSize]

/-- For a fair initial pick, the two possible retained sizes sum to the parent size
plus one extra copy of that size exactly when one daughter is empty. Divide by two
to obtain the mean across the two choices for this particular split. -/
theorem fallback_selection_bias (a b : ℕ) :
    followedSize true a b + followedSize true b a =
      (a + b) + (if a = 0 ∨ b = 0 then a + b else 0) := by
  by_cases ha : a = 0 <;> by_cases hb : b = 0 <;> simp_all [followedSize]

/-- A floor quota below one puts the entire parent in the second daughter. Selecting
the empty first daughter ends the lineage or returns it to the full threshold size.
The product is the value presented to floor (float64 multiplication in the engine). -/
theorem zero_quota_at_threshold (n : ℕ) (hn : 0 < n) {product : ℝ} (small : product < 1) :
    let k := ⌊product⌋₊
    k = 0 ∧ followedSize false k (n - k) = 0 ∧
      followedSize true k (n - k) = n ∧ followedSize false (n - k) k = n := by
  simp [Nat.floor_eq_zero.mpr small, followedSize, hn]

/-- On a split there is no exchange heat. With log weights Φ, work W = Φp − Φk − Φs
and outgoing free energy S = −Φs, the followed jump is −W + S. -/
theorem log_weight_jump (parent kept sibling : ℝ) :
    kept - parent = -(parent - kept - sibling) + (-sibling) := by ring

end CellsProofs.Chemistry.LineageFission
