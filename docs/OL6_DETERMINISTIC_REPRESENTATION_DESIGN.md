# OL6: the deterministic representation of the assembly laws, and the GARD limit (design)

**Status: proposed, 22 November 2026, for the lead.** Docs only: no engine code until the lead
decides (D142; the user sees options first). Branch `ol6-design` from main 0e54aa2a. **S** marks this
note's own derivation or probe. "From memory" marks standard theory cited without being read for
this note; it is read and cited properly when the piece is built. Evidence:
`/mnt/workspaces/Cells/ol6-20261122/` (desk probes P1–P3 and P2b, and `STATE.md`). The handover is
`/mnt/workspaces/Cells/ol6-handover-20261122/HANDOVER.md`.

**The request.**
- OL6's row (ORIGIN_OF_LIFE_ENGINE_DESIGN §8): the GARD limit (§7.3), and the deterministic
  representation of the same laws (§1.2 (d)) with its qualification against exact events.
- D287 item 4: OL6 comes right after FR-31's Phase A (a9a67d06), then FR-39's pore episodes.
- D303 item 8: a new owner, and a design note before code.

**Engine models (AGENTS.md).** This note runs none.
- The representation runs `cells.assembly_lineages@2`'s declared laws (§1.4's table) in a new
  declared representation. Its proposed ID is `cells.rate_equations@1`: the reaction-rate
  equations, the standard name for the deterministic limit of a chemical master equation.
- The GARD limit runs @2's exact events against @1's `cells.gard_catalysis_pair_consistent@1`.

**Two protocols, not one.** They are separate claims, each with its own worlds, criteria and plants
(§5):
- **Protocol D:** the deterministic representation against @2's exact events, at large counts;
- **Protocol G:** the GARD limit, @2's exact events against @1's, at N < 80.

**The probes this note uses** (desk probes, not registered):

