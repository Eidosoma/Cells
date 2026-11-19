import CellsProofs.Accounting.Transfer
import CellsProofs.Transport.ChannelStep
import CellsProofs.Transport.ProtonLeak

/-! # The channel declarations of resolved_pump_tissue@3

Voltage is inside minus outside in volts. Both gate time constants are in
seconds. The gate-free laws have no dynamic gate rows; their dispatch fills
the unused rows with target zero and time constant one.
-/

namespace CellsProofs.Transport.IonChannels

noncomputable section

inductive Law where
  | kv1p1_mh2 | kv1p2_mh | kv1p3_mh | kv1p4_mh | kv1p5_mh | kv1p6_mh
  | kir2p1_mh2 | nav1p2_m3h_regularized | kleak_always_open | naleak_always_open
  | clleak_always_open

inductive Ion where
  | potassium | sodium | chloride | other
  deriving DecidableEq

def boltz (v mid slope : ℝ) : ℝ := 1 / (1 + Real.exp ((v - mid) / slope))

/-- The sign-split sigmoid used by Kir2.1 and Kv1.5 has the usual logistic value. -/
theorem stable_sigmoid (x : ℝ) :
    (if 0 ≤ x then 1 / (1 + Real.exp (-|x|))
     else Real.exp (-|x|) / (1 + Real.exp (-|x|))) = 1 / (1 + Real.exp (-x)) := by
  split_ifs with hx
  · rw [abs_of_nonneg hx]
  · rw [abs_of_neg (lt_of_not_ge hx), neg_neg, Real.exp_neg]
    have hp := Real.exp_pos x
    field_simp
    ring

private theorem boltz_pos (v mid slope : ℝ) : 0 < boltz v mid slope := by
  unfold boltz; positivity

private theorem boltz_bounds (v mid slope : ℝ) : boltz v mid slope ∈ Set.Icc 0 1 := by
  refine ⟨(boltz_pos ..).le, ?_⟩
  unfold boltz
  exact (div_le_one (by positivity)).mpr (by linarith [Real.exp_pos ((v - mid) / slope)])

def naActivation (v : ℝ) := 0.182 * 9 * seriesFactor.eval (-(v + 0.025) / 0.009)
def naDeactivation (v : ℝ) := 0.124 * 9 * seriesFactor.eval ((v + 0.025) / 0.009)
def naRecovery (v : ℝ) := 0.024 * 5 * seriesFactor.eval (-(v + 0.040) / 0.005)
def naInactivation (v : ℝ) := 0.0091 * 5 * seriesFactor.eval ((v + 0.065000123) / 0.005)

def targets (law : Law) (v : ℝ) : ℝ × ℝ :=
  match law with
  | .kv1p1_mh2 => (boltz v (-0.0305) (-0.0113943), boltz v (-0.03) 0.0273943)
  | .kv1p2_mh => (boltz v (-0.021) (-0.0113943), boltz v (-0.022) 0.0113943)
  | .kv1p3_mh => (boltz v (-0.0141) (-0.0103), boltz v (-0.033) 0.0037)
  | .kv1p4_mh => (boltz v (-0.0217) (-0.0169), boltz v (-0.0736) 0.0128)
  | .kv1p5_mh => (boltz v (-0.006) (-0.0064), boltz v (-0.0253) 0.0035)
  | .kv1p6_mh => (boltz v (-0.0208) (-0.0081), boltz v (-0.022) 0.01139)
  | .kir2p1_mh2 => (boltz v (-0.09648) 0.02326, boltz v (-0.16828) (-0.04413))
  | .nav1p2_m3h_regularized =>
    (naActivation v / (naActivation v + naDeactivation v), boltz v (-0.055) 0.0062)
  | .kleak_always_open | .naleak_always_open | .clleak_always_open => (0, 0)

def times (law : Law) (v : ℝ) : ℝ × ℝ :=
  match law with
  | .kv1p1_mh2 => (0.03 * boltz v (-0.07656) 0.0261479, 15 * boltz v (-0.16056) (-0.1))
  | .kv1p2_mh => (0.15 * boltz v (-0.06756) 0.0341479, 15 * boltz v (-0.04656) (-0.0441479))
  | .kv1p3_mh => (0.01916 - 0.284 * v, 1.1624 - 13.76 * v)
  | .kv1p4_mh => (0.003, 0.119)
  | .kv1p5_mh => (0.00833 - 0.1163 * v, 1.62 - 15.5 * v)
  | .kv1p6_mh => (0.03 * boltz v (-0.04656) 0.04414, 5 * boltz v (-0.04656) (-0.04414))
  | .kir2p1_mh2 =>
    (0.0037 - 0.00337 * boltz v (-0.0329) 0.02793, 0.00085 + 0.3063 * boltz v (-0.11829) (-0.02723))
  | .nav1p2_m3h_regularized =>
    (0.001 / (naActivation v + naDeactivation v), 0.001 / (naRecovery v + naInactivation v))
  | .kleak_always_open | .naleak_always_open | .clleak_always_open => (1, 1)

