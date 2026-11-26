# The inner model made modular, in place (design)

> **Legacy cleanup (25 November 2026, D386).** Paths under `src/cells/legacy/` and the older model
> IDs named below left the engine. The tag `pre-cleanup-2026-11-25` keeps them.

**Status: landed on main on 16 November 2026** (merge ab267c39 of candidate 3c10b833, tag
`d172-landed-2026-11-16`), after the integrated gate; the records are in PROGRESS. **It was built
(D176, from 15 November) on `integration-d172` from tag `d172-base-2026-11-15` (44227075).
Proposed 14–15 November; revised for D172, D174 and D176.**
- **D176, in force:** F2 fuel; FR-4's first case on maintained fuel; the summation order chosen by
  a measured comparison (§10.6); every affected registered protocol re-run on the integrated
  candidate, E07 included (D181 later held E07-v1's re-run, its worlds covered by the results
  gate); the name kept; and eight design corrections, entered where they apply
  (§3, §8, §10, §15). The dependency table and the critical path, refreshed against main f791294,
  are §15.6. The interface the streams build against is §7.4.
- **D172, the user:** "lets just have one model for now, we don't need backwards compatbility at
  this early stage", then "but lets keep the core design we do modular".
- **D174:** an external architecture review, adopted by the lead after review with the advisor. Its
  requirements are in [ARCHITECTURE.md](ARCHITECTURE.md), "The modular core", each marked holds
  today, target or open. This note is the design that meets that section. §0 maps one onto the
  other.
- **A second review** of that section was adopted the same day (D174 amended). It made five
  clarifications:
  - per-law dispatch is build-time selection;
  - "target" covers D172's round or a later milestone, so this note gives three lists (§15);
  - fields declare evolution roles, apart from conservation;
  - the passive law's test has a closed boundary;
  - "holds today" means code read or a landed test.
- **The Syn3A audit** ([SYN3A_MINIMAL_CELL_TRACK.md](SYN3A_MINIMAL_CELL_TRACK.md) §5.2–§5.3) is
  folded into the passive law (§11).
- The commits on this branch keep the earlier drafts: route (c), with a second inner ID beside a
  frozen @3; then a grouped-or-per-law choice that D174 has since settled.
- No engine code was added or changed. Read-only probes ran (§17).
- "Today" and "holds today" claims here cite the code read at f2ada38d (file and function) or a
  probe's record.

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
   - After R, the laws a world declares are chosen when its program is built. A switch at run time
     over the whole catalogue would still compile the absent ones.
   - A probe measured whether separating them moves any result: **it does not.** In seven worlds,
     every value at every step was bit-for-bit the same, with smaller programs (§4).
   - **Summing species in one fixed order (A7) does move results, at rounding** (P7).
     - In most worlds only the energy and work running totals move, by 1–4 units in the last
       place; the physical state stays bit-for-bit the same.
     - Through an action potential the channel gates move too, by up to 36 units in the last
       place.
     - **So R re-runs every registered protocol in full,** on the integrated candidate, E07 included
       (D176, item 4). Door S's merge (A6) is still unprobed. *At the landing:* D181 held E07-v1's
       re-run, and its worlds were covered by the results gate instead.
4. **R is accepted by results, not by identical programs** (§3).
   - A named list of required scientific results must actually execute and match.
   - Every existing world gives the same CPU results.
   - A deliberately planted change must be caught.
5. **The GPU** (§5).
   - The registered L4 tolerance sets were measured on today's programs: W1's, W2's and G2-Q1's,
     and (refreshed at f791294) the ten BETSE parity variants on @3. R changes those programs, so
     all thirteen are re-measured in an L4 gap.
   - Two inventories, which D174 asks for before the GPU acceptance can be written: which checks run
     on the host for every step today, and which parameters are frozen into compiled programs.
6. **Combining mechanisms on parts of one array** (door S, §8). Two mechanisms that touch different
   cells or nodes of the same field are merged slot by slot, not by overwriting the whole field.
   The test case is a bath dose → uptake → a compartment → a reaction inside it.
7. **Ownership is separated from solver cost, and compartments get a host-side identity map**
   (§9).
