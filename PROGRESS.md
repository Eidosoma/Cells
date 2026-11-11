# Progress

Last updated: 2026-11-10 UTC.

This is the source of current implementation status. Milestone definitions live
in [Roadmap](docs/ROADMAP.md), scientific updates in
[Scientific basis](docs/SCIENTIFIC_BASIS.md), and design choices in
[Decisions](docs/DECISIONS.md). The complete status history up to 8 November
2026, with every earlier run summary and its evidence links, is preserved in
[the archived progress file](docs/history/PROGRESS_BEFORE_2026-11-08.md).

## Current position

- **Reset on 8 November: BETSE is an external reference, not part of the engine.**
  From 30 October the work drifted into re-hosting and transcribing BETSE inside
  `src/cells` (`betse_native_*`, about 110K lines; `betse_normal_*`, about 50K
  lines). The resulting end-to-end demonstration compared BETSE with BETSE; no
  Cells engine model ran in it. That track is superseded; its code was removed
  from the tree (stage A, below) and remains at tag `native-betse-frozen-2026-11-08`.
  Run evidence under `/mnt/workspaces/Cells` is untouched. The rule is in
  `AGENTS.md`.
- **Native demonstration outcome:** 15 actual launches (6–8 November) never
  reached tissue geometry. Every failure was in the provenance, observer, memory
  or wall-time layer. [Actual16](/mnt/workspaces/Cells/native-basic-end-to-end-20261105-01/actual-original-16/failure.json)
  stopped at its 1,800-second limit at 16:06:11 UTC, 20.5 minutes into phase
  construction. This track produced no numerical BETSE or Cells result.
- **Single lead agent from 8 November**, with at most four subagents on disjoint
  files. Work continues on `main`; milestones are tagged.

## Plan: BETSE parity on CPU and L4, then JUPITER (from 8 November)

Target: BETSE parity of the Cells engine, compared against output from plain
BETSE and run on CPU and the local L4. The JUPITER allocation (10,000 GH200
GPU-hours over about three months) follows; this session moves there when it
starts, and production design is deferred until parity is established.

| Step | Work | Status |
| --- | --- | --- |
| 1 | Plain BETSE reference outputs (default world; seven-cell fixture) | Done |
| 2 | Coverage map of default-world mechanisms, and the parity ladder | Done ([map](/mnt/workspaces/Cells/cells-betse-default-coverage-20261108-01/coverage.json)) |
| 3 | Cells run of BETSE's default world, compared with step 1 (physical route, D131) | Passed (pre-registered protocols D and F) |
| 3b | Parity rung 1: Cl/Ca ions plus the plasma-membrane Ca pump (`resolved_pump_tissue@2`) | v1 failed (one item); **v2 passed** (registered after attribution; weaker evidence) |
| 4 | The same comparison on the L4 GPU | Passed (CPU and L4 identical) |
| 5 | Further mechanism families from the parity ladder, on CPU and L4 | **P2 (ECM barriers), P3 (scheduled interventions, first subset) and P4 (general-network channels) passed** on CPU; **P4b (NaV1.2, Kir2.1, Na leak) passed** (three cases; NaV1.2 not yet at the D-state voltage); L4 runs of P2–P4 not yet done |
| 6 | JUPITER environment and one-node pilot | Recipe and runbook ready; untested on site |
| 7 | Stage B: neutral names; physiology stack moved to `validation/betse` | **Done** (tag `stage-b-neutral-names-2026-11-09`) |
| 8 | Re-host the short decodability assays on Cells physics | G0 probe viable; channels next |
| 9 | First heredity experiment, E07-v1 ([design](docs/HEREDITY_FIRST_EXPERIMENT.md)) | Channel model (G1), batched worlds (G4), the ledger rounding fix and @3 device checks landed; @3 on the L4 is 2.28 ms per world-step at 256 worlds (tier 1 about 4,100 L4 GPU-hours execute-only, about 7,200 end to end); GH200 throughput unmeasured. **Pre-screens 7–8 (retention, rim renewal) are in doubt**: they start from the fully loaded stationary D composition (+31% osmolarity), while cue-written discs carry H composition and behave differently (W1 sheet check, pre-screen 9); the design choice waits on fresh-disc runs |
| 10 | Morphogenesis track ([plan](docs/MORPHOGENESIS_PLAN.md); D134) | **MG0a and MG0b passed** (MG0 complete); MG1 (2-D vertex mechanics) next |
| 11 | Optional long-horizon modes (D135): E fixed points and continuation, C projective integration | **E qualified**; **C qualification qual-01 failed** (absolute caps; accuracy against its own estimator passed); F2 not evaluable (no lingering scale found) |

## Runs

Per-run summaries for this plan are added here, newest first, each linking its
machine-readable inputs, results, checks and failures.

- **Heredity pre-screen 9: newcomer rules under turnover (10–11 November;
  development, not judged).** Driver `validation/stationary/heredity_turnover.py`
  (`e06b104`), on `resolved_pump_tissue@3` sheets; 51 runs plus mechanism and
  frozen-composition checks, none refused.
  - **Control rule (open newcomer gates):** the rim stays H and the disc erodes or
    unzips; B1 fails at s 0.3 and 0.6, as predicted.
  - **Inherited gates:** gates to H neighbours carried across the replacement
    (state inheritance, against D133). They renew the rim only partly at s 0.6:
    J 0.811 after one turnover, 0.297 after two.
  - **91-cell disc at s 1.0** (homogeneous, inherit): J = 1.000 through two full
    turnovers, every newcomer converted. A heterogeneous 37-cell world at s 0.6
    fails B1 in the first turnover.
  - **Newcomer composition:** converted newcomers start at H composition and pull
    weaker. They load with τ 40–50 min, and junction conductance rises with ion
    content (×1.57 D–D).
  - **Fresh discs:** at fresh composition, discs are retained to about 3× stronger
    coupling in fast mode (19 cells to s 2.23, 37 cells to 3.10, against 0.766 and
    1.05 loaded).
  - Replacement is done by the driver (engine gap G2, next in the feature queue);
    the gate rate is not configurable (G6).
  - Evidence: [summary](/mnt/workspaces/Cells/heredity-design-20261108-01/prescreen-09-turnover/summary.md),
    `final.json`.
