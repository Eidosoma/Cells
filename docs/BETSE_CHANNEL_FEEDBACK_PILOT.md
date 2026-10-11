# REF-004b: reference-gated channel feedback pilot

D095, 2026-09-15. The user requested both the independent continuous reference
and the short evolving Cells/BETSE comparison. This is one versioned capture
with ordered stages; it does not authorize an automatic follow-up audit.

## Prerequisite and unchanged engineering

D094's [independent preparation audit](../runs/ref-004b-loop-audit-2026-09-14/audit-01/completion.json)
passes in **5.541 s**, all **74,092 comparisons**, zero failures. Its nine-file
packet, D093's 74-file preparation, 101 existing source inputs and all older
evidence remain immutable. Completion SHA-256:
`8ec513d8171ebf3a6670ae270f66fed1821ff4caf66670076c3e4bc03ef5c391`.

Keep accepted 352 implementation files / 51 production modules unchanged.
No new production integrator, channel-specific runtime branch or test-only
NumPy trajectory wrapper is introduced. Production trajectories use the normal
checked RK4 eager and compiled JAX paths. NumPy remains useful for constitutive
checks; it is not mislabeled as a separate production trajectory backend.

## Registered experiment

Retain seven cells / thirty faces, one finite well-mixed bath, fixed geometry,
298.15 K, matched F/R, Kv1p5 m=0.2 / h=0.6 and four controls: network off, empty
network, blocked channel, active channel. Ordinary leak, pumps, GJs, other
chemistry, flow, mechanics and noise stay off. This is a deliberately simplified
engineering regime, not a physiological resting state.

Select **2 ms** and observations at **0, 0.25, 0.5, 1 and 2 ms**. This short
horizon is a fraction of the initial approximately 8 ms activation timescale;
the 200 microsecond preparation demonstrated detectable voltage response and
correct native lifecycle. Actual reference-domain and convergence checks must
still pass before either simulator starts. Do not lengthen, refine or relax the
registered panel after seeing results.

- Native: 25 / 12.5 / 6.25 microseconds, four controls, each with observed and
  unobserved counterparts: **12 pairs / 24 fresh runs / 4,480 updates**.
- Cells: 50 / 25 / 12.5 microseconds on compiled JAX, all four controls; eager
  JAX additionally at 50 microseconds: **16 full trajectories**.
- Cells checkpoint/reload at 1 ms on each compiled 25 microsecond control,
  then four resumed segments. Compare all state fields and observations with
  uninterrupted tails, not only voltage. Preserve complete midpoint/final snapshots.

Each engine evolves its own full state. Cells definitions are the independently
audited readiness inputs, not states copied from the new native trajectories.
Native uses its unchanged gate-first loop; Cells uses its unchanged same-stage
RK4. Neither engine receives the other's post-gates or voltages.

## Independent numerical reference and gate

Use the frozen 80-digit Decimal vector field, previously independently checked,
with cumulative inward K transfer q, separate m/h for present channels, and
per-cell cumulative dissipation. Derive cell/bath amounts and capacitor voltage
from q; do not integrate a redundant voltage or subtract nearly equal large
ionic charges. Absent channels have no ODE gate coordinates. Blocked channels
retain their gates. Energy counters do not feed back into the physical state.

The independent `.reference-venv` has NumPy 2.5.3 / SciPy 1.18.1 and no JAX.
Bind package identities and installed IVP source hashes before launch; no
environment is upgraded. Use DOP853 with tighter tolerance/step repeats and a
distinct Radau cross-check. These are distinct algorithms within one library,
not independent library implementations. SciPy documents DOP853 as an explicit
eighth-order method with seventh-order dense output and Radau as an implicit
fifth-order method with cubic dense output. [SciPy solver documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html).

The **integrator is float64**, not 80-digit integration. The high precision is
only in RHS evaluation. Three solves per control, **12 solves total**, retain
accepted states/clocks, method-native dense coefficients, 321 common reference
samples, readouts and solver statistics. Replay dense coefficients without
calling a solver; compare base/tight DOP853 and Radau at every sample. Check
blocked-channel analytic exponentials, exact-zero controls and total passive
dissipation against the closed-system free-energy decrease. Check domains at
all RHS calls and saved states. No single solve is declared ground truth.

Only a passing reference convergence gate permits the two simulator workers
to start. Failure retains reference records and stops the one capture, with no
automatic change of method, tolerances or horizon. Passing this gate is not the
later independent saved-data closeout.

## Accuracy and accounting contracts

