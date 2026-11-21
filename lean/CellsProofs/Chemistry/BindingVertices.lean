import CellsProofs.Chemistry.BindingFeasibility

/-! Exact directions for the joint feasibility margin of a finite binding ensemble. -/

namespace CellsProofs.Chemistry.BindingVertices

open BindingEquilibrium BindingFeasibility
open scoped BigOperators

noncomputable section

variable {B : Type*} [Fintype B] {F : B → Type*} [∀ b, Fintype (F b)]

/-- Parameter on the two-ligand simplex. The coordinates follow the engine's ligand order. -/
def weights (t : ℝ) : Fin 2 → ℝ := ![t, 1 - t]

private def line (p : Fin 2 → ℤ) (t : ℝ) : ℝ := (p 0 : ℝ) * t + (p 1 : ℝ) * (1 - t)

/-- Weight of the first ligand where two distinct projected lines meet. Parallel lines
give zero by field division, which is already an endpoint. -/
def crossing (p q : Fin 2 → ℤ) : ℚ :=
  let dx : ℚ := p 0 - q 0
  let dy : ℚ := p 1 - q 1
  dy / (dy - dx)

/-- The two simplex endpoints and all in-range same-binder form crossings, in exact rationals. -/
def twoVertices (n : (b : B) → F b → Fin 2 → ℤ) : Finset ℚ :=
  insert 0 (insert 1 ((Finset.univ.biUnion fun b => Finset.univ.biUnion fun i =>
    Finset.univ.image fun k => crossing (n b i) (n b k)).filter fun r => 0 ≤ r ∧ r ≤ 1))

private theorem zero_mem (n : (b : B) → F b → Fin 2 → ℤ) : 0 ∈ twoVertices n := by
  simp [twoVertices]

private theorem one_mem (n : (b : B) → F b → Fin 2 → ℤ) : 1 ∈ twoVertices n := by
  simp [twoVertices]

private theorem vertex_range (n : (b : B) → F b → Fin 2 → ℤ) {q : ℚ} (hq : q ∈ twoVertices n) :
    (q : ℝ) ∈ Set.Icc (0 : ℝ) 1 := by
  simp only [twoVertices, Finset.mem_insert, Finset.mem_filter] at hq
  rcases hq with rfl | rfl | ⟨_, h₀, h₁⟩
  · norm_num
  · norm_num
  · exact ⟨by exact_mod_cast h₀, by exact_mod_cast h₁⟩

private theorem crossing_mem (n : (b : B) → F b → Fin 2 → ℤ) (b : B) (i k : F b)
    (h : (crossing (n b i) (n b k) : ℝ) ∈ Set.Icc (0 : ℝ) 1) :
    crossing (n b i) (n b k) ∈ twoVertices n := by
  apply Finset.mem_insert_of_mem
  apply Finset.mem_insert_of_mem
  apply Finset.mem_filter.mpr
  refine ⟨Finset.mem_biUnion.mpr ⟨b, Finset.mem_univ _, Finset.mem_biUnion.mpr
    ⟨i, Finset.mem_univ _, Finset.mem_image.mpr ⟨k, Finset.mem_univ _, rfl⟩⟩⟩, ?_⟩
  exact ⟨by exact_mod_cast h.1, by exact_mod_cast h.2⟩

