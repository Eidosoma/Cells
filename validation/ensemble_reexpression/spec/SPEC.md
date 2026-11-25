# The worlds, what a canonical definition must hold, and the runs (Part 1)

`inputs.json` governs the numbers. Where this text and it differ, stop and ask.

## 0. Units and constants

- **Units:** amounts in fmol, volumes in pL, concentrations in mM (1 mM = 1 fmol/pL = 1 mol/m³), areas in m², lengths in m,
  permeabilities in m/s, diffusivities in m²/s, capacitances in F, charges in C, potentials in V, energies in pJ, times in s.
- **Constants:** F = 6.02214076 × 10²³ × 1.602176634 × 10⁻¹⁹ C/mol and R = 6.02214076 × 10²³ × 1.380649 × 10⁻²³ J/mol/K, each the double
  product, and 1 fmol = 10⁻¹⁵ mol. They are in `inputs.json`. Both sides use them.
- **A declared number** is its nearest double, as `inputs.json` prints it.
- **ε = 2⁻⁵².**

## 1. The consumers

| Consumer | What legacy ran | Worlds here | Equations |
| --- | --- | --- | --- |
| `jupiter` | The JUPITER readiness check's two arms: two cells, one junction, three outside regions joined by three faces, one Na/K pump and one Kv1.5-type channel per cell | `jupiter_baseline`, `jupiter_pump_release` (both pumps off from 5 to 10 ms) | Same |
| `cell` | The assembly-regulated cell: one cell, one finite outside region, one pump, one channel, whose availability is set by one assembly pool. 64 worlds a seed | `cell` | Same, and the pool is live code |
| `base` | The assembly-regulated cluster's base: the JUPITER cluster with two pools, one per cell. 8 worlds a seed | `base` | Same, and the pool is live code |
| `integrated` | The integrated ensemble's world: seven cells, twelve gated junctions, one finite outside region, no pump, leak or channel. The junctions' availability follows a schedule: 1, 0.5 from 5 ms, 0 from 10 ms, 1 from 15 ms | `integrated` | Same |

**"Same equations"** means that the re-expression keeps the model's equations and changes only the code and the way it is
declared. A band applies. No consumer of Part 1 is a changed model.

**What the re-expression of Part 1 is.** Each ionic world is a closed world of the engine's inner tissue model, version 3, integrated by
RK4. Each assembly world is a run of the live assembly pool, whose event path becomes the ionic world's channel schedule (§3.2).

## 2. What a canonical definition must hold

**The rule.** A world's block in `inputs.json` is the content of the captured definition, value for value, in canonical terms.
A candidate's definition holds it, at the precision of §2.4. The exporter writes the block back from **the definition the engine parsed
and ran**, not from this folder (`TABLE.md` §3).

### 2.1 By name

| In the block | In the canonical definition |
| --- | --- |
| `species`, `temperature_K` | Species Na, K, Cl with valences +1, +1, −1. No other row. No species registry, kind, operator or label |
| `cells`, `outside` | Each compartment's volume, initial amounts, fixed charge and initial charge. No region is held: every `held` is false |
| `gauge`, `gauge_potential_V` | The closure's gauge reference, at 0 V. The world is closed: no reservoir, no electrode |
| `membranes` | Inside, outside, area, capacitance, the constant-field permeability of every species, the pump (or none). No calcium pump |
| `membranes[].pump` | The Na/K pump on maintained fuel: 3 Na out and 2 K in a cycle, its capacity, its three constants and its fuel |
| `channels` | One population per cell: its membrane, its permeant species K (relative permeability 1), its maximal permeability, its abundance, its two gates' initial values (m, h in that order). No factor, no block |
| `junctions` | `sender` (the captured `from_cell`), `receiver` (`to_cell`), area, permeabilities and the one-gate relaxation law's threshold, minimum and initial gate |
| `faces` | Sender, receiver, area, length and a diffusivity per species |
| `controls` | Schedules as `[time, value]`, each in force from its time. `leak` is a membrane's availability, `pump` the pump's, `channel` the population's, `junction` the junction's |
| `material_tolerance_fmol` | The execution's material tolerance per species |
| `end_s` | The horizon, 0.02 s |

**Which pieces a world names** (laws, the model, the solver, the field solver) is in the strings note, by label.

### 2.2 Derived declarations, by rule

Legacy declares a specific capacitance and an initial voltage. The canonical form declares a capacitance and a charge.

