# REF-004c: equal-current, different-history preparation

D097, 2026-09-15. The user reviewed D096's passing independent closeout and asked
to proceed. This is a **new preparation**, not an amendment to that experiment or
a new coupled-trajectory qualification. Keep the original source and evidence
unchanged, including its fourteen coarse diagnostic failures.

## Question and architecture relevance

Can a reduced cell description retain the response-relevant internal state?
At the same voltage, concentrations and maximum permeability, m=0.2/h=0.6 and
m=0.6/h=0.2 both have open fraction 0.12. Their initial channel currents match,
but their rates of change of open fraction need not:

`d(m*h)/dt = h*dm/dt + m*dh/dt`.

The first state has more available slow h and less activated fast m. This test
does not simulate a preparation history, establish biological memory, or imply
all possible reductions need both gates. It constructs an explicit equal-output
counterexample to treating voltage/current/open fraction alone as a sufficient
state for this kinetic law. A task-specific reduced model must retain enough
history or quantify its response error.

Use **two separately defined worlds** with identical physical settings within
each pair, not two independent cells inside a shared bath. The current fixture
has seven cells because of the audited native geometry; cell/organ count and
initial gates remain data, never production-engine branches.

## Fixed preparation panel

- Reuse the authenticated D095 initial physical setup: Na/K/Cl, auxiliary fixed
  charge, seven cells / thirty native faces, matched constants, 298.15 K, fixed
  geometry, one shared finite bath, no leak, pumps, GJs or other chemistry.
- Four definitions: active a/b and zero-maximum-permeability a/b. Within each
  pair **only `initial_gate` changes**. Blocking transport must not freeze gates.
- Use the existing Cells parser, initial-value/domain checks, complete ten-field
  RHS, and selected voltage/channel readouts on NumPy, eager JAX and compiled
  JAX, all CPU float64. Save complete initial states/RHS and lossless array-byte
  records. No Cells integration step or trajectory is performed.
- Check twelve candidate grids through the real timeline/resource guard:
  four definitions at 50/25/12.5 microseconds, candidate duration 2 ms and the
  original observation grid, 1,024-step / 64 MiB trace reservations. Eligibility
  and estimated working storage do not select a timestep or measure runtime/RAM.
- In the separate pinned BETSE environment, initialize actual unmodified Kv1p5
  objects at the seven archived cell voltages. Record equilibrium initialization,
  install the explicit a/b fixture, then perform one fresh gate update at each
  25/12.5/6.25 microsecond step. Six vector updates / 42 scalar-channel updates.
  These are **isolated channel calls**, with `targets=None` and no native world,
  transport, SIM events, new geometry or loop observer. The seven voltages are
  prescribed inputs, not a whole-cell voltage-clamp experiment. Initial open
  fraction is derived before the first real update, with no artificial dt=0 run.

## Independent mathematics and acceptance

Reuse the D094 independently audited 80-digit equations, not either simulator's
kinetics/flux kernel or the D095 continuous integrator. Independently reconstruct
the full initial state and RHS, gate products and opening slopes, membrane-owner
K transfers, the single opposite shared-bath sum, channel transfer/energy ledgers,
and exact zeros for inactive/blocked contributions. Validate saved float64 bytes.
Pair definitions, non-gate initial states, layouts, initial voltage/current and
non-gate initial RHS must match exactly within each backend. Gates and their
opening tendency must differ. Each backend is checked against the independent
equations; this is not a cross-device bitwise guarantee.

Native post-step gates are compared to their **own rational update**, not Cells
RK4 or an exact continuous step. Check equilibrium, target/time constants,
installed fixture, unchanged input voltage and native open-fraction output.
The three fresh steps are updater checks, not a measured coupled convergence rate.

The [plan](../validation/betse/channel_history_preflight/plan.json) registers
unit-specific absolute tolerances and relative tolerance 2e-11. Require at least
1 per second separation of the two initial open-fraction slopes in every cell.
Record a model-derived difference in transfer and voltage second derivatives:
at the shared initial point the concentration and voltage derivatives match,
so only the differing gate-product slopes remain in their difference. Compute
this using unit-open GHK flux, without dividing by possibly zero opening or
permeability. **Do not extrapolate this local derivative over the 2 ms horizon**
or count it as a directly measured production/native acceleration.

Conservation and initial-rate correspondence, native isolated-step agreement,
candidate eligibility, full coupled histories, biological evidence and GPU
accuracy remain distinct claims. Existing accepted complete checkpoint support
is unchanged; this preparation does not execute or qualify a new checkpoint.

## Resources and execution boundary

Bind D096 completion
`61e700cbddda5141f92443ba684bf344d14d09e1b3c9db12110d1a0a923a28b9`, its complete
packet, D095 data, prior source/runtime identities, a passing new test receipt,
and the new source capsule. Model-free controller comparison; actual engines
are restricted to separate subprocesses with the pinned numerical environment.

One detached preparation: CPUs 0–3, **240 seconds total / 90 seconds per worker /
64 MiB aggregate artifacts / 32 MiB per file**. Artifact caps are not RAM limits.
Preserve result/failure receipts; return after launch, without polling, automatic
retry, follow-up audit or coupled run. Long follow-up work requires the user's
next instruction. A pass is `history_preflight_pass_pending_review`, not coupled
history qualification or a new production release.

## Following steps, not launched here

1. Review the actual preparation evidence, including any mismatch or weak signal.
2. Register independently converged **paired coupled references**, preserving
   both m and h. A reduced mean-P/voltage view is a diagnostic negative control,
   not a replacement state or permission to remove the slow gate.
3. Run the smallest own-state native/Cells paired coupled comparison, with
   explicit full-state restart and refinement gates. Choose its horizon from
   reference/domain/signal and resource evidence, not the derivative witness.
4. Only then add suppression/release, longer recovery, communicating cells or
   another channel/mechanism as separate bounded experiments.

For future GPUs, pair/world batching is independent work; cells sharing a bath
still require stage-consistent reductions. Local numeric gate state, explicit
owners and separate observation code already fit that boundary. No optimization,
new plugin framework, organ-specific engine branch or GPU launch is needed now.
