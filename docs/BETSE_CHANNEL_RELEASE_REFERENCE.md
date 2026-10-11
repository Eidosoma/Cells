# Independent block/release reference

2026-09-15, D104 / REF-004d. Validation only; production remains unchanged.
Prerequisite: [D103's saved-input closeout](../reports/REF004D_RELEASE_INPUT_CLOSEOUT.md).
This stage has **no BETSE or Cells trajectory entry point**. Software tests and
reference readiness are distinct from a simulator-response qualification.

## Fixed experiment

Retain D101's seven-cell, finite shared-bath, K-only Kv1p5 fixture at 298.15 K,
matched constants, and histories a = (m=0.2, h=0.6), b = (0.6, 0.2).
Intrinsic permeability is positive for every condition; availability is separate.
Duration is a fixed candidate 2 ms, not a response-selected window.

| Condition | Availability | Solver segments |
| --- | --- | --- |
| Baseline | 1 throughout | One unsplit interval |
| No-op | 1, 1, 1 | Split at 0.5 and 1 ms |
| Static blocked | 0 throughout | One unsplit interval |
| Suppression/release | 1, 0, 1 | Split at 0.5 and 1 ms |

Two histories × four conditions × three registered solver settings give
**24 paths / 48 segment integrations**. Baseline versus no-op explicitly checks
whether splitting itself changes the result within the reference budget.

## Continuous state and input boundary

The independent reference carries inward K transfer q, m, h and dissipated
energy: 28 float64 coordinates, with the one bath inventory reconstructed from
the opposite sum of cell transfers. Voltage follows capacitor charge. No clamp,
gate reset, permeability history mutation or separate bath integration is added.

Use the frozen 80-digit Decimal RHS algebra with availability multiplying only
transport/current/dissipation. This is **float64 SciPy integration**, not an
80-digit ODE solution. The checker instead changes effective permeability in
the distinct audited algebra before reconstructing rates. Neither imports a
simulator, compiler or production integrator.

Every segment holds its input through all solver stages, including its endpoint
derivative. Finish exactly at a switch, copy the entire accepted state into a
new solve, then use the right-hand input for fresh observations. Preserve both
one-sided readouts and derivatives, and require exact state carry and unchanged
gate derivatives at each boundary. Dense interpolation never crosses a switch.
All samples, including switches, use a canonical 6.25 microsecond Decimal-built
grid; endpoint samples use the actual carried state rather than a reconstructed
polynomial endpoint.

## Checks and prospective resolution gate

Inherit D099/D095's unmodified DOP853 base/tight and Radau settings, float64
precision, unit-specific convergence budgets and RHS/accepted-step caps. Primary
is tight DOP853. Inherit dense replay limits (5e-13 absolute, 2e-13 relative).
Save all accepted states, dense polynomials, 321 readout samples per path and
one-sided switch records. Compare full readouts, interval transfers and both
sides across all three settings. Validate every RHS evaluation, accepted state,
sample and three interior points of every dense interval against the numerical
domain. Interior probing is not a mathematical global-domain proof.

During a blocked segment q and energy remain exactly constant, flux/current
are exactly zero, and m/h must match analytic fixed-voltage exponential evolution
from that segment's actual starting gates. Thermodynamic free-energy loss must
match accumulated dissipation. All no-op samples match the unsplit baseline;
suppression/release matches baseline before the first switch.

For each history, every solver must resolve all of:

- Block effect at 1 ms: maximum cell voltage difference from baseline ≥ 40 µV.
- Post-release response: maximum voltage change from 1 to 2 ms ≥ 40 µV.
- Immediate right-hand release flux: maximum magnitude ≥ 2e-4 fmol/s.
- Gate evolution during block: maximum m/h change ≥ 4e-4.

These are four times the **existing prospective simulator absolute budgets**,
plus a two-readout reference-uncertainty allowance. They are not fitted to a
new trajectory. That allowance is twice (absolute reference budget + relative
budget × magnitude bound), where the bound is the maximum absolute relevant
readout across all solvers, floored at one in the field's stated units. Retain
signed final a-minus-b voltage/open-fraction diagnostics
without requiring a particular sign or positive biological memory effect.
A failure stops this fixed reference experiment: no automatic window extension,
new tolerance, simulator execution or retry. Passing does not establish biology.

## Evidence and execution boundary

Freeze new sources, plan, solver runtime, 66-test prerequisite receipt, D103's
ten-file closeout packet and unchanged earlier source/artifact chain. Include
new software verification and the handoff report in registration. Never rewrite
old failed/pending receipts. The controller and saved-data checker are model-free;
only the reference subprocess may import NumPy/SciPy. Simulator imports are
actively forbidden there.

One detached job on CPUs 0–3: 900 s total, 480 s reference worker, 128 MiB per
file and 256 MiB aggregate. These are artifact limits, not a RAM allocation.
Durable accepted-path records, logs and completion/failure receipts; exclusive
writes, no polling, retries, follow-up audits or full regression. A pass is
`piecewise_reference_pass_pending_review`, not simulator qualification. The next
user instruction can review saved evidence and plan full-loop timed native/Cells
comparison. This stage adds no production API or GPU-specific reduction rule.
