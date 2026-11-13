# Composite v2: contract hardening, the entity volume ledger, membrane state, current injection

**Status: reviewed by the lead and the advisor on 12 November; code starts after this
revision is merged (D142).**
- Decisions 1, 5, 6 and 7 are accepted.
- Decisions 2 and 3 are accepted with the changes made here.
- §2 was designed on 13 November and waits for the lead's and the advisor's review before
  any code. Its contract parts (`VIEW_READS`, `ACCEPTS_WRITES` and `EVENT_REPLACES`) were
  approved and built with §1. Decision 4 is settled for donor copies by
  [E07_V1_DESIGN.md](E07_V1_DESIGN.md) §2. §2.2 carries it into @2: water's impermeant amount by
  declaration, and the charged impermeant species through a list in @2's declaration (proposed,
  §2.10 question 5). Decisions 10–12 are proposed.
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
5. the entity volume ledger and water plus replacement (§2): designed 13 November, with
   code after review. Its consumers are the composition gate and E07's donor-copy arms run
   past the fixed-volume budget (§2, D144).

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

## 2. The entity volume ledger: water plus replacement

**Status: designed 13 November for the lead's and the advisor's review; no code yet.** Its
contract parts (`VIEW_READS`, `ACCEPTS_WRITES`, `EVENT_REPLACES`) were built with §1. The
composite already does the rest of what §2 needs: event maps run first and views are evaluated
after them, an accepted writer's terms enter the owner's ledgers (§1.4), and a refused step
returns the full start state. §2 changes no composite code.

**The consumer.** The registered E07-v1 does not need §2: it runs at fixed volume and is judged
by 70 min after the cue. §2 serves:
- the composition gate's completion evidence ([CURRENT_PLAN.md](CURRENT_PLAN.md));
- E07's donor-copy arms ([E07_V1_DESIGN.md](E07_V1_DESIGN.md) §3 (a)) run past about 95 min of
  inherited loading. At fixed volume a D lineage's osmotic excess reaches the 15% censor there
  (E07_V1_DESIGN §2). Under water the loading becomes swelling, and the copies need replacement
  over water.

Its runs are labelled development until a protocol for the composition is registered (D143).

**Today the composition is refused.**
- Water provides `volume` and `extracellular_volume`, and replacement@1 declares both in
  `CONFLICTS_VIEW`. Its parser requires a template's volume to equal the slot's declared volume,
  and its `law_steady` arrival gate solves the field at the declared volumes.
- Both declare `membrane_area` in `CONFLICTS_VIEW`, since water's conductances and the
  templates' pump densities are bound from declared areas. Neither provides it, so the two do not
  conflict there.
- Water's RK4 part is coupled, and a coupled RK4 composition refuses event maps. The
  composition is IMEX only, and stays so.

### 2.1 A new law, `scheduled_cell_replacement@2`

Replacement@1 is unchanged. @2 is @1 over a volume owner: the same event map, formation law,
templates, donor rule, route values and bookings, plus the slot's volume and water's free
energy. Its declarations beyond @1's:

| Item | @2 |
| --- | --- |
| `REQUIRES` | `ideal_osmosis_linear_compliance_water@1` before it (the symport's precedent) |
| `VIEW_READS` | `volume`, read through water's own function (insertion and the lumen read membrane state's the same way) |
| `CONFLICTS_VIEW` | `membrane_area` (pump densities scaled by the declared area, as in @1), and the capacitances and activity masks that @1's event map reads from the declared layout: `membrane_capacitance`, `active`, `outside_active`, `membrane_active`, `channel_active`, `junction_active` (§2.7). `volume` and `extracellular_volume` leave the list |
| Declaration, added | `impermeant_species`: species IDs whose content every newcomer keeps from the slot's declaration (an explicit list, possibly empty; §2.2) |
| Owned state, added | `replacement_volume_removed_pL` and `replacement_volume_supplied_pL` (cell slot, ≥ 0); `replacement_water_free_energy_pJ` (cell slot, signed) and `replacement_water_energy_magnitude_pJ` (cell slot, ≥ 0). All are zero for founders |
| Layout, added | `template_volume_pL` [template rows]: each template's declared volume (padding 1.0, never selected); `replacement_impermeant` [species]: the declared impermeant species |
| `ENTITY_WRITES` and `EVENT_REPLACES`, added | `volume_increment_pL` ← (`replacement_volume_removed_pL`, `replacement_volume_supplied_pL`) |
| On water | `ACCEPTS_WRITES = {volume_increment_pL: (water_local, water_total)}`. Without a writer nothing changes (§1.4): no ledger term, and the same field map |
| Refused | `gate_at_arrival: law_steady` (§2.6, decision 11); RK4, as today |

### 2.2 Newcomers declare volume and contents

**Templates.** @1's templates already declare `volume_pL` beside their amounts, fixed charge
background and gates, and @1's parser requires it to equal the slot's declared volume V0. Under
@2 it is the newcomer's volume on arrival, and it may differ from V0:
- it lies strictly inside the slot's water bounds. This is checked with the definition, and
  again by water's domain in the event's step;
- the fixed charge background still equals the slot's, since @3's charge anchor is a
  declaration (@1's rule);
- the template's state at its own volume lies in the composition's domain. This is @1's host
  check at the template's first slot, run with @2's event map.

**Donor copies take the donor's volume (decision 10, proposed).** E07_V1_DESIGN §2 proposed this
and left the choice to §2. The alternatives are the slot's declared volume V0 and the occupant's
volume V_old.
- **A copy is a copy of state** (D139, [CELL_REPLACEMENT.md](CELL_REPLACEMENT.md)). Under water
  the volume is state too. The donor's amounts in any other volume would make a cell that never
  existed, the same objection E07 §2 makes to mixing impermeant contents.
- **What E07 asks about is intensive:** concentrations, voltage and gates. The donor's volume
  keeps all of them.
  - V0 would scale the copy's concentrations by V_d/V0 (1.03–1.06 at 70 min in W1's water arms)
    and start an osmotic transient made by the bookkeeping, not by biology.
  - V_old would mix the occupant's volume with the donor's contents.
- **The accounting matches the amounts.** The donor keeps its volume, and the copy's volume is
  supplied and booked, as its amounts are.
- **It is exact.** The donor's declared volume and water compartment equal the slot's (admission,
  below), so the copy's volume increment is the donor's and its volume is the donor's bit for
  bit. Its amounts are @1's copy, (reference + increment of the donor) − the slot's reference.
  That subtraction is exact when each amount lies within a factor of 2 of the slot's reference
  (Sterbenz), and then the copy's amounts, concentrations, water potential and water free energy
  are the donor's bit for bit too; otherwise they agree to rounding.
