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
| 3 | Cells run of BETSE's default world, compared with step 1 (physical route, D131) | In progress |
| 4 | The same comparison on the L4 GPU | L4 path checks in progress |
| 5 | Further mechanism families from the parity ladder, on CPU and L4 | Planned |
| 6 | JUPITER environment and one-node pilot | Recipe and runbook ready; untested on site |

## Runs

Per-run summaries for this plan are added here, newest first, each linking its
machine-readable inputs, results, checks and failures.

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
  - **Pending condition:** the IMEX energy-identity checks use relative bounds
    (2e-3 ARS, 2e-2 Euler) instead of the family's absolute 2e-8 pJ. Neither
    scheme integrates the energy identity exactly; measured residuals are 3e-8 to
    4e-4. Approved on condition of a refinement check showing the residual falling
    at each scheme's order. The RK4 path keeps the absolute bound.

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
