import CellsProofs.Transport.OsmoticWater
import Mathlib.Analysis.SpecialFunctions.Trigonometric.Basic
import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Positivity

/-! # Bilayer area and the osmotic volume of a closed vesicle

The model caps volume at the sphere with the given area. Volumes use a single
unit and external osmolarity is expressed as particles per unit volume.
-/

namespace CellsProofs.Chemistry.Vesicle

open scoped BigOperators

noncomputable section

variable {S : Type*} [Fintype S]

def footprint (count weight : S → ℕ) : ℕ := ∑ i, count i * weight i

def area (q : ℝ) (w : ℕ) := q * w / 2

theorem footprint_add (a b k : S → ℕ) :
    footprint (fun i => a i + b i) k = footprint a k + footprint b k := by
  simp [footprint, add_mul, Finset.sum_add_distrib]

/-- Refining the unit scales the exact integer footprint by the same factor. -/
theorem footprint_refine (count weight : S → ℕ) (r : ℕ) :
    footprint count (fun i => r * weight i) = r * footprint count weight := by
  simp only [footprint, Finset.mul_sum]
  exact Finset.sum_congr rfl (fun i _ => by ring)

theorem area_refine (count weight : S → ℕ) (r : ℕ) {q q' : ℝ} (scale : q' * r = q) :
    area q' (footprint count (fun i => r * weight i)) = area q (footprint count weight) := by
  rw [footprint_refine, area, area, Nat.cast_mul, ← mul_assoc, scale]

/-- Per-molecule area uncertainty accumulates with lipid count and is shared by two leaflets. -/
theorem area_error_bound (count weight : S → ℕ) (measured : S → ℝ) (q error : ℝ)
    (bound : ∀ i, |q * (weight i : ℝ) - measured i| ≤ error) :
    |area q (footprint count weight) - (∑ i, (count i : ℝ) * measured i) / 2| ≤
      (∑ i, (count i : ℝ)) * error / 2 := by
  have diff : q * (footprint count weight : ℝ) - ∑ i, (count i : ℝ) * measured i =
      ∑ i, (count i : ℝ) * (q * (weight i : ℝ) - measured i) := by
    simp [footprint, Finset.mul_sum, mul_sub, Finset.sum_sub_distrib,
      mul_comm, mul_left_comm, mul_assoc]
  rw [area, ← sub_div, diff, abs_div, abs_of_pos (by norm_num : (0 : ℝ) < 2)]
  apply div_le_div_of_nonneg_right _ (by norm_num)
  apply (Finset.abs_sum_le_sum_abs _ _).trans
  rw [Finset.sum_mul]
  apply Finset.sum_le_sum
  intro i _
  rw [abs_mul, abs_of_nonneg (Nat.cast_nonneg _)]
  exact mul_le_mul_of_nonneg_left (bound i) (Nat.cast_nonneg _)

def radius (a : ℝ) := Real.sqrt (a / (4 * Real.pi))

def sphere (a : ℝ) := a * radius a / 3

theorem radius_area {a : ℝ} (ha : 0 ≤ a) : 4 * Real.pi * radius a ^ 2 = a := by
  unfold radius
  rw [Real.sq_sqrt (by positivity)]
  field_simp [Real.pi_ne_zero]

theorem sphere_radius {a : ℝ} (ha : 0 ≤ a) : sphere a = 4 * Real.pi * radius a ^ 3 / 3 := by
  unfold sphere
  nth_rw 1 [← radius_area ha]
  ring

/-- The engine's area-only expression for the spherical volume cap. -/
theorem sphere_area {a : ℝ} (ha : 0 ≤ a) :
    sphere a = a * Real.sqrt a / (6 * Real.sqrt Real.pi) := by
  simp only [sphere, radius, Real.sqrt_div ha, Real.sqrt_mul (by norm_num : (0 : ℝ) ≤ 4)]
  have four : Real.sqrt 4 = 2 := by
    rw [show (4 : ℝ) = 2 ^ 2 by norm_num, Real.sqrt_sq (by norm_num : (0 : ℝ) ≤ 2)]
  rw [four]
  ring

def volume (n c cap : ℝ) := min (n / c) cap

