# The inner model made modular, in place (design)

**Status: proposed, 14 and 15 November 2026, revised for D172.**
- The user's route (D172): "lets just have one model for now, we don't need backwards compatbility
  at this early stage", then "but lets keep the core design we do modular".
- This note replaces the route (c) draft of the same day, which proposed a second inner ID beside
  a frozen @3. The commits on this branch keep that draft.
- No engine code was added or changed. Three read-only probes ran (§12).

## The decisions, in plain terms

1. **One inner model, changed once.** Today's model (`resolved_pump_tissue@3`) is restructured in
   one batched round, called R here.
   - Afterwards its channel laws, junction laws, pumps, fuel sources and solvers are separate
     declared pieces.
   - A world uses only the pieces it declares, and nothing else is even compiled for it.
2. **After that round, adding a new law changes nothing for worlds that do not use it** (§2.2).
   That holds under five rules, which the round puts in place.
   - A new kind of piece (transporters, for example) brings its own small insertion point, and its
     landing shows by the routine check that no existing world changed.
   - So the cost of the new physics is one re-verification round, not one per law.
3. **The safety check.** "No backwards compatibility" drops old compiled programs, not qualified
   results. So the round must pass a results gate (§3) before it lands:
   - every existing world gives the same CPU results as before;
   - every registered protocol is re-run from a new snapshot;
   - a deliberately planted change must be caught.
4. **Grouped or per-law** (§4). Track E asked for every law to be its own piece. Keeping today's
   five laws as one group is the conservative alternative. A probe tested whether per-law changes
   any result. *Result and recommendation: §4 (P2).*
5. **The GPU** (§5). The three registered L4 tolerance sets were measured on today's compiled
   programs. If the round changes those programs, they are re-measured in an L4 gap.
6. **The name** (§6). Recommended: keep `resolved_pump_tissue@3`, so registered protocols re-run
   unchanged. Old records stay unambiguous through their snapshots and a tag on main just before
   the round.
7. **Fuel for pumps** (§8.3), which may go to the user. Three options are set out. Recommended:
   fuel molecules (ATP, ADP, Pi) as ordinary rows of the shared inventory, so the reactions that
   Syn3A's metabolism needs can make and spend the same fuel the pumps use.
8. **When.** After MG0c and Track R's qualification are judged on today's model; with Track E's M2
   judged wholly before or wholly after; with in-flight `src/` branches re-gated after it; at a
   quiet point, with main tagged first (§10).
9. **Effort** (§10): the round is about 10–14 agent-days, plus CPU hours for the re-runs and an
   L4 gap if the programs change. Each later law is then a small, ordinary landing.

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

**Engine models:** `resolved_pump_tissue@3` (restructured) and `resolved_pump_composite@1` over it,
with every operator that composes over it; the definition-time bound shared with @1 and @2
(`surface_pump.explicit_rate_bound`).

