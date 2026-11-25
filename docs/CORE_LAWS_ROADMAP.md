# Core laws roadmap, and readiness for mitochondria

*Status: proposed, 19 November 2026, for the lead and the advisor, then the user. Desk work only:
no engine code and no runs. Written on branch `core-laws-roadmap` from main 7f357cfb, where the
code was read. Main's later commits, up to 2098b52c at hand-off, touch only `lean/` and
`visualizer/`.*

**Decided, 19 November 2026 (D234).** The user chose Option 2, and lifted D145's hold for a
gene-regulation design note. The lead's rulings for MT-1:
- **The host waits for P1′.** The @3 owner runs it first: host P's arm, then host C's two-cycle arm.
- **Owners.**
  - New law modules under `laws/cycles/`: the mitochondria lane (D209).
  - `kinds/transporter.py` and `laws/cycles/forms.py`: the kinds owner.
  - The registry: the binding owner.
  - `validation/mitochondria/`: the mitochondria lane, except `references/`, which belongs to the
    references agents.
  - `operators/species_common.py` and `operators/bath_schedule.py`, if touched: the operators owner.
- **The whole-organelle references are labelled MR1 and MR2 here,** to avoid the fingerprint gate's
  R1. MR1, the code-blind Beard reference, started on 19 November and serves MT-2. Its brief allowed
  MITOCHONDRIA_DESIGN.md, which already names Eq. 11's missing proton, so its finding on Eq. 11 is
  not independent. Its findings on Eq. 16 and Eq. 24 are.
- **State 4, with no external ADP:** its own held-buffer world with a declared ADP trace. The trace's
  effect is bounded against the judged effect, as D233 did for FR-7.
- **On host P, the outer membrane's face** uses `logmean_electrodiffusion@1` for porin permeation.
  This holds if the lane shows that it reduces to the source's p·Δc at zero potential difference.
  Its runs report the potential across the outer membrane.


**What it answers.** The user asked for two things:
- **(A)** a roadmap of the core physical laws, from which to choose an order (Part 1);
- **(B)** readiness to start mitochondria right after (Part 2).

**Words used.**
- **Judged:** a registered protocol passed. Its tag and scope line are named.
- **Compared:** checked against code-blind references in every gate, but not judged.
- **Development:** landed, neither judged nor compared.
- **Weaker evidence** is kept wherever the record says it.
- **Legacy:** `src/cells/legacy/`. It is a reference, not a supported surface (D196).
- **(estimate):** this note's own rough figure, in agent-days. A design note's own estimate is cited
  to that note.

**Labels.** Several notes number their milestones M1, M2 and so on. This note always says whose:
"mitochondria M4" (MITOCHONDRIA_DESIGN §8), "composition M2" (OPERATOR_COMPOSITION_DESIGN),
"machines M1" (MOLECULAR_MACHINES_DESIGN), "Track E" (EXCITABLE_TISSUE_DESIGN), "cardiac H1"
(HUMAN_CARDIAC_LAWS_DESIGN), "FR-8 rung 1". The mitochondria milestones proposed here are **MT-1**
and **MT-2**.

**Contents.**
- Part 1. The roadmap: 1.1 the engine in brief; 1.2 status at a glance; 1.3 the thirteen families;
  1.4 who needs what next; 1.5 ordering options and a recommendation.
- Part 2. Mitochondria readiness: 2.1 the decided direction; 2.2 the prerequisites on main;
  2.3 what is still missing, by owner; 2.4 the first milestone, MT-1; 2.5 questions; 2.6 the brief
  for the code-blind references (separable).
- Sources read.

---

# Part 1. The roadmap

## 1.1 The engine in brief

- **One modular inner model,** `resolved_pump_tissue@3` ("@3"; D172, tag `d172-landed-2026-11-16`).
  - Kinds plug into it: `cells.transporter@1`, `cells.passive_routes@1`,
    `cells.rapid_proton_buffer@1`, `cells.ph_condition@1` and `cells.patch_damage@1`.
  - Operators compose around it in `resolved_pump_composite@1`.
  - Laws sit in one law registry and are named by mechanism (D144; seam F).
- **The core-seams pass** (D195; [CORE_SEAMS_DESIGN.md](CORE_SEAMS_DESIGN.md)) has landed:
  - seam A, cycles (ee30e5d9); seam C stage 2, binding (aecbaed1); seam D, heat booking (6ca4a56f);
  - most of seam E, fuel's core part (ac43139d, bd9881d5); seam F, laws as modules; seam G, the run
    view;
  - B1, the populations' lifecycle by roles (3fd9c17c), and B1′, the operator rate route (ee43b082).
  - **Not landed:** B2, the own-axis maps that let a kind's populations divide.
- **Older families** live in `src/cells/legacy/` (D188). Calcium handling, and energy with
  mitochondria, live only there today. Each is rebuilt in the modular engine, then dropped in one
  approved batch (D196).
- **The assembly family** (`cells.assembly_lineages@1` and `@2`) is a separate stochastic engine,
  for GARD and origin of life (D192, D197, D199).

## 1.2 Status at a glance

| # | Family | Judged on main | Compared or development on main | Next (built on a branch, or designed) | Held |
| --- | --- | --- | --- | --- | --- |
| 1 | Electrodiffusion, channels, field | BETSE parity rungs; E07-v1, a judged experiment on @3 (`e07-v1-judged-2026-11-14`) | Kv1, Cl⁻ leak and inward-rectifier laws | Cardiac H1's channel seams; FR-16; FR-17 | Markov laws and subspace Ca²⁺ stay closed in version 1 |
| 2 | Transport | FR-4's proton pump on held fuel (`fr4-v1-qualified-2026-11-17`) | Seam A's population axis (compared); symporter version 1 | Symporter version 2 and availability schedules (branches); pumps moved onto the kind | — |
| 3 | Chemistry | MG0c's reactions (`mg0c-v1-qualified-2026-11-15`); D150's faces and turnover clearance (`secreted-species-v1-qualified-2026-11-14`); exchange, with FR-1; FR-10 (`fr10-v1-qualified-2026-11-17`) | FR-15 S1, charged species in reactions | FR-15 P2 (branch); metabolism at scale and a stochastic regime (not designed as notes) | Exchange stays neutral; the 16-row cap rises only by D148 changes (D165) |
| 4 | Binding, buffers, pH | FR-4; FR-3 (`fr3-v1-qualified-2026-11-18`) | The general closure `rapid_binding@1` (compared); P1's predictor | A first real mover of closure rows; registry moieties | — |
| 5 | Compartments, organelles | FR-1 (`fr1-v1-qualified-2026-11-18`); FR-5 (`fr5-v1-qualified-2026-11-17`) | Refusal 4 version 1.3; refusal 5 version 1.2 | FR-1's later doors; pools at the cell's potential; mitochondria | Subspace Ca²⁺; nested capacitors |
| 6 | Trafficking, abundance | S5a's insertion@2 (`cell-division-s5a-qualified-2026-11-14`); the coupling operator (`coupling-v1-qualified-2026-11-15`); FR-6's A5″ (`fr6-a5pp-v1-qualified-2026-11-18`) | FR-2 version 1 (compared, weaker evidence); FR-7 F1; B1′ | FR-7 F2–F4 | Catalogue stage 3 (D145) |
| 7 | Gene expression, regulation | — | Building blocks only | A design note | D145, narrowed by D218 |
| 8 | Metabolism, energy | FR-4, on held fuel | Finite fuel rows (compared at component level) | The first finite-fuel acceptance; pumps on finite fuel | — |
| 9 | Signalling | FR-6's A5″; D150 | FR-15 S1; @2's Ca²⁺ ion (BETSE parity rung 1) | Cardiac H2; FR-15 P2; FR-16 | Subspace Ca²⁺ |
| 10 | Mechanics, division | MG0a–c; MG1 (weaker evidence); S5a; water@1 and @2 | Composition M1; B1's lifecycle | Composition M2–M5; B2; lifecycle M2 | Mitosis machinery; lifecycle M2 queued (D176) |
| 11 | Assemblies, origin of life | — | GARD G1; OL1 (compared with OL5) | OL2 milestone 1 (branch); OL2 milestones 2–3; OL3 milestone 1 | Behind core and FR-1 to FR-10 (D230) |
| 12 | Long duration (FR-8) | — | FR-8 stage 0 and rung 0; X2 | Rung 1's control run (D232) | A full solver and an exact booking need approval (D217) |
| 13 | Shared needs | — | — | D175's fields; `cells.relations@2`; keyed streams; condensation | Module stage 1 at low priority (D214) |

**The judged register.** Every judged protocol on main that this note relies on, with its scope in
brief. Each verdict covers only its scope line and the build it judged.

| Protocol | Registered | Tag | Result | Scope, in brief |
| --- | --- | --- | --- | --- |
| `d150-v1-held-sphere` (`validation/tissue/secreted_species_protocol.json`) | 14 Nov | `secreted-species-v1-qualified-2026-11-14` | Every item passed | @3's faces and turnover's first-order clearance in a held sphere; exchange only in guard tests |
| The S5 protocol | 14 Nov (3b73579b) | `cell-division-s5a-qualified-2026-11-14` | Every judged item passed | Partition, bridge closure, insertion@2 and lumen@2, against R-ops and R-tissue |
| E07-v1 | Scorer frozen at 6b6912b | `e07-v1-judged-2026-11-14` | 8 of 15 predictions held | An experiment on @3's sheet; it qualifies no law |
| The coupling operator's protocol | abe4ef5c | `coupling-v1-qualified-2026-11-15` | 47 of 47 | `species_regulated_availability@1`, numerically |
| `mg0c-turing-v1` | 5ab4326a | `mg0c-v1-qualified-2026-11-15` | 55 of 55 | `local_species_reactions@1`'s driven mass action of orders 0, 1 and 3 at outside nodes |
| `fr4-acidification-v1` | 17 Nov, on main | `fr4-v1-qualified-2026-11-17` | 21 of 21 | Maintained fuel only; the K⁺ counter-ion only; a lumped population of 1,000; fixed volume |
| `fr5-transfer-v1` | 17 Nov, on main | `fr5-v1-qualified-2026-11-17` | 51 of 51 | FR-4's scope plus damage, a proton pore and a neutral cargo pore; ionic pores refused; the build at 32a1d439 |
| `fr10-dose-schedule-v1` | 407ba164 | `fr10-v1-qualified-2026-11-17` | 31 of 31 | Neutral formula units, held baths, steps inside the measured region |
| `fr1-closed-compartment-v1` | 05a8d193 | `fr1-v1-qualified-2026-11-18` | 44 of 44 | The neutral first version: no ion route, a zero charge anchor, a held-bath topology, one compartment per node |
| `fr3-site-occupancy-v1` | 1b838d75 | `fr3-v1-qualified-2026-11-18` | 51 of 51 | One neutral, impermeant ligand; the face-free first acceptance |
| `fr6-a5pp-v1` | 555d8771 | `fr6-a5pp-v1-qualified-2026-11-18` | 18 of 18 | Two pump-free cells; a gate-free K⁺ leak driven through the regulatory state from a per-cell prior |