/-- Bath fluid in an invagination occupies part of the volume inside the outer contour. -/
theorem invagination_bounds {outer bathInside initial : ℝ} (hi : 0 < initial)
    (hn : 0 ≤ bathInside) (hfits : bathInside ≤ outer) :
    0 ≤ (outer - bathInside) / initial ∧ (outer - bathInside) / initial ≤ outer / initial :=
  ⟨div_nonneg (sub_nonneg.mpr hfits) hi.le, div_le_div_of_nonneg_right (sub_le_self _ hn) hi.le⟩

/-- The part of the fixed-count free energy that depends on volume. -/
def energy (n c standard v : ℝ) := -n * Real.log (standard * v) + c * v

theorem energy_gap (n c : ℝ) {standard v u : ℝ}
    (hs : 0 < standard) (hv : 0 < v) (hu : 0 < u) :
    energy n c standard v - energy n c standard u =
      n * (v / u - 1 - Real.log (v / u)) + (c - n / u) * (v - u) := by
  simp only [energy, Real.log_mul hs.ne' hv.ne', Real.log_mul hs.ne' hu.ne',
    Real.log_div hv.ne' hu.ne']
  field_simp [hu.ne']
  ring

/-- Every other feasible positive volume has higher free energy. -/
theorem energy_strict_min {n c cap standard v : ℝ} (hn : 0 < n) (hc : 0 < c)
    (hk : 0 < cap) (hs : 0 < standard) (hv : 0 < v) (hvle : v ≤ cap)
    (hne : v ≠ volume n c cap) : energy n c standard (volume n c cap) < energy n c standard v := by
  let u := volume n c cap
  have hu : 0 < u := lt_min (div_pos hn hc) hk
  have hd : v / u ≠ 1 := fun h => hne ((div_eq_one_iff_eq hu.ne').mp h)
  have hlog := Real.log_lt_sub_one_of_pos (div_pos hv hu) hd
  have hrest : 0 ≤ (c - n / u) * (v - u) := by
    rcases le_total (n / c) cap with h | h
    · have he : u = n / c := min_eq_left h
      rw [he, div_div_eq_mul_div, mul_div_cancel_left₀ _ hn.ne', sub_self, zero_mul]
    · have he : u = cap := min_eq_right h
      rw [he]
      apply mul_nonneg_of_nonpos_of_nonpos _ (sub_nonpos.mpr hvle)
      apply sub_nonpos.mpr
      exact (le_div_iff₀ hk).mpr (by simpa [mul_comm] using (le_div_iff₀ hc).mp h)
  have hgap := energy_gap n c hs hv hu
  have hpos := mul_pos hn (sub_pos.mpr hlog)
  change energy n c standard u < energy n c standard v
  linarith

theorem empty_lumen (c cap standard : ℝ) (hk : 0 ≤ cap) :
    volume 0 c cap = 0 ∧ energy 0 c standard 0 = 0 := by simp [volume, energy, hk]

/-- With the membrane slack, the ideal water-flow law stalls at the same volume. -/
theorem slack_stall {g rt n c cap : ℝ} (hg : 0 < g) (ht : 0 < rt)
    (hn : 0 < n) (hc : 0 < c) (slack : n / c ≤ cap) (p : ℝ) :
    Transport.OsmoticWater.flow g
      (Transport.OsmoticWater.potential ⟨0, p, rt * n⟩ (volume n c cap)) (p - rt * c) = 0 := by
  rw [volume, min_eq_left slack]
  exact (Transport.OsmoticWater.ideal_bath_stall hg ht hc (div_pos hn hc) n p).mpr rfl

def tension (thermal r n c cap : ℝ) := thermal * r / 2 * max 0 (n / cap - c)

theorem slack_tension {n c cap : ℝ} (hc : 0 < c) (hk : 0 < cap) (slack : n / c ≤ cap)
    (thermal r : ℝ) : tension thermal r n c cap = 0 := by
  have h := (div_le_iff₀ hc).mp slack
  have h' : n / cap ≤ c := (div_le_iff₀ hk).mpr (by simpa [mul_comm] using h)
  simp [tension, max_eq_left (sub_nonpos.mpr h')]

/-- Evaluating Laplace's pressure jump at the equilibrated volume gives the tension in both regimes. -/
theorem laplace {n c cap : ℝ} (hn : 0 < n) (hc : 0 < c) (hk : 0 < cap) (thermal r : ℝ) :
    tension thermal r n c cap = thermal * r / 2 * (n / volume n c cap - c) := by
  rcases le_total (n / c) cap with h | h
  · rw [slack_tension hc hk h, volume, min_eq_left h, div_div_eq_mul_div,
      mul_div_cancel_left₀ _ hn.ne', sub_self, mul_zero]
  · have h' : c ≤ n / cap := (le_div_iff₀ hk).mpr (by simpa [mul_comm] using (le_div_iff₀ hc).mp h)
    rw [tension, max_eq_right (sub_nonneg.mpr h'), volume, min_eq_right h]

/-- Reduced volume, relative to the sphere, after a bath change at fixed area and solute. -/
theorem reduced_volume {cap : ℝ} (hk : 0 < cap) (initial bath : ℝ) :
    volume (cap * initial) bath cap / cap = min (initial / bath) 1 := by
  unfold volume
  rw [← min_div_div_right hk.le, div_self hk.ne', mul_div_assoc, mul_div_cancel_left₀ _ hk.ne']

/-- Fix the trapped density per spherical volume. Tension scales linearly with physical radius. -/
theorem tension_at_density {cap : ℝ} (hk : 0 < cap) (thermal r initial bath : ℝ) :
    tension thermal r (cap * initial) bath cap = thermal * r / 2 * max 0 (initial - bath) := by
  rw [tension, mul_div_cancel_left₀ _ hk.ne']

/-- After a vesicle reaches its area limit, further dilution of the bath leaves volume fixed. -/
theorem capped_bath_change {n cap c₁ c₂ : ℝ} (hk : 0 ≤ cap) (h₂ : 0 < c₂)
    (lower : c₂ ≤ c₁) (full : cap ≤ n / c₁) :
    volume n c₁ cap = cap ∧ volume n c₂ cap = cap := by
  have h₁ := lt_of_lt_of_le h₂ lower
  have fits := (le_div_iff₀ h₂).mpr ((mul_le_mul_of_nonneg_left lower hk).trans
    ((le_div_iff₀ h₁).mp full))
  exact ⟨min_eq_right full, min_eq_right fits⟩

/-- A change in footprint units preserves both physical observables and every strict lysis decision. -/
theorem refinement_outcome (count weight : S → ℕ) (r : ℕ) {q q' : ℝ} (scale : q' * r = q)
    (n c thermal threshold : ℝ) :
    let a := area q (footprint count weight)
    let a' := area q' (footprint count (fun i => r * weight i))
    volume n c (sphere a') = volume n c (sphere a) ∧
      (threshold < tension thermal (radius a') n c (sphere a') ↔
       threshold < tension thermal (radius a) n c (sphere a)) := by
  dsimp only
  rw [area_refine count weight r scale]
  simp

/-- A vesicle that passed the strict threshold cannot newly rupture while every
later check sees tension at or below the original value. Its own threshold is fixed. -/
theorem no_new_rupture {Time : Type*} {initial limit : ℝ} {stress : Time → ℝ}
    (intact : ¬ limit < initial) (hold : ∀ t, stress t ≤ initial) (t : Time) :
    ¬ limit < stress t := not_lt.mpr ((hold t).trans (le_of_not_gt intact))

/-- Any time-independent surviving fraction misses at least one of two
readings by at least half their observed fall. -/
theorem fixed_survival_error (early late prediction : ℝ) :
    (early - late) / 2 ≤ max |early - prediction| |late - prediction| := by
  have h₁ := (le_abs_self (early - prediction)).trans
    (le_max_left |early - prediction| |late - prediction|)
  have h₂ := (neg_le_abs (late - prediction)).trans
    (le_max_right |early - prediction| |late - prediction|)
  linarith

/-- On two spherical headgroup surfaces, equal area per lipid is equivalent to
the inner lipid fraction equalling the inner fraction of their combined areas. -/
theorem equal_leaflet_footprint_iff {ri ro ni no : ℝ}
    (hri : 0 < ri) (hro : 0 < ro) (hni : 0 < ni) (hno : 0 < no) :
    4 * Real.pi * ri ^ 2 / ni = 4 * Real.pi * ro ^ 2 / no ↔
      ni / (ni + no) = ri ^ 2 / (ri ^ 2 + ro ^ 2) := by
  rw [mul_div_assoc, mul_div_assoc, mul_right_inj' (by positivity : 4 * Real.pi ≠ 0),
    div_eq_div_iff hni.ne' hno.ne',
    div_eq_div_iff (add_pos hni hno).ne' (by positivity : ri ^ 2 + ro ^ 2 ≠ 0)]
  constructor <;> intro h <;> linarith only [h]

end

end CellsProofs.Chemistry.Vesicle
