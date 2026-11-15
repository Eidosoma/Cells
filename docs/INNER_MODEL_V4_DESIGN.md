# The inner model made modular, in place (design)

**Status: proposed, 14–15 November 2026, for the lead's review. Revised for D172 and D174.**
- **D172, the user:** "lets just have one model for now, we don't need backwards compatbility at
  this early stage", then "but lets keep the core design we do modular".
- **D174:** an external architecture review, adopted by the lead after review with the advisor. Its
  requirements are in [ARCHITECTURE.md](ARCHITECTURE.md), "The modular core", each marked holds
  today, target or open. This note is the design that meets that section. §0 maps one onto the
  other.
- The commits on this branch keep the earlier drafts: route (c), with a second inner ID beside a
  frozen @3; then a grouped-or-per-law choice that D174 has since settled.
- No engine code was added or changed. Five read-only probes ran (§17).

## The decisions, in plain terms

1. **One inner model, changed once.** Today's model (`resolved_pump_tissue@3`) is restructured in
   one batched round, called R here.
   - Afterwards every channel law, junction law, pump, fuel source and solver is a separate
     declared piece.
   - A world compiles only the pieces it declares.
2. **After R, adding a new law changes nothing for worlds that do not use it** (§2). A new *kind*
   of piece brings its own insertion point, and its landing shows by the routine check that no
   existing world changed. So new physics costs one re-verification round, not one per law.
3. **Every law becomes its own piece (required by D174).** Today all five laws are computed for
   every channel and selected afterwards, even in worlds that have no channels.
   - A probe measured whether separating them moves any result. *Result: §4.*
   - **If results move, even at rounding, R re-runs every registered protocol in full.**
4. **R is accepted by results, not by identical programs** (§3).
   - A named list of required scientific results must actually execute and match.
   - Every existing world gives the same CPU results.
   - A deliberately planted change must be caught.
5. **The GPU** (§5).
   - The three registered L4 tolerance sets were measured on today's programs. R changes those
     programs, so they are re-measured in an L4 gap.
   - Two inventories, which D174 asks for before the GPU acceptance can be written: which checks run
     on the host for every step today, and which parameters are frozen into compiled programs.
6. **Combining mechanisms on parts of one array** (door S, §8). Two mechanisms that touch different
   cells or nodes of the same field are merged slot by slot, not by overwriting the whole field.
   The test case is a bath dose → uptake → a compartment → a reaction inside it.
7. **Ownership is separated from solver cost, and compartments get a host-side identity map**
   (§9).
8. **Fuel** (§10). The requirement is fixed: reactions make and spend fuel, pumps draw from the
   same amounts, and each standard potential has one authority. **Recommended: fuel molecules
   (ATP, ADP, Pi) as ordinary rows of the shared inventory,** with each standard potential declared
   once, where species are declared. The first case is a regeneration reaction and a pump sharing
   finite ATP, ADP and Pi. *Open, possibly for the user.*
9. **The name** (§6). Recommended: keep `resolved_pump_tissue@3`, so registered protocols re-run
   unchanged. *Open.*
10. **When** (§15).
    - After MG0c and Track R's qualification are judged on today's model.
    - With Track E's M2 judged wholly before or wholly after R.
    - With in-flight `src/` branches re-gated after it.
    - At a quiet point, with main tagged first.
11. **Effort** (§15). R is large: eight work packages, about **19–27 agent-days**, landing
    together under one tag and one gate, plus CPU hours for the re-runs and an L4 gap.

**What this note gathers.**
- Track E's channel laws, `junction_ungated@1` and D167's move of the old catalogue
  ([EXCITABLE_TISSUE_DESIGN.md](EXCITABLE_TISSUE_DESIGN.md) §3.2–§3.4, §4, §7, §11; D170).
- FR-4's pump and the energy pool, with FR-2 and FR-5 ([FEATURE_REQUESTS.md](FEATURE_REQUESTS.md);
  D158, D160, D161).
- FR-1's charged door ([CLOSED_COMPARTMENT_DESIGN.md](CLOSED_COMPARTMENT_DESIGN.md) §3.4, §8–§11).
- The coupling note's stage hook ([INVENTORY_COUPLING_DESIGN.md](INVENTORY_COUPLING_DESIGN.md)
  §1.4).
- The bound-term fixes (finding 3, [SHARED_INVENTORY_REACTIONS_DESIGN.md](SHARED_INVENTORY_REACTIONS_DESIGN.md)
  §4.2, §9 Q7, §10.3; the face-free term).
- D174's requirements (ARCHITECTURE.md, "The modular core").

**Engine models:**
- `resolved_pump_tissue@3`, restructured;
- `resolved_pump_composite@1` over it, with every operator that composes over it;
- the definition-time bound shared with @1 and @2 (`surface_pump.explicit_rate_bound`).

**Evidence and log:** [inner-model-v4-20261114-01](/mnt/workspaces/Cells/inner-model-v4-20261114-01/).
HANDOFF.md holds every probe's criterion, written before its run, its amendments and its records.
**S** marks our own derivation or interpretation.

## 0. The note against ARCHITECTURE.md's "The modular core"

