# FR-65: turnover beside a changing volume (design)

**Status: final, decided on 24 November 2026 (D375, and the lead's rulings on this revision, §8.2); nothing is built.**
The first version was proposed and decided that day. This revision, on branch `fr65-design` with main merged (the probes
ran at 95559271, whose source is unchanged since):
- records the user's choice (Q3 b) and the lead's rulings (Q1 b, Q2 a) in §8;
- designs the lumen case (§3.5) and lists the saved amounts and volumes (§4.2);
- corrects the first version (§8.3).

The build comes after the rename. FR-65 is D301's composition M3, and D150's planned version 1.1 for turnover
(SECRETED_SPECIES_TRANSPORT_DESIGN §5.1, §5.3 and §5.5).

**Engine models:** `resolved_pump_composite@1` over `resolved_pump_tissue@3`. `scheduled_species_turnover@1` sits
beside `ideal_osmosis_linear_compliance_water@1`, `isopotential_partition@1`, `scheduled_membrane_insertion@1` and
`@2`, `restricted_cleft_lumen@1` and `@2`, and `neutral_arrival_labels@1`. A1 adds `templated_polymerisation@1`, and in
the second step `species_regulated_availability@2`.

**S** marks our own reading or derivation. The probes ran on the host only: nothing was compiled or run (§9).

## In short

- **Who refuses today.** Turnover's fixed reads alone stand between it and water, the partition and insertion@2. The
  same holds for insertion@1, where turnover acts in cells only, and for the lumens, which need insertion (§1.1). The
  reads are the shared `species_common.CONFLICTS_VIEW`: both volumes and three masks. Lifted in process, each pair
  passes every definition check. Behind them:
  - the occupant rule knows only replacement@1's carriers, so a daughter's routes cannot be keyed by the partition's
    carriers;
  - **A1 in a swelling cell is refused by two operators:** turnover, and the coupling operator
    (`species_regulated_availability@2`), which reads c = n/V at the declared volume. We read D334's and D347's "A1" as
    this world;
  - water with replacement@2 and turnover would parse, so the shared volume rule must refuse it by name.
- **The recommendation is option A, as in FR-43 part 2B:** the same law ID, turnover's own read declarations, and C1's
  fallback.
  - The volumes are read current at the split. The masks are read current at the split and from the declared layout
    for existence. The outside anchors are a reference read, kept true by a guard that refuses insertion@1 where
    turnover clears at a node.
  - Water is the one volume changer admitted at a slot turnover reads. A lumen is admitted at a node turnover does not
    read (§3.5). Both follow one shared rule in `species_common`.
  - The occupant rule works through a contract hook, so the partition's daughters are carriers with their own rates
    (D150 §5.2).
- **Why it is cheap.** No state, layout, control or ledger term is added, and no lumen program changes.
  - Turnover's update n′ = n e^(−kh) + P g reads no volume, so its amounts stay exact. Only its work booking reads the
    volume.
  - At the view's volume that booking is the composite's exact free-energy change. So the composed energy identity
    carries water's second order, and adds nothing of turnover's.
- **The cost:** 3.1–4.45 agent-days for the first build (turnover and the lumen), against D375's 3.25–4.5. Route B's
  lumen is 0.35–0.5 cheaper than D375's, and 0.2–0.45 was added for rows the first version lacked (§3.9). The coupling's
  step adds D375's 2–2.5, carried here, not re-derived.
- **The lead's rulings on this revision** (§8.2): route B for the lumen; the symport and the bath schedule each get a
  parse row and one tier-3 run; the run view for water worlds is logged apart (§9.2).

## 1. What reads the declared volume or masks today, and why

### 1.1 The refusals, in the engine's words

Rows 1–6 are run 2, at f8c6c326; rows 7–9 are the lumen probe, at 95559271 (§9). "Lifted" means turnover's fixed reads
were replaced in process by §3.1's set, under the same law ID.

| World | Today | Lifted |
| --- | --- | --- |
| FR-43 2B's swelling cell, with S produced and cleared in the cell | "scheduled_species_turnover@1 reads volume as declared, but ideal_osmosis_linear_compliance_water@1 provides it", and the same for `extracellular_volume` | Parses |
| A1 in a swelling cell: the gene unit, turnover of X, and the coupling's Hill factor on initiation | Turnover's two refusals, plus the same two for `species_regulated_availability@2` | Still refused by the coupling's two. It parses once the coupling's declarations are lifted too, but that program is unexercised: the coupling's code still reads `p.volume` |
| S5's division (`partition_fixtures.divided`), daughters keyed by their slots | "reads active as declared, but isopotential_partition@1 closes it", and the same for `membrane_active` | Parses |
| The same, with daughters keyed by their carriers c1 and c2 | "route p1 needs a schedule for its founder carrier d1" | The same refusal, from the occupant rule |
| The cleft cell's furrow, S cleared at the cleft, beside insertion@1 | "reads outside_active as declared, but scheduled_membrane_insertion@1 provides it", and the same for `membrane_active` | Parses (§3.1's anchor guard would then refuse it) |
| The same beside insertion@2 | "… scheduled_membrane_insertion@2 closes it", and the same for `membrane_active` | Parses |
| S5's furrow world with a lumen (`cleft_divided`), turnover on cells, declared after the lumen | Four: "reads extracellular_volume as declared, but restricted_cleft_lumen@2 provides it", and `active` (the partition), `outside_active` and `membrane_active` (insertion@2) | Parses |
| The same, turnover declared first | The same | "reads the view extracellular_volume at stage split before restricted_cleft_lumen@2 changes it there", and the same for `outside_active` and insertion@2 |
| The cleft cell with insertion and lumen@1, or @2, turnover on the cell | "reads extracellular_volume as declared, but restricted_cleft_lumen@1 provides it" (or @2), and the masks' | Parses |

- **Parsing runs every definition check** (`pump_composite_spec`, line 225). So nothing else in the engine refuses
  these pairs.
- **What a parse does not show.** Turnover's volume rule and anchor guard (§3.1, §3.5) are not written. So no probe
  exercised them, and the parses of the lumen worlds do not show that a lumen at a node turnover clears is refused.
- **What the lift was.** Run 2 made four fields current reads, unscoped, declared no anchor read, and set them as class
  attributes after registration, so the contract's `check_declarations` never saw them. It also lifted the coupling, for
  row 2's last case. Run 3 put §3.1's set through `check_declarations` (it passes) and the parse of five worlds. The
  anchor's read at the end was added since; the companions probe (§9.1) passed it through `check_declarations` too.
