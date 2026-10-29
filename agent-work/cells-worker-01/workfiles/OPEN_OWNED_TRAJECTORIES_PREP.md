# Full 8 µs mixed exterior trajectory preparation

Prepared for Chief review and future explicit execution. No numerical role has
run. The purpose is to assess complete trajectory accuracy and timestep
refinement, which the accepted short component probes did not establish.

The current bundle is
`open-owned-trajectories-prepared-20261029-02/`, beside this file. Its
`manifest.json` SHA256 is
`6685de9efd939d9d7ce751ce0aa4cc47859dca2edb48fedbb391a3b85c1f2cfa`.
The machine-readable queue is `open_owned_trajectory_workqueue.json`.

The bundle retains all 1,901 accepted component source files byte for byte and
the 96-check scoped completion receipt. Both exact mixed-case definitions come
from that receipt's hashed stage artifacts. All model parameters, original
control values and clocks, observation times, 8 µs duration and resource quotas
are preserved. Only `execution.dt` changes between production inputs.

Calcium and finite fuel each have six separate roles: standard oracle, tighter
oracle, production at 62.5/31.25/15.625 ns, and comparison. The grids have
129/257/513 accepted samples; all original controls are exact grid members and
the finest grid fits the original 512-step quota. Every production level keeps
all 34/38 physical arrays, padding, controls and layout. Every RK4 trial gets a
strict domain, field and energy check; accepted points also get the original
parent checks and independent conservation checks.

The independent oracles run in separate interpreters and reject Cells/JAX
imports. DOP853 stops at each original control boundary and holds the left
controls through every internal stage. Standard and tighter tolerances sample
the entire finest grid. `protocol.json` fixes accuracy, conservation and oracle
uncertainty budgets. Comparison requires all three production trajectories to
meet accuracy budgets. It reports refinement below resolution without an order
claim when both successive differences are below 1% of budget; otherwise it
requires decreasing differences and order at least three.

Use `commands.json` for exact argument arrays. `runner.py --bundle <bundle>
--check` only checks the frozen inventory. Future execution requires an explicit
single `--job`, Root-selected `--cpu`, `--execute` and fresh `--output` outside
the immutable bundle. Each role uses the existing `run_bounded` supervisor:
480 s, one CPU/thread, 1 GiB child-tree RSS, 8 GiB host reserve, no GPU or
persistent compiler cache. There is no aggregate launcher or automatic retry.

For each family, complete the two oracles and three production roles separately.
Then fill its `*-dependency-runs.template.json` with those five run directories
and supply it to the compare role with `--dependency-runs`. Comparison verifies
completed guard receipts, source/input hashes and full trajectory artifacts;
it never launches a missing dependency. Root controls scheduling and any
detached aggregate work. No automatic polling or follow-up runs are installed.

Numerical exceptions preserve the raw failed trial, controls, physical time,
held-control time and traceback. Progress and accepted prefixes are saved during
the run. A resource stop retains the last durable prefix and supervisor stop
evidence, without accepting an interrupted trial. Error arrays and refinement
metrics are written before a comparison refusal.

All six new Python files pass Ruff and AST checks; immutable inventory and exact
input/grid metadata checks pass. Preparation imported no Cells/JAX modules and
called no model parser, state constructor, RHS or integrator. These checks give
no new numerical accuracy credit. Earlier `...-01/` preparation is retained as
superseded: its unnecessary increase of `max_steps` to 2,048 was removed after
the grid metadata showed that the original quota suffices. It was never run.
