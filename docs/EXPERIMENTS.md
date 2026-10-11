# Experiment programme

Initial specification: 2026-09-07. These are proposed Cells assays and development
targets. E00 and the isolated regulatory E/M subset of E01 are implemented and
verified. E02's passive prerequisite and bounded nominal source-compatible pair
engineering are complete. Selected longer source switching protocols and E03
onward remain unexecuted Cells assays, not automatically launched campaigns.
Task status is maintained in [Progress](../PROGRESS.md). Scope reviewed
2026-10-11: recent tissue, calcium, assembly and CPU/L4 engineering results are
prerequisites and separate model tests; they do not establish the proposed
heredity/relay assays below. The engineering chronology retains its original dates.

## First engineering assay

E00 is the one-cell source-and-decay pulse fixture described in
[First build](FIRST_BUILD.md). It tests numerical accuracy against an analytic
solution, unit/accounting consistency, event timing, independent observation,
snapshot/restore, and isolated continuation branches. It is the first runnable
target, before E01. It passed the M1a checks on 2026-09-08; see the
[acceptance report](../reports/M1A_ACCEPTANCE.md). It is not a biological memory
or organ-function result.

## Physical engineering panel

The accepted [one-cell physical contract](BIOELECTRIC_CELL_SPEC.md) defines a
Na/K/Cl cell, explicit membrane and maintained bath, passive leaks, and an
energized reversible reference pump. Its instantaneous design checks are not
new E01/E02 source results. NUM-002 now verifies independent trajectories,
separate leak/pump controls, charge/exchange accounting, energy signs, off-grid
events, refinement, and an identified cubic-observation candidate. See
[qualification](../reports/NUM002_REFERENCE.md). MODEL-003 now passes separate
[production JAX checks](../reports/MODEL003_ACCEPTANCE.md), independent control
branches, and exact complete restart without re-preparation. The reference itself
has no Cells checkpoint or biological transfer implementation.

This fixture remains separate from the source library: no physical/source-scaled
unit or clock mapping is inferred, no biological memory result is claimed, and
the reviewed BETSE experiments have not been rerun in Cells.

## First experimental biology benchmark

[BIO-001](BIOLOGICAL_BENCHMARK_001.md), selected in D042, is a separate
experimental-data track. The provisional RPTEC endpoint pilot preserves three
consistent ion-solution conditions and quarantines two with conflicting published
inputs. It has a retrospective fit/evaluation split, approximate figure readings,
unknown numerical SEM, and an explicit whole-cell recording/bath compatibility
gate. BIO-001 remains the original no-fit curation slice.

D043 / [BIO-002](../reports/BIO002_CONDITIONED_VOLTAGE.md) now fits a separately
specified static electrical comparator to C1/C2 only and predicts C3 at
-14.59 mV versus an approximate -18 mV reading. Its [-18.32, -11.20] mV
reading-bound range is not a confidence interval; biological acceptance remains
not assessable. No recovery-time measurement or production trajectory is
claimed. D044 / [BIO-003 closes this pilot as descriptive](../reports/BIO003_PILOT_CLOSEOUT.md)
after reviewing the supplement and methods. No C1-C3 numeric summaries or
experiment-level records were recovered; recording assumptions remain
unqualified. There is no automatic continued search or fit. A future dynamic
cell benchmark needs appropriate data/boundaries and separate qualification.

D045 returns to the [BETSE capability roadmap](BETSE_CAPABILITY_ROADMAP.md):
small species/membrane, kinetic, graph and field fixtures precede wider physical
composition. Source parity and biological agreement are separate experiments;
neither follows from implementing a feature. At that September architecture stage, GPU implementation and the long E02
candidate campaign were deferred. Selected CPU/L4 model qualifications now exist;
see [GPU execution](GPU_ENSEMBLES.md). Those results do not complete the E02
campaign or qualify future distributed partition boundaries.

