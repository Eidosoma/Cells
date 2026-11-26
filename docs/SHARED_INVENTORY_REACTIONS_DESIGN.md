# Reactions on the shared inventory (design)

> **Legacy cleanup (25 November 2026, D386).** Paths under `src/cells/legacy/` and the older model
> IDs named below left the engine. The tag `pre-cleanup-2026-11-25` keeps them.

**Status: numerically qualified within MG0c's scope, 15 November 2026.**
- **The design** was accepted on 14 November 2026 (the lead, with the advisor; rulings in §9).
- **Milestones 1 and 2** (§11 to §11.2) and milestone 3, MG0c's driver and protocol (§11.3 to
  §11.5), are landed.
- **The judged run passed.** It ran the registered protocol `mg0c-turing-v1` at registration commit
  5ab4326 (§11.6). The run met:
  - 55 of 55 judged criteria, every kept control caught;
  - all 10 guard files;
  - the combined verdict;
  - and every value identical to the rehearsal's.
- **Tags:** `mg0c-v1-registered-2026-11-15` and `mg0c-v1-qualified-2026-11-15`.

**The scope of the qualification** is the protocol's scope line:
- **What runs judged:** `local_species_reactions@1`'s driven mass action, of orders 0, 1 and 3, at
  outside nodes. It runs with `resolved_pump_tissue@3`'s species transport on faces in
  `resolved_pump_composite@1`, five species per world.
- **One judged guard world** uses `ideal_detailed_balance_mass_action@1`: guard 2's passive
  world.
- **Guarded by tests only, not qualified:**
  - the passive law's other uses;
  - Michaelis–Menten and Hill factors;
  - cell routes and D150's writers;
  - the mixed-node heat and work split.
- **No biological claim:** the parameters are synthetic.

**History of this note:**
- The lead's rulings on §9's questions are recorded against each question.
- The advisor's first review corrected the stage condition for passive routes (§4.2).
- The lead's review made the mixed-node onset a blocking item. Probe 2d measured it, and the
  advisor's final review found a second failure mode at equilibrium crossings (probes 2e and 2f).
  The mixed-node heat is now a per-route hybrid: the average-vector-field share for a route that
  does not reverse within the step, the stage quadrature for one that does (§3.3).
- Probe 2g measured the hybrid's one known limit, the reversal onset.
- The lead's round-2 rulings:
  - the hybrid is adopted, with that limit recorded under the resolved-start rule (option (a));
  - the intra-node split is rejected;
  - a D148 round for @3 is queued after D150 v1 (§3.3, §9).
- Probe C3 set version 1's dt · L rule (§4.3).
- Probe C4 measured finding 3 on the engine (§4.2, §10.3). It does not gate acceptance. The
  existing-worlds sweep for the D148 round found no world that declares a neutral permeant species
  (§10.3).
- No engine code was added or changed.

D152 asks for this feature. The user's words were: "Yes on the question and lets go as you see fit
otherwise". The question was whether reactions acting on the same molecules that transport moves
should be designed as a general engine feature. The decision reads:
- **What it means.** Driven, open, nonlinear reactions that write @3's species rows become a
  general composite operator. These rows are the one inventory that membranes, faces and D150's
  operators move. The operator is the engine's route to Turing-type self-organisation.
- **Consumers named so far:** MG0c, Turing patterning at the predicted wavelength, which is its
  qualification case; the GZMK review's catalysis on a substrate (item 2); E15's
  self-organisation layer.
- **Design first (D142).** The note is written against D150 v1's accepted design. It settles the
  GZMK review's shared-state question. It must give one owner per species row, conserved material
  and charge, energy booked in the composite's ledgers, bitwise idleness at zero rate (D136) and
  cited kinetics.
- **What it does not authorise:** code before the note is accepted; any change to
  `network_reactions@1` or the calcium-energy family; lifting D145's holds; a law or species
  named for one experiment (D144); reproducing a paper's model (D138).

**Engine models it runs (AGENTS.md milestone rule):**
- `resolved_pump_composite@1` over `resolved_pump_tissue@3`;
- one new operator, `local_species_reactions@1` (§2);
- its passive law is `ideal_detailed_balance_mass_action@1`, the law `compartment_reactions@1`
  qualified. It runs through that law's shared kernel `laws/reactions/mass_action.reversible_flux`,
  called unchanged;
- it composes with D150 v1's `scheduled_species_turnover@1` and `scheduled_species_exchange@1` and
  with @3's transport.

No model, solver or shared function changes. Its one adapter need is D150's adapter addition, the
per-node and per-species chemical term, which D150 v1 builds.

**Basis.**
- The [secreted-species design](SECRETED_SPECIES_TRANSPORT_DESIGN.md) (D150 v1, accepted).
- The [v2 design](PUMP_COMPOSITE_V2_DESIGN.md) §1–§4: the contract, energy roles, and injection's
  split part that writes @3's amounts.
