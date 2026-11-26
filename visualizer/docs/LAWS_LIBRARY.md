# The Laws shelf as a 3D library: what the engine declares, five options, and a recommendation

Ideas and options for the user, 16 November 2026. The page beside this note,
[`docs/ideas/laws-library.html`](ideas/laws-library.html), draws each option live from the list
of pieces this note describes.

**Since 17 November 2026 the racks are built, and read from the engine's declarations.** The
engine's manifest (`cells.declarations@2`, its format the engine's page
`docs/library/DECLARATIONS_FORMAT.md`) is the whole truth of what the engine declares, the lead
ruled that day; what no active registry declares came off the wall. The list is made from that
file alone (`tools/extract_laws.py`, `data/engine/declarations.json`), and its contract is
`schema/LAWS_LIBRARY.md`. At main 93fc8c2c the wall holds 61 pieces (32 laws, 5 kinds, 24
operators), seven racks and four model families with no rows, with the 13 laws design notes name
apart; the 154 pieces of the code's reading at fa19d80c, the counts below, the engine's file
paths below (read before the engine's two source moves of D188) and the sketches' lists are this
note's record of 16 November, not the wall's. The wall is shelved by interface, the operators by
their part of the step, and a model family's own laws and operators each on a shelf of their
own, on one band (the stills weighed are kept with the hand-over of that round).
In the inner model's rack a row too long for a line goes on under it, six slots to a line, and the
rack's height is shared by lines: since main 1ca5eada its eleven channel laws and the free socket
stand on two lines (`src/lenses/laws_layout.js`; a test holds every slot inside its rack at thirty).
Since main 93fc8c2c a cycle law's card says its general form in words, key by key, and never pours
its data (`schema/LAWS_LIBRARY.md`, "A cycle law's general form").

**26 November 2026.** The v59 atlas reads declarations format 3. The family view groups
assembly geometry and events, reactions and free energy, and regulation and rate factors
into three pods. A selected family can map its cross-family relationships, with the individual
declarations available to trace. Shared addresses use the published ID move table.
The Engine view reports declared fields. Resolved writer and sole-writer rows depend on a
world's species and node configuration and require an export from that world.

**What a unit of the Protein atlas says of a law no active model declares (18 November 2026).**
On 17 November 2026 the project decided to port tested older laws to the active engine (D211),
and the engine's lead made a read-only inventory of the 54 law IDs behind the 38 units that open
no declared piece (`cells.law_port_inventory@1`, made 17 November 2026 at `72409622`, kept at
`/mnt/workspaces/Cells/law-port-20261117/`). Each of its rows carries one of three marks. The
viewer's table of it, `data/laws/law_port.json`, is made from the inventory by
`tools/extract_law_port.py` and holds for each row only the law, its units, its mark and its
tests' class, with the inventory's kind, date and head. A unit's panel says, in one line for each
mark and with no door, the mark's words after the laws' names (`src/lenses/law_port.js`): 47 laws
are marked "port as is", 5 "fold into an owner's planned law" (all five the cardiac lane's), and 2
"not a port", each of those two with words of its own. A door still opens only a declared piece, whatever the table says: since main 1ca5eada Seven of
its rows' laws, five Kv1 laws, CaV1.2 and electroneutral symport, are declared, and those units open them. The
14 laws on the atlas's units that the inventory has no row for, all on seven of the 15 units that
open a declared piece, keep the earlier words: the engine's declarations do not list them.

The user, 15 November 2026: "one idea for the backlog not now: for the Engine shelfs maybe we need
to make the Laws shelf clickable into a cool 3D library :)", because "there will be so many". And on
16 November 2026: "open the Laws shelf as a 3D library, to tie it to the modular structure frmo the
Engine".

## In short

- **Recommendation: the racks.** Model frames stand in front, each with a slot for every piece the
  model declares, and the whole library stands on a wall behind them, a bar for each piece in its
  family's column. Choose a piece and lines run to every slot it fills; choose a frame and its
  pieces light. It is the only option that draws how pieces plug into a model (the user's second
  sentence), and it still holds a thousand pieces (the first). Its index is the card catalogue's
  search, and the plain list is its stand-in where 3D cannot be drawn.
- **What the engine declares today.** The page's list holds 176 pieces: 150 on main, 13 on the
  landing candidate (`integration-d172`, not on main yet), and 13 named only in design notes.
- **Status is not kept per piece anywhere.** The plan keeps it per item. The sketches show no
  status; an opened piece shows a status only where the Engine view's overlay records one, with
  its source, and says "no level recorded" everywhere else.
- **The declarations manifest that D185 adds** (main, 16 November 2026) is what the library
  should be drawn from. A draft feature request with the viewer's fields is at the end of this
  note, for the lead.

## Refs read

| What | Ref | Notes |
| --- | --- | --- |
| main, code | `98c49993` | At `9a15108e` (15:34 UTC), and again at `cdeb0f04` (16:12 UTC), `src/cells` is unchanged (`git diff --stat 98c49993 9a15108e -- src/cells` is empty). D185 and the manifest entered the docs at `dff29f3b` and `33617054` |
| Landing candidate | `integration-d172` `3c10b833` | Not on main when read (`git merge-base --is-ancestor 3c10b833 main` false at 14:58, 15:34 and 16:12 UTC); the lead expected it to land about 17:00 |
| Development branches | `core-next` `17a3863b`, `run-view-d154` `fd008813`, `cardiac-laws` `59ae93e3`, `core-d172` `2c780f9f` | Not on main |
| The Engine view's map | `data/architecture/architecture.scene.json`, extracted at main `20107cd2` | Operators' contract facts and the overlay's curated statuses |
| Protein inventory | `data/proteins/inventory.snapshot.json`, 12 November 2026, engine `fec863f` | The units a law acts on |

Everything was read with `git show`, `git grep`, `git archive` into `out/scratch-laws/` and the
viewer's own static reader (`tools/lib/static_eval.py`). No engine code was imported or run. The
scripts that made the list are `out/scratch-laws/build_pieces.py` (with
`probe_catalogue.py` and `probe_static.py`) and `out/scratch-laws/assemble.py`, which writes the
page.

## 1. What the Engine view shows of laws today

Two pictures, taken with the viewer's screenshot tool (`tools/screenshot.mjs`, through the browser
lock) on 16 November 2026, map at main `20107cd2`:

