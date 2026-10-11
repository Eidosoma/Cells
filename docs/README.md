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
| [Scientific basis](SCIENTIFIC_BASIS.md) | Research provenance, hypotheses and the limits of source and experimental evidence |
| [Roadmap](ROADMAP.md) | Development priorities, dependencies and completion criteria |
| [Experiment programme](EXPERIMENTS.md) | Proposed memory and relay assays; implementing their prerequisites does not establish an assay result |

## Models and execution

- [GPU execution and ensembles](GPU_ENSEMBLES.md): local CPU/L4 support,
  independent workers, telemetry, checkpoints and the planned Jupiter path.
- [Protein assembly](CAPSID_ASSEMBLY.md): stochastic cages, finite pools,
  breakable bonds and experimental assembly-to-cell coupling.
- [Tissue electrical models](TISSUE_RETURN_CURRENT.md): cross-region return
  currents, resolved membranes and native BETSE comparison components.
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
Numerical qualification, native BETSE agreement and biological validation are
separate claims. L4 results do not establish Jupiter or multi-node scaling.

Paths under `/mnt/workspaces` and older `runs/` references identify local evidence
outside this checkout. They are not public downloads. Repository reports and
protocols provide the readable scope; the original artifacts retain the detailed
inputs, results, failures and hashes. External research-tree paths in the source
catalogue are provenance records, not bundled manuscripts.
