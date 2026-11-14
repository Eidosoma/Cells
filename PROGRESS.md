# Progress

Last updated: 2026-11-12 UTC.

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

The order (gates and their evidence) is now
[docs/CURRENT_PLAN.md](docs/CURRENT_PLAN.md), adopted 12 November (D145).
This table stays as the status record of the 8 November plan.

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
| 5 | Further mechanism families from the parity ladder, on CPU and L4 | **P2 (ECM barriers), P3 (scheduled interventions, first subset) and P4 (general-network channels) passed** on CPU; **P4b (NaV1.2, Kir2.1, Na leak) passed** (four cases, NaV1.2 including the D-state voltage); **all 12 also pass on the L4** (registered L4 variants, tolerances unchanged; worst 0.996 of tolerance, P2 stage 1 cell K, as on CPU) |
| 6 | JUPITER environment and one-node pilot | Recipe and runbook ready; untested on site |
| 7 | Stage B: neutral names; physiology stack moved to `validation/betse` | **Done** (tag `stage-b-neutral-names-2026-11-09`) |
| 8 | Re-host the short decodability assays on Cells physics | G0 probe viable; channels next |
| 9 | First heredity experiment, E07-v1 ([design](docs/HEREDITY_FIRST_EXPERIMENT.md)) | Channel model (G1), batched worlds (G4), the ledger rounding fix and @3 device checks landed; @3 on the L4 is 2.28 ms per world-step at 256 worlds (tier 1 about 4,100 L4 GPU-hours execute-only, about 7,200 end to end); GH200 throughput unmeasured. **Pre-screens 7–8 (retention, rim renewal) are in doubt**: they start from the fully loaded stationary D composition (+31% osmolarity), while cue-written discs carry H composition and behave differently (W1 sheet check, pre-screen 9); the design choice waits on fresh-disc runs |
| 10 | Morphogenesis track ([plan](docs/MORPHOGENESIS_PLAN.md); D134) | **MG0a and MG0b passed** (MG0 complete); **MG1 (2-D vertex mechanics) passed v2** (57/57; weaker evidence after the failed v1, 52/57) and is landed on main |
| 11 | Optional long-horizon modes (D135): E fixed points and continuation, C projective integration | **E qualified**; **C qualification qual-01 failed** (absolute caps; accuracy against its own estimator passed); F2 not evaluable (no lingering scale found) |

## Runs

Per-run summaries for this plan are added here, newest first, each linking its
machine-readable inputs, results, checks and failures.

- **The secreted-species protocol's rehearsal on main, and its final pre-registration amendments
  (14 November).** The protocol is still PROPOSED, with no judged run
  ([evidence](/mnt/workspaces/Cells/secreted-species-v1-20261114-01/HANDOFF.md): `rehearsal-6f339ab/`,
  `dryrun-0353b29/`).
  - **The rehearsal, from a clean snapshot of main at 6f339ab.**
    - All five crossrev sets and the species set are identical.
    - The development pipeline reproduced every frozen number bitwise: 1,212 protocol leaves,
      2,256 analysis leaves and 2,480 arm-record leaves.
    - A dry run of the Q1–Q3 judge on a registered copy passed every item and caught every
      control.
  - **Amendments before registration.**
    - A Q5 entry (`judge-q5`) and a `combine` entry now write one qualification verdict holding
      every item, the scope, the snapshot's revision and the unjudged step-map ratios.
    - The attempt rule counts a harness timeout, a runtime-limit kill or a Q5 file ended by a
      signal as an infrastructure ending, rerun once.
    - `rules.timing` sets runtime limits of about 3× the rehearsal's times. The judged units run
      without `--wait-headroom`: the lead launches each only when the slice has about 3 GB free.
    - Every judge entry was dry-run to a pass on a registered copy (judge 310 s, judge-q5 772 s,
      combine 0 s).
  - **Landing:** tier 1 at the merge 0698713: 314 files, no changed outcome. The tier-2 step-map
    guard passed 2 of 2.
  - **Next:** the advisor's check 1, which reruns judge, judge-q5 and combine on a registered
    dry-run copy from a clean snapshot of this main and compares them leaf by leaf with
    `dryrun-0353b29`. Then registration, through the generator, as a status-only change.

- **Reactions on the shared inventory (D152 v1): `local_species_reactions@1`, milestones 1 and 2,
  landed (14 November).** This is development code, with no judged run; MG0c's qualification is
  milestone 3 ([note](docs/SHARED_INVENTORY_REACTIONS_DESIGN.md) §11;
  [evidence](/mnt/workspaces/Cells/shared-inventory-reactions-v1-20261114-01/HANDOFF.md)).
  - **What landed.**
    - The operator and its declaration parser, with every refusal the note lists.
    - The contract parts, including the standard-potential term the operator owns.
    - The laws: mass action of orders 0–3, Michaelis–Menten with or without a catalyst, passive
      detailed balance, and Hill factors.
    - SSPRK(3,3) half-steps under the stage condition at θ = 1/2. dt·L > 1 is refused.
    - Exact ΔG bookings, the per-step node class, and the mixed-node hybrid.
  - **Against the independent references** (run through their usage note only):
    - the per-law ΔG test of record agrees within the references' tolerances over 4 world
      variants × 60 trials, with every law, class and branch reached;
    - whole compiled face-free runs agree to ≤ 7e-15 in amounts and ≤ 2.5e-16 of scale in
      energies;
    - the development figures are reproduced: the share at onset +0.33% in the first half-step,
      the background guard −6.32e-5 against the true −6.27e-5, and the reversal onset 5.4–5.6×
      at a 1e-12 mM trace.
  - **Guards.**
    - The face-free energy world stays within 0.26 of the rounding allowance on every booking
      path, and its three negative controls fail at the first row they touch.
    - C2: the shared bound is 0.35× the booking at µM and 409× at nM.
    - Benign padding: no NaN or infinity anywhere.
    - Identical programs across parameter twins. The batch signature refuses different
      structures.
    - Idleness is bitwise against the live half-step. Restart is bitwise, including through a
      snapshot.
    - Vector batches are bitwise against their reverse.
    - dt·L = 0.98 is admitted and 1.02 refused, with the state kept bitwise.
  - **Crossrev of record:** all five sets and D150's species set are identical. The reactions set
    has its first record.
  - **Landing checks.**
    - Tier 1 and 2 at the merge a4e2f7e: 397 files, no changed outcome.
    - D152's three tier-3 files pass: runs 6, guards 14, reference runs 18.
  - **For milestone 3:**
    - §3.4 guard 2, the transport world with the network;
    - a compiled composition with another writer;
    - idle claim 3, reported;
    - multi-site runs;
    - MG0c's driver and a PROPOSED protocol.

- **The checkpoint-continuity GPU probe (design §13.4): every question identical (14 November).** It
  ran in the L4 gap after hold segment 2 ended, as one GPU process under the GPU lock (about
  2 min, peak 1.5 GB), then the CPU part on CPU 3, from the frozen source `source-s1-e8cdda0`
  ([evidence](/mnt/workspaces/Cells/checkpoint-continuity-20261113-01/impl/gpu-probe/out/):
  `compare.json`, `queue.log`).
  1. A GPU cohort traces identically in two GPU-host processes: P0, P, B and H.
  2. A CPU-host trace, with `execution_device` patched, equals the GPU host's jaxprs, constants,
     bindings and host replay.
  3. The cross-lowered `cuda` StableHLO equals the GPU host's own lowering (1,799,725
     characters, identical).
  4. The overlap repeats bitwise on the CPU for a GPU definition.
  - **The decision §13.4 registered:** GPU definitions are probed on the CPU host and use no
    GPU time; the record notes the patch. This unblocks the GPU extension of case 1, which is
    to be built next.

- **E07-v1 follow-ups (14 November).** Both are descriptive or development work, and no verdict or
  class changed ([readout](/mnt/workspaces/Cells/e07-v1-judged-20261113-01/loss-positions.json),
  [1 ms check](/mnt/workspaces/Cells/e07-v1-dtcheck-20261114-01/HANDOFF.md)).
  - **Where losses sat,** over all 16 inheritance runs with any loss:
    - Of the 41 lost D copies, 33 were strays outside the disc, 8 sat on the rim, and none was
      interior.
    - Of the 21 lost founders, 20 were rim cells and 1 interior.
    - The erosion and small-bias classes therefore mix trimming of strays, which raises J, with
      rim erosion, which lowers it. Fast k3 s 1.0 seed 1 (ΔJ +0.044) is pure trimming.
  - **The s 1.0 control's collective falls at 1 ms.**
    - The same cells fell at the same records as at 5 ms: 6 at 436 s, 6 at 512 s and 2 at 514 s
      at 2 s resolution.
    - The D sets were identical at all 61 records, with |ΔVm| ≤ 0.21 µV.
    - A 5 ms rerun reproduced the judged run bitwise.
    - The falls are not a step-size artefact. It is still one run.
  - **The E07-v2 note** (still PROPOSED) carries the review fixes:
    - §2 leads with the pattern's fate;
    - fresh against long-held has its matched variables named, with a prediction;
    - 1-D chain screens come before the lesion arms only.
    - Its three questions are with the user.
  - **Landing.** The D147 guard exempts the two new scripts, with reasons: one is THRESHOLD_V
    only, and the other builds through e07_v1_run.build, which declares the solver. Tier 1 at
    23c979f: 310 files, no changed outcome.

- **Secreted-species v1 (D150), milestone 3 landed: the qualification protocol, PROPOSED
  (14 November).** It is not registered, and no judged run has been made
  ([protocol](validation/tissue/secreted_species_protocol.json); design §12.2;
  [evidence](/mnt/workspaces/Cells/secreted-species-v1-20261114-01/HANDOFF.md)).
  - **Scope.** The protocol judges @3's faces, with exact radial-shell conductances, and turnover's
    first-order clearance around a held-bath source: the held sphere with decay.
    - Q1: against the exact discrete solution, on the IMEX and RK4 arms. Two rules: the dt study,
      and an a priori bound by the splitting's leading term.
    - Q2: against the continuum closed form.
    - Q3: the observed orders, judged by stop rules only.
    - Q5: the guards of record, which are the RK4 face heat and the per-law ΔG tests, plus the
      runs, ions, definitions and refusal test files.
    - Exchange, production and the occupant rule enter only through Q5's test files.
  - **Judged controls.**
    - k and D put in error at a registered δ per rule and arm. In development every one was
      caught, at 13–79 times tolerance.
    - The planar-face arm against Q2. It fails at 28–248 times.
  - **Development.**
    - All eight arms pass every host check.
    - Q1 on IMEX reaches 0.47 of tolerance under the dt study and 0.37 under the splitting term;
      on RK4, 0.45 and 0.34.
    - Q2 reaches 0.44–0.47. The orders are 1.92–1.93 in space and 2.00–2.09 in time.
    - Pass fractions near 4/9 are structural for a second-order scheme; the controls are what
      show the test can fail.
    - The first-shell error equals the step map's fixed point to 5.8e-4 (reported).
  - **The review (the lead, with the advisor).**
    - Q1's claim is reworded to an a priori bound.
    - The controls are judged, and the scope is stated.
    - R-continuum is checked against the PDE itself: a fourth-order residual, both boundary
      conditions and the start.
    - The step map's agreement stays a tier-2 regression guard, not a judged item.
  - **Found and fixed in development.**
    - A radial-builder regrouping moved bindings by up to 5 ulp. The species crossrev caught it.
    - A refusal test would have failed once the protocol was registered.
  - **Landing:** tier 1 at the merge 780f5d9 310 files, no changed outcome; the new tier-2 step-map guard
    2 passed.
  - **Next:**
    - a rehearsal on main: all five crossrev sets and the species set from a clean snapshot, and
      a dry run of every judge entry;
    - the lead's final check with the advisor;
    - registration, then one judged run.

- **D152's independent references landed (14 November).** An agent that never read the operator's
  code or the design's prototype wrote them from the note's Appendix A and §6
  ([usage](validation/reactions/REFERENCES_USAGE.md);
  [evidence](/mnt/workspaces/Cells/reaction-references-20261114-01/), with the run of record
  `crosschecks-3/` at 5fd695b).
  - **What they are.**
    - The node kinetics and bookings: the SSPRK(3,3) half-step and its stage condition, the exact
      ΔG in floats and in 50-digit Decimal, the per-step node class and the mixed-node hybrid.
    - The exact dissipation integral (DOP853).
    - Closed-form linear reaction–diffusion on zero-flux chains.
    - MG0c's Turing references: the dispersion relation, the discrete mode propagators and the
      semi-discrete nonlinear integration.
  - **Independent reproduction.** Every fully specified development number in the design:
    - probes 2c, 2d, 2e/2f and 2g in every cell;
    - §6.4: d_c 8.5676, the band (0.2, 0.5), σ_max 0.05719, the domain table and the staircase.
  - **The tolerance basis.** Against a second float implementation, end amounts agree within
    4.7 ε. ΔG is within 1.06 ε of the 50-digit value, and mixed-node H within 0.38 ε of its terms'
    scale.
  - **Corrections to the note it found,** to be made through the engine branch's amendments:
    - the trace-sensitivity figures are relative changes of the whole heat, not pJ;
    - k̃² at σ_max is 0.3185;
    - Appendix A's RT uses R = 8.314; the references take RT as an input;
    - Q4's "both gaps" needs L/ℓ = 4 in the sweep.
  - **Checks.**
    - 44 self-tests in 5.8 s, tier 1, including a static check that the references import
      nothing from `cells`.
    - Tier 1 at the merge db8111b: 308 files, no changed outcome.
    - The tier record's merge conflict was resolved with the tier tool, re-measured on main's
      record.

