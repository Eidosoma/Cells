import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Ring

/-! # Net transfers in seven mitochondrial cycles

N is the matrix and P the intermembrane space. Weights refer to the engine's
base ionic forms. Water is the implicit solvent. All extents are signed.
-/
namespace CellsProofs.Chemistry.MitochondrialCycles
noncomputable section

inductive Row where
  | nadh | nad | q | qh₂ | oxygen | cytRed | cytOx | hN | hP
  | adpN | atpN | piN | adpP | atpP | piP | kN | kP
  deriving DecidableEq

inductive Cycle where
  | complexI | complexIII | complexIV | synthase | nucleotide | phosphate | potassium

open Row Cycle

/-- Products minus reactants for a forward turnover. A weight can select a
single row, a conserved pool, or the charge on one side. -/
def change (c : Cycle) (w : Row → ℝ) : ℝ :=
  match c with
  | .complexI => -w nadh - w q + w nad + w qh₂ - 5 * w hN + 4 * w hP
  | .complexIII => -w qh₂ + w q - 2 * w cytOx + 2 * w cytRed - 2 * w hN + 4 * w hP
  | .complexIV => -w oxygen - 4 * w cytRed + 4 * w cytOx - 8 * w hN + 4 * w hP
  | .synthase => -w adpN - w piN + w atpN + 2 * w hN - 3 * w hP
  | .nucleotide => -w atpN + w atpP - w adpP + w adpN
  | .phosphate => -w piP + w piN - 2 * w hP + 2 * w hN
  | .potassium => -w kP + w kN - w hN + w hP

def matrixCharge : Row → ℝ
  | .nadh | .piN => -2
  | .nad => -1
  | .adpN => -3
  | .atpN => -4
  | .hN | .kN => 1
  | _ => 0

def outerCharge : Row → ℝ
  | .cytRed => 2
  | .cytOx => 3
  | .adpP => -3
  | .atpP => -4
  | .piP => -2
  | .hP | .kP => 1
  | _ => 0

def chargePerTurn : Cycle → ℝ
  | .complexI => 4
  | .complexIII => 2
  | .complexIV => 8
  | .synthase => -3
  | .nucleotide => -1
  | .phosphate | .potassium => 0

/-- The net P-side charge includes redox and nucleotide interconversion.
Each cycle puts the opposite charge on N. -/
theorem charge_on_each_side (c : Cycle) :
    change c outerCharge = chargePerTurn c ∧ change c matrixCharge = -chargePerTurn c := by
  cases c <;> norm_num [change, outerCharge, matrixCharge, chargePerTurn]

def respiratory (i iii iv : ℝ) (w : Row → ℝ) : ℝ :=
  i * change complexI w + iii * change complexIII w + iv * change complexIV w

def count (row : Row) (s : Row) : ℝ := if s = row then 1 else 0

/-- Restoring both intermediate redox carriers fixes relative turnover. -/
theorem carrier_balance_iff (i iii iv : ℝ) :
    (respiratory i iii iv (count qh₂) = 0 ∧ respiratory i iii iv (count cytRed) = 0) ↔
    (i = 2 * iv ∧ iii = 2 * iv) := by
  simp +decide [respiratory, change, count]
  constructor
  · rintro ⟨hq, hc⟩
    constructor <;> linarith
  · rintro ⟨rfl, rfl⟩
    constructor <;> ring

/-- For any measured inventory, two NADH per oxygen cancel Q and cytochrome c
and add twenty explicit protons on P. N also supplies two scalar protons. -/
theorem respiratory_net (turn : ℝ) (w : Row → ℝ) :
    respiratory (2 * turn) (2 * turn) turn w =
    turn * (-2 * w nadh + 2 * w nad - w oxygen - 22 * w hN + 20 * w hP) := by
  unfold respiratory change
  ring

def delivery (w : Row → ℝ) : ℝ :=
  change synthase w + change nucleotide w + change phosphate w

/-- Synthesis, ATP/ADP exchange and phosphate uptake once each restore the
matrix nucleotide and phosphate rows. The solvent water is implicit. -/
theorem delivery_net (w : Row → ℝ) :
    delivery w = w atpP - w adpP - w piP + 4 * w hN - 5 * w hP := by
  unfold delivery change
  ring

theorem delivered_charge : delivery outerCharge = -4 := by norm_num [delivery_net, outerCharge]

theorem potassium_proton_swap (w : Row → ℝ) :
    change potassium w = (w kN - w kP) - (w hN - w hP) := by unfold change; ring

/-- For this three-proton synthase and these seven paths alone, if the
intermediate carriers balance, zero net charge transfer requires five ATP
deliveries per oxygen. Flux, slippage and other currents are separate inputs. -/
theorem charge_balance_iff (oxygenTurns deliveries exchanges : ℝ) :
    respiratory (2 * oxygenTurns) (2 * oxygenTurns) oxygenTurns outerCharge +
        deliveries * delivery outerCharge + exchanges * change potassium outerCharge = 0 ↔
      deliveries = 5 * oxygenTurns := by
  rw [respiratory_net, delivered_charge, (charge_on_each_side potassium).1]
  norm_num [outerCharge, chargePerTurn]
  constructor <;> intro h <;> linarith

end
end CellsProofs.Chemistry.MitochondrialCycles
