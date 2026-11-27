# Site occupancy: binding sites as owned state (design)

**Qualified, 18 November 2026.** The registered protocol `fr3-site-occupancy-v1`
(`validation/tissue/site_occupancy_acceptance_protocol.json`, registered at 1b838d75) was judged
once from a clean snapshot of that commit: passed, 51 of 51 judged criteria (Q1 to Q6 with their
controls and plants), against the code-blind references (`validation/fr3/references`). It is
`site_occupancy@1`'s first judged acceptance. Its scope is version 1's face-free first acceptance
(§8.3) as built there: one neutral, impermeant ligand, patch populations outward and inward,
site-conserving internalisation and a static α, ARS(2,2,2) at the declared 1 ms with q1_fast on
1, 0.5 and 0.25 ms. Contact populations in a run, composition with D150's or D152's operators,
faces, RK4 and site occupancy beside a bath schedule are not shown. The engine's own energy check
does not refuse the planted work error; the judge's closure catches it (FR-18).

**Accepted, 14 November 2026 (the lead, with the advisor; D169).** It uses D152's unsplit SSPRK(3,3) with the per-route hybrid; the palindrome was measured and rejected. α is static in version 1. The day-one guard is judged against an independent integration of the full kinetics.

**Milestone 1 landed on main, 15 November 2026 (§12; tier 1 and 2 at the merge a917d72).** Stage A, the contract fit, and stage B, the half-step with its bookings and guards, landed with it. Every host check holds on every row of the face-free world, passive-only and mixed; three planted corruptions fail them; idle is bitwise; restart is bitwise; the stage condition refuses dt L > 1 at run time. The integrator duplicates D152's numerical block, a consolidation item for D172's round. The references, the protocol and its judged run are not part of it.

**Status: PROPOSED, 14 November 2026. Revised the same day after the lead's review with the
advisor; the rulings are recorded in §11.** No engine code was added or changed. One pre-acceptance
probe was run, at the lead's request: a NumPy and SciPy prototype that took 14 s on one thread
(§4.5, §8.5). D159 logged the feature (FR-3), and D167 orders its design alongside FR-1's and
FR-10's. Design comes before code (D142), as a general feature (D144).

