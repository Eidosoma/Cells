# The composite pump-tissue model and its operators

`resolved_pump_composite@1` runs `resolved_pump_tissue@3`'s own step at a view of its
layout, plus an ordered list of declared operators (D142, D143). Water, cell replacement
and, later, division, growth and mechanics are operators; a new combination is a
definition, not a new model family. Design: [cell-division design note §3](CELL_DIVISION_DESIGN.md#3-composition-the-first-question).
Status and runs: [Progress](../PROGRESS.md).

Files:
- `src/cells/core/pump_composite_spec.py`: the definition and `frozen_definition`;
- `src/cells/models/pump_composite.py`: the composite (one cached implementation per
  inner identity and ordered operator list);
- `src/cells/models/pump_composite_adapter.py`: the @3 entity adapter;
- `src/cells/models/operators/`: the contract and the operators (the secreted-species operators
  share `species_common.py`: identity, the 16-species cap (FR-9 / D165, from 7), the occupant
  rule);
- `src/cells/core/inventory_species.py`: declares a neutral inventory species on @3's species axis
  (trace background, zero membrane and junction permeability, effective face diffusivity, its
  material floor);
- `validation/tissue/composite_guard.py`: the bitwise guards against the frozen models;
- `validation/tissue/composition_matrix.py`: which operators compose (the matrix below,
  generated from the declarations);
- `validation/tissue/composite_crossrev.py` and `composite_dump.py`: the cross-revision
  guards of the thin modules (compiled programs and bindings; saved runs).

**Status: development.** Integration grants no acceptance. A composition is not qualified
by its parts: unqualified combinations run as labelled development runs
(`composition_status` in the summary), and judged status comes only from a registered
protocol for that composition (D143).

## Definition

The model holds `resolved_pump_tissue@3`'s own fields (parsed by @3's parser) plus
`inner_model` and `operators`, an ordered list of operator blocks, each naming its `law`.
The experiment adds each operator's schedule under the operator's own keys:

