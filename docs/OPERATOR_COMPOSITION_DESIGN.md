# Operator composition: operators that read each other's current state (design)

**Status: DECIDED, 16 November 2026: option A, one general rule (D191).** Built in step 3 of D194's
order. Proposed the same day, written by this lane's operators owner for the lead. The
advisor reviews it before its options go to the user (D142: options first, then discussion). Docs
only; nothing here is built. Branch `composition-design` from 3c10b833 (integration-d172's c1).

**M1 landed, 18 November 2026 (§17):** the composite's rules C1–C4, built on branch
`core-pass-operators-m1` and merged into main as `core-pass-operators-b1` at 42ca1c94 (merge
c78462e7). Every operator is unchanged. M2–M5 follow B1 (CORE_SEAMS §18 as amended).

**Engine models:** `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with
`membrane_entity_state@1`, `scheduled_membrane_insertion@2`, `ideal_osmosis_linear_compliance_water@1`,
`scheduled_species_turnover@1`, `isopotential_partition@1`, and @3's Na/K pump for gap 4.

**S** marks our own reading or derivation. Evidence: `/mnt/workspaces/Cells/composition-design-20261116/`
(§15).

## 0. The acceptance criteria

The user, 16 November 2026: "we want to have our architecture clean, extendable and fast."
Every option below is judged against these three.

- **Clean.** One general rule by default (option A). Each operator declares statically, per field
  and stage, whether it reads `current`, `fixed` or `reference`, and its law ID stays the same. A
  new `@2` only where the physics or the accounting genuinely differs, with the reason given.
- **Extendable.** A new operator joins a composition by declaring its reads and changes. No other
  operator is edited and there is no pairing table. A planted third operator shows it (§12).
- **Fast.** Read modes resolve when the model is built, so nothing branches at run time. Worlds
  that do not compose get identical programs and pay nothing. Composed worlds' step and compile
  costs are estimated, with a measurement plan, and no per-step host work is added (§11).

## 1. Summary

1. **The list is closed, and "four" was a lower bound** (§2). The full-cycle definition was built
   and parsed once, then lifted layer by layer, host only. It has **eight items**:
   - the four as stated, with gap 1 split into production (1a) and the partition (1b);
   - **gap 5, new and silent:** water reads the activity masks without declaring them. In the
     cycle it moves water across the daughters' patches before they are born;
   - **gap 6, new, the composite's own rules:** declaring the reads `current` instead of `fixed`
     is refused twice. Outside a composition there is no provider, and inside the cycle the
     admission order is circular (mask readers must follow the partition, and the partition must
     follow water);
   - **gap 7, beyond the minimal cycle:** the furrow world. Water and a lumen both provide one
     cleft's volume, and an onset node's volume must keep its anchor;
   - **item 8, by design and not a composition gap:** FR-11's "ions' share" of growth cannot be
     produced. Turnover "acts on neutral species only (valence 0)", because producing a charged
     species would create charge. That share must come through transport: pumps (gap 4) or the
     K-anion symport over water.

   Once the seven declared fixed reads are lifted, **nothing else in the engine refuses the
   cycle.** What remains is silent: water on closed slots, volume lost at division, a pre-birth
   rate admitted, and a retired patch's pump still cycling. The probe found each by evaluating
   the parts in NumPy.
2. **The central option** (§4).
   - **(A):** one general rule plus six small, general refinements of the contract and the
     composite (C1–C6), with no new law IDs.
   - **(B):** a new `@2` per pairing.
   - **Recommendation: A.**
     - The read rules (C1–C4) cost about 2.5–3.5 days, paid once in M1. The two booking rules
       (C5, C6) sit inside M4, the partition over water.
     - Existing qualifications stay valid, because non-composing programs are identical, which
       meets D148's criteria by construction.
     - B adds three or four laws, each unqualified on every world, and it still needs the same
       order rule.
3. **No `@2` is needed in this lane.** The partition over water is the one place where B is
   defensible, because its accounting genuinely changes. So is the partition's pump record in gap
   4. A keeps each one law through declared conditional bookings, keyed on a static condition of
   the composition's structure (§4.4).
4. **Gap 4 is ownership, not a read** (§13). Behind its parse refusal, a retired parent's pump
   keeps cycling at a rate independent of its closed cell's contents, consistent with the inner
   model's placeholder concentration, and writes Na and K into the closed cell. Static pumps on a
   dividing cell cost about 2.5–3 days. Capacity as state and kinds beside closers are the core
   owner's (questions in §13.4).
5. **No gap has a registered judged consumer today** (§10). The division plan's judged observables
   (Xenopus, 1 to 4 cells) need no water, growth or pump. This is a finding for the lead:
   numerical qualification can proceed, but judged status waits for a consumer protocol.

## 2. Step 1: the gap list, closed

### 2.1 What was built

The world is S5's compact world: one heredity cell facing its held bath, dividing into d1 and d2
at 2 ms (`tests/partition_fixtures.parent`). The secreted species S (D150) is declared before the
split, so its daughter anchors follow the anchor rule.

The five operators run in the cycle's declared order:
1. `membrane_entity_state@1`;
2. `scheduled_membrane_insertion@2`: the parent's patch grows until the division, and each daughter's
   patch at half the rate after it;
3. water, with the approved heredity arm's values (`validation/tissue/pump_water_fixtures`);
4. turnover, producing S at the parent until the division and at each daughter after it;
5. the partition.

A variant keeps the heredity Na/K pump on the parent.

**The layers**, each host only, with nothing jitted:
- **L0:** `structure_errors` on the full list, and `scope_errors` on the parsed definition;
- **L1:** every parser;
- **L2:** the seven refused fixed reads lifted in probe-local subclasses with the same law IDs,
  then `Composition.check_definition`'s checks run one by one, and the bound step checks;
- **L3:** an AST scan of each operator's module for reads of view and padded fields, by the name
  they are read through;
- **L4:** the lifted parts evaluated in NumPy at the bound state;
- **L5:** what lies behind the pump refusal;
- **a second pass** with the refused fields declared `current`, not just lifted, and the furrow
  world with water;
- **a third pass:** ion production, the planted pre-birth rate through every definition check, the
  RK4 rule raised by the engine itself, the retired pump's inputs, and the K-anion symport beside
  the cycle.

### 2.2 What the engine says

- **L0, in the engine's words.** Seven structure errors. `scope_errors` is empty, because no
  operator of the cycle declares a scoped change or read.
  - "ideal_osmosis_linear_compliance_water@1 reads membrane_area as declared, but
    membrane_entity_state@1 provides it"
  - "scheduled_species_turnover@1 reads volume as declared, but
    ideal_osmosis_linear_compliance_water@1 provides it", and the same for extracellular_volume
  - "scheduled_species_turnover@1 reads active as declared, but isopotential_partition@1 closes it"
  - "scheduled_species_turnover@1 reads outside_active as declared, but
    scheduled_membrane_insertion@2 closes it", and the same for membrane_active
  - "isopotential_partition@1 reads volume as declared, but ideal_osmosis_linear_compliance_water@1
    provides it"
- **L1.** "Pumps on a dividing cell are later work (pump capacity as state)" comes from the
  partition's parser. `core/partition_spec.add_division` refuses the pump earlier still.
- **L2.** With the seven fixed reads lifted, the structure check passes and **every definition
  check passes**: species registry, scope, event times, compact binding, field inputs, every
  scheduled control's domain, each operator's `check_definition` and the bound step checks.
  - The only other refusal is under RK4. Run on the cycle with solver `rk4`, the engine's own
    `Composition.check_definition` says: "An RK4 composition with a coupled operator cannot hold
    event maps, split-only parts or integer state". Water's coupled part sits beside event maps and
    split parts, so references must come from NumPy and IMEX self-convergence (§10).
- **The ions' share** (third pass). A turnover route on K or on P is refused at the parser:
  "scheduled_species_turnover@1 acts on neutral species only (valence 0); 'K' has valence 1", and
  likewise 'P' with −1. The closure therefore covers neutral production only (item 8).

### 2.3 What the engine does not say

**L3, reads no declaration shows** (the AST scan; each read is classified in §3):
- Water reads `active`, `outside_active` and `membrane_active` from the declared layout, and none
  of them is declared.
  - `osmotic_water.bind` copies them into `water_active` and `water_edge_active`, which
    `edge_exchange` and `finite_nodes` use for its rates.
  - Its domain, ledgers, control check and observation read them too.
- @3's pump is gated by `pump_present`, which is declared layout, not by the view's patch mask
  (`surface_pump_v3.py:562`).

**L4, the lifted parts on closed slots.** Evaluated in NumPy at the bound state, on the probe's
compact world.

| What | Result | So |
| --- | --- | --- |
| The masks at t = 0 | The view closes d1, d2 and their patches. Water's bound masks and turnover's `p.active` hold them all open | The two readers see slots the partition keeps closed |
| Water's rates at t = 0 | −0.0014 pL/s at each pending daughter (half the parent's −0.0028) | Water flows through patches that do not exist yet |
| A turnover rate on d1 before its birth (planted) | Admitted: the planted world passes every definition check (third pass). The first half-step writes 5.0e-13 fmol into d1. At the division the partition overwrites d1's increment, and S's material ledger at d1 reads −2.0e-12 fmol | No rule refuses it at the definition. Only the run-time ledger would catch it |
| The partition's event after two water and turnover steps | The parent's −5.58e-6 pL stays on the retired slot. The daughters keep the −2.79e-6 pL each that water gave them while pending | The volume is never moved. In this symmetric world the sum matches only because water ran on the daughters in proportion |
| The same with strong production at the parent (1000 fmol/s) | The daughters' volumes sum to the parent's minus 2.36e-7 pL after 2 ms | Volume is lost at division, and every ledger still closes |

Water's ledgers close throughout (`water_local` reads 0 at every cell). The volume error is
invisible to the checks, which is why gap 5 matters.

### 2.4 Declaring the reads `current`: the composite's own rules

Lifting a fixed read is not declaring it current. So the second pass declares the refused fields
current, in probe-local subclasses: each field in `VIEW_READS`, with a `SCOPED_READS` current entry
at the part's stage.

| Composition | The engine's words | So |
| --- | --- | --- |
| The cycle in its declared order | water and turnover "read the view active; no earlier operator provides it", and "reads active before a closer of it" | A mask reader must follow the partition |
| The partition moved before water and turnover | "isopotential_partition@1 reads the view volume; no earlier operator provides it" | The partition must follow water: **a cycle in the declared order** |
| Turnover alone, water alone, the partition with its membrane state | "reads the view volume (area, masks); no earlier operator provides it" | **Worlds that do not compose are refused** |

So the lead's framing, per-operator work with no new mechanism, needs **two small composite
changes** in `contract.py` and `pump_composite.py`:
1. D150 §5.1's fallback: a current read with no changer reads the declared value.
2. A stage-aware order rule (§5).

The read-site table (§3) adds a third, a contract refinement: one field read in two modes in one
operator, which `_check_scopes` forbids today.

### 2.5 The furrow world, beyond the minimal cycle

This is the judged division consumers' world, not FR-11's: `tests/partition_fixtures.cleft_divided`
(an onset furrow into a cleft, the cleft a lumen), with water added.
- **With its lumen:** "two providers of the view field extracellular_volume". Water and
  `restricted_cleft_lumen@2` both provide the cleft's volume, and lifting a fixed read cannot
  remove that.
- **Without its lumen (water owns the cleft):** after the lift, `scheduled_membrane_insertion@2`
  refuses with "An onset node's volume must be its declared anchor". Water does not declare
  `ONSET_ANCHORED_VIEWS`.

The bath schedule's isosmotic rule beside water (PUMP_COMPOSITE.md's matrix) stays as it is.

### 2.6 The closed list

**Scope of the closure.** It is closed for the minimal cycle's world (no onset, one held bath,
IMEX) with neutral production. The furrow world adds gap 7, and the ions' share is item 8.

| # | Gap | Found by | Kind |
| --- | --- | --- | --- |
| 1a | Production reads the current volume (turnover: its work booking only) | L0 | Real (§3) |
| 1b | The partition takes the daughters' volumes from the current volume beside water | L0, L4 | Real. It writes water's state, books water's free energy, and needs the anchor rule on water's extensive parameters and an exact split (§7) |
| 2 | Water reads the current area | L0 | Real: conductance, in-step bound and step-check bound |
| 3 | Turnover reads the current masks | L0, L4 | Real for `active` and `outside_active`, nominal for `membrane_active`. Hidden behind it: the occupant rule for the partition's carriers and D150 §5.3's living-interval rule |
| 4 | Pumps on a dividing cell | L1, L5 | Ownership: pump padding, retirement, daughters' pumps, capacity as state, kinds beside closers (§13) |
| 5 | **New:** water reads the masks undeclared | L3, L4 | Real and silent |
| 6 | **New:** the composite's rules for current reads (the fallback, the stage-aware order) and per-stage modes | Second pass | Composite and contract |
| 7 | **New, the furrow world:** (7a) water beside a lumen on one node; (7b) an onset node's volume under water | §2.5 | 7b follows from gap 5: with current masks a closed node's volume keeps its anchor, so water can declare it (M2, §14). 7a is new physics: water through faces, for the Xenopus-with-water consumer (§14) |
| 8 | The ions' share of growth: turnover refuses charged species | Third pass | **By design** (charge conservation), not a composition gap. Growth's ions come through transport. The K-anion symport adds no declared refusal beside the cycle, but its route mask reads the declared `membrane_active` (`k_anion_symport.symport_rates`). On a dividing cell's patch it would keep cycling, as the pump does: gap 4's class |

## 3. Each refusal, read site by read site

One field can be read in two modes by one operator. Rates need the current mask. Existence checks
("zero where no owner") need the declared one: switch those to the current mask and a retired
parent's history refuses every step after its division. So the unit of this table is the read
site.

| Refusal | Read site | What assumes the field constant | Real or cautious | Under A |
| --- | --- | --- | --- | --- |
| Water: `membrane_area` | `bind` → `conductance_pL_per_Pa_s` = 1e15 A₀ Lp, used by `edge_exchange` | The flow law Q = G a Δψ at the declared area | Real | `current` at split: G = G_bound · A/A₀, exactly G_bound when A = A₀ (no new layout field) |
| | `water_rate` (the in-step relaxation bound) | The same G | Real | The same current G |
| | `WaterStepChecks.water_rate` (the host bound) | The declared state's G | Real | The largest area over the schedule, from the writers' `inner_check_spec` chain (R5) |
| | Ledgers, heat, free energy | None: flows are booked as moved volumes | — | Unchanged |
| Turnover: `volume` | `_node_update`'s work and magnitude, `species_chemical_free_energy_pJ` at `p.volume` | The free energy of the move at the declared volume | Real (booking only) | `current` at split. The probe checked it on the host: the booking at the current volume equals @3's term at V₀ plus the change of water's node free energy, to ≤ 3e-17 pJ. Without it, 4.8e-7 pJ is missed per 0.01 fmol |
| | The exact update n′ = n e^(−kh) + P g | None: the rates are amounts per time | — | Unchanged |
| Turnover: `extracellular_volume` | Outside clearance work at finite nodes | The same booking | Real only where a clearance route sits at a finite node. There is none in the cycle | `current`; or door S narrowing to its route nodes |
| Turnover: `active` | `turnover_half_step`'s `touched` mask | Rates on closed cells: pending daughters and the retired parent | Real | `current` at split, plus the living-interval rule at the definition |
| | `turnover_domain_valid`: zero where no owner, positivity | Slot existence | Reference | `reference` (as today) |
| | `species_common.occupants`, `route_tables` | Occupants from replacement@1 only. The partition's carriers (c1, c2) are unknown, and d1's route is a founder from t = 0 | Real (definition) | The occupant rule extended through the contract's `living_intervals` (D150 §5.2: "Daughters of an S5 partition are new carriers with their own declared rates") |
| Turnover: `outside_active` | `finite = p.outside_active & ~p.reservoir` for outside clearance | Rates on closed onset nodes | Real only at onset nodes with a route | `current` at split; `reference` in the domain |
| Turnover: `membrane_active` | None: it is on the shared `species_common.CONFLICTS_VIEW` list | — | **Cautious default** (the composition matrix tags it nominal) | Dropped from turnover's declaration |
| Partition: `volume` | Daughters' volumes are declared anchors, and the event writes no volume increment | The parent's volume at division equals its declared anchor | Real | `current` at event: an exact split written into water's increments (§7) |
| | `event_map`'s free energy, `chemical_free_energy_pJ` on V₀ | No dilution or elastic term | Real (booking) | Plus the change of the volume owner's declared node free energy |
| | `check_structure`'s volume anchors | Anchors as data | Reference | Kept, and extended to water's extensive compartment parameters: reference, minimum and maximum volumes, impermeant amount |
| **Water: masks, undeclared** | `bind` → `water_active`, `water_edge_active` (rates, `finite_nodes`) | Flows on closed patches and nodes | **Real, silent** | `current` at split |
| | `water_domain_valid`, `water_ledgers`, `water_control_valid` | Slot existence | Reference | `reference` (as today) |
| | `observe` (concentrations) | Columns at closed cells | Cosmetic | `current` at observe |
| **@3's pump: gated by `pump_present`** | `surface_pump_v3.readouts`; `role_inputs` keeps "physically present pumps" in their domain | A pump on a closed patch | Real (§13) | Gap 4 |

**Where one field is read in two modes** (current at rates, reference at existence):
- turnover's `active` and `outside_active`;
- water's three masks.

So A needs **per-stage read modes**: `SCOPED_READS[field]` may hold one `Read` per stage, for
example `current` at `split` and `reference` at `end`. `_check_scopes` refuses that today ("a
reference read of {field} is not also read, held as declared or provided").

**An alternative for turnover's masks: D150 §5.3's living-interval refusal alone.**
- A positive rate outside a slot's living interval is refused at the definition, from the
  partition's and insertion@2's schedules through the contract.
- No program changes: rates are zero on closed slots by schedule, so the declared mask read is
  harmless.
- It fails for triggered lifecycles, whose births are unknown at the definition (D176's lifecycle
  M2).
- **Recommended:** adopt the refusal now as cheap hygiene, *and* the current mask at the rate
  sites, which M2 needs.
- Water cannot rely on the refusal: its flows are driven by state, not by schedules.

## 4. The central option

### 4.1 (A) One general rule

An operator declares, per field and stage, how it reads: `current` (the merged view at its stage),
`fixed` (the declared value taken as physical) or `reference` (the declared value as data, such
as an anchor or slot existence). Its law ID stays the same.

The composite resolves each read when the model is built:
- **current** if some operator of the composition changes the field. That means a provider, a
  closer, or a writer of a provider's accepted state, such as insertion@2 writing membrane state's
  area;
- **otherwise the declared value**, with the part's call unchanged.

**Why the law IDs stay (D147, D148).** D147 makes an ID promise its semantics. D148 admits a change
under an unchanged ID only if four things hold:
- physical fields stay bitwise in every qualified world and program;
- verdicts are unchanged;
- ledger accumulators move only at rounding;
- the crossrev baseline is renewed at the landing.

A meets all four by construction. Every world that does not compose keeps its program, so its
records do not move at all, and the crossrev renewal is a no-op. The newly admitted compositions
are new definitions (D143), refused today. In them each law computes its stated semantics:
- water's flow "Q = 1e15 A Lp a (ψ_cell − ψ_outside)" with the patch's area;
- turnover's work, "the exact free-energy change of the touched node".

If the lead reads a current read as a change of a law's semantics, D147 sends it to a new ID,
which is option B. That is the ruling this note asks for.

**What A needs, all general and none per pairing:**

| # | Refinement | Where | Why |
| --- | --- | --- | --- |
| C1 | **The fallback.** A current read with no changer reads the declared value. Static: no `view=` is passed | `pump_composite.structure_errors`, `Composition.view_readers` | §2.4's third row. D150 §5.1 designed it |
| C2 | **The stage-aware order rule.** A reader sees every change made at an earlier stage of the step whatever the declared order. Same-stage pairs keep door S's rule 3, and a writer of a provider's state counts as a changer at its stage | `structure_errors` (the "reads before a closer" and "no earlier operator provides it" rules) | §2.4's circular order (§5) |
| C3 | **Per-stage read modes** | `contract._check_scopes` | §3's two-mode fields |
| C4 | **Scoped views.** A current reader receives its read fields only, merged to its stage, without `refresh_field` or the padding of unread fields | `pump_composite_adapter` | Fast (§11) |
| C5 | **Declared conditional bookings.** An operator's booking fields, entity writes and ledger terms exist only under a declared static condition of the composition's structure. There are two kinds: a read field has a changer (the partition's volume bookings beside water), or the inner structure declares a law (the partition's pump record where `structure.pump_laws` is non-empty) | `contract.py`, the composite's types and field map | §4.4: the partition over water, and gap 4's record |
| C6 | **An owner's declared free-energy term.** Writers book its change through the contract, never by importing the owner | `contract.py`; water's `node_free_energy_pJ`, already written as "its free-energy owner declaration" | Extendable: the partition must not import water (the J2 bright line's spirit) |

**Per operator** (the operators owner's files): the read declarations and read sites of §3, each
with its planted control. Gap 1b adds the exact split (§7) and the anchor rule on water's
compartment parameters.

### 4.2 (B) A new `@2` per pairing

This follows replacement@2 (over water), lumen@2 and insertion@2. For this cycle it means:
- `ideal_osmosis_linear_compliance_water@2` (current area and masks);
- `scheduled_species_turnover@2` (current volume and masks, with the occupant rule);
- `isopotential_partition@2` (over water);
- and a pump-carrying partition or a membrane state for gap 4.

**B does not avoid C2.** Water@2's mask read must follow the partition, and the partition must
follow water. It does avoid C1, because each @2 `REQUIRES` its provider, and C5, because each @2
owns its fields at all times.

### 4.3 Costs: qualification is the driver

| | A | B |
| --- | --- | --- |
| Existing worlds | Programs identical (§9), so every existing qualification stands verbatim: water's heredity arm, D150's judged scope, S5's protocol, insertion's S2/S3 | The @1 laws stay frozen beside the @2s. Each @2 is unqualified on all its worlds, not just the composed ones |
| Composed worlds | Numerical qualification (references and planted controls, a PROPOSED protocol). Judged status only from a consumer's registered protocol (D143) | The same, per @2 |
| New laws | None | Three or four, each with its own crossrev worlds, composition-matrix rows and columns, "two versions of one law" refusals, docs, summaries and batch signatures |
| Later pairings | A new provider or closer composes by declaration | Each new provider or closer may force another `@N` of every reader: a pairing table by another name |
| Precedent cost | — | Replacement@2 added about 1.5 ms per step on the 127-cell sheet, and its compile took 44 s against water's 28 s (PUMP_COMPOSITE_V2_DESIGN.md, B.13). Its qualification on the heredity sheet still waits for its assay (CURRENT_PLAN) |
| Effort, gaps 1–3, 5, 6 (§14) | 9.5–12.5 agent-days, plus references 3–4 in parallel | About 12–18, a rough bound (**S**), plus the same per later pairing. The derivation follows this table |

**B's rough bound, derived (S):**
- **Code:** three new laws with their scaffolding (parse, `to_dict`, summary, batch signature,
  matrix rows, "two versions" refusals). Water@2 takes 2–3 days, turnover@2 2–3 and partition@2
  3–4, so 7–10 in all.
- **Qualification:** 1–2 days per law on its own worlds, so 3–6.
- **The composite:** C2 and C4, which B still wants, take 1.5–2. B skips C1, C3, C5 and C6: each
  @2 `REQUIRES` its provider, hard-codes its read sites, owns its fields and may import its partner.
- **In all:** about 12–18, against A's 9.5–12.5. A is cheaper by about 2–5.5 agent-days on this
  lane. The larger difference is B's qualification debt, which sits on every world of each new
  law.

### 4.4 Where an `@2` would be justified, and why A does not need one

The test is whether composing needs new owned state, entity writes or ledger terms. Those are
class-level, so adding them under the same law ID changes every existing world of that operator.

| Gap | New state, writes or ledger terms? | A or @2 |
| --- | --- | --- |
| 2, 5 (water's area and masks) | None: G scales from the bound value, masks come from the view | A |
| 1a (turnover's volume) | None: the same expression at another volume (the identity of §3) | A |
| 3 (turnover's masks) | None: the occupant and living-interval rules are definition-time | A |
| 1b (the partition over water) | **Yes:** a moved-volume accumulator, an entity write onto water's `volume_increment_pL`, water's ledger terms, water's free-energy change | **The accounting genuinely differs.** B is defensible here. A keeps one law through C5, with bookings that exist only where `volume` has a changer, plus C6 |
| 4 (pumps) | **Yes:** the retirement record of the pump's history | The same: C5, keyed on a pump law declared in the inner structure (`structure.pump_laws`, built from the definition's patches). Every division world in crossrev is built pump-free (`tests/partition_fixtures` sets each patch's pump to None), so their programs stay identical |

**Recommendation: no `@2` in this lane.** C5 is the single general rule that lets the partition's
volume bookings exist only beside a volume owner, and its pump record only where a pump law is
declared. Without C5, the partition over water is the one `@2` to accept,
`isopotential_partition@2`, as replacement@2 was, and gap 4 would add another. That is the lead's
call.

**One general split rule, designed once.** The partition writes water's per-cell state through
water's declared interfaces (`ACCEPTS_WRITES`, C6) and never by name. So any owner that declares
them divides without an edit to the partition. The site-occupancy design's §5.1 door asks for
exactly this, "the liveness rule designed once for D150's, D152's and the coupling operator's
state". Sites, D152's pools and the pump's units (§13) are its next consumers.

### 4.5 Recommendation

**Option A**, with C1–C6, in the order of §14.
- It is clean: one rule, no new law IDs.
- It is extendable: declarations only (§12).
- It is fast: build-time resolution, identical programs outside compositions, and scoped views
  (§11).
- It saves roughly 2–5.5 agent-days against B on this lane alone (§4.3). B's cost and its
  qualification debt recur with every later pairing.

## 5. The full cycle's read/provide graph, per stage

The declared order is membrane state (MS), insertion@2 (INS), water (W), turnover (T), partition
(PT). @3 is the inner step.

| Stage (step order) | Reader | Reads, current | Changed by (its stage) | Seen as |
| --- | --- | --- | --- | --- |
| Event | PT | `volume` | W (split) | Water's state at the previous step's end: the state at the event's time, not a lag |
| | PT | masks, `membrane_capacitance` | INS's closures (event, earlier in order), MS (state) | This step's |
| Split, first halves | INS | `membrane_capacitance`, `membrane_active` | MS; PT and INS closures (event) | After this step's events |
| | W | `membrane_area` | MS, written by INS (split, earlier) and by PT (event) | After INS's first half |
| | W | masks | PT, INS (event) | After this step's events |
| | T | `volume` | W (split, earlier) | After W's first half |
| | T | masks | PT, INS (event) | After this step's events |
| Inner | @3 | the full view | everything | After events and first halves |
| Split, second halves (reverse) | T, then W, then INS | As above | | The palindrome: T before W's second half, W before INS's |
| End, observe | domain, observation | the full view | everything | The step's end, then the accepted row |

**State couplings** are not view edges: W reads amounts that T writes, and T reads the volume W
provides. They run as sequential sub-flows, which is the splitting itself.

**The graph is acyclic.** Key every edge by (stage, declared position). Every view edge then runs
from a smaller key to a larger one. A same-stage edge points forward in declared order, and C2 lets
an edge cross stages (event → split) whatever the declared order. Without C2 the same cycle is
refused, because PT must precede the mask readers and follow water.

**No lag is introduced.** A same-stage reader placed before its changer stays refused, as in door S
rule 3, rather than given lagged semantics.

**C2 needs each change's true stage.** The contract's default gives a closer with a split part the
stage `split` (`Operator.view_change`). Insertion@2's closures change only at its event
(`insertion_opened`), so it declares `VIEW_CHANGES = {mask: Change("and", "event")}` for both of
its masks. That is a declaration only; no program changes.

## 6. What "current" means inside a step, and the convergence order

**Definition.** A current read at stage s returns the merged view formed from the state current at
s. That is door S §4's reader-stage semantics (D169, D174), with C2 for cross-stage order:
- events see earlier events, and split changers as of the previous step's end;
- a first-half reader sees earlier split changers after their first half;
- the inner step sees everything after events and first halves;
- second halves see the inner step's result, and the later operators' second halves (the
  palindrome).

**Order (S).** The step is P₁(h)…Pₘ(h) I(dt) Pₘ(h)…P₁(h) E with h = dt/2. With stage-current reads,
each Pᵢ is an exact or second-order flow of its own variables, its reads frozen for the sub-step,
on the full state:
- turnover's half-step is exact;
- insertion's is exact;
- water's Heun step is second order;
- the inner ARS(2,2,2) step is second order.

The palindromic composition is therefore **second order for the coupled system**. The coupling
enters only through commutators, O(dt³) per step. The events are exact jumps at grid times.

**Against the alternatives:**
- a step-start (lagged) read would make the coupling first order;
- today's fixed read cuts the coupling, an O(1) modelling error that no dt reduces.

**Test:** self-convergence (dt, dt/2, dt/4: error ratio about 4) on water plus insertion and water
plus turnover, against §10's references. RK4 is refused for these worlds (§2.2).

## 7. Exactness at the division: daughters' volumes sum to the parent's, bit for bit

Let V_P = fl(A_P + d_P) be the parent's current volume (water's view), with A its declared anchor
and d its increment. The daughters' anchors follow the anchor rule: A₁ = fl(f A_P),
A₂ = A_P − A₁, exact by Sterbenz for f ≥ ½. There are two ways to split:

| | (i) Split the increments (S5 §5's sketch: "each daughter's f dv_P") | (ii) Split the current volume (recommended) |
| --- | --- | --- |
| Rule | d₁ = fl(f d_P), d₂ = d_P − d₁ | V₁ = fl(f V_P), V₂ = V_P − V₁ (Sterbenz), then d_k = V_k − A_k (Sterbenz) |
| Daughters' views sum to V_P | 83.5% of 400,000 random worlds; worst 1 ulp off | **100%**, and each daughter's view reproduces V_k exactly |
| Increments sum to d_P | 100% | Residual ≤ ½ ulp(V_P): the parent's own view rounding, booked |
| f = ½ | Both exact | Views exact; the residual is the parent's rounding |

In the probe the parent's view A + d rounds in 82.6% of the worlds, so the difference between (i)
and (ii) is not an edge case.

**(ii) meets the requirement.** The partition then books what it writes:
- +d₁ and +d₂ at the daughters, and −d_P at the parent, in its conditional accumulator (C5);
- water's `water_local` and `water_total` close exactly on the written increments, through
  `external_ledger_terms` as replacement@2's do;
- the partition's own volume ledger (Σ moved = the residual) is checked within its event rounding,
  as `partition_material` is.

**Device and definition guards:**
- **The definition** refuses a dividing parent or daughter whose water bounds extend beyond
  [½, 2] × its anchor, outside Sterbenz's range. The heredity arm declares exactly 0.5 and 2.0,
  with strict inequality in water's domain.
- **The event** refuses the step if fl(A_k + d_k) ≠ V_k for either daughter. That is the guard of
  record, and a refused event leaves the full prior state.
- **Fused multiply-add.** XLA on this CPU gave NumPy's bits with and without a barrier. GPUs
  contract multiply-add by default, so fl(f V_P) is formed behind `optimization_barrier`, as A7's
  sums are (D182).
- **Device test:** the daughters' views sum bitwise on CPU and the L4 across planted worlds with
  f ∈ [½, 1).

Amounts keep today's increment split (i). Their ledgers are checked at rounding, and the lead's
requirement names volume.

## 8. A slot that closes and reopens: what a reader sees

**Today:** closed slots are padding to @3 (`adapter.close`). Operators that read declared layouts
act on them, which is §2.3's hazard. It is also the hazard of the drift in §7.4 (o): the padding
gates evolve while closed.

**The rule (S), designed once for every current reader:**
1. **While closed, a reader neither treats the slot as live nor writes it.** Its rates and bookings
   there are selected exact zeros, never computed and then zeroed (D136).
2. **Its per-slot state there is frozen.** Increments and histories keep their values from the
   closure, which is why existence checks read `reference` (§3).
3. **Opening is the opener's event.** The opener writes the content it opens:
   - the partition: amounts, volume through water (§7), area, gates;
   - insertion@2: anchors, and its gates under (o) option 1.

   Readers see the opened slot from the next stage of that step (C2). Split readers see it in the
   same step. Event readers see it in the same step if later in the declared order, or at the next
   step if earlier.
4. **Reopening.** No operator today closes a slot and opens it again: pending daughters open once,
   parents retire for good, and onset patches open once. A reader's frozen state would resume
   from its closure, which is (o) option 2's model. Until a reader declares what its state does at
   reopening (keep, reset to declared, or set by the opener), the composite refuses a closer that
   can reopen a slot beside it, failing closed.

## 9. Invariance: worlds that do not compose

**The requirements:**
- the eight crossrev sets stay identical;
- G1 stays at 113 of 113;
- for every world without a changer of a read field, the program is today's: the same Python path,
  with no `view=` and no conditional fields.

**Why result identity is not enough.** In §7.4 (n), an absent routing door's `valid & True` alone
changed FR-4's jaxpr text, and only a pair check found it. So:
- **No ops for absent pairings.** No `& True`, no `where(m, x, x)`, no `* 1.0`. The declared path is
  the existing code. Water's conductance scaling exists only where `membrane_area` has a changer,
  so A/A₀ = 1 is never traced.
- **The evidence** at each milestone (§14), from a frozen snapshot:
  - crossrev's eight sets (programs and bindings);
  - G1 113/113 (records bitwise);
  - a jaxpr-text pair check, against 3c10b833, of every operator this lane touches, alone and
    with its existing partners: water alone and with replacement@2; turnover alone and with
    replacement@1; S5's division worlds; insertion@2's furrow worlds;
  - tiers 1 and 2.
- **Field maps, manifests and batch signatures:** unchanged where nothing composes. C5's fields
  enter only composed worlds' types.

## 10. Per gap: reference, planted control, judged consumer

| Gap | Independent reference (NumPy) | Planted control | Judged consumer |
| --- | --- | --- | --- |
| 2 | One cell, linear compliance, a prescribed A(t) = A₀ + r t: dV/dt from G(t) = 1e15 A(t) Lp at tight tolerance; the order-2 self-convergence (§6) | The fixed-read twin (water at A₀) differs from the reference beyond the declared budget | **None registered.** Candidates: an epithelial monolayer (growth with water), the minimal cell (no organism definition yet, D173) |
| 5 | Exact: a pending daughter's volume stays at its anchor bitwise until birth, and a retired parent's increment stays at its moved value | Today's water: −0.0014 pL/s at a pending daughter (L4) | As gap 1b |
| 1a | ΔG of each move from the closed form at the current volume; the energy ledger in a species-plus-water world | The declared-volume booking misses water's term (4.8e-7 pJ per 0.01 fmol at the probe's state) | **None registered.** D150's calibration world is a static tissue |
| 3 | Exact zero increments on closed slots; the production and clearance closed form from birth; the occupant table from the partition's lineage | A rate before birth is refused at the definition, with the reason. Today it is admitted and caught only by the run-time ledger (−2.0e-12 fmol) | **None registered** |
| 1b | §7's exact split. Water's node free energy before and after, zero for f = ½ with proportional content, nonzero with mismatch carriers. The anchor rule on water's compartment parameters | (i)'s split must miss bit-exactness in some worlds, which proves the test can fail. Today's partition loses 2.4e-7 pL with strong production | **None registered.** Likeliest: D176's lifecycle M2 (a size trigger reads the current volume), then C. elegans' volume asymmetry |
| 4 | Exact: the retired patch's pump is idle; Σ daughters' capacities = the parent's; pump history adds back in `adjust_inner` | Today: the retired patch cycles at 1.41e-5 fmol/s | **None registered.** Xenopus: "no electrogenic pump detected at first cleavage" (CELL_DIVISION_PLAN) |
| 6 | The contract tests of door S §7 (T1–T8), extended to C1–C4 | A same-stage reader before its changer is still refused. A non-composing world gives a bitwise-identical program | Not applicable: composite rules |

**The finding for the lead.** FR-11's loop is an illustration and cannot qualify these. The
division plan's judged runs need none of them. Numerical qualification can proceed under D144, and
each gap's judged status waits for one of the named candidates to register a protocol.

## 11. Fast: cost, measurement, host work

**Static count of view formations per step** (the cycle, no division that step; **S**):

| | Today's parts | A with full views | A with scoped views (C4) |
| --- | --- | --- | --- |
| Full formations, with `close` and `refresh_field` | 4: insertion@2's two half-steps (`BOOKS_AT_VIEW` with field inputs), the inner step, the end domain | 8: water's and turnover's four half-steps join them | 4 |
| Scoped formations (a few adds and boolean gathers over the slots) | 0 | 0 | 4 |

A division step adds the partition's two formations inside `lax.cond`.

**Estimates (to be measured, not promised):**

| | CPU, ≤ 64 field nodes | L4 GPU |
| --- | --- | --- |
| Full views, step time | About +0–10% (**S**). The measured cost of the refresh in every formation was +7.5% at 2 nodes and within noise at 14 (PUMP_COMPOSITE_V2_DESIGN.md §R3), and doubling the formations repeats it | About +5–20% at small, latency-bound worlds |
| Full views, compile time | +10–30%, from four more inlined refresh and Cholesky subgraphs | The same |
| Scoped views, step time | Under 1% | Under 2%: elementwise work that XLA fuses |
| Scoped views, compile time | +1–5% | +1–5% |

**Recommendation:** scoped views. A reader of `membrane_area` or masks never needs the capacitor
refresh.

**The measurement:**
- the composed cycle world against its planted fixed-read twin (the same world, reads forced to
  the declared layout), so the difference is the composition alone;
- on CPU, one thread per core, pinned in `cells.slice`, and on the L4;
- batched and unbatched;
- with `scripts/profile_dispatch.py`'s `split` and `phases` modes;
- reporting step ms, compile time as first call minus steady call, and memory;
- non-composing worlds measured once, to confirm the identical programs cost the same.

**Per-step host work: none added.**
- Modes, admission, slot sets, the occupant and living-interval tables and water's worst-case area
  bound are all resolved at build or definition, and cached as `bind_check_steps` does.
- The exact split and its check run on the device, inside the partition's event.
- To avoid: host callbacks to choose a mode, Python branches on traced values, and per-step
  rebinding.

## 12. Extendable: the planted third operator

These are acceptance tests that land with C1–C4. Every planted operator is a test double; none is
registered.

| Test | What is planted | Pass |
| --- | --- | --- |
| E1 | `stub_volume_reader@1`: declares only `SCOPED_READS = {"volume": Read("current", "split")}` and records what it reads | Joins the cycle with no edit to water, the partition or any table. It sees water's merged volume bitwise at its stage. Without water it reads the declared volume, and its program has no view input |
| E2 | `stub_closer@1`: closes `active` at one slot by an event | Water and turnover idle on that slot with no edits. A reader before it in declared order is admitted by C2 |
| E3 | A second volume changer with a scoped `add` on a disjoint slot, then on water's slot | Merged on the disjoint slot. Refused on the shared one, naming the slot (door S rules 1–2) |
| E4 | A per-slot owner that declares its split through `ACCEPTS_WRITES` and C6 | The partition divides it with no edit to the partition. Undeclared, it is refused at build |

## 13. Gap 4 on its own: pumps on a dividing cell

This is about ownership and partition, not a read.

### 13.1 Facts (probe L5)

- **The refusals.** The parser refuses the pump ("Pumps on a dividing cell are later work (pump
  capacity as state)"), and so does `add_division`. Behind the parser, with the pump admitted,
  every other definition check passes.
- **The retired patch keeps pumping.** After the division the parent's patch is closed at the view,
  but `pump_present` is true and the view's `pump_capacity` is 0.0326 fmol/s.
  - The inner pump keeps cycling at 1.41e-5 fmol/s.
  - The rate is unchanged to the bit when the closed cell's amounts are raised by a quarter of
    their anchors (third pass). That is consistent with @3's readouts forming a 1 mM placeholder
    concentration at inactive cells (`where(p.active, ci / p.volume, 1.0)` in
    `surface_pump_v3.readouts`). `role_inputs` keeps "physically present pumps" in their real
    domain. The placeholder itself is not exposed by the readouts, so this is inferred from the
    code and the invariance.
  - It writes −4.24e-5 fmol/s of Na and +2.82e-5 fmol/s of K at the closed cell (3:2 per cycle),
    and books 9.6e-4 pJ/s each of heat and metabolic work.
  - The readouts and the domain at the view are valid at the state right after the event. Whether
    a later step's checks would refuse the closed cell's drift was not run, because that needs a
    step.
- **The pump's history is not retired.** The partition's record covers membrane, junction and
  channel history, not `pump_cycles`, `pump_dissipated_energy_pJ`, metabolic work or the calcium
  pump's fields.
- **A caveat:** the daughters have no pump in the probe's world only because `add_division` refuses
  one. The fixture added the pump after the split.

### 13.2 Ownership and partition

- **Today.** Pump capacity is declared layout per patch: `pump_capacity` (a view field that
  replacement@1 provides for newcomers) and `pump_present`. It is constant for a slot's life.
- **Three levels:**
  - **(a) Static pumps.** The parent's capacity is constant over its life, so daughters can declare
    pumps with anchor-rule capacities (fl(a C), C − fl(a C)) and the parent's pump domain (law,
    stoichiometry, constants, metabolism). No state is needed. It needs three things:
    - the closer idles a closed patch's pump;
    - the partition retires the pump's history and `adjust_inner` adds it back;
    - the helper and parser write and check the daughters' pumps.
  - **(b) Capacity as state.** Capacity changes within a life whenever pumps grow with the
    membrane (insertion at a declared pump density), are synthesised, or come with a template.
    - An owner holds pump units per patch, as membrane state holds a population's units, and
      provides `pump_capacity`.
    - Its writers: insertion adds units, the partition splits them by area fraction (the split rule
      of §4.4), replacement replaces them.
    - Plus its entity ledger, and the R5 bound at the largest capacity.
    - FR-11's cycle needs this, since the daughters must meet the mother at t = 0.
  - **(c) Pumps as a kind** (`cells.transporter@1`: FR-4's proton pump, and the cardiac note's Na/K
    cycle and exchanger).
    - `structure_errors` refuses any closer or retirer beside declared kinds ("no closer resets a
      kind's per-slot fields").
    - So kinds need a per-slot close, open and split declaration at the kind interface (§7.4 (k)).
      That is the core's.
- **Finite fuel (F2, D176).**
  - Maintained fuel (@3's `maintained_chemical_reservoirs@1`) is intensive: daughters copy it.
  - Held inventory rows split as amounts by the anchor rule, so their concentrations are kept.
  - Finite fuel rows (refused this round) will split like any species, and each daughter's pump then
    draws on its own pool.
  - So fuel adds no partition logic. The kind route still waits for (c).

### 13.3 Options and estimate (agent-days)

| Level | Work | Owner | Estimate |
| --- | --- | --- | --- |
| (a) | Idle pumps at closed patches (§13.4, Q1); the partition's pump record under C5 and its `adjust_inner`; daughters' pumps by the anchor rule in `add_division` and `check_structure`; references | Core (Q1), operators | 2.5–3, plus 1 for references in parallel |
| (b) | Pump units as state; insertion's pump densities; the split; the ledger; R5 | Operators, with the core on Q3 | 2–3 |
| (c) | Kinds' per-slot close, open and split | Core | 2–4 |

**Recommendation:** (a) when a consumer needs a dividing cell with pumps; (b) with the first growth
consumer; (c) with FR-4's or the cardiac set's first dividing world. None has a registered consumer
(§10).

### 13.4 Questions for the core owner (for the lead to route)

1. **Idle pumps at closed patches.** Should @3's pump rates be gated by the view's
   `membrane_active` (a kernel change, static on closer worlds only), or should `adapter.close`
   pad `pump_capacity` and `calcium_pump_capacity` at closed patches? The second makes them padded
   fields, which refuses a provider of them beside a closer (replacement@1 provides `pump_capacity`
   and is already refused beside the partition).
2. **The pump's history at retirement.** Which @3 fields does the partition's record take
   (`pump_cycles`, `pump_dissipated_energy_pJ`, metabolic work, the calcium pump's), and do the
   inner ledgers read them back through `adjust_inner` unchanged?
3. **One pump representation for division.** Will @3's built-in `nak_atp_mass_action_positive@1`
   move into `cells.transporter@1` (D167's move; the cardiac note's `sodium_potassium_pump_cycle@1`)?
   If so, capacity-as-state belongs to the kind, not to membrane state.
4. **Kinds beside closers.** Is a per-slot hook at the kind interface the core's preferred seam: on
   close (idle), on retire (into the closer's record), on split (extensive by fraction, intensive
   copied)? It would replace today's refusal.
5. **Transporter populations.** The cardiac note asks for several roles per cycle, no fuel, and two
   populations on one membrane facing two pools. Does a transporter population become an entity
   with units, like a channel population, so the partition's population maps cover it?
6. **Held fuel at division.** Confirm that a held row at a dividing cell splits its anchors by the
   rule, and that `transporter_fuel_supplied_fmol` retires with the parent's patch.
7. **R5 with growing capacity.** Is the explicit-rate bound to be taken at the schedule's largest
   capacity, through `inner_check_spec`, as insertion's area is?

## 14. Milestones, effort and order

Agent-days, after this note's options are ruled.

| Milestone | Engine models | Work | Estimate |
| --- | --- | --- | --- |
| M1: the composite rules | `resolved_pump_composite@1` over @3 (contract, composite, adapter); every operator unchanged | C1–C4 with door S's tests extended; E1–E3 (§12); the invariance evidence (§9) | 2.5–3.5 |
| M2: water's current reads | water beside membrane state, insertion@2 and the partition | Gaps 2 and 5: G scaling, current masks at rates and reference at existence, the R5 area bound, `ONSET_ANCHORED_VIEWS` for water's outside volume (closes 7b) | 2–2.5 |
| M3: turnover's current reads | turnover beside water, the partition and insertion@2 | Gaps 1a and 3: current volume and masks, the living-interval refusal, the occupant rule for the partition's carriers, dropping the nominal `membrane_active` | 2–2.5 |
| M4: the partition over water | the partition beside water | Gap 1b: C5 and C6, §7's exact split with its barrier and guards, the anchor rule on water's compartment parameters, the free-energy booking; E4 | 3–4 |
| References and planted controls | — | §10's NumPy references and convergence tests, by a fresh agent, in parallel with M2–M4 | 3–4 |
| M5: static pumps on a dividing cell | the partition with @3's pump | Gap 4 (a), after Q1 and Q2 | 2.5–3, plus 1 for references |
| M6: capacity as state; kinds beside closers | with the core owner | Gap 4 (b) and (c), with a consumer | 2–3; the core's 2–4 |
| Gap 7a: water and a lumen on one node | — | New physics (water through faces, or the lumen as the node's volume owner); a design item with the Xenopus-with-water consumer | Not estimated |

**Order:** M1 → M2 and M3 (disjoint files, in parallel) → M4 → M5. M6 waits for a consumer.

**Totals:**
- gaps 1–3, 5 and 6: 9.5–12.5 agent-days plus 3–4 for references, about 8–10 working days with
  the references in parallel;
- with gap 4 (a): plus 3.5–4.

Each milestone lands behind tiers 1 and 2 with crossrev and G1. Integration grants no acceptance.

## 15. Evidence and files

Folder: `/mnt/workspaces/Cells/composition-design-20261116/`.
- `snapshot-3c10b833/`: the execution snapshot (`validation/source_snapshot.freeze`, clean, 6147
  files).
- `composition_closure_probe.py`, `closure-probe.json`, `closure-probe.log`: L0–L5.
- `composition_closure_probe_2.py`, `closure-probe-2.json`, `closure-probe-2.log`: current reads
  declared, the furrow world, the booking identity, the pump's drive.
- `composition_closure_probe_3.py`, `closure-probe-3.json`, `closure-probe-3.log`: ion production,
  the planted rate through every definition check, the RK4 rule raised by the engine, the retired
  pump's inputs, the symport beside the cycle.
- Every `"error"` entry in the three JSON files is a recorded engine refusal. No section failed.
- `water_mask_reachability.py`, `water-mask-reachability-7c8bfa47.json`: gap 5's reachability on
  main at 7c8bfa47 (§16.3).
- `volume_split_exactness.py`, `volume-split-exactness.log`: §7, NumPy and XLA on the CPU.

All ran on CPU 22 at nice 10, host only. **The probes exist only in this folder.** Whether they
land under `validation/replay/` beside FR-11's `cycle_probe.py` is the lead's call.

**Precedents read:**
- SECRETED_SPECIES_TRANSPORT_DESIGN.md §5.1–§5.5 and §9;
- SCOPED_COMPOSITION_DESIGN.md;
- ARCHITECTURE.md, "Scoped composition (door S)";
- INNER_MODEL_V4_DESIGN.md §7.4 (n) and (o) on core-next;
- CELL_DIVISION_PLAN.md;
- CELL_DIVISION_S5_DESIGN.md §3 and §5;
- PUMP_COMPOSITE.md's composition matrix;
- PUMP_COMPOSITE_V2_DESIGN.md §R3 and B.13;
- SITE_OCCUPANCY_DESIGN.md §5.1;
- CLOSED_COMPARTMENT_DESIGN.md §5.3;
- HUMAN_CARDIAC_LAWS_DESIGN.md on cardiac-laws;
- LOOPING_REPLAY_DESIGN.md §6 on run-view-d154;
- DECISIONS D142, D143, D144, D147, D148, D150, D169, D174, D176 and D185.

## 16. What option A changes in main's assertions, and gap 5 today

The lead's two checks, read on main at 7c8bfa47.

### 16.1 The refusals A would turn into admissions

**One registered protocol and four test files assert them:**

| Where | The assertion | Flipped by |
| --- | --- | --- |
| **D150's registered protocol** (`validation/tissue/secreted_species_protocol.json`). Its Q5, "The guards of record hold at the judged snapshot", runs `tests/unit/test_secreted_species.py`. Q5 was judged at f7f0592 (`/mnt/workspaces/Cells/secreted-species-v1-20261114-01/judged-f7f0592/q5/verdict.json`) | `test_version_1_refuses_volume_providers_area_providers_and_mask_providers`: turnover beside water, "reads volume as declared"; turnover beside insertion@1, "reads outside_active as declared". Its third case, exchange beside membrane state, stays refused | Gaps 1a and 3 |
| `tests/unit/test_membrane_state.py` | `test_operators_that_read_the_declared_area_refuse_the_membrane_state`: water beside membrane state, "reads membrane_area as declared". Replacement@1's half stays | Gap 2 |
| `tests/unit/test_pump_composite_contract.py` | `test_ownership_refusals_when_a_composition_is_built`: a current read with no provider, "reads the view volume; no earlier operator provides it" | C1 |
| `tests/unit/test_door_s.py` | `test_a_current_reader_follows_the_changers_of_its_slots`: "test_alone@1 … no earlier operator provides it"; and a split reader placed before an event-stage changer of its slot, "… before test_dose@1 changes it" | C1, then C2 |
| `tests/unit/test_composition_matrix.py`, with `docs/PUMP_COMPOSITE.md` and `validation/tissue/composition_matrix.py`'s tags | The matrix's refused cells and their tags. They are the only assertion of the partition's volume refusal beside water, and they also hold water's area refusal and turnover's volume and mask refusals | Gaps 1a, 1b, 2 and 3 |

**A's cost here.**
- Q5 is amended, or its test is split. The version-1 refusals stay in Q5's file for the static-tissue scope its verdict covers, and A's admissions are tested in a file outside Q5's list. The verdict judged at f7f0592 stands.
- Q5's scope line already limits any qualified statement to a static tissue.
- **Done for turnover by FR-65 (26 November 2026):** Q5's first two cases are amended in place and
  disclosed in the test (turnover beside water is admitted; a lumen at the node it clears stays
  refused by the shared volume rule, and insertion@1 at the node it clears by the anchor guard), and
  the admissions are tested in `tests/unit/test_species_turnover.py`, outside Q5's list.
- `test_membrane_state.py`, `test_pump_composite_contract.py` and `test_door_s.py` change their
  assertions to the admissions.
- `test_composition_matrix.py` passes again once the matrix is regenerated and the lifted tags are
  removed, in the same commit as each gap.

**Asserted nowhere on main:** the partition's pump refusal ("Pumps on a dividing cell are later
work") has no test. S5's registered protocol (`validation/division/s5_protocol.json`) states no
water or pump scope. M5's tests cover both what it lifts and what stays refused.

**These stay refused under A**, outside this lane:
- replacement over water or beside a closer;
- injection beside water;
- exchange, the reactions operator and the coupling operator.

That holds only if turnover gets its own declaration. Exchange and the coupling operator share
`species_common.CONFLICTS_VIEW`, so it must not be edited.

### 16.2 Gaps 2 and 5 land together

Water's area refusal is gap 5's only guard. Every operator that closes or provides a mask water
reads requires membrane state, and water refuses membrane state. Lifting gap 2 alone would admit
water beside insertion@2, with water flowing through closed onset patches before their onset. So M2
(§14) lands gaps 2 and 5 in one change, and no milestone lifts water's area read without its
current mask reads.

### 16.3 Water on closed slots is not reachable today

Gap 5 is latent, not an open finding on existing code.
- **The mask changers.** Only the partition (`active`), insertion@1 and insertion@2
  (`membrane_active`, `outside_active`) close or provide a mask water reads. Each is refused beside
  water in either order by rules that no reordering or added operator removes: all three need
  membrane state, and the partition also conflicts on volume.
- **What main admits.** Water's admitted partners are the K-anion symport, the bath schedule and
  replacement@2. That gives seven admitted water compositions, and none changes a mask.
  Replacement@2 restarts slots in place and closes nothing.

So in every admitted world water's bound masks are the view's masks.

**Evidence:** host-only enumeration on main's code:
- `water_mask_reachability.py`;
- `water-mask-reachability-7c8bfa47.json`.

Both are in `/mnt/workspaces/Cells/composition-design-20261116/`. The matrix's water row in
`docs/PUMP_COMPOSITE.md` at 7c8bfa47 agrees.

## 17. M1 as built (18 November 2026)

**The rules,** in `operators/contract.py`, `models/pump_composite.py` and
`models/pump_composite_adapter.py`:
- **One table of changes** (`pump_composite.view_changes`) feeds C1, C2 and the view readers. It
  lists every change of a view field, once per stage it is made at:
  - a provider's change, at its declared stage, and at the stages of the earlier changes of what it
    reads current, since its view takes the accumulated view. An undeclared change of an operator
    with an event map and a split part counts at both stages (insertion@2's closures open at its
    event, though `view_change` defaults them to `split`); a `VIEW_CHANGES` entry narrows it;
  - a closer's change of what `close()` changes for the masks it closes, the adapter's
    `CLOSURE_REACH`: the masks below them in the entity hierarchy and the padded fields of the
    slots closed. So a reader of `membrane_active` beside a closer of `active` alone receives the
    view, never the declared mask (gap 5's hazard), while a closer of cells reaches no face or
    outside anchor;
  - a writer of an owner's accepted state, as a change of everything the owner provides, at each
    stage its parts run at.
- **C1:** a current read of a field nothing changes is admitted and reads the declared value; its
  part receives no view. A current read of a name that is no view field is refused.
- **C2:** a change at another stage is seen whatever the declared order. A later change at the
  reader's own stage is refused, by the structure check, or per slot where both are scoped. The
  per-slot check covers a scoped provider's own declared stage only; a stage it inherits from what
  it reads is ordered at the structure check. A self pair is not a constraint, as door S's per-slot
  check already had it.
- **C3:** `SCOPED_READS[field]` may hold one Read per stage. A reference read may stand beside a
  current one at another stage. `contract.reads_of` gives every Read, and `Operator.scoped_read`
  refuses a field read at several stages. The contract's public names are unchanged.
- **A declared stage is one of the operator's parts':** a read or change at `event` needs the event
  map, at `split` the split part (a part-less owner may change at `split`, its default), and a read
  at `inner` the in-step process, or (R2, 19 November 2026) a control factor. A factor operator's
  current read at `inner` is its read at the control view. The control view is the state the inner
  step starts from, where its `control_factors`, `factor_valid` and `factor_record` are evaluated.
  The composite passes those hooks `view=`, a function of state giving C4's reader view of the read
  fields (`contract.factor_reads`). It does so only where such a read is declared, so no other
  call changes.
- **Fixed reads, tightened** (the lead's ruling on M1's hand-back): a fixed read is refused beside
  another operator's closer whose closure reaches the field, not only one that closes it by name
  (door S's rule 4). No sequence is newly refused or admitted; the composition matrix gains eleven
  tagged rows (four nominal), all in cells already refused, so no cell changes.
- **C4:** a door S reader's part receives `reader_view`: the full view's merge of every provider and
  closer, without the field refresh, holding only its read fields. An operator that books at the
  view keeps the full view.

**What changed for registered compositions** (`structure_errors` of main at f609dd7f against M1's,
over every sequence of one to four registered operators with their closures, 75,823 in all):
- none is newly refused, and none newly admitted;
- 9,302 sequences, all already refused as two versions of one law, gain an order message. Three are
  new rows of the composition matrix, tagged real: a lumen of one insertion version beside the other
  version. The matrix's cells are unchanged.
- No registered operator declares a current read in `SCOPED_READS`, so no part receives a view it
  did not receive before, and the per-slot check's new stage test meets no registered pair.

**Deferred:**
- E1's "joins the cycle" waits for M2–M4, and E2's "water and turnover idle on the closed slot" for
  M2 and M3.
- E3 waits for M2, since water's change of the volume is a replacement on every slot until it
  declares its slots.
- `registry/declarations.py` (the F owner's) calls `scoped_read`. A registered operator with reads
  at two stages, due at M2, needs it to call `reads_of`.
- `docs/SCOPED_COMPOSITION_DESIGN.md` §3 (rule 3 and the `VIEW_READS` rule) predates C1 and C2.

**Tests:** `tests/unit/test_composition_order.py` (new), with the flipped assertions of
`test_door_s.py` and `test_pump_composite_contract.py`, each beside a same-stage twin that is still
refused. Evidence: `/mnt/workspaces/Cells/core-pass-operators-20261118/m1/`.
