# Composite v2: contract hardening, the entity volume ledger, membrane state, current injection

**Status: proposed design, for review before any code (D142).** It serves two gates of the
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
1. contract hardening (§1), which everything else uses;
2. current injection (§4), which is small and unblocks the Rm pulse response against
   R-full;
3. stage S2, membrane state and insertion (§3);
4. the entity volume ledger and water plus replacement (§2), built when the renewal assay
   needs it (D144). Its contract parts come with §1.

Plus the L4 agreement (§5).

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

## 1. Contract hardening

### 1.1 Energy roles declared, not recognised by suffix

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
- It refuses two operators replacing the same column, and an operator replacing another
  operator's column.
- The assembly checks that each operator returns exactly its declared keys (host side, on
  every row).
- Water@2's energy columns become a declared `REPLACES`.

### 1.3 Combination rules checked when a composition is built

Each rule is a build-time check with a refusal message.

| Rule | Check |
| --- | --- |
| **Fluxes add** | Several writers of one entity field each book their own accumulators. The owner's ledger closes with the sum over writers (Δx = Σ booked terms). Split-part rates add in the RK4 coupled right-hand side. In-step processes stay at most one per composition: @3's hook returns one applied transfer, so two processes could not be booked separately. Current injection does not need the hook (§4). |
| **Factors multiply** | `CONTROL_FACTORS`, a product in declared order (exists). |
| **One provider per view field** | Exists. New `VIEW_READS`: an operator that needs the current value (replacement@2 reads volume) declares it, in place of `CONFLICTS_VIEW`. The reader must follow the provider in the list. |
| **Events replace and book** | For every field an event map writes, it declares either: <ul><li>removed and supplied accumulators (`EVENT_REPLACES`), for conserved quantities (material, charge, volume, area, abundance), wired into the owner's ledgers; or</li><li>an intensive reset (`STATE_RESETS`, gates only).</li></ul> It also books: <ul><li>the change of the summed free energy of the replaced entities, as supplied work (§1.1);</li><li>the image charge at the clamps, with its work Σ φ_b Δq_b, as replacement does today.</li></ul> |
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
| R3, derived arrays | Arrays derived from R2 inputs (the field arrays) are recomputed on the device only when an input changed in that step; otherwise the bound arrays are selected, so the result is bitwise when idle. |
| R4, when evaluated | After events; after the first split halves for providers whose view follows their split part; held through the inner step (Strang); re-checked at the step end. |
| R5, definition-time checks | Explicit step bounds, rounding floors and admission checks that depend on an R2 input are computed at the schedule's declared worst case (the largest area and abundance an insertion schedule reaches). Otherwise they move into the step's domain check as a refusal. They are never taken silently from the initial value. |
| R6, host consumers | Observations, checks and summaries recompute the view from each saved row (as `observe_history` does). |
| R7, restart | A view is a pure function of state and the bound layout, so restart saves nothing more. |
| R8, anchors | Increments from declared values; zero increments reproduce the declared values bit for bit. |

**Audit before code:** list @3's layout quantities that its binding derives from area,
capacitance or abundance. Each becomes an R2 view or is refused when its input is
state-dependent. Known so far:
- `initial_cell_charge_C`: the charge anchor, already a view field;
- the field arrays (R3).

**S2 guards:**
- idle membrane state equals the composition without it, bitwise;
- insertion at r = 0 equals idle;
- one-patch analytic checks: |Vm| falls by C/(C + ΔC) at fixed charge, and
  H = ½ q² ΔC / (C (C + ΔC));
- image-charge booking, and the energy ledger ΔU = W − H;
- restart across onset and insertion; vmap;
- the catalogue-metadata invariance above;
- R-full comparison in S3.

## 4. Current injection as a general control