- **The limit stays @1's.** A real division halves the donor. The copy models a division-born
  newcomer's composition, not the division's mass balance.

**Admission of a donor copy.** @1's conditions still hold: a shared junction, the slot's declared
volume and fixed charge background, and one population of each gated law. @2 adds one: the
donor's water compartment declaration equals the slot's (reference volume, bounds, impermeant
amount, bulk modulus and pressure offset). The copy keeps the slot's routes, hydraulic
permeabilities included, as @1's copy keeps the slot's channel routes.

**Decision 4, as E07_V1_DESIGN §2 settles it for donor copies.**
- **Water's neutral impermeant amount X** (`impermeant_amount_fmol`) is a declaration of the
  slot's compartment, not state.
  - Every newcomer keeps the slot's X. A template cannot declare one, and a donor copy is
    admitted only when the donor's compartment, X included, equals the slot's.
  - So the copy's water state (N, X, V) is the donor's and is never mixed.
  - A different X needs water-owned impermeant state, a later extension.
  - This settles decision 4 for both kinds of newcomer.
- **The charged impermeant species (E07's P)** is an amount, and a copy takes the donor's
  amounts exactly. E07 §2 settles that the newcomer gets the slot's declared content, and gives
  the refusal of a differing donor to @2's definition check. §2 carries that into @2 from
  declarations, as E07's driver already checks it (`validation/tissue/e07_v1_run.py`: every
  cell's declared P equals the template's). The engine is not asked to classify routeless
  species; the definition names them (proposed; open question 5).
  - @2's `impermeant_species` lists them.
  - When the definition is checked, each listed species must have no route of @3's in the
    replaced slots or their donors (a zero membrane and junction permeability, channel relative
    permeability and pump stoichiometry). Each donor's declared amount must equal the slot's, and
    each template's amount must equal the declared amount of every slot it fills.
  - By induction over the events, every cell then holds its declared amount of a listed species
    at every event, so a copy always brings the slot's declared content.
  - The event also checks it (§2.3, step 4), for any carrier the definition check cannot see,
    such as another operator's route. A differing copy refuses its step.

### 2.3 The event map

At the start of the step leaving t_e, for each due slot c, with V0 its declared volume and dv_c
its volume increment:
1. **@1's event map, called unchanged.** It removes and supplies the amounts, sets the gates,
   restarts the junctions and advances the generation. It books the image charge with its work,
   and @3's free-energy change in `replacement_free_energy_pJ`. Nothing in it depends on the
   current volume:
   - `capacitor_change` reads valences, amounts and the capacitor layout;
   - @3's chemical term is on the declared volume by definition (§2.5);
   - `law_steady`, whose field solve would read the volumes, is refused (§2.6).

   So under water its bookings are the view's.
2. **The volume.** V_old = V0 + dv_c, water's view. The newcomer's increment dv' is V_t − V0 for
   template t, or dv_d for a copy of donor d. The donor's is read before any event at t_e, as its
   amounts are. Then:
   - `volume_increment_pL[c] ← dv'`;
   - `replacement_volume_removed_pL[c] += V_old`;
   - `replacement_volume_supplied_pL[c] += V0 + dv'`.
3. **Water's free energy.** W_c is water's endpoint term of node c (§2.5), taken at the state
   before step 1 and after step 2:
   - `replacement_water_free_energy_pJ[c] += W_c(new) − W_c(old)`;
   - `replacement_water_energy_magnitude_pJ[c] += |W_c(old)| + |W_c(new)|`.
4. **The impermeant content.** For a donor copy, the copied amount of each listed impermeant
   species must equal the slot's declared amount exactly; otherwise the step is refused. Such
   amounts change only at events, so they are exact, and a definition that passed its check
   always passes this one.

Untouched entries are selected, never offset by zero. @1's fields are written by @1's own code,
in @1's order, and @2 writes only its own fields, so @1's fields come from @1's arithmetic alone.
Whether XLA compiles that arithmetic to the same bits inside the larger program is what guard 6
measures.

**Separate fields for water's share (decision 12, proposed).** The earlier draft of this section
added water's change to `replacement_free_energy_pJ` after @3's terms, and its magnitudes to
`replacement_energy_magnitude_pJ`. Fields of its own keep @1's accumulators out of @2's additions,
instead of relying on additions of exact zeros, and they show each owner's share of an event's
work. @2's `magnitude_terms` adds `replacement_water_energy_magnitude_pJ` to the energy magnitude
after @1's terms.

### 2.4 Volume in water's ledgers

Water accepts the write. @2 adds its terms (`external_ledger_terms`) and their magnitudes
(`external_magnitude_terms`) to water's ledgers (§1.4):
- per cell, `water_local − (supplied − removed)`: dv + (water moved out) − (supplied − removed)
  = 0;
- in total, `water_total − Σ(supplied − removed)`: Σdv + Σdve − Σ(bath supply) − Σ(supplied −
  removed) = 0;
- magnitudes: removed + supplied, per cell and in total. Each event adds about 2 V0 to the
  magnitudes, so the rounding allowance covers the rounding of V0 + dv at the event.

`water_outside` and `bath_water_work` are untouched, since an event changes no outside node.
Without events every term is an exact zero.

### 2.5 Free energy: dilution and elastic

**Water's endpoint term per node** is water's free-energy owner declaration of §1.1, built now.
It is taken against V0 at the current amounts, on finite nodes:

    W_j = −RT (Σ_s n_s,j + X_j) ln(V_j / V0_j) + P_j(V0_j) (V_j − V0_j) + ½ (K_j / Vref_j) (V_j − V0_j)²,

with P(V0) = K (V0 / Vref − 1) + P0. These are exactly the per-node terms that `water_ledgers`
sums into the energy ledger (the logarithm as log1p; 10⁻³ converts Pa·pL to pJ).

**The split is exact.** For the ideal solution G(n, V) = RT Σ_s n_s (ln(n_s / V) − 1), and
ln(n/V) = ln(n/V0) − ln(V/V0). So

    G(N, V) − G(N0, V0) = [G(N, V0) − G(N0, V0)] − RT (Σ_s n_s) ln(V / V0).

The first term is @3's own (`adapter.chemical_free_energy_pJ`, on the declared volume). The
second, with X's −RT X ln(V / V0), is water's dilution. There is no cross term. The event
therefore books as supplied work

    W_event = [Δ(@3 chemical) + Δ(capacitor) − W_clamps]  (@1)  +  ΔW_c  (@2).

