# Optional BETSE reference adapter

REF-003a, REF-003b1 and REF-003c, 2026-09-12. This is an **offline validation tool**, not part of the
installed Cells package, solver, model registry or ordinary test collection.
It uses separate worker processes and environments. No upstream implementation
is copied into Cells' production package.

The [result](../../reports/REF003A_PASSIVE_CONTACT.md) qualifies an instantaneous
passive-law comparison only. That capture did not run full BETSE initialization,
electrical closure or time integration. `SimpleNamespace(F, R)` supplies the two declared
constants consumed by the intact upstream function; it is not a replacement
Simulator or a fully loaded BETSE configuration. This paragraph describes the
completed REF-003a capture. The newer REF-003b1 preparation does load a native
configuration and seed; see its rejected-fixture status below. REF-003c now runs
actual initialization, charge/RHS and prescribed-update probes on explicitly
seven cells. Its capture and separate audit/closeout now pass, with all 171 short
adapter tests passing; see the limited scope below.

## Source and environment

The clean checkout is `upstream/betse-v1.5.0`, pinned at
`5269a714aa2593ed2a6708c4516289977d8ae1a2`. The installed BETSE package in
`upstream/betse-venv` is independently checked against all **332 upstream Python
files**, not just its flux function. Its source license is recorded by hash;
upstream attribution remains in the checkout and installed distribution.

The reference uses Python 3.13.5 and the separate [dependency lock](requirements-lock.txt).
This is a newly resolved 2026 reference environment, not the historical environment
used for the 2016 paper or 2025 release. The initial install has durable
[package provenance](../../runs/ref-003a-2026-09-12/setup-01/install.json) and
[installation log](../../runs/ref-003a-2026-09-12/setup-01/pip.log).
Neither `.venv` nor `.reference-venv` was modified.

For a new installation only, with those destinations absent:

```bash
git clone --depth 1 --branch v1.5.0 --single-branch https://github.com/betsee/betse.git upstream/betse-v1.5.0
git -C upstream/betse-v1.5.0 rev-parse HEAD
.venv/bin/python -m venv upstream/betse-venv
upstream/betse-venv/bin/python -m pip install -r validation/betse/requirements-lock.txt
upstream/betse-venv/bin/python -m pip install --no-deps ./upstream/betse-v1.5.0
```

Verify the commit before installation. Do not recreate or install over an existing
reference environment. Capture checks the exact installed runtime inventory and
source bytes, and refuses a dirty or different checkout. Python build-tool/wheel
metadata is not itself a claim of historical bitwise package reproducibility.

## Frozen comparison

[Protocol](protocol.json) fixes 54 probes and limits before upstream numerical
evaluation. Na/K/Cl each have seven voltages, two constant-specific Nernst points,
blocking, orientation reversal, area and thickness scaling, three equal-concentration
limits, and two exponent-domain stress points. The latter approach ±1.31 V and are
mathematical stress tests, not plausible physiological voltages. These are
prescribed instantaneous states, not charge-initialized cell worlds.

The adapter compares both source-declared and explicitly matched F/R profiles
against independent 70-digit decimal arithmetic. Only the matched profile is
the same-parameter BETSE-versus-Cells comparison. Cells is evaluated through its
unchanged NumPy, eager JAX and compiled JAX process paths on CPU/float64.

Limits are `2e-12 fmol/s + 2e-11 * abs(reference)` for amount rates and
`2e-22 A + 2e-11 * abs(reference)` for derived inward currents. Blocked transport
must be exactly zero. Fresh arrays isolate upstream's small voltage/valence
argument perturbations, and saved pre/post-call inputs are checked explicitly.
No probe, equation or tolerance was changed after numerical capture.

Run a fresh bounded capture and a separate read-only audit:

```bash
.venv/bin/python -B validation/betse/contact.py capture runs/betse-contact-new
.venv/bin/python -B validation/betse/contact.py audit runs/betse-contact-new --receipt reports/betse-contact-new-audit.json
```

Capture requires the [preserved development evidence](../../reports/ref-003a-preservation.json).
It registers inputs and adapter hashes before work, saves its source capsule,
uses CPU 0–3 and single-thread numerical libraries, and bounds each worker to
20 seconds and the capture to 60 seconds/16 MiB. It refuses existing output and
retains failures. The auditor authenticates files and replays numerical checks
without calling either model. Long future jobs must follow the root
[detached/no-poll policy](../../AGENTS.md); there is no automatic trajectory campaign.

## Tests and source boundary

Always-available adapter tests use synthetic records solely to test the checker:

```bash
.venv/bin/python -B -m pytest -q -W error validation/betse/test_contact.py
```

Additional tests require the actual saved `contact-01` packet and pinned checkout:

```bash
.venv/bin/python -B -m pytest -q -W error validation/betse/test_contact.py validation/betse/test_saved_contact.py
```

They audit the actual capture and reject nine rehashed corruptions. These 52
checks are separate from the previously passed 4190-test Cells matrix. All 352
captured implementation/protocol files remain unchanged, so no new production
matrix or long regression job was launched for this isolated adapter.

## REF-003b1: native preparation, currently rejected

[Result](../../reports/REF003B1_PREPARATION.md), [design](../../docs/BETSE_INITIALIZATION_ALIGNMENT.md),
[prospective protocol, revision 2](alignment_protocol.json), [driver](alignment.py).
The native v1.5.0 single-cell configuration seeds seven cells / 30 membrane
faces; the unchanged one-cell guard stops before numerical alignment or a
trajectory. The default general network is now explicitly disabled. This is
not a qualified whole-cell comparison. All five short attempts remain under
`runs/ref-003b1-2026-09-12` with generated configurations, logs and source capsules.

Audit the saved rejection without running either simulator:

```bash
.venv/bin/python -B validation/betse/preparation.py runs/ref-003b1-2026-09-12/alignment-05 --receipt reports/new-preparation-diagnostic.json
```

The diagnostic returns `mismatch_confirmed`, never a numerical acceptance. Its
13 actual-evidence tests and the 38 synthetic checker/guard tests can run with
the 52 preserved REF-003a tests:

```bash
.venv/bin/python -B -m pytest -q -W error validation/betse/test_contact.py validation/betse/test_saved_contact.py validation/betse/test_alignment.py validation/betse/test_preparation.py
```

The downstream one-cell voltage/RHS/update comparator is implemented but has not
executed against native BETSE. Do not rerun unchanged preparation expecting it
to pass. The new SVG probe and separately named seven-cell comparison below
preserve these prior captures/source capsules and the detached/no-poll policy.

## REF-003c: explicit seven-cell capture and independent closeout pass

[Result and limitations](../../reports/REF003C_CLUSTER_ALIGNMENT.md),
[protocol](cluster_protocol.json), [driver](cluster_alignment.py),
[saved-state checker](cluster_check.py), [preflight tests](test_cluster.py).
The [one-centre SVG probe](geometry_probe.py) fails native Delaunay triangulation;
its diagnostic and source capsule are retained separately from the earlier
one-cell rejections. No upstream or Cells production code is patched.

The registered seven-cell fixture maps all seven volumes and membrane owners,
not just one trace, to existing `finite_extracellular@1`. Nine prescribed
preparations and four flux footprints check charge, instantaneous transport and
one native update, with native/matched constants distinct. Cells evaluates the
actual NumPy/eager/JIT CPU float64 voltage/RHS paths. Initial preparations pass
production domain checks and do not fabricate transfer-history ledgers. Maximum
permeability and [0,1] availability remain separate concepts.

The saved `runs/ref-003c-2026-09-12/cluster-01` capture passes 19,691 numerical
checks in 18.666 seconds, with no worker warnings. It binds 14 payloads, including
the registration and source capsule. All 25 new preflight tests pass. This is not
a full native or Cells trajectory, biological validation, field correspondence
or GPU test. Existing source-bound one-cell adapter files remain frozen.

The [independent closeout](../../reports/REF003C_CLOSEOUT.md) now passes. The
frozen audit replays 19,691 comparisons; [cluster_evidence.py](cluster_evidence.py)
also independently anchors runtime/geometry claims and checks the one-centre
failure's meaning. [Actual-packet tests](test_saved_cluster.py) demonstrate
numerical/metadata/geometry rejection after rehashing and prevent either simulator
from being imported by the audit. All 171 adapter tests pass. The new evidence
layer leaves the frozen capture/checker sources unchanged.

For a deliberately requested read-only replay, choose absent receipt destinations:

```bash
.venv/bin/python -B validation/betse/cluster_evidence.py cluster runs/ref-003c-2026-09-12/cluster-01 --receipt reports/new-cluster-audit.json
.venv/bin/python -B validation/betse/cluster_evidence.py geometry runs/ref-003b1-2026-09-12/geometry-01 --receipt reports/new-geometry-audit.json
```

The original frozen-checker receipt remains `reports/ref-003c-audit-01.json`.
The closeout binds the original capture receipt SHA-256 as well as the independent
checks; changing copies and their local hashes is not a new authenticated native run.
Do not overwrite any existing capture, audit, preservation or closeout receipt.

For a deliberately authorized new capture only, with an absent output directory:

```bash
.venv/bin/python -B validation/betse/cluster_alignment.py capture runs/betse-cluster-new
```

Capture bounds workers to 25 seconds each, total runtime to 60 seconds and
artifacts to 32 MiB; output paths are exclusive and failures are retained.
No repeated polling or automatic follow-up campaign is scheduled. REF-003d below
adds the separate FULL/Cells RK4 adapter, preserving these captured sources.

## REF-003d v1: actual-loop panel completed, numerical criteria failed

The capture completed all 24 native/eight Cells runs in 79.695 s without warnings,
but failed 36 of 129384 comparisons on shared-bath Na/K amount increments.
The [failure audit](../../reports/ref-003d-failure-audit.json) reproduces that
rejection without model imports; all 119 files are preserved. The original
source capsule, protocol, launch report and numerical rejection are immutable.
The original engineering description follows; v2 is a separate panel below.

[Design](../../docs/BETSE_PASSIVE_TRAJECTORY_PLAN.md),
[protocol](trajectory_protocol.json), [launch report](../../reports/REF003D_TRAJECTORY_LAUNCH.md).
All **228 adapter tests pass**, including 57 new observer, synthetic accounting,
clock/field-coverage and static production readout tests. These preflights do not
run either full trajectory or qualify the proposed steps.

[native_observer.py](native_observer.py) uses a scoped Python profiling hook to
copy actual native FULL-loop boundaries. It never replaces BETSE methods or
integrates a substitute law. [trajectory.py](trajectory.py) runs native seed/INIT
and the unchanged Cells checked RK4 runner in isolated processes.
[trajectory_check.py](trajectory_check.py) checks saved arrays with independent
arithmetic; it imports neither simulator nor NumPy/JAX. Geometry and runtime map
through the separately authenticated REF-003c closeout.

The panel has a 1 ms passive baseline and an all-blocked control: three native
steps, two constant profiles, and a fresh unobserved partner for every observed
run (12 + 12 native runs). The eight Cells runs cover two steps on the actual
eager/JIT JAX backends. The earlier NumPy/eager/JIT instantaneous panel must not
be confused with three full integrators; production has no NumPy-only runner.

Raw labels and derived elapsed times are stored separately. The native first
unsampled update and all per-ion fluxes are retained. Declared ordinary and final
array sets must match bytes across observer modes. Conservation, charge, exact
blocking, within-program refinement and matched-constant cross-comparisons have
prospective limits. Raw current-after-update belongs to the preceding flux step;
there is no fabricated final instantaneous native rate.

For a deliberately authorized new capture, use an absent directory:

```bash
.venv/bin/python -B validation/betse/trajectory.py launch runs/ref-003d-new/trajectory-01
```

The launch registers definitions/protocol/source hashes and `sources.zip` before
starting detached execution, then returns `launch.json` immediately. CPUs 0–3,
single-threaded numerical libraries, 90 seconds per worker, 180 seconds total
and 64 MiB bound this first panel. Workers retain `betse.stdout.log`,
`betse.stderr.log`, `cells.stdout.log` and `cells.stderr.log`; outer logs are
`runner.stdout.log` and `runner.stderr.log`. Success writes `comparison.json`
and `verification.json`; errors write `failure.json` and retain partial data.
The native configuration, phase/seed artifacts and full declared exports stay
beside complete Cells histories and readouts. No failed run is silently retried.

Do not edit captured sources after registration, overwrite receipts, automatically
poll, or begin a follow-up audit/regression job. The user will request status;
independent actual-packet audit/corruption tests follow separately. A numerical
capture pass alone is not that independent closeout, biological validation,
family-wide parity, stable promotion or GPU qualification.

## REF-003d v2: native timestep refinement, with frozen workers and criteria

[Protocol](trajectory_refinement_protocol.json), [report](../../reports/REF003D_TRAJECTORY_REFINEMENT.md),
[versioned harness](trajectory_refinement.py), [registration checks](trajectory_refinement_context.py),
[comparison/overlap checks](trajectory_refinement_check.py).

The native step ladder becomes 25/12.5/6.25 µs, with 40/80/160 updates. All physical
inputs, Cells definitions/steps/backends, times, constants and numerical limits
are identical to v1. The twelve observed runs and twelve fresh unobserved partners
now contain 1120 observed native steps. Complete recording uses a prospectively
increased 128 MiB allowance; CPU lanes 0–3, 90-second workers and 180 seconds total
stay unchanged. No timestep extrapolation is used as a simulation result.

The new harness calls the frozen v1 actual-model workers without altering their
globals. Its comparator uses the same frozen saved-state arithmetic and adds
exact old/new overlap requirements for the eight native 25 µs records and all
eight Cells numerical records. Timing metadata are excluded from that comparison.
The retained old geometry, model definitions and runtime independently anchor
the new registration. All 29 old captured source files remain unchanged.

[trajectory_failure.py](trajectory_failure.py) preserves/replays the first
rejection and independently calculates its endpoint diagnostic without model
execution. All 276 adapter tests pass, including 48 new versioning, 80/160-step
synthetic observer, import-fenced audit, rehashed-overlap and failure-handling
checks. Neither actual-model worker is called by these new preflights.