- **Caveat on heredity pre-screens 7–9 (10 November).** Every pre-screen starts
  from the stationary written disc, whose D cells carry the fully loaded slow
  composition (Na+K+M+P about 372–380 mM against 284 mM for H, +31% osmolarity, past
  E07-v1's 15% censor). A disc written by the cue starts with H composition; K and
  anions load with an effective time constant of 40–50 min (pre-screen 9's mechanism
  run). The sign of the effect is mixed: on the held-bath sheet, cue-written 19-cell
  discs at s 1.0 were still held after 20 s where pre-screen 7 predicts loss within
  1 s, while freshly converted cells are weaker neighbours for rim conversion
  (pre-screen 9). A control in W1's driver, started from pre-screen 7's loaded
  disc with no cue, loses the 19-cell disc at s 1.0 in 0.56–0.62 s (pre-screen 7:
  0.5–1 s), so the drivers agree and the starting composition explains the
  difference (development run). A frozen-composition stationary comparison of the
  mechanism (junction conductance rises with ion content in the constant-field law,
  ×1.57 on a D–D junction) is queued. Until they and the
  fresh-disc runs (70 min, with composition and osmotic excess) report, pre-screen
  7's retention thresholds, the "12 of 14 arms fail" reading and the
  stage-A-at-x0.3 recommendation are on hold.
- **Parity P4b, the heredity carrier channels, passes (10 November).** Two protocols,
  registered at `acd4ead` (a merge, so the derivation revision `6239c5d` stays
  reachable), judged once each from a clean snapshot of it on CPU, both phases
  judged, no refusals
  ([judged](/mnt/workspaces/Cells/parity-p4b-channels-20261110-01/judged-01/), `margins.json`).
  `resolved_pump_tissue@3` with NaV1.2, Kir2.1, Na leak and K leak populations against
  BETSE's general network (`Nav1p2`, `Kir2p1`, `NaLeak`, `KLeak`) on the rung-1
  mammal world.

  | Case | Verdict | Worst item | INIT Vm (tol.) | SIM Vm (tol.) |
  | --- | --- | --- | --- | --- |
  | h1: NaV1.2 + leaks in INIT, Kir2.1 on at SIM | pass | 0.41 (INIT ECM M) | 0.40 mV (2) | 0.94 µV (6) |
  | h2: Kir2.1 + leaks in INIT, NaV1.2 on at SIM | pass | 0.35 (SIM ECM Ca) | 0.47 mV (2) | 1.71 µV (20) |
  | kir-h: Kir2.1 alone, tissue Na leak ×0.2 (registered `bc86673`) | pass | 0.35 (SIM ECM M) | 0.30 mV (1) | 4.2 µV (40) |

  - Each channel's effect over the observed error: NaV1.2 Vm 25 (INIT) and 3661 (SIM
    switch-on); Kir2.1 Vm 18 (INIT) and 1485 (SIM switch-on); cell Na and K 130–1800.
  - Formulation check first: Cells' `nav1p2_m3h_regularized@1`, `kir2p1_mh2@1` and
    `naleak_always_open@1` equal BETSE's classes to 5e-14 over −120…+60 mV (Cells
    uses the analytic limits where BETSE gives NaN at −25, −40 and −65.000123 mV).
  - INIT Vm sits at BETSE's own 10 ms step term (0.40 and 0.48 mV measured).
  - **Limits:**
    - **NaV1.2 voltages:** covered from 0 to −16.9 mV (h1) and −27.9 to −34.2 mV (h2).
      The heredity D state (−21.5 mV) lies in the gap between them, and the unstable
      point (−39 mV) lies below them.
    - **Kir2.1 voltages:** covered from 0 to −34.2 mV (h1, h2) and 0 to −91 mV
      (kir-h). kir-h rests at −91 mV, not at H; it passes −80 mV only on the way down
      in INIT, at BETSE's 10 ms steps.
    - **Kinetics:** almost untested. Only NaV1.2 h's lag enters (h2 SIM); τ_m and the
      Kir2.1 time constants are not tested.
    - CPU only, one geometry.
- **Known refusal in the pump family (10 November).** `resolved_pump_tissue@1`–`@3`
  refuse any step in which a junction's power falls by more than about 59%:
  ARS(2,2,2) books junction heat with weights (δ, 1−δ), δ = −0.707, so the booked
  increment goes negative and trips the strict dissipation check. It occurs at
  heterogeneous cue onsets (W1 pilot, 5.000→5.001 s) and on homogeneous sheets
  during disc loss. Stage powers are nonnegative analytically, so an in-step bound
  would never fire; that fix (option I) is withdrawn, and a single wrong-signed
  junction booking is never caught by the energy ledger. Alternatives (an opt-in
  nonnegative booking) are being measured; nothing is changed yet.
- **Parity P3 (scheduled interventions, first subset) passes (10 November).**
  Four protocols, `validation/betse/protocols/physical_p3_*_dense.json`, registered at
  `95f30b5` on `resolved_pump_tissue@3` with the event adapter (`ac2e127`): pump
  block, Na mem ×10 and K mem ×10 on a 19-cell spot, and Na mem plus a full
  gap-junction block. BETSE's events are additive ("multiplier m" gives (1+m)×
  base); pump and junction blocks are global; the junction block maps only as a
  full step held to the end of SIM.
  - The event emulator reproduces plain BETSE to roundoff (SIM Vm 3.2e-13 V), and
    every case's INIT is bitwise rung 1's.
  - Verdict on SIM only; INIT is reported, not judged (event-free and already
    judged in rung 1 and P4; decided before any P3 INIT error was seen).
  - SIM Vm effect over tolerance: pump 197, Na 40, K 113, junction block 102. ECM
    does not move in 35 ms and is listed as non-discriminating.
  - Method: pinned (3 × measured terms); step terms at dt10 with a dt100 order
    check (observed order 0.996–1.086, window 0.9–1.1); no BETSE fine runs (step
    error through the emulator); within-cell patch spread measured by propagation
    instead of P4's heuristic.
  - **Judged once each** from a clean snapshot of `95f30b5`, CPU, 16 min; no refusals
    ([judged](/mnt/workspaces/Cells/parity-p3-interventions-20261110-01/judged-01/), `margins.json`):

    | Case | Verdict | Worst SIM item | SIM Vm error (tol.) | Vm error / raw term sum |
    | --- | --- | --- | --- | --- |
    | Pump block | pass | Vm 0.29 | 2.0 µV (7) | 0.92 |
    | Na mem ×10 | pass | Vm 0.27 | 107 µV (400) | 0.92 |
    | K mem ×10 | pass | ECM K 0.27 (non-discriminating) | 3.5 µV (30) | 0.50 |
    | Na mem + junction block | pass | Vm 0.29 | 14 µV (50) | 0.97 |

  - The measured term sums predict the Vm errors (0.92–0.97 of the raw sum in three
    cases), so the ×3 factor is the whole margin. Na mem's tolerance is wide because
    BETSE advances the junction gate once per ion per step (a 99 µV term).
  - The worst SIM cell Na, K, Cl and M errors are identical in all four cases: the
    offset carried from the shared INIT end, not the events (which move these ions
    10–100× their tolerances). So the cell-ion verdicts lean on the INIT end state,
    which is reported: worst INIT item cell Ca at 0.30 of tolerance, Vm 132 µV (500).
  - **Limits:** Cl mem is not judged (engine gap); sharp steps only, no ramps; the
    junction block only as a held full step; CPU only, one geometry, one 19-cell spot,
    35 ms SIM; all ECM entries non-discriminating.
  - Engine gaps (Cl/Ca mem, environment, temperature, ECM break, external voltage)
    are proposals on hold. Evidence: `/mnt/workspaces/Cells/parity-p3-interventions-20261110-01/`.