That is the change of the slot's free energy from (N_old, V_old) to (N_new, V_new), elastic
energy included, less the clamps' work. @2 subtracts Σ `replacement_water_free_energy_pJ` from
the energy ledger after @1's terms, and the ledger closes across the event to rounding.

**Water's ledger code does not change.**
- The new per-node function mirrors its expressions, as the adapter's free-energy functions
  mirror @3's balances.
- A tier-1 test holds their sum equal to `water_ledgers`' terms to rounding.
- Refactoring `water_ledgers` to call it would reorder its traced operations and change
  water@1's and water@2's device-check jaxprs (open question 4).

### 2.6 Transport at the view, and refusal

**After an event, everything that depends on the volume reads the view.**
- The composite evaluates views after events (R4).
- Water's first half-step starts from (N_new, V_new).
- @3's step at the view sees N_new / V_new in every flux, the field's Newton solve, the drift
  weights and the explicit-stage refusal. This is water@1's existing path.
- The formation law reads no volume.
- @2's own reads of the volume (V_old, V_d) go through water's function, never through the
  declared V0.

**One declared-layout read is refused rather than moved (decision 11, proposed).** `law_steady`
solves the field at the post-event state inside @1's event map, on the declared volumes. With
floating components elsewhere in the world, the junction voltages it reads can depend on the
volumes, through those components' offsets, which follow the currents. No consumer needs it over
water: E07 uses `law_open`. The extension
would have the composite pass its view to event maps that declare it, and @1's arrival gate take
that layout (open question 1).

**The update rules (§3) for the volume view:**

| Rule | §2 |
| --- | --- |
| R1 | Bound once: V0, water's declarations, the template volumes, the event table |
| R2 | The volume view is water's, from `volume_increment_pL`. The event writes it, and @2 reads it through water's function |
| R3 | The volume is not a field input, so the 64-node cap does not apply (E07's 127-cell sheet has 254 field nodes). Nothing derived from the volume is bound, apart from the definition-time bounds (R5) |
| R4 | Events first and the view after them; @3's domain at the view, re-checked at the step end (water's `VIEW_FOLLOWS_SPLIT`) |
| R5 | @2's bound checks add the product of the two worst cases, which neither existing check covers. One is @3's explicit-rate and calcium bounds on @1's worst-case template routes at water's minimum volumes: water's checks read the declared routes, and @1's the declared volumes. The other is water's relaxation rate at each template's post-event state. @2's `inner_check_spec` applies @1's route maxima to the incoming check spec instead of discarding it |
| R6 | Observations recompute the view from each saved row: the row after the event shows V_new and N_new / V_new in water's columns |
| R7 | Restart saves nothing more: the volume is state |
| R8 | Anchored at V0: a template at V0 writes dv' = 0.0, an exact zero |

**Refusal.** A template volume outside water's bounds is refused when the definition is checked.
In a step, water's first half-step refuses a state outside its domain. The composite then
returns the full start state, water's volume and @2's accumulators included (the existing path;
guard 10).

### 2.7 How §2 uses the precedents

- **Booking at the view (`BOOKS_AT_VIEW`).** Injection composed with insertion by booking the
  clamps' plate charges and the capacitor energy at the composite's view. Replacement is the
  remaining declared-layout booker.
  - @2 books at the view what it reads there, the volume: water's terms at V_old and V_new.
  - Its capacitor bookings stay @1's, on the declared layout. That layout is the view, because
    @2 refuses every provider of capacitances and masks (`CONFLICTS_VIEW`). Today
    `membrane_area` already excludes membrane state, and with it insertion.
  - Booking those at the view too, with `adapter.charge_energy_change` as injection does, is the
    extension for replacement during insertion. @2 does not declare `BOOKS_AT_VIEW` until then.
- **The update rules R1–R8,** as tabulated above. The new case is a view input written by an
  event rather than integrated by its provider's split part. R2 and R4 already cover it.
- **The capacitor-energy correction against @3's declared-array term (decision 9).**
  - S2 found that @3's capacitor term on the declared layout is not the physical energy once C
    changes, and derived the correction against @3's actual term.
  - The same derivation for the volume gives water's existing dilution term, with nothing left
    over (§2.5). The chemical potential separates in V; the capacitor energy does not separate
    in C.
  - So @3's balances stay on the declared layout, water owns the correction, and an event books
    the change of the sum of the owners' terms, never @3's declared term alone.
  - The restricted lumen (S3) uses water's expression the same way.
- **An earlier owner required, and read through its own function.** The symport requires water,
  and insertion and the lumen read membrane state through its functions. @2 does both for water.

### 2.8 Files

| File | Change | Qualified code |
| --- | --- | --- |
| `src/cells/models/operators/cell_replacement_v2.py` | New: @2, a subclass of @1's operator, with its event map, ledger terms, domain, checks and observation | New |
| `src/cells/models/operators/__init__.py` | Register @2 | The registry; no program changes |
| `src/cells/models/operators/osmotic_water.py` | `ACCEPTS_WRITES`, and a new `node_free_energy_pJ` that water itself does not call | Water@1's and @2's module; no existing function changes |
| `src/cells/models/operators/cell_replacement.py` | `worst_case`'s route maxima applied to a given definition, and `check_definition` and `apply_events` taking the event function, each an optional argument whose default is @1's own code. `apply_events` also runs on the device; with the default its trace is unchanged (guard A) | @1's module |
| `src/cells/core/cell_replacement_spec.py` | `parse_events` and `check_template_on_slot` take the template-volume rule, with @1's as the default. The file is under this round's core/ restriction, so this needs approval; otherwise @2 duplicates the event parser (open question 2) | @1's parser |
| `src/cells/models/operators/current_injection.py` | Only if open question 6 is accepted: `volume` added to `CONFLICTS_VIEW`, a declaration that refuses injection over water and changes no program | Injection@1's module (Rm1); covered by guard A |
| `validation/tissue/composite_crossrev.py` | A new `volume` world set (water with @2) for later baselines, added on top of the extended tool (constants) once it lands on main; the existing sets are unchanged | Tool |
| `validation/tissue/cell_replacement_fixtures.py`, `tests/replacement_water_fixtures.py` | `over_water`, the [water, @2] definition builder; the test worlds | Fixtures |
| `tests/unit/test_cell_replacement_v2.py`, `tests/unit/test_cell_replacement_v2_runs.py`, `tests/test_tiers.json` | Tier-1 smoke, compiled runs, and the tier rows (re-measured) | New |
| `docs/PUMP_COMPOSITE.md`, `PROGRESS.md` | The operator table's row; status | Docs |