D046 / [SPEC-005](../reports/SPEC005_DESIGN_CHECK.md) now supplies two frozen
synthetic assemblies and an independent instantaneous reference: old Na/K/Cl
reduction and a divalent-ion/background-charge fixture. The 1546 arithmetic,
limiting-case and accounting checks are not new biological observations.
D047 / [NUM-006](../reports/NUM006_REFERENCE.md) now qualifies 14 short trajectory
cases with independent implicit references and three RK4 refinements. The 0.01 s
RK4/cubic candidate is bounded to that panel. D048 now implements the
[new production family](MULTISPECIES_MEMBRANE.md); eager/JIT, independent readout,
complete restart/branch and cohort [acceptance pass](../reports/CORE006_ACCEPTANCE.md).
All 2565 tests pass across explicit current/preserved-source contexts. No old timestep
limit or BIO-002 acceptance is changed.

D049 / [SPEC-006](../reports/SPEC006_DESIGN_CHECK.md) now checks one Kv1.5-style
channel reference: seven analytic prescribed-voltage gate protocols and
instantaneous ionic composition. Equal open fraction can conceal different
activation/inactivation histories; blocking permeation does not erase gates.
These are equation/ownership checks, not coupled trajectories, whole-cell voltage
clamp, source time-stepping parity or biological validation. NUM-007 must qualify
the new coupled regime before a production channel or timestep is selected.
D050 now [completes that independent NUM-007 qualification](../reports/NUM007_REFERENCE.md):
fourteen short synthetic cases, 0.5 ms RK4/cubic with passing refinement, retained
coarse failures, separate channel histories and read-only dense replay. CORE-007
now implements the [production channel](VOLTAGE_GATED_MEMBRANE.md), with
[bounded CPU/JAX acceptance complete](../reports/CORE007_ACCEPTANCE.md);
no biological or deferred E02 result is promoted.

D052 / [SPEC-007](PHYSICAL_IONIC_GRAPH_SPEC.md) now checks physical ionic graph
composition on single/disconnected cells, heterogeneous pairs and shared-recipient
stars, with explicit local/edge state ownership. [Instantaneous evidence passes](../reports/SPEC007_DESIGN_CHECK.md);
the circulation fixture is a supplied algebraic history, not a memory assay.
That instantaneous slice does not select a timestep or qualify the source E02 campaign.
D053 / [NUM-008](../reports/NUM008_REFERENCE.md) now separately qualifies twelve
short coupled graph cases, with 84 graph attempts and five independent component
solves. The 2 ms RK4/cubic selection has passing 1 ms refinement, complete
accounting, independent interventions and a substep junction pulse. Saved dense
data replay passes without an ODE rerun. This is numerical plausibility for
the frozen synthetic equations, not biological agreement, source E02 coverage,
production graph acceptance or an arbitrary-graph timestep guarantee.
D054 / CORE-008 now implements the [separate physical graph family](PHYSICAL_IONIC_GRAPH.md).
Its [production acceptance](../reports/CORE008_ACCEPTANCE.md) checks the same
twelve cases through CPU/JAX, independent readouts, complete scalar restart,
future branching, full windows and independent-world cohorts. Source assay,
biological plausibility and organ behavior remain separate experimental gates.

D055 / [SPEC-008](FINITE_EXTRACELLULAR_SPEC.md) checks one finite extracellular
compartment independently, without a trajectory or production change. The
[reference panel](../reports/SPEC008_DESIGN_CHECK.md) covers closed ionic material/
charge/energy accounting, shared-outside feedback without junctions, and the
maintained-bath limit on fixed algebraic transfers. Neither manufactured histories
nor an energy directional-derivative probe is a simulated adaptation or memory
assay. NUM-009 must qualify time-dependent depletion, controls and complete state
before a finite environment can become an experimental production capability.

