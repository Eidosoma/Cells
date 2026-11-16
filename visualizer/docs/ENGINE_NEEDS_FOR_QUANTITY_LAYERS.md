# What the quantity layers need from the engine: a note for the lead

Draft, 15 November 2026, from the visualizer. **Requests, not decisions.** The lead
decides whether, when and in what form.

The user chose seven of ten ideas for drawing what cannot be seen, and asked for this
note: "Lets do them all except wait with 8. 9. and 10. But draft a note in your docs
folder to Lead on what we need from the main engine, we're still designing and building
it so nothing of note has been run yet". So the note rests on what the models declare
and on the design notes, not on what a saved run happened to keep.

Read on main at **220d6e4d**: `docs/RUN_VIEW_DESIGN.md` (proposed, no code),
`docs/SCOPED_COMPOSITION_DESIGN.md` (door S, proposed), `docs/INNER_MODEL_V4_DESIGN.md`
(§7, §9, §10, §12, §15.2), `docs/ARCHITECTURE.md` ("The modular core"), and the code
named below. The viewer's side is `visualizer/schema/QUANTITY_LAYERS.md`.

## In short

- **No new physics is asked for.** Every number the seven layers draw is already a state
  field or a readout of the tissue model.
- **The engine's own output already carries them.** The shared output paths write every
  state field and every readout at each observation time. The cumulative ledgers among
  them (amounts transferred, pump cycles, energy dissipated) are the right feed: a
  ledger's difference between two records is the true mean rate between them, which a
  flux sampled now and then is not.
- **The run view as designed already covers most of a record's declaration:** what it
  lives on, its unit, its axes, its times, its layer, how the layer is represented, its
  owner, the events and the geometry.
- **Three things a layer needs are not in that design:** which way a signed record is
  positive, what kind of number it is, and its owner down to the law.
- **Two of the viewer's four derivations read values that operators may change** (a
  volume, a capacitance, a held bath's composition). Either those are saved as the run
  had them, or the engine saves the finished terms. That choice is the lead's.
- **One small run is asked for as a first real feed.** Until one exists, three layers
  are shown on examples with invented numbers, marked as such and kept apart from the
  experiments.

## The seven layers and what they read

All fields are of `resolved_pump_tissue@3` and its family: state in `STATE_AXES`,
readouts in `OBSERVATION_FIELDS` (`src/cells/models/surface_tissue.py`,
`surface_kinetic.py`, `surface_pump_v3.py`). Units are as the names and the model guides
give them; the code declares no unit table for this family yet.

| Layer | Draws | Reads | Where it is today |
| --- | --- | --- | --- |
| Voltage relief | each cell as high as its voltage | membrane voltage | readout `membrane_voltage_V`, per membrane, V |
| Junction drops | the voltage difference across each junction, and how open it is | the two cells' potentials; the junction's open fraction | readouts `cell_potential_V` per cell and `junction_voltage_V` per junction, V; state `junction_gate`, readout `junction_availability` |
| Push and pull on each ion | the two terms of the electrochemical potential, per ion | concentration on both sides of one membrane, its voltage, the temperature, the valence | readouts `amount` (species, cell) and `extracellular_amount` (species, outside node), fmol; volumes, pL; the definition's temperature and valences |
| Charge on the membrane | the charge a voltage stands for | capacitance, area and voltage of one membrane | `membrane_capacitance`, F, and `membrane_area`, m², with the voltage |
| Ion traffic | beads through channels and pumps | amounts transferred, and pump cycles, since the start | state `channel_transferred` (species, channel population), `membrane_transferred` (species, membrane), fmol; `pump_cycles` and `calcium_pump_cycles` (membrane), fmol of cycles |
| Where the energy goes | a glow where energy is dissipated | energy dissipated since the start | state `membrane_`, `channel_`, `junction_`, `face_` and `pump_dissipated_energy_pJ`, with `metabolic_work_pJ` |
| Signal fog | a secreted species spreading and fading | that species' amount per cell and per outside node | its rows of `amount` and `extracellular_amount`, with the volumes |

## What the run view already gives, and what is still missing

