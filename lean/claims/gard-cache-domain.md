<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# GARD v2 also needs a representable exponent and a reachable molecule capacity

The significand-width guard alone admits a row whose rounded high word overflows binary64. At the other extreme the grid model requires the smallest positive tick to survive. The public parser also imposes a smaller effective fission-size limit than its explicit capacity range.

## Assumptions

- The overflow witness uses coefficient 2¹⁰²³, two molecules of that type, one of a second type and capacity eight. The underlying exchange uses finite rates. The lower-end witness uses one coefficient at 2⁻¹⁰⁷⁴.
- The capacity comparison explicitly supplies the molecule capacity, using two types throughout. It checks parser behavior independently of either exponent example.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.GardCache.one_tick](../CellsProofs/Chemistry/GardCache.lean#L178)
- [CellsProofs.Chemistry.GardCache.exponent_counterexample](../CellsProofs/Chemistry/GardCache.lean#L184)

Direct proof subject `cells.gard_catalysis_pair_consistent@2`

Proof sources [Cells high-word and unit-tick definitions](../CellsProofs/Chemistry/GardCache.lean) · [IEEE binary64 input guard and the row-width calculation](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/models/assembly_lineages/gard.py#L359-L396)

Uses [GARD v2 preserves the smaller catalyst on a reverse event within the precision bound](gard-cache-reversibility.md)

## Numerical comparison

**Failed.** With an exact total propensity rounding to 25,165,824, the admitted four-bit row returned NaN cache words, zero events, a stalled status and a passing empty ledger. At 2⁻¹⁰⁷⁴ NumPy preserved one tick and compiled CPU returned zero. Explicit capacity 4,097 was refused by the default 4,096 type bucket.

**Engine** `cells.assembly_lineages@1`, `cells.reservoir_exchange@1`, `cells.gard_catalysis_pair_consistent@2`

[Finite-input check and exact fold](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/models/assembly_lineages/gard.py) · [Molecule capacity and default bucket](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/models/assembly_lineages/spec.py#L358-L371) · [Type bucket sizes](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/models/assembly_lineages/family.py#L28-L54) · [Independent declared fission-size limit](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/models/assembly_lineages/fission.py#L94-L102) · [Stalled event branch](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/models/assembly_lineages/kernel.py#L338-L352) · [Lineage result and energy ledger](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/models/assembly_lineages/runner.py) · [Independent rational join and leave propensities](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/validation/gard/references/kernels.py#L233-L304) · [Two-type world and explicit execution capacity](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/tests/assembly_lineage_fixtures.py) · [Precision proof and numerical-domain witnesses](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/CellsProofs/Chemistry/GardCache.lean) · [Stress-world construction and comparison](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/checks/gard_catalysis.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/checks/gard_cache.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/PROGRESS.md#gard-v2-range)

[Tested engine 6b28ec553680](https://github.com/Eidosoma/Cells/commit/6b28ec55368011de79dce85e6172b5844b77a287) · [Evidence checkpoint d6db91d64f5c](https://github.com/Eidosoma/Cells/commit/d6db91d64f5c90d8e4857873052f4e667eba7469)

## Biological evidence

**Open.** The examples test numerical domain handling and parser reachability. No organism-specific catalyst range is assigned.

**Unit** Binary exponent, row bits and molecule count

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
