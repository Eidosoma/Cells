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

### 2026-10-28 — Remaining pinned potassium-channel component catalog

- Accepted [the nine-class assignment](workfiles/POTASSIUM_CATALOG_ASSIGNMENT.md).
  Owns only the five new potassium catalog/reference/test/protocol/guide files
  and existing worker log/workfiles. Delivered sodium, cotransport and energy/
  water sources remain stable; shared tissue integration stays Chief-owned.
- Inspected Kv2p1/2, Kv3p1/2/3/4, K_Fast, KLeak and Kir2p1 plus actual inherited
  updates. Sent the proposed codes24--31, exact old Kir2.1/code1 reuse, two-gate
  API and separate negative padding sentinel before kernel coding. The
  [source/interface guide](../../docs/POTASSIUM_CHANNEL_CATALOG.md) records the
  pinned hashes, powers, units, native clock and computational domain.
- Reported the concrete Kv3p3 source discrepancy to the Chief: unused nominal
  vrev+82mV carries a source FIXME, and literal hyperpolarized tau_h gives a
  21.8409-day twelve-tau horizon at -80mV. Proposed preserving its coefficients
  as a `source_tau` law, with exact/geometric clamp checks covering the full
  physical horizon at bounded computational cost. No source unit/fit repair.
- Chief approved the exact law IDs/codes, separate -1 padding sentinel, literal
  Kv3p3 timing and unused +82mV source metadata before implementation. Added
  the new kernel, scalar/80-digit independent reference, actual AST/source
  probe, protocol and full host tests. The reference widens Decimal exponent
  range to represent the extremely separated gate timescales without a gate
  floor or shortened model-time horizon.
- Host checks cover all nine laws, ordinary/transition/adjacent-binary inputs,
  exact Kir2.1 overlap including opening evaluation order, source powers and
  auxiliary gates, real independent world broadcasts, padding/domain failures,
  12-slow-tau full clamp/recovery, and 36 isolated-gate RK4 refinements.
  Native source probes separately capture initialization, inherited backward
  Euler, voltage correction, transition centers and 2/4/8 clamp-clock refinement.
  Compiled prototypes remain deselected until the Chief's resource handoff.
- [Initial host/source result](/mnt/workspaces/Cells/potassium-catalog-contracts-20261028-01/result.json):
  **144 passed, zero failures/errors/skips**, with two JAX prototypes deselected,
  in **60.69 seconds**. Import sorting, formatting, lint and collection passed.
  The separately guarded actual pinned-source probe took **4.05 wall seconds**.
  Nine initialization/update, nine voltage-correction, seventeen transition
  and nine refined clamp/recovery source groups all passed; there are no
  invented singular outcomes for these smooth source laws.
- All **36** isolated continuous-gate refinements passed, with observed order
  **4.11084**. Kv3p3 actual native recovery spans **1,887,050.752 seconds /
  21.8409 days** of model time, plus 35.7109 seconds of depolarization. The
  explicit full horizon, unused source vrev+82mV, target baseline and source
  time units are preserved in the native arrays/metadata. Native backward-Euler
  errors decrease from 0.0051754 through 0.00262913 to 0.00132539 across
  2/4/8 refinement; finite-clock identity is not claimed.
- CPU 7/BLAS1 guard peak was **178,610,176 bytes**, with host availability at
  least **17,181,671,424 bytes**, inside the existing 1-GiB/8-GiB-reserve policy.
  No source drift occurred. The result binds 202 source snapshots and 583
  output hashes. Result SHA-256:
  `60f4945b4b51c560cbae7061f2b56fbf7a8b10f6912da435f4b85dcd9bcf167a`.
- Reported passing host/source results to the Chief and requested exactly two
  small CPU-only JAX array/domain/derivative checks. No compiled check or GPU
  launch was started before approval; earlier delivered sources stay stable.
- Chief approved exactly the two proposed compiled CPU checks.
  [JAX result](/mnt/workspaces/Cells/potassium-catalog-contracts-20261028-02/result.json):
  **two passed, zero failures/errors/skips**, with 144 host cases deselected,
  in **9.59 seconds**. Eager/JIT/vmap kinetics, RHS/opening, strict compiled
  rejection, smooth-transition derivatives and the long Kv3p3 tail passed.
  Together the passing receipts cover all **146** collected contracts.
- JAX [inputs](/mnt/workspaces/Cells/potassium-catalog-contracts-20261028-02/inputs.json),
  [test receipt](/mnt/workspaces/Cells/potassium-catalog-contracts-20261028-02/tests.xml),
  [test log](/mnt/workspaces/Cells/potassium-catalog-contracts-20261028-02/pytest.log)
  and [guard receipt](/mnt/workspaces/Cells/potassium-catalog-contracts-20261028-02/pytest-guard/result.json)
  are retained. Guard peak was **302,432,256 bytes (288.42 MiB)** and host
  availability at least **19,726,942,208 bytes**. Process-tree/individual RSS
  below the 1-GiB limit also bounds PSS; CPU 7/BLAS1, disabled persistent cache
  and no GPU satisfy the cleared resource handoff.
- Verified **all 583 host and 249 JAX output hashes** and all seven final
  delivered hashes. No drift occurred; executable/kernel/reference/test/probe/
  driver source matches between receipts. Only guide verification details and
  protocol authorization text changed after the host run. Six frozen sodium
  source/guide/probe files and the accepted Kir2.1 implementation remain
  unchanged. Whitespace checks passed. Final JAX result SHA-256:
  `4b0fa82bec4b908ec003086be82bc9d3c92782ec80ecd683af54422fc4a3b458`.
- Stable API: `POTASSIUM_LAWS`, `LAW_CODES`, `LAW_PERMEABILITIES`, `GATE_POWERS`,
  `PAD_CODE=-1`, `kinetics`, `initial_gates`, `opening`, `rhs`, `valid_codes`,
  `domain_valid`. Select `tests/unit/test_potassium_catalog.py`, host with
  `-k 'not jax'` or the two cleared compiled cases with `-k jax`. Sent complete
  source distinctions, receipts and hashes to the Chief for shared integration.
- This delivery is frozen. Accepted the separately scoped
  [leak-catalog assignment](workfiles/LEAK_CATALOG_ASSIGNMENT.md) after handoff;
  no further potassium qualification/regression, coupled trajectory, GPU job
  or existing-job poll follows automatically from this completed slice.

### 2026-10-28 — Chloride and mixed-cation leak components

- Accepted [the three-class assignment](workfiles/LEAK_CATALOG_ASSIGNMENT.md)
  after stable potassium handoff. Owns only the five new leak kernel/reference/
  test/protocol/guide paths plus own logs/workfiles; delivered catalogs and
  shared model/hooks/status stay untouched.
- Source inspection agrees with preapproved codes32--34 and named laws.
  Retains Cl=1, ordered CatLeak Na/K/Ca=1/1/0 and CatLeak2=1/1/1; all powers0/0,
  targets1, tau1second and no assigned reversal voltage. The
  [guide](../../docs/LEAK_CHANNEL_CATALOG.md) records native target defaults,
  assignment scatter, correction-argument differences and clock distinctions.
- Chief accepted the array/availability interface. Added explicit typed finite
  control-domain validation, strict zero padding controls and a pure canonical
  permeability-weight helper with one multiplier per population. Conductance
  blocking does not freeze auxiliary clocks or excuse invalid gate state.
  CatLeak's zero calcium remains explicit metadata, not an omitted ambiguity.
- Native probes will preserve reordered/empty/duplicate target semantics as
  source evidence only, without treating duplicate targets as duplicate physical
  populations. Twelve-second perturbed auxiliary recovery and clock/RK4
  refinement provide adequate duration without inventing voltage gating.
- Added independent source target/clock probes and host tests for all three
  laws, source metadata/zero Ca, common availability, actual six-world
  broadcasts, population reordering, blocked auxiliary validity and explicit
  padding. Control helpers preserve code-array population count and require
  explicit leading axes for independent-world controls; nonfinite controls
  remain invalid even when the declared population axis is empty.
- Separate manufactured auxiliary perturbations recover for twelve seconds
  with native 2/4/8 clock refinement and independent exact solutions. Six
  isolated-gate RK4 refinements cover the same twelve time constants. Two
  JAX array/domain/derivative prototypes remain deselected in the initial run.
- [Initial host/source result](/mnt/workspaces/Cells/leak-catalog-contracts-20261028-01/result.json):
  **63 passed, zero failures/errors/skips**, with two compiled prototypes
  deselected, in **3.09 seconds**. Import sorting, formatting, lint and
  collection passed. The separately guarded actual-source probe took **0.51
  seconds** and passed all **12** native default/reordered/empty/duplicate
  target/initialization/clock cases and **six** twelve-second auxiliary-recovery
  groups, each with 2/4/8 backward-Euler refinement.
- All **six** continuous auxiliary-clock RK4 refinements passed with observed
  order **4.11084**. Common availability/zero calcium, explicit population axes,
  actual six-world broadcasts, strict blocked auxiliary state and empty-axis
  nonfinite-control rejection passed. Native target assignment and correction
  argument differences remain separately labelled source evidence.
- CPU 7/BLAS1 guard peak was **178,147,328 bytes** and host availability at
  least **19,860,586,496 bytes**, within the 1-GiB/8-GiB-reserve limits.
  No source drift occurred. The result binds 203 source snapshots and 373
  output hashes. Result SHA-256:
  `44370851d7c3677b8c713103414329023c8858ff7846ac6cb527c685fdb8987b`.
- Sent the stable host interface/receipt to the Chief for shared @8 integration
  and requested exactly two CPU JAX array/domain/derivative checks. None was
  launched before authorization. All earlier delivered catalogs remain stable.