- `out/scratch-laws/engine-today-wide.png`: the whole stack, light, 1440 × 900.
- `out/scratch-laws/engine-today-channels-dark.png`: the channel catalogue chosen, dark.

What they show:

- **The Laws shelf holds 26 boxes, and a box is a group of files.** The overlay matches files to
  boxes by pattern (`data/architecture/overlay.json`, `components`, layer `laws`).
- **One box stands for 56 channel laws.** The "Channel catalogue" box's panel lists them as text
  under the 34 units they act on, seven units at a time, then "Show 27 more". No law can be chosen,
  searched or placed.
- **The rework's pieces have no place of their own.** They are one designed box, "Laws as declared
  pieces".
- **Composition is not drawn.** The Models shelf and the Laws shelf are joined only by lines
  between boxes. The operators are boxes on their own shelf, each with its contract in the panel.
- **It runs out of room.** The shelf's label is clipped by the boxes in front of it, and adding
  the catalogue's laws one by one would put 56 boxes on one shelf.

## 2. The engine's modular structure, as the code states it

### 2.1 On main (`98c49993`)

| Kind of piece | How identified | Where enumerated | Count |
| --- | --- | --- | --- |
| Channel laws of the older families | `name@version`, with a registry code 0–55, never reused | `LAW_CODES` tables of 17 modules in `src/cells/processes/` (the union has 56 ids and no code twice); one more leak, `neutral_mobile_leak@1`, in `core/surface_redistribution_spec.py` | 57 |
| Passive routes | `LAW_ID`-style constants and literals | `constant_field@1` (`processes/electrochemistry.py`), `logmean_electrodiffusion@1` (`core/spatial_extracellular_spec.py` and others), `extracellular_face_transport@1` and `bernoulli_fitted_environment_faces@1` (`processes/extracellular_face_transport.py`) | 4 |
| Junction laws | `LAW_ID` | `junction_voltage_relaxation@1`, `symmetric_opposing_relaxation@1`, `delayed_first_order_junction_formation@1` | 3 |
| Pumps, exchangers, cotransporters | `LAW_ID` and the inventory | for example `nak_atp_mass_action_positive@1`, `ca_atp_mass_action_positive@1`, `ncx_3na_1ca_symmetric_barrier@1`, `nkcc_reversible_tanh@1` (`k_anion_symport_mass_action@1` is counted with the operators) | 12 |
| Release and organelle routes | `LAW_ID` | `er_calcium_release@1`, `ip3_er_release@1`, `mitochondrial_passive_continuous_si@1` | 3 |
| Fuel kind | `METABOLISM_ID` | `maintained_chemical_reservoirs@1` (`core/kinetic_finite_spec.py`) | 1 |
| Operators of the composite | `LAW_ID` per class | `models/operators/__init__.py`, `OPERATORS`, each through `contract.check_declarations` | 19 |
| Solvers, step methods, a heat booking | `SOLVERS`, `*_SOLVER_ID`, `STEP_ID`, `TRAPEZOID_JUNCTION_HEAT` | per family: `core/surface_pump_spec.py` `SOLVERS` (`rk4` and two IMEX ids); the field solvers in `numerics/surface_field.py`, `tissue_field.py`, `core/spatial_extracellular_spec.py`; the gate update, water's Heun step, the projective step | 12 (the page's selection) |
| Other process laws | constants with `LAW` in their name in `processes/`, `numerics/`, `coupling/` | geometry, the outside grid, reactions, regulation, noise, injury, fuel regeneration | 39 |
| **In the page's list** | | | **150** |

