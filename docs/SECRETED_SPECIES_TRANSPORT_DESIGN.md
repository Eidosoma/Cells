# Secreted-species transport (design)

**Status: accepted by the lead with the advisor, 13 November 2026 (merged at ffc985a). Version 1
code: milestones 1 and 2 landed on main, 14 November 2026 (merge bbbc922), with the lead's
rulings at milestone 1 in §12. Development status: no judged run. Milestone 3 on the branch: the
closed-form development run and a PROPOSED protocol, not registered (§12.2).** The main choices stand: one inventory in @3 as neutral species
rows, uptake as a plain sink (a), and identity on the operator declarations. The lead's
pre-code checks (probes 2 to 5) were run the same day. Their results, the amendments they bring
and the lead's rulings are in §11:
- replacement rates belong to the occupant;
- the first acceptance is numerical qualification;
- a face diffusivity is the effective (FRAP) kind;
- the energy guards of record are the species-only world and a NumPy ΔG test per law, because
  the shared bound is blind to the species at µM–nM;
- guard worlds start from a pre-formed profile, a resolved switch-on. A switch-on from the trace
  is transported exactly, but the host energy ledger refuses it. In a mixed world its onset
  energy booking is a known limit, so production worlds should start resolved too;
- RK4 with a diffusing species is guarded, not refused;
- version 1 refuses a donor copy with different route values, the stationary analysis on the
  composite, and worlds of more than 7 species.

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
  Nothing is built for them now.

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
- The [S5 design](CELL_DIVISION_S5_DESIGN.md), on main since 3480082. It was first cited at
  34edc86 on the S5 branch.
- The [protein catalogue plan](PROTEIN_CATALOGUE_PLAN.md).
- The [field-solver interface](FIELD_SOLVER_INTERFACE_DESIGN.md).

**Evidence and log:** `/mnt/workspaces/Cells/secreted-species-20261113-01/` (HANDOFF.md; the
probe of §1.2 and probes 2 to 5 of §11). **S** marks our arithmetic or interpretation, as in the
division design.

## 0. Summary

1. **One inventory.** A secreted species is one more row of @3's species axis, with valence 0,
   zero membrane and junction permeability, and its own diffusivity on every face. @3 owns its
   amounts, as it owns the ions'. There is no second copy, so the split that
   `network_reactions@1` makes does not arise (§1.1).
2. **Transport needs no new law.**
   - @3's face law carries the species. For z = 0 it is Fick's law exactly (§2.1).
   - Held baths are its far-field sinks, already booked as reservoir supply.
   - **The probes** (§1.2, §11) measured this on the engine as it is:
     - the definition parses, and the face flux equals (D A/L) Δc to 1.0e-14 relative;
     - every ionic field is bitwise unchanged by the declared species, in every probed path:
       scalar runs, a vector batch, restart and replacement. That holds in those CPU programs;
     - around a held sphere, the engine matches the exact solution of its finite-volume system
       to 4.4e-7 of c0 at 1 ms, second order in dt (ratios 4.02 and 4.01);
     - that solution converges to the closed forms as the shells refine (observed orders 1.58
       and 1.84). The gap's size is the declared face geometry's (NumPy, §11.3).
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
   so its contribution is an additive solution bounded by c_bg (§1.3). Probe 3 measured it at
   0.947 times the trace.
7. **Version 1 is transport on a static tissue** (§5.5). Its operators refuse volume providers
   (water, the lumen), membrane-state areas and activity closers. Version 1.1 lifts these after
   the volume ledger and S5a land; the contents themselves already compose (§5). Version 1 also
   refuses these, by the lead's rulings (§11.5):
   - a donor copy whose route values differ from the slot's;
   - the stationary analysis on the composite;
   - worlds of more than 7 species.
8. **The guards of record** (§7, §11.4).
   - **Energy.** The shared IMEX energy bound is the ions' and cannot see the species' bookings
     at µM–nM: it is 1.7 to 1,721 times the species' whole free-energy change. So the energy
     guards of record are a species-only world and a NumPy ΔG test per law, and the operators'
     docstrings say so.
   - **Guard worlds start from a pre-formed profile,** a resolved switch-on. A ramped source is
     not admissible until a probe measures it.
     - A switch-on from the trace is transported exactly. But its first step books the face heat
       2.5–4% off (30% at dt·K_ii 0.30).
     - Under ARS that is 1–9% of the step's own flows, so the host energy ledger refuses it at
       every step size probed (dt·K_ii 0.005 to 0.30).
     - Probe 5 confirmed this cause; its size is smaller than first inferred.
   - **A known limit.** In a mixed world the same onset booking is a few percent off and passes
     unseen under the ions' bound. The species-only world and the NumPy ΔG tests certify the
     laws, and production worlds should start resolved too (§2.6).
   - **RK4** with a diffusing species is guarded, not refused. From a pre-formed profile it is
     exact to rounding (§4.2).
9. **Calibration:** Pomreinke et al. 2017 (BMP2b and Chordin; values read) first; Kicheva et al.
   2007 and Müller et al. 2012 (records verified; full text not readable here) (§6). Its first
   acceptance is numerical qualification against closed forms, not a comparison with the data.
10. **Effort:** about 6 agent-days (range 5–7.5), plus CPU hours for the calibration runs (§9).

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

**The writers' rules** (from a consult with the advisor before writing; the design review itself
is still to come):
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

Probes 2 to 5 extended these checks to every admitted path, and to a radial world against the
closed forms (§11).

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
  by much less than its tolerance. Probe 3 measured it in the radial world: a trace of 10⁻¹²,
  10⁻⁹ and 10⁻⁶ of c0 moved the profile by 0.947 times the trace, linear and below c_bg (§11.2).
- **Rejected:** a positivity-free @3 version. It would be heavy, and μ and the free energy are
  undefined at zero.
- **Underflow and resolution** (amended by the lead, 14 November 2026, at milestone 1; §12). @3
  stores an amount as its declared anchor plus an increment, so it resolves to about ε × its anchor.
  - A node cleared at rate k with no supply follows e^{−kt} until about ε × its anchor, reached at
    kt ≈ ln(1/ε) ≈ 36. Below that it stalls at about one rounding unit of its anchor: it stays
    positive and is never refused (`tests/unit/test_species_turnover.py` measures it).
  - Compared quantities are chosen far above that resolution. kt ≈ 708, the smallest normal float,
    applies only to amounts stored without an anchor.
  - A non-positive amount is refused, never repaired. Nodes joined to a held bath stay at or above
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

These are per-world control data, never closed-over constants. Cell-side routes are keyed by
carrier, not slot (§5.2): a slot's controls follow its occupant, and a newcomer takes its
template's or donor's rates.

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
- `turnover_energy_magnitude_pJ` [cell] and `turnover_outside_energy_magnitude_pJ` [outside], the
  rounding allowance's magnitudes (split by node kind; the lead, 14 November 2026, at milestone 1,
  §12 ruling 3).

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
- **Each half-step returns, as its validity, the finiteness and positivity of every amount it
  wrote**, as injection's `available` does. The composite re-runs @3's domain at the step end
  only when an operator's view follows its split (`_end_domain`), so a second-half write is
  guarded by this flag and the operator's own `domain_valid`, not by @3's.

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

**Whose rates.** Every route's rates and law parameters belong to the cell's carrier and follow
it through replacement (§5.2).

**Where the material lands.**
- An export lands in the patch's outside node. A patch on a held bath is refused: secretion
  into a held bath is clearance, and its composition is held.
- An import lands in the cell's inventory: the same species, in the same cell.

**Combining routes** (amended by the lead, 14 November 2026, at milestone 1; §12 ruling 2).
Routes apply by kind, in a fixed order, run as a palindrome within each half-step:
1. first-order exports, combined exactly per cell and shared by rate;
2. flux exports;
3. first-order imports, combined exactly per node and shared by rate;
4. saturable uptake: routes leaving one node in declared order, one rank each.

The half-step applies each stage for h/2 in this order, the last for h, then the others for h/2 in
reverse. Routes of different kinds do not depend on their declared order. The palindrome makes the
splitting between non-commuting routes (secretion into a node that another route takes up from)
second order: the local error ratio per halving of h measured 6.90, 7.43, 7.71 and 7.85, approaching
8 (`tests/unit/test_species_exchange.py`). This replaces the earlier "otherwise routes apply in
declared order".

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
  - a negative rate (J, k_e, k_u or V_max), and a non-positive K_M (K_M > 0 strictly). Zero rates
    are admitted: they are the idle state (D136) and a swap to a zero-rate template (the lead,
    14 November 2026, at milestone 1; §12 ruling 1);
  - schedule changes off the dt grid;
  - `CONFLICTS_VIEW` (`volume`, `extracellular_volume`, `membrane_area`) and closers.