- **Device checks and batched worlds for `resolved_pump_tissue@3` landed (10 November).**
  `surface_pump_v3.device_checks` runs @3's own domain, ledger, bound and
  dissipation checks on the device through the shared `row_checks`, with the
  host's functions, names and messages; `ionic_worlds@1` admits @3 under the
  opt-in `world_batching="vmap"`. Host checks and trajectories are unchanged.
  - **Tests:** device and host give the same verdict and first message on 20
    seeded faults covering all 12 checks, at step 0 and 3.6e6; batched
    heterogeneous worlds match single-world runs to 1e-12 relative, and bitwise
    with rewrites disabled; a fault in one world stops vmap and `lax_map` at the
    same step. The four new or changed files are tier 3 (275–604 s each).
  - **Heredity tissue (825 nodes, 2580 channel populations):** host and device
    checks agree on 129 rows on CPU and on the L4 (largest diagnostic
    difference 3.5e-3 of the smallest bound); batched worlds agree with single
    worlds to 1.1e-15 V on the L4.
  - **L4 throughput per world-step:** 12.5 ms at 1 world, 2.64 ms at 64, 2.34 ms
    at 128 and 2.28 ms at 256 (execute only; @1 was 2.10 ms). End to end, with
    host observers every 128 steps, 4.0–4.5 ms. 256 worlds need a preallocated
    allocator on the L4 (on-demand allocation ran out of memory; both failures
    are kept).
  - **Cost:** E07-v1's tier 1 (1,786 world-hours) is about 4,100 L4 GPU-hours
    execute-only (2.28 ms) and about 7,200 end to end with observers (4.01 ms),
    against the design's assumed 560–840 (4.9–13×). The earlier @1 figure of
    6,800 below is end to end. GH200 throughput is the open number.
  - **Gate:** tier 1+2 passed on the branch (326 files; `test_projective_judge`
    then differed only because it predated amendment 2), and again on merged
    main `e79c0b7` from a clean snapshot (266 + 60 files, none changed).
  - Evidence: `/mnt/workspaces/Cells/device-checks-v3-20261109-01/` (gate,
    `study-01-cpu`, `study-01-gpu`, `study-02-gpu`) and
    `/mnt/workspaces/Cells/land-v3-device-20261110-01/`.
- **Projective (C) qualification qual-01: FAIL (9–10 November).** Protocol
  `projective-c-qualification-v1` with amendments 1 and 2, judged once from a
  clean snapshot of `ca70d4a` on CPU float64
  ([judgement](/mnt/workspaces/Cells/projective-c-20261109-01/qual-01/judgement.json)).
  Two cases pass, four fail, F2 is not yet evaluable.
  - **Fails only on the absolute caps** (|dVm| ≤ 20 µV, |dc|/c ≤ 2e-4, the parity
    tolerances), in Q1, Q2, F1 and A1. |dc|/c reaches 1.25e-3 (Q1, F1), 1.16e-3
    (Q2) and 1.53e-3 (A1). The worst entry is cytosolic Na (about 6 mM, |dc| about
    8 µM), over the cap from the first observation after the window opens (60 s).
    |dVm| stays within 20 µV except in A1 (62 µV).
  - **Passes:** pre-run burst growth (0.024 < 0.1), accuracy against the
    estimator allowance in every case (worst ratio 0.40–0.51), energy (defect at
    most 0.09 of its bound), conservation, and F1's fallback around the cue.
  - **Reading:** the per-jump tolerance of 1 µM, summed over 100–170 jumps,
    admits about 0.16 mM, while the cap admits about 1.2 µM at 6 mM Na. The
    error estimator was accurate, but the tolerance it was held to was looser
    than the caps. The verdict stands; a later qualification needs error control
    budgeted against the caps.
  - Reported speed-up: 2.2–3.5× fewer fine steps, 1.4–3.3× wall time.
  - **F2 (switch near the fold) is not evaluable:** the registered NaV1.2
    pre-scan (13 runs on the L4,
    [prescan.json](/mnt/workspaces/Cells/projective-c-20261109-01/qual-01/f2-prescan/prescan.json))
    selected no scale, so the judged pair was not launched. The D state survives
    1800 s at scale 0.72 (Vm −28.2 mV) and switches within 3 s at 0.71, so no
    point on the 1% grid lingers for the required 200–1200 s. A usable F2 needs a
    protocol change (a finer scale step or another starting state).
- **Heredity pre-screen 8: newcomer conversion next to the retention window
  (9–10 November; development, not judged).** Driver
  `validation/stationary/heredity_conversion.py` (`370ceb6`), on
  `resolved_pump_tissue@3` through `stationary_continuation_analysis@1` plus
  600 s forward runs; homogeneous sheets; 63 runs, none refused.
  - **No coupling renews the whole disc** (19, 37, 61, 91 cells). Corner rim
    newcomers never convert: they stay H up to s 0.7 and destroy the disc from
    s 1.0 or at the window edge. Centre newcomers convert everywhere in the
    window; mid-side ones only near s 0.5–1.0; outside newcomers never.
  - A 9-cell rim batch at s 0.2 stays H (disc holds 28 of 37 for 600 s); at
    s 0.7 the disc is lost in 0.5 s.
  - Rim newcomers are insulated by their closing junction gates (the design's
    self-insulation risk). Under oldest-first turnover the disc erodes, so B1 is
    predicted to fail at every retaining coupling; A1 and C1 are unaffected.
  - Closers: seed 3's cells 64 and 73 have no D state at their draws (low NaV with
    high Kir); 10% CV moves the 37-cell boundary by −6%.
  - Evidence: [summary](/mnt/workspaces/Cells/heredity-design-20261108-01/prescreen-08-conversion/summary.md),
    `final.json`.

