import Mathlib.Algebra.Order.Ring.Abs
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Ring

/-! # The two-word GARD cache on a common binary grid

Amounts in one row are integers in units of its lowest set bit. A 53-bit word
may be shifted by a power of two. The exponent range and preservation of
subnormals are separate requirements when interpreting this model on a device.
-/

namespace CellsProofs.Chemistry.GardCache

/-- A binary word on the row's integer grid, ignoring the device's exponent limits. -/
def Word (x : ℤ) : Prop := ∃ (m : ℤ) (e : ℕ), |m| ≤ 2^53 ∧ x = m * 2^e

private theorem small_word {x : ℤ} (h : |x| ≤ 2^53) : Word x := ⟨x, 0, h, by simp⟩

private theorem neg_word {x : ℤ} (h : Word x) : Word (-x) := by
  obtain ⟨m, e, hm, rfl⟩ := h
  exact ⟨-m, e, by simpa using hm, by ring⟩

/-- The interface of round-to-nearest and Knuth's error-free TwoSum. Its implementation
requires finite operations and preservation of the low word (Ogita et al., Theorem 3.4). -/
structure Arithmetic where
  round : ℤ → ℤ
  represented : ∀ x, Word (round x)
  nearest : ∀ x y, Word y → |x - round x| ≤ |x - y|
  twoSum : ℤ → ℤ → ℤ × ℤ
  twoSum_spec : ∀ a b, Word a → Word b →
    twoSum a b = (round (a + b), a + b - round (a + b))

/-- A nearest word exists on this grid: minimise the integer distance to the input.
The following cache results allow either tie rule. -/
theorem grid_model_exists : Nonempty Arithmetic := by
  classical
  have closest (x : ℤ) : ∃ y, Word y ∧ ∀ z, Word z → |x - y| ≤ |x - z| := by
    let P := fun d : ℕ => ∃ y, Word y ∧ (x - y).natAbs = d
    have ex : ∃ d, P d := ⟨_, 0, small_word (by norm_num), rfl⟩
    obtain ⟨y, hy, hd⟩ := Nat.find_spec ex
    refine ⟨y, hy, fun z hz => ?_⟩
    have le : (x - y).natAbs ≤ (x - z).natAbs := hd ▸ Nat.find_min' ex ⟨z, hz, rfl⟩
    simpa only [Int.natCast_natAbs] using (Nat.cast_le (α := ℤ)).mpr le
  choose rn word near using closest
  exact ⟨⟨rn, word, near, fun a b => (rn (a + b), a + b - rn (a + b)), fun _ _ _ _ => rfl⟩⟩

theorem round_word (op : Arithmetic) {x : ℤ} (hx : Word x) : op.round x = x := by
  have h := op.nearest x x hx
  rw [sub_self, abs_zero, abs_nonpos_iff, sub_eq_zero] at h
  exact h.symm

