<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Finite molecule counts set stochastic encounter rates and paired event heat

A molecular encounter draws from the available counts without replacement. For a regular, finite two-way edge with a common locus extent and catalyst factor, log(forward rate / reverse rate) equals minus the free-energy change plus held-reservoir work. At full membrane consumption the declared cancellation determines the boundary rate.

## Assumptions

- Counts and reaction coefficients are natural numbers. The engine admits at most three reactants or products per side. The factorial identity holds for any finite integer order.
- For the regular pair identity the residual membrane count after drawing all reactants is at least the measure offset. At offset one, full consumption without a shared participant uses the cancelled denominator. Overlap at full order can give a singular rate. The kept, extinct and reversible tokens govern which boundary events can fire.
- The occupancy specialization uses one R molecule, distinct G partners, an ideal dilute pool and two reversible states at fixed volume.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.AssemblyKinetics.repeated_pair](../CellsProofs/Chemistry/AssemblyKinetics.lean#L18)
- [CellsProofs.Chemistry.AssemblyKinetics.log_draw](../CellsProofs/Chemistry/AssemblyKinetics.lean#L33)
- [CellsProofs.Chemistry.AssemblyKinetics.encounter_energy](../CellsProofs/Chemistry/AssemblyKinetics.lean#L100)
- [CellsProofs.Chemistry.AssemblyKinetics.pair_heat](../CellsProofs/Chemistry/AssemblyKinetics.lean#L194)
- [CellsProofs.Chemistry.AssemblyKinetics.membrane_cancel](../CellsProofs/Chemistry/AssemblyKinetics.lean#L210)
- [CellsProofs.Chemistry.AssemblyKinetics.last_draw](../CellsProofs/Chemistry/AssemblyKinetics.lean#L218)
- [CellsProofs.Chemistry.AssemblyKinetics.boundary_encounter_energy](../CellsProofs/Chemistry/AssemblyKinetics.lean#L226)
- [CellsProofs.Chemistry.AssemblyKinetics.singular_draw](../CellsProofs/Chemistry/AssemblyKinetics.lean#L239)
- [CellsProofs.Chemistry.AssemblyKinetics.occupancy_by_count](../CellsProofs/Chemistry/AssemblyKinetics.lean#L24)

Direct proof subject `cells.reaction.stochastic_mass_action@1`

Proof sources [Imported Mathlib falling-factorial identity](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Data/Nat/Factorial/Basic.lean#L368)

Uses [Whole-molecule counts set the ideal mixing cost of membrane entry](assembly-ideal-mixing.md) · [One-site binding follows the free ligand concentration](single-site-binding.md)

## Numerical comparison

**Checked.** The reference and engine agreed on ordinary rates and zero and singular patterns across 594 compositions under both count measures. Three boundary conventions were checked on six additional states. The pool kernel reproduced the two-state occupancy formula at one, two and three partners.

**Engine** `cells.assembly_lineages@2`, `cells.stochastic_mass_action@1`, `cells.transition_state_factor@1`, `cells.ideal_mixing@1`, `cells.regular_mixing@1`

[Ordered draws and cancelled membrane denominator](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/mass_action.py) · [Rate factor on the common state](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/transition_state.py) · [Forward and reverse rate assembly](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/kernel.py) · [World balance probe](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/balance.py) · [Independent rational draw and factor](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/validation/ool/references/laws.py) · [Independent rate tolerance](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/validation/ool/references/detailed_balance.py) · [Registered boundary world](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/validation/ool/references/designs/ol1_boundary.world.json) · [assembly lineage v2 fixtures](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/tests/assembly_lineage_v2_fixtures.py) · [probes](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/validation/assembly_lineages_v2/probes.py) · [ol1 wa.world](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/validation/ool/references/designs/ol1_wa.world.json) · [ol1 kernel probe states](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/validation/ool/references/designs/ol1_kernel_probe_states.json) · [ol1 boundary probe states](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/validation/ool/references/designs/ol1_boundary_probe_states.json) · [assembly mixing](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/assembly_mixing.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/assembly_kinetics.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/PROGRESS.md#ol5-six-replays)

[Tested engine 329e9e395ac1](https://github.com/Eidosoma/Cells/commit/329e9e395ac117998657a21eb827192d34314107) · [Evidence checkpoint ad1f96418722](https://github.com/Eidosoma/Cells/commit/ad1f96418722d25876b38b5a5f38996512d6a32c)

**Engine** `cells.assembly_lineages@2`, `cells.stochastic_mass_action@1`, `cells.ideal_mixing@1`

[Pool encounters](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/mass_action.py) · [Concentration extent](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/model.py) · [Pool standard potential and factorial](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/ideal_mixing.py) · [assembly lineage v2 fixtures](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/tests/assembly_lineage_v2_fixtures.py) · [probes](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/validation/assembly_lineages_v2/probes.py) · [shon2012 confined binding](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/data/shon2012_confined_binding.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/confined_binding.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/PROGRESS.md#ol5-six-replays)

[Tested engine 329e9e395ac1](https://github.com/Eidosoma/Cells/commit/329e9e395ac117998657a21eb827192d34314107) · [Evidence checkpoint ad1f96418722](https://github.com/Eidosoma/Cells/commit/ad1f96418722d25876b38b5a5f38996512d6a32c)

**Engine** `cells.assembly_lineages@2`, `cells.stochastic_mass_action@1`, `cells.transition_state_factor@1`, `cells.ideal_mixing@1`, `cells.regular_mixing@1`

[Ordered draws and cancelled membrane denominator](https://github.com/Eidosoma/Cells/blob/e584c79bfe74ef14085479e7d55b8a3975970656/src/cells/models/assembly_lineages_v2/mass_action.py#L76) · [Rate factor on the common state](https://github.com/Eidosoma/Cells/blob/e584c79bfe74ef14085479e7d55b8a3975970656/src/cells/models/assembly_lineages_v2/transition_state.py#L130) · [Forward and reverse rate assembly](https://github.com/Eidosoma/Cells/blob/e584c79bfe74ef14085479e7d55b8a3975970656/src/cells/models/assembly_lineages_v2/kernel.py#L254) · [Inert status for zero total propensity](https://github.com/Eidosoma/Cells/blob/e584c79bfe74ef14085479e7d55b8a3975970656/src/cells/models/assembly_lineages_v2/kernel.py#L463) · [World balance probe](https://github.com/Eidosoma/Cells/blob/e584c79bfe74ef14085479e7d55b8a3975970656/src/cells/models/assembly_lineages_v2/balance.py#L74) · [Independent rational draw and factor](https://github.com/Eidosoma/Cells/blob/e584c79bfe74ef14085479e7d55b8a3975970656/validation/ool/references/laws.py#L222) · [Independent rate tolerance](https://github.com/Eidosoma/Cells/blob/e584c79bfe74ef14085479e7d55b8a3975970656/validation/ool/references/detailed_balance.py#L191) · [Registered boundary world](https://github.com/Eidosoma/Cells/blob/e584c79bfe74ef14085479e7d55b8a3975970656/validation/ool/references/designs/ol1_boundary.world.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/cb4194144bdccd3c4ce4fc24c28979d91a3943a8/lean/checks/assembly_kinetics.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/cb4194144bdccd3c4ce4fc24c28979d91a3943a8/lean/PROGRESS.md#19-november-2026--stochastic-encounters-and-transition-state-catalysis)

[Tested engine e584c79bfe74](https://github.com/Eidosoma/Cells/commit/e584c79bfe74ef14085479e7d55b8a3975970656) · [Evidence checkpoint cb4194144bdc](https://github.com/Eidosoma/Cells/commit/cb4194144bdccd3c4ce4fc24c28979d91a3943a8)

**Engine** `cells.assembly_lineages@2`, `cells.stochastic_mass_action@1`, `cells.ideal_mixing@1`

[Pool encounters](https://github.com/Eidosoma/Cells/blob/e584c79bfe74ef14085479e7d55b8a3975970656/src/cells/models/assembly_lineages_v2/mass_action.py#L102) · [Concentration extent](https://github.com/Eidosoma/Cells/blob/e584c79bfe74ef14085479e7d55b8a3975970656/src/cells/models/assembly_lineages_v2/model.py#L51) · [Pool standard potential and factorial](https://github.com/Eidosoma/Cells/blob/e584c79bfe74ef14085479e7d55b8a3975970656/src/cells/models/assembly_lineages_v2/ideal_mixing.py#L64) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/cb4194144bdccd3c4ce4fc24c28979d91a3943a8/lean/checks/confined_binding.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/cb4194144bdccd3c4ce4fc24c28979d91a3943a8/lean/PROGRESS.md#19-november-2026--stochastic-encounters-and-transition-state-catalysis)

[Tested engine e584c79bfe74](https://github.com/Eidosoma/Cells/commit/e584c79bfe74ef14085479e7d55b8a3975970656) · [Evidence checkpoint cb4194144bdc](https://github.com/Eidosoma/Cells/commit/cb4194144bdccd3c4ce4fc24c28979d91a3943a8)

## Biological evidence

**Open.** Bound probability for one molecule as the integer count of its distinct partner changes, and association events for identical reactants at known counts.

For identical membrane partners, live-cell homodimer imaging measured a 91 ± 16 ms lifetime. It reported surface densities, leaving the repeated-reactant draw at fixed small counts open. [Kasai et al., Figs. 4–6](https://doi.org/10.1083/jcb.201009128)

**Unit** probability

### shon2012_confined_binding@1

Red- and green-labelled complementary strands confined in sealed dimples. Each class fixes the counts of the two distinct partners. Experimental grey bars for one dimer in the three classes with one red strand, at 250 nm radius. Table 1 and Fig. S8 provide the kinetic and independent bulk estimates. [Shon and Cohen (2012), Fig. 4f](https://doi.org/10.1021/ja3062425)

- **Evidence role** held out from fitting
- **Fit** One red molecule and one green partner
- **Evaluation** One red molecule and two green partners, One red molecule and three green partners

The figure shows error bars without tabulated uncertainties for individual bars. We calibrated on the one-partner class and evaluated the other classes from the same experiment. This cancels the common chamber volume. The authors fitted their confined dissociation constant using all classes. A separate calculation using bulk Kd depends appreciably on the volume estimate.

From one partner’s measured 0.48 bound probability, Cells predicted 0.649 and 0.735 with two and three partners. The figure gives about 0.64 and 0.67, respectively. [Dataset manifest](../checks/data/shon2012_confined_binding.json) · [Comparison verdict](../PROGRESS.md#19-november-2026--stochastic-encounters-and-transition-state-catalysis)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
