# REF-004a: isolated voltage-gated channel contact

D087, 2026-09-13. This is a small external-reference validation adapter, not a
new production model, release, channel catalog or coupled-cell qualification.
The user approved the channel-first recommendation after the scoped passive
response audit completed. Its [joint receipt](../runs/ref-003e1-refined-response-audit-2026-09-13/audit-01/completion.json)
passes in 249.644 seconds: 2,298,936 required checks, zero failures, 336 tests,
and 1,121,904 independently rebuilt surface comparisons. All 4173 diagnostic
failures remain. Only the specified seven-cell, 1 ms, matched-constant,
6.25 microsecond held-input response is qualified; native/input-waveform
convergence is not inferred. Its source, handoff and evidence remain frozen.

## Question and source alignment

Do the existing Cells Kv1.5-style continuous kinetics correspond to the
**executed**, pinned BETSE channel, and do their distinct numerical updates
approach the same held-voltage solution on explicitly selected protocols?

The source is BETSE v1.5.0, commit `5269a714aa2593ed2a6708c4516289977d8ae1a2`:
[channel](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/channels/vg_k.py),
[updater](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/channels/channelsabc.py).
The local clean checkout was read directly. Its byte identities and license
must match the earlier [SPEC-006 panel](../configs/reference/voltage_gated_channel_v1.json).
All 332 installed BETSE Python files are checked against the clean source in
the existing isolated environment. No upstream source is patched or vendored
into Cells. No new dependencies are installed.

- Voltage is inside minus outside, in volts; native entry points convert to mV.
- Gate targets are dimensionless; native time constants are converted ms to s.
- Native `init` prepares equilibrium. That behavior is recorded separately;
  trajectory fixtures explicitly install both registered m/h states afterward.
  Native `init` does not create P: the initial open fraction is explicitly
  derived as m*h. Subsequent P values come from native `run`. No zero-time
  trajectory update is added after fixture installation.
- Native `run` uses its unchanged held-voltage semi-implicit Euler update.
  Cells uses its unchanged continuous kinetic kernel and shared checked RK4.
- The engineering regime is **298.15 K**, not the passive fixture's 310.15 K.
  Neither gate formula consumes temperature. This is an alignment restriction,
  not evidence of physiological temperature calibration or a Q10 law.
- The source's declared -65 mV reversal constant does not enter this kinetic
  benchmark. There is no current, conductance, GHK transfer or membrane capacitor.

The native input carrier is `SimpleNamespace(dt)`, with `targets=None` and
`cells=None`, exactly the inputs consumed by this untargeted channel path.
It is not a loaded Parameters/Simulator, tissue profile or native world.
Prescribed voltage is an isolated gate input, **not a whole-cell voltage clamp**.
No electrode charge/current/work boundary has been added.

## Fixed panel and numerical gates

The [protocol](../validation/betse/voltage_gate_contact/protocol.json) is data.
Thirteen voltage probes retain SPEC-006's -120 to +60 mV engineering domain.
Kinetics and one shared RK4 step are checked on NumPy, eager JAX and compiled
JAX, all CPU/float64. Full gate histories use compiled JAX only: this does not
requalify the world runner, its dense output, restart or eager trajectories.

| Protocol | Duration | Purpose |
| --- | --- | --- |
| Activation at +20 mV | 40 ms | Fast m opening |
| Deactivation/recovery at -80 mV | 4 s | Closing and slow h recovery |
| Inactivation at +20 mV | 3 s | Slow hidden-state loss |
| -80 / +20 / -80 mV pulse | 60 ms | Exact event boundaries and retained history |
| Two equal-open-fraction initial states at -20 mV | 20 ms each | Preserve distinct m and h, not only their product |

Each uses **1 / 0.5 / 0.25 ms solver steps**, giving 18 native and 18 Cells
isolated trajectories, 49,980 updates per engine. Observations are independent
of integration steps; integer-microsecond clocks make every event/sample land
exactly on all three grids. Every real Cells trial stage and endpoint is checked;
every native update is inspected. No clipping or gate reinitialization at events.

