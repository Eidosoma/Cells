import CellsProofs.Transport.ChargedPermeation

/-! # Passive sodium, potassium and chloride on the same membrane

Concentrations are fixed during the current measurement. Each p is effective
area times permeability, including the opening. Voltage is inside minus outside.
-/

namespace CellsProofs.Transport.MixedMembrane

noncomputable section

structure Membrane where
  pNa : ℝ
  pK : ℝ
  pCl : ℝ
  naIn : ℝ
  naOut : ℝ
  kIn : ℝ
  kOut : ℝ
  clIn : ℝ
  clOut : ℝ

def numerator (m : Membrane) := m.pNa * m.naOut + m.pK * m.kOut + m.pCl * m.clIn
def denominator (m : Membrane) := m.pNa * m.naIn + m.pK * m.kIn + m.pCl * m.clOut

/-- Signed outward electrical current in amperes. x = FV/(RT). -/
def total (b : NormalizedFactor) (m : Membrane) (f x : ℝ) :=
  f * (-ProtonLeak.inward b m.pNa m.naIn m.naOut x
       - ProtonLeak.inward b m.pK m.kIn m.kOut x
       + ProtonLeak.inward b m.pCl m.clIn m.clOut (-x))

theorem current_factorization (m : Membrane) (f x : ℝ) :
    total analyticFactor m f x = f * analyticFactor.eval x *
      (Real.exp x * denominator m - numerator m) := by
  simp only [total, ProtonLeak.inward, constantFieldFlux, one_mul, neg_neg,
    ProtonLeak.analytic_reverse x, numerator, denominator]
  ring

/-- The analytic total vanishes at exactly the GHK voltage, including a
zero-volt reversal. Individual ions may still carry current there. -/
theorem reversal_iff (m : Membrane) {f thermal : ℝ} (hf : 0 < f) (ht : 0 < thermal)
    (hn : 0 < numerator m) (hd : 0 < denominator m) (v : ℝ) :
    total analyticFactor m f (v / thermal) = 0 ↔
      v = thermal * Real.log (numerator m / denominator m) := by
  rw [current_factorization, mul_eq_zero, or_iff_right (mul_pos hf (ProtonLeak.analytic_pos _)).ne',
    sub_eq_zero, ← eq_div_iff hd.ne']
  constructor
  · intro h
    have e := congrArg Real.log h
    rw [Real.log_exp] at e
    linarith [(div_eq_iff ht.ne').mp e]
  · intro h
    rw [h, mul_div_cancel_left₀ _ ht.ne', Real.exp_log (div_pos hn hd)]

/-- The real interpretation of the engine's evaluator equals the analytic
three-ion current at zero and outside its near-zero polynomial interval. -/
theorem engine_current_eq (m : Membrane) (f x : ℝ) (hx : x = 0 ∨ 1 / 10000 ≤ |x|) :
    total seriesFactor m f x = total analyticFactor m f x := by
  have hn : -x = 0 ∨ 1 / 10000 ≤ |-x| := by simpa using hx
  simp only [total, ProtonLeak.series_eq_analytic hx, ProtonLeak.series_eq_analytic hn]

end

end CellsProofs.Transport.MixedMembrane
