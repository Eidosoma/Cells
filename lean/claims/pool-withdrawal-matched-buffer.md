<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Matched-buffer heat per molecule tends to zero when sampling follows the liquid volume fraction

When the buffer supplies exactly the fraction f of the starting count at each place, the mixing heat of every split lies between zero and its physical split score. For one nonempty place with n molecules and sampler probability q=f, the mean heat is positive and at most the entropy of the withdrawn count, hence at most ln(n+1) in k_BT. The mean per starting molecule tends to zero along increasing, exactly matched pool sizes.

## Assumptions

- The finite pool has the additive discrete ideal free energy. All counts are nonnegative integers and 0 < f < 1. Exact matching requires b = nf for every place being compared.
- The mean uses one independent uniform midpoint word per original molecule. The volume fraction and its finite-word probability must agree for the entropy bound, including the tested quarters, halves, eighths and three-quarters.
- The limit concerns a fixed fraction and a sequence of admissible pool sizes tending to infinity. The finite bound applies at every positive size with an exactly matched integer buffer.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.MatchedBuffer.matched_mass](../CellsProofs/Chemistry/MatchedBuffer.lean#L38)
- [CellsProofs.Chemistry.MatchedBuffer.heat_le_split_score](../CellsProofs/Chemistry/MatchedBuffer.lean#L66)
- [CellsProofs.Chemistry.MatchedBuffer.booked_heat_bounds](../CellsProofs/Chemistry/MatchedBuffer.lean#L73)
- [CellsProofs.Chemistry.MatchedBuffer.mean_from_word_counts](../CellsProofs/Chemistry/MatchedBuffer.lean#L106)
- [CellsProofs.Chemistry.MatchedBuffer.mean_le_split_entropy](../CellsProofs/Chemistry/MatchedBuffer.lean#L138)
- [CellsProofs.Chemistry.MatchedBuffer.mean_bounds](../CellsProofs/Chemistry/MatchedBuffer.lean#L152)
- [CellsProofs.Chemistry.MatchedBuffer.per_molecule_bound](../CellsProofs/Chemistry/MatchedBuffer.lean#L168)
- [CellsProofs.Chemistry.MatchedBuffer.per_molecule_limit](../CellsProofs/Chemistry/MatchedBuffer.lean#L176)

Direct proof subject `cells.operator.pool_withdrawal@1`

Proof sources [Mathlib adjacent binomial coefficient identity, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Data/Nat/Choose/Basic.lean#L120-L126) · [Mathlib logarithm tangent bound, specialized to the uniform count distribution](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/SpecialFunctions/Log/Basic.lean#L288-L290) · [Mathlib sublinear growth of log, imported for the per-molecule limit](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/SpecialFunctions/Log/Basic.lean#L399-L402) · [Mathlib reciprocal limit for natural counts, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/SpecificLimits/Basic.lean#L36-L40) · [Cells binomial energy and finite word calculation](../CellsProofs/Chemistry/PoolWithdrawalEnergy.lean#L102-L115) · [Matched-concentration design and finite-pool reference](../../docs/ASSEMBLY_WITHDRAWAL_DESIGN.md#L182-L191)

Uses [Partial withdrawal closes the energy balance and releases nonnegative mixing heat](pool-withdrawal-energy.md)

## Numerical comparison

**Checked.** All 42,875 exact count comparisons passed. Across seven parsed pools and 575 guarded outcomes, the largest heat error against an 88-digit reference was 1.13 × 10⁻¹² k_BT. In a quarter wash the mean heat per starting molecule was 0.024193 k_BT at n=100 and 0.007775 k_BT at n=400. A complete three-species wash booked 4.535007 k_BT of heat against a split score of 5.164075.

**Engine** `cells.assembly_lineages@2`, `cells.ideal_mixing@1`

**Operators** `cells.pool_withdrawal@1`

[Parsed buffer, pre-draw guard and sampled counts](https://github.com/Eidosoma/Cells/blob/2ae9ce8e5c6b56ecab091b6167d034eb97a5520f/src/cells/models/assembly_lineages_v2/withdrawal.py#L81-L171) · [Five energy fields of a withdrawal](https://github.com/Eidosoma/Cells/blob/2ae9ce8e5c6b56ecab091b6167d034eb97a5520f/src/cells/models/assembly_lineages_v2/withdrawal.py#L173-L198) · [Normal population receipt](https://github.com/Eidosoma/Cells/blob/2ae9ce8e5c6b56ecab091b6167d034eb97a5520f/src/cells/models/assembly_lineages_v2/population.py#L785-L825) · [Discrete ideal free energy](https://github.com/Eidosoma/Cells/blob/2ae9ce8e5c6b56ecab091b6167d034eb97a5520f/src/cells/models/assembly_lineages_v2/ideal_mixing.py#L64-L78) · [Guarded pool energy table](https://github.com/Eidosoma/Cells/blob/2ae9ce8e5c6b56ecab091b6167d034eb97a5520f/src/cells/models/assembly_lineages_v2/ledger.py#L58-L81) · [Stream word grid](https://github.com/Eidosoma/Cells/blob/2ae9ce8e5c6b56ecab091b6167d034eb97a5520f/src/cells/models/assembly_lineages/streams.py#L120-L128) · [Population fixture and matched quarter-volume control](https://github.com/Eidosoma/Cells/blob/2ae9ce8e5c6b56ecab091b6167d034eb97a5520f/tests/unit/test_assembly_lineages_v2_replacement.py#L594-L727) · [Matched-buffer proofs](https://github.com/Eidosoma/Cells/blob/841e06cd5d0e97b449b6eb5fdfa55f4e4376da86/lean/CellsProofs/Chemistry/MatchedBuffer.lean) · [Per-outcome energy and count probabilities](https://github.com/Eidosoma/Cells/blob/841e06cd5d0e97b449b6eb5fdfa55f4e4376da86/lean/CellsProofs/Chemistry/PoolWithdrawalEnergy.lean) · [Independent energy and log-factorial reference](https://github.com/Eidosoma/Cells/blob/841e06cd5d0e97b449b6eb5fdfa55f4e4376da86/lean/checks/pool_withdrawal_energy.py) · [Exact word cutoffs](https://github.com/Eidosoma/Cells/blob/841e06cd5d0e97b449b6eb5fdfa55f4e4376da86/lean/checks/pool_withdrawal.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/841e06cd5d0e97b449b6eb5fdfa55f4e4376da86/lean/checks/matched_buffer.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/841e06cd5d0e97b449b6eb5fdfa55f4e4376da86/lean/PROGRESS.md#matched-buffer-heat)

[Tested engine 2ae9ce8e5c6b](https://github.com/Eidosoma/Cells/commit/2ae9ce8e5c6b56ecab091b6167d034eb97a5520f) · [Evidence checkpoint 841e06cd5d0e](https://github.com/Eidosoma/Cells/commit/841e06cd5d0e97b449b6eb5fdfa55f4e4376da86)

## Biological evidence

**Open.** Mean energy dissipated per starting tracer molecule in a partial exchange, with measured volumes and counts and concentration-matched buffer, across a range of pool sizes.

**Unit** k_BT per starting molecule

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