Not changed: the composite, the adapter, `surface_tissue.py`, `surface_pump*.py`,
`src/cells/numerics/`, `src/cells/core/` apart from the parser above, and the thin modules (@2
has no frozen model).

### 2.9 Guards

**A. Shared qualified code (D148).** Every touched function is new, host side or a declaration,
so no program of a qualified composition is expected to change. The check is registered with
its stop rule before its runs, comparing §2's head against main at the landing commit:
1. crossrev against the baseline the S3 agent renews at main's landing commit (D148's fourth
   criterion): every jaxpr and binding of the base, qualification and injection sets identical,
   and the 17 dumps bit-identical;
2. the forward guard (`validation/tissue/inplace_fix_guard.py`, its 58 worlds in the scalar,
   windowed, vector-window and batch programs): physical fields bitwise (the first criterion),
   and here the ledger accumulators too;
3. the registered judges, each compared with its rerun at main, every number identical apart
   from provenance and timing (the second criterion):
   - W1 (`pump_water_qualification.py`): trajectories and stationary step maps;
   - W2 (`pump_water_kcc_qualification.py`): the eight arms and their step-map numbers;
   - G2-Q1 (`cell_replacement_judge.py`): Q1 to Q7;
   - Rm1 (`injection_rm1.py`).

   W1 and W2 run although no water program is expected to change: a summation-order change
   moved their step-map numbers once (§3, prerequisite (c));
4. the qualified models' own test files and the composite test files pass.

Any difference stops the work, and is reported. Under D148 the change then needs a new ID or the
user's decision. These runs take a few hours of detached CPU time.

**Guard A as registered (13 November, in the commit that adds §2's code, before any A run).**
- **Sides.** Before: main 4465b48, from the S3 agent's clean snapshot
  (`/mnt/workspaces/Cells/cell-division-s3-20261113-01/snapshot-main-4465b48`). After: the
  registering commit, from its own clean snapshot (`composite-v2-s2-20261113-01/snapshot-after`).
- **Qualified code this commit touches.** None of these changes the arithmetic of a qualified
  program:
  - `osmotic_water.py`: `ACCEPTS_WRITES` and the new `node_free_energy_pJ`, which water never
    calls;
  - `cell_replacement.py` (@1): `worst_case`, `check_definition` and `apply_events` take an
    optional argument whose default is @1's own code. `apply_events` also runs on the device;
    with the default its trace is unchanged;
  - `current_injection.py`: `volume` in `CONFLICTS_VIEW`, a structure refusal;
  - `core/cell_replacement_spec.py`: the template-volume keyword, default @1's rule;
  - the registry, the cell-replacement fixtures (one new function) and `composite_crossrev.py`
    (a new `volume` set; the other sets unchanged).
- **Crossrev.** The after side's jaxprs and bindings of the base, qualification and injection
  sets are compared with the baseline of record,
  `/mnt/workspaces/Cells/cell-division-s3-20261113-01/crossrev-landing/baseline-of-record.json`
  (outputs `crossrev-landing/{base,qualification,injection}/4465b48`; 8416a72 stays the earlier
  record). Every jaxpr and binding must be identical. The new `volume` set is recorded at the
  after side as its first record.
- **Forward guard.** `inplace_fix_guard.py` dumps every part at both sides (the 825-node world in
  its own unit), and its compare must find every state field, observation column and diagnostic
  identical in every world, ledger accumulators included.
- **Judges.** W1, W2, G2-Q1 (Q1–Q4, Q5–Q7) and Rm1 at both sides. Every number must be identical
  apart from provenance and timing, under `compare_judges.py`'s rules (the S3 fix's tool).
- **Tests.** The composite, frozen-model and new test files pass at the after side.
- **Outcome.** (A) All identical: §2's code changes no qualified program, and lands under D148.
  (B) Any difference: the queue stops at a crossrev difference, and every other difference is
  reported. The work stops there; under D148 the change then needs a new ID or the user's
  decision.
- Scripts: `composite-v2-s2-20261113-01/scripts/guard_a.sh` (parts crossrev, guard, guard825,
  compare, judges, tests).
- **Amended by the lead (13 November, 18:10), after A.1's first run.** Crossrev compared neither
  closed-over constant values nor the check constants in bindings, so a constant that only gates
  acceptance could change unseen. The crossrev tool gains constant digests, and the baseline of
  record is re-taken with them at main. A.1 runs again against that re-taken baseline. The first
  A.1 run, against the 4465b48 baseline (identical in all three sets), stays as evidence and is
  superseded. The forward guard, the judges and the tests stand as registered.
- **A.1 as re-registered (13 November, before its rerun).**
  - Baseline of record:
    `/mnt/workspaces/Cells/cell-division-s3-20261113-01/crossrev-constants/baseline-of-record.json`,
    with outputs under `crossrev-constants/{base,qualification,injection}/main`. It was taken at
    main 7a8b538, whose src and crossrev fixtures are 4465b48's.
  - Tool: the extended `validation/tissue/composite_crossrev.py` of commit aaa0044 (the copy beside
    the baseline), run from the after side's snapshot as before. It also compares every constant
    each traced program closes over, and the device-check constants.
  - Pass: every jaxpr text, constants file and binding of the three sets identical to the
    baseline. Any difference stops the work, as registered above.
  - The `volume` world set leaves this commit's `composite_crossrev.py`: three agents write that
    file, so the set returns on top of the extended tool once it has landed on main, and is
    recorded then with constants.

**B. The new composition.** A tier-1 smoke test under 20 s covers the NumPy event map and
ledgers, the analytic checks and the refusals. The compiled runs go in tier 2 or 3.

5. **Idle:** [water, @2] with no event equals [water] bitwise: every state field, observation
   column and `max_` diagnostic, under open water, with Euler and ARS(2,2,2), on the heredity cell
   and a gated sheet.
6. **Reduction to @1:** [closed water, @2] with templates at V0 and donor copies equals [@1] on
   the shared fields, bitwise. @2's volume accumulators hold V0 per event, and its water free
   energy and its magnitude are exactly 0. If XLA's fusion moves a booked accumulator by rounding,
   the cause is pinned down before any tolerance is accepted (S1; §3, prerequisite (c)).
