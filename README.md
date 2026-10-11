# Cells

![Cells logo: three connected cells beside the Cells wordmark.](docs/assets/cells-logo.png)

Cells is an early-stage multiscale simulator for investigating how cellular state,
communication, and tissue organisation affect memory, inheritance, and adaptation.
The long-term goal is a whole-organ model and later multiple interacting organs.
The simulation stack is **Python and JAX**, with independent CPU references and
local NVIDIA GPU execution. See [Progress](PROGRESS.md) for current verification
status and [Scientific basis](docs/SCIENTIFIC_BASIS.md) for the research background.

## Current functionality

![Cells today: bioelectricity, calcium signalling and protein assembly. A shared work queue distributes independent simulations among GPU workers and collects results and checkpoints. CPU and L4 are verified locally; Jupiter qualification is planned.](docs/assets/cells-current.png)

- **Electrical cells and tissues:** ion transport, membrane voltage, pumps,
  channels, gap junctions and extracellular fields in selected model families.
- **Cell chemistry:** calcium and IP3 signalling, internal compartments and
  chemical reactions.
- **Protein assembly:** stochastic cage formation, finite material pools,
  breakable bonds and experimental coupling to cell models.
- **Repeatable experiments:** checkpoints, restart, branching and independent
  simulation ensembles, with CPU/L4 comparisons and conservation checks.

For GPU ensembles, workers take batches of independent simulations from a shared
queue and save their results and checkpoints. The four-worker illustration shows
that execution design. Numerical qualification has used CPUs and one L4; Jupiter
execution remains to be qualified. Distributing one interacting tissue across
multiple GPUs requires further development. See the
[GPU and ensemble guide](docs/GPU_ENSEMBLES.md).

Verified results apply to the declared models and test conditions. Selected
BETSE comparisons pass; full BETSE equivalence and biological validation remain
unfinished. The [assembly-to-cell coupling](docs/CAPSID_ASSEMBLY.md) is an
experimental modelling hypothesis.

## In progress

- Combining spatial fields, active membrane transport and dynamic junctions in
  BETSE comparisons.
- Extending verification of the integrated cell, tissue and assembly models.
- Bringing new components into the shared configuration, checkpoint and ensemble
  workflows.

## Planned

![Planned Cells development: broader BETSE channel and transport coverage; integrated assembly, energy and mechanics; Jupiter scaling from four to sixteen GPUs; and tissue-to-organ models.](docs/assets/cells-future.png)

The next directions are broader BETSE coverage, richer cell physiology including
water and mechanics, and Jupiter qualification from four to sixteen GPUs.
Experimental calibration and organ models are longer-term goals. The organ
illustration is schematic; it does not select a particular organ to build first.
Detailed scope and priorities are recorded in [Progress](PROGRESS.md) and the
[Roadmap](docs/ROADMAP.md).

## Development history

Earlier milestones, qualification results and retained failures are recorded in
[Development history](docs/DEVELOPMENT_HISTORY.md). See [Progress](PROGRESS.md)
for current status.

## Run with bounded recording memory

```bash
taskset -c 0-3 .venv/bin/python -m cells windowed run configs/source_pair_baseline.json --window-steps 256 --recording observations --checkpoint-at 5 --output runs/my-windowed-pair
taskset -c 0-3 .venv/bin/python -m cells windowed resume runs/my-windowed-pair/snapshots/step-0000000500 --window-steps 128 --recording checkpoints --output runs/my-windowed-replay
```

Choose `full`, `observations` (default), or `checkpoints`; every configured
numerical and observation check still runs. Checkpoints always contain complete
state, including diagnostic history. Change window size/recording on resume
without changing physics. Each output must be new. See the
[window guide](docs/WINDOWED_EXECUTION.md) for the Python API, chunk format,
resource bounds and branch commands. Ordinary scalar and batch commands remain
available with their full-trace behavior.

For independent cohorts, checkpoint cadence counts execution rounds, not a shared
biological time:

```bash
taskset -c 0-3 .venv/bin/python -m cells batch windowed run configs/batch_source_pair.json --window-steps 16 --recording observations --checkpoint-every-windows 2 --output runs/my-windowed-worlds
taskset -c 0-3 .venv/bin/python -m cells batch windowed resume runs/my-windowed-worlds/snapshots/round-0000000002 --window-steps 32 --recording checkpoints --output runs/my-windowed-worlds-replay
```

Initial/final checkpoints always contain the complete cohort, including finished
worlds. See the [cohort window guide](docs/WINDOWED_WORLDS.md) for branch commands,
independent clocks, memory guards and incremental output.

## Run independent worlds

