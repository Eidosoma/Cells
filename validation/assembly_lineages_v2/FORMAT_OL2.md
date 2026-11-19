# The engine's output format for OL2's and OL3's worlds (`cells.assembly_lineages@2`): OL2 milestones 1 and 2, OL3 milestone 1

This page adds to `FORMAT.md` (OL1's, unchanged) what a world that declares a geometry writes:
milestone 1's geometry, and milestone 2's osmotic lumen and lysis. The physical choices are the
lead's rulings in `docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md` §0.2b–§0.2e. A world without a geometry
writes exactly what `FORMAT.md` describes. The shared pool, the diagnostic record and OL3's division
come in later milestones, and so does the probe driver for OL5's registered OL2 inputs.

**Every declared physical value carries its provenance** (§0.2e rule 3): `{value, provenance}`,
where a value without a source says so, its provenance beginning "unsourced".

## The world (world.json `world`)

- **`geometry`** (only when declared): `{law: cells.bilayer_geometry@1, area_quantum_m2: q,
  area_per_leaflet: {species: {quanta: k, provenance}}, vesicle_floor: {quanta, provenance}}`, with
  the closure cost in one of two forms (§0.2e rule 6), and `sigma_max_N_per_m: {value,
  provenance}` exactly under `lumen_volume: osmotic` (§0.2c rule 8).
  - **An area** may add `sourced_m2` and `source`, given together (§0.2e rule 5). With a sourced
    area the rounding is the nearest quantum: |k − sourced_m2/q| ≤ ½, either integer at a tie.
    Without one, k is declared directly and no rounding check applies.
  - **The closure cost** is `closure_cost_kT: {value, provenance}`, or the bending moduli
    `kappa_kT` and `kappa_bar_kT`, each `{value, provenance}`, from which the engine computes the
    closed sphere's 8πκ + 4πκ̄ (k_BT). A negative cost is refused. world.json's `derived.geometry`
    states `closure_kT`, its `closure_form` (`declared` or `moduli`) and, for the moduli, the law.
  - The footprint is W(n) = Σ n_i k_i quanta, and the bilayer's area is A = q·W/2 (m²).
- **`conventions.exchange_encounter`**: `insertion_area` or `diffusion_radius`, declared exactly
  when `geometry` is (§0.2c rule 1). Never written otherwise.
- **A step's rate key** is its law's:
  - `forward_rate_per_s` for `cells.stochastic_mass_action@1`, a bare number as in OL1;
  - `insertion_velocity_m_per_s` (m/s) or `diffusivity_m2_per_s` (m²/s) for
    `cells.phase_exchange@1`, by the token, as `{value, provenance}` (§0.2e rule 7);
  - `permeability_m_per_s` (m/s) for `cells.membrane_permeation@1`, as `{value, provenance}`.

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

## Milestone 2: the osmotic lumen and lysis (§0.2b rules 2 and 3, §0.2c rules 6–8, §0.2d item 7)

### The world

- **`conventions.lumen_volume: osmotic`**, only with a geometry. Its lumen block declares no
  `volume_L`, and every lumen species is an ideal solute in a volume that water sets at once.
- **`free_energy`** adds `{law: cells.osmotic_lumen@1, outside_osmolarity_mM: {value, provenance}}`:
  c_ext, the outside's total osmolarity, held (§0.2c rule 6).
- **Refused at parse:**
  - osmotic without a geometry, without a lumen or without its term;
  - the term without osmotic, and `volume_L` under osmotic;
  - `sigma_max_N_per_m` missing under osmotic, or given without it;
  - a lumen-locus step with two or more lumen reactant molecules, and a membrane-locus step with a
    lumen reactant (§0.2c rule 7);
  - a membrane or lumen species without a pool place (§0.2c rule 8);
  - c_ext below the founder's pool solutes' total (finite ones at n/(N_A V_pool), held ones at
    their held_mM);
  - a founder whose tension is beyond σ_max.

### The free energy and the rates

- **F_osm(n) = −N_L ln(N_A c0 V(n)) + N_A c_ext V(n)** (k_BT), 0 at an empty lumen, with
  V(n) = min(N_L/(N_A c_ext), V_sph(A)) in L, N_L every lumen species, and V_sph = A^(3/2)/(6√π)
  from A in m² (times 10³ to L).
- **The lumen's ideal part** is taken at X = 1, Σ_s [n_s μ°_s + ln n_s!], and F_osm is an excess
  term. So each reverse is OL1's (the products' mass action, with the lumen's X at 1) times
  exp(F_osm(n′) − F_osm(n′ − ν)), and every pair keeps ln a⁺ − ln a⁻ = −ΔF + w exactly.
- **A lumen-locus step** has one lumen reactant molecule (rule 7), so its extent and its
  normalisation, both at V(m), cancel to 1: its forward is k_f·n_s.
- **The tension** is σ = max(0, Δp·R/2), with Δp = k_BT (N_L/V − N_A c_ext) in molecules per m³ and
  R = (A/4π)^(1/2). It is exactly 0 while floppy (V_osm ≤ V_sph).
- **The check:** run.json's `check.probe` is the osmotic probe's verdict
  (balance.osmotic_verdict): 16 generic worlds whose states cross the kink. A pair whose end
  state lyses has no reverse and is not checked.

### Lysis

- **An event whose end state has σ > σ_max** fires at its pair-rule rate, and the run ends with
  status `lysed` (one assembly).
- **The release, on the end row:**
  - the membrane's and the lumen's molecules go to their pool places as monomers;
  - the closure cost is released;
  - the end row books q = −(F(n_after) − F(n)) + w, the triggering step and the release together
    (§0.2d item 7), where w includes the reservoir work of any held place that receives molecules.
- **Observations after the lysis are censored:** the life has ended.

### The bundle

- **records.npz** adds `lumen_volume_L` [row] (L) and `tension_N_per_m` [row] (N/m).
- **run.json** adds `osmotic`:
  - `outside_osmolarity_mM`;
  - `pool_solutes_mM_at_start`;
  - `largest_relative_drift`: the pool's solute osmolarity's largest change over the run, relative
    to c_ext;
  - `lysis`: null, or its time, σ at the end state, σ_max, the returned counts by pool place, and
    the release's heat and reservoir work.
- **`lifecycle`** names `lysed`. An OL1 or milestone-1 world's lifecycle is unchanged.

## OL3 milestone 1: single-lineage division (§0.2c rules 9–13, §0.2d items 6, 7, 9 and 10)

Development only: not yet compared against OL5's references, which need the probe roles.

### The world and the experiment

- **The world** declares `division = {law: cells.shear_fission@1, continuation: first | uniform}`,
  with an optional `critical_stress_Pa = {value, provenance}`. It needs a geometry and an osmotic
  lumen.
- **The experiment** declares `schedules = [{index, kind: shear, k, times_s, stress_Pa?}]`. A
  stress is given exactly when the world declares a critical stress. Declared times only:
  `poisson_rate_per_s` is refused until the shared pool (OL2 milestone 3).
- **The run is refused** when JAX's threefry is not partitionable (§0.2d item 9). The environment
  record comes with milestone 3.

### A shear event

- **The clock:** the occupant's draw that crosses a schedule time is discarded and counted. Its
  next draw is at the next counter, with its wait measured from the schedule time.
- **The attempt,** in item 10.2's order:
  1. the stress test, when declared;
  2. 36πkV² ≤ A³;
  3. one block of N + k + N_L uniforms (domain 2, the parent's key, its fission counter);
  4. rule 9's membrane split, then rule 10's lumen split;
  5. the floor test.
- **The daughters** take the lineage counter's next k keys, in daughter order. The followed
  daughter (`first`, or ⌊u k⌋ with u from domain 3 at counter 0) takes the slot. Its own event
  stream starts at counter 0, and the others leave for `sink:discard`.
- **The booking:** w = Σ_j F_v(d_j) − F_v(parent), with F_v the vesicle's own F, its closure cost
  included. The sink takes the unfollowed daughters' F_v.
- **A followed daughter beyond σ_max** ends the lineage `lysed` at its birth, booked as a lysis.
  An unfollowed one leaves as born, with its flag recorded.

### The bundle (division worlds only; every other bundle is unchanged)

- **records.npz** adds:
  - `shear_work_kT` and `discarded_free_energy_kT` [row], both cumulative;
  - the fission table, one row per attempt: `fission_time`, `_schedule`, `_k`, `_parent`,
    `_parent_generation`, `_counter` (−1: no draw), `_outcome`, `_followed`, `_parent_counts`,
    `_daughters` (keys), `_daughter_counts`, `_lysed_at_birth`, `_shear_work_kT` and
    `_discarded_kT`.
- **row_kind** adds `shear` (4), a row after each split.
- **run.json** adds:
  - `division`: the operator's declaration, the schedules, the attempts and outcomes;
  - the `ssa.draw` text of the clock rule.
- **relations.json and relations.npz** are `cells.relations@2`: @1's tables, with `lysed` as an end
  reason at a `lysis` event. Each split's event is paid by `source:shear/<index>`.
