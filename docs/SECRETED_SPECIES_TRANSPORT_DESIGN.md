# Secreted-species transport (design)

**Status: proposed, 13 November 2026, for the lead's and the advisor's review (D142). No code.**
D150 promoted this feature. The user's words were: "we do have plans to be able to run special
modes of Cells at differnt timescales, so down the road nothing right now but for sure the
secreted-species transport now". The decision reads:
- **Promoted now:** general secreted-species transport. A protein-scale species is secreted by
  cells, moves in extracellular space, and is taken up or cleared, with conserved accounting and
  a catalogue identity. It is a general, reusable engine feature (D136, D144), never specific to
  granzyme K, and it also serves the roadmap's morphogen-source goal (ROADMAP item 9).
- **Design first (D142),** then code behind the usual guards. Calibration comes from a measured
  protein or morphogen gradient in the literature.
- **Deferred:** organ-scale ageing timescales (months) wait for Cells' planned long-time modes.

**Motivation.**
- The [granzyme K review](PAPER_REVIEW_GZMK_AGEING.md) gives this as candidate 1 (§3 item 1 and
  §4 rank 1).
- [ROADMAP](ROADMAP.md) item 9: "morphogen sources can come from secretion rather than being
  prescribed".
- The [current plan's](CURRENT_PLAN.md) entity table already lists secretion, uptake and
  diffusion as contributions to the extracellular environment.

**Engine models it runs (AGENTS.md milestone rule):**
- `resolved_pump_composite@1` over `resolved_pump_tissue@3`;
- two new operators, `scheduled_species_turnover@1` and `scheduled_species_exchange@1`
  (§2.2, §2.3).

No model, solver or shared function changes.

**Basis.**
- The [v2 design](PUMP_COMPOSITE_V2_DESIGN.md) §1–§4 (the contract).
- The S5 design, `docs/CELL_DIVISION_S5_DESIGN.md`, which is **not on main**. It is cited at
  34edc86 on branch `worktree-agent-aa650be3bffdbdb54`.
- The [protein catalogue plan](PROTEIN_CATALOGUE_PLAN.md).
- The [field-solver interface](FIELD_SOLVER_INTERFACE_DESIGN.md).

**Evidence and log:** `/mnt/workspaces/Cells/secreted-species-20261113-01/` (HANDOFF.md; the
probe of §1.2). **S** marks our arithmetic or interpretation, as in the division design.

## 0. Summary

1. **One inventory.** A secreted species is one more row of @3's species axis, with valence 0,
   zero membrane and junction permeability, and its own diffusivity on every face. @3 owns its
   amounts, as it owns the ions'. There is no second copy, so the split that
   `network_reactions@1` makes does not arise (§1.1).
2. **Transport needs no new law.**
   - @3's face law carries the species. For z = 0 it is Fick's law exactly (§2.1).
   - Held baths are its far-field sinks, already booked as reservoir supply.
   - **The probe** (§1.2) measured this on the engine as it is, at bab3d06:
     - the definition parses;
     - every host check passes;
     - the face flux equals (D A/L) Δc to 1.0e-14 relative;
     - the chain matches its exact solution to second order;
     - every ionic field is bitwise unchanged by the declared species, in that compiled
       program.
3. **Sources and sinks are writers** of that inventory, through `ENTITY_WRITES` with their own
   accumulators, as injection and the lumen are (§2.2, §2.3):
   - production and first-order clearance at nodes (`scheduled_species_turnover@1`);
   - secretion and uptake across patches (`scheduled_species_exchange@1`).

   Every half-step is exact. Each books the exact free-energy change as signed **work**, not
   heat (§2.4).
4. **Uptake is a plain sink in version 1** (the lead's option (a); §2.5):
   - first-order or saturable removal from an outside node into the cell's inventory;
   - no site state.

   The four occupancy requirements are recorded as a door kept open.
5. **Neutral in the field** (§3). With z = 0 every charge, drift and conductance term the
   species touches is an exact zero. The species provides no field input, so the 64-node cap
   does not apply to it.
6. **"Absent" means a declared trace background.** @3's spec and domain require every species to
   be positive at every active node. The references include the trace: the equations are linear,
   so its contribution is an additive solution bounded by c_bg (§1.3).
7. **Version 1 is transport on a static tissue** (§5.5). Its operators refuse volume providers
   (water, the lumen), membrane-state areas and activity closers. Version 1.1 lifts these after
   the volume ledger and S5a land; the contents themselves already compose (§5).
8. **Calibration:** Pomreinke et al. 2017 (BMP2b and Chordin; values read) first; Kicheva et al.
   2007 and Müller et al. 2012 (records verified; full text not readable here) (§6).
9. **Effort:** about 6 agent-days (range 5–7.5), plus CPU hours for the calibration runs (§9).

## 1. Entities and ownership

### 1.1 One inventory: @3's species axis

**Decision.** A protein-scale species is declared in the inner model's species list like an ion:
`{"id": ..., "valence": 0}`. Its amounts are then @3's state, in `amount_increment` [species,
cell] and `extracellular_amount_increment` [species, outside], over @3's declared anchors. These
are the compartment and extracellular-environment entities of the plan's ownership table, and
they are the material account every physical operator already acts on.

**What follows without new code** (each checked in the code and, for the first three, in the
probe):

| Mechanism | How it already treats every species |
| --- | --- |
| Face transport | Per-face, per-species diffusivity (`ExtracellularFaceSpec.diffusivity_m2_per_s`); the face law in `numerics/surface_transport.transport` |
| Held baths | Prescribed concentration per species; exchange booked in `reservoir_supplied` and `reservoir_work_pJ` (μ_b × supply) |
| Ledgers | Per-species local, outside and total material ledgers, with a per-species floor (`material_balance_atol_fmol`); the chemical term of the energy ledger sums every species |
| Water | Osmolytes are the sum of every species' amounts plus impermeants (`numerics/osmotic_water.edge_exchange`); the dilution term uses the same amounts |
| Replacement | The event swaps every species' amounts: occupant out as waste, template or donor in (`cell_replacement.py`) |
| Partition (S5) | Splits every species' increment by f, with anchors as exact fractions (S5 §3.2–§3.3) |
| Stationary analysis | Cell and finite extracellular amounts are dynamical fields (`analysis/stationary.py`) |

**Why not a separate inventory operator.** The alternative is an operator that owns the species'
amounts on cells and nodes. Diffusion would run through @3's face topology, with the operator's
own ledgers. That would keep @3's arrays untouched, but it is the `network_reactions@1` pattern:
a species state beside the physical inventory. `network_reactions@1` holds [..., species,
compartment] concentrations and "no heat, ATP, transport or clipping is owned". The cost of a
second inventory would be:
- every lifecycle operator (water, replacement@1/@2, partition) would have to learn its fields;
- water's osmotic pressure would not see the species, so its dilution free energy would be
  unbooked unless water changed;
- a second diffusion code path would need qualifying.

The one-inventory design has none of these costs. Its price is the trace background (§1.3) and
one species row in @3's per-species work (§4.4).

**The writers' rules, from the advisor's review:**
- **Book in own accumulators, never in @3's route accumulators.** @3's domain requires zero
  transfer wherever a route's coefficient is 0 (`surface_tissue.domain_valid`), and the species'
  membrane permeability is 0. So secretion and uptake cannot be booked as
  `membrane_transferred`, and `adjust_inner` must not add them there either. They enter @3's
  local and outside ledgers through `ledger_terms`, as injection's and the lumen's writes do.
- **Not the membrane-process hook.** It admits one process per composition and requires heat
  ≥ 0, and these laws can run uphill (§2.4). The same reasons rejected it for injection (v2 §4.1).
- **Bath clearance needs no law.** A held bath already removes the species at its prescribed
  concentration, with supply and work booked.

### 1.2 The probe (13 November)

The design rests on @3 carrying such a species with no code change, so this was measured before
writing.

**Setup.**
- Source: a clean snapshot of bab3d06, unit `cells-secreted-probe` on CPU 7.
- Results: exit 0 in 123 s, peak 0.89 GB, memory.events all 0. The script and the JSON are in
  `probe/`.
- **The world.**
  - Six heredity cells (state H), each with its pumped and channelled patch on its own held
    bath.
  - Each cell also has a contact patch on a finite extracellular node of 1 pL. The nodes form a
    chain joined by faces (A = 1e-10 m², L = 1e-5 m, ion D = 1e-9 m²/s), and the last node joins
    a bath.
  - S has valence 0, zero permeability on every membrane and D_S = 1e-10 m²/s.
  - S starts at a trace of 1e-9 mM everywhere and at 1e-3 mM in the first node. Its material
    floor is 1e-20 fmol.
  - The run is 1,000 steps of 1 ms.

| Question | Result |
| --- | --- |
| Does @3's spec accept a fifth species with z = 0 and P = 0? | Yes. Both definitions parse, and every host check (domain, ledgers, dissipation) passes on every row |
| Face flux of S against (D_S A/L)(c_sender − c_receiver) | Max relative difference 1.04e-14 (fluxes up to 1e-3 fmol/s) |
| S against the exact linear chain (matrix exponential) | Max error 1.80e-10 mM at 1 ms, 4.50e-11 mM at 0.5 ms: ratio 4.00, second order (ARS(2,2,2)'s explicit part) |
| Ionic fields with S declared against the same world without it | **Bitwise identical**: every ion row of every species-axis field, membrane heat, electrode charge and work, gates, pumps, channels. Only face heat and bath work differ, by S's own diffusion heat and bath supply work |
| Cost of the extra row | Second-run wall times 3.38 s and 3.50 s per 1,000 steps (host checks included; rough, +3%) |

The bitwise result holds for this compiled CPU program. XLA's reduce order over the species axis
is program-specific (v2 §3, prerequisite (c)), so it is reported, not promised (§7, idle claim
3).

### 1.3 Positivity: the trace background

@3 requires every species to be positive at every active cell and finite node:
- the spec: `initial_amount_fmol` is positive per species, in every compartment;
- the domain: `domain_valid` requires amount > 0;
- the transport: `transport` requires c > 0, because μ = RT ln c.

So a species that is "absent" somewhere is declared at a **trace background c_bg > 0** in every
cell, node, bath and replacement template.
- **The references include the trace.** Clearance acts on it too, so it is not a constant to
  subtract. The species' equations are linear (§4.2), so the trace's contribution is an additive
  solution of its own: the response to c_bg in the initial values and at the baths, which stays
  between 0 and c_bg (**S**, maximum principle). Compared quantities are chosen far above it.
- **A guard shows insensitivity to it** (§7): c_bg changed by 10³ moves every compared quantity
  by much less than its tolerance.
- **Rejected:** a positivity-free @3 version. It would be heavy, and μ and the free energy are
  undefined at zero.
- **Underflow.** A node cleared at rate k with no supply decays as e^{−kt}, reaching the smallest
  normal float after kt ≈ 708. At k = 1e-4/s that is 82 days (**S**), beyond any planned run. A
  non-positive amount is refused, never repaired. Nodes joined to a held bath stay at or above
  its c_bg.

**The mean-field limit** (**S**).
- 1 nM in 1 pL is 1e-6 fmol, about 600 molecules; in a 0.01 pL cleft it is about 6.
- The model is a continuum description. Below about 10² molecules per node, the compared
  quantities need coarser nodes or a stochastic treatment, which is out of scope.
- The background, often below one molecule per node, is a continuum trace with no molecular
  meaning.

**The material floor.**
- @3 caps `material_balance_atol_fmol` at 1e-10 fmol per species. That is only 1e-4 relative to
  a 1 nM pool in 1 pL.
- The species therefore declares a species-scale floor: the probe used 1e-20 fmol.
- `surface_pump.ledger_limits` applies the floor per species row and adds
  2.5 ε × steps × that row's own magnitudes. So the species' material ledgers are checked at its
  own scale, not at the ions' scale.

### 1.4 The ownership table

| Field | Owner | Writers (booked in) |
| --- | --- | --- |
| The species' cell amounts (`amount_increment` row) | @3 | @3's step (routes with nonzero coefficients only: none for this species except an S5 bridge, §5.3); turnover (`turnover_produced_fmol`, `turnover_cleared_fmol`); exchange (`exchange_moved_fmol`); replacement events; injection never (it refuses neutral carriers) |
| The species' node amounts (`extracellular_amount_increment` row) | @3 | @3's faces; turnover (`turnover_outside_cleared_fmol`); exchange (`exchange_moved_fmol`) |
| Bath exchange of the species | @3 (`reservoir_supplied`, `reservoir_work_pJ`) | @3's step |
| Operator accumulators and work | Each operator | Itself only |
| The species' identity (catalogue reference) | Declarations, never arrays (§1.5) | – |

**The contract's parts, as used:**
- `ENTITY_WRITES` on the two amount fields, each with its owned accumulators.
- `CONFLICTS_VIEW` in version 1: `volume` and `extracellular_volume` for both operators, plus
  `membrane_area` for exchange. Under the S5 rule that a closer counts as a mask's provider,
  the masks `active`, `outside_active` and `membrane_active` too. §5.5 says why;
  version 1.1 replaces these with `VIEW_READS`.
- No `VIEW_FIELDS`, `CONTROL_FACTORS`, `REPLACES`, `ACCEPTS_WRITES` or `EVENT_REPLACES`: they own
  nothing that another operator writes. Observation is @3's own amount columns.
- **Energy roles** (v2 §1.1): each operator's work fields are declared `WORK_FIELDS`, signed. No
  heat field is declared (§2.4).
- **Parts:** a split part with exact half-steps, kept "split" under an RK4 inner step (as
  injection: they write @3's amounts). They are statically idle with no routes, and a half-step
  at zero rate selects its start state.

### 1.5 Identity

**Where the reference lives.** @3's species spec is strictly `{id, valence}`, so the catalogue
reference cannot sit there. Each operator's declaration lists the species it acts on, with:
- an optional opaque reference, `null` or `{"catalogue": id, "entry": key}` (the S2 population
  form);
- the kind of evidence (catalogue plan, constraint 6).

**How it is used.**
- An operator refuses a species whose reference differs from another operator's declaration of
  it; it reads the other declarations, as lumen@1 reads insertion's.
- The reference goes to the summary and the manifest, never into arrays.
- **Guard (S2's):** changing a reference leaves bindings, jaxprs, the batch signature and
  trajectories bitwise unchanged.

**Generic laws stay generic** (catalogue rule). Production, clearance, secretion and uptake name
no protein. The reference identifies the species, and labelling a law with a protein would be a
new claim.

**Later (open question 3):** a composite-level species-identity block, which would also serve the
ions. The architecture page's "species definition" row (identity, valence, units, compartment
eligibility) is its natural home.

## 2. The laws

Units are @3's: fmol, pL, mM = fmol/pL, s, m. h is the half-step, and c = n/V uses the declared
volume in version 1.

### 2.1 Transport: @3's faces (no new law)

@3's face flux is

    J = (D A/L) · logmean(c_a, c_b) · [ln(c_a/c_b) + z F Δφ/RT] / MOL_PER_FMOL.

For z = 0, since logmean(a, b) = (a − b)/ln(a/b), this is exactly Fick's law,
J = (D A/L)(c_a − c_b). The probe measured it to 1.0e-14 relative (§1.2).

**The diffusivity.** It is declared per face and per species. It is the **effective** D: free
diffusivity reduced by tortuosity and hindrance. A FRAP-measured D is such an effective D; an
FCS-measured local D is the free one (§6). With no binding in version 1, the face carries the
effective D.

**Heat.** The face's heat is @3's `face_dissipated_energy_pJ`:

    RT · W · ln(c_a/c_b)² ≥ 0,   W = (D A/L) · logmean / MOL_PER_FMOL.

It is per face, summed over species. The species' share is therefore not separable, which is
why the energy guard needs a species-only world (§7).

**The far field** is a held bath at c_bg, a Dirichlet boundary. What it absorbs is booked as
`reservoir_supplied` with μ_b × supply.

### 2.2 `scheduled_species_turnover@1`: production and clearance at nodes

**Declaration.** Routes, each with:
- a species (neutral, declared in @3);
- a node: a cell, or a finite outside node. A held bath is refused: its composition is held;
- a kind: production (cells only) or clearance.

**Schedule.** `turnover_controls`, piecewise constant per route:
- production P (fmol/s) or clearance k (1/s);
- changes at exact multiples of dt.

These are per-world control data, never closed-over constants.

**Law, exact over each half-step.** For one node with total production P and total clearance k
on one species:

    n' = n e^{−kh} + (P/k)(1 − e^{−kh})        (n' = n + P h when k = 0),

computed with `expm1`. The bookings are:
- `turnover_produced_fmol` += P h;
- `turnover_cleared_fmol` (cells) or `turnover_outside_cleared_fmol` (nodes) += n + P h − n'.

Several clearance routes at one node combine exactly. They are simultaneous first-order
processes, so the cleared amount is shared in proportion to the rate constants.

**State:**
- `turnover_produced_fmol` [species, cell];
- `turnover_cleared_fmol` [species, cell];
- `turnover_outside_cleared_fmol` [species, outside];
- `turnover_work_pJ` [cell];
- `turnover_outside_work_pJ` [outside];
- `turnover_energy_magnitude_pJ` [cell + outside], the rounding allowance's magnitudes.

**Ledger terms.**
- Local, outside and total each gain (removed − supplied), as injection's do.
- The energy ledger loses Σ work.
- The magnitudes gain the moved amounts and |ΔG| terms.

**Refusals.**
- At the definition:
  - a charged species;
  - a production route on an outside node;
  - a route on a held bath;
  - negative rates;
  - schedule changes off the dt grid;
  - a volume provider or closer (`CONFLICTS_VIEW`).
- At run time: non-finite values, and any amount that would not stay positive (unreachable for
  these closed forms with positive inputs).

### 2.3 `scheduled_species_exchange@1`: secretion and uptake across patches

**Declaration.** Routes, each with:
- a species;
- a patch, whose cell and outside node give the two sides;
- a direction: **export** (secretion, cell → node) or **import** (uptake, node → cell);
- a rate law.

**The rate laws:**

| Law | Direction | Rate | Exact half-step |
| --- | --- | --- | --- |
| `flux` | export | scheduled J (fmol/s), drawn from the cell's pool | moved = J h; refused if the pool would not stay positive (no clipping, as injection refuses) |
| `first_order` | export | k_e n_c (1/s), constitutive export of the pool | moved = n_c (1 − e^{−k_e h}) |
| `first_order` | import | k_u A c_o: k_u is an uptake velocity (m/s, like a permeability), A the declared patch area | moved = n_o (1 − e^{−κh}), κ = k_u A / V_o |
| `saturable` | import | A V_max c_o / (K_M + c_o), with V_max in fmol s⁻¹ m⁻² and K_M in mM | n_o' solves b ln(n_o/n_o') + (n_o − n_o') = a h, with a = A V_max and b = K_M V_o: a fixed number of Newton steps, starting from the first-order step at c_o, with the residual checked (a failed solve refuses) |

**Where the material lands.**
- An export lands in the patch's outside node. A patch on a held bath is refused: secretion
  into a held bath is clearance, and its composition is held.
- An import lands in the cell's inventory: the same species, in the same cell.

**Combining routes.** First-order routes leaving one node combine exactly, shared by rate.
Otherwise routes apply in declared order, and the splitting between them is O(h²) relative to
their rates (§4.3).

**Supply.** A sustained source is production plus export:
- **from the pool:** turnover produces into the cell, and exchange exports from it. A pre-loaded
  pool (secretory granules) is the initial amount alone;
- **at steady state:** the pool reaches P/k_e and the export equals P after about 1/k_e.

The secretory path itself (ER, Golgi, vesicles, transit delays) is roadmap item 9's model. It
would own sub-compartments of this pool and replace the lumped first-order export, keeping the
same export bookings.

**State:**
- `exchange_moved_fmol` [route], with export positive;
- `exchange_work_pJ` [route];
- `exchange_energy_magnitude_pJ` [route].

The ledger terms scatter the moved amount to the route's cell (local) and node (outside) with
opposite signs, and the total gains nothing.

**Refusals.**
- At the definition:
  - a charged species;
  - a patch on a held bath;
  - an import law with a flux;
  - a non-positive K_M, V_max or k_u;
  - schedule changes off the dt grid;
  - `CONFLICTS_VIEW` (`volume`, `extracellular_volume`, `membrane_area`) and closers.
- At run time: a supply shortfall, a failed saturable solve and non-finite values.

### 2.4 Free energy and heat, law by law

The species' free energy is @3's chemical term restricted to its own rows,

    G_s = RT Σ_nodes n_s (ln(n_s/V) − 1),

against its anchors at the declared volume. That is `surface_tissue.balances`' expression
(**S**: per species, so a protein-scale change is never computed as a difference of ion-scale
sums).

**The adapter addition.**
- The adapter has `chemical_free_energy_pJ` for cells, summed over species, and nothing for
  outside nodes.
- It gains @3's per-node chemical term for both node kinds, restricted to declared species rows.
  That is new code beside the existing function, which stays as it is. No existing program calls
  it, so crossrev stays identical.
- **Sequenced after S5a,** which owns the adapter now.

| Process | Owner of the booking | Energy booked | Sign |
| --- | --- | --- | --- |
| Face diffusion | @3 | Face heat RT W ln²(c_a/c_b) | ≥ 0 |
| Bath exchange | @3 | Reservoir work μ_b × supply | signed |
| Production | turnover | Work W = ΔG_s(cell): the synthesis machinery supplies the new material's free energy | signed |
| Clearance | turnover | W = ΔG_s(node): the removed material carries its free energy to an external sink, as a held bath's supply does | signed |
| Secretion | exchange | W = ΔG_s(cell) + ΔG_s(node) | signed |
| Uptake | exchange | W = ΔG_s(node) + ΔG_s(cell) | signed |

**Why work, not heat.**
- A first-order law can run uphill in the 1 mM reference convention. For example, removing
  material where c < 1 mM raises G (**S**).
- The dissipation check refuses a decreasing heat element.
- So these laws declare signed work and no heat. Their real metabolic cost and dissipation
  (synthesis, trafficking, endocytosis, proteolysis) lie outside the modelled inventory: a
  declared limit.
- **Later:** when finite energy pools compose, the same laws can draw on them (§10).

**The energy ledger closes exactly in exact arithmetic:** ΔG = Σ W_ops + W_bath − H_faces.

**Charge.** Neutral species carry no charge, so no law moves image charge. None declares
`BOOKS_AT_VIEW`, and none touches the electrode fields.

### 2.5 Uptake: option (a), and the door kept open for occupancy

**Choice: (a). Uptake is a plain sink in version 1.** It is the first-order or saturable removal
of §2.3 from an outside node into the cell's inventory, with no site state. Receptor binding is
the general site-occupancy primitive that the lead said arrives by another door.

**Why (a):**
- **The targets do not need binding.** Their clearance constants are whole-tissue first-order
  rates (§6).
- **Occupancy has its own sources.** It is general (kinetochore sites, junction docking, surface
  catalysis) and should be designed once, from those sources, not shaped by this consumer
  (D142, D144).
- **The sink is a limit the primitive can be checked against.** The saturable sink is the
  quasi-steady limit of binding with internalisation:

      J = k_int R_T c / (K_M + c),   K_M = (k_off + k_int) / k_on   (**S**).

  So the primitive can later be checked against this sink in that limit, an analytic guard ready
  for it.
- **No site state means nothing to partition or reset** beyond the cell's inventory, which the
  partition and replacement already handle.

**The four requirements, recorded so that version 1 does not close the door:**
1. **Bound and free in one inventory, never a second copy.** A bound pool cannot sit in a node's
   amount, because @3's face law would diffuse it.
   - "One inventory" therefore means **one material ledger**:
     - the free amount stays in @3's inventory;
     - the bound amount is state on the site's owner;
     - binding and release are booked transfers between the two, as `exchange_moved_fmol` is.
   - Version 1's import routes are the shape the primitive's internalisation step would write
     into.
2. **Sites are state on a membrane domain or contact, with one owner.** `membrane_entity_state`'s
   populations (S2) are the natural owner: site abundance is a population's abundance, with its
   catalogue reference.
3. **Accessibility separate from stoichiometry.** Accessible sites are the stoichiometric sites
   times an accessibility state, a factor that multiplies, as availabilities do. The kinetochore
   review found sites left empty against a free pool about tenfold larger, which a naive
   mass-action occupancy over the stoichiometric sites cannot reproduce
   ([PAPER_REVIEW_KINETOCHORE_COUNTS.md](PAPER_REVIEW_KINETOCHORE_COUNTS.md)).
4. **Partition at division and reset at replacement, by declared rules.** S5's population map
   splits by a_k; templates declare the newcomer's occupancy.

**What version 1 must not do:** add binding state to these operators or name a receptor. The
primitive replaces the sink as a new law ID, and transport is unchanged.

### 2.6 Limits of version 1 (declared)

- **Neutral species only** (§3).
- **Fixed volumes and areas** (§5.1, §5.5).
- **Rates are scheduled, not regulated.** A regulatory input (GRN, signalling) would arrive as
  a control factor or a new law, not as an edit to these.
- **Effective diffusivity, no hindered-binding dynamics.**
- **No extracellular catalysis.** That is the granzyme K review's item 2, a separate feature.
- **No ECM entity** (its item 5).
- **No convection.**
- **A continuum** (§1.3).

## 3. Charge: neutral

**Decision.** A secreted species has valence 0 in the field solve and in transport. Its net
charge, which depends on pH and is often not an integer, is catalogue metadata only.

**Reasons:**
1. **Electroneutral release.** Exocytosis releases vesicle content with its counter-ions, so the
   release carries no net current. Booking a charged release would need a counter-ion carrier
   rule (which ions, from which side), an arbitrary new declaration that injection needed only
   because an electrode really does carry current.
2. **Magnitude** (**S**). 1 µM at |z| = 10 is 10 µM of charge equivalent against about 150 mM of
   ions, 7e-5. At 1 nM it is 7e-8.
3. **Exact zeros.** With z = 0 the species adds exact zeros everywhere the field sees it:
   - to `_species_sum`'s ordered charge sums (+0.0);
   - to the face Laplacian's conductance Σ z² W;
   - to the drift flux;
   - to the moved charge of the global-charge ledger.

   It touches neither the electrode ledger nor `capacitor_change`'s exactness conditions
   (valences of magnitude 0, 1, 2, 4 or 8 make z·n exact). The probe saw every ionic field
   bitwise unchanged.
4. **The spec and the step's domain exclude real protein charges.**
   - @3 admits integer valences in [−8, 8].
   - Every active route refuses |z F ΔV / RT| > 50, whatever its permeability
     (`surface_transport`, `MAX_ABS_X`). At 310 K that bounds |z| × |ΔV| by 1.34 V: |z| ≤ 16 at
     80 mV and ≤ 13 at 100 mV (**S**).

**Numerical consequences.**
- **Field inputs: none.** The species' laws provide no capacitance, area or mask (`FIELD_INPUTS`).
  So:
  - no field refresh;
  - **the 64-node cap does not apply to them, charged or neutral.** It bites only when they are
    composed with S2–S5 field-input providers, whose worlds stay at 47 nodes or fewer;
  - the floating-component refusal of field-input providers does not apply either.
- **The field-solver interface is untouched.** The capacitor, IMEX and offset solves never see
  the species, because its row of the face Laplacian is zero.
- **What it does inherit:** every extracellular node that resolves a gradient is a dense field
  node of @3. That means n³ refactorisation per step and the 2,048-node bound of the dense IDs.
  - Gradient resolution is therefore bounded by the dense field, not by anything here.
  - Version 1's calibration worlds are one-dimensional or radial reductions of about 100 nodes
    or fewer (§4.4, §6).
  - Two-dimensional sheets of 10⁴ nodes need the interface's sparse IDs (its §6.1).

**Later (open question 7):** an **electrophoretic drift valence**, a transport-only property.
Drift W z_eff F Δφ/RT would act on the face's existing potentials, without the species' charge
entering the field. That is one-way coupling, consistent with electroneutral pairing with
counter-ions. Its effective valence would need a screened-mobility source.

## 4. Numerics

### 4.1 Scales

| Quantity | Range | Source |
| --- | --- | --- |
| Free D, protein-scale | 1e-11–1e-10 m²/s (10–100 µm²/s) | brief; FCS: BMP2b 46, Chordin 59 µm²/s (Pomreinke 2017) |
| Effective D in tissue (FRAP) | about 1e-13–1e-11 m²/s | BMP2b 2.0–2.6, Chordin 6.0–7.3 µm²/s (Pomreinke 2017) |
| Clearance k | about 1e-4/s (half-lives of about 2 h) | BMP2b 8.9e-5/s, Chordin 9.6e-5/s (Pomreinke 2017) |
| λ = √(D/k) | about 150 µm for BMP2b's FRAP D (**S**) | – |
| Formation time | about 1/k to several 1/k: 3 h for BMP2b; 60 min observed mid-formation | – |
| Steps at 1 ms | 3.6e6 per simulated hour; 1e5–1e7 for minutes to hours | – |

### 4.2 The explicit and IMEX paths

- **IMEX (ARS(2,2,2) or Euler).** Face diffusion is explicit and drift implicit
  (`numerics/surface_imex`). With z = 0 the species has no implicit part.
  - Its update for linear diffusion dc/dt = −K c + b is, per step (**S**),

        c' = (I − dt K + ½ dt² K²) c + dt (I − ½ dt K) b,

    since ARS(2,2,2)'s explicit weights give (1 − δ)γ = ½.
  - It is second order: the probe measured a ratio of 4.00.
- **Positivity** (**S**).
  - K has a positive diagonal and non-positive off-diagonal entries. The update's matrix is
    entrywise non-negative when dt (K_ii + K_jj) ≤ 2.
  - @3's explicit-rate bound already enforces dt · 2 max_i K_ii ≤ 1 for the fastest species,
    the ions, a fortiori for the species.
  - So the trace background never goes non-positive under transport. The Euler variant's I − dt K
    needs dt K_ii ≤ 1, which holds as well.
  - The probe ran six decades (1e-3 against 1e-9 mM) with no refusal.
- **The species never sets dt.** @3's bound is 2 max Σ D A/(L V) over species. The species' D is
  20 to 20,000 times the ions' smaller, so the ions bind first. For a 10 µm cubic node at
  D = 1e-10 the species alone would allow 83 ms (**S**).
- **RK4 reference runs** integrate the species with everything else. Their steps (2.5–100 µs)
  make species timescales unreachable, so RK4 guards use compressed worlds (§4.5).

### 4.3 Splitting and the exact half-steps

The operators' parts are exact closed forms over each half-step, placed symmetrically around
@3's step (Strang). The splitting error is O(dt²) in the product of their rates and the
transport rates:
- at k = 1e-4/s and 1 ms, (k dt)² ≈ 1e-14 (**S**);
- a compressed guard world (k = 1/s) gives 1e-6, which the dt study measures (§7).

An idle half-step (rate 0) selects its start state, and a statically idle operator (no routes)
is skipped.

### 4.4 Cost

The cost is steps × nodes. The species adds one row to @3's per-species work, and nothing to the
dense node-space work, which dominates at scale ([field-solver note](FIELD_SOLVER_INTERFACE_DESIGN.md)
§1).
- **One CPU core** (v2 §3, measured): 1.7 ms per step at 14 field nodes, 7.7 ms at 254 and
  76 ms at 825.
- **So a simulated hour** is about 2–3 h of CPU at 50–100 nodes and about 8 h at 254 (**S**).
- **The probe's +3%** is for one species row on a small world, with host checks included.

### 4.5 The 30-minute rule

Guards that need a steady state or a formation transient use **compressed worlds**: small chains
or rings with k of about 1/s and D chosen so that λ spans 3–5 nodes. They reach the steady state
in about 5 s simulated (5,000 steps, seconds of CPU).

**Justification** (**S**): the species' equations are linear, with constant coefficients at
fixed volumes, and decoupled from the ions. The probe showed the ions bitwise unchanged; z = 0,
P = 0. The discrete problem depends only on dt k, dt K_ii and the geometry, so a compressed world
exercises the same discrete operator.

True-parameter calibration runs (hours simulated) are detached tier-3 runs.

## 5. Interactions with existing operators

### 5.1 Water and volume (dilution)

**What comes free:**
- the species is an osmolyte, in water's Σ amounts, though at nM it is 3e-9 of 300 mOsm (**S**);
- water's dilution term −RT N_tot ln(V/V0) includes it;
- @3's transport uses the volumes at the view.

So the species is diluted physically by any flow, and water's ledgers stay exact.

**What does not:**
- uptake's rates depend on c = n/V;
- every operator's ΔG booking depends on V.

With a volume provider, those must read the current volume and book the change of the summed
free energy of the touched entities: @3's chemical term plus water's dilution term (v2 §1.1,
"free-energy owners"). The lumen books this way, and replacement@2 is designed to.

**Version 1** declares `CONFLICTS_VIEW` on both volumes, and is refused beside water and the
lumen.

**Version 1.1, after the volume ledger lands:**
1. **A contract relaxation.** A `VIEW_READS` field with no provider reads its declared value.
   Today `structure_errors` refuses a read with no earlier provider. The relaxation is static and
   lives in `contract.py` and `pump_composite.py`, after S5a; crossrev applies.
2. **Bookings through water's declared endpoint free energy,** the interface replacement@2 is
   building.

### 5.2 Replacement (`scheduled_cell_replacement@1`, and @2 as built for the volume ledger)

**What newcomers carry.** The event swaps every species:
- the occupant's pool leaves as waste (`replacement_removed_fmol`);
- the template's declared pool, or a donor's, is supplied (D139's two routes).

Its free-energy booking uses @3's terms over every species. So the species is replaced with no
new code. Templates must declare a positive amount: the trace, or a loaded pool such as a
granule-loaded newcomer.

**What does not come free: secretion capacity follows the slot, not the occupant.**
- Version 1's rates are per slot and scheduled. A newcomer secretes only if the schedule says so
  from the event time.
- Occupant-indexed rates would read replacement's `occupant_template` (later; open question 9).

**Composition:**
- replacement@1 composes in version 1, since both read declared volumes;
- replacement@2 requires water, so it waits for version 1.1.

### 5.3 Division S5 (the partition)

**What comes free.** `isopotential_partition@1` splits every species' increment by f, and its
anchors are exact fractions (S5 §3.2–§3.3, at 34edc86). A symmetric division is bitwise, with
zero bookings. The species is never a mismatch carrier, because those are charged.

**What does not:**
- **Rates on pending or retired slots.** A pending daughter or a retired parent is padding at
  the view: its anchor reads 0. A law that read the declared layout would "clear" or "secrete"
  phantom content and write a closed slot, which @3's padded-slot domain refuses.
  - Version 1.1 adopts S5's rule: a rate outside a slot's living interval is refused at the
    definition, from the partition's and insertion@2's schedules (as lumen@1 reads insertion's).
  - Version 1 is refused beside any closer.
- **The S5 bridge.** It is an @3 junction with P_s A_j = 2 a D_s^cyt per species (S5 §4.1).
  - The species needs a declared cytoplasmic diffusivity there, among the bridge's declared
    diffusivities.
  - While the bridge is open, the daughters' pools equilibrate through it. That is physical:
    the cytoplasm is continuous.
  - It does not change the bridge's conductance, since z = 0.

### 5.4 The protein catalogue

- **The reference** (§1.5) uses the catalogue plan's opaque form. The catalogue is metadata and
  changes no physics; the guard is S2's.
- **Scope.** The catalogue today covers channels, pumps, transporters and junction channels.
  Extending it to secreted proteins is the granzyme K review's open question 6, for the user.
- **The first consumer.** This feature could be the "first engine model that consumes" the
  catalogue (catalogue plan, stage 4), or membrane populations could be. That is the lead's call.

### 5.5 Composition in version 1

| With | Version 1 | Why |
| --- | --- | --- |
| @3 alone, injection, the k-anion symport | Composes | No view conflict. Injection refuses neutral carriers, so it never moves the species |
| replacement@1 | Composes | Both read declared volumes |
| Water, restricted_cleft_lumen@1/@2 | Refused (`CONFLICTS_VIEW` volumes) | Version 1.1 (§5.1) |
| membrane_entity_state@1 | Refused for exchange (`membrane_area`) | Uptake per area must read the current area; version 1.1 (`VIEW_READS`) |
| Insertion@1/@2, partition, bridge (closers) | Refused (masks) | Version 1.1, under the living-interval rule (§5.3) |
| replacement@2 | Waits | It requires water |

## 6. Calibration targets

Every record was fetched by DOI from Europe PMC (title, authors, journal, volume, issue, pages,
PMID), with no project details sent. The criterion is the advisor's: each target reports D (with
its method), a clearance rate or half-life, and a length, in a stated geometry. That gives three
measured quantities against two free parameters.

**1. Pomreinke AP, Soh GH, Rogers KW, Bergmann JK, Bläßle AJ, Müller P. Dynamics of BMP signaling
and distribution during zebrafish dorsal-ventral patterning. *eLife* 2017;6:e25861.**
[doi:10.7554/eLife.25861](https://doi.org/10.7554/eLife.25861), PMID 28857744, PMC5658070,
CC BY. **The full text was read (Europe PMC).**

- **Values (as stated):**

  | Quantity | BMP2b | Chordin |
  | --- | --- | --- |
  | FRAP effective D (± SEM), µm²/s | 2.0 ± 0.4 (Dendra2), 2.6 ± 0.7 (sfGFP) | 6.0 ± 0.7 (Dendra2), 7.3 ± 3.9 (sfGFP) |
  | FCS local free D, µm²/s | 46 ± 1 | 59 ± 2 |
  | FDAP clearance k1, /s | (8.9 ± 0.1) × 10⁻⁵ (half-life 130 min) | (9.6 ± 0.3) × 10⁻⁵ (120 min) |
  | 50% of maximum at 60 min, from the source | about 30–40 µm | about 50–60 µm |

  - The authors attribute the FRAP–FCS gap to binding to immobile extracellular molecules.
  - The source is a clone of 50–75 cells transplanted at sphere stage (5–5.5 hpf). The authors'
    model blastoderm is 300 µm.
- **What it tests.** Time-dependent formation, far from steady state: 60 min against 1/k ≈ 3.1 h.
  - D and k are measured independently, and the normalised profile does not depend on the
    source's production rate (**S**). So the predicted half-maximum distance at 60 min is a
    genuine prediction, for two species with different D and similar k.
  - It also separates the two diffusivities. Version 1 must carry the FRAP D: the FCS D would
    spread the profile over √(D t) ≈ 400 µm in an hour, wider than the embryo (**S**). The gap is
    the occupancy door's quantity (§2.5).
- **Geometry.** A radial reduction (shells as finite nodes, face areas 4πr², volumes 4πr² Δr)
  around a spherical source.
  - @3's faces accept those areas and volumes, so the radial finite-volume scheme needs no new
    code (**S**).
  - Each shell faces the cells within it, as the probe's chain does. A finite node facing no
    membrane has not been tried.
  - The registration fixes the clone radius, the extracellular fraction and the start of
    secretion before any run.
- **First target.**

**2. Kicheva A, Pantazis P, Bollenbach T, Kalaidzidis Y, Bittig T, Jülicher F, González-Gaitán M.
Kinetics of morphogen gradient formation. *Science* 2007;315(5811):521–525.**
[doi:10.1126/science.1135774](https://doi.org/10.1126/science.1135774), PMID 17255514.
**Record verified.**

- **Access.** The abstract names the measured parameters: production rate, effective
  diffusion coefficient, degradation rate and immobile fraction, for Dpp and Wingless in the fly
  wing. It gives no values. The publisher's page returned 403, so the values must be read before
  registration.
- **What it tests.** The **steady-state** analytic limit λ = √(D/k) at biological scale, in the
  wing disc's epithelial sheet. D and k come from FRAP and λ from the steady profile, for two
  species in one tissue. The immobile fraction is a second pointer to the occupancy door.

**3. Müller P, Rogers KW, Jordan BM, Lee JS, Robson D, Ramanathan S, Schier AF. Differential
diffusivity of Nodal and Lefty underlies a reaction-diffusion patterning system. *Science*
2012;336(6082):721–724.** [doi:10.1126/science.1221920](https://doi.org/10.1126/science.1221920),
PMID 22499809, PMC3525670. **Record verified.**

- **Access.** The abstract states that Nodals have a shorter range than Leftys and similar
  clearance kinetics, and that Leftys have a higher effective diffusion coefficient
  (gradients, pulse labelling and FRAP in zebrafish embryos). It gives no values. Europe PMC's
  full text returned HTTP 500 twice, and PMC served a captcha.
- **What it tests.** **Per-species diffusivity** in one geometry with shared clearance. The range
  ratio should follow √(D ratio) (**S**). This checks the per-species face diffusivity directly.

**Considered, not chosen: Yu SR, Burkhardt M, Nowak M, Ries J, Petrášek Z, Scholpp S, Schwille P,
Brand M. Fgf8 morphogen gradient forms by a source-sink mechanism with freely diffusing molecules.
*Nature* 2009;461(7263):533–536.** [doi:10.1038/nature08391](https://doi.org/10.1038/nature08391),
PMID 19741606. **Record verified.**
- The abstract gives FCS of single molecules (a free D) and a sink by receptor-mediated
  endocytosis that shapes the gradient. It gives no numbers, and the paper is not in PMC.
- No independently measured clearance rate is visible here, so it would fit rather than test
  version 1. It serves the occupancy door: free D against a binding sink.

**Rules.**
- **D136, D144.** No target is a reason for a law. The laws are general, and the targets are
  qualification cases.
- **No simulator code is copied.** These are measurements.
- **Registration.** Each target's protocol is registered before its judged run, in G2-Q1's form.
  Tolerances are pinned from the measurement uncertainty and the engine's step terms, and the run
  is made once, from a clean snapshot.

## 7. Guards

**Tier 1.** Every operator ships a tier-1 smoke test under 20 s (the v2 rule).

**Idle: three separate claims.**
1. **Not declared.** Every existing composition's jaxprs, constants and bindings are identical
   under the constants-aware crossrev:
   - the operators are new modules;
   - the adapter addition is new functions that no existing program calls.

   **Promised.**
2. **Laws at zero rate,** or with no routes. The start state is selected, so every field is
   bitwise equal to the composition without the operator. **Promised.**
3. **Species declared but inert, against no species.** **Reported, not promised:**
   - the probe measured the ionic fields bitwise unchanged in its CPU program;
   - under water the species is an osmolyte, so volumes differ physically;
   - the reduce order over the species axis is program-specific.

**Ledgers at the species' own scale:**
- @3's per-species local, outside and total ledgers, with the species-scale floor (§1.3), on host
  and device;
- the operators' terms in them, with their moved amounts in the magnitudes;
- a negative control: a deliberately misbooked accumulator fails the species' row while the ions
  pass.

**Energy:**
- **A NumPy ΔG test per law:** booked work equals the exact change of G_s, written out
  independently. This is the lumen's remedy, since the IMEX energy bound (2e-3 of the flows) is
  set by the ions.
- **A species-only world.** The ions are quiescent (no pumps or channels, every node at bath
  composition), so the flows and the bound are the species' own, and a booking error shows in
  IMEX.
- **RK4 runs** of a compressed world, whose energy bound has no solver tolerance.

**Analytic limits** (independent NumPy references, written from Appendix A, not from engine
code):

| Limit | Check |
| --- | --- |
| Fick identity | The face flux equals (D A/L) Δc to rounding (the probe: 1e-14) |
| Transient chain | Against the matrix exponential, the observed order about 2 at 1, 0.5 and 0.25 ms (the probe: 4.00) |
| Steady gradient with decay | **The discrete-chain steady state** against the engine, to its tolerance. With node spacing h and uniform clearance k, c_i = A r^i + B r^{−i}, where r + 1/r = 2 + k h²/D, with A and B from the source flux and the bath's c_b (**S**) |
| The continuum limit | The fitted decay length tends to λ = √(D/k) as h/λ → 0, with error O(h²) (**S**) |
| Turnover | Closed form n(t) = n0 e^{−kt} + (P/k)(1 − e^{−kt}) |
| Uptake | First-order, exponential; saturable, the implicit closed form |
| Mass balance | produced − cleared − bath absorbed = Σ Δn, per species |

**Positivity:**
- a stiff-front world (source 1e-3 mM into a 1e-12 mM trace) at the planned dt, with no refusal;
- background insensitivity (§1.3);
- the refusal of an export flux beyond the pool, with the prior state kept bitwise.

**Restart and vmap:**
- restart at, before and after a schedule change, and through a written snapshot in a fresh
  process: bitwise;
- vector-window batches mixing per-world rates, K_M, V_max and k_u: each world within 1e-12 of
  its scalar run, and bitwise against the reversed batch;
- different route structures refused by the batch signature, which carries the static route
  shapes.

**The constants-aware crossrev** (D148, "what crossrev compares"). It compares the jaxprs of the
checked step, right-hand side and device row checks, with scalar constants printed as literals;
the dtype, shape and SHA-256 of every closed-over array; and the initial state, layout, controls
and device-check constants.
- **For the new operators:** per-world rates and parameters must be layout or control arrays
  (bindings), never closed-over constants, and the crossrev's records show it.
- **For existing compositions:** identical.

**D148.** No in-place change to shared qualified code is proposed: the adapter gains functions,
and nothing existing changes. If implementation finds that a shared function must change (the
adapter's chemical term, say), D148's four criteria apply, fix against no fix, with the stop rule
written first.

**Gates:** tier 1 and tier 2 before landing (AGENTS.md); the calibration runs are tier 3.

## 8. Timescales: keeping the door open for long-time modes

Nothing is built for months (D150). The design keeps the door open in four ways:
- **The species is ordinary slow state in the inventory.** A coarse mode (D135's projective C,
  quasi-steady B, stationary E) sees it as it sees ion amounts, with no special case.
- **Its laws are exact over any step.** Production, clearance and first-order transfer are
  closed forms, so a coarse step changes nothing in them. The saturable solve is the exception,
  and it has its own residual check.
- **The species never sets dt; the ions do** (§4.2). A mode that makes the electrical state
  algebraic (B) frees the step for slow inventories without any change here.
- **The stationary analysis** (`stationary_continuation_analysis@1`) already treats cell and
  finite extracellular amounts as dynamical fields. The operators' rates would enter its
  right-hand side only after the composite admits coupled rates on inner fields; today
  injection's are left out by design. That is a door, not a build.

## 9. Effort and order of work

| Part | Agent-days |
| --- | --- |
| Adapter addition (per-node, per-species chemical term) and a `core` definition helper (adds an inventory species: trace, per-face D, impermeance, floor), with tests; after S5a lands | 0.5 |
| `scheduled_species_turnover@1`: spec, schedule, exact half-steps, bookings, refusals, smoke and compiled runs | 1.0 |
| `scheduled_species_exchange@1`: four rate laws, the saturable solve, bookings, refusals, smoke and compiled runs | 1.5 |
| Guards: NumPy references (Appendix A), species-only and RK4 energy worlds, positivity, restart, vmap, crossrev, tier gates | 1.5 |
| Calibration: Pomreinke's radial world, development runs, protocol registration, the judged run (detached) | 1.5, plus about 2–4 CPU hours per 60–75 min run |
| **Version 1 total** | **6 (range 5–7.5)** |
| Version 1.1: the `VIEW_READS` fallback and bookings at the view (water, lumen, areas) | 1.0, after the volume ledger |
| Version 1.1: closers, the living-interval rule and the bridge's species diffusivity | 0.5–1.0, after S5a and S5b |

**Order:**
1. the adapter addition and helper;
2. turnover;
3. exchange;
4. guards;
5. calibration.

Each step lands behind its tier-1 tests. Long runs go through `scripts/run_detached.sh`.

**Sequencing against the plan.** This is promoted now (D150), but it touches no file of the
volume ledger, S5a or checkpoint continuity, except the adapter addition, which waits for S5a.

## 10. Open questions

**For the lead:**
1. **The ownership choice:** one inventory (@3's species axis), not a separate inventory operator
   (§1.1). Confirm.
2. **The trace background** as a declared requirement, rather than a positivity-free @3 version
   (§1.3).
3. **Identity:** on the operators' declarations now, or a composite-level species-identity block
   that ions could use too (§1.5)?
4. **Uptake: option (a)** is chosen, with the four occupancy requirements as the door (§2.5).
   Confirm that the occupancy primitive's design owns them.
5. **Version 1's refusals** (water, lumen, membrane areas, closers) and the order of version 1.1
   against the volume ledger and S5a/S5b (§5.5, §9).
6. **The first catalogue consumer:** this feature or membrane populations (§5.4)?

**For the user:**

7. Is an **electrophoretic drift valence** (transport-only) wanted later (§3)?
8. **Calibration access.** Is institutional access available for Kicheva 2007 and Müller 2012?
   Their values could not be read here. Pomreinke 2017 is the first target either way (§6).
9. Should **secretion capacity follow the occupant** (cell type) rather than the slot after a
   replacement (§5.2)?
10. **Catalogue scope:** should it extend to secreted proteins (the granzyme K review, question
    6)?
11. Should the laws later **draw their energy from finite energy pools** (ATP for synthesis,
    trafficking, endocytosis), making their work a metabolic cost (§2.4)?

## Appendix A. Equations for the independent references

The references are written from these equations, not from engine code. Units are @3's (fmol,
pL, mM, s, m); κ_f = D_f A_f / L_f is in pL/s (m³/s × 10¹⁵).

**Nodes and faces.** Finite nodes i have volumes V_i. A held bath b is fixed at c_b.

    dn_i/dt = Σ_f∋i κ_f (c_j − c_i) + P_i − k_i n_i + Σ_routes(i) (± moved rates),   c = n/V.

**Discrete chain.** N equal nodes with spacing h, a source flux J into node 0, and node N − 1
joined to a bath at c_b. With uniform clearance k, the interior steady state solves
κ(c_{i+1} − 2c_i + c_{i−1}) = k V c_i, which is homogeneous in c. With r + 1/r = 2 + kV/κ and
κ/V = D/h², the general solution is A r^i + B r^{−i}. A and B follow from the two end equations:
κ(c_1 − c_0) + J = k V c_0, and the bath face's κ(c_b − c_{N−1}). Its continuum limit is
e^{−x/λ}, λ = √(D/k).

**Exchange.**
- Export at flux J: Δn_c = −J h, Δn_o = +J h.
- First-order export: Δn_c = −n_c(1 − e^{−k_e h}).
- First-order import: κ_u = k_u A / V_o, Δn_o = −n_o(1 − e^{−κ_u h}).
- Saturable import: b ln(n_o/n_o') + (n_o − n_o') = a h, with a = A V_max and b = K_M V_o.

**Free energy.** G_s = RT Σ n (ln(n/V) − 1) per node, with RT = 2.577 pJ/fmol at 310 K.
- Every law's work is W = ΔG_s, summed over the nodes it touches.
- Face heat is RT κ (c_a − c_b) ln(c_a/c_b) per unit time.
- Bath work is μ_b × supply.
- The energy ledger closes as ΔG_s = W_ops + W_bath − H_faces.
