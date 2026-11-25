# Cells documentation

Start with the design guides below, then choose a model guide for the mechanism
you want to run. [PROGRESS.md](../PROGRESS.md) owns current run status and evidence;
the [project README](../README.md) gives the short feature overview.

## Design and direction

| Guide | What it explains |
| --- | --- |
| [Architecture](ARCHITECTURE.md) | State ownership, numerical execution, experiments, checkpoints and outputs |
| [Inner model design](INNER_MODEL_V4_DESIGN.md) | D172's one modular inner model (`resolved_pump_tissue@3`): declared laws, dispatch per declared structure, kinds and the results gate. Landed on 16 November 2026 |
| [Scoped composition (door S)](SCOPED_COMPOSITION_DESIGN.md) | How operators change and read slots of one view field, admitted per slot and merged in declared order. Landed with D172's round |
| [Module system design](MODULE_SYSTEM_DESIGN.md) | External and contributed modules: one registration path, a conformance kit and stages set by real consumers. Proposed, with its five decisions made by the user (D185) |
| [Run view design](RUN_VIEW_DESIGN.md) | The `view.json` record that makes every run visualizable (D154). Proposed; its writer is on main since 16 November |
| [Current plan](CURRENT_PLAN.md) | The current order, adopted 12 November 2026 (D145): gates and their completion evidence, after two architecture reviews |
| [Composite tissue model](PUMP_COMPOSITE.md) | `resolved_pump_composite@1`: `@3`'s step plus declared operators (water, symport, replacement), its contract and its bitwise guards |
| [Composite v2 design](PUMP_COMPOSITE_V2_DESIGN.md) | Reviewed design before code: declared energy roles, observation ownership, cross-operator writes, membrane state (S2), current injection, the L4 agreement protocol |
| [Architecture review notes](ARCHITECTURE_REVIEW_NOTES.md) | Read-only review of 12 November 2026: two coexisting designs, the operator contract, the GPU-native scope, execution paths and candidate follow-ups (for review) |
| [Multiscale composition](MULTISCALE_DESIGN.md) | How cells, regions and future organs compose without confusing membership with physical exchange |
| [Parallel execution architecture](MULTISCALE_EXECUTION_ARCHITECTURE.md) | Resolution, coupled clocks, device placement and the requirements for future distributed tissues |
| [BETSE capability coverage](BETSE_CAPABILITY_ROADMAP.md) | Implemented subsets, reference correspondence and remaining mechanism gaps |
| [BITSEY replication](ROADMAP.md#bitsey-replication) | Regulatory/ionic reference and planned reproduction of the *How Patterns Return* lineage experiments |
| [Scientific basis and calibration plan](SCIENTIFIC_BASIS.md#calibration-across-the-cells-stack) | References across the stack, future cell/organ data resources and the limits of model and experimental evidence |
| [Roadmap](ROADMAP.md) | Development priorities, dependencies and completion criteria |
| [Experiment programme](EXPERIMENTS.md) | Proposed memory and relay assays; implementing their prerequisites does not establish an assay result |
| [E07-v1 renewal-stage design](E07_V1_DESIGN.md) | Registered by the lead on 13 November 2026: donor copies with state-blind donors, an isolated threshold-finding set, the copy-only null, and composite v2's decision 4 for donor copies |
| [Secreted-species transport design](SECRETED_SPECIES_TRANSPORT_DESIGN.md) | Accepted design (D150): secreted species as rows of @3's one inventory, moved by @3's faces, with turnover and exchange operators; version 1 landed on 14 November and is numerically qualified for transport, decay and clearance |
| [Shared-inventory reactions design](SHARED_INVENTORY_REACTIONS_DESIGN.md) | Accepted 14 November 2026 (D152): local reactions on @3's species rows, with exact energy bookings and MG0c's Turing qualification; its operator, `local_species_reactions@1`, is numerically qualified within MG0c's scope (15 November, CPU only) |
| [Feature requests](FEATURE_REQUESTS.md) | Requested engine features with priority and status. FR-1, a closed internal compartment on the shared inventory, is high priority (D157) |
| [Closed compartment design](CLOSED_COMPARTMENT_DESIGN.md) | FR-1's cell-owned compartment and its refusals (refusal 4 to version 1.3, refusal 5 to version 1.2, and refusal 6 to version 1.1, 25 November) |
| [Calcium store and channels design](CALCIUM_STORE_AND_CHANNELS_DESIGN.md) | Calcium-permeant channels, a store with its own capacitor, its pump, leaks and gated release, the sodium-calcium exchange, and the step rules they need; built 25 November 2026, not judged ([the short version](ARCHITECTURE.md#what-the-calcium-store-adds)) |
| [Site occupancy design](SITE_OCCUPANCY_DESIGN.md) | FR-3's binding to sites (`site_occupancy@1`) |
| [Bath schedule design](BATH_SCHEDULE_DESIGN.md) | Scheduled changes of bath composition |
| [Inventory coupling design](INVENTORY_COUPLING_DESIGN.md) | Coupling out of the shared inventory (D155, D156) |
| [Compartment pH and transfer design](COMPARTMENT_PH_TRANSFER_DESIGN.md) | FR-4's compartment acidification and FR-5's transfer across a damaged membrane |
| [Excitable tissue design](EXCITABLE_TISSUE_DESIGN.md) | Track E: conduction in excitable tissue (D155, D170) |
| [Human cardiac laws design](HUMAN_CARDIAC_LAWS_DESIGN.md) | The human ventricular law set (D183, D184): proposed, nothing built |
| [Syn3A minimal-cell track](SYN3A_MINIMAL_CELL_TRACK.md) | JCVI-syn3A as the first whole cell: evidence audit and probes, no engine code |
| [Origin of life: state of the art](SOTA_ORIGIN_OF_LIFE.md) | Two reviews of a November 2026 overview of origin-of-life research, read for Cells: resemblance, function and renewal measured apart; every descendant tracked; founder material traced; SpudCell and Otto-type replicators as candidate benchmarks (D199) |
| [Syn3A state of the art](SOTA_SYN3A.md) | Why JCVI-syn3A is the first whole-cell validation organism, and its public measurements |
| [Operator composition design](OPERATOR_COMPOSITION_DESIGN.md) | Operators that read each other's current state: one general rule, option A (D191, 16 November 2026); built in D194's step 3 |
| [GARD design](GARD_DESIGN.md) | Catalytic assemblies, exchange, fission and lineage for the origin-of-life track (D192); the kernel finding's scope is in §2.5 |
| [Origin-of-life engine design](ORIGIN_OF_LIFE_ENGINE_DESIGN.md) | Cells' own first-principles engine (D197): laws as detailed-balanced event pairs from one free energy, physical assemblies, declared energy sources, division by geometry and shear, GARD as a declared limit. Proposed, options for the user |
| [Mitochondria design](MITOCHONDRIA_DESIGN.md) | One law set for mitochondria and bacteria, Beard 2005 as the source (D193) |
| [Core laws roadmap](CORE_LAWS_ROADMAP.md) | The core law families' status and ordering options, and mitochondria readiness; Option 2 chosen (D234) |
| [Gene regulation design](GENE_REGULATION_DESIGN.md) | Expression as templated polymerisation with one material and energy account; option A approved (D235), its build plan in §7: the neutral reduction registered first, the charged form later as its own arm; nothing built |
| [Molecular machines design](MOLECULAR_MACHINES_DESIGN.md) | FR-13: machines individually and in aggregate, at a level declared per run; M0 now, then M1 (ATP synthase) with its build plan (D209) |
| [Core seams design](CORE_SEAMS_DESIGN.md) | D194 step 2's one pass: the cycle kind, populations, binding, heat booking, laws as modules and the run view's format items, with the order and the estimate. Proposed |
| [Relationships design](RELATIONSHIPS_DESIGN.md) | D200: descent, material provenance (labels), dependence and history, written as plain node and edge tables so that lineage, flow, dependency and branch graphs are joins. Proposed, options for the user |
| [Law documentation design](LAW_DOCUMENTATION_DESIGN.md) | One plain-language Markdown page for each law, kind, operator and model, keyed by its ID, with a template that opens in words for every field, declared facts generated from the manifest, a glossary, the manifest's format page and the viewer's links; three pilot pages. Proposed |
| [The library of pages](library/README.md) | The plain-language pages themselves: one per law, kind, operator and model, with [the template](library/TEMPLATE.md), [the glossary](library/GLOSSARY.md) and [the declarations manifest's format](library/DECLARATIONS_FORMAT.md) (`cells.declarations@2`). First landing (D203): three pilot pages; the rest follow in batches |
| [Looping replay design](LOOPING_REPLAY_DESIGN.md) | FR-11's looping replay packages: the loop block and its closure measure (ruled 16 November 2026) |
| [Device row checks design](WINDOW_DEVICE_CHECKS_DESIGN.md) | Device-resident row checks for scalar windows, opt-in on the CPU, and the vector path's seams |
| [Test audit retire list](TEST_AUDIT_RETIRE_LIST.md) | D187's audit: the firm, held and candidate retirements, approved in D189 |
| [Packed GPU execution design](PACKED_GPU_EXECUTION_DESIGN.md) | Packing independent worlds on one GPU, and its qualification criterion |
| [E15 pattern-recovery experiment path](EXPERIMENT_PATH_PATTERN_RECOVERY.md) | Backlog, not active (13 November 2026): the engine features needed to test which layers restore a pattern after damage rather than only generating it, and a version 0 as E07-v2 arms |
| [Paper backlog](PAPER_BACKLOG.md) and [GRN wet-lab validations](GRN_WETLAB_VALIDATION.md) | Papers under test, and gene-network models validated against experiments (logged) |
| [Protein catalogue plan](PROTEIN_CATALOGUE_PLAN.md) | Path to protein identities linked to atlases (UniProt, Human Protein Atlas, PDB, Reactome) |

## Models and execution

- [GPU execution and ensembles](GPU_ENSEMBLES.md): local CPU/L4 support,
  independent workers, telemetry, checkpoints and the planned Jupiter path.
- [Protein assembly](CAPSID_ASSEMBLY.md): stochastic cages, finite pools,
  breakable bonds and experimental assembly-to-cell coupling.
- [BITSEY regulation](EMT_REFERENCE.md) and [coupled pair](SOURCE_EMT_PAIR.md):
  the existing bounded models behind the planned lineage replication.
- [Tissue electrical models](TISSUE_RETURN_CURRENT.md): cross-region return
  currents, resolved membranes and native BETSE comparison components.
- [Shared channel catalog](TISSUE_RETURN_CURRENT.md#hcn-leak-and-fixed-camp-variants):
  56 sodium, potassium, HCN, calcium and leak laws, including owned calcium/ER,
  finite-fuel and assembly-control compositions. Component correspondence,
  integrated qualification and experimental calibration remain distinct.
- [Legacy calcium-sensitive potassium](CALCIUM_ACTIVATED_POTASSIUM.md):
  a free-calcium/voltage equation with explicit source units and container
  limitations, now [composed with tissue, owned calcium and finite fuel](TISSUE_RETURN_CURRENT.md#calcium-sensitive-potassium-with-the-shared-catalog).
- [Morris–Lecar channels](MORRIS_LECAR_CHANNELS.md): five dynamic and eight
  instantaneous source laws, with explicit physical clocks, state contracts
  and shared tissue/calcium/fuel composition.
- [Channel catalog with compliant water](TISSUE_RETURN_CURRENT.md#shared-channel-catalog-with-compliant-water):
  all 53 laws use current compartment concentrations, with conservative water
  flow and separate water/gate timestep bounds.
- [Channel catalog with prescribed repair](TISSUE_RETURN_CURRENT.md#shared-channel-catalog-with-prescribed-repair):
  all 53 laws with owned calcium/ER, Na/K injury leakage and explicit resealing;
  fixed geometry and one-way assembly control.
- [Channel catalog with finite fuel and water](TISSUE_RETURN_CURRENT.md#shared-channel-catalog-with-finite-fuel-and-water):
  all 53 laws with owner-local ATP/ADP/Pi, explicit supply and current-volume
  concentrations; pool osmotic particles and mixing energy are counted once.
- [Owned calcium/ER with compliant cytosol](TISSUE_RETURN_CURRENT.md#owned-calcium-and-er-with-compliant-cytosol):
  shared chemical/water volume, fixed ER, one count per chemical particle and
  joint mixing, binding, capacitor and water energy accounting.
- [Owned calcium, finite ATP and water](TISSUE_RETURN_CURRENT.md#owned-calcium-finite-fuel-and-compliant-water):
  Na/K, plasma-calcium and ER pumps share one live fuel pool and cytosol volume;
  chemistry and fuel each contribute their osmotic particles and energy once.
- [Prescribed repair with calcium, ATP and water](TISSUE_RETURN_CURRENT.md#prescribed-repair-with-owned-calcium-finite-fuel-and-water):
  Na/K injury leakage reads the live volumes and preserves all shared owners;
  structural resealing remains prescribed. Development evidence is in Progress.
- [Shared fuel with owned calcium](TISSUE_RETURN_CURRENT.md#shared-finite-energy-with-owned-calcium-and-assembly):
  Na/K, PMCA and ER pumps share finite ATP/ADP/Pi, with explicit regeneration
  and internal pump-work accounting; assembly control remains one-way.
- [Finite mitochondrial ion/voltage coupling](TISSUE_RETURN_CURRENT.md#finite-mitochondrial-ion-and-voltage-coupling):
  passive internal exchange with actual cytosolic owners, capacitor energy and
  heat, composed with calcium/ER, finite fuel and configured plasma transport.
  [Mitochondrial cuts](TISSUE_RETURN_CURRENT.md#cell-removal-with-mitochondrial-owners)
  retain organelle inventories and paired internal charge; qualification is in Progress.
  Respiration and ATP synthesis remain outside this law.
- [Water-aware cuts](TISSUE_RETURN_CURRENT.md#cell-removal-with-compliant-water-and-finite-fuel):
  actual cytosol/exterior volumes and concentrations survive, while compliance
  references, pressure laws and all transfer/work histories stay explicit.
- [Live network regulation](TISSUE_RETURN_CURRENT.md#live-network-regulation-of-pumps-channels-and-junctions):
  bounded factors read actual free ions and finite fuel to regulate existing
  pumps, shared channels and junctions; public qualification is tracked in Progress.
  [Regulation-aware cuts](TISSUE_RETURN_CURRENT.md#cell-removal-with-live-network-regulation)
  preserve surviving rule order, physical sample owners and regulated fields.
- [Initial tissue geometry](TISSUE_GEOMETRY.md): prepare passive tissue from
  recorded native meshes with explicit physical measures and portable replay.
- [Static tissue-profile preparation](TISSUE_RETURN_CURRENT.md#static-tissue-profile-preparation):
  bind native regional profiles to resolved membrane/junction permeability using
  explicit physical thickness and owner maps, with a JSON/CLI preparation and replay interface.
- [Explicit INIT-to-SIM preparation](TISSUE_PHASES.md): carry passive, active or
  complete calcium/fuel inventories, intrinsic gates and accounting history into
  a new phase clock, with complete replay.
- [Scheduled active membrane profiles](TISSUE_RETURN_CURRENT.md#scheduled-active-membrane-profiles):
  apply regional background-permeability pulses while preserving channels, pumps,
  intrinsic gates, phase clocks and full transfer history.
- [Scheduled profiles with calcium and finite fuel](TISSUE_RETURN_CURRENT.md#scheduled-membrane-profiles-with-calcium-stores-and-finite-fuel):
  distinct models retain calcium/ER stores, buffers and ATP pool ownership;
  qualification is tracked in Progress.
- [Cell removal and continuation](TISSUE_RETURN_CURRENT.md#cell-removal-and-absolute-time-continuation):
  conservative passive tissue cuts, [active channel/pump cuts](TISSUE_RETURN_CURRENT.md#cell-removal-with-channels-and-maintained-fuel-pumps)
  and [owned calcium/ER cuts](TISSUE_RETURN_CURRENT.md#cell-removal-with-owned-calcium-and-er-stores),
  rebuilt electrical fields and complete archives retaining the original clock.
- [Two-task readout assay](TWO_TASK_READOUT_ASSAY.md): cue location and timing
  read from shared tissue trajectories, with frozen calibration and controls.
- [Compartment chemistry](COMPARTMENT_REACTIONS.md), [ER calcium](ER_CALCIUM.md),
  [spatial calcium](SPATIAL_CALCIUM.md) and [plasma calcium/IP3](PLASMA_CALCIUM.md):
  named model versions, ownership, equations and their synthetic test domains.
- [Finite exterior](FINITE_EXTRACELLULAR.md) and
  [spatial exterior](SPATIAL_EXTRACELLULAR.md): the earlier ionic model families.
- [Independent worlds](INDEPENDENT_WORLDS.md),
  [windowed execution](WINDOWED_EXECUTION.md) and
  [windowed cohorts](WINDOWED_WORLDS.md): the original shared-runner contracts.
  Later model and GPU guides state their supported extensions.

## Research and historical records

- [Reading list, 13 November 2026](SOTA_READING_LIST_FROM_ROBERT.md): the research brief's
  papers, with their links.
- [CCI-seq review](PAPER_REVIEW_CCI_SEQ.md) and
  [mitochondria review](PAPER_REVIEW_MITOCHONDRIA.md) record proposed uses of
  literature; they are not completed simulator validations.
- [Quantum birthmarks review](PAPER_REVIEW_QUANTUM_BIRTHMARKS.md) proposes
  classical history/readout tests inspired by a quantum theory and simulation
  paper, with explicit limits on biological and heredity claims.
- [Ion channel compensation review](PAPER_REVIEW_CHANNEL_COMPENSATION.md)
  examines Hazan and Levin's search methods, released GPU benchmark and
  possible functional-recovery experiments in Cells.
- [Cortical culture learning review](PAPER_REVIEW_CORTICAL_LEARNING.md) adds a
  future wet-lab benchmark for learning, persistence and error recovery, with
  data requirements, experimental limitations and missing simulator features.
- [T cell organelle coordination review](PAPER_REVIEW_T_CELL_ORGANELLES.md)
  proposes tests for calcium-linked clustering, directed delivery and imaging
  metrics, with explicit data and model prerequisites beyond BETSE parity.
- [Partial reprogramming review](PAPER_REVIEW_PARTIAL_REPROGRAMMING.md) reads Washizu et
  al.'s bioRxiv preprint for Cells: no engine feature, and write–clear–challenge rules for
  cue experiments.
- [Granzyme K and tissue ageing review](PAPER_REVIEW_GZMK_AGEING.md) checks a supplied
  secondary assessment and places a secreted-protease ageing module against the gates.
- [Kinetochore protein counts review](PAPER_REVIEW_KINETOCHORE_COUNTS.md) reads Hirano et al.'s
  FCS-calibrated counts as an abundance-evidence standard for the protein catalogue.
- [Bone mechanosensing review](PAPER_REVIEW_BONE_MECHANOSENSING.md) reads Zhang et al.'s abstract
  for Cells: mechanically gated conductance and state-dependent secretion as deferred features.
- [Gap-junction cancer replication](GAP_JUNCTION_CANCER_REPLICATION.md) specifies Grodstein,
  Mathews and Levin's bioRxiv preprint, runs its linear model (as written and as its Norton
  equivalent) and its 1D "neither" condition on the engine, and lists the engine features its
  tissue simulations need (development, not judged).
- [GJ-L1, the linear model's registration](GJ_LINEAR_REGISTRATION.md) registers the linear model's
  judged comparison against code-blind references (D219): its arms, error terms, verdicts, retry
  and planted failures, with its reader (D308).
- [GJ-N1, the "neither" threshold's registration](GJ_NEITHER_REGISTRATION.md) registers the
  threshold comparison on BITSEY's line (not blind) and its 25x25 field (a true pre-registration):
  refinement, the half-step convergence condition and agreement with an independent integration,
  with its reader and the pinned BITSEY runner, whose runs are reported, never judged.
- [Self-replicator selection replication](SELF_REPLICATOR_SELECTION_REPLICATION.md) specifies Liu
  et al.'s Darwinian selection of photocatalytic self-replicators (Nature Catalysis 2025) for the
  origin-of-life engine: the targets registered before any run, the mapping, the features the engine
  lacks, and the plan after OL3 (D220).
- [Decisions](DECISIONS.md) preserves dated design choices and stable decision IDs.
- [Development history](DEVELOPMENT_HISTORY.md) contains the milestones moved
  out of the project README.
- [Historical planning snapshots](history/) preserve superseded roadmap text.
- [Acceptance reports](../reports/) and [validation code](../validation/)
  retain the protocols, results and failed attempts behind scoped claims.

## Reading scope and status

The main design and coverage entry points were reviewed against the checkout and
recorded results on **2026-10-11**. Architecture documents distinguish implemented
building blocks from target interfaces. Older implementation notes are labelled
as history; their test counts and statements about future work apply to their
original stages.

Versioned model guides and frozen specifications describe a particular model,
source revision and numerical domain. A restriction in an older version is not
automatically a restriction on every Cells model. Consult its successor guide
and Progress before interpreting a historical "next" or "planned" statement.
Numerical qualification, native BETSE/BITSEY agreement and biological validation are
separate claims. L4 results do not establish Jupiter or multi-node scaling.

Paths under `/mnt/workspaces` and older `runs/` references identify local evidence
outside this checkout. They are not public downloads. Repository reports and
protocols provide the readable scope; the original artifacts retain the detailed
inputs, results, failures and hashes. External research-tree paths in the source
catalogue are provenance records, not bundled manuscripts.

## Capability overview and planned resources (moved from the project README)

**Historical overview.** Moved from the project README on 11 November 2026,
unchanged except for link paths and heading levels. It describes the project before
the 8 November reset; its "In progress" and "Planned" parts are out of date. The
README now carries a short current summary, and [Progress](../PROGRESS.md) holds the
current status.

### References and calibration

We draw on several sources, each serving a particular part of the simulator:

| Part of Cells | Reference and role |
| --- | --- |
| Bioelectric layer | [BETSE](BETSE_CAPABILITY_ROADMAP.md) provides scientific inspiration and a calibration and verification instrument for electrical transport, channels, pumps, junctions and fields. |
| Regulation and cellular-state transmission | [BITSEY](ROADMAP.md#bitsey-replication) supplies regulatory/ionic reference models; reproducing the Forms paper's writing, retention and replacement experiments is the first assay target. |
| Protein-cage assembly | [Asor et al.'s mass-photometry study and stochastic model](CAPSID_ASSEMBLY.md) underpin the assembly branch. The paper contains real measurements; fitting Cells to those data remains future work. |
| Physical chemistry and electrodiffusion | [Thermodynamic reaction-network and electrodiffusion references](SCIENTIFIC_BASIS.md#calibration-across-the-cells-stack) guide material, charge and energy accounting and numerical checks. |

Scientific feature parity with BETSE and BITSEY remains a verification goal for
the relevant layers within this broader programme. Comparisons cover declared
models and conditions; experimental calibration requires measured data.

For whole-cell and organ development, the planned resource set includes:

- **Cell physiology and energy:** published models from
  [Physiome/CellML](https://physiomeproject.org/data-repositories/physiome-model-repository)
  and [BioModels](https://www.ebi.ac.uk/training/online/courses/biomodels-quick-tour/what-is-biomodels/),
  alongside the [mitochondrial model and measurement leads](PAPER_REVIEW_MITOCHONDRIA.md).
- **Molecular quantities and locations:** [BioNumbers](https://bionumbers.hms.harvard.edu/aboutus.aspx)
  and the [Human Protein Atlas](https://www.proteinatlas.org/about/introduction),
  with each value traced to its experimental conditions.
- **Tissue composition and anatomy:** [CCI-seq](PAPER_REVIEW_CCI_SEQ.md),
  [Human Cell Atlas](https://data.humancellatlas.org/), and
  [HuBMAP](https://portal.hubmapconsortium.org/)/[Human Reference Atlas](https://humanatlas.io/asctb-tables)
  for cell types, neighbourhoods and spatial organisation.
- **Measured function:** matched experiments on voltage, calcium, ATP, oxygen
  use, transport, growth and mechanical responses; later, organ-level recordings
  from resources such as [PhysioNet](https://physionet.org/about/) where appropriate.

These are candidates for future benchmarks. The first organ and species are
still to be selected; human atlases apply to compatible human targets. Anatomical
or expression data do not by themselves specify transport rates or validate organ
function. See the [calibration plan](SCIENTIFIC_BASIS.md#calibration-across-the-cells-stack)
for source roles, existing evidence and the path to independent experimental tests.

### Current functionality

![Cells today, 11 November 2026: cell electricity; tissue preparation and interventions; calcium, reactions, fuel and water; simple gene control circuits; protein cage assembly; and saving, restarting and comparing runs. Material, charge and energy checks, with CPU and L4 GPU execution. Capabilities vary by model; whole-cell integration is ongoing.](assets/cells-current.png)

- **Electrical cells and tissues:** ion transport, membrane voltage, pumps,
  channels, gap junctions and extracellular fields in selected model families.
- **Tissue geometry:** [prepare passive tissue inputs from recorded BETSE meshes](TISSUE_GEOMETRY.md),
  with explicit volumes, membrane properties and a portable preparation recipe.
- **Regional tissue profiles:** [prepare different membrane transport properties
  and junction barriers](TISSUE_RETURN_CURRENT.md#static-tissue-profile-preparation)
  from explicit geometry for selected tissue, calcium, fuel, water and regulation
  models, with a reproducible preparation recipe. Timed interventions support
  [passive membranes](TISSUE_RETURN_CURRENT.md#scheduled-passive-membrane-profiles)
  and [tissues with active channels and pumps](TISSUE_RETURN_CURRENT.md#scheduled-active-membrane-profiles).
  Passive and active tissues support [carrying initialized state into a new experiment](TISSUE_PHASES.md).
- **Cell removal:** [cut and resume selected tissue models](TISSUE_RETURN_CURRENT.md#cell-removal-and-absolute-time-continuation),
  preserving surviving material, [channel and junction gate states](TISSUE_RETURN_CURRENT.md#cell-removal-with-channels-and-maintained-fuel-pumps)
  and [calcium/ER stores](TISSUE_RETURN_CURRENT.md#cell-removal-with-owned-calcium-and-er-stores),
  with complete prior history.
- **Cell chemistry:** calcium and IP3 signalling, internal compartments and
  chemical reactions, including [passive mitochondrial ion exchange and voltage](TISSUE_RETURN_CURRENT.md#finite-mitochondrial-ion-and-voltage-coupling).
- **Fuel and cell volume:** finite ATP supplies and osmotic water flow, including
  a [combined calcium/ER, ATP and water model](TISSUE_RETURN_CURRENT.md#owned-calcium-finite-fuel-and-compliant-water)
  with [prescribed injury and resealing](TISSUE_RETURN_CURRENT.md#prescribed-repair-with-owned-calcium-finite-fuel-and-water).
- **Regulatory cell state:** BITSEY-based isolated regulation and a bounded
  [two-cell regulatory/ionic model](SOURCE_EMT_PAIR.md).
- **Protein assembly:** stochastic cage formation, finite material pools,
  breakable bonds and experimental coupling to cell models.
- **Repeatable experiments:** checkpoints, restart, branching and independent
  simulation ensembles, with CPU/L4 comparisons and conservation checks.

For GPU ensembles, workers take batches of independent simulations from a shared
queue and save their results and checkpoints. Numerical qualification has used
CPUs and one L4; Jupiter
execution remains to be qualified. Distributing one interacting tissue across
multiple GPUs requires further development. See the
[GPU and ensemble guide](GPU_ENSEMBLES.md).

BITSEY's nominal model clock is kept distinct from physically calibrated time. The
[assembly-to-cell coupling](CAPSID_ASSEMBLY.md) is an experimental modelling
hypothesis.

### In progress

- Combining spatial fields, active membrane transport and dynamic junctions in
  BETSE comparisons.
- Extending verification of the integrated cell, tissue and assembly models.
- Bringing new components into the shared configuration, checkpoint and ensemble
  workflows.
- Qualifying [regional membrane interventions with calcium stores and finite ATP](TISSUE_RETURN_CURRENT.md#scheduled-membrane-profiles-with-calcium-stores-and-finite-fuel).

### Planned

![Where Cells goes next, 11 November 2026: cell water and size control, cell replacement and tissue mechanics are in development. Broader GPU checks and Jupiter runs are planned. Whole cells, organs and organ systems are longer-term goals.](assets/cells-future.png)

The next directions are richer integrated cell physiology, broader BETSE/BITSEY
verification, reproduction of the Forms assays, and Jupiter qualification from
four to sixteen GPUs. Experimental calibration, broader energy and water
coupling, mechanics and organ models extend that programme.
Detailed scope and priorities are recorded in [Progress](../PROGRESS.md) and the
[Roadmap](ROADMAP.md).

### Development history

Earlier milestones, qualification results and retained failures are recorded in
[Development history](DEVELOPMENT_HISTORY.md). See [Progress](../PROGRESS.md)
for current status.