Models and compositions:

- **102 module-level `MODEL_ID` literals** by grep of `src/cells` (and two `MODEL_ID` lines that
  refer to another module's). The registry `models/registry.py` dispatches on each spec's class;
  there is no single table of families.
- **One inner model,** `resolved_pump_tissue@3` (`core/surface_pump_v3_spec.py`), whose five
  channel laws are a closed table on main: `LAW_CODES` = `kv1p5_mh@1` 0, `kir2p1_mh2@1` 1,
  `nav1p2_m3h_regularized@1` 2, `kleak_always_open@1` 3, `naleak_always_open@1` 4.
- **One composite,** `resolved_pump_composite@1` (`core/pump_composite_spec.py`): the inner model
  plus an ordered list of operators. "New combinations are definitions, not model families"
  (D142, D143). `frozen_definition` rewrites three earlier definitions as compositions:
  `resolved_pump_water@1` (water), `resolved_pump_water@2` (water, then the K–anion symport) and
  `resolved_pump_replacement@1` (replacement).
- **What a composition is worth** is written in the code: `DEVELOPMENT_STATUS` = "development
  composition: integration grants no acceptance; judged status only from a registered protocol for
  this composition".

What an operator declares (`models/operators/contract.py`): owned state (`STATE_AXES`), the fields
it writes and the accumulators that book them (`ENTITY_WRITES`), what it provides (`VIEW_FIELDS`)
and reads (`VIEW_READS`, `CONFLICTS_VIEW`), its parts of the step, its ledgers, its heat and work
fields, the laws that must precede it (`REQUIRES`), its schedule keys and its ownership of
observation columns. The extractor already reads these (README, "What comes from the code").

### 2.2 Not on main: the landing candidate and development branches

**The landing candidate, `integration-d172` at `3c10b833`** (counted against main `98c49993`: 157
commits on it are not on main, and 85 on main are not on it):

- **@3's laws as declarations** in `models/inner_laws.py`: `CHANNEL_LAWS` (five `ChannelLaw`s: id,
  registry code, gates, permeant species with valence and relative permeability, voltage domain,
  the reference RK4 step, kinetics and opening kernels, stage term, reads, provenance, and four
  reserved fields for a law that stands in for something), `JUNCTION_LAWS` (one), `PUMP_LAWS`
  (two: rows moved per cycle and fuel kinds), the route ids `MEMBRANE_ROUTE_LAW_ID`
  (`constant_field@1`) and `FACE_ROUTE_LAW_ID` (`logmean_electrodiffusion@1`), and
  `MAINTAINED_FUEL_ID`. `InnerStructure` is what one definition declares, with no value in it.
