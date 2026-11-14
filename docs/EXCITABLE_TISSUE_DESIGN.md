# Excitable tissue: design (proposed)

**Status.** Proposed on 14 November 2026 by Track E (D155), for the lead's review with the
advisor. **It contains no code** (D142: design before code).

**The question it serves.** D155's: do weakly coupled cells with low sodium conductance, as
dividing cardiomyocytes become, slow or block conduction, and does their clustering matter? It
serves that question as **general excitable-tissue physics, not a cardiac mode** (D144).

**Evidence.**
- The conduction probe is in
  [excitable-tissue-20261114-01](/mnt/workspaces/Cells/excitable-tissue-20261114-01/):
  `HANDOFF.md` holds the numbers, and `PLAN.md` the criteria and both amendments.
- Its driver is `validation/tissue/excitable_probe.py`.
- Its equations, for the independent reference, are in
  [the equations appendix](EXCITABLE_TISSUE_EQUATIONS.md).

**Engine models the probe ran:** `resolved_pump_tissue@3`, which is
`nav1p2_m3h_regularized@1`, `kir2p1_mh2@1`, `kv1p5_mh@1`, `kleak_always_open@1` and
`naleak_always_open@1` with the following:
- `constant_field@1` leaks and junctions;
- the `nak_atp_mass_action_positive@1` pump;
- the `junction_voltage_relaxation@1` gate, pinned open or as declared;
- IMEX ARS(2,2,2) and Euler with exponential stage gates, and @3's RK4 as the step reference;
- field solver version 2, declared through `field_solver_choice.declare()`, with 0 free
  offsets in every world.

## 1. The probe's verdict, and how it was reached

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

## 2. What the probe shows about the engine

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
  - **The ±120 mV junction domain was not reached.** The largest |Vj| was 95 mV, at s = 10, so
    the domain is untested.
- **Stimuli and controls.** Scheduled `channel_controls` give cation-conductance stimuli,
  sodium-disabled controls and passive controls. `electrode_current_injection@1` (composite)
  gives current stimuli.
- **Checks, paths and the clean booking.** The host checks on every accepted row, the device
  row checks (vector windows) and @3's `trapezoid_nonnegative@1` junction-heat booking.

### 2.2 Limits found, with their scope

| Limit | Where it was found | Scope |
| --- | --- | --- |
| **The channel laws' −120 to +60 mV domain** (`channel_domain_valid`, for every active population of a cell, leaks included) | One scan corner, c_m 0.01, NaV1.2 1e-6, Kv1.5 1e-7: a 247 V/s upstroke reached +59.7 mV and was refused at every sub-step | Its neighbour at Kv1.5 1e-6 peaked at +45 mV and passed. In the chain, point 2's mid-chain peak is +11 mV, against +35 mV alone. §7.3 checks published overshoots against it |
| **The default junction-heat booking** (`explicit_tableau`) | Refused by the host dissipation check mid-wave, at 4.29 ms in the chain | It books a negative increment where Vj crosses zero. `trapezoid_nonnegative@1`, the booking E07-v1 registered, runs clean |
| **Large steps on the upstroke** | At point 2, ARS(2,2,2) at 0.25 ms and above refuses itself: dt × membrane_rate reaches 3.6 at 1 ms. The host energy-ledger check (relative residual above 2e-3) refuses at 100 µs at point 2, at 25 µs at the chain's stimulus onset, and at 0.25–1 ms in the heredity cell | 5 µs is accepted in chains and 50 µs in a single cell from a kick. The 25 µs chain refusal falls at the stimulus onset, so the wave's own largest step is not yet established. The planned 10 µs never ran: the driver's ladder excluded its own cap |
| **The explicit junction bound** dt ≤ 1/(2 max_i Σ_j G_j/C_i) | Static, at definition time | 39 µs at s = 1000, scaling as 1/s (13 µs at s = 3000). See §4.2 for cardiomyocyte sizes |
| **Near-threshold behaviour** | At c_m 0.05, kicks just below the overshoot threshold fire after 25–40 ms of latency with reduced peaks | This is Hodgkin–Huxley-type latency with accumulating inactivation. The firing boundary must be located by its own test (§6) |