/-- Even if adding to the rounded high word puts an intermediate just beyond the
row budget, a representable grid point remains within half the largest spacing. -/
theorem high_error (op : Arithmetic) {x : ℤ}
    (low : -(2^52) ≤ x) (high : x ≤ 2^106 + 2^52) : |x - op.round x| ≤ 2^52 := by
  by_cases h : x ≤ 0
  · refine (op.nearest x 0 (small_word (by norm_num))).trans ?_
    simpa [abs_of_nonpos h] using (neg_le_of_neg_le low)
  by_cases h' : 2^106 ≤ x
  · have w : Word (2^106) := ⟨2^53, 53, by norm_num, by norm_num⟩
    refine (op.nearest x (2^106) w).trans ?_
    rw [abs_of_nonneg (sub_nonneg.mpr h')]
    omega
  let m := (x + 2^52) / 2^53
  have hm : |m| ≤ 2^53 := by
    apply abs_le.mpr
    dsimp [m]
    norm_num at h h' ⊢
    omega
  refine (op.nearest x (m * 2^53) ⟨m, 53, hm, rfl⟩).trans ?_
  apply abs_le.mpr
  dsimp [m]
  norm_num
  omega

/-- The normalised cache is unique for a fixed rounding rule. -/
def cache (op : Arithmetic) (x : ℤ) : ℤ × ℤ := (op.round x, x - op.round x)

/-- First TwoSum and the subsequent addition of its error to the old low word. -/
def parts (op : Arithmetic) (c : ℤ × ℤ) (b : ℤ) : ℤ × ℤ :=
  let s := op.twoSum c.1 b
  (s.1, op.round (s.2 + c.2))

/-- Founder folds and single-molecule updates both call this renormalisation. -/
def add (op : Arithmetic) (c : ℤ × ℤ) (b : ℤ) : ℤ × ℤ :=
  let p := parts op c b
  op.twoSum p.1 p.2

/-- The leave expression makes only the high word of the renormalised difference. -/
def recovered (op : Arithmetic) (c : ℤ × ℤ) (diagonal : ℤ) : ℤ :=
  let p := parts op c (-diagonal)
  op.round (p.1 + p.2)

def InBudget (x : ℤ) : Prop := 0 ≤ x ∧ x < 2^106

/-- The parser bounds the largest coefficient times the molecule capacity in row ticks.
Every nonnegative composition up to capacity then has an in-budget weighted sum. -/
theorem row_in_budget {ι : Type*} (s : Finset ι) (beta count : ι → ℤ)
    {largest capacity : ℤ} (hmax : 0 ≤ largest) (hc : ∑ i ∈ s, count i ≤ capacity)
    (hn : ∀ i ∈ s, 0 ≤ count i) (hb : ∀ i ∈ s, 0 ≤ beta i ∧ beta i ≤ largest)
    (guard : largest * capacity < 2^106) : InBudget (∑ i ∈ s, beta i * count i) := by
  constructor
  · exact Finset.sum_nonneg fun i hi => mul_nonneg (hb i hi).1 (hn i hi)
  · calc
      (∑ i ∈ s, beta i * count i) ≤ ∑ i ∈ s, largest * count i :=
        Finset.sum_le_sum fun i hi => mul_le_mul_of_nonneg_right (hb i hi).2 (hn i hi)
      _ = largest * ∑ i ∈ s, count i := (Finset.mul_sum ..).symm
      _ ≤ largest * capacity := mul_le_mul_of_nonneg_left hc hmax
      _ < _ := guard

private theorem parts_sum (op : Arithmetic) {x b : ℤ} (hx : InBudget x)
    (hb : Word b) (hnew : InBudget (x + b)) :
    let p := parts op (cache op x) b
    p.1 + p.2 = x + b ∧ Word p.1 ∧ Word p.2 := by
  obtain ⟨hx0, hx1⟩ := hx
  obtain ⟨hn0, hn1⟩ := hnew
  have old := abs_le.mp (high_error op (x := x) (by omega) (by omega))
  have err := abs_le.mp (high_error op (x := op.round x + b) (by omega) (by omega))
  have fit : |(op.round x + b - op.round (op.round x + b)) + (x - op.round x)| ≤ 2^53 := by
    apply abs_le.mpr
    norm_num at old err ⊢
    omega
  simp only [parts, cache, op.twoSum_spec _ _ (op.represented _) hb, round_word op (small_word fit)]
  exact ⟨by ring, op.represented _, small_word fit⟩

/-- Every in-budget signed update gives the canonical pair for the new exact sum. -/
theorem add_exact (op : Arithmetic) {x b : ℤ} (hx : InBudget x) (hb : Word b)
    (hnew : InBudget (x + b)) : add op (cache op x) b = cache op (x + b) := by
  obtain ⟨hsum, wh, wl⟩ := parts_sum op hx hb hnew
  rw [add, op.twoSum_spec _ _ wh wl, hsum, cache]

/-- Tracks each partial sum along an event history or a founder/daughter fold. -/
inductive Admissible : ℤ → List ℤ → Prop where
  | nil (x) : InBudget x → Admissible x []
  | cons {x b bs} : InBudget x → Word b → Admissible (x + b) bs → Admissible x (b :: bs)

private theorem Admissible.start {x bs} (h : Admissible x bs) : InBudget x := by
  cases h <;> assumption

theorem fold_exact (op : Arithmetic) {x bs} (h : Admissible x bs) :
    bs.foldl (add op) (cache op x) = cache op (x + bs.sum) := by
  induction h with
  | nil => simp
  | cons hx hb tail ih =>
    simp only [List.foldl_cons, List.sum_cons]
    rw [add_exact op hx hb tail.start, ih, add_assoc]

/-- Adjacent join and reverse leave use the same rounded numerator, before identical
division by the parent count and addition of one. -/
theorem reverse_high (op : Arithmetic) {x b : ℤ} (hx : InBudget x) (hb : Word b)
    (hnext : InBudget (x + b)) :
    recovered op (add op (cache op x) b) b = (cache op x).1 := by
  rw [add_exact op hx hb hnext]
  have back : InBudget (x + b + -b) := by simpa using hx
  obtain ⟨hsum, _, _⟩ := parts_sum op hnext (neg_word hb) back
  dsimp only [recovered, cache]
  simpa using congrArg op.round hsum

/-- Each piece of the founder coefficient (33 high bits, at most 20 low bits) times
a count up to 2²⁰ fits in 53 significant bits, including its original binary shift. -/
theorem split_product_word {m n : ℤ} (e : ℕ) (hm : 0 ≤ m) (hm' : m < 2^33)
    (hn : 0 ≤ n) (hn' : n ≤ 2^20) : Word ((m * 2^e) * n) := by
  refine ⟨m * n, e, ?_, by ring⟩
  rw [abs_of_nonneg (mul_nonneg hm hn)]
  calc
    m * n ≤ 2^33 * 2^20 := mul_le_mul hm'.le hn' hn (by norm_num)
    _ = 2^53 := by norm_num

theorem stress_reverse (op : Arithmetic) :
    recovered op (add op (cache op 1) (2^54)) (2^54) = 1 := by
  have w : Word (2^54) := ⟨1, 54, by norm_num, by simp⟩
  rw [reverse_high op (by norm_num [InBudget]) w (by norm_num [InBudget])]
  exact round_word op (small_word (by norm_num))

/-- A single tick must survive in the high word, even if the physical tick is tiny. -/
theorem one_tick (op : Arithmetic) : cache op 1 = (1, 0) := by
  simp [cache, round_word op (x := 1) (small_word (by norm_num))]

/-- A short significand alone does not bound the physical exponent. A row with only
2¹⁰²³ as a nonzero coefficient uses four bits at capacity eight, yet its two-molecule
sum exceeds the round-to-nearest binary64 overflow threshold. -/
theorem exponent_counterexample :
    (8 : ℤ) < 2^106 ∧ 2 * (2^1023 : ℤ) > (2^53 - 1) * 2^971 + 2^970 := by norm_num

end CellsProofs.Chemistry.GardCache