- The Chief approved exactly those two compiled CPU checks.
  [Final JAX result](/mnt/workspaces/Cells/leak-catalog-contracts-20261028-02/result.json):
  **two passed, zero failures/errors/skips**, with 63 host cases deselected,
  in **2.94 seconds**. Eager/JIT/vmap arrays, canonical route weights, strict
  control domains, empty-axis nonfinite control rejection and blocked invalid
  auxiliary state passed. Derivatives retain zero voltage sensitivity, active
  auxiliary-clock Jacobian -1, neutral padding, one common route control and
  CatLeak's exact zero calcium coefficient. Together the receipts cover all
  **65** collected contracts.
- JAX [inputs](/mnt/workspaces/Cells/leak-catalog-contracts-20261028-02/inputs.json),
  [test receipt](/mnt/workspaces/Cells/leak-catalog-contracts-20261028-02/tests.xml),
  [test log](/mnt/workspaces/Cells/leak-catalog-contracts-20261028-02/pytest.log)
  and [guard receipt](/mnt/workspaces/Cells/leak-catalog-contracts-20261028-02/pytest-guard/result.json)
  remain external. The pytest guard recorded **240,836,608 bytes (229.68 MiB)**
  peak process-tree RSS and **19,011,796,992 bytes** minimum available host
  memory, within the 1-GiB/8-GiB-reserve limits. CPU 7, BLAS1, CPU-only JAX and
  disabled persistent cache match the cleared run.
- Verified **all 373 host and 252 JAX output hashes** and all seven final
  kernel/test/reference/protocol/guide/probe/driver hashes. No within-run
  source drift occurred. Executable/kernel/reference/test/probe/driver source
  agrees between receipts; only guide verification details and protocol
  authorization changed after the host run. The six frozen files of each
  sodium and potassium delivery still match their accepted receipts.
  Whitespace checks passed. Final JAX result SHA-256:
  `b692080421422807d6c06ffcd391d705eb1f1c4a9db3318409f00f3911adf8a6`.
- Stable API: `LEAK_LAWS`, `LAW_CODES`, `LAW_PERMEABILITIES`, `GATE_POWERS`,
  `SPECIES`, `SPECIES_VALENCE`, `PAD_CODE=-1`, `kinetics`, `initial_gates`,
  `opening`, `rhs`, `valid_codes`, `domain_valid`, `permeability_weights`,
  `permeability_domain_valid`. The last predicate must guard physical use of
  the unchecked weight helper. Select `tests/unit/test_leak_channels.py`,
  host with `-k 'not jax'` or the two cleared compiled cases with `-k jax`.
- This delivery is frozen and handed to the Chief for shared integration and
  canonical status. No further qualification/regression, coupled trajectory,
  GPU job or existing-job poll follows automatically from this completed slice.

### 2026-10-28 — Finite-pool calcium-pump adapter

- Accepted the Chief's next standalone assignment and sent ownership/API before
  coding. Owns only the five new finite-calcium kernel/test/reference/protocol/
  guide files and this worker's log/runner. All delivered component source and
  shared hooks/model/schema/PROGRESS stay untouched. The existing worker runner
  is extended for this explicitly assigned scope.
- Chief confirmed the required mapping
  `deltaG0_1mM=deltaG0_1M-R*T*ln1000`. Current owner concentrations and temperature
  feed unchanged PMCA/ER source kernels. Owner free energies and the existing
  Na/K convention retain the 1-M standard. ER is one Ca per signed formal ATP
  cycle; NCX is excluded from ATP demand.
- Added strict full pool/route predicates, neutral padding, signed route powers
  and a once-only exchange bridge. Independent Decimal contracts cover old
  maintained reductions, different-temperature owners, multiple PMCA/ER routes
  sharing one pool, stall/reversal, blocking, material/energy proofs and actual
  independent-world broadcasting. Two compiled prototypes remain deselected.
- The manufactured depletion/stall and supplied-recovery experiment uses
  equal-potential clamped calcium reservoirs. Each phase lasts twelve derived
  local relaxation times with independent Decimal integration and RK4 heat/work
  refinement. It makes no closed tissue or zero-ATP exhaustion claim.
- Initial checks use the existing bounded runner on CPU 7, BLAS1, at most 1 GiB
  process-tree/individual RSS and at least 8 GiB available host memory. Runtime
  evidence remains under `/mnt/workspaces/Cells/finite-calcium-contracts-20261028-*`.
- [First receipt](/mnt/workspaces/Cells/finite-calcium-contracts-20261028-01/failure.json)
  preserves a lint-only failure before test execution: two phase closures need
  explicit binding, one adjacent-error zip needs explicit non-strict length and
  one unused JAX import needs removal (five findings). Corrected these test/
  oracle hygiene issues; no physical law or numerical acceptance was changed.
- [Second receipt](/mnt/workspaces/Cells/finite-calcium-contracts-20261028-02/failure.json)
  retains **62 passing and two failing host contracts**. Both failures exposed
  genuine independent-world broadcasting in the adapter: the unchanged NumPy
  ER source kernel performs an in-place saturation subtraction and cannot grow
  its first operand's axes. Added explicit common-shape broadcasting before
  entering that kernel; old source files, physics and budgets are unchanged.
  Depletion/recovery, strict domains and material/energy contracts passed.
- [Corrected host result](/mnt/workspaces/Cells/finite-calcium-contracts-20261028-03/result.json):
  **64 passed, zero failures/errors/skips**, with two compiled prototypes
  deselected, in **11.44 seconds**. All 257 output hashes verified; no within-run
  source drift. Host result SHA-256:
  `4d232ac5d9f5760f31bdad14b490dc3a4627eb2522f46a12c7c7904807144c5a`.
  The guard peak was **179,216,384 bytes** and minimum host availability
  **18,429,378,560 bytes**, within the assigned limits.
- Both PMCA and formal-one-Ca ER manufactured paths run for **94.66252584 s**
  depletion and **46.39719362 s** driven recovery. Independent final ATP values
  are **0.3819713499993 / 0.7792971262174 fmol**. Heat/work balance orders are
  **4.02259 / 4.01083**, finest residual **1.70655e-6 pJ** against the declared
  1e-5-pJ budget, and finest ATP error **1.48832e-10 fmol**. Every stage retains
  positive pools; pump extent stays fixed during blocked recovery.
- Confirmed finite_energy, kinetic_pump and both original calcium kernels still
  match the accepted finite-energy receipt. Sent clean host proof to the Chief
  and requested exactly two small compiled array/domain/energy-derivative
  checks. Those prototypes add an explicit NumPy comparison and owner-T
  derivative check before their first selected execution; no host test changes.
- The Chief verified the host receipt and cleared exactly the two proposed
  CPU JAX checks. [Final result](/mnt/workspaces/Cells/finite-calcium-contracts-20261028-04/result.json):
  **two passed, zero failures/errors/skips**, with 64 host cases deselected,
  in **8.18 seconds**. Eager/JIT/vmap arrays, strict blocked/invalid-pool/control
  rejection, NumPy-equivalent owner exchange, finite free-energy gradients,
  near-stall signed rate derivatives and the owner-temperature convention
  derivative passed. Together the two clean receipts cover all **66** contracts.
- Final [inputs](/mnt/workspaces/Cells/finite-calcium-contracts-20261028-04/inputs.json),
  [test receipt](/mnt/workspaces/Cells/finite-calcium-contracts-20261028-04/tests.xml),
  [test log](/mnt/workspaces/Cells/finite-calcium-contracts-20261028-04/pytest.log)
  and [guard](/mnt/workspaces/Cells/finite-calcium-contracts-20261028-04/pytest-guard/result.json)
  remain external. Guard peak **356,610,048 bytes (340.09 MiB)** and minimum
  host availability **21,331,329,024 bytes** satisfy 1-GiB RSS and 8-GiB reserve;
  tree RSS also bounds individual RSS and PSS. CPU 7/BLAS1, CPU-only JAX and
  disabled persistent compilation cache match the cleared execution.
- Verified **all 257 host and 250 JAX output hashes** and all six final owned
  source/test/reference/protocol/guide/driver hashes. No within-run source drift.
  Kernel/reference/guide/driver agree between clean receipts. Test changes are
  limited to the two previously deselected prototypes and formatting; an AST
  comparison confirms every host definition is unchanged. Protocol changes
  record compiled authorization. Original finite-energy, Na/K, PMCA and ER
  kernels remain unchanged, as do the six sodium, potassium and leak delivered
  source/guide/probe files per catalog. Whitespace checks passed. Final result
  SHA-256:
  `0d13e7d3fd4f72c39a20441debecec793579a4fabed8ce8938ab20e97b92471a`.
- Stable API is `PumpParameters`, `Rates`, `Routes=finite_energy.Routes`,
  `legacy_standard_energy`, `pump_parameters`, `pmca_rates`, `er_rates`,
  `domain_valid(kind='pmca'|'er')`, and `pool_exchange`; named finite laws are
  `finite_atp_pmca_betse_positive@1` and `finite_atp_er_1ca_betse_positive@1`.
  The [guide](../../docs/FINITE_CALCIUM_PUMPS.md) defines argument order, native
  voltage signs, once-only shared-owner assembly and external supply terms.
  Select host tests with `-k 'not jax'`, compiled cases with `-k jax`.
- Sent complete receipts, API and final hashes to the Chief. The five component
  files are frozen; canonical status and later integration remain Chief-owned.
  No additional regression/qualification, GPU launch or detached-job polling
  follows automatically from this completed assignment.

### 2026-10-28 — Remaining calcium source classes

- Chief accepted the finite-calcium receipt and assigned four remaining pinned
  `vg_ca.py` classes. Sent source dependencies/aliases/quirks and API proposal
  before coding; Chief approved the scope and future codes35--38. Owns only
  new calcium-extra source/test/reference/protocol/guide and own probe/runner/
  log files. The five delivered finite-calcium files and all earlier catalogs
  stay frozen; shared models/hooks/status remain Chief-owned.
