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
| `integrated` | The integrated ensemble's world: seven cells, twelve gated junctions, one finite outside region, no pump, leak or channel | `integrated` | Same. **Its capture is pending** (§7) |

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
| Field solver | The factored capacitor reduction (label `field_solver`) | The same |
| Heat | Integrated by RK4 with the other states. No heat booking is declared | The same |
| Observation times | On the grid. They include every time of `potential_times_s` (§4) | The same |
| Backend | The CPU, double precision | The same |
| Rows | Every accepted row is recorded | The same |

- **The candidate's own step** need not be legacy's. The two are compared at the same times (§4).
- **A step that an event splits** is one accepted step for each part. The run then has more accepted rows than its grid (`TABLE.md` §3).

### 3.2 The assembly worlds

**The pool run.** For each seed and each cell's pool, the live assembly pool runs the block's definition to 0.02 s. The worlds are
IDs 0 to 63 (`cell`) or 0 to 7 (`base`), the seeds are `pools.<cell>.seeds`, and the initial state is the block's. Each pool
run is recorded as `TABLE.md` §4 says: its 19 final arrays and its event path.

**The event path** of a world and a cell is the list of its committed events, in order: `[time, availability after it]`. The availability is
1 if the number of set bits of the bond mask is at least the number of set bits of the occupied mask, and 0 otherwise. It is 1
before the first event.

**The schedule.** The availability of the channel of that cell, in that world, is the path's: 1 at time 0, and the availability after
each event from that event's time on. An entry that repeats the value before it may be left in or left out. An off-grid change splits the step there.
- **The event times are the pool's doubles.** They are not rounded, shifted or snapped. No captured event lies within 1.8 × 10⁻⁴ of a step
  from a grid point, at any step down to 1.5625 µs, so the clock's near-miss rule cannot refuse one (measured on the snapshot's own pool code).
- **The availability multiplies the channel only.** It touches no gate, pump, leak, junction or face.
- **The pool never reads the ionic side.**

**Where the schedule is made.** The builder's driver makes it, from the pool run of the same seed. If an operator of the composite
makes it instead (Part 2), that form is judged in Part 2. Part 1 registers the schedule form and nothing else.

**The ionic worlds judged.** World IDs 0 to 7 of each of the four seeds, for `cell` and for `base`: 32 ionic families each. For
`cell` the pools are judged on all 64 worlds a seed, and the ionic side on 8 of them. Nothing is said of the ionic side of IDs 8 to 63.

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

**The closure bound.** Both codes accept a field solve whose relative charge and current residuals are at most 2 × 10⁻¹²: the live model's
declared `CHARGE_RTOL` and `CURRENT_RTOL`, and legacy's own normalised residual at most 1 with the same constant. A potential in error by that
share moves a flux by at most that share of |z| F V*/(R T_K) of its gross one-way rate, which the scale already holds in χ.
So **e_close = 4 × 10⁻¹² s**, two codes at 2 × 10⁻¹² each.

## 7. The references

**The legacy captures,** `/mnt/workspaces/Cells/legacy-captures-20261125/`, read-only. `legacy_part1.json` pins them: the sha256 of
the science set's `MANIFEST.json`, the origin's manifest and the snapshot's. Every file the judge reads is in that manifest with its sha256.
- **`jupiter`:** `runs/jupiter_baseline-{h,h2,h4}` and `runs/jupiter_pump_release-{h,h2,h4}`: `history.*` at the compared rows, `observations.*` for the
  potentials. h is 100 µs, h/2 50 µs, h/4 25 µs.
- **`cell`:** `runs/cell-{h,h2,h4}-s{0..3}/checkpoint/state.npz` and `result.json` (`final_voltage_V`).
- **`base`:** `runs/cluster_base-{h,h2,h4}-s{0..3}/checkpoint/state.npz`, and `observations/tick-*.json` at the ticks of 5, 10 and 20 ms. h is 50 µs.
- **The pools:** the same checkpoints, and `reference_paths.json`.

**The legacy side's own classes** are in `legacy_part1.json`, by the rule of `CRITERIA.md` §4.3 with `inputs.json`'s scales. Every one of the
entries of `jupiter`, `cell` and `base` is **unresolved**: both of its step-halving differences are below the threshold. The largest observed differences are
about one part in 10¹² of the gross scale. So the reference side has no order to judge. Its error estimate U_l still enters the band.

**`integrated` is pending.** Its capture is being taken (the lead, 25 November 2026), at h, h/2 and h/4 of 100 µs. When it exists, the same rule gives its
classes, in a dated file `legacy_integrated.json` with its own tag, before the registration. Until then the consumer is not judged, and not passed.

**The captures' machine** is `legacy_part1.json`'s `cpu_model`. Class E holds on that machine.

**An independent reference** exists for the JUPITER cluster and, with a prescribed availability, for `base` (`PART2.md` §12): a scalar ODE of the same equations with no engine import. It corroborates the captures before any run (agreement with the captured h/4 rows within
3 × 10⁻⁹ relative and 3 × 10⁻¹² absolute, its own registered criterion). A disagreement is a C0 fault of the references. It does not cover `cell` or `integrated` as they stand, nor the pools. It decides nothing on the candidate's side.

## 8. The rehearsal set

`inputs_rehearsal.json` has `inputs.json`'s schema, with its own worlds and runs, named `inv_<name>`, and none of this folder's volumes, amounts, permeabilities,
rates, seeds, times or steps. It holds, at least:
- a two-cell cluster with a pump schedule (class S, R, D, the potentials), a one-cell assembly world and a two-pool assembly world (class E on the pool, the path and a restart), and a
  small cluster of gated junctions with a schedule;
- one family on the engine's IMEX integrator (declared order 2), at steps where its order is resolved. No RK4 family can be resolved at an admissible step, and the resolved branch of class S must be exercised;
- one restart, one refusal of each kind (`TABLE.md` §4), and one run stopped by the engine's own check;
- a step and a horizon that are not this folder's. Every number that a world sets is read from `inputs_rehearsal.json`, never from this text.

The reference side of the rehearsal is the frozen legacy snapshot, run on those definitions by the rehearsal's runner.
