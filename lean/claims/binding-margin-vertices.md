<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Finite vertex tests for binding equilibria

For one held ligand the feasibility margin has one direction. For two, its minimum over all real normalized weights occurs at a simplex endpoint or a rational crossing of two forms of the same binder. In any number of dimensions, if each binder has a form attaining its lowest count in every held row simultaneously, the smallest coordinate remainder gives the exact minimum.

## Assumptions

- Each binder has finitely many chemically present forms with signed integer counts relative to its base. Weights are nonnegative and sum to one on the held ligands.
- The equilibrium equivalences use nonnegative binder totals, strictly positive free concentrations and finite fixed standard log weights. In the two-ligand proof duplicate or parallel profiles and coincident crossings are allowed.
- The arbitrary-dimensional corner criterion requires a simultaneous componentwise minimum for each binder. The registered three-ligand S6 counts satisfy this hypothesis. The host caps on enumeration and the precision of the float64 margin are implementation properties.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.BindingVertices.two_ligand_vertex_le](../CellsProofs/Chemistry/BindingVertices.lean#L146)
- [CellsProofs.Chemistry.BindingVertices.two_ligand_minimum_at_vertex](../CellsProofs/Chemistry/BindingVertices.lean#L181)
- [CellsProofs.Chemistry.BindingVertices.one_ligand_equilibrium_iff](../CellsProofs/Chemistry/BindingVertices.lean#L195)
- [CellsProofs.Chemistry.BindingVertices.two_ligand_equilibrium_iff](../CellsProofs/Chemistry/BindingVertices.lean#L203)
- [CellsProofs.Chemistry.BindingVertices.margin_of_common_lowest_form](../CellsProofs/Chemistry/BindingVertices.lean#L219)
- [CellsProofs.Chemistry.BindingVertices.common_floor_minimum_at_corner](../CellsProofs/Chemistry/BindingVertices.lean#L232)
- [CellsProofs.Chemistry.BindingVertices.common_floor_equilibrium_iff](../CellsProofs/Chemistry/BindingVertices.lean#L249)

Direct proof subject `cells.binding.rapid_binding@1`

Proof sources [Mathlib interval parametrization of the two-weight simplex, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Convex/Basic.lean#L665-L675) · [Mathlib singleton simplex, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Convex/Basic.lean#L623-L627) · [Mathlib minimum on a nonempty finite set, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Data/Finset/Max.lean#L513-L516) · [Cells existence and uniqueness criterion](../CellsProofs/Chemistry/BindingFeasibility.lean#L264)

Uses [Which ligand totals admit a positive binding equilibrium?](binding-equilibrium-feasibility.md)

## Numerical comparison

**Checked.** The exact minima matched the frozen references on all 80 registered states. NumPy and compiled JAX CPU agreed with the rounded exact margins on all 236 nonempty held projections. Lean checked 31 fixture statements from the engine lists and form counts. Both backends found the negative −1/24 mM minimum in two controls where omitting one vertex would give a positive result. The earlier signed-total rounding failures remain recorded under equilibrium feasibility.

**Engine** `resolved_pump_tissue@3`, `rapid_binding@1`

[Exact vertex generation, held-face filtering and numerical margin](https://github.com/Eidosoma/Cells/blob/b521a11cf6384428a564e63e4c44ab4221345600/src/cells/laws/reactions/rapid_binding.py#L261-L340) · [Registered form counts, totals and four C4 challenges](https://github.com/Eidosoma/Cells/blob/b521a11cf6384428a564e63e4c44ab4221345600/validation/core_seams/references/reference_inputs.json) · [Frozen rational minima and minimizing directions](https://github.com/Eidosoma/Cells/blob/b521a11cf6384428a564e63e4c44ab4221345600/validation/core_seams/references/designs/core_seams_reference_values.json) · [Registry fixtures, tested margins and enumeration caps](https://github.com/Eidosoma/Cells/blob/b521a11cf6384428a564e63e4c44ab4221345600/tests/unit/test_rapid_binding_kernel.py#L175-L273) · [Formal vertex and corner criteria](https://github.com/Eidosoma/Cells/blob/739a47bf8e3ee77db8417c6255c690ae9bd89417/lean/CellsProofs/Chemistry/BindingVertices.lean) · [Continuous feasibility criterion](https://github.com/Eidosoma/Cells/blob/739a47bf8e3ee77db8417c6255c690ae9bd89417/lean/CellsProofs/Chemistry/BindingFeasibility.lean) · [Registry count extraction and compiled backend entry points](https://github.com/Eidosoma/Cells/blob/739a47bf8e3ee77db8417c6255c690ae9bd89417/lean/checks/binding_feasibility.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/739a47bf8e3ee77db8417c6255c690ae9bd89417/lean/checks/binding_vertices.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/739a47bf8e3ee77db8417c6255c690ae9bd89417/lean/PROGRESS.md#binding-margin-vertices)

[Tested engine b521a11cf638](https://github.com/Eidosoma/Cells/commit/b521a11cf6384428a564e63e4c44ab4221345600) · [Evidence checkpoint 739a47bf8e3e](https://github.com/Eidosoma/Cells/commit/739a47bf8e3ee77db8417c6255c690ae9bd89417)

## Biological evidence

**Open.** The finite directions follow from the model’s form counts. Experiments measure free and bound ligand at fixed inventories, as described under the linked equilibrium claim.

**Unit** mM for the associated concentration measurements

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
