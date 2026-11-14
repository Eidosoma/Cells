# The inner model after `resolved_pump_tissue@3` (@4): design

**Status: DRAFT, paused on 14 November 2026 at the lead's request (the agent cap).** Not for
review yet. This draft holds the code facts the route turns on and the leaning route, so that
the work resumes from them. Sections marked *TODO* are unwritten. No engine code was added or
changed, and no probe has run. Where the work stopped:
`/mnt/workspaces/Cells/inner-model-v4-20261114-01/HANDOFF.md`.

**Why this note exists.** @3 is the composite's one inner model (`pump_composite.INNERS`,
`pump_composite_spec.INNER_MODEL_IDS`). It is qualified and frozen. Four design notes of 14
November each want something inside it, and two bound-term fixes are queued. The lead ruled that
tracks do not fork @3 separately: this note gathers them all.
- Track E's channel laws as declarations, `junction_ungated@1` and D167's staged move of the old
  catalogue's laws ([EXCITABLE_TISSUE_DESIGN.md](EXCITABLE_TISSUE_DESIGN.md) §3.2–§3.4, §4, §7,
  §11; D170).
- FR-4's acidifying pump and the shared energy pool, which FR-2 and FR-5 also need
  ([FEATURE_REQUESTS.md](FEATURE_REQUESTS.md), FR-2, FR-4, FR-5; D158, D160, D161).
- FR-1's charged door: a face-free-node bound term, then an implicit treatment of the bounding
  patch as a new IMEX ID ([CLOSED_COMPARTMENT_DESIGN.md](CLOSED_COMPARTMENT_DESIGN.md) §3.4, §8,
  §9, §11).
- The coupling note's stage hook ([INVENTORY_COUPLING_DESIGN.md](INVENTORY_COUPLING_DESIGN.md)
  §1.4, §7, §8).
- The bound-term fixes: finding 3, the z = 0 material term
  ([SHARED_INVENTORY_REACTIONS_DESIGN.md](SHARED_INVENTORY_REACTIONS_DESIGN.md) §4.2, §9 question
  7, §10.3; D152), and the face-free-node term above.

## 1. The code facts the route turns on (read at f2ada38d)

### 1.1 How @3 can be changed without changing its programs

