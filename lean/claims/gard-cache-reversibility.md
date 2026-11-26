<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# GARD v2 preserves the smaller catalyst on a reverse event within the precision bound

On a row’s integer grid, every signed update within the 106-bit bound produces the canonical high and low words for the new sum. Refolding the same counts recovers the same cache, and removing the moving molecule restores the parent’s rounded numerator.

## Assumptions

- The catalyst coefficients are nonnegative multiples of each row’s least tick. The parser bounds the largest coefficient times the fission size to fewer than 2¹⁰⁶ ticks. Count products use at most 2²⁰ molecules and each coefficient part has at most 33 significant bits.
- Rounding selects a nearest 53-bit word. TwoSum returns that rounded sum and its exact error. Hardware also needs finite intermediates and preservation of low words. The companion range comparison records the new guards and the earlier counterexamples.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.GardCache.grid_model_exists](../CellsProofs/Chemistry/GardCache.lean#L37)
- [CellsProofs.Chemistry.GardCache.round_word](../CellsProofs/Chemistry/GardCache.lean#L49)
- [CellsProofs.Chemistry.GardCache.high_error](../CellsProofs/Chemistry/GardCache.lean#L56)
- [CellsProofs.Chemistry.GardCache.row_in_budget](../CellsProofs/Chemistry/GardCache.lean#L100)
- [CellsProofs.Chemistry.GardCache.add_exact](../CellsProofs/Chemistry/GardCache.lean#L129)
- [CellsProofs.Chemistry.GardCache.fold_exact](../CellsProofs/Chemistry/GardCache.lean#L142)
- [CellsProofs.Chemistry.GardCache.reverse_high](../CellsProofs/Chemistry/GardCache.lean#L152)
- [CellsProofs.Chemistry.GardCache.split_product_word](../CellsProofs/Chemistry/GardCache.lean#L163)
- [CellsProofs.Chemistry.GardCache.stress_reverse](../CellsProofs/Chemistry/GardCache.lean#L171)

Direct proof subject `cells.rate_factor.gard_catalysis_pair_consistent@2`

Proof sources [Mathlib finite-sum inequality, used to bound each weighted composition](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/Order/BigOperators/Group/Finset.lean#L102-L113) · [Mathlib least-witness principle, used to construct the nearest-word grid model](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Data/Nat/Find.lean#L56-L74) · [Ogita, Rump and Oishi, Theorem 3.4. The published TwoSum interface is an explicit assumption of the Cells specialization](https://doi.org/10.1137/030601818)

Uses [Pair-consistent catalysis preserves the heat of a reversible transfer](gard-pair-heat.md)

## Numerical comparison

**Checked.** The 2⁵⁴ stress event returned factors 2 and 2 and zero heat. All 22 signed updates matched the exact row and a fresh compiled fold. A 106-bit row passed and a 107-bit row was refused. The largest count was checked at the cache-function entry point. The repaired engine reproduced the complete earlier passing report byte for byte.

**Engine** `cells.assembly_lineages@1`, `cells.reservoir_exchange@1`, `cells.gard_catalysis_pair_consistent@2`

[TwoSum, founder fold, event update and reverse factor](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/src/cells/models/assembly_lineages/gard.py#L298-L371) · [Public engine model and execution parser](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/src/cells/models/assembly_lineages/spec.py) · [Compiled propensities and event handling](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/src/cells/models/assembly_lineages/kernel.py) · [Public lineage runner and closure](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/src/cells/models/assembly_lineages/runner.py) · [Compiled rate table probe](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/validation/assembly_lineages/probes.py#L210) · [Declared two-type worlds](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/tests/assembly_lineage_fixtures.py) · [Original regression with a dropped low word](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/tests/unit/test_assembly_lineages_kernel.py#L139-L172) · [Row precision, upper exponent and least-tick guards](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/src/cells/models/assembly_lineages/gard.py#L398-L428) · [Explicit molecule capacity at parse](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/src/cells/models/assembly_lineages/spec.py#L360-L375) · [Parser regression for precision, exponent and capacity](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/tests/unit/test_assembly_lineages_spec.py) · [Precision proof and numerical-domain witnesses](https://github.com/Eidosoma/Cells/blob/76418bab8488f24e041b511701b2376811358db8/lean/CellsProofs/Chemistry/GardCache.lean) · [Stress-world construction and comparison](https://github.com/Eidosoma/Cells/blob/76418bab8488f24e041b511701b2376811358db8/lean/checks/gard_catalysis.py) · [Upper margin and least nonzero grid tick](https://github.com/Eidosoma/Cells/blob/76418bab8488f24e041b511701b2376811358db8/lean/CellsProofs/Chemistry/GardRange.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/76418bab8488f24e041b511701b2376811358db8/lean/checks/gard_cache.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/76418bab8488f24e041b511701b2376811358db8/lean/PROGRESS.md#gard-v2-range-repair)

[Tested engine 184fc81cdfc0](https://github.com/Eidosoma/Cells/commit/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956) · [Evidence checkpoint 76418bab8488](https://github.com/Eidosoma/Cells/commit/76418bab8488f24e041b511701b2376811358db8)

**Engine** `cells.assembly_lineages@1`, `cells.reservoir_exchange@1`, `cells.gard_catalysis_pair_consistent@2`

[TwoSum, founder fold, event update and reverse factor](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/models/assembly_lineages/gard.py#L291-L357) · [Row precision and count guards](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/models/assembly_lineages/gard.py#L359-L396) · [Public engine model and execution parser](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/models/assembly_lineages/spec.py) · [Compiled propensities and event handling](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/models/assembly_lineages/kernel.py) · [Public lineage runner and closure](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/models/assembly_lineages/runner.py) · [Compiled rate table probe](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/validation/assembly_lineages/probes.py#L210) · [Declared two-type worlds](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/tests/assembly_lineage_fixtures.py) · [Original regression with a dropped low word](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/tests/unit/test_assembly_lineages_kernel.py#L139-L172) · [Precision proof and numerical-domain witnesses](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/CellsProofs/Chemistry/GardCache.lean) · [Stress-world construction and comparison](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/checks/gard_catalysis.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/checks/gard_cache.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/PROGRESS.md#gard-v2-cache)

[Tested engine 6b28ec553680](https://github.com/Eidosoma/Cells/commit/6b28ec55368011de79dce85e6172b5844b77a287) · [Evidence checkpoint d6db91d64f5c](https://github.com/Eidosoma/Cells/commit/d6db91d64f5c90d8e4857873052f4e667eba7469)

## Biological evidence

**Open.** The underlying composition-dependent entry and exit rates can be measured. The numerical precision of the two-word representation is checked against exact arithmetic.

**Unit** Dimensionless multiplier and kT per event

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
