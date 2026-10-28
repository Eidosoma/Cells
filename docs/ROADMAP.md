# Roadmap

Direction reviewed: **2026-10-28**. This document defines priorities and completion
criteria. [Progress](../PROGRESS.md) owns current status, active runs and results;
[BETSE coverage](BETSE_CAPABILITY_ROADMAP.md) records the mechanism-level gaps.
The [earlier roadmap](history/ROADMAP_BEFORE_2026-10-11.md) retains the original
build sequence and its historical status statements.

Cells' wider target is integrated cell physiology, molecular assembly, tissues
and organs for testing the Plastic Heredity and Forms ideas. The
[calibration plan](SCIENTIFIC_BASIS.md#calibration-across-the-cells-stack) combines
model references with measured molecular, cellular, anatomical and functional
evidence. Source-model comparisons support that programme one layer at a time.

Within that scope, **feature parity with the scientific simulation capabilities
of both BETSE and BITSEY** is a verification target, assessed against pinned
source versions. BITSEY is a
[simplified BETSE-derived simulator](SCIENTIFIC_BASIS.md#betse-and-bitsey-as-complementary-references)
with its own implementation; agreement with one does not establish agreement
with the other. Track their coverage separately, including coupled behaviour,
preparation, interventions, numerical clocks and complete state. Each supported
Cells model needs its own CPU/GPU evidence before GPU parity is claimed.

## Current development priorities

The current user priority is **BETSE scientific compatibility before moving
Cells production runs to Jupiter**, with CPU development and validation first.
The milestone below is an evidence gate; an allocation start date does not
make unfinished mechanisms compatible.

1. Extend the verified simulation stack: compose membrane transport, junctions,
   spatial fields, compartments and chemistry with explicit ownership and
   independent references. Complete shared configuration, checkpoint and ensemble
   support for each new component before treating it as a usable model family.
2. Use BETSE to calibrate and verify the bioelectric layer within the larger
   Cells simulations. Broaden comparisons of named mechanisms and their
   combinations within declared physical and numerical regimes; retain
   source-specific clock semantics separately from physical-time models.
3. Use BITSEY as the regulatory/ionic reference and reproduce the cellular
   state-writing, transmission, revision and replacement experiments in
   *How Forms Become Reconstructible*. Start with the corrected-clock lineage
   assays below, alongside continuing BETSE work.
4. Develop assembly coupling as an explicit model hypothesis. Keep finite protein
   material and ionic inventories distinct; use intervention and conservation
   checks before adding feedback from calcium, energy or neighbouring cells.
5. Build features with short CPU checks first, retaining independent references,
   conservation checks and failed evidence. Batch later GPU qualification across
   compatible features and pack independent worlds within each device. Use
   measured runtimes to balance arms across the four-GPU Jupiter node and later
   up to sixteen GPUs, preserving each case's identity and tolerances. Track both
   GPU-busy and SM-active, with useful work and allocation cost as the objective.
   New GPU rounds are deferred while the next mechanisms are implemented;
   CPU implementation and GPU qualification remain separate coverage claims.
   Validation duration follows the claimed behavior: component-stage checks do
   not establish coupled relaxation or long-time stability. Retain sufficient
   settling time, intervention/recovery intervals, independent references and
   refinement; launch longer necessary checks detached rather than shortening
   their scientific scope to meet a runtime target.
6. **Defer further two-task/channel-compensation research until more of the
   simulator is built and verified.** Preserve the existing experiments and
   the [Hazan and Levin review](PAPER_REVIEW_CHANNEL_COMPENSATION.md) for a later
   [bounded functional-recovery experiment](EXPERIMENTS.md#functional-recovery-through-channel-compensation):
   hold an impaired mechanism fixed, search other permitted controls, and test
   recovery across held-out challenges and parameter uncertainty. A reference
   must first demonstrate the function being restored. The review's GPU
   benchmarking, intervention and licensing caveats remain implementation inputs.
   Revisit its scope after additional platform capabilities are verified;
   do not automatically extend the search or launch confirmation runs.

The first [water/volume component](TISSUE_RETURN_CURRENT.md#osmotic-water-and-compliant-volumes)
couples conservative solvent transfer to passive ions in compliant compartments.
Its qualification is tracked in Progress. Integrating it with pumps, channels,
calcium and assembly comes before evolving geometry and fluid fields. Broader
biophysical mechanics, spatial redistribution and mitochondrial energy dynamics
still require additional laws and references; existing components provide
prerequisites rather than complete coverage.
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

## BETSE compatibility before Jupiter

Compatibility concerns the pinned BETSE v1.5.0 scientific runtime, not its GUI,
YAML syntax or serialized files. Use the [capability inventory](BETSE_CAPABILITY_ROADMAP.md)
to map each supported native mechanism and option to a Cells implementation,
source comparison and a coupled numerical test. Explicitly record unsupported
mechanisms and source defects; they cannot silently count as passing coverage.

The completion requirements are:

1. Finish the source inventory, including channel variants, ligand/network
   regulation, transporters, organelle branches and interventions. A complete
   subset such as Kv1 is not a complete simulator catalog.
2. Implement the missing reachable scientific mechanisms and compose them with
   the shared material, charge, energy and geometry owners. Fixed-geometry
   injury/resealing does not satisfy native cell removal and contact rebuilding.
3. Compare aligned native laws and representative coupled histories, retaining
   native initialization/update clocks and boundary conventions explicitly.
   Where Cells deliberately uses different physics, document that distinction
   and validate it independently rather than claiming source equivalence.
4. Demonstrate relevant intervention/recovery times, timestep and spatial
   convergence, conservation, complete observations/checkpoints and rejected
   invalid states. Short rate checks alone do not close a coupled capability.
5. Resolve or explicitly delimit source defects and loader-disabled features.
   Any narrower compatibility claim must state the excluded capabilities;
   full scientific feature parity remains the target.

When GPU work resumes, local batches can qualify completed feature groups
while broader source coverage continues. Jupiter qualification follows the
compatibility milestone and establishes execution equivalence, memory limits
and balanced independent-world throughput. Offline 1/4/16-GPU plans are
preparation, not evidence of a completed remote run.
Experimental biological validation remains a separate requirement.

## Injury and repair

Start with **localized membrane injury and prescribed resealing on a fixed
tissue geometry**. This adds a reusable physiological component before tackling
cell removal, regrowth or adaptive recovery. Existing channel/junction schedules
support reversible block/release, and complete checkpoints preserve their
histories. Explicit membrane damage is the component described below; tissue
cutting and growth remain later work. Ordinary checkpoint branches deliberately
reject a changed model/topology.

The first component, `resolved_repair@1`, gives each membrane patch an explicit
damage fraction between zero and one. A timed injury hazard opens the intact
fraction; a declared first-order closure law lets damage decay. Damage controls
additional Na/K permeability through the existing GHK transport and free-ion
ownership machinery. Its [equations and boundaries](TISSUE_RETURN_CURRENT.md#fixed-geometry-injury-and-prescribed-resealing)
are specified; current validation status stays in [Progress](../PROGRESS.md).
The initial law is a **phenomenological closure model**, with explicit units and
parameters, not an experimentally fitted repair mechanism. Structural repair
costs and finite metabolic support remain to be modelled. No concentration,
voltage, calcium store or intrinsic channel gate is reset to manufacture recovery.

The assembly-integrated runner also supports scheduled interventions alongside
cell-owned assembly events, with exact internal boundaries and complete damage
and transfer records. This connects the existing assembly and injury components;
assembly-driven closure, metabolic repair support and feedback into protein
pools still require explicit laws and references. Current validation status
belongs in [Progress](../PROGRESS.md).

Use the analytic damage-decay solution and independently integrated coupled
ion/field equations as references. Require uninjured, sham, held-injury
(closure disabled) and resealing controls; event-boundary restart, complete
ledgers, timestep convergence and CPU/L4 agreement. Recovery means returning
to a declared functional range for a specified hold time, after a reference has
demonstrated that function. Retain failures and separate passive relaxation,
prescribed resealing and any later autonomous adaptation. The parked channel-
compensation search is a separate research branch.

Keep patch/world identities and damage arrays explicit, with masked device
updates and complete checkpoint state. Independent worlds can use the existing
GPU execution path; moving a single interacting tissue across devices requires
the additional topology/communication work in the
[multiscale architecture](MULTISCALE_EXECUTION_ARCHITECTURE.md).

| Reference or later capability | What it contributes | Boundary of the first component |
| --- | --- | --- |
| Pinned BETSE [cutting configuration](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/data/yaml/sim_config.yaml) and [tissue handler](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/tissue/tishandler.py) | Removal of selected cells, rebuilt contacts/profiles and changed wound-boundary permeability | A separate topology-changing extension; fixed-geometry resealing does not establish cutting parity |
| Pinned BETSE [wound-channel file](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/channels/wound_channel.py) | A decaying wound factor and proposed Na/K route | Source inspection finds mismatched base/subclass method signatures and commented-out transport. It needs a runnable capture before any native correspondence claim; the proposed Cells closure law is independently specified |
| Actual tissue cutting and replacement | Changed material ownership, exterior geometry, capacitance, contacts and field components | Requires explicit accounting for removed material/charge/energy, stable entity IDs and conservative state remapping |
| Regrowth and autonomous repair | New tissue and sustained restoration | Requires growth/mechanics, water/volume, regulatory feedback and energetic/material supply, followed by suitable experimental calibration |

Source inspection and implementation evidence are recorded separately in
[Progress](../PROGRESS.md); neither establishes biological regeneration.

## Membrane redistribution

Use the [conservative surface-transport component](TISSUE_RETURN_CURRENT.md#lateral-membrane-redistribution)
for explicitly owned membrane-bound populations. The first ordinary composition,
`resolved_redistribution@1`, couples neutral always-open populations to patch
permeability while preserving each cell's total. Its fixed/mobile controls,
independent coupled references and full restart now pass on CPU/L4 in the
documented synthetic regime. The `resolved_redistribution@2` extension adds
conserved neutral Na/K ATPase populations whose current abundance sets capacity,
with separate pump cycles, dissipation and maintained ATP-reservoir work. The
[`resolved_redistribution@3` extension](TISSUE_RETURN_CURRENT.md#mobile-channels-carrying-joint-gating-states)
transports four joint Kv1.5 gate conformations without discarding their
correlations. Its declared rate-bias work is phenomenological accounting,
not a measurement of gating energetics. The
[`resolved_repair@2` composition](TISSUE_RETURN_CURRENT.md#mobile-kv15-with-owned-calcium-and-prescribed-repair)
connects mobile Kv1.5 to owned calcium/ER and prescribed injury/resealing,
retaining distinct protein and conducted-ion ledgers. The
[`resolved_repair@3` extension](TISSUE_RETURN_CURRENT.md#mobile-pumps-with-owned-calcium-and-prescribed-repair)
adds mobile Na/K ATPases with separate protein, ion and maintained-ATP work
ledgers; its qualification status belongs in Progress. The
[assembly integration](TISSUE_RETURN_CURRENT.md#assembly-with-mobile-channels-and-prescribed-repair)
applies each cell's existing assembly availability to fixed and mobile conduction
while preserving complete inventories and event clocks; its qualification status
is recorded in Progress. The [mobile-pump assembly extension](TISSUE_RETURN_CURRENT.md#assembly-with-mobile-pumps-channels-and-prescribed-repair)
retains independent pump controls and all 53 ionic fields, with separate protein,
ion-transfer and signed reservoir-work reports and its own qualification.
Broader mobile channel families and protein exchange
between assembly and membrane pools remain extensions. Charged cargo still needs
bound-charge and field-work accounting. Active trafficking, fluid motion, assembly
exchange and changing surface geometry remain separate extensions. Implementation
and qualification evidence belong in [Progress](../PROGRESS.md).

## BITSEY replication

The first target is the Forms programme's corrected-clock BITSEY experiments,
with [source versions and provenance](SCIENTIFIC_BASIS.md#betse-and-bitsey-as-complementary-references)
kept explicit. Existing isolated regulation, the coupled two-cell model and
independent graph references are starting components; full lineage reproduction
remains to be implemented and verified. This work can proceed alongside BETSE
coverage without waiting for every bioelectric mechanism to be complete.

Full BITSEY parity also requires an inventory of the pinned core and model
families beyond the selected miRNA/EMT circuit, including general regulatory
gates, reaction-diffusion and their coupled use. Map each capability to a Cells
implementation, a reference comparison or an explicit remaining gap. The Forms
lineage assays are the first replication priority, not the complete BITSEY
feature list; that broader inventory remains to be completed.

1. **Establish the coupled reference and clocks.** Pin BITSEY and the selected
   assay protocol; map the complete 17-entry native packet into primary state,
   fixed context and derived quantities. Account for all mechanisms needed by
   the assay, including state-dependent K expression omitted by the current
   pair. Reuse the graph references and implement the P10R boundary/observation
   clock contract, with waiting cells continuing to evolve. Check native and
   independent CPU trajectories, numerical refinement, accounting and restart
   before extending duration. Source time remains nominal model units.
2. **Reproduce the editable lineage (P11).** Rebuild the 13-by-13 preparation at
   each numerical resolution, write M into three E targets, remove cues and test
   isolated retention. Follow three complete M handovers, rewrite the actual
   current carriers to E, then follow three E handovers into fresh M recipients.
   Preserve full state and identity; remove every old teacher at each boundary.
   Require both isolated retention holds and the registered RNA-blocked,
   boundary-cut, sham, no-cue and ordinary-founder controls. Judge trajectories,
   clocks and retention criteria as well as endpoint labels.
3. **Qualify GPU execution and extend the assays.** Compare CPU and L4 state,
   outcomes, numerical refinement and complete checkpoint/replay behaviour for
   the new model. Use independent ensembles for later Jupiter runs across
   4–16 GPUs, recording GPU busy, measured SM-active and arm finish imbalance.
   Then extend to perturbation, tissue context, turnover and communication-pause
   experiments using their own pinned protocols and numerical checks.

The later P31/P32 pause studies are separate source campaigns; P32's completion
on 12 October postdates Forms v0.17. Preserve the original P10/P27/P30 numerical
failures when selecting their corrected successors. These are externally
scheduled cellular assays with supplied fresh cells, not autonomous division.
Agreement with BITSEY equations, reproduction of the Forms extensions and
biological validation are separate completion claims; the original cancer
paper's table/geometry correspondence also remains a separate question.

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

Select the calibration data alongside that function: published model repositories
for candidate laws, molecular/cell atlases for composition and placement, and
matched physiological and mechanical experiments for dynamics. Qualify one cell
or small functional tissue unit first; then test the assembled organ under held-out
conditions. Preserve the distinction between anatomical agreement and functional
validation, and between model-reproduction inputs and independent measurements.

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
