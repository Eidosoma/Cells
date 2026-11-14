# The inner model after `resolved_pump_tissue@3` (@4): design (proposed)

**Status: proposed, 14 November 2026, for the lead's review with the advisor.**
- No engine code was added or changed.
- One read-only probe ran: an as-is trace of @3 (§10).
- Every request in this note is a design. Code follows the note's acceptance (D142).

**Why this note exists.** @3 is the composite's one inner model (`pump_composite.INNERS`,
`pump_composite_spec.INNER_MODEL_IDS`). It is qualified and frozen. Four design notes of 14
November each want something inside it, and two bound-term fixes are queued. The lead ruled that
tracks do not fork @3 separately, so this one note gathers them:
1. **Track E's channel laws as declarations,** `junction_ungated@1`, and D167's staged move of the
   old catalogue's laws ([EXCITABLE_TISSUE_DESIGN.md](EXCITABLE_TISSUE_DESIGN.md) §3.2–§3.4, §4,
   §7, §11; D170).
2. **FR-4's acidifying pump and the shared energy pool,** which FR-2 and FR-5 also meet
   ([FEATURE_REQUESTS.md](FEATURE_REQUESTS.md), FR-2, FR-4 and FR-5 with the lead's mappings;
   D158, D160, D161).
3. **FR-1's charged door:** a face-free-node bound term, then an implicit treatment of the bounding
   patch as a new IMEX ID ([CLOSED_COMPARTMENT_DESIGN.md](CLOSED_COMPARTMENT_DESIGN.md) §3.4, §8,
   §9, §11).
4. **The coupling note's stage hook** ([INVENTORY_COUPLING_DESIGN.md](INVENTORY_COUPLING_DESIGN.md)
   §1.4, with §7 and §8 as built).
5. **The bound-term fixes:** finding 3, the z = 0 material term
   ([SHARED_INVENTORY_REACTIONS_DESIGN.md](SHARED_INVENTORY_REACTIONS_DESIGN.md) §4.2, §9 question
   7, §10.3; D152), and the face-free-node term of item 3.

**Engine models it concerns (AGENTS.md milestone rule):**
- `resolved_pump_tissue@3`, frozen;
- `resolved_pump_composite@1` over @3 and over the proposed `resolved_pump_tissue@4`;
- the definition-time bound shared by the resolved pump family (`surface_pump.explicit_rate_bound`).

Each milestone in §7 names the models it runs.

**Evidence and log:** [inner-model-v4-20261114-01](/mnt/workspaces/Cells/inner-model-v4-20261114-01/)
(HANDOFF.md: what was read, the code facts with their files and functions, the probe's criterion
written before its run, and its records). **S** marks our own derivation or interpretation, as in
the D150 and D152 notes.

## 0. Summary

1. **Recommended route: (c), a hybrid** (§2).
   - Everything that touches @3's traced code, or the shape of its state or layout, goes into a
     new inner ID, `resolved_pump_tissue@4`, beside a frozen @3. @4 is built on @3 as @3 was built
     on @2, so a definition that declares only @3's structures runs @3's own programs.
   - The two bound terms enter the definition-time bound, which runs on the host, in one D148 round
     that changes no compiled program and serves @3 and @4 alike.
2. **Why not in place.** @3's step has one static switch, layout shape (§1.1). The probe found the
   law table's length as a literal in every @3 program, and an empty layout leaf as an input of
   every jaxpr (§10). So any in-place addition to @3's traced code is flagged by crossrev in every
   world. It then needs D148 with the baseline renewed and D153 case 2 for live checkpoints, round
   after round. A third gate row, Ca²⁺ channels, a third pump family and per-junction laws change
   shapes or semantics, so they need a new ID anyway (D147).
3. **@4 is open by declaration** (§2.4, §4). A new law, junction law, transporter, fuel or implicit
   route is a new declaration, traced only where a definition declares it. Adding one changes no
   existing program. Crossrev is the standing guard, and a new mechanism takes a new law ID, not a
   new inner ID.
4. **@3's identity under @4** (§3). @3's five laws stay one base group, evaluated by @3's own
   kernels. That is required, because @3 traces all three gated laws for every population, even in
   a channel-free world, and most guarded worlds declare only Kir2.1 and NaV1.2.
   - **The check:** the jaxpr text, constants and bindings, as crossrev compares them, plus the
     lowered StableHLO, as the continuity probe compares it. Both inners are traced in one
     revision, over every crossrev set, with @3's test and qualification worlds run on CPU. It is
     not L4 bitwise equality (D168).
5. **The declarations** (§4). Each law declares:
   - its kinetics and opening, and its gate count;
   - its permeant ions with their valences, and the species rows it reads at each stage;
   - its own voltage domain, its bound term and its RK4 reference step;
   - its provenance status.

   Stage reads of moving rows are one mechanism. It serves Ca-dependent inactivation, a pump fed
   by a pool and, later, the coupling hook.
6. **Placement** (§5).
   - **Track E:** the moved catalogue laws and `fast_sodium_m3hj@1` in I3; the L-type current with
     Ca-dependent inactivation in M5's calcium work; `junction_ungated@1` in I2.
   - **FR-4's pump:** a declared transporter on an unchanged fuel interface in I4, with the fuel
     source declared as today (`metabolism.kind`), and a finite pool moved from the older energy
     family.
   - **FR-1's charged door:** the bound term in I0, and the implicit bounding patch in I5's
     implicit-route solver family, which also hosts Track E's junction-implicit solver.
   - **The stage hook:** a closed door in version 1.
