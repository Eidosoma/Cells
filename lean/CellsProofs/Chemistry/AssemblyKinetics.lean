import CellsProofs.Chemistry.AssemblyMixing
import CellsProofs.Chemistry.GardCatalysis
import CellsProofs.Chemistry.SingleSiteBinding

/-! # Stochastic encounters and common-state catalysis in assembly reactions -/

namespace CellsProofs.Chemistry.AssemblyKinetics

open CellsProofs.Chemistry.ReservoirExchange (size logFactorial)
open CellsProofs.Chemistry.AssemblyMixing (site)
open CellsProofs.Chemistry.GardCatalysis (weighted)

noncomputable section

variable {S : Type*} [Fintype S]

/-- The engine's coefficient counts ordered draws without replacement. -/
theorem repeated_pair (n : ℕ) : n.descFactorial 2 = n * (n - 1) := by
  rw [Nat.descFactorial_succ, Nat.descFactorial_one, Nat.mul_comm]

/-- For a distinct pair with one R molecule, the association rate from the unbound state
scales with the number of G partners. Its occupancy can be predicted from the one-partner
probability alone, eliminating the common chamber volume and dissociation constant. -/
theorem occupancy_by_count (n : ℕ) (c kd : ℝ) (hc : 0 < c) (hk : 0 < kd) :
    let p := SingleSite.occupancy c kd
    SingleSite.occupancy ((n : ℝ) * c) kd = n * p / (1 - p + n * p) := by
  dsimp only [SingleSite.occupancy]
  have den : 1 - c / (kd + c) + n * (c / (kd + c)) = (kd + n * c) / (kd + c) := by
    field_simp
  rw [den]
  field_simp

theorem log_draw (u a : ℕ) :
    Real.log ((u + a).descFactorial a : ℝ) = logFactorial (u + a) - logFactorial u := by
  have h := Nat.factorial_mul_descFactorial (n := u + a) (k := a) (by omega)
  rw [show u + a - a = u by omega] at h
  have prod : (u.factorial : ℝ) * ((u + a).descFactorial a : ℝ) = ((u + a).factorial : ℝ) := by
    exact_mod_cast h
  have hd : (u + a).descFactorial a ≠ 0 := fun hz => by
    have := Nat.descFactorial_eq_zero_iff_lt.mp hz
    omega
  have hlog := congrArg Real.log prod
  rw [Real.log_mul (by positivity) (Nat.cast_ne_zero.mpr hd)] at hlog
  unfold logFactorial
  linarith

def memCount (mem : Finset S) (n : S → ℕ) : ℕ := ∑ i ∈ mem, n i

def idealEnergy (mem : Finset S) (c : ℕ) (μ logX : S → ℝ) (n : S → ℕ) : ℝ :=
  (∑ i, site (μ i - logX i) (n i)) - logFactorial (memCount mem n - c)

/-- u remains after drawing all reactants on this side, including any shared participant.
Membrane places have logX = 0. Held activities and the locus extent enter separately. -/
def logDraws (logX : S → ℝ) (u a : S → ℕ) : ℝ :=
  ∑ i, (Real.log ((u i + a i).descFactorial (a i) : ℝ) - (a i : ℝ) * logX i)

def logEncounter (mem : Finset S) (c : ℕ) (logX : S → ℝ) (u a : S → ℕ) : ℝ :=
  logDraws logX u a - Real.log ((memCount mem (u + a) - c).descFactorial (memCount mem a) : ℝ)

def standard (μ : S → ℝ) (a : S → ℕ) : ℝ := ∑ i, (a i : ℝ) * μ i

private theorem draws_energy (μ logX : S → ℝ) (u a : S → ℕ) :
    logDraws logX u a = (∑ i, site (μ i - logX i) (u i + a i)) -
      (∑ i, site (μ i - logX i) (u i)) - standard μ a := by
  have row (i : S) : Real.log ((u i + a i).descFactorial (a i) : ℝ) - (a i : ℝ) * logX i =
      site (μ i - logX i) (u i + a i) - site (μ i - logX i) (u i) - (a i : ℝ) * μ i := by
    rw [log_draw]
    simp only [site, Nat.cast_add]
    ring
  unfold logDraws
  simp_rw [row]
  simp only [Finset.sum_sub_distrib, standard]

