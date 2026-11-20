<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A common catalyst factor preserves reversible rate ratios and equilibrium weights

On a positive reversible edge, catalysis preserves the forward-to-reverse rate ratio exactly when both rates receive the same multiplier. The transition-state law assigns a positive factor from the molecules common to both endpoints. The same equilibrium weights then balance the edge.

## Assumptions

- The stabilizations are finite, dimensionless contact energies in kBT. A nonempty common membrane uses its molecular fractions. An empty common membrane has factor 1.
- The rate-ratio identity refers to an available two-way transition. The equilibrium statement assumes the original rates and weights obey detailed balance on each edge.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.AssemblyKinetics.common_residual](../CellsProofs/Chemistry/AssemblyKinetics.lean#L89)
- [CellsProofs.Chemistry.AssemblyKinetics.common_weight](../CellsProofs/Chemistry/AssemblyKinetics.lean#L96)
- [CellsProofs.Chemistry.AssemblyKinetics.empty_factor](../CellsProofs/Chemistry/AssemblyKinetics.lean#L109)
- [CellsProofs.Chemistry.AssemblyKinetics.catalyst_mean](../CellsProofs/Chemistry/AssemblyKinetics.lean#L112)
- [CellsProofs.Chemistry.AssemblyKinetics.catalyst_pos](../CellsProofs/Chemistry/AssemblyKinetics.lean#L120)
- [CellsProofs.Chemistry.AssemblyKinetics.single_contact](../CellsProofs/Chemistry/AssemblyKinetics.lean#L130)
- [CellsProofs.Chemistry.AssemblyKinetics.shared_ratio](../CellsProofs/Chemistry/AssemblyKinetics.lean#L144)
- [CellsProofs.Chemistry.AssemblyKinetics.ratio_iff](../CellsProofs/Chemistry/AssemblyKinetics.lean#L156)
- [CellsProofs.Chemistry.AssemblyKinetics.equilibrium_flow_iff](../CellsProofs/Chemistry/AssemblyKinetics.lean#L150)

Direct proof subject `cells.transition_state_factor@1`

Uses [Finite molecule counts set stochastic encounter rates and paired event heat](assembly-stochastic-encounter.md)

## Numerical comparison

**Failed.** Both directional multipliers agreed with the exact common-state value on 1,925 ordinary reversible edges. In an admitted two-molecule world with +20 kBT moving contacts and −20 kBT for the stationary molecule, float64 gives both rates as zero instead of 2.0611536224/s. The compiled run returns inert with a passing ledger. The equivalent constant-rate control fires at 0.3459699807 s on the same draw. With neutral movers and the same stationary contact, the clock runs with a 2.00 × 10⁻⁸ relative rate error.

**Engine** `cells.assembly_lineages@2`, `cells.stochastic_mass_action@1`, `cells.transition_state_factor@1`, `cells.ideal_mixing@1`, `cells.regular_mixing@1`

[Transition-state factor](https://github.com/Eidosoma/Cells/blob/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc/src/cells/models/assembly_lineages_v2/transition_state.py#L130) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/b4353f85b18d489a277818bfe43e20c8416b6066/lean/checks/assembly_kinetics.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/b4353f85b18d489a277818bfe43e20c8416b6066/lean/PROGRESS.md#six-numerical-retests)

[Tested engine b9d6452dff1c](https://github.com/Eidosoma/Cells/commit/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc) · [Evidence checkpoint b4353f85b18d](https://github.com/Eidosoma/Cells/commit/b4353f85b18d489a277818bfe43e20c8416b6066)

**Engine** `cells.assembly_lineages@2`, `cells.stochastic_mass_action@1`, `cells.transition_state_factor@1`, `cells.ideal_mixing@1`, `cells.regular_mixing@1`

[Ordered draws and cancelled membrane denominator](https://github.com/Eidosoma/Cells/blob/e584c79bfe74ef14085479e7d55b8a3975970656/src/cells/models/assembly_lineages_v2/mass_action.py#L76) · [Rate factor on the common state](https://github.com/Eidosoma/Cells/blob/e584c79bfe74ef14085479e7d55b8a3975970656/src/cells/models/assembly_lineages_v2/transition_state.py#L130) · [Forward and reverse rate assembly](https://github.com/Eidosoma/Cells/blob/e584c79bfe74ef14085479e7d55b8a3975970656/src/cells/models/assembly_lineages_v2/kernel.py#L254) · [Inert status for zero total propensity](https://github.com/Eidosoma/Cells/blob/e584c79bfe74ef14085479e7d55b8a3975970656/src/cells/models/assembly_lineages_v2/kernel.py#L463) · [World balance probe](https://github.com/Eidosoma/Cells/blob/e584c79bfe74ef14085479e7d55b8a3975970656/src/cells/models/assembly_lineages_v2/balance.py#L74) · [Independent rational draw and factor](https://github.com/Eidosoma/Cells/blob/e584c79bfe74ef14085479e7d55b8a3975970656/validation/ool/references/laws.py#L222) · [Independent rate tolerance](https://github.com/Eidosoma/Cells/blob/e584c79bfe74ef14085479e7d55b8a3975970656/validation/ool/references/detailed_balance.py#L191) · [Registered boundary world](https://github.com/Eidosoma/Cells/blob/e584c79bfe74ef14085479e7d55b8a3975970656/validation/ool/references/designs/ol1_boundary.world.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/cb4194144bdccd3c4ce4fc24c28979d91a3943a8/lean/checks/assembly_kinetics.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/cb4194144bdccd3c4ce4fc24c28979d91a3943a8/lean/PROGRESS.md#19-november-2026--stochastic-encounters-and-transition-state-catalysis)

[Tested engine e584c79bfe74](https://github.com/Eidosoma/Cells/commit/e584c79bfe74ef14085479e7d55b8a3975970656) · [Evidence checkpoint cb4194144bdc](https://github.com/Eidosoma/Cells/commit/cb4194144bdccd3c4ce4fc24c28979d91a3943a8)

## Biological evidence

**Open.** Forward and reverse molecular transfer rates and an independently measured equilibrium partition under matched temperature and catalyst concentration.

At 37 °C, cholesterol exchange between vesicles sped up about 57-fold with 1 mM β-cyclodextrin. Half-times were 195 ± 13 and about 3.4 minutes. A separate 0.5 mM equilibrium series gave a partition coefficient of 0.91 ± 0.06. Equal scaling of the two directional rates remains unmeasured. This transfer catalyst is in solution. [Leventis and Silvius, Figs. 1–2 and Table 1](https://doi.org/10.1016/S0006-3495(01)75873-0)

**Unit** s⁻¹ for each direction, dimensionless equilibrium partition

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
