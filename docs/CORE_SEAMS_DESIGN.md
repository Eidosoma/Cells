# Core seams (D194 step 2): cycles, populations, binding, heat booking and laws as modules (design)

*Status: proposed, 17 November 2026, for the lead. Docs only, with no engine code. The code was
read at main df2b910b and is cited `file`:line there, by today's path under `src/cells/`. Where
D188's move-2 draft moves a file, its new folder follows in brackets
(`/mnt/workspaces/Cells/d188-step0-20261116/evidence/plan-fa19d80c/move2-draft.json`). The
core-fixes branch is cited at 79905c57. The note was checked against the lead's rulings on the
moves note, added on main at cbc52577 (its §17). Tags: **(code)** read in the code; **(cf)** built on
core-fixes, not yet landed; **S** this note's own reading, derivation or proposal. The pass is
built after D188's move 2, so the design is written for the new folders.*

**Engine models it runs** (AGENTS.md):
- `resolved_pump_tissue@3` with its kinds, alone and under `resolved_pump_composite@1`;
- with `isopotential_partition@1` and `cell_owned_compartments@1` for the populations' lifecycle
  (§4).

## 0. The plan

**One rule for every seam (**S**).** A piece joins by declaring five things, and nothing else names
it:
1. **its entities,** each on a host with two resolved ends: a patch (its cell and its outside
   node), a junction (its two cells), and later a route between two pools;
2. **the rows it reads and moves,** as species at a named end, with signs and units;
3. **its fields,** each with its roles: evolution, partition (extensive, intensive, history or
   structural), energy (heat, work or stored) and monotonicity;
4. **its step terms:** a charge slope, a material slope and a definition-time bound;
5. **its interface ID** (`cells.cycle_law@1`, `cells.kind@1`, ...), registered into the build's
   registry.

The core resolves these when the model is built, into value-free structure that enters the
compile key.
- Values stay layout data, so a parameter change reuses the executable (P5).
- An undeclared piece is absent: no field, no kernel and no hook call. So a world that does not
  declare it keeps its programs (A4), with crossrev and G1 unchanged.

**The seams:**

| | Seam | Proposal (**S**) | First consumers | Agent-days |
| --- | --- | --- | --- | --- |
| A | Cycles (§3) | One membrane-cycle kind. Populations sit on their own axis, any number per host. Each law declares stoichiometric modes on N/P ends. The kind computes each mode's ΔG from the registry and books rows, heat, work and stored energy. Built in place in `cells.transporter@1`, with version 1's layout kept for FR-4 and FR-5 (A3) | The cardiac exchanger, Na⁺/K⁺ cycle and SR uptake (H2); mitochondria (M1); finite fuel | 4.5–6.5 |
| B | Populations (§4) | One population concept for @3's populations and the kinds'. Declared field roles drive close, split and retire, with closure through the host's activity. One availability rule, with the routing door able to scale @3's channel availability. Refusal 4 checked per move, not by lists of IDs | Composition's gap 4 (c); CaMKII (H2); host C (M6) | 3–5.5 |
| C | Binding (§5) | One rapid-binding closure for a declared set of ligands and their binders, with multi-form rows in the registry. Laws declare the forms they move | The cardiac Ca²⁺ buffers (H2); mitochondria's H⁺ and Mg²⁺ (M1) | 3–5 |
| D | Heat booking (§6) | One declared booking per mover class (tableau, trapezoid or exact), with monotonicity declared. The trapezoid is written once, in the core, for every class | Cardiac H1; mitochondria M3; GARD's declared non-monotone heat | 1–2, plus 2–3 on branch X |
| E | Fuel (§7) | Adopt core-fixes ff5ca5ff and 0a00ba6e as built. Extend the potentials check to kinds and to reaction free energies. Moiety ledgers through §7.4 (p)'s deferred hook | Finite fuel; the cardiac screen's C3 | 1–1.5 |
| F | Laws as modules (§8) | A law template; one module per law; a law registry that kinds query by interface; operators registered as kinds are; `cells.modules` as the stable import surface; moved laws naming their originals | Every new law; GARD's family | 3–4.5 |
| G | Run view (§9) | The visualizer's three format items, with item 1 as a general rule of the writer | FR-11's loops; every new kind's view | 0.5–1 |

**The order** (§13):
- **Step 0:** two probes, each with its criterion written first: the cardiac booking probe and
  mitochondria's P1. Their results decide D's branches.
- **Then in parallel:** F's registry, D, E and G.
- **Then A and C,** with B's part for today's kinds beside them and their independent references
  in parallel; then B's part for the cycle kind; then the gates, at each merge.

**The estimate** (§13): 20–31.5 agent-days, plus 2–3 on branch X; about 9–13 working days elapsed
with five owners and a references agent.
- About 15.5–26 of it replaces work the consumer notes already counted: mitochondria's P1 and M1,
  the cardiac booking and part of H2, composition's level (c), and finite fuel's kind path.
- The rest, about 4.5–5.5, is mostly D188's refactors (F) and the run-view items (G).

**For the lead** (§12):
- how A is built: A3 keeps §0's rule, while A1 is cheaper but needs the rule waived for FR-4's
  and FR-5's worlds;
- finite fuel's home, the booking's branch and field roles;
- the registration tables' scope and the moved-law reading.

Three questions are marked for the user.

## 1. Where the needs repeat

| Need | Cardiac (D183, D184) | Mitochondria (D193) | Composition (D191) | Finite fuel (§17) | GARD (D192) | Seam |
| --- | --- | --- | --- | --- | --- | --- |
| Several roles per cycle, any integer stoichiometry, fuel at either end or none | The exchanger: 3 Na⁺ in, 1 Ca²⁺ out, no fuel (§3.6); the Na⁺/K⁺ cycle (§2) | Complexes (ten H⁺ when lumped), synthesis with c H⁺ per 3 ATP, nucleotide exchange, Pi/H⁺ symport, K⁺/H⁺ exchange (§1.2, §1.4) | — | ATP, ADP and Pi moved by the pump (§17.2) | — | A |
| Several populations per host, each facing a chosen end | The exchanger 80% to the bulk and 20% to the subspace; CaMKII's two copies of a law (§3.6, §3.7) | Every cycle on host C's one bounding patch (§1.2) | Transporter populations as entities with units (§13.4 Q5) | — | — | A, B |
| N/P orientation; roles at a patch's outside node | Pools, later | Host C: N is the patch's outside node (§1.1) | — | — | — | A |
| One thermodynamic form; one authority for potentials | The screen (§3.8); C2 and C3 (§3.9) | One cycle form (§1.4); registry potentials (§1.5) | — | D3 (§17.3 item 2) | Local detailed balance at the kernel (§2.4) | A, E |
| Rapid binding of several ligands; multi-form rows | Ca²⁺ buffers CMDN, TRPN, BSR, BSL, CSQN (§3.3, Q8) | H⁺ and Mg²⁺ on ATP, ADP and Pi; base-form valences (§1.3, Q3) | — | — | — | C |
| A heat booking that cannot go negative when a flux reverses | Channels at E_K; the exchanger's reversal (§3.8, Q13) | Synthesis and exchange reversing (§2.3, Q4) | — | — | Event heat, declared non-monotone (§2.4) | D |
| Exact energy closure at large steps | — | The ΔΨ mode: a step limit of 0.05/rate against 1/rate (§2.3) | — | — | — | D, branch X |
| Close, split and retire a kind's per-slot fields | — | Populations later (M8) | Gap 4 (c), Q4 (§13.2) | Finite rows split like any species (composition §13.2) | — | B |
| A factor into @3's channel availability | CaMKII's φ (§3.7, Q10) | Later regulation (§6) | — | — | — | B |
| A material slope at a small node | — | The matrix (M6) | — | D4 (§17.3 item 4) | — | E |
| A conserved quantity beyond today's ten ledgers | — | Adenine, NAD, Q and cytochrome c moieties (**S**) | — | The moiety check (§17.4) | Its own counts, in its family | E |
| Laws declared, cited and registered | 8 channel laws, 2 cycles, the release, a buffer read, CaMKII (§2) | Six or more cycle laws (§1.2) | — | — | 3 laws and 2 operators now, in its own family (§1.4, §1.5) | F |
| Run-view declarations of cycles | KindView, for FR-11's loop (§7) | ΔΨ, Δp, N→P flows (§8) | — | — | Event tables (its §5.3; not here) | G |

**Duplication already in the code** (code):
- **Closed lists that a new piece must edit:**
  - the transporter's and the passive routes' law tuples (`models/inner_kinds/transporter.py`:100,
    `passive_routes.py`:72 [`kinds/`]);
  - @3's channel table and the spec's codes, permeant ions and gate counts
    (`models/inner_laws.py`:132–170; `core/surface_pump_v3_spec.py`:56–66 [`definitions/`]);
  - the operators' dictionary (`models/operators/__init__.py`:29–52 [`operators/`]);
  - refusal 4's known kinds (`models/operators/compartments.py`:73–81 [`operators/`]).
- **Meaning keyed on a field-name suffix:** the heat and work roles (`models/operators/contract.py`:11–15),
  the dissipation check (`models/surface_pump_v3.py`:1713, 1735–1742) and the run view's
  monotone note (`run_view.py`:200, 1678 [`records/`]).