- **Capacitance** = area × specific capacitance, the double product. `inputs.json` holds it as `capacitance_F`.
- **A cell's initial charge** = capacitance × initial voltage, the double product (`initial_charge_C`).
- **An outside region's initial charge** = minus the correctly rounded sum of the charges of the cells that face it, and 0 for a region
  that no membrane faces.
- **Fixed charges** are the captured ones. The inner model's charge anchor admits them: the largest disagreement between a captured
  fixed charge and its rule is 5.1 × 10⁻²⁴ C, far below the model's anchor floor of 10⁻²⁰ C.
- **The captured leak multipliers** are 1 for every species at every time, so one availability of 1 per membrane holds them. A per-species
  multiplier has no canonical counterpart and none is used.
- **The captured pump multiplier** becomes the pump's availability, and the captured open fraction the junction's availability.

### 2.3 What has no counterpart, and is left out

- Array capacities and padding.
- The observation at 7.3 × 10⁻⁵ s (`jupiter`) and at 3.713 × 10⁻³ s (`integrated`). They are off the grid, and the inner model refuses an
  observation that is not an accepted boundary. Legacy's values there are interpolants. They are not compared.
- `integrated`: the captured pump schedules of membranes that have no pump.
- The window size, the trace budget and the backend.

### 2.4 The echo's precision

A candidate's block is compared with `inputs.json`'s block (`CRITERIA.md` §5):
- numbers to 10⁻¹² relative, each against its own value. A declared zero is exactly zero;
- **an outside region's initial charge** to 10⁻¹² of the sum of the magnitudes of the charges of the cells that face it, since it is a sum
  that cancels;
- a number in a schedule or a time, to 10⁻¹² relative. Integers, strings and booleans, exactly;
- **maps by key, never by order.** A JSON 4 equals 4.0. A schedule is compared after every entry that repeats the value before it is
  removed;
- **`controls.channel` of `cell` and `base`** is not part of the echo. `inputs.json` holds a sentence in its place, and the schedule is class E (`CRITERIA.md` §4.1). So are `inputs.assembly`'s `pool_seeds` and `switch_list`. Its `assembly_observable` is an echo of a label, and its `composed_file_fingerprint` is recorded;
- a key that `inputs.json` does not hold is recorded, and refuses nothing.

## 3. What a candidate declares, for the comparison to be lawful

### 3.1 The ionic worlds

| Item | `jupiter`, `cell`, `base` | `integrated` |
| --- | --- | --- |
| Model | The inner tissue model, version 3, with no kind and no operator | The same |
| Integrator | RK4, the classical one. **Declared order 4** | The same |
| Steps h₁, h₂, h₃ | 25, 12.5 and 6.25 µs | 100, 50 and 25 µs |
| Retry step | 3.125 µs | 12.5 µs |
| Why these steps | The channel law's own bound for RK4 is 25 µs, so legacy's 100 and 50 µs are refused by the model | No gated channel, so the model admits 100 µs |
| Field solver | By D147's rule (below). `jupiter` and `base` have free field offsets (their `near` and `far` regions), so they declare **the floor variant** of the factored capacitor reduction (label `field_solver_floor`). `cell` has none and declares the factored capacitor reduction itself (label `field_solver`) | No free field offset: the factored capacitor reduction (label `field_solver`) |
| Heat | Integrated by RK4 with the other states. No heat booking is declared | The same |
| Observation times | On the grid. They include every time of `potential_times_s` (§4) | The same |
| Backend | The CPU, double precision | The same |
| Rows | Every accepted row is recorded | The same |

- **The field solver is not part of the equations compared.** It solves the same algebraic field. Which variant a world declares is the standing rule of D147 (D156 for a composite, which follows its inner model): a definition with at least one free field
  offset declares the floor variant, and one with none keeps its own. The builders apply it with `validation/tissue/field_solver_choice.py`'s `declare()`, and never by hand. D147 also asks for its floor guard to be **rerun with constants before the floor variant serves a run of record**, and no rerun is recorded.
  It is a step before the campaign (the protocol's §5). This folder assumes nothing of its outcome.
- **The candidate's own step** need not be legacy's. The two are compared at the same times (§4).
- **A step that an event splits** is one accepted step for each part. The run then has more accepted rows than its grid (`TABLE.md` §3).

### 3.2 The assembly worlds

**The pool run.** For each seed and each cell's pool, the live assembly pool runs the block's definition to 0.02 s. The worlds are
IDs 0 to 63 (`cell`) or 0 to 7 (`base`), the seeds are `pools.<cell>.seeds`, and the initial state is the block's. Each pool
run is recorded as `TABLE.md` §3 says: its 19 final arrays and its event path.

**The event path** of a world and a cell is the list of its committed events, in order: `[time, availability after it]`. The availability is
1 if the number of set bits of the bond mask is at least the number of set bits of the occupied mask, and 0 otherwise. It is 1
before the first event.

**The schedule.** The availability of the channel of that cell, in that world, is the path's: 1 at time 0, and the availability after
each event from that event's time on. An entry that repeats the value before it may be left in or left out. An off-grid change splits the step there.
- **The event times are the pool's doubles.** They are not rounded, shifted or snapped. No captured event lies within 1.8 × 10⁻⁴ of a step
  from a grid point, at any step down to 1.5625 µs, so the clock's near-miss rule cannot refuse one (measured on the snapshot's own pool code).
