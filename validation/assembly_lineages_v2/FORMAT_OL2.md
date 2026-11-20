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
  stress is given exactly when the world declares a critical stress. Two shear schedules may not
  share a time, so each attempt has one payer. Declared times only:
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

## OL2 milestone 3: the shared pool, serial transfer, the diagnostic record and item 9

Development only, built in slices. Slice 1 is below.

### §0.2d item 9

- **Every run of the family refuses to start** when JAX's threefry is not partitionable.
- **The bundle's environment record,** manifest.json's `runtime`, states
  `jax_threefry_partitionable`. The invariance comparison already exempts that path.

### Streams

- **Domain 5 (`world`)** has carrier word 0 (the lead's ruling, 19 November 2026).
- **Domain 6 (`schedule`)** takes the schedule's declared index as its carrier word.
- **Both use @1's derivation:** fold the base key, then the 64-bit carrier, then the domain, then
  the counter.
- **A run that draws on either** states both in its stream identity (`scheduled_identity`), with
  only `label` reserved. Every other run's identity is unchanged.

### Poisson shear times

- **A shear schedule** declares `times_s` or `poisson_rate_per_s`.
- **Poisson gaps:** t₁ = −ln(u₀)/λ from t = 0, then t_(i+1) = t_i − ln(u_i)/λ. Each gap is its own
  draw on the schedule's stream, from counter 0, and the gap past the horizon is drawn too.

### The diagnostic record (§0.2d item 10.5)

The record is written when the experiment declares `diagnostic: true`, as `diagnostic.json` and
`diagnostic.npz`. It is absent by default.

- **`draw_*`** has one row per draw, in order: domain, carrier key, counter, uniforms (NaN pads)
  and fate (`committed`, `discarded_at_schedule` or `ended_run`).
  - The uniforms are recomputed on the host from each draw's address.
  - Each committed draw's uniforms equal the device's `event_uniforms` when those are recorded
    (checked).
- **`schedule_draw_*`** has one row per schedule draw: index, counter, uniform, use (`gap` or
  `transfer`), and the time a gap gives.
- **`event_*`** has one row per step event: time, group, the kernel's signed channel code,
  whether it lysed, and its heat and reservoir work. It also holds the changed vesicle's counts
  after the event (`vesicle_places` order) and the pool after it (`pool_places` order).
- **`attempt_uniforms`** holds each drawing attempt's block (N + k + N_L values), concatenated.
  `diagnostic.json`'s shear events give each attempt's offset and count.
- **`diagnostic.json`** gives:
  - the channel table;
  - the shear events, each with its time, schedule, the slots not admitted, and its attempts: slot,
    key, counter, outcome, daughters (key, slot, counts, lysed at birth), the followed daughter,
    shear work, sink, heat, reservoir work, and the pool after;
  - the initial and final states (each slot's key and counts, and the pool);
  - the world's key, the end reason and the environment record.

### The shared pool (`cells.shared_pool@1`, the first `cells.population_structure@1`)

- **The world** declares `population = {structure, slots: K, founders: [{place: count} of every
  finite membrane and lumen place]}`, with a geometry.
  - Its `founder` holds the pool, with every vesicle place 0.
  - The execution's `mode` is `population` exactly when a population is declared.
  - Founder i takes slot i and key `i:0`. The other slots start empty.
- **The selection map:** the groups are the pool, then slots 0 to K − 1.
  - A step with any membrane or lumen place belongs to every slot's group. The others belong to the
    pool's group.
  - Three uniforms per draw come from domain 5 at the world's draw count: τ, then the group, then
    the channel. Every total is a serial fold.
  - Each slot's rates are `kernel.rates` evaluated at the slot's vesicle together with the pool.
- **A lysis** sends the vesicle's molecules to their pool places, releases the closure cost, frees
  the slot and books one row. The world then goes on.
- **A shear stop** (declared or Poisson times) discards the crossing draw. Every daughter lives:
  - daughter 0 keeps its parent's slot and continues the parent's sub-lineage counter;
  - the other daughters take free slots in slot order, and each opens a new sub-lineage, numbered in
    world event order;
  - with too few free slots the run stops `slots_full` before the draw.

  The division block declares no `continuation` in a population.
- **A transfer** (`cells.serial_transfer@1`, `{index, kind: transfer, times_s, K_keep,
  fresh_pool}`, one fresh count per finite pool place) works as follows:
  - it draws one uniform per living assembly on its own stream and keeps the K_keep smallest;
  - the others end `removed`;
  - the pool's finite places take the fresh composition;
  - the sink takes F of the removed vesicles and of the old pool, and the transfer's column takes F
    of the fresh pool.
- **Records:**
  - rows: `pool_count` [row, place], `slot_count` [row, slot, place], `slot_key` [row, slot] (−1
    for an empty slot), and the geometry rows as [row, slot];
  - ledger terms: `schedule_work_kT` [row, schedule], one column per declared schedule, with
    run.json's `population.schedule_columns` naming each column's schedule and payer;
    `shear_work_kT` (the shears' total) and `discarded_free_energy_kT` (the sink). Every row checks
    that the columns sum to the shear total plus the transfers' work;
  - `row_kind` adds `shear`, `lysis` and `transfer`;
  - the fission table adds `fission_slot`, `fission_daughter_slots` and the outcome `slots_full`;
  - the trace adds `event_group`, and `event_uniforms` holds three uniforms per event;
  - run.json's `population` block lists the lyses, the transfers, the schedule draws and the
    payers;
  - relations@2 holds the lives (founders, divisions, `lysed`, `removed`, censored), the fission,
    lysis and transfer events, the slots, and each schedule's source.
- **The diagnostic record of a population:**
  - the world's draws (domain 5), read from the device and checked against their addresses;
  - every crossing draw is discarded at its stop, and the last ends the run when the device ended
    it;
  - `event_group`, the attempts with their slots, the transfer events and the lyses.

## FR-22, rung P: checkpoints of population worlds (`checkpoints.py`)

- **A stop** is a run argument, never a definition key, so no fingerprint moves:
  `runner.run(spec, stop=k)`, with k from 1 to below `experiment.event_limit`.
  - The run ends `stopped` after its k-th committed event and that event's own host action (a
    lysis), before the next draw. Every life is censored at the cut.
  - Its qualifier folds in `{events: k, fissions: the world's splits}`.
  - `run.checkpoint()` keeps its state. A cut at a lysing event is refused: the resumed run's
    first row would sit at the lysis's time, which needs relations' same-time order.
- **The checkpoint's files:**
  - `checkpoint.json`: the format `cells.assembly_lineages_v2.checkpoint@1`, the definition and
    its fingerprint, the stopped run's qualifier, the clock `{time, events, counter}` and the
    digest;
  - the host's document: the sub-lineages' counts, the next sub-lineage, the fission and
    transfer counters, the stops applied, the world's fission and transfer numbering, its splits
    and the living lives;
  - the runtime and the source identity;
  - `lane.npz`: the device lane, verbatim;
  - `host.npz`: each slot's key, sub-lineage and generation, the host's bookings, and the world's
    initial F.
- **A restart** is `runner.run(spec, start=checkpoint)`, with the checkpoint's definition.
  - Only the horizon, `event_limit`, `trace` and `diagnostic` may differ.
  - A new branch word is refused in this rung.
- **The resumed run's records:**
  - `run.json`'s `run.start` is its start record: the checkpoint's digest, the run that wrote it,
    the time, the events, the counter, the kind (`restart`) and what differs;
  - its qualifier folds in `{checkpoint, time}`;
  - its rows start with the cut's state, and their `row_event` counts from the world's start;
  - its ledger is referenced to the world's initial F;
  - its trace, event uniforms and diagnostic draws are its own events;
  - its `population.numbering` gives the world's events, fission attempts and transfers before
    it;
  - in relations@2, the lives alive at the cut are `continued`.
- **The joining rule** for the two segments' records is `checkpoints.py`'s module docstring.

## FR-20: a pool replacement, a pulse or a washout (`cells.pool_replacement@1`)

- **The declaration:** `{index, kind: replacement, times_s, pool}`, beside the shear and transfer
  schedules. `pool` gives one count per finite pool place, in place order, as a transfer's
  `fresh_pool` does.
- **At each time, a host stop:**
  - it draws nothing;
  - every slot is kept as it stands;
  - the pool's finite places take `pool`;
  - the held places, c_ext and the pool's volume are unchanged.
- **Refused:**
  - a replacement without a population;
  - a `pool` of the wrong length;
  - fresh solutes above c_ext;
  - a held pool species that also has a membrane or lumen place, since it could not be washed out.
- **Booking:** the sink takes F of the old pool, and the schedule's column `schedule_work_kT` takes
  F of the fresh pool. `shear_work_kT` plus the transfers' and replacements' work equals the
  columns' sum at every row.
- **Records:**
  - `row_kind` adds `replacement`;
  - `run.json`'s `population.replacements` lists each replacement: its `id`, `time_s`, `schedule`,
    `removed` and `supplied` (`{place: count}` over the finite pool places), `sink_kT` and
    `work_kT`;
  - the diagnostic record's `replacement_events` holds the same;
  - relations@2 adds the event `event:replacement/<n>` (kind `replacement`, at `node:pool`), the
    source `source:replacement/<index>` (schedule, substrate, the payer of its column), the nodes
    `node:pool` and `sink:discard`, and, per species with a count, a `removes_to` edge from
    `node:pool` to the sink and a `supplies` edge from the source to `node:pool`, each weighed by
    its count at the event (mode `event`);
  - a world without a replacement writes none of these, but for the `row_kind` legend in
    `run.json`, which lists `replacement` for every population.

## FR-21, the site step: one-step binding to a declared site (§0.2f)

- **The world's optional `sites`:** `[{"site": "R", "complex": "XR"}, ...]`.
  - Both are membrane species, distinct, and a complex belongs to one site.
  - A world without sites writes no key, so its id and fingerprint are unchanged.
- **The step it admits** in a world with a geometry (rule 3, amended):
  - `{"locus": "membrane", "reactants": {"X@pool": 1, "R@membrane": 1}, "products":
    {"XR@membrane": 1}, "law": "cells.stochastic_mass_action@1", "forward_rate_per_s": k_f}`;
  - declared in this direction, for a declared pair.

  Its rates are a⁺ = k_f·θ⁺·n_R and a⁻ = k_f·exp(μ°_XR − μ°_R − μ°_X)·n_XR. Any other interfacial
  shape is refused, as before.
- **No new record.** The step is an ordinary step of the event table and of relations@2. On a
  bilayer, R and XR carry their own area quanta.
