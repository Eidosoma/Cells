# REF-003d: first short seven-cell trajectory

2026-09-12, D068 design; D069 first capture; D070 refinement; D071 closeout.
**V1 remains rejected; v2 passes the independent bounded trajectory closeout.**
The [closeout report](../reports/REF003D_CLOSEOUT.md) records current state;
the [refinement launch report](../reports/REF003D_TRAJECTORY_REFINEMENT.md) and
[original launch report](../reports/REF003D_TRAJECTORY_LAUNCH.md) remain historical.
[REF-003c closeout](../reports/REF003C_CLOSEOUT.md) establishes
initialization, instantaneous transport and prescribed-update correspondence.
REF-003d now establishes that the actual simulators evolve this corresponding
model consistently over the selected 1 ms interval. Keep this separate from
physiology, longer horizons or family-wide BETSE parity.

## D071 independent closeout

All 435,144 frozen numerical checks pass; the maximum normalized error is
0.559745. The saved-data audit reproduces the result without importing either
simulator or NumPy/JAX. All 325 adapter tests pass, including 49 new actual-packet
and corruption checks. Both complete packets, the 35 captured v2 sources and all
352 accepted implementation files remain unchanged. The capture took 104.031 s;
closeout does not rerun it or the prior 4190-test production matrix.

Native 12.5 → 6.25 µs refinement meets the original bounds and contracts as
required. The selected matched comparison is native 6.25 µs versus Cells 50 µs,
on the declared observation grid. These are qualified settings for this fixture
and horizon only, not generic timestep limits. All eight Cells records and eight
repeated native records reproduce v1 exactly. The v1 rejection is not revised.

D072 now provides the [next phase/control design](BETSE_INTERVENTION_PLAN.md)
and [passing control-only checks](../reports/REF003E_INTERVENTION_DESIGN.md).
Because native events fire only in SIM and use smooth additive pulses, first
preflight a separate no-intervention SIM-phase bridge from the same neutral
preparation. No new panel is registered or launched, and no active mechanism or
longer biological relaxation is qualified.

D073's [first preparation attempt](../reports/REF003E0_PHASE_PREFLIGHT.md) now
fails on an absent default tissue in the old profiles-off configuration. Its
73 software/negative-evidence checks pass, but preparation and trajectory gates
remain open. The [next bridge version](BETSE_SIM_PHASE_BRIDGE.md) must isolate
default-profile activation before targeted events. REF-003d evidence is unchanged.

D074's [explicit profile preparation](../reports/REF003E0_PROFILE_BRIDGE.md) now
passes all six native preparations / 30 direct no-op dispatches and 87 focused
tests. Starting values match retained INIT and the profile/event configurations
preserve physical setup bytes. This is not a trajectory: next register the
separate full-loop bridge with noninterference and original numerical criteria.

D075 supplies the [full-loop pilot](BETSE_FULL_LOOP_BRIDGE.md): 100 focused
checks pass before its separate 12-run native SIM capture, retaining matched
constants, 25 µs and 1 ms from preparation. No new Cells run or modification of
REF-003d evidence/criteria occurs. Native capture controls and subsequent
independent saved-data audit remain separate; both-constant-set / finer-step
SIM coverage still requires an expanded bridge. See the
[detached handoff](../reports/REF003E0_FULL_LOOP_PILOT.md); status is user-polled.