```bash
taskset -c 0-3 .venv/bin/python -m cells batch run configs/batch_source_pair.json --output runs/my-worlds --checkpoint-at 0.5
taskset -c 0-3 .venv/bin/python -m cells batch resume runs/my-worlds/snapshots/checkpoint-000000 --output runs/my-worlds-replayed
taskset -c 0-3 .venv/bin/python -m cells batch branch runs/my-worlds/snapshots/checkpoint-000000 configs/batch_source_pair_branch.json --output runs/my-worlds-branched
```

These are two independent source-pair experiments, not four communicating cells
or two interacting organs. Each world retains its own clock and complete state.
The branch changes only world 101's future miRNA control. Every output must be
new; see the [batch guide](docs/INDEPENDENT_WORLDS.md) for schema, numerical and
resource restrictions, individual-world access and profiling commands.

## Run a source-compatible pair

```bash
taskset -c 0-3 .venv/bin/python -m cells run configs/source_pair_baseline.json --output runs/my-source-pair --checkpoint-at 5
taskset -c 0-3 .venv/bin/python -m cells resume runs/my-source-pair/snapshots/step-000500 --output runs/my-source-replay
taskset -c 0-3 .venv/bin/python -m cells branch runs/my-source-pair/snapshots/step-000500 configs/source_pair_branch.json --output runs/my-source-branch
```

The branch independently inhibits/restores miRNA transfer and one cell's pump;
ionic contact remains active. Full primary state, fixed context, anchors and
exchange histories survive restart. Each output must be new. See the
[guide](docs/SOURCE_EMT_PAIR.md) for units, supported controls and remaining scope.

## Run a physical gated pair

```bash
taskset -c 0-3 .venv/bin/python -m cells run configs/bioelectric_pair_baseline.json --output runs/my-physical-pair --checkpoint-at 6
taskset -c 0-3 .venv/bin/python -m cells resume runs/my-physical-pair/snapshots/step-006000 --output runs/my-pair-replay
taskset -c 0-3 .venv/bin/python -m cells branch runs/my-physical-pair/snapshots/step-006000 configs/bioelectric_pair_branch.json --output runs/my-pair-branch
```

The gate keeps evolving during a transport block; restart retains it and all
exchange history. This model uses the independently qualified 1 ms step, not
the single-cell 5 ms bound. See the [guide](docs/BIOELECTRIC_PAIR.md) for data,
controls, accounting, numerical limits and remaining scope. Every output must be new.

## Run one physical cell

```bash
taskset -c 0-3 .venv/bin/python -m cells run configs/bioelectric_baseline.json --output runs/my-physical-cell --checkpoint-at 6
taskset -c 0-3 .venv/bin/python -m cells resume runs/my-physical-cell/snapshots/step-001200 --output runs/my-physical-replay
taskset -c 0-3 .venv/bin/python -m cells branch runs/my-physical-cell/snapshots/step-001200 configs/bioelectric_branch.json --output runs/my-physical-branch
```

This runs 10 seconds, not automatic equilibration. The branch independently
blocks/releases Na leakage and pumping. Every destination must be new; accounting
and electrical anchors survive restart. See the [guide](docs/BIOELECTRIC_CELL.md)
for units, controls, outputs, numerical limits, and remaining scope.

## Run reactions and transport

Start with one reactive cell, then a three-cell chain using the same model:

```bash
.venv/bin/python -m cells run configs/reaction_transport_single.json --output runs/my-reaction-cell
.venv/bin/python -m cells run configs/reaction_transport_chain.json --output runs/my-reaction-chain --checkpoint-at 6
.venv/bin/python -m cells branch runs/my-reaction-chain/snapshots/step-000122 configs/reaction_transport_release.json --output runs/my-reaction-release
```

Two synthetic species interconvert locally and exchange through declared contacts.
Cell count, volumes, rates, species names, topology, and contact openings are data.
The release branch closes both contacts at six seconds: transport stops while
local reactions continue. Total A+B is conserved; each species total need not be.
The [composition contract](docs/REACTION_TRANSPORT.md) defines the equations,
axes, units, numerical limits, and model boundaries. It is not a general reaction
network language or a connection to the source-scaled EMT model.
Every output directory must be new. For bounded CPU use on this host, prefix
commands with `taskset -c 0-3`.

## Run two contacting cells

From this directory, using the installed CPU environment:

```bash
.venv/bin/python -m cells run configs/pair_exchange_active.json --output runs/my-pair --checkpoint-at 6
.venv/bin/python -m cells resume runs/my-pair/snapshots/step-000120 --output runs/my-pair-replay
.venv/bin/python -m cells branch runs/my-pair/snapshots/step-000120 configs/pair_exchange_release.json --output runs/my-pair-release
```

