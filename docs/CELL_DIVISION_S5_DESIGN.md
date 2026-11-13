# Stage S5: partition, bridge closure, lineage and the R-ops (design)

**Status: reviewed by the lead and the advisor (13 November 2026); staging S5a and S5b
approved.** The decisions as taken are in §12. Code starts once two things are back:
- the probe of risk 1 (§13; its result is in §0);
- the constants-aware crossrev baseline, which the checkpoint agent is producing (§8.4).

S5a lands after the volume ledger (v2 design §2). The review's amendments are in §4.2, §5.5,
§8.2–§8.4, §10.1, §13 and Appendix A. Appendix A states the equations the independent
references are written from, without the engine's code.

Design basis: the [cell-division design](CELL_DIVISION_DESIGN.md) §2–§5, §8 and §9; the
[v2 design](PUMP_COMPOSITE_V2_DESIGN.md) §1–§4; the [S3 plan](CELL_DIVISION_S3_PLAN.md).
Evidence and log: `/mnt/workspaces/Cells/cell-division-s5-20261113-01/` (HANDOFF.md).

Marks as in the division design: **S** our arithmetic or interpretation.

## 0. Summary

**Purpose.** S5 is the engine side of milestone 1 of the lifecycle gate
([current plan](CURRENT_PLAN.md)): the physiology and accounting of a declared division
sequence, 1 → 2 → 4 cells, as prescribed divisions. It qualifies the engine against
independent references. It computes no DFS74 or J2 quantity: J2 and C1 stay held (§10).

