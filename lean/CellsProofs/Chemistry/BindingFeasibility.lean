import CellsProofs.Chemistry.BindingEquilibrium
import Mathlib.Analysis.Calculus.LocalExtr.Basic
import Mathlib.Analysis.Convex.Topology
import Mathlib.Analysis.SpecialFunctions.Log.Deriv
import Mathlib.Topology.Order.Lattice

/-! Which inventories admit a positive equilibrium of a finite binding ensemble? -/

namespace CellsProofs.Chemistry.BindingFeasibility

open BindingEnsemble BindingResponse BindingEquilibrium
open scoped BigOperators

noncomputable section

variable {L B : Type*} [Fintype L] [Fintype B] {F : B → Type*}
  [∀ b, Fintype (F b)] [∀ b, Nonempty (F b)]

private def projected (v : L → ℤ) (d : L → ℝ) : ℝ := ∑ j, (v j : ℝ) * d j

/-- Smallest signed ligand inventory in direction `d` among the present forms of this binder. -/
def formFloor {I : Type*} [Fintype I] [Nonempty I] (n : I → L → ℤ) (d : L → ℝ) : ℝ :=
  Finset.univ.inf' Finset.univ_nonempty (fun i => projected (n i) d)

/-- Prescribed inventory left after subtracting the projected binder floors, in mM
for a normalized direction. The ligand index consists of the held coordinates. -/
def margin (T : B → ℝ) (n : (b : B) → F b → L → ℤ) (target d : L → ℝ) : ℝ :=
  ∑ j, target j * d j - ∑ b, T b * formFloor (n b) d

private theorem attains_floor {I : Type*} [Fintype I] [Nonempty I] (n : I → L → ℤ)
    (d : L → ℝ) : ∃ i, formFloor n d = projected (n i) d := by
  obtain ⟨i, _, hi⟩ := Finset.univ.exists_mem_eq_inf' Finset.univ_nonempty (fun i => projected (n i) d)
  exact ⟨i, hi⟩

private theorem floor_le {I : Type*} [Fintype I] [Nonempty I] (n : I → L → ℤ)
    (d : L → ℝ) (i : I) : formFloor n d ≤ projected (n i) d :=
  Finset.inf'_le _ (Finset.mem_univ i)