- **The availability multiplies the channel only.** It touches no gate, pump, leak, junction or face.
- **The pool never reads the ionic side.**
- **`inputs.json`'s `coupling` block** (the label `assembly_observable` and the two levels, 1 and 0) states the rule above. It is informational. No echo compares it: the pool runs' arrays, the path and the schedule are class E, and the label is checked as `inputs.assembly.assembly_observable` (`TABLE.md` §3).

**The ionic worlds judged.** World IDs 0 to 7 of each of the four seeds, for `cell` and for `base`: 32 ionic families each. For
`cell` the pools are judged on all 64 worlds a seed, and the ionic side on 8 of them. Nothing is said of the ionic side of IDs 8 to 63.

### 3.3 The assembly coupling, as decided

**Dated line, 25 November 2026 (the lead's note).** The user decided the form of the coupling (the plan's G-7): a driver runs the live pool and writes its switch path into the ionic world's channel controls. The ionic world stays the inner model, version 3, on RK4. No run informed the decision. An operator on the composite is not built now, and this registration
holds no form of it. A run of one departs from its strings note and is refused. (An earlier draft of this folder, commit 5f550674, registered a second form, with a held availability, as reported only. It is removed, as the simpler thing to judge.)

**The driver is the builder's.** It makes the schedule from the pool run of the same seed, world and cell. What it made is recorded by the ionic run's definition in the run's inputs, by name (`TABLE.md` §3):
- **the assembly observable,** the law that turns a pool's topology into an availability. It is a registered law with an ID and a page, of the family `assembly_observable` (the user's word). Label `assembly_observable`;
- **the composed file's fingerprint;**
- **the pool's seeds;**
- **the switch list,** the changes of availability that the driver wrote, per channel.

## 4. The runs and the compared times

**`inputs.json` lists every registered run:** its name, consumer, family, world, seed index, world ID, step, role and variant.
- **A family** is the three runs of one world (and one seed and world ID) at h₁, h₂, h₃. Its class S entries need all three.
- **Roles:** `judged`, `support` (the restarts) and `plant` (a declared change).
- **The retry's runs** are registered by rule, only when owed (`CRITERIA.md` §7): `<family> h=<step> retry`.
- **Counts:** `jupiter` 6 judged, 1 support, 1 plant. `integrated` 3 judged. `cell` 4 pool, 96 ionic, 1 support. `base` 4 pool, 96 ionic, 1 support, 1 plant. 214 in all.

**Compared times.**
- **`jupiter` and `integrated`,** for every readout but the potentials: i × 10⁻⁴ s, i = 0 … 200 (`history_times`). Every run has a row at each.
- **The potentials** (`voltage`, `phi_out`): the block's `potential_times_s`.
- **`cell`:** 0.02 s. **`base`:** 0.02 s, and for `voltage` and `channel_K` also 0.005 and 0.01 s.
- **A time matches a registered one within 10⁻¹² s** of it. The captured observation times themselves carry a last digit (0.0075 s is held as
  0.007500000000000001 s), so no comparison reads a time by its bits.

## 5. The scales

