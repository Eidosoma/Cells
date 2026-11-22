<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Rupture by the hold endpoint requires enough accumulated exposure

For a constant positive rate k and threshold E, the rupture time is at or before the cutoff exactly when E ≤ k(cutoff − start). The recorded founder’s threshold strictly exceeds the available exposure at the middle of three adjacent binary64 cutoffs.

## Assumptions

- One fixed-area, constant-tension hold. The cutoff is the earlier of hold end and observation horizon. The founder is alive at hold start and E = −ln u for a draw strictly between zero and one.
- The reference comparison treats the engine’s stored rate, threshold and times as their exact binary values. A crossing exactly at the cutoff belongs to the hold.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.VesiclePore.clock_by_cut](../CellsProofs/Chemistry/VesiclePore.lean#L87)
- [CellsProofs.Chemistry.VesiclePore.recorded_cut_precedes_rupture](../CellsProofs/Chemistry/VesiclePore.lean#L93)

Direct proof subject `cells.pore_nucleation@1`, `cells.tension_hold@1`

Proof sources [Mathlib div_le_iff₀, specialized to the positive hazard](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/Order/GroupWithZero/Unbundled/Basic.lean#L1072) · [Cells inclusive threshold crossing](https://github.com/Eidosoma/Cells/blob/f51a3b07d302fb177b166b1568155084ffb8e1c1/src/cells/models/assembly_lineages_v2/pore_clock.py#L5)

Uses [Vesicle pore rates scale with area and increase on warming](vesicle-pore-rate.md)

## Numerical comparison

**Failed.** Both runners recorded rupture at 1.4042194113471334 s. The crossing falls 2.42288 × 10⁻¹⁷ s later for the same binary inputs. Both neighboring cutoffs and the exactly sufficient exposure control agree. Both ledgers close. The replay exits nonzero on the middle cut.

**Engine** `cells.assembly_lineages@2`, `cells.pore_nucleation@1`

**Operators** `cells.tension_hold@1`

[Pore rate and temperature slope](https://github.com/Eidosoma/Cells/blob/f51a3b07d302fb177b166b1568155084ffb8e1c1/src/cells/models/assembly_lineages_v2/pore_nucleation.py#L58) · [Tension domain and hold payer](https://github.com/Eidosoma/Cells/blob/f51a3b07d302fb177b166b1568155084ffb8e1c1/src/cells/models/assembly_lineages_v2/tension_hold.py#L88) · [Clock, opening and release](https://github.com/Eidosoma/Cells/blob/f51a3b07d302fb177b166b1568155084ffb8e1c1/src/cells/models/assembly_lineages_v2/pore_clock.py#L69) · [Single-lineage pore event](https://github.com/Eidosoma/Cells/blob/f51a3b07d302fb177b166b1568155084ffb8e1c1/src/cells/models/assembly_lineages_v2/runner.py#L363) · [Population pore event](https://github.com/Eidosoma/Cells/blob/f51a3b07d302fb177b166b1568155084ffb8e1c1/src/cells/models/assembly_lineages_v2/population.py#L670) · [Per-founder random stream and threshold inputs](https://github.com/Eidosoma/Cells/blob/f51a3b07d302fb177b166b1568155084ffb8e1c1/src/cells/models/assembly_lineages_v2/streams.py) · [Geometry and area in both runners](https://github.com/Eidosoma/Cells/blob/f51a3b07d302fb177b166b1568155084ffb8e1c1/src/cells/models/assembly_lineages_v2/geometry.py) · [Closed-form work oracle, founder worlds and both public run modes](https://github.com/Eidosoma/Cells/blob/f51a3b07d302fb177b166b1568155084ffb8e1c1/tests/unit/test_assembly_lineages_v2_pores.py) · [Base assembly run definition](https://github.com/Eidosoma/Cells/blob/f51a3b07d302fb177b166b1568155084ffb8e1c1/tests/assembly_lineage_v2_fixtures.py) · [Exact rate, heat and recorded cutoff proof](https://github.com/Eidosoma/Cells/blob/870c9353c92b7e614f25a768f2dabecf7b81d49c/lean/CellsProofs/Chemistry/VesiclePore.lean) · [Common-exposure survival bounds](https://github.com/Eidosoma/Cells/blob/870c9353c92b7e614f25a768f2dabecf7b81d49c/lean/CellsProofs/Chemistry/VesicleArea.lean) · [Measured pore observables](https://github.com/Eidosoma/Cells/blob/870c9353c92b7e614f25a768f2dabecf7b81d49c/lean/checks/data/dopc_pore_observables.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/870c9353c92b7e614f25a768f2dabecf7b81d49c/lean/checks/vesicle_pore.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/870c9353c92b7e614f25a768f2dabecf7b81d49c/lean/PROGRESS.md#fr31-pore-rate-heat)

[Tested engine f51a3b07d302](https://github.com/Eidosoma/Cells/commit/f51a3b07d302fb177b166b1568155084ffb8e1c1) · [Evidence checkpoint 870c9353c92b](https://github.com/Eidosoma/Cells/commit/870c9353c92b7e614f25a768f2dabecf7b81d49c)

## Biological evidence

**Open.** First opening and eventual rupture observed separately during the same constant-tension hold. A time-resolved opening or resealing measurement would test the model’s choice of biological endpoint.

**Unit** time to first opening or rupture in seconds

### portet2010_dopc_pore_closure

The authors imaged closure after electrical poration of free vesicles. Table 1 and the pure-DOPC closure analysis. [Portet and Dimova (2010), Table 1](https://doi.org/10.1016/j.bpj.2010.09.032)

- **Evidence role** descriptive

Edge tension inferred from closure was 27.7 ± 2.5 pN (SE, 24 experiments).

Pores can reseal in free DOPC vesicles after a pulse. The probability of reclosure under sustained aspiration remains open. [Dataset manifest](../checks/data/dopc_pore_observables.json) · [Comparison verdict](../PROGRESS.md#fr31-pore-rate-heat)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
