<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Single-event catalysis can give different forward and reverse cycle rate products

The single-event rule evaluates the moving species’ multiplier at each event’s departure state. This adds the log ratio of two composition-dependent multipliers to the base heat. A rank-one β with only β_AA = 1 gives a four-transfer cycle ratio of 81/80. If adding one to every entry of β gives a positive rank-one matrix, the extra heat is a difference of state values and sums to zero around closed paths.

## Assumptions

- The assembly exchanges with a held reservoir and each reversible edge joins nonempty states. Base propensities and multipliers are positive on the edges in the cycle.
- The explicit square starts with one molecule each of A and B and follows +A, +B, −A, −B. The sufficient rank-one condition is 1 + βᵢⱼ = uᵢvⱼ. Then the correction to the base log weight is −ln(Σⱼ vⱼnⱼ / N).

## Lean proof

**Proved**

- [CellsProofs.Chemistry.GardCatalysis.single_heat](../CellsProofs/Chemistry/GardCatalysis.lean#L72)
- [CellsProofs.Chemistry.GardCatalysis.shifted_factor](../CellsProofs/Chemistry/GardCatalysis.lean#L82)
- [CellsProofs.Chemistry.GardCatalysis.shifted_heat](../CellsProofs/Chemistry/GardCatalysis.lean#L94)
- [CellsProofs.Chemistry.GardCatalysis.raw_rank_one_square](../CellsProofs/Chemistry/GardCatalysis.lean#L117)

Direct proof subject `cells.rate_factor.gard_catalysis_single_event@1`

Uses [Single-molecule exchange heat equals the change in assembly log weight](assembly-exchange-heat.md)

## Numerical comparison

**Checked.** The CPU agreed with rational forward and reverse rate products on 81 four-step cycles across three matrices. The rank-one β example gave 81/80. With a rank-one entrywise shift, all 27 cycles had ratio one in the exact reference and all 70 CPU edges matched the corrected log weight within 4.45 × 10⁻¹⁶ kBT. The lead corrected the design and assigned the matching code wording to the builder. [Design correction](https://github.com/Eidosoma/Cells/blob/0b564f2d99f70995c741456d7f55a515d049dd4d/docs/GARD_DESIGN.md#L320)

**Engine** `cells.assembly_lineages@1`, `cells.reservoir_exchange@1`, `cells.gard_catalysis_pair_consistent@1`, `cells.gard_catalysis_single_event@1`

**Operators** `cells.size_threshold_fission@1`, `cells.daughter_continuation@1`

[Single-event factor](https://github.com/Eidosoma/Cells/blob/f7767ad79edf2f972b78999e64b40f0c294bcf88/src/cells/models/assembly_lineages/gard.py#L137) · [Pair-consistent reverse and terminal factors](https://github.com/Eidosoma/Cells/blob/f7767ad79edf2f972b78999e64b40f0c294bcf88/src/cells/models/assembly_lineages/gard.py#L143) · [Event heat using reverse rates at arrival](https://github.com/Eidosoma/Cells/blob/f7767ad79edf2f972b78999e64b40f0c294bcf88/src/cells/models/assembly_lineages/kernel.py#L299) · [Passive ledger refusal](https://github.com/Eidosoma/Cells/blob/f7767ad79edf2f972b78999e64b40f0c294bcf88/src/cells/models/assembly_lineages/runner.py#L894) · [Compiled rate probe](https://github.com/Eidosoma/Cells/blob/f7767ad79edf2f972b78999e64b40f0c294bcf88/validation/assembly_lineages/probes.py#L210) · [Independent rational propensities](https://github.com/Eidosoma/Cells/blob/f7767ad79edf2f972b78999e64b40f0c294bcf88/validation/gard/references/kernels.py#L279) · [Rate products around a square](https://github.com/Eidosoma/Cells/blob/f7767ad79edf2f972b78999e64b40f0c294bcf88/validation/gard/references/detailed_balance.py#L132) · [Rank-one condition in the finite-reservoir reference](https://github.com/Eidosoma/Cells/blob/f7767ad79edf2f972b78999e64b40f0c294bcf88/validation/gard/references/closed_world.py#L202) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/f382628833be3f23b53cd95ac0a52ec15a76e6ca/lean/checks/gard_catalysis.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/f382628833be3f23b53cd95ac0a52ec15a76e6ca/lean/PROGRESS.md#19-november-2026--gard-catalysis-on-reversible-transfers)

[Tested engine f7767ad79edf](https://github.com/Eidosoma/Cells/commit/f7767ad79edf2f972b78999e64b40f0c294bcf88) · [Evidence checkpoint f382628833be](https://github.com/Eidosoma/Cells/commit/f382628833be3f23b53cd95ac0a52ec15a76e6ca)

## Biological evidence

**Open.** Forward and reverse transition rates around the same four known lipid compositions under a fixed reservoir, including the identity of the moving lipid.

**Unit** dimensionless ratio of rate products

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