- **@3's step has one static channel: layout shape.** `surface_pump_v3.checked_step(state, dt,
  control, p, active)` takes RK4 when `p.imex_explicit.shape[0] == 0` and otherwise calls
  `imex_step(state, dt, control, p)`. Every layout field is a traced argument.
- **The `membrane_process` hook** is a keyword of `imex_step` and `readouts` only. The composite
  reaches it by calling `imex_step` directly when an operator declares `PROCESS`
  (`Composition.split_step`). A plain @3 definition never passes it.
- **The precedent for an opt-in in place:** `junction_heat_trapezoid`, a layout leaf whose shape
  (0 or 1) selects the junction-heat booking (`trapezoid_nonnegative@1`, commit 8e486406). The
  module docstring says every @3 layout carries it, empty by default.
- **So every statically gated addition to @3's traced code needs a new layout leaf,** and an empty
  leaf is still a new jaxpr input in every @3 program (*to confirm*: an as-is trace, §8). Each such
  in-place round would cost D148's four criteria with the baseline renewed, a bitwise guard over
  every qualified world in every program kind (the judges' derivative programs included), and
  D153 case 2, lead-admitted, for live checkpoints.
- **Host-only code changes no program.** `surface_pump.explicit_rate_bound` and the `StepChecks`
  classes run on the host at the definition. They are shared by @1, @2, @3, water, replacement,
  the composite and projective mode.

### 1.2 What is closed in @3

| Item | Where | What it fixes |
| --- | --- | --- |
| The law table | `surface_pump_v3_spec.LAW_CODES`: five laws, codes 0–4 | `domain_valid` checks `laws < len(LAW_CODES)`, a literal in every @3 program, with or without channels |
| Gated laws | `GATED_CODES = 3`, `GATE_COUNTS` | Codes below 3 have two relaxation gates; leaks have none |
| The gate axis | `channel_gate`, [2, channel_slot]; `channel_gate_active` | Two rows. A slow-recovery j gate needs a third, which changes the state's shape |
| The dispatch | `channel_kinetics` → `sodium_channels.kinetics` → `potassium_channels.kinetics` | The Kv1.5, Kir2.1 and NaV1.2 kinetics are evaluated for every population and selected by code, so a world that declares a subset still traces all three |
| The channel ions | `SPECIES_VALENCE = {"Na": 1, "K": 1}`, `LAW_PERMEABILITIES` | No Ca²⁺ channel, so no L-type current |
| The voltage domain | `VOLTAGE_DOMAIN_V = (−0.120, 0.060)`, `channel_domain_valid` | One domain for every active population, leaks included |
| The kinetics' inputs | `potential_kinetics(potential, p)` at each IMEX stage | Voltage only. `explicit_rates` holds the stage concentrations (`ci`, `co`), but the kinetics never read them |
| The junction law | `junction_gate.domain_valid`, \|V\| ≤ 0.120 | Applied to every junction, pinned and closed ones included |
| The pumps | Na/K (`nak_atp_mass_action_positive@1`) and the calcium pump, each with its own state fields and control (`pump`, `calcium_pump`, `HELD_SCHEDULES`) | Two hard-wired families. ATP, ADP and Pi are held parameters, and `metabolic_work_pJ` books the supplied work |
| The bounds | `explicit_rate_bound` (host, at the declared state, on the channel-free projection); `membrane_rate` (traced, at each stage's actual openings, z²-weighted) | No z = 0 material term (finding 3) and no face-free-node term (FR-1 §3.4) |

### 1.3 What the composite and the operators assume

- **One inner identity.** `INNERS = {@3}` and `INNER_MODEL_IDS = (@3,)`. `CompositeModel` and
  `projection` are built from @3's dataclass at import. But `implementation(inner, laws)` is
  already cached per inner identity, and each operator's `parse(raw, base, inner_model)` receives
  the inner identity, so a per-operator admitted-inner declaration fits the contract as built
  (the lead's Q2: each composition over a new inner model gets its own guard).
- **Operators that import only the adapter or shared code:** injection, membrane state, the bath
  schedule, D150's turnover and exchange, D152's reactions, the coupling operator.
- **Operators that import @3 directly or assume its shapes:**
  - replacement@1: `LAW_CODES` sizes its template tables, `template_channel_gate` is
    [rows, 2, law], and its events call `junction_gate.kinetics` and the formation law;
  - replacement@2: replacement@1 over water;
  - partition: resets `channel_gate` and `junction_gate` (`STATE_RESETS`); the bridge requires it;
  - water@1 and the symport: import `surface_pump_v3` (the symport through the process hook);
  - insertion@1 and @2, the lumens: `surface_pump_v3_spec` or the insertion modules.
- **Crossrev** (`validation/tissue/composite_crossrev.py` and the operator-specific tools) compares
  one definition across two revisions: jaxpr text, closed-over constants and bindings. It does not
  lower StableHLO; `validation/continuity/probe.py` does (D153). Comparing two inner identities
  within one revision is a new validation mode, in a milestone that runs @3 and @4.
- **Checkpoints.** `io.source_hashes` covers every module under `src/cells`, so any landing makes
  older checkpoints resume only through D153's continuity records. A @3 checkpoint cannot resume as
  @4 (D153 case 3, a model ID change); a @4 run starts fresh or from imported state (D153 rule (b),
  Track E's importer, EXCITABLE_TISSUE_DESIGN §4.5).

## 2. The route (leaning; not yet argued in full)

Sort each gathered item by what it touches; the route follows from that.

| What it touches | Items | Route |
| --- | --- | --- |
| **Host only** (`explicit_rate_bound`, `StepChecks`) | Finding 3's z = 0 material term; the face-free-node term at the declared state | One D148 round that changes no program, shared by every family that uses the bound |
| **Traced code** (`membrane_rate`, the dispatch, `imex_step`) | Each law's run-time bound term; stage reads of moving rows; the stage hook | A new ID: in place it needs a new layout leaf in every @3 program |
| **State or layout shape** | A third gate row; Ca²⁺ and other channel ions; a third pump family with its fields and control; the junction law per junction; fuel pools; implicit routes | A new ID only |

**The leaning route is (c), a hybrid:**
- **@4, a new inner ID beside a frozen @3**, built on @3 as @3 was built on @2 (@3 reproduces @2
  when no channels are declared). @4 reproduces @3's programs exactly when a definition declares
  only @3's structures. It is open by declaration: a new law, junction law, pump family or
  implicit route is a new declaration, statically gated, so adding one changes no existing
  program, and crossrev is the standing guard.
- **One host-only D148 round** for the definition-time bound terms, which serves @3 and @4 alike.
  *Open:* whether finding 3's term needs its run-time half at all. A neutral species' P·A/V
  depends on neither openings nor concentrations, but the ruling (§9 question 7 of the reactions
  note) names both functions. The face-free charged term does need a run-time half, because the
  concentration enters, and that half belongs to @4.
- **Route (b), in-place rounds on @3,** is not available for the new laws: a j gate changes the
  state's shape, and new semantics take new IDs (D147). *TODO:* the costs in full.
- **D143 is a user decision that names @3.** A second inner ID is a question for the user, with
  this note's recommendation (§7).

## 3. @3's identity under @4 (*TODO*: the check in full)

What identity forces, from §1:
- state, layout and control leaves equal in order, shape and dtype;
- `channel_laws` codes 0–4 for @3's laws, by binding identity;
- the `len(LAW_CODES)` literal, `GATED_CODES`, the scalar `VOLTAGE_DOMAIN_V` and the gate axis of
  two;
- **@3's five laws dispatched as one base group by @3's unchanged kernels.** Per-law static
  dispatch cannot be text-identical for an @3 world, because @3 traces all three gated kinetics
  for every population. *TODO:* sweep which guarded worlds declare a strict subset of @3's laws
  (the 825-node world declares NaV1.2 and Kir2.1 only).

The check: jaxpr text, constants and bindings as crossrev compares them, the lowered StableHLO as
the continuity probe compares it, and @3's test and qualification worlds run on CPU. Not L4
bitwise equality (D168). *Open for the lead:* what status identity confers, since integration
grants no acceptance.

## 4. Law declarations (*TODO*)

To cover: the schema (kinetics, opening, gate count, permeant ions with valences, ligand reads at
stages, voltage domain, the conductance-bound term, the RK4 reference step, provenance status);
static dispatch; how each law's domain and bound term enter `StepChecks` and `membrane_rate`.
Stage reads of moving rows are one mechanism shared by Ca-dependent inactivation, a pool-fed pump
and the coupling hook; the old catalogue's `opening(..., calcium_free_mM=)` is the precedent, and
the coupling note's loop-gain concern (§1.4) applies to all three.

## 5. The gathered items (*TODO*: milestone, qualification, refusals, doors for each)

Organised by shared mechanism:
- **The IMEX implicit set.** FR-1's bounding patch and Track E's junction-implicit solver
  (EXCITABLE_TISSUE_DESIGN §4.2) are one kind of change: solver IDs in `execution.solver`.
  *TODO:* read the IMEX part of [FIELD_SOLVER_INTERFACE_DESIGN.md](FIELD_SOLVER_INTERFACE_DESIGN.md)
  before placing them.
- **Charged closed reactions or a rapid buffer.** FR-4's pH buffering and M5's calcium buffering
  are one door (D152 §7.3).
- **Pumps and fuel.** *TODO:* read `finite_energy.pump_parameters` and the
  `role_inputs`/`pump_parameters` path; the fuel source may be a declaration on an unchanged pump
  law. Stoichiometry and sources stay with FR-4's own note.
- **`junction_ungated@1`.** Refused beside replacement, partition and the bridge, which write
  `junction_gate`.
- **The stage hook.** No named consumer: ions already enter through regulatory states at second
  order (coupling note §1.4), and its probe P3 comes first. A closed door in version 1.

## 6. Order and effort (*TODO*)

Constraints already in the documents:
- **D170 ruling 3:** `junction_ungated@1` becomes an M3 prerequisite if the sheet's block sites
  need s·r_gj below 20. So the smallest first milestone is @3's identity plus the junction law.
- **CURRENT_PLAN:** the parked D148 rounds come after GH200, and nothing under `src/` lands
  between MG0c's rehearsal and its registration.
- **FR-4 → FR-5:** both wait for FR-1's milestone 1, the unrun probe P1 and FR-4's own note.
- Also to place: D147's trigger family, projective mode (@1–@3 only) and the tier re-measurement.

## 7. Open questions (*TODO*: each with a recommendation)

1. A second inner ID beside @3 (D143 names @3): the user's.
2. What status @3's identity under @4 confers: the lead's.
3. Finding 3's run-time half: needed, or host-only?
4. The face-free-node term: specified after P1, as ruled.
5. The stage hook: a closed door in version 1?