- **Parity rungs P2 and P4 pass (9 November).** The five protocols were
  registered at `621e2be` and judged once each, from a clean snapshot of that
  commit, on CPU
  ([evidence](/mnt/workspaces/Cells/parity-rung2-4-20261109-03/), `margins.json`).
  Tolerances use the pinned method (3 × the sum of measured terms), with no
  provisional terms. Each protocol lists its non-discriminating quantities, and
  no claim rests on those.
  - **P2 stage (i)**, the verdict: `resolved_pump_tissue@2` (field solver @3)
    against the BETSE-order emulator with Cells' harmonic faces, at BETSE dt/100.
    The reference is first order: observed order 1.00–1.01 over dt/10–dt/300.
    PASS. The barrier claim rests on:
    - ECM K: worst error 0.17 of tolerance, with the barrier effect 252× the error;
    - cell Na, K, M and Cl: effect 3–13× the error.
    Cell K passed with almost no margin: 0.984 (INIT) and 0.996 (SIM) of a
    2e-8 tolerance. The error is about 3.8× the raw term sum, at a
    tight-junction boundary cell.
  - **Attribution after the verdict** ([evidence](/mnt/workspaces/Cells/parity-rung2-4-20261109-04/attribution.json)):
    - The rung-1 convention set the exterior-field Boltzmann term to 0 for
      non-Ca cell ions. Measured by propagation through the reference
      emulator, it is 6.2e-8 for cell K, and 6.3e-7 for Na, 2.7e-7 for Cl and
      9.4e-9 for M.
    - With that term included, the cell-ion tolerances would be 10–100× wider,
      and cell K, Na, Cl and M would not discriminate the barrier.
    - **So P2's barrier claim rests on ECM K alone**, whose field term was
      already in the sum (effect 43× the tolerance, 252× the error). The verdict
      stands, but the cell-ion discrimination reported above is withdrawn.
    - The observed cell-K difference has the opposite sign to both measured
      field terms, so its mechanism is unidentified (open). A next step would
      drive the emulator's membranes with Cells' actual exterior concentrations.
    - **Method for later rungs:** no term is cut off by an absolute threshold.
      Every cell-ion field term is measured by propagation, at the cost of one
      emulator run. A term may stay unmeasured only under a recorded bound of at
      most 10% of the measured sum for the same quantity, phase and ion.
      Heuristic scalings follow the same rule: the X_ext concentration
      heuristic overstated the direct value 1600×.
  - **P2 stage (ii)**, the emulator against plain BETSE (tooling): PASS, worst 0.33.
  - **P2 direct**, Cells against BETSE: reported only; PASS, worst 0.30.
  - **P4 KLeak** (`resolved_pump_tissue@3` with channel populations, BETSE's
    general network): PASS, worst 0.29. The channel's effect is 46× the error on
    INIT Vm and 1.2e4× on SIM Vm.
  - **P4 Kv1p5+KLeak:** PASS, worst 0.31. Kv1p5's effect is 1.7e3× the error on
    SIM Vm.
- **MG0b bistable domain wall passes (9 November).** `resolved_pump_tissue@3`,
  unmodified (IMEX ARS(2,2,2), field solver @2, dt 1 ms, CPU, float64), ran on chains
  of resolved cells with Kir2.1, NaV1.2, leaks and gap junctions. The protocol
  `mg0b-domain-wall-v1` was registered beforehand (`f7e8b6b`), with its
  predictions set from theory and an independent reduced model before any
  engine run of the wall. The run used a clean snapshot of that commit
  ([results](/mnt/workspaces/Cells/morphogenesis-mg0-20261109-01/judged-02-mg0b/results/results.json),
  52 min). All 19 criteria pass, and re-judging the saved results gives the same verdict:
  - wall width against √G: fitted slope 0.521 (window 0.45–0.55; reduced 0.520);
    engine against reduced wall width 0.5–1.0% (allowed 5%); time step 1 and
    0.5 ms against 0.25 ms, profile to 1.2e-7;
  - pinning: below the predicted critical coupling the wall moves 0.06 cells
    (allowed 0.5); at 2× it moves +5.8 cells into H (reduced +5.7);
  - hysteresis: uncoupled loop 0.40 (reduced 0.425); a uniform chain matches
    one cell exactly; anchored loops narrow 0.30 → 0.125 → about 0 with
    coupling (reduced 0.35, 0.15, 0.0);
  - cut and restore: the written domain returns (Jaccard 1.0), the controls
    hold, no domain appears without a write;
  - energy balance 2.2e-5 relative (bound 2e-3); worst global charge 0.09 of
    its bound;
  - 36 registered theory and reduced-model values reproduced, largest
    relative difference 0.5%.
  Known weaknesses were recorded before the run (`lead_review`). B4 judges
  |shift|, but the observed shift has the predicted sign. B5 accepts equal widths,
  but the observed widths narrow strictly. At this coupling B6's return is close
  to guaranteed, so it tests the cut machinery, not memory. Limits: 1-D chain,
  junction gating held open, fixed volume, runs of 6–58 s.
