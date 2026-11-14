# Feature requests

Requests for engine features from the user or from studies the user runs, with their priority, the
lead's mapping to the existing plan, and their status. Each becomes a design note before code (D142)
and a general feature, never one built for one study (D144).

| ID | Feature | Priority | Status | Next step |
| --- | --- | --- | --- | --- |
| [FR-1](#fr-1--a-closed-internal-compartment-on-the-shared-inventory) | A closed internal compartment on the shared inventory | **High** (user, 14 November 2026; the request's own label: priority 1, blocking) | Logged; design not started | A design note for a fixed-topology compartment (below) |
| [FR-2](#fr-2--internalisation-of-membrane-and-its-populations) | Internalisation of membrane and its populations | Priority 2 (the request's label; logged by the user, 14 November 2026) | Logged; follows FR-1 | A design note after FR-1's, settling retrieval's energy source (below) |
| [FR-3](#fr-3--the-site-occupancy-primitive) | The site-occupancy primitive | Priority 2 (the request's label; logged by the user, 14 November 2026) | Logged; specified as a door in D150 §2.5 | A design note from its own sources (below) |
| [FR-5](#fr-5--state-conditioned-transfer-across-an-internal-membrane-with-leak-and-reseal) | State-conditioned transfer across an internal membrane, with leak and reseal | Priority 1, blocking (the request's label; logged 14 November 2026). It depends on FR-1 and FR-4 | Logged | A design note after FR-1's and FR-4's (below) |
| [FR-6](#fr-6--species-driven-control-factors) | Species-driven control factors | Priority 2 (the request's label; logged 14 November 2026) | **Addressed by an accepted design (D155, D156; [the coupling note](INVENTORY_COUPLING_DESIGN.md)); no code yet.** Three narrower items are recorded as consumer registrations | The channel target in the coupling operator's milestone 1 (in progress); the routing door; the regulatory state as a prior condition (below) |
| [FR-7](#fr-7--abundance-to-function-exposed-in-the-composite) | Abundance-to-function, exposed in the composite | Priority 3, ordering and not scope (the request's label; logged 14 November 2026) | Logged; most of part (b) is the coupling operator's channel target | Considered when the closed molecular-to-physiology loop's unit is chosen (below) |
| [FR-8](#fr-8--a-qualified-long-duration-mode) | A qualified long-duration mode | Priority 2 (the request's label; logged 14 November 2026) | Logged; it is the compute-limits gate's open long-time deliverable | Its acceptance gains an intervention applied during the slow phase; a long-time path for composite operators needs a design note (below) |
| [FR-9](#fr-9--raise-the-7-species-cap) | Raise the 7-species cap | Priority 2, **blocking for world design** (the request's label; logged 14 November 2026). Measured safe to 16 (the W4 probe) | **Accepted: the raise to 16 is queued** as a D148 change to `species_common` (D165) | The D148 change with a guard world of 8 or more species; the requester's species list comes with its world definition |
| [FR-10](#fr-10--a-dose-schedule-scheduled-bath-composition-in-the-pump-family) | A dose schedule: scheduled bath composition in the pump family | Priority 2, small (the request's label; logged 14 November 2026) | Logged; the law and its accounting exist in a frozen family | A short design note re-expressing it as a composite operator (below) |
| [FR-4](#fr-4--compartment-ph-a-proton-species-an-acidifying-pump-buffering) | Compartment pH: a proton species, an acidifying pump, buffering | Priority 1, blocking (the request's label; logged 14 November 2026). The request sequences it last of the block, after FR-1 | Logged | A design note after FR-1's, with the energy-pool and charged-reaction doors (below) |

## FR-1 — A closed internal compartment on the shared inventory

**Logged 14 November 2026, high priority** (the user: "here is a new feature request please log as
high prioriity"). The request below is the requesting study's text, condensed. The lead's mapping
follows.

**The request.** A finite node that belongs to one cell rather than to the exterior:
- no bath connection, and no faces to other nodes;
- bounded by one membrane patch of its owning cell;
- with its own volume and its own rows of @3's one inventory;
- with transport routes across that bounding patch to the owner's cytosolic rows.

**Why it is general.** Secretory vesicles and granules: this is roadmap item 9's vesicle pool,
already wanted for connexin and morphogen supply. Also lysosomes and degradative compartments,
phagosomes, autophagosomes, and the ER and mitochondrial matrix as species compartments rather than
calcium-only ones.

**Why the study needs it.** Without it, an imported species lands in the same cytosolic row as free
cargo. The model cannot then tell "particle inside a vesicle" from "cargo in the cytosol", which is
the one distinction the study exists to keep.

**The request's own reading of the code** (corrected by the requester on 14 November; the lead
checked the cited lines):
- `restricted_cleft_lumen@1` is not most of this.
  - It is "a finite outside node opened at an insertion onset", not cell-owned.
  - Its volume follows the inserted patch's area, with no water flow.
  - It declares `VIEW_READS = ("membrane_area",)`, so membrane state and insertion are mandatory
    providers.
  - It refuses any source that is not a held, electroneutral bath (`restricted_lumen.py`).
- **The mutual refusal.**
  - The species operators refuse water, the lumens, insertion, partition and the bridge
    (`species_common.py`, `CONFLICTS_VIEW`; D152's refusals likewise).
  - The lumen requires insertion and membrane state.
  - So today a restricted compartment cannot carry inventory species rows with any law acting on
    them, in either direction.
  - This is the version 1.1 composition problem: the volume ledger and the `VIEW_READS`
    relaxation.
- **What transfers is the lumen's accounting:**
  - volume as state;
  - the mixing-heat Jensen gap for fluid of one composition entering a compartment of another;
  - the dilution term that brings @3's chemical term on the declared volume to the physical one.
- **What is missing:**
  - a node owned by a cell rather than by the exterior, with its bath and faces closed;
  - a membrane route for a neutral inventory species (D150 §2.6 refuses it until a material-rate
    bound exists on membranes and junctions: the queued D148 round, D155 and D156);
  - composition with a volume provider (version 1.1 and the volume ledger);
  - the transfer law itself.
- **The order, adopted from the requester's reviewer.** A compartment of fixed topology comes first.
  In it, retained material stays distinguishable from cytosolic material, and transfers reconcile
  on both sides. Dynamic internalisation (FR-2) follows it and does not gate it.

**The lead's mapping (for the design note to test, not settled).**
- **A fixed volume first.** A compartment of fixed topology and fixed volume needs no volume
  provider, so the species operators' refusal of water does not bind its first version. The
  volume-provider composition is its second step.
- **A transfer law that may already exist.** D150's `scheduled_species_exchange@1` already moves
  neutral species across a patch, between a cell and a finite node, with exact half-steps and its
  own bookings. If a cell-owned compartment node can be that patch's node, exchange may be the
  transfer law. It would then avoid the membrane-permeability route, which needs the D148 bound.
  - The design note should test this first.
- **The electrical treatment is the hard question.** @3's patches face outside nodes inside the
  extracellular field solve. A compartment inside the cell faces the cytosol. The note must say:
  - what the bounding patch's membrane voltage and the compartment's charge are;
  - whether the node takes part in the field solve;
  - for a neutral first version, whether the compartment can be electrically silent;
  - and whether the field-input node cap (64) is affected.
- **What it touches.** The S3 lumen's accounting patterns, D150's exchange and identity rules, the
  D148 round for neutral species on membranes, the volume ledger, and roadmap item 9.

**The plan entry.** It sits in CURRENT_PLAN's composition gate, high priority, after the work in
flight.

## FR-2 — Internalisation of membrane and its populations

**Logged 14 November 2026, priority 2** (the request's label; the user: "first log this one"). The
request below is the requesting study's text, condensed. The lead's mapping follows.

**The request.** The retrieval direction of `scheduled_membrane_insertion@1`: membrane area,
capacitance and the populations on it move inward at a scheduled rate, carrying the compartment they
form (FR-1) with them.

**Why it is general.**
- endocytosis of every kind;
- receptor down-regulation and recycling;
- surface-population turnover, which the roadmap lists under membrane redistribution;
- synaptic vesicle recycling;
- membrane retrieval after division.

**What is missing, in the requester's reading.**
- Insertion@1 refuses retrieval because the capacitor's free energy would rise: its heat would be
  negative, and the work would need a declared source. The lead checked this:
  `membrane_insertion.py` refuses "a negative rate (retrieval: its heat would be negative, and the
  work would need a declared …)".
- The requester notes that finite ATP/ADP/Pi pools already exist, in the older calcium and energy
  families. Letting species laws draw on energy pools is deferred: D150 question 11, D152
  question 10 and D151.
- So a declared ATP-coupled retrieval law looks like the same question arriving twice, and one
  answer would serve both.

**Why the study needs it.** Receptor-mediated uptake depletes the surface pool and returns it. A sink
that never consumes its receptors cannot produce saturation, competition between neighbouring cells
for a shared dose, or the cell-to-cell variation that makes delivery selective.

**The lead's mapping (for its design note to test, not settled).**
- **It depends on FR-1.** The retrieved membrane carries the compartment FR-1 creates, so FR-2's
  design follows FR-1's.
- **The energy source is the design question.** Retrieval's work could come from:
  - a declared external reservoir, as D150's turnover and D152's driven routes book work today; or
  - a finite energy pool.

  The pools live in the older families, outside the composite, so drawing on them in the composite
  is new work. The energy-pool coupling deferred by D150 and D152 should be designed once and serve
  every consumer.
- **Populations move with the membrane.** Channel and pump populations on the retrieved area move
  inward with it: the receptor down-regulation the study needs. That touches membrane state's
  populations, S2's domains and insertion@2's bookings, and needs their accounting.
- **What it touches.** S3's insertion and membrane-state operators, D150 and D152's energy-pool door,
  FR-1's compartment, and the composition walls (the species operators refuse insertion today).

## FR-3 — The site-occupancy primitive

**Logged 14 November 2026, priority 2** (the request's label; the user: "then next one"). The request
below is the requesting study's text, condensed. The lead's mapping follows.

**The request.** Promote the primitive already specified as a door in
[D150 §2.5](SECRETED_SPECIES_TRANSPORT_DESIGN.md):
- binding sites as state on a membrane domain or contact, with one owner;
- bound and free in one material ledger, never a second copy;
- accessibility as a factor separate from stoichiometry;
- declared partition and reset rules at division and replacement.

**Why it is general.** D150's own list: kinetochore sites, junction docking and surface catalysis.
Add to it ligand–receptor signalling generally, and the engineered quorum-sensing consortia in the
13 November reading list, where a finite receptor pool reads the shared signal.

**What it builds on.**
- `membrane_entity_state@1`'s populations are the owner D150 identified.
- The day-one analytic guard is already derived (D150 §2.5; the lead checked it). The saturable
  sink is the quasi-steady limit of binding with internalisation:
  J = k_int R_T c / (K_M + c), K_M = (k_off + k_int)/k_on.

**Why the study needs it.** Accessibility separate from stoichiometry is not a detail. Uptake of the
same formulation differs by cell type through surface composition. The 2026 glycocalyx and
protein-corona work found heparan-sulfate dependence in some tested lines and not in others.
Accessibility is where that enters a model without naming a receptor.

**The lead's mapping (for its design note to test, not settled).**
- **D150 §2.5's four requirements are the contract.**
  - The bound amount is state on the site's owner. Binding and release are booked transfers
    with @3's free inventory, as `exchange_moved_fmol` is.
  - Version 1's import routes are the shape the internalisation step writes into.
- **Accessibility as a factor.**
  - It is a declared multiplier on the binding rate, separate from the site count.
  - It fits the coupling operator's factor form (D155 and D156: F ∈ [b, 1]) when accessibility
    is regulated, and is a plain per-domain parameter otherwise.
- **The links to FR-1 and FR-2.** Receptor-mediated uptake binds at the surface (FR-3),
  internalises the bound sites with their membrane (FR-2) and delivers the cargo into a
  compartment (FR-1). The three should be designed so the bound pool's identity survives each
  transfer.
- **The design order.** FR-3 can be designed before FR-1's code lands: its first version needs only
  membrane state and @3's free inventory, and its guard is analytic. Its internalisation step
  follows FR-2.
- **The sources.** The primitive must be designed from its own sources (kinetochore counting, the
  Hirano 2026 review in the paper backlog, receptor kinetics), not shaped by one consumer (D144).

## FR-4 — Compartment pH: a proton species, an acidifying pump, buffering

**Logged 14 November 2026, priority 1 (blocking)**, the request's label. The request itself sequences
it last of the block, after FR-1's compartment exists and can hold material. The request below is the
requesting study's text, condensed. The lead's mapping follows.

**The request.** Protons as a species, with a pump that can acidify a compartment against its
gradient, drawing on the existing fuel pools, plus buffering through the reaction operator.

**Why it is general.**
- endosomal and lysosomal acidification;
- the mitochondrial proton-motive force, which the roadmap wants for energetics;
- pH-dependent gating and enzyme activity;
- bicarbonate handling.

Cells has no pH anywhere today, and a whole-cell model needs it.

**The charge problem, in the requester's corrected reading.** The lead checked each point in the
code.
- **A proton row is legal in @3 itself.** `surface_tissue_spec.py` admits integer valences in
  [−8, 8], so a +1 species is a declarable ion row. The transport half starts from something that
  exists.
- **It cannot be a D150 or D152 inventory species.**
  - `inventory_species.py` fixes `valence=0`.
  - `parse_species` refuses a nonzero valence for all three species operators
    (`species_common.py`).
- **Buffering is D152's named door.** Its §3.2 lists, as later work, "closed reactions on charged
  species with Σ_s z_s ν_sr = 0 exactly (integer valences), such as buffering".
- **The counterion pathway is a physical modelling choice, not bookkeeping.** Acidifying a
  compartment without a parallel ion flux charges it. The counterion pathways and the pump's
  energy must be explicit.

**Numerics the requester expects to matter, which the lead agrees with.**
- pH 7.4 to 5.0 is 4e-5 to 1e-2 mM, against about 150 mM of ions. That is D150's µM–nM regime,
  where the shared IMEX energy bound was 1.7 to 1,721 times a species' whole free-energy change.
- D150's answer should transfer: a species-only guard world, a NumPy ΔG test per law, and
  per-species material floors and anchors.
- Buffering is an equilibrium with a large capacity ratio, expected to be the stiff part.

**The lead's mapping (for its design note to test, not settled).**
- **Three doors already drawn meet here:**
  - D152's charged closed reactions, for buffering;
  - the energy-pool coupling, for the pump's fuel (D150 question 11, D152 question 10, and FR-2's
    retrieval energy);
  - FR-1's electrical treatment, which a proton-carrying compartment makes unavoidable. It cannot
    be electrically silent.
- **The pump.** An acidifying pump is a new pump law on @3's patch: a V-ATPase-like stoichiometry,
  cited, with neutral naming. Its energy comes from a declared fuel. The fuel pools exist only in
  the older calcium and energy families, so drawing on them in the composite is the energy-pool
  door.
- **Stiffness.** D152 v1 refuses kinetics too stiff for the step (dt·L > 1). Buffering therefore
  needs either the stiff-kinetics door (a positive implicit half-step) or a rapid-buffer
  equilibrium treatment, each qualified. That is for the design note to choose.
- **pH-dependent gating and enzymes.** These read a charged source. Under the coupling operator
  (D156) that goes through its regulatory state, or through D152's read-only charged-species door.
- **The order.** After FR-1 and with FR-2's energy design, as the request itself sequences it.

## FR-5 — State-conditioned transfer across an internal membrane, with leak and reseal

**Logged 14 November 2026, priority 1 (blocking)**, the request's label. It depends on FR-1's
compartment and FR-4's pH. The request below is the requesting study's text, condensed. The lead's
mapping follows.

**The request.** Two parts, both generalisations of things Cells has:
1. `resolved_repair@1`'s damage fraction and prescribed closure law, applied to an internal
   compartment's bounding patch instead of the plasma membrane;
2. a transfer law across that patch whose rate reads the compartment's own state (its pH), so
   that a species crosses when the compartment is in a declared condition and not otherwise.

**Why it is general.**
- mitochondrial permeability transition;
- lysosomal membrane permeabilisation;
- pore-forming toxins and complement;
- bacterial escape from phagosomes;
- exocytic fusion, which is the same accounting in reverse.

**What is not asked for.** A fitted escape mechanism. The repair law is phenomenological, which is
fine. What is needed is the accounting:
- material that leaves a compartment arrives in the cytosol;
- damage opens and closes;
- the books close.

Calibration is the requester's to supply, with measurements.

**The lead's mapping (for its design note to test, not settled).**
- **The injury law lives only in an older family.** `resolved_repair@1` (`surface_repair_spec.py`;
  the law in `processes/membrane_injury.py`) is fixed-geometry injury on owned calcium tissue. Its
  patches carry an initial damage, an injury rate, a resealing rate and per-species permeabilities.
  It is not a composite operator.
  - Applying it to a compartment's patch means re-expressing it in the composite, as an operator.
  - That is a case of the open decision on moving old-family physics (D156: it waits for the
    conduction probe's verdict). A targeted re-expression, on its consumer's need, fits D144.
- **Damage as a control factor.** An open fraction on the patch's leak, or on the transfer's rate,
  is kinetic state with no ledger. It is like the bridge's aperture, or the coupling operator's
  regulatory state (D156). The material it lets through is booked by the transfer law.
- **The state-conditioned rate is the coupling operator's routing door.** A rate on another
  operator's transfer, read from the compartment's pH:
  - it routes to another operator's control (D156's named door);
  - it reads a charged source (FR-4's proton), through the regulatory state or D152's read-only
    charged door.
- **The accounting is FR-1's transfer bookings,** with both sides reconciled.
- **Exocytic fusion** is FR-2's direction in reverse, with the compartment's contents released.
- **The order.** After FR-1 and FR-4, with the routing door, as its dependencies require.

## FR-6 — Species-driven control factors

**Logged 14 November 2026, priority 2** (the request's label). The general request is **addressed by
an accepted design, with no code yet.** The inventory-coupling note (D155 item 1, scoped by D156;
[INVENTORY_COUPLING_DESIGN.md](INVENTORY_COUPLING_DESIGN.md)) was accepted on 14 November.
- **What it specifies:** `species_regulated_availability@1` reads a concentration from @3's own amount
  rows, through Hill laws, into a factor F ∈ [b, 1]. `hill_regulated_two_state@1` serves slow
  sources.
- **What the requester withdraws:** the general request. Its code started on 14 November, with
  milestone 1 (the contract fit) in progress.

**Three narrower items remain, recorded as consumer registrations, in the requester's order:**
1. **The channel-population availability target** (the note's milestone 1; ruling 12).
   - The junction target is accepted. The channel target is the one this study needs, because a
     delivered template's effect on a cell's electrical behaviour runs through channel
     availability.
   - Leaks and pumps on the same path would cover the rest.
   - *Mapping:* probe P1, the channel path, is in milestone 1 now. Leaks and pumps are the note's
     next targets on the same path.
2. **The routing door (§2): a factor on another operator's control,** specifically a turnover rate,
   an exchange rate and a reaction multiplier.
   - This study needs it twice: for a release rate that reads a compartment's pH (FR-5 part 2),
     and for a production rate driven by a delivered template (FR-7).
   - The requester asks for nothing to be built now. It registers as a second consumer, so the
     door is not designed for one.
   - *Mapping:* recorded against D156's named door, beside the division trigger.
3. **The two-state regulatory fraction as a per-cell slow state,** used for a cell's *prior*
   condition, set before a dose arrives. That is the variable the study turns on: the same
   formulation given to differently conditioned cells.
   - It matches the GZMK review's "slow, writable per-cell state" row.
   - *Mapping:* the note's state has a declared initial value per cell (s₀), and interventions
     write it (`regulatory_writes`). So a prior condition is a declared s₀ or a write before the
     dose. Its version 1 refuses replaced slots (version 1.1).

**Why it was general, for the record:** morphogen concentration driving a response, quorum sensing,
substrate induction, and any drug–effect relation. The note's own consumers: Track R's cycle gate,
GZMK item 6, the causal-carriers row and E15.

## FR-7 — Abundance-to-function, exposed in the composite

**Logged 14 November 2026, priority 3** (the request's label: "ordering, not scope"). The request
below is the requesting study's text, condensed. The lead's mapping follows.

**The request.** No new scope. When the closed molecular-to-physiology loop's functional unit is
chosen:
- (a) the loop admits a production rate driven by a declared species (FR-6 item 2), not only a
  scheduled one;
- (b) the quantitative abundance-to-function relation is reachable in the composite. Today it is
  state only in `resolved_redistribution@1/@2`.

**The requester's update, 14 November.** The coupling design's channel-availability target (its
milestone 1) is most of (b): a factor on a channel population's availability is an
abundance-to-function path in the composite. If that lands, (b) narrows to "and let the factor's
source be a population abundance, not only a species concentration".

**Why the study cares.** This is stage 5 of its table, and the one place where Cells already has the
better part of the answer. "A transient template changes a protein abundance, which changes a
measurable physiological response, and the response outlives or does not outlive the template" is
both the study's therapeutic question and *Plastic Heredity*'s question. The requester would rather
use Cells' unit choice than ask for its own.

**The lead's mapping (not settled).**
- **The unit choice stays the user's** (CURRENT_PLAN's closed molecular-to-physiology loop
  gate). The candidates where abundance is already state: the redistribution pumps
  (`resolved_redistribution@1/@2`, an older family) and junction formation. This request asks only
  that the chosen loop admit (a) and (b).
- **Part (a) is the coupling operator's routing door** (D156): a factor on a production operator's
  rate. FR-6 already records it, with this as a further consumer.
- **Part (b), narrowed, is a source-semantics door of the coupling operator.** The factor's source
  would be a population's abundance, read from `membrane_entity_state@1`'s view, as well as a
  species concentration. It is to be recorded in that note's doors when the channel target lands.
- **The link to the preprints.** The response's persistence after the template is gone is the
  heredity question. A unit chosen for the loop should be one where that question is measurable.

## FR-8 — A qualified long-duration mode

**Logged 14 November 2026, priority 2** (the request's label). The request below is the requesting
study's text, condensed. The lead's mapping follows.

**The request.** Keep the quasi-steady electrical mode, or any qualified multirate method, on the
path. When it is qualified, include **an intervention applied during the slow phase** in its
acceptance case.

**Why it is general.** Everything slow: turnover, regulation, reconstruction, the renewal assay, and
the organ-scale ageing timescales D150 deferred for exactly this reason.

**The requester's arithmetic, corrected 14 November** (its reading of Cells' reported costs; the
requester is writing a benchmark specification for its own composition):
- **Its stages and the step count.** The stages run at ms (electrical), minutes to hours (uptake,
  acidification, escape) and 24–72 h (expression, protein turnover, response decay). At 1 ms that
  is 3.6M steps per simulated hour.
- **A 72 h trajectory, by field nodes:**

  | Field nodes | Per step | 72 h |
  | --- | --- | --- |
  | 14 | 1.7 ms | about 5.1 days |
  | 254 | 7.7 ms | about 23 days |
  | 825 | 76 ms | about 228 days |

- **Why that understates it:**
  - those per-step costs are the empty composition, with operators cost on top;
  - the 825-node figure varies by about 2× across the tree;
  - the L4 buys ensembles, not one fast trajectory: about 26.7 ms one world at a time, and
    2.10 ms per world-step only when amortised over 256 worlds.
- **So duration is a numerical-method problem, not a hardware problem.** Projective
  time-stepping failed its qualification, and the requester does not ask for it to be revisited.

**The lead's mapping (not settled).**
- **This is CURRENT_PLAN's open deliverable.** The compute-limits gate has "a verdict on
  long-time methods: multirate or quasi-steady methods qualified, or bounded, on histories and
  intervention responses". FR-8 adds that the acceptance case include an intervention applied
  during the slow phase. That is recorded in the gate (D164).
- **The gap the lead's architecture review named.** The coarse modes cover `resolved_pump_tissue@1`
  to `@3` only, so no composite operator has a long-time path. That needs its own design note,
  which does not exist yet.
- **The requester's benchmark specification,** when it arrives, is an input to that note: its
  composition, its accuracy needs and its interventions.
- **The two-clock pattern helps where the physics separates.** Track E's plan runs a slow world
  coarsely and short fast assays from frozen snapshots (D155). It is not a long-time method for
  one coupled trajectory.

## FR-9 — Raise the 7-species cap

**Logged 14 November 2026, priority 2, blocking for world design** (the request's label). The raise
was measured safe to 16 by the W4 probe. The request below is the requesting study's text,
condensed. The lead's decision follows.

**The count, corrected by the requester.** The lead checked the source.
- **The cap counts every species, ions included.** `check_species_cap` takes
  `count = len(spec.model.species_ids)` (`species_common.py`).
  - With the six-ion set (Na, K, Cl, Ca, P, M), one row is free under a cap of 7.
  - With a four-ion world, three are free.
- **Locations are not identities.** The arrays are (species, node). The same species inside a
  compartment and outside it is one row at two nodes.
- **One caveat the other way.** A compartment that is not a declared node has no node axis, so a
  pool held outside the node structure would need its own row. Which way FR-1 goes therefore
  changes the budget. The requester will state the count with its world definition.
- **The result.** A minimal delivery world on a six-ion set is over the cap before any cargo,
  bound complex, buffer or proton is added. So the cap binds on the first world definition,
  ahead of FR-1 to FR-5.

**What the W4 probe found** (read-only, from a clean snapshot at f7f0592; PROGRESS):
- the cap can rise to 16 in every composition D150 and D152 admit;
- no ledger, guard or promised idleness depends on NumPy's sum order;
- host checks, the face-free energy world, batches, restart and idleness hold at 16.

D150's unpromised claim 3 departs at rounding in a 12-species chain. The requester does not rely on
cross-world bitwise identity.

**The lead's decision (D165): accepted, and queued now.** The requester is the consumer that
PROGRESS's "when a consumer needs it" waited for.
- **The change:** `MAX_SPECIES` from 7 to 16 in `species_common`, as a D148 in-place change, with
  the four criteria and the stop rule written first.
- **The tests:**
  - a tier-1 guard world of 8 or more species that exercises the sum order (for example the probe's
    `cell_charged_9`);
  - the three refusal tests updated.
- **The documents:** D150 §2.6 and §11.5, D152 §7.2 and its refusal lists, and the docstrings.
- **What stays the same:**
  - D150's claim 3 stays reported, with the chain departure recorded.
  - Worlds above 7 species are outside D150's judged scope until a protocol covers them.
  - Above 16 needs another probe.
- **The requester's species list,** with its world definition, confirms the need (16 or fewer).

## FR-10 — A dose schedule: scheduled bath composition in the pump family

**Logged 14 November 2026, priority 2, small** (the request's label). The request below is the
requesting study's text, condensed. The lead's mapping follows.

**The request.** Let a held bath's composition change on the dt grid in the composite, as the older
surface families already allow for K, Cl and Na.

**Why it is general.** Any medium change:
- a wash-in or wash-out;
- a drug dose;
- an ion substitution;
- a pH step;
- a nutrient step;
- an osmotic challenge.

E07-v2's design wants an osmotic step as a post-release challenge, which is this feature (its §8:
"none found" in the pump family).

**What exists** (the lead checked the source).
- `resolved_open_calcium_energy_bath_events@1` programs an ideal reservoir's bath composition on
  the 56-law calcium/ER and finite-fuel owner.
  - The ion dose, the compensating electrode charge and the external work are kept explicit
    (`core/surface_bath_events_binding.py`, policy
    `explicit_ideal_reservoir_dose_voltage_compensation_work@1`).
  - So the law and its accounting already exist, in a frozen family.
- Its status there is guarded, with full bath trajectories out of scope and evidence at ns–µs
  horizons.
- In the pump family, nothing does this.

**The lead's mapping (not settled).**
- **A small composite operator.** An event map at dt-grid times sets a declared held bath's
  composition. It books the dose as reservoir supply and the composition change's external work
  explicitly. For a charged step it keeps the older law's compensating-charge rule.
- **It re-expresses an older family's law,** a case of D156's open decision on moving old-family
  physics. It has at least three consumers (this study's doses, E07-v2's osmotic step, FR-4's pH
  step), so a targeted re-expression fits D144.
- **D150's species.** A held bath already serves as a species' far-field source or sink at a fixed
  concentration. A scheduled change of that concentration is a species dose with no charge
  compensation, since the species are neutral.
- **Water.** An osmotic step needs water plus a bath change. Water composes with the composite,
  but water plus the species operators is refused (version 1.1). The note must state which
  compositions an osmotic step admits.
- **The order.** It is small and has several consumers, so it is a candidate for an early slot,
  after FR-1's design. Its design note should be short.