**Physics.** An electrode delivers a declared current I(t) into a cell compartment. A
declared ion species (z) carries it from an external source (the pipette's reservoir), and
the return flows through the clamped bath.
- Amounts: ΔN = I Δt / (zF), booked as `injection_supplied_fmol`.
- Charge: it enters the cytosol; the clamps supply the image charge Δq_b, with work.
- Work: the source supplies W_src = ΔG_entities − W_clamps, the exact free-energy change
  of the cell less the clamps' work, booked as the declared work field
  `injection_work_pJ`. The membrane's response dissipates through @3's own heat.

### 4.1 How it enters: an operator with a split part (no @3 change)
- Operator `electrode_current_injection@1`; schedule `injection_controls` (piecewise-constant
  current per cell, per world).
- Entity writes: `amount_increment` ← (`injection_supplied_fmol`, `injection_charge_C`);
  `electrode_charge_transferred_C` ← `injection_image_charge_C`; `electrode_work_pJ` ← the
  clamps' work.
- Bookings are exact for each half-step (§1.3).
- RK4 "coupled": the rate joins the right-hand side.
- It is statically idle with no electrode. At I = 0 the half-steps select the inner value
  and never add a computed zero.

**Accuracy.** Strang splitting is O(dt²) on the transient. For the new membrane τ = RC is
about 0.5–1.8 ms (1.36–1.82 kΩ·cm² with c_new 0.4–1.0 µF/cm², design §4.2), comparable to
the step. The S0b Rm pulse response (design §9) compares 1,
0.5 and 0.25 ms against R-full. If the steady ΔV error at 1 ms exceeds what J1 needs, take
the fallback.

**Fallback: a second opt-in hook in @3, `cell_source`.**
- Default `None`, like the membrane-process hook. It takes the injected flux
  [species, cell] and the source's work rate, integrated in the explicit stages.
- The change to @3 is limited to the opt-in branch, guarded as in §4.3.

**Rejected:**
- a control field on @3: it changes @3's control type and every @3 binding;
- a versioned @3 successor (@4): heavier than needed, kept for a change of @3's physics;
- the existing membrane-process hook: it carries passive transmembrane fluxes with
  nonnegative heat, so a source's work would have to appear as negative heat.

### 4.2 Guards for injection
- An idle injection equals the composition without it, bitwise (no electrode, and I = 0
  throughout).
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

**Verdict (as the method judges):** each qualification's own judge, run on C against its
own reference with the variant tolerances, passes every item it passes on CPU.
- Not the verdict: C against the CPU result within the variant tolerance. For W1 and
  G2-Q1 the variant still carries the step-error term, so that test could hide a
  GPU-specific difference well above the measured backend term.
- Reported beside the verdict: the raw backend and run-to-run terms of C against CPU, per
  quantity and record.
- Discrimination ratios are rescaled where the protocol has them, and the
  non-discriminating lists are recomputed.

**Driver (outstanding, `validation/tissue/composite_l4_agreement.py`).** Planned actions:
- `run --part {w1,w2,g2} --label NAME`: runs each part's worlds through the qualification
  drivers' own engine functions and saves the judged quantities;
- `terms`: computes the measured terms;
- `variant`: writes the variant protocol, PROPOSED until you register it;
- `judge`: runs each qualification's judge on C with the variant tolerances.

It still needs:
- the three drivers' return shapes (`engine_observations`, `judge_arm`, `engine_records`);
- the mapping from saved quantities to each protocol's tolerance keys;
- a CPU-against-CPU test, where the terms are zero and the variant equals the registered
  protocol.

## 6. Open choices for the lead
1. The composite's model ID stays `resolved_pump_composite@1` through §1, since every
   existing result stays bitwise; new behaviour comes with new operator law IDs.
2. §1.1: an optional field-list argument to the family's energy-bound function (default
   unchanged), rather than reproducing the bound inside the composite.
3. §4: injection by a split part first, with the S0b step study deciding whether the @3
   opt-in source hook is needed.
4. §2: newcomers keep the slot's declared impermeant content in the first slice.
5. §3: capacitance kept as state alongside area, or derived from area (my proposal: state).
6. §1.3: at most one in-step process per composition, until @3's hook can return one
   applied transfer per process. This narrows "fluxes add" for in-step processes; split
   parts and the RK4 coupled right-hand side do add.
7. §5: the verdict is each qualification's own judge with the variant tolerances, as the
   method judges; C against CPU is reported but not judged.

Rough effort:

| Part | Agent-days |
| --- | --- |
| §1 | 1.5 |
| §4 | 1 |
| §3 (as the division plan estimates) | 2 |
| §2, when the renewal assay needs it | 1.5 |
| §5 driver | 0.5 |
| §5 GPU runs | the slot you give |