| Operator law | Block | Experiment key | Frozen model it re-expresses |
| --- | --- | --- | --- |
| `ideal_osmosis_linear_compliance_water@1` | `compartments`, `baths`, `membranes` | `water_controls` | `resolved_pump_water@1` |
| `k_anion_symport_mass_action@1` | `volume_factor`, `roles`, `routes` | `symport_controls` | `resolved_pump_water@2` (with water before it) |
| `scheduled_cell_replacement@1` | `junction_formation`, `templates`, `template_capacity` | `replacement_events` | `resolved_pump_replacement@1` |
| `scheduled_cell_replacement@2` | `junction_formation`, `templates`, `template_capacity`, `impermeant_species` | `replacement_events` | none: @1 over water, which must precede it; newcomers bring their volume ([v2 design](PUMP_COMPOSITE_V2_DESIGN.md) §2) |
| `electrode_current_injection@1` | `electrodes` | `injection_controls` | none: a new law ([v2 design](PUMP_COMPOSITE_V2_DESIGN.md) §4); refused over water, whose dilution term it does not book (§2.10) |
| `membrane_entity_state@1` | `populations` (functional unit, catalogue reference, reference density) | none | none: a state owner (v2 design §3) |
| `scheduled_membrane_insertion@1` | `patches` (specific capacitance, inserted densities) | `insertion_controls` (onset, rates) | none: a new law (v2 design §3) |
| `restricted_cleft_lumen@1` | `lumens` (each a finite node, its source bath and the gap width) | none | none: a new law ([division design](CELL_DIVISION_DESIGN.md) §4.2, §7; S3); a node opened at insertion@1's onset, filled with bath fluid as its patch's area grows |
| `isopotential_partition@1` | `divisions` (parent, two daughters, a volume fraction, and the patch, population and contact maps) | `partition_events` | none: a new law ([S5 design](CELL_DIVISION_S5_DESIGN.md) §3); prescribed division into fresh daughter slots, a closer that retires the parent |
| `cytoplasmic_bridge_closure@1` | `bridges` (a junction between one division's daughters, its initial aperture, closure law and time) | `bridge_controls` | none: a new law ([S5 design](CELL_DIVISION_S5_DESIGN.md) §4); requires the partition |
| `scheduled_membrane_insertion@2` | `patches`, as @1 | `insertion_controls`, as @1 | none: insertion@1's law with its onset a closer ([S5 design](CELL_DIVISION_S5_DESIGN.md) §5.1) |
| `restricted_cleft_lumen@2` | `lumens`, as @1 | none | none: lumen@1's fill, with a lumen faced by several patches ([S5 design](CELL_DIVISION_S5_DESIGN.md) §5.2); requires insertion@2 |
| `scheduled_species_turnover@1` | `species` (identity: catalogue reference, kind of evidence), `routes` (production at cells, clearance at cells and finite nodes), `templates` (newcomers' rates) | `turnover_controls` (per route and carrier; outside nodes per node) | none: a new law ([secreted-species design](SECRETED_SPECIES_TRANSPORT_DESIGN.md) §2.2, D150 v1); exact half-steps, signed work |
| `scheduled_species_exchange@1` | `species`, `routes` (secretion: flux or first-order export; uptake: first-order or saturable import, a plain sink), `templates` | `exchange_controls` (rate and K_M per route and carrier) | none: a new law (secreted-species design §2.3); palindromic exact stages, signed work |
| `local_species_reactions@1` | `standard_concentration_mM`, `species` (moieties, standard potential, identity), `reactions` (sites, integer stoichiometry, a passive, mass-action or Michaelis-Menten law with its parameters, Hill factors) | `reaction_controls` (a multiplier per reaction, optionally per site) | none: a new law ([shared-inventory reactions design](SHARED_INVENTORY_REACTIONS_DESIGN.md), D152 v1); SSPRK(3,3) half-steps under the stage condition dt L <= 1, exact dG bookings (work at driven nodes, heat at passive ones, the per-route hybrid at mixed ones) with the owned standard-potential term |
| `species_regulated_availability@1` | `species` (the species it reads, with identity), `states` (regulatory states: cells, Hill inputs, on- and off-rates, crossing level, initial value), `couplings` (a junction or channel target, a species or state source, its law and basal level) | `coupling_controls` (switches), `regulatory_writes` | none: a new law ([inventory coupling design](INVENTORY_COUPLING_DESIGN.md), D155, D162); a species amount sets @3's availability of a target through `CONTROL_FACTORS` |
| `scheduled_bath_composition@1` | `baths` (the held baths it schedules), `formula_units` (neutral formula units: integer counts of the world's species) | `bath_composition_events` (time, baths, the formula units' concentrations) | none: the older family's explicit ideal-reservoir dose law re-expressed ([bath-schedule design](BATH_SCHEDULE_DESIGN.md), FR-10, D166); an event map sets a held bath's composition, provided through the view of `extracellular_amount_reference` |
| `cell_owned_compartments@1` | `compartments` (each a finite node no face names, its one bounding patch on the owner cell, the owner, a label and a reference) | none | none: a declaration (`DECLARATION_ONLY`; [closed-compartment design](CLOSED_COMPARTMENT_DESIGN.md) §1.6, §12): no state and no part; its refusals at the definition and its host-side identity map |

The blocks and keys are the frozen models' own, so `frozen_definition(raw)` rewrites a
`resolved_pump_tissue@3`, water@1, water@2 or replacement@1 definition as the equivalent
composition. The run identity (composite ID, inner ID, ordered operator IDs) enters the
batch signature, the summary and the run manifest (`composition`).

## The operator contract

`src/cells/models/operators/contract.py` (design §3.3, with the additions found in S1):

| Item | Declaration |
| --- | --- |
| Owned state | `STATE_AXES` (only this operator writes them); heat and work fields declared, since the energy flows read the `_dissipated_energy_pJ` and `_work_pJ` suffixes by name |
| Entity writes | `ENTITY_WRITES`: inner state fields it changes, each with the owned accumulators that close the inner ledgers; `STATE_RESETS`: intensive kinetic state set at events (gates), which has no ledger |
| View fields | `VIEW_FIELDS`: @3 layout fields it provides from state, one provider each; `CONTROL_FACTORS`: @3 availabilities it multiplies (a product in declared order); `CONFLICTS_VIEW`: fields it reads as declared, which no other operator may provide |
| Parts | event map (`EVENT`), split process (`SPLIT`, with its RK4 mode `coupled` or `split`), in-step membrane process (`PROCESS`, through @3's opt-in hook, at most one per composition). One law may contribute several parts. A state owner has none: it holds entity state that later operators write (`ACCEPTS_WRITES`) and provides it through the view (`membrane_entity_state@1`) |
| Ledgers | terms added to @3's ledgers and rounding magnitudes, its own ledgers with their bounds |
| Domain and refusal | its domain and control validity (any failure refuses the step, which returns the start state); `REQUIRES` (laws that must precede it) |
| Schedule | its experiment keys, parsed and checked at the definition (event times exact multiples of dt) |
| Observation ownership | its own columns (state fields and readouts); `REPLACES`, {column: reason}, for the inner or earlier operators' columns it computes instead. Replacement is a declared chain in order and the last is the owner. Returned columns are checked against the declaration on every row ([v2 design](PUMP_COMPOSITE_V2_DESIGN.md) §1.2) |
| Views read and writes accepted | `VIEW_READS`: inner view fields read at their current value, provided by an earlier operator. `ACCEPTS_WRITES`, {owned field: own ledgers}: fields a later operator may write; the writer adds its terms to those ledgers and their magnitudes (`external_ledger_terms`, `external_magnitude_terms`) |
| Event replacements | `EVENT_REPLACES`, {field: (removed, supplied)}: the fields an event map replaces, with their owned accumulators |

When a composition is built, the composite checks these declarations and builds its
field-to-owner map: each state field's owner and writers, each layout and control field's
owner, each view field's provider and readers, and each observation column's owner chain.
Runs write the map to their manifest as `field_owners`, beside `composition`.

## Which operators compose

`validation/tissue/composition_matrix.py` generates the block below from the registered operators'
declarations; `python -m validation.tissue.composition_matrix --write` rewrites it, and
`tests/unit/test_composition_matrix.py` fails when the block differs from the declarations, when a
refusal has no tag or a tag no refusal, or when a cited check or test does not exist. For each
ordered pair of operators the composition is the first with its requirements, then the second
with its requirements, on @3, and `pump_composite.structure_errors` checks it from the
declarations alone. A ✓ means only that the declarations admit the pair. The rules at the
definition, listed after the matrix, still apply to every definition, and no composition is
qualified by its parts (D143).

Each refusal is tagged:
- **real**: the other operator can change a slot the reader reads or acts on, or the two are
  versions of one law. This includes "real, not shown nominal".
- **nominal**: in no admissible definition can the other operator change a slot the reader reads
  or acts on. A finer declaration, such as slot-scoped provision (door S of the
  [bath-schedule design](BATH_SCHEDULE_DESIGN.md) §3.1), would admit the pair without new
  physics. Each nominal tag cites the code that shows it.

The bath-schedule design (§3.1) found D152's conflict with the bath schedule nominal, and the
matrix records it so; it classes insertion@1's second provision and the closers' padding as
refusals, and the matrix keeps them real.

<!-- composition-matrix: generated by validation/tissue/composition_matrix.py --write -->

| # | Operator law | Requires | Provides | Closes | Reads as declared |
| --- | --- | --- | --- | --- | --- |
| 1 | `ideal_osmosis_linear_compliance_water@1` |  | `volume`, `extracellular_volume` |  | `membrane_area` |
| 2 | `k_anion_symport_mass_action@1` | 1 |  |  |  |
| 3 | `scheduled_cell_replacement@1` |  | `channel_permeability`, `channel_abundance`, `membrane_permeability`, `pump_capacity`, `calcium_pump_capacity` |  | `volume`, `extracellular_volume`, `membrane_area` |
| 4 | `scheduled_cell_replacement@2` | 1 | `channel_permeability`, `channel_abundance`, `membrane_permeability`, `pump_capacity`, `calcium_pump_capacity` |  | `membrane_area`, `membrane_capacitance`, `active`, `outside_active`, `membrane_active`, `channel_active`, `junction_active` |
| 5 | `electrode_current_injection@1` |  |  |  | `volume` |
| 6 | `membrane_entity_state@1` |  | `membrane_area`, `membrane_capacitance`, `channel_abundance` |  |  |
| 7 | `scheduled_membrane_insertion@1` | 6 | `membrane_active`, `outside_active`, `face_active`, `extracellular_amount_reference` |  |  |
| 8 | `restricted_cleft_lumen@1` | 6, 7 | `extracellular_volume` |  |  |
| 9 | `isopotential_partition@1` | 6 |  | `active` | `volume` |
| 10 | `cytoplasmic_bridge_closure@1` | 9 |  |  |  |
| 11 | `scheduled_membrane_insertion@2` | 6 |  | `membrane_active`, `outside_active` |  |
| 12 | `restricted_cleft_lumen@2` | 6, 11 | `extracellular_volume` |  |  |
| 13 | `scheduled_species_turnover@1` |  |  |  | `volume`, `extracellular_volume`, `active`, `outside_active`, `membrane_active` |
| 14 | `scheduled_species_exchange@1` |  |  |  | `volume`, `extracellular_volume`, `active`, `outside_active`, `membrane_active`, `membrane_area` |
| 15 | `local_species_reactions@1` |  |  |  | `volume`, `extracellular_volume`, `active`, `outside_active`, `extracellular_amount_reference` |
| 16 | `species_regulated_availability@1` |  |  |  | `volume`, `extracellular_volume`, `active`, `outside_active`, `membrane_active` |
| 17 | `scheduled_bath_composition@1` |  | `extracellular_amount_reference` |  |  |
| 18 | `cell_owned_compartments@1` |  |  |  | `volume`, `extracellular_volume`, `membrane_area`, `membrane_capacitance`, `active`, `outside_active`, `membrane_active`, `channel_active`, `junction_active`, `face_active` |

Row: the earlier operator in the list; column: the later. ✓ admitted by the declarations; R refused, with a real conflict among the refusals; n refused, every refusal nominal; d admitted by the declarations, refused at the definition by a law-level rule; · the same law.

| | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **1** | · | ✓ | R | ✓ | R | R | R | R | R | R | R | R | R | R | R | R | ✓ | R |
| **2** | ✓ | · | R | ✓ | R | R | R | R | R | R | R | R | R | R | R | R | ✓ | R |
| **3** | R | R | · | R | ✓ | R | R | R | R | R | R | R | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **4** | ✓ | ✓ | R | · | R | R | R | R | R | R | R | R | R | R | R | R | ✓ | R |
| **5** | R | R | ✓ | R | · | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **6** | R | R | R | R | ✓ | · | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | R | ✓ | ✓ | ✓ | R |
| **7** | R | R | R | R | ✓ | ✓ | · | ✓ | R | R | R | R | R | R | R | n | R | R |
| **8** | R | R | R | R | ✓ | ✓ | ✓ | · | R | R | R | R | R | R | R | n | R | R |
| **9** | R | R | R | R | ✓ | ✓ | R | R | · | ✓ | d | d | R | R | R | R | R | R |
| **10** | R | R | R | R | ✓ | ✓ | R | R | ✓ | · | d | d | R | R | R | R | R | R |
| **11** | R | R | R | R | ✓ | ✓ | R | R | ✓ | ✓ | · | ✓ | R | R | R | n | R | R |
| **12** | R | R | R | R | ✓ | ✓ | R | R | ✓ | ✓ | ✓ | · | R | R | R | n | R | R |
| **13** | R | R | ✓ | R | ✓ | ✓ | R | R | R | R | R | R | · | ✓ | ✓ | ✓ | ✓ | ✓ |
| **14** | R | R | ✓ | R | ✓ | R | R | R | R | R | R | R | ✓ | · | ✓ | ✓ | ✓ | ✓ |
| **15** | R | R | ✓ | R | ✓ | ✓ | R | R | R | R | R | R | ✓ | ✓ | · | ✓ | n | ✓ |
| **16** | R | R | ✓ | R | ✓ | ✓ | n | n | R | R | n | n | ✓ | ✓ | ✓ | · | ✓ | ✓ |
| **17** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | R | R | R | R | R | R | ✓ | ✓ | n | ✓ | · | ✓ |
| **18** | R | R | ✓ | R | ✓ | R | R | R | R | R | R | R | ✓ | ✓ | ✓ | ✓ | ✓ | · |

**Refusals from the declarations**, with the number of ordered pairs each refuses:

| Refusal | Pairs | Tag | Why |
| --- | --- | --- | --- |
| osmotic_water (1) reads `membrane_area` as declared; membrane_state (6) provides it | 42 | real | Water binds its conductance from the declared patch areas; insertion and the partition change areas through membrane state |
| osmotic_water (1) and restricted_lumen (8) both provide `extracellular_volume` | 6 | real | Both provide the lumen node's volume |
| osmotic_water (1) and restricted_lumen_v2 (12) both provide `extracellular_volume` | 6 | real | Both provide the lumen node's volume |
| cell_replacement (3) reads `extracellular_volume`, `volume` as declared; osmotic_water (1) provides them | 6 | real | Templates are checked at the declared volumes, which water changes; replacement@2 is the version over water |
| cell_replacement (3) and cell_replacement_v2 (4) are two versions of one law | 2 | real | Two versions of one law own the same state, columns and views; a composition uses one |
| cell_replacement (3) and membrane_state (6) both provide `channel_abundance` | 14 | real | Both provide the abundance of the same populations: replacement its newcomers', membrane state every population's (not shown nominal) |
| cell_replacement (3) reads `membrane_area` as declared; membrane_state (6) provides it | 14 | real | Template pump densities are scaled by the declared patch areas |
| cell_replacement (3) reads `extracellular_volume` as declared; restricted_lumen (8) provides it | 2 | real | Templates are checked at the declared volumes; a lumen changes its node's volume (not shown nominal) |
| cell_replacement (3) reads `extracellular_volume` as declared; restricted_lumen_v2 (12) provides it | 2 | real | Templates are checked at the declared volumes; a lumen changes its node's volume (not shown nominal) |
| cell_replacement_v2 (4) and membrane_state (6) both provide `channel_abundance` | 14 | real | Both provide the abundance of the same populations: replacement its newcomers', membrane state every population's (not shown nominal) |
| cell_replacement_v2 (4) reads `membrane_area`, `membrane_capacitance` as declared; membrane_state (6) provides them | 14 | real | Replacement@2 reads the declared areas and capacitances (DECLARED_LAYOUT_VIEWS) |
| cell_replacement_v2 (4) reads `membrane_active` as declared; membrane_insertion (7) provides it | 4 | real | Replacement@2 reads the masks as declared and its events act on a cell's patches (not shown nominal); insertion@1 opens onset patches |
| cell_replacement_v2 (4) reads `outside_active` as declared; membrane_insertion (7) provides it | 4 | real | Replacement@2 reads the masks as declared (not shown nominal); insertion@1 opens onset nodes |
| cell_replacement_v2 (4) reads `active` as declared; partition (9) closes it | 4 | real | Replacement acts on cell slots, which the partition retires (not shown nominal) |
| cell_replacement_v2 (4) reads `membrane_active` as declared; membrane_insertion_v2 (11) closes it | 4 | real | Replacement@2 reads the masks as declared and its events act on a cell's patches (not shown nominal); insertion@2 closes onset patches until their onset |
| cell_replacement_v2 (4) reads `outside_active` as declared; membrane_insertion_v2 (11) closes it | 4 | real | Replacement@2 reads the masks as declared (not shown nominal); insertion@2 closes onset nodes until their onset |
| current_injection (5) reads `volume` as declared; osmotic_water (1) provides it | 6 | real | Injection books its work at the declared volume, without water's dilution term (v2 design §2.10) |
| membrane_insertion (7) provides `extracellular_amount_reference`, `face_active`, `membrane_active`, `outside_active` beside the closer partition (9) | 8 | real | Beside a closer the adapter rewrites every mask and pads closed slots, overwriting a provider's view (S5 design §2); the partition also refuses insertion@1 at the definition |
| membrane_insertion (7) and membrane_insertion_v2 (11) are two versions of one law | 8 | real | Two versions of one law own the same state, columns and views; a composition uses one |
| membrane_insertion (7) and bath_schedule (17) both provide `extracellular_amount_reference` | 4 | real | Real as the bath-schedule design §3.1 classes it: the composite admits one provider per field (door S). Insertion@1's onset nodes are finite and the bath's targets held, but a lumen, which requires it, fills from its source bath at the declared composition and does not declare that read |
| restricted_lumen (8) and restricted_lumen_v2 (12) are two versions of one law | 2 | real | Two versions of one law own the same state, columns and views; a composition uses one |
| partition (9) reads `volume` as declared; osmotic_water (1) provides it | 12 | real | Daughters' volumes are declared anchors (S5); water would move them |
| species_turnover (13) reads `extracellular_volume`, `volume` as declared; osmotic_water (1) provides them | 6 | real | Turnover's exact update and work read the declared volumes at every cell and finite outside node (turnover_half_step) |
| species_turnover (13) reads `membrane_active` as declared; membrane_insertion (7) provides it | 4 | nominal | Turnover's runtime reads are cells, finite outside nodes and its own fields (turnover_half_step, turnover_domain_valid): it reads no patch and acts on none |
| species_turnover (13) reads `outside_active` as declared; membrane_insertion (7) provides it | 4 | real | Turnover reads the declared outside mask at its finite nodes (turnover_half_step); insertion@1 opens onset nodes |
| species_turnover (13) reads `extracellular_volume` as declared; restricted_lumen (8) provides it | 2 | real | Turnover's exact update and work read the declared volumes at every cell and finite outside node (turnover_half_step); a lumen changes its node's volume |
| species_turnover (13) reads `active` as declared; partition (9) closes it | 4 | real | Turnover reads the declared cell mask (turnover_half_step); the partition retires cells |
| species_turnover (13) reads `membrane_active` as declared; membrane_insertion_v2 (11) closes it | 4 | nominal | Turnover's runtime reads are cells, finite outside nodes and its own fields (turnover_half_step, turnover_domain_valid): it reads no patch and acts on none |
| species_turnover (13) reads `outside_active` as declared; membrane_insertion_v2 (11) closes it | 4 | real | Turnover reads the declared outside mask at its finite nodes (turnover_half_step); insertion@2 closes onset nodes until their onset |
| species_turnover (13) reads `extracellular_volume` as declared; restricted_lumen_v2 (12) provides it | 2 | real | Turnover's exact update and work read the declared volumes at every cell and finite outside node (turnover_half_step); a lumen changes its node's volume |
| species_exchange (14) reads `extracellular_volume`, `volume` as declared; osmotic_water (1) provides them | 6 | real | Exchange's rates and free energy read the declared volumes |
| species_exchange (14) reads `membrane_area` as declared; membrane_state (6) provides it | 14 | real | Exchange binds each route's declared patch area (uptake per area) |
| species_exchange (14) reads `membrane_active` as declared; membrane_insertion (7) provides it | 4 | real | Exchange moves species across its route patches without reading the patch mask; insertion@1 opens onset patches |
| species_exchange (14) reads `outside_active` as declared; membrane_insertion (7) provides it | 4 | real | Exchange reads the declared outside mask at its route nodes; insertion@1 opens onset nodes |
| species_exchange (14) reads `extracellular_volume` as declared; restricted_lumen (8) provides it | 2 | real | Exchange's rates and free energy read the declared volumes; a lumen changes its node's volume |
| species_exchange (14) reads `active` as declared; partition (9) closes it | 4 | real | Exchange acts on route cells, which the partition can retire (not shown nominal) |
| species_exchange (14) reads `membrane_active` as declared; membrane_insertion_v2 (11) closes it | 4 | real | Exchange moves species across its route patches without reading the patch mask; insertion@2 closes onset patches until their onset |
| species_exchange (14) reads `outside_active` as declared; membrane_insertion_v2 (11) closes it | 4 | real | Exchange reads the declared outside mask at its route nodes; insertion@2 closes onset nodes until their onset |
| species_exchange (14) reads `extracellular_volume` as declared; restricted_lumen_v2 (12) provides it | 2 | real | Exchange's rates and free energy read the declared volumes; a lumen changes its node's volume |
| species_reactions (15) reads `extracellular_volume`, `volume` as declared; osmotic_water (1) provides them | 6 | real | Concentrations and dG read the declared volumes |
| species_reactions (15) reads `extracellular_amount_reference` as declared; membrane_insertion (7) provides it | 4 | real | D152 reads finite nodes' anchors, which insertion@1 changes at its onset nodes (BATH_SCHEDULE_DESIGN.md §3.1) |
| species_reactions (15) reads `outside_active` as declared; membrane_insertion (7) provides it | 4 | real | D152 reads the declared outside mask at its finite sites; insertion@1 opens onset nodes |
| species_reactions (15) reads `extracellular_volume` as declared; restricted_lumen (8) provides it | 2 | real | Concentrations and dG read the declared volumes; a lumen changes its node's volume |
| species_reactions (15) reads `active` as declared; partition (9) closes it | 4 | real | D152's cell sites can be in a cell the partition retires (not shown nominal) |
| species_reactions (15) reads `outside_active` as declared; membrane_insertion_v2 (11) closes it | 4 | real | D152 reads the declared outside mask at its finite sites; insertion@2 closes onset nodes until their onset |
| species_reactions (15) reads `extracellular_volume` as declared; restricted_lumen_v2 (12) provides it | 2 | real | Concentrations and dG read the declared volumes; a lumen changes its node's volume |
| species_reactions (15) reads `extracellular_amount_reference` as declared; bath_schedule (17) provides it | 2 | nominal | D152 reads the anchors only at finite nodes (node_amounts and reactions_domain_valid mask held baths) and refuses held-bath sites (_sites); the bath schedule provides the declared array off its baths and schedules held baths only (held_view, parse_declaration). The bath-schedule design §3.1 |
| species_regulated_availability (16) reads `extracellular_volume` as declared; osmotic_water (1) provides it | 6 | nominal | The coupling's runtime reads are cell amounts, cell volumes and its own fields (route_factors, state_inputs, state_half_step, event_map), and it books nothing; it reads no outside node |
| species_regulated_availability (16) reads `volume` as declared; osmotic_water (1) provides it | 6 | real | The coupling's Hill factors read cell volumes as declared (route_factors, state_inputs); water changes them |
| species_regulated_availability (16) reads `membrane_active`, `outside_active` as declared; membrane_insertion (7) provides them | 4 | nominal | The coupling's runtime reads are cell amounts, cell volumes and its own fields (route_factors, state_inputs, state_half_step, event_map), and it books nothing; it reads no mask, and insertion@1 writes no cell amount or volume and refuses a channel population on an onset patch (check_onsets), so no coupling target sits on one |
| species_regulated_availability (16) reads `extracellular_volume` as declared; restricted_lumen (8) provides it | 2 | nominal | The coupling's runtime reads are cell amounts, cell volumes and its own fields (route_factors, state_inputs, state_half_step, event_map), and it books nothing; it reads no outside node |
| species_regulated_availability (16) reads `active` as declared; partition (9) closes it | 4 | real | A coupling's source cell can retire: the partition moves its amounts to the daughters, so a route or state on it would read moved amounts (not shown nominal) |
| species_regulated_availability (16) reads `membrane_active`, `outside_active` as declared; membrane_insertion_v2 (11) closes them | 4 | nominal | The coupling's runtime reads are cell amounts, cell volumes and its own fields (route_factors, state_inputs, state_half_step, event_map), and it books nothing; it reads no mask, and insertion@2 closes only onset patches and nodes, which hold no channel population (check_onsets), so nothing the coupling reads or multiplies is padded |
| species_regulated_availability (16) reads `extracellular_volume` as declared; restricted_lumen_v2 (12) provides it | 2 | nominal | The coupling's runtime reads are cell amounts, cell volumes and its own fields (route_factors, state_inputs, state_half_step, event_map), and it books nothing; it reads no outside node |
| bath_schedule (17) provides `extracellular_amount_reference` beside the closer partition (9) | 4 | real | Real as the bath-schedule design §3.1 classes it: beside a closer the adapter pads the field (door S). The partition closes no held bath (not shown nominal: the design does not class it so) |
| bath_schedule (17) provides `extracellular_amount_reference` beside the closer membrane_insertion_v2 (11) | 4 | real | Real as the bath-schedule design §3.1 classes it: beside a closer the adapter pads the field (door S). Insertion@2 closes only finite onset nodes, but a lumen, which requires it, fills from its source bath at the declared composition and does not declare that read |
| compartments (18) reads `extracellular_volume`, `volume` as declared; osmotic_water (1) provides them | 6 | real | A compartment's volume is fixed in version 1 (door V, the closed-compartment design §5.3); water changes the volumes of cells and finite nodes, an owner's and a compartment's included |
| compartments (18) reads `membrane_area`, `membrane_capacitance` as declared; membrane_state (6) provides them | 14 | real | The membrane-state wall (the closed-compartment design §4): membrane state provides every patch's area and capacitance as field inputs, a bounding patch's included; sites on a bounding patch wait for this wall's door |
| compartments (18) reads `face_active` as declared; membrane_insertion (7) provides it | 4 | nominal | No face names a compartment's node (refusal 1, parse_declaration), and insertion@1's face view differs from the declared only at faces naming its onset nodes (masks, onset_entities): the slots are disjoint |
| compartments (18) reads `membrane_active`, `outside_active` as declared; membrane_insertion (7) provides them | 4 | real | Insertion@1 closes its onset patches and nodes until their onset, and a bounding patch may be one: a compartment created at an event is FR-2's door C (the closed-compartment design §7) |
| compartments (18) reads `extracellular_volume` as declared; restricted_lumen (8) provides it | 2 | real | A lumen changes its node's volume and requires insertion; a lumen's onset node is not refused as a compartment (not shown nominal) |
| compartments (18) reads `active` as declared; partition (9) closes it | 4 | real | The partition closes and retires cells, an owner included: division of an owner is door D (the closed-compartment design §1.5) |
| compartments (18) reads `membrane_active`, `outside_active` as declared; membrane_insertion_v2 (11) closes them | 4 | real | Insertion@2 closes its onset patches and nodes until their onset, and a bounding patch may be one (FR-2's door C, the closed-compartment design §7) |
| compartments (18) reads `extracellular_volume` as declared; restricted_lumen_v2 (12) provides it | 2 | real | A lumen changes its node's volume and requires insertion; a lumen's onset node is not refused as a compartment (not shown nominal) |

**Rules at the definition** (each operator's `check_definition`; law-level rules refuse a pair or an order whatever the data, data-level rules a condition):

| Rule | Operators | Level | Check | Test | Tag | Why |
| --- | --- | --- | --- | --- | --- | --- |
| insertion@2 precedes every retiring operator | 11, 9 | law, marks 9→11, 9→12, 10→11, 10→12 | `src/cells/models/operators/membrane_insertion_v2.py::check_definition` | `tests/unit/test_membrane_insertion_v2.py::test_definition_refusals` | real | Its step-check share (R5) reads the inserted area. The other order is admitted, as the S5 egg runs it |
| the partition refuses replacement@1 and @2, insertion@1 and lumen@1 | 9, 3, 4, 7, 8 | law, behind a refusal of the declarations | `src/cells/models/operators/partition.py::check_definition` | `tests/unit/test_partition.py::test_a_provider_beside_a_closer_is_refused` | real | partition.REFUSED_LAWS: replacement books at the declared layout; insertion@1 provides the masks and computes at its own view; lumen@1 follows one patch; use restricted_cleft_lumen@2 |
| insertion refuses an operator that books image charge on the declared layout | 7, 11, 3, 4 | law, behind a refusal of the declarations | `src/cells/models/operators/membrane_insertion.py::check_definition` | `tests/unit/test_membrane_insertion.py::test_image_charge_on_the_declared_layout_and_the_node_cap_are_refused` | real | Replacement@1 and @2 write the electrode charge without BOOKS_AT_VIEW, on the declared layout whose capacitance insertion changes |
| an RK4 composition with a coupled operator holds no event maps, split-only parts or integer state | 1, 2, 4 | data | `src/cells/models/pump_composite.py::Composition.check_definition` | `tests/unit/test_pump_composite_rk4.py::test_each_condition_is_refused_beside_each_kind_of_coupled_operator` | real | RK4 integrates the coupled right-hand side unsplit (water@1's coupled split part, the symport's in-step process); replacement@2's events and integer state cannot join it |
| an onset node's volume is its declared anchor: its provider must declare ONSET_ANCHORED_VIEWS | 7 | data | `src/cells/models/operators/membrane_insertion.py::check_definition` | `tests/unit/test_restricted_lumen.py::test_insertions_onset_rule_admits_an_onset_anchored_volume` | real | The node opens with its declared content (D057); water's volume is not anchored |
| every lumen node is a finite onset node of the insertion | 8, 12 | data | `src/cells/models/operators/restricted_lumen.py::check_definition` | `tests/unit/test_restricted_lumen.py::test_definition_refusals` | real | A lumen grows with its patch's inserted area |
| lumen@2: facing patches are onset or live patches, and the onset volume is w A_on / 2 | 12 | data | `src/cells/models/operators/restricted_lumen_v2.py::check_definition` | `tests/unit/test_restricted_lumen_v2.py::test_definition_refusals` | real | Lumen@2 follows the live facing patches at the composite's view |
| a bridge joins one division's daughters, starts closing at its time, and has closed before either daughter divides again | 10, 9 | data | `src/cells/models/operators/bridge_closure.py::check_definition` | `tests/unit/test_bridge_closure.py::test_definition_refusals` | real | An exponential closure never ends, so it is admitted only for a terminal division |
| the partition: activity inside the slots' living intervals, every daughter patch mapped | 9, 5 | data | `src/cells/models/operators/partition.py::check_definition` | `tests/unit/test_partition.py::test_injection_into_a_daughter_closes_every_ledger` | real | A slot exists only between its birth and its retirement |
| insertion@2: onsets and rates inside their cells' living intervals, and no onset at a division's time | 11, 9 | data | `src/cells/models/operators/membrane_insertion_v2.py::check_definition` | `tests/unit/test_membrane_insertion_v2.py::test_definition_refusals` | real | An onset at a division's time is later work |
| replacement@2 refuses law_steady arrival gates over water | 4, 1 | data | `src/cells/models/operators/cell_replacement_v2.py::ScheduledReplacementOverWater.check_definition` | `tests/unit/test_cell_replacement_v2.py::test_the_definition_refusals` | real | Their field solve reads the declared volumes (v2 design §2.6) |
| rates belong to the occupant: templates for newcomers, donor copies only with the slot's route values | 13, 14, 3 | data | `src/cells/models/operators/species_common.py::check_donor_copies` | `tests/unit/test_secreted_species.py::test_a_donor_copy_whose_route_values_differ_is_refused` | real | A carrier's rates are its own (D150 §5.2) |
| no cell route on a slot that replacement@1 replaces | 15, 3 | data | `src/cells/models/operators/species_reactions.py::check_replaced_slots` | `tests/unit/test_species_reactions_refusals.py::test_cell_routes_on_replaced_slots_are_refused_and_outside_routes_compose` | real | Version 1 has no occupant rule for reactions (D152 §7.3's door) |
| no coupling target or regulatory state on a replaced slot | 16, 3 | data | `src/cells/models/operators/species_regulated_availability.py::check_replaced_slots` | `tests/unit/test_species_regulated_availability.py::test_refusals` | real | Version 1 has no occupant rule for the coupling |
| no turnover route on a (species, node) the network writes | 15, 13 | data | `src/cells/models/operators/species_reactions.py::check_turnover_rows` | `tests/unit/test_species_reactions_refusals.py::test_turnover_on_a_row_the_network_writes_is_refused` | real | One local-kinetics writer per row (D152 §1.1) |
| one identity per species across the species operators | 13, 14, 15, 16 | data | `src/cells/models/operators/species_common.py::check_identities` | `tests/unit/test_species_reactions_refusals.py::test_identities_must_agree_with_the_d150_operators_in_either_order` | real | Identity is a declaration of the species, not of an operator |
| at most 16 species per world | 13, 14, 15, 16 | data | `src/cells/models/operators/species_common.py::check_species_cap` | `tests/unit/test_secreted_species.py::test_more_than_sixteen_species_are_refused_with_the_reason` | real | Probed to 16 (FR-9 / D165); above it, another probe |
| beside water@1 every bath step is isosmotic | 17, 1 | data | `src/cells/models/operators/bath_schedule.py::check_definition` | `tests/unit/test_bath_schedule.py::test_beside_water_only_an_isosmotic_step_is_admitted` | real | Water reads the declared bath, its water potential bound at the definition (the bath-schedule design §3.1, door W) |
| cell_owned_compartments@1 composes only with its admitted list, which fails closed | 18 | law, behind a refusal of the declarations | `src/cells/models/operators/compartments.py::check_definition` | `tests/unit/test_cell_owned_compartments.py::test_the_admitted_list_fails_closed` | real | A new operator may treat outside nodes as environment (the closed-compartment design §4); every law off the list is also refused by the declarations |
| replacement@1 schedules no event on a compartment's owner and names no owner as a donor | 18, 3 | data | `src/cells/models/operators/compartments.py::check_definition` | `tests/unit/test_cell_owned_compartments.py::test_replacement_composes_away_from_owners_and_never_on_or_from_one` | real | A newcomer would inherit the compartment's content, and a donor copy takes the donor's cytosolic amounts only (door R, the closed-compartment design §1.5) |
| D152 refuses RK4 | 15 | data | `src/cells/models/operators/species_reactions.py::LocalSpeciesReactions.check_definition` | `tests/unit/test_species_reactions_refusals.py::test_rk4_is_refused_with_its_reasons` | real | Version 1's bookings are exact and checked at rounding under IMEX; D150's RK4 worlds stay the transport's sharp reference, and no consumer needs it (D152 §4.6) |

<!-- composition-matrix: end -->

## The step

For IMEX inner steps, `Phi_dt = P1(dt/2) o ... o Pm(dt/2) o I_dt[view] o Pm(dt/2) o ... o P1(dt/2) o E`:
the event maps first, then the split parts' first halves in declared order, @3's own
checked step at the view behind `jax.lax.optimization_barrier` (or @3's IMEX step with the
in-step process, whose applied transfer and heat the operator books), then the second
halves in reverse order. Idle parts select the inner value; branches are static (operator
list and layout shapes). The empty composition is @3's step itself.

For RK4 (reference runs), a composition with a `coupled` split part or an in-step process
integrates the coupled right-hand side unsplit, as water@1 and water@2 do; it refuses
event maps, `split`-mode parts and integer state. Otherwise the events and exact halves
stay around @3's own RK4 step, as replacement@1 does.

The @3 domain is evaluated at the view of the providers whose view follows their split
part (the current volumes), and re-checked at the step end when one exists; event-driven
route views keep @3's zero pattern, as the frozen models assume.

## Checks and observations

Host and device use @3's own row checks with @3's balances on the declared layout plus
the operators' terms in declared order, the operators' own ledgers after @3's, and the
dissipation fields with the operators' heat. Without operators every check is @3's.
Observations are @3's at each row's view (with factored availabilities held at their
effective values), then each operator's columns; an operator may override the energy
columns (water@2 does).

The step checks are bound to the definition (`bind_step_checks`, used by `core/grid`).
They are @3's bound checks on the operator-adjusted check spec (each operator's
`inner_check_spec`: water's minimum volumes, replacement's worst case), then each
operator's bound checks. What they read from the definition, for example the layouts
of the explicit-rate bounds, is evaluated once per clock at first use, in the order of
`check_steps`. Water@1, water@2 and replacement@1 used to build 5, 6 and 2 layouts per
chunk; they now build that many per clock.

## The entity adapter

The adapter maps operator-provided entity quantities onto @3's layout names and
availabilities onto @3's controls. When an operator provides a capacitance or an activity
mask, it recomputes the derived field arrays (capacitor matrix, scale, solve matrix,
Cholesky factor, fixed and active masks) on the device and selects them only where an
input changed that step. That path covers held-bath topologies only (no floating
components). The recomputation runs every step once a field input is provided (a select by
value), so such a composition is refused above 64 field nodes (option (a) of the v2 design
§3, from the measured cost). The S2 operators, membrane state and insertion, are its first
users.

The adapter is also the declared owner of @3's free energy: `chemical_free_energy_pJ`, each
cell's chemical term against its reference at the declared volume, and
`capacitor_free_energy_pJ`, the capacitor energy. An operator that changes @3's state outside
its step books the exact change with these. Replacement events and injection half-steps do.
With a capacitance or mask view, `view_capacitor_terms` brings @3's capacitor term on the
declared layout to the physical capacitor energy at the view, and the electrode ledger to
the view's plate charges (the energy rule, v2 design §3); `fixed_charge_change` applies one
capacitance change at fixed free-node charges (the insertion law).

## Equivalence with the frozen models (design §3.7)

Bitwise means every compared state field, observation column and `max_` diagnostic equal
under `np.array_equal` (NaN-aware), as the frozen models' own equivalence tests compare;
wherever the guards record bit patterns, they were identical. Every run, its snapshot and
result: `/mnt/workspaces/Cells/composite-s1-20261111-01/README.md`.

- **(a) The empty composition equals `resolved_pump_tissue@3`**
  (`tests/unit/test_pump_composite_identity.py`): heredity cell and seven-cell sheet with
  Euler and ARS(2,2,2), uncompiled, @3's padded reference world, RK4, a vmap batch and
  restart; and the 825-node world (200 steps). Its checked step is @3's own.
- **(b) An idle operator equals the composition without it:** closed water equals the
  empty composition; a symport with no route or every route blocked equals water alone;
  replacement without events equals the empty composition (Euler, ARS(2,2,2), RK4); on
  the 825-node world, closed water and event-free replacement equal @3.
- **(c) Re-expressed water@1, water@2 and replacement@1 equal the frozen models** on their
  test worlds (`test_pump_composite_water.py`, `test_pump_composite_replacement.py`) and
  on their qualification worlds (`validation/tissue/composite_guard.py`, run detached):
  - W1: the six judged trajectories through the judge's windowed path, the P2 stationary
    states (right-hand side, Jacobian and 4-step map at the guesses and the Newton
    solutions) and a 60 s drift from the stationary H state;
  - W2: all eight arms (the same evaluations at every predicted branch, and 1 s
    trajectories);
  - G2-Q1: the nine cases with the device row checks of every row, W37, and Q6's cohorts
    as vmap batches;
  - the 825-node world with closed water and with event-free replacement.

  The dt studies (W1's; G2-Q1's Q5, of which two of eight worlds ran, equal) were not
  repeated. Each world of both studies, traced at 1 ms with dt as an argument, gives
  identical jaxprs for the checked step, right-hand side and device checks; its bound
  inputs (initial state, layout, controls at every change time) have the same shapes and
  dtypes at every step size of the studies and are identical, frozen and thin, at each
  (`composite_crossrev.py`, qualification set). So each step size runs the same program on
  the same inputs. The device checks' constants, which depend on dt, come from @3's own
  function in both.
- **(d) Restart and vmap identity:** restart is bitwise, before, at and after events; vmap
  batches equal the frozen models' batches.

**Thin compositions.** Since the conversion, `frozen_definition` and the thin modules run
one composition, so the guards above would compare the composition with itself. The
comparison with the earlier implementation is across revisions, from the frozen snapshot
against the converted tree:
- `validation/tissue/composite_crossrev.py`: the jaxprs of the checked steps (IMEX and RK4),
  right-hand sides and device checks, traced with dt as an argument, are textually
  identical, and every initial state, layout and control array is identical, on small
  worlds of every structure and on every guarded qualification world (W1, W2, G2-Q1, W37,
  the 825-node world);
- the W2 judge (all eight arms) and W1's stationary phase give identical outputs;
- `validation/tissue/composite_dump.py`: saved runs of short worlds of every structure and
  W2's 1 s trajectories are bit-identical;
- the frozen models' own test files (130 tests) pass unmodified against the thin modules.