- Source inspection confirms no full kinetic aliases. Ca_L2 overlaps Cav1p3
  targets with fixed 10/59-ms tau; Ca_L3 retains a 15-mV shift and the same
  fixed taus. Cav_G has a removable alpha_m singularity at -27 mV; CaLeak has
  powers0/0, targets1 and one-second auxiliary clocks. The selected methods use
  voltage only, without a Ca/ligand gate equation. Source qt1, Texpt36/23C and
  nominal vrev131/30mV remain labelled metadata without refitting or Q10 scaling.
- Implemented the common two-gate/population/leading-world interface with
  explicit negative padding and strict domains. The differentiable existing
  Bernoulli helper supplies Cav_G's exact 0.209/ms limit; raw native failures
  are preserved separately. The independent Decimal oracle imports no Cells,
  NumPy or JAX helpers. Actual native AST captures include ordinary/correction/
  target scatter and backwards-Euler clock checks.
- Adequate-duration probes retain twelve slow taus per clamp phase, including
  separate twelve-second leak auxiliary recovery. Sixteen isolated RK4 checks
  refine over twelve individual gate taus with exact fixed-point companions.
  Host checks use CPU7, BLAS1, <=1GiB RSS and >=8GiB reserve under the reused
  guarded runner. Two JAX prototypes remain deselected pending Chief clearance.
- [Initial receipt](/mnt/workspaces/Cells/calcium-extra-contracts-20261028-01/failure.json)
  preserves one runner line-length lint finding before source/test execution.
  Split the new long probe path across its directory and filename components;
  no scientific input, source equation or acceptance budget changed.
- [First host/source pass](/mnt/workspaces/Cells/calcium-extra-contracts-20261028-02/result.json)
  passed **75 host contracts** and all native probes, including three retained
  upstream singular failures, in **8.66 seconds** of pytest. Before requesting
  compiled clearance, closing interface review found that empty broadcasting
  could discard an invalid raw input. Added pre-broadcast declared-code/gate/V
  checks and five targeted empty-axis cases. Existing physical equations,
  native probe/reference and numerical tolerances remain unchanged; this is a
  concrete strict-domain completion within the current assignment.
- [Final host/source result](/mnt/workspaces/Cells/calcium-extra-contracts-20261028-03/result.json):
  **80 passed, zero failures/errors/skips**, with two compiled prototypes
  deselected, in **24.92 seconds**. All **425** output hashes verified, with
  210 source snapshots and no within-run source drift. Host result SHA-256:
  `f4a3fb53dc7381d43772c6b610b4f7b4e456630e350418058e0247ba3813d2f8`.
- The separately guarded actual-source probe passed four ordinary, four
  correction, twelve target-scatter and four clamp groups in **2.29 seconds**.
  It retains three explicit native Cav_G init/calculate/run failures at -27mV
  with raw nonfinite arrays, plus seven nearby conditioning diagnostics. These
  defect records are not regularized native passes. Source qt/Texpt/vrev and
  Ca-only permeability metadata match the pinned checkout.
- Native phases last **0.708 s** each for Ca_L2/Ca_L3, **2.69501381 / 5.15870060
  s** for Cav_G depolarization/recovery, and **12 s** each for CaLeak's separately
  perturbed auxiliaries. All four 2/4/8 backward-Euler refinements converge.
  All **sixteen** isolated continuous refinements pass with order **4.11084**
  over twelve individual taus. Gate equations have no inferred Ca/ligand/T
  dependence or fixed ionic reversal.
- Host pytest guard peak **178,253,824 bytes** and minimum host availability
  **21,173,690,368 bytes** satisfy the assigned RSS/reserve limits. Sent clean
  host/API evidence to the Chief and requested exactly two CPU7 compiled
  prototypes: arrays/RHS/opening/strict domains (including empty input loss),
  and analytic-limit/shift/leak voltage derivatives. None has launched before
  clearance; accepted finite-calcium and all earlier component files stay frozen.
- Chief cleared exactly the proposed two CPU JAX checks.
  [Final compiled result](/mnt/workspaces/Cells/calcium-extra-contracts-20261028-04/result.json):
  **two passed, zero failures/errors/skips**, with 80 host cases deselected,
  in **9.49 seconds**. Eager/JIT/vmap targets/tau, RHS/opening, strict code/gate/
  padding rejection and invalid declarations discarded by empty broadcasting
  passed. Compiled derivatives agree with the independent 80-digit scalar
  reference at shift/transition/limit points, including finite Cav_G derivatives
  at -27mV and exactly zero CaLeak voltage sensitivity. Together the clean
  receipts cover all **82** contracts.
- Final [inputs](/mnt/workspaces/Cells/calcium-extra-contracts-20261028-04/inputs.json),
  [test receipt](/mnt/workspaces/Cells/calcium-extra-contracts-20261028-04/tests.xml),
  [test log](/mnt/workspaces/Cells/calcium-extra-contracts-20261028-04/pytest.log)
  and [guard](/mnt/workspaces/Cells/calcium-extra-contracts-20261028-04/pytest-guard/result.json)
  remain external. Guard peak **289,599,488 bytes (276.18 MiB)** and minimum
  host availability **20,118,044,672 bytes** satisfy 1-GiB RSS and 8-GiB reserve;
  tree RSS bounds individual RSS and PSS. CPU7/BLAS1, CPU-only JAX and disabled
  persistent compilation cache match the authorization.
- Verified **all 425 host and 261 JAX output hashes** and all seven final
  owned-file hashes. Only protocol authorization changed between the two clean
  owned snapshots; kernel/test/reference/guide/probe/driver stayed identical.
  The final run records concurrent changes to four **shared** files:
  `src/cells/assembly_cluster/engine.py`, `src/cells/assembly_cluster/spec.py`,
  `src/cells/ensemble/cluster.py`, `src/cells/models/surface_calcium_energy.py`.
  Both snapshots are retained by the runner. These are outside this standalone
  component's implementation/import path; no integrated-source freeze or tissue
  validation is claimed. No owned source drift occurred.
- The five finite-calcium adapter files and six delivered files per sodium,
  potassium and leak catalog still match their accepted receipts. Whitespace
  checks passed. Final compiled result SHA-256:
  `012d9bf209d8ac9ecb0f3ba2ed7c69fec8a7a254467898bd93e0e5e5888c0c28`.
- Stable API: `CALCIUM_EXTRA_LAWS`, `LAW_CODES`, `LAW_PERMEABILITIES`,
  `GATE_POWERS`, `PAD_CODE=-1`, `kinetics`, `initial_gates`, `opening`, `rhs`,
  `valid_codes`, `domain_valid`. Codes35--38 and volts/seconds use the proposed
  law identities. Select `tests/unit/test_calcium_catalog_extra.py`, host with
  `-k 'not jax'` or the two cleared compiled cases with `-k jax`.
- Sent final receipts/API/hashes and shared-drift details to the Chief. The five
  component files and native probe are frozen for later integration. No shared
  hook/PROGRESS edit, further qualification/regression, GPU launch or detached
  status poll follows automatically from this completed assignment.

### 2026-10-28 — Legacy calcium/voltage-activated potassium function

- Chief assigned inspection of remaining source Ca/ligand channels, then a
  disjoint new component. Found actual legacy
  `betse.science.tissue.channels_o.cagPotassium`; no Ca-gated K/Cl class or
  `cagPotassium` call site was found in the pinned checkout. Sent the equation,
  free-cytosolic owner dependency, literal numeric-mM scale, source targeting
  defects and instantaneous API before coding. Chief approved future code39
  and `betse_cagpotassium_numeric_mM_scale@1` with explicit legacy scope.
- Owns only new calcium_activated_potassium process/test/reference/protocol/
  guide and own probe/runner/log. The five calcium-extra files and their probe
  remain frozen while the Chief integrates them in versioned shared catalogs.
  All prior deliveries and shared/core/model/PROGRESS files stay untouched.
- Implemented a zero-state algebraic readout from V, current free cytosolic Ca
  and actual source T. It retains `1e6*C`, zero-Ca basal opening and K-only
  transport metadata without consuming sensed Ca. A stable bounded quotient
  and log-odds avoid raw source overflow, without floors or inferred BK/SK fits.
  Declared codes/population count, padding and controls have strict raw-domain
  checks, including blocked and empty-axis cases.
- Added independent 80-digit literal-source equations and analytic Ca/V/T/
  control derivatives. Native captures preserve whole-K-row assignment, selected
  Ca versus full V, two subset/container failures, extreme arithmetic overflow
  and an inspected call-site inventory. Owner-read probes preserve Ca amounts.
- Ca/V/control steps and a declared external pulse/12-input-tau decay provide
  algebraic response evidence. There is no native tau, gate recovery/settling
  or coupled calcium-dynamics claim. Initial checks use CPU7/BLAS1 with the
  established1-GiB RSS/8-GiB reserve guard and external runtime artifacts. Two
  compiled prototypes remain deselected pending Chief clearance.
- [Initial receipt](/mnt/workspaces/Cells/cagpotassium-contracts-20261028-01/failure.json)
  preserves one probe-description line-length lint finding before source/test
  execution. Wrapped that string and retained an all-checkout Python inventory;
  no physical equation, computational input or acceptance budget changed.
- [Clean host/native result](/mnt/workspaces/Cells/cagpotassium-contracts-20261028-02/result.json):
  **101 passed, zero failures/errors/skips**, with two compiled prototypes
  deselected, in **1.85 seconds**. All **360** output hashes verified, with
  216 source snapshots and no within-run source drift. Result SHA-256:
  `ac6e92ef62b072242f97627a0ed04f73a4d2dd68ed6b21cc14b91e12338d02a8`.
- Actual-source probe took **0.77 seconds** and passed three ordinary groups
  (18 Ca/V/T points), shared-owner readout checks, six targeting/container
  cases and the empty full-container case. It separately preserves **two**
  native subset/empty target shape failures and **one** extreme numeric-Ca
  overflow with raw nonfinite arrays. The inspected **397** pinned Python
  files contain only the definition and no found `cagPotassium` call site.
  Unit/configuration and source setup hashes match installed and checkout files.