**Engine models run.** `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with:
- `membrane_entity_state@1` (unchanged);
- `scheduled_membrane_insertion@2` (new version, §5.1);
- `restricted_cleft_lumen@2` (new version, §5.2);
- `isopotential_partition@1` (new, §3);
- `cytoplasmic_bridge_closure@1` (new, §4);
- `electrode_current_injection@1` (unchanged).

**Why S5 is larger than the four operators of design §4.2.** S2 and S3 were built for one
static topology. A partition changes the topology at run time, and three as-built facts follow
(§1):
1. @3 checks its domain at the layout it is given (the view), so a slot that a mask closes must
   hold exactly zero in every accumulator that mask covers. A pending daughter does. A retired
   parent does not: its history is nonzero.
2. Insertion@1 provides the activity masks itself, and both insertion@1 and lumen@1 compute at
   their own single-patch view. A second writer of masks breaks them.
3. The capacitor-energy correction at the view is insertion@1's ledger term today. The v2 design
   §3 already said it moves to the composite when a second writer arrives.

**The proposal in six points.**
1. **Activity closers.** Activity masks combine by conjunction, as availability factors
   multiply. Closure propagates down the entity hierarchy (cell → patches → populations;
   cell → contacts; node → faces), and the adapter presents every closed slot to @3 as padding
   (anchors and law codes read 0). The partition closes cells only; insertion@2 closes its onset
   patches and nodes (§2).
2. **Fresh daughter slots**, as design §5.2 decided. Every daughter anchor is declared at its
   exact fraction of the parent's declared anchor. Active slots then carry small increments,
   and a symmetric division is exact in floating point (§3.2).
3. **Retirement presents the parent to @3 as padding.**
   - Its amount increment moves to the daughters.
   - The @3 history of its patches, populations and contacts moves into the partition's
     retirement record.
   - Every @3 ledger and the dissipation check read the record added back (`adjust_inner`, the
     symport's precedent), so nothing in @3's own accounting changes (§3.5).
4. **Bookings follow the v2 contract.** Moved quantities are signed transfers that sum to zero.
   The free-energy change (the unmixing term, 0 for a symmetric division) is partition work;
   the rounding-level image charge is booked at the view. The composite owns the energy rule at
   the view. With a closer present, its reference is the view of the initial state, through
   two offsets bound once, so every ledger starts at zero (§3.6, §3.7, §5.3).
5. **The bridge** is an @3 junction between the daughters, with a constant-field law,
   P_s A = 2 a D_s and a fixed open gate. The closure is an availability factor a(t)/a_0 with
   exact half-steps. The partition's aperture a_0 is bounded by the step; the closure time is
   the physiological unknown (§4).
6. **New versions** `scheduled_membrane_insertion@2` and `restricted_cleft_lumen@2` work at the
   composite's view and admit partition-born patches. A lumen follows the summed area of its
   live facing patches (§5). Insertion@1 and lumen@1 stay registered and unchanged for S3's
   judged world.

**Effort:** about 9 agent-days (range 8.5–10.5) plus 3–6 CPU hours, the review's added guards
included, against the original 3–4 days that also held J2. It is staged as S5a (about 5.5 days)
and S5b (about 3.5 days), as the lead approved (§11).

**S4:** superseded and reported, with no new run. The lead records the decision when this note
lands (§9).

**The probe before code (risk 1, §13): clean, no drift.**
- **The world.** Four quarter eggs on one held bath, at egg scale, with three species moving in
  every cell (staggered pulses through one electrode per cell). The models are composite@1 over
  @3 with injection only. It is built from the S0 smoke egg, with no S5 code and no partition.
- **The run.** 1.78e6 steps at 0.25 ms (445 s), from a clean snapshot of b98702c, with device
  checks on every row. No step was refused and no check failed.
- **The electrode residual against its bound.**
  - Its worst was 2.6e-4: −1.9e-26 C against 7.4e-23 C at the fifth step, an early transient
    that the one-cell control shows too (1.8e-4).
  - After the first window it stayed below 1.3e-8. At every window end it was 0 or ±1.0e-25 C, a
    couple of ulps of the plate charge, while the bound grew to 6.3e-15 C.
  - The later-half slope is −4e-32 C per step against the bound's 5.5e-21 C per step, an
    asymptotic ratio of 8e-12.
- **The one-cell control** (D148's exact case) gives the same picture, with an asymptotic ratio
  of 1e-16.
- **So the stop branch is not triggered.** That branch was an ordered node sum or an allowance,
  with S5a at 1 → 2 only. Egg-scale 1 → 2 → 4 stays in the plan.
- **Caveat: "clean" covers this compiled program only.** The exposure is specific to each
  program.
  - The probe has no closer.
  - It ran the scalar rollout, one compiled program per window shape, with a separate vmapped
    pass of per-row checks, as S3's probe did. S5's studies run vector windows.
  - Q1's device checks remain the guard, and they measure the ratio again in S5's own programs.
- **Evidence.** `cell-division-s5-20261113-01/probe/` (unit `cells-s5-probe`; memory.events all
  0; peak 0.9 GB).

**Decisions:** §12, as taken on 13 November.

## 1. What the as-built engine imposes

**1.1 @3's padded-slot domain at the view.**
- @3 checks its domain at the end of its IMEX step (`surface_pump_v3.imex_step`) and inside
  `surface_pump_v3.readouts`, which its observer uses, both at the layout it is given. For the
  composite that layout is the view.
- `surface_tissue.domain_valid` requires the following of every slot its mask closes:
  - a zero amount increment and a physical amount of exactly 0 (cells);
  - zero transfers and heat (patches, contacts, faces).
- It also requires zero transfers wherever a route coefficient is 0.
- `surface_pump_v3.domain_valid` adds that a closed population carries law code 0 and zero
  channel accumulators. It also requires zero pump cycles wherever the pump capacity is 0.
- The dissipation check (`surface_pump_checks.row_checks`, `surface_pump.checked_rows`) refuses
  any heat element that decreases between rows.

**1.2 One provider per view field** (`pump_composite.structure_errors`). Insertion@1 provides
`membrane_active`, `outside_active`, `face_active` and `extracellular_amount_reference`, so no
other operator can change them.

**1.3 Single-topology assumptions.**
- Insertion@1 computes its fixed-charge change and its ledger terms on its own capacitor view
  (`membrane_insertion.capacitor_view`, its masks only).
- Its onset rule (`check_onsets`) requires every patch facing an onset node to open with it.
- Lumen@1 refuses a node faced by more than one patch, and its target follows one patch's area.

**1.4 The energy rule at the view** (v2 design §3, decision 9) is booked in insertion@1's
`ledger_terms` (`adapter.view_capacitor_terms`). Its reference is the declared layout at t = 0.
That equals the view of the initial state only under insertion@1's onset rules; pending
daughters break the equality (§3.6 point 4).

**1.5 Limits carried from S3, all kept:**
- the zero-charge onset;
- injection and the lumen book at the view;
- field-input providers are refused above 64 padded field nodes;
- the new membrane's leak is passive (§5.1 on lifting this);
- the energy correction is computed against @3's declared-array term;
- D148 governs any in-place change to shared qualified code (§8.4).

## 2. Topology at the view: closers, propagation and padding

**Contract addition (`contract.py`).** An operator declares `CLOSES`, the activity masks it may
close (`active`, `outside_active`, `membrane_active`, `face_active`, `junction_active`,
`channel_active`). Its `closures(state, p, q, *, xp)` returns {mask: open}. Then:
- **Conjunction.** The view's mask is the declared mask AND each closer's mask, in declared
  order. Boolean conjunction is exact and independent of order.
- **Closers or a provider, never both.** A composition in which one operator provides a mask
  (insertion@1) and another closes it is refused.
- **A closer counts as the mask's provider for `CONFLICTS_VIEW`.** An operator that reads a
  mask from the declared layout (replacement@1 and @2) is refused beside any closer of it
  (§5.5).
- **Propagation (adapter, after every closer).**
  - A patch of a closed cell is closed.
  - A population on a closed patch is closed.
  - A contact with a closed endpoint is closed.
  - A face at a closed node is closed.

  So the partition decides cell liveness only. Insertion@2 decides only its onset patches and
  nodes, and a node opens when its first onset patch opens.
- **Padded-slot semantics (adapter).** When any closer is present, the view presents every
  closed slot as @3 padding:
  - `amount_reference` and `extracellular_amount_reference` read 0;
  - `channel_laws` reads 0.

  The adapter's `VIEW_FIELDS` gains `amount_reference` and `channel_laws`. This is the only
  place that knows @3's names.
- **Field inputs.** A closer of `active`, `outside_active` or `membrane_active` counts as a
  field-input provider. It therefore triggers the device refresh, the 64-node cap and the
  refusal of floating components.
- **Mask readers.** An operator that reads a mask (`VIEW_READS`) follows every closer of it.
- **Static.** Without a closer the view is computed exactly as today. Every existing
  composition (water@1 and @2, replacement@1, injection, S2, S3) has no closer.

| Closer | Closes | Open when |
| --- | --- | --- |
| `isopotential_partition@1` | `active` (cells), and through propagation their patches, populations and contacts | A daughter after its division; a parent before it; any other cell always |
| `scheduled_membrane_insertion@2` | `membrane_active` of onset patches; `outside_active` of onset nodes (faces follow) | A patch from its onset; a node once any of its onset patches has opened |

## 3. The partition: `isopotential_partition@1`

### 3.1 Declaration and schedule
- **Declaration (model):** `divisions`, each with:
  - an id, a parent cell, two daughter cells and a volume fraction f;
  - a patch map (each parent patch to one patch in each daughter, with area fraction a_k);
  - a population map (each parent population to one population on each daughter patch);
  - a contact map (each parent contact to a neighbour, to declared daughter contacts);
  - the bridge junction between the daughters;
  - mismatch carriers {species: transference number}, used only when some a_k ≠ f.
- **Schedule (experiment):** `partition_events`, each with a division id, a time and the two
  daughters' carrier IDs (like replacement's `carrier_id`).
  - Times are exact multiples of dt inside the horizon.
  - The structure (slot maps) is static and enters the batch signature. Times and fractions are
    per-world data.
- **Own state:**
  - `division_applied[division]` (int64, 0 or 1);
  - the moved transfers (§3.7);
  - the retirement record (§3.5);
  - `partition_image_charge_C[outside]`, `partition_work_pJ[cell]` (declared work) and
    `partition_energy_magnitude_pJ[cell]`.
- **Parts:** an event map only.
  - It declares `CLOSES = (active,)`, `RETIRES`, and `BOOKS_AT_VIEW` for its event: the
    composite passes the view as a function of state (a contract addition).
  - `STATE_RESETS = (channel_gate, junction_gate)`.
  - It also declares `CONFLICTS_VIEW = (volume,)`.
  - `REQUIRES` `membrane_entity_state@1`.

### 3.2 Slots and anchors at birth
- **Fresh slots for both daughters** (design §5.2). Each daughter cell, patch, population and
  contact is a declared slot, closed by the partition until its division.
- **Every daughter anchor is its fraction of the parent's declared anchor.** The fraction is f
  for reference amounts, volume, fixed background and charge anchor; a_k for patch area,
  capacitance and population abundance; a_e for a neighbour contact's area.
- **Exact identities checked at the definition:**
  - Σ over the daughters of each anchor equals the parent's in float64, exactly;
  - the domain parameters are the parent's: permeability per area, law, specific capacitance,
    unit parameters.
- **A definition helper** (engine side, `core`) writes the daughter slots from a parent and its
  fractions, so drivers never hand-write anchors.
- **Why fractions of the declared anchors.**
  - The anchors do not depend on the division time or on the parent's state at the event.
  - The actual content travels in the increments: a daughter's increment is f times the
    parent's, plus δ.
  - Anchors stay immutable (D057), and active slots keep small increments.
- **Exactness for f = a_k = ½.**
  - Halving is exact in binary floating point, and the complement Δ − ½Δ is exact (Sterbenz).
  - So the event writes bitwise-identical daughter states, and every booking is an exact
    zero.
  - Potentials solved afterwards may differ between the daughters in the last bit, by
    elimination order (§7.3).
- **@3's definition charge check.**
  - Halved anchors pass `surface_tissue.check_definition`'s absolute 1e-20 C test whenever the
    parent's do, since the residual halves too.
  - Asymmetric anchors at egg scale may not pass: the background's ulp is about 1.8e-19 C,
    design §1.2.
  - So asymmetric egg-scale divisions wait for the scale-aware bound (design §1.2's follow-up,
    in `surface_tissue.py`, outside this design's files).
  - S5's Xenopus-scale worlds divide symmetrically.

### 3.3 What divides and how

| Entity quantity | Rule at the event | Owner of the field |
| --- | --- | --- |
| Cytosol amounts | Increments split: Δ_D1 = f Δn_P + δ, Δ_D2 = Δn_P − Δ_D1 (complement); the parent's increment → 0. With the declared anchors, n_D1 = f n_P + δ | @3 (`amount_increment`), booked by the partition |
| Mismatch δ | δ_s = t_s δq / (z_s F), δq = Σ_k (a_k − f) q_k, q_k = C_k V_k on the cell side at the view; 0 when a_k = f | Partition |
| Volume | Declared, f V_P (no volume provider; water is refused, §3.8) | @3 layout (anchor) |
| Fixed background and charge anchor | Declared, f X_P and f q_P; the daughter's charge is then Σ_k a_k q_k (§3.6) | @3 layout (anchor) |
| Patch area, capacitance | Increments split by a_k; the parent patch's increment → 0 | `membrane_entity_state@1`, written by the partition (`ACCEPTS_WRITES`) |
| Population abundance | Increments split by a_k; parent's → 0 | `membrane_entity_state@1` |
| Population gates | Copied from the parent (intensive) | @3 (`channel_gate`), `STATE_RESETS` |
| Pumps | Refused on dividing cells (later work: pump capacity as entity state) | – |
| Neighbour contacts | The parent's contact closes; declared daughter contacts open (areas a_e, 1 − a_e) with the parent's gate | @3 (`junction_gate`), `STATE_RESETS` |
| Bridge | Opens with both daughters, aperture a_0 (§4) | Bridge closure |
| Cleft lumens, outside nodes, faces | Not divided: a lumen stays shared; its live facing patches change, their summed area is continuous (§5.2) | Lumen@2, @3 |
| @3 history of the parent's patches, populations and contacts | Moved to the retirement record (§3.5) | Partition |
| Insertion's own accumulators on the parent patch | Frozen (they still close `membrane_entity_state`'s ledger with the moved transfer) | Insertion@2 |

### 3.4 The event map
At the start of the step leaving a division time, for each due division, in declared order:
1. **Due.** `control.partition[d] == division_applied[d] + 1`. A stale schedule is refused, as
   replacement refuses one.
2. **Pre-event view.** Patch voltages and patch charges q_k at the composite's view of the start
   state, and the clamps' plate charges.
3. **Content.** Write the daughters' increments and zero the parent's, booked as signed
   transfers. Write the area, capacitance and abundance increments the same way.
4. **Intensive state.** Copy the gates.
5. **Retirement.** Move the parent's @3 history into the record and zero it.
6. **Apply.** Set `division_applied[d] = 1`. The closures now close the parent and open the
   daughters, their patches, populations and contacts (the bridge included).
7. **Post-event view and checks.**
   - Isopotential check: daughters at the parent's potential within a rounding allowance; the
     outside potentials unchanged.
   - Book the clamps' plate-charge change (rounding level) as electrode transfer with its work.
   - Book the free-energy change as partition work (§3.6).
   - Refuse a non-positive daughter amount.

Untouched entries are selected, never offset by zero. Every step is a gather or scatter with
static index arrays.

### 3.5 Retirement: the parent presented to @3 as padding
- **What moves.** The partition's record holds the retired slots' @3 history. Each record field
  is named without the heat or work suffixes (role: accumulator) so it is not counted twice:
  - `partition_retired_membrane_transferred_fmol[species, membrane]`;
  - `..._membrane_heat_pJ[membrane]`;
  - `..._junction_transferred_fmol[species, edge]`, `..._junction_heat_pJ[edge]`;
  - `..._channel_transferred_fmol[species, channel]`, `..._channel_heat_pJ[species, channel]`.
- **What stays.** Entity state owned by operators stays in place, masked by the view:
  `membrane_entity_state`'s anchors and insertion's accumulators. Its own domains use the
  declared masks and stay valid: the parent patch keeps A0 > 0 and C0 > 0.
- **Add-back.**
  - The partition's `adjust_inner` returns the row with the record added into @3's
    accumulators, as `k_anion_symport` adds its transfer into `membrane_transferred`.
  - Every @3 ledger therefore closes on its own formulas: local, outside, total, energy
    (dissipated sum) and the charge ledgers.
- **Checks on the adjusted row (composite, static).**
  - With an operator that declares `RETIRES`, the composite runs its host and device row checks
    (domain, ledgers, dissipation) on the adjusted row, with balance and magnitude functions
    that do not adjust again.
  - Each heat element is then monotone across the event.
  - This changes only `pump_composite.py`, not `surface_pump*.py`. Compositions without a
    retiring operator are unchanged.
- **Observation.**
  - @3's columns read a closed slot as padding from its closure on.
  - The partition's readout columns report each slot's phase (pending, live, retired) and its
    record.
  - The summary adds the record to @3's totals.
- **Alternatives considered:**
  - **History kept in @3's fields, with @3 shown a living-state projection.** Every @3 call
    would need the projection: the step, readouts, the observer and control-domain checks. @3's
    observation columns would also disagree with the stored state.
  - **Retired patches left active with zero coefficients.** @3's domain refuses nonzero
    transfers wherever the permeability or channel route is 0.
  - **One daughter reusing the parent's slot.** That daughter carries whole-content increments
    on a living slot and needs a volume view with a dilution term. A symmetric division cannot
    then give identical daughters, and the other daughter still needs fresh slots.
  - All three are rejected.

### 3.6 Charge and energy (design §5.2, as built)
1. **Potentials are continuous.** With q_D1 = Σ_k a_k q_k at the parent's voltages, the
   daughters solve to φ_P. Each lumen's facing capacitance sum is unchanged, so its charge and
   potential are unchanged, and the clamps' plate charges are unchanged. Floating point leaves
   rounding: the partition books the plate-charge change at the view (as lumen@1 books its
   fill's), so the electrode ledger telescopes, and refuses a change beyond rounding.
2. **Charges follow the patches.**
   - Anchors f q_P, plus increments f Δn_P + δ, give f q_P(actual) + δq = Σ_k a_k q_k.
   - Material and charge are exact in exact arithmetic.
3. **Free energy.**
   - ΔG_entities is the change of @3's chemical terms of the touched slots on the declared
     layout (`adapter.chemical_free_energy_pJ`), plus the change of the physical capacitor
     energy at the view.
   - It is booked as `partition_work_pJ` = ΔG_entities − Σ φ_b Δq_b. This is the contract rule
     "events replace and book" (v2 design §1.3).
   - Because the anchors are proportional, the chemical change is the physical unmixing term,
     ≥ 0 and about RT Σ_s δ_s² / (2 n_s f (1 − f)). It is the contractile machinery's work, as
     §5.2 says. The capacitor term is 0 up to rounding.
   - For f = a_k = ½ every term is an exact zero.
4. **The energy rule at the view, and its reference.**
   - The composite books `view_capacitor_terms` once per ledger evaluation (§5.3). The
     partition changes both masks and capacitances. With the reference below, the parent's
     term leaves and the daughters' enter without extra bookings.
   - **With a closer present, the reference must be the view of the initial state (found in
     review).**
     - `view_capacitor_terms` measures both of its terms against the declared layout at t = 0.
       In that layout every declared slot is active, pending daughters included.
     - For a patch closed at the view, @3's term plus the correction leaves −½ C0 V0². The
       electrode residual becomes transferred − plates_view(t) + plates_declared(0).
     - S2 and S3 had zero offsets only because insertion@1's onset rules (a finite node, a zero
       charge anchor, every facing patch opening together) gave its onset patches V0 = 0. They
       also left the bath's plate charge equal in both layouts.
     - Pending daughters break all three. Their old patches face the held bath with charge
       anchors f q_P, so V0 ≈ V_P.
     - At egg scale the offsets would be about −½ Σ C0 V0² ≈ −1.6 pJ per generation in the
       energy ledger, against `ENERGY_ATOL_PJ` = 2e-8 pJ at zero flows. In the electrode ledger
       they would be about (C_D1 + C_D2) V ≈ 3e-10 C, against a bound of order 1e-23 C. Q1
       would fail at row 0 on every S5 world (S).
   - **The fix (static: only with a closer).** Two constants are bound once from the definition
     (R1). They are layout arrays of the composition: bindings, one per world in a batch, never
     constants closed over by the traced program (§8.3 Q6, §8.4).
     - E_ref = ½ Σ C0 V0² (declared) − ½ Σ C V² (view of the initial state);
     - q_ref = plates_declared(0) − plates_view(0), at the held nodes.

     The composite adds E_ref to the energy correction and subtracts q_ref in the electrode
     correction. Then:
     - the capacitor energy is ½ Σ C V²(t) − ½ Σ C V²(0), both at the view;
     - the electrode residual is transferred − (plates_view(t) − plates_view(0));
     - every ledger is zero at row 0 (to rounding: a host bind against a device solve) and
       stays so up to the first event.
   - No chemical offset is needed. Pending slots have zero increments, and proportional anchors
     keep Σ G(ref) unchanged across a birth.
   - Insertion@1's path (S3's world) is untouched: it has no closer, and its offsets are zero by
     its onset rules.
5. **No elastic term** (no water). With water (later), the partition writes water's volume
   increments through the v2 design §2 entity volume ledger.

### 3.7 Where each term is booked (design §5.3, updated for the as-built ledgers)

| Term | Booked in | Owner |
| --- | --- | --- |
| Transport (membranes, faces, junctions, the bridge) | @3's route ledgers and heat, at the view | Inner step |
| Insertion: area, capacitance, abundance | `membrane_entity_state` increments; `inserted_*` | Insertion@2 |
| Insertion: image charge, its work, heat H ≥ 0 | @3's electrode transfer and work; `insertion_image_charge_C`; `insertion_dissipated_energy_pJ` | Insertion@2, at the composite's view |
| Lumen fill: bath fluid, μ_b dn, −Π_b dV, mixing heat; dilution | As lumen@1 (S3 plan §1) | Lumen@2 |
| Partition: content moved (signed, Σ = 0 per division and species) | `partition_moved_fmol[species, cell]` in @3's local and total ledgers; own ledger `partition_material` | Partition |
| Partition: area, capacitance, abundance moved (signed, Σ = 0 per parent patch and population) | `partition_area_moved_m2`, `partition_capacitance_moved_F`, `partition_units_moved`; `membrane_entity_state`'s entity ledgers (external terms); own ledgers | Partition |
| Partition: retired @3 history | The record, added back for every ledger and check (§3.5) | Partition |
| Partition: free-energy change less the clamps' work | `partition_work_pJ` (declared work) | Partition |
| Partition: image charge at the clamps (rounding level) | @3's electrode transfer and work; `partition_image_charge_C` | Partition, at the view |
| Partition: gates | Intensive copies (`STATE_RESETS`), no ledger | Partition |
| Bridge aperture | `bridge_aperture_m[edge]` (own state; a factor on @3's junction availability) | Bridge closure |
| Capacitance and mask changes in @3's electric term | ½ Σ [(C − C0) V² + C0 (V − Vb)(V + Vb)] and the clamps' plate-charge difference; with a closer, also the bound offsets E_ref and q_ref (§3.6) | Composite (§5.3) |
| Current injection | As built (v2 design §4) | Injection@1 |
| Lineage | Host records from the schedule and `division_applied` (§6) | Partition |

**Magnitudes** (rounding allowances):
- the moved amounts in the local and total magnitudes;
- the record, through the adjusted row;
- the image charge in the electrode and global-charge magnitudes;
- |chemical terms| + |U| + |clamp work| in the energy magnitude;
- |E_ref| and |q_ref| in the energy and electrode magnitudes. The view terms' magnitudes already
  include the absolute declared plate charges and energies, pending slots included. The
  allowance therefore stays of the order of the physical capacitor energy and plate charge
  times the number of generations.

For f = ½ the moved transfers balance exactly. Otherwise their rounding is ulp(Δn), not ulp(n),
so no whole-content event allowance is needed: this improves on design §5.4's estimate.

### 3.8 Refusals
**At the definition:**
- **Slot structure.**
  - Daughter slots must be pending at t = 0.
  - Each slot is at most one division's parent and at most one division's daughter.
  - A parent must be live at its division time. Two events on one slot at one time are refused.
- **Anchors and fractions.**
  - Anchors that are not exact fractions, or domain parameters that differ (§3.2).
  - f or a_k outside (0, 1).
  - A daughter without a patch on a held bath: a floating component, which needs topology
    epochs.
- **Mismatch carriers.** They must be charged species with t_s ≥ 0 and Σ t_s = 1, and are
  required when some a_k ≠ f.
- **Features outside S5's scope.**
  - Pumps on a dividing cell.
  - A volume provider (water, through `CONFLICTS_VIEW`).
  - Replacement in the composition (it books at the declared layout).
  - Insertion@1 or lumen@1 (§1.3).
- **The bridge.** A parent with an open bridge at its division time (its closure must end
  first). A bridge aperture too wide for dt: @3's explicit-rate bound on the check spec (§3.9)
  refuses it.
- **Activity outside a slot's living interval.** An insertion rate, an onset or an injection
  current on a slot outside its living interval, read from the other operators' schedules
  (as lumen@1 reads insertion's).

**At the event:**
- a non-finite value;
- a daughter amount ≤ 0 (δ too large);
- an isopotential or plate-charge change beyond rounding;
- a stale schedule.

**A refused partition leaves the full prior state.** The event is part of the step, and the
composite's refusal path returns the start state for any refused piece. The event is applied in
full or not at all.

### 3.9 Step checks (R5)
- **Inner check spec.** Each daughter patch is taken at its largest area: a_k times the parent
  patch's largest area over the schedule, plus its own insertion, with its declared, smallest,
  capacitance.
- **The bridge** is declared at a_0, its largest. Availability only falls.
- So @3's definition-time explicit-rate bound covers every daughter from birth (S). The
  junction term, 2 max_i Σ_j G_j / C_i, is the design §5.4 bridge refusal.
- @3's in-step checks still refuse at the actual openings.

### 3.10 Observation and summary
- **Readout columns:** `slot_phase[cell]` (0 pending, 1 live, 2 retired) and the record.
- **Summary:** the lineage (§6), each division's fractions, and the moved and retired totals.
- @3's readouts of a closed slot are padding.

## 4. Bridge closure: `cytoplasmic_bridge_closure@1`

### 4.1 Law and entry
- **The bridge.** The bridge is an @3 junction between the two daughters, declared with:
  - the constant-field junction law (`coupling/selective.selective_flux`);
  - P_s A_j = 2 a_0 D_s^cyt per species: area 2 a_0 × 1 m and permeability D_s^cyt / (1 m),
    as the cleft's access face uses length 1 m;
  - a gate fixed open (minimum open fraction 1, initial gate 1).

  For equal concentrations its conductance is 2 a σ, with σ = (F²/RT) Σ z_s² c_s D_s
  (Nernst–Einstein): the access conductance of an aperture in a thin wall (design §4.2).
  The cytoplasmic diffusivities are D_s^cyt = D_s σ_cyt / σ_free. σ_cyt is a declared
  assumption until a source is found (§4.2; decision 12).
- **The operator.**
  - Own state: `bridge_aperture_m[edge]`, a_0 until the bridge's birth.
  - View: `CONTROL_FACTORS = (junction,)`, availability × a/a_0, a product with any other
    factor.
  - Split part: exact half-steps of the declared closure law, linear
    a(t) = a_0 max(0, 1 − (t − t_b)/τ_c) or exponential a_0 exp(−(t − t_b)/τ_c), with t_b the
    division time (checked against the partition's schedule). RK4 mode: split.
  - Statically idle without bridges. A half-step with no change selects its start state.
- **Ledgers.** Transport and heat are @3's junction ledgers. The aperture is not conserved, so
  it has no ledger of its own. Domain: 0 ≤ a ≤ a_0, non-increasing, and a_0 before birth.
- **Not G2's formation law:** here coupling falls, there it rises (design §4.2).
- **The composite-v2 audit's "junction area: S5".** It is resolved by the availability factor.
  `junction_area` stays declared at a_0 (R1), and no junction-area view is needed.

### 4.2 Stiffness and the partition's aperture
- **The bound (explicit term, design §5.4).** At 0.25 ms, dt × 2 G_b / C_D ≤ 1 with C_D about
  15.8 nF (half the old membrane's 31.7 nF) gives R_b ≥ about 32 kΩ (S).
- **The aperture.** That is a_0 ≤ about 18–32 µm, depending on the cytoplasmic conductivity
  σ_cyt (S).
- **The cytoplasmic conductivity is a declared assumption** (no measurement was found in the
  sources read; decision 12 waits for one).
  - Default 0.5 S/m (about 2 Ω·m, the division design's working value), band 0.2–0.9 S/m.
  - The upper end is the free-solution conductivity of the declared activity-basis cytosol,
    σ_free = (F²/RT) Σ_s z_s² c_s D_s ≈ 0.89 S/m. It uses standard free-solution diffusivities:
    Na 1.33, K 1.96 and Cl 2.03 × 10⁻⁹ m²/s, to be cited at build (S).
  - The lower end allows an obstruction factor of 2–5 for yolk, organelles and bound ions (S).
  - The bridge's cytoplasmic diffusivities are D_s^cyt = D_s (σ_cyt / σ_free): one obstruction
    factor for every species.
  - **σ_cyt is not an independent unknown in the engine.**
    - The engine sees the bridge only through P_s A_j (a/a_0) = 2 a σ_cyt D_s / σ_free: the
      product a σ_cyt times fixed free-solution weights.
    - So the declared parameter is in effect the bridge's initial conductance,
      G_b0 = 2 a_0 σ_cyt. The step bounds it (R_b0 ≥ 32 kΩ at 0.25 ms), and Q10's range over a_0
      at a fixed σ_cyt spans the same G_b0 as σ_cyt's band, a factor of 4.5.
    - A source for σ_cyt is needed only to read G_b0 as an aperture in µm. Decision 12's wait
      therefore does not hold up S5a's code.
- **Partition time and a_0: an influence to measure, not a numerical device.**
  - Before the partition the cytosol is one node. That is valid while the bridge resistance is
    far below the membrane's: about 3.5 kΩ at J1 (design §5.4), with coupling above 0.95.
  - At birth the bridge carries no current: the potentials and concentrations are equal.
  - **While it is open, R_b matters at the quantities' own scale.**
    - A daughter's input resistance with its sister behind R_b is Rm (R_b + Rm)/(2 Rm + R_b).
    - At Rm ≈ 1 MΩ (about twice dLB74's 488 kΩ for the whole egg) and R_b = 32 kΩ, that is
      about 508 kΩ. The limit R_b → 0 gives 500 kΩ, and the closed bridge gives 1 MΩ (S).
    - The 8 kΩ difference is about 500 times S3's Rm tolerance of 15 Ω.
  - **After closure** the bridge acts only through history: what the open interval exchanged.
    For a symmetric division without injection that is nothing. Otherwise it is small, and it
    is what Q10 measures.
  - **So the partition time and a_0 are declared parameters.** Q10 (§8.3) registers each
    compared quantity's sensitivity to them. A quantity is called insensitive only within its
    registered tolerance; otherwise t_p and a_0 enter its band.
  - The closure time τ_c is the physiological unknown (bridge closure was not measured). It
    needs a band in any judged protocol.

### 4.3 The cleft lumen and the furrow membrane through closure
- **Furrow membrane.**
  - Insertion continues on the daughters' furrow patches at their declared rates (each takes
    its share), until the declared end of the furrow.
  - The rim the closing bridge seals, π a_0² (about 0.003 mm² at 30 µm, 0.2% of the 1.39 mm²
    of new membrane), is not inserted: a declared limit.
- **Lumen.**
  - Each lumen stays shared. Its volume follows its live facing area (§5.2), and its access
    A/L stays constant (S3's limit).
  - After closure the trans-cleft path (face, lumen, face) is the only route between the
    daughters (design §7).
- **Second cleavage.**
  - Each daughter opens a new furrow patch at its own onset (insertion@2), facing a new cleft
    node with its own access face to the bath.
  - It may be joined to the first cleft at the centre by a declared face.
  - At the second partitions, each daughter's three patches (old, first furrow, second furrow)
    split between its daughters.

### 4.4 Refusals
- a bridge junction that is not a contact between one division's two daughters, or whose gate
  is not fixed open;
- P_s A_j ≠ 2 a_0 D_s^cyt for its declared diffusivities and σ_cyt;
- a start time other than its division's;
- a negative or reopening aperture.

## 5. New versions of S2 and S3 operators

### 5.1 `scheduled_membrane_insertion@2`
- **Unchanged from @1:** the law (dA, dC = c_d dA, dN = ρ dA at fixed free-node charges), the
  image charge and its work, and the heat H.
- **Changed:**
  - It computes the fixed-charge change at the composite's view: `BOOKS_AT_VIEW`, with every
    closer's masks.
  - Its onset is a closer (§2), not a provider. The adapter applies the padding.
  - **Onset rule generalised.** At an onset, the node's live facing patches are exactly those
    opening then; other facing patches must be closed then, as pending daughters are (checked
    against the partition's schedule). The zero-charge onset therefore holds unchanged. So
    does S3 prerequisite (a): each onset, the daughters' second furrows included, leaves at most
    ½ C_on V_m² unbooked by IMEX, and the host energy check guards it.
  - Rates only on live patches: refused at run time against the view's mask, and at the
    definition against the partition's schedule.
  - It does not book the energy rule at the view (§5.3).
  - It reuses @1's law functions unmodified.
- **Populations on onset patches** become admissible: the padded-slot rule gives them law code
  0 until onset, which lifts the declared departure of design §6. Admitting them is deferred to
  S5b (decision 9). In S5a, insertion@2 keeps insertion@1's refusal.

### 5.2 `restricted_cleft_lumen@2`
- **Target.** V = V_on + w (Σ_live A_k − A_on)/2, the sum over the facing patches live in the
  composite's view (`VIEW_READS` `membrane_area`, `membrane_active`), with A_on the onset
  patches' area. It is filled at the source's composition as @1, with the same budget,
  observer and bookings.
- **Admission.**
  - A lumen faced by several patches is admitted when its live facing patches are always its
    onset patches or partition-born descendants of them (from the partition's maps).
  - Then the summed area is continuous at every birth: exactly for a = ½, within one ulp
    otherwise.
- **Shrinkage.** A target below the held volume by no more than rounding is treated as no fill.
  Shrinkage beyond rounding is refused as before.
- **Debt.** The padded-slot test of the lumen owed since S3 runs here.

### 5.3 The composite owns the energy rule at the view
- **The rule.** The composite books `adapter.view_capacitor_terms` (energy and electrode) once
  per ledger evaluation, as the v2 design §3 anticipated. It does so whenever a writer of a
  field input does not declare that it books them itself. Insertion@1 declares that it does.
- **The reference.** With a closer present, the reference is the view of the initial state:
  the bound offsets E_ref and q_ref of §3.6 point 4. Without a closer the declared reference is
  unchanged.
- **The same rule moves the image-charge term.** The magnitude terms move with it.
- **Static and bitwise for existing worlds.** S3's world (insertion@1) and every existing
  composition compile as today.

### 5.4 What stays unchanged
- **Engine modules.**
  - Insertion@1, lumen@1, `membrane_entity_state@1` and injection@1.
  - S3's judged world and its registered protocol.
- **Other agents' files.** S5 needs no change to:
  - `cell_replacement*.py`, `osmotic_water.py`, `current_injection.py` and
    `core/cell_replacement_spec.py`;
  - the checkpoint code;
  - `surface_tissue.py`, `surface_pump*.py` and `numerics/`.
- **Files S5 touches:**
  - `contract.py` (`CLOSES`, `RETIRES`, event views);
  - `pump_composite.py` (conjunction, adjusted-row checks, the energy rule);
  - `pump_composite_adapter.py` (propagation, padding, two view fields);
  - two new operator modules and the registry;
  - a `core` spec helper;
  - the new insertion and lumen versions in new modules or new classes beside @1, without
    editing @1's code paths.

### 5.5 Closers and `scheduled_cell_replacement@2` (v2 design §2, the volume ledger)
- **Today they are refused together.**
  - Replacement@2 runs @1's event map unchanged, which reads capacitances and activity masks
    from the declared layout. So it declares `membrane_area`, `membrane_capacitance`, `active`,
    `outside_active`, `membrane_active`, `channel_active` and `junction_active` in
    `CONFLICTS_VIEW`. It books its image charge and capacitor terms on the declared layout,
    without `BOOKS_AT_VIEW`.
  - The composite checks `CONFLICTS_VIEW` against providers only, and a closer is not a
    provider. S5's contract change therefore counts **a closer of a mask as its provider for
    that check** (§2). [Replacement@1 or @2, any closer] is then refused when the composition is
    built, as insertion@1 refuses a declared-layout booker today.
  - They are also kept apart twice more: replacement@2 requires water, and the partition
    refuses a volume provider (`CONFLICTS_VIEW` `volume`) and replacement explicitly (§3.8).
- **Ownership stays per field.** The activity masks belong to their closers, combined by
  conjunction; the volume to water; the amounts to @3. Each event books what it moves.
- **Composing them later** (renewal and division in one tissue) needs three extensions, none in
  S5:
  - Replacement's event map books at the composite's view. That is the `BOOKS_AT_VIEW`
    extension v2 §2.7 names for replacement during insertion. S5's event view (§3.1) is the
    hook, and the same hook is what v2 §2.10's first open question proposes for `law_steady`.
  - Replacement refuses a slot that is not live in the view (pending or retired).
  - A partition law writes water's volume through water's `ACCEPTS_WRITES` on
    `volume_increment_pL`: the parent's increment to 0, each daughter's f dv_P. It books water's
    endpoint free energy (`node_free_energy_pJ`) for the touched nodes, as replacement@2 does.
- **Landing order.** S5a lands after the volume ledger, so its closer-as-provider rule is
  checked against replacement@2's declarations as landed.

## 6. Lineage, identity, slots and capacity

**6.1 Lineage and identity.**
- **Carrier IDs** are declared, and slots are storage.
- **Founders** are the declared cells that no division has as a daughter. Daughters get the
  carrier IDs of their schedule entry.
- **Records** are rebuilt on the host from the declaration, the schedule and the final
  `division_applied`, as replacement rebuilds its own from `generation`. Each holds:
  - carrier_id, slot, kind (founder or daughter);
  - parent_carrier, sibling, birth_s, death_s, successors;
  - route "division", the division id and its fractions.
- **One record shape** shared with replacement's (carrier_id, slot, birth_s, death_s,
  predecessor and successor), so the composite summary can later merge both lifecycles' records
  into one lineage. No composition has both in S5.
- **Keyed random streams** need a numeric carrier key per slot (int64 state, written at birth).
  It is noted for milestone 2: no S5 law is stochastic.

**6.2 Slots and capacity.** No reuse in S5: 1 → 2^k needs 2^(k+1) − 1 cell slots. The worlds,
against the 64-node cap of field-input providers:

| World | Cell slots | Outside slots | Field nodes | Patches | Contacts | Faces | Divisions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 → 2 | 3 | 2 (bath, cleft 1) | 5 | 6 | 1 bridge | 1 | 1 |
| 1 → 2 → 4 | 7 | 4 (bath, clefts 1, 2a, 2b) | 11 | 20 | 3 bridges | 3, or 5 with clefts joined at the centre | 3 |
| Plan's maximum, 1 → … → 16 | 31 | 16 | 47 | – | – | – | 15 |

- **Field topology.** Every cell keeps a patch on the held bath (a_old ∈ (0, 1)), so every
  capacitor component holds a reservoir. Masks change at events; components do not. The device
  refresh is the R3 path, already taken every step once a field input is provided.
- **vmap.** Worlds batch when capacities, operator lists and slot maps match. Times, fractions,
  apertures and closure times are per-world data.
- **Restart.** Every operator field is state (R7), so a checkpoint carries the record, the
  applied flags and the aperture.

**6.3 Toward milestone 2 (endogenous lifecycle).**
- **Anchors and triggered divisions.**
  - Because anchors are fractions of the parent's declared anchors, they do not depend on the
    division time.
  - So a triggered division with a declared fraction and pre-assigned slots needs no
    re-anchoring. This narrows design §5.2's statement.
  - Re-anchoring (a decision against D057) is needed for slot reuse, and for growth over many
    cycles if increments outgrow their anchors' precision.
- **Slot reuse.** Retirement already leaves a slot pristine to @3, so reuse needs only the
  anchor decision and carrier-keyed lineage.

## 7. Independent references (design §8.4)

### 7.1 R-ops (numpy; `validation/division/partition_reference.py`)
**Independence.** It is written from §3.6 and design §5.2, not from engine code. It solves its
own capacitor network: a dense nodal solve written here.

**Inputs.** Random small worlds:
- a parent with 2–3 patches to a held bath and a free cleft, populations, and a neighbour
  contact;
- random positive amounts, backgrounds, volumes, areas, capacitances and charges;
- random history accumulators;
- f, a_k and transference numbers.

**Outputs:**
- daughters' amounts and increments, charges and potentials (by its own solve), patch areas,
  capacitances, abundances and gates;
- moved transfers, Σ = 0;
- the clamps' image charge (0) and ΔU (0);
- the chemical change in absolute form, RT Σ n (ln(n/V) − 1);
- the record.

**Use.** It is also applied at the events inside R-tissue. The bridge's closure law is written
there too.

### 7.2 R-tissue (numpy/scipy; `validation/division/cleft_tissue_reference.py`)
- **What it is.** A graph-general R-full in R-full's style, independent of the engine:
  - nodes: cells, clefts and the bath; capacitor graph by patches;
  - membranes: constant-field;
  - access: log-mean or constant-field Nernst–Planck;
  - the bridge as a constant-field junction with P A = 2 a(t) D_s;
  - insertion at fixed charges, with heat ½ V² dC;
  - lumens filled to w Σ_live A / 2;
  - injection pulses;
  - R-ops at each division;
  - Radau at rtol 1e-10, with breakpoints at every event.
- **Shared code.** It imports R-full's transport laws (`ghk_flux`, `access_flux`), which S3
  qualified against the engine. It adds the graph solve, the bridge and the events.
- **Cross-check.** On S3's one-cell cleft egg it reproduces R-full: target 1e-10 V on every
  pulse edge, a run of minutes. This checks the new reference itself.
  - The cross-check reads the J1 inputs, so it calls R-tissue's static entry point
    (`simulate_static`, no divisions) from a module of its own.
  - Division runs use `simulate_divisions`. The J2 bright line's test tells the two apart
    (§10.1).
- **Written from this note alone.** A separate agent writes R-ops and R-tissue from Appendix A,
  without reading the engine's partition, bridge, insertion@2 or lumen@2 code.

### 7.3 Analytic limits
- **Symmetric division.** f = a_k = ½ gives:
  - daughters' states bitwise identical at the event;
  - every booking an exact 0;
  - potentials equal to rounding afterwards. Elimination order can differ by an ulp, so the
    trajectories are equal to rounding, not bitwise.
- **Asymmetric division.** The unmixing work equals RT Σ δ²/(2 n f (1 − f)) to leading order,
  and is ≥ 0.
- **Isopotential split of a one-patch-per-node chain.** V_D = V_P and q_D = a q_P, with no
  image charge.
- **Bridge.**
  - a = a_0 with R_b ≪ Rm: the daughters are near-isopotential under injection, with coupling
    Rm/(Rm + R_b).
  - a = 0: the coupling equals the trans-cleft T-network's, and the sealed limit (A/L = 0) gives
    Rj = 2 r_new / A_face. Both are computed on S5's compact world, never on a Xenopus J2 world.

### 7.4 What each reference checks

| Reference | Compared with the engine | Pass (registered later; G2-Q1's and S3's form) |
| --- | --- | --- |
| R-ops | The event map on random states and on each world's first events: every daughter field, the moved transfers, the record, the image charge, the work | 64 eps × magnitude per quantity |
| R-tissue | Trajectories after each partition: each cell's Vm, each lumen's composition and volume, the bridge current, at every record | 3 × (step term + reference term) |
| Analytic | The limits above | Exact or to rounding, as stated |

## 8. Guards and the S5 qualification

### 8.1 Worlds (no DFS74 or J2 quantity)
- **Compact division world.**
  - Nominal parameters (not Xenopus's), a cell of tissue scale with an old patch to the bath.
  - A furrow onset into a cleft with access, partition, bridge closure, second onsets and
    partitions, all within about 2 s, at 0.25 ms (seconds of CPU).
  - Variants (S5a, with the partition): a neighbour cell with a gated contact, and populations
    on the dividing cell's ordinary patches.
    - They are checked by Q1, Q2 (R-ops maps them, Appendix A.6), Q6–Q9 and Q11.
    - R-tissue's trajectories (Q3) use the base world: passive patches and bridges, with no gate
      kinetics.
- **Egg-scale accounting world.**
  - The egg's volume, contents and areas (dL74, the smoke test's), with the old membrane of the
    smoke test and a nominal new membrane and access.
  - A compressed timeline: onset about 1 s, partitions at about 5 s and 15 s, horizon about
    30 s.
  - It tests egg-scale magnitudes, increments after the partitions, and the electrode ledger
    at four cells (§13).
- **The 30-minute rule (AGENTS.md).**
  - Every guard reaches its first partition within minutes.
  - No guard runs the 35-minute egg to reach one.
  - S3's cleft egg on insertion@2 and lumen@2 (§8.3, Q7) is a deliberate tier-3 run of about
    an hour; it has no partition.
- **Not run in S5:** anything inside the J2 bright line (§10.1), the J1-calibrated egg through
  1 → 2 → 4 among it. The compact and egg-scale worlds are built from neither J1 input. The
  egg-scale world takes the S0 smoke test's declared egg, as the risk-1 probe does.

### 8.2 Tier-1 smoke tests (under 20 s each, the v2 design's rule)
- **Contract and composite:**
  - conjunction and propagation;
  - padding;
  - the provider-and-closer refusal;
  - the energy rule moved to the composite. With a closer present, the capacitor energy equals
    ½ Σ C V²(t) − ½ Σ C V²(0) at the view, over a spread of states;
  - every ledger is 0 at row 0 and up to the first event in a world with pending slots (the
    offsets of §3.6 point 4);
  - **an independent check of the t = 0 fix**, extending S2's energy test to live slots and
    computed in NumPy.
    - The states: before any event, after an onset, after a partition, and after a second
      partition.
    - The energy: @3's declared term, plus the correction, plus E_ref, must equal
      ½ Σ_live C V²(t) − ½ Σ_live C V²(0).
    - The electrode residual must equal transferred − (plates_live(t) − plates_live(0)).
    - The right sides come from the live graph alone, by a nodal solve written in the test, not
      the adapter's;
  - adjusted-row checks.
- **Partition:**
  - one event on a tiny world: every @3 and own ledger closing on host and device;
  - symmetric bitwise daughters with zero bookings;
  - asymmetric unmixing ≥ 0;
  - the record's add-back and heat monotonicity across the event;
  - closed slots valid at the view;
  - each refusal, and a refused event leaving the prior state bitwise.
- **Bridge:** exact closure half-steps, the availability product, idle.
- **Insertion@2:** the onset with a pending facing patch; rates refused on closed patches.
- **Lumen@2:** two facing patches; continuity across a birth; the owed padded-slot test.

### 8.3 Qualification items (a protocol registered before its judged run, in G2-Q1's form)

| # | Claim | Worlds | Pass |
| --- | --- | --- | --- |
| Q1 | Every @3 and operator ledger closes on host and device across partitions, with insertion, lumen, bridge and injection | Compact 1 → 2 and 1 → 2 → 4; egg-scale | No ledger, domain or dissipation check fails on any row |
| Q2 | The event map equals R-ops | 200 random states; each world's events | 64 eps × magnitude |
| Q3 | Trajectories after partition agree with R-tissue | Compact 1 → 2 → 4 | 3 × (step + reference) per quantity and record |
| Q4 | Analytic limits (§7.3) | Compact | As stated |
| Q5 | Observed order about 2 after partitions | Compact; 0.5, 0.25, 0.125 ms | Reported by inspection, with S3's stop condition (every step term decreases) |
| Q6 | Restart and batches (items below) | Compact | Bitwise for restart and against reversed order; within 1e-12 relative of scalar runs |
| Q7 | Idle and unchanged (items below) | As listed | As listed |
| Q8 | Each refusal (§3.8, §4.4, §5) | Compact | Refused with its message; the prior state is kept |
| Q9 | Closed slots are @3 padding at the view; the lumen's padded-slot test | Compact | Domain valid at the view; observations of closed slots are padding |
| Q10 | Sensitivity to the partition time and to a_0 (§4.2) | Compact 1 → 2 and 1 → 2 → 4, with and without injection into one daughter | Each compared quantity's change over the declared ranges is reported against its tolerance; "insensitive" only within it, otherwise t_p and a_0 enter its band |
| Q11 | The retirement record is state wherever state goes (items below) | Compact; egg-scale | Every check passes; the negative control fails |

The Q6 items:
- **Restart** at t_e − dt, t_e and t_e + dt, bitwise.
- **Restart from a checkpoint written after a partition** (at t_e + k dt, through a written
  snapshot, loaded in a fresh process), bitwise against the uninterrupted run.
- **Mixed batches.** S2's onset-mask bug was a static shape the batch signature could not see
  (fixed in 00672e8). So every shape that decides a static branch enters the batch signature:
  the division count and slot maps, the bridges, and the presence of closers and of the
  offsets E_ref and q_ref (§3.6).
  - A vector-window batch with device checks mixes worlds that differ only by value: events
    within and beyond the horizon, onsets or none, fractions, apertures and closure times. Each
    world equals its scalar run within 1e-12 of each field's scale, and the batch is bitwise
    against itself reversed.
  - A batch mixing a world with divisions and one without, or different slot maps, is refused
    by the signature, with a message.
  - E_ref and q_ref are bound arrays (bindings), one per world. They are never constants closed
    over by the traced program, which the constants-aware crossrev checks (§8.4).

The Q7 items:
- a partition with no divisions declared is statically idle, and so is a bridge with no
  bridges: both bitwise against the composition without them;
- the 19-cell sheet at the 64-node cap with idle division operators: bitwise;
- **S3's cleft egg on insertion@2 and lumen@2 (criterion fixed before any run):**
  - **The pass criterion is S3's registered protocol against R-full.** S3's judge runs once, from
    a clean snapshot, on S3's definition with the two new versions, under S3's registered
    tolerances (Q1, Q2, Q4, Q5; Q3 reported).
  - **The vehicle: a registered operator variant of S3's protocol.**
    - S3's judge refuses an unregistered protocol, and S3's judged run is not rerun.
    - The variant names S3's protocol as its base and changes only the operator list
      (insertion@2 and lumen@2), with the tolerances unchanged. It is registered before its run.
    - The precedent is the L4 backend variant of v2 §5: judges accept the registered protocol or
      a registered variant of it (bb40855).
    - S3's judge (`cleft_egg_engine judge`) gains that acceptance in S5a.
  - The comparison with S3's judged run is reported, bitwise or with each difference's size. It
    is not a pass criterion.
  - **Why this criterion.**
    - Insertion@2 and lumen@2 are new law IDs, not re-expressions of one ID, which is the case
      D143's bitwise rule covers. They are qualified as new laws are, by the registered protocol
      of the world they reproduce.
    - The engine does not promise identical bits across different compiled programs: XLA's
      association differed between programs in S3's prerequisite (c). The composite's view and
      the new offsets compile differently from insertion@1's own view. A bitwise criterion
      would let fusion, not physics, decide the verdict.
    - S3's tolerances are tight (1.0e-9 V on Em, 15.3 Ω on Rm, 2.6e-6 mM in the lumen; the
      judged run sat at 0.36–0.51 of them). A physics error in the new versions would show.
- crossrev (§8.4): identical jaxprs, constants and bindings.

The Q11 items:
- the history rows carry the record;
- a checkpoint written after a partition carries it, and its restart is bitwise (Q6);
- every host replay carries it: `check_values` on the saved history closes every ledger at the
  event row; `observe_history`'s partition columns equal the record; the summary's totals add it;
- a negative control: a replay with the record zeroed fails the local and outside ledgers at the
  event row.

The tolerance rule follows G2-Q1 and S3: 3 × (engine step term + reference term + rounding term),
pinned at registration from development runs that are disclosed. The judged run is made once,
from a clean snapshot.

### 8.4 Shared code: crossrev and D148
- **What changes.** `contract.py`, `pump_composite.py` and `pump_composite_adapter.py` are
  shared by every composition. Every S5 change is a static branch (a closer, a retiring
  operator, a view-energy writer).
- **Crossrev, constants-aware.**
  - "Static branch, identical jaxprs" is decided by the constants-aware baseline. The checkpoint
    agent is producing it now: `composite_crossrev` records the dtype, shape and SHA-256 of
    every constant each traced program closes over, and the device-check constants among the
    bindings (aaa0044 on its branch).
  - The old baseline (`cell-division-s3-20261113-01/crossrev-landing`: base 36 and 12,
    qualification 78 and 56, injection 6 and 2) compared jaxpr text, which does not print
    closed-over arrays.
  - The t = 0 fix binds two constants, exactly what that old comparison could not see.
  - S3's cleft egg and v2 §2's `volume` set join the sets.
  - The guard expects identical jaxprs, constants and bindings for every existing composition.
  - For S5's own worlds, it records E_ref and q_ref as bindings, never as closed-over constants.
- **If any jaxpr of an existing composition differs**, the change is an in-place change to
  shared qualified code and needs D148's four criteria, fix against no fix.
- **Gates.** Tier 1 and tier 2 before landing (AGENTS.md).

### 8.5 Order of work
1. Contract, composite and adapter.
2. Insertion@2 and lumen@2, with S3's re-expression guard.
3. The partition.
4. The bridge.
5. R-ops and R-tissue.
6. Worlds, development study, registration of the S5 protocol and the judged run.

Each step lands behind its tier-1 tests. Long runs go through `scripts/run_detached.sh`.

## 9. S4: superseded and reported (taken by the lead, 13 November)
- **The arithmetic.**
  - S3's judged run gives the engine's Em at J1 under J1's registered defaults: +4.0e-10 V
    from R-full's −12.79494 mV, inside its 1.0e-9 V tolerance (Q1, PROGRESS 13 November).
  - R-full's J1 band is −14.6 to −11.3 mV, against −20.3 ± 0.8 mV measured, and misses the
    2-SE window by 4.1 mV.
  - So an engine J1 verdict equals R-full's: fail. No plausible engine–reference difference
    near 1e-9 V moves a 4.1 mV margin. S3 judged the default only; the band members follow by
    the same smooth dependence (S).
- **Proposal.** S4 is superseded and reported as a PROGRESS entry: "the engine's J1 verdict is
  R-full's, by S3's registered agreement". No run, about 0.25 day.
- **Alternatives:**
  - a registered single-item S4 protocol applying the J1 window to S3's judged Q1 (bookkeeping
    only);
  - the full J1 band on the engine (23 egg runs, about 20 CPU hours): no new information.
- **Taken.** S4 is superseded and reported, with no run. The lead records the decision when this
  note lands.

## 10. J2 later: how it would be registered (not computed)
- **Prediction of record from R-tissue under J2's declared defaults**, registered before any
  model computes a DFS74 quantity. The defaults:
  - the old membrane set from DFS74's own one-cell Em (design §8.1);
  - the same new-membrane and cleft laws, with no refit;
  - the second- and third-furrow geometry (third furrows' onsets only: the 4-cell sampling is
    after the third furrow began; 7 cells, 8 outside nodes, 15 field nodes);
  - partition times and a_0;
  - the closure time τ_c with a band;
  - DFS74's sampling phases.

  The protocol also fixes the one-at-a-time ranges and a maximum band width.
- **Judged:** blastomere Em at 2 and 4 cells against DFS74 Table I, under the J1 rules.
- **The engine:** an S3-style comparison with R-tissue on J2's definition, so the engine
  inherits R-tissue's verdict.
- **Reported:** Rm per cell, Rj and the coupling ratio (tied, design §7).
- **Blocked:** J2 and C1 are held (D145; PROGRESS, the combination round). With J1's failure
  unexplained, whether J2 tests anything new (the same cleft laws in another lab's eggs) is the
  user's decision.
- **Effort after S5:** about 1.5–2 days.

### 10.1 The J2 bright line: the barred set and its static test
**The barred set.** Until the user releases J2, nothing in the repository computes either of:
1. **J1 input plus a partition.** A world, definition or reference input built from the J1
   declared inputs (`validation/division/j1_declared_inputs.json`) or the J1 record
   (`validation/division/j1_prediction_of_record.json`), directly or through a function that
   reads them, together with a partition. A partition here means any of:
   - an `isopotential_partition@1` declaration;
   - the partition definition helper;
   - R-ops' partition map;
   - R-tissue's division events.

   This holds in any engine run, reference run, test or analysis.
2. **DFS74 as input or target.** Any computation that takes DFS74's Table I or Fig. 2 values, or
   its sampling phases, as an input or a comparison target.

**Allowed:**
- J1-built worlds without a partition: S3's egg and its judge, and R-tissue's static
  cross-check against R-full;
- partitions on worlds built from neither J1 input (§8.1);
- the risk-1 probe (built from the S0 smoke egg, with no partition).

**The test, `tests/unit/test_j2_bright_line.py`.** It is written with S5a's first code and
mirrors `tests/unit/test_d147_drivers.py`.
- **Scope.** It parses every module under `validation/`, `tests/` and `scripts/` with `ast`,
  skipping docstrings, which cite the files freely. `current_injection.py`'s docstring names
  the J1 inputs, for example.
- **A J1 source in a module** is any of:
  - a non-docstring string constant containing `j1_declared_inputs` or
    `j1_prediction_of_record`;
  - an import of a J1 module: `validation.division.cleft_egg_engine`, `static_cleft_egg_steps`,
    `j1_diagnostic_runner`, `j1_combination_runner` and `cleft_rings_reference`;
    `validation.tissue.injection_rm1`; `tests.division_fixtures`;
  - the use of a J1-reading function of `validation.division.cleft_egg_reference` (`DECLARED`,
    `load_declared`, `build`, `scalar_values`, `band_members`), counted at function level as
    D147's `BUILDER_FUNCTIONS` are. R-tissue imports that module's transport laws (`ghk_flux`,
    `access_flux`) without reading J1.
- **A partition source** is any of:
  - a non-docstring string constant `isopotential_partition@1`;
  - an import of the engine's partition module or its definition helper (their paths are fixed
    when built);
  - an import of `validation.division.partition_reference` (R-ops);
  - the use of `cleft_tissue_reference.simulate_divisions`. R-tissue keeps its static entry
    point, `simulate_static`, apart, and its R-full cross-check lives in its own module.
- **The rule.** A module that holds both a J1 source and a partition source fails, unless it is
  listed in `EXEMPT` with its reason. `EXEMPT` starts empty. A J2 driver enters it only after the
  user releases J2, citing that decision.
- **Self-checks, as D147's:**
  - each listed J1 module and function still holds a J1 source, so the list stays honest;
  - synthetic sources show the scan catches each form: a literal, a module import, a function
    import, an attribute use of a listed function, and the partition literal;
  - a docstring mention is shown not to count.
- **Limits, as D147's.** The check is static, at module granularity, and sees only the listed
  sources. Use through an unlisted builder is outside its reach; the rule binds anyway.

## 11. Effort (revised)

| Part | Agent-days |
| --- | --- |
| Contract, composite, adapter (closers, propagation, padding, event views, adjusted-row checks, the energy rule's move), unit tests, crossrev and D148 | 1.5 |
| Insertion@2 and lumen@2, with S3's re-expression guard (one run of about an hour) | 1.5 |
| `isopotential_partition@1`: spec and helper, event map, retirement, bookings, refusals, lineage, R5; smoke tests and compiled runs | 2.0 |
| `cytoplasmic_bridge_closure@1` | 0.5 |
| R-ops and R-tissue, with R-tissue's cross-check against R-full (a separate agent, in parallel, from Appendix A) | 1.5 |
| The review's added guards: the J2 bright-line test, the NumPy live-slot energy test, restart after a partition, mixed batches, Q10's sensitivity runs and Q11's record checks | 0.5 |
| Worlds, development study, protocol, judged run | 1.5, plus 3–6 CPU hours |
| **Total** | **9 (range 8.5–10.5)** |

- **Staging (approved).**
  - **S5a** (about 5.5 days): the first four parts and R-ops, with 1 → 2 on the compact world
    and at egg scale. Also the bright-line test, which is written with S5a's first code.
  - **S5b** (about 3.5 days): R-tissue, 1 → 2 → 4 (at egg scale too, since the risk-1 probe is
    clean), the egg-scale world, populations on onset patches (decision 9), the protocol and the
    judged run.
- **Against the original estimate.** The original 3–4 days assumed design §4.2's four
  operators on a static topology, and included J2. The difference is the as-built facts of §1:
  - @3's padded-slot domain makes retirement necessary;
  - mask ownership needs closers;
  - S3's two operators need new versions;
  - the references must cover N cells.

  J2 moves out (held).

## 12. Decisions (taken by the lead on 13 November, after the advisor's review)

| # | Choice | Taken |
| --- | --- | --- |
| 1 | Slot rule: fresh slots for both daughters (design §5.2), not reuse of the parent's slot for one | Accepted |
| 2 | Retirement: the parent presented to @3 as padding, with a record added back (§3.5), not a projected state for @3 | Accepted |
| 3 | Mask ownership: closers by conjunction (§2), not one topology-state owner with ledgered writers | Accepted |
| 4 | Reference anchors at birth: declared exact fractions of the parent's declared anchors (D057 kept); triggered divisions with declared fractions need no re-anchoring either (§6.3) | Accepted |
| 5 | Slot reuse and capacity: none in S5 (2^(k+1) − 1 cells; 47 nodes at 16 cells); reuse and re-anchoring at milestone 2 (a user decision against D057) | Accepted |
| 6 | Lineage: declared carrier IDs, host records from applied flags, one record shape with replacement | Accepted |
| 7 | New versions insertion@2 and lumen@2; @1 stays registered for S3's world | Accepted |
| 8 | The composite owns the energy rule at the view (§5.3), referenced to the view of the initial state when a closer is present (§3.6 point 4) | Accepted |
| 9 | Populations on onset patches: admitted by the padding rule | Deferred to S5b; insertion@2 keeps insertion@1's refusal in S5a |
| 10 | S5's worlds: built from neither J1 input; the J2 bright line (§10.1) | Not ruled on separately. My reading: it is governed by the lead's bright-line instruction. Pending the lead's confirmation |
| 11 | Scope refusals: pumps on dividing cells, water (volume provider), replacement, asymmetric egg-scale divisions until `check_definition`'s scale-aware bound | Accepted |
| 12 | Bridge: an @3 junction with P A = 2 a D_s and a fixed open gate, prescribed closure (linear or exponential), a_0 bounded by dt | Waits for the cytoplasmic conductivity's source; until then a declared assumption with a band. σ_cyt enters only through G_b0 = 2 a_0 σ_cyt, so the wait does not hold up S5a's code (§4.2) |
| 13 | S4: superseded and reported, no run (§9) | Accepted; the lead records it when this note lands |
| 14 | Staging | S5a (about 5.5 days) and S5b (about 3.5 days, with the review's guards) approved. S5a lands after the volume ledger; code starts after the risk-1 probe and the constants-aware baseline |

## 13. Risks
1. **The electrode ledger at four cells.**
   - The bath couples to four charged free nodes.
   - D148's exactness condition (no held node coupled to three or more charged free nodes)
     fails there, so the electrode ledger rests on its bound, as in tissue worlds.
   - **Probed before any code** (the lead, 13 November).
     - The probe: `validation/division/four_cell_electrode_probe.py`, a static egg-scale world
       of four quarter eggs on one held bath. It uses no S5 code and is built from the S0 smoke
       egg, not from J1.
     - Three species move in every cell: K and Cl by pulses through one electrode per cell, Na
       and K through the membranes.
     - It runs at 0.25 ms for S3's bounded-probe length of 1.78e6 steps, with the one-cell
       control, which is D148's exact case.
     - **Result: clean, no drift** (§0). The residual stays within a couple of ulps of the plate
       charge, with an asymptotic ratio of 8e-12 against the one-cell control's 1e-16.
       Egg-scale 1 → 2 → 4 stays in the plan, and the S5 worlds' device checks measure the
       ratio again.
   - **If it drifts,** egg-scale 1 → 2 → 4 needs either an ordered node sum (another D148 round
     in `surface_tissue.py`) or an allowance, which is the user's call. S5a then stops at 1 → 2
     at egg scale, and four cells run on the compact world only.
2. **Re-expression of S3's egg.** XLA's fusion of the composite's view and insertion@2 may differ
   in the last bit from insertion@1's own view (the prerequisite (c) lesson). So the criterion,
   fixed before any run, is S3's registered protocol against R-full, with the bitwise comparison
   reported (§8.3, Q7).
3. **Shared-code changes.** Static branches are expected to leave every existing jaxpr
   identical. If one changes, D148 applies, and the stop rule follows.
4. **Composite complexity.** Closers, propagation, padding, retirement and the energy rule's
   move each add a static branch to the composite. Each has a tier-1 test and a crossrev guard.
5. **The cleft model is parked (J1).** S5's operators are general and do not depend on it. Any
   Xenopus physiology claim does (J2, held).
6. **Cost.** Eleven field nodes refactorise every step (R3), cheap below 64. The development
   study and the judged run are a few CPU hours.

## Appendix A. Equations for the independent references

R-ops and R-tissue are written from this appendix and the physics, without the engine's
partition, bridge, insertion@2 or lumen@2 code (§7). These conventions hold throughout:
- **Units:** SI, except amounts in fmol and volumes in pL, so n/V is in mM = mol/m³.
- **Constants:** F = N_A e and R = N_A k_B, the exact SI products, as R-full uses.
- **Free energies:** in pJ.

### A.1 The world
- **Species:** s, with valence z_s: Na +1, K +1, Cl −1 in S5's worlds.
- **Cells i.**
  - State: amounts n_{s,i} (fmol).
  - Declared: volume V_i (pL), fixed during S5, and a fixed background X_i (fmol of charge
    equivalent, constant).
  - Node charge Q_i = 10⁻¹⁵ F (Σ_s z_s n_{s,i} + X_i) (C).
- **Finite outside nodes c (clefts).** Amounts n_{s,c} and volume V_c(t) (§A.5). No background:
  Q_c = 10⁻¹⁵ F Σ_s z_s n_{s,c}.
- **The held bath b.** Potential φ_b = 0 and composition c_{s,b}, fixed: it supplies whatever it
  exchanges. Σ_s z_s c_{s,b} = 0.
- **Patches k.**
  - Endpoints: the inside cell i(k) and the outside node o(k).
  - Area A_k (m²), capacitance C_k (F), and permeability per area P_{k,s} (m/s), constant per
    patch.
- **Faces f** (accesses): between two outside nodes (a cleft and the bath, or two clefts), with
  k_{f,s} = (A/L)_f D_s (m³/s).
- **Bridges e:** between two cells, with aperture a_e(t) (m) and P_{e,s} A_e = 2 a_e(t) D_s^cyt
  (m³/s).
- **Liveness.** Each cell, patch, node, face and bridge is live or not at time t (§A.4 onsets,
  §A.6 partitions).
  - A patch is live only if its cell and node are; a face only if both its nodes are; a bridge
    only if both its cells are.
  - Only live entities enter A.2 and A.3.

### A.2 Electrostatics
- **Nodes.** Free nodes are the live cells and the live clefts; the bath is held.
- **The capacitor law.** K = Σ_{live k} C_k e_k e_kᵀ, with e_k = u_{i(k)} − u_{o(k)} (unit
  vectors over the nodes).
  - Node charges are Q = K φ.
  - The free potentials solve K_ff φ_f = Q_f, since φ_b = 0.
  - Every capacitor component holds the bath: every live cell has a live patch on it.
- **Patch quantities.**
  - Patch voltage V_k = φ_{i(k)} − φ_{o(k)}, and its cell-side charge q_k = C_k V_k.
  - A cell's charge is Σ_{k: i(k)=i} q_k, and a cleft's is −Σ_{k: o(k)=c} q_k.
- **The bath's plate charge:** q_b = (K φ)_b = −Σ_{live k: o(k)=b} C_k φ_{i(k)}.
- **Capacitor energy:** U = ½ Σ_{live k} C_k V_k².

### A.3 Transport rates
- **Notation.** ψ(x) = x / (1 − e^{−x}), with ψ(0) = 1, and concentrations c = n/V. In fmol/pL
  that is mM, which equals mol/m³, so the fluxes below are in mol/s with no conversion factor.
- **Membrane patch k**, outward constant-field flux (mol/s):
  J_{k,s} = P_{k,s} A_k ψ(x) (c_{s,i(k)} − c_{s,o(k)} e^{−x}), x = z_s F V_k / (R T). The
  bath's concentrations are c_{s,b}.
- **Face f from node c to node d.** One of R-full's two declared laws:
  - log-mean: J = k_{f,s} L(c_c, c_d) [ln(c_c/c_d) + z_s F (φ_c − φ_d)/(R T)], with
    L(a, b) = (a − b)/ln(a/b) and L(a, a) = a;
  - constant field: k_{f,s} in place of P A, with x = z_s F (φ_c − φ_d)/(R T).
- **Bridge e from cell 1 to cell 2:**
  J_{e,s} = 2 a_e(t) D_s^cyt ψ(x) (c_{s,1} − c_{s,2} e^{−x}), x = z_s F (φ_1 − φ_2)/(R T).
- **Current injection** I(t) into cell i (A; positive means cations in), with carrier fractions
  f_K + f_Cl = 1: dn_K/dt gains +10¹⁵ f_K I / F, and dn_Cl/dt gains −10¹⁵ f_Cl I / F.
- **Balances (fmol/s).**
  - A cell loses 10¹⁵ J_{k,s} through each of its patches, and 10¹⁵ J_{e,s} through each bridge
    it sends on, gaining the same from each bridge it receives on. Injection adds its terms.
  - A cleft gains 10¹⁵ J_{k,s} from each patch facing it, loses 10¹⁵ J_{f,s} through each face
    it sends on (gaining the same through each face it receives on), and gains its fill (§A.5).
  - The bath supplies whatever it exchanges.

### A.4 Insertion and onsets
- **Insertion.** A patch k is inserted at a declared, piecewise-constant rate r_k(t) ≥ 0:
  - dA_k/dt = r_k and dC_k/dt = c_d r_k, with P_{k,s} per area unchanged;
  - the free-node charges stay fixed while C changes, and the potentials are re-solved by A.2;
  - the bath supplies the image charge Δq_b;
  - the insertion heat rate is ½ Σ_k c_d r_k V_k² ≥ 0 (pJ/s after × 10¹²), R-full's form.
- **Onset** of an inserted patch k at t_on. The patch becomes live with its declared area A_on
  and C = c_d A_on, together with its cleft c.
  - The cleft opens at bath composition, n_{s,c} = c_{s,b} V_c(t_on), with zero charge.
  - Its faces open when both their nodes are live.
  - Patches facing c that are not live at t_on (pending daughters) stay closed until their
    birth.

### A.5 Lumens
- **Volume.** V_c(t) = V_on + w (Σ_{live k: o(k)=c} A_k(t) − A_on)/2. Here A_on is the summed
  area of the patches that open with c, V_on = w A_on / 2, and w is the declared gap width.
- **Fill.** Bath fluid at bath composition, with no water flow: dn_{s,c}/dt gains
  c_{s,b} dV_c/dt.
- **Continuity.** A partition keeps the live facing area unchanged (§A.6), so V_c is continuous.

### A.6 The partition map (R-ops)
**Inputs at t_p:**
- the parent P and its live patches k ∈ K_P;
- the daughters D1 and D2, with daughter patches k¹ (in D1) and k² (in D2) for each k, facing
  o(k);
- the fractions f (volume) and a_k (patch k's area to D1), all in (0, 1);
- the mismatch carriers, with t_s ≥ 0, Σ t_s = 1, charged species only;
- the parent's declared anchors: reference amounts n̄_P, V_P, X_P.

**The map:**
1. **Pre-event state.** A.2 with P live gives q_k = C_k V_k for k ∈ K_P.
2. **Mismatch.** δq = Σ_{k∈K_P} (a_k − f) q_k, and δ_s = 10¹⁵ t_s δq / (z_s F) fmol. δ = 0 when
   every a_k = f.
3. **Contents.**
   - Amounts: n_{D1} = f n_P + δ and n_{D2} = n_P − n_{D1}.
   - Volumes: V_{D1} = f V_P and V_{D2} = V_P − V_{D1}.
   - Backgrounds: X_{D1} = f X_P and X_{D2} = X_P − X_{D1}.
   - **The engine's increment form,** for comparing bookings:
     - anchors n̄_{D1} = f n̄_P and n̄_{D2} = n̄_P − n̄_{D1};
     - increments Δ = n − n̄: Δ_{D1} = f Δ_P + δ and Δ_{D2} = Δ_P − Δ_{D1};
     - the parent's increment becomes 0, so the moved amounts are −Δ_P at P and +Δ_{D1}, +Δ_{D2}
       at the daughters.
4. **Patches, populations and contacts.** The partition (S5a) maps all three. Only populations
   on *onset* patches wait for S5b (decision 9).
   - **Patches:** A_{k¹} = a_k A_k and A_{k²} = A_k − A_{k¹}; C likewise; permeability per area
     unchanged.
   - **Populations.** Each population j (abundance N_j in units, a unit permeability, gate
     values g_j) on a parent patch k maps to declared populations j¹ on k¹ and j² on k², with the
     same law and unit permeability.
     - N_{j¹} = a_k N_j and N_{j²} = N_j − N_{j¹}.
     - Both take the parent's gate values g_j (gates are intensive).
     - A population's conductance is its abundance times its unit permeability, so the split
       conserves it.
   - **Contacts to neighbours.** Each contact e between P and a neighbour cell M (area A_e,
     permeability per area, gate g_e) maps to declared daughter contacts e¹ (D1–M) and e² (D2–M).
     - Their areas are a_e A_e and A_e − a_e A_e, with permeability per area unchanged.
     - Both take g_e. a_e ∈ [0, 1] is declared from the geometry: 0 or 1 when only one daughter
       touches M.
     - The parent's contact retires with P.
   - R-ops needs these maps only, not the gate kinetics.
5. **Liveness.**
   - P and K_P stop being live (retired); their accumulated transfers and heats are kept, and
     still count in the totals.
   - D1, D2, their patches and the bridge between them (aperture a_0) become live.
   - Outside nodes and faces are unchanged.
6. **Identities and outputs.**
   - Charge: Q_{D1} = Σ_k a_k q_k, and Q_{D1} + Q_{D2} = Q_P.
   - Potentials after (A.2 with the new liveness): φ_{D1} = φ_{D2} = φ_P, and every outside
     potential is unchanged.
   - Plate charge and energy: Δq_b = 0 and ΔU = 0.
   - Material: n_{D1} + n_{D2} = n_P per species, and the areas and capacitances sum to the
     parent's.
   - Free energy, with G(n, V) = 10⁻³ R T Σ_s n_s (ln(n_s/V) − 1) (pJ; n in fmol, V in pL):
     ΔG = G(n_{D1}, V_{D1}) + G(n_{D2}, V_{D2}) − G(n_P, V_P) ≥ 0. To leading order this is
     10⁻³ R T Σ_s δ_s² / (2 n_{s,P} f (1 − f)), and it is exactly 0 when δ = 0.
   - The booked work: W = ΔG + 10¹² (ΔU − Σ_b φ_b Δq_b) (pJ; U from A.2 is in J). At a bath
     held at 0 V, this is ΔG.
7. **Refusal.** A daughter amount ≤ 0 refuses the event, which leaves the pre-event state.

### A.7 The bridge closure
- **Aperture.** a(t) = a_0 for t < t_b = t_p. After that it closes as one of:
  - linear: a(t) = a_0 max(0, 1 − (t − t_b)/τ_c);
  - exponential: a(t) = a_0 e^{−(t − t_b)/τ_c}.
- **Diffusivities.** D_s^cyt = D_s σ_cyt / σ_free, with σ_free = (F²/RT) Σ_s z_s² c_s D_s
  (S/m, c in mol/m³) at the cytosol's declared composition (§4.2).
- **Conductance.** For equal concentrations on both sides it is G_b = 2 a σ_cyt.

### A.8 What is compared with the engine
- **R-ops.** Every output of A.6 steps 3–6, on 200 random states and on each world's events.
  - Random states: positive amounts, backgrounds, volumes, areas, capacitances and charges, with
    f and a_k in (0, 1) and random transference numbers.
  - Pass: 64 eps × magnitude.
- **R-tissue.** Radau at rtol 1e-10, with breakpoints at every onset, partition, closure end,
  pulse edge and record. R-ops is applied at each partition. Compared at the records:
  - each live cell's Vm, φ_i − φ_b;
  - each lumen's composition and volume;
  - each bridge's current, Σ_s z_s F J_{e,s} (A).