For an explicitly authorized fresh panel with an absent destination:

```bash
.venv/bin/python -B validation/betse/trajectory_refinement.py launch runs/ref-003d-v2-new/trajectory-01
```

The launcher registers the protocol and 35-source capsule before starting detached
execution. Logs and completion/failure records follow the v1 naming above; no
automatic retry, polling or post-capture audit is scheduled. Keep v1 failed,
and freeze all v2 sources after registration. The user requests the next status
check; a fresh pass still needs its separate actual-packet closeout. The retained
September 12 capture now has that D071 closeout below; the launch report remains
an immutable historical record.

## REF-003d v2: independent saved-data closeout (D071)

[Report](../../reports/REF003D_CLOSEOUT.md),
[audit](../../reports/ref-003d-v2-evidence-audit.json),
[closeout](../../reports/ref-003d-closeout.json),
[evidence guards](trajectory_evidence.py),
[actual-packet tests](test_saved_trajectory.py),
[preservation/closeout driver](trajectory_closeout.py).

The 104.031-second capture passes all **435,144 comparisons**, maximum normalized
error 0.559745, at unchanged tolerances. Independent replay, anchored metadata,
auxiliary export links and all **325 adapter tests** (49 new) pass. The audit
uses only saved data and the frozen arithmetic, with an import fence against
both models and NumPy/JAX. It does not decode native pickles or call a stepper.
All 119 files in each trajectory packet, all 35 v2 captured sources and all
352 accepted implementation files remain unchanged. V1 stays rejected.

For an authorized read-only replay, choose an absent receipt path:

```bash
.venv/bin/python -B validation/betse/trajectory_evidence.py --receipt reports/ref-003d-v2-audit-new.json
```

Checks use `python -m pytest` from the repository root (the older adapter
modules require that import path). Passing receipts split the existing 276
checks (38.36 s) and 49 new checks (91.26 s). The new group exceeded the short-run
estimate; future full adapter suites should run detached with durable logs and
user-requested status, not assistant polling. Tests stage one ordinary packet
copy in pytest scratch before hard-linking scratch copies; unlink-before-write
avoids changing shared evidence inodes. First setup-error receipts are also
retained and explained in the report.

This is only 1 ms seven-cell passive/blocked trajectory correspondence, not
biology, an equilibrated resting state, family-wide BETSE parity or GPU coverage.
D072 below verifies the next phase/control design; it requires a SIM-phase bridge
before a suppression/recovery trajectory. No follow-up capture or full production
matrix runs automatically.

## REF-003e: intervention source/control design (D072)

[Design](../../docs/BETSE_INTERVENTION_PLAN.md),
[report](../../reports/REF003E_INTERVENTION_DESIGN.md),
[candidate inputs](intervention_plan.json),
[control-only checks](intervention_design.py),
[tests](test_intervention_design.py),
[review receipt](../../reports/ref-003e-design-review.json).

All 38 focused checks pass in 3.67 s, without integration. They authenticate the
closed trajectory sources, check native SIM-only event ordering and raw-clock
construction, call the pinned pulse function at 280 points, and exercise existing
Cells control/grid interfaces. Simulation-entry module imports are fenced; no
event handler, geometry seed, model initialization or trajectory runner is called.
Native startup diagnostics are retained inside structured probe output.

D073 below implements the REF-003e0 SIM-from-neutral adapter/observer and records
its first failed preflight. Later qualify a corresponding step-held smooth input; do not
infer exact square blocking or continuous-waveform RK4 support. Existing captures,
audit tooling, production source, dependencies and numerical criteria remain
unchanged. No trajectory is registered/launched by this design review.

The focused design tests, unlike the full adapter suite, currently take seconds:

```bash
taskset -c 0-3 .venv/bin/python -m pytest -q validation/betse/test_intervention_design.py
```

Any full adapter/production regression or future long capture stays detached
with durable logs/results and user-requested status checks.

## REF-003e0: SIM preparation adapter and failed prerequisite (D073)

[Bridge note](../../docs/BETSE_SIM_PHASE_BRIDGE.md),
[attempt report](../../reports/REF003E0_PHASE_PREFLIGHT.md),
[handoff](../../reports/ref-003e0-preflight-handoff.json),
[adapter](phase_bridge.py), [mapping/guard](phase_bridge_context.py),
[event observer](native_event_observer.py).

The first preparation-only native attempt stopped in 9.491 s at metadata export:
the profiles-off baseline has no `dyna.tissue_default`. Targeted events additionally
need the missing target map. The zero-amplitude row was not reached; no native
preparation result, full-loop observer noninterference or trajectory is qualified.
The failed packet and its source capsule remain under
`runs/ref-003e0-2026-09-12/preflight-01`. A new guard rejects another launch of
that unamended candidate. No profile activation, native patch or retry occurred.

All 73 focused software/negative-evidence checks pass:

```bash
taskset -c 0-3 .venv/bin/python -B -m pytest -q \
  validation/betse/test_phase_bridge.py validation/betse/test_native_event_observer.py
```

These tests use synthetic observer fixtures, source checks and the retained
failure; they launch neither simulator. The earlier 325-test full adapter suite
and 4190-test production matrix were not rerun. Next explicitly version the
profiles-off/default-profile-on/zero-amplitude configurations and improve partial
state persistence before a fresh bounded preparation attempt. Do not run the old
candidate again or interpret passing unit tests as preparation acceptance.

## REF-003e0 v2: explicit default-profile preparation (D074)

[Design](../../docs/BETSE_PROFILE_BRIDGE_PREFLIGHT.md),
[result](../../reports/REF003E0_PROFILE_BRIDGE.md),
[handoff](../../reports/ref-003e0-v2-handoff.json),
[plan](profile_bridge_plan.json), [adapter](profile_bridge.py),
[saved-preparation checker](profile_bridge_check.py), [tests](test_profile_bridge.py).

All six native preparations / 30 direct event dispatches pass in 17.360 s:
passive and blocked cases under profiles-off, homogeneous default-profile-on,
and enabled zero-amplitude Na/K/Cl configurations. Initial values match retained
INIT; physical preparation and no-op dispatch arrays match exactly across all
three configurations. Intermediate state is saved before optional metadata checks.
The native cutting request stays configured but is ineffective with no cut
profiles; configured and effective flags are recorded separately.

The 59-file packet is under `runs/ref-003e0-v2-2026-09-12/preflight-01`.
The source capsule contains 51 files and all 332 installed native Python files
match the pinned upstream source. No integration, Cells worker, full-loop observer
noninterference test or trajectory qualification occurs. D073's rejected attempt,
source files and launcher guard remain unchanged.

All 87 new focused checks pass in 2.10 s; they read saved native evidence without
rerunning it:

```bash
taskset -c 0-3 .venv/bin/python -B -m pytest -q validation/betse/test_profile_bridge.py
```

Next specify/implement the separately budgeted full-loop phase/profile/no-op
bridge and its observed/unobserved partners. The old full adapter suite and
4190-test production matrix were not rerun. No follow-up job is running or
launched automatically; long jobs and subsequent audits remain user-polled.

## REF-003e0: narrow full-loop pilot (D075)

[Contract](../../docs/BETSE_FULL_LOOP_BRIDGE.md),
[prelaunch handoff](../../reports/REF003E0_FULL_LOOP_PILOT.md),
[plan](full_loop_bridge_plan.json), [adapter](full_loop_bridge.py),
[lifecycle observer](full_loop_observer.py), [saved-data gates](full_loop_bridge_check.py).

All 100 focused checks pass in 7.45 s before native execution. The pilot has
12 freshly seeded full-SIM runs: two cases, three profile/event configurations,
observed/unobserved partners, matched constants, 25 µs, 1 ms. Six observed runs
give 240 dispatches, of which 80 have zero-amplitude targeted events enabled.
No new Cells run; exact comparison uses the retained corresponding INIT records.
The later 72-run expanded bridge is not covered by this pilot.

Focused reproduction (no native integration; use a fresh XML path if recording):

```bash
taskset -c 0-3 .venv/bin/python -B -m pytest -q validation/betse/test_full_loop_bridge.py validation/betse/test_full_loop_observer.py
```

Earlier handoff tests can bind the complete adapter directory of their historical
capsule. Reproduce those in their recorded source context, not by assuming every
historical live-directory check is valid after new adapter files are added. No
old full suite or production matrix is rerun in this slice.

After the separate prelaunch receipt, the explicit one-shot launch command is:

```bash
.venv/bin/python -B validation/betse/full_loop_bridge.py launch runs/ref-003e0-loop-2026-09-12/pilot-01
```

It refuses an existing output directory or changed source/prelaunch inputs.
The detached supervisor bounds the worker at 120 seconds and checks 150 seconds
overall; CPUs 0–3, a 256 MiB between-row panel cap and a 32 MiB worker per-file
OS limit are explicit. The capsule has 58 adapter/input files. Native sources,
all 352 accepted implementation files / 51 production modules and previous
evidence stay unchanged. Capture controls can pass only pending independent
audit. The user asks for status; no polling, follow-up audit or retry is automatic.

## REF-003e0: independent saved-pilot audit (D076)

[Contract](../../docs/BETSE_FULL_LOOP_AUDIT.md),
[handoff](../../reports/REF003E0_PILOT_AUDIT_HANDOFF.md),
[audit](full_loop_audit.py), [detached job](full_loop_audit_job.py),
[actual-evidence tests](test_saved_full_loop.py).

The pilot's capture passed in 26.139 s. All 65 new evidence preflight tests pass
in 16.47 s, including actual records and rehashed corruptions. The numerical
audit remains a separate stage: 88,956 comparisons using original independent
arithmetic and tolerances, plus source/metadata/physical/event controls. No model
or NumPy/JAX imports, pickle loading or integration is allowed in that worker.

After its separate prelaunch receipt, the explicit detached closeout command is:

```bash
.venv/bin/python -B validation/betse/full_loop_audit_job.py launch runs/ref-003e0-loop-audit-2026-09-12/audit-01
```

The job runs the numerical audit, then 165 focused tests (D075's 100 plus the new
65), and qualifies the narrow pilot only if all gates pass. It captures 62 source
files, including the unchanged original 58. Each stage has 90 seconds; total
elapsed and retained-output limits are 210 seconds and 64 MiB. All 142 pilot
files and prior accepted/rejected evidence stay unchanged. No old full adapter
suite, 4190-test production matrix, retry or expanded simulation. Status remains
user-polled; the prelaunch handoff is not a claim that the audit has completed.

The subsequently user-polled D076 completion now **passes**: 88,956 independent
comparisons, 165 focused tests, 32.682 s total. It qualifies only the narrow
matched-constant 25 µs / 1 ms SIM pilot. Its historical handoff/capture receipts
and all original evidence stay unchanged.

## REF-003e0: expanded full-loop bridge (D077)

[Contract](../../docs/BETSE_EXPANDED_BRIDGE.md),
[prelaunch handoff](../../reports/REF003E0_EXPANDED_BRIDGE.md),
[plan](expanded_bridge_plan.json), [detached job](expanded_bridge.py),
[capture gates](expanded_bridge_check.py), [tests](test_expanded_bridge.py).

All **125 focused tests pass in 17.67 s**, with actual pilot overlap checks and
explicitly synthetic finer-step/F-R fixtures. The 72-run native panel uses both
constant sets, all three refined timesteps, the same passive/blocked cases and
three profile/no-op variants, each with observed/unobserved partners. Reuse the
unchanged D075 row runner and observer; do not call or amend its narrow plan.
No Cells integration or production changes are included.

Prepare/freeze once, then launch once into the fresh destination:

```bash
.venv/bin/python -B validation/betse/expanded_bridge_context.py prelaunch --tests reports/ref-003e0-expanded-checks-01.xml --expected-tests 125
.venv/bin/python -B validation/betse/expanded_bridge.py launch runs/ref-003e0-expanded-2026-09-12/capture-01
```

Prospective limits are 600 s worker / 660 s total, CPUs 0–3, 2 GiB panel and
64 MiB per worker file. Pilot-based estimates and disk checks precede registration.
Capture must account for all 3360 observed steps, 1120 enabled-target dispatches,
36 observer pairs, 24 variant comparisons and 12 exact D075 overlaps. Record
ordinary/final/event/lifecycle evidence and preserve partial artifacts on error.

The launch returns detached with durable logs and capture/failure receipts.
No polling or automatic retries. A passing capture is explicitly unqualified
pending a separately user-requested independent saved-data audit and focused
regression. No nonzero intervention, biology, restart or GPU claim is added.

The user-polled D077 capture now passes all 72 runs / 3360 observed steps in
203.562 s, with no Python warnings and all observer/variant/pilot controls exact.
Its 802 files remain frozen; no result is inferred from the prelaunch handoff.

## REF-003e0: independent expanded audit (D078)

[Contract](../../docs/BETSE_EXPANDED_AUDIT.md),
[handoff](../../reports/REF003E0_EXPANDED_AUDIT_HANDOFF.md),
[offline audit](expanded_audit.py), [detached job](expanded_audit_job.py),
[context](expanded_audit_context.py), [actual-evidence tests](test_saved_expanded.py).

After focused preflight and source/preservation freeze, the separate job runs
1,232,616 independent arithmetic comparisons and focused regression over the
five D075–D078 modules. It checks actual saved event/state/control links and
source/runtime evidence without importing either model or NumPy/JAX into the
audit process. It never reruns either simulator or loads a native pickle.

All **143 new preflight tests pass in 48.73 s**; the first test-only fixture
error receipt is retained. The combined job has **433 tests**, 180 seconds per
stage / 420 seconds total, CPUs 0–3 and 64 MiB of new output. All 345 Python
files pass quality checks. The prelaunch receipt binds these checks, source
hashes and prospective resource estimates. Launch once into a fresh directory:

```bash
.venv/bin/python -B validation/betse/expanded_audit_job.py launch runs/ref-003e0-expanded-audit-2026-09-12/audit-01
```

The command returns detached, with durable audit/regression logs and a joint
completion or failure receipt. Only joint success qualifies the expanded no-op
bridge. Keep the historical capture and all previous evidence unchanged. The
user requests status; no polling, retry, full production matrix or automatic
nonzero-response experiment follows.

