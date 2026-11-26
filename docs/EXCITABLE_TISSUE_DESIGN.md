# Excitable tissue: design (proposed)

> **Legacy cleanup (25 November 2026, D386).** Paths under `src/cells/legacy/` and the older model
> IDs named below left the engine. The tag `pre-cleanup-2026-11-25` keeps them.

**Accepted narrowly, 14 November 2026 (the lead, D170; the advisor reviewed the ruling after it
landed and confirmed it): for M1 and M2 on @3
only.**
- **The acceptance condition failed.** It was one cheap probe, and probe 2 failed S1 as
  registered: at 0.05 F/m² every perturbed segment blocked.
- **What the acceptance rests on instead:** amendment 4, a second probe at candidate A (0.01
  F/m²). It is post hoc, but it was written before its runs.
- **The generic cell is A,** by amendment 3's text. The driver's stricter record names B; an
  addendum beside it explains why.
- **The s·r_gj ≥ 20 floor is provisional.** M1's first development runs measure the junction
  voltage at block sites on the sheet, the block threshold (coupling-only included) and the
  peaks at lightly loaded cells. M3's grid is registered only after them.
- **B is the pre-registered fallback** if A is refused on the sheet in M1.

**Status.** Proposed on 14 November 2026 by Track E (D155). **It contains no code** (D142:
design before code). The lead reviewed it with the advisor on 14 November and accepts it only
for the generic-cell work on @3, and only after one cheap probe. Probe 2 (§1.2) is that probe.
This revision carries its result and the lead's rulings (§12). **Since 16 November** the human
ventricular law set (§3.3, §7, and M4 and M5 in §11) is brought forward as its own lane (D183),
with its choices made in D184 and its design in
[HUMAN_CARDIAC_LAWS_DESIGN.md](HUMAN_CARDIAC_LAWS_DESIGN.md) (proposed); M1–M3 on the generic cell
are unchanged.

**The question it serves.** D155's: do weakly coupled cells with low sodium conductance, as
dividing cardiomyocytes become, slow or block conduction, and does their clustering matter? It
serves that question as **general excitable-tissue physics, not a cardiac mode** (D144).

**Evidence.**
- The conduction probe is in
  [excitable-tissue-20261114-01](/mnt/workspaces/Cells/excitable-tissue-20261114-01/):
  `HANDOFF.md` holds the numbers, and `PLAN.md` the criteria and amendments 1–4.
- Its driver is `validation/tissue/excitable_probe.py`.
- Its equations, for the independent reference, are in
  [the equations appendix](EXCITABLE_TISSUE_EQUATIONS.md).
- M1's development runs on the 127-cell sheet are in
  [excitable-tissue-m1-20261114-01](/mnt/workspaces/Cells/excitable-tissue-m1-20261114-01/), with
  their driver `validation/tissue/excitable_sheet.py`. `HANDOFF.md` holds the results and
  readings, and `PLAN.md` the criteria and amendment 1. They inform §5's activation and capture
  rules and §10's predictions and refusals.

**Engine models the probes ran:** `resolved_pump_tissue@3`, which is
`nav1p2_m3h_regularized@1`, `kir2p1_mh2@1`, `kv1p5_mh@1`, `kleak_always_open@1` and
`naleak_always_open@1` with the following:
- `constant_field@1` leaks and junctions;
- the `nak_atp_mass_action_positive@1` pump;
- the `junction_voltage_relaxation@1` gate, pinned open or as declared;
- IMEX ARS(2,2,2) and Euler with exponential stage gates, and @3's RK4 as the step reference;
- field solver version 2, declared through `field_solver_choice.declare()`, with 0 free
  offsets in every world.

## 1. The probes' verdict, and how it was reached

### 1.1 Probe 1: one cell and a uniform chain

**The decision was:** proceed with the existing mechanisms, or name the particular missing
mechanism the feature must add.

**The probe's answer: proceed with the existing mechanisms.** The coordinator accepted it on
14 November as this note's direction. It was reached as follows, and the record says so
plainly.

1. **The plan's own gate failed.** The plan's single cell was the heredity cell
   (`surface_pump_v3_fixtures.heredity_cells`) plus one Kv1.5 population.
   - No Kv1.5 value met the fixed selection rule.
   - At Kv1.5 = 0 the response was graded, not all-or-none. The overshoot threshold is a
     42.66 mV kick, and peaks 0.5 mV either side are −1.1 and +1.3 mV. Upstrokes across the
     scan were 16–23 V/s. The cell latched depolarised, with no S1–S2 recovery up to 60 ms.
   - The sodium-disabled and passive controls showed no rise.
   - By the plan, the chain did not run.
2. **Amendment 1, post hoc,** was dated before the runs it governs. A Kv-only scan cannot tell
   a density deficit from a missing law, so it scanned the admitted laws' densities: 24 points
   over specific capacitance, NaV1.2, Kir2.1 and Kv1.5.
   - 14 points gave an action potential that overshoots, repolarises within 60 ms and peaks
     below +55 mV.
   - The first three passing points, all at c_m 0.05 F/m², failed the plan's all-or-none
     clause.
3. **Amendment 2, post hoc,** was also dated before the runs it governs. It found that the
   clause compared two fired responses: the bisection located the overshoot, not firing.
   - The chain's gate became two tests: the sodium-disabled control, and controls bracketing
     the firing boundary (no rise 5 mV below, more than 10 V/s 0.5 mV below).
   - It selected **point 2**: c_m 0.05, NaV1.2 1e-6, Kir2.1 1e-8 and Kv1.5 3e-7 m/s.
   - The chain ran there.

**The criteria as recorded at point 2** (the criteria are the coordinator's, fixed before any
run):

| | Criterion | Recorded | Note |
| --- | --- | --- | --- |
| C1 | Excitation continues beyond the stimulated cells after the stimulus | Met | |
| C2 | Passive, subthreshold and sodium-disabled controls distinguish regeneration | Met | |
| C3 | Activation time, CV, capture, recovery and block measured | Met | |
| C4 | Step refinement; chain length and boundary distance | **Not met** | Refinement passes: CV moves 1.1e-6 between 5 and 2.5 µs. The 40-cell spans spread 4.0 % (limit 2 %). Mid-chain CV depends on the stimulus by 5 %. These are end effects |
| C5 | Material, charge and energy checks; mechanisms and cost recorded | **Not met as computed** | The one counted refusal is the 25 µs admissibility probe, refused at the stimulus onset. No accepted case failed a host or device check |

**Neither failure is a missing mechanism.** Both are fixed as measurement in the
qualification protocol (§6): longer chains, a stimulus-independent measurement window, and
the step probes.

**The probe's numbers at point 2:**
- **Single cell:** peak +34.9 mV, 82 V/s, APD90 12.1 ms and recovery 15–20 ms. The response
  is Na-dependent.
- **20-cell chain** (9.25 µm cells, 16.3 pF; g_j = 0.1045 nS × s, from the engine's own
  bound):
  - block between s = 42.09 and 42.49 (g_j ≈ 4.4 nS);
  - CV 572, 1,110, 2,086 and 3,704 cells/s at s = 100, 300, 1000 and 3000 (5.3 to 34 mm/s),
    uncorrected for end effects, and 292 cells/s just above block;
  - capture 1.29–1.36e-7 m/s per ion;
  - recovery for a second wave 25–30 ms;
  - device row checks passed.

### 1.2 Probe 2: a wave meeting a modified mid-chain segment (the first experiment's configuration)

This is the lead's blocking probe. Probe 1 saw block only at the first unstimulated cell, but
the first experiment is a wave meeting a cluster in mid-tissue. The chain has 40 cells at
s = 1000, and its segment, cells 16–23, holds NaV1.2 availability r_Na and the availability
r_gj of the segment's nine junctions. Criteria S1–S4 (slowing; block of a travelling wave;
step refinement at the segment; accounting and domains) were written first, in PLAN
amendment 3.

**At point 2 (0.05 F/m²), as registered: S1 failed.** The registered rule then reads: "If S1
or S2 fails, the probe reports which, and the verdict does not stand on this probe." S2–S4
held.
- **Everything stopped before the exit.** Every perturbed case stopped before cell 24:
  - combined r = 0.5 to 0.05;
  - sodium-only 0.3 and 0.1;
  - coupling-only 0.1 and 0.03.
- **How they stopped.** Combined 0.5 and the sodium-only cases conducted decrementally. Only
  coupling-only 0.1 fired through the segment, at 550 cells/s (3.9× slower than the
  control), and then failed at its exit junction.
- **S3:** outcomes and in-segment activation times (to 6.5 ns) were the same at 5 and 2.5 µs.
- **S4:** no refusal; |Vj| reached at most 91 mV.

**At candidate A (0.01 F/m²; NaV1.2 1e-6, Kir2.1 1e-8, Kv1.5 3e-7 m/s): S1–S4 met.** This is
amendment 4: post hoc, the last amendment, dated before its runs, with milder strengths added.

| Case at A | Segment CV (cells/s) | Delay over control |
| --- | --- | --- |
| Control | 8,277 | 1.00 |
| Combined 0.9 / 0.8 / 0.7 / 0.6 / 0.5 | 7,614 / 6,920 / 6,189 / 5,416 / 4,590 | 1.09 / 1.20 / 1.34 / 1.54 / 1.83 |
| Sodium-only 0.7 / 0.5 | 7,627 / 7,052 | 1.08 / 1.16 |
| Coupling-only 0.5 / 0.3 | 5,678 / 4,342 | 1.50 / 2.02 |
| Combined 0.02 / 0.01 | block at the segment's entry | — |

