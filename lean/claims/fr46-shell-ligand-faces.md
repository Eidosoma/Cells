<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A sealed shell excludes a ligand when its bound forms stay on one face

If every event conserves a ligand moiety and every possible transfer preserves its face, an initially ligand-free interior stays free through any finite event history. A ligand in the final free lumen has an initially occupied origin connected by transfers. Binding another ligand can carry the first one across a wall reaction.

## Assumptions

- Places include free pools and all wall forms. A nonnegative integer weight gives each place’s number of copies of the selected moiety per molecule. Every directed event consumes available molecules and balances their weighted counts. Include both directions of reversible reactions.
- Each consumed place with positive moiety weight connects to every produced place carrying that moiety in the same event. Each such connection must preserve its face. This sufficient condition can conservatively connect distinct copies when a reaction carries several.
- Every inner-accessible place, including bound complexes, starts with zero copies of the selected moiety. The free lumen place has positive weight. Other ligands may already be present inside.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.ShellLigandFaces.face_along_path](../CellsProofs/Chemistry/ShellLigandFaces.lean#L24)
- [CellsProofs.Chemistry.ShellLigandFaces.possible_origin](../CellsProofs/Chemistry/ShellLigandFaces.lean#L61)
- [CellsProofs.Chemistry.ShellLigandFaces.sealed_lumen](../CellsProofs/Chemistry/ShellLigandFaces.lean#L74)

Direct proof subject `cells.prescribed_shell@1`, `cells.stochastic_mass_action@1`

Proof sources [D323 sealed-lumen and face-propagation contract](https://github.com/Eidosoma/Cells/blob/9eb9890a91ad6049be9b2e5a1bfae7b383a464eb/docs/DECISIONS.md#L10202-L10212) · [Mathlib finite-path closure, imported and specialized to equality of ligand faces](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Logic/Relation.lean#L544-L546) · [Cells exact two-ligand carrier, same-face control and preloaded-site check](../checks/chemistry/ShellLigandFaces.lean)

## Numerical comparison

**Failed.** Development engine 61d823be admitted the carrier. The host kernel gave a positive rate for each of its four consecutive events. From one X outside, following these events left one X inside and zero outside while preserving X, Y and the wall scaffold. The otherwise identical sealed control with Y binding removed was admitted as expected.

**Engine** `cells.assembly_lineages@2`, `cells.prescribed_shell@1`, `cells.stochastic_mass_action@1`

[Declared-face binding and composition check](https://github.com/Eidosoma/Cells/blob/61d823be7e3913f44a4dd497507a8e8256151584/src/cells/models/assembly_lineages_v2/spec.py#L421) · [Site pairs, including a wall species that also acts as a site](https://github.com/Eidosoma/Cells/blob/61d823be7e3913f44a4dd497507a8e8256151584/src/cells/models/assembly_lineages_v2/world.py#L521) · [Host rate kernel at each state](https://github.com/Eidosoma/Cells/blob/61d823be7e3913f44a4dd497507a8e8256151584/src/cells/models/assembly_lineages_v2/balance.py#L56) · [Prescribed shell fixture](https://github.com/Eidosoma/Cells/blob/61d823be7e3913f44a4dd497507a8e8256151584/tests/unit/test_assembly_lineages_v2_geometry.py) · [World definition and stoichiometric steps](https://github.com/Eidosoma/Cells/blob/61d823be7e3913f44a4dd497507a8e8256151584/tests/assembly_lineage_v2_fixtures.py) · [Exact material accounting, four enabled events and sealed control](https://github.com/Eidosoma/Cells/blob/69176ea710e804bccf611a6f95c155631c4d16a9/lean/checks/chemistry/ShellLigandFaces.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/69176ea710e804bccf611a6f95c155631c4d16a9/lean/checks/shell_ligand_faces.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/69176ea710e804bccf611a6f95c155631c4d16a9/lean/PROGRESS.md#fr46-shell-ligand-faces)

[Tested engine 61d823be7e39](https://github.com/Eidosoma/Cells/commit/61d823be7e3913f44a4dd497507a8e8256151584) · [Evidence checkpoint 69176ea710e8](https://github.com/Eidosoma/Cells/commit/69176ea710e804bccf611a6f95c155631c4d16a9)

## Biological evidence

**Open.** Lumen tracer count over time in a closed shell with face-selective binding, with the initially free and wall-bound tracer inventories measured.

**Unit** molecules

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
