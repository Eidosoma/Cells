# Reactions on the shared inventory (design)

**Status: proposed, 14 November 2026, for the lead's review with the advisor before acceptance
(D142). No code.** Code follows D150 version 1's code (after S5a) and this note's acceptance
(D152). Four pre-code probes ran the same day (§10), the last after the advisor's review corrected
the stage condition for passive routes (§4.2). No engine code was added or changed.

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
  qualified. It runs through that law's shared kernel `processes/mass_action.reversible_flux`,
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
- probes 1, 2, 2b and 2c of §10;
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
   - **The bookings:**
     - at a node with driven routes only, W = ΔG;
     - with passive routes only, H = −ΔG, which the dissipation check requires to be non-negative;
     - with both, H is the stage quadrature of the passive dissipation (non-negative by
       construction) and W = ΔG + H.
   - **A finding: @3's chemical term has no standard potentials.** The operator therefore owns the
     standard-potential term and adds it to the energy ledger. Without it, a passive conversion with
     K ≠ 1 books negative heat (probe 2, B7).
   - **Why exact bookings.** A quadrature booking mis-books a switch-on from a trace by 27% in its
     first step (B5). The exact booking does not.
   - **The guards of record** check the residual at rounding in a face-free species-only world,
     where the operator is the only energy flow, not against the shared bound, which is blind at
     µM–nM (D150's lesson). A NumPy ΔG test per law and negative controls complete them.
6. **Numerics** (§4).
   - **The half-step:** SSPRK(3,3) sub-steps with a run-time stage condition h·L ≤ ½, which makes
     positivity a theorem. A failure is refused, never repaired.
   - **Order:** Strang splitting against transport is second order. The prototype's ratios are
     3.98 to 4.07 (probe 2).
   - **Idle:** bitwise idle at zero rate.
   - **Solvers:** IMEX only. RK4 and the stationary analysis are refused, with reasons (§4.6).
     Kinetics too stiff for the step are refused at run time, a door for later.
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
   - **Probes 2, 2b and 2c, a NumPy prototype:** they confirm the numerics, the bookings and the
     dispersion design. Probe 2c tests the stage condition as corrected in review.
   - **Proposed before code:** five further checks, chief among them a contract-fit probe with an
     in-process operator once D150 v1 lands.
9. **Limits** (§7). Version 1 is a static tissue with neutral species, at most 7 species and
   non-stiff kinetics. It is refused beside water, the lumen, closers, RK4 and the stationary
   analysis.
10. **Effort:** about 6 agent-days (range 5 to 7), plus about an hour of CPU for MG0c's judged runs
    (§8).

**Two departures, for the lead to rule on:**
1. **The brief says the operator composes with D150's turnover.** It does, except on the rows the
   network writes. A turnover route on a reacting (species, node) is refused, so that each node's
   local kinetics have one writer, and the production and clearance of a reacting species are
   declared as source and sink reactions instead (§1.1; §9 question 3).
2. **RK4 is refused, where D150 guards it** (§4.6; §9 question 5).

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

**One local-kinetics writer per (species, node)** (proposed for version 1, §9 question 3):
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
- **A law library.** `processes/network_reactions.py` offers:
  - `rates` over [..., species, compartment] concentrations (mM) and volumes (m³);
  - `accounting` of extents;
  - `bind` from the reference's dictionaries;
  - cell, mitochondrial, environment and growth branches.

  Its docstring reads: "No heat, ATP, transport or clipping is owned."
- **No engine model integrates its kinetics.**
  - Its one engine consumer is `network_control_factors@1` (`processes/network_control.py`). That
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

**What is reused.** `processes/mass_action.reversible_flux`, which is neutral and cited (Rao &
Esposito 2016). It is the kernel of `compartment_reactions@1`'s law. It is called unchanged, and no
program that calls it today changes, so crossrev stays identical and D148 does not arise.

**What else stays separate:**
- `compartment_reactions@1`, a standalone closed-chemistry model with its own state; its
  qualification stands;
- `reaction_transport@1`, MG0a's standalone model.

**Not authorised, and recorded for later** (§9 question 11):
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
 "substeps": 1,
 "species": [{"id": "U", "moieties": {"M": 1}, "standard_mu_RT": 0.0, "reference": null}],
 "reactions": [
   {"id": "u_autocatalysis",
    "sites": {"outside": ["node_0", "node_1"]},
    "reactants": {"U": 2, "V": 1}, "products": {"U": 3},
    "law": "mass_action", "rate_constant": 1e5,
    "factors": []}]}