- **The same physics written in each kind:**
  - each kind resolves its own host ends (`transporter.gather`, `passive_routes._ends`);
  - each computes its own ΔG and heat (`transporter.py`:564);
  - each writes step terms for its own laws only (`transporter.bound_rate`, :420–422, and
    `stage_term`, :602: the proton law alone).
- **Three pump representations by step 3** if nothing changes: @3's `PumpLaw` on maintained pools
  (`inner_laws.py`:119–128, 183–203), `cells.transporter@1`, and a cycle kind for the new
  consumers. Likewise two rapid closures.
- **Version-1 refusals that each consumer meets separately:**
  - one transporter per patch (`transporter.py`:245–249), the fuel node fixed to the inside cell
    (:188–192), and a stoichiometry of 1 to 4 (:118);
  - one stage read (`proton_buffer.py`:64);
  - every two-form row inert (`core/species_registry.py`:369–397 [`registry/`]);
  - no closer beside a kind (`models/pump_composite.py`:594–598), and no operator factor on a
    kind's control (:610–615).
- **Two ways to scale channel availability:** operators' `CONTROL_FACTORS`
  (`species_regulated_availability.py`:81, 863), and the routing door once B extends it (§4.3).

## 2. Scope: hosts, and what the pass leaves out

**Hosts (**S**).** A host is any entity with two ends, each resolved at binding to a node index.
- The core builds one host table per structure, as layout data: host kind, end-a node and end-b
  node.
- Each host kind has a voltage rule: φ(a) − φ(b) for a patch and for a junction; zero for a route
  between two pools.
- Kinds read their ends through the table, never through a host's own fields. Patches and
  junctions are its first entries.
- A route between two pools joins later as a host kind of its own, with no change to the kinds.
  It is needed for the cardiac SR uptake, leak and release, and for a resolved IMS.

**In the pass:** seams A–G (§0).

**Not in the pass, and where each item goes:**
- **Pools at the cell's potential** (cardiac §3.2 (a), its Q6): the core owner's work in H2.
  - It opens subspace calcium, which version 1 closes, so it goes to the user if it changes an
    approved closure (D184).
  - The host table admits a pool route later.
- **The channel-law seams of cardiac §4.5 (a)–(c):**
  - Ca²⁺ and Cl⁻ as permeant ions;
  - per-law gate counts, domains, reads and openings;
  - a linear driving force;
  - coefficients as data.

  These are H1's (6.5–8.5 days). The law template reserves their fields (§8.1).
- **A kind's read of @3's channel current** (ORd's release, cardiac §3.5): H2's. §4.3 sketches it
  as the door's value mode.
- **The compartment map's address** "species S in compartment C" (INNER_MODEL_V4_DESIGN §9.2,
  B2): mitochondria's M6.
- **The implicit cycle block,** a new IMEX ID: mitochondria's M2, only if P1 asks for it.
- **The species cap above 16:** a D148 change per consumer (D165).
- **Module stage 1** (MODULE_SYSTEM_DESIGN §2):
  - threading `registry=` through the parse and build call sites;
  - the CLI flag and the manifests' record of modules;
  - the conformance kit, the example package and the declarations manifest.

  The pass gives them one surface to build on (§8.7).
- **GARD's run-view additions** (its §5.3) and the RNG contract (MODULE_SYSTEM_DESIGN §5):
  GARD's G1.

## 3. Seam A: membrane cycles

### 3.1 Entities and state

- **A population:** one law on one host. It carries:
  - an orientation, which host end is N;
  - a capacity k (fmol cycles/s);
  - the law's parameters;
  - an availability control.

  Populations sit on the kind's own axis, `cycle_population`, not on `membrane_slot`, so a host
  carries any number of them (**S**).
- **A mode:** one stoichiometric cycle of the law, with integer ν_{s,e} for each species s at end
  e (N or P).
  - A population's net flux of row (s, e) is Σ_m ν_{s,e,m} J_m.
  - The exchanger's Na⁺-leak mode (cardiac §2, its INaCa row and D2) is a second mode, not a
    separate booking (**S**).
- **Rows.** Every row a population touches is either moved or held.
  - A held row is read and never moved. The one-writer rule (`held_rows`) applies, and its
    maintenance is booked as work, as `maintained_held_rows@1` books it today.
  - A moved row lands in the shared inventory (rule (c)). Finite fuel is moved rows, at either
    end (**S**).
- **State it owns:**
  - cycles, per population and mode;
  - heat, work and stored energy, per population;
  - held rows' supply record.

  All of it is cumulative, a history field in §4.2's terms.
- **Structure and values (**S**):**
  - structure: the declared laws, the number of modes and the largest number of rows in a mode;
  - values (layout data): ν, the row indices, the orientations, the capacities and the
    parameters.

  So a new stoichiometry reuses the executable.

### 3.2 The law contract: thermodynamics in the kind, kinetics in the law

- **The kind computes each mode's free energy from the registry:** ΔG_m = Σ ν μ̃_{s,e}. Each μ̃ is
  the sum of:
  - the registry's μ° (one authority, B3);
  - RT ln of the free activity that the stage read gives;
  - z F φ at that end.

  No law carries a ΔG° of its own (mitochondria §1.5; INNER_MODEL_V4_DESIGN §10.2).
- **The law supplies the kinetics:** a pure kernel S_m(activities, V, parameters) ≥ 0. The kind
  forms J_m = k a S_m (1 − e^{ΔG_m/RT}).
  - Then J_m ΔG_m ≤ 0 at every state, and J_m = 0 exactly at each mode's equilibrium (**S**).
  - This is the form of FR-4's pumps (`processes/proton_pump.py` [`laws/pumps/`]).
  - Hill's diagram method writes a steady-state cycle's net flux as such a product, with a
    non-negative factor (Sources).
- **A screen item, not yet a claim.** Whether ORd's exchanger (after Kang and Hilgemann) and its
  Na⁺/K⁺ cycle (after Smith and Crampin) factor in this form at the registry's potentials is
  checked first. The cardiac lane's component references do it from Text S1's equations, which
  this note did not read. Mitochondria's empirical nucleotide exchange (its §1.4 item 2) is
  screened the same way.
- **The fallback, for a law that does not factor:**
  - the law supplies the net flux J_m itself;
  - the kind enforces the sign: its domain refuses any stage where J_m ΔG_m > 0 beyond rounding,
    and the screen's grid is checked at parse;
  - a cycle that fails is refused, never repaired (cardiac §3.6).
