# REF-003: first corresponding BETSE comparison

2026-09-11, D064; updated 2026-09-17 through D130. Status: **REF-003d v2 and expanded
zero-amplitude SIM bridge independently closed; nonzero dispatch passes;
response rejection independently audited; finer-input dispatch passes;
finer-response independent closeout passes in its fixed finest-held scope;
REF-004a isolated-channel independent closeout passes; REF-004b coupled
configuration/transport preflight preserves native setup and Cells runtime
failures; runtime-corrected capture passes all 37,068 comparisons; independent
single-transfer closeout passes in 3.215 s with zero failures;
full-loop preparation/observer and Cells initial readiness pass in 18.031 s;
their separate saved-data audit passes in 5.541 s with zero failures;
reference-gated coupled pilot and D096 independent closeout pass in their fixed
2 ms four-control scope; D097 initial-history preparation and D098 saved review
pass; D099 paired reference/capture passes in 391.917 s with zero required
failures and 21 retained coarse misses; D100 independent closeout passes in
240.629 s with 8,036,300 independent comparisons and zero mismatches; D101
release-input design checks pass; D102 native panel completed, checker rejection
from zero-flux averaging retained; D103 saved-input closeout passes 916,176
comparisons in 24.469 s without a simulator rerun; D104 piecewise reference
software passes 102 tests and its full reference capture passes 1,485,380
comparisons in 160.675 s; D105 independently closes that reference review and
passes timed native/Cells capture in 1,004.27 s, with 49 coarse misses retained;
D106's separate independent timed-capture audit passes 15,042,946 comparisons /
182 groups in 387.772 s with zero mismatches**. D107 starts the
[realism-driven next tracks](BETSE_REALISM_AND_NEXT_STEPS.md): pump source contact,
junction/lifecycle planning and original biological-data preparation, not a
claim of production pump parity or experimental acceptance.
D108's [independent pump closeout](../reports/REF005A_PUMP_CONTACT_CLOSEOUT.md)
now passes all 1,240 comparisons / 248 raw triplets. D109 adds the
[coupled numerical prerequisite and production route](KINETIC_PUMP_INTEGRATION.md),
not yet a production change or coupled BETSE trajectory qualification.
D110 now [independently closes that six-case numerical scope](../reports/NUM011_COUPLED_CLOSEOUT.md).
D111 adds the [named production process](KINETIC_PUMP_PROCESS.md), with process
qualification/regression and versioned configuration/layout integration distinct
from the already closed numerical candidate. No native coupled or biological
validation follows merely from adding the kernel. D113 now
[reviews that process gate](../reports/SPEC010_PROCESS_CLOSEOUT.md) and implements
the [versioned finite-bath family](KINETIC_FINITE_BATH_MODEL.md) in 0.16.0.dev0.
D114's bounded trajectory/lifecycle/regression acceptance and independent
review now pass. D116 closes the native pump lifecycle; D121
[closes the refined matched 1 ms pilot](../reports/REF005C_PUMP_PILOT_CLOSEOUT.md),
with its original failed attempt preserved. D122's
[longer-duration design](BETSE_PUMP_RELAXATION_PLAN.md) qualifies lossless
recording before a separate 10 ms extension, then relaxation and recovery.
D123 adds the [offline lossless codec](../validation/betse/native_recording/README.md),
132 passing checks and an exact largest-row resource probe. The full 36-row
conversion now passes in 215.987 s, reducing native evidence from 1.51 GB to
18.1 MB. D124's [independent codec review](../reports/REF005D_CODEC_AUDIT_HANDOFF.md)
now independently passes **54.7 million exact comparisons / zero failures**.
D125 [closes offline recording](../reports/REF005D_CODEC_CLOSEOUT.md) and implements
[live recording / matched-window qualification](../reports/REF005D_LIVE_HANDOFF.md)
on the unchanged 1 ms fixture. Native histories stay intact; independent live
review and whole-process memory qualification remain ahead.
D126 [closes the 79-test preflight and proceeds to full live/window qualification](../reports/REF005D_LIVE_QUALIFICATION_LAUNCH.md)
using the exact same tested 668-input source context; no full verdict is implied
by the detached launch.
D127 [preserves its script-prefix logging failure and continues only Cells](../reports/REF005D_LIVE_CONTINUATION_LAUNCH.md).
The completed 36 native overlaps/eighteen pairs pass; all 964 saved files and
stream hash links authenticate for reuse. Fifty-four new regression checks
pass. The original failed run, tested source context, physics and thresholds
stay unchanged; full acceptance and independent live review remain pending.
D128 [corrects its later baseline/recording output collision](../reports/REF005D_OUTPUT_LAYOUT_LAUNCH.md),
preserving both failed runs and all native evidence. Fifty-one fast harness
checks pass; a detached real checkpoint-heavy case now gates the full matrix,
using the same worker for both. No physics, production or threshold changes;
probe/matrix acceptance and independent review are not implied by launch.
The probe and matrix subsequently **pass in 553.910 s**. D129 launches the
[independent saved-output review](../reports/REF005D_LIVE_AUDIT_LAUNCH.md)
after 97 passing preflight checks: direct
native/Cells artifact comparisons and reconstructed expected receipts for
unsaved windows, without another simulation. Independent live closure remains
pending at launch; the two original failures remain preserved.
The D129 review subsequently passes in **128.769 s**. D130
[closes R0](../reports/REF005D_LIVE_CLOSEOUT.md) and launches the
[reference-only 10 ms study](../reports/REF005E_REFERENCE_SCOPE_LAUNCH.md)
detached after **73 passing preflight checks**, keeping the old equations,
solver settings and scientific limits. The study's result remains pending. Native ladder,
resource probes, full matched execution and independent review remain separate.
No longer native run, full release promotion or biological acceptance is claimed.
The [audited seven-cell result](../reports/REF003C_CLOSEOUT.md)
checks all seven native cells using the existing finite-bath model. The original
[one-cell preparation](../reports/REF003B1_PREPARATION.md) remains rejected, and
a literal one-centre SVG fails native triangulation. REF-003b is deferred, not
silently redefined. The earlier [component result](../reports/REF003A_PASSIVE_CONTACT.md)
remains preserved. Neither result establishes biological validation.
The user approved proceeding carefully while bringing in an
external reference soon. This follows the [capability roadmap](BETSE_CAPABILITY_ROADMAP.md)
without waiting for organ models, GPU execution, or every BETSE mechanism.