7. **Analytic one-event checks** (NumPy). An occupant swollen or shrunk to V_old ≠ V0, with a
   changed composition, is replaced by a template at V_t ≠ V0 and, separately, by a donor copy:
   - dv', removed and supplied are as in §2.3, and water's local and total ledgers close;
   - the booked work equals G(N_new, V_new) − G(N_old, V_old) + ΔU + Δ(capacitor) − W_clamps,
     written out independently of the adapter and of water's code, to 10⁻¹² relative;
   - the copy's volume equals the donor's bitwise, and so do its amounts, water potential and
     water free energy, in a world built with every amount within a factor of 2 of the slot's
     reference (§2.2).

   Alongside, also NumPy: the sum of `node_free_energy_pJ` equals the dilution and elastic terms
   of `water_ledgers` to rounding, on random swollen and shrunk states. This test stands in for
   not refactoring water's qualified ledger code (§2.5).
8. **Ledgers across events** (compiled, with device checks on every row): a held-bath sheet under
   open water whose replaced cells have swollen or shrunk, with events of both kinds. Material,
   charge, electrode, energy and water's four ledgers all close.
9. **Later transport sees the newcomer's volume.** The step after an event reads N_new / V_new:
   the composite's readouts are compared with @3's own on a layout with volume V_new. Water's
   first flow equals the analytic Lp A (ψ(N_new, V_new) − ψ_out) to rounding.
10. **A refused event leaves the full prior state.** A layout whose template volume lies outside
    water's bounds (bypassing the definition check) gives an invalid step. Its returned state
    equals the start state in every field, water's and @2's included. So does a donor copy whose
    listed impermeant amount differs from the slot's (step 4). Each definition refusal of
    §2.1–§2.2 has its own test, including:
    - the combined R5 bound: a definition that passes water's bound and @1's worst-case bound,
      but whose template routes at the minimum volumes exceed the explicit-rate bound, is refused;
    - a listed impermeant species with a route, and a donor or template with a different declared
      amount of it.
11. **Restart** before, at and after an event, also through a written snapshot, is bitwise. The
    manifest's field owners name @2 as the writer of `volume_increment_pL`.
12. **vmap:** a vector-window batch with device checks and per-world events (template volumes,
    donor copies, none). It is bitwise against the same batch reversed, and within 10⁻¹² of each
    field's scale against single runs (the S2 precedent: the vmapped program compiles
    differently).
13. **Cost:** @2's step on the 127-cell sheet, event-free and with events, against water alone.
14. **Status:** runs are labelled development (`composition_status`). Qualification would come
    from a registered protocol against an independent reference, not from this slice. One
    candidate is R-full (`validation/tissue/cell_replacement_reference.py`) with open water and
    volume events.

### 2.10 Open questions for the lead

