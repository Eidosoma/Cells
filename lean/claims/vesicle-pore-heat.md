<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Hold work and release close the pore’s heat balance

The work to open a critical pore is σπ(Γ/σ)². In units of k_BT the opening heat equals the log forward-to-reverse rate ratio. Scaling the declared reference viscosity by c moves ln c between opening heat and release heat, conserving their sum.

## Assumptions

- One externally held tension, a critical radius Γ/σ, positive surface viscosity and fixed rate-law parameters. The reverse collapse rate is evaluated at the critical pore. Phase A releases the vesicle immediately after opening.
- The release starts from the open state. It includes the signed work of any held reservoir in addition to the work paid by the tension hold.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.VesiclePore.hold_work](../CellsProofs/Chemistry/VesiclePore.lean#L100)
- [CellsProofs.Chemistry.VesiclePore.opening_heat_eq_log_ratio](../CellsProofs/Chemistry/VesiclePore.lean#L121)
- [CellsProofs.Chemistry.VesiclePore.event_heat](../CellsProofs/Chemistry/VesiclePore.lean#L141)
- [CellsProofs.Chemistry.VesiclePore.viscosity_heat_split](../CellsProofs/Chemistry/VesiclePore.lean#L146)

Direct proof subject `cells.assembly_hazard.pore_nucleation@1`, `cells.operator.tension_hold@1`

Proof sources [Mathlib logarithms of products and quotients, imported for the rate ratio](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/SpecialFunctions/Log/Basic.lean#L125-L132) · [Mathlib log_sqrt, imported for the collapse rate](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/SpecialFunctions/Log/Basic.lean#L284) · [Cells forward and reverse rate pair and hold work](https://github.com/Eidosoma/Cells/blob/f51a3b07d302fb177b166b1568155084ffb8e1c1/docs/VESICLE_PORES_LAWS.md#7-the-event-pair-d287-opening-is-a-pair-no-second-exemption)

## Numerical comparison

**Checked.** Tenfold reference viscosity shifted the opening and release entries by +2.30258509299405 and −2.30258509299405 k_BT. Final heat change was zero. Time and hold work were identical. The log rate-ratio and geometric work agreed in the single founder and both population founders.

**Engine** `cells.assembly_lineages@2`, `cells.pore_nucleation@1`

**Operators** `cells.tension_hold@1`

[Pore rate and temperature slope](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/src/cells/models/assembly_lineages_v2/pore_nucleation.py#L58) · [Tension domain and hold payer](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/src/cells/models/assembly_lineages_v2/tension_hold.py#L88) · [Clock, opening and release](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/src/cells/models/assembly_lineages_v2/pore_clock.py#L82) · [Single-lineage pore event](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/src/cells/models/assembly_lineages_v2/runner.py#L363) · [Population pore event](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/src/cells/models/assembly_lineages_v2/population.py#L665) · [Per-founder random stream and threshold inputs](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/src/cells/models/assembly_lineages_v2/streams.py) · [Geometry and area in both runners](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/src/cells/models/assembly_lineages_v2/geometry.py) · [Closed-form work oracle, founder worlds and both public run modes](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/tests/unit/test_assembly_lineages_v2_pores.py) · [Base assembly run definition](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/tests/assembly_lineage_v2_fixtures.py) · [Exact rate, heat and recorded cutoff proof](https://github.com/Eidosoma/Cells/blob/1c3c422d32a6723d650b2f6d2bc5b531d4a3ff87/lean/CellsProofs/Chemistry/VesiclePore.lean) · [Common-exposure survival bounds](https://github.com/Eidosoma/Cells/blob/1c3c422d32a6723d650b2f6d2bc5b531d4a3ff87/lean/CellsProofs/Chemistry/VesicleArea.lean) · [Measured pore observables](https://github.com/Eidosoma/Cells/blob/1c3c422d32a6723d650b2f6d2bc5b531d4a3ff87/lean/checks/data/dopc_pore_observables.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/1c3c422d32a6723d650b2f6d2bc5b531d4a3ff87/lean/checks/vesicle_pore.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/1c3c422d32a6723d650b2f6d2bc5b531d4a3ff87/lean/PROGRESS.md#fr31-pore-endpoint-repair)

[Tested engine 0a1c1b0dc814](https://github.com/Eidosoma/Cells/commit/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe) · [Evidence checkpoint 1c3c422d32a6](https://github.com/Eidosoma/Cells/commit/1c3c422d32a6723d650b2f6d2bc5b531d4a3ff87)

## Biological evidence

**Open.** Opening heat and subsequent release heat measured separately from the same held DOPC vesicle. A molecular-scale surface shear viscosity series across temperatures would also test the declared damping law.

**Unit** heat per event in k_BT

### chwastek2020_dopc_rotor

A fluorescent molecular rotor measured its immediate environment in DOPC membranes. Figure 4 and Table 1. [Chwastek et al. (2020), Figure 4 and Table 1](https://doi.org/10.1002/cbic.201900510)

- **Evidence role** descriptive

At 25 °C the local viscosity was 41 ± 10 mPa·s. The fitted activation energy was 54 ± 9 kJ/mol.

Local rotational microviscosity has a measured temperature dependence. Transferring it to in-plane pore friction requires an independent relation. [Dataset manifest](../checks/data/dopc_pore_observables.json) · [Comparison verdict](../PROGRESS.md#fr31-pore-rate-heat)

### chakraborty2020_dopc_fluctuations

Nanoscale thickness fluctuations were measured in 100 nm tail-deuterated DOPC vesicles, at zero added cholesterol. Figure 5B, Eq. 2 and SI Table S4. [Chakraborty et al. (2020), Figure 5B and SI Table S4](https://doi.org/10.1073/pnas.2004807117)

- **Evidence role** descriptive

The fluctuation fit gave 16.7 ± 1.1 nPa·s·m at 25 °C.

The estimate supplies one temperature for a different dissipation measurement. Its temperature slope and the separate pore heats remain open. [Dataset manifest](../checks/data/dopc_pore_observables.json) · [Comparison verdict](../PROGRESS.md#fr31-pore-rate-heat)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