The user-polled D078 [joint closeout](../../runs/ref-003e0-expanded-audit-2026-09-12/audit-01/completion.json)
now passes 1,232,616 comparisons and 433 tests in 167.679 s. It qualifies the
expanded zero-amplitude bridge. Keep the historical handoff and standalone
pending-regression audit receipt unchanged; no simulator was rerun.

## REF-003e1: prescribed held-input design (D079)

[Contract](../../docs/BETSE_HELD_INTERVENTION.md),
[plan](held_intervention_plan.json), [compiler/control probes](held_intervention.py),
[evidence context](held_intervention_context.py), [tests](test_held_intervention.py),
[report](../../reports/REF003E1_CONTROL_DESIGN.md).

This is not a capture registration. It compiles declared suppression/recovery
inputs to the existing Cells format, checks source-order additive diffusion
against multiplicative controls using the actual pinned pulse, and probes
36 actual Cells event grids and boundary-side controls without integration.
It does not call the native event handler or validate nonzero target dispatch.
The next preflight must check that separately before an eight-native / 24-Cells
matched-constant, 25 µs hold pilot. No production changes or long jobs.

Run only the bounded control/design tests:

```bash
taskset -c 0-3 .venv/bin/python -B -m pytest -q -W error validation/betse/test_held_intervention.py
```

The first source-mutation fixture failed on whitespace, with 79 other tests
passing; its JUnit receipt is retained. The source checker and both actual
control probes passed that attempt. No physical equation or input law changed.
All **80 corrected focused tests pass in 14.14 s**, with 348 Python files
passing lint/format checks. The final design receipt binds these checks, source hashes,
whole-tree quality, 932-file preservation baseline, 802 capture files and
11 expanded-audit files. All 352 accepted files / 51 production modules remain
unchanged. No older full suite or production matrix is rerun.

## REF-003e1: actual nonzero event preflight (D080)

[Contract](../../docs/BETSE_NONZERO_DISPATCH_PREFLIGHT.md),
[plan/context](dispatch_preflight_context.py), [input plan](dispatch_preflight_plan.json),
[native runner](dispatch_preflight.py), [control-aware checker](dispatch_preflight_check.py),
[tests](test_dispatch_preflight.py), [result](../../reports/REF003E1_DISPATCH_PREFLIGHT.md).

The native attempt passes **four preparations / 160 direct event calls in
24.463 s**, with 80 enabled targeted dispatches, 40 nonzero-amplitude dispatches,
57,600 checked diffusion values and no Python warnings. Actual target/modifier
metadata and physical-state invariance pass. Baseline/zero-amplitude records
agree exactly. The 201-file packet includes each completed dispatch plus its
aggregate trace, 80 frozen adapter sources and 332 installed-native source hashes.

All **75 focused tests pass in 8.48 s**, before native registration; all 352
Python files pass quality checks. The earlier 74-test pass is retained. The
prepared-state gate was moved before dispatch and an interrupted-dispatch
persistence test was added before source freeze. No failed native attempt or
automatic retry occurred. All 352 accepted files / 51 production modules and
previous evidence remain unchanged.

For focused software checks only:

```bash
taskset -c 0-3 .venv/bin/python -B -m pytest -q -W error validation/betse/test_dispatch_preflight.py
```

The preparation entry point refuses existing attempt directories and registers
source/test/plan hashes before native work. Worker/attempt limits are 45/60 s,
with 64 MiB overall, 16 MiB per worker file and CPUs 0–3. It cannot enter native
transport/integration; passing dispatch does not qualify a response, biological
recovery, full-loop noninterference, restart or GPU execution. Next implement
and register the 8+24 response pilot under its own prospective resource bounds;
D081 below now supplies that separately approved implementation.

## REF-003e1: first fixed-input response pilot (D081)

[Contract](../../docs/BETSE_HELD_RESPONSE_PILOT.md),
[handoff](../../reports/REF003E1_RESPONSE_PILOT.md),
[plan](held_response_plan.json), [context](held_response_context.py),
[native capture](held_response_native.py), [Cells checks](held_response_cells_check.py),
[comparison](held_response_check.py), [detached job](held_response_job.py).

The eight-native / 24-Cells pilot keeps matched constants, 1 ms and the D079
prescribed 25 µs hold. Four conditions have native observer partners and Cells
eager/JIT subdivisions 1/2/4. New checks handle time-varying permeability and
observation-side semantics without changing production or frozen old checkers.
Initial/disabled/padding/zero-amplitude/noninterference controls, per-interval
flux laws, inventory/charge and interval/cumulative transfers are all explicit.
Cells' final held RHS is checked internally; no native final RHS is invented.

For focused software checks only (saved data and clearly synthetic fixtures,
not simulator integration):

```bash
taskset -c 0-3 .venv/bin/python -B -m pytest -q -W error validation/betse/test_held_response.py validation/betse/test_held_response_check.py
```

The independently bound prelaunch receipt and 88-source capsule precede capture.
All **122 focused tests pass in 21.41 s**; 359 Python files pass quality checks.
Two earlier software receipts retain corrected test count / synthetic-fixture
aliasing failures, without any equation, input-law or tolerance amendment.
The job has separate native / Cells / model-free comparison processes with
180/2100/180 s stage caps and a 2520 s total cap; CPUs 0–3, CPU float64, 512 MiB
artifacts and 64 MiB per worker file. Completed rows, logs and failures are
durable. Python-level native failures retain partial observer state; hard kills
cannot export unwritten state. Source/runtime and original tolerances stay fixed.

The 25 µs native baseline is already known to miss some shared-bath criteria.
The pilot must preserve such failures, even if all control/refinement checks
pass. A failed comparison writes `comparison.json` and `failure.json`, not a
passing capture receipt. No automatic retry or broader step/hold ladder occurs.
Launch detached and return control: the user requests status. Follow-up audit /
regression waits for instruction, and even a passing capture alone does not
qualify native/forcing convergence, biological recovery or GPU execution.

## REF-003e1: offline rejection audit and reporting correction (D082)

D081 completed all eight native / 24 Cells runs in 715.769 s, then rejected
150 of 345,576 comparisons. The original 150-file packet and flat 88-file
adapter inventory remain frozen. The new nested
[auditor](response_audit/response_audit.py), [context](response_audit/response_audit_context.py),
[job](response_audit/response_audit_job.py) and [tests](response_audit/test_saved_response.py)
are a separate audit layer, not a simulator or a replacement captured checker.
See the [contract](../../docs/BETSE_HELD_RESPONSE_AUDIT.md) and
[handoff](../../reports/REF003E1_RESPONSE_AUDIT_HANDOFF.md).

All 70 new focused tests pass in 12.01 s. They use saved data and synthetic
corruptions only. The detached audit replays all original checks with frozen
helpers, independently rebuilds the 147,312 surface comparisons, keeps all
150 failures, and writes a separate corrected report. The correction removes
only the incorrectly aliased internal-law failure list; rejection stays intact.
Neither simulator, NumPy nor JAX is imported by the numerical auditor.

The user independently added `reports/ref-*.xml` to `.gitignore`. Exact old/new
hashes and bytes are recorded; the 969-file new preservation inventory retains
the now-ignored old XML evidence. The original 122 tests ran without changing
assertions or skipping tests: 121 passes / one historical preservation-guard
failure, explicitly a non-green legacy receipt. All 70 new tests pass separately.

The prospective prelaunch receipt binds four new source files plus old 88 inputs
into a 92-file audit capsule. The detached job has audit/legacy/new regression
stage caps of 90/90/120 s, 360 s total, CPUs 0–3, 16 MiB artifacts and 8 MiB
worker-file limits. It never runs a native/Cells capture worker or retries a
failed stage. Actual launch/time/PID and completion/failure receipts live under
`runs/ref-003e1-response-audit-2026-09-13/audit-01`; the handoff is not a result.
Return control after launch and wait for user-requested status. A successful
closeout verifies the rejection, not physical qualification. The actual
[joint closeout](../../runs/ref-003e1-response-audit-2026-09-13/audit-01/completion.json)
now completes in 50.390 s, with the original 345,576 comparisons reproduced,
all 147,312 surfaces independently rebuilt and all 150 failures retained.
The [refinement plan](../../docs/BETSE_HELD_RESPONSE_REFINEMENT.md) separates
native integration from input sampling; D083 below starts its first bounded step.

## REF-003e1: finer-input preparation/dispatch preflight (D083)

[Contract](../../docs/BETSE_REFINED_DISPATCH_PREFLIGHT.md),
[handoff](../../reports/REF003E1_REFINED_DISPATCH_HANDOFF.md),
[plan/context](response_refinement/refined_dispatch_context.py),
[checker](response_refinement/refined_dispatch_check.py),
[native worker](response_refinement/refined_dispatch_native.py),
[detached job](response_refinement/refined_dispatch_job.py),
[tests](response_refinement/test_refined_dispatch.py).

Eight fresh SIM preparations use the two finer holds (12.5/6.25 µs), matched
constants and all four controls. All 960 direct events / 345,600 diffusion
values are prescribed before native execution. No transport or integration
is allowed. Reuse the old observer/fence and durable event writer unchanged;
separate new mapping and variable-length checks preserve the 25 µs contract
and the original baseline-scaled 2e-14 control criterion.

All 109 focused software tests pass in 36.21 s. They use saved initial states
and fabricated events/receipt data; synthetic checks do not qualify native
execution. The new 979-file preservation baseline keeps all 150 response files,
16 audit files, 352 accepted files / 51 production modules and previously
recorded `.gitignore` amendment intact. Five new Python modules and one plan
make a 98-input capsule with the old 88 inputs / four audit modules. No old
source or regression assertion is changed, and no old full suite is rerun.

The prelaunch receipt binds software evidence and prospective 300-second worker /
360-second total, CPU 0–3, 256 MiB aggregate / 32 MiB worker-file limits. Intended
output is `runs/ref-003e1-refined-dispatch-2026-09-13/preflight-01`, with actual
launch PID/time recorded separately. Run detached and return for user status;
there is no automatic retry, response capture or independent audit. A successful
native result is only an initial-state input-application gate, not response,
native/forcing convergence, biological, restart, organ or GPU qualification.

The actual D083 preflight now passes in **116.002 s**, with 960 dispatches /
345,600 diffusion checks, maximum baseline-scaled error 2.671e-15 and no
warnings or integration. All 1042 files remain intact.

## REF-003e1: finer held-response panels (D084)

[Contract](../../docs/BETSE_REFINED_RESPONSE_PANEL.md),
[handoff](../../reports/REF003E1_REFINED_RESPONSE_HANDOFF.md),
[plan/context](response_panel/refined_response_context.py),
[native capture](response_panel/refined_response_native.py),
[Cells arithmetic](response_panel/refined_response_cells_check.py),
[comparison](response_panel/refined_response_check.py),
[detached job](response_panel/refined_response_job.py).

New capture scope is 16 native / 48 Cells runs at 12.5/6.25 µs, all four
conditions, matched constants, fresh native observer pairs and Cells eager/JIT
1/2/4 fixed-input subdivisions. Reuse D081's 25 µs packet explicitly.
The old 150 failures stay rejected. Require internal/solver/backend checks at
all holds and finest-held cross-engine agreement; report coarse/intermediate
and across-hold failures separately, without tolerance changes or convergence
claims. Inspect all N+1 state/ledger boundaries and N native fresh-rate starts;
do not invent a native terminal RHS.

The first software run records 96 passes / four failures in 60.79 s. Corrected
checker/count/test-exception issues pass all 24 targeted checks in 31.84 s;
all 375 Python files pass lint/format. The final 114-test suite now passes
without failures/errors/skips in 64.15 s pytest / 95.688 s total. Its separate
five-minute software registration freezes source and prior receipts; all payload
hashes and its 106-input capsule verify. Actual receipts are under
`runs/ref-003e1-response-refined-preflight-2026-09-13/checks-01`.
No simulation was launched by that job, and the completion was user-reviewed.

Response prelaunch was frozen against that exact `regression.xml`, and the
separately approved capture launched under the 3 h 15 min, CPU 0–3, 1 GiB /
64 MiB file budget. It stopped after 1830.727 s at the configured 16 MiB trace
guard, with all 16 native / 26 Cells runs completed and no integration of the
27th Cells row. The failed attempt under
`runs/ref-003e1-response-refined-2026-09-13/capture-01` stays frozen. D085 below
provides the separately authorized resource-only continuation; no automatic retry.

The nested seven-module/one-plan extension makes a 106-input capsule while the
old flat 88 sources, audit/dispatch modules, production and numerical criteria
stay unchanged. Preserve all 990 baseline / 150 response / 16 audit / 1042
dispatch files and the recorded ignore-rule amendment. These adapter changes
do not qualify BETSE parity, biology, organs, native/forcing convergence or GPU.

## REF-003e1: trace-budget continuation (D085)

[Contract](../../docs/BETSE_TRACE_BUDGET_CONTINUATION.md),
[handoff](../../reports/REF003E1_TRACE_RESUME_HANDOFF.md),
[scope/context](response_resume/trace_resume_context.py),
[production resource probe](response_resume/trace_resume_probe.py),
[reuse/comparison](response_resume/trace_resume_check.py),
[detached job](response_resume/trace_resume_job.py).

Raise only the eight previously unexecuted 640-step definitions to 64 MiB
`max_trace_bytes`. The largest production reservation is 24.6415 MiB; this
does not measure total process RAM. The other 40 definitions retain 16 MiB,
so all reused results match their original definitions exactly. Model, grid,
controls, criteria, old adapters and accepted production stay unchanged.

All 48 actual production timeline/resource probes pass without integration;
eight original-cap failures are reproduced. Reused 16 native / 26 Cells rows
pass 666,108 internal checks with no failures. Read their original files and
do not fabricate the missing old aggregate Cells worker receipt. All 241
failed-attempt files and the 1013-file baseline are preserved; only the seven
established status documents may change. Five new modules plus one plan form
a 112-input capsule; the original flat 88 sources remain frozen.

