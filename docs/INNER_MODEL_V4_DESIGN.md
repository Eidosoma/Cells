# The inner model made modular, in place (design)

**Status: in implementation (D176, 15 November 2026), on `integration-d172` from tag
`d172-base-2026-11-15` (44227075). Proposed 14–15 November; revised for D172, D174 and D176.**
- **D176, in force:** F2 fuel; FR-4's first case on maintained fuel; the summation order chosen by
  a measured comparison (§10.6); every affected registered protocol re-run on the integrated
  candidate, E07 included; the name kept; and eight design corrections, entered where they apply
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
       (D176, item 4). Door S's merge (A6) is still unprobed.
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
   ATP, ADP and Pi) stays separate.
9. **The name** (§6). **Decided (D176): kept,** `resolved_pump_tissue@3`, with the snapshot, tag
   and results-gate provenance.
10. **When** (§15.5, refreshed). MG0c and Track R are judged, and main is tagged
    `d172-base-2026-11-15`. R is built now on `integration-d172` and lands once, after the
    integrated gate (§3). Track E's M2 is judged wholly before or wholly after the landing.
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
    or about 14.5–20.5 with FR-4's insertion points (C6) inside R (§15.6).

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
| **G1, existing worlds on CPU** | Every world of the crossrev sets (base, qualification, injection, volume, division, species, reactions, and each operator's own set) and @3's test worlds. Each runs from the tag before R and from the new snapshot. Compared: every state field, observation column and `max_` diagnostic of every accepted row, and every refusal (its step and its message) | Bitwise, NaN-aware, bit patterns compared, except where R changes rounding. **A7 does (P7):** physical fields and accumulators are compared within a tolerance stated before the run from P7's magnitudes, field by field, and G2 runs in full. **Padding (check K1, §7.4 (b)):** per-law dispatch changes `channel_targets` and `channel_tau_s` at inactive population slots (padded or closed) of worlds that do not declare Kv1.5, and nothing else; the comparator treats those two columns at inactive slots as padding, a rule agreed with the acceptance owner before the dispatch commit's run |
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
| Guarded batch (`core/batch.py`) | As above, per world under `lax.map` | **All of `check_values`**, per world | Observers |
| Vector windows (`core/vector_windows.py`) | The step's refusals, and the device row checks (`device_checks`): domain, every ledger (operators' own included, `Composition.DEVICE_CHECKS`), dissipation | **None.** Only per-window summaries leave the device | Observers and continuity checks; the window endpoint |
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
  - from later landings, each present only when declared: the passive law (A5), transporters (B5),
    stage reads (B4), implicit route kinds, and B7's flag for a free face-free node with an ion
    route.
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
| `permeant` | (species, valence, relative permeability): today's `LAW_PERMEABILITIES` with `SPECIES_VALENCE` |
| `voltage_domain` | (−0.120, 0.060) V for all five |
| `rk4_step_s` | 2.5e-6 for NaV1.2, 25e-6 for Kv1.5 and Kir2.1, none for the leaks (today's `RK4_*_STEP`) |
| `stage_term` | `constant_field_slope`, today's `membrane_rate` term at the actual opening |
| `reads`, `loop_term` | None for these five; (g) 1 below |
| `provenance` | `parity` |
| B8's four fields | Reserved, empty (D175) |

- **A junction law** declares its ID, `gated` (true for `junction_voltage_relaxation@1`), its
  kinetics, right-hand side and domain (`junction_gate`'s, ±0.120 V), and its definition-time bound
  (`junction_gate_rate_bound`).
- **A pump law** declares its ID, kernel and domain, the rows it moves per cycle by role, its fuel
  kind and its definition-time bound. Both of today's pumps run on
  `maintained_chemical_reservoirs@1` in today's parameter form (§10.2).
- **The padding rule (P2's measured form, check K1).** An inactive population slot, padded or
  closed, carries code 0, as today (`domain_valid`, the adapter's `close`). The dispatch selects a
  declared law's values wherever a slot carries its code, active or not, so:
  - in a world that declares Kv1.5 (code 0), an inactive slot reads Kv1.5's kinetics at 0 V, as
    today, bitwise (K1's five-law world);
  - in a world that does not, it reads target 0, time constant 1 and opening 1. Today it reads
    Kv1.5's values, so `channel_targets` and `channel_tau_s` change at those slots, and nowhere else
    (K1).
  - G1's comparator treats those two columns at inactive slots as padding (§3). ACC agrees the rule
    before the dispatch commit runs.
  - Masking by activity as well would make padding independent of the declared laws, but it would
    change those columns in every world with an inactive slot, and K1 did not measure it.

#### (c) Build-time selection: one implementation per structure

- **The calls:**
  - `surface_pump_v3.structure(model)` → `InnerStructure`;
  - `surface_pump_v3.implementation(structure)`: one object per structure, cached, so equal
    structures share one object, its functions and its executables;
  - `surface_pump_v3.model_for(model)` = `implementation(structure(model))`.
- **Who calls them:**
  - `registry.get_model` returns `model_for(model)` for a plain @3 definition: one line in the @3
    branch of `models/registry.py`, a file in no stream's list (the lead to confirm).
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
   bitwise, except the padding columns (K1's rule).
3. **Pump and junction-law dispatch:** bitwise, up to signed zeros at exact zeros, reported apart.
4. **The compile key and A4's two tests** (§2.2, §5.2):
   - an undeclared law contributes no kernel and no state: a jaxpr check that a world without
     NaV1.2 holds none of its kernel, and a world without the passive law none of its fields;
   - a parameter-only change reuses the executable (`compile_window` reports 0 s), and gives the
     result a fresh compile gives, bitwise.
   - `compile_window`'s key gains the model's `structure_key`, which the object sets to its
     structure (and the composite to its inner structure and operator list). The step and check
     functions stay in the key.

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
   - **Reads at a split** (FR-5's factors on the routing door) call the same pure `evaluate` on the
     split's state. They are first order in dt there, as FR-4's note says.
   - **Owners:** the slot is CORE's, in `surface_pump_v3`. The closure module
     (`processes/rapid_proton_buffer.py`) and its declaration are FR45's.
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
     - `stage_term`, its electrogenic conductance for the stage rule, and `loop_term`;
     - its definition-time bound term, `provenance` and B8's fields.
   - **Held rows:** `maintained_held_rows@1` (name **S**).
     - The population names its fuel node, the hydrolysing cell, and its fuel rows (ATP, ADP, Pi).
       They are read at every stage as rows nothing moves, and never moved.
     - The definition refuses a held row that any in-step mover or operator writes (OPS's
       `moved_in_step`, and D152's one-writer rule).
     - Δ_rG'° comes from the registry's potentials (B3, OPS's), never from the pump.
     - The supplied work per cycle, −Δ_rG'_ATP, is booked as today's metabolic work. The
       maintenance's material record (+1 ATP, −1 ADP, −1 Pi per cycle) is an accumulator of the
       population.
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
3. **B7's slot.**
   - **At the definition:** a new host function, `surface_pump.face_free_rate_bound(spec)`, beside
     `explicit_rate_bound`. It takes the maximum over free face-free finite nodes (active, not a
     held bath, not the gauge, not a fixed node, named by no face) of Σ_m G_m/C_node at the
     declared state, with G_m the max-side constant-field slope of each ion route on the node's
     patches. The step checks refuse dt × that rate > `FACE_FREE_STEP_BOUND`.
   - **At run time:** `membrane_rate`'s companion at the actual openings, checked at every explicit
     stage against the same constant. It is statically present only when the structure flags a free
     face-free node with an ion route, so every other world's program is unchanged.
   - **The split:** FR45 supplies the term's exact form and its constant (0.05 on the max-side G,
     from the energy threshold), after its booking-versus-state check. CORE implements both halves,
     with a D148 record for @1 and @2, which share `surface_pump`. P3 swept @3's family only; for
     @1 and @2, FR-1's static sweep of 99 model blocks found no free face-free node with an ion
     route in their worlds (CLOSED_COMPARTMENT_DESIGN.md §3.4), and the D148 record confirms it on
     their registered worlds before the change.
4. **The implicit patch: yes, behind one slot,** the IMEX step's implicit set.
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
   - **Owners, reconciled with §13.4:** CORE builds the slot in `surface_pump_v3.imex_step`, with
     faces moved behind it bitwise. FR45 codes the patch kind against it in a new module, and
     qualifies it, with REF's reference. The field-solver interface keeps the factorization and the
     solve (FIELD_SOLVER_INTERFACE_DESIGN §6), which the slot calls unchanged; a later sparse or
     condensed solver replaces them behind the same calls.

#### (h) What this adds to CORE's queue, and what the lead decides

- **C6 (§15.6) is now about 3.5–5 agent-days (S):**
  - the transporter insertion point, 1–1.5;
  - the stage-read slot, 1–1.5;
  - B7's two halves, 0.5;
  - the implicit-route slot with faces behind it, 1–1.5.
- **Its timing is the lead's call** (§15.6, option 3). After A7, FR-4's code can merge from about
  day 12.5–18. Before A5, R lands 3.5–5 days later.
- **How an operator reaches the implementation object is INT's contract question.** Operators
  receive state, control and layout only, and today import `surface_pump_v3` directly. The contract
  can pass the composite's inner object to the parts that call the inner model (replacement's event
  map, water's coupled RK4 part); or those calls stay on structure-free module functions where one
  suffices (replacement's post-event junction voltages need only the field solve). OPS's event-map
  work waits on INT's answer.
- **Files in no stream's list:**
  - `core/surface_pump_v3_spec.py` (the parser and `LAW_CODES`), taken as the core's unless the
    lead says otherwise;
  - the registry's @3 line;
  - the thin families (`models/cell_replacement.py`, `surface_pump_water.py`,
    `surface_pump_water_v2.py`). They import only structure-free names from @3, but
    `cell_replacement.py` builds its composite at import from the inner model ID, which becomes
    per structure (INT's change).

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
    or keep its species count. **For the lead:** keep that form as the declared representation of
    today's pumps, with a later, separately gated migration if wanted; new fuel consumers, FR-4's
    pump first, use held rows from the start.
- **Effort** (**S**): identity and trace policy are part of A7 (in R). **Refreshed (D176):** the
  operators stream's species registry (`core/species_registry.py`, approved) carries each
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
(`species_common.MAX_SPECIES`, 16 today) is raised whenever a consumer needs more species. Each
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
- **The summation study (D176, item 3), before A7 freezes; the core stream.**
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
  - Fixed-step runs read it and change nothing; the event-time rule (exact multiples of dt) stays.
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
| The face-free-node term | The maximum over **free** face-free finite nodes of Σ_m G_m / C_node at the declared state, with held baths, the gauge and the layout's fixed nodes excluded | A declared stage term in the inner model. Until it exists, channels and pumps on such a patch are refused |

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
- **R lands after MG0c and Track R's qualification are judged: done.** Both were judged on 15
  November, and both protocols join G2.
- **Track E's M2 is judged wholly before or wholly after it: still open.** Its protocol is PROPOSED.
  If it is judged before the landing, it joins G2.
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
| The species registry, `core/species_registry.py`, with one hook line in @3's parser (PLAN.md §2.2; approved) | OPS | Planned | CORE (the hook), FR45 (potentials, held fuel rows), the identity readers |
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
| F3 | **Charged buffering (D176):** FR-4's note chooses a rapid-buffer closure, a per-stage algebraic read (its §4), in a new module `processes/rapid_proton_buffer.py`. D152's charged slow reactions are a separate route, off FR-4's critical path (its §11, item 4) | FR45 (the closure, as its note proposes; the lead to confirm), on CORE's stage-read slot (C6) | Owner to supply | F2; O1's potentials; C6's slot | After F2 |
| C6 | FR-4's insertion points (§7.4 (g)): the transporter kind (B5), the stage-read slot (B4), B7's two halves and the implicit-route slot with faces behind it | CORE | 3.5–5 (**S**) | C2, F1, F2 | After C5: day 9–13 → 12.5–18, unless the lead moves it before C3 |
| F4 | FR-4's first case on maintained, held-row fuel: the law module, the world, its references (REF) and its protocol | FR45, REF | Owner to supply | C6, I1, O1, F2, F3 | Develops on `integration-d172` once C2 and I1 merge; merges after I4 |

**F3's acceptance criterion,** proposed here and matched to FR-4's note's closure (its §4, §13 and
§14), for that note to fix:
- **Admission:** buffer rows are inert (no route, no reaction), each with one declared pK and base
  valence. One representation of a node's protonation is admitted (D175's key). No @3 route for H
  at a buffered node.
- **Charge:** buffering changes no node's charge. The stored rows' charge sum is exact as it stands
  (that note's §3). In a world where only the closure acts, every node charge and the field stay
  bitwise unchanged.
- **Material and energy:** H_eq and every B_tot are conserved, except across routes. The closure's
  declared free-energy term ΔG_buf closes the energy ledger at rounding, from a trace start
  (pH 5 to 7.4).
- **Convergence:** |g|/H̄_eq ≤ 1e-13 at every stage, else the step is refused.
- **Accuracy:** against a kinetic-buffer reference (REF, Radau, k_on 1e10 M⁻¹ s⁻¹) within a budget
  declared before the comparison. D175's envelope (k_on B̄ ≫ 1/dt, and ≫ every per-free-proton
  transport rate) is checked as declared bounds, and one case outside it must fail.
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
   integrator consolidation (§14), of the registry's @3 line and of `core/surface_pump_v3_spec.py`;
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
- **So:** §7.4 fixes the padding rule, and G1's comparator treats those two columns at inactive
  slots as padding (§3).

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
