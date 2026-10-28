# Cells documentation

Start with the design guides below, then choose a model guide for the mechanism
you want to run. [PROGRESS.md](../PROGRESS.md) owns current run status and evidence;
the [project README](../README.md) gives the short feature overview.

## Design and direction

| Guide | What it explains |
| --- | --- |
| [Architecture](ARCHITECTURE.md) | State ownership, numerical execution, experiments, checkpoints and outputs |
| [Multiscale composition](MULTISCALE_DESIGN.md) | How cells, regions and future organs compose without confusing membership with physical exchange |
| [Parallel execution architecture](MULTISCALE_EXECUTION_ARCHITECTURE.md) | Resolution, coupled clocks, device placement and the requirements for future distributed tissues |
| [BETSE capability coverage](BETSE_CAPABILITY_ROADMAP.md) | Implemented subsets, reference correspondence and remaining mechanism gaps |
| [BITSEY replication](ROADMAP.md#bitsey-replication) | Regulatory/ionic reference and planned reproduction of the Forms lineage experiments |
| [Scientific basis and calibration plan](SCIENTIFIC_BASIS.md#calibration-across-the-cells-stack) | References across the stack, future cell/organ data resources and the limits of model and experimental evidence |
| [Roadmap](ROADMAP.md) | Development priorities, dependencies and completion criteria |
| [Experiment programme](EXPERIMENTS.md) | Proposed memory and relay assays; implementing their prerequisites does not establish an assay result |

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