- **Kinds,** through `core/kind_registry.py` (namespaced ids, "a bare ID resolves in the `cells`
  namespace"; canonical order by sorted id; a registered kind that is not declared changes
  nothing). Three built-ins in `models/inner_kinds/`:
  - `cells.passive_routes@1`, with `passive_neutral_permeation@1` and `proton_constant_field_leak@1`;
  - `cells.rapid_proton_buffer@1`, with the read `rapid_proton_buffer@1`;
  - `cells.transporter@1`, with `proton_atp_mass_action_positive@1`,
    `atp_driven_transporter_mass_action_positive@1` and the fuel kinds `maintained_held_rows@1` and
    `finite_fuel_rows@1`.
- **Kernels with unit tests that no kind or model imports** at this revision:
  `bounding_patch_damage@1` (`processes/patch_damage.py`), `ph_conditioned_factor@1`
  (`processes/ph_condition.py`) and `bounding_patch_constant_field@1`
  (`processes/patch_electrodiffusion.py`, which also names `imex_ars222_face_patch_electromigration@1`).
- **One identity per species,** `core/species_registry.py`.
- **The same 19 operators.**

**On other development branches, not on main:**

- `core-next` `17a3863b`: `ROUTE_LAWS` in `inner_laws.py`, each route law with the hosts it
  serves, its basis in its sources' words, and its provenance. @3's own run-view declarations at
  `b2b58f7c` (`UNITS`, `OBSERVATION_AXES`, `RECORD_KINDS`, `ORIENTATION`, `RECORD_LAYERS`,
  `VIEW_LAYERS`, `RECORD_NOTES` in `models/surface_pump_v3.py`), and the kinds' `KindView` at
  `74a75241`.
- `run-view-d154` `fd008813`: the operator contract carries the run-view fields. **Two of the 19
  operators declare them so far** (`scheduled_species_exchange@1` and
  `scheduled_species_turnover@1`: `VIEW_LAYERS`, `RECORD_KINDS`, and `ORIENTATION` for the first);
  the writer (`src/cells/run_view.py`) reports "declares no VIEW_LAYERS" for the others and keeps an
  interim table for @3.
- `cardiac-laws` `59ae93e3`: the human cardiac law design, proposed (below).

### 2.3 What is coming, as the plans name it

| Source | Pieces | Where |
| --- | --- | --- |
| Excitable tissue (D155, D170) | `junction_ungated@1`, `fast_sodium_m3hj@1`, `l_type_calcium_cdi@1`, and only if needed `transient_outward_potassium@1` | `docs/EXCITABLE_TISSUE_DESIGN.md` §3.3, main |
| Human cardiac laws (D183, D184) | eight new channel laws (`fast_sodium_m3hj@1`, `late_sodium_mh@1`, `transient_outward_potassium@1`, `l_type_calcium_cdi@1`, `rapid_delayed_rectifier_potassium@1`, `slow_delayed_rectifier_potassium@1`, `inward_rectifier_potassium@1`, `potassium_instantaneous_factor@1`), two transporter cycles (`sodium_calcium_exchange_cycle@1`, `sodium_potassium_pump_cycle@1`), a release law (`graded_sr_calcium_release@1`), a rapid buffer read (no id yet) and `calcium_triggered_phosphorylation_trapping@1`; four laws and the constant-field route moved from the catalogue | `docs/HUMAN_CARDIAC_LAWS_DESIGN.md` §2, branch `cardiac-laws`, proposed |
| The staged move (D167) | the catalogue's laws, each moved into the one model when a use needs it, keeping its source and parity tag | `docs/DECISIONS.md`, main |
| External modules (D180, D185) | contributed pieces in their own namespaces, by pull request inside `src/cells` | `docs/MODULE_SYSTEM_DESIGN.md`, `docs/DECISIONS.md`, main |
| The minimal-cell track (D173) | 338 reactions and 304 metabolites in one reconstruction; "over 7,000 reactions" in the 2022 kinetic model | `docs/SYN3A_MINIMAL_CELL_TRACK.md`, main. Whether a reaction is a piece is a question for the lead |

