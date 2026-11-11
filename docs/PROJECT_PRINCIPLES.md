# Project principles and document upkeep

Moved from the project README on 11 November 2026, unchanged except for link paths.
The binding rules for agents and contributors are in [AGENTS.md](../AGENTS.md).

## Working principles

- Never build something into the simulator or its models for a single experiment.
  An experiment may reveal a missing mechanism (D136), but what is added is a
  general, reusable, cited model or operator. The simulator is then qualified step
  by step for a widening range of work, so each qualified piece serves many
  experiments (user, 11 November 2026; D144).
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

The current sources are listed in [Scientific basis](SCIENTIFIC_BASIS.md).
The strict-eight, ingressing-minds/Ruliad, and AI branches of `../../preprints`
have now received a targeted design review (R002). The remaining collection is
still a later ideas source. Research results are model-specific evidence, not
universal laws to encode in the engine.

R remains an optional analysis interface. Python/JAX is the selected simulation
stack; Julia, Taichi, C++, PhysiCell, and CompuCell3D are retained as alternatives
in the decision record rather than additional implementation commitments.

## Keeping the documents current

Update [Progress](../PROGRESS.md) when work starts, completes, or encounters a
dependency. Record a substantive design change in [Decisions](DECISIONS.md).
Add a research check-in to [Scientific basis](SCIENTIFIC_BASIS.md), then
update the affected experiment or roadmap entry. Link completed tasks to their
code, tests, benchmark reports, or run artifacts.


## First build and first tissue destination (historical)

The [original one-cell build](FIRST_BUILD.md) established explicit state,
read-only observations and verified save/restore. Subsequent model families add
regulation, communicating cells, spatial fields and intracellular chemistry.
Their implemented and verified scopes are recorded in [Progress](../PROGRESS.md)
and the model guides. The [engineering gate](ENGINEERING_GATE.md) preserves
the original separation of engineering, numerical and scientific acceptance.

The proposed memory demonstration is a small 2D tissue in which a temporary local cue
changes cellular state, communication determines whether that change spreads, and subsequent carrier
replacement tests its persistence. Begin with a fixed contact graph and controlled
relay assays. Add growth, division, and turnover as an explicit later extension.

The model will represent intracellular dynamics, selective communication,
spatial context, and lineage events. Full numerical state will support multiple
readouts, including phenotype, retention, rewriting, transmission, and recovery.

