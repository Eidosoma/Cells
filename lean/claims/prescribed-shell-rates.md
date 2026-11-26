<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Shell entry and exit depend on conductance and the gate’s own forms

At fixed activities and standard density, the area–permeability product fixes both rate prefactors. Changing other wall counts leaves the gate factor unchanged. The common gate preserves the ratio of the two directional activities when the reverse rate is positive.

## Assumptions

- The declared area and lumen volume are fixed. Forward and reverse comparisons use their respective activities and the same gate counts on the pair’s common state.
- The gate factor is a count-weighted mean over its declared forms. An absent gate has factor one.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.PrescribedShell.same_conductance](../CellsProofs/Chemistry/PrescribedShell.lean#L34)
- [CellsProofs.Chemistry.PrescribedShell.gate_unchanged](../CellsProofs/Chemistry/PrescribedShell.lean#L19)
- [CellsProofs.Chemistry.PrescribedShell.absent_gate](../CellsProofs/Chemistry/PrescribedShell.lean#L26)
- [CellsProofs.Chemistry.PrescribedShell.paired_rates](../CellsProofs/Chemistry/PrescribedShell.lean#L40)

Direct proof subject `cells.assembly_geometry.prescribed_shell@1`, `cells.reaction.shell_permeation@1`, `cells.rate_factor.gate_factor@1`

## Numerical comparison

**Checked.** Two existing engine tests passed. Doubling area while halving permeability preserved both rates to rounding. Doubling permeability alone doubled both rates. Changes to nongate inventory left rates and lumen volume identical. Both run modes recorded the shell probe.

**Engine** `cells.assembly_lineages@2`, `cells.prescribed_shell@1`, `cells.shell_permeation@1`, `cells.gate_factor@1`

[Declared shell extent](https://github.com/Eidosoma/Cells/blob/a6235d7b02c04e147991342c2891eb0c1cd3deb6/src/cells/models/assembly_lineages_v2/prescribed_shell.py#L82) · [Permeation rate law](https://github.com/Eidosoma/Cells/blob/a6235d7b02c04e147991342c2891eb0c1cd3deb6/src/cells/models/assembly_lineages_v2/shell_permeation.py) · [Factor over gate forms only](https://github.com/Eidosoma/Cells/blob/a6235d7b02c04e147991342c2891eb0c1cd3deb6/src/cells/models/assembly_lineages_v2/gate_factor.py#L121) · [Closed-form rates and population records](https://github.com/Eidosoma/Cells/blob/a6235d7b02c04e147991342c2891eb0c1cd3deb6/tests/unit/test_assembly_lineages_v2_geometry.py#L538) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/tests/unit/test_assembly_lineages_v2_geometry.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/lean/PROGRESS.md#nov21-features)

[Tested engine a6235d7b02c0](https://github.com/Eidosoma/Cells/commit/a6235d7b02c04e147991342c2891eb0c1cd3deb6) · [Evidence checkpoint ceeca19816ac](https://github.com/Eidosoma/Cells/commit/ceeca19816acd761ab68379d67bb0f7426366a1c)

## Biological evidence

**Open.** Bidirectional flux at measured shell area and permeability, with the gate-form ratio held fixed while nongate site counts vary.

**Unit** molecules/s

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