- **A law with an implied ΔG° of its own** (ORd's Na⁺/K⁺ rate constants, C3) declares it. E's
  check refuses one that disagrees with the registry (§7.1).
- **The domain:** |ΔG_m/RT| ≤ 80 per mode, as today (`processes/proton_pump.py`:30). A law may
  declare the one-sided form, a ≤ 80, for strongly exergonic modes (mitochondria §1.4), as a
  declared change.
- **Charge and moieties, checked at parse:**
  - each mode conserves charge: Σ_e Σ_s z_s ν_{s,e} = 0;
  - each mode conserves every moiety the registry declares (§7.3);
  - the transported charge n_q = Σ_s z_s ν_{s,P} is derived, never declared (**S**).

  A planted imbalance is refused.

### 3.3 The hooks, written once in the kind

- **`rates`:**
  - gathers the end activities through the host table and the stage read, then computes J per
    mode;
  - moves Σ ν J into the cell and outside rates;
  - books heat −Σ J ΔG and work for held rows;
  - gives `stored_pJ_s` for moved rows' standard part (§3.4), and `membrane_flux` for charged
    moves;
  - its `valid` is each law's domain.
- **`stage_term` and `material_term`** (cf 0a00ba6e): the electrogenic conductance
  n_q F |∂J/∂V| at both host ends, and, per node, the largest |ν ∂J/∂n| of a row moved there.
  - **Who supplies them (**S**).** By default the kind takes the derivatives of the law's J by
    forward-mode differentiation (`jax.jvp`) at the stage's inputs, so a voltage- or
    state-dependent S is handled exactly.
  - A law may supply analytic slopes instead, as FR-4's `electrogenic_conductance_S` does. A test
    compares them with finite differences on the screen's grid, and a planted wrong slope must
    fail it.
  - At a static head with S constant, the slope is n_q² F² k S/RT: mitochondria §2.3's rate.
  - **The cost:** one tangent per slope, only in worlds that declare the kind.
- **`bound_rate`:** B7's definition-time term at each free node, at the declared amounts, with S
  and e^a at their forward maxima. Today `transporter.bound_rate` gives it for the proton law
  only.
- **The rest:**
  - `held_rows` and `moved_rows`;
  - `ledger_terms`: cell, outside, `produced` for the chemistry, heat, work and stored;
  - `domain`;
  - `readouts`: rate, ΔG and chemical drive, per mode;
  - `view` and `view_sets` (`per_cycle` per mode, §9);
  - `check_definition`: a registry potential for every row, charge, moieties and any implied ΔG°.

### 3.4 Finite and held fuel

- **Finite fuel is moved rows.** The stored part per cycle, in @3's 1 mM frame, is §17.2's:
  RT (Σ ν μ°/RT − (Σ ν) ln c0).
  - One helper gives both `stored_pJ` and `stored_pJ_s`.
  - `produced` records the chemistry's net change, so the global ledger `total` closes (§7.4 (m)).
- **§5.2's boundary stays in version 1:** finite fuel at a node with a dynamic proton row is
  refused, fail-closed. The one exception is a node that the binding closure holds (§5), where no
  transformed potential is used (mitochondria §1.3).

### 3.5 Options, and the end state

**The end state (**S**):** one cycle kind for every membrane cycle.
- @3's built-in Na⁺/K⁺ and Ca²⁺ pumps stay @3's in this pass. Every G1 world with pumps, and the
  registered protocols that have them, run those pumps.
- Moving them into the cycle kind is a later D167 move. It needs its own results-gate case and a
  parity check (§8.6), and it waits for a consumer, such as a dividing cell with the kind's pumps.
- This answers composition's Q3 (§4.5).

| Option | FR-4 and FR-5 | §0's invariance rule | Duplication | Finite fuel (ruling D1, §17.5) |
| --- | --- | --- | --- | --- |
| **A1. Generalise `cells.transporter@1` in place,** with one layout (the population axis) | Their programs change. Their records must stay bitwise (**S**: one population per patch, the same arithmetic per element and the same scatter order; signed zeros reported apart, as G1 does). The check is the FR lane's own quick compares: FR-4's rung_1ms --quick against `dt-3c10b833-dry/quick`, and FR-5's arm-R part against `dt5-7c8bfa47-dry`. If a record moves, their development evidence re-runs while it is still proposed | **Waived** for the kinds set's FR-4 and FR-5 worlds, which use none of the new features: records bitwise in place of programs, as for the raw-sum fix (INNER_MODEL_V4_DESIGN §7.5, "What changes") | None: one kind and one layout at once | Stays on `cells.transporter@1`, as D1 rules. The pass builds the moved-row path, so step 3 builds only R-fuel's world, and the FR lane's `finite-fuel-step2-partial.patch` is superseded |
| **A2. A new kind** (`cells.membrane_cycles@1`, mitochondria's name) beside a frozen transporter | Programs identical | Kept | Two kinds until a retire. After FR-4's and FR-5's judged runs, their worlds are re-expressed on the new kind, with an agreement test at rounding against their judged records. The transporter then retires on a D187 retire list, which goes to the user in its batch | Either on the frozen transporter, as the FR lane planned (D1 kept, the new kind re-hosting it later), or on the new kind, which departs from D1's "same kind path" and makes step 3's finite fuel wait for the pass |
| **A3. Generalise in place with two layouts:** an entry in version 1's form (at most one population per patch, today's two laws, held fuel) keeps today's fields and hook code, chosen statically on the structure entry (`declared_fields`, the passive routes' `Factored` precedent, §7.4 (n) 6); any other entry takes the population axis | Programs identical | Kept | Two layouts in one kind until FR-4 and FR-5 move to the general layout, with their records compared bitwise; then version 1's layout is deleted. Cost: about 0.5 day more than A1 for the static dispatch | As A1: on `cells.transporter@1`, through the general layout, so R-fuel's world selects it |

- **The discriminator for A1:** whether FR-4's or FR-5's judged runs start before the pass
  builds.
  - Nothing registered pins the transporter today: both protocols are PROPOSED, with
    development evidence only (the FR lane's handoff, 16 November).
  - So bitwise programs for them are a rule the lead can waive, not a constraint of evidence.
- **Recommended: A3,** which keeps §0's rule, one kind ID and D1's kind path.
  - A1 is cheaper if the lead waives the rule for those two worlds before their judged runs.
  - A2 if the lead wants no edit to the transporter's module at all before those runs.
- **The name.** A1 and A3 keep the ID, since optional fields keep an interface's major
  (MODULE_SYSTEM_DESIGN §2.3).
  - A rename to the mechanism's name moves the kind ahead of the passive routes in the canonical
    sorted order, so its fields move in the state types.
  - Under A3 that would change FR-4's and FR-5's programs, so the rename waits for version 1's
    layout to go (**S**).

## 4. Seam B: populations

### 4.1 One concept

- **What a population is:** a law on a host, with units or capacity, parameters and an
  availability.
- **@3's channel populations already are one:**
  - their host, abundance, law code and availability (`control.channel`) are layout and control;
  - their gates, transfers and heat are state;
  - the partition maps them, each taking its patch's fraction (`models/operators/partition.py`:7–8;
    retirement :30).