- **Refinement.** Outcomes were identical at 5 and 2.5 µs. Delays agree to about 1e-5, and
  in-segment activation times to 14 ns.
- **No refusal, but the margins are thin.** At the blocking cases the segment's |Vj| reaches
  106 mV and **118.1 mV, 1.9 mV inside the junction gate law's 120 mV**, which applies even to
  pinned gates. Vm reaches at most **+56.65 mV, 3.35 mV inside +60**.

**The 0.01 F/m² point** (PLAN amendment 3, domain part):
- **Candidate A** fires (230–248 V/s), repolarises (APD90 3.8 ms) and propagates (8,277
  cells/s), with every chain cell from cell 6 overshooting and nothing refused. So it passes by
  the amendment's text.
- **The driver's test was stricter.** It added C1's after-the-stimulus clause: A's fast wave
  activates cells 6 and 7 inside the 1 ms stimulus. The driver therefore also ran candidate B
  (NaV1.2 2.5e-7, Kv1.5 1e-7 m/s), which met that stricter test too, by 0.14 ms (5,117 cells/s,
  peaks at most +37.6 mV). That margin is no sign that B propagates better.
- **The generic cell is therefore 0.01 F/m² at candidate A** (§7.2). That follows the lead's
  ruling and amendment 3's registered rule ("A, or B if A fails"), applied by its text. The
  driver's record names B (`ruling_input`), because of its stricter test. §12 asks the lead to
  confirm A, given the junction margin below.

**The verdict, in the decision's terms: proceed with the existing mechanisms, for the
generic-cell work on @3 at candidate A (0.01 F/m²) and s = 1000, with every junction at
s·r_gj ≥ 20.**
- **Its evidence** is amendment 4's S1–S4 at candidate A. Amendment 4 is post hoc, and probe
  2's registered run at point 2 does not support the verdict.
- **The junction limit below bounds that scope; it is not a missing mechanism.** Under the
  verdict rule a mechanism is named only when S4 fails by a domain refusal, and no case was
  refused.

**The verdict's scope limit is the junction gate law's 120 mV domain at block sites.**
- **Where it comes from.** `junction_voltage_relaxation@1`'s `domain_valid` refuses
  |Vj| > 120 mV on every junction, whatever its availability: pinned gates and closed
  junctions are included ("even blocked routes retain their physical domain"). @3 applies it
  to all junctions. The constant-field junction flux itself has no such limit.
- **How close probe 2 came.** At a block site, Vj is the last firing cell's voltage less its
  blocked neighbour's. It grew as the boundary's coupling fell: 106 mV at r = 0.02 and
  118.1 mV at r = 0.01, that is at s·r_gj = 20 and 10 (about 2.1 and 1.0 nS). A weaker
  junction depolarises the neighbour less and loads the last cell less.
- **What lies past it.** A's unloaded peak-to-rest range is 136 mV: rest −79.6 mV, peaks up
  to +56.7 mV, and after-hyperpolarisation to −87.6 mV. So **a boundary below s·r_gj = 10 at A
  is expected to be refused**. That case was not run; the expectation comes from the trend.
- **The floor to plan on is s·r_gj ≥ 20,** the weakest boundary run with a clear margin
  (106 mV). It is r_gj ≥ 0.02 at s = 1000, and about 0.07 at s = 300.
- **Nothing at A ran at any s other than 1000.** At s = 300 weaker upstream coupling loads the
  last firing cell less, so its peak and the block-site |Vj| may be higher. The floor there is
  checked in the protocol's development runs (§6).
- **Cardiac cells too.** The same holds for a block site of any cell whose peak-to-rest range
  exceeds 120 mV, cardiac cells included (rest about −80 to −85 mV, overshoot about +40 mV,
  §7.3).
- **B has more margin, not immunity.** B's peak-to-rest range is 117 mV (+37.6 mV over
  −79.6 mV), so a block site whose neighbour is at rest stays below 120 mV. But its
  after-hyperpolarisation reaches −84.6 mV, which takes its full range to 122 mV. A junction
  to a neighbour in after-hyperpolarisation could therefore exceed 120 mV. B's segment
  response was not run.
- **The mechanism to add** is a junction law, ungated or with its own stated domain, that
  covers the full action-potential range: `junction_ungated@1` (§3.3, §3.4). It is an M4
  prerequisite. It is an M3 one too if M3's grid goes below s·r_gj = 20 at A (§10, §12).

## 2. What the probes show about the engine

### 2.1 Reusable as it is

- **@3's channel-population machinery.** Constant-field flux per population, abundance and
  availability, and per-species transfer and heat ledgers. The exponential stage gates
  (`exponential_mean_rate_linear_target_gates@1`, after Rush and Larsen 1978), whose stiff m
  gates relax to their quasi-steady values instead of destabilising the step. The
  explicit-stage refusal (`membrane_rate`).
- **The generic cell's laws.** `nav1p2_m3h_regularized@1` serves as a fast sodium current with
  inactivation, `kv1p5_mh@1` as a slowly activating, slowly inactivating delayed rectifier,
  and `kir2p1_mh2@1` as an inward rectifier with a kinetic m gate. These are BETSE-parity
  laws with no biological calibration (D107, D131).
- **Gap-junction conduction.** `constant_field@1` junctions with `junction_controls`
  availability (Track E's perturbation and control arm), and the voltage gate pinned open or
  as declared.
  - The BETSE-derived gate (15 mV, minimum 0.1) changed CV by 1.8 % at s = 1000.
  - **The ±120 mV junction domain** was not reached in probe 1 (95 mV at most). In probe 2 at
    the 0.01 cell it came within 1.9 mV (118.1 mV) at a block site (§2.2).
- **Stimuli and controls.** Scheduled `channel_controls` give cation-conductance stimuli,
  sodium-disabled controls and passive controls. `electrode_current_injection@1` (composite)
  gives current stimuli.
- **Checks, paths and the clean booking.** The host checks on every accepted row, the device
  row checks (vector windows) and @3's `trapezoid_nonnegative@1` junction-heat booking.

### 2.2 Limits found, with their scope

| Limit | Where it was found | Scope |
| --- | --- | --- |
| **The channel laws' −120 to +60 mV domain** (`channel_domain_valid`, for every active population of a cell, leaks included) | One scan corner, c_m 0.01, NaV1.2 1e-6, Kv1.5 1e-7: a 247 V/s upstroke reached +59.7 mV and was refused at every sub-step. The chosen 0.01 cell (A) peaks at +56.65 mV, 3.35 mV inside | Its neighbour at Kv1.5 1e-6 peaked at +45 mV and passed. At 0.05, point 2's mid-chain peak is +11 mV against +35 mV alone. §7.3 checks published overshoots against it |
| **The junction gate law's ±120 mV domain** (`junction_voltage_relaxation@1`'s `domain_valid`, applied to every junction, pinned and closed ones included) | Probe 2 at A: at the blocking segment the entry junction reached 106 mV (r = 0.02) and 118.1 mV (r = 0.01) | Not refused, but 1.9 mV inside, and rising as the boundary's coupling falls. A boundary below s·r_gj = 10 at A (range 136 mV) is expected to be refused, and so is a block site of any cell whose range exceeds 120 mV, cardiac cells included (§7.3). The floor to plan on is s·r_gj ≥ 20. **The mechanism to add:** `junction_ungated@1` (§1.2, §3.3, §11) |
| **A low safety factor at 0.05 F/m²** | Probe 2 at point 2: every perturbed segment blocked; coupling-only 0.1 fired through at 3.9× slower and failed at the exit | A property of the 0.05 cell's weak, graded excitability. At 0.01 the same segment slows conduction up to 2× before it blocks (§1.2) |
| **The default junction-heat booking** (`explicit_tableau`) | Refused by the host dissipation check mid-wave, at 4.29 ms in the chain | It books a negative increment where Vj crosses zero. `trapezoid_nonnegative@1`, the booking E07-v1 registered, runs clean |
| **Large steps on the upstroke** | At point 2, ARS(2,2,2) at 0.25 ms and above refuses itself: dt × membrane_rate reaches 3.6 at 1 ms. The host energy-ledger check (relative residual above 2e-3) refuses at 100 µs at point 2, at 25 µs at the chain's stimulus onset, and at 0.25–1 ms in the heredity cell | 5 µs is accepted in chains and 50 µs in a single cell from a kick. The 25 µs chain refusal falls at the stimulus onset, so the wave's own largest step is not yet established. The planned 10 µs never ran: the driver's ladder excluded its own cap |
| **The explicit junction bound** dt ≤ 1/(2 max_i Σ_j G_j/C_i) | Static, at definition time | In the chain, 39 µs at s = 1000, scaling as 1/s (13 µs at s = 3000). A hexagon interior cell's bound is a third of the chain's (§8); §4.2 covers cardiomyocyte sizes |
| **Near-threshold behaviour** | At c_m 0.05, kicks just below the overshoot threshold fire after 25–40 ms of latency with reduced peaks | This is Hodgkin–Huxley-type latency with accumulating inactivation. The firing boundary must be located by its own test (§6) |

