<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A fresh bath one molecule beyond capacity loses a logarithmic term if accepted

For a dilute species with count M + 1, using the last log-factorial entry M in its discrete ideal energy understates that energy by ln(M + 1) kBT. The molecular capacity must cover every finite count committed by an accepted replacement or serial transfer.

## Assumptions

- M is a positive integer capacity. The discrete ideal energy consists of a linear term in the full molecular count and a log-factorial term. At the first count outside the table the lookup returns the entry at M.
- The test replaces the bath at the horizon. The fresh bath is below the osmotic ceiling, and the transfer keeps both living slots.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.VesiclePopulation.replacement_capacity_gap](../CellsProofs/Chemistry/VesiclePopulation.lean#L153)

Direct proof subject `cells.pool_replacement@1`, `cells.serial_transfer@1`

Uses [A finite-pool wash preserves assembly cargo and books the two bath energies](pool-replacement.md) · [Whole-molecule counts set the ideal mixing cost of membrane entry](assembly-ideal-mixing.md)

## Numerical comparison

**Checked.** Both schedules now reject 33 molecules at capacity 32 during definition. Both accepted 32 at 32 and 33 at 64 with the reference work. The earlier comparison records the incorrect work of an accepted oversized pool.

**Engine** `cells.assembly_lineages@2`, `cells.shared_pool@1`, `cells.ideal_mixing@1`

**Operators** `cells.pool_replacement@1`, `cells.serial_transfer@1`

[Checks on every fresh count and founder](https://github.com/Eidosoma/Cells/blob/d74f519d40b9a9f7488b94b489c6dc4dd865504c/src/cells/models/assembly_lineages_v2/spec.py#L692) · [Discrete ideal-bath energy](https://github.com/Eidosoma/Cells/blob/d74f519d40b9a9f7488b94b489c6dc4dd865504c/src/cells/models/assembly_lineages_v2/ideal_mixing.py) · [Replacement and transfer schedule definitions](https://github.com/Eidosoma/Cells/blob/d74f519d40b9a9f7488b94b489c6dc4dd865504c/tests/unit/test_assembly_lineages_v2_replacement.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/lean/checks/pool_replacement.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/lean/PROGRESS.md#nov21-engine-review)

[Tested engine d74f519d40b9](https://github.com/Eidosoma/Cells/commit/d74f519d40b9a9f7488b94b489c6dc4dd865504c) · [Evidence checkpoint ceeca19816ac](https://github.com/Eidosoma/Cells/commit/ceeca19816acd761ab68379d67bb0f7426366a1c)

**Engine** `cells.assembly_lineages@2`, `cells.shared_pool@1`, `cells.ideal_mixing@1`

**Operators** `cells.pool_replacement@1`, `cells.serial_transfer@1`

[Declared per-count capacity](https://github.com/Eidosoma/Cells/blob/529070a8c844ae8d58da615494df31f21ce49774/src/cells/models/assembly_lineages_v2/spec.py#L35) · [Fresh replacement composition](https://github.com/Eidosoma/Cells/blob/529070a8c844ae8d58da615494df31f21ce49774/src/cells/models/assembly_lineages_v2/replacement.py#L67) · [Serial transfer and shared fresh-pool step](https://github.com/Eidosoma/Cells/blob/529070a8c844ae8d58da615494df31f21ce49774/src/cells/models/assembly_lineages_v2/transfer.py#L81) · [Transfer and replacement work](https://github.com/Eidosoma/Cells/blob/529070a8c844ae8d58da615494df31f21ce49774/src/cells/models/assembly_lineages_v2/population.py#L700) · [Discrete ideal free energy](https://github.com/Eidosoma/Cells/blob/529070a8c844ae8d58da615494df31f21ce49774/src/cells/models/assembly_lineages_v2/ideal_mixing.py#L64) · [Clipped log-factorial access](https://github.com/Eidosoma/Cells/blob/529070a8c844ae8d58da615494df31f21ce49774/src/cells/models/assembly_lineages_v2/mass_action.py#L66) · [Three-phase world and pool ordering](https://github.com/Eidosoma/Cells/blob/529070a8c844ae8d58da615494df31f21ce49774/tests/unit/test_assembly_lineages_v2_replacement.py#L56) · [Independent discrete ideal-bath energy](https://github.com/Eidosoma/Cells/blob/529070a8c844ae8d58da615494df31f21ce49774/lean/checks/vesicle_population.py#L37) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/529070a8c844ae8d58da615494df31f21ce49774/lean/checks/pool_replacement.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/529070a8c844ae8d58da615494df31f21ce49774/lean/PROGRESS.md#pool-replacement-capacity)

[Tested engine 529070a8c844](https://github.com/Eidosoma/Cells/commit/529070a8c844ae8d58da615494df31f21ce49774) · [Evidence checkpoint 529070a8c844](https://github.com/Eidosoma/Cells/commit/529070a8c844ae8d58da615494df31f21ce49774)

## Biological evidence

**Open.** The table limit is an implementation property. Its reference is the discrete ideal free energy of the finite bath.

**Unit** molecules and kBT

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
