# Coupling out of the inventory: species-regulated availability (design)

**Status: accepted, 14 November 2026 (the lead, with the advisor); rulings in §6.3.** The accepted
scope is the junction target; the channel target is pending milestone 1 (ruling 12). No engine code
was added or changed for this note. D155 item 1 authorises the design of one general feature,
*coupling out of the inventory*. D145's gene-regulation hold is narrowed, not lifted.

D155 item 1 reads:
- a species amount sets another operator's control, through the contract's `CONTROL_FACTORS`;
- later, it triggers an event such as division;
- the rest of the gene-regulation track stays held.

**The three contracts this note settles** (the lead's scope correction, from an external
architecture review that the advisor confirmed):
1. **Target routing** (§1.2). Version 1 targets @3's junction availability; the channel-population
   availability is pending milestone 1 (ruling 12). Routing to another operator's controls (a reaction multiplier, a turnover rate, an event's due
   flag) is a separate door. Its shape is designed in §2 because the division trigger needs it; it is
   not built.
2. **Source semantics** (§1.3). The source is the physical inventory itself, sensed as a
   concentration in the target's own cell, through declared laws, into a declared domain.
3. **Evaluation time** (§1.4). The effective control is computed once per step, after the first
   half-steps, and held through every stage of @3's step. This was verified in the code (§1.1).
   Version 1 keeps that evaluation. Feedback goes through a kinetic state, so no stage evaluation is
   needed.

**Consumers** (D144 asks for more than one):
- **Track R** of the [Myc–cyclin T1 review](PAPER_REVIEW_MYC_CYCLINT1_HEART.md) (D155): a pulse, a
  gate on cycle entry, then division triggered by state (review §6c, versions 2 and 3). This
  operator is version 2's gate. Version 3 needs §2 and §3.
- **The GZMK review's item 6** ([review](PAPER_REVIEW_GZMK_AGEING.md) §3): "a slow, writable per-cell
  state that changes transport, secretion or mechanics, with retention, reset and transfer
  distinguished — and with its own timescale declared". Version 1 covers transport. Secretion is
  §2's door, and mechanics has no composite operator yet.
- **The coupled-renewal gate's "causal carriers" row** ([plan](CURRENT_PLAN.md#gate-coupled-renewal)):
  interventions on slow variables, regulatory state among them (§1.13). Its renewal worlds also need
  version 1.1's replacement rule (§1.12).
- **E15** ([path](EXPERIMENT_PATH_PATTERN_RECOVERY.md) §1). Three of its rows use the coupling:
  - row 1(a), junction state driven by cell state;
  - row 5(b), a declared state-intervention event;
  - row 3's self-organised patterns acting on bioelectric controls, the chemical-to-bioelectric
    direction. D152's door "reads of charged or permeant species" (its §7.3) is the other direction.

**Engine models it runs** (AGENTS.md milestone rule):
- `resolved_pump_composite@1` over `resolved_pump_tissue@3`;
- one new operator, `species_regulated_availability@1` (§1), with one new state law,
  `hill_regulated_two_state@1` (§1.5);
- its qualification worlds also run D150's `scheduled_species_turnover@1`, which drives a regulator
  with closed-form kinetics, and the first consumer's world runs D152's `local_species_reactions@1`
  (§4).

No model or solver changes in version 1. Its one change to shared code is manifest-only: the
composite's field map gains a `factors` entry (ruling 6), which changes no program. Its first code
milestone exercises a path no operator has used: a factor on @3's channel availability (§1.1,
milestone 1).

**Basis.**
- The contract: [PUMP_COMPOSITE.md](PUMP_COMPOSITE.md); the [v2 design](PUMP_COMPOSITE_V2_DESIGN.md)
  §1 (energy roles, combination rules) and §3 (R1–R8, the 64-node cap).
- The inventory: the [secreted-species design](SECRETED_SPECIES_TRANSPORT_DESIGN.md) (D150) and the
  [shared-inventory reactions design](SHARED_INVENTORY_REACTIONS_DESIGN.md) (D152), whose Hill
  factor forms and citations this note reuses.