/-- On a regular edge, the exact factorial draw is the change in the ideal state energy
less the standard potentials of the reactants. This holds for arbitrary integer orders. -/
theorem encounter_energy (mem : Finset S) (c : ℕ) (μ logX : S → ℝ) (u a : S → ℕ)
    (hc : c ≤ memCount mem u) :
    logEncounter mem c logX u a =
      idealEnergy mem c μ logX (u + a) - idealEnergy mem c μ logX u - standard μ a := by
  have total : memCount mem (u + a) = memCount mem u + memCount mem a := by
    simp [memCount, Finset.sum_add_distrib]
  have hn : memCount mem (u + a) - c = (memCount mem u - c) + memCount mem a := by omega
  simp only [logEncounter, draws_energy μ, idealEnergy, hn, log_draw, Pi.add_apply]
  ring

def common (n p : S → ℕ) (i : S) : ℕ := min (n i) (p i)

omit [Fintype S] in
theorem common_residual (u a b : S → ℕ) : common (u + a) (u + b) = u + common a b := by
  funext i
  simp only [common, Pi.add_apply]
  omega

/-- In exact arithmetic the cached weighted sum less the consumed counts gives the sum
on the componentwise minimum, even for a species present on both sides. -/
theorem common_weight (w : S → ℝ) (n p : S → ℕ) :
    weighted w n - weighted w (fun i => n i - common n p i) = weighted w (common n p) := by
  unfold weighted
  rw [← Finset.sum_sub_distrib]
  apply Finset.sum_congr rfl
  intro i _
  dsimp only [common]
  rw [Nat.cast_sub (min_le_left (n i) (p i))]
  ring

def catalyst (energy : S → ℝ) (m : S → ℕ) : ℝ :=
  if size m = 0 then 1 else 1 + weighted (fun i => Real.exp (energy i) - 1) m / size m

theorem empty_factor (energy : S → ℝ) (m : S → ℕ) (h : size m = 0) : catalyst energy m = 1 := by
  simp [catalyst, h]

theorem catalyst_mean (energy : S → ℝ) (m : S → ℕ) (h : size m ≠ 0) :
    catalyst energy m = weighted (fun i => Real.exp (energy i)) m / size m := by
  have shift : weighted (fun i => Real.exp (energy i) - 1) m =
      weighted (fun i => Real.exp (energy i)) m - size m := by
    simp [weighted, size, sub_mul, Finset.sum_sub_distrib]
  rw [catalyst, if_neg h, shift]
  field_simp [Nat.cast_ne_zero.mpr h]

theorem catalyst_pos (energy : S → ℝ) (m : S → ℕ) : 0 < catalyst energy m := by
  by_cases h : size m = 0
  · simp [empty_factor energy m h]
  rw [catalyst_mean energy m h]
  apply div_pos _ (by exact_mod_cast Nat.pos_of_ne_zero h)
  obtain ⟨i, hi, hm⟩ := Finset.exists_ne_zero_of_sum_ne_zero (by simpa [size] using h : ∑ j, m j ≠ 0)
  exact Finset.sum_pos' (fun j _ => mul_nonneg (Real.exp_pos _).le (Nat.cast_nonneg _))
    ⟨i, hi, mul_pos (Real.exp_pos _) (by exact_mod_cast Nat.pos_of_ne_zero hm)⟩

/-- One stationary molecule gives its own Boltzmann multiplier exactly. -/
theorem single_contact [DecidableEq S] (energy : S → ℝ) (i : S) :
    catalyst energy (ReservoirExchange.addOne (fun _ => 0) i) = Real.exp (energy i) := by
  have hn : size (ReservoirExchange.addOne (fun _ => 0) i) = 1 := by
    rw [ReservoirExchange.size_addOne]
    simp [size]
  rw [catalyst_mean _ _ (by omega), hn, Nat.cast_one, div_one, GardCatalysis.weighted_addOne]
  simp [weighted]

omit [Fintype S] in
private theorem common_comm (n p : S → ℕ) : common p n = common n p := by
  funext i
  exact min_comm _ _