The viewer's contract asks eight things of every record. Set beside
`docs/RUN_VIEW_DESIGN.md`:

| A record's | The run view, as designed | Still missing |
| --- | --- | --- |
| id and file | §2: every array of the record file, by file and array | nothing |
| what it lives on | §1, §2: every column names its entity or is padding; every axis maps to a set | nothing for cells, membranes, junctions, channels, outside nodes and faces. Pumps are columns of the membrane set: request 6 |
| unit | §3: a `UNITS` table with a suffix rule; a test fails without one | nothing |
| times | §2: several time bases, each record naming its own | nothing |
| layer and how it is represented | §3: `VIEW_LAYERS`, with no default | nothing |
| owner | §1, §3: the layer and owner of every record, from the composition's field map | the law, for a record of one population: request 4 |
| sign | not there | request 2 |
| kind | not there | request 3 |

## The requests, in the order of what they unlock

### 1. Runs that are to be shown keep the standard history

- **Needs:** the ledgers and readouts of the table above, at a modest cadence.
- **Why:** ion traffic, the energy glow and the signal fog have nothing to draw without
  them; the other four layers draw from the same arrays.
- **The engine has:** all of it. `io.write_run` writes every state field at every
  accepted time and every readout at each observation time into `trajectory.npz`. The
  windowed path writes the same per window, by its recording policy: full, observations
  or checkpoints (`window_io._write_window_chunk`, `core/windows.py`). The readouts
  include every state field. What is slim is the experiments' own drivers, which write
  record files of their own.
- **Asked:** that a run which is to be shown goes through a shared output path with
  observation times, or that its driver keeps these fields and describes them through
  `write_view` (RUN_VIEW_DESIGN §4, and its question 3 to the lead). And one question:
  recording is all or nothing per run today. Would a run be able to name the fields, the
  elements and the cadence it keeps for viewing, so that a long run on a large sheet
  need not keep every ledger of every element?
- **Until then:** the viewer packages what a run kept, and lists a layer whose record a
  run lacks as "this run did not save it".

### 2. Which way a signed record is positive

- **Needs:** for every signed record, its two ends and the positive direction.
- **Why:** beads must move the right way, the arrows of push and pull must point the
  right way, and a wedge must point down the drop.
- **The engine has:** the convention, in code and in words, not as a declaration, and
  not one convention. In the tissue family a route runs from a source to a destination:
  a membrane from its cell to its outside, a junction and a face from sender to receiver
  (`numerics/surface_transport.py`), and `balances` closes each compartment with the
  transfer added to the increment, so a positive transfer leaves the source. The
  single-cell contract says the opposite for its flux: "positive from bath into cell"
  (`docs/BIOELECTRIC_CELL_SPEC.md`). I read the first from code and may have it wrong,
  which is the reason for the request.
- **Asked:** a declared orientation beside `UNITS` and `OBSERVATION_AXES`
  (RUN_VIEW_DESIGN §3): for each signed field, from which set to which, and which is
  positive. The compartment map's oriented endpoints (INNER_MODEL §9.2, "inside →
  outside") look like the natural source for membranes.
- **Until then:** the viewer shows the size of a transfer and no direction. Where it
  must show one, it uses the reading above and says in the legend that the direction is
  the viewer's reading.

### 3. What kind of number a record is

- **Needs:** one of four kinds for each record: a level (a voltage), an amount, a
  cumulative total, a rate.
- **Why:** the viewer may difference only a cumulative record, and may move something
  only where a rate stands behind it. A wrong kind would draw a flow that is not there.
