# Progress

Last updated: 2026-11-08 UTC.

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
| 5 | Further mechanism families from the parity ladder, on CPU and L4 | Planned |
| 6 | JUPITER environment and one-node pilot | Recipe and runbook ready; untested on site |
| 7 | Stage B: neutral names; physiology stack moved to `validation/betse` | Planned (map ready) |
| 8 | Re-host the short decodability assays on Cells physics | G0 probe viable; channels next |
| 9 | First heredity experiment, E07-v1 ([design](docs/HEREDITY_FIRST_EXPERIMENT.md)) | Designed; user choices recorded in D133 |
| 10 | Morphogenesis track ([plan](docs/MORPHOGENESIS_PLAN.md); D134) | MG0 drivers in progress |

## Runs

Per-run summaries for this plan are added here, newest first, each linking its
machine-readable inputs, results, checks and failures.

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