- Analytic zero/basal/high-Ca limits, literal numeric-mM scale, no sensed-Ca
  consumption, actual six-world broadcasts, strict raw/blocked/padded domains
  and stateless Ca/V/control steps passed. The declared external pulse decays
  over **24 s / twelve input taus**, ending at **26 s**; this evidence makes no
  native channel-recovery or coupled calcium-dynamics claim.
- Host guard peak **178,176,000 bytes** and minimum available host memory
  **21,604,364,288 bytes** satisfy the assigned limits. Sent native captures,
  scoped stage API and clean receipt to the Chief before any shared integration.
  Requested exactly two CPU7 JAX prototypes for eager/JIT/vmap arrays/strict
  domains and independent Ca/V/T/availability derivatives; none was launched
  before clearance. All frozen calcium-extra files remain unchanged.
- Chief cleared exactly the two proposed CPU7 JAX prototypes.
  [Final compiled result](/mnt/workspaces/Cells/cagpotassium-contracts-20261028-03/result.json):
  **two passed, zero failures/errors/skips**, with 101 host cases deselected,
  in **4.82 seconds**. Eager/JIT/vmap probabilities/control multipliers,
  strict invalid/blocked/empty-input rejection and independent analytic
  Ca/V/T/availability derivatives passed. The zero-Ca derivative is finite;
  blocked physical sensitivities vanish while the availability derivative
  retains the current source probability. Together receipts cover **103** tests.
- Final [inputs](/mnt/workspaces/Cells/cagpotassium-contracts-20261028-03/inputs.json),
  [test receipt](/mnt/workspaces/Cells/cagpotassium-contracts-20261028-03/tests.xml),
  [test log](/mnt/workspaces/Cells/cagpotassium-contracts-20261028-03/pytest.log)
  and [guard](/mnt/workspaces/Cells/cagpotassium-contracts-20261028-03/pytest-guard/result.json)
  remain external. Peak **250,810,368 bytes (239.19 MiB)** and minimum available
  host memory **20,925,972,480 bytes** satisfy 1-GiB RSS and 8-GiB reserve;
  process-tree RSS also bounds individual RSS and PSS. CPU7/BLAS1, CPU-only
  JAX and disabled persistent compilation cache match the authorization.
- Verified **all 360 host and 264 JAX output hashes**, all seven final owned
  snapshots and no within-run source drift. Kernel/test/reference/guide/probe/
  driver are identical between clean receipts; only protocol authorization
  changed. The five calcium-extra component files and native probe remain
  frozen, as do the five finite-calcium adapter files. Whitespace checks passed.
  Final compiled result SHA-256:
  `2913bfd839eabfb5991f3ed4d6aa62dba96cf4f9a54a0982f3d4748d811e71eb`.
- Stable API: `LAW_ID`, `LAW_CODE=39`, `PAD_CODE=-1`, `LAW_CODES`,
  `LAW_PERMEABILITIES`, `SENSED_SPECIES`, `TRANSPORTED_SPECIES`,
  `GATE_STATE_COUNT=0`, `opening(V,Ca_free_mM,T,codes)`,
  `effective_opening(...,availability)`, `domain_valid(...,availability=None)`
  and `valid_codes`, with `xp=np/jnp`. The
  [guide](../../docs/CALCIUM_ACTIVATED_POTASSIUM.md) preserves numeric units,
  current free-cytosolic owner inputs, legacy source/container limits and zero
  state/clock scope. Select host tests with `-k 'not jax'`, compiled with `-k jax`.
- Sent native captures, stage API, final receipts and hashes to the Chief. The
  five component files and probe are frozen. Code39 is not merged into the
  active 39-law catalog in this delivery. No shared/PROGRESS edits, extra
  source captures, follow-up regression/qualification, GPU job or detached
  status poll follows automatically from this completed standalone assignment.

### 2026-10-28 — Wound source limits and Morris–Lecar pivot

- Accepted wound/TRP source inspection. Reported incompatible base/subclass
  init/run signatures, missing gate time_unit and commented-out wound-factor
  permeability/ionic transport before implementing a component. The Chief
  requested a compact source-limit note/raw failures and explicitly redirected
  feature work to Morris–Lecar; no wound fragment project was created.
- [Wound source note](workfiles/WOUND_SOURCE_LIMITS.md) links unchanged native
  init/run `TypeError` evidence. Direct subclass metadata has raw tau1 without
  a defined clock. The captured run leaves W unchanged before the failing call.
  The audit source and three pinned files are retained externally, with JSON
  SHA-256 `7def0f6cb33a2bc039770872669f17e262ca8d0ec764d3e0b128bc01e8ef4381`.
  The first launcher lacked `src` on PYTHONPATH and stopped before the audit;
  corrected that bootstrap path without modifying native code. The actual
  bounded audit took **0.52 s**, peak **34,394,112 bytes**, with at least
  **19,404,083,200 bytes** available host memory, CPU7/BLAS1.
- Morris–Lecar source inspection confirms active ML factory/init/run call sites
  in chemistry/networks.py and thirteen concrete classes. Five kinetic K laws
  use native backward Euler with effective tau=raw_tau/(1000*Phi); the slow
  Kv1p5S law retains Phi=.00132 and 50x tau. Eight algebraic laws set m_inf
  instantaneously, including dt0. Source HCN sign and K/Na1/.2 metadata remain
  literal. Stale configuration comments reference nonexistent Kv_ML2.
- Sent source findings and one-state/zero-state hybrid API before coding. Chief
  cleared codes40--52 and absent packed states zero, without artificial h or
  algebraic relaxation clocks. Owns new morris_lecar_channels source/reference/
  protocol/tests/guide/capture/runner and this log only. All prior component and
  runner files stay frozen; source-limit note/audit are worker-local artifacts.
- [First ML receipt](/mnt/workspaces/Cells/morris-lecar-contracts-20261028-01/failure.json)
  preserves one lint finding in the missing-class probe before native/test
  execution. Passed the class name through a variable to retain the source
  factory's dynamic getattr form. No physical equation, state contract or
  numerical budget changed. A guide wording fix identifies Phi as a rate
  prefactor, consistent with the already declared effective tau equation.
- The Chief began versioned coupling integration and requested stable equations
  before completing its independent checks. Froze and sent the production
  source SHA `a84b6caedd53e586da3aae73c2f3f8b26815625b878f6656d197271c12bb5560`
  and scalar oracle SHA
  `20bc3e32f5760c90c4ede2ba5dfebf031e7c1f9b957a30bb0c94aeca3a2f57ff`.
  Native checks subsequently confirmed all thirteen selected classes run.
- [Clean host/native result](/mnt/workspaces/Cells/morris-lecar-contracts-20261028-02/result.json):
  **138 passed, zero failures/errors/skips**, with two compiled prototypes
  deselected, in **12.71 seconds**. All **369** output hashes verified; the
  fifteen owned/dependency snapshots show no within-run source drift. Result
  SHA-256 `3074688c30ab17a497db4435fcf8043da8c6745cc5eaa609f0240dc1619c8d56`.
- Actual-source checks passed thirteen ordinary groups, thirty-nine targeted
  groups, five dynamic backward-Euler clamp groups and eight instantaneous
  step groups, including dt0, in **2.28 seconds**. Selected classes have zero
  native failures. The stale-comment Kv_ML2 lookup failure remains separate.
  Full twelve-effective-tau slow-law phases last **8.91207271 s** depolarized
  and **1.53200722 s** recovering; no physical horizon was truncated.
- All **ten** dynamic continuous RK4 refinements pass with observed order
  **4.11084**. Hybrid state sizes, exact absent zeros, source HCN signs/species,
  scalar/type/domain rejection, actual six-world broadcasts and no algebraic
  clocks passed. Host guard peak **178,900,992 bytes** and minimum host memory
  **21,110,554,624 bytes** satisfy the assigned limits.
- Chief explicitly authorized exactly two CPU7 JAX checks conditional on these
  meaningful host/native results. With that condition satisfied, launched only
  the hybrid array/domain/vmap and analytic-derivative prototypes in a fresh
  output directory. Production/reference remain frozen. No shared edits or
  additional source captures/audits/GPU work were started.
- [Final compiled result](/mnt/workspaces/Cells/morris-lecar-contracts-20261028-03/result.json):
  **two passed, zero failures/errors/skips**, with 138 host cases deselected,
  in **7.36 seconds**. Eager/JIT/vmap hybrid targets/effective clocks, exact
  absent slots, strict state/code/empty-input rejection and NumPy-equivalent
  initialization/opening/RHS passed. Analytic target/tau/opening/RHS voltage
  derivatives and dynamic-state Jacobians preserve five kinetic and eight
  instantaneous semantics, including the source HCN sign. Together receipts
  cover all **140** component contracts.
- Final [inputs](/mnt/workspaces/Cells/morris-lecar-contracts-20261028-03/inputs.json),
  [test receipt](/mnt/workspaces/Cells/morris-lecar-contracts-20261028-03/tests.xml),
  [test log](/mnt/workspaces/Cells/morris-lecar-contracts-20261028-03/pytest.log)
  and [guard](/mnt/workspaces/Cells/morris-lecar-contracts-20261028-03/pytest-guard/result.json)
  remain external. Peak **285,446,144 bytes (272.22 MiB)** and minimum available
  host memory **21,863,026,688 bytes** satisfy 1-GiB RSS and 8-GiB reserve;
  process-tree RSS also bounds individual RSS and PSS. CPU7/BLAS1, CPU-only
  JAX and disabled persistent compilation cache match the authorization.
- Verified **all 369 host and 70 JAX output hashes**. All fifteen sources/
  dependencies were identical between the two passing receipts, with no
  within-run drift. Six final executable/test/reference/protocol/probe/runner
  files still match both snapshots, including the production/scalar hashes
  supplied before coupling validation. The previous worker runner remains
  frozen; the new wrapper reuses its helpers and the established live guard.