private theorem sodium_rates_pos (v : ℝ) :
    0 < naActivation v ∧ 0 < naDeactivation v ∧ 0 < naRecovery v ∧ 0 < naInactivation v := by
  unfold naActivation naDeactivation naRecovery naInactivation
  exact ⟨mul_pos (by norm_num) (ProtonLeak.series_pos _),
    mul_pos (by norm_num) (ProtonLeak.series_pos _), mul_pos (by norm_num) (ProtonLeak.series_pos _),
    mul_pos (by norm_num) (ProtonLeak.series_pos _)⟩

theorem targets_bounded (law : Law) (v : ℝ) :
    (targets law v).1 ∈ Set.Icc 0 1 ∧ (targets law v).2 ∈ Set.Icc 0 1 := by
  cases law <;> simp only [targets]
  all_goals first | exact ⟨boltz_bounds .., boltz_bounds ..⟩ | norm_num [Set.mem_Icc]
  obtain ⟨ha, hd, _, _⟩ := sodium_rates_pos v
  exact ⟨⟨(div_pos ha (add_pos ha hd)).le, (div_le_one (add_pos ha hd)).mpr (by linarith)⟩,
    boltz_bounds ..⟩

theorem times_positive (law : Law) {v : ℝ} (hv : v ∈ Set.Icc (-0.120) 0.060) :
    0 < (times law v).1 ∧ 0 < (times law v).2 := by
  have upper := hv.2
  obtain ⟨ha, hd, hr, hi⟩ := sodium_rates_pos v
  cases law <;> simp only [times] <;> constructor
  all_goals first
    | exact mul_pos (by norm_num) (boltz_pos ..)
    | exact div_pos (by norm_num) (add_pos ha hd)
    | exact div_pos (by norm_num) (add_pos hr hi)
    | linarith only [upper, (boltz_bounds v (-0.0329) 0.02793).2,
        boltz_pos v (-0.11829) (-0.02723)]

def opening (law : Law) (m h : ℝ) : ℝ :=
  match law with
  | .kv1p1_mh2 | .kir2p1_mh2 => m * h * h
  | .nav1p2_m3h_regularized => m ^ 3 * h
  | .kleak_always_open | .naleak_always_open | .clleak_always_open => 1
  | _ => m * h

def permeant : Law → Ion
  | .nav1p2_m3h_regularized | .naleak_always_open => .sodium
  | .clleak_always_open => .chloride
  | _ => .potassium

def valence : Law → ℤ
  | .clleak_always_open => -1
  | _ => 1

private theorem product_bounds {x y : ℝ} (hx : x ∈ Set.Icc 0 1) (hy : y ∈ Set.Icc 0 1) :
    x * y ∈ Set.Icc 0 1 := ⟨mul_nonneg hx.1 hy.1, mul_le_one₀ hx.2 hy.1 hy.2⟩

theorem opening_bounded (law : Law) {m h : ℝ} (hm : m ∈ Set.Icc 0 1) (hh : h ∈ Set.Icc 0 1) :
    opening law m h ∈ Set.Icc 0 1 := by
  have cubic : m ^ 3 ∈ Set.Icc 0 1 := ⟨pow_nonneg hm.1 _, pow_le_one₀ hm.1 hm.2⟩
  cases law <;> simp only [opening] <;> first
    | exact product_bounds (product_bounds hm hh) hh
    | exact product_bounds hm hh
    | exact product_bounds cubic hh
    | norm_num [Set.mem_Icc]

def flux (law : Law) (ion : Ion) (m h availability scale vf inside outside voltage : ℝ) : ℝ :=
  if ion = permeant law then
    constantFieldFlux seriesFactor (scale * (opening law m h * availability)) vf inside outside voltage
  else 0

/-- Updating the two active gate rows with the declared endpoint kinetics preserves
the population's opening bounds. Gate-free leaks have opening one for any rows. -/
theorem stage_opening_bounded (law : Law) {v w dt m h : ℝ}
    (hv : v ∈ Set.Icc (-0.120) 0.060) (hw : w ∈ Set.Icc (-0.120) 0.060)
    (ht : 0 ≤ dt) (hm : m ∈ Set.Icc 0 1) (hh : h ∈ Set.Icc 0 1) :
    opening law
      (ChannelStep.advance m (targets law v).1 (targets law w).1
        (dt / 2 * (1 / (times law v).1 + 1 / (times law w).1)))
      (ChannelStep.advance h (targets law v).2 (targets law w).2
        (dt / 2 * (1 / (times law v).2 + 1 / (times law w).2))) ∈ Set.Icc 0 1 := by
  obtain ⟨am, ah⟩ := targets_bounded law v
  obtain ⟨bm, bh⟩ := targets_bounded law w
  obtain ⟨ta, ua⟩ := times_positive law hv
  obtain ⟨tb, ub⟩ := times_positive law hw
  exact opening_bounded law (ChannelStep.stage_bounds hm am bm ht ta tb)
    (ChannelStep.stage_bounds hh ah bh ht ua ub)

