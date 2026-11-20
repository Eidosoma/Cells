import CellsProofs.Transport.SodiumAnionSymport
import Mathlib.Algebra.Order.BigOperators.GroupWithZero.List
import Mathlib.Analysis.SpecialFunctions.ExpDeriv
import Mathlib.Algebra.BigOperators.Fin
import Mathlib.Algebra.BigOperators.Field
import Mathlib.Data.List.Rotate

/-! # The ordered two-sodium, one-anion cycle

On a ring, deleting one edge leaves a directed spanning tree towards a chosen
root. The two possible orientations are fixed by the position of the deleted
edge. Only one of the eight forward rates reads the external anion activity.
-/

namespace CellsProofs.Transport.SodiumAnionDiagram

open SodiumAnionSymport
noncomputable section

structure Edge where
  f : ℝ
  b : ℝ

def forward (es : List Edge) : ℝ := (es.map Edge.f).prod
def backward (es : List Edge) : ℝ := (es.map Edge.b).prod

/-- Sum over the position of the omitted edge, with the root at the start of the list. -/
def trees : List Edge → ℝ
  | [] => 0
  | e :: es => forward es + e.b * trees es

private theorem trees_append (left right : List Edge) :
    trees (left ++ right) = trees left * forward right + backward left * trees right := by
  induction left with
  | nil => simp [trees, backward]
  | cons e es ih => simp [trees, forward, backward, ih]; ring

/-- With the same denominator for the roots, each edge carries the difference
of the full forward and backward cycle products divided by that denominator. -/
theorem stationary_edge (left right : List Edge) (e : Edge) (z : ℝ) :
    e.f * (trees (e :: (right ++ left)) / z) -
      e.b * (trees ((right ++ left) ++ [e]) / z) =
      (forward (left ++ e :: right) - backward (left ++ e :: right)) / z := by
  rw [trees_append (right ++ left) [e]]
  simp [trees, forward, backward, div_eq_mul_inv]
  ring

def Positive (es : List Edge) := ∀ e ∈ es, 0 < e.f ∧ 0 < e.b

private theorem product_pos {es : List Edge} (h : Positive es) :
    0 < forward es ∧ 0 < backward es := by
  constructor <;> apply List.prod_pos <;> intro x hx <;>
    obtain ⟨e, he, rfl⟩ := List.mem_map.mp hx
  · exact (h e he).1
  · exact (h e he).2

private theorem trees_nonneg {es : List Edge} (h : Positive es) : 0 ≤ trees es := by
  induction es with
  | nil => simp [trees]
  | cons e es ih =>
    have tail : Positive es := fun a ha => h a (List.mem_cons_of_mem _ ha)
    exact (add_pos_of_pos_of_nonneg (product_pos tail).1
      (mul_nonneg (h e (by simp)).2.le (ih tail))).le

private theorem trees_pos {e : Edge} {es : List Edge} (h : Positive es) (hb : 0 ≤ e.b) :
    0 < trees (e :: es) :=
  add_pos_of_pos_of_nonneg (product_pos h).1 (mul_nonneg hb (trees_nonneg h))

/-- Each split of the remaining path places the root at one carrier state.
When the path has seven edges this sums all eight rooted weights. -/
def denominator (e : Edge) (path : List Edge) : ℝ :=
  ∑ i : Fin (path.length + 1), trees (path.drop i ++ e :: path.take i)

private theorem parts_pos {es : List Edge} (h : Positive es) (i : ℕ) :
    Positive (es.drop i) ∧ Positive (es.take i) :=
  ⟨fun e he => h e (List.mem_of_mem_drop he), fun e he => h e (List.mem_of_mem_take he)⟩

private theorem root_pos {e : Edge} {path : List Edge} (hp : Positive path)
    (hf : 0 ≤ e.f) (hb : 0 ≤ e.b) (i : ℕ) :
    0 < trees (path.drop i ++ e :: path.take i) := by
  obtain ⟨hl, hr⟩ := parts_pos hp i
  rw [trees_append]
  apply add_pos_of_nonneg_of_pos
  · exact mul_nonneg (trees_nonneg hl) (mul_nonneg hf (product_pos hr).1.le)
  · exact mul_pos (product_pos hl).2 (trees_pos hr hb)

