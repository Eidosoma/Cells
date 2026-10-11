# REF-004b: registered worker-environment correction

D091, 2026-09-14. A launcher-only successor to the frozen
[D090 configuration correction](BETSE_CHANNEL_SETUP_FIX.md). Both earlier
attempts, their sources, configurations, receipts and numerical criteria remain
unchanged. No production, dependency or upstream edit is permitted here.

## Observed boundary and correction

D090 completed all twelve native single-update cases, without Python warnings,
then stopped after **7.084 seconds** before any Cells transfer. The Cells worker
requires exact equality with its registered accepted runtime. That runtime records
`JAX_DISABLE_JIT` as absent, but the launcher set the string `false`. These are
different provenance values even though the actual enabled-JIT guard passed.
The launcher also inherited `XLA_FLAGS` instead of enforcing its registered value.

Build the child environment from the registered numerical environment: remove a
variable recorded as null and reproduce any recorded string exactly. For this
accepted runtime both `XLA_FLAGS` and `JAX_DISABLE_JIT` must be absent. Preserve
CPU execution, float64, single-thread libraries, isolated imports and all resource
limits. Apply this before the child imports JAX. Do not weaken or normalize the
existing runtime check, change the accepted runtime, or turn off compilation.

The versioned runner directly imports the unchanged D090 native worker, D089
Cells worker and D089 comparator. Its execution-body difference is the environment
provider plus explicit D091 provenance fields. An AST test checks this boundary.

## Regression contract

Run the existing 76 transport tests and 31 configuration tests alongside new
environment, evidence and launcher tests. In fresh CPU subprocesses enter the
actual frozen `cells_worker` with an intentionally absent `betse.json`. The
positive probe must pass its backend, precision and exact runtime guards and
reach the native-input read. No numerical model step runs in this probe.

Negative controls reproduce the original explicit-`false` failure, reject an
unregistered empty `XLA_FLAGS` string, reject genuinely disabled JIT, and reject
a deliberately mismatched registered package version. No monkeypatching of JAX,
Cells, the worker, runtime identity or the numerical checker is used. Retain
actual runtime/configuration, installed production-source hashes, interpreter,
affinity, exception boundary and durable logs for every subprocess. A passing
startup test does not claim that subsequent transport or comparison will pass.

Each startup probe has an eight-second ceiling; the five-probe contract has a
25-second aggregate ceiling. All original short checks remain in the focused
suite. This is not a full regression campaign or a rerun of a prior audit.

## Evidence and execution

A new preservation receipt binds every file of D090's failed packet, its seventy
source inputs, historical handoff/test XML and the earlier D089 preservation.
Read/hash existing native results solely to identify the execution boundary;
do not qualify them or count them as fresh execution. Preserve the old native
configuration/type packet and accepted 352-file / 51-module implementation.

Register the new source capsule, unchanged scientific protocol, configuration
amendment, runtime amendment, both failure-preservation receipts, passing focused
test XML and passing real-worker startup packet before a fresh capture.

Re-execute the same four native configurations and three states each, followed
by the same twelve matched Cells transfers per NumPy/eager-JAX/JIT-JAX backend.
This is one prescribed transfer, not a production RK4 step or coupled trajectory.
Same seven cells / thirty faces, 298.15 K, 25 microseconds, constants, controls,
accounting and tolerances. Same CPU 0–3, 120 seconds per worker, **300 seconds
total**, 32 MiB per file and **128 MiB aggregate artifacts**. These are file
budgets, not RAM limits.

Launch once detached and return control. Preserve any failure without polling,
automatic retry, audit or dynamic expansion. A pass remains
`capture_pass_pending_audit`; independent closeout requires another user
instruction. No biological, general BETSE-parity or GPU qualification advances.
