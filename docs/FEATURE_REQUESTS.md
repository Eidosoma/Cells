# Feature requests

Requests for engine features from the user or from studies the user runs, with their priority, the
lead's mapping to the existing plan, and their status. Each becomes a design note before code (D142)
and a general feature, never one built for one study (D144).

| ID | Feature | Priority | Status | Next step |
| --- | --- | --- | --- | --- |
| [FR-1](#fr-1--a-closed-internal-compartment-on-the-shared-inventory) | A closed internal compartment on the shared inventory | **High** (user, 14 November 2026; the request's own label: priority 1, blocking) | **Milestone 1 landed** (15 November; [note](CLOSED_COMPARTMENT_DESIGN.md) §12, D169): `cell_owned_compartments@1`, neutral and silent, S1–S5 checked in a live-owner world with planted controls. **Judged, 18 November 2026:** its protocol, `fr1-closed-compartment-v1` (registration 05a8d193), passed, 44 of 44 judged criteria, against the code-blind references; exchange's first judged acceptance | The later doors (creation, division, fission and fusion, retirement) with seam B and the mitochondria work (D210, D216) |
| [FR-2](#fr-2--internalisation-of-membrane-and-its-populations) | Internalisation of membrane and its populations | Priority 2 (the request's label; logged by the user, 14 November 2026) | Logged; follows FR-1 | A design note after FR-1's, settling retrieval's energy source (below) |
| [FR-3](#fr-3--the-site-occupancy-primitive) | The site-occupancy primitive | Priority 2 (the request's label; logged by the user, 14 November 2026) | **Milestone 1 landed** (15 November; [note](SITE_OCCUPANCY_DESIGN.md) §12, D169): `site_occupancy@1`, the contract fit and the run, with idle, restart, batch and controls. **Judged, 18 November 2026:** its protocol, `fr3-site-occupancy-v1` (registration 1b838d75), passed, 51 of 51 judged criteria, against the code-blind references; `site_occupancy@1`'s first judged acceptance | A shared SSPRK(3,3) block, FR-3's own milestone (INNER_MODEL_V4_DESIGN §15.3; main still has separate integrators in `site_occupancy.py` and `species_reactions.py`) |
| [FR-5](#fr-5--state-conditioned-transfer-across-an-internal-membrane-with-leak-and-reseal) | State-conditioned transfer across an internal membrane, with leak and reseal | Priority 1, blocking (the request's label; logged 14 November 2026). It depends on FR-1 and FR-4 | Design accepted (§16 of [the FR-4/FR-5 note](COMPARTMENT_PH_TRANSFER_DESIGN.md)). Built and on main since fr45-next merged (16 November): the two source kinds, refusal 4 version 1.2, refusal 5 version 1.1 and FR-5's start part, for development, not judged. Its protocol, `fr5-transfer-v1`, is registered and judged on 17 November 2026: passed, 51 of 51 judged criteria (D195; tag fr5-v1-qualified-2026-11-17) | Done. The verdict's scope: `cell_owned_compartments@1` as built at 32a1d439 (refusal 4 v1.2, refusal 5 v1.1) |
| [FR-6](#fr-6--species-driven-control-factors) | Species-driven control factors | Priority 2 (the request's label; logged 14 November 2026) | **Addressed by an accepted design (D155, D156; [the coupling note](INVENTORY_COUPLING_DESIGN.md)). Its operator, `species_regulated_availability@1`, is numerically qualified (15 November).** Three narrower items are recorded as consumer registrations. **A5″ judged, 18 November 2026:** its protocol, `fr6-a5pp-v1` (registration 555d8771), passed, 18 of 18 judged criteria, against the code-blind references: the gate-free channel target (item 1) driven through the regulatory state from a per-cell prior (item 3) | The routing door (item 2); gated channel populations (A5′), leaks and pumps (item 1's rest) |
| [FR-7](#fr-7--abundance-to-function-exposed-in-the-composite) | Abundance-to-function, exposed in the composite | Priority 3, ordering and not scope (the request's label; logged 14 November 2026) | Logged, and registered as a consumer of the coupling operator's routing and abundance-source doors, with removal and surface insertion under FR-2 (D177). Most of part (b) is the coupling operator's channel target | A design note after D172's integrated landing; the closed loop's unit is the user's choice (below) |
| [FR-8](#fr-8--a-qualified-long-duration-mode) | A qualified long-duration mode | Priority 2 (the request's label; logged 14 November 2026) | Logged; it is the compute-limits gate's open long-time deliverable | Its acceptance gains an intervention applied during the slow phase; a long-time path for composite operators needs a design note (below) |
| [FR-9](#fr-9--raise-the-7-species-cap) | Raise the 7-species cap | Priority 2, **blocking for world design** (the request's label; logged 14 November 2026). Measured safe to 16 (the W4 probe) | **Landed** (14 November): `MAX_SPECIES` is 16, a D148 change to `species_common` with guard worlds of 8 or more species (D165) | The D148 change with a guard world of 8 or more species; the requester's species list comes with its world definition |
| [FR-10](#fr-10--a-dose-schedule-scheduled-bath-composition-in-the-pump-family) | A dose schedule: scheduled bath composition in the pump family | Priority 2, small (the request's label; logged 14 November 2026) | **Milestones 1 and 2 landed** (14–15 November; [note](BATH_SCHEDULE_DESIGN.md) §7–§8, D169): dose steps admitted only inside measured regions (neutral up and down, K up and Na down). Its protocol, `fr10-dose-schedule-v1`, is registered and judged on 17 November 2026: passed, 31 of 31 judged criteria (registration 407ba164), against the code-blind references R-faces, R-ion and R-records | Further ions and faster faces as each is measured |
| [FR-4](#fr-4--compartment-ph-a-proton-species-an-acidifying-pump-buffering) | Compartment pH: a proton species, an acidifying pump, buffering | Priority 1, blocking (the request's label; logged 14 November 2026). The request sequences it last of the block, after FR-1 | Design proposed in [the FR-4/FR-5 note](COMPARTMENT_PH_TRANSFER_DESIGN.md) (merged 15 November). Its kinds landed with D172's round (16 November), for development, not judged: the transporter with the proton pump, the rapid proton buffer, and the passive routes with the proton leak | Done: `fr4-acidification-v1` judged on 17 November 2026: passed, 21 of 21 judged criteria (D195; tag fr4-v1-qualified-2026-11-17) |
| [FR-11](#fr-11--looping-replay-packages-of-living-cells-for-the-viewer) | Looping replay packages of living cells for the viewer | Not stated (the user's request, logged 15 November 2026) | Logged, with the user's choices: periodic loops, a paced human heart cell, the minimal cells' cycle in scope. The heart cell is a human ventricular cell on Track E's human law set (D183); no generic stand-in, the lead's reading kept under the user's delegation (D184) | Partly built, on main with the run-view writer since 16 November: its design note (`docs/LOOPING_REPLAY_DESIGN.md`, ruled 16 November), the writer's loop block with its closure measure, and the planarian loop's builder (`validation/replay/`), with one development run of that loop, not judged. The human loop waits for the human cardiac laws |
| [FR-12](#fr-12--the-declarations-manifest-readable-by-the-viewer-d185) | The declarations manifest, readable by the viewer (D185) | Not stated (proposed by the visualizer session, 16 November 2026; logged 17 November) | Accepted: D185 already decided the manifest. It is being built in seam F of the core-seams pass (D195) | One command writing a versioned JSON file (`cells.declarations@1`) from the engine's registries at a revision |
| [FR-13](#fr-13--molecular-machines-individually-and-in-aggregate) | Molecular machines, individually and in aggregate, at a level of detail set by what is looked at | Not stated (the user's request, 17 November 2026; D204) | M0 now: the viewer's catalogue, as illustration. M1, ATP synthase, after the core-seams pass; no model yet (D209) | M1's build plan: [the design note](MOLECULAR_MACHINES_DESIGN.md) §10 |
| [FR-14](#fr-14--declared-extension-of-laws-operators-and-models) | Declared extension of laws, operators and models (object-oriented) | Not stated (the user's request, 17 November 2026; D205) | Requested; not scoped | Covered by FR-13's design note: options for a declared extends link, inherited checks and version rules |
| [FR-15](#fr-15--junction-crossing-and-charged-species-in-the-species-operators) | Junction-crossing and charged species in the species operators | Not stated (found by the gap-junction replication, D207; 17 November 2026) | Requested; awaits the user's go | First find why `check_impermeant` refuses, and whether D191's composition rule is the intended lift |
| [FR-16](#fr-16--junction-gating-and-availability) | Junction gating and availability: a two-state voltage gate, per-species floors, two-sided combination rules | Not stated (the same) | Requested; awaits the user's go | A short design after FR-15 |
| [FR-17](#fr-17--field-solves-beyond-2048-nodes) | Field solves beyond 2048 nodes | Not stated (the same) | Requested; awaits the user's go | The preprint's 3D table, and mitochondria (D210) unless condensing compartment nodes serves them |
| [FR-18](#fr-18--the-composites-energy-check-at-moderate-step-sizes) | The composite's energy check at moderate step sizes (a finding for the core) | Not stated (the same) | Reported to the core; the check is not loosened for one experiment | The core reviews the check's tolerance or its step-size advice |
| [FR-19](#fr-19--the-passive-routes-heat-share-sign-test-at-rounding-level) | The passive routes' heat-share sign test refuses rounding-level shares (a finding for the core) | Not stated (found by the gap-junction replication, D207; 17 November 2026) | Fixed on main (merge 49494e49): the raw-sum check's rounding floor; previously admitted steps bitwise unchanged. The band near 1 mM is closed too, landed by merge a7122a43 (18 November): the floor's scale is (\|μ̄_in\| + \|μ̄_out\| + 2)·\|m\|, and crossrev's kinds record was renewed at the landing (9 of 9) | None: closed |

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

**The design notes (proposed, 14 November 2026):** [CLOSED_COMPARTMENT_DESIGN.md](CLOSED_COMPARTMENT_DESIGN.md)
for FR-1 and [BATH_SCHEDULE_DESIGN.md](BATH_SCHEDULE_DESIGN.md) for FR-10.

### The first admissible delivery world

For the requester's world definition, which it is drafting now. It combines the two notes with D150's
two operators. It has no reactions inside, no binding sites and no pH.

**The operator list,** on `resolved_pump_composite@1` over `resolved_pump_tissue@3`, in this order:
1. `scheduled_bath_composition@1` (FR-10): the dose at a held bath, as neutral formula units at
   times on the dt grid after 0;
2. `cell_owned_compartments@1` (FR-1): each compartment's node, bounding patch and owner;
3. `scheduled_species_exchange@1` (D150): uptake into the cell, an import route on a patch that faces
   a finite extracellular node, which a face joins to the dosed bath; and loading into the
   compartment, an export route on the bounding patch;
4. `scheduled_species_turnover@1` (D150): clearance in the compartment (degradation), and if wanted
   at the extracellular node.

**The topology it needs:**
- Every cell keeps a patch on a held bath (the held-bath topology).
- The dosed bath is joined by a face to a finite extracellular node. Exchange refuses a patch on a
  held bath, so uptake runs from that node, not from the bath.
- Each compartment is a finite node with no face, faced by one bounding patch of its owner. The patch
  has zero ion permeability and no pump or channel. The content is electroneutral (a zero charge
  anchor): the cargo at a trace, the ions at a declared complement.
- **Species:** the ions and the neutral cargo, declared by `inventory_species.add_inventory_species`
  (valence 0, impermeant on every membrane and junction). **The cap was 7 in all** when this
  world was written (`species_common.MAX_SPECIES` at main's ced45c87). D165 raised it to 16 on 14
  November 2026.

**The refusals the definition meets,** each refused with its reason:
- **Exchange:** a route on a patch facing a held bath; a charged or permeant species; saturable
  loading (a saturable export); a negative rate; a schedule change off the dt grid; a provider of the
  volumes, the areas or the masks; more species than the cap; a donor copy whose route values differ
  from the slot's.
- **Turnover:** production at an outside node (production is at cells only); a route on a held bath.
- **The compartment declaration:**
  - a compartment node with a face, or one that is a held bath or the gauge;
  - more than one patch facing it, or a patch whose inside is not the owner;
  - an ion route on the bounding patch, or a nonzero charge anchor;
  - an owner whose capacitor component holds no held bath;
  - any operator outside its admitted list;
  - a replacement event on an owner's slot, or with an owner as its donor.
- **The bath schedule:** a target that is not a held bath; a net-charged formula unit; an event at
  time 0 or off the dt grid; a species that would not stay positive; water@1 with an anisosmotic step.
- **Refused beside this world,** each with its door in the notes: D152's reactions (door S), membrane
  state and FR-3's site occupancy (the membrane-state wall), FR-4's charged content (the charged
  door), water and what requires it, insertion, the partition, the bridge and the lumens.

**The onset.** A dose from nothing is D150's unresolved switch-on. FR-10's probe 1 measured it on the
engine as it is, in this world's topology ([BATH_SCHEDULE_DESIGN.md](BATH_SCHEDULE_DESIGN.md) §3.2):
- in a world whose ions move, it passes every check, with an onset-step energy residual of about 2%
  of that step's species flows, unseen;
- in a species-only world the energy ledger refuses it at row 1;
- loading the compartment from a trace books at rounding, by exchange's exact bookings.

So the definition can dose from nothing in a mixed world under the known limit, if the lead extends
D150's ruling to doses (FR-10 §3.2, way (a)). Guard worlds dose between resolved levels, at a step
ratio that registration pins; no probe has yet stepped a bath between two levels.

**Status.** Exchange and turnover exist; when this world was written, the declaration and the bath
schedule were designs, not code. Both have landed since: `cell_owned_compartments@1` (FR-1's
milestone 1, 15 November) and `scheduled_bath_composition@1` (FR-10's milestones 1 and 2, 14–15
November). Door S, which landed with D172's round (16 November), admits D152's reactions in the
compartment beside the dose, so they are no longer refused beside this world (door S's integration
world, `tests/unit/test_delivery_world.py`). FR-1's protocol is exchange's first judged acceptance.
Before the two operators landed, the same transport ran with the compartment as an anonymous
face-free node (D150's face-free world) and the dose as a bath held at the dose from time 0. That
form has no identity refusals and no dose time.

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

**The design note (proposed, 18 November 2026):** [MEMBRANE_RETRIEVAL_DESIGN.md](MEMBRANE_RETRIEVAL_DESIGN.md), with the energy source answered once for D150's question 11, D152's question 10 and D151 (D216).

**Answered 18 November (D217):** version 1 is retrieval and recycling, with "no new explicit machinery fuel draw in v1" and one lumped, well-mixed pool per cell. It starts when B1's operator part, with the split-and-merge kernel, lands (the note's §12).

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
  the law in `legacy/processes/membrane_injury.py`) is fixed-geometry injury on owned calcium tissue. Its
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
   - *Status (18 November):* **qualified for gate-free channel populations** by the coupling
     operator's judged protocol `coupling_regulated_availability_v1` (A5; 15 November, 47 of 47:
     V and the amounts at order 2.00, the factor exact to rounding, every control caught). Gated
     populations are not covered.
   - *Mapping:* probe P1, the channel path, was milestone 1's. Leaks and pumps are the note's
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
   - *Status (18 November):* **qualified for a gate-free channel population** by `fr6-a5pp-v1`
     (A5″; registration 555d8771, 18 of 18): two cells given the same regulator dose from
     s₀ = 0.1 and 0.8, V and the amounts at order 2.01 against R-cell, and every control that
     tells the two cells apart caught (the prior swapped, shared or ignored, the state bypassed,
     its rates 1% off, the basal level).
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

**The design note (proposed, 18 November 2026):** [ABUNDANCE_TO_FUNCTION_DESIGN.md](ABUNDANCE_TO_FUNCTION_DESIGN.md), framing the user's choice of the loop's unit (D216). **Answered 18 November (D217, D218):** U2 first, then U1; the loop is admitted through B1′; qualification needs a closed loop with a feedback-cut control (the note's §9).

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

**The design note (proposed, 18 November 2026):** [LONG_DURATION_MODE_DESIGN.md](LONG_DURATION_MODE_DESIGN.md), the long-time path for composite operators, written before the GH200 numbers and the benchmark specification (D216).

**Answered 18 November (D217):** stage 0 only, that is M1–M5 and a small harness, with criteria declared before comparison. The method follows stage 0 and the FR-18 probe (the note's §11).

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

**Landed 14 November 2026** (merge 2161f39, tier 1 and 2 with no changed outcome). `MAX_SPECIES` is 16.
The tier-1 guard is host-side (`tests/unit/test_species_cap.py`). The runner world `cell_charged_9`
is in tier 2 (`tests/unit/test_species_cap_runs.py`), since compilation alone takes about 15 s.

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
    (`legacy/core/surface_bath_events_binding.py`, policy
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

## FR-11 — Looping replay packages of living cells for the viewer

**Logged 15 November 2026, no priority stated** (the user: "we have four types of cells for
vizilation and that we are testing to different degreas in our upcomiung runs, human, planerian,
syn3a, bacteria - we'd like the engine part to prepare relativly high level simulation replay
packages so when you are not exploring some research with the viz tools the cell will be "alive" in
a loop").

**The request.** The viewer shows four cell types: human, planarian, Syn3A and a bacterium
(*M. pneumoniae*). For each, the engine prepares a relatively high-level simulation replay package.
The viewer plays it in a loop as the cell's resting state, whenever no research run is being
explored.

**The lead's mapping.**
- **It is output, not new physics.** Each package is a short run of laws the engine has, or gains
  through their own milestones.
  - It is written by the run-view writer (D154, [note](RUN_VIEW_DESIGN.md)), in its format.
  - It stays within the viewer's limit of about 1 MB per run.
- **High level means a declared low level of detail** (D175): lumped compartments and reduced
  representations. A package is labelled an illustration, never an experiment or a qualified result.
- **A seamless loop needs a periodic state.**
  - The physical way is a periodic drive, such as a pacing stimulus or a nutrient cycle. After the
    transient the response repeats, and one period loops, with the seam checked (the state at t + T
    against the state at t).
  - Playing the run back and forth, or cross-fading a stationary state, would be the viewer's
    choice, and is marked as such.
- **The four cell types differ in readiness:**
  - **Planarian:** the cue-written sheet's runs exist (E07-v1, W1).
  - **Human:** a cell type is still to be chosen. The viewer's human organ is the heart, so a paced
    cell would fit, with the channel laws it needs.
  - **Syn3A and *M. pneumoniae*:** neither has an organism definition yet (the
    [Syn3A note](SYN3A_MINIMAL_CELL_TRACK.md), D173). A first package would be a lumped single cell
    built from the engine's general laws (membrane potential, pumps, a small reaction set), labelled
    as such.
- **Sequencing:** after the run-view writer lands with D172's round. The per-species definitions are
  biological definitions, kept apart from engine mechanisms (ARCHITECTURE).
- **The user's choices (15 November 2026), after the options:**
  - **Loops are periodic:** a periodic drive, with one period played and its seam checked.
  - **Human is a paced heart cell.**
  - **For Syn3A and *M. pneumoniae*, the cell cycle is in scope as a loop** (grow, divide, follow
    one daughter), as an illustration, since division is prescribed.
  - **Timing:** after D172's round, at least to the stage where the run-view writer can carry the
    interim planarian loop. The planarian loop comes first.
- **Next:** a design note when the run-view writer lands (D142).
- **Since then (16 November 2026):**
  - **The human loop** is a paced human ventricular cell on Track E's human law set, O'Hara–Rudy
    2011's endocardial cell, and it waits for those laws (D183, D184;
    [design note](HUMAN_CARDIAC_LAWS_DESIGN.md), proposed). No generic stand-in is used: that was
    the lead's reading of the user's answer, kept under the user's delegation (D184).
  - **The run-view writer** did not land with D172's round. It merged into main later the same
    evening, on 16 November (050aa741).
  - **The design note** came with it, `docs/LOOPING_REPLAY_DESIGN.md` (ruled 16 November), with the
    writer's loop block, the interim planarian loop's builder and one development run of that loop,
    not judged.

## FR-12 — The declarations manifest, readable by the viewer (D185)

- **The request.** The visualizer session proposed it on 16 November 2026. Its full field list is in
  `visualizer/docs/LAWS_LIBRARY.md` §7.
  - One JSON file, written by the engine from its registries at a revision, with an entry for every
    registered law, operator and kind.
  - Each entry carries its id and version, interface, host and family; its provenance and
    citation; its declaring module; what it reads, writes and provides, with their roles; its
    ledgers and energy roles; its units and signs; and the models that declare it.
  - A status level is copied only from a record that states one, otherwise it is `null`.
  - Older families are listed by ID only and flagged legacy (D196).
- **Why it is general.** The viewer's laws library, the docs and the contributor guide read it, so
  contributed modules appear without hand edits (D185). The viewer never imports the engine: it
  reads the file.
- **The stable contract is the file's versioned format,** not any Python module (`cells.modules` is
  provisional, D195).
- **Status:** accepted, since D185 already decided the manifest. It is being built in seam F of the
  core-seams pass (D195).

## FR-13 — Molecular machines, individually and in aggregate

- **The request (D204).** It came from the user on 17 November 2026, first through the visualizer
  session, then to the lead directly.
  - **The viewer** gains a "Machines" tab: a catalogue of molecular machines gathered per species,
    as the proteins were.
  - **The engine** models them "both individuall and in aggregate in a cell or whatever, LODs based
    on what is being looked at".
  - **The first question is the user's:** "if there is something missing in our core archtecture
    or if they can be naturally modeled there".
- **Standing scope: D140.** Cells models the assembly of folded subunits into complexes and
  machines, from protein cages toward the proteasome and larger, and how the machines are used.
  Protein folding itself is not simulated.
  - On 16 November the user also asked for the nucleus, the Golgi apparatus and ribosomes "modeled
    to some extend, not protein folding level (yet)". That is recorded in
    `visualizer/docs/CELL_STRUCTURES.md`.
- **What exists today:**
  - membrane machines with laws: channels, pumps, exchangers and junctions;
  - `capsid_graph@1`, the first assembly case: one prescribed 20-site cage in a fixed bath
    (`docs/CAPSID_ASSEMBLY.md`);
  - `cells.assembly_lineages@1`, the stochastic assembly family built for GARD (D192, D197);
  - seam A's cycle contract: Hill cycles, the Wegscheider check and the J·ΔG guard
    (`docs/CORE_SEAMS_DESIGN.md` §16);
  - the relationship tables (`cells.relations@1`, D202) and the declarations manifest (FR-12).
  - **What is absent:** there is no model of a ribosome, RNA polymerase, ATP synthase, proteasome,
    translocon, flagellar motor, chemoreceptor array or attachment organelle.
- **The levels to scope.** This is the lead's framing, made with the advisor. A machine is one entity
  with three layers, not one model per machine:
  - **aggregate:** copy numbers and rates, with what the machine consumes and produces booked on the
    ledgers of the compartment it sits in;
  - **cycle:** the states of the machine's working cycle;
  - **assembly:** its subunits, their stoichiometry and the order they join.

  The level of detail follows what is looked at. So the layers must agree where they meet, and a
  switch between them must keep conserved accounting.
- **The first machines are chosen by constraint,** not by the catalogue's order:
  - the engine already carries what they consume and produce;
  - free-to-read data supports a judged check (D186, D201);
  - more than one organism target needs them.
- **Status (D209):** no model yet.
  - **M0 now:** the viewer's catalogue, labelled illustration.
  - **M1 next:** ATP synthase as general pieces, after the core-seams pass and D193's synthesis law.
    Its build plan is [`MOLECULAR_MACHINES_DESIGN.md`](MOLECULAR_MACHINES_DESIGN.md) §10.
  - The viewer's catalogue fields will follow what a declared model carries in the manifest once
    one exists.

## FR-14 — Declared extension of laws, operators and models

- **The request (D205).** The user asked on 17 November 2026, "is it possible to extend a model or an
  operator, like object oriently?", and then: "put the oo extension on the backlog".
- **What works today.** This was checked by planting subclasses in a scratch registry at seam F's
  registry head 6a0a9dc6, on 17 November.
  - A subclass of a law interface (`ChannelLaw`, built from `kv1p5_mh@1`'s fields) passes the law
    template's checks and registers under its own ID.
  - A subclass of a built-in operator (`OsmoticWater`) registers under a new ID. The operator
    contract checks it again at registration.
  - A subclass under a built-in `cells` ID is refused. Each built-in ID is one object, so a run
    cannot silently change meaning.
  - Models extend by composition. One composite model runs @3's step plus declared operators,
    and new combinations are definitions, not models (D143, under D142's design rule). D191 rules
    only how a composition reads fields.
  - A registry's `extended(...)` is a scoped copy with extra pieces planted in it. It is not
    extension.
- **What is missing:**
  - **A declared "extends" link:** the parent's ID and what changed, like a citation's departures.
    It would live in the registries and the declarations manifest, so the library and the viewer
    can show a family tree.
  - **Inherited checks:** the parent's contract and reference tests also run on the child.
  - **Rules for a child** when its parent moves to a new major version.
- **Why it is general.** It follows D142's object-oriented design. Molecular machines (FR-13) are a
  likely first use: one general machine cycle, specialised per machine.
- **Status:** requested; not scoped. FR-13's design note covers it, as part of the user's question
  about the core architecture.

## FR-15 — Junction-crossing and charged species in the species operators

- **Where it came from.** The gap-junction replication (D207) found it on 17 November 2026. In the
  public preprint 10.64898/2026.09.02.748840, a microRNA is made in cells and crosses gap junctions.
- **What refuses:**
  - **F1, narrower than first reported.** `species_common.check_impermeant` covers only @3's own
    constant-field junction route, for a species an operator writes.
    - A neutral species on the passive-routes kind (`cells.passive_routes@1`,
      `passive_neutral_permeation@1` on a junction host), made and destroyed by
      `local_species_reactions@1`, is admitted.
    - So the preprint's linear model runs as written, unqualified, converging at second order
      (dev-04). Its exact Norton equivalent serves as its check.
    - The first report said the model as written is refused. That was corrected the same day.
  - **F2:** the passive routes' neutral law carries valence 0 only, but the preprint's microRNA
    drifts with valence −1. The species operators also refuse charged species on @3's own routes.
- **Why it is general.** Any signalling species that cells make or use and that also crosses
  junctions needs it: second messengers, small RNAs, metabolites.
- **First step, done:** the reason for `check_impermeant`'s refusal was found (F1 above). What remains
  is F2.
- **Status:** requested; awaits the user's go. The lead recommends it first of the gap-junction
  features. (18 November 2026, D219: scheduled with the kinds and @3 owners after their current
  work. Not started.)

## FR-16 — Junction gating and availability

- **F3:** @3 hosts one junction law, `junction_voltage_relaxation@1`. The preprint's Cx45 gate needs a
  two-state voltage gate in the manner of Chen-Izu. The existing law's best fit is off by 0.05.
- **F4:** a junction has one minimum open fraction for every species. The preprint's microRNA curve
  needs a per-species floor (0); one floor for all is off by 0.11.
- **F5:** regulated junction availability combines the two sides only by product. The preprint
  needs min and mean as well.
- **Why it is general:** connexin-specific gating and permselectivity are general junction
  physiology.
- **Status:** requested; awaits the user's go. (18 November 2026, D219: scheduled with the F owner,
  after its per-law extractions, and with the @3 owner. Not started.)

## FR-17 — Field solves beyond 2048 nodes

- **F7:** the field solve is capped at 2048 nodes. The preprint's 3D table needs a 25³ field, 15,626
  nodes.
- **A second consumer: mitochondria (D210).** Compartment nodes count toward the cap, as cells and
  outside nodes do. K cells of N compartments, with B other outside nodes, allow
  N ≤ ⌊(2,048 − B)/K⌋ − 1: 2,046 for one cell in one bath, 126 per cell for 16 cells, and 14 for
  FR-1's 127-cell sheet. Any field-input provider, every event door among them, lowers the cap to 64
  field nodes ([MITOCHONDRIA_DESIGN](MITOCHONDRIA_DESIGN.md), addendum A.3).
- **A route that may fit compartments better than raising the cap:** condensing face-free
  compartment nodes out of the dense solve, which is exact. It is FR-1's condensation door, a new
  solver ID (D147; [CLOSED_COMPARTMENT_DESIGN](CLOSED_COMPARTMENT_DESIGN.md) §3.6, §8), and it also
  removes the 64-node cap's reason for compartment doors.
- **Status:** requested; awaits the user's go. Its consumers are the 3D table and, unless
  condensation serves them, mitochondria. (18 November 2026, D219: scheduled with numerics. Its
  owner is named when a seat frees, and FR-1's condensation door is the preferred route. Not
  started.)

## FR-18 — The composite's energy check at moderate step sizes

- **The finding.** @3's energy check (2e-3 under ARS(2,2,2)) refused neutral-species junction worlds
  at dt × rate from 0.08 to 0.31, well inside the stability bound of 1. Two dt studies show the error
  is second order, with a coefficient that depends on the world. The replication passed by using
  dt × rate ≤ 0.04.
- **What is asked of the core:** review whether the check's tolerance, or the step-size advice that
  goes with it, should change. It is not loosened for one experiment.
- **Status:** reported to the core.

## FR-19 — The passive routes' heat-share sign test at rounding level

- **The finding.** `passive_neutral_permeation@1`'s exact heat booking
  (`src/cells/kinds/passive_routes.py`, `_raw_sums` and `book`) refuses a step if any
  exact route's heat share is negative, with no tolerance. The raw-sum check beside it does allow
  `RAW_SUM_FACTOR` eps.
- **Where it showed.** The gap-junction replication's 1D tissue line has healthy cells that start
  identical, and its threshold search was refused at most coupling values.
- **The measurement.** A refused step was replayed with the engine unchanged
  (`/mnt/workspaces/Cells/gap-junction-20261117/probes/neither-fail-01/`):
  - share −2.1e-35 RT·fmol, about 40 times inside the raw-sum check's own bound for its terms;
  - transfer 4.8e-20 fmol, below the amounts' resolution;
  - potential difference 2 ulp of ln c.

  It is rounding, not a transfer against its gradient.
- **Scope.** FR-5's cargo routes use the same booking, so FR-5 can meet the refusal near equilibrium.
  FR-4's proton leak does not.
- **Fixed on main** (merge 49494e49, of branch `passive-share-tolerance` at 3d8e7b3b):
  - **The rule:** a share is refused only below `−RAW_SUM_FACTOR·eps` times its own terms, in the
    share's units. Admitted shares are booked as computed, so the ledgers close exactly.
  - **The gates:** G1 is 113 of 113; tiers 1+2 changed 0 of 514 files; FR's bitwise landing set
    passed. In crossrev only the kinds set's three checked steps differ, in the predicate, by design.
  - **The law keeps its ID** as an in-place fix (D148). Leaving qualified worlds on `@1` with a new
    `@2` stays the user's alternative.
  - **The replays:** the replication's previously refused points now run the full 20,000 s
    (`/mnt/workspaces/Cells/passive-share-tolerance-20261117/`).
- **Follow-up, the lead's call: the band near 1 mM, closed on branch `passive-share-band` and landed by merge a7122a43 on 18 November.**
  - **Why.** Near 1 mM the first floor still closed, since its terms scaled with |μ̄| while the
    potential keeps the ulp of ln c + 1.
  - **The fix.** The floor's scale adds the potential's evaluation rounding, (|μ̄_in| + |μ̄_out| +
    2)·|m|, so at 1 mM it is 32 eps |m|.
  - **On the closed pair:** all 47 rounding-level cases are admitted (leads of 1–16 ulp, 1e-4 to
    100 mM), the worst at half its floor. At 1 mM a share at twice its floor, or a million times
    below it, is still refused.
  - **Unchanged:** previously admitted steps, since the floor only moved down. The same gates
    apply, and crossrev's kinds record is renewed again at its landing.
  - The replication never reaches the band, since its concentrations stay at or below 0.1 mM.