- After the completed checks, the Chief requested integration wording in the
  new guide. Updated only that documentation to name tissue@11/calcium@10/
  calcium_energy@4, 53 laws/60 fixture populations, retained 19/34/38 fields,
  five m-only/eight stateless laws and exact absent packed zeros. It links the
  Chief-owned shared-catalog section and PROGRESS without claiming integration
  pass results. This requested guide update is the **sole** final owned-file
  difference from the test snapshots; no retest or source capture was needed.
  Final guide SHA:
  `d89fe68d7176e9d3c0f3874962f69f76f6782393332fcc95dbcf23f73384cd51`.
- Whitespace checks passed. Final JAX result SHA-256:
  `219401486eb35cc55345f163dc920ed5123e7109b77176260bf8d031ab9a08c0`.
  Sent complete receipts, final hashes, API and the guide-only snapshot
  distinction to the Chief. Production/scalar source remains frozen at the
  previously supplied hashes; the full standalone delivery is now frozen.
- No shared catalog/schema/model/PROGRESS edits, extra audits/qualifications,
  GPU launch or detached-job status poll follow from this completed assignment.
  The separately captured wound failures remain a source-limit note, without
  an invented wound feedback component.

## Prescribed repair with the 53-law catalog, 2026-10-28

- Chief assigned fixed-geometry `resolved_repair@4` over owned calcium@10 and
  tissue@11: 53 laws, 60 fixture populations, 39 state fields. Versions@1/@2/@3
  retain their current definitions. Chief owns all shared wiring and PROGRESS.
- Own edits are confined to `surface_repair_spec.py`, `surface_repair.py`, the
  new Morris–Lecar repair facade, newly named fixtures/reference/tests/configs,
  this log and a new worker runner. Prior component and runner files stay frozen.
- Parent projection and layout preserve the current free-calcium catalog while
  reusing the prescribed injury equations. Injury remains selective Na/K only;
  no structural repair energy, native wound feedback or physiological recovery
  claim is added.
- Host/reference checks include conservation, mixed 0/1/2 gate contracts,
  controls, compatibility, ordinary and assembly checkpoints/report metadata.
  Scalar opening and resealing checks each cover twelve time constants and are
  explicitly separate from 50-us coupled development. Chief owns subsequent
  compiled validation after receiving stable sources.
- Assigned runtime policy: CPU7, one thread, <=1-GiB process-tree RSS and
  >=8-GiB available-memory reserve. New artifacts go under
  `/mnt/workspaces/Cells/morris-lecar-repair-*`; no GPU or long job is launched.
- Implemented the distinct repair subtype/layout/facade and preserved the
  39-field injury law over calcium@10. Added the requested independent @4
  binding and established segmented DOP853 entry point without editing older
  references. All channel/injury intervention boundaries are retained.
- Created and checked the two source configurations:
  [ordinary](../../configs/resolved_morris_lecar_repair.json), SHA
  `123efb013107dffec126694fc81c90a7388450aca2e6d811681597d1c114fdf2`, and
  [assembly](../../configs/assembly_morris_lecar_repair.json), SHA
  `e55d7533168956dc91371d7edb1e03465006749bd86a749bcf5cbb6bc0d2a650`.
- Preserved all failed receipts under the assigned external prefix:
  [01](/mnt/workspaces/Cells/morris-lecar-repair-host-20261028-01/failure.json)
  stopped before tests on two long lint lines;
  [02](/mnt/workspaces/Cells/morris-lecar-repair-host-20261028-02/failure.json)
  passed 50 cases with two numerical-guard fixture errors;
  [03](/mnt/workspaces/Cells/morris-lecar-repair-host-20261028-03/failure.json)
  passed 51 cases, with the larger patch still below the injury loss limit;
  [04](/mnt/workspaces/Cells/morris-lecar-repair-host-20261028-04/failure.json)
  passed 51 cases, while the unsafe geometry correctly triggered the parent
  CaV guard before the injury-specific guard. No physical equation or numerical
  tolerance changed to correct these test premises.
- Isolated the injury loss case by setting dedicated CaV permeability to zero
  in that test only. The test first proves `dt * injury_loss_bound > 0.25` and
  that the projected parent accepts the step. The injury guard then rejects.
  [Targeted 05](/mnt/workspaces/Cells/morris-lecar-repair-host-20261028-05/result.json)
  passed all **three** numerical-guard cases in **5.49 seconds**. At the Chief's
  direction, no full-suite rerun followed this correction.
- The [combined receipt](/mnt/workspaces/Cells/morris-lecar-repair-host-combined-20261028-01/result.json)
  proves **52 distinct passing host/reference contracts** from 04's 51 passing
  cases plus 05's three passing cases, with two overlaps. All other test
  functions are AST-identical between those snapshots. It verifies **3,366**
  artifact hashes, all nine final owned source hashes, and no shared/owned
  source drift. Combined receipt SHA-256:
  `d7584c6d62a26d21b4f135b2dbd97e6c8c6c971e2c5ce9f90e39f6ef13c01d5e`.
- Eight independent full-stage cases compare all 39 fields, field potentials
  and first-law balance using the existing `rtol=3e-10`, `atol=3e-12`,
  charge `atol=3e-23` and energy `1e-9` budgets. Largest normalized stage error
  is **9.69294e-6**. Controls, owned free-calcium sensing, gate counts and exact
  absent zeros, sham bitwise parent reduction, earlier repair versions,
  ordinary observers/reports and complete assembly checkpoints also passed.
- Three scalar clock cases start at damage 0, .25 and 1, each covering twelve
  opening time constants (**0.5 ms**) and twelve closure time constants
  (**3 ms**). Full traces and opened/closed ledgers refine at 32/64/128 steps;
  minimum observed order is **4.11083**, largest coarse trace error
  **6.8663e-5**. This evidence concerns the prescribed scalar clock, separate
  from 50-us coupled development and any biological recovery claim.
- Final combined guard peak RSS is **236,793,856 bytes (225.82 MiB)** and
  minimum available memory **19,616,436,224 bytes**. CPU7, one-thread settings,
  CPU-only arrays, no JIT checks and disabled persistent caches match the
  assignment. Process-tree RSS also bounds individual RSS/PSS.
- Froze the five scientific files, tests, runner and both configurations and
  sent source hashes, both receipts and all failure attempts to the Chief.
  Chief accepted the host checks and started its separately owned compiled
  validation. Shared PROGRESS/docs/planning remain Chief-owned. No further
  checks, audit, GPU work or detached-job status poll follow this handoff.
- Chief subsequently reported the combined batch complete: **166 distinct
  checks**, including our 52 repair host contracts and two Chief-owned repair
  compiled checks. The complete 39-field repair trajectory passed at **0.33913**
  of its error budget with **3.59088e-16 pJ** energy residual, exact absent
  gates and final checkpoint. These are Chief-reported compiled results;
  this worker launched no additional computation.
- Chief's [final development receipt](/mnt/workspaces/Cells/morris-lecar-water-development-20261028-01/development-result.json)
  SHA-256 is
  `aa919eb7fdef5c8ba12346effa4d4c9f99f66701108cfcf31ad0f7a2b1bdbb65`.
  Chief verified the 3,366 host artifact hashes and merged coverage, and
  completed canonical PROGRESS/docs/configs. Further feature work awaits
  the user's next instruction; no follow-up job was launched.

## Owned chemical cytosol and compliant water, 2026-10-28

- Chief relayed a new user go and assigned `resolved_calcium_water@1`, with
  maintained ATP, owned calcium@10/tissue@11 and fixed ER volumes. Chief owns
  finite-fuel/water, all shared wiring, canonical PROGRESS/docs, assembly
  integration/planning and compiled checks. This worker owns only new spec,
  model, fixtures, independent reference, host tests, configs and worker runner.
- Sent and received approval of the volume/particle/free-energy contract before
  implementation. Each cell water volume equals its chemical cytosol volume;
  ER volume, interface areas and capacitor parameters stay fixed. Every distinct
  cytosolic chemical species counts once; a bound complex is one particle.
  Outside free ions are mapped into that species table once. Extra inert solute
  is explicitly additional; fixed charge and maintained ATP are not particles.
- All rates use current cytosol/exterior concentrations, current chemical
  cytosol volume and current IP3 concentration/weights. Batched assembly IP3
  readouts use each world's volume. The Chief requested effective-layout use
  for the ensemble-voltage callback as well; implemented it.
- Endpoint energy retains binding standard potentials and fixed ER chemical/
  capacitor energy. The parent reference-volume balance gains exact current-
  particle dilution, extra inert dilution, compliance energy and water heat.
  Chemical solute mixing is not added twice. Stage directional derivatives
  and an independent Decimal endpoint oracle will check this composition.
- Closed integer moieties bound the maximum particle inventory, including
  IP3 conversion/binding source and sink directions. Initial particle count
  alone is not a bound. Unsupported open material sources are rejected by the
  closed parent schema. Chemical loss bounds use minimum allowed volumes;
  the existing water relaxation bound and stage rejection also apply.
- Exposed the proposed parser/model/control APIs to the Chief. Created
  `surface_calcium_water_spec.py`, `surface_calcium_water.py`,
  `calcium_water_fixtures.py`, `calcium_water_reference.py`,
  `test_surface_calcium_water.py`, two source configs and a new worker runner.
  Old repair/channel files and runners remain frozen. Source scope is 38
  fields, 53 laws/60 populations; no new biological or native trajectory claim.
- CPU7 bounded host probes are underway with <=1-GiB process-tree RSS,
  >=8-GiB reserve, one thread and external `/mnt/workspaces/Cells/calcium-water-*`
  evidence. Initial receipt 01 retained lint-only failures before tests.
  The Chief's four integration tests cover assembly/compiled/planning work;
  removed duplicate assembly checkpoint checks from this worker's host suite.
- [Identity receipt 02](/mnt/workspaces/Cells/calcium-water-host-20261028-02/result.json)
  passed two host declaration/initialization cases. The first main host run,
  [03](/mnt/workspaces/Cells/calcium-water-host-20261028-03/failure.json), passed
  55 cases and retained three failing padding-test premises: the reused catalog
  helper padded channels only, so those tests had touched real cells/patches.
  Corrected only the new fixture to pad all six ionic capacities plus chemical
  and reaction capacities, and regenerated the two new source configs.
