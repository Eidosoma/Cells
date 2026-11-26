<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Dissipated free energy as tracer refills a washed pool

Between washes the free energy of the two mean tracer counts is nonincreasing, including at an empty starting place. Its drop is the deterministic continuous interval heat. Replacing an empty place’s initial term by its one-molecule value shifts the heat by (μ° − ln X − 1) kBT when both final counts are positive.

## Assumptions

- Two well-mixed compartments of fixed positive volumes exchange a single passive tracer during the interval. Temperature, standard potentials and the shell conductance are fixed. The surviving mean counts are nonnegative and their sum is conserved. Unchanged wall terms cancel in the difference.
- The free energy of a place in kBT is n(μ° − ln X) + n ln n − n, with μ° in RT units, X = N_A V c₀ in molecules and the continuous value zero at n = 0. Positive entry and exit rates obey ln k_in − ln k_out = (μ°outside − ln Xoutside) − (μ°inside − ln Xinside). A completely impermeable shell has both rates zero.
- The interval runs from just after the preceding wash to just before the following wash, or to the observation horizon. Each wash carries its own work, sink and mixing entries.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.ShellIntervalHeat.site_continuous](../CellsProofs/Chemistry/ShellIntervalHeat.lean#L21)
- [CellsProofs.Chemistry.ShellIntervalHeat.site_zero](../CellsProofs/Chemistry/ShellIntervalHeat.lean#L24)
- [CellsProofs.Chemistry.ShellIntervalHeat.shell_rate_balance](../CellsProofs/Chemistry/ShellIntervalHeat.lean#L29)
- [CellsProofs.Chemistry.ShellIntervalHeat.energy_derivative](../CellsProofs/Chemistry/ShellIntervalHeat.lean#L46)
- [CellsProofs.Chemistry.ShellIntervalHeat.energy_antitone](../CellsProofs/Chemistry/ShellIntervalHeat.lean#L88)
- [CellsProofs.Chemistry.ShellIntervalHeat.postwash_heat_nonneg](../CellsProofs/Chemistry/ShellIntervalHeat.lean#L122)
- [CellsProofs.Chemistry.ShellIntervalHeat.impermeable_heat](../CellsProofs/Chemistry/ShellIntervalHeat.lean#L131)
- [CellsProofs.Chemistry.ShellIntervalHeat.one_molecule_bias](../CellsProofs/Chemistry/ShellIntervalHeat.lean#L138)

Direct proof subject `cells.assembly_representation.rate_equations@1`, `cells.free_energy.ideal_mixing@1`, `cells.assembly_geometry.prescribed_shell@1`, `cells.reaction.shell_permeation@1`

Proof sources [Registered FR-47 mean-state energy and units](https://github.com/Eidosoma/Cells/blob/231aae399bd9f8d5db35bc31fe95207ec664ab7b/validation/assembly_lineages_v2/fr47_spec/SPEC.md#L109-L118) · [Registered whole-term P9 substitution](https://github.com/Eidosoma/Cells/blob/231aae399bd9f8d5db35bc31fe95207ec664ab7b/validation/assembly_lineages_v2/fr47_spec/CRITERIA.md#L65-L69) · [Mathlib continuity and derivative of x log x, imported for each ideal place](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/SpecialFunctions/Log/NegMulLog.lean#L27-L60) · [Mathlib nonpositive interior derivative, specialized to a closed interval starting at zero](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Calculus/Deriv/MeanValue.lean#L488-L496) · [Cells ideal concentration term, reused locally](../CellsProofs/Chemistry/ReleaseEnergy.lean#L17) · [Cells finite-pool derivative, specialized to a conserved tracer](../CellsProofs/Chemistry/ShellWashRecovery.lean#L31) · [Exact positive-heat and P9 controls](../checks/chemistry/ShellIntervalHeat.lean)

Uses [Tracer returns to a finite exterior pool after a wash](fr47-shell-wash-recovery.md) · [Whole-molecule counts set the ideal mixing cost of membrane entry](assembly-ideal-mixing.md)

## Numerical comparison

**Checked.** On development build 43763a36, all three synthetic intervals agreed within 6.60 × 10⁻⁸ kBT. After full replacement the engine booked 38.34719503 kBT against 38.34719500 predicted. The whole-term substitution gave 24.33882673 kBT. It also changed the empty-lumen interval and had zero effect on the interval with two occupied places. This comparison uses invented inputs. D373 records the independent FR-47 qualification and the separate schedule check. [Qualification decision](https://github.com/Eidosoma/Cells/blob/9b6191bdf0800d70dcae81107378401ab3c8b474/docs/DECISIONS.md#L12337-L12362)

**Engine** `cells.assembly_lineages@2`, `cells.rate_equations@1`, `cells.ideal_mixing@1`, `cells.prescribed_shell@1`, `cells.shell_permeation@1`

**Operators** `cells.pool_replacement@1`, `cells.pool_withdrawal@1`

[Continuous ideal free energy at real counts](https://github.com/Eidosoma/Cells/blob/43763a36f27d4dcf8381770649d6a59e4747ddf5/src/cells/models/assembly_lineages_v2/ideal_mixing.py#L106) · [Deterministic one-way shell fluxes](https://github.com/Eidosoma/Cells/blob/43763a36f27d4dcf8381770649d6a59e4747ddf5/src/cells/models/assembly_lineages_v2/rate_equations.py#L822) · [Heat booking for a step starting at zero](https://github.com/Eidosoma/Cells/blob/43763a36f27d4dcf8381770649d6a59e4747ddf5/src/cells/models/assembly_lineages_v2/rate_equations.py#L1784) · [Reader for continuous heat between stops](https://github.com/Eidosoma/Cells/blob/43763a36f27d4dcf8381770649d6a59e4747ddf5/validation/assembly_lineages_v2/fr47_judge.py#L195) · [Nonregistered shell fixture](https://github.com/Eidosoma/Cells/blob/43763a36f27d4dcf8381770649d6a59e4747ddf5/tests/unit/test_assembly_lineages_v2_rate_equations_population.py#L86) · [Passive interval heat theorem](https://github.com/Eidosoma/Cells/blob/499980de46f30e883d968db7e3d7e6dc9e337434/lean/CellsProofs/Chemistry/ShellIntervalHeat.lean) · [Two-molecule and whole-term controls](https://github.com/Eidosoma/Cells/blob/499980de46f30e883d968db7e3d7e6dc9e337434/lean/checks/chemistry/ShellIntervalHeat.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/499980de46f30e883d968db7e3d7e6dc9e337434/lean/checks/shell_interval_heat.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/499980de46f30e883d968db7e3d7e6dc9e337434/lean/PROGRESS.md#fr47-shell-interval-heat)

[Tested engine 43763a36f27d](https://github.com/Eidosoma/Cells/commit/43763a36f27d4dcf8381770649d6a59e4747ddf5) · [Evidence checkpoint 499980de46f3](https://github.com/Eidosoma/Cells/commit/499980de46f30e883d968db7e3d7e6dc9e337434)

## Biological evidence

**Open.** Free energy dissipated as tracer returns to a freshly washed finite exterior, measured by reversible work or inferred from independent chemical-potential differences over the transfer.

**Unit** kBT per wash-free interval

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