theorem denominator_pos {e : Edge} {path : List Edge} (hp : Positive path)
    (hf : 0 ≤ e.f) (hb : 0 ≤ e.b) : 0 < denominator e path :=
  Finset.sum_pos (fun i _ => root_pos hp hf hb i) Finset.univ_nonempty

/-- Every carrier state has positive probability and their probabilities sum to one. -/
theorem occupancy_normalized {e : Edge} {path : List Edge} (hp : Positive path)
    (hf : 0 ≤ e.f) (hb : 0 ≤ e.b) :
    let p := fun i : Fin (path.length + 1) =>
      trees (path.drop i ++ e :: path.take i) / denominator e path
    (∀ i, 0 < p i) ∧ ∑ i, p i = 1 := by
  have hz := denominator_pos hp hf hb
  refine ⟨fun i => div_pos (root_pos hp hf hb i) hz, ?_⟩
  dsimp
  rw [← Finset.sum_div]
  exact div_self hz.ne'

/-- For one substrate-dependent forward edge, the tree sum is affine in the
substrate. Each rooted tree uses that edge at most once. -/
theorem denominator_affine (a b x : ℝ) (path : List Edge) :
    denominator ⟨a * x, b⟩ path =
      (∑ i : Fin (path.length + 1), trees (path.drop i) * a * forward (path.take i)) * x +
      denominator ⟨0, b⟩ path := by
  unfold denominator
  rw [Finset.sum_mul, ← Finset.sum_add_distrib]
  apply Finset.sum_congr rfl
  intro i _
  simp [trees_append, forward, trees]
  ring

/-- With at least one other edge the denominator increases strictly with
external substrate activity at fixed voltage and fixed remaining activities. -/
theorem denominator_slope_pos {a : ℝ} (ha : 0 < a) {e : Edge} {rest : List Edge}
    (hp : Positive (e :: rest)) :
    0 < ∑ i : Fin ((e :: rest).length + 1),
      trees ((e :: rest).drop i) * a * forward ((e :: rest).take i) := by
  refine Finset.sum_pos' ?_ ⟨0, Finset.mem_univ _, ?_⟩
  · intro i _
    obtain ⟨hl, hr⟩ := parts_pos hp i
    exact mul_nonneg (mul_nonneg (trees_nonneg hl) ha.le) (product_pos hr).1.le
  · have tail : Positive rest := fun v hv => hp v (List.mem_cons_of_mem _ hv)
    simpa [forward] using mul_pos (trees_pos tail (hp e (by simp)).2.le) ha

def net (e : Edge) (path : List Edge) : ℝ :=
  (forward (e :: path) - backward (e :: path)) / denominator e path

/-- Subtracting the zero-substrate limiting turnover gives a rectangular
hyperbola. Both the amplitude and half-saturation are positive. -/
theorem substrate_response {a b : ℝ} (ha : 0 < a) (hb : 0 < b)
    {e : Edge} {rest : List Edge} (hp : Positive (e :: rest)) :
    ∃ amplitude half : ℝ, 0 < amplitude ∧ 0 < half ∧ ∀ x : ℝ, 0 ≤ x →
      net ⟨a * x, b⟩ (e :: rest) - net ⟨0, b⟩ (e :: rest) =
        amplitude * x / (half + x) := by
  let path := e :: rest
  let c := ∑ i : Fin (path.length + 1), trees (path.drop i) * a * forward (path.take i)
  let d := denominator ⟨0, b⟩ path
  have hc : 0 < c := denominator_slope_pos ha hp
  have hd : 0 < d := denominator_pos hp le_rfl hb.le
  obtain ⟨hf, hr⟩ := product_pos hp
  change 0 < forward path at hf
  change 0 < backward path at hr
  refine ⟨(a * forward path * d + b * backward path * c) / (d * c), d / c,
    by positivity, div_pos hd hc, ?_⟩
  intro x hx
  change net ⟨a * x, b⟩ path - net ⟨0, b⟩ path = _
  unfold net
  rw [denominator_affine a b x]
  change (a * x * forward path - b * backward path) / (c * x + d) -
    (0 * forward path - b * backward path) / d = _
  have hcx : 0 < c * x + d := add_pos_of_nonneg_of_pos (mul_nonneg hc.le hx) hd
  have hsum : 0 < d / c + x := add_pos_of_pos_of_nonneg (div_pos hd hc) hx
  field_simp [hc.ne', hd.ne', hcx.ne', hsum.ne']
  ring