7. **Order** (§7). I0 (the bound round), then I1 (@4 with @3's identity), then I2
   (`junction_ungated@1`), then I3, I4 and I5 as their consumers need them.
   - I1 and I2 are about 5–6 agent-days together.
   - Track E's M4 needs I1–I3, and I5's junction route if EXCITABLE_TISSUE_DESIGN §4.2's condition
     fails.
   - FR-4 needs I0, I1 and I4, and I5's patch route for millisecond steps; FR-5 follows FR-4.
8. **Open questions** (§9). The main one is for the user: D143 adopted one composite over @3, and
   a second inner ID needs that decision's extension. Recommended: yes.

## 1. The code facts the route turns on (read at f2ada38d)

### 1.1 How @3 can be changed without changing its programs

- **@3's step has one static switch: layout shape.**
  - `surface_pump_v3.checked_step(state, dt, control, p, active)` takes RK4 when
    `p.imex_explicit.shape[0] == 0`. Otherwise it calls `imex_step(state, dt, control, p)`.
  - Every layout field is a traced argument.
  - The `membrane_process` hook is a keyword of `imex_step` and `readouts` only. The composite
    reaches it by calling `imex_step` directly when an operator declares `PROCESS`
    (`Composition.split_step`).
- **The one in-place precedent predates program identity.**
  - `junction_heat_trapezoid` is a layout leaf whose shape, 0 or 1, selects the junction-heat
    booking (`trapezoid_nonnegative@1`, commit 8e486406, 11 November).
  - It entered every @3 layout, guarded then by "default runs and fingerprints unchanged" and
    bitwise trajectories (PROGRESS, gap A).
  - D148, of 13 November, and the composite's crossrev came after it.
- **What an in-place addition costs now** (probe, §10).
  - An empty leaf is an input of every @3 jaxpr, which crossrev compares. The lowered StableHLO
    can drop it, since `jax.jit` drops unused arguments by default; world (b) dropped it. The
    text still differs, and D153's case 1 requires the jaxpr to be identical.
  - So each leaf-gated round on @3 costs four things:
    - D148's four criteria with the baseline renewed;
    - the bitwise guard in every qualified world and program kind, the judges' derivative
      programs included (D148's own first case moved 49 judge numbers through a Jacobian);
    - D153 case 2, admitted by the lead, for live checkpoints;
    - a renewed crossrev baseline for every set.
- **Host-only code changes no program.** `surface_pump.explicit_rate_bound` and the `StepChecks`
  classes run on the host at the definition. @1, @2, @3, water, replacement, the composite and
  projective mode share them.

### 1.2 What is closed in @3

| Item | Where | What it fixes |
| --- | --- | --- |
| The law table | `surface_pump_v3_spec.LAW_CODES`: five laws, codes 0–4 | `domain_valid`'s `laws < len(LAW_CODES)`, a literal `5` in every @3 program, the channel-free one included (probe C1) |
| Gated laws and the gate axis | `GATED_CODES = 3`, `GATE_COUNTS`; `channel_gate` is [2, channel_slot] | Two relaxation gates or none. A j gate needs a third row, which changes the state's shape |
| The dispatch | `channel_kinetics` → `sodium_channels.kinetics` → `potassium_channels.kinetics` | The Kv1.5, Kir2.1 and NaV1.2 kinetics are traced for every population and selected by code, even with no population at all (probe C2) |
| The channel ions | `SPECIES_VALENCE = {"Na": 1, "K": 1}`, `LAW_PERMEABILITIES` | No Ca²⁺ channel, so no L-type current |
| The voltage domain | `VOLTAGE_DOMAIN_V = (−0.120, 0.060)`, `channel_domain_valid` | One domain for every active population, leaks included |
| The kinetics' inputs | `potential_kinetics(potential, p)` at each IMEX stage | Voltage only. `explicit_rates` holds the stage concentrations `ci` and `co`, but no kinetics read them |
| The junction law | `junction_gate.domain_valid`, \|V\| ≤ 0.120, with gate state on every junction | Applied to every junction, pinned and closed ones included (EXCITABLE_TISSUE_DESIGN §2.2) |
| The pumps | Na/K (`nak_atp_mass_action_positive@1`) and the calcium pump, each with its own state fields and control (`pump`, `calcium_pump`, `HELD_SCHEDULES`) | Two hard-wired families. The fuel is already a declaration: `metabolism.kind = maintained_chemical_reservoirs@1`, the only kind `kinetic_finite_spec.parse_pump` admits |
| The bounds | `explicit_rate_bound` (host, at the declared state, on the channel-free projection); `membrane_rate` (traced, at each stage's actual openings, z²-weighted) | No z = 0 material term (finding 3) and no face-free-node term (CLOSED_COMPARTMENT_DESIGN §3.4) |
| The implicit set | `numerics/surface_imex.py`: (C + a dt L) φ = q with L the face Laplacian | "Membranes, junctions, pumps, gates and face diffusion stay explicit." The solver IDs are `imex_euler_face_electromigration@1` and `imex_ars222_face_electromigration@1` |

### 1.3 What the composite and the operators assume

- **One inner identity.**
  - `INNERS = {@3}`, and `INNER_MODEL_IDS = (@3,)`.
  - `CompositeModel` and `projection` are built from @3's dataclass at import.
  - But `implementation(inner, laws)` is cached per inner identity, and every
    `Operator.parse(raw, base, inner_model)` receives the inner. The contract was built for more
    than one inner.
- **The operators fall into two groups:**

| Group | Operators | What they assume about the inner |
| --- | --- | --- |
| Adapter or shared code only | `electrode_current_injection@1`, `membrane_entity_state@1`, `scheduled_bath_composition@1`, `scheduled_species_turnover@1`, `scheduled_species_exchange@1`, `local_species_reactions@1`, `species_regulated_availability@1` | @3's view, control and state names through the adapter; species rows; @3's free-energy terms |
| Direct @3 imports or shapes | `scheduled_cell_replacement@1` and `@2` | `LAW_CODES` sizes the template tables; `template_channel_gate` is [rows, 2, law]; events call `junction_gate.kinetics` and the formation law |
| | `isopotential_partition@1` (S5a) and `cytoplasmic_bridge_closure@1`, which requires it | They reset `channel_gate` and `junction_gate` (`STATE_RESETS`) |
| | water@1 and the k-anion symport | They import `surface_pump_v3`; the symport goes through the process hook |
| | insertion@1 and @2, and the lumens | `surface_pump_v3_spec`, the insertion modules |

### 1.4 Crossrev, continuity and checkpoints

- **Crossrev** (`validation/tissue/composite_crossrev.py` and the operator-specific tools) compares
  one definition across two revisions: jaxpr text, closed-over constants and bindings.
  - It does not lower StableHLO; `validation/continuity/probe.py` does (D153).
  - It does not compare rollout programs or host checks (D148).
  - Comparing two inner identities within one revision is a new mode of the tool (§3.2).
- **Checkpoints.** `io.source_hashes` covers every module under `src/cells`.
  - So every landing makes older checkpoints resume only through D153's continuity records.
  - A @3 checkpoint cannot resume as @4: that is D153 case 3, a model ID change, which no record
    relaxes.
  - A @4 run starts fresh, or from imported state as a new run (D153 rule (b); Track E's importer,
    EXCITABLE_TISSUE_DESIGN §4.5, names "@3 (and @4)").

## 2. The route

### 2.1 What each item touches

| What it touches | Items | What it allows |
| --- | --- | --- |
| **Host only** (`explicit_rate_bound`, `StepChecks`) | Finding 3's z = 0 material term; the face-free-node term at the declared state | A D148 round that changes no program |
| **Traced code** (`membrane_rate`, the dispatch, `imex_step`) | Each further law's stage term; the face-free term at stage concentrations; stage reads; the stage hook | In place, a new leaf in every @3 program (§1.1); otherwise a new ID |
| **State or layout shape, or new semantics** | A third gate row; Ca²⁺ and other channel ions; per-law domains; a junction law per junction; a third pump family and its controls; fuel pools; implicit routes | A new ID only (D147; D148's criterion 1 cannot hold when a field's shape changes) |

### 2.2 The options and their costs

| Cost | (a) A new ID, @4, for everything | (b) D148 rounds on @3 | (c) A hybrid: @4, plus one host-only D148 round (recommended) |
| --- | --- | --- | --- |
| **Admissible for the new laws?** | Yes | **No.** New laws, gate rows, ions and pump families are new semantics (D147). A j gate changes the state's shape, so criterion 1 cannot hold | Yes, through @4 |
| **Crossrev** | @3's programs unchanged; the composite's generalization guarded across revisions; a new cross-inner mode (§3.2) | Every @3 program flagged in every set, at every round | As (a). The host-only round changes no program, so its crossrev is identical by construction |
| **Requalification** | None for @3. @4 with @3's structures inherits by program identity (status: the lead's, §9 Q2). Each new law, route or solver is qualified on its own | Every round: bitwise runs in every qualified world and program kind | As (a). The host-only round changes refusals only for definitions no qualified world contains (§5.6) |
| **The composite's single-inner rule** | Two inner identities; `CompositeModel` and `projection` per inner; D143's extension, for the user | Unchanged | As (a) |
| **Operators** | Each declares the inners and @4 features it admits. @3-identical declarations carry over under the identity guard (Q2) | Unchanged contract, but every operator's guard reruns at each round | As (a) |
| **Checkpoints (D153)** | Case 1 for @3 runs across the landing: programs unchanged, decided by the probe. @3 → @4 is refused (case 3) | Case 2, admitted by the lead, after every round | As (a). The host round needs case 1 only |
| **Recurring cost** | None per new law: static dispatch (§4.2) | One round per law: about ten in M4 alone (EXCITABLE_TISSUE_DESIGN §3.3) | As (a) |
| **Risk** | Two inner models to maintain. Mitigated: @4 imports @3's functions and copies none, and the identity guard runs at every @4 landing | Drift of the frozen, qualified model | As (a) |

### 2.3 The recommendation: (c)

- **@4 is a new inner ID, `resolved_pump_tissue@4`, beside a frozen @3.**
  - It is built on @3 as @3 was built on @2. @3's module docstring: "each rate below is @2's
    sequence of operations with the channel terms appended, so with no channels this identity
    reproduces resolved_pump_tissue@2".
  - @4 reproduces @3's programs exactly when a definition declares only @3's structures.
  - It imports @3's functions and copies none.
- **The definition-time bound terms go in one D148 round on the shared host function** (§5.6). @3
  and @4 both use it, and it changes no compiled program. The state-dependent run-time terms go in
  @4 only.
- **Route (b) is used for nothing else.**

### 2.4 What @4's ID promises

- **@4's step is @3's.**
  - Face electromigration is implicit; every other rate is explicit at stage potentials, with
    exponential stage gates and the explicit-stage refusal.
  - Declared laws are evaluated by their own IDs.
- **A definition's programs are fixed by its declarations.** Adding a law, junction law,
  transporter, fuel source or implicit route to @4's registry changes no existing definition's
  program.
- **New mechanisms take new law IDs.** A change to the step itself takes a new solver ID, as the
  implicit routes do (§5.4). Neither takes a new inner ID.
- **The standing guard** is crossrev over every set at every @4 landing, plus the cross-inner
  identity of §3 for @3's structures.
- **Version 1 refuses every structure whose milestone has not landed,** each with its reason.

## 3. @3's identity under @4

### 3.1 What identity forces

- **State, layout and control leaves** equal in order, shape and dtype. A @4 structure that a
  definition does not declare contributes no leaf: it is **absent, not empty**, because an empty
  leaf is a jaxpr input (§10, C3).
- **The bindings:** `channel_laws` holds codes 0–4 for @3's laws.
- **The literals:** the `len(LAW_CODES)` literal 5, `GATED_CODES`, the scalar `VOLTAGE_DOMAIN_V`
  and the gate axis of two.
- **@3's five laws are one base group, evaluated by @3's unchanged kernels.**
  - @3 traces all three gated kinetics for every population (§10, C2). A per-law dispatch would
    trace less, so its text could not equal @3's.
  - Most guarded worlds declare a strict subset: the heredity cells of W1, W2, G2-Q1 and E07 carry
    Kir2.1 and NaV1.2 only, and so does the 825-node world.
  - "Declares only @3's structures" therefore means: @3's five laws or any subset, gated
    junctions, @3's two pump slots with maintained fuel, and @3's two IMEX solvers. Such a
    definition traces exactly @3's program.
- **Mixed definitions.** A definition that also declares a further structure keeps the base group,
  with its domain check restricted to its own populations, and adds one kernel per further law
  (§4.2). Its program is new by design; identity is not claimed for it.

### 3.2 The check

| Part | What is compared | Where |
| --- | --- | --- |
| Programs | For every world of the crossrev sets, the same definition with `inner_model` @3 and @4, traced in one revision: the checked step, the right-hand side and the device row checks. The jaxpr text, constants (dtype, shape, digest) and bindings are compared, as crossrev compares them | A new mode of `composite_crossrev.py` (a validation extension in I1, which runs @3 and @4) |
| Lowered programs | The lowered StableHLO of the checked step, and the vector-window program as `validation/continuity/probe.py` captures it at `.lower()` | The same mode, reusing the probe's capture |
| CPU runs | @3's own test files run with @4 as the inner. The qualification worlds (W1's trajectories, W2's arms, G2-Q1's cases, W37, the 825-node world) run short and are compared bitwise with @3, with every accepted row's host checks | Detached, about an hour of CPU (**S**: two traces per world of about 10–17 s each, from the probe, plus short runs) |

- **Not L4 bitwise equality.** At 825 nodes @3 does not repeat bitwise against itself on the L4
  (D168). Identical programs on identical inputs are what the check establishes. Any GPU item for
  a new structure is a tolerance item of its own.
- **When it runs:** at I1's landing, and as a standing set at every later @4 landing.

### 3.3 What identity confers

That is the lead's ruling to make (§9, Q2). Integration grants no acceptance (D143).

## 4. Declarations and static dispatch

### 4.1 The law declaration

A registry module beside @4 holds one declaration object per law ID. The definition's population
format stays @3's: `id`, `membrane_id`, `kinetic_law`, `max_permeability_m_per_s`, `abundance`,
`initial_gate`, `permeant_ions`.

| Field | Meaning | @3's five laws |
| --- | --- | --- |
| `LAW_ID` | Versioned, named for its mechanism, never for a protein (EXCITABLE_TISSUE_DESIGN §3.3) | As today |
| Gates | Names and count of relaxation gates, each advanced by `exponential_mean_rate_linear_target_gates@1` | 2, or 0 for the leaks |
| `kinetics(V, reads)` | Target and time constant per gate | Voltage only |
| `opening(gates, V, reads)` | A product of gates, or an instantaneous function of V and reads | m·h, m·h², m³·h, 1 |
| Permeant ions | Species, valence and relative permeability, matched exactly by the parser, as `LAW_PERMEABILITIES` | Na⁺ or K⁺ |
| Reads | Species rows read at each stage, on the cell or outside side, each with its domain (positive and finite) | None |
| Voltage domain | Its own interval | (−0.120, 0.060), shared |
| Stage term | Its contribution to the stage rule (§4.4): by default @3's constant-field slope at the actual opening; an instantaneous opening adds its declared opening-slope term | The default |
| RK4 reference step | Its own limit | 2.5 µs (NaV1.2), 25 µs (gated K) |
| Provenance | `parity` (moved from the catalogue; moving is not calibrating, EXCITABLE_TISSUE_DESIGN §3.3), `cited` (a new law from a source), or `calibrated` | `parity` |
| Component reference | A test against an independent evaluation of its equations (EXCITABLE_TISSUE_DESIGN §3.3) | Existing |

**Junction laws, transporters and fuel** are declared in the same way (§5.2, §5.3), each with
its own domain and terms.

### 4.2 Static dispatch

- **The declared structure** is a hashable record of what a definition declares:
  - the law set and the junction laws;
  - the transporters and fuel kinds;
  - the implicit routes.

  It enters the batch signature and the composite's implementation key:
  `implementation(inner, structure, laws)`. Today's `(inner, laws)` stays exact for @3.
- **What gets traced.**
  - The base group is traced when any of @3's laws is declared, and then exactly as @3 traces it.
  - Each further law is traced once, by its own kernel, selected per population by code. This is
    @3's own selection, applied only to declared laws.
  - An undeclared law, structure or route is not traced and has no leaf.
- **Gate rows.** `channel_gate` is [G, slot], with G the largest gate count declared: two for @3's
  structures, three with a j gate. Each law's rows beyond its own count are inactive.
- **Codes.** Further laws take stable codes in @4's registry, from 5. Codes are data, so a batch
  shares one structure and its worlds may differ in values (D148's per-world bindings).

### 4.3 Stage reads of moving rows

- **One mechanism, three consumers.** Ca-dependent inactivation reads the cell's Ca²⁺; a pump fed
  by a pool reads the pool's ATP, ADP and Pi; the coupling hook (§5.5) would read an ion.
- **What is read.** Each read is evaluated on the stage's own state: the amounts after the stage's
  explicit and implicit increments, which `imex_step` already forms (`stage`). It is the same
  sequence that gives the stage voltages.
- **Order (S).** A read enters the explicit rates and the gate targets as any explicit term does,
  so ARS(2,2,2) stays second order. That is the coupling note's own argument for evaluation inside
  the stages (§1.4: "Second order would need the factor evaluated inside @3's stages").
- **The precedent:** the old catalogue's opening `(..., calcium_free_mM=)`
  (`calcium_activated_catalog`).
- **Stability.** The coupling note's loop-gain concern (§1.4) applies to every read: a read closes
  a feedback loop that a voltage-only bound cannot see. So a reading law declares a loop term with
  its stage term (§4.4). For the consumers above the loop is slow beside the step (**S**: cell ion
  and fuel contents relax over seconds or longer, coupling note §1.4's argument), but the term is
  declared, not assumed.

### 4.4 Domains and bound terms in `StepChecks` and the stage rule

| Check | @3 | @4 |
| --- | --- | --- |
| Definition time (host, `StepChecks`) | Face, junction and membrane terms of `explicit_rate_bound` at the declared state; the calcium-pump bound; the junction-gate bound; RK4 law steps | The same, from the shared function, with I0's two terms (§5.6). A further law adds a definition-time term only if it declares one; by default channels are left to the stage rule, as in @3 |
| Run time (traced, every explicit stage) | `dt × membrane_rate ≤ EXPLICIT_STEP_BOUND`, at the actual openings | The base group's term unchanged; each further law's stage term and loop term; the face-free-node term at stage concentrations, present only when a definition declares an ion route, channel or transporter on a face-free node's patch (§5.4) |
| Domains | One channel domain for every population; the junction gate's ±120 mV on every junction | Each law's own voltage and read domains on its own populations, at the definition (every schedule change, as `check_definition`) and at every stage; the gate law's domain on gated junctions only (§5.2) |

## 5. The gathered items

Each item below gives its milestone (§7), what qualifies it, what version 1 refuses, and the
doors left closed.

### 5.1 Track E's channel laws, and D167's move of the catalogue

- **Milestone I3:** the schema of §4 in full (gate rows, reads, per-law domains and terms, Ca²⁺ and
  other channel ions), with every law as a declaration.
- **The catalogue's laws move first** (D167; EXCITABLE_TISSUE_DESIGN §3.3's table).
  - Moving a law means a per-law kernel in @4's registry. An agreement test checks it against the
    old family's code-dispatched kernel on a voltage grid, to rounding. The precedent is the Hill
    helper against D152's inline expression (coupling note §7.1, item 10).
  - The law keeps its source and parity status.
  - The old family stays frozen as the reference once covered (D167).
  - Only the laws a consumer needs move: for M4, the inactivating, instantaneous and sustained K
    laws and the L-type CaV law of §3.3's table.
- **The new mechanisms** (EXCITABLE_TISSUE_DESIGN §3.3), each written only if the moved laws
  cannot serve:
  - `fast_sodium_m3hj@1`: three gates, with the j gate setting slow recovery. Its own domain
    (§7.3).
  - `transient_outward_potassium@1`, if needed: a Kv4-type law, two gates.
  - `l_type_calcium_cdi@1`: Ca²⁺ permeant, with a stage read of the cell's free Ca²⁺. It needs:
    - a Ca²⁺ row in each cell, already legal in @3's specification;
    - the read of §4.3;
    - buffering: the rapid-buffer or charged closed-reaction door (D152 §7.3), shared with FR-4's
      pH. Whether the row is free or total Ca²⁺ follows that choice;
    - release and uptake: an ER or SR store, either a cell-owned compartment carrying Ca²⁺ (FR-1's
      entity with the charged door) or a moved ER law;
    - an exchanger, a transporter law (§5.3).

    These are M5's calcium-handling move (D167; EXCITABLE_TISSUE_DESIGN §11). A subspace
    calcium compartment is not in version 1.
- **Qualification:** each law's component reference, then Track E's M4 references and protocol
  (EXCITABLE_TISSUE_DESIGN §6, §11).
- **Refused in version 1:**
  - replacement@1 and @2 and the partition beside a gate count above two, because their tables and
    resets assume two rows, until each is generalized under its own guard;
  - projective and coarse modes (@1–@3 only);
  - a law named after a protein.
- **Closed doors:** Markov-form laws, which are a second law if a comparison follows such a model
  (EXCITABLE_TISSUE_DESIGN §3.3); subspace calcium.

### 5.2 `junction_ungated@1`

- **Milestone I2,** right after I1. It is Track E's M4 prerequisite, and its M3 prerequisite if the
  sheet's block sites need s·r_gj below 20 (D170, ruling 3).
- **The declaration.** Each junction declares its conductance law. The default is
  `junction_voltage_relaxation@1`: @3's gate, gate state and ±120 mV domain. `junction_ungated@1`
  is the constant-field flux at the junction's availability, with no gate state and a domain that
  asks only for finite voltages (EXCITABLE_TISSUE_DESIGN §3.3).
- **Static.** An ungated junction carries no gate. A definition with no gated junction does not
  trace the gate law.
- **Qualification:** EXCITABLE_TISSUE_DESIGN §3.4's four checks.
  - Inside 120 mV it reproduces @3's pinned-open junction to rounding, in CPU runs of @3's chain
    worlds.
  - Beyond it, a two-cell case matches the appendix's flux, computed independently.
  - Conservation and non-negative heat hold.
  - Probe 2's segment case runs below s·r_gj = 10 without refusal.
- **Refused in version 1:**
  - an ungated junction beside replacement@1 and @2, the partition, the bridge and any closer,
    because they write or pad `junction_gate`;
  - the coupling operator's junction factor on an ungated junction, until its guard reruns.

### 5.3 FR-4's pump and the shared energy pool

- **Milestone I4.** A third pump family enters as a list of declared **transporter populations**,
  absent unless declared.
  - Each population names a law, a patch, a capacity density, its fuel and an availability
    schedule (`transporter_controls`).
  - Its state is cycles, transferred amounts per species, heat and work, as @3's pumps book them.
  - @3's two pump slots stay exactly as they are, which identity requires.
  - The law (stoichiometry, sources, neutral name) is FR-4's own note's. This note fixes only how
    it enters.
- **A transporter law declares:**
  - its roles and stoichiometry, matched exactly by the parser, as the Na/K pump's −3/+2;
  - its rate kernel, in the positive-domain mass-action form of `kinetic_pump` (D111);
  - its domains, as `kinetic_pump`'s affinity bounds;
  - the fuel kinds it admits;
  - its energy roles: heat ≥ 0 from the cycle free energy, and work from its fuel, declared as the
    composite's energy-role table requires (v2 design §1.1);
  - its bound terms: definition time, as `calcium_rate_bound`, and stage time.
- **The fuel is a declaration on an unchanged pump law.** That is how the older family does it:
  `finite_energy.pump_parameters` is a stage-local bridge that hands the unchanged
  `nak_atp_mass_action_positive@1` the pool's current ATP, ADP and Pi concentrations and its
  transformed ΔG°, in place of the maintained parameters.

| Fuel option | Where the pool lives | Stage reads | Energy accounting | Cost |
| --- | --- | --- | --- | --- |
| `maintained_chemical_reservoirs@1` (today) | Parameters | None needed | Metabolic work booked as supplied | None |
| **`finite_energy_pool@1`, moved from the older energy family (recommended)** | @4 state per cell: ATP, ADP and Pi amounts, absent unless declared, with `energy_pools` and `regeneration_ports` (`driven_atp_regeneration_tanh@1`) as `resolved_energy@1` declares them | Yes, through the stage-local bridge (§4.3) | The pool's free energy enters @4's energy ledger. Pumps book heat and no external work; the regeneration port books the supplied work | New state, absent unless declared |
| Pools as inventory rows (D150) | The one inventory | Yes | The standard potentials would need one owner, but D152's operator owns its own standard-potential term (D152) | The species cap, identity rules, and the standard potentials' owner |
| A pool owned by an operator | A composite operator | No: held through the inner step | Booked from the applied cycles after the step | A lag of first order in the coupling (coupling note §1.4's argument) |

- **Operators draw on a pool through the contract's entity writes.** An operator lists the pool's
  inner state in `ENTITY_WRITES`, with owned accumulators and ledger terms, so the pool's ledger
  closes with its draws.
  - That is the energy-pool door of D150 question 11, D152 question 10 and FR-2's retrieval work.
  - Each consumer's note designs its own draw. Version 1 of the pool admits only @4's transporters
    and pumps.
- **Charge.** The older pool law's species "are not ionic charges": pH and Mg are declared and
  buffered. Booking hydrolysis protons on FR-4's H⁺ row is a declared limit in version 1, and a
  door.
- **Qualification:**
  - each transporter law's component reference and NumPy ΔG test (D150's pattern);
  - the moved pool law's agreement with the older family's kernels;
  - conservation of adenylate and phosphorus (`finite_energy.invariants`);
  - the energy ledger closing to rounding with the regeneration port's work.
- **Refused in version 1:**
  - operator draws on a pool;
  - a pool beside replacement@1 and @2 and the partition, until their reset and partition rules
    are written;
  - a transporter on a dividing cell (the partition's existing wall W3a);
  - water with a pool, whose amounts would need the dilution term.
- **Closed doors:** pH-coupled hydrolysis; operator draws; inheritance at division.

### 5.4 FR-1's charged door, and the implicit set

- **The bound term:**
  - the definition-time half at the declared state in **I0**, the host round (§5.6), specified
    after FR-1's probe P1, as the lead ruled;
  - the stage-time half at stage concentrations in @4 only (§4.4).

  With the bound alone, CLOSED_COMPARTMENT_DESIGN §3.4's lysosomal chloride route needs
  dt ≤ about 0.2 ms.
- **The implicit set is one family of solver IDs** (**S**). These are FR-1's bounding patch
  (CLOSED_COMPARTMENT_DESIGN §3.4, door 2) and Track E's junction-implicit solver
  (EXCITABLE_TISSUE_DESIGN §4.2).
  - Both add electromigration to the operator: (C + a dt (L_face + L_junction + L_patch)).
  - Both are solver IDs in `execution.solver`, with the implicit routes declared and static.
  - A new method is a new solver ID (D147;
    [FIELD_SOLVER_INTERFACE_DESIGN.md](FIELD_SOLVER_INTERFACE_DESIGN.md) §6).
- **Milestone I5.** Each route kind is designed and qualified in its own note:
  - the patch in FR-4's note, which owns the first charged compartment;
  - the junctions in Track E's note, when §4.2's condition fails. It is an M4 prerequisite for
    mouse coupling on small cells, and an M3 option at s = 1000 and 5 µs.

  Each route needs its own flux form for the implicit part: constant-field routes linearly implicit
  under frozen slope conductances, as the faces use frozen weights (**S**). Each also needs its own
  heat booking, which the faces book as J²RT/W ≥ 0.
- **The field-solver interface owns the operator's factor and solve** (its §6). Junction routes
  add cell-to-cell entries to the operator's pattern, which a sparse solver's bind must take.
  Field-solver code waits for the GH200 numbers, so I5's dense version comes first, under its own
  ID, and the sparse version under the interface's.
- **Qualification:**
  - P1's reference, the exact two-volume relaxation (CLOSED_COMPARTMENT_DESIGN §9), for the patch;
  - R-cable and R-wave (EXCITABLE_TISSUE_DESIGN §6) for the junctions;
  - at an implicit route's limit of zero conductance, agreement with the explicit ID.
- **Refused in version 1 of @4:** every implicit route until I5. FR-1 version 1's refusal of ion
  routes on a bounding patch stays in force until then.

### 5.5 The coupling note's stage hook

- **A closed door in version 1.**
  - No consumer is named: ions already enter through regulatory states at second order (coupling
    note §1.4; A2's moving input measured order 2.00, §8.4; A4's reciprocal feedback waits for its
    references, §8.5).
  - The coupling note's probe P3, which measures the lag of an instantaneous factor of a moving
    row, comes first.
- **Its shape, when a consumer asks:**
  - a static keyword of @4's `imex_step`, as `membrane_process` is;
  - a factor operator declares stage factors in the contract, an addition that is a strict
    superset;
  - its factors are evaluated on each stage's state (§4.3) and multiply the availabilities at
    every explicit stage;
  - each such factor declares its loop term (§4.4);
  - it is absent unless declared, so no program changes.
- **Qualification:** the coupling note's A4, against R-feedback, at second order with an
  instantaneous factor of an ion row.

### 5.6 The bound-term fixes: one host-only D148 round (I0)

| Term | Its shape | Run-time half? |
| --- | --- | --- |
| **Finding 3's z = 0 material term** on junctions and membranes | A Gershgorin term of the face term's form: 2 × the maximum over neutral species and nodes of Σ P·A/V over that node's junctions and membrane routes. At the declared volumes, or water's minimum volumes through its check specification (R5) (**S**) | **Not needed (S).** P·A/V depends on neither openings nor concentrations, and an availability factor of at most 1 only lowers it. The ruling (D152 §9, Q7) names both functions, so the lead decides (§9, Q3) |
| **The face-free-node term** | The maximum over free face-free finite nodes of Σ_m G_m / C_node, with G_m the constant-field slope at the larger side's declared concentration, as the membrane term takes plasma membranes (CLOSED_COMPARTMENT_DESIGN §3.4, door 1) | **Yes, in @4 only** (§4.4). Its concentration moves; @3 keeps its existing convention for passive routes, the declared state |

**D148's four criteria hold by construction:**
1. No program changes, so no physical field changes.
2. No qualified world declares either structure, so no verdict changes. That is the existing-world
   sweeps of D152 §10.3 and CLOSED_COMPARTMENT_DESIGN §3.4.
3. No ledger changes.
4. The crossrev baseline is renewed at the landing, identical.

**What it adds is a refusal at the definition,** with a test per term, for raw definitions that
today run silently wrong: C4c's 13% at x = 1, and FR-1's dt × rate of 4.8 at 1 ms.
- **Engine models:** the resolved pump family that shares the function; @3 and the composite are
  the ones that matter.
- **Effort:** 1.0–1.5 agent-days (CLOSED_COMPARTMENT_DESIGN §10).

## 6. Operators over @4

- **The declaration.** Each operator declares the inners it admits and, for @4, the features it
  admits. It checks them in `parse(raw, base, inner_model)`, which already receives the inner.
  This implements the lead's Q2 (EXCITABLE_TISSUE_DESIGN §12).
- **At I1,** every operator admits @4 with no feature. Its compositions are then @3's programs,
  and the cross-inner identity of §3.2, over every crossrev set, is their guard.
- **Each later feature** is admitted per operator, with that operator's own guard:

| Feature | Admitted at its milestone | Refused until generalized |
| --- | --- | --- |
| Further channel laws (gate count of 2 or less) | Injection, D150's and D152's operators, the coupling operator, the bath schedule, membrane state | Replacement@1 and @2 (template tables keyed by @3's codes) |
| A gate count above 2 | As above | Replacement@1 and @2, the partition, the bridge |
| `junction_ungated@1` | As above, except the coupling operator's junction target until its guard reruns | Replacement@1 and @2, the partition, the bridge, every closer |
| Transporters, pools | Injection, D150's and D152's operators | Water and what requires it, replacement, the partition, insertion |
| Implicit routes | Decided in each route's note | — |

- **The operator matrix.** The architecture block's table of which operators admit and refuse
  which gains the inner as an axis. That is coordinated through the lead.

## 7. Order and effort

| Milestone | Engine models | Content | Qualification | Effort (agent-days) | Blocks |
| --- | --- | --- | --- | --- | --- |
| **I0** | The resolved pump family's shared bound; @3 and the composite | §5.6: finding 3's term now; the face-free term after P1 | D148's four criteria; a refusal test per term | 1.0–1.5 | FR-4 (the safety net); D150 v1.1's bridge for permeant neutral species |
| **I1** | `resolved_pump_composite@1` over @3 and @4 | The composite's inner generalization (`INNERS`, `CompositeModel`, `projection` and the implementation key per inner); @4's spec (@3's schema with every further key refused); the registry with @3's base group; static dispatch; operators' admission declarations; the cross-inner crossrev mode | §3.2; crossrev across revisions for @3 as the inner; tier files | 3–4 (**S**), plus about an hour of CPU | Everything below |
| **I2** | @4 | `junction_ungated@1` (§5.2) | EXCITABLE_TISSUE_DESIGN §3.4's four checks | 1.5–2 (**S**) | Track E's M4; its M3 if the floor fails |
| **I3** | @4 | §4's schema in full; the moved catalogue laws; `fast_sodium_m3hj@1`, and the transient outward current if needed | Component references; Track E's M4 protocol | 2–3 for the schema (**S**). The laws are within M4's 10–15 (EXCITABLE_TISSUE_DESIGN §11) | Track E's M4 |
| **I4** | @4 | Transporters with maintained fuel, then `finite_energy_pool@1` and its regeneration port (§5.3) | §5.3's list | 3–4, plus 2–3 for the pool (**S**) | FR-4; FR-2's energy source |
| **I5** | @4 with new solver IDs | The implicit routes: the bounding patch, junctions (§5.4) | Each route's own note | 3–5 per route kind (**S**), after its note | FR-4 at millisecond steps; FR-5's pores; Track E's mouse coupling on small cells |
| M5 calcium | @4 | `l_type_calcium_cdi@1` with calcium handling moved (D167) and the buffering door | Track E's M5 | A track of its own (EXCITABLE_TISSUE_DESIGN §11) | Track E's plateau and slow-conduction comparisons |
| (I6) | — | The stage hook: closed (§5.5) | A4 | — | Instantaneous ion sensing, if a consumer asks |

**What blocks what:**
- **Track E's M1–M3** run on @3 and are not blocked. M3 needs I1 and I2 only if its grid goes below
  s·r_gj = 20 (D170, ruling 3).
- **Track E's M4** needs I1–I3, and I5's junction route if §4.2's condition fails. It also needs
  the user's D138 approval and the paper's Supplementary Tables 1–2.
- **FR-4 needs:** FR-1's milestone 1, P1, FR-4's own note, I0, I1, I4, the buffering door (D152's
  charged closed reactions) and, for millisecond steps, I5's patch route.
- **FR-5 needs** FR-1, FR-4, the coupling note's routing door (its §2) and the injury law as an
  operator (D167). From I3 it needs a law reading the compartment's H⁺ on the outside side, and from
  I5 the pores' implicit patch.
- **FR-2 needs** FR-1, I4's pool and the operator-draw door.
- **Track R's second-order factors** need I6, which stays closed until a consumer and the coupling
  note's P3.

**Constraints already in the documents:**
- **Landing windows** (CURRENT_PLAN): nothing under `src/` lands between MG0c's rehearsal and its
  registration. The parked D148 rounds come after GH200, so I0's timing is the lead's (§9, Q4).
- **The field solver** (D147, D156): `field_solver_choice`'s family list gains @4, so a @4
  definition with free offsets declares version 3.
- **Long-time modes:** projective and coarse modes stay @1–@3. A @4 long-time path belongs to
  FR-8's note.
- **Tiers:** they are re-measured after each landing (AGENTS.md).
- **Checkpoints:** each landing needs D153 case 1 records for CPU runs resumed across it.
  Registered runs stay on their snapshots.

## 8. Refused in version 1 of @4, collected

- Every structure whose milestone has not landed: further laws before I3, transporters and pools
  before I4, implicit routes before I5, the stage hook.
- The feature walls of §6's table.
- Projective and coarse modes, and the stationary analysis, which refuses the composite (D150
  probe 2).
- A @3 checkpoint resumed as @4 (D153 case 3).
- Laws named after proteins, and features for one paper (D144).

## 9. Open questions, with recommendations

1. **For the user: a second inner ID beside @3.** D143 adopted one composite over @3.
   - **Recommended: yes.**
     - The composite stays one model: the inner is already a declared field (`inner_model`), and
       the implementation is cached per inner.
     - @3 stays frozen for its qualified worlds and existing definitions.
     - New mechanisms go to @4 as declarations rather than new model families, which keeps D142's
       and D143's intent.
   - **The alternative,** rounds on @3, is not admissible for most items (§2.2).
2. **For the lead: what @3's identity under @4 confers.**
   - **Recommended:** a @4 definition that declares only @3's structures inherits @3's guarded and
     numerically qualified status for the same worlds and programs, as the thin compositions
     inherited the frozen models' (PUMP_COMPOSITE.md, "Thin compositions"). Judged status still
     comes only from registered protocols (D143).
3. **For the lead: finding 3's run-time half.**
   - **Recommended:** none. The material term is state-independent, so the host-only term is
     exact.
   - The face-free term keeps its run-time half, in @4 only.
4. **For the lead: I0's timing.**
   - **Recommended:** land the host-only round when a landing window opens, before GH200. It
     changes no program, so the reason for parking D148 rounds until after GH200 does not apply.
   - The face-free part waits for P1.
5. **For the lead: the base group.**
   - **Recommended:** @3's five laws as one group evaluated by @3's kernels, and per-law kernels for
     every further law (§3.1).
   - Per-law dispatch for all would give up program identity for nearly every guarded world.
6. **For the lead: `junction_ungated@1` right after I1,** even if M3's floor holds.
   - **Recommended: yes.** It is small, it is M4's prerequisite, and it is the first test of the
     declaration path.
7. **For the lead and FR-4's note: the energy pool.**
   - **Recommended:** @4's own pool state, moving `finite_energy_pool@1`, with fuel as a pump
     declaration (§5.3).
   - Not inventory rows, because the standard potential would have two owners.
8. **For the lead: the implicit set.**
   - **Recommended:** one solver-ID family with declared route kinds, each kind designed in its
     consumer's note (the patch in FR-4's, the junctions in Track E's).
   - The field-solver agent is consulted on the operator's pattern (§5.4).
9. **For the lead: the stage hook.**
   - **Recommended:** a closed door until a named consumer and the coupling note's P3.

## 10. The probe

**P1, an as-is trace of @3** (unit `cells-inner-v4-probe1`).
- **The run:** a clean snapshot of 1f3cb36 (source identical to main's f2ada38d under `src/`), on
  CPU 0 with 3G. It took 43 s, peaked at 0.18 GB, and its memory events were all zero.
- **The method:** trace and lower only. Nothing was patched and nothing compiled. JAX 0.11.1, with
  x64 on.
- **The criterion** was written in HANDOFF.md before the run. Its records are in `probe1/`.

| Criterion | (a) Heredity cell D: Kir2.1, NaV1.2 | (b) v3 release: five laws, padded | (c) No channel | Verdict |
| --- | --- | --- | --- | --- |
| C0: two traces identical | Yes | Yes | Yes | The control holds |
| C1: `lt … 5:i64[]` | 2 | 2 | 2 | The table's length is in every @3 program |
| C2: Kv1.5's literals | Present | Present | Present | Every gated law is traced, even with no channel. Kir2.1's and NaV1.2's literals are present in (c) too |
| C3: the empty `junction_heat_trapezoid` leaf in the jaxpr | Input 105 of 106, `float64[0]` | The same | The same | An empty leaf is an input of every jaxpr |
| C3: the lowered StableHLO | 98 of 106 arguments kept | 99 of 106; no zero-size argument kept | 96 of 106 | `jax.jit` drops unused arguments. In (b) the empty leaf is not in the lowered module; (a) and (c) cannot tell |

**What it settles.**
- Adding a law code changes every @3 program.
- Per-law dispatch cannot reproduce @3's text.
- An in-place leaf is flagged by crossrev, and fails D153's case 1, even where the lowered module
  may be unchanged.
- @4's undeclared structures must therefore be absent, not empty.

## Sources

The design notes and decisions cited by section above, and the code read at f2ada38d:
- `models/surface_pump_v3.py`, `core/surface_pump_v3_spec.py`, `models/surface_pump.py`;
- `models/pump_composite.py`, `models/pump_composite_adapter.py`, `core/pump_composite_spec.py`;
- `models/operators/` (the contract and every operator's imports);
- `numerics/surface_imex.py`, `numerics/exponential_gates.py`;
- `processes/sodium_channels.py`, `potassium_channels.py`, `voltage_gates.py`, `junction_gate.py`,
  `kinetic_pump.py`, `finite_energy.py`, `calcium_activated_catalog.py`, `cav_channels.py`;
- `core/kinetic_finite_spec.py`, `core/surface_energy_spec.py`, `io.py`;
- `validation/tissue/composite_crossrev.py`, `validation/continuity/probe.py`.

No literature was added by this note. The laws' sources are those of the notes that propose them.
