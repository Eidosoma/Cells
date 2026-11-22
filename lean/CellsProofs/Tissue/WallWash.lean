import CellsProofs.Tissue.CompartmentWash

/-! # Free and surface-bound tracer during and after a wash

The event removes a fraction of the pre-event free amount. Binding can resume
in the following time interval. A signed uptake is positive for adsorption.
-/
namespace CellsProofs.Tissue.WallWash

open CompartmentWash (afterWash)

structure Stock where
  liquid : ℝ
  wall : ℝ
  specimen : ℝ

/-- At the instant of the exchange Cells writes the free pool and the wash counters. -/
noncomputable def draw (s : Stock) (f buffer : ℝ) : Stock :=
  { s with liquid := afterWash f s.liquid buffer }

theorem event_retention (s : Stock) (f buffer : ℝ) :
    (draw s f buffer).wall = s.wall ∧ (draw s f buffer).specimen = s.specimen ∧
    (draw s f buffer).liquid + f * s.liquid = s.liquid + f * buffer := by
  refine ⟨rfl, rfl, ?_⟩
  change afterWash f s.liquid buffer + f * s.liquid = s.liquid + f * buffer
  linarith only [CompartmentWash.inventory f s.liquid buffer 0]

/-- Free tracer, two bound pools, the gross sample and refill balance even after either
surface exchanges material with the liquid. At the event both uptakes are zero. -/
theorem inventory (f free buffer wall specimen wallUptake specimenUptake : ℝ) :
    (afterWash f free buffer - wallUptake - specimenUptake) + (wall + wallUptake) +
      (specimen + specimenUptake) + f * free =
      free + wall + specimen + f * buffer := by
  linarith only [CompartmentWash.inventory f free buffer (wall + specimen)]

/-- Applying the draw fraction to all tracer overstates the sample by that fraction of
the pre-existing surface-bound material. The measured sample is independent of that stock. -/
theorem whole_stock_bias (f free wall specimen : ℝ) :
    f * (free + wall + specimen) - f * free = f * (wall + specimen) := by ring

/-- Immediately after dilution, the binding rate at a previously equilibrated surface.
Here the wash acts on concentration at fixed volume. -/
theorem rate_after_draw {onRate offRate vacant bound c : ℝ}
    (equilibrium : onRate * c * vacant = offRate * bound) (f buffer : ℝ) :
    onRate * afterWash f c buffer * vacant - offRate * bound =
      -(f * onRate * vacant * (c - buffer)) := by
  rw [← equilibrium]
  unfold CompartmentWash.afterWash
  ring

/-- A strictly more dilute refill initiates net release provided some sites are vacant. -/
theorem release_after_dilution {onRate offRate vacant bound c f buffer : ℝ}
    (equilibrium : onRate * c * vacant = offRate * bound)
    (hf : 0 < f) (hk : 0 < onRate) (hv : 0 < vacant) (hc : buffer < c) :
    onRate * afterWash f c buffer * vacant - offRate * bound < 0 := by
  rw [rate_after_draw equilibrium]
  exact neg_neg_of_pos (mul_pos (mul_pos (mul_pos hf hk) hv) (sub_pos.mpr hc))

end CellsProofs.Tissue.WallWash
