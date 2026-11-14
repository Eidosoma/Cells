# Site occupancy: binding sites as owned state (design)

**Status: PROPOSED, 14 November 2026, for the lead's review with the advisor.** No engine code was
added or changed, and no probe was run. D159 logged the feature (FR-3), and D167 orders its design
alongside FR-1's and FR-10's. Design comes before code (D142), as a general feature (D144).

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
- one new operator, `site_occupancy@1` (§1, §2), with two laws: `langmuir_site_binding@1` (passive)
  and `site_conserving_internalisation@1` (driven);
- its qualification worlds also run D150's `scheduled_species_exchange@1`, for the engine-to-engine
  cross-check against the plain sink (§8.3, Q7).

No model, solver or compiled shared function changes. One host-only shared change is proposed:
the identity check's list of inventory laws (§6.3).

**Basis.**
- The contract: [PUMP_COMPOSITE.md](PUMP_COMPOSITE.md); the [v2 design](PUMP_COMPOSITE_V2_DESIGN.md)
  §1 (energy roles, free-energy owners, combination rules) and §3 (membrane state, R1–R8).
- The inventory: the [secreted-species design](SECRETED_SPECIES_TRANSPORT_DESIGN.md) (D150) and the
  [shared-inventory reactions design](SHARED_INVENTORY_REACTIONS_DESIGN.md) (D152), whose integrator,
  stage condition and booking rules this note reuses.
- The factor form: the [coupling design](INVENTORY_COUPLING_DESIGN.md) (D155, D156): F ∈ [b, 1], and
  its routing door.
- The primitive's own sources: the [kinetochore counting review](PAPER_REVIEW_KINETOCHORE_COUNTS.md)
  (Hirano et al. 2026), and receptor-kinetics texts (References). The neighbouring requests FR-1,
  FR-2 and FR-6 were read for the links (§5.3), not as design inputs (D144).

**Evidence and log:** `/mnt/workspaces/Cells/site-occupancy-20261114-01/` (HANDOFF.md: what was
read, the code facts with line numbers, the citation checks). **S** marks our own arithmetic or
interpretation, as in the D150, D152 and coupling notes. Every closed form in Appendix A is
derived here (**S**). The references agent derives them again. For the books and papers cited, the
records were verified and the texts were not read. No parameter value is taken from memory. Values
in examples are synthetic and labelled so.

## Departures from the brief, from D150 §2.5 and from FR-3's mapping

