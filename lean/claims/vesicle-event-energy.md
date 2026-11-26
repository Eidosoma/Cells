<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# The osmotic energy of a vesicle event is independent of its path

The incremental change equals the difference between the final and initial equilibrium energies for both membrane regimes and both crossing directions. A forward event followed by its exact reverse has zero net osmotic energy.

## Assumptions

- The lumen count, membrane footprint, bath density, molecular standard and footprint-to-volume coefficient are positive. Bath and standard remain fixed during the event. Fractional footprint powers and logarithms use exact reals.
- The volume is the smaller of the osmotic volume and the membrane's spherical cap. At equality the numerical law selects the slack branch. The empty or membraneless fallback has separate numerical cases.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.VesicleEvent.cap_eq_sqrt](../CellsProofs/Chemistry/VesicleEvent.lean#L29)
- [CellsProofs.Chemistry.VesicleEvent.slack_change_eq](../CellsProofs/Chemistry/VesicleEvent.lean#L76)
- [CellsProofs.Chemistry.VesicleEvent.taut_change_eq](../CellsProofs/Chemistry/VesicleEvent.lean#L88)
- [CellsProofs.Chemistry.VesicleEvent.gap_eq](../CellsProofs/Chemistry/VesicleEvent.lean#L96)
- [CellsProofs.Chemistry.VesicleEvent.gap_nonneg](../CellsProofs/Chemistry/VesicleEvent.lean#L104)
- [CellsProofs.Chemistry.VesicleEvent.gap_at_boundary](../CellsProofs/Chemistry/VesicleEvent.lean#L110)
- [CellsProofs.Chemistry.VesicleEvent.log_select](../CellsProofs/Chemistry/VesicleEvent.lean#L115)
- [CellsProofs.Chemistry.VesicleEvent.change_eq](../CellsProofs/Chemistry/VesicleEvent.lean#L126)
- [CellsProofs.Chemistry.VesicleEvent.round_trip](../CellsProofs/Chemistry/VesicleEvent.lean#L132)

Direct proof subject `cells.free_energy.osmotic_lumen@1`

Proof sources [Mathlib log_rpow, specialized to the three-halves footprint exponent](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/SpecialFunctions/Pow/Real.lean#L469) · [Mathlib log_le_sub_one_of_pos bounds the branch correction](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/SpecialFunctions/Log/Basic.lean#L288) · [Incremental energy in the Cells candidate](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/lumen.py#L193-L242)

Uses [Membrane area caps the volume that minimizes a vesicle’s osmotic free energy](osmotic-vesicle-volume.md)

## Numerical comparison

**Checked.** On 169 directed pairs including 26 regime crossings, the maximum compiled CPU error was 1.07 × 10⁻¹⁴ kT compared with 1.70 × 10⁻¹⁰ on the earlier engine. Maximum disagreement around the eighteen four-event cycles was 5.33 × 10⁻¹⁵ kT.

**Engine** `cells.assembly_lineages@2`, `cells.osmotic_lumen@1`, `cells.bilayer_geometry@1`

[Native step, regular energy change and boundary fallback](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/lumen.py#L193-L242) · [Spherical area and radius](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/geometry.py) · [Public compiled lineage](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/runner.py) · [Registered event and term execution](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/kernel.py) · [Moving bilayer fixture](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/tests/unit/test_assembly_lineages_v2_lumen.py) · [World and execution definition](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/tests/assembly_lineage_v2_fixtures.py) · [Vesicle event proof](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/CellsProofs/Chemistry/VesicleEvent.lean) · [Equilibrium energy and volume](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/CellsProofs/Chemistry/Vesicle.lean) · [Public trajectory, physical constants and independent volume calculation](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/vesicle.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/vesicle_events.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/PROGRESS.md#ol5-event-energy)

[Tested engine 329e9e395ac1](https://github.com/Eidosoma/Cells/commit/329e9e395ac117998657a21eb827192d34314107) · [Evidence checkpoint ad1f96418722](https://github.com/Eidosoma/Cells/commit/ad1f96418722d25876b38b5a5f38996512d6a32c)

## Biological evidence

**Open.** Reversible osmotic work across a specified change in internal solute and membrane area, with a measured bath and starting and ending states.

**Unit** kT per event

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