/-- Consecutive listed vertices bracketing an unlisted direction. -/
private theorem bracket (V : Finset ℚ) (h₀ : 0 ∈ V) (h₁ : 1 ∈ V)
    {t : ℝ} (ht : t ∈ Set.Icc (0 : ℝ) 1) (unlisted : ∀ q ∈ V, (q : ℝ) ≠ t) :
    ∃ l ∈ V, ∃ h ∈ V, (l : ℝ) < t ∧ t < (h : ℝ) ∧ ∀ q ∈ V, q ≤ l ∨ h ≤ q := by
  classical
  let left := V.filter fun q : ℚ => (q : ℝ) ≤ t
  let right := V.filter fun q : ℚ => t ≤ (q : ℝ)
  have hl : left.Nonempty := ⟨0, Finset.mem_filter.mpr ⟨h₀, by simpa using ht.1⟩⟩
  have hr : right.Nonempty := ⟨1, Finset.mem_filter.mpr ⟨h₁, by simpa using ht.2⟩⟩
  have ml := Finset.mem_filter.mp (left.max'_mem hl)
  have mr := Finset.mem_filter.mp (right.min'_mem hr)
  refine ⟨_, ml.1, _, mr.1, lt_of_le_of_ne ml.2 (unlisted _ ml.1),
    lt_of_le_of_ne mr.2 (unlisted _ mr.1).symm, fun q hq => ?_⟩
  rcases le_total (q : ℝ) t with h | h
  · exact Or.inl (left.le_max' _ (Finset.mem_filter.mpr ⟨hq, h⟩))
  · exact Or.inr (right.min'_le _ (Finset.mem_filter.mpr ⟨hq, h⟩))

/-- An affine difference cannot reverse sign between consecutive crossings. A tie at
the interior point is allowed, including identical profiles. -/
private theorem order_at_ends (p q : Fin 2 → ℤ) {l t h : ℝ} (hlt : l < t) (hth : t < h)
    (outside : (crossing p q : ℝ) ≤ l ∨ h ≤ (crossing p q : ℝ))
    (middle : line p t ≤ line q t) : line p l ≤ line q l ∧ line p h ≤ line q h := by
  let a := (p 0 : ℝ) - q 0 - ((p 1 : ℝ) - q 1)
  let b := (p 1 : ℝ) - q 1
  let r : ℝ := crossing p q
  have difference (x : ℝ) : line p x - line q x = b + a * x := by dsimp [line, a, b]; ring
  by_cases ha : a = 0
  · simp only [ha, zero_mul, add_zero] at difference
    constructor <;> linarith [difference l, difference t, difference h]
  have root : b + a * r = 0 := by
    have nonzero : b - ((p 0 : ℝ) - q 0) ≠ 0 := by
      intro hz
      apply ha
      dsimp [b] at hz
      dsimp [a]
      linarith
    dsimp only [r, crossing]
    push_cast
    change b + a * (b / (b - ((p 0 : ℝ) - q 0))) = 0
    field_simp [nonzero]
    dsimp [a, b]
    ring
  have factor (x : ℝ) : line p x - line q x = a * (x - r) := by
    rw [difference, mul_sub]
    linarith
  have atT := (factor t).symm.trans_le (sub_nonpos.mpr middle)
  rcases outside with before | after
  · have left : r ≤ l := before
    have slope : a ≤ 0 := nonpos_of_mul_nonpos_left atT (sub_pos.mpr (left.trans_lt hlt))
    exact ⟨sub_nonpos.mp ((factor l).trans_le (mul_nonpos_of_nonpos_of_nonneg slope (sub_nonneg.mpr left))),
      sub_nonpos.mp ((factor h).trans_le (mul_nonpos_of_nonpos_of_nonneg slope
        (sub_nonneg.mpr ((left.trans hlt.le).trans hth.le))))⟩
  · have right : h ≤ r := after
    have slope : 0 ≤ a := le_of_not_gt fun hn =>
      (not_lt_of_ge atT) (mul_pos_of_neg_of_neg hn (sub_neg.mpr (hth.trans_le right)))
    exact ⟨sub_nonpos.mp ((factor l).trans_le (mul_nonpos_of_nonneg_of_nonpos slope
        (sub_nonpos.mpr ((hlt.le.trans hth.le).trans right)))),
      sub_nonpos.mp ((factor h).trans_le (mul_nonpos_of_nonneg_of_nonpos slope (sub_nonpos.mpr right)))⟩


private theorem floor_at_min {I L : Type*} [Fintype I] [Nonempty I] [Fintype L]
    (n : I → L → ℤ) (d : L → ℝ) (i : I)
    (lowest : ∀ k, (∑ j, (n i j : ℝ) * d j) ≤ ∑ j, (n k j : ℝ) * d j) :
    formFloor n d = ∑ j, (n i j : ℝ) * d j := by
  change Finset.univ.inf' Finset.univ_nonempty (fun k => ∑ j, (n k j : ℝ) * d j) = _
  exact le_antisymm (Finset.inf'_le _ (Finset.mem_univ i))
    (Finset.le_inf' _ _ (fun k _ => lowest k))

variable [∀ b, Nonempty (F b)]

private theorem minimizer {I : Type*} [Fintype I] [Nonempty I] (n : I → Fin 2 → ℤ) (t : ℝ) :
    ∃ i, ∀ k, line (n i) t ≤ line (n k) t := by
  obtain ⟨i, _, hi⟩ := Finset.univ.exists_min_image (fun k => line (n k) t) Finset.univ_nonempty
  exact ⟨i, fun k => hi k (Finset.mem_univ k)⟩

private theorem margin_at_min (T : B → ℝ) (n : (b : B) → F b → Fin 2 → ℤ)
    (target : Fin 2 → ℝ) (t : ℝ) (s : (b : B) → F b)
    (lowest : ∀ b k, line (n b (s b)) t ≤ line (n b k) t) :
    margin T n target (weights t) =
      (target 0 - ∑ b, T b * (n b (s b) 0 : ℝ)) * t +
      (target 1 - ∑ b, T b * (n b (s b) 1 : ℝ)) * (1 - t) := by
  have floor (b : B) : formFloor (n b) (weights t) = line (n b (s b)) t := by
    have low (k : F b) : (∑ j, (n b (s b) j : ℝ) * weights t j) ≤ ∑ j, (n b k j : ℝ) * weights t j := by
      simpa [Fin.sum_univ_two, weights, line] using lowest b k
    simpa [Fin.sum_univ_two, weights, line] using floor_at_min (n b) (weights t) (s b) low
  simp only [margin, floor]
  simp [Fin.sum_univ_two, weights, line, mul_add, sub_mul,
    Finset.sum_add_distrib, Finset.sum_mul, mul_assoc]
  ring

/-- Every two-ligand weighting has margin at least as large as that at a listed rational vertex. -/
theorem two_ligand_vertex_le (T : B → ℝ) (n : (b : B) → F b → Fin 2 → ℤ) (target : Fin 2 → ℝ)
    {t : ℝ} (ht : t ∈ Set.Icc (0 : ℝ) 1) :
    ∃ q ∈ twoVertices n, margin T n target (weights q) ≤ margin T n target (weights t) := by
  classical
  by_cases found : ∃ q ∈ twoVertices n, (q : ℝ) = t
  · obtain ⟨q, hq, rfl⟩ := found
    exact ⟨q, hq, le_rfl⟩
  push_neg at found
  obtain ⟨l, hl, h, hh, hlt, hth, adjacent⟩ := bracket _ (zero_mem n) (one_mem n) ht found
  choose s lowest using fun b => minimizer (n b) t
  have ends (b : B) (k : F b) :
      line (n b (s b)) l ≤ line (n b k) l ∧ line (n b (s b)) h ≤ line (n b k) h := by
    apply order_at_ends _ _ hlt hth _ (lowest b k)
    let r := crossing (n b (s b)) (n b k)
    change (r : ℝ) ≤ (l : ℝ) ∨ (h : ℝ) ≤ (r : ℝ)
    by_cases inside : (r : ℝ) ∈ Set.Icc (0 : ℝ) 1
    · exact_mod_cast adjacent r (crossing_mem n b (s b) k inside)
    · rcases le_or_gt (r : ℝ) l with left | left
      · exact Or.inl left
      · exact Or.inr (le_of_not_gt fun right => inside
          ⟨(vertex_range n hl).1.trans left.le, right.le.trans (vertex_range n hh).2⟩)
  let A := target 0 - ∑ b, T b * (n b (s b) 0 : ℝ)
  let D := target 1 - ∑ b, T b * (n b (s b) 1 : ℝ)
  rw [margin_at_min T n target t s lowest]
  rcases le_total D A with up | down
  · refine ⟨l, hl, ?_⟩
    rw [margin_at_min T n target l s (fun b k => (ends b k).1)]
    change A * l + D * (1 - l) ≤ A * t + D * (1 - t)
    linarith only [mul_nonneg (sub_nonneg.mpr up) (sub_nonneg.mpr hlt.le)]
  · refine ⟨h, hh, ?_⟩
    rw [margin_at_min T n target h s (fun b k => (ends b k).2)]
    change A * h + D * (1 - h) ≤ A * t + D * (1 - t)
    linarith only [mul_nonneg (sub_nonneg.mpr down) (sub_nonneg.mpr hth.le)]

/-- One of the rational vertices attains the minimum over the entire real simplex. -/
theorem two_ligand_minimum_at_vertex (T : B → ℝ) (n : (b : B) → F b → Fin 2 → ℤ)
    (target : Fin 2 → ℝ) : ∃ q ∈ twoVertices n, ∀ d ∈ stdSimplex ℝ (Fin 2),
      margin T n target (weights q) ≤ margin T n target d := by
  obtain ⟨q, hq, best⟩ := (twoVertices n).exists_min_image
    (fun r => margin T n target (weights r)) ⟨0, zero_mem n⟩
  refine ⟨q, hq, fun d hd => ?_⟩
  let e := stdSimplexEquivIcc ℝ
  let t := e ⟨d, hd⟩
  obtain ⟨r, hr, le⟩ := two_ligand_vertex_le T n target t.property
  have back : weights (t : ℝ) = d := congrArg Subtype.val (e.symm_apply_apply ⟨d, hd⟩)
  rw [← back]
  exact (best r hr).trans le

/-- The engine checks the single weight 1 for a one-ligand closure. -/
theorem one_ligand_equilibrium_iff (T : B → ℝ) (hT : ∀ b, 0 ≤ T b)
    (a : (b : B) → F b → ℝ) (n : (b : B) → F b → Fin 1 → ℤ) (target : Fin 1 → ℝ) :
    (∃! u, total T a n u = target) ↔ 0 < margin T n target (fun _ => 1) := by
  rw [existsUnique_equilibrium_iff T hT, stdSimplex_unique]
  simp

/-- The finite rational test is necessary and sufficient for a positive equilibrium of
any two-ligand ensemble, including signed counts and zero binder totals. -/
theorem two_ligand_equilibrium_iff (T : B → ℝ) (hT : ∀ b, 0 ≤ T b)
    (a : (b : B) → F b → ℝ) (n : (b : B) → F b → Fin 2 → ℤ) (target : Fin 2 → ℝ) :
    (∃! u, total T a n u = target) ↔ ∀ q ∈ twoVertices n, 0 < margin T n target (weights q) := by
  rw [existsUnique_equilibrium_iff T hT]
  constructor
  · intro positive q hq
    exact positive _ (((stdSimplexEquivIcc ℝ).symm ⟨q, vertex_range n hq⟩).property)
  · intro finite d hd
    obtain ⟨q, hq, best⟩ := two_ligand_minimum_at_vertex T n target
    exact (finite q hq).trans_le (best d hd)


variable {L : Type*} [Fintype L]

/-- If one form of each binder attains that binder's lowest count in every ligand row,
its projected inventory is the floor in every nonnegative direction. -/
theorem margin_of_common_lowest_form (T : B → ℝ) (n : (b : B) → F b → L → ℤ)
    (target : L → ℝ) (s : (b : B) → F b) (lowest : ∀ b i j, n b (s b) j ≤ n b i j)
    (d : L → ℝ) (hd : ∀ j, 0 ≤ d j) :
    margin T n target d = ∑ j, (target j - ∑ b, T b * (n b (s b) j : ℝ)) * d j := by
  have floor (b : B) : formFloor (n b) d = ∑ j, (n b (s b) j : ℝ) * d j :=
    floor_at_min _ _ _ (fun i => Finset.sum_le_sum (fun j _ =>
      mul_le_mul_of_nonneg_right (by exact_mod_cast lowest b i j) (hd j)))
  simp only [margin, floor, sub_mul, Finset.sum_sub_distrib, Finset.sum_mul,
    Finset.mul_sum, mul_assoc]
  rw [Finset.sum_comm (f := fun b j => T b * ((n b (s b) j : ℝ) * d j))]

/-- In any positive number of dimensions with common lowest forms, a simplex corner attains
the minimum for every choice of totals. The base form of each S6 binder satisfies the premise. -/
theorem common_floor_minimum_at_corner [Nonempty L] [DecidableEq L] (T : B → ℝ)
    (n : (b : B) → F b → L → ℤ) (target : L → ℝ) (s : (b : B) → F b)
    (lowest : ∀ b i j, n b (s b) j ≤ n b i j) :
    ∃ k : L, ∀ d ∈ stdSimplex ℝ L, margin T n target (Pi.single k 1) ≤ margin T n target d := by
  let free := fun j => target j - ∑ b, T b * (n b (s b) j : ℝ)
  obtain ⟨k, _, hk⟩ := Finset.univ.exists_min_image free Finset.univ_nonempty
  refine ⟨k, fun d hd => ?_⟩
  rw [margin_of_common_lowest_form T n target s lowest _ (single_mem_stdSimplex ℝ k).1,
    margin_of_common_lowest_form T n target s lowest d hd.1]
  change (∑ j, free j * (Pi.single k 1 : L → ℝ) j) ≤ ∑ j, free j * d j
  have bound := Finset.sum_le_sum (s := Finset.univ) (fun j _ =>
    mul_le_mul_of_nonneg_right (hk j (Finset.mem_univ _)) (hd.1 j))
  rw [← Finset.mul_sum, hd.2, mul_one] at bound
  simpa [Pi.single_apply] using bound

/-- Under the common-minimizer hypothesis in any number of held rows, each row's
strict inventory bound is sufficient as well as necessary. -/
theorem common_floor_equilibrium_iff (T : B → ℝ) (hT : ∀ b, 0 ≤ T b)
    (a : (b : B) → F b → ℝ) (n : (b : B) → F b → L → ℤ) (target : L → ℝ)
    (s : (b : B) → F b) (lowest : ∀ b i j, n b (s b) j ≤ n b i j) :
    (∃! u, total T a n u = target) ↔ ∀ j, (∑ b, T b * (n b (s b) j : ℝ)) < target j := by
  classical
  rw [existsUnique_equilibrium_iff T hT]
  constructor
  · intro all j
    have hj := single_mem_stdSimplex ℝ j
    have strict := all _ hj
    rw [margin_of_common_lowest_form T n target s lowest _ hj.1] at strict
    simpa [Pi.single_apply, sub_pos] using strict
  · intro coord d hd
    rw [margin_of_common_lowest_form T n target s lowest d hd.1]
    have mass : ∃ j, 0 < d j := by
      by_contra! no
      have zero := Finset.sum_nonpos (s := Finset.univ) (fun j _ => no j)
      linarith [hd.2]
    obtain ⟨j, hj⟩ := mass
    exact (mul_pos (sub_pos.mpr (coord j)) hj).trans_le (Finset.single_le_sum
      (fun k _ => mul_nonneg (sub_nonneg.mpr (coord k).le) (hd.1 k)) (Finset.mem_univ j))

end

end CellsProofs.Chemistry.BindingVertices
