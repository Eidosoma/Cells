<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A common catalyst factor preserves reversible rate ratios and equilibrium weights

On a positive reversible edge, catalysis preserves the forward-to-reverse rate ratio exactly when both rates receive the same multiplier. The transition-state law assigns a positive factor from the molecules common to both endpoints. The same equilibrium weights then balance the edge.

## Assumptions

- The stabilizations are finite, dimensionless contact energies in kBT. A nonempty common membrane uses its molecular fractions. An empty common membrane has factor 1.
- The rate-ratio identity refers to an available two-way transition. The equilibrium statement assumes the original rates and weights obey detailed balance on each edge.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.AssemblyKinetics.common_residual](../CellsProofs/Chemistry/AssemblyKinetics.lean#L113)
- [CellsProofs.Chemistry.AssemblyKinetics.common_weight](../CellsProofs/Chemistry/AssemblyKinetics.lean#L120)
- [CellsProofs.Chemistry.AssemblyKinetics.empty_factor](../CellsProofs/Chemistry/AssemblyKinetics.lean#L133)
- [CellsProofs.Chemistry.AssemblyKinetics.catalyst_mean](../CellsProofs/Chemistry/AssemblyKinetics.lean#L136)
- [CellsProofs.Chemistry.AssemblyKinetics.catalyst_pos](../CellsProofs/Chemistry/AssemblyKinetics.lean#L144)
- [CellsProofs.Chemistry.AssemblyKinetics.single_contact](../CellsProofs/Chemistry/AssemblyKinetics.lean#L154)
- [CellsProofs.Chemistry.AssemblyKinetics.shared_ratio](../CellsProofs/Chemistry/AssemblyKinetics.lean#L168)
- [CellsProofs.Chemistry.AssemblyKinetics.ratio_iff](../CellsProofs/Chemistry/AssemblyKinetics.lean#L180)
- [CellsProofs.Chemistry.AssemblyKinetics.equilibrium_flow_iff](../CellsProofs/Chemistry/AssemblyKinetics.lean#L174)

Direct proof subject `cells.rate_factor.transition_state_factor@1`

Proof sources [Pythia Eyring rate and positivity proof, imported in the optional check](https://github.com/athanor-ai/pythia/blob/65404339b5c6fe8004d91fdd9c0c14ceb0bf7cd3/Pythia/Frontier/Chemistry/Eyring.lean#L23-L36) · [Cells single-contact factor as the ratio of the two Eyring rates](../checks/chemistry/Reuse.lean#L77)

Uses [Finite molecule counts set stochastic encounter rates and paired event heat](assembly-stochastic-encounter.md)

## Numerical comparison

**Checked.** The directional multipliers agreed with the exact common-state value on 1,925 ordinary reversible edges. In the opposed ±20 kBT contact case, both rates were 2.0611536224/s and the first event occurred at the reference 0.3459699807 s. All four seeded clocks fired four events with closed ledgers. The earlier comparison records the spurious inert state.

**Engine** `cells.assembly_lineages@2`, `cells.stochastic_mass_action@1`, `cells.transition_state_factor@1`, `cells.ideal_mixing@1`, `cells.regular_mixing@1`

[Ordered draws and cancelled membrane denominator](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/mass_action.py) · [Rate factor on the common state](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/transition_state.py) · [Forward and reverse rate assembly](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/kernel.py) · [World balance probe](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/balance.py) · [Independent rational draw and factor](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/validation/ool/references/laws.py) · [Independent rate tolerance](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/validation/ool/references/detailed_balance.py) · [Registered boundary world](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/validation/ool/references/designs/ol1_boundary.world.json) · [assembly lineage v2 fixtures](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/tests/assembly_lineage_v2_fixtures.py) · [probes](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/validation/assembly_lineages_v2/probes.py) · [ol1 wa.world](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/validation/ool/references/designs/ol1_wa.world.json) · [ol1 kernel probe states](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/validation/ool/references/designs/ol1_kernel_probe_states.json) · [ol1 boundary probe states](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/validation/ool/references/designs/ol1_boundary_probe_states.json) · [assembly mixing](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/assembly_mixing.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/assembly_kinetics.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/PROGRESS.md#ol5-six-replays)

[Tested engine 329e9e395ac1](https://github.com/Eidosoma/Cells/commit/329e9e395ac117998657a21eb827192d34314107) · [Evidence checkpoint ad1f96418722](https://github.com/Eidosoma/Cells/commit/ad1f96418722d25876b38b5a5f38996512d6a32c)

**Engine** `cells.assembly_lineages@2`, `cells.stochastic_mass_action@1`, `cells.transition_state_factor@1`, `cells.ideal_mixing@1`, `cells.regular_mixing@1`

[Choice of the count-weighted mean](https://github.com/Eidosoma/Cells/blob/dd085e36e9ced2edfed88c7194e970bd335f3ad0/src/cells/models/assembly_lineages_v2/transition_state.py#L143) · [Common-state transition factor](https://github.com/Eidosoma/Cells/blob/dd085e36e9ced2edfed88c7194e970bd335f3ad0/src/cells/models/assembly_lineages_v2/transition_state.py#L170) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/8f269af4c8b79150020b47a86dd71da848d91714/lean/checks/assembly_kinetics.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/8f269af4c8b79150020b47a86dd71da848d91714/lean/PROGRESS.md#claim-source-review)

[Tested engine dd085e36e9ce](https://github.com/Eidosoma/Cells/commit/dd085e36e9ced2edfed88c7194e970bd335f3ad0) · [Evidence checkpoint 8f269af4c8b7](https://github.com/Eidosoma/Cells/commit/8f269af4c8b79150020b47a86dd71da848d91714)

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
