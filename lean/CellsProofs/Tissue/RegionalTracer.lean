import CellsProofs.Accounting.Transfer
import CellsProofs.Chemistry.SpeciesTurnover
import Mathlib.Tactic.LinearCombination

/-! # An old label in a closed cell

The passive tracer reads one-way exchange and clearance records at each accepted
step. Once production has switched to another label, the old cohort has no source.
The balance below starts from its linear solve and permits clearance already
booked at the end of the pulse. Amounts and time are in fmol and seconds.
-/

namespace CellsProofs.Tissue.RegionalTracer

open scoped BigOperators
open CellsProofs.Chemistry

noncomputable section

variable {Node Route : Type*} [DecidableEq Node] [Fintype Route]

/-- One accepted step's records for a single species. Both route endpoints
belong to the cell. Clearance counts material leaving the tracked species. -/
structure Step (Node Route : Type*) where
  source : Route → Node
  destination : Route → Node
  moved : Route → ℝ
  cleared : Node → ℝ
  totalBefore : Node → ℝ
  totalAfter : Node → ℝ

def routeTotal (endpoint : Route → Node) (value : Route → ℝ) (n : Node) : ℝ :=
  ∑ e, if endpoint e = n then value e else 0

def Step.invAmount (s : Step Node Route) (n : Node) : ℝ :=
  let total := s.totalBefore n + s.totalAfter n
  if 0 < total then total⁻¹ else 0

def Step.share (s : Step Node Route) (x y : Node → ℝ) (n : Node) : ℝ :=
  (x n + y n) * s.invAmount n

/-- Incoming part of a matrix row, applied to the starting or ending cohort. -/
def Step.incoming (s : Step Node Route) (x : Node → ℝ) : Node → ℝ :=
  routeTotal s.destination (fun e => s.moved e * s.invAmount (s.source e) * x (s.source e))

/-- One column of the tracer's A y = B with no new members of this cohort. -/
def Step.Solves (s : Step Node Route) (x y : Node → ℝ) : Prop := ∀ n,
  let ratio := (s.cleared n + routeTotal s.source s.moved n) * s.invAmount n
  (1 + ratio) * y n - s.incoming y n = (1 - ratio) * x n + s.incoming x n

/-- Collecting the two sides of a solved row gives the outflow split used
for both cumulative records, including a node empty at both step endpoints. -/
theorem node_balance (s : Step Node Route) {x y : Node → ℝ} (solved : s.Solves x y) (n : Node) :
    y n + s.cleared n * s.share x y n = x n +
      Accounting.nodeChange s.source s.destination (fun e => s.moved e * s.share x y (s.source e)) n := by
  let flux := fun e => s.moved e * s.share x y (s.source e)
  have incoming : routeTotal s.destination flux n = s.incoming y n + s.incoming x n := by
    unfold Step.incoming routeTotal
    rw [← Finset.sum_add_distrib]
    apply Finset.sum_congr rfl
    intro e _
    by_cases h : s.destination e = n
    · simp only [if_pos h, flux, Step.share]
      ring
    · simp [h]
  have outgoing : routeTotal s.source flux n = routeTotal s.source s.moved n * s.share x y n := by
    unfold routeTotal
    rw [Finset.sum_mul]
    apply Finset.sum_congr rfl
    intro e _
    by_cases h : s.source e = n <;> simp [flux, h]
  have change : Accounting.nodeChange s.source s.destination flux n =
      routeTotal s.destination flux n - routeTotal s.source flux n := Finset.sum_sub_distrib
  change y n + s.cleared n * s.share x y n = x n + Accounting.nodeChange _ _ flux n
  rw [change, incoming, outgoing]
  unfold Step.share
  linear_combination solved n