- **E07-v1 judged (13–14 November): under donor-copy turnover the written disc did not renew.
  The pattern followed neutral copying closely, and 8 of 15 scored predictions held.**
  - **How it ran.** All 38 judged runs ran once each, from one clean snapshot of main at 4465b48,
    after the E1 numerics gate passed at 5 ms (|ΔVm| ≤ 5.7 µV). Every unit exited 0, and no E07
    process was killed. Scoring used the frozen scorer
    (`validation/tissue/e07_v1_score.py` at 6b6912b), covering 38 of 38 runs with every
    cross-check true
    ([evidence](/mnt/workspaces/Cells/e07-v1-judged-20261113-01/): `summary.json`,
    `scores.json`, `runs/*/seed*/outcome.json`, HANDOFF.md).
  - **The pattern's fate.** The renewal criterion B1 (J ≥ 0.8 through full founder turnover)
    was false in all 20 fast k1 runs and all 6 (b) runs, as predicted.
    - J at the judged record was 0.25–0.65 in fast k1, 0.49–0.59 in central k1 at 1.7
      turnovers, and 0.65–0.78 in fast k3 after one turnover.
    - The paired copy-only null gives similar values: in the whole-sheet fast k1 37-cell disc
      world, a median J of 0.50 (5–95%: 0.35–0.66) and P(B1) = 0.
  - **The deviation from neutral copying was far smaller than predicted.**
    - In all 30 inheritance runs (a), J was within about ±0.06 of its paired null (ΔJ −0.031 to
      +0.059). At s 1.0 the predicted range was −0.35 to −0.05.
    - At k1 with s 0.3 and 0.6, ΔJ was 0 in all but one run, with the D–H junction weight about
      0.02 of nominal.
    - 41 of 1,827 D copies were lost, which neutral copying cannot do. That makes the classes
      small bias and erosion at s 1.0 and in fast k3: erosion 3/3 at fast k3 s 1.0 and small
      bias 3/3 at s 0.6.
    - Several of those runs have ΔJ > 0, up to +0.044, so where the lost copies sat is not yet
      established. A descriptive readout is pending, and no mechanism is claimed.
    - 3 of 4,853 H copies converted to D, where none was predicted.
  - **The s 1.0 control.** With disc donors only, it lost 14 of 37 founders in two collective
    falls at the rim (6 at 440 s, 8 at 520 s); J was 0.784 at the judged record, minimum 0.649.
    The prediction was J ≥ 0.9 with no collective loss, at low confidence.
    - This is one run, at 5 ms. E1's segments did not cover it, so a 1 ms development check is
      pending.
    - At s 0.6 the control held J = 1 throughout.
  - **Naive isolated templates (b).** The sheet went all H within about one turnover at every τ
    from 40 to 300 s.
    - At s 0.6, recruitment of interior newcomers with five or more D neighbours fell with τ as
      predicted: 9/11, 5/10 and 1/7.
    - At s 1.0, conversions continued at 120 s and 300 s, beyond the predicted early-only
      recruitment.
    - tau* was 300 s at both s, a single draw.
  - **The verdicts.**
    - **Held (8 of 15):** E1; E3 at fast k1 s 0.3 and s 0.6; E4 at s 0.6; E5 at s 0.6; E6;
      validity; B1.
    - **Failed (7):** E3 at fast k1 s 1.0, central k1, fast k3 s 1.0, fast k3 s 0.6, and
      recruitment; E4 at s 1.0; E5 at s 1.0.
    - The design's §7 lists 14 rows; the scorer scores E4's two couplings separately.
  - **Disclosures** (HANDOFF):
    1. The verdicts rest on the scorer's ten readings. The lead accepted them before any
       outcome existed (17:41–17:55 UTC on 13 November, with no outcome on disk).
    2. The scored tau* follows E5's item, counting any converted interior newcomer. The
       driver's five-or-more-D count is supplementary; both give 300 s.
    3. E6's tolerances were set with the seed-101 dry-run values in view. Its A check tests the
       law's quoted constants, not the engine.
    4. Scoring ran from a scoring snapshot (1bfe041) and the loss readout from b351931. Both
       hold the execution snapshot's driver unchanged, with added files only.
    5. A few short jobs ran outside the CPU rule: a few seconds at nice 19, a once-a-minute
       poll, and dry runs on CPU 1.
    6. CPU 2's queue ran 2.6 h slower than CPU 3's, for an unestablished cause. This affects
       cost estimates only.
    7. The watcher restarted twice; no run was affected.
  - **Landing checks.**
    - Tier 1 at the merge f544ccc: 307 files. One outcome changed: `test_d147_drivers.py`.
    - That static guard flagged the three new scripts for importing `heredity_pilot` without
      declaring the field solver. The scorer and the loss readout import only `THRESHOLD_V`, and
      the challenge-build check builds held-bath sheets only.
    - They were added to its EXEMPT list with those reasons, as the guard provides; the frozen
      scorer is untouched. The file then passed 11 of 11, as recorded.
  - **Also landed.**
    - The scorer's tests.
    - The descriptive E4 loss readout (`validation/tissue/e07_v1_losses.py`), written after the
      outcomes; it scores nothing.
    - The E07-v2 challenge build check: four pairings admitted at definition time, nothing
      stepped.
    - The **PROPOSED** E07-v2 note ([E07_V2_DESIGN.md](docs/E07_V2_DESIGN.md)), for the lead's
      review with the advisor; nothing registered.

- **Secreted-species transport v1 (D150): milestones 1 and 2 landed (14 November).** This is
  development code; nothing is judged yet
  ([evidence](/mnt/workspaces/Cells/secreted-species-v1-20261114-01/HANDOFF.md); design §12 and
  §12.1).
  - **What landed.**
    - The operators `scheduled_species_turnover@1` and `scheduled_species_exchange@1`, and the
      inventory-species helper.
    - Two additive adapter functions for @3's per-species chemical term. No existing function
      changed.
    - A definition-time refusal of an inventory species with a membrane, junction or channel
      route of @3's.
    - The tests, a crossrev driver for the new operators, and a radial builder with exact shell
      conductances.
  - **Landing checks.**
    - Crossrev ran from a clean snapshot of 17d00b4 against baseline-21fb714 and was identical in
      all five sets: base 36, qualification 78, injection 6, volume 6 and division 27 programs.
    - The tier 1 and 2 gates at 806eec9: 388 files, no changed outcome. Tier 1 at the merge
      bbbc922: 306 files, no changed outcome.
      - The merge's first tier-1 attempt ran the system Python, which has no pytest, so every file
        failed to start. It is kept as `land-gate1-bbbc922-failed-system-python`; it is not a test
        result.
    - The tier-3 files pass: compiled runs 7/7, ion guards 3/3, energy and radial guards 6/6.
  - **Guards.**
    - Ion fields are bitwise unchanged with both operators active, in scalar runs, restarts, a
      vector batch and a replacement event.
    - Booked work matches the exact ΔG per law, computed independently in 50-digit Decimal.
    - Exchange's kind order, run as a palindrome, is second order.
    - The RK4 radial world's energy residual is 4.5e-14 pJ.
    - The IMEX radial world is second order in dt (ratio 4.05).
    - A stiff front run from a 1e-15 mM trace stays positive, with no step refused.
    - A thousandfold change of the trace moves the profile by 0.947 times that change.
  - **Findings.**
    - **The IMEX energy guard is coarse.** It sees a booking error only above about 2e-3 of the
      species' flows. A 1% face-heat error passes under IMEX at 0.89 of the bound and is refused
      under RK4. So RK4 and the per-law ΔG tests are the sensitive guards (design §7, amended).
    - **The radial errors are turnover's splitting:** dt²·k·(g − k·c_ss)/12 under RK4 and /4
      under ARS. That is negligible at morphogen rates.
    - **Anchored amounts** stall positive near ε × their anchor after kt ≈ 36 (design §1.3,
      corrected).
    - **S5's bridge.** The impermeability refusal blocks the bridge for inventory species until
      the queued D148 round for @3.

- **The shared-inventory reactions design (D152) is accepted (14 November).** The lead, with the
  advisor; docs only ([note](docs/SHARED_INVENTORY_REACTIONS_DESIGN.md), rulings in §9). Every probe
  ran on CPU through `run_detached.sh`
  ([evidence](/mnt/workspaces/Cells/shared-inventory-reactions-20261114-01/): HANDOFF.md,
  `sweep/SWEEP_SUMMARY.md`).
  - **Probe 1, the engine at ac5a251.**
    - MG0c's transport world runs, and its species-set step is admitted.
    - The species' transport is second order (ratios 4.00–4.01).
    - The ions are bitwise unchanged.
  - **The NumPy prototype** is development evidence only.
    - The half-step, the Strang composition and the bookings are second order (ratios 3.98–4.07).
    - The review corrected the stage condition for passive routes.
  - **Mixed-node heat.**
    - A stage quadrature overbooks a passive switch-on from a 1e-12 mM trace by 34–54% in the first
      step.
    - An average-vector-field share goes negative at crossings.
    - The adopted per-route hybrid does neither.
    - The known limit: a driven route that carries a trace species across a passive equilibrium
      within one half-step books 5.4–5.6 times that step's true heat at a 1e-12 mM trace. In the
      probed world that is 0.27–0.56% of the whole heat at 1 s.
  - **C3.** Second order holds up to dt·L ≈ 2 in three stiff worlds, so version 1 refuses
    dt·L > 1.
  - **C4, the engine at ac5a251.** A neutral species on a junction or membrane gets no rate bound
    from @3.
    - In species-only worlds it is refused loudly from x = 0.1.
    - Where other flows set the shared bound, it passes silently up to x = 1, with errors of 0.07%,
      2.3% and 13% at x = 0.1, 0.5 and 1.
    - The sweep found no config, test, registered or qualified world that declares such a species.
      A D148 round for @3 is queued after D150 v1.

