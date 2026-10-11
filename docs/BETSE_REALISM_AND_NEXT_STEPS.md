# BETSE as a bioelectric calibration reference

Framing updated 2026-10-11. Cells uses BETSE as a reference to calibrate and
verify the bioelectric layer of its larger simulations. That layer forms part
of a broader framework for cell chemistry, protein assembly, tissue organisation
and future organ models, with modular multiscale CPU/GPU execution.
Simplified models remain useful selectable resolutions.

## What counts as reaching the target

Use the pinned BETSE 1.5.0 source as a reproducible comparator for the bioelectric
layer, alongside experimental evidence. Review subsequent source and biological
evidence explicitly. Track reference coverage and related Cells extensions in
the [B01–B17 inventory](BETSE_CAPABILITY_ROADMAP.md#capability-inventory-and-engineering-route).
Deferring a feature does not remove it from that inventory.

For each mechanism distinguish specification, independent numerical reference,
production implementation, source correspondence, experimental evaluation,
GPU qualification, and cross-resolution qualification. A passing isolated
equation or short trajectory does not complete the other columns. More equations
alone do not establish greater biological accuracy.

The detailed path must support, in stages:

- Ion inventories, membrane charge and passive transport with realistic units,
  selective channels, substrate-dependent pumps/exchangers and energy accounting.
- Selective and voltage-dependent junctional communication, heterogeneous cells,
  regional interventions and tissue geometry.
- Finite and spatial extracellular spaces, tissue barriers, membrane surface
  resolution and electric-field coupling.
- Biochemical feedback, intracellular compartments and calcium handling; then
  water/volume/flow, mechanics and spatial redistribution where required.
- Reproducible preparation, parameter provenance, experimental observables and
  uncertainty, not merely agreement with another simulator.

Do not reproduce an upstream implementation quirk as a universal biological law.
Separate a source-compatibility adapter from a named physical mechanism, document
the difference, and test its consequences. No silent change to accepted models.

## Work now and the next gates

Use the [capability inventory](BETSE_CAPABILITY_ROADMAP.md#capability-inventory-and-engineering-route)
for implemented subsets and remaining gaps, [Roadmap](ROADMAP.md) for priorities,
and [Progress](../PROGRESS.md) for active work and completed evidence. These
have separate roles so a historic launch is not mistaken for the current result.

The [earlier plan](history/BETSE_REALISM_AND_NEXT_STEPS_BEFORE_2026-10-11.md)
preserves the September pump, recording and junction sequence. Since that
baseline, model guides cover [spatial and resolved tissue](TISSUE_RETURN_CURRENT.md),
[calcium/IP3](PLASMA_CALCIUM.md), [assembly coupling](CAPSID_ASSEMBLY.md) and
[CPU/L4 execution](GPU_ENSEMBLES.md). Their scoped implementation and comparison
results do not close full biological, BETSE-family or Jupiter qualification.

## Architecture guardrails

Biological mechanism, spatial resolution, numerical method and execution device
are independent choices. Organ identity remains data, including future multiple
organs and explicit inter-organ ports. Fine cells can retain membrane/compartment
state; any reduced region needs a declared validity regime and checked exchange
of amounts, charge, energy and volume with neighbouring regions.

Use batched, side-effect-free local laws; explicit species/compartment/membrane/
edge axes; one owner per stored inventory and one signed transfer per interface.
Evaluate coupled fluxes at a common solver stage. Inputs and observations do not
silently mutate hidden kinetics. Checkpoints contain all dynamical state.

JAX-friendly array algebra is a useful first constraint, not proof of GPU speed
or scalability. The present dense spatial solve is a bounded reference/backend;
large tissues will need sparse or matrix-free device-compatible solves, an
explicit precision policy and measured communication costs. Multirate stepping
and coarse/fine adaptation need their own conservation and convergence evidence.

No organ, geometry, timestep, biological parameter or experimental uncertainty
is chosen merely to make a source comparison pass. Detailed modes cannot be
silently replaced by reduced modes for speed. Long captures and regressions stay
detached, bounded and user-polled; there is no automatic follow-up campaign.