- At run time: a supply shortfall, a failed saturable solve and non-finite values. As in §2.2,
  each half-step returns the finiteness and positivity of both amounts it wrote as its validity,
  since @3's domain is not re-run after the second half.

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
- **As built** (accepted by the lead, 14 November 2026, at milestone 1; §12 ruling 7): two
  functions per element, `species_chemical_free_energy_pJ(anchor, change, volume, temperature)`
  and its absolute terms, `species_chemical_magnitude_pJ`. With the declared reference as the
  anchor and the increment as the change it is balances' own term; with the current amount as the
  anchor and a moved amount as the change it is that move's exact free-energy change, with no
  difference of bulk terms. The caller selects the species rows and the node kind. The D152
  operator will reuse `species_chemical_free_energy_pJ`.

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
- **At most 7 species per world** (the lead's ruling, §11.5).
  - **The refusal.** The two new operators' definition checks refuse a world with more, and the
    refusal names the cap and its reason. No model changes.
  - **The reason.** Host-side NumPy sums over the species axis switch to pairwise summation at
    8 or more terms. Host checks could then add the species in a different order from the
    device's explicit species-order adds (D148).
  - So version 1 admits at most 7 species until that is checked.
- **The onset energy booking in mixed worlds** (a known limit, the lead's ruling, §11.4).
  - A switch-on from the trace is transported exactly.
  - Under the ions' bound, the species' onset energy booking is off by a few percent and goes
    unseen. The species-only world and the NumPy ΔG test per law certify the laws (§7).
  - Production worlds should also start from a resolved switch-on.
- **No stationary analysis on the composite** (§8).
- **No donor copy whose route values differ from the slot's** (§5.2).
- **No membrane, junction or channel route of @3's for an inventory species** (17c3407, accepted by
  the lead at milestone 1; §12). @3's explicit-rate bound covers every species on faces, but on
  membranes and junctions it bounds only the z²-weighted charge relaxation, so such a species would
  have no material-rate bound at the definition. Both operators refuse it, naming the route.
- **Bridge closure stays refused for inventory species in version 1.1** until neutral species on
  junctions have a material-rate bound (§5.3; a D148 question, §12).

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
  - It is second order: the probe measured a ratio of 4.00, and probe 3's radial world 4.02
    and 4.01 (§11.2).
- **Positivity** (**S**).
  - K has a positive diagonal and non-positive off-diagonal entries. The update's matrix is
    entrywise non-negative when dt (K_ii + K_jj) ≤ 2.
  - @3's explicit-rate bound already enforces dt · 2 max_i K_ii ≤ 1 for the fastest species,
    the ions, a fortiori for the species.
  - So the trace background never goes non-positive under transport. The Euler variant's I − dt K
    needs dt K_ii ≤ 1, which holds as well.
  - The probe ran six decades (1e-3 against 1e-9 mM) with no refusal. Probe 4 ran twelve
    (1e-3 against 1e-15 mM) through the checked step, with no step refused. The runner's host
    energy ledger refuses that start, a booking matter, not positivity (§11.4).
- **The species never sets dt.** @3's bound is 2 max Σ D A/(L V) over species. The species' D is
  20 to 20,000 times the ions' smaller, so the ions bind first. For a 10 µm cubic node at
  D = 1e-10 the species alone would allow 83 ms (**S**).
- **RK4 reference runs** integrate the species with everything else, but under RK4 the face
  electromigration is explicit. Physical faces relax charge in "a few tens of nanoseconds"
  (`surface_imex`'s docstring), and the probe chain's face RC time is about 1 µs (**S**).
  Compressing 1/k does not help, because the ions' face conductance sets the step.
- **Decision (13 November): RK4 with a diffusing species is guarded, not refused.** Probe 3 ran
  the species-only radial world under RK4 at 0.1 ms. No ion diffuses on its faces.
  - **From a pre-formed profile** it passed every host check. It matched the exact discrete
    solution to 6.5e-16 of c0, with an energy residual of 3.2e-14 pJ against RK4's bound, the
    absolute 2e-8 pJ (§11.2).
  - **From the trace** the host energy ledger refused it, at dt·K_ii 0.005. Probe 5 found the
    cause shared with ARS: row 1 fails. Its onset step books the face heat 42% high, 1.6e-4 pJ,
    7,870 times the bound. From step 2 RK4 books to 4e-5 of each step's flows, falling to 1e-13.
    With no relative allowance the onset error never dilutes, so every later row fails too
    (§11.4).
  - **Why guard rather than refuse.** Once the switch-on is resolved, RK4 transports and books
    the species correctly.
    - It is the sharpest reference available: exact to rounding against the discrete solution,
      with no solver tolerance on energy.
    - An unresolved onset is refused loudly by the ledger, not passed silently.
    - A refusal would lose that reference, and the guard-world rule (§7) already excludes what
      the ledger refuses.
  - **Scope.** Those rows had no ion diffusion on any face. RK4 with ion-carrying faces is not
    covered here, and it needs nanosecond steps.
- **So RK4 guards use two worlds,** both started from a pre-formed profile. The second was
  proposed in this round and accepted (§11.5, item 9):
  - **a face-free world** for the operators' work: a passive cell, its finite node joined to it
    only by a membrane patch, and a held bath, with compressed rates within @3's RK4 step limit
    of 100 µs;
  - **the species-only radial world**, with zero ion face diffusivity, for transport and the
    face heat.

  There, the energy is checked with no solver tolerance. The alternative remains ion face
  diffusivities small enough that the face RC time is resolved, as the cleft fixture's narrow
  access does.

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
new code. Checked in `core/cell_replacement_spec.py`:
- a template must name every declared species' amount, each positive: the trace, or a loaded
  pool such as a granule-loaded newcomer;
- a donor copy takes the donor's amounts, the species' included;
- a template's route values replace only routes the slot already has, by a positive value, so
  a newcomer cannot make the species permeant.

**Rates belong to the occupant: carriers have identity, slots are storage** (S5's rule; the
lead's decision of 13 November, replacing this note's earlier "rates follow the slot").

**The rule:**
- The cell-side rates are properties of the carrier that occupies a slot: production, clearance
  of the cell's pool, export (secretion) and import (uptake), with their law parameters (k_e,
  k_u, V_max, K_M).
- **Founders.** Rates are declared per founder carrier.
- **Isolated template.** A newcomer takes the rates its template declares. The operators'
  declarations key them by replacement template ID, beside the template's amounts.
- **Donor copy.** A newcomer takes the donor's rates at the event time, before any event at that
  time (replacement's own rule for the donor's amounts). In version 1 a donor copy is admitted
  only when its declared route values, ion and secretion, equal the slot's (the lead's ruling,
  below).
- **Never from the previous occupant.** A slot's earlier rates never carry over to the
  newcomer.
- **Daughters** of an S5 partition are new carriers with their own declared rates.
- **Time schedules are keyed by carrier ID.** A carrier's schedule applies while it occupies a
  slot.
- **Node-side clearance stays per node.** An outside node is environment, not a carrier.

**How version 1 implements it, with no new state.**
- Replacement@1's events are prescribed, so the occupant of every slot at every step is known at
  the definition.
- Each operator builds each slot's rate controls from its occupants' declared rates, switching at
  the event step. These are per-world control data, recomputed from the definition at a restart
  (R7).
- Triggered lifecycles (milestone 2) will not know their occupants at the definition. Their
  rates move into state written at birth, by an event map that reads the lifecycle records.

**Guard: the swap.** A founder with nonzero rates is replaced:
- by a template with other rates, including zero: the slot's controls switch to the template's
  rates exactly at the event step, and the previous occupant's rate never applies after it;