**The rule** (the numbers are `inputs.json`'s, `worlds.<w>.scales`; the checker recomputes them from the block alone). Let T = `end_s`,
V* = 0.12 V (the gate law's domain), T_K the temperature, z the valence, χ = 1 + |z| F V*/(R T_K), and c* the larger of the two
initial concentrations of the species on the two sides (mM).

| Quantity | Scale |
| --- | --- |
| `leak_x` | max over membranes of P_x A/10⁻¹⁵ × c* × χ × T, in fmol |
| `channel_K` | max over channels of P_max × abundance × A/10⁻¹⁵ × c* × χ × T. Opening and availability are taken as 1 |
| `junction_x` | max over junctions of P_x A/10⁻¹⁵ × c* × χ × T. Gate and availability are taken as 1 |
| `face_x` | max over faces of D_x A/L/10⁻¹⁵ × c* × χ × T |
| `pump` | max over membranes of capacity × T, in fmol of cycles |
| `n_cell_x` | max over cells of the sum of the scales of the routes that touch it, the pump's times its stoichiometry |
| `n_out_x` | max over regions of the same sum, faces included |
| Gates | 1 |
| A passive route's heat | Σ_x (its transfer scale) × 10⁻³ R T_K (1 + |ln(c_a/c_b)| + |z| F V*/(R T_K)), in pJ |
| A pump's heat | capacity × T × 10⁻³ × (|ΔG⁰| + R T_K |ln(ADP Pi/(1000 ATP))| + 3 R T_K (1 + |ln Na ratio| + F V*/(R T_K)) + 2 R T_K (1 + |ln K ratio| + F V*/(R T_K))) |
| `heat_membrane` | max over membranes of the sum of its leak's, pump's and channels' heat scales |
| `heat_junction`, `heat_face` | max over junctions, over faces |
| `voltage` | max |V₀| + max over membranes of (F 10⁻¹⁵/C) Σ_x |z| × the cell's sum of route scales |
| `phi_out` | R T_K/F |
| An entry named `<readout>_summary` | The scale of `<readout>` |
| `energy_identity` | The sum over membranes of `heat_membrane`'s terms (leak, pump, channels), over junctions and over faces, plus the pumps' work, plus the amounts' and the capacitors' terms. Work: Σ over pumps of capacity × T × 10⁻³ × (|ΔG⁰| + R T_K |ln(ADP Pi/(1000 ATP))|). Amounts: Σ over compartments and species of (the sum of the scales of the routes that touch it) × 10⁻³ R T_K (1 + |ln(initial concentration)|), in the numeric mM of the concentration. Capacitors: Σ over membranes of 10¹² C s(`voltage`)² |

**Why this scale.** It is the gross one-way throughput that a readout is formed from, so a rounding or a solver residual relative to it is
the one the arithmetic makes. It comes from the declared values alone. It is at least the magnitude of the captured ledger in every
entry, and far above it where a net flow is the small difference of two large ones (leak of Cl, the faces).

## 6. The rounding count, derived

A transfer y after S steps is the sum of S increments, each a step times a rate.
- **Additions:** a step adds to a stored value at most five times (the engine's own ledger allowance, 2.5 ε a step, is the same count). Each
  rounds at most ε/2 of a value of at most s. So at most 5 (S + 1) ε/2 × s.
- **Rates:** a rate is evaluated with at most 64 roundings of terms no larger than the gross one-way rate. Over the run the steps sum to the gross throughput,
  which s holds. So at most 64 ε/2 × s, with no factor S.
- **Feedback:** a state's own rounding moves a rate by less than one part in a hundred of the first bound.
- **Total:** at most (5 (S + 1) + 64 + a hundredth of the first) ε/2 × s, which is at most 16 (S + 1) ε/2 × s for S ≥ 8.

So **e_round(S) = 8 ε (S + 1) s**, FR-38's form (`8 ε S s`), with this derivation.

**The closure bound** is on the potentials that a field solver leaves in error, and not on its current residual.
- **A node's charge.** The live model accepts a node whose relative charge residual is at most 2 × 10⁻¹² (its declared `CHARGE_RTOL`). That is a potential error of at most 2 × 10⁻¹² of the potential, so at most 2 × 10⁻¹² V*. Legacy forms a membrane's voltage from its charges directly, with no solve to leave an error.
- **A free offset** (the `near` and `far` regions). A current residual R_k at a component is a potential error δ_k ≤ |R_k|/ΣG_k, with ΣG_k the conductances of the faces and junctions incident to it. Legacy accepts |R_k| at most 2 × 10⁻¹² of the largest diffusion or drift current of any route (its own rule, with a negligible absolute 10⁻²³ A), and the live default solver at most
  0.01 × 2 × 10⁻¹² of the largest net route current. A route's diffusion or drift current is at most its own conductance times a driving force, which is a diffusion potential (R T_K/F) |ln (concentration ratio)| or a voltage, and both are below V*. No conductance anywhere exceeds the smallest ΣG_k (it is 0.53 of it at most, from the declared values of the JUPITER cluster). So δ_k ≤ 2 × 10⁻¹² V*.
- **The floor variant** (`jupiter`, `base`) also accepts |R_k| ≤ 10³ ε Σ G (|φ_s| + |φ_r|) over the routes incident to k. So δ_k ≤ 10³ ε × 2 max|φ| = 4.4 × 10⁻¹³ max|φ| ≤ 4.4 × 10⁻¹³ V*, below the share above.
  **The cap is not a small current residual:** in the JUPITER cluster, at the declared initial values, it is 15 to 29 times 2 × 10⁻¹² of the largest current (1,550 to 2,930 times the default solver's target, and D147 measured 8 to 2,200 on another tissue). The route currents there nearly cancel, so the same cap is a potential error of 1.1 × 10⁻¹⁶ V. A bound on the current residual would not hold for the floor variant, and this one does.
- **What it does to a readout.** A potential error δ moves a flux by at most |z| F δ/(R T_K) of its gross one-way rate, which is a share δ/V* × (χ − 1)/χ of the scale s, since s holds χ. So at δ ≤ 2 × 10⁻¹² V* it is at most 2 × 10⁻¹² s. **e_close = 4 × 10⁻¹² s** is two codes at that share.

## 7. The references

**The legacy captures,** `/mnt/workspaces/Cells/legacy-captures-20261125/`, read-only. `legacy_part1.json` pins them: the sha256 of
the science set's `MANIFEST.json`, the origin's manifest and the snapshot's. Every file the judge reads is in that manifest with its sha256.
- **`jupiter`:** `runs/jupiter_baseline-{h,h2,h4}` and `runs/jupiter_pump_release-{h,h2,h4}`: `history.*` at the compared rows, `observations.*` for the
  potentials. h is 100 µs, h/2 50 µs, h/4 25 µs.
- **`cell`:** `runs/cell-{h,h2,h4}-s{0..3}/checkpoint/state.npz` and `result.json` (`final_voltage_V`).
- **`base`:** `runs/cluster_base-{h,h2,h4}-s{0..3}/checkpoint/state.npz`, and `observations/tick-*.json` at the ticks of 5, 10 and 20 ms. h is 50 µs.
- **The pools:** the same checkpoints, and `reference_paths.json`.

**The legacy side's own classes** are in `legacy_part1.json`, by the rule of `CRITERIA.md` §4.3 with `inputs.json`'s scales. Every one of the
entries of `jupiter`, `cell`, `base` and `integrated` is **unresolved**: both of its step-halving differences are below the threshold. The largest observed differences are
about one part in 10¹² of the gross scale. So the reference side has no order to judge. Its error estimate U_l still enters the band.

**`integrated`:** `extra-49529e71/runs/finite_junction_cluster-{h,h2,h4}` (`legacy_part1.json` `integrated_capture` pins its manifest and its origin's), at h, h/2 and h/4 of 100 µs. It was captured at the pre-cleanup revision, where legacy's source equals the
snapshot's byte for byte (the lead's and the plan's statement, and the author's `git diff`). Its definition is the configuration, unchanged.

**The captures' machine** is `legacy_part1.json`'s `cpu_model`. Class E holds on that machine.

**An independent reference** exists for the JUPITER cluster and, with a prescribed availability, for `base` (`PART2.md` §12): a scalar ODE of the same equations with no engine import. It corroborates the captures before any run (agreement with the captured h/4 rows within
3 × 10⁻⁹ relative and 3 × 10⁻¹² absolute, its own registered criterion). A disagreement is a C0 fault of the references. It does not cover `cell` or `integrated` as they stand, nor the pools. It decides nothing on the candidate's side.

## 8. The rehearsal set

`inputs_rehearsal.json` has `inputs.json`'s schema, with its own worlds and runs, named `inv_<name>`, and none of this folder's volumes, amounts, permeabilities,
rates, seeds, times or steps. It holds, at least:
- a two-cell cluster with a pump schedule **and free field offsets** (class S, R, D, the potentials; it is the one that exercises the floor variant of the solver), a one-cell assembly world and a two-pool assembly world (class E on the pool, the path and a restart), and a
  small cluster of gated junctions with a schedule;
- one family on the engine's IMEX integrator (declared order 2), at steps where its order is resolved. No RK4 family can be resolved at an admissible step, and the resolved branch of class S must be exercised;
- one restart, one refusal of each kind (`TABLE.md` §4), and one run stopped by the engine's own check;
- a step and a horizon that are not this folder's. Every number that a world sets is read from `inputs_rehearsal.json`, never from this text.

The reference side of the rehearsal is the frozen legacy snapshot, run on those definitions by the rehearsal's runner.