- **The pass makes the kinds' populations the same concept (**S**).** Each entity of a kind declares
  its host through a structural field, a host index. So the adapter's closure, which propagates
  from a cell to its patches and from a patch to its populations (`contract.py`'s `CLOSES`),
  reaches the kind's entities as it reaches @3's.

### 4.2 Field roles, and the lifecycle

Each per-entity field of a kind declares its partition role (**S**):

| Role | At a split | At retirement | Examples |
| --- | --- | --- | --- |
| extensive | Divided by the host's fraction, with the anchor rule (fl(a C), C − fl(a C); composition §4.4), so the daughters sum to the parent exactly | Padded: its amount went to the daughters | Capacity or units, amount increments |
| intensive | Copied | Padded | Gates, saturation parameters |
| history | Each daughter starts from 0 | Moved into the closer's record; `adjust_inner` adds it back | Cycles, transfers, heat, work, supply records |
| structural | As declared: law, host and orientation | Padded with its declared fill | Law index, host index |

- **One implementation.** The adapter implements close, split, retire and open once, for every
  role.
- **Close acts through the host's activity, not through availability (**S**).**
  - The adapter already closes a host's activity mask at the view (`membrane_active` for a patch),
    and observation sees the view, under door S's merged records.
  - The core gates every population's rates by its host's activity, through the host table, as
    @3 gates its channels by `channel_active`. That is static, present only where a closer is
    declared (composition's C5).
  - Writing 0 into a kind's availability control at the view would not work. The composite
    refuses a factor on a kind's control (`pump_composite.py`:610–615), because observation holds
    only today's schedules, so the observed rows would show a closed population running.
  - Per-node fields at a closed node take their declared fills, as @3's padded fields do.
- **Fail-closed.** A kind that declares no roles stays refused beside closers. The refusal in
  `pump_composite.py`:594–598 is lifted only for kinds whose every per-entity field declares a
  role.
- **@3's own pump and channel fields take the same roles,** in place of the partition's
  hand-written lists. That is host-side, so no program changes.

### 4.3 One availability rule, and the routing door into @3

- **Every population's availability is a control in [0, 1]** (rule (d)). It may follow a schedule
  (§7.4 (l)), operators may factor it at the step (`CONTROL_FACTORS`, held), and kinds may factor
  it at each stage (the door).
- **Extend the door's sinks to @3's own populations (**S**).**
  - A channel population may declare `factors`, a list of source IDs, in its definition entry, as
    a passive route does (§7.4 (n) 6). Where it is omitted, the definition and its fingerprint
    are today's.
  - `_routes` (`surface_pump_v3.py`:436–471) then admits @3 as the sink of its own `channel`
    field. The rule "a sink routes its own control fields only" (:463) holds, since @3 owns that
    field.
  - The door already runs before @3's channel rates (:918–945), so nothing is reordered.
  - Without such a population the door stays absent (A4).
- **The order with operators' factors (**S**):**
  - the composite multiplies the held control first (`pump_composite_adapter.control_view`,
    :470–472);
  - the door multiplies the stage's copy afterwards;
  - so a routed slot is (held × Π operator factors) × Π kind factors, each product a left fold
    in declared order, and its rounding is fixed.
  - The composite's refusal of an operator factor on a kind's control (`pump_composite.py`:610–615)
    stays, so the two meet only on @3's own controls.
- **CaMKII's mixing** (cardiac §3.7): two populations of one law, sinks of φ and of 1 − φ. The
  door forms products of factors, not complements, so the source exposes φ and 1 − φ as two
  factors (**S**).
- **A value mode, H2's (a sketch).** A source exposes a stage quantity, such as a channel
  population's Ca²⁺ flux, into a reader's control slot by replacement, with the reader's
  `control_domain` as its rule. That is ORd's release. It is not built in the pass.

### 4.4 Admission per move: refusal 4, version 1.3

Refusal 4 checks each move, not each kind (**S**).
- **Why per move:** a hook's presence is per kind, but coverage is needed per law. Today's
  transporter has a `stage_term`, yet its neutral law has no term of any kind (§17.3 item 4).
- **The check** reads `moved_rows`, which already gives (species, node, law ID) triples
  (`transporter.moved_rows`), and each law's declared step terms from the law registry (§8.1).
  For every row a kind moves at the compartment's node or across its bounding patch:
  - a charged row's law declares a charge slope (`stage_term`);
  - a neutral row's law declares a material slope (`material_term`) or a definition-time bound
    (`bound_rate`).
- **A stage read** declares its rows. A source kind, with no moves and no charge, is admitted.
- **Fail-closed:** a move whose law declares no term is refused, naming the law.

`ROUTE_KINDS`, `READ_KINDS` and `FACTOR_KINDS` (`compartments.py`:73–81) then go. The
transporter's neutral law is admitted once it declares D4's term (§7.2), which closes
CLOSED_COMPARTMENT_DESIGN §3.4.1's open item.

Version 1.2 admits that law beside a compartment today with no term. So before the change, main
is searched for any world the per-move check would newly refuse, as was done for D3's check
(§17.5), and the lead hears of any it finds.

### 4.5 Answers to composition's questions for the core (its §13.4)

1. **Idle pumps at closed patches.** By the host's activity, the first of the two options there:
   @3's pump and calcium-pump rates are gated by the view's `membrane_active`, as every
   population's are (§4.2).
   - It is static, present only in worlds that declare both a closer and a pump law (C5's
     condition), so pump-free division worlds keep their programs.
   - Padding `pump_capacity` instead would refuse replacement@1's provider beside a closer.
2. **The pump's history at retirement.** Every field with the history role: `pump_cycles`,
   `pump_dissipated_energy_pJ`, the metabolic work and the calcium pump's fields. They are read
   back through `adjust_inner` unchanged.
3. **One pump representation.** @3's built-in pumps stay @3's in this pass (§3.5). Capacity as
   state is an extensive field of the population concept, for @3's pumps and the kinds' alike.
4. **Kinds beside closers.** Yes, by declared field roles, with a hook only for a field that no
   role fits.
5. **Transporter populations as entities with units.** Yes: the cycle kind's populations, on their
   own axis with a host, each taking its host patch's fraction.
6. **Held fuel at division.** A held row is an inventory row, so it splits its anchors by the rule.
   The supply record is history and retires with the parent's patch.
7. **R5 with growing capacity.** The kind's `bound_rate` takes the schedule's largest capacity,
   since it sees the spec and so the schedule, as insertion's area bound does.

## 5. Seam C: binding

### 5.1 One closure

The pass generalises B4 to a declared set of ligands (H⁺, Mg²⁺, Ca²⁺) and their binders at named
nodes (**S**).
- **Each binder row has forms in the registry:** `forms`, each with an ID, its ligand counts and
  its μ°/RT, the base form at the row's valence.
- **What the rows hold:**
  - each ligand row holds its total equivalents, free plus bound, counted from each binder's base
    form (mitochondria §1.3, FR-4's §3 counting);
  - each binder row holds its total.

  Charge depends on totals only, so the field solve stays exact as it stands (FR-4's §3
  argument).
- **The solve, at every stage:**
  - one ligand: B4's log-space bisection, 80 fixed steps (`processes/rapid_proton_buffer.py`:46
    [`laws/reactions/`]);
  - two or more: a safeguarded Newton with a fixed iteration count (**S**), deterministic on the
    device, with no loop count that depends on data.

  The read gives every law the free forms it needs (free h, free Mg²⁺, MgATP²⁻), as B4 gives free
  h today.
- **Energy:** the speciation minimum G*, less the stored rows' own terms, as B4 books it
  (`proton_buffer.py`:300–304). Its derivatives are the free base forms' potentials, so every
  route books against free forms (mitochondria §1.3).
- **The envelope:** the closure's lag behind the kinetic system, per ligand, as B4's, with a
  declared k_on per binding (D175's stand-in parameter).
- **One closure per node and connected ligand set (**S**).** Ligands that share a binder are coupled
  and are solved jointly. Reads on disjoint rows compose by today's rule
  (`surface_pump_v3._check_stage_rows`, :1347–1365).

### 5.2 Laws declare the forms they move

- `check_two_form_rows` refuses every mover of a two-form row (`species_registry.py`:369–397).
- **In version 2 (**S**),** a mover is admitted when its law declares its stoichiometry in base forms
  with every ligand written out, as the cycle kind's modes do (mitochondria §1.3's table). The
  closure's totals then stay exact.
- Any other mover is still refused, and the check names the law.

### 5.3 FR-3's site binding

`site_occupancy@1` (an operator, kinetic Langmuir binding) is the detailed representation of the
same mechanism, and the closure is its rapid limit. Both take K from the registry
(ΔG°_b = RT ln(K_d/c0)).
- Version 1 couples them in no way.
- When B8 lands, D175's "represents" key, one representation per scope, would refuse both on the
  same ligand and binder at one node.

### 5.4 Options

- **C1. Generalise `cells.rapid_proton_buffer@1` in place.**
  - Its one-ligand declaration keeps today's fields and kernel, by static dispatch on its
    structure entry (`declared_fields`; the passive routes' `Factored` precedent, §7.4 (n) 6).
  - So FR-4's and FR-5's programs stay identical.
- **C2. A new kind** (`cells.rapid_binding@1`) beside a frozen B4, retired as A2 is.
- **Recommended: C1, whatever FR-4's timing,** since its one-ligand path is today's code.
- **The name.** A rename to `cells.rapid_binding@1` keeps the canonical order: between
  `cells.ph_condition@1` and `cells.transporter@1`, as today (**S**). So it moves no field, to be
  confirmed by crossrev.

## 6. Seam D: heat booking

### 6.1 One table, declared per mover class

| Booking | What it books | Non-negative per element | Energy ledger | Used today by |
| --- | --- | --- | --- | --- |
| Tableau (the default) | The tableau's quadrature of the dissipation rate | No. ARS(2,2,2)'s δ < 0 books a negative increment where a power falls by more than about 59% within a step (cardiac §3.8) | Within `ENERGY_RTOL`, second order | Every route |
| `trapezoid_nonnegative@1` | ½ dt (q_start + q_end), each power non-negative at its own state | Yes, by construction | Within `ENERGY_RTOL`, second order | Junctions (`surface_pump_v3.py`:1202–1213); the opt-in membrane process (:1240) |
| `exact_free_energy_heat@1` | Each route's divided-difference share of each row's exact free-energy decrease | A step with a negative share is refused ("negative exact share") | To rounding | Neutral passive routes alone on their rows (§7.5) |

- **Selection.**
  - Each law declares the bookings it admits.
  - The definition picks one per mover class: channels, junctions, and each kind's routes. This
    generalises `junction_heat_booking` (`core/surface_pump_v3_spec.py`:53).
  - The default is the tableau, so a world that picks none keeps its programs.
- **The trapezoid and the exact booking answer different problems (**S**).**
  - The trapezoid keeps every element non-negative when a flux reverses within a step: channels at
    E_K, the exchanger's reversal, synthesis on an uncoupler. It holds the ledger at its
    tolerance.
  - The exact booking closes the ledger to rounding at large steps, but a flux that crosses its
    reversal within a step can give a negative share, which it refuses.
  - **So: the trapezoid for channels and cycles, and the exact booking for neutral routes on rows
    no other mover moves, as ruled.**
- **Monotonicity is a declared property of a field (**S**).** A field declares its energy role (heat,
  work or stored) and whether it is monotone.
  - The checks and the run view read these declarations.
  - Today's suffix rule becomes the default for undeclared fields, so programs are identical.
  - GARD's event heat is heat, declared non-monotone, closing against a state function (its §2.4).

### 6.2 The trapezoid, written once

- **The gap.** The kind hook `book(applied, start, end, control, p, dt)` receives no potentials
  (`core/kind_registry.py`:252–259 [`registry/`]), so a kind cannot evaluate its power at the end
  state.
- **The core does it once (**S**).** For each mover class booked by the trapezoid, after the tableau's
  combination:
  - it evaluates the class's heat rate at the end state with the last-stage potentials, as the
    junction booking does (:1202–1213). That is `channel_rates` for @3's channels, and a kind's
    `rates` at the end state's read, with the stage read and the door;
  - it books ½ dt (q_start + q_end) into the class's heat fields, where q_start is stage 0's
    power, already computed.
- **The cost:** one more evaluation per step of the booked classes' rates, with the stage read and
  the door, only in worlds that declare the trapezoid.
- The state is unchanged; only the heat fields' quadrature changes.

### 6.3 Branch X: the exact booking for charged rows and cycles

- **What §7.5 sketches.** The electrical part is the capacitor energy's change, exact for the
  linear capacitor through the step's mean patch voltage, V̄ Δq.
  - With affine potentials φ = A q + b and A symmetric, ΔE = φ̄ · Δq exactly, with φ̄ the mean of
    the step's start and end potentials (**S**).
  - A cycle's share is then its divided-difference affinity, Σ ν (μ̄_row + z F φ̄_end), times its
    cycles.
- **What it would buy** (mitochondria §2.3's table):
  - today's explicit booking limits steps near dt ΣG/C ≈ 0.05: FR-4's measured energy-ledger
    limit for constant-field routes (COMPARTMENT_PH_TRANSFER_DESIGN §7.2);
  - the stage rule allows dt ΣG/C up to 1, a step 20 times larger;
  - so it may decide mitochondria's branch E against branch I, which costs 6–9 agent-days.
- **What it does not do:** serve a crossing (§6.1). So it is a choice per mover class, and H1 does
  not need it.
- **Its scope (**S**):**
  - rows moved only by exact-booked movers, version 1's rule;
  - extended to charged rows where the electrical energy is local: a face-free compartment's
    node, where V_b = −q/C_b (FR-1 §3.1), so moving charge between the owner and its compartment
    changes only q²/2C_b;
  - elsewhere the capacitor couples every node through the field solve, so the scope would be the
    whole world.
- **When:** built only if P1 shows the energy ledger binding before the stage rule. Its split goes
  to the lead first, since §7.5's version-1 rulings (no groups, no scaling) bind it.

### 6.4 Step 0: two probes, each criterion written first

- **The booking probe** (cardiac §3.8):
  - a K⁺ leak while an injected current drives V through E_K, under ARS(2,2,2), on @3 as it
    stands;
  - **expected:** the dissipation check refuses the step. If it does not, the trapezoid's need
    for channels is revisited before H1.
- **P1** (mitochondria §2.3):
  - FR-4's proton law past its static head at large capacity, with n = 4, on host C and host P;
  - a ladder of dt ΣG/C from 0.01 to 2;
  - it records where the per-stage rule refuses, where the energy ledger refuses, and the error
    against an independent two-capacitor reference.

  Its result decides branch X, and mitochondria's branch E or I.
- **Both run on today's code, in CPU minutes,** with one exception:
  - P1's host-P arm puts the transporter on a cell's plasma patch facing a faced finite node.
    Probe P0 parsed that topology with no kinds declared, and whether the existing kinds parse
    there was not checked (mitochondria §2.3).
  - So that arm first checks the parse. If the parse is refused, the arm waits for A.
- P1 is mitochondria's own probe, run early: the lead's call.

## 7. Seam E: finite fuel's core part

### 7.1 ff5ca5ff (D3): adopt as built

- **What it does (cf).**
  - The operator contract gains `species_potentials(declaration)` → ((species, μ°/RT, c0 in mM),
    ...), with a default of none, and D152 implements it.
  - `species_registry.check_potentials`, run from `check_definition`, converts each declared
    potential to the registry's c0 (μ°/RT + ln(c0_registry/c0)).
  - It refuses one that differs from the registry's by more than 16 ulps of the magnitudes
    involved, naming the operator.
  - It is host-side, so no program changes. Every registered world and the kinds set parse under
    it (its message).
- **What the pass adds (**S**): the same check for kinds and for reaction free energies.**
  - A hook `standard_free_energies(declaration)` → ((stoichiometry, ΔG°/RT, c0), ...) on operators
    and kinds. A species' potential is its case with one species at ν = 1.
  - The check compares each with the registry's Σ ν μ°/RT, converted by (Σ ν) ln(c0_registry/c0).
  - It serves the cardiac screen's C3 (ORd's Na⁺/K⁺ cycle) and any cycle law with constants of
    its own.

### 7.2 0a00ba6e (D4): adopt as built

- **What it does (cf).**
  - `Kind.material_term(read, potentials, control, p, *, xp)` → [cells, then outside nodes], the
    kind's material slope (1/s).
  - `surface_pump_v3.material_rate` sums the kinds' terms per node, after the stage read and the
    door.
  - The IMEX step refuses any explicit stage where dt × its largest value, over active cells and
    non-held outside nodes, exceeds `EXPLICIT_STEP_BOUND`.
  - It is gated statically: the kinds, base and division crossrev sets matched, 12/12, 48/48 and
    36/36 programs (its message).
- **Notes (**S**):**
  - its node set includes faced outside nodes, which `membrane_rate`'s free-node set leaves out.
    That is right for material, since a faced node can also empty;
  - like `membrane_rate` (:1525–1526), it evaluates the stage read and the door again. Passing the
    stage's read to both is a later cost item, not a correctness one;
  - the cycle kind supplies the term generically (§3.3). If finite fuel stays on the frozen
    transporter (A2), the FR lane adds the neutral law's term, as planned.

### 7.3 Moieties: the first kind-declared ledger

- **The hook** is the one INNER_MODEL_V4_DESIGN §7.4 (p) left for its first consumer:
  `ledgers(declaration)`, values under their own names in `ledger_terms`, and `ledger_bounds`.
  `ledger_lists(structure)` (`surface_pump_v3.py`:1758–1767) then appends them, and the shared
  checks take them with no edit.
- **The registry declares the moieties (**S**),** for example adenine = ATP + ADP (+ AMP), each a
  linear form w_M over species.
- **The ledger is defined on producers, not on global totals (**S**).**
  - A global total against its start would fail in open worlds: a held or scheduled bath (such
    as mitochondria §7's ADP step), turnover and replacement all change totals legitimately.
  - So each producer of chemistry declares itself as one: a kind's `produced` record, or an
    operator's booked net production per species (D152's reactions).
  - For each declared moiety M and each such producer, Σ_s w_M,s × its cumulative net production
    of s is held to zero at rounding bounds.
  - Baths, schedules, turnover and replacement are not chemistry. The `total` ledger already
    closes every species with their terms, so open worlds are unaffected.
- **What it catches.** Every transport keeps a species' identity, so only chemistry can break a
  moiety: a cycle mode's chemistry, or a D152 reaction.
  - §17.4's planted error, a fuel stoichiometry off by one, fails it. With Pi +2 per cycle, the
    phosphate moiety (3 ATP + 2 ADP + Pi) changes by one per cycle.
  - The parse-time check on each mode's declared stoichiometry (§3.2) catches the same error
    earlier, where the declaration itself is wrong.
- **Its first consumer is finite fuel.** Mitochondria's NAD, Q and cytochrome c moieties follow.

## 8. Seam F: laws as modules

### 8.1 The law template

Every law module holds one declaration of its interface's type, its pure kernels, and a docstring
with its citation in our own words. Its fields (**S**):

| Field | Content |
| --- | --- |
| Identity | `law_id`, namespaced, naming the mechanism and its form, never a protein; `interface` (`cells.channel_law@1`, `cells.cycle_law@1`, `cells.route_law@1`, `cells.binding_law@1`, or a family's own, such as GARD's event laws). A fifth, `cells.junction_law@1`, is @3's junction conductance law's: its contract (a gated state with kinetics(V, parameters), a right-hand side, a domain and a voltage bound) is not the membrane channel's (codes, named gates, permeant ions, an RK4 step). `host`: the namespaced ID of the kind or model that runs it, by which a host finds its laws (version 1's restriction, built in step 1; §8.3) |
| What it reads and changes | Rows by role at named ends, with units and signs; its own state, if any |
| Its math | Pure kernels in the `xp` style; for a cycle law, S ≥ 0 or J (§3.2) |
| Energy role | Passive or driven (books work); the heat bookings it admits (§6.1) |
| Domain and step terms | Enforceable bounds, checked at run time; who supplies its slopes (§3.3) |
| Parameters | Names and units, split into structure and values, with no defaults |
| Provenance | `parity` with `moved_from` (§8.6); `cited`, with source, place in the source, the numbers' licence (D186) and its departures list; or `calibrated`, with data and method |
| Levels of detail | B8's four optional fields (D175), as reserved today (`inner_laws.py`:95–99) |
| Its test | The kernel against its reference, with a planted error (D187), named by test ID so that the manifest can link the evidence |

- **Today's `ChannelLaw`, `JunctionLaw`, `PumpLaw` and `RouteLaw`** (`inner_laws.py`:79–213) become
  instances of this template, with their fields kept.
- **H1's channel-law fields** (cardiac §4.5) are optional fields of `cells.channel_law@1`, so their
  addition keeps its major: reads, gate counts, the driving force and coefficients as data.

### 8.2 One module per law

- **New laws** get one module each, under `laws/<group>/`.
- **@3's laws today** keep their kernels in shared modules that older families also import:
  - `voltage_gates` has 5 legacy importers, `kinetic_pump` 6 and `junction_gate` 2
    (`move1-draft.json` against an AST scan, **S**);
  - each law's kernel moves to its own module by a P2-style extraction (D188 step 0's probe): the
    old module re-imports the names, and an AST check shows the moved text identical;
  - no live code pin names any of these files (`code-pins.json` at b844f920). The pinned files are
    `processes/__init__.py`, `electrochemistry.py`, the field and transport numerics, and the
    geometry cluster;
  - so the frozen families' bits and tests are unaffected.
- **Six files keep their bytes.** The lead's ruling for move 2 (SOURCE_LAYOUT_MOVES_DESIGN §17
  item 2, main cbc52577) keeps `processes/electrochemistry.py`, `numerics/fixed_step.py`,
  `numerics/extracellular_field.py` and the three package `__init__` files byte for byte. The pass
  edits none of them, and the surface (§8.5) re-exports R, F and `scatter` from them by import.