structure Parameters where
  logF : ℝ
  logB : ℝ
  zF : ℝ
  zB : ℝ

def rates (p : Parameters) (logFAct logBAct voltage : ℝ) : Edge :=
  ⟨Real.exp (p.logF + logFAct + p.zF * voltage),
   Real.exp (p.logB + logBAct + p.zB * voltage)⟩

/-- The four binding arguments are log activities. Zero voltage on an edge
implements the fixed zero electrical coefficients of the declared diagram. -/
def ordered (p : Fin 8 → Parameters) (nN nP bN bP ψ : ℝ) : List Edge :=
  [rates (p 0) nP 0 ψ, rates (p 1) nP 0 ψ, rates (p 2) bP 0 0, rates (p 3) 0 0 ψ,
   rates (p 4) 0 bN 0, rates (p 5) 0 nN 0, rates (p 6) 0 nN 0, rates (p 7) 0 0 ψ]

/-- Rotating the declared ring to its anion-binding edge exposes exactly
one rate proportional to the external activity x. The other seven are fixed. -/
theorem ordered_substrate_edge (p : Fin 8 → Parameters) (nN nP bN ψ : ℝ)
    {x : ℝ} (hx : 0 < x) :
    (ordered p nN nP bN (Real.log x) ψ).rotate 2 =
      ⟨Real.exp (p 2).logF * x, Real.exp (p 2).logB⟩ ::
        ((ordered p nN nP bN 0 ψ).rotate 2).tail := by
  have edge : rates (p 2) (Real.log x) 0 0 =
      ⟨Real.exp (p 2).logF * x, Real.exp (p 2).logB⟩ := by
    simp [rates, Real.exp_add, Real.exp_log hx]
  change rates (p 2) (Real.log x) 0 0 :: _ = _
  rw [edge]
  rfl

/-- The turnover starting from the first edge of an ordered ring. -/
def turnover : List Edge → ℝ
  | [] => 0
  | e :: path => net e path

/-- Specialize the saturation result to the actual seven other rates of this carrier.
The reference at zero is the boundary value of the mass-action expression. -/
theorem ordered_dose_response (p : Fin 8 → Parameters) (nN nP bN ψ : ℝ) :
    let path := ((ordered p nN nP bN 0 ψ).rotate 2).tail
    ∃ amplitude half : ℝ, 0 < amplitude ∧ 0 < half ∧ ∀ x : ℝ, 0 < x →
      turnover ((ordered p nN nP bN (Real.log x) ψ).rotate 2) -
        net ⟨0, Real.exp (p 2).logB⟩ path = amplitude * x / (half + x) := by
  let tail := [rates (p 4) 0 bN 0, rates (p 5) 0 nN 0, rates (p 6) 0 nN 0,
    rates (p 7) 0 0 ψ, rates (p 0) nP 0 ψ, rates (p 1) nP 0 ψ]
  have h : Positive (rates (p 3) 0 0 ψ :: tail) := by
    intro edge he
    simp [tail] at he
    rcases he with h | h | h | h | h | h | h <;> subst edge <;> exact ⟨Real.exp_pos _, Real.exp_pos _⟩
  obtain ⟨a, k, ha, hk, eq⟩ := substrate_response (Real.exp_pos (p 2).logF)
    (Real.exp_pos (p 2).logB) h
  refine ⟨a, k, ha, hk, fun x hx => ?_⟩
  rw [ordered_substrate_edge p nN nP bN ψ hx]
  exact eq x hx.le

