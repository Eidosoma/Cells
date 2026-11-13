# Composite v2: contract hardening, the entity volume ledger, membrane state, current injection

**Status: reviewed by the lead and the advisor on 12 November; code starts after this
revision is merged (D142).**
- Decisions 1, 5, 6 and 7 are accepted.
- Decisions 2 and 3 are accepted with the changes made here.
- Decision 4, and §2 as a whole, stay open until the renewal assay asks for them. Only
  §2's contract parts are approved: `VIEW_READS`, `ACCEPTS_WRITES` and `EVENT_REPLACES`,
  which live in §1.
- Built and guarded on 13 November: §1, current injection (§4, Rm1 passed) and stage S2
  (§3, with decisions 8 and 9). S3's prerequisites are listed in §3.

It serves two gates of the
[current plan](CURRENT_PLAN.md) (D145): *composition* (the ownership and conflict
contract, the entity volume ledger, water plus replacement, GPU agreement by tolerance)
and *lifecycle operators* (membrane state as entity state, insertion, current
injection). It builds on the landed composite ([PUMP_COMPOSITE.md](PUMP_COMPOSITE.md)) and
the division design's §2–§5 ([CELL_DIVISION_DESIGN.md](CELL_DIVISION_DESIGN.md)).

What does not change:
- `resolved_pump_tissue@3`'s physics and default code path;
- the results of every existing composition (water@1, water@2, replacement@1 and their
  thin modules), bit for bit;
- the composite's model ID. Results stay bitwise, as for the S1 thin modules, and new
  behaviour comes with new operator law IDs.

Order of work:
1. §1.2–§1.4 (observation ownership, combination rules, cross-operator writes), once the
   composite has landed;
2. §1.1 (energy roles), once the plan-validation fix has landed. That fix is editing
   `surface_pump*.py` now;
3. current injection (§4);
4. stage S2, membrane state and insertion (§3);
5. the entity volume ledger and water plus replacement (§2): open, built when the renewal
   assay asks for it (D144).

Alongside: the L4 agreement (§5). Its CPU-only driver parts come once CPU 4 is free; the
GPU runs come in a slot the lead gives.

Every new operator ships a **tier-1 smoke test under 20 s**: one tiny world, a few steps,
its ledgers closing and its idle identity. Its proofs are tier 3, so the routine gate would
otherwise never run it.