## Immediate order

1. Finish the existing CORE-010 independent audit, six-context regression and
   development closeout against the frozen acceptance-02 sources. Do not rerun
   its 73-minute simulation capture or promote a stable release implicitly.
2. Make direct, bounded contact with BETSE's unmodified passive-flux function.
   Keep the reference environment and adapter outside the Cells runtime.
3. Complete the [REF-003d v2 refinement](BETSE_PASSIVE_TRAJECTORY_PLAN.md)
   and its independent saved-data closeout. Both now pass with unchanged criteria;
   the [closeout report](../reports/REF003D_CLOSEOUT.md) retains v1's rejection.
   The counterpart uses the existing finite-bath family; the native nonspatial
   bath is not maintained at fixed composition.
4. Review the next passive permeability intervention's phase, input law and clocks.
   The [D072 design/control review](../reports/REF003E_INTERVENTION_DESIGN.md) now
   passes 38 checks. Native events are SIM-only, additive and smooth; existing
   Cells controls are right-continuous and held over each interval.
5. The [REF-003e0 v2 preparation](BETSE_PROFILE_BRIDGE_PREFLIGHT.md) now passes:
   six native preparations / 30 direct dispatches and 87 focused tests, with
   separate profiles-off/default-profile-on/zero-amplitude controls. D075 adds
   the [narrow full-loop pilot](BETSE_FULL_LOOP_BRIDGE.md) and 100 passing focused
   checks before its separate 12-run detached capture, which now passes in
   26.139 s. D076's [independent closeout](../runs/ref-003e0-loop-audit-2026-09-12/audit-01/completion.json)
   now passes 88,956 numerical comparisons and 165 tests in 32.682 s.
   D077's separately approved 72-run expansion passed capture controls in
   203.562 s and was user-reviewed. D078's
   [joint expanded closeout](../runs/ref-003e0-expanded-audit-2026-09-12/audit-01/completion.json)
   passes 1,232,616 comparisons and 433 tests in 167.679 s, with no model rerun.
   The first failed preparation stays unchanged.