D056 / [NUM-009 v1](FINITE_EXTRACELLULAR_NUMERICS.md) freezes fourteen short
engineering cases, including tiny-outside depletion stress, independent route
blocking/release and a sub-step junction pulse. All ten physical fields,
outside concentration errors and conservation are checked. A depletion witness
is a numerical test of this synthetic model, not evidence for biological
homeostasis, adaptation, memory or an organ function. Production acceptance and
later source-backed assays remain separate gates.
The first NUM-009 run stopped at the junction-only reference's exact outside-
increment invariant. D057 / [v2](FINITE_EXTRACELLULAR_NUMERICS_V2.md) keeps every
inventory explicit and corrects reference linearization without weakening any
gate. Its [new result](../reports/NUM009_REFERENCE_V2.md) completes all fourteen
cases, including full block/release, pulse and both depletion stresses.
1 ms RK4/cubic with passing 0.5 ms refinement is selected only for this short
panel; the synthetic pump-only outside-K drop is 80.8057%. Original failures
remain retained. Neither depletion nor numerical agreement validates biology.

D058 / [CORE-009](../reports/CORE009_ACCEPTANCE.md) now implements that finite
environment as a separate CPU/JAX model through the shared engine. All fourteen
reference cases pass in eager/JIT, with complete restart, future branching,
bounded windows and independent-world cohorts; 150 new targeted tests pass.
All 3616 maintained/historical regression tests pass; release evidence is tracked
in [Progress](../PROGRESS.md). Each world's outside
is an owned, changing inventory: disconnected cells can affect each other through
it, while separate worlds cannot exchange ions. This is a well-mixed numerical
engineering capability, not a spatial tissue environment, a source E02 assay or
biological validation. Source-backed physiological comparisons remain necessary.

D059 / [SPEC-009](SPATIAL_EXTRACELLULAR_SPEC.md) adds eight synthetic spatial
definitions and [passing independent instantaneous checks](../reports/SPEC009_DESIGN_CHECK.md),
not a spatial biology assay. The binary-salt witness separates zero net electrical
current from nonzero species exchange; the loop distinguishes node balance from
zero current on every face. Membrane-free outside volumes, monovalent/divalent
species, gauge/ordering invariance and passive whole-system energy are checked.
[NUM-010](../reports/NUM010_REFERENCE.md) now qualifies short time-dependent
relaxation, membrane feedback and a one-dimensional spatial-refinement path
using separately frozen methods and residual/error budgets. The pure-bulk salt
contrast falls by 22.1199%, matching the exact analytic relaxation; blocked cell
inventories stay fixed during continuing outside diffusion. The 8/16/32-volume
continuum errors fall to 0.0059 mM on the finest grid. These are synthetic
numerical witnesses, not measured biological recovery or validated tissue.
The selected 0.125 ms step has passing 0.0625 ms refinement; the old 1 ms
well-mixed step is not a spatial stability or accuracy guarantee. See the result
for the retained rejected trials and completed accuracy failures.

D061 / [CORE-010](SPATIAL_EXTRACELLULAR.md) now implements the passive subset in
the shared CPU/JAX engine. Its development tests compare all state coordinates
and potentials with the preserved numerical reference, and exercise full-state
restart, exact blocking, windows and independent-world cohorts. The
[one-cell example](../configs/spatial_extracellular_cell.json) is a synthetic
numerical fixture, not a new biological experiment. A separately captured and
audited production panel remains required before release acceptance.

## Reference library

Build a small, versioned library from the continuing exploration. Each case
records its equations/source revision, full starting state, geometry, schedule,
solver and sampling settings, outcome definition, and expected comparison.
Source results are identified in [Scientific basis](SCIENTIFIC_BASIS.md).

These assays are clients of Cells' mechanisms and experiment interfaces, not
branches in its solver. The [engineering gate](ENGINEERING_GATE.md) now verifies
independent reaction/transport composition before source-selective coupling;
[CORE-003 acceptance](../reports/CORE003_ACCEPTANCE.md) records that result. It
does not execute or establish correspondence with the source's coupled assays.
Keep engineering invariants, numerical-reference checks, and scientific outcome
comparisons distinct; none substitutes for the others. Experimental success is
not a reason to tune generic engine behaviour to a case ID or expected label.

