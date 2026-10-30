# Native temperature calendar replay

Chief approved this separate source replay and guarded CPU6 qualification. Root
owns shared status; Key owns normal current/material/voltage joins. This work
does not inspect the CPU3/4/7 jobs or modify their files or shared APIs.

`betse_temperature_calendar_source_v1_5_0@1` advances only a temperature buffer,
explicit HH/ML clock probes and an original source call cursor. It reuses the
existing complete native phase calendar, temperature setter and fixed-material
fast-coefficient declaration without changing those components. INIT suppresses
event/tissue callbacks; SIM executes the temperature setter, selected clock
probes and the normalized `makeAllChanges` marker in native order. Source labels
span `[0,N*dt]` in N calls, while elapsed boundaries and HH/ML updates use the
declared `dt`. Restart retains the original N and does not rebase labels.

The declared material, geometry, voltages and HH/ML targets/tau/Phi stay fixed.
The probes are source update-clock examples, not 55 complete channel-class
trajectories. Transport outputs are isolated coefficient prefixes on fresh
argument copies, not the native per-moving-ion nonce history or an ionic join.
Membrane electroflux and Nernst–Planck factors follow live temperature;
junction electroflux arguments and conductivity factors follow configured p.T.
The complete original fast initializer cache remains unchanged. Initial sum and
post-update_V mean conductivity are separately retained. Whole native coupled
evolution, conservative fields, accepted tissue stepping, heat and thermal
transitions are outside this law.

Fresh entry executes the configured-T copy. Carried entry binds an explicitly
supplied original runtime-T buffer; it does not authenticate that buffer as an
external native simulation checkpoint. Literal native and matched-SI constants
are named separately and checked against their exact declarations. No native
constant mismatch, commented Q10 or thermal calibration is inferred away.

Binding records associate the complete original material/owners/constants,
calendar, program, clock probes and cached coefficients. Accepted buffers are
immutable binary64 arrays. Restart archives preserve their exact bytes and
require the caller's original binding identity. Validation rebuilds the source
prefix, rejecting resealed temperature/gate/cursor/cache changes. These are
deterministic content/causal associations, not cryptographic proof that a native
simulation performed the work. Invalid proposed temperatures, coefficients or
gate intermediates remain available as raw hexadecimal/NPZ buffers, and the
parent/caches are not committed. The component's finite/positive/probability
guards are stricter than unguarded literal source publication.

The native capture authenticates nine checkout/installed source files, executes
unchanged full setter/HH/ML/fast-initializer/GHK functions and isolated original
calendar/count/dt/owner/conductivity/coefficient sites. Function metadata and
phase/tissue interfaces are normalized; coefficient expression selection is
declared explicitly. Original source lines and selected/executed AST hashes are
saved. The independent reference uses Decimal at 125 and 170 digits, rational
calendar labels and owner loops; it imports no Cells, BETSE, JAX or NumPy.

The qualified suite has 82 checks, including 34 complete source streams and 192
call rows: both INIT/SIM phases, both constant profiles, fresh/carried entry,
reordered/divalent/zero-voltage cases, empty events, zero/one/two-call calendars,
binary64 duration truncation, 16 exact disk restart splits, raw refusals and
resealed input/checkpoint/cache archives. Both native solver event guards are
checked. Fresh import-denied native and independent replays must verify every
saved cache, state, coefficient and gate arithmetic column. Existing fast-law
budgets, four-ULP calendar reference limits, exact restart bytes and a 0.1-budget
reference precision criterion remain fixed in the protocol.

The completed `betse-temperature-calendar-20261030-01` capture and verified
receipt are linked by `betse_temperature_calendar_qualification_plan.json`.
Both fresh import-denied replays passed. The record includes measured resources,
all frozen/native/runtime hashes and preserved restart/refusal buffers. These
are declared source call rows, not coupled native or biological trajectories.

Qualification uses CPU6, one thread, 1 GiB summed process-tree RSS, 8 GiB host
reserve and 480 seconds per phase. All generated files, frozen sources, logs and
results belong under `/mnt/workspaces/Cells`. Runs expected to reach ten minutes
launch detached and are not automatically polled. No JAX/GPU compilation or
compiled-memory improvement is claimed by these source replay checks.