6. D079's [held-intervention design/compiler](BETSE_HELD_INTERVENTION.md) checks
   additive/multiplicative input correspondence, true solver subdivisions and
   observation-side contracts. D080's [actual nonzero SIM dispatch preflight](BETSE_NONZERO_DISPATCH_PREFLIGHT.md)
   now passes four preparations / 160 dispatches in 24.463 s and 75 focused
   tests, without transport or integration. D081 now implements the
   [eight-native / 24-Cells control-aware response pilot](BETSE_HELD_RESPONSE_PILOT.md)
   under a prospective 42-minute cap. All 32 runs completed in 715.769 s, then
   comparison rejected 150 of 345,576 checks. D082's [offline audit](BETSE_HELD_RESPONSE_AUDIT.md)
   now closes in 50.390 s, preserving that result and separating a reporting-list
   correction from physics. All 70 new tests pass; the unchanged legacy suite
   records 121 passes / one expected metadata-guard failure from the user's
   ignore-rule edit. D083 implements the [finer-input preflight](BETSE_REFINED_DISPATCH_PREFLIGHT.md)
   from the [refinement design](BETSE_HELD_RESPONSE_REFINEMENT.md): eight fresh
   preparations / 960 dispatches at 12.5/6.25 µs, without integration. All 109
   software tests pass; the actual native result passes in 116.002 s without
   integration. D084 implements the [two finer response panels](BETSE_REFINED_RESPONSE_PANEL.md).
   The separate detached 114-test software result now passes in 95.688 s total,
   with no failures/errors/skips, and was user-reviewed. The subsequent capture
   stopped at its 16 MiB trace guard after 16 native / 26 Cells runs. D085's
   [resource-only continuation](BETSE_TRACE_BUDGET_CONTINUATION.md) changes only
   eight unexecuted definitions to 64 MiB; all 48 resource probes and 47 focused
   tests pass. Reuse completed results and launch only 22 remaining Cells runs,
   then the unchanged comparison (two-hour / 1 GiB combined artifact cap).
   No polling or follow-up audit; actual execution state belongs to its new run
   receipts. The response keeps unchanged scientific limits, fixed-h Cells
   subdivisions and explicitly diagnostic
   cross-h native/resampled-pulse differences; no convergence claim follows
   from a single passing finest-h comparison.
   The continuation now completes in 2239.322 s, with 2,298,936 required checks
   passing and all 4173 diagnostic failures retained. D086's
   [independent closeout](BETSE_REFINED_RESPONSE_AUDIT.md) replays the full saved
   comparison and rebuilds 1,121,904 surface checks separately. All 105 new
   preflight tests pass. The user-reviewed
   [joint result](../runs/ref-003e1-refined-response-audit-2026-09-13/audit-01/completion.json)
   now passes in 249.644 s, including all 336 tests and 2,298,936 required checks.
   Only the specified seven-cell, 1 ms, matched-constant, finest-held 6.25 µs
   response is qualified. No simulator rerun; all 4173 diagnostic failures remain.
7. D087 starts [REF-004a isolated Kv1.5 contact](BETSE_VOLTAGE_GATE_CONTACT.md):
   source/unit/temperature alignment, six voltage protocols and three timesteps,
   with direct native execution and independent discrete/continuous references.
   Reuse production kinetics/shared RK4 without modifying the engine. Short
   preflight preceded a user-reviewed 11.971-second capture, with all 11,266
   comparisons passing. D088's [independent closeout](../reports/REF004A_KV1P5_CLOSEOUT.md)
   now passes in 0.979 s: all numerical rows independently rebuilt, 102 focused
   tests passing, no simulator rerun or change to old evidence. Only the isolated
   channel scope is qualified.
8. D089 implements the [REF-004b configuration/transport preflight](BETSE_CHANNEL_TRANSPORT_PREFLIGHT.md)
   at 298.15 K: four minimal-network controls, actual face-target and cell ownership,
   matched-state channel permeability/flux, one conservative update and explicit
   current/charge/voltage accounting. All 76 focused software tests pass in 2.03 s.
   The [handoff](../reports/REF004B_TRANSPORT_PREFLIGHT_HANDOFF.md) binds one detached
   300-second / 128 MiB attempt; it stopped after 4.672 s on the null biomolecule
   input, before channel/Cells comparisons. D090's [correction](BETSE_CHANNEL_SETUP_FIX.md)
   changes only that entry to an empty list. All 107 focused tests pass, including
   actual native YAML/type-contract checks. The [new handoff](../reports/REF004B_SETUP_FIX_HANDOFF.md)
   binds a fresh capture under unchanged limits; prior failure and criteria stay
   frozen. That attempt completed all twelve native cases but stopped after
   7.084 s before any Cells transfer, on the launcher's explicit-false/unset
   runtime mismatch. D091's [environment correction](BETSE_CHANNEL_RUNTIME_FIX.md)
   preserves the strict guard and both failures. All 152 focused tests and five
   real-worker startup probes pass; the [new handoff](../reports/REF004B_RUNTIME_FIX_HANDOFF.md)
   binds a fresh capture under identical numerical/resource bounds. That capture
   now passes all 37,068 comparisons in 21.272 s. D092's [independent audit](BETSE_CHANNEL_TRANSPORT_CLOSEOUT.md)
   adds exact replay and a separate 80-digit reconstruction of every row;
   all 220 focused tests pass. Its actual closeout now passes in 3.215 s.
   D093's [full-loop preparation](BETSE_CHANNEL_LOOP_PREPARATION.md) checks native
   initialization and read-only observation; [pilot readiness](BETSE_CHANNEL_FEEDBACK_DESIGN.md)
   checks candidate Cells definitions/resources and independent initial rates.
   The actual preparation passes in 18.031 s, with 73,744 native and 348 Cells
   initial-rate comparisons and zero failures. D094's [saved-data closeout](BETSE_CHANNEL_LOOP_CLOSEOUT.md)
   independently rebuilds every row and audits full-state, byte, clock and
   resource contracts. No simulator is rerun; qualification follows only from
   the actual separate audit receipt.
   That audit now passes in 5.541 s. D095's [reference-gated coupled pilot](BETSE_CHANNEL_FEEDBACK_PILOT.md)
   implements base/tight DOP853 and Radau comparison before a 2 ms native/Cells
   panel. It preserves independently evolving states, checked production eager/
   compiled RK4, complete checkpoint resumes and all native observed boundaries.
   Passing capture and independent saved-data closeout remain separate gates.
   D095's actual capture passes in 338.424 s, with zero required failures and
   fourteen retained coarse native diagnostics. D096's [independent audit](BETSE_CHANNEL_FEEDBACK_CLOSEOUT.md)
   reconstructs its saved numerical evidence, complete checkpoints and refinement
   decisions, without a simulator or continuous-reference integration rerun.
   The actual D096 [closeout](../reports/REF004B_FEEDBACK_CLOSEOUT.md) now passes
   in 172.504 s: 5,806,006 independent comparisons, zero mismatches and 24 complete
   checkpoints; all fourteen coarse diagnostic misses remain unchanged.
   No Cells trajectory or automatically launched dynamic panel follows from
   preparation. Physiological data, gap-junction communication and a small
   tissue remain subsequent distinct questions.