The 13 pieces with ids and no code are in the page's list as outlines; none of them is found by
`git grep` on main or on the landing candidate.

### 2.4 Where status and evidence are kept

- **Not per piece.** The plan's levels (implemented, guarded, numerically qualified, judged) are
  kept per item in the status table of `docs/CURRENT_PLAN.md`, with evidence in `PROGRESS.md` and
  choices in `docs/DECISIONS.md`.
- **`provenance: "parity"`** on a declaration in `inner_laws.py` is a source tag ("moved from the
  catalogue; moving is not calibrating"), not a level.
- **The Engine view's overlay** gives each operator a curated status with its source and date
  (for example `ideal_osmosis_linear_compliance_water@1`, qualified, 11 November 2026, from
  PROGRESS.md "Osmotic water and volume qualified and landed"), and gives each box a status (the
  "Channel catalogue" box is established, from `docs/README.md`). The page uses these as the record
  states them and names the source; for a law it says that the status belongs to the box.

### 2.5 What a static reader gets, and what stays curated

Run with the viewer's own evaluator over `git archive`s of both refs (`out/scratch-laws/probe_static.py`,
`probe_catalogue.py`):

- **Resolves:** every catalogue table on main (`LAW_CODES`, `LAW_PERMEABILITIES`, `GATE_POWERS` or
  `STATE_COUNTS`, `SPECIES_VALENCE`); @3's `LAW_CODES`, `LAW_PERMEABILITIES`, `GATE_COUNTS` and
  `TRAPEZOID_JUNCTION_HEAT`; the pump family's `SOLVERS`; `inner_laws`' route and fuel ids; each
  kind's `KIND_ID`; `passive_routes.LAWS`; the transporter's fuel kinds; every `MODEL_ID`; the
  operators' contract attributes.
- **Does not resolve:** `inner_laws`' `CHANNEL_LAWS`, `JUNCTION_LAWS`, `PUMP_LAWS` and
  `ROUTE_LAWS` (frozen dataclasses that hold kernel functions), and the transporter's
  `NEUTRAL_LAW` and `PROTON_LAW` (built by a call to `qualified`).
- **The form does not say what a thing is.** `git grep` finds 673 distinct `name@version`
  literals in `src/cells` on main: laws, models, step methods, solvers, random streams, stage
  domains and schema ids. Only 22 of the inventory's 79 law ids are bound to a `*_ID` constant in
  `processes/`; the rest live in tables.
- **Stays curated today:** the family, what a piece computes in plain words (the page quotes the
  first paragraph of its module's docstring instead), a law's reads and writes, the records it
  saves, which models other than @3 use it, and every status.

### 2.6 Against the lead's pointers of 16 November 2026

Each pointer was checked against the code at the ref named.

- **Model families, `get_model`, `MODEL_ID`:** as stated. 102 literals at main.
- **@3's laws in `inner_laws.py`:** as stated, on the landing candidate only; on main the same
  five laws are `LAW_CODES` in `surface_pump_v3_spec.py`. `ROUTE_LAWS` is on `core-next`, as
  stated.
- **Operators:** as stated, 19 on main and on the candidate.
- **Kinds and species:** as stated, on the candidate. The kinds also name two fuel kinds and one
  read that are ids of their own.
- **Solvers:** as stated, declared per family; the field solvers' ids sit in `numerics/`, and
  `rk4` has no version.
- **Static reading: "only partly", ids only.** It differs in one direction: the viewer's reader
  gets more than ids from the older catalogue and @3's tables on main (codes, permeant species,
  gate powers). It does not get the landing's declarations, which become the source of truth.