All 47 focused tests pass in 22.88 s; all 380 Python files pass lint/format.
D084's prior 114-test software receipt stays frozen, not rerun. Freeze the
new prelaunch against the resource/reuse/test receipts, then launch only
22 remaining Cells rows / 8480 steps and the unchanged full comparison.
The Cells worker repeats all 48 resource checks before its first rollout.
Reuse the old coarse panel and retain all 150 rejections; the full comparison
still contains 2,494,936 checks, including 2,298,936 required checks.

Fresh destination: `runs/ref-003e1-trace-resume-2026-09-13/capture-01`.
CPU 0–3, float64, single-thread libraries; 6600/300-second Cells/comparison
stages, two-hour total, 1 GiB combined retained-plus-new artifacts and 64 MiB
OS-enforced individual worker files. Only actual launch/capture/failure receipts
establish state. Return without polling, retry, expansion or follow-up audit.
No new trajectory, native/forcing convergence, biology, restart, organ or GPU
qualification follows from this resource-only amendment.

The user-reviewed D085 capture now finishes in **2239.322 s**, completing all
22 remaining Cells runs. All **2,298,936 required checks pass**, maximum
normalized error 0.5592883878208624. The 2,494,936 total includes 4173 diagnostic
failures: 150 coarse, 40 intermediate and 3983 across-hold. All 56 continuation
and 241 resource-failure files remain intact. D086 below implements the now
separately requested independent closeout; nothing was launched automatically.

## REF-003e1: independent finer-response closeout (D086)

[Contract](../../docs/BETSE_REFINED_RESPONSE_AUDIT.md),
[handoff](../../reports/REF003E1_REFINED_AUDIT_HANDOFF.md),
[context](response_closeout/refined_audit_context.py),
[independent surfaces](response_closeout/refined_audit_surfaces.py),
[saved-data audit](response_closeout/refined_audit.py),
[detached job](response_closeout/refined_audit_job.py).

Authenticate exact packet/source coverage and split old/new provenance, then
replay all 2,494,936 frozen checks. Independently rebuild 1,121,904 surface
comparisons / 132 scopes with separate full-grid loops and D082's saved-array/
`fsum` route. Preserve 1,373,032 replayed internal checks and all 4173 diagnostic
failures. Full ledger, per-scope counts and first-100 summaries must agree.
No original physical threshold, input, model, source or evidence changes.

First software receipt: 94 passes / one wrong test-exception expectation in
25.53 s, preserved. The import guard itself worked and remains unchanged.
All 105 new tests now pass in 28.38 s; all 385 Python files pass lint/format.
The 118-input capsule preserves D085's 112 and the original flat 88 inputs.
The 1027-file baseline allows only seven established status-document edits;
all 352 accepted files / 51 production modules and earlier evidence stay frozen.

Launch the independent audit and exact 336-test focused regression detached,
without rerunning either simulator: CPU 0–3, 300/300-second stages, 15-minute
total, 64 MiB new artifacts and 16 MiB worker files. Preserve the old expected
metadata-guard failure as its historical result, not a passing regression.
Fresh destination: `runs/ref-003e1-refined-response-audit-2026-09-13/audit-01`.
Only actual launch/completion/failure receipts establish state. No polling,
retry, refinement expansion, simulation or subsequent job.

A passing joint result qualifies only the explicitly scoped finest-held
seven-cell response. Across-hold failures remain limitations, not isolated
native or forcing convergence. No biological, GPU, organ or general BETSE
parity claim follows from software preflight or this bounded closeout.

The user-reviewed [actual joint completion](../../runs/ref-003e1-refined-response-audit-2026-09-13/audit-01/completion.json)
now passes in **249.644 s**, with **336/336 tests**, **2,298,936 required checks**,
zero failures, and **1,121,904 independent surface comparisons**. Only the
specified seven-cell, 1 ms, matched-constant, finest-held 6.25 µs CPU response
is qualified. All 4173 diagnostic failures and historical artifacts remain
unchanged. No simulator was rerun; native/forcing convergence stays unqualified.

## REF-004a: isolated active-channel contact (D087)

[Design and limits](../../docs/BETSE_VOLTAGE_GATE_CONTACT.md),
[data protocol](voltage_gate_contact/protocol.json),
[model-free reference/checker](voltage_gate_contact/gate_reference.py),
[isolated workers](voltage_gate_contact/gate_workers.py),
[detached job](voltage_gate_contact/gate_job.py),
[short synthetic preflight](voltage_gate_contact/test_gate_contact.py).

Run the existing Kv1.5 kinetic law/shared RK4 and intact native `Kv1p5` updater
on six prescribed-voltage protocols with fast/slow state and three timesteps.
No cells geometry, ionic transport, native world, voltage clamp or new temperature
law is claimed. Native equilibrium preparation, explicit m/h fixture states,
different discrete updates and the 298.15 K engineering regime are recorded.
Both full histories are inspected; full Cells trajectories here are compiled
JAX, while rate/one-step probes also cover NumPy/eager execution.

All 63 preflight tests pass in 1.11 s using synthetic records and read-only
preservation checks, not new native evidence. Earlier 41/62-pass receipts are
retained. Initial native P is explicitly derived from m*h; no redundant zero-
time trajectory update is inserted. The [handoff](../../reports/REF004A_KV1P5_HANDOFF.md) precedes one
capture to `runs/ref-004a-kv1p5-2026-09-13/capture-01`, with frozen source/protocol,
60/90-second workers, 180-second total and 64 MiB artifacts. CPU 0–3; float64;
no polling, retry or automatic audit. Actual launch/completion/failure receipts
establish execution state. Production and all old evidence remain unchanged.

## REF-004a: independent isolated-channel closeout (D088)

[Result](../../reports/REF004A_KV1P5_CLOSEOUT.md),
[audit contract](../../docs/BETSE_VOLTAGE_GATE_CLOSEOUT.md),
[source/receipt audit](voltage_gate_audit/gate_audit.py),
[independent arithmetic](voltage_gate_audit/gate_independent.py),
[actual-packet tests](voltage_gate_audit/test_gate_audit.py).

The user-reviewed capture passed all 11,266 comparisons in 11.971 s. The new
actual closeout now passes in **0.979 s**, replaying and independently rebuilding
all rows, without importing or rerunning either model. All **102 focused tests
pass in 2.58 s**: 63 original and 39 new; 392 Python files pass lint/format.
All 13 capture files and prior source/evidence remain intact. The original
pending-audit receipt is not rewritten. Only isolated gating is qualified;
the 36 measured and 12 roundoff-limited diagnostics remain distinct.

Next: the [coupled-channel configuration/transport preflight](../../docs/BETSE_COUPLED_CHANNEL_PLAN.md).
Native face-target mapping, effective channel diffusion, direct concentration
updates and separate current bookkeeping require explicit checks before a
full dynamic comparison. No follow-up job was launched at that closeout; D089
below is the separately requested next implementation.

## REF-004b: native channel setup and single transfer (D089)

[Contract](../../docs/BETSE_CHANNEL_TRANSPORT_PREFLIGHT.md),
[handoff](../../reports/REF004B_TRANSPORT_PREFLIGHT_HANDOFF.md),
[protocol](channel_transport_preflight/protocol.json),
[separated workers](channel_transport_preflight/transport_workers.py),
[model-free checker](channel_transport_preflight/transport_check.py),
[detached job](channel_transport_preflight/transport_job.py).

Four real native preparations, three fresh states each: network off, empty
network, zero-permeability Kv1p5 and active Kv1p5. Seven cells / thirty faces,
298.15 K, matched constants, 25 microseconds, no background leak, pumps, junction
transport or auxiliary chemistry. Actual face gates and channel/current export
must agree with independent references and finite-bath ownership. Native init
P remains absent; its separately derived initial product is explicitly labelled.

Cells evaluates unchanged finite-bath readouts/RHS using the actual post-native
gates and pre-transfer amounts/voltage. It applies one prescribed amount/ledger
increment, not an RK4 step or full trajectory. NumPy/eager/JIT are independently
executed only by the actual capture worker; the software fixture's backend
copies are explicitly synthetic.

All **76 focused software tests pass in 2.03 s**, no failures/errors/skips.
Earlier 71/76-pass receipts are retained. Repository lint/format checks pass;
352 accepted files / 51 production modules, isolated source/capture/audit and
older frozen files remain unchanged. Register a 63-input capsule and 393-file
earlier source baseline before one detached attempt at
`runs/ref-004b-transport-2026-09-14/capture-01`.

CPU 0–3, float64, 120 seconds per worker / 300 seconds total, 128 MiB artifacts
and 32 MiB per file (not RAM). Actual launch/completion/failure receipts establish
execution status. No automatic polling, retry, audit or full-loop pilot. A raw
pass remains pending independent closeout and does not qualify biology or GPUs.

The D089 attempt subsequently stopped after 4.672 s at empty-network
initialization: its null biomolecule input violated BETSE's sequence annotation.
Three network-off cases completed; no channel-runner/Cells comparison ran.
The original source, 22-file failure packet and historical handoff stay frozen.

## REF-004b: configuration-only empty-sequence correction (D090)

[Contract](../../docs/BETSE_CHANNEL_SETUP_FIX.md),
[handoff](../../reports/REF004B_SETUP_FIX_HANDOFF.md),
[amendment](channel_transport_setup_fix/amendment.json),
[configuration/preservation](channel_transport_setup_fix/setup_context.py),
[versioned native worker](channel_transport_setup_fix/native_setup_fix.py),
[native YAML/type regression](channel_transport_setup_fix/native_config_contract.py),
[detached job](channel_transport_setup_fix/setup_job.py).

Change only `general network / biomolecules` from null to `[]`. The native
worker body is AST-identical to D089 except for its configuration-provider call;
reuse the frozen Cells worker, numerical checker and full numerical protocol.
Other optional-network lists retain their null/presence behavior. No native
monkeypatch, new physics, changed criterion or post hoc qualification.

All **107 focused tests pass in 7.00 s**: the original 76 and 31 new checks.
The **4.143-second native contract probe** loads eight real YAMLs and checks
the loaded values against the actual `tissue_init` annotation using BETSE's
type-checking library. Null is rejected; empty sequences are accepted. Its
11-file packet is durable, with all 332 installed native Python files matching
the pinned source and no warnings. This does not initialize a world/network
or execute transport; those remain tasks of the numerical capture.

Preserve all 22 prior failure files, 63 original capsule sources, 393 earlier
sources and historical reports. Register 70 source-capsule inputs, correction,
preservation receipt, focused-test XML and native contract packet before one
fresh attempt at `runs/ref-004b-setup-fix-2026-09-14/capture-01`.
All twelve cases are fresh executions, including the three previously completed
network-off controls. Same CPU 0–3, float64, 120 seconds per worker / 300 seconds
total and 128 MiB aggregate / 32 MiB per-file quotas, not RAM ceilings.
No automatic polling, retry, audit or dynamic pilot. Actual receipts establish
results; any pass still needs separately requested independent closeout.

D090's actual attempt completed all twelve native cases, then stopped after
7.084 s at the strict Cells runtime guard. The launcher set explicit-false where
the accepted runtime records absence. No Cells transfer or comparison ran.

## REF-004b: registered worker-environment correction (D091)

[Contract](../../docs/BETSE_CHANNEL_RUNTIME_FIX.md),
[handoff](../../reports/REF004B_RUNTIME_FIX_HANDOFF.md),
[amendment](channel_transport_runtime_fix/amendment.json),
[environment/preservation](channel_transport_runtime_fix/runtime_context.py),
[real-worker startup contract](channel_transport_runtime_fix/startup_contract.py),
[detached job](channel_transport_runtime_fix/runtime_job.py).

Apply the exact registered numerical environment before importing JAX. In this
runtime both `XLA_FLAGS` and `JAX_DISABLE_JIT` must be absent. Preserve all strict
runtime, enabled-JIT, CPU and float64 guards, not a semantic normalization of
their inputs. Frozen native and Cells workers and numerical checker are reused.

All **152 focused tests pass in 13.25 s** (107 original / 45 new). Five fresh
subprocesses enter the actual worker, passing in **4.589 s** total. Corrected
startup reaches the deliberately missing input read; explicit-false, empty-XLA,
disabled-JIT and wrong-package controls are rejected. Actual source/runtime,
affinity and exception evidence is retained in an 11-file packet. No transport,
integration or GPU work runs in these probes. Legacy native YAML/type checks
also rerun as part of the unchanged configuration tests.

Preserve all 51 D090 failed-packet files, 70 old source inputs and the earlier
22-file failure. Bind a 76-input capsule, both amendments/preservations, original
native contract, focused XML and actual startup packet before a fresh capture.

```sh
.venv/bin/python -B validation/betse/channel_transport_runtime_fix/runtime_job.py launch \
  runs/ref-004b-runtime-fix-2026-09-14/capture-01 \
  --preflight reports/ref-004b-runtime-fix-checks-01.xml \
  --startup reports/ref-004b-worker-startup-contract-01
```

This command is single-use: registration refuses an existing output directory.
Same twelve native cases and twelve matched transfers per CPU backend, all
fresh numerical executions; same 300-second / 128 MiB limits and unchanged
protocol. Actual receipts establish status. No polling, automatic retry, audit
or trajectory expansion. No new biological or GPU qualification.

D091's user-reviewed capture now passes all **37,068 comparisons in 21.272 s**,
without warnings. All twelve native cases and twelve matched Cells transfers
per NumPy/eager/JIT backend completed. Its 54-file packet stays unchanged with
the original `capture_pass_pending_audit` status.

## REF-004b: independent saved-transfer audit (D092)

[Contract](../../docs/BETSE_CHANNEL_TRANSPORT_CLOSEOUT.md),
[handoff](../../reports/REF004B_TRANSPORT_AUDIT_HANDOFF.md),
[plan](channel_transport_audit/plan.json),
[provenance/partial records](channel_transport_audit/transport_audit_context.py),
[independent arithmetic](channel_transport_audit/transport_independent.py),
[detached audit](channel_transport_audit/transport_audit_job.py),
[conditional next pilot](../../docs/BETSE_CHANNEL_DYNAMIC_PILOT.md).

