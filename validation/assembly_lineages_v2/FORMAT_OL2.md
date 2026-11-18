# The engine's output format for OL2's worlds (`cells.assembly_lineages@2`): milestone 1, geometry

This page adds to `FORMAT.md` (OL1's, unchanged) what a world that declares a geometry writes. The
physical choices are the lead's rulings in `docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md` §0.2b–§0.2d. A
world without a geometry writes exactly what `FORMAT.md` describes. The osmotic lumen, the shared
pool, the diagnostic record and OL3's division come in later milestones, and so does the probe
driver for OL5's registered OL2 inputs.

## The world (world.json `world`)

- **`geometry`** (only when declared): `{law: cells.bilayer_geometry@1, area_quantum_m2: q,
  area_per_leaflet: {species: {quanta: k, sourced_m2: a, source}}, vesicle_floor_quanta: {value,
  provenance}, closure_cost_kT: {value, provenance}}`.
  - k is the nearest integer to a/q (§0.2c rule 4), and the parser refuses any other.
  - The footprint is W(n) = Σ n_i k_i quanta, and the bilayer's area is A = q·W/2 (m²).
- **`conventions.exchange_encounter`**: `insertion_area` or `diffusion_radius`, declared exactly
  when `geometry` is (§0.2c rule 1). Never written otherwise.
- **A step's rate key** is its law's:
  - `forward_rate_per_s` for `cells.stochastic_mass_action@1`;
  - `insertion_velocity_m_per_s` (m/s) or `diffusivity_m2_per_s` (m²/s) for
    `cells.phase_exchange@1`, by the token;
  - `permeability_m_per_s` (m/s) for `cells.membrane_permeation@1`.

## The rates

- **A geometric step's forward** at the firing state n is a⁺ = k·E(m)·ρ0·θ⁺(n) (§0.2d item 2):
  - E(m) = A(m) in m² for `insertion_area` and permeation, and 4πR(m) in m for
    `diffusion_radius`, with R = (A/4π)^(1/2);
  - W(m) = W(n) − Σ_e k_e (n_e − m_e) is an exact integer, and E(m) = 0 at W(m) = 0;
  - ρ0 = N_A·c0 in molecules per m³ (c0 in mol/L, times 10³);
  - θ⁺ is the pool's activity: n/X_pool, or c/c0 when held.
- **Its reverse** is OL1's: the same law applied to the products, with k⁻ = k·exp(Σ ν μ°) and the same
  extent on m. The membrane reactant's activity is ff(n_i, 1)/ff(N − c, 1), at the firing state.
- **The floor** (§0.2c rule 5): a channel whose step changes W, at a firing state or a result below
  W_floor, has rate 0. A step that keeps W fires at its own rate.
- **The check:** run.json's `check.probe` is the geometry probe's verdict (balance.geometry_verdict:
  16 generic worlds, both measures, both encounters, with and without regular mixing and the
  factor). An OL1 world keeps OL1's verdict.

## The bundle

- **records.npz** gains `membrane_footprint_quanta` [row]: W at each row (int64).
- **run.json:** the laws include `cells.bilayer_geometry@1`, and `records` names the footprint.
- **world.json `derived`** gains `geometry`: `rho0_per_m3`, `log_area_constant` (ln(q·ρ0/2)),
  `log_radius_constant` (ln(4π·ρ0) + ½ ln(q/(8π))), `floor_quanta` and `closure_kT`.
- **free_energy_kT** includes C_close once, for the one living vesicle (§0.2c rule 8). The ledger's
  closure is unchanged.
