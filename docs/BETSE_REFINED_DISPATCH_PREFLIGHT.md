# REF-003e1: finer-input dispatch preflight

2026-09-13, D083. **Native preparation and event dispatch only, not response
integration or convergence qualification.** This implements the first bounded
step of the [D082 refinement design](BETSE_HELD_RESPONSE_REFINEMENT.md) after
the user reviewed the completed failure audit and approved continuation.

## Reviewed starting point

The [D082 joint closeout](../runs/ref-003e1-response-audit-2026-09-13/audit-01/completion.json)
completed in 50.390 s. It reproduced 345,576 original comparisons, independently
rebuilt 147,312 comparison-surface checks and retained all 150 failures in
shared-bath Na/K amount changes. All 198,264 internal checks pass. The reporting
correction changes only the aliased internal failure list, not physical criteria
or the rejection. All 70 new tests pass; the unchanged legacy suite reports
121 passes and its one explicitly recorded metadata-guard failure.

The saved constant-input baseline error halves at each native timestep halving;
6.25 µs meets the original trajectory tolerance. That supports a baseline
timestep explanation but cannot establish convergence for the pulse. Native
pulse sampling changes along with its integration timestep.

## Exactly what will execute

Use the [new plan](../validation/betse/response_refinement/refined_dispatch_plan.json)
and unchanged pinned BETSE v1.5.0 in its separate environment. Freshly seed
the same seven cells / 30 membrane faces and finite-bath preparation at matched
F/R constants. Keep all physical inputs, disabled mechanisms and the declared
1 ms horizon unchanged. Do not load a retained state as a restart.

| Nominal timestep / input hold | Conditions | Fresh preparations | Dispatches per preparation |
| --- | --- | ---: | ---: |
| 12.5 µs | Baseline, zero amplitude, static block, suppression/recovery | 4 | 80 |
| 6.25 µs | Same four controls | 4 | 160 |

Total: **eight preparations / 960 direct dispatches**, including 480 enabled
targeted dispatches and 240 nonzero-amplitude dispatches. These calls are made
on the freshly prepared physical state; they are not elapsed physical evolution.
**No transport, concentration update, integrator or Cells run is allowed.**

Retain D080's 25 µs preparation and D081's response as immutable reference
evidence; do not rerun them or count them as new dispatches. The new mapping
reproduces D080's declared mapping and metadata exactly at 25 µs in software
tests. Its finer-clock physical setup must match the qualified retained initial
states, geometry and topology.

## Input and evidence contracts

The new mapping extends only timestep/sampling fields and the three clock-scaled
pulse parameters. The input still comes from D079's prescribed decimal compiler,
not measured native event histories. Record the full declared YAML mapping,
raw labels, elapsed input times and control tables before native execution.

Native labels use `linspace(0, T, N)`. Scale the three pulse-time settings by
`N/(N−1)` so dispatch k corresponds to elapsed input time `k*h`. The final raw
label is T, but its input is for elapsed T−h: 0.9875 ms or 0.99375 ms respectively.
There is no newly evaluated endpoint pulse. A later response comparison must
retain this held-input convention and distinguish state, fresh-rate and ledger
observation sides.

Reuse the frozen preparation fence and read-only event observer unchanged.
The new worker uses a separately versioned fresh-phase mapping, not a patched
native handler or a modified old adapter. Persist core/dynamics/ready state
before optional metadata extraction. Check prepared state before dispatch.
Persist each completed event immediately; exceptions preserve completed/open
events and all already written artifacts, without pretending unwritten state
can be recovered after a hard timeout.

The variable-length checker verifies actual targets, tissue defaults, resolved
modifiers, multipliers, pulse times, array shapes/dtypes/hashes, event ordering,
full pre/post-state linkage, final state and zero-amplitude controls. Only
scheduled/effective mobile diffusion may change; physical state, topology and
disabled routes remain unchanged. Require the exact native additive composition.

There are **345,600 diffusion-value checks**: two arrays × six species × 30 faces
× 960 dispatches. Use the original **2e-14 error divided by positive unsuppressed
diffusion**, not a relative error against the tiny suppressed residual. Blocked
and immobile diffusion remain exactly zero; the smooth pulse is not a square
block. No physical comparison threshold is amended.

The native worker performs the physical checks. The controller verifies source,
runtime, result, reference and individual/aggregate event linkage. These receipt
checks are not a separately executed independent numerical audit. Any future
audit or response capture requires the next user instruction.

## Software evidence, preservation and resource boundary

All **109 focused tests pass in 36.21 s**, using saved initial states, fabricated
events and receipt fixtures. Tests include the exact old mapping, finer raw/
elapsed clocks, unexpected endpoint evaluation, rehashed state/event corruption,
forbidden-entry fences, provenance, partial records and a launcher with no
poll/wait method. They do not run native preparation or integrate either model.

The [new preservation record](../reports/ref-003e1-refined-dispatch-preservation.json)
pins **979 existing files**, all 150 response-capture files and all 16 failure-
audit files. Keep 352 accepted implementation files / 51 production modules,
the old flat 88 adapter inputs and four D082 audit modules unchanged. Five new
Python modules and one plan form a separate **98-input source capsule**. Only
the seven existing status documents may change. The previously recorded user
`.gitignore` amendment and now-ignored historical XML receipts remain pinned;
no legacy assertion is patched or old regression rerun in this slice.

Measured D080 preparation/dispatch costs, scaled conservatively by the sixfold
dispatch count with explicit allowances, give estimates of **251 worker seconds**,
**206,406,234 artifact bytes** and **17,333,340 bytes for the largest worker file**.
Bind **300 seconds worker / 360 seconds total**, CPUs 0–3, single-thread numeric
libraries, **256 MiB artifacts** and OS-enforced **32 MiB per worker file** before
launch. Aggregate bytes are checked between rows and before completion, not
enforced as a filesystem quota; peak RAM is not measured by these limits.

Launch once detached into a fresh attempt, preserve success/failure artifacts,
return control and let the user request status. No polling, retry or automatic
trajectory/audit follows. Even a passing result qualifies only this initial-state
input-application gate, not a nonzero response, solver/forcing convergence,
biological recovery, restart, organs, GPU behavior or stable promotion.

See the [prelaunch handoff](../reports/REF003E1_REFINED_DISPATCH_HANDOFF.md).