/-- A positive multiplier evaluated on the same composition preserves the rate ratio. -/
theorem shared_ratio (energy : S → ℝ) (n p : S → ℕ) (forward reverse : ℝ) :
    (forward * catalyst energy (common n p)) / (reverse * catalyst energy (common p n)) =
      forward / reverse := by
  rw [common_comm n p, mul_div_mul_right _ _ (catalyst_pos energy _).ne']

/-- The same equilibrium weights balance each edge after catalysis whenever they did before. -/
theorem equilibrium_flow_iff (energy : S → ℝ) (n p : S → ℕ) (w v f r : ℝ) :
    w * (f * catalyst energy (common n p)) = v * (r * catalyst energy (common p n)) ↔
      w * f = v * r := by
  rw [common_comm n p, ← mul_assoc, ← mul_assoc, mul_left_inj' (catalyst_pos energy _).ne']

/-- On a positive two-way edge, equality of the two multipliers is also necessary. -/
theorem ratio_iff (f r g h : ℝ) (hf : 0 < f) (hr : 0 < r) (hh : 0 < h) :
    (f * g) / (r * h) = f / r ↔ g = h := by
  rw [div_eq_div_iff (mul_ne_zero hr.ne' hh.ne') hr.ne']
  constructor
  · intro he
    apply mul_left_cancel₀ (mul_ne_zero hf.ne' hr.ne' : f * r ≠ 0)
    calc f * r * g = f * g * r := by ring
         _ = f * (r * h) := he
         _ = f * r * h := by ring
  · rintro rfl
    ring

/-- Log forward rate minus log reverse rate is initial energy minus final energy plus
held-reservoir work. base is the shared log rate constant and log locus extent. -/
theorem pair_heat (mem : Finset S) (c : ℕ) (μ logX energy : S → ℝ) (u a b : S → ℕ)
    (hc : c ≤ memCount mem u) (excess : (S → ℕ) → ℝ) (base heldF heldR heldStd : ℝ) :
    let n := u + a
    let p := u + b
    (base + Real.log (catalyst energy (common n p)) + logEncounter mem c logX u a + heldF) -
      (base + Real.log (catalyst energy (common p n)) + (standard μ b - standard μ a + heldStd) +
        logEncounter mem c logX u b + heldR + (excess p - excess n)) =
      (idealEnergy mem c μ logX n + excess n) - (idealEnergy mem c μ logX p + excess p) +
        (heldF - heldR - heldStd) := by
  dsimp only
  rw [common_comm (u + a) (u + b), encounter_energy mem c μ logX u a hc,
    encounter_energy mem c μ logX u b hc]
  ring

/-- The common extent cancels the final draw on the ordinary branch when no membrane
reactant remains on both sides. M = N - c and the order is k + 1. -/
theorem membrane_cancel (M k : ℕ) (hk : k < M) :
    ((M - k : ℕ) : ℝ) / (M.descFactorial (k + 1) : ℝ) = 1 / (M.descFactorial k : ℝ) := by
  have h : ((M - k : ℕ) : ℝ) ≠ 0 := Nat.cast_ne_zero.mpr (by omega)
  rw [Nat.descFactorial_succ, Nat.cast_mul, mul_comm]
  simpa only [one_mul] using (mul_div_mul_right (1 : ℝ) (M.descFactorial k : ℝ) h)

/-- At N = k+1 under c = 1, consuming all k+1 membrane reactants cancels one draw.
The remaining denominator is k!, including 0! = 1 for the last molecule. -/
theorem last_draw (k : ℕ) :
    k.descFactorial (k + 1) = 0 ∧ k.descFactorial k = k.factorial ∧ 0 < k.descFactorial k := by
  exact ⟨Nat.descFactorial_of_lt (by omega), Nat.descFactorial_self _, by
    rw [Nat.descFactorial_self]; exact Nat.factorial_pos _⟩

/-- Under c = 1, if the common membrane is empty and this side draws all its membrane
molecules, the engine uses the cancelled denominator (r-1)! for r ≥ 1. This gives the
same state-energy identity, including the singleton case. -/
theorem boundary_encounter_energy (mem : Finset S) (μ logX : S → ℝ) (u a : S → ℕ)
    (hu : memCount mem u = 0) (r : ℕ) (ha : memCount mem a = r + 1) :
    logDraws logX u a - Real.log (r.descFactorial r : ℝ) =
      idealEnergy mem 1 μ logX (u + a) - idealEnergy mem 1 μ logX u - standard μ a := by
  have hn : memCount mem (u + a) = r + 1 := by
    simpa [memCount, Finset.sum_add_distrib] using (show memCount mem u + memCount mem a = r + 1 by
      rw [hu, ha, Nat.zero_add])
  simp only [draws_energy μ, idealEnergy, Pi.add_apply, hu, hn, Nat.zero_sub, Nat.add_sub_cancel,
    Nat.descFactorial_self, logFactorial, Nat.factorial_zero, Nat.cast_one, Real.log_one]
  ring

/-- With a shared membrane participant the extent numerator is positive at N = r,
while the direction's full falling-factorial denominator is zero under c = 1. -/
theorem singular_draw (r consumed : ℕ) (shared : consumed < r) :
    (r - 1).descFactorial r = 0 ∧ 0 < r - consumed := by
  exact ⟨Nat.descFactorial_of_lt (by omega), by omega⟩

end

end CellsProofs.Chemistry.AssemblyKinetics