Exact values are registered in [protocol.json](../validation/betse/channel_feedback_pilot/protocol.json).
The finest trajectory must meet every common-observation budget against the
independent reference. Coarse rows remain diagnostics; their failures are
retained and reported separately. Both halvings must reduce per-field error by
at least 20%, unless already below the registered reference/roundoff floor.
Require this for gate, voltage, transfer and bath amount, and check successive
own-grid differences as well. Roundoff-limited agreement is not a measured
convergence order.

| Quantity | Finest-trajectory absolute budget | Reference disagreement budget |
| --- | --- | --- |
| m/h | 1e-4 | 1e-8 |
| Voltage | 1e-5 V (0.01 mV) | 1e-8 V |
| Per-cell K amount / accumulated transfer | 5e-7 fmol | 5e-10 fmol |
| Shared-bath K amount | 3.5e-6 fmol | 3.5e-9 fmol |
| Interval transfer | 1e-6 fmol | 1e-9 fmol |
| Fresh inward K rate | 5e-5 fmol/s | 5e-8 fmol/s |
| Effective permeability | 1e-12 m/s | 1e-15 m/s |
| Cells/reference cumulative dissipation | 1e-9 pJ | 1e-10 pJ |

Relative tolerance is 2e-11 times the expected magnitude. Bath budgets sum seven
cell budgets; interval budgets combine two endpoint budgets; current budgets
derive from F times the K-rate budget. Finest cross-engine budgets are twice the
single-engine budget by the triangle inequality. These are engineering error
budgets fixed before new trajectory capture, not fitted biological uncertainties.
The gate budget resolves 0.01 percentage points and the voltage budget 10 microvolts.

Native boundary-law checks reuse frozen D093 observer/checker code at every
update. Only accumulation/conservation accounting receives a new duration-scaled
roundoff allowance: `2e-12 + 8 * epsilon64 * update_count * largest_initial_total_inventory`
fmol, computed from old preparation data. Gate, GHK, instantaneous transfer,
current and voltage-law tolerances stay unchanged. This bound does not loosen
any earlier capture or its audit and is separate from dynamic approximation error.

Keep complete native boundary snapshots and exported float64 byte records;
serialize them losslessly as bounded gzip JSON, with aggregate files containing
paths rather than duplicate traces. The frozen initial-condition callback and
read-only observer are unchanged. Native labels are never mistaken for elapsed
time. Observed/unobserved exports and native sampled histories must match.
Link all final channel byte records to raw state, and independently check
absolute six-species charge at every completed observed state and each
unobserved final state, alongside the increment-based capacitor check.

Stored native channel current belongs to the gate-first step, not the newly
completed voltage. Obtain fresh common-time native flux separately, after the
trajectory, by calling the unmodified native constitutive function on **copies**
of recorded completed states. Record its small input mutations and prove live
state unchanged. Never advance gates or transport for a readout. Native INIT/
world pickles are preserved; native restart equivalence is still not claimed.
Recheck probe permeability from its saved gates and GHK flux from its saved
chemistry/voltage at the original strict constitutive tolerances.

Cells records include all ten state fields, complete production observations,
invariant diagnostics and numerical checkpoints. Verify inactive padding,
Na/Cl constancy, one-owned transfer, shared-bath sum, capacitor state and
thermodynamic accounting. All ordinary production domain/interpolant guards
remain active. Energy comparison is Cells/reference only; native has no newly
invented cumulative energy counter.
Reconcile Cells sampled amounts, voltage, permeability and current with its own
accepted state and independent constitutive equations before cross-trajectory
comparison. These strict readout checks are separate from integration budgets.

## Resources, handoff and limits of the result

One detached capture: CPUs 0–3, float64, **900 s overall**, reference/native/Cells
worker caps **180 / 240 / 360 s**, **512 MiB aggregate artifacts**, **128 MiB per
file and per decompressed record**. Existing Cells reservations remain 64 MiB /
1,024 steps. Artifact limits are not RAM caps. No polling, retry, optimization,
GPU launch or automatic follow-up audit. The user checks status.

Bind 112 source inputs, prior evidence, actual environments and passing focused
software XML before launch. Software tests include synthetic reference problems
and a distinctly declared -35 mV / 100 microsecond production integration and
restart fixture, not the registered scientific result. Retain failed attempts.

A successful capture stays `capture_pass_pending_audit`. A later independent
saved-data audit is required for coupled qualification at these observations.
No biological calibration, broad BETSE parity, long-time/stiff-regime accuracy,
GPU, organ, multiorgan or cross-resolution qualification follows. Future GPUs
can batch independent worlds; a shared bath remains a same-stage reduction,
not a collection of independent cells. Organ type and size remain data settings.