D075 capture controls pass all 12 runs in 26.139 s. D076's
[independent closeout](../runs/ref-003e0-loop-audit-2026-09-12/audit-01/completion.json)
now passes 88,956 numerical comparisons and 165 tests in 32.682 s, with original
criteria and unchanged REF-003d/pilot evidence. It qualifies only the narrow
SIM pilot. D077's expanded capture now passes 72 native runs / 3360 observed
steps in 203.562 s at both F/R profiles and all three timesteps. D078's
[joint expanded closeout](../runs/ref-003e0-expanded-audit-2026-09-12/audit-01/completion.json)
now passes 1,232,616 original-criteria comparisons and 433 tests in 167.679 s.
It qualifies the expanded zero-amplitude SIM bridge without a simulation rerun.
D079's [held-intervention design](BETSE_HELD_INTERVENTION.md) adds input
composition and actual schedule/grid probes for a four-condition response
pilot. D080's [actual event-handler preflight](BETSE_NONZERO_DISPATCH_PREFLIGHT.md)
now passes four preparations / 160 dispatches in 24.463 s, with 75 focused
tests passing. Actual controls and unchanged physical state are checked at all
40 first-pilot input times without integration. D081 now implements the
[control-aware response pilot](BETSE_HELD_RESPONSE_PILOT.md): eight native /
24 Cells runs with a fixed 25 µs input hold and separate Cells subdivisions.
Original instantaneous/cumulative/trajectory criteria stay unchanged. The known
coarse native baseline can still fail; this is not native/forcing convergence
or a biological claim. The capture subsequently completed all 32 runs in
715.769 s and rejected 150 of 345,576 comparisons. D082's
[joint failure closeout](../runs/ref-003e1-response-audit-2026-09-13/audit-01/completion.json)
now completes in 50.390 s, preserving the rejection with a separate report-list
correction, 70 passing new tests and one explicitly recorded legacy metadata-
guard failure. No simulation or numerical criterion changed. D083 implements
the first step of the [refinement design](BETSE_HELD_RESPONSE_REFINEMENT.md):
[actual finer-input dispatch preflight](BETSE_REFINED_DISPATCH_PREFLIGHT.md),
without transport/integration. Its 109 software checks pass; native execution
is a separate detached, user-polled attempt, now passing in 116.002 s.
D084's [finer response implementation](BETSE_REFINED_RESPONSE_PANEL.md) adds
16 new native / 48 Cells runs at the two finer holds, retaining the coarse
packet and every failure. The final 114-test software regression now passes
in 95.688 s total, without failures/errors/skips or simulation launch. The
subsequent capture stopped after 1830.727 s at a configured trace-storage guard,
with 16 native / 26 Cells runs completed. D085's
[resource-only continuation](BETSE_TRACE_BUDGET_CONTINUATION.md) preserves all
241 failure files and raises only eight unexecuted definitions from 16 to 64 MiB.
All 48 production resource checks and 47 focused tests pass. Reuse the completed
rows directly and launch only 22 remaining Cells runs, then the unchanged full
comparison, under a two-hour / 1 GiB combined artifact cap. No polling or
follow-up audit; all earlier evidence, numerical criteria and production stay
frozen. Actual new run receipts determine continuation state. Trace reservation
is not peak process RAM, and no scientific criterion is loosened by this change.

The D085 continuation now finishes in 2239.322 s, with all 2,298,936 required
checks passing and 4173 diagnostic failures preserved. D086's
[independent finer-response audit](BETSE_REFINED_RESPONSE_AUDIT.md) replays all
2,494,936 checks and independently reconstructs 1,121,904 surface comparisons.
All 105 new preflight tests pass. The user-reviewed
[joint completion](../runs/ref-003e1-refined-response-audit-2026-09-13/audit-01/completion.json)
now passes in 249.644 s, with all 336 focused tests and 2,298,936 required checks.
No simulator was rerun. Native integration/resampling, fixed-input solver
refinement and input-hold sensitivity remain distinct: only the specified
finest-held seven-cell response is qualified. All 4173 diagnostic failures and
old sources, criteria and evidence remain frozen. D087's next
[isolated channel contact](BETSE_VOLTAGE_GATE_CONTACT.md) is a separate active-
mechanism question, not a resolution of the passive input-sampling limitations.

D088 now independently closes that isolated-channel comparison; see its
[result](../reports/REF004A_KV1P5_CLOSEOUT.md). The
[coupled-channel design](BETSE_COUPLED_CHANNEL_PLAN.md) explicitly preserves the
open passive sampling question and rechecks shared-bath normalization and
separate channel-transfer accounting before any new full-loop comparison.