- **The declarations leave `inner_laws.py`'s central tables** and join their laws' modules.
  `InnerStructure` then validates against the registry (:274–278), not against module tables.

### 8.3 The law registry

- **Build-scoped, like kinds' registry:**
  - one registration call;
  - namespaced IDs, with bare IDs in `cells`;
  - built-ins registered from their own packages, through a package loaded by name
    (`kind_registry.BUILTIN_PACKAGE`'s pattern, :437);
  - a registered but undeclared law changes nothing.
- **Kinds find their laws by interface,** in the active registry, never in a module tuple. A new
  cycle law is then one module and one registration, with no edit to the kind (**S**).
- **Codes:**
  - @3's channel laws keep theirs (`LAW_CODES`, `surface_pump_v3_spec.py`:56);
  - kinds' laws carry none (§7.4 (k)'s rule);
  - external channel codes are MODULE_SYSTEM_DESIGN §2.3's, in stage 1.

### 8.4 The registration tables

SOURCE_LAYOUT_MOVES_DESIGN §6 leaves D185's registration tables to this pass.
- **One registry, in sections by interface (**S**):** laws, kinds, operators and models, each keyed by
  namespaced ID.
- **Operators register the way kinds do:**
  - the `OPERATORS` dictionary (`models/operators/__init__.py`:29–52) becomes a section filled from
    the built-in package;
  - `check_declarations` runs at registration;
  - built in the pass.