**Not established:**
- whether the heredity densities themselves propagate (no chain ran at point 1);
- the block threshold at A between r = 0.5 (exits) and 0.02 (blocks), which was not sampled;
- slow conduction within a block-adjacent regime at A, and any exit block there;
- the wave's largest admissible step;
- any sheet run: every value is from chains.

## 3. Entities, state and laws (D142)

### 3.1 Entities touched

| Entity (CURRENT_PLAN's table) | State it owns | What excitable tissue adds |
| --- | --- | --- |
| Membrane domain | Area, capacitance | Nothing new. Specific capacitance is a declared parameter (the probe used 0.05 and 0.01 F/m²) |
| Functional-unit population | Channel populations: law, P_max, abundance, gates, ledgers | New laws (§3.3). Populations keep @3's format: one law, permeant ions, gate state, availability schedule |
| Contact | Junction area, permeabilities, gate state, availability | Nothing new in v1. A Vj-dependent connexin-type gate is a later law |
| Cell | Volume, inventory, charge, voltage | Nothing new. Activation and recovery records are observations (§5), not state of the cell |
| Extracellular | Held baths (v1); finite extracellular space later | v1 assays use held baths. Finite extracellular conduction waits for the sparse solver (§4.3) |

### 3.2 Where new laws enter: pending M4

New laws take **new law IDs** (D147, D148). **Qualified @3 changes nowhere.**
- @3's `LAW_CODES` is a closed table, and its dispatch evaluates every law for every
  population. Adding a code therefore changes every @3 program, which crossrev would flag.
- The composite takes one inner identity (`INNER_MODEL_IDS`, `pump_composite.INNERS`).

**The route is not ruled here** (the lead, 14 November). Four notes of that day want something
inside @3, and two bound-term fixes are queued as well:
- these new laws;
- FR-4's pump;
- FR-1's implicit bounding patch;
- the coupling note's stage hook.

They become **one inner-model design note, which the lead commissions**. Tracks do not fork @3
separately, so the route stays "pending M4".

**What Track E needs from that note:**
- **Laws as declarations.** Each law declares its kinetics, opening, gate count, permeant ions,
  its own voltage domain and its conductance-bound term.
- **Static dispatch.** Only the laws a definition declares are traced.
- **The currents stay in the explicit stages.** Every channel current stays inside the IMEX
  explicit stages, under the exponential gates and the explicit-stage refusal.
- **@3's laws unchanged.** @3's five laws give the same results under the new inner model as
  under @3. The check is **program identity plus CPU runs**: the checked step's jaxpr,
  constants and lowered StableHLO, as crossrev compares them, with @3's test and
  qualification worlds run on CPU. It is not L4 bitwise equality: at 825 nodes @3 does not
  repeat bitwise against itself on the L4 (D168, G2-Q1's Q7).
- **Operators carry over only with their guards.** Each composition over the new inner model
  gets its own guard (the lead's ruling on Q2).
- **A junction route without the gate law's domain:** `junction_ungated@1` (§3.3, §3.4), so a
  block site is not refused at |Vj| > 120 mV (§1.2).

**Routes already weighed, as input to that note:**
- **A composite split operator for the excitable currents** is unsuitable: it would split the
  upstroke from the coupling that propagates it, and duplicate the population concept.
- **@3's `membrane_process` hook** is not admissible: its contract forbids conductance outside
  the family's bound.

**The generic cell needs no new law** (§1), provided every junction stays at s·r_gj ≥ 20 at A
(§1.2). Its work runs on @3 itself. Below that floor it needs `junction_ungated@1`.

### 3.3 The laws (new IDs, mechanism names, cited)

Each law states its source, units, domain and conductance bound, uses no protein name (the
protein-catalogue rule), and has a component reference test.

**The old catalogue comes first (D167).** D167's staged move takes old-family physics into the
composite when a consumer needs it. The channel library goes first, through Track E, and
calcium handling goes with excitable tissue. So before any law is written from a cardiac
paper, the mouse currents are matched to the 56-law catalogue's process modules
(`processes/`):

| Mouse current | Already in the old catalogue (moved first) | Missing, so a new law from a paper |
| --- | --- | --- |
| Fast sodium | `nav1p2_m3h_regularized@1` (in @3), `nav1p3_m3h_regularized@1`, `navrat1/2/3_m3h_regularized@1` (m³h, fast inactivation); `nav1p6_persistent_m@1`; `nav_ml_instantaneous@1` | The slow-recovery (j) gate, if the comparison needs slow recovery |
| Transient outward K (Ito) | `kv1p4_mh@1`, an inactivating Kv1 law (mouse Ito,s is attributed to Kv1.4; source not re-checked here); `kv3p4_mh@1`; `k_fast_mh@1` | Kv4-type kinetics for Ito,f, only if the catalogue's A-type laws cannot stand in |
| Inward rectifier IK1 | `kir_ml_instantaneous@1`, an instantaneous rectifier (Morris–Lecar family); `kir2p1_mh2@1` (in @3, kinetic) | None |
| Sustained delayed rectifiers (IKur, IKss) | `kv1p5_mh@1` (in @3; mouse IKur is attributed to Kv1.5, London et al. 2001), `kv2p1_mh@1`, `kv2p2_mh@1`, the ML laws `kv1p5_ml_dynamic_m@1`, `kv1p5s_ml_slow_dynamic_m@1`, `kv2p1_ml_dynamic_m@1` | None, for a first comparison |
| L-type Ca | `cav1p2_m2h@1`, `cav1p3_m2h@1`, `ca_l2_m2h@1`, `ca_l3_shift15_m2h@1`, `cav_l_ml_instantaneous@1`, `cav_l_ml2_instantaneous@1` (voltage-gated). Owned cytosolic Ca, ER and IP3 in `resolved_calcium@11` | Ca-dependent inactivation |

**The genuinely new mechanisms are short.** They are the fast sodium current's slow-recovery
gate, the L-type current's Ca-dependent inactivation and, perhaps, Kv4-type Ito,f kinetics.
For the junctions there is one more: a route without the gate law's 120 mV domain (§3.4).
Everything else is moved from the catalogue under D167. The catalogue's laws keep their
BETSE-parity status: moving one is not calibrating it.

The proposed IDs for the new mechanisms, written only if the moved catalogue laws cannot
serve:

| Law (proposed ID) | Mechanism | For | Sources |
| --- | --- | --- | --- |
| *(no channel law for the generic cell)* | The generic cell uses @3's five laws | Qualification (§6) | BETSE v1.5.0 classes, as in the equations appendix |
| `junction_ungated@1` | The junction's constant-field flux at its availability, with no voltage gate. Its domain needs only finite voltages, since the constant-field flux is defined at every voltage | Block sites at A below s·r_gj = 20; any cell whose range exceeds 120 mV, cardiac cells included (§1.2) | @3's `constant_field@1` junction flux (equations appendix). The snapshot's only junction conductance law is `junction_voltage_relaxation@1`, so the catalogue holds no ungated route to move |
| `fast_sodium_m3hj@1` | Fast sodium current with fast (h) and slow (j) inactivation, the j gate setting slow recovery; its own declared domain (§7.3) | Mouse, then human | Beeler and Reuter 1977 introduced the j gate; Luo and Rudy 1991 re-fitted it; the ten Tusscher and O'Hara models keep it. Bondarenko et al. 2004's mouse INa is a Markov model, so a Markov form is a second law if the comparison follows that model |
| `l_type_calcium_cdi@1` | L-type Ca current with voltage activation and inactivation and Ca-dependent inactivation, built on the moved catalogue CaV law and the moved calcium handling | The plateau and APD; slow conduction under reduced coupling (Shaw and Rudy 1997) | Luo and Rudy 1994 (the dynamic model's two papers), and the species models. It needs cytosolic Ca, buffering and minimal release and uptake: D167 moves calcium handling with excitable tissue (M5) |
| `transient_outward_potassium@1` (only if needed) | Kv4-type fast transient outward K current | Mouse Ito,f; human Ito | Bondarenko et al. 2004; O'Hara et al. 2011 |

**Covered by moved catalogue laws, so no new law:**
- **The instantaneous inward rectifier,** by `kir_ml_instantaneous@1`. The cardiac models' IK1
  is time-independent (Beeler and Reuter 1977; Luo and Rudy 1991; ten Tusscher et al. 2004
  and 2006). O'Hara et al. 2011 add a time-dependent gate, a later variant if a comparison
  needs it.
- **The sustained delayed rectifiers,** by the Kv1.5 and Kv2 laws.
- **Each moved law keeps its source and parity status.** Fitting one to a mouse current is a
  calibration step, recorded as such.

### 3.4 Gap-junction conduction

**v1** is @3's constant-field junction: its area and permeabilities, availability from
`junction_controls`, and the gate pinned open. Track E's perturbation and its passive control
arm both act on availability.
- **Coupling** is reported as g_j (nS) and g_j/C (1/s). Those, not the factor s, set the
  physics and the step bound.
- **The gate law's domain binds v1, even pinned open.** Its `domain_valid` refuses
  |Vj| > 120 mV on every junction, closed ones included. At A that limits planning to
  s·r_gj ≥ 20 at every junction (§1.2).
- **`junction_ungated@1` lifts that limit** (§3.3). It enters through the lead's inner-model
  note (§3.2), and it is qualified by four checks:
  - inside 120 mV it reproduces @3's pinned-open junction to rounding, in CPU runs of @3's
    chain worlds;
  - beyond 120 mV, a two-cell case matches the appendix's junction flux, computed
    independently;
  - charge and species are conserved, and its heat is booked non-negative;
  - probe 2's segment case at A, with s·r_gj below 10, runs without refusal.
- **Later:** a connexin-type gate (Vj-dependent, seconds), or heterogeneous junction
  abundance as contact state (CURRENT_PLAN's planned entity row). Each takes its own ID.

## 4. Numerics

### 4.1 The upstroke and the step

- **What refuses and when.** The upstroke is the stiff event.
  - At point 2, ARS(2,2,2)'s explicit channel currents refuse themselves at 0.25 ms and above.
  - The host energy-ledger tolerance (2e-3 of the flows) refuses 100 µs at point 2, and 25 µs
    at the chain's stimulus onset.
  - The heredity cell's slower upstroke is refused by the energy check alone, at 0.25–1 ms.
  - **The stimulus onset (M1).** A switched conductance stimulus is refused at its onset by the
    host energy ledger, with the cells at rest, when its strength times the step reaches 4e-12 m.
    It is accepted at 2e-12 m:

    | | Strength at 2.5 µs | at 5 µs | at 10 µs |
    | --- | --- | --- | --- |
    | Accepted (2e-12 m) | 8e-7 m/s | 4e-7 | 2e-7 |
    | Refused (4e-12 m) | 1.6e-6 m/s | 8e-7 | 4e-7 |

    The protocol's stimuli keep strength × step ≤ 2e-12 m, or ramp their onset. This is a limit of
    the stimulus form, not of the tissue (`excitable_qualification_v1.json`, `stimulus_onset`).
- **What converges.** ARS(2,2,2) is second order (single cell: peak error 1.5e-7 V at 10 µs
  against RK4), Euler first order. In the chain, CV at 5 µs and 2.5 µs agrees to 1.1e-6.
- **The working step is 5 µs for chains.** The wave's own largest step is a qualification
  development run (§6): 10 µs and 25 µs with the stimulus onset outside the measured window.
- **At the generic cell (A),** whose upstroke is three times faster than point 2's, the 40-cell
  chains ran at 5 and 2.5 µs without a refusal. The energy residual was at most 2.1e-4 at
  5 µs and 5.0e-5 at 2.5 µs, against 2e-3. Its largest admissible step is unmeasured, and the
  sheet's junction bound (2.6 µs at s = 1000, §4.2) may bind first.
- **@3's RK4 reference path** needs steps of 2.5 µs or less with NaV1.2. It is the step
  reference for small worlds only.

### 4.2 Propagation and the IMEX split

@3 makes only face electromigration implicit. Membranes and **junctions** stay explicit
(`numerics/surface_imex.py`). So the static bound dt ≤ 1/(2 max_i Σ_j g_j/C_i) applies, and it
depends on **g_j/C, not g_j alone**.

| Configuration | C | g_j per junction | Junctions per cell | Σ g_j/C | Bound |
| --- | --- | --- | --- | --- | --- |
| 0.05 cell, s = 1000 (probe 1) | 16.3 pF | 104.5 nS | 2 (chain) | 12,800/s | 39 µs |
| 0.05 cell, s = 1000, hexagon interior | 16.3 pF | 104.5 nS | 6 | 38,500/s | 13 µs (`StepChecks`: 13.0) |
| **0.01 cell (the generic cell), s = 1000, chain** | 3.26 pF | 104.5 nS | 2 | 64,100/s | 7.8 µs |
| **0.01 cell, s = 1000, hexagon interior** | 3.26 pF | 104.5 nS | 6 | 192,000/s | **2.6 µs** (`StepChecks`) |
| 0.01 cell, s = 300, hexagon interior | 3.26 pF | 31.4 nS | 6 | 57,700/s | 8.7 µs (`StepChecks`) |
| **Mouse coupling on the 0.05 cell** (s ≈ 5,400) | 16.3 pF | 558–588 nS (Yao et al. 2003, abstract) | 2 / 6 | 70,000 / 210,000/s | **7 µs / 2.4 µs** |
| **Mouse coupling on the 0.01 cell** (s ≈ 5,400) | 3.26 pF | 558–588 nS | 2 / 6 | 350,000 / 1,050,000/s | **1.4 µs / 0.5 µs** |
| Mouse coupling on a mouse-sized cell | about 140 pF (Xu, Guo and Nerbonne 1999; Brunet et al. 2004) | 558–588 nS | 2 / 6 | 8,200 / 24,600/s | 61 µs / 20 µs |

**Mouse coupling on a small cell binds.**
- At 16.3 pF the bounds are about 7 µs in a chain and 2.4 µs in the sheet.
- At the generic cell's 3.26 pF they are 1.4 and 0.5 µs.
- Mouse coupling on a mouse-sized cell does not bind, at about 20–61 µs.

So **the junction-implicit IMEX is deferred only on a condition**, and that condition is an
M4 prerequisite (§11). The solver would be a new solver ID, with junction electromigration
under frozen junction weights in the operator C + a dt (L_face + L_junction). Its operator is
SPD and sparse on the junction graph, and its heat could be booked like the faces' (J²RT/W,
non-negative).
- **The condition:** every M4 world declares its cells at their own capacitance, and keeps
  2 Σ_j g_j/C below 1/dt at the step the upstroke needs (5 µs: Σ_j g_j/C below 100,000/s).
- **If it fails, the solver is an M4 prerequisite.** That happens for mouse coupling on small
  cells.
- **At the generic cell's 0.01 F/m² the condition already fails in the sheet at s = 1000.**
  There the hexagon's bound is 2.6 µs (the engine's `StepChecks`, 127 cells, 342 junctions),
  so 5 µs is refused. M2 and M3 therefore take one of two settings, decided in the protocol:
  - s = 1000 at 2.5 µs, which doubles the steps;
  - a baseline of s = 300, whose bound is 8.7 µs, at 5 µs. Nothing at A has run at s = 300,
    so this setting has no propagation, CV or segment evidence yet.

  Chains at s = 1000 stay at 5 µs (bound 7.8 µs).
- **The junction-implicit solver is therefore an M3 option, not only an M4 one,** if the
  first experiment needs s = 1000 at 5 µs on the 0.01 sheet.

### 4.3 The field solve

- **Held-bath sheets** have diagonal field matrices: the 127-cell sheet's 254 nodes cost
  8.25 ms per step on one CPU core, plus 2.0 ms of device checks
  ([field-solver note](FIELD_SOLVER_INTERFACE_DESIGN.md) §2).
- **Finite extracellular worlds** carry a wavefront's return current through the faces, so
  the dense node-space solves (about 100 ms per step at 825 nodes on CPU) and D147's
  version 3 for free offsets apply. Conduction there waits for the sparse field solver and
  GH200.
- **Any joint world with division** is capped at 64 field nodes with held baths
  (`pump_composite_adapter.FIELD_INPUT_NODE_CAP`). Partition also refuses water, pumps on the
  dividing cell and replacement, so excitable assays on dividing tissue are not v1.

### 4.4 Ledgers

- **Excitable runs declare `trapezoid_nonnegative@1` by driver rule** (the lead's ruling on
  Q4). There is no "excitable world" predicate for a definition check to refuse on.
- **The rule is backed by the run-time refusal.** The probe showed the host dissipation check
  refusing the default booking mid-wave, so a run that breaks the rule stops.
- **The energy rule stays as it is.** It is what refuses coarse steps.

### 4.5 Two clocks (D155; D153)

| | Slow world | Conduction assay |
| --- | --- | --- |
| Step | 1 ms (E07-v1 at 1–5 ms) | 5 µs (§4.1) |
| Runs | Hours | A short stimulus protocol, 50–200 ms |
| Starts from | Its own definition | The slow world's frozen state at a chosen time |

- **The assay is a new run** of a definition whose initial values are imported: D153's
  rule (b). It records the source snapshot's manifest digest and identity, claims no
  continuity, and is judged on its own.
- **Why not a branch.** `branch_checkpoint` refuses a change of execution settings (dt), and
  `refinement_times` admit only `resolved_cotransport_water@1`.
- **The import belongs with D153's open rule (b) records** (the lead's ruling on Q5). The
  existing pattern is `heredity_turnover_literature.start_state` with its `importcheck`. That check runs the imported definition without events at the source's own
  step (5 ms) for 60 s. It compares Vm at the source's record times (largest |ΔVm|) and the
  layout (largest absolute difference) with the source. It is an agreement check, not a
  bitwise one.
  - A general importer for @3 (and @4) carries amounts, charges, gates, junction gates and
    availabilities into the assay definition, with the same kind of check at the slow world's
    own step.
  - **Whether a bitwise check is attainable is to be tested.** An import re-bases the amounts
    and zeroes the ledgers, so rounding can differ from the source's next step.
  - **An unstimulated imported state must stay at rest.** At the assay's own step, with no
    stimulus, for the protocol's length, every cell stays within a declared band of its
    imported voltage. An import that drifts or fires is refused before any stimulus runs.
- **What refuses if a slow-world cell fires at 1 ms.** The run stops with a refusal, never
  integrating silently.
  - A fast upstroke (point 2) is refused by @3's explicit-stage bound: dt × membrane_rate
    reached 3.6 at 1 ms.
  - A slower one (the heredity cell) is refused by the host energy-ledger check (relative
    residual above 2e-3).
- **v1 is one-way.** Assay results are readouts of the slow world's state, with no feedback
  into it.
- **The cost ratio.** 100 ms of assay is 20,000 steps, about 20 s of slow-world time at 1 ms.

## 5. Conduction observables

All of these are derived observations with one declared owner (D143's observation ownership,
D154's run view).

| Observable | Definition (from the probe) |
| --- | --- |
| Activation time | Each cell's upward crossing of a declared level (−30 mV) after a declared arming time, interpolated within the accepted step; every crossing kept |
| Activation by the cell's own upstroke (M1) | Over the cell's rise from −50 mV to its peak: the inward part of its net ionic membrane current, integrated (its **inward charge**), and its largest dVm/dt. The **source fraction** is the inward charge over C (V_peak − V_rest). A passive cell is a pure sink, with zero inward charge. A perturbed cell counts as activated only when it is a source. The threshold is registered from development runs, with passive twins as its measured floor. M1 showed why a peak margin cannot serve: strongly coupled cells peak within a few mV of their passive twins |
| Conduction velocity | Inverse least-squares slope of activation time against path distance, over a declared span, in cells/s and m/s. In 2-D, from the activation-time gradient |
| Refractoriness and recovery | The S1–S2 interval bracket for a response at a declared site, and for a second far-end wave; APD50 and APD90 from the upstroke |
| Capture | **A launched front** (M1):<br>• every cell crosses the level;<br>• the stimulated cells cross within the stimulus;<br>• the mean activation per graph-distance ring from the stimulated cells rises strictly;<br>• every ring at distance ≥ 2 activates after the stimulus ends.<br>The front need not be steady: on the hexagon its column steps shrink. The bracket is reported in stimulus width and strength. M1's first rule ("every cell crosses") passed a delayed, synchronous firing at s = 1000 |
| Block | The coupling or perturbation bracket between block and propagation, with the last activated cell |
| Re-entry (later) | Phase singularities and cycle length, once the scale allows (§8) |

**How they are recorded.**
- **In v1, on the host.** M2 and M3 run `resolved_pump_tissue@3` itself, with activation times
  taken on the host from @3's own readouts, compiled on each window's accepted history. That is
  what the probe did, because the observer costs 2.3–5 ms per row.
- **Later, in state, through one shared door.** Track R's crossing record is the same
  mechanism (the lead's ruling on Q3). So in-state event times have **one door**: an
  observation-only operator, provisionally `threshold_crossing_record@1`, shared by Track E's
  activation times and Track R's crossings. Per entity it holds a declared variable's first
  and last crossing of a declared level and the crossing count. It writes no inner field.
  - Runs that use it are `resolved_pump_composite@1` development compositions (D143).
  - They are outside D147's automatic solver choice, so each world records its free field
    offsets and its declared solver.
  - The operator needs the composite's idle guard: equal to the composition without it.

## 6. Qualification

The first qualification is **on the generic cell (0.01 F/m², candidate A of §1.2), running
`resolved_pump_tissue@3`** (no operator), against independent references.
- **Who writes them.** One fresh agent writes them, for both Track E and Track R, from
  [the equations appendix](EXCITABLE_TISSUE_EQUATIONS.md). It never reads the driver or the
  engine, as in S5's R-ops and R-tissue and D152's references. The appendix carries the
  mid-chain segment case and the 0.01 F/m² cells (its §8.5–§8.6).
- **The protocol.** PROPOSED, then registered, with its tolerances set before the judged run.

| Reference | What it checks | Source |
| --- | --- | --- |
| R-cell | Single-cell AP features, the kick and stimulus thresholds, the firing boundary (located by its own bisection on regenerative rise) and S1–S2 | Independent stiff integration of the appendix's equations |
| R-cable | Spatial coupling in the passive control: steady attenuation and charging modes of the linearised discrete cable. Per-cell decay θ with cosh θ = 1 + g_m/(2 g_j) (g_m the membrane slope conductance at rest), and the sealed-end chain's discrete solution | Analytic; the linearisation computed by the reference |
| R-wave | CV against coupling, the block bracket, capture and recovery for chains of the protocol's lengths | The commissioned independent implementation of the active equations |
| R-limit | Approach to the continuum at strong coupling: CV × L against a 1-D cable of the same kinetics, as diffusion D = g_j L²/C grows. Propagation failure below a finite coupling (Keener 1987). The engine side is bounded: the step shrinks as 1/s, and end effects should lengthen, so the protocol states its coupling range (s up to 3000 in chains, at 1.25–5 µs) and chain lengths | The reference's fine-grid 1-D solver |
| R-benchmark (later) | Activation times in the N-version slab (Niederer et al. 2011, ten Tusscher–Panfilov 2006 human cell) | Needs the human laws and the user's approval (D138) |

**Framing.**
- R-wave and R-limit follow Hodgkin and Huxley's (1952) test: they compute the propagated
  velocity of a declared kinetic scheme and set it against the engine's. Their computed
  18.8 m/s matched a measured 21.2 m/s.
- Pathmanathan and Gray (2014) give manufactured-solution problems for cardiac solvers. Those
  test a solver but not a travelling wave, so they complement R-wave rather than replace it.
- Rudy and Quan (1987) and Keener (1987) frame the effects of discrete cellular structure,
  including propagation failure at finite coupling. Kléber and Rudy (2004) review the
  mechanisms.
- **The wider channel catalogue is not an independent reference.** These are the
  `resolved_tissue@5`–`@12`, `resolved_calcium*` and `resolved_calcium_energy*` families.
  - They are RK4-only, at 298.15 K, with steps of 2.5 µs or less for sodium and 1.25 µs for
    CaV.
  - They share `laws/channels/sodium_channels.py`, `potassium_channels.py`, `voltage_gates.py`
    and the constant-field transport with @3.
  - They can serve as a cross-integrator consistency check of the generic cell's equations at
    298.15 K: `surface_pump_v3_fixtures.catalog_reference` rewrites an @3 world as
    `resolved_tissue@8`.
  - No probe run backs this yet.

**The protocol carries D150's and MG0c's lessons from the start** (the lead's ruling on Q6):
- **a scope line:** generic cell, held-bath chains and the 127-cell sheet, `resolved_pump_tissue@3`,
  the step and coupling range, and what it does not qualify;
- **one judged bound not scaled from the engine's own runs.** Each tolerance comes from the
  references' own convergence or from a stated physical scale, never from the engine's spread;
- **judged controls by parameter:** planted errors of registered size in a parameter (a
  junction permeability, a NaV1.2 density) that the judge must catch;
- **a guards entry and a combined verdict:** the static guards and the crossrev identity of
  the run's programs listed beside the judged items, and one verdict over both;
- **timing rules:** what is timed, on which core, and when timing is not judged;
- **near-threshold block cases excluded up front.** Block brackets are judged on cases
  declared away from the threshold. Near-threshold cases are reported, not judged, because
  the probe showed long-latency graded responses there;
- **the backend named:** CPU for the judged run. The L4 is not bitwise at scale (D168), so any
  GPU item is a tolerance item of its own.

**Development runs before registration**, which close the probe's C4 and C5 gaps:
- 10 µs and 25 µs with the stimulus onset excluded from the measured window;
- length checks at s = 100 and 3000, as well as 1000;
- **a stimulus shorter than 1 ms, or a later first measured cell.** At the 0.01 cell, C1's
  after-the-stimulus clause fails with a 1 ms stimulus: the wave activates cells 6 and 7 before
  the stimulus ends;
- **the segment cases at the generic cell,** with the block threshold bracketed between
  r = 0.5 and 0.02, and the junction voltage at the blocking boundary reported against
  120 mV;
- **at s = 300, if the protocol takes it,** the segment cases and the floor s·r_gj ≥ 20 checked
  again, since nothing at A has run there;
- **a coupling sweep towards block at A that respects the junction domain.** Near block, a
  uniform chain puts most of the action-potential range across the wavefront's junction:
  probe 1 reached 95 mV at s = 10 on point 2's smaller range. A refusal at the junction domain
  is reported as that limit, not as block, and the block bracket is stated only where no
  junction refuses;
- chains of 80 cells, with spans that exclude the first ten cells beyond the stimulus and the
  last ten;
- CV at two stimulus strengths;
- block of a travelling wave: a uniform chain with a reduced-coupling segment downstream.

## 7. Cardiac realism and species (D155 item 5)

### 7.1 Stated plainly

The generic cell's action potential is not cardiac.

| Cell | APD | Upstroke | Peak |
| --- | --- | --- | --- |
| **Candidate A, the generic cell** (0.01 F/m²) | APD90 3.8 ms | 230–248 V/s | +56 mV alone; +40 to +42 mV mid-chain at s = 1000 |
| Point 2 (0.05 F/m², probe 1) | APD90 12 ms | 82 V/s | +35 mV alone; +11 mV mid-chain at s = 1000, 41 V/s |
| Mouse ventricle | About 14–50 ms by preparation and temperature (isolated cells 13.7–20.3 ms, Brouillette et al. 2004; 45 ms at 22–24 °C, Wang et al. 2005; intact tissue 36–37 ms, Anumonwo et al. 2001; about 50 ms, Kaese and Verheule 2012) | 114–154 V/s in tissue (Anumonwo et al. 2001); 309–394 V/s in isolated cells (Remme et al. 2009) | About +40 mV in an isolated cell; +4 to +17 mV in tissue (§7.3) |
| Human ventricle | About 275 ms (O'Hara et al. 2011, endocardial, 1 Hz); 454–510 ms in isolated non-failing myocytes at 35–37 °C (Johnson et al. 2018) | 254 V/s (O'Hara et al. 2011); 228–326 V/s in tissue (Drouin et al. 1995, secondary) | +36 to +43 mV (§7.3) |

- **Slowing before block.** Without a plateau current, point 2's uniform chain slowed only
  about sevenfold before block (probe 1's coupling sweep, to 292 cells/s). At A, probe 2's
  segment slowed conduction at most 2.0×, and every slowed case exited; the block threshold
  between r = 0.5 and 0.02 was not sampled. Shaw and Rudy (1997) found reduced coupling could slow conduction to
  0.26 cm/s, a factor of about 200, before block, sustained by ICa(L).
- **So a mouse comparison of reduced coupling needs** the L-type Ca current, and the law set
  of §3.3: a fast sodium current with slow recovery (Nav1.5-like), Ito, an instantaneous IK1,
  and the sustained K currents. The first qualification stays on the generic cell.
- **Point 2's 12 ms APD90 sits just below the short end of the mouse range** (14–50 ms), with
  no plateau. Its 82 V/s upstroke is below the mouse's 114–394 V/s.
- **A's 3.8 ms APD90 is far below the mouse range.** Its 230–248 V/s upstroke lies inside the
  mouse's, and its +56 mV peak is above the isolated mouse cell's +40 mV.
- No scan point approaches the human 260–510 ms.

### 7.2 Species and parameter sources

| | Generic (qualification) | Mouse (first comparison) | Human (second) |
| --- | --- | --- | --- |
| Cell | Heredity cell geometry (area 3.26e-10 m², volume 0.75 pL, 9.25 µm spacing) at **0.01 F/m²**, 3.26 pF, by the lead's ruling after probe 2 | 122–147 pF (Brunet et al. 2004); 142 ± 4 pF (Xu, Guo and Nerbonne 1999); about 132 × 21 × 10 µm (Benndorf et al. 1985, chamber unstated) | Per the human model (O'Hara et al. 2011) |
| Currents | @3's five laws at candidate A: NaV1.2 1e-6, Kir2.1 1e-8 and Kv1.5 3e-7 m/s, with the leaks and pump of the heredity cell. Peak +56.65 mV, and junction voltage at block 118.1 mV: both inside their domains by under 4 mV | Bondarenko et al. 2004 (298 K) or Morotti et al. 2014 (37 °C) | O'Hara et al. 2011; ten Tusscher and Panfilov 2006 |
| Coupling | g_j from the factor s | 558–588 nS (Yao et al. 2003, mouse pairs; abstract only, culture status unverified); Cx43-knockout pairs 4–11 nS | From the model's tissue conductivity |
| Targets | None (the qualification is numerical) | CV 30–60 cm/s; APD about 50 ms; ERP 33–80 ms; heart rate 500–724/min (Kaese and Verheule 2012) | CV 45 cm/s at 1 Hz, 70 from rest (O'Hara et al. 2011); ERP 223–257 ms (Kaese and Verheule 2012) |
| Newborn or immature cells | Reduced NaV and coupling availability | The paper's reductions (Supplementary Tables 1–2, requested) | hiPSC-CM models (Paci et al. 2013): immature INa, If and IK1 |

**Mixed strands** of stem-cell-derived and primary cardiomyocytes conduct slowly: 5.5 cm/s,
against 34.9 cm/s in primary strands (Kucera et al. 2015). Strands with Cx43-knockout cells
slow and block non-linearly with the knockout fraction (Prudat and Kucera 2014). These are
Track E's nearest experimental anchors.

### 7.3 The +60 mV domain against published overshoots

Peaks are as printed, or derived as rest + amplitude where marked. They were checked by a
web-search subagent on 14 November 2026; sources reached only through abstracts or secondary
tables are marked.

| Preparation | Peak | Rest | APD90 | dV/dt max | Source |
| --- | --- | --- | --- | --- | --- |
| Mouse, isolated RV myocytes, 20–22 and 32 °C | About +40 mV (one example cell) | −73.7 mV | 13.7 ms (room temperature), 20.3 ms (32 °C), example cells | — | Brouillette et al. 2004, J Physiol 559:777 |
| Mouse, intact ventricle, 38 °C | +4 to +17 mV (derived) | −73 to −77 mV | 36–37 ms | 114–154 V/s | Anumonwo et al. 2001, Circ Res 89:329, Table 2 |
| Mouse, isolated LV myocytes, 37 °C | — | — | — | 309–394 V/s | Remme et al. 2009, Basic Res Cardiol 104:511 |
| Mouse models | Not stated in text (plotted only) | — | About 35 ms (Morotti et al. 2014) | — | Bondarenko et al. 2004; Morotti et al. 2014 |
| Human, isolated non-failing LV myocytes, 35–37 °C | +36 to +46 mV (derived; +46 mV is the sub-endocardial row, −85 mV with 131 mV amplitude) | −83 to −86 mV | 454–510 ms | — | Johnson et al. 2018, Circ Arrhythm Electrophysiol 11:e005914, Table 2 |
| Human tissue and isolated cells | Amplitudes 119–131 mV, so about +36 to +48 mV at the mean rest of −83 mV (derived) | Mean −83 mV | 263–271 ms (Li et al. 1998, failing hearts) | 228–326 V/s (Drouin et al. 1995) | Via Bueno-Orovio et al. 2008's tables (secondary) |
| Human models | O'Hara et al. 2011: +40.0 mV (Paci et al. 2015's table); +35 to +39 mV derived (Elshrif and Cherry 2014). ten Tusscher models: about +38 to +39 mV derived | About −86 to −88 mV | ORd 229–349 ms by cell type | ORd 216–259 V/s; TP06 368 V/s (single cell) | Secondary tables, as named |
| hiPSC-CM, ventricular-like | +28.3 mV | MDP −75.6 mV | 415 ms | 27.8 V/s | Ma et al. 2011, via Paci et al. 2015 (secondary) |

**The finding.** Published overshoots lie between about +4 and +48 mV, at least 12 mV inside
@3's +60 mV.

**What follows:**
- **The margin is at least 12 mV.** Whether that is within reach is the coordinator's call. This
  note's reading is that the domain does not, on these numbers, call for a new fast-sodium law
  of its own.
- The new laws that the mouse comparison needs anyway (§3.3) declare their own domains. Each
  must cover its cell's range; −120 to +60 mV covers these.
- The probe's refused corner reached +59.7 mV with @3's laws at c_m 0.01 and NaV1.2 ×4, with
  the weakest Kv1.5 and no fast K current to limit the peak. A calibrated law set has those
  currents.
- **The margin is the open point.** Under a constant-field driving force a Cells cell's peak
  can differ from a model's linear one. A calibrated cell's component test should report its
  peak against its domain.

## 8. Scale: the wavelength against the 127-cell sheet

The wavelength is λ = CV × the refractory period (Smeets et al. 1986; Kaese and Verheule 2012).

**The sheet.** The 127-cell hexagon is 13 cells across. Its ring at graph distance r has 6r
cells, so the longest circuits are 24–36 cells (rings 4–6).

| Cell and coupling | CV | Refractory period | λ | Re-entry in 127 cells? |
| --- | --- | --- | --- | --- |
| 0.01 cell (the generic cell), s = 1000 | 8,277 cells/s (probe 2, A) | Not measured (APD90 3.8 ms) | Unmeasured; at an assumed 10 ms, about 80 cells | No |
| 0.05 cell, s = 1000 | 2,086–2,124 cells/s | 25–30 ms (chain S1–S2) | 52–64 cells | No |
| 0.05 cell, s = 300 | 1,110 cells/s | 25–30 ms (assumed) | 28–33 cells | Marginal |
| 0.05 cell, s = 100 | 572 cells/s | 25–30 ms (assumed) | 14–17 cells | Fits |
| Mouse, normal | 30–60 cm/s | ERP 33–80 ms | 1.0–4.8 cm, so 75–360 cells of about 132 µm | No: a circuit needs a radius of 12–58 cells, a sheet of about 450–10,000 cells; the top end exceeds the dense solver's 2,048 nodes |
| Mouse, near block | 1–5 cm/s, an assumed slow range (Shaw and Rudy's model reached 0.26 cm/s) | About 50 ms | 4–19 cells | Fits |
| Human, normal | 45–80 cm/s | 223–257 ms | 10–20 cm, so 1,000–2,000 cells | No: needs at least 10⁵ cells, so the sparse solver and GH200 |

**What fits the sheet.**
- **Block, as a yes/no outcome, fits at every coupling the junction domain admits** (at A,
  every junction at s·r_gj ≥ 20, §1.2).
- **A boundary-free CV at s = 1000 does not fit, on this evidence.** In the 0.05 chain, the
  stimulus transient covered about the first ten cells past the stimulus, and the sealed end the last
  seven or eight. The 20-cell chain never reached a steady delay, and the sheet is 13 cells
  across.
- **Every value above is a two-neighbour chain value.** No sheet run exists, and couplings
  other than s = 1000 have no length check.
- **The s = 100 length check (§6) decides** whether slowing can be read as a CV in the sheet at
  reduced coupling, or only as activation delays against the unperturbed sheet.

**Re-entry.**
- At normal conduction it needs the sparse field solver and GH200, as D155 expected.
- **The exception is re-entry through slowed conduction.** Track E's own perturbation regime
  (the generic cell at reduced coupling; mouse cells near block) could fit 127 cells. The
  first experiment's readouts should watch for it, not assume it away.

**The step in the sheet.** An interior hexagon cell has six junctions, so its explicit bound is
a third of the chain's (the engine's `StepChecks` on the 127-cell hexagon):
- at 0.01 F/m² (the generic cell): 26 µs at s = 100, 8.7 µs at s = 300, **2.6 µs at
  s = 1000**, and 0.87 µs at s = 3000. The 5 µs step therefore needs s ≤ 300 (§4.2);
- at 0.05 F/m²: 130 µs, 43 µs, 13 µs and 4.3 µs.

## 9. Cost

**Measured (CPU, one loaded core):**

| Run | Execution | Host checks and observer | Note |
| --- | --- | --- | --- |
| Single cell, ARS(2,2,2) | 0.13–0.21 ms per step | 2.3–3.5 ms per row | Host checks dominate |
| 20-cell chain, 5 µs (0.05 cell) | 1.07 ms per step | 5.2 ms per row | Host checks dominate |
| 40-cell chain, 5 and 2.5 µs (probe 2: 44 segment cases, 0.05 and 0.01 cells) | 0.95–2.37 ms per step | 2.7–6.6 ms per row | 25–147 s per case. The 0.01 sweep (24 cases) took 16.5 min |
| Vector-window path with device checks | 0.78 ms per world-step | — | 2 × 10,000 steps in 15.5 s |

Compiles take 20–40 s and are cached afterwards. Peak memory was 1.4–1.7 GB in probe 1 and
0.7–1.2 GB in probe 2.

**The qualification** (§6) is about 150 engine runs, mostly chains of 20–80 cells at 5 µs.
- On the host path that is about 5–10 CPU-hours; running the bulk on the vector path brings
  it to about 3.
- The references' own cost is separate.

**The first experiment** (§10) runs about 84 sheet worlds (the 127-cell sheet; 2 arms × 6
fractions × 7 arrangements, the scattered ones by seed).
- At 10 ms per step, 100 ms at 5 µs is 20,000 steps, about 200 s per world. That makes about
  5 CPU-hours per stimulus site on the vector path; host checks on every row would multiply
  it.
- That is for s = 300 at 5 µs. At the 0.01 cell with s = 1000, the sheet needs 2.5 µs (§4.2),
  which doubles it to about 10 CPU-hours per stimulus site.
- On the L4, a batch of 84 should take tens of minutes. That is an estimate: @3 on the 825-node
  world measured 2.28 ms per world-step at 256 worlds, and the 254-node sheet is unmeasured.

## 10. Track E's first experiment (a sketch, for registration later)

| | |
| --- | --- |
| **Question** | In a coupled excitable sheet, does a cluster of cells with reduced sodium availability and reduced coupling slow or block conduction more than the same fraction scattered? |
| **Engine models** | `resolved_pump_tissue@3` (the generic 0.01 F/m² cell, `trapezoid_nonnegative@1`), with activation analysed on the host (§5). Later the mouse law set through @4 |
| **World** | The 127-cell held-bath hexagon (`validation/stationary/worlds.hexagon(6)`), each cell the generic 0.01 F/m² cell at its relaxed rest. At s = 1000 the sheet's bound is 2.6 µs, so the protocol chooses between s = 1000 at 2.5 µs and s = 300 (bound 8.7 µs) at 5 µs (§4.2). The perturbation only loosens the bound |
| **Stimulus** | A planar edge stimulus, or a corner stimulus, declared per arm. Each one's width and strength must launch a front by §5's capture rule. At s = 300 the 1 ms planar stimulus at 2e-7 m/s does so in M1's control, though only by 0.04 ms (ring 2 at 3.04 ms). A shorter stimulus is safer |
| **Perturbation** | For a fraction f of cells: NaV1.2 availability × r_Na (`channel_controls`) and availability × r_gj on every junction incident to them (`junction_controls`), from t = 0 |
| **Sweep** | f ∈ {0, 0.05, 0.1, 0.2, 0.3, 0.5}. At fixed f, the arrangements are one compact disc, two discs, and scattered (5 seeds), with a clustering index (cluster-internal junction fraction) |
| **Passive control arm** | The same sweep on the passive sheet (every voltage-gated population unavailable), with junction availability on the same schedule and a weak current or conductance stimulus. It reports electrotonic spread (space constant, input resistance, attenuation map) and so separates coupling geometry from excitability |
| **Readouts** | Activation map; total activation time; activation delays across and beyond the cluster against the unperturbed sheet, the far column's mean delay among them; activation inside the cluster by each cell's own upstroke (§5); capture; and, from §8, any re-entry in the slow regime. A local CV inside the cluster is reported only if §6's length checks show one exists at that coupling |
| **Values** | A generic sweep: r_Na and r_gj over a declared grid, informed by probe 2's segment results (§1). At A every junction keeps s·r_gj ≥ 20 (r_gj ≥ 0.02 at s = 1000, about 0.07 at s = 300), because a boundary below s·r_gj = 10 is expected to be refused by the junction gate law's domain (§1.2). The grid goes lower only if `junction_ungated@1` comes first (§3.3), or if the lead chooses B after its own segment run (§12). Every run reports its block-site junction voltage against 120 mV. The paper's Supplementary Tables 1–2 are not needed for it; they enter at M4, where a mouse comparison maps transcript fold changes to availabilities under a declared assumption |
| **Predictions** | Registered before runs (D155 item 2), with thresholds, and tested on arrangements M1 did not run (other fractions, seeds and two discs). On the sheet the front goes around a cluster rather than being blocked beyond it, as M1's s = 300 runs showed, so the candidates are phrased for that. Each cites M1's development value at f = 0.15:<br>• **(Q1) Arrangement:** at equal f and r, scattered cells delay the far column more than one compact disc. M1: 0.36 against 0.21 ms at s·r_gj = 20. This is Prudat and Kucera's (2014) meandering.<br>• **(Q2) The load peaks:** a compact disc's far-column delay rises as its coupling falls from full, peaks at intermediate coupling, and falls as the disc decouples and the front passes around it. M1: the peak lies near s·r_gj = 36–54 in all three disc arms.<br>• **(Q3) Load, not excitability, at low coupling:** below that peak the combined arm's delay matches its passive twin's. Above it the passive twin delays more than the active disc, whose own sodium current offsets its load. M1: equal at s·r_gj = 20 and 24; at 210, 0.142 (passive) against 0.080 ms.<br>• **(Q4) Inside the cluster:** activation is lost gradually as r falls, interior cells first, read by each cell's own upstroke. M1, by peaks: two interior cells below 0 mV at s·r_gj ≤ 24, boundary cells above.<br>• **(Q5) No block beyond the cluster within the floor:** every unperturbed cell activates at s·r_gj ≥ 20. With `junction_ungated@1` (ruling 3's second option) the same question is asked below 20.<br>• **(Q6) The passive arm predicts the excitable arm's far-column delay** where Q3 says load dominates.<br>Earlier candidates that assumed block beyond the cluster (compact versus scattered block thresholds; uncoupling restoring conduction, after Rohr et al. 1997) move to the option with `junction_ungated@1` |
| **Refusals (a proposal; D170's fallback covers M1 only)** | **The corner margin is thin.** M1 at s = 300 peaked at +57.7 mV at a far corner, 2.3 mV inside +60, with edges near +57.3 mV. Every run therefore reports per-class peaks and margins (corner, rim, end, collision, before block, and the perturbed cells), flagging any under 3 mV. At s = 1000 under a launched front (M1 amendment 1) the binding class was a perturbed disc cell, at +57.58 mV.<br>**If an M3 case at A is refused on the channel domain at a corner, an edge or a perturbed cell:** the case is not an outcome. That arm's comparison keeps only the strengths at which every arrangement ran without refusal, and the refusal is reported with its cell class.<br>**If the unperturbed control is refused, or refusals remove more than one strength from an arm,** M3 moves wholesale to B (peak +37.6 mV). That needs B's sheet development run in M1 first, because B has none |
| **Gate** | After the qualification's judged run |

## 11. Milestones, effort and refusals

| Milestone | Engine models | Content | Effort |
| --- | --- | --- | --- |
| M0 (done) | `resolved_pump_tissue@3` | The probe and this note | — |
| M1 | `resolved_pump_tissue@3` | The conduction observables as a host analysis (§5); the rule (b) assay importer with its agreement check (§4.5); the trapezoid booking as a driver rule; the qualification protocol, PROPOSED, with §6's development runs. The importer is validation tooling used by a milestone that runs @3; if the lead reads it as tooling on its own, it needs the user's approval | About 4–6 agent-days, 1 CPU-hour |
| M2 | `resolved_pump_tissue@3` | R-cell, R-cable, R-wave and R-limit by one fresh agent (for Tracks E and R); the protocol registered; the judged qualification on the generic 0.01 F/m² cell | About 4 agent-days (references), about 3 CPU-hours |
| M3 | `resolved_pump_tissue@3` | The first experiment as a generic sweep, registered with its predictions; s = 1000 at 2.5 µs or s = 300 at 5 µs on the sheet (§4.2); s·r_gj ≥ 20 at every junction at A (§10) | About 3 agent-days; about 5 CPU-hours per stimulus site at s = 300, about 10 at s = 1000 and 2.5 µs, or under an L4-hour |
| M4 | The inner model of the lead's inner-model note; compositions over it as `resolved_pump_composite@1` | The catalogue laws of §3.3 moved under D167, then the few new laws (§3.3) with component references; optionally `threshold_crossing_record@1` (§5) with its idle guard. **Prerequisites:** `junction_ungated@1`, the junction route of §1.2 and §3.3 (M3's too, if its grid goes below s·r_gj = 20 at A); the lead's inner-model design note (§3.2); the user's D138 approval for assembling and comparing against a published whole-cell model (single cited laws need none); the paper's Supplementary Tables 1–2; and §4.2's condition, failing which the junction-implicit solver comes first | About 10–15 agent-days |
| M5 | That inner model with the calcium laws | Calcium handling moved from the old calcium families (D167's order), with Ca-dependent inactivation for the L-type current; then the human law set; re-entry on large sheets with the sparse solver and GH200 | A track of its own |

**Refused in v1:**
- `explicit_tableau` junction heat in excitable runs (§4.4; a driver rule, backed by the
  run-time dissipation refusal);
- channel voltages outside each law's domain (already enforced);
- RK4 beyond small reference worlds;
- finite extracellular conduction (§4.3);
- division, water and replacement in conduction assays (§4.3);
- feedback from assay to slow world (§4.5).

**Not authorised by this note:**
- any change to @3 or to qualified models;
- a law named after a protein;
- a feature for this paper alone (D144);
- reproducing a published cardiac model's AP as a benchmark without the user's approval
  (D138, D151).

## 12. Rulings and open questions

**The lead's rulings** (14 November, with the advisor):
- **Q1, the route for new laws:** pending M4, not ruled. One inner-model design note, which the
  lead commissions, gathers every request to change @3 (§3.2). Its check against @3 is program
  identity plus CPU runs.
- **Q2:** each composition over the new inner model gets its own guard.
- **Q3:** activation times are taken on the host for now. In-state event times later go
  through one door shared with Track R's crossing record (§5).
- **Q4:** the trapezoid booking is a driver rule, backed by the run-time dissipation refusal
  (§4.4).
- **Q5:** the importer belongs with D153's open rule (b) records. An unstimulated imported
  state must stay at rest, and a slow-world cell firing at 1 ms is refused (§4.5).
- **Q6:** the protocol carries D150's and MG0c's lessons (§6).
- **Capacitance:** the generic cell uses 0.01 F/m² if probe 2 shows it fires, repolarises and
  propagates inside the domain; otherwise 0.05, with the reason.
  - **Applied:** candidate A passes by amendment 3's text, so the generic cell is 0.01 F/m² at
    candidate A (§7.2). The driver's record names B, by its stricter test (§1.2).
  - **Its margins are recorded:** +56.65 mV against +60, and 118.1 mV against 120 at a block
    site.
  - **B also passed the domain part.** Its peak-to-rest range is 117 mV against A's 136.
    - It keeps 22 mV of channel margin.
    - It stays below the junction limit at a block site whose neighbour is at rest.
    - But its after-hyperpolarisation (−84.6 mV) takes its full range to 122 mV.
    - Its segment response was not run.
- **The user:** no questions now. D138 gates M4 only, and the Supplementary Tables are M4
  prerequisites (§11).

**Still open, for the lead:**
1. **The generic cell's junction margin.** At A, a boundary below s·r_gj = 10 is expected to
   be refused (§1.2).
   - **Recommended:** confirm A, and keep every M3 junction at s·r_gj ≥ 20. If the protocol
     takes s = 300, that floor (r_gj ≥ about 0.07) is checked first in its development runs,
     since nothing at A has run there.
   - **The alternatives:** B, after its own segment run (minutes on CPU); or
     `junction_ungated@1` before M3, which needs the route Q1 holds pending.
2. **The importer's carriage** from a Track R composite: volumes under water, and junction
   availability with replacement's formation factor. Recommended: the effective availability at
   the import time, frozen, with the factor's source recorded. Water's volumes are refused
   until the assay's identity takes water.
3. **The qualification's tolerances**, and whether the probe's driver becomes the protocol's
   development driver. Its step ladder must then include its own cap.
4. **GH200 time** for re-entry at normal conduction (§8), when it becomes a target.

## 13. Sources

**Probe and verification.**
- Evidence: `/mnt/workspaces/Cells/excitable-tissue-20261114-01/`. Snapshots: snapshot-02
  (0da0218), snapshot-03 (9b48454), snapshot-04 (e051362) and snapshot-05 (4649012, probe 2),
  all clean.
- The citations below were checked against PubMed, PMC or the publisher by web-search
  subagents on 14 November 2026. Keener 1987 was confirmed through Crossref only.

**References.**
- Beeler G. W., Reuter H. (1977). J Physiol 268:177–210.
- Benndorf K., Boldt W., Nilius B. (1985). Pflügers Arch 404:190–196.
- Bondarenko V. E. et al. (2004). Am J Physiol Heart Circ Physiol 287:H1378–H1403.
- Brunet S. et al. (2004). J Physiol 559:103–120.
- Hodgkin A. L., Huxley A. F. (1952). J Physiol 117:500–544. Computed 18.8 m/s against
  21.2 m/s measured, at 18.5 °C.
- Kaese S., Verheule S. (2012). Front Physiol 3:345.
- Keener J. P. (1987). SIAM J Appl Math 47:556–572.
- Kléber A. G., Rudy Y. (2004). Physiol Rev 84:431–488.
- Kucera J. P., Prudat Y., Marcu I. C., Azzarito M., Ullrich N. D. (2015). Front Cell Dev
  Biol 3:58.
- Luo C. H., Rudy Y. (1991). Circ Res 68:1501–1526.
- Metzger P., Weingart R. (1985). J Physiol 366:177–195. Weingart R. (1986). J Physiol
  370:267–284.
- Morotti S. et al. (2014). J Physiol 592:1181–1197.
- Niederer S. A. et al. (2011). Phil Trans R Soc A 369:4331–4351.
- O'Hara T., Virág L., Varró A., Rudy Y. (2011). PLoS Comput Biol 7:e1002061.
- Paci M. et al. (2013). Ann Biomed Eng 41:2334–2348.
- Pathmanathan P., Gray R. A. (2014). Int J Numer Method Biomed Eng 30:525–544.
- Prudat Y., Kucera J. P. (2014). J Mol Cell Cardiol 76:46–54.
- Rohr S., Kucera J. P., Fast V. G., Kléber A. G. (1997). Science 275:841–844.
- Rudy Y., Quan W. L. (1987). Circ Res 61:815–823.
- Rush S., Larsen H. (1978). IEEE Trans Biomed Eng 25:389–392.
- Shaw R. M., Rudy Y. (1997). Circ Res 81:727–741.
- Smeets J. L. et al. (1986). Circ Res 58:96–108.
- ten Tusscher K. H. W. J., Panfilov A. V. (2006). Am J Physiol Heart Circ Physiol
  291:H1088–H1100.
- ten Tusscher K. H. W. J. et al. (2004). Am J Physiol Heart Circ Physiol 286:H1573–H1589.
- Xu H., Guo W., Nerbonne J. M. (1999). J Gen Physiol 113:661–678.

**Added by the second check (§7.3 and the law table).** Some were reached only through an
abstract or a secondary table; those are marked where used.
- Anumonwo J. M. B. et al. (2001). Circ Res 89:329.
- Brouillette J. et al. (2004). J Physiol 559:777.
- Bueno-Orovio A. et al. (2008). J Theor Biol 253:544 (secondary tables for Drouin et al.
  1995, Li et al. 1998 and Näbauer et al. 1996).
- Elshrif M. M., Cherry E. M. (2014). PLoS One 9:e84401.
- Johnson E. K. et al. (2018). Circ Arrhythm Electrophysiol 11:e005914.
- London B. et al. (2001). Circ Res 88:940 (abstract).
- Ma J. et al. (2011). Am J Physiol Heart Circ Physiol 301:H2006 (via Paci et al. 2015).
- Paci M. et al. (2015). Br J Pharmacol 172:5147.
- Remme C. A. et al. (2009). Basic Res Cardiol 104:511.
- Wang Y. et al. (2005). J Physiol 568:423.
- Yao J.-A. et al. (2003). Circ Res 93:736 (abstract).

**Not verified:** Luo and Rudy 1994 (the dynamic model's two papers); the peaks of the
Bondarenko and Morotti mouse models, which are plotted only.