Each is a question for the lead (§11).
1. **The owner is not membrane state** (D150 §2.5 requirement 2; the brief's "membrane state's
   populations?"; lead question 1).
   - The population form is kept: a functional unit, a catalogue reference and copies on a
     domain.
   - The state lives on a new operator. Three code facts weigh against membrane state.
     - **Its populations are @3's channel populations by construction.**
     - **It is a field-input provider.** It provides `membrane_capacitance`, so every composition
       with it pays the per-step field refresh and is capped at 64 field nodes.
     - **Three operators refuse it beside them:** exchange@1 (the sink this primitive replaces),
       replacement@1 and water.
   - §1.3 costs both options.
2. **Version 1 has an internalisation step.** FR-3's mapping says "its internalisation step follows
   FR-2"; the brief's day-one guard needs one (lead question 3).
   - The guard's J = k_int R_T c/(K_M + c) holds only when the site count stays constant: the cargo
     goes in and the site stays.
   - So version 1 has that form only: site-conserving internalisation into the patch's cell, with
     the destination a declared target.
   - FR-2's form, in which the site goes inward with its membrane and the surface pool is consumed,
     follows FR-2. FR-1's destination, a compartment instead of the cytosol, follows FR-1 (§2.4).
3. **Accessibility scales the accessible site capacity, not the binding rate** (FR-3's mapping:
   "a declared multiplier on the binding rate"; lead question 2).
   - Under detailed balance, a binding-rate multiplier either scales both directions or only the
     on-rate.
     - Scaling both changes no equilibrium, so it cannot leave sites empty, which is what the
       kinetochore constraint needs.
     - Scaling only the on-rate changes K_d, which is the standard binding free energy, not an
       accessibility.
   - D150 §2.5's own wording, "accessible sites are the stoichiometric sites times an accessibility
     state", is the capacity form. §2.3 tests all three.
   - The both-direction multiplier stays, as a separate kinetic control.
4. **Binding and internalisation are split inside the half-step**, as a palindrome. D152 rejected a
   split of passive and driven routes within a node (lead question 4).
   - Here the network that carries the coupling (shared ligand pools, shared sites, competing
     ligands) stays whole. Only a first-order drain of the bound pool is split off, as D150's
     exchange splits its routes.
   - Every booking is then an exact state-function difference, so D152's per-route hybrid and its
     known limit do not arise.
   - The split's steady bias is derived in closed form and measured (§4.5).
5. **RK4 is refused**, as in D152 and not as in D150 (§4.6).

## 0. Summary

1. **The entity: a site population** (§1.1). It is a population of identical, independent,
   single-occupancy sites on one owner, facing one free pool.
   - **Its owner** is a membrane patch, facing its outside node or its cell, or a contact, facing
     one of its two cells.
   - **Its count** is copies × sites per copy (stoichiometry), and its accessible capacity is that
     count times an accessible fraction α (§2.3).
   - **Its state** is the free accessible sites and the bound amount of each ligand.
   - **It takes no species row.** Sites and complexes are not @3 species, so a receptor type costs
     nothing against the species cap; each ligand is one row, shared with D150 and D152.
2. **One owner** (§1.3). The operator `site_occupancy@1` owns every site population of a composition
   and runs their laws. A law appears once per composition (`pump_composite.py:150`). It declares
   `ACCEPTS_WRITES` on its pools for the later writers: FR-2's retrieval and a partition version.
3. **One material ledger** (§1.4, §3.1). The free ligand stays in @3's rows; the bound amount is the
   owner's state.
   - Binding, release and internalisation are booked transfers between the two, as
     `exchange_moved_fmol` is.
   - The per-species system total, free plus bound, changes only through declared sources and
     sinks.
   - **Bound cargo keeps its identity:** it is booked per species row on a named population, and
     every transfer of it is per species.
4. **The laws** (§2).
   - **Binding** is Langmuir's mass action on finite sites, L + site ⇌ complex, with k_on and k_off
     per (population, ligand). Several ligands may share one population's free sites (competition).
   - **Detailed balance** sets the standard binding free energy, ΔG°_b = RT ln(K_d/1 mM), with
     K_d = k_off/k_on.
   - **Internalisation** is first order in the bound pool, moves the cargo into the patch's cell and
     returns the site free. This is the site-conserving form, version 1's only one.
5. **Accessibility** (§2.3) is the accessible fraction α ∈ (0, 1] of the stoichiometric sites,
   declared per population and domain, constant in version 1.
   - It caps occupancy at α, leaves K_d unchanged, and scales the sink's V_max but not its K_M.
   - **Regulated accessibility** has three routes:
     - its kinetic form (both rates × F ∈ [b, 1]) through the coupling operator's routing door,
       booking nothing;
     - a regulated capacity, which books work and needs its own design;
     - an occluder species competing for the sites, available in version 1 with full accounting.
6. **Energy** (§3.3).
   - **A finding:** @3's chemical term holds no binding free energy, so binding below 1 mM would
     book negative heat. The owner therefore holds the site free energy as a declared free-energy
     term: the standard binding term plus the Langmuir configurational term over accessible sites.
   - Passive binding books heat H = −ΔG ≥ 0 per facing node. Internalisation books signed work
     W = ΔG per receiving cell.
   - Each element is an exact state-function difference of a closed single-class sub-stage.
7. **Numerics** (§4).
   - Each half-step is the palindrome Int(h/2) Bind(h) Int(h/2).
   - Internalisation is exact. Binding uses D152's SSPRK(3,3) under its unidirectional stage
     condition at θ = ½, with internalisation counted in L, so dt · L > 1 is refused at run time.
   - Positivity is a theorem. Zero and full occupancy are in the domain.
   - The split's steady bias has a closed form (Appendix A.6).
8. **Partition and reset** (§5). These are declared rules, refused in version 1 with their doors
   named.
   - At division a population splits with its owner's fraction, extensively. Its occupancy is
     preserved and its free energy changes by exactly zero.
   - At replacement the occupant's sites and bound cargo leave with it, booked per species. The
     newcomer takes its template's declared site state.
9. **Composition** (§6). It composes with @3, injection, D150's turnover and exchange, D152's
   reactions, the coupling operator, membrane state, and replacement@1 off replaced slots.
   - It refuses volume providers, closers, sites facing a held bath, charged or permeant ligands,
     RK4, the stationary analysis, and worlds above `MAX_SPECIES`. That cap is 16 once D165's D148
     change lands; it is 7 in code today.
   - It provides no field input, so the 64-node cap does not apply to it.
10. **Qualification** (§8) is numerical first, against references written from Appendix A by an
    agent that never reads the code.
    - Day one: the saturable-sink limit as a sweep in the Segel–Slemrod parameter ε, with the unit
      map to D150's A·V_max and K_M.
    - Then the equilibrium occupancy, the binding kinetics against closed forms, accessibility as a
      pure factor with negative controls that tell the three forms apart, and the energy guards of
      record.
11. **Effort:** about 6 agent-days (5 to 7) for version 1, plus CPU minutes (§10).

## 1. Entities and ownership

### 1.1 The entity: a site population

A **site population** is a population of identical, independent sites, each holding at most one
ligand: Langmuir's model of localized binding (Langmuir 1918). It is declared once, with:

| Item | Content | Units |
| --- | --- | --- |
| Identity | A functional unit ID and an opaque catalogue reference, null or `{"catalogue": id, "entry": key}`: membrane state's population form (v2 §3) | – |
| Owner | A patch with its face, `outside` (the patch's outside node) or `inside` (the patch's cell); or a contact with its side, `first` or `second` (@3's `junction_sender` or `junction_receiver`) | – |
| Copies N | The population's abundance on that owner: copies of the functional unit | units |
| Sites per copy ν | The stoichiometry: identical sites per copy, an integer ≥ 1 | – |
| Accessible fraction α | The fraction of the stoichiometric sites that can be occupied (§2.3) | – |
| Ligands | One or more neutral inventory species, each with its binding constants and, on an outward-facing patch, an optional internalisation route | – |

**Derived:**
- the stoichiometric count R_T = ν N, in units;
- the accessible capacity S = α R_T / N_f, in fmol, with N_f = 602,214,076 sites per fmol (exact,
  from the SI value of the Avogadro constant).

**State** (anchored increments from the declared values, membrane state's R8):
- **free accessible sites** R ≥ 0 (fmol);
- **the bound amount** B_s ≥ 0 (fmol) of each ligand s.

R + Σ_s B_s = S is the population's moiety identity. It is checked as a guard, as D152's moieties
are, and every update keeps it by construction.

**The free partner.** Every ligand is a free species at the population's **facing node**:
- the outside node of an outward-facing patch, which must be finite;
- the cell of an inward-facing patch;
- the side's cell of a contact.

A contact population therefore binds a species from the cytoplasm of one of its two cells. Binding
between two populations across a contact (docking) is a different law: a door (§9).

**Why counts and not densities.** Version 1 reads no area. The kinetochore review reports copies per
structure, and receptor abundances are counts too. A density would tie the site count to
`membrane_area`, whose providers version 1 refuses. FR-2's retrieval, moving a fraction of a
patch's area, would move the same fraction of its sites (uniform density, **S**), so counts serve it
too.

### 1.2 Why a new entity: not species rows, not the regulatory state, not the plain sink

| Alternative | Why it fails as the site primitive |
| --- | --- |
| **D152 species rows** for the free site R and the complex C, with a passive reaction L + R ⇌ C. D152 §2.2 itself writes an enzyme–substrate complex this way | (1) A row lives in a node's volume, and @3's face law would diffuse it: D150 §2.5 requirement 1. (2) A row at an outside node is shared by every patch facing it, so per-cell receptor pools, which competition for a shared dose needs (FR-2's requester), cannot exist. (3) Each receptor type costs two rows against the cap (FR-9). (4) The count would be a concentration in a volume, not copies on a domain |
| **The coupling operator's regulatory state** (`hill_regulated_two_state@1`) | It has the same form, ds/dt = k_on u (1 − s) − k_off s, but it is kinetic state with no ledger. It cannot deplete or conserve the ligand. The coupling note says so itself: "where binding sequesters a significant share, the binding must be explicit: a D152 passive reaction, or D150 §2.5's occupancy door" (its §1.8) |
| **D150's plain sink** (`saturable` import) | It has no site state, so it has no sequestration, no release, no competition between cells for a finite receptor pool, and nothing for FR-2 to move. It is this primitive's quasi-steady limit, and day one's guard (§8.3, Q1) |

### 1.3 The owner: two options, costed

**Option O (recommended): the operator owns its site populations.** `site_occupancy@1` holds every
population's state and runs its laws. It is the owner and, in version 1, the only writer. Water is
the precedent: it owns the volume and runs its own flow. It declares
`ACCEPTS_WRITES = {site_free_increment_fmol: (site_moiety_entity,), site_bound_increment_fmol:
(site_bound_entity, site_moiety_entity)}` for its later writers: FR-2's retrieval, a partition
version, and a site-turnover law. With no writer the terms are absent, a static branch (v2 §1.4).

**Option M: membrane state owns the sites.** A new law, `membrane_entity_state@2`, would add a
non-conducting population kind holding copies and occupancy. A binding law would write it, as
insertion writes membrane state @1 today.

| | Option O | Option M |
| --- | --- | --- |
| New law IDs | One operator | Membrane state @2, plus a binding writer |
| Population owner on a patch | Channels with membrane state, sites with this operator. Ownership is per field (v2's entity table) | One owner for every population |
| Field input | None, so no 64-node cap and no refresh. Morphogen-scale and sheet worlds of hundreds of nodes stay admissible, as for D150 and D152 | `membrane_capacitance` is a view (`membrane_state.py:194`, `pump_composite_adapter.py:76, 100`, `pump_composite.py:317–318, 709–711`). Every binding world is capped at 64 field nodes, with the measured refresh cost: +13% at the cap, +20% at 254 nodes (v2 §3) |
| With D150's exchange (secretion beside binding; Q7's cross-check) | Composes | Refused: exchange lists `membrane_area` in `CONFLICTS_VIEW` (`species_exchange.py:461`). D150 v1.1's `VIEW_READS` would lift it |
| With replacement@1 and water | Composes off replaced slots; water is refused for the volumes, as by D150 and D152 | Refused: both list `membrane_area` (`cell_replacement.py:625`, `osmotic_water.py:492`), and replacement@1 provides `channel_abundance` too (614–620), so one provider per field already excludes it |
| What its parser admits | Any declared population | @1's admits exactly @3's channel populations (`membrane_state.py:105–108`). @2 needs a new population kind and a bitwise guard against @1 when none is declared |
| FR-2 and the partition | Write both owners through `ACCEPTS_WRITES`. Insertion's inserted densities would need a site entry later | One population map serves them. The partition `REQUIRES` membrane state @1 (`partition.py:935`), so it changes in either option |
| Cost (**S**) | Included in §10 | About +1.5 agent-days: membrane state @2, its guards and the writer split |

**The recommendation is option O.** The deciding facts are the field-input cap and the three
refusals. A binding world with secretion, renewal or more than 64 nodes would otherwise wait for
membrane state's own redesign.
- **What is kept from requirement 2:** site abundance is a population's abundance with its
  catalogue reference. The declaration form is membrane state's.
- **The owner and law split is the door.** The coupling note's ruling 2 took one operator in
  version 1 and left the split into a state owner and a provider to the first outside reader. Here
  the owner and law separate when a second law writes the pools. That law is FR-2's retrieval, or
  surface catalysis (§9).
- **One contract change would come with that split.** A state owner without `VIEW_FIELDS` is
  inadmissible as built (`contract.py:335–341`).

### 1.4 One material ledger, and the identity of bound cargo

- **Free:** the ligand's amounts stay in @3's rows (`amount_increment`,
  `extracellular_amount_increment`), which @3 owns. This operator writes them through
  `ENTITY_WRITES`, booked in its own accumulators, never in @3's route accumulators (D150 §1.1's
  writers' rules).
- **Bound:** B_s is this operator's state on a named population. It is never a species row, never
  on @3's species axis, and never diffused.
- **Transfers:** binding and release move the ligand between the facing node's row and B_s;
  internalisation moves it from B_s to the receiving cell's row. Each move is booked once, in one
  accumulator, which enters @3's ledger with one sign and the owner's with the other (§3.1).
- **Identity** (FR-3's links; §5.3). A bound pool is identified by its species and its population.
  - Bound cargo stays its species: binding converts nothing, and a bound pool is booked per
    species row.
  - Moved by FR-2, it stays bound to its population on the moved membrane. Released (FR-1), it
    enters the same species' row at the release node.
  - A conversion of bound cargo into another species is a declared driven route with D152's moiety
    rules (surface catalysis, a door; §9), never a side effect.

### 1.5 The ownership table and the contract's parts

| Field | Owner | Writers (booked in) |
| --- | --- | --- |
| A ligand's free amounts (`amount_increment`, `extracellular_amount_increment` rows) | @3 | @3's step (none for an impermeant ligand, except faces at outside nodes); D150's operators; D152's operator; replacement events; **this operator** (`site_bound_net_fmol`, `site_internalised_fmol`) |
| Free accessible sites (`site_free_increment_fmol` [site population]) | This operator | Itself; later writers through `ACCEPTS_WRITES` |
| Bound amounts (`site_bound_increment_fmol` [site route]) | This operator | Itself; later writers through `ACCEPTS_WRITES` |
| Accumulators, heat, work, magnitudes | This operator | Itself only |
| Populations' and ligands' identities | Declarations, never arrays (§1.6) | – |

A **site route** is one (population, ligand) pair: one binding route and, where declared, one
internalisation route.

**The contract's parts, as used:**
- `ENTITY_WRITES` on the two amount fields, each with the owned accumulators that close @3's
  ledgers.
- `STATE_AXES` for the pools, accumulators and energy fields (§2.5).
- **Energy roles** (v2 §1.1):
  - `HEAT_FIELDS`: `site_dissipated_energy_pJ` [cell] and `site_outside_dissipated_energy_pJ`
    [outside];
  - `WORK_FIELDS`: `site_internalisation_work_pJ` [cell];
  - the site free energy is a declared free-energy term (§3.3), not a flow.
- **`CONFLICTS_VIEW`**: `volume`, `extracellular_volume`, `active`, `outside_active`,
  `membrane_active` (D150's static-tissue list) and `extracellular_amount_reference` (D152's
  addition, since insertion@1 provides it).
  - The reason is the contract as built: a half-step receives the declared layout, and the view
    only for a `BOOKS_AT_VIEW` operator in a field-input composition (`pump_composite.py:585–590`).
  - So version 1 is a static tissue, as D150's and D152's are.
- **One split part**, the palindromic half-step (§4.2), with RK4 refused (§4.6). It is statically
  idle with no routes.
- **`ACCEPTS_WRITES`** as in §1.3.
- None of `VIEW_FIELDS`, `CONTROL_FACTORS`, `REPLACES`, `EVENT_REPLACES`, `CLOSES` or `REQUIRES`.
  It provides no view, so it is no field input (§3.2).
- `ROUTABLE_CONTROLS`: none in version 1. The binding and internalisation multipliers are the
  natural rate targets when the coupling operator's routing door is built (§2.3, §9).

### 1.6 Identity

- **Ligands** carry D150's identity form, parsed by `species_common.parse_species`: neutral,
  impermeant, an optional catalogue reference with its kind of evidence.
- **Populations** carry membrane state's form: a functional unit and a catalogue reference, parsed
  by `membrane_state.parse_catalogue`.
- **Both reach the summary and the manifest, never the arrays.** S2's guard applies: changing a
  reference leaves bindings, jaxprs, the batch signature and trajectories bitwise unchanged.
- **Conflicts.** A ligand whose identity differs from another inventory operator's declaration of
  it is refused. The shared check needs one list extended (§6.3).
- **Generic laws stay generic** (the catalogue rule). No law names a receptor, a kinetochore protein
  or a ligand. "Receptor" is a role a driver's declaration gives a population.

## 2. The laws

Units are @3's: fmol, pL, mM = fmol/pL, s. c = n/V is at the facing node's declared volume
(version 1). h is the operator's half-step, dt/2.

### 2.1 Declaration

```json
{"law": "site_occupancy@1",
 "species": [{"id": "L", "catalogue": null, "evidence": null},
             {"id": "X", "catalogue": null, "evidence": null}],
 "populations": [
   {"id": "r_c0", "functional_unit": "site_unit_a", "catalogue": null,
    "owner": {"patch": "c0_contact", "face": "outside"},
    "copies": 1.0e5, "sites_per_copy": 1, "accessible_fraction": 0.5,
    "ligands": [
      {"species": "L", "association_rate_per_mM_per_s": 1.0e3, "dissociation_rate_per_s": 1.0,
       "initial_occupancy": 0.0,
       "internalisation": {"rate_per_s": 0.1, "destination": "cell"}},
      {"species": "X", "association_rate_per_mM_per_s": 1.0e2, "dissociation_rate_per_s": 0.01,
       "initial_occupancy": 0.0, "internalisation": null}]},
   {"id": "k_c1", "functional_unit": "site_unit_b", "catalogue": null,
    "owner": {"contact": "j01", "side": "first"},
    "copies": 4.0e3, "sites_per_copy": 2, "accessible_fraction": 1.0,
    "ligands": [{"species": "L", "association_rate_per_mM_per_s": 5.0e2,
                 "dissociation_rate_per_s": 0.5, "initial_occupancy": 0.1,
                 "internalisation": null}]}]}
```

The values are illustrative and synthetic.
- **Every key is explicit** (D152's ruling Q5). `internalisation` is null or an object.
- **`destination`** admits one value in version 1, `"cell"`: the patch's own cell. The key exists
  so that FR-1 and FR-2 add destinations without changing the form (§2.4).
- **The experiment** adds `site_controls`: per site route and kind (`binding`, `internalisation`), a
  piecewise-constant multiplier m ≥ 0 from time 0, changing at exact multiples of dt.
  - A zero multiplier switches the route off (D136): a blocking antibody, a washout, an inhibitor
    of uptake.
  - A binding multiplier scales k_on and k_off together, so the equilibrium is unchanged, as D152's
    multiplier on a passive reaction does.
  - Parameters themselves are not scheduled. A scheduled k_off alone would change ΔG°_b, a free
    energy, with no declared work.

### 2.2 Binding: Langmuir's mass action on finite sites, with competition

For population k at facing node i, and each of its ligands s (**S**, the standard form):

    J_ks = m_b,ks [k_on,ks c_s,i R_k − k_off,ks B_ks]          (fmol/s; c in mM, R and B in fmol)
    dB_ks/dt = J_ks,   dR_k/dt = −Σ_s J_ks,   dn_s,i/dt = −Σ_{k facing i} J_ks.

| Item | Content | Source |
| --- | --- | --- |
| Law | Independent, identical, single-occupancy sites; the free sites R are shared by every ligand of the population (competition) | Langmuir 1918; Lauffenburger & Linderman 1993, ch. 2; competitive kinetics: Motulsky & Mahan 1984 (records verified, texts not read) |
| Parameters | k_on in mM⁻¹ s⁻¹, k_off in s⁻¹, both > 0, per (population, ligand); K_d = k_off/k_on in mM | Per world, with sources: a cited measurement with its method, or a declared synthetic value labelled so (D152 §2.4's rule). The engine holds no default |
| Equilibrium at fixed free concentrations | B_ks = S_k (c_s/K_d,ks) / (1 + Σ_j c_j/K_d,kj), the competitive Langmuir isotherm | **S**, Appendix A.4 |
| Detailed balance | ΔG°_b,ks = RT ln(K_d,ks / 1 mM), per mole of complex, against @3's 1 mM reference | **S** (§3.3) |

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
- **Cooperativity between sites of one copy** is not in version 1. The sites are independent.
  Cooperative or multivalent binding is a door; Hill factors elsewhere are no substitute, because
  they hold no material.
- **The written form is linear,** J⁺ = k_on c R and J⁻ = k_off B, not D152's log-space kernel
  `reversible_flux`.
  - It is finite at zero occupancy (B = 0) and at full occupancy (R = 0), which are in the domain
    (§4.3).
  - Near equilibrium the net flux is a difference of nearly equal terms. That costs rounding in
    the trajectory, not in the energy, which is booked as a state-function difference (§3.3).

### 2.3 Accessibility: what it multiplies

**The constraint it must meet.** The kinetochore review records a modelling constraint from Hirano
et al. (2026):
- in the wild type, binding sites stay unoccupied although the free pool is "an order of magnitude"
  larger than the bound pool;
- in either single mutant, "the remaining sites fill completely";
- "a simple mass-action occupancy law over a finite site population would predict saturation in
  all three states and would be falsified here".

The review also states what is not measured. The occupancy split between the two platforms is
inferred from genotype differences plus assumed stoichiometry, and the paper says the wild-type
split is beyond its method. **S**, from the review's numbers: 18.6 and 68.6 nM free in 636–2,208 µm³
cells is about 7,000–25,000 free Dsn1 and 26,000–91,000 free Nuf2 per cell. Against about 3,520 and
5,280 bound, that is 2–7 and 5–17 times the bound pools.

**Three candidates, against four checks** (**S**):

| Form | Detailed balance with the declared ΔG°_b | Sites empty at equilibrium at saturating c | Carried by the coupling factor path | A change under bound cargo |
| --- | --- | --- | --- | --- |
| **(C) Capacity:** S = α R_T / N_f; binding on accessible free sites only | Kept: K_d unchanged, Langmuir over the accessible sites | **Yes:** θ_max = α | Not as built. A capacity factor changes the site free energy (the configurational term over S), and the coupling path carries only rate factors that book nothing | Changes the free energy, so it books work. A fall below the occupancy has no consistent rule without a third pool (below) |
| **(K) Kinetic:** both directions × F | Kept: D152's passive-multiplier rule | **No:** the equilibrium is unchanged, and only the approach slows | **Yes,** once the routing door exists: a rate route on the binding multiplier, booking nothing (coupling note §2.1) | Nothing to book |
| **(A) Affinity:** k_on × F only | **Broken:** K_d → K_d/F, so ΔG°_b moves by −RT ln F | Only below saturation: at F c ≫ K_d every site fills | As a rate factor it would book nothing while changing ΔG°_b: inconsistent | Every change of F is unbooked work: refused |

**Decision: accessibility is (C)**, declared per population and domain, constant in version 1.
- **"Separate from stoichiometry" is literal.** The declaration has three numbers: copies N
  (abundance), sites per copy ν (stoichiometry) and accessible fraction α (accessibility).
- **Its signatures** (**S**):
  - equilibrium occupancy scales by α at every free concentration;
  - occupancy saturates at α;
  - the relaxation rate k_on c + k_off is unchanged;
  - the sink's V_max scales by α and its K_M does not.

  §8.3, Q4 judges them, with negative controls for (K) and (A).
- **FR-3's mapping, read against it.** "A declared multiplier on the binding rate" equals (C) only at
  zero occupancy, where k_on c (αR_T − B) = α k_on c R_T. At finite occupancy the two part, and the
  rate forms are (K) or (A).
- **(K) stays, as a kinetic control,** not called accessibility: the scheduled binding multiplier of
  §2.1.
- **(A) is not an accessibility.** A per-domain difference of affinity is a different declared K_d.
  A regulated affinity is a change of the bound state's standard free energy, which needs a
  declared work source.

**Regulated accessibility, through the coupling operator's factor form F ∈ [b, 1].**
1. **The kinetic form first.** A rate route from the coupling operator (D156's routing door, not
   built) multiplies the binding multiplier m_b by F. It books nothing and keeps detailed balance.
   The site operator then declares `ROUTABLE_CONTROLS = {site_binding_multiplier: "rate",
   site_internalisation_multiplier: "rate"}`.
2. **A regulated capacity** (C with α(t) = α₀ F(t)) needs its own design, for two reasons (**S**).
   - **A change of S books work.** At fixed bound amounts, the configurational term RT[Σ B ln(B/S) +
     R ln(R/S)] changes with S. The agent that occludes or exposes free sites does work on the
     site pool.
   - **A fall below the occupancy** (S < Σ B) has no consistent two-pool rule. The excess cargo
     must either be forced off, as a booked driven release, or be held on occupied, inaccessible
     sites, a third pool that releases at k_off and cannot rebind.
3. **An occluder species, available in version 1 with full accounting** (**S**). An occluding
   molecule that competes for the sites is a second ligand of the population.
   - Its level can be produced, cleared, reacted or regulated by D150's and D152's operators, and
     every booking is the law's own.
   - When the occluder exchanges slowly beside the ligand, its occupancy θ_O is quasi-frozen on the
     ligand's time scale. The ligand then sees the capacity (1 − θ_O) S, which is form (C) with
     α = 1 − θ_O. At true equilibrium, a ligand at saturating concentration displaces any
     reversible occluder, which is the thermodynamic content of the table above.
   - It costs one species row. It is the thermodynamically explicit route to a regulated
     accessibility, and the likely reading of regulation by modification, where a modified and an
     unmodified ligand bind with different K_d (two rows, two routes).

### 2.4 Internalisation: the site-conserving form, and the door to FR-2 and FR-1

**The law, `site_conserving_internalisation@1`.** On an outward-facing patch population, a ligand
may declare a first-order route (**S**, the standard form):

    I_ks = m_i,ks k_int,ks B_ks:   B_ks → (ligand s into the patch's cell) + (one free site on k).

| Item | Content |
| --- | --- |
| Rate | k_int ≥ 0 (s⁻¹), per (population, ligand); zero admitted (idle) |
| The cargo | Lands in the destination's row of the same species. In version 1 that is the patch's own cell, the row D150's import routes write ("the shape the internalisation step writes into", D150 §2.5 requirement 1) |
| The site | Returns at once, free, to the same population: R gains exactly the internalised amount. The site count is constant |
| Role | Driven: endocytic machinery moves cargo regardless of the cytosol's concentration. It books signed work (§3.3), as D150's uptake does |
| Sources | Receptor-trafficking models with binding, internalisation, recycling and synthesis (Lauffenburger & Linderman 1993, ch. 3; Wiley & Cunningham 1981; records verified, texts not read). The site-conserving form is their limit of instant recycling with no net loss of surface sites (**S**) |

**Why version 1 has it, and why only this form** (departure 2).
- **The guard needs it.** D150's sink is the quasi-steady limit of exactly this system:
  dB/dt = k_on c (S − B) − (k_off + k_int) B = 0 gives B = S c/(K_M + c) and an uptake
  k_int S c/(K_M + c). That limit needs the site count constant.
- **FR-2's form is a different law.** Its requester wants the surface pool consumed and returned:
  "a sink that never consumes its receptors cannot produce saturation, competition ... or the
  cell-to-cell variation that makes delivery selective". In it, the site travels inward with its
  membrane and returns later. Building that needs FR-2's retrieval, with its energy source, and
  FR-1's compartment. So it follows FR-2, as FR-3's mapping says.
- **Version 1's form is not FR-2's,** and it does not pre-empt it. FR-2's law will be another route
  kind with another destination, written through `ACCEPTS_WRITES` (§5.3).

**What version 1 loses, stated.** Cargo internalised in version 1 lands in the cytosolic row. FR-1's
request exists because that row cannot tell "particle inside a vesicle" from "cargo in the cytosol".
So version 1's internalisation is the D150 limit's companion, not the study's delivery path. The
delivery path is FR-3 with FR-2 and FR-1 (§5.3).

**Refusals:** internalisation on an inward-facing patch or a contact (there is no "inward" for it), a
destination other than `"cell"`, a negative rate, and a route whose ligand the population does not
bind.

### 2.5 State, ledger terms, observations

**State** (per world; the pools start at their declared values, the rest at zero):

| Field | Axes | Role |
| --- | --- | --- |
| `site_free_increment_fmol` | [site population] | Entity: free accessible sites R, from R₀ = S − Σ B₀ |
| `site_bound_increment_fmol` | [site route] | Entity: bound amount B, from B₀ = θ₀ S |
| `site_bound_net_fmol` | [site route] | Material accumulator: net binding, signed (bound positive) |
| `site_internalised_fmol` | [site route] | Material accumulator, ≥ 0 and non-decreasing |
| `site_dissipated_energy_pJ` | [cell] | Heat of binding at sites facing that cell (inward-facing patches, contacts) |
| `site_outside_dissipated_energy_pJ` | [outside] | Heat of binding at sites facing that node (outward-facing patches) |
| `site_internalisation_work_pJ` | [cell] | Work of internalisation into that cell, signed |
| `site_energy_magnitude_pJ`, `site_outside_energy_magnitude_pJ` | [cell], [outside] | Rounding magnitudes (D150's split by node kind) |

**Layout (bound per world, R1):** owner and facing-node indices, receiving cells, S, B₀ and R₀ as
anchors, k_on, k_off, k_int, and ΔG°_b/RT = ln(k_off/(k_on · 1 mM)), computed on the host.

**Own ledgers:**
- `site_bound_entity` [site route]: the bound increment equals net binding − internalised, plus
  the external terms later.
- `site_moiety_entity` [site population]: the free increment + Σ bound increments = 0, plus the
  external terms later.

Each has a floor at the ligands' species-scale material floors (D150 §1.3).

**@3's ledgers** (D150's sign convention, removed − supplied):
- the facing node's local or outside ledger gains `site_bound_net_fmol`;
- the receiving cell's local ledger gains −`site_internalised_fmol`;
- the total gains both.
- The energy ledger gains the site free energy's change + heat − work (§3.3).
- The magnitudes gain the moved amounts and the |ΔG| terms.

**Observations:** the state columns, and three readouts at each row's state and held controls:
- `site_occupancy` [site route], B/S;
- `site_binding_rate_fmol_per_s` [site route], the net J;
- `site_internalisation_rate_fmol_per_s` [site route].

### 2.6 Per-world data and the batch signature

- **Bindings, never constants.** Copies, sites per copy, α, k_on, k_off, k_int and θ₀ are layout
  arrays bound per world; the multipliers are controls. None is a closed-over constant, and the
  crossrev records show it (D148).
- **The static structure enters the batch signature:** the law; the ligand list; each
  population's id, owner kind, owner id and face or side; its ligands; which routes have
  internalisation, and their destination kind.
- Identities are not part of the signature, as in membrane state's.

## 3. Accounting

### 3.1 Material

- **Extent-consistent updates.** Each sub-stage computes its extents once (Δξ for binding, the
  internalised amount for internalisation). It adds them to the pools, to @3's rows and to the
  accumulators. So Δn, ΔB and ΔR are consistent by construction.
- **@3's ledgers close to rounding** at the ligand's own scale: D150's species-scale floor plus
  2.5 ε × steps × the row's magnitudes.
- **The owner's ledgers** close the same way, at the same floors.
- **The system total per species** is Σ free (cells, finite nodes) + Σ bound (populations). It
  changes only through declared sources and sinks: turnover, baths, replacement's removal and
  supply. It is a guard (a test), not a third run-time ledger, since @3's total ledger and the
  owner's bound ledger already imply it.
- **The moiety identity per population**, R + Σ B = S, holds by construction and is a guard.

### 3.2 Charge

- **Neutral ligands only in version 1** (`parse_species`'s rule). Sites carry no charge in the model.
  Every charge, drift and conductance term the operator touches is an exact zero (D150 §3).
- **No field input.** The operator provides no capacitance, area or mask, so it causes no field
  refresh and the 64-node cap does not apply to it. With membrane state in the same composition,
  the cap is membrane state's.
- **The charged door** (**S**). A charged ligand bound to a site stays on its face's side of the
  membrane. Its charge would be counted in the facing node's charge, so binding would move no
  charge across the membrane, while internalisation would carry it into the cell like a current.
  - D150 §3's exactness argument must be re-made for it.
  - It meets FR-4's buffering, by membrane sites as well as by reactions, and D152's charged door.

### 3.3 Energy: the site free energy, heat for binding, work for internalisation

**The site free energy** (**S**). For population k, with S_k = R_k + Σ_s B_ks:

    G_site,k = Σ_s B_ks [ΔG°_b,ks + RT ln(B_ks/S_k)] + RT R_k ln(R_k/S_k),   ΔG°_b = RT ln(K_d/1 mM),

with 0 ln 0 = 0. This is the Langmuir lattice free energy of the occupied and empty accessible
sites. Its reference is the empty population, G = 0. The free site carries no standard potential;
only the difference ΔG°_b between complex and free site matters.
- **Equilibrium follows** (**S**). Setting μ_bound = μ_free gives ΔG°_b + RT ln(B/R) = RT ln(c/1 mM),
  that is B/R = c/K_d: Langmuir's isotherm, and the competitive one with several ligands.
- **The relation to the ideal form** (**S**). With S fixed, G_site and the ideal-dilute form
  RT Σ x (ln(x/S) − 1) over the pools x ∈ {R, B_s}, each with the standard term, differ by the
  constant RT S. So D152's machinery applies, with the capacity S in place of a volume.

**A finding: @3's chemical term holds no binding free energy, so the owner must hold it.** This is
D152's B7 finding carried over (**S**).
- @3 books RT Σ n (ln(n/V) − 1) on free rows only.
- Binding δ fmol from a node at c removes δ μ_L, with μ_L = RT ln(c/1 mM). At c = 10⁻³ mM that is
  ΔG_chem = +6.9 RT δ.
- Booked alone, the passive heat −ΔG_chem = −6.9 RT δ is negative. The dissipation check would
  refuse every binding step from below 1 mM, which covers every protein-scale ligand. Above 1 mM
  the heat would be positive but wrong.
- With the site term, the change per mole bound is RT ln(K_d B/(c R)). That is negative while
  binding runs forward (c R/K_d > B) and zero at equilibrium.

**So the answer to the brief's question is yes: a site's state needs its own standard term.** The
owner declares G_site as its endpoint free energy relative to the declared reference (v2 §1.1's
free-energy owners). The energy ledger adds G_site(state) − G_site(declared), evaluated in the
anchored increment form below. D152's operator owns its standard term in the same way.

**The bookings.** Each sub-stage is single-class (§4.2), and each element is an exact
state-function difference of a closed sub-system (**S**).

| Sub-stage | Closed sub-system per element | Booked | Sign |
| --- | --- | --- | --- |
| Binding (passive) | One facing node: its ligands' free rows and every population facing it. Populations facing different nodes share nothing in this sub-stage | Heat at that node: H = −(ΔG_chem + Σ ΔG_site) | ≥ 0; the composite's dissipation check refuses a fall |
| Internalisation (driven) | One receiving cell: its ligands' free rows and every outward-facing population on its patches. A population belongs to one patch, and a patch to one cell | Work at that cell: W = ΔG_chem + Σ ΔG_site | Signed |

- **The ledger closes exactly in exact arithmetic:**
  Δ(@3's chemical term on the touched rows) + Δ(G_site) + H − W = 0 per half-step. No route-level
  attribution is needed, so D152's per-route hybrid and its reversal-onset limit do not arise.
- **The increments are stable** (**S**). For each pool x with anchor a and change δ, and S fixed
  within the sub-stage:

      Δg = μ° δ + RT [δ ln(a/S) + (a + δ) log1p(δ/a)]   (a > 0),     Δg = μ° δ + RT δ ln(δ/S)   (a = 0),

  selected by `where`, with every unselected branch finite (D152's ruling Q11 (a), benign padding).
  @3's rows use the adapter's `species_chemical_free_energy_pJ` and `species_chemical_magnitude_pJ`
  (D150 §2.4, as built), whose anchor is the current amount.
- **What W is.** The endocytic machinery's free-energy change of the modelled inventory. Its own
  dissipation and fuel lie outside the model, a declared limit as in D150 §2.4. Drawing it from
  finite energy pools is the energy-pool door shared with FR-2 and FR-4 (D150 question 11, D152
  question 10).
- **What exactness does not test.** A wrong rate is booked exactly too. The kinetics are checked
  against the references (§8).

### 3.4 The energy guards of record

D150's lesson holds: under IMEX, the shared bound (2e-8 pJ + 2e-3 × the flows) is the ions' in a
mixed world. The guards check the residual itself.
1. **The face-free species-only world**, the guard of record.
   - The world: quiescent ions; a passive cell and a finite node joined only by a patch, with no
     face. That is the topology of D150's `face_free` fixture
     (`validation/tissue/secreted_species_fixtures.py:220`).
   - The operator is the only energy flow, so the residual must be at rounding at every row:
     2.5 ε × steps × the energy magnitudes, as in D152 §3.4.
   - Each booking path is forced by a world built to take it: binding only; internalisation only;
     both; two populations sharing the node; two competing ligands; a switch-on of binding from
     B = 0 and from a free trace; release into a node held near the trace; and a closed relaxation,
     whose total heat must equal G(start) − G(equilibrium).
2. **A NumPy ΔG test per law**, written from Appendix A by the references agent. On random states it
   checks:
   - the booked H and W against the independently computed ΔG with the site term;
   - H = −ΔG on binding sub-stages and W = ΔG on internalisation;
   - the moiety and material identities;
   - zero multipliers selecting the start state bitwise.
3. **Negative controls**, as edits of saved histories, in D152's form:
   - work scaled by 1 + 10⁻⁶;
   - the site free energy dropped, which must also fail the dissipation check (§3.3's finding);
   - a heat of the wrong sign.

   Each must fail world 1 at the first row it touches.
4. **The mixed-world statement.** A measured bound/booking ratio in a mixed heredity world goes into
   the docstring, as D150's probe 2 part C and D152's C2 did.

**Scale** (**S**, synthetic). 10⁵ sites is 1.66e-4 fmol. Its free energies are of order
S RT |ln| ≈ 4e-3 pJ, 2 × 10⁵ times ENERGY_ATOL_PJ. A kinetochore-scale aggregate of about 3,500 sites
is 5.8e-6 fmol, about 1e-4 pJ. Both lie above the absolute floor. The guard worlds still use
µM-scale pools in pL nodes, D150 §7's rule.

## 4. Numerics

### 4.1 Scales (**S**)

| Quantity | Value | Note |
| --- | --- | --- |
| Sites per fmol | N_f = 602,214,076 | Exact |
| 10⁵ sites (synthetic) | 1.66e-4 fmol; facing a 1 pL node, 1.66e-4 mM of sites | Can exceed a nM ligand's whole content of that node (1e-6 fmol): the depletion regime, where explicit binding differs from a sink |
| Kinetochore aggregate (the review: about 3,520 Dsn1 bound across about 160 kinetochores) | 5.8e-6 fmol per cell | Per kinetochore, 14–36 copies: below D150 §1.3's mean-field limit of about 10² molecules. A continuum occupancy describes a cell's aggregate sites, not one structure |
| Stage rates | L_n = Σ m_b k_on R/V, L_R = Σ_s m_b k_on c_s, L_B = m_b k_off + m_i k_int | A small node facing many sites makes L_n large: refused at dt·L > 1 (§4.2), the stiff door |
| Who sets dt | The ions in mixed worlds; the faces in species-only worlds (D150 §4.2, D152 §4.1). The operator refuses, never sets, a step | – |

### 4.2 The half-step

**The palindrome**, each half-step of length h = dt/2 (**S**):

    P(h) = Int(h/2) ∘ Bind(h) ∘ Int(h/2).

The composite places P around @3's step (Strang), so the operator is second order in dt against
transport.

**Int(τ), exact.** For each internalisation route, B' = B e^{−m_i k_int τ}, computed with `expm1`.
The internalised amount (B − B') goes to the receiving cell's row, and its sites go to R. Nothing
else acts in this sub-stage, so the closed form is exact.

**Bind(h): D152's SSPRK(3,3)** (Shu & Osher 1988; Gottlieb, Shu & Tadmor 2001), in its Butcher
form (D152 §4.2). One sub-step, over the whole binding network: every facing node's ligand rows,
every population's R and B.

    Y1 = y,  Y2 = y + h f(Y1),  Y3 = y + h (f(Y1) + f(Y2))/4,
    Δξ = h (J(Y1) + J(Y2) + 4 J(Y3))/6 per binding route,   y' = y + ν Δξ.

- It is extent-consistent, so the moiety and material identities hold by construction.
- **The network is integrated whole.** Competition through a shared ligand pool (several cells
  facing one node) and through shared sites (several ligands on one population) is never split.

**The stage condition, with internalisation counted.** At every stage, h max L ≤ θ = ½, with D152's
unidirectional rates per amount:
- L_n,s,i = Σ_{k facing i} m_b k_on,ks R_k / V_i (consumption of the free ligand);
- L_R,k = Σ_s m_b k_on,ks c_s (of free sites);
- L_B,ks = m_b k_off,ks + m_i k_int,ks (of the bound pool, by release and internalisation).

So dt · L > 1 is refused at run time: D152's rule, and the coupling note's ruling 5 (no unenforced
limit).
- The rates are written as rate constants times the partner's amount, never as J/Y, so they are
  finite at zero amounts.
- The internalisation term is not needed for positivity, since Int is exact. It bounds the split's
  bias (§4.5): h k_int ≤ ½ at every admitted step (**S**).

**Refused, never repaired.** A stage that fails the condition, or any non-finite or negative amount,
invalidates the half-step, as D152's do. The composite returns the start state. A host-side
diagnosis gives the largest h L and the step that would admit it, since the runner's message is
generic; D152's `stage_report` is the precedent.

**No sub-steps and no implicit binding in version 1.** The stiff door (§9) is sub-steps with a
splitting that holds its order, or a positive implicit half-step. The single-ligand binding has an
exact Riccati solution (Appendix A.4), a candidate for that door; competition has none.

### 4.3 Positivity and the domain

- **Positivity is a theorem** (**S**, D152 §4.2's SSP argument). Write f = P − C. Each consumption
  is L_x x, with L the rate constants above, so each Euler stage gives Y + h f(Y) ≥ Y (1 − h L) ≥ Y/2.
  The free rows stay positive, as @3 requires, and R and B stay non-negative.
- **Zero and full occupancy are in the domain.** B = 0 (nothing bound) and R = 0 (all accessible
  sites bound) are finite states of the law and of G_site (0 ln 0 = 0). They need no trace,
  unlike @3's free rows.
- **The anchored stall** (D150 §1.3, amended). A pool anchored at a positive value and drained
  follows its closed form until about ε × its anchor, then stalls, positive and unrefused. A pool
  anchored at zero carries its whole value in the increment.
- **The trace rule for ligands** (**S**, a world-building rule, not a refusal). D150's "absent"
  ligand is a trace c_bg > 0, and high-affinity sites bind it: at equilibrium θ_bg = c_bg/(K_d +
  c_bg).
  - A trace of 10⁻⁹ mM against K_d = 10⁻⁶ mM occupies 10⁻³ of the sites; 10⁻⁶ mM would occupy
    half.
  - So guard and production worlds choose c_bg ≪ K_d × the tolerance of every compared occupancy.
    The background guard (§8.3, Q5) checks the insensitivity.
  - Sites also sequester the trace itself. A node's trace content is far below a site pool, so its
    free trace falls toward the anchored stall: positive, and no refusal.

### 4.4 The heat sign

- **For the exact flow,** H ≥ 0 at every binding sub-stage. The sub-system is closed and
  detailed-balanced, so G is its Lyapunov function (Rao & Esposito 2016; D152 §3.3).
- **For the integrator, one ligand on one population** (**S**). The sub-stage is one-dimensional
  along the binding extent.
  - |f′| = L_n + L_R + m_b k_off ≤ 3 max L, so h |f′| ≤ 1.5 under the condition.
  - SSPRK(3,3)'s amplification R(z) = 1 + z + z²/2 + z³/6 lies in [0.0625, 1) for z ∈ [−1.5, 0];
    its real root is near −1.596.
  - So the linearised step approaches the binding equilibrium without crossing it. G is convex
    along the extent, so the step lowers G: H ≥ 0.
  - D152 proved the linear A ⇌ B case the same way, with R ∈ [1/3, 1).
- **Several ligands or a shared node:** not proved. It is measured by the guards, and the
  dissipation check refuses a falling heat, loudly (D152's rule).

### 4.5 Splitting

**Against transport.** D152's probe C3, world W2 (A + B ⇌ C with B and C immobile, on a diffusing
chain) is this primitive's structure against @3's faces. It held second order to dt · L ≈ 2, with
order reduction beyond (D152 §4.3). Version 1's refusal of dt · L > 1 sits inside that margin. C3 is
D152's prototype evidence, not a reference of record; this operator's own dt study is its evidence.

**Within the half-step: the departure from D152's rejected split** (departure 4).
- **What D152 rejected.** A symmetric split of passive and driven routes within a node, which would
  split a mixed network's kinetics at O(h²). That network is the activator–inhibitor coupling of a
  Turing system, and "the kinetics outweigh the heat and work attribution".
- **What is split here.** Only internalisation, a one-way, first-order drain of the bound pool that
  is solvable exactly. That is the kind of route D150's exchange already sub-splits in a palindrome
  of exact stages (D150 §2.3: local error ratios 6.90 to 7.85 per halving, approaching 8). The
  coupled network stays whole.
- **What it buys.** Single-class sub-stages, exact state-function bookings, and no hybrid with its
  measured known limit, the reversal onset (D152 §3.3).
- **What it costs: a second-order steady bias, with a closed form** (**S**, Appendix A.6). At a fixed
  free concentration, the palindrome's fixed point B_s against the true quasi-steady B* is

      B_s / B* = e^{−k_i h/2} φ(λh) / φ((λ + k_i) h)  for exact sub-flows,   φ(x) = (1 − e^{−x})/x,

  with λ = m_b(k_on c + k_off) and k_i = m_i k_int. That is 1 − (k_i λ/12 + k_i²/24) h² + O(h⁴).
  - With SSPRK(3,3) for the binding sub-flow, the scheme's own fixed point replaces e^{−λh} by
    R(−λh) (Appendix A.6). That is a sharp prediction for the dt study, as D150's milestone 2
    predicted its splitting bias from the step map's fixed point.
- **Its size** (**S**).
  - At h λ = 0.05 and h k_i = 10⁻³ the bias is about 4e-6.
  - **At the stage condition's extreme it is about 3%.** The condition bounds h k_on c ≤ ½ and
    h (k_off + k_i) ≤ ½ together, so h λ and h k_i cannot both reach their own limits. The largest
    bias is at h k_on c = ½ and h k_i = ½, where the closed form gives 0.970.
  - In the stiff limit, which the condition refuses, binding re-equilibrates before each
    internalisation stage. The apparent K_M then tends to K_d. The rule keeps the scheme away from
    it.
- **The alternative, if the lead prefers it:** one SSPRK(3,3) stage over binding and internalisation
  together, with D152's per-route hybrid at mixed sites. It has no splitting bias. It inherits the
  hybrid, its attribution and its reversal-onset limit (lead question 4).

### 4.6 Which solvers admit it

| Solver or mode | Version 1 | Reason |
| --- | --- | --- |
| IMEX ARS(2,2,2), IMEX Euler | Admitted | The composite's split parts |
| RK4 (reference runs) | **Refused** at the definition | D152 §4.6's reasons hold: (b) the bookings are exact and checked at rounding in the face-free world under IMEX, so RK4's absolute bound adds nothing; (d) D150's RK4 worlds stay the transport's sharp reference; (c) RK4's 1e-4 s step limit; and no consumer needs it. Admitted when a consumer needs it |
| Stationary analysis | Refused | It refuses the composite's ID (D150 probe 2); its Newton test is not scaled per species (D150 §8) |
| Projective and coarse modes | Not admitted | `execution.projective` supports @1 to @3 only |
| vmap, windows, restart, snapshots | Admitted | Per-world parameters and controls are bindings; all state is state (R7) |

**The long-time door** (**S**, for FR-8's note). The primitive's quasi-steady limit is D150's sink,
which is already exact over any step. A long-time mode that makes binding algebraic (quasi-steady
occupancy from the free concentrations, the sink as the uptake) has a qualified target on each
side.

### 4.7 Cost and the 30-minute rule

- **Cost** (**S**). Per half-step, one SSPRK(3,3) stage (three rate and three stage-condition
  evaluations over the routes) and two exact internalisation stages: O(routes), small beside the
  dense field (D150 §4.4). The operator adds no species row and no field node.
- **The 30-minute rule** (**S**). With neutral, impermeant ligands at fixed volumes, the site
  equations are decoupled from the ions. Their discrete problem depends only on dt times the rates,
  the ratios S/(V K_d) and c/K_d, and the geometry. Compressed worlds with rates of order 1 to
  10 s⁻¹ exercise the same discrete operator in seconds to minutes of CPU. True-parameter runs are
  detached tier-3 runs.

### 4.8 Idleness (D136)

There are three claims, in D150's and D152's form.
1. **Not declared. Promised.** Every existing composition's jaxprs, constants and bindings are
   identical under the constants-aware crossrev, in all five sets and in D150's and D152's own sets.
   The operator is a new module, and its one shared change is host-only (§6.3).
2. **Declared, but idle. Promised.**
   - No routes: statically idle.
   - Every multiplier of a sub-system zero in a step: each sub-stage selects its start state with
     `where`, never adding a computed zero.
   - Every field is then bitwise equal to the composition without the operator. A population whose
     routes are all off is selected unchanged.
3. **Populations declared and inert, against none. Reported, not promised** (D150's claim 3): the
   reduce order over the route axis is program-specific.

## 5. Partition and reset at division and replacement

The rules are declared now so that the state fits them. Version 1 refuses both compositions: closers
through `CONFLICTS_VIEW`, and replaced slots at the definition. The doors are named.

### 5.1 Division (the partition, S5)

**The declared rule.** A population moves with its owner's map. The extensive quantities split by
the owner's fraction:
- a patch population by a_k, its patch's area fraction (S5 §3: a population takes its patch's
  fraction);
- a contact population by a_e.

The split covers copies, free sites R and every bound pool B_s. The daughter populations are the
parent's functional unit, with anchors as exact fractions (S5 §3.2's fl(a x), fl(x − fl(a x)) rule).

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
  ligands' constants and initial occupancy (D150 §2.5 requirement 4: "templates declare the
  newcomer's occupancy").
- **A donor copy** takes the donor's site state, under D150's ruling for donor route values: admitted
  only where the declared values equal the slot's.
- **Never from the previous occupant.**
- **Contacts incident to a replaced slot** restart: their populations reset to a declared arrival
  state, as the formation law restarts their abundance from its declared arrival state.

**Version 1 refuses** populations on patches of replaced slots and on contacts incident to them, at
the definition, reading replacement's schedule as D152 does. Populations of cells that are not
replaced, and of contacts between such cells, compose. The door is D150's occupant tables plus an
event part of this operator at replacement's event steps, as the coupling note's version 1.1 reset
is designed.

### 5.3 The chain: binding (FR-3), internalisation with membrane (FR-2), delivery (FR-1)

What each step writes, so that the bound pool's identity survives each transfer (**S**; FR-1 and
FR-2 have no accepted design yet):

| Step | Writer | What moves | Identity |
| --- | --- | --- | --- |
| Binding at the surface | This operator (version 1) | Free ligand at the facing node ↔ B on the population | (species, population) |
| Site-conserving internalisation | This operator (version 1) | B → the patch's cell's row; the site stays | (species) in the cytosol: FR-1's identity loss, version 1's stated limit |
| Internalisation with membrane | FR-2's retrieval law, through `ACCEPTS_WRITES` | A fraction of the patch's area, with that fraction of each population's R and B, onto the compartment's bounding patch | (species, population): cargo stays bound on the moved membrane |
| Release into the compartment | This operator's binding law, at the moved population's facing node | B → the compartment's free row (release at k_off; a pH-conditioned release is FR-4's and FR-5's routing door) | (species) inside the compartment, distinct from the cytosol |
| Recycling or degradation | FR-2's exocytic direction, or a sink law | Sites back to the surface, or consumed | Population abundance |

**What this note asks of FR-1** (lead question 11). The FR-1 agent's notes, read only, point to a
face-free finite node bounded by one patch of its owning cell (D150's `face_free` topology).
- If FR-1 presents the compartment's lumen as the bounding patch's outside node, an outward-facing
  population on that patch faces the lumen. The outer leaflet faces the lumen after endocytosis
  (**S**). Release then needs no new rule.
- Internalisation from a patch that faces a compartment means nothing. FR-1 must let the site
  operator tell an extracellular finite node from a compartment, and refuse it there.

**What this note asks of FR-2.** Its retrieval moves this operator's pools by the same area fraction
as the membrane, through `ACCEPTS_WRITES`. Its energy source, the shared energy-pool design, also
serves this operator's internalisation work (§3.3).

## 6. Composition

### 6.1 With the existing operators

| With | Version 1 | Why |
| --- | --- | --- |
| @3 alone; `electrode_current_injection@1` | Composes | No view conflict. Injection refuses neutral carriers |
| D150's `scheduled_species_turnover@1` | Composes | Writers of the same rows; fluxes add, split at O(dt²) |
| D150's `scheduled_species_exchange@1` | Composes | Both read the declared volumes; secretion beside binding is the autocrine and paracrine case. Declaring the saturable sink and the primitive for one uptake would double-count; that is the world's choice, flagged in the summary |
| D152's `local_species_reactions@1` | Composes, including on a row both write | Binding is a surface process across a patch, as exchange is. D152's one-local-kinetics-writer rule refuses turnover, not exchange (its §1.1). Split at O(dt²), measured by the composition world (§8.3); lead question 7 |
| The coupling operator (`species_regulated_availability@1`) | Composes | It reads cell rows that this operator writes in half-steps; reads are not writes. Occupancy as a coupling source is a door (§9) |
| `membrane_entity_state@1` | Composes | No conflict; it provides views this operator never reads. The composition is then a field-input composition because of membrane state. Areas do not move without insertion, which is refused |
| `scheduled_cell_replacement@1` | Composes off replaced slots | §5.2 |
| Water; the lumens; replacement@2 | Refused (volumes) | Concentrations and ΔG read the declared volume. The door is D150 §5.1's `VIEW_READS` with bookings at the view |
| Insertion@1 and @2; the partition; the bridge | Refused (masks) | Insertion@1 provides the masks and outside anchors (`membrane_insertion.py:480–485`); the others are closers. The door is §5.1's liveness rule |
| The k-anion symport | Waits | It requires water |

### 6.2 Refusals

**At the definition:**
- **Ligands:** a charged or permeant species (`parse_species`, `check_impermeant`); a species the
  model does not declare; an identity that differs from another inventory operator's; more than
  `MAX_SPECIES` species in the world (`check_species_cap`, with its message).
- **Owners:** an unknown patch or contact; an outward-facing population on a patch that faces a
  held bath. The bath's composition is held, and binding from a chemostat, booked as reservoir
  supply, is a door.
- **Populations:** copies ≤ 0; sites per copy not a positive integer; α outside (0, 1]; no ligand;
  a ligand listed twice; initial occupancies negative or summing above 1.
- **Laws:** k_on ≤ 0 or k_off ≤ 0; k_int < 0; internalisation on an inward-facing patch or a
  contact; a destination other than `"cell"`.
- **Slots:** a population on a patch of a replaced slot, or on a contact incident to one.
- **Solvers:** RK4; the stationary analysis.
- **View conflicts** (§1.5).
- **Schedules:** a route without a schedule; one not starting at 0; a change off the dt grid or
  outside the horizon; a negative multiplier.
- **Keys:** unknown keys; duplicate IDs.

**At run time:** the stage condition (dt · L > 1); a non-finite or negative amount; a free row not
positive. Each is returned as the half-step's validity, since @3's domain is not re-run after the
second half (D150 §2.2). The composite's dissipation check refuses a falling heat.

### 6.3 Crossrev, the batch signature, D148

- **Crossrev.** The five existing sets and D150's and D152's own sets are identical. The operator's
  own set gets its first record at landing: two value twins with every parameter and multiplier
  changed must give identical jaxpr text and constants, with only bound arrays differing (D152's
  ruling Q11 (b)).
- **One host-only shared change.** `species_common.SPECIES_LAWS` (line 45) lists only D150's two
  laws, and `check_identities` (177–192) compares against that list alone. This operator and D152's
  join it. The change is definition-time and changes no compiled program, so crossrev is unchanged.
- **The species cap** is referenced symbolically, through `check_species_cap`. It is 7 in code until
  D165's D148 change lands, then 16. Code may start before that; worlds above 7 species wait for
  it.
- **D148.** No in-place change to compiled shared code is proposed. The SSPRK(3,3) stages are
  written for this operator from D152 §4.2's equations, and D152's module stays untouched during
  MG0c. A later shared helper is adopted under crossrev, as the coupling note's ruling 7 did for the
  Hill factor.

## 7. Generality (D144): the consumers, against version 1 and the doors

| Consumer (source) | What it needs | Version 1 | Door |
| --- | --- | --- | --- |
| The saturable uptake limit (D150 §2.5) | Binding with site-conserving internalisation | **Yes** | – |
| Receptor-mediated uptake with surface depletion (FR-2's requester) | Sites consumed and returned | Binding only | FR-2's internalisation with membrane |
| Delivery into a compartment (FR-1's requester) | Cargo distinct from the cytosol | – | FR-1's destination and FR-2 (§5.3) |
| Competition between cells for a shared dose (FR-2's requester) | Several cells' populations facing one node | **Yes** | – |
| Ligand–receptor signalling (FR-3) | Occupancy driving a response | Binding: **yes** | **Occupancy as a coupling source**: a cross-operator state read in the coupling operator's source semantics, beside FR-7's population-abundance source. Occupancy is not moved by @3's step, so an instantaneous factor of it would be held exactly (**S**) |
| Engineered quorum-sensing consortia (FR-3; the requester's reading list, not in the repository and not read) | Finite receptor pools per cell reading a shared signal | Binding: **yes** | The occupancy source, above |
| Kinetochore-like sites (D150 §2.5; the kinetochore review) | Sites present but inaccessible against a large free pool | α: **yes**, with inward-facing or contact populations as cytosol-facing owners | An intracellular-structure owner, with a segregation rule. No kinetochore entity (the review; D144) |
| Accessibility by surface composition (FR-3: the 2026 glycocalyx and protein-corona work; the requester's text, not read) | Uptake of one formulation differing by cell type, without naming a receptor | Per-domain α: **yes** | Regulated: §2.3 |
| Antagonists, competitors, modification states | Several ligands per population | **Yes** | – |
| Junction docking (D150 §2.5) | Binding between two populations across a contact | – | A docking law writing junction abundance: the mechanistic form of the coupling note's contact-maturation process (its §3.3) |
| Surface catalysis (D150 §2.5; D152 §2.2) | A driven fate of the bound complex into a product at the facing node | – | A second driven route kind, with D152's moiety rules |
| Morphogen gradients with binding (D150 §6: FCS free D against FRAP effective D; Kicheva 2007's immobile fraction; Yu 2009's receptor sink) | Binding to cell-surface sites beside face transport | Binding with faces: **yes** | Its qualification against the fast-binding limit D/(1 + (S/V)/K_d) (Appendix A.7) is a later item (§8.3) |
| Buffering by membrane sites (FR-4) | Charged ligands | – | The charged door (§3.2) |

## 8. Qualification

### 8.1 The first acceptance is numerical (D138)

**Can a version 1 run differ from its references?** Only by discretisation and splitting error
(**S**):
- the law's equations are the declared ones;
- the ligands are neutral and impermeant, so they are decoupled from the ions;
- the volumes are fixed.

A comparison with a paper's data would test that paper's binding model and parameters, not the
engine. So the first acceptance is numerical qualification against mathematics: closed forms, an
independent integration of the declared equations, and D150's sink. That is within D138 on the
lead's reading of MG0c (D152 question 9).

### 8.2 The references

- **Written by an agent that never reads the operator's code,** from Appendix A, with a usage note.
  The engine agent runs them only through that note, as in S5, D152 and the coupling note.
- **R-closed:** every closed form of A.4.
- **R-ode:** the declared ODE (A.2) integrated by SciPy at tight tolerance (Radau, cross-checked by
  DOP853, as D152's references are). It covers depletion with internalisation, two populations
  sharing a node, and competition.
- **R-qss:** D150's saturable closed form with A.5's unit map.
- **R-dG:** the NumPy ΔG test per law (§3.4 item 2).
- **R-eq:** an independent equilibrium solver for shared-node worlds, and the relaxation's total heat
  G(start) − G(equilibrium).

### 8.3 The acceptance items

Tolerances are pinned at registration from the dt studies and the references' own terms (D150 §6's
rule). Each judged run is made once, from a clean snapshot.

| Item | World | Shows | Criterion |
| --- | --- | --- | --- |
| **Q1, day one: the saturable-sink limit** | Face-free: one passive cell; an outward-facing population on its patch, facing a finite node of volume V; the ligand pre-formed at c₀ and B₀ at its quasi-steady value (the resolved start, against the initial layer); binding and internalisation. A sweep ε = (S/V)/(K_M + c₀) ∈ {10⁻¹, 10⁻², 10⁻³}, with rates fixed and S varied | (a) The engine against R-ode at each ε, under dt refinement. (b) R-ode against R-qss, with the unit map A·V_max = k_int S and K_M = (k_off + k_int)/k_on. (c) The engine at the smallest admitted ε against R-qss | (a) The dt study (D150's form), with the splitting bias against A.6's fixed point. (b) Reported: the observed order in ε, expected 1 (Segel & Slemrod 1989), the validity regime stated. (c) Within the ε term plus the dt term |
| **Q2, equilibrium occupancy** | Large V (no depletion), one and two ligands; small V (depletion), one ligand; two cells' populations facing one node | Competitive Langmuir; the depletion quadratic; R-eq's shared-node root; the total heat to equilibrium | Long-time state within the steady tolerance; heat against G(start) − G(eq) |
| **Q3, binding kinetics** | Fixed c (association, dissociation, competition); a closed node (depletion); internalisation at fixed c | Pseudo-first-order exponentials; the Riccati form; the matrix exponential of competition (Motulsky & Mahan's form); the linear internalisation closed form | Second order in dt against each, at every record |
| **Q4, accessibility as a pure factor** | α ∈ {1, ½, ¼} (exact binary fractions), at c ≪ K_d and c = 100 K_d, no depletion; Q1's world at α = ½ | Equilibrium θ(α)/θ(1) = α in both regimes; saturation at α; relaxation rate independent of α; the sink's V_max ∝ α and K_M unchanged. **Negative controls:** (K) implemented instead fails at c ≪ K_d and in the rate; (A) fails at saturation and in K_M | Within the steady and dt tolerances; each control caught by a registered margin |
| **Q5, accounting and energy** | §3.4's worlds | The material, moiety and system-total identities at the species' floors; the face-free residual at rounding; heat ≥ 0 on every row; the NumPy ΔG test; the negative controls; the background guard (a 10³ change of a trace well below K_d moves every compared quantity far below its tolerance) | As stated |
| **Q6, idleness, restart, vmap, crossrev, signature, refusals** | Existing sets; Q1–Q3 worlds | §4.8's claims 1 and 2; restart bitwise at, before and after a multiplier change, also through a written snapshot; a vector batch mixing every parameter, bitwise against its reverse and within 1e-12 of each scalar run; the signature refusing different structures; each refusal with its message | As claimed |
| **Q7, against D150's sink, engine to engine** | Q1's world twice: once with this operator, once with exchange's saturable import at the mapped A·V_max and K_M | The node's and cell's amounts agree to the ε term | Reported, not judged: two engine laws, one author per side |

**Later items, not the first acceptance:**
- **The composition world with faces**: binding to sites on every node of a chain, against the
  fast-binding limit D/(1 + (S/V)/K_d) of A.7, and against R-ode's diffusion–binding system under
  refinement. This is D152's C5 analogue and the bridge to D150 §6's FCS-against-FRAP distinction.
- **A biological comparison**, only when a consumer registers one (D151). The candidates are D150
  §6's Fgf8, Dpp and Wingless records. None is proposed here.

### 8.4 What is not claimed

- **No reproduction of the kinetochore counts.** That test is the review's rank 3, deferred under
  D151 (first written "not recommended"). It needs kinetochore-specific topology to score six
  numbers from one species in one arrested state.
  The primitive represents the review's constraint through α, which is what α means. That is a value
  check of the factor (Q4), not a biological result.
- **No claim about the glycocalyx or quorum-sensing work.** It is the requester's text, not found in
  the repository and not read.
- **No claim about receptor-kinetic values.** Every value in this note is synthetic.

### 8.5 Pre-code probes, for the lead (none run)

| Probe | Question | Criterion, written now |
| --- | --- | --- |
| P1, the contract fit (the code's milestone 1, as D152's C1) | The field map (one owner per row, the `ACCEPTS_WRITES` wiring with no writer), the ledgers at the species' floors, the face-free world at rounding, idle and restart | Bitwise idle; every ledger at its floor; residual/allowance ≤ 1 on every row |
| P2, the split's bias (NumPy) | Does A.6's closed form predict the palindrome's fixed point? | Within 10% of the leading term at hλ ≤ 0.25; the scheme's fixed point with R(−λh) to rounding in the linear case |
| P3, the heat sign (NumPy) | Is H ≥ 0 at admitted steps with two ligands and with two populations sharing a node, across the binding equilibrium? | No negative heat beyond −1e-12 pJ over a declared sweep up to h max L = ½ |
| P4, the trace | How far below K_d must c_bg sit for Q4's and Q1's tolerances? | The rule c_bg ≤ (tolerance) × K_d confirmed on Q1's world |

## 9. Limits and doors

**Version 1 includes** the operator `site_occupancy@1` with:
- site populations on patches (either face) and contacts (one side);
- Langmuir binding with competition, and per-domain accessibility;
- site-conserving internalisation into the patch's cell;
- the owned site free energy, heat for binding and work for internalisation;
- the palindromic half-step;
- IMEX inner steps, vmap, windows and restart;
- composition as in §6.1.

**The doors** (each needs its own design and qualification):

| Door | What it needs |
| --- | --- |
| Internalisation with membrane (FR-2) | FR-2's retrieval writing these pools through `ACCEPTS_WRITES`; its energy source |
| A compartment destination (FR-1) | FR-1's node; a destination key value; refusal of internalisation from a compartment-facing patch |
| Partition | A partition version writing these pools; the one liveness rule (coupling ruling 8) |
| Replacement | D150's occupant tables; an event part at replacement's steps (§5.2) |
| Volume (water, the lumens) | D150 §5.1's `VIEW_READS` fallback and bookings at the view |
| Regulated accessibility | The kinetic form through the routing door (D156); a regulated capacity with its work booking and its rule above occupancy (§2.3) |
| Occupancy as a coupling source | A cross-operator state read in the coupling operator's source semantics |
| Surface catalysis | A driven route from the bound complex to a product at the facing node, with D152's moiety rules |
| Docking between populations | A 2D–2D law between two cells' populations across a contact, writing junction abundance |
| An intracellular-structure owner | A cell-owned population with a declared segregation fraction |
| Binding from a held bath (a chemostat) | Bookings as reservoir supply with μ_b work |
| Charged ligands | §3.2's charge rule; FR-4's buffering |
| Stiff binding (dt · L > 1) | Sub-steps with an order-holding splitting, a positive implicit half-step, or the exact Riccati stage for single-ligand populations |
| Cooperative or multivalent sites; irreversible capture | Their own laws |
| Site turnover (synthesis, degradation, constitutive internalisation of free sites) | A writer of R and copies, booked as population abundance |
| Owner and law split | A state owner without `VIEW_FIELDS` admitted by the contract (`contract.py:335–341`), when a second law writes the pools |
| Energy pools | Internalisation's work drawn from finite pools, in the shared design (FR-2, FR-4) |

**What this note does not authorise:**
- code before it is accepted (D142);
- any change to membrane state, the partition, replacement, D150's or D152's operators or designs,
  the coupling operator, @3, or the composite and adapter, beyond §6.3's host-only list;
- a law or population named for a receptor, a protein or a study (D144);
- reproducing a paper's model (D138, D151);
- any scientific acceptance. Integration grants none.

## 10. Effort and order of work

| Part | Agent-days |
| --- | --- |
| Milestone 1, the contract fit (P1): spec, parser, refusals (owners, faces, ligands, destinations, accessibility, identities, cap), binding layout, the identity list | 1.0 |
| The half-step: the binding stage (SSPRK(3,3), the stage condition with internalisation counted), the exact internalisation stages, the palindrome, the bookings per facing node and receiving cell, the site free energy, idle selection | 1.5 |
| Ledger terms, own ledgers, observations, the summary, the tier-1 smoke (under 20 s) | 0.5 |
| Guards in the branch: the face-free energy world, negative controls, positivity, restart, vmap, the crossrev set, refusals | 1.0 |
| **Independent references, by a second agent that never reads the operator's code:** Appendix A's closed forms, R-ode, R-qss, R-dG, R-eq and the usage note | 1.0–1.5 |
| The numerical protocol and its judged run (CPU, under an hour) | 0.5–1.0 |
| **Total** | **about 6 (5 to 7)** |

Option M (§1.3) would add about 1.5 days (**S**).

**Order:**
1. **This note's review**, the lead with the advisor.
2. **Milestone 1**, the contract fit, in the checkout behind its guards. Nothing blocks it: @3, D150's
   adapter functions and helpers, and D152's equations are on main. Worlds stay at 7 species or
   fewer until D165 lands.
3. **The operator and its guards.**
4. **The references agent** starts once milestone 1 has fixed the declaration, as for the coupling
   note (its ruling 11).
5. **The protocol** and its judged run.
6. **The doors**, in FR-1's and FR-2's order (D167). Internalisation with membrane follows FR-2's
   design; the compartment destination follows FR-1's code.

Each step lands behind its tier-1 tests; tier 2 runs before landing (AGENTS.md). Long runs go
through `scripts/run_detached.sh`. No GPU is needed.

## 11. Questions

**For the lead:**
1. **The owner** (§1.3): option O, this operator owning its populations (recommended), or option M,
   membrane state @2?
2. **Accessibility** (§2.3): the capacity form, with the both-direction multiplier as a separate
   kinetic control, in place of the mapping's "multiplier on the binding rate"?
3. **Internalisation in version 1** (§2.4): the site-conserving form into the patch's cell only, with
   a declared destination key? FR-2's consuming form and FR-1's destination would stay doors. This
   resolves "follows FR-2" against "guard on day one".
4. **The palindrome** (§4.5), with internalisation counted in the stage condition? Or one coupled
   SSPRK(3,3) stage with D152's per-route hybrid?
5. **Owners in version 1**: patches on both faces and contacts on one side, with intracellular
   structures a door?
6. **Several ligands per population** in version 1, for competition and occluders?
7. **D152 on a shared row** (§6.1): compose, treating binding as a surface process as exchange is,
   rather than extend D152's one-writer refusal?
8. **The refusals** of RK4, of sites facing a held bath, and of the stationary analysis?
9. **The trace rule**, c_bg ≪ K_d, as a world-building rule checked by the background guard rather
   than a definition refusal?
10. **The host-only identity list** in `species_common` (§6.3)?
11. **FR-1's node shape** (§5.3): will FR-1 present the compartment's lumen as its bounding patch's
    outside node? If so, outward-facing populations face the lumen with no new rule. This assumes
    the FR-1 agent's notes, which are not yet a design.
12. **The pre-code probes** P1 to P4 (§8.5): P1 as milestone 1, and P2 to P4 before code or folded
    into the references?

**For the user:**
1. **Regulated accessibility.** Is the kinetic form, through the routing door and booking nothing,
   enough at first? Sites made inaccessible while occupied would then be designed when a consumer
   needs them, with an occluder species as the accounted route meanwhile.
2. **The energy of internalisation.** Should it draw on finite energy pools when the shared
   energy-pool design lands, with FR-2's and FR-4's (D150 question 11, D152 question 10)?
3. **Benchmarks.** No biological comparison is proposed. The kinetochore test is deferred (D151;
   the review's rank 3), and the requester's glycocalyx and quorum-sensing sources are unread here.
   Is a numerical first acceptance acceptable, with a biological benchmark sourced when a consumer
   registers one?

## Appendix A. Equations for the independent references

The references are written from these equations, not from engine code. Units are @3's: fmol, pL,
mM, s. RT is the engine's, 1e-3 R T pJ/fmol; the references take it as an input (D152 §11's
correction).

**A.1 Notation.**
- Node i (a cell or a finite outside node) has declared volume V_i. A ligand s has free amount
  n_s,i > 0 and c = n/V.
- Population k has facing node i(k) and, if outward-facing on a patch, receiving cell r(k).
- Copies N_k, sites per copy ν_k, accessible fraction α_k ∈ (0, 1], N_f = 602,214,076 per fmol, and
  S_k = α_k ν_k N_k / N_f.
- The pools are R_k ≥ 0 and B_ks ≥ 0, with R_k + Σ_s B_ks = S_k.
- Constants k_on,ks, k_off,ks > 0 and k_int,ks ≥ 0, with K_d = k_off/k_on; multipliers m_b, m_i ≥ 0.
- h = dt/2.

**A.2 The ODE.**

    J_ks = m_b,ks (k_on,ks c_s,i(k) R_k − k_off,ks B_ks),     I_ks = m_i,ks k_int,ks B_ks
    dB_ks/dt = J_ks − I_ks
    dR_k/dt = −Σ_s J_ks + Σ_s I_ks
    dn_s,i/dt = −Σ_{k: i(k)=i} J_ks + Σ_{k: r(k)=i} I_ks + (other writers)

**A.3 Free energy.**
- G_site,k = Σ_s B_ks [ΔG°_ks + RT ln(B_ks/S_k)] + RT R_k ln(R_k/S_k), with
  ΔG°_ks = RT ln(K_d,ks / 1 mM) and 0 ln 0 = 0.
- G_node,i = RT Σ_s n_s,i (ln(n_s,i/V_i) − 1), on the touched rows.
- The binding sub-stage books H = −Δ(Σ G) per facing node; the internalisation sub-stage books
  W = Δ(Σ G) per receiving cell. The ledger: Δ(G_node) + Δ(G_site) + H − W = 0.
- The per-mole free-energy change of binding is RT ln(K_d B/(c R)), zero at equilibrium.

**A.4 Closed forms** (each with one ligand on one population unless stated; m = 1):
- **Association at fixed c:** B(t) = B_eq + (B₀ − B_eq) e^{−λt}, with λ = k_on c + k_off and
  B_eq = S c/(K_d + c).
- **Dissociation** into a node held near zero: B(t) = B₀ e^{−k_off t}.
- **Competition at fixed concentrations.**
  - Equilibrium: B_s = S (c_s/K_s)/(1 + Σ_j c_j/K_j).
  - Kinetics: dB/dt = a − M B, with a_s = k_on,s c_s S and M = diag(k_off) + (k_on ∘ c) 1ᵀ, so
    B(t) = B_eq + expm(−M t)(B₀ − B_eq) and B_eq = M⁻¹ a. This is the form Motulsky & Mahan (1984)
    give for one labelled ligand and one competitor (record verified, text not read).
- **Depletion in a closed node, no internalisation.** With N = n + B constant:
  dB/dt = (k_on/V)(B − r₋)(B − r₊).
  - r± = [(N + S + K_d V) ± √((N + S + K_d V)² − 4 N S)]/2, and the equilibrium is r₋ (the
    quadratic binding equation of ligand depletion).
  - With Δ = r₊ − r₋, κ = k_on Δ/V and Q₀ = (B₀ − r₋)/(B₀ − r₊):
    B(t) = (r₋ − r₊ Q₀ e^{−κt})/(1 − Q₀ e^{−κt}).
- **Internalisation at fixed c.** With Λ = k_on c + k_off + k_int and B* = k_on c S/Λ:
  B(t) = B* + (B₀ − B*) e^{−Λt}, and the internalised amount is
  U(t) = k_int [B* t + (B₀ − B*)(1 − e^{−Λt})/Λ].
- **Two populations on one closed node:** no closed form. R-ode and R-eq cover it.

**A.5 The quasi-steady limit and D150's sink.**
- With ε = (S/V)/(K_M + c₀) ≪ 1 (Segel & Slemrod 1989; Borghans, de Boer & Segel 1996 for the total
  approximation), the node's amount follows D150's saturable law:
  b ln(n₀/n) + (n₀ − n) = a t.
- The unit map: a = k_int S = A·V_max, b = K_M V, and K_M = (k_off + k_int)/k_on.
- The error is O(ε) after an initial layer of duration about 1/Λ. A start with B₀ at its
  quasi-steady value suppresses the layer.
- With accessibility, S already carries α, so V_max scales by α and K_M does not.

**A.6 The palindrome's fixed point** (needed only to read the dt study; the references do not
reproduce the scheme).
- At fixed c, one half-step maps B to u[B_e + (uB − B_e) v], with u = e^{−k_i h/2},
  B_e = S c/(K_d + c), λ = m_b(k_on c + k_off) and k_i = m_i k_int.
  - With exact sub-flows, v = e^{−λh}.
  - With SSPRK(3,3) for binding, v = R(−λh), where R(z) = 1 + z + z²/2 + z³/6: exact for this affine
    ODE.
- Its fixed point is B_s = u B_e (1 − v)/(1 − u² v).
- With exact sub-flows, B_s/B* = e^{−k_i h/2} φ(λh)/φ((λ + k_i)h), with φ(x) = (1 − e^{−x})/x, which
  is 1 − (k_i λ/12 + k_i²/24) h² + O(h⁴). Here B* = m_b k_on c S/(λ + k_i).

**A.7 The fast-binding limit with transport** (for the later composition item). With local
equilibrium b = s c/(K_d + c), s = S/V per node and immobile sites, ∂(c + b)/∂t = D ∇²c. That gives
(1 + s K_d/(K_d + c)²) ∂c/∂t = D ∇²c, and for c ≪ K_d an effective diffusivity D/(1 + s/K_d)
(**S**; the linear case of Crank 1975, ch. 14, not re-read here).

**A.8 What is compared:** amounts, pools, occupancies, rates, heat and work at saved rows; the
observed orders in dt and in ε.

## References

Records checked by Crossref (and Europe PMC for one PMID), with no project details sent. The texts
were not read unless stated. Entries marked D152 were checked there.
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
  2026;226(1):e202603185. doi:10.1083/jcb.202603185. Read through the repository's review
  ([PAPER_REVIEW_KINETOCHORE_COUNTS.md](PAPER_REVIEW_KINETOCHORE_COUNTS.md)), which read the full text.
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
- Motulsky HJ, Mahan LC. The kinetics of competitive radioligand binding predicted by the law of
  mass action. *Mol Pharmacol* 1984;25(1):1–9. PMID 6708928; doi:10.1016/s0026-895x(25)15016-5
- Rao R, Esposito M. Nonequilibrium thermodynamics of chemical reaction networks: wisdom from
  stochastic thermodynamics. *Phys Rev X* 2016;6(4):041064. doi:10.1103/PhysRevX.6.041064 (D152)
- Segel LA, Slemrod M. The quasi-steady-state assumption: a case study in perturbation. *SIAM Rev*
  1989;31(3):446–477. doi:10.1137/1031091 (D152)
- Shu C-W, Osher S. Efficient implementation of essentially non-oscillatory shock-capturing schemes.
  *J Comput Phys* 1988;77(2):439–471. doi:10.1016/0021-9991(88)90177-5 (D152)
- Strang G. On the construction and comparison of difference schemes. *SIAM J Numer Anal*
  1968;5(3):506–517. doi:10.1137/0705041 (D152)
- Wiley HS, Cunningham DD. A steady state model for analyzing the cellular binding, internalization
  and degradation of polypeptide ligands. *Cell* 1981;25(2):433–440.
  doi:10.1016/0092-8674(81)90061-1

The requester's sources that this note did not find or read: the 2026 glycocalyx and protein-corona
work, and the engineered quorum-sensing consortia of the 13 November reading list (FR-3).