| Section of the modular core | This note | Where |
| --- | --- | --- |
| Responsibilities (arrays in the loop; reuse through configuration; D172 drops programs, not results) | **Covered.** Declarations are host objects; the loop stays arrays; the results gate protects results | §2, §3, §7 |
| GPU-native execution: undeclared mechanisms absent | **Covered; this contradicts the earlier grouped option, now dropped.** Per-law dispatch and the five rules | §2, §4 |
| GPU-native execution: same-structure sweeps reuse one executable | **New:** the constants inventory | §5.2, P5 |
| GPU-native execution: state, checks and refusals inside device windows | **New:** the inventory of host checks per row | §5.1 |
| GPU-native execution: no per-cell Python dispatch or CPU solver; compile, memory and end-to-end measured | **Covered** by static dispatch; **new:** the measurements list in the gate | §2, §3 |
| Scoped composition (door S, with the runtime merge) | **New:** the design | §8 |
| Ownership, geometry and solver invalidation; compartment identity as a host map | **New:** the design | §9 |
| Material identity and fuel | **Revised.** The route (c) draft recommended pool state, which contradicts the requirement unless the pool is those amounts. Now: inventory rows, one authority for each standard potential, the first case, the two boundaries | §10 |
| Transport laws by physical contract | **New:** the passive permeation law joins R | §11 |
| State roles and time | **New:** interfaces only | §12 |
| Reuse cases and the results gate | **Revised:** a required-results list that must execute, plus the planted test; the four reuse cases placed | §3, §15 |
| Order | **Covered** | §15 |

## 1. The code facts the design turns on (read at f2ada38d)

### 1.1 What is fixed in today's model

| Item | Where | What it fixes |
| --- | --- | --- |
| The law table | `surface_pump_v3_spec.LAW_CODES`: five laws, codes 0–4 | `domain_valid`'s `laws < len(LAW_CODES)`, a literal 5 in every program, the channel-free one included (P1) |
| Gate rows | `GATED_CODES = 3`; `channel_gate` is [2, channel_slot] | Two relaxation gates or none. A j gate needs a third row |
| The dispatch | `channel_kinetics` → `sodium_channels.kinetics` → `potassium_channels.kinetics` | The Kv1.5, Kir2.1 and NaV1.2 kinetics are traced for every population and selected by code, even with no population (P1). The heredity cells of W1, W2, G2-Q1 and E07, and the 825-node world, declare only Kir2.1 and NaV1.2 |
| Channel ions | `SPECIES_VALENCE = {"Na": 1, "K": 1}` | No Ca²⁺ channel |
| The voltage domain | `VOLTAGE_DOMAIN_V = (−0.120, 0.060)` | One domain for every population, leaks included |
| Kinetics' inputs | `potential_kinetics(potential, p)` | Voltage only, although `explicit_rates` holds the stage concentrations |
| The junction law | `junction_gate.domain_valid`, \|V\| ≤ 0.120, with gate state on every junction | Applied to every junction, pinned and closed ones included |
| The pumps | Na/K (`nak_atp_mass_action_positive@1`) and the calcium pump, with fixed state fields and controls | Fuel is already a declaration, `metabolism.kind = maintained_chemical_reservoirs@1` |
| The bounds | `explicit_rate_bound` (host, declared state, channel-free projection); `membrane_rate` (traced, every stage, actual openings, z²-weighted) | No z = 0 material term (finding 3); no face-free-node term |
| The implicit set | `numerics/surface_imex.py`: (C + a dt L_face) φ = q | "Membranes, junctions, pumps, gates and face diffusion stay explicit" |
| Static switches | `checked_step` branches on layout shape only; `membrane_process` is a keyword of `imex_step` | An empty layout leaf is still a jaxpr input (P1) |
| The view | `pump_composite_adapter.view` | Each provider replaces whole fields; one provider per field (`structure_errors`); `CONFLICTS_VIEW` refuses whole fields |
| The field refresh | `adapter.FIELD_INPUTS`, `refresh_field`, `check_field_inputs` | Any provider of a capacitance or mask, changed or not, puts the refresh in every step and the 64-node cap on the world |

### 1.2 What the operators assume

| Operator | What touches @3's structures |
| --- | --- |
| `scheduled_cell_replacement@1` and `@2` | `STATE_RESETS = (channel_gate, junction_gate)`. Per-population views from template tables keyed by @3's `LAW_CODES`, with `template_channel_gate` [rows, 2, law]. Events call `junction_gate.kinetics` and the formation law |
| `isopotential_partition@1` | `CLOSES = (active,)`, so closed contacts' gates are padded at 0; `STATE_RESETS = (channel_gate, junction_gate)` |
| `cytoplasmic_bridge_closure@1` | `CONTROL_FACTORS = (junction,)`. It requires the partition and writes no gate |
| water@1 and the k-anion symport | Direct imports of `surface_pump_v3`; the symport is @3's in-step process |
| insertion@1 and @2, the lumens | `surface_pump_v3_spec` types; mask, area and outside-volume views |
| `membrane_entity_state@1` | Views of area, capacitance (a field input) and per-population `channel_abundance` |
| Injection, the bath schedule, D150's and D152's operators, the coupling operator | The adapter only |
| `cell_owned_compartments@1` (FR-1, on its branch) | Declaration only: no @3 import, no part, no program. Its refusal 4 names @3's route kinds, so it must fail closed over every declared route kind (§14) |

## 2. The route under D172: what R does

### 2.1 Today's structures become declarations

| Declaration kind | Today's members, declared | Later members (each its own landing) |
| --- | --- | --- |
| Channel law, **one module per law** (D174) | Kv1.5, Kir2.1, NaV1.2, the K and Na leaks | The moved catalogue laws, `fast_sodium_m3hj@1`, the transient outward current, `l_type_calcium_cdi@1` (§13.1) |
| Junction conductance law, per junction | `junction_voltage_relaxation@1` (the default) | `junction_ungated@1` (§13.2) |
| Pump family | Na/K and the calcium pump | Transporters, among them FR-4's pump (§13.3) |
| Fuel kind | `maintained_chemical_reservoirs@1` | Finite fuel on inventory rows (§10) |
| Solver | RK4 (reference runs), `imex_euler_face_electromigration@1`, `imex_ars222_face_electromigration@1` | Implicit-route solvers (§13.4) |

