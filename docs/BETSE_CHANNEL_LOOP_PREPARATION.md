# REF-004b: full-loop channel preparation and observation

D093, 2026-09-14. The D092 independent single-transfer audit **passed** in
3.215 s: 37,068 independently reconstructed comparisons, zero failures, twelve
definition contracts and two hidden-state controls. Its completion SHA-256 is
`18070f9898bbbd6061867f050ac54d00dbb407b9bd978ced3ebfef136e8b40fb`.
That closes only the prescribed transfer, not a coupled trajectory.

This separately registered step addresses the native lifecycle boundary and
prepares the [small feedback pilot](BETSE_CHANNEL_FEEDBACK_DESIGN.md). It changes
no accepted Cells production, pinned BETSE code, old criteria or old evidence.

## Bounded actual-native preparation

Retain the qualified seven-cell / thirty-face geometry, fixed temperature and
matched constants, one finite well-mixed bath, zero ordinary leak/pump/junction
transport and no additional chemistry, flow or mechanics. Four variants remain:
network off, empty network, zero-permeability Kv1p5, active Kv1p5. Each has an
observed and unobserved counterpart: **eight fresh native runs, eight 25 µs
updates each (200 µs), 32 observed updates / 64 updates altogether**.

Every run performs real seed, INIT `init_core`, and a single native `run_sim_core`.
The latter owns `init_dynamics`, `clear_storage`, initial voltage calculation,
the full time loop, native sampling and native INIT serialization. No copied
time loop or replaced method is used. This is not an equilibrium preparation
or physiological resting-state claim.

## An explicit fixture is not an observer

Pinned `Channel.init_channel` / `VgKABC.init` initializes equilibrium gates; the
configuration has no arbitrary starting m/h setting. Setting gates before
`run_sim_core` would lose them when its initialization constructs the channel.
Use an explicitly mutating experimental initial-condition callback exactly once,
at the successful native `init_dynamics` return, before storage reset and voltage
closure. Set m=0.2, h=0.6 on every target face. The identical callback applies to
both observation modes, including the blocked channel. Save pre/post fixture
state and verify that only the declared gates/product changed.

This source-bound setup callback uses a profiling dispatcher, not a monkeypatched
model method. A separate optional observer shares that dispatcher but only copies
state. “Unobserved” means no step observer; it still has the same initial-condition
callback. This pairing isolates the additional observer, not the callback itself.
Python profiling also reports exception unwinding as a return. Check the pinned
CPython return opcode so failed initialization cannot apply the fixture, hide
the original exception, or become a completed boundary in a partial trace.
Native equilibrium gates and their initialization voltage remain recorded.
No extra channel update is called at zero time. P/DChan remain absent initially;
other derived fields absent before voltage closure are explicitly null.

## What the observer must distinguish

Record loop entry; network clearing; channel entry; actual gate-call entry/return;
channel return (transfer completed); empty chemistry/current export; ordinary
concentration update; and voltage closure. Require that exact order for each
variant. Channel current is exported separately from ordinary membrane flux.
Do not add it to the ordinary flux buffer and count it twice.

The native channel modulation changes representation from scalar 1 to a face
array of ones before the first gate call. Record that real transition; it must
remain physically constant. Native electroflux's minute voltage-input mutation
is retained, not converted into a clamp or compensating offset. Check that gates
read the previous completed voltage within the already registered transport
tolerance and are neither reset nor advanced twice.

Native `_plot_loop` constructs `linspace(0, N*dt, N)` labels. The loop performs
one update per label, including label zero. Therefore step i covers elapsed
`i*dt` to `(i+1)*dt`; its label is not an initial-state timestamp. At N=8, the
first sampled index is 1: its label is approximately 28.571 µs but it records
the completed 50 µs state. Save labels and elapsed times separately, and compare
ordinary native sampled histories with those actual completed boundaries.

Verify initial configuration/geometry/channel metadata against the independently
qualified preparation. Check gate recurrences and GHK at each actual boundary,
six-species conservation, exact blocking, finite bath ownership, inward transfer
versus outward native current, current smoothing, accumulated transfer and charge-
derived voltage. These native-method checks do not establish continuous-solution
accuracy or cross-engine coupled agreement.

Observer-on/off equality covers exported numerical values, shapes and float64
byte hashes, gates/flux, and native histories. Both native full-object INIT
pickles are retained. Their path-dependent bytes need not match; no restart replay
or equality of every internal native object is claimed by this preparation.
The model-free checker also reconstructs the exported float64 bytes from values
and shapes, so agreement of copied hash strings alone cannot establish equality.

## Cells pilot readiness, not integration

Only after native preparation checks pass, map its **loop-entry** state into the
existing `finite_extracellular@1` definition. Resolve four controls × three candidate
Cells grids through the unchanged parser, full initial-state checks, timeline
and resource estimator. Save all ten state fields. Compare initial coupled RHS
against an independent 80-digit continuous vector field. **No Cells trajectory
is run, no native post-gates are injected into a Cells trajectory, and feasibility
of a timestep is not its numerical qualification.**

## Registration and stopping rule

Bind the prior closeout and its nine-file packet, original 54-file capture,
source hashes/capsule, accepted implementation, dependency/runtime identities,
fixed protocol and passing focused software XML before execution. Authenticate
earlier evidence without rerunning its numerical audits. Only seven existing
status documents remain mutable; new sources and this protocol freeze at launch.

CPU 0–3, float64; **240 s overall**, native worker 120 s, Cells readiness worker
60 s; **128 MiB aggregate artifact allowance**, 32 MiB per file. The aggregate
allowance is checked between native rows and before completion, not an OS-wide
disk quota or RAM allocation. Keep durable logs, partial preparation/observer
records, complete comparisons, and failure/completion receipts. A failure ends
this version without automatic retry. Launch detached and return without polling.

A pass is `preparation_readiness_pass_pending_audit`. It permits a separately
requested saved-data review and subsequent dynamic registration, not automatic
execution of a longer experiment. Biological realism, general BETSE parity,
GPU performance and multiscale numerical qualification remain open.
