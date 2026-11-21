import CellsProofs.Chemistry.Stoichiometry
import CellsProofs.Transport.ChargedPermeation

/-! # Exchanging the solution in a held bath

Each target is specified relative to the original bath. A positive supply goes
from the bath to the tissue. Work identities are per species and use chemical
potentials in energy per amount, including the common unit conversion.
-/

namespace CellsProofs.Tissue.BathSchedule

open CellsProofs.Chemistry
open scoped BigOperators

noncomputable section

variable {Species Formula : Type*} [Fintype Species] [Fintype Formula]

def target (counts : Formula → Species → ℤ) (offset : Formula → ℝ)
    (volume : ℝ) (declared : Species → ℝ) : Species → ℝ :=
  afterReactions counts (fun f => volume * offset f) declared

/-- Signed offsets of individually neutral formula units preserve the bath's declared charge. -/
theorem target_charge (z : Species → ℤ) (counts : Formula → Species → ℤ)
    (neutral : ∀ f, ∑ s, z s * counts f s = 0)
    (offset : Formula → ℝ) (v : ℝ) (declared : Species → ℝ) :
    inventory z (target counts offset v declared) = inventory z declared :=
  inventory_after_reactions z counts _ declared neutral

/-- The charge difference between two absolute targets is zero for every pair of recipes. -/
theorem neutral_event (z : Species → ℤ) (counts : Formula → Species → ℤ)
    (neutral : ∀ f, ∑ s, z s * counts f s = 0)
    (before after : Formula → ℝ) (v : ℝ) (declared : Species → ℝ) :
    inventory z (fun s => target counts after v declared s - target counts before v declared s) = 0 := by
  change ∑ s, (z s : ℝ) * (_ - _) = 0
  simp only [mul_sub, Finset.sum_sub_distrib]
  exact sub_eq_zero.mpr ((target_charge z counts neutral after v declared).trans
    (target_charge z counts neutral before v declared).symm)

/-- The sum the parser evaluates for one species is independent of formula-unit order. -/
theorem recipe_order {α : Type*} {first second : List α} (order : first.Perm second)
    (counts : α → ℤ) (offset : α → ℝ) (v declared : ℝ) :
    declared + v * (first.map (fun f => (counts f : ℝ) * offset f)).sum =
      declared + v * (second.map (fun f => (counts f : ℝ) * offset f)).sum := by
  rw [(order.map (fun f => (counts f : ℝ) * offset f)).sum_eq]

/-- Adding two-count units and removing three-count units in matching amounts leaves just d. -/
theorem recipe_residual (a d : ℝ) : 2 * (3 * a) + d + 3 * (-2 * a) = d := by ring

/-- An equimolar KCl-for-NaCl swap preserves ideal particle concentration, chloride and charge. -/
theorem salt_swap (k na cl d : ℝ) :
    (k + d) + (na - d) + (cl + d - d) = k + na + cl ∧
    cl + d - d = cl ∧ (k + d) + (na - d) - (cl + d - d) = k + na - cl := by
  constructor <;> [ring; constructor <;> ring]

/-- Sum the changes of any state quantity over a sequence of absolute targets. -/
def changes {α : Type*} (value : α → ℝ) (start : α) : List α → ℝ
  | [] => 0
  | next :: rest => value next - value start + changes value next rest

theorem changes_telescope {α : Type*} (value : α → ℝ) (start : α) (stops : List α) :
    changes value start stops = value (stops.foldl (fun _ next => next) start) - value start := by
  induction stops generalizing start with
  | nil => simp [changes]
  | cons next rest ih => simp only [changes, List.foldl_cons, ih]; ring

/-- Ideal bath energy at fixed positive volume. rt is RT in energy per fmol. -/
def energy (rt v n : ℝ) := rt * n * (Real.log (n / v) - 1)

theorem energy_booking (rt : ℝ) {v old new : ℝ} (hv : 0 < v)
    (ho : 0 < old) (hn : 0 < new) :
    rt * ((new - old) * (Real.log (old / v) - 1) + new * Real.log (new / old)) =
      energy rt v new - energy rt v old := by
  simp only [energy, Real.log_div ho.ne' hv.ne', Real.log_div hn.ne' hv.ne',
    Real.log_div hn.ne' ho.ne']
  ring

/-- A held electrical potential cancels out of the change in reservoir potential. -/
theorem potential_change (rt electrical : ℝ) {old new : ℝ} (ho : 0 < old) (hn : 0 < new) :
    (rt * Real.log new + electrical) - (rt * Real.log old + electrical) =
      rt * Real.log (new / old) := by rw [Real.log_div hn.ne' ho.ne']; ring

def correction (baseline current supplied carry : ℝ) := carry + (current - baseline) * supplied

/-- Changing composition before any new supply leaves the reconciled work continuous. -/
theorem switch_continuous (baseline old new supplied carry : ℝ) :
    correction baseline new supplied (carry + (old - new) * supplied) =
      correction baseline old supplied carry := by unfold correction; ring

/-- Advancing the tissue's supply books work at the current potential. -/
theorem supply_work (baseline current supplied carry dn : ℝ) :
    baseline * dn + (correction baseline current (supplied + dn) carry -
      correction baseline current supplied carry) = current * dn := by unfold correction; ring

/-- Each epoch switches the potential, then delivers its signed increment of tissue supply. -/
def epochCorrection (baseline current supplied carry : ℝ) : List (ℝ × ℝ) → ℝ
  | [] => correction baseline current supplied carry
  | (μ, dn) :: rest =>
    epochCorrection baseline μ (supplied + dn) (carry + (current - μ) * supplied) rest

theorem epoch_sum (baseline current supplied carry : ℝ) (epochs : List (ℝ × ℝ)) :
    epochCorrection baseline current supplied carry epochs = correction baseline current supplied carry +
      (epochs.map (fun e => (e.1 - baseline) * e.2)).sum := by
  induction epochs generalizing current supplied carry with
  | nil => simp [epochCorrection]
  | cons e rest ih =>
    obtain ⟨μ, dn⟩ := e
    simp only [epochCorrection, List.map_cons, List.sum_cons, ih, correction]
    ring

/-- At fixed intracellular concentration the change in a single ion's reversal voltage
depends only on the two external concentrations, temperature and signed molar charge. -/
theorem reversal_shift {scale ci lo hi rt q v₁ v₂ : ℝ} (hp : 0 < scale) (hc : 0 < ci)
    (hlo : 0 < lo) (hhi : 0 < hi) (ht : 0 < rt) (hq : q ≠ 0)
    (first : Transport.ProtonLeak.inward Transport.analyticFactor scale ci lo (q * v₁ / rt) = 0)
    (second : Transport.ProtonLeak.inward Transport.analyticFactor scale ci hi (q * v₂ / rt) = 0) :
    v₂ - v₁ = rt / q * Real.log (hi / lo) := by
  rw [(Transport.ChargedPermeation.reversal_iff hp hc hlo ht hq v₁).mp first,
    (Transport.ChargedPermeation.reversal_iff hp hc hhi ht hq v₂).mp second,
    Real.log_div hhi.ne' hlo.ne']
  ring

end

end CellsProofs.Tissue.BathSchedule