- **Ledger rounding fix landed (9 November; `5ba4426`..`9f59fb0`).**
  - **What changed:**
    - The electrode increment is booked from the start and end charge states.
    - The running work and material ledgers' allowance is 2.5 eps × steps × magnitude (projective bursts and jumps included).
    - Component net charge is checked in the capacitor ledgers instead of in field convergence. The gauge component's rows take the world's summed increments.
    - Opt-in field solver `capacitive_reduction_gauged_damped_newton@3` accepts Newton at its rounding floor and is bitwise equal to @2 wherever @2 converges.
  - **Same trajectories:** trajectories are bitwise unchanged on 7 definitions, and the electrode charge moves by at most 7.5e-26 C.
  - **Now completes:** the 64k-step fine reference, the MG0b wall, the 30-minute relaxing @3 worlds, the 1-hour closed fixture (worst row 2e-4 of its bound) and the P2/P4 parity cases.
  - **Detection floors:** 1e-13 fmol on a floating component. On the gauge component, 3.1e-15 fmol after 5 steps and 2.3e-11 fmol after 1e5 steps.
  - **Gate:** tier 1+2 passed with 323 files unchanged, from a clean snapshot whose tree equals `9f59fb0`.
  - **New tests:** `test_ledger_rounding.py` and `test_field_floor.py` are in tier 3 (each runs about 6 min; both pass).
  - Evidence: `/mnt/workspaces/Cells/ledger-fix-20261109-01/`.
- **Heredity pre-screen 7: written discs at E07-v1's couplings (9 November;
  development, not judged).** This ran `resolved_pump_tissue@3` through
  `stationary_continuation_analysis@1` on hexagonal heredity sheets with held baths
  (F0 surrogate) and E07-v1's junctions. Driver: `validation/stationary/heredity_prescreen.py`
  (`83b92b1`).
  - With voltage-gated junctions, the 7-, 19- and 37-cell discs are stable at x0.3
    and have no stationary state at x1, x3 or x10. 61- and 91-cell discs hold at
    x1 (critical theta 1.909 and 2.257 against 1.657). With open junctions, no
    disc holds at any arm.
  - Uniform H is stable at every arm.
  - At x1 the written 19-cell disc is lost in 0.5–1 s, and the 37-cell disc in
    30–60 s.
  - Heterogeneity at 15% CV lowers the 37-cell critical coupling by 9–16%.
  - So 12 of E07-v1's 14 stage-A write arms, and most stage-B arms, would fail
    retention by construction. The choice is with the user (D133).
  - Evidence: [summary](/mnt/workspaces/Cells/heredity-design-20261108-01/prescreen-07-stationary/summary.md),
    `final.json`. Pre-screen 8 (newcomer conversion) is above.
- **Stationary-state analysis (E) qualified (9 November).**
  `stationary_continuation_analysis@1` (`890567b`, opt-in, D135) passed all 16
  criteria of the pre-registered protocol `stationary-analysis-e-v1`
  (`2b4dd5e`). The run used a clean snapshot of that commit, on CPU; the
  verdict came from `validation/stationary/judge.py`
  ([judgement](/mnt/workspaces/Cells/fixed-points-e-20261109-01/judged-01/judgement.json)).
  It ran `resolved_pump_tissue@1` and `@3` unmodified.

  | Target | Result | Agreement |
  | --- | --- | --- |
  | Default-world cell (`@1`) | −6.07376 mV, K 239.21 mM, 493 mOsm; stable, τ 0.259 s, 189 s and 16,661 s | 3.5e-14 V against the reduced model (budget 8.8e-12); eigenvalues 1.1e-11 /s |
  | Heredity cell (`@3`) | H −79.556 mV and D −21.518 mV stable; U −39.445 mV with one unstable mode | at most 6.6e-15 V |
  | MG0b cell, fast mode | folds at u = 0.3770832491 and 0.6794743372 | 1.2e-15 from the reduced folds |
  | 61-cell sheet, written 7-cell disc, fast mode | stable up to a fold at θ = 0.10467 g_H | 8.8e-9 from an independent graph model (budget 2.8e-7) |

  Reported, not judged (no reference exists): in slow mode the disc loses
  stability through a Hopf point at θ = 0.0701 g_H (period about 112 s).
  Diagnostic D1: a 2e5 s step-map run ends where the slowest mode predicts.
  Its qualified-runner probe was refused by the ledger-rounding issue, and it
  is repeated once the fix lands.

- **Projective mode (C) landed (9 November), not yet qualified.**
  `projective_forward_euler@1` (`ab27087`, opt-in, D135) runs bursts of the
  unchanged fine engine with checked extrapolated jumps. Its qualification
  protocol is committed (`3b906ca`) and waits on the ledger-rounding fix.
  Development runs over 30 s: error at most 0.42 of the allowance, 2.5× fewer
  fine steps during relaxation.

- **Stage B landed (9 November).**
  - Neutral names throughout `src/cells`: 7 modules and more than 65 law IDs
    renamed, the junction law merged and 4 mixed modules split.
  - The physiology stack moved to `validation/betse/physiology`.
  - Hash-pinned source manifests retired.
  - No BETSE-specific ID or import remains in `src`; the boundary test
    enforces it. The remaining text mentions are source citations, which are
    allowed, plus some leftover message wording, which is a follow-up.

  Tiers 1 and 2 ran from a clean snapshot of the rebased branch (`0736231`,
  [gate](/mnt/workspaces/Cells/stage-b-20261109-01/landing-01/gate-01/)).
  Three files differ from the record:
  - two polygon-preparation files now pass in full, 77 and 78 tests, because
    the hash pins they failed on were retired;
  - `test_default_world_adapter` grew to 19 tests in the rung-1 work and now
    takes about 220 s, so it belongs in tier 3.

- **Channel model and batched worlds landed (9 November).**
  - `resolved_pump_tissue@3` (`6853aa6`) adds Kv1.5, Kir2.1, NaV1.2 and K/Na
    leak populations to the IMEX pump family, with exponential gate updates.
    - The heredity cell reproduces the pre-screen states, H −79.556 mV and
      D −21.518 mV.
    - On 825 nodes on the L4, Vm agrees with the 0.25 ms run to 7.5 nV at 1 ms
      but not at 2 ms (145 µV); CPU and L4 agree.
    - [Evidence](/mnt/workspaces/Cells/pump-channels-20261109-01/).
  - Batched worlds (`5d61544`): `run_vector_windowed` vmaps worlds, with
    domain, ledger and dissipation checks on the device.
    - Bitwise equal to single worlds on CPU with compiler rewrites off;
      5.7e-16 V on the L4.
    - L4 throughput per world-step, 825 nodes at 1 ms: 26.7 ms one world at a
      time; 2.38 ms at 64 worlds; 2.10 ms at 256; 3.79 ms end to end with
      observations. SM active 80–94%.
    - The heredity plan assumed 0.47 ms on GH200; at the L4 rate, tier 1 would
      need about 6,800 GPU-hours. A GH200 measurement is now the deciding
      input. [Evidence](/mnt/workspaces/Cells/batched-worlds-20261109-01/).
  - Gate: [tiers 1 and 2](/mnt/workspaces/Cells/land-g1-g4-20261109-01/gate-02/).
    Three files differ, none because of these changes: two read-only fixture
    copies (fixed in `7ec5589`) and the adapter file above. The 68 new tests
    pass (one skipped).
  - **Found afterwards:** long runs and worlds with many held baths were
    refused by rounding in the conservation checks, not by physics errors.
    The fix is in progress: electrode charge is now booked consistently, and
    allowances derived from rounding grow with the step count. It blocks MG0b
    and hour-scale qualification.

