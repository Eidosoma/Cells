# BETSE-level capability through the Cells multiscale design

Current position, 2026-09-17 / D130: the fixed channel suppression/release,
instantaneous Na/K contact and short coupled pump numerical scope are independently
closed. The process gate is reviewed and the versioned finite-bath model is
implemented in development, with its bounded 422-test ordinary-runner gate and
independent review closed. Native pump lifecycle ownership is also independently
closed. The matched 1 ms pilot completed but failed six energy criteria;
independent diagnosis supports a finer native ladder, not a physics/tolerance
change. The explicitly amended native refinement passes its independent review:
203,274 acceptance comparisons and 10,610,676 additional law/conservation/link
checks, with zero failures. D121 closes the 1 ms scope; D122 plans bounded
lossless recording before a separate 10 ms extension. Thirty-five planning
checks pass. D123 implements [lossless evidence recording](../validation/betse/native_recording/README.md):
132 software checks pass and all 36 saved rows now round-trip exactly with
83.6× smaller storage overall. D124's [independent codec review](../reports/REF005D_CODEC_AUDIT_HANDOFF.md)
passes its full review with 54.7 million exact comparisons and zero failures.
D125 [closes offline recording](../reports/REF005D_CODEC_CLOSEOUT.md) and implements
the [same-1 ms live/window qualification](../reports/REF005D_LIVE_HANDOFF.md);
D126 [closes its 79-test preflight and starts the full qualification step](../reports/REF005D_LIVE_QUALIFICATION_LAUNCH.md)
with the unchanged tested implementation. Its 36 native comparisons/eighteen
pairs pass, but a script-prefix logging gate stops the controller before Cells.
D127 [preserves that failure and adds a Cells-only continuation](../reports/REF005D_LIVE_CONTINUATION_LAUNCH.md),
with 54 passing regression checks and hash-authenticated reuse of all saved
native streams. That continuation stopped on baseline/window output collision;
D128 [separates their directories and gates the matrix on the same real worker](../reports/REF005D_OUTPUT_LAYOUT_LAUNCH.md).
Fifty-one fast harness checks pass. No native recomputation or simulator change.
The actual-worker probe and full matrix subsequently pass in **553.910 s**.
D129 launches their [independent saved-evidence review](../reports/REF005D_LIVE_AUDIT_LAUNCH.md)
after 97 passing preflight checks,
including direct saved-array checks and expected-receipt replay for unsaved
windows. That independent review now **passes in 128.769 s**, and D130
[closes the recording scope](../reports/REF005D_LIVE_CLOSEOUT.md). The
[10 ms reference/domain study](../reports/REF005E_REFERENCE_SCOPE_LAUNCH.md)
launches detached after **73 passing preflight checks**; its result remains
pending. This is not yet a native/Cells duration-extension campaign. Native retained
histories are unchanged, not constant-memory. No production change. Full release
promotion, junction correspondence and original-data evaluation remain ahead. See the
[active realism plan](BETSE_REALISM_AND_NEXT_STEPS.md). The chronology below
preserves earlier step-specific statements, not a claim of current full parity.

2026-09-09, D045 / R009 / ARCH-003. **Accepted target architecture and staged
roadmap, not implemented feature parity.** The first endpoint pilot is
[closed as descriptive](../reports/BIO003_PILOT_CLOSEOUT.md). Cells
0.11.0 now adds a [multispecies membrane family](MULTISPECIES_MEMBRANE.md), with
[bounded production acceptance complete](../reports/CORE006_ACCEPTANCE.md). GPU implementation and long E02 execution are
not started by this design update.
SPEC-006 now adds a [first channel design/reference](VOLTAGE_GATED_CHANNEL_SPEC.md),
with [passing checks](../reports/SPEC006_DESIGN_CHECK.md), not production B03 support.
NUM-007 now adds [bounded coupled numerical qualification](../reports/NUM007_REFERENCE.md),
selecting 0.5 ms RK4/cubic with refinement. CORE-007's
[production implementation](VOLTAGE_GATED_MEMBRANE.md) now exists in 0.12.0;
[bounded production acceptance](../reports/CORE007_ACCEPTANCE.md) passes.
SPEC-007 now provides the [physical ionic graph contract](PHYSICAL_IONIC_GRAPH_SPEC.md)
and [passing instantaneous composition checks](../reports/SPEC007_DESIGN_CHECK.md).
[NUM-008 now qualifies short graph trajectories](../reports/NUM008_REFERENCE.md):
twelve fixed cases, 2 ms RK4/cubic with passing 1 ms refinement and saved-data
audit. CORE-008 now implements a separate [production graph family](PHYSICAL_IONIC_GRAPH.md)
in 0.13.0; its [CPU/JAX acceptance status](../reports/CORE008_ACCEPTANCE.md)
remains distinct from reference qualification and biological/source parity.
CORE-009 adds a separate [finite well-mixed outside](FINITE_EXTRACELLULAR.md)
in 0.14.0, with [formal production acceptance](../reports/CORE009_ACCEPTANCE.md)
passing. Spatial extracellular design and NUM-010 numerical qualification now
pass; D061/CORE-010 adds a development passive CPU/JAX implementation, with its
formal bounded development acceptance now complete in 0.15.0.dev0; stable 0.14.0
is not promoted. This is not complete B08 support. D065/REF-003a now adds the
[first executed BETSE passive-law comparison](../reports/REF003A_PASSIVE_CONTACT.md),
not a whole-cell or biological validation result. D066/REF-003b1 now executes
[native preparation](../reports/REF003B1_PREPARATION.md), but rejects seven cell
compartments from the requested single-cell preset. D067/REF-003c adds a
[passing explicitly seven-cell capture](../reports/REF003C_CLUSTER_ALIGNMENT.md)
for initialization, charge, instantaneous rates and prescribed single updates;
the existing finite-bath model needs no production changes. D068's
[separate audit/closeout](../reports/REF003C_CLOSEOUT.md) now passes all 171 short
adapter tests. D069's [first full-loop trajectory](BETSE_PASSIVE_TRAJECTORY_PLAN.md)
completed but failed 36 shared-bath amount checks; D070 independently reproduces
the rejection and uses a finer native ladder with unchanged physics and
tolerances. D071's [independent closeout](../reports/REF003D_CLOSEOUT.md) now
reproduces all 435,144 passing comparisons; all 325 adapter tests pass.
This is bounded 1 ms passive/blocked trajectory correspondence. The literal
one-centre SVG also fails triangulation; the original one-cell gate stays rejected.