- The lifecycle: the [S5 design](CELL_DIVISION_S5_DESIGN.md), the
  [division design](CELL_DIVISION_DESIGN.md) and the [current plan's](CURRENT_PLAN.md) lifecycle
  gate (milestone 2).
- The review's composition walls (its §6a) and its version plan (its §6c).

**Evidence and log:** `/mnt/workspaces/Cells/inventory-coupling-20261114-01/` (HANDOFF.md: what was
read, the code facts with line numbers, and the citation checks). **S** marks our arithmetic or
interpretation, as in the D150 and D152 notes.

## 0. Summary

1. **One operator per composition, `species_regulated_availability@1`.** It holds declared
   *couplings*, each a factor on @3's junction or channel availability. It also holds declared
   *regulatory states*, each a slow or fast two-state fraction per cell. Its parts are an event map
   and a split part, so it fits the contract as built (§1.1, §1.6).
2. **Target routing** (§1.2). The accepted target is the junction availability, per contact;
   replacement and the bridge already use its factor path. The channel-population availability, per
   population, is pending milestone 1, which checks its path (ruling 12). Leaks and pumps come next,
   on the same path. Other operators' controls are §2's door.
3. **Source semantics** (§1.3).
   - Sensing reads @3's own amount rows, never a copy, as the concentration c = n/V in the target's
     own cell (a junction's two cells).
   - The laws are D152's Hill activation and inhibition, or a regulatory state's fraction, with a
     basal level: F = b + (1 − b) f. So F ∈ [b, 1], and the scheduled availability is the maximum.
   - Volume providers and mask closers are refused in version 1. Amount sensing is rejected.
4. **Evaluation time** (§1.4). The held evaluation is exact for rows @3's step leaves unchanged: the
   cell rows of neutral, impermeant species. An *instantaneous* factor is admitted only on those
   rows. A source that @3's step moves, such as an ion, enters only through a *regulatory state*,
   whose half-steps read the source before and after @3's step. That keeps the composite step
   Strang-symmetric, second order (**S**, measured by acceptance A4). An instantaneous factor of a
   moving row would lag within the step, and is refused. Its door is a hook in @3's stages. Ions are
   admitted through a state (ruling 1), and the definition refuses dt·(k_on + k_off) > 1 (ruling 5).
5. **The regulatory state** (§1.5): ds/dt = k_on u (1 − s) − k_off s, with u a product of Hill
   factors of the cell's species.
   - Retention is 1/k_off. With k_off = 0 it is a saturating integrator of the input (the review's
     "time integral of the active complex").
   - Its half-steps are exact, and s stays in [0, 1].
   - It has no ledger, because it is kinetic state with no free energy, as @3's gates, the bridge's
     aperture and the formation law's deficit are.
   - Interventions write it. Replacement and division write it only at their doors.
6. **Ownership** (§1.7). It owns its states, switches and diagnostics. It writes no @3 field. It reads
   species rows, which stay @3's. Its factors multiply replacement's and the bridge's in declared
   order.
7. **Energy** (§1.8). A factor books nothing. Within a step it is a constant in [0, 1] times a
   scheduled availability, the same object as a schedule that changes at that step. @3 books every
   gated flux at the effective value, and each gated rate keeps the sign of its own driving force.
8. **Idleness, crossrev and the batch signature** (§1.10).
   - Not declared: every program is unchanged.
   - Declared but idle or switched off: bitwise equal to the composition without it.
   - The structure enters the batch signature; the parameters are per-world bindings.
9. **Version 1 is a static tissue** (§1.12), as D150's and D152's version 1s are. It composes with @3,
   injection, membrane state, D150's two operators, D152's operator, and replacement@1 on slots it
   does not replace.
10. **Routing and the trigger are doors** (§2).
    - A *rate route* multiplies another operator's rate control, evaluated in that operator's own
      half-steps.
    - An *event route* sets an event operator's due flag from a crossing.
    - Everything prescription binds at the definition today is listed and mapped onto milestone 2's
      five open decisions. None is settled.
11. **Newborn integration** (§3).
    - Today's refusals are real missing interactions and stay until qualified.
    - A reusable contact-maturation process, initialised by replacement or by division, is new
      work.
    - The order is four named steps, each with conservation, identity, restart and event-boundary
      checks.
    - The start state of a division-born contact is a question for the user (§3.5).
12. **Qualification** (§4). The first acceptance is numerical, against references written from
    Appendix A by an agent that never reads the code.
    - Ledgers cannot see a wrong factor, so the guards of record are value checks: a reciprocal
      feedback system against a coupled-ODE reference under refinement; the identity, zero and
      multiple factor cases; locality; restart and window identity; the first consumer's local
      accuracy.
    - The yeast cell-cycle model does not fit (§4.6).
13. **Not authorised** (§5): a transcription network or any network inside the operator, production
    laws, routes to other operators' controls, and anything named for one paper.
14. **Effort** (§6): about 5.5 agent-days (4.5 to 7) for version 1, plus CPU minutes.

## 1. The operator (version 1)

### 1.1 The contract as built (code read at 62ca548)

**Evaluation time, verified.**
- `Composition.split_step` (`models/pump_composite.py`, 517–580) runs in this order:
  1. the event maps;
  2. every operator's first half-step, in declared order;
  3. one evaluation of `control_view(control, current, p)` (line 547) and of the view, on the state
     after (1) and (2);
  4. @3's checked step, behind `jax.lax.optimization_barrier` (line 550);
  5. the second half-steps, in reverse order.
- @3's `imex_step` (`models/surface_pump_v3.py`, 654–717) uses that one control at every stage. Its
  run-time stiffness refusal (`membrane_rate`) also reads it, so it sees the factored availability.
- On the split path an inner RK4 step holds it in the same way.
- **The coupled RK4 path** (`rk4_checked_step(self.rhs, ...)`, line 514) evaluates the control view
  at every stage. It applies only with a "coupled" split part (water) or an in-step process (the
  symport), both refused here (§1.12).
- `readouts` (608), `control_domain_valid` (664) and `observe_history` (985–1000) evaluate the
  factors at the state they are given. Observation therefore reports the factor at each saved row's
  state, which is not the value held inside the step that produced the row (R6).

**What the contract admits.**
- `CONTROL_FACTORS` must name inner control fields (`structure_errors`). @3 has five availabilities:
  - `membrane` (passive leaks, per patch);
  - `junction` (per contact);
  - `channel` (per population);
  - `pump` and `calcium_pump` (per patch).

  They are scheduled fractions in [0, 1]. Factors multiply in declared operator order
  (`adapter.control_view`, 248–254).
- **Only `junction` has ever been factored**, by replacement@1 (A = 1 − deficit on every contact,
  exactly 1 on formed ones) and by the bridge (a/a₀ on bridges, exactly 1 elsewhere). The channel,
  leak and pump factors would pass through `control_view` and `held_schedules` for the first time.
  `held_schedules` holds an observed row's schedules at their effective values.
- `control_factors(state, p, *, xp)` receives **no control and no view**. A factor cannot read a
  schedule, the current volume or the masks except through owned state.
- A factor operator contributes through the control view **even when it is statically idle**. The
  view loops over every factor operator; `split_step` skips only idle parts.
- `check_declarations` refuses an operator with no part unless it is a state owner with
  `ACCEPTS_WRITES` and `VIEW_FIELDS`. A factor-only operator is not admissible as built.
- `STATE_RESETS` must be inner state, and `ACCEPTS_WRITES` requires owned ledgers. **No path lets
  another operator's event write an intensive, operator-owned state**, such as a regulatory state
  at a birth.
- @3's definition-time explicit-rate bound (`surface_pump.explicit_rate_bound`) reads the declared
  permeabilities at availability 1. R5's worst cases and the bridge's rule ("availability only
  falls") assume the same. **An effective availability above its schedule is not admissible.**

**What is not reused.** `network_control_factors@1` (`processes/network_control.py`) is the
calcium-energy family's regulation.
- It carries its reference's conventions: ordered overwrite rather than multiplication, signed
  maximum effects, a voltage-dependent half-saturation, and direct and indirect modes.
- It works over its own arrays, outside the composite contract.
- As with D152 §1.2, it stays separate and unchanged, and nothing here wraps it.

### 1.2 Contract 1: target routing

| Target | Inner control | Element | Version |
| --- | --- | --- | --- |
| **Junction availability** | `junction` | One contact | **1, the accepted scope** (ruling 12): its factor path is exercised today |
| **Channel-population availability** | `channel` | One population | **1, pending milestone 1** (ruling 12), which shows its path (§1.1) |
| Passive leak availability | `membrane` | One patch, all its leak species | 1.1: the same path, with its own first-use check |
| Na/K or Ca pump rate | `pump`, `calcium_pump` | One patch's pump | 1.1, as above; on dividing cells it meets wall W3a (§3.2) |
| Another operator's rate control | That operator's control | Per its axes | Door (§2.1): a rate route |
| An event's due flag (the division trigger) | That operator's event | One declared event | Door (§2.1–§2.2): an event route |

- **Scope of a version 1 target.** It is an element of a live cell that replacement@1 does not
  replace, in a static tissue. Its factor lies in [b, 1].
- The class declares `CONTROL_FACTORS = ("junction",)` until milestone 1 passes, and refuses channel
  targets until then; it then declares `("junction", "channel")`. A field that no coupling targets
  is not returned, a static choice by layout shape. An untargeted element selects exactly 1.
- **The declaration names the target's operator** (`"operator": "inner"`), so §2's routes extend
  this declaration without changing its form (§1.6).

### 1.3 Contract 2: source semantics

| Item | Version 1 |
| --- | --- |
| **Entity** | A cell's cytosolic amount of one of @3's species rows: the compartment entity's material. Sensing reads @3's state, n = `amount_reference` + `amount_increment`, never a second copy |
| **Sensing** | **Concentration**, c = n/V in mM (fmol/pL), with V the cell's declared volume. **Amount sensing is rejected.** A half-saturation is a dissociation constant, which is a concentration, so a law of the amount would ignore dilution and depend on the declared volume's scale |
| **Species admitted** | *Instantaneous factors:* neutral, impermeant inventory species, under D150's declaration rules (`species_common.parse_species`). These are the rows that @3's step does not move (§1.4). *Regulatory-state inputs:* any species row of the world, ions included, through a read-only list (D152 §7.3's door "reads of charged or permeant species": reads book nothing). Ions are admitted through regulatory states only (ruling 1), by the read-only read below |
| **Laws** | `hill_activation` x^n/(K^n + x^n) and `hill_inhibition` K^n/(K^n + x^n), D152's forms and log-space evaluation. `state_fraction` s and `state_complement` 1 − s of a regulatory state (§1.5). Every coupling then applies F = b + (1 − b) f |
| **Units** | K in mM; n > 0, dimensionless; rates in s⁻¹; b, s and F dimensionless |
| **Target domain** | F ∈ [b, 1] ⊂ [0, 1], with 0 ≤ b < 1. The effective availability is a_sched × Π F ≤ a_sched ≤ 1. Hill factors are positive at positive c; a state factor reaches exactly 0 only when b = 0 and s = 0 or 1 |
| **Axes** | A channel population k lives on patch `channel_membranes[k]`, whose cell is `membrane_cell[...]`. A contact e joins `junction_sender[e]` and `junction_receiver[e]`. The side is `first`, `second` or `both` (ruling 4): first and second are the contact's declared cells (@3's `junction_sender` and `junction_receiver`), and both is the product of the two cells' factors. A route is (coupling, element). Its cell, species or state, and element indices are integer layout arrays bound once (R1) |
| **Locality** | A target reads only its own cell, or a contact's two cells. No cell reads another cell's inventory. Outside-node sources (paracrine sensing) are a door (§1.4) |
| **Volumes and masks** | The declared ones. Every provider of a volume and every closer of a mask is refused at the definition (§1.12). Concentration sensing at the current volume and the live masks is the water and closer door, and it needs the view in `control_factors` and in half-steps (§1.12) |
| **Failure** | Unsupported combinations fail at the definition (parse and `check_definition`), or at binding where an index map is built. None fails at run time |

**The "both" product (S, a modelling choice).** Each endpoint's hemichannels are taken to be
regulated by their own cytoplasm, independently, so the contact's available fraction is the product.
A declared side, first or second, is the alternative (ruling 4).

**The read-only read (ruling 1): one mechanism, reused by D152.** It serves every operator that reads
a row it does not write.
- **A read-only species list** in the declaration, parsed by one shared function beside D150's
  `species_common.parse_species`. It admits any species row of the world, ions included, with D150's
  identity form (null for an ion). A read-only species is never a write target of the reader.
- **A read of a row that @3's step moves** is evaluated only in half-steps, which read it before and
  after @3's step. It is never frozen through @3's stages.
- **Reads book nothing.**
- **D152's version 1.1 door**, "reads of charged or permeant species" (its §7.3), reuses this list
  and this rule for its factors and catalysts rather than building a second mechanism. Its
  half-steps already read before and after @3's step, so its reads are second order in the same way
  (**S**).

### 1.4 Contract 3: evaluation time

**Decision: version 1 keeps the held evaluation of §1.1 and needs no stage evaluation.** The reasons
depend on what the source row does inside @3's step.

| Source | What @3's step does to it | Coupling form admitted | Order of the composite step |
| --- | --- | --- | --- |
| A neutral, impermeant species in a cell (D150 and D152 inventory) | Nothing: zero membrane and junction permeability, refused otherwise, and no face touches a cell | Instantaneous or kinetic | Second order (**S**). Freezing F through @3's step is exact, since its argument is constant there, so only the operators' Strang splitting remains (Strang 1968; Hundsdorfer & Verwer 2003, ch. IV) |
| An ion in a cell | Moves it: channels, leaks, pumps, junctions | **Kinetic only**, through a regulatory state (ruling 1) | Second order (**S**). The state's two halves read the ion before and after @3's step, and @3 sees the state's midpoint value. That is Strang splitting of the state's flow against @3's flow with the state as a parameter; acceptance A4 measures it |
| An outside node's species (paracrine sensing) | Moves it through the faces | Refused in version 1 | Door: through a regulatory state, as for ions; probe P2 |
| A permeant neutral species | Would move it | Refused (D150's rule; the D148 round for neutral species on junctions comes first) | – |

**Why an instantaneous factor of a moving row is refused.** It would be held through all of @3's
stages at its value after the first halves.
- That is a lagged, explicit coupling: an O(dt) error per unit time in the coupling term, so the
  scheme drops to first order (**S**).
- It can close a feedback loop whose stiffness @3's explicit bound cannot see. The bound reads
  declared conductances at availability 1, not the factor's sensitivity to the state it moves.
- Second order would need the factor evaluated inside @3's stages. That means a new hook in @3's
  `imex_step` beside its membrane-process hook, which is an @3 change (a new ID or a D148 round),
  not this operator's. Probe P3 would measure the lag first, if a consumer needs instantaneous ion
  sensing.

**The physics of the kinetic route.** Regulation by binding has finite rates. The regulatory state
is that binding's two-state kinetics, and its quasi-steady limit is a Hill factor (Appendix A.3).
The kinetic form is therefore the physical model, and the instantaneous factor is the limit used
where the source does not move.

**Order within the operator list (S).** Each order is second order.
- Placed after D150's and D152's writers, the state's two halves both read the source at the
  midpoint of those writers' flows (a midpoint rule).
- Placed before them, its halves read the source at the step's start and end (a trapezoid).
- The control view reads the state after every first half either way.
- **The recommendation:** after the writers, and after replacement, so the order of factors is
  abundance, then aperture, then regulation (§1.7).

**Stability and the rate limit (ruling 5: no unenforced limit).** The state's half-step is exact and
unconditionally stable, but the splitting is not. A state that relaxes within one step makes @3's
held midpoint value an endpoint value.
- **The rule.** u is a product of Hill factors in [0, 1], so λ = k_on u + k_off ≤ k_on + k_off. The
  definition refuses dt·(k_on + k_off) > 1, as D152 refuses dt·L > 1. The rule is enforced, not a
  declared regime.
- **The loop (S).** Its gain per step is the state's change times the target's effect on the source
  over one step. For cell ions this is far below 1 at millisecond steps: a cell's ion content
  relaxes over seconds to minutes.
- **A4** measures the order, including a fast arm at the largest admitted rates, dt·(k_on + k_off)
  near 1, and reports the order constant there.

### 1.5 The regulatory state

**Law `hill_regulated_two_state@1`.** For each declared state and each of its cells:

    ds/dt = k_on · u · (1 − s) − k_off · s,     u = Π_j f_j(c_j),

with each f_j a Hill activation or inhibition of a species row of that cell (D152's rule: factors
multiply). At least one input is required, and s(0) = s₀ ∈ [0, 1].
- **Its basis.** This is the deterministic kinetics of a population of two-state units. Each unit
  switches on at a rate k_on u set by its regulators and off at a rate k_off. It is the
  gating-variable form of Hodgkin & Huxley (1952), and a covalent-modification cycle in its
  first-order regime (Goldbeter & Koshland 1981; their zero-order ultrasensitivity is not included).
- **Units and sources.** When the units are unnamed, the state is phenomenological. Its rates are
  declared per use, with sources or labelled synthetic. The engine holds no default.
- **The step.** Each half-step is the exact solution with u frozen at its value at the half-step's
  start:

      s' = s + (k_on u (1 − s) − k_off s) · h · φ(λh),   λ = k_on u + k_off,   φ(x) = (1 − e^(−x))/x,

  with φ(0) = 1 and φ computed with `expm1`. In exact arithmetic s' lies between s and the
  quasi-steady value s* = k_on u / λ, so s stays in [0, 1]. In floating point a value outside
  [0, 1] is refused, never clipped. Where λ = 0, or for an undeclared (state, cell), the start value
  is selected.
- **Zero rates are admitted.** k_on = k_off = 0 gives a frozen state, held at s₀ or at its last
  write. A3's zero and pass-through cases use it.
- **The rate limit.** The definition refuses dt·(k_on + k_off) > 1 (§1.4, ruling 5).
- **What it can be (S):**
  - a fast binding step, for ion feedback;
  - a low-pass filter of its input, with time constant 1/λ;
  - a leaky integrator, with retention 1/k_off;
  - with k_off = 0, a **saturating integrator**, s = 1 − (1 − s₀) e^(−k_on U), U = ∫ u dt. A threshold
    on s is then a threshold on the integrated input, which is the review's "time integral of the
    active complex".
- **Diagnostics.** Two diagnostics are recorded per (state, cell):
  - `regulatory_input_integral` U, accumulated exactly per half-step (u frozen: U += u h);
  - `regulatory_crossing_step`, the index k of the first step end k·dt at which s ≥ θ, for a
    declared `crossing_level` θ (−1 before it). It is set by the event map at the next step start,
    from an operator step counter.

  Their energy role is diagnostic (v2 §1.1). They give the first consumer its exposure and its
  threshold time at step resolution, whatever the observation interval (§4.5), and they are the
  trigger's detection half (§2.2).
- **A known limit of the crossing record.** A crossing in a run's final step is never recorded,
  because no later step start runs the event map. The summary reports a final row with s ≥ θ and no
  record as such, and the trigger door inherits the rule.

**Retention, reset and transfer** (GZMK item 6's three, and who writes the state at each):

| Item | Version 1 | Who writes it |
| --- | --- | --- |
| Retention | Declared k_off: half-life ln 2 / k_off; with k_off = 0 the state is held | Its own law |
| Reset by intervention | `regulatory_writes` sets s to a declared value at the start of the step leaving t | This operator's event map |
| Reset at replacement | **Refused** on slots that replacement@1 replaces | 1.1, when the coupled-renewal gate asks (ruling 10, D144), for prescribed events: this operator's event map at replacement's event steps, which it reads from replacement's schedule at the definition. A template's newcomer takes the template's declared value; a donor copy takes the donor's s, an inheritance route as D139 defines one |
| Transfer at division | **Refused** (closers, §1.12) | Prescribed divisions: this operator's event map, after the partition's, copies the parent's s to both daughters (an intensive copy, as the partition copies gates) or sets a declared newborn value. Triggered divisions: **no path exists** (§1.1). It needs a carry mechanism in the contract (§2.4) |

**Why it needs no ledger.**
1. It is not a conserved quantity. No material, charge, volume or area moves when s changes.
2. The model assigns it no free energy. It enters no chemical potential, and no flux except through
   the factor.
3. Its maintenance cost, a modification cycle's ATP for instance, lies outside the model. That limit
   is declared, as D150 declares its synthesis cost.
4. The precedents have no ledgers either: @3's gates (set at events through `STATE_RESETS`), the
   bridge's aperture ("not a conserved quantity, so the operator has no ledger of its own") and
   replacement's formation deficit.

Its energy role is kinetic.

**When a species is better.** A memory whose molecular carrier is known, and whose amount matters,
is better written as D152 species.
- Such an amount splits at division, swaps at replacement and carries an identity.
- An example is a two-species modification cycle M ⇄ M*: a Hill-factored driven activation and a
  first-order driven return. Its moiety is conserved and its work is booked.
- It costs two species rows against the 7-species cap (W4, §3.2) and books free energy for a
  molecule.
- The operator's state is for regulatory states with no named carrier, and for binding kinetics on a
  target.

**Why a regulatory state rather than species (ruling 1).** It is not the only second-order route for
feedback: a D152 species pair with read-only reads of the ion would also be Strang second order,
since its half-steps read the ion before and after @3's step. Three reasons hold:
- there is no named molecular carrier, so there is no moiety to conserve and no free energy to book;
- the species cap: a pair costs two of the world's seven rows (W4, §3.2);
- binding kinetics on a target belong to the target's regulation, not to a molecule in the
  inventory.

It is also the first consumer's gate (§4.5).

### 1.6 Declaration and parts

```json
{"law": "species_regulated_availability@1",
 "species": [{"id": "X", "catalogue": null, "evidence": null},
             {"id": "Na", "catalogue": null, "evidence": null}],
 "states": [
   {"id": "s1", "law": "hill_regulated_two_state@1", "cells": ["c0", "c1"],
    "inputs": [{"law": "hill_activation", "species": "Na",
                "half_saturation_mM": 12.0, "hill_coefficient": 2.0}],
    "on_rate_per_s": 50.0, "off_rate_per_s": 5.0, "initial": 0.1, "crossing_level": null}],
 "couplings": [
   {"id": "j_regulated",
    "target": {"operator": "inner", "control": "junction", "ids": ["j01"], "side": "both"},
    "source": {"state": "s1"}, "law": "state_complement", "basal": 0.2},
   {"id": "k_regulated",
    "target": {"operator": "inner", "control": "channel", "ids": ["kleak_c0"], "side": null},
    "source": {"species": "X"}, "law": "hill_inhibition",
    "half_saturation_mM": 1e-4, "hill_coefficient": 1.0, "basal": 0.0}]}
```

The values are illustrative and synthetic. The channel coupling is admitted once milestone 1 passes
(ruling 12).
- **Every key is explicit** (D152's amendment). Hill laws take `half_saturation_mM` and
  `hill_coefficient`; state laws take neither.
- **Species.** Each listed species carries D150's identity form (catalogue reference and kind of
  evidence). An ion's is null.
- **The experiment** adds:
  - `coupling_controls`: one schedule per coupling, from time 0, of `enabled` ∈ {0, 1};
  - `regulatory_writes`: (state, cell, time, value) entries, with the times exact multiples of dt
    inside the horizon.

**Parts.**
- **An event map** at each step start. It:
  - advances the step counter;
  - copies the switches from their schedule into state, since `control_factors` sees no control
    (§1.1);
  - applies due writes (a count per (state, cell), refused when stale, as replacement refuses a
    stale generation);
  - records crossings.
- **A split part** with exact half-steps of the states (`exact_two_state_half_steps@1`), kept
  "split" under an RK4 inner step.
- **`control_factors`**: per element, the product of its routes' factors in declared order, with
  padding slots exactly 1, and untargeted elements and switched-off couplings selected as 1.
- **Statically idle** when it declares no state, no scheduled change and no crossing level. Its
  factors still apply through the control view, as the bridge's do.

**State** (zero or declared at the start; per world):

| Field | Axes | Role |
| --- | --- | --- |
| `regulatory_state` | [state, cell slot] | Kinetic, in [0, 1] |
| `regulatory_input_integral` | [state, cell slot] | Diagnostic, ≥ 0 and non-decreasing |
| `regulatory_crossing_step` | [state, cell slot], int64 | Diagnostic, −1 until the crossing |
| `regulatory_writes_applied` | [state, cell slot], int64 | Kinetic counter, as replacement's `generation` |
| `coupling_enabled` | [coupling] | Kinetic, 0 or 1 |
| `coupling_step_count` | scalar, int64 | Kinetic counter; time = count × dt |

**Readout column:** `coupling_factor` [route], the route's F at each saved row's state.

### 1.7 Ownership, and factors with replacement's and the bridge's

| Field | Owner | Writers | Readers |
| --- | --- | --- | --- |
| The state, diagnostic and counter fields above | This operator | Its event map and half-steps only | Its factors; later the event route (§2.2) |
| Parameters and index maps (layout) | This operator | – | – |
| @3's species rows (`amount_increment`) | @3 | @3's step, D150's operators, D152's operator, replacement's events, injection | This operator: **read, never written** |
| @3's `junction` and `channel` availabilities | @3, from the experiment's schedules | – | @3's step, at the product of every factor operator's multipliers |

- **One operator per composition.** `structure_errors` refuses a law that appears twice, so every
  coupling and state is declared in one place, as D152's network is.
- **It writes no @3 field.** `ENTITY_WRITES`, `STATE_RESETS`, `VIEW_FIELDS`, `ACCEPTS_WRITES`,
  `EVENT_REPLACES`, `CLOSES` and `REPLACES` are all empty.
- **Reads are not writes.** This is D152 §1.1's rule for catalysts and factors. The operator's reads
  do not count against D152's rule of one local-kinetics writer per row.
- **`CONFLICTS_VIEW`** is D150's static-tissue list: `volume`, `extracellular_volume`, `active`,
  `outside_active`, `membrane_active`. Under S5's rule a closer counts as the provider of its mask.

**Factors from several operators.**
- **The arithmetic.** The scheduled availability is multiplied by each factor operator's
  multipliers in declared operator order (`adapter.control_view`): replacement's A, the bridge's
  a/a₀, this operator's product. Every factor lies in [0, 1], so the order changes rounding only.
- **The physics (S).** The product is the physical availability only when its factors stand for
  independent mechanisms: abundance (formation), geometry (aperture) and regulation (this operator).
  Two operators modelling one mechanism on one element would double-count it. The composite cannot
  check meaning, so each operator's summary names the mechanism its factor stands for. §3.3 keeps
  one owner of junction abundance.
- **In version 1** the operator refuses targets on replaced slots and their contacts, and the
  partition and bridge are refused. So its product meets only the scheduled availability, and
  replacement's exact 1.0 on untouched contacts. Version 1.1's replacement composition is the first
  to multiply two non-trivial factors on one element. Its guard: the product against an independent
  evaluation, and order invariance to rounding.
- **The manifest (ruling 6).** The field map records each control's owner (`inner`) but not the
  chain of factors. Version 1 adds a `factors` entry, {control: [laws in declared order]}, in
  `pump_composite.field_map`. It is manifest-only: no program changes, so crossrev is identical. The
  manifests of compositions with replacement@1 or the bridge gain the key too. Earlier manifests
  lack it, and readers treat it as optional, as with `field_owners`.

### 1.8 Energy: a factor books nothing

1. **Roles** (v2 §1.1). The operator adds kinetic fields (the states, switches and counters) and
   diagnostic fields (the integrals and crossings). It adds no material, volume, area or charge
   accumulator, no heat or work field and no free-energy owner. It has no ledger, no ledger term and
   no magnitude term.
2. **A factor is a schedule written by state.** Within a step it is a constant in [0, 1] multiplying a
   scheduled availability in [0, 1], held through @3's step. That is the same object as a scheduled
   availability that changes at that step, which @3 admits at every step. @3 books each gated flux,
   with its heat and, for version 1.1's pump targets, its work, at the effective availability. Acceptance A3 shows the
   equivalence bit for bit.
3. **The sign (S).** Each gated rate is the availability times a function that vanishes, and changes
   sign, with its own driving force. For constant-field leaks, channels and junctions that force is
   the electrochemical gradient; for the mass-action pumps it is the cycle affinity, ATP included.
   So at any availability ≥ 0 every heat increment keeps its sign, as it does under schedules, and
   the dissipation check's monotonicity is untouched.
4. **Reading costs nothing in the model.** No species is consumed or moved by being read, as for
   D152's catalysts and factors.
   - **Declared limit:** the regulator's bound fraction is neglected. That is quasi-steady binding
     without ligand depletion, the Hill factor's own assumption (Weiss 1997).
   - Where binding sequesters a significant share, the binding must be explicit: a D152 passive
     reaction, or D150 §2.5's occupancy door.
5. **The state carries no free energy** (§1.5).
6. **No demon (S).** In a deterministic continuum model, every gated process dissipates at every
   instant at any availability ≥ 0. Feedback through the availability therefore cannot extract work,
   whatever the factor depends on.

**The consequence:** there is nothing to book, and so nothing for a ledger to detect. §4.2 draws the
conclusion for the guards.

### 1.9 Numerics beyond evaluation time

| Solver or mode | Version 1 | Why |
| --- | --- | --- |
| IMEX ARS(2,2,2) | Admitted | Second order (§1.4) |
| IMEX Euler | Admitted | First order overall |
| RK4 (reference runs) | Admitted, "split" | The split part runs around @3's RK4 step, as the bridge's and replacement's do. Nothing is booked, so nothing loses RK4's sharp bound |
| Stationary analysis | Refused | It refuses the composite's ID (D150 probe 2) |
| Projective and coarse modes | Not admitted | `execution.projective` supports @1 to @3 only |
| vmap, windows, restart, snapshots | Admitted | Parameters are per-world bindings, and all state is state (R7) |

- **The factor's evaluation.** z = n (ln x − ln K); activation is ln f = −logaddexp(0, −z), inhibition
  ln f = −logaddexp(0, z). This is D152's kernel form, finite at the trace (D150 §1.3) and at large x.
  The basal combination is linear, so b = 0 gives f exactly.
- **Shared code (ruling 7).** D152's evaluation is inline in `species_reactions.route_rates` (around
  line 947, `-logaddexp(0, ∓z)`), not a function, so it cannot be called unchanged. Version 1 writes
  a neutral helper for the log-space Hill factors, used by this operator, with a bitwise-agreement
  test against D152's expression. D152 stays untouched during MG0c and adopts the helper at its next
  version, under crossrev.
- **Step bounds.** One of its own: dt·(k_on + k_off) ≤ 1 for every state (§1.4), checked at the
  definition. `inner_check_spec` is unchanged, because a factor ≤ 1 keeps @3's bound, taken at
  availability 1, valid. @3's run-time refusal reads the effective availability.
- **Cost (S).** O(routes) per step for the factors and O(states × cells) per half-step. Both are
  negligible beside @3's field solves. The operator provides no field input, so the 64-node cap does
  not apply to it.
- **The 30-minute rule.** Every check uses worlds of one to a few cells and reaches the code in
  seconds.
- **Mean field.** D150 §1.3's caution applies. Below about 10² molecules per cell, a Hill factor of a
  regulator is not meaningful.
- **Rows saved at an event time.** The state saved at a switch or write time t_e is the end of the
  step that ends at t_e, before the event map of the step leaving t_e runs. The controls observed at
  t_e are the schedules' values from t_e, the composite's convention for every event operator. Such
  a row therefore shows the pre-event state (the old switch, the unwritten state) against the
  post-change schedules of @3's availabilities. An analysis reads an event's effect from the next
  row, and A8 checks that the convention holds across restarts and windows.

### 1.10 Idleness (D136), crossrev and the batch signature

There are three claims, in D150's and D152's form.
1. **Not declared. Promised.** The operator and the Hill helper are new modules. Version 1's one
   shared change is the field map's `factors` entry, which is manifest-only (§1.7). Every existing
   composition's jaxprs, constants and bindings are identical under the constants-aware crossrev, in
   all five sets. The operator's own set gets its first record at
   landing.
2. **Declared, but idle or switched off. Promised:** every field is bitwise equal to the composition
   without the operator. That covers three cases:
   - no couplings and no states: nothing is returned, and the parts are statically idle;
   - every coupling switched off: each factor selects exactly 1, and availability × 1.0 is exact;
   - a state with no input change and λ = 0: its start value is selected.
3. **Species declared and read by no coupling, against no species.** Reported, not promised (D150's
   claim 3).

`CONTROL_FACTORS` is a class attribute, so a composition with this operator holds the junction and
channel schedules at their effective values during observation, even where nothing is targeted. The
held value equals the scheduled one (**S**, from the code). Milestone 1 checks it.

**Batch signature:** the law, then each state's id, cells and input laws and species, then each
coupling's target operator, control, ids and side, source kind and law. The parameters (K, n, b,
k_on, k_off, s₀ and θ) are layout arrays bound per world. They are never closed-over constants, and
the crossrev records show it (D148).

### 1.11 Refusals

**At the definition:**
- **Species.** An instantaneous source that is not a neutral, impermeant inventory species. A species
  the model does not declare. An identity that differs from a D150 or D152 declaration. More than 7
  species in the world (D150's cap and message).
- **Targets.** A target operator other than `inner` in version 1. A control other than `junction` or
  `channel`. An unknown element id, or an element named twice by one coupling. A side on a channel
  target, or a junction side other than first, second or both. A channel target before milestone 1
  passes (ruling 12).
- **Laws.** A law that does not match its source kind. K ≤ 0, n ≤ 0, b outside [0, 1), negative
  rates, s₀ or θ outside [0, 1], a state with no input, a state with dt·(k_on + k_off) > 1
  (ruling 5).
- **Locality.** A state source not declared in every cell the coupling reads.
- **Replacement.** A coupling target, a state cell or a junction endpoint on a slot that
  replacement@1 replaces.
- **View conflicts** (`CONFLICTS_VIEW`): water, the lumens, replacement@2 (through its water),
  insertion@1 and @2, the partition and the bridge (which requires the partition).
- **Schedules.** A switch schedule that does not start at 0. A change or write off the dt grid or
  outside the horizon. Two writes to one (state, cell) at one time. A write value outside [0, 1].
- **Keys.** Unknown keys and duplicate ids.

**At run time:** a non-finite or out-of-range state or factor (the operator's domain), and a stale
write count. Either refuses the step, which returns the start state.

### 1.12 What composes and what is refused

| With | Version 1 | Why |
| --- | --- | --- |
| @3 alone; `electrode_current_injection@1` | Composes | No view conflict. Injection's charged carriers may be state inputs (kinetic form only) |
| `membrane_entity_state@1` | Composes | It provides membrane views; this operator multiplies controls |
| D150's turnover and exchange | Composes | They write rows this operator reads. Any order is second order (§1.4) |
| D152's reactions | Composes | Reads are not writes (§1.7) |
| `scheduled_cell_replacement@1` | Composes on slots it does not replace | Rates and couplings belong to the occupant (D150 §5.2), and the state needs a reset rule. The 1.1 door, when the coupled-renewal gate asks (ruling 10): D150's occupant tables for parameters, and §1.5's reset and inheritance |
| Water; the lumens; replacement@2 | Refused (volumes) | See below |
| Insertion@1 and @2; the partition; the bridge | Refused (masks) | See below |
| The k-anion symport | Waits | It requires water |

**Beside water.** Concentration sensing would read c = n/V at the declared V while water changes the
real volume, so the composition is refused.
- **The door** is concentration at the current volume: a `VIEW_READS` of `volume`, with D150 §5.1's
  relaxation for a read with no provider, plus the view passed to `control_factors` and to the
  half-steps. Both are static changes in `contract.py` and `pump_composite.py`, under crossrev.
- The operator books no free energy, so it needs none of water's endpoint free energy. Its water
  door is smaller than D150's and D152's.

**Beside closers.** Pending and retired slots are padding at the view, but `control_factors` and the
half-steps read the declared layout. The operator would read a pending daughter's declared anchor as
a live regulator, and evolve a state on a slot that does not exist yet, so the composition is
refused.
- **The door:** hold every state on a closed slot, selected by the view's liveness at run time;
  carry it at births (§1.5); and evaluate factors at the view. That needs the same contract change.
- **So the operator adds no new wall.** It sits behind walls W1 and W3c with D150 and D152 (§3.2).

### 1.13 Interventions (the causal-carriers row)

| Intervention | How | Booking |
| --- | --- | --- |
| Remove the driver | D150's and D152's schedules (exists) | Theirs |
| Write or clear the regulatory state | `regulatory_writes` | None: kinetic state, the reset class of @3's gates |
| Cut the coupling: the target stops responding | `coupling_controls` | None |

Each changes one slow variable in place, at an exact step start, with restart across it bitwise
(A8). A booked intervention on a *material* slow variable, such as ion loading, is the other half of
E15 row 5(b). It belongs to the operators that own that material, not to this one.

## 2. Routing to other operators' controls, and the event trigger (doors)

Neither door is built in version 1. Their shapes are fixed now so that version 1's declaration and
state already fit them.

### 2.1 The routing door's shape

**Today `CONTROL_FACTORS` reaches only @3's controls.** It cannot reach a reaction multiplier, a
turnover or exchange rate, or an event's due flag.

**Two kinds of route:**

| Route | Target operator declares | Source declares | Evaluated |
| --- | --- | --- | --- |
| **Rate route**: a factor in [b, 1] on a rate control | `ROUTABLE_CONTROLS = {control: "rate"}`, for example D152's `reaction_multiplier`, D150's production, clearance, secretion and uptake rates | `target: {"operator": "<law>", "control": "<control>", "ids": [...]}` and a §1.3 law | **In the target's own half-steps**, from the state that half-step receives. The two halves read before and after @3's step, so the route is second order (**S**), with no frozen-through-@3 approximation |
| **Event route**: a condition sets a declared event's due flag | `ROUTABLE_EVENTS = {event: "due"}` on an event operator, for example a triggered partition (§2.2) | `target: {"operator": "<law>", "event": "<event>", "ids": [...]}` with a condition: a regulatory state crossing θ upward, optionally with a declared delay | **At the step start**, before the target's event map, from state |

**The contract change** is in `contract.py` and `pump_composite.py`.
- The composite wires routes when the composition is built, as it wires `ACCEPTS_WRITES`.
- It refuses a route to an undeclared control.
- It passes each target operator a routed control in its half-steps and events, by a static
  per-operator branch. A composition without routes is unchanged, and crossrev shows it.

**Energy.** The target operator books as today.
- A factor on a D150 or D152 rate is the same object as a scheduled rate.
- D152's multiplier on a passive reaction scales both directions, so detailed balance is kept.
- Driven routes book their exact ΔG.

**Consumers.**
- The division trigger (§2.2).
- State-dependent secretion: E15 row 2(b), and GZMK item 6's "secretion".
- Regulated production through D150's turnover.

**The loop it closes.** Rate routes close a species → control → production loop. That is a
regulatory loop. Whether it stays within the narrowed hold or waits for the gene-regulation
decision is the user's question 2 (§6.4).

### 2.2 The event trigger as an event route

- **What it would be.** A declared condition on a regulatory state fires a declared event of a
  lifecycle operator, either at the next step start or a declared delay after the crossing. The
  crossing is `regulatory_crossing_step`; the delay is k_c + ⌈delay/dt⌉ steps.
- **The first case.** A division from a **pre-declared tree**, with daughter slots, fractions and maps
  declared, and only its time determined by state.
- **Latching.** Each declared event fires at most once, latched by the event operator's own applied
  state (the partition's `division_applied`).
- **Two contract options for milestone 2's note:**
  - (a) the event route of §2.1, where the composite computes the condition and passes due flags;
  - (b) a declared cross-operator state read (`STATE_READS`), where the event operator evaluates the
    condition itself.

  Option (a) keeps the condition with the state's owner and the event with its operator, so one
  mechanism serves every event operator. This note leans to (a); it does not settle it.
- **The operator's split comes with this door** (ruling 2). Version 1 keeps one operator. The trigger
  is the first reader of a state outside it, so the state owner and the factor provider separate
  when this door is designed.

### 2.3 What prescription binds at the definition today

| Bound at the definition | Where |
| --- | --- |
| Event times on the dt grid, inside the horizon | The composite's `check_definition` (`schedule_times` of every event operator) |
| Each event's due flag, built from a schedule | The partition's `partition_due`; replacement's `generation` counts |
| Daughter slots, fractions and maps; anchors as exact fractions of the parent's | Partition parse; S5 §3.2 and §6.3 |
| D150's occupant controls: each slot's rates from its occupants over time | `species_common` occupant tables |
| Living intervals read from schedules | The partition's `living_interval`, insertion@2's onset rules, injection's interval refusal, lumen@2's facing patches, D150 v1.1's planned rule |
| The bridge starts at its division's time and has closed before a daughter divides | The bridge's `check_definition` |
| R5's worst case over the schedule | `inner_check_spec` (insertion@2, replacement) |
| Lineage rebuilt from the declaration, the schedule and the final `division_applied` | The partition's summary; replacement's lineage |
| This operator's carry and reset at prescribed events (its 1.1 doors) | §1.5 |
| The continuity probe runs past the next event | D153 case 1 |

### 2.4 Mapping onto milestone 2's open decisions (not settled)

| Milestone 2 decision (CURRENT_PLAN) | What a trigger turns into state, and the question it raises |
| --- | --- |
| **Reference anchors at birth** | With a pre-declared tree, the anchors stay exact fractions of the parent's declared anchors, so no re-anchoring is needed (S5 §6.3). Fractions set by state at the event (growth) would need re-anchoring, a decision against D057, which is the user's |
| **Slot reuse and capacity** | A tree of depth k costs 2^(k+1) − 1 cell slots. A branch that never triggers stays pending. Reuse needs re-anchoring and carrier-keyed lineage (user) |
| **Lineage across storage changes** | Event times become state: a recorded step per declared event. Carrier ids are pre-declared per tree node. Records are rebuilt from state, not from the schedule |
| **Conservation through topology changes** | The partition's bookings are unchanged. Three things move from the definition to run time: per-carrier state (this operator's states, D150's occupant rates) carried by a contract mechanism (owners declare a carry rule; the composite applies it when an event operator moves carriers); living-interval checks, which become liveness at the view; the bridge's start, which follows the birth, with its "closed before a daughter divides" check refused at run time. R5's worst case must cover every division the tree admits |
| **Checkpoints at events** | The latches, counters and records are state (R7), so restart is exact. But D153's probe cannot know the next event in advance, and execution windows do not break at triggered events, since the event map runs inside the step |

### 2.5 Further questions for that door

1. **A refused triggered event.** Today a refused event refuses the step, which returns the start
   state; for a prescribed event that ends the run. A triggered event's condition still holds at the
   next attempt, so it would re-fire and be refused again. The options are to stop the run
   (consistent with "refused, never repaired"), or to record a failed event and suppress it, which
   would be new semantics.
2. **Timing.** A crossing is detected at step ends, so an event time carries an O(dt) error unless the
   crossing is located within the step. Events must occur at step starts, so the references compare
   the event step with the closed-form crossing (A8, §4.5).
3. **Agreement near thresholds.** Between CPU and GPU, or between step sizes, the firing step can move
   by one (ARCHITECTURE, "especially near commitment thresholds"). Agreement is judged on event
   steps with a declared tolerance, not bitwise.
4. **Batches.** Due flags are per world. Under vmap, `lax.cond` becomes a select, so the event map runs
   at every step of a batch, as the partition's does today.
5. **The field refresh.** The v2 note's option (b), refactorising at declared epochs, needs declared
   times. It does not serve triggered events (W3c, §3.2).

## 3. Newborn integration and the composition walls on Track R's path

### 3.1 Today's behaviour, from the code

- **Daughters keep the mother's junctions.** The partition maps each parent contact to two daughter
  contacts, with areas a_e and 1 − a_e. Each daughter contact opens with the parent's gate, copied as
  intensive state, at its own scheduled availability. There is no abundance state and no maturation.
- **A contact between one division's two daughters** is treated as a bridge link (`bridges()`,
  `partition.py`): it opens at birth with its declared gate.
  - With `cytoplasmic_bridge_closure@1` it is a cytoplasmic bridge, P_s A = 2 a D_s with a fixed open
    gate, closed by its aperture.
  - It is not a gap junction, and nothing forms one between sisters gradually.
- **`delayed_first_order_junction_formation@1`** is applied only inside replacement@1 and @2, to
  contacts incident to replaced slots. D139 ruled on replacement only.
- **The refusals are real missing interactions** (S5 §3.8, D150 §5.3, D152 §7.2). Each is an explicit
  refusal in the operator code, and each stays until its door is designed, built and qualified.

### 3.2 The walls

| # | Wall: the refusal in code | What is missing | Lifting it requires | Door or new | Owner |
| --- | --- | --- | --- | --- | --- |
| W1 | D150's turnover and exchange, D152's reactions and this operator refuse closers (the masks in `CONFLICTS_VIEW`) | Reads and writes at the view; no evolution on closed slots; daughters as new carriers; per-carrier state carried at birth | **One liveness rule, designed once, as step 1 of newborn integration** (ruling 8): select by the view's liveness at run time, which serves triggered births too, where definition-time living intervals cannot. D150 §5.2's daughters as new carriers. This operator's states copied or declared at birth. The view in half-steps and factors (contract) | Doors: D150 §5.3 (v1.1), D152 §7.3 ("Closers"), this note's 1.1 | D150's and D152's notes and this note; the contract change is the lead's |
| W1b | The bridge beside inventory species | A material-rate bound for neutral species on junctions | @3's queued D148 round (probe C4), then D150 v1.1's bridge | Door, queued | The lead (D148) |
| W2 | The partition refuses replacement, and the formation law lives inside replacement@1 and @2 | A maturation law any arrival can initialise; one owner of junction abundance | §3.3's contact-maturation process, with replacement preserved through a guarded composition | **New work** | A short design note in the lifecycle line (milestone 2) |
| W2b | The partition beside replacement (renewal and division in one tissue) | Replacement books on the declared layout and does not refuse a slot that is not live | S5 §5.5's three extensions | Door | S5's note |
| W3a | Pumps on a dividing cell | Pump capacity as entity state | The next `membrane_entity_state` version providing the pump views from state; a partition version splitting them by a_k; R5's worst case over the daughters | Door (S5 §3.3, "later work") | S5's line |
| W3b | Water beside the partition | The partition writing water's volume | S5 §5.5's third extension, booking water's endpoint free energy | Door | S5's line |
| W3c | 64 padded field nodes, held baths only, with any field-input provider (every closer is one) | A refresh policy that scales | (a) a raised cap at the measured cost (+20% per step at 254 nodes, +48% at 825, one CPU core; GPU unmeasured); (b) declared epochs, which do not serve triggered events or per-world predicates under vmap; (c) rank-k updates; or the field-solver interface's sparse IDs | A decision, then a door | The v2 note §3 (the lead), with the field-solver interface note |
| W4 | 7 species per world, ions included (`check_species_cap`) | A host-side summation-order check at 8 or more terms | D150's check (D148) | Door | D150's note |

**The count that makes W4 bind (S).** The heredity world has 4 species (Na, K, M, P). Track R's
minimal chain adds 3: an activator, a partner and their complex. That is exactly 7. The regulatory
state takes no species row, which is one reason it is the gate.

### 3.3 The contact-maturation process (new work)

**The general feature.** A contact matures after it arrives, whichever way its cells arrived:
replacement, division, or later growth or migration. It is a new operator, provisionally
`contact_maturation@1`. It is not an edit of replacement@1, which is qualified (G2-Q1).

| Item | Specification |
| --- | --- |
| Law | `delayed_first_order_junction_formation@1` (`processes/junction_formation.py`), reused unchanged: A(age) = 1 − (1 − A₀) exp(−max(0, age − lag)/τ), advanced exactly |
| Contact age | State per contact slot: the lag remaining and the deficit 1 − A, both 0 for a formed contact, plus a recorded arrival step. Age = (count − arrival step) × dt |
| Abundance | A = 1 − deficit, a factor on @3's `junction` availability, exactly 1 for a formed contact |
| Initialisation | Arrival rules declared per arrival kind: a contact mapped from a parent contact; a contact new at a birth (between sisters); a replacement newcomer's contact. Each rule declares A₀, lag and τ. The start state of a division-born contact is the user's decision (§3.5) |
| Gate initialisation | One writer per event. At a division the partition writes the gate (copied, or declared for a sister contact), and maturation sets abundance only. At a replacement arrival the gate follows replacement's declared rule (`law_open` or `law_steady`) |
| Stable identities | A contact's identity is its two carriers and its arrival. A replaced or divided endpoint makes a new contact on the same storage slot. Records (slot, endpoint carriers, arrival time and kind, parent contact) are rebuilt on the host from the schedules for prescribed events, and from recorded steps for triggered ones (§2.4) |
| Retirement | A contact retires when an endpoint retires, closing by propagation. Its maturation state is held, masked at the view, and kept for the lineage record. A slot reused later (milestone 2) restarts at its next arrival |
| Energy | None. Junction abundance carries no free energy in the model, as with replacement's formation |
| Ownership | One owner of junction abundance per contact. Maturation is refused beside replacement@1 and @2 on the same contacts |

**Replacement's behaviour is preserved by a guarded composition.**
- A later replacement version that delegates its formation to this operator must be bitwise equal to
  replacement@1 and @2 on their test and G2-Q1 qualification worlds. That is D143's method for the
  S1 re-expressions.
- If a guard fails, replacement@1 and @2 stay as they are, and maturation serves division only.

**Sources first (D136: "hypotheses stay hypotheses").** D139's sources concern replacement
newcomers: a departing cell's plaques leave whole, and new channels form after a lag. Division-born
contacts differ. Plaques may stay on the dividing membrane, or be internalised during mitosis and
re-formed after cytokinesis. The arrival rules need division-specific sources before the design note
fixes them.

**The membrane side** of the review's §6b item 4(b), newborns' channel abundances maturing, is a
further feature. It would write population abundance through `membrane_entity_state`'s
`ACCEPTS_WRITES`, booked in units. Meanwhile this operator expresses state-driven changes, for
example a junction availability that falls while a state is high and recovers as it decays.

### 3.4 The order: four named steps

Each step carries four checks:
- **conservation:** every ledger closing on the adjusted row across the event;
- **identity:** carrier, contact and species identities, and the records rebuilt;
- **restart:** bitwise before, at and after each event, through a written snapshot;
- **event boundary:** an event on a window boundary, or coinciding with a write or switch, equal to
  the run without the boundary.

**Before the steps.** This operator's version 1 (§1), and W4's check if Track R's network needs more
than 7 species.

| Step | Content | Walls it lifts | Prerequisites |
| --- | --- | --- | --- |
| **1. The reaction inventory and its state across partition** | The one liveness rule, designed once here for D150's, D152's and this operator (ruling 8). D152's network, D150's turnover and exchange, and this operator's states through prescribed 1 → 2 and 1 → 2 → 4 divisions. Species split by f with the partition's bookings, daughters' rates as new carriers, states copied or declared at birth | W1 (W4 if needed) | Version 1; D150's and D152's acceptances |
| **2. Contact formation after birth** | §3.3's process, initialised by the partition's births. The guarded replacement composition, if the lead wants it now | W2 | The user's start-state decision (§3.5) and its sources |
| **3. The effect of newborn integration on an already qualified conduction model** | The slow world (division and maturation) feeds conduction assays (D155's two clocks). An assay can run as a new run from imported state (D153), with no closer, so the 64-node cap binds only the slow world (**S**) | W3c, for sheet-scale slow worlds | Track E's excitable tissue qualified (D155 item 4); steps 1 and 2 |
| **4. Volume-dependent and pump or lifecycle interactions, when a consumer needs them** | Water beside the partition, with this operator's water door; pumps on dividing cells; replacement beside the partition; slot reuse and re-anchoring | W3b, W3a, W2b; milestone 2's anchor and reuse decisions | A consumer's need |

**Where the trigger falls.** §2's routing door and the trigger come after steps 1 and 2, because the
trigger needs the inventory, the states and contact formation working across a partition. They come
before Track R's state-triggered stage. Step 3 can run first with prescribed divisions, since
integration does not need the trigger.

**Pumps (S, a constraint on step 3).** Until W3a lifts, a dividing cell carries no pump. The slow
world's dividing cells must therefore be declared pump-free, a limit each stage that uses them
registers.

### 3.5 A question for the user: the start state of a division-born contact

D139 decided replacement only: "inherit" is excluded there, because the departing cell takes its
plaques. Division is different, and S5 today keeps the mother's junctions (§3.1).

| Option | Mapped daughter contacts | A contact between sisters |
| --- | --- | --- |
| **(A) Inherit**, today's behaviour | The mother's junction, split by area, at full abundance and the mother's gate | Opens as declared: a cytoplasmic bridge, or a fully formed junction |
| **(B) Re-form** | Restart from a declared low abundance, with a lag and τ, as replacement newcomers do (D139's law): plaques internalised at mitosis | Forms de novo after the bridge closes, or from birth if there is no bridge |
| **(C) Retain a fraction** | Start at a declared A₀ ∈ (0, 1], then mature to 1 | As in (B) |

- §3.3's law covers all three: (A) is A₀ = 1 with no lag, (B) a small A₀ with a lag, (C) a declared A₀.
- **The decision is which start states the engine admits.** Each needs division-specific sources
  first (D136).
- The lead's suggestion, for the user to rule on: admit (C) as the general rule, with (A) and (B) as
  its cases, once the sources are read.
- **Held by the lead** until the division sources are read (§6.4).

## 4. Qualification

### 4.1 The first acceptance is numerical (D138)

The references are mathematics: closed forms, quadrature, and independent integrations of the
declared equations of Appendix A. They are not a paper's model. On the lead's reading of MG0c
(D152 question 9), that is within D138.

### 4.2 Ledgers are blind to a wrong factor

@3 books whatever availability it is given, so every ledger closes with a wrong factor. The guards
of record are therefore value checks:
- the factor against an independent evaluation;
- the state against closed forms;
- the response against an independent integration;
- the pass-through against schedules, bitwise.

**A negative control.** A world with a perturbed K passes every ledger and fails A1 and A2.

### 4.3 The references (an independent agent that never reads the operator's code)

- **R-fac:** every factor law, side and basal combination at given concentrations and states. It is
  written in linear space, independently of the log-space kernel.
- **R-state:** the regulatory state's closed forms (A.3): frozen input, retention, and commitment under
  first-order clearance for any n, with activation and inhibition. Quadrature or a one-equation
  adaptive integration covers general inputs and k_off > 0. It also gives the crossing time t* of a
  level θ.
- **R-cell and R-feedback:** R-tissue's constant-field equations (S5 Appendix A;
  `validation/division/cleft_tissue_reference.py`, itself an independent reference), with the
  availability a(t) of A.2 multiplying P A of the gated route.
  - R-cell gates a `kleak_always_open@1` population in one cell, an always-open constant-field law,
    so no channel gate law is needed.
  - R-feedback joins two cells by a contact with a fixed open gate. Its availability is set by each
    cell's state, which senses that cell's intracellular Na. The state equations are integrated
    together with the ions, by Radau at rtol 1e-10, R-tissue's setting.
- **Pump-free worlds.** R-tissue has no pumps, so R-cell's and R-feedback's worlds declare leaks,
  the gated route and a held bath only. Their species are Na, K and Cl with a fixed background, as in
  S5's worlds, and they are compared over transients of seconds to minutes, before the unpumped
  gradients run down.
- **Written afresh, inside the J2 bright line** (S5 §10.1). The new references are written from
  Appendix A. They may import R-full's transport laws (`ghk_flux`), as R-tissue does. They never
  import `simulate_divisions`, a J1 builder of `cleft_egg_reference` or any J1 input, so
  `tests/unit/test_j2_bright_line.py` sees no J1 source in them. The later division-world references
  of §3.4 steps 1 and 2 use R-tissue's division path only on worlds built from neither J1 input.
- **A usage note.** The engine agent runs the references only through it, as in S5 and D152.

### 4.4 The acceptance items

| Item | World | Shows | Criterion |
| --- | --- | --- | --- |
| **M1 (milestone 1, contract fit), first** | Tiny worlds, each of the two targets | The first factored `channel` path through `control_view` and `held_schedules`: step and observation equal the same availability scheduled. With A3 it is the replay check of the electrical leg (ruling 12) | Bitwise. If a shared path needs a fix, D148 applies and the lead decides. The channel target enters the accepted scope only when M1 passes |
| **A1 Factor values** | Host and device evaluations over grids of c, K, n, b and s | Each law and side, the products | Within a few ulps of R-fac |
| **A2 The state** | One cell; regulator cleared first order by turnover; also a production pulse | s(t), U(t), the crossing step | Frozen input: exact to rounding at every dt. Moving input: second order, against R-state |
| **A3 Identity, zero and multiple factors** | One cell and two cells | *Identity* (switched off, or untargeted): no regulation; equal to the world without the operator. *Zero* (b = 0 and s = 0 under `state_fraction`): the target unavailable, carrying no transport and no heat while its gate still evolves; equal to availability 0 scheduled. *Multiple* (two couplings on one element times a schedule below 1): independent mechanisms multiply; equal to the product scheduled | Bitwise against the comparison world, using exactly representable values (s = 0.5, 0.25, a schedule of 0.5) |
| **A4 Reciprocal feedback** | R-feedback's two cells: the junction target, an ion source through a regulatory state (ruling 1) | Inventory → effective control → electrical response → inventory, under dt refinement at four step sizes, plus a fast arm at the largest admitted rates, dt·(k_on + k_off) near 1 (ruling 5) | Against the coupled-ODE reference: expected order 2 (**S**), with the error at the production dt reported against its tolerance and the fast arm's order constant reported |
| **A5 The channel response** (after M1) | R-cell's one cell; a neutral regulator with closed-form kinetics, instantaneous form | The first integrated milestone: inventory → effective control → measurable electrical response (voltage and amounts) | Against R-cell, tolerance from the dt study |
| **A6 Locality** | Two cells with no path between them; two species | *An unrelated cell:* every control and the whole trajectory of a cell the coupling does not target is bitwise unchanged. *An unrelated species:* perturbing a species the coupling does not read leaves every factor bitwise unchanged, and the operator writes no species row | Bitwise |
| **A7 Volume** | Water, a lumen, replacement@2 | A conserved amount with changing volume is refused at the definition in version 1, with the reason named. The water door's own acceptance, concentration following n/V(t) at conserved n, is recorded for 1.1 | Refusal |
| **A8 Restart, windows and observation** | A2's and A4's worlds | Bitwise state across a restart at, before and after writes, switches and crossings; across window boundaries; through a written snapshot. Identical crossing steps. Identical observed factors at identical rows | Bitwise |
| **A9 Idleness, crossrev, signature, refusals** | Existing sets; each refusal | §1.10's claims 1 and 2; the signature refusing different structures; each refusal with its message | As claimed |
| **A10 The first consumer** | §4.5 | Local accuracy at the concentrations it uses | §4.5 |

The tolerances are pinned at registration from the dt studies, as for MG0c.

### 4.5 The first consumer's local accuracy (Track R version 2)

- **The world.** A static tissue with D152's pulse network: an activator from a scheduled source
  reaction, cleared first order at the review's 20–40 min protein half-life, plus a partner and their
  complex by passive binding. A regulatory state integrates a Hill factor of the complex, with
  k_off = 0 or slow, and gates a junction or channel availability.
- **What is compared, at the concentrations the consumer actually uses** (not test-friendly values),
  each above D150 §1.3's resolution floor:
  1. **the complex's concentration over time**, against D152's independent network reference;
  2. **the integrated exposure**: the engine's U against quadrature, and ∫ c dt of the complex from
     saved rows, with its quadrature error bounded by the observation interval;
  3. **the effective control** F(t);
  4. **the response or threshold time**: the crossing step k against the reference's t*, within
     (k − 1)·dt < t* ≤ k·dt, widened by the dt study's error in s near the crossing divided by ds/dt.
- **The paper's data.** Comparing with them is approved under D155 item 2, with predictions
  registered first. They are a comparison for Track R, not this operator's qualification: "do not
  use this paper as the qualification case for any feature" (review §7).

### 4.6 The benchmark question: the yeast cell cycle does not fit

The test is whether a benchmark exercises species → physical control, or node → node logic.
- **The yeast model is node → node.** Taoma et al. 2024, as listed in
  [GRN_WETLAB_VALIDATION.md](GRN_WETLAB_VALIDATION.md):
  - it is a stochastic, weighted-threshold Boolean network of 15 components;
  - its behaviour comes from nodes regulating nodes;
  - its observables are mutant phenotypes of a cycle;
  - this operator has no node reading a node (§5), and its laws are deterministic continuum laws.
- **Its claims are still unverified** in that document. Running it is per-paper tooling (D138), on the
  held GRN track (D145).
- **Where it belongs.** When the gene-regulation layer opens, the yeast model would test that layer,
  with this operator as its output stage.
- **The right first benchmark is mathematical** (§4.3–§4.4).
- **A biological benchmark** must exercise species → physical control: a measured concentration–
  response and its kinetics for a transport target, under a regulator of measured concentration, in
  one preparation. One candidate class is pharmacological gap-junction uncoupling by a neutral
  uncoupler, with its washout. It is to be sourced when a consumer needs it; nothing is claimed here.

## 5. What it does not authorise

- **A transcription network, or the GRN track.** Both stay held (D145). The operator:
  - has no node → node regulation: no state reads a state, its own included, so there is no
    self-activation and no bistable switch inside it;
  - has no production, degradation or expression law; production is D152's;
  - has no Boolean or stochastic nodes.

  In version 1, feedback closes only through physical state (an ion through a target), which is
  physiology.
- **Routes to other operators' controls**, and the trigger (§2): shapes only.
- **Anything for one paper** (D144). No law, species or operator is named after Myc, cyclin T1, CDK9,
  P-TEFb, `Scn5a` or connexin 43. The competence gate is a generic regulatory state, and Track R's
  network is a driver's declaration.
- **Any change** to `network_control_factors@1`, `network_reactions@1` or the calcium-energy family;
  to D150's or D152's design or code, whose doors stay theirs; to @3; or to the composite or adapter.
  The contract changes of §1.12 and §2.1 belong to their doors.
- **Code before this note is accepted** (D142). Integration grants no acceptance.
- **Milestone 2's decisions** (§2.4): re-anchoring and slot reuse are the user's, against D057.
- **Reproducing a paper's model or code** (D138).

## 6. Effort, order and open questions

### 6.1 Effort (version 1)

| Part | Agent-days |
| --- | --- |
| Milestone 1: the contract fit, the first factored channel path, the parser, refusals and binding; the field map's `factors` entry | 1.0 |
| The laws: the neutral Hill helper and its agreement test against D152's expression, the factors, the exact two-state half-step; the event map (switches, writes, crossings, counter) | 1.0 |
| Observation, the summary and the tier-1 smoke (under 20 s) | 0.5 |
| Guards in the branch: idleness, the crossrev set, restart and windows, vmap, refusals, A3 and A6 | 1.0 |
| **Independent references, by a second agent that never reads the operator's code**: R-fac, R-state, R-cell and R-feedback from R-tissue, and the usage note | 1.0–1.5 |
| The numerical protocol and its judged runs (CPU, under an hour) | 0.5–1.0 |
| **Total** | **about 5.5 (4.5 to 7)** |

**The doors (S, rough):**
- the routing door and the trigger, milestone 2's first slice: 6–10 days, with their design note;
- step 1, closers for three operators plus carry: 3–4;
- step 2, maturation, sources and the guarded replacement composition: 4–6;
- W4's check: about 1;
- step 3 depends on Track E, and step 4 is 2–5 per item.

### 6.2 Order of work

1. **This note's review**, the lead with the advisor: accepted on 14 November 2026 (§6.3).
2. **Version 1's code.** Milestone 1 first: the factored channel path and, with A3, the replay check
   of the electrical leg (ruling 12). Then the operator and its guards. Nothing blocks the code:
   D150 v1's and D152 v1's code is on main.
3. **The independent references.** Their agent starts once milestone 1 has fixed the declaration
   (ruling 11).
4. **The judged numerical qualification**, after the code (ruling 11). Its references use
   turnover's closed forms, so D150 v1's acceptance comes first.
5. **The first consumer**, Track R version 2 (§4.5), after D152's acceptance (MG0c).
6. **Then §3.4's four steps**, with §2's doors placed as stated there.

### 6.3 Questions for the lead, and the rulings

The lead, with the advisor, ruled on every question on 14 November 2026. Each ruling is recorded
against its question, and the in-text changes are marked with the ruling's number.

1. **Ion sources in version 1**, the largest step beyond "a species sets availability". They enter
   through the kinetic form only, by a read-only species list: D152's unopened door "reads of
   charged or permeant species" (its §7.3). The consequence of refusing them: version 1 has no
   admissible reciprocal-feedback world, because nothing electrical moves a neutral, impermeant
   source.
   - *Ruled:* **yes, through the regulatory state only.** Instantaneous factors of moving rows stay
     refused.
   - §1.5's claim that the state is "the only second-order route" is corrected. A D152 species pair
     with read-only ion reads would also be Strang second order, since its half-steps read the ion
     before and after @3's step. The reasons that hold (§1.5): there is no named molecular carrier,
     so no moiety and no free energy; the species cap, since a pair costs two rows; and binding
     kinetics on a target.
   - The read-only read of a charged source is one mechanism, designed here, which D152's v1.1 door
     reuses rather than building a second (§1.3).
   - A4's reference, R-feedback built from R-tissue with a(t) on P·A, stays within §6.1's 1.0–1.5
     days.
2. **One operator, or two?** As here, one operator holds states and couplings. The alternative is a
   state owner and a factor provider, with a cross-operator state read added to the contract now.
   - *Ruled:* **one operator in version 1.** The split into a state owner and a factor provider
     comes with the trigger door (§2.2).
3. **The basal level b** (the four-parameter Hill form, Goutelle et al. 2008) in version 1?
   - *Ruled:* **yes.**
4. **The junction side "both"** in version 1, as our modelling choice (S)?
   - *Ruled:* **"both" (S), plus "first" and "second"** (§1.3).
5. **A run-time loop bound for feedback** (§1.4), or A4's measured regime as the declared limit?
   - *Ruled:* **no unenforced limit.** u is a product of Hill factors in [0, 1], so
     λ ≤ k_on + k_off. The definition refuses dt·(k_on + k_off) > 1, as D152 refuses dt·L > 1. A4's
     fast arm lies inside the admitted range and reports the order constant there (§1.4).
6. **A `factors` entry** in the manifest's field map, recording the chain of factors?
   - *Ruled:* **yes** (§1.7).
7. **The Hill evaluation:** a neutral helper that D152 adopts later under crossrev, or repeated with a
   bitwise-agreement test against D152's kernel?
   - *Ruled:* D152's evaluation is inline (`species_reactions.py`, around line 947:
     `-logaddexp(0, ∓z)`), not a function, so it cannot be called unchanged. **A neutral helper** is
     written for this operator, with a bitwise-agreement test against D152's expression. D152 stays
     untouched during MG0c and adopts the helper at its next version, under crossrev (§1.9).
8. **One liveness rule** for D150, D152 and this operator beside closers, designed once, at run time
   rather than from definition-time living intervals (W1)?
   - *Ruled:* **one liveness rule, designed once, as step 1 of newborn integration** (§3.2, §3.4).
9. **The crossing record and step counter** in version 1, for A8 and A10's threshold time, or deferred
   to the trigger door?
   - *Ruled:* **yes, in version 1.**
10. **Version 1.1's replacement rule** (D150's occupant tables; reset and inheritance at replacement):
    next after version 1, or when the coupled-renewal gate asks?
    - *Ruled:* **when the coupled-renewal gate asks** (D144).
11. **The judged qualification's timing:** after D150's acceptance, or partly now with frozen and
    constant regulators?
    - *Ruled:* **after the code.** The references agent starts once the code's milestone 1 has fixed
      the declaration (§6.2).
12. **Probe P1** (the channel path) before this note's acceptance, or as milestone 1. The door probes
    P2 (outside-node sources through a state) and P3 (an instantaneous factor of a moving row) wait
    for their consumers.
    - *Ruled:* **the accepted scope is the junction target; the channel target is pending
      milestone 1.** M1's bitwise comparison, the factored path against the same availability
      scheduled, is with A3 the replay check of the electrical leg, and it stays first (§4.4).

### 6.4 Questions for the user

**Held by the lead (14 November 2026).** None blocks version 1, and they stay here. Question 3 (§3.5)
waits until the division sources are read.

1. **The benchmark.** The yeast cell-cycle model tests a network, not this coupling (§4.6). Do you
   accept a numerical first acceptance now, with a biological benchmark of species → physical
   control sourced when a consumer needs one?
2. **Routing to other operators' controls** (state-dependent secretion; regulated production) closes
   species → control → production loops (§2.1). Is that within the narrowed hold when its door
   comes, or does it wait for the gene-regulation decision?
3. **The start state of a division-born contact** (§3.5): which of inherit, re-form and a retained
   fraction should the engine admit, once the sources are read?
4. **Milestone 2's anchor and slot decisions** (§2.4): a pre-declared division tree first, which needs
   no re-anchoring, with re-anchoring and slot reuse decided later?
5. **The output stage.** When the gene-regulation layer opens, should its output reach physics only
   through this operator, keeping one route from molecular state to controls?
6. **Energy pools.** Should a regulatory state's maintenance cost be drawn from finite energy pools
   later, as D150's question 11 and D152's question 10 ask for their laws?

## Appendix A. Equations for the independent references

**A.1 Notation.**
- Cell i has declared volume V_i (pL). A species row s has amount n_si = reference + increment
  (fmol), and c_si = n_si / V_i (mM).
- Contact e joins cells a(e) and b(e). Channel population k sits on patch m(k) of cell i(k).
- The step is dt and the half-step h = dt/2. Time t is in seconds.

**A.2 Factors.**
- z = n (ln x − ln K).
- Activation: f = 1/(1 + e^(−z)) = x^n/(K^n + x^n). Inhibition: f = 1/(1 + e^z) = K^n/(K^n + x^n).
- State fraction: f = s. Complement: f = 1 − s.
- The coupling's factor is F = b + (1 − b) f, with 0 ≤ b < 1. A switched-off coupling has F = 1.
- A contact with side "both": F_e = F(source at a(e)) · F(source at b(e)).
- An element's product is G = Π over its routes of F_r, in declared order, and 1 with none.
- The effective availability is a_eff(t) = a_sched(t) · G(t), times the other operators' factors.
  Version 1's worlds have none that are non-trivial.

**A.3 The two-state law.**
- ds/dt = k_on u(t) (1 − s) − k_off s, with u = Π_j f_j(c_j(t)) and s(0) = s₀.
- **Quasi-steady value (S):** s* = k_on u / (k_on u + k_off). For one activation input,
  s* = [k_on/(k_on + k_off)] · c^n/(c^n + K_eff^n), with K_eff^n = K^n k_off/(k_on + k_off). This is
  the Hill form that the instantaneous factor is the fast limit of.
- **Exact over h with u frozen:** λ = k_on u + k_off, s(h) = s + (k_on u (1 − s) − k_off s) h φ(λh),
  with φ(x) = (1 − e^(−x))/x and φ(0) = 1.
- **Retention** (u = 0): s(t) = s₀ e^(−k_off t).
- **Commitment** (k_off = 0): s(t) = 1 − (1 − s₀) e^(−k_on U(t)), with U(t) = ∫₀ᵗ u dτ.
- **U under first-order clearance**, c(t) = c₀ e^(−kt), with one input (**S**, derived here; the
  reference agent derives it again):
  - activation: U(t) = (1/(n k)) ln[(K^n + c₀^n)/(K^n + c(t)^n)], so
    s(t) = 1 − (1 − s₀) [(K^n + c(t)^n)/(K^n + c₀^n)]^(k_on/(n k)), tending to
    1 − (1 − s₀) [K^n/(K^n + c₀^n)]^(k_on/(n k));
  - inhibition: U(t) = t − (the activation expression).
- **General input and k_off > 0:** s(t) = e^(−Λ(t)) [s₀ + ∫₀ᵗ k_on u(τ) e^(Λ(τ)) dτ], with
  Λ(t) = ∫₀ᵗ (k_on u + k_off) dτ.
- **The regulator under D150's turnover** (production P, clearance k): n(t) = n₀ e^(−kt) +
  (P/k)(1 − e^(−kt)), piecewise in its schedule.
- **The crossing:** k* is the smallest step index with s(k* dt) ≥ θ. The reference's t* solves
  s(t*) = θ.

**A.4 What the engine computes per step**, needed only to read the dt study.
1. The event map: the counter, the switches, due writes, crossings recorded from the state at the
   step start.
2. The first half-steps, in declared order.
3. The effective availability from the state after every first half, held through every stage of
   @3's step.
4. The second half-steps, in reverse order.

Version 1's instantaneous sources are unchanged by @3's step, so their F is exactly constant over
the step. A state's two halves read its inputs before and after @3's step. The references do not
reproduce this sequence; the dt study measures its order against them.

**A.5 The bioelectric references.**
- **Electrostatics and transport** are S5 Appendix A.2 (the capacitor graph and the held bath) and
  A.3: the constant-field flux J_{k,s} = P_{k,s} A_k ψ(x) (c_{s,i} − c_{s,o} e^{−x}), with
  x = z_s F V_k/(R T) and ψ(x) = x/(1 − e^{−x}). The worlds are pump-free.
- **A channel population on patch k** (R-cell) adds one more route for each permeant species s, the
  same constant-field flux with P_{k,s} A_k replaced by P r_s N o a(t) A_k:
  - P is the population's declared permeability and r_s its relative permeability for s (1 for K
    under `kleak_always_open@1`);
  - N is its declared abundance, and o its opening, which is 1 for a gate-free law;
  - a(t) is the effective availability of A.2.
- **A contact e between cells a and b** (R-feedback) carries J_{e,s} = P_{e,s} A_e g a(t) ψ(x)
  (c_{s,a} − c_{s,b} e^{−x}), with x = z_s F (φ_a − φ_b)/(R T) and its gate fixed open (g = 1).
  Here a(t) is the product of the two cells' factors (side "both").
- **The regulator in R-cell** is a neutral, impermeant species: it enters neither the electrostatics
  nor the transport, so a(t) = F(c(t)) comes from its closed form (A.3, D150's turnover), one way.
- **In R-feedback**, a(t) depends on the two cells' states, which sense each cell's c_Na. Their
  equations (A.3) are integrated together with the ions, so the system is coupled.

**A.6 What is compared:**
- s(t), U(t) and F_r(t) at saved rows;
- the gated cells' voltages and amounts;
- crossing steps;
- the order in dt.

## References

Every reference beyond D152's list was checked against its Crossref record, with no project details
sent. The other entries are D152's, checked there.
- Goldbeter A, Koshland DE Jr. An amplified sensitivity arising from covalent modification in
  biological systems. *Proc Natl Acad Sci USA* 1981;78(11):6840–6844. doi:10.1073/pnas.78.11.6840
- Goutelle S, Maurin M, Rougier F, Barbaut X, Bourguignon L, Ducher M, Maire P. The Hill equation: a
  review of its capabilities in pharmacological modelling. *Fundam Clin Pharmacol*
  2008;22(6):633–648. doi:10.1111/j.1472-8206.2008.00633.x
- Hill AV. The possible effects of the aggregation of the molecules of haemoglobin on its
  dissociation curves. *J Physiol* 1910;40(Suppl):iv–vii.
- Hodgkin AL, Huxley AF. A quantitative description of membrane current and its application to
  conduction and excitation in nerve. *J Physiol* 1952;117(4):500–544.
  doi:10.1113/jphysiol.1952.sp004764
- Hundsdorfer W, Verwer JG. *Numerical Solution of Time-Dependent Advection-Diffusion-Reaction
  Equations*. Springer; 2003. Chapter IV (splitting).
- Keener J, Sneyd J. *Mathematical Physiology I: Cellular Physiology*, 2nd ed. Springer; 2009.
  Chapter 1.
- Strang G. On the construction and comparison of difference schemes. *SIAM J Numer Anal*
  1968;5(3):506–517. doi:10.1137/0705041
- Weiss JN. The Hill equation revisited: uses and misuses. *FASEB J* 1997;11(11):835–841.
  doi:10.1096/fasebj.11.11.9285481
