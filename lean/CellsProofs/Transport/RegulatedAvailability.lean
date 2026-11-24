import CellsProofs.Chemistry.SpeciesTurnover
import Mathlib.Analysis.SpecialFunctions.Log.Deriv

/-! # Availability controlled by a molecular input

During a regulatory half-step the opening rate `a = k_on * u` is held
fixed, where `u` is the product of the Hill inputs. The closing rate is `b`.
Versions 1 and 2 share this stage and the basal availability rule. Version 2
can also multiply a scheduled operator rate at each of its target's half-steps.
-/

namespace CellsProofs.Transport.RegulatedAvailability

open CellsProofs.Chemistry.SpeciesTurnover

noncomputable section

def step (s a b h : ℝ) := amount s a (a + b) h
def plateau (a b : ℝ) := a / (a + b)
def tau (a b : ℝ) := 1 / (a + b)

def phi (x : ℝ) := if 0 < x then (1 - Real.exp (-x)) / x else 1

/-- The engine's increment and zero-rate branch give the turnover solution. -/
theorem half_step_eq (s : ℝ) {a b h : ℝ} (ha : 0 ≤ a) (hb : 0 ≤ b) (hh : 0 ≤ h) :
    (if 0 < a + b then s + (a * (1 - s) - b * s) * h * phi ((a + b) * h) else s)
      = step s a b h := by
  rcases (add_nonneg ha hb).eq_or_lt with hz | hp
  · have az : a = 0 := by linarith
    have bz : b = 0 := by linarith
    simp [az, bz, step, amount, exposure, survival]
  by_cases ht : h = 0
  · simp [ht, step, initial_amount]
  have hx := mul_pos hp (lt_of_le_of_ne hh (Ne.symm ht))
  simp only [if_pos hp, step, amount, phi, if_pos hx, exposure, if_neg hp.ne', survival]
  field_simp [hp.ne', ht]
  ring

theorem state_derivative (s a b t : ℝ) :
    HasDerivAt (step s a b) (a * (1 - step s a b t) - b * step s a b t) t := by
  convert amount_derivative s a (a + b) t using 1
  unfold step
  ring

/-- A held dose approaches its plateau from the starting side. -/
theorem no_overshoot (s : ℝ) {a b h : ℝ} (hp : 0 < a + b) (hh : 0 ≤ h) :
    step s a b h ∈ Set.Icc (min s (plateau a b)) (max s (plateau a b)) := by
  have he : 0 ≤ survival (a + b) h := (Real.exp_pos _).le
  have hw : 0 ≤ 1 - survival (a + b) h :=
    sub_nonneg.mpr (Real.exp_le_one_iff.mpr (neg_nonpos.mpr (mul_nonneg hp.le hh)))
  have hn : step s a b h - s = (plateau a b - s) * (1 - survival (a + b) h) :=
    net_change s a h hp.ne'
  have hr : step s a b h - plateau a b = (s - plateau a b) * survival (a + b) h :=
    equilibrium_offset s a h hp.ne'
  rcases le_total s (plateau a b) with hs | hs
  · rw [min_eq_left hs, max_eq_right hs]
    exact ⟨sub_nonneg.mp (hn.symm ▸ mul_nonneg (sub_nonneg.mpr hs) hw),
      sub_nonpos.mp (hr.symm ▸ mul_nonpos_of_nonpos_of_nonneg (sub_nonpos.mpr hs) he)⟩
  · rw [min_eq_right hs, max_eq_left hs]
    exact ⟨sub_nonneg.mp (hr.symm ▸ mul_nonneg (sub_nonneg.mpr hs) he),
      sub_nonpos.mp (hn.symm ▸ mul_nonpos_of_nonpos_of_nonneg (sub_nonpos.mpr hs) hw)⟩

theorem state_bounds {s a b h : ℝ} (hs : s ∈ Set.Icc 0 1)
    (ha : 0 ≤ a) (hb : 0 ≤ b) (hh : 0 ≤ h) : step s a b h ∈ Set.Icc 0 1 := by
  rcases (add_nonneg ha hb).eq_or_lt with hz | hp
  · rw [← half_step_eq s ha hb hh, if_neg (by linarith)]
    exact hs
  obtain ⟨lo, hi⟩ := no_overshoot s hp hh
  have pq : plateau a b ≤ 1 := (div_le_one hp).mpr (by linarith)
  exact ⟨le_trans (le_min hs.1 (div_nonneg ha hp.le)) lo,
    le_trans hi (max_le hs.2 pq)⟩

theorem constant_input_split (s a b h t : ℝ) :
    step (step s a b h) a b t = step s a b (h + t) := (compose_stages s a (a + b) h t).1

theorem washout (s b h : ℝ) : step s 0 b h = s * Real.exp (-(b * h)) := by
  simp [step, amount, survival]

/-- An absolute plateau and the relaxation time jointly identify the off-rate. -/
theorem timing_identity {a b : ℝ} (ha : 0 ≤ a) (hb : 0 < b) :
    tau a b = (1 - plateau a b) * tau 0 b := by
  have hp := (add_pos_of_nonneg_of_pos ha hb).ne'
  simp only [tau, plateau, zero_add]
  field_simp [hp, hb.ne']

/-- With x = (c/K)^n, the steady response is also a Hill curve, with a lower
maximum and a different half-saturation from the opening-rate input. -/
theorem steady_hill {onRate offRate x : ℝ} (hon : 0 < onRate) (hoff : 0 < offRate)
    (hx : 0 ≤ x) :
    plateau (onRate * (x / (1 + x))) offRate =
      plateau onRate offRate * x / ((1 - plateau onRate offRate) + x) := by
  have hsum := add_pos hon hoff
  have hmax : plateau onRate offRate < 1 := (div_lt_one hsum).mpr (by linarith)
  have hden := add_pos_of_pos_of_nonneg (sub_pos.mpr hmax) hx
  unfold plateau at *
  have h1 : 0 < 1 + x := by positivity
  have h2 : 0 < onRate * (x / (1 + x)) + offRate := by positivity
  apply (div_eq_div_iff h2.ne' hden.ne').mpr
  field_simp [h1.ne', hsum.ne']
  ring

def route (enabled : Bool) (basal f : ℝ) := if enabled then basal + (1 - basal) * f else 1

theorem route_bounds (enabled : Bool) {basal f : ℝ} (hb : basal ∈ Set.Icc 0 1)
    (hf : f ∈ Set.Icc 0 1) : route enabled basal f ∈ Set.Icc basal 1 := by
  cases enabled
  · exact ⟨hb.2, le_rfl⟩
  · simp only [route, if_true, Bool.true_eq, Set.mem_Icc]
    exact ⟨le_add_of_nonneg_right (mul_nonneg (sub_nonneg.mpr hb.2) hf.1),
      by nlinarith only [mul_nonneg (sub_nonneg.mpr hb.2) (sub_nonneg.mpr hf.2)]⟩

theorem route_mono (enabled : Bool) {basal x y : ℝ} (hb : basal ≤ 1) (hxy : x ≤ y) :
    route enabled basal x ≤ route enabled basal y := by
  cases enabled
  · exact le_rfl
  · exact add_le_add_left (mul_le_mul_of_nonneg_left hxy (sub_nonneg.mpr hb)) _

/-- Multiple routes on an element preserve the bounds on its scheduled rate. -/
theorem routed_rate_bounds (factors : List ℝ) {rate : ℝ} (hr : 0 ≤ rate)
    (hf : ∀ f ∈ factors, f ∈ Set.Icc 0 1) : rate * factors.prod ∈ Set.Icc 0 rate := by
  have prod_bounds : factors.prod ∈ Set.Icc (0 : ℝ) 1 := by
    induction factors with
    | nil => simp
    | cons f fs ih =>
      have a := hf f (List.mem_cons_self ..)
      have b := ih (fun x hx => hf x (List.mem_cons_of_mem _ hx))
      exact ⟨mul_nonneg a.1 b.1, by simpa using mul_le_mul a.2 b.2 b.1 zero_le_one⟩
  exact ⟨mul_nonneg hr prod_bounds.1, by simpa using mul_le_mul_of_nonneg_left prod_bounds.2 hr⟩

/-- For a production route, using the first multiplier again in the second
half misses this signed amount of gross production. -/
theorem reread_production (p h first second : ℝ) :
    (p * first * h + p * second * h) - 2 * p * first * h = p * h * (second - first) := by
  ring

/-- A unit-volume cell produces its regulator at one unit per time from c(0) = 1.
The factor on reporter production is the activating Hill law with K = n = 1. -/
def rampGate (t : ℝ) := (1 + t) / (2 + t)

theorem ramp_reference {t : ℝ} (ht : 0 ≤ t) :
    HasDerivAt (fun z : ℝ => z - (Real.log (2 + z) - Real.log 2)) (rampGate t) t := by
  have hd := ((hasDerivAt_id t).const_add 2).log (by dsimp; positivity)
  convert (hasDerivAt_id t).sub (hd.sub_const (Real.log 2)) using 1
  unfold rampGate
  field_simp
  ring

theorem ramp_panel_difference {t h : ℝ} (ht : 0 ≤ t) (hh : 0 ≤ h) :
    h / 2 * (rampGate t + rampGate (t + h / 2)) - h * rampGate t =
      h ^ 2 / (4 * (2 + t) * (2 + (t + h / 2))) := by
  unfold rampGate
  have ha : 2 + t ≠ 0 := by positivity
  have hb : 2 + (t + h / 2) ≠ 0 := by positivity
  field_simp [ha, hb]
  ring

/-- Over one unit of time, halving every target stage changes the accumulated
reporter by at least h/36. Thus these left-endpoint bookings cannot converge
with global error O(h²) on this admitted, smoothly varying input. -/
theorem ramp_refinement_lower (n : ℕ) {h : ℝ} (hh : 0 ≤ h) (span : (n : ℝ) * h = 1) :
    h / 36 ≤ ∑ j ∈ Finset.range n,
      (h / 2 * (rampGate (j * h) + rampGate (j * h + h / 2)) - h * rampGate (j * h)) := by
  calc
    h / 36 = ((n : ℝ) * h) * h / 36 := by rw [span, one_mul]
    _ = ∑ _j ∈ Finset.range n, h ^ 2 / 36 := by simp; ring
    _ ≤ _ := by
      apply Finset.sum_le_sum
      intro j hj
      have hjn : (j : ℝ) + 1 ≤ (n : ℝ) := by exact_mod_cast Finset.mem_range.mp hj
      have ht : 0 ≤ (j : ℝ) * h := by positivity
      have hend := mul_le_mul_of_nonneg_right hjn hh
      rw [add_mul, one_mul, span] at hend
      rw [ramp_panel_difference ht hh]
      apply div_le_div_of_nonneg_left (sq_nonneg h) (by positivity)
      calc
        4 * (2 + (j : ℝ) * h) * (2 + ((j : ℝ) * h + h / 2)) ≤ (4 * 3) * 3 := by
          gcongr <;> linarith
        _ = 36 := by norm_num

/-- With the self-moved source read at the midpoint, the same refinement has a cubic
panel difference. This compares one target stage with two equal target stages. -/
theorem ramp_midpoint_difference {t h : ℝ} (ht : 0 ≤ t) (hh : 0 ≤ h) :
    h * rampGate (t + h / 2) - h / 2 * (rampGate (t + h / 4) + rampGate (t + 3 * h / 4)) =
      h ^ 3 / (16 * (2 + (t + h / 4)) * (2 + (t + h / 2)) * (2 + (t + 3 * h / 4))) := by
  unfold rampGate
  have ha : 2 + (t + h / 4) ≠ 0 := by positivity
  have hb : 2 + (t + h / 2) ≠ 0 := by positivity
  have hc : 2 + (t + 3 * h / 4) ≠ 0 := by positivity
  field_simp [ha, hb, hc]
  ring

/-- For a rising response, the time between 20% and 80% of the excursion is
`log 4` times the relaxation time. A common positive closing rate bounds this
interval using the zero-input washout time, even when the plateau is unknown. -/
theorem rise_20_80 {s a b t20 t80 : ℝ} (ha : 0 ≤ a) (hb : 0 < b)
    (hs : s < plateau a b)
    (h20 : step s a b t20 = s + (1 / 5 : ℝ) * (plateau a b - s))
    (h80 : step s a b t80 = s + (4 / 5 : ℝ) * (plateau a b - s)) :
    t80 - t20 = Real.log 4 * tau a b ∧ t80 - t20 ≤ Real.log 4 * tau 0 b := by
  have hp := add_pos_of_nonneg_of_pos ha hb
  have remaining (t f : ℝ) (ht : step s a b t = s + f * (plateau a b - s)) :
      Real.exp (-((a + b) * t)) = 1 - f := by
    have h : step s a b t - plateau a b =
        (s - plateau a b) * Real.exp (-((a + b) * t)) := equilibrium_offset s a t hp.ne'
    apply mul_left_cancel₀ (sub_ne_zero.mpr hs.ne)
    rw [← h, ht]
    ring
  have hratio : Real.exp ((a + b) * (t80 - t20)) = 4 := by
    rw [show (a + b) * (t80 - t20) = -((a + b) * t20) - (-((a + b) * t80)) by ring,
      Real.exp_sub, remaining _ _ h20, remaining _ _ h80]
    norm_num
  have elapsed := congrArg Real.log hratio
  rw [Real.log_exp] at elapsed
  have interval : t80 - t20 = Real.log 4 * tau a b := by
    rw [tau, mul_one_div, eq_div_iff hp.ne', mul_comm]
    exact elapsed
  refine ⟨interval, interval.le.trans ?_⟩
  apply mul_le_mul_of_nonneg_left _ (Real.log_nonneg (by norm_num))
  simpa [tau] using one_div_le_one_div_of_le hb (show b ≤ a + b by linarith)

end

end CellsProofs.Transport.RegulatedAvailability