D073's [SIM-phase preparation preflight](../reports/REF003E0_PHASE_PREFLIGHT.md)
finds another configuration dependency: targeted events require tissue-profile
structures absent in the profiles-off baseline. The adapter/observer's 73 focused
checks pass, but the native preflight failed. An [explicit profile bridge](BETSE_SIM_PHASE_BRIDGE.md)
must precede event-response qualification; no feature-parity row is promoted.

D074 now passes that [explicit preparation bridge](../reports/REF003E0_PROFILE_BRIDGE.md):
six native preparations, 30 direct no-op dispatches, unchanged physical setup
and 87 passing focused tests. Profile activation is separately controlled and
partial state is durable. Full-loop phase/profile/event correspondence remains
unqualified; no capability-parity or biological claim follows from preparation.

D075 adds the [full-loop pilot contract/adapter](BETSE_FULL_LOOP_BRIDGE.md),
with 100 passing focused tests before native execution. Its 12-run matched-
constant 25 µs pilot isolates phase, profile and no-op transitions with observer
partners. This is a detached, user-polled capture, not expanded-bridge or feature
qualification; production and earlier evidence remain unchanged.

D075's capture reports all 12 runs passing in 26.139 s. D076's
[independent closeout](../runs/ref-003e0-loop-audit-2026-09-12/audit-01/completion.json)
passes 88,956 numerical comparisons and 165 tests in 32.682 s, qualifying only
that narrow pilot. D077's expanded capture now passes all 72 runs / 3360
observed steps in 203.562 s, including both constant sets and three timesteps.
D078's [joint independent closeout](../runs/ref-003e0-expanded-audit-2026-09-12/audit-01/completion.json)
passes 1,232,616 numerical comparisons and 433 tests in 167.679 s, qualifying
the expanded zero-amplitude bridge. No capability-parity row or biological
validation follows. D079's [held-intervention design](BETSE_HELD_INTERVENTION.md)
now checks prescribed nonzero input composition and actual Cells grids without
event-handler dispatch or integration.

D080's [actual nonzero dispatch preflight](BETSE_NONZERO_DISPATCH_PREFLIGHT.md)
now passes four preparations / 160 dispatches in 24.463 s and 75 focused tests.
Targets/modifiers, effective diffusion and physical-state invariance pass without
transport or integration. This is an input-application gate, not a new feature-
parity row or a qualified nonzero response.

D081 adds the [control-aware response pilot](BETSE_HELD_RESPONSE_PILOT.md),
with eight native / 24 Cells runs, fixed 25 µs input and separate solver/backend
comparisons. The new adapter leaves production unchanged and preserves the
original criteria, including known coarse-native baseline failures. Detached
capture, independent audit and convergence qualification remain separate;
no capability-parity row is promoted merely by implementing the checker.

D081's capture completed all 32 runs in 715.769 s, then rejected 150 of 345,576
comparisons under the original criteria. D082's [joint failure closeout](../runs/ref-003e1-response-audit-2026-09-13/audit-01/completion.json)
completes in 50.390 s, with 70 passing new tests and the expected legacy
metadata-guard failure separately recorded. The physical verdict stays rejected.
Its [refinement design](BETSE_HELD_RESPONSE_REFINEMENT.md) distinguishes solver
error from native pulse resampling. D083 now implements the
[finer-input dispatch preflight](BETSE_REFINED_DISPATCH_PREFLIGHT.md), with 109
passing software checks and a separately launched eight-preparation / 960-
dispatch native attempt, which now passes in 116.002 s without integration.
D084 adds the [two finer response panels](BETSE_REFINED_RESPONSE_PANEL.md):
separate fixed-h solver checks, finest-h cross-engine gates and labelled
across-h diagnostics, retaining the original 150 failures. The final 114-test
software regression passes in 95.688 s total without failures/errors/skips,
and was user-reviewed. The capture then stopped at the 16 MiB trace guard after
16 native / 26 Cells runs. D085's [resource-only continuation](BETSE_TRACE_BUDGET_CONTINUATION.md)
raises only eight unexecuted definitions to 64 MiB, retaining exact old-result
provenance and all scientific criteria. All 48 production resource probes and
47 focused tests pass. Launch only 22 remaining Cells runs, then the unchanged
comparison, with a two-hour / 1 GiB combined artifact cap; no polling or follow-up
audit. No capability row is promoted by resource checks or launch. Future
multiscale resource preflight should cover the entire declared grid, while
keeping memory policy separate from physical model and accuracy requirements.

