# REF-004b: native channel setup and single-transfer preflight

D089, 2026-09-14. Implements the next bounded step in the frozen
[coupled-channel design](BETSE_COUPLED_CHANNEL_PLAN.md). The independently closed
[isolated gate comparison](BETSE_VOLTAGE_GATE_CLOSEOUT.md) is the prerequisite.
This document specifies the capture prospectively; an actual completion or
failure receipt, not this plan or a synthetic test, establishes its result.

## Scope and controls

Use unmodified BETSE v1.5.0, commit
`5269a714aa2593ed2a6708c4516289977d8ae1a2`, in its existing isolated environment.
Reuse the actual seven-cell / 30-face geometry fixture, not a fake one-cell
tissue. Seed one geometry for each of four native configurations, then create a
fresh real `Parameters`-associated `SimPhase` / `Simulator` state for each case.

| Native configuration | Channel object | Maximum permeability |
| --- | --- | --- |
| Network off | None | Zero |
| Minimal empty network | None | Zero |
| Minimal Kv1p5 network, blocked | Present; m and h still evolve | Zero |
| Minimal Kv1p5 network, active | Present; m and h still evolve | `1e-8 m/s` |

Each configuration uses three independent preparations: native-initial gates,
prescribed `(m,h)=(0.2,0.6)`, and prescribed `(0.4,0.3)`. The last two pairs have
equal initial open fraction but different subsequent gate updates. They are
explicit initial conditions, **not reconstructed prior physiological histories**.
Channel-free controls have the same chemistry but no invented gates.

There are twelve prescribed single-update cases, six actual channel-runner
calls, and twelve matched Cells transfers on each of NumPy, eager JAX and
compiled JAX. No native or Cells trajectory driver, equilibration, voltage clamp,
new channel catalog, parameter fitting or GPU computation is run.

## Fixed physical and numerical choices

- Actual native parameter and simulator temperatures and Cells temperature are
  **298.15 K**. No Q10 extrapolation is introduced.
- Use the existing matched F/R constants; retain native source-default constants
  separately. Apply the explicit parameter intervention before native seeding.
- Fixed geometry, FULL solver configuration, zero polarizability, one shared
  finite well-mixed bath. Native `apply to: all` must target all thirty faces.
- All ordinary membrane permeabilities, pumps, gap-junction transport, ER/Ca
  dynamics, noise, fluid/mechanical processes and unrelated network chemistry
  are off. Replacing the whole example network removes X, Nav and KLeak.
- `substances affect Vmem` is explicitly true to exercise real current export.
  The native empty-network charge-balancing hook must leave every ion inventory
  unchanged. Preserve auxiliary Ca/P/M charge in the Cells fixed-charge terms;
  do not neutralize residuals or adjust voltage after seeing results.
- `maxDm = thickness * P_max * abundance`, thickness `7.5e-9 m`, abundance one,
  relative permeability one and uniform modulation/density one. This permeability
  is an engineering fixture, not a channel-density or physiological calibration.
- Each prescribed update is **25 microseconds**, with initially native-derived,
  near-zero charge voltage. This does not qualify a voltage range or a long-run
  stable step size. The earlier passive regime was at a different temperature.

All values, tolerances and resource bounds are in the versioned
[protocol](../validation/betse/channel_transport_preflight/protocol.json), frozen
in registration before either numerical worker executes.

## State and accounting boundary

Record initial native m/h with native P and DChan absent. A separately labelled
`derived_m_times_h` is not a fictitious native P output. Export the actual
face-target array and actual post-update P, DChan and channel flux.

The native sequence is:

1. Fresh core and dynamics initialization, charge-derived voltage, optional
   declared m/h initial condition; save a durable before-state.
2. Clear network accumulators; advance native gates and call its full channel
   transport path once. Its dynamic concentration mappings update real ion arrays.
3. Run the empty chemistry loop to export the channel's extra current.
4. Apply the ordinary concentration updater with zero ordinary and junction
   fluxes. This must not apply the channel's transfer a second time.
5. Recompute native charge, voltage and currents.

Save all these boundaries separately. Charge/current/voltage readouts can be
stale at intermediate boundaries until their actual updater is called. The
native electroflux law's `+1e-25 V` input mutation is recorded and checked,
not patched away or described as an unchanged input.

Cells receives pre-transfer amounts/voltage and the **actual post-native gate
state**. It evaluates its unchanged `finite_extracellular@1` constitutive
readouts and RHS. An adapter-only prescribed amount/ledger update applies
`dt * RHS` while holding that already-advanced gate state. This is **not a Cells
RK4 step**, does not advance m/h twice, and makes no discrete-integrator parity
claim. The existing production integrator remains unchanged and unexecuted.

Reduce native faces to one Cells channel per cell only after exact within-cell
m/h/voltage uniformity checks. Sum flux density times face area by owner, never
average hidden gates. Independent padded capacities are cell 8, membrane 9,
channel 10, outside 2 and edge 1, with seven active cells and no active edges.

## Required checks and evidence

The model-free checker uses 80-digit SI gate targets, native rational gate
updates and the independent constant-field oracle. It checks configuration,
target/index coverage, gate evolution under block, gate/permeability units,
actual current export and signs, and initial m/h information preservation.

For every case, test each of all six native species' conservation, the bath
convention `V_effective = 30 * p.vol_env`, concentration and amount changes,
charge-derived voltage and outside countercharge. Native inward mol/(m² s)
becomes Cells inward fmol/s after owner-area integration; native extra current
is outward `-F*z*flux_density`. Check raw Jmem and its separately smoothed Jn /
I_mem, without treating smoothing as another material transfer. Native ordinary
flux arrays must remain zero. Cells material increments, transfer ledgers and
inactive slots must retain their proper owners.

Keep all numerical failures in the comparison artifact; never widen a tolerance
or silently retry. Structural/preparation failures retain logs, configuration,
geometry and any completed before/after case artifacts. A raw numerical pass is
`capture_pass_pending_audit`, not a coupled-trajectory qualification.

Register the source capsule, all 51 unchanged production modules, 352-file
accepted implementation anchor, earlier source baseline, isolated audit and
original capture identities, geometry identity and focused-test XML. Keep the
old flat validation source inventory unchanged by adding only a nested adapter.

## Run policy and next gate

One detached attempt, CPUs 0–3, float64 and single-thread numerical libraries.
Each numerical worker has at most 120 seconds; total wall budget is 300 seconds.
Artifact ceiling is 128 MiB, with a 32 MiB per-file limit, **not a RAM limit**.
Logs and completion/failure receipts are durable. No polling, retry, automatic
audit, regression campaign or dynamic pilot follows the launch.

After the user requests status, inspect the actual result. A passing capture
still needs a separately requested saved-data audit and review before registering
a short coupled trajectory with timestep refinement. General BETSE parity,
physiological plausibility, passive input-sampling convergence and GPU validation
remain distinct open questions.