- The [closed-chemistry note](COMPARTMENT_REACTIONS.md) for the passive law.
- The [S5 design](CELL_DIVISION_S5_DESIGN.md) for closers.
- The [GZMK review](PAPER_REVIEW_GZMK_AGEING.md) §3 item 2, [E15](EXPERIMENT_PATH_PATTERN_RECOVERY.md)
  §1.3 and the [morphogenesis plan's](MORPHOGENESIS_PLAN.md) MG0c row.

**Evidence and log:** `/mnt/workspaces/Cells/shared-inventory-reactions-20261114-01/`:
- HANDOFF.md;
- the clean snapshot `snapshot-ac5a251`;
- probes 1, 2, 2b, 2c, 2d, 2e, 2f, 2g, C3, C3b, C4, C4b and C4c of §10;
- the citation records in `sources/`.

**S** marks our arithmetic or interpretation, as in the division and secreted-species designs.

## 0. Summary

1. **The operator.** `local_species_reactions@1` is one reaction network per composition, run as a
   split part (Strang halves) around @3's step.
   - Every reaction is local: it acts within one node, a cell or a finite outside node, on @3's
     neutral species rows.
   - @3 owns every row. The operator is a writer that books in its own accumulators, as D150's
     operators do (§1).
   - Version 1 never acts on held baths, membranes or ions.
2. **The shared-state question: `network_reactions@1` stays separate.** It is neither migrated nor
   wrapped (§1.2).
   - **What it is.** Its kinetics are a library over its own [species, compartment] concentration
     arrays, and no engine model integrates them. The engine uses only its Hill-regulation part,
     over views of physical amounts.
   - **Why not wrap it.** Its kernels carry a reference simulator's conventions and no energy
     accounting.
   - **What the operator uses instead.** It takes its forms from textbooks and reuses only the
     neutral detailed-balance kernel. Nothing in `network_reactions@1` or the calcium-energy family
     changes.
3. **Cited laws only** (§2.2).
   - **Passive (spontaneous):** reversible mass action, detailed-balanced by species standard
     potentials.
   - **Driven:** irreversible mass action (orders 0 to 3), and Michaelis–Menten with an optional
     catalyst species, which is GZMK item 2's catalytic law.
   - **Factors:** Hill activation and inhibition, on driven laws.
   - **Nothing named for one experiment.** MG0c's network is Schnakenberg's, declared in a driver as
     four mass-action reactions.
4. **Material and charge** (§3.1, §3.2).
   - Every reaction either conserves its declared moieties exactly or is a declared source or sink.
   - Changes are booked per species and node, and extents per route.
   - Version 1 acts on neutral species only, so every charge term it touches is an exact zero.
5. **Energy** (§3.3, §3.4). Per node and half-step, the operator books the exact free-energy change
   ΔG of the rows it wrote, so W − H = ΔG closes exactly.
   - **The bookings,** by the node's class in the step, which the step's multipliers set:
     - at a node with driven routes only, W = ΔG;
     - with passive routes only, H = −ΔG, which the dissipation check requires to be
       non-negative;
     - with both, H = Σ_passive H_r and W = ΔG + H.

     So a node whose driven routes are all switched off books no work.
   - **Each passive route's heat at a mixed node is a per-route hybrid.**
     - **A route that does not reverse within the step** books its average-vector-field share,
       −Δξ_r Σ_s ν_sr μ̄_s (McLachlan, Quispel & Robidoux 1999), with μ̄_s each species'
       divided-difference potential over the half-step.
     - **A route that reverses** books the stage quadrature of RT·A·J, which is non-negative.
   - **Why a hybrid.** Each rule alone fails somewhere, unseen or loudly:
     - **The quadrature alone** (the first draft) overbooks a passive switch-on from a 1e-12 mM
       trace by 34–54% in the first step, and by 1–6% of the whole heat after 5 s. W carries the
       same error, and the closure stays exact (probe 2d).
     - **The share alone** goes negative where a driven route carries the state across the passive
       equilibrium within a step, a refusal mode above about 4e-3 fmol at h L = 0.05 (probe 2e).
     - **The hybrid** is 0.06–0.33% at the onset, with the true heat's trace dependence, and
       non-negative at every probed crossing (probe 2f).
     - **One measured known limit remains, the reversal onset** (probe 2g; option (a), ruled).
       - **Where it applies.** At any half-step in which a driven route carries a trace species
         across a passive route's equilibrium. That includes a scheduled switch-on mid-run, since
         the half-step depends only on state and multipliers.
       - **Its size.** That half-step books 5.4–5.6 times its true heat at a 1e-12 mM trace (+436% to
         +459%), 3.4–3.7 times at 1e-9 and 1.6–1.8 times at 1e-6, trace-dependently. In probe 2g's
         one world the whole heat at 1 s was off by 0.27–0.56%.
       - **How it is recorded.** Under the resolved-start rule (§3.3).
     - **Rejected:** a symmetric split of passive and driven routes within the node (§3.3).
   - **A finding: @3's chemical term has no standard potentials.** The operator therefore owns the
     standard-potential term and adds it to the energy ledger as a declared free-energy term, not a
     flow. Without it, a passive conversion with K ≠ 1 books negative heat (probe 2, B7).
   - **The guards of record** check the residual at rounding in a face-free species-only world,
     where the operator is the only energy flow, not against the shared bound, which is blind at
     µM–nM (D150's lesson). A NumPy ΔG test per law and negative controls complete them. They are
     written by an agent that never reads the operator's code (§3.4).
6. **Numerics** (§4).
   - **The half-step:** SSPRK(3,3) with a run-time stage condition h·L ≤ ½ on unidirectional
     fluxes, which makes positivity a theorem. A failure is refused, never repaired.
   - **Version 1 refuses dt · L > 1 at run time.** C3 measured second order up to dt · L of about 2
     in all three of its worlds, and order reduction beyond it. So version 1 takes one sub-step, and
     the stage condition at θ = ½ is the rule.
   - **Order:** Strang splitting against transport is second order. The prototype's ratios are
     3.98 to 4.07 (probe 2).
   - **Idle:** bitwise idle at zero rate.
   - **Solvers:** IMEX only. RK4 and the stationary analysis are refused, with reasons (§4.6).
7. **Qualification** (§6). The first acceptance is numerical (D138). It runs against two textbook
   references: the closed-form linear reaction–diffusion solution, and the linear stability
   analysis of a two-species activator–inhibitor system. MG0c checks, on zero-flux chains:
   - every mode's propagation against the discrete dispersion relation;
   - that only k = nπ/L appear: a domain with no admissible unstable mode stays homogeneous;
   - patterning at the predicted wavelength, and the mode staircase;
   - the subcritical control;
   - the nonlinear pattern against an independent integration.
8. **Pre-code probes** (§10).
   - **Probe 1, the engine as it is:** the MG0c transport world runs, its species-set step is
     admitted and second order, and the ions are bitwise unchanged.
   - **Probes 2 to 2g, C3 and C3b, a NumPy prototype:** they confirm the numerics, the bookings and
     the dispersion design. The prototype is development evidence, not a reference of record.
     - Probe 2c tests the stage condition as corrected in review.
     - 2d measures the mixed-node onset.
     - C3 measures stiffness relative to the split step.
   - **Probe C4, the engine as it is:** finding 3, neutral species on junctions and membranes. It
     is a separate track.
   - **Still to come:** the contract fit (C1) is now the code branch's first milestone (§10.4).
9. **Limits** (§7). Version 1 is a static tissue with neutral species, at most 1,024 species
   (D150's cap: 16 until FR-43 / D315, 7 until FR-9 / D165), and kinetics with dt · L ≤ 1.
   - It is refused beside the lumens, replacement@2, closers, RK4 and the stationary analysis.
     Beside water it reads the current volumes (FR-43 / D315, §7.3's volume door, delivered).
   - Cell routes on slots that replacement@1 replaces are refused.
10. **Effort:** about 6 agent-days (range 5 to 7), plus about an hour of CPU for MG0c's judged runs
    (§8).

**Two departures from the brief and from D150,** both ruled on by the lead with the advisor on
14 November 2026:
1. **The brief says the operator composes with D150's turnover.** It does, except on the rows the
   network writes. A turnover route on a reacting (species, node) is refused, so that each node's
   local kinetics have one writer. The production and clearance of a reacting species are declared
   as source and sink reactions instead (§1.1). **Confirmed for version 1, with a door later**
   (§9 question 3).
2. **RK4 is refused, where D150 guards it.** **Confirmed,** with the framing corrected (§4.6;
   §9 question 5).

## 1. Entities and ownership

### 1.1 One inventory, one owner per row

**Decision.** The operator writes @3's species rows in place: `amount_increment` [species, cell]
and `extracellular_amount_increment` [species, outside].
- **Ownership.** @3 owns every row. Turnover, exchange, replacement events and this operator are
  writers. Each books its writes in its own accumulators through `ENTITY_WRITES`, and @3's ledgers
  close with the sum over writers (v2 §1.3, "fluxes add").
- **No second copy.** There is no second inventory, so the split that `network_reactions@1`'s arrays
  imply (§1.2) does not arise.
- **What comes free,** as D150 §1.1's table shows: transport, held baths, ledgers, osmolytes,
  replacement swaps and the partition already treat every species row alike.

**The writers' rules are D150's** (§1.1 there):
- book in own accumulators, never in @3's route accumulators;
- do not use the membrane-process hook. It admits one process per composition and requires
  heat ≥ 0, and driven laws book work;
- every half-step returns, as its validity, the finiteness and positivity of every amount it wrote.
  The composite re-runs @3's domain at the step end only when an operator's view follows its split.

**One network per composition.**
- The composite refuses an operator law that appears twice (`structure_errors`). So every reaction
  on the inventory is declared in the one operator, and its integrator sees each node's local
  kinetics whole.
- Splitting one network's reactions between operators would split the very coupling that makes a
  Turing instability, at an unmeasured O(dt²).

**One local-kinetics writer per (species, node)** (confirmed for version 1 by the lead with the
advisor, with a door later; §9 question 3):
- **The refusal.** A turnover route on a (species, node) that a reaction writes (net coefficient
  ν ≠ 0 there) is refused at the definition. The production and clearance of a reacting species are
  declared in the network as source and sink reactions instead, where the integrator sees them with
  the rest.
- **How it is checked.** The operator reads turnover's declaration, as `restricted_cleft_lumen@1`
  reads insertion's.
- **What it does not cover:**
  - exchange routes (secretion, uptake), which are transport across a patch and compose freely;
  - catalysts and Hill factors, which are read, not written, so they do not count as writes.
- **Probe 2b's B9** shows the network reproducing turnover's closed form for the same linear
  kinetics, at third order (§10.2).

### 1.2 The shared-state question: `network_reactions@1` stays separate

**What `network_reactions@1` is, at ac5a251** (code read; HANDOFF finding 1):
- **A law library.** `legacy/processes/network_reactions.py` offers:
  - `rates` over [..., species, compartment] concentrations (mM) and volumes (m³);
  - `accounting` of extents;
  - `bind` from the reference's dictionaries;
  - cell, mitochondrial, environment and growth branches.

  Its docstring reads: "No heat, ATP, transport or clipping is owned."
- **No engine model integrates its kinetics.**
  - Its one engine consumer is `network_control_factors@1` (`legacy/processes/network_control.py`). That
    module binds its influencer parsing and Hill regulation.
  - `resolved_calcium_energy_regulated@1/@2` apply those factors to existing pumps, channels and
    junctions. Their regulator concentrations "are read views of the existing ion/store/fuel
    amounts".
  - The rate and accounting kernels run only in its correspondence tests
    (`tests/unit/test_network_reactions.py`, `validation/chemistry/betse_network_reactions_*`).
- **What "its own species state" means.** The phrase "its own species state beside the physical
  inventory" (GZMK review item 2; E15 §1.3) describes the convention of its arrays. Any model that
  integrated those kernels would hold a second copy beside @3's rows.
- **It carries its reference's conventions.** Its equations are those of the BETSE v1.5.0 network
  (cited; no BETSE code), with that network's own conventions:
  - the literal Q conversion outside each power (a factor 1e-3 per term);
  - a reversible cell branch that drops both saturation coefficients;
  - growth "time dilation" and native optimisation auxiliaries;
  - the direct-inhibitor parse order.

  Each reversible reaction declares its own standard free energy, so cycle consistency (Wegscheider)
  is not enforced across reactions.

**The options:**

| Option | What it would mean | Verdict |
| --- | --- | --- |
| Migrate | Move its state onto @3's rows and its kinetics into the composite | Refused. D152 authorises no change to it or to the calcium-energy family |
| Wrap | A composite operator calling its `rates` and `accounting` on views of @3's rows | Rejected, below |
| Separate | It stays as it is, serving the calcium-energy family's regulation and its own tests; the new operator is written from textbook forms | **Chosen** |

**Why not wrap.** Each reason below is sufficient on its own.
1. **Conventions.** A wrapper would carry a reference simulator's numerical conventions into the
   composite's physics. AGENTS.md admits neutral implementations of physical laws and keeps such
   conventions out of new engine code. §2 writes the neutral laws.
2. **Energy.** It owns no heat or work, and its reversible branches are not tied to species
   potentials. So a spontaneous step cannot be shown to dissipate, and a reaction cycle need not
   close. D152 requires energy booked in the composite's ledgers.
3. **Positivity and stiffness.** Its kernels are "unchecked literal rates", and nothing bounds a
   step. Its reversible cell branch has no saturation, so the rate is proportional to 1 − Q/K. Its
   reverse rate therefore grows without bound as a reactant's concentration falls, and the products
   are consumed ever faster. §4's positivity rests on rates whose consumption per amount stays
   bounded, and on a stage condition that refuses a step otherwise.
4. **Units and axes.** Concentrations [species, compartment], volumes in m³ and a zone taxonomy
   (cell, mitochondrion, environment, growth) differ from @3's amounts on cell and outside slots. A
   wrapper would be a conversion layer around every call.
5. **Scope of acceptance.** Its qualification is correspondence with captured reference outputs. A
   wrapper would inherit no acceptance that applies to the composite's conservation and energy.

**What is reused.** `laws/reactions/mass_action.reversible_flux`, which is neutral and cited (Rao &
Esposito 2016). It is the kernel of `compartment_reactions@1`'s law. It is called unchanged, and no
program that calls it today changes, so crossrev stays identical and D148 does not arise.

**What else stays separate:**
- `compartment_reactions@1`, a standalone closed-chemistry model with its own state; its
  qualification stands;
- `reaction_transport@1`, MG0a's standalone model.

**Not authorised, and recorded for later** (§9 question 11, answered on 25 November 2026):
- retiring `network_reactions@1`'s kinetic branches;
- letting the calcium-energy family's regulation read species rows of a shared inventory.

Either would be the user's decision. Nothing here depends on it.

### 1.3 Nodes and routes

- **A route** is one declared reaction at one node. Nodes are:
  - cells (the cytosol);
  - finite outside nodes.
- **A held bath is refused.** Its composition is held, so a reaction there would be a source or sink
  of the bath, not of the inventory.
- **Routes are static,** and the batch signature carries them. Parameters and controls are
  per-world data (§2.3).
- **Concentrations** are c = n/V at the declared volume. Version 1 refuses volume providers (§5).

### 1.4 The ownership table

| Field | Owner | Writers (booked in) |
| --- | --- | --- |
| A species' cell amounts (`amount_increment` rows) | @3 | @3's step (routes with nonzero coefficients); turnover; exchange; replacement events; **this operator** (`reaction_produced_fmol`, `reaction_consumed_fmol`) |
| A species' outside amounts (`extracellular_amount_increment` rows) | @3 | @3's faces; turnover; exchange; **this operator** (`reaction_outside_produced_fmol`, `reaction_outside_consumed_fmol`) |
| Extents, heat, work, the standard-potential term, magnitudes | This operator | Itself only |
| Species identity (catalogue reference) | Declarations, never arrays (§1.5) | – |

**The contract's parts, as used:**
- `ENTITY_WRITES` on the two amount fields, each with its owned accumulators.
- **Energy roles** (v2 §1.1):
  - `HEAT_FIELDS`: `reaction_dissipated_energy_pJ`, `reaction_outside_dissipated_energy_pJ`;
  - `WORK_FIELDS`: `reaction_work_pJ`, `reaction_outside_work_pJ`;
  - the standard-potential term is a free-energy term (§3.3), not a flow.
- `CONFLICTS_VIEW`: `volume`, `extracellular_volume`, `active`, `outside_active` and
  `extracellular_amount_reference`, all read as declared. The masks are listed under the S5 rule
  that a closer counts as a mask's provider. Insertion@1 provides `outside_active` and the outside
  anchors, so it is refused too.
- **Parts:** one split part, with RK4 mode "split" and RK4 refused at the definition (§4.6).
  - Statically idle with no routes.
  - With every multiplier zero, a half-step selects its start state (§4.5).
- None of `VIEW_FIELDS`, `CONTROL_FACTORS`, `REPLACES`, `ACCEPTS_WRITES`, `EVENT_REPLACES`: it owns
  nothing another operator writes.
- **Observation:** its own state columns and two readouts (§2.5).

### 1.5 Identity

This is D150 §1.5's form.
- **Where the reference lives.** Each species the network names carries an optional opaque
  catalogue reference on the declaration, with its evidence kind. It never enters an array.
- **Conflicts.** A reference that differs from another operator's declaration of the same species is
  refused. S2's guard applies: changing a reference changes no binding, jaxpr or trajectory.
- **Generic laws stay generic** (catalogue rule). No law is labelled with a protein. The catalytic
  law names no protease, and labelling it with one would be a new scientific claim.

## 2. The operator and its laws

### 2.1 Declaration

```json
{"law": "local_species_reactions@1",
 "standard_concentration_mM": 1.0,
 "species": [{"id": "U", "moieties": {"M": 1}, "standard_mu_RT": 0.0,
              "catalogue": null, "evidence": null}],
 "reactions": [
   {"id": "u_autocatalysis",
    "sites": {"outside": ["node_0", "node_1"]},
    "reactants": {"U": 2, "V": 1}, "products": {"U": 3},
    "law": "mass_action", "rate_constant": 1e5,
    "factors": []}]}
```

(Amended at milestone 1, §11: the identity keys are D150's `catalogue` and `evidence`; every key is
explicit; Michaelis–Menten declares `catalytic_rate_per_s` with a catalyst and `max_rate_mM_per_s`
without one; a passive law declares `forward_rate_per_s`.)

**What each part declares:**
- **Species:** neutral species already declared in @3 (§3.2), with:
  - integer moiety counts (default: the species is its own moiety);
  - a standard potential μ°/RT at the declared standard concentration c0 (default 0, D150's 1 mM
    convention);
  - the D150 catalogue reference.
- **Sites:** cells, finite outside nodes, or `"all"` of either kind.
- **Reactants and products:** integer coefficients, with an empty side for a source or a sink
  (§3.1).
- **Law and parameters** (§2.2), and **factors** (driven laws only).
- **No sub-step count in version 1.** Version 1 refuses dt · L > 1 (§4.3, from C3). At one
  sub-step the stage condition at θ = 1/2 is that rule, so a declared count would add nothing.
  Sub-steps are a door, opened with a splitting that holds its order where C3 measured order
  reduction.

**The schedule, `reaction_controls`:**
- per reaction, and optionally per site, a piecewise-constant multiplier m_r(t) ≥ 0;
- changes on the clock's grid (D283), refused otherwise;
- a zero multiplier switches a reaction off (D136 idleness; E15's "switching off at the damage");
- on a passive reaction the multiplier scales both directions, as `compartment_reactions@1`'s does.
  It changes the kinetic barrier, adds no material and leaves the equilibrium unchanged.

**Whose rates** (the lead's ruling with the advisor, 14 November 2026; §9 question 6).
- **Outside routes** belong to their node, which is environment. They compose with
  replacement@1.
- **Cell routes on replaced slots are refused in version 1.** A cell route on a slot that
  `scheduled_cell_replacement@1` replaces is refused at the definition.
  - **Why.** No version 1 consumer needs it, and D150's occupant mechanism is still being coded.
  - **The door.** Version 1.1 applies D150 §5.2's rule, that carriers have identity and slots are
    storage, through D150's mechanism once it lands. A newcomer would then take its template's or
    donor's rates at the event step.
- **Law parameters** are per reaction, shared by its sites, and per world.

### 2.2 The rate laws

**Notation.** At node i, with declared volume V_i (pL):
- c_s = n_s/V_i (mM);
- J_r is the route's rate (fmol/s);
- α_sr are the reactant coefficients and β_sr the product coefficients, so ν_sr = β_sr − α_sr;
- F_r is the product of the route's factors;
- m_r is the scheduled multiplier.

| Law | Role | Rate J_r (fmol/s) | Parameters | Sources |
| --- | --- | --- | --- | --- |
| `mass_action` | driven | m_r F_r k V ∏_s c_s^{α_s} | k in mM^{1−q} s⁻¹, with q = Σ_s α_s ≤ 3 and integer α_s | Mass action (Guldberg and Waage); Keener & Sneyd 2009, ch. 1 |
| `michaelis_menten` | driven | m_r F_r V k_cat c_E c_S/(K_M + c_S), with catalyst E; or m_r F_r V V_max c_S/(K_M + c_S) | k_cat (s⁻¹) or V_max (mM s⁻¹); K_M (mM); one substrate S with α_S = 1; E is read, not written | Michaelis & Menten 1913; Briggs & Haldane 1925; validity: Segel & Slemrod 1989 |
| `ideal_detailed_balance_mass_action@1` (passive) | passive | m_r V c0 k_f [∏ a^{α} − exp(Σ_s ν_s μ°_s/RT) ∏ a^{β}], with a = c/c0 | k_f (s⁻¹, at c0); species μ°/RT; c0 | Rao & Esposito 2016; [closed-chemistry note](COMPARTMENT_REACTIONS.md) |
| factor `hill_activation` | multiplies a driven law | x^n/(K^n + x^n) | K (mM), n > 0; the species x is read | Hill 1910; Weiss 1997; Keener & Sneyd 2009, ch. 1 |
| factor `hill_inhibition` | multiplies a driven law | K^n/(K^n + x^n) | as above | as above |

**Rules on the laws.**
- **Factors.** Factors multiply (v2 §1.3, "factors multiply"). They are evaluated in log space
  (logaddexp), so they stay finite at the trace and at large x. A factor's species is read; it is
  written only if it is also a reactant or product of that reaction.
- **Rates vanish as consumed species vanish** (the premise of §4.2's positivity):
  - mass action consumes only its reactants, each at order α ≥ 1;
  - Michaelis–Menten consumes only S, at order 1 near zero;
  - a passive route has two unidirectional fluxes. Its forward flux J⁺ = m V c0 k_f ∏ a^{α}
    consumes its reactants, and its reverse flux J⁻ = m V c0 k_f exp(Σ_s ν_s μ°_s/RT) ∏ a^{β}
    consumes its products. Each vanishes with every species it consumes. Its net rate, J⁺ − J⁻, can
    have either sign, so a positivity argument must use the two fluxes, not the net rate (§4.2);
  - a zeroth-order consumption is refused. That is a sink whose rate does not vanish with the
    species, such as a constant-flux removal.
- **Passive reactions are closed and take no factors** in version 1.
  - An open passive reaction would need the chemical potential of its external partner, a
    chemostat. In @3 the only chemostat is a held bath (§7.3).
  - A species-dependent common factor would keep detailed balance, but no consumer needs one.
  - A catalyst of a reversible reaction is written in its stoichiometry (E on both sides), which
    mass action handles exactly: E's net coefficient is 0 and it cancels from ΔG°.
- **Molecularity at most 3.** Higher orders are not elementary steps, and cooperativity enters
  through Hill factors.

**Not in version 1:**
- reversible Michaelis–Menten (the Haldane relation);
- multi-substrate enzyme mechanisms and substrate inhibition;
- delays;
- surface-bound catalysis, which is D150 §2.5's occupancy door.

An explicit enzyme–substrate complex needs no new law: it is written as elementary steps, passive
binding E + S ⇌ C followed by a driven catalytic step C → E + P.

### 2.3 Per-world data and the batch signature

- **Parameters as bindings.** Law parameters (k, k_cat, V_max, K_M, K, n, k_f, μ°/RT, c0) are layout
  arrays bound per world, so vmap batches may differ in them. Controls are per-world data. Neither
  is ever a closed-over constant, and the crossrev records show it (D148, "what crossrev compares").
- **The static structure enters the batch signature:** species, routes, stoichiometry, law and
  factor kinds and their species, and roles.

### 2.4 Generality (D144) and parameter sources

- **No law is named for a molecule, a pathway or an experiment:** no Wnt, BMP, Nodal, granzyme or
  Turing law. "Activator" and "inhibitor" are roles of declared species in a driver, not engine
  concepts.
- **MG0c's network** is Schnakenberg's (1979), written in a validation driver as four mass-action
  declarations (§6.4).
- **GZMK item 2's catalytic law** is `michaelis_menten` with a catalyst:
  - E converts S to P, two distinct species rows with distinct catalogue references;
  - E is not consumed and keeps its own material account in @3's row, where D150's operators secrete
    and clear it.

  The review found no kinetic constant in its papers. A calibration needs a published kinetic
  dataset (§6.6).
- **E15's self-organisation layer** is any network of these laws.
- **Parameters come with sources.**
  - Every parameter in a registered world carries its source. It is either a cited measurement with
    its method, or a declared synthetic value in a stated non-dimensional regime, labelled synthetic,
    as `compartment_reactions@1`'s example is.
  - The engine holds no default kinetic value.

### 2.5 State, ledger terms, observations and refusals

**State** (zero at the start; per world):

| Field | Axes | Role |
| --- | --- | --- |
| `reaction_extent_fmol` | [route] | Signed cumulative extent. Diagnostic; non-negative on driven routes |
| `reaction_produced_fmol`, `reaction_consumed_fmol` | [species, cell] | The positive and negative parts of each half-step's net change, per species and node. Material accumulators, ≥ 0 |
| `reaction_outside_produced_fmol`, `reaction_outside_consumed_fmol` | [species, outside] | The same at outside nodes |
| `reaction_dissipated_energy_pJ`, `reaction_outside_dissipated_energy_pJ` | [cell], [outside] | Heat: ≥ 0 and non-decreasing |
| `reaction_work_pJ`, `reaction_outside_work_pJ` | [cell], [outside] | Work, signed |
| `reaction_standard_energy_pJ`, `reaction_outside_standard_energy_pJ` | [cell], [outside] | The owned standard-potential term, signed (§3.3) |
| `reaction_energy_magnitude_pJ`, `reaction_outside_energy_magnitude_pJ` | [cell], [outside] | Rounding magnitudes |

**Ledger terms:**
- @3's local ledger gains consumed − produced at cells, and its outside ledger the same at outside
  nodes. The total gains the sum over nodes.
- The energy ledger gains standard term + heat − work.
- The magnitudes gain the moved amounts and the |ΔG| terms.

**Observations:**
- the state columns;
- `reaction_rate_fmol_per_s` [route], at each row's state and held controls;
- `reaction_affinity_RT` [route], on passive routes, 0 on driven ones.

**Refusals at the definition:**
- a charged species;
- a species with nonzero membrane or junction permeability (§4.2, finding 3);
- a held-bath site;
- an unbalanced reaction that is neither a source nor a sink;
- a passive reaction that is open or carries factors;
- molecularity above 3, and non-integer or negative coefficients;
- a consumed species absent from its law's rate;
- non-positive K_M, K, n, k_f or c0, and negative rate constants;
- schedule changes off the dt grid;
- the `CONFLICTS_VIEW` providers and closers (§5);
- more than 1,024 species, D150's cap (16 until FR-43 / D315, 7 until FR-9 / D165), refused with
  the cap named (D150 §2.6, §13, §14);
- a turnover route on a (species, node) the network writes (§1.1);
- a cell route on a slot that `scheduled_cell_replacement@1` replaces (§2.1);
- RK4 (§4.6);
- a catalogue reference that differs from another operator's.

**At run time:** the stage condition at one sub-step (h L ≤ 1/2, that is dt · L ≤ 1), positivity
and finiteness (§4.2, §4.3), returned as the half-step's validity.

## 3. Accounting

### 3.1 Material, with sources and sinks declared

- **Extent-consistent updates.** Per route, the extent increment over the half-step (one sub-step
  in version 1, h_sub = h) is Δξ_r = h_sub Σ_k b_k J_r(Y_k) (§4.2). The net change Δn_s = Σ_r ν_sr Δξ_r is computed once per node
  and added both to @3's row and to the produced and consumed accumulators, as its positive and
  negative parts.
- **@3's ledgers then close to rounding,** and at the species' own scale. D150 §1.3 gives each such
  species a species-scale `material_balance_atol_fmol`, plus 2.5 ε × steps × the row's magnitudes.
- **Closed reactions conserve declared moieties exactly.** Each species declares integer moiety
  counts M_qs. A reaction is closed when its net change conserves every moiety, Σ_s M_qs ν_sr = 0,
  which is checked in integer arithmetic at the definition. A catalyst on both sides cancels in ν.
- **Sources and sinks are declared by sign.**
  - A reaction whose net change is not moiety-balanced must be a pure source (every ν_sr ≥ 0) or a
    pure sink (every ν_sr ≤ 0). Any other unbalanced reaction is refused.
  - The external partner of a source or sink (a precursor supply, a degradation pathway) lies
    outside the modelled inventory. Its produced or consumed amounts are booked as D150's turnover
    books its own (§2.2 there).
  - So material can enter or leave the inventory only through a declared source or sink. A typo in a
    stoichiometry is a refusal, not a silent creation of material.
- **The moiety identity is a guard, not a ledger** (§3.4). The inventory's moiety totals change only
  through sources and sinks: Σ_s M_qs Δn_s = Σ_{open r} (M ν_r)_q Δξ_r. This holds by construction
  (integer ν, Δn = ν Δξ), and @3's per-species ledgers carry the run-time check.

### 3.2 Charge

- **Neutral species only in version 1** (valence 0), refused otherwise. Every charge, drift and
  conductance term the operator touches is an exact zero (D150 §3).
  - The field never sees the operator.
  - The operator provides no field input, so the 64-node cap does not apply to it.
- **Probe 1:** in the species-only world, the ion rows are bitwise unchanged by two declared neutral
  species (§10.1).
- **Later** (§7.3): closed reactions on charged species with Σ_s z_s ν_sr = 0 exactly (integer
  valences), such as buffering. A charged source or sink would need a counter-ion rule, as
  injection's carriers do, and stays refused.

### 3.3 Energy: work for driven steps, heat for spontaneous ones

**The inventory's free energy at a node**, at the declared volume and against @3's 1 mM reference:

    G_i = RT Σ_s n_s (ln(n_s/V_i) − 1) + Σ_s μ°'_s n_s,   μ°'_s = RT (μ°_s/RT − ln(c0 / 1 mM)).

The first term is @3's chemical term on the touched rows (D150's adapter addition). The second term
is new.

**A finding: @3's chemical term has no standard potentials** (HANDOFF finding 2).
- **What @3 books.** `surface_tissue.balances` and the adapter's `chemical_free_energy_pJ` book
  RT Σ n (ln(n/V) − 1) only.
- **Exact for transport and baths.** A species keeps its identity there, so its standard potential
  cancels.
- **Not for reactions.** A reaction converts species, so ΔG°_r ξ_r is real free energy that the
  chemical term cannot see.
- **Probe 2, B7.** A passive A ⇌ B with K = 10, relaxing from equal concentrations in one node, books
  heat −ΔG ≥ 0 at every step with the standard term (at least 5.4e-5 pJ per step). Without it the
  heat is negative from the first step (−1.3e-6 pJ) and reaches −2.4e-5 pJ. The dissipation check
  would refuse that, or a booking without the check would be wrong.
- **So the operator owns the standard-potential term.** It adds Σ_r ΔG°'_r Δξ_r per node to
  `reaction_standard_energy_pJ`, and that field to the energy ledger, as a declared free-energy owner
  (v2 §1.1). Replacement@2 adds water's free-energy term the same way.
- **Only reactions move it.** Transport and baths never change it, since the standard potentials
  cancel there.

**The booking rule: the exact ΔG; at mixed nodes, a per-route hybrid of the average-vector-field
share and the stage quadrature.**
- **The exact change.** ΔG_i is the exact change of G_i over the operator's half-step at node i. It
  is computed in the stable increment form, anchored at the half-step's start, so a protein-scale
  change is never a difference of large sums.
- **The node's class is selected per step from its controls,** by the step's multipliers, not by
  the declared routes. It uses `where`, with no branching.
  - **A node acts as driven** in a step when at least one driven route there has a nonzero
    multiplier, and as passive when at least one passive route does.
  - **So a node whose driven routes are all switched off books no work in that step.** This is what
    E15's "switching off at the damage" does: the node is then passive-only, and its heat is −ΔG.
- **Single-class nodes (in the step):**
  - driven only: W = ΔG and H = 0;
  - passive only: H = −ΔG and W = 0, and the composite's dissipation check requires H to be ≥ 0.
- **Mixed nodes (in the step).** H_i = Σ_passive H_r, with each passive route's heat H_r chosen as
  below, and W_i = ΔG_i + H_i. So W − H = ΔG holds exactly whatever H is. Probe 2d's largest
  |W − H − ΔG| was 2e-18 pJ.
  - **A route that does not reverse within the step books its average-vector-field share**
    (McLachlan, Quispel & Robidoux 1999). "Does not reverse" means that its three stage fluxes and
    its end-state affinity share one sign.
    - **The potential.** Per species, μ̄_s = [g_s(n'_s) − g_s(n_s)]/(n'_s − n_s), with
      g_s(n) = RT n (ln(n/V_i) − 1) + μ°'_s n. It is evaluated in the stable form
      μ̄_s = RT [ln(n_s/V_i) + (1 + x) log1p(x)/x − 1] + μ°'_s, with x = Δn_s/n_s and the series
      1 + x/2 − x²/6 for the ratio near x = 0.
    - **The share.** H_r = −Δξ_r Σ_s ν_sr μ̄_s.
    - **Why it is exact in total.** G is separable, so Σ_s μ̄_s Δn_s = ΔG exactly, and the routes'
      shares Δξ_r Σ_s ν_sr μ̄_s sum to ΔG.
    - **Along a single route's path, exact.** That path is the straight segment along ν_r, where the
      average-vector-field gradient is the exact line integral.
  - **A route that reverses within the step books its stage quadrature**
    H_r = h Σ_k b_k RT J_r(Y_k) A_r(Y_k), which is non-negative by construction.
- **Why each branch goes where it does.**
  - **A route switching on from a trace, driven by its own affinity, never reverses.** There the
    share is accurate and the quadrature is not (probe 2d below).
  - **A route that reverses is usually near its equilibrium,** with a moderate affinity. There the
    quadrature is safe and the share is not, because the share books only the net extent, which the
    reversal cancels (probe 2e below).
  - **The exception: a reversal onset** (probe 2g; a known limit, below). A driven source can lift a
    trace species across a passive equilibrium within one half-step. The route then reverses, goes
    to the quadrature, and the quadrature samples the log-singular start.
- **The selection costs nothing at run time.** Both selections are by `where`, with no branching,
  and the network's coupling is integrated whole:
  - the node's class, per step from the multipliers;
  - the branch, per route and step by sign tests.

  A node whose driven routes are all switched off is passive-only in that step. It books H = −ΔG and
  no work, whatever branch a passive route would take.
- **How accurate it is.**
  - In the non-reversing branch it is second order in smooth runs. In probe 2d's smooth mixed world
    the hybrid took no step on the quadrature (probe 2g), so its ratios, 3.70 and 3.87, are the
    share's.
  - At a reversing step the quadrature is positive but per-step inaccurate, more so as h L grows
    (below). Such steps are isolated crossings.

**Why not the stage quadrature at mixed nodes** (the first draft's rule; the lead's blocking item;
probe 2d).
- **The first draft.** It booked mixed-node heat as the stage quadrature h Σ_k b_k RT A_r J_r(Y_k),
  with W = ΔG + H.
- **What goes wrong.** A is log-singular at a trace, so a passive route switching on from a trace is
  misbooked. W carries the same absolute error, and the closure stays exact, so no guard sees it.
- **Probe 2d, the enzyme recipe.** Passive E + S ⇌ C (k_on 1e3 mM⁻¹ s⁻¹, K_d 1e-3 mM) and driven
  C → E + P (k_cat 1 s⁻¹) at one 1 pL node, with E at 1e-4 mM and S at 1e-3 mM, and C and P starting
  at a trace. The reference is an independent dissipation integral (SciPy DOP853, rtol 1e-13; it
  agrees with rtol 1e-11 to 2e-11).

  | Trace | Half-step | First-step H, quadrature | First-step H, attribution | Whole H at 5 s, quadrature | At 5 s, attribution |
  | --- | --- | --- | --- | --- | --- |
  | 1e-12 mM | 0.05, 0.025, 0.0125 s | +54%, +42%, +34% | +0.33%, +0.14%, +0.06% | +6.1%, +2.9%, +1.3% | +0.063%, +0.018%, +0.005% |
  | 1e-9 mM | same | +24%, +17%, +12% | +0.33%, +0.14%, +0.06% | +2.7%, +1.2%, +0.49% | +0.063%, +0.018%, +0.005% |
  | 1e-6 mM | same | +0.8%, +0.2%, +0.04% | +0.21%, +0.07%, +0.02% | +0.09%, +0.015%, +0.002% | +0.045%, +0.012%, +0.003% |

  - **Why the quadrature's first-step error does not vanish with h.** The log-singular stage
    dominates whatever the step.
  - **W.** It carries the same absolute error. At 5 s it is −3.4%, −1.6% and −0.75% (quadrature) and
    −0.035%, −0.010% and −0.003% (attribution) at a 1e-12 trace.
- **Trace sensitivity** (half-step 0.025 s, at 5 s; the true heat converges as the trace goes to
  zero; relative changes of the whole heat, not pJ, amended at milestone 1, §11):

  | Change of trace | True H | Quadrature H | Attribution H |
  | --- | --- | --- | --- |
  | 1e-12 → 1e-9 mM | −6.27e-5 | −1.66e-2 | −6.32e-5 |
  | 1e-9 → 1e-6 mM | −2.21e-2 | −3.31e-2 | −2.21e-2 |

  The attribution's heat moves with the trace as the true heat does. The second row is physics: a
  1e-6 mM complex is not negligible against the 3e-5 mM it reaches. So §6.5's background guard can
  hold H and W to the true heat's own dependence (§3.4).
- **For driven-only nodes nothing changes.** The state-function difference was already exact at any
  switch-on (probe 2's B5: a stage quadrature of ΔG_r J would be 27% off at a 1e-12 trace).
- **So the operator's own bookings carry D150's onset limit only in the reversal onset** (below).
  @3's face heat keeps it too, so production worlds should still start resolved where species
  diffuse (§3.4).
- **The hybrid at the onset is the share.** In probe 2f the binding never reversed at the onset, so
  no step went to the quadrature. Its numbers are the share's above, and its trace dependence is
  −6.32e-5 against the true −6.27e-5.

**Why not the share alone: the crossing** (the advisor's review; probes 2e and 2f).
- **The world.** Passive A ⇌ B (K = 1, k_p = 1 s⁻¹) with a driven sink A → ∅ (k_d = 1 or
  10 s⁻¹), at one 1 pL node. The start is a hair off the passive equilibrium, swept finely through
  the point where the sink carries the state across it within one half-step.
- **The share fails there.** It goes negative, and it misses nearly all of the step's dissipation:
  the reversing flux cancels the net extent while the true heat, ∫ RT A J dt, is positive.

  | k_d (s⁻¹) | h L | Most negative share, per fmol | True step heat there, at 1 fmol | Hybrid there (the quadrature), against the true heat |
  | --- | --- | --- | --- | --- |
  | 1 | 0.05 | −2.5e-10 pJ | 3.4e-6 pJ | +7.9% |
  | 1 | 0.1 | −7.2e-9 pJ | 2.7e-5 pJ | +17% |
  | 1 | 0.2 | −1.8e-7 pJ | 2.1e-4 pJ | +37% |
  | 1 | 0.5 | −3.2e-6 pJ | 3.3e-3 pJ | +127% |
  | 10 | 0.05 | −3.8e-11 pJ | 2.0e-6 pJ | +5.7% |
  | 10 | 0.5 | −5.4e-7 pJ | 2.0e-3 pJ | +94% |

  - **It would be a refusal mode.** The most negative share scales with the amount, and roughly as
    (h L)⁵ at small h L. Against the dissipation check's −1e-12 pJ it would refuse steps above about
    4e-3 fmol at h L = 0.05 (k_d = 1), and at far smaller amounts at coarser steps.
  - **The hybrid does not fail.** It booked no negative heat anywhere in the sweep (2f, at 1 fmol).
    These kinetics are linear, so every booking scales with the amount and the sign does not depend
    on it. The reversing steps go to the quadrature, which is positive but overbooks that one step,
    by 6–8% at h L = 0.05 and up to about 2× at 0.5.

**A known limit: the reversal onset** (the advisor's last review; probe 2g; option (a), ruled by
the lead with the advisor, 14 November 2026).
- **Where it applies.** At any half-step in which a driven route carries a trace species across a
  passive route's equilibrium within that half-step. The route then reverses and goes to the
  quadrature, which samples the log-singular start.
  - This is not only the run's first step. The half-step depends only on the state and the
    multipliers, so a driven route switched on mid-run from a trace reproduces it exactly: the
    half-step is bitwise at the same state, multipliers and step. Two compiled runs around a
    mid-run switch-on agree to rounding (8.5e-21 pJ), not bitwise, because the runner's clock
    forms the step as a difference of grid times (3 dt − 2 dt is 0.02500000000000001 s at
    dt = 0.025 s). That is the runner, not the operator (amended at milestone 2, §11.2).
  - E15's switch-off at the damage, followed by a switch back on, is that case.
- **Its size is a per-step factor.** The half-step books 5.4–5.6 times its true heat at a
  1e-12 mM trace (+436% to +459%), 3.4–3.7 times at 1e-9 (+243% to +267%) and 1.6–1.8 times at
  1e-6 (+59% to +80%). W carries the same absolute error, and the closure stays exact. What that does to a run's whole heat depends on the world. The table's cumulative column
  is one world's.
- **The world measured.** Passive R + L ⇌ C (k_on 1e3 mM⁻¹ s⁻¹, K_d 1e-3 mM) at one 1 pL node, with
  R at 1e-3 mM, C pre-loaded at 1e-4 mM and L at a trace. A driven source 0 → L at 1e-2 mM/s carries
  L across its equilibrium (1e-4 mM) in about 0.01 s.

  | Trace | Half-step | Route reverses in step 1? | First-step H, hybrid | Whole H at 1 s, hybrid (this world) | Share alone, first step |
  | --- | --- | --- | --- | --- | --- |
  | 1e-12 mM | 0.025, 0.0125 s | yes, yes | +459%, +436% | +0.56%, +0.27% | −104% (negative), −53% |
  | 1e-9 mM | same | yes, yes | +267%, +243% | +0.30%, +0.14% | −104% (negative), −53% |
  | 1e-6 mM | same | yes, yes | +80%, +59% | +0.034%, +0.012% | −103% (negative), −53% |
  | 1e-12 mM | 0.00625 s | no (the crossing falls in step 2) | −14% (the share) | −0.016% | – |

  - **The trace dependence.** At h = 0.0125 s, a 10³ change of the trace (1e-12 to 1e-9) moves the
    hybrid's whole heat by −1.3e-3 of itself (a relative change, not pJ; §11), against −1.4e-7
    for the true heat. W carries the same absolute error, and the closure stays exact.
- **How it is recorded:** option (a), a known limit under the resolved-start rule.
  - Guard worlds and production worlds keep every passive route's species resolved at every step
    where a driven route could carry it across that route's equilibrium. That covers the start and
    every scheduled switch-on.
  - §3.4's world 1 runs the case as a documented check of the limit's size, at the first step and
    at a mid-run switch-on, not as a pass/fail item.
  - The background guard does not cover H and W in this configuration.
- **The options not taken** (§9 question 2):
  - (b) replacing the first stage's affinity in the reversing branch by its average-vector-field
    mean over the first stage interval, which is unmeasured;
  - (c) a run-time refusal of a reversing passive route whose step starts with a species below a
    declared floor.

**Rejected** (the lead, with the advisor): a symmetric split of passive and driven routes within the
node. It would make every booking an exact state-function difference, but it would split a mixed
network's kinetics at O(h²). The kinetics outweigh the heat and work attribution, which cannot affect
closure.

**Why heat ≥ 0 holds:**
- **At mixed nodes:**
  - **The reversing branch** is non-negative by construction: the quadrature of RT A J, with
    sign(J) = sign(A) at every stage.
  - **The non-reversing branch, unimolecular passive routes** (A ⇌ B), is non-negative by
    construction (**S**). The affinity's sign is the sign of K c_A − c_B, which is linear along the
    straight segment. It is positive at both ends, by the branch's own end-state test, so it is
    positive throughout. The share is then its average times Δξ, and both have one sign.
  - **The non-reversing branch, higher molecularity** (E + S ⇌ C) is not guaranteed: the sign
    function is then quadratic along the segment, and it could dip between positive ends. It is
    measured and checked:
    - none negative in probe 2d's onset runs (smallest 6.3e-7 pJ);
    - none in its near-equilibrium runs, with k_cat 1e-3, 0.1 and 1 s⁻¹ (hybrid smallest 6.7e-16,
      7.5e-12 and 2.3e-9 pJ). The binding started near its equilibrium, about 5% off, since the
      start was an approximate formula;
    - none in its smooth mixed world (probe 2g: no step went to the quadrature there).

    The dissipation check refuses a step whose heat falls, loudly.
- **The trade, three ways:**
  - the quadrature alone keeps its sign by construction, but misbooks onsets by 34–54% unseen;
  - the share alone is accurate at onsets, but refuses at crossings;
  - the hybrid is accurate at onsets and non-negative at crossings, overbooking the isolated
    crossing step.

  The hybrid is recommended (§9 question 2).
- **At passive-only nodes,** −ΔG ≥ 0 holds for the exact flow, because G is a Lyapunov function of a
  closed detailed-balanced network. For the integrator it is proved in one case and measured in the
  others:
  - **For a linear A ⇌ B (S).** The corrected stage condition bounds h (k_f + k_r) ≤ 1, since
    max L ≥ (k_f + k_r)/2. There SSPRK(3,3)'s amplification R(z), with z = −h (k_f + k_r), lies in
    [1/3, 1). So the deviation from equilibrium shrinks without changing sign, and G falls.
  - **Measured.** In probe 2's B4 (h k about 0.014), the smallest half-step heat at any node was
    −1.1e-18 pJ. That is rounding in energies of about 1e-3 pJ, against the dissipation check's
    −1e-12 pJ tolerance. In probe 2c, at every step the corrected condition admits, the heat was
    positive: at least 1.1e-11 pJ near equilibrium, up to h (k_f + k_r) = 0.55.
  - **Not proved for general passive networks.** It rests on these measurements and on the
    dissipation check, which refuses a step whose heat falls, loudly.

**What the work means.**
- **What W is.** Driven routes exchange free energy with an undeclared reservoir: synthesis
  machinery, a degradation pathway or a fuel. W is the change in the inventory's free energy that
  they cause.
- **What W leaves out.** Their own dissipation lies outside the inventory, a declared limit (D150
  §2.4). Later they may draw on finite energy pools (§7.3).
- **At mixed nodes,** H and W carry the same absolute error from the hybrid, since their difference
  is exact. That error is second order in smooth runs (probe 2d), and positive at the isolated
  crossing steps (probe 2f).

**What exactness means, and what it does not.**
- **The ledger closes.** The operator's part of the composite's energy ledger closes exactly in each
  half-step: Δ(chemical term on its rows) + Δ(standard term) + H − W = 0 to rounding.
- **It does not test kinetics.** That closure checks the bookings' consistency, not the kinetics. A
  wrong rate would be booked exactly too. The kinetics are checked against the references (§6).

**The rest of the energy roles.**
- No charge moves and the electrode fields are untouched; there is no `BOOKS_AT_VIEW`.
- H is a heat field and W a work field. The standard term and the magnitudes are not flows, so they
  do not enlarge the shared bound.

### 3.4 The guards of record, and what each must show

**The shared bound is not one** (D150 §7, §11.1).
- Under IMEX it is 2e-8 pJ + 2e-3 × the accumulated flows (ARS(2,2,2)). In a mixed world those flows
  are the ions'.
- D150's probe 2 measured it at 1.7 to 1,721 times a species' whole free-energy change, from µM to
  nM.
- The operator's docstring carries D150's statement, adapted.

**Why the residual itself is checked.** The operator's bookings are exact, so a correct
implementation leaves no residual of its own. An implementation error would leave one that the
shared bound cannot see. The guards therefore check the residual itself, not the bound.

1. **The face-free species-only world: the guard of record for energy.**
   - **The world:** quiescent ions, no faces, and the network at isolated cells and outside nodes,
     with µM-scale amounts in pL nodes (energies of about 1e-2 pJ, D150 §7).
   - **The test.** The operator is the world's only energy flow, so the composite's energy residual
     must be at rounding at every row: |residual| ≤ 2.5 ε × steps × the energy magnitudes
     (`LEDGER_STEP_ROUNDING`). It is not judged against 2e-3 × the flows.
   - **The cases it must cover.** Each booking path is forced by a world built to take it.
     - **Single-class nodes:** driven-only, and passive-only.
     - **A driven switch-on from the trace** (B5's case): the exact ΔG as work.
     - **The share** (the non-reversing branch): a passive switch-on from the trace at a mixed node.
       This is probe 2d's enzyme recipe at traces of 1e-12, 1e-9 and 1e-6 mM, where no route
       reverses. Its H and W go against an independent dissipation integral, first step and
       cumulative, within tolerances pinned from probe 2f's hybrid errors.
     - **The quadrature** (the reversing branch): a passive route carried across its equilibrium by a
       driven route at a mixed node, probe 2e's crossing sweep. Every step's heat must be
       non-negative. The crossing step's heat must lie within a tolerance pinned from probe 2f's
       quadrature errors there, which are positive and grow with h L.
     - **The per-step class switch.** A driven route at a mixed node is switched off by its
       multiplier mid-run and later back on.
       - While it is off, the node must book W = 0 and H = −ΔG, even in a state where a passive
         route would take the quadrature branch.
       - At the switch-back the node books as mixed again, and the rows on both sides close at
         rounding.
     - **The reversal onset, at the first step and at a mid-run switch-on** (probe 2g's recipe; the
       known limit of §3.3). It is run as a documented check of the limit's size against probe 2g's
       per-step factors, not as a pass/fail item.
       - At the first step: L starts at a trace and the source is on.
       - At the mid-run switch-on: the source is off until L has been held at a trace, then switched
         on.

       The guard and production worlds themselves stay resolved at every switch-on.
     - **A closed passive relaxation,** with total heat = G(start) − G(equilibrium).
     - **On every row,** the heat is non-negative and non-decreasing.
2. **The species-only transport world.** This is probe 1's closed chain with the network, the MG0c
   world.
   - It must pass every host check at the species' scale, with residual/bound reported.
   - Its residual is then @3's face-heat booking, which is second order in dt. Probe 1, without
     reactions, measured 1.2e-5, 3.1e-6 and 7.6e-7 relative at dt 0.2, 0.1 and 0.05 s.
   - It starts from a resolved profile, D150's guard-world rule, since its faces book the onset.
3. **Negative controls**, three misbookings:
   - work scaled by 1 + 1e-6;
   - a dropped standard term;
   - a heat booked with the wrong sign.

   **What they must show:**
   - each fails world 1 at the first row it touches;
   - in a mixed heredity world, the shared bound does not see the scaled work. It catches a
     dropped standard term at µM, where it is 0.35 times the booking, and is blind to it at nM,
     where it is 409 times (C2, measured at milestone 2; amended in place, §11.2). The face-free
     world at rounding and the per-law ΔG test remain the guards of record. The bound/booking
     ratio goes into the docstring statement, as D150's probe 2 part C did (§10.4, C2);
   - a wrong-sign heat is still caught there by the composite's dissipation check. Only the bound
     is blind to it.
4. **A NumPy ΔG test per law,** written from Appendix A, not from engine code. For each law, order,
   factor and node kind, it takes random positive states, volumes and parameters and one half-step.
   It must show:
   - booked W − H equals the independently computed ΔG_i, standard term included, to 1e-12 of the
     summed |terms|;
   - **the hybrid's branches.** A passive route whose three stage fluxes and end-state affinity
     share a sign books −Δξ_r Σ_s ν_sr μ̄_s, computed independently; any other passive route books
     its stage quadrature. The test includes states built to sit on each side of the selection, and
     at it;
   - H = −ΔG at passive-only nodes, and H ≥ 0 at every mixed node, on random states and on probe
     2e's crossing states;
   - **the switched-off case:** at a node whose driven routes all have zero multipliers in the
     step, W = 0 and H = −ΔG, even where a passive route would take the quadrature branch. A node
     whose passive routes are all off books H = 0 and W = ΔG;
   - Δn = ν Δξ, and moiety totals change only through sources and sinks;
   - the standard term equals Σ ΔG°'_r Δξ_r;
   - zero multipliers select the start state bitwise;
   - a closed passive network relaxes to the equilibrium its potentials set. In probe 2's B4,
     c_B/c_A came out at 9.99999999999996 against K = 10;
   - at mixed nodes in the non-reversing branch, H converges to an independent dissipation integral
     at second order in h. In probe 2d's smooth mixed world the hybrid took no quadrature step
     (probe 2g), so its ratios, 3.70 and 3.87, are the share's;
   - world 1's share, quadrature, class-switch and reversal-onset cases, each at the half-step level,
     with the expected branch asserted for each state.
5. **The background guard** (§6.5) covers H and W too.
   - A 10³ change of a negligible trace (1e-12 to 1e-9 mM) must move them by no more than the true
     heat's own change plus a tolerance pinned from probe 2f. The true change there was −6.27e-5
     of the whole heat, and the hybrid's −6.32e-5 (relative changes, not pJ; §11).
   - Under the first draft's quadrature this guard would have failed (1.7e-2). That is the collision
     the lead's review found.
   - **Its scope excludes the reversal onset** (§3.3's known limit). There the hybrid's heat moves
     by −1.3e-3 of itself for a 10³ trace change (probe 2g; a relative change). The resolved-start
     rule keeps that configuration out of the guard worlds.

**Independence of the references** (the lead's ruling with the advisor, 14 November 2026).
- **The prototype is development evidence, not a reference of record.** Probes 2 to 2g, C3 and C3b share
  the operator's scheme and its author.
- **Who writes the references.** Appendix A's ΔG tests (item 4) and MG0c's references (§6.4: the
  dispersion relation, the mode propagators, the SciPy pattern) are written by an agent that never
  reads the operator's code.
- **How the engine agent runs them.** Only through a usage note, as in S5. The usage note gives
  their inputs, outputs and tolerances, never their internals.

## 4. Numerics

### 4.1 Scales

| Case | Rates | h_sub · L at the step |
| --- | --- | --- |
| MG0c (synthetic, §6.4): k = 0.1 s⁻¹, ℓ = √(D_U/k) = 10 µm, D_U = 1e-11 and D_V = 1e-10 m²/s | L up to about 0.3 s⁻¹ while the pattern forms | at most 0.0076 at dt 0.05 s (probe 2, B2) |
| Morphogen scale (D150 §4.1): k about 1e-4 s⁻¹ | – | about 5e-8 at 1 ms |
| Catalysis (GZMK item 2): k_cat c_E/K_M, which no paper there reports | e.g. 1 s⁻¹ × 0.1 | about 5e-5 at 1 ms |
| Fast binding, k_on c of about 1e2 to 1e4 s⁻¹ | stiff at 1 ms | refused where dt · L > 1 (§4.3); a door (§7.3) |

**Who sets the transport's step:**
- **Species-only worlds:** the species' own face rates set dt. Probe 1's chain (h = 10 µm,
  D_V = 1e-10 m²/s) has an explicit-rate bound of 4 s⁻¹, so it admits dt ≤ 0.25 s. A step at 1.24
  times the bound was refused.
- **Worlds with moving ions:** the ions set dt (D150 §4.2).

### 4.2 The half-step integrator

**SSPRK(3,3)** (Shu & Osher 1988; Gottlieb, Shu & Tadmor 2001), with m sub-steps of size
h_sub = h/m.
- **Version 1 takes m = 1** (h_sub = h = dt/2), because it refuses dt · L > 1 (§4.3).
- **Larger m is the stiff door.** It is written here generally so that door stays open.

The stages are:

    Y1 = n,  Y2 = n + h_sub ν J(Y1),  Y3 = n + h_sub ν (J(Y1) + J(Y2))/4,
    Δξ = h_sub (J(Y1) + J(Y2) + 4 J(Y3))/6,  n' = n + ν Δξ.

This is the Butcher form. It is extent-consistent, so the material identity Δn = ν Δξ holds by
construction.

**The stage condition.** L_s(Y) is the rate at which the node's routes consume species s, per amount,
written with unidirectional fluxes:

    L_s(Y) = [ Σ_driven max(−ν_sr, 0) J_r(Y) + Σ_passive (max(−ν_sr, 0) J⁺_r(Y) + max(ν_sr, 0) J⁻_r(Y)) ] / Y_s.

- **A driven route** has one flux J_r ≥ 0, which consumes the species it net-consumes.
- **A passive route's** forward flux consumes its net reactants, and its reverse flux its net
  products (§2.2).
- **The rule:** at every stage of every sub-step, h_sub max_{s,i} L_s ≤ θ = 1/2.
- **Which fluxes come from where.** The operator computes J⁺ and J⁻ itself from the same activity
  logarithms, for the condition only. The net rate it integrates still comes from
  `reversible_flux`, called unchanged, whose expm1 form stays accurate near equilibrium.
- **A correction, found in review.** The signed net rate must not be used in place of the two
  fluxes. For a passive route running in reverse (J_r < 0), the signed form makes the condition pass
  vacuously while its products are consumed.
  - Probe 2's stage check had exactly that flaw for passive routes. Its passive cases (B4, B6, B7)
    ran forward at h k of about 0.01, so they did not test the condition.
  - Probe 2c tested the corrected definition (§10.2). On a passive A ⇌ B running in reverse, the
    signed form read 0 and admitted steps up to h (k_f + k_r) = 1.5. The corrected form admitted up
    to 0.55 and refused beyond.

**Positivity is then a theorem** (**S**, the SSP property).
- In Shu–Osher form each stage is a convex combination of the start state and forward-Euler steps
  Y + h_sub f(Y).
- Write f = P − C. Production P_s = Σ_driven max(ν_sr, 0) J_r +
  Σ_passive (max(ν_sr, 0) J⁺_r + max(−ν_sr, 0) J⁻_r) is non-negative at positive states.
  Consumption is C_s = L_s Y_s (§2.2: every flux vanishes with the species it consumes).
- Then Y + h_sub f(Y) ≥ Y (1 − h_sub L(Y)) > 0, component by component.
- So with θ < 1 every stage and the result are positive. At θ = 1/2 each Euler step keeps at least
  half of every amount, a margin that rounding cannot cross.
- **The backstop.** The half-step also refuses any non-positive stage or result directly (its
  validity, §2.5). In probe 2c that refusal caught the one negative stage, at h (k_f + k_r) = 3,
  under both forms.
- **What the corrected condition adds** is the theorem and the accuracy and stability role of θ, not
  only a refusal after the fact.

**Stability and accuracy.**
- **The bound.** The condition bounds each species' own consumption slope by α_max θ ≤ 1.5. For mass
  action and for each unidirectional flux of a passive route, ∂C_s/∂n_s ≤ α_max L_s, since each flux
  is a power of the amount of order at most 3. For Michaelis–Menten, the slope is at most L_s. That
  is inside SSPRK(3,3)'s real stability interval of [−2.51, 0] (**S**).
- **What it leaves out.** It does not bound the full spectrum: couplings between species can add
  complex eigenvalues.
- **So the dt study measures accuracy and stability at the admitted steps; it does not prove them.**
  Probe 2's B8 shows the margins on a fast catalysed depletion:

| h L at the start | Forward Euler | SSPRK(3,3) | Exact | At θ = 1/2 |
| --- | --- | --- | --- | --- |
| 0.25 | 7.50e-7 | 7.788e-7 | 7.790e-7 | admitted (0.02% error) |
| 0.5 | 5.00e-7 | 6.044e-7 | 6.068e-7 | admitted (0.4%) |
| 0.9 | 1.01e-7 | 3.838e-7 | 4.068e-7 | refused (5.6% error) |
| 1.5 | −4.99e-7 | a non-positive stage | 2.23e-7 | refused |
| 3.0 | −2.00e-6 | −2.00e-6 | 4.98e-8 | refused |

**Refused, never repaired.**
- **What a failure is.** A stage that fails the condition, or any non-finite or non-positive amount,
  invalidates the half-step.
- **What follows.** The composite returns the start state, and the runner reports the refusal with
  the operator's message: the largest h L and the step that admits it. Version 1 offers no
  sub-steps, so the advice is a smaller dt.
- **A property of the run.** As with @3's membrane-rate rule, the admissible step depends on the run,
  not on the definition.

**Why not an implicit or Patankar-type scheme in version 1.**
- **The candidates.** Modified Patankar schemes (Burchard, Deleersnijder & Meister 2003; Bruggeman et
  al. 2007) are unconditionally positive and conservative, and they suit stiff kinetics.
- **Their cost.** At large h L they stay positive by slowing the kinetics, through a scaling factor.
  That is an error the run cannot see.
- **Why explicit is enough.** Version 1's consumers are not stiff at the transport's step (§4.1).
  An explicit SSP method under a hard condition is then the more transparent choice: every step it
  takes is accurate to its order, or it is refused.
- **The door for stiff kinetics** (§7.3): a linearly implicit positive scheme, or a per-node implicit
  solve with a fixed iteration count and a residual check (D150's saturable-solve precedent), each
  with its own qualification.

**The half-step is not the limit.** It is third order inside a second-order split. Probe 2b's B9 ran
the open linear network 0 → A, A → 0 against turnover's closed form, with ratios 8.19 and 8.10.

**Finding 3: neutral species on junctions and membranes** (HANDOFF).
- **What the bound covers.** @3's `explicit_rate_bound` bounds the faces for every species. On
  junctions and membranes it bounds only charge relaxation, weighted by z².
- **The gap.** A neutral species with a junction or membrane permeability therefore has no
  material-rate bound at the definition.
- **What C4 measured on the engine** (§10.3).
  - Nothing refuses at the definition, and the run-time membrane-rate rule reads 0 for a neutral
    species.
  - **In species-only worlds** the host energy ledger refuses at row 1 once the per-step relaxation
    exponent x reaches 0.1. Below that, runs pass with small, second-order errors.
  - **When other flows set the shared bound** (C4c), runs pass every host check up to x = 1, with
    silent errors against the exact relaxation of up to 13% of the initial difference. From
    x = 1.5 the energy ledger refuses. Beyond x = 2, the difference grows until positivity
    refuses.
- **What version 1 does** (the lead's ruling, §9 question 7). It keeps the refusal of reacting
  species with nonzero membrane or junction permeability. D150's inventory species are impermeant
  anyway, so nothing a consumer needs is lost.
- **The queued D148 round** (the lead's ruling, §9 question 7). After D150 v1 lands, @3 gains the
  z = 0 material term on junctions and membranes, in `explicit_rate_bound` and in the run-time
  membrane-rate rule, statically gated.
  - It fixes stability, not accuracy. On the faces' convention it admits x ≤ 1, so the silent
    errors of up to 13% at x = 1 stay admitted, as they are on faces.
  - The existing-worlds sweep found no world that declares a neutral permeant species (§10.3).

### 4.3 Splitting against transport, and stiffness

**The split.** Strang (1968) splitting, the composite's symmetric order P(h/2) … I(dt) … P(h/2),
makes the network a split part around @3's step. D150's turnover and exchange sit in their declared
order.

**It is second order in dt,** with an error O(dt²) in the commutator of reactions and transport.
Probe 2's prototype measured it, with @3's species transport as the explicit ARS(2,2,2)
polynomial. Probe 1 confirmed that polynomial on the engine to 1.3e-14 at 32 nodes (3.0e-14 at
128).
- **Linear modes** of the Turing chain, against the exact discrete propagator: ratios 3.98 to 4.07
  over four modes, unstable, stable real and stable complex (B1, B1b).
- **The nonlinear pattern** from seeded noise, against an independent SciPy integration (DOP853,
  rtol 1e-12) of the same semi-discrete system: ratios 4.01 to 4.03 on three domains (B2).
- **A passive linear system** against its closed form: ratios 4.02 and 4.01 (B4).

**The network's own couplings are not split.** One integrator per node sees every route (§1.1). So
the activator–inhibitor feedback is integrated whole, and only the reaction–transport coupling is
split.

**Stiffness relative to the split step (probe C3; the lead's ruling).**
- **The risk.** With sub-steps, a network may be stiff relative to dt (dt · L > 1) while every
  sub-step meets the condition. Splitting stiff reactions from transport can then lose order
  (Hundsdorfer & Verwer 2003, ch. IV).
- **What C3 measured** (prototype; transport the ARS(2,2,2) polynomial). It used three worlds on a
  zero-flux chain, with m = ceil(dt · L) sub-steps holding the stage condition, against exact or
  stiff-solver references, at T = 50 s:

  | dt · L | 0.25 → 0.5 | 0.5 → 1 | 1 → 2 | 2 → 5 | 5 → 10 | 10 → 20 |
  | --- | --- | --- | --- | --- | --- | --- |
  | W1, fast buffering A ⇌ B (B immobile), on the slow manifold | 1.93 | 1.78 | 2.17 | 1.74 | 1.41 | 1.22 |
  | W1, off the manifold | 1.97 | 1.91 | 1.98 | 1.63 | 1.25 | 1.10 |
  | W2, nonlinear fast binding A + B ⇌ C (B, C immobile) | 1.99 | 1.98 | 1.83 | 1.43 | 1.09 | 1.04 |
  | W3, a driven sink on half the domain | 1.97 | 1.92 | 2.03 | 1.77 | 1.47 | 1.39 |

  These are observed orders between consecutive steps.
  - **All three worlds hold second order up to dt · L of about 2,** then fall toward first order.
  - **A correction, found in the advisor's review.** C3's first run of W2 used L = 59.82 s⁻¹, the
    start's largest consumption rate, so its steps missed T = 50 s by up to 0.15 s, and that
    end-time artefact looked like an irregular order. The rerun, with L = 60 and exact end times,
    gives the row above. Its reference stands: Radau at rtol 1e-11 against DOP853 at rtol 1e-13
    agree to 1.6e-14. 4× the sub-steps moved no error by more than 2% (C3b, rerun). The first run's
    evidence is kept beside the rerun's.
- **The rule (version 1).**
  - **dt · L > 1 is refused at run time.** With one sub-step that is the stage condition at θ = 1/2,
    so version 1 declares no sub-step count (§2.1).
  - **The measured margin.** Second order holds to about 2 in all three worlds.
  - **Below 1, each registered world's own dt study is still its evidence.** MG0c's worlds sit at
    dt · L ≤ 0.015, where probe 2 measured ratios of 4.0.
- **The door.** Sub-steps (m > 1) need a splitting that holds its order where C3 found reduction:
  for example a stiff reaction treated implicitly in the transport step, or a different
  composition. Each needs its own probe.

### 4.4 Positivity and the trace

- **The trace background.** D150 §1.3's background holds: every species is positive everywhere, and
  a reacting species that is "absent" is a declared trace.
- **Depletion is safe.** Rates vanish as consumed species vanish (§2.2), so depletion approaches zero
  at worst as e^{−L t}, and the stage condition keeps every step positive.
- **The anchored representation stalls, it does not underflow** (D150 v1's milestone 1; D150 §1.3,
  as amended).
  - **Why.** @3 stores an amount as anchor + increment, n = a + δ.
  - **What a cleared pool does.** A pool cleared with no supply follows the closed form only until
    L t ≈ 36, where e^{−L t} reaches ε. It then stalls, positive, at about ε × its anchor, and is
    never refused.
  - **Where kt ≈ 708 applies.** Only to amounts stored without an anchor.
  - **For this operator.** A depleted reacting species stalls the same way. Its rates, computed from
    the stalled amount, stay finite, and the stage condition is unaffected. Its half-step changes
    round to nothing, and its share of ΔG is then zero.
- **For the stiff-front guard the stall is expected, not a failure** (§6.5). The guard checks:
  - that every accepted step stays positive;
  - that the stage condition refuses where it must;
  - that a species driven below about ε × its anchor stalls there, positive and unrefused.
- **The prototype's representation.** The prototype (probes 2 to 2g, C3, C3b) stores amounts directly,
  without an anchor. That is immaterial there:
  - no probed species falls more than a factor of about 40 below its start. The largest fall is
    C3's half-domain sink, 2.5e-5 against 1e-3 mM;
  - there, the anchored rounding of about ε × the anchor is near 1e-14 relative, far below every
    error the probes report.
- **Production from the trace is positive by construction,** since sources add.
- **The stiff-front guard** runs through the checked step map, as D150's ruling 7 does:
  - a species at 1e-15 mM consumed by a fast sink;
  - a product switched on from 1e-15 mM.

  Every accepted step must stay positive, and a step where the condition fails must be refused
  (B8).

### 4.5 Bitwise idleness (D136)

There are three claims, as in D150 §7.
1. **Not declared.** Every existing composition's jaxprs, constants and bindings are identical under
   the constants-aware crossrev. The operator is a new module, and the adapter function it uses is
   D150's addition. **Promised.**
2. **Declared, but idle.**
   - With no routes, the operator is statically idle and skipped.
   - With every multiplier zero in a step, the half-step selects its start state at every node
     (`where`; it never adds a computed zero), and every field is bitwise equal to the composition
     without it.
   - A node whose routes all have zero multipliers is selected unchanged in the same way.

   **Promised.**
3. **Species declared, with no reaction, against no species.** **Reported, not promised** (D150's
   claim 3). Probe 1 saw the ion rows bitwise unchanged in its CPU program.

A network in which only some reactions run at zero rate is not promised bitwise against the network
without them. XLA's reduction order over the route axis depends on the program.

### 4.6 Which solvers admit it, and what is refused

| Solver or mode | Version 1 | Reason |
| --- | --- | --- |
| IMEX ARS(2,2,2) | Admitted | The composite's split parts; second order (§4.3) |
| IMEX Euler | Admitted | First order overall; its energy rtol is 2e-2 |
| RK4 (reference runs) | **Refused** at the definition | Reasons (a) to (d) below the table |
| Stationary analysis (`stationary_continuation_analysis@1`) | **Refused** | Reasons (e) to (g) below the table |
| Projective mode C and the other coarse modes | Not admitted | `execution.projective` supports @1 to @3 only |
| vmap batches, windows, restart, snapshots | Admitted | Per-world parameters and controls are bindings; the static network enters the batch signature |

**Why RK4 is refused** (confirmed by the lead with the advisor, 14 November 2026, with this
framing; §9 question 5):
- (a) **The split is not what distinguishes this operator.**
  - The coupled RK4 path takes operator rates on owned fields only, and this operator writes @3's
    rows (injection's finding, v2 §4.1). Under RK4 it would therefore run "split", with half-steps
    around the inner RK4 step.
  - D150's turnover and exchange run the same way. D150's RK4 runs are not unsplit references for
    its operators either: what they sharpen is @3's transport and face heat, under the absolute
    bound (D150 §4.2).
  - So (a) holds for both, and it is not a reason to treat them differently.
- **What distinguishes it:**
  - (b) **RK4's sharp absolute energy bound (2e-8 pJ) adds nothing for this operator's own
    bookings.** They are exact and are checked at rounding in the face-free world under IMEX (§3.4).
  - (d) **D150's RK4 guard worlds stay the transport's sharp reference,** without the network, so
    nothing is lost.
  - **No consumer needs it.** MG0c's references are NumPy, and its runs are IMEX (§6).
- (c) **Cost.** RK4's step limit of 1e-4 s multiplies the steps by 10 to 2,500.

RK4 is admitted when a consumer needs it, or once a coupled-rates contract extension (operator rates
on inner fields) makes an unsplit RK4 a reference for the coupled reaction–transport system.

**Why the stationary analysis is refused:**
- (e) It refuses the composite's ID (D150 probe 2).
- (f) Its right-hand side would need operator rates on inner fields, the same extension.
- (g) Its Newton test is one absolute tolerance (1e-10 mM per amount), too coarse for µM–nM species
  without per-species scaling (D150 §8).

MG0c's steady states and Jacobians come from the NumPy references (§6). The door is coupled rates
plus per-species scaling, and continuation of Turing bifurcations would be worth having later.

### 4.7 Cost

- **Per node and half-step:** three rate evaluations and three stage-condition evaluations over the
  node's routes, plus one divided-difference potential per species for the hybrid's share. That is
  O(R) work for R routes, small beside the dense field (D150 §4.4).
- **Probe 1.** The species-only chain costs 2.2 to 2.7 ms per step at 32 nodes and 4.1 ms at 128
  nodes, on one CPU core with host checks, after a compile of about 15 s. The network adds
  O(R × N) work per half-step (**S**).
- **MG0c's runs.** A run of about 6e4 steps at dt = 0.05 s (3,000 s simulated) costs about 3 min of
  CPU (**S**).

### 4.8 The 30-minute rule

- **Scale invariance** (**S**). Fix h/ℓ, d and the network's non-dimensional parameters. The number
  of steps to pattern saturation is then set by D_V/(h² σ_max) at the transport's admissible step,
  and it does not depend on k. A compressed world is the same discrete problem.
- **So every check reaches the code under test in minutes.** Detached runs are needed only for the
  full judged set: about 20 runs, about 1 h of CPU (§6.4).

## 5. Interactions with existing operators

| With | Version 1 | Why |
| --- | --- | --- |
| @3 alone; `electrode_current_injection@1` | Composes | No view conflict. Injection refuses neutral carriers, so it never writes the reacting rows |
| D150's `scheduled_species_turnover@1` | Composes, except a route on a (species, node) the network writes (§1.1) | Writers of the same rows; fluxes add |
| D150's `scheduled_species_exchange@1` | Composes | Transport across a patch, split from the network at O(dt²) in the composite's symmetric order |
| `scheduled_cell_replacement@1` | Outside routes compose; **cell routes on replaced slots are refused** (the lead's ruling, §2.1) | Both read declared volumes, and the event swaps every species' pool (D150 §5.2). No version 1 consumer needs cell routes on replaced slots, and D150's occupant mechanism is still being coded. Version 1.1 door: the occupant rule through that mechanism |
| Water; `restricted_cleft_lumen@1/@2`; replacement@2 | Refused (`CONFLICTS_VIEW` volumes; @2 requires water) | Concentrations and ΔG read the declared volume. Version 1.1 books at the view through water's endpoint free energy (D150 §5.1) |
| `membrane_entity_state@1` | Composes | It provides membrane views, which the network never reads |
| Insertion@1/@2, partition, bridge closure | Refused | The partition and insertion@2 close masks the network reads (`active`, `outside_active`); insertion@1 provides `outside_active` and the outside anchors; bridge closure requires the partition. Version 1.1, under the S5 living-interval rule (D150 §5.3) |
| The k-anion symport | Waits | It requires water |

## 6. Qualification

### 6.1 The first acceptance is numerical qualification (D138)

**Can a version 1 run differ from its references?** Only by discretisation and splitting error
(**S**):
- the network's equations are the declared ones;
- its species are decoupled from the ions (neutral, impermeant; probe 1 found the ions bitwise
  unchanged);
- its volumes are fixed.

So a comparison with a paper's data would test that paper's kinetic model and parameters, not the
engine. Running the paper's own model would also be reproducing it, which needs the user's approval
(D138; D151 keeps that line). That would apply, for example, to Nodal and Lefty (Müller 2012).

**So the first acceptance is registered as numerical qualification** against independent textbook
references, which take no paper's data and fit nothing:
- the closed-form linear reaction–diffusion solution (§6.2);
- the linear stability analysis of a two-species system (§6.3);
- the exact solutions of the same discrete systems (§6.4).

**Who writes the references** (the lead's ruling with the advisor; §3.4).
- **An agent that never reads the operator's code** writes these references and Appendix A's ΔG
  tests. The engine agent runs them only through a usage note, as in S5.
- **The probe numbers quoted below are the prototype's.** That prototype shares the scheme and its
  author, so its numbers are development evidence. They guided the design and will guide the
  tolerances, but they are not references of record.

**The lead's reading of D138** (§9 question 9). MG0c is within D138, proceeding unless the user
objects:
- D152 names MG0c as the qualification case;
- the morphogenesis plan's row names the dispersion relation;
- the check runs a new engine operator on a textbook network and compares it with mathematics, not
  with a paper's results.

### 6.2 Reference 1: the closed-form linear reaction–diffusion solution

**The textbook source.** Linear reaction and diffusion admit closed forms: Crank 1975, ch. 14, which
includes Danckwerts' (1951) transformation for first-order reaction. On a zero-flux chain of N nodes
of width h, the Neumann cosines cos(nπ(i + ½)/N) are exact eigenvectors of the discrete Laplacian,
with eigenvalues λ_n = (4/h²) sin²(nπ/(2N)). These tend to (nπ/L)² as h → 0, with L = N h.

**The closed form per mode.** A linear network couples the species only within a mode. Each mode's
coefficient vector a_n therefore evolves exactly as

    a_n(t) = expm[(K − λ_n D) t] a_n(0),

with K the network's rate matrix and D = diag(D_s).

**The worlds:**
1. **Passive A ⇌ B** (detailed balance, K_eq = 10) with D_A ≠ D_B, on a zero-flux chain. Probe 2's
   B4 measured:
   - the mode-wise closed form against the full matrix exponential: 2.5e-14;
   - the prototype against the closed form at dt 0.05, 0.025 and 0.0125 s: 4.6e-7, 1.15e-7 and
     2.9e-8 of the scale (ratios 4.02 and 4.01);
   - total heat converging to 0.0346789 pJ;
   - the well-mixed equilibrium c_B/c_A = 10.000.
2. **Open linear kinetics** (0 → A at P, A → 0 at k) at one node, against turnover's closed form
   n(t) = n0 e^{−kt} + (P/k)(1 − e^{−kt}). This is a cross-check with D150. Probe 2b's B9 measured
   1.25e-6, 1.53e-7 and 1.89e-8 relative at h 0.2, 0.1 and 0.05 s (ratios 8.19 and 8.10).

### 6.3 Reference 2: the linear stability analysis of a two-species activator–inhibitor system

**The analysis** (Turing 1952; Murray 2003, ch. 2; Maini & Woolley, the source the morphogenesis plan
cites). Take u_t = f(u, v) + D_u ∇²u and v_t = g(u, v) + D_v ∇²v, with homogeneous steady state
(u0, v0) and Jacobian J = [[f_u, f_v], [g_u, g_v]]. A mode of wavenumber k grows at σ(k), the largest
real part of the eigenvalues of J − k² diag(D_u, D_v).

**The conditions for diffusion-driven instability:**
- f_u + g_v < 0 and f_u g_v − f_v g_u > 0, so the uniform state is stable without diffusion;
- D_v f_u + D_u g_v > 2 √(D_u D_v det J) > 0.

**What follows from them:**
- **The band:** the unstable modes are those whose k² lies between the roots of
  D_u D_v k⁴ − (D_v f_u + D_u g_v) k² + det J = 0.
- **The critical ratio** d_c = D_v/D_u is the ratio at which the band opens.
- **Only k = nπ/L on a zero-flux domain** (Neumann eigenfunctions cos(nπx/L)). A domain whose band
  contains no admissible k stays homogeneous although d > d_c.
- **On the discrete chain,** k² is replaced by λ_n, so each mode's linear evolution is the 2×2 matrix
  exponential of §6.2 with K the Jacobian. That is an exact discrete reference.

### 6.4 MG0c: Turing patterning at the predicted wavelength

**The kinetics:** Schnakenberg (1979), written as four generic mass-action reactions at the outside
nodes:
- ∅ → U, at the rate constant a k c* (mM s⁻¹);
- U → ∅, at k (s⁻¹);
- ∅ → V, at b k c*;
- 2U + V → 3U, at k/c*² (mM⁻² s⁻¹).

**Moieties.** U and V share a moiety M, so the fourth reaction is closed. The first and third are
sources, and the second is a sink.

**In non-dimensional form,** with u = c_U/c*, τ = k t and x̃ = x/ℓ, where ℓ = √(D_U/k):

    u_τ = a − u + u² v + ∇²u,   v_τ = b − u² v + d ∇²v,   d = D_V/D_U

(Murray 2003, ch. 2).

**Energy.** Every route is driven, so W = ΔG at every node and no heat is booked.

**Parameters** (synthetic, labelled so; a textbook regime): a = 0.1, b = 0.9, d = 10. Probe 2, part A:
- steady state (u0, v0) = (1, 0.9);
- J = [[0.8, 1], [−1.8, −1]], with trace −0.2 and determinant 1, so every Turing condition holds;
- d_c = 8.568;
- the band is 0.2 < k̃² < 0.5;
- σ_max = 0.0572 at k̃² = 0.3185 (0.318545; amended at milestone 1, §11), a wavelength of
  11.13 ℓ.

**The dimensional scale** (synthetic, compressed): k = 0.1 s⁻¹, c* = 1 µM, D_U = 1e-11 m²/s and
D_V = 1e-10 m²/s, so ℓ = 10 µm. The fastest mode then e-folds in 175 s, at a wavelength of 111 µm.

**The world:** probe 1's closed chain, at node spacing h = ℓ/2 = 5 µm (0.5 pL nodes):
- quiescent ions;
- one quiescent cell with a capacitive patch on every node and one on a held bath;
- no face to a bath, so the chain has zero-flux ends.

The explicit-rate bound is 4 D_V/h² = 16 s⁻¹, which admits dt ≤ 0.0625 s. The dt study uses 0.05,
0.025 and 0.0125 s.

**The domains** (probe 2, part A, discrete at h = ℓ/2):

| L/ℓ | Nodes | Admissible unstable modes | σ_n (non-dimensional) | Role |
| --- | --- | --- | --- | --- |
| 6 | 12 | n = 1 | 0.0508 | one mode, wavelength 2L |
| 8 | 16 | **none** (n = 1: −0.089; n = 2: −0.065) | – | **no admissible mode** although d > d_c |
| 11 | 22 | n = 2 | 0.0571 | one mode, wavelength L |
| 16 | 32 | n = 3 | 0.0556 | one mode, wavelength 2L/3 |
| 22 | 44 | n = 4 (n = 5 marginal, −0.0023) | 0.0571 | not used: a near-marginal neighbour |

At h = ℓ/2, the discrete k² falls short of the continuum value by 0.6–0.7% near the band (O(h²),
reported).

**The staircase** (the continuum's fastest admissible mode against L/ℓ, sampled every 0.5):

| L/ℓ | 4 | 4.5–7 | 7.5–8.5 | 9–13.5 | 14–19 | 19.5–24.5 | 25–30.5 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Fastest admissible mode | none | 1 | none | 2 | 3 | 4 | 5 |

**Judged items.** These are the basis for registration (the lead's ruling with the advisor; §9
question 8).
- Tolerances are pinned at registration from the dt study and the reference terms (D150 §6's rule).
- Each run is made once, from a clean snapshot.
- The references are written independently of the operator's code (§6.1).

| Item | Check |
| --- | --- |
| Q1, mode propagation | On L/ℓ = 6, 11 and 16, single-mode starts (amplitude 1e-7 of c*) for every n ≤ 6: each mode's coefficient vector at its record against the exact discrete propagator; second order in dt. Prototype: 2.0e-6 to 1.25e-3 relative at 0.0125 to 0.05 s, ratios 3.98 to 4.07 (B1, B1b) |
| Q2, admissible modes only | On L/ℓ = 8, from seeded noise (1e-3 of c*), the deviation from uniform decays at the slowest admissible rate (n = 2, σ = −0.065 k) and the pattern never forms. Prototype: 1.4e-8 of u0 at 1,500 s from 1e-3 (B2) |
| Q3, the predicted wavelength | On L/ℓ = 6, 11 and 16, from seeded noise, the dominant mode during the linear phase and at saturation is the only admissible unstable mode, n = 1, 2 and 3 (wavelengths 2L, L and 2L/3), and its fitted growth rate matches σ_n. Prototype: dominant modes 1 and 2 on 6 and 11, as the reference integration gives (B2) |
| Q4, the staircase | Over a declared sweep of L/ℓ from 4 to 30 (amended at milestone 1, §11), the fastest-growing mode among single-mode starts on the engine follows the discrete argmax of σ_n, including the no-mode point at 4 and the 7.5–8.5 gap |
| Q5, the subcritical control | d = 8 < d_c: on every domain every mode decays, at its predicted rate |
| Q6, the nonlinear pattern | From the same seeded start, the engine's pattern at its records (to saturation) against an independent integration of the same semi-discrete system (SciPy DOP853, rtol 1e-12); second order in dt. Prototype: 4.8e-4, 1.19e-4 and 2.97e-5 of c* on L/ℓ = 11 (ratios 4.02 and 4.01). The saturated amplitude, max over nodes of \|u − mean(u)\| at 3000 s in the reference's own integration of Q6's start, is 0.43 c*, with u* = c* (corrected at the lead's review, §11.4; the prototype's "0.68 u0" was the range (max u − min u)/u* at 1500 s from its own start, B2) |
| Q7, accounting | Material ledgers at the species' floors; every host check; the face-free energy world at rounding (§3.4); positivity; restart through a written snapshot, bitwise; a vmap batch of seeds on L/ℓ = 6, bitwise against its reverse and each world within 1e-12 of its scalar run (a batch of domains cannot run, since a route's node is in the batch signature; ruling 1, §11.4) |

**Reported, not judged:** the discrete σ_n and k_n against the continuum, which converge at second
order in h.

The lead's review of the protocol (§11.4) sets how each check is judged: the tolerances, the
controls by parameter, Q4's near ties and the scope line.

**What MG0c does not show:**
- any biological claim;
- the selection between several unstable modes on wide domains, which is nonlinear and outside the
  linear theory;
- two-dimensional patterns (they need sparse field IDs, D150 §3);
- recovery after damage, which is E15's question.

**The second world is a separate, later item, not part of MG0c's first acceptance** (the lead's
ruling, §9 question 8).
- **The world.** The same network inside cells, with secretion and uptake by D150's exchange, and
  diffusion on faces.
- **Its reference.** The linear stability of the three-compartment system.
- **What it checks.** The composition, not only the operator.
- **When.** It follows C5 (§10.4) and D150 v1's code.

### 6.5 Guards

- **Tier 1.** A smoke test under 20 s (the v2 rule): one tiny world, a few steps, the ledgers
  closing and the idle identity.
- **Idle:** §4.5's three claims.
- **Ledgers at the species' scale.** @3's per-species ledgers with D150's species-scale floors, on
  host and device. The negative control: a misbooked accumulator fails the species' row while the
  ions pass.
- **Energy:** §3.4's guards.
- **Positivity:**
  - **the stiff-front guard** (§4.4). A species driven below about ε × its anchor stalls there,
    positive and unrefused; that is expected, not a failure;
  - **background insensitivity** (D150 §1.3). A 10³ change of a negligible trace (1e-12 to 1e-9 mM)
    moves every compared quantity far below its tolerance.
    - That includes H and W at mixed nodes, which are held to the true heat's own dependence (§3.4,
      guard 5).
    - A trace that is not negligible against the amounts a species reaches (probe 2d's 1e-6 against
      3e-5 mM) changes the physics, and lies outside this guard;
  - **the refusal of a step beyond the stage condition** (dt · L > 1), with the prior state kept
    bitwise.
- **Restart and vmap:**
  - restart at, before and after a multiplier change, and through a written snapshot in a fresh
    process, bitwise;
  - vector-window batches mixing per-world parameters, each world within 1e-12 of its scalar run
    and bitwise against the reversed batch;
  - different networks refused by the batch signature.
- **The constants-aware crossrev** (D148):
  - existing compositions are identical;
  - the operator's per-world values are bindings, as the crossrev records show.
- **D148.** No in-place change to shared qualified code is proposed. If implementation finds one is
  needed, its four criteria apply, with the stop rule written first.
- **Gates.** Tier 1 and tier 2 before landing (AGENTS.md); MG0c's judged runs are tier 3.

### 6.6 Later targets (deferred under D151)

- **GZMK item 2's catalysis.** The review's papers report no kinetic constant (Donado 2025 states
  concentrations and times only). So a calibration needs a published kinetic dataset for a
  protease on a soluble substrate, and none is named yet.
- **A biological Turing comparison** (for example Nodal and Lefty, Müller 2012, whose records D150
  §6 verified) would reproduce that paper's model, and needs the user's approval (D138). It becomes
  informative when the engine's model holds something the textbook form lacks: cell-resolved
  secretion and uptake, binding, volume change or regulation.

## 7. Limits and versions

### 7.1 What version 1 includes

- The operator `local_species_reactions@1`, on neutral species rows, at cells and finite outside
  nodes, at the declared volumes.
- Passive detailed-balanced mass action; driven mass action (orders 0 to 3) and Michaelis–Menten
  (with or without a catalyst); Hill activation and inhibition factors on driven laws.
- Declared moieties, sources and sinks; the exact energy bookings, with the per-route hybrid at
  mixed nodes and the owned standard-potential term.
- SSPRK(3,3) half-steps at one sub-step with the stage condition (dt · L ≤ 1); IMEX inner steps;
  vmap, windows and restart.
- Composition with:
  - @3 and injection;
  - D150's turnover (outside the network's rows) and exchange;
  - replacement@1, for outside routes and for cells that are not replaced;
  - `membrane_entity_state@1`.

### 7.2 What version 1 does not include, and refuses

- Charged species, and reacting species with membrane or junction permeability.
- Held-bath sites, membrane-surface reactions and occupancy.
- Volume providers (water, the lumen, replacement@2) and closers (insertion, partition, bridge).
- RK4, the stationary analysis and the coarse modes.
- Kinetics with dt · L > 1, refused at run time (§4.3, from C3); sub-steps. The step a declared
  accuracy needs is reported, not enforced (FR-43 / D315; the operator's docstring): third order,
  so about 0.1 / k_f for 2 × 10⁻⁵ of the largest amount on FR-43's chain at any size, six times
  below the refusal; a stiff integrator stays the door of §7.3, a separate law.
- More than 1,024 species per world (D150's cap, raised from 16 by FR-43 / D315 on FR-43's probe
  and from 7 by FR-9 / D165 on the W4 probe; every species counts, ions included).
- Per-carrier parameter sets; reversible Michaelis–Menten; multi-substrate mechanisms; delays.
- A turnover route on a reacting (species, node) (Q3).
- A cell route on a slot that replacement@1 replaces (Q6).
- **The combined effect of Q3 and Q6.** In version 1 a species cannot both react inside a replaced
  cell and be produced there by turnover:
  - Q6 refuses reactions on the replaced slot;
  - Q3 refuses turnover on any reacting row;
  - turnover alone may still act in a replaced cell, under D150's occupant rule.

  That is fine for MG0c, which has no replacement, and for catalysis at outside nodes, whose routes
  compose with replacement@1. A consumer that needs both, E15's regeneration being the likely first,
  waits for version 1.1's occupant rule for cell routes.

### 7.3 The doors (version 1.1 and later; each needs its own design and qualification)

| Door | What it needs |
| --- | --- |
| Volume (water, the lumen) | **Delivered for water (FR-43 / D315):** `volume` and `extracellular_volume` are current reads at the split, with C1's fallback, so every world without a volume changer keeps its program; the half-step's concentrations, rates, stage condition and bookings take the view's volumes, held over the half-step, and its bookings meet water's dilution term (docs/FR43_SHARED_INVENTORIES_DESIGN.md §2.3). The lumens and replacement@2 stay refused (`check_volume_changers`) until a probe covers them |
| Closers | S5's living-interval rule (D150 §5.3) |
| Charged closed reactions (buffering) | Σ_s z_s ν_sr = 0 checked in integers; the field and electrode exactness of D150 §3 re-argued |
| Stiff kinetics (dt · L > 1) | Sub-steps with a splitting that holds its order where C3 found reduction; or a positive implicit or linearly implicit half-step. Each needs its own order and positivity probes |
| Cell routes on replaced slots | Built (FR-26, D244): the operator's optional `templates` give a newcomer's multiplier per reaction, the founder's schedule ending at its death; a donor copy there is version 1.1 |
| Turnover on reacting rows | A measured splitting between turnover and the network, if a consumer needs it (Q3) |
| Coupled RK4 and the stationary analysis | Operator rates on inner fields in the composite's coupled right-hand side; per-species Newton scaling |
| Chemostats inside cells | A held species, an open passive law whose partner has a declared potential |
| Energy pools | Driven routes drawing on finite energy pools, making their work a metabolic cost (D150 question 11) |
| Regulation from other layers | The gene-regulation layer (held, D145) as a factor source or a production law, not an edit to these laws |
| More than 1,024 species | Another probe above 1,024 (FR-43's probe checked the ledgers, the sum orders and W4's parts up to it; FR-43 / D315, D150 §14), and the per-entry network layout, whose dense form costs about the square of the count (docs/FR43_SHARED_INVENTORIES_DESIGN.md §1.6) |
| Occupancy and surface catalysis | D150 §2.5's primitive and its four requirements |
| Reads of charged or permeant species (added at milestone 1, §11) | Factors and catalysts that read charged or permeant species, for example calcium-regulated production. Reads book nothing, so they need only a read-only species list beside the written one. E15's coupling from bioelectric to chemical signalling is the likely consumer |

### 7.4 What this note does not authorise

- Code before the note is accepted (D152).
- Any change to `network_reactions@1`, `network_control_factors@1` or the calcium-energy family.
- Any change to @3, the composite, the adapter (beyond D150's addition), or D150 v1's design or code.
- Lifting D145's holds (Cortés-Poza Phase 1, the gene-regulation track, catalogue stage 3).
- A law or species named for one experiment (D144).
- Reproducing a paper's model or writing a reference solution of it (D138, D151).
- Any scientific acceptance. Integration grants none, and MG0c's acceptance comes only from its
  registered protocol.

## 8. Effort and order of work

| Part | Agent-days |
| --- | --- |
| The operator's spec, parser and refusals (moieties, roles, sites, the turnover overlap, the species cap), binding | 1.0 |
| The laws and the half-step: rates, factors, SSPRK(3,3), the stage condition on unidirectional fluxes, extents, the exact bookings (the per-route hybrid) with the standard term, idle selection | 1.5 |
| Ledger terms, observations, the summary, the tier-1 smoke | 0.5 |
| Guards in the engine branch: the face-free and transport species-only worlds, negative controls, positivity, restart, vmap, crossrev, tier gates | 1.0 |
| **Independent references, by a second agent that never reads the operator's code:** Appendix A's ΔG tests, MG0c's references (dispersion, mode propagators, the SciPy pattern), and their usage note | 1.0 |
| MG0c: the driver, registration, judged runs (CPU, about 1 h) | 1.0 |
| **Total** | **6 (range 5 to 7)** |

**Order:**
1. **After D150 v1's code lands** (the adapter addition and the inventory-species helper).
2. **The code branch's first milestone is the contract fit, C1** (§10.4). It is in the checkout,
   behind its guards.
3. The operator.
4. Its guards.
5. MG0c.

**The independent references run in parallel.** They come from their own agent, with no access to
the operator's code. The engine agent runs them only through their usage note, as in S5.

Each step lands behind its tier-1 tests. Long runs go through `scripts/run_detached.sh`.

## 9. Questions and rulings

Rulings marked *ruled* are the lead's, with the advisor, 14 November 2026.

**For the lead:**
1. **The shared-state decision:** `network_reactions@1` stays separate, neither migrated nor wrapped
   (§1.2).
   - *Ruled:* confirmed, separate.
2. **The energy rule:** exact ΔG bookings, the three node cases, and the owned standard-potential
   term as a free-energy field outside the flows (§3.3).
   - *Ruled:* confirmed: exact ΔG, the three node cases, and the owned standard-potential term as a
     declared free-energy term, not a flow. This was subject to the mixed-node item, which the lead
     made blocking.
   - *That item's outcome* (probes 2d, 2e and 2f; §3.3):
     - **The stage quadrature alone fails at onsets.** It overbooks a passive switch-on from a trace
       by 34–54% in the first step, unseen.
     - **The average-vector-field share alone fails at crossings.** It goes negative where a driven
       route carries the state across the passive equilibrium. That is a refusal mode at admitted
       steps above a few 1e-3 fmol, found in the advisor's final review.
     - **The per-route hybrid fails at neither.** A route that keeps its sign through the step books
       its share; one that reverses books its quadrature. It keeps the network's coupling whole.
     - **The hybrid's sign:** non-negative by construction in the reversing branch and for
       unimolecular passive routes; measured and checked otherwise, with no negative step heat in
       any probe.
     - **What remains:** a measured known limit, the reversal onset (probe 2g). It arises when a
       driven source lifts a trace species across a passive equilibrium within one half-step.
       - The hybrid's quadrature branch then books 5.4–5.6 times that half-step's true heat
         (1e-12 trace), trace-dependently. In probe 2g's one world the whole heat was off by
         0.27–0.56% at 1 s.
       - It is recorded under the resolved-start rule.
       - The options put to the lead: (a) accept it as that known limit; (b) the first stage's
         affinity in the reversing branch by its average-vector-field mean, which is unmeasured;
         (c) a run-time refusal of a reversing route that starts at a trace. Option (a) was
         ruled (below).
   - *Ruled (round 2):* the per-route hybrid is adopted, with option (a) for the reversal onset. The
     limit applies at any half-step in which a driven route carries a trace species across a
     passive equilibrium, a mid-run switch-on included (§3.3).
   - *Ruled (round 2), rejected:* a symmetric split of passive and driven routes within the node. It
     would make every booking an exact state-function difference, but it would split a mixed
     network's kinetics at O(h²). The kinetics outweigh the heat and work attribution, which cannot
     affect closure.
3. **One local-kinetics writer per (species, node):** refuse a turnover route on a reacting row
   (§1.1).
   - *Ruled:* confirmed for version 1, with a door later (§7.3).
4. **Numerics:** SSPRK(3,3), θ = 1/2, stiff kinetics refused at run time (§4.2).
   - *Ruled:* confirmed: SSPRK(3,3), θ = 1/2 on the unidirectional-flux condition, refused not
     repaired. A Patankar-type or implicit half-step stays a door.
   - *Ruled:* the "labelled development runs" for dt · L > 1 with sub-steps are replaced by C3's
     outcome; until C3 shows the order holds, version 1 refuses dt · L > 1 at run time.
   - *C3's outcome* (§4.3): second order to dt · L of about 2 in all three worlds (buffering,
     nonlinear binding, a half-domain sink), with order reduction toward first order beyond. A first
     run's apparent irregularity in the binding world was an end-time artefact, corrected. So
     version 1 refuses dt · L > 1, takes one sub-step, and declares no sub-step count.
5. **RK4 refused,** not guarded as in D150 (§4.6).
   - *Ruled:* refusal confirmed, with the framing fixed. D150's split parts also run "split" under
     RK4, so the split applies to D150 too. The distinguishing reasons are:
     - exact bookings, checked at rounding in the face-free world;
     - D150's RK4 worlds stay the transport's sharp reference;
     - no consumer needs it.

     §4.6 is rewritten so that it no longer implies D150's RK4 runs are unsplit references for its
     operators.
6. **Replacement@1:** compose with the occupant rule, or refuse reaction routes on replaced slots in
   version 1 (§2.1)?
   - *Ruled:* in version 1, refuse cell routes on slots that replacement@1 replaces. Outside routes
     compose. This is a version 1.1 door: no version 1 consumer needs it, and D150's occupant
     mechanism is still being coded.
   - §2.1, §5, §7.1 and §7.2 match, and §7.2 records the combined effect with question 3.
7. **Finding 3:** version 1 refuses reacting species with membrane or junction permeability.
   - *Ruled:* version 1 keeps the refusal. C4 runs on a separate track and does not gate acceptance.
   - *C4's result* is in §10.3.
   - *Ruled (round 2):* a D148 round for @3 is queued for after D150 v1 lands.
     - **What it adds.** The z = 0 material term on junctions and membranes, in `explicit_rate_bound`
       and in the run-time membrane-rate rule. It is statically gated, so a program without a
       neutral permeant species is unchanged.
     - **What it fixes: stability, not accuracy.** On the faces' convention it admits x ≤ 1, so
       C4c's errors of 2.3% and 13% at x = 0.5 and 1 stay admitted, as they are on faces. The round
       does not close the silent window below that bound.
     - **Why it can wait.** Both version 1s refuse such species (D150's inventory species are
       impermeant; this operator refuses permeant reacting species). The existing-worlds sweep
       (§10.3) found no world that declares one.
8. **MG0c's registration:** §6.4's domains, items and tolerances, and the second world.
   - *Ruled:* §6.4's domains and items are the basis, with tolerances pinned at registration from
     the dt study.
   - *Ruled:* the second world (cells with exchange) becomes a separate later item after C5. It is
     not part of MG0c's first acceptance.

**For the user:**

9. MG0c uses Schnakenberg's textbook network as a declared test case, compared with mathematics (the
   dispersion relation and exact discrete solutions), not with any paper's results. Is that within
   D138 as written?
   - *The lead's reading, proceeding unless the user objects:* MG0c is within D138. D152 names MG0c
     as the qualification case, and the plan's row names the dispersion relation. MG0c runs a new
     engine operator on a textbook network and compares it with mathematics.
10. Should reactions on charged species, such as buffering on the pump family, and driven routes
    drawing on finite energy pools come later (§7.3)? *Open for the user.*
11. Should `network_reactions@1`'s kinetic branches eventually be retired, or re-expressed through
    this operator? Not authorised now; recorded only. *Open for the user.*
   - *Answered by the user, 25 November 2026:* they are retired with the legacy cleanup, with
     `network_control_factors@1`, and the tag `pre-cleanup-2026-11-25` keeps both. On the live engine
     their work is `local_species_reactions@1`'s (qualified with MG0c) and
     `species_regulated_availability@1` and `@2`'s, and, not judged yet, the pump of any valence's,
     the symports' and the species condition's. The finite-fuel forms and their regulated kinetics
     have no live replacement.

## 10. Pre-code checks (14 November)

No engine code was added or changed.
- **Evidence:** the scripts, logs and JSON are in the evidence folder's `probe1/`, `probe2/` and
  `probe3/`.
- **Execution:** each probe ran as its own unit through `scripts/run_detached.sh` (`--oom-first`,
  `--wait-headroom`). memory.events were all zero.
- **The prototype probes (2 to 2g, C3, C3b) are development evidence, not references of record**
  (§3.4).

| Probe | Question | Where | Exit, wall time, peak |
| --- | --- | --- | --- |
| 1 (`cells-sir-probe1`) | MG0c's transport world on the engine as it is | Clean snapshot of ac5a251, CPU 7, 3 GB cap | 0, 88 s, 0.95 GB |
| 2 (`cells-sir-probe2`) | The proposed numerics and bookings, and MG0c's dispersion design | NumPy and SciPy only (a prototype in the evidence folder, never under `validation/`), CPU 5, 2 GB cap | 0, 357 s, 49 MB |
| 2b (`cells-sir-probe2b`) | Follow-ups: decaying modes over decay-matched windows; turnover's closed form | As probe 2, CPU 7, 1 GB cap | 0, 8 s, 46 MB |
| 2c (`cells-sir-probe2c`) | After the advisor's review: the stage condition on a passive route running in reverse, and the heat sign near θ | As probe 2, CPU 5, 1 GB cap | 0, under 1 s, 44 MB |
| 2d (`cells-sir-probe2d`) | The lead's blocking item: the mixed-node onset; the stage quadrature against the average-vector-field share | As probe 2, CPU 5, 1 GB cap | 0, 2 s, 46 MB |
| 2e (`cells-sir-probe2e`) | The advisor's final review: the share's sign through an equilibrium crossing; with C3 and C3b rerun (W2's round L) | As probe 2, CPU 5, 1 GB cap | 0, 60 s, 53 MB |
| 2f (`cells-sir-probe2f`) | The per-route hybrid on the onset, crossing and near-equilibrium cases | As probe 2, CPU 5, 1 GB cap | 0, 5 s, 47 MB |
| 2g (`cells-sir-probe2g`) | The advisor's last review: a reversal onset (the hybrid's quadrature branch at a trace); probe 2d's smooth mixed world under the hybrid | As probe 2, CPU 5, 1 GB cap | 0, 2 s, 44 MB |
| C3 (`cells-sir-probe-c3`) | Stiffness relative to the split step, dt · L from 0.25 to 20 | As probe 2, CPU 7, 1 GB cap | 0, 16 s, 49 MB |
| C3b (`cells-sir-probe-c3b`) | C3's nonlinear binding world: its reference and its sub-steps | As probe 2, CPU 5, 1 GB cap | 0, 36 s, 53 MB |
| C4 (`cells-sir-probe-c4`) | Finding 3: a neutral species on a junction or membrane, z around 1 and 2 | Clean snapshot of ac5a251, CPU 7, 3 GB cap | 0, 113 s, 0.63 GB |
| C4b (`cells-sir-probe-c4b`) | C4 at small z, and a mixed variant with ion leaks | As C4 | 0, 153 s, 0.62 GB |
| C4c (`cells-sir-probe-c4c`) | C4 in a world whose shared bound is set by another species' resolved flows | As C4 | 0, 167 s, 0.75 GB |

### 10.1 Probe 1: MG0c's transport world on the engine

**The world:**
- a closed chain of 32 finite outside nodes (1 pL, h = 10 µm) joined by faces;
- two neutral species U (D = 1e-11 m²/s) and V (1e-10 m²/s) at 1 µM, each with a cosine mode of
  1e-2 relative (n = 3 for U, n = 2 for V);
- every ion diffusivity zero and every membrane impermeant;
- one cell with a capacitive patch on every node and one on a held bath;
- no face to a bath;
- species floors of 1e-20 fmol.

| Question | Result |
| --- | --- |
| Parse and host checks at species-set steps | Every host check passed at dt 0.2, 0.1 and 0.05 s. The explicit-rate bound is 4 s⁻¹, so dt ≤ 0.25 s |
| A step above the bound | dt = 0.31 s (1.24 × the bound) was refused: "IMEX step exceeds the explicit-rate stability bound" |
| Zero-flux conservation | Each species' total was constant to 4.3e-16 relative |
| The engine's discrete map | Each mode's amplitude equals the ARS(2,2,2) explicit polynomial (1 − dt μ + (dt μ)²/2)^k to 1.3e-14 at 32 nodes (3.0e-14 at 128), with μ = D (4/h²) sin²(nπ/(2N)) |
| Against the semi-discrete exact decay | V: 3.64e-6, 9.07e-7 and 2.27e-7 (ratios 4.01 and 4.01). U: 1.39e-7, 3.46e-8 and 8.65e-9 (4.00 and 4.00) |
| Mode mixing | Off-mode content at most 9.7e-14 of the initial amplitude: the Neumann cosines are exact eigenvectors on the engine |
| Ions | The ion rows of the cell and outside amounts are bitwise equal to the same world without U and V |
| Energy residual relative to the flows | 1.2e-5, 3.1e-6 and 7.6e-7 at 0.2, 0.1 and 0.05 s: @3's face heat, second order |
| Cost (second run, host checks included) | 2.5, 2.7 and 2.2 ms per step at 32 nodes; 4.1 ms at 128 nodes. The compile takes about 15 s |

These hold for the CPU programs probed (D150 §1.2's caveat on reduce order).

### 10.2 Probes 2, 2b and 2c: the prototype

**The prototype** implements the proposed half-step (§4.2), Strang composition with @3's species
transport as the ARS(2,2,2) polynomial that probe 1 verified, and the bookings of §3.3. It imports no
Cells code.

| Part | Result |
| --- | --- |
| A, the dispersion design | §6.3–§6.4: every Turing condition holds; d_c = 8.568; the band is 0.2 < k̃² < 0.5; the one-mode domains L/ℓ = 6, 11 and 16 and the no-mode domain 8; the staircase |
| B1 and B1b, mode propagation on L/ℓ = 11 | Against expm of each mode's 2×2 discrete system: mode 1 (complex pair, −0.0548 ± 0.0443i s⁻¹), 3.2e-5, 8.0e-6 and 2.0e-6 (ratios 4.00 and 4.02); mode 2 (+5.71e-3 s⁻¹), 4.5e-4, 1.13e-4 and 2.8e-5 (4.01 and 4.00); mode 3 (−0.0146 s⁻¹), 1.25e-3, 3.1e-4 and 7.8e-5 (4.04 and 3.98); mode 4 (−0.0607 s⁻¹), 5.6e-4, 1.37e-4 and 3.4e-5 (4.07 and 4.03). B1's first windows for modes 1 and 4 had reached the rounding floor, so B1b measured them again over 3/|Re λ| |
| B2, the nonlinear pattern against SciPy | L/ℓ = 11: 4.8e-4, 1.19e-4 and 2.97e-5 of c* (4.02 and 4.01), dominant mode 2, amplitude 0.68 u0 (reference 0.679), the range (max u − min u)/u* at 1500 s (§11.4). L/ℓ = 6: 4.8e-4 to 3.0e-5 (4.01 and 4.01), mode 1. L/ℓ = 8: the deviation fell to 1.4e-8 of u0, no pattern. Largest h_sub L: 0.0076. No step refused |
| B4, passive linear reaction–diffusion | §6.2: ratios 4.02 and 4.01; equilibrium 10.000; smallest half-step heat −1.1e-18 pJ, rounding against the −1e-12 pJ check |
| B5, switch-on from a trace | Quadrature against exact ΔG in the first step: 27%, 11% and 0.07% at traces of 1e-12, 1e-9 and 1e-6 mM; below 1e-4 from the second step |
| B6, a mixed node | The first draft's stage quadrature, since replaced at mixed nodes by the per-route hybrid (§3.3), against a SciPy dissipation integral: 2.0e-5, 2.35e-6 and 2.85e-7 (ratios 8.50 and 8.26); never negative; W − H − ΔG at most 2.7e-20 pJ. The hybrid's order there is the share's, 3.70 and 3.87 (probes 2d and 2g) |
| B7, the standard-potential term | §3.3: with it every heat ≥ 5.4e-5 pJ; without it −1.3e-6 pJ from the first step, down to −2.4e-5 pJ |
| B8, the stage condition near depletion | §4.2's table |
| B9, turnover's closed form | 1.25e-6, 1.53e-7 and 1.89e-8 (8.19 and 8.10) |
| 2c, the corrected stage condition | A ⇌ B with K = 10, started at c_B/c_A = 1e4 so that it runs in reverse. Over h (k_f + k_r) from 0.05 to 3, the signed form read 0 below 1.1 and admitted steps up to 1.5. There the deviation shrinks by R = 0.0625 against an exact 0.223. The corrected form admitted up to 0.55 and refused from 0.9. The one negative stage, at 3, was refused under both. Every admitted step's heat was positive, at least 1.1e-11 pJ near equilibrium |

**The correction this changes** (§4.2). Probe 2's own stage check used the signed net rate for
passive routes. Its passive cases ran forward at small h k, so their results stand, but they do not
test the condition. Probe 2c does.

**What the probes did not test:** the operator itself on the engine, which does not exist yet; JAX
and GPU behaviour; the composite's contract plumbing for this operator. C1 covers the last.

### 10.3 After the lead's review: 2d, C3 and C4

**Probe 2d, the mixed-node onset** (blocking; prototype). See §3.3 for the world and the tables.
- **The first draft's stage quadrature** overbooks a passive switch-on from a 1e-12 mM trace by 34–54%
  in the first step, and by 1.3–6.1% of the whole heat at 5 s. W carries the same absolute error,
  and the closure stays exact, so no guard sees it.
- **The average-vector-field share** is within 0.06–0.33% in the first step, and within
  0.005–0.063% at 5 s, which is second order.
- **Trace sensitivity.** Across a 10³ change of a negligible trace the share moves with the true
  heat: −6.32e-5 against −6.27e-5, where the quadrature moves −1.66e-2.
- **Sign and closure.** No step heat was negative in 2d's cases. The closure was at most 2e-18 pJ.

**Probe 2e, the share's sign through a crossing** (the advisor's final review; prototype). See §3.3
for the table.
- **The failure.** Where a driven sink carries a passive A ⇌ B across its equilibrium within a
  half-step, the share is negative and misses nearly all of the step's true heat.
- **How large.** It scales with the amount, and roughly as (h L)⁵. It would cross the dissipation
  check's −1e-12 pJ above about 4e-3 fmol at h L = 0.05, and at far smaller amounts at coarser
  steps.
- **What the quadrature does there.** It stays positive, but overbooks the crossing step by 6–8% at
  h L = 0.05 and up to about 2× at 0.5.

**Probe 2f, the per-route hybrid.**
- **At the onset** it equals the share, since no route reversed: 0.06–0.33% in the first step, and
  the true heat's trace dependence.
- **At the crossings** no step heat was negative, and the quadrature carried the reversing steps.
- **Near equilibrium** no step heat was negative either: smallest 6.7e-16, 7.5e-12 and 2.3e-9 pJ at
  k_cat 1e-3, 0.1 and 1 s⁻¹.
- **Recommendation, adopted in §3.3:** the per-route hybrid.

**Probe 2g, the reversal onset** (the advisor's last review; §3.3's known limit).
- **The case.** A driven source lifts a trace species across a passive equilibrium within the first
  half-step. The route reverses, the hybrid sends it to the quadrature, and the quadrature samples
  the log-singular start.
- **The size.** The step books 5.4–5.6 times its true heat at a 1e-12 trace (+436% to +459%),
  trace-dependently: −1.3e-3 of the whole heat for a 10³ change of the trace, against the true
  −1.4e-7 (relative changes, §11). In this one
  world the whole heat at 1 s was off by 0.27–0.56%.
- **When it vanishes.** At a step fine enough that the crossing falls after the first step.
- **How it is recorded.** As a known limit under the resolved-start rule: option (a), ruled by the
  lead (§9 question 2). It applies at any half-step in which a driven route carries a trace
  species across a passive equilibrium, a mid-run switch-on included.
- **The smooth mixed world under the hybrid** took no step on the quadrature, so its order is the
  share's: 3.70 and 3.87.

**Probe C3, stiffness relative to the split step** (prototype; §4.3).
- **The result.** All three worlds hold second order to dt · L of about 2 and fall toward first
  order beyond.
- **The W2 correction.** The first run's W2 (nonlinear binding) looked irregular. The advisor found
  an end-time artefact: L = 59.82 did not divide T. With L = 60 its orders are 1.99, 1.98, 1.83,
  1.43, 1.09 and 1.04 (C3 and C3b rerun; the first run's files are kept).
- **The rule:** version 1 refuses dt · L > 1 at run time, with one sub-step and no declared count.

**Probe C4, finding 3 on the engine as it is** (separate track; it does not gate acceptance).
- **The worlds.** A neutral species X on a junction between two 1 pL cells, or on a membrane patch
  between a 1 pL cell and a 1,000 pL node. The parameter is z = dt P A/V. The exact per-step
  relaxation exponent of the concentration difference is x: 2z on the junction, about z on the
  membrane.
- **What the polynomial does.** For @3's explicit ARS(2,2,2) map the difference evolves by
  g = 1 − x + x²/2 per step. On every accepted row of C4b and C4c the engine's junction and membrane
  maps equal g^k to at most 8.8e-16 relative. g never changes sign, so the signature is slow decay for
  x up to 2 and growth beyond, not oscillation.

| What | Result |
| --- | --- |
| The definition | Never refuses: `explicit_rate_bound` is 0 in these worlds (no faces, impermeant ions), and the step checks pass at every z |
| The run-time membrane-rate rule | dt × `membrane_rate` = 0 at every z: it is z²-weighted and cannot see X |
| Species-only worlds, the host ledgers (C4, C4b) | Every run passes up to x = 0.04 (junction) and 0.05 (membrane), with errors against the exact relaxation of at most 1.0e-4 and 1.6e-4 of the initial difference. From x = 0.1 a host ledger refuses at row 1: the energy ledger, or the outside material ledger at x ≈ 2 on the membrane. The membrane was probed to x = 3. The junction at x = 4 was refused first by the step's own validity flag at step 1 |
| Positivity | For x > 2 the difference grows (g > 1) until the domain refuses: step 6 at x = 2.2 (junction) and step 8 at x = 3 (membrane) |
| A world whose shared bound is set by other flows (C4c: a second neutral species on a face, started smooth; about 26 pJ/s of face heat by design, **S**) | **Passes silently up to x = 1.** Every host check passes, with errors of 6.6e-4, 2.3e-2 and 1.3e-1 of the initial difference at x = 0.1, 0.5 and 1.0 (junction and membrane alike, over 30 steps). From x = 1.5 the energy ledger refuses at row 1; on the membrane at x = 3, the dissipation check |
| The mixed variant with ion leaks (C4b) | Uninformative: the ions' own leak onset (dt × membrane_rate 0.56 and 0.28) failed the energy ledger at row 1 at every z |

- **So the gap is real.** It is loud in species-only worlds, where the energy ledger is at the
  species' scale. It is silent wherever other flows set the shared bound, up to x of about 1: the
  decay is too slow and nothing refuses. That is D150's blindness, applied to transport.
- **The ruling stands:** version 1 keeps its refusal of reacting species with membrane or junction
  permeability.
- **The queued D148 round** (§9 question 7) adds the z = 0 material term to `explicit_rate_bound`
  and to the run-time membrane-rate rule, statically gated.
  - It fixes stability, not accuracy. On the faces' convention it admits x ≤ 1, so C4c's errors of
    2.3% and 13% at x = 0.5 and 1 stay admitted, as on faces.
  - It does not close the silent window below the bound.

**The existing-worlds sweep for that round** (the lead's ruling; read-only, 14 November; evidence in
`sweep/SWEEP_SUMMARY.md`).
- **The numerics in question.** `explicit_rate_bound` and the z²-weighted membrane-rate rule belong
  to the IMEX pump family alone:
  - resolved_pump_tissue@1, @2 and @3;
  - resolved_pump_water@1/@2 and resolved_pump_replacement@1;
  - resolved_pump_composite@1, whose water, replacement@2 and insertion operators read the bound on
    their own projections;
  - projective mode on @1 to @3.

  The membrane-rate rule is @3's, so it reaches every @3-based composition. Every other tissue
  family is RK4-only, since `surface_tissue_spec` refuses any other solver, so neither check applies
  to it.
- **The worlds.** No world declares a z = 0 species with a nonzero membrane, junction or channel
  permeability.
  - **JSON**, every file in the checkout (configs, validation protocols and caller documents, test
    fixtures). 125 model blocks hold a neutral species, all `compartment_reactions@1` or
    `er_calcium@1`, and none of them is permeant.
  - **Permeability maps.** The IP3 keys (the calcium family's store chemistry, RK4) are zero
    everywhere. Every other nonzero key outside Na, K, Cl, Ca, H, P and M is charged.
  - **The pump-family Python builders.** Heredity, E07, MG0b, stationary, projective, egg and
    division, injection and water all use charged species only.
  - **The parity worlds** use one BETSE ion set (Na, K, Cl, Ca, P, M), all charged.
  - **Channels.** @3's parser refuses a channel ion that is not its law's ion at the law's valence,
    so a channel cannot carry a neutral species.
  - **Probe worlds.** Only this note's C4 probe worlds declare a neutral permeant species, on
    purpose.
- **So no registered or qualified result can carry the silent error.** The gap is latent: it would
  apply to a future definition with a neutral permeant species, which both version 1s refuse.

### 10.4 Still to come

- **C1, the contract fit: the code branch's first milestone** (re-specified by the lead's ruling).
  - **Why not a probe.** As first written, C1 was an operator class registered in-process from the
    evidence folder. That would be a parallel implementation under `/mnt/workspaces`, which
    AGENTS.md forbids.
  - **Where it lives instead.** It is the first milestone of the code branch, in the checkout and
    behind its guards.
  - **What it must show:**
    - the field map (one owner per row);
    - every host ledger at the species' floors;
    - the face-free energy world at rounding, and the negative controls;
    - zero multipliers bitwise idle;
    - restart and a vmap batch.
  - **When.** After D150 v1 lands, since it uses D150's adapter addition and helper.
- **C2, the mixed-world blindness of these bookings.** D150's probe 2 part C method, in a heredity
  world with a reacting pair at µM and nM: the bound/booking ratio for the docstring statement. C4c's
  masking result shows the same mechanism for transport.
- **C5, the composition world.** The network in cells with D150's exchange and faces, against the
  three-compartment linear stability analysis (NumPy). It needs D150 v1, and precedes the later
  item that §6.4's second world becomes.

## 11. Amendments at milestone 1 (the lead, 14 November 2026)

Version 1's first milestone is the contract fit, C1 of §10.4 (branch commits 04499a8 and 8e6438d;
the design-to-code checklist and the runs in
`/mnt/workspaces/Cells/shared-inventory-reactions-v1-20261114-01/HANDOFF.md`). The lead accepted it
and ruled on its readings as follows. Each ruling is the lead's, 14 November 2026, at milestone 1.

1. **The milestone-1 half-step (Q1).** Until milestone 2 the half-step selects its start state when
   every multiplier is zero and refuses any step with a positive multiplier, through the half-step's
   validity (not `control_valid`). Accepted as a temporary state.
2. **Identity keys (Q2).** D150's `catalogue` and `evidence` (`species_common.parse_species`), not
   `reference`. §2.1's example is amended to match.
3. **Read-only species (Q3).** Accepted for version 1: catalysts and factor species are listed, and
   so are neutral and impermeant. A version 1.1 door is recorded in §7.3: factors and catalysts that
   read charged or permeant species (calcium-regulated production, say). Reads book nothing, so they
   need only a read-only species list. E15's coupling from bioelectric to chemical signalling is its
   likely consumer.
4. **A reaction that changes no species is refused (Q4)**, as a typo guard (§3.1's spirit), beside
   §2.5's list.
5. **No defaults (Q5).** Every key is explicit. `moieties: null` is the species as its own moiety,
   and `standard_mu_RT` is required.
6. **Schedules (Q6).** A route takes its site's schedule, else its reaction's (site null). Every
   schedule starts at time 0. A reaction-level schedule that applies to no site is refused.
7. **Sites (Q7).** `"all"` is every cell, or every finite outside node, never a held bath. Routes are
   ordered cells, then outside nodes, each in declared order (model order for `"all"`).
8. **Parameter names (Q8).**
   - `rate_constant` stays for mass action, whose order sets its units (k in mM^(1−q) s⁻¹), as
     D150's "rate" does.
   - Michaelis–Menten does not flip one key's meaning on its catalyst:
     - `catalytic_rate_per_s` (k_cat) when a catalyst is declared;
     - `max_rate_mM_per_s` (V_max) when none is;
     - the other case's key is refused, with the reason.
   - `saturation_mM`, `forward_rate_per_s`, `half_saturation_mM` and `hill_coefficient` stand.
   - One internal rate array (`reaction_rate_constant`) is fine. The summary reports each route's
     parameters under their law-specific names and units.
9. **The consumed species absent from its law's rate (Q9)** is unreachable by construction, tested
   through the Michaelis–Menten refusals. Accepted.
10. **The domain (Q10)** also refuses the operator's accumulators off its species rows, on padded
    slots and at held baths, and a negative extent on a driven route. Accepted.
11. **The layout (Q11): accepted, with three conditions.** Structure as bound layout arrays (law
    codes, stoichiometry, catalysts, factor kinds), kept apart by the batch signature; per-reaction
    parameters repeated per route; one internal rate array; a dense route × factor array with kind 0
    as padding. This matches D150's practice and keeps programs stable, with per-world values as
    bindings.
    - (a) **Benign padding.** Every unused law branch and padded entry stays finite, with positive
      padding for K_M, K, c0 and amounts. A compiled test with every law and factor kind present,
      plus padding, checks that no intermediate or output is NaN or infinite.
    - (b) **The bindings check.** As D150's crossrev driver: two worlds with different network
      parameters and multipliers but the same structure give identical jaxpr text and constants;
      only the bound arrays differ.
    - (c) **The batch signature** refuses two different structures in one batch (stoichiometry, law
      kinds or factor species), with a test.
12. **Where rulings go (Q12):** dated amendments in this note, as D150's §12 does. This section.

**Corrections found by the references' agent** (the coordinator, 14 November 2026, at milestone 2;
amended in place where marked):
1. **Units of the trace sensitivity.** The figures in §3.3's trace-sensitivity table, §3.4 guard 5
   and probe 2g's −1.3e-3 and −1.4e-7 are relative changes of the whole heat, not pJ.
2. **k̃² at σ_max** is 0.318545, which rounds to 0.3185, not 0.3186 (§6.4).
3. **RT.** Appendix A's 2.5773 pJ/fmol uses R = 8.314; SI R at 310 K gives 2.5775. The engine's R
   and T apply, and the references take RT as an input.
4. **Q4's sweep** (§6.4). The 4.5–30 sweep contains only the 7.5–8.5 gap, not "both gaps". The
   ruling: the sweep runs from L/ℓ = 4 to 30, so it includes the no-mode point at 4, judged
   against the discrete argmax of σ_n. The discrete argmax differs from the continuum's at
   L/ℓ = 30.5 (mode 6 against 5).

**Added to milestone 2** (beyond §10.4 and the plan): the ledger and magnitude terms compiled, not
only on the host; a test of the summary; the full energy-guard statement in the docstring, with C2's
measured ratio; the idle tests re-run against the live half-step; tier 1 and tier 2 from the clean
head before hand-back; the independent references only through
`validation/reactions/REFERENCES_USAGE.md`, once it is on main.

### 11.1 Milestone 2: the half-step and its guards, as built and run (14 November 2026)

The code is on the branch from aaf2f67, the amendments and ruling Q8, through 2b31f88, the
half-step, and the merge of main with the independent references (0f88501). The evidence is in
`/mnt/workspaces/Cells/shared-inventory-reactions-v1-20261114-01/`: HANDOFF.md, `tests/`,
`crossrev/`, `tiers/`. The records in the tables come from the clean head 5de1c96 (the source at
6ab0cb0 plus the tier record), and its snapshot `snapshot-5de1c96`.
- **Negative controls** are edits of saved histories, judged by the face-free world's residual
  against its rounding allowance, not misbookings inside the compiled program.
- **The references** (`validation/reactions`) were used only through `REFERENCES_USAGE.md`.

| Guard | Result | Where |
| --- | --- | --- |
| The per-law ΔG test of record (§3.4 guard 4): the half-step against `nr.half_step` on random states | 4 world variants × 60 trials (every law, mass action of orders 0 to 3, a coefficient of 2, Michaelis–Menten with and without its catalyst, both factor kinds, cells and outside nodes of 0.7 and 1.9 pL, c0 = 0.4 mM): 174 admitted and 57 refused half-steps, every node class, 92 share and 28 quadrature branches. Every comparison within the usage note's tolerances | `test_species_reactions_against_references.py` |
| Whole compiled face-free runs against `nr.run_half_steps` | The amounts, extents, heat, work and standard term at every row agree to 7e-15 of their scales or better (the share onsets, crossings, class switch, reversal onset at the start and mid-run, a 400-step relaxation); the relaxation ends at `dr.passive_equilibrium`'s state, its heat its free-energy drop to 1e-15 | `test_species_reactions_reference_runs.py` |
| The face-free energy world (§3.4 guard 1): the residual over 2.5 ε × steps × the energy magnitudes at every row | At most 0.26 (driven only), 0.066 (passive relaxation), 0.04–0.15 (the share's onsets), 0.10–0.35 (the quadrature's crossings), 0.071 (the class switch), 0.19 and 0.11 (the reversal onset at the start and mid-run) | `test_species_reactions_guards.py` |
| Negative controls (§3.4 guard 3) | Each fails the face-free world at row 1, its first touched row: scaled work 6.0e8 × the allowance, a dropped standard term 6.7e12 ×, a wrong-sign heat 4.0e13 × (and the dissipation check) | guards |
| C2 (§10.4): the shared bound over the booking \|W − H\| in the mixed heredity chain | 0.35 at µM and 409 at nM (the docstring's statement, tied to the test). A 1e-6 relative work error is unseen at both, and a wrong-sign heat is refused at both by the dissipation check | guards |
| Benign padding (ruling Q11 (a)) | With every law, both factor kinds, and padded cell, outside and factor slots, no intermediate is NaN or infinite: NumPy raising on divide, invalid and overflow, and eager JAX under `jax_debug_nans` and `jax_debug_infs`. The jitted outputs are finite. A planted zero padding (a factor's K) raises in both | `test_species_reactions_halfstep.py`, `_runs.py` |
| The bindings (ruling Q11 (b)) | The operator's own crossrev set (eight worlds, its first record): both value twins (every parameter, potential, c0 and multiplier changed) are identical in jaxpr text and constants, only the parameter layout arrays and the multiplier controls differ, and no bound row equals a closed-over constant (c0 included) | `crossrev/reactions/5de1c96` |
| The batch signature (ruling Q11 (c)) | Another stoichiometry, law kind or factor species is refused in one batch; other parameters, potentials, c0 and multipliers are admitted | `_refusals.py` |
| Idle (§4.5) against the live half-step | Zero multipliers and no routes: every field, observation and diagnostic bitwise the composition's without the operator. An idle node beside an active one, and a catalyst's row at an active node, keep their planted −0.0 | `_runs.py`, smoke |
| Restart and vmap (§6.5) | Restart at 10, 20, 25, 30 and 40 ms around a multiplier change, in process and through a snapshot loaded in a fresh process: bitwise. A vector batch of three worlds mixing every parameter and multiplier: bitwise against its reverse, within 1e-12 of each scalar run, its device energy diagnostics equal to the host's to the terms' rounding. The device row checks refuse a misbooked accumulator (local), work (energy) and heat sign (dissipation) | `_runs.py` |
| Crossrev of record (snapshot-5de1c96: 2,945 files, empty patch; the tools unchanged) | Against the baseline of record: base 36/36 texts, 36/36 constants, 12/12 bindings; qualification 78/78, 78/78, 56/56; injection 6/6, 6/6, 2/2; volume 6/6, 6/6, 2/2; division 27/27, 27/27, 9/9 with its check holding: identical. D150's species set against its record at 17d00b4: 24/24, 24/24, 8/8, its check holding: identical | `crossrev/` |
| Tiers | Tier 1 is 312 files: `_halfstep.py` and `_against_references.py` join. Tier 2 is 82. Tier 3 is 218: `_runs.py` moves there from tier 2, beside `_guards.py` and `_reference_runs.py` | `tests/test_tiers.json` |
| Gates | Tier 1 + 2 from the clean head 5de1c96 (dirty 0): 394 files, no changed outcome against the record. The three tier-3 files, also from that head, all passed: `_runs.py` 6, `_guards.py` 14 and `_reference_runs.py` 18 | `tiers/gate12-5de1c96`, `tests/final-5de1c96-*` |
| The stage condition, positivity | Compiled: dt L = 0.98 admitted, 1.02 refused with the start state bitwise, always tested either side of the bound. A passive route in reverse is read on its reverse flux. 200 compiled steps at dt L = 0.99 from 1e-15 mM traces: all accepted and positive, the cleared amounts stalling at about ε × their anchors | `_halfstep.py`, `_runs.py`, guards |

**The scheme's accuracy, beside the note's figures** (the reference's half-steps equal the engine's
to rounding, above, so these are the engine's; the pins are proposals for the lead):

| Item | Engine against the true kinetics (`dr.integrate_node`) | The note's figure (the prototype's) | Proposed pin |
| --- | --- | --- | --- |
| The share's onset (probe 2d), the first half-step's heat at h = 0.05, 0.025 and 0.0125 s | 1e-12 mM: +0.332%, +0.137%, +0.059%. 1e-9: +0.331%, +0.136%, +0.058%. 1e-6: +0.212%, +0.067%, +0.020% | +0.33/0.14/0.06%; +0.21/0.07/0.02% | ≤ 0.5% at h ≤ 0.05 s |
| The share's onset, the whole heat at 5 s | 1e-12 and 1e-9: +0.063%, +0.018%, +0.0051%. 1e-6: +0.045%, +0.012%, +0.0030% | +0.063/0.018/0.005%; +0.045/0.012/0.003% | ≤ 0.1% at h ≤ 0.05 s, second order |
| W at 5 s (W carries H's absolute error) | 1e-12: 0.035%, 0.010%, 0.0029% of \|W\| | 0.035/0.010/0.003% | as H |
| The background guard (§3.4 guard 5; h = 0.025 s, 5 s): the whole heat's relative change for a trace of 1e-12 → 1e-9 mM | Engine −6.324e-5, true −6.273e-5 (a difference of 5.1e-7). Work: +3.62e-5 against +3.65e-5 | −6.32e-5 against −6.27e-5 | \|engine − true\| ≤ 2e-6 of the whole heat and work |
| The crossing's quadrature (probe 2e, offset 0.01 above the equilibrium) | +6.9% (k_d = 1, h L = 0.05), +7.6% (k_d = 1, h L = 0.1), +10.3% (k_d = 10, h L = 0.275); never negative | +7.9% at h L = 0.05 to +127% at 0.5, at the sweep's crossing | 0 ≤ error ≤ probe 2f's figure at that h L |
| The reversal onset (probe 2g, the known limit), the booked first half-step over its true heat | 1e-12 mM: 5.59 and 5.36 (h = 0.025 and 0.0125 s). 1e-9: 3.67 and 3.43. 1e-6: 1.80 and 1.59 | 5.4–5.6, 3.4–3.7, 1.6–1.8 | documented, not judged (option (a)) |

**Findings for the lead:**
1. **§3.4 guard 3 holds at nM only.** In C2's chain at µM the shared bound (0.35 of the booking)
   sees an error of a booking's size: the dropped standard term, 0.76 of the booking, is refused
   by the energy ledger. The note expected the bound to be blind to it. At nM it is unseen (bound
   432 × the term). The docstring's statement now says so.
2. **"Reproduces it exactly" (§3.3) holds for the half-step, not for two compiled runs.** At a
   mid-run switch-on the whole state is bitwise the start state, and the half-step at the same
   (state, multipliers, h) is bitwise. The runner's step at 50 ms, however, is a difference of grid
   times: 3 dt − 2 dt = 0.02500000000000001 s on the float grid (`EventGrid`'s k × dt), against
   the first step's 0.025 s. So the two runs' first active steps agree to rounding (8.5e-21 pJ),
   not bitwise. This is a property of the runner's clock, not of the operator. No change is
   proposed (D148).
3. **The standard term** is booked in species form, Σ_s μ°'_s δ_s; the references book it in route
   form, Σ_r ΔG°'_r Δξ_r. They agree to rounding (the per-law test compares them at 1e-12 of the
   terms). A reading, recorded.

**Changes from milestone 1:**
- The domain no longer requires heat ≥ 0 exactly. A passive-only node's −ΔG can be −1e-18 pJ by
  rounding, and the composite's dissipation check judges it (at −1e-12 pJ).
- The readout columns `reaction_rate_fmol_per_s` and `reaction_affinity_RT`.
- `STEP_ID` is `ssprk33_unidirectional_stage_condition_exact_bookings@1`.
- `stage_report` diagnoses a refused step on the host, since the runner's message is generic. No
  runner edit is proposed.
- The docstring carries the full guard statement, with C2's ratios.

### 11.2 Rulings at milestone 2 (the lead, 14 November 2026)

Milestone 2 was accepted and landed (merge a4e2f7e). The lead ruled on its questions as follows,
14 November 2026.
1. **§3.4 guard 3, amended in place.** The shared bound catches a dropped standard term at µM
   (0.35 times the booking) and is blind at nM (409 times). The face-free world at rounding and the
   per-law ΔG test remain the guards of record.
2. **§3.3, amended in place.** The half-step is bitwise at the same state, multipliers and step.
   Two compiled runs around a mid-run switch-on agree to rounding (8.5e-21 pJ), not bitwise,
   because the runner's clock forms the step as a difference of grid times. That is the runner, not
   the operator.
3. **The standard term's form, noted.** The engine books it in species form, Σ_s μ°'_s δ_s, and
   the references in route form, Σ_r ΔG°'_r Δξ_r. The two agree to rounding.
4. **`stage_report` is enough for version 1.** There is no D148 round for the runner's refusal
   message.
5. **The accuracy pins in §11.1 stay proposals,** and the tests keep their loose bounds. The lead
   rules on them in the MG0c protocol review.

**Milestone 3** adds, beside MG0c's driver, development runs and PROPOSED protocol, the items moved
from milestone 2:
- §3.4 guard 2, the species-only transport world with the network, its residual over the bound,
  and the reaction–transport check against `strang_mode_map`;
- a short compiled run of the composition with another writer: exchange, turnover on a read row,
  and replacement@1 with outside routes;
- idle claim 3, reported: the ion rows bitwise with the network active;
- reactions at several sites with different multipliers.

### 11.3 Milestone 3: MG0c's driver, development runs and the moved items (14 November 2026)

Milestone 3 adds no engine code: `src/` is unchanged since the landed head a4e2f7e.
- **Engine models run:** `resolved_pump_composite@1` over `resolved_pump_tissue@3` with
  `local_species_reactions@1` (driven mass action; the passive law in guard 2's passive world).
- **References:** `validation/reactions`, used only through `REFERENCES_USAGE.md`, fed the raw
  declaration; every prediction computed at run time.
- **Evidence:** `/mnt/workspaces/Cells/shared-inventory-reactions-v1-20261114-01/` (HANDOFF.md,
  `mg0c/`, `tests/`, `tiers/`). The development runs come from `snapshot-d4cee87` (dev-d4cee87-a,
  -b and -c) and `snapshot-3e7399a` (the D147 part and the tier-3 files).

**The code** (after the merge d5738a1):
- `validation/morphogenesis/mg0c_turing.py`, MG0c's driver.
  - Its own closed chain, from §6.4 and the usage note's convention: h = ℓ/2, face area V/h,
    length h, quiescent ions, U and V through `cells.registry.inventory_species`.
  - Runs go through `run_windowed` with every host check. The energy residual is reported over the
    composite's own bound.
  - Deviations are (anchor − reference) + increment, carrying none of the representation's
    rounding.
  - The rules take D150's reviewed forms: S5's dt-study rule per element and record, the orders
    and their stop rules, and judged controls with registered deltas.
  - The parts: d147, timing, theory, linear (guard 2), floor, q1 to q7, sites.
  - A judged run is refused unless the protocol is registered, the source is a clean snapshot and
    the output directory is new. A judge entry merges the judged runs of one snapshot.
- `validation/morphogenesis/mg0c_protocol.py` drafts the PROPOSED protocol
  `validation/morphogenesis/protocols/mg0c_turing_v1.json` from the named development runs.
- The tests:
  - `tests/unit/test_mg0c_judged_refusal.py` (tier 1);
  - `tests/unit/test_species_reactions_composition.py` (tier 3);
  - a several-sites test in `test_species_reactions_reference_runs.py` (tier 3);
  - `rfx.several_sites` and `rfx.reference_multipliers`.

**Where the moved items are.** The figures in this table and in the coordinator's additions
below come from the tier-3 files' run from `snapshot-3e7399a`, `tests/m3-3e7399a`:
`_composition.py` 8 passed and `_reference_runs.py` 19 passed. The checkout's development checks
gave the same values.

| Item | Where | Development result |
| --- | --- | --- |
| §3.4 guard 2, the species-only transport world with the network | the driver's `linear` part (100 s; 50, 25, 12.5 ms); `_composition.py` (10 s) | The engine equals `strang_mode_map` iterated at 0.008–0.021 of the usage note's 1e-14 × steps × scale. Against D150's steps × ε rule it is 0.36–0.96, and long double shows that rounding to be the engine's own, accumulating linearly. Second order against `propagate_modes`: 6.6e-9 → 4.1e-10 of the scale, ratios 4.07/4.03. The energy residual is 6e-5 to 1.5e-3 of its bound |
| A compiled composition with other writers | `_composition.py` | D150's exchange, turnover on a read row (the catalyst at ecs_0) and replacement@1 with outside routes. Every host check passes at the species' floors, every writer moves something, and the event fires |
| Idle claim 3, reported | `_composition.py` | With the network active, and with U and V declared without it, every ion row and every field U and V do not enter is bitwise. Only `face_dissipated_energy_pJ` differs |
| Several sites with different multipliers | exactly: `_reference_runs.py` (`rfx.several_sites`); on the chain: the driver's `sites` part | Exact: two cells and three nodes of unequal volumes, one site at zero and one schedule changed mid-run, against `nr.run_half_steps` with [R, N] multipliers. Amounts agree to 8.9e-16, energies to 2.5e-16 and extents to 1.5e-15. On the chain, against `integrate_chain` with [R, N] multipliers: 1.5e-5 → 9.4e-7, ratios 4.06/4.03 |

**The coordinator's additions** (an external architecture review, confirmed by the advisor), in
`_composition.py`:
- **Transport and reactions see the same material.** A face-free composition of D150's
  first-order export and the reactions equals the composed map E R I R E at rounding: 3.9e-15 of
  the scale, while the other order is more than 1e3 times farther off. The composition converges
  at second order to the coupled exact solution (5.4e-5 → 1.35e-5). Guard 2 shows the same for
  @3's faces.
- **Supply is counted once across writers.** Each species' inventory against its writers' sources
  closes at every row to 1e-16 of its scale, with each writer's term present. At ecs_0, S's
  delivery, consumption and face outflow close to 4e-18.
- **Restart and batching preserve the results.** Restart is bitwise around the event and through a
  fresh-process snapshot. The batch is bitwise against its reverse and equal to the scalar runs.
- **A rejected step restores every field bitwise,** the exchange's, turnover's, replacement's and
  network's accumulators included.
- **D147 solver check, done before the draft.** Every MG0c world has zero free field offsets, with
  @2 declared:
  - 60 worlds in the driver's `d147` part (`snapshot-3e7399a`);
  - 61 in the first check from `snapshot-d4cee87`, which also covered the composition test's world
    (`mg0c/d147/`).

  The zero is not vacuous: the composite layout carries the leaf. Every chain node shares the
  cell's capacitor component with the held bath, so the chain has no floating component even
  without a face to the bath. D147's automatic choice would also keep @2.
- **Not MG0c's:** local accuracy at a consumer's concentrations belongs to the coupling
  milestone's protocol.
- **Kept as guards of record:** the independent kinetic and dissipation comparisons, with their
  trace-scale limits.

**MG0c's development runs:**

| Item | Result | Against |
| --- | --- | --- |
| Theory | d_c 8.5676, band (0.2, 0.5), k̃² 0.318545, σ_max 0.057191 (e-fold 174.9 s, wavelength 111 µm). The domain table and the staircase are as §6.4, the discrete argmax equal to the continuum's at every L/ℓ from 4 to 30. The declaration equals `tu.schnakenberg_network` | `tu` |
| Floor (the linearised map against the start) | At L/ℓ = 11, n = 2, rounding falls as about 1/a and the quadratic term rises as a² (the minimum, 8.5e-11, at 1e-6). At the 1e-7 start: 2.4e-10 (n = 2) and 8.8e-9 (n = 5, which decays by its record) | `cr.strang_mode_map` with K = kJ |
| Q1 | Linearised map: 5e-11 to 1.3e-7. Exact: 3.3e-6 to 2.35e-3 at 50 ms and 2.1e-7 to 1.45e-4 at 12.5 ms, ratios 3.98–4.55 (fast modes on L/ℓ = 6 show orders up to 2.2). The dt rule is 0.44–0.46, no element exceeding. Controls caught k at 5e-8 to 2e-2 and D_V at 2e-7 to 1e-1 | `cr.mode_propagator` |
| Q2 | Slowest mode 2, its fitted rate within 1.0e-8 of the engine order's. The deviation falls from 9.3e-4 to 1.6e-8 of c* (the prototype's 1.4e-8), never above its start | `cr.strang_mode_map` |
| Q3 | Dominant modes 1, 2 and 3 on L/ℓ = 6, 11 and 16, from 50, 50 and 350 s to saturation (0.42–0.43 c*). Fitted rates within 1.7e-5, 4.1e-5 and 2.8e-6 of the discrete-time rates (σ_n is 4e-4 above them) | `tu`, `cr` |
| Q4 | The staircase covers every L/ℓ from 4 to 30 in steps of 0.5: 53 lengths and 163 single-mode starts of 100 s. At every length the engine's fastest-growing start is the discrete argmax of σ_n, and its growing set is the admissible unstable set (none at 4 and 7.5–8.5, then modes 1 to 5). The smallest predicted |rate| among the candidates is 3.8e-5 /s, and the smallest top-two gap is 3.2e-4 /s. The fitted rates match the predicted ones to a median of 3e-9. The worst, up to 6%, are strongly decaying modes near k̃² = 0.1: there the two eigenvalues are close, so the transient outlasts the fit window. None of them is near the argmax or a change of sign | `tu.staircase` (discrete) |
| Q5 | Every one of the 24 modes on L/ℓ = 6, 8, 11 and 16 decays at d = 8. The dt rule against the exact propagator at d = 8 is 0.44–0.47 (6.4e-6 to 1.2e-3 at 50 ms). Fitted rates are within 5e-10 to 6e-7 of the predicted ones, except the complex-eigenvalue modes (L/ℓ = 8, 11 and 16 at n = 1, and 16 at n = 2), whose oscillating norm fits 3e-3 to 0.40 off. Those rates are reported only | `cr.mode_propagator` at d = 8 |
| Q6 | 5.4e-4, 1.4e-4 and 3.4e-5 of c* at 50, 25 and 12.5 ms over 3000 s (ratios 4.01, orders 2.005 at every record; the prototype's 4.8e-4/1.19e-4/2.97e-5). The rule is 0.446/0.445 over 528 elements, none exceeding. Controls caught k at 1e-5 and 1e-6, D_V at 1e-4 and 1e-5. The reference's own rtol difference is 8.3e-13 of c*. §6.4's 0.68 u0 (the prototype's B2) measures something else: in the reference's own integration of Q6's start at 3000 s, max |u − ū| is 0.43, the peak to peak 0.85 and the mode-2 coefficient 0.43. B2 is not specified fully, and the engine matches the reference to 5.4e-4 of c* | `cr.integrate_chain` |
| Q7 | The face-free world's energy residual is 0.052 of the rounding allowance at every one of 4,000 rows. Restart through a snapshot read in a fresh process is bitwise. The batch of three seeds on L/ℓ = 6 is bitwise against its reverse and equal to the scalar runs. The worst accounting comes from every run that records it, which is every part's but Q4's: Q4's 163 runs pass every host check on every window but record only their rates. Over those runs the energy residual is 2.2e-3 of its bound and the network rows' material residuals 6.7e-3 of theirs | — |

**The PROPOSED protocol.** It is `validation/morphogenesis/protocols/mg0c_turing_v1.json`, not
registered. `mg0c_protocol.py` drafts it from dev-d4cee87-a, -b and -c and dev-3e7399a-d.
- **Criteria:** 52 judged criteria, as metric paths for `mg0a_gradient.evaluate`, in
  D150's reviewed forms:
  - S5's dt-study rule at 50 and 25 ms, per element and record: 3 × the step term plus the
    reference's own term;
  - the orders' stop rules, with the orders themselves reported;
  - the k and D_V controls at 76 registered deltas, each 10 × the larger of the smallest
    deltas caught in development;
  - a priori bounds where an exact discrete map exists: guard 2's 1e-14 × steps × the scale, and
    Q1's linearised map at 1e-6;
  - the structural items: Q2's to Q5's modes and the staircase;
  - Q7's bitwise and rounding checks;
  - D147.

  Every criterion a development run can evaluate passes (`development_values`). The four
  control criteria are evaluable only in a judged run, and the development's smallest caught
  deltas stand beside them.
- **Guards of record:** ten test files at the judged snapshot. They include the kinetic and
  dissipation comparisons, with their trace-scale limits, and the composed world.
- **The judged run:** the three unit groups, each into its own new directory from one clean
  snapshot of main, then the judge entry over the merged results.
- **Questions for the lead** (in the protocol):
  1. Q7's batch over seeds instead of over domains.
  2. The records' 600 s cap. It never binds in Q1, whose longest record is 590.5 s; in Q5 it binds
     for the near-marginal modes, which would run to 640–1,100 s.
  3. The linearised-map tolerance. No single tolerance separates the two scales with margin: the
     worst floor at the 1e-7 start is 1.3e-7, while the smallest discretisation error is 2.1e-7
     (L/ℓ = 16, n = 1 at 12.5 ms).
  4. The fit-limited rate tolerances.
  5. Q4's candidate modes.
  6. Q6's control grid.
  7. §11.1's pins.
  8. Guard 2's rounding rule: 0.021 of the usage note's, against 0.96 of D150's at 8,000 steps.
  9. The judged run's memory caps (unit b peaked at 3.5 GB of its 4 GiB).
  10. The composition file's place: a judged guard, or a regression guard outside the judged list.
      Its same-material test uses an exchange map the engine agent wrote from D150's documented
      law, and its idle claim 3 is reported, not promised.

**Findings for the lead:**
1. **Q7's "vmap batch of the domains" cannot run.** A route's node is in the batch signature, so
   the protocol proposes a batch of seeds on one domain.
2. **Guard 2's rounding.** In the passive world the engine accumulates about 0.95 ε × the scale
   per step. The long-double iteration shows this is the engine's own rounding, linear in steps,
   with no composition term. D150's steps × ε rule would sit at 0.96; the usage note's sits at
   0.021 (question 8).
3. **The floor at the 1e-7 start** is the representation's rounding for decaying modes: up to
   1.3e-7 at L/ℓ = 6, n = 6, at its record. For slow modes a start of 1e-6 would lower it. No
   change is proposed; §6.4 sets 1e-7.
4. **Q5's fitted rates fail for complex-eigenvalue modes**, whose norm oscillates. "At its predicted
   rate" is judged by the dt rule against the exact propagator at d = 8.
5. **The dt rule's power lies in its controls.** It sits at 4/9 for a clean second-order error,
   D150's structural finding. Some controls are weak: D_V on L/ℓ = 6's fast modes at 50 ms is
   caught only at 0.1, so it is registered at 1.0.
6. **Memory.** Unit b's cgroup peak was 3.5 GB of its 4 GiB cap, from q7's vector batch (question
   9).
7. **The judged path has run only as a dry run** (not evidence; `mg0c/judge-dry-run-cc32976-b`).
   - The judge entry, on copies of the development results rewritten as judged runs of one clean
     snapshot, merged the four runs and evaluated all 52 criteria. Only the four control criteria
     failed: `caught_at_registered` exists only in a judged run.
   - With the registered deltas loaded, Q1's quick part (L/ℓ = 11; n = 1 at its full record)
     caught both controls at 50 ms.
   - The development launcher `mg0c/dev.sh` creates its output directory first, so it cannot start
     a judged run, which refuses an existing directory.

### 11.4 The lead's review of MG0c's protocol, and the revision (14 November 2026)

The lead reviewed the PROPOSED protocol landed at e659ce4, with the advisor: ten rulings and four
items blocking registration. The revised protocol is still PROPOSED and is drafted by the generator
alone (`python -m validation.morphogenesis.mg0c_protocol draft ...`). It draws on milestone 3's
development runs, with three parts rerun from `snapshot-7495288`, the driver with the review's
additions. The branch adds no `src/` change. Main's `src/` changes since milestone 3 arrived
through the merge of da94f81: FR-9's cap of 16 and the architecture block's items, among them
D156, under which a composite follows its inner model's D147 choice.
- **Which evidence is on which source:**
  - The development runs and the reruns (q1, q6 and q7 from `snapshot-7495288`) predate the merge,
    and so FR-9.
  - These ran at the merged head: the four split files uncapped from `snapshot-454fa75` (1 + 10 + 9
    + 7 = 27 passed, cgroup peak 2.81 GB), the tier measurement at 454fa75, and tier 1 at a98e6cd
    (322 files, no changed outcome).
  - A smoke of the driver at the final head is in HANDOFF.md: `d147` and `theory`, plus `--quick
    q1`.
- **Engine models run:** as §11.3: `resolved_pump_composite@1` over `resolved_pump_tissue@3` with
  `local_species_reactions@1`.
- **Evidence:** `/mnt/workspaces/Cells/shared-inventory-reactions-v1-20261114-01/` (HANDOFF.md,
  round 2): `mg0c/dev-7495288-q1`, `-q6` and `-q7` with their quick passes,
  `dev-7495288-q4-quick`, `mg0c/checks-r2.json`, and `tiers/`.

**The rulings, as the protocol carries them:**

| Ruling | In the protocol |
| --- | --- |
| 1. Q7's batch of seeds on L/ℓ = 6 | `Q7_batch` checks the batch bitwise against its reverse, and `Q7_batch_scalar` checks each world within 1e-12 of its scalar run. §6.4's Q7 row now says so |
| 2. The 600 s cap | It binds in Q5 only (`world.cap_binds_in_q5`), at L/ℓ = 6 n = 1, 11 n = 2 and 16 n = 3. Uncapped, those records would be 638.5, 1,026.9 and 1,101.6 s. It binds nowhere in Q1 |
| 3. The linearised map at 1e-6 | `Q1_L*_linearised_map` is judged at 50 ms only. Its control comes from the other side: the exact propagator must fail the same criterion there (`Q1_linearised_map_control`); both read the same normalisation. At 50 ms the worst floor is 1.3e-7, 7.8 × under the tolerance, and the smallest discretisation error is 3.3e-6, 3.3 × over it. At 25 and 12.5 ms the smallest discretisation errors, 8.2e-7 and 2.1e-7, lie below 1e-6, so those steps are reported only (`linearised_map_by_dt`). The 4.55 ratio: see the findings |
| 4. The rate tolerances | Q2 at 1e-3 and Q3 at 1e-2, against the engine order's discrete-time rate. Q5's fitted rates are reported only |
| 5. Q4's near ties | Near ties are excluded up front, from the references alone: two candidates whose predicted rates differ by less than 2 × 1e-2 × the larger \|rate\|. There are none. The smallest top-two gap is 3.47 × its allowance, at L/ℓ = 25. `Q4_staircase` reads `all_agree_outside_near_ties`, and `Q4_near_ties_as_registered` (an addition) holds the registered empty list: the smallest gap over its allowance must be ≥ 1 |
| 6. Q6's controls at rtol 1e-12 | As drafted |
| 7. §11.1's pins | Moved to `test_species_reactions_accuracy.py` with the tests' loose bounds, a regression guard outside the judged list. The scope line says the heat and work split is guarded, not qualified, until the first mixed-node protocol |
| 8. Guard 2's rule | The usage note's 1e-14 × steps × the scale. The protocol discloses that it was chosen with D150's 0.96 in view |
| 9. q7's memory | q7 runs in its own unit, with a cap of at least 5 GiB |
| 10. The composition file | The same-material test, whose exchange map is the engine agent's own, moved to `test_species_reactions_same_material.py`, a regression guard outside the judged list. Supply counted once, the rejected step's restore, restart and batch stay in `test_species_reactions_composition.py`, a judged guard |

**The blocking items:**
- **(a) The scope line** (`scope`). It keeps the lead's words, with one addition for the lead to
  rule on (question 1). MG0c's judged arms run driven mass action only, of orders 0, 1 and 3, at
  outside nodes. One judged guard world departs from that: guard 2's passive world runs
  `ideal_detailed_balance_mass_action@1` (A ⇌ B, linear) at outside nodes, judged against the
  engine order's exact map (`G2_passive_*`). Ruling 8 rules on that very criterion, since D150's
  0.96 is the passive world's ratio, so the draft keeps it judged and names it. The passive law's
  other uses, Michaelis–Menten, Hill factors, cell routes, D150's writers and the mixed-node heat
  and work split enter only through test files. The scope line also names the species count:
  five per world (three quiescent ions and the network's two), within the 7 the scope stays at.
  FR-9's cap of 16 (D165, merged into this branch at da94f81) is not exercised.
- **(b) D150's pre-registration amendments, carried over:**
  - `judge-guards` runs the guards of record from the snapshot, uncapped per file, into its own
    verdict. A file ended by a signal writes `infrastructure.json` instead of a verdict.
  - `combine` writes the one qualification verdict: every criterion, the guards' files, the scope
    line and the snapshot's revision. It refuses verdicts of another protocol or snapshot.
  - The attempt rule counts a harness timeout, a runtime-limit kill, a signal and an incomplete
    part run as infrastructure endings. The judge refuses an incomplete run, reading its
    `requested_parts` and `complete`.
  - `rules.timing` sets each unit's `--runtime-max` at about 3 × its development seconds plus
    10 min, until the rehearsal measures them. The judged units launch without `--wait-headroom`,
    after the lead checks the slice's headroom.
  - `register PROTOCOL RECORD` changes the status and adds the lead's record alone. The guard reads
    the record: a registered status needs a record with the same status.
  - `rules.controls_evaluable` explains why the control criteria fail outside a judged run. They
    read `caught_at_registered`, which the driver writes only under `--protocol`, with the
    registered deltas loaded. A development run has no registered deltas, so the metric is
    missing and the criterion fails. The five criteria's passing path has never run, so the
    rehearsal must run them to a pass on a registered dry-run copy.
- **(c) Controls by parameter.** (results below)
- **(d) §6.4's amplitude.** The defined measure is the maximum over nodes of \|u − mean(u)\| at
  the last record (3000 s), in c* (u* = c*), in the reference's own integration of Q6's start
  (`cr.integrate_chain`, rtol 1e-13): 0.432 on L/ℓ = 11. Q3's engine measure, the maximum over
  nodes of \|u − u*\| at its end, is 0.427, 0.432 and 0.424 on L/ℓ = 6, 11 and 16. §6.4's Q6 row
  now gives 0.43 c*. The prototype's "0.68 u0" is identified in its record (`probe2/`,
  `reaction_numerics_probe.py` part_b2, `probe2.json`). It is another measure, time and start:
  the range (max u − min u)/u* at 1500 s, from its own start (1e-3 relative noise on U and V,
  seed 20261114), 0.678 to 0.679 at 50 to 12.5 ms and 0.679 in its reference. §11.3's "B2 is not
  specified fully" is corrected by this.

**(c) Controls by parameter** (`rules.controls`, `controls`). Each of k, a, b, D_U and D_V is
perturbed in the reference by (1 + δ) on 38 rules:
- Q1's 36: 18 modes at 50 and 25 ms, against the exact propagator with K = kJ(a, b) and D, on the
  1-2-5 grid from 1e-14 to 0.5;
- Q6's two: the reference re-integrated at rtol 1e-12, bisected on the 1-2-5 grid from 1e-9 to
  0.1 (32 integrations, 572 s).

A control is kept when 10 × its smallest caught δ is at most 1e-2, and it is registered there.
Every parameter keeps controls, so each is caught by a judged criterion at a small δ with a 10 ×
margin. The criteria are `Control_k` to `Control_D_V`. Each requires every kept control of its
parameter to catch at its registered δ, which is stricter than the ruling's "at least one".

| Parameter | Kept (of 38) | Registered δ | Removed |
| --- | --- | --- | --- |
| k | 35 | 5e-7 to 1e-2 | 3: L/ℓ = 6, n = 5 and 6 |
| a | 34 | 1e-8 to 1e-2 | 4: L/ℓ = 6, n = 5 and 6 |
| b | 30 | 1e-8 to 1e-2 | 8: L/ℓ = 6, n = 3 to 6; 11, n = 4; 16, n = 6 |
| D_U | 38 | 5e-6 to 5e-3 | none |
| D_V | 28 | 2e-6 to 1e-2 | 10: L/ℓ = 6, n = 3 to 6; 11, n = 4 and 6; 16, n = 6 |

- **Why controls are removed.** Each removed control's reason is in `controls.removed`. The
  removed controls sit on decaying modes whose slow eigenvalue barely depends on the parameter.
- **The D_V check the lead asked for.** On L/ℓ = 6 at n = 3 to 6, the D_V-sensitive fast component
  has decayed by each mode's first record, to 8.8e-7, 8.6e-6, 2.2e-5 and 3.3e-5 of the slow one.
  The slow eigenvalue's D_V log-sensitivity times the record is 0.15, 0.047, 0.020 and 0.011. A δ
  therefore moves the coefficient by about that much times δ, against a tolerance of about 3 × the
  step term. That estimate gives thresholds of 4e-3 to 0.27, within a factor of 5 of the measured
  5e-3 to 0.1. The same holds for k, a and b on L/ℓ = 6's fastest modes.
- **Q6's a and b controls are caught at the grid's lowest point,** 1e-9, at both steps, so they
  are registered at 1e-8 (`controls.at_grid_floor`). The likely reason is inferred from the
  tolerances, not measured. a and b set the uniform state, u* = (a + b) c*, which k and the
  diffusivities do not, so a δ moves every element by about δ c* from the start. At the early
  records the per-element tolerance falls to 1.3e-14 mM. The floor catch is consistent with this.
- **Q1's passing path, checked on the host** (not a judged run;
  `mg0c/q1_controls_at_registered.py`, `mg0c/q1-controls-at-registered-218eaa3.json`). The check
  loads the registered deltas into the driver's own `controls()` and feeds it dev-7495288-q1's
  stored arrays. All 155 kept Q1 controls catch at their registered δ. The stored arrays reproduce
  every development smallest-caught δ exactly. Q6's 10 kept controls need re-integration and are
  left to the rehearsal.
- **What was in view when the cutoff was set.** The 1e-2 cutoff was set before the a, b and D_U
  thresholds were measured. By then `mg0c/checks-r2.json` already held every Q1 mode's
  slow-eigenvalue sensitivity to all five parameters, which estimates the thresholds to within
  about 5 × (`disclosures`).

**Findings:**
1. **The 4.55 ratio is the scheme's higher-order term, not the floor.** The linearised
   engine-order map alone against the exact propagator at L/ℓ = 6, n = 6 gives the same errors:
   1.27e-3, 2.79e-4 and 6.61e-5, with ratios 4.549 and 4.223 falling toward 4. dt·D_V·λ₆ is 0.40
   at 50 ms, and the floor there is 1.3e-7 (`mg0c/checks-r2.json`).
2. **Memory.** The cgroup peaks were 1.8 GB for q7 alone, 0.87 GB for q6 alone and 2.2 GB for q1,
   so the old unit b's 3.5 GB did not come from q7's batch alone. Unit b (q6, q3, q5) is a prefix of
   that run, so its peak is at most 3.5 GB but has not been measured. The protocol therefore caps
   unit b, like q7, at 5 GiB until the rehearsal measures it. This goes beyond ruling 9.
3. **Q4's sign margin** is 0.19 at L/ℓ = 26.5: there a near-marginal candidate's |rate| is under
   1e-2 of the fastest one's. Each length's smallest-|rate| candidate fits its predicted rate to
   within 5.1e-4 relative (worst at L/ℓ = 28, n = 4), so no sign is in doubt.
4. **The reruns reproduce the earlier parts bitwise:** Q1's errors against both maps and its rule
   ratios, Q6's errors (5.4e-4 and 1.4e-4 of c* at 50 and 25 ms) and ratios (0.446, 0.445), and Q7's
   face-free ratio (0.052). Restart and the batch are bitwise.

**Added beyond the rulings:**
- `Q4_near_ties_as_registered`;
- §6.4's Q7 row;
- unit b's 5 GiB cap;
- `controls.at_grid_floor`;
- each `Control_p` requires every kept control to catch, not just one.

`test_mg0c_judged_refusal.py` now runs main against a PROPOSED copy, never the checked-in file.
Once the file is registered, the old form would have failed from a checkout. Under judge-guards
at the judged snapshot, it would have started a judged part (found by the advisor).

**Questions for the lead** (in the protocol):
1. Does guard 2's passive world stay judged (item (a))?
2. Ruling 7's consequence. With §11.1's pins in `test_species_reactions_accuracy.py`, the heat
   and work comparisons against the true kinetics (`dr.integrate_node`) leave the judged list. The
   judged guards keep dissipation in two forms: rounding-level agreement with `nr.run_half_steps`
   (the same half-steps), and the passive relaxation's total heat against
   `dr.passive_equilibrium`'s drop. The milestone-3 instruction kept the independent kinetic and
   dissipation comparisons as guards of record. Is this split what the lead intends?

**Next** (S5's and D150's path): the lead lands this revision. Then the rehearsal on main, after
FR-9:
- redraft the protocol with one generator command from the runs named here, which predate FR-9;
- run every entry on registered dry-run copies, including the five control criteria to a pass;
- measure each unit's time and peak, unit b's in particular.

Then come the lead's final check, registration and one judged run.

### 11.5 The rehearsal on main (14 and 15 November 2026)

The lead answered §11.4's two questions when landing the revision on main at 58b6f14, in the
combined landing f0e154a with FR-10 milestone 1 and the coupling operator's milestone 2. The lead
also confirmed the six additions and accepted both disclosures (`review` in the protocol).
- **Question 1:** guard 2's passive world stays judged, with the disclosure. Both candidate rules
  pass on the development runs, so the choice concerned fragility, not the outcome. The final check
  can revisit it.
- **Question 2:** the split is intended. The heat and work comparisons against the true kinetics
  are regression guards of record, and the scope line's "guarded, not qualified" is right.

The rehearsal is not a judged run and not evidence of record. Its purpose was to run every judged
entry as the judged run will, before registration.
- **Engine models run:** as §11.3.
- **Snapshot:** a clean snapshot of main at 58b6f14 (`snapshot-58b6f14`). It includes FR-9 and the
  combined landing; the `src/` hold runs from the rehearsal to the registration commit.
- **The dry-run copy.** The protocol was registered through the generator's `register` with a record
  whose status says "registered for MG0c's rehearsal only: a dry-run copy, not a registration".
  Every other leaf is identical.
- **How the entries ran:** through `mg0c/rehearse_entry.sh`, each in its own unit on CPUs 5 and 7.
  The caps were 4 GiB (a, c, guards) and 5 GiB (b, q7), the runtime limits came from the
  protocol, and no `--wait-headroom` was used. Each successor was launched by hand once its lane
  was free.
- **Evidence:** `/mnt/workspaces/Cells/shared-inventory-reactions-v1-20261114-01/rehearsal-58b6f14/`,
  and HANDOFF.md.

| Entry | Lane | Wall time | Peak (cap) | Result |
| --- | --- | --- | --- | --- |
| Unit a (d147, theory, timing, linear, floor, q1, q2, sites) | CPU 5 | 66 min | 2.59 GB (4 GiB) | complete; every part identical to development |
| Unit b (q6, q3, q5) | CPU 7 | 102 min | 2.55 GB (5 GiB) | complete; identical, except Q6's count of control integrations, 38 against 32: the registered deltas' re-integrations |
| q7 | CPU 7 | 7 min | 1.79 GB (5 GiB) | complete; identical |
| Unit c (q4) | CPU 5 | 73 min | 0.98 GB (4 GiB) | complete; identical. Its near-tie leaves are the judged run's own and equal those derived at drafting |
| judge-guards | CPU 7 | 53 min | 3.18 GB (4 GiB) | passed: 10 files, 205 tests, each file exit 0 |
| judge | CPU 5 | 5 s | 0.20 GB | passed: 55 of 55 criteria |
| combine | CPU 5 | 2 s | — | passed: the one verdict (`cells.mg0c_qualification_verdict@1`) |

Against their development times, the parts took:
- q6 1.13 ×, q5 1.10 ×, q1 1.24 ×, q4 1.40 × and q7 1.88 ×;
- q3 0.95 ×.

The tier-3 guard files took 1.5 to 2.8 × their earlier uncapped runs: §11.4's from
`snapshot-454fa75` for `_reference_runs` and `_composition`, and milestone 2's for `_runs` and
`_guards`. The composition file was slowest: 1,498 s against 535 s. These slowdowns are attributed to the
machine's load from other units, which was not measured. The runtime limits that follow carry
it.

**What the rehearsal showed:**
- **The control criteria pass.** All five run to a pass on the registered copy:
  - all 155 kept Q1 controls catch at their registered δ, as the host check predicted (§11.4);
  - all 10 of Q6's re-integrated controls catch: k at 2e-5 and 5e-6; a and b at 1e-8 at both steps;
    D_U at 5e-5 and 5e-6; D_V at 5e-4 and 5e-5. Re-integration took 1,324 s.
- **Main's code reproduces the development numbers.** Every number compared reproduces exactly:
  `mg0c/compare_rehearsal.py` checked 10,103 leaves, skipping only timing. The development runs
  predate FR-9 and the combined landing; main's `src/` changes since then do not touch MG0c's worlds.
- **The judged path works end to end.** The judge merged four runs from one snapshot. judge-guards
  wrote its own verdict, and combine wrote the one verdict with the scope line and the snapshot's
  revision.

**The redraft.** The protocol is redrafted with one generator command from the rehearsal's runs
and the guards' verdict, at the clean head e127755. It is still PROPOSED. The criteria, thresholds,
165 registered deltas and controls are unchanged. These parts are new:
- **Timings and peaks.** The units' times and peaks are the rehearsal's. The runtime limits are
  about 3 × those times plus 10 min: a 12,419 s, b 18,994 s, q7 1,791 s, c 13,768 s and
  judge-guards 10,065 s.
- **Control criteria.** They are evaluable and pass in `development_values`.
- **The lead's answers and confirmations,** in `review`.
- **Two disclosures:** the rehearsal's comparison, and the runs it is drafted from.
- **Lanes.** As the rehearsal ran them: CPU 5 runs a then c; CPU 7 runs b, then q7, then
  judge-guards.

Judge and combine on a registered copy of the redraft pass, with the same 55 criterion verdicts as
the rehearsal's.

**The lead's final check** (15 November 2026):
- **Confirmed:** the lanes as rehearsed, and judge-guards at a 5 GiB minimum cap.
- **Unchanged:** unit b's cap (5 GiB, peak 2.55 GB) and guard 2's passive world (judged). Changing a
  judged item now would mean another rehearsal.
- **Two requests, done at b8f19d3:**
  - The development runs are named again as the protocol's basis, beside the rehearsal's runs,
    in `development_runs.basis`. They are dev-d4cee87-a, -b and -c, dev-3e7399a-d, and
    dev-7495288-q1, -q6 and -q7, the runs the thresholds and the 165 deltas were first derived
    from, before FR-9. The generator's `--basis` refuses to draft unless they give the same
    criteria, thresholds, deltas and controls, and they do.
  - The launcher of record is named in `rules.judge_entries.launcher`: `scripts/run_detached.sh`
    and the rehearsal's `rehearse_entry.sh`, copied unchanged into the judged run's inputs. It
    takes the snapshot's checked-in registered protocol as its argument. No code reads the caps,
    lanes or runtime limits; the launcher alone enforces them, through run_detached.sh's
    MemoryMax, CPUAffinity and RuntimeMaxSec.
- Judge and combine on a registered copy of b8f19d3's protocol pass with the rehearsal judge's 55
  verdicts.

**What follows:**
1. Track R registers first.
2. These commits land on main behind tier 1.
3. From the landed tree the lead registers a copy and runs judge and combine on the rehearsal's
   outputs. Both must run from `snapshot-58b6f14`, whose identity the runs carry, and the copy
   must carry the rehearsal record's status so that combine accepts the rehearsal's guards
   verdict. All 55 verdicts must match.
4. The lead registers through `register` with the lead's record.
5. One judged run follows, from a fresh snapshot of main at the registration commit.

### 11.6 The judged run (15 November 2026)

- **Registration.** The lead registered `mg0c-turing-v1` in commit 5ab4326, which changed the
  status and the registration record only. It came after three steps:
  - the rehearsal (§11.5);
  - the final check with the advisor;
  - a check of the registration path from the landed tree, in which judge and combine were rerun
    on the rehearsal's outputs.
- **The run.** Every entry ran from the clean snapshot of 5ab4326 (`snapshot-judged-5ab4326a`),
  each in its own unit. Each entry was launched through `scripts/run_detached.sh` and the
  rehearsal's `rehearse_entry.sh`, copied unchanged into the run's inputs, with the snapshot's
  registered protocol as its argument. The lanes, caps and limits were the protocol's.
- **Timeline.** The run started at 01:55 UTC. The lead's `orchestrate.sh` launched each successor
  when its lane was free. Every unit succeeded, with no out-of-memory event. The run took 1 h
  52 min in all.

| Entry | Lane | Wall time (limit) | Peak (cap) | Rehearsal |
| --- | --- | --- | --- | --- |
| Unit a (d147, theory, timing, linear, floor, q1, q2, sites) | CPU 5 | 62.6 min (207 min) | 2.62 GB (4 GiB) | 66 min, 2.59 GB |
| Unit b (q6, q3, q5) | CPU 7 | 74.1 min (317 min) | 2.54 GB (5 GiB) | 102 min, 2.55 GB |
| q7 | CPU 7 | 2.8 min (30 min) | 1.77 GB (5 GiB) | 7 min, 1.79 GB |
| Unit c (q4) | CPU 5 | 48.3 min (229 min) | 0.98 GB (4 GiB) | 73 min, 0.98 GB |
| judge-guards | CPU 7 | 18.0 min (168 min) | 3.24 GB (5 GiB) | 53 min, 3.18 GB |
| judge | CPU 5 | 1 s (10 min) | 0.10 GB (2 GiB) | 5 s |
| combine | CPU 5 | 2 s (10 min) | 0.10 GB (1 GiB) | 2 s |

- **The verdict.** `combine/verdict.json` is `cells.mg0c_qualification_verdict@1` and passed. Its
  snapshot revision is 5ab4326, and it carries the scope line.
  - **The judge:** 55 of 55 judged criteria. The five control criteria passed with every kept
    control caught at its registered δ: k 35, a 34, b 30, D_U 38 and D_V 28.
  - **judge-guards:** all 10 files exit 0, 205 tests, 1,080 s in all.
- **Against the rehearsal.** 10,502 non-timing values were compared, all identical and none
  present on only one side (`compare-judged-vs-rehearsal.json`): a 4,122, b 5,323, q7 25 and c
  1,032. The rehearsal in turn reproduced the development runs (§11.5). The judged run's numbers
  are therefore those of the protocol's basis.
- **Timing.** The run was faster than the rehearsal, especially for the guards and unit b. Every
  unit stayed well inside its runtime limit, and every peak matched the rehearsal's to within
  0.06 GB.
- **Evidence.** In `/mnt/workspaces/Cells/shared-inventory-reactions-v1-20261114-01/`:
  - `judged-5ab4326a/`: each entry's output directory, with the entry's log, `run.txt` and
    memory record beside it, and `compare-judged-vs-rehearsal.json`;
  - `judged-inputs-5ab4326a/`: `orchestrate.sh`, its log and the copied `rehearse_entry.sh`.

  PROGRESS and the plan are at c269339.
- **What it qualifies** is the status line's scope, numerically. It makes no biological claim.

## Appendix A. Equations for the independent references

The references are written from these equations, not from engine code.
- Units are @3's: fmol, pL, mM, s, m.
- RT is the engine's: 1e-3 R T pJ/fmol with the engine's R and T; the references take RT as an
  input. (2.5773 pJ/fmol at 310 K uses R = 8.314; SI R gives 2.5775. Amended at milestone 1, §11.)
- κ_f = D_f A_f/L_f in pL/s.

**Node kinetics.** At node i, with c = n/V_i and route rates J_r(c) from §2.2:

    dn_s/dt = Σ_r ν_sr J_r + Σ_{f∋i} κ_f (c_j − c_i) + (other writers),
    J_mass_action = m F k V ∏ c^α;   J_MM = m F V k_cat c_E c_S/(K_M + c_S);
    J_passive = m V c0 k_f [exp(Σ α ln a) − exp(Σ β ln a + Σ ν μ°/RT)],   a = c/c0.

**Factors:** x^n/(K^n + x^n) for activation and K^n/(K^n + x^n) for inhibition, evaluated as
exp(−logaddexp(0, ∓n(ln x − ln K))).

**The passive net rate,** in its stable form, the kernel's:
J = m V c0 k_f exp(max(f, r)) (−expm1(−|A|)) sign(A), with f = Σ α ln a, r = Σ β ln a + Σ ν μ°/RT
and A = f − r. In exact arithmetic it equals J⁺ − J⁻ below.

**The half-step.** SSPRK(3,3) in Butcher form, with one sub-step in version 1 (h_sub = h = dt/2):

    Y1 = n,  Y2 = n + h ν J(Y1),  Y3 = n + h ν (J(Y1) + J(Y2))/4,
    Δξ = h (J(Y1) + J(Y2) + 4 J(Y3))/6,  n' = n + ν Δξ.

Its weights are (1/6, 1/6, 2/3), at stages (0, 1, 1/2). The stage condition is h max L ≤ 1/2 at
Y1, Y2 and Y3, that is dt · L ≤ 1. A failure refuses the step, as does any non-positive or
non-finite stage or result. L is defined as follows.

    L_s = [Σ_driven max(−ν_sr, 0) J_r + Σ_passive (max(−ν_sr, 0) J⁺_r + max(ν_sr, 0) J⁻_r)] / n_s,
    J⁺_r = m V c0 k_f exp(Σ α ln a),   J⁻_r = m V c0 k_f exp(Σ β ln a + Σ ν μ°/RT).

The unidirectional fluxes are used, never the signed net rate of a passive route.

**Free energy.** G_i = RT Σ_s n_s (ln(n_s/V_i) − 1) + Σ_s μ°'_s n_s, with
μ°'_s = RT (μ°_s/RT − ln c0). The increment form over a half-step from a (start) to a + δ:

    ΔG_i = RT Σ_s [δ_s (ln(a_s/V_i) − 1) + (a_s + δ_s) log1p(δ_s/a_s)] + Σ_s μ°'_s δ_s.

**Bookings,** per node and half-step.
- **The node's class in a step comes from the step's multipliers.** A node is driven-active if a
  driven route there has m_r > 0, and passive-active if a passive route does.
- **A node with neither** selects its start state: W = H = 0 and no change (§4.5).
- **Single-class nodes (in the step):** driven only, W = ΔG and H = 0; passive only, H = −ΔG and
  W = 0.
- **Mixed nodes (in the step):** H = Σ_passive H_r and W = ΔG + H, with the per-route hybrid:
  - **The non-reversing test.** A passive route does not reverse when sign J_r(Y1) = sign J_r(Y2) =
    sign J_r(Y3) = sign A_r(n'), all nonzero. A zero flux or affinity counts as reversing. J_r is
    the net rate above, and A_r is defined below.
  - **The non-reversing branch: the average-vector-field share** (McLachlan, Quispel & Robidoux
    1999), H_r = −Δξ_r Σ_s ν_sr μ̄_s. Per species, with Δ_s = n'_s − n_s and x = Δ_s/n_s:

        μ̄_s = RT [ln(n_s/V_i) + (1 + x) log1p(x)/x − 1] + μ°'_s
            (the ratio is 1 + x/2 − x²/6 when |x| < 1e-6).

    This is the divided difference [g_s(n'_s) − g_s(n_s)]/Δ_s of g_s(n) = RT n (ln(n/V_i) − 1) +
    μ°'_s n, so Σ_s μ̄_s Δ_s = ΔG_i exactly.
  - **The reversing branch: the stage quadrature** H_r = h Σ_k b_k RT J_r(Y_k) A_r(Y_k), with
    b = (1/6, 1/6, 2/3) at Y1, Y2 and Y3, and A_r = Σ α ln a − Σ β ln a − Σ ν μ°/RT.
  - **The known limit.** At a half-step in which a driven route carries a trace species across a
    passive route's equilibrium, the reversing branch samples the trace (§3.3). The references
    document its size; they do not pass or fail it.
- **The dissipation integral for the references** (the independent check of H at mixed nodes):
  dH/dt = RT Σ_passive J_r A_r, integrated with the amounts by a high-order solver at tight
  tolerance from the same start (probe 2d's method).
- **The standard term** gains Σ_r ΔG°'_r Δξ_r, with ΔG°'_r = Σ_s ν_sr μ°'_s.
- **The ledger:** Δ(chemical) + Δ(standard) + H − W = 0.

**Moieties.**
- A closed reaction has Σ_s M_qs ν_sr = 0 for every moiety q.
- A source has every ν_sr ≥ 0 and a sink every ν_sr ≤ 0.
- Moiety totals change by Σ_{open r} (M ν_r) Δξ_r.

**The zero-flux chain.**
- Eigenvectors cos(nπ(i + ½)/N) and eigenvalues λ_n = (4/h²) sin²(nπ/(2N)), n = 0, …, N − 1.
- @3's species transport for z = 0 under ARS(2,2,2) is c' = (I − dt K + ½ (dt K)²) c, with
  K = D λ on each mode (probe 1).

**Linear evolution per mode.** a_n(t) = expm[(K_lin − λ_n diag(D)) t] a_n(0), with K_lin the network's
Jacobian at the uniform state (MG0c) or its rate matrix (linear networks).

**Dispersion** (two species): σ(k²) is the largest real part of the eigenvalues of
J − k² diag(D_u, D_v). Instability needs tr J < 0, det J > 0 and
D_v f_u + D_u g_v > 2 √(D_u D_v det J). The band's edges are the roots of
D_u D_v k⁴ − (D_v f_u + D_u g_v) k² + det J = 0.

**Schnakenberg in mass action.** The rate constants a k c*, k, b k c* and k/c*². The uniform state is
u0 = a + b and v0 = b/(a + b)², with

    J = [[−1 + 2 u0 v0, u0²], [−2 u0 v0, −u0²]]   (time unit 1/k, length unit ℓ = √(D_U/k)).

**Closed-form references.**
- Turnover: n(t) = n0 e^{−kt} + (P/k)(1 − e^{−kt}).
- Michaelis–Menten depletion: K_M ln(S0/S) + (S0 − S) = V_max t.
- Passive equilibrium: c_B/c_A = exp(−(μ°_B − μ°_A)/RT) at a common c0.

## References

Every DOI was checked against its Crossref record (`sources/crossref_records.json` in the evidence
folder), with no project details sent. The books and the 1910 and 1913 papers were not fetched.
- Briggs GE, Haldane JBS. A note on the kinetics of enzyme action. *Biochem J* 1925;19(2):338–339.
  doi:10.1042/bj0190338
- Bruggeman J, Burchard H, Kooi BW, Sommeijer B. A second-order, unconditionally positive,
  mass-conserving integration scheme for biochemical systems. *Appl Numer Math* 2007;57(1):36–58.
  doi:10.1016/j.apnum.2005.12.001
- Burchard H, Deleersnijder E, Meister A. A high-order conservative Patankar-type discretisation for
  stiff systems of production–destruction equations. *Appl Numer Math* 2003;47(1):1–30.
  doi:10.1016/S0168-9274(03)00101-6
- Crank J. *The Mathematics of Diffusion*, 2nd ed. Oxford: Clarendon Press; 1975. Chapter 14.
- Danckwerts PV. Absorption by simultaneous diffusion and chemical reaction into particles of various
  shapes and into falling drops. *Trans Faraday Soc* 1951;47:1014. doi:10.1039/TF9514701014
- Gierer A, Meinhardt H. A theory of biological pattern formation. *Kybernetik* 1972;12(1):30–39.
  doi:10.1007/BF00289234 (background; not used)
- Gottlieb S, Shu C-W, Tadmor E. Strong stability-preserving high-order time discretization methods.
  *SIAM Rev* 2001;43(1):89–112. doi:10.1137/S003614450036757X
- Hill AV. The possible effects of the aggregation of the molecules of haemoglobin on its
  dissociation curves. *J Physiol* 1910;40(Suppl):iv–vii.
- Hundsdorfer W, Verwer JG. *Numerical Solution of Time-Dependent Advection-Diffusion-Reaction
  Equations*. Springer; 2003. Chapter IV (splitting).
- Keener J, Sneyd J. *Mathematical Physiology I: Cellular Physiology*, 2nd ed. Springer; 2009.
  Chapter 1 (mass action, Michaelis–Menten, cooperativity and the Hill equation).
- Maini PK, Woolley TE. On the Turing model as cited by the [morphogenesis plan](MORPHOGENESIS_PLAN.md)
  (people.maths.ox.ac.uk/maini/PKM publications/462.pdf; its claim C2c in that plan's verified
  record).
- McLachlan RI, Quispel GRW, Robidoux N. Geometric integration using discrete gradients. *Phil Trans
  R Soc Lond A* 1999;357(1754):1021–1045. doi:10.1098/rsta.1999.0363 (the average-vector-field
  discrete gradient of §3.3)
- Michaelis L, Menten ML. Die Kinetik der Invertinwirkung. *Biochem Z* 1913;49:333–369.
- Mielke A. A gradient structure for reaction–diffusion systems and for energy-drift-diffusion
  systems. *Nonlinearity* 2011;24(4):1329–1346. doi:10.1088/0951-7715/24/4/016 (the dissipative
  structure behind §3.3's heat sign)
- Murray JD. *Mathematical Biology II: Spatial Models and Biomedical Applications*, 3rd ed.
  Springer; 2003. Chapter 2.
- Rao R, Esposito M. Nonequilibrium thermodynamics of chemical reaction networks: wisdom from
  stochastic thermodynamics. *Phys Rev X* 2016;6(4):041064. doi:10.1103/PhysRevX.6.041064
- Schnakenberg J. Simple chemical reaction systems with limit cycle behaviour. *J Theor Biol*
  1979;81(3):389–400. doi:10.1016/0022-5193(79)90042-0
- Segel LA, Slemrod M. The quasi-steady-state assumption: a case study in perturbation. *SIAM Rev*
  1989;31(3):446–477. doi:10.1137/1031091
- Shu C-W, Osher S. Efficient implementation of essentially non-oscillatory shock-capturing schemes.
  *J Comput Phys* 1988;77(2):439–471. doi:10.1016/0021-9991(88)90177-5
- Strang G. On the construction and comparison of difference schemes. *SIAM J Numer Anal*
  1968;5(3):506–517. doi:10.1137/0705041
- Turing AM. The chemical basis of morphogenesis. *Phil Trans R Soc Lond B* 1952;237(641):37–72.
  doi:10.1098/rstb.1952.0012
- Weiss JN. The Hill equation revisited: uses and misuses. *FASEB J* 1997;11(11):835–841.
  doi:10.1096/fasebj.11.11.9285481
