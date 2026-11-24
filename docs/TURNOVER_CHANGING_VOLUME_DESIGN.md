# FR-65: turnover beside a changing volume (design)

**Status: proposed, 24 November 2026.** This is a design note; nothing in it is built. It was written on branch
`fr65-design` from main f8c6c326, for the lead and the user (FR-65, high, part of FR-43; D365). FR-65 is D301's
composition M3, and D150's planned version 1.1 for turnover (SECRETED_SPECIES_TRANSPORT_DESIGN §5.1, §5.3 and §5.5).

**Engine models:** `resolved_pump_composite@1` over `resolved_pump_tissue@3`. `scheduled_species_turnover@1` sits
beside `ideal_osmosis_linear_compliance_water@1`, `isopotential_partition@1`, `scheduled_membrane_insertion@1` and
`@2`, and `neutral_arrival_labels@1`. A1 (Q1) adds `templated_polymerisation@1` and
`species_regulated_availability@2`.

**S** marks our own reading or derivation. The probes ran on the host only: nothing was compiled or run (§9).

## In short

- **Who refuses.** Turnover's fixed reads alone stand between it and water, the partition, and insertion@2 (§1.1).
  The same holds for insertion@1 where turnover acts in cells only. The fixed reads are the shared
  `species_common.CONFLICTS_VIEW`: both volumes and three masks. Lifted in process, each pair passes every definition
  check. Two more things are behind them:
  - the occupant rule knows only replacement@1's carriers, so a daughter's routes cannot be keyed by the partition's
    carriers;
  - **A1 in a swelling cell is refused by two operators:** turnover, and the coupling operator
    (`species_regulated_availability@2`), which reads c = n/V at the declared volume. We read D334's and D347's "A1"
    as this world (Q1).
- **The recommendation is option A, as in FR-43 part 2B:** the same law ID, turnover's own read declarations, and
  C1's fallback.
  - The volumes are read current at the split. The masks are read current at the split and from the declared
    layout for existence. The outside anchors are a reference read, kept true by a guard that refuses insertion@1
    where turnover clears at a node.
  - Water is the one volume changer admitted, through part 2B's shared rule moved into `species_common`.
  - The occupant rule works through a contract hook, so the partition's daughters are carriers with their own rates
    (D150 §5.2).
- **Why it is cheap.** No state, layout, control or ledger term is added.
  - Turnover's update n′ = n e^(−kh) + P g reads no volume, so its amounts stay exact. Only its work booking reads
    the volume.
  - At the view's volume that booking is the composite's exact free-energy change. So the composed energy identity
    carries water's second order, and adds nothing of turnover's.
- **The cost:** about 2.25–3 agent-days, and no references are needed. A1 in a swelling cell adds 2–2.5 (Q1); a
  judged status adds about 1 (Q2).
- **Three questions** (§8): A1's second refusal; judged or tested; and how much of the dividing, inserting cell to
  cover (the lumen, M4, M2).

## 1. What reads the declared volume or masks today, and why

### 1.1 The refusals, in the engine's words

This is the probe's run 2, at f8c6c326 (§9). "Lifted" means turnover's fixed reads were replaced in process by
current reads at the split, with reference reads at the end for the masks, under the same law ID.

| World | Today | Lifted |
| --- | --- | --- |
| FR-43 2B's swelling cell, with S produced and cleared in the cell | "scheduled_species_turnover@1 reads volume as declared, but ideal_osmosis_linear_compliance_water@1 provides it", and the same for `extracellular_volume` | Parses |
| A1 in a swelling cell: the gene unit, turnover of X, and the coupling's Hill factor on initiation | Turnover's two refusals, plus "species_regulated_availability@2 reads volume as declared, but ideal_osmosis_linear_compliance_water@1 provides it", and the same for `extracellular_volume` | Still refused by the coupling's two. It parses once the coupling's declarations are lifted too, but that program is unexercised: the coupling's code still reads `p.volume` |
| S5's division (`partition_fixtures.divided`): S produced at the parent and at each daughter, daughters keyed by their slots | "reads active as declared, but isopotential_partition@1 closes it", and the same for `membrane_active` | Parses |
| The same, with daughters keyed by their carriers c1 and c2 | "route p1 needs a schedule for its founder carrier d1" | The same refusal, from the occupant rule |
| The cleft cell's furrow, S cleared at the cleft, beside insertion@1 | "reads outside_active as declared, but scheduled_membrane_insertion@1 provides it", and the same for `membrane_active` | Parses |
| The same beside insertion@2 | "… scheduled_membrane_insertion@2 closes it", and the same for `membrane_active` | Parses |