- **Models: a table designed here, built with module stage 1 or with GARD's family.** Each entry
  gives the model's parse, `to_dict`, build, `control_values` and CLI.
  - It replaces the active branches of `get_model`'s chain (`models/registry.py`, "no dynamic
    plugins", :1 [`registry/models.py`]) and of `parse_spec`.
  - The older families stay behind `legacy/registration.py`'s delegation (D188's R1).
  - GARD's family registers one model entry and its laws and operators in its own namespace.
    That answers its Q4: through the table if stage 1 has built it by then, otherwise through
    today's chain. Its runner shape is its own.
- **File ownership.** D188's R1 owner changes the dispatch points (`models/registry.py`,
  `core/specs.py`, `core/schedule.py`, `__main__.py`, `ensemble/*`) in move 1. The pass touches
  only the operators' registration, after the moves.

### 8.5 The stable import surface: `cells.modules`

- **One package whose path never moves (**S**).** It is MODULE_SYSTEM_DESIGN §2.6's
  `src/cells/modules/`.
- **What it exports:**
  - the declaration types of each interface: `ChannelLaw`, `CycleLaw`, `RouteLaw`, `BindingLaw`,
    `Citation` (the source a cited law gives), `Kind`, `KindFields`, `KindView`, `KindRates` and
    `Schedule`;
  - the parsing helpers: `ConfigError`, `require_fields`, `finite_number`, `bounded_integer`,
    `parse_series`, `series_to_dict`, `qualified` and `declared_schedule`;
  - the constants: R, F, `CHARGE_PER_FMOL` and `EXPLICIT_STEP_BOUND`;
  - the array helpers kinds use: `scatter`, `species_sum`, `entity_sum`, the host table's end
    readers and `physical_amounts`;
  - in stage 1, `Module`, `Registry` and `BUILTIN`.
- **`KindRates` moves into the kind contract** (`registry/`). Today it is defined in @3's
  implementation module (`surface_pump_v3.py`:372–392), which re-imports it as the same object.
- **Built-ins import only the surface** (the D180 rule extended). An AST test over `kinds/` and
  `laws/` enforces it, with a planted violation that must fail. Internals never import the
  surface, so it adds no cycle.
- **Stability: provisional (D195).** There is no stability promise until a first outside module
  arrives; then the promise goes back to the user. The word "provisional" stands in the
  package's docstring and in MODULE_SYSTEM_DESIGN §2.6. Internals may move freely, since the
  surface re-exports them.
- **The surface is the stable import path that SOURCE_LAYOUT_MOVES_DESIGN §12 left to this
  pass,** in place of compatibility aliases.

### 8.6 How a moved law names its frozen original

**Two readings:**
- **A D188 file move,** where a kernel's path changes. The committed move maps and path tables
  already record it (SOURCE_LAYOUT_MOVES_DESIGN §2, §11), so the declaration needs nothing.
- **A D167 law move,** where an older family's law is hosted on the modular path, such as the
  cardiac lane's moved Ca²⁺ leak and SR pump. This note takes this reading, as D184 calls the
  catalogue's laws "parity references".

**The proposal for the D167 reading (**S**):**
- **One copy of the math.** The kernel stays in `laws/`, and the frozen family imports it, legacy
  importing active, which D188 allows.
  - Of the kernels the cardiac set moves, `er_calcium` (6 legacy importers) stays active after
    move 1, and so does `calcium_catalog_extra` (move 2 takes it to `laws/channels/`).
  - Neither is pinned.
- **`moved_from` in the declaration,** in `provenance`, holds:
  - the original law's ID and its family's model ID;
  - the frozen reference: a Git tag and the module path at that tag (no hash literal, AGENTS.md).

  The run view states it beside the law's provenance (`run_view.py`:672–700).
- **The parity claim is proved once, at the kernel** (D187). The kernel object is the family's
  own, so the claim holds by construction. A law re-hosted on a new host adds one test at matched
  inputs, against outputs saved from the frozen reference, with a planted perturbation that must
  fail.