| Assay | Purpose | Required comparison |
| --- | --- | --- |
| E01: isolated regulation | Verify intracellular equations and state handling | Prepared E/M states, continuous trajectories, primary/derived consistency |
| E02: selective contact | Verify reciprocal communication | Active/blocked exchange, appropriate flux accounting, selected source switching cases |
| E03: write and release | Separate acquisition from retention | Cue exposure, cue removal, isolated continuation, naive/same-state/blocked controls |
| E04: commitment | Detect hidden differences within a coarse phenotype | Same-labelled six/eight-contact checkpoints and declared component substitutions |
| E05: onward relay | Separate retention from transmission and renewal | Fresh opposite-state recipients, ordinary-state controls, pair/single/blocked conditions |
| E06: rewriting context | Separate group effects during exposure and readout | H2 source reproduction first; a crossed exposure-width/readout-width extension later |

E01 completion (2026-09-08): the source's isolated regulatory subsystem was checked
at 36 derivative/binding probes and two 10000-unit E/M trajectories, with independent
Radau/BDF references, RK4 refinement, and complete model-specific replay. This is
not yet ionic or contact validation, attraction-basin mapping, or a proof of
memory robustness. See [M1b acceptance](../reports/M1B_ACCEPTANCE.md).

E02 partial completion (2026-09-08): two unequal-volume cells exchange a synthetic
quantity through a retained physical contact, with active/blocked, release,
off-grid pulse, conservation, reference/refinement, and exact-restart checks.
This completes M1c-a's passive transport prerequisite, not the selective source
switching cases. No ions, voltage, or regulatory coupling are present in this
fixture. See [M1c-a acceptance](../reports/M1C_A_ACCEPTANCE.md).

E02 correspondence update (R005): [native instantaneous contact probes](SOURCE_COUPLING_MAP.md)
now identify the source's algebraic gates, upwind drift, voltage orientation and
miRNA tracer approximation. The memory harness and voltage-gated cancer cases
use different switches. These checks do not complete E02 trajectories; the
separately implemented [physical gated pair](BIOELECTRIC_PAIR.md) must not be
presented as a source-assay reproduction.

E02 engineering update (MODEL-005): [bitsey_emt_pair@1](SOURCE_EMT_PAIR.md) now
couples complete ionic/regulatory state on the shared JAX engine, with 14 frozen
short-horizon reference cases, independent route controls, exact replay and
future branching. This validates the bounded source-compatible mechanisms, not
the longer source switching protocols or all cancer-expression strategies.
Those protocols need explicit source/preparation/outcome pinning and long-time
numerical checks; no paper-table or biological memory result is claimed.

E02 protocol update (SPEC-004): [E02-SW1](E02_SWITCHING_PROTOCOL.md) now freezes
fresh isolated 500-unit full-state preparation and 1000-unit contact, two
directions and seven conditions each. The primary three-cell star requires a
general fixed-graph source extension; the existing pair is a control, not a
substitute. [NUM-005](E02_SWITCHING_NUMERICS.md) must qualify the preparation,
long-time references and numerical candidate before production assay execution.
This independent source-equation assay differs explicitly from the native
historical helper's preparation/sampling; it is not a threshold reproduction.
No new trajectory, switching result or post-removal memory is established.

E02 reference update (NUM-005a): [independent fixed-graph composition](SOURCE_EMT_GRAPH_REFERENCE.md)
now passes 45 native instantaneous inputs and the existing pair-oracle settings.
The E02 cases in that input panel are construction seeds, not prepared packets.
Those probes do not themselves qualify preparation or longer trajectories.

E02 preparation update (NUM-005b): both fresh isolated 500-unit preparations now
pass Radau/BDF/refined agreement, complete accounting/domain checks and the
specified 400–500 phenotype margins. Full refined E/M packets and provenance
are [retained separately](../reports/NUM005B_PREPARATION.md). Ions continue to
drift despite stable sampled phenotype; equilibrium is not claimed. No connected
condition or switching outcome was measured. NUM-005c must qualify long paths
and candidates, including candidate-owned preparation continuations, before
production graph implementation and assay execution.

