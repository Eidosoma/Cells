# REF-003e design review: phase, clocks and controls

2026-09-12, D072. **38 design checks pass in 3.67 s. No model was integrated and
no trajectory panel was registered or launched.**

The [design](../docs/BETSE_INTERVENTION_PLAN.md) replaces an assumed immediate
hard block/release test with an explicit sequence: first a no-intervention
SIM-from-neutral phase bridge, then a corresponding native-step-held smooth
suppression/recovery comparison. Exact square pulses and continuous-waveform
integration remain separate future contracts.

## Findings

1. The qualified REF-003d transient ran in native `INIT`. Scheduled interventions
   fire only in `SIM`, before pumps/electrodiffusion. The normal high-level
   `SimRunner.sim()` also loads the previous initialization state. A phase change
   is therefore a new condition, not inherited acceptance.
2. Native event labels are `k*N*dt/(N-1)`, while the pre-update state is at elapsed
   `k*dt`. A shared elapsed-time experiment requires explicit scaling of all
   three native pulse time parameters by `N/(N-1)`. Native labels stay untouched.
3. Native permeability changes add a logistic pulse times the tissue-default
   diffusion, rather than replacing permeability with a square-wave multiplier.
   For homogeneous baseline/default diffusion, multiplier -1 yields `1-pulse`.
4. Cells already has right-continuous numeric controls, exact event-split grids,
   and one control held over all RK4 stages of an interval. Its existing interface
   can express a declared held drive; continuously reevaluated input is not that
   same contract.

## What was checked

The [control-only driver](../validation/betse/intervention_design.py) verifies
the prior closeout SHA-256, both complete 119-file trajectory packets, 35 captured
adapter sources and all 352 accepted implementation files. The six reviewed
native source files match both the retained checkout and installed pinned copy.
The review also records five existing Cells source hashes. Static syntax checks
locate the native phase guard, event-before-flux ordering and raw clock formula.

An isolated native worker calls the actual pinned `toolbox.pulse`, not an
extracted replacement, at 280 update-start points across the candidate native
ladder. Applied availability after the explicit clock mapping agrees with
independent 70-digit Decimal evaluation within the declared 2e-14 control
allowance. The unconverted clock comparison is retained as a diagnostic.
The candidate midpoint availability is approximately 4.1223e-9, explicitly not
zero; logistic tails before/after the named centres are also checked.

| Native step | Maximum mapped control error | Maximum difference without conversion |
| --- | ---: | ---: |
| 25 µs | 2.665e-15 | 0.357524 |
| 12.5 µs | 2.443e-15 | 0.208080 |
| 6.25 µs | 2.665e-15 | 0.108319 |

These are dimensionless availability differences in the **control-only** test,
not voltage/amount errors or measured trajectory effects. The large unconverted
differences illustrate why otherwise identical YAML times need not prescribe
the same elapsed-time experiment near a rapid transition.

An isolated Cells worker loads an unchanged finite-bath definition in memory and
tests its existing control/grid interfaces with a unit-test square control at
0.35/0.75 ms. Values immediately before and at boundaries show right-continuity,
inactive slots remain zero, and the 10-interval nominal grid splits into 12
intervals. This square-control probe is not a claimed native counterpart or a
simulated response to the candidate smooth pulse.

Both workers fence imports of the simulation stepping-entry modules. No seed,
`init_core`, `run_sim_core`, Cells runner, ODE step, native event handler or tissue
targeting operation is called. Source inspection and control-function tests do
not qualify the proposed SIM-phase trajectory or its intervention response.

The [38 tests](ref-003e-design-checks-02.xml) cover source/closeout identity,
phase/clock mutations, all three mapped timing parameters, invalid pulse inputs,
scope overclaims, no-op control algebra, smooth tails, source-control agreement,
existing Cells event semantics, and genuinely distinct held-input refinements.
The [first test receipt](ref-003e-design-checks-01.xml) retains 33 passes / one
setup error: BETSE's normal startup log preceded JSON on stdout. The driver now
captures that diagnostic text inside the structured result instead of discarding
it or changing native logging/source behavior. No numerical criterion changed.
Lint and formatting pass for all 318 Python files; seven existing status/design
documents are the only modified baseline files.

## Evidence and next step

- [Candidate design inputs](../validation/betse/intervention_plan.json), explicitly
  `design_only_not_registered`.
- [Preservation baseline](ref-003e-design-preservation.json): 858 pre-existing files.
- [Final source/control review](ref-003e-design-review.json), including actual
  control probes, source hashes, test receipt and document-change accounting.
- [Prior trajectory closeout](ref-003d-closeout.json) stays immutable, with SHA-256
  `4caaa0485d971821ebccc7fa255323bb3e38708531503c4cb8838ef97bd197b9`.

Next implement and preflight **REF-003e0**, a separate SIM-phase bridge adapter
and read-only event observer. Freeze a bounded capture only after those checks;
launch and subsequent audit remain separate user-authorized stages. The old
325 adapter tests and 4190 production tests are not rerun here. Stable 0.14.0,
accepted development 0.15.0.dev0, biological qualification and GPU status do not
change.