**Not established:**
- whether the heredity densities themselves propagate (no chain ran at point 1);
- the c_m 0.01 points, beyond the scan's kick test;
- block of a wave already travelling: block was seen only at the first unstimulated cell;
- the wave's largest admissible step.

## 3. Entities, state and laws (D142)

### 3.1 Entities touched

| Entity (CURRENT_PLAN's table) | State it owns | What excitable tissue adds |
| --- | --- | --- |
| Membrane domain | Area, capacitance | Nothing new. Specific capacitance is a declared parameter (the probe used 0.05 and 0.01 F/m²) |
| Functional-unit population | Channel populations: law, P_max, abundance, gates, ledgers | New laws (§3.3). Populations keep @3's format: one law, permeant ions, gate state, availability schedule |
| Contact | Junction area, permeabilities, gate state, availability | Nothing new in v1. A Vj-dependent connexin-type gate is a later law |
| Cell | Volume, inventory, charge, voltage | Nothing new. Activation and recovery records are observations (§5), not state of the cell |
| Extracellular | Held baths (v1); finite extracellular space later | v1 assays use held baths. Finite extracellular conduction waits for the sparse solver (§4.3) |

### 3.2 Where new laws enter

New laws take **new law IDs** (D147, D148). **Qualified @3 changes nowhere.**
- @3's `LAW_CODES` is a closed table, and its dispatch evaluates every law for every
  population. Adding a code therefore changes every @3 program, which crossrev would flag.
- The composite takes one inner identity (`INNER_MODEL_IDS`, `pump_composite.INNERS`).

Three routes were weighed.

| Route | What it is | Assessment |
| --- | --- | --- |
| **A. A new inner identity, `resolved_pump_tissue@4`** | @3's state, step, checks and ledgers, with the channel laws taken from a **law registry**. Each law object declares its kinetics, opening, gate count, permeant ions, voltage domain and conductance-bound term. Dispatch is static: only the laws a definition declares are traced | **Recommended.** Every channel current stays inside the IMEX explicit stages, under the exponential gates and the explicit-stage refusal. Each law carries its own domain, the precondition for §7.3. Guard: @4 restricted to @3's five laws equals @3 bitwise on @3's test and qualification worlds (as the composite's identity guard did), and enters `INNER_MODEL_IDS` only then |
| B. A composite split operator for excitable currents | Excitable currents and gates in half-steps around @3's step (reaction–diffusion splitting) | Rejected. The upstroke would be split from the coupling that propagates it. The operator would need its own voltage solve, stability rule and ledgers, duplicating the population concept |
| C. @3's in-step `membrane_process` hook | An extra explicit membrane flux | Not admissible. The hook's contract forbids added conductance outside the family's bound, and changing that is an edit to @3 |

**The generic cell needs no new law** (§1). Route A is designed now and built when the mouse
comparison is approved (§7, §11).

### 3.3 The laws (new IDs, mechanism names, cited)

Each law states its source, units, domain and conductance bound, uses no protein name (the
protein-catalogue rule), and has a component reference test.