9. D097's [history preparation](BETSE_CHANNEL_HISTORY_PREFLIGHT.md) changes only
   initial m/h within paired active/blocked definitions. Check complete initial
   states/RHS, equal visible state/current, distinct opening tendency, candidate
   resources and fresh isolated native gate updates before paired coupled
   references/trajectories. It passes 2,442 comparisons in 14.036 s. D098's
   [review](../reports/REF004C_HISTORY_PREPARATION_CLOSEOUT.md) closes the saved
   preparation in 3.062 s, with all replay rows, 1,404 alternate rates and 528
   layout-array hashes checked. No integration or production change.
10. D099's [paired-history workflow](BETSE_CHANNEL_HISTORY_PILOT.md) implements the
    explicitly requested references and detached comparison as one gated job.
    Twelve actual reference solves must meet convergence/domain/signal criteria
    before native/Cells evolve independently. Preserve per-history accounting,
    refinement and restart checks, then compare signed a-minus-b responses.
    All 56 focused tests pass; these short software fixtures do not qualify the
    full proposed 2 ms window. Capture and independent closeout remain separate;
    no polling, automatic retry or automatic post-capture audit.
    The actual [capture](../reports/REF004C_PAIRED_HISTORY_CAPTURE.md) now passes
    in 391.917 s, with zero required failures and all 21 coarse misses retained.
11. D100's [independent paired audit](BETSE_CHANNEL_HISTORY_CLOSEOUT.md) replays
    frozen checks and separately reconstructs both histories, complete native/
    Cells state, reference mathematics, full checkpoint bytes, contrasts and
    refinement decisions. No integration or production change. The original
    pending-audit receipt remains immutable; actual audit completion supplies
    any scoped qualification. Launch detached, no polling or automatic follow-up.
    Its actual [closeout](../reports/REF004C_PAIRED_HISTORY_CLOSEOUT.md) now passes
    in 240.629 s with 8,036,300 independent comparisons, zero mismatches and
    all 21 coarse misses preserved. Only the registered 2 ms paired scope closes.
12. D101's [channel suppression/release input design](BETSE_CHANNEL_RELEASE_DESIGN.md)
    passes 107 software checks, including 54 real instantaneous CPU probes at
    saved states and 24 candidate Cells grids. It uses existing availability
    controls and proposes an explicit native `maxDm` parameter input, not a
    built-in tissue event or a drug model. No new trajectory/native dispatch.
    D102 supplies the separately implemented native preflight below.
13. D102's [native input preflight](BETSE_CHANNEL_RELEASE_PREFLIGHT.md) checks
    fresh native preparation, one active priming update, state-preserving input
    prefixes and one subsequent update. All 71 software tests pass, including
    real block/release smoke cases and observer partners. The detached full
    panel is 144 phases / 288 updates / 288 applications / 72 pairs, bounded to
    480 s and 256 MiB aggregate artifacts. The query times are not elapsed
    simulation times; full capture/review must precede piecewise references and
    dynamic response. No polling, automatic follow-up or production changes.
    Its actual native work completed without warnings, but the checker rejected
    a one-ULP zero-flux bath change; [failure retained](../reports/REF004D_RELEASE_PREFLIGHT_FAILURE.md).