**The entity table** (the plan's ownership contract) mapped onto owners in the composite:

| Entity | Its state | Owner | Writers |
| --- | --- | --- | --- |
| Compartment | Amounts | @3 | @3's step; replacement events; injection (§4); partition later |
| | Volume | Water (`volume_increment_pL`) | Water's flow; replacement events (§2) |
| | Fixed-charge background | @3, constant except at events | Events |
| Membrane domain | Area, capacitance | Not owned today (@3 layout). `membrane_entity_state` (§3) | Insertion (§3); partition and mechanics later |
| Functional-unit population | Abundance (gates are @3's) | Not owned today (@3 layout). `membrane_entity_state` (§3) | Insertion; replacement templates; trafficking and regulation later |
| Contact | Gate state | @3 | @3's step |
| | Junction abundance | Replacement's formation law | Replacement's formation law |
| | Aperture | Not owned yet | Bridge closure (S5) |
| Cell and lineage | Identity, membership, ancestry | Replacement's lineage records | Replacement events; partition later |
| Extracellular environment | Finite nodes' amounts and volumes | @3 and water | Transport, water, bath supply (booked) |

**Ownership is per field, not per entity.**
- One operator can own fields of two entities: `membrane_entity_state` holds the
  membrane domain's and the population's fields.
- One entity's fields can have several owners: the compartment's amounts are @3's and its
  volume is water's.
- When a composition is built, the composite builds a field-to-owner map, with each
  field's writers. It checks that every field has one owner and that every write is
  accepted by the field's owner.
- The map is written to the run manifest beside `composition`. It is a new optional key:
  existing manifests lack it, and readers treat it as optional.
- **Explicit choice: no typed entity classes for now.** The entities are documentation
  over the field map.

**Run identity (decision 1).**
- `composition_identity` is (composite ID, inner ID, ordered operator law IDs).
  Declarations do not enter it.
- The batch signature adds each operator's declaration data and the array axes.
- §1 adds declarations and no state fields, so it changes neither of these. Existing
  manifests' `composition` entries and checkpoints' identities stay valid.
- A later operator that adds state fields changes the batch signature for compositions
  that include it, and only for those.

## 1. Contract hardening

### 1.1 Energy roles declared, not recognised by suffix

**Built (bbe40af):**
- The composite binds its step checks: @3's bound checks on `inner_check_spec`, then
  each operator's; definition-only parts are evaluated once per clock (R5).
- @3's free energy has its declared owner in the adapter (`chemical_free_energy_pJ`,
  `capacitor_free_energy_pJ`). Replacement and injection book their exact changes with
  it, and injection's temporary import is gone.
- The energy-role table (55b802e). The composite's flow bound reads @3's heat and work
  fields by name (the adapter's `HEAT_FIELDS`, `WORK_FIELDS`) and each operator's
  declared fields, in state order. `surface_pump.ledger_limits` gained one optional
  `flow_fields` argument, whose default keeps the suffix selection for every other caller.


This starts after the plan-validation fix lands; that fix is editing `surface_pump*.py`.

**Today:**
- Operators declare `HEAT_FIELDS` and `WORK_FIELDS`, and the composite's dissipation list
  is built from them.
- But the family's shared energy-ledger bound (`surface_pump.py`, the flow-magnitude sum)
  still selects row fields ending in `_dissipated_energy_pJ` or `_work_pJ`.
- The contract only cross-checks names against declarations.

**v2:** the composite builds one energy table when the composition is built.
- Each float state field gets exactly one role:
  - *material, volume, area or charge accumulator*: booked transfers, signed;
  - *heat*: dissipation, with nonnegative increments checked;
  - *work*: supplied energy, signed;
  - *diagnostic*: an unbooked running magnitude;
  - *kinetic*: everything else.
- Inner fields take their roles from the adapter's explicit lists (@3's dissipation and
  work fields), operator fields from their declarations.
- Every energy sum, flow magnitude and bound reads the table in state-field order, so
  existing compositions keep their bounds bit for bit.
- Suffixes become naming convention only.
- The family function gains an optional explicit field list. Its default stays the suffix
  selection, so @1–@3 are unchanged; the guards are in §4.3.

**Free-energy owners (new declaration).** Each owner of state that carries free energy
declares a per-entity endpoint free energy relative to its declared reference:
- @3: the chemical term F(N, V0) − F(N0, V0) and the capacitor energy (through the adapter);
- water: dilution −RT N_tot log(V/V0) and elastic U(V) − U(V0), which it already sums in
  its energy ledger;
- membrane state (§3): the capacitor energy at the current C.

Any state change made outside the inner step (an event or a split part that writes entity
state) books the exact change of the summed free energy of the entities it touched. §1.3
gives the rule.

### 1.2 Observation ownership explicit

**Today:** an operator's `observe` returns columns that are merged with `row.update`. An
operator can replace an inner column by returning its key (water@2 replaces the energy
columns). The owner is the last writer in declared order.

**v2:**
- Each operator declares `OBSERVES`, the new columns it owns, and `REPLACES`,
  {inner column: reason}.
- The composite builds the column-ownership map when the composition is built. Every
  column has exactly one owner, the inner model by default.
- Replacement is a declared chain in operator order, and a column's owner is the last in
  its chain. This corrects the reviewed rule, which refused a second replacer and the
  replacement of another operator's column.
  - The implementation found that existing compositions already chain: water replaces the
    inner energy-balance rate, and the symport then replaces both energy columns.
  - The reviewed rule would therefore have refused water@2.
- It refuses:
  - a column added by two owners;
  - a replaced column that no earlier owner observes;
  - an operator that returns a column it did not declare, or omits one it did.
- The assembly checks that each operator returns exactly its declared keys (host side, on
  every row).
- Water declares that it replaces the inner `energy_balance_pJ_s`. The symport declares
  that it replaces `energy_balance_pJ` and `energy_balance_pJ_s`.

### 1.3 Combination rules checked when a composition is built

Each rule is a build-time check with a refusal message.

| Rule | Check |
| --- | --- |
| **Fluxes add** | Several writers of one entity field each book their own accumulators. The owner's ledger closes with the sum over writers (Δx = Σ booked terms). Split-part rates add in the RK4 coupled right-hand side. In-step processes stay at most one per composition: @3's hook returns one applied transfer, so two processes could not be booked separately. Current injection does not need the hook (§4). |
| **Factors multiply** | `CONTROL_FACTORS`, a product in declared order (exists). |
| **One provider per view field** | Exists. New `VIEW_READS`: an operator that needs the current value (replacement@2 reads volume) declares it, in place of `CONFLICTS_VIEW`. The reader must follow the provider in the list. |
| **Events replace and book** | Every field an event map changes is declared, in one of three ways: <ul><li>a replaced field (`EVENT_REPLACES`): removed and supplied accumulators, for conserved quantities (material, charge, volume, area, abundance), wired into the owner's ledgers;</li><li>a booked increment of an inner accumulator, such as replacement's image charge and work added to @3's electrode fields: an `ENTITY_WRITES` entry with the owned accumulators that mirror it;</li><li>an intensive reset (`STATE_RESETS`, gates only).</li></ul> The declarations are checked for consistency when operators are registered. What an event map actually writes is not verified at run time. It also books: <ul><li>the change of the summed free energy of the replaced entities, as supplied work (§1.1);</li><li>the image charge at the clamps, with its work Σ φ_b Δq_b, as replacement does today.</li></ul> |
| **Split parts that write entity state** | They book like events, for each half-step: the exact free-energy change as work, or as heat for a dissipative law (water's flow keeps its own heat), and the image charge at the clamps. |
| **One owner per derived observation** | §1.2. |
| **Energy roles** | §1.1. Every float field has one role; heat and work fields belong to one operator. |
| **Order** | `REQUIRES`; owners before writers; event maps first in the step (exists). |

### 1.4 Cross-operator entity writes (S1 report, item 6)
- The target of `ENTITY_WRITES` may be an inner state field (as today) or a field owned by
  another operator.
- The owner declares `ACCEPTS_WRITES`, {field: its ledgers}, for example water:
  {`volume_increment_pL`: (`water_local`, `water_total`)}.
- When the composition is built, the composite:
  - resolves each written field to its owner and refuses a write the owner does not
    accept;
  - wires the writer's accumulators into the owner's ledger terms and rounding magnitudes.
- The owner's ledger code reads them through one interface, `external_net(field)`: the sum
  over writers of supplied minus removed, per element.
- With no writer the term is absent (a static branch), so the owner's ledger, and its
  jaxpr, are unchanged.

### 1.5 Guards for §1 (all on CPU)
- **The families that share `surface_pump.py`.** @1, @2 and @3's own test files pass, and
  their checked steps, right-hand sides and device checks trace to identical jaxprs
  across revisions (§4.3 for each), since the energy-bound function is shared.
- **Existing compositions bitwise.** Measured across revisions (composite_crossrev,
  composite_dump), before against after §1:
  - the S1 composite test files and the frozen models' own test files pass;
  - the jaxprs of the 12 base and 26 qualification worlds are identical;
  - the bindings are identical;
  - the 17 dumped runs are bit-identical.
- Unit tests of each refusal: a heat role without nonnegativity, two column owners, an
  undeclared returned column, a write the owner does not accept, an event writing an
  undeclared field.

## 2. The entity volume ledger: water plus replacement (open)

Open until the renewal assay asks for it. Its contract parts (`VIEW_READS`,
`ACCEPTS_WRITES`, `EVENT_REPLACES`) are approved and built with §1. The rest is kept here
as the plan.

**Today the composition is refused:**
- water provides `volume` and `extracellular_volume`;
- replacement@1 declares them `CONFLICTS_VIEW`: its templates, formation law and free
  energy use the declared volume V0;
- under RK4, water's coupled part with an event map is refused as well.

So the composition is IMEX only, and it stays so.

**New law `scheduled_cell_replacement@2`** (replacement@1 unchanged):
- **Newcomers declare volume and contents.** A template declares `volume_pL`, defaulting to
  the slot's declared volume (replacement@1's meaning), and its amounts, as today.
  - The water-side impermeant content must equal the slot's declared value in this first
    slice; it is refused otherwise.
  - A different impermeant content needs water-owned impermeant state, a later extension.
- **The event map writes water's volume.** At an event on slot c with old volume
  V_old = V0 + dv:
  - `volume_increment_pL[c] ← V_new − V0`;
  - `replacement_volume_removed_pL[c] += V_old` and
    `replacement_volume_supplied_pL[c] += V_new`.
  - Water's ledgers then read, per cell, `dv + moved_out − (supplied − removed) = 0`, and
    in total `Σdv + Σdve − Σ bath supply − Σ(supplied − removed) = 0`.
  - Material and charge are booked as today (removed and supplied amounts, charge, image
    charge).
- **Free energy:** the event books the change of the slot's summed free energy (@3's
  chemical and capacitor terms, water's dilution and elastic terms) from (N_old, V_old) to
  (N_new, V_new) as supplied work. The energy ledger then closes across the event.
- **Transport sees the newcomer's volume.** The formation law and the inner step read the
  view volume (`VIEW_READS`), so concentrations after the event are N_new / V_new.
- **Refusal:** a newcomer volume outside water's bounds is refused when the definition is
  checked and again in the event's domain check. A refused step returns the full start
  state, water's volume included (the composite's existing refusal path).