- [Host 04](/mnt/workspaces/Cells/calcium-water-host-20261028-04/result.json)
  passed **58 cases** in **30.42 seconds**, with actual compact/padded storage,
  mixed gate populations, thirty valid independent stages and two expected
  sealed-history rejections. Binding particles, IP3 source/sink conversion,
  current-volume batched readouts, domains, bounds and ordinary artifacts passed.
  No physical equation or previously frozen tolerance was changed to correct
  the fixture premises. Initial lint failure 01 is also preserved externally.
- [Host 05](/mnt/workspaces/Cells/calcium-water-host-20261028-05/result.json)
  passed the two remaining scientific checks. The **20-us full 38-field NumPy
  trajectory** agrees with independent segmented DOP853 at **0.00466881** of
  its state budget. Maximum energy residual is **3.01191e-16 pJ**, water-ledger
  error **2.16840e-19 pL**, material error **2.84364e-21 fmol** and capacitor
  charge error **5.05364e-29 C**.
- The isolated water check freezes the actual cytosol chemical-particle table
  and finite outside ions. It covers **twelve physical water time constants**:
  tau **0.0306785244892 s**, horizon **0.368142293870 s**. Production RK4 agrees
  with independent adaptive water evolution, retains positive bounded volumes,
  and approaches **[1.66270717, 4.33729283] pL**. Largest energy residual is
  **2.14465e-7 pJ**. Full traces/inputs are retained; this is separate from a
  full chemical/ER relaxation or any physiological equilibrium claim.
- The endpoint derivative check was strengthened to `rtol=2e-10` from the
  initial new-test `2e-6`, retaining `atol=2e-5 pJ/s`, so small binding-dependent
  `Ndot * log(V/V0)` terms remain resolved beneath large water power.
  [Targeted 06](/mnt/workspaces/Cells/calcium-water-host-20261028-06/result.json)
  passed its **three** cases in **6.11 seconds**; largest derivative error is
  **7.81030e-7 pJ/s**. No full-suite repeat followed this strengthening.
- The [final combined host receipt](/mnt/workspaces/Cells/calcium-water-host-combined-20261028-01/result.json)
  maps XML cases to the latest final source and proves **60 distinct passing
  contracts** (58 + 2, with the three stronger derivative cases superseding
  their earlier passes). All selected test functions match final ASTs, and all
  helpers/module globals are unchanged. It verifies **5,086 artifact hashes**,
  all eight final owned hashes and zero within-run source drift. Receipt SHA:
  `008cbea6892858f11b8e49acd87c8d0bc1a612b2e1bcfe5131180dc94442365d`.
- Production core/model/fixture/reference and both configs are identical across
  the final three receipts. Scientific sources were sent stable before Chief
  compilation; the only subsequent edit strengthened the worker test budget.
  Final science hashes and config hashes are all in the combined receipt.
- Peak worker process-tree RSS **234,631,168 bytes (223.76 MiB)** and minimum
  available memory **19,105,202,176 bytes** meet the assigned 1-GiB/8-GiB limits.
  CPU7/one-thread execution, CPU-only host arrays and disabled caches were used.
- Chief reported its separate assembly/checkpoint/planning host checks and
  two-world compiled stage passing; its 50-us compiled trajectory is separately
  owned and active. Sent the complete frozen handoff for the final collector.
  Shared PROGRESS/docs remain Chief-owned. No further scientific jobs, audits,
  regressions, GPU work or detached-job polling follow this completed worker
  assignment.

## Independent joint finite fuel / chemical cytosol / water, 2026-10-28

- Chief relayed another user go and retained ownership of production, shared
  wiring, fixtures, ordinary/integration tests and docs. This worker owns only
  new `calcium_energy_water_reference.py`, its independent test module, a new
  bounded runner and this log. Existing scientific files/runners stay frozen.
- Reviewed the thermodynamic/ownership contract before coding. Joint model is
  `resolved_calcium_energy_water@1`, 43 fields, with both explicit particle
  coupling declarations. Chemical cytosol particles count once, with three
  separately owned neutral fuel particles; fixed ER has no water route.
- The oracle rebinds all three pumps at live fuel amounts and current physical
  cytosol volume, retaining the 1-M/1-mM standard-state bridge. Endpoint G owns
  molecular, fuel, capacitor and compliance energy once. Pump work is internal;
  regeneration is external. Signed pool volume work is a diagnostic subledger
  subtracted in pool accounting and excluded from total-system work.
- Chief supplied 23 serialized cases in its external reference-inputs folder.
  Each worker receipt copies/hashes those inputs. The separate adaptive and
  physical-time checks will retain manufactured-input changes explicitly.
- Initial reference smoke passed. After Chief review, added negative water/
  regeneration heat, sealed-route/unsupported volume-work history, shared-volume
  and state-length checks. No valid material rate changed. The oracle froze at
  SHA `74345b57009cc75e4cd53703b7de09a92656c0857cf5f683aba13efb88cef522`.
- Receipt 02 passed 14 smoke/negative-domain cases. Broad 03 passed 73 of 76:
  all frozen stages and material/energy invariants passed; one test had assumed
  unchanged global node potentials after changing free Ca, rather than checking
  conserved capacitor voltage/charge. Corrected the test to permit the physical
  resistive-field response; particle pressure cancellation then passed in 04.
- Endpoint differences at too-small steps amplified rounded bulk amounts.
  Receipts 03/04/05 preserve all failures and geometric tables. Extending to
  larger, domain-safe steps shows second-order convergence, then roundoff grows
  as `1/h`. Acceptance retains `rtol=2e-10`, `atol=2e-5 pJ/s` and requires three
  adjacent passing differences, with chemical/fuel/volume/gate bounds checked.
  This correction changes test numerics only; oracle/production remain frozen.
- Chief's 48 production/integration/compiled checks have passed, including its
  full 50-us 43-field trajectory. This worker is completing the separately
  authorized short independent refinement and reduced physical fuel/water
  relaxation on CPU7 with 1-GiB RSS / 8-GiB reserve, without GPU or shared edits.
- The final derivative table demonstrates coarse orders **2.00181 / 1.97801**
  for initial/perturbed states. Adjacent **1.6 / 0.8 / 0.4 us** differences pass
  the unchanged budget. All twelve geometric steps, both sides of the rounding
  plateau, positive-domain margins and raw errors remain in the evidence.
  The oracle stayed at its frozen hash throughout these test corrections.
- Receipt 06 stopped before scientific execution on one long lint string.
  Receipt 07 completed the corrected assertions and short refinement, then its
  planned **180-second** guard stopped the reduced Radau/Decimal calculation.
  RSS was **104,161,280 bytes**, available memory **19,136,049,152 bytes**.
  Preserved its resource-stop/failure and partial evidence; no manual stop or
  shortened physical horizon was used.
- Optimized only the reduced test integration: independent scalar log/tanh
  algebra with explicit DOP853, bounded by the fastest measured eigenvalue,
  then checked against eighty-digit water/regeneration oracles at every saved
  trajectory point. Kept the original physical horizon, positive coordinate
  transform, two refinements, material and energy tolerances. Plan, eigenvalues
  and each refinement profile are written before acceptance checks.
- [Final selected receipt 08](/mnt/workspaces/Cells/calcium-energy-water-reference-20261028-08/result.json)
  passed all **five** remaining cases in **51.49 seconds**. Its two reduced ODE
  solves took **0.566 / 0.762 seconds**, **3,509 / 6,305 evaluations**; the rest
  includes the full Decimal checkpoint and endpoint validations.
- The actual-parameter reduced pair has eigenvalues
  **[-26.11432694, -21.07451566] /s**, slow tau **0.04745067531 s**, transit
  allowance **4.07169884826 s**, and a **4.64110695198-s** horizon containing
  another twelve slow time constants. Both curves reach volumes
  **[1.66855565, 4.33144435] pL** and ATP/ADP/Pi
  **[3.19544154, 0.00455845528, 0.00455845528] fmol**. Maximum joint-energy
  errors are **3.26507e-11 / 5.13611e-12 pJ**; pool-internal errors are
  **2.19558e-12 / 1.04139e-13 pJ**. Exact chemical particles are frozen, with
  fixed ER/capacitors, absent pumps and other ports omitted. This demonstrates
  the declared reduced process's physical time, not full-cell settling.
- The separate **2.5-us full 43-field** adaptive refinement passed at
  **1.32811e-6** of its state budget, with **83 / 98 evaluations**. It preserves
  off-grid channel/regeneration/water control splits, total material, adenylate,
  phosphorus, signed internal pool-volume work and water. Maximum whole-energy
  error is **2.92451e-12 pJ**, pool-internal error **4.59149e-15 pJ**.
- [Combined independent receipt](/mnt/workspaces/Cells/calcium-energy-water-reference-combined-20261028-01/result.json)
  proves **78 distinct passing contracts** from 03's 73 passing cases and 08's
  five passing cases. It maps XML cases to final AST bodies, retains every
  attempt 01--08, verifies **3,472 output hashes**, binds the identical **23 raw
  inputs**, and records no within-run source drift. SHA-256:
  `40ffb48bb0966fb44e5e7a97baa779d9e6e582f3dde633e81c2786c4c55e6c85`.
- Final selected guard peak RSS **98,766,848 bytes** and minimum available
  memory **19,591,254,016 bytes** meet the assigned limits. The independent
  child imports no production Cells or JAX modules. The new oracle, tests and
  runner are frozen; all earlier scientific/reference files remain untouched.
  Sent the full handoff for the Chief's 126-check final collector. No further
  scientific job, follow-up audit or regression is launched by this worker.

## Independent prescribed repair on the joint model, 2026-10-28

- Chief relayed the next user go, with BETSE compatibility prioritized before
  Jupiter. Chief owns new production/core/wiring/root tests/config/docs/PROGRESS.
  This worker owns only new joint-repair fixtures/reference/independent tests,
  a new bounded runner and this log. Previous scientific files stay frozen.
