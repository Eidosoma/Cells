# Liquid routing: a liquid exchange routed into a node (FR-54 and FR-57), design note

**Status: a design, written 24 November 2026 at main 05826ec1 on branch `fr54-57-design`. It was
revised the same day with the user's decisions (Q1 and Q3) and the coordinator's rulings on the rest
(§10). Nothing is built.** Integration would grant no acceptance (D143). **S** marks this note's own
reading, derivation or proposal. The desk sketches cited are decimal and NumPy arithmetic on the
note's reading of the code, not engine runs; each is measured before any tag (§8.2).

**The requests** ([FEATURE_REQUESTS.md](FEATURE_REQUESTS.md)), both high priority (the user; D341 for
FR-54):
- **FR-54:** passive neutral diffusion between two finite liquid regions, checked against the exact
  two-well solution; a stopped run that reports its numbers; then a wash at a diffusion-connected
  node.
- **FR-57:** a passive tracer carried by a prescribed liquid flow between finite regions, with its
  free-energy check and the growing collector of 24 November (D352).

**The shared idea** (FR-57's first reading): one mechanism, D246's liquid exchange, with the sample
routed into a node or a record and the supply drawn from a node or a declared inlet.

**Engine models it runs:**
- `resolved_pump_composite@1` over `resolved_pump_tissue@3`;
- @3's faces (`logmean_electrodiffusion@1`) under the default face heat and `exact_free_energy_heat@1`;
- the new operator `liquid_routing@1` (§3.1), beside `neutral_arrival_labels@1` and `site_occupancy@1`;
- the solvers ARS(2,2,2) (`imex_ars222_face_electromigration@1`) and IMEX Euler.

**Read for it:**
- FR-27, FR-37, FR-44, FR-45, FR-54 and FR-57; D246, D263, D280, D327, D349 and D352;
- [COMPARTMENT_WASH_DESIGN.md](COMPARTMENT_WASH_DESIGN.md), [NEUTRAL_LABELS_DESIGN.md](NEUTRAL_LABELS_DESIGN.md)
  §13, [CORE_SEAMS_DESIGN.md](CORE_SEAMS_DESIGN.md) §6.5 and [BATH_SCHEDULE_DESIGN.md](BATH_SCHEDULE_DESIGN.md) §3.2;
- the code: `operators/wash_schedule.py`, `contract.py` and `species_labels.py`; `numerics/label_shares.py`
  and `ideal_mixing.py`; `restricted_lumen.fill_energy`; `models/surface_pump_v3.py` (the IMEX step and
  `exact_face_heat`); `surface_pump.checked_rows`; `execution/vector_windows.py` and `energy_check.py`;
- the FR-44/45 design note (`/mnt/workspaces/Cells/fr44-45-design-20261123/DESIGN.md`).

## 0. Summary

| | |
| --- | --- |
| **Today** | The wash exchanges a node's liquid with a buffer, and its sample goes to a record (D246). No operator moves one region's liquid into another. A face at a washed node is refused (D246 item 5), and a stopped energy check names no numbers |
| **The mechanism** | One definition: well-mixed liquid moved between holders (inlets, finite nodes, records). A wash is two moves at an instant; a flow is moves at prescribed rates (§2) |
| **Decided** | One new operator, `liquid_routing@1`. Its event part moves portions at declared times. Its split part runs prescribed flows by the exact step of the declared network. It takes over the wash after a bitwise check (§3.1). Its collector is a record that a later landing can open as a node (§3.2) |
| **Exact to rounding** | The flow's trajectory at any step; volume and every solute; each portion's free energy and mixing heat; a step's total heat, which equals the state-function balance because flows end in collectors; labels |
| **Carrying an order** | How a step's heat is split among the holders (first order in the step); flow beside diffusion (Strang splitting, second order); @3's face transfer (the tableau's polynomial) and its default heat (third order per step, at resolved levels only) |
| **FR-54** | A two-well harness on @3's faces against closed forms (§4.1). A stopped run reports its residual and bound (§4.2). The wash at a faced node, admitted for one neutral species once measured (§4.3) |
| **Decisions** | Made on 24 November: Q1 and Q3 by the user, the rest by the coordinator (§10) |

## 1. What exists

- **The wash** (`scheduled_compartment_wash@1`). This is an event map at the start of the step leaving t.
  - Each species becomes (1 − f) n + f V c_buf, at constant volume.
  - Its records are cumulative, with the latest event's values as level records:
    `wash_last_sample_fmol`, `wash_last_supply_fmol` and `wash_last_mixing_heat_pJ`.
  - H_mix is computed in φ form and is never a ledger remainder (D246 ruling 3).
  - Its energy terms are records without a heat suffix, so they sit outside the IMEX flow bound.
  - Ions are `same_as_compartment`.
- **FR-44's report.** The event with `labels=` returns `(state, valid, LiquidExchange(removed, supplied))`,
  read from the two level records.
  - The owner maps each label to (n − r) s_k + a [k = 0] (`label_shares.exchange`). The buffer joins the
    base label.
  - What leaves goes to `label_outside_removed_fmol`.
  - The report's axis is the outside nodes.
- **@3's faces.**
  - **The flux.** A neutral face's flux is the log-mean times the log ratio, which is D A/L (c₁ − c₂) to
    rounding.
  - **The step.** It moves in the explicit stages only. The implicit electromigration is z-weighted and
    carries none of it.
  - **The default heat** is dt RT J̄²/W, with J̄ the step's applied face flux and W the log-mean weight at
    the predicted midpoint (the step start under IMEX Euler).
  - **`exact_free_energy_heat@1`** (D280) books the exact release from divided-difference potentials. Its
    scope is neutral rows at finite nodes that faces alone move.
- **The free energy.** @3's chemical term is F(n, V) = 10⁻³ RT n (ln(n/V) − 1) pJ, with n in fmol, V in pL
  and c = n/V in mM (a 1 mM standard state).
  - The −n term is the ideal −ΠV part.
  - F is homogeneous of degree 1 in (n, V), so a portion's F is its volume fraction of its source's F.
  - The lumen's fill (`restricted_lumen.fill_energy`) books liquid added to a growing volume. Its work is
    W = Σ μ_b dn − Π_b dV, and its heat H = RT Σ c′[V φ(c/c′) + dV φ(c_b/c′)] ≥ 0. That is the collector's
    form (§3.2).
- **The refusals.**
  - D246 item 5 refuses a face at a washed node.
  - D263's `surface_crossings` refuses every declared path across a washed node's surface, failing
    closed.
- **A stopped run.**
  - `surface_pump.checked_rows` raises "Resolved pump accounting failed: energy" with no numbers. The
    composite's own-ledger loop (`pump_composite.check_values`) does the same.
  - The vector windows and the projective bursts build their message from `device_failure_message`, which
    gives the check's name and time only.
  - The step-doubled check (`execution/energy_check.py`) already reports |C| and its allowance. It is the
    precedent.

## 2. The mechanism (S)

**Holders.**

| Holder | What it is | Its state |
| --- | --- | --- |
| Inlet | A declared liquid: a concentration for every neutral species, piecewise constant on the grid, unlimited | What it supplied: amounts, volume and F |
| Node | A finite outside node of @3, well mixed, at constant volume in version 1 | @3's amounts |
| Sink | Unpooled portions leaving the world (the wash's samples). Portion events only in version 1 (§3.4) | The amounts and F it took |
| Collector | One pooled liquid leaving the world: a record that starts at zero volume (§3.2) | Its amounts, volume and F, and its pooling heat |

**Links** are directed liquid connections: inlet to node, node to node, node to a sink (by portion events
only) or collector, and inlet to collector. Records only receive, and inlets only supply.

**One mechanism, two schedules.**
- **A portion event.** At a declared grid time, declared volumes (or fractions of the source node) move
  along a set of links.
  - Every portion is drawn from the state before the event and delivered at once.
  - A wash is {node → sink: fV; inlet → node: fV}.
  - FR-37's uneven draw is two draws into one collector and two refills.
- **A flow.** A prescribed volume rate Q ≥ 0 on each link, piecewise constant on the grid.

**The volume rule.** At every node, inflow equals outflow, per event and per flow segment, by the declared
values. Anything else is refused by name. Records grow by what they receive.

**The exact step of a flow.** With the volumes fixed and Q constant within a step, every dissolved species
obeys one linear system:
- dn/dt = M n + Σ_ι q_ι c_ι, with M_ji = Q_ij/V_i for i ≠ j and M_jj = −Q_out,j/V_j, and q_ι the inlets'
  flows into each node;
- its exact step over h is P = e^(Mh), with the inlet and record columns from the same exponential
  (Van Loan's block form);
- P depends on the declared Q, V and h alone, never on the time. So it is a control, computed once per
  schedule segment on the host;
- it is species-blind: one P carries every dissolved species.

**The exponential's bits.** They set restart identity and crossrev, so the routine is named and its
library version is held.
- **The routine** is `scipy.linalg.expm` (Al-Mohy and Higham's scaling and squaring with Padé
  approximants), on the host, once per segment.
- **The version is pinned and recorded.**
  - `scipy==1.18.1` is pinned in `pyproject.toml`.
  - Every run's runtime identity records it (`records/io.runtime_identity`, `RUNTIME_PACKAGES`).
  - Its BLAS runs at one thread (D190), and the run manifest records those libraries
    (`execution/blas_threads`).
- **So P's bits follow** the declared Q, V and h, the scipy version and the CPU type, as every other
  host computation's do.
  - A resume across a runtime change is refused (checkpoint continuity, case 4).
  - crossrev hashes the controls, P among them, so a change of scipy shows there.
- **A decimal routine was weighed.** Its bits would not follow the CPU, but the engine's do anyway
  (D190), and it costs seconds per segment at 64 nodes.

**The repeated eigenvalue.** A chain of identical wells at one rate has a repeated eigenvalue.
- B's amount is then N₀ (Qt/V) e^(−Qt/V), the t·e^(−t) form.
- The two-rate formula k_A/(k_B − k_A)(e^(−k_A t) − e^(−k_B t)) reaches it only as a limit (0/0 at
  equal rates).
- FR-57's 26.42%, 1 − 2/e, is that case. So the references write the confluent form, and nearly equal
  rates by a stable divided difference.
- The engine's exponential needs no special case.

**The step as portions.**
- P_ji V_i is the volume of node i's start liquid that ends in j within the step. The inlet columns give
  the inlet liquid that ends in each node or record.
- So each holder's end liquid is a mixture of portions at their sources' start compositions.
- A flow's step is therefore one routed exchange whose portions come from P, and §3.3 and §3.4 apply
  to it unchanged.

## 3. Options and decisions

### 3.1 What routes the liquid

| Option | What | For | Against |
| --- | --- | --- | --- |
| A | Widen `scheduled_compartment_wash@1` in place (D148) | One operator, no new ID | The name no longer fits a flow. New fields enter every washed world's state, so crossrev changes (the FR-44/45 note §12.2: even a zero-size field differs) |
| **B** | **A new operator with an event part and a split part; it takes over the wash** | One mechanism, one representation per node (D175, D246). A flow is its continuous schedule | A new operator and a migration of the wash's worlds |
| C | A flow-only operator beside the wash, sharing one kernel | The wash untouched | Two operators for one mechanism. The wash refuses every non-local law at its nodes, so the two cannot share a node |
| D | A mover class in @3 (advective faces) | Inside the tableau | Integrated by the explicit stages, not exactly. Rate-booked heat reads the trace (§3.4). It has no records for a collector |

**Decided: B, `liquid_routing@1`** (`cells.operator.liquid_routing@1` under the rename, §7; the user, Q1).
- **The name** avoids `exchange`, the assembly family's law interface (§7). It also avoids "routes", which
  are kinds' passive routes and exchange routes. The entities are holders, links and portions.
- **The wash becomes its event.** A wash maps one to one onto a portion event with a sink and an inlet.
- **Its kernel is `wash_terms`, generalized.** The wash's worlds re-declared as portion events must give
  every physical field and mapped record bit for bit (§8.2, arm 7) before the wash is retired.
- **What the retirement touches:**
  - FR-49's registration (`validation/fr49/REGISTRATION.md`) names the wash's ID in Worlds B and C1;
  - FR-45's protocol, `fr45-site-competition-v1`, washes in W2 and W7. W7 comes from its amendment 2 on
    branch `fr45-protocol` (ff99fead), which is not yet tagged;
  - Lean's claims name the wash at their engine revisions, which old tags keep;
  - frozen checkpoints of washed worlds need renewing (D350).
- **The timing (the user's decision).** The wash is retired after arm 7's bitwise check, and only once:
  - FR-49's registered B and C1 runs have finished, or are pinned to a snapshot from before the
    retirement;
  - FR-45's protocol is written against the router before its tag, or its judged runs are pinned the
    same way.

### 3.2 The collector at zero volume

| Option | What | Verdict |
| --- | --- | --- |
| (a) | A record from zero volume, which grows, and stays a record | Superseded by (b) |
| **(b)** | **A record from zero volume, which grows, and which a later landing can open as a node whose liquid keeps reacting** | **Decided (the user, Q3), as FR-57 settled (D352)** |
| (c) | A node at a trace, with a small volume | Refused. A node's volume is fixed in version 1, so it cannot grow. And a tube at zero volume holds no trace: a trace volume V_ε would book about RT V_ε x at the first portion instead of 0, a number set by the declared V_ε alone (plant 9) |

**The record, in version 1:**
- At zero volume the amounts are exactly 0, and F(0, 0) = 0 (n ln n → 0).
- The first portion is taken as it is: the record's concentrations become the portion's, bit for bit, and
  its loss is exactly 0.0.
- Later portions pool by the lumen's fill form, with the resident liquid as one portion.
- Each delivery records its loss and that loss's two terms, the resident's and the arriving portion's,
  as level records (Q5).
- **A node empty of tracer is a different thing.** It is a node at the tracer's trace (§3.4, "the
  trace"). The two are never mixed up.

**Opening it as a node, designed in now** (S; a later landing, +1 to 1.5 agent-days, §10). Version 1
fixes the record so that opening changes none of its meaning or bits.
- **The record holds exactly what a node needs:**
  - its amounts as plain binary64 levels in fmol, never anchor plus increment, so a copy is exact;
  - its volume in pL, the same way;
  - the F of its liquid as a stored level in @3's convention;
  - its pooling heat, cumulative.

  The field names and record kinds are fixed in version 1 and never renamed.
- **Every species stays positive once liquid arrives.** Every inlet and node liquid carries every neutral
  species at its trace or above. So a record that has received liquid holds every species above 0, as
  @3 requires of a node.
- **The opening is additive** (D148: statically absent unless declared). At a declared grid time:
  - an outside node slot, declared closed until then, opens;
  - its anchor is the record's amounts and its volume the record's, bit for bit. The router provides both
    through the view for that slot alone, as insertion's onset anchors are provided (D057). Door S's scoping
    keeps the router's fixed reads at its other nodes unchanged;
  - the energy ledger books the record's stored F as entering the world, never recomputed, and the
    material ledgers book its amounts as supplied into the node;
  - the node's label shares are the record's labelled contents over its total (§3.5);
  - the node's ions are declared at the opening, under §3.3's rule for liquid from another node.
- **After the opening,** the record keeps its values: what was collected until then. It takes no further
  delivery, refused by name, and the node is an ordinary node under the volume rule.
- **Its rows,** in the later landing:
  - the node's first row against the record's last, bit for bit;
  - the ledgers on the opening row;
  - a restart cut at the opening.

### 3.3 Volume and every solute

- **Volume.** A node's volume is constant, by the volume rule. Each record's volume grows by exactly what
  it receives. The volume ledger holds the records' volume less the inlets' volume at zero, to rounding.
- **Every solute.**
  - One species-blind P moves every dissolved species.
  - The step is applied as moved amounts m_ji = P_ji n_i (j ≠ i) and inlet amounts. Each is one
    expression used at both of its ends (D266), and the stored increments change by their sums, so P_ii
    is never applied directly.
  - **The kept part absorbs the column-sum remainder.** A source's kept amount is n − Σ moved out, and a
    holder's kept volume is V − Σ moved in, each formed as the remainder.
    - So the books close by construction.
    - The remainder, 1 − Σ_j P̂_ji, is at most a few eps. It is a trajectory error inside the rounding
      bound, not a booking error.
  - The router's own ledger holds, per species, Σ nodes + Σ records − Σ inlets supplied equal to the
    start.
  - @3's outside and total ledgers gain (to records − from inlets) at each node, D150's sign, as the
    wash's do.
- **The rounding bound,** derived:
  - P's columns, with their record entries, are checked on the host, as each segment's P is computed, to
    sum to 1 within 4 eps. The protocol also checks P̂ entry by entry against the references' decimal P,
    within 8 eps absolute (‖P‖ ≤ 1).
  - Each half-step's material error is then at most (K + 4) eps of the moved amounts, with K the routed
    nodes. Over S steps each amount lies within 2S (K + 12) eps of the total amount from the exact one,
    since P only contracts (S).
  - That enters the composite's allowance (`LEDGER_STEP_ROUNDING` eps × steps × magnitudes) through the
    router's magnitude terms.
  - The amounts are an anchor plus an increment, so near depletion the wash's limit holds (wash note §4.5).
- **Ions** are `same_as_compartment`, as D246 requires.
  - Every routed node's ions stay bit for bit. Where liquid moves, each ion's outflow and inflow records at
    a node are one expression, so they cancel exactly.
  - That is exact only where the liquid moved carries the receiving node's own ion composition. An
    inlet's liquid does by declaration, as the wash's buffer does. Liquid from another node does only if
    the two nodes' ions stay equal for the whole run.
  - **So, at the definition:** nodes joined by a node-to-node link must declare equal ion
    concentrations, and no mover of a charged row may act at them (a patch's permeability, a channel, a
    pump, a face, a kind's charged route, an operator's in-step process). Each is refused by name.
  - **At run time,** as a guard behind that check: every event and half-step compares the ions at each
    node-to-node link's two ends, and refuses the step where they differ beyond rounding.
  - A node with only inlet and record links keeps the wash's rule, with ion movers admitted.
  - Records hold neutral species only, and an ion in an inlet's composition is refused at the definition.
- **Bound material** is never read or written.
- **Rejected: per-species first-order transfers.** No volume moves, and any two-stage chain reaches FR-57's
  two targets (its first reading).

### 3.4 Free energy and heat, exactly per portion

**The booking.**
- **A portion's free energy.** A node portion carries (v/V_src) F(src), an exact split by homogeneity. An
  inlet portion carries F(v c_ι, v).
- **The mixing heat** at each receiving holder is H = RT Σ_s Σ_k V_k c′ φ(c_k/c′), over the portions mixed
  there, its kept liquid among them.
  - φ is `numerics/ideal_mixing.phi`, the cleft fix's form, computed and never a remainder.
  - H ≥ 0 is checked at every event and step, on the device and on every row.
  - A collector's heat is the lumen's fill form.
- **The step's total.** Σ H = F(inlet liquid) + Σ F(start) − Σ F(end) − ΔF(records), exactly in real
  arithmetic. So @3's energy ledger, closing to rounding, checks the φ computation, as D246 ruling 3
  intends.
  - This needs the outflow to be pooled. A collector's F is a state function, so its pooling heat takes
    up the stream's non-uniformity.
  - A sink's is not. A flow into a sink would book its outflow's F from the step's portions, first order
    like the split.
  - **So in version 1 flows end in collectors, and a sink takes portion events only** (§6). A drain is a
    collector whose contents nobody reads.
- **Records, outside the IMEX flow bound, as the wash's** (Q6). Rounding-level closure is forced: in a
  species-only world the energy allowance is about 2·10⁻⁸ pJ plus 2·10⁻³ of the flows, and the bath note's
  B1 to B4 were refused at that level.

**The free-energy addition (FR-57).**
- **Per chamber and step, exactly:** ΔF_j = F(portions in) − F(portions out) − H_j.
- **The one-mechanism link,** derived by expanding `wash_terms`' H_mix in f, with resident y and incoming x:

      H_mix / (RT V) = f y φ(x/y) − f² (x − y)² / (2y) + O(f³),   φ(r) = r ln r − r + 1.

  - With fV = QΔt, the first term is RT QΔt [x ln(x/y) − x + y], the FR's rate.
  - At f = 0.01 and x/y = 3 the remainder is 1.3·10⁻⁶ of RT V, which is third order.
  - So a train of D246 events at f = QΔt/V is first order.
- **The exact step's split.** At a chamber it books ½ ρ² RT V y φ(x/y) less per step than
  ∫ RT Q y φ(x/y) dt, with ρ = Qh/V. The desk check gives a ratio near 4 per halving. That heat appears at
  the downstream holder instead.
  - So a holder's share is first order over a horizon.
  - The total is exact.
- **The −n term.** This note uses the engine's convention above. A moved liquid carries the liquid's F,
  −ΠV included. Booking a stream as μ times its amount misses by RT Q |x − y| per unit time at each
  chamber, so the identity closes only with the liquid's F (plant 5).
- **A uniform stream** (x = y) books zero, within the square of the amounts' rounding: φ(1 + e) ≈ e²/2.
- **Flow off** gives P = I, and the half-step selects its start state bit for bit.
- **The trace.** An empty chamber is a node at the tracer's trace ε.
  - The rate form at the start, x ln(x/ε), is never booked.
  - The step's total is independent of the trace to O(ε V |ln ε|).
  - Over the first steps from the trace, the chamber's share converges as O(h ln(1/h)).
  - The refinement is stated as ladders in h and in ε (10⁻⁹, 10⁻¹² and 10⁻¹⁵ mM), as FR-59 must.

| Heat option | Verdict |
| --- | --- |
| **(a) The exact step's portions, in φ form** | **Chosen** (with Q2): the total exact, the split first order, H ≥ 0 per holder |
| (b) The rate form, integrated by quadrature on the exact trajectory | A better split, but the total misses rounding, and it is singular at a trace start |
| (c) The ledger's remainder | Rejected (D246 ruling 3): it checks nothing |
| (d) The rate at the step's start × h | Rejected: it reads the trace, is first order, and the energy check stops the run (plant 7) |

### 3.5 Composition

**FR-44's labels and washes.**
- **The report grows a carried part.** `LiquidExchange` gains `carried`: (amount, source, destination) for
  liquid moved from node to node.
  - `removed` is what leaves a node into a record: a sink by events, or a collector by events or flows.
    It leaves with the node's shares just before the event or half-step.
  - `supplied` (from inlets) joins the base label, even inside an open window (D327).
  - `carried` keeps its source's shares just before the event or half-step.
  - `supplied` cannot stand for liquid from another node, since it means "no label".
- **Collectors are records, not label pools.** The contract refuses an exchanged report from an operator
  that holds label pools (`label_event_error`). A record's labelled amounts only add, so it needs no
  shares of its own.
- **No new field on the label owner.**
  - `label_outside_removed_fmol` keeps its meaning: what left each outside node by label, into a record.
    It covers collectors as well as sinks.
  - In version 1 a node feeds at most one record, refused by name otherwise.
  - So a collector's labelled contents are the sum of its feeding nodes' records, plus its direct inlet
    deliveries at the base. Its shares are those contents over its total.
  - So FR-49's judge, whose `LABELS_ONLY` names every owner field (its erratum 1 added this one), needs no
    second erratum, and neither does the labels test's `same_physics`.
  - Rejected: a field `label_collected_fmol`, zero-size elsewhere. It would need FR-49's judge erratum 2
    before any of its later judged runs on an engine with the router.
- **The exact map** at a node: x_k = kept s_k + Σ carried s_source,k + supplied [k = 0], with the shares
  x over its sum.
  - It is exact for a flow, not only for events. Each label's material obeys the same linear,
    species-blind system, so carrying the start shares along P's portions gives the exact end
    materials.
  - `advance_transfers`, the inner step's predictor-corrector, is second order and is not used.
- **The half-step's report is a contract amendment** (S, kept marked, for the builder to settle with the
  label owner's owner).
  - Today a labels-taking split part reports moves that the continuous kernel reads, and only events
    declare a report kind (`contract.label_event`).
  - The router's half-step needs a declared kind that the exact map reads.
  - The owner refuses a report it does not read, so the kind and its handling land together.
- **Worlds without the router** keep their label programs, by a static switch.
- **The physical rows are bit for bit** with labels on or off (FR-42's promise).
- **Sites beside labels** stay refused, as today (the labels note §13).
- **The wash** becomes the router's event (§3.1). While the wash exists, the two are refused at a shared
  node and admitted at different nodes.

**FR-45's finite sites.**
- **Bound material is not liquid.** The router never touches it. Retention is tested on the operator alone,
  with the bound arrays bit for bit (D327's rule), because binding resumes within the step.
- **Portion events beside binding at a node** are admitted, as the wash's are. FR-45's target (a half wash
  collects 4 fmol of A, 2 fmol of B and no sites) holds unchanged.
- **A flow beside binding at the same node** is refused in version 1. The flow and the binding's half-steps
  do not commute, and nothing measures that. At other nodes it is admitted.
- **Shared site sets** (FR-45's shape (a)) leave every reader the router uses unchanged:
  `surface_crossings` and the trace rule read `Population.ligand` and the owner, which FR-45 keeps.

**Other operators.**
- **At a flow's nodes,** turnover, the reactions and species exchange are refused in version 1, since their
  splitting is unmeasured. Beside portion events they are admitted, as the wash admits them.
- **Door S:** as the wash. Volumes, anchors and the outside mask are fixed reads, scoped to the router's
  nodes. So water, the lumens and insertion are refused.
- **The compartments' list.** `cell_owned_compartments@1`'s admitted list fails closed until it names the
  router.
- **@3's faces:** §4.3.

### 3.6 A restart, and a checkpoint cut just before an event

- **Portion events** use the wash's counters: the events due by now (a control) against those applied
  (state, int64).
  - A checkpoint at the event's row holds the state the event acts on, and the resumed first step applies
    it (FR-44's cut, D352).
  - A stale count refuses the step.
- **Flows.** P is a control from the schedule, a function of (Q, V, h) alone.
  - A cut at a Q switch resumes with the step that leaves the switch under the new segment (D283's
    `same_instant`). The resumed controls are the uninterrupted run's, bit for bit.
- **Records are state.** A collector's amounts, volume, F and heat all ride in the checkpoint. A record at
  zero volume is 0.0, not a trace.
- **No cut splits a step,** since checkpoints fall between steps.
- **The cuts tested:**
  - mid-flow, through a snapshot;
  - exactly at a Q switch (D349 item 2's form);
  - at a portion row;
  - at the first delivery into an empty collector.
- **The plants,** each caught by the bitwise comparison:
  - a redo and a skip of a portion;
  - a collector's volume restored as zero;
  - a resumed control computed with h in place of h/2.

## 4. FR-54

### 4.1 Item 1: the two-well references and their tolerances (S)

**The world** is `face_world` (`tests/unit/test_heat_bookings.py`): two finite nodes joined by one face.
Its parameters are volumes V₁ and V₂, permeance κ = DA/L and k = κ(1/V₁ + 1/V₂).
- **Which rows run the composite.** The tier rows run @3's step on `face_world` directly. A composite with
  no operator takes @3's step as its own, and one row checks the two bit for bit.
- **Arm 1** runs the cases through `resolved_pump_composite@1`, as FR-54 asks: with no operator, and with
  the router declared but idle (D148's check).

**The references,** code-blind and tagged before any engine reading:
- **The transfer:** m*(h) = (c₁ − c₂)(1 − e^(−kh))/(1/V₁ + 1/V₂).
- **The wells' free-energy drop for a moved amount m:** D(m) = F(n₁, V₁) + F(n₂, V₂) − F(n₁ − m, V₁) −
  F(n₂ + m, V₂). The closed form's dissipated free energy is D(m*).

**The engine's step** (S, from the tableau and the code as read).
- Neutral rows move by the explicit stages alone.
- Under ARS(2,2,2) the transfer is m*'s form with 1 − e^(−kh) replaced by kh − (kh)²/2, the tableau's
  polynomial. The relative error leads at −(kh)²/6. Under IMEX Euler it is kh, leading at +kh/2.

**What a positive background changes.** The FR asks: activity, volume or nothing?
- **The transfer: nothing.** The neutral face flux is DA/L (c₁ − c₂), the solution is ideal, and the volumes
  are declared and fixed.
- **The free energy and both heats** change through the logs: D(m) and the log-mean weight.
- **The flux's rounding** changes through the log difference, about eps |ln c| / |ln(c₁/c₂)|.
- So the cases vary the background to test the heats and the rounding, and a transfer that moves with
  the background is an error (plant 15).

**The comparisons, at steps declared in advance:**

| Row | Subject | Reference | Tolerance |
| --- | --- | --- | --- |
| T1, scheme | The step's transfer | The tableau's polynomial | Rounding: it catches errors hidden inside the truncation band |
| T2, physics | The step's transfer | m*(h) | The polynomial's own deviation from 1 − e^(−kh), plus rounding |
| T3, control | `exact_free_energy_heat@1` | D(m_engine) | Rounding, its raw-sum bound. A miss points at the harness |
| T4, subject | The default face heat | D(m_engine) | Its local error, third order: the leading term by series from the closed form, times 2, plus rounding. Only in the resolved domain below |
| Order | T2 and T4 at halved steps | | Ratios near 8 (local) under ARS(2,2,2), near 4 under Euler |

D(m*) − D(m_engine) follows from T2 with no tolerance of its own: about Δμ̄ (m* − m_engine).

**The default's domain.** Its series bound holds only where a step changes both ends little, roughly
kh · c_max/c_min ≲ 1, pinned by the registration's dt study.
- At a trace background its first step stays a few percent off as h falls. That is FR-10's onset limit
  (BATH_SCHEDULE_DESIGN §3.2), recorded as such, not judged.

**A desk sketch** (S, the default as this note reads it). Its edges are measured on the engine, in a
recorded dt study, before any tag, and the measured edges replace them:
- At kh = 0.2 and c₁/c₂ = 4, T2's error is −0.70% and T4's is −1.6%. With backgrounds of 10 and 1000 mM,
  T4's is −1.1%.
- T4's ratios approach 8 per halving.
- At c₂ = 10⁻⁹ mM, T4 stays between −3% and −12% from h = 0.1 to 10⁻⁴.
- So under ARS(2,2,2), whose energy allowance is 2·10⁻³ of the flows, a species-only two-well run is
  expected to stop above about kh ≈ 0.08. The cases include steps on both sides, which also tests item 2.

**The cases** are fixed in the registration. A proposal:
- kh ∈ {0.2, 0.1, 0.05, 0.025};
- V₂/V₁ ∈ {1, 4};
- background ∈ {the trace, 0.1 a, a, 10 a, 1000 a}, with a = c₁ − c₂;
- both heat laws; ARS(2,2,2), and IMEX Euler for T1 and T2.

### 4.2 Item 2: a stopped run's report

- **The message** names the failing ledger and its element (species and node where the ledger has axes),
  the residual, the bound there, their ratio, and the accepted step (and its time where known).
- **The prefix is kept,** so the about twenty test files that match "accounting failed" by prefix stand.
  Readers of exact messages (`tests/tier3_record.json`, frozen verdicts) are listed before the change.
- **Where:**
  - `surface_pump.checked_rows` and the composite's own-ledger loop, on the host. The scalar path's device
    mode hands a failing window to the host, so this covers it too (`execution/row_checks.py`);
  - the vector windows and projective bursts, from the device's reduced residual and its ratio at the
    failing row (the `margins` branch), or by a host re-check of that row. The builder chooses and states
    which.
- **What changes.** On the host only messages change, and crossrev does not compare host checks. The
  vector path states what its choice changes: a host re-check of the failing row changes no program.
- **The tests are rows:**
  - `test_heat_bookings_formula.py`'s trace-start row, where the default refuses at row 1, also reads both
    numbers;
  - one vector-window refusal row does the same.

### 4.3 Item 3: the wash at a diffusion-connected node

**The lift (D246 item 5),** for the qualified form only:
- a node one face touches, the face carrying exactly one neutral species and no other row, with no other
  path across the node's surface (`surface_crossings`);
- **under `exact_free_energy_heat@1`:** any event;
- **under the default face heat:** only where the state after the event lies within §4.1's resolved
  domain across that face. This is checked at the event and refused by name outside it (Q7);
- everything else stays refused, including a second neutral species, an ion on the face, or a patch.

**The native run.** Diffusion, a half wash of the first well (a sink and an inlet), then diffusion, under
both heat laws. Three checks are read from the event's level records against the preceding row:
1. **the tracer removed:** f times the node's amount just before the event, to rounding;
2. **the tracer supplied:** f V c_buf, the buffer's amount in the refilled volume;
3. **the refill's heat:** D246's small-ratio form, against a 50-digit evaluation at the preceding row. The
   event row's energy ledger closes on its own.

**The acceptance target's numbers.**
- A saved row after the event already holds one step of diffusion. So "8 and 2 just before, 4 collected,
  4 plus the refill kept, 2 still" is read on the event map, not on saved rows: one NumPy row with exact
  values.
- In the run, 8 and 2 hold only to the integrator's tolerance. The run's exact claim is the sample equal to
  f times the preceding row.
- The legs before and after the event are compared with the closed form, restarted at the event's exact
  map, at successively smaller steps.

**The 8 and 2 fmol world lies inside the admitted domain** (desk figures, measured before any tag).
- Before the event its two wells stand at c_max/c_min = 4, at equal volumes.
- After the half wash at the trace, they stand at 2: 4 fmol plus the refill's trace, against 2 fmol.
- So at the declared steps, kh ≤ 0.2, kh · c_max/c_min is at most 0.8 before and 0.4 after: inside the
  sketched edge near 1.
- **The energy check is a separate limit.** Under the default heat it is expected to stop this world
  above kh ≈ 0.08 (§4.1). So arm 2 runs the default heat to completion at kh ≤ 0.05, and its larger steps
  are item 2's stop cases.

**"With FR-10's schedule"** (item 3's words; Q10, ruled). FR-10 is the held baths' dose schedule. Item 3
says "a withdrawal and a refill at a connected finite node", so the plain reading holds: the events'
schedule form, times on the dt grid by D283's predicate, as FR-10's bath schedule takes them. No held
bath enters.

**Flow beside diffusion.** It arrives with this qualification (Q8). FR-57's "flow off while diffusion
continues" is then a world with Q = 0, bit for bit equal to its diffusion-only twin.
- With Q > 0 the step is P(h/2), @3's step, P(h/2).
- Both are linear for neutral rows, so the reference is the exact system's exponential, evaluated in
  decimal.
- The error is second order, from the splitting and the tableau.
- **The faces take `exact_free_energy_heat@1` at a flow's nodes** in version 1. A flow can fill a
  trace-level chamber that a face touches, which is the onset limit with no event to check at. A
  domain check at every half-step is the later widening.

## 5. Every acceptance target, and where it is checked

"Kernel" rows are NumPy rows on the router's event and half-step, with no world compiled. "Runs" is the
compiled file of §8.4. "Arm n" is an arm of the registered protocol (§8.2). Each readout's class (§8)
sets its tolerance: a rounding bound or an order window, never the other.

| Target | Where it is checked | Controls |
| --- | --- | --- |
| **54.1** First step's transfer and dissipated free energy, across backgrounds and steps; derived tolerances; declared steps | Host one-step rows in `test_heat_bookings_formula.py` (T1 to T4); arm 1 | T3, exact heat to rounding; T1 against the polynomial; the trace case recorded as the onset limit; plants 14 to 16 |
| **54.2** A stopped run reports residual and tolerance | The trace-start refusal row extended; one vector-window row | The prefix kept |
| **54.3** Removed, supplied and refill heat at a faced node; the lift only for the qualified form | Kernel row; Runs (faced world, exact heat); arm 2 under both heats; refusal rows | A twin with the event declared and not due, bit for bit; the event row's ledger; plant 17 |
| **54 target** Equal volumes, 8 and 2 fmol; half of the first collects 4; it keeps 4 plus the refill; the second still 2 | A kernel row, exact: 4.0, then 4 + 0.5 V c_buf, then 2 bit for bit | In the run: the sample equals f times the preceding row |
| **54 target** Diffusion before and after, at successively smaller steps | Arm 2 | The no-event twin |
| **54.3** "With FR-10's schedule" | Ruled: the events' grid form, with no held bath (§4.3) | Q10 |
| **57** A → B → collector at V/Q: 1 − 2/e = 26.4241% | Kernel rows at 1 and 64 steps per residence time, to the derived bound; Runs | B → A gives 63.2121% from the same compile, P being a control (plant 1) |
| **57** B → A → collector: 1 − 1/e = 63.2121% | The same | — |
| **57** The tracer in each chamber and the collector; the sum is the start | The router's records; its own ledger on every row | — |
| **57** Only a flow passes: unequal volumes; two species carried by one Q; a bound species stays | Kernel rows. At V_B = 2 V_A and t = V_A/Q: A 36.7879%, B 47.7302%, collector 15.4818%. Bound arrays bit for bit on the operator alone | Plants 2 to 4 |
| **57** Volume: inflow equals outflow at every chamber, or refused by name | Refusal rows | — |
| **57** An exact coupled step; derived tolerance; the sum to a derived rounding bound | §2 and §3.3; kernel rows at 1, 8 and 64 steps per residence time agree within the bound | Plant 10 |
| **57** Mixing heat booked; otherwise the energy check stops the run | Runs, with host checks on every row | Plant 8, refused with item 2's message |
| **57** Version-1 refusals: ions; flow beside diffusion or binding at one node | Refusal rows: ions across a node-to-node link, at the definition and at run time (§3.3). Diffusion opens with §4.3 | — |
| **57** Wording: V/Q of one chamber; clean buffer at the trace | The references include the inlet's trace exactly (the system is linear) | — |
| **57** D148: absent unless declared; washed worlds bit for bit; a restart mid-flow bit for bit | A new operator; arm 7, the takeover's bitwise check; the resume file (§3.6) | The restart plants |
| **57 energy** The loss rate Q[x ln(x/y) − x + y] against storage and fluxes | Kernel rows per step, exact; arm 5, each chamber's heat converging to ∫ RT Q y φ(x/y) dt at first order | Plant 5 |
| **57 energy** A uniform stream loses nothing; flow off contributes nothing while diffusion continues | A kernel row: H ≤ (16 eps)² RT Σ n. Runs: Q = 0 against the diffusion-only twin, bit for bit | — |
| **57 energy** The one-mechanism link; an empty chamber's trace and its refinement | A kernel row: H_mix against the series of §3.4, ratio 4 per halving; arm 5's ladders in h and ε | Plant 7 |
| **57 collector** An empty tube; 1 pL of 1 mM, then 1 pL of 3 mM; 4 fmol in 2 pL at 2 mM | A kernel row by events; arm 4 also by a flow from an inlet that switches from 1 to 3 mM, with the same totals at every step | — |
| **57 collector** The first portion loses nothing; the total is 0.523248 RT·fmol | Exactly 0.0; the total against decimal (3 ln 3 − 4 ln 2) | Plant 9 |
| **57 collector** Reversed order: the same total, different per-portion losses | With two deliveries each delivery's loss is (0, 0.523248) in either order (D362 corrects D352). Judged per delivery, with a third delivery added: 1, 3 and 3 mM give (0, 0.523248, 0.137341); 3, 3 and 1 mM give (0, 0, 0.660589). Recorded too, the two-delivery split, resident and arriving: (0.306853, 0.216395) forward, (0.216395, 0.306853) reversed | Q5 |

## 6. Refusals and domains

**Refused at the definition, each by name:**
- a node whose declared inflows and outflows differ, per event or per flow segment, with the difference
  named;
- a held bath as a node, since that composition is the bath schedule's;
- ions other than `same_as_compartment`;
- a node-to-node link whose nodes declare different ion concentrations, or at whose nodes a mover of a
  charged row acts (§3.3);
- an inlet that names an ion, misses a neutral species, or holds a concentration ≤ 0 or below a site
  ligand's trace;
- a link out of a record or into an inlet, and a record declared with contents but no volume;
- a flow into a sink (flows end in collectors, §3.4);
- a node that feeds more than one record (§3.5, labels);
- a flow at a node that a face touches, unless the faces take `exact_free_energy_heat@1` (§4.3);
- a path across a routed node's surface (`surface_crossings`), apart from §4.3's lift;
- at a flow's nodes: binding, turnover, the reactions and species exchange;
- the wash at a router's node, while the wash exists;
- water, the lumens and insertion (door S); the compartments, until their list names the router;
- under RK4, the coupled mode (the router's flows are a split part, kept split);
- more than 64 routed nodes, since P is dense (a sparse form is a later item);
- off-grid times, times outside (0, end), Q < 0, unknown keys and duplicates.

**Refused at run time** (the step is refused and fails closed):
- an amount that is not positive and finite at a node, or a record's amount that is negative or not
  finite;
- a heat that is not finite, or below its rounding floor;
- a stale event count;
- ions differing beyond rounding across a node-to-node link;
- under the default face heat, a state after an event outside §4.1's domain at a faced node.

**Domains:**
- the liquid is ideal, dilute, incompressible and well mixed at every node, with no volume of mixing;
- Q is prescribed: no pressure or hydraulics;
- the solutes are neutral;
- a node's concentration is positive (a trace at least), and a record's is ≥ 0 with zero volume
  admitted;
- the step is any size for the flow itself, since the step is exact. Beside diffusion it is the step the
  registration declares.

## 7. IDs under the planned rename (D345, D346)

The form is `cells.<family>.<name>@major`, from the closed family list. The forms below are provisional
until the rename's design note of 25 November settles D350's open points:
- the one-dot grammar of `laws._ID`;
- `kind_registry.qualified()` reading a family as a namespace;
- `registry/declarations.py` splitting on the first dot;
- the manifest's `family` field.

| Today | Under the rename | Role here |
| --- | --- | --- |
| `liquid_routing@1` (new) | `cells.operator.liquid_routing@1` | The router. If it lands after the rename it is born in this form, with a registry record (the operator registry, the model table and the declarations manifest). If it lands before, it also gets a mapping row |
| `scheduled_compartment_wash@1` | `cells.operator.scheduled_compartment_wash@1` | Kept until retired. Afterwards it is refused at parse, and the refusal names the router |
| `neutral_arrival_labels@1`, `site_occupancy@1`, `cell_owned_compartments@1` | `cells.operator.…@1` | Composed with the router |
| `resolved_pump_composite@1`, `resolved_pump_tissue@3` | `cells.model.…` | The models it runs |
| `logmean_electrodiffusion@1` | `cells.route.logmean_electrodiffusion@1` | @3's face law |
| `exact_free_energy_heat@1` | `cells.heat.exact_free_energy_heat@1` | FR-54's control |
| `imex_ars222_face_electromigration@1`, `imex_euler_face_electromigration@1` | `cells.solver.…@1` | The solvers |

- **No new family.** The router's mixing heat is its own booking, not a heat choice, so no `cells.heat.*`
  ID is added.
- **`exchange` is not this router's family.** It is the assembly family's law interface
  (`cells.exchange_law@1`). FR-20's `cells.pool_replacement@1`, the wash's exact-count execution, is an
  assembly operator, and whether it shares `cells.operator.*` is one of D350's open points.
- **Kept as they are:** the interface ID `cells.operator@1`, the experiment keys and the report kinds,
  none of which is an ID.

## 8. The qualification plan

**Three readout classes.** Each readout is classed before its tolerance is written, so an exact readout
is never judged by an order window, nor an order-carrying one held to rounding. FR-38's amendment 3
(D354) corrected the second kind of mismatch on 24 November.

| Class | Readouts | How each is judged |
| --- | --- | --- |
| **Exact** | Flow alone: trajectories, targets, sums, volumes. Portion events and the growing collector. Each step's total heat. Labels through events and flows. FR-54's T1 and T3 | A derived rounding bound (§3.3), never an order window |
| **Second order** | Flow beside diffusion: Strang splitting with @3's tableau (arm 6) | An order window at halved steps, global ratio near 4 |
| **First order** | How a step's heat splits among the holders (arm 5) | An order window, global ratio near 2 |

FR-54's T2 and T4 carry the tableau's own orders, with derived bounds and ratios near 8 (§4.1).

### 8.1 The cheapest proof of each claim

| Claim | The cheapest proof |
| --- | --- |
| The flow's trajectory is exact at any step | Kernel rows: the half-step applied twice per step, against the closed forms in decimal, at 1, 8 and 64 steps per residence time |
| Volume and every solute are conserved | The same rows' own ledgers; the runner's host checks on Runs' every row |
| Each portion's heat is exact and ≥ 0, and the total is the state-function balance | Kernel rows: the growing collector in both orders and with three deliveries; the uniform stream; the wash's 50-digit φ rows, kept |
| The one-mechanism link | One kernel row: an f-ladder with ratio 4 |
| FR-54's first step | Host one-step rows (§4.1), with no runner |
| A stopped run's report | Existing refusal rows, extended |
| The wash at a faced node | The event-map row; one compiled world under exact heat |
| Labels are exact through events and flows | NumPy rows: the exact map against P applied to label materials, and the labelled call's state and validity bit for bit the unlabelled call's. Arm 3 runs the twins |
| Sites are untouched | One operator-alone row: bound arrays bit for bit |
| A restart is bit for bit | The resume file (§3.6) |
| The wash is taken over bit for bit (Q1) | The wash's existing rows, re-declared |

### 8.2 The composed worlds: one registered protocol, a verdict per request (Q9)

- **The references come from a separate, code-blind agent.** This note's author has read the engine, so
  writes none of them.
  - They are written from this note and the requests, and tagged before any engine reading.
  - They compute P in decimal, and FR-57's equal-rate chain in its confluent form (§2).
- **Before the tag,** a recorded dt study on the engine measures §4.1's and §4.3's desk edges. The
  measured edges replace the sketched ones.
- **Two verdicts.**
  - FR-54's verdict reads arms 1 and 2. Item 2's message is read on arm 2's stop cases.
  - FR-57's verdict reads arms 3 to 7. Arm 6 runs only once FR-54's arms pass (Q8).
- **The run** is detached, with its evidence on disk. It is not a tier file.
- **Arm 1, the two-well first step:** §4.1's cases, both heats.
- **Arm 2, the native run:** diffusion, a half wash, then diffusion, at the declared steps. The three
  event checks, under both heats.
- **Arm 3, the flows:**
  - A → B → collector and B → A → collector, at equal and unequal volumes, and a split and merge and a
    loop (Q4);
  - two species, and the label owner with a labelled tracer in A;
  - the targets, the sums, the exact labels, and the physical rows bit for bit against the unlabelled twin;
  - a separate unlabelled world with a site population at a third node, whose rows are bit for bit those
    of the same world without the router. Sites beside labels stay refused (§3.5), so no world holds
    both.
- **Arm 4, the growing collector:** fed by portions, and by a flow from an inlet switching from 1 to 3 mM;
  also 1, 3 and 3 mM. A restart at the switch.
- **Arm 5, energy:**
  - each chamber's heat converging to ∫ RT Q y φ(x/y) dt at first order;
  - the trace ladder: B empty at ε = 10⁻⁹, 10⁻¹² and 10⁻¹⁵ mM, with h halved;
  - the per-step total, exact throughout.
- **Arm 6, flow beside diffusion:** A ↔ B by a face, with A → B → collector. Checked against the linear
  system's exponential, second order at halved steps; Q = 0 bit for bit against the diffusion-only twin.
- **Arm 7, the takeover (Q1):** the wash's worlds re-declared as portion events, with every physical
  field and mapped record bit for bit. Those are FR-27's review well, FR-44's twins and FR-37's three
  draws. It gates the wash's retirement (§3.1).

### 8.3 Planted errors

Each plant fails the named check. No plant needs a world of its own.

| # | The plant | It fails |
| --- | --- | --- |
| 1 | The chain declared in reverse (B → A) | 57's 26.42%, giving 63.21% (the FR's plant) |
| 2 | No mixing in B: B passes its inflow on unchanged | 57's 26.42%, giving 63.21% |
| 3 | A first-order transfer at k = Q/V_A for both chambers, with no volume moved | It passes at equal volumes. It fails at unequal ones (26.42% against 15.48%), on the collector's volume (0 against Qt), and on the heat |
| 4 | A rate per species | Two species carried by one Q |
| 5 | The stream's F booked as μ times its amount | The per-chamber identity, by RT Q\|x − y\| per unit time. It passes a uniform stream, so the row needs x ≠ y |
| 6 | The heat taken as the ledger's remainder | The φ row against 50 digits (D246 ruling 3) |
| 7 | The heat as the start rate × h | The trace row: it books Qh x ln(x/ε), and the energy ledger refuses it |
| 8 | No heat booked | The energy check stops the run, and item 2's message names the residual and bound |
| 9 | The collector as a node at a trace | The first portion's zero loss |
| 10 | P with h in place of h/2 | The targets, and the resume comparison |
| 11 | A carried portion with the destination's shares; an inlet joining an open window's label | The label rows |
| 12 | The router writes bound material | The retention row |
| 13 | A restart: a portion's count one over (a skip), one short (a redo); a collector's volume reset to 0 | The bitwise comparisons and the volume ledger |
| 14 | k from V₁ alone | T2 at V₂/V₁ = 4 |
| 15 | A transfer that depends on the background | T2 across the backgrounds |
| 16 | The default heat's weight at the step start | T4's bound and its order (ratio 4, not 8) |
| 17 | The event applied after the inner step | 54.3's "removed = f × the amount just before" |
| 18 | A stopped run's message without its numbers | 54.2's row |

### 8.4 Test cost (D224)

The seconds below are priced from measured rows in `tests/test_tiers.json`. The cap is 90 s.

| File | Change | Seconds | Reason |
| --- | --- | --- | --- |
| `test_wash_schedule.py` (tier 1, 9.7 s; renamed with the operator when the wash is retired) | Kernel and refusal rows, NumPy | +3 | The operator's own rows, with no world compiled |
| `test_heat_bookings_formula.py` (tier 2, 35 s) | §4.1's host one-step rows on `face_world`, both heats; the trace-start row reads item 2's numbers | +20 | No runner needed |
| `test_neutral_arrival_labels.py` (tier 2, 60 s) | The exact map with `carried`, and plant 11 | +2 | NumPy |
| One vector-window refusal test | Item 2's numbers | 0 | An extended row |
| **New** `test_liquid_routing_runs.py` (tier 2) | Two compiles: the flow world with the label owner (forward and reversed on one compile) and the faced-node wash under exact heat | About 60 | The only path through the compiled split part, and the event at a faced node, under the runner's host checks. The wash's runs file (76 s) and the twins (70 s) have no room |
| **New** `test_liquid_routing_resume.py` (tier 2) | Three compiles: the run and two resumes (§3.6) | About 60, priced from `test_wash_schedule_resume.py` (59 s, three compiles) | No other file restarts across a flow or at a flow switch |

- **The total** is about +145 s on tiers 1 and 2, about 1.4% of their 172 CPU-minutes.
- **With the wash taken over (Q1),** its three files (about 145 s) are folded into the router's, their
  worlds sharing its compiles. The net is estimated at about +50 s.
- **The collector's opening (Q3),** in its later landing: one NumPy row, and one compiled world in
  `test_liquid_routing_runs.py`, about +25 s, taking it to about 85 s. Its reason: the only path
  through an opened node. It moves to a file of its own if the measured row passes the cap.
- **The registered protocol** runs once, as a detached job. It is not tier-tested.

## 9. What is not claimed

- **No fluid dynamics:** no pressure, no Navier–Stokes, no dispersion, and no advection on faces. FR-37's
  "which part of the liquid a port draws" stays out.
- **Every node is well mixed.** A plug-flow tube is not a node, and a series of nodes approximating one is
  not claimed.
- **No ions are carried.** They stay at their nodes, which is exact only where the liquid moved has the
  receiving node's ion composition, as §3.3 requires. There is no charge transport by liquid.
- **No flow beside binding, turnover, reactions or exchange at one node** in version 1.
- **How a step's heat splits among holders** is first order in the step. Only the totals are exact.
- **A collector has no chemistry while it is a record.** Opening it as a node is a later landing (§3.2).
- **No count-level (binomial) execution** of routed portions. That stays FR-20's later extension.
- **No claim that the default face heat books a step from the trace.** FR-10's onset limit stands.
- **Nothing about real instruments** beyond the declared Q and portions.
- **Integration grants no acceptance** (D143). The registered protocol's verdict does.

## 10. Decisions, the price and the order

The decisions were made on 24 November 2026. The user decided Q1 and Q3, and the coordinator ruled the
rest as this note recommended.

| Question | Decision | By |
| --- | --- | --- |
| Q1. The operator's identity | A new `liquid_routing@1` takes over the wash. The wash is retired after arm 7's bitwise check, once FR-49's B and C1 and FR-45's W2 and W7 allow, or with them pinned to an earlier snapshot (§3.1). Not a sibling beside the wash, nor the wash widened in place | The user |
| Q2. Events, flows, and how a flow runs | Both in one operator, a flow by its network's exact step. Not a train of D246 events (first order), nor rates in @3's tableau | The coordinator |
| Q3. The collector | A record that a later landing can open as a node whose liquid keeps reacting. Version 1 fixes the record so the opening changes none of its meaning or bits (§3.2) | The user |
| Q4. Networks | Any balanced network of at most 64 nodes, qualified on a chain, a split and merge, and a loop | The coordinator |
| Q5. "Different per-portion losses" | Each delivery's loss, with a third delivery added: 1, 3 and 3 mM give (0, 0.523248, 0.137341); 3, 3 and 1 mM give (0, 0, 0.660589). The two-delivery resident and arriving split is recorded too. D362 corrects D352 | The coordinator |
| Q6. The heat's form | Records outside the IMEX flow bound, as the wash's, with H ≥ 0 checked at every event and step | The coordinator |
| Q7. The default face heat at a faced exchanged node | For events, admitted within §4.1's resolved domain and refused by name outside it. A flow's faced nodes take the exact heat. The edges are measured before any tag, and the 8 and 2 fmol world lies inside the domain (§4.3) | The coordinator |
| Q8. Flow beside diffusion | In the same build, once arms 1 and 2 pass | The coordinator |
| Q9. Qualification | One registered protocol, with a verdict per request: FR-54's and FR-57's (§8.2) | The coordinator |
| Q10. "With FR-10's schedule" | The events' grid form. Item 3 says "a withdrawal and a refill at a connected finite node" | The coordinator |

**The price** (S, in agent-days):

| Part | Agent-days |
| --- | --- |
| FR-54 item 2 | 0.25 |
| The router: parse, holders, links, the exact step, books, records, refusals, summary and run view | 3 to 4 |
| Labels: the report, the exact map and the collectors' labelled contents | 0.75 to 1 |
| The faced-node lift and the default's domain | 0.5 |
| Tests | 1 |
| The registered protocol: the dt study, the references (a separate agent), judge and run | 1.5 to 2 |
| Docs: library page, composition table and `PUMP_COMPOSITE.md` | 0.25 |
| The wash taken over (Q1): arm 7, its tests re-expressed, its retirement | 1 to 1.5 |
| **Development** | **8.25 to 10.5** |
| The collector's opening as a node (Q3), a later landing | +1 to 1.5 |

**The order.**
1. **This note** lands with the rename's design note, in one stack with no src change.
2. **The build comes after the rename of 25 November,** so the operator's ID is minted once, as
   `cells.operator.liquid_routing@1`, with no mapping row. The wash's files carry FR-49's wash narrowing
   first (D327).
3. **The registered protocol is tagged before the build.**
   - Its dt study runs on today's engine first. The default face heat's edges need only @3's faces: the
     8 and 2 fmol world before and after the event is a two-well start.
   - Its references come from a separate code-blind agent (§8.2).
4. **The wash is retired after arm 7,** when FR-49's and FR-45's runs allow (§3.1).
5. **The collector's opening** follows as its own landing, statically absent until declared (§3.2).