- **Run-view declarations for operators on `run-view-d154`:** the contract has the fields, but
  only 2 of the 19 operators declare them at `fd008813`.
- **Not in the pointers:** three kernels on the candidate that no kind imports; and D185 (main
  `33617054`, the same afternoon), which already adds the declarations manifest and names "the
  viewer's laws library" as a consumer. The draft below is therefore written as the viewer's fields
  for D185's manifest.

## 3. The options

Each option is drawn from the same list and uses the same three shared parts: the opened piece's
card, one search with filters (family, where the piece is, model, and namespace once modules
arrive), and the plain list. Shape tells where a piece is (solid on main, banded on the landing
candidate, an outline when only a design note names it, faint for an empty slot); blue marks only
what was chosen or found; no colour stands for a status. Each sketch has a Size switch that adds
empty slots to show a few hundred and a thousand pieces; the slots are spread over the families
in today's proportions, which is an assumption and not a plan.

| | Racks (recommended) | Stacks | Card catalogue | Plugboard | Pull-out shelf |
| --- | --- | --- | --- | --- | --- |
| What it is | Model frames with a slot per declared piece, in front of a wall of all pieces | A round reading room: a case per group, a shelf per family, a spine per piece | A cabinet with a drawer per family; search pulls drawers and stands matches up | Modules wired to the six shared-state rails they change or read | Drawers in the Engine view's own shelves |
| Composition | Drawn | In words | In words | Drawn as shared state | In words |
| A thousand pieces | Search, then the lines to its frames | A ring of about twenty cases | Same steps as today | Family blocks | Drawers far too long |
| Data today | Enough for @3 and the composite | Enough | Enough | Operators only | Enough |
| Phone | Fair | Good | Good | Weak | Weak |
| Cost | Medium to large | Medium | Small to medium | Large | Small |

The page gives each option's full account: what a visitor sees and does, what an opened piece
shows, how it ties to the modular structure and stays true as pieces are added, how it holds at
three sizes, phone, keys, less motion and the list, and what it costs. At the three sizes:

| | Today (176) | About 300 | A thousand |
| --- | --- | --- | --- |
| Racks: the tallest wall column | 39 bars (other process laws) | 67 | 222 |
| Stacks: cases (six shelves of 30) | 6 | 6 | 10 |
| Pull-out shelf: the longest drawer, six to a row | 7 rows | 12 rows | 37 rows |
| Plugboard | readable | the wires weave | the modules pack tight; family blocks with bundled wires are proposed, not drawn |

Each opened piece says where its design note is: on main, or only on a development branch.

**The opened piece** shows, for every option: what it computes, quoting its module's docstring at
the ref read; what it declares (registry code, permeant species and gates for a channel law; parts
of the step, what it provides and reads for an operator; its pieces for a kind); where it plugs in
(the frames that hold it, directly, through a kind or through the inner model); what it saves
(heat, work and ledgers for an operator, and the run-view layer where a branch declares one); its
status as the record states it, with the source; the unit it acts on, from the protein inventory;
and its files at the ref.

**The plugboard's wires** come from each operator's contract (what it provides, and what it reads
as declared), placed on a rail by the overlay's field table (`shared_state.fields`). Fields the
table does not name are placed by prefix (`channel_`, `pump_` to the unit population; `membrane_`
to the membrane domain; `outside_`, `face_`, `extracellular_` to the outside): that is the page's
reading. A law's wires are drawn from its kind, dashed, until laws declare their reads and writes.

