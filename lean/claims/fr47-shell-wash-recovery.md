<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Tracer returns to a finite exterior pool after a wash

A full tracer-free wash leaves the retained lumen mean L and sets the exterior count to zero. With constant per-molecule rates k_in into the lumen and k_out back out, the exterior mean at elapsed time t is L k_out (1 − exp(−s t))/s, where s = k_in + k_out > 0. Its right derivative at the wash is k_out L. A later withdrawal of fraction f on the sampler’s word grid removes f times that recovered mean.

## Assumptions

- A finite set of tracers exchanges between two well-mixed compartments of fixed positive volume. Each tracer obeys the two-state forward equation between washes. Molecules removed by a wash stay absent. The interval has constant rates and conserves the surviving tracer.
- The physical rates per second are k_in = P A / V_out and k_out = P A exp(Δ) / V_in, with volumes in m³, permeability P in m/s, area A in m² and Δ = (μ°lumen − μ°solution)/RT. A fixed gate can multiply both rates by the same factor.
- A complete replacement exchanges the exterior for tracer-free medium. At the next fractional withdrawal, each exterior molecule has the declared removal probability, independently, under the sampler’s equal-weight word law. The fraction is exactly representable on its grid.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.ShellWashRecovery.mean_flux](../CellsProofs/Chemistry/ShellWashRecovery.lean#L20)
- [CellsProofs.Chemistry.ShellWashRecovery.exterior_derivative](../CellsProofs/Chemistry/ShellWashRecovery.lean#L33)
- [CellsProofs.Chemistry.ShellWashRecovery.unique_on_interval](../CellsProofs/Chemistry/ShellWashRecovery.lean#L44)
- [CellsProofs.Chemistry.ShellWashRecovery.recovery_curve](../CellsProofs/Chemistry/ShellWashRecovery.lean#L62)
- [CellsProofs.Chemistry.ShellWashRecovery.initial_recovery](../CellsProofs/Chemistry/ShellWashRecovery.lean#L71)
- [CellsProofs.Chemistry.ShellWashRecovery.recovery_bounds](../CellsProofs/Chemistry/ShellWashRecovery.lean#L81)
- [CellsProofs.Chemistry.ShellWashRecovery.withdrawal_mean](../CellsProofs/Chemistry/ShellWashRecovery.lean#L95)
- [CellsProofs.Chemistry.ShellWashRecovery.removed_after_recovery](../CellsProofs/Chemistry/ShellWashRecovery.lean#L110)

Direct proof subject `cells.assembly_geometry.prescribed_shell@1`, `cells.reaction.shell_permeation@1`, `cells.operator.pool_replacement@1`, `cells.operator.pool_withdrawal@1`

Proof sources [Registered FR-47 rates, finite bath and wash actions](https://github.com/Eidosoma/Cells/blob/231aae399bd9f8d5db35bc31fe95207ec664ab7b/validation/assembly_lineages_v2/fr47_spec/SPEC.md#L37-L79) · [Mathlib ODE uniqueness on a closed time interval, imported and specialized to shell exchange](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/ODE/Gronwall.lean#L351-L364) · [Mathlib derivative of a finite sum, imported to close the mean equation](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Calculus/Deriv/Add.lean#L184-L186) · [Cells constant-source interval solution, reused with source k_out times surviving total](../CellsProofs/Chemistry/SpeciesTurnover.lean#L73) · [Cells conditional mean of the sampler, reused at each possible exterior count](../CellsProofs/Chemistry/PoolWithdrawal.lean#L107)

Uses [Shell entry and exit depend on conductance and the gate’s own forms](prescribed-shell-rates.md) · [Production and first-order clearance preserve a positive pool and account for gross turnover](scheduled-species-turnover.md) · [Partial pool withdrawal conserves counts and fixes their conditional moments](pool-withdrawal.md)

## Numerical comparison

**Checked.** On cf5ddcff replacement removed five exterior tracers and left seven in the lumen. The eight-state host rate matrix gave exterior means of 1.3607043414 at 0.75 s and 2.8910229384 at 2 s. The native half-withdrawal averaged 1.4455114692 removed. All agreed within 10⁻¹² molecules. On the separate deterministic development build 43763a36, all six compartment reads and both removed amounts met a 0.00024-molecule tolerance on an invented 240-tracer shell. FR-47 subsequently passed its registered qualification. [D373](https://github.com/Eidosoma/Cells/blob/9b6191bdf0800d70dcae81107378401ab3c8b474/docs/DECISIONS.md#L12337-L12362)

**Engine** `cells.assembly_lineages@2`, `cells.prescribed_shell@1`, `cells.shell_permeation@1`

**Operators** `cells.pool_replacement@1`, `cells.pool_withdrawal@1`

[Per-state host rates](https://github.com/Eidosoma/Cells/blob/cf5ddcff0054eac89a02f34c6cfe740ed5d833ce/src/cells/models/assembly_lineages_v2/balance.py#L56) · [Forward and reverse shell rates](https://github.com/Eidosoma/Cells/blob/cf5ddcff0054eac89a02f34c6cfe740ed5d833ce/src/cells/models/assembly_lineages_v2/kernel.py#L279) · [Full replacement and the finite pool](https://github.com/Eidosoma/Cells/blob/cf5ddcff0054eac89a02f34c6cfe740ed5d833ce/src/cells/models/assembly_lineages_v2/transfer.py#L81) · [Removed and supplied counts](https://github.com/Eidosoma/Cells/blob/cf5ddcff0054eac89a02f34c6cfe740ed5d833ce/src/cells/models/assembly_lineages_v2/replacement.py#L130) · [Threshold draw for each molecule](https://github.com/Eidosoma/Cells/blob/cf5ddcff0054eac89a02f34c6cfe740ed5d833ce/src/cells/models/assembly_lineages_v2/withdrawal.py#L150) · [Shell fixture with an absolute lumen potential](https://github.com/Eidosoma/Cells/blob/cf5ddcff0054eac89a02f34c6cfe740ed5d833ce/tests/unit/test_assembly_lineages_v2_shell_interior.py#L35) · [Two-compartment mean and its unique trajectory](https://github.com/Eidosoma/Cells/blob/db1278778fa36e4f9376eea783d199783ded5b2f/lean/CellsProofs/Chemistry/ShellWashRecovery.lean) · [Analytic controls for both reads and the next draw](https://github.com/Eidosoma/Cells/blob/db1278778fa36e4f9376eea783d199783ded5b2f/lean/checks/chemistry/ShellWashRecovery.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/db1278778fa36e4f9376eea783d199783ded5b2f/lean/checks/shell_wash_recovery.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/db1278778fa36e4f9376eea783d199783ded5b2f/lean/PROGRESS.md#fr47-shell-wash-recovery)

[Tested engine cf5ddcff0054](https://github.com/Eidosoma/Cells/commit/cf5ddcff0054eac89a02f34c6cfe740ed5d833ce) · [Evidence checkpoint db1278778fa3](https://github.com/Eidosoma/Cells/commit/db1278778fa36e4f9376eea783d199783ded5b2f)

**Engine** `cells.assembly_lineages@2`, `cells.rate_equations@1`, `cells.ideal_mixing@1`, `cells.prescribed_shell@1`, `cells.shell_permeation@1`

**Operators** `cells.pool_replacement@1`, `cells.pool_withdrawal@1`

[Continuous ideal free energy at real counts](https://github.com/Eidosoma/Cells/blob/43763a36f27d4dcf8381770649d6a59e4747ddf5/src/cells/models/assembly_lineages_v2/ideal_mixing.py#L106) · [Deterministic one-way shell fluxes](https://github.com/Eidosoma/Cells/blob/43763a36f27d4dcf8381770649d6a59e4747ddf5/src/cells/models/assembly_lineages_v2/rate_equations.py#L822) · [Heat booking for a step starting at zero](https://github.com/Eidosoma/Cells/blob/43763a36f27d4dcf8381770649d6a59e4747ddf5/src/cells/models/assembly_lineages_v2/rate_equations.py#L1784) · [Reader for continuous heat between stops](https://github.com/Eidosoma/Cells/blob/43763a36f27d4dcf8381770649d6a59e4747ddf5/validation/assembly_lineages_v2/fr47_judge.py#L195) · [Nonregistered shell fixture](https://github.com/Eidosoma/Cells/blob/43763a36f27d4dcf8381770649d6a59e4747ddf5/tests/unit/test_assembly_lineages_v2_rate_equations_population.py#L86) · [Passive interval heat theorem](https://github.com/Eidosoma/Cells/blob/499980de46f30e883d968db7e3d7e6dc9e337434/lean/CellsProofs/Chemistry/ShellIntervalHeat.lean) · [Two-molecule and whole-term controls](https://github.com/Eidosoma/Cells/blob/499980de46f30e883d968db7e3d7e6dc9e337434/lean/checks/chemistry/ShellIntervalHeat.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/499980de46f30e883d968db7e3d7e6dc9e337434/lean/checks/shell_interval_heat.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/499980de46f30e883d968db7e3d7e6dc9e337434/lean/PROGRESS.md#fr47-shell-interval-heat)

[Tested engine 43763a36f27d](https://github.com/Eidosoma/Cells/commit/43763a36f27d4dcf8381770649d6a59e4747ddf5) · [Evidence checkpoint 499980de46f3](https://github.com/Eidosoma/Cells/commit/499980de46f30e883d968db7e3d7e6dc9e337434)

## Biological evidence

**Open.** Exterior tracer recovered after a full wash, paired with retained lumen tracer and subsequent exterior sampling, at measured compartment volumes and independently calibrated exchange rates.

**Unit** molecules or calibrated concentration

### boyer-2007-dppc-release

Single-bilayer DPPC vesicles, carboxyfluorescein loaded at 20 mM, exterior dye removed by chromatography, pH 7.4, 37 °C. Figure 2 and the buffer-control release half-time on page 179. [Boyer and Zasadzinski (2007)](https://doi.org/10.1021/nn7002025)

- **Evidence role** descriptive

The half-time is a lower bound. A lysed-sample fluorescence reference gives total dye. Absolute retained counts and trapped aqueous volume are unavailable for this comparison.

The post-wash release half-time exceeded 20 h. The suspension fluorescence tracks dye release. An independent exterior recovery curve and return rate remain open. [Dataset manifest](../checks/data/shell_tracer_recovery.json) · [Comparison verdict](../PROGRESS.md#fr47-shell-wash-recovery)

### bachler-2021-finite-droplet-transfer

Two approximately 25 nL droplets across a symmetric DOPC bilayer, initially 50 µM rhodamine 6G on the donor side and dye-free buffer in the receiver, pH 6, incubation at 37 °C. Figure 2A–B follows fluorescence. Figure 5B–C reports the paired LC–MS measurements and permeability fits. [Bachler et al. (2021)](https://doi.org/10.1021/acs.analchem.0c04939)

- **Evidence role** descriptive

The fluorescence series normalized the two signals to their sum. LC–MS measured the two separated droplets at each sampling time (N = 4). The authors report possible cooling during later sampling.

The full-series apparent permeability was (6.28 ± 0.68) × 10⁻⁶ cm/s. These paired signals document finite-volume redistribution. Both permeability fits use the same experiment, and vesicle washout remains a separate measurement. [Dataset manifest](../checks/data/shell_tracer_recovery.json) · [Comparison verdict](../PROGRESS.md#fr47-shell-wash-recovery)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