NUM-005c1 now provides [long-reference infrastructure](SOURCE_GRAPH_PATHS_REFERENCE.md)
for all 14 cases, using exact qualified packet imports, lossless complete-state
recording and reference-only observers. Its [first session](../reports/NUM005C1_LONG_REFERENCE.md)
reached the one-hour cap with eight qualified conditions and six still incomplete;
no long reference was automatically retried. Independent subset auditing passes.
Any eventual reference label result is separate from production ASSAY-002 and
from the later candidate-owned preparation sensitivity checks. Uncertain labels,
donor changes and full-state drift remain explicit; a positive switch is not a
numerical acceptance criterion.

The [registered continuation](../reports/NUM005C1_CONTINUATION.md) adds qualified
reverse blocked and ionic-only controls, bringing the total to ten. Reverse
miRNA-only fails the unchanged reference agreement limit; no qualified phenotype
outcome is published for it. Same-state, one-neighbour and isolated in that
direction were not started. Independent artifact auditing passes, but does not
resolve the failed accuracy gate. No automatic retry or tolerance change occurs.

The separately authorized [A1 refinement](../reports/NUM005C1_A1_BDF_REFINEMENT.md)
then meets the same agreement target with a tenfold-tighter BDF reference. The
audit confirms the new curve, full union-grid samples and primary/history
scores. No original failed result is reclassified and no qualified miRNA-only
phenotype is published by that diagnostic. An amended reference/observer policy
and the three remaining controls still preceded full-panel acceptance at that stage.

[A2](../reports/NUM005C1_A2_REFERENCE_PANEL.md) now explicitly adopts that reference
and completes the panel: all 14 cases and their reference observers pass the
independent audit. The active and miRNA-only conditions reach the recipient's
target label in both directions; the other five controls do not at the sampled
times. There are no unresolved sampled labels or donor label changes. These
outcomes are readouts, not numerical pass criteria or evidence of full-state
equilibrium. With the equal-ion prepared states, this is not a demonstration of
a voltage-driven mechanism or biological validation. Production ASSAY-002 and
candidate-owned preparation sensitivity remain separate unfinished gates.

The subsequent [D037 candidate engineering profiles](../reports/NUM005C2A_CANDIDATE_ENGINEERING.md)
cover only the first 5.12 units of the six registered study inputs. Their RK4
agreement, exact window/restart evidence and resource measurements pass; they
are not new switching, preparation-equilibrium or candidate-owned continuation
results. The full long-study resource fit and candidate qualification remain
open before production assay execution.

D038's [diagnostic optimization](E02_DIAGNOSTIC_OPTIMIZATION.md) uses the same
six short prefixes, with matched scalar/batched readout policies and full
evidence retained. This is a computational comparison, not a new biological
condition or an additional switching result. The [compact-evidence proposal](E02_COMPACT_EVIDENCE_DESIGN.md)
is not an adopted output policy for any assay.

D039's [lossless recording prototype](E02_LOSSLESS_EVIDENCE.md) continues with
the same six short prefixes and complete comparison evidence. Reconstructed
state/curve identity and checkpoint publication are engineering acceptance
criteria, not new phenotype outcomes. No compact long-assay policy is adopted
by the prototype or its storage measurements.

D040's [comparison-recording prototype](E02_COMPARISON_RECORDING.md) keeps those
same sample clocks and logical comparison states, reconstructing repeated arrays
from candidate/reference evidence with explicit dependencies. Its short profiles
test storage and audit semantics, not new switching conditions or phenotypes.