The cells start with [8, 0] fmol in unequal volumes [1, 3] pL. Passive transport
moves them toward equal concentration while preserving total amount. The release
branch closes the contact at six seconds; the physical connection remains present
but further exchange stops. The [contact contract](docs/PASSIVE_CONTACT.md) describes
units, controls, edge state, numerical limits, and the separate source-coupling gate.
Every output directory must be new. For bounded CPU use on this host, prefix
commands with `taskset -c 0-3`.

## Run a regulatory cell

From this directory, using the installed CPU environment:

```bash
.venv/bin/python -m cells run configs/emt_isolated_e.json --output runs/my-emt-e --checkpoint-at 5000
.venv/bin/python -m cells run configs/emt_isolated_m.json --output runs/my-emt-m
.venv/bin/python -m cells resume runs/my-emt-e/snapshots/step-050000 --output runs/my-emt-replay
```

The two configurations differ only in initial regulatory state. Each runs to
10000 source-time units with fixed Snail 72; the coordinates are source-scaled,
not calibrated physical concentrations or seconds. Outputs include the three
primary trajectories, derived binding complexes, observer labels, and provenance.
Read the [reference contract](docs/EMT_REFERENCE.md) for the model's limits.

## Run the synthetic pulse fixture

From this directory, using the already installed local environment:

```bash
.venv/bin/python -m cells run configs/single_cell_pulse.json --output runs/my-first-cell --checkpoint-at 6
```

This simulates 12 seconds with an input pulse from 2.03 to 5.07 seconds. It writes
the resolved configuration, accepted/observed trajectories, a summary, hashes,
timings, and complete checkpoints. The output directory must not already exist.

Continue unchanged, or change only future inputs from the same six-second state:

```bash
.venv/bin/python -m cells resume runs/my-first-cell/snapshots/step-000122 --output runs/my-replay
.venv/bin/python -m cells branch runs/my-first-cell/snapshots/step-000122 configs/single_cell_rechallenge.json --output runs/my-rechallenge
```

The snapshot name above is for the shipped configuration; other grids list their
snapshot paths in the run manifest. Rechallenge adds a 0.5 fmol/s source at six
seconds. It changes the future without modifying the parent or its prior inputs.