D089's [implemented channel preflight](BETSE_CHANNEL_TRANSPORT_PREFLIGHT.md)
uses zero background leak and a separate 298.15 K regime to isolate one active
transfer. Its 76 passing software checks and prospective detached capture do
not reopen the passive campaign or resolve its input-sampling limitations.
Native gate-before-transfer and Cells matched-state RHS are explicit; the
adapter's conservative ledger update is not a shared-RK4 trajectory comparison.

D090 corrects the native empty-biomolecule representation after D089's preserved
setup failure. The [configuration-only successor](BETSE_CHANNEL_SETUP_FIX.md)
does not change the numerical protocol or revisit the passive campaign. Native
YAML/type checks pass; actual channel transport and a later coupled trajectory
remain separate gates. No passive sampling limitation is resolved by this fix.

D090 then completed native single transfers but stopped at the Cells runtime
identity guard before any Cells transfer. D091's [launcher-environment correction](BETSE_CHANNEL_RUNTIME_FIX.md)
preserves both failures and the strict guard; 152 focused tests and five actual
startup probes pass. The same fresh bounded active-channel preflight follows,
not a reopened passive campaign, changed input hold or new coupled trajectory.

That D091 capture now passes all 37,068 single-transfer checks. D092's
[saved-data audit](BETSE_CHANNEL_TRANSPORT_CLOSEOUT.md) and 220 passing focused
tests add independent reconstruction without reopening the passive campaign.
The actual independent closeout now passes in 3.215 s, with no simulator rerun.
D093's [full-loop channel preparation](BETSE_CHANNEL_LOOP_PREPARATION.md) and
[feedback-pilot design](BETSE_CHANNEL_FEEDBACK_DESIGN.md) use constant controls
and separately refined methods. The bounded preparation runs no Cells trajectory;
no passive campaign is reopened and no old input-sampling limitation is resolved.
The preparation now passes in 18.031 s: 73,744 native boundary and 348 Cells
initial-rate comparisons, zero failures. D094's [separate saved-data audit](BETSE_CHANNEL_LOOP_CLOSEOUT.md)
reconstructs that evidence and full-state/clock/resource contracts, without
simulator reruns or a cross-engine dynamic qualification.
The actual D094 audit now passes in 5.541 s with zero failures. D095's
[reference-gated channel pilot](BETSE_CHANNEL_FEEDBACK_PILOT.md) adds independent
continuous integration/convergence and the next small constant-control coupled
comparison. It does not reopen this passive campaign, change its old criteria or
resolve its held-input sampling limitations. Production remains unchanged.
That capture now passes in 338.424 s, with fourteen retained coarse diagnostics
and zero required failures. D096's [separate saved-data audit](BETSE_CHANNEL_FEEDBACK_CLOSEOUT.md)
checks the coupled pilot, not this passive campaign. No old capture, criteria or
input-sampling limitation is rewritten, and no simulator is rerun by the audit.
The actual D096 closeout now passes in 172.504 s, with 5,806,006 independent
comparisons and zero mismatches. Its [closed scope](../reports/REF004B_FEEDBACK_CLOSEOUT.md)
is the fixed active-channel pilot, not expanded passive qualification. D097's
[history preparation](BETSE_CHANNEL_HISTORY_PREFLIGHT.md) and D098's
[saved-data closeout](../reports/REF004C_HISTORY_PREPARATION_CLOSEOUT.md) now pass.
D099's [paired-history workflow](BETSE_CHANNEL_HISTORY_PILOT.md) now passes
capture in 391.917 s, with zero required failures and 21 retained coarse misses.
D100 adds its separately requested [saved-data audit](BETSE_CHANNEL_HISTORY_CLOSEOUT.md)
without simulator/reference integration. This does not reopen the passive
campaign; its input-sampling limits and original criteria remain unchanged.
The actual paired [closeout](../reports/REF004C_PAIRED_HISTORY_CLOSEOUT.md) now passes
in 240.629 s, with 8,036,300 independent comparisons and zero mismatches. D101's
[channel release input design](BETSE_CHANNEL_RELEASE_DESIGN.md) is a new, distinct
parameter-input question, not reuse or promotion of the passive tissue pulse.
Its 107 software tests pass. D102's [native input preflight](BETSE_CHANNEL_RELEASE_PREFLIGHT.md)
adds 71 passing software checks with real native smoke cases and a separate
detached 144-phase / 288-update panel. Each phase advances only two native steps;
input queries do not constitute a dynamic release trajectory. Full capture,
review and response still need their own gates. Its native panel completed but
an exact-identity check rejected zero-flux bath rounding. D103's
[saved-data review](BETSE_CHANNEL_RELEASE_REVIEW.md) reconstructs the native
reduction exactly while preserving original physical budgets and the failed
capture. All 66 software tests pass; its actual
[input closeout](../reports/REF004D_RELEASE_INPUT_CLOSEOUT.md) passes 916,176
comparisons in 24.469 s without simulator reruns or response promotion. D104's
[piecewise reference](BETSE_CHANNEL_RELEASE_REFERENCE.md), with 102 passing
software tests, subsequently passes all 1,485,380 comparisons in 160.675 s on
the fixed 2 ms block/release candidate, not a passive pulse rerun. D105's
[timed comparison](BETSE_CHANNEL_TIMED_RELEASE.md) first independently reviews
that saved reference, then gates actual native/Cells trajectories, release-
boundary restart and refinement. No reference reintegration, production change,
automatic post-capture audit or reopening of old passive work.
Its actual timed capture subsequently passes in 1,004.27 s, with zero required
failures and 49 coarse misses retained. D106's separately user-authorized
[saved-data audit](BETSE_CHANNEL_RELEASE_CLOSEOUT.md) checks the fixed timed
scope without reintegration, production changes or reopening passive work.
The [completed D106 audit](../reports/REF004D_TIMED_RELEASE_CLOSEOUT.md) now passes
15,042,946 independent comparisons in 387.772 s, with zero column mismatches and
all 49 coarse misses retained. D107 moves to [pump, junction and biological
tracks](BETSE_REALISM_AND_NEXT_STEPS.md); no old passive campaign is reopened.

