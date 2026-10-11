# REF-003e1: first held-input response pilot

2026-09-13, D081. Implementation and prospective execution contract, not a
passing response result. The [D080 preflight](../reports/REF003E1_DISPATCH_PREFLIGHT.md)
establishes actual nonzero input application; this slice now integrates the
corresponding native and Cells models. See the
[handoff](../reports/REF003E1_RESPONSE_PILOT.md) for software checks and launch boundary.

## Fixed scope

Keep seven explicit cells, a finite well-mixed shared bath, 1 ms duration and
matched F/R constants. Na/K/Cl passive exchange and charge-based voltage are
active; pumps, channels, junction transport, spatial fields and mechanics are
disabled. Preparation remains fresh neutral SIM, not an equilibrated cell or
an INIT restart. No Cells production code, equation, dependency or old adapter
is changed. BETSE is still the pinned historical v1.5.0 reference.

| Input condition | Native | Cells |
| --- | --- | --- |
| Baseline, profile on / event off | Observed and unobserved | Eager/JIT at h, h/2, h/4 |
| Enabled zero-amplitude event | Observed and unobserved | Same six solver/backend combinations |
| Static blocked exchange | Observed and unobserved | Same six combinations |
| Suppression/recovery of permeability | Observed and unobserved | Same six combinations |

Here h = 25 µs. The total is eight native and 24 Cells runs, 160 observed
native steps and 2240 Cells steps (1120 each eager and JIT). All six Cells
runs within a condition use one identical, independently prescribed 40-hold
input table. Solver subdivision does not resample the pulse. All 41 hold
boundaries, including T, are requested observations.

Recovery names permeability returning toward baseline, not return of the cell
to its original state, tissue normalization or biological recovery.

## Separate the input, state and rate contracts

Use the frozen D079 input compiler and D080 fresh preparation/metadata helper.
The native raw `linspace(0,T,N)` labels map to elapsed interval starts k*h;
pulse times retain the explicit N/(N−1) scaling. Native event dispatch happens
once before each update. Cells RK4 stages use that interval's fixed control.
Neither simulator gets a new control at elapsed T: Cells retains u[N−1].

The unchanged full-loop observer records actual dispatch, six ion flux calls
and concentration/voltage update boundaries. A separate control-aware checker
permits only scheduled/effective Dm to change during dispatch, and checks
unchanged target/modifier metadata, fixed controls, state ownership and full
lifecycle. It checks each interval against the independent declared input with
the original 2e-14 baseline-scaled tolerance. It does not divide by the nearly
suppressed residual. Static/immobile diffusion remains exactly zero.

Require exact observer-on/off physical outputs, exact baseline/zero-amplitude
outputs and exact six no-op overlaps with D077's qualified capture. A new
nonzero event does not weaken the old no-op or constant-permeability checkers.

The new numerical comparison reads saved JSON, imports neither simulator nor
NumPy/JAX, and uses 70-digit Decimal passive-flux arithmetic. It checks:

- Positive native/cell inventories, shared-bath material balance, owned and
  cumulative transfer ledgers, charge-based voltage and current/flux signs.
- Native flux against each event's actual effective permeability, already
  checked against the declared hold—not the final Dm reused for every step.
- Native stored state/current/diffusion against the observer, including the
  source's six in-place 1e-25 V voltage additions during flux evaluation.
- Complete Cells history/readout shapes, precision and byte hashes, disabled
  and padded fields, all on-grid history/readout links and fresh held-input
  GHK rates at every requested observation, including the final held rate.
- Fixed-input Cells solver differences, eager/JIT differences, and native
  versus finest-Cells differences, both cumulative and per-interval transfer.

Native state at an update end and the current used for that update are not a
fresh right-side RHS evaluation. Cross-engine instantaneous rate comparisons
therefore use the 40 interval starts; state/amount/transfer comparisons use all
41 boundaries. The final native RHS is absent, not invented or inferred from
its last stored current. Cells' real final RHS is checked internally against
the last hold, then excluded from that unmatched cross-engine rate comparison.

Auxiliary thermodynamic exports and diagnostics remain finite and retained;
this external checker does not independently rederive every energy diagnostic
or every internal RK4 stage. Actual runner provenance, existing acceptance,
fixed-input refinement and subsequent independent evidence audit have separate
roles. Synthetic prescribed-state tests are checker tests, not new ODE evidence.

## A response pilot, not convergence qualification

Keep all REF-003d v2 instantaneous, cumulative and trajectory tolerances.
At 25 µs the retained native baseline already misses some cross-engine
shared-bath amount criteria. This pilot may reproduce that known discrepancy.
The checker must record it as failure even if pulse/control/backend checks
pass. Do not ignore the baseline, loosen criteria, substitute the retained
6.25 µs solution, or automatically select a better-looking run.

One native step/hold cannot establish native integration or forcing convergence.
A later experiment must separate native integration refinement at a fixed
prescribed input from refinement of the input hold itself. Those qualifications,
longer-time response, biological plausibility and GPU execution remain open.

## Resources, evidence and launch boundary

The [machine-readable plan](../validation/betse/held_response_plan.json) freezes
180 s native, 2100 s Cells and 180 s comparison stage limits, under a 2520 s
(42 minute) total cap. Estimates use D080's measured 24.463 s preparation cost
and the slowest retained eager per-step / compiled-run costs, with explicit
allowances: 134/1894/120 s and 136,459,177 artifact bytes. These are budgeting
estimates, not measured new throughput or a promised finish time.

Use CPUs 0–3, single-thread numeric libraries, CPU float64 and JIT enabled in a
separate Cells worker. Bind 512 MiB overall artifacts and an OS-enforced 64 MiB
worker-file cap. Overall bytes are checked between rows/stages and at completion,
not enforced as a filesystem quota. Peak RAM is not measured. The existing
per-run Cells trace allocation bound also remains active.

Freeze all 88 adapter/input files and focused test receipts before registration.
Preserve the 954-file starting worktree, allowing changes only to seven status
documents, along with D080's 201-file packet, earlier evidence, 352 accepted
implementation files and 51 production modules. Authenticate the installed
332-file native package; bind unchanged Cells sources/runtime at execution.

Fresh exclusive run directories contain source capsule, registration, stage
logs, each completed result, native preparation/events/final records, Cells
full histories/readouts and numerical comparison. Python-level native failures
also export partial/open observer state. A hard timeout retains previously
written files; it cannot manufacture an unwritten partial trajectory or resume
the interrupted run. Failure receipts preserve evidence and forbid automatic
retry or expansion. A numerical comparison failure retains `comparison.json`
and yields `failure.json`, never a passing `capture.json`.

Launch detached, return immediately and let the user request status. Do not
poll, automatically audit/regress, or interrupt an active run to end polling.
Even a passing capture awaits the separately requested independent audit and
does not qualify forcing/native convergence, biology, GPU or general BETSE parity.

## Architectural consequence

Keep source-specific clocks and observation conventions in an offline adapter.
Production consumes ordinary numeric control tables and retains its pure JAX
state/ledger calculations. This adds no BETSE runtime dependency or Python
event callback inside future GPU kernels. It reinforces the multiscale contract:
compare conserved inventories and interface transfers, not only voltage curves;
keep input resolution, integration resolution and readout side explicit.