14. D103's [saved-input review](BETSE_CHANNEL_RELEASE_REVIEW.md) checks the exact
    native averaging operation without normalizing captured data or widening
    physical tolerances. All 66 software tests pass, including 198 actual pinned
    NumPy mean probes and eight saved rows. Freeze all 605 original files and
    175 review inputs before one detached 180 s / 64 MiB job. Actual full-panel
    success, not diagnosis or software tests, supplies scoped input readiness.
    No simulator integration, automatic follow-up or dynamic-response claim.
    The actual [closeout](../reports/REF004D_RELEASE_INPUT_CLOSEOUT.md) passes
    916,176 comparisons in 24.469 s; all 104 original guard rejections remain.
15. D104's [independent piecewise reference](BETSE_CHANNEL_RELEASE_REFERENCE.md)
    keeps the fixed 2 ms window and two history/four condition design. Three solver
    settings yield 24 paths / 48 segment integrations, with exact state carry,
    one-sided switch records, analytic blocked gates and no-op splitting controls.
    All 102 software tests pass in 4.35 s; full seven-cell convergence/domain/signal
    is checked in one detached reference-only job (900 s total, 256 MiB aggregate).
    No native/Cells trajectory is launched by this job. User-directed saved review
    and timed full-loop comparison remain later gates; no polling or automatic retry.
    The actual [reference capture](../reports/REF004D_RELEASE_REFERENCE_CAPTURE.md)
    now passes all 1,485,380 comparisons in 160.675 s, pending independent review.
16. D105's [timed release contract](BETSE_CHANNEL_TIMED_RELEASE.md) combines the
    newly authorized saved-reference review and a gated simulator experiment.
    No simulator starts until independent numerical-column review passes. Keep
    all physical budgets, the 2 ms horizon, four conditions and two histories.
    Check 48 native phases / 32 Cells trajectories, full state carry, separate
    one-sided currents, eight release-boundary restarts, refinement and signed
    contrasts. Launch detached; retain all failures and coarse misses. A capture
    pass remains pending a separately user-directed audit, with no polling,
    retry, reference reintegration, production change or GPU work.
    The actual capture subsequently passes in 1,004.27 s, with 49 coarse misses
    retained and the reference review closed.
17. D106's [saved timed-capture audit](BETSE_CHANNEL_RELEASE_CLOSEOUT.md) is now
    separately authorized: reconstruct all 15,042,946 numeric columns and complete
    checkpoint/state/input evidence, preserving all coarse misses and original
    diagnostics. Reuse the closed reference review without repeating integration
    or its full review. One detached audit, no production change, polling,
    automatic follow-up or broad scientific qualification.
    Its [completed closeout](../reports/REF004D_TIMED_RELEASE_CLOSEOUT.md) now
    passes, preserving all 49 coarse misses. No further channel run is needed.
18. D107 starts [substrate-dependent Na/K contact](BETSE_PUMP_CONTACT.md) in a
    validation-only native/NumPy/JAX panel; a named production pump and coupled
    pump–leak qualification remain subsequent gates. Scope the
    [junction comparison](BETSE_GAP_JUNCTION_PLAN.md) and prepare the
    [original-data benchmark](BETSE_BIOLOGICAL_BENCHMARK_PLAN.md) alongside it.
    Detailed realism must reach at least the BETSE baseline; merely passing
    selected component comparisons cannot fulfill that requirement.
19. D108 independently reconstructs every saved pump comparison without importing
    either simulator or the old oracle; component scope is closed. D109 freezes
    the new kinetic law's chemical-reservoir/ownership contract and implements
    a six-case coupled numerical candidate with independent DOP853/Radau and
    NumPy/compiled-JAX trajectories. Full capture/review comes before production
    preservation, versioned integration and ordinary-runner acceptance. Do not
    reuse the old synthetic pump timestep or call this native full-loop parity.
20. D110 closes all 4,070 candidate comparisons, 3,756 physical records and 12
    restart links without solver reruns. D111 adds a separately named process
    and binds its qualification to the saved 31 matched-constant probes, then
    targeted existing-model regression. Preserve old full-source checkpoint
    identities; versioned host/layout/runner integration remains next.
21. D113 reviews the passing process qualification and preserves 1,273 working
    files before editing production. `finite_extracellular@2` now composes the
    kinetic law through strict host/layout contracts and the ordinary runner.
    Sixty focused checks plus eight controller checks pass; the full 422-test
    development gate remains pending. This does not close coupled native
    correspondence, long biological relaxation, experiments or GPU qualification.

The first seven steps are complete only in the explicitly stated scopes; input-
sampling limitations remain open. The [detached closeout result](../reports/CORE010_CLOSEOUT_HANDOFF.md)
was inspected and its existing source capsule authenticated before REF-003a.
The execution protocol below remains the basis for reproduction. Subsequent
work adds the separately authorized REF-003d v2 bounded capture and D071 closeout
on user instruction, not an automatic campaign. Future long audits/regression retain the no-poll policy.
Failures stop their job and are retained, without automatic retry.

## REF-003a: direct passive-law contact