- **MG0a morphogen gradient passes (9 November).** `reaction_transport@1`,
  unmodified, ran under the protocol `mg0a-gradient-v1`, committed beforehand
  (`e8ded03`). The run used a clean snapshot of that commit, on CPU in float64
  ([results](/mnt/workspaces/Cells/morphogenesis-mg0-20261109-01/judged-01/results/results.json)).
  The source is a large-volume reservoir cell (the model has no source term).
  The references are independent numpy/scipy solutions. All 12 criteria pass:
  - profile against the exact discrete steady state: at most 4.6e-13
    relative on strips and 3.0e-14 on the Voronoi tissue, against 1e-9;
  - decay length against √(D/k) = 19.92 µm (Kicheva 2007 wing-disc values):
    +0.072%, as predicted by the discretisation error;
  - scaling slope 0.499 (registered window 0.495–0.505); refinement order
    1.99–2.00; RK4 time-step order 4.02–4.04, resolved above the reference
    floor;
  - mass and per-cell ledgers at most 1.1e-13 relative;
  - cut and restore returns the uncut profile within 1.8e-15; the
    cut-without-restore distal fragment decays to 8e-22.

  Two design changes made after development runs are recorded in the
  protocol; no physics threshold moved. The steady state is unique, so the cut
  tests the machinery, not memory. Engine gaps found by the driver: no source
  term, no excision contract, and a closed-world balance guard that does not
  grow with step count. The guard gap limited refinement to three levels.

- **Parity rung 1 v2 passes (9 November).** Attribution of the v1 failure
  ([summary](/mnt/workspaces/Cells/parity-rung1-20261108-01/attribution-01/summary.json)):
  - **Not the Ca pump.** With matched constants, Cells' Ca-pump law
    reproduces BETSE's `pumpCaATP` exactly.
  - **The cause.** The extracellular offset is equilibrium electromigration in
    Cells' own resolved exterior field (0.8 µV interior spread). It follows the
    Boltzmann response for every mobile ion, with r = 0.81–0.94 and signs set
    by valence.
  - **The v1 flaw.** The v1 field-law proxy was one-sided: it removed only
    BETSE's drift.

  The v2 protocols (`cecfb13`) add the field term |z|F·max|φ−⟨φ⟩|/RT, from
  blind Cells-only potentials, and were committed before the fresh judged runs
  ([results](/mnt/workspaces/Cells/parity-rung1-20261108-01/judged-02/)). All
  three runs pass from a clean snapshot of `cecfb13`:
  - D on CPU and on L4 (identical): Vm 132 µV against 400 µV in INIT, 1.82 µV
    against 7 µV in SIM;
  - F on L4: Vm 1.82 µV against 20 µV; cell Ca 1.2e-3 against 5e-3;
    extracellular Ca 4.42e-5 against 2e-4.

  F's first attempt was cut off by a session crash; it is preserved as
  `F-l4-interrupted-01` and was rerun from the same snapshot and protocol.
  Because the method was revised after a failure, this pass is weaker evidence
  than a first-time pass. The same field term leaves every rounded rung-0
  threshold unchanged.

- **Parity rung 1 (mammal ion profile): pre-registered FAIL (9 November).**
  `resolved_pump_tissue@2` was judged against plain BETSE's mammal-profile
  default world (Na, K, Cl, Ca, P, M plus the plasma-membrane Ca pump) under
  protocols committed beforehand (`82452a0`). The runs were from a clean
  snapshot of that commit.
  [Results](/mnt/workspaces/Cells/parity-rung1-20261108-01/judged-01/).
  - D (CPU and L4, identical) and F (L4) all **fail on one item**: SIM
    extracellular Ca, worst relative error 4.42e-5 against a tolerance of 2e-5.
  - Everything else passes:
    - Vm: F INIT 1.82 µV against 20 µV.
    - Cell concentrations, including Ca: F INIT 1.2e-3 against 5e-3.
    - INIT extracellular concentrations, including Ca at 4.42e-5 against 5e-5.
  - The Ca offset is steady: identical in INIT and SIM, and in D and F, so it
    is not BETSE's step error. The budget predicted 1.45e-5 (INIT) and 5.3e-6
    (SIM); the likely missing term is the new mechanism itself, the Cells Ca
    pump law against BETSE's `pumpCaATP`.
  - Next: attribute it with emulator variants, then pre-register a v2
    derivation and run it fresh. The v1 failure stays on record; nothing is
    retuned.

- **Fast test tiers (9 November).** Each test file was timed separately
  (`scripts/test_tiers.py`) under a standard environment: `JAX_ENABLE_X64=1`
  and per-file output and evidence roots, run in a clean worktree. Tiers are in
  `tests/test_tiers.json`.
  - Tier 1: 260 files, about 6 min on 4 cores, 6,251 passing tests.
  - Tier 2: 62 files, about 11 min, 2,659 passing tests.
  - Tier 3: 173 files exceed the 90 s cap and are run deliberately.
  - 73 tier-1 and 8 tier-2 files fail at baseline: stale hash pins, missing old
    evidence files, and one test still importing a deleted frozen module. The
    gate flags only changes from these recorded outcomes; cleaning them up
    belongs to stage B.
  - [Measurements](/mnt/workspaces/Cells/test-tiers-20261109-02/measure/measured.json),
    plus the first full pass under `test-tiers-20261108-01`.