D041's [integration-evaluation prototype](E02_INTEGRATION_EVALUATION.md) again
uses those same short prefixes. It tests immutable fixed-parameter preparation,
exact complete derivatives, evaluator-specific restart identity and independent
recomputation of every stored stage slope. Its runtime improvement is engineering
evidence only; it adds no switching outcome, biological validation or long-time
candidate qualification.

### E04 extension: matched phenotype, different history

Prepare histories that reach a matched visible phenotype, retaining their full
states and preparation records. Freeze the matching variables/tolerances and
report remaining differences; this is not an assertion of complete-state equality.
Branch each checkpoint into the same future challenges with explicitly paired
randomness, environment, and schedules. Compare response trajectories, commitment,
and collateral changes, not only the final label.

Use declared component substitutions or ablations to distinguish intracellular,
contact, and environmental contributions. Challenge definitions must not expose
the answer to a biological reader. Later slow-state/plasticity modules can be
tested through the same interface, but are not added to the reference model by
assumption. Identical complete deterministic states, parameters, and future
inputs should evolve identically; history cannot act through an undeclared channel.

Begin with the smallest sufficient reference subset. Reproducing every historical
panel is not a prerequisite for building a useful prototype. Positive and negative
cases should exercise the mechanisms on which the next milestone depends.

Reported timing context from the source pilot: a 625-cell case took approximately
100 seconds in-worker, compared with approximately 37 seconds for its matched
25-cell case on that shared CPU host. This is a historical observation, not a
Cells benchmark or a scaling law.

## First 2D demonstration

E07 uses a small fixed 2D contact graph. Its sequence is:

1. Prepare a tissue with specified intracellular states and communication rules.
2. Apply a temporary local cue using explicit donor cells or declared external input.
3. Remove the cue and measure continuous state, visible phenotype, and retention.
4. Change selected communication boundaries and test spread or isolation.
5. Run controlled carrier replacement with ancestry and identity tracking.

Record which cells carry the state, which connections support it, and whether
new recipients actually change from their own starting state. Observe donors as
well as recipients because communication is reciprocal.

The first E07 version uses scripted replacement. Its result can establish finite
renewal under the supplied schedule. A later E08 version adds growth, division,
resources, and endogenous contact formation to test autonomous renewal under
those declared rules.

## Common experimental contract

Before a scientific run, fix the following in a versioned specification:

- The question, model version, observer, outcome horizon, and stopping criteria.
- Initial-state selection, source checkpoints, parameter ranges, units, and topology.
- What is supplied externally: cues, prepared cells, resource reservoirs,
  interventions, and any feedback controller.
- Paired conditions, ordinary-state controls, and mechanism-specific controls.
- Independent replicate units and how dependence within lineages or environments
  enters analysis; saved time points are not independent replicates.
- Random-stream coupling and held-out schedules where confirmation is intended.
- Numerical tolerances, refinement comparisons, resource budget, and output policy.
- Biological boundary rules, including all passed, partitioned, erased, rebuilt,
  and externally retained state; these are separate from restart completeness.
- Mechanism input/output access versus observer access, with any feedback and
  rejected/accepted actions explicitly recorded.
- Observer coordinates, scale, calibration positives/nulls, and scope. A change
  of label definition is an observer revision, not a discovered biological transition.

Exploration and confirmation are separately labelled. Continue valid negative
branches under the declared protocol; any rescue or restart is an explicit arm.
Record extinction, failure to transfer, numerical failure, and finite-horizon
censoring as distinct outcomes.

## Measurements

| Measurement | Operational question |
| --- | --- |
| Full-state trajectory | How do the declared biochemical and ionic coordinates evolve? |
| Phenotype | What does a specified observer classify at a given time? |
| Cue-free retention | Does the acquired state persist after external instruction ends? |
| Commitment | Does the removal checkpoint lead to the retained target without further cues? |
| Transmission | Do carriers change fresh recipients relative to appropriate controls? |
| Renewal | Does that transmissible state continue through actual carrier replacements? |
| Rewriting | Is alternative content acquired, retained, and transmitted? |
| Resistance and recovery | Does a challenge disrupt continuity, and what returns afterwards? |
| Episode coherence | How similar are states across an entire episode, beyond adjacent comparisons? |
| Challenge signature | Do matched visible states respond differently to the same future inputs? |
| Ancestor and family fidelity | What persists relative to a fixed ancestor and across both daughter branches? |
| Cost and benefit | What time, contact, material, or energy assumptions accompany an outcome? |

