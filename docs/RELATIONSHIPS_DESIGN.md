# Relationships: descent, material provenance, dependence and history as plain tables (design)

*Status: proposed, 17 November 2026, for the lead and then the user. D200 asks for a design note
with options before any building (D142). Docs only: nothing here is built. Branch
`relationships-design` from main 01bc75ec. Code is cited `file`:line at main 01bc75ec, by today's
paths under `src/cells/` (D188's move 2 has not landed). GARD's G1 family is not on main; it is
cited on branch `gard-g1` at fb652315. **S** marks this note's own derivation or proposal. Two
different things are called G1 in the record, so this note never writes G1 alone: **the results
gate** is the 113-world bitwise check, and **GARD's G1** is the assembly-lineage milestone (D192).*

**The request (D200).** The user, 17 November: "let's have a good way to track things in general so
we can create graphs from the raw data easily, for example so plug the gaps". Relationships are
four things:
- **descent:** who descends from whom;
- **material provenance:** whose material is whose;
- **dependence:** who depends on or fed whom;
- **history:** what history a state carries.

D199 found the gaps. `docs/SOTA_ORIGIN_OF_LIFE.md` asks for every descendant tracked, founder
material traced, external help visible, and resemblance, function and renewal kept apart.

**Engine models (AGENTS.md).** This note runs none. Its milestones (§7) run:
- `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with `isopotential_partition@1`,
  `membrane_entity_state@1`, `scheduled_cell_replacement@1` and `@2`, the source operators
  (`scheduled_bath_composition@1`, `scheduled_species_turnover@1`, `scheduled_species_exchange@1`,
  `local_species_reactions@1`, `electrode_current_injection@1`) and the kinds
  `cells.transporter@1` and `cells.passive_routes@1`;
- GARD's G1 family, `cells.assembly_lineages@1` with `cells.reservoir_exchange@1`,
  `cells.size_threshold_fission@1` and `cells.daughter_continuation@1`, once it lands.

## 0. The plan

**One rule (S).** A relationship is declared by the mechanism that creates it, never inferred by a
reader:
1. a birth or an end, by the operator or kernel that makes it, as one row shape (§1);
2. a move of material, by the law that moves it, as rows at named ends (the core-seams rule's
   item 2), which the core's label stage follows (§2);
3. a read, a change or a supply, by the mechanism's existing declarations, with every external
   input a named source (§3);
4. a branch or a transplant, by the tool that makes it (§4).

The core resolves these when the model is built, into value-free structure. A run writes them as
plain node and edge tables with stable string identifiers (`cells.relations@1`, §5). A lineage
tree, a material-flow graph, a dependency graph or a history of branches is then a join. Nothing
reads the tables back into a run.

**What exists, and what this note proposes:**

| | Today (findings) | Proposal (**S**) | Recommended |
| --- | --- | --- | --- |
| Descent (§1) | Three host-side lifecycle builders, no two in one shape, with no end reasons; two write `summary.json`. The run view cannot carry division or replacement worlds outside tests. GARD's G1 follows one daughter, and its keys are unique per lineage | One row shape for every birth and end, with its parent and end reason; keys unique across a world from one rule, a counter per sub-lineage, which keeps GARD's G1 keys; a population mode in which every daughter lives | D-b; P-a now, P-b with OL2 |
| Material (§2) | Nothing labels material by origin. The ledgers already book every change, by accumulator | Labels: state beside the tracked species rows, moved by one core stage from each step's booked moves, which no law sees. One mechanism with seam E's moieties | M-1; one-way where declared (O); the implicit stage (T-I); species-origin chemistry, moiety-mapped labels where declared |
| Dependence (§3) | FR-12's manifest is accepted, not built. Supplies are per-operator arrays. "Payer" exists only in the origin-of-life note | The static graph as the manifest joined with the run's composition; direct flows as edges weighted by existing records; one sources table naming every external input and the payer of every work field | All three |
| History (§4) | `cells branch` changes future inputs only. Continuity records chain admissions. GARD's G1 has a branch word. The donor copy is a same-world, tissue-only copy | A branch table with keys; tracking may start at a branch; transplants at branch points, by seam B's field roles; a state's history is its labels, its history-role fields, its descent path and its branch path | X-2 now, X-3 on a consumer's request |
| Graphs (§5) | `lineage` lists in two summaries, which would collide in one composite summary | `relations.npz` with a JSON descriptor, named by the view, written by the shared paths and by GARD's G1 writer through one function, on request | F-a |

**The standing rules hold (§6):**
- a world that declares no tracking gets identical programs: crossrev and the results gate are
  unchanged, and so are GARD's G1 programs;
- with tracking, every array the run writes without it is bitwise the same, and any label draw is
  on its own stream;
- totals are conserved per label;
- each claim is proved once, with a planted error (D187).

**Estimate (§7, S):** 23.5–35 agent-days.
- The host-side tables come first and change no program: descent and sources in about 5–6.5,
  and the static dependency graph in 1–1.5 more once FR-12's manifest exists. Its home is not
  settled (§3.1).
- Labels and the population mode need the core-seams pass's seams A, B, E and F, and GARD's G1 on
  main, so they follow the pass.
- Elapsed: about 14–21 working days after the pass, with two builders and a references agent, if
  GARD's G1 and FR-12 have landed by then.

**Questions:** seven for the user (§8.1, marked), six for the lead (§8.2).

## 1. Descent

### 1.1 What the engine writes today

| Mechanism | What it writes | Where | Missing |
| --- | --- | --- | --- |
| The partition, `isopotential_partition@1` | One record per carrier: `carrier_id`, `slot`, `kind` (founder or daughter), `parent_carrier`, `sibling`, `birth_s`, `death_s`, a `successors` list, `route`, `division`, `volume_fraction` (`models/operators/partition.py`:1139–1175) | `summary.json` under `lineage`, rebuilt on the host from the declaration, the schedule and the final `division_applied` (:1004–1034) | An end reason; generation and root; numeric keys (S5 §6.1 left them to milestone 2); the run view's declarations |
| Replacement, `scheduled_cell_replacement@1` and `@2` | One record per carrier: `carrier_id`, `slot`, a `founder` flag, `birth_s`, `death_s`, `newcomer`, `inheritance_route`, `template`, `donor`, `donor_carrier`, `predecessor`, a scalar `successor` (`core/cell_replacement_spec.py`:569–611) | `summary.json` under `lineage` (`models/operators/cell_replacement.py`:744–763), rebuilt from the schedule and the final `generation` | As above, and any view declaration |
| The secreted-species operators | Each slot's occupants: the founder, then newcomers with their kind, template and donor (`models/operators/species_common.py`:351–367) | Host only, for building controls | It is a third derivation of the same lifecycle |
| The run view | Per-slot lifetimes, and birth and retirement events, from `living_intervals` (`run_view.py`:664–669, :714, :1256–1284). An event may name `from` (:1286–1292) | `view.json` | Parents: the default events give no `from` (`models/operators/contract.py`:387–408). Carriers: the sets are slots |
| GARD's G1 (`gard-g1`, fb652315) | The fission table: time, slot, parent, both daughters, the followed one, the split, H and the partition counter; the occupant and generation per row; the event trace; discarded totals (`models/assembly_lineages/records.py`:84–246) | Its own bundle (`run.json`, `records.npz`). The view's version 1 refuses the family | Population mode (refused, `spec.py`:301–302); keys unique across a world |

**Findings:**
1. **The two tissue records are not one shape.** S5 §6.1 planned one ("carrier_id, slot, birth_s,
   death_s, predecessor and successor"). As built, they differ in the founder field, the parent
   field and the successor field. Neither states why a life ended.
2. **Both are rebuilt on the host from the schedule.** So neither can carry a state-triggered
   birth: the endogenous lifecycle's division, or any fission.
3. **They would collide in one composite.** The composite merges its operators' summaries by dict
   union (`models/pump_composite.py`:1535–1536), so of two operators writing `lineage`, one would
   be lost. Only the partition's refusal of replacement (`partition.py`:135–140) prevents it today.
4. **Division and replacement worlds have no view.**
   - On main, only three operators declare `VIEW_LAYERS` (`current_injection.py`:269,
     `species_turnover.py`:432, `species_exchange.py`:470), and only injection overrides
     `view_events` (:285).
   - The partition's and the membrane state's declarations are planted for a test's duration
     only (`tests/run_view_fixtures.py`:115–135).
   - So the writer refuses those worlds outside tests (`run_view.py`:588–592).
5. **Key uniqueness is checked per operator.**
   - The partition checks its daughters' carrier IDs against the model's cells
     (`partition.py`:484–486); replacement checks against the cells and its own events
     (`cell_replacement_spec.py`:432, :466–467). Nothing checks across operators.
   - GARD's G1 keys start at 0 in every lineage (`continuation.py`:17–19; `kernel.py`:277–279,
     :390–400). They are unique within a world only because a world is one lineage.
6. **GARD's G1 records both daughters of every fission, but follows one.** The other's life ends
   at its birth (GARD_DESIGN §5.2). The SOTA note's warning applies: "repeatedly following a
   successful daughter could obscure frequent failures elsewhere in the population".

### 1.2 One row shape (S)

Every birth and end in a world is one row of a `lives` table:

| Column | Meaning |
| --- | --- |
| `id` | The entity's stable id: `carrier:<declared carrier ID>` in the tissue family (a founder's is its cell ID), `carrier:a<key>` for an assembly |
| `key` | int64, unique across the world (§1.3), for device arrays and keyed streams |
| `slot` | The storage it occupies at birth, or none (an unfollowed daughter) |
| `parent` | The entity whose material it was made from by a split, or none: founders, template newcomers and donor copies have none |
| `predecessor` | The previous occupant of its slot, for a replacement newcomer; otherwise none |
| `birth_time`, `birth_event`, `birth_kind` | The event that made it, and how: `founder`, `division`, `template`, `copy`, `transplant`, or `continued` (alive at a branch's start, §4.1) |
| `end_time`, `end_event`, `end_reason` | `divided`, `replaced`, `extinct`, `not_followed`, `removed` (a declared bottleneck), `transplanted_out`, or `censored` (alive at the horizon or at a declared budget) |
| `generation`, `root` | Divisions since its founder, and that founder's id |

Its relations are also edges (§5.1), generated from the same rows: `parent_of` (division and
fission, weighted by the daughter's fraction or size), `precedes_in_slot` (replacement's
predecessor), `copied_from` (a donor copy: descent without material, §4.3) and `occupies` (a
carrier in a slot over its life). Each row carries its parent and its end reason, as D199 asks; the
edges carry the weights and let a graph library read the tree directly.

- **One source per mechanism.** A contract method `descent(spec, declaration, schedule, saved)`
  returns a mechanism's rows:
  - host-side from the schedule, for prescribed events (the partition, replacement);
  - from the run's saved event table, for events made on the device (GARD's G1 fission table; a
    triggered division later).
- **The old builders derive from the rows.** The two `lineage()` builders and the occupants table
  are rebuilt from them. `summary.json` keeps its `lineage` lists in their present shapes, compared
  byte for byte, so no output changes.
- **End reasons are the run's, not the reader's.** No end is inferred from a missing successor.

### 1.3 Keys unique across a world (S)

**One rule: a counter per sub-lineage.** A key is s·2³² + c, written `s:c`: a sub-lineage s and a
count c within it.
- **Founders:** founder i, in declared order, holds `i:0` and starts sub-lineage i's counter at 1.
- **At a split,** every daughter takes its key from the parent's counter, in daughter order, as
  GARD's G1 does today (`kernel.py`:390–400). A daughter that is not followed still takes its key.
- **Which daughter continues the counter:** the followed one (GARD's continuation rule), or the
  first where every daughter lives (tissue division). Each other daughter that lives on starts a
  new sub-lineage s′ for its own descendants, with its counter at s′·2³² + 1. Its own key stays the
  one its parent's counter gave it.
- **A newcomer with no parent** (a template, a transplant) holds `s′:0` in a new sub-lineage.
- **New sub-lineages are numbered in the mode's own deterministic order:** by (generation, parent
  key, daughter index) in P-a (§1.4), and by the world's event order (time, then declared order)
  in P-b and in the tissue family, where tissue keys are assigned at build.

**What follows:**
- **GARD's G1 keys are kept, bitwise.** Single-lineage mode only ever uses sub-lineage 0, whose
  counter is G1's `next_carrier` (`kernel.py`:279, :400). A sub-lineage needs no new lane field: it
  is the high word of that counter.
- **In P-a, the followed path keeps GARD's G1 keys at every depth,** because no other life draws
  on sub-lineage 0's counter. GARD's G1 streams fold both words of the key (`streams.py`'s
  docstring), so other sub-lineages draw from distinct streams.
- **Keys are unique:** the counters' ranges are disjoint, and each new sub-lineage's first entity
  holds a key from its parent's range.
- **In §5.4's tissue world:** `cell_0` holds `0:0` and `cell_1` `1:0`; division `first` gives `c1`
  `0:1` and `c2` `0:2`, and `c2` starts sub-lineage 2; the newcomer `n1` holds `3:0`.
- **A world-level check:** every declared carrier ID is unique across all operators, checked at
  build and naming both declarers. It closes finding 5.

**Qualifiers across runs (S).** An id is unique within its run. Across runs it is qualified by the
run's identity: the digest of {definition fingerprint, start}, where start is `fresh` or the parent
checkpoint's digest and time. Both are already in the run's manifest and provenance
(`io.py`:285, :319; `__main__.py`:236–251).
- **It is not GARD's G1 `world.json` id,** which names the environment that many lineages share
  (`records.py`'s `world_record`), and not the run view's `run.id`, which is a caller's label.
- **A stochastic run's fingerprint includes its stream words** (GARD's G1 `execution.stream`), so
  lineages, seeds and branch words get distinct qualifiers.
- **A branch has its own qualifier,** even with no declared difference, since its start differs.
  Its entities keep their keys, and the branch table joins them to the parent's (§4.1).
- Two runs with one qualifier are the same declared computation: replicas, not different entities.

### 1.4 Every descendant: a population mode

| Option | What it is | For | Against |
| --- | --- | --- | --- |
| **P-a Branching lives under a held phase** | Each life is a job: a lane runs it from its birth state to its fission, extinction or the horizon. Generations run in turn, and generation g+1's new sub-lineages are numbered once generation g ends (§1.3) | Exact: under a held phase, assemblies are independent between fissions (OL §5.2), and GARD's G1 streams depend on the key alone (`streams.py`'s docstring). The followed path keeps GARD's G1 keys (§1.3), so it reproduces single-lineage mode bitwise, which is the check | Growth is 2^g. A declared generation limit or entity budget applies, past which lives are `censored`, never dropped |
| **P-b A world of K slots** | One world-level SSA over K assemblies; every daughter is placed in a free slot; when full, a declared bottleneck (serial transfer) or a capacity stop | Needed for a finite shared pool (OL2's R5), where assemblies compete | It is OL2's kernel work, not this note's |
| P-c One followed lineage (today) | Unfollowed daughters end at birth, `not_followed` | Cheap; GARD's contracts | Hides failures in the rest of the population |

**Recommended: P-a with GARD's G1 follow-up, and P-b as OL2 builds it,** both writing the same
rows. P-c stays for GARD's reference contracts. Tissue division already keeps both daughters (S5's
fresh slots), so the tissue family needs no population mode.

### 1.5 Options

| Decision | Options | Recommended | Why |
| --- | --- | --- | --- |
| Descent records | D-a per-mechanism dicts, with a converter in `validation/`; D-b one contract method and one row shape; D-c a device table for every family, prescribed events included | D-b | D-a is the reconstruction D200 asks to avoid. D-c adds device state where the host already knows the schedule |
| Every descendant | P-a, P-b, P-c (§1.4) | P-a now, P-b with OL2 | Exact, and checked against single-lineage mode |
| Keys | A counter per sub-lineage (§1.3); one world counter in event order; slot and occupant number; keys derived from the parent's | A counter per sub-lineage | It keeps GARD's G1 keys, and in P-a keeps them on the followed path at every depth. One world counter shifts the followed path's keys from the third generation on, in P-a's order and in time order alike; slot-based keys need fixed slots; derived keys change GARD's G1 streams |

## 2. Material provenance: labels

### 2.1 What a label is (S)

- **A tracked quantity** is a species, or a moiety declared in the species registry as a linear
  form over species (CORE_SEAMS_DESIGN §7.3).
- **A label set** is declared on it: small and static, a capacity bucket as species are. Each
  origin of tracked material maps to exactly one label (§2.6).
- **Label content** is state. For a tracked species it is an amount per label per node,
  [label, species, node], held beside the core's species rows. Its sum over labels is the amount.
- **No law reads it.** Laws move totals; the core's label stage moves label content after them.

So founder material can be told from rebuilt material, and supplied material from inherited
material, as renewal needs (ARCHITECTURE.md, "Growth and renewal": "a lineage label alone is not
evidence of material replacement").
- **Renewal** becomes a label measure: the share of founder material in a descendant.
- **Resemblance and function** stay measures on states, in `validation/` (OL §5.1).
- The three come from different raw data, so they cannot be confused.

### 2.2 One rule: a move carries the composition of the node it leaves (S)

- **Every mover already books its moves.**
  - @3's routes accumulate per-route transfers (`membrane_transferred`, `junction_transferred`,
    `face_transferred`, `reservoir_supplied`: `models/surface_tissue.py`:30–43;
    `channel_transferred`: `models/surface_pump_v3.py`:97–100), and pump cycles with their
    stoichiometry.
  - @3 lists every mover with its entities (`surface_pump_v3.py`:2211). Kinds give their moved
    rows (`core/kind_registry.py`:193–194). Each operator books its writes in accumulators
    (`ENTITY_WRITES`).
  - The material ledgers close on exactly these terms.
- **What labels add is the ends.** Each booked term is resolved at build, through seam A's host
  table, to (species, from-node, to-node), (species, node, source) or (species, node, sink). That
  is the core-seams rule's item 2, "the rows it reads and moves, as species at a named end", read
  once more.
- **The stage** takes each term's amount over the step and moves label content in proportion to
  the composition of the node it leaves. Sources add content under their own label; sinks remove
  it in proportion.
- **Fail-closed.** A tracked species moved by a term without resolved ends is refused at build,
  naming the mover, as refusal 4 per move names a law without a step term
  (CORE_SEAMS_DESIGN §4.4).
- **Events** move content exactly at the event, before the step, with the composition at that
  moment:
  - a daughter takes its fraction of the parent's label content;
  - a removed occupant's content goes to the sink, label by label;
  - a template's supply comes in under the template's label.

### 2.3 Net or one-way: which flux a label rides

A route's net transfer is all the engine books. At equilibrium a route moves nothing net, but
molecules still cross both ways.

| Option | Rule | For | Against |
| --- | --- | --- | --- |
| N Net | Labels ride each route's net transfer | Needs only what is booked today | **A boundary at steady state exchanges no label, so founder material looks retained.** A cell in steady exchange with its bath would keep its founder K⁺ for ever. That reverses renewal conclusions |
| **O One-way** | Labels ride each route's two one-way fluxes, whose difference is the booked net | The isotope reading: what molecules do. Most laws give it directly (below) | A law must declare its one-way kernels, a new optional field of seam F's law template. A pump law written only as a net cycle rate has none |
| N+O | One-way where declared, net elsewhere, recorded per route | Never refuses | A reader must check every route's mode before a renewal claim |

**Which laws have one-way forms:**
- the cycle kind's factored form, J_m = k a S_m (1 − e^{ΔG_m/RT}): forward k a S_m, reverse
  k a S_m e^{ΔG_m/RT} (CORE_SEAMS_DESIGN §3.2). A law in that section's fallback, which supplies
  only J_m, has none;
- OL's event pairs: a⁺ and a⁻ (ORIGIN_OF_LIFE_ENGINE_DESIGN §0.1);
- linear and constant-field permeation: their two terms (Ussing's flux ratio, from memory);
- mass action: its forward and reverse terms;
- one-way already: production, clearance, driven exchange routes and events;
- one-way by nature: stochastic events.

**Why the law's own factor, and not the net alone (S).** For a single-path law, the two one-way
fluxes follow from the net and ΔG, since J⁻/J⁺ = e^{ΔG/RT} (the flux-ratio relation, from memory).
But that inversion, J⁺ = J/(1 − e^{ΔG/RT}), is 0/0 at equilibrium, which is exactly where renewal is
measured. It also fails for multi-ion single-file pores (from memory). The non-negative factor
itself (k a S_m, s θ⁺) is what seam A's contract and OL's event-pair contract already make each
law's primary output, so the new law families pay almost nothing for O.

**Recommended: O for every tracked species, fail-closed.** A tracked species moved by a law without
one-way kernels is refused at build, unless the definition names that law as net (`mode: net`).
The tables then record the mode on that route's edges (§5.1), so a renewal measure can refuse or
bound that species.

**Where the one-way parts come from (S).**
- The booked net is exact. The label stage evaluates the one-way parts from the states and node
  potentials around the step, then scales them to the net: forward ≥ max(0, net), and
  reverse = forward − net ≥ 0. The step itself is not touched (§2.4).
- **Potentials.** A neutral tracked species' one-way rates need none. For a charged one, the stage
  needs the node potentials at the step's end (the start's are the previous step's end, carried).
  Either the barrier-wrapped step returns potentials it already computes, as one more output with
  no new arithmetic, which §2.4's proof then covers (whether they are the end state's depends on the
  tableau, which RT3's probe checks); or the stage makes one capacitor solve at the end state, by
  triangular solves on the bound factor (`numerics/surface_field.py`:295–299), or with a
  refactorisation where a field input refreshes it.
- The alternative is an extra accumulator per tracked route, integrated by the step's own tableau.
  It is more accurate in stiff exchange, and it changes the step's program.
- RT3's probe compares the two on a fast cleft, and fixes the stage's quadrature, before either is
  adopted.
- The stage's cumulative one-way transfers are saved as records, so the gross exchange on each
  tracked route is a join as well.

### 2.4 The label stage in a deterministic step

**The time scheme (S).** For one tracked species, with amounts n at the step's start and n′ at its
end (from the step), at each node A and for each label L:

  n′_{A,L} (1 + Out_A/n′_A) − Σ_B In_{B→A} n′_{B,L}/n′_B = n_{A,L} + Src_{A,L}

Here Out_A is the step's outflow from A (one-way or net), In_{B→A} the part of B's outflow arriving
at A, and Src the sources' supply under their labels. Consumption by chemistry is an outflow to a
sink; species-origin production is a source.
- **It is a nonsingular M-matrix.** Each column has diagonal 1 + Out_B/n′_B, and off-diagonal
  entries summing to −Out_B/n′_B, or to less in magnitude where part of the outflow goes to a sink.
- **So, in exact arithmetic:** label content stays non-negative at any step size; it sums over
  labels to n′; and a uniform composition stays uniform.
- **One factorisation per tracked quantity per step** serves every label, with one right-hand side
  each.

| Option | For | Against |
| --- | --- | --- |
| T-E Explicit: the composition at the step's start | O(moves × labels), no solve | Non-negative only while no node's outflow in a step exceeds its content. One-way flows across a fast cleft exceed it routinely, and a failed label update cannot refuse a step without changing results |
| **T-I Implicit, as above** | Non-negative and conservative at any step; first order, like T-E | One solve per tracked quantity per step (§2.8) |
| T-H Explicit where the step's throughput allows, implicit otherwise | Cheaper on most steps | A data-dependent branch, with two error behaviours |

**Recommended: T-I.** T-H is an optimisation only if RT3's cost probe asks for it. Accuracy is
qualified against closed-form tracer solutions (§6).

**Placement: results unchanged by construction, then proved.**
- **The stage runs after the accepted step.** It reads the step's start and end states and its
  booked terms, behind `jax.lax.optimization_barrier`. The composite already compiles @3's step
  behind one (`models/pump_composite.py`:17–21; `pump_composite_adapter.py`:575–576), and its thin
  compositions were bitwise equal to their frozen models (D143).
- A refused step returns its start state, so labels do not move.
- **The proof:** the same world with and without tracking, every array common to both outputs
  bitwise equal (§6).
- **The fallback, if the compiled step does not stay bitwise:**
  1. the label stage becomes a second program per window, reading the window's saved per-step
     booked terms, so the dynamic program is compiled exactly as without tracking. It costs one
     window's terms in memory;
  2. if that fails too, labels run only on small worlds, from saved per-step terms on the host,
     and the claim is reported as failed, not narrowed.

### 2.5 Chemistry, and one mechanism with the moiety ledgers

| Option | A product's label | For | Against |
| --- | --- | --- | --- |
| C-s Species origin | The producing route's own label: new material | Says when a species was rebuilt. Needs no atom map | Says nothing about atoms |
| C-m Moiety-mapped | The labels of the moiety content its reactants gave up, in proportion | The isotope reading through reactions; pulse–chase of a moiety | Needs the moiety declared, and one unknown per label per carrying species per node |

**Recommended: both, chosen by the tracked quantity.** A tracked species takes C-s; a tracked moiety
takes C-m.

**What is shared with seam E's moiety ledgers** (CORE_SEAMS_DESIGN §7.3, agreed in D195):
- **the declaration:** a moiety is the registry's linear form w_M over species, and a label set may
  be declared on it;
- **the ledger path:** per-label ledgers go through the same `ledgers` hook, with `ledger_terms`
  and `ledger_bounds`, appended by `ledger_lists` (`surface_pump_v3.py`:1757–1767). The shared
  checks take them with no edit;
- **the one-label case:** with no labels declared, the moiety ledger is §7.3's check exactly.

**What is not shared:**
- §7.3 checks producers and needs no state: Σ_s w_M,s × each producer's cumulative production is
  held at zero;
- labels need state and the stage. With labels, the producers' check holds per label: chemistry
  moves a label's moiety content between species, and creates or destroys none of it.

### 2.6 Origins, sources and label schedules

- **Every origin maps to one declared label,** checked at build and fail-closed: an unmapped origin
  is refused, by name. The origins are the initial content of each node, each source (§3.3) and
  each producing route (§2.5).
- **Initial content:** per node by default (`founder/<node>`), or grouped.
- **Held nodes are sources and sinks, not stores.** What leaves a held bath carries the bath's
  label; what enters it leaves the system. `reservoir_supplied` is already its record.
- **Label schedules, for pulse–chase.** A source's label may change at declared times, as a
  piecewise-constant control on the step grid. Material supplied in a window is then told from
  material supplied later, which is how turnover is measured in the laboratory (from memory). No
  state is added.

### 2.7 Stochastic laws (GARD's G1 family, then OL)

- **Label counts:** integer counts per label, [label, type, slot]. The exact identity per slot
  holds per label: count = founder + joined − left − discarded.
- **A join** takes its source's label (the held reservoir's, or a schedule's). No draw.
- **A leave** takes label L with probability n_{i,L}/n_i. The draw is one uniform from a new stream
  domain, `label`, at the event's counter (`streams.py`:34–36 lists the four domains today). The
  exchange stream is untouched, so the event trace is the same with labels on or off.
- **A fission's split needs no draw (S).**
  - List each type's molecule places by label, inside the type's range. The partition's uniforms
    choose places without seeing their contents (`fission.py`), so each type's count is unchanged,
    bitwise.
  - The choice is exchangeable over places. So, given the type's count, each label's chosen places
    follow the right law: hypergeometric under `exact_fraction`, binomial under `binomial`. The
    exception is GARD's G1 tie rule, at probability about N²·2⁻⁵³.
- **OL's general reactions:** each consumed molecule's label is drawn from its pool's composition
  on the `label` stream, and the products follow §2.5's rule.

### 2.8 Cost, and where it pays nothing (S)

Per world, with L labels, S_t tracked species and P nodes (cells and non-held outside nodes):

| | Deterministic | Stochastic |
| --- | --- | --- |
| Memory | L·S_t·P floats in state and checkpoints; for a moiety, L·(carrying species)·P. At L = 4, S_t = 2, P = 64: 512 floats, 4 kB | L times the counts: L·C·K integers for C types and K slots |
| Per step or event | One evaluation of the tracked routes' one-way rates, with the end's potentials for a charged species (§2.3: an output of the step, or one capacitor solve); one P×P LU per tracked quantity, about (2/3)P³ flops; L solves, 2LP² | One uniform per leave, and O(L) to pick the label. Nothing at joins or fissions |
| For scale | @3's IMEX step already factors its node-space operator every step: 21 ms of a 91 ms one-core step on the 825-node world (ARCHITECTURE.md, D190's section). A dense LU on the same nodes takes about twice a Cholesky's flops, so one labelled species there would cost about 40 ms a step. At P = 64 it is about 2·10⁵ flops | The kernel's own work per event is O(C), for the propensities |

**It pays nothing:**
- in a world that declares no tracking: no field, no stage and no resolution, so identical programs
  (the core-seams rule: an undeclared piece is absent);
- for an untracked species in a tracked world: its terms are left out of the stage's index arrays
  at build;
- at held nodes, which hold no label state;
- at fissions and joins in the stochastic family;
- in output, beyond label records on observed rows, under the recording subset.

**Measured first.** RT3 begins with a cost probe: memory, compile time and step time on the kinds
world, S5's division world and the 825-node world, before the stage is fixed. Large worlds may need
a sparse solve; that is decided on the probe's numbers.

### 2.9 Options

| Decision | Options | Recommended | Why |
| --- | --- | --- | --- |
| The mechanism | M-1 label content as state, moved by one core stage; M-2 a species row per label; M-3 reconstruction from saved transfers | M-1 | M-2 lets laws see labels: a saturating pump or a constant-field law would treat each label as its own species, and the 16-species cap binds. M-3 needs every route's transfers at step cadence; it serves as RT7's independent check on small worlds |
| The flux (§2.3) | N, O, N+O | O, fail-closed, with a recorded `mode: net` exception | Net semantics make founder material look retained |
| The time scheme (§2.4) | T-E, T-I, T-H | T-I | Non-negative and conservative at any step |
| Chemistry (§2.5) | C-s, C-m | Both, by tracked quantity | A rebuilt species and traced atoms are different questions |

## 3. Dependence

### 3.1 Static: the manifest joined with the run's composition

- **FR-12's manifest** (`cells.declarations@1`) lists, per revision, every registered law,
  operator and kind with what it reads, writes and provides. It is accepted, not built:
  FEATURE_REQUESTS.md places it in seam F, and CORE_SEAMS_DESIGN §8.7 leaves it to module stage 1.
- **The run's own graph is its join** with what the definition resolves, all on the host:
  - the composition and its field map (`field_owners`, already in each composite run's manifest:
    `io.py`:307–308);
  - @3's movers with their entities (`surface_pump_v3.py`:2211), and the kinds' moved rows;
  - door S's slots per field (`changed_slots`, `read_slots`: `contract.py`:367–374);
  - seam A's host table, for the ends.
- **It is written as** one `mechanism` node per instance (a population's law, an operator, a kind's
  population), joined to the manifest by its ID, with `reads`, `changes` and `moves` edges to
  entities.
- **Who depends on whom** is then a two-hop join: e is read by m, and m changes e′.
- Nothing here changes a program.

### 3.2 Dynamic: who fed whom

- **Directly:** one `moves_to` edge per route and species, weighted by the route's own cumulative
  record (`weight_record`, §5.1). The material moved between two times is the difference of two
  rows: a join, with no array copied.
- **Ultimately:** label content. Its record gives, per node, how much of each origin it holds: a
  founder's material in its great-granddaughter, the bath's share of a cell's K⁺, a template's
  share of a replaced slot. These are `contains` edges from labels to nodes, weighted by the label
  record.
- **By carrier:** nodes and slots are storage. `occupies` edges say which carrier held which slot
  when, so flows by carrier are one more join.

### 3.3 Sources: supplied material names its source, as work names a payer

**Today (findings):**
- **Supplies are per-operator accumulators**, by species and entity:
  - the held bath's `reservoir_supplied` (`surface_tissue.py`:36);
  - a dose's `bath_dose_fmol` (`bath_schedule.py`:108–110);
  - turnover's production (`species_turnover.py`:79–82);
  - injection's supply (`current_injection.py`:56–58);
  - replacement's supply (`models/operators/cell_replacement.py`:83–94);
  - GARD's G1 `joined_total`.

  A reader must know each operator's field names to find them, and a template or a donor is named
  only in the schedule.
- **Work is declared per operator** (`WORK_FIELDS`, `contract.py`:216), so its owner is known. But
  no code names a payer. The word is the origin-of-life note's (its §3.2, and R8: "works by
  payer"). GARD's G1 books fission work "from an unmodelled agent" (`fission.py`:53).

**The proposal (S): one sources table, declared, for material and work alike.**
- **Each supplying mechanism declares `SOURCES`:** per accumulator, the source's kind (held bath,
  chemostat or reservoir, dose, template, electrode, feeder, transplant, production route,
  schedule), its class, the entity it acts at, the species it carries, and the payer of any work it
  books. It is host-side, read only by the writer.
- **Four classes,** as the SOTA note asks to "separate supplied substrates, energy, assembled
  machinery, and externally imposed interventions": `substrate`, `energy`, `machinery` and
  `intervention`.
- **Every `WORK_FIELDS` entry names its payer,** a source id. Where a law set's honest answer is "an
  unmodelled agent" (GARD's G1 fission), the source says so. OL's engine names the shear or the
  schedule instead (its §3.2).
- **External help is then a join:** `supplies` edges from sources, weighted by their accumulators,
  and label content where the species is tracked.
- **Fail-closed:** the writer refuses a supplying accumulator without a declared source, as it
  refuses an operator without `VIEW_LAYERS` (`run_view.py`:588–592).

### 3.4 Options

| Decision | Options | Recommended | Why |
| --- | --- | --- | --- |
| Static graph | (a) the manifest joined with the run's composition; (b) a per-run dump of declarations | (a) | FR-12 is the one declarations format; the join adds only the run's entities |
| Sources | (a) declared per mechanism; (b) a table of field names in the writer | (a) | D142: a new operator brings its sources with it |
| Feeder material (SpudCell-like) | (a) a source of class `machinery` on a scheduled supply operator; (b) a transplant | (a) when the supply repeats; (b) for one prepared component (§4.3) | Both are external help, named |

## 4. History

### 4.1 Branches

**Today:**
- `cells branch snapshot config` continues a saved world with changed future inputs
  (`__main__.py`:55–57).
- The model, the execution and the past schedule must be unchanged (`core/runner.py`:111–135).
- The run's provenance records the parent snapshot, the parent definition and the branch time
  (`__main__.py`:236–251). Batches branch per world (`core/batch.py`:274–290).
- Continuity records chain admissions across source changes (`continuity.py`), not branches.
- GARD's G1 folds a branch word into every stream (`streams.py`:37–45).
- There is no branch id, no table of branches, and no statement that entities continue.

**Proposed (S):**
- **A branch record,** in the run's provenance and the relations tables: a branch id; its parent
  run and checkpoint; the time and step; the branch key (the stream word, for stochastic families);
  and the declared difference, as the definition's diff.
- **Entities continue.** Those alive at the branch time keep their ids and keys, with `birth_kind`
  `continued`, and the world counter continues. So a branch with no difference continues bitwise,
  which is the check (§6).
- **The history of branches is a table:** `branched_into` edges between worlds.

### 4.2 Tracking started at a branch (D153)

- **Label content is checkpointed state.** A checkpoint written without tracking cannot resume with
  it: the definition differs, which D153's case 3 refuses.
- **Proposed:** a branch may add a `tracking` block, beyond the future inputs it may change today,
  with its initial labels declared at the branch: per node (`at_branch/<node>`), or one label. The
  dynamic fields continue bitwise, checked against the same branch without tracking.
- **What it gives:** pulse–chase on a prepared state, without re-preparing it (ARCHITECTURE.md, "no
  silent equilibration on resume or branch").
- **Where the block lives:** a top-level `tracking` block, beside `model`, `experiment` and
  `execution`. The parser's top-level fields (`core/specs.py`:967) gain it as optional. It is in
  the fingerprint and changes no physics. **A definition without it is today's, byte for byte, and
  so is its fingerprint.**
- **What must change for a branch to add it.** `branch_checkpoint`'s check of model and execution
  (`runner.py`:117–122) already passes a new top-level block. The checkpoint does not: its state
  gains the label fields, built from the initial labels declared at the branch time, and
  `validate_checkpoint` must accept that one extension. That is the lead's question (§8.2).
- A branch never crosses a source change: that stays D153's admission.

### 4.3 Transplants

**Is the donor copy general? No: it is a tissue-only, same-world copy** (findings).
- **It is replacement's event map over @3's state.** The newcomer takes the donor's amounts and its
  channel gates by law. The donor keeps its contents, so material is created and booked as supply
  (`models/operators/cell_replacement.py`:7–14; `core/cell_replacement_spec.py`:31–39).
- **The donor must match the slot:** a shared junction, the same volume and fixed charge, and one
  population per gated law.
- **It is refused where it would not be a copy:**
  - by the secreted-species operators, unless route values match (`species_common.py`:524–557);
  - for compartment owners (`compartments.py`:372–385);
  - at site slots (`site_occupancy.py`:474–487);
  - and the partition refuses replacement altogether (`partition.py`:135–140).
- **It is scheduled on the host, within one world,** and has no counterpart in the stochastic
  family.

| Option | What it is | For | Against |
| --- | --- | --- | --- |
| X-1 Extend the donor copy | More fields copied, more families | Reuse | A copy inside one tissue world: lineages in different worlds never meet |
| **X-2 A transplant at a branch point** | A branch whose start state takes a declared component of entity X, from any checkpoint of the same world or another, into entity Y. A component is defined by seam B's field roles: extensive fields move, intensive fields copy, history-role fields stay with their entity, and structural fields must match or are refused | Swaps between lineages, which are separate worlds. The SOTA note's arms ("the relevant inherited carrier; no carrier; a carrier from a different history; a disrupted carrier") are branches. One tool for every family | It is D153's "new run started from imported state, recorded and judged on its own", so the tool joins D153's list of exempt tools |
| X-3 A transplant event within one world | A scheduled move of a component between two entities of one world | No material created; labels move with it | One world only; on a consumer's request |

**Recommended: X-2 now, X-3 on request.**
- **Bookings:** the recipient's replaced content goes to a sink. The inserted content comes from a
  source `transplant/<world>/<entity>/<time>` of class `intervention`, since worlds are independent
  and the material is created in the recipient's world.
- **Labels:** the inserted content takes the transplant's label by default. A declared option
  keeps the donor's label composition, where both worlds share a label set.
- **Descent:** a `transplanted_into` edge between world-qualified ids, so material provenance and
  descent stay distinct (ARCHITECTURE.md's rule, §2.1).

### 4.4 What history a state carries

In a deterministic world, equal complete states have equal futures. SCIENTIFIC_BASIS.md: a history
effect "must reside in complete state, parameters, structure, or environment". So two present
states matched in their dynamic fields differ in their pasts only through records that cannot act:
1. **labels,** which no law reads (§2);
2. **history-role fields,** seam B's role: cycles, transfers, heat, work and supply records;
3. **the descent path** (§1) and **the branch path** (§4.1).

**Proposed (S):**
- **A static check at registration** that no law, kind or operator reads a history-role field. Then
  "matched in dynamic fields" is well defined: the comparison set is every field without the
  history role.
- **If two matched states have different futures,** the difference lies in a dynamic field the
  match left out. That is the experiment's finding, and the field roles name the candidates.
- **The engine gives** the roles, the labels and the tables. The matching, its tolerance and the
  attribution are analysis, in `validation/`.

## 5. Graphs from the raw data: `cells.relations@1`

### 5.1 The tables

One NPZ file of columns (`relations.npz`) and its JSON descriptor (`relations.json`, format
`cells.relations@1`), per run, and per world in a batch.
- Ids are strings, unique within a world. Every table carries a `world` column.
- Strings are fixed-width Unicode arrays, so nothing is pickled.

| Table | Key | Columns |
| --- | --- | --- |
| `nodes` | `id` | `kind` (world, carrier, slot, node, patch, junction, face, population, mechanism, source, sink, label), `declared_by` |
| `lives` | `id` | §1.2's columns |
| `events` | `id` | `time`, `step`, `kind`, `at`, `by` (a mechanism), `source` (its payer or supplier), `scheduled` |
| `edges` | row | `relation`, `from`, `to`, `event`, `time_from`, `time_to`, `species`, `weight`, `weight_record`, `weight_index`, `mode` (`event`, `one_way` or `net`), `declared_by` |
| `sources` | `id` | `kind`, `class`, `at`, `carries`, `record`, `payer_of`, `declared_by` |
| `labels` | `id` | `quantity` (a species or a moiety), `origins`, `chemistry` (`species` or `moiety`) |

**The relations** (the `relation` column):
- descent: `parent_of`, `precedes_in_slot`, `copied_from`, `occupies`;
- material: `supplies`, `removes_to`, `moves_to`, `contains`;
- dependence: `reads`, `changes`, `moves`;
- history: `branched_into`, `transplanted_into`.

**Rules of the edges:**
- **Weights point at records.** A flow edge names its record (`junction_transferred`) and the
  column, so a graph at any time is the edges joined with that record's row. No array is copied:
  the run view's rule that arrays stay in the run's files.
- **An edge's direction** is its record's positive direction, as the run view's orientation states
  it.
- **Material sits where it is stored:** in a slot or node while a carrier occupies it, in the
  carrier itself when it has none (an unfollowed daughter).
- **`mode`** says which flux a material edge's labels rode (§2.3).

### 5.2 Where they live

- **Named by the view.** The view gains a `relations` block naming the file, its tables and the
  vocabulary, as `records` name arrays. That is GARD_DESIGN §5.3's items 1–2 in general form:
  events from the run, and event tables as arrays, with JSON events kept for scheduled
  interventions.
- **One generator for events.** The view's JSON events are the table's scheduled rows, generated
  together and checked equal.
- **Sets stay storage.** The view's sets are slots. `occupies` edges give their occupants, so a
  viewer colours slots by carrier or lineage without inferring either.
- **Record kinds are unchanged.** Label content is an `amount` record with a `label` axis (a new
  set, `labels`). Per-label ledger residuals are diagnostics. Edge weights point at existing
  `cumulative` and `amount` records.
- **No new output path.** One function in a new module, `records/relations.py`, is called by the
  four shared paths that write views today (`io.write_run`, `window_io.write_windowed_run`,
  `batch_io.write_batch_run`, `batch_window_io.write_windowed_batch`) and by GARD's G1 bundle
  writer (`records.py`'s `write_run`). The view's version 1 still refuses GARD's family, but its
  tables do not wait for that: their descriptor describes them.
- **Opt-in.** The tables are written on request (`relations=`, like `view=`), before the manifest,
  so its checksums cover them. Without the request every path writes exactly what it wrote before.
  So the results gate, which compares the union of array names, is unaffected (RUN_VIEW_DESIGN §9).
- **Deterministic bytes:** sorted rows, no host paths, no timestamps.

### 5.3 Worked example: a GARD lineage

GARD's G1 in single-lineage mode: one world `w`, the founder at key 0, two fissions at nominal times
t₁ and t₂, the first daughter followed each time. Labels `founder` and `reservoir` on every type.

`lives`:

| id | key | slot | parent | birth_time | birth_kind | end_time | end_reason | generation | root |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| carrier:a0 | 0:0 | 0 | — | 0 | founder | t₁ | divided | 0 | carrier:a0 |
| carrier:a1 | 0:1 | 0 | carrier:a0 | t₁ | division | t₂ | divided | 1 | carrier:a0 |
| carrier:a2 | 0:2 | — | carrier:a0 | t₁ | division | t₁ | not_followed | 1 | carrier:a0 |
| carrier:a3 | 0:3 | 0 | carrier:a1 | t₂ | division | t_end | censored | 2 | carrier:a0 |
| carrier:a4 | 0:4 | — | carrier:a1 | t₂ | division | t₂ | not_followed | 2 | carrier:a0 |

The keys are GARD's G1's own, 0 to 4: single-lineage mode uses sub-lineage 0 only (§1.3).

`events`: `f1` at t₁ (`fission`, at `carrier:a0`, by `cells.size_threshold_fission@1`, source
`source:unmodelled_agent`, the payer of `fission_work_kT`), and `f2` at t₂ likewise.

`edges` (a selection; type `t017` stands for any type):

| relation | from | to | event | species | weight | weight_record | mode |
| --- | --- | --- | --- | --- | --- | --- | --- |
| parent_of | carrier:a0 | carrier:a1 | f1 | | N₁/N | | event |
| parent_of | carrier:a0 | carrier:a2 | f1 | | N₂/N | | event |
| parent_of | carrier:a1 | carrier:a3 | f2 | | … | | event |
| parent_of | carrier:a1 | carrier:a4 | f2 | | … | | event |
| occupies | carrier:a1 | slot:0 | f1 | | | | |
| supplies | source:reservoir | slot:0 | | t017 | | joined_total[:, 17, 0] | one_way |
| removes_to | carrier:a2 | sink:discard | f1 | t017 | | discarded_total[:, 17, 0] | event |
| contains | label:founder | slot:0 | | t017 | | label_counts[:, founder, 17, 0] | |

- **In population mode (P-a),** `a2` and `a4` get slots and lives of their own, ending `divided`,
  `extinct` or `censored`. `a2` starts sub-lineage 1 and `a4` sub-lineage 2, so `a2`'s daughters
  hold `1:1` and `1:2`, while the followed path keeps `0:5`, `0:6`, … as in single-lineage mode.
- **The lineage tree** is `edges[relation == "parent_of"]`. **The founder's share in the living
  assembly** is the `contains` edges at the last row. **What the reservoir supplied** is the
  `supplies` edges.

### 5.4 Worked example: a tissue with a division and a replacement

**Admissible today only as two worlds.** The partition refuses replacement in one composition
(`partition.py`:135–140), and composing them needs S5 §5.5's three extensions. The tables show the
target shape for one world. Each mechanism's rows are the ones its `descent` and `SOURCES` would
write in its own world today.

**The world:** S5's partition fixture with its neighbour (`tests/partition_fixtures.py`):
- `cell_0` with its bath `bath_0`, and the neighbour `cell_1` with `bath_1`, joined by the junction
  `contact`;
- division `first` at 0.002 s puts carriers `c1` and `c2` into slots `d1` and `d2`;
- a replacement at 0.003 s puts a newcomer `n1`, from template `T1`, into slot `cell_1`;
- tracked: K⁺, with labels `founder/cell_0`, `founder/cell_1`, `bath` and `template/T1`.

`lives`:

| id | key | slot | parent | predecessor | birth_time | birth_kind | end_time | end_reason | generation | root |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| carrier:cell_0 | 0:0 | cell_0 | — | — | 0 | founder | 0.002 | divided | 0 | carrier:cell_0 |
| carrier:cell_1 | 1:0 | cell_1 | — | — | 0 | founder | 0.003 | replaced | 0 | carrier:cell_1 |
| carrier:c1 | 0:1 | d1 | carrier:cell_0 | — | 0.002 | division | 0.004 | censored | 1 | carrier:cell_0 |
| carrier:c2 | 0:2 | d2 | carrier:cell_0 | — | 0.002 | division | 0.004 | censored | 1 | carrier:cell_0 |
| carrier:n1 | 3:0 | cell_1 | — | carrier:cell_1 | 0.003 | template | 0.004 | censored | 0 | carrier:n1 |

`c2` starts sub-lineage 2 for its own daughters, and `n1`, which has no parent, starts sub-lineage
3 (§1.3).

`events` (the fixture's dt is 1 ms):
- `first`: 0.002 s, step 2, `division`, at `carrier:cell_0`, by `isopotential_partition@1`, source
  `source:schedule/partition_events` (the payer of `partition_work_pJ`);
- `r1`: 0.003 s, step 3, `replacement`, at `slot:cell_1`, by `scheduled_cell_replacement@1`, source
  `source:template/T1`.

`edges` (a selection):

| relation | from | to | event | species | weight | weight_record | mode |
| --- | --- | --- | --- | --- | --- | --- | --- |
| parent_of | carrier:cell_0 | carrier:c1 | first | | f | | event |
| parent_of | carrier:cell_0 | carrier:c2 | first | | 1 − f | | event |
| precedes_in_slot | carrier:cell_1 | carrier:n1 | r1 | | | | |
| occupies | carrier:c1 | slot:d1 | first | | | | |
| removes_to | slot:cell_1 | sink:waste | r1 | K | | replacement_removed_fmol[K, cell_1] | event |
| supplies | source:template/T1 | slot:cell_1 | r1 | K | | replacement_supplied_fmol[K, cell_1] | event |
| supplies | source:bath_0 | node:bath_0 | | K | | reservoir_supplied[K, bath_0] | one_way |
| moves_to | node:bath_0 | slot:cell_0 | | K | | membrane_transferred[K, membrane_0] | one_way |
| moves_to | slot:cell_0 | slot:cell_1 | | K | | junction_transferred[K, contact] | one_way |
| contains | label:founder/cell_0 | slot:d1 | | K | | label_content[:, founder/cell_0, K, d1] | |
| reads | mechanism:junction/contact | slot:cell_0 | | | | | |

**What the joins answer:**
- **The lineage:** `c1` and `c2` descend from `cell_0`. `n1` replaced `cell_1` but descends from
  nobody (its `root` is itself): the replacement made a carrier, not a descendant.
- **Renewal:** the share of `founder/cell_0` K⁺ still in `d1` at the end, under one-way semantics,
  from the `contains` edges.
- **External help:** the template's supply at `r1` and the bath's supply over the run, by source
  class.

### 5.5 Graphs as joins

- **A lineage tree:** `edges[relation == "parent_of"]`, with `lives` for the times. With pandas and
  networkx it is one `from_pandas_edgelist` call.
- **A material-flow graph over [t_a, t_b]:** the `moves_to`, `supplies` and `removes_to` edges,
  each weighted by its record's row at t_b less its row at t_a.
- **Who fed whom, ultimately:** the `contains` edges at a row, joined with `labels` for their
  origins.
- **A dependency graph:** the `reads`, `changes` and `moves` edges, joined with FR-12's manifest on
  the mechanism's law ID.
- **A history of branches:** the `branched_into` edges, with the branch records.
- **Across a campaign:** the same tables from many worlds, concatenated, with ids qualified by
  world.

## 6. The standing rules and verification (D187)

- Each claim is proved once, at the cheapest level that can prove it, with a planted error it must
  catch, and one composed-world check per composition claim.
- Each landed milestone adds one world to crossrev's kinds set and to the results baseline (D187
  rule 2).
- RT7's references are written by a fresh agent who has read neither the engine nor this note's
  derivations.

| Claim | Cheapest proof | Planted error |
| --- | --- | --- |
| No tracking declared: identical programs | crossrev's program identity on every set, and GARD's G1 programs | A registered tracking piece that adds a field to a world that declares none |
| With tracking, events and results unchanged | The same world with and without tracking, every common array bitwise: a kinds world, S5's division world, a replacement world, GARD's G1 single lineage with its event trace | A stage that writes back into an amount; a label draw taken from the exchange stream |
| Totals conserved per label; label content sums to the amounts | The per-label ledgers and the sum check on every checked row, at the material ledger's bounds | A booked term dropped from the stage; a source booked to the wrong label |
| The transport rule is right | The stage against closed-form tracer solutions: two-node exchange at equilibrium (one-way), turnover with production and clearance, a pulse–chase; non-negativity at throughput far above content | The destination's composition used for a move; net semantics on an equilibrium route, where the founder share must fail to fall; T-E at high throughput, which must go negative |
| Stochastic labels are right | Exact enumeration on a small assembly: the label marginals at equilibrium, and the split's law per label given the type counts | Places ordered by label before type, which changes type counts; a label draw that sees the propensities |
| One descent shape; keys unique across a world | Host-side: the partition's, replacement's and GARD's G1 rows pass one schema; every non-founder has one birth edge, and every ended life a reason | A key duplicated across two operators; a missing end reason; a child born before its parent ends |
| Every descendant | Lives = founders + daughters; the followed path of a P-a run equals single-lineage mode bitwise | A dropped unfollowed daughter; keys taken out of order |
| Graphs are joins | The tree from `parent_of` equals the partition's and GARD's G1's own records; each flow edge's weight equals its record | A wrong parent; a weight pointing at the wrong column |
| Branches and transplants | A branch with no difference continues bitwise; a transplant closes every ledger with its sink and source | A branch that restarts a counter; a transplant that copies a history-role field |
| Sources and dependence | Every supplying accumulator has a source; the dependency edges equal the declarations, resolved | An accumulator without a source, which must be refused; a door S slot left out |

## 7. Milestones, estimate and order

Agent-days are this note's estimate (**S**). The owners are step 0's (CORE_SEAMS_STEP0 §4.2), during
the pass.

| Milestone | Content | Engine models it runs | Needs | Files (owner during the pass) | Agent-days |
| --- | --- | --- | --- | --- | --- |
| **RT0 Desk** | The user's ruling. Interface reservations handed to the pass's owners: the law template's moves and one-way kernels (F owner); tracked quantities beside moieties (binding owner); `descent` and `SOURCES` in the contract (operators owner) | None (design) | This note | Reservations only | 0.5–1 |
| **RT1 Descent and the tables** | `records/relations.py` (new): the schema, the writer and its checks. `descent` in the contract, the partition and replacement, with the occupants from it; the summaries' lineage lists rebuilt byte for byte. The partition's, membrane state's and replacement's view declarations into source. `relations=` on the four shared paths | The composite with the partition and the membrane state; with replacement @1 and @2 | RT0 | The new module and `cell_replacement*.py` (no owner); `contract.py`, `partition.py`, `membrane_state.py` (operators owner); `run_view.py` (@3 owner) | 3.5–4.5 |
| **RT2a Sources** | `SOURCES` and payers on every supplying operator and @3's held baths; flow and supply edges | The composite with the source operators and both kinds | RT1 | The operators' files (several owners); `surface_pump_v3.py` (@3 owner) | 1.5–2 |
| **RT2b Dependence** | The mechanisms and their edges, from FR-12's manifest joined with the run's composition | As RT2a | RT2a; FR-12's manifest, whose home is not settled (§3.1) | The new module only | 1–1.5 |
| **RT3 Labels, deterministic** | The cost probe first. Tracked quantities and labels in the registry. The move table for @3's routes, the kinds and the operators. One-way kernels for the laws of the first worlds. The stage, its barrier and its fallback; per-label ledgers; records and checkpoints | As RT2a | The pass's seams A, B, E and F; RT2a | `species_registry.py`, `surface_pump_v3.py`, `pump_composite*.py`, `kind_registry.py`, the laws | 6.5–10 |
| **RT4 Labels, stochastic** | Label counts; the `label` domain; joins, leaves and the split; continuation and sinks; GARD's G1 writer | GARD's G1 family | GARD's G1 on main | GARD's G1 family files | 2–3 |
| **RT5 Every descendant** | P-a's generation sweep; the key rule; lives with their reasons; budgets | GARD's G1 family | RT4 | GARD's G1 family files | 3–4.5 |
| **RT6a Branches and transplants** | Branch records, qualifiers and keys on the shared paths and in GARD's G1; X-2 with its bookings and descent; the history-read check | Both families | RT1, RT5 | `runner.py`, `__main__.py`, the shared paths, a new transplant tool | 2.5–3.5 |
| **RT6b Labels across branches** | Tracking added at a branch (§4.2); a transplant's labels | Both families | RT3, RT6a | The same files, and the checkpoint's validation | 0.5–1 |
| **RT7 References** | Tracer closed forms and a small-graph tracer solve (numpy, scipy); exact enumeration for stochastic labels; M-3's reconstruction on small worlds | Compared with RT3's and RT4's runs of the models above | RT0's ruling | `validation/relationships/` (new) | 1.5–2.5 |
| **Gates** | At each merge, with §6's composed-world checks | All | Each | The lead's | 1–1.5 |
| **Total** | | | | | **23.5–35** |

**The order:**
- **Now:** RT0. Each reservation costs its owner about a quarter of a day if made before the file's
  pass work freezes. After the pass, each is a second edit of the same file.
- **During the pass:** RT1's new module and replacement's files, which no pass owner holds; RT7,
  once the user rules.
- **After the pass:** RT1's parts in the operators owner's and the @3 owner's files, then RT2a and
  RT3, and RT2b once FR-12's manifest exists. The operators owner is the pass's critical path
  (step 0 §4.2: done by day 13.25–18), so RT1 adds nothing to its load during the pass.
- **After GARD's G1 lands:** RT4, RT5 and RT6a, on its files and the shared paths, in parallel with
  RT3. RT6a needs only RT1's edits to the shared paths, which come first.
- **Last:** RT6b, after RT3 and RT6a.
- **Elapsed (S):** about 14–21 working days after the pass, with two builders on disjoint files and
  the references agent: three agents within seven.
  - The deterministic lane is the critical path: RT1, RT2a, RT2b, RT3, RT6b and the final gates,
    14–20.5.
  - The stochastic lane, RT4, RT5 and RT6a, takes 7.5–11 beside it.
  - It assumes GARD's G1 and FR-12's manifest have landed when the pass ends.

**Partners:**
- **Seam B** gives the field roles that labels (extensive), transplants (what moves, what stays)
  and history (the history role) all read.
- **Seam A** gives the host table: each route's ends.
- **Seam E** gives the moieties: §2.5's one mechanism.
- **Seam F and FR-12** give the law template (moves at named ends, one-way kernels) and the
  manifest (§3.1).
- **OL** consumes the stochastic labels, every descendant and named payers. Its R8 ("works by
  payer") is §3.3.

**What it replaces elsewhere (S):** the two `lineage()` builders and the occupants table (RT1); the
run-view declarations planted in tests (RT1); OL's R8, apart from its geometry and pool records.
RT6a builds on GARD's G1 branching rather than repeating it.

## 8. Questions

### 8.1 For the user (marked)

1. **U1, scope.** The whole design (RT0–RT7, about 23.5–35 agent-days)? Or the host-side tables
   first (RT1 and RT2a, about 5–6.5, with RT2b's dependency graph 1–1.5 more once FR-12's manifest
   exists), with labels decided after?
2. **U2, which flux a label rides** (§2.3). One-way for every tracked species, fail-closed, with
   `mode: net` recorded where a law has no one-way form (recommended)? Net semantics would make
   founder material look retained at steady state.
3. **U3, chemistry** (§2.5). Species origin for tracked species, and moiety-mapped labels for
   tracked moieties (recommended)?
4. **U4, every descendant** (§1.4). Branching lives under a held phase now, with GARD's G1
   follow-up, and the K-slot world with OL2 (recommended)?
5. **U5, transplants** (§4.3). At branch points, between any two checkpoints, recorded as new runs
   from imported state (D153), with seam B's roles defining a component (recommended)?
6. **U6, the format** (§5). NPZ columns and a JSON descriptor, with no new dependency
   (recommended)? Or Parquet, which needs pyarrow?
7. **U7, opt-in.** Tables written only on request, like the view, so existing outputs and the
   results gate are unchanged (recommended)?

### 8.2 For the lead

1. **RT0's reservations:** hand them to the F, binding and operators owners now, or wait for the
   pass to end?
2. **Tracking added at a branch** (§4.2): may a branch's checkpoint gain the label fields, built
   from initial labels declared at the branch, with `validate_checkpoint` accepting that one
   extension? And does a top-level `tracking` block suit the definition's structure?
3. **D153's exempt tools:** the transplant tool joins the list (§4.3).
4. **GARD's G1:** the `label` stream domain, P-a and the key rule, agreed with GARD's G1 owner
   before its channel layout freezes.
5. **`summary.json`:** do its `lineage` lists stay in their present shapes, rebuilt from the rows,
   or retire later in a D187 batch?
6. **The run view's owner:** the `relations` block and the `labels` set in RUN_VIEW_DESIGN, after
   seam G's items.

## Sources

- **Engine documents read:** AGENTS.md; DECISIONS.md (D142, D144, D153, D154, D185, D187, D190,
  D192, D195–D200); ARCHITECTURE.md; CORE_SEAMS_DESIGN.md (§0–§2, §4, §7, §8, §9, §13, §14) and
  CORE_SEAMS_STEP0.md (§4.2); FEATURE_REQUESTS.md (FR-12); RUN_VIEW_DESIGN.md and
  LOOPING_REPLAY_DESIGN.md; GARD_DESIGN.md (§1, §5, §7); ORIGIN_OF_LIFE_ENGINE_DESIGN.md (§0–§6,
  §8, §10); SOTA_ORIGIN_OF_LIFE.md; CELL_DIVISION_S5_DESIGN.md (§5.5, §6); E07_V1_DESIGN.md (§1,
  §4); SCIENTIFIC_BASIS.md (its operational distinctions); INNER_MODEL_V4_DESIGN.md §7.4 (k).
- **Code read** at main 01bc75ec: the files cited above. GARD's G1 at `gard-g1` fb652315:
  `models/assembly_lineages/{records,streams,continuation,fission,kernel,spec}.py`.
- **Cited from memory, not read for this note:** Ussing's flux ratio, for one-way fluxes through a
  membrane, and the flux-ratio relation for a single path in general; its failure for multi-ion
  single-file pores (Hodgkin and Keynes); pulse–chase labelling, as the laboratory's measure of
  turnover. No text, figure or data is used.
- No web search was made and no external file was fetched.