- **S5a is qualified: every judged item passed (14 November).** Judged once each, in series, from a
  fresh clean snapshot of main at 7f9c473 (src identical to baseline-21fb714's), after the
  division crossrev matched that baseline. There were no infrastructure kills
  ([judged outputs](/mnt/workspaces/Cells/cell-division-s5-20261113-01/judged-s5j1/)).
  - **Q2, the event map against R-ops:** pass, under the registered rule (the third amendment).
    - The worst ratio is 1.98 eps × magnitude, against a limit of 64.
    - All 66 judged control entries are caught at or below 1e-9.
    - The construction checks are faithful in all 12 cases.
    - Ten near-zero cases were found in the judged sets. Spread 0.1 had none, so it is vacuous
      there.
    - Five readings of the three controls the third amendment exempts fall below 64 at 1e-9, at
      first order (observed against predicted 0.998–1.003). They are reported, not judged.
      Under the frozen rule they would have failed Q2.
  - **Q3, trajectories against R-tissue:** pass. 33 rows, the largest difference 0.445 of its
    tolerance.
  - **Q5, observed order:** pass. Every step term decreases for all 8 measurable components.
  - **Q1 and Q11, the egg-scale world:** pass. The replay is identical and the negative control
    fails.
  - **Q4 and Q6–Q9:** all 21 test files pass at the judged snapshot. Q10 is reported.
  - **What this qualifies:** partition, bridge closure, insertion@2 and lumen@2 in division
    worlds. Q7(b), S3's egg on @2, is deferred to its own registered variant.
  - [Protocol](validation/division/s5_protocol.json);
    [evidence and log](/mnt/workspaces/Cells/cell-division-s5-20261113-01/HANDOFF.md).

- **The S5 protocol is registered (14 November).** The lead registered
  `validation/division/s5_protocol.json` after the final review with the advisor. The JSON's
  registration diff is the status line only.
  - **Before registering:**
    - **The lead read the protocol.** The judged seeds sit in their slots and appear nowhere
      else. The changes since the freeze are the three disclosed amendments and one erratum.
      The threshold is unchanged.
    - **Two rules were added:**
      - an infrastructure kill is not a verdict, and is rerun once from the same snapshot;
      - a judged set with no near-zero draw is reported as untested there, not failed.
    - **A rehearsal on main** reproduced every frozen number. The egg is byte-identical across
      the merges, and the division crossrev matches baseline-21fb714. The rehearsal also found
      that Q2's judge read its seeds from the wrong path, which would have crashed the judged
      run; that is fixed and tested.
    - **A dry run of every judge entry** (Q2 with throwaway seeds, Q3, Q5 and the egg) reached
      and wrote its verdict, and the deterministic items matched the rehearsal exactly.
  - **Next:** the judged runs, once per item, from a clean snapshot of main. They run in
    series and `--oom-first`, so E07-v1's registered arms are protected.
  - **Gate:** tier 1, 303 files, no changed outcome
    ([gate](/mnt/workspaces/Cells/land-20261114d/)).
  - [Evidence and log](/mnt/workspaces/Cells/cell-division-s5-20261113-01/HANDOFF.md).

- **S5 protocol: the third and last control amendment, and the references' self-checks pinned
  (14 November).**
  - **The finding.** Three controls move charge in proportion to the patch charges: a_k, mismatch
    scale and transference. Their effect fades near 0 V while A.8's term does not, so under the
    frozen rule the seen-set preview failed on one near-zero draw.
  - **The amendment.**
    - The three are now judged on the fixed cases, and reported on the near-zero cases beside
      their first-order size.
    - The cause holds in all ten near-zero cases: observed against predicted is 0.99974–1.00040.
    - Parent charge, non-conservation, f and W stay judged everywhere, with margins of 174× or
      more.
    - The threshold, the seeds and the comparison rule are unchanged.
    - Both preview verdicts are recorded: fail under the frozen rule, pass under the amended
      one.
    - No judged state has been drawn. After registration, any control miss is a failed Q2.
  - **The references' own 64-eps self-checks** are pinned to the tight scale
    (`charge_term=False`). R-tissue uses R-ops' values only.
  - **Gate:** tier 1, 303 files, no changed outcome
    ([gate](/mnt/workspaces/Cells/land-20261114c/)).

- **The S5 protocol, frozen as PROPOSED, then R-ops' A.8 amendment (14 November).** They land
  as two merges in that order, so the freeze is on main before the new Q2 scale.
  - **The protocol** (`validation/division/s5_protocol.json`, built by `s5_protocol.py`) is
    PROPOSED, not registered. The S5 drivers refuse a judged run until it is registered from a
    clean snapshot. It fixes in advance:
    - **Q2's draws:** seen sets (development evidence) and judged sets with fresh seeds the lead
      assigned. The judged sets have never been run at either scale.
    - **Negative controls:** their targets, the 1e-9 threshold and the smallest-defect-caught
      statistic. Two amendments record findings:
      - ΔG is stationary at the correct split, so W can be reached only at second order. W
        gets its own free-energy control.
      - The bath's image charge moves only under a non-conserving defect, so it gets a
        non-conservation control.
    - **Q5 and Q10:** reported, not judged. Q5 keeps its stop rules.
    - **Q7(a):** the 19-cell sheet with idle division operators is bitwise.
    - **Q7(b):** deferred. S3's egg on @2 needs its own registered variant, so the @2
      operators count only in division worlds until it passes.
  - **R-ops' A.8 amendment.**
    - A cell's node-charge magnitude adds |Q̄| + 10⁻¹⁵ F Σ|zΔ|, carried through R-ops' own
      solve. `charge_term=False` gives the earlier magnitudes.
    - It loosens charges and potentials 70–160× on the usage example, and amounts barely.
    - On R-ops' own random states, which have large increments, it loosens them up to 1e9
      ([ratios](/mnt/workspaces/Cells/cell-division-s5-references-20261113-01/a8-ratios/a8_ratios.json)).
  - **Next:**
    1. the new-scale development pass: the seen sets under both scales, and every control;
    2. the advisor's review;
    3. registration and the judged runs.
  - **Gate:** tier 1 on the merged tree, 303 files, no changed outcome. The two new runs files
    pass uncapped: limits 4 tests, idle sheet 2 ([gate](/mnt/workspaces/Cells/land-20261114b/)).
  - [Evidence and log](/mnt/workspaces/Cells/cell-division-s5-20261113-01/HANDOFF.md).

- **Checkpoint continuity, first landing (D153; 14 November).** A checkpoint written under one
  source resumes under another only through a recorded admission. Refusal stays the default
  ([design](docs/CHECKPOINT_CONTINUITY_DESIGN.md)).
  - **Engine:**
    - `cells/continuity.py` verifies and binds records on the host;
    - `load_snapshot` and `load_batch_snapshot` take `continuity=`, and with `None` today's
      code path and messages are unchanged.
  - **Tools** (`validation/continuity/`):
    - `probe.py` compares programs, constants, StableHLO and bindings, replays the host
      side, and runs a bitwise CPU overlap;
    - `admit.py` and `verify_run.py`;
    - `dev_run.py` drives the first consumer.
  - **Scope:**
    - vector windows only, on CPU definitions with `jit: true`;
    - case 1 (source changed, programs unchanged) is admitted by the probe;
    - case 2 needs a D148 record, admitted by the lead;
    - cases 3 and 4 are refused.
  - **Evidence:**
    - an admitted resume across a source change is bitwise equal to the uninterrupted run
      and passes `verify_run` (17 checks);
    - a program edit is refused;
    - 100 tests pass: loaders 54, bypass guard 17, tools 18, acceptance 11.
  - **D148 for the landing:** crossrev on the landing tree (21fb714) is identical in all five
    sets: base, qualification, injection, volume and division. The renewed baseline of record is
    [baseline-21fb714](/mnt/workspaces/Cells/checkpoint-continuity-20261113-01/baseline-21fb714/baseline-of-record.json).
  - **Not yet:**
    - the GPU probe (§13.4), queued for the next L4 gap;
    - rule (b) records for four tools;
    - scalar snapshots, which answer "cannot decide".
  - [Evidence and log](/mnt/workspaces/Cells/checkpoint-continuity-20261113-01/HANDOFF.md).
- **Cell division S5a, qualification pending (14 November).** `isopotential_partition@1`,
  `cytoplasmic_bridge_closure@1`, `scheduled_membrane_insertion@2` and
  `restricted_cleft_lumen@2` land at S5a's 1691dc2, with closers and the contract's host-side
  liveness methods ([design](docs/CELL_DIVISION_S5_DESIGN.md)).
  - **Guards:**
    - crossrev is identical in every existing set (base, qualification, injection, volume);
    - S5's own set records E_ref, q_ref and `partition_birth_gate` as bindings;
    - the J2 bright line holds, including a fresh-process test that S5's crossrev tool never
      loads a J1 module.
  - **Development comparisons with the independent references, at this commit:**
    - **Q3**, trajectories after partition against R-tissue on the compact 1→2→4 world: each
      difference is about 4/3 of the engine's step term (Vm 1.13e-7 V against 8.5e-8 V),
      within 3 × (step + reference).
    - **Q5**, observed order 1.99–2.06.
    - **Q4:** the open-bridge limit holds to 1e-3, and the symmetric, asymmetric and
      isopotential limits hold in NumPy.
    - **Q1 and Q11** at egg scale, 120,000 steps through 1→2→4:
      - energy balance 4.2e-7;
      - charge at 0.0087 of its bound;
      - electrode charge error 3.4e-23 C.
    - **Q2 is open.** It sat within 64 eps × magnitude only under a 10% net-charge band, now
      withdrawn; near zero potential the ratio reached 860.6.
      - The cause is confirmed: rounding in charge formation from increments.
      - The lead's ruling adds an increment-form charge term to R-ops' magnitudes (A.8,
        pending in R-ops).
  - **Scope change:** S3's cleft egg on insertion@2 and lumen@2 (Q7b) is deferred to its own
    registered variant in S3's protocol family. Until it passes, the @2 operators count only
    in division worlds, and S3's egg stays on @1.
  - **Not yet:**
    - the registered protocol and its judged runs;
    - the second Q3 world, the closed-bridge limits and the PROPOSED protocol, which exist so
      far only on S5's branch.
  - **Gate:** tiers 1 and 2 on the combined tree with checkpoint continuity, 382 files, no
    changed outcome. The four slow new files also pass uncapped on the same tree: partition
    runs 11, division runs 5, bridge runs 1, continuity acceptance 11
    ([gate](/mnt/workspaces/Cells/land-20261114a/)).
  - [Evidence and log](/mnt/workspaces/Cells/cell-division-s5-20261113-01/HANDOFF.md).

- **Water plus replacement: `scheduled_cell_replacement@2`, the volume ledger (composite v2
  §2; 13 November).** @2 runs @1's event map unchanged, then:
  - gives the newcomer its volume: a template's declared volume, or for a donor copy the donor's
    (decision 10);
  - books removed and supplied volume in water's ledgers;
  - books water's dilution and elastic free-energy change in fields of its own.

  It refuses `law_steady` over water, and it refuses `[water, injection@1]` (injection's view
  conflict on volume).
  - **Guard A, outcome A under its registered rule:** no qualified program changed.
    - Crossrev with constants is identical to the baseline of record (36/36/12, 78/78/56,
      6/6/2).
    - All 58 forward worlds are identical in every field, ledger accumulators included.
    - The W1 and W2 judges are identical, step-map numbers included. Rm1 and G2-Q1 are
      identical apart from provenance strings.
    - 24 files (354 tests) pass, the frozen models' 130 included.
  - **Guard B passes:**
    - without events the composition equals water alone, bitwise;
    - with water closed it equals @1 on @1's fields, bitwise;
    - every ledger closes across events (energy within 1e-9 pJ, water within 1e-14 pL);
    - water's first flow after an event is analytic to 1e-12;
    - restart and vmap pass.
  - **Cost:** about 1.5 ms per step on the 127-cell sheet (water alone 4.3–5.5 ms, with @2
    6.0–7.0 ms); compile goes from 28 s to 44 s.
  - **Open:** `law_steady` over water, and an injection law that books dilution. Both wait for
    a consumer. All runs so far are development runs; no judged run uses @2 yet.
  - **Gate:** tiers 1 and 2 on the merged tree, 374 files, no changed outcome
    ([gate](/mnt/workspaces/Cells/land-20261113s/)). New files: `test_cell_replacement_v2.py`
    in tier 1, `test_cell_replacement_v2_runs.py` in tier 3.
  - [Evidence and log](/mnt/workspaces/Cells/composite-v2-s2-20261113-01/HANDOFF.md).

- **The S5 independent references, R-ops and R-tissue (13 November).** A separate agent wrote
  them from Appendix A and §10.1 of the [S5 design](docs/CELL_DIVISION_S5_DESIGN.md). It read no
  S5 engine code, and its read list is in the log.
  - **R-ops** (`validation/division/partition_reference.py`) is the division map (A.6) in NumPy.
  - **R-tissue** (`validation/division/cleft_tissue_reference.py`) generalises R-full to cells,
    clefts, contacts, bridges and lumens. It integrates with Radau at rtol 1e-10 and applies
    R-ops at each division.
  - **Results:**
    - R-tissue reproduces R-full on S3's egg at J1 to 6.4e-16 V (target 1e-10 V), and over all
      211 pulses to 1.0e-14 V;
    - R-ops' identities hold to 1.96 eps × magnitude on 200 random states;
    - the symmetric, isopotential and bridge-open and bridge-closed limits hold;
    - R-full is untouched.
  - **Status:** they are the references for S5's Q2–Q5, and nothing is judged yet.
  - **Gate:** tier 1 on the merged tree, 291 files, no changed outcome
    ([gate](/mnt/workspaces/Cells/land-20261113r/)). Of the new files, one is in tier 1, two in
    tier 2, and the J1 cross-check (about 110 s) in tier 3.
  - [Evidence and log](/mnt/workspaces/Cells/cell-division-s5-references-20261113-01/HANDOFF.md).

- **Crossrev now compares constants; earlier verdicts stand (13 November).** The
  checkpoint-continuity design found that `composite_crossrev.py` compared jaxpr text and
  bindings, but not the values of closed-over arrays or the device-check constants. A
  constant that only gates acceptance could have changed unseen.
  - The tool now records the dtype, shape and SHA-256 of every closed-over array, and the
    check constants. Scalars such as `NEWTON_TARGET` were already caught as full-precision
    literals in the text.
  - The retro-check from `8416a72` to main found every constant unchanged, so the D148,
    S2 and S3 crossrev verdicts stand.
  - The new baseline of record, with constants, is
    [crossrev-constants](/mnt/workspaces/Cells/cell-division-s3-20261113-01/crossrev-constants/baseline-of-record.json).
  - D148 states what crossrev compares. The D147 floor guard compares primitive counts,
    not constants, so it is rerun with constants before version 3 serves a run of record.
  - Tier 1 gate: 290 files, no changed outcome.
  - The proposed [checkpoint-continuity design](docs/CHECKPOINT_CONTINUITY_DESIGN.md)
    landed with it. Implementation waits for its probes and for the user's answer on
    AGENTS.md's attestation rule.

- **Field-solver limits: on CPU the hold step is mostly work on dense node-space matrices that
  are under 1% dense. The factorisation and solve kernels alone are just under half. An
  interface is proposed, with no code (13 November; `resolved_pump_tissue@3`,
  `capacitive_reduction_gauged_damped_newton@2`).**
  - **Hypothesis and test.** Most of a hold step is dense float64 node-space linear algebra:
    the IMEX operator's Cholesky every step, the capacitor and stage triangular solves, and
    the offset LU and products. It is falsified if these take under half the step at 825
    nodes on CPU.
  - **Result on CPU: falsified as stated, narrowly.** The measurement is the hold world's
    fused step on one core, each instruction's own time:
    - the four kernel classes take 45% of attributed time (Cholesky 25%, triangular solves 15%,
      LU 5%), or 33% of the 110 ms to ready;
    - adding the n × n assembly, copies and checks that dense matrices need, dense node-space
      work takes 70% (51% of time to ready);
    - the pieces compiled alone (75–81%) are an upper bound;
    - a first trace that summed nested events read 49% and is kept.
  - **Sparsity at 825 nodes.**
    - The free IMEX operator is 0.67% dense. Minimum degree gives a factor with 7,537
      nonzeros and about 1,800 times less factorisation work than the dense Cholesky.
    - The offset incidence is 0.40% dense, and the junction incidence is empty, so the
      Jacobian's junction product adds an exact zero.
    - At 254 nodes (the 127-cell sheet) every node-space operator is diagonal.
  - **Conditioning and drift.** The operator's condition number is 223 after Jacobi scaling.
    In the hold it moves at most 4.7 × 10⁻⁵ from t = 8 s to 1,206 s, and 3.3 × 10⁻¹⁰ over one
    200-step window.
  - **Design.**
    - **Interface.** One solver per field-solver ID covers the capacitor, IMEX and offset
      solves, in three phases: bind, prepare and solve. The existing residual checks are the
      acceptance test.
    - **Candidates.** Sparse direct with a bound ordering, PCG, and factor reuse at declared
      epochs (the composite note's R3 options (b) and (c)). Each is a new solver ID with
      tolerance-based qualification.
    - **Node bound.** Each ID would declare its own node bound in place of the 2,048-node
      dense limit.
    - **Ceilings.** By the L4 split no single piece gives 2×. On CPU, making all dense
      node-space work free gives about 2× to 3.4×.
    - **Next.** No code until the kernel profile has run on the L4 and GH200.
  - **Kernel profile plan.** About 15 min: traces of E07's world at 6 and 256 worlds and of the
    hold world at 6, then the pieces on the device and batched.
    - It reruns unchanged on GH200 and was smoke-tested on CPU.
    - Device-kernel attribution is untested on a GPU; the batched pieces are the fallback.
  - **The first pass's three hold steps refused** the hold's GPU backend on CPU. They are kept
    in `logs/` and were rerun with `--backend cpu`.
  - [Design note](docs/FIELD_SOLVER_INTERFACE_DESIGN.md),
    [summary](/mnt/workspaces/Cells/field-solver-limits-20261113-01/summary.json),
    [results](/mnt/workspaces/Cells/field-solver-limits-20261113-01/results/),
    [kernel profile plan](/mnt/workspaces/Cells/field-solver-limits-20261113-01/kernel_profile_plan.sh).
  - **Also landed:** the L4 agreement driver now takes three blind repeats (A, B, D)
    before a judged run, after a third L4 repeat exceeded one pair's spread by up to 6×.
    The definition-invariant waste found here is listed as a parked candidate for its own
    D148 round. Tier 1 gates: 289 files, no changed outcome.

- **Stage S3 judged: the engine's cleft egg agrees with R-full (13 November; registered
  protocol `486cc60`; verdict pass).**
  - **Engine models:** `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with
    `membrane_entity_state@1`, `scheduled_membrane_insertion@1`, `restricted_cleft_lumen@1`
    and `electrode_current_injection@1`.
  - **The run:** once, from a clean snapshot of main `4465b48` on CPU 4 (54 min, no OOM),
    with device checks passing on every row. It reproduces the 0.25 ms development run
    bitwise in every recorded number
    ([protocol](validation/division/cleft_egg_protocol.json),
    [evidence](/mnt/workspaces/Cells/cell-division-s3-20261113-01/judged/)).
  - **Engine − R-full at 0.25 ms,** against 3 × (step term + integrator-only reference term):

    | Quantity | Engine − R-full | Tolerance |
    | --- | --- | --- |
    | Em at J1 | +4.0e-10 V | 1.0e-9 V |
    | Rm at J1 | +7.8 Ω | 15.3 Ω |
    | Em at every pulse edge, 0–210 | at most 1.1e-7 V | 2.7e-7 V |
    | Lumen K at J1 | −9.5e-7 mM | 2.6e-6 mM |
    | Lumen Na at J1 | +7.6e-7 mM | 1.9e-6 mM |
    | Rm1 (reported only) | +18 Ω | 41 Ω |

    Each judged quantity is at 0.36–0.51 of its tolerance.
  - **The reference term** covers R-full's integrator variants only. It was chosen after the
    development data and disclosed as the stricter rule. The activation-area variant is
    reported as a sensitivity both models share.
  - **Crossrev baseline renewed at the landing commit (D148):** base 36/36 jaxprs and 12/12
    bindings, qualification 78/78 and 56/56, injection 6/6 and 2/2, all identical to the
    earlier runs.
    - The new baseline of record is
      [crossrev-landing](/mnt/workspaces/Cells/cell-division-s3-20261113-01/crossrev-landing/baseline-of-record.json).
    - `8416a72` stays the earlier record.
  - **Next in division:** S4–S5, partition and bridge closure, towards prescribed division
    (milestone 1).

- **Checkpoint continuity approved as tooling (13 November).** The user's words: "yes fix
  checkpoint continuty also". This approves the versioned checkpoint migration, which D145 listed
  as unapproved tooling; the public validation package is still unapproved.
  - **What refuses resumes today:** `io.load_snapshot` and `batch_io.load_batch_snapshot`
    refuse any change in the SHA-256 of every `.py` under `src/cells`, and any change in
    `runtime_identity`. That covers the package versions, `XLA_FLAGS` and, on GPU, the device
    kind, so an L4 checkpoint cannot resume on GH200. `runner.validate_checkpoint` also
    refuses a layout that differs from the declared model's.
  - **Already outside that rule** (corrected from the design's §7): 32 non-test files under
    `validation/` and `scripts/` name `state.npz`, but most only read or write saved bytes.
    - Three uses crossed an identity: `scripts/profile_dispatch.py` (held L4 states under
      other XLA flags), `field_floor_held.py` (version 3 on version-2 states), and E07-v1's
      import of the sheet70 start states, which crosses the D148 ledger fix.
    - The driver-owned resumes have no identity check: `e07_v1_run.py`, the turnover tool's
      `checkpoint.npz`, and `open_calcium_bath_trajectory_production.py`'s handoff.
  - **Plan:** a fresh agent writes the design only, in the slot the S3 agent frees, ahead of
    the one-execution-path work, since both own the checkpoint validation.
    - It keeps four cases apart:
      - **source changed, step program identical:** admitted;
      - **program changed, physical fields unchanged:** only with a D148 record;
      - **definition, layout, solver or model ID changed:** refused (D146, D147);
      - **runtime changed:** its own rule, with a move to GH200 judged by tolerance.
    - Refusal stays the default, and every migration is an explicit, recorded step.
    - Registered runs are unchanged, and the first consumer is a CPU development run.

- **Hold segment 2 continues on version 2. The L4 dispatch test rules out loop control
  (13 November).**
  - **The hold.** Segment 1 ended cleanly at 14:48 UTC: 6,000 windows and snapshot
    `t01206`, in 20.1 h. The restart rule gave no restart:
    - command buffers ran at 1.00× and masked loops at 0.22×;
    - the margin at the end of segment 1 is 0.21 of `NEWTON_TARGET` (at most 0.45 over the
      snapshots).
    - Segment 2 runs from `source-09` as `cells-w1-ft2-seg2`, from 15:48 UTC.
  - **The finding.** One six-world step takes 48 ms on the L4: 23 ms of field solve, 25 ms
    of the rest, and 9 ms more for the device checks. The rest and the checks run no loops.
    - Removing all host-blocked loop time would give at most 1.37×, under the 1.4×
      break-even.
    - The cost is device execution. The leading hypothesis is dense float64 node-space
      linear algebra per world, about 0.32 GFLOP per world-step: chiefly a Cholesky of the
      825-node IMEX operator every step. This is read from the code, not timed.
    - The L4 does not repeat bitwise, so an equivalence test there needs three or more
      repeats.
    - Version 3 accepted all 1,000 steps from t = 0 on the L4.
    - [Note](/mnt/workspaces/Cells/window-timing-20261112-01/l4-dispatch-note.md).
- **Combined landing: the S3 ledger fix (D148), stage S3's engine side and the phase markers
  (13 November).** Tier 1 + 2 gate: 369 files. The one changed outcome was the D147 driver
  guard catching the new D148 guard tool; it is now exempt with its reason and passes.
  - **The ledger fix.** `surface_tissue.capacitor_change` sums species in a fixed order, so
    @3's electrode ledger telescopes exactly at egg scale.
    - Physical fields are bitwise in all 58 guard worlds, and the judges' registered numbers
      are unchanged; only the electrode accumulator moves, by each world's former residual.
    - D148 records when an in-place fix to qualified code is admissible.
    - The crossrev baseline is renewed at this landing, and `8416a72` stays as the earlier
      record.
  - **`restricted_cleft_lumen@1`.** A restricted compartment filled from the bath as the
    membrane area grows. It books volume work and mixing heat, and reads lumen composition
    at the area of each saved time.
  - **The cleft-egg engine definition** is built from R-full's own egg; all 30 fields agree.
    - The development dt study gives, at 0.25 ms, engine − R-full of 4e-10 V in Em at J1,
      7.8 Ω in Rm at J1, and under 1e-6 mM in the lumen.
    - The S3 protocol uses an integrator-only reference term, chosen after the data and
      disclosed as the stricter rule. Its judged run follows.
  - **Phase markers.** Binding, plan validation, compile and the first window are reported as
    they happen, and timings are grouped into phases. This is host-only and bitwise.

- **Cell division S0b: the registered J1 combination round is parked (13 November;
  development, judged by its own registered criteria).** No eligible point passes, under
  either criterion form. Nothing is frozen and no C1 registration follows. R-full with the
  registered inputs stays the reference, and its J1 failure and the shared shape mismatches
  are recorded as unexplained. C1 and J2 stay held, and there is no third round
  ([registration](validation/division/j1_combination_round.md),
  [evidence](/mnt/workspaces/Cells/cell-division-s0b-20261111-01/j1-combination-01/)).
  - **What ran:** nine points on R-full, from a clean snapshot of main `6b77733`, in two
    units (66 CPU-min in total, no OOM). The null check reproduced the record to 2.3e-12 V.
    - A1 × A7a, with f calibrated at J1 at α 0, 0.5, 1 and 2 (f = 0.0193 throughout).
    - Seal × A7a and seal × A6c at α 0 and 1.
    - A6c × A7a at α 1.
  - **The front-loaded Rm fall fails at all nine points** (D5 0.85–0.98, against ≤ 0.66).
    It is the only criterion A1 × A7a fails at the marked α = 1.
  - **The early Em minimum** (T-D3) fails everywhere except A1 × A7a at α 0–1, where Em is
    still falling at J1.
  - **Pairings without A1 miss the J1 window.** Seal × A7a gives −16.5 mV and A6c × A7a
    −13.8 mV, both within 0.04 mV of their registered predictions. Seal × A6c gives −18.4 mV,
    0.9 mV more negative than its additive estimate and 0.3 mV short of the window.
  - **The two T-D7 forms** disagree at two points, both of which fail other criteria under
    both forms. No verdict depends on the form.
  - **Reported only:** cytosolic Na at J1 is 20.1–20.3 mM, against the measured
    22.4 ± 1.1 mM.
  - **Resuming** needs new measurements or the user's decision. One cosmetic runner bug:
    the null check's flag is written as 1.0 rather than true.

- **E07-v1 registered (13 November; renewal stage, option (c)).** Registered before any engine
  run: [design](docs/E07_V1_DESIGN.md) and
  [protocol](validation/tissue/e07_v1_protocol.json).
  - **The frame.** Donors are drawn without regard to state, over the whole sheet, and
    each run is judged against its paired copy-only null. Copying alone never passes B1
    (0 of 2,000 seeds), so a positive B1 needs recruitment. Disc-only donors are a
    control.
  - **The formation law** gives time-averaged junction abundance after the first
    turnover of only 0.20 (fast k1) and 0.15 (central k1). That is why fast k3 arms were
    added, and why junction weight is reported per run (E6).
  - **Judging.** Each run is classed and judged by 4080 s, the control's end. Censored
    runs are judged at their last valid record and never dropped. Arm (b) is
    threshold-finding.
  - **Scale:** 38 judged runs plus E1, about 50 core-hours.
  - **Execution:** one clean snapshot of main after the S3 ledger fix and the engine-run
    driver land.
  - Tier 1 gate: no changed outcome
    ([gate](/mnt/workspaces/Cells/land-20261113j/)).

- **User decisions of 13 November, taken on the lead's suggestions after the advisor's
  review.**
  - **D149:** `processes/source_electrochemistry.py` keeps the reference's four
    numerical conventions as a cited profile of `emt_mirna_pair@1`. This is an exception
    to AGENTS.md, for bitwise continuity of the recorded replication runs.
    `tests/unit/test_source_profile_boundary.py` confines the module to that model.
    Nothing is renamed. Tier 1 gate: 285 files, no changed outcome.
  - **J1:** a registered combination round. Its registration is being drafted, and
    nothing runs until the lead registers it. The round has:
    - an exit rule;
    - numeric criteria fixed before the runs;
    - a calibration datum per unknown;
    - a pairing without A1.
  - **E07-v1, option (c):** donor copies as the main route, and isolated newcomers with
    fast junction formation as a threshold-finding set.
    - Donors are drawn without regard to state; disc-only donors are a control.
    - A copy-only null comes first, and a design and registration draft follow.
    - Replacement over water (v2 §2) comes after the S3 fix lands.

- **G2-Q1's judge runs again as registered (13 November).** Its Q2 part had failed on the
  tree since `92a4eeb`, when replacement@1 became a thin composite module and stopped
  exporting `CHARGE_PER_FMOL`, which the judge reads. The thin module re-exports it, and Q2
  run as registered equals the recorded judged run. A tier-1 test,
  `tests/unit/test_judge_imports.py`, checks that every name the registered judges (G2-Q1,
  W1, W2, Rm1) import or read exists. Tier 1 gate: 284 files, no changed outcome.

- **Field-solve acceptance: a convergence test with no margin on the full tissue; new
  definitions with free field offsets declare solver version 3 (D147; 13 November).**
  - **The defect.** Version 2 accepts a field solve when the normalized residual is ≤ 0.01.
    On the W1 hold's 825-node tissue a converged root sits at 0.8–1.1 of that, at the
    rounding floor of the current balance. So acceptance depends on how XLA compiled
    the program.
    - From t = 0, the vectorized CPU program refuses at 0.085 s and 0.186 s, and scalar
      `jit` refuses at 0.45 s. The L4 accepted 0–6 s and more than 1,100 hold windows.
  - **Exposure.**
    - The W1, W2, G2-Q1 and sheet70/turnover worlds have no free field offsets (residual
      exactly 0), so their results don't depend on this.
    - The hold's tissue reaches 0.92–0.995 of the target from t = 0 (CPU), and 0.18–0.45
      at 8 s.
  - **Version 3** (`capacitive_reduction_gauged_damped_newton@3`, opt-in since 9 November)
    also accepts residuals within 1e3 ulps of the attainable floor. It accepts every edge
    state, with states bitwise equal to version 2's before them.
    - **Guards:**
      - crossrev on 41 worlds;
      - dumps of W1, W2, G2-Q1, Q5, Q6, W37 and the 825-node world equal under v3;
      - a solve held at 0.95 of the cap passes every row check and ledger, and moves
        the state by ≤ 5e-13.
    - Row checks and ledgers cannot see field residuals, so v3's safety rests on that
      state bound.
  - **D147:** a definition with free field offsets declares version 3. Version 2 and every
    qualified ID are unchanged, and a switch is a new definition. `heredity_pilot.py
    --field-solver auto|2|3` applies it (default `auto`), and `--field-solver 2` rebuilds
    `source-09`'s definitions exactly.
  - **The hold** stays on version 2. Its restart rule at the end of segment 1 is set by the
    L4 dispatch test (`scripts/profile_dispatch.py`).
  - Tier 1 + 2 gate: 359 files, no changed outcome
    ([gate](/mnt/workspaces/Cells/land-20261113e/)).
  - Evidence: [design note](docs/FIELD_FLOOR_ACCEPTANCE_DESIGN.md),
    [guards](/mnt/workspaces/Cells/field-floor-guards-20261113-01/summary.json),
    [driver](/mnt/workspaces/Cells/field-solver-driver-20261113-01/summary.json).

- **S3 prerequisites (a) and (b) resolved; the L4 driver takes runs split across GPU gaps
  (13 November).**
  - **(b) Injection books at the view.** A split part declaring `BOOKS_AT_VIEW` receives
    the composite's view in its half-steps when a field input is provided. Injection then
    books plate charges and the capacitor-energy change there, so insertion and injection
    compose. Without a field input the arithmetic is unchanged.
    - Guards: the analytic two-clamp image charge after insertion; every ledger closing;
      pulses across a masked furrow and its onset; restart mid-insertion; vmap.
    - Crossrev against `8416a72` identical, and the injection world set identical to
      `00672e8`, so the judged Rm1 stands.
  - **(a) The onset energy.** The furrow opens uncharged at bath composition, which is
    R-full's convention. Charging dissipates ½·C_on·Vm² whatever the access resistance.
    - At the egg's 6.6 µs access time no admitted step resolves this. The unbooked part is
      at most 3.1e-4 pJ, 7e-8 of the host energy bound, and tests pin it.
  - **(c) Open: an egg-scale electrode-ledger drift**, about half an ulp per step after the
    Na increment crosses 2¹⁶ fmol, seeded by the pulses. The mechanism is being pinned
    before any fix; S3's egg runs wait for it.
  - **S3 plan** (`docs/CELL_DIVISION_S3_PLAN.md`): the engine against R-full on the cleft
    egg. Draft; the lead's choices are a judged step of 0.25 ms, lumen K and Na judged, and
    Rm1 reported. Nothing has run.
  - Tier 1 + 2 gate: 357 files, no changed outcome
    ([gate](/mnt/workspaces/Cells/land-20261113d/)).

- **Composite v2 §3, stage S2: membrane state and insertion landed (13 November).**
  `membrane_entity_state@1` owns area and capacitance as state (R2 views).
  `scheduled_membrane_insertion@1` inserts membrane on a patch as a split process, with
  onset masks selected by value. Engine models: `resolved_pump_composite@1` over `@3`.
  - **Energy:** @3's capacitor term reads the declared C0 and arrays, so insertion's ledger
    terms add the correction. The total equals ½ΣCV² − ½ΣC0V0² to 1e-12 (one patch, and two
    clamps with plate charges). The one-patch analytic checks hold: V′ = VC/C′,
    H = ½q²ΔC/(CC′), ΔU = W − H.
  - **Guards:**
    - crossrev against `8416a72` identical, measured twice;
    - 17 saved runs bit-identical;
    - idle and rate 0 bitwise equal to the composition without the operators;
    - restart across onset and insertion bitwise, and a reversed vmap batch bitwise;
    - catalogue invariance holds, and every composite test file passes.
  - **Limits:**
    - Field-input providers are refused above 64 padded field nodes. The per-step
      refactorisation costs +7.5% on the egg and +48% at 825 nodes.
    - Every planned egg world fits (up to 16 cells, 47 nodes). The 825-node idle guard
      waits for option (b) or (c).
    - Insertion itself adds 15% per step on the cleft egg.
  - **Departures and open items:**
    - The new membrane's leak is its passive permeability. This departs from division
      design §6, because @3 needs law code 0 for inactive populations.
    - Water and replacement refuse to compose with membrane state (`CONFLICTS_VIEW`).
    - S3 prerequisites: the onset energy at a fast access (about ½C_f·Vm² unbooked), and
      injection booking its image charge at the view.
  - Tier 1 + 2 gate: 358 files, no changed outcome
    ([gate](/mnt/workspaces/Cells/land-20261113c/));
    [evidence](/mnt/workspaces/Cells/composite-v2-20261112-01/HANDOFF.md).

- **Energy roles declared, and the hold's window timing diagnosed (13 November).** Tier 1 + 2
  gate: 356 files, no changed outcome ([gate](/mnt/workspaces/Cells/land-20261113b/)).
  - **Energy roles** (completes v2 §1.1): heat and work fields are declared by name (the
    adapter's `HEAT_FIELDS` and `WORK_FIELDS`, and each operator's own). They reach
    `surface_pump.ledger_limits` through its new optional `flow_fields` argument; the
    default keeps suffix selection. For every registered composition the declared table
    equals the suffix selection, and the guards against `8416a72` are identical.
  - **Window timing** (read-only on the hold):
    - On the L4, 88% of the hold's wall time is inside the GPU dispatch call, about 53 ms
      per batch step for six worlds; host work is about 12%.
    - The 0.41 ms per step in `run.json` was the previous window's host tail, not device
      time.
    - Leading hypothesis, untested: the field solve's data-dependent `while_loop`s are
      driven from the host.
    - Segment 1 ends about 15:25–16:55 UTC: 20–22 h per 1,200 s segment and 71–77 h for
      the whole hold.
  - **Fix:** pump-family experiments keep their built `changes`. That takes the call from
    10.3 ms to 0.4 µs (and `event_index` from 10.3 ms to 1.3 µs), about 2% of a window.
    The jaxpr, a scalar run and a six-window vectorized run are bitwise identical. The
    hold stays on `source-09`.
  - [Evidence](/mnt/workspaces/Cells/window-timing-20261112-01/summary.json).

- **Heredity turnover under the literature newcomer rule: no disc renewed, and B1 failed
  in all 21 arms, as predicted (11–13 November; development pre-screen, not judged).**
  Driver `validation/tissue/heredity_turnover_literature.py` on
  `resolved_pump_replacement@1` (inner `@3`, IMEX ARS(2,2,2), dt 5 ms). 5 ms matches 1 ms
  within 9 µV, with identical D sets. [Summary](/mnt/workspaces/Cells/heredity-turnover-literature-20261111-01/summary.json),
  [log](/mnt/workspaces/Cells/heredity-turnover-literature-20261111-01/HANDOFF.md).
  - **Design:**
    - the five sheet70 discs that held 70 min, from their state 2 min after the cue;
    - only disc cells are replaced, oldest first, with residence 1, 3 or 10 times the
      formation time (fast 2 + 15, central 10 + 30, slow 20 + 60 min);
    - newcomers are isolated H templates or donor copies of a random neighbour (D139);
    - predictions were registered before any run.
  - **Isolated newcomers: none of 317 became D.**
    - Their junctions form only after their D neighbours have been replaced or pulled to
      H, and their Vm never rose above −68.9 mV (D starts at −39.4 mV).
    - Discs ended all H at 0.98 R (s 0.3), 0.59–0.96 R (s 0.6) and 0.23–0.81 R (s 1.0).
      At s 1.0 that was 15–59 min after the cue, against 70 min without turnover.
    - Stronger coupling made it worse.
  - **Donor copies: persistence by copying only.**
    - D copies stay D, but H cells from outside dividing into the rim erode it.
    - J after one and two turnovers was 0.73–0.89 and 0.51–0.58 at s ≤ 0.6, and 0.59
      and 0.43 at s 1.0 with k1. The disc was lost at k3 and k10.
    - Each disc had one seed.
  - **Predictions:** 26 registered items failed, listed in `summary.json`. Most are the
    predicted interior conversions, loss windows and donor J ranges.
  - **After the predictions were frozen,** a stress segment (formation tau 40 s, s 0.6,
    six D founder neighbours) converted newcomers at A 0.59–0.68. Conversion needs D
    neighbours that persist.
  - **Also:** no refusal, no D outside the disc, no osmotic censor (max excess 14.4%).
  - **Incidents:** out-of-memory kills stopped three arms (12 November 01:36 machine-wide;
    19:33 in cells.slice). Each was rerun from the same snapshot; the 19:33 rerun
    reproduced its completed run bitwise. The end-of-arm analysis peaks near 5 GB RSS, so
    cap longer arms at 6G or run the analysis separately.
  - **Engine gap:** replacement over the water inner model (G2 stage 3), needed for
    donor-copy arms beyond about 95 min of inherited loading.
  - **Next:** the E07-v1 redesign is the user's decision.

- **Composite v2 §1.1: bound step checks and @3's free-energy owner (13 November).** The
  composite binds its step checks to the definition. @3's bound checks run on each
  operator's `inner_check_spec` adjustment, then each operator's own checks run; water's and
  the symport's definition-only bounds are computed once.
  - Layout builds per clock are now constant (water@1 5, water@2 6, replacement@1 2), where
    before that many were built per chunk; no control tables are built.
  - @3's chemical and capacitor free energy are owned by `pump_composite_adapter`.
    Replacement and injection use it there, so injection's temporary import is gone.
  - Guards against snapshot `8416a72`: jaxprs 36/36 and 78/78 and bindings 12/12 and 56/56
    identical; 17 dumped worlds bit-identical; the eight composite, injection and
    step-check test files pass.
  - Tier 1 + 2 gate: 355 files, no changed outcome
    ([gate](/mnt/workspaces/Cells/land-20261113a/)).
  - **Next:** the declared energy-role table (built and guarded, lands next round), then S2
    membrane state (v2 §3), with field-input providers refused above 64 field nodes.

- **BITSEY-derived identifiers renamed to neutral names (D146; 12 November).** A pure
  rename: `bitsey_emt_pair@1` → `emt_mirna_pair@1`, its observer →
  `emt_mirna_pair_pure_readouts@1`, the parameter sets → `emt-mirna-pair-scaled-simple` and
  `emt-mirna-scaled-simple`, the units → `nominal_time_unit` and `scaled_coordinate`.
  - Ten runs are bitwise identical before and after. There are no aliases: old configs
    and checkpoints are refused. Frozen inputs keep their labels, and the source stays
    cited. The old names are at tag `bitsey-names-frozen-2026-11-12` (`67f9c43`).
  - Tier 1 + 2 gate: 355 files, no changed outcome, no OOM kill
    ([gate](/mnt/workspaces/Cells/land-20261112d/)).
  - BITSEY declares no licence, so its code may not be copied.
  - **Open:** the classification of `processes/source_electrochemistry.py` (the user's
    decision); BITSEY's species names and the `source_*` names; moving the five
    `scripts/capture_*` tools into `validation/bitsey/`.
  - Evidence: [audit and identity](/mnt/workspaces/Cells/bitsey-rename-20261112-01/),
    [tests after the rebase](/mnt/workspaces/Cells/bitsey-rename-20261112-02/).

- **Current injection: first acceptance passed (Rm1 on the uncleaved egg against R-full;
  12 November).** Engine models: `resolved_pump_composite@1` over `resolved_pump_tissue@3`
  with `electrode_current_injection@1`.
  - **Definition:** R-full's own uncleaved egg (its `build()` from
    `j1_declared_inputs.json` with the record's P_old), written as `@3`; J1's pulse protocol
    (±30 nA for 1.2 s every 10 s, K 0.4912 / Cl 0.5088); J1's Rm rule on pulses 0 and 1.
    Every field matches R-full's egg; the declared differences are activities used as
    concentrations, N_A·e against F (3.4e-11) and a 1.3e-16 volume rounding.
  - **Development dt study** (seen before registration): Rm1 is 852298.5 Ω at 1 ms and
    852073.9 Ω at 0.5 ms against R-full's 852000.0 Ω. The error is second order (ratio
    4.04) and extrapolates to within about 1 Ω of R-full.
  - **Registered** in
    [`injection_rm1_protocol.json`](validation/tissue/injection_rm1_protocol.json): pass
    when |Rm1(1 ms) − 852000.0 Ω| ≤ 3 × (step term 224.58 Ω + reference term 1.7e-6 Ω) =
    673.74 Ω. The judged run happens once, from a clean snapshot of main.
  - **Judged run: pass.** Rm1 = 852298.5 Ω, +298.5 Ω against the 673.74 Ω tolerance,
    from a clean snapshot of main at `2aa2793` (CPU 5, no OOM). It equals the 1 ms
    development run bit for bit, as expected on CPU.
  - Evidence: [development](/mnt/workspaces/Cells/composite-v2-20261112-01/rm1-dtstudy/),
    [judged](/mnt/workspaces/Cells/composite-v2-20261112-01/rm1-judged/judged.json).

- **Combined landing: the plan-validation fix, composite v2 §1.2–§1.4, the L4 agreement
  driver, `electrode_current_injection@1` and the J1 diagnostic code (12 November).** One
  tier 1 + 2 gate on the combined tree: 355 files, no changed outcome, no OOM kill
  ([gate](/mnt/workspaces/Cells/land-20261112b/)). New test files measured into the tier
  record: four in tier 1, `test_current_injection_runs.py` (81 s) and
  `test_division_diagnostic_record.py` (30 s) in tier 2, and the ring-model record test
  (about 150 s) in tier 3.
  - **Plan-validation fix.** `bind_step_checks(spec)` binds `resolved_pump_tissue@1`–`@3`'s
    step checks to their definition. The observation boundaries, the explicit, calcium and
    junction bounds, and the gated RK4 laws are evaluated once per definition rather than
    once per 1,024-step chunk; `core.grid.clock_checks` gives `checked_grid` and the
    projective clock admission the bound checks with no control tables. Other models keep
    `check_steps` per chunk.
    - Refusals, messages and their order are unchanged; the traced step, layouts, initial
      states and controls hash identically.
    - The 825-node clock check drops from 59.6 CPU-min to 6.9 s; on the L4 the W1 probe's
      plan validation takes 106 s.
    - All 29 related files pass at the fix head, the composite's tier-3 files included
      ([evidence](/mnt/workspaces/Cells/clock-validation-20261112-01/summary.json)). One
      failure, `test_numerical_refinement.py::test_legacy_hash_and_empty_omission` (a
      fingerprint literal), also fails on main before the fix; the tier record times that
      file out, so it carries no outcome.
    - **Open:** the composites (water `@1`, `@2`, replacement `@1`) still check per chunk,
      with 5, 6 and 2 layout builds; `pump_composite` adopts binding next (v2 §1.1).
  - **Composite v2 §1.2–§1.4 (D143).** Operators declare `REPLACES`, `VIEW_READS`,
    `ACCEPTS_WRITES` and `EVENT_REPLACES`, checked at registration and at composite build:
    writers follow the owners that accept their fields, view readers follow providers, and
    each observation column has one owner. Replacement is a declared chain in operator
    order, the last replacer owning the column; the reviewed one-replacer rule would have
    refused water@2 as qualified. Returned columns are checked against the declaration on
    every row, and the field-to-owner map is written to all three manifest writers.
    - Guards against snapshot `8416a72`: jaxprs 36/36 and 78/78 and bindings 12/12 and
      56/56 identical; 17 dumped worlds bit-identical; composite test files 59/59 and the
      frozen models' own files 130/130.
    - Not yet enforced: free-energy booking by events and split parts (needs §1.1).
      `ACCEPTS_WRITES` and `VIEW_READS` have no production user yet.
  - **L4 agreement driver** (`validation/tissue/composite_l4_agreement.py`). It runs each
    qualification's own engine functions (W1, W2, G2-Q1), measures the backend and
    run-to-run terms and writes PROPOSED variant protocols with the widening and stop
    rules. CPU dry runs give zero terms and the registered tolerances unchanged. Judged
    runs of G2-Q1, W1 and W2 now accept only the registered protocol or a registered
    backend variant of it. The L4 runs wait for the GPU.
  - **`electrode_current_injection@1`.** A scheduled current into a cell through declared
    carrier fractions (K 0.4912 / Cl 0.5088), both polarities, separate supply and removal
    bookings, and refusal when a cell cannot supply a carrier. It is split around the step
    (not coupled into RK4, so stationary analyses exclude it), and borrows the replacement
    law's free-energy terms until §1.1. Not yet accepted; its first acceptance (Rm1 on
    R-full's uncleaved egg) lands next.
  - [Composite evidence and log](/mnt/workspaces/Cells/composite-v2-20261112-01/HANDOFF.md).

- **Cell division S0b: J1 diagnostic arms on R-full. No single arm gives both J1's level
  and the registered time course; cause not isolated (12 November; development, not judged).**
  - **What ran:** the arms registered at `cfe0fa3`
    ([rationale](validation/division/j1_diagnostic_arms.md)), on R-full only, from a clean
    snapshot of branch commit `556b5eb` (merged with this entry). 3.9 CPU-hours in detached
    units on CPU 5, plus a one-point Radau check; every unit exited 0.
    [Evidence](/mnt/workspaces/Cells/cell-division-s0b-20261111-01/j1-diagnostic-01/):
    `g1/` (A1, A2, A4, A7a, A7b), `a3/`, `a6/`, `radau_check/`.
    - No engine run, and no C1 or J2 quantity. The only root searches are each curve's
      A/L → 0 end and A6's fits to each arm's own Em2 and Rm2; nothing targets J1's Em.
  - **Em at J1** (window −21.9 to −18.7 mV; record −12.795 mV, reproduced to 2.3e-12 V).
    Every calibrated point recalibrates on Rm1 and Rm2, so Rm at J1 is 488.00 kΩ throughout.

    | Arm | Em at J1 (mV) |
    | --- | --- |
    | A1 bath-facing fraction f, 0.01 to its end (0.0728) | −16.9 to −36.1 |
    | A2 furrow-zone conductance, to its end | −12.4 to −9.9 |
    | A3 ring lumen, calibrated (N = 1, 10, 20; w and bridge ranged) | −12.76 to −12.86 |
    | A4 old-membrane P_Cl/P_K, 0.03 to 0.12 | −12.6 to −11.9 |
    | A6 new-membrane rules and fits (all 14 fits converged) | −12.4 to −15.2 |
    | A7a access scaled with furrow depth, α 0.5 to 2 | −12.80 to −12.84 |
    | A7b late apposition, β 0.8 to 0.4 | −12.78 to −12.79 |
    | A8 (computed earlier) | −12.6 to −16.5 |

  - **A1 alone crosses the window**, at f ≈ 0.015–0.024 by interpolation. The curve is
    monotone from −13 to −36 mV at one Rm, so the crossing was expected and selects
    nothing; no f is adopted. Near it Em is still falling at J1 (D4 −0.05 to −0.08 mV) and
    Rm has no late rise (D7 −0.2 to −0.6 kΩ), against the registered p531 description.
  - **A7a is the only calibrated arm with a late Rm rise** (D7 +64, +130, +224 kΩ at α 0.5,
    1, 2), with a deeper, later Em minimum (8.7–9.7 min). Rm2 fixes the access at J1, so
    A3, A7a and A7b stay within 0.07 mV of the record there.
  - **Shared by every calibrated arm:** the Rm fall is front-loaded (D5 0.85–0.94, except
    A1 from f 0.03 and A2 from half its end); the Em minimum comes at 7–10 min; cytosolic
    Na at J1 is 20.0–20.2 mM against the measured 22.4 ± 1.1 mM.
  - **Without a rim restriction** (the geometric-access check) Rm at J1 is 104–108 kΩ,
    4.5–4.7× below Rm2. Its N = 10, w = 2.5 µm point **failed** (integration failure at
    insertion onset, 420–421 s); it is recorded in `a3_final.json` and not rerun.
  - **Fig. 2 values**, read after the runs from one egg and not registered targets: D2 ≈
    −10 mV, D3 ≈ 15 min and −19.5 mV, D4 ≈ +2.5 mV, D5 ≈ 0.46, D6 ≈ 0.64, D7 ≈ +80 kΩ.
  - **Deviations from the registration:**
    - A3 used BDF with a batched finite-difference Jacobian, not a declared sparsity
      pattern; the Radau check on the N = 10 default point agrees to 2e-13 V.
    - A3 used two undeclared numerics: a 1e-11 m² seed face per ring and a 1e-12 mM
      concentration floor in the log-mean flux.
    - The snapshot is of the branch commit, not main.
    - A1's curve ends at f = 0.0728 (root search), not the estimated 0.10.
    - The Radau check ran from a driver in the evidence folder; it is now the runner's
      `radau-check` group, not rerun.
  - **Code:** `validation/division/cleft_egg_reference.py` (extended; the null path is
    unchanged), `cleft_rings_reference.py` (A3), `j1_diagnostic_runner.py`; tests
    `tests/unit/test_division_diagnostic_*.py` (11 + 2 + 1 pass).
  - **Next:** the cleft-model choice is the user's (a registered combination round,
    freezing candidates for C1, or parking it). C1 and J2 stay held.

- **Heredity pilot W1, water arms: held discs also hold under water; the osmotically
  balanced start, not water itself, makes the marginal loss 3× earlier (11–12
  November; development, not judged).**
  - **What ran:** the sheet70 discs under `resolved_pump_water@1` and `@2` (KCC at
    red-cell capacity 4, s 1), dt 5 ms, plus a water-off control.
    - Predictions were written first.
    - There were no refusals and no volume censors.
    - The four arms killed by the 12 November crash were rerun.
    - [note](/mnt/workspaces/Cells/heredity-pilot-w1-20261110-01/sheet70w/NOTE-water-sheet-results.md),
      [summary](/mnt/workspaces/Cells/heredity-pilot-w1-20261110-01/sheet70w/summary-sheet-arms.json)
  - **Retention is as in fixed volume.** In both water models, 37-cell discs held 70 min
    at s 1.0, 0.6 and 0.3, and 19-cell discs held at s 0.6 and 0.3.
  - **The 19-cell disc at s 1.0 was lost at 345–348 s after the cue**, against 990.5 s
    in fixed volume (5 ms runs, 1 s records).
    - **Re-timed at 1 ms (12 November):** water1, water2 and the water-off control lose
      the disc in the same 1 s brackets as at 5 ms (347–348, 345–346 and 304–305 s), with
      per-cell Vm within 0.02 mV before the loss. Fixed volume at 1 ms lost it at 990.46 s,
      so the shift is 2.85× (water1) and the water-dynamics effect +14.1%. Snapshot
      `source-w1a-02` (`f42eaa4`);
      [comparison](/mnt/workspaces/Cells/heredity-pilot-w1-20261110-01/sheet70w/retiming-1ms.json).
  - **The cause is the start state.**
    - The declared heredity H is hypo-osmotic, 284 against 300 mOsm.
    - Under water each cell starts at its model's balanced stationary H: 0.942 V0, 1.7 mV
      more polarised, K 144 rather than 136 mM.
    - The water-off control (balanced start, `@3` at fixed volume) lost the disc at
      304–305 s.
    - So water dynamics move the loss by only about 14%, and the +1% swelling before the
      loss slightly delays it.
  - **Loss account, refined.**
    - Every disc loads Na after writing, from 6 to 10–11.6 mM by about 10 min, and drifts
      more polarised.
    - Na load does not separate lost from held discs. The drift does: just before
      collapse the most depolarised cell sat near −27 mV in the lost discs, against −20
      to −23 mV in the held ones.
    - Candidate carrier: Na-driven drift together with a small disc and strong coupling.
      Untested.
  - **Water matters for slow composition and volume.**
    - Solute loading is the same in every model: 11.7–12.5% content excess at 70 min.
    - Under water it shows as swelling from 0.94 to 1.03–1.06 V0.
    - Disc K is 7–8.5 mM lower than in fixed volume.
    - KCC at capacity 4 is invisible over 70 min, but caps stationary D at 1.47 V0 instead
      of 1.76.
  - **Predictions** held as written, except two:
    - the marginal loss came earlier under water, a direction not predicted;
    - the control lost its disc at 304 s, against a predicted 330–370 s.
  - **For the E07-v1 redesign** (the user's decision):
    - start from a balanced H;
    - use water2 for hour-scale renewal, with water1 and a higher KCC capacity as
      robustness arms;
    - s 0.6 with a 37-cell disc is safe for retention, though pre-screen 8 found renewal
      failing at every coupling that retains;
    - turnover results are pending.
- **Composite tissue model landed (12 November; D143).** `resolved_pump_composite@1` is
  `@3`'s own step plus declared operators ([PUMP_COMPOSITE.md](docs/PUMP_COMPOSITE.md)).
  `resolved_pump_water@1`, `@2` and `resolved_pump_replacement@1` are now thin
  compositions; none had to stay frozen.
  - **In-tree guards, all bitwise equal:**
    - the empty composition equals `@3` (9/9 cases, and the 825-node world);
    - water test worlds 15/15; replacement 17/17;
    - W1's six judged trajectories, its stationary states and a 60 s drift;
    - W2's 8 arms;
    - G2-Q1's 9 cases with device checks on every row;
    - W37; Q5 (2 step sizes); Q6 cohorts.
  - **Cross-revision guards** (frozen `8416a72` against the converted tree):
    - jaxprs with dt traced: 36/36 on the base worlds, 69/69 on the qualification worlds,
      78/78 at the head;
    - bindings at every step size used;
    - W2's judge on all 8 arms identical;
    - 17/17 saved runs bit-identical;
    - the frozen models' own tests, unmodified, 130/130 against the thin modules.
  - **Step studies:** W1's dt study and 6 of Q5's 8 worlds were not rerun. The argument
    for equality (dt-traced jaxprs, with bound shapes and bindings checked at every step
    size) is written into the evidence README with its limits.
  - **Gate:** tiers 1 and 2 at `3f7d93e`, 349 files, none changed. The composite's
    identity, water and replacement files are tier 3: 12–23 min each, and they need more
    than 3 GB in one process.
  - Integration grants no new acceptance. GPU agreement by tolerance is pending.
  - Evidence: `/mnt/workspaces/Cells/composite-s1-20261111-01/README.md` and
    `land-composite-20261112-01/`. Landed at `54a2ea0`.
- **Plan-validation fix accepted on the L4; full-tissue hold segment 1 started (12 November).**
  - **The fix:** `bind_step_checks(spec)` evaluates `@1`–`@3`'s definition-only
    step-check quantities once per definition, not once per 1,024-step chunk. The
    definition stays unchanged, and the traced code hashes identically before and after.
  - **On CPU,** the 825-node clock check drops from 59.6 min of CPU to 6.9 s:
    - layout builds from 8,240 to 2;
    - control tables from 4,120 to 0.
  - **The acceptance probe on the L4** (from `source-09`, main `efa8267` plus the fix,
    into `fulltissue-v2/`):
    - start, prepare and probe all exit 0;
    - the probe wrote 10 windows, with all six worlds at t = 8 s and no failed check;
    - plan validation took 106 s, against a 40+ min stall before; compile 210 s.
  - **Segment 1** (1,200 s of model time, snapshots every 300 s) has run from the same
    snapshot since 18:39.
    - The measured rate is 11.1 s per 200-step window of six worlds. That projects to
      about 18.5 h per segment and about 65 h for the whole hold on the L4.
    - GH200 arrives next week. Each 300-s snapshot is a point to reassess.
  - **Open findings:**
    - `run.json` reports 0.41 ms per batch step against 55 ms seen, so the per-window
      wall lies outside every recorded timing;
    - `experiment.changes` is recomputed on every access, at 13.6 ms each;
    - the composite and the models that wrap `@3` still rebuild per chunk. Their owner
      adopts the fix.
  - The fix lands after a rebase onto the composite.
  - Evidence: `/mnt/workspaces/Cells/clock-validation-20261112-01/summary.json`.
- **Out-of-memory crash and relaunch (12 November).**
  - **Cause:** at 01:36:13 UTC the composite S1 guard on the water@2 qualification
    worlds was 8.2 GB resident, mid-compile. It set off a machine-wide out-of-memory
    kill. systemd then stopped the whole terminal-session scope that held it, and with
    it the lead session, its agents and every detached job (setsid does not leave the
    cgroup). Nothing ran from 01:36 to 12:30.
  - **Cut short:** outputs are kept with the suffix `.killed-oom-20261112`.

    | Work | State at the crash |
    | --- | --- |
    | W1 water sheet arms | 8 of 12 finished. Killed: `water2-disc37-s0.6` at t = 4080 of 4200 s, and `water1-disc19-s0.6` and `water2-disc19-s0.3` about 30 min in. `water2-disc19-s0.6` never started |
    | W1 full-tissue cost probe | Started 23:25. It wrote no window in 2 h 10 min, against a measured 482 s compile at 64 worlds, so it never finished; cause unknown. The first segment never started |
    | Turnover pre-screen | 3 of 21 arms finished. 2 were killed and 16 never started |
    | J1 band | 4 of about 24 members done: the default and 3 one-at-a-time members, −12.67 to −12.89 mV |
    | J1-state step study | RK4 0.05 ms, rfull and compare missing |
    | 35-min egg smoke | Never started |
    | Composite S1 guards | `w2` killed; `scale` killed |

  - **Fix:** [`scripts/run_detached.sh`](scripts/run_detached.sh) runs each long job as
    its own systemd user unit in `cells.slice`.
    - Each unit has its own memory cap, and the slice caps the total at 16 GB.
    - `OOMPolicy=continue` keeps a queue going past one killed item.
    - A positive `OOMScoreAdjust` makes a Cells job the victim before the user's other
      services.
    - Tested: a unit over its cap is killed alone.
    - Subagents' long test runs go through it too.
  - **Relaunched from zero:** same snapshots and arguments; the new launchers record
    why. The band and the longsheet part have no resume.
    - The J1 band ([`queue_rerun.sh`](/mnt/workspaces/Cells/cell-division-s0b-20261111-01/rfull-band-01/queue_rerun.sh), CPU 5).
    - The J1 step-study remainder, then the smoke ([`queue_j1_rest.sh`](/mnt/workspaces/Cells/cell-division-s0b-20261111-01/static-cleft-steps-01/queue_j1_rest.sh), CPU 7).
    - Water queue A ([`launch6.sh`](/mnt/workspaces/Cells/heredity-pilot-w1-20261110-01/launch6.sh), CPU 0).
    - The composite `w2` guard alone, with 11 GB, to measure its peak.
  - **Started at 13:01**, after the `w2` guard passed with an 8 GB peak:
    - water queue B;
    - the turnover remainder ([`arms-rest.sh`](/mnt/workspaces/Cells/heredity-turnover-literature-20261111-01/arms-rest.sh)
      with `queues-rest.json`; `queues.json` unchanged);
    - the cost probe alone, with a 45-min limit and Python's fault handler.
  - **Finished by 13:00:** the J1 band, its arms and time course; the step-study
    remainder; the 35-min smoke (see the S0b entry below).
  - **Cost probe diagnosed: an engine performance bug, not a GPU hang.** Rerun alone on
    CPU 6 from 13:01, it again wrote no window. At 40 min a SIGABRT dumped its stack
    ([log](/mnt/workspaces/Cells/heredity-pilot-w1-20261110-01/logs/ft-costprobe.log),
    exit 134).
    - It sat in host-side plan validation. `_validate_window_plan` checks the whole
      declared clock, 4218 s at 1 ms, in chunks of at most 1024 steps.
    - For each chunk, `check_steps` recomputes bounds that depend only on the definition,
      through `initial_values`, which includes the 825-node field bind.
    - An engine fix, computing those bounds once per definition with no numerical change,
      is in progress. The GPU segment waits for it.
  - **A further fix:** the step study's `compare` part had written the J1 comparison over
    the activation one, because it used one file name for both starts.
    - Both are kept now: `compare.json` was regenerated from the same snapshot and inputs,
      and the J1 result is `compare_j1.json`.
    - The driver now writes one file per start (`45fc727`).

- **Cell replacement qualified and landed (11 November).** `resolved_pump_replacement@1`
  is an opt-in wrapper over `resolved_pump_tissue@3`.
  - **What it does:** scheduled newcomer events with waste and supply ledgers and
    lineage, with the literature-based delayed junction-formation law, and both
    newcomer kinds (isolated template and donor copy, D139).
  - **Judged run G2-Q1:** one run from a clean snapshot of `81d5de7`, with protocol and
    predictions byte-equal to main `2cd2b3a`
    ([evidence](/mnt/workspaces/Cells/cell-replacement-g2-20261111-01/qualification/judged-01/README.md)).
    All 7 items pass:

    | Item | Result |
    | --- | --- |
    | Ledgers | Worst energy residual 9.8e-7 of flows |
    | Event map against an independent operator | 0.0041 of tolerance |
    | Trajectories against an independent reference | 0.44 of tolerance, as second order predicts |
    | Fast-chain end states | Identical in all six cases |
    | Order | 2.05 and 2.07 (amendment A3) |
    | Restart and vmap | Bitwise, or within 9.5e-15 |
    | 825-node no-event equivalence | Bitwise |

  - **Caveats:** in Q4 only the end states discriminate, because the voltage ratio is
    1/3 by construction. Q5 mostly measures a newcomer relaxing on its own.
  - **Limits:** in-place swap only (no vacancy); the donor copy does not halve the
    parent; the water inner model and finite extracellular worlds are stage 3.
  - **Gate:** tier 1+2 from a clean snapshot of the merge `2f372c5` (337 files) changed
    one file, `test_betse_tissue_contact.py`. Its BETSE reference refused to start for
    lack of its 4 GiB disk reserve while the workspace disk was full. Rerun from the
    same snapshot after space was freed, it passes as recorded (16 passed, 1 skipped).
    The tier-3 and new files pass in full. The tier record adds the two new files
    (271/66/196, with `test_cell_replacement_vector.py` in tier 3: 85–101 s against the 90 s cap).
- **Parity on the L4: variants registered (11 November).** None of the 12 P2–P4b
  protocols allowed a GPU run, so each has a registered L4 variant built by
  `validation/betse/backend_variant.py`
  ([evidence](/mnt/workspaces/Cells/parity-l4-20261111-01/)).
  - **CPU against L4:** Vm up to 1.1e-14 V and cell ions up to 1.9e-13 relative.
    Bitwise CPU reruns confirm this is the backend alone.
  - **L4 run to run:** Vm up to 6.5e-16 V and cell ions up to 1.0e-14 relative.
  - Both terms are at least 1e5 below every tolerance, so no tolerance changed.
  - **Rehearsal:** a full-size run of the judged chain on a non-registered case passed
    (worst 0.60 of tolerance; not a verdict).
  - **Judged L4 runs: all 12 pass (11 November, 21:18–22:40 UTC).** Each protocol ran once
    from a clean snapshot of the registering commit `25d0fe9`, host on CPU 6
    ([margins](/mnt/workspaces/Cells/parity-l4-20261111-01/judged/margins.json)). All 24
    run and compare steps exited 0, and none was refused.

    | Protocol | Worst, fraction of tolerance |
    | --- | --- |
    | P2 stage 1 | 0.996 (cell K, as on CPU) |
    | P2 direct | 0.30 |
    | P3, four cases | 0.27–0.29 |
    | P4 | 0.29–0.31 |
    | P4b | 0.35–0.48 |

    - **Status line:** the registered variants differ from the drafts only in their status
      line. The drafts are kept beside them.
    - **What this establishes:** every parity rung so far now passes on CPU and on the
      L4.
- **MG1 qualified and landed (11–12 November).** `apical_vertex_mechanics@1`,
  `mechanical_equilibrium_analysis@1` and `junction_tension_inference@1` passed protocol
  v2.
  - **Judged run:** 57 of 57 criteria, run once (judged-02, 20:27–22:42 UTC) from a clean
    snapshot of `840488e`
    ([results](/mnt/workspaces/Cells/morphogenesis-mg1-20261111-01/judged-02/results/results.json),
    [margins](/mnt/workspaces/Cells/morphogenesis-mg1-20261111-01/judged-02/margins.json)).
    Re-judging the saved results reproduces the verdict.
  - **Weaker evidence by its own rules:** v2 follows the failed judged-01, and values were
    seen while diagnosing it (disclosed in v2).
  - **Tightest margins:**
    - the barrier vanishes at p0 = 3.82, 0.0081 above the window's 3.8119 lower bound;
    - Euler order 0.998;
    - I3 slopes 0.997–1.002 (noise 1e-9 to 1e-7);
    - small-cut recoil slope 0.999.
  - **Other values:** rigidity vanishes at p0 = 3.7224 for every r; 144 barrier paths, none
    failed (max |F| 9.8e-12).
  - **Gate:** tier 1+2 from a clean snapshot of the merge `90ceec5` (337 files) matches the
    record. The 9 new test files pass in full and enter the tier record (1 in tier 1,
    8 in tier 2; 272/74/196).
  - **Process slip, disclosed:** the merge was pushed at about 23:00 UTC together with
    J1's registration, before this gate finished at 23:48. The gate then passed with no
    changes, so nothing was reverted.
- **MG1 v2 registered; judged run under way (11 November).**
  - **The two failures were diagnosed:**
    - The barrier crash was a genuinely flat landscape where a compatible start
      loses compatibility. It is fixed with a trust-region Newton step and a
      force-residual polish.
    - I3's registered noise range was past the linear regime.
  - **v2:** the same 57 criteria and thresholds. Its noise levels come from a
    reference-only study and a rule fixed in advance. It discloses what was seen during
    diagnosis, and a pass is labelled weaker evidence.
  - **Dry run:** a full-scale run on non-registered inputs passed (144 barrier paths,
    none failed).
  - **Timing, disclosed:**
    - v2 was committed on main at `699e96d` (20:25:59 UTC);
    - the judged run started at 20:27:57 from a clean snapshot of `840488e`, which
      contains it (empty patch; protocol bytes equal main's);
    - the commit was pushed at about 21:17, after the run began.
- **Cell division S0b: J1 prediction of record and verdict; J1 fails on the reference (12 November; development).**
  - **J1's declared inputs** were registered at `d7a1797` before any model computed an
    Em.
  - **The reference:** R-full, an independent numpy/scipy model of the egg with its
    restricted cleft (`validation/division/cleft_egg_reference.py`; 17 tests pass).
    - It calibrates the old membrane on pulse Rm1 = 852 kΩ and the cleft access on pulse
      Rm2 = 488 kΩ.
    - It predicts **Em = −12.795 mV** at onset of second cleavage, under the defaults.
    - The prediction was committed at `7c1b70c` before any band member ran
      ([record](validation/division/j1_prediction_of_record.json)).
  - **Against the data:** the measured value is −20.3 ± 0.8 mV, so the default sits 7.5 mV
    (9.4 SE) above it.
  - **Verdict, 12 November: J1 fails on the reference (R-full) within the declared
    ranges.** There is no engine run yet, and the cause is not isolated
    ([verdict](/mnt/workspaces/Cells/cell-division-s0b-20261111-01/rfull-band-01/results/j1_verdict.json);
    declared inputs unchanged since `d7a1797`).
    - **The band:** one-at-a-time members, summed worst case, corners checked. It runs
      from −14.58 to −11.32 mV.
    - **Width:** W = 3.26 mV, with t = 0.18 µV. That is inside the 8-mV maximum, so J1 is
      judged.
    - **The miss:** the band lies wholly above the datum's ±2 SE window of −21.9 to
      −18.7 mV, and misses it by 4.1 mV.
    - **Largest shifts:** the new membrane's P_Na/P_K (0.42 mV) and the Rm2 and Rm1 targets
      (0.37 and 0.33 mV). No corner falls outside the summed band.
    - **In R-full at J1:** the lumen holds 29 mM K, against 0.55 mM in the bath, and
      21 mM Na, against 47 mM. The K potential across the new membrane is about −14 mV.
  - **Arms and limits (reported, not banded):**

    | Case | Em (mV) | Rm (kΩ) | Measured |
    | --- | --- | --- | --- |
    | Cation-selective rim | −16.5 | 488 (calibrated) | – |
    | Constant-field access | −12.6 | 488 (calibrated) | – |
    | 0.5 µm gap | −12.7 | 488 (calibrated) | – |
    | Bath-equivalent lumen (limit) | −69.4 | 125 | – |
    | Sealed lumen (limit) | −9.9 | 852 | – |
    | Exposed arm −VM | −54.4 | 309 | −60.0 ± 2.5 mV, 336 ± 31 kΩ |
    | Exposed arm +VM +CCB | −61.4 | 199 | −60.9 ± 3.4 mV, 165 ± 10 kΩ |

    - The exposed arms are the data the new-membrane rules came from, and they do not
      fit cleanly: +VM +CCB Rm is 3.4 SE from its mean, and −VM Em 2.2 SE.
    - Cytosolic Na at J1 is 20.1 mM; dL74 measured 22.4 ± 1.1 mM.
  - **What it means:** the declared model as a whole misses J1. Which assumption is wrong
    is not isolated.
    - The measured Em lies between two readings of the same Rm 488 kΩ. All new membrane
      behind a restricted lumen gives −12.8 mV; a bath-exposed patch gives −37 to −44 mV.
      A mix of the two can reach −20.3 mV, so a match alone proves nothing.
    - dLB74's 0.14 mm² "exposed to the outer medium" (p535) is not independent evidence.
      It is calculated from the same Rm series (1148 ± 104 kΩ, n = 17, the parallel
      reading of Rm2) as the bath-exposed reading.
    - The declared assumptions with independent evidence against them in the papers:
      - a uniform, constant old membrane; K83 measures 4–30 times more current in the
        old membrane beside the furrow;
      - a well-mixed lumen with one access path, for a furrow about 150 µm deep and
        2 µm wide;
      - no Ca²⁺ or Cl⁻ currents; K83 assigns old-membrane inward current to Na⁺, Ca²⁺
        and Cl⁻;
      - the new-membrane rules, given the exposed-arm misfit above.
    - **The time-course shape differs too** (reported, single traces). In R-full, Em
      steps to −15.2 mV at 8 min and then relaxes to −12.8 mV as the lumen fills with K.
      Rm falls mostly within 7–10 min (852 to 525 kΩ). dLB74 describes Em falling about
      10 mV gradually over 7–17 min, with Rm falling over the same period.
  - **Next (the user chose this with the advisor, 12 November):** a diagnostic on R-full.
    - The arm file is registered on main before any run. J1 is now a selection datum.
    - Each arm states its change, its source and what is recalibrated.
    - An arm that adds an unknown with no measurement of its own is reported as a curve
      of Em against that unknown at fixed Rm. No value is picked from Em.
    - Arms are compared on the time-course shape as well as on Em at J1.
    - No model computes J2 until a revised model is frozen. The revision comes back to
      the user with the results.
    - Composite S1 and the division operators continue unaffected.
  - **Rerun check:** the four band members finished before the crash were recomputed on
    the rerun and agree to every printed digit.
  - **Static cleft egg as a plain `@3` definition:**
    - **1 ms is refused** by @3's explicit-rate bound (dt × rate = 1.145); 0.5 ms and finer
      are accepted. The division work therefore needs about 0.5 ms or an implicit
      membrane–cleft term.
    - **Energy ledger:** with the whole 1.39 mm² patch switched on uncharged at once,
      the energy ledger fails at IMEX 0.5 and 0.25 ms (37% and 6.9% of flows) and nearly
      closes under RK4 at 0.1 ms. Whether gradual insertion stays within the bound is
      pending.
    - **From R-full's J1 state, over 2 s:** IMEX ARS(2,2,2) passes every check on every
      row at 0.5, 0.25 and 0.125 ms, and agrees with R-full to 3e-10, 1e-11 and 2e-12 V.
      The energy-ledger failure belongs to the switch-on transient.
    - **RK4 from the same state:** at 0.1 and 0.05 ms it agrees to 5e-13 V, but fails the
      electrode ledger on 19,511 and 38,761 rows (225 and 599 times its bound). This is
      consistent with the latent `@3` RK4 electrode rounding recorded on 11 November: the
      excess grows with the step count at the two step sizes run
      ([comparison](/mnt/workspaces/Cells/cell-division-s0b-20261111-01/static-cleft-steps-01/results/compare_j1.json)).
  - **Egg smoke to 35 min:** the uncleaved egg on `@3`, at IMEX 1 ms for 2100 s through
    the vector-window runner, is accepted.
    - Device checks passed on every row, and the worst ledger reached 5.3e-4 of its bound.
    - Wall time 228 s ([result](/mnt/workspaces/Cells/cell-division-s0b-20261111-01/smoke-35min-01/results/long.json)).
    - On a free core the band members took about 40 s instead of 8–17 min. Last night's
      long times were likely from sharing cores at nice 10 (not measured).
  - **Engine gaps:**
    - no current-injection control, so Rm cannot be run on the engine yet;
    - the explicit-rate bound at 1 ms;
    - the energy ledger in a stiff switch-on transient;
    - RK4 electrode-ledger rounding over long runs.
  - Evidence: `/mnt/workspaces/Cells/cell-division-s0b-20261111-01/`.
- **Cell division: design note (draft) and egg-scale smoke test (11 November).**
  [CELL_DIVISION_DESIGN.md](docs/CELL_DIVISION_DESIGN.md) answers D142. One composite
  pump-tissue model runs `resolved_pump_tissue@3`'s own step plus declared operators
  (water, replacement, division); new combinations are definitions, not model families.
  It is merged as a draft for review, before any model produced an Em for the first
  judged observable.
  - **Smoke test:** one Xenopus-egg-sized cell at rest, on `@3` and on
    `resolved_pump_water@1`, 60 s at 1 ms with host and device checks on every row
    ([evidence](/mnt/workspaces/Cells/cell-division-20261111-01/scale-smoke-01/)). It was
    accepted, with every ledger at most 1% of its bound; Vm −9.945 mV; fluxes equal an
    independent constant-field calculation to 8 digits.
  - **Scale:** the egg's volume is about 10⁶ times a heredity cell's, six orders of
    magnitude, not nine as first stated.
  - **Engine gaps found:**
    - `surface_tissue.check_definition` has an absolute 1e-20 C bound on the gap
      between the charge anchor and the inventory. An egg built like the heredity
      fixtures misses it by 1.2e-20 C, whereas one float64 step of its fixed background
      is 1.8e-19 C. It should scale with Σ|zFn|, as the running ledgers do. The same
      module also has an absolute energy floor (`ENERGY_ATOL_PJ`) to review. The fix
      lands separately, with the gate.
    - The pump-tissue family has no current-injection control. Rm must be the simulated
      response to dLB74's pulse protocol, because constant-field membranes rectify.
  - **Next (S0b, before any composer code):** an independent numpy reference of the
    cleft egg and J1's prediction of record; a static cleft-egg step study if it can be
    written as a plain `@3` definition; the pulse-response Rm; the smoke test to 35 min.
- **Cell division, stage 1 (11 November).** Verified data for the
  [cell-division plan](docs/CELL_DIVISION_PLAN.md) (D141):
  - Xenopus goes first;
  - the first judged observable is blastomere Em at 2 and 4 cells, with Rm from the
    same eggs as calibrator;
  - new cleavage membrane is low-resistance and mainly K-selective.

  Evidence: `/mnt/workspaces/Cells/cell-division-20261111-01/verification/`.
- **Heredity pilot W1, water arms (11 November; development, in progress).** The
  sheet70 discs are rerun under `resolved_pump_water@1` and `@2`, with predictions
  written first ([runs](/mnt/workspaces/Cells/heredity-pilot-w1-20261110-01/runs.jsonl)).
  - **Three of 12 arms done:** the 37-cell disc held for 70 min at s 1.0 (water, and
    water with KCC) and at s 0.3, with no refusal and no volume censor.
  - **Swelling:** disc cells swelled to 1.03–1.06 V0, about 12% over their start.
    Solute loading matches fixed volume, now taking the form of swelling.
  - **KCC effect:** small, as predicted.
  - **Running:** the 19-cell discs at s 1.0, under both water models.
- **Workspace disk (11 November).** `/mnt/workspaces` filled, which is what blocked the
  BETSE test above. At the user's direction, the AI scientist project folder
  `groups/35` (564 GB, 49,589 files) moved to
  `/mnt/datasets/workspaces-archive-20261111/groups/35`, leaving a symlink. It was
  checked file by file
  ([log](/mnt/workspaces/Cells/disk-move-20261111-01/move.log)), and 523 GB is now
  free.
- **Heredity pilot W1: the cue writes discs; fresh discs hold for 70 min (10–11
  November; development, not judged).** Driver `validation/tissue/heredity_pilot.py`
  on `resolved_pump_tissue@3`; evidence `/mnt/workspaces/Cells/heredity-pilot-w1-20261110-01/`.
  - **The cue:** an added Na leak at 9× each disc patch's leak for 2 s, through the
    engine's channel availability schedule. No engine gap.
  - **Full 825-node heterogeneous tissue at s 1.0 (replay):** 19- and 37-cell discs
    were written within 0.4 s and stayed fully D through the run, with no D outside.
    The default @3 refuses the cue step (junction-heat refusal, below). The
    opt-in junction-heat booking accepts it, with the energy ledger closing to about
    1e-7 of flows.
  - **Held-bath 127-cell sheet, cue-written discs, 70 min at dt 5 ms** (six arms,
    none refused, no D outside any disc;
    [summary](/mnt/workspaces/Cells/heredity-pilot-w1-20261110-01/sheet70/summary-six-arms.json)):
    - **Five held to 70 min:** 37 cells at s 1.0, 0.6 and 0.3, and 19 cells at s 0.6
      and 0.3.
    - **The 19-cell disc at s 1.0 was lost all at once,** 990.46 s (16.5 min) after
      the cue in a 1 ms replay, inside the 5 ms run's bracket. All 19 cells went to
      H within 0.12 s; no check failed and no step was refused.
    - **Before the loss it was drifting toward U, with K and M not loading** (Na
      loaded to 11.6 mM). Just before collapse its Vm was about −32 to −27 mV, with
      K 134.6 and M 11.2 mM (content excess 2.7–3.1%). A range of −37.8 to −30.6 mV
      quoted here earlier was sampled mid-collapse, 0.06 s before the first flip;
      corrected 12 November. The held discs had instead loaded to K about 146 and M
      about 22 mM by 70 min. So the loaded-composition limit from pre-screen 9 does
      not explain this loss; the small disc at strong coupling slid toward the
      unstable state before it could load. The mechanism is not yet identified.
    - **Predictions:** written beforehand, they predicted loss at s 1.0 for both
      sizes. The 19-cell prediction held; the 37-cell one was falsified.
    - **Osmotic excess** (against each cell's own start) passed 10% at 56–58 min in
      the held arms and peaked at 11.7–12.1% (censor 15%).
    - Held baths supply K without limit, so loading may be overstated.
  - **Control:** started from pre-screen 7's loaded disc with no cue, the driver
    loses the disc in 0.56–0.62 s, as pre-screen 7 does.
  - **L4 reproducibility:** runs on the L4 are not bitwise reproducible from run to
    run, with or without the junction-heat option (likely atomic scatter-adds).
    Bitwise restart on the GPU would need deterministic XLA ops, whose cost is
    unmeasured. One L4 refusal (pilot-03, 0.047 s) did not reproduce.
- **MG1 (2-D vertex mechanics) judged run: FAIL (11 November).** Protocol
  `mg1-vertex-mechanics-v1`, registered at `70f5456`. Run once on CPU from a clean
  snapshot of `db82f63` (the MG1 branch rebased on `70f5456`; empty patch; protocol
  bytes equal main's)
  ([results](/mnt/workspaces/Cells/morphogenesis-mg1-20261111-01/judged-01/results/results.json)).
  - **52 of 57 criteria pass:** the case-I ground state, the box stress, ordered-
    network rigidity, recoil after a junction cut, numerics (RK4 order about 4,
    Euler about 1), tension inference with known pressures, and the tyssue
    comparison.
  - **The barrier part failed** before judging: its contraction minimizer did not
    converge (`ConfigError`), so criteria B1–B4 have no values and count as failed.
  - **I3 (noise linearity of tension inference) failed** on its own values.
  - Per the outcome rules, thresholds are not changed. The causes are being
    diagnosed (development). Any rerun is a new judged run under a v2 protocol,
    with all 57 criteria, this run kept on record, and a pass labelled weaker
    evidence. I3's window will not be re-derived from engine output.
- **Osmotic water and volume qualified and landed (11 November).**
  - **`resolved_pump_water@1`:** osmotic water and compliant volumes on
    `resolved_pump_tissue@3`, through a Strang split around @3's own step.
    - With water off it is bitwise @3 on CPU (single cell, 7-cell sheet, 825-node
      tissue, vmap).
    - **W1 judge: 25 of 25 pass,** one run from `628a3d0`, against predictions P1–P6
      frozen from an independent numpy/scipy reference (`b0ff7e2`). Every trajectory
      sits at about 1/3 of its tolerance, i.e. the engine's own 1 ms step error. The
      engine converges on the reference at second order.
    - **Procedure:** the W1 tolerances were pinned on the agent's branch (`628a3d0`)
      before the run, but not publicly registered on main first. P5 is judged on
      volumes and concentrations only (its Vm is constant by construction), as
      decided before any judged result.
    - Predictions to compare later, not claims: with water, the heredity D state
      swells to 1.76 V0 (approved parameters).
  - **`resolved_pump_water@2`:** adds a KCC-type K⁺/anion symport
    (`k_anion_symport_mass_action@1`). Its stationary judge passed 24 of 24; D
    swells 1.1–1.5× instead of 1.76×.
  - **Global-charge bound:** the ledger now gets the per-step rounding allowance of
    the other running ledgers, with no trajectory change. Reduced sensitivity: a
    persistent supply-booking leak is caught only above about 2.5 eps × moved charge
    per step. Global-charge ratios recorded before and after are not comparable.
  - **Also:** an opt-in membrane-process hook in @3 (default off, unchanged), and
    volume blocks in `stationary_continuation_analysis@1` (existing IDs bitwise
    unchanged).
  - **Gate:** tier 1+2 from a clean snapshot of the merge (334 files, none changed).
    15 tier-3 and new test files pass in full.
  - **1 h drift of the D state** (3.6e6 steps at 1 ms, no refusal): volume moves by
    2e-16 pL, Vm by 4.3e-14 V and concentrations by 3e-14 mM. Every ledger stays at
    rounding (energy 7e-8 pJ).
  - Evidence: `/mnt/workspaces/Cells/water-volume-pump-20261110-01/` and
    `/mnt/workspaces/Cells/land-water-20261111-01/`.
- **In development on branches, not yet on main (11 November):**
  - **Cell replacement:** `resolved_pump_replacement@1` (G2), with a
    literature-based junction formation law (D139). Stage 1 is built and tested;
    the donor-copy template is being added.
- **Cortés-Poza (2026) Phase 0: reproduction with corrections and a plain baseline
  (11 November; tooling, D137, no Cells engine model).** The author's code at `2b53a08`
  (MIT) was run out of process, with the review's corrections and a plain
  bistable-chain baseline
  ([plan, Phase 0 results](docs/CORTES_POZA_2026_TEST_PLAN.md); evidence
  `/mnt/workspaces/Cells/cortes-poza-2026-phase0-20261111-01/`).
  - **Regeneration fidelity:** 1.00 only with the one-sided coded metric. Two-sided
    agreement is 0.63–0.93, below 0.95 in every run, and the plain chain recovers
    better.
  - **Full-model energy:** rises in 93% of steps, through the omitted dG/dt term.
  - **Memory switching curve:** a formula. Simulated, slow memory erases the
    patterns.
  - **Remark 4:** a 4× typo.
  - **Thresholds:** the nucleation and switching thresholds also appear in the plain
    chain.
  - **For Phase 1:** test bistability, pinning, nucleation and strength–duration
    switching in Cells against the plain baseline.
  - **Limits:**
    - N, seeds and grids that the paper does not give were chosen by us;
    - regeneration outcomes were identical across seeds, so each condition is
      effectively one trial;
    - the long-horizon controls used one seed;
    - the paper's figures were not seen.
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
  | nav-kleak: NaV1.2 + K leak at rest −21.2 mV (registered `f79cc30`; own order check fired, dt/100 terms) | pass | 0.475 (SIM ECM M) | 0.53 mV (2) | 0.39 µV (3) |

  - Each channel's effect over the observed error: NaV1.2 Vm 25 (INIT) and 3661 (SIM
    switch-on); Kir2.1 Vm 18 (INIT) and 1485 (SIM switch-on); cell Na and K 130–1800.
  - Formulation check first: Cells' `nav1p2_m3h_regularized@1`, `kir2p1_mh2@1` and
    `naleak_always_open@1` equal BETSE's classes to 5e-14 over −120…+60 mV (Cells
    uses the analytic limits where BETSE gives NaN at −25, −40 and −65.000123 mV).
  - INIT Vm sits at BETSE's own 10 ms step term (0.40 and 0.48 mV measured).
  - **Limits:**
    - **NaV1.2 voltages:** covered from 0 to −16.9 mV (h1), −27.9 to −34.2 mV (h2) and
      0 to −21.2 mV, resting at −21.2 mV (nav-kleak), which includes the heredity D
      state (−21.5 mV). Its lower window (−60 to −35 mV) and the unstable point
      (−39 mV) are not exercised.
    - **Kir2.1 voltages:** covered from 0 to −34.2 mV (h1, h2) and 0 to −91 mV
      (kir-h). kir-h rests at −91 mV, not at H; it passes −80 mV only on the way down
      in INIT, at BETSE's 10 ms steps.
    - **Kinetics:** almost untested. Only NaV1.2 h's lag enters (h2 SIM); τ_m and the
      Kir2.1 time constants are not tested.
    - CPU only, one geometry.
- **Latent RK4 electrode rounding in `resolved_pump_tissue@3` (11 November).**
  - **Where it shows:** under RK4, the electrode ledger integrates stage currents
    and does not see the rounding of large amount increments.
  - **When it trips:** in plain @3 increments stay small, so this is latent. After
    a whole-content swap in cell replacement, the gap random-walks past the bound
    (5.5e-24 against 2.2e-24 C in 51 steps).
  - **Not affected:** IMEX books the electrode from rounded states, so it telescopes
    exactly.
  - **Handling:** `resolved_pump_replacement@1` adds an allowance for replaced slots
    only. @3 itself is unchanged.
- **Known refusal in the pump family (10 November).** `resolved_pump_tissue@1`–`@3`
  refuse any step in which a junction's power falls by more than about 59%:
  ARS(2,2,2) books junction heat with weights (δ, 1−δ), δ = −0.707, so the booked
  increment goes negative and trips the strict dissipation check. It occurs at
  heterogeneous cue onsets (W1 pilot, 5.000→5.001 s) and on homogeneous sheets
  during disc loss. Stage powers are nonnegative analytically, so an in-step bound
  would never fire; that fix (option I) is withdrawn, and a single wrong-signed
  junction booking is never caught by the energy ledger.
  - **Fix landed 11 November (gap A):** an opt-in `"junction_heat_booking":
    "trapezoid_nonnegative@1"` on @3. Junction heat is booked as dt·(q_start +
    q_end)/2, with no extra field solve.
    - Default runs and fingerprints are unchanged. With the option, trajectories are
      bitwise the default's on CPU; only junction heat differs. The strict row tests
      are kept.
    - The cost is +0.45% on the L4 at 64 worlds.
    - With the option, the 5 ms collapse and the full-tissue cue step are accepted,
      with energy residuals of about 1e-7 of flows.
  - **Host-cost fix landed with it (gap B):** `held_controls` reads the schedule's
    change times once per call, so output is identical and the host overhead per
    world-step is gone.
  - **Gate:** tier 1+2 from a clean snapshot of `bd0a41d` (327 files, none changed).
    The tier-3 files touching @3 and the vector windows also pass, run in full
    (ledger rounding 41, @3 35 + 1 skip, device checks 45, junction heat 5, vector
    windows 8 + 1, v3 6 + 1).
  - **Seven E/C test files** (projective, projective runner, and five stationary-
    analysis files) were missing from the tier record, so the routine gate never
    ran them. All pass (47 tests) and are now in tiers 1 and 2. The new junction-heat
    test is in tier 3.
  - Evidence: `/mnt/workspaces/Cells/land-gapA-gapB-20261111-01/`.
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
