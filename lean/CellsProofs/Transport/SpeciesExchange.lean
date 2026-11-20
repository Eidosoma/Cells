import Mathlib.Analysis.SpecialFunctions.Log.Deriv
import Mathlib.Analysis.Calculus.MeanValue
import Mathlib.Topology.Order.IntermediateValue
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Ring

/-! # Saturable uptake from a finite extracellular pool

Cells uses an initial amount n, saturation amount b = K_M V and dose d = A V_max h.
The logarithmic change u gives a remaining amount n exp(u). All arithmetic here is real.
-/

namespace CellsProofs.Transport.SpeciesExchange

noncomputable section

/-- Left side of the integrated uptake equation in the engine's log coordinate. -/
def spent (n b u : ℝ) : ℝ := -b * u + n * (1 - Real.exp u)

/-- At fixed volume, b = K_M V converts the amount law back to the measured
concentration response. The capacity a already includes the patch area. -/
theorem concentration_rate (a c km : ℝ) {volume : ℝ} (hv : 0 < volume) :
    a * (volume * c) / (km * volume + volume * c) = a * c / (km + c) := by
  rw [show km * volume + volume * c = (km + c) * volume by ring,
    show a * (volume * c) = (a * c) * volume by ring, mul_div_mul_right _ _ hv.ne']

/-- Along the Michaelis–Menten depletion ODE, the primitive decreases at the
constant rate a. The logarithm uses the fixed fmol unit of the amount. -/
theorem primitive_rate {y : ℝ → ℝ} {a b t : ℝ} (hn : 0 < y t) (hb : 0 < b)
    (hy : HasDerivAt y (-a * y t / (b + y t)) t) :
    HasDerivAt (fun s => y s + b * Real.log (y s)) (-a) t := by
  convert hy.add ((hy.log hn.ne').const_mul b) using 1
  field_simp [hn.ne', (add_pos hb hn).ne']
  ring

theorem integrated_equation {n : ℝ} (hn : 0 < n) (b u : ℝ) :
    b * Real.log (n / (n * Real.exp u)) + (n - n * Real.exp u) = spent n b u := by
  rw [Real.log_div hn.ne' (mul_pos hn (Real.exp_pos _)).ne',
    Real.log_mul hn.ne' (Real.exp_pos _).ne', Real.log_exp, spent]
  ring

private theorem spent_decreases {n b : ℝ} (hn : 0 < n) (hb : 0 < b) :
    StrictAnti (spent n b) := by
  intro u v huv
  unfold spent
  linarith [mul_lt_mul_of_pos_left huv hb,
    mul_lt_mul_of_pos_left (Real.exp_lt_exp.mpr huv) hn]

/-- The engine starts Newton iteration at the right endpoint of this bracket. -/
theorem root_bracket {n b d : ℝ} (hn : 0 < n) (hb : 0 < b) (hd : 0 ≤ d) :
    ∃ r ∈ Set.Icc (-d / b) (-d / (b + n)), spent n b r = d := by
  have hc := add_pos hb hn
  have order : -d / b ≤ -d / (b + n) := by
    apply (div_le_div_iff₀ hb hc).2
    nlinarith [mul_nonneg hd hn.le]
  have low : d ≤ spent n b (-d / b) := by
    have h := Real.exp_le_one_iff.mpr (div_nonpos_of_nonpos_of_nonneg (neg_nonpos.mpr hd) hb.le)
    have e : -b * (-d / b) = d := by field_simp
    rw [spent, e]
    linarith [mul_nonneg hn.le (sub_nonneg.mpr h)]
  have high : spent n b (-d / (b + n)) ≤ d := by
    let u := -d / (b + n)
    have e : u * (b + n) = -d := div_mul_cancel₀ _ hc.ne'
    have h := mul_le_mul_of_nonneg_left (Real.add_one_le_exp u) hn.le
    change -b * u + n * (1 - Real.exp u) ≤ d
    linarith
  apply intermediate_value_Icc' order _ ⟨high, low⟩
  exact (continuous_const.mul continuous_id |>.add
    (continuous_const.mul (continuous_const.sub Real.continuous_exp))).continuousOn

theorem unique_root {n b d : ℝ} (hn : 0 < n) (hb : 0 < b) (hd : 0 ≤ d) :
    ∃! r, spent n b r = d := by
  obtain ⟨r, _, hr⟩ := root_bracket hn hb hd
  exact ⟨r, hr, fun _ h => (spent_decreases hn hb).injective (h.trans hr.symm)⟩

/-- Existence and uniqueness in the measured variable, the amount left outside. -/
theorem unique_remainder {n b d : ℝ} (hn : 0 < n) (hb : 0 < b) (hd : 0 ≤ d) :
    ∃! q, 0 < q ∧ b * Real.log (n / q) + (n - q) = d := by
  obtain ⟨r, hr, unique⟩ := unique_root hn hb hd
  refine ⟨n * Real.exp r, ⟨mul_pos hn (Real.exp_pos _), (integrated_equation hn b r).trans hr⟩, ?_⟩
  rintro q ⟨hq, balance⟩
  let u := Real.log (q / n)
  have amount : n * Real.exp u = q := by
    rw [show Real.exp u = q / n from Real.exp_log (div_pos hq hn)]
    field_simp
  have h : spent n b u = d := by rwa [← integrated_equation hn b u, amount]
  rw [← unique u h, amount]

/-- The cell gains the same amount the outside loses. At any nonnegative dose
the source retains a positive amount, including at zero dose. -/
theorem finite_pool_booking {n b d u : ℝ} (hn : 0 < n) (hb : 0 < b) (hd : 0 ≤ d)
    (hu : spent n b u = d) (cell : ℝ) :
    let moved := n * (1 - Real.exp u)
    0 ≤ moved ∧ moved < n ∧ n - moved = n * Real.exp u ∧
      (n - moved) + (cell + moved) = n + cell := by
  obtain ⟨r, h, hr⟩ := root_bracket hn hb hd
  have eq : u = r := (spent_decreases hn hb).injective (hu.trans hr.symm)
  have hu0 := eq ▸ h.2.trans (div_nonpos_of_nonpos_of_nonneg (neg_nonpos.mpr hd) (add_pos hb hn).le)
  dsimp only
  constructor
  · exact mul_nonneg hn.le (sub_nonneg.mpr (Real.exp_le_one_iff.mpr hu0))
  exact ⟨by linarith [mul_pos hn (Real.exp_pos u)], by ring, by ring⟩

/-- Two consecutive exact stages on the same static route accumulate their doses. -/
theorem compose_stages (n b u v : ℝ) :
    spent n b (u + v) = spent n b u + spent (n * Real.exp u) b v := by
  rw [spent, spent, spent, Real.exp_add]
  ring

/-- For two simultaneous routes with the same K_M on a shared pool, a
recipient's gain is its capacity fraction of total depletion. The engine
applies its routes successively within each symmetric split step. -/
theorem shared_pool_allocation {pool cell : ℝ → ℝ} {a k b t : ℝ} (ht : 0 ≤ t)
    (hp : ∀ s ∈ Set.Icc 0 t, HasDerivAt pool (-(a + k) * pool s / (b + pool s)) s)
    (hc : ∀ s ∈ Set.Icc 0 t, HasDerivAt cell (a * pool s / (b + pool s)) s) :
    (a + k) * (cell t - cell 0) = a * (pool 0 - pool t) := by
  let f := fun s => (a + k) * cell s + a * pool s
  have hf (s) (hs : s ∈ Set.Icc 0 t) : HasDerivWithinAt f 0 (Set.Icc 0 t) s := by
    apply HasDerivAt.hasDerivWithinAt
    convert ((hc s hs).const_mul (a + k)).add ((hp s hs).const_mul a) using 1
    ring
  have bound := (convex_Icc (0 : ℝ) t).norm_image_sub_le_of_norm_hasDerivWithin_le
    hf (C := 0) (by simp) (Set.left_mem_Icc.mpr ht) (Set.right_mem_Icc.mpr ht)
  have eq : f t - f 0 = 0 := norm_le_zero_iff.mp (by simpa using bound)
  unfold f at eq
  linarith

def newton (n b d u : ℝ) : ℝ :=
  u + (spent n b u - d) / (b + n * Real.exp u)

/-- Starting on the right of the root, the tangent update stays on that
side and takes a nonpositive step. This holds at each of the eight iterations. -/
theorem newton_bounds {n b d r u : ℝ} (hn : 0 < n) (hb : 0 < b)
    (hr : spent n b r = d) (hru : r ≤ u) : r ≤ newton n b d u ∧ newton n b d u ≤ u := by
  have den := add_pos hb (mul_pos hn (Real.exp_pos u))
  have tangent : Real.exp u * ((r - u) + 1) ≤ Real.exp r := by
    calc
      _ ≤ Real.exp u * Real.exp (r - u) :=
        mul_le_mul_of_nonneg_left (Real.add_one_le_exp _) (Real.exp_pos _).le
      _ = Real.exp r := by rw [← Real.exp_add]; congr 1; ring
  have lower : (r - u) * (b + n * Real.exp u) ≤ spent n b u - d := by
    rw [← hr, spent, spent]
    linarith [mul_le_mul_of_nonneg_left tangent hn.le]
  have upper := (spent_decreases hn hb).antitone hru
  unfold newton
  constructor
  · linarith [(le_div_iff₀ den).mpr lower]
  · linarith [div_nonpos_of_nonpos_of_nonneg (sub_nonpos.mpr (upper.trans_eq hr)) den.le]

/-- Every finite iteration from the actual initializer stays inside the bracket. -/
theorem iterate_bounds {n b d : ℝ} (hn : 0 < n) (hb : 0 < b) (hd : 0 ≤ d) (i : ℕ) :
    ∃ r, spent n b r = d ∧ (newton n b d)^[i] (-d / (b + n)) ∈ Set.Icc r (-d / (b + n)) := by
  obtain ⟨r, h, hr⟩ := root_bracket hn hb hd
  refine ⟨r, hr, ?_⟩
  induction i with
  | zero => exact ⟨h.2, le_rfl⟩
  | succ i ih =>
    rw [Function.iterate_succ_apply']
    have step := newton_bounds hn hb hr ih.1
    exact ⟨step.1, step.2.trans ih.2⟩

/-- The true absolute equation residual bounds the absolute remaining-amount
error in fmol for any trial log change, including a trial on either side. -/
theorem amount_error_le_residual {n b d r : ℝ} (hn : 0 < n) (hb : 0 < b)
    (hr : spent n b r = d) (u : ℝ) :
    |n * Real.exp u - n * Real.exp r| ≤ |spent n b u - d| := by
  rw [← hr]
  rcases le_total r u with h | h
  · have he := mul_le_mul_of_nonneg_left (Real.exp_le_exp.mpr h) hn.le
    rw [abs_of_nonneg (sub_nonneg.mpr he), abs_of_nonpos (sub_nonpos.mpr ((spent_decreases hn hb).antitone h))]
    unfold spent
    linarith [mul_le_mul_of_nonneg_left h hb.le]
  · have he := mul_le_mul_of_nonneg_left (Real.exp_le_exp.mpr h) hn.le
    rw [abs_of_nonpos (sub_nonpos.mpr he), abs_of_nonneg (sub_nonneg.mpr ((spent_decreases hn hb).antitone h))]
    unfold spent
    linarith [mul_le_mul_of_nonneg_left h hb.le]

end

end CellsProofs.Transport.SpeciesExchange