Also judged, before these: the BETSE parity rungs (PROGRESS's plan table); MG0a and MG0b; MG1's
version 2 (57 of 57, weaker evidence after version 1's 52 of 57); and `resolved_pump_water@1` and
`@2` (11 November, ROADMAP).

**A caution on the FR verdicts.** FR-1's, FR-4's and FR-5's verdicts predate refusal 4 version 1.3,
refusal 5 version 1.2 and seam A. Each covers the build it judged; FR-5's scope names 32a1d439. Later
core landings keep those worlds' programs bitwise, through crossrev's FR set and FR's landing set
(CORE_SEAMS §18). That is a gate, not a new verdict.

## 1.3 The families

Each family has the same blocks: on main, designed, held, consumers, and then prerequisites,
effort and the main risk.

### Family 1. Electrodiffusion, channels and the field

**On main (modular).**
- **The field:** @3's capacitor solve (`resolved_capacitor_components_current_continuity@1`, in
  `numerics/surface_field.py`), with the solver declared per world (D147).
  - The solve caps at 2,048 nodes.
  - Any field-input provider lowers the cap to 64 field nodes (MITOCHONDRIA_DESIGN, addendum A.3).
- **Channel laws as @3's law homes:**
  - `kleak_always_open@1`, `naleak_always_open@1`, `nav1p2_m3h_regularized@1` and `kir2p1_mh2@1`;
  - the Kv1 laws, registered as law homes (c7d570a0);
  - `clleak_always_open@1` (D228 item 3; 6ed4b280, tag `f-chloride-leak-landed-2026-11-19`).
  - Channel populations carry Na⁺, K⁺ and Cl⁻ (`surface_pump_v3_spec.SPECIES_VALENCE`). They do not
    carry Ca²⁺.
- **Junctions:** `junction_voltage_relaxation@1` and `delayed_first_order_junction_formation@1`,
  with junction heat booked by `trapezoid_nonnegative@1`.
- **Routes on the passive-routes kind:**
  - `inward_rectifier_linear_driving_force@1` (D228 item 2; 2db46727, tag
    `rectifier-landed-2026-11-19`). Its coefficients are unsourced today.
  - `proton_constant_field_leak@1` and `passive_neutral_permeation@1`.
- **Faces:** `logmean_electrodiffusion@1`. **Pacing:** `electrode_current_injection@1`.
- **Judged:** the BETSE parity rungs (PROGRESS's plan table, steps 3–5, on CPU and the L4). E07-v1
  is a judged experiment that runs @3's channels (`e07-v1-judged-2026-11-14`); it scored predictions,
  and does not qualify the laws.
- **Older catalogues:** the channel catalogues in `laws/channels/` up to the 35-law one serve
  `resolved_tissue@8`, which stays as D167's parity reference. The four tables of
  `resolved_tissue@9` to `@12` left with the legacy cleanup; they held no kernel.
- **D211's port programme: open, and it continues after the legacy cleanup** (D386, 25 November
  2026). Its 54 law IDs, by what each group waits for. Every kernel named here stays in live `laws/`
  with its reference and a kernel-level test. A law is registered on @3 when its module lands, and
  a registered law is not thereby qualified.

  | Group | Laws | Kernel | Waits for |
  |---|---|---|---|
  | Kv1.1 to Kv1.4 and Kv1.6 | 5 | `kv1p1_mh2` to `kv1p6_mh` | done: registered on @3 |
  | Voltage-only K and Na: Kv2.1, Kv2.2, Kv3.1 to Kv3.4, K_fast; Nav1.3, the three rat Nav laws, Nav1.6 | 12 | `potassium_catalog`, `sodium_catalog` | one module each; no engine feature |
  | Voltage-only, one gate: the three dynamic Morris-Lecar K laws | 3 | `morris_lecar_channels` | one module each (not checked: whether @3's gate template takes one gate as it stands) |
  | CaV1.2, 1.3, 2.1, 2.2, 2.3, 3.1, 3.3; Ca_L2, Ca_L3, Cav_G | 10 | `cav_channels`, `calcium_catalog_extra` | calcium through channels, being built |
  | HCN1, HCN2, HCN4; the HCN leak and the two cAMP-shifted laws | 6 | `hcn_channels`, `hcn_extra_channels` | the same: they carry calcium |
  | The seven instantaneous Morris-Lecar laws | 7 | `morris_lecar_channels` | G-2, a law without a gate |
  | Calcium-activated K | 1 | `calcium_activated_potassium` | G-3, a channel that reads a species, which the cardiac plan's H1 holds |
  | Store pump and release, IP3 release, the Na/Ca exchanger | 4 | `er_calcium`, `plasma_calcium`; IP3 release only at the tag | the calcium store, the release factor and the exchanger, being built |
  | The finite-ATP store pump | 1 | only at the tag | row fuel, a request the user may make |
  | NKCC and the generic symport | 2 | only in legacy today | ported in the cleanup, as modules on the transporter kind |
  | The cell-zone transporter | 1 | only at the tag | left there (the user, D386) |
  | Mitochondrial passive; `junction_flux()` | 2 | not a port | nothing |

**Designed.**
- Cardiac H1 (HUMAN_CARDIAC_LAWS_DESIGN §4.5, §8):
  - Ca²⁺ as a permeant ion;
  - per-law gate counts and domains;
  - a linear driving force, and coefficients as data;
  - routes that face a pool;
  - then eight channel laws of O'Hara–Rudy 2011.
- Track E (EXCITABLE_TISSUE_DESIGN): `junction_ungated@1` and the junction step condition (§4.2).
- FR-16: a two-state junction gate, per-species floors, and min and mean docking rules.
- FR-17: field solves beyond 2,048 nodes. FR-1's condensation door is the preferred route (D219).
- Field-input providers beyond 64 field nodes: a design note after the Xenopus lane's first decision
  (D228 item 7).

**Held.**
- Markov-form laws and subspace calcium are closed in version 1 (INNER_MODEL_V4_DESIGN §13.1).
  Opening subspace calcium goes to the user (D184).
- FR-16 and FR-17 are scheduled with their owners and not started (D219, D222).

**Consumers.**
- Cardiac H1 and H4, and FR-11's human loop.
- The Xenopus lane's XC0: Kir4.1 through the rectifier, and a Cl⁻-only patch (D228).
- The gap-junction replication: FR-16 (its F3–F5) and FR-17 (its F7, for the 3D table).
- FR-8: NaV activation limits coarse steps (rung 0).
- The heredity work, at 825 nodes.
- Mitochondria with many compartments per cell (FR-17, or condensation).

**Prerequisites, effort, risk.**
- H1's seams take 6.5–8.5 days (the cardiac note's estimate), then the eight laws.
- FR-16 is a short design, then about 3–6 days (estimate).
- Condensation takes 3–5 days (the mitochondria addendum's estimate).
- **Main risk:** the step. NaV resolution and the junction step condition bound it, whatever the
  integrator (FR-8 rung 0; D231).

### Family 2. Transport: pumps, cycle laws, symporters and routes

**On main (modular).**
- **The cycle kind is `cells.transporter@1`,** with two layouts (CORE_SEAMS §14, ruling A3).
  - Version 1's layout keeps FR-4's programs bit for bit.
  - Seam A's population axis (ee30e5d9, tag `seam-a-landed-2026-11-19`) holds any number of
    populations per patch. Each runs its law's form in `laws/cycles/forms.py`: `factored`, `diagram`
    (Hill cycles from directional diagrams) or `net_flow`.
  - Each population declares its N/P orientation. A mode may move charge across the membrane, as
    long as the mode conserves charge across its two ends.
  - Wegscheider's condition is checked per Hill cycle at parse (CORE_SEAMS §16).
- **Free energies:**
  - every kind declares `FreeEnergyEntry` (69ac2ba7, 4e6ca60e);
  - each entry is checked against the registry's sum of ν μ°/RT (bd9881d5);
  - the old 3-tuple form is refused (985c6a44).
- **Cycle laws:**
  - `atp_driven_transporter_mass_action_positive@1`, a neutral role, on held or finite fuel;
  - `proton_atp_mass_action_positive@1`, FR-4's pump, on held fuel;
  - `na_anion_symport_factored@1` (D228 item 1; 845ee670, tag `symporter-v1-landed-2026-11-19`):
    electrogenic and fuel-free, with n_Na from 1 to 4. It is refused at a compartment's node by
    design.
- **@3's own pumps:** `nak_atp_mass_action_positive@1` and `ca_atp_mass_action_positive@1`, on
  maintained pools.
- **Routes:** the passive-routes kind's laws (family 1); `k_anion_symport_mass_action@1` with its
  operator.
- **Judged:** FR-4's protocol (21 of 21) covers the proton pump on held fuel, with the buffer and
  the leak. FR-5's (51 of 51) covers its source kinds.
- **Compared:** the population axis against the code-blind references at every registered state
  (`tests/unit/test_cycle_kind_references.py`).
- **This pass's limits on the population axis** (the kind's own docstring, read at 7f357cfb):
  - hosts are membrane patches only;
  - a mode that changes a species at P without changing it at N is refused ("chemistry at P");
    lifted by K3, which landed on 20 November 2026 (merge c88f5338);
  - held rows are neutral;
  - moved fuel at a node whose proton row moves is refused (§5.2's boundary). The general
    closure's exception is not wired: `_general_closure_nodes` returns `()`. K1 wired it, landed on
    20 November 2026 (206d5c7b), with the binder-form deferral (4ca478b8).

**On branches, not on main.**
- Symporter version 2, `na2_anion_symport_diagram@1`: an eight-state diagram with named rates, and
  the cycle form's named k0 and ζ (core-pass-kinds-7 at 967922e6).
- Availability schedules for the population axis (D228 item 5; core-pass-kinds-8 at 6f55940c). On
  main a population's availability is fixed at 1.

**Designed.**
- Cardiac H2: the exchanger (`sodium_calcium_exchange_cycle@1`), uptake and pumps on the kind
  (HUMAN_CARDIAC_LAWS_DESIGN §3.4–§3.6).
- The mitochondrial cycle laws (MITOCHONDRIA_DESIGN §1.2; Part 2 here).
- ATP synthase as a machine (MOLECULAR_MACHINES_DESIGN §10).
- A route between two pools, as a new host kind (CORE_SEAMS §2).
- Light-driven pumps: a design note after the Xenopus lane's decision point (D226).

**Held.** Nothing by decision. Printed source laws that fail the screen enter only with declared
departures, on which the user rules (CORE_SEAMS §16).

**Consumers.**
- The Xenopus lane: the SLC5-type symporter and its schedules (XC0, XC1).
- Cardiac H2.
- Mitochondria.
- FR-7's closed loop: the Na/K pump with Na-leak units (D231).
- Finite fuel (family 8).
- Syn3A: the synthesis cycle running in reverse (MITOCHONDRIA_DESIGN §4).
- Machines M1.
- The heredity work: the KCC law's robustness (CURRENT_PLAN's coupled-renewal gate).

**Prerequisites, effort, risk.**
- Symporter version 2 and the schedules are built. They need only their gates.
- The Na/K and Ca pumps as cycle laws on the kind, so that one pump representation draws fuel:
  about 2–4 days (estimate).
- A host kind for routes between pools: 3–5 days (the cardiac note's figure for its pools).
- **Main risk:** two pump representations. @3's pumps on maintained pools and the kind's laws cannot
  share a finite ATP economy until the pumps move. And one owner holds `kinds/transporter.py`.

### Family 3. Chemistry: reactions, turnover, exchange and charged species

**On main (modular).**
- `local_species_reactions@1` with `ideal_detailed_balance_mass_action@1` (D152). It is judged
  within MG0c's scope (55 of 55; `mg0c-v1-qualified-2026-11-15`).
- **FR-15 S1,** charged species in reactions, in place under D148 (ddb52790, tag
  `fr15-s1-landed-2026-11-19`; development).
  - Every reaction conserves charge.
  - A charged row stays off @3's routes unless it is a declared counter-ion.
- `scheduled_species_turnover@1` and `scheduled_species_exchange@1` (D150). D150's protocol judged
  the faces and turnover's first-order clearance, within its held-sphere scope
  (`secreted-species-v1-qualified-2026-11-14`); exchange entered it only through guard tests.
  Exchange's first judged acceptance came with FR-1 (`fr1-v1-qualified-2026-11-18`).
- `scheduled_bath_composition@1` (FR-10), judged (31 of 31). Steps are admitted only inside measured
  regions.
- **The species registry** is the one authority for standard potentials, with seam E's checks.
- **The cap:** 1,024 rows wherever a species operator is declared (FR-43 / D315, 16 by FR-9; `species_common.MAX_SPECIES`).
- **Legacy:** `network_reactions@1` and the calcium-energy family's networks.

**On a branch.** FR-15 P2: a charged constant-field route law, `passive_constant_field_permeation@1`,
on patches first (core-pass-operators-3-p2 at f2cf3cfb). Junction hosting waits for the @3 owner's
two answers (FR-15's entry).

**Designed.**
- `scheduled_species_turnover@2`, for charged clearance when a consumer needs it (FR-15).
- Syn3A's F8, metabolism at scale: a sparse, stiff network well past 16 species
  (SYN3A_MINIMAL_CELL_TRACK §4.3).
- Syn3A's F11, a stochastic regime: exact stochastic reactions per node with keyed streams, then a
  hybrid split by copy number.

**Held.** Exchange stays neutral (FR-15's rulings). Each raise of the cap is a D148 change with a
guard world (D165).

**Consumers.**
- The Xenopus lane: butyrate and serotonin chemistry need charged species (D228 item 4).
- The gap-junction replication: the charged microRNA (FR-15's F2).
- FR-7: the precursor.
- Finite fuel: regeneration.
- Syn3A's Stage 4.
- Mitochondria: the NADH supply now, substrate reactions later.
- The heredity work: turnover.

**Prerequisites, effort, risk.**
- P2 is in progress. Junction hosting follows the @3 owner's answers: about 2–4 days (estimate).
- F8 and F11 are large, about 10–20 days each (estimate), with no design note yet.
- **Main risk:** scale. The 16-row cap and the dense per-node treatment block metabolism, and
  deterministic amounts misstate low-copy species.

### Family 4. Binding, buffers and pH

**On main (modular).**
- `cells.rapid_proton_buffer@1`, FR-4's closure (version 1).
- In the same kind, the general closure `rapid_binding@1`: several ligands on binders whose forms
  the registry declares.
  - Seam C stage 2 (aecbaed1), C4's joint margin (4736d974), C5's release steps (6ec01be1) and
    §5.2's admission (b546c99d).
- P1's predictor for stage reads under a free-amount closure (9e181b08). It applies to
  `rapid_binding@1` only. Version 1 keeps the earlier predictor bit for bit.
- `cells.ph_condition@1` with `ph_conditioned_factor@1`.
- `site_occupancy@1` (FR-3).
- **Judged:** FR-4 (21 of 21) and FR-3 (51 of 51; `fr3-v1-qualified-2026-11-18`).
- **Compared:** seam C against the code-blind references.

**Not yet on main.**
- **No built-in law moves a closure row.** A mover must declare base forms and read `rapid_binding@1`.
  None does, so the tests use a test-namespace law (`tests/unit/test_rapid_binding_world.py`). The
  docstrings still say no kind declares `role_species`; the transporter's landed at c9549dfc, and
  the law side is what is missing.
- **No moieties in the registry** (the binding owner's item 6). The cycle references' moiety plant
  waits for it.
- FR-3's shared SSPRK(3,3) block, FR-3's own milestone.

**Designed.** H⁺ and Mg²⁺ on ATP, ADP and Pi (MITOCHONDRIA_DESIGN §1.3). The cardiac Ca²⁺ buffers
(HUMAN_CARDIAC_LAWS_DESIGN §3.3).

**Held.** Nothing.

**Consumers.** Mitochondria; cardiac H2; FR-4 and FR-5 with faster pumps; Syn3A's pH stage (subject
to D173's licence condition); FR-15 P2.

**Prerequisites, effort, risk.**
- Item 6: 0.25–0.5 days (CORE_SEAMS_STEP0 §4.2).
- Binder data for nucleotides, or for Ca²⁺: about 1–2 days each (estimate).
- **Main risk:** the rapid-equilibrium envelope fails at fast transport. A kinetic binding would
  then be needed.

### Family 5. Compartments and organelles

**On main (modular).**
- `cell_owned_compartments@1` (FR-1), judged (44 of 44; `fr1-v1-qualified-2026-11-18`).
  - Refusal 4 version 1.3 (e515b87b) admits a kind's move at a compartment's node when its law
    declares the step term that its kind supplies.
  - Refusal 5 version 1.2 (af1206e2) admits a charged anchor where an admitted operator charges the
    node.
- FR-5's transfer, with leak and reseal, judged (51 of 51; `fr5-v1-qualified-2026-11-17`).
- The division cleft: `restricted_cleft_lumen@2`, judged with S5a. Its `@1` is on main too.
- The host-side identity map (D174), which "partly holds" B2 of INNER_MODEL_V4_DESIGN.
- **Legacy:** `er_calcium@1` and `ip3_er_release@1`. And `resolved_calcium_energy_mitochondria@1`,
  whose mitochondrial law is passive: no respiration and no ATP.

**Not built** (FR-1's doors, [CLOSED_COMPARTMENT_DESIGN.md](CLOSED_COMPARTMENT_DESIGN.md) §8).
- Creation (C), division (D), fusion and fission (F), replacement (R), volume (V), condensation and
  floating topology.
- The compartment operator refuses water, insertion, the lumens and the division closers
  (`compartments.CONFLICTS_VIEW`).
- No pool at the cell's potential, and no route between pools. The host table has patches and
  junctions only (`surface_pump_v3.HOST_KINDS`).

**The organelles, by engine feature.**
- **Mitochondria:** Part 2.
- **ER and SR:** the cardiac note's pools at the cell's potential (§3.2), unruled. Legacy ER calcium
  is the reference.
- **The endosome and lysosome path.** On main: a closed compartment with a proton pump, a buffer and a
  leak (FR-4); state-conditioned transfer (FR-5); membrane retrieval into a compartment pool (FR-2).
  Missing: the creation and fusion doors; the volume door; and Cl⁻ counter-ions on a bounding patch,
  which need the implicit patch (COMPARTMENT_PH_TRANSFER_DESIGN §7.3).
- **Vesicles:** FR-2's one lumped pool per cell (D217). Cohorts or discrete vesicles come later.
- **The nucleus:** only the user's wish that the nucleus, the Golgi and ribosomes be "modeled to
  some extend" (FR-13's entry). There is no design.

**Designed.** CLOSED_COMPARTMENT_DESIGN §8; MITOCHONDRIA_DESIGN and its addendum (D193, D210);
HUMAN_CARDIAC_LAWS_DESIGN §3.2; ROADMAP item 9 (the Golgi and trafficking, planned, not started).

**Held.** Subspace calcium. Nested capacitors (refused by @3's topology, FR-1 §1.4). Stochastic
partition of discrete organelles, which is outside door D's first version.

**Consumers.**
- FR-1 to FR-5's requester, the requesting study: the later doors.
- Mitochondria.
- Cardiac H2: the SR.
- FR-2's later versions.
- Division: organelle inheritance.

**Prerequisites, effort, risk.**
- The doors need seam B's verbs (the merge verb is a collected requirement, CORE_SEAMS §4.6) and
  composition M2–M5's current reads.
- The addendum puts the dynamic doors at 25–39 days.
- **Main risk:** the 64-field-node cap whenever an event door is declared, and running out of slots.
  S5 reuses none, and reuse with re-anchoring would need a decision against D057 (the mitochondria
  addendum's B.2).

### Family 6. Trafficking, insertion and protein abundance (FR-2, FR-7)

**On main (modular).**
- `scheduled_membrane_trafficking@1`, FR-2 version 1 (1bd35184): membrane and channel retrieval and
  recycling into one pool per cell, with charge following the membrane.
  - Development. Compared against code-blind references: run 1 matched 770 of 782 rows; run 2
    matched 782 of 782 after a blind erratum, which is weaker evidence (d2dc7b8c, tag
    `fr2-comparison-landed-2026-11-19`).
- `scheduled_membrane_insertion@2`, judged with S5a. `scheduled_membrane_insertion@1` and
  `membrane_entity_state@1` are on main too.
- `population_unit_turnover@1`, FR-7 F1 (7fb27a92, tag `fr7-f1-landed-2026-11-19`; development).
  - A finite precursor becomes channel units through maturation pools, with first-order removal.
  - It is a scoped exception to D177, and its refusal is simulation-wide (D232).
- `species_regulated_availability@1`, judged for the coupling operator and FR-6's A5″.
- Its `@2` with B1′'s rate route (ee43b082; development), and R2's control view (6c501ab3).

**On branches, not on main** (development):
- FR-7's references (tag `fr7-references-registered-2026-11-19`);
- F2, the population abundance source on `species_regulated_availability@2` (fr7-f2 at dbd4d9e0);
- F3, the producer's assembly rate as a B1′ target (fr7-f3 at cf7145ad).

**Designed.**
- FR-7's F2–F4 and its closed loop: the Na/K pump with Na-leak units, gated on an engine probe of
  the loop's gain (D231). Its references are R-chain, R-clear and R-loop.
- FR-2's version 1.1, fluid-phase uptake, and later versions
  ([MEMBRANE_RETRIEVAL_DESIGN.md](MEMBRANE_RETRIEVAL_DESIGN.md)).
- ROADMAP item 9.

**Held.**
- Catalogue stage 3 (D145).
- FR-2 version 1 draws no machinery fuel (D217).
- FR-7's producer excludes recycling, insertion and division in the same simulation (D232).

**Consumers.**
- The requesting study (FR-2, FR-7).
- FR-8: FR-7's loop is its first scientific consumer (D217).
- The heredity work: the junction-channel unit (U1) for renewal.
- The gap-junction replication: expression-coupled junctions (FR-16's F5).
- The Xenopus lane: the regulation-to-behaviour path belongs to FR-7's family (D226).

**Prerequisites, effort, risk.**
- FR-7's loop is 10–16 days in all (its note's estimate); F1 is done.
- Before FR-2's next version: one owner for insertion, and one for terminal removal, per population
  (D232).
- **Main risk:** the closed and cut arms may not differ beyond the comparison band. D231 declares
  the fallback: the question returns to the user.

### Family 7. Gene expression and regulation

**On main, as building blocks only.**
- Production from a finite precursor, with maturation delays and removal (`population_unit_turnover@1`).
- A regulatory state with a rate bound, driving availability (`species_regulated_availability@1`)
  or rates (`@2`, B1′).
- Mass-action reactions (`local_species_reactions@1`).
- An isolated regulatory model, `emt_mirna@1` ([GRN_WETLAB_VALIDATION.md](GRN_WETLAB_VALIDATION.md)).

**Held.**
- D145 holds the gene-regulation track, with Cortés-Poza Phase 1 and catalogue stage 3. D179 kept
  the hold.
- D218 narrows it. Physical, state-mediated production feedback is admitted, only through B1′. Each
  loop declares its timing and range, and is verified whole, under timestep refinement, with a
  cut-feedback control.
- Refusals kept: instantaneous algebraic cycles; and a population's availability multiplied by its
  own abundance where that abundance already sets its conductance.

**Designed.**
- [GRN_WETLAB_VALIDATION.md](GRN_WETLAB_VALIDATION.md): logged, not started.
- Syn3A's F10: polymerisation laws for transcription and translation, held under D145.
- Machines' U4: the ribosome and D145, open (D209).
- A regulatory state that drives cell behaviour: a design note after the Xenopus lane's first
  decision (D228 item 7).

**Transcription and translation as physics** (this note's framing).
- Production is polymerisation. It consumes finite precursors (nucleotides, amino acids) and fuel
  (ATP, GTP). Finite machine populations (polymerases, ribosomes) do the work, with delays. Material
  and energy go into one account.
- On main: the producer's material account and delays; B1′'s regulated rate; moved fuel rows
  (family 8).
- Missing:
  - polymerisation laws;
  - a fuel draw on producers, which D217 assigns to the common energy interface;
  - low-copy stochastic counts (family 3's F11);
  - machines as populations (FR-13).

**Consumers.** The heredity work (the gene-regulation layer); Syn3A's Stage 4; the Xenopus lane's
XC1 (the butyrate route); the gap-junction replication (regulatory laws as declared laws, its F6);
the REVERT plan; FR-7.

**Prerequisites, effort, risk.**
- A design note first: about 2–3 days (estimate).
- Anything beyond D218's door needs the user's decision on D145.
- **Main risk:** a network fitted to the data it reproduces. GRN_WETLAB_VALIDATION warns that most
  candidate benchmarks are not independent, and that the public perturbation data are snapshots.

### Family 8. Metabolism and energy

**On main (modular).**
- Fuel as shared inventory rows (D176, F2):
  - `maintained_held_rows@1`: held, with its work booked;
  - `finite_fuel_rows@1`: moved, with its stored energy booked. On the population axis it runs
    under the neutral ATP-driven law.
- Seam A's references compare a finite-fuel world (`ff_neutral_n1`) state by state.
- Kind ledgers for moieties (ac43139d). D3's potentials check and `FreeEnergyEntry` (seam E).
- Regeneration as D152 reactions.
- @3's Na/K and Ca pumps on maintained pools.
- **Legacy:** `finite_atp_adp_pi_transformed@1` ([FINITE_ENERGY_POOLS.md](FINITE_ENERGY_POOLS.md)), a
  reference (D196).

**Not yet on main.**
- **The first finite-fuel acceptance** has no engine world and no protocol. That is `finite-fuel-v1`
  on R-fuel's world: depletion, regeneration and recovery (COMPARTMENT_PH_TRANSFER_DESIGN §17.4).
  `validation/compartment_ph/protocols/` holds FR-4's and FR-5's protocols only.
- Moved fuel beside moving protons is refused (§5.2).
- D175's four fields are reserved, and refused at registration (`registry/laws.py`).
- No pump of @3 draws finite fuel.

**Designed.**
- COMPARTMENT_PH_TRANSFER_DESIGN §17, with the lead's rulings D1–D5.
- CURRENT_PLAN item 4: finite fuel as D175's first executable consumer, with a reduced regeneration
  closure against a small detailed network.
- Mitochondria M6's demand pulse (MITOCHONDRIA_DESIGN §7).
- Syn3A's F9: fuel made and spent, with GTP, UTP, CTP, the dNTPs and PEP (SYN3A_MINIMAL_CELL_TRACK §11).

**Held.** Nothing by decision. The proton pump on finite fuel waits for charged hydrolysis
(COMPARTMENT_PH_TRANSFER_DESIGN §17.5, D1 (b)).

**Consumers.** Mitochondria; cardiac (ORd holds ATP fixed today); Syn3A's Stage 4 and
*M. pneumoniae*'s Stage 4a; machines M1; FR-2's later machinery fuel; FR-7 (D231 declares the
pump's fuel pools); origin of life, in its own family.

**Prerequisites, effort, risk.**
- `finite-fuel-v1`: about 1.5–2 days, plus 1–3 CPU-hours (COMPARTMENT_PH_TRANSFER_DESIGN §17.6).
- §5.2's exception at closure nodes: about 1–2 days (estimate).
- The pumps as cycle laws (family 2).
- D175's minimal static contract: unestimated (CURRENT_PLAN).
- **Main risk:** one authority for potentials across reactions, kinds and the closure. A small
  disagreement shows as energy from nothing.

### Family 9. Signalling: Ca²⁺, second messengers and junction-crossing signals

**On main (modular).**
- `species_regulated_availability@1` and `@2`: a species drives channel availability or rates
  through a regulatory state. Judged for FR-6's A5″.
- FR-15 S1: charged species in reactions.
- `passive_neutral_permeation@1` on junction hosts: admitted, not qualified (the gap-junction
  replication's Q1).
- D150's secreted-species transport, judged within its held-sphere scope.
- `resolved_pump_tissue@2` carries Ca²⁺ and a plasma-membrane Ca pump (BETSE parity rung 1: version 2
  passed, weaker evidence after version 1 failed).
- **Legacy:** the calcium families, `er_calcium@1` and `ip3_er_release@1`.
- **Not on @3:** Ca²⁺ in channel populations, Ca²⁺ buffers and pools.
- **Second messengers:** only the legacy IP₃ release. No modular design exists for IP₃, cAMP or
  others. FR-15 names second messengers among the junction-crossing species it would serve.

**Designed.**
- Cardiac H2 (HUMAN_CARDIAC_LAWS_DESIGN §3):
  - pools at the cell's potential;
  - the Ca²⁺ buffer read on the general closure;
  - uptake, leak and exchange;
  - the release law, which reads the L-type current, so a kind reads @3's channel current (CORE_SEAMS §2);
  - CaMKII through the routing door.
- Mitochondria M7: uniport, exchange and matrix Ca²⁺ buffering.
- FR-15 P2 and junction hosting; FR-16.
- The gap-junction replication's F8, a neighbour-depolarisation mechanism, to be sourced first (D136).

**Held.** Subspace calcium. Calcium handling is rebuilt with the human cardiac laws, and the legacy
family is dropped after a coverage check (D196).

**Consumers.** Cardiac H2 and H3; mitochondria M7; the gap-junction replication; the Xenopus lane
(serotonin and its transporter); the heredity work (junction gating); FR-6's remaining items.

**Prerequisites, effort, risk.**
- H2 is 14–20 days, with the core owner's pools 3–5 (the cardiac note's estimate).
- **Main risk:** the release law's read of a channel current within one stage, and the opening of
  subspace calcium.

### Family 10. Mechanics, morphogenesis and division

**On main (modular).**
- `apical_vertex_mechanics@1`: MG1, judged version 2 (57 of 57), weaker evidence after the failed
  version 1.
- MG0a, MG0b and MG0c, judged.
- Division S5a, judged (`cell-division-s5a-qualified-2026-11-14`): `isopotential_partition@1`,
  `cytoplasmic_bridge_closure@1`, `scheduled_membrane_insertion@2` and `restricted_cleft_lumen@2`.
- Cell replacement: `scheduled_cell_replacement@2`.
- Water and volume: `ideal_osmosis_linear_compliance_water@1`, and `resolved_pump_water@1` and `@2`,
  qualified on 11 November (ROADMAP).
- B1's role-driven lifecycle for kinds at division and retirement (3fd9c17c).
- Composition M1, the fixed-read rule (c78462e7).

**Not yet on main.**
- Composition M2–M5: current volume, area, activity masks and capacity.
- B2: a kind's own entity axes beside a dividing closer are refused until B2's maps
  (`tests/unit/test_kind_lifecycle_roles.py`).
- State-triggered division (lifecycle M2), growth of material, and T1 transitions (MG2).

**Designed.** [MORPHOGENESIS_PLAN.md](MORPHOGENESIS_PLAN.md) (MG2–MG6);
[CELL_DIVISION_PLAN.md](CELL_DIVISION_PLAN.md) (Xenopus cleavage first, then *C. elegans*; D141);
OPERATOR_COMPOSITION_DESIGN (D191); Syn3A's F12–F14; cell migration and topology changes, a design
note later (D228 item 7).

**Held.** Mitosis machinery is out of scope for now (ROADMAP item 7). Lifecycle M2 is queued behind
the core and the priority features (D176 item 8).

**Consumers.** The division subjects (D141); Syn3A's Stage 5; the heredity work (renewal);
mitochondria (inheritance, door D); FR-4 and FR-5 on a growing compartment (D217's visible list);
the Xenopus lane later (migration).

**Prerequisites, effort, risk.**
- Composition M2–M5: 9.5–12 days, from CORE_SEAMS_STEP0 §4.2's series without M1, which has
  landed. B2: 1–1.5 days (the same table). Pumps on dividing cells: about 3 more (D191).
- **Main risk:** geometry as state. A changing capacitance needs its own charge law and work
  accounting (CELL_DIVISION_PLAN).

### Family 11. Assemblies and origin of life

**On main.**
- `cells.assembly_lineages@1`: GARD G1, development, frozen by D215, with its G2 references.
- `cells.assembly_lineages@2`: OL1's laws, development, verified 6 of 6 against OL5's code-blind
  references (tag `ol1-landed-2026-11-18`).
- OL5's references for OL2 and OL3 (e8759b48).
- `cells.relations@1` (D200, D202).
- Older assembly models: `capsid_graph@1`, `finite_bond_assembly@1`, `assembly_regulated_cell@1` and
  `assembly_regulated_cluster@1`.

**On branches.** OL2 milestone 1 (ol2-engine at 9190ae78: `cells.bilayer_geometry@1`,
`cells.phase_exchange@1`, `cells.membrane_permeation@1`; development). The `ol3-engine` branch.

**Designed.**
- [ORIGIN_OF_LIFE_ENGINE_DESIGN.md](ORIGIN_OF_LIFE_ENGINE_DESIGN.md) §0.2e's order: OL2 milestone 2
  (the osmotic lumen and lysis), OL3 milestone 1 (single-lineage division), OL2 milestone 3 (the
  shared pool and serial transfer), then OL5's probe roles.
- The self-replicator replication's R0 and R1 (D221).
- Machines M1 (FR-13).
- `cells.relations@2`'s requirements, from machines, mitochondrial fusion and GARD's same-time
  order (D209).

**Held.** OL work runs behind core and FR-1 to FR-10 (D230). R0 and R1 come after OL3 (D221, D222).
Folding is out of scope (D140).

**Consumers.** Origin of life (D212, D230); the self-replicator replication; machines; mitochondria
(GARD's partition rules for stochastic partition, the addendum's L3); Syn3A's lipid vesicles
(analysis only).

**Prerequisites, effort, risk.**
- The programme is 33–51 days (its note's estimate). R0 and R1 are 16–25 (D221).
- **Main risk:** two engines, the assembly family and @3's composite, drifting apart in their
  conventions.

### Family 12. Long-duration modes (FR-8)

**On main.**
- FR-8 stage 0 (f5025e6f; development).
- Rung 0 (6cec0fc4). Its registered verdict is "instrument not validated". Under a blind amendment,
  the cause is a pre-asymptotic transient.
- X2, `step_doubled_energy@1` (fd894b91). Registered and judged runs must select it, each with its
  own per-row cap (D224). It is scoped to ARS(2,2,2) and refused elsewhere.
- **Earlier work:** the optional long-horizon modes (D135). E is qualified; C's qual-01 failed
  (PROGRESS's plan table, step 11).

**On a branch.** Rung 1's registration (branch fr8-rung1, tag `fr8-rung1-registration-2026-11-19`).

**Designed.**
- [LONG_DURATION_MODE_DESIGN.md](LONG_DURATION_MODE_DESIGN.md)'s ladder (D224): rung 1 is N2 with the
  exponential junction-gate update; rung 2 is the slow integrator; face diffusion joins if 825-node
  tissue is a target.
- D232: run rung 1's control first, on today's integrator with X2. Then choose A (N2) or C (a
  fine-window executor) by its rules.

**Held.** The full solver build and an exact charged booking need approval (D217). Branch X has a
recorded trigger (D231).

**Consumers.** FR-8's requester, the requesting study; FR-7's loop at measured lifetimes; the
heredity work at 825 nodes; cardiac pacing to a periodic state; mitochondria's protocols of hundreds
of seconds; Syn3A's 105-minute cycle.

**Prerequisites, effort, risk.**
- N1 with N2, branch X and their qualification: 17–27 days (its note's estimate).
- **Main risk:** NaV resolution bounds the step whatever the integrator (D231).

### Family 13. What several families need

1. **Composition** (D191): M2–M5 (family 10). Growing compartments, pumps on dividing cells, and
   FR-7's live integration all need them.
2. **Levels of detail** (D175): four fields, reserved and refused at registration. Finite fuel is the
   first consumer (D214), then machines M1b, then mitochondria (lumped against individuals).
3. **`cells.relations@2`:** two parents, lives that are not cells, `degraded`, and an order for
   events at the same time (D209 L1; the mitochondria addendum's B.4).
4. **Keyed random streams in the composite,** for draws at events and stochastic partition (the
   addendum's B.3; MOLECULAR_MACHINES_DESIGN §10.4). The fixed-step checkpoint refuses random state;
   keyed counter-based streams need none.
5. **Field scale:** FR-17, or condensation; and field-input providers beyond 64 nodes (D228 item 7).
6. **Light as an energy input** (D228 item 7): the Xenopus lane's XC4, and the self-replicator's R1.
7. **Anatomy as data** (D226).
8. **Compute:** the packed GPU qualification (CURRENT_PLAN item 6) and GH200 access (D145).
9. **The module system's stage 1** (D185), at low priority (D214).

Not planned here: the Lean proofs project in `lean/`, an independent agent's work (D227).

## 1.4 Who needs what next

Consumers are named as the repository names them. "F" numbers refer to section 1.3's families.

| Consumer | Where it stands | Needs next | Waits on |
| --- | --- | --- | --- |
| FR-1 to FR-10 (the requesting study) | FR-1, FR-3, FR-4, FR-5, FR-6's A5″ and FR-10 judged; FR-9 landed; FR-2 version 1 compared (weaker evidence); FR-7 F1, and FR-8's stage 0 and rung 0, development | F6: FR-7 F2–F4. F12: FR-8 rung 1's control (D232). F5: FR-1's later doors. F4: FR-3's shared block. F6: FR-6's routing door (item 2) and gated populations (A5′) | The operators and @3 owners; composition M2–M5 for growing compartments |
| FR-11, looping replays | The planarian loop, built (development) | F1 and F9: the human cell (cardiac H1–H3) | The cardiac lane |
| FR-13, molecular machines | M0, illustration only | F2 and F8: D193's synthesis law. F13: D175's minimal fields | Mitochondria MT-1 |
| FR-15 to FR-17 | FR-15 S1 landed; P2 on a branch; FR-16 and FR-17 not started | F3: P2 and junction hosting. F1: FR-16. F1 and F13: FR-17, or condensation | The @3 owner's two answers; seats |
| The Xenopus lane (D225, D226) | XC0's general laws landed: symporter version 1, the rectifier, the Cl⁻ leak, charged reactions, the axes check | F2: symporter version 2 and the schedules (built, on branches). F3: FR-15 P2. F13: anatomy as data; providers past 64 nodes. F7: the regulation-to-behaviour path (a design note; beyond D218's door it needs the user) | Gates for the two branches; the lane's decision point after the matched replay (D226) |
| The Syn3A minimal cell (D173) | Probes only; S2-M1 designed | F3 and F13: a trace-start policy for S2-M1. F4 and F8: pH and fuel for *M. pneumoniae*'s Stage 4a (a licence decision). F3, F7 and F8: F8–F11 for Stage 4. F10: F12–F14 | Mostly not designed as notes |
| The human cardiac laws (D183, D184) | Decided; no engine code | F1: H1's seams. F4, F5 and F9: H2 (pools, Ca²⁺ buffers, the exchanger and pumps on the kind, release, CaMKII) | The F, @3, binding and kinds owners |
| Origin of life (D212, D230) | OL1 landed; OL2 milestone 1 on a branch | F11: OL2 milestones 2–3, OL3 milestone 1, OL5's probes. F13: `cells.relations@2` | D230's lanes and seats |
| The heredity work (E07; the coupled-renewal gate) | E07-v1 judged; E07-v2 proposed, with three questions for the user (CURRENT_PLAN) | F6: the junction-channel unit (U1), with contact maturation. F12: long horizons and 825 nodes. F2: the KCC law's robustness | FR-7's loop; FR-8; the user's E07-v2 answers |
| The gap-junction replication (D207, D219) | Its first stage and the 1D "neither" search on main (development) | F3: FR-15's F2 on junctions. F1: FR-16's F3–F5. F1 and F13: FR-17's F7, for Table 1. F8, sourced first | FR-15 P2's junction hosting; seats (D222) |
| Mitochondria (D193, D210) | Decided; no engine code | Part 2 | Part 2 |
| Division (D141) and morphogenesis | S5a, MG0 and MG1 judged | F10: composition M2–M5, B2, lifecycle M2 | The operators owner |

## 1.5 Ordering options and a recommendation

**The constraints.**
- Core and the FRs come first (D222). The Xenopus lane is one of the top three priorities (D225).
- OL work comes after core and FR-1 to FR-10 (D230).
- The user wants mitochondria startable right after this roadmap.
- Anything beyond D218's door into gene regulation needs the user's decision on D145.
- **One owner per file** (CORE_SEAMS_STEP0 §4.2 as amended by CORE_SEAMS §18). Two files carry most
  of the contention: `kinds/transporter.py` (the kinds owner) and `models/surface_pump_v3.py` (the
  @3 owner). The options differ mainly in what those two owners do next.

**Option 1. Requests and the Xenopus lane first.**
- **The order.**
  - Kinds owner: land symporter version 2 and the schedules, then move the Na/K pump onto the kind.
  - Operators owner: FR-15 P2, then FR-7 F2–F4, then composition M2–M5.
  - F owner: FR-16, then cardiac H1's seams.
  - @3 owner: FR-8 rung 1's control, then FR-15's junction answers, then FR-16's @3 part.
  - The energy spine and mitochondria start when these queues drain.
- **It unlocks first:** XC0 and XC1's transport (the Xenopus lane); FR-7's closed loop and FR-8 rung
  1 (the requesting study); then the gap-junction replication's Tables 2 and 3.
- **It delays** mitochondria by about two to three weeks (estimate), and cardiac H2.
- **Its risk:** the closure's first real mover and the cycle kind's booking stay untried by a real
  consumer. FR-7's pump stays on maintained fuel.

**Option 2. The energy spine and mitochondria on the kinds and binding owners; requests and the
Xenopus lane on the others.** *(Recommended.)*
- **The order.**
  - Kinds owner: land symporter version 2 and the schedules (both built), then moved fuel at closure
    nodes, the trapezoid for the kind, and the Δp readout (Part 2, K1–K4).
  - Binding owner: item 6 (moieties), then the nucleotide forms (Part 2, B1–B2).
  - @3 owner: P1′, half a day, then Option 1's order.
  - Two new agents start MT-1: the mitochondria lane agent (the laws and `validation/mitochondria/`)
    and the MR1 agent (the code-blind reference, from day one). A component-references agent joins
    once the laws' appendix exists.
  - Operators and F owners: Option 1's order.
  - After MT-1a: `finite-fuel-v1`, and the Na/K pump on the kind with finite fuel.
- **It unlocks first:** mitochondria MT-1 within days; MR1 at once. Then finite fuel, which serves
  FR-7's pump, cardiac H2's exchanger pieces, machines M1's synthesis law and Syn3A's synthesis
  cycle.
- **It delays** nothing in D222's order, if the new seats exist. The Na/K pump's move slips by
  about a week (estimate).
- **Its risk:** the kinds owner is the bottleneck. The option needs two new seats at the start and
  three at peak.

**Option 3. The excitable cell first.**
- **The order.** F owner: H1's seams. @3 owner: Ca²⁺ in channel populations and a host kind for pool
  routes. Binding owner: Ca²⁺ buffers. Kinds owner: the exchanger and pumps on pools. Mitochondria
  afterwards, straight into a cardiac cell (mitochondria M6 and M7).
- **It unlocks first:** cardiac H1–H3 and FR-11's human loop (33–48 days for H1–H3, the cardiac
  note's estimate).
- **It delays** FR-16, which shares the F owner, and mitochondria, by weeks.
- **Its risk:** calcium's openings need the user's ruling first (D184). It opens the most new seams
  at once.

**Option 4. Composition and division first.**
- **The order.** Operators owner: composition M2–M5, then B2 with the kinds owner, then lifecycle M2.
  FR-7's F2 and FR-15 P2 come later.
- **It unlocks first:** growing compartments, pumps on dividing cells, Xenopus cleavage (D141),
  Syn3A's Stage 5 groundwork, and organelle inheritance.
- **It delays** FR-7's loop and FR-15 P2.
- **Its risk:** no protocol is ready to judge it soon, and D176 item 8 queues lifecycle M2 behind
  the priority features.

**What each option unlocks first, by consumer** ("1st" means within the first round of owner work;
the rest follow in order).

| Consumer | Option 1 | Option 2 | Option 3 | Option 4 |
| --- | --- | --- | --- | --- |
| FR-7, FR-8 (the requesting study) | 1st | 1st (pump on finite fuel soon after) | 2nd | 2nd |
| The Xenopus lane | 1st | 1st | 2nd | 2nd |
| The gap-junction replication | 1st (FR-15, FR-16) | 1st (FR-15), 2nd (FR-16) | 2nd | 2nd |
| Mitochondria | 3rd | 1st | 3rd (in a cardiac cell) | 3rd |
| The human cardiac laws | 3rd | 2nd (shared cycle and closure pieces) | 1st | 3rd |
| Syn3A | 3rd | 2nd (fuel, synthesis cycle) | 3rd | 2nd (division groundwork) |
| The heredity work | 2nd (FR-7, FR-8) | 2nd | 3rd | 2nd (renewal through division) |
| Division and morphogenesis | 3rd | 3rd | 3rd | 1st |
| Origin of life | Unchanged (D230) | Unchanged | Unchanged | Unchanged |

**The recommendation: Option 2.** The reasons, in plain words:
- **It does what the user asked without displacing D222 or D225.** The kinds owner's two Xenopus heads
  are already built, so they land first. The operators, F and @3 owners keep their request and
  Xenopus order.
- **The energy spine is core work, and it is shared.** Seam C's first real mover, seam E's
  moieties, the cycle kind's booking and §5.2's exception are general features. Mitochondria, cardiac
  H2, Syn3A's fuel and machines M1 all need them, and FR-7's loop already declares its pump's fuel
  pools (D231).
- **It keeps one owner per file.** New mitochondrial law modules go to the mitochondria lane, as
  D209 says (Part 2, §2.4); the kind file stays with the kinds owner.
- **Its cost is two new seats at the start and three at peak** (section 2.4 lists the roles). Whether
  they fit the cap of seven beside today's seats is the lead's count. If they do not fit, Option 2
  becomes Option 1, with mitochondria's readiness steps (MR1, P1′) running first.

**In every option:**
- gene expression stays at a design note until the user decides on D145;
- OL work follows D230;
- composition M2–M5 follows FR-7 on the operators owner, unless Option 4 is chosen.

---

# Part 2. Mitochondria readiness

## 2.1 The decided direction

- **D193** (16 November 2026), on [MITOCHONDRIA_DESIGN.md](MITOCHONDRIA_DESIGN.md):
  - **One law set** for mitochondria and bacteria (*E. coli*, JCVI-syn3A), with one thermodynamic
    cycle form.
  - **One effective mitochondrion per cell first:** a lumped node of N identical members, exact for
    identical members.
  - **Isolated cardiac mitochondria first,** then mitochondria in a cardiac cell (D183).
  - **The source:** Beard 2005 (PLoS Comput Biol 1(4):e36) with its 2006 correction (2(1):e8). The
    PDF is the version of record; the web XML's Eq. 22 is stale.
  - **Probe P1 first,** because the membrane-potential mode is stiff.
  - **The comparison is approved:** (A) an independent whole-organelle reference, in two arms;
    (B) the published model, run unmodified and out of process; (C) a comparison over the source's
    steady states and low-oxygen sweep.
  - **Working defaults** (the note's questions 3 and 4, not put separately): the source's driven
    NADH supply for the organelle; held NADH for single-law checks; the IMS as a finite node for the
    isolated organelle, merged with the cytosol in the first in-cell world.
  - **Host P or host C** remains the lead's call (§3.6). It is not yet ruled.
- **D210** (17 November 2026):
  - The level of detail is chosen per research question, as declared representations (D175).
  - The lumped node is the reference that N identical individuals must reduce to.
  - Individuals with fission and fusion come "sooner": the design now, and its dependencies pulled
    forward. Static individuals may need no new door. Dynamic ones need split, merge, retirement in
    a living owner, stochastic partition and `cells.relations@2`.
- **D194's order:** mitochondria is step 4, after the core-seams pass. The pass took the design's P1
  and most of mitochondria M1 (CORE_SEAMS §13).
- **D209:** the synthesis law, `proton_coupled_atp_synthesis_cycle@1`, is one law with one owner, the
  mitochondria lane. Machines M1 consumes it. Beard's Eq. 11 needs a departure on which the user
  rules. The zero-rate run is the mitochondria lane's (L5).
- **Licences, re-read on 19 November 2026** from the PLOS article pages, through a page-reading tool
  that quoted the licence lines: Beard 2005 is CC BY ("© 2005 Beard"); the 2006 correction is CC BY
  ("© 2006 Public Library of Science"). The correction changes Table 1's parameter values. The MR1
  agent re-reads both in the PDFs (section 2.6).

## 2.2 The prerequisites, and their state on main

Read in the code at 7f357cfb and in git's log.

| Prerequisite | State on main | Still missing |
| --- | --- | --- |
| **FR-1's compartments** (host C) | `cell_owned_compartments@1`, judged 44 of 44 (`fr1-v1-qualified-2026-11-18`). Refusal 4 version 1.3 (e515b87b) admits a kind's move at the compartment's node when its law declares the needed step term: `stage_term` for a charged row, `material_term` or `material_bound` for a neutral one. Refusal 5 version 1.2 (af1206e2) admits charged anchors. Several compartments per owner are admitted at parse; the addendum found no stepped world with two (A.1). | None of the new cycle laws exists, so none declares its terms yet. Among today's cycle laws only the proton pump's declares a step term (`stage_term`); the symporter is refused at a compartment's node by design. The later doors (creation, division, fusion and fission, retirement in a living owner, volume, condensation) are not built. The operator refuses water, insertion, lumens and the division closers. |
| **FR-4's pH** | Judged 21 of 21 (`fr4-v1-qualified-2026-11-17`) on version 1's pieces: the proton pump on held fuel, `cells.rapid_proton_buffer@1` and `proton_constant_field_leak@1`. The general closure `rapid_binding@1` holds several ligands on multi-form binders (aecbaed1, 4736d974, 6ec01be1, b546c99d). P1's predictor (9e181b08) covers the general closure only. | No built-in law moves a closure row: none declares base forms or reads `rapid_binding@1`. No registry entries for ATP, ADP and Pi with H⁺ and Mg²⁺ forms. No registry moieties (item 6). |
| **The cycle kind and its forms** | Seam A's population axis of `cells.transporter@1` (ee30e5d9): any number of populations per patch, N/P orientation, integer roles at both ends, electrogenic modes, the `factored`, `diagram` and `net_flow` forms, Wegscheider per Hill cycle. `FreeEnergyEntry` everywhere, checked against the registry (69ac2ba7, 4e6ca60e, bd9881d5, 985c6a44). Symporter version 1 (845ee670). | Named rates, from symporter version 2 (`na2_anion_symport_diagram@1`), are on branch core-pass-kinds-7 at 967922e6, not on main. Availability schedules are on core-pass-kinds-8 at 6f55940c; on main a population's availability is 1. This pass's limits: patch hosts only; chemistry at P refused; held rows neutral; moved fuel at a node whose protons move is refused, with the closure's exception unwired. Since 20 November 2026, K1 (206d5c7b) admits moved fuel at a closure's node and K3 (c88f5338) admits chemistry at P. |
| **The energy accounting, X2 included** | Seam D (6ca4a56f): a heat booking per mover class, with the trapezoid admitted for @3's own classes. The booking probe confirmed the need (CORE_SEAMS_STEP0 §6.1). Seam E: kind ledgers (ac43139d), the potentials check and `FreeEnergyEntry`. X2, `step_doubled_energy@1` (fd894b91): registered and judged runs must select it, with a per-row cap (D224); ARS(2,2,2) only. | No kind declares `heat_bookings`, so `cells.transporter@1` books by the tableau only. A synthesis cycle that reverses within a step can then book negative heat. Branch X, the exact charged booking, is not built: P1 gave a weak no (CORE_SEAMS_STEP0 §8). If an implicit cycle block is needed, X2's scope must extend to its new solver ID. |
| **The §2 question: can a cell-owned compartment carry its own voltage?** | Yes, in the field. At a face-free node with one patch, V_b = −q/C_b exactly (FR-1 §3.1). FR-4's judged world carries a charged lumen. Refusal 5 admits charged restarts. Host P (the matrix as a @3 cell, the IMS as a finite node) parses (probe P0; nothing stepped). | The step at real fluxes. On 17 November P1 admitted host C up to dt·ΣG/C = 0.02 and host P up to 0.01. Refusals then came from the step-validity flag, partly the predictor gap since fixed for the general closure, and from the explicit-rate and face bounds (caps of 0.289 and 0.108). P1 has not been rerun since the fix. So branch E (explicit steps suffice) or branch I (an implicit cycle block) is open. |
| **Finite fuel and the ATP pools** | `finite_fuel_rows@1` on the population axis under the neutral ATP-driven law, with stored energy booked. Seam A's references compare a finite-fuel world state by state (`ff_neutral_n1`). D152's regeneration, with the potentials check. | The first finite-fuel acceptance (`finite-fuel-v1`) has no world and no protocol. @3's Na/K and Ca pumps run on maintained pools, so a cell's ATP economy cannot close across them. D175's fields are refused at registration. |
| **The protocol's steps** (MITOCHONDRIA_DESIGN §7) | FR-10's `scheduled_bath_composition@1` acts on held baths, and is judged. | The ADP step from 0 mM is "a dose from nothing", which the bath schedule refuses, and ADP has no measured region. The inhibitor step sets a population's availability to 0, which needs the schedules (on a branch). The uncoupler step could use a second leak route on its own patch, with that patch's availability scheduled: to check. Whether the bath schedule composes with declared kinds is still to check. |
| **Rows and the species cap** | The cap is 1,024 where a species operator is declared (`species_common.MAX_SPECIES`; 16 until FR-43 / D315). No cap was found in @3's spec. | Host P needs about 14–16 rows (MITOCHONDRIA_DESIGN §2.2). The builder counts rows and checks which declared operator applies the cap. No parse probe was run for this note. |

## 2.3 What is still missing, by owner

Owners follow CORE_SEAMS_STEP0 §4.2 as amended by CORE_SEAMS §18. Figures are estimates unless a
note is cited.

**Kinds owner** (`kinds/transporter.py`, `laws/cycles/forms.py`):
- **K1. Moved fuel at a closure node.** `_general_closure_nodes` names the general closure's nodes,
  so ATP, ADP and Pi may move where protons move, under `rapid_binding@1` (§5.2's exception).
  1–2 days.
- **K2. The trapezoid for the kind.** The kind declares the booking in `heat_bookings`, so synthesis
  and exchange may reverse within a step. 0.5–1 day.
- **K3. Chemistry at P,** only if host P runs per-complex respiration, with cytochrome c on the P
  side. 1–1.5 days. Host C's two-cycle form does not need it. **Landed 20 November 2026**
  (merge c88f5338), after D235 chose host P.
- **K4. A Δp readout,** and the run-view declarations for ΔΨ, Δp and N→P flows. 0.5 day.
- **K5. Land symporter version 2 and the schedules.** Both are built; they need their gates.
- **K6. A form for Beard's forward terms,** if needed. The forward terms are unsaturated mass action.
  Whether `factored` or `diagram` expresses them exactly is the laws owner's first design point. A
  new form costs about 0–1.5 days.

**Binding owner** (`registry/species_registry.py`, `kinds/proton_buffer.py`,
`laws/reactions/rapid_binding.py`):
- **B1. Registry entries:** ATP, ADP and Pi with their H⁺ and Mg²⁺ forms and cited constants; a
  matrix buffer; NADH, NAD⁺, Q, QH₂, O₂, K⁺ and Mg²⁺; and cytochrome c's two forms on host P. Each
  binding's k_on, for the envelope. 1–1.5 days.
- **B2. Registry moieties** (item 6): adenine, NAD, Q and cytochrome c. 0.25–0.5 days
  (CORE_SEAMS_STEP0 §4.2).

**@3 owner** (`models/surface_pump_v3.py`, `definitions/surface_pump_v3_spec.py`):
- **A1. P1′:** P1's ladder rerun with the buffer declared as `rapid_binding@1`, on the chosen host,
  with the criterion written first. 0.25–0.5 days. It edits no file under `src/`. Giving it to the
  @3 owner is this note's proposal, since it reads @3's predictor; CORE_SEAMS §13 gave P1 to the
  kinds owner, who is the busier of the two.
- **A2. Branch I, only if P1′ asks for it:** an implicit cycle block, a new IMEX ID (D147), with X2's
  scope extended to it. 6–9 days (MITOCHONDRIA_DESIGN §8).
- **A3. Branch X, only if the ledger binds first** (CORE_SEAMS §6.3). 2–3 days.

**The mitochondria lane agent, for the laws** (new files in `laws/cycles/`; the lead's ruling,
§2.4):
- **L1. The six laws of §2.4.** Each is data on seam A's forms, and declares its base forms, its read
  of `rapid_binding@1`, its step terms for refusal 4 version 1.3, its `FreeEnergyEntry` and its
  cited parameters. A short appendix of the declared equations comes first, for the component
  references. 2–4 days (MITOCHONDRIA_DESIGN §8, mitochondria M3's laws).

**The mitochondria lane agent, for validation** (new `validation/mitochondria/`, except its
`references/` folder):
- **V1.** The organism definition: cited parameter sets for isolated cardiac mitochondria. Nothing
  species-specific goes into `src/cells` (D144).
- **V2.** Worlds for host P (the matrix as a cell, the IMS as a finite node, the outer membrane as a
  face to a held buffer), and for host C if the lead rules for it.
- **V3.** The protocol of MITOCHONDRIA_DESIGN §7, registered before its run, selecting X2 with a
  per-row cap. Steady states as separate held-buffer worlds avoid the dose schedule.
- 3–5 days plus CPU (mitochondria M4's figure).

**Operators owner:** nothing for MT-1 on host P. On host C, refusal 4 version 1.3 admits the laws
once they declare their terms, so no edit is expected.

**Files outside the owner table** (the lead assigns them if they are touched):
`operators/species_common.py`, if the 16-row cap binds; `operators/bath_schedule.py`, if a dose step
is kept.

**Held NADH is not needed in MT-1.** On the population axis held rows must be neutral, and the
registry may declare NADH and NAD⁺ with charge. MT-1's single-law checks run on the laws' kernels at
clamped concentrations, with no world, and the organelle uses the driven supply. If a world must
hold them, the lead either admits zero valences there as a declared departure, or the kinds owner
lifts the neutral-held-row limit (about 1 day, estimate).

**For later milestones, not MT-1:**
- `finite-fuel-v1`, and the Na/K pump as a cycle law on finite fuel: mitochondria M6's demand pulse;
- the compartment map's address "species S in compartment C": M6 on host C, 2–3 days;
- a host kind for routes between pools: a resolved IMS, and M7's ER contacts;
- FR-1's doors and `cells.relations@2`: individuals.

## 2.4 The first milestone, MT-1: one isolated cardiac mitochondrion, lumped, on @3

**What it shows.** The organelle's laws run on @3 and close every ledger. Cells' own organelle runs
the respiratory-control protocol against an independent integration of the same declared equations
(MITOCHONDRIA_DESIGN §5.2 and §7). It reproduces no published model: that is MT-2.

**Its stages.**
- **MT-1a.** P1′ (A1); the kind and closure work (K1, K2, K4, K5, B1, B2); the six laws with their
  component references (MITOCHONDRIA_DESIGN §5.1). Development, with the references compared in
  every gate.
- **MT-1b.** Cells' own organelle in a medium, on host P (or host C by the lead's ruling), with
  §7's protocol, registered and judged (mitochondria M4).
- **From day one, in parallel:** MR1, the code-blind whole-organelle reference of Beard 2005 (approved,
  D193 (A)). MR2, the published model run out of process (D193 (B)), follows once MR1 is registered.
  Both belong to MT-2. Section 2.6 is their brief.

**The engine models it runs** (AGENTS.md):
- `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with IMEX ARS(2,2,2);
- `cells.transporter@1`'s population axis, hosting the six laws;
- `cells.passive_routes@1` with `proton_constant_field_leak@1` (the leak and the uncoupler), and
  `passive_neutral_permeation@1` for O₂ across the membranes, if declared;
- `cells.rapid_proton_buffer@1` declaring the general closure `rapid_binding@1`: H⁺ and Mg²⁺ on
  ATP, ADP, Pi and a buffer;
- on host P, the outer membrane as a face under `logmean_electrodiffusion@1` (subject to the lead's
  reuse check, MITOCHONDRIA_DESIGN §3.4);
- on host C, `cell_owned_compartments@1`;
- `step_doubled_energy@1` (X2) in registered and judged runs;
- `scheduled_bath_composition@1` only if a dose step is kept (V3).

There is **no new kind and no new operator.** Seam A built the cycle kind into `cells.transporter@1`
(ruling A3), so the design's proposed `cells.membrane_cycles@1` is not needed.

**The new laws.** Neutral names as MITOCHONDRIA_DESIGN §1.2 proposes them (proposals, not rulings):

| Law | Physics | Charge across the membrane | Note |
| --- | --- | --- | --- |
| `redox_driven_proton_cycle@1` | Respiration: each complex a population. Host C, or the reduced form: two populations, NADH:Q and QH₂:O₂ | Electrogenic | Host P's per-complex form needs chemistry at P (K3) |
| `proton_coupled_atp_synthesis_cycle@1` | Reversible synthesis: c H⁺ from P to N per 3 ATP, or an effective n_A per ATP | Electrogenic | Beard's Eq. 11 fails the screen; a departure for the user (§2.5) |
| `electrogenic_nucleotide_exchange@1` | ATP⁴⁻ out of N, ADP³⁻ in | One negative charge out per cycle | The cardiac exchanger's sibling |
| `phosphate_proton_symport@1` | H₂PO₄⁻ with one H⁺ into N | Electroneutral | Beard's Eq. 16 fails the screen |
| `potassium_proton_exchange@1` | K⁺ against H⁺ | Electroneutral | — |
| `driven_redox_supply@1` | The NADH supply relaxing to a declared ratio, booked as signed work | — | Its home (the cycle kind or a reaction) is the laws owner's design point |

Reused laws: `proton_constant_field_leak@1`, `rapid_binding@1` and `logmean_electrodiffusion@1`.
Later, not in MT-1: `electrophoretic_calcium_uniport@1`, and the cardiac lane's
`sodium_calcium_exchange_cycle@1` facing the matrix (mitochondria M7).

**The code-blind references.**
- **Component references** (MITOCHONDRIA_DESIGN §5.1). A fresh agent writes them from the laws'
  declared equations (L1's appendix) and the paper's printed formulas. It checks each cycle at
  clamped ΔΨ and concentrations, in high-precision arithmetic, with planted controls.
- **The organelle's independent integration** (§5.2): the same declared equations, integrated with
  tight tolerances.
- **MR1 and MR2,** for MT-2 (section 2.6).
- **Licences:** Beard 2005 and its correction are CC BY (read on 19 November 2026 through a
  page-reading tool; section 2.1). The Physiome
  Model Repository's CellML encoding is CC BY 3.0 on its metadata page, and libOpenCOR is Apache 2.0
  (both as read on 16 November, MITOCHONDRIA_DESIGN §5.5). Nothing from them is committed; only saved
  outputs enter the evidence.

**Owners, file by file.**

| Files | Owner | MT-1 work |
| --- | --- | --- |
| `kinds/transporter.py`, `laws/cycles/forms.py` | Kinds owner | K1, K2, K4, K5; K3 and K6 if needed |
| `registry/species_registry.py`, `kinds/proton_buffer.py`, `laws/reactions/rapid_binding.py` | Binding owner | B1, B2 |
| `models/surface_pump_v3.py`, `definitions/surface_pump_v3_spec.py` | @3 owner | A1; A2 and A3 only if triggered |
| New law modules in `laws/cycles/` | The mitochondria lane agent (new; the lead's ruling) | L1 |
| `validation/mitochondria/`, except `references/` | The mitochondria lane agent | V1–V3, the protocol |
| `validation/mitochondria/references/components/` (new) | A fresh component-references agent. It reads L1's appendix and the paper; no code and no model file | The component references, and the organelle's independent integration |
| `validation/mitochondria/references/organelle/` (new) | A fresh MR1 agent. It reads the paper only; section 2.6 is its whole brief | MR1; then MR2, only after MR1 is registered |
| `operators/compartments.py` | Operators owner | Nothing expected |
| `registry/laws.py`, `registry/kind_registry.py` | F owner | Nothing expected |

**One conflict for the lead.** The owner table gives "any new cycle-law module" to the kinds owner.
D209 gives the synthesis law to the mitochondria lane. Recommended: amend the table so that the new
mitochondrial law modules (new files only) go to the mitochondria lane agent. The kind file stays
with the kinds owner.

**The new seats.** Two at the start: the mitochondria lane agent and the MR1 agent. A third, the
component-references agent, joins when L1's appendix exists. The kinds, binding and @3 owners work
part-time from their current seats. The two reference agents stay separate: the component agent
reads the engine's declared equations, and MR1's agent must not (D193 (A)). MR2 follows MR1 in the same
agent, so that MR1 is registered before any model file is opened.

**Test cost, under D224.**
- **The laws' kernels:** rows in a parametrized test of pure functions, with no world compiled. For
  scale, `test_core_seams_references_cycles.py` takes 1.1 s and `test_rapid_binding_kernel.py`
  8.6 s, both in tier 1.
- **The component references:** one parametrized comparison file, through the references'
  interface. For scale, `test_cycle_kind_references.py` takes 11.3 s, in tier 1.
- **Worlds:** at most two new compiled-world files, one per host. For scale, `test_cycle_kind_runs.py`
  takes 25.5 s and `test_cycle_kind_compiled.py` 82.5 s, in tier 2. Each states its seconds and its
  reason at landing.
- Fixes add rows, not files. P1′ and the judged protocol run outside the tiers.
- **The expected addition:** about 1–3 CPU-minutes to tiers 1 and 2's 172 (estimate).

**Effort** (estimates; branch E):

| Part | Agent-days |
| --- | --- |
| MT-1a: P1′, K1, K2, K4, B1, B2, L1 and the component references | About 8.5–14 (plus 1–1.5 for K3, and 0–1.5 for K6) |
| MT-1b: worlds, protocol, registration and the judged run | 3–5, plus CPU |
| MT-1 in all | About 11.5–19, or 12.5–22 with K3 and K6; plus 6–9 on branch I |
| MR1, in parallel (part of MT-2) | About 3–4 |
| MT-2 after MT-1: MR2, its registration and the judged comparison | About 3–5 |

- **Elapsed:** about 8–12 working days for MT-1, with the kinds and binding owners part-time, the
  lane agent and the two reference agents (estimate).
- **CPU:** P1′ and the component references take minutes. MT-1b's protocol takes minutes at a 1 ms
  step and tens of CPU-hours at 10 µs (MITOCHONDRIA_DESIGN §8). A run of 10 minutes or more goes
  detached, with durable logs (AGENTS.md).

**The main risks.**
1. **Stiffness.** If P1′ asks for branch I, MT-1 grows by 6–9 days.
2. **Departures.** Beard's printed Eqs. 11, 16 and 24 fail the screen, so the engine runs declared
   forms. The user rules first.
3. **Zero concentrations.** State 4's external ADP of 0 and the Pi sweep's start at 0 cannot be
   represented: the kind's domain refuses non-positive inputs. A declared trace value would be a
   departure, reported to the user before MT-2's judged run (D193).
4. **Rows.** The 16-row cap is at the edge on host P.
5. **The kinds owner** is the bottleneck.

## 2.5 Questions

**For the user, before MT-1's laws are written.**
1. **The printed laws' departures** (D209; CORE_SEAMS §16).
   - Beard's Eq. 11 (ATP synthesis) omits the matrix proton its reaction consumes.
   - Eq. 16 (the phosphate carrier) has the matrix and outer protons reversed against its stated
     1:1 cotransport.
   - Eq. 24 drops a term of Eq. 7.
   - The engine refuses laws that fail this check. Do you approve the consistent forms as declared
     departures, keeping Beard's forward term in each, with MR1 run both as printed and as declared?
2. **U7** (machines, D209). Change the synthase's approved zero-flux check, so that the coupling
   ratio is an input, the intercept is judged and the structural ratio is reported as a finding?
   Until you rule, the approved check stands. The zero-rate run is the mitochondria lane's (D209, L5).
3. **Individual mitochondria** (the addendum's questions, D210).
   - **U1:** is the first individuals question "do fission, selective fusion and removal keep a
     cell's mitochondria polarised?", on data from cells that are not cardiac (Twig et al. 2008),
     with inheritance second and discrete units drawn at fission as the source of asymmetry?
   - **U2:** option O1, with individuals (mitochondria M8) ahead of calcium (mitochondria M7)?
   - **U3:** split and merge, or fixed segments with gated links (option O4)?
4. **Seats and order.** MT-1 needs two new seats at the start (the mitochondria lane agent and the
   MR1 agent) and a third at peak (the component-references agent), beside part-time work by the
   kinds, binding and @3 owners. Which of Part 1's options do you choose?

**For the lead** (not the user's).
1. Host P or host C for the isolated organelle (MITOCHONDRIA_DESIGN §3.6). P1′ runs the chosen host's
   arm. Host C's two-cycle form needs no chemistry at P, but loses cytochrome c's curve.
2. The ownership conflict over the new law modules (§2.4).
3. Owners for `validation/mitochondria/`, and for `operators/species_common.py` and
   `operators/bath_schedule.py` if they are touched.
4. The outer membrane's face law under ARCHITECTURE.md's reuse rule (MITOCHONDRIA_DESIGN §3.4).
5. Fresh agents for the component references, MR1 and MR2. The design note's author and this note's
   author have read the engine.
6. State 4's zero external ADP: a declared trace concentration, or another world design.
7. The design's question 13 is answered: numbers from free-to-read papers may be used with a
   citation (D186, D201), and bare numbers from non-commercial papers too (D227).

## 2.6 Brief for the code-blind references agent (separable)

*Give this section alone to the references agent. It names no part of the engine.*

**Do not read:**
- `src/` and `tests/`;
- anything under `validation/` outside your own folder, `validation/mitochondria/references/organelle/`;
- the engine's design notes, decisions and progress files, and any other part of this document;
- engine run outputs, under `/mnt/workspaces/Cells` or anywhere else;
- any model file of this paper (a CellML encoding, a BioModels entry, the authors' code), until MR1 is
  registered.

**Read:** D. A. Beard, "A Biophysical Model of the Mitochondrial Respiratory System and Oxidative
Phosphorylation", PLoS Comput Biol 1(4):e36 (2005), doi:10.1371/journal.pcbi.0010036; and its
correction, PLoS Comput Biol 2(1):e8 (2006), doi:10.1371/journal.pcbi.0020008. Both are CC BY. The
PDF is the version of record.

**Task MR1: an independent implementation of the whole-organelle model, from the paper and its
correction only.**
1. **First,** confirm that the printed equations and the corrected Table 1 are legible in the PDF. If
   not, stop and report. Record both licences as you read them.
2. **Two arms:**
   - **MR1-published:** as printed, with the corrected Table 1;
   - **MR1-declared:** with the declared departures below, each behind its own switch.
3. **The declared departures known now,** in physical terms:
   - Mg²⁺ binding in rapid equilibrium;
   - matrix H⁺ buffering by a declared buffer species, at the source's capacity;
   - a finite synthase activity, at a declared value where the outputs converge (the paper sets it
     large);
   - exact SI constants;
   - the outer membrane as passive electrodiffusion with heat, if the printed flux form allows it;
   - thermodynamically consistent forms of Eqs. 11, 16 and 24, pending the user's ruling;
   - a declared trace value for any zero concentration, if the lead rules so.

   Report any further departure you find before any judged run.
4. **Check these independently; do not assume them:**
   - Eq. 11's exponent omits the matrix proton that its reaction consumes;
   - Eq. 16's proton terms are reversed against the stated 1:1 cotransport;
   - Eq. 24 drops Eq. 7's +2RT ln([H⁺]x/10⁻⁷);
   - the printed ΔG°_ATP has the sign of hydrolysis, but Eq. 11 uses it for synthesis;
   - the web XML's Eq. 22 differs from the PDF's.
5. **The protocols, as the paper states them** (re-read them there):
   - steady states over external Pi from 0 to 10 mM, at external ADP 0 (state 4) and 1.3 mM
     (state 3), at external pH 7.1, K⁺ 150 mM, total Mg²⁺ 5 mM and O₂ at 20 mmHg;
   - outputs: NADH/NAD_tot, oxygen consumption, cytochrome c's redox state and ΔΨ (Figs. 2–5);
   - the low-oxygen sweep (Fig. 6), with the model's P50.
6. **Method:** your own stiff integrator with a convergence check, run out of process. Take
   tolerances from your own convergence or a stated physical scale. Plant a coefficient change that
   must be caught.
7. **Where:** `validation/mitochondria/references/organelle/`, a new folder. Write the design files
   before any engine output exists. Deliver the values as a registered interface file.

**MR2, separately approved (D193 (B)), after MR1 is registered.** Run the Physiome Model Repository's
curated CellML encoding of Beard 2005 unmodified, in libOpenCOR, in its own environment under
`/mnt/workspaces/Cells`. Use the file by reference and never commit it. First check whether it
carries the 2006 correction. If any wall appears (an account, a guard, a missing tool), stop and
report; do not work around it.

---

## Sources read

- AGENTS.md; [DECISIONS.md](DECISIONS.md):
  - read in full: D136, D138, D141, D144, D145, D173, D175, D176, D183, D184, D191–D196, D209, D210,
    D212, D216–D232;
  - read in part: D167, D177 (FR-7's lines), D179 (the hold), D185;
  - read by heading only: D057, D135, D140, D147, D148, D150, D152, D155, D156, D163, D165, D172,
    D174, D186, D188, D197, D199, D200, D201, D202, D207, D214, D215.
- [CURRENT_PLAN.md](CURRENT_PLAN.md); [ROADMAP.md](ROADMAP.md); [PROGRESS.md](../PROGRESS.md)'s
  current position and run entries of 17–19 November; [FEATURE_REQUESTS.md](FEATURE_REQUESTS.md).
- [CORE_SEAMS_DESIGN.md](CORE_SEAMS_DESIGN.md) (§0–§2, §13, §16, §18); [CORE_SEAMS_STEP0.md](CORE_SEAMS_STEP0.md)
  (§4.2, §7, §8); [MITOCHONDRIA_DESIGN.md](MITOCHONDRIA_DESIGN.md), with its addendum;
  [HUMAN_CARDIAC_LAWS_DESIGN.md](HUMAN_CARDIAC_LAWS_DESIGN.md) (§6, §8, §9.2);
  [CLOSED_COMPARTMENT_DESIGN.md](CLOSED_COMPARTMENT_DESIGN.md) (§3.4.4, §3.4.5, §8);
  [COMPARTMENT_PH_TRANSFER_DESIGN.md](COMPARTMENT_PH_TRANSFER_DESIGN.md) (§17);
  [SYN3A_MINIMAL_CELL_TRACK.md](SYN3A_MINIMAL_CELL_TRACK.md) (§0, §4.3, §4.4, §11);
  [MOLECULAR_MACHINES_DESIGN.md](MOLECULAR_MACHINES_DESIGN.md) (§10.1, §10.6);
  [GAP_JUNCTION_CANCER_REPLICATION.md](GAP_JUNCTION_CANCER_REPLICATION.md) (§5);
  [ORIGIN_OF_LIFE_ENGINE_DESIGN.md](ORIGIN_OF_LIFE_ENGINE_DESIGN.md) (§0.2e, §0.3);
  [ABUNDANCE_TO_FUNCTION_DESIGN.md](ABUNDANCE_TO_FUNCTION_DESIGN.md) (§0);
  [MEMBRANE_RETRIEVAL_DESIGN.md](MEMBRANE_RETRIEVAL_DESIGN.md) (§0);
  [OPERATOR_COMPOSITION_DESIGN.md](OPERATOR_COMPOSITION_DESIGN.md) (status);
  [GRN_WETLAB_VALIDATION.md](GRN_WETLAB_VALIDATION.md); [MORPHOGENESIS_PLAN.md](MORPHOGENESIS_PLAN.md);
  [CELL_DIVISION_PLAN.md](CELL_DIVISION_PLAN.md); [E07_V2_DESIGN.md](E07_V2_DESIGN.md) (status);
  [FINITE_ENERGY_POOLS.md](FINITE_ENERGY_POOLS.md); [lanes/LEVIN_CANCER_XENOPUS.md](lanes/LEVIN_CANCER_XENOPUS.md)
  (headings); [library/README.md](library/README.md).
- **Code at 7f357cfb:** `kinds/transporter.py`, `kinds/proton_buffer.py`, `kinds/passive_routes.py`,
  `laws/cycles/forms.py`, `laws/reactions/rapid_binding.py`, `laws/pumps/atp_transporter.py`,
  `registry/laws.py`, `registry/species_registry.py`, `models/inner_laws.py`,
  `models/surface_pump_v3.py` (the host table), `definitions/surface_pump_v3_spec.py`,
  `operators/compartments.py`, `operators/bath_schedule.py`, `operators/species_common.py`, and the
  tests named above. `tests/test_tiers.json` for the measured seconds.
- **Git:** main's first-parent log from 17 November; the unmerged heads of core-pass-kinds-7,
  core-pass-kinds-8 and core-pass-operators-3-p2; the qualification tags.
- **External, 19 November 2026:** the PLOS article pages of Beard 2005 and its 2006 correction, for
  their licence lines only.