8. **Fuel** (§10). The requirement is fixed: reactions make and spend fuel, pumps draw from the
   same amounts, and each standard potential has one authority. **Decided (D176): F2,** fuel
   molecules (ATP, ADP, Pi) as ordinary rows of the shared inventory, with each standard potential
   declared once, where species are declared. Maintained fuel is held inventory rows, not pump
   parameters (ARCHITECTURE.md; §10.2 says what that means for today's pumps). FR-4's first case
   runs on maintained fuel; the finite-fuel case (a regeneration reaction and a pump sharing finite
   ATP, ADP and Pi) stays separate, with its own acceptance world (D176 item 2, §7.4 (g) 2), and
   finite rows are the transporter kind's default fuel.
9. **The name** (§6). **Decided (D176): kept,** `resolved_pump_tissue@3`, with the snapshot, tag
   and results-gate provenance.
10. **When** (§15.5, refreshed). MG0c and Track R are judged, and main is tagged
    `d172-base-2026-11-15`. R was built on `integration-d172` and landed once, on 16 November,
    after the integrated gate (§3). Track E's M2 is judged wholly before or wholly after the
    landing: after, since it was not judged before it.
11. **What R must contain, and what waits** (§15). Three lists:
    - **(a) What R needs to land:** the declarations with build-time selection, the operators that
      depend on today's tables, the results gate, the GPU audit's tests, one added law (the
      passive permeation law) to show that adding a law changes nothing else, door S's merge with
      its integration case (bath → uptake → owned compartment → reaction, D176), and species
      identity consolidated with every sum over species in one explicit order. That last item
      makes later raises of the species cap a guard and a measurement only (D165, amended).
    - **(b) Interfaces R only reserves:** evolution roles and step time, the compartment map,
      the shared potential declarations, the reads, transporters, fuel and implicit routes, and
      the four optional fields of a law that stands in for something (D175).
    - **(c) Qualifications that come in their consumers' own approved milestones:** Track E's
      laws, FR-1's qualification, FR-4's pump, the fuel case, Syn3A's vesicles, FR-8.

    Every item kept out of (a) is time not added before FR-4 and FR-5, which are blocking, and
    Track E's M3.
12. **Effort** (§15): list (a) is **about 17–24.5 agent-days**, landing together under one tag and
    one gate, plus CPU hours for the re-runs and an L4 gap. Split by owner, with the summation
    study D176 adds, the elapsed critical path is **about 11–15.5 days** from the round's start,
    or about 14.5–20.5 with FR-4's insertion points (C6) inside R (§15.6). Re-planned after the
    lead's rulings (15 November): about 13–17 days with FR-4's three first insertion points inside
    R, and 14–18 with the implicit slot too.

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
| GPU-native execution: undeclared mechanisms absent | **Covered.** Per-law dispatch as build-time selection: one cached implementation per declared structure, generalising `vector_windows.compile_window`'s key. This contradicted the earlier grouped option, now dropped | §2, §4 |
| GPU-native execution: executable reuse (target, audit pending) | **New:** the audit's half on constants frozen into programs, and a reuse test in R's gate | §5.2, P5, §15 |
| GPU-native execution: device-resident checks (target, audit pending) | **New:** the audit's half on host checks per row, by path and by operator | §5.1 |
| GPU-native execution: no per-cell Python dispatch or CPU solver; compile, memory and end-to-end measured | **Covered** by static dispatch; **new:** the measurements list in the gate | §2, §3 |
| Scoped composition (door S, with the runtime merge) | **New:** the design; its authority is now SCOPED_COMPOSITION_DESIGN.md (D176's corrections entered) | §8 |
| Ownership, geometry and solver invalidation; compartment identity as a host map | **New:** the design | §9 |
| Material identity and fuel | **Covered,** after a contradiction is corrected: the route (c) draft recommended pool state, which contradicts the requirement unless the pool is those amounts. **New:** inventory rows with one authority for each standard potential (F2, decided by D176; maintained fuel as held rows), the first case, the two boundaries; species identity consolidated, with one explicit order for every sum over species (D165, amended), chosen by a measured comparison (D176) | §10 |
| Transport laws by physical contract | **New:** the passive law joins R as list (a)'s added law. Its kernel is the constant-field route at valence 0, per the Syn3A audit. It is tested on the closed, fixed-volume two-compartment boundary, with water qualified separately | §11 |
| State roles and time | **New:** evolution roles apart from conservation relationships; counters that declare steps or events; the step context. Interfaces only, in list (b) | §12 |
| Reuse cases and the results gate | **Covered** (the results gate); **new:** a required-results list that must execute, the planted tests, and the four reuse cases placed | §3, §15 |
| Order | **Covered** | §15 |
| Targets in D172's round or later (the second review) | **New:** the three lists, and what FR-4, FR-5 and Track E's M3 wait on | §15 |

## 1. The code facts the design turns on (read at f2ada38d)

### 1.1 What is fixed in today's model

| Item | Where | What it fixes |
| --- | --- | --- |
| The law table | `surface_pump_v3_spec.LAW_CODES`: five laws, codes 0–4 | `domain_valid`'s `laws < len(LAW_CODES)`, a literal 5 in every program, the channel-free one included (P1) |
| Gate rows | `GATED_CODES = 3`; `channel_gate` is [2, channel_slot] | Two relaxation gates or none. A j gate needs a third row |
| The dispatch | `channel_kinetics` → `sodium_channels.kinetics` → `potassium_channels.kinetics` | The Kv1.5, Kir2.1 and NaV1.2 kinetics are traced for every population and selected by code, even with no population (P1). The heredity cells of W1, W2, G2-Q1 and E07, and the 825-node world, declare only Kir2.1 and NaV1.2 |
| Channel ions | `SPECIES_VALENCE = {"Na": 1, "K": 1}` | No Ca²⁺ channel. **Lifted 25 November 2026:** the table is gone, each law is the authority for its own ions, and `cav1p2_m2h@1` carries Ca²⁺ (CALCIUM_STORE_AND_CHANNELS_DESIGN §5.2) |
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
| `cell_owned_compartments@1` (FR-1; on main since 15 November, development code) | Declaration only: no @3 import, no part, no program. Its refusal 4 names @3's route kinds, so it must fail closed over every declared route kind (§14). It carries the compartment identity map (`compartments.identity_map`) that door S's integration case reuses |
| `site_occupancy@1` (FR-3; on main since 15 November, development code) | No @3 import; no field input. Its own species-identity check (the coupling operator's pattern until R). Its integrator duplicates D152's numerical block, a consolidation item for R (SITE_OCCUPANCY_DESIGN.md §12) |

## 2. The route under D172: what R does

### 2.1 Today's structures become declarations

| Declaration kind | Today's members, declared | Later members (each its own landing) |
| --- | --- | --- |
| Channel law, **one module per law** (D174) | Kv1.5, Kir2.1, NaV1.2, the K and Na leaks | The moved catalogue laws, `fast_sodium_m3hj@1`, the transient outward current, `l_type_calcium_cdi@1` (§13.1) |
| Junction conductance law, per junction | `junction_voltage_relaxation@1` (the default) | `junction_ungated@1` (§13.2) |
| Pump family | Na/K and the calcium pump | Transporters, among them FR-4's pump (§13.3) |
| Fuel kind | `maintained_chemical_reservoirs@1` | Finite fuel on inventory rows (§10) |
| Solver | RK4 (reference runs), `imex_euler_face_electromigration@1`, `imex_ars222_face_electromigration@1` | Implicit-route solvers (§13.4) |

**R also lands, or reserves, D174's targets.** §15 sorts them into three lists:
- **in R** (list (a)): the results gate (§3), door S's runtime merge (§8), the passive permeation
  law (§11);
- **reserved** (list (b)): the compartment map (§9.2), the shared identity and potential
  declarations (§10.2), evolution roles and step time (§12), and ownership separated from solver
  invalidation (§9.1), unless the lead moves it into (a).

### 2.2 How structure reaches the compiled step

- **Today** the only static switches are a layout leaf's shape and one keyword. A leaf, even an
  empty one, changes every program (P1).
- **A plain @3 definition bypasses the composite's cached key:** `get_model` returns the bare
  module.
- **After R,** `get_model` returns, for every inner-model definition, plain or composite, one
  implementation object cached per declared structure, as the composite's is per operator list.
  - Its step closes over that structure as Python values. An undeclared piece is then absent from
    the program, with no leaf.
  - **This is build-time selection.** A switch at run time over the whole catalogue (a `cond`, or a
    select by code) would still trace every law, which P1 found today's dispatch does.
- **It generalises the vector-window pattern.** `vector_windows.compile_window` keys an executable
  on the model's `checked_step` and `device_checks` functions, the window's rows, the array tree,
  and every leaf's shape, dtype and sharding.
  - With one implementation per structure, the functions in that key are the structure.
  - Parameter-only changes then keep the key and reuse the executable.
- **The rule that keeps this safe:** an implementation closes over structure only, never over a
  value. A value captured in a cached function would be frozen into every later world that shares
  the key. P5 tests that no value is captured today (§5.2).

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
bitwise. An exactly-zero contribution changes no sum's value. **The known exception is signed
zero:** −0.0 + 0.0 is +0.0, and the gate compares bit patterns (FIELD_SOLVER_INTERFACE_DESIGN.md
§6.5 flags the same). A difference in signed zeros only is reported as such, not as a moved
result.

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
| **G1, existing worlds on CPU** | Every world of the crossrev sets (base, qualification, injection, volume, division, species, reactions, and each operator's own set) and @3's test worlds. Each runs from the tag before R and from the new snapshot. Compared: every state field, observation column and `max_` diagnostic of every accepted row, and every refusal (its step and its message) | Bitwise, NaN-aware, bit patterns compared, except where R changes rounding. **A7 does (P7):** physical fields and accumulators are compared within a tolerance stated before the run from P7's magnitudes, field by field, and G2 runs in full. **Padding (check K1, the activity check, §7.4 (b)):** compiled per-law dispatch would change `channel_targets` and `channel_tau_s` at inactive population slots of worlds that do not declare Kv1.5, closed slots of the division worlds included; the host observer therefore keeps today's padding values as a declared, temporary fill (the lead's ruling, 15 November), so every observation column stays bitwise and the whole-run padding mask is withdrawn. A planted change to an active slot's kinetics must fail, as the gate's self-test |
| **G2, registered protocols re-run** | Every registered protocol whose engine models include the inner model or the composite. **Refreshed at f791294 by model-ID text match,** since protocol files name their models under different keys (`engine_models`, `engine_model`, `cells_run.model`) or only in their drivers. As before: W1, W2, G2-Q1, S2, S3, Rm1, S5a, D150's judged run, E07-v1. Judged on 15 November: MG0c (`mg0c-turing-v1`) and Track R (`regulated_availability_protocol.json`). **Newly listed, all on @3:** MG0b (`mg0b_domain_wall_v1`); the stationary analysis E (`stationary_analysis_e_v1`, items E2–E4); the BETSE parity rungs P3 (four cases), P4 (two) and P4b (four), registered by commit (PROGRESS), although their files' `status` fields still read PROPOSED, each with a registered L4 variant (§5.3). **The lead's call:** the projective qualification C (`projective_c_qualification_v1`, on @3), whose qual-01 failed. Track E's M2 (`excitable_qualification_v1.json`, PROPOSED) joins if judged before R lands. A7's import-closure manifest may add older families' protocols (§10.6) | Every verdict unchanged; numbers bitwise, or within the protocol's own tolerances |
| **G3, planted changes, aligned with G1 (D176)** | **Exact contract tests,** run in the bitwise commits (declarations, dispatch, operators, door S, the passive law): (a) one law coefficient moved by one ulp in a test double (P2's planted arm shows the effect's size); (b) one world parameter moved by one ulp; (c) one required-results entry deleted from a run. **Scientific negative controls,** in the final gate at A7's tolerance, where a one-ulp plant passes by design: perturbations whose effects on judged observables exceed the declared budget, each effect measured against the budget before the run; (c) again | The gate must fail every plant and every control. If it passes any of them, it is void |
| **G4, measurements** | Compile time, host and device memory, and end-to-end time, on representative compositions: the heredity cell, the 127-cell sheet, a water composition, D150's arm, MG0c's chain, the 825-node world | Reported against the tag; judged only where a protocol registers a bound |
| **The reuse cases** (ARCHITECTURE.md's table) | Inventory → regulation → electrical response (Track R's A4 and A5, judged 15 November). Bath → uptake → owned compartment → reaction lands in R as door S's integration world (§8; D176). The other two join as they land: reaction → finite fuel → pump (§10); neutral solute and water in a vesicle (§11) | As registered; the integration world by SCOPED_COMPOSITION_DESIGN.md §7 |

**Cost-savers, the lead's call:**
- If G1 were bitwise, E07-v1 could be re-run as a sample (its E1 segments and one arm per group,
  about 5 core-hours against about 50). **With A7 it is not,** so E07-v1 runs in full, about 50
  core-hours. **Decided (D176, item 4):** every affected registered protocol is re-run in full on
  the integrated candidate, E07 included; targeted development checks come first, and the expensive
  final gate is not run repeatedly.
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

**The result (15 November, 00:52–01:25 UTC; records in `probe2/out/`).**
- **Per-law dispatch changes no result.** Every forward state field of every recorded step is
  bitwise identical to today's code in all seven worlds (C1). That includes the water composition
  and the 127-cell sheet.
  - The Jacobians of the right-hand side and of one step are bitwise identical for the heredity cell
    and the water composition (C2).
  - The planted one-ulp change differs from today's in every world (C0), so the comparison is not
    blind.
  - No world differs by signed zeros only.
- **The cost is a smaller program, at no measurable time.**

| World (steps) | Checked-step equations, today → per-law | First run, compile and execute (s), today / per-law | Second run, execute only (s), today / per-law |
| --- | --- | --- | --- |
| Heredity cell (201) | 7,768 → 7,578 | 27.5 / 41.9 | 0.72 / 1.22 |
| Five-law padded world (14) | 7,812 → 7,802 | 86.2 / 77.3 | 1.38 / 0.74 |
| Seven-cell gated sheet (101) | 7,776 → 7,586 | 70.4 / 49.3 | 0.85 / 0.62 |
| Generic cell, an action potential at 5 µs (801) | 7,768 → 7,758 | 57.6 / 53.8 | 3.31 / 4.18 |
| RK4 single patch (401) | 1,844 → 1,844 | 111.7 / 102.7 | 2.04 / 5.74 |
| Water composition (101) | 9,011 → 8,821 | 51.7 / 48.5 | 0.72 / 0.65 |
| 127-cell sheet (51) | 7,776 → 7,586 | 66.6 / 65.6 | 2.04 / 3.09 |

  - Worlds without Kv1.5 lose 190 equations; worlds with all three gated laws lose the selection
    chain's 10.
  - **The timings are within the loaded machine's noise:** they go both ways, by up to 2.8×. A cost
    claim needs G4's measurements on a quiet machine.
  - **Every second run compiled nothing** (XLA's compile log). Within one process, the window path
    reuses its executable.
- **The consequence:**
  - The dispatch change is bitwise, so it alone would let G1 run bitwise.
  - **A7 is not bitwise** (P7, §10.6), so §3's rounding contingency applies to R: G1 runs at a
    tolerance stated before the run, and G2 re-runs every registered protocol in full.
  - A6, the merge, is still unprobed. If it moves results, the same rule covers it.
  - Judges that differentiate the step still re-run in full (§3), since P2's Jacobians cover two
    worlds, not W1's and W2's.
  - P2 tests the dispatch change alone. The rest of R (A2–A7) is tested by the results gate.

## 5. The GPU

### 5.1 Inventory 1: what runs on the host for every accepted row today

| Path | On the device, every row | On the host, every accepted row | On the host, observed rows only |
| --- | --- | --- | --- |
| Scalar and windowed runs (`runner._run_segment`, `windows.iter_windows`) | The step's own refusals: domain, controls, the stage rule, the field solve's residual | **All of `check_values`**: @3's row checks, the operators' terms and own ledgers, the retiring operators' actual-domain check (`Composition.check_values`, `_check_actual_domains`) | Observers (`observe_history`); continuity checks (`windows._observation_tail`) |
| Guarded batch (`execution/batch.py`) | As above, per world under `lax.map` | **All of `check_values`**, per world | Observers |
| Vector windows (`execution/vector_windows.py`) | The step's refusals, and the device row checks (`device_checks`): domain, every ledger (operators' own included, `Composition.DEVICE_CHECKS`), dissipation | **None.** Only per-window summaries leave the device | Observers and continuity checks; the window endpoint |
| Every path, at the definition | — | Parsing, operator refusals, `check_definition`, `StepChecks` (once per clock, by chunk) | — |

**By operator** (their declarations at f2ada38d). Every operator's in-step refusals run inside the
program on every path: its `domain_valid`, `control_valid` and `rate_checks`.

| Operator | Own ledgers (host per row on the scalar, window and batch paths; device rows on vector windows) | Other host work |
| --- | --- | --- |
| `scheduled_bath_composition@1` | `bath_dose`, `bath_dose_free_energy`, `bath_neutrality` | — |
| `membrane_entity_state@1` | `membrane_area_entity`, `membrane_capacitance_entity`, `population_abundance_entity` | Its observation columns |
| `ideal_osmosis_linear_compliance_water@1` | Water's ledgers | Its observation columns, which replace the energy columns |
| `isopotential_partition@1` | `partition_material`, `partition_area`, `partition_capacitance`, `partition_units` | **It retires slots:** on the host paths, `_check_actual_domains` reads every actual row at its view. On vector windows, the device checks evaluate the same domain |
| `restricted_cleft_lumen@1` and `@2` | `lumen_fill` | Their observation columns |
| Replacement@1 and @2, injection, insertion@1 and @2, D150's exchange and turnover, D152's reactions, the bridge, the coupling operator, the symport | None of their own. Their terms enter @3's ledgers (`ledger_terms`) | Observation columns (replacement, the symport, reactions, the coupling operator, whose factors `held_schedules` holds for observation) |

So no operator has a per-row check that exists only on the host (**S**). The composite's device
checks carry every ledger (`DEVICE_CHECKS` = the domain, @3's ledgers and each operator's own, and
dissipation).

- **What this means for D174's "state, step checks and refusals stay inside device windows":** it
  holds today on the vector-window path only (**S**, from the code). It needs `device_checks`,
  which the composite has.
- **Host-only work on that path:** observers, continuity checks on observed rows, and the
  factored availabilities that `held_schedules` holds for observation.
- **Every new piece must give its checks a device form,** as the composite's operators do today.
  A host-only per-row check would take that piece off the vector-window path.

### 5.2 Inventory 2: parameters frozen into programs

**P5's result (15 November, 00:47–00:52 UTC; 279 s).**
- **No world needed a second executable.** In all nine worlds the value twin traced the same three
  programs as the original: the same jaxpr text, the same closed-over constants and the same batch
  signature. The worlds:
  - plain @3: the heredity cell and the gated sheet;
  - water, the symport, replacement, and replacement with routes;
  - D150's turnover arm;
  - an MG0c reaction chain;
  - injection.

  The twins scaled 8 to 92 rate-like parameters each.
- **The value search's hits are coincidences, checked against the code:**
  - 140.0 is the junction-gate law's coefficient;
  - 12.0 and 0.12 appear as kernel literals, while `km_na_mM` and the symport's steepness are
    layout arrays (`pump_km_na`, `symport_steepness`);
  - 1e-10 is the definition's `execution.material_balance_atol_fmol`. Crossrev's trace closes
    over it in the device-check program, but in production the vector-window path passes the
    device-check constants per world as arguments (`vector_windows.resident_inputs`). So it is a
    tracing artefact, not a value frozen into a production executable;
  - 0.001 and 1e-15 are law and floor literals;
  - 5.684e-14 is 2⁻⁴⁴.
- **So no definition-derived value is frozen into the step's programs today.** Same-structure
  parameter sweeps reuse one executable, within P5's scope.
- **P5's scope:** the step's three programs, and rate-like parameters of the model block. Schedules,
  event times, dt and window length are outside it (dt is a traced input, per crossrev).
- **R must keep this property,** by §2.2's rule: implementations close over structure only. List
  (a)'s A4 makes it a test.

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
- **Refreshed at f791294: ten more registered L4 variants run @3,** the BETSE parity rungs P3 (four
  cases), P4 (two) and P4b (four) (`validation/betse/protocols/physical_p3*_l4.json`,
  `physical_p4*_l4.json`, registered 11 November). Their tolerances also add measured
  Cells-vs-Cells backend terms, and per-law dispatch changes their programs too (each declares a
  subset of the laws; P4's K-leak case traces no gated kernel at all). So the same L4 gap
  re-measures thirteen variants, then runs their judged L4 items. The two P2 variants run @2 and
  are outside R, unless A7's manifest brings them in (§10.6).
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

**Four optional fields, only on laws that stand in for something** (D175; ARCHITECTURE.md,
"Levels of detail"). They are reserved in list (b) as B8; nothing in R uses them, and their first
consumer comes after the fuel case.
- **What it represents:** a declared key that admission compares, so one pathway has one
  representation per scope, and the reference it was reduced from.
- **What it preserves:** the state and history it retains.
- **What can be asked of it:** the interventions, controls and observations it supports; others
  are refused.
- **Where it is qualified:** its validity envelope and error budget. Enforceable bounds, checked
  at run time as the channel laws' voltage domains are today (`surface_pump_v3.channel_domain_valid`),
  are kept apart from assumptions that need evidence.

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

### 7.4 The interface for D176's round (published 15 November 2026)

The core owner's interface, for the operators stream (OPS), the integration owner (INT) and the
FR-4/FR-5 physics owner (FR45) to build against (owners as in §15.6). It is design (**S**), checked
against the code at the tag (44227075) and against check K1 (§17). Changes go through the lead and
are recorded here.

#### (a) Structure and values

- **Structure** is a frozen, hashable, value-free record of what a definition declares,
  `InnerStructure`, computed on the host from the parsed model block:
  - `declared_channel_laws`: the channel law IDs its populations name, in registry-code order (not
    the layout's per-slot `channel_laws`);
  - `junction_laws`: `junction_voltage_relaxation@1` when it has junctions, else none;
  - `pump_laws`: `nak_atp_mass_action_positive@1` when a patch declares a Na/K pump,
    `ca_atp_mass_action_positive@1` when a patch declares a calcium pump, each with its fuel kind;
  - `junction_heat_booking`;
  - `heat_bookings` (seam D, CORE_SEAMS §6.1–6.2): ((mover class, booking ID), ...), the
    definition's `heat_bookings` key for channels, membranes, pumps, calcium pumps and each declared
    kind by its ID, never junctions (they keep `junction_heat_booking`) and never the tableau, so ()
    for every definition of today's. The step books each class picked as `trapezoid_nonnegative@1`
    once, in the core (`surface_pump_v3.trapezoid_fields`): its heat rates at the end state and the
    last-stage potentials, through `explicit_rates` with the stage read and the door, averaged with
    stage 0's. The water and replacement families run @3 through compositions whose inner carries
    the structure, so they book what is picked too;
  - `free_amount_reads` (P1, CORE_SEAMS §17; §19 as amended): the declared kinds, sorted, whose
    stage rows all name, as their third item, a registered law that declares `free_amounts`
    (`rapid_binding@1`). The step's positivity predictor then reads the quantity it
    differentiates: the stage read at the predicted stored totals, whose failure refuses the step.
    Everywhere else, version 1's reads included, it keeps today's form, the start read's amount
    plus the stored derivative, so () for every definition of today's. A read whose rows mix the
    two, and a free-amount read beside a read of today's form, are refused at binding;
  - from later landings, each present only when declared: the passive law (A5), transporters (B5),
    stage reads (B4), implicit route kinds, and B7's flag for a free face-free node with an ion
    route.
  - **added 25 November 2026** (CALCIUM_STORE_AND_CHANNELS_DESIGN §8.3 and §6.5): `floating_nodes`,
    whether an outside node floats (B7's flag, for the corrected charge rule), and `loops`, the
    loops that routed slots close on their own gates, by position. False and () for every other
    definition, so no structure or program of theirs moves.
- **Values** are layout arrays, bound per world and passed as arguments: permeabilities,
  abundances, capacities, initial gates, rates and schedules, **and each population's law code**
  (`channel_laws`, int [channel_slot]), that is, which declared law a slot runs. P2's bitwise
  result rests on this split: the declared set is structure, the per-slot assignment is data.
- **Not structure in R:** the time integrator stays selected by the tableau's static shape, and the
  field solver by the layout's type, as today. `get_model` receives the model block, not the
  execution block, so moving them needs a later change of its signature.
- **The rule (P5):** an implementation closes over structure only, never over a value, because a
  captured value would be frozen into every later world with the same key.

#### (b) The law declarations

A new core module, `models/inner_laws.py`, holds one frozen declaration per law ID, with a fixed
registry code.
- **The kernels stay where they are,** unchanged: `voltage_gates.kinetics`,
  `potassium_channels.kir2p1_kinetics`, `sodium_channels.nav1p2_kinetics`, `junction_gate`,
  `kinetic_pump` and `calcium_atpase`. The shared dispatchers in `processes/`
  (`sodium_channels.kinetics` and `opening`, and their potassium counterparts) stay too, since
  older families import them. @3 stops calling them.
- **A channel law declares:**

| Field | Today's five laws |
| --- | --- |
| `law_id`, `code` | Kv1.5 0, Kir2.1 1, NaV1.2 2, K leak 3, Na leak 4: today's codes, fixed. A new law takes the next free code; no code is reused |
| `gates` | ("m", "h") for the three gated laws; none for the leaks |
| `kinetics(voltage, *, xp)` → (target, tau), each [..., gates, n] | The existing kernels |
| `opening(gates, *, xp)` → [..., n] | Today's operation order, which P2's bitwise result needs: Kv1.5 m·h, Kir2.1 (m·h)·h, NaV1.2 m³·h. None for the leaks (open fraction 1) |
| `permeant` | (species, valence, relative permeability): today's `LAW_PERMEABILITIES` with `SPECIES_VALENCE`. Since 25 November 2026 the parser reads each ion's valence from the law, and `SPECIES_VALENCE` is gone |
| `voltage_domain` | (−0.120, 0.060) V for all five |
| `rk4_step_s` | 2.5e-6 for NaV1.2, 25e-6 for Kv1.5 and Kir2.1, none for the leaks (today's `RK4_*_STEP`) |
| `stage_term` | `constant_field_slope`, today's `membrane_rate` term at the actual opening |
| `material_term` | Added 25 November 2026. None for these five. A law that carries an ion other than Na, K and Cl names the kernel of its material slope here (`material_slope_per_s`, the one @3 runs): the stage holds dt to its ions' own relaxation, and the parser refuses such a law that names none (CALCIUM_STORE_AND_CHANNELS_DESIGN §5.2 and §5.3) |
| `reads` | None for these five; (g) 1 below. `loop_term`, reserved beside it, was removed on 25 November 2026: no law declared it (CALCIUM_STORE_AND_CHANNELS_DESIGN §6.5) |
| `provenance` | `parity` |
| B8's four fields | Reserved, empty (D175) |

- **A junction law** declares its ID, `gated` (true for `junction_voltage_relaxation@1`), its
  kinetics, right-hand side and domain (`junction_gate`'s, ±0.120 V), and its definition-time bound
  (`junction_gate_rate_bound`).
- **A pump law** declares its ID, kernel and domain, the rows it moves per cycle by role, its fuel
  kind and its definition-time bound. Both of today's pumps run on
  `maintained_chemical_reservoirs@1` in today's parameter form (§10.2).
- **The padding rule (P2's measured form in compiled programs, check K1; today's values on the
  host, revised below).** An inactive population slot, padded or closed, carries code 0, as today
  (`domain_valid`, the adapter's `close`). The compiled dispatch selects a declared law's values
  wherever a slot carries its code, active or not, so:
  - in a world that declares Kv1.5 (code 0), an inactive slot reads Kv1.5's kinetics at 0 V, as
    today, bitwise (K1's five-law world);
  - in a world that does not, it reads target 0, time constant 1 and opening 1. Today it reads
    Kv1.5's values, so `channel_targets` and `channel_tau_s` would change at those slots, and
    nowhere else (K1).
  - That was to be a comparator exception (§3), before the activity check below; the host rule
    removes the need for it.
  - Masking by activity as well would make padding independent of the declared laws, but it would
    change those columns in every world with an inactive slot, and K1 did not measure it.
  - **The lead's ruling (15 November):** the comparator's padding mask covers only those two
    columns, at slots inactive for the whole run, and a planted difference at an active slot must
    fail it. The dispatch commit merges only then.
  - **Which events change a population slot's activity during a run** (read in the code at the
    tag): the closers do (`CLOSES`: the partition and insertion@2 only). The partition's births
    and retirements close cells, and insertion@2's onsets close patches and nodes; the adapter's
    `close` carries each down to the populations. Insertion@1 provides `membrane_active` but no
    closure, so populations keep their declared activity. Replacement, its law-steady arrival
    included, provides route values and junction gates only, never a mask.
  - **Checked on the saved worlds (activity check, 15 November; core log):** the partition's worlds
    build on the heredity cell and keep its Kir2.1 and NaV1.2 populations. In eight of the nine
    crossrev division worlds, and in S5a's furrow world, every population sits on a cell the
    partition opens or closes, and none declares Kv1.5. The composite observes the inner model at
    each row's view, with the closures, so those slots carry code 0 on their closed rows. Per-law
    dispatch would change both columns there, at slots that are active on other rows, which the
    whole-run mask rightly does not cover. S3's cleft egg has no population.
  - **Accepted (the lead's ruling, 15 November): the host keeps today's padding values, as a
    declared fill, not physics.** The observer evaluates readouts in NumPy, and nothing compiled
    reads a padded slot's kinetics (the gate update, the gate rate, the flux and the domain all mask
    them). So the host readouts give a code-0 slot the code-0 law's kinetics, as today, when the
    code-0 law is not declared (every code-0 slot is then padding), while compiled programs keep
    P2's form and carry no undeclared kernel. Both columns stay bitwise in every world.
    - **The dispatch commit's condition:** every observation column bitwise on the division worlds
      with closed slots, the eight crossrev division sets and S5a's furrow world.
    - **The whole-run padding mask is withdrawn:** with bitwise observations there is nothing to
      mask. The planted active-slot failure stays, as the gate's self-test: a planted change to an
      active slot's kinetics must fail.
    - **The law-steady replacement world stays a merge condition** (refused at the tag; with the
      acceptance owner).
    - **The fill is temporary.** After the round, an explicit absent marker for padded entries can
      be proposed as its own gated change, with the run view (D154).

#### (c) Build-time selection: one implementation per structure

- **The calls:**
  - `surface_pump_v3.structure(model)` → `InnerStructure`;
  - `surface_pump_v3.implementation(structure)`: one object per structure, cached, so equal
    structures share one object, its functions and its executables;
  - `surface_pump_v3.model_for(model)` = `implementation(structure(model))`.
- **Who calls them:**
  - `registry.get_model` returns `model_for(model)` for a plain @3 definition: one line in the @3
    branch of `registry/models.py`, a file in no stream's list (the lead to confirm).
  - INT keys the composite on the inner structure as well as the operator list, and its adapter
    forwards the inner protocol from that object (§15.6, I2).
- **The selection inside,** one kernel per declared law (P2's form):
  - channel kinetics start from target 0 and time constant 1. For each declared gated law, in code
    order, its kernel's values are selected where the slot carries its code (the padding rule, (b));
  - openings start from 1, and each declared gated law's opening is selected where its code
    matches;
  - **the domain:** an active slot's code must be a declared code, so no literal comes from the
    registry. Padding carries code 0. Each law's voltage domain applies on its own populations;
  - **the pumps and the junction law:** each kernel is traced only when declared. An undeclared
    pump's rates are exact zeros of today's shapes. They can differ from today's masked values only
    in the sign of a zero, which is reported apart (§2.3).
- **The surface.** It has every public name of today's module, with the same signatures:
  - the adapter's re-export block, which is the de facto inner protocol;
  - what the operators import (`STATE_TYPE`, `LAYOUT_TYPE`, `FLOOR_LAYOUT_TYPE`, `field_values`,
    `MembraneProcess`, `EXPLICIT_STEP_BOUND`, `physical_amounts`).

  Structure-free names (types, constants, `parameters`, `physical_amounts`, `projection`,
  `rebind`) are the module's own objects and stay importable from it. Step, readout, domain, check
  and observation functions are bound to the structure, and consumers take them from the object.
  **New names:** `structure`; `declared_channel_laws` (the declared IDs, in code order);
  `law_columns` ({law ID: column}); `gate_rows`; `channel_kinetics(voltage, codes, *, xp)` and
  `channel_opening(gate, codes, *, xp)`, today's signatures; `junction_kinetics(voltage, p, *,
  xp)`; `moved_rows(model)`.
- **During the round,** the module's own structure-dependent names stay, bound to the full
  catalogue (every registered law declared). That gives today's values bitwise (K1's five-law
  world), so a caller not yet moved keeps working. They are removed before the landing, once every
  caller takes the object, and a static test then refuses them.
- **The batch signature gains the structure** (§2.3, rule 5): today's topology signature plus
  `structure(model)`. Worlds with different law sets never share a batch program, so a batch of
  today's that mixed law sets would be split. G1 shows whether any does.

#### (d) What "absent" means in R

| Level | Meaning | Delivered in R for | Commit |
| --- | --- | --- | --- |
| Kernel | No kernel of the law in the traced program | Every channel law, both pumps, the junction law | The dispatch commits, (e) 2–3 |
| Schema | No state or layout field | New kinds only: the passive law's fields (A5), transporters' (B5), a stage read's, a third gate row | Each with its kind |

- **Today's kinds keep their schema in R.**
  - `channel_gate` stays [gate_rows, channel_slot], with gate_rows the larger of 2 and the largest
    declared gate count: 2 in every world of R.
  - The pump fields stay [membrane], zero where no pump is declared, and `junction_gate` stays.
  - So every state field, observation column and checkpoint type is today's, and the baseline
    compares field by field.
- **Shrinking today's schema** (no pump fields, or no gate rows, when undeclared) is a later change,
  with a comparator rule agreed before its run.
- **One empty leaf goes, in the dispatch commit:** `junction_heat_trapezoid` becomes structure,
  the booking. No other reader exists under `src/`; validation and tests are checked in that
  commit.

#### (e) The commits, each checked against the baseline saved at the tag

1. **Declarations and the implementation object,** with today's dispatch inside, so values and
   programs are unchanged: checked by crossrev identity as well as against the baseline. This is
   the first API commit, which OPS and INT test against.
2. **Per-law channel dispatch,** the declared-code domain and the trapezoid leaf's removal:
   bitwise in every observation column, the host keeping today's padding values (b), shown on
   the eight crossrev division sets and S5a's furrow world.
3. **Pump and junction-law dispatch:** bitwise, up to signed zeros at exact zeros, reported apart.
4. **The compile key and A4's two tests** (§2.2, §5.2):
   - an undeclared law contributes no kernel and no state: a jaxpr check that a world without
     NaV1.2 holds none of its kernel, and a world without the passive law none of its fields;
   - a parameter-only change reuses the executable (`compile_window` reports 0 s), and gives the
     result a fresh compile gives, bitwise.
   - `compile_window`'s key gains the model's `structure_key`, which the object sets to its
     structure (and the composite to its inner structure and operator list). The step and check
     functions stay in the key.
   - **The packed planner's key (built on `core-d172`):** `vector_windows.world_key` is the part
     of the key one world fixes: the structure key, the step and check functions, and the tree,
     shapes and dtypes of the world's state, parameters, activity mask and check constants,
     without the world axis. `spec_world_key(model, spec, start)` computes it on the host, before
     any compile; `compile_window` builds its own key through it (`window_key`: the world part,
     then the observation rows, the round arrays' shapes, the world count and the placement), so
     the two cannot drift. Value twins get equal keys (`tests/unit/test_window_key.py`).

#### (f) Answers to the operators stream (its PLAN.md §4)

1. **The code-to-column map and the gate count.**
   - Codes stay the registry's (b).
   - Per definition, `declared_channel_laws` lists the declared laws in code order, and
     `law_columns` maps each to its column. A table keyed by declared laws has one column per
     declared law, in that order. A per-slot column array for gathers is the operator's own layout
     data, built at its bind from `law_columns`.
   - The gate count is `gate_rows` (d): 2 in every world of R.
2. **Kinetics in an event map.**
   - The step's own selection is `channel_kinetics(voltage, codes, *, xp)` and
     `channel_opening(gate, codes, *, xp)`. Calling these, rather than a law's kernel directly,
     makes an event's gates the step's bit for bit.
   - Junction gates: `junction_kinetics(voltage, p, *, xp)` returns today's
     `junction_gate.kinetics` for the declared law. Its target at 0 V is law_open, and at the
     post-event voltage law_steady.
   - The post-event field solve is the object's `field_values(state, control, p, *, xp)`.
3. **Ungated junctions carry no gate state in R, because none exist:** every junction runs
   `junction_voltage_relaxation@1` and carries its gate, as today. When `junction_ungated@1`
   lands (follow-on physics, D176):
   - its slots hold `junction_gate` at exactly 1, the factor it multiplies, never advanced;
   - its domain requires exactly 1 on its active slots, and closed contacts keep the adapter's 0;
   - its first version is refused beside replacement@1 and @2, the partition and every closer
     (§13.2), so no operator event meets one until a later version says how.
4. **Water's coupled RK4:** the object's `rhs(state, control, p, active, *, xp)` (readouts'
   derivative, NaN where invalid) and `readouts(state, control, p, *, xp, membrane_process=None)`,
   as today.
5. **The symport's in-step process** keeps today's hook unchanged: the `membrane_process` keyword
   of the object's `imex_step` and `readouts`.
   - The signature: `membrane_process(ci, co, volume, voltage, *, xp)` returns
     `MembraneProcess(flux [species, membrane] outward fmol/s, heat [membrane] pJ/s, valid)`.
   - One process per composition; `imex_step` then returns (state, valid, (transfer, heat)).
   - It is not §13.5's stage hook, which (g) 1 opens for stage reads. `MOVES_IN_STEP` is a contract
     addition, INT's.
6. **Moved rows:** `moved_rows(model)` returns {species: ((mover kind, law ID, entity IDs), ...)}
   for every in-step mover of the inner model:
   - membrane and junction routes with nonzero permeability;
   - each declared channel law's permeant ions on its populations' patches;
   - the Na/K pump's Na and K, and the calcium pump's Ca;
   - the faces, for outside nodes;
   - later, each transporter's moved roles and each passive route.

   Held fuel rows are read, never moved, so they are not movers ((g) 2). Today's pumps hold their
   fuel as parameters, so they move no fuel rows. Under finite fuel (later) the pump's fuel rows
   join.
7. **The registry hook.**
   - @3's parser (`surface_pump_v3_spec.parse`) calls `species_registry.parse_entries(raw_model)`
     once, before it delegates to @2's parser, whose species parse is strict (`{"id",
     "valence"}`). The call pops the registry's keys from each species entry of the deep copy and
     returns the immutable registry.
   - The model gains one field, `species_registry`, default None, omitted from `to_dict` when None,
     so every existing definition keeps its fingerprint. `to_dict` writes the entries back through
     `species_registry.to_entries`.
   - **Refreshed against the operators' registry (e66fea95, 15 November):**
     - `parse_entries(raw_model)` also pops `standard_concentration_mM`, and returns None when
       nothing is declared; the hook calls `species_registry.check_definition(spec)` ahead of @3's
       own checks, so the registry's refusal, which names the background to declare, fires first;
     - two-form rows carry `protonated_standard_mu_RT`; the stage read takes K at binding from
       `dissociation_constant_mM(spec, base, proton)`, the closure's own formula a cross-check
       test;
     - `check_two_form_rows` refuses in-step movers of a two-form row. The inner model's movers come
       from `moved_rows`, which gains each declared transporter's roles and finite fuel rows with
       the transporter kind; the stage read moves nothing;
     - the hook lands on `core-d172` after the registry is on `integration-d172` (merged in, never
       rebased).

#### (g) Answers to FR-4 and FR-5 (COMPARTMENT_PH_TRANSFER_DESIGN.md, branch `fr45-physics`)

1. **A per-stage algebraic read: the stage hook opens (B4), with FR-4's rapid-buffer closure its
   first member.**
   - **The declaration**, a `StageRead`:
     - `read_id`;
     - the rows and nodes it reads, resolved at binding through FR-1's identity map;
     - `evaluate(cell_amounts, outside_amounts, p, *, xp)` → (values, valid): pure, with values a
       {name: [node] array} mapping (free h, pH);
     - its bound parameters, as layout fields present only when it is declared;
     - its declared free-energy term (the closure's ΔG_buf) and that term's rounding magnitude,
       for the energy ledger;
     - its observation columns.
   - **Its place in the step:** the inner model evaluates every declared read once per stage, on
     that stage's own state, before any law. A law that names the read in its `reads` receives the
     values: `kinetics(inputs, parameters, availability, reads, *, xp)`.
   - **Its stage semantics:**
     - stage k's reads are evaluated at Y_k, the state at which stage k's explicit rates are
       evaluated: the step start for the first stage, and each later stage's combined state after
       its implicit solve;
     - so a reading law is explicit at that stage like every other rate, with no iteration, and
       ARS(2,2,2) keeps its order (§7.2);
     - the end-of-step domain evaluates the reads at the end state (FR-4's pH band); observations
       evaluate them at the accepted row;
     - a failed read refuses the step: the closure's |g|/H̄_eq > 1e-13, or an inadmissible state.
   - **The loop term:** a law whose flux moves a row its read depends on declares a loop term for
     the stage rule, dt × rate ≤ 1. The law's owner supplies it: for the proton pump, |∂J/∂H_eq|
     through dh/dH̄_eq.
     **Superseded (25 November 2026; CALCIUM_STORE_AND_CHANNELS_DESIGN §6.5):** nothing evaluated
     the reserved field `loop_term`, so it was removed. A closure's loop is the transporter's
     material term with the closure's derivative (that note's §6.3); a loop that a routed slot
     closes on its own gate is the core's (`surface_pump_v3.loop_material_rates`).
   - **Reads at a split** (FR-5's factors on the routing door) call the same pure `evaluate` on the
     split's state. They are first order in dt there, as FR-4's note says.
   - **Coverage and padding** (the FR-4/FR-5 owner's two notes, 15 November):
     - a read declares every node it covers, buffered or not. At an unbuffered node h = H̄.
       **Superseded (B4, core-d172 8f405f12; checked by the FR-4/FR-5 owner, FR-4's note §4.4 on
       main 85108c77):** the kernel's declared term carries the proton's standard part,
       RT H_eq (μ°(H⁺)/RT − ln c°), which @3's routes and its reservoir work never book (they use
       RT ln c with c in mM). With it, a proton exchanged with a held bath would leave RT ln c° in
       the energy ledger. So the kind books the term in @3's convention: the kernel's
       `declared_term_pJ` less that standard part, which is zero at every unbuffered node, with
       H_eq-derivative RT ln(h/H̄). The kernel stays unedited and convention-neutral; the kind
       owns the engine's 1 mM convention (`kinds/proton_buffer.py`);
     - the slot masks padding, as @3 masks its own padded slots. Before `evaluate`, an inactive
       node's amounts are replaced by a benign value, as `physical_amounts`' padding reads
       concentration 1. After it, that node's validity is ignored, and its values and energy term
       are exact zeros, selected rather than computed into a sum. `evaluate` needs no activity
       mask.
   - **What the closure's declaration carries (the lead's rulings, 15 November), and how the slot
     takes it:**
     - **its per-(node, row) buffer membership:** the read's coverage, bound as a [row, node] mask,
       which the closure's own mask keys on. It is data, so worlds that differ only in membership
       share one program;
     - **its k_on,** a D175 stand-in parameter: bound with the read's parameters and used only by
       the envelope check (at the definition, and at each stage where the envelope is checked
       against that stage's transport rates) and by the reference, never by the equilibrium;
     - **its c0,** from the registry's declared standard concentration, and the pair's two standard
       potentials, from the registry.
   - **Owners:** the slot is CORE's, in `surface_pump_v3`. The closure module
     (`laws/reactions/rapid_proton_buffer.py`) and its declaration are FR45's.
   - **On FR-4's open question 2:** the general slot, now. Three consumers in one stage read the
     same h (the pump, the proton leak and the pH-band check), and one evaluation per stage keeps
     them consistent.
2. **The transporter insertion point and held rows (B5).**
   - **The declaration:** a `transporters` list in the model block, absent unless declared. Each
     population names its ID, patch, law, capacity (fmol cycles/s: N × the per-member value for a
     lumped node), fuel and availability schedule (`transporter_controls`).
   - **A transporter law declares:**
     - `law_id` and `code`;
     - `moves`: the per-cycle stoichiometry by role, inward-positive like today's pumps, each role
       bound at binding to a species row at a node. `proton_atp_mass_action_positive@1` moves n H⁺
       from the patch's inside to its outside, n a declared integer from 1 to 4;
     - `reads`: the stage reads it needs (free h at both nodes);
     - `kinetics(inputs, parameters, availability, reads, *, xp)` → `Rates(cycles,
       cycle_free_energy, chemical_drive)`, in `kinetic_pump`'s form. The insertion point gathers
       `inputs`: each role's concentration at its node (its read's value instead, for a role read
       through a stage read, such as H at a buffered node) and electrochemical potential, the held
       fuel rows' concentrations, the patch voltage and the temperature;
     - `domain_valid(...)`: |ΔG_cyc/RT| ≤ 80, and the fuel node's pH band;
     - `stage_term`, its electrogenic conductance for the stage rule (and `loop_term` until 25
       November 2026, when it was removed: nothing evaluated it);
     - its definition-time bound term, `provenance` and B8's fields.
   - **Fuel, two kinds, finite the default** (revised 15 November for D176 item 2's acceptance
     world). The population names its fuel node (the hydrolysing cell) and its fuel rows (ATP,
     ADP, Pi), and one kind:
     - **`finite_fuel_rows@1` (name S), the default:** the pump moves its fuel rows in the step,
       −1 ATP, +1 ADP and +1 Pi per forward cycle at the fuel node, inward-positive like its other
       roles, booked in @3's material ledgers. Δ_rG'° comes from the registry's potentials at its
       c0. The fuel rows' standard-potential term (Σ μ°' n) is stored free energy in the energy
       ledger, as D152's operator-owned term, and no work is supplied. The fuel rows are in-step
       movers: `moved_rows` lists them, so the operators' `moved_in_step` and
       `check_two_form_rows` see them, and D150's writers and instantaneous reads refuse them;
     - **`maintained_held_rows@1` (name S), the special case:** the rows are read at every stage
       and never moved; the definition refuses a held row that any in-step mover or operator
       writes (OPS's `moved_in_step`, and D152's one-writer rule). The maintenance's work per
       cycle, −Δ_rG'_ATP, is booked as today's metabolic work, and its material record (+1 ATP,
       −1 ADP, −1 Pi per cycle) is an accumulator of the population.
     - Either way Δ_rG'° comes from the registry's potentials (B3, OPS's), never from the pump.
   - **A moved role may be a neutral species** (valence 0), as the finite-fuel world's solute Y:
     its transfer joins the material ledgers and carries no charge.
   - **The finite-fuel acceptance world (D176 item 2):** an ATP-driven pump moving a neutral
     solute Y in FR-4's §6 form, on finite ATP, ADP and Pi rows, with D152's
     `ideal_detailed_balance_mass_action@1` regeneration on a schedule. Its independent reference
     is built to that world. Today's Na/K and calcium pumps keep their parameter form in R.
   - **The insertion point** (CORE, in `readouts` and `explicit_rates`, beside today's pumps):
     - each declared transporter law's kernel runs on its own slots at every stage, with its reads;
     - its transfers enter the membrane totals and the node rates;
     - heat is −cycles × ΔG_cyc, and work −cycles × the chemical drive;
     - its state fields exist only when declared: `transporter_cycles`,
       `transporter_dissipated_energy_pJ` and `transporter_metabolic_work_pJ` [transporter_slot],
       and `transporter_fuel_supplied_fmol` [fuel row, transporter_slot]. Each joins @3's material,
       charge and energy ledgers and the device checks.
   - Door S's stage is `inner`. Its rows are rows, not view fields (SCOPED_COMPOSITION_DESIGN.md
     §6).
3. **B7's slot (as the lead ruled on 15 November; §13.6).**
   - **At the definition, host-only:** a new term beside `explicit_rate_bound`'s, the maximum over
     free face-free finite nodes (active, not a held bath, not the gauge, not a fixed node, named by
     no face) of Σ_m G_m/C_node at the declared state, with G_m the max-side constant-field slope of
     each ion route on the node's patches. The step checks refuse dt × that rate above the bound's
     **ordinary constant**, `EXPLICIT_STEP_BOUND`, as for every other term.
     **Amended 25 November 2026** (§13.6): the fixed-node exclusion is gone, each patch that faces such a
     node has its own row, and the cell's row and the junction term divide by the capacitance of the
     cell's other patches alone.
   - **One commit with finding 3's term,** with one D148 record and @1's and @2's cases, since they
     share `surface_pump`. P3 swept @3's family only; for @1 and @2, FR-1's static sweep of 99
     model blocks found no free face-free node with an ion route in their worlds
     (CLOSED_COMPARTMENT_DESIGN.md §3.4), and the D148 record confirms it on their registered worlds
     before the change.
   - **No run-time half in this commit,** and no 0.05 constant. FR-4 declares its own step, 0.025
     on the max-side G, confirmed by its own dt study. A tighter constant, and a run-time half if one
     is needed, belong with the exact heat booking (§7.5), which removes the energy-ledger limit the
     charged-patch test measured.
   - **FR45 supplies the term's exact form** after its booking-versus-state check; CORE implements
     it.
4. **The implicit patch: yes, behind one slot,** the IMEX step's implicit set. *The first design
   below put the patch into the global operator beside the faces. The decision at the end of this
   item runs it instead as a local stage solve, FR45's Newton form, and leaves the faces as they
   are.*
   - **Today the set is face electromigration alone:**
     - the stage operator (C + a_ii dt L_face) φ = q, with face weights frozen at the predicted
       state;
     - the drift flux at each stage's potentials (`implicit_rates`);
     - the face heat J² RT/W from the applied flux.
   - **CORE generalises it to a declared list of implicit route kinds,** with faces as the first
     member, bitwise. Each kind provides:
     - `weights(predicted state, p)` → W, frozen for the step;
     - `laplacian(W)`, its node-space block, added to the operator before the one factorization;
     - `implicit_flux(W, potential)`, per species and route, at each stage's potentials, into the
       amounts on both sides (for a patch, the cell's and the node's) and its transfer ledger;
     - `explicit_remainder(state, potential)`: the part of the law left among the explicit rates
       (for the constant-field law, J(V) less its linear part in W), which `explicit_rates`
       subtracts on the kind's routes;
     - `heat(...)` ≥ 0, its own booking. For faces it is J² RT/W from the applied flux; a patch
       kind's must close the energy ledger with the stored-energy change, since the charged-patch
       test showed that ledger, not stability, binds the explicit route.
   - **The bounding patch is the second member.**
     - It couples one face-free node to its owner, four entries per compartment (cell i and outside
       node j), so it rides in the same dense factorization; no separate local solve is needed.
     - **Checked in the code at the tag:** `numerics/surface_imex.factor_operator` takes any
       node-space Laplacian over cells and outside nodes and factors C + a dt L on the free nodes;
       `solve_operator` is generic. Only `face_laplacian` and `drift_flux` are face-specific, and
       they stay as they are. A positive patch conductance keeps the matrix positive definite on
       the free nodes. So the slot needs no edit of `surface_imex` (shared with @1 and @2): it lives
       in `surface_pump_v3.imex_step`, which sums the kinds' blocks before calling
       `factor_operator`, and in `implicit_rates`, which gains the cell-side amounts for a patch.
     - The patch's frozen weights need the cell's predicted concentrations as well as the node's;
       `imex_step` already holds the start derivative for both.
     - Each implicit set is a new solver ID (D147), for example
       `imex_ars222_face_patch_electromigration@1` (name **S**).
   - **Owners, reconciled with §13.4** (the first design; see the decision below): CORE builds the
     slot in `surface_pump_v3.imex_step`; FR45 codes the patch kind against it in a new module, and
     qualifies it, with REF's reference. The field-solver interface keeps the factorization and the
     solve (FIELD_SOLVER_INTERFACE_DESIGN §6), which the slot calls unchanged; a later sparse or
     condensed solver replaces them behind the same calls. Under the decision below the faces stay
     where they are, and CORE's slot is the local stage solve.
   - **Which form the slot runs (decided 15 November, after reading the module).** FR45's module
     (`laws/routes/patch_electrodiffusion.py`, `fr45-physics` 4f267ef4) gives two forms: the global
     pieces above (frozen weights with a non-negative conductance; the patch's block, symmetric,
     with zero row sums, positive semidefinite; an implicit-plus-explicit split that recombines
     exactly to the full constant-field flux), and a per-compartment Newton stage solve,
     R(x) = x − x̂ − γh J(x) on the compartment's own permeant amounts, with V_b = −q_j/C_b and a
     Sherman–Morrison Jacobian, checked at a residual of 1e-13.
     - **Its tests exercise the Newton form:** stable at dt × G/C_b up to 48, first order under
       implicit Euler against Radau, the booking closing the energy ledger to rounding, and a
       planted error caught. The global pieces are tested only for the exact split and the
       positive semidefinite block.
     - **So the slot runs the Newton form, as a local stage solve,** at each implicit stage of
       ARS(2,2,2), with that stage's γh (the SDIRK diagonal), before the global field solve:
       - **it is self-contained:** at a face-free node V_b = −q_j/C_b exactly (FR-1 §3.1), so the
         compartment's solve needs no potential from the global solve; the owner cell's amounts
         change by what the compartment loses, and the global solve then sees both charges;
       - **existing programs stay unchanged:** the face part of the implicit set is untouched, and
         the patch's solve is present only where a patch kind is declared;
       - **its routes leave the explicit rates** and the explicit-stage rule, and B7's face-free
         term counts only explicit routes.
     - **Its admission:** the solve is self-contained only on a face-free node with exactly one
       bounding patch, so a patch kind is refused anywhere else.
     - **To settle with FR45 before it is wired:** what `x_hat` carries at ARS's last stage, and how
       the owner cell receives the moved amount within the stage (CORE reads `stage_solve` itself
       first; the module's head and commit message were read for this note).
     - **Its qualification** (FR45, with REF) shows second order under ARS(2,2,2). The owner cell's
       concentrations enter each stage's solve at that stage's known state, an O(h)-relative
       approximation scaled by V_comp/V_cell, which the order study measures.
     - **The global split stays a fallback,** as its own solver ID (D147), if the Newton form fails
       that qualification.
     - **Cost:** the local stage-solve slot, about 1–1.5 agent-days (CORE), as estimated in (h).

#### (h) What this adds to CORE's queue: the lead's rulings (15 November)

- **FR-4's insertion points are split.** FR-4's first world (explicit, with a K⁺ counterion) needs
  three, each a declared-only addition with every existing world unchanged, right after the
  dispatch commits. Costs (**S**, agent-days):
  - **the per-structure schema** (state, layout, control and observation types that gain a kind's
    fields only where it is declared): about 1, paid once by the first of the three and reused by
    the passive law. It touches the adapter's view of the inner layout and control, so it is
    coordinated with INT;
  - **the stage-read slot** ((g) 1): 1–1.5;
  - **the transporter kind with its fuel rows** ((g) 2): 2.5–3.5, revised from 2–2.5 for finite
    fuel as the default (the fuel rows' in-step writes and their standard-potential term). It
    includes the transporters' controls, the held-row admission against `moved_rows`, the ledgers
    and device checks, and the refusal of a parameter-form pump whose own ΔG° disagrees with the
    registry's fuel rows (§10.2);
  - **B7** ((g) 3), at the bound's ordinary constant, with finding 3's term: about 1, host-only,
    one commit with one D148 record and @1's and @2's cases (§13.6).
  - **The implicit slot** ((g) 4) follows once FR-4's first world runs: 1–1.5. It stays outside
    the round unless FR-5's first world needs it (the lead's ruling).
  - **In all, 6.5–8.5 agent-days with finite fuel as the default** (6–7.5 before it), of which
    the implicit slot's 1–1.5 stays outside the round. This supersedes the earlier 3.5–5, which
    had no per-structure schema and a smaller transporter.
- **Off the core's path:** the passive law's kernel module goes to FR45 (the proton leak's
  sibling), and CORE writes its insertion point only, with the exact heat booking (§7.5); the
  summation study goes to OPS (§10.6).
- **The question of how operators reach the implementation object is answered (INT, accepted):**
  operators declaring `USES_INNER = True` receive it as a static `inner=` keyword in their event,
  half_step and rates calls; host methods use `model.inner`; operators stay registry singletons.
  Until the first API commit lands, `inner=` passes today's adapter, which has the same surface.
- **Files:** `definitions/surface_pump_v3_spec.py` and the registry's @3 line are the core's;
  `compartments.py`'s refusal 4 and the charged-buffering closure are FR45's; FR-3's integrator
  consolidation is outside the round. The thin families (`models/cell_replacement.py`,
  `surface_pump_water.py`, `surface_pump_water_v2.py`) import only structure-free names from @3,
  but `cell_replacement.py` builds its composite at import from the inner model ID, which becomes
  per structure (INT's change).

#### (i) The passive law's insertion point: its conventions (REF's closed-pair reference reads them)

The kernel is FR45's (`processes/passive_neutral_permeation`, law `passive_neutral_permeation@1`);
the insertion point is CORE's. Its conventions, fixed here:
- **The declaration:** a `passive_routes` list in the model block, absent unless declared. Each
  route names its ID, the law, its host route (one membrane patch, or one junction), and a
  permeability per neutral species it carries. A species it carries has zero constant-field
  permeability on that host route (refused otherwise), so one law moves it there.
- **The effective PA:**
  - **on a junction, P·A·gate·availability:** the junction's area, its gate state
    (`junction_gate`, the junction law's) and its availability control, the same opening the
    junction's ions see. The gate is evolving state, not 1 at 0 V, so the closed-pair world starts
    it at its steady value, or the reference integrates it;
  - **on a membrane patch, P·A·availability:** the patch's area and its availability control.
- **The flux** is the kernel's constant-field route at valence 0 (Fick's law), at every explicit
  stage, inward-positive, into the node amounts on both sides.
- **The heat is booked in the law's own field, never in the membrane or junction fields:**
  `passive_dissipated_energy_pJ` [passive route], with the transfers in `passive_transferred`
  [species, passive route]. Both exist only where the law is declared, and both join @3's
  material and energy ledgers. The booking is §7.5's exact one, on the neutral rows that only
  exact-booked passive routes move (version 1's scope); elsewhere it is today's tableau booking.
- **Bound:** finding 3's term covers the routes (§13.6).
- **Its own step (ruled):** dt × L ≤ 1, with L = 1e15·PA·(1/V_a + 1/V_b) summed over the
  routes at each node. That is finding 3's z = 0 term for its routes, declared as its bound term.
  A dt-study criterion covers accuracy. Exact booking closes the ledger up to h = 2, so it no
  longer signals an overshoot by itself (§7.5).
- **As built (core-d172 6a43f189, 7af1382f; the lead's ruling: one kind, laws by contract):** the
  kind `cells.passive_routes@1` (`kinds/passive_routes.py`), model key
  `passive_routes` in FR-4's form (`validation/compartment_ph_engine/definitions.py`): a list of
  {id, patch | junction, law, permeability_m_per_s (one number), species (the neutral law's row;
  the leak's defaults to H), factors (empty: FR-5's damage and pH condition come with FR-5's
  laws)}.
  - `passive_neutral_permeation@1`: the kernel's Fick flux on the read amounts, inward from the
    host's outside end to its inside end; §7.5's exact booking where version 1's scope mask
    (`passive_exact`, set at binding from `moved_nodes`; a route touching a held bath is never
    exact) allows; its step is `bound_rate` (gap 5). The mask is a fixpoint over shared rows
    (1e57af61): a route sharing a row with a tableau-booked passive route is tableau-booked too,
    so every exact row is moved by exact routes alone. The operators' writers (`moved_in_step`)
    join at the composite's admission (INT).
  - `proton_constant_field_leak@1` (`laws/transport/proton_leak.py`): an H⁺ constant-field route on a
    membrane patch at the patch voltage, reading free h through B4's read at buffered nodes;
    tableau-booked (charged: never exact); its max-side slope conductance is its `stage_term`
    (B7, gap 5) and its flux joins the membrane current (gap 9); its row must be B4's proton row
    where B4 is declared.
- **B4's declaration (7af1382f)** is FR-4's `stage_reads` list: [{read_id:
  "rapid_proton_buffer@1", proton_row, buffers, k_on_per_mM_s}], one read in version 1.

#### (j) The per-structure schema: three options, and the ruling (A, 15 November)

**What it must do.** New kinds add state, layout, control and observation fields: FR-4's
transporter with its fuel rows, its stage read and the passive law ((i)). B7 adds none. A world
that declares none of them keeps today's types. A world that declares one carries that kind's
fields and no others ((d), the "Schema" level).

**How types are used today** (the facts the options are judged on):
- **Snapshots** are npz archives keyed by the state's and layout's field names. Reading requires
  the archive's key set to equal `model.STATE_TYPE._fields` plus the layout's, and builds
  `model.STATE_TYPE(*…)` (`io.py`). A restart requires `type(checkpoint.state) is
  model.STATE_TYPE` (`execution/runner.py`).
- **Results and the acceptance owner's baseline** flatten histories, observations, diagnostics and
  final states by field name (`results_baseline.py`'s `flatten`). D176's gate compares key sets as
  well as bits.
- **The compile key** holds the argument tree, which includes its NamedTuple types, and the leaves'
  shapes (§7.4 (e) 4; 43812f59).
- **The composite already builds its types per composition.** Its STATE_AXES is the inner model's
  plus each operator's, and it builds `CompositeState`, its layouts and its Observations from them
  (`pump_composite.py`). Operators address fields by name (`state.x`, `_replace(x=…)`).
- **Generic code builds and splits states positionally:** `STATE_TYPE(*(…))` and
  `type(state)(*(v[i] for v in state))` (rates, readouts, windows, checks). That is about 50 sites
  in `core/` and more in the models and operators.

**Option A: types per structure, on the implementation object.**
- **The design.** The object carries its structure's STATE_AXES, STATE_TYPE, LAYOUT_TYPE (and the
  floor layout), the Control type the schedule fills (a transporter's controls), OBSERVATION_FIELDS
  and Observations. They hold today's fields in today's order,
  then each declared kind's fields in kind order. A structure that declares no new kind returns
  today's module types themselves, the same class objects. Classes are cached by field set, so
  structures with the same kinds share one class, and they get deterministic names
  (`SurfacePumpChannelState[transporter]`).
- **Checkpoints:** today's worlds unchanged (same keys, same class). A kind's world writes and
  reads its own fields. `io.py` and the runner already read `model.STATE_TYPE`, and the object
  supplies it.
- **Observation columns:** today's worlds unchanged. A kind appends its columns, as an operator
  does in the composite.
- **Compile key:** today's worlds' trees unchanged. A kind's world has its own tree and so its own
  executable, which it needs anyway for its own program.
- **D176's gate:** today's worlds bitwise, with no new leaves and no renamed keys, by construction.
  It can be tested by identity: `impl.STATE_TYPE is surface_pump_v3.STATE_TYPE`.
- **Operators by name:** today's fields are unchanged. An operator that reads or writes a kind's
  field declares that kind. The composite's admission refuses it at binding in a world without
  the kind, so there are no runtime presence checks.
- **Cost:** about 1 agent-day, as costed in (h).
  - @3's own builders that name the module's STATE_TYPE take the structure's instead; the dispatch
    commits already thread the structure.
  - The composite builds from `inner.STATE_AXES`, so its types follow once INT's switch passes the
    object.
- **Risks:**
  - A re-created class would break `type(…) is` and the compile cache, hence the cache by field
    set.
  - No pickling is involved: snapshots are npz by name.

**Option B: one superset type, with zero-size fields for undeclared kinds.**
- **Checkpoints:** every world's snapshots gain every kind's keys as empty arrays. Today's
  snapshots no longer load (the key-set check) unless the reader tolerates missing empty keys.
- **Observation columns:** every world gains empty columns.
- **Compile key:** every world's tree gains zero-size leaves. So every program changes, every
  executable recompiles, and crossrev's records change.
- **D176's gate:** fails as written, with new keys in every world. It would pass only with a
  comparator exemption for empty new keys, which the gate does not have.
- **Operators by name:** the simplest, since every field always exists. But every reduction over a
  kind's field must handle empty arrays (initial values for max and min), in every operator and
  check.
- **Later kinds:** each new kind changes every world again.

**Option C: today's types plus one extension container, `kinds`, empty for today's worlds.**
- **Checkpoints:** the container is a new field name in every world's state. The npz writer and
  reader must flatten it to prefixed keys and skip it when empty. Otherwise today's snapshots stop
  loading, and an empty tuple would be saved as an empty array.
- **Observation columns:** unchanged, if the observer ignores the container. A kind's columns come
  from inside it.
- **Compile key:** an empty container (a dict or an empty NamedTuple) adds no leaves, but every
  world's tree changes by one node. The programs are unchanged (the jaxpr is over leaves), and
  executables recompile once.
- **D176's gate:** leaves are identical. Keys are identical in the acceptance owner's `flatten` for
  a dict or empty-NamedTuple container (no keys), but not for an empty tuple (a new key). The
  snapshot IO still has to change.
- **Operators by name:** today's fields are unchanged. A kind's field is reached as
  `state.kinds.<kind>.<field>`, and `_replace` needs a nested form. Every positional build or split
  of a state must skip or recurse into the container: the ~50 sites in `core/` and those in the
  models and operators.
- **Its merit:** later kinds are added inside the container without touching today's fields.

**A later kind, and a kind declared by two laws (the same under A, B and C).** Fields belong to
the kind, not to a law:
- The kind has one population axis, and each population's law code selects its kernel, as
  channel slots do.
- A field that only some laws need is present when any declared law needs it, sized by the
  largest declaring law, as `gate_rows` is today.

Examples:
- **FR-4's charged buffering:**
  - Buffer rows are inventory rows on the species axis, so they need no new state.
  - The closure's declaration adds layout fields: the buffered (node, row) mask, k_on and c0.
  - It adds one state accumulator, the closure's free-energy term ΔG_buf per node for the energy
    ledger.
  - It adds one diagnostic column, the stage residual |g|/H̄_eq.
  - Under A all of these appear only where the closure is declared.
- **Fuel:**
  - Held fuel (`maintained_held_rows@1`) adds the maintenance's material record per population
    (+1 ATP, −1 ADP, −1 Pi per cycle).
  - Finite fuel adds only its standard-potential term's accumulator: its rows are inventory rows,
    moved by the pump.
  - A world declaring both fuel kinds carries both.
- **Two transporter laws:** one transporter population axis, each population with its law code.
  Cycles and ledgers are per population. A law with an extra internal state adds a field sized by
  the largest such law.

**Recommendation: A.**
- **Why A:**
  - Under A alone, today's worlds get the very same type objects as today. D176's gate, the
    snapshots, crossrev and the compile cache then need no exemption and no IO change.
  - It follows the composite's existing per-composition pattern, and the implementation object
    is already its home.
- **Why not C:** C's isolation of kinds is attractive, but it changes today's types by one field
  and touches every positional build and split of a state.
- **Why not B:** B changes every world now, and again at every new kind.
- **A's own risks** are handled by caching classes by field set, with deterministic names, and by
  a static admission rule for operators that need a kind's fields.
- **Cost and coordination:** about 1 agent-day, inside FR-4's first insertion point. INT's switch
  is the only coordination needed: the composite then builds from the object's STATE_AXES.
- **Acceptance for A:**
  - today's worlds' types are the module's own (identity);
  - a planted kind adds exactly its fields, at the end;
  - a kind's world round-trips through a snapshot;
  - the results gate is bitwise for today's worlds.

**The lead's ruling (15 November, after the advisor's review and INT's comments): A, with three
additions to its acceptance.**
1. **Canonical kind order.** The appended kinds' fields follow the canonical kind order, never the
   definition's declaration order. It is the sorted namespaced kind ID, a total order independent
   of registration and import order (the lead, 15 November, for external modules). Test: two worlds that declare the same kinds in
   different orders get the same class, compile key and snapshot layout.
2. **The families' refusal must exist.**
   - Replacement@1 and both water families bind full-catalogue types at import and build states
     positionally, so a planted kind in each family is refused at binding.
   - An operator that reads a kind's field declares `REQUIRES_KINDS = (...)`, and
     `structure_errors` refuses a missing kind, naming the operator and the kind.
   - INT builds both, and the adapter's forwarding of the object's types: `STATE_AXES`,
     `STATE_TYPE`, `STATE_FIELDS`, the layout and control types, `OBSERVATION_FIELDS`.
3. **A planted kind through the run paths.** Its snapshot round trip runs in a fresh process, and
   the planted kind also runs on the vector-window path, since packing depends on it.

**Scope rules (the lead's ruling, 15 November, after CORE's map of today's fixed-field
sites):**
- (a) **Ledgers.** A kind's ledger terms fold into today's 10 ledgers by role (material per
  species and node, charge, energy, heat, work). No new ledger rows in this round; a kind with a
  genuinely new conserved quantity would be a later core change.
- (b) **Columns.** A kind's state fields are observation columns, right after today's state
  fields (the windowed runner rebuilds states from observations by name), and its readout columns
  follow today's readouts. Today's worlds keep today's columns, bitwise.
- (c) **Material.** A kind's material moves land in the shared inventory, today's amount fields
  (F2: one authoritative account per quantity). Only the kind's own accumulators stay outside the
  families' and operators' projections, which therefore keep charge right.
- (d) **Controls.** A kind's controls are availabilities in [0, 1], unless its control-domain hook
  declares otherwise.

**A padding artifact kept for bitwise identity (F1; K2's amendment 6; the lead's ruling, 15
November):**
- **The artifact.** A closed or not-yet-open population slot carries code 0, Kv1.5's code, and
  keeps its gate update. Today's catalogue evolves that gate under Kv1.5's kinetics. That is an
  artifact of today's padding, kept only for bitwise identity through D176's gate.
- **Where it is traced.** A4's "no kernel" holds for worlds without closers. A world whose
  composition closes slots (an operator with CLOSES) traces code 0's kernel as declared padding,
  named by the structure's `padding_fill`. That is ruling 8's declared, temporary fill, compiled
  where it is needed.
- **Its effect on physics, by opener:**
  - the partition sets the gate (daughters take the parent's at division);
  - replacement sets it (the template's or a source slot's at arrival);
  - insertion@2's onset does not: a gated population on an onset patch starts from the gate the
    artifact evolved while it was closed. Today's physics after an onset therefore depends on the
    artifact.
- **The insertion@2 bug is latent** (the acceptance owner's scan, `acceptance/insertion2-scan.txt`).
  - `membrane_insertion_v2.check_onsets` refuses any channel population on an onset patch
    ("Channel populations on an onset patch are later work"). So no accepted definition reaches
    the inherited gate, and no evidence is affected.
  - Insertion@2's onset patches (S5 and its tools, crossrev's division_furrow and
    division_quartered) carry no channels. Kir2.1 and NaV1.2 sit only on cell membranes, which
    the partition opens with their gates set.
  - The gate fix (gates frozen while closed, or set at opening) is a precondition for lifting
    `check_onsets`'s refusal, and lands with or before that change, as its own gated change.

**Costs accepted:** about 2.5–3 days for CORE, with INT and OPS in parallel. INT takes the
adapter's lookup order (the object first), the composite's 11 inner type reads, the composite
spec's controls from the object and the families' refusal. OPS has `moved_in_step` call the
declared kinds' `moved_rows`.

**CORE's part (about one day as first costed, 2.5–3 days with the scope rules above; after the registry hook and B7):**
- the object's per-structure types, cached by field set in canonical order;
- today's classes returned for today's structures;
- the identity test, the planted-kind test, the fresh-process round trip and the vector-window
  run.

INT merges CORE's types first, then the adapter's forwarding.

#### (k) The kind interface: one module per kind (the lead's ruling, 15 November; design before code, D142)

**Why.** After schema A, each new kind is its own module under `models/inner_kinds/`: FR-4's
stage read (B4), the transporter (B5) and the passive law ((i)). Core functions call the declared
kinds generically at fixed seams, so two writers never edit one core function. A kind edits no
core file, and a seam change goes through CORE.

**The registry and IDs** (constraints from the user's direction on external modules; the lead,
15 November):
- Core holds a registry of kind objects (register and lookup) and imports no kind module.
- Built-in kinds register through the same call an external package would use, from their own
  package (`models/inner_kinds`). Parse and build take the registry, defaulting to the built-in
  one, so the lookup is scoped to the model build.
- Kind IDs and new law IDs are namespaced (`cells.transporter@1`). A bare ID resolves in the
  `cells` namespace: today's law IDs stay as written, since renaming them would change every
  definition and fingerprint.
- A registered but undeclared kind changes nothing. A second planted-kind test checks that a
  world which does not declare it keeps today's classes, compile key and snapshot layout.

**A kind declares** a module-level object, registered by its namespaced ID, appended in the
canonical kind order (sorted ID) that schema A's types use:
- `KIND_ID`, and its laws' declarations in its own module, as `inner_laws` holds the channels';
- its fields: state axes, layout fields, control fields and observation columns, each with its
  axes' names. Schema A appends them in canonical order;
- `parse(entries, base)` → its declaration, from its model-key block (`entries`) and the parsed
  @2 base definition; `to_dict(declaration)` → that block; `control_values(spec, declaration,
  times)` → {control field: [time, ...]}, constant over the run in version 1, piecewise constant
  on the step grid from its schedule under (l);
- `initial(spec, declaration, layout)` → ({state field: array}, {layout field: array});
- `structure_entry(declaration)` → its hashable, value-free part of the InnerStructure. That part
  enters the compile key, the batch signature and the cached implementation.

**The hooks the core calls, as built** (schema A, `core-d172` e71dac25, with the stage check and
the bookings' validity from 307daf3a and 6c850d91; the authoritative list is the `Kind` docstring
in `registry/kind_registry.py`). Each is optional; a kind supplies the ones it needs. `p` is the
world's layout and `state`, `control` are in the structure's own types. **Built-in kinds**
register on `BUILTIN` from their own package: `kind_registry.active()` imports
`cells.kinds` by name once, so the core imports no kind module and a registered,
undeclared built-in changes nothing:
1. **`stage_read(state, p, *, xp)` → (the state whose amount fields hold the amounts the stage's
   rates read, valid),** at the concentration entry of every stage: `readouts` (so `rhs`),
   `explicit_rates` and `imex_step`'s face weights call it before any rate reads a
   concentration; `implicit_rates` uses the frozen weights. B4 uses it; reads compose in hook
   order. **A failed read refuses the row and the step,** and `domain_valid` evaluates the reads
   at every checked state, the step's end included (§7.4 (g) 1). **The read changes
   concentrations, never charge:** the field solve takes the stored rows' charges (FR-4's H_eq
   and buffer totals), and only the rates see the read amounts. A stage read declares
   `stage_rows(declaration)` → ((species, node ID), ...), every row it reads or rewrites. A row
   may name its read's law as a third item (P1's selector, `free_amount_reads` above); rows are
   shared by their (species, node), whatever law each names.
   - **`stage_check(read, cell, outside, p, *, xp)` → one bool,** after every rate of a stage
     (`readouts` and `explicit_rates`), with the read state and the stage's total node rates; a
     false check refuses the row or the step. FR-4's envelope (the closure's lag at the stage's
     transport) is one.
2. **`rates(state, potentials, control, p, *, xp)` → `KindRates(cell, outside, derivatives,
   heat_pJ_s, work_pJ_s)`:** inward-positive node changes (cell [species, cell], outside
   [species, outside node]) into the shared inventory, where the field solve sees their charge
   (rule (c)); its own state fields' derivatives; heat and work rates, which join the energy rate
   by role (rule (a)). `potentials` are the stage's node potentials, cells then outside nodes.
   They are added after today's terms, in hook order. `KindRates.valid` (7af1382f) is the
   kind's own domain at the stage's read and potentials (a charged law's V-dependent domain,
   such as |ΔG_cyc/RT| ≤ 80), and-ed into the stage's validity. `KindRates.membrane_flux` (outward
   [species, membrane], optional) joins the patches' total flux and membrane current
   (observations; gap 9, 669f8ed6). `KindRates.stored_pJ_s` (optional, gap 2, (m)) is the rate of
   the kind's stored free energy that its read does not carry; it joins the stage energy-rate
   observation by role.
   - **Step size (B7 for kinds; gap 5, 669f8ed6; 5b1b931e; 2c780f9f):** `stage_term(read,
     potentials, control, p, *, xp)` → [cells, then outside nodes] conductance (S) at the stage's
     read and node potentials, a patch's slope at both of its ends (`patch_node_conductance`), so
     a pump driven past its static head into reverse counts its e^a. With kinds declared,
     `membrane_rate`'s per-stage refusal holds every cell and every free outside node
     (`free_outside_nodes`: B7's face-free nodes, a face-free compartment's included) to
     dt·ΣG/C ≤ 1; without kinds it is today's cells-only rate. `bound_rate(spec, declaration)` →
     1/s, a definition-time term the host step checks hold to the same bound (the passive law's
     dt·L ≤ 1).
     **Amended 25 November 2026 (CALCIUM_STORE_AND_CHANNELS_DESIGN.md §8.3):** beside a floating
     node (a finite node that no face names, no held bath and not the gauge) the rule holds, with
     kinds or without, every cell over its held patches alone and every patch that faces such a
     node over its own capacitance (`charge_rows`). It reads each `stage_term` twice, as it is for
     those patches' rows and with them closed for the cells'. A world with no floating node keeps
     the sentence above and its program.
   - **The material rule, as of 25 November 2026** (CALCIUM_STORE_AND_CHANNELS_DESIGN §8.2):
     `material_rate` adds, per node, the blocked populations' part (FR-51), each kind's
     `material_term`, the channel populations' whose law declares one (`channel_material_rates`) and
     the loops that routed slots close on their own gates (`loop_material_rates`). In each part a
     mode's own rate goes to every row the mode moves, at both ends, held baths left out; the modes
     add per row and a node's rate is its largest row. dt x rate is held to the charge rule's bound,
     at every explicit stage. A world with none of the four has none of the rule.
   - **One writer (gap 8, 669f8ed6):** `held_rows(declaration)` → ((species, node ID), ...), rows
     the kind reads and never moves; binding refuses any inner route or other kind that moves
     one. The operators' writers are the composite's admission.
   - **Per-stage diagnostics (gap 7, dfe1234c):** `stage_values(read, cell, outside, p, *, xp)` →
     {own state field: value} at every explicit IMEX stage, with `stage_extrema` = ((field,
     "max" | "min"), ...); the step's end state holds each field's running extremum over every
     stage so far. B4 reports `proton_buffer_max_lag_pH`, `_min_pH` and
     `_max_pH` per node; an envelope breach stays a refusal (the verdict), these are the margin.
3. **`book(applied, start, end, control, p, dt, *, xp)` → ({own state field: new value},
   valid),** in `imex_step` after the tableau's combination; `applied(name)` is the step's applied
   rate of a state field (the tableau's explicit and implicit weights). Every kind receives the
   same end state (before any kind books) and may write only its own state fields, so bookings
   commute. A false valid refuses the step: §7.5's "negative exact share: step-bound breach".
   §7.5's exact booking is one. `control` is the step's held control, constant over the step
   ((l) 5, core-next): a kind can book an exact per-step update at the step's values, as FR-5's
   damage step needs.
   - **Kinds need an IMEX solver (the lead's ruling, 16 November 2026; compartment-op-fixes
     9a48041c).** @3 refuses a definition that declares kinds under RK4, fail-closed
     (`surface_pump_v3._check_kinds_solver`). Every step guard above belongs to the IMEX step:
     the host step checks hold B7's term and the kinds' `bound_rate` for the IMEX solvers only,
     and the per-stage rule (`stage_term`) and the bookings run in `imex_step` only, so an RK4
     step ran none of them and kept only its 0.1 ms cap. The earlier reading here, that under
     RK4 a kind's derivative fields integrate like any state, described that unguarded path; no
     test or world used it. A design for kinds under RK4 can lift the refusal. The core's review
     of FR-1's refusal 4, version 1.1, found the gap (CLOSED_COMPARTMENT_DESIGN.md §3.4.1).
4. **`ledger_terms(state, p, *, xp)` → {"cell", "outside", "produced", "heat_pJ", "work_pJ",
   "stored_pJ"} (any subset):** cumulative inward-positive node transfers, a reaction's net
   production per species (`produced`, (m)), heat and work accumulators, and `stored_pJ`, the
   free energy the kind holds beyond the stored rows' own terms (its change since the start:
   FR-4's buffer term, finite fuel's standard term), folded by role into `balances`,
   `device_balances` and the ledger magnitudes, so every ledger closes with its moves.
5. **`domain(state, p, *, xp)` → one bool,** and-ed into `domain_valid`, on the host and the
   device; **`control_domain(control, p, *, xp)` → one bool,** in place of the [0, 1] rule for
   its controls (rule (d)).
6. **`readouts(state, read, potentials, control, p, *, xp)` → its readout columns** (7af1382f:
   the stored state, the row's read and its node potentials, so a charged law reports its
   instantaneous rate at a buffered node), in order, which
   `observe_history` writes after today's.
7. **`moved_rows(declaration)`** → ((species, node ID), ...), or ((species, node ID, law ID),
   ...), the rows it moves in the step, joined into `moved_rows` (the registry's `moved_in_step`
   reads them).
8. **`check_definition(spec)`:** its definition-time refusals (for example B5's held-row admission
   and ΔG° against the registry). It runs after the registry's checks and before @3's.

**Rules.**
- **Hooks are pure.** They close over the kind's declaration (structure), never over values (P5),
  so a value change reuses executables.
- **No cross-kind reads.** No kind reads another kind's fields; a dependency between kinds is a
  seam change, through CORE.
- **An undeclared kind is absent:** no field, no kernel, no hook call. A4's criterion extends to
  kinds.
- **Two orders, named apart** (docs/MODULE_SYSTEM_DESIGN.md §7, D180): the field order is
  `structure.kinds`, canonical by sorted ID. The hook-evaluation order is a separate name, equal
  to the field order in version 1, so a later dependency order moves no field or snapshot layout.
- **No global codes for kinds:** kinds and their laws carry no code. A kind's law index is bound
  per definition by the resolved structure, and no global code sequence is hardened. Today's
  channel LAW_CODES stay as they are.
- **Non-commuting hooks on the same rows are refused at binding.** Of the hooks, only stage reads
  compose: two kinds' stage reads on a shared row (their `stage_rows`) are refused at binding, and
  a stage read that declares no rows is refused. Bookings commute by construction (one end state
  for every kind, own fields only); rates, ledger terms and domains add or and. Version 1 has one
  stage read, so no declared world is refused.
- **The planted kinds are registered from outside `src/cells`,** under a non-`cells` namespace
  (`tests.`), on a test-local registry.
- **The parsing surface (core-d172 d4b3c01f; D180):** a kind's `parse` and `check_definition`
  refuse with `ConfigError` and may use `require_fields(value, expected, name)`,
  `finite_number(value, name, *, positive=False)` and `bounded_integer(value, name, *,
  minimum, maximum)`, all exported by `cells.registry.kind_registry` (public names in
  `cells.definitions.specs`, whose underscored helpers stay as aliases for today's callers). Kinds and
  external modules use these, never the private names.
- **Ledger lists stay the shared literals in this round** (rule (a)). Reading them from the
  implementation object would change @1's and @2's shared check code, so it follows the landing,
  with its own D148 case.
- **Hooks on the check path trace on the device.** `domain`, `control_domain` and
  `ledger_terms` take `xp`, trace under jnp and branch on no value in Python. So the device's
  per-row checks include kinds as the host's do. That leaves room to move host-side checks into
  device windows: the coupling export measured them at 91% of the runner path's wall time.
  Enforced at binding: `check_definition` traces each of them once (`jax.eval_shape`) on the
  definition's initial state, with `stage_read` (which `domain_valid` evaluates) and
  `stage_check`, and refuses a hook that does not trace, a domain, read or check that is not one
  bool, and a ledger term of an unknown role or shape.
- **The planted kind of schema A's acceptance implements every hook** with trivial physics: a
  neutral species exchanged at a constant rate between two nodes, with its own ledgers. So each
  seam is exercised before any real kind lands.

**Ownership.**
- The seams in `surface_pump_v3.py`, `inner_laws.py` and `surface_pump_v3_spec.py` are CORE's.
- Each kind module is its owner's:
  - B5's transporter is FR45's, reviewed by CORE before INT merges it;
  - B4's stage read is CORE's, with FR45's closure kernel;
  - the passive law is CORE's insertion with FR45's kernel.

#### (l) Time-varying kind controls: schedules on the step grid (gap 6; designed 16 November 2026, before code)

**What it must do.**
- In version 1 a kind's controls are constant over the run: `control_values(spec, declaration,
  times)` gives one value at every time (the transporter's availability 1).
- A kind must be able to declare piecewise-constant control schedules. FR-5 is the first consumer.
  - Its damage state on a bounding patch (`bounding_patch_damage@1`, `laws/transport/patch_damage.py`)
    follows dd/dt = k_inj u_inj(t)(1 − d) − k_res u_res(t) d, with u_inj and u_res declared
    schedules in [0, 1] (the FR-4/FR-5 note, §9).
  - Its step, d(h) = d_eq + (d − d_eq) e^{−(a+b)h}, is exact only where the schedules are
    constant over the step. So every breakpoint must be a step boundary, and the step's update
    must see the step's values.
  - FR-5's definitions already declare the form, as a pending experiment key
    (`validation/compartment_ph_engine/definitions.py`): `damage_controls`, [{damage_id,
    injury: [{time, value}], resealing: [{time, value}]}].
- Today's definitions, programs and records stay as they are.

**How controls work today** (the facts the design turns on):
- Controls are host-side, right-continuous and held over each step. Every path evaluates
  `control_values(spec, times[:-1])` at the steps' starts: the runner, the windowed and vector
  paths, and the projective mode.
- The step grid is `EventGrid(spec)`: the nominal i·dt grid joined with every time of
  `spec.experiment.changes`, an off-nominal time inserted exactly. So a breakpoint is a step
  boundary exactly when it is a change time.
- The change records hold, at each time, every family's values. They also serve two checks:
  - a checkpoint's event index (`event_index`);
  - `branch_checkpoint`, which compares the records before a branch's checkpoint, so a branch
    cannot rewrite the past schedule.
- The vector path holds controls per segment between change times, and refuses controls that
  vary inside one (`vector_windows.held_controls`). The scalar runner has no such check.
- The composite's and replacement's records build on @3's (`ionic.Experiment.changes.fget`). Each
  operator adds its `schedule_times` and its `value_at` records.
- A kind's declaration lives in the model block, and `branch_checkpoint` refuses any change of
  the model.

**The design.**
1. **A kind's schedule lives in the experiment, under its own keys.**
   - A kind declares `experiment_keys`, as an operator declares `EXPERIMENT_KEYS`. Each key is
     optional in a definition. One that the definition omits takes the kind's default, version 1's
     constant.
   - `parse_schedule(raw, base, declaration)` → a `Schedule` (2), with `raw` the {key: value} that
     the definition gives, possibly none. `schedule_to_dict(schedule, declaration)` → the {key:
     value} to write back. The kind omits its default, so a definition that omits the key keeps
     its form and its fingerprint.
   - @3's parse pops each declared kind's experiment keys before @2's strict parse. It refuses an
     experiment key of a registered kind that the model does not declare. The registry refuses
     two kinds with one experiment key, and the composite refuses an operator's key that a
     registered kind declares.
   - In the experiment, a branch may change a kind's future schedule, as it may any control's.
   - Schedules are values. They enter neither `structure_entry` nor the compile key, so
     definitions that differ only in their schedules share one implementation object and its
     executables.
2. **One schedule type, the core's: `kind_registry.Schedule`.**
   - It holds named series, each right-continuous and piecewise constant from time 0: ((name,
     ((time, value), ...)), ...). Times start at 0 and strictly increase, and values are finite.
     `times` is the union of the breakpoints, `at(t)` gives one value per series, and
     `values(name, times)` evaluates one series.
   - The core checks every breakpoint against the horizon.
   - **Why one type, not one per kind:** every control reaches the step as a number per slot, held
     over the step. So named scalar series carry anything the control path can, and the core
     needs no hooks for the times or the records.
   - The parsing surface gains `parse_series(entries, name, *, value="value", unit_interval=True)`
     → ((time, value), ...) for a list of {time, value} entries, and `series_to_dict(series, *,
     value="value")`. FR-5's form is two such lists per population.
3. **The breakpoints join the change times, and the records carry the values.**
   - @3's experiment gains `kinds`: ((kind ID, Schedule), ...) for the declared kinds that
     declare experiment keys, in canonical order. Every other definition has (), and so keeps
     today's records, by value and by type.
   - With a schedule, the change times are the union of today's and every schedule's
     breakpoints. Each record is a `KindChange`: today's held values plus each schedule's `at(t)`.
     So:
     - each breakpoint is a step boundary, on the nominal grid or inserted exactly;
     - the composite's and replacement's records carry it, since they build on @3's;
     - `branch_checkpoint` refuses a branch that rewrites a kind's schedule before the checkpoint;
     - the definition's control check, which evaluates the controls at every change time
       (`check_definition`), holds rule (d), or the kind's `control_domain`, at every breakpoint.
4. **The control table comes from the change records.**
   - @3's `control_values` evaluates each kind's `control_values(spec, declaration, change times)`
     once per record. It holds each row over the steps that record governs, by the records'
     index: the row of the last change time at or before each time, as today's families' rows.
   - So a kind's controls are constant between change times on every path, the scalar runner
     included.
   - The hook's signature is unchanged. A scheduled kind reads its schedule with
     `kind_registry.declared_schedule(spec, kind_id)`.
5. **The step's control reaches `book`** (a seam change, in its own commit):
   - `book(applied, start, end, control, p, dt, *, xp)`, with `control` the step's held control,
     constant over the step by 3 and 4;
   - so a kind can book an exact per-step update at the step's values, FR-5's d(h);
   - a bound term reads the schedule through `declared_schedule` where it needs it (for example
     its largest value).
6. **What stays unchanged.**
   - A definition without a scheduled kind keeps the same records (values and type), grid, event
     indices, controls and programs.
   - Today's built-in kinds declare no experiment keys. The transporter keeps its constant
     availability until its owner adopts (g) 2's `transporter_controls` in this form.

**Acceptance (tests, with planted scheduled kinds registered from outside `src/cells`):**
- an off-nominal breakpoint splits the grid exactly, and each step's control is the schedule's
  value at the step's start;
- a planted relaxation, booked per step at the step's control (FR-5's form, through
  `patch_damage.exact_step`), matches its closed form across the breakpoints to rounding;
- a planted constant-rate mover under a schedule moves exactly Σ rate × value × duration;
- the definition round-trips with and without the key, and an omitted key keeps its default and
  its fingerprint;
- refused: an undeclared kind's key, a breakpoint past the horizon, and a value outside the
  control domain;
- two schedules share one implementation object and compile key;
- `branch_checkpoint` refuses a rewritten past and admits a changed future. A restart from a
  checkpoint across a breakpoint continues bitwise, in a fresh process as well;
- the vector-window path and the composite path hold the same controls (FR-5's judged world runs
  with FR-1's compartment operator);
- crossrev against 3c10b833 identical, and a pair check on kind-declaring worlds (FR-4's
  development and declared worlds): jaxpr text, and control bindings at every change time.

**As built (core-next, 16 November 2026; accepted by the lead):** 614a081b (the schedules) and
5fcfe9ed (`book` receives the step's control). The second changes a hook's signature, so it is a
change of the kind interface's public surface (D180): every kind's `book` takes `control`.

#### (m) The stored-rate term in the stage energy-rate observation (gap 2; designed 16 November 2026)

**What it must do.**
- A kind that holds free energy beyond the stored rows' own terms books it as `stored_pJ` in
  `ledger_terms`, its change since the start, so the cumulative energy ledger closes ((k) 4).
- The stage energy-rate observation, `energy_balance_pJ_s`, has no term for that free energy's
  rate. It is the chemical rate at the stage's read concentrations, plus the capacitor's, plus the
  heat, minus the work. It is zero to rounding in every world of today's, FR-4's included.
- Finite fuel (`finite_fuel_rows@1`, D176 item 2, the R-fuel world) is the first case. Its rows'
  standard part, Σ μ°' ṅ = Δ_rG'° × cycles, lies outside @3's RT ln c terms, so without its rate
  the observation is off by exactly that amount.

**What the read already carries.** The chemical rate is Σ RT ln c ṅ at the read's
concentrations. A stage read whose stored term G has ∂G/∂n = RT ln(c_read/c_stored) therefore has
its rate in the chemical rate already. B4's closure term is one: its H_eq derivative is
RT ln(h/H̄), (g) 1. So B4 declares no stored rate, and its world's observation closes today
(checked: residual 0.0 at FR-4's development world's rows).

**The design.**
- `KindRates` gains `stored_pJ_s`, optional (None by default). It is the rate (pJ/s) of the
  kind's stored free energy at the stage, less the part that its read carries.
- It joins `energy_balance_pJ_s` by role, after today's terms and the kinds' heat and work, in
  hook order: + stored. The ledger roles and the rate roles now match: heat_pJ and heat_pJ_s,
  work_pJ and work_pJ_s, stored_pJ and stored_pJ_s.
- **The rule for a kind's author:** `stored_pJ_s` is the time derivative of the kind's `stored_pJ`
  less its read's carried part. Then the cumulative ledger and the rate observation agree. For
  finite fuel it is Δ_rG'° × cycles at the fuel node.
- **Unchanged:** a kind that gives no stored rate adds nothing to any program (None is static).
  Today's kinds give none (B4's is carried, and the passive routes and held fuel store nothing),
  so FR-4's programs are identical.

**Acceptance:** a planted kind converting a neutral S to a neutral P at a cell, with declared
standard potentials, so its standard part is stored and no read carries it. Every ledger closes
in the host checks, and its observation's residual is zero to rounding. Without its stored rate,
the residual is exactly minus that rate while the cumulative ledger still closes. FR-4's kind
worlds are unchanged in the pair check, and crossrev is identical.

**Found while building it: a kind's net production per species.** The planted conversion failed
the global material ledger, `total`: Σ amounts − the reservoirs' supply, per species, which
holds every transfer to zero. A kind's `cell` and `outside` terms close the node ledgers but do
not reach `total`. Finite fuel converts ATP into ADP and Pi, so it would fail there too. The
reactions operator closes it with its node sums (D152). For a kind:
- **`ledger_terms` gains the role `produced`:** [species], the cumulative net amount the kind has
  created (+) or consumed (−). It is a reaction's record and joins `total` and its magnitude.
- **A transfer kind gives none,** so `total` still holds it to conservation independently of its
  node terms.
- **Charge:** `produced` must be charge-neutral, or the global charge ledger refuses it. Finite
  fuel's rows are neutral.
- **The test:** the planted conversion closes `total` with its record, host and device alike, and
  fails it by exactly its record without one.

**As built (core-next 3e7095cc; accepted by the lead):** `KindRates.stored_pJ_s` and the ledger
role `produced` are additions to the kind interface's public surface (D180), as (l)'s `book`
control is. The transporter's finite fuel adopts them in its own module (the FR lane's).

#### (n) The routing door: factors from source kinds into routed control slots (designed 16 November 2026, before code)

**What it must do** (FR-5; the FR-4/FR-5 note §16 on `fr45-next`; the lead's brief):
- FR-5's routes are FR-4's laws, each scaled by a rate multiplier m ∈ [0, 1], the product of the
  route's factors in declared order. The factors are a patch's damage d (`cells.patch_damage@1`)
  and a node's pH condition f(pH) (`cells.ph_condition@1`).
- The factors are evaluated on each stage's state, which keeps second order. A factor outside
  [0, 1] refuses the step. Factors book nothing.
- One kind's factor must reach another kind's routes without a cross-kind read ((k)'s rule). So
  this is one core seam, a stable surface for external modules (D180).
- FR-4's structure, Control type and compile key stay as they are. The sink's multiplier slot
  exists only where some route declares factors (the lead's preference).

**The design.**
1. **Sources.** A kind declares `factor_sources(declaration)` → (source ID, ...): the entity IDs
   whose factors it exposes. It also declares `factors(read, p, *, xp)` → [len(sources)] values
   at the stage, from its own fields and the stage's read state. A factor that depends on node
   potentials would be a later extension of this seam.
2. **Sinks.** A kind declares `routed_controls(declaration)` → ((control field, slot, (source ID,
   ...)), ...). Each entry names a slot of one of its own control fields and the sources whose
   product scales it, in declared order.
3. **Binding.**
   - The core resolves every named source to one declared kind's source.
   - It refuses an unknown ID, an ID that two kinds expose, a slot routed twice, a field that is
     not the sink's own control field, and a slot outside its field.
   - The resolved table, (field, slot, ((source kind, position), ...)), is the structure's
     `routes`. It is value-free, so it enters the compile key.
   - A definition without a sink has (), so the door is absent and every program unchanged (A4).
4. **At every stage,** the stage read comes first and the door second; then every kind's
   `rates`, `stage_term` and `readouts` see its result.
   - This happens in `readouts` (observed rows included), `explicit_rates` and `membrane_rate`'s
     stage term.
   - Each routed slot becomes its held value × its sources' values, a left fold in declared order,
     so its rounding is fixed. The result is written into the control that every kind receives at
     that stage.
   - A source value outside [0, 1], or not finite, refuses the row or the step. The routed product
     is then held to the sink's control rule ((d), or its `control_domain`) like any control.
   - `book` receives the step's held control, not a routed one: `book` is per step, while a routed
     value belongs to a stage.
   - No ledger and no state: factors book nothing, and the routes book what they move.
5. **Fields that depend on the declaration (schema A completed).**
   - A kind may declare `declared_fields(entry)` → `KindFields(state_axes, layout_fields,
     control_fields, readout_columns)` for its structure entry. Without it, its static fields
     stand.
   - The core binds each declared kind to its entry's fields wherever it resolves a structure's
     kinds: the hooks, the types, the controls and the adapter's ownership map.
   - Classes are cached by field set in canonical order, with a deterministic name for each
     variant.
   - So a field exists only where the declaration needs it, as (j) asked: "present when any
     declared law needs it".
6. **The sink, `cells.passive_routes@1`.**
   - A route's `factors` is a list of source IDs, in declared order.
   - Where any route declares factors, the kind's entry records which routes and which sources.
     That record is value-free. The kind's fields then gain the control `passive_multiplier`
     [route], 1.0 from `control_values`, and each factored route is routed through
     `routed_controls`.
   - Each route's opening is multiplied by the slot in `rates`, `stage_term` and `readouts`.
   - Unchanged:
     - §7.5's exact booking and its scope, so the cargo routes stay exact;
     - `bound_rate`, which holds at m ≤ 1;
     - `moved_rows`.
   - FR-4's routes declare no factors, so FR-4 keeps the same entry, fields, types and programs.
     The `@2` fallback is not needed.

**Why a control slot** (FR-4/FR-5 note §16.3, kept): every hook keeps its signature, and a sink
reads only its own field. Scheduled and routed controls compose: a slot's held value may itself
follow a schedule ((l)).

**Acceptance (tests, with planted source and sink kinds under `tests.`):**
- a routed slot equals held × Π sources, a left fold, at the stage's state;
- a factor outside [0, 1] refuses the step;
- each binding refusal fires;
- with no sink, the door is absent and the programs identical;
- FR-4's kind worlds are unchanged (the pair check);
- the passive routes with a planted source:
  - at a held factor m, a route equals a route of permeability m·P, to rounding;
  - a factored cargo route keeps its exact booking;
  - `passive_multiplier` exists only where a route declares factors;
- crossrev is identical.

**As built (core-next; the API accepted by the lead, 16 November 2026):**
- **The registry:** `KindFields`, `bound(kind, entry)` (cached, one object per kind and entry) and
  the hooks `declared_fields`, `factor_sources`, `factors` and `routed_controls`.
- **The structure:** `InnerStructure.routes`.
- **@3's door:** `surface_pump_v3._route`.
  - It runs in `readouts`, `explicit_rates` and `membrane_rate`, and on the kinds' readouts in
    `observe_history`.
  - It is gated on `structure.routes`. The FR-4 pair check showed why: an absent door's
    `valid & True` alone changed FR-4's jaxpr text.
- **The checks at binding:** `_routes` (sources, ownership, slots routed twice) and
  `_check_routes` (factors traced as [len(sources)] floats, slots inside their field).
- **The sink:** `cells.passive_routes@1`'s entry is `Factored(laws)` only where a route declares
  factors; otherwise it is today's tuple of laws.

**The hooks that bound a factor's feedback (25 November 2026; CALCIUM_STORE_AND_CHANNELS_DESIGN
§6.5).** A source may have `factor_rows` and `factor_log_slopes`, and a sink `routed_rows` and
`routed_flux`: both or neither of a side. Binding pairs a slot's rows with the rows its sources read
into `InnerStructure.loops`, and the stage adds |J| |d ln f / d ln n| / n, J at the routed control,
at both ends of every row the slot moves. @3 has the sink's two for its channel slots, and
`cells.passive_routes@1` for factored declarations. Refused by name: one hook of a side without the
other; a sink with neither, where a loop would close; and, beside a loop, an operator that opens,
closes or retires slots.

#### (o) insertion@2's gate at opening (item 4; options for a ruling, 16 November 2026, before code)

**What it must do** ((j), "A padding artifact kept for bitwise identity"):
- A closed or not-yet-open channel slot carries code 0, Kv1.5's, and keeps its gate update.
- The partition and replacement set the gate when they open a slot. Insertion@2's onset does not.
  So a gated population on an onset patch would start from the gate the artifact evolved while
  the patch was closed.
- `membrane_insertion_v2.check_onsets` refuses such populations today ("later work"). So no
  accepted world reaches the inherited gate, and the fix is a precondition for lifting that
  refusal, as its own gated change.

**What constrains it** (read in code at core-next):
- Insertion@2's `event(state, control, p, *, xp, view)` is static per operator class: it gets no
  declaration. Anything it does per definition comes from its layout or state.
- The declared initial gate exists only in the inner model's initial state.

**Option 1, recommended: set at opening, in insertion@2.**
- At binding, `initial_values` gets the inner initial state. Insertion@2 binds two layout fields:
  `insertion_onset_channel` [channel], marking a population whose patch is an onset patch, and
  `insertion_onset_gate` [gate, channel], its declared initial gate.
- Its event sets `channel_gate = where(opening, onset_gate, channel_gate)` for the populations
  whose patch opens at that event. `channel_gate` joins its STATE_RESETS.
- A population on an onset patch therefore starts at its declared gate at the onset, however long
  its patch was closed: the declared gate is the population's gate at its opening.
- **Programs:** every insertion@2 world (crossrev's division set: division_furrow,
  division_quartered) gains two layout leaves and one select. This is an intended program change.
- **Records:** bitwise unchanged. No accepted world has a population on an onset patch, so the
  mask is all false and the select returns the old gate exactly.
- **Ownership:** the operators stream's file (`operators/membrane_insertion_v2.py`).
- **Cost:** about 0.5 day.
- **Test:** a planted population on an onset patch, with check_onsets' refusal lifted inside the
  test only. Its gate after the onset equals its declared gate whether the patch opens early or
  late, while today's code would give the artifact's.

**Option 2: gates frozen while closed, in @3.**
- `stage_gates` keeps a closed slot's gate: `where(channel_active, updated, old)`, on structures
  with `padding_fill`.
- A slot never opened keeps its declared gate. A slot that closes keeps its gate from closing.
- The artifact goes for every closer, and the code-0 kernel's padding result is no longer read.
- **Programs and records:** every closer world (partition, replacement, insertion@1 and @2, so the
  division and replacement worlds) changes its program and its closed slots' gate records. That
  is not physics, but it is a results-gate difference to accept, world by world.
- **Cost:** about 1 day, mostly evidence.

**The recommendation is Option 1:** it changes no record, it is local to the one opener that lacks
the write, and it keeps the partition's and replacement's own rules. Option 2 is the cleaner
long-term model, but its records change across the closer worlds. It can follow when the padding
fill is retired (the "explicit absent marker" of (b)).

**The lead's ruling (16 November 2026): Option 1, built by the core** (no operators owner is
active), with check_onsets' refusal kept.
- **The semantics, a declared rule of insertion@2:** a channel population on an onset patch starts
  at its declared initial gate when its patch opens, however long the patch stayed closed. It is
  not a claim about the state of channels that vesicles deliver.
- **Lifting the refusal** is a separate, later change with its own evidence.
- **Option 2** stays the cleaner later alternative, if closed-slot drift ever reaches a record
  that matters.
- **As built (core-next):**
  - `membrane_insertion_v2.onset_gates` binds `insertion_onset_channel` and
    `insertion_onset_gate`;
  - `opened_at_onset` names the populations whose patch opens at the step's onsets;
  - its event writes their gates, and `channel_gate` is in its `STATE_RESETS`.
- **The test** (`tests/unit/test_insertion_gate_at_opening.py`): a planted population, onset
  early and late, starts at its declared gate whatever the padding drifted to; the write is idle in
  today's worlds; the refusal stays.

#### (p) Ledger lists read from the implementation object (item 5; designed 16 November 2026, before code)

**What it must do.**
- A model's ledgers are today the shared literals of @1, `surface_pump`:
  - `LEDGERS`, ten names in `balances()` order;
  - `LEDGER_DIAGNOSTICS`, their residual diagnostics;
  - `ledger_limits`, their bounds;
  - `ENERGY_RTOL`, the energy ledger's tolerance by solver.
  `DEVICE_CHECKS` and `DEVICE_DIAGNOSTICS` are built from these lists.
- The shared check paths read these as module globals:
  - `surface_pump.checked_rows`, the host check of @1, @2, @3 and the composite. It reads
    `LEDGER_DIAGNOSTICS`, `ledger_limits` and `ENERGY_RTOL`, and takes `limits[5]` for the
    global-charge ratio.
  - `surface_pump_checks.row_checks`, the device check, which takes `bounds[5]`.
  - @2's and @3's `DEVICE_CHECKS = first.DEVICE_CHECKS`, and `limits=first.ledger_limits` in
    their `device_checks`.
  - @3's `channel_magnitudes`, which takes `first.LEDGERS.index(...)`.
- The composite already reads `inner.LEDGERS`, `LEDGER_DIAGNOSTICS`, `ENERGY_RTOL` and
  `ledger_limits` from its inner object. Its host check, though, calls `inner.checked_rows`, which
  reads @1's globals, and checks its operators' ledgers after that.
- (k) kept the literals for D176's round: reading them from the object changes @1's and @2's
  shared check code, so it is a D148 change, made after the landing.
- **The goal ((k)):** every model object exposes its ledger lists, and the shared paths read the
  lists from the object they are given. A later kind with a new conserved quantity then adds a
  ledger to its structure's object by declaration, and no check function changes.

**The design.**
1. **The ledger protocol: four names on every model object.** They are `LEDGERS`,
   `LEDGER_DIAGNOSTICS`, `ledger_limits` and `ENERGY_RTOL`.
   - @1's module defines them. @2's and @3's modules carry `ENERGY_RTOL` from @1 and gain the
     other three as aliases of @1's objects.
   - @3's `InnerImplementation` sets them from its structure (`ledger_lists(structure)`). Today
     these are @1's own objects, so `impl.LEDGERS is surface_pump.LEDGERS`.
   - The adapter forwards them from its implementation.
   - The composite's object keeps its own: inner's, then its operators'.
   - No new type is needed: the protocol is just these names, the ones the composite already
     reads from its inner object. The two ratio diagnostics keep their ledgers by name, "energy"
     and "global_charge".
2. **The shared paths take the object.** The new keyword is `ledgers`:
   `checked_rows(..., ledgers=None)` and `row_checks(..., ledgers=None)`. They read the diagnostic
   names, the bounds function and the tolerance from it. `None` means @1's module, so every
   caller that passes nothing makes today's call.
   - `limits[5]` (host) and `bounds[5]` (device) become the position of "global_charge" in the
     object's `LEDGERS`. That is a Python-level index, so no program changes.
3. **@3 reads its own object.**
   - `check_values` and `device_checks` pass `ledgers=` the structure's object.
   - `channel_magnitudes` takes its indices from the structure's `LEDGERS`.
   - `DEVICE_CHECKS` and `DEVICE_DIAGNOSTICS` become the object's attributes, built from its
     lists: ("domain", *LEDGERS, "dissipation") and the max_ names.
4. **The composite** passes `ledgers=self.inner` to `inner.checked_rows`, so the inner lists come
   from its inner object, not from @1's module. Its operators' ledgers stay its own, checked after
   as today.
5. **Unchanged.**
   - The lists' values and order: every object's lists are today's tuples, and the same objects.
   - `device_check_constants`, which reads `ENERGY_RTOL[solver]` (the same table everywhere).
   - The validation tools that read `first.LEDGERS` (@1's lists stay where they are).
   - The in-place guard's quiet host check (`inplace_fix_guard._quiet_host_checks`) gains the
     `ledgers` keyword.

**What a later kind declares (the seam this prepares; a sketch, not built in this item).**
- A `ledgers(declaration)` hook returns ((ledger, diagnostic), ...).
- The kind's `ledger_terms` gives each ledger's value under its own name, beside today's roles.
- A `ledger_bounds(row, p, tol, steps, *, xp)` hook returns their bounds.
- The structure's object then appends these to its lists (`ledger_lists`), `balances` to its
  values and `ledger_limits` to its bounds. `checked_rows`, `row_checks`, `DEVICE_CHECKS` and the
  windows' failure codes take them with no edit.
- **Option A (recommended):** this item builds the protocol and the reads only. The hook follows
  with its first consumer, a kind with a conserved quantity that is not one of today's ten.
- **Option B:** the hook now, with a planted kind under `tests.` that declares a neutral conserved
  quantity and its ledger. This costs about 0.5 day more, and the hook's shape would be fixed
  before any real consumer exists.

**The lead's ruling (16 November 2026): Option A.**
- Build the protocol and the reads now. The kind's own ledger hook waits for its first real
  consumer: probably finite fuel with the transporter's fuel rows, queued right after the landing.
  Its shape is then fixed against real needs.
- This follows D180's rule of staging by consumer. The sketch above is the finite-fuel owner's
  starting point: `ledgers(declaration)`, values under their own names in `ledger_terms`, and
  `ledger_bounds`.

**As built (core-next):**
- `surface_pump.checked_rows(..., ledgers=None)` and `surface_pump_checks.row_checks(...,
  ledgers=None)` read the object's lists. The global-charge bound is found by name in its
  `LEDGERS`, and `None` is @1's module, today's call.
- @2's and @3's modules alias @1's `LEDGERS`, `LEDGER_DIAGNOSTICS` and `ledger_limits` beside
  `ENERGY_RTOL`. @2 passes its own module.
- `surface_pump_v3.ledger_lists(structure)` gives the four names, with `DEVICE_CHECKS` and
  `DEVICE_DIAGNOSTICS`; today these are @1's own objects for every structure.
  - The implementation object carries them, and the adapter forwards them.
  - `check_values`, `device_checks` and `channel_magnitudes` read them.
- The composite passes its inner adapter to `inner.checked_rows` and itself to `row_checks`.
- The in-place guard's quiet host check takes `ledgers`.
- The tests are in `tests/unit/test_ledger_lists.py`.

**The kind's hook, as built (E, CORE_SEAMS §7.3; the lead's ruling (b) of 19 November 2026).**
- `structure(model)` reads each declared kind's ledgers once, through the kind contract's
  `kind_ledgers(kind, declaration)`, into `InnerStructure.kind_ledgers`: ((kind ID, ((ledger,
  diagnostic), ...)), ...) by kind ID, names only. A malformed result, or a name one of @1's ten
  ledgers or their diagnostics holds, refuses the definition, naming the kind.
- With no kind ledger, `ledger_lists` returns @1's own objects, so today's programs are unchanged.
  Otherwise each kind's ledgers follow @1's ten: their names and diagnostics, their bounds
  through `ledger_limits` (the kind's `ledger_bounds`, a function of the row and the layout at
  check time) and their values through `balances` and `device_balances` (the kind's
  `ledger_terms` under the same names).
- At binding, a declared ledger its `ledger_terms` does not value is refused, and so is a
  `ledger_bounds` that gives one bound per ledger in another number or shape.
- The composite builds its lists from its inner model's, so it takes the ledgers with no edit.
- The tests are in `tests/unit/test_kind_ledgers.py`: a planted producer's adenine moiety on both
  check paths and through a composite, its off-by-one plant, and the refusals.

**The D148 case.** This is an in-place change to shared qualified code, `checked_rows` and
`row_checks`. Nothing should change, so the criteria are checked as "identical":
1. Programs: crossrev, all eight sets, and the kinds pair, against 82d3d67a's saved outputs, the
   head after the raw-sum fix (3c10b833's differ by item 4): every jaxpr, binding and constant
   identical.
2. Records:
   - `validation/tissue/inplace_fix_guard.py` dump at 82d3d67a and at the change, then
     compare. The parts are `pump` (@1's and @2's registered worlds, RK4 and IMEX), `base`,
     `injection`, `qualification`, `dumps` and `cohorts`. Every state field, observation, `max_`
     diagnostic and device row-check result must be identical, the ledger diagnostics included.
   - G1, bitwise 113 of 113 against c1's merged save.
3. Verdicts and registered numbers: unchanged, as a consequence of 2. There is no ledger-level
   change to list.
4. The crossrev baseline needs no renewal, since nothing differs.

**Acceptance (tests).**
- Each model object (@1, @2, @3 with and without kinds, a composite) exposes the four names, with
  values equal to today's tuples.
- A planted object (test-local) with one extra ledger: `checked_rows` and `row_checks` check it
  against its own bound, report its own diagnostic, and fail with its name. They read the object,
  not @1's literals.
- `ledgers=None` is today's result, bit for bit, on @1's and @3's test worlds, host and device.
- Tiers 1+2 pass against the record.

### 7.5 Exact heat booking: one declared booking, designed once (the lead's ruling, 15 November)

- **Why.** Today a route's heat is the tableau's quadrature of its dissipation rate (Σ J Δμ̃ at the
  stages, with the explicit weights). It matches the free-energy decrease only within the energy
  ledger's tolerance, and the residual grows where a route moves a large share of a small pool in
  one step. Three consumers meet that limit:
  - the passive law's trace start (the Syn3A audit's probes P0b–P0d; §11);
  - the implicit patch: the charged-patch test found that the energy ledger, not stability, binds
    the explicit route near dt × G/C_b ≈ 0.05 ((g) 4 of §7.4);
  - FR-10's onset at a dosed bath's face (its resolved-start rule).
- **The booking, `exact_free_energy_heat@1` (name S).** Routes that declare it book, per step, the
  exact decrease of the stored free energy that their moves cause, with no rate quadrature:
  - **exact per row, not per route.** A row (a species at a node) may be moved by several routes in
    one step, for example FR-5's transfer and damage pore across one patch. Its chemical term is
    nonlinear, so terms anchored at the start amount, one per route, do not sum to the row's
    change. The booking therefore takes each row's exact change once: ΔG_row, from @3's per-row
    term (`species_chemical_free_energy_pJ`, the per-row form of `balances`' own term) between the
    row's start and end amounts. That closes the ledger to rounding without forming a difference of
    bulk terms;
  - **the split between routes, declared:** each route moving the row takes the share μ̄_row ×
    (its transfer at that row), with μ̄_row = ΔG_row/Δn_row the row's divided-difference potential
    over the step (its limit, the potential at the start amount, when Δn_row = 0). The shares sum
    to ΔG_row exactly, as in D152's per-route hybrid and FR45's kernel (`divided_potential_RT`). A
    route's heat is minus the sum of its shares at its two ends;
  - **version 1's scope (ruled):** neutral rows only (the passive law is valence 0), and only rows
    that exact-booked passive routes alone move. This is checked at binding, from `moved_rows` and
    the operators' `moved_in_step`. A passive route on a row that a pump or a tableau-booked route
    also moves keeps today's tableau booking and checks: there μ̄ would average over a change the
    route did not make. The accepted cost: FR-4's acidified compartment, pumped and leaked, keeps
    its energy-ledger step limit (dt·G/C_b ≈ 0.05, declared by its worlds) until a pump booking by
    the same divided differences is designed, a later item;
  - **@3's faces (D280):** a definition may pick the same booking for its faces, under the same
    version-1 scope (CORE_SEAMS_DESIGN §6.5);
  - **charged species (outside version 1):** the electrical part is the capacitor energy's change, exact for the
    linear capacitor through the step's mean patch voltage (V̄ Δq), split in the same way. The
    implicit patch, the first charged consumer, fixes it in its own module (FR45's
    `patch_booking_pJ`);
  - **sign and refusal, ruled for version 1 (15 November)** (after FR45's probe, two rounds, and
    the advisor's review; this replaces f81f213d's proposal and the earlier group rule, and R3's
    clamp is dropped):
    - **booking:** each route books its exact divided-difference share of each row's exact
      free-energy decrease. No clamp, no scaling, no trapezoid, and no groups;
    - **refusal:** a step with any negative raw share is refused, with the reason "negative exact
      share: step-bound breach". That covers a negative row decrease too, since the shares sum to
      it;
      - **Amended 17 November 2026 (the sign rule's floor; the lead's four conditions):** a share
        is refused only below its floor, −16 × eps × (|μ̄_in| + |μ̄_out| + 2)·|m|, in pJ (the
        share's 1e-3 RT). That is the raw-sum check's factor on the share's own terms, |μ̄| |m| at
        each end, plus its potentials' evaluation rounding, 2|m| (added the same day: the band
        below). A share within its floor is booked as computed, with no clamp, so every row's
        raw sum and the energy ledger close exactly as before.
      - **What it was refused at:** the gap-junction replication's line of 25 cells, between
        identical healthy cells. In the step measured, two miR200 routes moved 4.8e-20 fmol each,
        below the amounts' resolution (about 7e-18 fmol, so no stored amount changed), against a
        potential difference of 4.44e-16 (2 eps, one ulp at ln c ≈ −2.3). Each share was
        −2.1e-35 RT fmol, about 40 times inside its floor
        (`/mnt/workspaces/Cells/gap-junction-20261117/probes/neither-fail-01/`).
      - **The band near 1 mM, closed the same day (the lead's call; FR-19's follow-up):**
        - **Why it existed.** With the share's own terms alone, the floor scaled with |μ̄|, but
          the potential difference keeps the ulp of ln c + 1: the kernel forms μ̄ as
          ln(n0/V) + p(x) − 1, with p near 1. So that floor closed as c → 1 mM (μ̄ → 0). On the
          closed pair, a rounding-level share was refused within about 1% of 1 mM for a 1-ulp
          lead, 5% for 4 ulp and at least 10% for 16 ulp
          (`/mnt/workspaces/Cells/passive-share-tolerance-20261117/probes/band.json`).
        - **The fix.** The floor's 2|m| carries that evaluation rounding, so at 1 mM the floor
          is 32 eps |m|. On the same plant, all 47 rounding-level cases of the table are admitted
          (leads of 1–16 ulp, 1e-4 to 100 mM), the worst at half its floor (1 mM, 16 ulp)
          (`/mnt/workspaces/Cells/passive-share-band-20261117/probes/band.json`).
        - **What stays refused.** At 1 mM a share at twice its floor is refused, and so is one a
          million times below it. Steps admitted before are unchanged, since the floor only
          moved down (tests/unit/test_passive_share_floor.py);
    - **why a share can be negative at all:**
      - Under ARS(2,2,2) the explicit weights (δ, 1 − δ), δ < 0, can reverse the applied transfer
        against stage rates of one sign.
      - For a neutral row the share is ≥ 0 whenever the applied transfer and both end affinities
        agree in sign: μ̄ is the mean of μ over the row's amount interval, and those intervals are
        ordered when both end affinities are.
      - Reachability is not proven. With one route per pair, FR45 shows a negative share is
        unreachable under dt·L ≤ 1. With several routes at a node, one route's end affinity can
        still reverse, though the share stayed positive in FR45's example (a chain a–b–c with a
        small pool c).
      - So version 1 fails loudly if it ever happens. If real runs show refusals, R3 is revisited
        with that evidence;
    - **the raw-sum check, per row:** |Σ shares − ΔG_row,exact| ≤ 16 × eps × (own + inputs).
      Here own is the row's own terms, |G0| + |G1| + Σ|μ̄ m|, and inputs is their inputs'
      rounding, |μ̄| (|n0| + |n1| + |Δ0| + |Δ1| + Σ(|T0| + |T1|)). This was amended on 16
      November 2026; the analysis is below ("The raw-sum bound's inputs"). The bound as first
      built had own alone, so FR-5's arm R was refused at rounding.
      - At the probe's case-4 magnitudes that is about 1.3e-14 pJ. The honest sum, 7.5e-15 pJ,
        passes it, and a planted sign flip, 1.84e-3 pJ, fails it.
      - The factor is confirmed by a test at implementation;
    - **the step bound:** the passive law declares dt × L ≤ 1 as its bound term, finding 3's z = 0
      term for its routes (§7.4 (i), §13.6). L = 1e15·PA·(1/V_a + 1/V_b), summed over the routes
      at each node. A dt-study criterion covers accuracy. Exact booking closes the ledger up to
      h = 2, so it no longer signals an overshoot by itself;
    - **for the run view:** route heat stays monotone to rounding, since a step with a share below
      its floor is refused (a share within it moves a route's heat by at most 16 eps of its
      scale, (|μ̄_in| + |μ̄_out| + 2)·|m|). A route's value is an exact attribution of its rows'
      decrease (the divided-difference split), not a separately measurable quantity.
  - **The probe's numbers.** They are recorded here because they exist only as data and hand-back
    text: FR45's `fr45/booking-probe/` (`HANDOFF.md`, `results.json`, `round2.json`).
    - R1 (the share, else the trapezoid) missed the ledger's allowance by 48× to 480× wherever its
      trapezoid fired.
    - R3's clamp fired once, in case 4 at hγL = 0.6: raw shares −9.20e-4 and +2.727e-3 pJ against
      the group's exact decrease of +1.806e-3 pJ. The honest clamp was 51% of the decrease.
    - The raw shares summed to each row's exact decrease within 7.5e-15 pJ.
    - A planted sign flip on the minor route missed the exact sum by 1.84e-3 pJ, so the raw-sum
      check catches it, where the clamp would have absorbed it.
- **Static and declared.** Only a route law that declares the booking computes it. Today's routes
  (the membrane and junction constant-field routes, the channels, the faces) keep the tableau
  booking, so every existing program is unchanged. The booking needs the step's start amounts and
  the route's applied transfer, both of which `imex_step` already holds (`applied`).
- **When.** It is implemented with its first consumer, the passive law's insertion point, and
  reused by the implicit patch and FR-10's onset. A tighter face-free bound constant than the
  ordinary one belongs with it (§13.6).
- **Built (core-d172 6a43f189), with its acceptance as tests** (`tests/unit/
  test_passive_routes_kind.py`, the closed pair being FR-1's face-free world W as plain @3, k =
  100/s at dt = 1 ms): the pair relaxes as REF's closed form says and its heat is the engine's own
  free-energy decrease to 1e-10; a trace start is admitted while the tableau's booking of the same
  run fails the energy ledger; the honest raw sums stay within the factor 16 and a planted sign
  flip on a minor route fails; an uphill step's negative share is refused; a route on a row
  another route moves keeps the tableau's booking bitwise; binding refuses a charged species and
  a carrying host. On the device and host path a refusal is the step's (the booking's validity);
  the reason's text is the module's `NEGATIVE_SHARE`.
- **The raw-sum bound's inputs (16 November 2026; FR-5's arm R; the lead's ruling, derived here
  before code).**
  - **What failed.** FR-5's arm R starts from the engine's 1800 s state (fr45-next d9323e1a,
    `fr45/pipeline/fr5-raw-sum-diag/`). About 1 s into the injury it was refused ("trial/endpoint
    domain failure"); every other check passed at that state.
    - Over the release (1.9–4.0 s, 4200 steps), 459 steps exceeded the bound as built, by up to
      2.80 times.
    - After the burst the lumen holds about 1.5% of its X. Its stored amount is a small difference
      of its reference (0.0654 fmol) and its increment (−0.0644 fmol), and the routes' cumulative
      transfers are of the same size. The bound's own terms, evaluated at the small current
      amount, fall below the rounding those inputs carry.
  - **The analysis.** For an exact row (a species at a node) over one step, with u = eps/2:
    1. **The amounts.** The booking forms n_k = reference + Δ_k (`_amounts`), rounded relative to
       its result, so |n_k − (reference + Δ_k)| ≤ u|n_k|. The reference does not enter on its
       own.
    2. **The accumulators.** The step forms Δ_1 and each exact route's cumulative transfer T_1 by
       adding the tableau's terms one at a time onto Δ_0 and T_0 (`surface_pump._combine`). Each
       addition rounds to its running sum.
       - The last stage of ARS(2,2,2) has q = 2 explicit terms; imex_euler has q = 1.
       - Its implicit terms are exactly zero at an exact row, because exact routes alone move it,
         and adding zero is exact.
       - So the increment's accumulated rounding is at most q·u·max|Δ|, and each route's at most
         q·u·max|T|.
    3. **The terms.** Both accumulators add the same stage fluxes: the kind's node changes and its
       transfer derivative. So their terms agree to about u·Σ|m|, the scatter over several routes
       and the weights' products.
    4. **The mismatch.** The recorded net transfer N = Σ ±(T_1 − T_0) and n1 − n0 therefore differ
       by at most u(|n0| + |n1|) + q·u(max|Δ| + Σ max|T|) + c·u·Σ|m|.
    5. **The residual.** The divided potential is exact for the stored amounts:
       μ̄(n1 − n0) = G(n1) − G(n0). So Σ shares − ΔG = μ̄(N − (n1 − n0)) plus the evaluation
       rounding of μ̄, G and the products. The evaluation rounding is the bound's own terms:
       |G0| + |G1| + Σ|μ̄ m|, with the u·|n|(|ln c| + 1) of evaluating G covered by
       |G| + |μ̄||n|.
    6. **The bound.** |Σ shares − ΔG| ≤ 16 eps [|G0| + |G1| + Σ_i |μ̄ m_i| + |μ̄| (|n0| + |n1| +
       |Δ0| + |Δ1| + Σ_i (|T_i,0| + |T_i,1|))], where i runs over the exact routes at the row.
       - 16 eps = 32u, against the 1 + q ≤ 3 roundings the inputs carry. Both ends' magnitudes
         enter, so the margin is at least 10 times. The factor is unchanged.
       - Where the inputs are small (a fresh start), the bound is today's.
  - **Measured on the fix's tree** (d9323e1a with the patch; `core-next-20261116/rawsum/`), over
    FR-5's arm R release (1.9–4.0 s, 4200 steps, no factor relaxed):
    - **Ratios:** the derived bound's largest is 0.051, with 0 steps over. The bound as built is
      exceeded by 459 steps, by up to 2.80. The FR lane's candidate, which keeps a |reference|
      term, also gives 0.051.
      - The candidate is looser where the inputs dominate: 0.022 against 0.027 at the step the old
        bound fails most.
      - The candidate is not wrong, only not derived: the reference rounds relative to the sum it
        forms.
    - **The exact decomposition,** with Fractions of the stored floats:
      - the amounts' part reaches 0.93 of u(|n0| + |n1|);
      - the accumulation part reaches 0.89 of its q = 2 ceiling, so two roundings, not one;
      - |μ̄| times the mismatch accounts for the residual, a median 92% of it.
    - **The run:** arm R completes its 10 s on the host and vector paths of the development
      world. Its records match R-transfer as with the factor relaxed: X_L within 3.8e-5 of X's
      budget, pH within 2.9e-9.
      - The declared world is not admitted for FR-5 at d9323e1a: FR-1's operator refuses the
        lumen's charge anchor at binding. That is not the bound.
  - **The teeth (accepted by the lead, 16 November 2026).**
    - The bound scales with the stored fields' precision. The smallest unrecorded transfer it
      refuses at a row is bound/|μ̄|, about 16 eps (|n0| + |n1| + |Δ0| + |Δ1| + Σ(|T0| + |T1|))
      in fmol. It grows with the increments and cumulative transfers: that is the resolution limit
      of a cumulative field, not a weakening by choice.
    - **Its scaling.** The threshold rises in proportion to the cumulative transfer, so roughly
      with elapsed steps. A route that carries a steady m per step has |T| ≈ K·m after K steps,
      so the threshold relative to m is about 16 eps × 2K ≈ 7e-15 K. That is about 7e-9 of a
      step's transfer after 10⁶ steps.
    - **Measured today:** over FR-5's release it is a median 1.2e-15 fmol, 6.2e-10 of the step's
      transfer.
    - In the test's drained pair it is 2e-15 fmol, 6e-10 of the step's transfer. There the minor
      route's planted sign flip is refused, and so are unrecorded transfers of 1e-6 and 1e-8 of
      the step's.
  - **What changes.**
    - **Programs** (an intended change, accepted): every world that declares
      `cells.passive_routes@1`, since its `book` traces the bound and exactness is a layout value.
      That is FR-4's (the proton leak, with no exact route, where the term is masked) and FR-5's.
      The kinds pair records +32 equations in the checked step of fr4_development, fr4_declared
      and fr5_t_development, none removed, with rhs, device checks and bindings identical.
    - **Unaffected:** no G1 world and no crossrev world declares a kind.
    - **Records:** FR-4's declared world gives the same records, bit for bit.
  - **Tests** (`tests/unit/test_passive_routes_kind.py`):
    - 300 honest steps in the drained, large-increment pair are all admitted. At 17a3863b the
      first of them was refused.
    - In the same state the planted flip and the unrecorded transfers are refused.
- **Acceptance, with its first consumer:**
  - on the closed pair each row's raw shares sum to its exact decrease within the raw-sum check,
    with the factor 16 confirmed by a test;
  - a trace start (1e-12 mM) is admitted;
  - a planted sign flip on a minor route fails the raw-sum check;
  - a step built to make a raw share negative is refused with "negative exact share: step-bound
    breach";
  - a passive route on a pumped row keeps today's tableau booking, bitwise;
  - binding refuses no world of today's.

## 8. Scoped composition: door S's runtime merge (list (a))

**The authority for door S is now [SCOPED_COMPOSITION_DESIGN.md](SCOPED_COMPOSITION_DESIGN.md)**
(the integration owner's, on main at 7b9aeb1): its declarations, admission rules, runtime merge,
defaults that reproduce today, and tests T1–T8. This section keeps the sketch it started from,
with D176's two corrections entered; where the two differ, that note applies.

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
| Read mode | **Three, after D176:** `reference`, an immutable anchor read as data from the layout (an anchor or an energy reference), correct whatever any changer does; `fixed`, the declared value used as the physical value, an assumption that the field is unchanged on those slots (today's `CONFLICTS_VIEW`, whole-field); `current`, the accumulated view at its stage. D176 keeps the first two apart |
| Changed slots | The slots it may change. Static, from the definition |
| Contribution | `replace`, `add` or `multiply` |
| Stage | When it is evaluated: at the step's events, in a split half-step, at the view before the inner step, or at observation |

**Admission (host, at the definition):**
- Two providers' changed slots must be disjoint, unless both declare the same commuting
  contribution (`add` with `add`, or `multiply` with `multiply`). The coupling factors on controls
  already multiply in declared order, which is the precedent.
- A `fixed` read must not intersect any changer's slots, at any stage. A `reference` read has no
  constraint (D176).
- A `current` read is satisfied by every provider evaluated before its stage.
- Anything else is refused with the overlapping slots named.

**The runtime merge** (the adapter's `view`):
- The accumulated view starts from the bound layout.
- Each provider returns values for its own slots only. The composite applies them in declared
  order with a static scatter: set for `replace`, add for `add`, multiply for `multiply`.
- **Order independence, narrowed (D176):** disjoint provider writes are invariant under
  reordering. Overlapping contributions (`add` with `add`, `multiply` with `multiply`) have a
  fixed evaluation order, the declared one, recorded as a chain; they are not claimed
  order-free at rounding. The numerical split order is preserved: permutation tests reorder the
  merge, never the split parts.
- A provider whose slots cover a whole field reproduces today's replacement bitwise.

**Changed slots feed §9:** only a field input with changed slots puts the field refresh into the
program (§9.1).

**Acceptance** (ARCHITECTURE.md):
- two providers on disjoint slots compose identically in either declaration order (bitwise);
- an overlap is refused unless a combination rule applies;
- each reader sees the merged values at its declared stage.

**The integration case: bath → uptake → owned compartment → reaction.** **In R (D176):** FR-1's
operator is on main, so this is a real acceptance world of door S, reusing FR-1's compartment
identity map (`compartments.identity_map`); SCOPED_COMPOSITION_DESIGN.md §5 and §7 (T5) specify it.
- FR-10 doses a held bath (`replace` on the bath's slot, at its event).
- D150's exchange takes up from the finite node that a face joins to the bath, into the cell, and
  exports into FR-1's compartment.
- D152's reactions run in the compartment. Their `fixed` reads are the compartment's and cells'
  slots, disjoint from the bath's.

**Its checks:**
- material closes across all four, by D150's and D152's own records;
- the requester's first admissible delivery world runs with reactions instead of its turnover
  workaround (FEATURE_REQUESTS.md, FR-1);
- the same world with the event-only bath schedule first and last in the declared order gives the
  same bits, every split part keeping its order.

**Effort** (**S**): 3–4 agent-days, the integration owner's.
- The contract, the adapter and the composite's slot-level admission and merge.
- **Slot declarations, narrowed by SCOPED_COMPOSITION_DESIGN.md §5:** defaults reproduce today
  (`replace` on all slots for every provider, `fixed` on all slots for every `CONFLICTS_VIEW`
  field). R narrows only what the integration case needs, the bath schedule's changes and D152's
  reads; every other operator keeps the defaults until its owner narrows it.

## 9. Ownership, solver invalidation and compartment identity (list (b))

### 9.1 Three things kept apart (B6: with its first consumer, unless moved into R)

Today's column is from `pump_composite_adapter` (`FIELD_INPUTS`, `refresh_field`,
`check_field_inputs`) and `membrane_state.VIEW_FIELDS`.

| Concept | Today | Once it lands |
| --- | --- | --- |
| Owning a membrane population (abundance, sites) | Membrane state provides `channel_abundance`, and its provision of `membrane_capacitance` makes the world a field-input world | An owner declares the population fields it changes; abundance is not a field input |
| Changing geometry or capacitance | Any provider of a field input | Only a mechanism whose **changed slots** include a field input (§8) |
| Invalidating a factorization (the field refresh) | Every step, by value, once any field input is provided; the 64-node cap applies | Only where a field input has changed slots. The refresh and the cap are statically absent otherwise. Option (b) of the v2 design §3, epochs, stays available |

**Acceptance** (ARCHITECTURE.md):
- an occupancy-only world with fixed field inputs has no refresh in its program (crossrev);
- a capacitance-changing world has it, and its view-capacitor terms close;
- ownership-changing operations update the declared resources or refuse.

FR-3's separate owner stays as accepted.

### 9.2 Compartment identity as a host-side map (B2)

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

**Effort** (**S**): 2–3 agent-days for §9.1 and §9.2, when they land with their consumers (B6, B2).
Not in R's total.

## 10. Material identity and fuel (the representation decided: F2, D176)

### 10.1 The requirement, fixed by D174

- Reactions can make and spend fuel.
- Pumps draw from those same amounts.
- Each standard chemical potential has one authority.
- Water and division get explicit interfaces later.

### 10.2 One authority for identity and standard potentials

- **Today, in code,** the coupling operator checks species identity against D150's and D152's
  declarations (`species_regulated_availability.check_identities`). D152's operator declares its own
  standard potentials in its block (`local_species_reactions@1`). FR-3's accepted design proposes
  extending the pairwise pattern.
- **After R,** species identity, background and trace policy, and each species' standard
  potential are declared once, at the definition boundary. Laws read them; none redeclares them.
- **This is what makes F2 below meet "one authority".**
- **One hole to close.** Today's pump declares its own hydrolysis free energy (`metabolism`'s
  `delta_g0_J_per_mol`). Under finite fuel that would be a second source for the same quantity.
  - The finite-fuel kind therefore takes ΔG° from the species' declared potentials and has no
    `delta_g0` of its own.
  - This note had the maintained kind keep its own ΔG°, its reservoir being external. **Superseded
    (D176; ARCHITECTURE.md, "Material identity and fuel"): maintained fuel is held inventory rows,
    not pump parameters.** A maintained-fuel pump reads held ATP, ADP and Pi rows
    (read at their declared amounts, never moved; the external resupply is the pump's supplied
    work, as today's metabolic work) with ΔG° from the registry's potentials. So both kinds have one
    authority; they differ only in whether the pump moves the rows.
  - **Today's two pumps keep their parameter form in R** (`maintained_chemical_reservoirs@1`, with
    `delta_g0_J_per_mol` and the pool concentrations as layout data). Re-expressing them as held
    rows would add three species rows to every pump world, so no existing world would stay bitwise
    or keep its species count. **The lead's ruling (15 November):** today's two pumps keep their
    parameter fuel form in R, and new fuel consumers, FR-4's pump first, use held rows from the
    start. **But a world is refused where a pump's own ΔG° and the registry's fuel rows
    disagree,** so one quantity never has two values (the check lands with the transporter kind,
    once the registry exists).
- **Effort** (**S**): identity and trace policy are part of A7 (in R). **Refreshed (D176):** the
  operators stream's species registry (`registry/species_registry.py`, approved) carries each
  species' `standard_mu_RT` at one declared standard concentration in R, host-side. So B3's field
  lands in R; D152's move to read it is one small change in its owner's file, which the lead
  coordinates. FR-4's held-row fuel reads it.

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

**FR-4's first pump needs only part of this** (refreshed, D176). It runs on maintained fuel, which
is now held inventory rows: it needs the registry's potentials (B3, above), the pump law's read of
its cell's held rows (a `reference` read of rows no in-step mover touches, checked by the
operators stream's `moved_in_step`; part of B4) and one species row per fuel species within the cap.
The in-step writes, D150's refusal and the moved-by-the-step repair come with the finite-fuel case.

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

**Decided (D176): F2, with §10.2's single authority,** including the "moved by the step"
admission fix. It fixes where fuel lives for every later consumer (FR-2, FR-4's finite fuel,
Syn3A's stage 4, the molecular-to-physiology gate). The transformed-potential boundary above stays
a prerequisite of FR-4's note.

### 10.6 The species cap: one sum order, and the cost of more species (A7)

**The rule** (D165, amended by the user: "so we should increase that limit as we need!"). The cap
(`species_common.MAX_SPECIES`, 1,024 since FR-43 / D315) is raised whenever a consumer needs more species. Each
raise is a D148 change, with a guard world at the new size and a measurement of memory and step
cost.

**Today's sums over species, in code:**
- **The ledgers add species in an explicit order** (`surface_tissue.capacitor_change`, D148's
  first case).
- **Other sums use `xp.sum` over the species axis:**
  - `surface_tissue.charge_increment`;
  - `readouts`' node charge rates and membrane current;
  - the chemical energy rate;
  - `membrane_rate`'s and `explicit_rate_bound`'s z²-weighted sums;
  - `numerics/surface_imex.face_laplacian`'s Σ z² W.
- **On the host, NumPy sums 8 or more terms pairwise.** `tests/unit/test_species_cap.py` shows that
  the host's sum differs from the explicit one for a single column of 9 species, while the explicit
  host sum equals the compiled one bitwise. That is why every raise past 16 needed its own
  summation-order probe.

**In R (A7):**
- One helper sums over species as an explicit left fold, in declared species order, on host
  (NumPy) and device (JAX) alike.
- Every species-axis sum in the inner model and the operators uses it.
- A static test refuses any other species-axis reduction in those modules.
- Since every program contains such sums, the change rides in R's single results gate (§3).
- **P7 measured its effect, and it is not bitwise.**
  - **The method.** A prototype replaced jax.numpy's sum over the species axis with an explicit
    left fold in declared order (62 folded sums in each IMEX step, 351 in the RK4 step), in P2's
    seven worlds.
  - **Values move at rounding in six worlds.** In five of them only ledger accumulators moved:
    reservoir work, membrane and junction heat, by 1–4 ulps, from the first rows. The physical
    state stayed bitwise.
  - **In the generic cell through an action potential,** gates, transfers and the electrode
    ledger moved too, from row 10, by up to 36 ulps (gates) and 54 ulps (the electrode charge).
  - **Unchanged:** the 127-cell sheet, and the Jacobians at the initial state in both worlds
    where they were taken.
  - **No difference was a signed zero only.**
  - **So A7 forces §3's contingency:** G1 at a stated tolerance, and G2 in full.
- After it, a raise needs only the guard world and the cost measurement. No new order probe.

**Refreshed (D176): a measured order, then A7 last.**
- **The summation study (D176, item 3), before A7 freezes; the operators stream (the lead's
  ruling, 15 November; the core reviews).**
  - It compares serial left folds with an explicitly ordered hierarchical alternative (a pairwise
    tree in declared species order). Both are written as explicit adds, never a reduce.
  - Species counts: about 8, 16, 50 and 150.
  - It reports compilation, checked-window runtime, memory, accuracy against a high-precision sum,
    and ledger residuals. For each order, the host guard must equal the device bitwise.
  - Charge and energy quantities are evaluated consistently: one order wherever a quantity and its
    ledger meet.
  - One GPU timing arm runs in an L4 gap, which the acceptance owner schedules.
  - The choice is recorded with its measurements. A7 then lands as a mechanical sweep at the
    declared tolerance, last and alone, with the integration owner's go-ahead.
- **A7's gate manifest is the import closure of the files it changes (D176),** not a search for the
  new helper's name.
  - **Measured on the tag's source** along program-code imports (models, numerics, processes and
    coupling, with the registry and the run paths excluded as hubs; `core/import_closure.json` in
    the round's evidence folder). Modules under `models/` that reach each candidate file:
    `surface_tissue` 143, most of them older families; `numerics/surface_imex` 28 and
    `surface_pump` 27, both bringing in @1 and @2; `surface_pump_v2` 24; `surface_pump_v3` 23 (the
    composite, its operators and the thin families); `species_common` 19.
  - **So the fold's placement decides G1's and G2's scope.** A helper called only from @3's module
    and the operators, with the shared functions left as they are, keeps the manifest to @3's
    family. Changing a shared function brings @1's and @2's registered protocols into the gate under
    D148: for example the BETSE parity rungs P2 and 1 on @2, and the @1 items of E (E1, D1) and C
    (A1). Changing `surface_tissue` brings in every older family.
  - **The lead's ruling (15 November):** the helper is called only from @3's module and the
    operators, so @1, @2 and the older families stay out of G1 and G2. Where @3 calls a shared
    function that sums over species (`surface_tissue.charge_increment`,
    `surface_imex.face_laplacian`), @3's own call site takes the helper and the shared function
    stays as it is.
  - **A5 meets the same rule:** finding 3's term lives in `surface_pump.explicit_rate_bound`,
    shared with @1 and @2, so it needs their cases and a D148 record (§13.6).

**The cost model.**
- **What scales with the species count S:**
  - the state's and layout's species arrays, which are species × entities (cells, outside nodes,
    patches, junctions, faces, channels);
  - the elementwise transport work, per species per route at each explicit stage;
  - the node-charge sums, O(S × nodes).
- **What does not scale with S:** the dense node-space solves, O(nodes³), which dominate today's
  step at 825 nodes (FIELD_SOLVER_INTERFACE_DESIGN.md §1–§2).
- **Not included:** D152's reaction half-steps, which add their own work per route and site at
  Syn3A's metabolic scale.

**P6's measurements** (15 November, 01:25–01:42 UTC; the last row rerun at 04:12–04:17 UTC). The probe ran on CPU, one loaded core,
under a 2G cap. It times the inner model's compiled checked step alone, without host checks.

| World | Species | State (MB) | Layout (MB) | XLA temp (MB) | Step, median (ms) |
| --- | --- | --- | --- | --- | --- |
| 127-cell sheet (254 nodes) | 4 | 0.06 | 1.64 | 2.2 | 8.3 |
| | 16 | 0.19 | 1.76 | 2.7 | 10.3 |
| | 64 | 0.71 | 2.24 | 5.8 | 32.6 |
| | 160 | 1.76 | 3.18 | 12.0 | 82.0 |
| | 320 | 3.50 | 4.76 | 22.4 | 132.2 |
| 825-node world (225 cells, 600 outside nodes, 1,151 faces) | 8 | 0.76 | 20.9 | 32.1 | 107 |
| | 64 | 5.08 | 25.0 | 57.7 | 604 |
| | 160 | 12.5 | 31.9 | 110.0 | 1,086 (minimum 717). Rerun at 04:12 UTC: the first attempt was the designated victim of a machine-wide out-of-memory event at 01:42 UTC, below its cap |

Every compile took 55–90 s, whatever the species count. Every step was accepted.

**Per species, from these rows** (**S**, linear):
- **The sheet:** about 11 KB of state, 10 KB of layout, 64 KB of XLA temporaries, and 0.3–0.5 ms
  of step time.
- **The 825-node world:** about 77 KB of state, 72 KB of layout, and 0.46–0.55 MB of
  temporaries per species.
  - Step time is **8.9 ms per species from 8 to 64 species, and 5.0 ms from 64 to 160** (medians;
    the minima give 5.6 and 3.2 ms). The cost grows less than linearly.
  - Its 1,151 faces and 600 outside nodes carry every species, so the species work overtakes
    the dense field solves somewhere between 8 and 64 species.

**Extrapolated to the lead's three sizes** (**S**). Memory is per world; times are one CPU core,
for the checked step alone:

| Species | 127-cell sheet: memory / step | 825-node world: memory / step |
| --- | --- | --- |
| 50 | about 8 MB / 25–30 ms (3× today) | about 80 MB / about 0.5 s (4–5× today) |
| 150 | about 16 MB / 65–80 ms (8–10×) | about 150 MB / about 1.0 s (10×), between measured rows |
| 600 | about 54 MB / about 0.2 s (25×) | about 0.45 GB / about 2–3.3 s (20–30×), extrapolated from the 64–160 slope |

**On the L4 (not measured here; a stated extrapolation, S).**
- **Memory bounds the batch.**
  - The 825-node world: about 0.45 GB per world at 600 species, so roughly 50 worlds in the L4's
    24 GB; about 150 worlds at 150 species.
  - The sheet: several hundred worlds at every size.
- **Time:** today's 825-node world runs 2.28 ms per world-step at 256 worlds (PROGRESS), with the
  dense kernels at about half the device time. If the species work accelerates as the dense work
  does (about 60× from CPU), it adds 0.08–0.15 ms per species per world-step: about 10 ms at 64
  species, and about 50 ms at 600.
- **G4 replaces these numbers** with measurements in an L4 gap.

**What follows:**
- **About 50 species is affordable** on both worlds.
- **About 150 species is affordable on the sheet,** and slow on the 825-node world on CPU.
- **About 600 species (Syn3A's metabolism)** is a GPU and sparse-solver question for tissue-scale
  worlds. A single Syn3A cell, or a small tissue, is the sheet's case or smaller, where 600 species
  costs about 0.2 s per step on one core.
- **The per-species work in the 825-node world** (face weights, per-route fluxes and scatters) is
  where the field-solver interface's sparse methods and fused scatters would act
  (FIELD_SOLVER_INTERFACE_DESIGN.md §6). A7's explicit sums add no operations.
- **Each cap raise** measures exactly these columns at its new size (D165, amended).

## 11. Transport by physical contract: the passive permeation law (list (a))

**What holds today, in code and in a probe.**
- **Exchange is a driven route.** `scheduled_species_exchange@1` books the free-energy change of
  what it moves as signed work, with no heat (its module's bookings; ARCHITECTURE.md, "Transport
  laws by physical contract").
- **The inner model's constant-field route at valence 0 is passive** (the Syn3A audit, probes
  P0b–P0d, SYN3A_MINIMAL_CELL_TRACK.md §5.2–§5.3). It:
  - reduces exactly to Fick's law;
  - books membrane heat and no work;
  - has zero net flux without a gradient;
  - reverses with the gradient;
  - conserves material;
  - composes with water@1, which already counts the inner model's species rows.
- **Two gaps, both found by those probes:**
  - the heat it books matches the free-energy decrease only within the ledger's tolerance, and the
    residual grows with the start's ratio;
  - **a trace start is refused** by the energy ledger.

**The law.** A declared route law for neutral species on membranes and junctions,
`passive_neutral_permeation@1` (name **S**), whose kernel is that constant-field route at
valence 0. It adds three things the route lacks:
- **exact booking:** each step's exact free-energy change of what it moved is booked as heat, as
  D150's exchange books its own as work, so trace starts are admitted;
- **the trace and background policy** from the shared species declarations (§10.2), with
  species-scaled material floors (D150's rule; the Syn3A audit's C4);
- **finding 3's z = 0 bound term** (I0's first term, §13.6).

Today `species_common.check_impermeant` refuses such routes. Its refusal lifts only for this law,
declared.

**Its acceptance** (ARCHITECTURE.md, as the second review clarified):
- **The closed test.** A closed, fixed-volume, two-compartment test, closed for the test species,
  must show:
  - conserved material;
  - zero net flux at equal chemical potential;
  - reversal with the driving force;
  - the free-energy decrease dissipated as heat, with no externally supplied work;
  - a trace start admitted;
  - agreement with an independent reference.
- **Which topology is closed.** It is checked first, since FR-1's compartments sit in held-bath
  worlds. Two cells joined by a junction, each wall impermeant to the species, are closed for it
  even beside held baths; so is a cell with a face-free node.
- **In a held-bath world,** the total balance includes the declared reservoir work.
- **Its addition** leaves every existing program crossrev-identical, which is list (a)'s working
  case of §2.3's rules, and it passes D136's idle guard.

**Not in R:** its composition with water, which is qualified separately with the same amounts and
current volumes. That is list (c): Syn3A's S2-M1 (neutral solute and water across vesicles) and
the fourth reuse case.

**Effort** (**S**): 2–3 agent-days, with the kernel existing.

## 12. Evolution roles and step time (interfaces only: list (b))

- **Each state field declares its evolution role:**
  - continuous dynamical state (amounts, gates, regulatory states);
  - algebraic state;
  - accumulated history (transfers, heat, work, ledger accumulators);
  - discrete event state (generations, occupants, switches, crossing records).
  - The inner model declares its own fields, and the contract gains the declaration for
    operators' `STATE_AXES`. The composite checks that every field has exactly one role.
- **Conservation laws are relationships over those fields, not roles.**
  - An evolving amount may take part in several invariants: a species row is in its material
    ledger, the charge ledger and the energy ledger.
  - The ledgers keep declaring those relationships, as `LEDGERS` and the inner balances do today.
- **Exact counters declare what they count:** numerical steps or physical events.
  - The coupling operator's crossing record counts numerical steps today (its event map records
    the counter's value k, INVENTORY_COUPLING_DESIGN §7.1, item 3), and its declaration will say
    so.
  - Replacement's generation counts events.
  - Physical time and crossing-time interpretation come from the numerical plan.
- **A step context.** Each plan receives the interval [t, t + dt], its stage times, and the next
  compulsory event boundary: a dose, a regulatory write or a timed event.
  - Fixed-step runs read it and change nothing; the event-time rule (on the clock's grid, D283) stays.
  - A future coarse step must stop at that boundary.
- **Today's coarse and stationary paths handle restricted sets of fields.** They read the roles to
  refuse what they cannot treat.
- **A local implicit or substepped block** for stiff chemistry is allowed by the interface, with
  explicit exchange stages and residual checks. One law keeps one ID while its treatment evolves.
- **FR-8's acceptance is a target of FR-8's own milestone** (list (c)).
- **Effort** (**S**), when FR-8's milestone lands (B1), not in R: 1–1.5 agent-days for the
  declarations, the context and the checks; no
  algorithm. They are host-side, so they change no program.

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
  **D176 (item 6):** it is follow-on physics, not R's added law. It removes a domain restriction and
  does not by itself produce block; before a judged M3, loss of activation inside the cluster is
  separated from failure of propagation beyond it.
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

- **Opened in D176's round (15 November),** where this note had it closed in version 1: FR-4's
  rapid-buffer closure is its first named consumer, as a per-stage algebraic read (free H⁺) that the
  pump, the proton leak and the pH-band check share. Its signature and stage semantics are §7.4
  (g) 1.
- **Its shape:** declared reads evaluated once per stage on that stage's own state, before any law
  that reads them, with a loop term per reading law. The coupling note's stage factors, when a
  consumer names them, read through the same slot; its probe P3 still comes first for them.

### 13.6 The bound-term fixes (I0)

| Term | Shape | Run-time half |
| --- | --- | --- |
| Finding 3's z = 0 material term | 2 × the maximum over neutral species and nodes of Σ P·A/V over junction and membrane routes, on R5's worst cases (water's minimum volumes, insertion's largest areas) | None needed (**S**): it depends on neither openings nor concentrations. The earlier ruling named both functions; the lead decides |
| The face-free-node term | The maximum over **free** face-free finite nodes of Σ_m G_m / C_node at the declared state, with held baths, the gauge and the layout's fixed nodes excluded. **Amended 25 November 2026** (below) | None in this round, and the refusal R is not adopted (the lead's ruling, 15 November; below). **Amended 25 November 2026** (below) |

**The term's rows, amended 25 November 2026** (CALCIUM_STORE_AND_CHANNELS_DESIGN.md §8.3, with its
derivation and its limits):
- **One row per patch,** G_m / C_m, for each patch that faces a floating node (B7's free face-free
  node), in place of the node's sum, which is no bound where several patches face the node. Where
  one does, as at every compartment, the two are the same.
- **A component's representative that no face names floats too:** the fixed-node exclusion left a
  node out that the stage's operator solves like any other.
- **The cell's row and the junction term** divide by the capacitance of the cell's other patches
  alone. Dividing by its stores' as well read up to 1 + C_b/C_m times too low.
- **The run-time half exists:** the per-stage rule holds the same rows, with kinds or without
  (`surface_pump_v3.charge_rows`).
- **A cell with no other patch** that a junction or a kind charges is refused by name.

**Parking.**
- CURRENT_PLAN's "parked D148 rounds" (after GH200) are FIELD_SOLVER_INTERFACE_DESIGN §6.5's
  performance candidates. That reason does not apply to I0, which changes no program.
- **"Changes no program" is not "changes no outcome",** so P3 swept the registered and PROPOSED
  protocols' worlds at their registered dt.

**P3's result** (two runs from the same snapshot; the first was void by a probe bug in worlds with a
neutral species, and its rerun covers them):
- **Every control hit its known answer:**
  - T1 on a neutral junction: 2.000e-5 s⁻¹, as expected;
  - T2 on a face-free chloride route: 6501.285 s⁻¹, as expected, to rounding;
  - R refused the planted leak channel on the bounding patch;
  - the face-free node was detected;
  - P5's face-free gauge was excluded.
- **No world is refused, and none is bound more tightly.** The worlds swept, at their registered
  dt:
  - D150's eight arms (the RK4 ones not applicable);
  - MG0c's chains and its face-free world;
  - E07-v1's five discs;
  - the 56 worlds of the three L4 variants' protocols;
  - Track R's A4 and A5 at four steps.
- **No registered world declares a neutral permeant species.** The one free face-free world,
  MG0c's, carries no ion route there, so T2 is 0.
- **So I0 changes no registered or PROPOSED outcome.**

**Recommendation if P3 refuses nothing:** finding 3's term rides in R with the passive law (A5), with a D148 record for @1 and @2, since they share the function. The face-free term waits for P1 and FR-4 (B7).

**The lead's ruling (15 November), which supersedes that recommendation's timing:** both terms land
together, in one host-only commit with one D148 record and @1's and @2's cases, right after the
dispatch commits (§7.4 (h)).
- The face-free term is checked at the bound's **ordinary constant** (`EXPLICIT_STEP_BOUND`), not
  FR-4's 0.05, so it refuses only steps that are unstable.
- FR-4 declares its own step, 0.025 on the max-side G, confirmed by its own dt study.
- A tighter constant belongs with the exact heat booking (§7.5), which removes the energy-ledger
  limit the charged-patch test measured.
- **Built:** `119ffb74` on `core-d172` (`neutral_material_rate`, `face_free_node_rate`, read by
  `explicit_rate_bound`). Its D148 record covers @3 through P3 and @1 and @2 through the @1/@2
  sweep (`core/HANDOFF.md`, "Check D148-B7").

**The refusal R is not adopted (the lead's ruling, 15 November).**
- **What R was:** P3 tested R, the refusal of channels and pumps on a patch facing a free
  face-free node "until the run-time half exists".
- **Why not:** R would refuse FR-4's own world. Its proton pump (a transporter) and its K⁺ route
  sit on the lumen's bounding patch, which faces a free face-free node.
- **What admits such worlds instead:**
  - B7's host-only bound at the ordinary constant, with both terms;
  - each world's declared step, checked by its dt study: FR-4 declares 0.025 on the max-side G,
    FR-5 0.5 ms on the patch total;
  - the implicit patch's stage checks, when that slot comes.
- **Later, with its own record:** a run-time half for gated channels on face-free patches. This
  round does not need it, since FR-4's and FR-5's routes are constant-field routes and a
  transporter, not gated channels.

## 14. The operators in R

| Operator | What changes in R | Effort (**S**) |
| --- | --- | --- |
| Replacement@1 and @2 | Template tables keyed by declared law IDs; gate rows from the structure; formation and resets on gated junctions only; slot declarations (§8) | 1.5–2 |
| The partition and the bridge | Resets over declared gate rows; gated junctions only; closer slots (§8) | 1–1.5 |
| Water@1 and the symport | Imports through the restructured module; volume slots (§8) | 0.5–1 |
| Insertion@1 and @2, the lumens | Restructured spec types; changed field-input slots (§8, §9.1) | 0.5–1 |
| Membrane state | Its slot declarations for door S (A6). Its changed-slot rule for the field refresh is B6, later | Within A6 |
| D150's and D152's operators, the coupling operator, the bath schedule, injection | Read and changed slots (§8, A6: in R only the bath schedule's changes and D152's reads are narrowed); their identity checks consolidated into the species registry (A7, the operators stream). Compartment references (B2) come later; the registry's standard potentials (B3) land in R (§10.2) | Within A6 and A7 |
| **FR-1's `cell_owned_compartments@1`** (on main since 15 November) | Generic in code (declaration only, no program), but @3-tied in its refusal 4, which names @3's route kinds. It is already the compartment map's writer (`identity_map`) and must refuse **every** declared route kind on a bounding patch, failing closed on kinds it does not know, the passive law's included | 0.5, in R (FR45 claims `compartments.py` in its note's §11; the lead to confirm) |
| **FR-3's `site_occupancy@1`** (on main since 15 November) | Its identity check moves to the registry (A7). Its integrator duplicates D152's numerical block, recorded as a consolidation item for R (SITE_OCCUPANCY_DESIGN.md §12); its own-ledger floor needs the hook to see the layout | 0.5–1 (owner to be named; the lead may defer the consolidation, which changes no result) |

**Who needs what:**
- **FR-4's first world needs none of the @3-tied operators.** It uses the bath schedule, the
  compartments, exchange, turnover, reactions and the coupling operator, and (D176) charged
  buffering, which today's reactions parser refuses (§15.6).
- **The lifecycle gate's milestone 2** needs the partition, the bridge, insertion@2, lumen@2,
  water@1 and replacement@2, all adapted in R. Their admissions of new features (a third gate row,
  ungated junctions, transporters, finite fuel) come with their consumers.

## 15. What R must land, what it reserves, and what comes later

"Target" means decided but not yet met, in D172's round or in a later accepted milestone
(ARCHITECTURE.md, as clarified). A reserved interface does not bring its consumer's
qualification into R.

### 15.1 List (a): what R needs to land

Two tests decide membership:
- **A1–A4 meet the lead's strict test:** R's own acceptance cannot be shown without them.
- **A5 meets it only as the chosen working case.** Showing that an added law changes nothing
  needs one added law, and any law would do. The passive law is chosen because D174 expects it in
  R and its kernel exists.
- **A6 and A7 are in (a) under a second test:** they change shared traced code in every program,
  so landing them later would need a second G1 and G2.

| Item | Why R needs it | Effort (agent-days, **S**) |
| --- | --- | --- |
| A1. Today's structures as declarations, with build-time selection (§2, §7) | It is the restructure | 4–6 |
| A2. The operators tied to today's tables (§14) | They import @3's tables and gate shapes, so R breaks them | 3.5–5.5 |
| A3. The results gate (§3): the required-results list, G1, G2, the planted tests G3, the measurements G4 | R is accepted by it | 1.5–2 |
| A4. The GPU audit's tests (§5): a world without NaV1.2 traces no NaV1.2 kernel; a parameter-only change reuses `compile_window`'s executable; the host-per-row exceptions listed for the production path | ARCHITECTURE.md's targets for R cannot be claimed without them | 1 |
| A5. One added law, the passive permeation law (§11), with finding 3's term (§13.6) and its closed two-compartment test | The working case of §2.3: adding a law leaves every existing program crossrev-identical and passes the idle guard. D174 expects the law in R, and its kernel exists | 2–3 |
| A6. Door S's runtime merge (§8; SCOPED_COMPOSITION_DESIGN.md), with slot declarations for today's providers and readers and its own acceptance (disjoint providers in either order, overlap refused, merged values at each reader's stage), and its integration world, bath → uptake → owned compartment → reaction (D176) | It changes every composition's view, so landing it later would need a second G1 and G2. FR-4's pH step with buffering inside a compartment needs it (BATH_SCHEDULE_DESIGN §3.1) | 3–4 |
| A7. Species identity and trace policy consolidated at the definition boundary (§10.2), with every sum over species in one explicit order on host and device (§10.6) | Every sum over species is in every program, so changing their order later would need a second G1 and G2. D165, amended, ties it to identity consolidation in this round, so that a later raise of the species cap needs only a guard world and a cost measurement. **It moves results at rounding (P7), so with it G2 re-runs every registered protocol in full** | 2–3 |
| **(a) in total** | | **about 17–24.5**, plus CPU hours (G1 about an hour; G2 the protocols' own costs, E07-v1 about 50 core-hours in full) and an L4 gap (§5.3). D176 adds the summation study (1–1.5, §10.6) and the operators stream's registry and moved-row work (3, PLAN §7); by owner in §15.6 |

**What is deliberately not in (a):**
- **Ownership separated from solver invalidation** (§9.1). It changes only the programs of
  compositions with a field-input provider: membrane state, insertion, the lumens and the
  partition. So it can land with its first consumer (FR-2, or FR-3's later step) under a narrow
  gate over those compositions. Moving it into (a) adds 1.5–2 days and saves that later gate.
- **The integration case is no longer here: moved into (a) (D176).** FR-1's operator is on main
  since 15 November, so bath → uptake → owned compartment → reaction is door S's acceptance world
  in R (A6; SCOPED_COMPOSITION_DESIGN.md §5, T5).

### 15.2 List (b): interfaces R reserves

Specified in this note; implemented when their first consumer lands. **None of list (b) is in R's
code or in R's effort.**

| Interface | Specified here | Its consumer, which implements it |
| --- | --- | --- |
| B1. Evolution roles, counter kinds, the step context (§12) | The roles and the context's fields | FR-8's milestone (1–1.5 days, host-side) |
| B2. The compartment identity map (§9.2) | The map's fields | **Partly holds (f791294):** FR-1's operator, on main, writes it (`compartments.identity_map`), and door S's integration world reuses it in R. Laws addressing "S in compartment C" come with FR-4 and FR-5 |
| B3. Standard potentials at the definition boundary (§10.2); identity and trace policy are A7 | The field | **Lands in R (D176):** the operators stream's registry carries `standard_mu_RT`. Read first by FR-4's held-row fuel, then by the fuel case and D152's reading change |
| B4. Laws' stage reads and loop terms (§7.2) | The law declaration's fields; **the slot, §7.4 (g) 1 (opened, D176's round)** | FR-4's rapid-buffer closure (free H⁺ per stage) and its pump's held-row fuel; Track E's Ca-dependent inactivation; a pump on finite fuel |
| B5. New kinds: transporters, finite fuel, implicit-route solvers, the stage hook | Their shapes; **for FR-4, the transporter kind and the implicit-route slot are §7.4 (g) 2 and 4** | FR-4 (CORE's insertion points, C6 in §15.6); the fuel case; FR-4's patch and Track E's junctions; the coupling note's stage factors |
| B6. Ownership separated from solver invalidation (§9.1) | The changed-slot rule | FR-2, or FR-3's later step (2–3 days with B2's share), unless the lead moves it into (a) |
| B7. The face-free bound term (§13.6), after P1 (the charged-patch test CP, running since 15 November) | Its shape | FR-4, unless CP shows the implicit patch is needed instead |
| B8. The four optional fields of a law that stands in for something (§7.1; D175) | Reserved in the law declaration's schema, unused | A reduced law after the fuel case |

### 15.3 List (c): consumer qualifications, in their own approved milestones

| Consumer | Its qualification | Needs from R |
| --- | --- | --- |
| Track E | M1 development landed (15 November); M2, the judged qualification (`excitable_qualification_v1.json`, PROPOSED); M3 on today's model; M4 (the moved laws, `fast_sodium_m3hj@1`, its protocol); M5 (calcium). D176: slowing and arrangement work follows the required qualification without delaying FR-4 and FR-5 | M4: A1, then `junction_ungated@1` (follow-on physics, D176) and the laws |
| FR-1 | Milestone 1 landed on main (15 November; development code); its references, protocol and judged run. The delivery world with reactions comes with door S's integration world in R | A6; B2 (partly holds) |
| FR-3 | Milestone 1 landed on main (15 November; development code); its references, protocol and judged run; its integrator's consolidation | B6, when its later step needs it |
| FR-4 | Its note, which must declare §10.5's boundary; charged buffering (D176); transporters on maintained, held-row fuel (D176); the charged compartment, sized by the charged-patch test | A1, A6, B3 (in R), B4's held-row read, B5, B7 or the implicit patch |
| FR-5 | After FR-1 and FR-4: the routing door, the injury law as an operator, the neutral leak | A5's law, FR-4 |
| The fuel case | The regeneration reaction and pump sharing finite ATP, ADP and Pi (§10.4) | B3, B5, the representation chosen |
| Syn3A | S2-M1: neutral solute and water across vesicles, the passive law's water composition | A5 |
| Track R | **Judged 15 November** (`species_regulated_availability@1` numerically qualified on today's model; its protocol joins G2); the routing door later | — |
| FR-8 | Its acceptance (ARCHITECTURE.md, "State roles and time") | B1 |

### 15.4 What FR-4, FR-5 and Track E's M3 each wait on

A larger R delays the work labelled blocking, so each wait is stated. **Refreshed against main
f791294 (15 November).**
- **Track E's M3 waits on its own qualification and registration, not on R,** while its grid keeps
  every junction at s·r_gj ≥ 20 (D170, ruling 3).
  - M1's development work landed: within the floor no arm blocks at s = 300, and block beyond a
    cluster needs coupling below the floor, `junction_ungated@1`'s domain. M3's direction is the
    user's (PROGRESS).
  - **D176 (item 6):** `junction_ungated@1` is follow-on physics after R, not R's added law; it
    removes a domain restriction and does not by itself produce block. Before a judged M3, loss of
    activation inside the cluster is separated from failure of propagation beyond it. Slowing and
    arrangement work follows the required qualification without delaying FR-4 and FR-5.
- **FR-4 (blocking) waits on:**
  - FR-1's milestone 1: **landed** (15 November);
  - the charged-patch feasibility test, FR-1's probe P1 extended to FR-4's counterions and
    protons and FR-5's pores (D176: early). **Running since 15 November** from the tag's snapshot
    (`fr45/charged_patch/`, the FR-4/FR-5 physics owner). It decides between the face-free bound
    term (B7) and an implicit treatment of the bounding patch;
  - its own design note, with §10.5's transformed-potential boundary, the counterion pathways,
    the pump law and charged buffering;
  - **charged buffering (D176):** today's reactions parser refuses charged species
    (`species_common.parse_species`), so buffering needs D152's charged closed reactions or a
    rapid-buffer law, with an owner and an acceptance criterion (§15.6, row F3);
  - R: A1 (the declarations, then the transporter kind's insertion point, B5), A6 (buffering inside
    a compartment beside a bath dose) and the registry's potentials (B3) for held-row fuel;
  - the face-free term (B7) or the implicit patch, per the charged-patch test.

  Its note can be written now, against §7.4 and SCOPED_COMPOSITION_DESIGN.md §6. Its code merges
  after R lands (§15.6).
- **FR-5 (blocking) waits on** FR-1 (landed), FR-4, the coupling note's routing door, the injury
  law as an operator (D167) and the passive law (A5).
- **So every day on R's critical path delays FR-4's and FR-5's code by a day.** That is the reason
  (a) holds only what R's acceptance needs, plus door S, which FR-4 needs anyway.

### 15.5 Order

Refreshed against main f791294 (15 November):
- **R landed on 16 November** (main ab267c39, tag `d172-landed-2026-11-16`), after the integrated
  gate (PROGRESS).
- **R lands after MG0c and Track R's qualification are judged: done.** Both were judged on 15
  November, and both protocols join G2.
- **Track E's M2 is judged wholly before or wholly after it: after.** It was not judged before the
  landing, so it did not join G2. Its protocol is PROPOSED.
- **Main is tagged just before it: done,** as `d172-base-2026-11-15` (44227075), with the frozen
  snapshot `snapshot-base-44227075`. R is built on `integration-d172` from the tag, and `src/` does
  not land on main until the single landing (D176).
- **The branches that were in flight landed before the tag:** FR-1's milestone 1, FR-10's milestone
  2 and the phase records, with FR-3's milestone 1. They are in the base, so G1 covers their worlds
  and they need no separate re-gate. A `src/` branch begun after the tag re-gates against the landed
  R.
- **The commit order on `integration-d172` (D176):** declarations, dispatch, the operators'
  adaptation and door S, each checked bitwise against the outputs saved at the tag; the passive
  law; the summation change last and alone, at its declared tolerance.

### 15.6 The dependency table and the critical path (D176; refreshed against main f791294)

**Owners** (D176: one integration owner; the rest split by file):
- **INT,** integration: the contract, the composite, the adapter, door S, every merge and the
  tier gates;
- **CORE,** the inner model's internals: `surface_pump_v3`, its law modules, `surface_pump`'s bound
  and step checks, `compile_window`'s key;
- **OPS,** operators and species identity (its plan:
  `d172-restructure-20261115-01/operators/PLAN.md`);
- **ACC,** acceptance and GPU: the baseline at the tag, the results gate, G2, the L4 gaps;
- **FR45,** FR-4 and FR-5 physics;
- **REF,** independent references, written from the equations by an agent who never reads the
  code.

**The interfaces between them:**

| Interface | Owner | State | Built against by |
| --- | --- | --- | --- |
| The law declarations and the implementation object (§7.4) | CORE | Published with this table | OPS, INT, FR45 |
| Door S ([SCOPED_COMPOSITION_DESIGN.md](SCOPED_COMPOSITION_DESIGN.md) §2–§6): `VIEW_CHANGES`, `SCOPED_READS`, `changed_slots`, `read_slots`; the `reference`, `fixed` and `current` modes; admission; the merge | INT | On main (7b9aeb1) | OPS and D152's owner (slot declarations, as each narrows), FR45 (§6) |
| The species registry, `registry/species_registry.py`, with one hook line in @3's parser (PLAN.md §2.2; approved) | OPS | Planned | CORE (the hook), FR45 (potentials, held fuel rows), the identity readers |
| The results baseline at the tag | ACC | Saving since 11:08 UTC, 15 November (`acceptance/baseline-44227075`) | CORE, OPS and INT, for every bitwise commit |
| The required-results list and its comparator (A3), with §3's padding rule | ACC | Planned | Every bitwise check, and the final gate |

**Method (S).** Each owner works serially, in the order listed. An item starts when its owner is
free and its predecessors are done. Elapsed days count from the round's start (15 November = day 0),
as ranges from the efforts' low and high ends. Efforts are the note's, PLAN.md §7's and
SCOPED_COMPOSITION_DESIGN.md's; where none exists, the owner supplies it. Machine time is listed
apart, on the shared machine (8 cores, 31 GB).

**R's items:**

| ID | Item | Owner | Effort (agent-days) | Needs | Machine time | Elapsed days |
| --- | --- | --- | --- | --- | --- | --- |
| Q1 | The results baseline at the tag, with its self-check | ACC | 0.5 | The tag | CPU, about 1–2 h (running) | 0 → 0.5 |
| Q2 | A3: the required-results list and runner; G1 with §3's padding rule; G2's refreshed list; G3's exact tests and negative controls; G4's harness | ACC | 1.5–2 | Q1 | — | 0.5 → 2–2.5 |
| C1 | This table and the interface (§7.4) | CORE | 1 | — | — | 0 → 1 |
| C2 | A1 with A4's two tests: structure apart from values; per-law dispatch of the channel laws, both pumps and the junction law; one cached implementation per structure; the compile key. In D176's commit order, each commit bitwise against Q1 | CORE | 4–6 | C1, Q1 | CPU, about 1 h per bitwise check | 1 → 5–7 |
| O1 | The species registry, its readers and their migration (host-side) | OPS | 2 | The note; C2's parser hook | — | 0 → 2 |
| O2 | Moved by the step | OPS | 1 | O1; §7.4, answer 6 | — | 2 → 3 |
| O3 | A2: four operator families, with their run-view declarations, each bitwise | OPS | 4.5 | §7.4 (build), C2's first API commit (test), C2 merged (merge) | CPU, per family | 3 → 7.5 |
| I1 | A6: door S (contract, adapter, composite, merge, admission; tests T1–T8), with its integration world, bath → uptake → owned compartment → reaction (SCOPED §5) | INT | 3–4 | SCOPED_COMPOSITION_DESIGN.md; FR-1's operator (on main) | CPU, minutes | 0 → 3–4 |
| I2 | The adapter and the composite take the inner implementation per structure (§7.4) | INT | 0.5–1 | C2's first API commit | — | 3–4 → 4–5 |
| I3 | Merges in D176's order: tier 1 at each, tier 2 for engine changes | INT | About 0.25 each | Each item | CPU, about 20 min per gate | As items land |
| X1 | The passive law's closed-pair reference, from a spec sent through the lead | REF | 0.75–1 | The spec (CORE, through the lead, about day 2) | — | 2 → 3 |
| C3 | A5: the passive permeation law, finding 3's term (with @1's and @2's cases and a D148 record, §10.6), the closed-pair acceptance | CORE | 2–3 | C2, X1 | CPU, hours | 5–7 → 7–10 |
| C4 | The summation study (D176, item 3; §10.6) | CORE, with ACC's L4 arm | 1–1.5 | None in code: prototypes; its CPU arms can run detached during C3 | CPU, about 4–8 h; one L4 gap | 7–10 → 8–11.5 |
| C5 | A7: the sum-order sweep at the declared tolerance, last and alone (the identity half is O1) | CORE | 1–1.5 | Every merge above; C4; INT's go-ahead | CPU | 8–11.5 → 9–13 |
| Q3 | G1 at the declared tolerance, and G3's negative controls, on the integrated candidate | ACC | 0.5 | C5 merged | CPU, about 1–2 h | 9–13 → 9.5–13.5 |
| Q4 | G2: every protocol of §3's refreshed list, in full | ACC | Supervision | Q3 | CPU, about 60–70 core-hours (**S**: E07-v1 about 50, MG0c about 3.5, Track R 0.4, the rest for ACC to sum); about 1–1.5 days on four or five free cores, with setup | 9.5–13.5 → 10.5–15 |
| Q5 | The L4 gap: the thirteen variants' backend terms re-measured (§5.3), then their judged L4 items | ACC | 0.5–1 | C5 | An L4 gap of about a day | Beside Q4, if the GPU is free |
| I4 | The landing: tier 1 and 2 on the integrated candidate (tier 3 deliberately), the merge to main, the tag | INT | 0.5 | Q3, Q4, Q5 | CPU, about 1 h | 10.5–15 → 11–15.5 |

**FR-4's path** (its own milestone, outside R's gate):

| ID | Item | Owner | Effort (agent-days) | Needs | Elapsed days |
| --- | --- | --- | --- | --- | --- |
| F1 | The charged-patch feasibility test CP: FR-1's probe P1, extended to FR-4's counterions and protons and FR-5's pores (D176: early) | FR45 | Owner to supply | The tag's snapshot | Running since 15 November |
| F2 | FR-4's design note: §10.5's boundary; the counterion pathways; the pump law against §7.4's transporter shape; charged buffering's design and criterion; the patch treatment from F1 | FR45 | Owner to supply | F1; §7.4; SCOPED §6 | From day 1 |
| F3 | **Charged buffering (D176):** FR-4's note chooses a rapid-buffer closure, a per-stage algebraic read (its §4), in a new module `laws/reactions/rapid_proton_buffer.py`. D152's charged slow reactions are a separate route, off FR-4's critical path (its §11, item 4) | FR45 (the closure, as its note proposes; the lead to confirm), on CORE's stage-read slot (C6) | Owner to supply | F2; O1's potentials; C6's slot | After F2 |
| C6 | FR-4's insertion points (§7.4 (g)): the transporter kind (B5), the stage-read slot (B4), B7's two halves and the implicit-route slot with faces behind it | CORE | 3.5–5 (**S**); re-estimated after the rulings at 5.5–7 for the three that open in the round (§7.4 (h)) | C2, F1, F2 | After C5: day 9–13 → 12.5–18, unless the lead moves it before C3 |
| F4 | FR-4's first case on maintained, held-row fuel: the law module, the world, its references (REF) and its protocol | FR45, REF | Owner to supply | C6, I1, O1, F2, F3 | Develops on `integration-d172` once C2 and I1 merge; merges after I4 |

**F3's acceptance criterion,** proposed here and matched to FR-4's note's closure (its §4, §13 and
§14), for that note to fix:
- **Admission:** buffer rows are inert (no route, no reaction). Each has one acid–base pair whose
  two standard potentials, of the base form and the protonated form, the registry holds (FR-4's
  note's B3), and a base valence; the operators stream extends the registry to carry both, in a
  shape of its choosing (the lead's ruling, 15 November). The pair's K follows from the two
  potentials, so no pK is declared beside them. One representation of a node's protonation is
  admitted (D175's key). No @3 route for H at a buffered node.
- **The closure's declaration:** the (node, row) pairs it buffers, which its mask keys on; the
  standard concentration c0, taken from the registry's declared one; and k_on, a D175 stand-in
  parameter used only for the envelope check and by the reference, never by the closure's own
  equilibrium.
- **Charge:** buffering changes no node's charge. The stored rows' charge sum is exact as it stands
  (that note's §3). In a world where only the closure acts, every node charge and the field stay
  bitwise unchanged.
- **Material and energy:** H_eq and every B_tot are conserved, except across routes. The closure's
  declared free-energy term ΔG_buf closes the energy ledger at rounding, from a trace start
  (pH 5 to 7.4).
- **Convergence:** |g|/H̄_eq ≤ 1e-13 at every stage, else the step is refused.
- **Accuracy:** against a kinetic-buffer reference (REF, Radau, at the closure's declared k_on,
  1e10 M⁻¹ s⁻¹ in FR-4's worlds) within a budget declared before the comparison. D175's envelope
  (k_on B̄ ≫ 1/dt, and ≫ every per-free-proton transport rate) is checked as declared bounds, and
  one case outside it must fail.
- **Planted control:** a wrong base valence fails the charge check.

**D176's corrections: where each is entered, and whose it is.**

| Correction | Where | Owner |
| --- | --- | --- |
| The dependency table refreshed | This section, §15.3–§15.5 | CORE |
| Bath → uptake → owned compartment → reaction, a real acceptance world | §8, A6; SCOPED §5, T5 | INT |
| Charged buffering, an FR-4 dependency with an owner and a criterion | §15.4; F3 above | FR45 (the closure, as its note proposes; the lead to confirm), on CORE's stage-read slot |
| The charged-patch test early | §15.4; F1 | FR45 (running) |
| Order independence narrowed | §8; SCOPED §4 | INT |
| Reference reads apart from field-unchanged assumptions | §8; SCOPED §2 (`reference` against `fixed`) | INT |
| G1 and G3 aligned | §3 | ACC |
| A7's manifest from the import closure | §10.6 | CORE, with ACC |

**The critical path (S).** C1 → C2 → C3 → C4 → C5 → Q3 → Q4 → I4: 1 + (4–6) + (2–3) + (1–1.5) +
(1–1.5) + 0.5 + (1–1.5) + 0.5 = **about 11–15.5 days without C6,** so a landing about 26–30
November.
- **With C6 inside R** (the stage hook opens in this round, §7.4 (g)), the core's queue grows by
  3.5–5 days wherever C6 sits before the landing: **about 14.5–20.5 days,** a landing about 29
  November to 5 December. Where C6 goes, and whether it lands with R or as FR-4's first commits on
  top of it, is the lead's call.
- **The core stream is the long pole,** with 9–13 agent-days in series (12.5–18 with C6).
- **Every other owner has slack:**
  - OPS finishes its adaptation about when C2 merges (day 7–7.5);
  - INT's door S (day 3–4) and its adapter work (day 4–5) come early;
  - ACC is free between Q2 (day 2–2.5) and the candidate (day 9–13), apart from C4's L4 arm.

**Dates per consumer:**

| Consumer | Can build against | Can merge onto `integration-d172` | Accepted |
| --- | --- | --- | --- |
| OPS | §7.4, from day 1 | After C2's merge, day 5–7 | At the landing, day 11–15.5 |
| INT (the adapter per structure) | §7.4, from day 1 | After C2's first API commit, about day 2–3 | At the landing |
| FR45 (FR-4) | §7.4 (g) and SCOPED §6, from day 1 | Its laws (pump, closure, patch kind) once C6's slots merge: day 12.5–18 if C6 follows C5, about day 8.5–12 if it precedes C3 | In its own milestone, after the landing |
| REF | The spec, about day 2 | Validation, onto main through the lead | With C3 |

**Ways to shorten the core's path, each the lead's call:**
1. **ACC runs the summation study's harness and arms, and CORE reviews.** It saves 1–1.5 days,
   and ACC is free then.
2. **CORE writes A5's insertion point while FR45 writes the passive law's kernel and booking** as a
   new law module against §7.4. It saves 1–1.5 days, at the cost of one more hand-off.
3. **FR-4's insertion points (C6) go before A5.** FR-4's laws can merge about 4 days earlier, and
   R lands 3.5–5 days later, unless 1 and 2 absorb part of it.

With 1 and 2, the path is about 9–13 days; with 1, 2 and 3, about 12.5–18.

**Re-planned after the lead's rulings (15 November; §7.4 (h)).** Options 1 and 2 are taken (the
summation study goes to OPS; FR45 writes the passive law's kernel), and FR-4's insertion points are
split. The core's queue, from day 1:

| Core item | Effort (agent-days, **S**) | Elapsed days |
| --- | --- | --- |
| A1's first API commit: declarations and one implementation per structure (programs unchanged) | Done (034a60e on `core-d172`, from the tag) | About 1.2 |
| The dispatch commits (channel laws; pumps and the junction law) and A4's two tests with the compile key. **Built** on `core-d172` (11176e3, 1386c13, 43812f5); K2 and the acceptance owner's results baseline (K3) are running on 43812f5; merging waits for the bitwise observations on the division worlds and a running law-steady replacement world (§7.4 (b)) | 2.5–3.5 | → 3.7–4.7 |
| FR-4's three insertion points: the per-structure schema (1), the stage-read slot (1–1.5), the transporter kind with its fuel rows, finite by default and held as the special case (2.5–3.5, §7.4 (h)), B7 with finding 3's term (1, host-only, one D148 record) | 5.5–7 | → 9.2–11.7 |
| The passive law's insertion point, with the exact heat booking (§7.5); FR45's kernel | 1.5–2 | → 10.7–13.7 |
| A7's sweep, last and alone (OPS's study done meanwhile) | 1–1.5 | → 11.7–15.2 |
| Then G1, G2 and the landing (Q3, Q4, I4) | 2–2.5 elapsed | → **13.7–17.7** |

- **The implicit slot** (1–1.5) follows once FR-4's first world runs. **The lead's ruling (15
  November): it stays outside the round unless FR-5's first world needs it** (the lead asks FR45),
  so the plan was 13–17 days. Finite fuel as the transporter's default (the coordinator, 15
  November; §7.4 (g) 2) adds 0.5–1 day, so about 14–18; inside R the implicit slot would move the
  landing to about 15–19.
- **FR-4's laws can merge onto `integration-d172`** once the three insertion points merge, about
  day 9–12, and are accepted in FR-4's own milestone.

**Refreshed from today (15 November, 17:00 UTC; the lead asked for one number).**

| Item | Owner | Effort (agent-days, **S**) | Elapsed from today |
| --- | --- | --- | --- |
| The dispatch clearance (amendment 7): K2 with F1 (`core-d172-dispatch` 2337aeb2), tier 3 | CORE | Running | Day 0 |
| The registry hook (89d0919) and B7 (119ffb7); B7's D148 record (sweep unchanged, crossrev pair running) | CORE | Built | Day 0 |
| Schema A plus the kind seams (§7.4 (j), (k); stage 1 coded) | CORE | 2.5–3 | → 2.5–3 |
| The adapter's lookup order, the composite's inner type reads, the composite spec's controls, the families' refusal | INT | 1–1.5, in parallel | → 2.5–3 |
| B4's stage read | CORE | 1–1.5 | → 3.5–4.5 |
| The passive law's insertion point (§7.5, version 1) | CORE | 1.5–2 | → 5–6.5 |
| B5's transporter, version 1 (FR-4's held-fuel proton pump and R-fuel's neutral finite-fuel case), its module and kernel, with CORE's review | FR45, CORE | 2.5–3.5, then 0.5 | → 5.5–7 |
| A7's sweep, last and alone | CORE | 1–1.5 | → 6.5–8.5 |
| G1, G2 and the landing (Q3, Q4, I4) | INT, ACC | 2–2.5 elapsed | → **8.5–11** |

**One number: about 10 days from today, so an integrated landing around 25 November.**

## 16. Open questions, with recommendations

Questions 1, 2, 3, 5 and 6's added law were decided by D176 (15 November); they stay here with
their answers.
1. **The fuel representation** (§10). **Decided: F2,** inventory rows with one authority per
   standard potential (§10.2); maintained fuel is held rows. Open for the lead: today's two pumps
   keep their parameter form in R (§10.2).
2. **The name** (§6). **Decided: kept,** `resolved_pump_tissue@3`, with D147 amended as written.
3. **Rounding in G1** (§3, §4, §10.6). P2 found per-law dispatch bitwise. P7 found A7's fixed
   order moves results at rounding. **Decided:** A7 stays in R, its order chosen by the summation
   study, landing last and alone; G1's tolerance is stated before R's gate, and G2 runs in full.
4. **I0** (§13.6). P3 refused nothing, so finding 3's term rides in R with the passive law and
   needs no run-time half. The face-free term waits for the charged-patch test and FR-4 (B7).
5. **The cost-savers** (§3). **Decided:** no sample; E07 runs in full on the integrated candidate.
   Derivative-program judges always run in full.
6. **R's scope** (§15).
   - List (a) as given, A1–A7, with door S's integration world in A6 (D176).
   - Ownership separation stays in (b), with a narrow later gate; moving it into (a) costs 1.5–2
     days and saves that gate.
   - **R's added law: the passive law (decided, D176).** `junction_ungated@1` is follow-on physics.
7. **The stage hook: opened** in D176's round for FR-4's closure (§7.4 (g) 1, §13.5). The coupling
   note's stage factors still wait for a named consumer and its P3.
8. **New (§7.4 (h), §15.6), for the lead:** the owners of charged buffering (F3: FR45's closure, as
   its note proposes), of FR-1's refusal 4 (FR45 claims `compartments.py` in its §11), of FR-3's
   integrator consolidation (§14), of the registry's @3 line and of `definitions/surface_pump_v3_spec.py`;
   whether FR-4's insertion points (C6) go before A5; and whether today's pumps keep their
   parameter form (§10.2).

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

**P2, per-law dispatch against today's** (results and cost). In seven worlds, the forward runs and two worlds' Jacobians are bitwise identical. Programs lose 10 to 190 equations. Times are within noise, and second runs compile nothing (§4).

**P3, the I0 sweep**, with planted controls of known answer.
- **The first run was void, by a probe bug** (valence held as a column). Its ion-only worlds stand.
- **The rerun** (amendment 3) covers the controls, D150, MG0c and Track R. Every control hit its known answer.
- **No registered or PROPOSED world is refused or tightened** (§13.6).

**P5, the constants inventory.** All nine worlds share one executable with their parameter twins; the value-search hits are coincidences checked in code (§5.2).

**P6, memory and step cost against the species count.** All eight rows are measured. The 825-node world at 160 species was rerun at 04:12 UTC, after its first attempt fell to the 01:42 machine-wide out-of-memory event. Per species, on one CPU core: 0.3–0.5 ms per step on the sheet; 8.9 ms on the 825-node world from 8 to 64 species, falling to 5.0 ms from 64 to 160 (§10.6).

**P7, A7's fixed species-sum order** (15 November, 03:49–04:12 UTC; peak 1.48 GB, no memory events).
- **C0 holds:** the planted change is seen everywhere.
- **C1 fails:** values move at rounding in six of seven worlds. That is 1–4 ulps in ledger accumulators only, in five; up to 36–54 ulps in the excitable cell's gates and electrode ledger.
- **C2 holds:** the Jacobians are bitwise.
- **By the registered reading:** G1 runs at a stated tolerance and G2 in full (§10.6).

(P4, the cost of per-law dispatch, was folded into P2 as its amendment 2.)

**K1, padding slots under per-law dispatch** (D176's round, 15 November; the core stream's log,
`/mnt/workspaces/Cells/d172-restructure-20261115-01/core/HANDOFF.md`, criterion written before the
run; host only, from the tag's snapshot, 2.5 s).
- **The question:** code 0 is both Kv1.5's and every inactive slot's. Today inactive slots get
  Kv1.5's kinetics at 0 V, which `readouts` returns unmasked and the observer records. P2 compared
  state fields only.
- **The result, as expected:** in a heredity cell with two padded slots (Kir2.1 and NaV1.2
  declared), P2's per-law functions change `channel_targets` and `channel_tau_s` at the two
  inactive slots only (Kv1.5 at 0 V before; 0 and 1 after). The other 65 readouts are bitwise. In
  the five-law release world, all 67 are bitwise.
- **So:** §7.4 (b) first made those two columns a comparator exception. The later activity check
  found closed slots that are active on other rows (the division worlds), so the host keeps
  today's padding values as a declared fill (§7.4 (b); the lead's ruling), and no comparator
  exception remains (§3).

## Sources

- The design notes and decisions cited by section.
- ARCHITECTURE.md, "The modular core"; D172; D174.
- The code read at f2ada38d:
  - `models/surface_pump_v3.py`, `definitions/surface_pump_v3_spec.py`, `models/surface_pump.py`;
  - `models/pump_composite.py`, `models/pump_composite_adapter.py`, `definitions/pump_composite_spec.py`;
  - `models/operators/`, and FR-1's `compartments.py` on its branch;
  - `execution/runner.py`, `execution/windows.py`, `execution/batch.py`, `execution/vector_windows.py`;
  - `numerics/surface_imex.py`;
  - `processes/` (the channel kernels, `junction_gate.py`, `kinetic_pump.py`, `finite_energy.py`);
  - `legacy/core/kinetic_finite_spec.py`, `legacy/core/surface_energy_spec.py`, `io.py`;
  - `validation/tissue/composite_crossrev.py`, `validation/continuity/probe.py`,
    `validation/tissue/l4_variants/`.

No literature is added by this note.
