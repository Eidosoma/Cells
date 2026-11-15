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
