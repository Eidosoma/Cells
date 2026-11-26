<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# GARD v2 guards the cache exponent range and honors explicit molecule capacity

The 106-bit width condition alone admits overflow. With the repaired upper and lower exponent guards, an exact intermediate of magnitude at most six times the row bound fits below the binary64 maximum, and any nonzero exact integer multiple of the row tick is at least one normal tick in magnitude. The parser resolves the tested explicit molecule capacities on either side of the default bucket limit.

## Assumptions

- The row bound is its largest coefficient times the fission size. Lean assumes the six-times bound on an intermediate and integer-grid membership. It proves their arithmetic consequences. The original one-tick and overflow witnesses explain the extra guards.
- The range replay uses a two-type world at fission size eight for the exponent cases. It exercises the parser, NumPy and the compiled CPU kernel. The explicit capacity cases use matched fission sizes of 4,096 and 4,097.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.GardCache.one_tick](../CellsProofs/Chemistry/GardCache.lean#L178)
- [CellsProofs.Chemistry.GardCache.exponent_counterexample](../CellsProofs/Chemistry/GardCache.lean#L184)
- [CellsProofs.Chemistry.GardRange.upper_margin](../CellsProofs/Chemistry/GardRange.lean#L12)
- [CellsProofs.Chemistry.GardRange.grid_floor](../CellsProofs/Chemistry/GardRange.lean#L21)

Direct proof subject `cells.rate_factor.gard_catalysis_pair_consistent@2`

Proof sources [Cells exact upper and lower parser guards](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/src/cells/models/assembly_lineages/gard.py#L398-L428) · [Mathlib integer absolute-value lower bound, used for the positive grid tick](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/Order/Group/Unbundled/Int.lean#L83) · [Original width-only guard for the historical witnesses](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/models/assembly_lineages/gard.py#L359-L396)

Uses [GARD v2 preserves the smaller catalyst on a reverse event within the precision bound](gard-cache-reversibility.md)

## Numerical comparison

**Checked.** The repaired engine passed all nine cases. At size eight, 2¹⁰¹⁶ ran one event with a closed ledger. The upper boundary and two larger powers were refused. NumPy and compiled CPU preserved 2⁻¹⁰²², and the parser refused both inputs with subnormal low bits. Explicit capacities 4,096 and 4,097 resolved as requested. Six expectations differ on the earlier engine, where the original overflowing row stalled at a finite positive exact-reference rate.

**Engine** `cells.assembly_lineages@1`, `cells.reservoir_exchange@1`, `cells.gard_catalysis_pair_consistent@2`

[Finite-input check and exact fold](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/src/cells/models/assembly_lineages/gard.py) · [Type bucket sizes](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/src/cells/models/assembly_lineages/family.py#L28-L54) · [Independent declared fission-size limit](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/src/cells/models/assembly_lineages/fission.py#L94-L102) · [Stalled event branch](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/src/cells/models/assembly_lineages/kernel.py#L338-L352) · [Lineage result and energy ledger](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/src/cells/models/assembly_lineages/runner.py) · [Independent rational join and leave propensities](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/validation/gard/references/kernels.py#L233-L304) · [Two-type world and explicit execution capacity](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/tests/assembly_lineage_fixtures.py) · [Row precision, upper exponent and least-tick guards](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/src/cells/models/assembly_lineages/gard.py#L398-L428) · [Explicit molecule capacity at parse](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/src/cells/models/assembly_lineages/spec.py#L360-L375) · [Finite check in the public event runner](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/src/cells/models/assembly_lineages/runner.py#L381) · [Parser regression for precision, exponent and capacity](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/tests/unit/test_assembly_lineages_spec.py) · [Precision proof and numerical-domain witnesses](https://github.com/Eidosoma/Cells/blob/76418bab8488f24e041b511701b2376811358db8/lean/CellsProofs/Chemistry/GardCache.lean) · [Stress-world construction and comparison](https://github.com/Eidosoma/Cells/blob/76418bab8488f24e041b511701b2376811358db8/lean/checks/gard_catalysis.py) · [Upper margin and least nonzero grid tick](https://github.com/Eidosoma/Cells/blob/76418bab8488f24e041b511701b2376811358db8/lean/CellsProofs/Chemistry/GardRange.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/76418bab8488f24e041b511701b2376811358db8/lean/checks/gard_cache.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/76418bab8488f24e041b511701b2376811358db8/lean/PROGRESS.md#gard-v2-range-repair)

[Tested engine 184fc81cdfc0](https://github.com/Eidosoma/Cells/commit/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956) · [Evidence checkpoint 76418bab8488](https://github.com/Eidosoma/Cells/commit/76418bab8488f24e041b511701b2376811358db8)

**Engine** `cells.assembly_lineages@1`, `cells.reservoir_exchange@1`, `cells.gard_catalysis_pair_consistent@2`

[Finite-input check and exact fold](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/models/assembly_lineages/gard.py) · [Molecule capacity and default bucket](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/models/assembly_lineages/spec.py#L358-L371) · [Type bucket sizes](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/models/assembly_lineages/family.py#L28-L54) · [Independent declared fission-size limit](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/models/assembly_lineages/fission.py#L94-L102) · [Stalled event branch](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/models/assembly_lineages/kernel.py#L338-L352) · [Lineage result and energy ledger](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/models/assembly_lineages/runner.py) · [Independent rational join and leave propensities](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/validation/gard/references/kernels.py#L233-L304) · [Two-type world and explicit execution capacity](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/tests/assembly_lineage_fixtures.py) · [Precision proof and numerical-domain witnesses](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/CellsProofs/Chemistry/GardCache.lean) · [Stress-world construction and comparison](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/checks/gard_catalysis.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/checks/gard_cache.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/PROGRESS.md#gard-v2-range)

[Tested engine 6b28ec553680](https://github.com/Eidosoma/Cells/commit/6b28ec55368011de79dce85e6172b5844b77a287) · [Evidence checkpoint d6db91d64f5c](https://github.com/Eidosoma/Cells/commit/d6db91d64f5c90d8e4857873052f4e667eba7469)

## Biological evidence

**Open.** The examples test numerical domain handling and parser reachability. No organism-specific catalyst range is assigned.

**Unit** Binary exponent, row bits and molecule count

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