private theorem weighted_floor {I : Type*} [Fintype I] [Nonempty I] (a : I → ℝ)
    (n : I → L → ℤ) (d : L → ℝ) :
    formFloor n d ≤ ∑ j, mean a (fun i => (n i j : ℝ)) * d j := by
  have pos : 0 < ∑ i, Real.exp (a i) :=
    Finset.sum_pos (fun i _ => Real.exp_pos (a i)) Finset.univ_nonempty
  have norm : ∑ i, fraction a i = 1 := by simp [fraction, ← Finset.sum_div, pos.ne']
  calc
    formFloor n d = ∑ i, fraction a i * formFloor n d := by rw [← Finset.sum_mul, norm, one_mul]
    _ ≤ ∑ i, fraction a i * projected (n i) d := Finset.sum_le_sum (fun i _ =>
      mul_le_mul_of_nonneg_left (floor_le n d i) (div_nonneg (Real.exp_pos _).le pos.le))
    _ = _ := by
      simp only [projected, mean, Finset.mul_sum, Finset.sum_mul, mul_assoc]
      exact Finset.sum_comm

/-- Every positive equilibrium leaves at least the same positive amount in each normalized
nonnegative direction. This also covers the empty set of held rows. -/
theorem equilibrium_has_margin (T : B → ℝ) (hT : ∀ b, 0 ≤ T b)
    (a : (b : B) → F b → ℝ) (n : (b : B) → F b → L → ℤ) (u : L → ℝ) :
    ∃ ε : ℝ, 0 < ε ∧ ∀ d : L → ℝ, (∀ j, 0 ≤ d j) →
      ε * ∑ j, d j ≤ margin T n (total T a n u) d := by
  classical
  let ε := (insert (1 : ℝ) (Finset.univ.image (fun j => Real.exp (u j)))).min' (Finset.insert_nonempty ..)
  have hε : 0 < ε := by
    have hm := Finset.min'_mem _ (Finset.insert_nonempty (1 : ℝ) (Finset.univ.image (fun j => Real.exp (u j))))
    change 0 < ε
    change ε ∈ insert (1 : ℝ) _ at hm
    rcases Finset.mem_insert.mp hm with h | h
    · rw [h]; norm_num
    · obtain ⟨j, _, hj⟩ := Finset.mem_image.mp h
      exact hj ▸ Real.exp_pos _
  refine ⟨ε, hε, fun d hd => ?_⟩
  have free := Finset.sum_le_sum (s := Finset.univ) (fun j _ =>
    mul_le_mul_of_nonneg_right (show ε ≤ Real.exp (u j) from Finset.min'_le _ _
      (Finset.mem_insert_of_mem (Finset.mem_image_of_mem _ (Finset.mem_univ j)))) (hd j))
  have bound := Finset.sum_le_sum (s := Finset.univ) (fun b _ => mul_le_mul_of_nonneg_left
    (weighted_floor (fun i => logWeight (a b i) (n b i) u) (n b) d) (hT b))
  simp only [margin, total, add_mul, Finset.sum_add_distrib, Finset.sum_mul]
  rw [Finset.sum_comm (f := fun j b => T b * mean (fun i => logWeight (a b i) (n b i) u)
    (fun i => (n b i j : ℝ)) * d j)]
  simp_rw [mul_assoc, ← Finset.mul_sum]
  rw [Finset.mul_sum]
  linarith

/-- The convex dual whose coordinate derivative is the inventory residual. -/
private def potential (T : B → ℝ) (a : (b : B) → F b → ℝ) (n : (b : B) → F b → L → ℤ)
    (target u : L → ℝ) : ℝ :=
  (∑ j, (Real.exp (u j) - target j * u j)) +
    ∑ b, T b * Real.log (∑ i, Real.exp (logWeight (a b i) (n b i) u))

private theorem partition_pos {I : Type*} [Fintype I] [Nonempty I] (a : I → ℝ) :
    0 < ∑ i, Real.exp (a i) := Finset.sum_pos (fun i _ => Real.exp_pos (a i)) Finset.univ_nonempty

private theorem potential_continuous (T : B → ℝ) (a : (b : B) → F b → ℝ)
    (n : (b : B) → F b → L → ℤ) (target : L → ℝ) : Continuous (potential T a n target) := by
  unfold potential
  apply Continuous.add
  · fun_prop
  · apply continuous_finset_sum
    intro b _
    apply Continuous.mul continuous_const
    apply Continuous.log _ (fun u => (partition_pos (fun i => logWeight (a b i) (n b i) u)).ne')
    unfold logWeight
    fun_prop

private theorem potential_lower (T : B → ℝ) (hT : ∀ b, 0 ≤ T b) (a : (b : B) → F b → ℝ)
    (n : (b : B) → F b → L → ℤ) (target u : L → ℝ) (s : (b : B) → F b) :
    (∑ j, Real.exp (u j)) + (∑ b, T b * a b (s b)) -
      ∑ j, (target j - ∑ b, T b * (n b (s b) j : ℝ)) * u j ≤ potential T a n target u := by
  have weight (b : B) : logWeight (a b (s b)) (n b (s b)) u ≤
      Real.log (∑ i, Real.exp (logWeight (a b i) (n b i) u)) := by
    rw [← Real.exp_le_exp, Real.exp_log (partition_pos _)]
    exact Finset.single_le_sum (fun i _ => (Real.exp_pos (logWeight (a b i) (n b i) u)).le) (Finset.mem_univ (s b))
  have bound := Finset.sum_le_sum (s := Finset.univ) (fun b _ =>
    mul_le_mul_of_nonneg_left (weight b) (hT b))
  simp only [logWeight, mul_add, Finset.sum_add_distrib, Finset.mul_sum] at bound
  simp only [potential, logWeight, Finset.sum_sub_distrib, sub_mul, Finset.sum_mul, mul_assoc]
  rw [Finset.sum_comm (f := fun j b => T b * ((n b (s b) j : ℝ) * u j))]
  linarith

private theorem exp_linear_bound (k : ℝ) (hk : 0 < k) :
    ∃ c : ℝ, ∀ x : ℝ, k * max x 0 - c ≤ Real.exp x := by
  refine ⟨k * |Real.log k|, fun x => ?_⟩
  by_cases hx : 0 ≤ x
  · rw [max_eq_left hx]
    have t := mul_le_mul_of_nonneg_left (Real.add_one_le_exp (x - Real.log k)) hk.le
    rw [Real.exp_sub, Real.exp_log hk, mul_div_cancel₀ _ hk.ne'] at t
    have h := mul_le_mul_of_nonneg_left (le_abs_self (Real.log k)) hk.le
    linarith
  · rw [max_eq_right (le_of_not_ge hx), mul_zero]
    linarith [mul_nonneg hk.le (abs_nonneg (Real.log k)), Real.exp_pos x]


/-- The margin controls negative log concentrations. The exponential term controls the
positive ones. Together they bound every sublevel of the potential in a finite box. -/
private theorem potential_bound (T : B → ℝ) (hT : ∀ b, 0 ≤ T b) (a : (b : B) → F b → ℝ)
    (n : (b : B) → F b → L → ℤ) (target : L → ℝ) (ε : ℝ) (hε : 0 < ε)
    (room : ∀ d : L → ℝ, (∀ j, 0 ≤ d j) → ε * ∑ j, d j ≤ margin T n target d) :
    ∃ C : ℝ, ∀ u : L → ℝ, ε * ∑ j, |u j| ≤ potential T a n target u + C := by
  classical
  let w (s : (b : B) → F b) (j : L) := target j - ∑ b, T b * (n b (s b) j : ℝ)
  let bias (s : (b : B) → F b) := ∑ b, T b * a b (s b)
  obtain ⟨k, hk⟩ := (Set.finite_range (fun p : ((b : B) → F b) × L => w p.1 p.2)).bddAbove
  obtain ⟨k₀, hk₀⟩ := (Set.finite_range (fun s => -bias s)).bddAbove
  let K := max k 0
  obtain ⟨c, hc⟩ := exp_linear_bound (K + ε) (add_pos_of_nonneg_of_pos (le_max_right ..) hε)
  refine ⟨(∑ _ : L, c) + k₀, fun u => ?_⟩
  let d (j : L) := max (-u j) 0
  choose s hs using fun b => attains_floor (n b) d
  have selected : ε * ∑ j, d j ≤ ∑ j, w s j * d j := by
    have h := room d (fun _ => le_max_right ..)
    simp only [w, sub_mul, Finset.sum_sub_distrib, Finset.sum_mul, mul_assoc]
    rw [Finset.sum_comm (f := fun j b => T b * ((n b (s b) j : ℝ) * d j))]
    simpa only [margin, hs, projected, Finset.mul_sum] using h
  have one (j : L) : ε * |u j| + w s j * u j + w s j * d j ≤ Real.exp (u j) + c + ε * d j := by
    have cap : w s j ≤ K := (hk (Set.mem_range_self (s, j))).trans (le_max_left ..)
    have e := hc (u j)
    by_cases hu : 0 ≤ u j
    · simp only [d, max_eq_right (neg_nonpos.mpr hu), abs_of_nonneg hu, max_eq_left hu,
        mul_zero, add_zero] at e ⊢
      linarith [mul_le_mul_of_nonneg_right cap hu]
    · have hu' := le_of_not_ge hu
      simp only [d, max_eq_left (neg_nonneg.mpr hu'), abs_of_nonpos hu', max_eq_right hu',
        mul_neg, mul_zero] at e ⊢
      linarith
  have combined := Finset.sum_le_sum (s := Finset.univ) (fun j _ => one j)
  simp only [Finset.sum_add_distrib, ← Finset.mul_sum] at combined
  have low := potential_lower T hT a n target u s
  change (∑ j, Real.exp (u j)) + bias s - ∑ j, w s j * u j ≤ _ at low
  have biasBound : -bias s ≤ k₀ := hk₀ (Set.mem_range_self s)
  linarith

private theorem bounded_minimum (f : (L → ℝ) → ℝ) (hf : Continuous f) (ε C : ℝ) (hε : 0 < ε)
    (bound : ∀ u, ε * ∑ j, |u j| ≤ f u + C) : ∃ u, ∀ y, f u ≤ f y := by
  let R := (|f 0 + C| + 1) / ε
  have hR : 0 ≤ R := div_nonneg (by positivity) hε.le
  let box := Set.Icc (fun _ : L => -R) (fun _ => R)
  have zero : (0 : L → ℝ) ∈ box := ⟨fun _ => neg_nonpos.mpr hR, fun _ => hR⟩
  obtain ⟨w, _, hw⟩ := isCompact_Icc.exists_isMinOn ⟨0, zero⟩ hf.continuousOn
  refine ⟨w, fun y => ?_⟩
  by_cases hy : y ∈ box
  · exact hw hy
  · apply (hw zero).trans
    by_contra! h
    apply hy
    have inside (j : L) : |y j| ≤ R := by
      apply (le_div_iff₀ hε).mpr
      have one : |y j| ≤ ∑ k, |y k| :=
        Finset.single_le_sum (fun k _ => abs_nonneg (y k)) (Finset.mem_univ j)
      linarith [bound y, mul_le_mul_of_nonneg_left one hε.le, le_abs_self (f 0 + C)]
    exact ⟨fun j => (abs_le.mp (inside j)).1, fun j => (abs_le.mp (inside j)).2⟩

private theorem log_partition_deriv {I : Type*} [Fintype I] [Nonempty I] (a q : I → ℝ) :
    HasDerivAt (fun t : ℝ => Real.log (∑ i, Real.exp (a i + t * q i))) (mean a q) 0 := by
  have weight (i : I) : HasDerivAt (fun t : ℝ => Real.exp (a i + t * q i))
      (Real.exp (a i) * q i) 0 := by
    simpa using (((hasDerivAt_id (0 : ℝ)).mul_const (q i)).const_add (a i)).exp
  have den := HasDerivAt.sum (u := Finset.univ) (fun i _ => weight i)
  simpa [mean, fraction, div_mul_eq_mul_div, Finset.sum_div] using
    den.log (by simpa using (partition_pos a).ne')

private theorem potential_deriv [DecidableEq L] (T : B → ℝ) (a : (b : B) → F b → ℝ)
    (n : (b : B) → F b → L → ℤ) (target u : L → ℝ) (k : L) :
    HasDerivAt (fun t : ℝ => potential T a n target (fun j => u j + if j = k then t else 0))
      (total T a n u k - target k) 0 := by
  have free (j : L) : HasDerivAt (fun t : ℝ => Real.exp (u j + if j = k then t else 0) -
      target j * (u j + if j = k then t else 0)) (if j = k then Real.exp (u j) - target j else 0) 0 := by
    by_cases hj : j = k
    · have move := (hasDerivAt_id (0 : ℝ)).const_add (u j)
      simpa [hj] using move.exp.sub (move.const_mul (target j))
    · simpa [hj] using hasDerivAt_const (0 : ℝ) (Real.exp (u j) - target j * u j)
  have one := HasDerivAt.sum (u := Finset.univ) (fun j _ => free j)
  have binders := HasDerivAt.sum (u := Finset.univ) (fun b _ =>
    (log_partition_deriv (fun i => logWeight (a b i) (n b i) u) (fun i => (n b i k : ℝ))).const_mul (T b))
  simpa [potential, total, logWeight_perturb, sub_add_eq_add_sub] using one.add binders

/-- A uniform positive joint margin suffices for an equilibrium with the specified held
totals, at any finite standard log weights. Zero binder totals and signed counts are allowed. -/
theorem equilibrium_of_margin (T : B → ℝ) (hT : ∀ b, 0 ≤ T b) (a : (b : B) → F b → ℝ)
    (n : (b : B) → F b → L → ℤ) (target : L → ℝ) (ε : ℝ) (hε : 0 < ε)
    (room : ∀ d : L → ℝ, (∀ j, 0 ≤ d j) → ε * ∑ j, d j ≤ margin T n target d) :
    ∃ u, total T a n u = target := by
  classical
  obtain ⟨C, bound⟩ := potential_bound T hT a n target ε hε room
  obtain ⟨u, hu⟩ := bounded_minimum _ (potential_continuous T a n target) ε C hε bound
  refine ⟨u, funext fun j => sub_eq_zero.mp ?_⟩
  apply IsLocalMin.hasDerivAt_eq_zero _ (potential_deriv T a n target u j)
  apply Filter.Eventually.of_forall
  intro t
  simpa using hu (fun k => u k + if k = j then t else 0)


private theorem floor_scale {I : Type*} [Fintype I] [Nonempty I] (n : I → L → ℤ)
    (d : L → ℝ) (r : ℝ) (hr : 0 ≤ r) : formFloor n (fun j => r * d j) = r * formFloor n d := by
  have scale (i : I) : projected (n i) (fun j => r * d j) = r * projected (n i) d := by
    simp [projected, Finset.mul_sum, mul_left_comm]
  obtain ⟨i, hi⟩ := attains_floor n d
  obtain ⟨k, hk⟩ := attains_floor n (fun j => r * d j)
  apply le_antisymm
  · rw [hi, ← scale]
    apply floor_le
  · rw [hk, scale]
    exact mul_le_mul_of_nonneg_left (floor_le n d k) hr

private theorem margin_scale (T : B → ℝ) (n : (b : B) → F b → L → ℤ)
    (target d : L → ℝ) (r : ℝ) (hr : 0 ≤ r) :
    margin T n target (fun j => r * d j) = r * margin T n target d := by
  simp [margin, floor_scale _ _ _ hr, mul_sub, Finset.mul_sum, mul_left_comm]

private theorem margin_continuous (T : B → ℝ) (n : (b : B) → F b → L → ℤ)
    (target : L → ℝ) : Continuous (margin T n target) := by
  unfold margin
  apply Continuous.sub
  · fun_prop
  · apply continuous_finset_sum
    intro b _
    apply Continuous.mul continuous_const
    unfold formFloor
    apply Continuous.finset_inf'_apply
    intro i _
    unfold projected
    fun_prop

/-- Exactly one finite log-concentration vector solves the held equations if and only if every
normalized nonnegative direction leaves strictly positive room. Unheld free log concentrations
can be included in the standard log weights. With no held rows the criterion is vacuous. -/
theorem existsUnique_equilibrium_iff (T : B → ℝ) (hT : ∀ b, 0 ≤ T b) (a : (b : B) → F b → ℝ)
    (n : (b : B) → F b → L → ℤ) (target : L → ℝ) :
    (∃! u, total T a n u = target) ↔ ∀ d ∈ stdSimplex ℝ L, 0 < margin T n target d := by
  classical
  constructor
  · rintro ⟨u, rfl, _⟩ d hd
    obtain ⟨ε, hε, room⟩ := equilibrium_has_margin T hT a n u
    have h := room d hd.1
    rw [hd.2, mul_one] at h
    exact hε.trans_le h
  · intro strict
    rcases isEmpty_or_nonempty L with empty | nonempty
    · exact ⟨0, Subsingleton.elim .., fun _ _ => Subsingleton.elim ..⟩
    obtain ⟨d₀, h₀, least⟩ := (isCompact_stdSimplex L).exists_isMinOn
      ⟨_, single_mem_stdSimplex ℝ (Classical.choice nonempty)⟩ (margin_continuous T n target).continuousOn
    let ε := margin T n target d₀
    have hε : 0 < ε := strict d₀ h₀
    have room (d : L → ℝ) (hd : ∀ j, 0 ≤ d j) : ε * ∑ j, d j ≤ margin T n target d := by
      let r := ∑ j, d j
      have hr : 0 ≤ r := Finset.sum_nonneg (fun j _ => hd j)
      rcases hr.eq_or_lt with hz | hp
      · have z (j) : d j = 0 := (Finset.sum_eq_zero_iff_of_nonneg (fun k _ => hd k)).mp hz.symm j (Finset.mem_univ j)
        have h := margin_scale T n target d 0 le_rfl
        have zd : d = fun _ => 0 := funext z
        rw [zd]
        simpa [zd] using h.ge
      · let e := fun j => d j / r
        have he : e ∈ stdSimplex ℝ L := ⟨fun j => div_nonneg (hd j) hp.le, by
          simpa only [e, ← Finset.sum_div] using div_self hp.ne'⟩
        have scaled : (fun j => r * e j) = d := funext (fun j => mul_div_cancel₀ _ hp.ne')
        have h := margin_scale T n target e r hp.le
        rw [scaled] at h
        change ε * r ≤ _
        rw [h, mul_comm ε]
        exact mul_le_mul_of_nonneg_left (least he) hp.le
    obtain ⟨u, hu⟩ := equilibrium_of_margin T hT a n target ε hε room
    exact ⟨u, hu, fun y hy => held_equilibrium_unique T hT a n (fun _ => true)
      (fun _ => by simp) (fun j _ => congrFun (hy.trans hu.symm) j)⟩


/-- Fix the free log concentrations of all unheld ligands. Their contribution shifts each
form's standard log weight. Feasibility depends only on the counts in the held coordinates. -/
theorem existsUnique_held_equilibrium_iff {U : Type*} [Fintype U] (T : B → ℝ) (hT : ∀ b, 0 ≤ T b)
    (a : (b : B) → F b → ℝ) (n : (b : B) → F b → L ⊕ U → ℤ) (target : L → ℝ) (fixed : U → ℝ) :
    (∃! u : L → ℝ, ∀ j, total T a n (Sum.elim u fixed) (Sum.inl j) = target j) ↔
      ∀ d ∈ stdSimplex ℝ L, 0 < margin T (fun b i j => n b i (Sum.inl j)) target d := by
  let counts := fun b i (j : L) => n b i (Sum.inl j)
  let shifted := fun b i => a b i + ∑ k, (n b i (Sum.inr k) : ℝ) * fixed k
  have weight (b : B) (i : F b) (u : L → ℝ) :
      logWeight (a b i) (n b i) (Sum.elim u fixed) = logWeight (shifted b i) (counts b i) u := by
    simp only [logWeight, Fintype.sum_sum_type, shifted, counts, Sum.elim_inl, Sum.elim_inr]
    ring
  have eqn (u : L → ℝ) :
      (∀ j, total T a n (Sum.elim u fixed) (Sum.inl j) = target j) ↔ total T shifted counts u = target := by
    simp only [total, weight, Sum.elim_inl, counts, funext_iff]
  simpa only [eqn] using existsUnique_equilibrium_iff T hT shifted counts target


/-- The tissue host stores strictly positive held totals, and every binder has a base form
with zero counts. Those two facts already guarantee exact feasibility throughout its domain. -/
theorem positive_totals_admit_equilibrium (T : B → ℝ) (hT : ∀ b, 0 ≤ T b)
    (a : (b : B) → F b → ℝ) (n : (b : B) → F b → L → ℤ) (target : L → ℝ)
    (positive : ∀ j, 0 < target j) (base : ∀ b, ∃ i, ∀ j, n b i j = 0) :
    ∃! u, total T a n u = target := by
  apply (existsUnique_equilibrium_iff T hT a n target).2
  intro d hd
  have coord : ∃ j, 0 < d j := by
    by_contra! no
    have z := Finset.sum_nonpos (s := Finset.univ) (fun j _ => no j)
    linarith [hd.2]
  obtain ⟨j, hj⟩ := coord
  have free : 0 < ∑ k, target k * d k := (mul_pos (positive j) hj).trans_le
    (Finset.single_le_sum (fun k _ => mul_nonneg (positive k).le (hd.1 k)) (Finset.mem_univ j))
  have floorNonpos (b : B) : formFloor (n b) d ≤ 0 := by
    obtain ⟨i, hi⟩ := base b
    simpa [projected, hi] using floor_le (n b) d i
  exact sub_pos.mpr ((Finset.sum_nonpos (fun b _ => mul_nonpos_of_nonneg_of_nonpos
    (hT b) (floorNonpos b))).trans_lt free)

end

end CellsProofs.Chemistry.BindingFeasibility
