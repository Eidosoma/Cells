<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Competing binding sites retain capacity through an SSPRK step

Each population keeps its total of free and bound sites. Both site counts stay nonnegative, and an initially positive shared ligand pool stays positive through the three-stage update.

## Assumptions

- Free and bound counts start nonnegative and sum to capacity. Forward binding, release and internalisation have nonnegative rates.
- At each stage the step length times every outgoing loss coefficient is at most one half. Populations drawing on the same ligand pool contribute to one summed coefficient.
- The proof uses exact arithmetic and the SSPRK(3,3) weights. The comparison uses two populations at fixed volumes with one internalisation route.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.SiteOccupancy.site_guards](../CellsProofs/Chemistry/SiteOccupancy.lean#L18)
- [CellsProofs.Chemistry.SiteOccupancy.shared_pool_guard](../CellsProofs/Chemistry/SiteOccupancy.lean#L28)
- [CellsProofs.Chemistry.SiteOccupancy.ssprk_bounds](../CellsProofs/Chemistry/SiteOccupancy.lean#L41)
- [CellsProofs.Chemistry.SiteOccupancy.network_step](../CellsProofs/Chemistry/SiteOccupancy.lean#L54)
- [CellsProofs.Chemistry.SiteOccupancy.site_capacity_step](../CellsProofs/Chemistry/SiteOccupancy.lean#L67)

Direct proof subject `cells.operator.site_occupancy@1`

## Numerical comparison

**Checked.** In the finite-pool run both populations gained bound ligand. The largest ligand residual was 2.17 × 10⁻¹⁹ fmol and halving the step reduced the final ODE error by a factor of 8.26. Each route alone passed at load 0.300. Their combined loss load of 0.600 was refused.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.site_occupancy@1`

[Pool and site loss coefficients](https://github.com/Eidosoma/Cells/blob/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc/src/cells/operators/site_occupancy.py#L812) · [Three stages and weighted bookings](https://github.com/Eidosoma/Cells/blob/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc/src/cells/operators/site_occupancy.py#L845) · [Free, bound and internalised update](https://github.com/Eidosoma/Cells/blob/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc/src/cells/operators/site_occupancy.py#L964) · [Finite ligand-pool fixture](https://github.com/Eidosoma/Cells/blob/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc/validation/tissue/site_occupancy_fixtures.py#L92) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/b4353f85b18d489a277818bfe43e20c8416b6066/lean/checks/site_occupancy.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/b4353f85b18d489a277818bfe43e20c8416b6066/lean/PROGRESS.md#site-occupancy-stages)

[Tested engine b9d6452dff1c](https://github.com/Eidosoma/Cells/commit/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc) · [Evidence checkpoint b4353f85b18d](https://github.com/Eidosoma/Cells/commit/b4353f85b18d489a277818bfe43e20c8416b6066)

## Biological evidence

**Open.** Time-matched free ligand, occupancy of each of two competing site populations, and internalised cargo in a finite volume.

**Unit** fmol

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