- Proposed and received confirmation of `resolved_calcium_energy_water_repair@1`:
  parent joint 43 fields plus the existing five damage/lesion ledgers. Exact
  injury patch/control schema, Na/K(+1)-only GHK, fixed ER/interfaces, current
  cytosol/exterior volumes and no structural ATP cost or free-energy term.
- Created 15 fixture arms with compact/full padding and a mixed-control probe.
  Stress arms begin with a .25 lesion on patch zero; no-injury/sham retain zero
  initial damage. The coupled horizon is 50 us at .625-us steps, with injury
  changes at 5.3 and 15.3 us. Assembly observations stay on nominal ticks.
- Oracle composes the frozen joint reference, adds explicit scalar lesion
  flux/heat/material/charge, preserves direct parent fuel/water/gate rates, and
  checks damage/opened/closed and route-support ledgers. Endpoint G is exactly
  the parent G; no damage-dependent structural energy is invented.
- Chief provided 31 parser-serialized raw inputs and independently matched the
  current full 48-field rates in its host comparisons. Worker receipt 01 stopped
  before science on two lint-only findings; corrected them and retained the
  failure. First bounded smoke receipt 02 is running before the source freeze.
- Planned independent checks include Decimal source-law GHK, exact parent
  reduction, live-volume material/energy accounting, off-grid short refinement,
  lesion/water/fuel endpoint derivative, negative histories/definitions, and
  separately scoped twelve-tau opening and closure clocks at actual rates.
  CPU7/one thread, <=1-GiB process-tree RSS, >=8-GiB reserve and external
  `/mnt/workspaces/Cells/calcium-energy-water-repair-*` artifacts apply; no GPU.
- The first smoke passed, followed by all **88** broad independent contracts
  in receipt 03 (**35.13 s**). Added five scoped checks without changing the
  frozen valid oracle (SHA `b1e2ce8b7e3d684ace8b302369f701bc44181651c2722ef99dad02b364f356ce`).
- Receipt 04 passed the endpoint derivative and all three twelve-tau scalar
  clocks, then its **180-s wall guard** stopped the full48 refinement. The
  first **20-us / 520-evaluation** profile and all resource/failure evidence
  remain intact. The endpoint table gives coarse order **1.98804**, with
  adjacent **1.6 / 0.8 / 0.4 us** differences within the unchanged tolerance.
- The same five checks are rerunning in receipt 05 with a **540-s** attached
  command allowance. Equations, actual 20-us horizon, two refinements,
  tolerances, CPU affinity and memory/reserve limits are unchanged. The new
  runner now accepts an explicit command allowance from 1 through 540 s.
- Chief relayed the user's larger, separate feature-stream preference: finish
  this repair receipt, then own configurable native BETSE network transport
  end-to-end. Chief owns HCN expansion and shared integration. Messages are
  limited to the final repair receipt, blockers/shared needs and substantive
  transporter handoff. New ownership: `src/cells/processes/betse_network_transport.py`,
  `validation/transport/betse_network_transport*`, matching new unit tests and
  own workfiles. Existing cotransport/dispatch/docs/PROGRESS stay untouched.
- [Selected receipt 05](/mnt/workspaces/Cells/calcium-energy-water-repair-reference-20261028-05/result.json)
  passed all five remaining checks in **371.46 s**. The unchanged **20-us**
  two-resolution full48 calculation uses **520 / 1,000 evaluations**, with
  maximum state error **7.64033e-7** of its budget, whole-energy residual
  **1.25370e-12 pJ** and internal pool residual **7.00308e-15 pJ**. Injury
  changes remain at the actual **5.3 / 15.3 us**. Memory peak **100,294,656 B**,
  minimum available **17,193,050,112 B** meet the original resource limits.
- All three scalar clocks (initial damage 0/.25/1) span **0.5-ms opening plus
  3-ms closure**, twelve actual time constants each. The finest maximum trace
  error is about **2.133e-7**, with convergence orders **4.2196 / 4.1108**;
  damage bounds and opened/closed histories pass. Other43 fields are frozen
  in these clock calculations; they are not full-cell settling or recovery.
- [Combined repair receipt](/mnt/workspaces/Cells/calcium-energy-water-repair-reference-combined-20261028-01/result.json)
  binds **93 distinct passing contracts**, all **31 input hashes**, unchanged
  case/helper ASTs and frozen dependencies, and verifies **3,521 output hashes**.
  SHA `657d75608565ed7e3ed3faec4144763e107358913473e97b117a2dd22e8e7919`.
  Preserves attempts 01--05; only the new runner's optional wall allowance
  differs between the selected receipts. Metadata assembly's first permission
  review timed out before process creation; the permitted single retry passed.
  Final handoff sent to Chief, whose 46 integration checks and full50us final
  checkpoint also passed. Repair files are frozen; no further repair job starts.

## Configurable native BETSE transporter component, 2026-10-28

- New independent feature stream authorized by Chief on the user's behalf;
  CPU7, <=1-GiB process-tree RSS, >=8-GiB reserve, external outputs, no GPU.
  Chief owns HCN/shared integration. Existing cotransport and scientific
  references/runners remain frozen. Root PROGRESS stays Chief-owned.
- Read the pinned `networks.py` and template in BETSE 1.5.0 at revision
  `5269a714aa2593ed2a6708c4516289977d8ae1a2`. The actual executable generator
  omits product saturation, uses `1e-3*c**n` in Q, and ignores configured
  regulator zones and star voltage requests for transporters. Captures execute
  actual `default_zones`, `get_influencers` and `write_transporters` ASTs.
- Added a versioned NumPy/JAX component, independent Decimal reference, raw
  fixtures, authenticated native capture and targeted tests. The protocol
  resolves concrete native-expression ambiguity rather than adding a generic
  design stage. Explicit owner updates convert density*area to fmol/s; source
  outward current follows native net_z. Generic reaction conversions require
  charge balance; extra moiety ownership belongs to the composing model.
- Native direct inhibitors may produce negative regulation. No physical heat,
  ATP, water or solvent term is inferred. Malformed reversible expressions with
  no transfer term and unsupported direct-inhibitor ordering are captured as
  source limits and rejected by the binder. Native geometry/update/full-tissue
  equivalence remains outside this component's source correspondence claim.
- Attempt 01 exposed an additional actual generator failure: simultaneous
  only-direct activators and only-direct inhibitors leave `()` in the native
  expression and raise TypeError. Preserved the generated string and failure,
  added a binder rejection, and retained a valid mixed direct/Hill fixture.
- Attempt 02 captured all **39 native expressions** and **three known native
  failures**. Its host checks exposed singleton temperature being expanded and
  then incorrectly rebound in the trial predicate; fixed that shape handling.
  Two near-stall checks had incorrectly used a density tolerance for log Q;
  added the separate dimensionless roundoff budget. Material-history checks now
  use the already declared fmol tolerance. Density, energy and charge keep
  their own units/tolerances; all original failures remain available.
- Attempt 03 passed **113 host checks** and three CPU JAX checks; the fourth
  exposed a NumPy index array entering compiled deterministic scatter. Converted
  those indices through the selected backend. Added finite-output/malformed-axis
  rejection and empty-route raw-parameter cases before final qualification.
- [Final component receipt 04](/mnt/workspaces/Cells/betse-network-transport-development-20261028-04/result.json)
  passes **123 tests: 119 host / four CPU JAX**, plus the **39 actual native
  captures / three expected native failures**. Native/host/JAX guarded phases
  take **0.763 / 2.522 / 6.559 s**. Peak process-tree RSS is **347,062,272 B**;
  minimum available memory **21,177,835,520 B**. All source snapshots stayed
  unchanged during checks. Native capture proves no Cells/JAX imports; the
  compiled evidence records CPU devices, raw batch outputs, invalid-world
  rejection, near-stall gradient and empty-route behavior. No GPU ran.
- [Frozen handoff receipt](/mnt/workspaces/Cells/betse-network-transport-handoff-20261028-01/result.json)
  verifies **161 component artifact hashes**, binds all seven final owned source
  files and authenticated upstream source, preserves attempts 01--04, and freezes
  the [integration contract](/home/robert/Cells/agent-work/cells-worker-01/workfiles/BETSE_NETWORK_TRANSPORT_HANDOFF.md).
  SHA `b242aeb5ea1cdc4e283e78522889e2a9b9d11c41a3c114211cfbef11724debb5`.
  Production process SHA `6004e87b44d99d9ede041358add93493347f863b4002bcd58fde4d885fa83726`;
  component result SHA `464a4766e8dd2b8bd1f8090328cf4952b563684c122c20e2e8be5f9b35ac7922`.
- The component and scientific evidence are frozen. Integration contract states
  native Q/product-Km/regulator quirks, current/owner signs, batch and padding
  requirements, physical-energy exclusions and the source failures. Shared
  dispatch/schema/docs/PROGRESS remain untouched. Final handoff is sent to Chief;
  no follow-up computation, regression, audit or detached job is running.

## Native BETSE mitochondrial ion/voltage component, 2026-10-28

- Chief assigned the next separate feature after transporter handoff. Own only
  new `src/cells/processes/betse_mitochondria.py`, matching organelle validation
  and unit-test prefixes, own workfiles/log. Chief retains shared integration,
  documentation and root PROGRESS. CPU7/one thread, <=1-GiB process-tree RSS,
  >=8-GiB reserve and external evidence remain required; no GPU. Only final
  handoff or substantive blockers go to Chief.
- Read pinned `organelles/mitochondria.py`, actual `electroflux`/`get_charge`,
  network initialization/run-loop/removal/redefinition callers, simulator call
  order and parameter defaults. Native Mito snapshots half cell volume/area,
  copies cytosolic concentrations, initializes Q/V caches to zero and all three
  diffusivity arrays to 1e-19 m2/s. Cytosolic update retains full cell volume.