theorem leak_opening (m h : ℝ) :
    opening .kleak_always_open m h = 1 ∧ opening .naleak_always_open m h = 1 := ⟨rfl, rfl⟩

/-- With valence −1 the chloride flux outward has the same algebra as a positive
ion flowing inward with the concentrations exchanged. This holds on both branches. -/
theorem chloride_flux (m h availability scale vf inside outside voltage : ℝ) :
    flux .clleak_always_open .chloride m h availability scale
      ((valence .clleak_always_open : ℝ) * vf) inside outside voltage =
      ProtonLeak.inward seriesFactor (scale * availability) outside inside (vf * voltage) := by
  simp [flux, permeant, opening, valence, ProtonLeak.inward, constantFieldFlux]

/-- For a conducting route, the chloride reversal voltage in volts on the analytic
branch (and at zero). The general flux identity also covers the near-zero series. -/
theorem chloride_reversal_iff {scale availability inside outside rt faraday : ℝ}
    (hs : 0 < scale) (ha : 0 < availability) (hi : 0 < inside) (ho : 0 < outside)
    (hrt : 0 < rt) (hf : 0 < faraday) (m h voltage : ℝ)
    (branch : faraday * voltage / rt = 0 ∨ 1 / 10000 ≤ |faraday * voltage / rt|) :
    flux .clleak_always_open .chloride m h availability scale
      ((valence .clleak_always_open : ℝ) * (faraday / rt)) inside outside voltage = 0 ↔
      voltage = rt / faraday * (Real.log inside - Real.log outside) := by
  rw [chloride_flux, div_mul_eq_mul_div, ProtonLeak.series_eq_analytic branch]
  exact ProtonLeak.reversal_voltage_iff (mul_pos hs ha) ho hi hrt hf voltage

/-- Outward membrane current in A for signed outward material flux in fmol/s,
with a positive monovalent conversion factor in C/fmol. -/
def outwardCurrent (law : Law) (chargePerFmol materialFlux : ℝ) : ℝ :=
  (valence law : ℝ) * chargePerFmol * materialFlux

theorem chloride_current_positive_iff {chargePerFmol materialFlux : ℝ} (hq : 0 < chargePerFmol) :
    0 < outwardCurrent .clleak_always_open chargePerFmol materialFlux ↔ materialFlux < 0 := by
  simp [outwardCurrent, valence, neg_mul, mul_neg_iff, hq, not_lt_of_ge hq.le]

/-- On its permeant ion a population scales the signed, inside-to-outside flux. -/
theorem permeant_flux (law : Law) (m h availability scale vf inside outside voltage : ℝ) :
    flux law (permeant law) m h availability scale vf inside outside voltage =
      opening law m h * availability * constantFieldFlux seriesFactor scale vf inside outside voltage := by
  simp [flux, constantFieldFlux]; ring

theorem flux_bound (law : Law) {m h availability : ℝ}
    (hm : m ∈ Set.Icc 0 1) (hh : h ∈ Set.Icc 0 1) (ha : availability ∈ Set.Icc 0 1)
    (scale vf inside outside voltage : ℝ) :
    |flux law (permeant law) m h availability scale vf inside outside voltage| ≤
      |constantFieldFlux seriesFactor scale vf inside outside voltage| := by
  have weight := product_bounds (opening_bounded law hm hh) ha
  rw [permeant_flux, abs_mul, abs_of_nonneg weight.1]
  exact mul_le_of_le_one_left (abs_nonneg _) weight.2

theorem other_flux {law : Law} {ion : Ion} (off : ion ≠ permeant law)
    (m h availability scale vf inside outside voltage : ℝ) :
    flux law ion m h availability scale vf inside outside voltage = 0 := by simp [flux, off]

theorem blocked (law : Law) (ion : Ion) (m h scale vf inside outside voltage : ℝ) :
    flux law ion m h 0 scale vf inside outside voltage = 0 := by simp [flux, flux_blocked]

/-- A single patch debits its cell (false) and credits its exterior (true) by the same
signed permeant flux. At a held exterior the reservoir supply offsets that credit. -/
theorem patch_booking (law : Law) (m h availability scale vf inside outside voltage : ℝ) :
    let j := flux law (permeant law) m h availability scale vf inside outside voltage
    let change := Accounting.nodeChange (fun _ : Unit => false) (fun _ => true) (fun _ => j)
    let full := constantFieldFlux seriesFactor scale vf inside outside voltage
    (change false, change true) = (-(opening law m h * availability * full),
      opening law m h * availability * full) := by
  simp [Accounting.nodeChange, permeant_flux]

end

end CellsProofs.Transport.IonChannels