**R also installs D174's targets:**
- door S's runtime merge (§8);
- ownership separated from solver invalidation, and the compartment map (§9);
- one authority for species identity and standard potentials (§10.2);
- state roles and stage-time interfaces (§12);
- the passive permeation law (§11);
- the results gate (§3).

### 2.2 How structure reaches the compiled step

- **Today** the only static switches are a layout leaf's shape and one keyword. A leaf, even an
  empty one, changes every program (P1).
- **A plain @3 definition bypasses the composite's cached key:** `get_model` returns the bare
  module.
- **After R,** `get_model` returns, for every inner-model definition, plain or composite, one
  implementation object cached per declared structure, as the composite's is per operator list.
  Its step closes over that structure as Python values. An undeclared piece is then absent from
  the program, with no leaf.

### 2.3 Why later additions change nothing: five rules

1. **Static dispatch.** Only declared pieces are traced, each law by its own kernel.
2. **No literal depends on the registry.** A definition's codes are checked against its own
   declared set (today's `len(LAW_CODES)` is in every program, P1).
3. **Shapes come from declarations.** Gate rows are the largest declared count. An undeclared kind
   has **no** leaf: absent, not empty (P1).
4. **Codes are stable data.** Each law has a fixed registry code, bound per definition.
5. **The structure is part of the program's identity.** It is in the implementation key and the
   batch signature.

**Two kinds of later addition** (**S**):
- **A new member of a kind R installs** (a channel law, a junction law) changes nothing for worlds
  that do not declare it, by construction.
- **A new kind** brings its own insertion point. Its landing shows crossrev identity for every
  existing world: shown, not assumed.

**Every piece gets D136's idle guard:** declared but switched off, against the world without it,
bitwise. An exactly-zero contribution changes no sum.

**What R does not touch.** The code @3 shares with @1 and @2 (`surface_pump.py`,
`surface_pump_v2.py`, `surface_tissue`, `numerics/surface_transport`): R calls it unchanged. The
one shared-code edit is I0's host-only bound (§13.6), under D148 for @1 and @2.

## 3. The results gate

D174 adds that the gate must name the required scientific cases and check that they actually ran:
today's tier gate compares exit codes and failure counts only, and its counts are stale for about
a dozen files (ARCHITECTURE.md, "Reuse cases and the results gate").

**The required-results list.** A machine-readable list in `validation/`, one entry per result.
- **Each entry names:**
  - the case (a protocol item, a crossrev world or a test node);
  - how it runs;
  - what it must give: a verdict, bit patterns, or a stated tolerance;
  - where its evidence goes.
- **The gate's runner** executes every entry. It **fails if any entry did not execute** (missing,
  skipped or deselected) or differs. Exit codes alone are never read as coverage.

| Part | Entries | Pass |
| --- | --- | --- |
| **G1, existing worlds on CPU** | Every world of the crossrev sets (base, qualification, injection, volume, division, species, reactions, and each operator's own set) and @3's test worlds. Each runs from the tag before R and from the new snapshot. Compared: every state field, observation column and `max_` diagnostic of every accepted row, and every refusal (its step and its message) | Bitwise, NaN-aware, bit patterns compared. **If P2 shows per-law dispatch moves results, a rounding tolerance is stated before the run, reported field by field, and G2 runs in full** |
| **G2, registered protocols re-run** | Every registered protocol whose engine models include the inner model or the composite, listed from each protocol's engine-models field. Known today: W1, W2, G2-Q1, S2, S3, Rm1, S5a, D150's judged run, E07-v1; MG0c and Track R once judged; Track E's M2 if judged before R | Every verdict unchanged; numbers bitwise, or within the protocol's own tolerances |
| **G3, planted changes** | (a) one law coefficient moved by one ulp in a test double (P2's planted arm shows the effect's size); (b) one world parameter moved by one ulp; (c) one required-results entry deleted from a run | The gate must fail all three. If it passes any of them, it is void |
| **G4, measurements** | Compile time, host and device memory, and end-to-end time, on representative compositions: the heredity cell, the 127-cell sheet, a water composition, D150's arm, MG0c's chain, the 825-node world | Reported against the tag; judged only where a protocol registers a bound |
| **The reuse cases** (ARCHITECTURE.md's table) | Inventory → regulation → electrical response (Track R's A4 and A5) now. The other three join the list as they land: bath → uptake → compartment → reaction (§8); reaction → finite fuel → pump (§10); neutral solute and water in a vesicle (§11) | As registered |

**Cost-savers, the lead's call:**
- If G1 is bitwise, E07-v1 can be re-run as a sample (its E1 segments and one arm per group, about 5
  core-hours against about 50).
- Judges that differentiate the step (W1's and W2's stationary parts) re-run in full whatever G1
  shows. D148's first case moved a Jacobian under an identical forward run.

## 4. Per-law dispatch: results and cost (probe P2)

**D174 requires it:** undeclared mechanisms must be absent from the traced program. The grouped
option is dropped.

**P2** is a prototype in the probe only, with each arm in its own process on CPU:
- `base`: today's code;
- `perlaw`: a kernel per declared law;
- `planted`: per-law with one coefficient moved by one ulp.

It ran on seven worlds:
- the heredity cell;
- the five-law padded world;
- the seven-cell gated sheet;
- Track E's generic cell through an action potential at 5 µs;
- the RK4 single patch;
- a water composition;
- the 127-cell sheet.

Every state field of every step was compared bitwise, together with the Jacobians of the
right-hand side and of one step for the heredity cell and the water composition. Two runs per
world gave compile and execution times.

*The result, its cost and its consequence for G1 and G2 are written here from P2's records (§17).*

## 5. The GPU

### 5.1 Inventory 1: what runs on the host for every accepted row today

| Path | On the device, every row | On the host, every accepted row | On the host, observed rows only |
| --- | --- | --- | --- |
| Scalar and windowed runs (`runner._run_segment`, `windows.iter_windows`) | The step's own refusals: domain, controls, the stage rule, the field solve's residual | **All of `check_values`**: @3's row checks, the operators' terms and own ledgers, the retiring operators' actual-domain check (`Composition.check_values`, `_check_actual_domains`) | Observers (`observe_history`); continuity checks (`windows._observation_tail`) |
| Guarded batch (`core/batch.py`) | As above, per world under `lax.map` | **All of `check_values`**, per world | Observers |
| Vector windows (`core/vector_windows.py`) | The step's refusals, and the device row checks (`device_checks`): domain, every ledger (operators' own included, `Composition.DEVICE_CHECKS`), dissipation | **None.** Only per-window summaries leave the device | Observers and continuity checks; the window endpoint |
| Every path, at the definition | — | Parsing, operator refusals, `check_definition`, `StepChecks` (once per clock, by chunk) | — |

