# BETSE and related software: design review

Review R004, 2026-09-08 UTC. The user accepted the recommendations from the
[Levin software directory](https://drmichaellevin.org/resources/software.html#BETSE)
and primary-source web review. Outcome: retain Python/JAX and Cells' engineering
boundaries; make the next physical model more explicit about membranes,
environment, charge, energy, and preparation. This is a reviewed design input,
not a BETSE reproduction or a new result from the continuing exploration.

## What was reviewed

The directory's 2016 BETSE date identifies its original publication, not its latest
release. As checked on this date, PyPI's latest published release is 1.5.0,
released 2025-04-15. Publication age alone is not a maintenance assessment.
[Release history](https://pypi.org/project/betse/#history).

Code inspection used BETSE tag `v1.5.0`, revision
`5269a714aa2593ed2a6708c4516289977d8ae1a2`, including the configuration,
cell/membrane mappings, gap-junction gating, and simulator driver. Calculion's
electrochemical-system and reaction definitions were inspected at revision
`9484d2b978e5fc493b0e6fbbe9236e4bc44df359`.
These are source identifiers for read-only inspection, not captured executable
environments. BETSE and Calculion were not installed or run, and no upstream code
was copied into Cells. Other repository observations below are dated reviews,
not pinned imports.

## How strong is the experimental evidence?

| Evidence | What it supports | Boundary to retain |
| --- | --- | --- |
| [Pietak and Levin, 2016: BETSE](https://www.frontiersin.org/journals/bioengineering-and-biotechnology/articles/10.3389/fbioe.2016.00055/full) | Comparison with measured Xenopus oocyte voltage and ion concentrations using experimental membrane permeabilities; reported discrepancies below 10%. Nernst/Goldman checks supply additional physical sanity tests. | A bounded physiological comparison, not whole-organ validation or independent confirmation of every mechanism. |
| [Pai et al., 2018: HCN2 rescue](https://pmc.ncbi.nlm.nih.gov/articles/PMC5843655/) | BETSE predicted disruption of a Xenopus neural voltage pattern by nicotine and a context-dependent rescue through HCN2. Subsequent voltage mapping and experiments on brain morphology and learning supported the intervention. | The simulation represented a stage-15 surface-cell configuration, not a complete brain or a learning model. HCN2-alone hyperpolarization was about 30 mV predicted versus 15 mV observed. |
| [Pietak et al., 2019: planarian axis control](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1006904) | PLIMBO combined regulatory dynamics and directed morphogen transport; fragment experiments supported novel axial-pattern predictions, including rotated regeneration. | PLIMBO is a separate 1D/2D finite-volume application using BETSE and other components, not simply an unmodified BETSE run. Its particular transport hypotheses are not universal biological laws. |
| [Pietak and Levin, 2017: bioelectric gene/reaction networks](https://pmc.ncbi.nlm.nih.gov/articles/PMC5636277/) | Computational examples couple regulation, reactions, channels, and pumps, including feedback and hysteresis. | In-silico mechanism demonstrations are a different evidence tier from new wet-lab prediction tests. |

Our inference: BETSE is a useful physics and reference-case source with genuine
connections to experimental work. None of this validates Cells automatically.
Keep equation checks, numerical agreement, source reproduction, and biological
prediction as separately reported achievements. Do not tune a reference mismatch
out of the report or treat anatomical success as exact trajectory agreement.

## Architectural lessons accepted for Cells

The first column identifies source observations; the other columns are our
engineering choices, not claims that BETSE already implements Cells' contracts.

| Source observation | Cells decision now | Extension when exercised |
| --- | --- | --- |
| BETSE distinguishes cells, membrane surfaces, and extracellular sites in its [geometry arrays](https://github.com/betsee/betse/blob/v1.5.0/betse/science/cells.py). | Give a membrane its own identity, endpoint mapping, area, and capacitance; keep volume separate. Start with one lumped membrane. | Multiple surfaces, separate facing compartments, geometry, and cell-field mappings; no dense all-cell matrix required by the interface. |
| The physiological papers distinguish extracellular conditions and transmembrane exchange. | Declare a maintained external bath and signed exchange accounting. It is an externally supported boundary, not an unlimited invisible intracellular source. | Finite reservoirs and spatial fields with their own state, charge closure, and conservation checks. |
| BETSE has [dynamic and instantaneous gap-junction gates](https://github.com/betsee/betse/blob/v1.5.0/betse/science/channels/gap_junction.py). | Separate physical adjacency, experiment-imposed inhibition, and endogenous gate state. Do not use one field for all three. | Checkpoint evolving gates and test their time units and history dependence when introduced. |
| BETSE's [configuration](https://github.com/betsee/betse/blob/v1.5.0/betse/data/yaml/sim_config.yaml) distinguishes preparation from simulation and provides an equivalent-circuit fast mode that omits ionic/field variables. | Make preparation an explicit recorded protocol. Separate physical approximation, solver, and device; reject unsupported requests instead of silently ignoring them. | Capability declarations for ionic, circuit-only, and field models; complete preparation checkpoints and validated reductions. |
| Calculion includes ion electrochemical potentials and ATP-coupled transport in its [system](https://github.com/betsee/calculion/blob/9484d2b978e5fc493b0e6fbbe9236e4bc44df359/calculion/science/bioe_system.py) and [reaction definitions](https://github.com/betsee/calculion/blob/9484d2b978e5fc493b0e6fbbe9236e4bc44df359/calculion/science/chem_base.py). | Specify ion amount, charge, voltage closure, and external chemical drive together. Check passive dissipation and pump stoichiometry before trajectories. | Explicit ATP/resource pools and calibrated pump kinetics only with their own contracts. |
| PLIMBO needs directed transport, not diffusion alone. | Keep conservative accumulation separate from the transport law; a signed flux can come from an explicitly directional mechanism. | Advection or carrier transport with declared polarity, energy assumptions, and appropriate discretization. |
| BETSE's inspected [driver](https://github.com/betsee/betse/blob/v1.5.0/betse/science/sim.py) uses mutable simulation state and retained trajectory collections. | Retain Cells' pure array kernels and strict snapshots; profile state, scratch, and output separately. | Sparse/local operators and bounded streaming before large tissue/GPU workloads. Do not port a full object graph or unbounded trajectory history onto a GPU. |

The one-cell charge closure and phenomenological pump law in the
[new specification](BIOELECTRIC_CELL_SPEC.md) are our deliberately limited
engineering model. They are not copied BETSE/Calculion equations or a calibrated
replacement for their complete physiology. Specific physical simplifications
must have their own validity and reference checks.

For scale, the 2016 paper's roughly 10,000-cell/14 GB fully enabled example is
historical context only. It is neither a current BETSE benchmark nor a Cells
GPU sizing estimate. Organ feasibility requires measurements of solver work,
fields, state, and output at equivalent accuracy.

## Other software worth retaining as references

| Tool | Potential use | Boundary before adoption |
| --- | --- | --- |
| [Calculion](https://github.com/betsee/calculion) | Closest conceptual companion for the one-cell electrochemical reference. | Inspect assumptions and create a compatible reference capture; no runtime dependency now. |
| [SBMLtoODEjax](https://github.com/flowersteam/sbmltoodejax) | Possible adapter for independently validated intracellular ODE modules. | Its documented unsupported events, restricted expressions, and solver limitations rule out a universal SBML-import promise. Imported RHSs must not take over Cells' scheduling, state, or units. |
| [Cellnition](https://github.com/betsee/cellnition) | Offline regulatory response/transition maps; useful for our observer and challenge-signature work. | Its [documentation](https://betsee.github.io/cellnition/) distinguishes computational demonstrations from real-world validation. Review its repository's noncommercial/academic licensing rider before any reuse; do not assume an unrestricted Apache-only grant. |
| [NeuralPlatePatterning](https://github.com/santamanicka/NeuralPlatePatterning) and [ElectricMorphogenesis](https://github.com/santamanicka/ElectricMorphogenesis) | Later bioelectric/regulatory and tissue-field reference models. | Their reduced representations are model choices, not reasons to replace our backend or equate a voltage pattern with a complete organ. |
| [BETSEE](https://github.com/betsee/betsee) | Reinforces a separate GUI over a headless simulation library. | No viewer dependency or GUI implementation in this slice. |
| [PyInform](https://github.com/elife-asu/PyInform) | Optional read-only information-theoretic analysis. | Specify estimator, sampling, nulls, and interpretation separately from the dynamics. |
| [Growing neural cellular automata](https://distill.pub/2020/growing-ca/) | Local-update and regeneration/challenge experiments. | Learned toy dynamics do not supply missing physical cell equations. |
| [EDEn publication](https://www.sciencedirect.com/science/article/pii/S2589004218302323) | Later channel/expression/modulator data discovery. | A database entry is a lead to experimental provenance, not automatically a current calibrated parameter. |

## Delivery and next implementation

[D018](DECISIONS.md#d018-bioelectric-interfaces-and-a-one-cell-physical-contract)
records the accepted refinements. [BIOELECTRIC_CELL_SPEC.md](BIOELECTRIC_CELL_SPEC.md)
defines one cell, one membrane, three ions, a maintained bath, passive leaks, and
an externally energized reversible reference pump. An independent calculator
checks instantaneous limits and identities; it does not integrate the model.

The subsequent NUM-002 and MODEL-003 builds establish independent trajectories,
a bounded numerical domain, and the small production model through Cells'
composition, control, observer, and checkpoint boundaries; see the
[implementation guide](BIOELECTRIC_CELL.md). A later pinned BETSE comparison
must select genuinely corresponding equations, parameters, and approximations;
the new synthetic fixture must not be labelled a BETSE reproduction.
No libraries, source-assay campaigns, continuing-agent jobs, or GPU work were
launched by this review.