D085's capture now finishes in 2239.322 s: all 2,298,936 required checks pass,
while 4173 coarse/intermediate/across-hold diagnostic failures remain recorded.
D086's [independent saved-data closeout](BETSE_REFINED_RESPONSE_AUDIT.md) replays
the full comparison and separately rebuilds 1,121,904 surface checks. Its 105
new software tests pass. The user-reviewed
[joint completion](../runs/ref-003e1-refined-response-audit-2026-09-13/audit-01/completion.json)
now passes in 249.644 s with all 336 tests and all 2,298,936 required comparisons.
It qualifies only the specified finest-held seven-cell response, not native/
forcing convergence, biology, GPU or a general capability-parity row.

D087/REF-004a adds [isolated Kv1.5 contact](BETSE_VOLTAGE_GATE_CONTACT.md): the
existing continuous kernel/shared RK4 and native gate updater are compared to
separate discrete and exact held-voltage references. Explicit 298.15 K regime,
fast/slow gates and preserved hidden histories precede coupled active transport.
Short software preflight and detached numerical capture are separate from
independent closeout. B03 is not promoted to channel-family or biological parity.

D088's [actual isolated-channel closeout](../reports/REF004A_KV1P5_CLOSEOUT.md)
now passes in 0.979 s, independently rebuilding all 11,266 comparisons; all 102
focused tests pass. Original sources/captures remain unchanged, with no model
rerun. This establishes bounded isolated B03 correspondence only. The
[next coupled preflight](BETSE_COUPLED_CHANNEL_PLAN.md) checks native face targets,
channel-specific transfer/current accounting and common temperature before a
full dynamic comparison; no new production mechanism or GPU optimization.

D089 now implements that [configuration / single-transfer preflight](BETSE_CHANNEL_TRANSPORT_PREFLIGHT.md).
All 76 short software tests pass, with production unchanged. Native network-off,
empty, blocked and active controls isolate channel-specific material/current
ownership; Cells uses its existing finite-bath model at a matched post-gate
state. One detached 300-second / 128 MiB attempt has separate actual receipts,
without automatic polling or closeout. No capability-parity row is promoted
from software tests or a raw capture pass; coupled dynamics and physiology
remain separate qualification stages.

The D089 attempt stopped after 4.672 s on our null biomolecule configuration,
not a transport comparison. D090's [setup correction](BETSE_CHANNEL_SETUP_FIX.md)
uses an empty list, with 107 focused tests passing and the actual native YAML /
type contract checked. The failed packet remains frozen and all numerical
criteria and production physics are unchanged. That capture executed all twelve
native cases, then stopped after 7.084 s at the Cells runtime-identity guard:
the launcher supplied explicit-false instead of the registered absent flag.
D091's [environment correction](BETSE_CHANNEL_RUNTIME_FIX.md) keeps the strict
guard intact. All 152 focused tests and five actual worker startup probes pass;
no transport runs in those probes. Its actual capture now passes all 37,068
comparisons in 21.272 s. D092's [independent single-transfer audit](BETSE_CHANNEL_TRANSPORT_CLOSEOUT.md)
adds exact replay, independent 80-digit reconstruction and complete saved-record
authentication; all 220 focused tests pass. Its actual closeout now passes in
3.215 s with zero failures: the narrow single-transfer contact is closed, not
general channel/tissue parity. D093 adds [full-loop preparation/observer checks](BETSE_CHANNEL_LOOP_PREPARATION.md)
and [feedback-pilot readiness](BETSE_CHANNEL_FEEDBACK_DESIGN.md). Eight short
native INIT runs and twelve Cells candidate-grid/initial-rate checks precede
dynamic registration. No Cells trajectory, new production capability, biological
qualification or GPU execution is included in that preparation.

That preparation now passes in **18.031 s**, with **73,744 native + 348 Cells
initial-rate comparisons**, no warnings and zero failures. D094's
[independent saved-data closeout](BETSE_CHANNEL_LOOP_CLOSEOUT.md) checks every row,
complete states, float64 bytes, clock mapping and candidate resources, without
simulator reruns or production changes. Preparation/readiness, coupled dynamic
qualification and biological validation remain distinct gates; no feature-parity
row is promoted by this audit.

D094's actual preparation/readiness audit now passes in **5.541 s**, all 74,092
comparisons, zero failures. D095's [reference-gated feedback pilot](BETSE_CHANNEL_FEEDBACK_PILOT.md)
implements independent continuous integration/convergence and a 2 ms coupled
comparison through existing production interfaces. Reference checks precede any
simulator trajectory; final coupled qualification still needs a separate saved-
data audit. Full-state restart and distinct native gate-first / Cells RK4 methods
are explicit. No feature-parity row or production release is promoted here.