| Probe | What it measured | What this note takes from it |
| --- | --- | --- |
| **P1** (the previous owner's), `probe_gard_rates` | @1's pair-consistent GARD rates against the same world declared in @2, on 4,000 random states of 8 types, in both of the factor's branches | The rates agree to 3.1 × 10⁻¹⁵ relative, but only about 13% of them are bitwise equal, and 0 of 256,000 shared draws per case select a different channel. So §7.3's bitwise branch does not apply as built (§5.2) |
| **P2** (the previous owner's), `probe_continuum_identity` | Whether the factored flux equals "the law applied to the products" under three continuous count arithmetics | The finding, re-measured as P2b. P2 divided each gap by the net flux, which vanishes near equilibrium, so its ratios for B and C are inflated |
| **P2b** (S), `probe_continuum_identity_fwd` | P2 with each gap divided by the one-way fluxes a⁺ + a⁻, at n in [10, 100] and [10³, 10⁵] | Arithmetic A (Kurtz's limit: powers, and Stirling's F) is an identity to 1 × 10⁻¹⁴ at both scales. B (gamma interpolation) fails at every order: 4–20% at n ≈ 10–100, 5 × 10⁻⁴ to 2 × 10⁻³ at n ≈ 10³–10⁵. C (falling factorials with Stirling's F) holds at first order per species, and fails for 2A + B → C (10% and 1 × 10⁻³) and for the membrane (3% and 6 × 10⁻⁵). Both failures are O(1/n). So A is the one consistent arithmetic (§1.3, §6.2) |
| **P3** (the previous owner's script, run by S at 0e54aa2a) | The exact kernel's throughput: A + B ⇌ C in the pool, 64 lanes, CPU 7 | 45,000 events/s at Ω = 10³ and 64,000 at Ω = 10⁴, after 15–38 s of compiling. The CPU was shared with a job at 79%, so these are conservative. They price §5.3's ensembles |

## 0. Summary: the recommendations, and the decisions asked

| # | Decision | Options | Recommended | § |
| --- | --- | --- | --- | --- |
| 1 | What (d) is | R1: a world that declares `free_energy_form: continuum`. R2: a representation over the same declared world, chosen by the definition's execution | **R2.** One world id runs in both, so the qualification pairs runs by world. It is D301's contract. The `continuum` token stays refused, with its text unchanged: a test and OL5's registered menu pin it | 1.1, 6.4 |
| 2 | The continuous count arithmetic | A: Kurtz's limit (n^a, m → n, Stirling's form of every ln k!). B: gamma interpolation of the discrete forms. C: falling factorials on real counts | **A,** keeping the declared measure's offset c in N − c. It is the only one in which the factored flux equals the products' law (P2b) | 1.3, 6.2 |
| 3 | Where each law's limit lives | H1: a limit hook in each law's own declaration and module. H2: separate limit declarations under a new interface | **H1,** with the existing `FORMULAS` untouched | 1.4, 6.5 |
| 4 | The integrator | I-A: explicit Tsitouras 5(4) with dense output and a stiffness stop. I-B: a Rosenbrock method (Rodas4) with dense output and an exact Jacobian by forward differentiation. I-C: SciPy's `solve_ivp` on the host | **I-B.** It is stiff-safe (FR-39's open pore is a fast sub-dynamics), keeps moieties to rounding, is deterministic and runs in lanes. I-A is the cheaper start if FR-39 adds I-B later | 6.1 |
| 5 | The envelope | E1: every place a rate reads holds at least n_min, at the founder and at every accepted step. E2: E1, plus places rising from zero | **E1 in version 1.** n_min is the smallest rung that passes Protocol D | 1.5, 6.6 |
| 6 | Lift Phase A's count-change refusal in exact events | L0: keep it. L1: the clock moves onto the device, with σ from F and areas that change at events | **L1, as its own slice.** Without it, no exact-event world has a varying hazard, so (d)'s clock can be checked only against closed forms | 3.6, 6.3 |
| 7 | A held tension over a changing area | T1: the hold does σ·dA of work on every area-changing step, which shifts those steps' rates. T2: refuse area-changing steps under a hold, in both representations | **T2 in version 1.** T1 is new physics for the laws sheet, and no consumer needs it yet | 2.3, 6.7 |
| 8 | The GARD limit's fission | G1: compare up to @1's first fission, with no engine change. G2: add a size-threshold division to @2 | **G2.** §7.3 names D1 fission, and OL9's ladder starts from it. G1 is its first tier | 5.2, 6.8 |
| 9 | §7.3's bitwise wording | Keep it; or replace its first tier with "pathwise to rounding" | **Replace it** (P1). This is the lead's ruling on the design note's wording | 5.2 |
| 10 | A population's linear algebra in (d) | Dense, with a slot cap; or a block solve over the pool's arrowhead | **Dense, at most 64 slots, in version 1** | 6.9 |
| 11 | Checkpoints in (d) | Refuse; or save the integrator's state | **Refuse in version 1** | 3.8 |

**The price** (§6.11): about 4.75–6.25 agent-days for the OL6 row as designed (the core, the
vesicles, Protocols D and G1), against the row's 3–5. The populations, divisions and lysis
crossings that OL2's third milestone and OL3 added after that estimate explain the difference. The
hazard clock for FR-39 (S3 and L1) adds 1.5–2.25, and G2 adds 1–1.5.

## 1. The representation as a declared level of detail

### 1.1 What (d) is: a representation over the same declared world (R2)

**The world is the physics, and the definition chooses its representation.** One world, with its
id, its laws, its terms, its geometry and its founder, runs as exact events (the default) or as
rate equations (opt-in). The choice is made at definition, never at run time, and it is recorded
with the run. This is ARCHITECTURE's "Levels of detail" and D301's contract:
- one representation per scope (here, the whole world);
- chosen at definition, with the detailed form the default and the reduced form opt-in;
- out-of-range use refused (the envelope, §1.5), and unsupported readouts refused (§4);
- an automated comparison (Protocol D, §5.1).

**The `free_energy_form` token is not the switch.**
- A world keeps `discrete`: the F the exact kernel uses. The representation takes the large-count
  limit of that declared F, term by term, by its own declared rule (Stirling's form, §1.3), and
  states the rule in its record.
- `continuum` stays refused, with its text unchanged:
  - `tests/unit/test_assembly_lineages_v2_spec.py:90` pins the text;
  - OL5's registered menu lists `continuum` as refused (`tests/unit/test_ool_references_registration.py:54`).
- No input under `ol5-inputs-5d68cc15` declares `continuum` (a file-name grep). Whether any of
  OL1's registered refusal inputs does is for the lead to confirm; this note did not open them.

**The declaration** sits in the definition's execution block. It is absent by default, and then
never written, so every existing definition, fingerprint and record stays as it is:

```json
"execution": {
  "backend": "cpu", "precision": "float64", "mode": "single_lineage",
  "stream": {"seed": 1, "environment": 0, "lineage": 0, "branch": 0},
  "representation": {
    "id": "cells.rate_equations@1",
    "envelope": {"min_count": 1000, "provenance": "Protocol D's smallest passing rung, <tag>"},
    "integrator": {"id": "rosenbrock_rodas4_dense@1", "rtol": 1e-8, "atol_count": 1e-3,
                   "step_limit": 1000000}
  }
}
```

- `molecule_capacity` and `chunk_events` do not apply: (d) builds no log-factorial table, and its
  counts may exceed the exact kernel's 2^24 (a giant vesicle holds about 4 × 10⁹ lipids).
- The stream stays. (d) draws on the domains whose operators stay stochastic (§3.7).
- The experiment block is the same one the exact run uses. Its event-based keys (`event_limit`,
  `row_every_events`) are stated as not applicable in (d)'s record. Its event-level readouts
  (`trace`, `uniforms`, `diagnostic`) are refused when true (§4).

**The representation is a declaration of its own.** It uses `Law`'s four reserved fields
(registry/laws.py; ARCHITECTURE's "small declaration … on laws that stand in for something"), under
a new interface of the family, `cells.assembly_representation@1`:
- `represents`: the family's exact-event execution of the same world, reduced by the large-count
  limit (Kurtz 1972, from memory);
- `preserves`: every moiety, exactly; the ledgers, in continuous form (§2); F's minimum, and so
  every end state that is a minimum of F (A1's end states, for example);
- `supports`: the readouts of §4's admitted list; every other readout is refused by name;
- `qualified`: the envelope (§1.5), and the tag of Protocol D's registered record (§5.1).

### 1.2 Entities and operators

| Entity | What it is | Owns |
| --- | --- | --- |
| **`RateEquations`** (the representation) | The declaration above, and the host loop that runs a world in it | Its envelope, its integrator's declaration and the run's lifecycle (§3.9) |
| **`ContinuousState`** | The world's state as continuous amounts | §1.6's state |
| **The force kind** | Thermodynamics in the kind (CORE_SEAMS §3.2): μ(n) = ∇F_cont(n), once per state | ΔF_r = ν_r·μ − w_r for every step |
| **Each law's limit** | Kinetics in the law: the law's own large-count form, in its own module (H1) | θ⁺_r, the extent and the factor at n |
| **`Crossing`** | A guard g(t, y) with a direction and a handler, located on the dense output (§3.2) | Lysis, the pore clock, the envelope, the lumen's branch switch |
| **`Stop`** | A declared time the integrator lands on exactly (§3.1) | Observation times, schedule times, hold edges, the horizon |
| **The integrator** | A numerical method, declared apart from the representation (ARCHITECTURE: "representation and numerical method stay separate"), in `src/cells/numerics/` | Its step, error estimate and dense output |
| **`ContinuousLedger`** | §2's ledger | Q, W by payer and the sinks, as quadratures and event bookings |

**The operators' semantics in (d)** are each operator's own, in the limit:
- shear fission splits by its mean (§3.4);
- the lysis release, the serial transfer and the pore's rupture are reused as they are, on
  continuous amounts.

### 1.3 Reusing the laws and the factored form

**The flux of one step (S).** The exact pair keeps a⁻(n + ν)/a⁺(n) = exp(F(n + ν) − F(n) − w),
with both rates carrying the same s(m). In the large-count limit the finite difference becomes a
gradient, and m becomes n:

    J_r(n) = s_r(n) θ⁺_r(n) (1 − e^{ΔF_r}),   ΔF_r = ν_r·μ(n) − w_r,   μ = ∇F_cont (k_BT)

- This is the cycle kind's factored form (CORE_SEAMS §3.2: J = k a S (1 − e^{ΔG/RT})), and §1.2
  (d)'s J = Σ s θ⁺ (1 − e^{ΔF/k_BT}).
- J_r and ΔF_r have opposite signs for every step at every state, so each step dissipates:
  −J_r ΔF_r ≥ 0. (d) can check that per channel (§2.1). The exact kernel cannot, because its event
  heats are signed.
- dn/dt = Σ_r ν_r J_r, and each held place's net supply integrates −Σ_r ν_r,p J_r.

**Arithmetic A: every discrete form by its large-count limit (S; P2b).** The rule is mechanical:
- in F, every ln k! becomes Stirling's k ln k − k (the "continuum" form the conventions reserve);
- in θ⁺, every falling factorial ff(n, a) becomes n^a, and the membrane's ff(N − c, r) becomes
  (N − c)^r, keeping the declared offset c;
- in s, the common state m becomes n, so the extent and the factor are evaluated at n.

So a dilute reactant's activity is (n/X)^a, a membrane reactant's is x^a with x = n/(N − c), and
μ_i = μ°_i + ln(n_i/X) in a dilute phase, μ°_i + ln(n_i/(N − c)) in the membrane. P2b shows the
factored form then equals "the same law applied to the products, with k⁻ = k_f e^{Σνμ°}" to
rounding, as in the exact kernel's discrete arithmetic. The other two arithmetics break that
identity at O(1/n) (§6.2). Every difference between A and the exact kernel's propensities is
O(1/n), so it belongs to the limit's error budget, not to the laws.

**How J is evaluated, and what the check compares (S).**
- **Evaluated:** form (i), a⁺·(−expm1(ΔF_r)), in log space for a⁺. Near equilibrium, which is
  where A1's end states sit, it has no cancellation, where a⁺ − a⁻ would lose digits.
- **Checked:** form (ii), a⁻ computed independently as each reaction law's limit applied to the
  products, times the same factor, times e^{ν·∇F_ex} for the excess terms.
  - The check is not vacuous for the ideal part. θ of the products comes from the reaction law's
    limit kernel, and the ideal part of μ comes from the ideal term's continuum value, by
    differentiation. Two separate pieces of code must agree.
  - For the excess terms (ii) shares e^{ν·∇F_ex} with (i), so their check is separate: ∇F_ex by
    differentiation against central differences of F_ex's own value, and against the exact
    kernel's finite-difference `delta` at large n (§1.4, "the limit's check").
- **Zero counts:** (i) is 0·∞ where a reactant's count is 0 and a product's is not. Under E1 no
  place a rate reads is ever 0 in an admitted run: a trial stage below the envelope is rejected and
  the step retried smaller (§3.2). An inert place, read by no rate, may be 0.

**μ by differentiation.** Each free-energy term declares one traceable continuum value. μ is its
gradient by JAX's reverse mode, so no term writes a gradient by hand. The integrator's Jacobian is
the forward derivative of the flux, so second derivatives of F come from the same values.
- The values must be safe to differentiate. A `where` whose untaken branch is not finite takes the
  double-`where` form. `lumen.free_energy` already guards its logarithms that way.
- The lumen's two branches, V = min(V_osm, V_sph), meet at a kink. There μ is continuous: V
  minimises F at fixed solutes, so ∂F/∂V = 0 on the floppy side and the envelope theorem applies
  (S). μ's own derivative jumps, so the integrator restarts at the kink (§3.2).

### 1.4 Each law, term, factor, geometry and operator in version 1

**The limit's check** runs before every (d) run, as `balance.verdict` and `world_report` run before
an exact one. It runs on its own generic probe worlds and on the world's own states, and refuses a
world that fails. It checks four things:
1. (i) equals (ii) for every step, to rounding;
2. μ equals central differences of F_cont's value;
3. −J_r ΔF_r ≥ 0 for every step;
4. parity with the exact kernel: at integer states scaled by λ = 10³, 10⁴, 10⁵ and 10⁶, each law's
   limit and its exact form differ in ln a⁺ by O(1/λ), with a fitted order of at least 0.9 (S).

A law whose limit is wrong by a constant factor fails item 4, and one whose limit disagrees with F
fails item 1.

| Piece | Version 1 in (d) | Reused as it is | New |
| --- | --- | --- | --- |
| `cells.stochastic_mass_action@1` | Admitted | The view's fields, `entry_sum`, `safe_log`, the layout's k_f, k⁻ ratio and extents | A limit kernel: powers for falling factorials (P2b: `log_falling` on real counts is arithmetic C, which breaks the identity at order 2 or more), and the membrane factor (N − c + 1)/(N − c)^r |
| `cells.phase_exchange@1`, `cells.membrane_permeation@1` | Admitted | `exchange.geometric_log_direction`, on a continuous view (consumed 0, real counts). Each moves one molecule, so every falling factorial has a ≤ 1, and arithmetics A and C coincide (S) | The view, and `kernel.encounter_extent` at a real footprint W |
| `cells.transition_state_factor@1` | Admitted | `log_factor` on a continuous view: z = βn and the counts are float64 already (`state`), and with consumed 0 the factor is g(n), in either branch, cached or count-weighted mean | — |
| `cells.ideal_mixing@1` | Admitted | The tables (μ°, ln X, the offset c) | A traceable continuum value: Stirling's form of the declared F_id |
| `cells.regular_mixing@1` | Admitted | `state` (y = χn and S = n·y, by serial folds, traceable) | Its value S/(2N), three lines |
| `cells.osmotic_lumen@1` | Admitted | `free_energy`, `log_volume` and `tension`, which compute in float64 and trace already | Verified safe to differentiate; the kink as a restart (§3.2) |
| `cells.bilayer_geometry@1` | Admitted | `log_constants`, the area, the radius and the closure cost | W as a real number. The floor becomes part of the envelope: W ≥ max(W_floor, envelope) |
| `cells.shared_pool@1` | Admitted, at most 64 slots (§6.9) | Slots, founders, keys and the additive F | The pool's coupling in the Jacobian. The world-level selection map is not used |
| `cells.shear_fission@1` | Admitted | Admission (stress, then v ≤ k^(−1/2)), the floor test, keys, continuation and the booking | The mean split, with the complement rule (§3.4) |
| `cells.serial_transfer@1` | Admitted | Its draws on domain 6, its keep rule and its booking | F_cont in the booking |
| `cells.pore_nucleation@1` | Admitted | `log_rate`, `sigma_beta`, `log_site_density` and `pore_clock.opening` | H in the state (§3.5). Area changes admitted; σ from the osmotic lumen admitted (w = 0), with σ_max ≤ σ_β/4 required at parse |
| `cells.tension_hold@1` | Admitted | Its parse, payer, work column and cross-checks | Under a hold, area-changing steps stay refused (T2) |
| `cells.prescribed_shell@1`, `cells.shell_permeation@1`, `cells.gate_factor@1` | Refused | — | About 0.25 agent-day when a consumer needs them |
| `cells.pool_replacement@1`, `cells.pool_withdrawal@1` | Refused | — | Their means and bookings in (d), about 0.5 agent-day |
| Labels, the diagnostic record, checkpoints | Refused | — | — |

**The six convention tokens, and the other declared keys, in (d):**
- `free_energy_form: discrete`: (d) takes Stirling's form of it (§1.1). `continuum` stays refused.
- `condensed_measure`: c is kept in N − c. The two measures differ by O(1/N) in (d).
- `membrane_kinetics: count_on_m`: activities x^a with x = n/(N − c), and the extent at n.
- `lumen_volume`: `declared` is a constant V; `osmotic` is V(n) = min(V_osm, V_sph), as now.
- `empty_catalyst_phase: uncatalysed`: g = 1 at N = 0, a state outside the envelope.
- `last_molecule` (`kept`, `reversible`, `extinct`): each governs only an empty membrane, which
  lies outside the envelope. All three are admitted, so one world runs in both representations, and
  the record states that the token does not apply inside the envelope.
- `exchange_encounter`: the extent at a real W.
- `vesicle_floor`: part of the envelope (above).

### 1.5 The envelope (E1)

(d) is valid only where every count is large (§1.2 (d)). The envelope makes that enforceable
(ARCHITECTURE keeps enforceable bounds apart from assumptions that need evidence):
- **What it covers:** every finite place that some rate reads. That means a reactant or product of
  a step, a catalyst of a factor, or a member of a phase whose total enters a normalisation or a
  factor. A place no rate reads is inert, and is exempt.
- **At parse:** a founder with such a place below n_min is refused, by name.
- **At run time:** an accepted step whose state has such a place below n_min ends the run
  `outside_envelope` at the crossing (§3.2), recorded and never repaired. A trial stage below
  n_min/2 rejects the step, which is retried smaller.
- **n_min** is declared with its provenance: Protocol D's smallest passing rung (§5.1).
- **Exact zeros against sparse counts:** an exact zero in a place no rate reads is inert. A zero in
  a place some step can feed (a product starting from nothing) is refused at parse in version 1.
  E2, admitting places that rise from zero, is a later option (§6.6).

### 1.6 The state it carries

| Part | Contents |
| --- | --- |
| Per vesicle (slot) | Real counts of its membrane and lumen places; alive; key, generation and sub-lineage (integers, as the exact runner's); the pore clock (E, H and the counter); its fission counter |
| Pool | Real counts of its finite places; each held place's net supply, real |
| Ledger | Q; W by payer (reservoir, `tension_hold/<i>`, `shear/<i>`, `transfer/<i>`); the sinks |
| Integrator | t, the next h, the step controller's memory, and the last accepted step's dense coefficients |
| Schedules | Each schedule's draw counter (domain 6), and the stops already applied |

**Not carried:** event counters, channel counts, rates, the factor's and terms' incremental states
(recomputed at every evaluation, which is cheap), and the log-factorial table.

## 2. The ledgers in continuous form

### 2.1 The state function and the bookings

**The state function** is F_cont(n): the declared terms' continuum values (§1.3), plus the closure
cost once per living vesicle. A held place has no term.

**The continuous bookings.** Each is a component of the ODE state, integrated by the same stages
under the same error control, and never formed by difference:
- **Heat:** dQ/dt = −Σ_r J_r ΔF_r. Every term is at least 0, so Q never falls between events.
  The exact kernel's event heats are signed. In the limit their mean rate tends to this one, since
  ln(a⁺/a⁻) → −ΔF_r (S).
- **Reservoir work:** dW_res/dt = Σ_r J_r w_r, with w_r = −Σ_held ν μ_held, as the exact kernel's.
- **The held places' supplies:** d(supplied_p)/dt = −Σ_r ν_r,p J_r.

**The event bookings** are exact differences of F_cont, each as the exact runner books it:
- **A lysis**, by σ_max or by a pore: one booking, q = −(F_cont(after) − F_cont(before)) + w_r. The
  release moves the vesicle's amounts to their pool places and drops its closure cost, and w_r is
  the reservoir work of held places that take molecules back (§0.2d item 7).
- **A pore's opening** (Phase A's booking, unchanged):
  - **Under a hold:** q_open = −ΔF_open + w, with ΔF_open = 2σ_β/σ − ln(A·n_s) and
    w = σπr_c² = σ_β/σ, booked in `tension_hold_work_kT` and paid by `source:tension_hold/<i>`.
  - **With σ from F:** w = 0 and ΔF_open = σ_β/σ − ln(A·n_s) (VESICLE_PORES_LAWS §7, to leading
    order in r_c/R_v). So q_open = ln(A·n_s) − σ_β/σ = ln(k_v/P), as under a hold.
  - **Either way,** the rupture's release is taken from the open state, so ΔF_open cancels in the
    event's total: −(F_cont(after) − F_cont(n)) + w + w_r.
- **A division:** shear work Σ_j F_v(d_j) − F_v(parent), which holds (k − 1)·C_close. The sink takes
  the unfollowed daughters' F_v in a single lineage.
- **A serial transfer:** the sink takes F_removed + F(old pool), and the schedule's work column takes
  F(fresh pool).

### 2.2 How they close

At every row: **F_cont(n_t) − F_cont(n_0) = W(t) − Q(t) − S(t)**, W summed over payers and S the
sinks.
- **The event bookings close exactly** (each is defined from F_cont).
- **The continuous part closes to the integrator's error, not to rounding.** The residual is the
  quadrature error of ∫ Σ_r J_r ν_r·μ dt along the numerical solution.
  - Its linear part, Σ μ° n, closes to rounding: Runge–Kutta and Rosenbrock steps integrate linear
    functionals of the state exactly (S). So the residual comes from F's nonlinear terms only, and
    scales with their change, not with F's size.
  - **Registered tolerance:** |residual| ≤ 100 × rtol × max(1, Σ|bookings|) + 64 ε (|F_cont(n_t)| +
    |F_cont(n_0)|), with ε float64's epsilon. A run beyond it is refused, as the exact runner
    refuses one whose books do not close.
- **The second law per step:** −J_r ΔF_r ≥ −64 ε |J_r ΔF_r| at every stage of every accepted step.
  The smallest margin is recorded. This is a check (d) can make per channel and (a) cannot.

### 2.3 Work by payer, including the held tension

| Payer | Continuous | At events |
| --- | --- | --- |
| Reservoirs (held places) | Σ_r J_r w_r | The release's w_r |
| `source:tension_hold/<i>` | None under T2 (§6.7) | σπr_c² at each opening |
| `source:shear/<i>` | — | Σ_j F_v(d_j) − F_v(parent) |
| `source:transfer/<i>` | — | F(fresh pool) |

**A held tension over a changing area (the advisor's point; a ruling Phase A never faced).**
- At a held σ, the boundary does σ·dA as the membrane's area changes. A step that changes W by ΔW_r
  would then carry w_r ⊃ σ·q·ΔW_r/(2 k_BT). That work enters the pair's rate ratio: the hold pulls
  amphiphiles in, by σ·a_L/2 per molecule, about 0.36 k_BT at 10 mN/m and 0.3 nm² (§2.5's
  number).
- Phase A never met this case, because its pore law refuses every step that changes a membrane
  place. The laws sheet's §3 books the hold's work only at an opening.
- **Version 1 keeps that boundary (T2):** a world with a hold refuses area-changing steps in both
  representations. T1, the work on every area-changing step, needs a laws-sheet amendment and a
  ruling (§6.7).

### 2.4 Moieties

- Every step conserves every declared moiety (seam E's check at parse), so moiety totals are linear
  invariants of dn/dt = Σ ν J, once the held reservoirs' supplies are counted.
- **They close to rounding,** not to the integrator's tolerance. Any Runge–Kutta step keeps linear
  invariants. A Rosenbrock step keeps them when its Jacobian is exact: L·f(n) ≡ 0 gives L·∂f/∂n ≡ 0,
  so every stage's increment satisfies L·k_i = 0 (S). Forward differentiation gives the exact
  Jacobian.
- **Registered:** a relative residual of at most 1 × 10⁻¹² per moiety at every row, counted per
  moiety and never per species (the handover's pitfall).
- **The events conserve them exactly:** the mean split's last daughter takes the complement, and
  releases and transfers move whole amounts.

### 2.5 Comparing the ledgers of the two representations

- **F differs between them by more than the limit's O(1/N):**
  - Stirling's correction: ln n! − (n ln n − n) = ½ ln(2πn) + O(1/n) per finite place (from
    memory). That is O(ln n) per place.
  - Fluctuations: E[F_disc(n_t)] − F_disc(E[n_t]) ≈ ½ Σ_p Var(n_p)/n_p, which is O(1) per place
    (S, a second-order expansion).
- **So Protocol D compares the counts and the works per unit Ω, not F or Q.** The heats then agree
  through each representation's own closure.

## 3. Events in a continuous world

### 3.1 Stops

The integrator lands exactly on each declared time, truncating its step there. The declared times
are:
- observation times;
- each schedule's times: declared shear times, Poisson shear times drawn on domain 6, and transfer
  times;
- each hold's start and end, where k_v jumps;
- the horizon.

At a stop the operators act in schedule-index order (§0.2d item 10.1). A declared time equal to the
horizon applies.

### 3.2 Crossings: solved, never snapped

A crossing is a guard g(t, y) with a direction, whose root is an event:

| Guard | Direction | Handler |
| --- | --- | --- |
| σ_v − σ_max (a vesicle's tension) | Upward | Lysis by threshold (§3.3) |
| H_v − E_v (a vesicle's pore clock) | Upward | Opening, then rupture (§3.5) |
| Every enveloped place's count − n_min | Downward | Stop `outside_envelope` |
| ln V_osm − ln V_sph (the lumen's branch) | Either | None: restart the integration there, so the method keeps its order past μ's kink |

**How a root is found** (S; the methods from memory):
1. After each accepted step, each guard is evaluated on the step's dense output, at its ends and at
   8 interior points, to bracket sign changes. A guard that changes sign twice within one step is
   bracketed by the interior points. The step controller makes this rare.
2. The earliest bracket's root is located on the dense output by the Illinois method (modified
   regula falsi), to max(4 ulps of t, τ_c). τ_c is the crossing tolerance, registered.
3. The step is then re-taken from its start to the root, with h′ = t* − t_n, so the state at t*
   carries the method's own order and not the dense output's lower one.
4. The guard is evaluated again at the re-stepped state. If |g| is still beyond its tolerance, a
   secant on h′ repeats step 3, at most 4 times, or else the run stops `stalled`.

**Ties are refused, as in exact events (FR-20's rule: relations have no order between same-time
events).** That covers two vesicles' roots within D283's `same_instant` of each other, and a root
within `same_instant` of a stop.

**The planted error** of this design is the snap. A root moved to the end of its step must fail the
crossing-time check (§5.1, P-D5).

### 3.3 Lysis at σ_max

- **Exact events:** an event whose end state has σ > σ_max fires, and ends the life `lysed`.
- **(d):** the crossing σ(t) = σ_max, upward. This is the limit of the exact rule, since the exact
  overshoot is one event's change, O(1/N).
- **The handler** is the release (§2.1), with cause `threshold`. In a population the slot frees and
  the run goes on. In a single lineage the run ends `lysed`.

### 3.4 Division at a shear stop (`cells.shear_fission@1`)

1. **Admission,** on the continuous state at the stop: the stress test, then v ≤ k^(−1/2), as the
   exact operator's.
2. **The split is the mean of §0.2c rules 9 and 10.**
   - At equal target areas, C3x's daughters are exchangeable, and the lumen's multinomial weights
     are 1/k. So each daughter takes n/k of every place.
   - The last daughter takes the complement, so the daughters sum exactly to the parent (S5 §3.3's
     rule).
   - A declared distribution of sizes (a later token value) would split in proportion to each
     daughter's area. It is refused until that token exists.
3. **The floor:** each daughter must be within the envelope, or the fission is refused and recorded,
   with the parent kept.
4. **Keys** in daughter order. Continuation is `first`, or `uniform` from domain 3: the same draw as
   the exact run's.
5. **The booking** is §2.1's.

**What (d) cannot say:** its daughters are identical, so the composition's fluctuation at division,
and with it H similarity, F12 and composomes, are unsupported readouts (§4). In a population,
daughters take free slots in slot order, and a full set stops the run `slots_full` before the split.

### 3.5 The hazard clock in (d)

- **The threshold.** Each vesicle draws E_v = −ln u from domain 7 (its key, counter 0) when the run
  first holds it: a founder at the start, a daughter at its birth. H_v starts at 0 then.
  - **The daughters' clocks (S):** a daughter is a new vesicle with its own opening process; the
    parent's ends at the division.
- **The rate.** dH_v/dt = k_v(A_v(n(t)), σ_v(t), T) while the hazard is in force:
  - during a hold's interval [start_s, end_s), with σ = σ_hold (Phase A's);
  - always, with σ from F, the osmotic lumen's tension (new). The parse requires σ_max ≤ σ_β/4, so
    the law's domain, σ ≤ σ_β/4, holds on every trajectory that has not lysed.
- **H_v is a component of the ODE state,** under the same error control, with an absolute tolerance
  registered at 1 × 10⁻¹⁰. A crossing time's error is then about 10⁻¹⁰/k_v.
- **The opening** fires at the crossing H_v = E_v (§3.2). Phase A's outcome follows: rupture through
  the release, with cause `pore`.
- **The hazard and σ_max both stand** (D287). Whichever crosses first acts.
- **Area changes are admitted in (d),** lifting Phase A's refusal there, except under a hold (T2).
  The edges of a hold are stops, and the lumen's kink is a restart.
- **The regression identity, a test row.** A Phase A world (a hold, and no step that changes a
  membrane place) gives t* = start_s + E/k_v with the same domain-7 E (`pore_clock.rupture_time`),
  to the crossing tolerance.
- **FR-39's Phase B** adds the open pore's radius as a further per-vesicle variable, switched on at
  the opening and off at resealing, through the same crossing and per-vesicle machinery. It is not
  built in OL6. So "opening" and "rupture" stay one event in version 1, as Phase A ruled.

### 3.6 Paired runs on the pore stream

- **What pairs.** Exact and (d) runs of one world with one stream draw the same E for the same
  vesicle key:
  - founders always (key i:0);
  - daughters when the vesicle-level events occur in the same order in both runs, since keys follow
    world event order (the relations rule, s′·2³² + 1).
- **What the pairing qualifies depends on L0 or L1 (§6.3):**
  - **Under L0** (Phase A's refusal kept in exact events), only constant σ and A exist in exact
    events. The pairing then checks the stream's identity and the crossing solver: (d)'s t*
    against Phase A's exact one. A varying k_v is checked only within (d), against closed forms.
    One such form is an area that grows exponentially by insertion, which gives H(t) in closed
    form.
  - **Under L1,** exact events run a varying σ (from F) and area, with H piecewise linear between
    events and its crossing exact (VESICLE_PORES_LAWS §5). The paired difference t*_a − t*_d per
    vesicle then shrinks as N^(−1/2) (Protocol D, world D7).
- **Pores against no pores.** One world run in (d) with the pore law and without it is identical,
  bit for bit, until the first opening: a test row. In exact events the two share every chemistry
  draw until then (VESICLE_PORES_DESIGN §3.2).

### 3.7 What (d) draws

- Domain 7: the pore thresholds.
- Domain 6: Poisson shear gaps, and a transfer's sampling.
- Domain 3: the `uniform` continuation.

It never draws on domains 1, 2 or 5 (the events, the partition and the world's selection). The
stream identity records only the domains drawn, as now.

### 3.8 Checkpoints

Refused in version 1. FR-22's rung P is defined on exact events. A later option saves t, y, the
next h and the controller's memory at an accepted step, and restarts bit for bit.

### 3.9 The lifecycle in (d)

(d) declares its own table, so `kernel.STATUS` and `LIFECYCLE` do not change:
- `complete`: the horizon was reached;
- `lysed`: a single lineage's vesicle lysed, by σ_max or by a pore;
- `outside_envelope`: an enveloped place crossed n_min;
- `stalled`: h fell below its floor, or no smaller step avoids a non-finite stage;
- `step_limit`: the integrator's guard was reached;
- `slots_full`: a population.

Equilibrium is not a stop: the state holds, and the run completes at the horizon.

## 4. What version 1 refuses

Each is refused at parse, by name, with its reason, unless marked as a run-time stop:

1. **A law without a declared limit** (H1), and every law §1.4 lists as refused in (d): FR-21's
   shell, its permeation and its gate; FR-20's replacement; FR-35's withdrawal.
2. **A founder outside the envelope** (§1.5), including a place that some step can feed starting
   at 0 (E2 is later). Leaving the envelope during a run is a stop, `outside_envelope`.
3. **Event-level readouts:** `trace`, `uniforms` and the diagnostic record, when true. Channel
   counts are never written. The relations record keeps its vesicle-level events: lysis, division
   and rupture.
4. **Readouts that measure discreteness:** H similarity, F12, composomes and extinction statistics,
   in (d)'s records and in any analysis that reads a (d) bundle (`validation/` checks the bundle's
   representation).
5. **A world with `world_role: probe`,** whose singular rate is a statement about integer states.
6. **Area-changing steps under a hold** (T2), in both representations, as Phase A has them now.
7. **A pore world with σ from F whose σ_max exceeds σ_β/4.**
8. **Same-time events:** two crossings within `same_instant`, or a crossing at a stop (run time,
   refused as FR-20's rule refuses them).
9. **Checkpoint cuts and restarts** (§3.8).
10. **A population of more than 64 slots** (§6.9), and labels (FR-42's shares).
11. **Mixed representations,** whether a world part in each, or a switch during a run. ARCHITECTURE
    makes promotion and demotion a later milestone.
12. **A declared size distribution at division** (§3.4), until its token exists.

## 5. The qualification protocols, registered before any reading

### 5.0 Registration

- **What is tagged.** This section's text, as amended by the lead's decisions, together with the
  world generators, seeds, rungs, times, observables, tolerances and plants as code in `validation/`
  (proposed: `validation/assembly_lineages_v2/limit_qualification.py`). It is tagged before any
  comparison of (d) with exact events is computed.
- **What is not a reading.** (d)'s development tests against closed forms (criterion N, below) and
  the limit's check (§1.4) read no exact-event comparison, so they may run before the tag.
- **Who runs it.** Proposed: the builder, at the tag, one detached job per protocol (§5.3). The lead
  may instead assign a checker, as for D287's sealed extractor.
- **Where it goes.** Verdicts as JSON beside the runs, and a summary in PROGRESS.

### 5.1 Protocol D: the deterministic representation against exact events

**The worlds.** Each names its engine models.

| World | What it is | Laws | Family |
| --- | --- | --- | --- |
| **D1** | Dilute chemistry in a finite pool: A + B ⇌ C and 2A ⇌ D, the second for order 2 in one species (P2b's sensitive case). Volume ∝ Ω, founders (0.5, 0.3, 0.1, 0.1)·Ω, and one inert membrane molecule that no rate reads | `cells.stochastic_mass_action@1`, `cells.ideal_mixing@1` | Density-dependent in Ω |
| **D2** | A membrane exchanging 4 types with a held pool, catalysed (β from GARD's lognormal, a recorded seed), plus one membrane step A + B ⇌ C at order 2 in the membrane. Σ K ρ = 1.5, so N roughly doubles over the horizon. `multinomial`, `kept`. Founder N₀ = Ω | Plus `cells.transition_state_factor@1` | Density-dependent in N₀ |
| **D3** | 3 types between a finite pool (volume ∝ Ω) and a membrane (founder ∝ Ω), with regular mixing (χ = ±1.5), relaxing to equilibrium | Plus `cells.regular_mixing@1` | Density-dependent in Ω |
| **D4** | A vesicle swelling to lysis. A permeant solute enters an osmotic lumen that holds an impermeant one, and amphiphiles join from a held pool. The tension rises through the kink to σ_max | `cells.bilayer_geometry@1`, `cells.phase_exchange@1`, `cells.membrane_permeation@1`, `cells.osmotic_lumen@1`, ideal mixing | Not density-dependent (V_sph ∝ N^(3/2); the closure cost is constant): per-rung criteria only |
| **D5** | Two vesicles on one finite pool, one swollen and tense, one isotonic and floppy, exchanging amphiphile through the pool: A1's mechanism at small scale | Plus `cells.shared_pool@1` | Per rung |
| **D6** | A floppy vesicle divided at declared shear times (k = 2, continuation `first`). Its v at each shear time lies at least 5 standard deviations below 2^(−1/2) in the exact runs, so admission is never random there | Plus `cells.shear_fission@1` | Per rung |
| **D7** | D4 with the pore law, σ from F, paired by E (needs L1). Under L0: D7′, Phase A's held, fixed-area world, paired by E, which reduces to the regression identity (§3.5) | Plus `cells.pore_nucleation@1` (and `cells.tension_hold@1` for D7′) | Per rung (D7′: exact) |
| **D0** | The sparse plant: D2's family at N₀ = 8, `multinomial_less_one` with `extinct`, Σ K ρ = 0.5 (shrinking). Exact lineages go extinct with positive probability, and the rate equations never do | As D2 | Planted only |

**Rungs and replicas.**
- **D1–D3:** Ω or N₀ ∈ {250, 1000, 4000, 16000}, with M = 256 replicas per rung.
- **D4–D7:** vesicles of diameter 25, 50 and 100 nm, which is N ≈ 1.3 × 10⁴, 5.2 × 10⁴ and
  2.1 × 10⁵ amphiphiles at 0.3 nm² per leaflet. Their lumens are near 1 M, so N_L ≈ 5 × 10³,
  3.9 × 10⁴ and 3.1 × 10⁵ (S). M = 128 replicas per rung.
- **Seeds and times:** seeds 1 to M, environment 0, lineage 0, branch 0. Each world has 8
  observation times over its horizon, registered.
- **Observables:**
  - D1–D3: the count per Ω of every enveloped place;
  - D4–D7: A, V, σ and the lumen's counts;
  - every world: W_res per Ω;
  - D4 and D7: the event time per replica.
- **The scale.** Each observable's founder value, or its registered scale where the founder's is 0,
  is its scale s_y.

**The criteria (S).**
- **P, pathwise, density families only.**
  - D_k is the root mean square, over replicas, times and observables, of (y_a − y_d)/s_y at rung
    k.
  - **Pass:** the least-squares slope of ln D_k against ln Ω_k over the four rungs lies in
    [−0.65, −0.35].
  - Single trajectories deviate from the limit by O(Ω^(−1/2)) (Kurtz; van Kampen's expansion, from
    memory). So this tolerance scales as 1/√N, and the slope is the trajectories' order of
    convergence, ½.
- **M, means converge, every world.** For each registered (observable, time), e_k = mean_a − y_d,
  with SE_k from the replicas.
  - **Pass:** at the top rung K, |e_K| ≤ z*·(SE_K² + SE_(K−1)²/4)^(1/2) + |e_(K−1)|/2, with
    z* = 4.5.
  - **Why:** the limit's bias is O(1/N), so it falls by 4 per rung. A model error ε does not fall,
    and fails once ε exceeds about 2z* combined SE.
  - **No bias constant is guessed.** The top rung must show at most half the previous rung's error,
    within noise: an observed order of at least ½, with 1 expected.
  - **False alarms:** z* = 4.5 is two-sided 6.8 × 10⁻⁶ per comparison. At up to 200 registered
    comparisons per world, that is at most 0.14% per world.
  - **Power:** SE at the top density rung (Ω = 16,000, M = 256) is about 5 × 10⁻⁴ of the scale, so
    a mean shifted by more than about 6.4 × 10⁻³ of its scale fails. At the top vesicle rung it is
    about 1 × 10⁻² (S). Every plant below is O(1).
  - **The bias's order** across all rungs is also reported, as a description.
- **E, events (D4 and D7).**
  - Criterion M applies to mean(T_a) − t*_d, for the lysis time and the opening time.
  - The spread must fall with N: SD_K ≤ 0.75·SD_(K−1), with 0.5 expected.
  - **Under L1** (D7, paired by E): the same two tests on Δ = T_a − t*_d per vesicle, using
    RMS(Δ).
  - **Censoring:** each world is chosen so that no replica is censored at a horizon of (d)'s t* plus
    10 standard deviations. A censored replica is reported, and fails its world.
- **L, ledgers.**
  - (d) alone, every run: closure within §2.2's tolerance, the per-step dissipation margin, and
    moieties to 1 × 10⁻¹².
  - Across representations: W_res per Ω, and the hold's work per opening, are observables under M.
- **N, numerics, (d) alone** (development tests; §5.0):
  - **Tolerance:** at rtol = 10⁻⁶, 10⁻⁸ and 10⁻¹⁰, the error against a run at 10⁻¹² falls at least
    50-fold per 100-fold in rtol.
  - **Closed forms:**
    - a first-order network against its matrix exponential (the test's SciPy, not `src/`), to
      10⁻⁷ relative at rtol 10⁻⁹;
    - D3's end state against F_cont's minimum, to 10⁻⁸;
    - a crossing with an analytic root (§3.6's growing area), to τ_c.
  - **Lane invariance:** a world's records are bitwise the same alone, in a batch of 8 lanes, and in
    another lane order. (d)'s sums use the serial folds (D182), as the exact kernel's do.
  - **Identities:** the regression identity (§3.5), and pores against no pores (§3.6).

**The envelope's n_min** is the smallest rung at which every world passes, stated with the tag.

**The planted failures.** Each is O(1), and each must fail its criterion. Plants of order 1/N vanish
in the limit and are not used: a factor at each direction's own state, the measure's offset, and
falling factorials against powers.

| Plant | Where | Must fail |
| --- | --- | --- |
| **P-D1:** the envelope check disabled | D0 | M (exact lineages go extinct). With the check on, D0 is refused at parse: §7.1's "a sparse case admitted" |
| **P-D2:** a reactant's power off by one in mass action's limit, (n/X)² for a first-order reactant | D1 | The limit's check, items 1 and 4, at registration. With the check off, M |
| **P-D3:** one factor entry's β × 1.5, in (d)'s layout only | D2 | M |
| **P-D4:** the Laplace factor doubled (σ = Δp·R), in (d) only | D4 | E (the lysis time) |
| **P-D5:** each crossing snapped to its step's end | D4, and N's crossing test | N at τ_c, and E |
| **P-D6:** the heat's sign flipped | Any | L (closure) |
| **P-D7:** one species' μ° shifted by 0.5 k_BT, in F_cont only | Any | The limit's check, item 1 (the identity), at registration |

Each plant runs through a scoped registry or a planted layout, as the exact kernel's plants do.

### 5.2 Protocol G: the GARD limit

**What it is.** A consistency check by construction, not a D138 comparison (D199's U6(a)). §7.3's
configuration in @2 reproduces G1's GARD law set.

**The law the claim is against:** G1's registered default, `cells.gard_catalysis_pair_consistent@1`,
the cached form P1 compared. Its exact-cache successor, `…pair_consistent@2` (D244, D246), is
reported beside it.

**The @2 world** (§7.3's configuration; P1's construction):
- types T_i, with held pool places at ρ_i. With c0 = 1 mM, ln(held/c0) is ln ρ_i;
- one join per type, mass action with `count_on_m` at the membrane locus, k_f = K_i·kb_i;
- μ°_sol = 0 and μ°_bil = −ln K_i, so k⁻ = kb_i;
- the transition-state factor with ΔΔG‡_ij = log1p(β_ij);
- ideal mixing, no geometry, a single lineage;
- fission: none in @2 today (G1), or D1 (G2, §6.8).

**The measures (D215).**
- **Exact,** `multinomial_less_one` with `extinct`: the claim.
- **Physical,** `multinomial` with `kept`: a report. It differs at O(1/N): the join's extent is
  N + 1 against N, and the last molecule is kept.

**The tiers.**
- **T-bit, §7.3's first branch, does not apply as built.**
  - P1 found about 13% of rates bitwise equal, and a largest relative difference of
    3.1 × 10⁻¹⁵.
  - The two kernels differ by construction. @1 multiplies, kf_rho × N × g. @2 exponentiates a sum
    of logarithms, k_f·exp(ln θ + ln E + ln g).
  - ΔΔG‡ = log1p(β) does not return β exactly for about 13% of entries (P1).
  - Making the two bitwise would need a GARD-only product kernel in @2: building for one
    experiment, rejected (D144).
- **T-path (proposed).**
  - Under shared streams (one seed's words; @2's domain 1 is @1's derivation, `streams.py`), the
    channel sequences are identical, and event times agree to 1 × 10⁻¹² relative.
  - A divergence at an event is a **threshold coincidence** when u₂·a₀ lies within 64 ulps of a
    prefix boundary in either kernel. It is counted and allowed, and ends that seed's comparison.
    Any other divergence fails.
  - **Expected coincidences:** about 2C × 3 × 10⁻¹⁵ ≈ 5 × 10⁻¹⁴ per event (S, from P1). The
    registered bound is at most 1 in the whole set.
- **T-dist (distributional, at registered tolerances):** the physical measure's report, and the
  fallback if the lead rules T-path out.

**The scope of each option.**
- **G1:** each seed from its founder to @1's first fission, both kernels run with `trace`.
- **G2:** through 50 fissions, with @2's size-threshold division drawing @1's partition uniforms
  (domain 2, the parent's key, counter 0; floor(N/2) to the first daughter; floor-to-first), and
  the first daughter followed.

**The worlds.**
- C = 8, with 16 matrices β = exp(−4 + 4Z) (GARD's lognormal), from recorded seeds. K_i and kb_i
  are drawn as P1 draws them, with Σ K_i ρ_i = 100 and N_split = 80. Founders are uniform from 1 to
  9 per type, with 64 seeds per matrix.
- Plus 4 matrices with one entry of 10⁵, so that the factor takes its count-weighted-mean branch
  (κ > κ_limit), as in P1's second case.

**The physical measure's report.** The distributions of the time to the first fission and the
composition at fission (and H at fission under G2), against @1's, with their predicted O(1/N) shift
from the join's (N + 1)/N. It has no pass or fail unless the lead rules one.

**The β plant.**
- **The plant:** the largest entry of each matrix × 1.5, in the @2 world only.
- **Its power is computed at registration from @1 alone,** from the matrix and its plant, both run
  in @1, and never from the comparison. It is the fraction of seeds whose channel sequences
  diverge, beyond rounding, within the first growth.
- **Required:** at least 99% per matrix for T-path.
- **For T-dist,** the plant is the largest entry × 4, and it must shift the registered statistic by
  at least 5 SE at the registered sample size, again computed from @1 alone.
- A plant that cannot reach its power is resized before the tag, never after.

### 5.3 The cost (P3, conservative)

| Protocol | Events | CPU time on one light CPU (at 5 × 10⁴ events/s) |
| --- | --- | --- |
| D1–D3 | About 1.5–3 events per replica per unit of Ω, over 4 rungs summing to 21,250, × 256 replicas × 3 worlds: about 5 × 10⁷ | About 20 min, plus about 1 min of compiling per structure |
| D4–D7 | About 2.5 events per amphiphile per replica, over rungs summing to 2.75 × 10⁵, × 128 replicas × 4 worlds: about 3.5 × 10⁸ | About 2 h |
| G (G1, then G2 through 50 fissions), with @1's runs and the plants' power | About 10⁷ | Minutes; compiling dominates |
| (d)'s own runs | A few thousand steps each | Seconds |

So about 2.5–3 CPU-hours in all, as detached jobs on the light CPUs (AGENTS.md: a run over 10
minutes is detached, with durable logs).

### 5.4 What the protocols do not claim

- **The anchors' scale.** (d)'s accuracy at 10⁵ molecules and above is extrapolated from the rungs
  by the limit's theory (a bias of order 1/N), not measured. The anchors themselves are OL7's
  (D138).
- **Phase B.** The open pore's dynamics are not qualified here.
- **An independent ODE reference.** §7.2's code-blind ODE reference (OL5's) would add a check of
  (d)'s arithmetic against equations, not code. Whether OL5's set carries it is OL5's to say. If
  the lead wants it for OL6, §1.3 and §2 are written to stand alone as its sheet, and the sheet is
  tagged before code.

<!-- §6 onward follows -->