- by a donor copy whose route values (ion or secretion) differ from the slot's: refused at the
  definition (the lead's ruling, below);
- by an admitted donor copy: the slot takes the donor's rates, which equal its own, so its
  controls are unchanged across the event.

The guard includes a restart across the event. Probe 2 checked the part that exists today:
replacement@1 swaps the species' pool (§11).

**A difference, settled for version 1 (the lead's ruling, 13 November).** Replacement@1's own rule
for **ion route values** in a donor copy is "the slot's own, or a declared route-only template's",
not the donor's (D139). The rule above gives the donor's rates for these laws.
- **Version 1 refuses a donor copy whose declared route values (ion and secretion) differ from the
  slot's.** The refusal is at the definition.
- In every admitted donor copy the two rules therefore give the same values. D139 is kept, and
  the occupant rule holds.

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
  - **A version 1.1 limit** (the lead, 14 November 2026, at milestone 1). Version 1 refuses an
    inventory species with junction permeability, since @3's explicit-rate bound covers junctions
    only through the z²-weighted charge relaxation. So bridge closure stays refused for inventory
    species until neutral species on junctions have a material-rate bound. That is a D148
    question; the D152 agent's probe C4 is measuring @3's behaviour there.

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
| @3 alone, injection | Composes | No view conflict. Injection refuses neutral carriers, so it never moves the species |
| replacement@1 | Composes | Both read declared volumes |
| The k-anion symport | Waits | It requires water (`REQUIRES`). Its in-step process also makes RK4 run coupled, which refuses split parts kept "split" |
| Water, restricted_cleft_lumen@1/@2 | Refused (`CONFLICTS_VIEW` volumes) | Version 1.1 (§5.1) |
| membrane_entity_state@1 | Refused for exchange (`membrane_area`) | Uptake per area must read the current area; version 1.1 (`VIEW_READS`) |
| Insertion@1/@2, partition, bridge (closers) | Refused (masks) | Version 1.1, under the living-interval rule (§5.3) |
| replacement@2 | Waits | It requires water |

## 6. Calibration targets

Every record was fetched by DOI from Europe PMC (title, authors, journal, volume, issue, pages,
PMID), with no project details sent. The selection criterion, from the pre-writing consult with
the advisor: each target reports D (with its method), a clearance rate or half-life, and a
length, in a stated geometry. That gives three measured quantities against two free parameters.
It is **confirmed for target 1 only**; for targets 2 and 3 it is expected, to be confirmed on
reading.

**1. Pomreinke AP, Soh GH, Rogers KW, Bergmann JK, Bläßle AJ, Müller P. Dynamics of BMP signaling
and distribution during zebrafish dorsal-ventral patterning. *eLife* 2017;6:e25861.**
[doi:10.7554/eLife.25861](https://doi.org/10.7554/eLife.25861), PMID 28857744, PMC5658070,
CC BY.
- **How the values were read (re-read 13 November, at the lead's request).** The whole
  open-access JATS XML was downloaded from Europe PMC (PMC5658070, 281,353 bytes, SHA-256
  250e9c67…bbae). Its sentences were then extracted by text search, not by the fetch tool's
  summary. File and digest are in the evidence folder's `sources/`. The figures themselves were
  not seen. Every value below is a quoted sentence of the text; the earlier extraction's values
  all match.

- **Values (as stated in the text):**

  | Quantity | BMP2b | Chordin |
  | --- | --- | --- |
  | FRAP effective D (± SEM), µm²/s | 2.0 ± 0.4 (Dendra2), 2.6 ± 0.7 (sfGFP) | 6.0 ± 0.7 (Dendra2), 7.3 ± 3.9 (sfGFP) |
  | FCS free D, µm²/s, with the fit's parameters constrained (Figure 4) | 46 ± 1 | 59 ± 2 |
  | FCS free D, freely fitted (20–30% lower) | 35 ± 2 | 50 ± 3 |
  | FDAP clearance k1, /s | (8.9 ± 0.1) × 10⁻⁵ (half-life 130 min) | (9.6 ± 0.3) × 10⁻⁵ (120 min) |
  | 50% of maximum at 60 min post-transplantation, from the source boundary | 30–40 µm | 50–60 µm |

  - The authors measured FCS "in very small extracellular volumes far away from cell surfaces".
    They write that diffusivities "are reduced at the global scale when they move across a field
    of cells".
  - The FRAP fits use "a model with uniform production, diffusion, and clearance", constrained by
    the FDAP k1. **The FRAP D is a model-derived effective D.**
  - The source is a clone of about 50–75 cells transplanted at sphere stage (5–5.5 hpf).
  - **The paper fits a model of the same kind.** It fitted "a gradient formation model based on
    local production, uniform diffusion, and clearance constrained with our measured protein
    half-lives in a realistic three-dimensional zebrafish embryo-like geometry", and found the
    best agreement at D = 4 µm²/s (BMP2b) and 6 µm²/s (Chordin). It also simulated gradient
    formation for 70 min against data at about 70–75 min.

- **Which diffusivity a face carries (declared, at the lead's request).** In version 1 a face
  diffusivity is an **effective** diffusivity, the FRAP kind.
  - With no binding, the face law must reproduce how the whole mobile and reversibly bound pool
    spreads over tissue scales.
  - An FCS free diffusivity is admissible only together with an explicit binding model (the
    occupancy primitive, §2.5), never alone on a face.
  - The two differ about twentyfold for BMP2b (46 against 2.0–2.6 µm²/s, 18–23×) and eight- to
    tenfold for Chordin (**S**).
  - Using the free value would spread the profile over √(D t) ≈ 400 µm in an hour, wider than
    the embryo (**S**).
  - The clearance constant is likewise the whole pool's (FDAP), consistent with an effective D.

- **The first acceptance is numerical qualification, not a biological test** (the lead's check).
  - **Can a version 1 run of this target differ from the closed form? No** (**S**, and probe 2,
    §11):
    - with uniform D and k, a source and fixed volumes, the species' equations are the linear
      diffusion–decay problem;
    - the species is decoupled from the ions (z = 0, impermeant; the ionic fields are bitwise
      unchanged);
    - so the engine's solution is the closed-form or discrete solution, to discretisation error.
  - A comparison with the measured distances would therefore test the diffusion–clearance model
    and the paper's parameters, not the engine, and the paper has already fitted that model
    itself. Running it on the engine would come close to reproducing the paper's own model,
    which is tooling needing the user's approval (D138; D151 keeps that line).
  - **So the first acceptance is registered as numerical qualification.** The engine is checked
    against independent closed-form and discrete references in a radial geometry and a
    non-dimensional regime of this kind (kt below 1, profiles over a few λ). Nothing is compared
    with the paper's data, and its simulation is not reproduced.
  - **The references are textbook solutions, not a reference solution of the paper** (D151):
    - a sphere held at a fixed concentration with first-order decay (the planar Danckwerts form
      through v = r u, **S**);
    - the finite-domain steady state;
    - the exact solution of the same finite-volume system.

    They take none of the paper's data and fit nothing to it.
  - **A biological comparison against this target becomes informative** when the engine's
    model holds something the closed form lacks: cell-resolved uptake geometry, binding and
    occupancy, volume change, or regulation. It is then registered on its own, with the user's
    approval if it reproduces the paper's model.
- **Geometry.** A radial reduction around a spherical source: shells as finite nodes with their
  exact volumes. Each face is declared with the exact spherical-shell conductance between the
  points it joins: area 4π r_a r_b over length r_b − r_a. This is a requirement on the builders
  of radial calibration worlds (accepted by the lead, §11.5, item 8).
  - Planar areas 4πr² at the edges are wrong at first order in Δr/R at the source. They made the
    probes' continuum gap 10 to 12.5 times larger (§11.3, NumPy only, **S**).
  - @3's faces accept those areas and volumes, so the radial finite-volume scheme needs no new
    code (**S**).
  - Each shell faces the cells within it, as the probe's chain does. A finite node facing no
    membrane has not been tried.
  - The registration fixes the clone radius, the extracellular fraction and the start of
    secretion before any run.
- **Standing.** First target, registered as numerical qualification (above). Its biological
  comparison is deferred under D151, not closed.

**2. Kicheva A, Pantazis P, Bollenbach T, Kalaidzidis Y, Bittig T, Jülicher F, González-Gaitán M.
Kinetics of morphogen gradient formation. *Science* 2007;315(5811):521–525.**
[doi:10.1126/science.1135774](https://doi.org/10.1126/science.1135774), PMID 17255514.
**Record verified.**

- **Access.** The abstract names the measured parameters: production rate, effective
  diffusion coefficient, degradation rate and immobile fraction, for Dpp and Wingless in the fly
  wing. It gives no values. The publisher's page returned 403, so the values must be read before
  registration.
- **What it tests.** The **steady-state** analytic limit λ = √(D/k) at biological scale, in the
  wing disc's epithelial sheet, for two species in one tissue. The abstract names the effective
  D and the degradation rate as measured; their method and the measured decay length are to be
  confirmed on reading. The immobile fraction is a second pointer to the occupancy door.

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

**Energy: the guards of record** (the lead's ruling, §11.5):
- **The shared bound is not one.** Under the IMEX solvers it is `ENERGY_ATOL_PJ` +
  `ENERGY_RTOL` × the accumulated heat and work: 2e-8 pJ + 2e-3 × the flows under ARS(2,2,2),
  and 2e-2 under Euler. In a mixed world those flows are the ions'. In probe 2 the bound was 1.7
  times the species' whole free-energy change at µM and 1,721 times at nM (§11.1).
  - **The docstring statement (required).** Each operator's module docstring, and the adapter
    addition's, says: *under the IMEX solvers the shared energy bound is set by the ions' flows
    and is blind to these bookings at µM–nM (bound/change 1.7 to 1,721 in a probed mixed world);
    the species-only world and a NumPy ΔG test per law are the guards of record.*
  - **Under RK4** the bound is the absolute 2e-8 pJ (`ENERGY_RTOL` 0, which the composite takes
    from @3). It is not blind, but RK4 is practical only where no ion diffuses on a face (§4.2).
- **A NumPy ΔG test per law:** booked work equals the exact change of G_s, written out
  independently. This is the lumen's remedy.
- **A species-only world.** The ions are quiescent (no pumps or channels, every node at bath
  composition), so the flows and the bound are the species' own, and a booking error shows in
  IMEX.
  - Its amounts sit well above the energy floor. `ENERGY_ATOL_PJ` is 2e-8 pJ, while a 1e-6 fmol
    pool's energies are only about 1e-5 pJ.
  - So it uses µM-scale amounts in pL nodes: about 1e-3 fmol and energies of about 1e-2 pJ, some
    5 × 10⁵ times the floor (**S**).
  - This is the guard of the face heat. **Measured at milestone 2 (§12.1):** under IMEX it sees a
    booking error only above 2e-3 of the species' total accumulated flows, so its sensitivity to
    one term is that term's share of the flows. A 1% error in the face heat of the radial world
    reached 0.89 of the bound and passed; under RK4's absolute bound it was refused 6.1e4-fold. The
    RK4 worlds are therefore the sensitive guards of the face heat and the operators' work, the
    IMEX species-only world a coarse one, and the NumPy dG test per law the exact one.
- **The guard-world rule: a resolved switch-on, by a pre-formed profile** (the lead's ruling).
  Every version 1 guard world that reaches the host energy ledger starts the species from a
  pre-formed profile, the measured arm. Half the steady profile passes every row under ARS at
  dt·K_ii up to 0.30, the largest probed, and under RK4 at 0.005 (§11.2, §11.4).
  - **A ramped source is unmeasured and not admissible** in a version 1 guard world until a
    probe measures it.
  - A ramp would resolve the switch-on only if each step changed the receiving node's
    concentration by a small factor (**S**). A linear ramp from zero still lifts the first node
    from the trace by many decades in its first step.

  **No bound on dt·D/Δr² is set beyond stability.** Resolved starts passed at every dt·K_ii
  probed, up to 0.30.

  **Why.** A switch-on from the trace is transported exactly (probe 4), but its first step books
  the face heat 2.5–4% off, and 30% off at dt·K_ii 0.30. That is 1–9% of the step's own flows,
  against a bound of 2e-3 of the accumulated flows, so the host energy ledger refuses it at every
  step size probed, dt·K_ii 0.005 to 0.30 (§11.4).
- **RK4 runs** of the face-free world and the species-only radial world (§4.2), from pre-formed
  profiles. Their energy bound has no solver tolerance (`ENERGY_RTOL` 0 for RK4), so they check the
  operators' work and the face heat to 2e-8 pJ.

**Analytic limits** (independent NumPy references, written from Appendix A, not from engine
code):

| Limit | Check |
| --- | --- |
| Fick identity | The face flux equals (D A/L) Δc to rounding (the probe: 1e-14) |
| Transient chain | Against the matrix exponential, the observed order about 2 at 1, 0.5 and 0.25 ms (the probe: 4.00) |
| Held sphere with decay | From a pre-formed profile, the engine against the exact solution of the same finite-volume system and against the finite-domain closed form (steady state plus sine series); the switch-on, through the checked step map, against the Danckwerts form (probes 3 and 4, §11.2–§11.3) |
| Steady gradient with decay | **The discrete-chain steady state** against the engine, to its tolerance. With node spacing h and uniform clearance k, c_i = A r^i + B r^{−i}, where r + 1/r = 2 + k h²/D, with A and B from the source flux and the bath's c_b (**S**) |
| The continuum limit | The fitted decay length tends to λ = √(D/k) as h/λ → 0, with error O(h²) (**S**) |
| Turnover | Closed form n(t) = n0 e^{−kt} + (P/k)(1 − e^{−kt}) |
| Uptake | First-order, exponential; saturable, the implicit closed form |
| Mass balance | produced − cleared − bath absorbed = Σ Δn, per species |

**Positivity:**
- a stiff-front world (source 1e-3 mM into a 1e-15 mM trace) at the planned dt, through the
  checked step map: every step accepted and every amount positive (probe 4: 2,000 steps, none
  refused). The runner's host energy ledger refuses this start (§11.4), so this guard checks the
  domain at every row, not the energy ledger. It expects the anchored-amount stall (§1.3): an
  amount below about ε × its anchor holds positive, and that is not a failure;
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
  - **Version 1 does not admit it on the composite** (the lead's ruling, 13 November). Probe 2
    found that it refuses the composite's ID (§11.1).
  - **Per-species tolerance scaling is required** before trace or nM species use it on plain
    @3. Probe 2's solve there converged in 5 iterations, and S came out at the bath's trace
    (1e-9 mM), the steady state of its initial pulse.
  - **Its Newton test is not scaled per species.** It stops on one absolute correction of
    1e-10 mM per amount (`NEWTON_TOLERANCE`, with `AMOUNT_UNIT_mM` = 1). That is 10% of a
    1e-9 mM trace and 1e-4 of 1 nM.

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
9. **Decided by the lead (13 November):** rates follow the occupant; carriers have identity,
   slots are storage (§5.2). Version 1 refuses a donor copy whose declared route values (ion and
   secretion) differ from the slot's, which keeps D139 and the occupant rule consistent (§5.2,
   §11.5).
10. **Catalogue scope:** should it extend to secreted proteins (the granzyme K review, question
    6)?
11. Should the laws later **draw their energy from finite energy pools** (ATP for synthesis,
    trafficking, endocytosis), making their work a metabolic cost (§2.4)?

## 11. Pre-code checks: results and amendments (13 November)

These are the lead's checks after the design landed. No engine code was changed.
- **Source:** every probe ran from a clean snapshot of b7ac255 (`snapshot-probe2`).
- **Execution:** each probe ran as its own unit through `scripts/run_detached.sh`, on CPU 7 with
  a 3 GB cap. memory.events was all zero for each.
- **Evidence:** scripts, logs and JSON are in the evidence folder, `probe2/` to `probe5/`.

| Probe | Question | Exit, wall time, peak |
| --- | --- | --- |
| 2 (`cells-secreted-probe2`) | Every admitted path; energy-bound visibility | 0, 531 s, 1.79 GB |
| 3 (`cells-secreted-probe3`) | The radial world's refusal, separated; order in dt; trace; RK4 | 0, 361 s, 1.47 GB |
| 4 (`cells-secreted-probe4`) | The closed forms | 0, 132 s, 0.96 GB |
| 5 (`cells-secreted-probe5`) | The cause of the switch-on refusal, row by row | 0, 443 s, 0.68 GB (a first launch stopped at a syntax error in the script at 0 s; its log is kept) |

### 11.1 Probe 2: every admitted path

**The world** is §1.2's chain with five species (four ions and S). It runs as the composite with
no new operators, which equals @3, and also with replacement@1. Each path compares the S world
against the same world without S.

| Path | Result |
| --- | --- |
| A1: scalar runs | Every ion row of every species-axis field, and every other field, bitwise equal over the whole history. Only face heat and bath work differ, by S's own diffusion heat and supply work |
| A2: a vector-window batch of three worlds, with device checks (final states compared) | Ion rows bitwise against the batch without S, the same two fields excepted. The batch is bitwise against its reverse and within 1.7e-15 (relative) of each world's scalar run. The device checks pass, with energy relative at most 6.5e-4 |
| A3: restart at 0.1 s (the S world) | In process and through a written snapshot, the resumed history is bitwise equal to the uninterrupted run's |
| A5: one replacement event | Ion rows bitwise. Besides the two fields, only the replacement free-energy terms differ, by S's share. **S's pool is swapped exactly:** the occupant's 7.505e-10 fmol (the trace) leaves as waste, the template's 1e-4 fmol is supplied, and the pool after the event is 1e-4 fmol |

These hold for the CPU programs probed (§1.2's caveat).

**Three further results:**
- **The stationary analysis refuses the composite's ID** (A4): it "supports
  resolved_pump_tissue@1, resolved_pump_tissue@2, resolved_pump_tissue@3, resolved_pump_water@1,
  resolved_pump_water@2, not resolved_pump_composite@1".
  - On plain @3 (the same world) it converged in 5 iterations, with and without S.
  - The ions agreed within 2.8e-14 mM. S came out at the bath's trace everywhere (1e-9 mM): the
    steady state, to which the chain's initial pulse of 1e-3 mM drains.
  - Its Newton test is one absolute tolerance, 1e-10 mM per amount, for every species (§8).
    Ruling 2 of §11.5 follows.
- **No fixed species counts.** Every path ran the five-species world with no change. No module on
  those paths holds a species-count limit, by a search of the snapshot's source: @3's spec and
  model, the composite, replacement, the batch, the windows, the runner and the stationary
  analysis.
- **The shared energy bound is blind to the species** (part C).
  - In A1's world run for 1 s, the bound at the end was 4.88e-3 pJ: 2e-8 + 2e-3 × 2.44 pJ of
    flows, nearly all the ions'.
  - S's whole free-energy change was −2.90e-3 pJ at µM (1e-3 mM in the first node), so
    bound/change is 1.7.
  - At nM (1e-6 mM) it was −2.83e-6 pJ, so bound/change is 1,721.

**Part B,** the radial world, was refused by the host energy ledger on every solver tried, RK4
included. Probes 3 to 5 find out why.

### 11.2 Probe 3: the radial refusal separated; the order in dt, the trace and RK4

**The world.**
- A sphere of radius R = 10 µm is held at c0 = 1e-3 mM by a bath.
- Shells are finite nodes out to 130 µm: 24 of 5 µm or 60 of 2 µm. Each shell faces a quiescent
  cell through a capacitive patch.
- An outer bath is held at the trace. Decay (k = 1/s) is a face to a 1e-30 mM sink.
- D = 4e-10 m²/s, so λ = 20 µm.
- No ion moves: every patch has zero permeability and every face zero ion diffusivity.
- **A jump start** has every shell at the trace, 1e-15 mM, twelve decades below c0. **A smooth
  start** has half the steady profile.

| Start, shells | Solver, dt | max dt·K_ii | Host checks | Against the exact discrete solution, of c0 |
| --- | --- | --- | --- | --- |
| jump, 2 µm | ARS, 1 ms | 0.30 | refused (energy) | – |
| jump, 2 µm | ARS, 0.1 ms | 0.030 | refused (energy) | – |
| jump, 5 µm | ARS, 1 ms | 0.050 | refused (energy) | – |
| smooth, 2 µm | ARS, 1 ms | 0.30 | pass; energy relative 4.1e-4 | 4.3e-7 |
| smooth, 5 µm | ARS, 1 ms | 0.050 | pass; 6.5e-6 | 4.45e-7 |
| smooth, 5 µm | ARS, 0.5 ms | 0.025 | pass; 1.7e-6 | 1.11e-7 |
| smooth, 5 µm | ARS, 0.25 ms | 0.012 | pass; 4.2e-7 | 2.76e-8 |
| smooth, 5 µm | RK4, 0.1 ms | 0.005 | pass; energy 3.2e-14 pJ | 6.5e-16 |
| jump, 5 µm | RK4, 0.1 ms | 0.005 | refused (energy) | – |

- **The cause is the switch-on, not stiffness.** Jump starts are refused at dt·K_ii from 0.030 to
  0.30, and smooth starts pass at 0.050 and 0.30. A smaller step does not rescue a jump start.
- **Second order in dt:** the smooth 5 µm errors give ratios 4.02 and 4.01.
  - The energy residual relative to the flows is second order too: 6.5e-6, 1.7e-6 and 4.2e-7.
  - It grows with dt·K_ii, reaching 4.1e-4 at 0.30. That is within the 2e-3 bound at every
    smooth start probed.
- **The trace** (smooth, 5 µm, 1 ms).
  - Raising it from 10⁻¹⁵ c0 to 10⁻¹², 10⁻⁹ and 10⁻⁶ c0 moved the profile by 9.47e-13, 9.47e-10
    and 9.47e-7 of c0. That is 0.947 times the trace: linear and below c_bg (§1.3).
  - The agreement with the discrete reference, which carries the trace, stayed at 4.4457e-7, and
    the energy residual at 6.5e-6.
- **RK4.** Its bound has no solver tolerance: 2e-8 pJ absolute.
  - From the smooth start it is exact to rounding.
  - From the jump it is refused, at a dt·K_ii 60 times below the largest passing ARS start.
  - §11.4 measures why, and §11.5 gives the decision.
- **The discrete solution against the continuum** (NumPy, jump start).
  - The steady state differs from the finite-domain closed form by 1.31e-2 of c0 at 2 µm and
    3.66e-3 at 1 µm.
  - The transient near the source (r ≤ R + 3λ, at 0.25 and 0.5 s) differs from the
    infinite-medium form by 1.48e-2 and 4.12e-3.
  - Both ratios are 3.59, an observed order of 1.84.

### 11.3 Probe 4: the closed forms

**(a) The smooth start through the runner,** with every host check enforced, for 6 s at 1 ms.
- **The reference** is the continuum finite-domain solution from the same start: the steady state
  u = (A e^{r/λ} + B e^{−r/λ})/r plus the sine series of v = r u, with eigenvalues D(nπ/L)² + k
  and 400 terms.

| Shell width | Max error, of c0, at 0.5 s and 6 s | Energy relative |
| --- | --- | --- |
| 5 µm (24 shells) | 5.94e-2, 5.79e-2 | 6.5e-6 |
| 2.5 µm (48 shells) | 1.99e-2, 1.94e-2 | 1.6e-4 |

- **The observed order:** the ratio is 2.98 at every observed time, an order of 1.58 from 5 to
  2.5 µm. Probe 3's NumPy check gives 1.84 from 2 to 1 µm.
- **The gap is the declared shells' discretisation, not the engine's transport.** The engine
  matches the exact discrete solution to 4e-7 of c0 (§11.2).
- **Its size is the declared face geometry's.** The probes' faces take the area 4πr² at the
  edge, so the conductance at the curved source boundary is wrong at first order in Δr/R.
  - Probe 5 (NumPy) declared the exact spherical-shell conductances 4πD r_a r_b/(r_b − r_a) on
    the same shells instead.
  - The steady gap then falls by a factor of 10 to 12.5: to 5.6e-3 of c0 at 5 µm, 1.6e-3 at
    2.5 µm, 1.1e-3 at 2 µm and 2.9e-4 at 1 µm.
  - The observed orders become 1.77 (5 to 2.5 µm) and 1.90 (2 to 1 µm). With the declared
    faces, the NumPy steady states reproduce the engine's (5.79e-2 and 1.94e-2).
  - So the builders of radial calibration worlds declare each face with that conductance (§6;
    accepted, §11.5, item 8).

**(b) The switch-on through the checked step map,** without the runner's host checks: 2.5 µm,
1 ms, 2,000 steps. No step was refused.

| Time | Against the exact discrete solution, of c0 | Against the Danckwerts form near the source (r ≤ R + 3λ), of c0 |
| --- | --- | --- |
| 0.25 s | 8.6e-7 | 2.19e-2 |
| 0.5 s | 1.7e-7 | 2.04e-2 |
| 1 s | 3.1e-8 | 1.97e-2 |
| 2 s | 4.2e-9 | 1.95e-2 |

**Transport through the switch-on is exact to the discrete solution.** Its gap from the closed
form approaches the smooth start's at that width: 2.04e-2 against 1.99e-2 at 0.5 s, and 1.95e-2
against 1.94e-2 at 2 s. The references differ: the infinite-medium form near the source here, and
the finite-domain series for the smooth start. So the refusal of §11.2 is the ledger's booking of
the onset, not a transport error.

### 11.4 Probe 5: the cause of the switch-on refusal, row by row

**The inferred cause** (probe 3): in the switch-on's first step the first shell rises from the
trace by ten decades or more, and that step books its face heat poorly. The runner host-checks
every accepted step as a row, against 2e-8 pJ + `ENERGY_RTOL` × the accumulated |heat| + |work|.
At row 1 those flows are the onset step's own.

**Method.**
- The model's own checked step, the step the runner takes, ran the worlds of §11.2.
- At every accepted row the runner's host check ran on that row (`surface_pump.checked_rows`,
  `steps=[k]`). Its verdict matched `model.check_values` on every row compared: the first ten and
  the first failure.
- At each row the probe recorded:
  - the energy residual E, here S's chemical change plus face heat minus bath work;
  - the accumulated flows and the bound;
  - the material and reservoir-work ledgers.
- Per step, it recorded the residual's increment over the step's own flows.
- **The criterion was written before the run** (HANDOFF). It has five parts, (a) to (e) below.

| Start, shells | Solver, dt | dt·K_ii | Failing rows | Onset step: residual / its flows | Onset: booked against implied face heat, relative | Step 2: residual / its flows | Row 1: residual / bound |
| --- | --- | --- | --- | --- | --- | --- | --- |
| jump, 5 µm | ARS, 1 ms | 0.050 | 1–7 | 1.04e-2 | −0.025 | 1.8e-3 | 5.2 |
| jump, 5 µm | ARS, 0.1 ms | 0.005 | 1–14 | 2.12e-2 | −0.041 | 1.5e-3 | 10.5 |
| jump, 2 µm | ARS, 1 ms | 0.30 | 1–93 | 8.75e-2 | +0.31 | 1.9e-3 | 43.7 |
| jump, 2 µm | ARS, 0.1 ms | 0.030 | 1–14 | 1.83e-2 | −0.042 | 1.9e-3 | 9.1 |
| jump, 5 µm | RK4, 0.1 ms | 0.005 | all 500 | 0.177 | +0.42 | 3.7e-5 | 7,870 |
| smooth, 5 µm | ARS, 1 ms | 0.050 | none | 6.5e-6 | −1.6e-5 | 5.7e-6 | 3.3e-3 |
| smooth, 2 µm | ARS, 1 ms | 0.30 | none | 4.2e-4 | −1.2e-3 | 2.0e-4 | 0.21 |
| smooth, 5 µm | RK4, 0.1 ms | 0.005 | none | 2.5e-13 | 6e-13 | 2.4e-13 | 1.8e-8 |

The implied heat is the one the energy identity requires, W − ΔG for the realised step. No step
was refused by the model's own step.

**The result: the cause is confirmed, but its size is smaller than inferred.**
- **Its location is fully confirmed.** Row 1 fails, every later step books within the bound, and
  the other ledgers are clean.
- **Its size is not "comparable to the step's own flow".** The onset residual is 1–2% of the
  step's flows at dt·K_ii up to 0.05, 8.7% at 0.30 and 18% under RK4. Row 1 fails by 5–10 times
  at dt·K_ii up to 0.05.
- **The pre-set thresholds were met narrowly:** 1.04e-2 against 1e-2 in (b), and a 4.8-fold fall
  against the 5-fold limit.

All five parts of the criterion hold:
- (a) every jump start fails first at row 1;
- (b) the onset step's residual is 1.0–8.7% of its own flows under ARS, 5 to 44 times the
  bound.
  - At 0.1 ms it is 1.8–2.1% on both widths, so it does not vanish with dt.
  - From 1 to 0.1 ms it rose twofold on 5 µm shells and fell 4.8-fold on 2 µm shells, whose
    1 ms step has dt·K_ii 0.30;
- (c) from step 2 every step books its heat within the bound: 1.5e-3 to 1.9e-3 of its flows at
  step 2, and 3e-6 to 1.5e-5 by step 20;
- (d) the smooth starts pass every row. The largest residual/bound is 0.21, at dt·K_ii 0.30;
- (e) the local, outside, total and reservoir-work ledgers stay within their bounds at every row,
  at most 0.70 of the bound. So the residual is the face-heat booking.

**Why rows keep failing after step 1.** The energy ledger is cumulative, so the onset's error
stays in every later row.
- Under ARS a row passes once 2e-3 of the accumulated flows exceeds that error: from row 8, 15,
  94 and 15, in the table's order.
- RK4's bound has no relative part, so all 500 rows fail. From step 2, RK4 books to 4e-5 of each
  step's flows, falling to 1e-13.

**The mechanism** (**S**).
- In the onset step, ln(c_a/c_b) on the source face falls from 27.6 to about 2–6 at the step's
  end, depending on the step and the shell.
- ARS books the face heat as J²RT/W, with the weight at a predicted state. RK4 books it as a
  four-stage quadrature of RT J ln(c_a/c_b).
- Either way a single step integrates a nearly log-singular path, so the relative error need not
  shrink with the step. At 0.1 ms, the one smaller step probed, it is about 4% under ARS on both
  widths.

**What it means.**
- The refusal is the ledger's booking of an unresolved onset. It is not a transport error
  (§11.3 (b)), not positivity, and not stiffness.
- It is a refusal, not a silent error. So guard worlds start from a resolved switch-on (§7).
- **In a mixed world the same onset error passes unseen,** because the shared bound is the
  ions' (§11.1). Probe 1's chain had a six-decade front at t = 0 and passed every host check
  (§1.2). The error misbooks a few percent of one step's species heat, up to a third at dt·K_ii
  0.30, and leaves transport exact (**S**).
- **This is a known limit** (the lead's ruling, 13 November; §2.6).
  - Transport is exact.
  - Under the ions' bound, the species' onset energy booking is off by a few percent and goes
    unseen.
  - The species-only world and the NumPy ΔG test per law certify the laws.
  - Production worlds should also start from a resolved switch-on.

### 11.5 Amendments and rulings

**From part 1 of the amendments** (7e55705):
1. **Rates belong to the occupant** (§5.2).
2. **A face diffusivity is the effective (FRAP) kind** (§2.1, §6).
3. **The first acceptance is numerical qualification** (§6).

**From these results, as the lead directed:**

4. **The energy guards of record** are the species-only world and a NumPy ΔG test per law.
   Each operator's docstring states that the shared IMEX bound is blind to these bookings at
   µM–nM, with bound/change from 1.7 to 1,721 (§7).
5. **The guard-world rule: a resolved switch-on, by a pre-formed profile** (§7).
   - Version 1 guard worlds use a pre-formed profile only, the measured arm.
   - A ramped source is unmeasured and not admissible until a probe measures it.
   - No bound on dt·D/Δr² is set beyond stability. Resolved starts pass at every dt·K_ii probed,
     up to 0.30.
6. **RK4 with a diffusing species is guarded, not refused** (§4.2). This is the decision the lead
   asked for, from probe 3's two RK4 rows.
   - From a pre-formed profile it is exact to rounding.
   - An unresolved onset is refused by the ledger, for the cause that ARS shares.

**Proposed in this round and accepted by the lead** (13 November):

7. **The stiff-front positivity guard runs the checked step map,** because the host ledger
   refuses an unresolved onset (§7).
8. **Radial calibration worlds declare exact spherical-shell conductances,** a requirement on
   their builders (§6). The probes' planar face areas made the continuum gap 10 to 12.5 times
   larger (§11.3). This rests on NumPy alone; no engine run has used those faces yet.
9. **The species-only radial world, with zero ion face diffusivity, is the RK4 guard world** for
   transport and face heat, beside the face-free world for the operators' work (§4.2).
10. **The onset energy booking in mixed worlds is a known limit** (§2.6, §11.4).
11. **The two new operators perform the 7-species refusal** (§2.6).

**The lead's rulings (13 November)**, also recorded in the evidence folder's HANDOFF.md:
1. **Donor copies.** Version 1 refuses a donor copy whose declared route values (ion and
   secretion) differ from the slot's. That keeps D139 and the occupant rule consistent (§5.2;
   §10, question 9).
2. **The stationary analysis is not admitted on the composite in version 1.** Per-species
   tolerance scaling is required before trace or nM species use the plain @3 path (§8).
3. **At most 7 species per world in version 1** (§2.6).
   - The two new operators' definition checks refuse a world with more, with a message naming
     the cap. No model changes.
   - The reason: host-side NumPy sums over the species axis switch to pairwise summation at 8
     or more terms. Host checks could then add the species in a different order from the
     device's explicit species-order adds (D148).
   - The cap holds until that is checked.
4. **The energy guards of record** are those of item 4: the species-only world and a NumPy ΔG
   test per law, with the docstring statement (§7).
5. **The ramped-source arm.** Version 1 guard worlds use a pre-formed profile only, the measured
   arm. A ramped source is not admissible until a probe measures it (§7).
6. **The mixed-world onset is a known limit.**
   - Transport is exact.
   - Under the ions' bound, the species' onset energy booking is off by a few percent and goes
     unseen.
   - The species-only world and the NumPy ΔG test per law certify the laws.
   - Production worlds should also start from a resolved switch-on (§2.6, §11.4).
7. **This round's five proposals are accepted** (items 7 to 11 above).

## 12. Amendments at milestone 1 (the lead, 14 November 2026, at milestone 1)

Version 1's first milestone is the two operators with their unit tests (branch commits 9400bc6 to
79044bb; evidence and the design-to-code checklist in
`/mnt/workspaces/Cells/secreted-species-v1-20261114-01/HANDOFF.md`). The lead ruled on its
questions as follows. Each ruling is the lead's, 14 November 2026, at milestone 1.

1. **Zero rates are admitted.** Zero V_max and k_u (and zero J, k_e, P and k) are the idle state
   (D136) and a swap to a zero-rate template. Negative values are refused, and K_M > 0 strictly.
   §2.3's refusal line is amended to match.
2. **The fixed kind order is accepted**, run as a palindrome within each half-step: first-order
   exports combined per cell, then flux exports, then first-order imports combined per node, then
   saturable uptake in declared order (§2.3, amended). It replaces "otherwise routes apply in
   declared order": routes of different kinds do not depend on their declared order. The evidence
   is the measured local error ratios per halving, 6.90, 7.43, 7.71 and 7.85, approaching 8.
3. **The turnover magnitude field is split** into a cell field and an outside field
   (`turnover_energy_magnitude_pJ`, `turnover_outside_energy_magnitude_pJ`; §2.2, amended). The
   D152 operator will use the same convention.
4. **Donor copies, as read in version 1, are accepted**; they are consistent with §5.2 and D139:
   - the slot's ion route values are its declared ones (D139's newcomer values);
   - the slot's secretion route values are the rates in force just before the event, so an
     admitted copy leaves the slot's controls unchanged across it;
   - a donor copy naming a route-only template is refused;
   - the newcomer takes the slot's rates, which equal the donor's by admission.
5. **Evidence kinds.** The catalogue plan's four kinds (`label_only`, `expressed_isoform`,
   `native_current`, `model`) are accepted for version 1, given exactly when a catalogue reference
   is. `native_current` was written for channel products; a secreted product would need a
   native-measurement kind, to be decided at catalogue stage 3 (held, D145). No new kind is added
   now.
6. **The schema is accepted:**
   - `templates` carry the rates of newcomers from replacement templates, keyed by template ID, then
     route ID;
   - schedules are entries of `route_id` and `carrier_id`: per carrier for cell-side routes (a
     founder's from time 0), per node (`carrier_id` null) for outside-node clearance;
   - a newcomer starts from its template's rate, or for a donor copy the slot's, then follows its
     own schedule strictly inside its life; schedule entries outside a carrier's life are refused.
7. **The adapter addition as two functions** with an explicit anchor and a separate magnitude
   function is accepted (§2.4, amended). The D152 operator will reuse
   `species_chemical_free_energy_pJ`.
8. **Crossrev:** the existing tools run unchanged, from a clean snapshot of the head, against the
   baseline of record (`/mnt/workspaces/Cells/checkpoint-continuity-20261113-01/baseline-21fb714/
   baseline-of-record.json`); all five sets (base, qualification, injection, volume, division) must
   be identical. The new operators' bindings driver lives in the checkout, under `validation/tissue/`
   (as `validation/division/division_crossrev.py` does for S5), importing the crossrev library, with
   its records in the evidence folder.

**Also accepted at milestone 1:**
- **The impermeability refusal** (17c3407; §2.6). Both operators refuse an inventory species with a
  membrane, junction or channel route of @3's, naming the route and the reason.
- **The §1.3 finding.** An anchored amount resolves to about ε × its anchor, reached at kt ≈ 36;
  below that it stalls positive and is never refused. kt ≈ 708 applies only to amounts stored
  without an anchor (§1.3, amended). The stiff-front guard expects the stall (§7, amended).
- **The bridge consequence** is a version 1.1 limit (§2.6, §5.3): bridge closure stays refused for
  inventory species until neutral species on junctions have a material-rate bound, a D148 question.

### 12.1 Milestone 2: the guards, as built and run (14 November 2026)

Code at b102da4 onward on the branch (tests and validation only; `src/` unchanged since 17c3407).
The runs in this table are development runs from clean heads, through `scripts/run_detached.sh`;
evidence in `/mnt/workspaces/Cells/secreted-species-v1-20261114-01/` (HANDOFF.md; `tests/`,
`crossrev/`, `tiers/`, `splitting_bias.json`). The negative controls are edits of saved histories
checked by the host ledgers, not misbookings inside the compiled program.

| Guard (§7) | Result | Where |
| --- | --- | --- |
| Crossrev of every existing set, constants included, from a clean snapshot of the branch head at hand-back 2 (first at b102da4, 2,924 files, empty patch; rerun at the final head, revision in HANDOFF), the tools unchanged, against the baseline of record | Identical: base 36/36 jaxpr texts, 36/36 constants, 12/12 bindings; qualification 78/78, 78/78, 56/56; injection 6/6, 6/6, 2/2; volume 6/6, 6/6, 2/2; division 27/27, 27/27, 9/9, its check holding | `crossrev/` |
| The new operators' bindings (`validation/tissue/secreted_species_crossrev.py`, eight worlds, its first record) | Holds: in two value twins (every rate and K_M changed) the traced programs are identical in text and constants and only control arrays differ; no nonzero control row equals a closed-over constant | `crossrev/species/b102da4/check.json` |
| Ion fields with both operators active, the mixed heredity chain against the same world without the species (idle claim 3, reported) | Bitwise on the scalar run, restart (in process and through a snapshot), a three-world vector batch (also bitwise against its reverse) and a replacement event; only the face heat and the baths' supply work differ (with the replacement's free-energy terms by the species' share) | `tests/unit/test_secreted_species_ions.py` |
| Energy, the species-only world (ruling 4), negative control | A systematic 1% error in a law's booked work, in a species-only world whose flow is that law's work: 3.17 (exchange) and 4.90 (turnover) times the IMEX bound at the last row, refused; the same error in the mixed world: 2.9e-4 and 3.0e-3 of its bound, unseen (the known blindness) | `tests/unit/test_secreted_species_guards.py` |
| The IMEX energy guard's sensitivity (a finding) | Under IMEX the species-only world sees a law's booking error only above 2e-3 of the species' total accumulated flows. In the secreting cell whose node leaks to a trace bath, the face heat dominates those flows: a 1% error in the secretion work was 0.02 of the bound at the last row, and was caught only at row 1, where the flows were one step's. RK4's absolute bound and the NumPy dG test per law cover what the IMEX ledger cannot see | b102da4 record, HANDOFF |
| Face heat, negative control (a finding) | A systematic 1% error in the booked face heat: refused by RK4's absolute bound in the radial world (6.1e4 times the bound). Under IMEX the same error reaches 0.89 of the bound at its largest and passes: the face heat is about a fifth of the radial world's flows (the source bath's supply work and the clearance's work carry the rest), so the IMEX ledger sees a face-heat error above about 1.1% only. The RK4 world is the face heat's sensitive guard, the IMEX species-only world a coarse one (§7, amended) | guards |
| RK4, the species-only radial world (ruling 6) | Energy residual 4.5e-14 pJ against the absolute 2e-8 pJ; 2.06e-8 of c0 from the exact discrete solution, which is the splitting's steady bias: the composite step's fixed point predicts 2.08e-8 at the first shell, the closed form dt² k (g − k c_ss)/12 2.05e-8 | guards, `splitting_bias.json` |
| IMEX radial world, pre-formed | Every host check; 9.93e-6 and 2.45e-6 of c0 from the exact discrete solution at 1 and 0.5 ms, ratio 4.05 (second order). The splitting's steady bias under ARS is dt² k (g − k c_ss)/4 at the first shell (6.14e-6 of c0 at 1 ms; the fixed point gives 6.21e-6), with g the source face's κ c0 / V0: milestone 3's step term. It scales with k, so it is negligible at k = 1e-4/s | guards, `splitting_bias.json` |
| Stiff front (§7, item 7 of §11.5) | From a 1e-15 mM trace under 1e-3 mM, 2,000 steps of 1 ms through the checked step map (dt K_ii 0.049): none refused, every amount positive, 6.2-6.6e-6 of c0 from the exact discrete solution; at 2 s, 6.209e-6, the splitting's steady bias to four digits. The run does not reach the anchored-amount stall (kt = 2); the tier-1 turnover test exercises it | guards |
| The trace background (§1.3) | A thousandfold trace moves the pre-formed profile by 0.947 times the trace's change, below it (as probe 3 measured) | guards |
| Unit and smoke tests (milestone 1) | Tier 1: turnover 18, exchange 16, definitions 20; the compiled runs 7 (tier 3) | `tests/unit/test_species_*.py`, `test_secreted_species*.py` |

**The radial world as built** (`validation/tissue/secreted_species_radial.py`): faces declared with
the exact spherical-shell conductance between the points they join (the source surface, the shell
mid-radii, the outer boundary), decay by turnover's node clearance at every shell, references from
the same declared system (matrix exponential). Its first engine runs are these guards; the
closed-form comparison against the continuum is milestone 3.

### 12.2 Milestone 3: the closed-form development run and the PROPOSED protocol (14 November 2026)

Code on the branch, `src/` unchanged throughout:
- dc2e494: the held sphere's closed forms, the radial builder's faces kind, the driver.
- 8d94451: the analysis, and the protocol's guard, judge and draft.
- a7e1869: the builder's exact areas evaluated as before; two tier-1 files.
- a40a332 to 392c633: the draft's findings, the PROPOSED protocol, the status-following refusal
  test.
- af2d2b4 to acbc27f: the lead's review — judged controls, the scope line, the PDE check, the
  step-map guard, and the protocol redrafted.

The engine arms ran twice, from the clean snapshots of dc2e494 and of a7e1869. The tolerances
come from the second run. It was analysed first from the snapshot of a7e1869, then, after the
review, from the snapshot of af2d2b4, with every judged number identical and the controls and the
step map's ratios added. No arm ran again after a7e1869: the eight worlds' definitions are
byte-identical. Evidence: `qualification-dev-a7e1869/` (and `-dc2e494/`) in the evidence folder
(HANDOFF.md). These are development runs: nothing here is judged.

| Item | Development result | Where |
| --- | --- | --- |
| The arms (§6's radial world: R = 10 µm, λ = 20 µm, the medium out to 6λ, k = 1/s, pre-formed: the steady state plus two positive sine modes of v) | All eight through the runner with every host check, none refused, `memory.events` all 0, peaks 1.4 and 1.6 GB. The 1.25 µm arm runs at dt K_ii 0.384, beyond the probed 0.30, and passed. The engine's amounts against its own bookings: 2.6e-15 fmol at most; energy relative 5.4e-8 (IMEX), 1.5e-14 (RK4) | `*.json`, `analysis.json` |
| Q1, IMEX (2.5 µm, 1 ms) against the exact discrete solution | The dt study per shell and record (S5's form): 0.468 of the tolerance at most, no element at the floor. The splitting term per record in the max norm: 0.368. Controls: the dt study catches k and D in error by 5e-10 and 5e-9, the splitting term by 1e-3 and 2e-3 | `analysis.json` Q1_imex |
| Q1, RK4 (2.5 µm, 0.1 ms) | 0.449 (31 of 96 elements at the floor), and 0.335. Controls 1e-12 and 1e-11, and 5e-6 and 1e-5 | Q1_rk4 |
| The step term is the splitting term | IMEX: the first shell's error is −3.100e-5 to −3.102e-5 of c0 from 0.25 to 4 s; the composite step's fixed point gives −3.102e-5, the leading-order term dt² k (g − k c_ss)/4 −2.812e-5 (9.4% low at dt K_ii 0.19). RK4: −9.40e-8 to −9.41e-8, the fixed point −9.41e-8, the /12 term −9.37e-8. The step map iterated in NumPy reproduces the engine to 4.1e-15 (IMEX) and 9.0e-14 (RK4) of c0 at every shell and record | Q1 predictions |
| Q2, IMEX (2.5 µm, 1 ms) against the closed forms, per element and record | 0.465 (the 24 coarse shells), 0.443 (the amount), 0.442 (the source's supply), 0.445 (the outer bath's), 0.442 (the clearance); the time term is at most 0.6% of the spatial. The probes' planar faces against the same tolerances: 28 to 248 times | Q2 |
| Q3, the orders | Space at 0.5 ms, in the max norm per record: the coarse shells 1.92-1.93; the scalars 0.85-3.28 by record (the source's supply irregular at 0.25-0.5 s, during the start's transient near the source; 2.0-2.1 from 2 s). Time at 2.5 µm: 2.00-2.09. Every stop rule holds. Element by element, one coarse shell of 120 (shell 19 at 2 s) does not fall where the spatial error changes sign: the reason the stop rule takes the max norm | Q3 |
| The two runs | Every fraction of tolerance within 0.001; the dt study's tolerances within 1.2e-5 (IMEX) and 1.3e-3 (RK4, at step terms of 5e-18 mM, about 1e3 times their own rounding) relative, Q2's within 1.4e-9 | the two `analysis.json` |
| The species crossrev (the new operators' set) | From the clean snapshot of 8d94451 it found the radial world's bindings changed against its first record (b102da4): face factors by up to 2 ulp, anchors by up to 5, from a regrouping of 4π r_a r_b at dc2e494. Restored at a7e1869: 24/24 jaxpr texts, 24/24 constants, 8/8 bindings identical, its check holding. `src/` is unchanged, so the five existing sets are untouched | `crossrev/species/` |
| A preview verdict (S5's precedent: the judge's code on copies of the development arms, the guard bypassed in-process) | Before the review: every item passes (Q1 IMEX and RK4, Q2, Q3). After it, with the judged controls: every item passes and every control is caught (Q1's k and D at the registered δ by 13 to 79 times the tolerance, Q2's planar arm by 28 to 248 times). It is no verdict | `qualification-dev-a7e1869-preview/`, `-preview-review/` |
| The closed forms' own checks (tier 1) | Both boundary conditions and a positive start; exact shell integrals against Gauss-Legendre to 1e-12; the mass balance to 1e-13 of the supply; the declared system's exact solution converges to them at second order (1.95-2.14, then 1.99-2.04 at 2 s) | `tests/unit/test_secreted_species_closed_forms.py` |

**The protocol** (`validation/tissue/secreted_species_protocol.json`, PROPOSED, not registered;
revised after the lead's review with the advisor, the same day):
- **Scope.** The judged arms run @3's faces with exact radial conductances and turnover's
  first-order clearance, with a held-bath source. Exchange, turnover's production and the
  occupant rule enter only through Q5's test files. This is §6's first acceptance, so no arm is
  missing.
- **Q1**, against the exact discrete solution, for the IMEX and RK4 arms. The claim is "bounded a
  priori by the splitting's leading term", and both rules are judged.
  - The dt-study rule detects bias, not order: a second-order error passes near 4/9 by
    construction, and a first-order one would pass near 2/3.
  - The splitting rule is the one bound not scaled from the engine's runs. It is one-sided, so
    it bounds the step term without identifying it; the identification (the fixed point, to
    5.8e-4 at the first record) is reported.
  - Its k and D controls are judged at a registered δ per rule and arm: 10× the larger of the
    smallest δ caught. At those δ the development catches them at 13 to 79 times the tolerance.
- **Q2**, against the continuum closed forms. Its judged control is the planar-face arm, which
  must fail every quantity's tolerance; in development it does so by 28 to 248 times.
- **Q3**, the orders: reported, with the stop rules judged in the max norm. The per-element count
  is reported, and both rule changes are disclosed.
- **Q4**, the Danckwerts switch-on: reported only, under the resolved-start rule. Probe 4's record
  stands.
- **Q5**, the guards of record: the test files at the judged snapshot. They include
  **R-continuum's independence check**, added at the review. The closed form is tested against the
  PDE itself, without the builder. Its fourth-order difference residual falls at fourth order to
  3.6e-10, and 1e-6 errors in D or k are caught. Both boundary conditions hold over time, and the
  start and the steady state match their sinh forms. R-discrete shares the builder's declared
  system, so Q2 is what covers a builder error.
- **The step-map guard** (`tests/unit/test_secreted_species_step_map.py`, tier 2): a regression
  guard for the landing gates, outside Q5's judged list (the lead, after the review round).
  - The judged configuration is shortened to 500 steps, with max |engine − map| ≤ n_steps ε × the
    scale. From the clean snapshot of af2d2b4, the results are 0.041 (IMEX) and 0.32 (RK4) of
    that bound.
  - It carries no qualification verdict, since one author wrote both sides. At its 3× margin on
    RK4, a rounding-level platform change would fail the qualification for the wrong reason.
  - The judged run reports the full arms' ratios (0.0055 and 0.095 in development), not judged.

It carries:
- S5's attempt rule;
- the resolved-start and guard-world rules;
- the guards of record: RK4 for the face heat, and a NumPy dG test per law.

The judge (`python -m validation.tissue.secreted_species_qualification judge OUT`) refuses three
things before it runs anything: an unregistered protocol, a source other than a clean snapshot,
and an existing OUT (`tests/unit/test_secreted_species_judged_refusal.py`). That test follows the
protocol's status, so registration leaves its outcome unchanged.

The review's rulings and changes are recorded in the protocol (`review`). What follows is S5's
order: land on main as PROPOSED, rehearse on main, dry-run every judge entry, register, then one
judged run from a clean snapshot.

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