For a fresh checkout, use Python 3.13 (tested with 3.13.5):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --no-cache-dir -r requirements-lock.txt
.venv/bin/python -m pip install --no-build-isolation --no-deps -e .
```

The lock is CPU-only. Supported model families can also select GPU execution;
see the [GPU and ensemble guide](docs/GPU_ENSEMBLES.md) for the separate CUDA
environment and model-specific requirements.

## Verify

```bash
.venv/bin/python scripts/test_spatial_extracellular_build.py --output reports/my-test-matrix
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
```

Tests use temporary directories and retained numerical reference fixtures; neither
network nor the upstream checkout is needed. The matrix explicitly separates
current production from ten NUM-005 modules under preserved 0.10.0, three
SPEC-006/NUM-007 modules under preserved 0.11.0 and three physical-graph reference
modules under preserved 0.12.0, plus six finite-outside reference/test-context
modules under preserved 0.13.0 and two NUM-010 reference modules under preserved
0.14.0. All three earlier drivers and the original reference guards remain unchanged.
It explicitly retains the original 13 prospective NUM-009 v1 complete-session
tests as unexecuted (that scientific run stopped), runs their maintained v2
replacement, and still runs v1 preflight/stopped-evidence tests. No skip is
counted as passing acceptance. The matrix
uses CPUs 0–3 and an independent temporary evidence copy (currently about 7.5 GB);
the historical confinement/source guards stay intact. See the
[multispecies test-context explanation](docs/MULTISPECIES_MEMBRANE.md#run-resume-and-qualify).
Generated `runs/` are local and excluded from Git. Earlier window/clock acceptance, exact seven-model scalar and cohort
regressions, preserved 0.9.0 replay and memory/cost measurements are in
[CORE-005b acceptance](reports/CORE005B_ACCEPTANCE.md). The preceding scalar-window
release is in [CORE-005a acceptance](reports/CORE005A_ACCEPTANCE.md). The preceding batch
implementation/profile is in [CORE-004 acceptance](reports/CORE004_ACCEPTANCE.md).
The preceding source-model release is in
[MODEL-005 acceptance](reports/MODEL005_ACCEPTANCE.md). Earlier physical-pair
evidence is in [MODEL-004 acceptance](reports/MODEL004_ACCEPTANCE.md). Physical-cell
evidence is in [MODEL-003 acceptance](reports/MODEL003_ACCEPTANCE.md); composition
evidence is in [CORE-003 acceptance](reports/CORE003_ACCEPTANCE.md).
The subsequent [SPEC-002 design gate](reports/SPEC002_DESIGN_CHECK.md) adds
709 instantaneous contact/source checks. [NUM-003 qualification](reports/NUM003_REFERENCE.md)
now passes all 20 independent physical-pair cases at RK4/1 ms with cubic
observations. Those design/reference stages left 0.5.0 unchanged; MODEL-004 now
implements the qualified physical pair (670 release tests). SPEC-003 adds the
complete source-compatible design/native RHS panel and 65 tests. NUM-004 adds
48 numerical, native-audit and artifact/protocol tests. MODEL-005 adds 69 production
engineering and CLI checks. CORE-004 adds 43 batch unit tests and one fresh-process
CLI case. CORE-005a adds 86 window/clock/recording/replay checks; CORE-005b adds
75 cohort-window checks. That 0.10.0 release suite passed 1057 tests.
Pair acceptance commands are in [M1c-a acceptance](reports/M1C_A_ACCEPTANCE.md);
source capture and regulatory reruns are in [M1b acceptance](reports/M1B_ACCEPTANCE.md).

Snapshots deliberately require matching source/runtime identity. Old 0.1.0,
0.2.0, 0.3.0, 0.4.0, 0.5.0, 0.6.0, 0.7.0, 0.8.0, 0.9.0 and 0.10.0 runs are preserved with archived source bundles. See the
[0.10.0 preservation receipt](reports/core-006-preservation.json),
[0.9.0 preservation record](reports/CORE005B_ACCEPTANCE.md#preserved-source-and-checkpoints),
[0.5.0 preservation instructions](reports/MODEL004_ACCEPTANCE.md#version-preservation)
and [earlier versions](reports/M1C_A_ACCEPTANCE.md#previous-model-regression-and-preserved-versions)
to inspect them. They are not silently migrated into this version.

## Start here

| Document | Purpose |
| --- | --- |
| [Finite extracellular production guide](docs/FINITE_EXTRACELLULAR.md) | CORE-009: explicit outside inventories, shared feedback, independent capacities and a runnable one-cell example |
| [Spatial extracellular contract](docs/SPATIAL_EXTRACELLULAR_SPEC.md) | SPEC-009: membrane-free bulk volumes, owned electrodiffusive faces, capacitor/current closure and future sparse field solves |
| [Spatial numerical qualification](docs/SPATIAL_EXTRACELLULAR_NUMERICS.md) | NUM-010: frozen short trajectories, independent fields/methods, temporal/spatial refinement, complete-state restart and read-only replay |
| [Spatial numerical result](reports/NUM010_REFERENCE.md) | Fourteen-case reference/audit, 0.125 ms plus 0.0625 ms refinement, analytic grid checks and retained coarse failures |
| [Spatial design/reference result](reports/SPEC009_DESIGN_CHECK.md) | Eight synthetic definitions, independent high-precision arithmetic and explicit limits before spatial trajectories |
| [Finite extracellular production acceptance](reports/CORE009_ACCEPTANCE.md) | Fourteen frozen cases, complete replay/accounting, independent worlds, preserved evidence and release status |
| [Finite extracellular-compartment contract](docs/FINITE_EXTRACELLULAR_SPEC.md) | SPEC-008: real outside inventories, capacitor countercharge, closed ionic energy and future shared reduction |
| [Finite extracellular design checks](reports/SPEC008_DESIGN_CHECK.md) | Nine synthetic cases, independent Decimal/reference reductions, correction history and unchanged production |
| [Finite extracellular numerical amendment](docs/FINITE_EXTRACELLULAR_NUMERICS_V2.md) | NUM-009 v2: explicit inventories, conservation-tangent reference linearization and unchanged acceptance gates |
| [Finite extracellular numerical results](reports/NUM009_REFERENCE_V2.md) | Fourteen cases, 1 ms / 0.5 ms refinement, depletion, saved-data audit and production boundary |
| [Original finite-outside protocol](docs/FINITE_EXTRACELLULAR_NUMERICS.md) | Immutable v1 coordinates, cases and numerical/accounting gates |
| [Original stopped attempt](reports/NUM009_REFERENCE.md) | Retained preflight correction and exact-blocking failure; not reclassified as passing |
| [Physical ionic graph production guide](docs/PHYSICAL_IONIC_GRAPH.md) | New numeric model family, state ownership, runnable three-cell example and prospective CPU acceptance contract |
| [Physical ionic graph production acceptance](reports/CORE008_ACCEPTANCE.md) | Targeted tests, preserved baseline, compiled/eager/replay/cohort evidence and release status |
| [Physical ionic graph contract](docs/PHYSICAL_IONIC_GRAPH_SPEC.md) | SPEC-007: shared bath, explicit charge closure, one-owned edge transfer and independent state axes |
| [Physical ionic graph design checks](reports/SPEC007_DESIGN_CHECK.md) | Frozen instantaneous pair/star reductions, Decimal arithmetic, conservation, history and preservation evidence |
| [Physical ionic graph numerical protocol](docs/PHYSICAL_IONIC_GRAPH_NUMERICS.md) | NUM-008 frozen cases, common-stage control/observation rules, independent methods, refinement and resource caps |
| [Physical ionic graph numerical result](reports/NUM008_REFERENCE.md) | Twelve short cases, 2 ms RK4/cubic with 1 ms refinement, complete history/energy checks, component reductions and saved-data audit |
| [Pilot closeout](reports/BIO003_PILOT_CLOSEOUT.md) | Completed descriptive comparison and supplementary review; biological validation remains unestablished |
| [BETSE capability roadmap](docs/BETSE_CAPABILITY_ROADMAP.md) | Pinned 17-family scientific target, current gaps, staged CPU build and later GPU qualification |
| [Multiscale execution architecture](docs/MULTISCALE_EXECUTION_ARCHITECTURE.md) | Operator ownership, fine/coarse coupling, parallel GPU partitions, coupled clocks and checkpoint requirements |
| [Multispecies membrane contract](docs/MULTISPECIES_MEMBRANE_SPEC.md) | SPEC-005 schema, species/charge ownership, equations, boundary support and frozen synthetic inputs |
| [Multispecies reference result](reports/SPEC005_DESIGN_CHECK.md) | Design-stage evidence: 1,546 instantaneous checks and 352 targeted tests; production unchanged |
| [Multispecies numerical qualification](reports/NUM006_REFERENCE.md) | 14 frozen trajectory cases, independent/refined methods, bounded RK4/cubic candidate and 446 targeted tests; production acceptance is next |
| [Multispecies numerical protocol](docs/MULTISPECIES_NUMERICS.md) | Frozen error/resource limits, complete event handling, accounting and method-selection rule |
| [Multispecies build sequence](docs/MULTISPECIES_MEMBRANE_NEXT.md) | Original stage-1 scope and reference gates |
| [Multispecies production guide](docs/MULTISPECIES_MEMBRANE.md) | New 0.11.0 species/charge/role schema, numerical checks, complete replay and explicit test contexts |
| [Multispecies production acceptance](reports/CORE006_ACCEPTANCE.md) | Frozen-panel eager/JIT and readout checks, exact replay/regressions, retained attempts and 2565 passing tests |
| [First state-bearing channel contract](docs/VOLTAGE_GATED_CHANNEL_SPEC.md) | SPEC-006: Kv1.5-style activation/inactivation, separate mechanism ownership, exact gate reference and coupled/GPU boundaries |
| [Channel design/reference evidence](reports/SPEC006_DESIGN_CHECK.md) | 7528 checks, seven analytic gate protocols, instantaneous ionic accounting and unchanged production |
| [Coupled channel numerical protocol](docs/VOLTAGE_GATED_NUMERICS.md) | NUM-007 frozen preparations, accuracy/resource limits, full gate/channel histories and candidate refinement rule |
| [Coupled channel numerical result](reports/NUM007_REFERENCE.md) | 14 cases/98 attempts, selected 0.5 ms RK4/cubic, retained coarse failures and source-bound dense replay audit |
| [First biological benchmark](docs/BIOLOGICAL_BENCHMARK_001.md) | One-cell endpoint pilot, retrospective fit/evaluation split, measurement-boundary gaps and evidence criteria |
| [Experimental data card](data/biology/bonzanni2020_rptec_v1/README.md) | RPTEC source figures, recipes, approximate voltages, unknown SEM and quarantined input conflicts |
| [Conditioned voltage reference](docs/CONDITIONED_VOLTAGE_REFERENCE.md) | Fixed endpoint approximation, two-coefficient equation and reading-bound propagation, separate from production cells |
| [First voltage prediction](reports/BIO002_CONDITIONED_VOLTAGE.md) | C1/C2-only fit, C3 result, comparison plot and 63 targeted checks; no biological acceptance claim |
| [Windowed cohort guide](docs/WINDOWED_WORLDS.md) | Bounded independent rounds, prepared execution, complete cohort restart, recording and failure semantics |
| [CORE-005b acceptance](reports/CORE005B_ACCEPTANCE.md) | 1057 tests, exact seven-model cohort recording/replay, unchanged regressions, archived 0.9.0 and isolated CPU trade-offs |
| [Bounded-window guide](docs/WINDOWED_EXECUTION.md) | Exact clock/storage partitioning, selectable recording, complete restart, incremental artifacts and scope |
| [CORE-005a acceptance](reports/CORE005A_ACCEPTANCE.md) | 982 tests, all accepted scalar/cohort arrays unchanged, archived 0.8.0 replay and measured memory/overhead trade-offs |
| [Independent-world guide](docs/INDEPENDENT_WORLDS.md) | Batch definitions, world-local clocks/identity, conservative mapping, cohort replay and resource limits |
| [CORE-004 acceptance](reports/CORE004_ACCEPTANCE.md) | 896 tests, 44 accepted batch-world runs, all 78 prior scalar trajectories unchanged, archived 0.7.0 and bounded CPU profiles |
| [Physical-pair guide](docs/BIOELECTRIC_PAIR.md) | Runnable selective gated pair, independent controls, complete state/replay, and numerical limits |
| [MODEL-004 acceptance](reports/MODEL004_ACCEPTANCE.md) | 670 tests, 20 frozen physical-pair cases, exact replay, five-model regressions and preserved 0.5.0 |
| [Physical-cell guide](docs/BIOELECTRIC_CELL.md) | Runnable membrane/bath model, controls, outputs, replay, and limitations |
| [Progress](PROGRESS.md) | Current milestone, task status, dependencies, and activity log |
| [Scientific basis](docs/SCIENTIFIC_BASIS.md) | Source material, reviewed findings, hypotheses, and research updates |
| [Architecture](docs/ARCHITECTURE.md) | Python/JAX design, state, coupling, numerical execution, and outputs |
| [Engineering gate](docs/ENGINEERING_GATE.md) | Completed bounded composition build and separate source-correspondence gate |
| [BETSE/software review](docs/BETSE_DESIGN_REVIEW.md) | Primary sources, experimental evidence and limits, accepted architecture lessons, and reference candidates |
| [Bioelectric cell specification](docs/BIOELECTRIC_CELL_SPEC.md) | Physical equations, membrane/bath interfaces, units, charge/energy closure, controls, and original acceptance sequence |
| [Bioelectric design checks](reports/BIOELECTRIC_DESIGN_CHECK.md) | 74 instantaneous equation checks, reproducible calculator and receipt; not trajectory or source validation |
| [Bioelectric numerical contract](docs/BIOELECTRIC_NUMERICS.md) | Independent CPU reference, bounded RK4/cubic-observation candidate, numerical domain, and multiscale implications |
| [NUM-002 qualification](reports/NUM002_REFERENCE.md) | 18 reference cases, solver/refinement and accounting checks, retained interpolation failures, and 346 passing tests; not a production model |
| [MODEL-003 acceptance](reports/MODEL003_ACCEPTANCE.md) | 447 tests, pinned production comparisons, complete replay/branches, four-model regressions, and source preservation |
| [Stateful selective contact](docs/SELECTIVE_CONTACT_SPEC.md) | Two-cell physical equations, gate/transfer contract and original 20-case qualification requirements; now implemented in MODEL-004 |
| [Source-coupling map](docs/SOURCE_COUPLING_MAP.md) | Native contact probes, units/signs/gating/charge approximations, and the distinct source-compatible acceptance gate |
| [Source-compatible pair specification](docs/SOURCE_EMT_PAIR_SPEC.md) | Complete ionic/regulatory state, fixed and derived roles, source equations/controls, prepared inputs and frozen future numerical gate |
| [SPEC-003 evidence](reports/SPEC003_DESIGN_CHECK.md) | 3192 instantaneous checks against 17 native settings, state/control negative tests and unchanged 0.6.0 production; no coupled trajectories |
| [Source-compatible numerics](docs/SOURCE_EMT_PAIR_NUMERICS.md) | Qualified nominal-clock RK4/cubic candidate, typed history, event semantics and native-clock distinction |
| [NUM-004 qualification](reports/NUM004_REFERENCE.md) | 14 independent cases, 44 native paths, retained release-timing failure and passing refinement, 783 tests; production unchanged |
| [Source-compatible pair guide](docs/SOURCE_EMT_PAIR.md) | Runnable nominal ionic/regulatory pair, independent routes, complete history, exact replay and limitations |
| [MODEL-005 acceptance](reports/MODEL005_ACCEPTANCE.md) | 852 tests, 14 frozen cases plus replay/branch, six-model regressions and preserved 0.6.0 |
| [E02-SW1 protocol](docs/E02_SWITCHING_PROTOCOL.md) | SPEC-004: fresh preparation, two-neighbour switching and 12 controls, fixed observers and source-reproduction boundaries; independent reference status in Progress, not production/native long reproduction |
| [E02-SW1 numerical plan](docs/E02_SWITCHING_NUMERICS.md) | Prospective NUM-005 graph composition, long-time references, bounded candidate selection and full preparation sensitivity checks |
| [SPEC-004 design evidence](reports/SPEC004_PROTOCOL_CHECK.md) | Frozen protocol/inventory checks and unchanged 0.10.0 production; no prepared outputs, graph model or long trajectories |
| [Independent graph reference](docs/SOURCE_EMT_GRAPH_REFERENCE.md) | NUM-005a: source-coordinate cell/edge composition and complete reference state, native derivatives and pair reduction; no integrator or production model |
| [NUM-005a acceptance](reports/NUM005A_REFERENCE.md) | 45 native inputs, 18,499 arithmetic/structural checks, 118 new tests and retained adapter failure; preparation and long-time qualification remain |
| [Bounded preparation reference](docs/SOURCE_PREPARATION_REFERENCE.md) | NUM-005b: independent live implicit integration, chunked dense-state evidence, preparation qualification and strict publication boundaries |
| [NUM-005b preparation evidence](reports/NUM005B_PREPARATION.md) | Six 500-unit trajectories, cross-method agreement, complete hash-pinned E/M packets, remaining ionic drift and independent artifact audit |
| [Long fixed-graph reference paths](docs/SOURCE_GRAPH_PATHS_REFERENCE.md) | NUM-005c1: immutable prepared-state imports, lossless bounded evidence and full-panel implicit references/readouts; candidate qualification remains separate |
| [NUM-005c1 long-reference session](reports/NUM005C1_LONG_REFERENCE.md) | Eight qualified conditions, retained one-hour resource stop and exact unfinished inventory; no full-panel or production claim |
| [A2 amended reference policy](docs/E02_REFERENCE_POLICY_A2.md) | D036: explicit mixed-setting acceptance, immutable per-case reference manifests, bounded remaining controls and independent auditing |
| [NUM-005c1 A2 panel evidence](reports/NUM005C1_A2_REFERENCE_PANEL.md) | All 14 amended-policy reference conditions/observers audited; original failure retained, production and candidate qualification still separate |
| [Bounded candidate engineering](docs/E02_CANDIDATE_ENGINEERING.md) | NUM-005c2a: complete accepted RK4 carries, checked curves, bounded reference comparison and twelve short resource profiles |
| [Candidate engineering evidence](reports/NUM005C2A_CANDIDATE_ENGINEERING.md) | Exact window/restart evidence and short-prefix accuracy pass; complete-runtime/storage estimates identify work before the long study |
| [Cached diagnostic contract](docs/E02_DIAGNOSTIC_OPTIMIZATION.md) | NUM-005c2b: static-cache isolation, bounded observation-axis batching, frozen scalar equivalence and full retained evidence |
| [Diagnostic optimization evidence](reports/NUM005C2B_DIAGNOSTIC_OPTIMIZATION.md) | Twelve matched short profiles, exact numerical/readout evidence, expanded audit and measured complete-path speed with remaining resource gates |
| [Compact-evidence proposal](docs/E02_COMPACT_EVIDENCE_DESIGN.md) | D038 output-policy options and requirements; D039 implements a selected lossless prototype, not a compact long-study policy |
| [Lossless recording contract](docs/E02_LOSSLESS_EVIDENCE.md) | NUM-005c2c: exact full/basis codecs, complete committed checkpoints, fail-closed bounded readers and unchanged numerical identity |
| [Lossless recording evidence](reports/NUM005C2C_LOSSLESS_EVIDENCE.md) | Twelve short profiles and independent reconstruction audit; exact evidence, smaller storage, unchanged runtime and remaining long-study gates |
| [Reference-backed comparison contract](docs/E02_COMPARISON_RECORDING.md) | NUM-005c2d: lossless sampled-state reconstruction, pinned dependencies, explicit reader/restart API and unchanged commit boundary |
| [Reference-backed comparison evidence](reports/NUM005C2D_COMPARISON_RECORDING.md) | Implementation, short profiles, dependency/reconstruction auditing and remaining resource gates; current closeout status in the report |
| [SPEC-002 evidence](reports/SPEC002_DESIGN_CHECK.md) | 709 instantaneous checks, native fixture, 483 tests and unchanged 0.5.0 production sources |
| [Selective-contact numerics](docs/SELECTIVE_CONTACT_NUMERICS.md) | Independent physical-pair reference, bounded RK4/1 ms candidate, gate-domain/observation/accounting checks and production handoff |
| [NUM-003 qualification](reports/NUM003_REFERENCE.md) | 20 passing cases, retained coarser/linear failures, 542 tests, two source capsules and separate native-state audit |
| [Multiscale design](docs/MULTISCALE_DESIGN.md) | Data-defined composition, scale interfaces, and future organ-to-organ exchange |
| [First build](docs/FIRST_BUILD.md) | Implemented one-cell scope, module boundaries, numerical contract, and limitations |
| [M1a acceptance](reports/M1A_ACCEPTANCE.md) | Test results, saved examples, numerical errors, and reproduction commands |
| [Isolated regulatory reference](docs/EMT_REFERENCE.md) | Source equations, units, approximations, reuse boundary, and reference capture |
| [M1b acceptance](reports/M1B_ACCEPTANCE.md) | Source comparison, solver/refinement errors, replay, and version preservation |
| [Passive contact](docs/PASSIVE_CONTACT.md) | Two-cell transport, cell/edge state, contact controls, units, and numerical contract |
| [M1c-a acceptance](reports/M1C_A_ACCEPTANCE.md) | Conservation/reference errors, blocked/release/replay checks, and earlier-model regression |
| [Reaction and transport](docs/REACTION_TRANSPORT.md) | Composed local/graph dynamics, species/cell/edge axes, controls, and numerical contract |
| [CORE-003 acceptance](reports/CORE003_ACCEPTANCE.md) | 270 tests, eight composed-model runs, independent matrix checks, and all earlier-model regressions |
| [Experiments](docs/EXPERIMENTS.md) | Reference assays, first tissue demonstration, controls, and later questions |
| [Roadmap](docs/ROADMAP.md) | Staged implementation and evidence needed to complete each milestone |
| [Decisions](docs/DECISIONS.md) | Accepted choices, their reasons, and unresolved implementation details |

## First build and first tissue destination

First run one well-mixed cell with a timed external input, explicit numerical
state, read-only observations, and verified save/restore. An analytically
checkable fixture established the engine contract; source-backed isolated
regulation, a passive two-cell contact, and reusable local-reaction/graph-transport
composition now work. The physical-cell contract is now implemented: one
Na/K/Cl cell, one membrane and maintained bath, charge-derived voltage, passive
leaks, and an explicitly energized reference pump. Independent CPU trajectories
and the bounded numerical candidate pass NUM-002; production JAX, independent
controls, identified observations, complete replay and earlier-model regressions
pass MODEL-003. D021 now specifies a stateful physical junction and records
its differences from the source's algebraic gate and transport approximation.
Independent pair trajectory qualification now passes NUM-003; production
implementation and JAX/replay/regression acceptance come next. Coupled
source compatibility and any physical regulatory unit/clock mapping remain
separate work. The [engineering gate](docs/ENGINEERING_GATE.md)
keeps engineering, numerical, and scientific acceptance distinct.
The Levin assays are reference experiments on this foundation, not special engine
behaviour. See [First build](docs/FIRST_BUILD.md) and [Passive contact](docs/PASSIVE_CONTACT.md).

The first tissue demonstration is a small 2D tissue in which a temporary local cue
changes cellular state, communication determines whether that change spreads, and subsequent carrier
replacement tests its persistence. Begin with a fixed contact graph and controlled
relay assays. Add growth, division, and turnover as an explicit later extension.

The model will represent intracellular dynamics, selective communication,
spatial context, and lineage events. Full numerical state will support multiple
readouts, including phenotype, retention, rewriting, transmission, and recovery.

## Working principles

- Keep model equations, numerical methods, experiment interventions, and
  measurements explicit and separately versioned.
- Use array-based state and JAX kernels suitable for CPU and GPU execution.
- Preserve a readable CPU numerical reference and validate accelerated execution.
- Make saved-state restoration and branching into alternative futures central
  capabilities.
- Track cell identity, ancestry, external support, and material/state transfer.
- Keep biological inheritance boundaries distinct from complete restart snapshots.
- Compose cell, tissue, and organ instances through data definitions and typed
  exchange interfaces; keep biological models separate from numerical execution.
- Preserve access controls and challenge-response measurements as models gain
  slow regulatory state, local sensing, or memory-writing mechanisms.
- Develop a headless simulation library with a separate viewer and analysis tools.
- Carry positive and negative reference outcomes into verification.
- Bring findings from the continuing exploration into Cells through reviewed,
  identifiable snapshots.

## Scope of the ideas base

The current sources are listed in [Scientific basis](docs/SCIENTIFIC_BASIS.md).
The strict-eight, ingressing-minds/Ruliad, and AI branches of `../../preprints`
have now received a targeted design review (R002). The remaining collection is
still a later ideas source. Research results are model-specific evidence, not
universal laws to encode in the engine.

R remains an optional analysis interface. Python/JAX is the selected simulation
stack; Julia, Taichi, C++, PhysiCell, and CompuCell3D are retained as alternatives
in the decision record rather than additional implementation commitments.

## Keeping the documents current

Update [Progress](PROGRESS.md) when work starts, completes, or encounters a
dependency. Record a substantive design change in [Decisions](docs/DECISIONS.md).
Add a research check-in to [Scientific basis](docs/SCIENTIFIC_BASIS.md), then
update the affected experiment or roadmap entry. Link completed tasks to their
code, tests, benchmark reports, or run artifacts.