| Law (proposed ID) | Mechanism | For | Sources |
| --- | --- | --- | --- |
| *(none for v1)* | The generic cell uses @3's five laws | Qualification (§6) | BETSE v1.5.0 classes, as in the equations appendix |
| `fast_sodium_m3hj@1` | Fast sodium current with fast (h) and slow (j) inactivation, the j gate setting slow recovery; its own declared domain (§7.3) | Mouse, then human | Beeler and Reuter 1977 introduced the j gate; Luo and Rudy 1991 re-fitted it; the ten Tusscher and O'Hara models keep it. Bondarenko et al. 2004's mouse INa is a Markov model, so a Markov form is a second law if the mouse comparison follows that model |
| `transient_outward_potassium@1` | Fast transient outward K current, activation and inactivation gates | Mouse (Ito,f; Ito,s); human (Ito) | Bondarenko et al. 2004; O'Hara et al. 2011 |
| `inward_rectifier_instantaneous@1` | Time-independent inward rectifier (Beeler and Reuter 1977; Luo and Rudy 1991; ten Tusscher et al. 2004 and 2006). @3's Kir2.1 law has a kinetic m gate instead. O'Hara et al. 2011 add a time-dependent inactivation gate to the instantaneous rectification (a later variant) | Mouse and human IK1 | As named |
| `sustained_delayed_rectifier@1` | Non-inactivating (or slowly inactivating) delayed rectifier | Mouse (IKur, IKss); human (IKr, IKs as separate laws later) | Bondarenko et al. 2004; O'Hara et al. 2011. The mouse IKur is attributed to Kv1.5, as the 4-AP-sensitive component of IK,slow (London et al. 2001). @3's `kv1p5_mh@1` is BETSE's parity law, not that current's kinetics |
| `l_type_calcium_cdi@1` | L-type Ca current with voltage activation and inactivation and Ca-dependent inactivation | The plateau and APD; slow conduction under reduced coupling (Shaw and Rudy 1997) | Luo and Rudy 1994 (two papers on the dynamic model), and the species models above. **This needs cytosolic Ca, its buffering and a minimal release and uptake, which @3's inventory lacks.** It is a milestone of its own (§11) |

### 3.4 Gap-junction conduction

**v1** is @3's constant-field junction: its area and permeabilities, availability from
`junction_controls`, and the gate pinned open. Track E's perturbation and its passive control
arm both act on availability.
- **Coupling** is reported as g_j (nS) and g_j/C (1/s). Those, not the factor s, set the
  physics and the step bound.