- Each ordered moving ion uses incoming cached voltage. The actual helper
  mutates that voltage by a 1e-25 nonce before each flux; charge/voltage refresh
  occurs after all explicit Euler ion updates. Extra charge density is supplied
  by the caller. No active channel, Ca uniporter or ATP synthesis exists in
  this class. The optimizer's -150mV override is separate from constructor init.
- The protocol addresses concrete source risks: raw missing extra_rho, nonce
  singularity, incomplete extra-charge deletion, caller reinitialization and
  low-precision synthetic inputs. Planned pure NumPy/JAX API preserves cached
  timing, finite amount ownership and native geometry. Invalid predicted trials
  reject without clamping. An analytic neutral two-volume check will resolve
  geometry/diffusivity units at the actual physical time, separately from any
  full-cell settling claim.
- Pinned parameter source defines **F=96485 / R=8.314**, rather than the repo's
  modern SI constants. Exposed both as per-world singleton inputs with native
  defaults, and captured a deliberate SI override. Reported this concrete
  integration distinction to Chief for the earlier frozen transporter; Chief
  acknowledged supplied-constant correspondence and retained frozen files.
- [First bounded component receipt](/mnt/workspaces/Cells/betse-mitochondria-development-20261028-01/result.json)
  passes **85 tests: 81 host and four CPU JAX**. Actual native Mito and helper
  ASTs pass **21 valid configurations**, the **0.012-s** controlled multi-ion
  sequence, complete-state restart and three neutral physical profiles. The
  independent oracle imports no Cells/NumPy/JAX; the native capture imports no
  Cells/JAX. All source snapshots remain unchanged during execution.
- Retained **seven source limitations**: absent extra_rho at get_v; absent
  extra_rho after partial update mutation; nonce alpha=0; untrimmed extra charge
  after deletion; integer minimum-D truncation; float32 precision loss; and
  unguarded negative Euler outputs. Source bytes, line ranges, inputs, states
  and exceptions/nonfinite outputs are retained. No inactive comment became an
  ATP, Ca uniporter, channel or respiratory mechanism.
- The reduced neutral pair uses actual default D and geometry. Its tau is
  **50,000 s**, horizon **600,000 s** (twelve tau), with native/component steps
  tau/32, tau/64 and tau/128. Maximum trace errors are
  **0.0776554 / 0.0385722 / 0.0192230 mM**; observed Euler orders
  **1.00952 / 1.00473**; maximum material residual **5.32907e-14 fmol**.
  This resolves half-volume/area and D/thickness units for one neutral finite
  pair, without claiming all-ion organelle or full-cell settling.
- Native/host/JAX guarded phases take **1.014 / 6.288 / 10.330 s**. Peak RSS
  **367,468,544 B**, minimum available memory **18,979,463,168 B**, CPU7 and
  one-thread operation meet all assigned limits. CPU-only compilation covers
  batching/padding, singular-world isolation, scan/restart and external-charge
  voltage differentiation. No GPU, detached job or persistent cache was used.
- [Frozen metadata handoff](/mnt/workspaces/Cells/betse-mitochondria-handoff-20261028-01/result.json)
  verifies **143 artifact hashes**, binds all final owned sources/upstream
  captures and freezes the [owner/energy integration contract](/home/robert/Cells/agent-work/cells-worker-01/workfiles/BETSE_MITOCHONDRIA_HANDOFF.md).
  SHA `1ff9bd3aa35d725278d3bceaaee4a5270f7b3fc792fa46453ea19b383140d06b`.
  Process SHA `a062869889c218284cf953d668477e40d2fa7a99ab15c2e4b08a0c2383d0b83d`;
  component result SHA `9551e3ba7b3b43c5992f162408bd46b0990d49c298712d7189488c72f552cb45`.
- Contract distinguishes native copy allocation, cached voltage and external
  charge work, physical SI/native constant choices, paired amount signs and
  discrete Euler timing. No heat/ATP/water ledger is inferred. Shared files and
  earlier scientific evidence remain untouched; final handoff sent to Chief.
  All new scientific files are frozen; no follow-up computation or audit starts.

## Native cutting and conservative topology remapping, 2026-10-28

- Chief assigned the next larger feature after mitochondrial handoff. Own only
  new `src/cells/processes/betse_tissue_cut.py`, `validation/topology/betse_tissue_cut*`,
  matching unit tests and own workfiles/log. Root owns configurable transport
  integration and all shared files/docs/PROGRESS. CPU7/one thread, <=1-GiB RSS,
  >=8-GiB reserve, external logs/evidence; no GPU. Only blockers/final handoff
  go to Chief. No earlier scientific file or active job is changed.
- Reviewed actual `_cut_cells`, event callers, all geometric/contact/environment
  rebuild methods, DEC `cut_mesh` and its core map/operator rebuilds, native
  diffusion reinitialization and downstream molecular/ER/reset hooks. Native
  cutting infers ownership from array length and a hardcoded special-field set;
  list handling and equal-length axes require explicit failure evidence. Native
  ATP release is commented out. No conservative material ledger is supplied.
- Planned component uses stable cell/membrane/edge/environment IDs and explicit
  ownership axes. It drops owned membranes and incident edges, preserves
  surviving order/identity/orientation, distinguishes contact from abstract
  field edges, and identifies surviving hurt/exposed faces. No new cells/edges,
  mechanical geometry or regeneration is inferred. Operators/layout/checkpoint
  bindings must be rebuilt. Fields retain exact values unless a declared density
  measure changes, in which case amount is preserved and density rescaled.
  Removed contents remain in a named ledger, never silently released to ECM.
- Native capture design uses three manufactured adjacent 4/5/6-sided polygons,
  actual source geometry/contact/environment/Poisson/diffusion methods, and
  actual DEC vertex/edge cut/core operators. Profile-selection hooks are recorded
  explicitly; native Voronoi seeding/full simulation are outside the claim.
  Source reset/ownership/DEC hanging-edge limitations will remain distinct from
  conservative Cells behavior. The mixed geometry also avoids silently repairing
  native rectangular-object-index failures in equal-sided/single-cell cases.
- [Source preflight 01](/mnt/workspaces/Cells/betse-tissue-cut-development-20261028-01/result.json)
  passes all three left/middle/right native cuts. Captures execute actual cut,
  geometry/contact/environment/mask/Poisson/DEC and diffusion-reinitialization
  bodies; only profile selection is a recorded hook. Seven native limitations
  and partially mutated failure states are retained. This receipt is explicitly
  source-only and does not count component unit tests.
- Implemented immutable stable topologies/plans, explicit old/new/removed maps,
  distinct contact/field edge roles, hurt/exposed surviving IDs, linear-size CSR
  owner maps, and explicit field-axis handling. State remains bitwise unchanged
  on survivors; declared quantity/density fields carry removed-owner values,
  quantities and totals. New measures rescale densities while preserving amount.
  Finite/positive measures, float64 quantities and representable results are
  checked before publication. No removed contents are implicitly released.
- Checkpoint metadata binds topology and field-declaration identities, owner
  axes, shapes, dtypes and units. It rejects stale layouts, altered units and
  incompatible declarations. Numerical state, measures, clocks and removed
  ledgers remain caller-owned checkpoint data. All derived field/operator and
  compiled bindings are explicitly invalidated after a real cut.
- [Complete component receipt 02](/mnt/workspaces/Cells/betse-tissue-cut-development-20261028-02/result.json)
  passes **60 tests: 57 host / three CPU JAX**. Independent list/80-digit Decimal
  checks cover graph sizes including empty/singleton layouts, no-op and complete
  removal, signed charge/material accounting, density measure changes, explicit
  equal-size axes, sequential cuts/checkpoint roundtrip, immutable plans and
  rejection without input mutation. CPU compilation covers fixed-plan gathers,
  new-measure density conversion, independent batches and complete removal.
- Actual native topology and owner matrices match the three small cut outcomes.
  The middle cut retains field edge **C>A** without a membrane contact. Native
  diffusion/current resets are observed separately from conservative remapping.
  Captured limitations: empty cut, all removal, single survivor, list-tail loss,
  list-last index error, equal-length global deletion and unknown nested-owner
  state left stale. No native ATP/content-release comment became a mechanism.
- The middle cut archives **[17.82057854, 44.55144635] fmol** from the two ion
  rows, with partition residual at most **7.10543e-15 fmol**. Native environment
  volume rebuilding at unchanged concentration changes apparent material by
  **[1.22000581, 1.83000871] fmol**. Explicit new measures preserve both amounts
  in the conservative policy, with zero residual here and no ECM release.
- Native/host/JAX guarded phases take **2.591 / 1.538 / 3.553 s**. Peak RSS
  **248,418,304 B**, minimum available memory **19,199,733,760 B**, CPU7 and
  one-thread execution satisfy the assigned limits. Source snapshots do not
  drift during checks. The native child imports no production Cells or JAX.
- [Frozen metadata handoff](/mnt/workspaces/Cells/betse-tissue-cut-handoff-20261028-01/result.json)
  verifies **104 artifact hashes**, retains source preflight and full receipts,
  binds all seven owned scientific files/upstream sources, and freezes the
  [checkpoint/owner integration contract](/home/robert/Cells/agent-work/cells-worker-01/workfiles/BETSE_TISSUE_CUT_HANDOFF.md).
  SHA `5f25661a6d3af158984f3e968805c6e4bfdc3f076790e1d6392c562d17219e9e`.
  Process SHA `2ca66f3f0e3c95b210586c85826668ff681579e908ba896e7c11201c868bc0b1`;
  full receipt SHA `e90fed8be76ff2d41b82ac8ad282d38060124f15120908e51acdab4e5a752284`.
- Final handoff sent to Chief. All new scientific files/evidence are frozen;
  shared models/dispatch/docs/PROGRESS and earlier evidence remain untouched.
  No regeneration/mechanics/whole-tissue parity, complete checkpoint migration
  or cut-energy law is claimed. No follow-up computation, regression or audit
  is running.