- **A changed law takes a new ID** (D148's reading: "D147 makes an ID promise its semantics"; the
  inner-model design's §6). The old ID's kernel stays, frozen, for its family.

### 8.7 Left to module stage 1

Registry threading through the parse and build call sites, the CLI's `--module`, the manifests'
`modules` record, the conformance kit, the example package and the declarations manifest. The
template's fields are the manifest's content, so the manifest becomes one generator over the
registries.

## 9. Seam G: the run view's three format items

1. **Kinds are words (built: cf 9b0d8baa).** Each passive route gives its kind as a word
   (`KIND_WORDS`, `passive_routes.py`:583 on core-fixes) and its law ID under `laws`.
   - The writer already passes `laws` through and checks one per ID.
   - **The general rule (**S**):** the writer refuses a `kinds` value that contains "@", and law IDs
     go only under `laws`, for every set.
   - The planted case is real: `ph_condition`'s set still gives its law ID as its kind
     (`ph_condition.py`:217), fixed in the same commit.
   - RUN_VIEW_DESIGN §9 gains the sentence.
2. **What `carries` means.** A route's listed species each move with their own flux, not as a
   coupled set.
   - Coupled stoichiometry is `per_cycle`, as @3's pumps give it today (`run_view.py`:681–685).
     The cycle kind's sets give `per_cycle` per mode and population, with each mode's ν per
     species and end.
   - This goes into the writer's docstring and §9.
3. **References.**
   - A reference constant is written only when a record names it, built in `view()` from the
     records' references (today :1217–1244 writes every declared one).
   - A `{"field": X}` reference, from door S without saved rows (:1246–1252), requires X's
     `unstated` entry (:1706–1714). The reader's check refuses it otherwise.
   - A planted view without the entry must fail.

Owner: the run-view writer's (`run_view.py` [`records/`]); item 1's kind-side fixes are the
kinds'.

## 10. Verification and accounting (D187)

Each claim is proved once, at the cheapest level that can prove it, with a planted error that it
must catch. Each composition claim gets one composed-world check. Each landed seam adds one world
to crossrev's kinds set and to the results baseline (D187 rule 2). The references for A and C are
written by a fresh agent who has read neither the engine nor this note's derivations, because
this note's author has read the engine.

| Seam | Claim | Cheapest proof | Planted error | Composed-world check | Ledgers kept |
| --- | --- | --- | --- | --- | --- |
| A | Each mode's flux has the sign of −ΔG and is zero at equilibrium; the kind conserves material, charge and moieties; heat is non-negative | The kernel on random states with registry potentials: J·ΔG ≤ 0 and J = 0 at ΔG = 0; parse-time charge and moiety checks; slopes against finite differences | A law whose S < 0 somewhere; a mode with unbalanced charge; a wrong analytic slope | Two populations on one patch, one a fuel-free exchanger and one a pump on finite rows, over a run with every ledger closing; FR-4's and FR-5's worlds identical in programs (A2, A3) or bitwise in records (A1) | Material (local, outside, `total` with `produced`), charge, energy (heat, work, stored), moieties |
| B: refusal 4 | Every move at a compartment's node or across its bounding patch is held by its law's declared step term | Host-side, at binding, on planted kinds | A planted kind that moves a charged row with no `stage_term`, and one that moves a neutral row with neither term, must both be refused, naming the law | FR-4's and FR-5's declared worlds admitted exactly as today | — |
| B | Close, split and retire by declared roles keep every ledger and leave a closed host idle | Host-side: an extensive field split sums exactly (anchor rule); an intensive field copied; history retired and added back | A field declared extensive but split by the wrong fraction; a closed patch's mover whose rates are not gated by its host's activity (composition §13.1's 1.41e-5 fmol/s, as the planted case) | A dividing cell with a kind population, every ledger closing through the division and the retired patch idle; one population with an operator factor and a routed kind factor, giving the product in its fixed order, bitwise | Material, charge, energy, with each retired history added back |
| C | The free forms satisfy each binding's equilibrium and every conservation law to the closure's tolerance; its term is the speciation minimum; only movers that declare their forms move a multi-form row | The kernel against an independent solve with two ligands on random totals; B4's one-ligand case bitwise; the forms check at parse | A wrong K; a dropped form; the term booked without its stored rows' own part; a planted mover of a multi-form row that declares no forms, which must be refused | A node holding H⁺ and Mg²⁺ under the closure, with a cycle reading free forms: charge exact from totals, and the energy ledger closing with the closure's term | Charge (totals), material, energy (stored) |
| D | The trapezoid books every element non-negative, within the energy ledger's tolerance | The booking probe (§6.4), refused under the tableau and admitted under the trapezoid | The tableau's weights in a class declared trapezoid must fail the dissipation check | A cycle that crosses its equilibrium (synthesis reversing) beside channels at E_K, admitted with every heat element monotone; branch X: the energy ledger at rounding up to dt ΣG/C = 1, with a planted sign flip | Energy |
| E | One authority for every standard free energy; material slopes bound the step; moieties hold | As built (5 and 3 tests with logs of their teeth, cf); a reaction-level ΔG° compared with the registry | A planted ΔG° off by twice the bound; a fuel stoichiometry off by one | R-fuel's world (step 3's) | Moieties; material |
| F | The refactor changes no program; a registered but undeclared law changes nothing; built-ins import only the surface | crossrev's sets and G1 identical; the I1-style invariance test; the AST guard | A law registered without its citation is refused at registration; a planted internal import is caught | — | — |
| G | The view's statements are the engine's | The writer's tests | A law ID as a kind; a field reference without its unstated entry | One kind world's written view | — |

## 11. Options and recommendations

| Decision | Options | Recommended | Why |
| --- | --- | --- | --- |
| The cycle kind (§3.5) | A1 in place with one layout; A2 a new kind beside a frozen transporter; A3 in place with version 1's layout kept | A3; A1 only if the lead waives §0's rule for FR-4's and FR-5's worlds | A3 keeps the rule, one kind ID and D1's kind path; nothing registered pins the transporter |
| Finite fuel's home (§3.5) | On the generalised transporter; on the frozen one, as the FR lane planned; on a new kind | The generalised transporter (A3 or A1) | D1's "same kind path" kept; the partial patch superseded; step 3 builds only R-fuel's world |
| The binding closure (§5.4) | C1 in place; C2 new | C1 | FR-4's and FR-5's programs stay identical either way |
| Heat booking (§6) | The trapezoid now; the exact charged booking now; both by P1 | The trapezoid now; branch X only if P1 shows the energy ledger binding | The two solve different problems; P1 is cheap and decides |
| Populations (§4.2) | Declared field roles; per-kind hooks | Roles, with a hook only where no role fits | Written once; a new kind joins by declaring |
| The door into @3's availability (§4.3) | In the pass; in H2 | In the pass | Small; one availability rule for every population |
| Refusal 4 (§4.4) | Per move, from each law's declared terms; extend the lists | Per move | No edit to the compartments operator for a new kind, and a law with no term is refused |
| Laws (§8.2) | One module per law by extraction; declarations beside shared kernels | Extraction | D188's target layout, with the frozen families unaffected |
| Registration (§8.4) | Operators and laws now, models designed; all now; none | Operators and laws now | A new operator or law joins with no edit; models wait for stage 1 or GARD |
| Moved laws (§8.6) | D167 reading, one copy; D188 reading | D167, one copy, `moved_from` | D184's "parity references"; no pins on those kernels |

## 12. Questions

**For the lead:**
1. **The cycle kind** (§3.5): A3 (recommended), A1 or A2?
   - A1 asks you to waive §0's invariance rule for the kinds set's FR-4 and FR-5 worlds, which
     use none of the new features: their records bitwise in place of their programs. It is only
     open if their judged runs have not started when the pass builds.
   - When do FR-4's and FR-5's judged runs start? That also sets when A3's version-1 layout can
     go.
2. **Finite fuel.** On the generalised transporter, built by the pass, with the FR lane's partial
   patch dropped (A3 or A1)? Or as planned, with the lane building on the frozen transporter in
   step 3 (A2)?
3. **The kinds' names.** Should the general kinds keep `cells.transporter@1` and
   `cells.rapid_proton_buffer@1`, or take their mechanisms' names?
   - The binding kind's rename keeps the canonical order, so it can come now (§5.4).
   - The cycle kind's rename would move FR-4's and FR-5's fields, so it waits for A3's version-1
     layout to go (§3.5).
4. **P1 moved into step 0** (§6.4), and branch X decided by its result?
5. **Composition's Q1–Q7** answered as in §4.5, to route to that note's owner?
6. **The registration tables' scope** (§8.4): operators and laws in the pass, models designed
   here and built with stage 1 or with GARD?
7. **Moved laws** (§8.6): the D167 reading, with one copy and `moved_from`?
8. **Moieties declared in the species registry** (§7.3), with finite fuel as the first consumer?
9. **Owners** (§13): who owns the operators' files that B touches, namely refusal 4 in the
   compartments operator and the partition's field roles?

**Marked for the user (through the lead):**

10. **Pools at the cell's potential** reopen subspace calcium, which version 1 closes (cardiac Q6;
    D184). The pass decides nothing here, but its host table admits a pool route later without
    any change to the kinds.
11. **`cells.modules`** (§8.5) is a stability promise to outside contributors in a public
    repository. If the lead treats it as a public commitment, its name and its rule go to the user
    with D185's direction.
12. **Under A3, A2 or C2,** a frozen layout or kind and its tests retire later: A3's version-1
    layout once FR-4 and FR-5 move, or A2's and C2's frozen kinds. That goes on a D187 retire list,
    which goes to the user in one batch before any removal.

## 13. Order of building, and the estimate

**The order.** Code starts after D188's move 2. core-fixes is first carried across by the move
script (SOURCE_LAYOUT_MOVES_DESIGN §10).