- **Heredity design and re-hosting probe G0 (8–9 November).**
  - **E07-v1 design:** "write, release, replace", in [the design doc](docs/HEREDITY_FIRST_EXPERIMENT.md).
    Single-cell pre-screens find NaV1.2 window current plus Kir2.1 bistability
    (H −79.6 mV, D −21.5 mV). Tier-1 JUPITER cost is about 12,500 GPU-hours
    with today's sequential kernels and about 840 with 64-world batches, so
    batched worlds are on the critical path.
  - **G0 probe** ([summary](/mnt/workspaces/Cells/rehost-g0-20261108-01/summary.json)):
    two_task and unstimulated_readout on `resolved_tissue@2` (RK4).
    - Stable only at dt ≤ 62.5 ns.
    - The source-cell cue response is 6.62 µV, about 3,000× the 2 nV readout
      margin, and dt refinement changes it by under 1e-8 nV.
    - The old BETSE-order archive gives 6.632 µV (same direction, not parity).
    - Neighbour cells move only 0.5–1.1 nV, below the margin, so the old
      decodability results rest on few cells.
    - IMEX with channels is still needed for µs steps.

- **First BETSE parity of Cells' own physics: default world passes (8 November).**
  Model `resolved_pump_tissue@1` (IMEX ARS(2,2,2)) on BETSE's default world (222
  cells, 25×25 extracellular grid), judged against plain BETSE under protocols
  committed before the runs (`3c09891`). The runs were from `ba8694f` with a clean
  tree, and each named its protocol and geometry hashes.
  [Summary](/mnt/workspaces/Cells/default-world-parity-20261108-01/judged-01/summary.json).

  | Protocol | INIT Vm (tol.) | INIT cells | Interior ECM | SIM Vm | Verdict |
  | --- | --- | --- | --- | --- | --- |
  | D vs BETSE 10 ms, CPU = L4 | 131 µV (400) | 2.8e-6 (9e-6) | 3.9e-4 (2e-3) | 2.27 µV (7) | pass |
  | F vs BETSE 0.1 ms, L4 | 2.27 µV (20) | 1.0e-7 (4e-7) | 3.9e-4 (2e-3) | 2.27 µV (7) | pass |

  - Each difference matches its predicted budget term. D's INIT maximum is
    BETSE's own 10 ms step error (127–130 µV, at 0.33 s). With that removed (F),
    Cells and BETSE agree to 2.27 µV over a 22.8 mV INIT change, against a
    3.4 µV predicted budget (constants, field law, exterior potentials, BETSE's
    residual step). The 3.9e-4 ECM difference is the conservative-stencil term,
    a deliberate Cells model difference.
  - Health: 1 Newton iteration per field solve; global charge ≤3% of its bound.
    D took 4 min on the L4 and 7 min 22 s on CPU; F took 19 min 44 s on the L4.
  - **Limits of this claim.**
    - One seeded geometry and BETSE's default mechanisms only: four ions, leak,
      Na/K pump, gap-junction gating, extracellular electrodiffusion. No
      channels, networks or interventions.
    - SIM is nearly flat in BETSE (Vm moves 3 µV), so INIT carries the test.
    - venv is not compared, because the field models differ by design.
    - The next mechanism families follow the parity ladder in the coverage map.

- **Difference budget and first blind resolved run (8 November).**
  [Index](/mnt/workspaces/Cells/default-world-parity-20261108-01/index.json).
  - **Emulator-only budget** (dense default world; `difference_budget.json`):
    - BETSE's own 10 ms INIT step versus dt/100 differs by up to 130 µV in Vmem
      (at 0.34 s; 4.9 nV by the end of INIT; first order), 2.8e-6 in cell
      concentrations and 3.6e-5 in ECM concentrations.
    - BETSE's rounded constants versus CODATA give a steady 1.22 µV.
    - The ECM maximum sits on the boundary ring, which BETSE resets every step
      and the resolved model holds as reservoirs. Ring sites are excluded from
      judged ECM concentrations.
  - **Blind resolved run** (`resolved_pump_tissue@1`, ARS(2,2,2) at 1 ms, real
    geometry; BETSE histories not read):
    - It stopped near 2 s on the global-charge check. That bound is a fixed 3e-25 C,
      while reservoir supply accumulates about 1e-9 C, so float64 rounding
      (about 3e-16 relative) crosses it. A scaled bound is in progress.
    - Up to then everything held: 1 Newton iteration per window, material ledger
      within 3.6e-15 fmol, CPU vs L4 within 3e-15 V. About 90 ms per step on CPU
      and 60 ms on the L4.

- **Stage A: copied BETSE code removed from the engine (8 November).** 716 files
  deleted, 63 adapted, 1 added. Deleted: 243 `src` modules (the 207
  `betse_native_*`/`betse_normal_*`, 34 BETSE glue modules, and 2 BETSE-only
  processes); 233 validation files; 240 tests. Three engine seams were cut with
  no behavioural change: the mitochondria source label is now a literal of the
  same value, and the BETSE-mesh bridge in `conservative_polygon_geometry` and
  the BETSE grid-audit entry in `rectangular_environment` are removed.
  [Evidence](/mnt/workspaces/Cells/engine-cleanup-stage-a-20261108-01/verify/summary.json).
  - Polygon tests now use `tests/fixtures/conservative_polygon_generated.json`,
    exported once from the old generator; replayed geometry is identical.
  - Guards pinning edited files were re-pinned to a fixpoint (18 src, 35
    validation records); entries for deleted files were dropped, and all other
    entries are unchanged.
  - **Verification** against the unmodified tree:
    - test collection is identical apart from the adaptations, with the same 13
      pre-existing `runs/` errors;
    - imports of 1,675 modules are identical;
    - targeted tests (39 files) show 0 new failures, and 90 now pass that failed
      on a stale pin;
    - 115 fail on both sides with identical messages.
  - **Full suite not run:** the whole suite is too slow here (about 3% after 2.7
    hours; [stopped attempt](/mnt/workspaces/Cells/engine-cleanup-baseline-20261108-01/attempt-02-infeasible/NOTE.json)).
    A fast tiered gate is needed.
  - Remaining for stage B: BETSE-named engine modules and IDs, plus BETSE-side
    `*_native.py` tools and records in `validation/betse` that refer to deleted
    components.