## D070 amendment after the first numerical rejection

All 32 v1 runs completed, but 36 shared-bath Na/K amount checks failed. The
[independent saved-data replay](../reports/ref-003d-failure-audit.json) reproduces
all 129,384 comparisons. Coherent per-cell errors accumulate in the shared bath;
native endpoint differences approximately halve with timestep. This supports finer
native resolution, not a relaxation of tolerances or replacement of physics.

The [v2 protocol](../validation/betse/trajectory_refinement_protocol.json) changes
only revision/scope labels, the native ladder to **25/12.5/6.25 µs**, and storage
to **128 MiB**. There are 40/80/160 native updates, 1120 observed steps overall,
with an unobserved partner for every native run. All Cells definitions, steps,
backends, cases, constants, clocks and numerical criteria are unchanged. The same
1e-10 fmol cumulative allowance now applies to up to 160 steps without widening.
CPU/time bounds remain 0–3 / 90 s per worker / 180 s total. The original 23.1 MB
packet makes fourfold recording growth too close to the old 64 MiB cap; complete
recording is retained under the new explicit cap.

The new harness calls the frozen v1 workers and saved-state arithmetic directly.
Additional gates require repeated 25 µs native data and all eight Cells numerical
records to match v1 exactly; timings are excluded. All 276 adapter tests pass,
including 48 new checks. The old failed packet and all 29 captured adapter files
stay unchanged. Launch detached, without automatic polling, retry or post-capture
audit. A fresh pass still needs its own independent actual-packet closeout.

## Original v1 panel and unchanged physical model

Start with the same seven native cells / 30 faces and one effective 6.75 pL
finite bath. Retain the frozen Na/K/Cl inputs, fixed auxiliary charges, zero
polarizability, disabled active mechanisms and neutral preparation from
[REF-003c](../validation/betse/cluster_protocol.json). No new model family or
production equation is needed. The original one-cell REF-003b stays deferred.