| Step | Work | Needs | Owner (disjoint files) | Agent-days (**S**) |
| --- | --- | --- | --- | --- |
| 0 | The booking probe; core-fixes carried across and its three commits' tests re-run | Move 2 | Core owner 1 | 0.5–0.75 |
| 0 | P1, criterion first (scratch and `validation/`) | Move 2 | Kinds owner | 0.5–0.75 |
| 1 | F: the law registry, the template, the surface and `KindRates`'s move | 0 | Core owner 1: `registry/`, `modules/` | 1.5–2.5 |
| 1 | D: the booking table and the trapezoid, written once | The booking probe | Core owner 2: `models/surface_pump_v3.py`, `definitions/surface_pump_v3_spec.py` | 1–2 |
| 1 | E: D3 and D4 adopted; reaction-level potentials | 0 | Core owner 2: `registry/species_registry.py`, `registry/kind_registry.py`, `operators/contract.py` | 0.5–0.75 |
| 1 | G: the three run-view items | 0 | Run-view owner: `records/run_view.py`, `docs/RUN_VIEW_DESIGN.md`, `kinds/ph_condition.py` | 0.5–1 |
| 2 | A: the cycle kind and its first two laws (A3's two layouts included) | F's registry | Kinds owner: `kinds/transporter.py` (A1, A3) or a new module (A2), `laws/pumps/` | 4.5–6.5 |
| 2 | C: the binding closure and multi-form registry entries | F's registry, E | Core owner 2: `kinds/proton_buffer.py`, `laws/reactions/`, `registry/species_registry.py` | 3–5 |
| 2 | F: per-law extractions, operators' registration | F's registry | Core owner 1: `laws/*`, `models/inner_laws.py`, `operators/__init__.py` | 1.5–2 |
| 2 | B1, beside A: field roles and the lifecycle for today's kinds and @3's fields; the door into @3; refusal 4 per move | F's registry | Core owner 1: `models/surface_pump_v3.py`; operators owner: `models/pump_composite*.py`, `operators/partition.py`, `operators/compartments.py` | 2–4 |
| 2 | Independent references for A and C | F's registry | A fresh references agent: `validation/core_seams/` (new) | 2–3 |
| 3 | B2, after A: the cycle kind's roles, and the dividing world with a kind population | A, B1 | Kinds owner, with the operators owner | 1–1.5 |
| 3 | E: moiety ledgers with A's moved rows | A | Core owner 1: `models/surface_pump_v3.py`, `registry/` | 0.5–0.75 |
| 4 | Gates at each merge, and §10's composed-world checks | Each | The lead's gate lane | 1 |
| X | The exact charged booking, only if P1 asks | P1, A | Core owner 2 | 2–3 |

**Built now, or with a first consumer.** Every row above is built in the pass, except branch X,
which waits for P1. Built later, with their consumers: the model table (module stage 1 or GARD),
the door's value mode (H2) and B8's "represents" key.

**Totals (**S**):**
- **20–31.5 agent-days,** plus 2–3 on branch X. Under A1 instead of A3, 0.5 less.
- **Elapsed, about 9–13 working days,** with five owners (two core owners, a kinds owner, an
  operators owner and the run view's) and a references agent, six agents within D171's seven.
  - The critical path: step 0 (1–1.5 with the carry-over), F's registry (1.5–2.5), A (4.5–6.5),
    B2 (1–1.5) and the gates (1).
  - The other paths are shorter: C ends 5.5–9 days in, B1 4.5–8.

**What it replaces in the consumer notes (**S**):**

| Consumer note's line | Its estimate | Taken by this pass |
| --- | --- | --- |
| Mitochondria P1 and M1 (kind 4–6, closure 3–5, booking 1–2, refusal 4 0.5) | 9–14.5 | All |
| Cardiac H1's booking probe and booking | about 1–1.5 | All |
| Cardiac H2's exchanger and pumps on the kind, and the buffer read | Part of its 9–15 non-pool days | About 3–5 |
| Composition's gap 4 level (c) | 2–4 | All |
| Finite fuel's kind path (the FR lane's 0.5–1) | 0.5–1 | All, under A3 or A1 |
| **Sum** | | **about 15.5–26** |

The rest, about 4.5–5.5, is mostly F and G.

**Which step-3 and step-4 lanes each seam blocks:**
- **cardiac H1:** D, and F's template and registry, on which its eight channel laws are written;
- **cardiac H2:** A, B (the door), C and F;
- **composition's M6:** B;
- **finite fuel:** A and E;
- **mitochondria's M1:** A, C, D, B's refusal 4 and F; **M3:** F, for its laws;
- **GARD's G1:** F's registry and surface only.

Composition's M1–M5 (gaps 1–3, 5, 6 and level (a)) need none of the pass, so they can start in
step 3 as planned.

## Sources

- **Cycle kinetics** [not read for this note; cited as standard theory, from memory]:
  - T. L. Hill, *Free Energy Transduction and Biochemical Cycle Kinetics* (Springer, 1989). Its
    diagram method gives each cycle's net flux as a non-negative factor times (1 − e^{−X/kT}),
    with X the cycle's force;
  - E. L. King and C. Altman (1956), *J. Phys. Chem.*, for steady-state kinetic diagrams.

  No text or figure is used. §3.2's form is a screen item, not a claim resting on these.
- **The source models,** as the consumer notes read them: O'Hara et al. 2011 (cardiac note);
  Beard 2005 and its 2006 correction (mitochondria note). This note reads neither paper; it cites
  facts only through those notes.
- **Evidence read for §8:** D188 step 0's evidence in `/mnt/workspaces/Cells/d188-step0-20261116/`:
  `evidence/plan-b844f920/{move1-draft,code-pins,reach}.json`, and the move-2 draft named in the
  status line. Legacy importers of active kernels were counted by an AST scan of the draft's moved
  modules at main df2b910b (**S**).
- No web search was made and no external file was fetched for this note.

## 14. The lead's review, with the advisor (17 November 2026)

**The lead's answers** to §12's questions for the lead:
1. **The cycle kind: A3.** The transporter is generalised in place, and version 1's layout is kept,
   so FR-4's and FR-5's programs are unchanged. D148 already admits a later collapse to one layout
   with bitwise records, so A1 can come then. FR-4's and FR-5's judged runs do not wait for the pass.
2. **Finite fuel goes on the generalised transporter.** The FR lane's partial patch is superseded,
   and step 3 builds only R-fuel's world.
3. **No renames now.**
4. **P1 joins step 0, with two conditions:**
   - P1 runs in scratch, not in `validation/`.
   - Step 0 gains a third item, written criterion first: screen the cardiac and mitochondrial
     cycle laws (ORd's exchanger and Na⁺/K⁺ cycle, Beard's complexes) against A's factored form.
     A's contract rests on that, and §12 lists it as not verified.
5. **Composition's questions (Q5) wait on file ownership.**
   - Composition's C1–C6 and B1 edit the same files: `pump_composite.structure_errors`, the
     adapter, the partition and `contract.py`. One operators owner does composition's M1–M5
     first, then B1. That answers Q9.
   - §4.5's answers go to the composition note once that ownership is in place.
6. **Laws as modules (Q6, Q7) are answered after one check, made first in step 0.** The planner's
   pin inventory must show that F's extraction list and the files the `cells.modules` guard would
   rewrite touch none of the live pinned files. Six of those must keep their bytes (§8.2; D188's
   note §17).
7. **Moieties in the species registry (Q8): agreed.**

**With D188:** files should move once.
- Move 2's 36 unplaced modules are placed against §8.2's layout before its map freezes.
- §8.3–8.4's registration tables are checked against R1's legacy entry point as built.

**For the user** (17 November): the pass at this scope, staffing within seven, `cells.modules` as
provisional, and checkpoints across move 2. §12's items 10 and 12 are not decisions today.

**Decided, 17 November (D195):** all four as proposed. A and C wait for step 0's cycle-law screen,
and §13's owner table is redone with one owner per file before the code starts.



## 15. Seam F's foundation landed: the advisor's follow-ups (17 November 2026)

Seam F's step 1 and D185's declarations manifest are on main (75e925ea). Its gate: crossrev
identical, G1 113 of 113, and tiers 1+2 with none changed. The advisor's review asks for the
following before work builds on it.
- **The interfaces are provisional,** like `cells.modules` (D195).
  - `cells.cycle_law@1` is PumpLaw's shape while seam A's contract waits for the blind check.
  - `cells.binding_law@1`'s fields predate seam C.
  - Both are labelled provisional until their seams land.
- **F's claim is tested on GARD's family in G1's part 2.** A new piece joins with no edit to other
  pieces: GARD's laws register under their own interface, importing only `cells.modules`. Any edit
  to F's files is a finding. Until then GARD is absent from the manifest.
  - **What the test showed (17 November).** GARD's three laws register on F's template and
    registry, with no edit to F's files, and are listed with their sources and tests. Four gaps
    remain on F's side:
    1. **The surface** exports no `Law`.
    2. **Loading:** a fresh-process manifest lists only the built-in homes, so its bytes depend on
       import order. This is a defect.
    3. **No model section.**
    4. **Operator entries are wired to the composite's contract.**
  - **The fixes, reviewed with the advisor,** are their own landing under seam F, ahead of @2:
    - **The surface:** export `Law` only. A registration entry stays module stage 1, fenced (§8.5,
      D195).
    - **Loading and models:** a static table keyed by model, read when the registry loads:
      `{type, law_homes, operator_homes, interfaces, runner}`. It is the minimal form of §8.4's
      model table. It feeds the manifest's `models` rows and is guarded by a static scan.
      Replacing the dispatch chains stays deferred.
    - **Operators:** a family's operators carry their own interface and host, with their own
      declaration check. The composite's `OPERATORS` section is unchanged.
    - **Interfaces:** the set is open to built-in families in the `cells` namespace (MODULE_SYSTEM
      §2.3: one namespace per distribution, `cells` reserved), with F's five as the initial set.
      A family's interfaces take general names, because D197's first-principles laws implement
      them too: for example `cells.exchange_law@1`, `cells.rate_factor_law@1` and
      `cells.lineage_operator@1`.
- **The manifest `cells.declarations@1` is partly delivered (FR-12):**
  - **IDs:** each piece carries `id` (namespaced) and `declared_id` (the spelling definitions use;
    bare in the `cells` namespace). `host` is namespaced only (`cells.resolved_pump_tissue@3`),
    while definitions name `resolved_pump_tissue@3`. A raw join needs D185's rule, that a bare ID
    is the `cells` namespace. The format states it, or the manifest gives hosts in both spellings.
  - **Nulls carry three meanings:** not stated by any record (`status`), not applicable, and not yet
    extracted (the kinds' `ledgers` and `energy`, and every piece's `test`). The format
    distinguishes them before the visualizer binds.
  - **The format** is documented only in the module's docstring. A format page comes with the
    documentation analysis.
  - **Checked as right:** each of the 19 operators names its own declaring module.
- **Citations.** Fick (1855), Goldman (1943) and Hodgkin and Katz (1949) were named from memory, not
  read. They are marked unread, or read and confirmed, in step 2.
- **Open branches.** core-fixes' four commits merge textually with F's files: `passive_routes`, the
  kinds' registry and @3's step merge automatically, and only the tier record conflicts. They still
  need their own gate after merging main. Move 2's carry-over proof starts from that merge.
- **FR-4 and FR-5.** F changed how the transporter and the passive routes find their laws. The FR
  rehearsals run from a snapshot older than F, so their bitwise checks are repeated from main at or
  after 75e925ea before registration.

## 16. Seam A's contract, amended after the independent check (17 November 2026)

The check is recorded in `docs/CORE_SEAMS_STEP0.md` §7. It lifts seam A's hold, with these changes:
- **Modes.** A law that declares per-mode signs declares the full set of its diagram's Hill cycles,
  dependent ones included. A basis is admitted only when its cycles share no edge.
- **The admission check.** At parse time, each declared Hill cycle must satisfy Wegscheider's
  condition, ln(Π⁺/Π⁻) + ΔG/RT = 0, at the engine's potentials. A law that fails is refused, never
  repaired.
- **The ledger's guard.** The population's total Σ J·ΔG ≤ 0 is checked at run time. It is
  basis-independent. Per-mode bookings are readouts, not guards.
- **Printed laws that fail the check** (O'Hara–Rudy's INaCa; Beard's Eqs. 11, 16 and 24) enter only
  with declared departures. The user rules on those with the cardiac and mitochondria lanes.
- **One-way fluxes (D202).** Every admitted Hill cycle has J⁺ and J⁺·e^{ΔG/RT}, so a factored cycle
  law exposes both one-way fluxes. Material labels need them. Only fallback laws lack them, and
  those declare net-flow mode.