Replay the frozen comparison exactly and independently rebuild every one of
its 37,068 numerical rows with 80-digit arithmetic from raw data. Check each
stored actual/expected value, unchanged tolerance, owner mapping, ion balance,
gate/current/charge relation and hidden-state control. Check all partial native
records and separately saved Cells definitions against aggregate output.

All **220 focused tests pass in 33.27 s**, including the original 152 and 68
new audit checks. Earlier 59-pass/seven-error and 67-pass/one-failure receipts
remain: an audit-only null-channel assumption and test rejection expectation
were corrected, not the captured experiment. The actual audit process forbids
all model imports; numerical capture and prior audits are not rerun.

```sh
.venv/bin/python -B validation/betse/channel_transport_audit/transport_audit_job.py launch \
  runs/ref-004b-transport-audit-2026-09-14/audit-01 \
  --tests reports/ref-004b-transport-audit-checks-03.xml
```

Single-use fresh output only. Register 83 source inputs, all 54 capture-file
digests, original anchors, passing software XML and historical handoffs before
detached execution. CPU 0–3, 120 seconds, 64 MiB aggregate / 32 MiB per file.
The later user-requested status check confirmed actual independent closeout in
**3.215 s**, all **37,068 comparisons** reconstructed, zero failures, twelve
definition contracts and two hidden-state controls. Only the bounded transfer
contact is qualified. Original capture/audit receipts remain unchanged; no
simulator rerun, polling, retry or automatic pilot followed.

## REF-004b: full-loop preparation and feedback-pilot readiness (D093)

See [preparation protocol](../../docs/BETSE_CHANNEL_LOOP_PREPARATION.md) and
[feedback design](../../docs/BETSE_CHANNEL_FEEDBACK_DESIGN.md). The new nested
`channel_loop_preparation/` adapter keeps the original flat source inventory and
all accepted production unchanged. Eight real native INIT runs, four controls
with observer-on/off counterparts, each execute eight 25 µs updates. An explicit
initial-condition callback sets m/h once after actual initialization, identically
in both modes. The separate observer records channel/gate/transfer/current/voltage
boundaries without changing model state. Null initial P and distinct native label
versus elapsed-time clocks remain explicit.

After native checks pass, twelve candidate Cells definitions use the existing
parser, initial-state checks, RHS, timeline and resource estimator; no integration
is performed. A model-free 80-digit vector field checks continuous initial
coupling. The future dynamic panel still needs independent-reference integration,
registered convergence criteria and a separate capture/audit.

```sh
.venv/bin/python -B validation/betse/channel_loop_preparation/loop_job.py launch \
  runs/ref-004b-loop-preparation-2026-09-14/capture-01 \
  --tests reports/ref-004b-loop-preparation-checks-03.xml
```

Fresh output only; consult actual receipts before any execution. Bind the D092
closeout, frozen capture and source inputs, dependency/runtime identities and
software XML. CPU 0–3, float64, 240 s overall, 128 MiB aggregate artifacts,
32 MiB per file. Detached, no automatic polling, retry, audit or dynamic pilot.
Readiness is not trajectory convergence, biological realism or GPU qualification.

All **96 focused tests pass in 18.70 s**, including complete software execution
of the Cells readiness worker against explicitly fabricated native input. Earlier
83/95-pass receipts remain. The [handoff](../../reports/REF004B_LOOP_PREPARATION_HANDOFF.md)
records the 94-source capsule, passing XML and unchanged prerequisites. The
actual preparation now passes in **18.031 s**, without warnings: **73,744 native
boundary + 348 Cells initial-rate comparisons**, zero failures, four matched
observer pairs and twelve ready candidate definitions. No Cells trajectory ran.
Its original 74-file packet retains the pending-audit completion.

## REF-004b: independent preparation/readiness audit (D094)

The nested `channel_loop_audit/` implements a [separate saved-data closeout](../../docs/BETSE_CHANNEL_LOOP_CLOSEOUT.md),
with frozen replay and independent reconstruction of **all 74,092 rows**.
It also checks 204 float64 array records, 36 direct charge snapshots, four
observer pairs and twelve complete definition/state/RHS/grid-resource contracts.
Original evidence, production and flat adapter inventory remain unchanged.

All **176 focused tests pass in 25.21 s** (96 original / 80 new), including
saved-data reconstruction and corruption checks. The first software receipt
retains 162 passes and eight test-exception-type mismatches; the rejection guards
were already operating correctly. The [handoff](../../reports/REF004B_LOOP_AUDIT_HANDOFF.md)
records passing XML and the **101-input source capsule**. Software preflight
does not replace the separate registered audit receipt.

```sh
.venv/bin/python -B validation/betse/channel_loop_audit/loop_audit_job.py launch \
  runs/ref-004b-loop-audit-2026-09-14/audit-01 \
  --tests reports/ref-004b-loop-audit-checks-02.xml
```

The named directory is single-use: consult the handoff/launch receipt; never
relaunch an existing output. One detached audit, 120 seconds, 64 MiB aggregate /
32 MiB per-file artifacts, CPUs 0–3. No model imports, simulator or previous
numerical-audit rerun, polling, retry or automatic dynamic pilot. Only an actual
`loop_preparation_audit_closed` receipt qualifies this preparation/readiness;
coupled trajectory accuracy, restart replay, biology and GPU remain unqualified.

The actual D094 audit now **passes in 5.541 s**: all **74,092 comparisons**, zero
failures, 204 float64 records, 36 direct charge snapshots and twelve complete
readiness contracts. Its nine-file packet and 101 source inputs authenticate.

## REF-004b: reference-gated coupled feedback pilot (D095)

The nested `channel_feedback_pilot/` implements the [two requested stages](../../docs/BETSE_CHANNEL_FEEDBACK_PILOT.md)
as one registered capture: independent reference convergence first, then the
small native/Cells trajectory panel only if that gate passes. No automatic
follow-up audit is scheduled. Preserve all older source inputs and packets.

The fixed 2 ms panel uses 12 reference solves, 12 native observed/unobserved
pairs (24 runs / 4,480 updates), 12 compiled + four eager production JAX
trajectories, and four complete checkpoint/reload/resume checks. NumPy is not
mislabeled as a separate production trajectory runner. Both simulators evolve
their own full state; native post-gates are never injected into Cells.

Native snapshots and float64 byte records are losslessly gzip-encoded with a
bounded reader. Separate post-hoc native flux probes use copies of saved states;
step current is not treated as fresh current. Native accounting, reference
convergence, finest-grid accuracy, refinement, backend agreement and full-state
restart remain separate reported checks. Failed coarse accuracy rows are retained
as diagnostics; no criterion is changed after observing them.

One detached capture is bounded to 900 s / 512 MiB aggregate, 128 MiB per file
and per decompressed record, CPUs 0–3. No polling, retries, prior simulation
reruns, production changes, GPU execution or automatic follow-up. Source/test
bindings and the single-use launch are recorded in the
[handoff](../../reports/REF004B_FEEDBACK_PILOT_HANDOFF.md) before execution.
All 157 focused software tests pass in 50.23 s (96 original / 61 new); earlier
fixture-failure receipts remain intact. Capture success is still pending a
separate independent audit.

## REF-004b: independent coupled feedback closeout (D096)

The user-reviewed D095 capture passes in 338.424 s: all 5,181,760 native identities,
2,264 charge snapshots, reference convergence, required finest-grid comparisons,
refinement, four restart pairs and four eager/JIT pairs. Fourteen coarse native
diagnostic misses remain. Its original status stays `capture_pass_pending_audit`.

The new `channel_feedback_audit/` implements the [separate saved-data closeout](../../docs/BETSE_CHANNEL_FEEDBACK_CLOSEOUT.md).
It authenticates all 284 files / 112 capture source inputs and the complete
historical chain. Frozen replay uses guarded, redirected output sinks; independent
math checks every numerical identity. Native reconstruction is streamed one step
at a time. Numeric-only NPZ decoding checks all 24 Cells checkpoints without
NumPy or production imports. No reference or simulator integration is rerun.

The original tolerances, refinement floors and fourteen coarse diagnostic rows
remain unchanged. One detached audit is bounded to 900 s / 256 MiB aggregate /
128 MiB per file, CPUs 0–3, without polling, retries or automatic follow-up.
Its actual [passing receipt](../../runs/ref-004b-feedback-audit-2026-09-15/audit-01/completion.json)
now closes this fixed numerical pilot in **172.504 s**: **5,806,006 independent
comparisons**, zero mismatches, 24 checkpoints / 1,296 arrays and fourteen
unchanged coarse misses. Biology, broad BETSE parity, native restart, GPU and
multiscale accuracy remain separate; see the [closeout](../../reports/REF004B_FEEDBACK_CLOSEOUT.md).
All 122 audit-only tests pass in 11.18 s; the original 157-test pilot receipt
remains bound without rerunning integration. The
[handoff](../../reports/REF004B_FEEDBACK_AUDIT_HANDOFF.md) records software receipts,
the 122-input source capsule and the single-use detached launch procedure.

## REF-004c: equal-current, different-history preparation (D097)

The [new preparation](../../docs/BETSE_CHANNEL_HISTORY_PREFLIGHT.md) uses paired
m/h settings (0.2/0.6 and 0.6/0.2), with otherwise identical active or blocked
definitions from the audited physical fixture. It checks complete production
initial state/RHS on NumPy/eager/JIT, candidate grids/resources and six fresh
isolated native Kv1p5 updates. Independent mathematics checks equal current and
different opening slopes. No new Cells trajectory, native world/transport or
continuous reference integration runs; no checkpoint or biological claim.

Sources live in `channel_history_preflight/`. The fixed preparation is detached,
240 s total / 90 s per worker, 64 MiB aggregate / 32 MiB per file, CPUs 0–3.
Success remains `history_preflight_pass_pending_review`; later paired reference
and coupled trajectory qualification require separate work. Previous sources,
diagnostic failures and accepted production remain unchanged; no automatic
polling, retry, follow-up audit or GPU job.
All **49 focused software checks pass in 7.50 s**, including actual eager/JIT
initial rates with integration entry points forbidden. The
[handoff](../../reports/REF004C_HISTORY_PREFLIGHT_HANDOFF.md) records the retained
44-test first receipt, passing final receipt, 130-input capsule and detached
launch command. Software checks do not replace the actual native preparation
worker or a subsequent paired coupled-trajectory experiment.

## REF-004c: preparation closed and paired reference-gated pilot (D098–D099)

D097's actual preparation passes 2,442 comparisons in 14.036 s without warnings.
D098's [separate saved-data closeout](../../reports/REF004C_HISTORY_PREPARATION_CLOSEOUT.md)
now passes in 3.062 s: exact replay of every comparison, 1,404 alternate rate
checks and 528 layout-array hashes authenticated against audited full checkpoints.
All twelve review tests pass in 0.38 s. No simulator or reference integration
is rerun, and the original pending-review receipt stays unchanged.

D099's [paired-history contract](../../docs/BETSE_CHANNEL_HISTORY_PILOT.md) and
[handoff](../../reports/REF004C_PAIRED_HISTORY_HANDOFF.md) implement the user's
requested paired references followed by detached own-state capture. Sources are
in `channel_history_pilot/`; the two already executed D098 review sources there
remain frozen. New explicit a/b parameter views and validators use the existing
production interfaces without global patches or a simulator-code change.

Twelve actual reference solves must pass the unchanged convergence/domain checks
and a prospective integrated 2 ms signal gate before any native or Cells worker
starts. Hash-bound reference receipts are rechecked before both workers. The
conditional panel has 24 native runs / 4,480 updates, 16 complete Cells histories,
four midpoint resumes, 24 full checkpoints and signed a-minus-b contrasts.
Per-trajectory accuracy, refinement, accounting and restart criteria are unchanged;
contrast budgets explicitly propagate the contributing trajectory errors.

All **56 focused tests pass in 22.96 s**; the earlier 46-pass receipt remains.
Short synthetic references and two-step real eager/JIT/restart tests are software
evidence, not the full registered experiment. D098's four-file review, original
evidence and accepted production authenticate; the new capsule has **143 inputs**.

The single detached workflow is bounded to **1,200 seconds / 512 MiB aggregate /
128 MiB per file**, CPUs 0–3, with separate 240/360/480-second reference/native/
Cells worker limits. Return after launch; no assistant polling, automatic retry,
post-capture audit/regression or GPU work. Actual result/failure receipts establish
execution state. Even a pass remains `paired_capture_pass_pending_audit`, not
biological validation, broad BETSE parity or expanded trajectory qualification.

## REF-004c: paired capture pass and independent audit (D100)

The [D099 capture](../../reports/REF004C_PAIRED_HISTORY_CAPTURE.md) now passes in
391.917 s, with no warnings: twelve reference solves, 24 native / 16 Cells runs,
7,367,280 native identities and all required trajectory/refinement/restart and
contrast checks. Preserve 21 coarse misses (a: fourteen, b: seven), 24 complete
checkpoints / 1,296 arrays and the original pending-audit receipt.

The separately requested [D100 audit](../../docs/BETSE_CHANNEL_HISTORY_CLOSEOUT.md)
is in `channel_history_audit/`. It uses explicit per-history reconstruction,
independent numerical columns, signed paired responses, eight refinement
decisions and a raw checkpoint-byte route distinct from the capture's value
decoder. All old code and evidence remain unchanged; no simulator or numerical
library is imported, and no reference integrator is rerun.

Register a 152-input source capsule and passing software evidence before one
detached audit, CPUs 0–3, 900 seconds / 256 MiB aggregate / 128 MiB per file.
No polling, automatic retry, follow-up regression or GPU work. Software checks
and launch do not establish closeout; the actual completion must pass before
this fixed paired-history scope is qualified. No biological or organ-scale claim.

All **137 audit-only tests pass in 16.56 s**. The
[handoff](../../reports/REF004C_PAIRED_HISTORY_AUDIT_HANDOFF.md) records the retained
canonical-hash setup error, 128-pass second receipt and 55 s expanded-software
timeout. Full reference replay stays in the detached audit; quick software replay
uses explicitly bounded saved slices, without changing audit coverage or capture
criteria. The final software receipt is not the complete numerical audit result.