- **The engine has:** the idea, as a target. Each state field is to declare its
  evolution role: continuous dynamical state, algebraic state, accumulated history,
  discrete event state (ARCHITECTURE, "State roles and time"; INNER_MODEL §12, list (b)
  item B1, with FR-8's milestone). Accumulated history is the viewer's cumulative.
- **Asked:** that the run view carries the role once B1 lands, and says of each readout
  whether it is an instantaneous value. If a small table in the view's writer could
  state the kind before B1, as `UNITS` states the unit, the layers would not wait for
  FR-8.
- **Until then:** the viewer keeps its own table of kinds for this model family, by
  field name, and marks it as its own reading.

### 4. The owner, down to the law

- **Needs:** for a record of one channel population, pump, junction or membrane: the
  law that computed it, and how sure that law is.
- **Why:** every layer's legend says what stands behind the number.
- **The engine has:** the owner of each record as a model or operator (RUN_VIEW_DESIGN
  §1, §3). The definition names each population's law. The rework gives each law a
  declaration with its `law_id` and its `provenance`: parity, cited or calibrated
  (INNER_MODEL §7.1, §7.4 (b)).
- **Asked:** that each entry of a set carries its law's id, and its provenance once
  declared, so the viewer does not parse definitions family by family.
- **Until then:** the viewer reads the law's id from the run's definition by the
  element's id, for the composite family only, and shows no provenance.

### 5. The values two derivations read: saved as the run had them, or the terms themselves

- **Needs:** for push and pull, the concentration on both sides of a membrane, its
  voltage, the temperature and each ion's valence. For the charge, the membrane's
  capacitance and area with its voltage.
- **Why:** the contract lets the viewer work out two things itself. The potential terms
  are the engine's own `electrochemical_potential`: R T (ln ci − ln co) + z F V
  (`src/cells/processes/electrochemistry.py`). The charge is capacitance times voltage.
- **The engine has:** the inputs, but not all of them are constants of the definition.
  The model forms a concentration as reference plus increment over the volume
  (`physical_amounts`, then `ci / p.volume`), and operators may change those view
  fields: the bath schedule replaces a held bath's reference amounts, the lumens and
  water change volumes, and membrane state provides capacitance and area (door S, §2
  and §5; INNER_MODEL §9.1).
  The readouts `amount` and `extracellular_amount` are the run's own values; the
  volumes, capacitance and area over time are not readouts today.
- **Asked, one of two:**
  - **(a)** that a view field a layer reads is written as a record whenever some
    operator of the composition declares a change to it, and is a named constant of the
    definition otherwise. Door S already makes that test from declarations, field by
    field (§2), and has an `observe` stage whose merged view would be the value to
    write. Or
  - **(b)** that the engine saves the finished terms as readouts: for each ion at each
    membrane the chemical term and the electrical term, in J/mol, and the charge of each
    membrane, in C. The viewer then derives nothing here.
  Which would the lead rather have? (b) keeps the physics in one place; (a) is more
  general and smaller.
- **Until then:** the viewer works these out only for runs whose definition has no
  operator that changes those fields, and the legend says "worked out by the viewer
  from" with the inputs.

### 6. What one pump cycle moves

- **Needs:** for each pump, the ions it moves in one cycle and which way.
- **Why:** `pump_cycles` counts cycles. Beads for sodium and potassium need the three
  and the two.
- **The engine has:** it as layout values (`stoichiometry`), and the rework's pump law
  declares "the rows it moves per cycle by role" (INNER_MODEL §7.4 (b)).
- **Asked:** that the view states it for each pump, and says how pumps are named: as a
  set of their own or as columns of the membrane set.
- **Until then:** a pump's beads count cycles, and the legend says so.

### 7. One name for each species

- **Needs:** for each species row: its name, its valence and what it stands for.
- **Why:** each ion has one colour and one name everywhere in the viewer, and the fog
  must name its signal.
- **The engine has:** the species' ids and valences in each definition. Identity is to
  be consolidated at the definition boundary (ARCHITECTURE, "Material identity and
  fuel"; INNER_MODEL §10.2, with the registry of D176's round).
- **Asked:** that the run view carries each species' identity from that one authority.
- **Until then:** the viewer shows a definition's own ids as they are and guesses
  nothing about what a generic row stands for.

### 8. A record that spans several files

- **Needs:** to read one record across a run's window files without loading the rest.
- **Why:** a layer's numbers come in a file of their own beside the replay, fetched when
  the layer is switched on, so that a replay stays near 1 MB. The viewer's packager cuts
  those files from the run's arrays; nothing is asked of the engine's writer but names.
- **The engine has:** window chunks, one file per window, and a view that names each
  record by file and array, with a time base of its own (RUN_VIEW_DESIGN §2, §4).
- **Asked:** how the view will name a record that lies in many chunk files: one entry
  with a list of files and row ranges, or one per chunk? Either works; the packager
  needs to know which.
- **Until then:** nothing depends on it. The runs the viewer has are single files.

### 9. A first real feed

- **Asked:** when it suits the engine's work, two small runs that keep the standard
  history at a modest cadence:
  - a sheet of a few dozen cells with a written voltage pattern, on
    `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with observation times a
    few seconds apart;
  - one small world with a secreted species, on D150's operators
    (`scheduled_species_exchange@1`, `scheduled_species_turnover@1`).
- **Why:** they would show five layers on engine numbers for the first time, and test
  requests 1 to 7 on real arrays before the run view's writer is built.
- **This is a request.** The lead decides whether and when, and whether such a run is a
  milestone at all. Nothing in the viewer waits for it.
- **Until then:** ion traffic, the energy glow and the signal fog are shown on examples
  with invented numbers, which stand under "Examples", never among the experiments, and
  carry "Example: invented numbers" on the picture and in the legend.

## Questions on the modular rework

The rework is in development on a branch and not on main. These are questions.

- **Owners as declared laws.** Will a law's `law_id` and `provenance` be readable from
  the definition's side, where the run view's writer assembles its declarations, or
  only inside the compiled structure? (Request 4.)
- **Levels of detail.** A law that stands in for something is to declare what it
  represents and where it is qualified, with an error budget (ARCHITECTURE, "Levels of
  detail"; INNER_MODEL §7.1, reserved as B8). Could the run view carry those fields for
  a record's law? A legend could then say how exact a number is, in the engine's words.
- **Compartments.** The compartment map gives each owned compartment a role (cytosol,
  lysosome, vesicle, ER, mitochondrion) and an owner cell, while its storage is an
  outside node (INNER_MODEL §9.2, B2, partly on main). Could a set's entry for such a
  node carry the role and the owner? The viewer would then draw a record on the right
  part of the cell.
- **Exact heat booking.** With `exact_free_energy_heat@1` (INNER_MODEL §7.5), does a
  route's heat stay a cumulative total per element that never falls? The energy glow
  assumes so.

## Not asked now

The three ideas the user set aside would each need more. They are listed so the lead
sees them coming, with nothing to do today.

- **Field between cells** (idea 8): positions for outside nodes and faces, where a world
  resolves the space between cells, as the builders give positions for cells.
- **Tension web** (idea 9): geometry that moves. The run view already foresees it as a
  record with the role of geometry (RUN_VIEW_DESIGN §6).
- **Wavefront** (idea 10): a short window of records at fine time steps around a fast
  event. The view's several time bases already allow it.

## What the design notes already answer

Nothing is asked for these; they are what the layers were built to expect.

- Identity of every column, units, axes, time bases, layers, representation, owner by
  operator, events with their entities, geometry from the builders (RUN_VIEW_DESIGN
  §1 to §4).
- That every state field and readout is written at each observation time by the shared
  output paths (`io.write_run`, `window_io`).
- Evolution roles, the compartment map with oriented endpoints, the law declarations
  and the reserved levels-of-detail fields (INNER_MODEL §12, §9.2, §7.4 (b), §7.1).

## The lead's answers (15 November 2026)

The lead read this note at `d0201f3a` and answered the same day. Requests 1 to 8 go to
the owner of the run view's writer as requirements, in the round of the modular rework.
Nothing of this is on main yet.

| Request | Answer |
| --- | --- |
| 1. Standard history | Yes. A run that is to be shown goes through a shared output path with observation times, or its driver describes its records through `write_view`. A declared recording subset (fields, elements, cadence) is accepted as a requirement on the writer, and the view records the subset |
| 2. Direction of signed records | Yes. The view declares, for each signed field, its from-set, its to-set and which way is positive, beside `UNITS` and `OBSERVATION_AXES`; membranes take theirs from the compartment map's oriented endpoints. The owner of the core confirms this note's reading of the tissue family when the table is written: the legend keeps its caveat until then |
| 3. Kinds | Yes. A small table in the writer (level, amount, cumulative, rate), like `UNITS`; once the evolution roles land, the kinds come from them |
| 4. Owner down to the law | Yes. Each entry of a set carries its law's `law_id`, and its provenance once declared; both are readable where the writer works |
| 5. Inputs of the two derivations | Choice (a): a view field is written as a record whenever an operator of the composition declares a change to it, and is a named constant of the definition otherwise. The two potential terms stay the viewer's declared derivation |
| 6. Pumps | Yes. The view states each pump's rows per cycle by role, from its law declaration. In version 1 pumps stay columns of the membrane set, and the view says so |
| 7. Species | Yes. Each species' identity comes from the species registry (on the integration branch) |
| 8. Records over several files | One entry for a record, with a list of file and row range |
| 9. A first real feed | Approved by the user the same day, as the lead reported: two small development runs through existing drivers and the shared output path, keeping the standard history at a modest cadence (a sheet of a few dozen cells with a written voltage pattern; one small world with a secreted species). They are development runs, not experiments, and apart from the user's further request for looping replays of each species' cell |

The four questions: law declarations are readable from the definition's side; the
levels-of-detail fields will be carried for a record's law when they land; a set's entry
for a compartment node will carry its role and owner from the compartment map; whether a
route's cumulative heat never falls under the exact heat booking is asked of the core's
owner, answer to follow.

### From the owner of the core, through the lead (15 November 2026)

- **Signs in the tissue family: this note's reading is right.** A positive
  `membrane_transferred` leaves the patch's cell for its outside node.
  `channel_transferred` is added unchanged into its patch's membrane total, so it has the
  same sign. A positive junction or face transfer leaves the sender for the receiver.
- **Two exceptions.** Pump cycles are positive inwards (stoichiometry times cycles, which
  the balance subtracts from the membrane total). `reservoir_supplied` is positive into
  the outside node.
- The single-cell specification's flux, positive from bath into cell, is that model's
  own convention.
- **Heat.** Every `*_dissipated_energy_pJ` field that exists today is checked to be zero
  or more and never to fall, per element, at each accepted row (with an allowance of
  1e-12 pJ); a run that would lower one is refused. So the energy layer may take them as
  totals that only grow. Under the exact booking of the rework a route's own share can
  be negative while its row's total is not: whether a route's heat still only grows
  there awaits the lead's ruling.
- **The lead's ruling on heat under the exact booking (15 November 2026).** A route's heat
  stays a total that only grows: in the rework's first version a step with any negative
  share for a route is refused, so every `*_dissipated_energy_pJ` field stays zero or more
  and never falls per element, as today. A value for one route is an exact attribution of
  its row's fall in free energy between the routes that move it; it cannot be measured
  apart, and the energy layer's legend says so wherever it shows routes and not elements.
  Elsewhere (pumped rows, tableau-booked routes) today's booking and checks are unchanged.

### The first real feed (15 November 2026)

- **Ready:** one development run of a secreted species, written through the engine's
  shared output path from snapshot 5c2b04d6: one passive cell secretes a species into a
  finite node that leaks to a held bath (`scheduled_species_turnover@1` and
  `scheduled_species_exchange@1`; 4 s at a step of 1 ms; 21 records 0.2 s apart). It is
  kept under `/mnt/workspaces/Cells/viewer-feed-20261115-01/secreted-species-dev-run/`
  with a note that says "development run, no verdict". It is the first run the layers'
  reader meets that the engine wrote by its own writer.
- **Not yet:** the sheet with a written voltage pattern. Neither existing sheet builder
  writes one through the shared writer unchanged, so it comes with the run view's writer
  in the rework's round. Until then ion traffic and the energy glow on a sheet are shown
  on examples with invented numbers, marked as such.

### The worked example of the run view, read by the layers (15 November 2026)

The engine's run-view writer was shown on a worked example: a `view.json` for the
development run above (`run-view-20261115-01/secreted-species-dev-run-view-01fa27d9`).
The viewer's adapter now packages a run from such a view and from nothing else: under a
view it uses none of its own tables and reads no kind and no sign out of the arrays
(`schema/RUN_VIEW.md`, "A run with the engine's own view beside its files"). Read that
way, the worked example feeds the fog, the beads across the face and the glow. What it
cannot feed is listed here for the writer's owner. **Items 1 and 10 change a picture;**
the rest are smaller. The lead answered items 1 and 10 the same day, as written under
each; items 2 to 9 and 11 are in the queue of the run view's writer, after the modular
rework lands.

1. **`exchange_moved_fmol` has no `kind` and no `sign`** (on both time bases). So it gives
   no rate, and the two exchange routes get no beads: on this run that is the whole of "a
   species leaving the cell". Needed: `kind: cumulative`, and a sign by the roles of the
   route's membrane patch (`inside`, `outside`). The run's own amounts add up with a
   positive total read as leaving the cell, for the export route and for the import
   route alike, and under no other reading. The published page shows this run packaged
   with the viewer's own table, which draws the routes by that reading and says that it
   is the viewer's; a word from the core's owner would let the legend say "confirmed".
   **Answered by the lead the same day: yes, that is the convention.** The total is
   cumulative and positive outwards, from the inside of the route's patch to its outside,
   for both directions: an export route's value is nought or more and an import route's
   nought or less, and the operator's own domain check enforces it
   (`src/cells/models/operators/species_exchange.py`: the state's axes mark the field
   "Export positive", and the validity rule asks for a total of nought or more on an
   export and nought or less on an import). The writer will declare it (`kind:
   cumulative`, a sign by roles, with item 2). Until it does, the page says that the
   direction is the engine's convention, confirmed, and no longer the viewer's reading;
   the adapter still draws it only where the run's amounts agree.
2. **The writer's `SIGN_ROLES` has no entry for `exchange_route`,** so its own reader would
   refuse a sign on that record as things stand.
3. **No route states the species it carries.** `exchange_route` has ids, the membrane each
   lies on and its owner, and the record has no species axis. A bead needs the species
   for its colour and its name. (The run's `summary.json` does name each route's species
   and declared direction; the viewer's own table reads it there.)
4. **The turnover ledgers have no `kind`** (`turnover_produced_fmol`,
   `turnover_cleared_fmol`, `turnover_outside_cleared_fmol`; the view lists them under
   `unstated`). The page shows the saved numbers and can neither call them totals since
   the start nor take a rate of them.
5. **The voltages have no sign** (`membrane_voltage_V`, `junction_voltage_V`: "not
   confirmed"). The push and pull on ions, the membrane charge and the junctions' own
   drops need to know which side is the higher when the value is positive. The viewer's
   own table reads that from the arrays (the cell's potential less that of its outside),
   which it does not do under a view.
6. **Nothing marks the secreted species.** The viewer takes the species whose identity
   names an operator of the run as its source, and says that this is its own reading.
7. **Which entities restart at a retirement.** `resets` names the retiring laws and the
   events name cells. Nothing says which entities outside the cell set restart (a
   membrane of the cell, a channel population, a junction to a neighbour, a face). The
   viewer assumes the cell, its membranes and what lies on them, and its junctions;
   anything it cannot trace to a cell gets no rate in an interval that holds such an
   event.
8. **An event at a record's own time.** The view does not say whether the row saved at
   that time shows the state before the event or after it, so the viewer takes no rate
   in either interval the event bounds.
9. **Geometry is null** (no builder for this world), so the three tiles are the viewer's
   own layout, and the page says so. Nothing to change; only to know.
10. **A question on `membrane_transferred`.** The view's sign on `channel_transferred`
    says "added unchanged into the patch's membrane total", as the core's owner said
    above; the view's note on `membrane_transferred` says "the passive membrane routes
    only: each channel population's and each pump's transfers are their own ledgers".
    The viewer rests on the note: on the close-up of a cell it draws the channels'
    totals, the pump's cycles and `membrane_transferred` as three ledgers side by side.
    If the saved `membrane_transferred` did contain what the channels carried, that
    picture would count the channels twice. Is "the patch's membrane total" in the
    sign's words the balance's sum, and not the saved array? Until a saved run of a
    sheet carries these totals the close-up is shown on an example only, so no real
    picture rests on the answer yet.
    **Answered by the lead the same day: yes.** The saved `membrane_transferred` holds
    the passive membrane routes only. "The patch's membrane total" is the balance's sum
    when the balance is checked: `membrane_transferred` plus `channel_transferred` mapped
    to its patch. The pump's moves are a third, separate term (its stoichiometry times
    `pump_cycles`). Drawing the channels, the pump and the membrane side by side counts
    nothing twice.
11. **Reading notes, not gaps.** The view has no `id`, no `arm` and no end state for the
    run: the catalogue names it, and how it ended still comes from `summary.json`. The
    run's own files name no revision of the engine by its commit (the note beside the
    folder does), so the page gives none for this run. A
    recording subset (`recording.subset`) is refused by the viewer's adapter until there
    is an example of one, and a builder's geometry in a view is not read yet for the same
    reason.

### What a species' looping run must carry (16 November 2026)

Flux in the Cell view is published. No species has a looping run of its own yet, so it
shows as illustration ("Illustration: not a run", direction only). The first real flux
there needs a run the engine made of one cell of a species, packaged to loop
(`schema/QUANTITY_LAYERS.md`, rule 7). The viewer's reader refuses a run as a loop unless
all of this holds, so that a run written the way the development run of 15 November was
would be refused:

- **`loop` in the run's view** (`schema/RUN_VIEW.md`): `{"species", "cell", "closes":
  {"within", "says"}}`. The species by the viewer's id (`human`, `planarian`,
  `fruitfly`, `syn3a`, `mpneumoniae`, `ecoli`, `thalecress`), the cell's id in the run's
  set of cells, and the run's own word that its last record meets its first: the largest
  relative difference of any level between the two, and a sentence the page may show.
- **The engine's models and its revision** (`run.engine_models`, `run.revision`). The
  development run names no revision in its own files (item 11 above, then a reading
  note). For a loop that is a gap: a run with no revision is refused.
- **Not an example.** A run with invented numbers is never a loop.
- **The totals whose rates feed the beads,** each with its kind and its sign as the run
  view declares them: what crossed through each channel population, the pump's cycles
  with what one cycle moves, and what crossed the membrane itself. Those three are read
  today. What crossed junctions, water, the exchange routes and fuel is not read from a
  loop yet; where a run carries them the page names them as not read.
- Every rate is a mean between two records that both lie inside the loop; no difference
  is taken across its seam.

### The lead's news on the format (16 November 2026)

The run view's writer has moved on, on its branch (`run-view-d154`, RUN_VIEW_DESIGN §9);
it lands on main after the modular rework. The eleven items above are answered there.
What the viewer's reader has to take, when it lands:

- **`view_<field>` records:** the merged view of each field that an operator changes, for
  each observed row.
- **Roles on sets,** in place of the writer's table of sign roles.
- **`difference` beside `sign` for voltages** (plus, minus, says): the membrane's voltage is
  the cell less its outside node; a junction's is the sender less the receiver. This
  answers item 5.
- **`carries`, `direction`, `kinds` and `at` on an operator's sets:** an exchange route then
  states its species and its direction (items 1 to 3).
- **`resets.mask`:** which entities restart at a retirement (item 7).
- **`time.event_rows`:** a row saved at an event's time holds the state before the event
  (item 8).
- **`run.id`, `run.end` and `run.source`:** the engine's revision and whether its tree was
  clean, from the execution snapshot (item 11).
- Geometry stays the caller's input (item 9).

**The loop block** (FR-11, `docs/LOOPING_REPLAY_DESIGN.md` on the same branch; proposed,
nothing built): `loop: {"species", "cell", "period", "closes": {"within", "says",
"tolerance"}, "follows"?}`. The writer measures `within` on the saved arrays and refuses a
block without `run.source`. The revision is read from `run.source.revision`, the one
source of truth; the viewer's packaged replay fills its own `run.revision` from it.
`follows` is for a cell cycle: the cell the loop follows after a division. The order of
the loops: a planarian patch loop first, then a paced generic excitable cell labelled
"not a human cardiomyocyte model", then the minimal cells' cycle.

The viewer's side of this is not done yet: the page's loop reader is being brought to the
block's shape, and the adapter's reading of a view takes the additions when the writer is
on main.

