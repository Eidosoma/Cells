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

<!-- §2 onward follows -->