Use the already reviewed BETSE **v1.5.0**, commit
`5269a714aa2593ed2a6708c4516289977d8ae1a2`, as a deliberate historical reference,
not a claim about the latest release. Authenticate the tag/commit, downloaded
source and license. Record the exact interpreter, dependencies, import paths
and source hashes in a separate environment; do not change `.venv`,
`.reference-venv`, Cells dependencies or production equations to install BETSE.

Import and call the upstream module itself. A transcription of its formula,
an extracted function with replacement dependencies, or a reimplementation is
not an executed BETSE reference. If the intact module cannot run, retain the
setup failure and resolve the environment explicitly.

### Preliminary source mapping

Read-only inspection identifies pinned [`electroflux`](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/sim_toolbox.py)
as a candidate counterpart to Cells' [`ghk_leak`](../src/cells/processes/electrochemistry.py).
REF-003a has now checked this mapping in direct function calls, including
area/thickness scaling and separate native/matched constants; it remains a
component mapping, not a full-model equivalence statement.

| Quantity | Correspondence to check |
| --- | --- |
| Orientation | `cA` is outside, `cB` inside; positive flux is inward and voltage is inside minus outside |
| Concentration | mol/m3 and mM are numerically equal |
| Transport coefficient | With `rho=1`, identify Cells permeability `P` with BETSE `Dc/d` |
| Amount rate | Dimensional inference: multiply upstream flux density by area and divide by `1e-15` for fmol/s |
| Current | Convert using valence and Faraday's constant; name the sign convention |

Check area scaling against call sites; the return docstring is insufficient.
Record both implementations' constants rather than silently changing Cells'.
Upstream adds a small nonce to voltage and valence; preserve fresh inputs and
examine zero-voltage behavior and input mutation explicitly.

Before numerical comparison, freeze the probe values, unit conversions, expected
analytic relations, separate absolute/relative tolerances and bounded execution
settings. Include Na+, K+ and Cl- with negative, zero and positive voltage,
near-zero voltage, single-ion reversal, blocked permeability, orientation
reversal and area scaling. Only select finite states in Cells' declared domain.
Near-zero flux needs an absolute error criterion, not division by a vanishing
reference. Keep native-default and any explicitly matched-constant probes labelled
separately; a parameter-adjusted call is not an untouched-default result.

Compare upstream outputs with the existing Cells process on CPU, including its
normal JAX float64 path, and independent analytic limits. The adapter owns only
conversion and reporting, not an alternative membrane law or solver. Record all
case inputs, outputs, differences, warnings, mutations and failed comparisons.
Prespecify success criteria before seeing comparison outcomes; no case dropping
or tolerance adjustment to obtain agreement.

Deliverable: a small source-bound reference packet and readable comparison table.
This establishes **instantaneous passive-law correspondence only**, not BETSE
trajectory, tissue or biological validation. Keep this first calculation bounded
to seconds rather than starting an overnight simulation campaign.

## REF-003b: one-cell trajectory, conditional on a matched model

**Deferred after the two tested native geometry routes failed to supply one
cell.** The original one-cell protocol and its rejection remain immutable.
The explicitly seven-cell successor is described below; it does not qualify
this original one-cell milestone.

The original candidate was a fixed-volume cell in a maintained bath using
`multispecies_membrane@1`. D066 source inspection shows that BETSE's nonspatial
outside concentrations still evolve, so the amended candidate uses the already
implemented `finite_extracellular@1` family. The native geometry guard
rejects seven cells where one was requested; a literal one-centre SVG also fails
the native triangulator. A genuine one-cell configuration remains unresolved;
see the [alignment design and explicit limitations](BETSE_INITIALIZATION_ALIGNMENT.md).
The spatial family is not needed for this comparison. Keep passive Na/K/Cl
transport with pumps, voltage-gated channels, gap-junction exchange, water,
mechanics, regulation and dynamic extracellular fields absent or disabled.

Before execution, document geometry and membrane area, total capacitance,
temperature, ion inventories, background/fixed charge, voltage convention,
electrical closure, initialization and any equilibration. Establish whether
BETSE can actually express that same model. A one-cell label is not sufficient
if its charge-to-voltage rule or initialization differs.

If there is a mismatch, report it and choose an explicitly corresponding reduction
or propose a separately specified model extension. Do not change established
Cells physics just to reproduce a BETSE curve. Running BETSE's flux function in
our own integrator would test a component, not constitute a full BETSE trajectory.

Select a short horizon and output schedule, qualify timestep refinement in both
simulators, and compare voltage, species amounts, individual currents and
integrated transfers. Retain analytic and accounting checks alongside the external
comparison. Then add a controlled permeability perturbation; do not assume the
current Cells model supports changing bath composition during a run. Independent
solvers need justified tolerances, not bitwise-identical trajectories.

## REF-003c: explicit seven-cell alignment

