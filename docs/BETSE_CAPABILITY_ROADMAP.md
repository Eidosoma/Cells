# BETSE calibration of the Cells bioelectric layer

Coverage reviewed against the checkout and recorded results on **2026-10-11**.
This is a capability inventory, not a live run log. [Progress](../PROGRESS.md)
contains the current qualifications and their evidence; the [Roadmap](ROADMAP.md)
defines priorities. The [September planning snapshot](history/BETSE_CAPABILITY_ROADMAP_BEFORE_2026-10-11.md)
retains the earlier inventory, implementation sequence and failed comparisons.

## What the target means

Cells uses BETSE as a reference to calibrate and verify the bioelectric layer
of its broader cell and tissue simulations. This layer connects to chemistry,
protein assembly and other processes within Cells' multiscale CPU/GPU framework.
Reference comparisons, experimental validation and distributed execution each
require their own evidence; reduced models remain selectable.

The reproducible comparison baseline is BETSE **v1.5.0**, commit
`5269a714aa2593ed2a6708c4516289977d8ae1a2`. It is not a moving latest release.
The B01-B17 inventory groups capabilities; every subtype, supported option and
coupled regime still needs explicit coverage. Cells source-compatible components
may retain native update ordering and clock conventions; those choices must not
silently become universal physical laws or replace accepted physical-time models.

Calibration focuses on the selected physical mechanisms, equations and responses.
GUI, plot style, YAML import and legacy serialized-state compatibility are
separate concerns. Experimental agreement requires its own evaluation.

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

**Partial** means that a named subset is implemented or compared. It does not
mean every BETSE mechanism in that row is covered. **Planned** means that the
physical capability is not yet implemented. Linked guides define model versions
and numerical limits; Progress links to the actual passing or failed evidence.

| ID | Scientific capability / source | Implemented scope | Remaining coverage |
| --- | --- | --- | --- |
| B01 | Ions, valence and background charge / B1-B2 | Partial: multispecies cell, finite-exterior, spatial and calcium families with explicit ownership | Broader species/route combinations and parameter regimes require their own checks |
| B02 | Passive membrane electrochemistry / B1-B2 | Partial: physical GHK transport and selected native single-cell/cluster/spatial comparisons; [spatial guide](TISSUE_RETURN_CURRENT.md) | Broader geometries, boundaries and convergence; no arbitrary-regime equivalence |
| B03 | Voltage/ligand-gated channels / B1, B7 | Partial: Kv1.5 and selected [CaV1.2/IP3 routes](PLASMA_CALCIUM.md), with scoped native law or trajectory comparisons | Additional channel/ligand families, kinetic regimes and experimental calibration |
| B04 | Pumps, exchangers and cotransport / B1, B3 | Partial: Na/K pumps including scheduled spatial comparisons; [PMCA and synthetic NCX](PLASMA_CALCIUM.md); [ER calcium pump](ER_CALCIUM.md) | Further transporters, physiological relaxation regimes and finite energetic supply; synthetic NCX is not native BETSE correspondence |
| B05 | Selective, voltage-sensitive gap junctions / B1-B2 | Partial: physical-time junction models and selected native gate and combined spatial pump/channel/junction trajectories | Broader coupled native regimes, connexin diversity and fitted recovery/heterogeneity |
| B06 | ER/calcium and mitochondrial compartments / B1, B6-B7 | Partial: finite [ER/cytosol](ER_CALCIUM.md), calcium buffers, plasma transport and IP3 composition | [Mitochondrial energetics and calcium coupling](PAPER_REVIEW_MITOCHONDRIA.md) remain proposed; ER support does not imply mitochondria support |
| B07 | Chemistry, regulation and bioelectric feedback / B1, B3 | Partial: EMT, [compartment reactions](COMPARTMENT_REACTIONS.md), calcium/IP3 and one-way [assembly regulation](CAPSID_ASSEMBLY.md) | Broader regulatory networks, calibrated feedback and bidirectional assembly/energy coupling |
| B08 | Extracellular electrodiffusion and barriers / B1-B2 | Partial: finite and spatial exterior, cross-region return currents and selected native spatial fields | Broader boundary/barrier physics, spatial convergence and transepithelial comparisons |
| B09 | Resolved membrane polarization and fields / B1-B2 | Partial: [resolved membrane surfaces and tissue fields](TISSUE_RETURN_CURRENT.md), with scoped CPU/L4 qualification | General meshes, larger sparse/device solves, additional boundary conditions and native coupled coverage |
| B10 | Channel/pump redistribution and polarity / B5, B7 | Planned: patch-specific parameters and scheduled availability do not move channels along a membrane | Explicit surface transport/redistribution laws, conservation and field-reversal checks |
| B11 | Osmotic pressure, water and flow / B2, B4 | Planned | Water/solute/volume and pressure coupling; equilibrium, dilution and closed-volume checks |
| B12 | Deformation and electromechanics / B2, B7 | Planned: electrical tissue geometry is not a deformation law | Named mechanics, geometry/capacitance/contact updates, force balance and convergence |
| B13 | Tissue geometry, regional profiles and interventions / B2 | Partial: spatial tissues, region/surface ownership and scheduled transport controls | Tissue cutting, changing topology, general profiles and native SIM-event correspondence beyond the declared panels |
| B14 | Heterogeneity and stochastic perturbations / B2 | Partial: heterogeneous parameters and stochastic assembly with stable world IDs/random streams | Additional stochastic physiological laws and distributional validation; assembly randomness does not cover all BETSE perturbations |
| B15 | Preparation and detailed/reduced modes / B1-B2 | Partial: explicit preparations, versioned fidelity choices and bounded recording | Validated fine/coarse reduction, adaptive resolution and coupled multirate execution |
| B16 | Parameters, calibration and model comparison / B3 | Partial: preserved descriptive endpoint pilot and [candidate data plan](BETSE_BIOLOGICAL_BENCHMARK_PLAN.md) | Suitable measurements, parameter provenance, uncertainty and independent biological evaluation |
| B17 | Headless workflows, observations and visualization / B1-B2 | Partial: CLI/configurations, manifests, arrays, checkpoints, windows, ensembles and GPU telemetry | A general scientific viewer, further interoperable exports and qualified remote execution |

A feature combination requires its own comparison: qualifying ER, a field solver
and a pump independently does not establish their integrated trajectory. Native
law checks, native clock-matched trajectories and independently integrated
physical models retain their separate meanings. Existing numerical tolerances
and failed evidence remain part of the record.

## Staged build order

The [Roadmap](ROADMAP.md#current-development-priorities) owns the build priorities.
New mechanisms proceed through declared equations/ownership, independent
references, implementation and integrated CPU/L4 checks. Jupiter qualification
and a distributed interacting tissue require additional execution evidence.
Completed prerequisites are recorded in Progress rather than repeated as tasks
in every design document.

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

See [Progress](../PROGRESS.md#current-position) for the active comparison and its
next integration step. The [calibration approach](BETSE_REALISM_AND_NEXT_STEPS.md)
sets the acceptance distinctions; it is not a second current-status tracker.

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