- **The order after insertion and the lumen is the engine's word** (C2). Turnover declared before insertion@1 or @2 is
  refused with "reads the view outside_active at stage split before scheduled_membrane_insertion@… changes it there",
  and before a lumen with the volume's message above.
- **The slot-keyed admission hides a hazard.** A positive rate keyed to slot d1 from t = 0 applies before d1 is born.
  With today's declared mask it writes into the pending slot, and the partition's overwrite then breaks S's ledger at d1,
  by −2.0e-12 fmol (OPERATOR_COMPOSITION_DESIGN §2.3, L4).

### 1.2 Turnover's read sites

The sites are in `src/cells/operators/species_turnover.py`, re-checked after the merge. OPERATOR_COMPOSITION_DESIGN §3
has the same table, at 3c10b833.

| Field | Read site | What it assumes | Kind |
| --- | --- | --- | --- |
| `volume` | `_node_update`'s work and magnitude: `species_chemical_free_energy_pJ` and `species_chemical_magnitude_pJ` at `p.volume` (lines 299–300, 333) | The booked work is ΔF at the declared volume | Real, but for the booking only. The update reads no volume |
| `extracellular_volume` | The same at finite outside nodes (line 345) | The same | Real at a node with a route. At every other node the value is computed and selected away |
| `active` | `touched` in `_node_update` (`p.active`, line 334) | Rates act on closed cells: a pending daughter or a retired parent | Real |
| | `turnover_domain_valid`: zero where no owner, and positivity (lines 458–470) | Slot existence | Reference |
| `outside_active` | `finite = p.outside_active & ~p.reservoir` (line 341) | Clearance acts on a closed onset node | Real |
| | The domain (line 462) | Slot existence | Reference |
| `membrane_active` | Never read; it is only on the shared list | — | Nominal (the matrix's tag) |
| `extracellular_amount_reference` | `p.extracellular_amount_reference[rows]` (line 344), **undeclared**, and again in the domain | An open finite node holds its declared anchor | Latent, but true today. Closers pad closed nodes only. Insertion@1 provides the declared anchor at open nodes. The bath schedule doses held baths, where turnover has no route |
| Occupants (host) | `species_common.occupants` and `route_tables`. Each cell is its own founder from t = 0, followed by replacement@1's newcomers, which are found by law ID | A slot's carrier is its cell from the start | Real beside the partition |

### 1.3 The other declared readers in these worlds

| Operator | Fixed reads | Why | Under FR-65 |
| --- | --- | --- | --- |
| `species_regulated_availability@1`, `@2` (the coupling) | The shared list | Its factors read c = n/V at the declared volume (D244's Q2 for @2's site sources), at the control view and in its targets' half-steps | The second step (§3.8) |
| `scheduled_species_exchange@1` | The shared list | Uptake reads c = n/V | Unchanged |
| `population_unit_turnover@1` | The shared list | It requires membrane state, which water refuses. Division and insertion are refused world-wide (D232) | Unchanged |
| `templated_polymerisation@1` | The masks | Its chains, hold and machines have no division or onset rule. Its volumes have been current since part 2B, so its degradations already run in a swelling cell (FR-38 v2's family D) | Unchanged |
| `local_species_reactions@1` | The masks and the outside anchors | Closers, and insertion@1 | Unchanged |
| `isopotential_partition@1` | `volume` | The daughters' volumes are declared anchors (M4) | So turnover with water and the partition together stays refused |
| `ideal_osmosis_linear_compliance_water@1` | `membrane_area` | Its conductances are bound from the declared areas. Its undeclared mask reads (gap 5) land with this change (M2) | So turnover with water and insertion together stays refused |

The compartments declaration, trafficking, the wash, replacement@1 and injection keep their reads, and so do the integer
population's volumes. None of them meets FR-65's worlds.

## 2. The prior art

- **FR-43 part 2B** (FR43_SHARED_INVENTORIES_DESIGN §2.3; D324). The reactions and the gene unit read both volumes
  current at the split, with a view passed only where water changes them (C1's fallback), and their masks still fixed.
  `check_volume_changers` admits water alone. C2.7's endpoint identity converged at a ratio of 4.006.
- **FR-38 v2's family D.** The gene unit's first-order degradations run in the same swelling cell, with labels, and read
  V only through their bookings, as turnover does. Amendment 3 judges their energy identity as a stepped entry at p = 2.
- **`integer_unit_population@1`** reads the patch mask and the outside anchors current at the split, and selects a
  closed site idle.
- **The lumens' bookings are exact per fill** (`restricted_lumen.py`): the mixing heat is the exact W − ΔG, and the
  dilution term brings @3's chemical term to the physical one. Their `own_valid` refuses a volume increment at any node
  that is not theirs.
- **Lifetimes through the contract.** Insertion@2 (`lifetimes`) and the integer population (`lives`) read every
  operator's `living_intervals`, never importing the operator that decides them. `patch_maps` and `onset_patches` are
  host hooks of the same kind.

## 3. The design

### 3.1 How turnover reads, stage by stage

**Option A:** the same law ID, with its own declarations.
- It meets the composition design's test (§4.4): no new state, entity write or ledger term, and the same expression at
  another volume.
- Turnover takes its own tuples, as the gene unit did. The shared list stays as it is, because exchange, the coupling
  and the unit producer read it.

| Field | Read | Where it is used |
| --- | --- | --- |
| `volume` | Current at the split | The work and magnitude of each half-step |
| `extracellular_volume` | Current at the split, scoped to its outside route nodes (`read_slots`) | The same at finite nodes |
| `active` | Current at the split; reference at the end (C3) | `touched`; the domain's existence and positivity |
| `outside_active` | Current at the split; reference at the end | `finite`; the domain |
| `membrane_active` | Dropped | Never read |
| `extracellular_amount_reference` | Reference at the split, and the domain's at the end, with the guard below | n = anchor + increment at open finite nodes |

- **The half-step** takes `view=None`.
  - With a view, its volumes and masks come from the view and are held over the half-step. Without one, today's code
    runs.
  - Cell anchors (`amount_reference`) stay on the declared layout. They are not a view field, and close() changes them
    only on closed slots, where turnover now writes nothing.
- **It has no event part, and its observed columns are its own accumulators.** So it reads nothing at the event or at
  observation.
- **The order follows C2.** Turnover is declared after water, insertion and a lumen, whose changes count at their split.
  The partition closes at its event, so turnover sees it in the same step in any order.
- **Option B,** `scheduled_species_turnover@2`, is rejected. It would be a new law, unqualified on every world, with its
  own crossrev and matrix rows, for no change in accounting (composition design §4.2–4.3).
- **A lagged read**, at the step's start, would make the coupling first order. Today's fixed read is an O(1) error
  (composition design §6).

**The outside anchors.** There are three ways to declare the read.
- **(i) A reference read with a guard (the design).**
  - It states what the code reads and constrains no changer, so no admitted world's program moves.
  - The guard keeps it true. Turnover's definition check refuses a provider of `extracellular_amount_reference` whose
    change reaches one of its outside route nodes. An unscoped change reaches every node.
  - The bath schedule is scoped to held baths, so it never meets the guard.
  - Insertion@1 is unscoped. It is refused where turnover clears at a node, and admitted where turnover acts in cells
    only. Admitting it at a node would need insertion@1 to declare its anchor change as padding, which is not proposed.
  - The composite already refuses an anchor provider beside a closer.
- **(ii) A current read.** Turnover would become a view reader beside every bath schedule. That changes the program of a
  pair that never meets, because the composite's view readers ignore slots.
- **(iii) A fixed read, as the reactions have.** It would be refused beside insertion@2, by M1's rule on closures that
  reach the field.

### 3.2 Concentrations, rates and the ledgers

- **Rates** are amounts per time: P in fmol/s and k in 1/s, a per-cell source and a per-molecule hazard. Neither
  depends on V, so the current volume leaves them, and the exact update, unchanged.
- **No swelling-dependent clearance law is introduced.** Evidence the Lean lane holds supports keeping such a rate
  specific to its preparation and its nutrient conditions. It was relayed by the user through the lead on 24 November;
  this author has not read it, and one preparation is an indication only.
  - A world whose clearance depends on swelling, or on its nutrient conditions, declares that rate as a parameter of the
    world: a sourced, piecewise value in `turnover_controls`.
  - A routed rate changes as its regulator dilutes. That is the world's declared coupling, not a swelling law.
- **Amounts** follow the closed form at every dt, to rounding, on a row that turnover alone writes.
- **Concentrations** are water's readout columns, n/V at the row's current volume (§4.2). Turnover owns no concentration
  column.
- **The material ledgers** are unchanged.
  - Produced is P h and cleared is n f + P (h − g), both gross and in amounts.
  - At a division the partition books its moves of each increment.
  - Turnover never writes a closed slot, so a daughter's increment is still 0 when the partition writes it (§3.4).
- **The energy ledger** (S).
  - Each half-step books F(n′, V) − F(n, V) at the view's volume V.
  - The composite's stored free energy is @3's chemical term at V₀ plus water's dilution term −RT N ln(V/V₀), which
    equals F(N, V) (FR43_SHARED_INVENTORIES_DESIGN §2.3).
  - So turnover's booking is the exact change of that stored energy, to rounding: 3e-17 pJ or less in the composition
    probe.
  - The identity's step error then comes from water's Heun heat and bath work alone, which are second order.
  - Booked at V₀, each move would miss −RT Δn ln(V/V₀). That is an O(1) error, which no dt reduces: 4.8e-7 pJ per
    0.01 fmol at the probe's state.
- **Water's bookings** are unchanged. Turnover's production and clearance change the osmolyte count, so V couples to
  turnover through water's Π. The palindrome W(h) T(h) I(dt) T(h) W(h) is second order for the coupled system
  (composition design §6).

### 3.3 Composition

- **Water:** cells and finite outside nodes, through the view.
- **The partition, at fixed volume.**
  - Closed cells are idle by the current mask, and carriers come from the occupant hook (§3.4).
  - Turnover's per-slot accumulators need no division rule. The parent's stay on its retired slot as its history, and
    each daughter's start from zero at birth.
- **Insertion@2, at fixed volume.** A closed onset node is idle until its onset. From then on it is cleared from its
  declared content. Outside routes are environment, scheduled per node, but a positive rate in force before the node's
  onset is refused at the definition (§3.4).
- **Insertion@1** is admitted where turnover acts in cells only (§3.1's guard).
- **A lumen,** where turnover has no route at its node (§3.5).
- **Labels (FR-42).** Turnover reports its one-way moves from its amounts: production into the arrival label, and
  clearance out of every label at its share. So labels beside water carry over unchanged, as FR-38's family D's do.
- **Cohorts.** A window's labelled material decays as e^(−k(t − s)), whatever V does. Its concentration dilutes with V.
- **FR-50's one-way records** (phase 1 landed, 1939563e).
  - Turnover's produced and cleared are already its one-way records, in amounts, so the current volume leaves them
    exact. FR-65 adds no record.
  - Phase 1's route records are the passive kind's and the transporter's. Its refusal rows (K5) are a rectifier, a
    net-flow transporter mode, RK4, and an operator that retires or closes slots. They name neither turnover nor water.
    So a route with `one_way` cannot sit beside the partition or insertion@2, whatever turnover does.
- **The other writers of a row** keep today's rules (§3.6).

### 3.4 The occupant rule for the partition's carriers

Today each slot's carriers are built from replacement@1's events, which `occupants` finds by law ID. The partition's
daughters are invisible to it. D150 §5.2 has already ruled that "Daughters of an S5 partition are new carriers with
their own declared rates".

- **A host hook in the contract,** `slot_occupants(spec, declaration, schedule)`, with the default `{}`.
  - It gives the slots an operator fills, each with its carriers as records (carrier, birth, death, kind, template,
    donor). The record type moves into `contract.py`, so the operators need not import `species_common`.
  - Replacement@1 and the partition implement it; the partition builds its records from its `lineage`.
  - `species_common.occupants` merges them over the founders, and refuses a slot that two operators fill.
  - No module imports the operator that decides: the J2 line, as in insertion@2's `lifetimes`.
- **Rates outside every life are zero, by explicit entries in the tables.**
  - A daughter's schedule, keyed by its carrier, starts at its birth, and its table opens with (0, 0) before it. Without
    that entry the rate at birth would apply from t = 0: `control_arrays` reads the first entry before its time.
  - A retired parent's table ends with a zero at its retirement.
  - Each reader gives its idle value. Turnover's is 0. The other users of `occupants` stay refused beside a partition.
  - So for cells the composition design's living-interval refusal follows from the occupant rule.
- **An outside route before its node's onset is refused** (D150 §5.3). The onset comes from the contract's
  `onset_patches`, which insertion@2 defines. An outside route beside insertion@1 is refused anyway (§3.1).
- **The founder rule moves from parse to the definition, where the occupants are known.** Today `parse_schedules` holds
  it ("needs a schedule for its founder carrier", "starts at time 0").
- **Its other readers get the same tables:** exchange, sites, labels and the reactions. Without a partition the tables
  are bitwise today's.
- **`pump_composite.OCCUPANT_EVENTS`** also names replacement@1 by law ID. It selects the event rows whose observed
  controls are held (D264). It stays: turnover observes only its accumulators, so the partition's events need no entry.
- **Triggered lifecycles,** whose births are unknown at the definition, would write their rates into state at birth
  (D150 §5.2). They are not part of FR-65.

### 3.5 The lumen

**What a lumen does.** It provides `extracellular_volume` at its own node, fills the node with bath fluid at the source's
declared composition (every species row, so S too), and books the fill itself. It changes no cell volume. `own_valid`
refuses, at every step's end, a nonzero volume increment at any node that is not its own.

**The nodes turnover does not read.** Turnover reads a volume at each cell and at each of its outside route nodes, and at
no other node. It reads its rows' amounts at every finite outside node only to check that they are finite and positive,
from the declared anchors. A lumen's fill keeps its node's amounts positive (S). So a lumen at a node where turnover has
no route is invisible to it, which is what the user's decision asks for.

**The shared rule refuses the other case.** Its definition check, `check_volume_changers` in `species_common`, becomes
per node for the outside volume, and is used by turnover, the reactions, the gene unit, and in the second step the
coupling.
- A changer of the cell volume other than water is refused, as today, which covers replacement@2 (it writes water's
  volume increments).
- A changer of the outside volume other than water is refused if it reaches a node the reader reads.
- Door S does not do this for us. A current read declared after a change on a shared slot is admitted
  (`scope_errors`), so the refusal has to be by name.

**The mechanism.** The rule has to know which nodes a lumen changes. The reactions' row for it
(`test_the_other_volume_changers_are_refused_by_name`) calls it with no declarations, so it is rewritten. Three routes:

| Route | How | What it admits | Price (S) |
| --- | --- | --- | --- |
| A | Refuse any outside route of turnover beside a lumen. No lumen edit | Turnover in cells only | 0.5–0.75 |
| **B** (chosen) | A host-only hook, `changed_volume_nodes(spec, declaration)`, with the default "every node". The lumens name their nodes. The rule asks it | A lumen at any node turnover has no route at | 0.65–1 |
| C | Door S: the lumens declare a scoped change, `changed_slots` and `view_slots` | The same, plus turnover declared before the lumen, and water on another node later (gap 7a) | 1–1.5 (D375's figure) |

- **What decides between them.** No known consumer clears at a finite node in a lumen world. The furrow consumers act in
  cells only, which route A already covers. Route B is the least that says what the user chose, for about 0.15–0.25 more
  than A, and 0.35–0.5 less than C. It changes no device program, so S3's cleft egg and S5's judged furrow worlds keep
  theirs.
- **Route C** adds a select to the view merge of every lumen world. The values stay bitwise, but the program text moves.
  So S3's and S5's judged worlds would need a pair check, and the crossrev sets that hold a lumen would be renewed. It
  buys order freedom and coexistence with water at another node. Neither is asked for today.
- **The lead ruled route B** (§8.2). A and B need only that turnover is declared after the lumen, which the probe
  confirms. C relaxes that too.

**The lumen at a node turnover clears** stays refused by name, until a probe covers its dilution term for an outside
booking. The identity is water's, and the fill is exact, so the same argument would hold there (S), but no probe has
shown it.

### 3.6 Which refusals lift, which stay, and what newly parses

| Composition | After FR-65 |
| --- | --- |
| Turnover beside water | Admitted, with water declared first |
| Turnover beside the partition | Admitted, with daughters keyed by their carriers |
| Turnover beside insertion@2 | Admitted |
| Turnover beside insertion@1 | Admitted with cell routes. Refused by the anchor guard where turnover clears at a node |
| Turnover beside a lumen at a node it does not read | Admitted (route B), turnover declared after the lumen |
| A lumen at a node turnover clears; replacement@2 beside turnover | Refused by name (the shared rule) |
| Water with the partition, or with insertion | Refused by the partition's and water's own reads (M4, M2) |
| A1 in a swelling cell, and any routed turnover rate beside water | Refused by the coupling's reads until its step (§3.8) |
| Charged routes, held baths, and D152 or the gene unit on the same row | Refused, as today |
| RK4 beside water | Refused by the engine: split-only parts cannot sit beside water's coupled part |
| Labels beside insertion@1 or @2, or a lumen | Refused by the label owner, in its own words: insertion@1's "view changes species amounts", insertion@2 "closes or retires slots", and a lumen "writes species amounts without reporting its one-way moves" |
| S crossing a bridge | Refused by name (`check_impermeant`: "'S' has a route through junction bridge_1") |

**What newly parses, and what covers it** (D327's rule). Among the ordered sequences of up to three operators
that contain turnover or a lumen, 5,559 in all, the structure check admits 584 where it admitted 565: 19 more. A lumen
stack with turnover has at least four operators, so it is parsed apart (§9). Reduced to sets:

| Newly parsing set | What couples | Covered by |
| --- | --- | --- |
| Water + turnover | V and the osmolyte count | The swelling rows (run) |
| + the reactions | The network reads V, and turnover moves it | The same rows, with the network active (run) |
| + labels | Labels report turnover's moves | The labelled rung (run), beside water. Labels beside insertion or a lumen are refused by name (a row) |
| + the gene unit | It reads V and writes its own rows | A1 without the coupling, one run; A1 with it, in the second step |
| + replacement@2 | It writes water's volume | Refused by name (a row) |
| + the K-anion symport | It reads water's volume factor; turnover reaches it only through V | A parse row, and one tier-3 run (below) |
| + the bath schedule | Doses at held baths, isosmotic beside water | A parse row, and one tier-3 run (below) |
| The partition, or insertion@2 | Closed slots, carriers, masks, anchors | The furrow and cleft worlds (run) |
| Insertion@1, turnover on cells only | Masks and anchors, which the guard keeps away from turnover | A parse row, and the argument. The runs use insertion@2 |
| Insertion with a lumen, and with the partition | The lumen's volume at its node | The furrow world with a lumen (run) |
| + injection | Charge only, and it reads `volume` as declared, so it never meets water | A parse row |
| + a bridge, S impermeant on it | A junction that S does not cross | A parse row. S's pools do not equilibrate through it |

- **The argument** for the symport and the bath schedule: neither writes a row turnover writes, changes a mask or an
  anchor, or is read by turnover. Their own dependence on V, or their own isosmotic rule, is tested in their own worlds.
- **Their runs** (the lead's ruling: a pairing that newly parses gets one composed-world check). Each is a row of
  `test_shared_inventory_volume.py` (tier 3), with every host check on every row and S's amounts against its closed form
  at rounding, over 100 steps of 1 ms.
  - **The symport:** `with_symport(with_water(heredity_cell("D")))` with S and turnover. Reason: the symport's volume
    factor reads the same V that turnover's osmolytes move. About 40 s or more (an estimate: the record of
    `test_pump_composite_water.py`, 558 s over 15 tests, some of them parse-only, so a compiled run may take longer).
  - **The bath schedule:** `bath_schedule_fixtures.water_world` with an isosmotic step and S. Reason: its event changes
    the held bath's anchors, and water's exchange with it. About 60 s (an estimate: the recorded wall times of
    the bath schedule's two compiled test files, 57 s and 67 s).
  - **The measured seconds are stated at landing** (D224), where the tier record is re-measured. Both worlds parse under
    §3.1's set (one parse per process, §9.1); without it they are refused by turnover's two volume reads.
- **The composition-matrix cells** are regenerated and their tags rewritten in the landing's commit, per
  `composition_matrix --write`.

### 3.7 Restart and checkpoints

- No state, layout or control field is added, and no lumen program changes.
- The reader view is a function of the state. The occupant tables are per-world control data, recomputed from the
  definition at a restart (R7), now with the partition's carriers.

So a resume is bitwise by construction. Rows check it in the swelling cell, across a division and across an onset
(§6).

### 3.8 The coupling's step: its inputs (D375, Q1 b)

The coupling's step comes second. Its contract extension is designed there, and this is what it starts from:

- **The volume read sites in `species_regulated_availability.py`:** `route_factors` (control factors, `factor_valid`,
  `factor_record`, `rate_factors`, and the observed `coupling_factor`), `state_inputs` (its states' half-steps),
  `range_valid` (the routes' declared operating range), `site_route_sources`, and `factors_valid`. `site_route_sources`
  is not reached beside water today, since sites refuse it. `factors_valid` has the same outcome at any volume: a Hill
  factor lies in [0, 1].
- **A routed half-step receives no view.** `pump_composite._routed_control` passes `rate_factors` and the routed
  `factor_record` the state only. The extension passes a source with a current read its reader view there, as R2 does
  at the control view. `observe_history` calls it too, at the row's state.
- **R2 passes the views wherever the read is declared,** not only where a field has a changer: `factor_fields` is built
  from the declarations alone. The extension must pass a view only where a changer exists, or show that an unused view
  changes no program. This bears on A5″'s program identity, and on the carried price.
- **The coupling calls the shared volume rule.** Otherwise water with replacement@2 and the coupling would parse, and
  its replaced-slot checks look up replacement@1 only.
- **Operating ranges.** A world whose regulator dilutes out of its declared range is refused at run time, as today; the
  world must declare a range that holds it.
- **Evidence.** @2 subclasses @1, and FR-6's A5″ (@1) is judged, so the pair check covers both. The masks stay fixed, so
  the coupling stays refused beside closers and lumens.
- **Price:** D375's 2–2.5 agent-days, carried. A1 in a swelling cell is the composed check of its readers.

### 3.9 What changes, and the cost

| Item | Files | Agent-days |
| --- | --- | --- |
| Turnover's declarations, `read_slots`, the half-step's view and the anchor guard | `species_turnover.py`, `species_common.py` | 0.5–0.75 |
| The shared volume rule moved, with its two callers updated | `species_common.py`, `species_reactions.py`, and an import in `templated_polymerisation.py` (the gene-regulation lane's file) | 0.25 |
| The occupant hook and tables, the founder rule moved | `contract.py`, `cell_replacement.py`, `partition.py`, `species_common.py` | 0.75–1 |
| The tests, the regenerated matrix and library pages, Q5's split, D148's evidence | tests, `composition_matrix.py`, `PUMP_COMPOSITE.md`, D150's §5.5, `tests/tier3_record.json` | 0.75–1 |
| *The first version's core* | | *2.25–3* |
| Added since: the tables' zeros, the onset-node refusal, the companion rows and their two runs, the replay row and its saved-file check, plants P3 and P5 | tests, `species_common.py` | 0.2–0.45 |
| The lumen (route B): the hook, both lumens, the per-node rule and its rows, the furrow world's runs | `contract.py`, `restricted_lumen.py`, `restricted_lumen_v2.py`, `species_common.py`, tests | 0.65–1 |
| **The first build** | | **3.1–4.45** |
| The coupling's step (D375, carried) | | 2–2.5 |
| **In all** | | **5.1–6.95** |

- **Against D375's 3.25–4.5.** D375 took the first version's core (2.25–3) and priced the lumen at 1–1.5, the scoped
  route C. Route B costs 0.65–1, 0.35–0.5 less, and D148 covers no lumen world. Against that, 0.2–0.45 was added, the two
  companion runs among it. So the first build comes to 0.15 less at the low end and 0.05 less at the high end. With
  route C it is 3.45–4.95.
- **The run view for water worlds** (§9.2) is priced apart, at 0.25–0.5 (S), for the water owner, and is not in these
  figures.
- **Pre-alpha, so no backwards compatibility.** The moved helpers leave no alias. `occupants`' lookup of replacement@1 by
  law ID goes when the hook lands; `replacement_of` stays for its other callers.

**D148.**
- **By construction:**
  - every world without a changer of turnover's read fields keeps its program, because no view is passed;
  - the lumens' programs do not change under route B;
  - without a lifecycle operator other than replacement@1, the occupant tables are bitwise today's.
- **The evidence at landing:**
  - a jaxpr-text pair check of turnover's admitted worlds: turnover alone, and beside replacement@1, the bath schedule,
    exchange, labels, the coupling (FR-6's A5″) and FR-1's C6 compartment;
  - crossrev's sets, and G1 at 113 of 113;
  - the control arrays of every crossrev world whose operators read `occupants`.

**Q5 flips.** D150's registered Q5 runs `test_version_1_refuses_volume_providers_area_providers_and_mask_providers`.
- Its turnover-beside-water case becomes an admission. Its insertion@1 case stays refused, now by the anchor guard.
- The composition design's §16.1 rule applies, with its 20 November precedent: the case is amended in place and
  disclosed, the admission is tested outside Q5's list, and the verdict judged at f7f0592 stands within its static-tissue
  scope.

**Fast.** The cost is two scoped reader views per step, elementwise (C4). The composition design's estimate is under
1–2% (§11); it is not measured. One development timing of the swelling world against its V₀ twin runs on the timed
cores, under their lock, and is reported with the landing. It is not a gate.

## 4. Readout classes and saved records

### 4.1 The classes

FR-38's amendment 3 taught the split. An identity that a writer books exactly closes at rounding. One that integrates
water's dynamics carries water's second order.

| Class | Identity or readout | Bound |
| --- | --- | --- |
| **Exact** | Worlds without a changer of turnover's read fields: program and records | Bitwise |
| | A closed slot (a pending daughter, a retired parent, a closed onset node): its rows' increments and turnover's fields there, while it is closed | Bitwise |
| | Turnover's fields at a lumen's node: it has no route there | Bitwise zero |
| | Zero rates: the start state | Bitwise |
| | Labels on and off: the physical rows | Bitwise |
| | A resume against the unbroken run | Bitwise |
| **Rounding** | Turnover's amounts against n(t) = P/k + (n₀ − P/k) e^(−k(t − t₀)), per carrier from its birth and per node from its onset. In a lumen world the same, for the cells | The bookings' rounding over the steps taken |
| | Water's concentration columns against n/V | 4 ε |
| | The material ledgers, the partition's moves at a division, and the lumens' fill ledger | Their own allowances |
| | Each half-step's work against F(n′, V) − F(n, V) at the view's V | 1e-11 relative (Decimal, the test of record) |
| | The same work against @3's term at V₀ plus the change of water's `node_free_energy_pJ` | The absolute rounding of its terms |
| | A cohort's labelled amount against its closed form | Rounding |
| **Order window, p = 2** | V(t), and every quantity that integrates it: water's heat, the bath's water work, and turnover's cumulative work | FR-43's C2.6 form: the ratio of the errors against an in-test reference at 2h and at h lies in [3.6, 4.4], with its 1e-8 floor |
| | The endpoint identity F(N_t, V_t) + U(V_t) − F(N₀, V₀) − U(V₀) − (W − H), with turnover's, water's and the bath's terms | Amendment 3's stepped entry, with e_ref = 0 (below) |

**A lumen world has no water.** Nothing of turnover's enters the order window there, and it adds no readout of its own.
The lumen's bookings are exact per fill, and its ledgers keep their own bounds. Its volume follows the area with a
splitting lag that its own step study covers. We claim no bitwise twin of a lumen's fields without turnover: that has
not been checked.

**The stepped entry.**
- d₁ = max |r_2h − r_h| and d₂ = max |r_4h − r_2h|, from runs at h, 2h and 4h.
- est = max(d₁/3, d₂/12).
- **Pass** if max |r_h| ≤ 3 est + e_round. e_round is amendment 3's, 8 ε S_h s, with turnover's work among the bookings'
  magnitude s.
- **The order:** where d₁ and d₂ both exceed 10 e_round, q = log₂(d₂/d₁) must lie in [1.5, 3.5]. Otherwise the run is
  inconclusive, and takes amendment 3's retry.

**The V₀ plant shows in energy only.** Turnover's amounts never read V, so an amount ratio or a "miss in amounts" plant
(C2.6, C2.8) cannot discriminate it.
- **The miss is on the net move.** The work is booked on the moved amount, produced less cleared. So a V₀ booking misses
  RT ∫ (P − k n) ln(V/V₀) dt.
- **The plant world is sized first.** That miss must be at least 100 times the correct run's identity residual at h
  (C2.7's rule). It is set in development, before the rows land.
- **The world stays far from steady state while V moves.** Near n = P/k the net move, and with it the plant's miss,
  vanishes. Production alone, or a pool far below P/k, keeps it large.
- **The run-time ledger is not relied on.** The operator's own guard statement says the shared energy bound is blind to
  these bookings at µM to nM. Whether the ledger refuses the plant is reported.

### 4.2 What a saved run carries, for replay outside the engine

The Lean lane asked, through the user, for amounts and the water volume as separate readouts, so dilution can be replayed
outside the engine. They exist. What follows is read from `io.write_run` and the bound model of FR-43's swelling cell
(the records probe), not from a saved file.

- **In `trajectory.npz`,** at every accepted row, the state arrays `amount_increment` [species, cell], in fmol,
  `extracellular_amount_increment`, `volume_increment_pL` [cell] and `extracellular_volume_increment_pL` [node]. The
  same file holds the anchors as constants: `amount_reference`, `extracellular_amount_reference`, `volume` and
  `extracellular_volume`.
  - The amount is `amount_reference` + `amount_increment`, and the volume `volume` + `volume_increment_pL`.
- **At each observed row:** `observed_amount` [species, cell] and `observed_extracellular_amount`, in fmol (their declared
  unit), beside `observed_cell_volume_pL`, `observed_extracellular_volume_pL` and `observed_cell_concentration_mM`. So n
  and V are separate columns on the same rows, and c = n/V.
- **The files.** `io.write_run` writes both. In a windowed run the chunks hold the state arrays only with
  `recording: full`, and the observed columns unless it records checkpoints only. The anchors are then the definition's,
  in `checkpoint_initial`.
- **No new export is needed.** These readouts are from the code and the bound model, not from a saved file, so the
  build checks them against one saved file, once, and its test says so: it writes the swelling run with `io.write_run`,
  reads `trajectory.npz` back, and checks the fields, that `observed_amount` equals anchor plus increment, and that
  c·V = n.
- **At a lumen's node,** `lumen_volume_pL` is filled to the area at the saved time, while the amount column is the
  state's. Amount over volume is not the concentration there; the lumen's own `lumen_concentration_mM` is.
- **The run view is refused for a water world.** `run_view.prepare` on the swelling cell says: "ideal_osmosis_linear_compliance_water@1
  declares no VIEW_LAYERS; resolved_pump_tissue@3 declares no axes, unit or layer for its field energy_balance_pJ_s; …
  declares no axes for its readout column cell_volume_pL …". Water's layers, units, kinds and axes, its volume
  increments' reference, and the balance rate it replaces are missing. It is logged apart (§9.2) and does not block
  replay.

## 5. IDs under the planned rename

- **No new ID or major** (option A). Turnover keeps `scheduled_species_turnover@1`. The rename's candidate mapping
  (read-only, at ce4780d2, in `/mnt/workspaces/Cells/rename-design-20261124/`) maps it to
  `cells.operator.scheduled_species_turnover@1`.
- **Its partners there** take the same form, `cells.operator.<name>@major`: water, the partition, insertion@1 and @2, the
  lumens, the labels, the coupling and the gene unit. The table at f8c6c326 has a row for each. The rename's design note
  (`rename-design`, b5c44a6e, not yet on main) keeps `operator` for every operator (D371).
- **Step IDs are not renamed.** Turnover's `exact_production_clearance_half_steps@1`, water's
  `heun_frozen_amount_water@1` and the lumens' fill step are among the 35 recorded labels that D371 (Q4) leaves out of
  scope.
- **The build comes after the rename** (D375), so its code, refusal messages and test rows use the new keys, and nothing
  waits for a re-merge.

## 6. The qualification plan

Q2 (a), D375: the builder's tests, with no registered criterion. Everything below is development evidence.

### 6.1 Each claim and its cheapest proof

| Claim | Proof | Where (tier) |
| --- | --- | --- |
| The booking at the view's volume is the exact ΔF, and the exact change of the composite's stored energy | The NumPy half-step, given a reader view with V ≠ V₀: its work against Decimal ΔF at V, and against @3's term at V₀ plus water's node term. Its amounts are bitwise the viewless call's | A row of `test_booked_work_is_the_exact_free_energy_change` (1) |
| Nothing writes a closed slot, or a lumen's node | The NumPy half-step, given a view that closes a cell and a node, with positive rates there: the rows and fields there stay bitwise unchanged, and the declared-mask plant writes there. A lumen's node, with no route, stays bitwise zero | A row of `test_zero_rates_select_the_start_state_and_untouched_entries_stay_bitwise` (1) |
| Admissions and refusals | Parse rows for §3.6's sets. Admitted: water, the partition, insertion@2 at a node, insertion@1 with cell routes, a lumen at a node turnover does not read. Refused, with their reasons: replacement@2, a lumen at a cleared node, insertion@1 at a node, the slot-keyed daughter, S crossing a bridge | Rows beside `test_definition_refusals` (1) |
| The occupant tables | Host rows. A daughter's controls are zero before its birth and its own after. The parent's are zero after retirement. An outside rate before its node's onset is refused. Without a partition the tables are bitwise today's. Planted: a table without the leading zero, and one that keeps the parent's rate | `test_species_turnover.py` (1) |
| The swelling cell | Three rungs (4h, 2h, h) of FR-43's swelling cell, the network active. S is produced strongly enough to move V, and stays far below P/k while V moves (§4.1). The checks: the amounts against the closed form, the concentrations, V against the in-test reference, the identity's stepped entry, the V₀ plant, the replay row of §4.2 (checked once against a saved file, which the test says), and a resume mid-run, in process and through a written snapshot | Rows of `test_shared_inventory_volume.py` (3) |
| The gene unit beside turnover and water | A1 without the coupling: host checks on every row, and X's closed form | One row beside the swelling rows (3) |
| The symport, and the bath schedule, beside water and turnover | §3.6's two runs: host checks on every row, and S's closed form | Two rows beside the swelling rows (3), about 40 s and 60 s (estimates; §3.6) |
| The division, with insertion@2 and a lumen | S5's furrow world (`cleft_divided`, with its lumen) with turnover in its cells, keyed by carriers: closed slots bitwise, the closed forms from birth, every ledger including the lumen's, and a resume before, at and after the division | A turnover fixture beside `division_run`, used by `test_partition_runs.py`'s closure and restart tests (3) |
| The onset | The cleft cell with insertion@2 and clearance at the cleft, lumen-free: idle before the onset, the closed form after it, and a resume across the onset. S's face diffusivity is set so low that its transport stays below rounding over the run, since a positive value is required | A turnover fixture beside `cleft_run`, used by `test_membrane_insertion_runs.py`'s closure and restart tests (3) |
| Labels beside water | The swelling cell's h rung, labelled: its physical rows bitwise, and a production window's cohort against its closed form | One row beside the swelling rows (3) |
| D148 | §3.9's pair check, crossrev and G1 | The landing's gate |

**The in-test reference for V(t)** runs on the host. It integrates the coupled ODE of V and the network's amounts, with
S's amount taken from turnover's closed form, together with the quadratures of water's heat, the bath's water work and
turnover's work, at a tolerance far below the engine's error. It is development evidence and not code-blind.

**Cost (D224).**
- **Tier 1:** every item is a row, NumPy or parse only, a few seconds in all. These rows are the routine guard.
- **Tier 3:** the compiled items are rows and fixtures in three existing files: about 9 runs of the swelling cell and its
  companions (3 rungs, the V₀ plant, the resume, the labelled rung, the gene unit, the symport, the bath schedule), 3 of
  the furrow world (the run, its resume, and the declared-mask twin, today's code, which must break S's ledger at a
  daughter), and 2 of the cleft.
- **Their evidence is one deliberate run,** recorded at landing in `tests/tier3_record.json` (D187), which compares it
  with the last record per test ID. That holds these files' last passes: shared inventory 95 s, partition 289 s and
  insertion 383 s. Their seconds are stated at landing, and tiers 1 and 2 are re-measured.
- No test file is added.

### 6.2 Composed worlds and planted errors

- **The composed worlds** are §6.1's, each with every host check on every row. In the coupling's step, A1 in a swelling
  cell is the next: three current-volume readers beside water.
- **The plants,** each caught by name:
  - **P1:** turnover books at V₀, because its half-step drops the view. The identity's stepped entry fails.
  - **P2:** the declared masks, with a positive control on a closed slot. The closed-slot row fails.
  - **P3:** an occupant table without the leading zero, or one that keeps a retired parent's rate. The table row fails.
  - **P4:** a daughter's schedule keyed by its slot. The definition check refuses it, since §3.4 moves the founder rule
    there.
  - **P5:** a lumen at a node turnover clears, or replacement@2. The shared rule refuses it. Removing the rule must make
    the row fail.

### 6.3 Why no registration

FR-43's registered criteria (C2.3, C2.6/C2.7, C2.8) name the network and the gene unit as the writers, and their amount
ratios and plants cannot discriminate turnover. The user chose no registered criterion (Q2 a). Every turnover-specific
claim is exact or has a closed form. The one order-window claim with a limit to check is V(t), and that is water's
numerics, which C2.6 judged in the same world family.

## 7. What is not claimed

- **Other laws.** No production that scales with volume, no clearance law other than first order, no swelling-dependent
  clearance law, and no charged routes (FR-15 S1).
- **A volume changer other than water at a slot turnover reads.** A lumen is admitted only at a node turnover does not
  read. A lumen at a cleared node, and replacement@2, stay out. The reactions and the gene unit keep the same rule.
- **The division consumers' furrow world is delivered with turnover in its cells** (lumen, partition, insertion@2), with
  no turnover route at the cleft and none crossing a bridge. S's pools do not equilibrate through a bridge.
- **Other cells.** No dividing or inserting cell that also swells (M4, M2), no triggered lifecycles, and no RK4 beside
  water.
- **The other readers of §1.3.** The coupling changes in its own step. Exchange, the unit producer and the gene unit's
  masks are unchanged.
- **Labelled turnover beside insertion@1 or @2, a lumen, or any closer** (the label owner refuses them), and FR-50's
  one-way records beside a closer.
- **An energy identity at rounding in a swelling cell.** It closes at water's second order.
- **A run view of a water world** (§9.2).
- **Any biology.** The worlds are synthetic, and no consumer is registered (composition design §10). Nothing is judged.
  The composite on a GPU stays refused (D336).

## 8. Decisions and corrections

### 8.1 Decided (D375)

- **Q1 (b).** Turnover first, then the coupling's current-volume reads, so A1 in a swelling cell is admitted. The
  coupling's contract extension is designed in that step (§3.8).
- **Q2 (a).** The builder's tests, with no new registered criterion. D150's Q5 assertion flips, amended in place with
  disclosure, as on 20 November.
- **Q3 (b).** The first build also admits a lumen at nodes turnover does not read. Not now: the partition beside water
  (M4), and water's current area and masks (M2).

### 8.2 The lead's rulings on this revision

- **The lumen:** route B, the host-only hook. It changes no lumen program, so S3's and S5's judged worlds keep theirs.
- **The symport and the bath schedule beside water and turnover:** each a parse row with the argument, and one tier-3
  composed run (§3.6), since a pairing that newly parses gets one composed-world check. The seconds and the reason are
  stated for each.
- **The run view for water worlds** is not part of FR-65. It is logged in §9.2 for the water owner.
- **Q1 (b):** the coupling's contract extension is designed in its own step; §3.8 lists its inputs.
- **The readouts** of §4.2 come from the code and the bound model, so the build checks them against one saved file, and
  says so in its test.

### 8.3 Corrections to the first version

- **The occupant tables.** It said rates outside every life are zero by construction. They are not: `control_arrays` reads
  the first entry for every time before it. The tables carry explicit zeros (§3.4).
- **A rate before an onset** was admitted, as environment. D150 §5.3 refuses it at the definition, and so does this note.
- **The order after insertion** was our reading. The probes now show it as the engine's refusal (§1.1).
- **The lumen's route** (then "scoped, with a D148 proof") is now host-only (§3.5), and the price falls by 0.25.
- **What newly parses** was not listed. It is now (§3.6).
- **Run 2** also patched the coupling's class attributes. The first version said turnover's only.
- **e_round** was used without being defined. It is amendment 3's (§4.1).

## 9. Evidence, and a logged item

### 9.1 Evidence

- **The probes** are host-only: parses, structure checks, binds, and one `run_view.prepare`. Nothing was compiled or
  run. Each ran on CPU 4 under the timed cores' lock; the first waited for another holder. Each patched class attributes
  in process only, and saved nothing: turnover's in every run, and the coupling's in run 2.
  - **In `/mnt/workspaces/Cells/fr65-design-20261124/probe/`:**
    - **run 1,** `parse-probe-f8c6c326.json`, is kept. Four of its worlds failed in the probe's own fixture (a zero
      diffusivity is refused), which one line then fixed;
    - **run 2,** `parse-probe-2-f8c6c326.json`, is §1.1's rows 1–6, from the clean worktree at f8c6c326;
    - **run 3,** `declaration-probe-4f523206.json`, is §3.1's set without the anchor's end read, from the shared
      checkout, read only, at 4f523206.
      Between f8c6c326 and 4f523206 only `docs/DECISIONS.md` and `docs/FEATURE_REQUESTS.md` changed. Its only dirty
      paths are two untracked `lean/` files.
  - **In `probe2/`,** all from the clean merged worktree at 95559271:
    - **`records-probe.json`:** the saved fields of the swelling cell, and the 19 sequences newly admitted at up to three
      operators. It stops there, so it says nothing of a lumen's scope;
    - **`lumen-probe.json`:** the lumen stacks, with turnover at every position, and the furrow and cleft parses;
    - **`checks-probe.json`:** the run view's refusal, the units, and which operators parse beside water and turnover. Its
      row "bridge linear, lumen, S with one" is invalid (an identical definition was served from a composition cached
      under the lift), and is replaced by the next;
    - **`bridge-probe.log`,** one parse per process: S impermeant on the bridge parses, and S crossing it is refused.
    - **`labels-probe-2.log`,** one parse per process: labels beside insertion@1, @2 and each lumen are refused by the
      label owner. Its first run failed in the probe's own label declaration and is kept as `labels-probe.log`.
  - **In `probe3/`,** at 8ad40a72: **`companions-probe.log`,** one parse per process: water with the symport, and with the
    bath schedule, each with S and turnover, refused today and parsed under §3.1's set. `check_declarations` passed with
    the anchor's two reference reads.
- **Read:** D150's design §5; OPERATOR_COMPOSITION_DESIGN §2–§6, §14 and §16; FR43_SHARED_INVENTORIES_DESIGN §2.3, and
  FR-43 part 2's registered CRITERIA.md; FR-38 v2's amendment 3, SPEC §1.6, LAWS §4 and READOUTS §2, at tag
  `fr38-v2-amendment-3-2026-11-24`; the lumens' and the coupling's source; FR-50's registration; the rename's candidate
  mapping at ce4780d2; D301, D324, D327, D328, D334, D345 to D347, D354, D363, D365 and D375. The Lean lane's evidence on
  clearance was relayed by the user through the lead and has not been read by this author.

### 9.2 A run view for water worlds (logged apart; not part of FR-65)

- **The owner:** the water operator's. **The price:** 0.25–0.5 agent-day (S). It is not in §3.9's figures.
- **Today** `run_view.prepare` refuses a water world (§4.2): water declares no layers, axes, units or record kinds, and no
  reference for its volume increments, and it replaces a balance rate that @3 gives no axes or layer.
- **What it would give replay:** a `view.json` beside the run, with the unit, axes, kind and layer of each record, and for
  each increment the anchor it is taken over. A reader outside the engine would then form n, V and c from declarations
  rather than from the names and units in §4.2. The numbers themselves are already in `trajectory.npz`, so replay does
  not wait for it.