The actual [D100 closeout](../../reports/REF004C_PAIRED_HISTORY_CLOSEOUT.md) now
passes in **240.629 s**, with **8,036,300 independent comparisons**, zero
mismatches and all 21 coarse misses retained. All 24 complete checkpoints,
six contrasts/eight refinement groups and the original source/evidence chain
authenticate. This closes only the fixed paired-history numerical scope.

## REF-004d: suppression/release input design (D101)

The [design](../../docs/BETSE_CHANNEL_RELEASE_DESIGN.md) and
`channel_release_design/` add numeric schedules, pinned native source contracts,
and real Cells control/RHS probes without modifying production. The proposed
native input is absolute `maxDm = baseline * availability`, not a tissue event,
new molecular inhibitor or native gate rewrite. Actual input dispatch is not
executed or inferred from a source check.

All **107 focused tests pass in 11.88 s**, including 54 NumPy/eager/JIT probes
at six saved active states, complete independently reconstructed RHS, exact
blocked transport, continuing intrinsic gates, retained ledgers and all 24
candidate Cells grids. Those saved states are not release trajectories. No
integration, new checkpoint qualification or detached job runs in this design.
[Software result and exact command](../../reports/REF004D_RELEASE_DESIGN_CHECK.md).

Next: separately registered actual native input-application/single-update
preflight, then piecewise reference and dynamic response gates. No polling,
automatic expansion, biology or GPU promotion.

## REF-004d: actual native input preflight (D102)

The [contract](../../docs/BETSE_CHANNEL_RELEASE_PREFLIGHT.md) and
[handoff](../../reports/REF004D_RELEASE_PREFLIGHT_HANDOFF.md) cover
`channel_release_preflight/`. This is a separate validation adapter, not a
production or upstream patch. One active priming update creates nonzero native
state; input prefixes change only absolute `maxDm`, followed by one separately
checked update. No integration occurs between queries. Query times do not imply
elapsed simulation time or qualify a 2 ms release experiment.

All **71 focused software tests pass in 14.01 s**, including two actual native
cases / four phases / eight updates and exact observer partners. Full gate,
flux, transfer and charge equations, numeric-state preservation, preparation and
boundary artifacts, corruption guards and exception paths are checked. Earlier
development receipts remain; only unregistered new tooling was corrected.

The 165-input capsule binds the prior authenticated chain, explicit data,
supporting reports and final XML. One detached panel has six seeds, 144 fresh
phases, 288 single updates, 288 applications and 72 observer pairs. Limits:
CPUs 0–3, 480 seconds total / 360 seconds native worker / 256 MiB aggregate /
64 MiB per file. Return after launch without polling. Actual result/failure
artifacts, then separate review, establish its scoped status; no automatic
reference/response/audit or GPU work follows.

## REF-004d: saved native-input review after rounding rejection (D103)

D102's native worker completed its full panel in 36.066 s without warnings, but
the controller rejected exact bath identity after zero-flux averaging at 52.782 s.
All [failed capture evidence](../../reports/REF004D_RELEASE_PREFLIGHT_FAILURE.md)
is preserved. Do not modify the executed `channel_release_preflight/` sources.

The [D103 contract](../../docs/BETSE_CHANNEL_RELEASE_REVIEW.md) is implemented
separately in `channel_release_review/`. It reconstructs the pinned native
float64 mean exactly, including successive blocked/ordinary remixing, and
records signed roundoff within unchanged material budgets. No captured value
is corrected. All original input, physical, artifact and observer checks remain.

All **66 review tests pass in 10.66 s**, with 198 actual NumPy reduction probes,
eight saved rows, exact one-ULP rejection and original failure reproduction.
The first two fixture failures remain; `nextafter` makes those corruptions
representable. See the [handoff](../../reports/REF004D_RELEASE_REVIEW_HANDOFF.md).

Freeze 605 capture files and a 175-input capsule before one detached saved-data
review: CPUs 0–3, 180 seconds / 64 MiB aggregate / 32 MiB per file. Check the full
144-phase / 288-update / 72-pair panel and 1,776 zero-flux means. No simulator or
numerical-library imports, pickle loading, polling, retry or automatic follow-up.
The actual review receipt, not software success, establishes any fixed-scope
qualification; the original failure receipt remains unchanged.

The actual [D103 input closeout](../../reports/REF004D_RELEASE_INPUT_CLOSEOUT.md)
now passes **916,176 comparisons in 24.469 s**, all 1,776 source-order means and
72 observer pairs. All 104 original rejections remain. This qualifies native
input/two-single-update scope only, without simulator integration.

## REF-004d: independent piecewise release reference (D104)

The [reference contract](../../docs/BETSE_CHANNEL_RELEASE_REFERENCE.md) and
`channel_release_reference/` implement a reference-only next gate. Two histories,
four conditions and three solver settings give **24 paths / 48 integrations**.
Keep all 28 state coordinates continuous across block/release, gate evolution
active during block and one-sided fresh currents explicit. Unsplit baseline
versus split no-op controls segmentation. Check independent algebra, analytic
blocked gates, dense replay, conservation/thermodynamics and fixed signal budgets.

All **102 focused tests pass in 4.35 s**, including short one-cell software
integrations (not the registered seven-cell experiment), exact carry and state
corruption, prospective signal failures and detached success/failure/timeout
paths. The earlier 79-pass / 4.53 s receipt remains. See the
[handoff](../../reports/REF004D_RELEASE_REFERENCE_HANDOFF.md).

Launch one fresh reference-only job with `piecewise_job.py launch OUTPUT --tests
REPORT_XML`, using the Cells controller interpreter; the job selects the pinned
independent `.reference-venv` worker itself. CPUs 0–3, 900 s total / 480 s worker,
128 MiB per file / 256 MiB aggregate artifacts. It contains no native/Cells
trajectory command. Return immediately without polling, retry, automatic audit
or regression. Completion is `piecewise_reference_pass_pending_review`; saved
review and actual timed simulator comparison remain later user-directed work.

Launched detached 2026-09-15 23:19:29 UTC, PID 3018977, at
`runs/ref-004d-release-reference-2026-09-15/reference-01`. The launcher returned
without polling; consult actual completion/failure evidence on a later status request.

The actual [reference result](../../reports/REF004D_RELEASE_REFERENCE_CAPTURE.md)
now passes all **1,485,380 comparisons in 160.675 s**, with zero failures or worker
warnings. All 34 files / 182 inputs authenticate. Its original pending-review
receipt remains unchanged.

## REF-004d: reference-gated timed block/release comparison (D105)

The [contract](../../docs/BETSE_CHANNEL_TIMED_RELEASE.md) and `channel_release_pilot/`
first independently reconstruct the saved D104 numerical columns without a
simulator or reference integrator. Only a hash-linked review pass enables native
and Cells workers. Both are explicitly authorized parts of this single job;
there is no automatic post-capture audit or regression.

Retain the 2 ms window, histories a/b, four conditions and existing physical /
refinement budgets. Native input uses actual elapsed boundaries and an immutable
unsuppressed maximum; its numeric state and read-only observer remain separate.
Record both sides of each fresh current switch, full histories, conservation,
source-order bath remixing and pre-channel voltage-nonce operations. Cells keeps
complete state, gate evolution during block and release-boundary restart.

Full panel: **48 native phases / 8,960 updates / 96 input applications / 24
observer pairs**, **32 Cells trajectories / eight resumes**, **48 checkpoints /
2,592 arrays**, and 12 signed history-contrast groups. Coarse errors remain
diagnostics; finest-grid contact and refinement are required. This is not
biological validation, native restart or broad BETSE/GPU parity.

Software checks are intentionally split into bounded receipts; registration
requires passing, disjoint coverage including both real engine smoke tests.
All **121 tests pass**: 107 in 36.15 s and 14 in 29.33 s, in
`ref-004d-timed-release-checks-09.xml` and `ref-004d-timed-release-checks-10.xml`.
See the [handoff](../../reports/REF004D_TIMED_RELEASE_HANDOFF.md) for exact receipts
and retained development failures. Launch once with the Cells interpreter:

```text
.venv/bin/python -B validation/betse/channel_release_pilot/timed_job.py launch OUTPUT --tests REPORT_XML_1 REPORT_XML_2
```

Use a fresh directory under `runs/`. Resources: CPUs 0–3, 1,800 s total, 480 s
native / 600 s Cells, 128 MiB per file / 512 MiB aggregate artifacts. Return
immediately; no polling, retry or automatic follow-up. Completion remains
`timed_release_capture_pass_pending_audit`; immutable receipts establish actual
status, not this prospective description. Production implementation is unchanged.

Launched detached **2026-09-16 09:21:29 UTC**, PID **3100871**, at
`runs/ref-004d-timed-release-2026-09-16/capture-01`; registration SHA-256
`a82235aa0940c3c237d947104231ad24dfe0d02d05d55991858ca41690953352`.
The launcher returned successfully without completion/status polling. Frozen
sources and reports must remain unchanged while the job runs.

The subsequent user-requested status found a passing capture in **1,004.27 s**:
all 14,772,920 native comparisons and all required/refinement checks pass; 49
coarse misses remain. The 555-file packet and 194 source inputs authenticate.
See [capture result](../../reports/REF004D_TIMED_RELEASE_CAPTURE.md).

## REF-004d: independent saved timed-response audit (D106)

The [audit contract](../../docs/BETSE_CHANNEL_RELEASE_CLOSEOUT.md) and
`channel_release_audit/` implement the next separately authorized gate. Rebuild
both numeric columns of 15,042,946 identities / 182 groups using alternate
algebra and complete state/byte checks. Preserve 28,280 exact zero-flux means,
3,265 original identity diagnostics, all 49 coarse misses, 16 refinement groups
and 12 history contrasts. Check all 48 checkpoints / 2,592 arrays and both
switch-side complete RHS arrays, without rerunning either simulator.

The D105 reference review is already closed: authenticate it, then reconstruct
only the reference points/sides/floors used here, without repeating its full
1,485,380-identity review. The original capture and receipts remain unchanged.

All **116 software checks pass** in two bounded, disjoint batches (103 in
41.99 s; 13 in 43.13 s), with required coverage verified before registration.
See the [handoff](../../reports/REF004D_RELEASE_AUDIT_HANDOFF.md) for retained
earlier receipts and the foreground software timeout. The final receipts are
`ref-004d-release-audit-checks-04.xml` and `ref-004d-release-audit-checks-05.xml`.

```text
.venv/bin/python -B validation/betse/channel_release_audit/release_audit_job.py launch OUTPUT --tests REPORT_XML_1 REPORT_XML_2
```

Use one fresh `runs/` directory. Resources: CPUs 0–3, 1,800 s, 128 MiB/file and
256 MiB total disk artifacts; no RAM cap is implied. Return after launch, without
polling, retry or follow-up. Success is `timed_release_pilot_audit_closed` only
for the fixed numerical scope. Biology, native restart and GPU remain unqualified.

Launched detached **2026-09-16 10:18:14 UTC**, PID **3114261**, at
`runs/ref-004d-timed-release-audit-2026-09-16/audit-01`; registration SHA-256
`a786544e970a7056f0efd1e122ef39bf8eb174fb0373149f15cb7abe1dc592fb`.
The launcher returned successfully; no completion/status polling was performed.
New audit sources, contract and reports are immutable. The subsequently reviewed
[terminal closeout](../../reports/REF004D_TIMED_RELEASE_CLOSEOUT.md) now passes
in **387.772 s**, reconstructing **15,042,946 comparisons / 182 groups** with
zero column mismatches, and preserving all 49 coarse misses. No simulator rerun.

## REF-005a: Na/K pump kinetic contact (D107)

The [pump contract](../../docs/BETSE_PUMP_CONTACT.md) and `pump_contact/` compare
the actual pinned `pumpNaKATP` function with independent 80-digit thermodynamics
and a **validation-only** NumPy/eager-JAX/JIT-JAX array prototype. Production
still has its distinct synthetic reversible pump. Fixtures cover saturation,
voltage/temperature, area/capacity, blocking, stall and reversal. Source/matched
constants remain separate. The third native return is outward Na, not ATP
turnover; the accepted `met` argument is unused.

This is prescribed-state component contact, not a loaded native world, coupled
pump–leak trajectory, production mechanism or biological/GPU qualification.
The [handoff](../../reports/REF005A_PUMP_CONTACT_HANDOFF.md) records final software
checks and the exact candidate. Register all fixtures, budgets, source bytes,
software receipt, upstream/installed source and preserved production before work.

```text
.venv/bin/python -B validation/betse/pump_contact/pump_job.py launch OUTPUT --tests REPORT_XML
```

Use a fresh `runs/` directory. CPUs 0–3; 45 s per worker / 150 s controller;
8 MiB/file / 32 MiB disk artifacts, not a RAM limit. Native and prototype run
in separate pinned environments. Capture stores raw densities, all comparison
rows and durable success/failure receipts. A pass remains pending independent
saved-data review. Return after launch; no polling, automatic retry or follow-up.

The [junction plan](../../docs/BETSE_GAP_JUNCTION_PLAN.md) and
[biological-data plan](../../docs/BETSE_BIOLOGICAL_BENCHMARK_PLAN.md) advance the
other approved tracks without launching additional campaigns. The latter's
JSON is literature metadata, not a simulation definition. The overall target
is [at least BETSE-level realism](../../docs/BETSE_REALISM_AND_NEXT_STEPS.md), not
merely these component tests.

Launched detached **2026-09-16 11:07:21 UTC**, PID **3127417**, at
`runs/ref-005a-pump-contact-2026-09-16/capture-01`; registration SHA-256
`152b7ff43ff946450ef9c96f034d4a25ed09e2982ffa50a6ceaf451de0178fc4`.
The launcher returned successfully. No completion/status polling was performed;
the 11 bound source inputs and handoff are immutable. A passing full-panel
capture, independent audit and production kinetic mechanism are not yet claimed.

