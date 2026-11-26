<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Resolving neutral labels can increase the heat booked for diffusion

At a neutral Fick face, the sum of label powers exceeds or equals the parent power. Equality holds exactly when the label fractions agree at both ends. An accepted-step face booking with positive weights is zero exactly when every applied flux is zero.

## Assumptions

- The two end concentrations, all normalized label fractions and the common mobility and temperature factor are strictly positive. The exact Cells face reduction uses its logarithmic quotient or equal-concentration branch on every row and the parent.
- The timestep booking uses the applied mean flux and its predicted weight. The two-row square identity combines the two weights by addition. A separately simulated parent uses the weight predicted for its own concentration.
- The trajectory comparison runs a closed, two-node neutral system with the same physical concentrations in both representations.

## Lean proof

**Proved**

- [CellsProofs.Transport.LabelMixingPower.neutral_face_power](../CellsProofs/Transport/LabelMixingPower.lean#L17)
- [CellsProofs.Transport.LabelMixingPower.power_difference](../CellsProofs/Transport/LabelMixingPower.lean#L68)
- [CellsProofs.Transport.LabelMixingPower.power_order_and_equality](../CellsProofs/Transport/LabelMixingPower.lean#L88)
- [CellsProofs.Transport.LabelMixingPower.booking_zero_iff](../CellsProofs/Transport/LabelMixingPower.lean#L104)
- [CellsProofs.Transport.LabelMixingPower.booking_difference_two](../CellsProofs/Transport/LabelMixingPower.lean#L115)

Direct proof subject `cells.route.logmean_electrodiffusion@1`

Proof sources [Mathlib strict logarithmic inequality for the equality condition](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/SpecialFunctions/Log/Basic.lean#L242-L246) · [Mathlib non-strict logarithmic bound for each term](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/SpecialFunctions/Log/Basic.lean#L288-L292) · [Mathlib relative-entropy function, identified in the optional check](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/InformationTheory/KullbackLeibler/KLFun.lean#L45-L51)

Uses [Neutral label fluxes add and labels can exchange across a face with zero parent flux](neutral-label-diffusion.md) · [Passive extracellular face transport dissipates energy](extracellular-face-dissipation.md)

## Numerical comparison

**Checked.** Across 800 accepted steps the largest reconstruction error was 3.68 × 10⁻¹⁶ pJ. Opposing labels booked 1.47315444 pJ in 1 s and the parent booked zero. With the same label fractions both booked 0.33000851 pJ.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `logmean_electrodiffusion@1`

[Neutral face and instantaneous power](https://github.com/Eidosoma/Cells/blob/ee0b8106406eb26e57ab1b0c34e16ed6c3f83a2b/src/cells/numerics/surface_transport.py#L283-L302) · [Logarithmic mean and series threshold](https://github.com/Eidosoma/Cells/blob/ee0b8106406eb26e57ab1b0c34e16ed6c3f83a2b/src/cells/numerics/extracellular_field.py#L48-L69) · [Predicted face conductances](https://github.com/Eidosoma/Cells/blob/ee0b8106406eb26e57ab1b0c34e16ed6c3f83a2b/src/cells/numerics/surface_imex.py#L109-L135) · [Applied flux and cumulative heat](https://github.com/Eidosoma/Cells/blob/ee0b8106406eb26e57ab1b0c34e16ed6c3f83a2b/src/cells/models/surface_pump_v3.py#L2111-L2134) · [Diffusion rate, two nodes and explicit labels](https://github.com/Eidosoma/Cells/blob/ee0b8106406eb26e57ab1b0c34e16ed6c3f83a2b/validation/regions/example.py#L45-L105) · [Accepted-step histories](https://github.com/Eidosoma/Cells/blob/ee0b8106406eb26e57ab1b0c34e16ed6c3f83a2b/validation/regions/readouts.py#L269-L290) · [Pointwise surface comparison inputs](https://github.com/Eidosoma/Cells/blob/ee0b8106406eb26e57ab1b0c34e16ed6c3f83a2b/validation/tissue/surface_fixtures.py) · [Baseline concentration for inactive species](https://github.com/Eidosoma/Cells/blob/ee0b8106406eb26e57ab1b0c34e16ed6c3f83a2b/validation/tissue/secreted_species_fixtures.py#L29-L33) · [Mixing power and accepted-step proofs](https://github.com/Eidosoma/Cells/blob/a710e377ea87a865af46a1e6b2d7cf3574ff5aa3/lean/CellsProofs/Transport/LabelMixingPower.lean) · [Neutral face reduction](https://github.com/Eidosoma/Cells/blob/a710e377ea87a865af46a1e6b2d7cf3574ff5aa3/lean/CellsProofs/Transport/LabelDiffusion.lean) · [Optional Mathlib relative-entropy equivalence](https://github.com/Eidosoma/Cells/blob/a710e377ea87a865af46a1e6b2d7cf3574ff5aa3/lean/checks/mixing/KLFun.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/a710e377ea87a865af46a1e6b2d7cf3574ff5aa3/lean/checks/label_mixing_power.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/a710e377ea87a865af46a1e6b2d7cf3574ff5aa3/lean/PROGRESS.md#fr33-label-energy)

[Tested engine ee0b8106406e](https://github.com/Eidosoma/Cells/commit/ee0b8106406eb26e57ab1b0c34e16ed6c3f83a2b) · [Evidence checkpoint a710e377ea87](https://github.com/Eidosoma/Cells/commit/a710e377ea87a865af46a1e6b2d7cf3574ff5aa3)

## Biological evidence

**Open.** Heat of mixing for independently characterized neutral tracers with equal mobility. Interpreting the extra booking for labels used solely to track provenance remains open.

**Unit** pJ of heat over a specified interval

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
