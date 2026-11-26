# Using the site-occupancy references: R-ode, R-closed, R-qss, R-eq and R-dG (interface only)

How to run the independent references for `cells.operator.site_occupancy@1` (FR-3) and read their outputs without
reading their source. They were written from
[SITE_OCCUPANCY_DESIGN.md](../../docs/SITE_OCCUPANCY_DESIGN.md) and the rulings of D169, without
reading the operator, its fixtures or its tests:
- Appendix A, with §2, §3.3, §4.2 and §4.3;
- §8's acceptance;
- §12's as-built trace rule;
- for R-dG, the booking rules of D152's Appendix A
  ([SHARED_INVENTORY_REACTIONS_DESIGN.md](../../docs/SHARED_INVENTORY_REACTIONS_DESIGN.md)).

Readings of the note are listed under [Readings](#readings-of-the-design-taken-here); disagreements
go to the lead.

| Module | Reference | What it gives |
| --- | --- | --- |
| `validation/occupancy/site_reference.py` (`sr`) | R-ode | The world, its rules (the domain and the trace rule), free energies, and the integration of A.2 with heat and work, the closure, the floor and the background guard |
| `validation/occupancy/site_closed.py` (`sc`) | R-closed, R-qss | A.4's closed forms (fixed c, the closed node's Riccati form and depletion quadratic, internalisation) and D150's saturable sink with A.5's unit map |
| `validation/occupancy/site_equilibrium.py` (`se`) | R-eq | The passive equilibrium per facing node and the total heat G(start) − G(eq) |
| `validation/occupancy/site_bookings.py` (`sb`) | R-dG | An independent half-step of the site network with its checks, classes and bookings (§3.3, §4.2), the 50-digit ΔG, and consecutive half-steps |
| `validation/occupancy/occupancy_crosschecks.py` | – | The driver behind the measured numbers below (`--out DIR`) |