def logResidual (p : Fin 8 → Parameters) : ℝ := ∑ i, ((p i).logB - (p i).logF)
def chargeResidual (p : Fin 8 → Parameters) : ℝ :=
  ((p 0).zB - (p 0).zF) + ((p 1).zB - (p 1).zF) +
  ((p 3).zB - (p 3).zF) + ((p 7).zB - (p 7).zF) - 1

/-- The discrepancy from thermodynamic closure is a constant plus a term
linear in voltage. This also covers populations admitted within a numerical tolerance. -/
theorem product_with_residual (p : Fin 8 → Parameters) (nN nP bN bP ψ : ℝ) :
    let es := ordered p nN nP bN bP ψ
    backward es = forward es *
      Real.exp (energy 2 (nN - nP) (bN - bP) ψ + logResidual p + chargeResidual p * ψ) := by
  simp [ordered, backward, forward, rates, ← Real.exp_add, logResidual,
    chargeResidual, Fin.sum_univ_succ, energy]
  ring

/-- With exact thermodynamic closure, the stationary master-equation current
equals the host’s reversible rate given the same positive tree normalization. -/
theorem cycle_flux_eq_host (p : Fin 8 → Parameters) (hc : logResidual p = 0)
    (hz : chargeResidual p = 0) (nN nP bN bP ψ : ℝ) {z : ℝ} (hd : 0 < z) :
    let es := ordered p nN nP bN bP ψ
    (forward es - backward es) / z =
      ATPCycle.flux true (Real.log (forward es / z)) (energy 2 (nN - nP) (bN - bP) ψ) := by
  have h := product_with_residual p nN nP bN bP ψ
  simp only [hc, hz, zero_mul, add_zero] at h
  have hf : 0 < forward (ordered p nN nP bN bP ψ) := by
    simp [ordered, forward, rates, ← Real.exp_add, Real.exp_pos]
  dsimp only
  rw [h, ATPCycle.flux_eq_mass_action, Real.exp_log (div_pos hf hd)]
  ring

/-- With exact detailed balance, the eight-edge rate products give the same
stall and drive as the two-sodium specialization of the factored carrier. -/
theorem cycle_stall (p : Fin 8 → Parameters) (hc : logResidual p = 0)
    (hz : chargeResidual p = 0) (nN nP bN bP ψ : ℝ) :
    let es := ordered p nN nP bN bP ψ
    backward es = forward es ↔ ψ = head 2 (nN - nP) (bN - bP) := by
  have h := product_with_residual p nN nP bN bP ψ
  simp only [hc, hz, zero_mul, add_zero] at h
  dsimp only
  rw [h]
  have hf : 0 < forward (ordered p nN nP bN bP ψ) := by
    simp [ordered, forward, rates, ← Real.exp_add, Real.exp_pos]
  rw [mul_eq_left₀ hf.ne', Real.exp_eq_one_iff, energy_relative_to_stall (by norm_num : (1 : ℝ) < 2)]
  norm_num [sub_eq_zero]

/-- At stall the derivative of net cycles with respect to dimensionless
voltage is minus the forward one-way rate, even when that rate varies with voltage. -/
theorem stall_slope {oneWay : ℝ → ℝ} {d stall : ℝ} (h : HasDerivAt oneWay d stall) :
    HasDerivAt (fun ψ => oneWay ψ * (1 - Real.exp (ψ - stall))) (-oneWay stall) stall := by
  have hd := ((hasDerivAt_id stall).sub_const stall).exp
  simpa using h.mul ((hasDerivAt_const stall (1 : ℝ)).sub hd)

end
end CellsProofs.Transport.SodiumAnionDiagram
