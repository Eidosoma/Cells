# Using the coupling references: R-fac, R-state, R-cell and R-feedback (interface only)

How to feed the independent references for `cells.operator.species_regulated_availability@1` and read their
outputs without reading their source. They were written from Appendix A of
[INVENTORY_COUPLING_DESIGN.md](../../docs/INVENTORY_COUPLING_DESIGN.md), with §4.3 and §4.4, from
S5's Appendix A ([CELL_DIVISION_S5_DESIGN.md](../../docs/CELL_DIVISION_S5_DESIGN.md), A.1 to A.3)
and from D150's turnover law
([SECRETED_SPECIES_TRANSPORT_DESIGN.md](../../docs/SECRETED_SPECIES_TRANSPORT_DESIGN.md) §2.2).
Their author never read the operator, its Hill helper or their tests. Readings of the design are
listed under [Readings](#readings-of-the-design-taken-here); disagreements go to the lead.

| Module | Reference | What it gives |
| --- | --- | --- |
| `validation/coupling/factor_reference.py` | R-fac | Every factor law, side and basal combination in linear space: a float64 path and a 40-digit decimal path rounded once; ulp and eps comparisons |
| `validation/coupling/state_reference.py` | R-state | The two-state fraction's closed forms, D150's turnover regulator, nested quadrature, an adaptive integration of (s, U), the crossing time t* and the crossing step k* |
| `validation/coupling/cells_reference.py` | R-cell, R-feedback | Pump-free constant-field cells with regulated availabilities on channel populations and contacts, the regulatory states integrated with the ions |
| `validation/coupling/piecewise_ode.py` | – | The shared segment-by-segment integrator (internal) |
| `validation/coupling/reference_crosschecks.py` | – | The driver behind the numbers in [Tolerances](#recommended-settings-and-the-measured-floor) (`--out DIR`; about 1.5 minutes) |

Self-tests: `tests/unit/test_coupling_references.py` (tier 1, about 12 s). They also check that
nothing in this folder imports `cells`, statically and in a fresh process, and that the only
thing taken from `validation.division` is R-full's flux law `ghk_flux` (the J2 bright line holds:
no J1 input and no partition).

## Conventions

- **Units** (@3's and S5's): amounts fmol, volumes pL, concentrations mM (= fmol/pL = mol/m³),
  time s, permeabilities m/s, areas m², capacitances F, potentials V, currents A, rates 1/s.
- **Constants are inputs.** `rc.Constants(faraday_C_per_mol, gas_J_per_mol_K, temperature_K)`.
  The tests pass the exact SI products N_A e and N_A k_B (S5's); pass the engine's own values.
- **Laws** (A.2): `hill_activation` x^n/(K^n + x^n), `hill_inhibition` K^n/(K^n + x^n),
  `state_fraction` s, `state_complement` 1 − s. A coupling's factor is F = b + (1 − b) f with
  0 ≤ b < 1, and exactly 1 while it is switched off.
- **Sides** (§1.3, ruling 4): `"first"` reads the contact's `cells[0]` (@3's `junction_sender`),
  `"second"` its `cells[1]` (`junction_receiver`), and `"both"` is F(first) × F(second) with the
  basal level applied on each side before the product. A population has no side (`None`).
- **Declared order.** An element's routes multiply left to right in the order of the world's
  `couplings` dict, G = (F₁ F₂) F₃ …, and a_eff = a_sched × G with G formed first.
- **One element per coupling.** A design coupling with several `ids` is several reference
  couplings, one per id, at the same position in the declared order.
- **Inputs are never modified**; results are new objects.

## R-fac: `factor_reference` (`fr`)

```python
from validation.coupling import factor_reference as fr
f = fr.law_value("hill_activation", x=c, K=K, n=n)           # f, float64, numpy-broadcast
F = fr.coupling_factor("hill_inhibition", b, x=c, K=K, n=n)  # b + (1 - b) f; enabled=False -> 1
F = fr.coupling_factor("state_complement", b, s=s)
Fe = fr.side_factor("both", "state_complement", b, first=s_a, second=s_b)
a = fr.effective_availability(a_sched, [F1, F2])             # a_sched * ((F1 * F2))
ref = fr.exact_grid("hill_activation", b, x=c_grid, K=K, n=n)  # the reference values (float64)
d = fr.exact_side_factor("both", "hill_activation", b, first=c_a, second=c_b, K=K, n=n)  # Decimal
fr.to_float(d); fr.exact_product([d1, d2], a_sched=0.5)      # one rounding at the end
fr.ulp_distance(engine, ref); fr.eps_error(engine, ref)      # uint64 ulps; |diff| / 2.22e-16
```

- **The reference values for A1 are the exact path's**: `exact_grid`, or `to_float(exact_*)`. They
  are the true law at the float64 inputs, within half an ulp. Inputs may be floats (converted
  exactly), strings or Decimals.
- **The float64 path** is within 2 + ⌈n/2⌉ ulps of the exact path. Measured: ≤ 2 ulps for n ≤ 3,
  3 at n = 4 and 6 at n = 8, over x from 0 and 1e-300 to 1e10, K ∈ {1e-4, 0.37, 12}, b ∈ {0, 0.2}.
  pow amplifies the rounding of x/K n-fold.
- **Edge values:** x = 0 gives activation 0 and inhibition 1 exactly, x = K gives 1/2 exactly, and
  there is no overflow at x/K = 1e600.
- **`hill_scalar(law, x, K, n)`:** the same float form at one point, without checks.
- **`log_space_condition(law, x, K, n)`** is a guide for setting A1's tolerance, not a tolerance.
  - It estimates, in eps, the relative error that the conditioning of the design's
    z = n (ln x − ln K) form allows (§1.9): |d ln f/dz| = 1 − f, with z rounded to about
    n (|ln x| + |ln K|) eps.
  - It is large in deep tails: up to 5.6e3 eps for activation at n = 8 and x = 1e-10 on the grid
    above, 258 for inhibition.
  - A relative-ulp criterion is therefore strict where f is tiny. `eps_error` gives the absolute
    scale, the relevant one for a multiplier in [0, 1].
- **Refusals** (`ValueError`): x < 0 or non-finite, K ≤ 0, n ≤ 0, s outside [0, 1], b outside
  [0, 1), a schedule outside [0, 1], an unknown law or side, the wrong source for a law.

## R-state: `state_reference` (`rs`)

**Regulators** (anything with `concentration(t)` in mM and `breakpoints()`):
- `rs.Turnover(n0_fmol, volume_pL, segments)`. D150's turnover: segments
  `((t_start_s, production_fmol_per_s, clearance_per_s), ...)`, the first at 0. It has the closed
  form n(t) = n_j e^(−k τ) + (P/k)(1 − e^(−k τ)), carried across segments. Also `amount(t)`,
  `exact_amount(t)` (Decimal) and `concentration(t)` = n/V.
- `rs.clearance(c0_mM, k_per_s, volume_pL=1.0)` and `rs.constant(c_mM, volume_pL=1.0)`.
- `rs.Function(fn, breakpoints=())`: any c(t), for example a D152 network reference's dense output
  for §4.5's first consumer.

**An input** is `rs.Input(law, regulator, K_mM, n)`. A state's u(t) is the product of its inputs,
in order (`rs.input_value(inputs, t)`).

**Closed forms** (float64; `exact=True` returns a 40-digit Decimal):

| Function | Gives |
| --- | --- |
| `rs.quasi_steady(u, k_on, k_off)` | s* = k_on u/(k_on u + k_off); NaN when both rates are 0 |
| `rs.effective_half_saturation(K, n, k_on, k_off)` | K_eff = K (k_off/(k_on + k_off))^(1/n) |
| `rs.frozen(t, s0, u, k_on, k_off, exact=False)` | s* + (s0 − s*) e^(−λt); s0 when λ = 0 |
| `rs.retention(t, s0, k_off)` | s0 e^(−k_off t) |
| `rs.commitment(U, s0, k_on)` | 1 − (1 − s0) e^(−k_on U), any input |
| `rs.clearance_exposure(t, c0, k, K, n, law)` | U(t) under c0 e^(−kt): activation (1/(nk)) ln[(K^n + c0^n)/(K^n + c^n)]; inhibition t minus that |
| `rs.clearance_commitment(t, s0, k_on, c0, k, K, n, law)` | s(t) for k_off = 0 under clearance |
| `rs.clearance_commitment_crossing(θ, s0, k_on, c0, k, K, n, law)` | t*: closed form for activation, Brent's method on the closed U for inhibition; inf if never |
| `rs.frozen_crossing(θ, s0, u, k_on, k_off)` | t* = ln((s* − s0)/(s* − θ))/λ |
| `rs.commitment_level(θ, s0, k_on)` | U_θ = ln((1 − s0)/(1 − θ))/k_on |

**General inputs:**
- `rs.exposure(inputs, t, t_from=0)` gives U by adaptive quadrature, split at every breakpoint.
- `rs.state_quadrature(inputs, k_on, k_off, s0, t)` gives s(t) from the variation-of-constants
  integral, with nested quadrature. It takes tens of milliseconds per t: a cross-check.
- `run = rs.integrate(inputs, k_on, k_off, s0, t_end, record=(...))` integrates (s, U) segment
  by segment. It uses DOP853 at rtol 1e-13 by default; `method="Radau"` gives the exact Jacobian.
  - `run.at[t]` is (s, U) at each record time, each an integration end point.
  - `run.s(t)` and `run.U(t)` give the pair anywhere, by re-integration from the last stored step.
  - `run.crossing(θ)` is t*.
  - `run.crossing_step(θ, dt)` returns `dict(k, t_star, margin_after, margin_before, slope)`.
    - k is k* = min{k : s(k dt) ≥ θ}, from the reference's own s.
    - `margin_after` is s(k* dt) − θ ≥ 0, and `margin_before` is θ − s((k* − 1) dt) > 0.
    - `slope` is the grid estimate of ds/dt there.
  - If a margin is below the engine's error in s at that dt, k* is ambiguous by one step: §4.5's
    widening by δs/(ds/dt).
- **Admitted rates.** Use Radau past about λ t_end = 1e5. Measured on a pulse input:
  - at λ t_end ≈ 2e4, DOP853 took 9,646 steps and Radau 6,462, and DOP853 was faster;
  - at λ t_end ≈ 2e5, they took 44,628 and 5,724 steps, Radau being 3 times faster;
  - the two agreed to 1e-14.

## R-cell and R-feedback: `cells_reference` (`rc`)

```python
from validation.coupling import cells_reference as rc
run = rc.simulate(world, t_end, record=(...), rtol=1e-10, atol=None, method="Radau")
```

### Declaring a `World`

| Class | Fields (units) |
| --- | --- |
| `World` | `constants`, `species` (e.g. `("Na", "K", "Cl")`), `z`, `bath_mM` (held, 0 V), `cells`, `patches`, `populations`, `contacts`, `regulators`, `states`, `couplings` (dicts by name; `couplings` in declared order) |
| `Cell(volume_pL, mM, initial_V=nan, background_fmol=nan)` | Initial concentrations of every species. The start: `initial_V` (V) sets the charge C V₀ and the background follows; or `background_fmol` sets X and V₀ follows; or, with neither, V₀ is the zero-current potential of the cell's routes to the bath at 0+ (its leaks, and its populations at their availability then; contacts excluded) |
| `Patch(cell, area_m2, capacitance_F, permeability_m_s)` | A membrane patch facing the bath, with constant-field leaks P_s per unit area. Every cell needs one. The cell's capacitance is the sum over its patches |
| `Population(patch, permeability_m_s, relative, abundance=1, opening=1, schedule=((0, 1),))` | A gate-free population, P r_s N o a(t) A_k per species. `relative` gives r_s for every species (`cells.channel.kleak_always_open@1`: 1 for K, 0 otherwise). `schedule` is a_sched, piecewise constant from 0 |
| `Contact(cells, area_m2, permeability_m_s, gate=1, schedule=((0, 1),))` | P_s A_e g a(t), with a fixed gate g. The current is reported from `cells[0]` to `cells[1]` |
| `Regulator(amounts)` | `{cell: rs.Turnover}`, each at that cell's volume. A neutral, impermeant species: it enters no transport and no charge |
| `State(cells, inputs, k_on_per_s, k_off_per_s, initial=0.0, crossing_level=nan)` | `inputs`: a tuple of `Input(law, species, K_mM, n)`, read in each of the state's cells (an ion or a regulator). `initial` is one s₀ or `{cell: s₀}` |
| `Coupling(target, law, source, basal=0, K_mM=nan, n=nan, side=None, enabled=((0, 1),))` | `target` is a population or contact name. The `source` of a state law is a state, of a Hill law a species or regulator. `enabled` is the switch schedule, 0 or 1, from 0 |

`rc.check_world(world)` raises `ValueError` for: a missing or duplicate name, non-positive
volumes, concentrations, areas or capacitances, negative permeabilities, a cell with no patch, a
schedule that does not start at 0 or leaves [0, 1], both `initial_V` and `background_fmol`, a side
on a population or none on a contact, a state law reading no state, a Hill law without K and n,
b outside [0, 1), and a source not declared in a cell the coupling or state reads.

### Reading a run

`run.at[t]` holds, for each record time t:

| Key | Content |
| --- | --- |
| `V`, `charge_C` | `{cell: φ}` (V; the bath at 0) and the node charge (C) |
| `amounts_fmol`, `mM`, `background_fmol` | Per cell, every species, in the world's order |
| `regulators_mM` | `{(regulator, cell): c}` |
| `s`, `U`, `u` | `{(state, cell): value}`: the state, its exposure ∫u dt from 0, and its input product |
| `routes` | `{(coupling, element): {F, F_left, F_right}}` |
| `elements` | `{element: {a_sched, G, a_eff, current_A}}`, each also as `*_left` and `*_right`. `current_A` is outward for a population and first to second for a contact |
| `patch_current_A` | `{patch: outward leak current (A)}` |
| `exchanged_fmol` | Cumulative bath-to-tissue exchange per species: the sum over cells of n(t) − n(0) equals it, a conservation check on the contacts |

Further, on the run:
- **`run.initial`** gives `{cell: {V, background_fmol, charge_fmol}}` at t = 0.
- **`run.observe(t)`** gives the same record at any t, by re-integration.
- **`run.crossings`** gives `{(state, cell): t*}` for each state with a crossing level: the first
  t with s ≥ θ, 0 if s₀ ≥ θ, inf if not by t_end.
- **`run.crossing_step(state, cell, dt, theta=None)`** is R-state's k* helper.
- **`run.slots`** is the list of (state, cell) pairs in declared order: states, then each
  state's cells. It is the engine's flat `regulatory_slot` axis (§7.1 item 1).
- **`run.steps`** and **`run.wall_s`** give the work done.

**Both sides of an event time.**
- Every record time and every schedule, switch and regulator-segment start is an integration
  breakpoint, so records are integration end points.
- The state (V, amounts, s, U) is continuous. The quantities that use a schedule or a switch
  (`F`, `a_sched`, `G`, `a_eff`, `current_A`) are given three ways:
  - **unsuffixed: the as-built convention** (§7.1 item 3 with §1.9). A row saved at a switch's
    time shows the switch in force before that time, against the availability schedules from that
    time on. Compare engine rows with these keys.
  - **`*_left`:** switches and schedules just before t.
  - **`*_right`:** switches and schedules from t on.
  - Away from an event time, the three coincide.
- **Changed after §7:** the unsuffixed keys were the `*_right` values. The default now follows the
  as-built convention, and the earlier values remain as `*_right`.
- **Row 0.** The engine's own `_runs` comparison skips row 0 (§7.1 item 3), so compare from the
  first step's row on.

### The two worlds of §4.3, as declared in the self-tests

- **R-cell (A5).**
  - One cell, a patch on the bath, and a population `Population(patch, P, (0, 1, 0))`.
  - A `Regulator({"c0": rs.Turnover(...)})` with a production pulse.
  - A coupling `Coupling("kleak", "hill_inhibition", "X", basal=b, K_mM=K, n=n)`: the instantaneous
    form.
- **R-feedback (A4).**
  - Two cells with patches on the bath, and a `Contact(("a", "b"), A_e, P_e)` with its gate fixed
    open.
  - A state `State(("a", "b"), (Input("hill_activation", "Na", K, n),), k_on, k_off, s0, θ)`.
  - A coupling `Coupling("e", "state_complement", "s1", basal=b, side="both")`.
- The worlds of the floor study are in `reference_crosschecks.py` (`feedback_world`, `cell_world`).

## Recommended settings and the measured floor

**R-cell and R-feedback.** Use `rc.simulate` at its defaults: Radau, rtol 1e-10, and `rc.ATOL`:
- 1e-15 fmol for the charge and 1e-12 fmol for the amounts (R-tissue's tissue-scale values);
- 1e-14 for s, 1e-12 s for U and 1e-12 fmol for the exchange.

Scale `atol` with the world: these suit cells of about 2 pL and 4 pF. The floor is measured
against rtol 1e-12 with atol / 1000, which is the error estimate. The second method is LSODA at
rtol 1e-12, atol / 1000.

| World (synthetic) | V | amounts (fmol) | s | U (s) | F, a_eff | t* (s) |
| --- | --- | --- | --- | --- | --- | --- |
| A4-like feedback, 60 s | 2.8e-16 | 1.9e-12 | 2.3e-12 | 1.9e-13 | 7.1e-13 | 7.8e-16 |
| A4 fast arm, k_on + k_off = 1000/s, 20 s | 4.3e-16 | 5.1e-13 | 1.1e-12 | 1.4e-13 | 2.9e-13 | 3.6e-17 |
| A5-like gated leak, 60 s | 1.5e-12 | 5.7e-13 | – | – | 0 (closed form) | – |
| LSODA against tight Radau, A4-like | 4.7e-15 | 2.4e-10 | 4.1e-12 | 8.2e-11 | 9.8e-13 | 8.0e-13 |

- A two-cell world costs about 1 to 2 s per 60 s of model time at rtol 1e-10 on one core.
- The rtol 1e-12 run costs about three times as much.

**R-state:** the default DOP853 at rtol 1e-13. Measured against the closed forms and quadrature:

| Case | max error |
| --- | --- |
| Frozen input, three λ (DOP853; Radau at rtol 1e-12) | s: 4.0e-15 (3.4e-15); t*: 1.1e-14 s |
| Commitment under clearance, activation and inhibition, n ∈ {1, 2.5, 4}, to 200 s | s: 9.7e-15 (Radau 1.7e-14); U: 7.9e-13; t* relative 8.0e-15 |
| Production pulse with k_off > 0, against nested quadrature | s: 1.4e-14 (Radau 7.8e-15); U: 3.6e-15; t* DOP853 against Radau 8.0e-15 |
| Fast arm, λ up to 1000/s | DOP853 against Radau: 1.3e-14 |

**R-fac:** the exact path agrees with a literal 60-digit x^n/(K^n + x^n) to 6.9e-38 relative,
on 400 random points. The float64 path's ulps are given above.

**The floor is world-specific: measure it on the engine's own world.**

```python
run, tight, floor = rc.floor(world, t_end, record)  # rtol 1e-10, against rtol 1e-12, atol / 1000
floor["s"], floor["V"], floor["amounts"], floor["crossing"]  # max |difference| per observable
rc.compare(run_a, run_b, record)                      # the same comparison for any two runs
```

An engine error is resolvable in a dt study only where it exceeds that floor. On the synthetic
worlds above, the floor sits near 1e-12 in s and in amounts (fmol).

Evidence: `/mnt/workspaces/Cells/independent-references-20261114-01/` (`HANDOFF.md`;
`track-r-crosschecks-02/crosschecks.json` and its log, run from the frozen snapshot
`track-r-snapshot-02` of 91726e4c; run 01, from f8c9bca4, gave the same floor without the
stiffness rows).

## Readings of the design taken here

1. **§7, milestone 1 as built** (main 21b31f1, with the head note of Appendix A), read after these
   references were first written. Each convention was checked against it:
   - **The crossing record** (§7.1 item 3; the head note): k* is the smallest k with
     s(k·dt) ≥ θ, and a declared s₀ ≥ θ is recorded at k = 0. `crossing_step` gives exactly this.
     **Matches.** Writes are not modelled, so the head note's write rule (recorded at k + 1) does
     not arise here.
   - **Rows at an event time** (§7.1 item 3): the pre-event switch and state. **Changed:** the
     unsuffixed record keys now follow it, and the previous values are kept as `*_right`.
   - **The slots** (§7.1 item 1): the (state, cell) pairs in declared order. **Matches**, and is
     now exposed as `run.slots`.
   - **A per-cell s₀** (§7.2 item 3): `State(initial={cell: s₀})`. **Matches.**
   - **The switch schedule** starts at 0, and later changes lie in 0 < t < end (§7.1 item 8). The
     reference admits any increasing times from 0, a superset. **Matches.**
   - **The sides, the declared order of factors, and the basal level per side.** §7 changes none.
     **Matches.**
   - **The worlds** (§7.1 item 12): Na, K, M and P (P impermeant) with a neutral regulator R.
     Declare the ions as species, and R as a `Regulator` with its turnover, not as a species row.
     The four-species case equals R-tissue (`test_four_species_with_an_impermeant_anion_...`).
2. **The crossing at the start:** s₀ ≥ θ gives t* = 0 and k* = 0. Otherwise t* is the first upward
   reach of θ, and k* = min{k ≥ 1 : s(k dt) ≥ θ}. This is §7's as-built rule.
3. **The zero-current start** (neither `initial_V` nor `background_fmol`) includes populations at
   their availability at 0+, and excludes contacts. For an engine comparison, pass the engine's
   initial V or background explicitly.
4. **An ion read by a Hill coupling** is admitted here as the true instantaneous coupling. It is the
   fast-state limit used in the self-tests; the engine refuses it (ruling 1).
5. **The exposure U** accumulates from 0 and is never reset. `regulatory_writes` (state resets at
   event times) are not modelled. §7.2 item 3's prior condition is covered by a per-cell s₀, and
   its write at 0 is compared engine against engine (A2, as amended).
6. **A regulator** is exogenous and closed-form in every cell that declares it. A neutral species
   that moves, or one the states feed back on, is outside version 1 and is not modelled.

## Known limits

- **Not modelled:** pumps, water, clefts, faces, insertion, divisions, gate kinetics (o is
  constant), writes and injection. The bath is held at 0 V, and every patch faces it.
- **Crossings.** A crossing that comes and goes within one solver step is not seen. Pass
  `max_step` to bound the step if s can be non-monotone near θ.
- **Cost.** The right-hand side is plain Python, so worlds beyond a few cells, or horizons of
  hours, are slow.
- **Mean field.** D150 §1.3's caution applies: below about 10² molecules per cell a Hill factor is
  not meaningful. The references do not check it.