## 4. Recommendation

**The racks,** for four reasons:

1. **It answers both sentences.** The wall gives room; the frames show the modular structure.
2. **It is drawn from declarations.** @3's frame holds what its registries hold on the landing
   candidate (`inner_laws.py` and the built-in kinds); a world's frame would hold what its
   definition declares (`InnerStructure`). The composite's column is the operator registry. Only
   words are curated.
3. **It holds at a thousand without redrawing.** A new piece is a bar; a frame grows only when a
   model declares more.
4. **It keeps the record's honesty.** A frame never takes a status from its parts; the dashed
   "next free code" slot is the engine's own rule that no registry code is reused.

Build first the shared card, the list and the search, with the wall and @3's frame, from what can
be read today and marked so. Add the other frames and the "used by" lines when the manifest lands.
The plugboard can become a second face of the wall once every piece declares its reads and writes.

## 5. Questions for the user

Each with the recommended answer.

1. **Which option?** The racks, with the catalogue's search as its index.
2. **Should the older families' laws stand in the library before they move into the one model?**
   Yes, on their own shelves, marked as in an older family.
3. **Should a piece show a status only where the record states one?** Yes, and "no level recorded"
   everywhere else.
4. **Build now from what can be read, or wait for the manifest?** Build the wall, the card and the
   list now, marked as read from the code, and switch to the manifest when it lands.
5. **A view of its own, or a room inside the Engine view?** A room entered from the Laws shelf, with
   its own address and a way back.
6. **How should it look?** The Engine view's glass and slate, so that it reads as part of one map.

## 6. Questions for the engine's lead

1. **Is a reaction a piece?** A minimal cell's network has hundreds of reactions: is each a piece of
   the library, or a row of one reaction law?
2. **Do the older families' 56 catalogue laws count as pieces** before they move (D167), and how
   should a moved piece name the frozen original it came from?
3. **Will the manifest carry a status level per piece,** and from which record would it be filled,
   given that the plan's table is kept per item?
4. **Are the three kernels on the candidate that no kind imports** (`bounding_patch_damage@1`,
   `ph_conditioned_factor@1`, `bounding_patch_constant_field@1`) pieces yet?
5. **Are solvers and step methods pieces?** @3's integrator is chosen by the tableau's shape, not
   by an id (`INNER_MODEL_V4_DESIGN.md` §7.4 (a)), and `rk4` has no version.
6. **Which compositions should be frames:** only the three frozen definitions, or every registered
   protocol's world?
7. **Will each record of the run view name the piece that owns it,** so that a piece can say what
   it saves for a replay?
8. **Will contributed pieces carry a namespace and a named owner** in the manifest (D185)?

## 7. Draft feature request: the declarations manifest, as the viewer needs it

Written in the form of `docs/FEATURE_REQUESTS.md` on main, to be pasted by the lead, who assigns
the number and writes the mapping.

