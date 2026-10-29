# Full 56-law calcium/fuel/water and prescribed repair

Status: all 46 independent component checks passed on 2026-10-29. The
[component receipt](/mnt/workspaces/Cells/joint-water-hcn-development-20261029-04/result.json)
retains 44 finalized contract checks and the water trajectory without rerunning
them, then adds the remaining repair trajectory. Root owns shared routing,
schedule, public integration, assembly/cohort admission and PROGRESS. All @1
schema/runtime/reference files remain unchanged.

| Versioned model | New schema/runtime stem | Physical fields |
| --- | --- | --- |
| `resolved_calcium_energy_water@2` | `surface_calcium_energy_water_hcn_extra` | 43 |
| `resolved_calcium_energy_water_repair@2` | `surface_calcium_energy_water_repair_hcn_extra` | 48 |

Each schema is in `src/cells/core/<stem>_spec.py` and its runtime in
`src/cells/models/<stem>.py`. Model classes are
`SurfaceCalciumEnergyWaterHCNExtraModel` and
`SurfaceCalciumEnergyWaterRepairHCNExtraModel`. Configuration keys retain the
@1 structure; the nested ionic family is @12 and the complete finite-fuel
projection is @5. Each new Control/Experiment type requires the explicit shared
route before the inherited fuel fallback. Water exposes `energy_spec`,
`minimum_energy_spec`, `water_spec`, `Control`, `parse` and `to_dict`; repair
exposes `base_spec`, `accounting_spec`, `Control`, `parse` and `to_dict`.

The @2 field/layout projection always reconstructs the exact full HCN_EXTRA
finite-fuel type. This is necessary for HCNLeak, HCN2 cAMP and HCN4 cAMP, their
zero/one/two-slot contracts and the complete existing catalog. The new full
fixture has 63 populations covering 56 distinct laws. Water/repair introduce
no additional gate state or constitutive law.

Actual free chemical cytosol and actual ATP/ADP/Pi use the changing cytosol
volume at every stage; all three pump families read those current pools.
Chemical/fuel particles and free energy count once. ER volume, interface area
and capacitances retain the @1 fixed-geometry contract. Water increments,
chemical amounts, pumps, neutral fuel, osmotic/compliance energy, volume work,
charge and every original material/work/heat ledger remain explicit. Prescribed
repair adds only its existing Na/K lesion and damage/resealing ledgers; no
structural ATP cost or extra water owner is introduced.

[Static comparison](joint_water_hcn_static_boundary.json) verifies all 49
production runtime function ASTs match @1 after the exact full-catalog layout
substitution and repair Control import. This correspondence alone is not
scientific qualification. Separate numerical old/new overlap tests pass for
the 53-law subset, together with explicit @1 rejection of the new laws.

New independent references and fixtures are under `validation/tissue/` with
stems `calcium_energy_water_hcn_extra` and
`calcium_energy_water_repair_hcn_extra`. The old chemical-water binder forces
the 53-law calcium @10 parent; the new reference explicitly binds full calcium
@11 and uses a passive view solely for water geometry/parameters. Physical
fields/RHS always use the complete finite-fuel @5 owner. Its molecular/compliance
free-energy calculation obtains fields from actual current pools and volumes.
No reduced catalog supplies physical rates or current pump concentrations.

New component tests are `test_surface_calcium_energy_water_hcn_extra.py` and
`test_surface_calcium_energy_water_repair_hcn_extra.py`, with the private helper
`tests/owned_joint_water_hcn_helpers.py`. They cover all-law initial and
manufactured in-domain stages, actual moving-volume pools, fixed ER, absent/
blocked/sealed/subset controls, padding, exact reductions, repair ownership and
invalid states. Manufactured stages do not claim a generated ledger history.
Separate full trajectories compare every declared observation
and held-control boundary against segmented independent DOP853, with compact
full-state/reference NPZ retained at both steps. The 46 unique checks include
48 independent complete-field/RHS stage comparisons, 24 initial and 24
manufactured. Both integrated trajectories show resolved error reduction; no
endpoint-only or convergence-order claim is made.

Both trajectories cover 50 microseconds at RK4 steps 0.625 and 0.3125
microseconds. Independent segmented DOP853 uses rtol 1e-11 and maximum step
0.3125 microseconds. State acceptance retains rtol 3e-9, atol 2e-11 and
electrode-charge atol 3e-25 C. Every declared observation and held-control
boundary is included, with all 43 or 48 padded production arrays at both steps,
full independent/reference arrays, times and shape metadata retained.

| Trajectory | Samples | Coarse/fine state error over budget | Maximum independent energy residual |
| --- | ---: | --- | ---: |
| Water, 43 fields | 8 | 0.00687962 / 0.000428878 | 1.531e-12 pJ |
| Repair, 48 fields | 11 | 0.339130 / 0.0222444 | 2.460e-12 pJ |

The independent Decimal molecular/compliance/fuel free-energy residual is
checked at every sampled production state against the unchanged 1e-9 pJ
tolerance. Original material, charge, chemical ownership, adenylate,
phosphorus, pool, water and prescribed-damage ledgers also pass. Manufactured
stage checks remain separate from these integrated-history claims.

All numerical work used CPU7, single-threaded numerical libraries, JIT disabled,
a 1 GiB child-tree RSS cap, at least 8 GiB host reserve and a 480 s limit per
bounded process. The combined receipt verifies 748 component artifacts and
unchanged captured source/workspace hashes. Existing accepted suites and
Root's public checks were not rerun. No GPU, compiled coupled admission,
stochastic history, new repair energetics or physiological claim is qualified.
The calcium/fuel INIT-to-SIM continuation is separate and remains held.
