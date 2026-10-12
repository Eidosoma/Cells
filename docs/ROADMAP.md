# Roadmap

Direction reviewed: **2026-10-11**. This document defines priorities and completion
criteria. [Progress](../PROGRESS.md) owns current status, active runs and results;
[BETSE coverage](BETSE_CAPABILITY_ROADMAP.md) records the mechanism-level gaps.
The [earlier roadmap](history/ROADMAP_BEFORE_2026-10-11.md) retains the original
build sequence and its historical status statements.

## Current development priorities

1. Extend the verified simulation stack: compose membrane transport, junctions,
   spatial fields, compartments and chemistry with explicit ownership and
   independent references. Complete shared configuration, checkpoint and ensemble
   support for each new component before treating it as a usable model family.
2. Use BETSE to calibrate and verify the bioelectric layer within the larger
   Cells simulations. Broaden comparisons of named mechanisms and their
   combinations within declared physical and numerical regimes; retain
   source-specific clock semantics separately from physical-time models.
3. Develop assembly coupling as an explicit model hypothesis. Keep finite protein
   material and ionic inventories distinct; use intervention and conservation
   checks before adding feedback from calcium, energy or neighbouring cells.
4. Carry CPU/L4 verification and resource measurement into each new family.
   Prepare Jupiter qualification in stages while capability work remains the
   immediate priority. Further utilization optimization is parked; telemetry
   continues on GPU runs.

Water/volume/flow, biophysical mechanics, spatial redistribution and mitochondrial
energy dynamics require new laws and references. Existing calcium and tissue
implementations are useful prerequisites, not complete coverage of those targets.
Biological calibration needs measured inputs, uncertainty and independent
experimental evaluation in addition to numerical or source agreement.

For broader BETSE coverage, the engineering order and relative difficulty are:

| Remaining work | Relative difficulty | What makes it difficult |
| --- | --- | --- |
| Complete ordinary execution for new coupled components, then extend duration and timestep comparisons | Moderate | Preserve full state, native update order, intervention timing and conservation through every execution path |
| Additional channel, ligand, pump and transporter families | Moderate to high | Each law needs explicit units, parameter provenance and coupled reference cases; one representative channel does not cover a family |
| Varied tissue geometries, barriers, regional profiles, cutting and changing contacts | High | Boundaries and ownership change both field solutions and material accounting; spatial convergence needs independent evidence |
| Surface redistribution of channels and pumps | High | Move membrane-bound quantities conservatively while their distributions alter local transport and fields |
| Water, osmotic pressure, volume and flow | Very high | Water movement changes concentrations and geometry, which feed back into electrical and chemical dynamics |
| Deformation and electromechanics | Very high | Evolving geometry changes forces, capacitance and contacts together; stable integration and force/material balance must agree |
| Long-time behaviour of the complete coupled system | Very high | Individually checked components can produce new stiffness and feedback; both numerical convergence and suitable biological measurements are needed |

These are engineering judgments, not runtime or delivery estimates. The
[capability inventory](BETSE_CAPABILITY_ROADMAP.md) defines the remaining scope.
Mitochondrial energetics and assembly feedback also serve the wider Cells research
programme; their proposed scope should not be confused with a fully audited list
of mechanisms exercised by the pinned BETSE runtime. Jupiter execution remains a
separate qualification track.

## Milestones

| Milestone | Deliverable | Completion evidence |
| --- | --- | --- |
| M0: project foundation | Scientific basis, architecture, experiment plan, decisions, and tracker | Documents are consistent, linked, and explicit about implemented versus planned work |
| M1: executable CPU foundation | M1a one-cell engine; M1b source-backed regulation; M1c two-cell contact | Analytic fixture and replay tests first; E01/E02 source checks subsequently; pinned numerical settings |
| M2: memory and relay assays | Checkpoints, branching, cue schedules, observers, stable identities | Restart comparison; selected E03-E06 positive/negative references; full-state and endpoint agreement |
| M3: fixed 2D tissue | Graph geometry, selective boundaries, E07, and separate viewer | Reproducible cue/removal/boundary/replacement demonstration; viewer does not affect dynamics |
| M4: GPU execution | Qualified one-GPU execution, then multi-GPU ensembles and coupled spatial partitions; multi-host operation later | Accuracy/precision and partition-interface checks, collective-safe failure/restart, strong/weak scaling and complete memory/communication/output measurements |
| M5: growth and turnover | Cell-centre mechanics, resource/volume accounting, division, death, changing contacts | Accounting and ancestry checks; capacity/event handling; E08 comparison with scripted renewal |
| M6: multiscale tissue unit | Detailed regions coupled to fields/compartments or validated reduced models | Interface accounting, multirate/refinement tests, E12 held-out challenge agreement, cost/accuracy profile |
| M7: first whole-organ preset | Simplest useful organ/function selected and expressed as a data definition | Declared extent and omitted physiology; organ-level validation within scope; repeatable configuration-driven run |
| M8: coupled organ presets | Two or more organ instances linked through explicit transport/signalling models | Disconnected controls, exchange/delay/accounting tests, coupled functional validation, reproducible world checkpoint |