The [machine-readable protocol](../validation/betse/trajectory_protocol.json)
sets the first horizon to **1 ms**, with two conditions:

- The existing passive baseline, with all three registered permeabilities.
- An all-membrane-blocked control from the same preparation. Require exact zero
  transport and unchanged inventories; separately bound the native initial
  floating-point charge residual, without adjusting the voltage trace.

Use native rounded F/R and explicitly matched F/R as separate BETSE profiles;
only the matched profile is a same-parameter comparison with unchanged Cells.
Native steps are 0.1, 0.05 and 0.025 ms (10, 20 and 40 updates).
Cells RK4 steps are 0.1 and 0.05 ms, on eager and compiled JAX CPU/float64.
D069 clarifies D068's proposed three-backend panel: the existing full production
runner has two JAX execution paths, not a separate NumPy integrator. NumPy supplies
ordinary readouts and independent arithmetic; do not invent a third stepping
loop for this benchmark. These are prospectively specified refinement settings,
**not accepted step sizes** and not inherited from another Cells model or the
single-update check.
Do not add permeability switching, pumps or a longer relaxation run to this
first baseline panel. Those follow only after its numerical qualification.

## Execute the real loops

Use actual native configuration loading, seeding and an INIT phase, followed by
the unmodified `Simulator.run_sim_core` FULL path. The pinned
[runner](../upstream/betse-v1.5.0/betse/science/simrunner.py) normally performs
`SimPhase(INIT)`, `init_core`, then `run_sim_core`; the latter performs
`init_dynamics`, clears storage and computes initial voltage before looping.
Record the actual initial state at that boundary, not a state inferred from
the first saved observation. INIT is a physical transient here, not a claim
that resting equilibrium has been reached.

Use Cells' ordinary checked finite-compartment RK4 execution and its full
transfer histories. Do not integrate BETSE's flux law inside a substitute loop
and call that a native BETSE trajectory. Keep both environments, source/runtime
identities, geometry correspondence, mechanism flags and constants explicit.
Verify `rho_channel == 1` and inactive Ca handling as well as the already
registered disabled mechanisms: the actual FULL loop invokes `ca_handler` even
when its pump and ER branches are disabled.

## Native time and accounting need explicit observation

Pinned [FULL-loop and storage source](../upstream/betse-v1.5.0/betse/science/sim.py)
shows that state is updated before storage, and ordinary per-step sampling
starts at index 1. For N updates of size dt:

```text
native label at index k = k * (N * dt) / (N - 1)
physical time after that update = (k + 1) * dt
ordinary sampled indices = 1, ..., N - 1
```

Thus a ten-update run's first stored state is after two updates, not the initial
state and not the state at its raw label. Export raw labels, loop indices, actual
update counts and physical elapsed times separately. The final label and elapsed
time coincide; checking only endpoints would miss the earlier mismatch.

The ordinary storage method saves concentrations, voltage and aggregate membrane
current, but not the complete per-ion flux/transfer history. A faithful accounting
check needs the initial state and actual per-step fluxes, including the unsampled
first update. Prefer a narrowly scoped read-only profiling observer that copies
native step-boundary data and counts actual native calls. Do not replace the
solver, patch upstream methods, infer flux solely from a later state, or fill a
missing interval by interpolation. Check observer-enabled versus observer-disabled
native outputs before using it as evidence; restore observation hooks reliably.

D069 implements that observer using `sys.setprofile`, filtered to the actual
simulator instance and pinned source filename. It copies the initial state,
pre-concentration-update flux/state, post-voltage-update state and storage
boundaries. Derived `before_elapsed_s` and `after_elapsed_s` columns accompany
the original raw labels; the checker independently verifies their formulas.
An existing profiler is not replaced. Every one of the twelve native
case/profile/step combinations has a fresh unobserved partner. All nine declared
ordinary array fields and ten final array fields must have identical precision,
shape and bytes across partners. This checks exported outputs, not a universal
non-interference guarantee for unobserved internal state or other BETSE modes.

