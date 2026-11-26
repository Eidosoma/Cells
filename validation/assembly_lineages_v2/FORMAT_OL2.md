# The engine's output format for OL2's and OL3's worlds (`cells.model.assembly_lineages@2`): OL2 milestones 1 and 2, OL3 milestone 1

This page adds to `FORMAT.md` (OL1's, unchanged) what a world that declares a geometry writes:
milestone 1's geometry, and milestone 2's osmotic lumen and lysis. The physical choices are the
lead's rulings in `docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md` §0.2b–§0.2e. A world without a geometry
writes exactly what `FORMAT.md` describes. The shared pool, the diagnostic record and OL3's division
came in later milestones, and the probe driver for OL5's registered OL2 and OL3 inputs is the last
section ("OL5's probe roles").

**Every declared physical value carries its provenance** (§0.2e rule 3): `{value, provenance}`,
where a value without a source says so, its provenance beginning "unsourced".

## The world (world.json `world`)

- **`geometry`** (only when declared): `{law: cells.assembly_geometry.bilayer_geometry@1, area_quantum_m2: q,
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
  - `forward_rate_per_s` for `cells.reaction.stochastic_mass_action@1`, a bare number as in OL1;
  - `insertion_velocity_m_per_s` (m/s) or `diffusivity_m2_per_s` (m²/s) for
    `cells.reaction.phase_exchange@1`, by the token, as `{value, provenance}` (§0.2e rule 7);
  - `permeability_m_per_s` (m/s) for `cells.reaction.membrane_permeation@1`, as `{value, provenance}`.

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
- **run.json:** the laws include `cells.assembly_geometry.bilayer_geometry@1`, and `records` names the footprint.
- **world.json `derived`** gains `geometry`: `rho0_per_m3`, `log_area_constant` (ln(q·ρ0/2)),
  `log_radius_constant` (ln(4π·ρ0) + ½ ln(q/(8π))), `floor_quanta` and `closure_kT`.
- **free_energy_kT** includes C_close once, for the one living vesicle (§0.2c rule 8). The ledger's
  closure is unchanged.

## Milestone 2: the osmotic lumen and lysis (§0.2b rules 2 and 3, §0.2c rules 6–8, §0.2d item 7)

### The world

- **`conventions.lumen_volume: osmotic`**, only with a geometry. Its lumen block declares no
  `volume_L`, and every lumen species is an ideal solute in a volume that water sets at once.
- **`free_energy`** adds `{law: cells.free_energy.osmotic_lumen@1, outside_osmolarity_mM: {value, provenance}}`:
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

- **The world** declares `division = {law: cells.operator.shear_fission@1, continuation: first | uniform}`,
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
- **The state after each scheduled event** (OL5's run rows): every shear event, and in a population
  every transfer event, states `pool_after` and `slots_after` (each living slot's slot, key and
  counts), the state once its attempts and their births beyond σ_max, or its sample and fresh pool,
  are applied.
- **An attempt's heat and reservoir work** in a population include the release of each daughter
  that lysed at birth. That lysis is still listed in `lyses` with `at_birth` true, and its row
  books the release once: the attempt's figures attribute it to the attempt and are not a second
  booking, so a reader sums one or the other, never both.
- **A transfer event's draws** are `[{slot, counter, uniform}]`, one per living assembly in slot
  order, on the schedule's stream (domain 6, its index) at those counters.
- **`diagnostic.json`** gives:
  - the channel table;
  - the shear events, each with its time, schedule, the slots not admitted, and its attempts: slot,
    key, counter, outcome, daughters (key, slot, counts, lysed at birth), the followed daughter,
    shear work, sink, heat, reservoir work, and the pool after;
  - the initial and final states (each slot's key and counts, and the pool);
  - the world's key, the end reason and the environment record.

### The shared pool (`cells.population.shared_pool@1`, the first `cells.population_structure@1`)

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
- **A transfer** (`cells.operator.serial_transfer@1`, `{index, kind: transfer, times_s, K_keep,
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

## FR-20: a pool replacement, a pulse or a washout (`cells.operator.pool_replacement@1`)

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
    {"XR@membrane": 1}, "law": "cells.reaction.stochastic_mass_action@1", "forward_rate_per_s": k_f}`;
  - declared in this direction, for a declared pair.

  Its rates are a⁺ = k_f·θ⁺·n_R and a⁻ = k_f·exp(μ°_XR − μ°_R − μ°_X)·n_XR. Any other interfacial
  shape is refused, as before.
- **No new record.** The step is an ordinary step of the event table and of relations@2. On a
  bilayer, R and XR carry their own area quanta.

## FR-21, the shell: a prescribed wall and lumen (§0.2g)

- **The geometry:** `{"law": "cells.assembly_geometry.prescribed_shell@1", "area_m2": {"value", "provenance"}}`.
  - The world has `lumen_volume: declared` and `phases.lumen.volume_L`, and no
    `exchange_encounter`.
  - The wall's species carry no area quanta.
- **The entry:** `{"locus": "membrane", "reactants": {"S@pool": 1}, "products": {"S@lumen": 1},
  "law": "cells.reaction.shell_permeation@1", "permeability_m_per_s": {"value", "provenance"}}`, with
  a⁺ = P_s·A_sh·ρ0·θ⁺.
- **The gate factor (optional):** `{"law": "cells.rate_factor.gate_factor@1", "forms": [...],
  "entries": [{"form", "step", "ddG_kT"}]}`, with fractions over the gate's forms only.
- **world.json's `derived.shell`** gives `rho0_per_m3`, `area_m2`, `lumen_volume_L`, `log_extent`
  = ln(A_sh·ρ0), and `conductance_m3_per_s` (G_s = P_s·A_sh per permeant).
- **The rows:**
  - `membrane_footprint_quanta`, where written, is 0: the wall has no quanta.
  - There is no tension, lysis or division record.

## FR-35: a pool withdrawal, a partial exchange (`cells.operator.pool_withdrawal@1`)

The design is [the note](../../docs/ASSEMBLY_WITHDRAWAL_DESIGN.md) under D261.

- **The schedule:** `{"index", "kind": "withdrawal", "times_s", "fraction", "buffer"}`.
  - `fraction` f is in (0, 1).
  - `buffer` gives one integer count per finite pool place, in place order: the molecules in the
    withdrawn volume fV. Tracer-free is 0.
- **The draw:** each molecule leaves with probability f. Place j (its ordinal among the finite
  pool places) draws one block of its count on the schedule's stream (domain 6, the schedule's
  index) at draw number w·P_f + j. The counter w is the schedule's washes among the applied stops,
  so a checkpoint carries it as FR-22's applied-stops record, with no key of its own.
- **`run.json`'s `population.withdrawals`** lists each withdrawal, with these fields:

  | Field | What |
  | --- | --- |
  | `id` | the event's ID |
  | `time_s`, `schedule`, `fraction` | the stop and its schedule |
  | `before`, `withdrawn`, `remaining`, `supplied` | `{place: count}` over the finite pool places |
  | `draws` | each block's `[index, draw number, size]` |
  | `pool_loss_kT` | the sink: F(before; V) − F(kept; (1 − f)V) |
  | `sample_F_kT` | the sample's own F at fV |
  | `split_surprisal_kT` | σ = −ln P(k), so the sink is `sample_F_kT` − σ |
  | `buffer_F_kT` | the schedule's work: the buffer's F at fV |
  | `mixing_heat_kT` | in the heat; never negative |

- **Only when a world declares a withdrawal:**
  - the diagnostic record's `withdrawal_events`;
  - a row of kind `withdrawal` (8), whose legend entry is written only then;
  - in relations@2, the event `event:withdrawal/<n>` (kind `withdrawal`, at `node:pool`, paid by
    `source:withdrawal/<index>`), with `removes_to` edges from the pool to the sink weighed by the
    withdrawn counts and `supplies` edges from the source weighed by the supplied counts (mode
    `event`).
- **Refused at the wash, before the draw:** a place whose pre-wash count plus its buffer count
  exceeds `molecule_capacity`.

## OL5's probe roles: OL2's and OL3's registered inputs (`probes2.py`)

The engine's outputs on OL5's registered OL2 and OL3 inputs, for the rows OL2-1 to OL2-5 and OL3-1
to OL3-5 of `validation/ool/references/harness2.py`. An adapter written from this page alone maps
them onto harness2's canonical layout; the driver reads only the inputs' export folder, never the
references' code.

- **Running it:** `python -m validation.assembly_lineages_v2.probes2 freeze OUT`, then, inside
  `OUT/source`, `PYTHONPATH=src:. python -m validation.assembly_lineages_v2.probes2 run INPUTS OUT`.
  INPUTS is an export of the registered inputs (`INPUTS/designs/`: the worlds, runs, probe states,
  partition parents, `refusals2/` and amendment 7's `ol3_division.json`). OUT holds `roles2.json`,
  this page and `FORMAT.md`, and one folder per role.
- **Settings** fixed before the first run (the lead's rulings of 22 November 2026), recorded in
  `roles2.json`: the stream `{seed: 1, environment: 0, lineage: 0, branch: 0}`;
  `molecule_capacity` 2^18 = 262,144, above every registered count (it changes no value); 64
  events a device call; a row every 1,000 events. A different seed waits for a ruling.

### The reader (`registered.py`: `world2`, `run_entries`, `definition2`)

The module's docstring gives the mapping field by field; it checks nothing, so every refusal is
the engine parser's. In short:
- **Places** are `species@phase`. The pool's places are its `finite` species in order, then its
  `held_mM` species in order; then the membrane's and the lumen's species in order.
- **Steps:** a join is `cells.reaction.phase_exchange@1` and an entry `cells.reaction.membrane_permeation@1`, one
  molecule from the direction's first phase to its second; a mass-action step keeps its law, locus
  and sides. Rates are `{value, provenance}`.
- **Units:** `standard_concentration_M` and `outside_osmolarity_M` × 10³ become mM; held
  concentrations are mM already.
- **The founder:** `{n, l, p}` by position over the membrane, lumen and finite pool species. A
  population's founder vesicles become `population.founders`, founder i in slot i, with the
  run's `slots`; the world's founder then holds the pool and every vesicle place at 0.
- **The run:** `mode`; `t_end_s` → `time_horizon_s`; `max_events` → `event_limit`; `schedules`
  unchanged (none when empty). Amendment 7's division inputs give `division = {law:
  cells.operator.shear_fission@1, continuation?}`.
- **Provenance** (§0.2e rule 3, as ruled for these roles on 22 November 2026): a value takes the
  registered world's own source text where the registered format carries one, and otherwise
  `unsourced; registered OL5 world <id>`. The format carries one only for σ_max
  (`sigma_max_source`), which §0.2c rule 8 requires: a missing source passes through as a σ_max
  with no provenance, and the parser refuses it. The default is never put in its place.
- **Defects reach the parser as they are:** nothing is cast or defaulted, and a field the reader
  does not map, or whose engine block is absent, is passed on under its own name for the parser to
  refuse. So the parser's message may name an earlier check than the rule a declaration breaks.

### `roles2.json`

| Field | What |
| --- | --- |
| `format` | `cells.assembly_lineages.probe_roles2@1` |
| `source` | the engine's source: the snapshot's revision, dirty state and diff hash |
| `inputs` | `directory`, and `files`: every input JSON file's SHA-256, by its path under INPUTS |
| `settings` | `stream`, `molecule_capacity`, `chunk_events`, `row_every_events`, the `execution` and the two experiments (`probe_experiment` for parses and probes, `run_experiment` for runs), the partition's carrier keys, and when they were fixed |
| `roles` | the roles run |
| `problems` | each role's problem (a declaration admitted, a run refused), or none |
| `files` | every output file's SHA-256, by its path under OUT |

### `refusals2/refusals.json` (OL2-5)

`{format: cells.assembly_lineages.probe@2, role, source, rule, results, all_refused}`. `results`
maps each declaration's `id` (its file name before the first dot) to `{file, sha256, refused,
message}`, the parser's message when refused. A run declaration (`*.run2.json`) is parsed on its
registered world with amendment 7's division inputs, and its entry adds `registered_world`,
`registered_world_sha256`, `division_inputs` and `division_inputs_sha256`.

### `kernel2/<world>/` (OL2-1, OL2-2)

For `ol2_wa` and `ol2_wa_diffusion` at their probe states, and `ol2_closed` and `ol2_two` at their
one-vesicle states. `ol2_two`'s states are evaluated on its first founder vesicle's world (a
one-vesicle state's rates do not depend on another vesicle); `probe.json`'s
`world.founder_vesicle` says which, null for a one-vesicle world.

`probe.npz` (S states, C the vesicle steps: every step with a membrane or lumen place, in declared
order, named by `probe.json`'s `steps`):

| Array | Shape | What |
| --- | --- | --- |
| `input_states` | [S, D] int64 | the registered states echoed in the registered order: membrane counts, lumen counts, finite pool counts; `probe.json`'s `places` names each column `species@phase` |
| `a_plus` | [S, C] | the step's forward rate at the state (1/s), from the kernel's own rate function on the host; 0 where it cannot fire |
| `a_minus` | [S, C] | the rate at the state of the step's reverse event (the step run backwards from the state) |
| `lyses_plus`, `lyses_minus` | [S, C] bool | whether that event's end state has σ > σ_max (`kernel.lysis_at`); false where its rate is 0 |
| `derived` | [S, 7] | at the state: W (quanta), A (m²), R (m), V_osm (L), V_sph (L), V (L), σ (N/m), in `probe.json`'s `derived` order; V_osm is 0 at an empty lumen (`lumen.host_derived`) |
| `free_energy_kT` | [S] | F(state), the ledger's value |
| `reservoir_work_kT` | [C] | the held reservoirs' work of each forward event; its reverse books minus that |

`probe.json` also gives the world (`registered`, `sha256`, `engine_world_id`), the conventions,
the full definition, the channel table and `arrays_sha256`; held places are at their declared
concentrations.

### `partition/` (OL3-1)

`probe.npz` holds, for each parent of `ol3_parents.json` (M = `attempts_per_parent` attempts):

| Array | Shape | What |
| --- | --- | --- |
| `<id>_u` | [M, N + k + N_L] | the attempt's block of uniforms as used: rule 9's N (one per listed membrane molecule, species in the listed order) and k (π), then rule 10's N_L (one per listed lumen molecule) |
| `<id>_membrane` | [M, k, G] int64 | each daughter's membrane counts, by daughter: block t went to daughter π(t) |
| `<id>_lumen` | [M, k, G_L] int64 | each daughter's lumen counts, by daughter |

Attempt m is the engine's fission stream (domain 2) of the parent's carrier key at counter m
(`division.block`), under the run stream above; the daughters are the engine's own split
(`division.split`). `probe.json`'s `parents` gives each parent's `id`, `carrier_key` (its index
in `ol3_parents.json`), `counters`, `k` and `uniforms_per_attempt`, and `area_quantum_m2` the
quantum used for the lumen's weights, the registered OL3 worlds' own (it cancels in
V_sph(A_j)/Σ V_sph(A_l)).

### `runs2/<run>/` (OL2-3, OL2-4, OL3-2 to OL3-5)

Each registered run is a bundle (FORMAT.md, and this page's sections above) run in the diagnostic
mode: `manifest.json` (its `runtime` states `jax_threefry_partitionable`), `resolved_config.json`
(the definition: the reader's world with the run's `mode`, `slots`, horizon, event limit and
schedules), `world.json`, `run.json`, `records.npz`, the relations files for a population, and
`diagnostic.json` and `diagnostic.npz`. A run the engine refuses writes `refused.json` (`message`)
instead. The record's forms differ by mode:

| Item | Single lineage | Population |
| --- | --- | --- |
| draws: `draw_domain`, `draw_key`, `draw_counter` | domain 1: the occupant's carrier key, its age counter (draws since its birth, from 0) | domain 5: carrier word 0, the world's draw count (from 0) |
| `draw_uniforms` | [draws, 2]: u1 sets τ = −ln(u1)/a0, u2 the channel | [draws, 3]: u1 τ, u2 the group, u3 the channel |
| `draw_fate` | an index into `fates`: `committed`, `discarded_at_schedule`, `ended_run` | the same |
| `event_group` | 0: the slot's group (every declared step) | 0 the pool, 1 + k slot k |
| `event_channel` | the kernel's signed code: +(r+1) step r's forward, −(r+1) its reverse (`channels.lineage`'s rows) | the same code; `channels.pool` and `channels.vesicle` list each group's channels as `[step, direction]` in fold order |
| `event_vesicle_after`, `event_pool_after` | over `vesicle_places` and over `pool_places` (the finite pool places) | both over `places` (every place), 0 outside their phase; all 0 for a pool event's vesicle |
| a slot's `counts` (states, `slots_after`, daughters) | over `vesicle_places` | over `places` (daughters: over the membrane and lumen places) |
| a `pool` (states, `pool_after`) | over `pool_places` | over `places` |

Common to both:
- **Schedule draws:** `schedule_draw_index`, `_counter`, `_uniform`, `_use` (an index into
  `schedule_uses`: `gap`, `transfer`) and `_time` (the time a gap gives, NaN for a transfer draw);
  a gap past the horizon is drawn too.
- **Step events:** `event_time`, `event_lysed`, `event_heat_kT` and `event_reservoir_work_kT`.
  A lysing step's `event_heat_kT` and `event_reservoir_work_kT` are the step's own. The same
  event's release is booked separately: in a single lineage in `run.json`'s `osmotic.lysis`
  (`release_heat_kT`, `release_reservoir_work_kT`), in a population in that event's `lyses` entry
  (`at_birth` false). The event's total is the sum.

  A lysing step's counts read the same way. At a step with `event_lysed` true, `event_vesicle_after`
  and `event_pool_after` are the step's own state: after the step and before the release, with the
  vesicle still full. The release's molecules are in the same record's `returned` (`osmotic.lysis`
  or the `lyses` entry), by pool place, and they total the vesicle's counts. The pool after the
  whole event is `event_pool_after` plus `returned` at the finite pool places, matched by name. A
  held place's count does not change: its reservoir takes the molecules back, booked in
  `release_reservoir_work_kT`. The record keeps both pools: the step's own in `event_pool_after`,
  and the pool after the event in records.npz. In a single lineage that is the end row, also
  `diagnostic.json`'s `states.final` (the vesicle then empty); in a population it is that lysis's
  row (`row_kind` `lysis`).
- **`shear_events`:** `{time, schedule, not_admitted, attempts, pool_after, slots_after}`, in time
  and schedule order. An attempt is `{slot, key, counter, outcome, uniforms_offset,
  uniforms_count}`, with `outcome` one of `split`, `refused_floor`, `refused_volume`,
  `refused_stress` or `slots_full`. A slot not admitted (v > k^(−1/2), or a stress test) appears
  in `not_admitted` and as an attempt with outcome `refused_volume` or `refused_stress` and no draw
  (`counter` −1, `uniforms_count` 0), as does a `slots_full` attempt. A drawing attempt's block,
  the used prefix, is `attempt_uniforms[uniforms_offset : uniforms_offset + uniforms_count]`. A
  split adds `daughters` (`{key, slot, counts, lysed_at_birth}`), `shear_work_kT`, `heat_kT`,
  `reservoir_work_kT` and `sink_kT`. An attempt that does not split books nothing: no shear work,
  heat, reservoir work or sink (its entry carries none of them). In a single lineage a daughter's `slot` is 0 for the followed
  one and null otherwise, and the attempt adds `followed` (its daughter index) and `pool_after`.
  In a population every daughter's `slot` is the slot it took (a birth-lysed daughter's too), and
  the attempt's heat and reservoir work include its births beyond σ_max (attribution: the lyses'
  rows book them once).

  At a birth beyond σ_max, a shear event's `pool_after` (the diagnostic record's state after the
  event, above) reads differently in the two modes. Its `slots_after` reads the same in both: the
  living slots after the event, so a birth-lysed daughter is never in it. So that section's
  sentence, "the state once its attempts and their births beyond σ_max ... are applied", holds for
  both of a population's fields, and in a single lineage for `slots_after` only.
  - In a population, `pool_after` is the pool after the whole event. Each birth lysis has freed
    its slot (a later attempt's daughter in the same event can take it) and returned its molecules:
    its `lyses` entry, `at_birth` true, matched to the daughter by `key`. The pool before those
    lyses is `pool_after` minus their `returned` at the finite pool places. records.npz keeps both
    states: each split's `shear` row before its births' lyses, and each lysis's `lysis` row after
    it.
  - In a single lineage, a followed daughter born beyond σ_max ends the run `lysed`, and
    `pool_after` (the event's and the attempt's) is the pool before its release. Its molecules are
    in neither `pool_after` nor `slots_after`; they are in `run.json`'s `osmotic.lysis.returned`.
    The release's heat and reservoir work are in `osmotic.lysis` (a single lineage's split books 0
    in `heat_kT` and `reservoir_work_kT`), and no step event is marked `event_lysed`. The pool
    after the whole event is `pool_after` plus `returned` at the finite pool places, matched by name
    (a held place's molecules go back to its reservoir). That pool is on records.npz's end row and
    in `diagnostic.json`'s `states.final`; the `shear` row before it holds the state before the
    release, the daughter still full. An unfollowed daughter born beyond σ_max leaves for the sink
    as born and returns nothing to the pool.
- **`transfer_events`** (a population): `{id, time_s, schedule, draws, kept, removed, sink_kT,
  work_kT, pool_after, slots_after}`, with `draws` `[{slot, counter, uniform}]`, `kept` and
  `removed` slots, the sink and the schedule's work.
- **`lyses`** (a population): `{time_s, slot, key, event, returned, release_heat_kT,
  release_reservoir_work_kT, sigma_N_per_m, at_birth}`.
- **`states`:** `initial` and `final`, each `{slots: [{slot, key, counts}], pool}`; a carrier key
  is an int64, spelled `s * 2**32 + c` (`keys`).
- **Identity:** `world` is the engine's world ID (the definition's SHA-256), not a carrier key;
  `end` is the run's status (`complete`: held to the horizon; `lysed`; `slots_full`;
  `event_limit`; `capacity`; ...); `environment` gives `jax_threefry_partitionable`.