```

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
- **`substeps`:** the static sub-step count m of §4.2.

**The schedule, `reaction_controls`:**
- per reaction, and optionally per site, a piecewise-constant multiplier m_r(t) ≥ 0;
- changes at exact multiples of dt, refused otherwise;
- a zero multiplier switches a reaction off (D136 idleness; E15's "switching off at the damage");
- on a passive reaction the multiplier scales both directions, as `compartment_reactions@1`'s does.
  It changes the kinetic barrier, adds no material and leaves the equilibrium unchanged.

**Whose rates.**
- **Outside routes** belong to their node, which is environment.
- **Cell routes follow the occupant.** D150 §5.2's rule applies: carriers have identity, slots are
  storage. Version 1 applies it to the per-site multipliers through D150's mechanism. A newcomer
  takes its template's or donor's multipliers at the event step, and a donor copy whose route values
  differ from the slot's is refused.
- **Law parameters** are per reaction, shared by its sites, and per world. Per-carrier parameter sets
  wait for version 1.1 (§9 question 6).

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
  factor kinds and their species, roles, and `substeps`.

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
- more than 7 species, D150's cap, refused with the cap named (D150 §2.6);
- a turnover route on a (species, node) the network writes (§1.1);
- RK4 (§4.6);
- a catalogue reference that differs from another operator's.

**At run time:** the stage condition, positivity and finiteness (§4.2), returned as the half-step's
validity.

## 3. Accounting

### 3.1 Material, with sources and sinks declared

- **Extent-consistent updates.** Per route, the extent increment over a sub-step is
  Δξ_r = h_sub Σ_k b_k J_r(Y_k) (§4.2). The net change Δn_s = Σ_r ν_sr Δξ_r is computed once per node
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

**The booking rule.** ΔG_i is the exact change of G_i over the operator's half-step at node i. It is
computed in the stable increment form, anchored at the half-step's start, so a protein-scale change
is never a difference of large sums.

| Node holds, by the step's multipliers | Heat H_i | Work W_i | Closure |
| --- | --- | --- | --- |
| Driven routes only | 0 | ΔG_i | Exact |
| Passive routes only | −ΔG_i, which the composite's dissipation check requires to be ≥ 0 | 0 | Exact |
| Both | The stage quadrature h_sub Σ_k b_k RT Σ_passive A_r J_r(Y_k), ≥ 0 by construction | ΔG_i + H_i | Exact |

The node's case is selected per step from its controls, without branching (`where`). So a driven
reaction switched off leaves a passive node, and no work is booked there.

**Why the exact ΔG** (D150's onset lesson; probe 2, B5):
- **What goes wrong with a quadrature.** A switch-on from a trace is a nearly log-singular path in
  μ, so a stage quadrature of ΔG_r J mis-books the first step. In B5, a catalysed S → P with P at a
  trace of 1e-12 mM, it is 27% off; at 1e-9 mM, 11%; at 1e-6 mM, 0.07%. From the second step it
  agrees to 1e-4 or better.
- **What the exact booking does.** The state-function difference is exact at any switch-on, so the
  onset limit D150 recorded for face heat (§11.4 there) does not arise in this operator's own
  bookings. @3's face heat keeps it, so production worlds should still start resolved where species
  diffuse (§3.4).

**Why heat ≥ 0 holds:**
- **At mixed nodes, by construction.** Passive routes use detailed-balance mass action, whose rate
  has exactly the sign of its affinity (`reversible_flux`: sign(J) = sign(A)). So each stage's
  RT A J ≥ 0, and the weights (1/6, 1/6, 2/3) are positive.
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
- **At mixed nodes,** W also absorbs the quadrature error of H, which is O(h³) (B6: order ratios
  8.50 and 8.26).

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
   - **The cases it must cover:**
     - driven-only, passive-only and mixed nodes;
     - a switch-on from the trace (B5's case);
     - a closed passive relaxation, with total heat = G(start) − G(equilibrium);
     - every row's heat non-negative and non-decreasing.
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
   - in a mixed heredity world, the shared bound does not see the scaled work or the dropped
     standard term. The bound/booking ratio measured there goes into the docstring statement, as
     D150's probe 2 part C did (§10.3, C2);
   - a wrong-sign heat is still caught there by the composite's dissipation check. Only the bound
     is blind to it.
4. **A NumPy ΔG test per law,** written from Appendix A, not from engine code. For each law, order,
   factor and node kind, it takes random positive states, volumes and parameters and one half-step.
   It must show:
   - booked W − H equals the independently computed ΔG_i, standard term included, to 1e-12 of the
     summed |terms|;
   - passive H ≥ 0 at mixed nodes, and H = −ΔG at passive-only nodes;
   - Δn = ν Δξ, and moiety totals change only through sources and sinks;
   - the standard term equals Σ ΔG°'_r Δξ_r;
   - zero multipliers select the start state bitwise;
   - a closed passive network relaxes to the equilibrium its potentials set. In probe 2's B4,
     c_B/c_A came out at 9.99999999999996 against K = 10;
   - at mixed nodes, H converges to an independent dissipation integral at third order in h_sub.
     B6's ratios were 8.50 and 8.26.

## 4. Numerics

### 4.1 Scales

| Case | Rates | h_sub · L at the step |
| --- | --- | --- |
| MG0c (synthetic, §6.4): k = 0.1 s⁻¹, ℓ = √(D_U/k) = 10 µm, D_U = 1e-11 and D_V = 1e-10 m²/s | L up to about 0.3 s⁻¹ while the pattern forms | at most 0.0076 at dt 0.05 s (probe 2, B2) |
| Morphogen scale (D150 §4.1): k about 1e-4 s⁻¹ | – | about 5e-8 at 1 ms |
| Catalysis (GZMK item 2): k_cat c_E/K_M, which no paper there reports | e.g. 1 s⁻¹ × 0.1 | about 5e-5 at 1 ms |
| Fast binding, k_on c of about 1e2 to 1e4 s⁻¹ | stiff at 1 ms | refused unless m sub-steps bring it under θ; a door (§7.3) |

**Who sets the transport's step:**
- **Species-only worlds:** the species' own face rates set dt. Probe 1's chain (h = 10 µm,
  D_V = 1e-10 m²/s) has an explicit-rate bound of 4 s⁻¹, so it admits dt ≤ 0.25 s. A step at 1.24
  times the bound was refused.
- **Worlds with moving ions:** the ions set dt (D150 §4.2).

### 4.2 The half-step integrator

**SSPRK(3,3)** (Shu & Osher 1988; Gottlieb, Shu & Tadmor 2001), with m static sub-steps (the
declared `substeps`, default 1) of size h_sub = h/m:

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
  the operator's message: the largest h_sub L, and the advice to use more sub-steps or a smaller dt.
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
- **What version 1 does.** It refuses reacting species with nonzero membrane or junction permeability.
  D150's inventory species are impermeant anyway, so nothing a consumer needs is lost.
- **For the lead.** Whether @3's bound should be extended is a D148 question (§9 question 7, §10.3
  C4).

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

**Stiffness relative to the split step.**
- **The risk.** With sub-steps, a network may be stiff relative to dt (dt · L > 1) while every
  sub-step meets the condition. Splitting stiff reactions from transport can then lose order
  (Hundsdorfer & Verwer 2003, ch. IV).
- **Version 1's scope.** Version 1 admits such worlds only as labelled development runs, until a
  probe measures their splitting order (§10.3, C3).
- **The default.** The default of one sub-step keeps dt · L ≤ 2θ = 1.

### 4.4 Positivity and the trace

- **The trace background.** D150 §1.3's background holds: every species is positive everywhere, and
  a reacting species that is "absent" is a declared trace.
- **Depletion is safe.** Rates vanish as consumed species vanish (§2.2), so depletion approaches zero
  at worst as e^{−L t}, and the stage condition keeps every step positive. Underflow comes only
  after L t ≈ 708 (D150 §1.3).
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

**Why RK4 is refused:**
- (a) The coupled RK4 path takes operator rates on owned fields only, and this operator writes @3's
  rows (injection's finding, v2 §4.1). So RK4 could run only as a Strang split around the inner
  step, at second order. Such a run is no fourth-order reference, and it would be mistaken for one.
- (b) RK4's sharp absolute energy bound (2e-8 pJ) adds nothing here. The operator's bookings are
  exact and are checked at rounding in the face-free world (§3.4).
- (c) Its step limit of 1e-4 s multiplies the steps by 10 to 2,500.
- (d) D150's RK4 guard worlds stay the transport's sharp reference, without the network.

  RK4 is admitted once a coupled-rates contract extension, operator rates on inner fields, makes an
  unsplit RK4 a true reference. This differs from D150, where RK4 is guarded (§9 question 5).

**Why the stationary analysis is refused:**
- (e) It refuses the composite's ID (D150 probe 2).
- (f) Its right-hand side would need operator rates on inner fields, the same extension.
- (g) Its Newton test is one absolute tolerance (1e-10 mM per amount), too coarse for µM–nM species
  without per-species scaling (D150 §8).

MG0c's steady states and Jacobians come from the NumPy references (§6). The door is coupled rates
plus per-species scaling, and continuation of Turing bifurcations would be worth having later.

### 4.7 Cost

- **Per node and sub-step:** three rate evaluations and three stage-condition evaluations over the
  node's routes. That is O(R) work for R routes, small beside the dense field (D150 §4.4).
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
| `scheduled_cell_replacement@1` | Composes | Cell routes follow the occupant through their multipliers (§2.1); both read declared volumes; the event swaps every species' pool (D150 §5.2) |
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
- σ_max = 0.0572 at k̃² = 0.3186, a wavelength of 11.13 ℓ.

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

**Judged items** (proposed; tolerances are pinned at registration from the dt study and the reference
terms, D150 §6's rule, and each run is made once from a clean snapshot):

| Item | Check |
| --- | --- |
| Q1, mode propagation | On L/ℓ = 6, 11 and 16, single-mode starts (amplitude 1e-7 of c*) for every n ≤ 6: each mode's coefficient vector at its record against the exact discrete propagator; second order in dt. Prototype: 2.0e-6 to 1.25e-3 relative at 0.0125 to 0.05 s, ratios 3.98 to 4.07 (B1, B1b) |
| Q2, admissible modes only | On L/ℓ = 8, from seeded noise (1e-3 of c*), the deviation from uniform decays at the slowest admissible rate (n = 2, σ = −0.065 k) and the pattern never forms. Prototype: 1.4e-8 of u0 at 1,500 s from 1e-3 (B2) |
| Q3, the predicted wavelength | On L/ℓ = 6, 11 and 16, from seeded noise, the dominant mode during the linear phase and at saturation is the only admissible unstable mode, n = 1, 2 and 3 (wavelengths 2L, L and 2L/3), and its fitted growth rate matches σ_n. Prototype: dominant modes 1 and 2 on 6 and 11, as the reference integration gives (B2) |
| Q4, the staircase | Over a declared sweep of L/ℓ (4.5 to 30), the fastest-growing mode among single-mode starts on the engine follows the discrete argmax of σ_n, including both gaps |
| Q5, the subcritical control | d = 8 < d_c: on every domain every mode decays, at its predicted rate |
| Q6, the nonlinear pattern | From the same seeded start, the engine's pattern at its records (to saturation) against an independent integration of the same semi-discrete system (SciPy DOP853, rtol 1e-12); second order in dt. Prototype: 4.8e-4, 1.19e-4 and 2.97e-5 of c* on L/ℓ = 11 (ratios 4.02 and 4.01); amplitude 0.68 u0 (B2) |
| Q7, accounting | Material ledgers at the species' floors; every host check; the face-free energy world at rounding (§3.4); positivity; restart through a written snapshot, bitwise; a vmap batch of the domains, each world within 1e-12 of its scalar run |

**Reported, not judged:** the discrete σ_n and k_n against the continuum, which converge at second
order in h.

**What MG0c does not show:**
- any biological claim;
- the selection between several unstable modes on wide domains, which is nonlinear and outside the
  linear theory;
- two-dimensional patterns (they need sparse field IDs, D150 §3);
- recovery after damage, which is E15's question.

**A second world, after D150 v1 lands** (proposed, §10.3, C5): the same network inside cells, with
secretion and uptake by D150's exchange, and diffusion on faces. Its NumPy reference is the linear
stability of the three-compartment system. It checks the composition, not only the operator.

### 6.5 Guards

- **Tier 1.** A smoke test under 20 s (the v2 rule): one tiny world, a few steps, the ledgers
  closing and the idle identity.
- **Idle:** §4.5's three claims.
- **Ledgers at the species' scale.** @3's per-species ledgers with D150's species-scale floors, on
  host and device. The negative control: a misbooked accumulator fails the species' row while the
  ions pass.
- **Energy:** §3.4's four guards.
- **Positivity:**
  - the stiff-front guard (§4.4);
  - background insensitivity (D150 §1.3): a 10³ change of the trace moves every compared quantity
    far below its tolerance;
  - the refusal of a step beyond the stage condition, with the prior state kept bitwise.
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
- Declared moieties, sources and sinks; the exact energy bookings with the owned standard-potential
  term.
- SSPRK(3,3) half-steps with the stage condition; IMEX inner steps; vmap, windows and restart.
- Composition with @3, injection, D150's turnover (outside the network's rows) and exchange,
  replacement@1 (by the occupant rule on multipliers) and `membrane_entity_state@1`.

### 7.2 What version 1 does not include, and refuses

- Charged species, and reacting species with membrane or junction permeability.
- Held-bath sites, membrane-surface reactions and occupancy.
- Volume providers (water, the lumen, replacement@2) and closers (insertion, partition, bridge).
- RK4, the stationary analysis and the coarse modes.
- Kinetics too stiff for the step (refused at run time); development runs only where dt · L > 1
  with sub-steps (§4.3).
- More than 7 species per world (D150's cap).
- Per-carrier parameter sets; reversible Michaelis–Menten; multi-substrate mechanisms; delays.
- A turnover route on a reacting (species, node).

### 7.3 The doors (version 1.1 and later; each needs its own design and qualification)

| Door | What it needs |
| --- | --- |
| Volume (water, the lumen) | `VIEW_READS` with D150's fallback; bookings at the view through water's endpoint free energy (D150 §5.1) |
| Closers | S5's living-interval rule (D150 §5.3) |
| Charged closed reactions (buffering) | Σ_s z_s ν_sr = 0 checked in integers; the field and electrode exactness of D150 §3 re-argued |
| Stiff kinetics | A positive implicit or linearly implicit half-step, with its own order and positivity probes |
| Coupled RK4 and the stationary analysis | Operator rates on inner fields in the composite's coupled right-hand side; per-species Newton scaling |
| Chemostats inside cells | A held species, an open passive law whose partner has a declared potential |
| Energy pools | Driven routes drawing on finite energy pools, making their work a metabolic cost (D150 question 11) |
| Regulation from other layers | The gene-regulation layer (held, D145) as a factor source or a production law, not an edit to these laws |
| More than 7 species | D150's check of host-side summation order at 8 or more terms |
| Occupancy and surface catalysis | D150 §2.5's primitive and its four requirements |

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
| The laws and the half-step: rates, factors, SSPRK(3,3) sub-steps, the stage condition, extents, the exact bookings with the standard term, idle selection | 1.5 |
| Ledger terms, observations, the summary, the tier-1 smoke | 0.5 |
| Guards: NumPy references (Appendix A), the face-free and transport species-only worlds, negative controls, positivity, restart, vmap, crossrev, tier gates | 1.5 |
| MG0c: the driver, its NumPy references (dispersion, mode propagators, the SciPy pattern), registration, judged runs (CPU, about 1 h) | 1.5 |
| **Total** | **6 (range 5 to 7)** |

**Order:**
1. after D150 v1's code lands (the adapter addition and the inventory-species helper);
2. the contract-fit probe C1 (§10.3);
3. the operator;
4. its guards;
5. MG0c.

Each step lands behind its tier-1 tests. Long runs go through `scripts/run_detached.sh`.

## 9. Open questions

**For the lead:**
1. **The shared-state decision:** `network_reactions@1` stays separate, neither migrated nor wrapped
   (§1.2). Confirm.
2. **The energy rule:** exact ΔG bookings, the three node cases, and the owned standard-potential
   term as a free-energy field outside the flows (§3.3). Confirm, including the field's role in the
   energy-role table.
3. **One local-kinetics writer per (species, node):** refuse a turnover route on a reacting row
   (§1.1). Confirm, or relax it and measure the splitting.
4. **Numerics:** SSPRK(3,3) with θ = 1/2 and static sub-steps; stiff kinetics refused at run time,
   with a Patankar-type or implicit half-step as a later door (§4.2). Confirm θ and the choice.
5. **RK4 refused,** not guarded as in D150 (§4.6). Confirm.
6. **Replacement@1:** compose with the occupant rule on per-site multipliers and shared parameters,
   or refuse reaction routes on replaced slots in version 1 (§2.1)?
7. **Finding 3:** version 1 refuses reacting species with membrane or junction permeability. Should
   @3's explicit bound gain the neutral material term (D148), and does that matter for D150 v1?
8. **MG0c's registration:** the domains, items and tolerances of §6.4, and whether the second world
   (cells with exchange) belongs to MG0c or to a later item.

**For the user:**

9. MG0c uses Schnakenberg's textbook network as a declared test case, compared with mathematics
   (the dispersion relation and exact discrete solutions), not with any paper's results. Is that
   within D138 as written, as this note assumes?
10. Should reactions on charged species, such as buffering on the pump family, and driven routes
    drawing on finite energy pools come later (§7.3)?
11. Should `network_reactions@1`'s kinetic branches eventually be retired, or re-expressed through
    this operator? Not authorised now; recorded only.

## 10. Pre-code checks (14 November)

No engine code was added or changed.
- **Evidence:** the scripts, logs and JSON are in the evidence folder's `probe1/` and `probe2/`.
- **Execution:** each probe ran as its own unit through `scripts/run_detached.sh` (`--oom-first`,
  `--wait-headroom`). memory.events were all zero.

| Probe | Question | Where | Exit, wall time, peak |
| --- | --- | --- | --- |
| 1 (`cells-sir-probe1`) | MG0c's transport world on the engine as it is | Clean snapshot of ac5a251, CPU 7, 3 GB cap | 0, 88 s, 0.95 GB |
| 2 (`cells-sir-probe2`) | The proposed numerics and bookings, and MG0c's dispersion design | NumPy and SciPy only (a prototype in the evidence folder, never under `validation/`), CPU 5, 2 GB cap | 0, 357 s, 49 MB |
| 2b (`cells-sir-probe2b`) | Follow-ups: decaying modes over decay-matched windows; turnover's closed form | As probe 2, CPU 7, 1 GB cap | 0, 8 s, 46 MB |
| 2c (`cells-sir-probe2c`) | After the advisor's review: the stage condition on a passive route running in reverse, and the heat sign near θ | As probe 2, CPU 5, 1 GB cap | 0, under 1 s, 44 MB |

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
| B2, the nonlinear pattern against SciPy | L/ℓ = 11: 4.8e-4, 1.19e-4 and 2.97e-5 of c* (4.02 and 4.01), dominant mode 2, amplitude 0.68 u0 (reference 0.679). L/ℓ = 6: 4.8e-4 to 3.0e-5 (4.01 and 4.01), mode 1. L/ℓ = 8: the deviation fell to 1.4e-8 of u0, no pattern. Largest h_sub L: 0.0076. No step refused |
| B4, passive linear reaction–diffusion | §6.2: ratios 4.02 and 4.01; equilibrium 10.000; smallest half-step heat −1.1e-18 pJ, rounding against the −1e-12 pJ check |
| B5, switch-on from a trace | Quadrature against exact ΔG in the first step: 27%, 11% and 0.07% at traces of 1e-12, 1e-9 and 1e-6 mM; below 1e-4 from the second step |
| B6, a mixed node | Quadrature heat against a SciPy dissipation integral: 2.0e-5, 2.35e-6 and 2.85e-7 (ratios 8.50 and 8.26); never negative; W − H − ΔG at most 2.7e-20 pJ |
| B7, the standard-potential term | §3.3: with it every heat ≥ 5.4e-5 pJ; without it −1.3e-6 pJ from the first step, down to −2.4e-5 pJ |
| B8, the stage condition near depletion | §4.2's table |
| B9, turnover's closed form | 1.25e-6, 1.53e-7 and 1.89e-8 (8.19 and 8.10) |
| 2c, the corrected stage condition | A ⇌ B with K = 10, started at c_B/c_A = 1e4 so that it runs in reverse. Over h (k_f + k_r) from 0.05 to 3, the signed form read 0 below 1.1 and admitted steps up to 1.5. There the deviation shrinks by R = 0.0625 against an exact 0.223. The corrected form admitted up to 0.55 and refused from 0.9. The one negative stage, at 3, was refused under both. Every admitted step's heat was positive, at least 1.1e-11 pJ near equilibrium |

**The correction this changes** (§4.2). Probe 2's own stage check used the signed net rate for
passive routes. Its passive cases ran forward at small h k, so their results stand, but they do not
test the condition. Probe 2c does.

**What the probes did not test:** the operator itself on the engine, which does not exist yet; JAX
and GPU behaviour; the composite's contract plumbing for this operator. C1 covers the last.

### 10.3 Proposed before code (for the lead)

- **C1, the contract fit, by an in-process probe operator.**
  - **What.** A probe script defines the proposed operator class in its own process, registers it at
    run time, and leaves the snapshot's source on disk unchanged. It runs probe 1's chain with the
    Schnakenberg network inside the composite.
  - **What it must show:**
    - the field map (one owner per row);
    - every host ledger at the species' floors;
    - the face-free energy world at rounding, and the negative controls;
    - zero multipliers bitwise idle;
    - restart and a vmap batch.
  - **When.** After D150 v1 lands, since it uses D150's adapter addition and helper. It de-risks the
    operator's code more than any other check.
- **C2, the mixed-world blindness of these bookings.** D150's probe 2 part C method, in a heredity
  world with a reacting pair at µM and nM: the bound/booking ratio for the docstring statement.
- **C3, stiffness relative to the split step.** Worlds with dt · L of 2 to 20 handled by sub-steps:
  the measured splitting order and the onset of any order reduction. It decides whether version 1
  refuses dt · L > 1 or admits it with sub-steps.
- **C4, finding 3 on the engine as it is.** A neutral species through a junction with dt P A/V near
  and above 1: is the run refused (domain), or silently oscillatory? This informs question 7, which
  also bears on D150 v1.
- **C5, MG0c's second world.** The network in cells with D150's exchange and faces, against the
  three-compartment linear stability analysis (NumPy). It needs D150 v1.

## Appendix A. Equations for the independent references

The references are written from these equations, not from engine code.
- Units are @3's: fmol, pL, mM, s, m.
- RT = 2.5773 pJ/fmol at 310 K.
- κ_f = D_f A_f/L_f in pL/s.

**Node kinetics.** At node i, with c = n/V_i and route rates J_r(c) from §2.2:

    dn_s/dt = Σ_r ν_sr J_r + Σ_{f∋i} κ_f (c_j − c_i) + (other writers),
    J_mass_action = m F k V ∏ c^α;   J_MM = m F V k_cat c_E c_S/(K_M + c_S);
    J_passive = m V c0 k_f [exp(Σ α ln a) − exp(Σ β ln a + Σ ν μ°/RT)],   a = c/c0.

**Factors:** x^n/(K^n + x^n) for activation and K^n/(K^n + x^n) for inhibition, evaluated as
exp(−logaddexp(0, ∓n(ln x − ln K))).

**The half-step.** SSPRK(3,3) in Butcher form (§4.2), with weights (1/6, 1/6, 2/3) at stages
(0, 1, 1/2), and the stage condition h_sub max L ≤ 1/2, where

    L_s = [Σ_driven max(−ν_sr, 0) J_r + Σ_passive (max(−ν_sr, 0) J⁺_r + max(ν_sr, 0) J⁻_r)] / n_s,
    J⁺_r = m V c0 k_f exp(Σ α ln a),   J⁻_r = m V c0 k_f exp(Σ β ln a + Σ ν μ°/RT).

The unidirectional fluxes are used, never the signed net rate of a passive route.

**Free energy.** G_i = RT Σ_s n_s (ln(n_s/V_i) − 1) + Σ_s μ°'_s n_s, with
μ°'_s = RT (μ°_s/RT − ln c0). The increment form over a half-step from a (start) to a + δ:

    ΔG_i = RT Σ_s [δ_s (ln(a_s/V_i) − 1) + (a_s + δ_s) log1p(δ_s/a_s)] + Σ_s μ°'_s δ_s.

**Bookings.**
- **Driven only:** W = ΔG and H = 0.
- **Passive only:** H = −ΔG and W = 0.
- **Mixed:** H = h_sub Σ_k b_k RT Σ_passive A_r J_r(Y_k), where
  A_r = Σ α ln a − Σ β ln a − Σ ν μ°/RT; and W = ΔG + H.
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