1. **`law_steady` over water.** Proposed: refused in this slice. The alternative is for the
   composite to pass its view to event maps that declare it, and for @1's arrival gate to take
   that layout (a composite change and a static branch in @1's event map).
2. **The template-volume rule in `core/cell_replacement_spec.py`.** Proposed: a keyword whose
   default is @1's rule (host side, but under the core/ restriction). The alternative is a second
   event parser in @2's module.
3. **@1's host-side helpers** (`worst_case`, `check_definition`). Proposed: parameterised, with
   @1's behaviour as the default. The alternative is duplicating them in @2's module.
4. **Water's free energy per node.** Proposed: a new function beside an unchanged
   `water_ledgers`. The alternative, refactoring `water_ledgers` to call it, changes water@1's and
   water@2's device-check jaxprs and so needs D148's full run.
5. **E07's charged impermeant P in donor copies.** E07 §2 gives the refusal to @2's definition
   check. Proposed: honour it from declarations, as E07's driver does. @2 names its impermeant
   species, the definition check requires them routeless and their declared amounts equal, and
   the event checks the copy (§2.2, §2.3 step 4). The alternative departs from E07 §2: the engine
   refuses a differing X only, and E07's driver alone keeps its P check.
6. **Injection over water, found in this round.**
   - [water, `electrode_current_injection@1`] is admitted under IMEX. Injection books @3's
     chemical term on V0, but not water's dilution term.
   - A probe (composite-v2-s2-20261113-01/probe_injection_water.json) applied one half-step of
     1 nA for 0.5 ms. It left exactly −RT ΔN_tot ln(V/V0) unbooked: +1.15 × 10⁻⁵ pJ at 5%
     swelling (the prediction met to 5 × 10⁻¹⁶ pJ), and 0 at V0.
   - No test or registered run composes the two. An IMEX run's energy bound, 2 × 10⁻³ of the
     flows, may not catch it.
   - Proposed: injection@1 declares `volume` in `CONFLICTS_VIEW` now. That is a refusal and changes
     no program. An injection law that books ΔW with `node_free_energy_pJ` follows when a consumer
     needs injection under water.
7. **Decisions 10, 11 and 12:** the donor's volume, `law_steady` refused, and separate fields
   for water's share of an event's work.
8. **The renewed crossrev baseline** (guard A.1) is the S3 agent's, at main's landing commit.
   Its path enters the registered guard when the lead sends it.

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
| `face_factor` (D × area / length) | Per face | Fixed in S2 and in S3: the access A/L stays constant from activation, as in R-full (the lumen grows its volume only) |
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
- **(c) Found and pinned down 13 November: an electrode-ledger drift at egg scale. The fix
  waits for the lead's approval** (composite-v2-20261112-01/s3-prereq: electrode_diag*.json,
  electrode_mechanism.json and mechanism2/).
  - The symptom:
    - the uncleaved Rm1 egg, with its two pulses (0–12 s), run to 420 s at 1 ms, fails the
      host electrode ledger by 8.4 × 10⁻¹⁷ C, 5 times its bound;
    - with the electrode at zero current throughout, or with no operator, the ledger is
      exactly 0.
  - The ledger's two sides. Both come from `surface_tissue.capacitor_change` on the
    state's amounts; no flux or current enters either.
    - Booked: `electrode_charge_transferred_C`. @3's IMEX step adds
      `surface_pump.electrode_increment`, which is cap(end) − cap(start) at the held nodes.
      Injection's half-steps and replacement's events add the same difference when they
      change the state.
    - Recomputed: the held nodes' plate charges cap[n:] of the current state, in
      `surface_tissue.balances` (host) and `surface_pump_checks.tissue_balances` (device).
    - The bookings telescope only if every evaluation of a state's plate charge gives the
      same bits.
  - Where it breaks: the compiled step evaluates that one function differently at the
    start and at the end of a step. XLA leaves the order of a reduce unspecified.
    - The start's species sum Σ z_s n_s (`electrode_increment`, line 262) is merged by
      XLA with the identical sum in the start state's field solve
      (`surface_tissue.field_values`). That kernel adds in species order:
      (t_Na + t_K) + t_Cl, with t_s = z_s n_s.
    - The end's sum (line 263) is fused with the computation of the end state's amounts.
      That kernel is vectorized and adds its lanes as (t_Na + t_Cl) + t_K.
    - Each state is one step's end and the next step's start, so it is evaluated once
      each way.
  - Why the pulses and the knee matter:
    - the pulses leave t_Cl = 7.34 × 10⁻¹² fmol (P_Cl = 0, so nothing else moves Cl);
    - (t_Na + t_K) + t_Cl is exact here, because t_Na + t_K cancels exactly;
      t_Na + t_Cl rounds t_Cl at Na's ulp;
    - each step therefore books F (t_Cl − ulp(n_Na)): +6.2 × 10⁻²⁴ C below 2¹⁶ fmol, where
      t_Cl is 1.009 ulp, and −6.96 × 10⁻²² C above it, where t_Cl is 0.504 ulp;
    - with t_Cl = 0 both orders agree, which explains the exact zeros.
  - The evidence:
    - after the knee (history row 296,107), each step's booking equals the exact plate-charge
      change, in rational arithmetic on the saved amounts, plus −6.958102 × 10⁻²² C, with
      a spread of 10⁻³⁵ C over 400 steps;
    - summing F[((t_Na + t_K) + t_Cl) − ((t_Na + t_Cl) + t_K)] over the saved states from
      12 s to 420 s predicts the ledger's change, −8.44415674257 × 10⁻¹⁷ C, to 4 × 10⁻²⁹ C;
    - the compiled rollout's two kernels show the two orders (mechanism2/kernels.txt);
    - with the species sum written as explicit adds in species order, the ledger is
      exactly 0 at 12 s and at 420 s, and every other field of the 420 s state is
      bitwise identical. An optimization barrier between each state and its sum gives
      the same result.
  - A second exposure: the end's kernel recomputes the end state's amounts instead of
    reading them back. Here they agree bit for bit (the prediction above), but this is a
    second way the two evaluations could differ.
  - The proposed remedy is an exact one: one computation of each state's plate charge,
    in `surface_tissue.capacitor_change` (shared @3 code, so it needs the lead's approval).
    - It sums the species with explicit adds in species order, and on the device it puts
      an optimization barrier on the amounts it sums (s3-prereq/proposed/).
    - Tested as written (mechanism3/): the egg's ledger is exactly 0 at 12 s and at
      420 s, and every field of all 420,001 rows except `electrode_charge_transferred_C`
      is bitwise identical.
    - Installed in the injection, insertion and adapter test files, those files pass,
      including vmap and the composition with insertion at the view. Replacement's
      vector-window file also passes; it runs a vmapped batch with device checks.
    - Fields: none. Trajectories: unchanged, because capacitor_change feeds no rate
      (measured on the egg; elsewhere from the call graph).
    - Ledger fields: change at the rounding level where XLA's order differed.
    - Jaxprs: from the call graph, every checked step and device check that calls it
      changes, so the crossrev needs a run comparison and a new baseline.
    - Host values: unchanged where NumPy already sums in species order. That holds for
      every shape tried except a single column with 8 or more species, where NumPy sums
      pairwise.
    - Exact under three conditions:
      - valences are 0, ±1 or ±2, because the kernels contract z n into the accumulate,
        which is harmless only when z n is exact;
      - the solve keeps its zero boundary, because the end's kernel contracts
        F Σ − C·boundary into one fused multiply-subtract;
      - no held node couples to three or more charged free nodes. Such a node would
        expose the matrix product's node sum in the same way; neither the egg nor S3 has
        one.
  - On S3's path, with a field-input provider:
    - the bookings at the view are @3's step and injection, both through
      capacitor_change, and the remedy covers them;
    - insertion's image charge (`adapter.fixed_charge_change`) is computed directly, not
      as a difference of two evaluations;
    - the check's view term (`adapter.view_capacitor_terms`, through `node_potentials`) is
      evaluated once per row and has its own allowance, rounding × |absolute plate
      charges|, about 5 × 10⁻²⁵ C per step at egg scale. Unfixed, the drift (7 × 10⁻²² C
      per step) would exceed that allowance.
  - A step-scaled allowance would be the wrong kind. The residual is not the state's
    representable precision, and at 420 s the allowance would be 4 × 10⁻¹⁵ C, 250 times
    the present bound.
  - Not caused by this round's change (the crossrev above). The judged Rm1 ran 12 s and
    passed. S3's egg runs wait for (c).
  - **Approved 13 November as branch work, not to land yet.** It lands alone, in its own
    round, after the hold decision at the L4 gap and after any restart snapshot is
    frozen: it changes the hold model's step program, and `source-l4-05` lacks it.
  - **Stop rule, written before the comparison.** The fix is compared against no fix:
    snapshot-s3f (69df9f9) against the fix's snapshot.
    - Coverage: every qualified world in the crossrev base, qualification and injection
      sets, the 17 saved runs, the 825-node world, and @1 and @2, in their scalar,
      vmapped and vector-window programs.
    - Physical, for this rule: every state field except the ledger accumulators, every
      observation, and every diagnostic except the ledger residuals.
    - The ledger accumulators are `electrode_charge_transferred_C` and the fields booked
      from capacitor_change's plate charges and patch voltages: electrode work, image
      charge, and injection's and replacement's work and energy magnitude.
    - Clarified after the first parts: the observers record every state field as an
      observation column under its own name. Those columns count as the accumulators, as
      in the lead's definition of physical fields (state, observations and diagnostics
      other than the ledger accumulators). In the Rm1
      egg, `observations.electrode_charge_transferred_C` was the only column that
      changed. Every other observation, including the derived readouts (potentials,
      `electrode_charge_C`, residuals), stays physical.
    - If any physical bit changes in any qualified world, the fix is not admissible in
      place. It then needs a new ID or the allowance, which is the user's decision. The
      comparison is reported, and the work stops there.
  - **D148, an in-place fix to shared qualified code, is in DECISIONS.md, after D147.** It
    was decided by the lead on 13 November, accepting the exemption for ledger
    diagnostics. The draft that the stop rule applied is above.
  - **The stop rule triggered (13 November): the fix moves registered judge numbers.**
    Forward runs are identical, but W2's stationary judge changes.
    - Two outputs of W2's judge change at about 10⁻¹⁴ relative, fix against no fix: the
      step-map consistency corrections (one Newton step, J⁻¹(Φ_T(u) − u)) and their
      rounding floors. That is 43 numbers in 24 items (composite-v2-20261112-01/s3-fix/
      judges).
    - Unchanged: the residuals Φ_T(u) − u, bitwise in all 72 entries, and every verdict
      (pass).
    - W1's judge behaves the same way. Six step-map numbers in its two stationary items
      move by about 10⁻¹³ relative, and its verdicts are unchanged. Its trajectory items
      change only in ledger diagnostics: the electrode error goes to 0 and the
      global-charge ratios fall.
    - Rm1's judge changes only in ledger diagnostics.
    - The run without the fix reproduces the recorded judged run (10 November) bit for bit,
      and the only source change is `capacitor_change`. The moved quantity is therefore
      the step map's Jacobian J. The stationary analysis takes it by automatic
      differentiation through the checked step, and XLA compiles that derivative program
      differently once the booking's sums are explicit and behind a barrier.
    - By D148's draft this is not an in-place fix, because a judge's registered numbers
      change. It needs a new ID or the allowance, and that is the user's decision. The
      fix stays branch work, unlanded.
  - **Option 3, registered before any of its runs (13 November).** The species are added
    explicitly in species order, with no barrier (f91ce9d, snapshot-s3h), compared against
    snapshot-s3f (69df9f9) under the same stop rule.
    - Runs at s3h:
      - the forward guard's parts pump (@1 and @2), injection (the heredity cell, and
        Rm1 at 12 s) and egg (420 s), compared with the guard's s3f outputs;
      - the regression test;
      - the registered judges W1, W2, G2-Q1 (Q1 to Q7) and Rm1, compared with their s3f
        reruns, which reproduce the recorded judged runs. s3h runs Q2 as registered (it
        includes e1cc472). For Q2 the s3f baseline is the run with the constant supplied.
    - (A) Admissible under D148 only if all of these hold:
      - every physical field in those parts is bitwise identical;
      - the egg's host electrode ledger is exact: 0 at 420 s, and within one ulp of the
        plate charge on every row;
      - the regression test passes;
      - every number in the judges' outputs is identical, except provenance and timing
        and the residual diagnostics of the electrode, global-charge and energy ledgers.
    - (B) If the only numbers that move are Q2's `image_charge` and `free_energy`
      comparisons, which are booked from capacitor_change's plate charges and patch
      voltages, and every verdict holds, the result is reported and the lead decides.
    - (C) If anything else moves, the work stops, and options 1 and 2 go to the user.
  - **Option 3's outcome: A under the rule registered at c540fdb.** That rule exempts the
    residual diagnostics of the electrode, global-charge and energy ledgers; the lead rules
    on the exemption (s3-fix/opt3-outcome.json, classified by `classify_opt3.py`, written
    before the runs).
    - The judge outputs that the exemption covers, all of which changed:
      - W1: nine paths in three trajectory items. The electrode error goes to 0, and the
        global-charge bound ratios fall from about 5 × 10⁻⁴ to about 3 × 10⁻⁶;
      - Rm1: three paths. The electrode error falls from 2.0 × 10⁻²⁰ C to 0, and the
        global-charge error from 3.6 × 10⁻²⁰ to 1.6 × 10⁻²⁰ C, but the global-charge bound
        ratio rises from 0.0236 to 0.0241.
    - The global-charge ledger is the electrodes' transferred charge plus the reservoirs'
      supplied charge, and its bound uses the same magnitudes. So it depends on the fix only
      through the electrode accumulator; the supplies are physical and unchanged.
    - If the lead accepts the exemption, D148's second criterion should name it.
    - Everything else is identical:
      - W2 matches entirely, including the 43 step-map numbers the barrier moved, and W1's
        six step-map numbers match too. So the barrier alone moved the step map's Jacobian;
        the explicit adds do not;
      - G2-Q1 differs only in provenance, Q1 to Q7. Q2 was run as registered at s3h, which
        includes this option. Its numbers equal those of the s3f run with the constant
        supplied, and so the recorded ones.
    - The W1 and W2 "before" sides are today's s3f reruns, which reproduce the recorded
      judged runs.
    - The forward subset (seven worlds) is physically bitwise identical: @1 and @2 under
      RK4 and IMEX, the injection cell, Rm1 at 12 s, and the egg to 420 s.
    - The egg's ledger is 0 at 420 s and within one ulp of the plate charge on every one of
      its 420,001 rows (largest 9.4 × 10⁻³⁸ C). Here "exact" means within one ulp per
      row, not 0 on every row.
    - At s3h, the regression test and the judge-imports test pass (8 tests).
    - The barrier's protection against recomputed stage amounts is dropped. The docstring
      states the exposure, and the regression test guards it.
  - **Option 3's landing evidence (13 November), fix against no fix (s3f):**
    - Source: snapshot-s3i (f651bfe), option 3 merged with main 82f9308. Its src is option
      3's. The branch head 3d2e7a6 adds main e33ad71, which brings the Q2 re-export once,
      as its only further src change.
    - The full forward guard, all 58 worlds in every program: physical fields are bitwise
      identical (s3-fix/guard-s3i/compare.json).
    - Every ledger case (D148's third criterion):
      - `electrode_charge_transferred_C` changes in 18 worlds, each by its own unfixed
        residual. The largest differences are the egg at 420 s (8.4 × 10⁻¹⁷ C), Rm1
        (2.0 × 10⁻²⁰), W1's P2 from D and from H (2.7 × 10⁻²⁵ and 4.1 × 10⁻²⁶), and W1's
        P6 (6.9 × 10⁻²⁸).
      - The rest change by 10⁻³⁰ to 7 × 10⁻²⁸ C: W2's eight 1 s trajectories, the routes
        on and off, water, water_on, symport and symport_none.
      - Alongside: the electrode and global-charge residual diagnostics, and the device-check
        values of injection_rm1, symport, symport_none and water.
    - The composite test files at s3i all pass: the regression test 2, injection 12 and its
      runs 5, insertion 23 and its runs 10, adapter 5, and replacement vector 1.
    - Step time, s3f against s3i over four alternated runs each, by median (fastest in
      brackets):
      - the egg: 0.0511 (0.0485) against 0.0526 (0.0498) ms;
      - the 825-node world as @3: 49.4 (47.8) against 49.9 (46.9) ms;
      - with closed water: 48.8 (47.9) against 49.5 (47.1) ms.
      Compile times are unchanged, so the differences lie within the run-to-run spread.
    - The crossrev baseline, renewed at s3i (s3-fix/crossrev-s3i):
      - every jaxpr that traces capacitor_change differs: base 22 of 36, qualification 52
        of 78, injection 4 of 6. The counts are the same against 8416a72 and against
        f0c8e46;
      - the right-hand sides and every binding are identical: 12, 56 and 2.
      Retaken at the head (snapshot-s3j, 3d2e7a6), every jaxpr and binding matches s3i's,
      and the regression and judge-imports tests pass (8). It is retaken once more at the
      landing commit (D148's fourth criterion).
    - History: e32c20a introduced the barrier version, and f91ce9d supersedes it by
      removing the barrier. Their messages and this note record why.
    - Not run: the tier gate, which is the lead's landing gate.
  - **The barrier version's forward guard (s3g), fix against no fix: physical fields are
    identical**
    (composite-v2-20261112-01/s3-fix/guard/compare-final.json).
    - Setup: snapshot-s3f (69df9f9) against snapshot-s3g (e32c20a), run by
      `validation/tissue/inplace_fix_guard.py`. Peak memory was 3.2 GB.
    - Every state field, observation column, physical diagnostic and device-check flag is
      bitwise identical in all 58 worlds:
      - @1 and @2 worlds, under RK4 and IMEX;
      - crossrev's injection and base worlds;
      - the 17 saved runs, and the Rm1 egg to 420 s;
      - G2-Q1's nine cases and W37, with device checks on every row;
      - the 825-node world as @3, as its empty composition, with closed water and with
        event-free replacement;
      - Q6's cohorts, both as vector windows and as lax_map batches;
      - W1's six judged trajectories, through the windowed program.
    - `replacement_steady`, a base world, is refused by @3's dissipation check in both
      revisions alike. With its checks recorded rather than enforced, it is identical too.
    - Ledger accumulators: only `electrode_charge_transferred_C` changes, in 18 worlds.
      Each change is that world's own unfixed electrode-ledger residual, which the fix
      removes: 8.4 × 10⁻¹⁷ C for the egg at 420 s, 2.0 × 10⁻²⁰ C for Rm1 at 12 s,
      2.7 × 10⁻²⁵ C for W1's P2 from D, and 10⁻³⁰ to 7 × 10⁻²⁸ C elsewhere. After the fix,
      `max_electrode_charge_error_C` is 0 in each of these worlds.
    - The field solve's own charge sum is unchanged: in the egg's compiled program it is
      the same kernel, instruction for instruction (s3-fix/hlo-s3g).
    - Step time (medians of four runs each, before against after):
      - the egg: 0.0517 against 0.0516 ms;
      - the 825-node world: 48.5 against 49.9 ms as @3, and 48.3 against 50.4 ms with
        closed water. The fastest runs are equal (47.8 against 47.8 and 47.2 ms), so the
        difference lies within the run-to-run spread;
      - compile times are unchanged.
  - The same run gives the engine's energy bound used in (a). The pulses leave about
    0.45 pJ each in the energy residual, scheme error within IMEX's tolerance.

**The restricted lumen's fill (S3, `restricted_cleft_lumen@1`; the lead's ruling of 13
November).** The lumen's volume follows its patch's area, V = V_on + w (A − A_on)/2, and each
added dV fills with bath fluid, dn_s = c_b,s dV, with no water flow. Its energy budget:
- @3's free energy at the view is G(n, V) = RT Σ_s n_s (ln(n_s / V) − 1). The dilution term
  −RT N ln(V / V_on) (the water law's expression) brings @3's chemical term on the declared
  volume to it.
- The bath gives up W = Σ μ_b dn − Π_b dV. The first term is its solutes' supply work, booked as
  @3 books its own supply (the bath's `reservoir_supplied` and `reservoir_work_pJ`). The second
  is its fluid's volume work at the osmotic pressure Π_b = RT Σ c_b: the water law's bath water
  work at ψ_b = −Π_b.
- H = W − dG = RT Σ_s c'_s [V φ(c_s / c'_s) + dV φ(c_b,s / c'_s)], with φ(y) = y ln y − y + 1
  and c' = (n + dn)/(V + dV), is a Jensen gap: nonnegative, and zero at bath composition. It is
  the mixing heat of bath fluid entering a lumen of another composition.
- So dG = Σ μ_b dn − Π_b dV − H. −Π_b dV is booked in the declared work field
  `lumen_fluid_work_pJ` and H in the declared heat field `lumen_fill_dissipated_energy_pJ`.
  Without them the ledger misses RT c_tot dV per fill even at bath composition (3.26 × 10⁵ pJ by
  J1).
- An IMEX energy bound (2 × 10⁻³ of the flows) cannot see an error in these terms at egg scale.
  Their guards are a NumPy test of H against W − dG written out independently, and an RK4 run
  whose energy bound has no solver tolerance (S3 plan §1).

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
2. Three blind L4 runs, A, B and D (13 November: one L4 pair understated the spread; a third repeat exceeded it by up to 6×).
3. One judged L4 run, C, after the variant is frozen.

One GPU process at a time, in the slot the lead gives.

**Measured terms:** per quantity and record, the maximum over samples of:
- the backend term: the largest |CPU − X| over A, B and D;
- the run-to-run term: the largest difference between two of A, B and D.

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
- Reported beside the verdict: |A − C| over the run-to-run term, per quantity (the driver's
  `deviation` action).
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
| 4 | §2: newcomers keep the slot's declared impermeant content | Settled for donor copies in E07_V1_DESIGN §2 (13 November). Carried into @2 in §2.2: water's impermeant amount X is a declaration, and a donor copy needs the donor's water compartment to equal the slot's. The charged impermeant species are named in @2's declaration, checked from declarations and again at the event (proposed; §2.10, question 5) |
| 5 | §3: capacitance kept as state alongside area | Accepted |
| 6 | §1.3: at most one in-step process per composition | Accepted |
| 7 | §5: the verdict is each qualification's own judge with the variant tolerances | Accepted, with the stop rule before run C |
| 8 | §3, R3: option (a), with a field-input provider refused above 64 field nodes | Accepted (13 November), from the measured cost; (b) or (c) before larger worlds |
| 9 | §3: the capacitor energy at a view is corrected in operator ledger terms; @3's balances stay on the declared layout | Accepted (13 November). The requirement is on the total, ½ Σ C V² − ½ Σ C0 V0²; the correction is derived against @3's actual term |
| 10 | §2.2: a donor copy takes the donor's volume, an exact state copy | Proposed (13 November), for review |
| 11 | §2.6: `law_steady` is refused over water in the first slice | Proposed (13 November), for review |
| 12 | §2.3: water's free-energy change at events is booked in a field of its own | Proposed (13 November), for review |

Rough effort:

| Part | Agent-days |
| --- | --- |
| §1 | 1.5 |
| §4 | 1 |
| §3 (as the division plan estimates) | 2 |
| §2, after review | 1.5, plus a few hours of detached guard runs |
| §5 driver | 0.5 |
| §5 GPU runs | the slot you give |