> ## FR-12 — The declarations manifest, readable by the viewer (D185)
>
> **Proposed 16 November 2026 by the visualizer session, for the lead.** D185 adds a declarations
> manifest to the module system's stage 1: "The engine writes a JSON list of every registered law,
> operator and kind, with its ID, what it reads and writes, what it conserves, and its units and
> signs. Contributed modules then appear in the docs and in the viewer's laws library without hand
> edits." This request is the viewer's side: the fields it needs, and what would count as done.
>
> **The request.** One JSON file, written by the engine from its registries at a revision, with an
> entry for every registered piece:
> - its namespaced id (`namespace.name@version`), its kind (channel law, junction law, pump or
>   transporter law, route law, kind, operator, solver or step method, fuel kind, read) and its
>   family, with the module's namespace and named owner;
> - one plain sentence on what it computes, and its source citation and provenance tag (`parity`,
>   `cited` or `calibrated`);
> - what it reads and what it writes or provides, by field or by species row, with the role of each
>   (reads, changes, provides, owns), as the contract and the kind declarations hold them;
> - what it conserves and books: its ledgers, its heat and work fields, its energy roles;
> - for each field it declares, its unit and sign, and the records it saves with their kind and
>   layer, as the run view's declarations hold them;
> - for a channel law its registry code, gates, permeant species with valence and relative
>   permeability, voltage domain and reference step; for a pump its rows per cycle and fuel kinds;
> - the models and compositions that declare it, and for an operator the laws it requires;
> - a status level, with the record it was read from (document and heading), or `null` where no
>   record states one;
> - its source files, and for the file as a whole the revision and dirty state it was written at.
>
> The older families' laws are listed too, as their own kind, until each moves (D167); a moved
> piece names the frozen original it came from.
>
> **Why it is general.** The viewer's laws library is drawn from it, so it stays true as pieces are
> added. The contributor guide and the docs can list pieces from it, and a contributed module's
> pieces appear without hand edits (D180, D185). The conformance kit can check that every
> registered piece has a complete entry, and a run's provenance can name pieces by the same ids.
>
> **What it must not be.**
> - Not a reason for the viewer to import the engine: the engine writes the file in its own
>   environment, and the viewer reads only the file, as its extractor reads the code today without
>   importing `cells`.
> - Not a source of invented status: a level is copied from the record that states it, or left
>   `null`.
> - Not a second source of truth: it is generated from the registered declarations, never edited by
>   hand.
> - Not a list of reference simulators: none is a piece of Cells.
> - Not a replacement for a run's `view.json`, which says what one run saved.
>
> **What would count as done.**
> - A command writes the manifest at a revision, and the same revision gives the same bytes, apart
>   from a time stamp.
> - A test fails when a registered law, kind or operator has no entry, or an entry's id is not in
>   its registry.
> - Its schema is written down beside the run view's.
> - The example module's pieces appear in it under their own namespace.
> - The viewer's extractor reads it without importing `cells`, and the laws library is drawn from it.

## 8. What was checked, and how

- **Counts:** made by `out/scratch-laws/build_pieces.py`, which asserts that every id it lists from
  the inventory, the solvers and the landing candidate occurs in the code at its ref, and that
  every design-note id occurs in neither main nor the candidate. The union of the catalogue
  tables was checked for duplicate codes (none).
- **The page:** assembled by `out/scratch-laws/assemble.py`; its scripts pass `node --check`, and
  the card was rendered in Node for all 176 pieces without an error. Its look and behaviour were
  checked in headless Chrome with software WebGL by `out/scratch-laws/shoot_page.mjs`, through the
  browser lock; the handover (`out/handover/laws-library.md`) says what was looked at and what
  could not be checked.

## 9. Uncertain

- **Families are the page's reading.** The channel families follow the protein inventory's unit
  kinds; "other process laws" are the constants whose name contains `LAW`, which may include
  things the lead would not call a law. The selection of 12 solvers and step methods is the page's.
- **The three.js build.** The page loads the same address as the earlier ideas pages, the ES
  module `three.module.min.js` from cdnjs, through `import`. three.js 0.170.0 ships no build that
  defines a global, so the contract's "the build that defines a global" cannot be met with it; the
  data, the card and the list are in a classic script and in the markup, so the page is whole if
  the module never loads.
- **The landing.** If `integration-d172` has landed by the time this is read, its 13 pieces are on
  main, and the page's labels need one pass.
- **The reference simulator in docstrings.** Many catalogue modules' docstrings name BETSE v1.5.0
  as the source of their coefficients (for example "All seven BETSE v1.5.0 sodium classes as
  regularized continuous gate laws."). The card quotes them as the module's own words. BETSE is
  never drawn or listed as a piece.
- **Pictures by capture beyond the viewport.** In a first try, two sketches came out blank when the
  page was captured beyond the viewport, although their canvases held the picture (read back with
  `toDataURL`). The pictures in the handover were taken of the viewport, with the element scrolled
  into it.