The [frozen protocol](../validation/betse/cluster_protocol.json) and
[capture result](../reports/REF003C_CLUSTER_ALIGNMENT.md) now cover all seven
native cells / 30 membrane faces, two constant profiles, nine independent
preparations and four prescribed flux footprints. The existing Cells finite-bath
model matches charge closure and instantaneous rates on NumPy, eager JAX and
compiled JAX; prescribed native single updates preserve mapped inventories.
The capture passes 19,691 scalar checks in 18.666 seconds with no worker warnings.
The separate [saved-packet audit and closeout](../reports/REF003C_CLOSEOUT.md)
now pass all 171 short adapter tests, including the 25 preflights and 43 new
actual-packet checks. The original capture is not rerun or rewritten.

Keep the native source-specific effective bath volume `30 * p.vol_env` in the
adapter only. Prepared snapshots are explicitly new initial states, not simulated
histories. Immobile auxiliary ions reduce to fixed charge only for the selected
passive/charge model, not for chemistry, osmolarity or resolved fields.

## REF-003d: v1 rejected; v2 bounded trajectory qualified and closed

The original 1 ms panel completed in 79.695 seconds with all 32 runs and no
warnings. It failed 36/129384 checks on shared-bath Na/K amount increments;
the [independent audit](../reports/ref-003d-failure-audit.json) reproduces that
rejection without model execution. No failed criterion is relaxed. The
[v2 protocol](../validation/betse/trajectory_refinement_protocol.json) specifies
native 25/12.5/6.25 µs steps and 128 MiB of artifacts, retaining the original
Cells runs, physics, all tolerances, CPU lanes and 180-second wall limit.
Repeated native 25 µs runs and all Cells arrays match v1 exactly. The capture
passes all 435,144 comparisons in 104.031 s. The separate model-import-free audit
reproduces the result; all 325 adapter tests pass, including 49 new evidence
checks. See the [independent closeout](../reports/REF003D_CLOSEOUT.md).

The original model/measurement requirements below still apply. The v1 numerical
packet remains failed and immutable; v2 has a separate registration and result.

The [implemented design](BETSE_PASSIVE_TRAJECTORY_PLAN.md) and
[prospective protocol](../validation/betse/trajectory_protocol.json) specify a
1 ms baseline and all-blocked control, with a read-only native observer and
independent step refinement. All 228 short adapter tests pass, including 57 new
preflights, before numerical capture. Execute the actual native FULL
initialization-phase transient and the corresponding unchanged Cells checked RK4
runner. Its full backends are eager and compiled JAX; NumPy readouts and independent
arithmetic are not a third integrator. Start from the neutral preparation;
do not call it an equilibrated resting cell. Use all seven cells and their shared
bath. Freeze horizon, independent timestep-refinement ladders, tolerances and
resource limits prospectively; a prescribed 0.1 ms update does not establish a
stable or accurate integration step.

Retain the initial state, actual native step counts, raw stored time labels and
an explicitly derived elapsed-update-time column. Native schedule construction
and full-loop observation timing have now been checked on the completed v1 packet.
Every observed native run has an unobserved byte-comparison partner. Distinguish flux/current
evaluated before a step from state saved after it. Compare matched constants
directly and report native rounded constants separately. Keep independent
conservation/charge checks alongside the external curves. Only after the baseline
passes, add a declared permeability perturbation; pumps and other active
mechanisms remain later work. V1 used 180 seconds / 64 MiB; v2 keeps the time bound
and explicitly raises storage to 128 MiB for the finer traces. Both use exclusive
artifacts and retained failures. The [original launch record](../reports/REF003D_TRAJECTORY_LAUNCH.md)
is not a current success claim.
The independent actual-packet audit was authorized separately and is now complete.
Future captures still return control without polling or automatic follow-up.
A bounded trajectory pass is not biological validation.

## REF-003e: phase and control semantics before intervention response

The [source-bound design](BETSE_INTERVENTION_PLAN.md) and
[38 passing checks](../reports/REF003E_INTERVENTION_DESIGN.md) identify a required
new bridge: the accepted transient used INIT, which never fires scheduled
interventions. A SIM-from-neutral no-event/blocked comparison and enabled
zero-amplitude no-op must qualify the phase/event path separately.

Native permeability events add a logistic pulse relative to the tissue default.
The candidate suppression/recovery has nonzero tails and is not an exact square
block. Native raw labels differ from elapsed update time; scale all three native
pulse time parameters explicitly and retain both clocks. Actual source control
values agree with independent elapsed-time arithmetic at 280 points within
2.665e-15. That D072 review executed no event handler, model initialization or
ODE runner. D073 separately attempted native preparation, with the failure below.

First compare the same declared native-step-held input, using existing Cells
numeric controls. Distinguish forcing refinement from actual solver-grid
refinement; old nominal Cells steps may collapse to identical event-split grids.
Continuous-waveform semantics, hard square blocks and a standard initialized
SIM continuation are separate later contracts. No production source, original
numerical tolerance or prior qualification is changed by this design.