A model-free 70-digit Decimal reference uses the source's mV/ms expressions.
At each segment it propagates from the event anchor to each observation using:

- Continuous kinetics: `q_inf + (q0 - q_inf) exp(-t/tau)`.
- Native discretization: the decay factor `(1 + dt/tau)^(-n)`.
- RK4 discretization: the fourth-degree exponential polynomial raised to n.

Discrete arithmetic uses 2e-11 absolute plus 2e-11 relative gate error. Kinetic
target/time-constant limits retain SPEC-006 values. At the finest step, maximum
continuous-solution gate errors must be at most **0.01 for native** (one percentage
point) and **1e-7 for Cells**, across every saved observation. These are engineering
limits for this first panel, not biological measurement uncertainty. At the
fastest trajectory time constant (~6 ms), the leading native error scale is
`dt/(2 e tau)` (~0.0077 at 0.25 ms); RK4's fourth-order error is much smaller.
The different bounds acknowledge the different methods; they do not require
identical discrete trajectories. Every coarse/fine error and maximum direct
native-versus-Cells gate difference is retained.

Observed error ratios on halving dt must be 0.4–0.6 for native, 0.03–0.10 for
RK4 when both errors exceed 1e-11. Below that floor, report **roundoff-limited**,
not a passed observed-order test. Resolved activation-m RK4 refinement must be
present. This is fixed piecewise-constant voltage, not smooth waveform sampling
convergence. Earlier passive across-hold failures are unrelated open evidence.

## Execution and preservation

Code stays under `validation/betse/voltage_gate_contact/`, outside the installed
package and normal test discovery. The source capsule binds the protocol,
adapter, focused tests, design, source-review panel, dependency lock and two
unchanged production kernels. The accepted 352-file implementation and previous
audit receipt/payloads are authenticated. No older source, criteria, failure
receipt, report, ignore rule, production module or release version changes.
Only the seven existing mutable progress/status documents are updated.

Run short synthetic adapter preflight before numerical capture. These tests
check reference arithmetic, corruption rejection, grid/history semantics and
detached failure handling; synthetic results are never native evidence.
The native/coupled acceptance regression is not rerun here.

Preflight receipts are preserved separately: **41 pass in 0.94 s**, then
**62 pass in 0.96 s**, adding worker provenance, numeric-type, timeout and
XML-receipt checks. Final review removes a redundant zero-time native update
after fixture installation and labels initial P as derived. The final
**63 tests pass in 1.11 s**, including that provenance guard. All 389 Python
files pass lint/format checks. No numerical native result follows from preflight.

Launch once to a fresh directory, with a passing new XML preflight receipt:

```bash
.venv/bin/python -B validation/betse/voltage_gate_contact/gate_job.py launch runs/ref-004a-kv1p5-2026-09-13/capture-01 --preflight reports/ref-004a-kv1p5-checks-03.xml
```

CPU affinity 0–3; single-thread libraries; native worker 60 seconds, Cells worker
90 seconds, total 180 seconds. New artifacts are bounded at 64 MiB, with 16 MiB
individual worker files; these are not peak-RAM claims. The long horizons above
are physical time, not expected hours of computation. Registration/source capsule,
worker logs/results and completion/failure receipts are durable. Return immediately
after detached launch; no polling, retry, automatic audit or expansion.
`capture_pass_pending_audit` is deliberately not independent closeout.

## Next gates and multiscale consequences

After user review, separately audit the actual saved channel packet. Then design
a small channel-plus-membrane/finite-bath comparison using the existing assembly,
with an explicit common temperature, ion/permeability mapping and same-stage
voltage feedback. The native seven-cell geometry limitation remains in force.
Whole-cell clamping would need a distinct electrode/boundary specification.

Kinetic law, state, transfer accounting and numerical method retain separate
ownership. Both m and h must survive checkpointing and future coarse-graining;
fast and slow gate times suggest later multirate work, not permission to assume
instantaneous equilibrium. Existing numeric channel/cell axes and pure JAX
kernels remain the foundation for future GPU batching. No GPU optimization or
new general-purpose plug-in framework is needed for this contact.