D095's actual capture passes in **338.424 s**, with zero required failures and
fourteen preserved coarse diagnostics. D096's [independent coupled closeout](BETSE_CHANNEL_FEEDBACK_CLOSEOUT.md)
checks the saved reference, complete state/checkpoints, native accounting and
refinement decisions without integration or production changes. Its actual
receipt now **passes in 172.504 s**, with **5,806,006 independently reconstructed
comparisons**, zero mismatches and all 24 full checkpoints. Its
[closeout](../reports/REF004B_FEEDBACK_CLOSEOUT.md) qualifies only the fixed 2 ms
four-control feedback pilot. D097's [paired-history preparation](BETSE_CHANNEL_HISTORY_PREFLIGHT.md)
passes 2,442 comparisons; D098's [closeout](../reports/REF004C_HISTORY_PREPARATION_CLOSEOUT.md)
replays all checks, independently checks 1,404 rates and authenticates 528 layout
arrays. D099 implements [paired coupled references and capture](BETSE_CHANNEL_HISTORY_PILOT.md)
through existing production interfaces. The actual [paired capture](../reports/REF004C_PAIRED_HISTORY_CAPTURE.md)
now passes in 391.917 s, with all required reference, accounting, refinement,
restart and contrast checks passing. All 21 coarse misses remain. D100 adds the
separately requested [saved-data audit](BETSE_CHANNEL_HISTORY_CLOSEOUT.md), with
explicit histories, independent contrasts and a distinct checkpoint byte check.
No simulator is rerun. Its actual [closeout](../reports/REF004C_PAIRED_HISTORY_CLOSEOUT.md)
now passes in **240.629 s**, with **8,036,300 independent comparisons**, zero
mismatches and all 21 coarse misses preserved. Only this fixed paired-history
scope is closed. D101 adds [suppression/release input design](BETSE_CHANNEL_RELEASE_DESIGN.md)
and 107 passing software checks, not a new response, native dispatch or broader
capability-parity claim.
D102 adds the [actual native input preflight](BETSE_CHANNEL_RELEASE_PREFLIGHT.md)
with 71 passing software tests and two real native smoke cases. The detached
144-phase panel tests input/state separation and single updates; it is not a
release trajectory or a broader parity claim.
The actual D102 native panel completed, but its exact-identity checker rejected
one-ULP shared-bath remixing. D103 adds a [saved-data correction](BETSE_CHANNEL_RELEASE_REVIEW.md):
exact source arithmetic and retained physical budgets, 66 passing software tests,
then separate detached review. Its [actual closeout](../reports/REF004D_RELEASE_INPUT_CLOSEOUT.md)
passes 916,176 comparisons in 24.469 s, with all 104 old exact-guard rejections
preserved. D104's [reference-only block/release experiment](BETSE_CHANNEL_RELEASE_REFERENCE.md)
passes 1,485,380 comparisons in 160.675 s. D105 independently reviews that saved
reference before the [timed simulator comparison](BETSE_CHANNEL_TIMED_RELEASE.md).
D105 subsequently passes in 1,004.27 s with zero required failures and 49 retained
coarse misses. D106's [saved-data audit](BETSE_CHANNEL_RELEASE_CLOSEOUT.md) is the
separate independent gate and now [closes successfully](../reports/REF004D_TIMED_RELEASE_CLOSEOUT.md)
in 387.772 s: 15,042,946 independent comparisons / 182 groups, zero mismatches.
No new integration or production change is included.
Neither software checks nor a reference pass establish biology or broad BETSE
parity. No old captured data or production implementation changes.

## What the target means

User clarification, D107: **at least BETSE-level biological and physical
realism**, not selected-test equivalence. The detailed model must grow to
coupled mechanism/geometry coverage and experimental evaluation; reduced models
stay optional. The [active plan](BETSE_REALISM_AND_NEXT_STEPS.md) distinguishes
those gates from source contact and GPU/multiscale qualification.

Use BETSE's scientific coverage as a long-term baseline and aim beyond it in
validated multiscale execution, 3D geometry, growth/inheritance and interacting
organ models. These are Cells targets, not claims that no other simulator can
do them. Supporting detailed physiology does not require enabling it in every
cell, region or experiment. Small models remain first-class choices.

The comparison baseline is BETSE **v1.5.0**, commit
`5269a714aa2593ed2a6708c4516289977d8ae1a2`, not an unbounded moving latest release.
The inventory below groups scientific capabilities; it is not yet a complete
catalog of every channel subtype, option combination or source defect. Each
implementation slice must enumerate its concrete mechanisms and source cases
before claiming coverage. No row has family-level or end-to-end BETSE numerical
parity. REF-003a supplies bounded instantaneous correspondence for B02's passive
law; REF-003c adds selected seven-cell initialization/update correspondence and
REF-003d v2 an independently audited 1 ms passive/blocked trajectory. Matched
constants and native-default reports remain distinct.

Scientific coverage, input-file compatibility and exact implementation behavior
are different targets. A YAML importer, legacy serialized-state loader, matching
GUI or identical plots are not prerequisites for scientific parity. BETSEE is
a separate GUI. Do not import arbitrary Python expressions or unsafe serialized
objects as an architecture shortcut.