Track physical time, lineage boundaries, and observation times separately.
Returning to an E/M label is not necessarily return to an identical full state.
Equal nominal contact time or conductance-time is not necessarily equal molecular
delivery; calculate flux-based exposure where supported.

Where renewal is claimed, separate information detectable by an analyst, its
usefulness through an actual reader, and its reconstruction into a fresh carrier.
Choose correct/wrong carrier or recipient, reader-off, writer-off, passive-copy,
and fresh-reconstruction controls as appropriate. Shared support, sensing, writing,
and reconstruction belong in resource accounting alongside transmitted material.
Any deterministic/model-specific evidence is labelled at that scope.

## Later experiments

| Assay | Question | Added requirements |
| --- | --- | --- |
| E08: autonomous renewal | Can acquired organisation survive growth and material turnover? | Partition, resources, division, death, and contact rules |
| E09: memory location | Which cell, edge, group, or environmental states support retention and transfer? | Targeted ablation/rescue and matched context manipulations |
| E10: changing ecology | When does inherited memory help or hurt? | Independently specified benefit/cost functions and fair resource budgets |
| E11: embedded control | Can local sensing and actuation maintain continuity? | Explicit controller embodiment, information access, action limits, and costs |
| E12: scale reduction | Which smaller state descriptions preserve causal behaviour? | Held-out dynamics and intervention comparisons across resolutions |
| E13: first organ function | Can a data-defined model reproduce the selected whole-organ function within scope? | Explicit species/extent/geometry, external support, resolution, omissions, and validation observations |
| E14: interacting organs | Do configured organ instances influence one another through the declared routes? | Generic coupling tests first; disconnected/isolated controls, exchange accounting, delays, and coupled-function validation |

For E10, include constant, slowly changing, rapidly changing, returning, and misleading-cue
environments. Compare rewritable inheritance, ordinary/fixed inheritance, and
equally resourced reactive strategies. A reward constructed from E/M matching
establishes utility only in that constructed ecology.

E09/E11 may test restricted slow-state writing and correlated versus independent
disturbances. These are optional hypotheses about memory protection and coupling,
not biological constraints encoded as successful outcomes.

For E11, distinguish externally chosen interventions from the system's own
actions. Population-level competition and evolution require explicit variation,
selection, reproduction, and inheritance rules beyond the first tissue model.

E12 checks fine/coarse interfaces and alternative time-step rates as well as
state reduction. Report conservation/accounting errors, coupling refinement,
future-response differences, runtime, and memory. Resolution or fidelity changes
must retain relevant slow state and cannot simply replace it with an average label.

E13 follows the simplest useful organ target selected later, not a hard-coded
engine type. E14 creates coupled organs inside one world, distinct from batched
independent worlds. A generic two-compartment transport fixture can verify its
interface before any biological organ result is claimed.

## Performance experiments

P01 compares small isolated-cell and contact calculations with CPU references.
P02 measures batches of independent relay worlds. P03 measures a growing series
of fixed coupled 2D graphs. P04, after lifecycle implementation, measures topology
updates and division under changing population size.
P05 later profiles detailed/coarse regions, process subcycling, and computational
partitioning; P06 profiles coupled organ workloads. These are future tasks, not
large-GPU runs authorised by the architecture note.

For each, report equations, precision, tolerances, population/edge capacities,
batch size, hardware, compilation time, warmed runtime, output overhead, memory,
and scientific agreement. Compare CPU and GPU only on defined workloads with
equivalent accuracy requirements. Hardware-specific numerical differences must
be assessed before a speed result is used to select a scientific configuration.