**Guards (from the S1 report):**
1. Replacement@2 over closed water (availability 0), with template volume equal to the
   declared volume, equals replacement@1 bitwise: the volume view is V0 + 0.0, and the
   dilution and elastic changes are exact zeros.
   - This holds for the free-energy accumulator only if @2 computes @3's terms with
     replacement@1's own expressions, in the same order, and adds the other owners'
     terms after them.
   - Audit before code: whether @3's per-entity free-energy terms can be reached through
     the adapter without copying. Today they live in the replacement law (`_chemical`,
     `_electric`).
2. Event-free replacement@2 over water equals water@1 bitwise.
3. Water's volume and energy ledgers close across events on a world whose replaced cell
   has swollen or shrunk; material and charge reconcile.
4. After an event, the next step's concentrations are N_new / V_new (analytic).
5. A refused event leaves the full prior state.
6. Restart before, at and after an event; vmap with per-world events.
7. The composition runs labelled development (`composition_status`) until a protocol for
   it is registered.

## 3. Stage S2: membrane state as entity state

**Owner: a state-only operator, `membrane_entity_state@1`.** It has no dynamics of its own;
its writers are insertion now and partition, mechanics and trafficking later. It owns, as
anchored increments from the declared values:
- per patch: area A and capacitance C, both state;
- per population and patch: abundance N.

C is kept as state, not derived from A, because a declared patch need not satisfy
C = c_d A exactly. Insertion keeps dC = c_d dA.

**It provides through the view:**
- `membrane_area` and `membrane_capacitance`;
- `channel_abundance` as declared × (A0 / A) + ΔN / (A ρ_ref), so zero increments give the
  declared value bit for bit;
- route values per area where @3's layout uses them.

**Populations:**
- Each declares a `functional_unit` ID and an opaque `catalogue` reference (null, or
  `{"catalogue": id, "entry": key}`) ([PROTEIN_CATALOGUE_PLAN.md](PROTEIN_CATALOGUE_PLAN.md)).
- The reference is carried to the summary and manifest and never into arrays.
- Guard: changing a catalogue reference leaves bindings, jaxprs and trajectories bitwise
  unchanged.