## Primary-source baseline

- [B1: pinned overview](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/README.rst): ions, channels, pumps, extracellular space, networks and workflows.
- [B2: pinned simulation configuration](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/data/yaml/sim_config.yaml): tissue profiles, interventions, noise, mechanics and full/circuit settings.
- [B3: network template](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/data/yaml/extra_configs/extra_config_template.yaml): configurable chemistry, transport, modulation and optimization.
- [B4: flow module](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/physics/flow.py): electroosmotic/Stokes-style flow and divergence-free projection, not a general turbulent-flow model.
- [B5: membrane redistribution](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/physics/move_channels.py): spatial channel/pump weighting dynamics.
- [B6: ER module](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/organelles/endo_retic.py): internal membrane, calcium and pump/channel state.
- [B7: source tree](https://github.com/betsee/betse/tree/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science): channel families, mitochondria and microtubule modules; presence alone does not establish runtime coverage or biological validity.

The original inventory is a read-only source/configuration review, not an
equation-by-equation audit. The later [REF-003a result](../reports/REF003A_PASSIVE_CONTACT.md)
installs pinned BETSE separately and executes only its passive-flux component;
it does not establish other inventory rows. The [earlier review](BETSE_DESIGN_REVIEW.md)
retains the experimental-evidence distinctions. Upstream source is not vendored
into Cells. Any later code/data reuse needs its own attribution and dependency
license review; BETSE and the separate BITSEY source have different provenance.

## Capability inventory and engineering route

"Partial" means a related bounded Cells mechanism exists, not corresponding
BETSE equations or experimental calibration. "Planned" means not implemented.
Source identifiers refer to the reviewed material above.

| ID | Scientific capability / source | Cells today | Required extension and first useful check |
| --- | --- | --- | --- |
| B01 | Multiple ions, valence and background charge / B1-B2 | Partial: new one-cell multispecies family | Explicit transported/fixed/maintained charge and role bindings; larger mechanisms/parameter regimes remain unqualified |
| B02 | Passive membrane electrochemistry / B1-B2 | Partial: passive-law, seven-cell initialization/update and bounded 1 ms passive/blocked trajectory independently audited | [Trajectory closeout](../reports/REF003D_CLOSEOUT.md); finer native steps meet unchanged bounds, v1 remains rejected. Matched/native constants separate. Perturbations, broader regimes and family-wide parity remain unqualified |
| B03 | Voltage/ligand-gated channel families / B1, B7 | Partial: one Kv1.5-style m/h channel; CORE-007 accepted, REF-004a/b/c and fixed REF-004d suppression/release pilots independently closed | [Pinned law](VOLTAGE_GATED_CHANNEL_SPEC.md), [production guide](VOLTAGE_GATED_MEMBRANE.md), [release closeout](../reports/REF004D_TIMED_RELEASE_CLOSEOUT.md); only registered regimes, not broader subtype/ligand coverage or biological memory |
| B04 | Pumps, exchangers and cotransport / B1, B3 | Partial: source contact/numerical candidate, bounded v2 production acceptance, native lifecycle and refined 1 ms matched pilot independently closed | [Pilot closeout](../reports/REF005C_PUMP_PILOT_CLOSEOUT.md); original six-miss attempt preserved. [Longer-duration design](BETSE_PUMP_RELAXATION_PLAN.md) qualifies recording before a separate 10 ms extension. Longer relaxation, other transporters, release matrix and biology remain |
| B05 | Selective, voltage-sensitive gap junctions / B1-B2 | Partial: physical pair plus heterogeneous fixed physical graph family; no BETSE-specific gate qualification | [Graph guide](PHYSICAL_IONIC_GRAPH.md), [production acceptance](../reports/CORE008_ACCEPTANCE.md), [D107 junction plan](BETSE_GAP_JUNCTION_PLAN.md); held-open transport then native lifecycle/state/block semantics. Twelve short graph cases do not establish a fitted connexin catalog |
| B06 | ER/calcium and mitochondrial compartments / B1, B6-B7 | Planned | Compartment-owned inventories, membrane maps and charge closure; closed-compartment exchange and pool balance |
| B07 | Biochemistry, regulation and bioelectric feedback / B1, B3 | Partial: separate EMT and two-species reaction fixtures | Reaction-network assembly and declared feedback ports; stoichiometric conservation and feedback interventions |
| B08 | Extracellular electrodiffusion and tissue barriers / B1-B2 | CORE-009 finite outside accepted; SPEC-009/NUM-010 references and CORE-010 bounded development acceptance complete; stable promotion separate | [Spatial integration](SPATIAL_EXTRACELLULAR.md); barriers, transepithelial references and BETSE full-field comparisons remain later work |
| B09 | Spatial membrane polarization and electric fields / B1-B2 | Planned: current membrane is lumped | Multiple surfaces, potential constraints and local/global field solves; geometry/mesh refinement and gauge checks |
| B10 | Channel/pump spatial redistribution and polarity mechanisms / B5, B7 | Planned; specialized source modules need deeper review | Surface state/transport and explicit polarity laws; conservation on surfaces and field-reversal response |
| B11 | Osmotic pressure, water transport and flow / B2, B4 | Planned | Coupled water/solute/volume state and pressure closure; zero-drive equilibrium, dilution and closed-volume balance |
| B12 | Deformation and electrical/mechanical coupling / B2, B7 | Planned | Geometry-dependent area/capacitance/contact updates with a named mechanics model; force balance and mesh/motion convergence |
| B13 | Tissue geometry, regional profiles, cuts and interventions / B2 | Partial: graph data and timed controls, no spatial tissue | Dimensioned geometry, topology events and targeted controls; cut-boundary accounting and event replay |
| B14 | Heterogeneity and stochastic perturbations / B2 | Partial: deterministic parameter heterogeneity | Explicit stochastic law and ID-based random streams; distributional/refinement tests and restart invariance |
| B15 | Preparation and detailed/reduced execution modes / B1-B2 | Partial: recorded preparation and bounded windows | Separate physical fidelity from solver; capability rejection and reduced-versus-detailed response tests |
| B16 | Parameters, calibration and model comparison / B3 | Partial: BIO-002 offline two-point fit; D107 original-data candidate preparation, not acceptance | [Biological benchmark plan](BETSE_BIOLOGICAL_BENCHMARK_PLAN.md): provenance, permeability discrepancy, uncertainty and independent evaluation; no targets exposed to dynamics |
| B17 | Headless workflows, observations, exports and visualization / B1-B2 | Partial: CLI, manifests, arrays and checkpoints | Spatial observations, scalable output and separate viewer; replay/units/source identity and bounded-I/O checks |

B03 must eventually inventory every selected subtype, not just provide a generic
Hodgkin-Huxley function. B06/B10 must distinguish public configuration support
from dormant or specialized modules. A feature list alone never certifies an
arbitrary combination of those features. Package-version changes require an
explicit inventory revision, not silent movement of the target.

## Staged build order

The [execution architecture](MULTISCALE_EXECUTION_ARCHITECTURE.md) defines the
interfaces that let these capabilities share accounting, scheduling and future
GPU placement. Avoid building a universal plugin system before small assemblies
exercise those interfaces.

| Stage | Bounded deliverable | Exit evidence / connection to existing milestones |
| --- | --- | --- |
| 1: multispecies membrane assembly | SPEC-005/NUM-006/CORE-006 complete within the frozen one-cell panel | [1546 instantaneous checks](../reports/SPEC005_DESIGN_CHECK.md), [14 reference trajectories](../reports/NUM006_REFERENCE.md), and [production acceptance](../reports/CORE006_ACCEPTANCE.md). M1 extension, not a retroactive change to old models or biological/source parity |
| 2: channels and communicating cells | Channel production accepted; SPEC-007/NUM-008 reference gates pass; CORE-008 graph implemented | [Channel guide](VOLTAGE_GATED_MEMBRANE.md), [graph guide](PHYSICAL_IONIC_GRAPH.md), [production acceptance status](../reports/CORE008_ACCEPTANCE.md); complete CPU/replay/cohort evidence remains separate from biology. Does not qualify the source E02 campaign |
| 3: finite environments and tissue | Finite reservoirs, membrane surfaces, fixed 2D geometry and extracellular field operators | Cell/field conservation, spatial/temporal refinement, barrier and polarization tests. M3; no engine-wide 2D restriction |
| 4: coupled chemistry and compartments | General reaction assembly, calcium/ER, energy pools and regulation/channel feedback | Closed-pool tests, interventions and source-specific captures. Can proceed alongside stage 3 after stage 1 |
| 5: water, mechanics and lifecycle | Water/solute transport, appropriate flow/mechanics, topology events, growth and partition laws | Mass/charge/volume and mechanical balances; motion/event and partition checks. M5; no implied organism fitness or inheritance result |
| 6: computational multiscale | Static fine/coarse region coupling and qualified multi-rate updates before adaptive refinement | Detailed-reference response, interface conservation, hidden-history retention and measured work reduction. M6 |
| 7: organ and multi-organ presets | Select a bounded 3D organ function, then couple organ ports and shared transport compartments | Organ-specific measurements, refinement and exchange/function tests. M7/M8; not independent-world batching |

GPU-001 can test a representative qualified CPU workload before stages 6/7;
full BETSE parity is not a prerequisite for a GPU feasibility test. GPU-002 then
separates multi-GPU independent ensembles from domain-decomposed interacting
worlds, with multi-host operation later. These are future implementation gates,
not jobs authorized to launch during this design slice.

The long source-compatible E02 numerical campaign remains unfinished/deferred
with its current checks and budgets. The new physical-model path is independent:
it does not use that deferral to claim source switching/relay coverage. Existing
M1/M1c acceptance requirements remain visible rather than being marked complete.

## Coverage and success criteria

For each concrete mechanism record separately: specified, independently checked,
CPU implemented, source compared, experimentally evaluated, GPU qualified, and
multiscale qualified. Store the reference version, units, regime and known
omissions with each result. "Implemented" never implies all other columns pass.

Source parity uses aligned equations, boundaries and parameters with independent
numerical tolerances. Biological plausibility uses separate measured data and
outcomes. Reduction preserves the response and history relevant to its declared
task, not merely a matching final mean voltage. Parallel implementations retain
those requirements; floating reduction order means cross-device bitwise identity
must not be promised generally.

To claim progress beyond the baseline, report accuracy at a declared fidelity
alongside end-to-end runtime, memory, communication and output costs. Larger cell
counts or a GPU kernel alone do not establish an organ-scale advance.

## Immediate next slice

D106's independent timed-channel audit is closed; the 49 coarse-grid misses
remain. D108 closes the independent substrate-dependent Na/K contact, and D110
[closes the short coupled numerical scope](../reports/NUM011_COUPLED_CLOSEOUT.md).
D111's [named process](KINETIC_PUMP_PROCESS.md) qualification and targeted
regression now pass. D113 implements versioned configuration/model integration;
the [422-test family gate and independent review](../reports/SPEC010_FAMILY_CLOSEOUT.md)
now pass. D116 independently closes [native lifecycle ownership](../reports/REF005B_PUMP_LOOP_CLOSEOUT.md).
D117 prepares [matched short trajectories](BETSE_MATCHED_PUMP_PILOT.md), with
refinement, an independent reference and complete production restart checks.
D118 now [diagnoses its rejection](../reports/REF005C_PILOT_FAILURE_DIAGNOSIS.md):
six energy misses remain, while all refinement groups and restart checks pass.
Preserve the failed capture and prepare a finer native ladder with unchanged
physics/budgets and revised recording bounds. D119 now implements that explicit
amendment with 46 passing preflight checks, exact overlap and reuse of saved
Cells/reference trajectories. Its producer now reports 616,806 comparisons with
zero failures in 501.812 s. D120's independent saved-data audit now passes in
337.048 s; D121 [closes that bounded pilot](../reports/REF005C_PUMP_PILOT_CLOSEOUT.md).
D122 adds the [longer-duration plan](BETSE_PUMP_RELAXATION_PLAN.md), with 35
passing design checks: qualify lossless recording, then separately register a
10 ms extension before relaxation and recovery. That design launched no job.
D123 now implements the offline codec and prepares the bounded, detached
[all-record qualification](../reports/REF005D_CODEC_HANDOFF.md); live observer
parity and matched Cells window/restart checks remain prerequisites. Its full
36-row conversion now passes exactly, with 83.6× smaller storage. D124's
separately implemented decoder/direct-value audit now independently passes;
D125 closes that offline sub-gate and implements live/matched-window checks.
This does not qualify longer integration or bound native retained histories. The
[next-step plan](BETSE_REALISM_AND_NEXT_STEPS.md) also scopes held-open
junction transport and dynamic lifecycle checks, and prepares an original-data
biological benchmark. Source contact is an intermediate gate toward a named
production pump and coupled pump–leak model, not feature completion. Existing
family semantics are preserved through narrowly shared helpers; fourteen v1
initial preparations match the pre-edit archive exactly. The new family is a
development extension with bounded acceptance, not full release promotion,
and no GPU claim. Long work stays detached and user-polled;
no automatic audit or follow-up. The passive history below does not reopen jobs.

Current external gate: REF-003d v2's bounded trajectory is independently
[closed](../reports/REF003D_CLOSEOUT.md), and v1's rejection remains preserved.
D072's [phase/control design](BETSE_INTERVENTION_PLAN.md) now passes
[38 focused source/control checks](../reports/REF003E_INTERVENTION_DESIGN.md).
BETSE events are SIM-only and use smooth additive pulses, while REF-003d used
INIT. D074's [profile/dispatch preparation](BETSE_PROFILE_BRIDGE_PREFLIGHT.md) now
passes. D075 now supplies the [narrow full-loop pilot](BETSE_FULL_LOOP_BRIDGE.md)
and its detached launch boundary. The capture and D076's independent audit /
165-test regression closeout now pass and were user-reviewed. D077's separately
approved 72-run expansion also passed capture controls and was user-reviewed.
D078's independent arithmetic audit / 433-test joint closeout now passes and
was user-reviewed, without a model rerun. D079's
[held-input compiler/design](BETSE_HELD_INTERVENTION.md) specifies four conditions
and a proposed eight-native / 24-Cells matched-constant pilot. D080's
[actual nonzero SIM preparation/dispatch](BETSE_NONZERO_DISPATCH_PREFLIGHT.md)
now passes. D081 implements [control-aware capture/checking](BETSE_HELD_RESPONSE_PILOT.md)
with prospective resources, observed/unobserved native partners and fixed-input
Cells subdivisions. Its completed capture remains numerically rejected; D082's
[offline failure closeout](../runs/ref-003e1-response-audit-2026-09-13/audit-01/completion.json)
now verifies that rejection and was user-reviewed. D083 passes the separate
[finer-input application gate](BETSE_REFINED_DISPATCH_PREFLIGHT.md) before a new
response. Keep the 1 ms horizon and original criteria. D084 implements that
response panel; its detached 114-test software completion passes and was
user-reviewed. Freeze prelaunch and launch the separately requested capture.
No capture was launched by the software job. Return immediately and await
user status; no automatic follow-up audit or regression.
One fixed native timestep/hold does not qualify native or forcing convergence.
Known coarse-baseline discrepancies must remain failures, not tuned-away results.
No automatic expansion or inference of a response from dispatch-only checks.
See the [current reference plan](BETSE_REFERENCE_PLAN.md).

The shared-bath error is also a multiscale design lesson: validate inventories
and interface transfers across compartments, not just cell-wise or mean voltage
agreement. Keep source-specific clocks and conversions in adapters. Different
solvers and future CPU/GPU paths need their own accuracy/resource qualification;
matching timesteps or promising cross-device bitwise identity is insufficient.
Also separate an input law, its hold/sampling policy, the solver grid and the
observation side. Existing numeric controls cover the first held-drive design;
continuously stage-evaluated controls would need a distinct general contract.
Native event labels require explicit input-time conversion, not a hidden change
to production timing. The implementation history below does not authorize
automatic follow-up jobs.

The [SPEC-005 multispecies design/reference](MULTISPECIES_MEMBRANE_SPEC.md)
is now [complete](../reports/SPEC005_DESIGN_CHECK.md), on CPU.
[NUM-006's bounded trajectory qualification](../reports/NUM006_REFERENCE.md)
and [CORE-006's CPU/JAX production acceptance](../reports/CORE006_ACCEPTANCE.md)
also pass. [SPEC-006](VOLTAGE_GATED_CHANNEL_SPEC.md) now completes the bounded
Kv1.5-style m/h design and independent reference. **NUM-007** now qualifies
[bounded coupled trajectories](../reports/NUM007_REFERENCE.md): fourteen cases,
0.5 ms RK4/cubic with passing refinement, complete histories and gate-domain
checks. Coarse failures remain recorded. **CORE-007** now completes the
[production channel](VOLTAGE_GATED_MEMBRANE.md): a new identity, numeric gate/channel
axes and complete CPU/JAX/replay/cohort acceptance. Accepted 0.11.0 was preserved
before edits; no earlier timestep limit is changed. SPEC-007 now specifies and
independently checks physical ionic graph composition, including one/disconnected
reductions, reciprocal two-cell exchange and a three-cell star. NUM-008 now
qualifies twelve short coupled cases with independent methods, component reductions,
2 ms RK4/cubic and passing 1 ms refinement. **CORE-008 now implements the
production graph**, preserving accepted 0.12.0 and its source contexts, mapping
the reference onto numeric axes and checking full CPU/JAX restart/branch/cohort
behavior in [separate acceptance](../reports/CORE008_ACCEPTANCE.md).
The 2 ms selection is not a bound for arbitrary graph sizes or couplings. Prescribed
isolated-gate voltage remains distinct from whole-cell voltage clamp, which
requires an electrode/charge closure. D055 / [SPEC-008](FINITE_EXTRACELLULAR_SPEC.md)
now supplies that bounded first step toward B08: a finite well-mixed outside,
not yet a mesh. Explicit outside amounts and opposing capacitor charge,
maintained-bath reduction, inverse-volume feedback and full ionic free-energy
checks pass in the [independent reference](../reports/SPEC008_DESIGN_CHECK.md).
NUM-009 v2 now passes the fourteen-case numerical reference and saved-data audit
with explicit inventories, 1 ms RK4/cubic and passing 0.5 ms refinement. Its
[closeout](../reports/NUM009_REFERENCE_V2.md) passes all 3466 regression tests;
CORE-009 now implements a distinct finite-outside family and passes its
[formal CPU/JAX execution gate](../reports/CORE009_ACCEPTANCE.md).
D059 / [SPEC-009](SPATIAL_EXTRACELLULAR_SPEC.md) now supplies spatial inventory,
owned electrodiffusive faces and capacitance/current closure at the independent
instantaneous-reference level. [NUM-010](../reports/NUM010_REFERENCE.md) now
qualifies fourteen short cases, analytic salt relaxation and one 8/16/32-volume
line refinement path. Its 0.125 ms RK4/cubic step has passing 0.0625 ms refinement;
coarse-step failures remain recorded. There is no inherited 1 ms spatial bound.
Full-state reference restarts and independent saved-data replay pass. The new
[passive spatial implementation](SPATIAL_EXTRACELLULAR.md) uses separate array axes
and a bounded same-stage CPU field solver; its full captured production/audit
acceptance remains open. Tissue barriers and BETSE parity remain unimplemented;
BIO-002 fitting and the long E02 campaign stay closed/deferred.

## Reviewed byte identities

Hashes identify the inspected source files at the pinned commit; they do not
replace later executable source captures or reproduce upstream code here.

| Source | SHA-256 |
| --- | --- |
| B1 | `9c9c95d913fbbbf8e0db4afe6f38299dbf55bd8c164bade13b34a64b20fddb87` |
| B2 | `7ed5a32f9fc256c541db63090aeed6d0207bf706d2847b27269d6bc8c9e85415` |
| B3 | `2dd1322fdab1dff7d7b9b1d90894d27e5f8357bf37b30050c2ae8c10e91492b7` |
| B4 | `37e99f7af5030127d203bc7ed674f53796149410ab15c80d2e8aca45838413ad` |
| B5 | `b857d8d125962ef50cc48a17c53044a20b09e2e0141f046521d7909d8df23ffb` |
| B6 | `14a989709bd22558f557b7177bd7728c8bf02b5711e0306a3673833812a848f8` |