**The request** (FR-3, condensed in [FEATURE_REQUESTS.md](FEATURE_REQUESTS.md#fr-3--the-site-occupancy-primitive)):
promote the primitive that [D150 §2.5](SECRETED_SPECIES_TRANSPORT_DESIGN.md) kept as a door:
- binding sites as state on a membrane domain or contact, with one owner;
- bound and free in one material ledger, never a second copy;
- accessibility as a factor separate from stoichiometry;
- declared partition and reset rules at division and replacement.

D150 §2.5 recorded four requirements for it and an analytic guard: the saturable sink is the
quasi-steady limit of binding with internalisation, J = k_int R_T c/(K_M + c) with
K_M = (k_off + k_int)/k_on (**S** there; the lead checked it).

**Engine models it runs** (AGENTS.md milestone rule):
- `resolved_pump_composite@1` over `resolved_pump_tissue@3`;
- one new operator, `site_occupancy@1` (§1, §2), with two laws: `langmuir_site_binding@1`
  (passive) and `site_conserving_internalisation@1` (driven);
- its half-step is D152's: SSPRK(3,3) under the unidirectional stage condition, with D152's exact
  bookings and per-route hybrid (§3.3, §4.2).

No model, solver or shared function changes, compiled or host-side, in version 1 (§6.3).

**Basis.**
- The contract: [PUMP_COMPOSITE.md](PUMP_COMPOSITE.md); the [v2 design](PUMP_COMPOSITE_V2_DESIGN.md)
  §1 (energy roles, free-energy owners, combination rules) and §3 (membrane state, R1–R8).
- The inventory: the [secreted-species design](SECRETED_SPECIES_TRANSPORT_DESIGN.md) (D150) and the
  [shared-inventory reactions design](SHARED_INVENTORY_REACTIONS_DESIGN.md) (D152), whose integrator,
  stage condition and booking rules this note reuses.
- The factor form: the [coupling design](INVENTORY_COUPLING_DESIGN.md) (D155, D156): F ∈ [b, 1], its
  regulatory state and its routing door.
- The primitive's own sources: the [kinetochore counting review](PAPER_REVIEW_KINETOCHORE_COUNTS.md)
  and the paper it reviews (Hirano et al. 2026), and receptor-kinetics texts (References). The
  neighbouring requests FR-1, FR-2 and FR-6 were read for the links (§5.3), not as design inputs
  (D144).

**Evidence and log:** `/mnt/workspaces/Cells/site-occupancy-20261114-01/`.
- HANDOFF.md: what was read, the code facts with line numbers, the citation checks.
- `probe-split/`: the prototype, its log and its JSON (§4.5, §8.5). It is development evidence by
  the note's author, not a reference of record.

**S** marks our own arithmetic or interpretation, as in the D150, D152 and coupling notes. Every
closed form in Appendix A is derived here (**S**), and the references agent derives them again.
For the books and papers cited, the records were verified and the texts were not read, except the
kinetochore paper's own figures (§2.3). No parameter value is taken from memory: values in examples
and probes are synthetic and labelled so.

## Departures from the brief, from D150 §2.5 and from FR-3's mapping

All were ruled on by the lead with the advisor, 14 November 2026 (§11).
1. **The owner is not membrane state** (D150 §2.5 requirement 2; the brief's "membrane state's
   populations?"). *Ruled: option O.*
   - The population form is kept: a functional unit, a catalogue reference, and copies on a
     domain. The state lives on a new operator.
   - **The reason is field input.** Membrane state provides `membrane_capacitance`, so every
     composition with it refactorises the field every step and is capped at 64 field nodes (§1.3).
   - The refusals by exchange@1, replacement@1 and water are walls that version 1.1 lifts, so they
     are not the reason.
   - **FR-2 must then move two population owners:** membrane state's channels and this operator's
     sites.
2. **Version 1 has an internalisation step, in its site-conserving form only.** FR-3's mapping says
   "its internalisation step follows FR-2"; the brief's day-one guard needs one. *Ruled: yes.*
   - The guard's J = k_int R_T c/(K_M + c) holds only when the site count stays constant: the cargo
     goes in and the site stays.
   - FR-2's form, in which the site goes inward with its membrane, follows FR-2. FR-1's destination
     follows FR-1 (§2.4).
3. **Accessibility scales the accessible site capacity, not the binding rate,** and it is static in
   version 1 (FR-3's mapping: "a declared multiplier on the binding rate"; §2.3).
   - A binding-rate multiplier under detailed balance either scales both directions (no
     equilibrium effect) or only the on-rate (a change of K_d, which is the standard binding free
     energy).
   - Only the capacity form leaves sites empty at saturation.
   - α cannot change during a run, so capacity never falls below what is bound.
4. **One ligand per population.** *Ruled:* competition between ligands for one population's sites
   is a door (§9). Several populations, including several cells' populations, may share one facing
   node.
5. **The scheme is D152's own: unsplit, with its per-route hybrid.** An earlier draft split
   internalisation from binding in a palindrome. The lead's review asked for the cost to be measured
   rather than argued by analogy. The prototype measured it, and the palindrome was rejected (§4.5).
6. **RK4 is refused,** as in D152 and not as in D150 (§4.6). *Ruled: yes.*

## 0. Summary

1. **The entity: a site population** (§1.1). It is a population of identical, independent,
   single-occupancy sites on one owner, facing one free pool, binding one ligand.
   - **Its owner** is a membrane patch, facing its outside node or its cell, or a contact, facing
     one of its two cells.
   - **Its count** is copies × sites per copy (stoichiometry). Its accessible capacity is that count
     times a static accessible fraction α (§2.3).
   - **Its state** is the free accessible sites and the bound amount.
   - **It takes no species row.** A receptor type costs nothing against the species cap; its ligand
     is one row, shared with D150 and D152.
2. **One owner** (§1.3). The operator `site_occupancy@1` owns every site population of a composition
   and runs their laws. A law appears once per composition (`pump_composite.py:150`). It provides no
   field input. It declares `ACCEPTS_WRITES` on its pools for its later writers: FR-2's retrieval
   and a partition version.
3. **One material ledger** (§1.4, §3.1). The free ligand stays in @3's rows; the bound amount is the
   owner's state.
   - Binding, release and internalisation are booked transfers between the two, as
     `exchange_moved_fmol` is.
   - The per-species system total, free plus bound, changes only through declared sources and sinks.
   - Bound cargo keeps its identity: it is booked per species row on a named population.
4. **The laws** (§2).
   - **Binding** is Langmuir's mass action on finite sites, L + site ⇌ complex, with k_on and k_off.
     Detailed balance sets ΔG°_b = RT ln(K_d/1 mM), with K_d = k_off/k_on.
   - **Internalisation** is first order in the bound pool. It moves the cargo into the patch's cell
     and returns the site free.
5. **Accessibility** (§2.3) is the accessible fraction α ∈ (0, 1] of the stoichiometric sites,
   declared per population and domain.
   - It is static in version 1. It caps occupancy at α, leaves K_d unchanged, and scales the sink's
     V_max but not its K_M.
   - Regulated forms are doors.
6. **Energy** (§3.3).
   - **A finding:** @3's chemical term holds no binding free energy, so binding below 1 mM would book
     negative heat. The owner holds the site free energy as a declared free-energy term: the standard
     binding term plus the Langmuir configurational term over accessible sites.
   - **The bookings are D152's.** A passive-only component books heat H = −ΔG. A mixed one (binding
     with internalisation) books the per-route hybrid heat, and work W = ΔG + H, so W − H = ΔG holds
     exactly.
7. **Numerics** (§4).
   - D152's SSPRK(3,3) integrates binding and internalisation together under its unidirectional
     stage condition at θ = ½, so dt · L > 1 is refused at run time. Positivity is a theorem.
   - Face-free worlds are third order (prototype ratios 8.39 and 8.19 at ε = 0.1), and worlds with
     faces are second order.
   - The rejected palindrome's steady bias was the dominant error in the guard's own quantity (§4.5).
8. **Partition and reset** (§5). These are declared rules, refused in version 1 with their doors
   named.
   - At division a population splits with its owner's fraction, extensively. Its occupancy is
     preserved and its free energy changes by exactly zero.
   - At replacement the occupant's sites and bound cargo leave with it, booked per species. The
     newcomer takes its template's declared site state.
9. **Composition** (§6). It composes with @3, injection, D150's turnover and exchange, D152's
   reactions (no edit to D152's files), the coupling operator, membrane state, and replacement@1 off
   replaced slots.
   - It refuses volume providers, closers, sites facing a held bath, charged or permeant ligands, a
     trace above 10⁻⁶ K_d, RK4, the stationary analysis, and worlds above `MAX_SPECIES`. That cap is
     16 since D165's D148 change landed (14 November 2026).
   - Beside a compartment, as FR-1 proposes, it raises no field-input wall (§6.4).
10. **Qualification** (§8) is numerical first, against references written from Appendix A by an
    agent that never reads the code.
    - **Day one:** the engine against an independent integration of the full binding kinetics. The
      saturable sink is tested on the reference side, as convergence in the Segel–Slemrod parameter
      ε (prototype: observed order 0.98 and 0.998).
    - **Then:** equilibrium occupancy, binding kinetics against closed forms, accessibility as a pure
      factor with negative controls, and the energy guards of record.
11. **Effort:** about 6 agent-days (5 to 7) for version 1, plus CPU minutes (§10).

## 1. Entities and ownership

### 1.1 The entity: a site population

A **site population** is a population of identical, independent sites, each holding at most one
ligand: Langmuir's model of localized binding (Langmuir 1918). It is declared once, with:

| Item | Content | Units |
| --- | --- | --- |
| Identity | A functional unit ID and an opaque catalogue reference, null or `{"catalogue": id, "entry": key}`: membrane state's population form (v2 §3) | – |
| Owner | A patch with its face, `outside` (the patch's outside node) or `inside` (the patch's cell); or a contact with its side, `first` or `second` (@3's `junction_sender` or `junction_receiver`); or a finite outside node's own surface, `{"node": N}`, facing N, binding only, in no cell (FR-28, D268; [NODE_SURFACE_SITES_DESIGN.md](NODE_SURFACE_SITES_DESIGN.md)) | – |
| Copies N | The population's abundance on that owner: copies of the functional unit | units |
| Sites per copy ν | The stoichiometry: identical sites per copy, an integer ≥ 1 | – |
| Accessible fraction α | The static fraction of the stoichiometric sites that can be occupied (§2.3) | – |
| Ligand | One neutral inventory species, with its binding constants and, on an outward-facing patch, an optional internalisation route | – |

**Derived:**
- the stoichiometric count R_T = ν N, in units;
- the accessible capacity S = α R_T / N_f, in fmol, with N_f = 602,214,076 sites per fmol (exact,
  from the SI value of the Avogadro constant).

**State** (anchored increments from the declared values, membrane state's R8):
- **free accessible sites** R ≥ 0 (fmol);
- **the bound amount** B ≥ 0 (fmol).

R + B = S is the population's moiety identity. It is checked as a guard, as D152's moieties are, and
every update keeps it by construction. Both pools are stored, rather than one derived from the
other, for precision near full occupancy and because later writers move both.

**The free partner.** The ligand is a free species at the population's **facing node**:
- the outside node of an outward-facing patch, which must be finite;
- the cell of an inward-facing patch;
- the side's cell of a contact.

Several populations may face one node. That is how several cells compete for a shared dose.

**Contacts are in version 1** (ruling on question 5).
- **What they cost** (**S**): about 0.25–0.5 agent-days.
  - The owner key and its side; the facing cell's index.
  - Refusals: internalisation on a contact, and contacts incident to replaced slots.
  - One equivalence test: a contact population against an inward-facing patch population with the
    same parameters on the same cell, which must agree to rounding.
  - The partition door's a_e (§5.1).
- **What they serve.** A contact population binds a species from the cytoplasm of one of its two
  cells.
- **Docking is not this law.** The junction docking that D150 lists is binding between two
  populations across a contact. It is a population-to-population law that would write junction
  abundance, so it is a door with its own design: about 3–5 agent-days (**S**; §9).

**Why counts and not densities.** Version 1 reads no area. The kinetochore review reports copies per
structure, and receptor abundances are counts too. A density would tie the site count to
`membrane_area`, whose providers version 1 refuses. FR-2's retrieval, moving a fraction of a patch's
area, would move the same fraction of its sites (uniform density, **S**).

### 1.2 Why a new entity: not species rows, not the regulatory state, not the plain sink

| Alternative | Why it fails as the site primitive |
| --- | --- |
| **D152 species rows** for the free site R and the complex C, with a passive reaction L + R ⇌ C. D152 §2.2 itself writes an enzyme–substrate complex this way | (1) A row lives in a node's volume, and @3's face law would diffuse it: D150 §2.5 requirement 1. (2) A row at an outside node is shared by every patch facing it, so per-cell receptor pools, which competition for a shared dose needs (FR-2's requester), cannot exist. (3) Each receptor type costs two rows against the cap (FR-9). (4) The count would be a concentration in a volume, not copies on a domain |
| **The coupling operator's regulatory state** (`hill_regulated_two_state@1`) | Occupancy at a non-depleted free concentration obeys the same two-state form, but the state holds no material. It cannot deplete or conserve the ligand. §2.6 states the relation, and the coupling note itself sends sequestering binding here (its §1.8) |
| **D150's plain sink** (`saturable` import) | It has no site state, so it has no sequestration, no release, no competition between cells for a finite receptor pool, and nothing for FR-2 to move. It is this primitive's quasi-steady limit, tested on the reference side (§8.3, Q1) |

### 1.3 The owner: two options, costed

**Option O (ruled): the operator owns its site populations.** `site_occupancy@1` holds every
population's state and runs its laws.
- It is the owner and, in version 1, the only writer. Water is the precedent: it owns the volume
  and runs its own flow.
- It declares `ACCEPTS_WRITES = {site_free_increment_fmol: (site_moiety_entity,),
  site_bound_increment_fmol: (site_bound_entity, site_moiety_entity)}` for its later writers:
  FR-2's retrieval, a partition version, and a site-turnover law. With no writer the terms are
  absent, a static branch (v2 §1.4).

**Option M: membrane state owns the sites.** A new law, `membrane_entity_state@2`, would add a
non-conducting population kind holding copies and occupancy. A binding law would write it, as
insertion writes membrane state @1 today.

| | Option O | Option M |
| --- | --- | --- |
| **Field input (the deciding fact)** | None: no refresh and no 64-node cap. Morphogen-scale and sheet worlds of hundreds of nodes stay admissible, as for D150 and D152 | `membrane_capacitance` is a view (`membrane_state.py:194`, `pump_composite_adapter.py:76, 100`, `pump_composite.py:317–318, 709–711`). Every binding world refactorises the field every step and is capped at 64 field nodes. The measured refresh cost behind the cap is +13% at 64 nodes and +20% at 254 nodes (v2 §3) |
| Population owner on a patch | Channels with membrane state, sites with this operator. Ownership is per field (v2's entity table). **FR-2 moves two owners** | One owner for every population |
| What its parser admits | Any declared population | @1's admits exactly @3's channel populations (`membrane_state.py:105–108`). @2 needs a new population kind and a bitwise guard against @1 when none is declared |
| Refusals that version 1.1 lifts (not the reason) | Composes with exchange; replacement@1 off replaced slots | Refused by exchange@1, replacement@1 and water, which list `membrane_area` (`species_exchange.py:461`, `cell_replacement.py:625`, `osmotic_water.py:492`). Replacement@1 also provides `channel_abundance` (614–620) |
| FR-2 and the partition | Both write both owners through `ACCEPTS_WRITES` | One population map serves them. The partition `REQUIRES` membrane state @1 (`partition.py:935`), so it changes in either option |
| Cost (**S**) | Included in §10 | About +1.5 agent-days: membrane state @2, its guards and the writer split |

**What is kept from requirement 2:** site abundance is a population's abundance with its catalogue
reference. The declaration form is membrane state's.

**The owner and law split is the door.** The coupling note's ruling 2 took one operator in version
1 and left the split into a state owner and a provider to the first outside reader.
- Here the owner and law separate when a second law writes the pools: FR-2's retrieval, or surface
  catalysis (§9).
- A state owner without `VIEW_FIELDS` is inadmissible as built (`contract.py:335–341`). The split
  needs a host-only contract admission for one.

### 1.4 One material ledger, and the identity of bound cargo

- **Free:** the ligand's amounts stay in @3's rows (`amount_increment`,
  `extracellular_amount_increment`), which @3 owns. This operator writes them through
  `ENTITY_WRITES`, booked in its own accumulators, never in @3's route accumulators (D150 §1.1's
  writers' rules).
- **Bound:** B is this operator's state on a named population. It is never a species row, never on
  @3's species axis, and never diffused.
- **Transfers:** binding and release move the ligand between the facing node's row and B;
  internalisation moves it from B to the receiving cell's row. Each move is booked once, in one
  accumulator, which enters @3's ledger with one sign and the owner's with the other (§3.1).
- **Identity** (FR-3's links; §5.3). A bound pool is identified by its species and its population.
  - Bound cargo stays its species: binding converts nothing.
  - Moved by FR-2, it stays bound to its population on the moved membrane. Released (FR-1), it
    enters the same species' row at the release node.
  - A conversion of bound cargo into another species is a declared driven route with D152's moiety
    rules (surface catalysis, a door; §9), never a side effect.

### 1.5 The ownership table and the contract's parts

| Field | Owner | Writers (booked in) |
| --- | --- | --- |
| A ligand's free amounts (`amount_increment`, `extracellular_amount_increment` rows) | @3 | @3's step (none for an impermeant ligand, except faces at outside nodes); D150's operators; D152's operator; replacement events; **this operator** (`site_bound_net_fmol`, `site_internalised_fmol`) |
| Free accessible sites (`site_free_increment_fmol` [site population]) | This operator | Itself; later writers through `ACCEPTS_WRITES` |
| Bound amounts (`site_bound_increment_fmol` [site population]) | This operator | Itself; later writers through `ACCEPTS_WRITES` |
| Accumulators, heat, work, magnitudes | This operator | Itself only |
| Populations' and ligands' identities | Declarations, never arrays (§1.6) | – |

**The contract's parts, as used:**
- `ENTITY_WRITES` on the two amount fields, each with the owned accumulators that close @3's
  ledgers.
- `STATE_AXES` for the pools, accumulators and energy fields (§2.5).
- **Energy roles** (v2 §1.1):
  - `HEAT_FIELDS`: `site_dissipated_energy_pJ` [cell] and `site_outside_dissipated_energy_pJ`
    [outside], the facing nodes;
  - `WORK_FIELDS`: `site_work_pJ` [site population];
  - the site free energy is a declared free-energy term (§3.3), not a flow.
- **`CONFLICTS_VIEW`**: `volume`, `extracellular_volume`, `active`, `outside_active`,
  `membrane_active` (D150's static-tissue list) and `extracellular_amount_reference` (D152's
  addition, since insertion@1 provides it).
  - The reason is the contract as built: a half-step receives the declared layout, and the view
    only for a `BOOKS_AT_VIEW` operator in a field-input composition (`pump_composite.py:585–590`).
  - So version 1 is a static tissue, as D150's and D152's are.
- **One split part**, D152's half-step (§4.2), with RK4 refused (§4.6). It is statically idle with
  no populations.
- **`ACCEPTS_WRITES`** as in §1.3.
- None of `VIEW_FIELDS`, `CONTROL_FACTORS`, `REPLACES`, `EVENT_REPLACES`, `CLOSES` or `REQUIRES`.
  It provides no view, so it is no field input (§3.2).
- `ROUTABLE_CONTROLS`: none in version 1. The binding and internalisation multipliers are the
  natural rate targets when the coupling operator's routing door is built (§2.3, §9).

### 1.6 Identity

- **Ligands** carry D150's identity form, parsed by `species_common.parse_species`: neutral,
  impermeant, an optional catalogue reference with its kind of evidence.
- **Populations** carry membrane state's form: a functional unit and a catalogue reference, parsed by
  `membrane_state.parse_catalogue`.
- **Both reach the summary and the manifest, never the arrays.** S2's guard applies: changing a
  reference leaves bindings, jaxprs, the batch signature and trajectories bitwise unchanged.
- **Conflicts are checked by this operator, in either order, with no shared change** (ruling on
  question 10).
  - It calls `species_common.check_identities` with its own law ID, which compares it against D150's
    two operators.
  - It reads D152's declaration through `composite_spec.entries` and compares against it too.
  - So a conflict is refused whichever operator comes first, and neither `species_common` nor D152's
    files change.
  - The shared list `SPECIES_LAWS` (`species_common.py:45`) could later name every inventory law. That
    would be a D148 item, after FR-9's change to the same file lands and outside MG0c's
    rehearsal-to-freeze window. D152's either-order test matches only "another identity"
    (`tests/unit/test_species_reactions_refusals.py:361–386`), and it would be run then.
- **Generic laws stay generic** (the catalogue rule). No law names a receptor, a kinetochore protein
  or a ligand. "Receptor" is a role a driver's declaration gives a population.

## 2. The laws

Units are @3's: fmol, pL, mM = fmol/pL, s. c = n/V is at the facing node's declared volume
(version 1). h is the operator's half-step, dt/2.

### 2.1 Declaration

```json
{"law": "site_occupancy@1",
 "species": [{"id": "L", "catalogue": null, "evidence": null, "trace_mM": 1.0e-15}],
 "populations": [
   {"id": "r_c0", "functional_unit": "site_unit_a", "catalogue": null,
    "owner": {"patch": "c0_contact", "face": "outside"},
    "copies": 1.0e5, "sites_per_copy": 1, "accessible_fraction": 0.5,
    "ligand": "L", "association_rate_per_mM_per_s": 1.0e3, "dissociation_rate_per_s": 1.0,
    "initial_occupancy": 0.0,
    "internalisation": {"rate_per_s": 0.1, "destination": "cell"}},
   {"id": "k_c1", "functional_unit": "site_unit_b", "catalogue": null,
    "owner": {"contact": "j01", "side": "first"},
    "copies": 4.0e3, "sites_per_copy": 2, "accessible_fraction": 1.0,
    "ligand": "L", "association_rate_per_mM_per_s": 5.0e2, "dissociation_rate_per_s": 0.5,
    "initial_occupancy": 0.1, "internalisation": null}]}
```

The values are illustrative and synthetic.
- **Every key is explicit** (D152's ruling Q5). `internalisation` is null or an object.
- **`destination`** admits one value in version 1, `"cell"`: the patch's own cell. The key exists so
  that FR-1 and FR-2 add destinations without changing the form (§2.4).
- **The experiment** adds `site_controls`: per population and route (`binding`, `internalisation`), a
  piecewise-constant multiplier m ≥ 0 from time 0, changing on the clock's grid (D283).
  - A zero multiplier switches the route off (D136): a blocking antibody, a washout, an inhibitor of
    uptake.
  - A binding multiplier scales k_on and k_off together, so the equilibrium is unchanged, as D152's
    multiplier on a passive reaction does.
- **Parameters are not scheduled.** A scheduled k_off alone would change ΔG°_b, a free energy, with
  no declared work. α, copies and sites per copy are not scheduled either (§2.3).

### 2.2 Binding: Langmuir's mass action on finite sites

For population k at facing node i (**S**, the standard form):

    J_k = m_b,k [k_on,k c_i R_k − k_off,k B_k]          (fmol/s; c in mM, R and B in fmol)
    dB_k/dt = J_k,   dR_k/dt = −J_k,   dn_i/dt = −Σ_{k facing i} J_k.

| Item | Content | Source |
| --- | --- | --- |
| Law | Independent, identical, single-occupancy sites binding one ligand | Langmuir 1918; Lauffenburger & Linderman 1993, ch. 2 (records verified, texts not read) |
| Parameters | k_on in mM⁻¹ s⁻¹ and k_off in s⁻¹, both > 0; K_d = k_off/k_on in mM | Per world, with sources: a cited measurement with its method, or a declared synthetic value labelled so (D152 §2.4's rule). The engine holds no default |
| Equilibrium at a fixed free concentration | B = S c/(K_d + c), Langmuir's isotherm over the accessible sites | **S**, Appendix A.4 |
| Detailed balance | ΔG°_b = RT ln(K_d / 1 mM), per mole of complex, against @3's 1 mM reference | **S** (§3.3) |

**What k_on is.** It is the effective association constant per site on the cell, as measured on
cells. Transport to a surface that carries many sites can limit it (Berg & Purcell 1977; record
verified, text not read). This is the analogue of D150's effective face diffusivity (**S**): a
declared value carries its method.

**Rules on the law.**
- **Rates vanish with what they consume** (the premise of §4.3's positivity). The forward flux
  k_on c R consumes the free ligand and the free sites, and vanishes with either. The reverse flux
  k_off B consumes B and vanishes with it.
- **Irreversible binding (k_off = 0) is refused.** Its standard free energy is unbounded, and a
  capture with no release is a driven route, a door. k_on = 0 is refused too: a route switched off
  is a zero multiplier.
- **Cooperativity between sites of one copy** is not in version 1; the sites are independent.
  Cooperative or multivalent binding is a door.
- **Competition between ligands for one population's sites is a door** (ruling on question 6). Its
  law is the competitive Langmuir form with shared free sites (Motulsky & Mahan 1984 for the
  kinetics; record verified, text not read).
- **The written form is linear:** J⁺ = k_on c R and J⁻ = k_off B, not D152's log-space kernel
  `reversible_flux`.
  - It is finite at zero occupancy (B = 0) and at full occupancy (R = 0), which are in the domain
    (§4.3).
  - Near equilibrium the net flux is a difference of nearly equal terms. That costs rounding in the
    trajectory, not in the energy, which is booked from state-function differences and
    divided-difference potentials (§3.3).

### 2.3 Accessibility: what it multiplies, and why it is static

**The constraint it must meet.** The kinetochore review records a modelling constraint from Hirano
et al. (2026):
- in the wild type, binding sites stay unoccupied although the free pool is "an order of magnitude"
  larger than the bound pool;
- in either single mutant, "the remaining sites fill completely";
- "a simple mass-action occupancy law over a finite site population would predict saturation in all
  three states and would be falsified here".

The review also states what is not measured. The occupancy split between the two platforms is
inferred from genotype differences plus assumed stoichiometry, and the paper says the wild-type split
is beyond its method.

**The figures, checked against the paper.** A text search confirms each quote verbatim, in the copy
the review saved: its folder's `text/paper.txt`, flattened from
`downloads/epmc-fulltext/PMC13753873.fullTextXML.xml`. The paper states:
- 18.6 ± 0.4 and 68.6 ± 18.6 nM free, in mitotic cells of 636–2,208 µm³ (n = 18);
- about 160 kinetochores per cell;
- about 3,520 Dsn1 and 5,280 Nuf2 molecules at kinetochores per cell. These are its estimates:
  "∼22 Dsn1 and ∼33 Nuf2 molecules per kinetochore × ∼160";
- cytosolic pools of "∼10⁴–10⁵ molecules", one range for both;
- kinetochore numbers "one order of magnitude lower than those of the cytosolic pool".

From those figures (**S**):
- free Dsn1 is 7,100–24,700 molecules, 2.0–7.0 times its bound pool;
- free Nuf2 is 26,300–91,200 molecules, 5.0–17 times its bound pool;
- Dsn1's lower end lies just below the paper's 10⁴.

The review quotes the paper faithfully. These ratios are this note's own arithmetic.

**Three candidates, against four checks** (**S**):

| Form | Detailed balance with the declared ΔG°_b | Sites empty at equilibrium at saturating c | Carried by the coupling factor path | A change under bound cargo |
| --- | --- | --- | --- | --- |
| **(C) Capacity:** S = α R_T / N_f; binding on accessible free sites only | Kept: K_d unchanged, Langmuir over the accessible sites | **Yes:** θ_max = α | Not as built: a capacity factor changes the site free energy (the configurational term over S), and the coupling path carries only rate factors that book nothing | Changes the free energy, so it books work. A fall below the occupancy needs a rule (below) |
| **(K) Kinetic:** both directions × F | Kept: D152's passive-multiplier rule | **No:** the equilibrium is unchanged; only the approach slows | **Yes,** once the routing door exists: a rate route on the binding multiplier, booking nothing (coupling note §2.1) | Nothing to book |
| **(A) Affinity:** k_on × F only | **Broken:** K_d → K_d/F, so ΔG°_b moves by −RT ln F | Only below saturation: at F c ≫ K_d every site fills | As a rate factor it would book nothing while changing ΔG°_b: inconsistent | Every change of F is unbooked work: refused |

**Decision: accessibility is (C), declared per population and domain, and static in version 1**
(blocking item 3 of the lead's review).
- **Static.** α is a layout parameter. No schedule, control, event or factor route can change it.
  Copies and sites per copy are static too, so S is constant and the moiety identity R + B = S keeps
  B ≤ S at every step.
- **So capacity never falls below what is bound.** The question of free sites going negative, or the
  Langmuir term moving with nothing booked, cannot arise in version 1.
- **"Separate from stoichiometry" is literal.** The declaration has three numbers: copies N
  (abundance), sites per copy ν (stoichiometry) and accessible fraction α (accessibility).
- **Its signatures** (**S**):
  - equilibrium occupancy scales by α at every free concentration;
  - occupancy saturates at α;
  - the relaxation rate k_on c + k_off is unchanged;
  - the sink's V_max scales by α and its K_M does not.

  §8.3, Q4 judges them, with negative controls for (K) and (A).
- **FR-3's mapping, read against it.** "A declared multiplier on the binding rate" equals (C) only at
  zero occupancy, where k_on c (αR_T − B) = α k_on c R_T. At finite occupancy they part, and the rate
  forms are (K) or (A).
- **(K) stays, as a kinetic control,** not called accessibility: the scheduled binding multiplier of
  §2.1.
- **(A) is not an accessibility.** A per-domain difference of affinity is a different declared K_d.

**Regulated accessibility is a door** (§9), with three shapes (**S**):
1. **The kinetic form, through the coupling operator's routing door** (D156, not built). A rate
   route multiplies the binding multiplier by F ∈ [b, 1]. It books nothing and keeps detailed
   balance. The site operator would then declare `ROUTABLE_CONTROLS = {site_binding_multiplier:
   "rate", site_internalisation_multiplier: "rate"}`.
2. **A regulated capacity,** α(t) = α₀ F(t). It needs two rules before it is admitted:
   - **A change of S books work.** The configurational term RT [B ln(B/S) + R ln(R/S)] changes with
     S at fixed B, so the agent that occludes or exposes free sites does work on the pool.
   - **A fall below the occupancy (S < B)** is either refused, or forces the excess off as a booked
     driven release. A third pool of occupied, inaccessible sites is the alternative.
3. **An occluder species competing for the sites.** This is fully accounted by the law's own
   bookings, but it needs competition, which is itself a door. When the occluder exchanges slowly
   beside the ligand it acts as (C) with α = 1 − θ_occluder.

### 2.4 Internalisation: the site-conserving form, and the door to FR-2 and FR-1

**The law, `site_conserving_internalisation@1`.** On an outward-facing patch population, a
first-order route may be declared (**S**, the standard form):

    I_k = m_i,k k_int,k B_k:   B_k → (the ligand into the patch's cell) + (one free site on k).

| Item | Content |
| --- | --- |
| Rate | k_int ≥ 0 (s⁻¹), per population; zero admitted (idle) |
| The cargo | Lands in the destination's row of the same species. In version 1 that is the patch's own cell, the row D150's import routes write: "the shape the primitive's internalisation step would write into" (D150 §2.5 requirement 1; FR-3's mapping repeats it) |
| The site | Returns at once, free, to the same population: R gains exactly the internalised amount. The site count is constant |
| Role | Driven: endocytic machinery moves cargo regardless of the cytosol's concentration. It books signed work (§3.3), as D150's uptake does |
| Sources | Receptor-trafficking models with binding, internalisation, recycling and synthesis (Lauffenburger & Linderman 1993, ch. 3; Wiley & Cunningham 1981; records verified, texts not read). The site-conserving form is their limit of instant recycling with no net loss of surface sites (**S**) |

**Why version 1 has it, and only this form** (ruling on question 3).
- **The guard needs it.** D150's sink is the quasi-steady limit of exactly this system:
  dB/dt = k_on c (S − B) − (k_off + k_int) B = 0 gives B = S c/(K_M + c) and an uptake
  k_int S c/(K_M + c). That limit needs the site count constant.
- **FR-2's form is a different law.** Its requester wants the surface pool consumed and returned: "a
  sink that never consumes its receptors cannot produce saturation, competition ... or the
  cell-to-cell variation that makes delivery selective".
  - In FR-2's form the site travels inward with its membrane and returns later. That needs FR-2's
    retrieval, with its energy source, and FR-1's compartment.
  - It will be another route kind with another destination, written through `ACCEPTS_WRITES`
    (§5.3).

**What version 1 loses, stated.** Cargo internalised in version 1 lands in the cytosolic row. FR-1's
request exists because that row cannot tell "particle inside a vesicle" from "cargo in the cytosol".
So version 1's internalisation is the D150 limit's companion, not the study's delivery path, which
is FR-3 with FR-2 and FR-1 (§5.3).

**Refusals:** internalisation on an inward-facing patch or a contact (there is no "inward" for it),
or on a patch whose outside node is a declared compartment (§6.4); a destination other than
`"cell"`; a negative rate.

### 2.5 State, ledger terms, observations

**State** (per world; the pools start at their declared values, the rest at zero):

| Field | Axes | Role |
| --- | --- | --- |
| `site_free_increment_fmol` | [site population] | Entity: free accessible sites R, from R₀ = S − B₀ |
| `site_bound_increment_fmol` | [site population] | Entity: bound amount B, from B₀ = θ₀ S |
| `site_bound_net_fmol` | [site population] | Material accumulator: net binding, signed (bound positive) |
| `site_internalised_fmol` | [site population] | Material accumulator, ≥ 0 and non-decreasing |
| `site_dissipated_energy_pJ` | [cell] | Heat of binding at populations facing that cell (inward-facing patches, contacts) |
| `site_outside_dissipated_energy_pJ` | [outside] | Heat of binding at populations facing that node (outward-facing patches) |
| `site_work_pJ` | [site population] | Work, signed: its internalisation, and its binding's hybrid correction at mixed components (§3.3) |
| `site_energy_magnitude_pJ` | [site population] | Rounding magnitudes |

**Layout (bound per world, R1):**
- owner and facing-node indices, and receiving cells;
- S, with B₀ and R₀ as anchors;
- k_on, k_off, k_int, and ΔG°_b/RT = ln(k_off/(k_on · 1 mM)), computed on the host;
- the static component map of §3.3.

**Own ledgers**, each with a floor at the ligand's species-scale material floor (D150 §1.3):
- `site_bound_entity` [site population]: the bound increment equals net binding − internalised,
  plus later external terms;
- `site_moiety_entity` [site population]: the free increment + the bound increment = 0, plus later
  external terms.

**@3's ledgers** (D150's sign convention, removed − supplied):
- the facing node's local or outside ledger gains `site_bound_net_fmol`;
- the receiving cell's local ledger gains −`site_internalised_fmol`;
- the total gains both.
- The energy ledger gains the site free energy's change + heat − work (§3.3).
- The magnitudes gain the moved amounts and the |ΔG| terms.

**Observations:** the state columns, and three readouts at each row's state and held controls:
- `site_occupancy` [site population], B/S;
- `site_binding_rate_fmol_per_s` [site population], the net J;
- `site_internalisation_rate_fmol_per_s` [site population].

### 2.6 Occupancy and the coupling operator's regulatory state

**The relation** (**S**). The coupling operator's regulatory state follows ds/dt = k_on u (1 − s) −
k_off s, with u a product of Hill factors of a cell's species (D156; coupling note §1.5). A site
population's occupancy θ = B/S, at a free concentration that binding does not deplete, follows

    dθ/dt = m_b k_on c (1 − θ) − (m_b k_off + m_i k_int) θ.

That is the same two-state form, with k_on u ↔ m_b k_on c and k_off ↔ m_b k_off + m_i k_int.

**So the regulatory state is occupancy's material-free limit.** The two agree when:
- the depletion term S/(V (K_d + c)) is negligible;
- the input is first order in the free concentration.

The coupling note sends the other case here: "where binding sequesters a significant share, the
binding must be explicit" (its §1.8).

| | Regulatory state | Occupancy |
| --- | --- | --- |
| Material, ledger, energy | None (kinetic state) | One material ledger, the site free energy, heat and work |
| Depletion of its input | None | Yes: the free ligand is consumed and returned |
| Input | Any product of Hill factors; any species row, ions included, through the read-only list | Mass action in the facing node's free ligand |
| Where it lives | Per cell | Per population on a domain (patch or contact), with identity, partition and reset rules |

**Occupancy as a coupling source is a door** (§9). It is what ligand–receptor signalling and quorum
sensing need: a response driven by receptor occupancy.
- **The shape** (**S**). The coupling operator's source semantics would gain a source kind:
  `{"site_population": id}`, read as θ. It would feed an instantaneous factor or a regulatory
  state's input u.
- **It is a cross-operator state read.** @3's step never moves the site pools, so an instantaneous
  factor of θ is held exactly through it. That is the property the coupling note requires of
  instantaneous sources (its §1.4).
- **It belongs in the coupling note's doors,** beside FR-7(b)'s population-abundance source.
- **Built (FR-24, 20 November 2026; development):** the source kind exists on
  `species_regulated_availability@2`, read through this operator's readable quantities (the
  contract's R3: θ = B/(B + R), B and S per population) as θ, B/V or S/V in the element's cell
  ([INVENTORY_COUPLING_DESIGN.md](INVENTORY_COUPLING_DESIGN.md) §2.6). A regulatory state's input
  from occupancy is not built.

### 2.7 Per-world data and the batch signature

- **Bindings, never constants.** Copies, sites per copy, α, k_on, k_off, k_int and θ₀ are layout
  arrays bound per world; the multipliers are controls. None is a closed-over constant, and the
  crossrev records show it (D148).
- **The static structure enters the batch signature:** the law; the ligand list; each population's
  id, owner kind, owner id and face or side, its ligand, whether it has internalisation and its
  destination kind; and the component map (§3.3).
- Identities are not part of the signature, as in membrane state's.

## 3. Accounting

### 3.1 Material

- **Extent-consistent updates.** Each half-step computes its route extents once (D152 §3.1) and
  adds them to the pools, to @3's rows and to the accumulators. So Δn, ΔB and ΔR are consistent by
  construction.
- **@3's ledgers close to rounding** at the ligand's own scale: D150's species-scale floor plus
  2.5 ε × steps × the row's magnitudes.
- **The owner's ledgers** close the same way, at the same floors.
- **The system total per species** is Σ free (cells, finite nodes) + Σ bound (populations). It
  changes only through declared sources and sinks: turnover, baths, replacement's removal and
  supply. It is a guard (a test), not a third run-time ledger, since @3's total ledger and the
  owner's bound ledger already imply it.
- **The moiety identity per population**, R + B = S, holds by construction and is a guard.

### 3.2 Charge

- **Neutral ligands only in version 1** (`parse_species`'s rule). Sites carry no charge in the model.
  Every charge, drift and conductance term the operator touches is an exact zero (D150 §3).
- **No field input.** The operator provides no capacitance, area or mask, so it causes no field
  refresh and the 64-node cap does not apply to it. With membrane state in the same composition, the
  cap is membrane state's.
- **The charged door** (**S**). A charged ligand bound to a site stays on its face's side of the
  membrane. Its charge would be counted in the facing node's charge, so binding would move no charge
  across the membrane, while internalisation would carry it into the cell like a current.
  - D150 §3's exactness argument must be re-made for it.
  - It meets FR-4's buffering, by membrane sites as well as by reactions, and D152's charged door.

### 3.3 Energy: the site free energy, and D152's bookings

**The site free energy** (**S**). For population k, with S_k = R_k + B_k:

    G_site,k = B_k [ΔG°_b,k + RT ln(B_k/S_k)] + RT R_k ln(R_k/S_k),   ΔG°_b = RT ln(K_d/1 mM),

with 0 ln 0 = 0. This is the Langmuir lattice free energy of the occupied and empty accessible
sites. Its reference is the empty population, G = 0. The free site carries no standard potential;
only the difference ΔG°_b between complex and free site matters.
- **Equilibrium follows** (**S**). Setting μ_bound = μ_free gives ΔG°_b + RT ln(B/R) =
  RT ln(c/1 mM), that is B/R = c/K_d: Langmuir's isotherm.
- **The relation to the ideal form** (**S**). With S fixed, G_site and the ideal-dilute form
  RT Σ x (ln(x/S) − 1) over the pools x ∈ {R, B}, each with the standard term, differ by the
  constant RT S. So D152's machinery applies, with the capacity S in place of a volume.

**A finding: @3's chemical term holds no binding free energy, so the owner must hold it.** This is
D152's B7 finding carried over (**S**).
- @3 books RT Σ n (ln(n/V) − 1) on free rows only.
- Binding δ fmol from a node at c removes δ μ_L, with μ_L = RT ln(c/1 mM). At c = 10⁻³ mM that is
  ΔG_chem = +6.9 RT δ.
- Booked alone, the passive heat −ΔG_chem = −6.9 RT δ is negative. The dissipation check would refuse
  every binding step from below 1 mM, which covers every protein-scale ligand. Above 1 mM the heat
  would be positive but wrong.
- With the site term, the change per mole bound is RT ln(K_d B/(c R)). It is negative while binding
  runs forward (c R/K_d > B) and zero at equilibrium.

**So a site's state needs its own standard term,** answering the brief's question.
- The owner declares G_site as its endpoint free energy relative to the declared reference (v2
  §1.1's free-energy owners).
- The energy ledger adds G_site(state) − G_site(declared), evaluated in the anchored increment form
  below. D152's operator owns its standard term in the same way.

**The bookings: D152's rule, with the facing node as D152's node** (**S**; measured, §4.4).
1. **Components.** At the definition, the operator builds the static components of its route graph.
   A component is the facing nodes, populations and receiving cells that its binding and
   internalisation routes link.
2. **Class per step,** from the multipliers, by `where` with no branching (D152 §3.3):
   - a component is **passive-only** when none of its internalisation routes has a positive
     multiplier;
   - it is **mixed** otherwise.
3. **Passive-only.** Its facing nodes' sub-systems (each node's ligand row and the populations facing
   it) are then closed. Each books heat H = −ΔG of its sub-system, an exact state-function
   difference, and no work.
4. **Mixed.** Every route gets its average-vector-field share, Δξ_r Σ_j ν_jr μ̄_j, with μ̄_j each
   pool's divided-difference potential over the half-step (McLachlan, Quispel & Robidoux 1999, D152's
   form). G is separable, so the shares sum to ΔG exactly.
   - **Each binding route books D152's hybrid heat** at its facing node: its share if it does not
     reverse within the step (its three stage fluxes and end-state affinity share a sign), and its
     stage quadrature if it does.
   - **Each population's work** is its internalisation share + its binding share + its binding heat.
     So W − H = ΔG holds exactly per population and in total.
5. **What follows.** No route-level attribution enters a passive-only component, and a mixed one
   books D152's measured rule.
   - The prototype's closure residual was ≤ 1.1e-16 of the scale in 39,860 random mixed half-steps.
   - No step in its day-one runs took the quadrature (§4.5).

**D152's known limit, the reversal onset, can arise here in one place** (**S**). The binding route
reverses within a step only when internalisation drains a bound pool down through its binding
equilibrium. That happens after a washout, when the free ligand is near its trace.
- The trace rule (§4.3) puts that equilibrium below 10⁻⁶ S, so the overbooked half-step's heat is of
  order RT × 10⁻⁶ S × its log terms.
- It is recorded under D152's resolved-start rule, documented and not judged.

**The increments are stable** (**S**). For each pool x with anchor a and change δ, with S fixed:

    Δg = μ° δ + RT [δ ln(a/S) + (a + δ) log1p(δ/a)]   (a > 0),     Δg = μ° δ + RT · xlogy(δ, δ/S)   (a = 0).

- **The a = 0 branch is a real branch, not padding.** It is selected at a population's default start
  (B₀ = 0), where δ may be 0 too. xlogy gives exactly 0 at 0, so an idle pool at zero books exactly
  0.
- The divided-difference potentials use D152's stable series near x = δ/a = 0.
- Every unselected branch stays finite (D152's ruling Q11 (a)). The quadrature's affinity at B = 0 is
  +∞. It is not selected there, because binding from B = 0 runs forward through the step (**S**,
  §4.4), and it is padded finite anyway.
- @3's rows use the adapter's `species_chemical_free_energy_pJ` and `species_chemical_magnitude_pJ`
  (D150 §2.4, as built).

**What W is.** The endocytic machinery's free-energy change of the modelled inventory, plus the
hybrid's correction at the rare reversing step. The machinery's own dissipation and fuel lie outside
the model, a declared limit as in D150 §2.4. Drawing it from finite energy pools is the energy-pool
door shared with FR-2 and FR-4 (ruled: it goes with them).

**What exactness does not test.** A wrong rate is booked exactly too. The kinetics are checked
against the references (§8).

### 3.4 The energy guards of record

D150's lesson holds: under IMEX, the shared bound (2e-8 pJ + 2e-3 × the flows) is the ions' in a
mixed world. The guards check the residual itself.
1. **The face-free species-only world**, the guard of record.
   - The world: quiescent ions, and a passive cell and a finite node joined only by a patch, with no
     face. That is the topology of D150's `face_free` fixture
     (`validation/tissue/secreted_species_fixtures.py:220`).
   - The operator is the only energy flow, so the residual must be at rounding at every row:
     2.5 ε × steps × the energy magnitudes, as in D152 §3.4.
   - Each booking path is forced by a world built to take it:
     - a passive-only component (binding only, from B = 0 and from a pre-formed occupancy);
     - a mixed component at quasi-steady uptake (the share branch);
     - a washout with internalisation draining the pool (the quadrature branch);
     - the class switch, with the internalisation multiplier turned off and then on;
     - two populations sharing one node;
     - a cell that both receives internalised cargo and is faced by an inward population;
     - a closed relaxation, whose total heat must equal G(start) − G(equilibrium).
2. **A NumPy ΔG test per law**, written from Appendix A by the references agent. On random states it
   checks:
   - the booked H and W against the independently computed ΔG with the site term;
   - the class rule and the hybrid's branches, with states on each side of the selection;
   - the moiety and material identities;
   - zero multipliers selecting the start state bitwise.
3. **Negative controls**, as edits of saved histories, in D152's form:
   - work scaled by 1 + 10⁻⁶;
   - the site free energy dropped, which must also fail the dissipation check (§3.3's finding);
   - a heat of the wrong sign.

   Each must fail world 1 at the first row it touches.
4. **The mixed-world statement.** A measured bound/booking ratio in a mixed heredity world goes into
   the docstring, as D150's probe 2 part C and D152's C2 did.

**Scale** (**S**, synthetic). 10⁵ sites is 1.66e-4 fmol. Its free energies are of order S RT |ln| ≈
4e-3 pJ, 2 × 10⁵ times ENERGY_ATOL_PJ. A kinetochore-scale aggregate of about 3,500 sites is
5.8e-6 fmol, about 1e-4 pJ. Both lie above the absolute floor. The guard worlds still use µM-scale
pools in pL nodes, D150 §7's rule.

## 4. Numerics

### 4.1 Scales (**S**)

| Quantity | Value | Note |
| --- | --- | --- |
| Sites per fmol | N_f = 602,214,076 | Exact |
| 10⁵ sites (synthetic) | 1.66e-4 fmol; facing a 1 pL node, 1.66e-4 mM of sites | Can exceed a nM ligand's whole content of that node (1e-6 fmol). That is the depletion regime, where explicit binding differs from a sink |
| Kinetochore aggregate (the paper: about 3,520 Dsn1 at about 160 kinetochores) | 5.8e-6 fmol per cell | Per kinetochore, 14–36 copies: below D150 §1.3's mean-field limit of about 10² molecules. A continuum occupancy describes a cell's aggregate sites, not one structure |
| Stage rates | L_n = Σ_k m_b k_on R_k/V, L_R = m_b k_on c, L_B = m_b k_off + m_i k_int | A small node facing many sites makes L_n large: refused at dt·L > 1 (§4.2), the stiff door |
| Who sets dt | The ions in mixed worlds; the faces in species-only worlds (D150 §4.2, D152 §4.1). The operator refuses a step, but never sets one | – |

### 4.2 The half-step: D152's SSPRK(3,3), unsplit

**The integrator** is D152 §4.2's, applied to the operator's whole route network: every population's
binding and internalisation routes, every facing node's ligand row and every receiving cell's row
(Shu & Osher 1988; Gottlieb, Shu & Tadmor 2001). It runs in one sub-step, in its Butcher form:

    Y1 = y,  Y2 = y + h ν J(Y1),  Y3 = y + h ν (J(Y1) + J(Y2))/4,
    Δξ = h (J(Y1) + J(Y2) + 4 J(Y3))/6 per route,   y' = y + ν Δξ.

- It is extent-consistent, so the moiety and material identities hold by construction.
- **Nothing is split within the operator.** Competition through a shared ligand pool (several cells
  facing one node) and the binding–internalisation coupling are integrated whole. Only the
  composite's Strang split against @3's step remains.

**The stage condition is D152's.** At every stage, h max L ≤ θ = ½, with the unidirectional rates per
amount:
- L_n,i = Σ_{k facing i} m_b k_on,k R_k / V_i (consumption of the free ligand);
- L_R,k = m_b k_on,k c (of free sites);
- L_B,k = m_b k_off,k + m_i k_int,k (of the bound pool, by release and by internalisation, a driven
  route that consumes it).

So dt · L > 1 is refused at run time: D152's rule, and the coupling note's ruling 5 (no unenforced
limit).
- The rates are written as rate constants times the partner's amount, never as J/Y, so they are
  finite at zero amounts.

**Refused, never repaired.** A stage that fails the condition, or any non-finite or negative amount,
invalidates the half-step, as D152's do, and the composite returns the start state. A host-side
diagnosis gives the largest h L and the step that would admit it, since the runner's message is
generic. D152's `stage_report` is the precedent.

**No sub-steps and no implicit binding in version 1.** The stiff door (§9) is sub-steps with a
splitting that holds its order, or a positive implicit half-step. The single-population binding has
an exact Riccati solution (Appendix A.4), a candidate for that door.

### 4.3 Positivity, the domain, and the trace refusal

- **Positivity is a theorem** (**S**, D152 §4.2's SSP argument). Write f = P − C. Each consumption is
  L_x x, with L the rate constants above, so each Euler stage gives Y + h f(Y) ≥ Y (1 − h L) ≥ Y/2.
  The free rows stay positive, as @3 requires, and R and B stay non-negative.
- **Zero and full occupancy are in the domain.** B = 0 (nothing bound) and R = 0 (all accessible
  sites bound) are finite states of the law and of G_site (0 ln 0 = 0). They need no trace, unlike
  @3's free rows.
- **The anchored stall** (D150 §1.3, amended). A pool anchored at a positive value and drained follows
  its closed form until about ε × its anchor, then stalls, positive and unrefused. A pool anchored at
  zero carries its whole value in the increment.
- **Known limit: an exactly empty pool reached from a positive anchor** (found in FR-26, 20 November
  2026).
  - **What happens:** `site_free_energy`'s stable increment form evaluates such a pool as
    0 × log1p(−1) = NaN, and with it the energy ledger.
  - **No path reaches it in version 1 except W, which refuses it.**
    - *The half-step cannot reach it.* Each Euler stage keeps at least half of a pool (h L ≤ θ = ½),
      so a half-step keeps at least 0.604 of it, and the stored anchor + increment never rounds a
      positive pool to zero: the stall above. A step that ended exactly empty would fail its own
      finiteness check, through the same form.
    - *No other operator writes the pools.* `site_occupant_replacement@1` (W, §5.2) is the only
      accepted writer.
    - *W refuses it,* by the engine's trace convention: a pool goes to its trace, never exactly to
      zero (FR-23's dose rule). A template gives a newcomer's occupancy in (0, 1), and its bound and
      free sites each lie at least 4 ulps of the capacity from empty. The event writes
      anchor + (amount − anchor), which is within about 1.5 ulps of the amount, and it refuses a
      step whose pools would read as non-positive (fail closed).
  - **The check:** `/mnt/workspaces/Cells/operators-fr26-20261120/check_arrival_margin.json`. It
    samples 2 × 10⁶ capacities and anchors at 4 to 6 ulps from either end, and finds every pool
    positive, both in NumPy and in a jitted program. The jitted program rounds differently from
    NumPy in a quarter of the samples, which is why the rule is a margin rather than an emulation
    of the event's arithmetic. Below the margin, at θ′ = 10⁻¹⁷ or 1 − 2⁻⁵³, 42% of the samples read
    exactly empty.
- **The trace refusal** (ruling on question 9: "when both the trace and K_d are declared, refuse at
  the definition", with the threshold stated).
  - **Why it is needed.** D150's "absent" ligand is a trace c_bg > 0, and high-affinity sites bind
    it: at equilibrium θ_bg = c_bg/(K_d + c_bg). A trace of 10⁻⁹ mM against K_d = 10⁻⁶ mM occupies
    10⁻³ of the sites (**S**).
  - **The ruling's premise does not hold as built.** The trace is not stored in the definition:
    `add_inventory_species` takes it as an argument (`registry/inventory_species.py`). So the rule needs
    either a declared trace or a proxy for it.
  - **Proposed: (a), a declared trace.** This operator's species entry declares `trace_mM`, the
    ligand's background. The definition refuses, naming the ratio and the threshold, if:
    - any declared concentration of the ligand lies below it (cells, finite nodes, held baths,
      replacement templates), since D150 §1.3 requires every node at or above the trace; or
    - it exceeds 10⁻⁶ K_d for any population binding the ligand.

    This is the coupling operator's precedent for an enforced rule (its ruling 5). Its residual: a
    node declared above the trace is treated as present, whatever its builder meant.
  - **The alternative: (b), a proxy.** Read the ligand's lowest declared concentration as its trace.
    It needs no key, but it fails both ways.
    - *False refusal:* a ligand declared above 10⁻⁶ K_d at every node has no trace.
    - *False acceptance:* a bath or node that no site faces can hold the minimum, while a
      site-facing "absent" node sits higher.
  - **The threshold** (**S**). 10⁻⁶ keeps the trace's occupancy below 10⁻⁶ of every population's
    capacity. The background guard (§8.3, Q5) lowers the trace by 10³ from a world at or below the
    threshold, and must see every compared quantity move far below its tolerance.
  - **The cost** (**S**). A nM binder (K_d = 10⁻⁶ mM) needs a trace at or below 10⁻¹² mM. D150's guard
    worlds used 10⁻⁹ to 10⁻¹⁵ mM, and the anchored representation resolves them.
  - **Sequestration.** Sites also bind the trace itself. A node's trace content is far below a site
    pool, so its free trace falls toward the anchored stall: positive, and no refusal.

### 4.4 The heat sign

- **For the exact flow,** H ≥ 0 at every passive-only sub-system. It is closed and
  detailed-balanced, so G is its Lyapunov function (Rao & Esposito 2016; D152 §3.3).
- **For the integrator, one population on its own node** (**S**). A passive-only sub-system is then
  one-dimensional along the binding extent.
  - |f′| = L_n + L_R + m_b k_off ≤ 3 max L, so h |f′| ≤ 1.5 under the condition.
  - SSPRK(3,3)'s amplification R(z) = 1 + z + z²/2 + z³/6 lies in [0.0625, 1) for z ∈ [−1.5, 0]; its
    real root is near −1.596.
  - So the linearised step approaches the binding equilibrium without crossing it. G is convex along
    the extent, so the step lowers G: H ≥ 0. D152 proved the linear A ⇌ B case the same way.
- **Measured before acceptance** (the prototype, `probe-split/`; random states with h max L up to ½,
  including starts near the binding equilibrium and from B = 0):

  | Case | Admitted half-steps | Negative heats | Smallest heat over the energy scale |
  | --- | --- | --- | --- |
  | Passive-only, one population | 19,939 | 0 | 1.6e-20 |
  | Passive-only, two populations sharing a node | 19,894 | 0 | 9.7e-19 |
  | Mixed (binding and internalisation), one population, D152's hybrid | 19,928 (3,839 quadrature routes) | 0 | 7.0e-20 |
  | Mixed, two populations sharing a node | 19,932 (6,868 quadrature routes) | 0 | 2.1e-18 |

- **What remains a guard.** A falling heat in an unmeasured configuration is refused loudly by the
  dissipation check (D152's rule). One example is a cell that both receives internalised cargo and is
  faced by an inward population. World 1 of §3.4 covers it.

### 4.5 Splitting, and the palindrome measured and rejected

**Against transport.** D152's probe C3, world W2 (A + B ⇌ C with B and C immobile, on a diffusing
chain) is this primitive's structure against @3's faces. It held second order to dt · L ≈ 2, with
order reduction beyond (D152 §4.3). Version 1's refusal of dt · L > 1 sits inside that margin. C3 is
D152's prototype evidence, not a reference of record; this operator's own dt study is its evidence.

**Within the operator: nothing is split.** An earlier draft split internalisation from binding in a
palindrome, Int(h/2) Bind(h) Int(h/2). It hoped for single-class bookings without D152's hybrid. The
lead's review pointed out that binding with site-conserving internalisation is D152's enzyme recipe
(R + L ⇌ RL, then RL → R + L inside), the mixed case where D152 rejected an intra-node split. It
asked for the choice to be decided on measured cost.

**The measurement** (the prototype, 14 s on one thread; `probe-split/result.json`):
- **The day-one world:** one population on a closed node; synthetic, compressed rates, k_on = 10⁴ mM⁻¹
  s⁻¹, k_off = 10 s⁻¹, k_int = 10 s⁻¹; V = 1 pL, c₀ = 10⁻³ mM; occupancy pre-formed at its quasi-steady
  value; run to two depletion half-times.
- **The reference:** DOP853 at rtol 10⁻¹², with the dissipation and work integrals carried as extra
  states.

| Quantity | Palindrome | Unsplit (D152's scheme and hybrid) |
| --- | --- | --- |
| Node amount, worst error over the run (of n₀), dt = 8, 4, 2 ms (h max L = 0.08, 0.04, 0.02), ε = 0.1 | 9.7e-5, 2.5e-5, 6.2e-6 (ratios 3.94, 3.97: second order) | 3.8e-8, 4.5e-9, 5.5e-10 (ratios 8.39, 8.19: third order) |
| The same at ε = 0.01 | 8.9e-5, 2.2e-5, 5.7e-6 | 6.1e-12, 7.3e-13, 8.5e-14 (ratios 8.27, 8.56) |
| The same at ε = 0.001, dt = 8, 4 ms | 8.8e-5, 2.2e-5 | At rounding (5e-15) |
| Total heat against the exact integral, ε = 0.1 | 1.9e-4, 4.9e-5, 1.2e-5 | 3.3e-6, 8.6e-7, 2.2e-7 (the share: second order) |
| Total work against the exact integral, ε = 0.1 | 6.9e-5, 1.6e-5, 4.0e-6 | 4.8e-6, 1.3e-6, 3.2e-7 |
| Quadrature steps in these runs | – | 0 |
| Steady occupancy and uptake at a fixed free concentration | A second-order steady bias, matching its closed form to 6e-14. At the stage condition's extreme (h k_on c = ½, h k_int = 0.499): occupancy −2.7%, uptake −1.7%. At dt = 1 ms for rates up to 10 s⁻¹: at most 3.1e-6 | None: the fixed point is the true steady state, to rounding |

**The reading.**
- **The palindrome's bias sits in the guard's own quantity.** Its error is a steady bias of the
  quasi-steady uptake, the quantity the day-one guard measures.
  - In the day-one world it is about 3 × 10³ to 7 × 10⁷ times the unsplit scheme's error, which
    reaches rounding at ε = 10⁻³.
  - At ε = 10⁻³ it is 40% of the ε term itself (2.2e-4 of n₀) at dt = 8 ms.
- **The unsplit scheme has no such bias.** At a fixed concentration its fixed point is exact. Its
  heat attribution, the hybrid's share, is second order and 60 times more accurate here.
- **The hybrid's costs did not appear.** Its known limit did not arise in the day-one runs, and its
  heat stayed non-negative in about 40,000 random mixed steps (§4.4).
- **So D152's scheme is adopted,** and the palindrome is recorded here as measured and rejected.
- **"Realistic receptor rates" are bracketed, not asserted.** No sourced receptor parameter set was
  reached: Shankaran et al. 2007's parameter table is an image, not read, and Wiley & Cunningham
  1981's abstract was not available. The bracket covers every rate up to 10 s⁻¹ at dt = 1 ms.

### 4.6 Which solvers admit it

| Solver or mode | Version 1 | Reason |
| --- | --- | --- |
| IMEX ARS(2,2,2), IMEX Euler | Admitted | The composite's split parts |
| RK4 (reference runs) | **Refused** at the definition (ruled) | D152 §4.6's reasons hold: (b) the bookings are exact and checked at rounding in the face-free world under IMEX, so RK4's absolute bound adds nothing; (d) D150's RK4 worlds stay the transport's sharp reference; (c) RK4's 1e-4 s step limit; and no consumer needs it |
| Stationary analysis | Refused (ruled) | It refuses the composite's ID (D150 probe 2); its Newton test is not scaled per species (D150 §8) |
| Projective and coarse modes | Not admitted | `execution.projective` supports @1 to @3 only |
| vmap, windows, restart, snapshots | Admitted | Per-world parameters and controls are bindings; all state is state (R7) |

**The long-time door** (**S**, for FR-8's note). The primitive's quasi-steady limit is D150's sink,
which is already exact over any step. A long-time mode that makes binding algebraic (quasi-steady
occupancy from the free concentration, with the sink as the uptake) has a qualified target on each
side.

### 4.7 Cost and the 30-minute rule

- **Cost** (**S**). Per half-step, one SSPRK(3,3) stage: three rate and three stage-condition
  evaluations over the routes, plus one divided-difference potential per pool for the hybrid. That
  is O(routes), small beside the dense field (D150 §4.4). The operator adds no species row and no
  field node.
- **The 30-minute rule** (**S**). With neutral, impermeant ligands at fixed volumes, the site
  equations are decoupled from the ions. Their discrete problem depends only on dt times the rates,
  the ratios S/(V K_d) and c/K_d, and the geometry. Compressed worlds with rates of order 1 to
  10 s⁻¹ exercise the same discrete operator in seconds to minutes of CPU. True-parameter runs are
  detached tier-3 runs.

### 4.8 Idleness (D136)

There are three claims, in D150's and D152's form.
1. **Not declared. Promised.** Every existing composition's jaxprs, constants and bindings are
   identical under the constants-aware crossrev, in all five sets and in D150's and D152's own sets.
   The operator is a new module, and no shared code changes (§6.3).
2. **Declared, but idle. Promised.**
   - No populations: statically idle.
   - Every multiplier of a component zero in a step: its half-step selects the start state with
     `where`, never adding a computed zero.
   - Every field is then bitwise equal to the composition without the operator.
3. **Populations declared and inert, against none. Reported, not promised** (D150's claim 3): the
   reduce order over the population axis is program-specific.

## 5. Partition and reset at division and replacement

The rules are declared now so that the state fits them. Version 1 refuses both compositions: closers
through `CONFLICTS_VIEW`, and replaced slots at the definition. The doors are named.

### 5.1 Division (the partition, S5)

**The declared rule.** A population moves with its owner's map. The extensive quantities split by
the owner's fraction:
- a patch population by a_k, its patch's area fraction (S5 §3: a population takes its patch's
  fraction);
- a contact population by a_e.

The split covers copies, free sites R and the bound pool B. The daughter populations are the parent's
functional unit, with anchors as exact fractions (S5 §3.2's fl(a x), fl(x − fl(a x)) rule).

**What follows** (**S**):
- **Occupancy is intensive and preserved:** θ in each daughter equals the parent's.
- **The free energy changes by exactly zero.** G_site is homogeneous of degree 1 in (R, B, S), so
  G_site(aR, aB; aS) = a G_site(R, B; S). The two daughters' terms sum to the parent's, and nothing
  is booked.
- **The ledgers.** The partition books the moved amounts as signed transfers summing to zero per
  parent population, as it books `partition_units_moved`.
- **Bound cargo keeps its identity:** the same species, on the same functional unit, in each
  daughter.

**The door.** A partition version that writes this operator's pools through `ACCEPTS_WRITES`, with
the liveness rule designed once for D150's, D152's and the coupling operator's state (coupling
ruling 8; W1 of its §3.2). The partition `REQUIRES` membrane state @1 (`partition.py:935`), which
option O leaves unaffected.

**Other owners, later** (**S**). Sites on an intracellular structure would follow the structure's
segregation, not an area fraction. A declared fraction is the general form, and the structure owner
is a door (§9).

### 5.2 Replacement (`scheduled_cell_replacement@1`)

**The declared rule:** carriers have identity, slots are storage (D150 §5.2; D139).
- **The occupant leaves with its sites and its bound cargo.** Its bound pools are booked as removed,
  per species, beside replacement's `replacement_removed_fmol`. Its site free energy leaves with
  them, in the event's free-energy booking.
- **The newcomer arrives with its template's declared site state:** copies, sites per copy, α, its
  ligand's constants and initial occupancy (D150 §2.5 requirement 4: "templates declare the
  newcomer's occupancy").
- **A donor copy** takes the donor's site state, under D150's ruling for donor route values: admitted
  only where the declared values equal the slot's.
- **Never from the previous occupant.**
- **Contacts incident to a replaced slot** restart. Their populations reset to a declared arrival
  state, as the formation law restarts their abundance from its declared arrival state.

**Version 1 refuses** populations on patches of replaced slots and on contacts incident to them, at
the definition, reading replacement's schedule as D152 does.
- Populations of cells that are not replaced, and of contacts between such cells, compose.
- The door is D150's occupant tables plus an event part of this operator at replacement's event
  steps, as the coupling note's version 1.1 reset is designed.

**Built (FR-26, 20 November 2026; development): W, `site_occupant_replacement@1`** (D244 chose W over
an event part of this operator; [OPERATOR_FEATURES_FR23_24_26_DESIGN.md](OPERATOR_FEATURES_FR23_24_26_DESIGN.md)
§4).
- **What it is:** a law of its own in this module, declared after this operator and replacement@1.
  This operator and replacement@1 keep their structure and programs.
- **What its event map does:** at replacement's event steps, it resets each patch population (either
  face) of a replaced slot through this operator's accepted writes:
  - B′ = θ′S, from the newcomer's template (W's `templates`, keyed by replacement template ID);
  - R′ = S − B′.
- **What it records:** the departed B, the arrived θ′S and the site free energy's jump (formed from
  the endpoints).
- **How its books close:** this operator's bound ledger through W's external terms, and @3's energy
  ledger through its own term.
- **The multipliers follow the occupant:** the founder's schedule ends at its death, and a newcomer
  takes its template's multipliers, held through its life.
- **Refused in version 1:**
  - contact populations incident to a replaced slot;
  - donor copies onto a slot with populations;
  - a newcomer's occupancy of exactly 0 or 1, or within 4 ulps of the capacity from either end. By
    the engine's trace convention a template gives a fresh cell's occupancy at a trace level (§4.3,
    the known limit);
  - templates that change capacity or constants.

### 5.3 The chain: binding (FR-3), internalisation with membrane (FR-2), delivery (FR-1)

What each step writes, so that the bound pool's identity survives each transfer. This is **S**: FR-1
and FR-2 have no accepted design yet.

| Step | Writer | What moves | Identity |
| --- | --- | --- | --- |
| Binding at the surface | This operator (version 1) | Free ligand at the facing node ↔ B on the population | (species, population) |
| Site-conserving internalisation | This operator (version 1) | B → the patch's cell's row; the site stays | (species) in the cytosol: FR-1's identity loss, version 1's stated limit |
| Internalisation with membrane | FR-2's retrieval law, through `ACCEPTS_WRITES` of both owners: membrane state's channels and this operator's sites | A fraction of the patch's area, with that fraction of each population's R and B, onto the compartment's bounding patch | (species, population): cargo stays bound on the moved membrane |
| Release into the compartment | This operator's binding law, at the moved population's facing node | B → the compartment's free row (release at k_off; a pH-conditioned release is FR-4's and FR-5's routing door) | (species) inside the compartment, distinct from the cytosol |
| Recycling or degradation | FR-2's exocytic direction, or a sink law | Sites back to the surface, or consumed | Population abundance |

**What this note asks of FR-1** (as FR-1 proposes; FR-1 is not yet accepted; §6.4):
- **The lumen faces the population.** FR-1 proposes the compartment as a face-free finite node with
  the lumen as its bounding patch's outside node. An outward-facing population on that patch then
  faces the lumen, and release needs no new rule. The outer leaflet faces the lumen after
  endocytosis (**S**).
- **The site operator can tell the nodes apart.** FR-1's declaration names each compartment node, so
  the site operator can distinguish an extracellular finite node from a compartment and refuse
  internalisation from a compartment-facing patch.
- **FR-1's admitted list names `site_occupancy@1`.** That list fails closed as FR-1 proposes it.

**What this note asks of FR-2.**
- Its retrieval moves this operator's pools by the same area fraction as the membrane, through
  `ACCEPTS_WRITES`. It writes two population owners (ruling on question 1).
- Its energy source, the shared energy-pool design, also serves this operator's internalisation work
  (§3.3).

## 6. Composition

### 6.1 With the existing operators

| With | Version 1 | Why |
| --- | --- | --- |
| @3 alone; `electrode_current_injection@1` | Composes | No view conflict. Injection refuses neutral carriers |
| D150's `scheduled_species_turnover@1` | Composes | Writers of the same rows; fluxes add, split at O(dt²) |
| D150's `scheduled_species_exchange@1` | Composes | Both read the declared volumes; secretion beside binding is the autocrine and paracrine case. Declaring the saturable sink and the primitive for one uptake would double-count; that is the world's choice, flagged in the summary |
| D152's `local_species_reactions@1` | Composes, including on a row both write (ruled) | Binding is a surface process across a patch, as exchange is. D152's one-local-kinetics-writer rule refuses turnover, not exchange (its §1.1), and D152 has no admitted-operator list. So no edit to D152's files is needed; they are held for MG0c's registration. Split at O(dt²), measured by the composition world (§8.3) |
| The coupling operator (`species_regulated_availability@1`) | Composes | It reads cell rows that this operator writes in half-steps; reads are not writes. Occupancy as a coupling source is a door (§2.6) |
| `membrane_entity_state@1` | Composes | No conflict: it provides views this operator never reads. The composition is then a field-input composition because of membrane state. Areas do not move without insertion, which is refused |
| `scheduled_cell_replacement@1` | Composes off replaced slots | §5.2 |
| Water; the lumens; replacement@2 | Refused (volumes) | Concentrations and ΔG read the declared volume. The door is D150 §5.1's `VIEW_READS` with bookings at the view |
| Insertion@1 and @2; the partition; the bridge | Refused (masks) | Insertion@1 provides the masks and outside anchors (`membrane_insertion.py:480–485`); the others are closers. The door is §5.1's liveness rule |
| The k-anion symport | Waits | It requires water |
| `cell_owned_compartments@1`, as FR-1 proposes (not accepted, not on main) | Not admitted until FR-1's admitted list names this operator | That list fails closed as proposed. Under option O there is no field-input reason (§6.4) |

### 6.2 Refusals

**At the definition:**
- **Ligands:**
  - a charged or permeant species (`parse_species`, `check_impermeant`);
  - a species the model does not declare;
  - an identity that differs from another inventory operator's (§1.6);
  - more than `MAX_SPECIES` species in the world (`check_species_cap`, with its message);
  - under §4.3's proposal (a): a declared concentration below the ligand's declared `trace_mM`, or
    a trace above 10⁻⁶ K_d of a population binding it.
- **Owners:** an unknown patch or contact; an outward-facing population on a patch that faces a held
  bath. The bath's composition is held, and binding from a chemostat, booked as reservoir supply, is
  a door.
- **Populations:** copies ≤ 0; sites per copy not a positive integer; α outside (0, 1]; a ligand not
  listed; initial occupancy outside [0, 1].
- **Laws:**
  - k_on ≤ 0 or k_off ≤ 0; k_int < 0;
  - internalisation on an inward-facing patch, a contact or a compartment-facing patch;
  - a destination other than `"cell"`.
- **Slots:** a population on a patch of a replaced slot, or on a contact incident to one.
- **Solvers:** RK4; the stationary analysis.
- **View conflicts** (§1.5).
- **Schedules:** a route without a schedule; one not starting at 0; a change off the dt grid or
  outside the horizon; a negative multiplier; any schedule of α, copies, sites per copy or the rate
  constants.
- **Keys:** unknown keys; duplicate IDs.

**At run time:** the stage condition (dt · L > 1); a non-finite or negative amount; a free row not
positive. Each is returned as the half-step's validity, since @3's domain is not re-run after the
second half (D150 §2.2). The composite's dissipation check refuses a falling heat.

### 6.3 Crossrev, the batch signature, D148

- **Crossrev.** The five existing sets and D150's and D152's own sets are identical.
- **The operator's own set** gets its first record at landing. Two value twins with every parameter
  and multiplier changed must give identical jaxpr text and constants, with only bound arrays
  differing (D152's ruling Q11 (b)).
- **No shared change in version 1.** The identity check runs inside this operator (§1.6). The SSPRK(3,3)
  stages and hybrid bookings are written for it from D152 §3.3, §4.2 and Appendix A's equations, and
  D152's module stays untouched during MG0c. A later shared helper is adopted under crossrev, as the
  coupling note's ruling 7 did for the Hill factor.
- **The species cap** is referenced symbolically, through `check_species_cap`. It is 16 in code since
  D165's D148 change landed (14 November 2026).
- **D148 items later:** the shared identity list (§1.6), after FR-9 and outside MG0c's window.

### 6.4 Beside a compartment, as FR-1 proposes

FR-1's note (`docs/CLOSED_COMPARTMENT_DESIGN.md` on the FR-1 branch) is proposed and not accepted.
It refuses field-input providers beside a compartment, membrane state and insertion among them, and
its admitted-operator list fails closed.
- **Under option O the operator provides no field input,** so that wall does not arise between FR-3
  and FR-1.
- **What remains:** FR-1's list naming this operator, and this operator refusing internalisation from
  a compartment-facing patch (§5.3).
- **The cap returns with FR-2.** Retrieval moves area and capacitance, so it is a field-input
  provider whatever FR-3 does. The door it needs, field-input providers beside a compartment node,
  is FR-1's and FR-2's. With one compartment per cell, a 64-node world holds about half as many
  cells (FR-1 §3.6, **S** there).

## 7. Generality (D144): the consumers, against version 1 and the doors

| Consumer (source) | What it needs | Version 1 | Door |
| --- | --- | --- | --- |
| The saturable uptake limit (D150 §2.5) | Binding with site-conserving internalisation | **Yes** | – |
| Receptor-mediated uptake with surface depletion (FR-2's requester) | Sites consumed and returned | Binding only | FR-2's internalisation with membrane |
| Delivery into a compartment (FR-1's requester) | Cargo distinct from the cytosol | – | FR-1's destination and FR-2 (§5.3) |
| Competition between cells for a shared dose (FR-2's requester) | Several cells' populations facing one node | **Yes** | – |
| Ligand–receptor signalling (FR-3) | Occupancy driving a response | Binding: **yes** | Occupancy as a coupling source (§2.6) |
| Engineered quorum-sensing consortia (FR-3; the requester's reading list, not in the repository and not read) | Finite receptor pools per cell reading a shared signal | Binding: **yes** | The occupancy source (§2.6) |
| Kinetochore-like sites (D150 §2.5; the kinetochore review) | Sites present but inaccessible against a large free pool | α: **yes**, with inward-facing or contact populations as cytosol-facing owners | An intracellular-structure owner, with a segregation rule. No kinetochore entity (the review; D144) |
| Accessibility by surface composition (FR-3: the 2026 glycocalyx and protein-corona work; the requester's text, not read) | Uptake of one formulation differing by cell type, without naming a receptor | Static per-domain α: **yes** | Regulated: §2.3 |
| Antagonists, occluders, modification states | Several ligands per population | – | Competition (ruled a door) |
| Junction docking (D150 §2.5) | Binding between two populations across a contact | Contact-owned populations binding a cytosolic species: **yes** | A docking law writing junction abundance: the mechanistic form of the coupling note's contact-maturation process (its §3.3); about 3–5 agent-days with its design (**S**) |
| Surface catalysis (D150 §2.5; D152 §2.2) | A driven fate of the bound complex into a product at the facing node | – | A second driven route kind, with D152's moiety rules |
| Morphogen gradients with binding (D150 §6: FCS free D against FRAP effective D; Kicheva 2007's immobile fraction; Yu 2009's receptor sink) | Binding to cell-surface sites beside face transport | Binding with faces: **yes** | Its qualification against the fast-binding limit D/(1 + (S/V)/K_d) (Appendix A.6) is a later item (§8.3) |
| Buffering by membrane sites (FR-4) | Charged ligands | – | The charged door (§3.2) |

## 8. Qualification

### 8.1 The first acceptance is numerical (D138)

**Can a version 1 run differ from its references?** Only by discretisation error, and by the
splitting error against transport where faces act (**S**):
- the law's equations are the declared ones;
- the ligands are neutral and impermeant, so they are decoupled from the ions;
- the volumes are fixed.

A comparison with a paper's data would test that paper's binding model and parameters, not the
engine. So the first acceptance is numerical qualification against mathematics: closed forms, and an
independent integration of the declared equations. That is within D138 on the lead's reading of
MG0c (D152 question 9), and numerical-first is standard (ruled).

### 8.2 The references

- **Written by an agent that never reads the operator's code,** from Appendix A, with a usage note.
  The engine agent runs them only through that note, as in S5, D152 and the coupling note.
- **R-ode, the judged reference:** the declared ODE (A.2) integrated by SciPy at tight tolerance
  (Radau, cross-checked by DOP853, as D152's references are). It carries the dissipation and work
  integrals as extra states. It covers depletion, internalisation and populations sharing a node.
- **R-closed:** the closed forms of A.4, checked against R-ode on the reference side. The closed
  node's forms are also judged against the engine directly.
- **R-qss:** D150's saturable closed form with A.5's unit map. It is a reference-side check of
  R-ode's convergence in ε, never compared with the engine directly.
- **R-dG:** the NumPy ΔG test per law (§3.4 item 2).
- **R-eq:** an independent equilibrium solver for shared-node worlds, and the relaxation's total heat
  G(start) − G(equilibrium).

### 8.3 The acceptance items

Tolerances are pinned at registration from the dt studies and the references' own terms (D150 §6's
rule). Each judged run is made once, from a clean snapshot.

**No engine world holds a free concentration exactly** (**S**). Version 1 refuses sites facing a held
bath, so a "fixed c" world is a large node. Its residual depletion is of relative order
S/(V (K_d + c)).
- **So every item judges the engine against R-ode, or R-eq, at the world's true V,** which carries
  the depletion exactly.
- **The fixed-c closed forms are checked against R-ode on the reference side,** with the depletion
  term stated.
- **The closed node's forms are exact for their worlds,** and are judged directly: the Riccati
  solution and the depletion quadratic.

**The expected order depends on the world** (**S**).
- **Third order in face-free worlds,** with or without internalisation: the operator's whole network
  is one SSPRK(3,3) stage per half-step, and nothing between the two half-steps touches its rows.
  - The prototype's solid evidence is ε = 0.1: ratios of 8.39 and 8.19.
  - At ε = 0.01 the errors fall to or below the reference's rtol (10⁻¹²), and at ε = 10⁻³ they sit
    at rounding.
  - So an order is judged only where the errors stand above the reference's floor, and the dt
    study registers that floor.
- **Second order where faces carry the ligand** (Strang against transport).

| Item | World | Shows | Criterion |
| --- | --- | --- | --- |
| **Q1, day one: binding with internalisation against its full kinetics** | Face-free: one passive cell; an outward-facing population on its patch, facing a closed finite node of volume V; occupancy pre-formed at its quasi-steady value at c₀; binding and internalisation. A sweep ε = (S/V)/(K_M + c₀) ∈ {10⁻¹, 10⁻², 10⁻³}, rates fixed and S varied | (a) **Judged:** the engine against R-ode at each ε, under dt refinement: the node's and the cell's amounts, B, and the heat and work against R-ode's integrals. (b) **On the reference side:** R-ode against R-qss, with the unit map A·V_max = k_int S and K_M = (k_off + k_int)/k_on | (a) The dt study, third order where the errors stand above the reference's floor (prototype at ε = 0.1: 8.39 and 8.19). (b) The observed order in ε, expected 1 (Segel & Slemrod 1989; prototype: 0.98 and 0.998), with the validity regime stated. **No engine-to-engine comparison with exchange's saturable law:** it would be judged nowhere, D150's scope excludes exchange, and FR-1 refuses saturable loading (ruled) |
| **Q2, equilibrium occupancy** | Large V; small V; two cells' populations facing one node | The engine against R-eq at the true V in every world, and against the depletion quadratic directly in the small-V world. On the reference side, R-eq against the Langmuir isotherm with the depletion term stated. The total heat to equilibrium | Long-time state within the steady tolerance; heat against G(start) − G(eq) |
| **Q3, binding kinetics** | Large V (association, dissociation); a closed node (depletion); internalisation in a large V | The engine against R-ode at the true V, and against the Riccati form directly in the closed node. On the reference side, R-ode against the pseudo-first-order exponentials and the linear internalisation form | Third order, at every record |
| **Q4, accessibility as a pure factor** | α ∈ {1, ½, ¼} (exact binary fractions), at c ≪ K_d and c = 100 K_d, in a large V; Q1's world at α = ½ | **Judged on the engine,** against R-eq and R-ode at the true V: equilibrium θ(α)/θ(1) = α in both regimes; saturation at α; a relaxation rate independent of α; and Q1's world at α = ½. **The depletion term scales with α**, so Q4's worlds choose V to put S/(V (K_d + c)) at least 10³ below Q4's registered margin (**S**). **Negative controls,** on the same engine quantities: (K) implemented instead fails at c ≪ K_d and in the rate; (A) fails at saturation, where θ → 1 against α, an order-one difference. **On the reference side only:** the sink's V_max ∝ α with K_M unchanged, which carries the sink's O(ε) model error (blocking item 2) | The engine against R-eq and R-ode within their tolerances; the α-scaling within the margin; each control caught by a registered margin |
| **Q5, accounting and energy** | §3.4's worlds | The material, moiety and system-total identities at the species' floors; the face-free residual at rounding; heat ≥ 0 on every row; the NumPy ΔG test; the negative controls; the background guard (lowering a trace at or below 10⁻⁶ K_d by 10³ moves every compared quantity far below its tolerance) | As stated |
| **Q6, idleness, restart, vmap, crossrev, signature, refusals** | Existing sets; Q1–Q3 worlds | §4.8's claims 1 and 2; restart bitwise at, before and after a multiplier change, also through a written snapshot; a vector batch mixing every parameter, bitwise against its reverse and within 1e-12 of each scalar run; the signature refusing different structures; each refusal with its message | As claimed |

**Later items, not the first acceptance:**
- **The composition world with faces.** Binding to sites on every node of a chain, against the
  fast-binding limit D/(1 + (S/V)/K_d) of A.6, and against R-ode's diffusion–binding system under
  refinement. This is D152's C5 analogue, the bridge to D150 §6's FCS-against-FRAP distinction, and
  the measurement of the split against D152's reactions on a shared row.
- **A biological comparison,** only when a consumer registers one (D151). The candidates are D150 §6's
  Fgf8, Dpp and Wingless records. None is proposed here.

### 8.4 What is not claimed

- **No reproduction of the kinetochore counts.** That test is the review's rank 3, deferred under
  D151 (first written "not recommended"). It needs kinetochore-specific topology to score six numbers
  from one species in one arrested state. The primitive represents the review's constraint through α,
  which is what α means. That is a value check of the factor (Q4), not a biological result.
- **No claim about the glycocalyx or quorum-sensing work.** It is the requester's text, not found in
  the repository and not read.
- **No claim about receptor-kinetic values.** Every value in this note and its probe is synthetic.

### 8.5 Pre-acceptance and pre-code probes

| Probe | Purpose | Status |
| --- | --- | --- |
| P1, the contract fit (the code's milestone 1, as D152's C1) | That the operator fits the contract as built: the field map (one owner per row, the `ACCEPTS_WRITES` wiring with no writer), the ledgers at the species' floors, the face-free world at rounding, idle and restart. It tests code, not an assumption of the note | After acceptance, as milestone 1. Criteria: bitwise idle; every ledger at its floor; residual/allowance ≤ 1 on every row |
| P2, the split's cost | Whether the palindrome's steady bias was acceptable. The scheme choice rested on it | **Run before acceptance** (§4.5). It decided the scheme: the palindrome was rejected and D152's adopted. Its closed form matched the scheme to 6e-14 |
| P3, the heat sign | Whether admitted binding steps book non-negative heat, passive-only and mixed, with one or two populations on a node. The bookings rest on it | **Run before acceptance** (§4.4): no negative heat in 79,693 admitted half-steps |
| P4, the trace threshold | Whether 10⁻⁶ K_d keeps the trace's effect below the tolerances | Closed by the arithmetic of §4.3 and the ruling. The background guard (Q5) checks it in the judged worlds |

## 9. Limits and doors

**Version 1 includes** the operator `site_occupancy@1`, with:
- site populations on patches (either face) and contacts (one side), one ligand each;
- Langmuir binding with a static per-domain accessibility;
- site-conserving internalisation into the patch's cell;
- the owned site free energy, and D152's bookings;
- D152's SSPRK(3,3) half-step;
- IMEX inner steps, vmap, windows and restart;
- composition as in §6.1.

**The doors** (each needs its own design and qualification):

| Door | What it needs |
| --- | --- |
| Internalisation with membrane (FR-2) | FR-2's retrieval writing these pools and membrane state's through `ACCEPTS_WRITES`; its energy source |
| A compartment destination (FR-1) | FR-1's node; a destination key value; refusal of internalisation from a compartment-facing patch |
| Partition | A partition version writing these pools; the one liveness rule (coupling ruling 8) |
| Replacement | Built (FR-26): W, `site_occupant_replacement@1`, on D150's occupant tables (§5.2). Contact populations and donor copies remain doors |
| Volume (water, the lumens) | D150 §5.1's `VIEW_READS` fallback and bookings at the view |
| Regulated accessibility | The kinetic form through the routing door (D156); a regulated capacity with its work booking and its rule for a fall below occupancy (§2.3) |
| Competition (several ligands per population) | Shared free sites; the competitive Langmuir law; its references |
| Occupancy as a coupling source | A cross-operator state read in the coupling operator's source semantics (§2.6) |
| Surface catalysis | A driven route from the bound complex to a product at the facing node, with D152's moiety rules |
| Docking between populations | A population-to-population law across a contact, writing junction abundance |
| An intracellular-structure owner | A cell-owned population with a declared segregation fraction |
| Binding from a held bath (a chemostat) | Bookings as reservoir supply with μ_b work |
| Charged ligands | §3.2's charge rule; FR-4's buffering |
| Stiff binding (dt · L > 1) | Sub-steps with an order-holding splitting, a positive implicit half-step, or the exact Riccati stage for single-population nodes |
| Cooperative or multivalent sites; irreversible capture | Their own laws |
| Site turnover (synthesis, degradation, constitutive internalisation of free sites) | A writer of R and copies, booked as population abundance |
| Owner and law split | A state owner without `VIEW_FIELDS` admitted by the contract (`contract.py:335–341`), when a second law writes the pools |
| Energy pools | Internalisation's work drawn from finite pools, with FR-2 and FR-4 (ruled) |

**What this note does not authorise:**
- code before it is accepted (D142);
- any change to membrane state, the partition, replacement, D150's or D152's operators or designs,
  the coupling operator, `species_common`, @3, or the composite and adapter;
- a law or population named for a receptor, a protein or a study (D144);
- reproducing a paper's model (D138, D151);
- any scientific acceptance. Integration grants none.

## 10. Effort and order of work

| Part | Agent-days |
| --- | --- |
| Milestone 1, the contract fit (P1): spec, parser, refusals (owners and contacts, faces, the ligand, destinations, accessibility, the trace rule, identities, cap), binding layout and the component map | 1.25 |
| The half-step: D152's SSPRK(3,3) over the network, the stage condition, extents, the bookings by component class with the per-route hybrid, the site free energy, idle selection | 1.5 |
| Ledger terms, own ledgers, observations, the summary, the tier-1 smoke (under 20 s) | 0.5 |
| Guards in the branch: the face-free energy world and its cases, negative controls, positivity, restart, vmap, the crossrev set, refusals | 1.0 |
| **Independent references, by a second agent that never reads the operator's code:** R-ode, R-closed, R-qss, R-dG, R-eq and the usage note | 1.0–1.5 |
| The numerical protocol and its judged run (CPU, under an hour) | 0.5–1.0 |
| **Total** | **about 6 (5.25 to 7)** |

Contacts are included (about 0.25–0.5 of the first row). Option M (§1.3) would add about 1.5 days
(**S**).

**Order:**
1. **This note's acceptance,** after the lead's review with the advisor.
2. **Milestone 1**, the contract fit, in the checkout behind its guards. Nothing blocks it: @3, D150's
   adapter functions and helpers, and D152's equations are on main, as is D165's cap
   of 16.
3. **The operator and its guards.**
4. **The references agent** starts once milestone 1 has fixed the declaration, as for the coupling
   note (its ruling 11).
5. **The protocol** and its judged run.
6. **The doors**, in FR-1's and FR-2's order (D167). Internalisation with membrane follows FR-2's
   design; the compartment destination follows FR-1's code.

Each step lands behind its tier-1 tests; tier 2 runs before landing (AGENTS.md). Long runs go through
`scripts/run_detached.sh`. No GPU is needed.

## 11. Questions and rulings

The lead ruled with the advisor on 14 November 2026. Each ruling is recorded against its question,
and the text above follows it. There are no questions for the user (ruled):
- numerical-first acceptance is standard;
- energy pools go with FR-2 and FR-4;
- regulated accessibility uses the routing door.

**Blocking items of the review, and how each was closed:**
1. **The palindrome.** Measured in a NumPy prototype before acceptance, at the stage condition's
   extreme and across a rate bracket. Its steady bias sits in the guard's own quantity, the steady
   uptake. D152's unsplit scheme and per-route hybrid are adopted (§4.5).
2. **The day-one guard.** It is judged against R-ode, an independent integration of the full binding
   kinetics. The saturable sink is tested on the reference side as convergence in ε, and there is
   no engine-to-engine comparison with exchange (§8.3, Q1).
3. **Accessibility.** α is static in version 1; regulated forms are doors, with their rules
   (§2.3).

**The questions:**
1. **The owner** (§1.3): option O or option M?
   - *Ruled:* option O. The reason recorded is the per-step capacitance refresh and the 64-node cap,
     not walls that version 1.1 lifts. FR-2 must then move two population owners.
2. **Accessibility** (§2.3): the capacity form?
   - *Ruled through blocking item 3:* the capacity form, static in version 1.
3. **Internalisation in version 1** (§2.4): site-conserving only?
   - *Ruled:* yes.
4. **The scheme** (§4.5): the palindrome or D152's hybrid?
   - *Ruled through blocking item 1:* decided on measured cost. D152's is adopted.
5. **Owners in version 1** (§1.1): estimate what contacts cost before narrowing to patches; include
   them if they are cheap.
   - *Ruled.* About 0.25–0.5 agent-days, so they are included. Docking is a separate door.
6. **Ligands per population** (§2.2): one or several?
   - *Ruled:* one in version 1; competition is a door.
7. **D152 on a shared row** (§6.1): compose, like exchange?
   - *Ruled:* yes, provided no edit to D152's files is needed. None is.
8. **The refusals** of RK4, of sites facing a held bath, and of the stationary analysis?
   - *Ruled:* refuse all three.
9. **The trace rule** (§4.3): world-building rule or refusal?
   - *Ruled:* when both the trace and K_d are declared, refuse at the definition, and state the
     threshold.
   - *The note's implementation, for the lead to confirm.* The threshold is 10⁻⁶ K_d. The ruling's
     premise does not hold as built, because the trace is not stored in the definition. So §4.3
     proposes (a), a declared `trace_mM` per ligand, checked against every declared concentration.
     The proxy (b), the lowest declared concentration, has both a false-refusal and a
     false-acceptance mode.
10. **The identity list** (§1.6): extend `SPECIES_LAWS` now?
    - *Ruled:* check against D152's identity tests; the shared change is a D148 item after FR-9 and
      outside MG0c's window.
    - Version 1 needs no shared change: the operator checks both other inventory operators itself.
11. **FR-1** (§5.3, §6.4).
    - *Ruled:* write "as FR-1 proposes"; FR-1 is not yet accepted.
12. **The probes** (§8.5): list each one's purpose, and run any that tests an assumption of the note
    before acceptance.
    - *Ruled.* P2 and P3 ran; P1 is milestone 1; P4 is closed by its arithmetic.

**Also ruled:**
- **The regulatory state.** Its relation to occupancy is stated, and occupancy as a coupling source
  is named as a door (§2.6).
- **The kinetochore figures.** Checked against the paper's own text (§2.3). The landed review is left
  as it is; the lead handles it.

**Open for the lead at acceptance.** These are choices this revision introduced, which the review
has not seen:
1. **The booking rule's structure** (§3.3): static components, classed per step, with heat at the
   facing node and **work booked per population**. That includes a reversing binding route's hybrid
   correction at a mixed component.
2. **The trace refusal's form** (§4.3): (a), a declared `trace_mM` checked against the world
   (proposed); or (b), the proxy, with its two failure modes.
3. **The rate bracket** (§4.5). "Realistic receptor rates" are bracketed (every rate up to 10 s⁻¹ at
   dt = 1 ms), not taken from a sourced parameter set, which was sought and not reached.
4. **One unmeasured mixed configuration** (§4.4): a cell that both receives internalised cargo and is
   faced by an inward population binding the same ligand. World 1 of §3.4 covers it, and the
   dissipation check refuses a falling heat in it loudly.

The probe's numbers are development evidence by the note's author. The registered references
supersede them, and the third-order evidence that matters is ε = 0.1's (§8.3).

## 12. Milestone 1 as built (15 November 2026)

The engine agent built milestone 1 after D169, on its branch, as agreed with the lead on 15 November.
It is §8.5's P1 in two stages, each committed with its tests: A, the contract fit, and B, the
half-step with its bookings and guards. The operator was registered only with stage B. The criteria
A1 to A5 and B1 to B6 were fixed before any code in `/mnt/workspaces/Cells/site-occupancy-m1-20261115-01/`
(HANDOFF.md). That folder also holds the snapshots, the test logs and the queue log.

**The operator** (`operators/site_occupancy.py`), registered with one import and one line:
- **The declaration** (§2.1) has three parts, and it round-trips:
  - `species`, the ligands, parsed by `species_common.parse_species`, each with a declared
    `trace_mM`;
  - `populations`, each with its owner (a patch and its face, or a contact and its side), copies,
    sites per copy, accessible fraction, ligand, k_on, k_off, initial occupancy and optional
    site-conserving internalisation;
  - the schedule `site_controls`: a multiplier per population and route, under D152's schedule
    rules.
- **§6.2's refusals fire with their reasons.**
  - The test's table holds 32 cases: the ligands, owners, populations, laws, keys, schedules and
    RK4.
  - The definition check refuses RK4, more than 16 species (FR-10's `check_species_cap`), an
    identity that differs from D150's or D152's operators in either order, a population on a
    replaced slot, and internalisation from a patch facing a declared compartment
    (`cell_owned_compartments@1`).
  - **The trace rule is §4.3's form (a), as proposed** (§11's open item 2, for the lead to
    confirm). Every declared concentration of a ligand must be at or above its declared trace, to
    1e-12 relative. That covers every node and every replacement template's amounts. The trace must
    be at most 1e-6 K_d of every population binding the ligand.
  - The composite's structure check refuses water, the lumens, insertion@1 and @2 and the
    partition, in either order, and the stationary analysis refuses the composite by its own ID
    check.
- **The binding layout** (§2.5) holds:
  - S = α ν N / N_f, with B₀ and R₀ as anchors;
  - the rates and ln(K_d / 1 mM);
  - the facing and receiving indices, and the pools (the distinct facing and receiving slots);
  - the static component map, a union-find: a population joins its facing node, and
    internalisation joins it to its cell.
- **The contract** follows §1.5's table.
  - The operator owns its eight fields. `ACCEPTS_WRITES` covers its two pools,
    `ENTITY_WRITES` @3's two amount fields. Heat is booked at the facing nodes and work per
    population.
  - `CONFLICTS_VIEW` is D150's static-tissue list plus `extracellular_amount_reference`.
  - **It provides no view, mask or capacitance, so it is no field input.** An occupancy-only
    composition has no field inputs and does not refresh the field: ownership is separate from
    solver invalidation (ARCHITECTURE.md's modular core, D174). A5 tests this.
  - Species identity follows the coupling operator's pattern until D172 (§1.6), with no shared
    change.
- **The half-step** (§4.2, §3.3) is D152's SSPRK(3,3) over the site network, unsplit.
  - The stage condition h max L ≤ 1/2 is checked at every stage, over the pools' loads, k_on c at
    R, and k_off + k_int at B. Every stage and the end must be positive.
  - The bookings follow each component's class in the step. A passive-only component books
    H = −ΔG of its facing sub-system at the facing node, and no work.
  - A mixed component books average-vector-field shares with divided-difference potentials and work
    per population. Each binding route takes the per-route hybrid: its share, unless it reverses
    within the step, else the quadrature.
  - The site free energy is the owner's (`site_free_energy`).
- **Idleness** (§4.8): each entry is selected with `where` wherever a route with a positive
  multiplier writes it, never offset by a computed zero. A composition with no populations is
  statically idle.
- **The ledgers** (§2.5):
  - @3's local, outside and total ledgers gain net binding at the facing node, and lose the
    internalised cargo at the receiving cell;
  - the energy ledger gains the site free energy's change + heat − work;
  - the operator's own ledgers are `site_bound_entity` and `site_moiety_entity`.
- **Observations:** the owned fields and the three readouts. `stage_report` diagnoses a refused
  step on the host, as D152's does.
- **The batch signature** (§2.7) holds the ligands and each population's structure: its owner,
  facing, ligand, internalisation and destination. Identities and parameters are per-world data.

**The D172 consolidation item.** The integrator duplicates D152's numerical block: SSPRK(3,3) under
the unidirectional stage condition, with D152's exact bookings and per-route hybrid
(`species_reactions.py`, `half_step_terms`). It was reimplemented over the site network because
D152's files stay untouched while MG0c is judged (the lead, 15 November 2026). **It is a
consolidation item for D172's round: one shared numerical block in the inner model's numerical plan,
serving D152 and FR-3.** A comment at the top of the integrator says so.

**One departure from §2.5: the own ledgers' floor is a constant.** It is 1e-20 fmol, D150's
species-scale floor as its worlds declare it, plus 2.5 ε × steps × magnitude. It is not read from
the ligand's declared floor, because the contract's `own_bounds` receives no layout (the bath
schedule's floors are constants for the same reason). In a world that declares a larger floor for
the ligand, the own check is stricter than §2.5's. In one that declares a smaller floor (the
definition requires only a positive one), it is looser, by less than 1e-20 fmol. A per-ligand floor
needs the hook to see the layout, an item for D172.

**Fixtures:** `validation/tissue/site_occupancy_fixtures.py`.
- `face_free_sites` is D150's face-free topology, with S at 1e-3 mM in the cell and in ecs_0, and a
  trace of 1e-12 mM elsewhere.
- `population` builds one population's declaration.
- `with_site_occupancy` adds the operator's block, with a multiplier of 1 on every declared route by
  default.

**The gates.** They ran from clean snapshots, docs/ included, on CPU 2, one unit at a time: a 2G cap,
`--oom-first` and `--wait-headroom 4G`. The unit at 369120a had its runtime capped so that it ended
before the lead's memory stop at 02:10 UTC (peak 903 MB). Other units shared the machine (five at
that unit's start, MG0c's two judged runs among them), so the times are loaded. The lead measures
tiers on clean CPUs at landing.

| Gate | Result |
| --- | --- |
| A1 to A5, `test_site_occupancy.py` (NumPy, tier 1) | 47 passed at 6f79249 (8 s): the 31 refusals; the five view conflicts in either order; the neighbours admitted in either order; the replaced slots; the compartment; D150's identity in either order; the cap; the round trip; the layout; the component map; identities as metadata; the contract fit; static idleness. Five cases were added after 369120a, to cover A1 fully: D152's identity in either order, a contact population's facing cells and components (5eddcfe), internalisation on a contact, lumen@2's conflict, and the stationary analysis (c7ef446). They run after the memory stop |
| B1 and B6, `_runs.py` | 2 passed at 6f79249 and at 369120a (81 and 96 s). Passive-only and mixed: every host check on every row, the energy ledger included. R + B = S to 1e-18 fmol, and the ligand's system total (free in every node, plus bound) constant to 1e-15 relative |
| B2, `_controls.py` | 3 passed at both. Each corruption fails the runner's host checks: the site free energy dropped from the energy ledger, a material term scaled by 1 + 1e-6, and the heat's sign flipped. The corruptions are test-only, in the host's ledger terms (monkeypatch, xp = NumPy) |
| B3, `_idle.py` | 1 passed at 6f79249 and at 369120a (94 and 112 s). Zero multipliers, and no populations: each is bitwise equal, on every inner field and row, to the world without the operator |
| B4, `_restart.py` and `_vector.py` | 2 passed at 6f79249, in one file (158 s): restart in process and through a snapshot, bitwise; the vector-window batch of three k_on values, within 1e-12 of its scalar runs and bitwise against its reverse. Split at 369120a, where the restart passed again (94 s). The vector file had not run when the unit's runtime limit stopped it, before the lead's memory stop; it reruns after the stop |
| B5, `_stage.py` | It failed at 6f79249 because of the test, which closed over a NumPy layout inside `jit` (TracerArrayConversionError); its runner half had passed. Fixed at 6dff2ff: the pool reads take `xp.asarray`, and the test binds jnp arrays. 1 passed at 369120a (126 s): dt L_R = 2 is refused at run time, the checked step returns its start state bit for bit, and k_on = 2e3 is admitted |
| The matrix, FR-1's and the contract's tests | 6, 121 and 16 passed at 6f79249 |
| D148 | No shared code changed. The registry gains one import and one line; the matrix's tags and block are validation and docs. Crossrev was not rerun: no shared function changed, compiled or host-side, and no existing composition contains the operator |

**The composition matrix** (`validation/tissue/composition_matrix.py`; docs/PUMP_COMPOSITE.md, row
and column 19). The operator's eleven refusals all come from its `CONFLICTS_VIEW`.
- **Ten are real:**
  - water's volumes;
  - the lumens' node volumes, @1 and @2;
  - insertion@1's anchors and masks;
  - insertion@2's closed patches and nodes;
  - the partition's cell mask (door §5.1).
- **One is nominal: the bath schedule's `extracellular_amount_reference`.** The sites read the
  anchors only at finite facing nodes, since a population facing a held bath is refused. The bath
  schedule provides the declared array away from its baths, and schedules held baths only. The slots
  are disjoint, and the code is cited.
- **The compartments' admitted-list rule** now marks the off-list pairs its declarations admit, site
  occupancy among them (§6.4, FR-1's door for it). It stands behind the declarations' refusals of the
  rest.

**Not exercised by milestone 1's worlds:**
- **composition with D150's or D152's operators in a run.** The structure check admits them and the
  identities are checked, but no compiled world holds both;
- **contact populations in a run.** Stage A checks their layout;
- **the hybrid's quadrature branch.** By its parameters, no binding route in B1's mixed world
  reverses within a step: binding starts from empty sites and stays far from equilibrium over its
  20 ms (**S**; the branch taken was not recorded). That world is §11's open item 4's configuration: a cell receives internalised cargo and is faced
  by an inward population binding the same ligand. The dissipation check held on all its rows: no
  heat field fell by more than 1e-12 pJ.

**Not in milestone 1:**
- the references R-ode, R-closed, R-qss, R-dG and R-eq (a separate agent);
- the protocol and its judged run;
- the doors of §9;
- the tier record (the lead measures at landing).

## 13. FR-23: beside a bath dose (20 November 2026; D244)

The design is [OPERATOR_FEATURES_FR23_24_26_DESIGN.md](OPERATOR_FEATURES_FR23_24_26_DESIGN.md)
§2, option A, as D244 decided it. This is development, not judged.

**What changed** (`site_occupancy.py`):
- **Door S's scoped reads.** The operator declares its outside anchors and volumes
  (`extracellular_amount_reference`, `extracellular_volume`) as `fixed` reads at stage `split`,
  scoped to the outside nodes its populations face (`read_slots`, `facing_outside_nodes`).
  - They are finite nodes, since a population facing a held bath is refused at parse.
  - Cells' volumes and the masks stay unscoped, so water, insertion and the closers stay refused.
- **So it composes with the bath schedule in either order.** The dose changes the anchors at held
  baths only. The composition matrix's cells 17↔19 go from `n` to ✓, and the nominal row goes.
- **The trace rule covers scheduled compositions** (`check_schedule_traces`). A dose may not set a
  ligand below its declared trace at a held bath, read from the bath schedule's parsed program, as
  a declared node or a replacement template may not.

**What stays:**
- **Every world, at all three levels.** The declarations are host-side, and the check runs at the
  definition.
- **FR-3's judged scope,** which named site occupancy beside a bath schedule as not claimed.
- **A dose into a finite node is still refused** by the bath schedule ("a finite node cannot be
  clamped"). D244 names it as not covered.

**Evidence:**
- the event-boundary row (`tests/unit/test_site_occupancy.py`): the dose is booked as the held
  content's change, and every site field is unchanged, bit for bit;
- the flipped structure assertion, beside its still-refused twin (`tests/unit/test_door_s.py`);
- the dosed and undosed development run, `/mnt/workspaces/Cells/operators-fr23-20261120/`.

## 14. FR-45: shared site sets (27 November 2026; D327)

The design is the FR-44/45 design note's Part II, widened in place under D148, as the lead's rulings
of 27 November 2026 read it. This is development: FR-45's judged run comes with `validation/fr45/`.

**The declaration:**
- **An optional `site_sets` list.** Each set has an ID, its unit and catalogue, an owner (a patch's
  face, a contact's side or a finite node's own surface), copies, sites per copy and an accessible
  fraction.
- **A member form of a population.** `sites` names the member's set, beside its ligand, rates and
  initial occupancy. Its owner and counts are its set's.
- **Private sites are unchanged.** A population without `sites` is a private set, declared inline
  as before. Leaving `site_sets` out is the only spelling of "no sets", so an empty list is refused.

**The law.** Competitive Langmuir binding on a shared pool of free sites. For a set s with free
sites R_s and members b:
- dB_b/dt = m_b k_on,b c_b R_s − k_off,b B_b, and dR_s/dt = −Σ_b dB_b/dt.
- **R moves on the set axis.** `site_free_increment_fmol` lies on `site_set`, and the capacity
  moiety R_s + Σ_b B_b = S_s is booked per set.
- **The half-step is SSPRK(3,3) as before.** Its stage condition is h·max L ≤ 1/2. The loads are
  each pool's, each set's free-site load summed over its members, and each member's dissociation
  (`stage_loads`).
- **The heat at each facing node** is −(ΔG of the pools + ΔG_B + ΔG_R), with each set's free sites
  counted once (`site_lattice_terms`, `node_booking`).

**The static switch.** Without `site_sets`, the new layout leaves are zero-size and the half-step is
today's, bit for bit. D148's first probe found the programs identical after dead-code elimination,
and every field equal.

**R3's quantity:**
- on a shared set (ruling 1): θ_b = B_b / (R_s + Σ_q B_q);
- on private sets: B / (B + R), as before.

**The step report.** `step_report` gives step 1's loads by kind, ID and sum, with the stage verdict
and the domain verdict apart. When the first half-step's stages refuse, `refusal_condition` names
the stage condition.

**Refused by name** (`site_occupancy.REFUSALS`):
- **Version 1's exclusions:**
  - internalisation anywhere in a set world;
  - W;
  - every operator law outside the design note's §15 partners;
  - @3's own one-way records, a blocked channel population, the sparse field solver and the
    step-doubled energy check. The energy check's block is attached after the definition's
    checks, so a set world that selects it parses, and its binding refuses it before any step.
    The user's open X2 question (D406) may reverse this refusal; if the user selects X2 for
    FR-45, it is revisited with a qualification.
- **The set's own rules:**
  - a set named by fewer than two populations;
  - one ligand twice on a set;
  - initial occupancies over 1 on a set;
  - an unknown or twice-declared set ID;
  - a shared set on a replaced slot;
  - a set that faces a held bath.

**Admitted, each with its check** (ruling 2):
- **Partners:**
  - the wash;
  - @2's θ (a node set's member stays refused as a source);
  - the bath schedule;
  - replacement@1 off a replaced slot;
  - turnover, exchange and D152's reactions;
  - a face at a set's node.
- **Run paths:** `runner.run`, windows, a resume, and the batch and vector paths.

**Evidence:**
- `tests/unit/test_site_occupancy.py`: the FR-45 rows;
- `tests/unit/test_site_competition_runs.py`;
- `tests/unit/test_site_competition_partners_runs.py`;
- `tests/unit/test_species_regulated_availability.py`: θ on a shared set;
- D148's first probe: `/mnt/workspaces/Cells/fr45-build-20261127/probe/`.

## Appendix A. Equations for the independent references

The references are written from these equations, not from engine code. Units are @3's: fmol, pL, mM,
s. RT is the engine's, 1e-3 R T pJ/fmol; the references take it as an input (D152 §11's correction).

**A.1 Notation.**
- Node i (a cell or a finite outside node) has declared volume V_i. The ligand has free amount
  n_i > 0 there, and c = n/V.
- Population k has facing node i(k) and, if outward-facing on a patch with internalisation, receiving
  cell r(k).
- Copies N_k, sites per copy ν_k, accessible fraction α_k ∈ (0, 1], N_f = 602,214,076 per fmol, and
  S_k = α_k ν_k N_k / N_f.
- The pools are R_k ≥ 0 and B_k ≥ 0, with R_k + B_k = S_k.
- Constants k_on,k, k_off,k > 0 and k_int,k ≥ 0, with K_d = k_off/k_on; multipliers m_b, m_i ≥ 0.
- h = dt/2.

**A.2 The ODE.**

    J_k = m_b,k (k_on,k c_i(k) R_k − k_off,k B_k),     I_k = m_i,k k_int,k B_k
    dB_k/dt = J_k − I_k,     dR_k/dt = −J_k + I_k
    dn_i/dt = −Σ_{k: i(k)=i} J_k + Σ_{k: r(k)=i} I_k + (other writers)

**A.3 Free energy and bookings.**
- G_site,k = B_k [ΔG°_k + RT ln(B_k/S_k)] + RT R_k ln(R_k/S_k), with ΔG°_k = RT ln(K_d,k / 1 mM) and
  0 ln 0 = 0.
- G_node,i = RT n_i (ln(n_i/V_i) − 1), on the ligand's rows.
- **The rates of heat and work along the exact path:**
  - dH/dt = Σ_k RT J_k A_k, with A_k = ln(c R_k/(K_d,k B_k)), which is ≥ 0;
  - dW/dt = Σ_k I_k (μ_r(k) + μ_R,k − μ_B,k), with μ_r = RT ln(n_r/V_r), μ_R = RT ln(R/S) and
    μ_B = ΔG° + RT ln(B/S).
- **The ledger:** Δ(Σ G_node) + Δ(Σ G_site) + H − W = 0.
- **The engine's bookings,** for the per-law ΔG test: D152's Appendix A rules. The site pools R and B
  are species with "volume" S and standard potentials 0 and ΔG°. The facing node is D152's node, and
  the class comes from §3.3's components.

**A.4 Closed forms** (one population, m = 1).
- The fixed-c forms are large-V limits. The references check them against R-ode at the world's V,
  and the engine is judged against R-ode (§8.3). The closed node's forms are exact for their worlds.
- **Association at fixed c:** B(t) = B_eq + (B₀ − B_eq) e^{−λt}, with λ = k_on c + k_off and
  B_eq = S c/(K_d + c).
- **Dissociation** into a node held near zero: B(t) = B₀ e^{−k_off t}.
- **Depletion in a closed node, no internalisation.** With N = n + B constant:
  dB/dt = (k_on/V)(B − r₋)(B − r₊).
  - r± = [(N + S + K_d V) ± √((N + S + K_d V)² − 4 N S)]/2, and the equilibrium is r₋ (the quadratic
    binding equation of ligand depletion).
  - With Δ = r₊ − r₋, κ = k_on Δ/V and Q₀ = (B₀ − r₋)/(B₀ − r₊):
    B(t) = (r₋ − r₊ Q₀ e^{−κt})/(1 − Q₀ e^{−κt}).
- **Internalisation at fixed c.** With Λ = k_on c + k_off + k_int and B* = k_on c S/Λ:
  B(t) = B* + (B₀ − B*) e^{−Λt}, and the internalised amount is
  U(t) = k_int [B* t + (B₀ − B*)(1 − e^{−Λt})/Λ].
- **Two populations on one closed node:** no closed form. R-ode and R-eq cover it.

**A.5 The quasi-steady limit and D150's sink** (reference side only).
- With ε = (S/V)/(K_M + c₀) ≪ 1 (Segel & Slemrod 1989; Borghans, de Boer & Segel 1996 for the total
  approximation), the node's amount follows D150's saturable law: b ln(n₀/n) + (n₀ − n) = a t.
- The unit map: a = k_int S = A·V_max, b = K_M V, and K_M = (k_off + k_int)/k_on.
- The error is O(ε) after an initial layer of duration about 1/Λ. A start with B₀ at its quasi-steady
  value suppresses the layer.
- With accessibility, S already carries α, so V_max scales by α and K_M does not.

**A.6 The fast-binding limit with transport** (for the later composition item). With local
equilibrium b = s c/(K_d + c), s = S/V per node and immobile sites, ∂(c + b)/∂t = D ∇²c. That gives
(1 + s K_d/(K_d + c)²) ∂c/∂t = D ∇²c, and for c ≪ K_d an effective diffusivity D/(1 + s/K_d)
(**S**; the linear case of Crank 1975, ch. 14, not re-read here).

**A.7 What is compared:** amounts, pools, occupancies, rates, heat and work at saved rows; the
observed orders in dt and in ε.

## References

Records were checked by Crossref, and by Europe PMC for the PMIDs, with no project details sent. The
kinetochore paper's figures were checked by text search of the review's saved copy. The texts were
not read unless stated. Entries marked D152 were checked there.
- Berg HC, Purcell EM. Physics of chemoreception. *Biophys J* 1977;20(2):193–219.
  doi:10.1016/S0006-3495(77)85544-6
- Borghans JAM, de Boer RJ, Segel LA. Extending the quasi-steady state approximation by changing
  variables. *Bull Math Biol* 1996;58(1):43–63. doi:10.1007/BF02458281
- Crank J. *The Mathematics of Diffusion*, 2nd ed. Oxford: Clarendon Press; 1975. Chapter 14 (D152;
  not re-read).
- Gottlieb S, Shu C-W, Tadmor E. Strong stability-preserving high-order time discretization methods.
  *SIAM Rev* 2001;43(1):89–112. doi:10.1137/S003614450036757X (D152)
- Hirano Y, Takenoshita Y, Kitamura A, Hirota T, Fukagawa T. Quantitative measurements of
  kinetochore protein copy numbers via FCS-calibrated molecular counting. *J Cell Biol*
  2026;226(1):e202603185. doi:10.1083/jcb.202603185. PMC13753873.
  - Read through the repository's review
    ([PAPER_REVIEW_KINETOCHORE_COUNTS.md](PAPER_REVIEW_KINETOCHORE_COUNTS.md)), which read the full
    text.
  - The figures of §2.3 were checked by text search of the copy the review saved
    (`/mnt/workspaces/Cells/paper-review-20261113-02/text/paper.txt`).
- Hulme EC, Trevethick MA. Ligand binding assays at equilibrium: validation and interpretation.
  *Br J Pharmacol* 2010;161(6):1219–1237. doi:10.1111/j.1476-5381.2009.00604.x (context for
  equilibrium binding with depletion; the quadratic is derived in A.4)
- Hundsdorfer W, Verwer JG. *Numerical Solution of Time-Dependent Advection-Diffusion-Reaction
  Equations*. Springer; 2003. Chapter IV (D152).
- Langmuir I. The adsorption of gases on plane surfaces of glass, mica and platinum. *J Am Chem Soc*
  1918;40(9):1361–1403. doi:10.1021/ja02242a004
- Lauffenburger DA, Linderman JJ. *Receptors: Models for Binding, Trafficking, and Signaling*. New
  York: Oxford University Press; 1993. doi:10.1093/oso/9780195064667.001.0001. Chapter 2, "Cell
  Surface Receptor/Ligand Binding Fundamentals" (doi:10.1093/oso/9780195064667.003.0002); chapter 3,
  "Receptor/Ligand Trafficking" (doi:10.1093/oso/9780195064667.003.0003).
- McLachlan RI, Quispel GRW, Robidoux N. Geometric integration using discrete gradients. *Phil Trans
  R Soc Lond A* 1999;357(1754):1021–1045. doi:10.1098/rsta.1999.0363 (D152; the average-vector-field
  share)
- Motulsky HJ, Mahan LC. The kinetics of competitive radioligand binding predicted by the law of
  mass action. *Mol Pharmacol* 1984;25(1):1–9. PMID 6708928; doi:10.1016/s0026-895x(25)15016-5 (the
  competition door)
- Rao R, Esposito M. Nonequilibrium thermodynamics of chemical reaction networks: wisdom from
  stochastic thermodynamics. *Phys Rev X* 2016;6(4):041064. doi:10.1103/PhysRevX.6.041064 (D152)
- Segel LA, Slemrod M. The quasi-steady-state assumption: a case study in perturbation. *SIAM Rev*
  1989;31(3):446–477. doi:10.1137/1031091 (D152)
- Shankaran H, Resat H, Wiley HS. Cell surface receptors for signal transduction and ligand transport:
  a design principles study. *PLoS Comput Biol* 2007;3(6):e101. doi:10.1371/journal.pcbi.0030101,
  PMID 17542642, PMC1885276. Its receptor parameter table is an image and was not read (§4.5).
- Shu C-W, Osher S. Efficient implementation of essentially non-oscillatory shock-capturing schemes.
  *J Comput Phys* 1988;77(2):439–471. doi:10.1016/0021-9991(88)90177-5 (D152)
- Strang G. On the construction and comparison of difference schemes. *SIAM J Numer Anal*
  1968;5(3):506–517. doi:10.1137/0705041 (D152)
- Wiley HS, Cunningham DD. A steady state model for analyzing the cellular binding, internalization
  and degradation of polypeptide ligands. *Cell* 1981;25(2):433–440.
  doi:10.1016/0092-8674(81)90061-1, PMID 6269748 (abstract not available through Europe PMC)

The requester's sources that this note did not find or read: the 2026 glycocalyx and protein-corona
work, and the engineered quorum-sensing consortia of the 13 November reading list (FR-3).
