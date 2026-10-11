# CORE-008 physical ionic graph production acceptance

2026-09-10 UTC. Status: **complete — bounded CPU/JAX production acceptance**.
All 114 new targeted tests and all 3210 regression tests pass, with no failures,
errors or skips. The [release audit](../runs/core-008-2026-09-10/release-audit.json)
and [workspace closeout](core-008-closeout.json) retain the machine-readable result.

The new identity is `physical_ionic_graph@1`, Cells 0.13.0. The
[production guide](../docs/PHYSICAL_IONIC_GRAPH.md) records the prospective
scope and resource limits. The nine earlier model identities retain their
equations, timestep limits and serialization semantics; old snapshots are not
implicitly migrated to a changed source version.

## Preserved baseline and numerical authority

[Pre-edit preservation](core-008-preservation.json) authenticates accepted
0.12.0, repeats the NUM-008 reference and CORE-007 production audits, and saves
318 source/configuration/documentation/packaging files including all 44 old
production modules. The archive SHA-256 is
`432fa9ec599c056f145f5e97ec6007a5b94e631e08ce3995df832367985ef5c6`.

The unchanged [NUM-008 reference](NUM008_REFERENCE.md) supplies twelve short
single/disconnected/pair/star cases and saved refined implicit trajectories.
Its 2 ms RK4/cubic selection has passing 1 ms refinement only for this panel.
The preserved-source auditor repeats all 194 payload/26 source checks and
replays 256283 sample rows without rerunning an ODE solver. Its source guards
remain unchanged and execute under authenticated 0.12.0.

## Implementation and preflight

One common maintained bath; explicit species/charge support; heterogeneous
cells; independently padded cell/membrane/channel/edge axes; optional local
channels and sparse fixed junctions. All local and edge rates use the same
complete solver stage. Internal transfers have separate histories and never
enter the bath ledger. Amounts alone determine mobile ionic charge.

All nine state leaves survive the existing scalar/checkpoint/window/cohort
interfaces. Inhibited gates continue relaxing. Real trial states and complete
cubic interiors have domain guards; there is no clipping, gate reset or ledger
reconstruction. Both local/global material and weighted-charge accounting and
total chemical/electrical/pump-work/dissipation accounting are checked.

The final targeted preflight passes **114 tests** in 85.286 s of JUnit time:
[JUnit receipt](core-008-targeted-02.xml). Earlier preflight failures are retained:
field/API naming and a finite-vs-overflow boundary in the initial test harness;
scalar-array corruption helpers that initially modified a copy; and a cycle
witness whose control vector initially had the wrong edge count. No frozen
physical input, trajectory tolerance or numerical bound was changed. The cycle
test is an algebraic checkpoint-history witness, not a qualified cycle trajectory.
The twelve full production trajectories already pass the saved-reference test.

## Formal session

The prospective acceptance limit is 2400 s wall time and 1 GiB artifacts, with
CPU-only float64 execution, four pinned eager lanes, and single-thread BLAS/OpenMP.
Each attempt uses a new output directory; partial/failure evidence is retained.
The first formal session, `runs/core-008-2026-09-10/acceptance-01`, passes in
453.535560 s with 462687262 bytes (441.253 MiB) of evidence, within both limits.
These are acceptance-workload costs, not a simulator performance benchmark.
No formal attempt failed or required a revised scientific/resource plan.

The [standalone read-only audit](core-008-production-audit.json) authenticates
600 payloads and 223 captured implementation files, including 46 production
modules. The verification SHA-256 is
`6d60fd732bfd0f8a068fb0a0b342f9487f9b0b74326f73d8af84aefc7f6a9b43`.
[All saved checkpoints load](core-008-checkpoint-load.json): 162 scalar and
16 cohort checkpoints, with complete state and layout under the current sources.

All twelve unchanged cases pass in compiled and eager execution, with twelve
exact fresh-process restarts and a future-only branch: 37 scalar outputs in all.
The branch changes future junction inhibition/horizon while preserving every
state leaf, and is checked against the frozen always-on star reference.
Two full scalar window runs and four original/resumed cohorts pass exact replay;
the monovalent cohort combines eight single/disconnected/pair/star worlds and
the divalent cohort four worlds, with independent clocks and equal capacity
extents. Finished worlds stay finished when other worlds continue.

Earlier-model regression is exact on 78 scalar cases, 1777 windows, ten batches
and 44 worlds, plus 1680 arrays across the fourteen multispecies and fourteen
channel references. All 488 old scalar and 54 old cohort snapshots load under
preserved 0.12.0, and old channel replay is exact. Current sources explicitly
refuse implicit migration of those old checkpoints.
The read-only auditor independently reconstructs 38 physical readouts and cubic
observations, checks complete histories/accounting against saved reference data,
and rejects rehashed corruption of real quantities as well as inactive padding.

The worst observed normalized trajectory error is 0.0921231 (9.21% of budget).
Maximum cell-voltage error is 4.593821e-8 V, membrane-gate error 1.661762e-6,
and junction-gate error 2.374518e-8. Maximum local charge residual is
1.793819e-12 V; global weighted-charge residual is 3.777270e-23 C; resolved
energy residual is 3.223453e-8 pJ. No dissipation decrease is detected. These
are bounds observed on the frozen short panel, not universal physical accuracy.

## Full regression and release checks

The [four-context regression receipt](core-008-regression-01/verification.json)
records **3210 passing tests**, with no failures, errors or skips. Each historical
reference suite runs under its authenticated source version; source guards are
not relaxed to accommodate the new production version.

| Source context | Tests passed | JUnit seconds |
| --- | --- | --- |
| Current production, 0.13.0 | 1821 | 713.004 |
| Preserved reference, 0.10.0 | 971 | 160.725 |
| Preserved channel reference, 0.11.0 | 205 | 19.262 |
| Preserved graph reference, 0.12.0 | 213 | 15.554 |

Summed test-context time is 908.545 s, excluding the driver's archive-copy/setup
overhead. All eight JUnit/log payloads, the driver and the three archive hashes
are reauthenticated. The matrix receipt SHA-256 is
`f0bc59c18c316ed5ac1085fe27e9984742168d8457f35e84fd247ea3a16c31a1`.
All 218 Python files pass Ruff lint and format checks; dependency and whitespace
checks pass. The edited Markdown links and structure are checked at closeout.

The [pre-edit workspace baseline](core-008-workspace-baseline.json) retains 466
file hashes. Of those, 448 are byte-identical and none is missing. Eighteen
expected changes comprise eleven status/design documents, five production
version/schema/control/registry modules, packaging and the test-context driver.
The new graph adds two production modules; earlier model equations, transport
laws, numerical methods and shared runner/checkpoint/window/cohort machinery
remain unchanged. Frozen SPEC-007/NUM-008 and earlier scientific/pilot evidence
remain byte-identical. The release rechecks all 600 accepted payloads, 223 source
capsule members and 318 preserved 0.12.0 archive members against their hashes.

## Limits and next boundary

No biological validation, BETSE parity, arbitrary-graph accuracy guarantee,
cycle trajectory qualification, GPU execution, optimization, organ model or
multirate solver is claimed. Batching is independent experiments, not communication
between organs. The descriptive pilot stays closed and the E02 source campaign
stays deferred.

The next recommended architecture step, SPEC-008, is a deliberately small
finite extracellular-compartment contract: explicit outside inventories,
membrane/charge ownership, maintained-bath reduction and closed-system material
and energy checks before any mesh PDE or organ preset. It needs its own reference
and numerical qualification; the present maintained bath is not silently converted.