The pinned native flux function adds a `1e-25 V` nonce in place before the
concentration-update boundary. Preserve this behavior and the raw snapshots;
do not erase the nonce or relabel that boundary as a pre-flux observation.

Native current stored after an update is formed from that step's pre-update
fluxes. Compare that quantity with the correctly timed rate/transfer—not blindly
with Cells' post-update instantaneous current. A common state-comparison grid
can include the separately captured initial state and shared elapsed times;
native raw observations must remain available alongside it.

The common state grid is 0 through 1 ms at 0.1 ms intervals. Beginning-of-step
native fluxes and charge-weighted currents compare at 0 through 0.9 ms; the final
1 ms state has no subsequent native flux evaluation in this run. Final stored
current still belongs to the preceding step and is independently checked there.
No final rate is fabricated or interpolated. Transfer sums include every actual
step, including the first unsampled update.

## Prospective capture criteria

The adapter, synthetic observer/clock/accounting tests and static production
readout checks are implemented. All **228 adapter tests pass in 24.234 seconds**,
including 57 new tests; these preflights do not execute either full trajectory.
The protocol and all adapter sources are captured before launching a worker.
They specify:

1. Exact definitions, horizons, timestep ladders and common observation times.
2. Native pre/post-update readout semantics and observer non-interference checks.
3. Absolute/relative voltage, amount, current and integrated-transfer limits;
   independent conservation/charge checks and exact inactive-route requirements.
4. Refinement acceptance within each simulator, plus cross-simulator agreement
   at matched constants. First-order native explicit updates and fourth-order
   RK4 need not agree bit-for-bit or have equal coarse-step error. Near-roundoff
   differences must not be used to estimate a fictitious convergence order.
5. Numerical warnings, nonpositive inventories, source/coverage mismatches,
   resource exhaustion and failed comparisons as retained failures—not grounds
   for silently discarding a run or widening tolerances after seeing it.
6. CPU lanes, worker/whole-job timeouts, artifact budget, exclusive output paths
   and a detached launcher with durable completion/failure records: CPUs 0–3,
   single-threaded numerical libraries, 90 seconds per simulator worker,
   180 seconds for the panel and 64 MiB of artifacts. Budget overruns fail the
   capture; these are prospective bounds, not a measured performance claim.

Instantaneous tolerances remain identical to REF-003c. Per-step amount accounting
uses its 2e-12 fmol absolute limit; cumulative sums use a separately declared
1e-10 fmol allowance for up to forty native concentration updates. Trajectory
limits are 5e-6 V, 1e-7 fmol for amount increments and integrated transfers,
1e-5 fmol/s and 1e-15 A, each with relative tolerance 1e-5. These are explicit
initial numerical budgets, not physiological measurement uncertainties. Comparing
increments avoids hiding transport error under the much larger starting inventory.

Each native constant profile must meet the trajectory limits between its two
finest steps, with contraction at most 0.75 of the coarse-to-middle difference
plus the instantaneous absolute floor for that quantity. Cells' own refinement
and eager/JIT agreement use the tighter instantaneous limits. Cross-program
checks compare the finest matched-constant native run against both finest Cells
runs. Retain the rounded-constant runs and their refinement separately; do not
present them as a same-parameter test.

The capture has 12 observed native runs, 12 unobserved partners and eight actual
Cells runs. It retains native YAML, seed/phase artifacts, all declared raw exports,
complete Cells histories/readouts, warnings, comparison results and source hashes.
An incomplete or failed run stays not qualified, without automatic retry or
post-result tolerance changes. No production equations, old tests or frozen
source capsules are edited.

The detached launcher returns immediately. Follow-up audits/regression require
the user's next instruction under the [no-poll policy](../AGENTS.md). A capture
pass alone is not the later independent evidence closeout. GPU work, stable
promotion, longer relaxation, active mechanisms and biological validation remain
separate gates.