**Self-tests:** `tests/unit/test_occupancy_references.py`, 20 tests, tier 1, about 9 s. They also
check that nothing here imports `cells` or `validation.tissue` (the engine's fixtures live there).
The one import from another reference is `validation.coupling.piecewise_ode`.

## Conventions

- **Units are @3's:** fmol, pL, mM (= fmol/pL), s, pJ.
- **RT is an input** (`World.rt_pJ_per_fmol`, 1e-3 R T). Pass the engine's own value. The tests use
  2.5775 for orientation only.
- **N_f** = 602,214,076 sites per fmol (`sr.N_F`). Pass S directly, or copies, sites per copy and
  the accessible fraction (S = α ν N / N_f).
- **One ligand per world.** Version 1's ligands do not compete, so a world of several ligands is
  several independent worlds.
- **Nodes** are the engine's cells and finite outside nodes alike. Each declares its volume and its
  initial free ligand amount, which is > 0: an absent ligand is its trace.
- **Populations** name the node they face and, for internalisation, the node that receives the
  cargo. Map the engine's owners onto them as follows:

  | Engine owner | `facing` | `receiving` |
  | --- | --- | --- |
  | An outward-facing patch | The patch's outside node | Its cell, if internalisation is declared |
  | An inward-facing patch | Its cell | – |
  | A contact, on a side | That side's cell | – |

- **Multipliers** are piecewise-constant schedules `((t_start, m), ...)` from 0, one for binding and
  one for internalisation per population. A binding multiplier scales k_on and k_off together.
- **The heat is booked at the facing node,** as the engine books it:
  - the engine's `site_dissipated_energy_pJ` [cell] holds the heat of populations facing a cell;
  - `site_outside_dissipated_energy_pJ` [outside] holds the heat of those facing an outside node;
  - work is per population.

## R-ode: `sr.integrate`

```python
from validation.occupancy import site_reference as sr
world = sr.World(rt_pJ_per_fmol=RT,
                 nodes={"ecs": sr.Node(volume_pL=1.0, ligand_fmol=1e-3),
                        "cell": sr.Node(2.0, 2e-15)},
                 populations={"r": sr.Population("ecs", k_on_per_mM_per_s=1e4, k_off_per_s=10.0,
                                                 sites_fmol=3e-4, initial_occupancy=0.5,
                                                 k_int_per_s=10.0, receiving="cell")},
                 trace_mM=1e-15)
run = sr.integrate(world, t_end, record=(...), rtol=1e-12, method="Radau")
run.at[t]["n_fmol"]["ecs"], run.at[t]["B_fmol"]["r"], run.at[t]["heat_pJ"]
```

- **`integrate(world, t_end, record=(), rtol=1e-12, method="Radau", atol_fraction=1e-6, trace_rule=True)`.**
  - Each state's absolute tolerance is rtol × atol_fraction × its own scale: n_i(0) for a ligand row,
    S for a pool. So trace rows and nearly saturated pools keep their relative accuracy.
  - Every record time and multiplier change is an integration end point.
  - `method="DOP853"` (rtol 1e-13) is the cross-check. It is faster in non-stiff worlds.
- **A record** `run.at[t]` holds:

  | Key | Content |
  | --- | --- |
  | `n_fmol`, `c_mM` | Free ligand per node |
  | `B_fmol`, `R_fmol`, `occupancy` | The pools and B/S per population |
  | `bound_net_fmol` | The binding extent (the engine's `site_bound_net_fmol`) |
  | `internalised_fmol` | The engine's `site_internalised_fmol` |
  | `binding_rate_fmol_per_s`, `internalisation_rate_fmol_per_s` | The net J and I with the multipliers in force from t on; each also as `*_left_*`, the multipliers just before t |
  | `heat_pJ`, `work_pJ` | The exact path's integrals, in total |
  | `heat_by_node_pJ`, `heat_by_population_pJ`, `work_by_population_pJ` | The same per facing node (the sum over the populations facing it, as the engine books heat) and per population |
  | `free_energy_change_pJ`, `node_free_energy_change_pJ`, `site_free_energy_change_pJ` | ΔG from t = 0 (increment form) |
  | `closure_pJ` | W − H − ΔG, the integration's own balance |
  | `moiety_residual_fmol`, `material_residual_fmol`, `material_total_fmol` | The identities' residuals |

  `run.observe(t)` gives the same record at any t.
- **The heat** is integrated in a regular form that is finite at B = 0, the default start. It uses
  the identity J ln(R/B) = I ln(R/B) − d/dt[R ln(R/S) + B ln(B/S)], per population, and reports
  the boundary term exactly.
- **The closure is not evidence for H.** The I ln(R/B) term enters H and W alike, so W − H − ΔG
  cannot see an error in it. What checks H and W separately is R-dG's share heat converging to
  them at second order (Measured below).
- **`sr.check_world(world, trace_rule=True)`** refuses:
  - k_on ≤ 0 and k_off ≤ 0 (irreversible binding);
  - k_int < 0, or internalisation without a receiving node;
  - S ≤ 0, α outside (0, 1], θ₀ outside [0, 1], n ≤ 0 or V ≤ 0;
  - a bad schedule;
  - **the trace rule, as built (§12):** with a declared `trace_mM`, every node's initial
    concentration must be at or above it, to 1e-12 relative, and the trace at most 1e-6 K_d of
    every population. `trace_rule=False` admits such a world for reference-side studies only.
- **`sr.compare(a, b, record)`** gives the max |difference| per observable between two runs.
- **`sr.floor(world, t_end, record, rtol=1e-12, method="Radau", factor=100)`** gives (run, tight run,
  differences): the run's own error on the engine's world.
- **`sr.background_guard(world, t_end, record, factor=1e3)`** is Q5's guard on the reference side:
  the world against itself with the trace, and every node at the trace, lowered by `factor`.
- **Free energies:**
  - `sr.node_free_energy`, `sr.site_free_energy`, `sr.node_increment` and `sr.pool_increment`
    (§3.3's stable forms);
  - `sr.exact_free_energy_change(world, start, end, digits=50)`.

## R-closed and R-qss: `site_closed` (`sc`)

| Function | Gives |
| --- | --- |
| `sc.association(t, B0, S, c, k_on, k_off)` | B(t) at fixed c: B_eq + (B₀ − B_eq) e^(−(k_on c + k_off) t) |
| `sc.dissociation(t, B0, k_off)` | B₀ e^(−k_off t), into a node held near zero (it neglects rebinding, of relative size c_released/K_d) |
| `sc.internalisation_fixed(t, B0, S, c, k_on, k_off, k_int)` | (B(t), U(t)) at fixed c |
| `sc.depletion(t, B0, n0, S, V, k_on, k_off, exact=False)` | The closed node's Riccati B(t); `exact=True` gives 50 digits |
| `sc.depletion_roots(N, S, K_d, V)` | (r₋, r₊). r₋ is the depleted equilibrium: the quadratic binding equation |
| `sc.free_concentration_closed(n_total, S, K_d, V)` | The closed node's equilibrium c |
| `sc.langmuir(S, c, K_d)` | S c/(K_d + c) |
| `sc.depletion_term(S, V, K_d, c)` | S/(V (K_d + c)): what a fixed-c form neglects (§8.3) |
| `sc.sink_constants(S, V, k_on, k_off, k_int)` | A.5's unit map: a = k_int S, K_M = (k_off + k_int)/k_on, b = K_M V |
| `sc.epsilon(S, V, k_on, k_off, k_int, c0)` | (S/V)/(K_M + c₀) |
| `sc.sink_amount(t, n0, a, b)` | D150's saturable sink, the root of b ln(n₀/n) + (n₀ − n) = a t |
| `sc.sink_half_time(n0, a, b)` | (b ln 2 + n₀/2)/a |
| `sc.quasi_steady_bound(S, c, K_M)` | S c/(K_M + c): the pre-formed occupancy of Q1 |

**Q1's reference side** (R-ode against R-qss) compares the free node amount n(t), with B₀ at its
quasi-steady value at c₀, rates fixed and S varied. See `occupancy_crosschecks.q1` for the world.
- The error is O(ε) after the initial layer, which the quasi-steady start suppresses.
- The local ε grows as c falls, so the order is measured over two of the sink's half-times.

## R-eq: `se.equilibrium(world)`

- **Scope:** worlds without internalisation; it refuses any population with k_int > 0.
- **Method:** for each facing node, one monotone root, c V + Σ_k S_k c/(K_d,k + c) = N, polished in
  50 digits.
- **Returns:**
  - `c_mM`, `n_fmol`, `B_fmol`, `R_fmol` and `occupancy`;
  - `node_heat_pJ` and `heat_pJ`: G(start) − G(eq), the closed relaxation's total heat;
  - `delta_G_pJ`;
  - `langmuir_at_start`, the large-V isotherm at the starting c;
  - `depletion_term` at equilibrium.

## R-dG: `sb.half_step(world, n, B, R, h, mb=None, mi=None, theta=0.5)`

One half-step of length h (dt/2) from the arrays n [nodes], B and R [populations], in the world's
declaration order, with multipliers mb and mi [populations] (default 1). It returns a `HalfStep`:

| Field | Meaning |
| --- | --- |
| `start`, `end`, `accepted`, `delta` | (n, B, R) arrays. `end` is the candidate. An idle component selects its start bitwise. `delta` = ν Δξ |
| `extent_binding`, `extent_internalisation` | Δξ per population |
| `stages`, `stage_binding`, `stage_forward`, `stage_reverse`, `stage_internalisation`, `stage_affinity` | Y1, Y2, Y3, and J, J⁺, J⁻, I and A = ln(cR/(K_d B)) at each stage |
| `end_affinity`, `sign_margin` | A at the end; min abs(A) over the stages and the end (treat the branch as rounding-ambiguous below about 1e-10) |
| `hL`, `stage_condition_ok`, `positive_ok`, `finite_ok`, `admitted` | h max L per stage and component; the checks |
| `component_class` | Per static component: `"idle"`, `"passive"` or `"mixed"` |
| `non_reversing`, `branch` | Per population: `"node"` (passive-only), `"share"` or `"quadrature"` (mixed), `"off"` (binding multiplier 0 in a mixed component), `"idle"` |
| `heat_share`, `heat_quadrature`, `share_binding`, `share_internalisation`, `mu_bar` | Both candidate heats, the route shares and the divided-difference potentials |
| `route_heat`, `heat` [nodes], `work` [populations] | The bookings: heat at each facing node, and work per population |
| `delta_G`, `delta_G_terms`, `heat_terms`, `ledger_residual` | Per component: ΔG (increment form), the rounding scales, and ΔG + H − W |

`h.named("heat")` returns a field as a dict by name. There are two companions:
- `sb.exact_delta_G(world, n, B, R, dn, dB, dR)` gives ΔG per component in 50 digits, from the
  engine's own start and change. An unchanged row contributes exactly 0.
- `sb.run_half_steps(world, h, count, multipliers=None)` runs consecutive half-steps from the
  initial state, with cumulative heat, work and extents. That is the engine's evolution in a
  face-free world, two half-steps per dt. `multipliers(k)` returns (mb, mi) for half-step k.

**Use for the engine's per-step ΔG test (§3.4 item 2):**
1. On random states, give the engine's half-step and R-dG the same (n, B, R, h, mb, mi).
2. Compare the end states, the classes and branches (watch `sign_margin`), and the booked heat per
   node and work per population. Use the scales `delta_G_terms + heat_terms`.
3. Check the engine's ΔG against `exact_delta_G` from the engine's own change.

## Measured, and recommended settings

These are from the full cross-check runs (see Evidence) on CPU 0.

| Check | Result |
| --- | --- |
| Q1, R-ode against R-qss, error of n₀ at ε = 0.1, 0.01, 0.001 | 2.1224e-2, 2.2214e-3, 2.2316e-4: **orders 0.980 and 0.998** (the note's prototype also reports 0.98 and 0.998; it was not blind) |
| R-ode's floor (Radau rtol 1e-12 and DOP853 rtol 1e-13, against DOP853 rtol 3e-14 with atol × 1e-3) | n ≤ 1.3e-14 of n₀; B and R ≤ 1.9e-14 of S; heat and work ≤ 4.4e-17 pJ |
| Q2, R-eq against R-ode at 300 s | B within 2.3e-14 relative; the heat within 6e-11 relative (large V) and 9e-16 (small V) |
| R-eq against the depletion quadratic (small V) | 2.2e-16 relative |
| Q3, the Riccati form against R-ode | 1.1e-15 of S |
| Q3, internalisation at fixed c in V = 1e4 pL | 1.5e-6 of S, within its depletion term 3.3e-6 |
| Q4, θ(α)/θ(1) at α = ½, ¼ | α to 4e-7 at c ≪ K_d (depletion term 1.7e-6); to 4e-11 at c = 100 K_d |
| Q4, saturation at c = 100 K_d | 0.990 α |
| Q4, relaxation rate | Independent of α to 1.2e-6 |
| R-dG on 4,000 random states (mixed world, a cell receiving and faced) | Ledger ≤ 0.41 ε × scale; ΔG ≤ 0.91 ε × terms against 50 digits; no negative heat; every branch reached (share 2,553; quadrature 68; node 3,532; off 1,345; idle 502) |
| R-dG half-steps against R-ode (ε = 0.1, T = 0.128 s) | n errors 1.43e-8, 1.72e-9, 2.10e-10, 2.60e-11 of n₀ at dt = 8, 4, 2, 1 ms: **third order (8.35, 8.17, 8.09)**. Heat second order (3.87, 3.94, 3.97) |
| R-dG, two populations in one mixed component (a cell receiving and faced), T = 0.064 s | Heat at each facing node and work per population, second order (3.94 to 3.99 from dt = 8 to 0.5 ms) |
| R-dG, a washout through the binding equilibrium (one quadrature step per run; §3.3's reversal onset, documented and not judged) | Heat errors 1.8e-10, 4.9e-11, 1.3e-11, 3.2e-12 pJ at dt = 4 to 0.5 ms, against a heat of 9.7e-8 pJ: the hybrid converges through the reversal |
| Q1's world at α = ½ (copies fixed, so S and ε halve) against R-qss with V_max ∝ α and K_M unchanged | Error of n₀ 1.09e-2, against 2.12e-2 at α = 1: ratio 1.95, O(ε) |

**Recommended settings:**
- **Radau at rtol 1e-12, the judged reference (§8.2).**
- **DOP853 at rtol 1e-13 as the cross-check.** It is faster in non-stiff worlds and has the lower
  floor.
- **Judge an engine order only where its errors stand above the floor.** On these worlds that is
  about 1e-14 of n₀. Measure the floor on the engine's own worlds with `sr.floor`.

## Readings of the design taken here

- **For a rounding-level comparison with the engine,** pass the engine's own S through
  `sites_fmol`. Forming α ν N / N_f in another order differs in the last bits.
- **The trace bound is inclusive and has no tolerance.** A trace of exactly 1e-6 K_d is admitted.
  The concentrations' bound has 1e-12 relative, as built.

1. **Positivity at stages.** Free rows must stay > 0, and pools ≥ 0. B = 0 and R = 0 are in the
   domain (§4.3).
2. **A binding route with a zero multiplier in a mixed component** books exactly 0 heat (branch
   `"off"`). Its population's work is its internalisation share.
3. **The class rule.** A component is mixed when an internalisation route with a positive
   multiplier exists, whatever its rate. It is idle when every route's multiplier is 0.
   Internalisation joins a population's component only where it is declared (a receiving node).
4. **A pool at a = 0 with no change** has an unused divided-difference potential, set to μ°.
5. **The stage condition is inclusive:** h L ≤ ½ is admitted.
6. **The quadrature candidate at a stage with B = 0 (or R = 0) is +∞,** and is reported so. The
   engine pads it finite. It is selected only when the route reverses within the step, which a
   start from B = 0 does not do.
7. **Readouts at a multiplier change.** The rates are given with the multipliers from t on, and as
   `*_left` with those before t. **Ask the lead which side the engine's rows show.**
8. **Q1's horizon** is two of the sink's half-times, read from "run to two depletion half-times"
   (§4.5).
9. **Q4's negative controls (K) and (A)** are the engine's edits. The references model only the
   capacity form (C).

## Known limits

- **Not modelled:**
  - other writers of the ligand rows (turnover, exchange, faces);
  - charged ligands;
  - competition;
  - scheduled parameters.
  "+ (other writers)" in A.2 is outside these references.
- **The heat at R = 0 with internalisation:** every site bound at the start, θ₀ = 1. There ln R is
  floored at the smallest normal float.
- **Cost.** The right-hand sides are NumPy on small arrays. Radau in Q1's worlds takes about 4 s per
  run, and DOP853 0.3 to 5 s.

## Evidence

`/mnt/workspaces/Cells/independent-references-20261115-01/` (HANDOFF.md): `occupancy-crosschecks-02/`
(crosschecks.json, log.txt), run from the frozen snapshot `occupancy-snapshot-02` (86064dae). The
first run, `occupancy-crosschecks-01/` from c5ac9986, gave the same numbers without the per-node,
washout and α items.
