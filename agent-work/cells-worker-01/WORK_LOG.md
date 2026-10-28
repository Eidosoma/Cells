# Cells Key Developer work log

Owner: Cells Key Developer (`cells-worker-01`).
Task ID: `01a18248-236d-7563-be79-59a4e6007c02`.
Coordinator: Cells Chief Developer, task `01a0ba89-33fd-7c52-8dd5-ae4a9473b922`.

This file records this worker's assignments, changed files, checks and evidence
links. `PROGRESS.md` remains the project status record; coordinate project-level
updates with the Chief Developer instead of duplicating them here.

Task-specific working files belong in [workfiles/](workfiles/). Production code,
tests and validation changes use paths agreed with the Chief Developer. Record
the exact paths touched for each assignment and preserve other agents' edits.
Use selective Git staging if a commit is requested.

## Entries

### 2026-10-28 11:36 UTC — Repository orientation and workspace setup

- Read `AGENTS.md`, the project overview, current progress, architecture, BETSE
  coverage and GPU execution guidance.
- Reviewed model registration, scheduling, checkpoint checks, device routing,
  the mobile-pump/calcium/injury implementation and its independent reference.
- Identified existing shared edits to `PROGRESS.md`; this worker has not edited it.
- Created this worker-owned log and workfile directory at the user's request.
- No tests or simulation jobs were launched during orientation.
- Ready to receive scoped assignments through direct Codex task messages.
- Sent the Chief Developer a direct readiness message with this task ID, the
  worker-owned paths and the request to coordinate production file ownership.

### 2026-10-28 — Water/volume schema assignment