/-- In an arbitrary region the live cohort plus its clearance changes only
by labelled transfers across the boundary. Internal routes cancel. -/
theorem region_balance (region : Finset Node) (s : Step Node Route) {x y : Node → ℝ}
    (solved : s.Solves x y) :
    (∑ n ∈ region, y n) + (∑ n ∈ region, s.cleared n * s.share x y n) =
      (∑ n ∈ region, x n) + ∑ e,
        ((if s.destination e ∈ region then s.moved e * s.share x y (s.source e) else 0) -
         (if s.source e ∈ region then s.moved e * s.share x y (s.source e) else 0)) := by
  simpa only [Finset.sum_add_distrib, Accounting.region_balance] using
    (Finset.sum_congr (s₁ := region) rfl (fun n _ => node_balance s solved n))

/-- From the pulse endpoint (row zero) to any later accepted row, the region,
its complement and the increase in labelled clearance account for the original cohort. -/
theorem pulse_balance [Fintype Node] (region : Finset Node) (step : ℕ → Step Node Route)
    (held loss : ℕ → Node → ℝ) (last : ℕ)
    (solved : ∀ k < last, (step k).Solves (held k) (held (k + 1)))
    (booked : ∀ k < last, ∀ n, loss (k + 1) n = loss k n +
      (step k).cleared n * (step k).share (held k) (held (k + 1)) n) :
    (∑ n ∈ region, held last n) + (∑ n ∈ regionᶜ, held last n) +
      ∑ n, (loss last n - loss 0 n) = ∑ n, held 0 n := by
  have conserved (k : ℕ) (hk : k ≤ last) :
      (∑ n, held k n) + (∑ n, loss k n) = (∑ n, held 0 n) + (∑ n, loss 0 n) := by
    induction k with
    | zero => rfl
    | succ k ih =>
      have h := Nat.lt_of_succ_le hk
      have closed := region_balance Finset.univ (step k) (solved k h)
      simp only [Finset.mem_univ, if_true, sub_self, Finset.sum_const_zero, add_zero] at closed
      have record := Finset.sum_congr (s₁ := Finset.univ) rfl (fun n _ => booked k h n)
      rw [Finset.sum_add_distrib] at record
      linarith only [closed, record, ih h.le]
  rw [Finset.sum_add_sum_compl, Finset.sum_sub_distrib]
  linarith only [conserved last le_rfl]

structure Readout where
  donor : ℝ
  receiver : ℝ
  loss : ℝ

/-- One-way first-order exchange debits the donor and credits the receiver. -/
def transfer (n receiver k t : ℝ) : Readout :=
  let moved := n * (1 - Real.exp (-(k * t)))
  ⟨n - moved, receiver + moved, 0⟩

/-- First-order turnover with zero production, at the same donor and rate. -/
def degradation (n receiver k t : ℝ) : Readout :=
  ⟨SpeciesTurnover.amount n 0 k t, receiver, SpeciesTurnover.cleared n 0 k t⟩

/-- Even the entire noiseless donor trace is identical for the two controls. -/
theorem equal_donor_traces (n receiver k : ℝ) :
    (fun t => (transfer n receiver k t).donor) = fun t => (degradation n receiver k t).donor := by
  funext t
  simp only [transfer, degradation, SpeciesTurnover.amount, SpeciesTurnover.survival, zero_mul, add_zero]
  ring

/-- At any positive time with material and an active rate, either the receiver
or the loss record distinguishes the controls. Both differences equal the material moved. -/
theorem receiver_and_loss_distinguish {n k t : ℝ} (receiver : ℝ)
    (hn : 0 < n) (hk : 0 < k) (ht : 0 < t) :
    let tr := transfer n receiver k t
    let deg := degradation n receiver k t
    deg.receiver < tr.receiver ∧ tr.loss < deg.loss ∧
      tr.receiver - deg.receiver = deg.loss - tr.loss ∧ deg.loss = n - tr.donor := by
  have moved := mul_pos hn (sub_pos.mpr (Real.exp_lt_one_iff.mpr (neg_lt_zero.mpr (mul_pos hk ht))))
  simp only [transfer, degradation, SpeciesTurnover.cleared, SpeciesTurnover.survival,
    zero_mul, add_zero, sub_zero]
  exact ⟨lt_add_of_pos_right _ moved, moved, by ring, by ring⟩

end

end CellsProofs.Tissue.RegionalTracer