**Evidence and log:** [inner-model-v4-20261114-01](/mnt/workspaces/Cells/inner-model-v4-20261114-01/)
(HANDOFF.md holds every probe's criterion, written before its run, and the records). **S** marks
our own derivation or interpretation.

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
| The pumps | Na/K (`nak_atp_mass_action_positive@1`) and the calcium pump: fixed state fields and controls | Two families. Fuel is already a declaration, `metabolism.kind = maintained_chemical_reservoirs@1` (the only kind `kinetic_finite_spec.parse_pump` admits) |
| The bounds | `explicit_rate_bound` (host, declared state, channel-free projection); `membrane_rate` (traced, every stage, actual openings, z²-weighted) | No z = 0 material term (finding 3); no face-free-node term |
| The implicit set | `numerics/surface_imex.py`: (C + a dt L_face) φ = q | "Membranes, junctions, pumps, gates and face diffusion stay explicit" |
| The step's static switch | `checked_step` branches on layout shape only; `membrane_process` is a keyword of `imex_step` | Every optional piece is selected by a layout leaf's shape, and an empty leaf is still a jaxpr input (P1) |

### 1.2 What the composite and the operators assume

- **One inner.** `INNERS`, `INNER_MODEL_IDS` and the composite spec's `CompositeModel` and
  `projection` are built from @3's dataclass. Under D172 that stays: one inner, restructured.
- **The operators,** by their class declarations and imports:

| Operator | What touches @3's structures |
| --- | --- |
| `scheduled_cell_replacement@1` and `@2` | `STATE_RESETS = (channel_gate, junction_gate)`. Per-population views of `channel_permeability` and `channel_abundance` from template tables keyed by @3's `LAW_CODES`, with `template_channel_gate` [rows, 2, law]. Events call `junction_gate.kinetics` and the formation law |
| `isopotential_partition@1` | `CLOSES = (active,)`: closed contacts' gates are padded at 0. `STATE_RESETS = (channel_gate, junction_gate)` |
| `cytoplasmic_bridge_closure@1` | `CONTROL_FACTORS = (junction,)`. It requires the partition and writes no gate |
| `ideal_osmosis_linear_compliance_water@1`, `k_anion_symport_mass_action@1` | Direct imports of `surface_pump_v3`; the symport is @3's in-step process (`PROCESS`) |
| `scheduled_membrane_insertion@1` and `@2`, `restricted_cleft_lumen@1` and `@2` | `surface_pump_v3_spec` types; views of masks, areas and outside volumes; insertion@2 closes patch and node masks |
| `membrane_entity_state@1` | Views of area, capacitance and per-population `channel_abundance` (generic over the population axis) |
| Injection, the bath schedule, D150's turnover and exchange, D152's reactions, the coupling operator | The adapter only: amount rows, electrode fields and the `junction` and `channel` controls |
| `cell_owned_compartments@1` (FR-1, on its branch) | Declaration only: no @3 import, no part, no program. **But** its refusal 4 names @3's route kinds (a permeability, the two pumps, a channel population), so it must fail closed over every route kind the restructured model declares (§9) |

### 1.3 Checks and checkpoints

- **Crossrev** compares one definition across two revisions: jaxpr text, constants and bindings.
  The continuity probe (D153) adds the lowered StableHLO.
- **Checkpoints.** `io.source_hashes` covers every module. Under D172, old checkpoints are not
  carried across the round; old evidence stays reproducible from its snapshots and tags.

## 2. The route under D172

### 2.1 What the round makes modular

The round turns today's structures into declarations. Nothing new is added in it:

| Declaration kind | Today's members, declared | Later members (each its own landing) |
| --- | --- | --- |
| Channel law | The five laws: one group or five modules (§4) | The moved catalogue laws, `fast_sodium_m3hj@1`, the transient outward current, `l_type_calcium_cdi@1` (§8.1) |
| Junction conductance law, per junction | `junction_voltage_relaxation@1` (the default) | `junction_ungated@1` (§8.2) |
| Pump family | Na/K and the calcium pump, unchanged | Transporters, among them FR-4's acidifying pump (§8.3) |
| Fuel kind | `maintained_chemical_reservoirs@1` | Finite fuel (§8.3) |
| Solver | RK4 (reference runs), `imex_euler_face_electromigration@1`, `imex_ars222_face_electromigration@1` | Implicit-route solvers (§8.4) |
| Stage contributions | — | Stage reads of moving rows, and the closed stage hook (§7.3, §8.5) |

**Kept out of the round on purpose:** new kinds and new laws arrive with their consumers' designs
(D142). The round's own claim is "same results, modular structure", which the results gate
checks (§3).

### 2.2 Why later additions change nothing: the five rules

**How static structure reaches the compiled step.**
- **Today,** the only static switches are a layout leaf's shape and the `membrane_process` keyword
  (§1.1). A new leaf, even an empty one, changes every program (P1).
- **A plain @3 definition bypasses the composite's key:** `get_model` returns the bare @3 module
  for it, so the composite's cached `implementation(inner, laws)` does not cover Track E's plain
  worlds.
- **The round therefore changes how the model is built.** For every definition of the inner
  model, plain or composite, `get_model` returns one implementation object, cached per declared
  structure, as the composite's is cached per operator list. Its step closes over the structure as
  Python values. An undeclared piece is then absent from the program, with no leaf.

After the round, adding a law (or a junction law, transporter, fuel kind or solver) leaves every
world that does not declare it with the same compiled program. That is **text-identical under
crossrev**, the check every operator already passes at landing. It holds by construction if the
round enforces five rules (**S**, each from §1.1's facts):

1. **Static dispatch.** Only declared pieces are traced. There is no "evaluate every registered law,
   then select".
2. **No literal depends on the registry.** Today's `len(LAW_CODES)` is a literal in every program
   (P1, C1). After the round, a definition's codes are checked against its own declared set. A
   grouped five-law form keeps its own literal 5, which a new law does not change.
3. **Shapes come from declarations.**
   - Gate rows are the largest declared gate count: two for today's laws.
   - A kind no world declares contributes **no** layout or state leaf. Absent, not empty: an
     empty leaf is a jaxpr input (P1, C3).
4. **Codes are stable data.** Each law has a fixed registry code, bound per definition, so a new
   law renumbers nothing.
5. **The structure is part of the program's identity.** The composite's implementation key and the
   batch signature carry the declared structure.

**Two kinds of later addition** (**S**):
- **A new member of a kind the round installs:** a channel law, a junction conductance law, or a
  fuel kind once fuel is a kind. It changes nothing for worlds that do not declare it, **by
  construction** under the rules.
- **A new kind** needs its own insertion point in the shared step: transporters, finite fuel,
  stage reads and loop terms, the face-free stage term, implicit routes, the stage hook.
  - The round installs insertion points only for today's kinds.
  - Each new kind's landing adds its own, statically gated as the rules require.
  - At that landing, crossrev identity for every existing world is **shown, not assumed**: the
    standing check.

**Every piece gets D136's idle guard:** declared but switched off (availability or capacity 0)
against the world without it. The target is bitwise, as the coupling operator's claim 2: an
exactly-zero contribution changes no sum.

**The cost is therefore one re-verification round,** not one per law. After it:
- a law of an existing kind lands as an operator lands today, crossrev identical in every
  existing set, with its own worlds' guards and qualification;
- a new kind lands the same way, its crossrev identity shown at its landing.

**What the round does not touch.** @3's step calls code shared with @1 and @2, which stay outside
D172: `surface_pump.py`, `surface_pump_v2.py`, `surface_tissue`, `numerics/surface_transport`.
- The round calls them unchanged and edits none of their traced code.
- The one shared-code edit is I0's host-only bound (§8.6), under D148 for @1 and @2.

**What the rules do not cover:**
- an edit to an existing law's behaviour, which is a new law ID by D147's rule, kept for pieces;
- an edit to the shared step or a shared kernel, which changes existing worlds and needs its own
  gate.

### 2.3 What changes in the same round

- **The inner model:** `surface_pump_v3_spec.py`, `surface_pump_v3.py` and the composite adapter
  are restructured to the declarations of §2.1 and the rules of §2.2.
- **The @3-tied operators change in the same round** (§9). Replacement@1 and @2, the partition,
  the bridge, water@1 and the symport, insertion@1 and @2, and the lumens read the declared
  structures, not @3's closed table and two gate rows.
- **The bound terms (I0):** they can ride in the round (§8.6, after P3's sweep).
- **The crossrev baseline is renewed at the landing.** From then on crossrev identity is the
  standing check for every later addition.

## 3. The results gate (replacing program identity)

"No backwards compatibility" drops old programs, not qualified results. The round lands only if
all three parts pass:

| Part | What is compared | Pass |
| --- | --- | --- |
| **G1, existing worlds on CPU** | Every world of the crossrev sets (base, qualification, injection, volume, division, species, reactions, and each operator's own set) and @3's own test worlds, run on CPU from the tag before the round and from the new snapshot. Every state field, observation column and `max_` diagnostic of every accepted row is compared, and every refusal: its step and its message | Bitwise, NaN-aware, bit patterns compared. A stated rounding is used only if §4's choice requires it; it is fixed before the run and reported field by field |
| **G2, registered protocols re-run** | Every registered protocol whose engine models include the inner model or the composite, re-run from the new snapshot with its own judge. Today: W1, W2, G2-Q1, S2, S3, Rm1, S5a, D150's judged run and E07-v1; MG0c and Track R once judged; Track E's M2 if judged before the round | Every verdict unchanged. Numbers bitwise, or within the protocol's own tolerances where G1 allows rounding |
| **G3, planted changes** | (a) one law coefficient moved by one ulp in a test double (P2's planted arm shows the effect's size); (b) one world parameter moved by one ulp | The gate must fail both. If it passes either, it is void |

**Two cost-savers, for the lead to rule on:**
- **If G1 is bitwise,** a judged experiment's re-run can be a sample: for E07-v1, its E1 segments
  and one arm per group, about 5 core-hours instead of about 50 (E07-v1's budget).
- **Judges that read derivative programs** (W1's and W2's stationary parts, which differentiate
  the step) re-run in full whatever G1 shows. A forward-identical change can still move a
  Jacobian: D148's first case moved 49 judge numbers this way.

**Also in the gate:** tiers 1 to 3, the tier re-measurement, and every in-flight `src/` branch
re-gated on the new main (§10).

## 4. Grouped or per-law dispatch (probe P2)

**The choice.**
- **Grouped:** today's five laws stay one group, evaluated together for every population, as
  today. New laws are per-law modules.
- **Per-law:** every law, today's five included, is its own module, traced only where declared
  (Track E's request, EXCITABLE_TISSUE_DESIGN §3.2).

**What P2 tested.** It is a prototype in the probe only, never under `src/`. Each arm ran in its own
process on CPU:
- `base`: today's code;
- `perlaw`: per-law kernels for the declared laws only;
- `planted`: per-law with one coefficient moved by one ulp.

The worlds:
- the heredity cell;
- the five-law padded world;
- the seven-cell gated sheet;
- Track E's generic cell through an action potential at 5 µs;
- the RK4 single patch.

Every state field of every step was compared bitwise, with the Jacobians of the right-hand side
and of one step for the heredity cell.

*The result and the recommendation are written here from P2's records (§12).*

## 5. The GPU: the L4 variants

- **The three registered L4 variants'** terms (`validation/tissue/l4_variants/`: W1, W2, G2-Q1)
  are measured on today's compiled programs.
  - The backend term is the largest difference between the CPU reference and each of the three
    L4 repeats (A, B, D).
  - The run-to-run term is the largest difference between two repeats.
- **So they depend on the compiled programs.** A different program fuses and reduces differently
  on the GPU, and its CPU reference may move too.
  - **If the round changes W1's, W2's or G2-Q1's programs** (crossrev not identical for the
    qualification set), the three terms are re-measured in an L4 gap (repeats A, B and D, as the
    agreement driver takes them) before any L4 item is judged on the new code.
  - **If those programs stay text-identical,** the terms carry over.
- **Per-law dispatch changes those programs by construction:** the heredity cells trace fewer
  kernels.
- **Q7** (D168) is open in either case.

## 6. The name

| Option | For | Against |
| --- | --- | --- |
| **Keep `resolved_pump_tissue@3`** (recommended) | One model, in the user's words. Registered protocols re-run unchanged: their definitions name @3 and its law IDs | One ID covers two codes, before and after the tag. That is resolved by provenance: every run records its revision, dirty diff and snapshot (AGENTS.md), and main is tagged just before the round |
| Rename once (`resolved_pump_tissue@4`) | Old records unambiguous by ID alone | Every registered protocol's definitions name @3, so each would need an amendment, that is a re-registration, for no change in physics. Old definitions would be refused, which D172 accepts, but the protocols would be stranded |

**D147's amendment** (D172 already amends D147 for the inner model): the inner model's ID names
the model, not one compiled program.
- A restructure that passes the results gate keeps the ID.
- Every **piece** keeps D147's rule: a law, junction law, transporter, fuel kind or solver whose
  behaviour changes takes a new ID.
- The composite ID `resolved_pump_composite@1` is unchanged.
- PROGRESS records the tag that separates the two codes.

## 7. Declarations and static dispatch

### 7.1 A law's declaration

The definition's population format stays as it is: `id`, `membrane_id`, `kinetic_law`,
`max_permeability_m_per_s`, `abundance`, `initial_gate`, `permeant_ions`. The law, by its ID, declares:

| Field | Meaning |
| --- | --- |
| `LAW_ID` | Versioned and named for its mechanism, never a protein (EXCITABLE_TISSUE_DESIGN §3.3) |
| Gates | Names and count of relaxation gates, each advanced by `exponential_mean_rate_linear_target_gates@1` |
| `kinetics(V, reads)` | Target and time constant per gate |
| `opening(gates, V, reads)` | A product of gates, or an instantaneous function |
| Permeant ions | Species, valence and relative permeability, matched exactly by the parser |
| Reads | Species rows read at each stage, on the cell or outside side, with their domains |
| Voltage domain | Its own interval |
| Stage term | Its contribution to the stage rule: by default today's constant-field slope at the actual opening. An instantaneous opening adds its declared opening-slope term; a reading law adds its loop term |
| RK4 reference step | Its own limit |
| Provenance | `parity` (moved from the catalogue; moving is not calibrating), `cited` or `calibrated` |
| Component reference | A test against an independent evaluation of its equations |

### 7.2 Static dispatch

- **The declared structure** is the law set, the junction laws, the pump families and fuel kinds,
  and the solver with its implicit routes. It is a hashable record: static, in the implementation
  key and the batch signature.
- **Each declared piece is traced once,** selected per population by code. An undeclared piece is
  not traced and has no leaf.
- **Gate rows** are the largest declared count. A law's rows beyond its own count are inactive.

### 7.3 Stage reads of moving rows

- **One mechanism, three consumers:** Ca-dependent inactivation reads the cell's Ca²⁺; a pump on
  finite fuel reads its fuel; the coupling hook (§8.5) would read an ion.
- **What is read.** A read takes the stage's own state, the amounts `imex_step` already forms at
  each stage, so ARS(2,2,2) stays second order (**S**). This is the coupling note's own argument for
  evaluation inside the stages (its §1.4). The precedent is the old catalogue's
  `opening(..., calcium_free_mM=)`.
- **A reading law declares a loop term,** because the loop it closes is invisible to a
  voltage-only bound (the coupling note's §1.4 concern).

### 7.4 Domains and bound terms

| Check | Today | After the round |
| --- | --- | --- |
| Definition time (host) | `explicit_rate_bound` at the declared state; the calcium-pump and junction-gate bounds; RK4 law steps | The same, plus I0's terms (§8.6). A law adds a definition-time term only if it declares one |
| Run time (every explicit stage) | `dt × membrane_rate ≤ 1` at the actual openings | Each declared law's stage term (today's laws: unchanged), plus loop terms and the face-free term where declared |
| Domains | One channel domain for all; the junction gate's ±120 mV on every junction | Each law's own domains on its own populations; the gate law's domain on gated junctions only |

## 8. The gathered items

Each item comes after the round, as its own landing, crossrev-identical for every world that does
not declare it.

### 8.1 Track E's channel laws, and D167's move

- **The catalogue's laws move first** (EXCITABLE_TISSUE_DESIGN §3.3's table).
  - Each becomes a per-law kernel in the registry, with an agreement test against the old family's
    kernel on a voltage grid, to rounding. The precedent is the Hill helper (coupling note §7.1,
    item 10).
  - Each keeps its parity status. The old family stays frozen as the reference (D167).
- **New laws, only where the moved ones cannot serve:**
  - `fast_sodium_m3hj@1`: three gates, its own domain (EXCITABLE_TISSUE_DESIGN §7.3);
  - `transient_outward_potassium@1`, if needed;
  - `l_type_calcium_cdi@1`: Ca²⁺ permeant, reading the cell's free Ca²⁺. Its calcium needs are:
    - a Ca²⁺ row, already legal;
    - the stage read (§7.3);
    - buffering, through the rapid-buffer or charged closed-reaction door (D152 §7.3, shared with
      FR-4);
    - a store, either a compartment carrying Ca²⁺ (FR-1 with the charged door) or a moved ER law;
    - an exchanger, as a transporter law.

    These are M5's calcium-handling move.
- **Qualification:** component references, then Track E's M4 protocol.
- **Closed in version 1:** Markov-form laws and subspace calcium.

### 8.2 `junction_ungated@1`

- **The first law after the round.** It is small, it is M4's prerequisite, and it is M3's if the
  sheet's block sites need s·r_gj below 20 (D170, ruling 3).
- **The law:** the constant-field flux at availability, with no gate state and a domain of finite
  voltages only.
- **Qualification:** EXCITABLE_TISSUE_DESIGN §3.4's four checks.
- **Refused in version 1** beside replacement@1 and @2 and the partition (they reset
  `junction_gate`), any closer (it pads it), and so the bridge.

### 8.3 FR-4's pump and fuel (options; this may go to the user)

**How a new pump family enters.** As a declared transporter list, absent unless declared.
- Each population names its law, patch, capacity density, fuel and availability schedule, and books
  cycles, transfers, heat and work as today's pumps do.
- The law itself (stoichiometry, sources) is FR-4's own note's.
- **FR-4's first milestone needs no finite fuel:** maintained fuel (today's kind) serves it. So the
  fuel decision blocks only the consumers of finite fuel: FR-2's retrieval work, D150's and D152's
  pool doors, Syn3A's stage 4 and the molecular-to-physiology gate.

**The precedent for finite fuel.** The older energy family declares `finite_energy_pool@1`
(`energy_pools` per cell, `regeneration_ports` with `driven_atp_regeneration_tanh@1`).
`finite_energy.pump_parameters` hands the **unchanged** pump law the pool's current ATP, ADP and Pi,
and its transformed ΔG°, at each stage. So fuel is a declaration on an unchanged pump law.

| | **F1. Pool state in the inner model** | **F2. Fuel as inventory rows** (recommended) | **F3. A hybrid: pool state coupled to rows** |
| --- | --- | --- | --- |
| What it is | The older family's pool law moved: ATP, ADP and Pi as the inner model's own state per cell, not inventory rows | ATP, ADP and Pi as rows of the one inventory (D150's neutral species), read by the pump law at each stage and moved by its cycles inside the step | A pool in the inner model for the pumps, plus inventory rows for the reactions, kept in step by a declared exchange in each half-step |
| Accounting | The pool's free energy, with transformed potentials at declared pH and Mg, enters the inner ledger; pumps book heat and no external work; the regeneration port books the supplied work | One material ledger per molecule. Each writer of a fuel row (pumps in the step, D152's reactions, D150's operators) books its own standard-potential term with **one shared set of declared potentials**, checked at the definition. That is D152's own rule, an operator-owned standard-potential term, extended to every writer. D150's operators refuse fuel rows until they book that term | Two copies of each molecule, reconciled by the exchange. It breaks the plan's shared-state rule ("when two mechanisms affect the same physical thing, they must change the same state") and FR-3's "never a second copy" |
| D152 composition | **None:** reactions act on inventory rows, so they can neither make nor spend pool fuel without a new door that makes reactions write pool state | **Natural:** reactions make and spend the same rows the pump uses; Strang splitting around the step stays second order. This is what Syn3A's metabolism needs | Through the exchange, at a rate whose stiffness must itself be bounded |
| Cost (**S**) | 2–3 agent-days: the move plus a parity guard against the older family | 3–4 agent-days: the pump's in-step writes of neutral rows, the shared-potential rule and its check, D150's refusals, the guards. **Plus a broken invariant to repair:** accepted designs assume the step never moves a neutral row with no route. The coupling operator admits an instantaneous factor only on "a row @3's step does not move", detected as neutral with no route (`species_common.check_impermeant`; coupling note §1.3–§1.4). A fuel row passes that test, yet the pump moves it in the step, so the factor would lag. Fuel rows must carry a declared "moved by the step" property that this admission, and every other user of `check_impermeant`, reads. Each fuel species also takes a row of the 16-species cap; Syn3A's metabolism may need a probe above 16 (FR-9's) | 4–5 agent-days, plus the exchange's stiffness and the duplicate bookkeeping |
| Risks | Closes Syn3A's route until a door exists; two inventories of ATP once metabolism arrives | One standard-potential owner must be settled with D152's next version; protons from hydrolysis are a declared limit until FR-4's pH is dynamic (then untransformed potentials with explicit H⁺) | Drift between the copies; double booking |

**Recommendation: F2.**
- The fuel is shared physical state, and the metabolism that makes it (Syn3A's stage 4, the
  closed molecular-to-physiology gate) is reactions on the shared inventory.
- The older family's pool law (F1's content) keeps its value as the parity reference: its
  transformed potentials are F2's first parameter set, checked against it on a world without
  metabolism.
- This is a user-level choice because it fixes where fuel lives for every later consumer.

### 8.4 FR-1's charged door, and the implicit routes

- **The bound term:**
  - the definition-time half at the declared state rides in I0 (§8.6), with a refusal of
    channels and pumps on a face-free node's patch in the inner model;
  - the stage-time half (concentrations move) is a declared stage term (§7.4), present only where
    a definition declares an ion route, channel or transporter on such a patch.
- **Implicit routes are one family of solver IDs** (**S**): FR-1's bounding patch
  (CLOSED_COMPARTMENT_DESIGN §3.4, door 2) and Track E's junction-implicit solver
  (EXCITABLE_TISSUE_DESIGN §4.2).
  - Both add electromigration to the operator: (C + a dt (L_face + L_junction + L_patch)).
  - Both declare their routes statically.
  - Each route kind is designed in its consumer's note (the patch in FR-4's, the junctions in
    Track E's) and qualified on its own: P1's two-volume relaxation for the patch (FR-1 §9), R-cable
    and R-wave for the junctions.
  - The field-solver interface owns the operator's factor and solve
    ([FIELD_SOLVER_INTERFACE_DESIGN.md](FIELD_SOLVER_INTERFACE_DESIGN.md) §6). Junction routes add
    cell-to-cell entries to its pattern.

### 8.5 The coupling note's stage hook

- **Closed in version 1.**
  - No consumer is named: ions already enter through regulatory states at second order (coupling
    note §1.4; A2's measured order 2.00, §8.4).
  - The coupling note's probe P3 comes first.
- **Its shape:** a static keyword of the step, as `membrane_process` is, evaluating a factor
  operator's declared stage factors on each stage's state, with a declared loop term.

### 8.6 The bound-term fixes (I0)

| Term | Shape | Run-time half |
| --- | --- | --- |
| Finding 3's z = 0 material term | 2 × the maximum over neutral species and nodes of Σ P·A/V over junction and membrane routes, on the operator-adjusted check specification (R5's worst cases: water's minimum volumes, insertion's largest areas) | None needed (**S**): it depends on neither openings nor concentrations. The earlier ruling named both functions (D152 §9, Q7); the lead decides |
| The face-free-node term | The maximum over **free** face-free finite nodes of Σ_m G_m / C_node at the declared state. Held baths and the gauge are excluded; P5 in `pump_water_predictions.json`, a face-free gauge with an ion route, is the near miss | In the inner model, a declared stage term (§8.4). With a refusal of channels and pumps on such a patch until that term exists |

**Where it lands, and the parking question.**
- **CURRENT_PLAN's "parked D148 rounds"** (item 5, "after GH200") are FIELD_SOLVER_INTERFACE_DESIGN
  §6.5's performance candidates. They change the step program for speed, and the lead parked them
  on 13 November until their value is measured.
  - That reason does not apply to I0, which changes no program and is a stability refusal.
  - I0 is the separate round "queued after D150 v1" (CURRENT_PLAN's composition gate), and D150 v1
    has landed.
- **"Changes no program" is not "changes no outcome":** a tighter bound or a new refusal can refuse
  a world that runs today. P3 swept the registered and PROPOSED protocols' worlds at their
  registered dt.

*P3's result is written here (§12).*

- **The recommendation, if P3 refuses nothing:** I0 rides in the round, so there is one
  re-verification. For @1 and @2, which share the function and stay outside D172, it carries a
  D148 record.

## 9. The operators in the round

**What changes in each @3-tied operator,** so that it reads declarations instead of @3's closed
table:

| Operator | What changes in the round | Effort (**S**) |
| --- | --- | --- |
| Replacement@1 and @2 | Template tables keyed by declared law IDs, gate rows from the structure; formation and gate resets on gated junctions only | 1.5–2 |
| The partition, and the bridge through it | Resets over the declared gate rows; gated junctions only | 1–1.5 |
| Water@1 and the symport | Their direct imports go through the restructured module; the symport's process hook unchanged | 0.5–1 |
| Insertion@1 and @2, the lumens | The restructured spec types | 0.5–1 |
| Membrane state, injection, the bath schedule, D150's and D152's operators, the coupling operator | Nothing but the re-gate | — |
| **FR-1's `cell_owned_compartments@1`** (in flight) | Generic in code (declaration only, no program), but its refusal 4 must refuse **every** declared route kind on a bounding patch, failing closed on kinds it does not know, or a later transporter would slip past it | 0.25, at its re-gate |

**Who needs what:**
- **FR-4's first world needs none of the @3-tied operators.** It uses the bath schedule, the
  compartments, exchange, turnover, reactions (the buffering door) and the coupling operator, all
  generic.
- **The lifecycle gate's milestone 2** (endogenous division) needs the partition, the bridge,
  insertion@2, lumen@2, water@1 and replacement@2. All are adapted in the round for today's
  structures.
- **Admissions for new features** come with their consumers, each with that operator's own guard:
  a third gate row, ungated junctions, transporters and finite fuel beside replacement, the
  partition and water.

## 10. Order and effort

**The round R** is one batched landing at a quiet point:
- after MG0c and Track R's qualification are judged on today's model;
- with Track E's M2 judged wholly before or wholly after it;
- with main tagged just before it;
- with in-flight `src/` branches (FR-1's milestone 1, the phase records, FR-10's milestone 2)
  re-gated on the new main.

| Step | Engine models | Content | Effort |
| --- | --- | --- | --- |
| **R** | The inner model restructured; the composite and every operator over it | §2.1–§2.3: today's structures as declarations, the five rules, the @3-tied operators (§9), I0 if P3 is clean; then the results gate (§3) | About 4–6 agent-days for the model, 4–5.5 for the operators and 1–1.5 for the gate tooling: **about 10–14 agent-days** (**S**). CPU: G1 about an hour; G2 the protocols' own costs (E07-v1 about 50 core-hours in full, about 5 as a sample if G1 is bitwise). An L4 gap if §5 applies |
| `junction_ungated@1` | The inner model | §8.2 | 1.5–2 |
| Track E's laws | The inner model | §8.1: the schema's law fields in use, the moved laws, `fast_sodium_m3hj@1` | Within M4's 10–15 (EXCITABLE_TISSUE_DESIGN §11) |
| Transporters and fuel | The inner model | §8.3: transporters on maintained fuel, then the fuel option chosen | 3–4, plus F2's 3–4 |
| Implicit routes | The inner model with new solver IDs | §8.4, each route kind after its note | 3–5 per route kind |
| The stage hook | — | Closed | — |

**What blocks what:**
- **Track E:** M1–M3 run on today's model (M3 needs `junction_ungated@1` only if its floor fails).
  M4 needs R, `junction_ungated@1`, the laws, and the junction route if §4.2's condition fails.
- **FR-4** needs FR-1's milestone 1, P1, its own note, R, I0 and the transporters, plus the patch
  route for millisecond steps.
- **FR-5** follows FR-4.
- **FR-2 and Syn3A's stage 4** need the fuel option.
- **Track R's second-order factors** need the closed stage hook.

## 11. Open questions, with recommendations

1. **Grouped or per-law** (§4). *Recommendation from P2's result: §4.*
2. **The name** (§6). Recommended: keep `resolved_pump_tissue@3`, with D147 amended as in §6.
3. **The fuel** (§8.3), possibly the user's. Recommended: F2, fuel as inventory rows with one
   shared set of standard potentials.
4. **The gate's cost-savers** (§3): a sampled re-run of E07-v1 if G1 is bitwise. Recommended: yes;
   derivative-program judges always in full.
5. **I0** (§8.6): it rides in the round if P3 refuses nothing; finding 3's term needs no run-time
   half; the face-free run-time half is a declared stage term. Recommended as written.
6. **§6.5's parked performance candidates.** The round changes the step program anyway, so the
   candidates expected to be bitwise could ride in it. Recommended: not until GH200's profile shows
   their value; the round's claim stays "same results".
7. **The stage hook:** closed until a named consumer and the coupling note's P3.

## 12. The probes

**P1, an as-is trace of today's model** (14 November).
- **The run:** the snapshot of 1f3cb36, CPU 0, 43 s, 0.18 GB. Trace and lower only.
- **The findings:**
  - The literal 5 (`len(LAW_CODES)`) is in every program, the channel-free one included.
  - Every gated law's kinetics are traced even with no channel.
  - An empty layout leaf is a jaxpr input in every program, though `jax.jit` dropped it from the
    lowered StableHLO in one world.

**P2, grouped against per-law, on CPU.**
- **The run:** a clean snapshot of Track R's commit 73d7fba5 (`src/` identical to main), on CPU 0.
- *The records and verdicts are entered here after the run.*

**P3, the I0 sweep.**
- **The run:** the same snapshot, host-only.
- *The records and verdicts are entered here after the run.*

## Sources

The design notes and decisions cited by section, D172 on main, and the code read at f2ada38d:
- `models/surface_pump_v3.py`, `core/surface_pump_v3_spec.py`, `models/surface_pump.py`;
- `models/pump_composite.py`, `models/pump_composite_adapter.py`, `core/pump_composite_spec.py`;
- `models/operators/` (the contract and every operator's declarations);
- FR-1's `models/operators/compartments.py` on its branch;
- `numerics/surface_imex.py`, `numerics/exponential_gates.py`;
- `processes/` (the channel kernels, `junction_gate.py`, `kinetic_pump.py`, `finite_energy.py`,
  `cav_channels.py`, `calcium_activated_catalog.py`);
- `core/kinetic_finite_spec.py`, `core/surface_energy_spec.py`, `io.py`;
- `validation/tissue/composite_crossrev.py`, `validation/continuity/probe.py`;
- `validation/tissue/l4_variants/`.

No literature is added by this note.