- Accepted [the Chief's assignment](workfiles/WATER_VOLUME_ASSIGNMENT.md).
- Exclusive implementation paths: `src/cells/core/surface_water_spec.py`,
  `tests/unit/test_surface_water_spec.py`, `configs/resolved_water_tissue.json`
  and this worker's directory. Shared dispatch, numerical code, independent
  reference and project status remain with their assigned owners.
- Sent ownership acknowledgement and the proposed dataclass/control interface
  directly to the Chief before implementation.
- Check policy: CPU 7, one BLAS thread, no GPU, target at most 1 GiB RSS;
  runtime evidence belongs under `/mnt/workspaces/Cells/water-volume-schema-20261028-*`.
- Implemented the strict `resolved_water@1` schema, immutable owner declarations,
  independent water controls, right-continuous union clocks and lossless ionic
  projection. The Chief confirmed this interface and owns numerical preflight
  in the production model's `check_steps`.
- Added the GPU-configured one-cell/one-finite-outside example and schema-only
  tests. No water trajectory or GPU computation was run by this worker.
- Changed files for this assignment: `src/cells/core/surface_water_spec.py`,
  `tests/unit/test_surface_water_spec.py`, `configs/resolved_water_tissue.json`,
  `agent-work/cells-worker-01/workfiles/check_water_schema.py` and this log.
- [Run result](/mnt/workspaces/Cells/water-volume-schema-20261028-01/result.json):
  **159 passed**, zero failures/errors/skips; pytest reported 2.27 seconds.
  Ruff checks passed. Peak child RSS was **183,271,424 bytes (174.78 MiB)**.
  The test process used CPU 7, single-threaded BLAS and CPU-only JAX routing.
- [Inputs and commands](/mnt/workspaces/Cells/water-volume-schema-20261028-01/inputs.json),
  [test receipt](/mnt/workspaces/Cells/water-volume-schema-20261028-01/tests.xml),
  [test log](/mnt/workspaces/Cells/water-volume-schema-20261028-01/pytest.log) and
  [lint log](/mnt/workspaces/Cells/water-volume-schema-20261028-01/lint.log) are retained.
  The result binds **183 source snapshots and 189 output hashes**; no source
  changed during the checks, and all four worker code/config hashes still match.
  Result SHA-256: `0618f02bcb6425acf31dadfeeb37e645b9f5eaaa24997c6d3603b310b762c0d9`.
- Reproduction entry point: run `workfiles/check_water_schema.py` with the CPU
  venv's `python -B`, affinity CPU 7 and a fresh assigned evidence directory.
  Shared-checkout whitespace checking also passed. No unresolved interface issue;
  ready for the Chief's dispatch and numerical integration.
- Sent the completed handoff, exact modified paths, evidence location, resource
  results and subclass-dispatch ordering reminder directly to the Chief.

### 2026-10-28 — Deferred numerical definition preflight

- The Chief requested the standard deferred production `check_definition` hook
  now that the water model and shared dispatch exist. Added the call after
  constructing the normalized spec, with arithmetic/value errors converted to
  `ConfigError` consistently with the base resolved parser.
- Added a regression for finite extreme hydraulic permeability whose derived
  area/unit-converted conductance overflows, both with ordinary water controls
  and with water blocked throughout. Kept timestep/union-grid validation with
  the Chief's `check_steps` implementation.
- Reusing the bounded parser runner in a fresh `water-volume-schema-20261028-02`
  evidence directory; the original run and source snapshots remain preserved.
- [Run result](/mnt/workspaces/Cells/water-volume-schema-20261028-02/result.json):
  **161 passed**, zero failures/errors/skips; pytest reported **2.51 seconds**.
  Ruff and whitespace checks passed. Peak child RSS was **183,496,704 bytes
  (175.00 MiB)**, on CPU 7 with single-threaded BLAS and CPU-only JAX routing.
- [Inputs](/mnt/workspaces/Cells/water-volume-schema-20261028-02/inputs.json),
  [test receipt](/mnt/workspaces/Cells/water-volume-schema-20261028-02/tests.xml),
  [test log](/mnt/workspaces/Cells/water-volume-schema-20261028-02/pytest.log) and
  [lint log](/mnt/workspaces/Cells/water-volume-schema-20261028-02/lint.log) retain
  the checks. The result binds **184 source snapshots and 190 output hashes**,
  with no source drift during checks and all worker code/config hashes matching.
  Result SHA-256: `1e06217279e6993e23714ebdf0ccf93b08a645a2580b65120172ed0d39acc72e`.
- This follow-up changed only `src/cells/core/surface_water_spec.py`,
  `tests/unit/test_surface_water_spec.py` and this log. No failed checks or
  remaining interface concerns; reported the completed hook and checks directly
  to the Chief. No further run was started.

### 2026-10-28 — Water execution and replay coding assignment

- The Chief assigned two additional exclusive files:
  `tests/unit/test_surface_water_execution.py` and
  `validation/tissue/surface_water_replay.py`.
- Implementing complete 16-field disk, fresh-process and terminal replay;
  future water-control branches; changed scalar/cohort windows; independent
  world partition/reorder; and offline planning for 1–16 GPUs.
- Reusing the existing sequential replay-worker and component-evidence patterns.
  Actual histories plus checkpoint state/layout/clocks are saved before
  comparisons, with exclusive artifact creation and phase failure receipts.
- Sent the Chief the planned protocol selectors and required `water-execution-`
  replay, worlds and planning reports. New lightweight host contracts also
  report definition/grid/layout and failed-comparison evidence retention.
- Extended the existing worker check driver with `--scope execution-contracts`
  to collect all five tests and run only host contracts/capture/planning.
  Compiled, GPU and trajectory tests remain unexecuted pending coordination.
- [Initial host-check failure](/mnt/workspaces/Cells/water-volume-execution-20261028-01/failure.json)
  retains the source, logs and XML: five tests collected and lint passed; the
  capture contract passed; two host/planning checks failed because the Chief's
  coupled/sealed fixture observation `0.0012` differs from the exact nominal
  boundary `12 * 1e-4 == 0.0012000000000000001`. Reported the concrete fix to
  the fixture owner without editing their file or changing numerical criteria.
- The Chief corrected constant-arm observation values to exact
  `i * STEPS[0]` boundaries and requested the same bounded host-only recheck.
  Recheck evidence uses the fresh `water-volume-execution-20261028-02` directory.
- [Recheck result](/mnt/workspaces/Cells/water-volume-execution-20261028-02/result.json):
  **five tests collected; three host/capture/planning tests passed, two compiled
  tests deselected**. Host pytest time was **44.06 seconds**, collection 1.12
  seconds. Ruff and whitespace checks passed. Peak child RSS was
  **190,894,080 bytes (182.05 MiB)** on CPU 7 / BLAS1 / CPU-only JAX routing.
- [Inputs and exact commands](/mnt/workspaces/Cells/water-volume-execution-20261028-02/inputs.json),
  [collection](/mnt/workspaces/Cells/water-volume-execution-20261028-02/collect.log),
  [test receipt](/mnt/workspaces/Cells/water-volume-execution-20261028-02/tests.xml),
  [test log](/mnt/workspaces/Cells/water-volume-execution-20261028-02/pytest.log) and
  the three host [component reports](/mnt/workspaces/Cells/water-volume-execution-20261028-02/evidence/cpu)
  are retained. The result binds **186 source snapshots and 219 output hashes**;
  every output hash was verified, source drift was absent, and worker hashes
  match the executed copies. Result SHA-256:
  `096e69ba566026eba0414a1a77420c2e2bd88e5e25b4b413a9ba5ba7a9ae3fb7`.
- Planning preserves 32 stable world IDs, registered counts and seed for every
  local GPU count 1–16 and Jupiter nodes 1–4. This is offline planning only.
- This assignment changed only the two newly assigned execution/replay files,
  the existing worker check driver and this log. Sent the Chief the ownership
  list, selectors/reports and evidence. Compiled replay/worlds and GPU/trajectory
  checks remain for the Chief's coordinated run; this worker launched none.

Execution selectors are in `tests/unit/test_surface_water_execution.py`:

| Selector | Component report | Run type |
| --- | --- | --- |
| `test_complete_saved_restart_branch_and_windows` | `water-execution-replay.json` | Coordinated compiled replay; not run by this worker |
| `test_independent_world_partition_reorder_and_restart` | `water-execution-worlds.json` | Coordinated compiled worlds; not run by this worker |
| `test_execution_host_contracts` | `water-execution-host-contracts.json` | Host definitions/grid/layout |
| `test_execution_history_capture_retains_complete_fields` | `water-execution-capture-contract.json` | Synthetic host buffers and retained failure evidence |
| `test_one_to_sixteen_gpu_planning_preserves_water_worlds` | `water-execution-planning.json` | Offline planning only |

The Chief accepted the completed handoff and requested stable delivered source
for the coordinated detached CPU/L4 qualification. Protocol, launch and
`PROGRESS.md` remain with the Chief; this worker is awaiting further assignments.

### 2026-10-28 — Independent finite-energy lane

- The active-water schema assignment was superseded before this worker created
  any source, configuration or test drafts. Confirmed that handoff directly;
  the Chief now owns all active-water integration.
- Accepted [the finite-energy assignment](workfiles/FINITE_ENERGY_ASSIGNMENT.md).
  Exclusive files are `src/cells/processes/finite_energy.py`,
  `tests/unit/test_finite_energy.py`,
  `validation/chemistry/finite_energy_reference.py`, optional new protocol and
  `docs/FINITE_ENERGY_POOLS.md`, plus this log.
- Read the existing positive-domain Na/K law, its independent Decimal oracle,
  integration contract and finite-metabolism limitations. The new component
  will preserve the 1-M standard state and signed hydrolysis/synthesis, with
  explicit finite free energy and supply-port work. Existing source and
  detached jobs remain untouched.
- Implemented the new finite-energy process, independent 80-digit scalar
  reference, predeclared contract protocol, tests and usage/physics guide.
  Supplied regeneration uses the declared bounded reversible tanh law; separate
  owner osmolyte counts and volume derivatives remain explicit readouts.
- The Chief reviewed the energy gauge and supply law and authorized small
  CPU-only JIT/vmap checks after their CPU preview completed. Added an explicit
  heterogeneous owner/world temperature-gather bridge contract and guide text.
- Reused the worker-local check driver with finite-energy selectors and the
  established `validation.assembly.component_process.run_bounded` guard:
  CPU 7, BLAS1, <=1 GiB RSS, >=8 GiB host reserve, 180 seconds per command,
  CPU-only JAX and persistent compilation cache disabled. NumPy/reference
  contracts run first; CPU JAX prototypes are selected separately.
- [Initial driver failure](/mnt/workspaces/Cells/finite-energy-contracts-20261028-01/failure.json)
  stopped before any child check: importing the established guard required
  `src` on the driver's own Python import path. Preserved the original failure
  and six exact [source copies](/mnt/workspaces/Cells/finite-energy-contracts-20261028-01/failed-driver-sources.json)
  before fixing that path. The driver now snapshots owned inputs before any
  checks, as well as capturing final formatted sources before validation.
- [NumPy/reference result](/mnt/workspaces/Cells/finite-energy-contracts-20261028-02/result.json):
  **75 passed**, with the initial four JAX prototypes deselected.
  [CPU JAX result](/mnt/workspaces/Cells/finite-energy-contracts-20261028-03/result.json):
  **four passed**, covering eager/JIT/vmap, dynamic parameters, gradients and
  the analytic regeneration derivative at stall. These separate phases passed
  before adding one compiled invalid-domain regression to resolve the different
  JAX predicate path.
- [Final complete component result](/mnt/workspaces/Cells/finite-energy-contracts-20261028-04/result.json):
  **80 passed, zero failures/errors/skips**, in **12.37 seconds** of pytest time.
  This binds the delivered source: 75 NumPy/Decimal contracts and five CPU JAX
  contracts. Ruff, collection and whitespace checks passed. No standalone
  numerical trajectory, whole-model integration or GPU run was performed.
- Final [inputs](/mnt/workspaces/Cells/finite-energy-contracts-20261028-04/inputs.json),
  [test receipt](/mnt/workspaces/Cells/finite-energy-contracts-20261028-04/tests.xml),
  [test log](/mnt/workspaces/Cells/finite-energy-contracts-20261028-04/pytest.log),
  [resource receipt](/mnt/workspaces/Cells/finite-energy-contracts-20261028-04/pytest-guard/result.json)
  and [component reports](/mnt/workspaces/Cells/finite-energy-contracts-20261028-04/evidence/cpu)
  are retained. The established process-tree guard observed peak RSS/high-water
  **369,725,440 bytes (352.60 MiB)** and host availability at least
  **20,813,697,024 bytes (19.38 GiB)**, within the 1-GiB/8-GiB-reserve policy.
  CPU 7, BLAS1 and CPU-only JAX were used; persistent compilation cache was
  explicitly disabled.
- Final result binds **190 source snapshots and 238 output hashes**. Every
  output hash was verified, no source drift occurred during checks, and all six
  delivered code/reference/protocol/guide/driver hashes match their snapshots.
  Result SHA-256: `64a7cd8f9359c9b15b6deb7ae927d692d655de85ef152a9280e3e838691d1435`.
- Usable API: validated `Parameters`, `Routes` and `RegenerationParameters`;
  `thermodynamics`, `domain_valid`, `invariants`, `exchange_rates`,
  `exchange_domain_valid`, `material_balances`, `chemical_power_pJ_s`,
  stage-local `pump_parameters`, `regeneration_rates` and
  `regeneration_domain_valid`. The guide explicitly gathers matching owner/world
  temperatures for the existing pump's separate temperature argument.
- Selectors: `tests/unit/test_finite_energy.py` for all 80;
  `-k 'not jax'` for 75 NumPy/reference cases; `-k jax` for five CPU JAX cases.
  Contract protocol: `validation/chemistry/finite_energy_protocol.json`.
  Required preview reports use `finite-energy-` stems `standard-state`,
  `ownership`, `supply-port` and `pump-bridge`; complete per-case results are in
  the XML. This contract protocol does not launch a GPU qualification.
- Changed only the five assigned new files, this log and the worker-local
  bounded check driver. No existing pump, calcium, ER, model/schema/registry,
  shared status or frozen job artifact was edited by this worker.
- Remaining integration includes finite-pool state/checkpoints, once-owned
  membrane demand and matching temperatures, replacing maintained chemical work,
  and explicit metabolite osmolyte/charge decisions. The transformed pH/Mg model
  rejects substrate exhaustion; it has no biological calibration or respiration
  claim. Supply-off/recovery examples are instantaneous direction contracts.
- Proposed next independent assignment: a bounded standalone demand/supply
  interruption/resumption trajectory harness with an independently integrated
  scalar reference, complete energetic replay and step refinement. Reported
  the finished component and proposal to the Chief; awaiting further scope.

### 2026-10-28 — Finite energy coupled to resolved tissue

- Accepted [the tissue assignment](workfiles/FINITE_ENERGY_TISSUE_ASSIGNMENT.md).
  Owns the seven new spec/model/test/fixture/reference/configuration paths and
  the allowed guide extension; existing finite-energy component and frozen
  qualifications remain unchanged.
- Drafted [the raw schema and Python interface](workfiles/FINITE_ENERGY_TISSUE_INTERFACE.md)
  first, including finite pool references in pump metabolism, independent
  regeneration controls and all 23 complete state fields, for the Chief's
  shared integration hooks.
- [Import readiness](/mnt/workspaces/Cells/finite-energy-tissue-imports-20261028-01/result.json)
  passed under the existing guard on CPU 7; spec/model/fixture imports expose
  23 complete state fields. Notified the Chief so shared hooks and execution
  work could proceed in parallel.
- Implemented the strict schema, model, six synthetic fixtures, independent
  23-field scalar/Decimal reference, example and schema/stage tests. Existing
  pump/internal-transfer fields are integrated with current fuel; no fixed-drive
  work identity or external maintained chemical source is used in the balance.
- [First host/stage run](/mnt/workspaces/Cells/finite-energy-tissue-development-20261028-01/failure.json)
  retained **57 passes and 14 failures**, all before numerical reference
  comparison: NumPy scalar metabolic fields were rejected by the older oracle's
  exact Python-number type contract; one scalar-temperature adapter had the same
  issue. Cast only in the new reference/test adapters. No production physics or
  delivered finite-energy component change was needed. Also routed stage
  evidence through `CELLS_COMPONENT_BACKEND` and capture actual derivatives
  before calling the independent oracle.
- [Final host/schema/stage result](/mnt/workspaces/Cells/finite-energy-tissue-development-20261028-02/result.json):
  **71 passed, zero failures/errors/skips**, in **5.63 seconds** of pytest time.
  Import sorting, formatting, lint, collection and whitespace checks passed.
  The two selectors are `tests/unit/test_surface_energy_spec.py` and
  `tests/unit/test_surface_energy.py`; no JIT, numerical tissue trajectory,
  replay or GPU qualification was run by this worker.
- Retained [inputs](/mnt/workspaces/Cells/finite-energy-tissue-development-20261028-02/inputs.json),
  [test receipt](/mnt/workspaces/Cells/finite-energy-tissue-development-20261028-02/tests.xml),
  [test log](/mnt/workspaces/Cells/finite-energy-tissue-development-20261028-02/pytest.log)
  and [stage reports](/mnt/workspaces/Cells/finite-energy-tissue-development-20261028-02/evidence/cpu).
  All **12** complete 23-field derivative comparisons passed: six synthetic
  arms with compact and padded layouts. Additional checks cover current-pool
  pump coupling, once-owned shared demand, inhibition/reversal, regeneration,
  exhaustion rejection, combined energy and the maintained-pool initial limit.
- CPU 7, BLAS1, CPU-only JAX configuration and disabled persistent compilation
  cache were retained. Across the bounded checks the established guard observed
  peak process-tree/high-water **226,263,040 bytes (215.78 MiB)** and host
  availability at least **17,896,861,696 bytes**, within the 1-GiB/8-GiB-reserve
  limits. The main result's direct-child RSS is 226,160,640 bytes; the guard
  includes its process tree. No detached qualification was inspected or polled.
- The final result binds **194 source snapshots and 265 output hashes**.
  Verified every output hash and all nine owned delivered source/guide/driver
  hashes; no source drift occurred during checks. The existing finite-energy
  component, component reference/tests/protocol and kinetic pump still match
  their accepted component snapshots. Result SHA-256:
  `ef60b4690b80ab4b459b59f943535621463ca705b6af1cc0734d6c173af77b19`.
- Delivered the strict schema, complete-state model, independent stage/reference
  implementation, six fixtures, example configuration and guide extension to
  the Chief. Shared registry/schedule/serialization hooks and compiled
  trajectory, execution/replay and full qualification remain Chief-owned.
  Keep this delivery stable during that work; await the separately scoped
  cotransport source/kernel assignment.

### 2026-10-28 — Conservative electroneutral cotransport component

- Chief accepted the stable finite-energy handoff and assigned
  [the new component](workfiles/COTRANSPORT_ASSIGNMENT.md). Owns only the new
  cotransport process, tests, reference/protocol and guide, plus worker-local
  logs/workfiles. Existing energy/water models and active qualifications remain
  untouched.
- Read pinned BETSE v1.5.0 commit
  `5269a714aa2593ed2a6708c4516289977d8ae1a2`, installed metadata and generic
  transporter/network configuration. Confirmed the four inspected installed
  files match the actual pinned checkout, located under `/mnt/workspaces/Cells`;
  the older documentation's workspace-relative upstream path is absent.
- Drafted [the physical/source contract](../../docs/COTRANSPORT.md) and sent it
  to the Chief before kernel coding: inward-positive KCC 1K/1Cl and NKCC
  1Na/1K/2Cl, log-product affinity, manufactured reversible tanh response,
  matched signed transfer and chemical dissipation, explicit owners/worlds and
  strict positive substrate/padding domains. The pinned generic BETSE builder
  has a different saturation law and remains a separate source-only probe.
- Chief approved the contract before implementation. Added the new process,
  independent scalar/Decimal reference, contract protocol, tests and a worker-local
  pinned-source probe; extended the existing bounded check driver for this scope.
- [First check failure](/mnt/workspaces/Cells/cotransport-contracts-20261028-01/failure.json)
  stopped at lint before source execution or numerical contracts. Fixed the
  probe's loop-closure binding and changed one test lambda to a named function;
  retained exact source snapshots and lint output. Physical equations and
  tolerances were unchanged.
- [Second check failure](/mnt/workspaces/Cells/cotransport-contracts-20261028-02/failure.json)
  passed lint and collected 94 tests, then stopped while serializing the native
  generator's NumPy integer `net_z` into JSON. Source/configuration snapshots and
  the prepared probe inputs were retained. Cast that diagnostic to a Python
  integer; no source law, component physics or numerical tolerance changed.
- [Host/source result](/mnt/workspaces/Cells/cotransport-contracts-20261028-03/result.json):
  **90 passed, zero failures/errors/skips**, with four CPU JAX cases deselected;
  pytest took **1.92 seconds**. Lint/format/collection passed. The
  [source probe](/mnt/workspaces/Cells/cotransport-contracts-20261028-03/evidence/cpu/native-source/source-manifest.json)
  passed **10** separate generic-source cases, binding the actual revision,
  version, installed/checkout equality, four source hashes and exact upstream
  source captures. Cases retain generated expressions and manufactured inputs;
  no native simulation was run.
- All **22** manufactured host reports passed, including 18 named-law Decimal
  cases, shared ownership, six independent broadcast worlds and two independent
  chemical free-energy derivatives. CPU 7/BLAS1 guard peak was **178,987,008
  bytes**, with at least **21,841,784,832 bytes** host memory available.
  No source drift occurred. Result SHA-256:
  `4407e397d4de0f38ffbfffe96b7723d774c097442ddc8fb8d43ba67d87b4f583`.
- Reported the host/source pass and requested the assignment's required
  resource handoff from the Chief before running the four CPU-only JAX
  contracts. No compiled check, GPU job or other job's status poll was started.
- Chief then explicitly cleared all four small CPU JAX cases on CPU 7 under
  the same limits. [CPU JAX result](/mnt/workspaces/Cells/cotransport-contracts-20261028-04/result.json):
  **four passed, zero failures/errors/skips**, with the 90 completed host
  cases deselected, in **10.71 seconds** of pytest time. Covered eager/JIT/vmap
  with two real broadcast world axes, analytic derivatives at stall, independent
  automatic-differentiation chemical power, compiled invalid-trial rejection
  and empty-route material accumulation.
- Together the two passing receipts cover **all 94 collected contracts** and
  ten separate native-generic source cases. Kernel, reference, tests, source
  probe and bounded driver are identical between receipts. Only the guide and
  protocol authorization text changed after the host pass; the final JAX
  receipt binds all seven delivered files. No numerical tissue trajectory,
  tissue integration, GPU run or other job's status poll was performed.
- Final [inputs](/mnt/workspaces/Cells/cotransport-contracts-20261028-04/inputs.json),
  [test receipt](/mnt/workspaces/Cells/cotransport-contracts-20261028-04/tests.xml),
  [test log](/mnt/workspaces/Cells/cotransport-contracts-20261028-04/pytest.log)
  and [guard receipt](/mnt/workspaces/Cells/cotransport-contracts-20261028-04/pytest-guard/result.json)
  are retained. JAX guard peak was **299,933,696 bytes (286.04 MiB)** and host
  availability at least **20,065,640,448 bytes**, within the 1-GiB/8-GiB-reserve
  policy. CPU-only JAX, BLAS1 and disabled persistent compilation cache were used.
- Verified **all 303 host and 242 JAX output hashes**, with no source drift
  during either passing run. All seven final delivered files match the JAX
  snapshots; the eight delivered finite-energy tissue source/guide files still
  match their accepted frozen receipt. Whitespace checks passed. Final JAX
  result SHA-256:
  `df439c89e220cff1cd151d2cfe486672a036d3ebb961a752d69962f28c389f78`.
- Handoff API: `named_stoichiometry`, `Topology`/`Parameters` host validators,
  pure `domain_valid`/`rates`, `exchange_domain_valid`/`exchange_rates` and
  `material_balances`. [Guide and source distinctions](../../docs/COTRANSPORT.md)
  include the governing equations, pinned links/hashes and usage. Select all
  contracts with `tests/unit/test_cotransport.py`, host with `-k 'not jax'`,
  or the four compiled CPU cases with `-k jax`. The generic source probe remains
  a separate driver step and keeps upstream captures outside the repository.
- Delivered the component and exact hashes to the Chief for later tissue
  composition and CPU/L4 qualification. Keep this new delivery stable; await
  the exact ownership/interface for the proposed fixed-volume tissue follow-on.

### 2026-10-28 — Fixed-volume cotransport tissue

- Accepted [the tissue assignment](workfiles/COTRANSPORT_TISSUE_ASSIGNMENT.md).
  Owns eight new spec/model/example/fixture/reference/test/guide paths and own
  workfiles; delivered component/energy files, shared hooks, active jobs and
  canonical project status remain untouched by this worker.
- Sent the approved six-clock/26-state interface early; its public details
  live in [the tissue guide](../../docs/TISSUE_COTRANSPORT.md). The Chief wired
  registration, serialization, scheduling/padding and the ionic-world family.
- [Import readiness](/mnt/workspaces/Cells/cotransport-tissue-imports-20261028-01/result.json)
  passed under CPU 7's existing memory guard. Its supplemental bootstrap
  failure records an initial system-Python guard import that lacked NumPy;
  corrected the launcher to the established CPU environment before any child
  computation. The Chief's separate parse smoke caught a draft assumption
  about `model.species`; corrected all new production callers to use the actual
  `species_ids`/`valence` representation. Chief retained that failed smoke.
- Implemented signed owner transfer, neutral direct-current semantics, local
  route evidence and heat in the combined finite-energy identity. New reference
  combines independently projected energy equations with scalar/Decimal
  cotransport; it imports no production Cells/JAX/schema helpers. Eight fixture
  arms include reversal/stall, sealed/absent routes, release clocks, repeated
  shared patches/pools and renamed/reordered species.
- Initial host suite covers complete 26-field stages, independent clocks,
  live next-stage channel/pump response, exact finite-energy reduction,
  closed finite material/energy extents, compensating local-ledger corruption,
  strict exhaustion/padding, full initial observation and ensemble parsing.
  No numerical tissue trajectory, JIT or GPU run has been started by this lane.
- [First host run](/mnt/workspaces/Cells/cotransport-tissue-development-20261028-01/failure.json)
  retained **33 passes and 42 failures**. Of those, 39 failed at the bridge from
  legacy floating-point layout valences into the new integer topology; three
  hit existing named channels' canonical-species restrictions in the renamed
  fixture. Added the schema's explicit integer valence layout and an agreement
  predicate; made that fixture channel-free while preserving renamed finite
  pump/cotransport roles. Equations and tolerances are unchanged.
- [Second host run](/mnt/workspaces/Cells/cotransport-tissue-development-20261028-02/failure.json)
  retained **76 passes and one failure**. All 23 full-state/clock/energy/observer
  reports passed. The remaining rejection fixture used a KCC capacity whose
  computed power was still finite at the initial gradient; changed that input
  to NKCC at the same capacity, which genuinely overflows. No production law
  or tolerance change was needed. Added two separately selected small CPU JAX
  prototypes for the later required resource handoff; host runs deselect them.
- [Passing host result](/mnt/workspaces/Cells/cotransport-tissue-development-20261028-03/result.json):
  **77 passed, zero failures/errors/skips**, with two JAX cases deselected, in
  **68.83 seconds** of pytest time. Import sorting, formatting, lint and
  collection passed. All **23** saved reports passed: 16 compact/padded
  complete-state cases, four independent control-clock stages, a changed live
  ionic stage, a conservative finite extent and its nonzero-history observer.
- Maximum full-state derivative discrepancy was **1.0291e-5 of its budget**;
  maximum independent combined energy residual was **6.011e-11 pJ/s**, within
  the existing 2e-8 bound. These remain manufactured state/stage checks; no
  numerical tissue trajectory or step-refinement was run by this worker.
- CPU 7/BLAS1 guard peak was **228,573,184 bytes**, with host availability at
  least **19,059,179,520 bytes**, inside the 1-GiB/8-GiB-reserve limits.
  The result binds 199 source snapshots and 292 output hashes, with no source
  drift. Result SHA-256:
  `066fa2e2989a7a39842d01eaa3641917899ca0851617f49e8561057734053ae8`.
- Sent the passing receipt to the Chief and requested the required resource
  handoff for two small CPU-only JAX cases: one complete RHS comparison and a
  state-domain rejection predicate. Neither was launched before that approval.
  Proposed the remaining pinned NaV catalog as the next independent BETSE
  parity feature, based on capability roadmap B03; wait for exact ownership.
- Chief approved exactly the two CPU-only RHS/domain checks under the existing
  limits. [JAX result](/mnt/workspaces/Cells/cotransport-tissue-development-20261028-04/result.json):
  **two passed, zero failures/errors/skips**, with 77 host cases deselected,
  in **95.53 seconds**. Together the passing receipts cover all **79** collected
  schema/stage/compiled contracts. No numerical trajectory, replay, refinement,
  GPU qualification or additional follow-up run was launched by this worker.
- JAX [inputs](/mnt/workspaces/Cells/cotransport-tissue-development-20261028-04/inputs.json),
  [test receipt](/mnt/workspaces/Cells/cotransport-tissue-development-20261028-04/tests.xml),
  [test log](/mnt/workspaces/Cells/cotransport-tissue-development-20261028-04/pytest.log)
  and [resource receipt](/mnt/workspaces/Cells/cotransport-tissue-development-20261028-04/pytest-guard/result.json)
  are retained. Guard peak **1,014,263,808 bytes (967.28 MiB)** and host
  availability at least **17,615,974,400 bytes** satisfy the 1-GiB/8-GiB-reserve
  policy. CPU 7/BLAS1, CPU-only JAX and disabled persistent cache were used.
- Verified **all 292 host and 249 JAX output hashes**, and all nine final
  source/guide/driver hashes. No source drift occurred in either passing run;
  executable source/configuration/tests/driver match between receipts. Only
  the guide gained verification details after the host pass. The accepted
  standalone cotransport component and eight frozen finite-energy tissue
  source/guide files remain unchanged. Whitespace checks passed.
  Final JAX result SHA-256:
  `f038c71ebfdbba1035061859b1a719acb737702bba9d72b243abbcdcdf4f9a58`.
- Handed the stable implementation, guide, complete reports and hashes to the
  Chief, who owns water/finite-energy composition and later execution/replay
  qualification. New GPU qualification is deferred under current user steering.
  Accepted [the next pinned sodium-catalog assignment](workfiles/SODIUM_CATALOG_ASSIGNMENT.md)
  in separately owned new files; this tissue delivery remains frozen.

### 2026-10-28 — Complete pinned sodium-channel component catalog

- Accepted [the seven-class assignment](workfiles/SODIUM_CATALOG_ASSIGNMENT.md)
  after handing off cotransport tissue. Owns only the new sodium catalog,
  independent reference/tests/protocol, guide and worker-local workfiles/log.
- Inspected all seven actual `vg_na.py` classes and inherited
  `ChannelsABC.update_mh`, binding installed files to the pinned checkout.
  Confirmed ms units except NaLeak's seconds, default zero voltage correction,
  NaV1.2's separate internal shifts, identical NavRat1/NavRat3 formulas, leak
  powers 0/0, persistent Nav1p6 powers 1/0, and native backward-Euler update.
- Sent proposed law IDs, codes and array/domain API to the Chief before kernel
  implementation. [Source/physical contract](../../docs/SODIUM_CHANNEL_CATALOG.md)
  separates singular native evidence, regularized limits, continuous rates,
  native initialization/clock and later tissue/biological claims. Retain the
  accepted NaV1.2 implementation unchanged and reuse it exactly.
- Chief approved the law/API proposal and clarified the user's request for
  scientifically adequate validation duration. Implemented twelve-slow-tau
  native depolarization/recovery traces with 2/4/8 clock refinement, independent
  exact full-gate solutions, and isolated continuous-gate RK4 refinement over
  twelve gate time constants at 32/64/128 steps. Physical durations follow the
  actual selected law, including slow seconds; computation stays bounded.
- New kernel keeps Nav1.2 code2 as an exact call into the accepted implementation,
  adds only standalone codes18--23 and explicitly treats code0 as padding in
  this component. The independent 80-digit millivolt reference imports no
  production/NumPy/JAX helpers. The native probe executes the actual pinned
  class and inherited update ASTs, captures ordinary initialization/update,
  voltage corrections, singular failures and physically adequate clamp traces.
  No upstream implementation is copied into the repository.
- [Initial host/source result](/mnt/workspaces/Cells/sodium-catalog-contracts-20261028-01/result.json):
  **113 passed, zero failures/errors/skips**, with two JAX prototypes deselected,
  in **50.96 seconds** of pytest time. Import sorting, formatting, lint and
  collection passed. The separately guarded actual-source probe took **2.53
  seconds**; all seven initialization/discrete-update, seven voltage-correction
  and seven clamp/recovery groups passed.
- The [native manifest](/mnt/workspaces/Cells/sodium-catalog-contracts-20261028-01/evidence/cpu/native-source/source-manifest.json)
  binds revision/version, all three installed/checkout hashes and exact source
  captures. **Eleven actual native singular failures** remain labelled and
  retained; analytic regularization is a separate claim. Native forward/recovery
  traces at 2/4/8 refinement cover **0.024--24 seconds** of physical time;
  Nav1p3 covers **14.8458 seconds**. Native-clock errors converge toward the
  continuous solution with first-order behavior, without claiming finite-clock
  identity. Constant NaLeak traces remain exactly one.
- All **28** independent isolated-gate RK4 refinements passed, with observed
  order **4.11084** and gate durations up to **14.8378 seconds**. Full exact
  two-gate clamp solutions, ordinary/adjacent-singular Decimal equations,
  exact accepted Nav1p2 overlap, source gate powers, real six-world broadcasts,
  population reordering and strict domains/padding passed.
- CPU 7/BLAS1 guard peak was **178,495,488 bytes**, with at least
  **18,389,155,840 bytes** host memory available. No source drift occurred;
  the result binds 201 source snapshots and 503 output hashes. Result SHA-256:
  `9782f54670fdf0af34fda4f9c83de94fed393ff8a2a155f9ad8652229d001b62`.
- Reported the passing host/source receipts and requested the required Chief
  resource handoff for two small CPU JAX array/domain/gradient checks. No JAX
  or GPU check was launched before receiving that authorization.
- Chief verified the host receipt and cleared exactly the two proposed CPU
  JAX cases. [Compiled result](/mnt/workspaces/Cells/sodium-catalog-contracts-20261028-02/result.json):
  **two passed, zero failures/errors/skips**, with 113 host cases deselected,
  in **14.05 seconds**. Eager/JIT/vmap kinetics, opening/RHS agreement,
  compiled strict-domain rejection and finite derivatives at all eleven
  removable singularities passed. Together the receipts cover all **115**
  collected contracts, plus the separately captured native-source groups.
- Final [inputs](/mnt/workspaces/Cells/sodium-catalog-contracts-20261028-02/inputs.json),
  [test receipt](/mnt/workspaces/Cells/sodium-catalog-contracts-20261028-02/tests.xml),
  [test log](/mnt/workspaces/Cells/sodium-catalog-contracts-20261028-02/pytest.log)
  and [guard receipt](/mnt/workspaces/Cells/sodium-catalog-contracts-20261028-02/pytest-guard/result.json)
  remain durable. Guard peak was **329,826,304 bytes (314.55 MiB)** and host
  availability at least **17,956,786,176 bytes**. The process-tree RSS limit
  also bounds PSS and individual RSS below the approved 1-GiB cap. CPU 7/BLAS1,
  CPU-only JAX and disabled persistent compilation cache were retained.
- Verified **all 503 host and 248 JAX output hashes** and all seven delivered
  file hashes. No source drift occurred. All five executable/reference/probe/
  driver files are identical between receipts; only the guide and protocol
  authorization text changed after the host pass. All eight delivered
  cotransport tissue files and the accepted NaV1.2 implementation still match
  their frozen receipts. Whitespace checks passed. Final result SHA-256:
  `69c16cef2cf6c6bc1512d5e959a96c83941147cb0cd180c04889166399a2f009`.
- Stable handoff: `SODIUM_LAWS`, `LAW_CODES`, `LAW_PERMEABILITIES`, `GATE_POWERS`,
  `kinetics`, `initial_gates`, `opening`, `rhs`, `valid_codes`, `domain_valid`.
  Arrays/codes/domain and native/continuous distinctions are documented in the
  [guide](../../docs/SODIUM_CHANNEL_CATALOG.md) and bound
  [protocol](../../validation/channels/sodium_catalog_protocol.json).
  Test selector: `tests/unit/test_sodium_catalog.py`, host `-k 'not jax'`, CPU
  JAX `-k jax`. Sent exact hashes/receipts to the Chief for shared integration.
- This delivery is frozen. No further automatic qualification/regression,
  coupled tissue trajectory, GPU run or existing-job poll is authorized or
  launched by this completed slice. Await the next separately scoped feature.