- **Parsing runs every definition check** (`pump_composite_spec`, line 225). So nothing else in the engine refuses
  these pairs.
- **What the lift was.** Four fields were made current reads, unscoped, and no anchor read was declared. They were set
  as class attributes after registration, so the contract's `check_declarations` never saw them. Run 3 (§9) puts
  §3.1's exact set through `check_declarations` and the parse.
- **The probed insertion@1 world clears at the cleft.** §3.1's anchor guard would refuse that world. Run 3 also
  parses insertion@1 with a cell route only, the case the guard admits.
- **The slot-keyed admission hides a hazard.** A positive rate keyed to slot d1 from t = 0 applies before d1 is born.
  With today's declared mask it writes into the pending slot. The partition's overwrite then breaks S's ledger at d1,
  by −2.0e-12 fmol (OPERATOR_COMPOSITION_DESIGN §2.3, L4).

### 1.2 Turnover's read sites

The sites are in `src/cells/operators/species_turnover.py`. OPERATOR_COMPOSITION_DESIGN §3 has the same table, at
3c10b833.

| Field | Read site | What it assumes | Kind |
| --- | --- | --- | --- |
| `volume` | `_node_update`'s work and magnitude: `species_chemical_free_energy_pJ` and `species_chemical_magnitude_pJ` at `p.volume` (lines 299–300, 333) | The booked work is ΔF at the declared volume | Real, but for the booking only. The update reads no volume |
| `extracellular_volume` | The same at finite outside nodes (line 345) | The same | Real at a finite node that water changes |
| `active` | `touched` in `_node_update` (`p.active`, line 334) | Rates act on closed cells: a pending daughter or a retired parent | Real |
| | `turnover_domain_valid`: zero where no owner, and positivity (lines 458–470) | Slot existence | Reference |
| `outside_active` | `finite = p.outside_active & ~p.reservoir` (line 341) | Clearance acts on a closed onset node | Real |
| | The domain (line 462) | Slot existence | Reference |
| `membrane_active` | Never read; it is only on the shared list | — | Nominal (the matrix's tag) |
| `extracellular_amount_reference` | `p.extracellular_amount_reference[rows]` (line 344), **undeclared** | An open finite node holds its declared anchor | Latent, but true today. Closers pad closed nodes only. Insertion@1 provides the declared anchor at open nodes. The bath schedule doses held baths, where turnover has no route |
| Occupants (host) | `species_common.occupants` and `route_tables`. Each cell is its own founder from t = 0, followed by replacement@1's newcomers, which are found by law ID | A slot's carrier is its cell from the start | Real beside the partition |

### 1.3 The other declared readers in these worlds

| Operator | Fixed reads | Why | Under FR-65 |
| --- | --- | --- | --- |
| `species_regulated_availability@1`, `@2` (the coupling) | The shared list | Its factors read c = n/V at the declared volume (D244, Q2), at the control view and in its targets' half-steps | Unchanged (Q1) |
| `scheduled_species_exchange@1` | The shared list | Uptake reads c = n/V | Unchanged |
| `population_unit_turnover@1` | The shared list | It requires membrane state, which water refuses. Division and insertion are refused world-wide (D232) | Unchanged |
| `templated_polymerisation@1` | The masks | Its chains, hold and machines have no division or onset rule. Its volumes have been current since part 2B, so its degradations already run in a swelling cell (FR-38 v2's family D) | Unchanged |
| `local_species_reactions@1` | The masks and the outside anchors | Closers, and insertion@1 | Unchanged |
| `isopotential_partition@1` | `volume` | The daughters' volumes are declared anchors (M4) | So turnover with water and the partition together stays refused |
| `ideal_osmosis_linear_compliance_water@1` | `membrane_area` | Its conductances are bound from the declared areas. Its undeclared mask reads (gap 5) land with this change (M2) | So turnover with water and insertion together stays refused |

The compartments declaration, trafficking, the wash, replacement@1 and injection keep their reads, and so do the
integer population's volumes. None of them meets FR-65's worlds.

## 2. The prior art

- **FR-43 part 2B** (FR43_SHARED_INVENTORIES_DESIGN §2.3; D324). The reactions and the gene unit read both volumes
  current at the split, with a view passed only where water changes them (C1's fallback), and their masks still
  fixed. `check_volume_changers` admits water alone. C2.7's endpoint identity converged at a ratio of 4.006.
- **FR-38 v2's family D.** The gene unit's first-order degradations run in the same swelling cell, with labels, and
  read V only through their bookings, as turnover does. Amendment 3 judges their energy identity as a stepped entry
  at p = 2.
- **`integer_unit_population@1`** reads the patch mask and the outside anchors current at the split, and selects a
  closed site idle.
- **Lifetimes through the contract.** Insertion@2 (`lifetimes`) and the integer population (`lives`) read every
  operator's `living_intervals`, never importing the operator that decides them.

## 3. Options and the recommendation

### 3.1 How turnover reads, stage by stage

**Option A (recommended): the same law ID, with its own declarations.**
- It meets the composition design's test (§4.4): no new state, entity write or ledger term, and the same expression
  at another volume.
- Turnover takes its own tuples, as the gene unit did. The shared list stays as it is, because exchange, the coupling
  and the unit producer read it.

| Field | Read | Where it is used |
| --- | --- | --- |
| `volume` | Current at the split | The work and magnitude of each half-step |
| `extracellular_volume` | Current at the split, scoped to its outside route nodes (`read_slots`) | The same at finite nodes |
| `active` | Current at the split; reference at the end (C3) | `touched`; the domain's existence and positivity |
| `outside_active` | Current at the split; reference at the end | `finite`; the domain |
| `membrane_active` | Dropped | Never read |
| `extracellular_amount_reference` | Reference at the split, unscoped (scope does not apply to a reference read), with the guard below | n = anchor + increment at open finite nodes |

- **The half-step** takes `view=None`.
  - With a view, its volumes and masks come from the view and are held over the half-step. Without one, today's code
    runs.
  - Cell anchors (`amount_reference`) stay on the declared layout. They are not a view field, and close() changes
    them only on closed slots, where turnover now writes nothing.
- **It has no event part, and its observed columns are its own accumulators.** So it reads nothing at the event or
  at observation.
- **The order follows C2.**
  - Turnover is declared after water, as the reactions are.
  - It is declared after insertion@1 or @2, whose undeclared mask changes also count at their split. This is our
    reading of M1's text (OPERATOR_COMPOSITION_DESIGN §17), not a refusal the probes saw (S).
  - The partition closes at its event, so turnover sees it in the same step in any order.
- **Run 3 of the probe checks this set** (§9). The contract's `check_declarations` passes it. With it, water, the partition and
  insertion@2 at the cleft parse, and so does insertion@1 with a cell route. The guard is not yet written, so it is
  not exercised.
- **Option B,** `scheduled_species_turnover@2`, is rejected. It would be a new law, unqualified on every world, with
  its own crossrev and matrix rows, for no change in accounting (composition design §4.2–4.3).
- **A lagged read**, at the step's start, would make the coupling first order. Today's fixed read is an O(1) error
  (composition design §6).

**The outside anchors.** There are three ways to declare the read.
- **(i) A reference read with a guard (recommended).**
  - It states what the code reads and constrains no changer, so no admitted world's program moves.
  - The guard keeps it true. Turnover's definition check refuses a provider of `extracellular_amount_reference`
    whose change reaches one of its outside route nodes; an unscoped change reaches every node.
  - The bath schedule is scoped to held baths, so it never meets the guard.
  - Insertion@1 is unscoped. It is refused where turnover clears at a node, and admitted where turnover acts in cells
    only. Admitting it at a node would need insertion@1 to declare its anchor change as padding, a change to
    insertion@1 that is not proposed here.
  - The composite already refuses an anchor provider beside a closer.
- **(ii) A current read.** Turnover would become a view reader beside every bath schedule. That changes the program
  of a pair that never meets, because the composite's view readers ignore slots.
- **(iii) A fixed read, as the reactions have.** It would be refused beside insertion@2, by M1's rule on closures that
  reach the field.

### 3.2 Concentrations, rates and the ledgers

- **Rates** are amounts per time: P in fmol/s and k in 1/s, a per-cell source and a per-molecule hazard. Neither
  depends on V, so the current volume leaves them, and the exact update, unchanged.
- **Amounts** follow the closed form at every dt, to rounding, on a row that turnover alone writes.
- **Concentrations** are water's readout columns, n/V at the row's current volume (`osmotic_water.observe`).
  Turnover owns no concentration column.
- **The material ledgers** are unchanged.
  - Produced is P h and cleared is n f + P (h − g), both gross and in amounts.
  - At a division the partition books its moves of each increment.
  - Turnover never writes a closed slot, so a daughter's increment is still 0 when the partition writes it (§3.4).
- **The energy ledger** (S).
  - Each half-step books F(n′, V) − F(n, V) at the view's volume V.
  - The composite's stored free energy is @3's chemical term at V₀ plus water's dilution term −RT N ln(V/V₀), which
    equals F(N, V) (FR43_SHARED_INVENTORIES_DESIGN §2.3).
  - So turnover's booking is the exact change of that stored energy, to rounding: 3e-17 pJ or less in the
    composition probe.
  - The identity's step error then comes from water's Heun heat and bath work alone, which are second order.
  - Booked at V₀, each move would miss −RT Δn ln(V/V₀). That is an O(1) error, which no dt reduces: 4.8e-7 pJ per
    0.01 fmol at the probe's state.
- **Water's bookings** are unchanged. Turnover's production and clearance change the osmolyte count, so V couples to
  turnover through water's Π. The palindrome W(h) T(h) I(dt) T(h) W(h) is second order for the coupled system
  (composition design §6).

### 3.3 Composition

- **Water:** cells and finite outside nodes, through the view.
  - Water is the one volume changer admitted.
  - `check_volume_changers` and `row_volumes` move from `species_reactions` into `species_common`, as one rule for all
    three readers. Turnover cannot import `species_reactions`, which imports from it.
- **The partition, at fixed volume.**
  - Closed cells are idle by the current mask, and carriers come from the occupant hook (§3.4).
  - Turnover's per-slot accumulators need no division rule. The parent's stay on its retired slot as its history, and
    each daughter's start from zero at birth.
- **Insertion@2, at fixed volume.**
  - A closed onset node is idle until its onset. From then on it is cleared from its declared content.
  - Outside routes are environment (D150 §5.2). So a rate in force before the onset is admitted, and acts from the
    onset.
- **Insertion@1** is admitted where turnover acts in cells only (§3.1's guard).
- **Labels (FR-42).** Turnover reports its one-way moves from its amounts: production into the arrival label, and
  clearance out of every label at its share. So labels beside water carry over unchanged, as FR-38's family D's do.
- **Cohorts.** A window's labelled material decays as e^(−k(t − s)), whatever V does. Its concentration dilutes with
  V.
- **FR-50.** Turnover's produced and cleared are already its one-way records. They are amounts, so the current volume
  leaves them exact. FR-50's route records are @3's, read at @3's view. FR-65 adds no record.
- **The other writers of a row** keep today's rules (§3.6).

### 3.4 The occupant rule for the partition's carriers

Today each slot's carriers are built from replacement@1's events, which `occupants` finds by law ID. The partition's
daughters are invisible to it. D150 §5.2 has already ruled that "Daughters of an S5 partition are new carriers with
their own declared rates".

- **A host hook in the contract,** `slot_occupants(spec, declaration, schedule)`, with the default `{}`.
  - It gives the slots an operator fills, each with its carriers as `species_common.Occupant` records (carrier, birth,
    death, kind, template, donor).
  - Replacement@1 and the partition implement it; the partition builds its records from its `lineage`.
  - `species_common.occupants` merges them over the founders, and refuses a slot that two operators fill.
  - No module imports the operator that decides: the J2 line, as in insertion@2's `lifetimes`.
- **Rates outside every life are zero by construction.**
  - A daughter's schedule, keyed by its carrier, starts at its birth.
  - A retired parent's table ends with a zero.
  - So for cells the composition design's living-interval refusal follows from the occupant rule.
- **The founder rule moves from parse to the definition, where the occupants are known.** Today `parse_schedules`
  holds it ("needs a schedule for its founder carrier", "starts at time 0").
- **Its other readers get the same tables:** exchange, sites, labels and the reactions. Without a partition the tables
  are bitwise today's. Beside a partition, each of those readers stays refused by its own reads.
- **Triggered lifecycles,** whose births are unknown at the definition, would write their rates into state at birth
  (D150 §5.2). They are not part of FR-65.

### 3.5 Restart and checkpoints

- No state, layout or control field is added.
- The reader view is a function of the state.
- The occupant tables are per-world control data, recomputed from the definition at a restart (R7), now with the
  partition's carriers.

So a resume is bitwise by construction. Rows check it in the swelling cell, across a division and across an onset
(§6).

### 3.6 Which refusals lift, and which stay

| Composition | After FR-65 |
| --- | --- |
| Turnover beside water | Admitted, with water declared first |
| Turnover beside the partition | Admitted, with daughters keyed by their carriers |
| Turnover beside insertion@2 | Admitted |
| Turnover beside insertion@1 | Admitted with cell routes. Refused by the anchor guard where turnover clears at a node |
| A lumen or replacement@2 beside turnover | Refused by name (`check_volume_changers`), even where turnover acts in cells only. So the division consumers' furrow world, insertion@2 with lumen@2 (composition design §2.5), stays refused: FR-65's onset worlds are lumen-free (Q3) |
| Water with the partition, or with insertion | Refused by the partition's and water's own reads (M4, M2) |
| A1 in a swelling cell, and any routed turnover rate beside water | Refused by the coupling's reads (Q1) |
| Charged routes, held baths, and D152 or the gene unit on the same row | Refused, as today |
| RK4 beside water | Refused by the engine: split-only parts cannot sit beside water's coupled part |
| Labels beside a closer | Refused by the label owner |

### 3.7 What changes, and the cost

| Item | Files (owner) | Agent-days |
| --- | --- | --- |
| Turnover's declarations, `read_slots`, the half-step's view and the anchor guard | `species_turnover.py`, `species_common.py` (operators) | 0.5–0.75 |
| The shared volume rule moved, with its two callers updated | `species_common.py`, `species_reactions.py`, and one import in `templated_polymerisation.py` (the gene-regulation lane's file) | 0.25 |
| The occupant hook and tables, and the founder rule moved | `contract.py`, `cell_replacement.py`, `partition.py`, `species_common.py` | 0.75–1 |
| The tests, the regenerated matrix, Q5's split and the D148 evidence | tests, `composition_matrix.py`, `PUMP_COMPOSITE.md`, D150's §5.5 | 0.75–1 |
| **In all** | | **2.25–3** |

**Pre-alpha, so no backwards compatibility.** The moved helpers leave no alias. `occupants`' lookup of replacement@1
by law ID goes when the hook lands; `replacement_of` stays for its other callers.

**D148.**
- **By construction:**
  - every world without a changer of turnover's read fields keeps its program, because no view is passed;
  - without a lifecycle operator other than replacement@1, the occupant tables are bitwise today's.
- **The evidence at landing:**
  - a jaxpr-text pair check of turnover's admitted worlds: turnover alone, and beside replacement@1, the bath
    schedule, exchange, labels, the coupling (FR-6's A5'') and FR-1's C6 compartment;
  - crossrev's sets, and G1 at 113 of 113;
  - the control arrays of every crossrev world whose operators read `occupants`.

**Q5 flips.** D150's registered Q5 runs `test_version_1_refuses_volume_providers_area_providers_and_mask_providers`.
- Its turnover-beside-water case becomes an admission.
- Its insertion@1 case stays refused, now by the anchor guard.
- The composition design's §16.1 rule applies, with its 20 November precedent:
  - the case is amended in place and disclosed;
  - the admission is tested outside Q5's list;
  - the verdict judged at f7f0592 stands within its static-tissue scope.

**Fast.**
- The cost is two scoped reader views per step, elementwise (C4). The composition design's estimate is under 1–2%
  (§11); it is not measured.
- One development timing of the swelling world against its V₀ twin runs on the timed cores, under their lock. It is
  reported with the landing and is not a gate.

## 4. Readout classes

FR-38's amendment 3 taught the split. An identity that a writer books exactly closes at rounding. One that integrates
water's dynamics carries water's second order.

| Class | Identity or readout | Bound |
| --- | --- | --- |
| **Exact** | Worlds without a changer of turnover's read fields: program and records | Bitwise |
| | A closed slot (a pending daughter, a retired parent, a closed onset node): its rows' increments and turnover's fields there, at every step while it is closed | Bitwise |
| | Zero rates: the start state | Bitwise |
| | Labels on and off: the physical rows | Bitwise |
| | A resume against the unbroken run | Bitwise |
| **Rounding** | Turnover's amounts against the closed form n(t) = P/k + (n₀ − P/k) e^(−k(t − t₀)), per carrier from its birth and per node from its onset | The bookings' rounding over the steps taken |
| | Water's concentration columns against n/V | 4 ε |
| | The material ledgers, and the partition's moves at a division | Their own allowances |
| | Each half-step's work against F(n′, V) − F(n, V) at the view's V, and against @3's term at V₀ plus the change of water's `node_free_energy_pJ` | 1e-11 relative (Decimal, the test of record) |
| | A cohort's labelled amount against its closed form | Rounding |
| **Order window, p = 2** | V(t), and every quantity that integrates it: water's heat, the bath's water work, and turnover's cumulative work | FR-43's C2.6 form: the ratio of the errors against an in-test reference at 2h and at h lies in [3.6, 4.4], with its 1e-8 floor |
| | The endpoint identity F(N_t, V_t) + U(V_t) − F(N₀, V₀) − U(V₀) − (W − H), with turnover's, water's and the bath's terms | Amendment 3's stepped entry, with e_ref = 0 (below) |

**The stepped entry.**
- d₁ = max |r_2h − r_h| and d₂ = max |r_4h − r_2h|, from runs at h, 2h and 4h.
- est = max(d₁/3, d₂/12).
- **Pass** if max |r_h| ≤ 3 est + e_round.
- **The order:** where d₁ and d₂ both exceed 10 e_round, q = log₂(d₂/d₁) must lie in [1.5, 3.5]. Otherwise the run is
  inconclusive.

**The V₀ plant shows in energy only.** Turnover's amounts never read V, so an amount ratio or a "miss in amounts"
plant (C2.6, C2.8) cannot discriminate it.
- **The miss is on the net move.** The work is booked on the moved amount, produced less cleared. So a V₀ booking
  misses RT ∫ (P − k n) ln(V/V₀) dt.
- **The plant world is sized first.** That miss must be at least 100 times the correct run's identity residual at h
  (C2.7's rule). It is set in development, before the rows land.
- **The world stays far from steady state while V moves.** Near n = P/k the net move, and with it the plant's miss,
  vanishes. Production alone, or a pool far below P/k, keeps it large.
- **The run-time ledger is not relied on.** The operator's own guard statement says the shared energy bound is blind
  to these bookings at µM to nM. Whether the ledger refuses the plant is reported.

## 5. IDs under the planned rename

- **No new ID or major** (option A). Turnover keeps `scheduled_species_turnover@1`. The rename's candidate mapping
  (read-only, at ce4780d2, in `/mnt/workspaces/Cells/rename-design-20261124/`) maps it to
  `cells.operator.scheduled_species_turnover@1`.
- **Its partners there** take the same form, `cells.operator.<name>@major`: water, the partition, insertion@1 and @2,
  the labels, the coupling and the gene unit. The rename's note settles the final keys.
- **Step IDs are not in the candidate mapping:** turnover's `exact_production_clearance_half_steps@1` and water's
  `heun_frozen_amount_water@1`. They are the rename note's to place; this note picks no family.
- **We recommend to the lead that the build start from main after the rename lands.** Its code, refusal messages and
  test rows would then use the new keys, and nothing would wait for a re-merge.

## 6. The qualification plan

### 6.1 Each claim and its cheapest proof

| Claim | Proof | Where (tier) |
| --- | --- | --- |
| The booking at the view's volume is the exact ΔF, and the exact change of the composite's stored energy | The NumPy half-step, given a reader view with V ≠ V₀: its work against Decimal ΔF at V, and against @3's term at V₀ plus water's node term. Its amounts are bitwise the viewless call's | A row of `test_booked_work_is_the_exact_free_energy_change` (1) |
| Nothing writes a closed slot | The NumPy half-step, given a view that closes a cell and a node, with positive rates there: the rows and fields there stay bitwise unchanged, and the declared-mask plant writes there | A row of `test_zero_rates_select_the_start_state_and_untouched_entries_stay_bitwise` (1) |
| Admissions and refusals | Parse rows. Water, the partition, insertion@2 at a node and insertion@1 with cell routes only are admitted. The lumen, replacement@2, insertion@1 at a node and the slot-keyed daughter are refused, with their reasons | Rows beside `test_definition_refusals` (1) |
| The occupant tables | Host rows. A daughter's controls are zero before its birth and its own after. The parent's are zero after retirement. Without a partition the tables are bitwise today's. A planted table that keeps the parent's rate is caught | `test_species_turnover.py` (1) |
| The swelling cell | Three rungs (4h, 2h, h) of FR-43's swelling cell. S is produced strongly enough to move V, and stays far below P/k while V moves (§4). The checks: the amounts against the closed form, the concentrations, V against the in-test reference, the identity's stepped entry, the V₀ plant, and a resume mid-run, in process and through a written snapshot | Rows of `test_shared_inventory_volume.py` (3) |
| The division | S5's division world with turnover, keyed by carriers: closed slots bitwise, the closed forms from birth, every ledger, and a resume before, at and after the division | A turnover fixture beside `division_run`, used by `test_partition_runs.py`'s closure and restart tests (3) |
| The onset | The cleft cell with insertion@2 and clearance at the cleft: idle before the onset, the closed form after it, and a resume across the onset. S's face diffusivity is set so low that its transport stays below rounding over the run, since a positive value is required | A turnover fixture beside `cleft_run`, used by `test_membrane_insertion_runs.py`'s closure and restart tests (3) |
| Labels beside water | The swelling cell's h rung, labelled: its physical rows bitwise, and a production window's cohort against its closed form | One row beside the swelling rows (3) |
| D148 | §3.7's pair check, crossrev and G1 | The landing's gate |

**The in-test reference for V(t)** runs on the host. It integrates the scalar ODE dV/dt = −Q(V, N(t)), with N(t)
taken from turnover's closed form, together with the quadratures of water's heat, the bath's water work and turnover's
work, at a tolerance far below the engine's error. It is development evidence and not code-blind.

**Cost (D224).**
- **Tier 1:** every item is a row, NumPy or parse only, a few seconds in all. These rows are the routine guard.
- **Tier 3:** the compiled items are rows and fixtures in three existing files:
  - about 6 runs of the swelling cell (3 rungs, the plant, the resume and the labelled rung);
  - one fixture each beside `division_run` and `cleft_run`.
- **Their evidence is one deliberate run, recorded at landing.** The three tier-3 files have no recorded outcome at
  the 90 s cap. Their seconds are stated at landing, and tiers 1–3 are re-measured.
- No test file is added.

### 6.2 Composed worlds and planted errors

- **The composed worlds** are §6.1's three, each with every host check on every row. If Q1 is (b), A1 in a swelling
  cell is the fourth: three current-volume readers beside water.
- **The plants,** each caught by name:
  - **P1:** turnover books at V₀, because its half-step drops the view. The identity's stepped entry fails.
  - **P2:** the declared masks, with a positive control on a closed slot. The closed-slot row fails.
  - **P3:** an occupant table that keeps a retired parent's rate. The table row fails.
  - **P4:** a daughter's schedule keyed by its slot. The definition check refuses it, since §3.4 moves the founder
    rule there.

### 6.3 Is a registration needed?

**FR-43's registered criteria do not cover FR-65.** C2.3, C2.6/C2.7 and C2.8 name the network and the gene unit as
the writers. Their amount ratios and amount plants cannot discriminate turnover. So judged status needs a
registration (Q2).

**The engine's own rows can carry most of it.** Every turnover-specific claim is exact or has a closed form. The one
order-window claim with a limit to check is V(t), and that is water's numerics, which C2.6 judged in the same world
family.

## 7. What is not claimed

- **Other laws.** No production that scales with volume, no clearance law other than first order, and no charged
  routes (FR-15 S1).
- **A volume changer other than water.** The lumens and replacement@2 stay out until a probe covers their
  free-energy terms for an outside booking. The reactions and the gene unit wait for the same probe. So the furrow
  world with its lumen is not delivered.
- **Other cells.** No dividing or inserting cell that also swells (M4, M2), no triggered lifecycles, and no RK4
  beside water.
- **The other readers of §1.3.** The coupling, exchange, the unit producer and the gene unit's masks are unchanged.
  The coupling changes only if Q1 is (b).
- **Labelled turnover beside a closer.**
- **An energy identity at rounding in a swelling cell.** It closes at water's second order.
- **Any biology.** The worlds are synthetic, and no consumer is registered (composition design §10). Nothing is judged
  unless Q2 is (b). The composite on a GPU stays refused (D336).

## 8. Questions for the user

**Q1. A1 in a swelling cell is refused by two operators.** We read D334's and D347's "A1" as this world. The coupling
operator reads c_X = n_X/V at the declared volume. Its factor on a target's half-step receives the state only, with no
view (`pump_composite._routed_control`).
- **(a) FR-65 as logged, turnover only.** A1 in a swelling cell, and any routed rate beside water, stay refused by the
  coupling, by name.
- **(b) Recommended: FR-65 in two steps.**
  - First, turnover (§3).
  - Then the coupling's current-volume reads, at two points:
    - at the control view, where R2 already passes a view;
    - in its targets' half-steps. That needs a small contract extension: the composite passes a rate-route source its
      reader view there.
  - Each step lands with its own D148 proof; FR-6's A5'' is judged.
  - A1 in a swelling cell is then the composed check of three readers.
  - It adds about 2–2.5 agent-days.
- **(c) The coupling as a separate request,** later.

**Q2. Judged, or tested.**
- **(a) Recommended: the builder's rows of §6, with no registration.** Every turnover-specific claim is exact or has a
  closed form.
- **(b) One criterion, C2.9, added to FR-43 part 2's registration before any engine run.**
  - The world is the swelling cell with turnover.
  - It is judged by §4's two order-window forms and by the V₀ plant in energy.
  - The code-blind references are extended to a zero-order source and a first-order sink.
  - It adds about 1 agent-day.
- **(c) A registration for FR-65 alone,** with its own judge.

**Q3. How much of the dividing, inserting cell FR-65 covers.**
- **(a) Recommended: pairwise and lumen-free now.** M4 (the partition over water, 3–4 agent-days) and M2 (water's
  current area and masks, 2–2.5) wait for a consumer, and turnover needs no further change for them. The lumen waits
  too.
- **(b) Also a lumen at a node turnover does not read.**
  - The lumen declares its volume change scoped to its own nodes, and the shared volume rule becomes per slot.
  - The division consumers' furrow world then carries turnover in its cells.
  - It needs the lumen owner's file and a D148 proof for the lumen's judged worlds. About 1–1.5 agent-days (S).
- **(c)** Add M4, with or without (b).
- **(d)** Add both M4 and M2.

## 9. Evidence

- **The probes:** `/mnt/workspaces/Cells/fr65-design-20261124/probe/`. Each ran on the host only, parsing and
  checking definitions, with nothing compiled or run. Each ran on CPU 4 under the timed cores' lock; the first waited
  for another holder. Each patched turnover's class attributes in process only, and saved nothing.
  - **Run 1,** `parse-probe-f8c6c326.json`, is kept. Its four division and insertion worlds failed in the probe's own
    fixture, not in the engine: a zero diffusivity is refused. One line of `fr65_parse_probe.py` was then changed, to a
    positive diffusivity.
  - **Run 2,** `parse-probe-2-f8c6c326.json`, is §1.1's table. It ran from this branch's worktree at the clean main
    f8c6c326.
  - **Run 3,** `fr65_declaration_probe.py` and `declaration-probe-4f523206.json`, is §3.1's set. It ran from the shared
    checkout at 4f523206, two commits after f8c6c326 that change no source. Its only dirty paths are two untracked
    `lean/` files.
- **Read:**
  - D150's design §5;
  - OPERATOR_COMPOSITION_DESIGN §2–§6, §14 and §16;
  - FR43_SHARED_INVENTORIES_DESIGN §2.3, and FR-43 part 2's registered CRITERIA.md;
  - FR-38 v2's amendment 3, SPEC §1.6, LAWS §4 and READOUTS §2, at tag `fr38-v2-amendment-3-2026-11-24`;
  - the rename's candidate mapping at ce4780d2;
  - D301, D324, D328, D334, D345 to D347, D354, D363 and D365.
