# Full8us scheduled calcium/fuel trajectory preparation

The seven new Python files are statically checked. No numerical role, model
parser, state constructor, RHS or integrator has run. Final bundle sealing waits
for Chief's completed epoch qualification receipt and matching frozen source.
The current machine-readable status and static receipt are in
`open_calcium_bath_trajectory_workqueue.json`. Chief owns PROGRESS.md, numerical
execution and the separate campaign launcher.

The scope is ordinary calcium/fuel SIM8us and full actual INIT8us→SIM8us
calcium/fuel pipelines. The original recipes, native bath ramps, all ordinary
control clocks, 512-step limits, storage caps and physical tolerances remain.
Only execution.dt changes to 62.5ns, 31.25ns and 15.625ns. Metadata inspection of
the accepted ordinary recipes gives exact nested 129/257/513-row grids.

Each of six phase datasets (`ordinary-calcium`, `ordinary-energy`,
`init-calcium`, `init-energy`, `epoch-calcium`, `epoch-energy`) has five
integration roles: `oracle_standard`, `oracle_tight`, `production_dt1`,
`production_dt2`, `production_dt4`. Each has one `projection` role requiring its
two oracles. The two ordinary comparisons require their own six receipts; the
two epoch comparisons require all twelve corresponding INIT and SIM receipts.
There are 40 roles in total. No role launches its dependencies.

Each epoch production resolution uses the exact typed, complete checkpoint
from its own completed full8us INIT job through the qualified handoff bridge.
Each independent tolerance carries its own full8us INIT endpoint. Every
nonclock array remains exact; only phase_clock_s resets. A short component
checkpoint is retained as evidence and never substituted for a full INIT run.
Full INIT and SIM trajectories are compared independently and lineage is
checked against both retained supervisor and child receipt hashes.

The independent DOP853 process imports no Cells/JAX. It uses the qualified
independent full-node/scalar equations, native bath evaluation at every actual
stage clock and ordinary controls held at segment-left. Production uses the
existing classical RK4 with full domain, finite-field and energy checks at all
four stages. Both check original independent material/charge/fuel/work budgets
at every accepted point. Full production states and all observer rows are
written in overlapping recording windows of at most eight steps; only this
recording width may shrink to respect the original trace cap.

All 36/40 complete state fields and all 87/105 ordinary observer channels
(89/107 epoch channels) are compared. Separate projection roles apply the
qualified production observer to independent oracle states. Those roles also
check independent voltage, actual ionic/fuel material, bath/source/work and
conservation identities. This measures temporal/state-to-observer accuracy;
it does not claim an independent derivation of every observer formula.

Each channel must meet the fixed accuracy budget at all three production
steps. Oracle tightening must consume no more than 10% of that budget. Boolean
observations require equality. Timestep differences below 1% of the budget at
both successive refinements are reported as below refinement resolution,
without an observed-order claim; resolved differences must decrease at order
at least three. Raw differences/budgets and metrics are saved before accuracy
or refinement refusal. No automatic retries, shorter horizons or relaxed limits
are supplied.

Chief supplies `--qualification-inputs` to
`prepare_open_calcium_bath_trajectories.py` and a new `--output` directory. The
JSON descriptor has these fields:

- `qualified_source`: `directory`, `expected_files` and `inventory` containing
  an absolute `path` and exact `sha256`; its JSON contains `source_hashes`.
- `receipts`: `ordinary_completion`, `ordinary_components`, `epoch_completion`;
  each has `path`, `sha256`, and nonempty `required_fields` with exact accepted
  receipt counters. Ordinary completion requires
  `total_family_and_adjacent_checks: 103` and `core_window_regression_checks: 53`.
- `evidence`: `ordinary-calcium`, `ordinary-energy`, `epoch-calcium`,
  `epoch-energy`, each with qualified stage JSON `path` and `sha256`. Epoch JSON
  includes the qualified epoch `definition` with its raw source definition and
  scheduled SIM model. The changed-control fixture is the intended epoch case.
- Optional `source_correspondence`: separate completed source/CLI reporting
  receipt with `path` and `sha256`, retained without changing qualified physics.

The preparer verifies every source hash, copies the qualified source, overlays
only the five new trajectory validation modules, and freezes receipts, raw
inputs, protocol, plan, dependency templates and command arrays. No existing
product file is overlaid. `plan.json` has `jobs` and `datasets`; every job has
`role`, `family`, `dataset`, `phase`, `is_epoch`, `requires`, `definition`,
`definition_sha256` and `physics_sha256`. Epoch integrations additionally name
their `parent`. Dataset rows list `integrations`, `oracles`, `production` and
`projection` job IDs.

After sealing, `bundle/runner.py --bundle BUNDLE --check` checks metadata only.
Every future numerical command explicitly selects `--execute --job JOB --cpu
CPU --output NEW_DIRECTORY`, and supplies `--dependency-runs JSON` exactly when
the job has prerequisites. It reuses the existing `run_bounded` supervisor:
one selected CPU, one thread, CPU float64, no JIT/GPU/persistent compiler cache,
480s wall, 1GiB child-tree RSS and 8GiB host memory reserve. Receipts retain
`resource_result` and `qualifier_result_sha256`. Source/input hashes are checked
before and after execution; failures and interrupted prefixes remain durable.
Dependency receipts must also record finite actual elapsed time in [0,480]s
and a positive integer resource sample count. Chunk joins require identical
field dtype/trailing shape as well as exact overlapping values and hashes.

The individual-role runner has no campaign loop, retry, polling or automatic
follow-up. Chief's separately owned campaign launcher handles any explicitly
selected aggregate, detached when expected to last ten minutes or more.