- **`resolved_pump_tissue@1` at BETSE default-world scale (8 November).** New
  identity: resolved field + Na/K pump + physical-time junction gate
  (`junction_voltage_relaxation@1`), 200–400 K, no channels. The new field-solver
  version (Cholesky-factored, ≤2048 nodes) leaves the field law unchanged.
  [Index](/mnt/workspaces/Cells/resolved-tissue-scale-20261108-01/index.json),
  on a synthetic 825-node world with BETSE default coefficients.
  - **Stiffness:** with BETSE's real face conductances, explicit RK4 is only stable
    below about 69 ns (extracellular charge relaxation through faces against the
    patch capacitors). New IMEX solvers treat face electromigration implicitly:
    `imex_ars222_face_electromigration@1` (order 2.0 measured) and
    `imex_euler_face_electromigration@1`.
  - **Accuracy:** ARS(2,2,2) Vm error 13 nV at 1 ms over a 0.256 s INIT window and
    47 pV in SIM at 0.1 ms; material ledger ≤2.3e-16 fmol; capacitor-charge
    residual about 1e-28 C. Equivalence checks: factored vs dense field ≤1e-12;
    channel-free `resolved_tissue@2` 1.4e-14; CPU vs L4 within family bounds.
  - **Cost and limits:** INIT 5 s takes about 6.5 min on CPU and 2.5 min on the L4;
    face diffusion limits explicit stability to about 7 ms, and the identity
    enforces dt ≤ 3.4 ms. `tests/unit/test_surface_pump.py` passes 43, with 1
    L4-only skip on CPU.
  - **Energy bounds (condition met):** the IMEX energy-identity checks use
    relative bounds (2e-3 ARS, 2e-2 Euler) instead of the family's absolute 2e-8
    pJ, since neither scheme integrates the energy identity exactly. The residual
    converges at each scheme's order with no plateau (Euler 1.00, ARS 2.00; at
    825 nodes the largest ARS residual is 9.5e-7). A fast test asserts the order,
    and the RK4 path keeps the absolute bound
    ([study-03](/mnt/workspaces/Cells/resolved-tissue-scale-20261108-01/index.json)).
  - **Global-charge bound:** now 3e-25 C + 256·eps·(charge moved) rather than a
    fixed 3e-25 C, which float64 rounding crossed once reservoirs had supplied
    about 1e-9 C. The full 5 s INIT on real BETSE geometry completes (L4, 249 s)
    with a worst residual-to-bound ratio of 0.0125; an injected error of 10× the
    bound still fails (study-04).
  - Added to the ionic ensemble list; two windowed ensemble worlds reproduce the
    plain run's final state bitwise.

- **BETSE-order emulator out of the engine; comparison pipeline proven (8 November).**
  The seven BETSE-order modules (spatial, active, junction, specs, models) and
  their four configs moved to `validation/betse/emulator/`. The engine registry,
  spec and schedule entries are removed. [Index](/mnt/workspaces/Cells/default-world-parity-20261108-01/index.json).
  - The emulator matches plain BETSE to roundoff with BETSE's constants:
    Vmem ≤ 3.2e-13 V against a 22.1 mV INIT change (dense case), with
    concentrations ≤ 1.1e-14 relative, on both CPU and L4 (CPU vs L4 ≤ 2.5e-13
    V). This validates the extract → adapter → run → layout → comparator chain.
  - Standard (CODATA) constants alone change Vmem by 1.22 µV in INIT and 0.19 µV
    in SIM.
  - Assays and tests that ran this model through the engine runner are skipped
    with one reason (D131; last runnable at `432e62b`), not deleted. The
    re-hosting work list is `validation/betse/emulator/rehost_pending.json`.
    Every module-skipped test already had errors at HEAD (stale source-hash
    checks, native re-capture subprocesses).
  - The resolved-tissue adapter backend is written but not yet run. SIM must
    continue from the Cells INIT end state: BETSE's INIT end leaves up to
    5.9e-13 C on isolated extracellular squares, which the resolved closure
    does not admit.

- **L4 platform checks and JUPITER preparation (8 November).**
  [Index](/mnt/workspaces/Cells/jupiter-platform-20261108-01/index.json) of runs,
  inputs, results and failures.
  - GPU unit tests 33/33; integrated ensemble on GPU vs CPU 7/7; GPU
    integration (real pause/resume) 7/8.
  - **Known failure:** `test_signal_pause_and_exact_integrated_resume[ionic]` fails
    at ≤2.4e-15 relative when processes share the persistent JAX compilation
    cache, and passes with `JAX_ENABLE_COMPILATION_CACHE=false`; in-process
    pause/resume is bit-exact. Cross-process bitwise replay therefore needs the
    cache disabled.
  - Ensemble smoke (`spatial_extracellular@2`, 32 worlds): pause within 2.8 s of
    SIGUSR1, resume 32/32 bitwise equal to uninterrupted runs, 98 s, 0.02
    GPU-hours. GPU busy 84–89% but SM-active 0.5–0.6%: single-world `lax.map`
    kernels are latency-bound, so JUPITER needs vectorised worlds.
  - JUPITER recipe: `validation/ensemble/jupiter_env_setup.sh` (wheels only, all
    28 pins have aarch64 Python 3.13 wheels), `jupiter_check.py`, the reworked
    `jupiter.sbatch` and the [runbook](docs/JUPITER_RUNBOOK.md). Site details are
    unverified until access.
  - Runner gaps for later: workers are killed 55 s after a pause request;
    multi-node runs are separate campaigns that need distinct seeds; per-leg
    `allocated_gpu_hours` must not be summed within one job.

- **Plain BETSE reference outputs (8 November).** Unmodified BETSE v1.5.0 CLI,
  isolated HOME, CPUs 1–2; tools `validation/betse/betse_reference_run.py` and
  `betse_reference_extract.py`. [Index](/mnt/workspaces/Cells/betse-reference-20261108-01/index.json)
  of four cases, each with its run result, extract manifest and checks:
  - default world (headless_core): 226 cells, 1,298 membranes, 24×25 ECM grid;
    seed 11.1 s, INIT 11.8 s, SIM 9.6 s, peak 239 MiB;
  - dense default world (sampling = dt; 499 INIT / 349 SIM samples): its own
    unseeded geometry (222 cells, 25×25 grid);
  - dense run on the standard seed: histories bit-identical at all common
    samples, so dense sampling does not change dynamics;
  - seven-cell REF-003c configuration (YAML hash reproduced; new geometry).

  Comparison notes: sample k is the state after k+1 updates, and the end state
  is only in `*_final.npz`; BETSE uses F = 96485 and R = 8.314; geometry differs
  per run (unseeded RNG), so each comparison uses its case's own
  `geometry.npz`; INIT `P_cells_time` is an aliased series. Default-world SIM
  Vmem moves only about 3 µV, so the dense INIT is the informative comparison.
