<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Partial withdrawal closes the energy balance and releases nonnegative mixing heat

For every count split and supplied buffer, the change of pool free energy equals buffer work minus pool loss minus mixing heat. The loss equals sample free energy minus the physical binomial split score. Both the split score and the mixing heat are nonnegative. For a tracer-free buffer the mean heat per initial tracer is −(1−q) ln(1−f), where q is the effective withdrawal probability and f is the physical volume fraction.

## Assumptions

- The pool has finitely many places with nonnegative integer counts. Its discrete ideal free energy is additive over finite species and includes the log factorial of each count. The buffer fills the withdrawn volume and the full pool volume is restored.
- The physical fraction f lies strictly between zero and one. Work, sink and heat use Cells’ withdrawal convention in units of k_BT. Closure and signs hold for each realized split.
- Sampler probabilities and mean heats assume independent, uniformly distributed word indices. Cells compares each midpoint from 2⁵² bins strictly to f. The split-score comparison uses outcomes with positive sampler probability.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.PoolWithdrawalEnergy.binomial_mass](../CellsProofs/Chemistry/PoolWithdrawalEnergy.lean#L20)
- [CellsProofs.Chemistry.PoolWithdrawalEnergy.partition_cost](../CellsProofs/Chemistry/PoolWithdrawalEnergy.lean#L55)
- [CellsProofs.Chemistry.PoolWithdrawalEnergy.energy_balance](../CellsProofs/Chemistry/PoolWithdrawalEnergy.lean#L87)
- [CellsProofs.Chemistry.PoolWithdrawalEnergy.binomial_bookings](../CellsProofs/Chemistry/PoolWithdrawalEnergy.lean#L102)
- [CellsProofs.Chemistry.PoolWithdrawalEnergy.nonnegative_heat_and_split](../CellsProofs/Chemistry/PoolWithdrawalEnergy.lean#L108)
- [CellsProofs.Chemistry.PoolWithdrawalEnergy.tracer_free_heat](../CellsProofs/Chemistry/PoolWithdrawalEnergy.lean#L117)
- [CellsProofs.Chemistry.PoolWithdrawalEnergy.mean_tracer_free_heat](../CellsProofs/Chemistry/PoolWithdrawalEnergy.lean#L126)
- [CellsProofs.Chemistry.PoolWithdrawalEnergy.sampled_count_mass](../CellsProofs/Chemistry/PoolWithdrawalEnergy.lean#L169)
- [CellsProofs.Chemistry.PoolWithdrawalEnergy.sampled_score_gap](../CellsProofs/Chemistry/PoolWithdrawalEnergy.lean#L177)
- [CellsProofs.Chemistry.PoolWithdrawalEnergy.last_midpoint_mean_heat](../CellsProofs/Chemistry/PoolWithdrawalEnergy.lean#L196)
- [CellsProofs.Chemistry.PoolWithdrawalEnergy.last_midpoint_gap](../CellsProofs/Chemistry/PoolWithdrawalEnergy.lean#L211)

Direct proof subject `cells.operator.pool_withdrawal@1`

Proof sources [Mathlib binomial distribution and its point mass, imported and specialized](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Probability/ProbabilityMassFunction/Binomial.lean#L25-L44) · [Mathlib bound on the mass of a single outcome, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Probability/ProbabilityMassFunction/Basic.lean#L115) · [Mathlib binomial coefficient and factorial identity, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Data/Nat/Choose/Basic.lean#L174) · [Cells proof of the midpoint sampler’s count law](../CellsProofs/Chemistry/PoolWithdrawal.lean#L91-L125) · [Discrete energy and expected heat convention in the withdrawal design](../../docs/ASSEMBLY_WITHDRAWAL_DESIGN.md#L101-L175)

Uses [Partial pool withdrawal conserves counts and fixes their conditional moments](pool-withdrawal.md) · [Whole-molecule counts set the ideal mixing cost of membrane entry](assembly-ideal-mixing.md)

## Numerical comparison

**Checked.** Three complete worlds and 1,080 small-count cases matched an 88-digit independent reference. The largest balance error was 6.21 × 10⁻¹⁴ k_BT. All booked heats were nonnegative. At f = 1−2⁻⁵³ the last word retains one tracer, the split score exceeds its sampler score by ln 2, and the word-weighted tracer-free mean is 8.1572 × 10⁻¹⁵ k_BT against an ideal-volume mean of 4.0786 × 10⁻¹⁵ k_BT.

**Engine** `cells.assembly_lineages@2`, `cells.ideal_mixing@1`

**Operators** `cells.pool_withdrawal@1`

[Per-place sample and five signed energy fields](https://github.com/Eidosoma/Cells/blob/695f8cdd974e130f25b021df8efeabe4cac8a515/src/cells/models/assembly_lineages_v2/withdrawal.py#L140-L188) · [Host receipt, work column, sink and heat](https://github.com/Eidosoma/Cells/blob/695f8cdd974e130f25b021df8efeabe4cac8a515/src/cells/models/assembly_lineages_v2/population.py#L785-L825) · [Discrete free energy in the finite pool](https://github.com/Eidosoma/Cells/blob/695f8cdd974e130f25b021df8efeabe4cac8a515/src/cells/models/assembly_lineages_v2/ideal_mixing.py#L64-L78) · [Host free energy and table guard](https://github.com/Eidosoma/Cells/blob/695f8cdd974e130f25b021df8efeabe4cac8a515/src/cells/models/assembly_lineages_v2/ledger.py#L46-L81) · [Word addresses for each sampled place](https://github.com/Eidosoma/Cells/blob/695f8cdd974e130f25b021df8efeabe4cac8a515/src/cells/models/assembly_lineages_v2/streams.py#L49-L66) · [Conversion to a uniform midpoint](https://github.com/Eidosoma/Cells/blob/695f8cdd974e130f25b021df8efeabe4cac8a515/src/cells/models/assembly_lineages/streams.py#L120-L128) · [Acceptance world and independent withdrawal booking tests](https://github.com/Eidosoma/Cells/blob/695f8cdd974e130f25b021df8efeabe4cac8a515/tests/unit/test_assembly_lineages_v2_replacement.py#L594-L735) · [Exact energy and word-weighted heat proof](https://github.com/Eidosoma/Cells/blob/59f5bba6d8773a907706db8333ac8e9ca6d29cea/lean/CellsProofs/Chemistry/PoolWithdrawalEnergy.lean) · [Finite-word counting law](https://github.com/Eidosoma/Cells/blob/59f5bba6d8773a907706db8333ac8e9ca6d29cea/lean/CellsProofs/Chemistry/PoolWithdrawal.lean) · [Discrete site energy](https://github.com/Eidosoma/Cells/blob/59f5bba6d8773a907706db8333ac8e9ca6d29cea/lean/CellsProofs/Chemistry/AssemblyMixing.lean) · [Binomial expectation on finite trials](https://github.com/Eidosoma/Cells/blob/59f5bba6d8773a907706db8333ac8e9ca6d29cea/lean/CellsProofs/Chemistry/LineageFission.lean) · [Shared exact word indices and thresholds](https://github.com/Eidosoma/Cells/blob/59f5bba6d8773a907706db8333ac8e9ca6d29cea/lean/checks/pool_withdrawal.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/59f5bba6d8773a907706db8333ac8e9ca6d29cea/lean/checks/pool_withdrawal_energy.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/59f5bba6d8773a907706db8333ac8e9ca6d29cea/lean/PROGRESS.md#fr35-withdrawal-energy)

[Tested engine 695f8cdd974e](https://github.com/Eidosoma/Cells/commit/695f8cdd974e130f25b021df8efeabe4cac8a515) · [Evidence checkpoint 59f5bba6d877](https://github.com/Eidosoma/Cells/commit/59f5bba6d8773a907706db8333ac8e9ca6d29cea)

## Biological evidence

**Open.** Independent energy budget for a measured partial withdrawal with known tracer counts, buffer content, liquid volumes and work during resupply.

**Unit** k_BT per withdrawal

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
