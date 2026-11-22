import CellsProofs.Chemistry.Vesicle
import Mathlib.Analysis.SpecialFunctions.Pow.Real

/-! Exact-real osmotic energy change for a single assembly event. The bath and
standard densities are in particles per unit volume. The membrane's spherical
capacity is proportional to the three-halves power of its integer footprint. -/

namespace CellsProofs.Chemistry.VesicleEvent

noncomputable section

structure Medium where
  bath : ℝ
  standard : ℝ
  scale : ℝ
  bath_pos : 0 < bath
  standard_pos : 0 < standard
  scale_pos : 0 < scale

/-- The regular event path requires a nonempty lumen and a positive membrane footprint. -/
structure State where
  n : ℝ
  w : ℝ
  n_pos : 0 < n
  w_pos : 0 < w

def cap (p : Medium) (s : State) : ℝ := p.scale * s.w ^ (3 / 2 : ℝ)

theorem cap_eq_sqrt (p : Medium) (s : State) :
    cap p s = p.scale * s.w * Real.sqrt s.w := by
  rw [cap, Real.sqrt_eq_rpow, show (3 / 2 : ℝ) = 1 + 1 / 2 by norm_num,
    Real.rpow_add s.w_pos, Real.rpow_one, mul_assoc]

private theorem cap_pos (p : Medium) (s : State) : 0 < cap p s :=
  mul_pos p.scale_pos (Real.rpow_pos_of_pos s.w_pos _)

def slack (p : Medium) (s : State) := Vesicle.energy s.n p.bath p.standard (s.n / p.bath)
def taut (p : Medium) (s : State) := Vesicle.energy s.n p.bath p.standard (cap p s)
def energy (p : Medium) (s : State) :=
  Vesicle.energy s.n p.bath p.standard (Vesicle.volume s.n p.bath (cap p s))

/-- Exact-real interpretation of log1p((b-a)/a). -/
def logStep (a b : ℝ) := Real.log (1 + (b - a) / a)

private theorem logStep_eq {a b : ℝ} (ha : 0 < a) (hb : 0 < b) :
    logStep a b = Real.log b - Real.log a := by
  have hr : 1 + (b - a) / a = b / a := by field_simp
  rw [logStep, hr, Real.log_div hb.ne' ha.ne']

def slackChange (p : Medium) (a b : State) :=
  (b.n - a.n) * (1 + Real.log (p.bath / p.standard)) -
    (b.n - a.n) * Real.log b.n - a.n * logStep a.n b.n

def tautChange (p : Medium) (a b : State) :=
  -(b.n - a.n) * (Real.log (p.standard * p.scale) + 3 / 2 * Real.log b.w) -
    3 / 2 * a.n * logStep a.w b.w +
    p.bath * cap p a * (Real.exp (3 / 2 * logStep a.w b.w) - 1)

def gap (p : Medium) (s : State) :=
  let x := p.bath * cap p s / s.n
  s.n * (Real.exp (Real.log x) - 1 - Real.log x)

private theorem slack_form (p : Medium) (s : State) :
    slack p s = s.n * (1 + Real.log (p.bath / p.standard)) - s.n * Real.log s.n := by
  rw [slack, Vesicle.energy, Real.log_mul p.standard_pos.ne' (div_pos s.n_pos p.bath_pos).ne',
    Real.log_div s.n_pos.ne' p.bath_pos.ne', Real.log_div p.bath_pos.ne' p.standard_pos.ne']
  field_simp [p.bath_pos.ne']
  ring

private theorem taut_form (p : Medium) (s : State) :
    taut p s = -s.n * (Real.log (p.standard * p.scale) + 3 / 2 * Real.log s.w) +
      p.bath * cap p s := by
  rw [taut, Vesicle.energy, cap, ← mul_assoc, Real.log_mul (mul_pos p.standard_pos p.scale_pos).ne'
    (Real.rpow_pos_of_pos s.w_pos _).ne', Real.log_rpow s.w_pos, mul_comm (3 / 2 : ℝ)]

theorem slack_change_eq (p : Medium) (a b : State) :
    slackChange p a b = slack p b - slack p a := by
  rw [slackChange, logStep_eq a.n_pos b.n_pos, slack_form, slack_form]
  ring

private theorem cap_ratio (p : Medium) (a b : State) :
    cap p a * Real.exp (3 / 2 * logStep a.w b.w) = cap p b := by
  simp only [cap, logStep_eq a.w_pos b.w_pos, Real.rpow_def_of_pos a.w_pos,
    Real.rpow_def_of_pos b.w_pos, mul_assoc, ← Real.exp_add]
  congr 2
  ring

theorem taut_change_eq (p : Medium) (a b : State) :
    tautChange p a b = taut p b - taut p a := by
  have hcap := congrArg (fun v => p.bath * v) (cap_ratio p a b)
  dsimp only at hcap
  rw [logStep_eq a.w_pos b.w_pos] at hcap
  rw [tautChange, logStep_eq a.w_pos b.w_pos, taut_form, taut_form]
  linear_combination hcap

theorem gap_eq (p : Medium) (s : State) : gap p s = taut p s - slack p s := by
  have h : s.n / (s.n / p.bath) = p.bath := by field_simp [s.n_pos.ne']
  have hx : cap p s / (s.n / p.bath) = p.bath * cap p s / s.n := by
    field_simp [s.n_pos.ne', p.bath_pos.ne']
    ring
  rw [taut, slack, Vesicle.energy_gap _ _ p.standard_pos (cap_pos p s) (div_pos s.n_pos p.bath_pos),
    h, sub_self, zero_mul, add_zero, hx, gap, Real.exp_log (div_pos (mul_pos p.bath_pos (cap_pos p s)) s.n_pos)]

theorem gap_nonneg (p : Medium) (s : State) : 0 ≤ gap p s := by
  have hx := div_pos (mul_pos p.bath_pos (cap_pos p s)) s.n_pos
  dsimp only [gap]
  rw [Real.exp_log hx]
  exact mul_nonneg s.n_pos.le (sub_nonneg.mpr (Real.log_le_sub_one_of_pos hx))

theorem gap_at_boundary (p : Medium) (s : State) (boundary : cap p s = s.n / p.bath) :
    gap p s = 0 := by
  rw [gap_eq, taut, slack, boundary, sub_self]

/-- The logarithmic comparison in the engine selects the same cap, with equality on the slack side. -/
theorem log_select (p : Medium) (s : State) :
    Real.log (cap p s) < Real.log (s.n / p.bath) ↔ cap p s < s.n / p.bath :=
  Real.log_lt_log_iff (cap_pos p s) (div_pos s.n_pos p.bath_pos)

/-- Price the change along the final branch and correct the energy at the starting state. -/
def change (p : Medium) (a b : State) :=
  if cap p b < b.n / p.bath then
    tautChange p a b + (if cap p a < a.n / p.bath then 0 else gap p a)
  else
    slackChange p a b - (if cap p a < a.n / p.bath then gap p a else 0)

theorem change_eq (p : Medium) (a b : State) :
    change p a b = energy p b - energy p a := by
  by_cases ha : cap p a < a.n / p.bath <;> by_cases hb : cap p b < b.n / p.bath <;>
    simp [change, ha, hb, energy, Vesicle.volume, min_eq_left, min_eq_right,
      le_of_not_gt, le_of_lt, slack_change_eq, taut_change_eq, gap_eq, taut, slack, *]

theorem round_trip (p : Medium) (a b : State) : change p a b + change p b a = 0 := by
  rw [change_eq, change_eq]
  ring

end

end CellsProofs.Chemistry.VesicleEvent