- **What this means for D174's "state, step checks and refusals stay inside device windows":** it
  holds today on the vector-window path only (**S**, from the code). It needs `device_checks`,
  which the composite has.
- **Host-only work on that path:** observers, continuity checks on observed rows, and the
  factored availabilities that `held_schedules` holds for observation.
- **Every new piece must give its checks a device form,** as the composite's operators do today.
  A host-only per-row check would take that piece off the vector-window path.

### 5.2 Inventory 2: parameters frozen into programs

*P5's result is written here (§17).*

**What the code says** (**S**): the layout, controls and state reach the window program as
arguments, so a parameter held in the layout is a binding. A value frozen into a program can come
only from three places:
- module constants, which are the same for every world;
- execution-level constants (`device_check_constants`: the material tolerance and the solver's
  energy tolerance);
- a Python value captured from a definition when a program is built.

P5 checks whether any of the third kind exists.

### 5.3 The L4 variants

- **The three registered L4 variants'** terms (W1, W2, G2-Q1) are measured on today's compiled
  programs. The backend term is the largest difference between the CPU reference and each of the
  L4 repeats A, B and D; the run-to-run term is the largest difference between two repeats.
- **So they depend on the compiled program.** Per-law dispatch changes W1's, W2's and G2-Q1's
  programs, since the heredity cells trace fewer kernels.
- **Their terms are therefore re-measured in an L4 gap** (repeats A, B and D) before any L4 item
  is judged on the new code.
- Q7 (D168) stays open either way.

## 6. The name (open)

| Option | For | Against |
| --- | --- | --- |
| **Keep `resolved_pump_tissue@3`** (recommended) | One model, in the user's words. Registered protocols re-run unchanged, since their definitions name @3 and its law IDs | One ID covers two codes, before and after the tag. That is resolved by provenance: every run records its revision, dirty diff and snapshot, and main is tagged just before R |
| Rename once | Old records unambiguous by ID alone | Every registered protocol's definitions name @3, so each would need re-registration, for no change in physics |

**D147, amended by D172 for the inner model:** the inner model's ID names the model, not one
compiled program.
- A restructure that passes the results gate keeps the ID.
- Each **piece** keeps D147's rule: a changed behaviour takes a new ID.
- PROGRESS records the tag that separates the two codes.

## 7. Declarations and static dispatch

### 7.1 A law's declaration

The definition's population format stays as it is. The law, by its ID, declares:

| Field | Meaning |
| --- | --- |
| `LAW_ID` | Versioned and named for its mechanism, never a protein |
| Gates | Names and count of relaxation gates, each advanced by `exponential_mean_rate_linear_target_gates@1` |
| `kinetics(V, reads)`, `opening(gates, V, reads)` | Targets and time constants; a product of gates or an instantaneous function |
| Permeant ions | Species, valence and relative permeability, matched exactly by the parser |
| Reads | Species rows read at each stage, as "species S in compartment C" (§9.2), each with its domain |
| Voltage domain | Its own interval |
| Stage term | Its contribution to the stage rule: by default today's constant-field slope at the actual opening; an instantaneous opening adds an opening-slope term; a reading law adds a loop term |
| RK4 reference step | Its own limit |
| State roles | For its gates: continuous dynamical variables (§12) |
| Provenance | `parity` (moved from the catalogue; moving is not calibrating), `cited` or `calibrated` |

### 7.2 Stage reads of moving rows