- **Later:** a connexin-type gate (Vj-dependent, seconds), or heterogeneous junction
  abundance as contact state (CURRENT_PLAN's planned entity row). Each takes its own ID.

## 4. Numerics

### 4.1 The upstroke and the step

- **What refuses and when.** The upstroke is the stiff event.
  - At point 2, ARS(2,2,2)'s explicit channel currents refuse themselves at 0.25 ms and above.
  - The host energy-ledger tolerance (2e-3 of the flows) refuses 100 µs at point 2, and 25 µs
    at the chain's stimulus onset.
  - The heredity cell's slower upstroke is refused by the energy check alone, at 0.25–1 ms.
- **What converges.** ARS(2,2,2) is second order (single cell: peak error 1.5e-7 V at 10 µs
  against RK4), Euler first order. In the chain, CV at 5 µs and 2.5 µs agrees to 1.1e-6.
- **The working step is 5 µs for chains.** The wave's own largest step is a qualification
  development run (§6): 10 µs and 25 µs with the stimulus onset outside the measured window.
- **@3's RK4 reference path** needs steps of 2.5 µs or less with NaV1.2. It is the step
  reference for small worlds only.

### 4.2 Propagation and the IMEX split

@3 makes only face electromigration implicit. Membranes and **junctions** stay explicit
(`numerics/surface_imex.py`), so the junction bound dt ≤ 1/(2 max_i Σ_j G_j/C_i) applies.

| Cell | C | g_j | Neighbours | Bound |
| --- | --- | --- | --- | --- |
| The probe's (9.25 µm) | 16.3 pF | 104.5 nS (s = 1000) | 2 | 39 µs |
| Adult mouse ventricular myocyte | about 140 pF (Xu, Guo and Nerbonne 1999; Brunet et al. 2004) | 558–588 nS (mouse pairs, end-to-end and side-to-side: Yao et al. 2003, abstract; adult rat pairs about 0.5 µS: Metzger and Weingart 1985, Weingart 1986) | about 4 effective | about 2 × 4 × 4,100/s, so dt ≤ 30 µs |

**At cardiomyocyte scale the junction bound does not bind** at the 5–10 µs the upstroke needs
anyway. A junction-implicit IMEX (a new solver ID, with junction electromigration under
frozen junction weights in the operator C + a dt (L_face + L_junction)) is therefore
**deferred until a consumer needs larger steps or small, strongly coupled cells.** Its
operator is SPD and sparse on the junction graph, and its heat could be booked like the faces'
(J²RT/W, non-negative).

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

- **Excitable definitions should declare `trapezoid_nonnegative@1`.** In @4, a definition
  check should refuse `explicit_tableau` for definitions with gated sodium populations and
  junctions. This is a decision for the lead.
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
- **The import.** The existing pattern is `heredity_turnover_literature.start_state` with its
  `importcheck`. A general importer for @3 (and @4) carries amounts, charges, gates, junction
  gates and availabilities into the assay definition, with its own import check: at the slow
  world's own dt, the imported definition must reproduce the slow world's next steps bitwise.
- **The slow clock is safe by construction.** An action potential arising in the slow world at
  1 ms is refused (§4.1), not silently mis-integrated.
- **v1 is one-way.** Assay results are readouts of the slow world's state, with no feedback
  into it.
- **The cost ratio.** 100 ms of assay is 20,000 steps, about 20 s of slow-world time at 1 ms.

## 5. Conduction observables

All of these are derived observations with one declared owner (D143's observation ownership,
D154's run view).

| Observable | Definition (from the probe) |
| --- | --- |
| Activation time | Each cell's upward crossing of a declared level (−30 mV) after a declared arming time, interpolated within the accepted step; every crossing kept |
| Conduction velocity | Inverse least-squares slope of activation time against path distance, over a declared span, in cells/s and m/s. In 2-D, from the activation-time gradient |
| Refractoriness and recovery | The S1–S2 interval bracket for a response at a declared site, and for a second far-end wave; APD50 and APD90 from the upstroke |
| Capture | The stimulus bracket for a propagated response |
| Block | The coupling or perturbation bracket between block and propagation, with the last activated cell |
| Re-entry (later) | Phase singularities and cycle length, once the scale allows (§8) |

**How they are recorded.** The probe computed every-step voltages with @3's own readouts,
compiled on each window's accepted history, because the observer costs 2.3–5 ms per row. For
GH200 batches the activation times should be recorded **in state**, by an observation-only
operator.
- Proposed: `activation_time_record@1`. It holds, per cell, the first and last crossing time
  and the crossing count. It writes no inner field, so it is bitwise idle for the physics.
- Its alternative is a host analysis over windows. This is for the lead to choose.

## 6. Qualification

The first qualification is **on the generic cell, point 2**, against independent references.
- **Who writes them.** A separate agent writes them from
  [the equations appendix](EXCITABLE_TISSUE_EQUATIONS.md) and never reads the driver or the
  engine, as in S5's R-ops and R-tissue and D152's references.
- **The protocol.** PROPOSED, then registered, with its tolerances set before the judged run.

| Reference | What it checks | Source |
| --- | --- | --- |
| R-cell | Single-cell AP features, the kick and stimulus thresholds, the firing boundary (located by its own bisection on regenerative rise) and S1–S2 | Independent stiff integration of the appendix's equations |
| R-cable | Spatial coupling in the passive control: steady attenuation and charging modes of the linearised discrete cable. Per-cell decay θ with cosh θ = 1 + g_m/(2 g_j) (g_m the membrane slope conductance at rest), and the sealed-end chain's discrete solution | Analytic; the linearisation computed by the reference |
| R-wave | CV against coupling, the block bracket, capture and recovery for chains of the protocol's lengths | The commissioned independent implementation of the active equations |
| R-limit | Approach to the continuum at strong coupling: CV × L against a 1-D cable of the same kinetics, as diffusion D = g_j L²/C grows. Propagation failure below a finite coupling (Keener 1987) | The reference's fine-grid 1-D solver |
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
  - They share `processes/sodium_channels.py`, `potassium_channels.py`, `voltage_gates.py`
    and the constant-field transport with @3.
  - They can serve as a cross-integrator consistency check of the generic cell's equations at
    298.15 K: `surface_pump_v3_fixtures.catalog_reference` rewrites an @3 world as
    `resolved_tissue@8`.
  - No probe run backs this yet.

**Development runs before registration**, which close the probe's C4 and C5 gaps:
- 10 µs and 25 µs with the stimulus onset excluded from the measured window;
- length checks at s = 100 and 3000, as well as 1000;
- chains of 80 cells, with spans that exclude the first ten cells beyond the stimulus and the
  last ten;
- CV at two stimulus strengths;
- block of a travelling wave: a uniform chain with a reduced-coupling segment downstream.

## 7. Cardiac realism and species (D155 item 5)

### 7.1 Stated plainly

The generic cell's action potential is not cardiac.

| Cell | APD | Upstroke | Peak |
| --- | --- | --- | --- |
| Point 2 | APD90 12 ms | 82 V/s | +35 mV alone; +11 mV mid-chain at s = 1000, 41 V/s |
| Mouse ventricle | About 14–50 ms by preparation and temperature (isolated cells 13.7–20.3 ms, Brouillette et al. 2004; 45 ms at 22–24 °C, Wang et al. 2005; intact tissue 36–37 ms, Anumonwo et al. 2001; about 50 ms, Kaese and Verheule 2012) | 114–154 V/s in tissue (Anumonwo et al. 2001); 309–394 V/s in isolated cells (Remme et al. 2009) | About +40 mV in an isolated cell; +4 to +17 mV in tissue (§7.3) |
| Human ventricle | About 275 ms (O'Hara et al. 2011, endocardial, 1 Hz); 454–510 ms in isolated non-failing myocytes at 35–37 °C (Johnson et al. 2018) | 254 V/s (O'Hara et al. 2011); 228–326 V/s in tissue (Drouin et al. 1995, secondary) | +36 to +43 mV (§7.3) |

- **Slowing before block.** Without a plateau current the generic chain slows only about
  sevenfold before block. Shaw and Rudy (1997) found reduced coupling could slow conduction to
  0.26 cm/s, a factor of about 200, before block, sustained by ICa(L).
- **So a mouse comparison of reduced coupling needs** the L-type Ca current, and the law set
  of §3.3: a fast sodium current with slow recovery (Nav1.5-like), Ito, an instantaneous IK1,
  and the sustained K currents. The first qualification stays on the generic cell.
- **Point 2's 12 ms APD90 sits just below the short end of the mouse range** (14–50 ms), with
  no plateau. Its 82 V/s upstroke is below the mouse's 114–394 V/s. Neither it nor any scan point
  approaches the human 260–510 ms.

### 7.2 Species and parameter sources

| | Generic (qualification) | Mouse (first comparison) | Human (second) |
| --- | --- | --- | --- |
| Cell | Heredity cell geometry: area 3.26e-10 m², volume 0.75 pL, 9.25 µm spacing | 122–147 pF (Brunet et al. 2004); 142 ± 4 pF (Xu, Guo and Nerbonne 1999); about 132 × 21 × 10 µm (Benndorf et al. 1985, chamber unstated) | Per the human model (O'Hara et al. 2011) |
| Currents | @3's five laws at point 2 | Bondarenko et al. 2004 (298 K) or Morotti et al. 2014 (37 °C) | O'Hara et al. 2011; ten Tusscher and Panfilov 2006 |
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
| Human, isolated non-failing LV myocytes, 35–37 °C | +36 to +43 mV (derived) | −83 to −86 mV | 454–510 ms | — | Johnson et al. 2018, Circ Arrhythm Electrophysiol 11:e005914, Table 2 |
| Human tissue and isolated cells | Amplitudes 119–131 mV, so about +36 to +48 mV at the mean rest of −83 mV (derived) | Mean −83 mV | 263–271 ms (Li et al. 1998, failing hearts) | 228–326 V/s (Drouin et al. 1995) | Via Bueno-Orovio et al. 2008's tables (secondary) |
| Human models | O'Hara et al. 2011: +40.0 mV (Paci et al. 2015's table); +35 to +39 mV derived (Elshrif and Cherry 2014). ten Tusscher models: about +38 to +39 mV derived | About −86 to −88 mV | ORd 229–349 ms by cell type | ORd 216–259 V/s; TP06 368 V/s (single cell) | Secondary tables, as named |
| hiPSC-CM, ventricular-like | +28.3 mV | MDP −75.6 mV | 415 ms | 27.8 V/s | Ma et al. 2011, via Paci et al. 2015 (secondary) |

**The finding.** Published overshoots lie between about +4 and +48 mV, at least 12 mV inside
@3's +60 mV.

**What follows:**
- The domain does **not**, on these numbers, call for a new fast-sodium law of its own.
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
| Generic, s = 1000 | 2,086–2,124 cells/s | 25–30 ms (chain S1–S2) | 52–64 cells | No |
| Generic, s = 300 | 1,110 cells/s | 25–30 ms (assumed) | 28–33 cells | Marginal |
| Generic, s = 100 | 572 cells/s | 25–30 ms (assumed) | 14–17 cells | Fits |
| Mouse, normal | 30–60 cm/s | ERP 33–80 ms | 1.0–4.8 cm, so 75–360 cells of about 132 µm | No: a circuit needs a radius of 12–58 cells, a sheet of about 450–10,000 cells; the top end exceeds the dense solver's 2,048 nodes |
| Mouse, near block | 1–5 cm/s, an assumed slow range (Shaw and Rudy's model reached 0.26 cm/s) | About 50 ms | 4–19 cells | Fits |
| Human, normal | 45–80 cm/s | 223–257 ms | 10–20 cm, so 1,000–2,000 cells | No: needs at least 10⁵ cells, so the sparse solver and GH200 |

**Slowing and block fit the 127-cell sheet at every coupling.** Re-entry at normal conduction
needs the sparse field solver and GH200, as D155 expected.

**The exception is re-entry through slowed conduction.** Track E's own perturbation regime
(the generic cell at reduced coupling; mouse cells near block) could fit 127 cells. The first
experiment's readouts should therefore watch for it, not assume it away.

## 9. Cost

**Measured (CPU, one loaded core):**

| Run | Execution | Host checks and observer | Note |
| --- | --- | --- | --- |
| Single cell, ARS(2,2,2) | 0.13–0.21 ms per step | 2.3–3.5 ms per row | Host checks dominate |
| 20-cell chain, 5 µs | 1.07 ms per step | 5.2 ms per row | Host checks dominate |
| Vector-window path with device checks | 0.78 ms per world-step | — | 2 × 10,000 steps in 15.5 s |

Compiles take 20–40 s and are cached afterwards. Peak memory is 1.4–1.7 GB.

**The qualification** (§6) is about 150 engine runs, mostly chains of 20–80 cells at 5 µs.
- On the host path that is about 5–10 CPU-hours; running the bulk on the vector path brings
  it to about 3.
- The references' own cost is separate.

**The first experiment** (§10) runs about 84 sheet worlds (the 127-cell sheet; 2 arms × 6
fractions × 7 arrangements, the scattered ones by seed).
- At 10 ms per step, 100 ms at 5 µs is 20,000 steps, about 200 s per world. That makes about
  5 CPU-hours per stimulus site on the vector path; host checks on every row would multiply
  it.
- On the L4, a batch of 84 should take tens of minutes. That is an estimate: @3 on the 825-node
  world measured 2.28 ms per world-step at 256 worlds, and the 254-node sheet is unmeasured.

## 10. Track E's first experiment (a sketch, for registration later)

| | |
| --- | --- |
| **Question** | In a coupled excitable sheet, does a cluster of cells with reduced sodium availability and reduced coupling slow or block conduction more than the same fraction scattered? |
| **Engine models** | `resolved_pump_tissue@3` (generic cell at point 2, `trapezoid_nonnegative@1`). Later the mouse law set through @4 |
| **World** | The 127-cell held-bath hexagon (`validation/stationary/worlds.hexagon(6)`), each cell at the point's relaxed rest |
| **Stimulus** | A planar edge stimulus or a corner stimulus, declared per arm |
| **Perturbation** | For a fraction f of cells: NaV1.2 availability × r_Na (`channel_controls`) and availability × r_gj on every junction incident to them (`junction_controls`), from t = 0 |
| **Sweep** | f ∈ {0, 0.05, 0.1, 0.2, 0.3, 0.5}. At fixed f, the arrangements are one compact disc, two discs, and scattered (5 seeds), with a clustering index (cluster-internal junction fraction) |
| **Passive control arm** | The same sweep on the passive sheet (every voltage-gated population unavailable), with junction availability on the same schedule and a weak current or conductance stimulus. It reports electrotonic spread (space constant, input resistance, attenuation map) and so separates coupling geometry from excitability |
| **Readouts** | Activation map; total activation time; local CV inside, around and beyond the cluster; block (cells not activated); capture; and, from §8, any re-entry in the slow regime |
| **Values** | r_Na and r_gj wait for the paper's Supplementary Tables 1–2 (asked of the user, D155). The mapping from transcript fold change to availability is a declared assumption, swept around its value |
| **Predictions** | Registered before runs (D155 item 2). Candidates: (P1) at equal f, a compact cluster blocks at a higher r than scattered cells (source–sink); (P2) scattered cells slow conduction more at low f (Prudat and Kucera 2014's meandering); (P3) the passive arm's attenuation map predicts the excitable arm's block sites; (P4) where a cluster's boundary is a source–sink mismatch, partial uniform uncoupling can restore conduction (Rohr et al. 1997) |
| **Gate** | After the qualification's judged run |

## 11. Milestones, effort and refusals

| Milestone | Content | Effort |
| --- | --- | --- |
| M0 (done) | The probe and this note | — |
| M1 | The conduction observables (§5) and the rule (b) assay importer with its import check (§4.5). The trapezoid-booking definition check. The qualification protocol, PROPOSED, with §6's development runs | About 4–6 agent-days, 1 CPU-hour |
| M2 | R-cell, R-cable, R-wave and R-limit by a separate agent; the protocol registered; the judged qualification on the generic cell | About 4 agent-days (references), about 3 CPU-hours |
| M3 | The first experiment, registered with its predictions once Supplementary Tables 1–2 are in hand | About 3 agent-days, about 5 CPU-hours or under an L4-hour |
| M4 | Route A: `resolved_pump_tissue@4` with the law registry, its bitwise guard against @3, `INNER_MODEL_IDS`. Then the mouse law set (§3.3) with component references | About 10–15 agent-days; needs the user's D138 decision |
| M5 | Cytosolic Ca with buffering and minimal release and uptake for `l_type_calcium_cdi@1`; then the human law set; re-entry on large sheets with the sparse solver and GH200 | A track of its own |

**Refused in v1:**
- `explicit_tableau` junction heat in excitable definitions (§4.4);
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

## 12. Open questions

**For the lead:**
1. **Route A** (an inner identity with a law registry), or another route for new laws (§3.2)?
   Recommended: A, built at M4.
2. **Activation times recorded in state** by an observation-only operator, or by host
   analysis (§5)? Recommended: the operator, for GH200 batches.
3. **Refuse `explicit_tableau`** for excitable definitions (§4.4)? Recommended: yes, as a
   definition check in @4. Until then, as a driver rule.
4. **The rule (b) importer**: where it lives (validation, as `start_state` does) and its
   import check (§4.5).
5. **The qualification's tolerances**, and whether the probe's driver becomes the protocol's
   development driver. Its step ladder must then include its cap.

**For the user:**
1. **The perturbation's values.** Supplementary Tables 1–2 and the source data of the paper
   (D155).
2. **D138.** May Track E implement the current formulations of a published mouse model
   (Bondarenko et al. 2004 or Morotti et al. 2014), and later a human one (O'Hara et al.
   2011; ten Tusscher and Panfilov 2006), as Cells laws under mechanism names, and compare
   with their published action potentials and the N-version benchmark? Approval is per paper.
3. **The generic cell's specific capacitance.** BETSE's default 0.05 F/m² (the probe's
   point 2), or the physiological 0.01 F/m² that the scan showed gives faster, sharper
   action potentials?
4. **GH200 time** for re-entry at normal conduction (§8), when it becomes a target.

## 13. Sources

**Probe and verification.**
- Evidence: `/mnt/workspaces/Cells/excitable-tissue-20261114-01/`. Snapshots: snapshot-02
  (0da0218), snapshot-03 (9b48454) and snapshot-04 (e051362), all clean.
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