## Sequence and dependencies

The milestone IDs below remain stable for historical reports. They are goal
families, not a current task board or a requirement to finish all of one family
before starting another. Existing spatial, chemistry, assembly and GPU work
crosses those boundaries; consult Progress for its tested scope.

New physics first needs declared units, state ownership, equations and controls,
then independent numerical comparisons and complete replay/accounting checks.
Integrated models need additional tests of their interfaces. An isolated law
comparison does not certify a coupled tissue or a new parameter regime.

## M1 implementation slices

The original one-cell, pair and shared-runner slices are preserved in the
[historical roadmap](history/ROADMAP_BEFORE_2026-10-11.md#m1-implementation-slices)
and [development history](DEVELOPMENT_HISTORY.md). New development builds on the
versioned models rather than treating those completed slices as future work.

## M2 and M3 implementation slice

The [experiment programme](EXPERIMENTS.md) defines proposed memory, relay and
cue/removal/replacement assays. Existing electrical tissue and checkpoint
capabilities supply parts of their infrastructure; they do not establish the
assays' biological outcomes. Select a bounded assay with positive and negative
controls, explicit preparation and read-only observations before claiming memory,
transmission or renewal.

The [first two-task readout assay](TWO_TASK_READOUT_ASSAY.md) applies the
verified CPU/L4 dynamic-junction runtime to this question, following the
[polycomputing design](MULTISCALE_EXECUTION_ARCHITECTURE.md#polycomputing-several-functions-in-the-same-evolving-substrate).
Test whether one tissue trajectory supports both cue-location and temporal-pattern
readouts. Fix the readout complexity and calibration split, hold out complete
input combinations, and compare single-task and joint-task inputs with input-only,
disconnected and shuffled controls. Keep passive readouts separate from physical
consumers. Causal use, ablation/rescue and feedback coupling follow only when their
mechanisms and accounting are explicit; successful decoding alone does not
establish biological polycomputing. This bounded assay can precede organ models
and larger GPU runs.

## M4 and M5 implementation slice

CPU and local L4 execution are implemented for selected model families. The
[GPU guide](GPU_ENSEMBLES.md) describes the independent-world worker queue and
offline planning for up to sixteen GPUs. Qualification on Jupiter should proceed
from one four-GPU node to two and then four nodes, with per-device correctness,
restart, resource and allocation-cost checks at each step. Planning is not a
measurement of remote execution or scaling.

A single interacting tissue split across GPUs requires additional partitioned
state, once-owned transfers, same-stage communication and a distributed field
solve. It is a separate engineering task from independent ensemble scheduling.
Record GPU-busy time, measured SM-active, coverage, throughput and arm finish
imbalance. Do not treat the earlier advisory 70% utilization target as a physics
acceptance criterion or invent a warmed interval for mixed correctness suites.

Growth and turnover require explicit resource, volume, division, death, contact
and partition laws. A scripted event, complete checkpoint or assembly fragment
is not autonomous cell division. Preserve material and lineage accounting and
qualify mechanics and event coupling before testing biological renewal.

## M6 to M8: tissue units, organs, and coupled organs

First make one explicit fine/coarse interface work. Add spatial fields, 3D
geometry, and process-specific rates as required by the chosen tissue question;
test each addition against a smaller detailed/reference case. A reduced state
must preserve relevant history and future responses, not only a current label.

Select the first organ using simplicity, available evidence, external dependency
count, and one measurable function. Its definition specifies species, geometry,
cell/process families, resolution, parameters, ports, and omitted physiology.
Implement any missing reusable mechanism as a model module; keep organ selection
and assembly in data. Do not relabel a tissue patch as a whole organ.

Add a second independently initialised organ instance and explicit couplers only
after generic multi-compartment exchange tests pass. A coupled world checkpoint
includes transport compartments, pending exchanges, delays, and each component's
numerical state. Independent ensemble batching is not organ-to-organ coupling.

Computational multiscale and large-GPU execution are future requirements recorded
in [Multiscale design](MULTISCALE_DESIGN.md). Profile memory, numerical work,
coupling, output, and transfers before selecting spatial partitioning, different
regional fidelity, or multiple devices. GPU capacity alone does not establish
whole-organ feasibility. These extensions need their own scientific and execution qualifications.

## Other research options

Cell shape models, population evolution, inherited regulatory structure,
information-dynamic observers, differentiable inference, and validated coarse
models can be selected when they answer a concrete research question. E09-E11
memory-location, ecology, and embedded-control experiments can branch from the
appropriate milestones; all are not mandatory gates to an organ demonstration.
The strict-eight, ingressing/Ruliad, and AI design review is recorded as R002.
Unreviewed parts of the broader preprints collection remain later ideas sources.

## Updating this roadmap

Track daily execution and evidence in [Progress](../PROGRESS.md). Change a milestone
here when its scope or acceptance evidence changes. Record architectural changes
in [Decisions](DECISIONS.md), preserving the reasons for earlier choices. A valid
negative scientific result may complete a milestone; implementation success does
not require a favourable biological hypothesis.
