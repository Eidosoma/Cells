# REF-003d closeout: bounded passive trajectory correspondence

2026-09-12, D071. The refined capture passes its original numerical criteria,
the separate saved-data audit and all 325 adapter tests. Closeout is complete.
This qualifies a **1 ms, neutral-prepared seven-cell passive/blocked finite-bath
comparison**, not physiology, a resting cell, the original one-cell fixture,
general BETSE parity, or a production timestep for other cases.

## Result and unchanged scope

The [v2 capture](../runs/ref-003d-v2-2026-09-12/trajectory-01/verification.json)
finished at **17:57:58 UTC**, in **104.031 s** including orchestration and checking.
BETSE and Cells worker times were 36.039 s and 52.638 s respectively. These workers
have different run counts, steps and compilation work; this is not a speed benchmark.
All 24 native runs and eight Cells runs completed without recorded warnings.
There are twelve observed/unobserved native pairs, 1120 observed native steps,
seven cells, 30 membrane faces, and one effective 6.75 pL shared bath.

All **435,144 numerical comparisons pass**, with maximum normalized error
**0.559745** (acceptance threshold 1). Native timesteps are 25/12.5/6.25 µs;
Cells uses its existing checked RK4 runner at 100/50 µs, eager and compiled JAX
on CPU/float64. Physics, Cells definitions, horizon, preparations, constant
profiles, all numerical tolerances and time/CPU bounds are unchanged from v1.
Only the native ladder, revision/scope labels and declared storage cap changed.

The largest matched-constant, finest-step cross-program differences are:

| Quantity | Maximum absolute difference |
| --- | ---: |
| Amount increment, including the shared bath | 5.903e-8 fmol |
| Membrane voltage | 4.894e-7 V (0.4894 µV) |
| Instantaneous ionic amount rate | 8.122e-7 fmol/s |
| Inward current | 1.404e-16 A |
| Integrated membrane transfer | 9.837e-9 fmol |

These are maxima over the registered comparison grid and components, not relative
biological errors. States are compared at eleven elapsed times from 0 to 1 ms;
instantaneous rates at ten begin-step times from 0 to 0.9 ms. Native final saved
flux/current belongs to the preceding update, not a newly evaluated 1 ms RHS.
Native rounded F/R remains a separate profile, not silently substituted into Cells.

For matched native constants, the largest amount refinement difference decreases
from 1.183e-7 fmol (25 → 12.5 µs) to 5.907e-8 fmol (12.5 → 6.25 µs).
The latter passes the frozen bounds and contraction requirement. Both native
constant profiles pass. Cells' own 100 → 50 µs amount refinement differs by at
most 8.909e-15 fmol. The fully blocked controls have exactly zero transport and
unchanged inventories. No extrapolated result is used for acceptance.

Eight repeated native 25 µs records and all eight Cells numerical records match
the failed v1 packet exactly; run timing metadata are excluded. V1 **remains
rejected**, with its 36 failed shared-bath Na/K amount checks and all 119 files
retained. Finer native resolution resolves the selected accuracy failure without
altering Cells or weakening the original criteria.

## Independent evidence audit

[trajectory_evidence.py](../validation/betse/trajectory_evidence.py) authenticates
the captured registration, result, comparison and 35-member source capsule against
retained SHA-256 anchors. It verifies exact coverage and every digest for 115
payload files, canonical paths, regular nonempty artifacts, runtime/source
identity, worker/clock/budget records, geometry and claim scope. There are 119
files overall: launch and outer runner logs are operational records outside the
capture payload manifest; closeout preservation also binds those files.
Native pickle artifacts are authenticated as captured bytes, not unpickled.

The [saved-data audit](ref-003d-v2-evidence-audit.json) reproduces the entire frozen
comparison exactly. A fresh-process import fence rejects Cells, BETSE, NumPy and
JAX imports. No model, ODE stepper, reference worker or simulation is executed.
The arithmetic is a replay of the prospectively captured checker, not a second
new numerical method; the independent evidence layer adds provenance and field
consistency guards around it.

New checks cross-link auxiliary native exports that the captured checker only
unpacked and byte-hashed: final membrane/junction fluxes, boundary voltage,
membrane concentration owner mapping, diffusion/permeability and diffusion history,
disabled pump history and constant gap-junction gate history. Final flux is linked
to the last observed update. Native gate openness remains one while `gj_surface=0`
disables junction transport; an open gate does not imply an active junction here.
One corruption test explicitly demonstrates the old final-flux field boundary
and rejection by the new link check. No captured checker was patched.

The closeout preservation baseline records 846 existing files before document
edits, all 352 accepted implementation files, and both complete 119-file packets.
The dated v1/v2 launch reports, original 29-source capsule and refined 35-source
capsule remain unchanged. New audit, tests and closeout tooling are separate files.

## Checks and receipts

- [New actual-packet/corruption tests](ref-003d-v2-closeout-new-02.xml): **49 pass
  in 91.26 s**, no failures/errors/skips. This exceeded the short-run estimate;
  future full adapter suites should run detached with durable logs and
  user-requested status checks.
- [Existing adapter regression](ref-003d-v2-closeout-existing-02.xml): **276 pass
  in 38.36 s**, no failures/errors/skips. Combined total: **325 passing tests**.
- Lint and formatting pass for 316 Python files.
- The first new-test invocation retained 15 passes / 34 setup errors because
  `/tmp` and the capture are on different filesystems. Tests now stage one ordinary
  scratch copy before hard-linking between scratch directories. The first existing
  suite invocation had two collection errors; invoking `python -m pytest` supplies
  its required repository import path. Both unsuccessful receipts are retained as
  [new tests attempt 01](ref-003d-v2-closeout-new-01.xml) and
  [existing tests attempt 01](ref-003d-v2-closeout-existing-01.xml). These are test
  setup failures, not simulation failures or relaxed numerical checks.
- Formal closeout: [ref-003d-closeout.json](ref-003d-closeout.json).
  The [first closeout receipt](ref-003d-closeout-01.json) is retained; finalization
  corrects two stale progress-table rows and records the final documentation
  hashes. Test results, captured sources and numerical evidence are unchanged.

The previous 4190-test production matrix is preserved, not rerun. Stable 0.14.0
and accepted development 0.15.0.dev0 are unchanged. No stable, biological, organ,
family-wide BETSE or GPU promotion follows from this bounded external comparison.

## Engineering implications and next step

Keep source-specific geometry, unit conversions and clock conventions in the
external adapter. The existing Cells model needed no production adjustment.
For future multiscale execution, accuracy needs checks at shared interfaces and
inventory totals as well as individual cells: small coherent per-cell errors can
accumulate in a bath. Different solvers may need different timestep ladders;
equal timesteps are not the definition of equal accuracy. Same-context byte-exact
repeatability here is not a promise of bitwise CPU/GPU correspondence.

Next, design a small passive permeability block/release comparison. First verify
how both engines apply events relative to flux evaluation and state recording;
the initialization-phase native clock must not be assumed to support the desired
schedule. Specify observable continuity, exact zero flux during the block,
resumption afterward, material/charge accounting, event-aligned refinement and
eager/compiled agreement before registering any new capture. If existing hooks do
not express that contract, resolve the adapter/model boundary explicitly rather
than patching native methods or adding benchmark-only production physics.

No new panel is registered or launched in this closeout. Pumps, published
physiology, longer horizons and coupled tissue remain separate later gates.
Future long jobs stay detached with durable evidence and user-requested status.