- **Three consumers:** Ca-dependent inactivation, a pump on finite fuel, and the stage hook.
- **A read takes each stage's own state** (`imex_step`'s `stage`), so the scheme stays second
  order (**S**; the coupling note's own argument, its §1.4).
- **A reading law declares a loop term** (the coupling note's §1.4 concern).

### 7.3 Domains and bound terms

| Check | Today | After R |
| --- | --- | --- |
| Definition time (host) | `explicit_rate_bound` and the other `StepChecks` | The same, plus I0's terms (§13.6) |
| Every explicit stage | `dt × membrane_rate ≤ 1` | Each declared law's stage term; loop terms; the face-free term where declared |
| Domains | One channel domain; the junction gate's ±120 mV everywhere | Each law's own domains on its own populations; the gate law's domain on gated junctions only |

## 8. Scoped composition: door S's runtime merge (in R)

**Today** (ARCHITECTURE.md, "Scoped composition"):
- The adapter's view applies each provider by replacing the whole field.
- The bath schedule returns its values on its baths and the bound values elsewhere.
- So a second provider on other slots would be overwritten.
- `structure_errors` therefore admits one provider per field, and `CONFLICTS_VIEW` refuses whole
  fields. That is why D152's reactions and the bath schedule refuse each other: the reactions
  declare `extracellular_amount_reference` as read-as-declared.

**What each mechanism declares, per view field:**

| Declaration | Meaning |
| --- | --- |
| Read slots | The entity slots it reads (cells, nodes, patches, populations, contacts), resolved from the definition at binding |
| Read mode | `reference` (the bound, declared values) or `current` (the accumulated view at its stage) |
| Changed slots | The slots it may change. Static, from the definition |
| Contribution | `replace`, `add` or `multiply` |
| Stage | When it is evaluated: at the step's events, in a split half-step, at the view before the inner step, or at observation |

**Admission (host, at the definition):**
- Two providers' changed slots must be disjoint, unless both declare the same commuting
  contribution (`add` with `add`, or `multiply` with `multiply`). The coupling factors on controls
  already multiply in declared order, which is the precedent.
- A `reference` read must not intersect any provider's changed slots at an earlier or equal stage.
- A `current` read is satisfied by every provider evaluated before its stage.
- Anything else is refused with the overlapping slots named.

**The runtime merge** (the adapter's `view`):
- The accumulated view starts from the bound layout.
- Each provider returns values for its own slots only. The composite applies them in declared
  order with a static scatter: set for `replace`, add for `add`, multiply for `multiply`.
- With disjoint slots, or commuting rules, the order cannot change the result.
- A provider whose slots cover a whole field reproduces today's replacement bitwise.

**Changed slots feed §9:** only a field input with changed slots puts the field refresh into the
program (§9.1).

**Acceptance** (ARCHITECTURE.md):
- two providers on disjoint slots compose identically in either declaration order (bitwise);
- an overlap is refused unless a combination rule applies;
- each reader sees the merged values at its declared stage.

**The integration case: bath → uptake → compartment → reaction.**
- FR-10 doses a held bath (`replace` on the bath's slot, at its event).
- D150's exchange takes up from the finite node that a face joins to the bath, into the cell, and
  exports into FR-1's compartment.
- D152's reactions run in the compartment. Their `reference` reads are the compartment's and cells'
  slots, disjoint from the bath's.

**Its checks:**
- material closes across all four, by D150's and D152's own records;
- the requester's first admissible delivery world runs with reactions instead of its turnover
  workaround (FEATURE_REQUESTS.md, FR-1);
- the same world in both declaration orders gives the same bits.

**Effort** (**S**): 3–4 agent-days.
- The contract, the adapter and the composite's slot-level admission.
- Slot declarations for every provider and reader: the bath schedule, water, membrane state,
  insertion, the lumens, replacement, the partition (its closers), and D150's, D152's and the
  coupling operator's reads.

## 9. Ownership, solver invalidation and compartment identity (in R)

### 9.1 Three things kept apart

| Concept | Today | After R |
| --- | --- | --- |
| Owning a membrane population (abundance, sites) | Membrane state provides `channel_abundance`, and its provision of `membrane_capacitance` makes the world a field-input world | An owner declares the population fields it changes; abundance is not a field input |
| Changing geometry or capacitance | Any provider of a field input | Only a mechanism whose **changed slots** include a field input (§8) |
| Invalidating a factorization (the field refresh) | Every step, by value, once any field input is provided; the 64-node cap applies | Only where a field input has changed slots. The refresh and the cap are statically absent otherwise. Option (b) of the v2 design §3, epochs, stays available |

**Acceptance** (ARCHITECTURE.md):
- an occupancy-only world with fixed field inputs has no refresh in its program (crossrev);
- a capacitance-changing world has it, and its view-capacitor terms close;
- ownership-changing operations update the declared resources or refuse.

FR-3's separate owner stays as accepted.

### 9.2 Compartment identity as a host-side map

- **The map** is at the definition boundary, beside species identity (§10.2): compartment ID,
  owner cell, role (cytosol, lysosome, vesicle, ER or mitochondrion), storage slot (today an
  outside node), and its oriented membrane endpoints (bounding patch, inside → outside).
- **It is independent of storage.** Binding resolves it to indices, so programs see only arrays.
- **FR-1's operator becomes the map's first writer:** it keeps its refusals and checks the map,
  not a private parse.
- **Laws address "species S in compartment C".** A sensing or transfer law is written once and
  serves cytosolic, lysosomal and mitochondrial cases. The coupling operator's and D150's
  cell-or-node choices become compartment references.

**Acceptance:**
- two compartments in one cell stay distinct (material, identity and records);
- a law reading "S in compartment C" reads the right slots in a cell with two compartments;
- replacement and the partition refuse owners until their door R and door D land
  (CLOSED_COMPARTMENT_DESIGN §8).

**Not now:** runtime entity objects; nested compartments.

**Effort** (**S**): 2–3 agent-days for §9.1 and §9.2.

## 10. Material identity and fuel (the representation is open)

### 10.1 The requirement, fixed by D174

- Reactions can make and spend fuel.
- Pumps draw from those same amounts.
- Each standard chemical potential has one authority.
- Water and division get explicit interfaces later.

### 10.2 One authority for identity and standard potentials

- **Today** each operator checks the others' declarations: D150's identity form, D152's
  standard potentials in its own block, FR-3's check against both.
- **After R,** species identity, background and trace policy, and each species' standard
  potential are declared once, at the definition boundary. Laws read them; none redeclares them.
- **This is what makes F2 below meet "one authority".**
- **Effort** (**S**): 1.5–2 agent-days, including moving D152's block to read it.

### 10.3 The representation: options against the requirement

| Option | Reactions make and spend it | Pumps draw from the same amounts | One authority per potential | Verdict |
| --- | --- | --- | --- | --- |
| **F1. Pool state:** the older energy family's `finite_energy_pool@1` moved into the inner model as its own per-cell ATP, ADP and Pi | **No.** Reactions act on inventory rows, so they cannot touch pool state without a second door, and then ATP has two accounts | Yes, through `finite_energy.pump_parameters`, which feeds the pool's current concentrations to the **unchanged** pump law at each stage | The pool's transformed potentials, separate from D152's | **Contradicts the requirement, unless the pool *is* the inventory rows, which is F2** |
| **F2. Inventory rows** (recommended) | **Yes.** D152 makes and spends the same rows; Strang splitting around the step stays second order | Yes. The pump law reads the rows at each stage and moves them by its cycles inside the step | Yes, with §10.2. Each writer books its own standard-potential term from the one declared set: D152's operator-owned term, generalised | **Meets it** |
| **F3. A hybrid:** pool state for pumps, rows for reactions, kept in step by an exchange | Through the exchange | Through the pool | Two copies to keep consistent | **Contradicts "one authoritative account"** (ARCHITECTURE.md, "Material identity and fuel") |

**F2's costs** (**S**, 3–4 agent-days with §10.2):
- **In-step writes.** The pump's in-step writes of neutral rows, booked in the inner model's
  ledgers.
- **D150.** D150's operators refuse fuel rows until they book the standard-potential term.
- **A broken invariant to repair.** The coupling operator admits an instantaneous factor only on
  "a row @3's step does not move", detected as neutral with no route
  (`species_common.check_impermeant`; coupling note §1.3–§1.4).
  - A fuel row passes that test, yet the pump moves it in the step, so the factor would lag.
  - Fuel rows must therefore carry a declared "moved by the step" property, read by that admission
    and by every other user of `check_impermeant`.
- **The species cap.** Each fuel species takes a row of the 16-species cap; Syn3A's metabolism may
  need FR-9's probe above 16.
- **The parity reference.** The older family's pool law keeps its value as one: its transformed
  potentials are F2's first parameter set, checked against it in a world without metabolism.

**FR-4's first pump needs none of this:** maintained fuel (today's kind) serves it.

### 10.4 The first case: a regeneration reaction and a pump sharing finite fuel

From ARCHITECTURE.md, "Material identity and fuel": a fixed volume, one cell, finite ATP, ADP and
Pi rows (F2).
- **One explicitly stoichiometric regeneration reaction** (D152) with a declared donor,
  stoichiometry and affinity. A donor is a finite row, or a held species with a declared potential.
  Booked external work is not a fuel law (D174).
- **One Na/K pump** drawing ATP → ADP + Pi in the step.

**It shows, against an independent ODE reference** (written from the equations by an agent who
never reads the code, as Tracks R and E did):
- **depletion:** the donor is exhausted or switched off, and ATP falls;
- **reduced pump activity:** cycles fall with the fuel's affinity and saturation, as the pump law
  gives;
- **recovery:** the donor is restored.

**Checked independently:**
- adenylate and phosphate totals, conserved (`finite_energy.invariants` as the pattern);
- the energy ledger: the change of chemical free energy, with the one set of standard potentials,
  plus the pump's heat, equals the donor's supplied free energy, to rounding.

Water, division and full metabolism are not prerequisites. This is the third reuse case.

### 10.5 Two boundaries to declare

- **Transformed potentials against explicit protons. A prerequisite of FR-4's note.**
  - The older pool law uses transformed ATP, ADP and Pi potentials at buffered pH and Mg.
  - Where FR-4 makes pH dynamic, hydrolysis releases H⁺ explicitly, and untransformed potentials
    apply.
  - FR-4's note must declare, per compartment, which convention holds, and how hydrolysis protons
    are booked across the boundary.
- **Booked work is not fuel.** D152's and D150's booked external work stays a declared
  limit, not a finite fuel. Finite fuel needs the donor, stoichiometry and affinity above.

**Recommendation: F2, with §10.2's single authority.** It is open: it fixes where fuel lives for
every later consumer (FR-2, FR-4's finite fuel, Syn3A's stage 4, the molecular-to-physiology
gate), so the lead may take it to the user.

## 11. Transport by physical contract: a passive permeation law (in R)

- **Today exchange is a driven route.** `scheduled_species_exchange@1` books the free-energy change
  of what it moves as signed work, with no heat (ARCHITECTURE.md, "Transport laws by physical
  contract"). A matching trajectory does not make it passive.
- **A new generic passive law** for neutral species across a patch reuses the common inventory,
  geometry and half-step machinery: CLOSED_COMPARTMENT_DESIGN §2.3's door T1, and FR-5's neutral
  leak.
- **Its acceptance, in a fixed-volume case:**
  - zero net flux at equal chemical potential;
  - reversal when the driving force reverses;
  - conserved material;
  - zero external work;
  - dissipation equal to the free-energy decrease.

  Then its composition with water is qualified, which is the fourth reuse case.
- **Effort** (**S**): 2–3 agent-days. This uses CLOSED_COMPARTMENT_DESIGN §10's estimate of 1.0
  for door T1, plus the contract's qualification and the water composition.

## 12. State roles and stage time (interfaces only, in R)

- **Each state field declares its role:**
  - a continuous dynamical variable;
  - an algebraic or conserved constraint;
  - an accumulated physical history;
  - discrete event state or an exact counter.

  The inner model declares its own fields; the contract gains the declaration for operators'
  `STATE_AXES`. The composite checks that every field has one.
- **Today's coarse and stationary paths handle restricted sets of fields.** They read the roles to
  refuse what they cannot treat. Admitting a composite ID alone would not make them valid
  (ARCHITECTURE.md, "State roles and time").
- **A step context:** each plan receives the interval [t, t + dt], its stage times, and the next
  compulsory event boundary: a dose, a regulatory write or a timed event.
  - Fixed-step runs read it and change nothing; the event-time rule (exact multiples of dt)
    stays.
  - A future coarse step must stop at that boundary.
- **A local implicit or substepped block** for stiff chemistry is allowed by the interface, with
  explicit exchange stages and residual checks. One physical law keeps one ID while its numerical
  treatment evolves.
- **FR-8's acceptance stays open, in FR-8's order.**
- **Effort** (**S**): 1–1.5 agent-days. The declarations, the context and the checks; no algorithm.

## 13. The gathered items

Each lands after R, crossrev-identical for every world that does not declare it, with D136's idle
guard.

### 13.1 Track E's channel laws, and D167's move

- **The catalogue's laws move first** (EXCITABLE_TISSUE_DESIGN §3.3's table).
  - Each becomes a per-law kernel, with an agreement test against the old family's kernel on a
    voltage grid, to rounding (the Hill helper's precedent, coupling note §7.1, item 10).
  - Each keeps its parity status. The old family stays the frozen reference (D167).
- **New laws, only where the moved ones cannot serve:**
  - `fast_sodium_m3hj@1`: three gates, its own domain;
  - `transient_outward_potassium@1`, if needed;
  - `l_type_calcium_cdi@1`: Ca²⁺ permeant, reading "free Ca²⁺ in the cell's cytosol" (§9.2).
    Its calcium needs are a Ca²⁺ row, buffering through the rapid-buffer or charged-reaction
    door, a store (FR-1's compartment with the charged door, or a moved ER law) and an exchanger
    as a transporter. These are M5's calcium move.
- **Qualification:** component references, then Track E's M4 protocol.
- **Closed in version 1:** Markov-form laws and subspace calcium.

### 13.2 `junction_ungated@1`

- **The first law after R.** It is M4's prerequisite, and M3's if the floor fails (D170, ruling 3).
- **The law:** the constant-field flux at availability, with no gate state, and finite voltage as
  its whole domain.
- **Qualification:** EXCITABLE_TISSUE_DESIGN §3.4's four checks.
- **Refused** beside replacement@1 and @2 and the partition (they reset `junction_gate`) and any
  closer (it pads it).

### 13.3 FR-4's pump

- **A declared transporter list,** absent unless declared. Each population names its law, patch,
  capacity density, fuel and availability schedule, and books cycles, transfers, heat and work as
  today's pumps do.
- **The law** (stoichiometry, sources) is FR-4's note's.
- **Maintained fuel first;** finite fuel by §10.

### 13.4 FR-1's charged door, and the implicit routes

- **The bound term:**
  - the definition-time half rides in I0 (§13.6), with a refusal of channels and pumps on a
    face-free node's patch;
  - the stage-time half is a declared stage term.
- **Implicit routes are one family of solver IDs** (**S**): the bounding patch (FR-1 §3.4, door 2)
  and the junction-implicit solver (EXCITABLE_TISSUE_DESIGN §4.2).
  - Each route kind is designed in its consumer's note and qualified on its own.
  - The field-solver interface owns the operator's factor and solve
    ([FIELD_SOLVER_INTERFACE_DESIGN.md](FIELD_SOLVER_INTERFACE_DESIGN.md) §6).

### 13.5 The coupling note's stage hook

- **Closed in version 1.** No consumer is named, and the coupling note's probe P3 comes first.
- **Its shape:** a static keyword of the step that evaluates declared stage factors on each
  stage's state, with a loop term.

### 13.6 The bound-term fixes (I0)

| Term | Shape | Run-time half |
| --- | --- | --- |
| Finding 3's z = 0 material term | 2 × the maximum over neutral species and nodes of Σ P·A/V over junction and membrane routes, on R5's worst cases (water's minimum volumes, insertion's largest areas) | None needed (**S**): it depends on neither openings nor concentrations. The earlier ruling named both functions; the lead decides |
| The face-free-node term | The maximum over **free** face-free finite nodes of Σ_m G_m / C_node at the declared state, with held baths, the gauge and the layout's fixed nodes excluded | A declared stage term in the inner model. Until it exists, channels and pumps on such a patch are refused |

**Parking.**
- CURRENT_PLAN's "parked D148 rounds" (after GH200) are FIELD_SOLVER_INTERFACE_DESIGN §6.5's
  performance candidates. That reason does not apply to I0, which changes no program.
- **"Changes no program" is not "changes no outcome",** so P3 swept the registered and PROPOSED
  protocols' worlds at their registered dt.

*P3's result is written here (§17).*

**Recommendation if P3 refuses nothing:** I0 rides in R, with a D148 record for @1 and @2.

## 14. The operators in R

| Operator | What changes in R | Effort (**S**) |
| --- | --- | --- |
| Replacement@1 and @2 | Template tables keyed by declared law IDs; gate rows from the structure; formation and resets on gated junctions only; slot declarations (§8) | 1.5–2 |
| The partition and the bridge | Resets over declared gate rows; gated junctions only; closer slots (§8) | 1–1.5 |
| Water@1 and the symport | Imports through the restructured module; volume slots (§8) | 0.5–1 |
| Insertion@1 and @2, the lumens | Restructured spec types; changed field-input slots (§8, §9.1) | 0.5–1 |
| Membrane state | Changed-slot declarations, so an abundance-only owner is no field-input world (§9.1) | 0.5 |
| D150's and D152's operators, the coupling operator, the bath schedule, injection | Read and changed slots (§8); compartment references (§9.2); D152 reads the one set of standard potentials (§10.2) | Within §8 and §10.2 |
| **FR-1's `cell_owned_compartments@1`** (in flight) | Generic in code (declaration only, no program), but @3-tied in its refusal 4, which names @3's route kinds. It becomes the compartment map's writer (§9.2) and must refuse **every** declared route kind on a bounding patch, failing closed on kinds it does not know | 0.5, at its re-gate |

**Who needs what:**
- **FR-4's first world needs none of the @3-tied operators.** It uses the bath schedule, the
  compartments, exchange, turnover, reactions and the coupling operator.
- **The lifecycle gate's milestone 2** needs the partition, the bridge, insertion@2, lumen@2,
  water@1 and replacement@2, all adapted in R. Their admissions of new features (a third gate row,
  ungated junctions, transporters, finite fuel) come with their consumers.

## 15. Order and effort

**R** is one batched landing: one tag, one results gate. It comes:
- after MG0c and Track R's qualification are judged;
- with Track E's M2 judged wholly before or wholly after it;
- with in-flight `src/` branches (FR-1's milestone 1, the phase records, FR-10's milestone 2)
  re-gated after it.

Its work packages can run in parallel on disjoint files:

| Work package | Content | Effort (agent-days, **S**) |
| --- | --- | --- |
| WP1. The inner model | §2 and §7: declarations, per-law dispatch, the structure-keyed implementation, I0 if P3 is clean | 4–6 |
| WP2. The operators | §14 | 4–5.5 |
| WP3. Door S | §8 | 3–4 |
| WP4. Ownership and the compartment map | §9 | 2–3 |
| WP5. Identity and standard potentials | §10.2 | 1.5–2 |
| WP6. State roles and stage time | §12 | 1–1.5 |
| WP7. The passive law | §11 | 2–3 |
| WP8. The results gate | §3: the required-results list, G1's comparison tool, the planted tests, G4's measurements | 1.5–2 |
| **R in total** | | **about 19–27**, plus CPU hours (G1 about an hour; G2 the protocols' own costs, with E07-v1 about 50 core-hours in full) and an L4 gap (§5.3) |

**After R, in their accepted order:**
- `junction_ungated@1`: 1.5–2;
- Track E's laws: within M4's 10–15;
- FR-1, FR-3 and the delivery world: the bath → uptake → compartment → reaction case;
- FR-4's transporters: 3–4;
- the fuel case, if F2 is chosen: 3–4 with §10.2 already in R;
- implicit routes: 3–5 per route kind.

The stage hook stays closed.

**What blocks what:**
- **Track E:** M1–M3 run on today's model (M3 needs `junction_ungated@1` only if its floor fails).
  M4 needs R, `junction_ungated@1`, the laws, and the junction route if §4.2's condition fails.
- **FR-4** needs FR-1's milestone 1, P1, its own note (with §10.5's boundary), R, I0 and the
  transporters, plus the patch route for millisecond steps. FR-5 follows.
- **FR-2 and Syn3A's stage 4** need the fuel representation.
- **The four reuse cases** run as the gate's required results as they land.

## 16. Open questions, with recommendations

1. **The fuel representation** (§10), possibly the user's. Recommended: **F2**, inventory rows with
   one authority per standard potential (§10.2). F1 and F3 contradict D174's requirement.
2. **The name** (§6). Recommended: keep `resolved_pump_tissue@3`, with D147 amended as written.
3. **Rounding in G1** (§3, §4). If P2 shows per-law dispatch moves results, the tolerance is
   stated before the run and G2 runs in full. Recommended: as written.
4. **I0** (§13.6): it rides in R if P3 refuses nothing; finding 3's term needs no run-time half;
   the face-free run-time half is a declared stage term.
5. **The cost-savers** (§3): sample E07-v1 only if G1 is bitwise; derivative-program judges always
   in full.
6. **R's size** (§15): one landing of eight work packages. The alternative, landing door S and the
   compartment map first as separate rounds, would re-verify twice. Recommended: one round, the
   packages in parallel.
7. **The stage hook:** closed until a named consumer and the coupling note's P3.

## 17. The probes

All ran read-only from frozen snapshots, on CPU 0, with criteria written in HANDOFF.md before the
runs.

**P1, an as-is trace of today's model** (14 November).
- **The run:** the snapshot of 1f3cb36; 43 s; 0.18 GB.
- **The findings:**
  - the literal 5 (`len(LAW_CODES)`) is in every program, the channel-free one included;
  - every gated law's kinetics are traced even with no channel;
  - an empty layout leaf is a jaxpr input in every program, though `jax.jit` dropped it from the
    lowered StableHLO in one world.

**P2, per-law dispatch against today's** (results and cost). *Entered after the run.*

**P3, the I0 sweep**, with planted controls of known answer. *Entered after the run.*

**P5, the constants inventory.** *Entered after the run.*

(P4, the cost of per-law dispatch, was folded into P2 as its amendment 2.)

## Sources

- The design notes and decisions cited by section.
- ARCHITECTURE.md, "The modular core"; D172; D174.
- The code read at f2ada38d:
  - `models/surface_pump_v3.py`, `core/surface_pump_v3_spec.py`, `models/surface_pump.py`;
  - `models/pump_composite.py`, `models/pump_composite_adapter.py`, `core/pump_composite_spec.py`;
  - `models/operators/`, and FR-1's `compartments.py` on its branch;
  - `core/runner.py`, `core/windows.py`, `core/batch.py`, `core/vector_windows.py`;
  - `numerics/surface_imex.py`;
  - `processes/` (the channel kernels, `junction_gate.py`, `kinetic_pump.py`, `finite_energy.py`);
  - `core/kinetic_finite_spec.py`, `core/surface_energy_spec.py`, `io.py`;
  - `validation/tissue/composite_crossrev.py`, `validation/continuity/probe.py`,
    `validation/tissue/l4_variants/`.

No literature is added by this note.