The [D073 native preflight](../reports/REF003E0_PHASE_PREFLIGHT.md) is failed,
not a trajectory result. The profiles-off baseline has no resolved default tissue
or target map for the planned targeted events. The [profile bridge amendment](BETSE_SIM_PHASE_BRIDGE.md)
must retain a profiles-off control, then independently test default-only profiles
and enabled zero-amplitude events. Preserve partial setup data before optional
metadata checks. No further preparation or trajectory was launched automatically.

D074 then implements the [separate v2 profile bridge](BETSE_PROFILE_BRIDGE_PREFLIGHT.md)
on user instruction. All six native preparations and 30 direct dispatches pass
in 17.360 s, with 87 focused tests passing. Initial values match retained INIT;
between-configuration physical setup and no-op state/control arrays match exactly.
Partial records survive optional metadata failure. This resolves preparation,
not full-loop noninterference or trajectory correspondence. Register the latter
separately with its own coverage, runtime/storage budget and unchanged criteria.

D075 implements that boundary first as a [12-run pilot](BETSE_FULL_LOOP_BRIDGE.md)
using D074's exact input coverage and observed/unobserved partners. No additional
Cells trajectory is needed for the phase/profile/no-op comparison against
retained INIT. Its 100 focused tests pass in 7.45 s; the
[handoff](../reports/REF003E0_FULL_LOOP_PILOT.md) separates prospective registration,
detached capture status and later independent audit. The 72-run expanded
constant/timestep bridge remains future work, not an inferred pilot result.

D075's completed capture reports passing controls for all twelve runs. D076
now provides the [offline audit contract](BETSE_FULL_LOOP_AUDIT.md), 65 passing
actual-evidence/corruption tests and a detached numerical/regression closeout
boundary. It makes no new model calls or tolerance changes. Its user-reviewed
closeout now passes all 88,956 comparisons and 165 tests, qualifying only the
narrow SIM pilot. The historical [audit handoff](../reports/REF003E0_PILOT_AUDIT_HANDOFF.md)
stays frozen. D077's [expanded handoff](../reports/REF003E0_EXPANDED_BRIDGE.md)
registers both constant sets and three timesteps, under new prospective
resources. The 72-run capture now passes in 203.562 s; its 802 files are retained
unchanged. D078's [audit handoff](../reports/REF003E0_EXPANDED_AUDIT_HANDOFF.md)
stays frozen; its separate joint closeout now passes 1,232,616 comparisons and
433 tests, qualifying the expanded zero-amplitude bridge. D079's
[held-input design](BETSE_HELD_INTERVENTION.md) extends the frozen D072 plan
without editing accepted checkers or production. Its control-only probes add
no nonzero event-dispatch, trajectory or biological evidence.

D080 separately [executes native nonzero dispatch](../reports/REF003E1_DISPATCH_PREFLIGHT.md)
at all 40 first-pilot input times for each of four conditions. All 160 calls /
57,600 diffusion-value checks pass; actual targets and modifiers agree and
physical state is unchanged at dispatch. The 201-file attempt and 80-source
capsule are retained. This still does not run a response trajectory or qualify
nonzero full-loop observer noninterference, refinement or biological recovery.

D081's [response pilot](BETSE_HELD_RESPONSE_PILOT.md) is the separate integration
step, with four input conditions, six Cells solver/backend combinations per
condition and observed/unobserved native partners. Its new saved-data checker
uses the actual per-interval permeability, independently prescribed controls,
41 state/ledger boundaries and 40 comparable fresh-rate boundaries. It does
not invent a final native RHS or treat permeability recovery as state recovery.
The [handoff](../reports/REF003E1_RESPONSE_PILOT.md) fixes scope and resources
before launch; no post-capture tuning or automatic follow-up campaign is allowed.

D082 preserves that completed rejection and adds a separately versioned
[failure-audit contract](BETSE_HELD_RESPONSE_AUDIT.md). The finer saved
constant-input baselines support a timestep diagnostic without rerunning a
model. They do not establish convergence for the scheduled pulse, whose held
input changes when native integration is refined. Keep those effects separate
in any later experiment and do not alter the production solver to match a
coarse external result.

## Later biological contact and scope

The 2016 [published validation examples](https://www.frontiersin.org/journals/bioengineering-and-biotechnology/articles/10.3389/fbioe.2016.00055/full)
are a subsequent target, starting with the Xenopus oocyte example after matching
its physiology and preparation. Cells' synthetic Na/K pump is not automatically
BETSE-equivalent. Longer simulated times require their own numerical qualification.

Maintain separate verdicts for source/equation correspondence, cross-simulator
numerical agreement, and agreement with experimental measurements. Neither an
internal acceptance pass nor agreement between two programs validates biology by
itself.