The later user-requested inspection found a **5.0625 s capture pass**, all 1,240
comparisons and no warnings. D108's separately authorized
[independent closeout](../../reports/REF005A_PUMP_CONTACT_CLOSEOUT.md) now passes
all 1,240 rebuilt columns / 248 raw triplets in 0.163 s, with 17 passing audit
checks. All original files/receipts stay unchanged; component scope is closed,
not production pump or native coupled-cell parity.

## SPEC-010 / NUM-011: coupled kinetic pump numerical candidate (D109)

The [integration contract](../../docs/KINETIC_PUMP_INTEGRATION.md) and new
`pump_coupled/` tooling define the numerical prerequisite for a named production
pump. The candidate composes the audited array kinetics with existing GHK and
checked RK4 primitives; production files remain unchanged. Independent scalar
mass-action/symmetric-leak equations run DOP853 and Radau in a separate process.

Six 10 ms cases cover pump-only, leak-only, pump–leak, all-blocked, pump
suppression/release and two heterogeneous cells sharing a finite bath. The full
panel is 12 adaptive reference trajectories, 24 NumPy/compiled-JAX trajectories
at 100/50 µs and 12 complete-state restart suffixes. Save all endpoints and
physical ledgers; neither a native BETSE full loop nor biological data is run.
The [handoff](../../reports/NUM011_KINETIC_PUMP_HANDOFF.md) records 37 passing short
checks and earlier retained software findings.

```text
.venv/bin/python -B validation/betse/pump_coupled/coupled_job.py launch OUTPUT --tests REPORT_XML
```

Use a fresh `runs/` directory. CPU 0–3; 240 s per worker / 600 s total;
16 MiB/file / 64 MiB aggregate artifacts. Register 14 source/contract/report
inputs, exact fixtures/budgets and software receipt, and authenticate the closed
pump contact and unchanged accepted implementation. Return after detached launch,
without polling, retry, automatic audit or regression. A passing capture stays
pending independent review and does not constitute production integration.

Launched detached **2026-09-16 12:14:01 UTC**, PID **3178097**, at
`runs/num-011-kinetic-pump-2026-09-16/candidate-01`; registration SHA-256
`127ddcba432198f05a5705687293054bfc7cdcbc3e34eec5720ce776c4aba9f2`.
The launcher returned successfully. No completion/status polling was performed;
the 14 source/contract/report inputs and final software receipt are immutable.
Full-panel success, numerical closeout and production pump support are not
claimed at launch.

The later user-requested inspection found **21.908 s / 4,070 comparisons passing**
with no warnings. D110's [independent coupled review](../../reports/NUM011_COUPLED_CLOSEOUT.md)
now closes 3,756 physical records, all comparisons/refinement records and all
12 restart links in 4.535 s without solver imports. All 20 short audit tests
pass. This closes only the six-case / 10 ms numerical prerequisite; all
refinement groups are roundoff-limited, not a convergence-order measurement.

## SPEC-010 production process qualification (D111)

`src/cells/processes/kinetic_pump.py` adds the named pure numeric law;
[32 process tests and 10 gate tests pass](../../reports/SPEC010_PROCESS_HANDOFF.md).
See the [process contract](../../docs/KINETIC_PUMP_PROCESS.md). The law is not yet
selectable through a simulation definition. All 352 previously accepted files
remain unchanged, but adding a module changes the whole-package source inventory
from 51 to 52. Old checkpoints retain their strict preserved-source identity.

`pump_process/` checks all 31 saved matched-constant probes against both the
independent oracle and native values on NumPy/eager/compiled JAX (930 comparisons),
then runs the five-file / 348-test targeted regression listed in its registration. No
native rerun, new coupled production trajectory or full release matrix is implied.

```text
.venv/bin/python -B validation/betse/pump_process/process_job.py launch OUTPUT --checks PROCESS_XML --gate-checks GATE_XML
```

One detached attempt: CPUs 0–3, 60 s contact / 600 s regression / 900 s total,
32 MiB/file / 128 MiB artifacts. Authenticate both closed prior scopes, freeze
old/new code and documents, retain durable results/failure, and return without
polling, retry or automatic review. Production host/layout/runner integration
follows separately after inspection of the saved result.

Launched detached **2026-09-16 12:55:00 UTC**, PID **3212517**, at
`runs/spec-010-pump-process-2026-09-16/qualification-01`; registration SHA-256
`ae42471c0e2b6dc0ac97c31fb18f70fc02cd8883eab38420da4b2f8fe0ba13e9`.
The launcher returned successfully. All 361 source/contract/report inputs and
both final software receipts are immutable. No completion/status polling was
performed; a full process qualification/regression pass is not claimed at launch.

## SPEC-010 versioned kinetic finite-bath family (D113)

The later user-requested review finds the D111 process job complete: **930
comparisons and 348 regression tests pass**. The
[review and preservation](../../reports/SPEC010_PROCESS_CLOSEOUT.md) authenticate
361 sources/payloads and archive 1,273 pre-edit working-context files. The original
receipts are unchanged. Old current-tree guards must still run in their own
preserved source contexts; this development extension does not waive them.

`finite_extracellular@2` is now implemented in **0.16.0.dev0**, with strict
kinetic/metabolism declarations, flat role/parameter arrays, ordinary-engine
composition and kinetic stage/interpolation guards. See the
[contract](../../docs/KINETIC_FINITE_BATH_MODEL.md) and
[handoff](../../reports/SPEC010_FAMILY_HANDOFF.md). Sixty focused checks plus
eight controller checks pass; full model acceptance remains pending.

```text
.venv/bin/python -B validation/betse/kinetic_family/family_job.py launch runs/spec-010-family-2026-09-16/acceptance-01
```

One detached job: 74 new-family tests (including 12 saved-reference trajectories,
restart/branch/fresh-process/window/batch/cohort evidence), then 348 targeted
existing-model tests. Retain full ordinary-runner artifacts, complete snapshots,
comparison records, source capsule, runtime, JUnit and terminal receipt/failure.
CPU 0–3, float64/JIT, 1,200 s family / 600 s regression / 1,860 s total;
64 MiB per file / 256 MiB artifacts, not RAM. No polling, retry or automatic audit.
Neither a native coupled BETSE capture nor a full historical release matrix is
run here. Stable 0.14.0 and accepted development 0.15.0.dev0 are not promoted.

Launched detached **2026-09-16 13:41:18 UTC**, PID **3224245**, at
`runs/spec-010-family-2026-09-16/acceptance-01`; registration SHA-256
`112c7158956bbfdffe57a44a122097dddf8babbcac1461b66e4722c52b7aa01d`.
All 601 source/configuration/contract inputs and six software receipts are
frozen. The launcher returned successfully; no completion polling or automatic
follow-up. At launch acceptance remained pending; D114 below now closes its
bounded scope after user-requested result inspection.

## SPEC-010 independent family closeout (D114)

All 422 registered tests pass in 418.438 s. The new stdlib/Decimal saved-data
review closes 3,256 reference comparisons, 1,944 physical records, twelve
complete restart suffixes and 36 checkpoint links in 3.601 s. All 601 captured
inputs / 292 results authenticate; 24 audit software checks pass. No solver
reruns or production edits. [Closeout and identities](../../reports/SPEC010_FAMILY_CLOSEOUT.md).

The new files in `kinetic_family_audit` extend the worktree, not the frozen
capture. Do not relax or invoke the original launcher's whole-directory guard
as if the growing tree were the original context. Full historical release
regression, native coupled comparison, biology and GPU remain separate.

## REF-005b native pump–leak lifecycle preparation (D115)

`pump_loop_preflight` prepares six native controls × observed/unobserved,
eight 25 µs FULL INIT steps on the supported seven-cell fixture. Record direct
loop pump/passive arguments and returns, driver scaling and masking, ordinary
concentration updates, native histories and exact observer pairs. The sodium-rate
diagnostic is explicitly not ATP consumption. No Cells trajectory runs here.

**29 software checks pass in 2.70 s**, including all six real native YAML loads.
[Contract](../../docs/BETSE_PUMP_LOOP_PREFLIGHT.md) and
[detached handoff](../../reports/REF005B_PUMP_PREFLIGHT_HANDOFF.md) define the
new source context, immutable prerequisites, bounds and launch command.
Return after launching; successful producer checks still need an independent
review on the user's next instruction. No polling or automatic follow-up.

Launched **2026-09-16 15:41:13 UTC**, PID **3247939**, at
`runs/ref-005b-pump-loop-2026-09-16/capture-01`; registration SHA-256
`5d8a6285baec4182758eff0e407ff95e2580dce5db3a9718460384e45d70c6bf`.
The launcher returned successfully and freezes 613 inputs. At launch no terminal
result was inspected or claimed. D116 below records the later user-requested review.

## REF-005b independent native lifecycle closeout (D116)

The capture passed in 29.314 s. The new `pump_loop_audit` stdlib/70-digit reviewer
independently closes **73,188 comparisons, 150 physical records, 48 updates and
six exact observer pairs in 1.877 s**. All 613 inputs / 73 payloads authenticate;
26 audit software checks pass. Known disabled-cut notices are accounted for.
No simulators are rerun, native restart pickles are not executed, and no coupled
trajectory or biology claim follows. [Closeout](../../reports/REF005B_PUMP_LOOP_CLOSEOUT.md).

## REF-005c matched refined pump–leak pilot (D117)

`pump_matched_pilot` maps the actual native preparation into the existing public
kinetic finite-bath model. Full capacitance is retained when boundary masks
reduce transport area. **37 software checks pass in 24.07 s**, including real
compiled execution and complete-checkpoint restart. Production is unchanged.

```text
.venv/bin/python -B validation/betse/pump_matched_pilot/pilot_job.py launch runs/ref-005c-matched-pump-2026-09-16/pilot-01 --tests reports/ref-005c-pilot-checks-01.xml
```

The [contract](../../docs/BETSE_MATCHED_PUMP_PILOT.md) and
[handoff](../../reports/REF005C_MATCHED_PUMP_HANDOFF.md) register a 1 ms six-control
scope: 144 held-state backend evaluations, 18 independent reference solves,
36 native runs / 18 observer pairs, 24 Cells trajectories and six exact restart
suffixes. Reference refinement precedes producer trajectory comparisons; raw
native time labels remain distinct from elapsed physical updates.

One detached attempt: CPUs 0–3, one BLAS thread, 1,080 s total, 64 MiB/file /
512 MiB disk artifacts. Freeze 629 inputs and the test receipt; retain complete
inputs/outputs, phase logs and terminal result/failure. No automatic polling,
audit, retry, regression or follow-up. A launch is not a passing result; a
producer pass still needs user-requested independent review.

Launched **2026-09-16 16:29:02 UTC**, PID **3261836**, at
`runs/ref-005c-matched-pump-2026-09-16/pilot-01`; registration SHA-256
`2dc09a3d112b1f0efc3a03d0a43f9cc2a395078553881ba7a7cc33497dff269b`.
The launcher returned successfully and freezes 629 inputs plus the receipt.
No completion/status polling or automatic follow-up was performed.

## REF-005c independent failed-pilot diagnosis (D118)

On the later user-requested review, all simulation phases had completed but
the final comparator had rejected native energy after **385.829 s**. The failed
attempt and all 629 sources remain unchanged. No new simulation is run here.

`pump_pilot_diagnosis` independently reconstructs energy from total applied
flux and potassium-derived cycles using 70-digit Decimal arithmetic. A bounded
**41.424 s** saved-data review finds **six failures in 203,274 comparisons**:
two native finest energy coordinates and four total energy-balance limits.
All 376,320 additional flux/transfer checks, 36 refinement groups, six decoded
full-state restart suffixes and six complete checkpoint links pass. All 431
failed-attempt files are newly sealed and rechecked; this is not a successful
original capture manifest. **33 diagnosis tests pass / 1.73 s**.

Review: `runs/ref-005c-pilot-diagnosis-2026-09-16/review-01`.
Completion SHA-256:
`c6b5f18258d1fa14c2e742fa76b582c0bc7c32ff9e729d96800d8475830a8bb3`.
[Diagnosis, identities and next proposal](../../reports/REF005C_PILOT_FAILURE_DIAGNOSIS.md).

The pilot stays unqualified. The energy errors contract at first order and the
convex energy remainder explains the dominant defect. Recommend a finer native
ladder with unchanged physics/tolerances and explicitly revised recording
bounds. No replacement capture or automatic follow-up is launched.

## REF-005c explicit native refinement (D119)

`pump_pilot_refinement` prepares a separately authorized native ladder:
6.25 / 3.125 / 1.5625 µs, unchanged six controls / 1 ms physical scope / numerical
budgets. All twelve repeated 6.25 µs records must match exactly. Reuse 213
byte-verified saved files for 24 Cells trajectories, eighteen references and six
restart suffixes; no new Cells/reference solver execution. Production is unchanged.

**46 preflight checks pass in 36.82 s**, including all eighteen actual native
YAML loads, saved-panel replay reproducing all six old misses, exact-copy and
single-dispatch controls, native grid identity and bounded failure reporting.
Receipt 01 retains the earlier 41-check scope; receipt 02 binds the final source.

```text
.venv/bin/python -B validation/betse/pump_pilot_refinement/refinement_job.py launch runs/ref-005c-refined-pump-2026-09-16/refinement-01 --tests reports/ref-005c-refinement-checks-02.xml
```

[Contract](../../docs/BETSE_PUMP_REFINEMENT.md) and
[handoff](../../reports/REF005C_REFINEMENT_HANDOFF.md) bind 641 inputs and one
detached campaign: 36 native runs / 18 observer pairs / 6,720 observed updates.
CPUs 0–3, one BLAS thread; 1,260 s total, hard 256 MiB/file and checked 2 GiB disk
artifacts. Retain original criteria, all numerical miss counts and partial
records on failure. A producer pass still needs independent review. Do not poll,
retry or launch automatic follow-up work, and do not change Cells to imitate
upstream discretization errors.