**Insertion, `scheduled_membrane_insertion@1`** (a general name; the furrow is a use; D144):
- **Law** (design §5.1): a split process on a patch.
  - dA = r dt, dC = c_d r dt, dN_k = ρ_k r dt, applied in half-steps at fixed free-node
    charges, with the potentials re-solved.
  - Each clamp supplies image charge Δq_b, booked as electrode transfer with work
    W = Σ φ_b Δq_b.
  - Insertion heat H = G(C) − G(C') ≥ 0 is a new declared heat field, so the energy
    ledger closes as ΔU = W − H.
- **Onset:** an event part flips the patch and cleft masks. Activation needs anchors
  declared for the slot (§3.8).
- **Refusals:**
  - negative area or retrieval (dA < 0): heat would be negative, and supplied work needs a
    declared source;
  - a rate outside its schedule;
  - a definition with floating capacitor components (topology epochs are later work).
- **Field:** a change of C or of a mask makes the adapter recompute the capacitor matrix,
  scale, solve matrix, Cholesky factor and the fixed and active masks on the device. They
  are selected only in a step where an input changed. That path exists, is unit-tested and
  is exercised for the first time here.

**Update rules for state-dependent views.** Bind-once applies only to quantities that do
not change during the run.

| Rule | Content |
| --- | --- |
| R1, bind once | Topology indices, slot capacities, species, law parameters, declared reference values (V0, A0, C0, declared abundances, anchors) and bath potentials are bound on the host, once. |
| R2, views from state | Volume (water), area, capacitance and abundance density (membrane state), and activity masks (events) are computed on the device from state by their single provider. |
| R3, derived arrays | Arrays derived from R2 inputs (the field arrays) are taken from the recomputed values only when an input changed in that step; otherwise the bound arrays are selected, so the result is bitwise when idle. The recomputation itself is not skipped (below). |
| R4, when evaluated | After events; after the first split halves for providers whose view follows their split part; held through the inner step (Strang); re-checked at the step end. |
| R5, definition-time checks | Explicit step bounds, rounding floors and admission checks that depend on an R2 input are computed once per definition on the operator-adjusted check spec, never on the raw inner spec. That spec is each provider's `inner_check_spec`, the worst case of the views it provides: water's declared minimum volumes; insertion's largest area with its declared (smallest) capacitance, and with onsets the definition before them (below). The plan-validation fix's once-per-definition bounds must take that spec. A check that has no worst case moves into the step's domain check as a refusal. |
| R6, host consumers | Observations, checks and summaries recompute the view from each saved row (as `observe_history` does). |
| R7, restart | A view is a pure function of state and the bound layout, so restart saves nothing more. |
| R8, anchors | Increments from declared values; zero increments reproduce the declared values bit for bit. |

**R3's cost: the refactorisation is a select by value.**
- `refresh_field` combines the recomputed and bound arrays with `xp.where`. So whenever
  any operator provides a field input, the capacitor matrix, solve matrix and Cholesky
  factor are recomputed every step, changed or not.
- A `lax.cond` would skip that only in unbatched runs: under vmap, a per-world predicate
  turns the cond into a select and both branches run. The static-branch rule (§3.7)
  covers which code is present, not this per-step cost.
- Estimate (before measuring): one dense refactorisation of the n-node system costs about
  n³/3 operations, about 4 × 10⁴ at n = 50 and 1.9 × 10⁸ at 825 nodes.

Options:
- (a) accept it, and refuse a field-input provider above a declared node count;
- (b) refactorise only at declared insertion epochs: C is held between epochs and the
  §5.1 booking is exact at each one;
- (c) a rank-k update of the factor for the k patches whose C changed, about k n²
  operations. It is bitwise when idle only if it is skipped statically or shown to be
  exact at ΔC = 0.

**Measured on CPU** (13 November; one core; the same compiled step with and without an
operator that provides `membrane_capacitance`; composite-v2-20261112-01/s2-r3-cost):

| World | Field nodes | Step | With the provider | Increase |
| --- | --- | --- | --- | --- |
| Uncleaved egg | 2 | 0.690 ms | 0.742 ms | +0.05 ms (+7.5%) |
| Seven-cell sheet | 14 | 1.72 ms | 1.70 ms | within noise |
| 127-cell sheet | 254 | 7.68 ms | 9.24 ms | +1.56 ms (+20%) |
| 825-node world | 825 | 75.7 ms | 111.9 ms | +36.2 ms (+48%) |

As a separate call, the refresh costs 0.64, 1.00, 3.19 and 27.9 ms; at small sizes that is
mostly call overhead, so the in-step increase is the number that matters.

**Decision (lead, 13 November): option (a), capped at 64 field nodes.** A field-input
provider is refused when the definition's padded field size (cell plus outside capacity)
exceeds 64, with a message naming (b) and (c). S2–S5 need about 50 nodes or fewer (up to
16 cells, their clefts and the bath). (b) or (c) is decided before any larger world uses a
field input.

Insertion adds two refactorisations per half-step (before and after the change) and the
view's capacitor solves in every checked row. Its own cost was measured after it was built
(one core; median of 200 jitted steps; composite-v2-20261112-01/s2-cost):

| World | Field nodes | Plain composite | Membrane state | Membrane state and insertion |
| --- | --- | --- | --- | --- |
| Cleft cell | 3 | 0.93 ms | 0.88 ms (noise) | 1.07 ms (+15%) |
| 19-cell sheet at the cap, insertion into every patch | 64 | 1.51 ms | 1.70 ms (+13%) | 2.11 ms (+40%) |

For S3's cleft egg (3 nodes, about 4 × 10⁶ steps) insertion adds about 15%.

**Audit before code** (13 November): @3's layout quantities that its binding derives from
area, capacitance or abundance, and how each is handled:

| Quantity | Binding | Handling |
| --- | --- | --- |
| `membrane_area`, `membrane_capacitance` | Copied per patch; read at run time (fluxes, capacitor terms, energy) | R2 views (membrane state) |
| `channel_abundance` | Copied per population; channel flux ∝ P × abundance × area | R2 view, N / (A ρ_ref) |
| Field arrays (capacitor matrix, scale, solve matrix, Cholesky factor, fixed and active masks) | From capacitances and masks | R3 (refresh) |
| `initial_membrane_voltage_V` | A bind-time capacitor solve (`surface_tissue.py`, initial values) | Stays the declared reference V0 (R1); the energy rule below |
| Explicit-rate bound | Definition time, from capacitance and area-scaled conductance | R5 (below) |
| `pump_capacity`, `calcium_pump_capacity` | Per-membrane totals, not area-derived | Unchanged; inserting pumps is out of the first slice |
| `face_factor` (D × area / length) | Per face | Fixed in S2; an R2 view when the lumen grows (S3) |
| Junction area | Per junction | S5 |
| Device-check constants, capacitor tolerance, ledger bounds | No bind-time area or capacitance; the latter two read the layout at run time | Unchanged |

**The energy rule: the capacitor energy at a view.** The composite runs @3's balances on
the declared layout, so @3's capacitor term reads the declared C0, the declared V0 and a
charge response dv_b solved with the declared field arrays:

    E3 = ½ Σ C0 dv_b (2 V0 + dv_b) = ½ Σ C0 (Vb² − V0²),   Vb = V0 + dv_b,

where Vb is the patch voltage that the declared capacitances and masks give the current
charges. It is not the actual voltage V once C ≠ C0: for one patch, V = q/C but
Vb = q/C0. The requirement is on the total: the composite's capacitor energy must be the
physical

    E = ½ Σ C V² − ½ Σ C0 V0²,

with C and V at the view and the reference fixed at the declared initial state. So the
correction is

    E − E3 = ½ Σ (C V² − C0 Vb²) = ½ Σ [(C − C0) V² + C0 (V − Vb)(V + Vb)].

The second form subtracts no bulk energies. Neither simpler formula applies here: a term
that read the view C with the view's response would need ½ (C − C0) V0², and a declared
term with the actual voltage would need ½ (C − C0) V². Both assume V0 + dv equals the
actual V, which fails as soon as C changes, because V0 and dv come from different
capacitances. @3's electrode ledger needs the matching term: the clamps supplied the view's
plate charges, so at each held node it subtracts q_b(view) − q_b(declared), both at the
current charges. Both terms are exact zeros, selected, when no field input differs from its
declared value (`adapter.view_capacitor_terms`). They are booked in insertion's ledger
terms, since insertion is the only writer of capacitances and masks in S2. When a second
writer arrives (partition, S5), the same function moves to the composite and is called once
for any field-input provider: division design §5.3 names the composite as the owner. A
tier-1 test checks the total against ½ C V² − ½ C0 V0² over a spread of declared (C0, V0)
and current (C, V), on one patch and on two clamps with their plate charges.

**The insertion change at fixed charges** (division design §5.1, `adapter.fixed_charge_change`).
With dKφ = Σ_k ΔC_k V_k e_k, the free potentials move by δ_f = −(K'_ff)⁻¹ (dKφ)_f and the
held nodes' plate charges by Δq_b = (K' δ + dKφ)_b. The capacitor free energy falls by

    H = ½ Σ ΔC_k V_k² + ½ δ_f · (dKφ)_f = ½ Σ ΔC_k V_k² − ½ (dKφ)_fᵀ (K'_ff)⁻¹ (dKφ)_f ≥ 0,

whose second term is of second order, so H too subtracts no bulk energies. One patch gives
V' = V C/(C + ΔC) and H = ½ q² ΔC / (C (C + ΔC)); with W = Σ φ_b Δq_b, ΔU = W − H holds
exactly in exact arithmetic.

**Onset, as built.** A patch declared with an onset time is masked until then, with its
outside node and that node's faces: the view masks `membrane_active`, `outside_active` and
`face_active`, and the node's reference amounts read 0 while it is inactive. The adapter
gained the last two as view fields. The anchors are declared in @3's model at the onset
values (§3.8). The node is finite, has a zero charge anchor, and every patch facing it
opens at the same time. The patch therefore opens at zero voltage with the node following
its cell: the onset moves no charge, changes no energy and books nothing. The node's content
is its anchor (D057), already counted on the declared layout.
- Refused: channel populations or pumps on an onset patch; an onset patch facing a held
  bath; an operator that provides the node's volume.
- **Declared departure from division design §6 (accepted 13 November).** @3's domain
  requires an inactive population to carry law code 0, and the onset masks the patch, not
  the population's law. So the new membrane's leak is the onset patch's passive
  permeability (per area, so it scales with the inserted area), not K and Na leak
  populations, until populations on onset patches are built. Populations on patches open
  from the start are inserted at their declared densities. The departure is recorded in
  division design §6 too.

**S3 prerequisites** (accepted 13 November; both resolved the same day, guards below).
- **(a) The onset energy.** A wide access face makes the onset a transient faster than the
  step. It charges the patch to about V_m through the face, which an IMEX step books only
  to its own tolerance: about ½ C_f V_m² of heat goes unbooked when the access time
  constant is far below dt. Plain @3 gives the same residual bit for bit with the cleft
  active from t = 0 (−0.0015217 pJ in the S2 probe, against a host energy bound of a few
  10⁻⁶ pJ).
  - **Physics.** The zero-charge onset is right. The new membrane arrives uncharged, and
    R-full opens its lumen at bath composition and zero charge too. Charging it through the
    access then dissipates exactly ½ C_on V_m², whatever the access resistance.
  - **Decision: neither book the charge nor resolve the access.** Booking the charge as an
    event would be the τ → 0 limit of that physics, wrong for a slow access. Resolving
    τ = C_on / G_acc ≈ 6.6 µs (0.94 µS access, 6.2 pF at activation) in the egg would
    need microsecond steps.
  - **The bound.** What IMEX leaves unbooked is at most ½ C_on V_m² ≈ 3.1 × 10⁻⁴ pJ
    (V_m = −9.95 mV). The engine's own host energy bound at 420 s, measured on the
    uncleaved Rm1 egg, is 4.5 × 10³ pJ, so that is 7 × 10⁻⁸ of it. The insertion's later
    perturbations add 1.5 × 10⁻⁷ pJ per 0.5 ms step, 0.43 pJ to J1 (R-full's values;
    composite-v2-20261112-01/s3-prereq).
  - The host energy check stays the guard: in a world where the unbooked heat exceeds
    the solver's tolerance, the run is refused, as the tiny S2 world's was.
  - Tests: one coarse step leaves −½ C_on V_m² in the energy residual (within 10%); 0.1 µs
    steps at a 5 µs access book the heat in the access (within 10%), with the residual
    below 1% of it; and the 1 ms run of that small world is refused.
- **(b) Image charge at the view.** Insertion refused to compose with an operator that
  books image charge on the declared layout, whose bookings would miss the changed
  capacitances, and Rm during cleavage needs injection with insertion.
  - Built: a split part that `BOOKS_AT_VIEW` gets the composite's view in its half-steps
    when a field input is provided. Injection then books the clamps' plate charges and the
    capacitor energy change at the view (`adapter.charge_energy_change`). Without a field
    input the call and the arithmetic are as before.
  - Insertion now refuses only declared-layout bookers (replacement's event map).
  - Guards: the two-clamp analytic image charge after insertion; every ledger closing; the
    declared booking shown to leave the electrode ledger open; a compiled run of pulses into
    a growing patch closing every host check; and crossrev of injection without field
    inputs (the heredity cell, and the Rm1 egg that the judged Rm1 ran on), whose jaxprs
    and bindings are identical to 00672e8.
- **(c) Found 13 November, open: injection's electrode-ledger drift at egg scale.**
  - The uncleaved Rm1 egg, with its two pulses (0–12 s), run to 420 s at 1 ms fails the
    host electrode ledger (composite-v2-20261112-01/s3-prereq/electrode_diag.json).
    - The residual is 1.6 × 10⁻²⁰ C after the pulses. It drifts at about 2 × 10⁻²³ C per
      step to 200 s.
    - From about 300 s it grows linearly at 7 × 10⁻²² C per step, reaching
      8.4 × 10⁻¹⁷ C at 420 s, 5 times its bound. The bound grows by only
      4 × 10⁻²³ C per step (the step-scaled allowance on injection's image charge).
  - Without the electrode the residual is exactly 0 at every one of the 420,000 rows:
    @3's electrode increment is a difference of plate charges and telescopes exactly
    there.
  - Not caused by this round's change: the crossrev above shows injection's program and
    bindings unchanged. The judged Rm1 ran 12 s and passed.
  - The cause is not isolated. Injection books its image charge as the same difference
    of plate charges, and it is idle after 12 s, yet the drift continues and changes rate
    near 300 s.
  - S3 needs 2100 s with 210 pulses, so this blocks S3's egg runs until it is diagnosed
    and fixed, or bounded with a justified allowance.
  - The same run gives the engine's energy bound used in (a). The pulses leave about
    0.45 pJ each in the energy residual, scheme error within IMEX's tolerance.

**R5 for insertion, as built.** The inner checks run on the definition with every inserted
patch at its largest area over the schedule and its declared capacitance, which is the
smallest. When onsets are present, insertion's own check adds the explicit-rate bound of
the definition before any onset, with onset patches, nodes and faces removed. The cell's
rate is total conductance over total capacitance, a Möbius function of the inserted area,
so its maximum lies at an end of the schedule. The two checks bound it everywhere: the
largest conductance over the smallest capacitance after onset, and the cell without its
onset patches before. Channel populations are not in the definition-time bound, as before;
@3's IMEX steps refuse themselves at the actual openings and areas of the view.

**The egg worlds under the cap.** The cap counts padded capacity: cell slots plus outside
slots. Division gives each daughter a fresh slot and retires the parent's (§5.2 of the
division design), so a 1 → 2^k run needs 2^(k+1) − 1 cell slots, one cleft per furrow, and
the bath.

| Stage | World | Cell slots | Outside slots | Field nodes |
| --- | --- | --- | --- | --- |
| Rm1 (§4) | Uncleaved egg (`injection_rm1`) | 1 | 1 | 2 |
| S3, S4 (J1) | Cleft egg: cytosol, cleft, bath (as in `static_cleft_egg_steps`) | 1 | 2 | 3 |
| S5 | First partition, 1 → 2 (parent and two daughters) | 3 | 2 | 5 |
| S5 | 1 → 2 → 4 | 7 | 4 | 11 |
| Plan's maximum | 1 → … → 16 | 31 | 16 | 47 |

All of these are under 64. The 825-node world of division design §3.7's idle guard is
not, so that guard is deferred until (b) or (c) is decided. S2 runs the idle guard on
the largest world the cap admits instead: the radius-2 heredity sheet (19 cells, each with
its held bath, 42 gated junctions, 38 channel populations) padded to 32 + 32 = 64 field
nodes.

**S2 guards** (13 November). The guards of record ran from a clean snapshot of d58751b
(unit cells-composite-s2-guards, CPU 4). The targeted rerun ran from a clean snapshot of
965a804 (cells-composite-s2-followup), after water and replacement declared `membrane_area`
in `CONFLICTS_VIEW` and the cap-edge, population and reversed-batch tests were added.
Evidence: composite-v2-20261112-01/s2-*, s2b-tests and s2-vmap.

| Guard | Result | Where |
| --- | --- | --- |
| Tier-1 smoke test under 20 s for each operator | Membrane state 12 tests, insertion 23 tests (at 00672e8), 2–3 s each | `test_membrane_state.py`, `test_membrane_insertion.py` |
| The energy rule: the total is ½ Σ C V² − ½ Σ C0 V0² | Within 10⁻¹² of the bulk: one patch over 6 declared (C0, V0) × 12 current (C, V); two clamps over 12 states, with the plate charges | smoke |
| Idle membrane state equals the composition without it | Bitwise: heredity cell, seven-cell sheet, and the 19-cell sheet at the 64-node cap (in place of the 825-node world) | runs |
| Insertion at r = 0 equals idle | Bitwise (two clamps) | runs |
| One-patch analytic | V' = V C/(C + ΔC) to 10⁻¹²; H = ½ q² ΔC / (C (C + ΔC)) to 10⁻⁹ at ΔC/C = 10⁻⁶, ½ and 1; ΔU = −H; every ledger below 10⁻¹⁵ | smoke |
| Image charge and ΔU = W − H | Two clamps: Δq_b analytic to 10⁻¹², W = Σ φ_b Δq_b, ΔU = W − H to 10⁻¹², host checks pass | smoke |
| Onset | Masked until the event; the declared layout bitwise after it; a stale schedule and a rate before onset refused; a compiled run closes every ledger | smoke, runs |
| Restart across onset and insertion | Bitwise at 1 ms, at the onset (2 ms) and at 3 ms, also through a written snapshot; the manifest carries the field owners | runs |
| vmap | Vector-window batch with device checks, three cleft worlds at three rates. Bitwise against the same worlds in reversed order (one compiled program). Within 1.6 × 10⁻¹³ of each field's scale against each world's own run, apart from the one-clamp image charge, which is rounding noise of about 10⁻³⁴ C. The same worlds without the S2 operators differ from their own runs by up to 1.3 × 10⁻¹³, in the same fields, so the difference is the vmapped program's, not S2's | runs, s2-vmap/probe.json |
| Catalogue-metadata invariance | Bindings, batch signature, the step's jaxpr and the trajectory bitwise; the summary and the definition carry the references | smoke, runs |
| Padded slots | Idle view bitwise; one half-step closes every ledger (two clamps, cleft onset) | smoke |
| Existing compositions unchanged | Crossrev against 8416a72: base 36/36 jaxprs and 12/12 bindings, qualification 78/78 and 56/56, identical; 17 saved runs bit-identical; composite files pass (contract 15, adapter 5, injection 9 and 3, step checks 37, identity 9, water 15, replacement 17). Unit: 57 min CPU, peak 3.7 GB, memory.events all 0 | s2-crossrev-*, s2-dumps, s2-tests |
| Targeted rerun at 965a804 | S2 smoke 12 and 22, runs 9/9 (288 s, the cap-edge idle guard included), contract 15, adapter 5, injection 9; the vmap probe. Unit: 6.8 min CPU, peak 2.1 GB, memory.events all 0 | s2b-tests, s2-vmap |
| Final rerun at 00672e8 (the onset masks selected by value) | Crossrev head side against the same frozen outputs: base 36/36 and 12/12, qualification 78/78 and 56/56, identical. This measures water's and replacement's programs and bindings unchanged after `CONFLICTS_VIEW` (603285a). S2 smoke 12 and 23 (worlds with and without an onset have the same shapes and batch signature), runs 9/9 (284 s); insertion's step cost. Unit: 8.4 min CPU, peak 2.2 GB, memory.events all 0 | s2d-crossrev-*, s2d-tests, s2-cost |
| R-full comparison | S3 | – |

## 4. Current injection as a general control

**Physics.** An electrode delivers a declared current I(t) into a cell compartment, and
the return flows through the clamped bath.
- **Carriers.** Each electrode declares its carrier fractions; none is hard-coded. The
  default is the rule registered for J1 (`rm_definition.injected_carrier_fractions` in
  `validation/division/j1_declared_inputs.json`): {K: 0.4912, Cl: 0.5088}, the
  free-solution proportion for a 3 M KCl filling (dLB74 p530).
- **Both polarities.** A positive current is K⁺ entering and Cl⁻ leaving the cytosol:
  ΔN_K = +f_K I Δt / F and ΔN_Cl = −f_Cl I Δt / F, for a total charge I Δt. A negative
  current reverses both.
- **Booking.** Supply and removal are both booked (`injection_supplied_fmol`,
  `injection_removed_fmol`), with the electrode's reservoir as source and sink.
- **Refusal.** The domain check refuses a step in which the cytosol cannot supply a
  removed carrier: its amount would fall below its floor within the half-step.
- Charge: it enters the cytosol; the clamps supply the image charge Δq_b, with work.
- Work: the source supplies W_src = ΔG_entities − W_clamps, the exact free-energy change
  of the cell less the clamps' work, booked as the declared work field
  `injection_work_pJ`. The membrane's response dissipates through @3's own heat.

### 4.1 How it enters: an operator with a split part (no @3 change)
- Operator `electrode_current_injection@1`; schedule `injection_controls` (piecewise-constant
  current per cell, per world).
- Entity writes: `amount_increment` ← (`injection_supplied_fmol`, `injection_removed_fmol`,
  `injection_charge_C`);
  `electrode_charge_transferred_C` ← `injection_image_charge_C`; `electrode_work_pJ` ← the
  clamps' work.
- Bookings are exact for each half-step (§1.3).
- RK4 "coupled": the rate joins the right-hand side.
- It is statically idle with no electrode. At I = 0 the half-steps select the inner value
  and never add a computed zero.

**Accuracy.** Strang splitting is O(dt²) on the transient. For the new membrane τ = RC is
about 0.5–1.8 ms (1.36–1.82 kΩ·cm² with c_new 0.4–1.0 µF/cm², design §4.2), comparable to
the step.

**First acceptance: Rm1 = 852 kΩ on the uncleaved egg**, against R-full's first pulse
pair. That egg ran 35 min at 1 ms cleanly. Its tolerance (step term + reference term) is
registered before the run. This test decides whether the split part is accurate enough or
the fallback below is needed.

**The cleft-egg study cannot run as first written.** At 1 ms the cleft egg is refused, and
RK4 fails the electrode ledger from the J1 state. It needs the recorded egg-scale gaps
closed, in this order:
1. **The 1e-20 C definition charge bound in `surface_tissue.check_definition`.** Egg-scale
   charges need a bound scaled to the charges, and this check gates the definition itself.
2. **`ENERGY_ATOL_PJ`.** An absolute energy floor is too small for egg-scale energies over
   a 35 min run.
3. **The explicit bound at 1 ms in the cleft transient.** It needs the step study at 0.5
   and 0.25 ms, or an implicit membrane–cleft term (design §5.4).
4. **RK4 electrode rounding,** for the RK4 reference comparison.

**Fallback: a second opt-in hook in @3, `cell_source`.**
- Default `None`, like the membrane-process hook. It takes the injected flux
  [species, cell] and the source's work rate, integrated in the explicit stages.
- The change to @3 is limited to the opt-in branch, guarded as in §4.3.

**Rejected:**
- a control field on @3: it changes @3's control type and every @3 binding;
- a versioned @3 successor (@4): heavier than needed, kept for a change of @3's physics;
- the existing membrane-process hook: it carries passive transmembrane fluxes with
  nonnegative heat, so a source's work would have to appear as negative heat.

**As built (cd2859d), with the lead's acceptance:**
- RK4 keeps the half-steps around the inner step ("split"), not "coupled". The coupled
  right-hand side takes operator rates on owned fields only, and injection writes @3's
  amounts. A dt study's step term captures the splitting error, and the stationary
  right-hand side leaves the forcing out.
- The free-energy terms are the replacement law's `_chemical` and `_electric`, imported
  until §1.1 gives @3's free energy a declared owner.

### 4.2 Guards for injection
- An idle injection equals the composition without it, bitwise (no electrode, and I = 0
  throughout).
- A tier-1 smoke test under 20 s.
- Both polarities; carrier fractions taken from the declaration; the refusal when the
  cytosol cannot supply a removed carrier.
- A single-cell analytic test: a linear membrane gives ΔV = I R_m at steady state. Its
  transient is compared at three step sizes.
- Ledgers: material, charge (image charge at the clamps) and energy (W_src − H − ΔG = 0)
  close.
- Restart across a current step; vmap with per-world currents.

### 4.3 Guards protecting the default paths (for §1.1's argument and the §4.1 fallback)
- @3's own test files pass unchanged. For §1.1, so do @1's and @2's, since they share
  `surface_pump.py`.
- Without the new argument or hook, each family's checked step, right-hand side and device
  checks trace to jaxprs identical to the frozen family's, with dt traced. This is
  composite_crossrev run on @1, @2 and @3 worlds across revisions.
- The empty composition equals @3 (the S1 identity tests).

## 5. L4 agreement for the composite (protocol draft; the driver is outstanding)

The plan's completion evidence is GPU agreement by tolerance, because L4 repeats are not
bitwise. It is a **backend variant** of each qualification's own registered protocol,
following `validation/betse/backend_variant.py`.

**Worlds and quantities:** each protocol's judged quantities.
- W1: the six trajectories' quantities at their records.
- W2: per arm and branch, volume, voltage, route cycles and the step-map correction,
  which have registered tolerances; and the stability classification, which the
  protocol judges by sign only (no tolerance on the growth rate).
- G2-Q1: the nine cases' compared quantities per record.

**Runs:** all from one clean snapshot of the landed head, x64.
1. The CPU reference: the judged CPU outputs, which the composite reproduces bit for bit.
   It is rerun on CPU from the snapshot rather than reused across revisions.
2. Two blind L4 runs, A and B.
3. One judged L4 run, C, after the variant is frozen.

One GPU process at a time, in the slot the lead gives.

**Measured terms:** per quantity and record, the maximum over samples of:
- the backend term |CPU − A|;
- the run-to-run term |A − B|.

**Variant tolerance** (the method's rule; never tighter than registered):
- W1 and G2-Q1: their tolerances are 3 × (registered terms), recorded per quantity and
  record (W1: step error at 1 ms + reference stability; G2-Q1: step + reference + rounding
  terms). So new tolerance = max(registered, up1(3 × (registered terms + backend + run-to-run))).
- W2: its stationary tolerances are fixed, not derived. So new tolerance =
  max(registered, up1(3 × (backend + run-to-run))).
- The classification and convergence of every W2 branch must match exactly.
- `up1` (round up to one significant figure) is reimplemented in the tissue driver. The
  method's `validation/betse/protocol_tolerances.py` imports BETSE-side modules, so a
  `validation/tissue` driver must not import it (AGENTS.md).

**Stop rule before run C.** If any backend term exceeds the registered terms it is added
to (W1's and G2-Q1's step and reference terms; for W2, its registered tolerance), stop.
Diagnose the GPU difference, and do not register the variant.

**Verdict (as the method judges):** each qualification's own judge, run on C against its
own reference with the variant tolerances, passes every item it passes on CPU.
- Not the verdict: C against the CPU result within the variant tolerance. For W1 and
  G2-Q1 the variant still carries the step-error term, so that test could hide a
  GPU-specific difference well above the measured backend term.
- Reported beside the verdict: the raw backend and run-to-run terms of C against CPU, per
  quantity and record.
- Discrimination ratios are rescaled where the protocol has them, and the
  non-discriminating lists are recomputed.
- The result, pass or fail, is recorded as the first L4 qualification of water and
  replacement as compositions.

**Driver (outstanding, `validation/tissue/composite_l4_agreement.py`).** Planned actions:
- `run --part {w1,w2,g2} --label NAME`: runs each part's worlds through the qualification
  drivers' own engine functions and saves the judged quantities;
- `terms`: computes the measured terms;
- `variant`: writes the variant protocol, PROPOSED until you register it;
- `judge`: runs each qualification's judge on C with the variant tolerances.

Its CPU-only parts and the CPU-against-CPU test are written once your gate frees CPU 4
(about 18:00). Nothing runs on the GPU until you give a slot.

It still needs:
- the three drivers' return shapes (`engine_observations`, `judge_arm`, `engine_records`);
- the mapping from saved quantities to each protocol's tolerance keys;
- a CPU-against-CPU test, where the terms are zero and the variant equals the registered
  protocol.

## 6. Decisions (review of 12 November)

| # | Choice | Decision |
| --- | --- | --- |
| 1 | The composite's model ID stays `resolved_pump_composite@1` through §1; new behaviour comes with new operator law IDs | Accepted. The identity is unchanged by declarations (Run identity, above) |
| 2 | §1.1: an optional field-list argument to the family's energy-bound function, default unchanged | Accepted; it waits for the plan-validation fix to land |
| 3 | §4: injection by a split part first | Accepted. The first acceptance is Rm1 on the uncleaved egg. Carrier fractions are declared per electrode (J1's rule as default), with both polarities, removal booked and a refusal |
| 4 | §2: newcomers keep the slot's declared impermeant content | Open, with §2, until the renewal assay asks |
| 5 | §3: capacitance kept as state alongside area | Accepted |
| 6 | §1.3: at most one in-step process per composition | Accepted |
| 7 | §5: the verdict is each qualification's own judge with the variant tolerances | Accepted, with the stop rule before run C |
| 8 | §3, R3: option (a), with a field-input provider refused above 64 field nodes | Accepted (13 November), from the measured cost; (b) or (c) before larger worlds |
| 9 | §3: the capacitor energy at a view is corrected in operator ledger terms; @3's balances stay on the declared layout | Accepted (13 November). The requirement is on the total, ½ Σ C V² − ½ Σ C0 V0²; the correction is derived against @3's actual term |

Rough effort:

| Part | Agent-days |
| --- | --- |
| §1 | 1.5 |
| §4 | 1 |
| §3 (as the division plan estimates) | 2 |
| §2, when the renewal assay needs it | 1.5 |
| §5 driver | 0.5 |
| §5 GPU runs | the slot you give |
