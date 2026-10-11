# E02-SW1: prospective numerical qualification

NUM-005 plan / SPEC-004, 2026-09-08. **No solver or longer trajectory is qualified
by this document.** The [protocol](E02_SWITCHING_PROTOCOL.md) and
[JSON](../configs/reference/e02_switching_protocol_v1.json) freeze the scientific
inputs. The existing [NUM-004](SOURCE_EMT_PAIR_NUMERICS.md) evidence covers only
1/10-unit pair trajectories and cannot be extrapolated to 500/1000-unit graphs.

## First independent step: graph composition, not a new constitutive law

Extend the independent NumPy/SciPy reference outside production, importing
neither Cells kernels nor BITSEY. Reuse the already independently written local
equations; assemble contacts by an explicit edge loop so it does not reproduce
the production scatter implementation. Apply each cell's local and membrane
rates once, then sum reciprocal contributions for each edge. Never sum complete
pair RHSs, which would duplicate a high-degree cell's local reactions.

Check N=1/no edges, N=2/one edge, N=3/star, a short chain and disconnected
components instantaneously before long integration. The one-edge reduction must
match the frozen pair reference, including heterotypic orientation and independent
controls; the selected long assay itself is ungated. Test cell/edge permutation,
edge reversal with hemichannel swap, degree accumulation, blocked edges, no
double-counted local sources, and separate ionic/regulatory charge semantics.
Preserve the existing pair calculator and its 14-case evidence unchanged.

Native instantaneous witnesses for the three-cell composition must use a new
bounded adapter of the pinned reusable modules, with recorded input/config/source
hashes. Do not import the unguarded cancer driver or continuing-exploration
dispatchers. This checks source-equation correspondence, not a long native
reproduction. Any later long native comparison requires its own registered
settings, resource budget and intended/realized-clock audit; none is run here.

For N cells and E edges, the independent packet has `13*N + 4*E` coordinates:
`6*N` primary, `3*N` membrane histories, `N` pump-cycle histories, `3*N` local
regulatory histories, and `4*E` oriented exchange histories. Derived
binding/voltage/gates and fixed context are not integrated. Ionic and regulatory
histories retain different units and
never feed back. Reconstruct primary state from its fixed anchor and histories;
check cancellation across reciprocal equal-volume transfers.

## Preparation gate and independent reference

Qualify the two 500-unit isolated preparations first. Record the complete
accepted/dense state, fixed context, residuals, statistics and typed histories.
Use Radau and BDF at `rtol=1e-10`, `atol=1e-11`, then refined Radau at one tenth
both tolerances, each with maximum step 0.1. Evolve primary increments about a
fixed anchor to reduce cancellation; diagnostic ledgers remain passive. Use an
independently checked Jacobian strategy. Save and check dense-polynomial
coefficients against the solver's own output, including all relevant extrema.

After numerical agreement and the protocol's preparation criteria pass, freeze
the refined endpoints and their hashes **before** any connected trajectory.
All 14 connected cases start from those exact anchors. Integrate all with the
same three reference settings; reference agreement must use at most one tenth
of each error budget below. Include the zero-edge and one-edge controls, not
only positive-hypothesis stars. No desired E/M result is an integration gate.

## Explicit candidate and error budgets

Study RK4 at maximum steps 0.01, 0.005 and 0.0025 on both preparations, both
active stars and both one-neighbour cases. Select the largest passing step only
after all six study cases pass. Qualify **every** preparation and connected case
at that step and its half; the half of 0.0025 is allowed as a qualification trial,
not an unregistered new method-selection sweep. Retain all rejected trials.
If no candidate passes, stop and diagnose; any solver, tolerance or input change
requires a named amendment with the original evidence retained.

For each scalar use `abs(candidate-reference)/(atol+rtol*abs(reference)) <= 1`.
These retain NUM-004's existing targets deliberately; extending the horizon is
a test of them, not an assumption that they pass.

| Quantity | Absolute budget | Relative budget |
| --- | ---: | ---: |
| Ionic concentration and ionic histories | 5e-8 | 5e-10 |
| Regulatory coordinates and regulatory histories | 5e-6 | 5e-8 |
| Voltage, V | 5e-7 | 0 |
| Algebraic junction scale | 5e-6 | 5e-8 |
| Membrane and junction flux, respective source units | 1e-13 | 1e-5 |

Require primary reconstruction residual at most `2e-9` per coordinate. Compare
all accepted endpoints, midpoints, fixed observer times and phase boundaries;
stream maximum scores, not only endpoints. Check finite values, RK4 stages,
endpoints and all cubic extrema, with ions `[1e-6,1000]`, regulation `[0,1000]`,
absolute cell/transjunction voltage at most 0.2 V and electrical exponents at
most 50. Implicit dense polynomials get corresponding full-interval domain
checks. Floating-point extrema checks are not rigorous interval certification.
Blocked histories must remain exactly constant. Do not clip negative values.

Label uncertainty at each decision time uses the sum of the u and m error
budgets as a conservative numerical allowance around `u-m`; include reference
disagreement and actual candidate differences. If that interval reaches either
label threshold (+2 or -2), classify the label as unresolved. Preparation margin
and anchor-separation gates need corresponding allowances. Agreement of visible
labels alone is not solver qualification; this empirical allowance is not a
rigorous ODE error enclosure. Also compare binding caches
reconstructed from state; they cannot be omitted from source-style diagnostics.

After connected-only tests, separately carry each selected/half-step candidate's
own full 500-unit prepared state into the two active stars. Compare against the
reference's full preparation→contact path with the same final budgets. These
four end-to-end continuations detect preparation sensitivity; do not reset them
to the reference anchor or reclassify their references to hide divergence.

## Bounded execution, receipts and stopping

CPU float64 only, affinity 0–3, one worker at a time. Maximum 900 seconds per
trajectory, 1,000,000 candidate steps, 2,000,000 reference RHS calls; pause after
a 3,600-second session budget. Estimate arrays against 256 MiB and enforce a
1 GiB artifact budget before writing batches of output. These are work/array/
output limits, not a promise of bounded total process RSS. Budget exhaustion
means incomplete, not a negative or numerical pass; no automatic extension.

Use 256-step windows or equivalent bounded reference chunks. Streaming must
preserve all domain checks, complete checkpoints and exact global clocks.
Never retain a Python list of every window while claiming bounded memory.
Record reference coefficients/accepted states in hash-indexed chunks; retain
observer samples, complete initial/final states and streaming error summaries.
Time out workers without presenting a partially written manifest as complete.

Before execution, hash the protocol, reference implementation, adapter, runtime
pins and planned case inventory. Record each attempt including failures/timeouts,
resource usage, solver work and actual clocks. Before production work, publish
an audited numerical receipt, immutable prepared packets, independent readouts,
the chosen method or explicit failure, and a limited claim statement. Preserve
0.10.0 before a later production edit; strict source/runtime checkpoint identity
and all accepted short-case and earlier-model regressions remain required.