Launched **2026-09-16 17:56:47 UTC**, PID **3280084**, at
`runs/ref-005c-refined-pump-2026-09-16/refinement-01`; registration SHA-256
`1dcfb80dc010bc694bf752caa0b72c0f97699e162f4aa3599bfc5258deec9c07`.
The launcher returned successfully and freezes all 641 inputs plus the passing
software receipt. No numerical pass, completion/status check or automatic
follow-up is claimed by this launch acknowledgement.

## REF-005c independent refined-pilot review (D120)

The later user-requested status check finds D119 completed in **501.812 s**:
**616,806 comparisons / zero failures**, 36 native runs, eighteen observer
pairs, twelve exact overlap records and 36 passing refinement groups. The
producer receipt still requires independent review; the original failed attempt
and its diagnosis remain unchanged.

`pump_pilot_audit` independently reads the saved records using stdlib-only
decoders, an import fence and 70-digit native energy/raw-law arithmetic.
Authenticate all 641 inputs, 55 production modules and 444 payloads, then
review all 6,720 observed updates, 20,178 physical records, original numerical
criteria, exact overlap, reference agreement and complete Cells restarts.
No simulator or reference integration is invoked. **47 preflight checks pass
in 30.06 s**, including an actual complete 640-step refined control.

```text
.venv/bin/python -B validation/betse/pump_pilot_audit/audit_job.py launch runs/ref-005c-refined-pump-audit-2026-09-16/audit-01 --tests reports/ref-005c-audit-checks-01.xml
```

[Handoff and precise scope](../../reports/REF005C_AUDIT_HANDOFF.md).
One detached audit: CPUs 0–3, 900 s, hard 32 MiB/file and checked 128 MiB output.
Native pickles are hashed, never executed. Preserve known disabled-cut notices,
partial rows, logs and terminal failure/result. No polling, automatic retry,
regression, physics/tolerance changes or subsequent campaign. Independent
acceptance remains pending until the review passes.

Launched **2026-09-16 18:27:11 UTC**, PID **3286920**, at
`runs/ref-005c-refined-pump-audit-2026-09-16/audit-01`; registration SHA-256
`55f85fb313424311247f2174e2b1f034e3a01d27e148191a12114b726250ea9d`.
The launcher returned successfully, freezing eleven review/helper/handoff
inputs and the 47-test receipt. No completion/status check or automatic
follow-up was performed. The launch is not independent acceptance.

## REF-005c formal closeout and longer-duration planning (D121–D122)

On 2026-09-17 the independent terminal result is verified and
[formally closed](../../reports/REF005C_PUMP_PILOT_CLOSEOUT.md): **203,274
acceptance comparisons with zero failures**, plus **10,610,676 additional
law/transfer/conservation/link checks**, in **337.048 s**. All 6,720 native
updates, 36 refinement groups, twelve overlap records and six complete Cells
restart/checkpoint links pass. Twenty-three refinement groups are floor-limited.
The original rejected attempt, physics and all scientific limits are preserved.

Review completion SHA-256:
`e2e67df2b6118cdacfcbf4f23357a972bcb6ecae7d4eacad3f02956ab4369bc1`.
No simulator or high-precision review rerun occurs at formal closeout.

The [D122 plan](../../docs/BETSE_PUMP_RELAXATION_PLAN.md) and
[`pump_relaxation_plan/proposal.json`](pump_relaxation_plan/proposal.json) are
explicitly design-only. Qualify bounded, lossless native recording and matched
Cells window/restart behavior first; then register a 10 ms numerical extension
before longer relaxation and timed recovery. Original biological-data readiness
is separate and can proceed alongside the engineering.

**35 planning checks pass / 7.25 s**. The bounded saved-data planning command
authenticates the completed pilot and computes matrix/resource estimates only:

```text
.venv/bin/python -B validation/betse/pump_relaxation_plan/check_plan.py runs/ref-005d-planning-2026-09-17/design-01 --tests reports/ref-005d-plan-checks-01.xml
```

That planning output now exists and must not be overwritten. Completion SHA-256:
`db57a5c3fb2219e7dd03b885485888d798b2cc63d9473ee639540bdd4a4142cb`.
The naive legacy-format 10 ms projection is 14.74 GiB, not an approved storage
budget or an ETA. No long run, production change, automatic follow-up or GPU
claim follows from the design receipt.

## REF-005d R0: lossless offline native recording (D123)

The [new recording layer](native_recording/README.md) preserves every field of
the closed pump INIT rows using typed float64 records, bounded compressed chunks,
an append-only hashed index and a terminal manifest. It changes no simulator,
upstream source, physical law or acceptance criterion. Static metadata begins a
stream; endpoint/history hashes close it, without requiring future state up front.

**132 checks pass / 3.51 s**, including all twelve actual short rows and a
writer/iterator allocation check with cyclic GC disabled. The final 640-update
largest-row probe exactly reconstructs **143,185,735 bytes** from **1,549,225 bytes**
(92.424× smaller); encoded chunk peak is 1,087,999 bytes. Whole-process RSS is
reported separately: 504.82 MiB including materialized legacy/decoded trees.
This is not a simulation speedup or bounded live observer-memory result.

The [handoff](../../reports/REF005D_CODEC_HANDOFF.md) scopes one detached offline
matrix: all 36 saved native rows, 6,720 observed updates and 20,196 stream records.
Source/receipt binding, per-row exact canonical comparison, resource limits and
durable failures precede successful terminal status. No polling, automatic
review, simulator run, retry or follow-up. Live observer neutrality, actual
seven-cell Cells window/restart parity and 10 ms remain separate gates.

## REF-005d R0: independent offline review (D124)

D123's conversion is complete: **36 exact rows / 215.987 s**, preserving all
6,720 observed updates and 20,196 stream records. Native JSON files shrink from
**1,509,951,698 to 18,070,684 bytes** (83.558× smaller). All 778 sealed payloads
and fourteen captured source/helper/contract inputs authenticate. Completion:
`9e5ea291c711deb6edbd6c674c8a7aaff033b932f4c8ef9388db40a4637fe379`.

The [independent reader/reviewer](native_recording_audit/README.md) uses no
producer serializer, partitioner, row decoder or canonical digest to establish
equality. It compares every original value/type/float64 bit, accounts for whole
field/primitive coverage, and independently recomputes array and stream hashes.
**133 preflight checks pass / 52.34 s**, including all six actual coarse-grid
controls in both modes and a complete finest 640-update pump+leak row.

One [bounded detached review](../../reports/REF005D_CODEC_AUDIT_HANDOFF.md) targets
all 36 rows. No physics rerun, new simulator trajectory, production change or
tolerance change. No polling, retry, audit/regression or automatic follow-up.
Only a passing terminal review may close the offline codec sub-gate; live
recording, matched Cells windows/restarts, 10 ms, biology and GPU remain separate.

## REF-005d R0: offline closeout and live/window qualification (D125)

The independent offline review now passes in **191.565 s**: all **36 rows /
54,685,116 exact scalar comparisons / zero failures**, including signed-zero
preservation and 828 independently recomputed history/endpoint array digests.
Forty sealed review payloads and fourteen frozen inputs authenticate. See the
[closeout](../../reports/REF005D_CODEC_CLOSEOUT.md); old launch narratives and
captured source contexts remain unchanged.

The new [live adapter](live_recording/README.md) holds one pending update/raw-call
group, emits ordered records during actual native execution, and compares all
36 same-1 ms runs to accepted evidence. Storage-only observation is explicitly
distinguished from truly hook-free execution. Native histories/time arrays and
pickle creation are retained; no constant-memory native claim is made.

The [handoff](../../reports/REF005D_LIVE_HANDOFF.md) also qualifies the ordinary
Cells APIs on all 24 matched trajectories: 72 window comparisons, eighteen disk
recording policies and six complete saved-checkpoint restart pairs. Long work
is bounded and detached, with no automatic polling or independent follow-up.
Production/physics/tolerances, 10 ms and broader BETSE/biological/GPU scope are
unchanged; a producer pass still needs separate independent review.

## REF-005d R0: passed preflight to full live/window matrix (D126)

The D125 preflight now passes **79 tests in 54.27 s / 77.511 s overall**.
All 235 sealed payloads, 668 frozen inputs/capsule members and the passing
receipt authenticate, including the actual native and Cells smoke evidence.
Earlier preflight failures remain preserved. The frozen implementation and
handoff are not edited to replace their historical launch statements.

The [new execution account](../../reports/REF005D_LIVE_QUALIFICATION_LAUNCH.md)
launches the prepared same-1 ms matrix using exactly that source context:
36 native runs/eighteen pairs and the 24-baseline/72-window Cells qualification,
with all disk policies and complete restart checks. Same physics, thresholds
and resource caps; detached and user-polled. Full acceptance and separate
independent review are pending at launch, and no later campaign starts automatically.

## REF-005d R0: authenticated native reuse and Cells-only continuation (D127)

D126 stopped at its controller stderr gate after **577.531 s**, after all
36 native overlaps/eighteen pairs passed. Exactly 72 known cut-disabled notices
used `[live_job.py]`, while the `-c` smoke had supplied `[betse]`. No Cells
phase started. Preserve that failure and every frozen source unchanged.

The [new continuation](live_recording_resume/README.md) checks the registered
script prefix, exact message and count; it does not discard other stderr.
**54 regression checks pass / 6.41 s**, including an actual installed terminal
formatter launched as a script, the saved failure regression, all native hash
links, corruption/coverage refusals, Cells-only dispatch and timeout cleanup.
The source-bound passing receipt covers 674 inputs; the previous 79-test
observer/window implementation is reused without edits.

Bind all 964 original files, comparison/capture/stream/index/chunk hashes and
prerequisites in the new registration. Reuse 36 native runs without recomputation;
run the unchanged 24-baseline/72-window/eighteen-recording Cells matrix with all
restart and sparse/zero-length controls. Same limits and scientific scope,
detached without polling or automatic follow-up. The original stays failed;
success in the new packet is still pending separate independent review.
[Handoff](../../reports/REF005D_LIVE_CONTINUATION_HANDOFF.md),
[current launch/evidence](../../reports/REF005D_LIVE_CONTINUATION_LAUNCH.md).

## REF-005d R0: output ownership and shared-worker gate (D128)

D127 stopped after **79.799 s** on a validation-path collision: the ordinary
baseline and full window recording both targeted `full/`. The production
non-overwrite guard correctly refused. Native reuse authenticated, and one
Cells case completed all three windows; this is not a completed Cells matrix.
Preserve both failed attempts, all frozen code and all native evidence.

The [new adapter](live_recording_paths/README.md) reserves disjoint baseline,
per-policy recording and resumed-output leaves before simulation, then verifies
that baseline bytes stay unchanged. Frozen numerical checkers and public Cells
APIs are reused. **51 fast harness tests pass / 2.91 s**; source-bound software
execution takes **3.402 s**, covering 680 inputs. Tests exercise the real worker's
filesystem/control sequence with stubbed physics, not numerical validation.
An earlier temporary-directory fixture failure remains preserved.

One detached job first runs a real 1 ms pump+leak / 25 µs compiled case through
the same worker, including all disk policies, full/windowed loaded restarts and
zero-length continuation. Only a sealed passing probe admits the original full
24-baseline/72-window/eighteen-recording matrix and its remaining controls.
Probe output is separate, not counted toward the matrix. Reuse 36 native runs
without recomputation; recompute all Cells cases under the corrected layout.
No polling, automatic retry or follow-up. Numerical and independent acceptance
remain pending. [Contract](../../reports/REF005D_OUTPUT_LAYOUT_HANDOFF.md),
[launch/evidence](../../reports/REF005D_OUTPUT_LAYOUT_LAUNCH.md).

## REF-005d R0: independent saved live-output review (D129)

D128's probe and full matrix subsequently **pass in 553.910 s**, with 516 sealed
payloads, 520 regular files and 680 frozen inputs. The separate probe is additional
to the 24-baseline/72-window/eighteen-recording matrix and its six full/window
restart pairs, six zero-length and two sparse controls. This is producer success.

The [new independent reviewer](live_recording_audit/README.md) compares all 36
live native streams with accepted original JSON through the qualified independent
codec decoder, then all eighteen observer pairs. Saved Cells arrays, chunk indexes
and complete checkpoints receive direct byte/schema/clock checks. Unsaved windows
receive separately implemented expected-receipt reconstruction, not direct
inspection of trajectories that do not exist on disk. No solver/model imports,
physics reruns, changed tolerances or upgraded biological/GPU claims.

Authenticate the complete accepted prerequisite chain and both preserved failed
packets, plus source-bound software and frozen sources before/after review.
Pass corruption/resealing, real saved-case and job-control tests first; then
launch one detached bounded audit with no polling or automatic follow-up.
**97 preflight checks pass / 15.33 s**; the full audit was launched detached
at **17:18:03 UTC**, with its verdict still pending. Both earlier software
failures remain preserved. [Frozen scope](../../reports/REF005D_LIVE_AUDIT_HANDOFF.md),
[software and launch](../../reports/REF005D_LIVE_AUDIT_LAUNCH.md).

## REF-005d closeout and REF-005e R1-S0 reference scoping (D130)

D129 now passes in **128.769 s**: 54,685,116 exact native comparisons, eighteen
observer pairs and all registered direct saved-output/expected-receipt checks,
with zero failures. [R0 closeout](../../reports/REF005D_LIVE_CLOSEOUT.md) preserves
both earlier failed attempts and the limited assurance of unsaved-window receipts.

The [reference-scoping adapter](pump_relaxation_scope/README.md) prepares eighteen
new **10 ms** independent solves on the unchanged six-control preparation.
Cross-solver, prefix, sampled domain/accounting and resource checks precede a
separately scoped native/Cells campaign. Production, equations and scientific
limits stay fixed. **73 source-bound checks pass / 17.83 s**; formal closeout
completed and the reference-only study launched detached at **18:25:49 UTC**.
Its result remains pending; no polling or automatic follow-up. Junction topology and biological data
readiness are recorded separately, not declared complete by pump/reference work.
[Contract](../../reports/REF005E_REFERENCE_SCOPE_HANDOFF.md),
[software, closeout and launch](../../reports/REF005E_REFERENCE_SCOPE_LAUNCH.md).
