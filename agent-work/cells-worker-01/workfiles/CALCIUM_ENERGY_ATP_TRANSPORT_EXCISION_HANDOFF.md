# Finite-ATP configured-transport excision handoff

Six Chief-assigned files, frozen 2026-10-30. Current exact hashes, failed and
accepted evidence, resources and metrics are in
[the workqueue](calcium_energy_atp_transport_excision_workqueue.json).
Chief owns shared public parse/registry/schedule/ensemble/excision/archive hooks,
public tests and PROGRESS. This worker changed only the six new files and its
own workfiles/log. Ordinary ATP, physiological binding and previous cut sources
remain unchanged.

## API and state

Identity `resolved_calcium_energy_atp_transport_excision@1`, model class
`SurfaceCalciumEnergyATPTransportExcisionModel`. The schema and model have the
prefix `surface_calcium_energy_atp_transport_excision`; the core adapter is
`cells.core.calcium_energy_atp_transport_tissue_excision`.

The new model adds immutable canonical `excision_json` and `epoch_start_time` to
the exact ordinary ATP model. `base_spec` projects that declaration. Its state
and layout types are the unchanged parent ATP types: all 46 fields and all 8
route ledgers retain their static-law dispatch. `initial_time(spec)` is the
absolute cut time. The nominal grid remains anchored at zero.

Core API is `excise(spec, checkpoint, removed_cell_ids) -> ExcisionResult`,
plus `capture_source`, `decode_source`, `physical`, `derive_tissue`, `experiment`,
`histories` and `transition_report`. `_parse`, `_serialize` and `_implementation`
are direct family helpers used while Chief's shared hooks are being added;
they do not depend on shared registration of the new epoch identity.

The source record seals the complete 46-field raw state/layout/definition and
original time/step/event indices. Exact source, retained and removed owner IDs
are explicit. No-op keeps the accepted checkpoint; terminal removal archives
without constructing a zero-cell solver. Sequential cuts retain full nested
lineage with the existing 16-cut limit.

Every one of the 8 route fields is partitioned by actual membrane owner:
cycles, ionic transfer, heat, released internal fuel work, ionic chemical work,
electric work, gross hydrolysis and gross synthesis. All old histories stay in
the full source archive and named retained/removed partitions. New segment
ledgers start at zero; actual retained gates and finite inventories become the
new anchors. Report fields `network_route_ledger_fields` and
`network_transporter_pool_ids` make the route/fuel ownership explicit.

Actual retained/removed ATP/ADP/Pi, adenylate/phosphorus, chemical stores and
physical charges are preserved. The ordinary finite-ATP schema/physics is
unchanged: route fuel work stays internal and `network_work_external=False`,
`network_fuel_work_internal=True`. Route histories are not another material
inventory. There is no ATP-triggered charge neutralization or wound release.

The qualified finite-fuel cut policy is reused: authoritative chemical stores,
free-cytosol ionic reference with conserved whole-cell charge, explicit physical
fixed-background roundoff bound, unchanged exterior owners/amounts, unchanged
1-M fuel standards, original PMCA/ER anchor range [1e-9,1e3] mM and all absolute
control histories. Removed-owner event clocks remain on a surviving carrier.
No gate or mechanical cutting-energy law is invented.

## Qualification and the temporal limit

22 direct owner-removal/RHS/archive/refusal checks passed in the original run.
They cover six arms, initial/evolved sources, exact 46-field rates, 8-ledger
partitions including both gross directions, no-op/terminal/sequential cuts,
charged closed-field refusal and corrupt source/owner/history declarations.
There are 13 full postcut rate comparisons; maximum error/budget is
`0.012985495353651299`.

The initial additional trajectory check FAILED its fixed accuracy budget at
nominal source dt=1.25 us and dt/2: error/budget was
`352.7379358082391` and `21.2717500032766`.
The worst field was exterior amount (~1.0591e-9 fmol coarse error against a
~3.0026e-12 fmol budget). Both source/segment conservation and endpoint energy
checks passed; this is a temporal-accuracy limit, not evidence for a coarse
full-state accuracy claim. The full raw failure, arrays, budgets and logs are
retained under the first run directory. No tolerance was widened.

To qualify the same physical interval, the temporal unit declares the finer
original source dt=0.15625 us BEFORE evolving the source or cutting. It evolves
the source to the same 1.25 us cut time, then follows the same 2.5 us postcut
interval and route event at 2.1875 us. The cut retains that declared source dt,
all absolute controls, anchors and clock origin. It never rewrites dt after
removal. At that finer source dt, full-state error/budget is
`0.08893114159930408`; half-step error/budget is
`0.00537537110030125`; tightened-oracle uncertainty/budget is
`2.37295533682127e-06`.

This refined check passed from a private captured source tree, as Chief was
editing shared hooks. All five scientific files were byte-identical to the
original run. AST correspondence proves every non-temporal unit module node
unchanged, reusing the 22 passed checks without rerunning them. Thus the final
qualification combines those 22 checks with 1 passing refined temporal check;
it does not relabel the nominal-step trajectory failure as a pass.

Fixed state/rate budget is 3e-12 absolute +3e-10 relative, charge 3e-23 C;
potential 3e-12 V; rate-energy and endpoint energy 1e-10 pJ/s and pJ;
cut-energy comparison 2e-10 pJ +3e-9 relative. Existing parent material,
charge/energy, internal pool and domain checks remain active. Quantity
partition bounds stay 8*epsilon*sum(abs(source quantities)); chemical fixed
background uses the original charge tolerance +16*epsilon*absolute charge scale.

Fresh actual independent source integration, cut, postcut RHS and continuation
also passed with both import mechanisms denying Cells/JAX. Its endpoint energy
residual was `7.22433723086835e-15 pJ`.
That proof uses the independent 46-field ATP reference and independently
reconstructed physical/fuel cut equations, not production source mappings.
It adds no extra counted scientific case.

## Receipts and resources

Original run (22 direct checks pass, 1 coarse temporal failure preserved):
`/mnt/workspaces/Cells/calcium-energy-atp-transport-excision-development-20261030-01/`.
Its isolated reference completed in 5.79 s; direct pytest completed in 224.36 s.

Accepted focused refined receipt:
`/mnt/workspaces/Cells/calcium-energy-atp-transport-excision-refinement-20261030-02/result.json`
SHA256 `80776def0519a5725c66215c9bb85c78eddb1b59569d4e060b963870631f7d63`.
AST/source correspondence is `source-correspondence.json` beside that receipt.
The focused check took 45.23 s with peak RSS 240730112 B. Each run used CPU7,
one thread, <=480 s/command, <=1 GiB process-tree RSS and >=8 GiB host reserve.
No long detached job, GPU computation or campaign poll was launched.

The fixtures explicitly enable neutral KCl hydrolysis plus a manufactured
32:32 KCl import route that runs backward to synthesize ATP. Both retained and
removed fuel-direction histories are nonzero without changing plasma charge.
These are synthetic short cut probes, not fitted stoichiometry, native whole-
tissue equivalence, slow relaxation, temporal order, wound or GPU claims.

## Frozen worker sources

| Source | SHA256 |
| --- | --- |
| `src/cells/core/surface_calcium_energy_atp_transport_excision_spec.py` | `b408768c3eccbf1847dbfabf38b18aee4cc829b72ac7c85ac51faecb0ca3ffd1` |
| `src/cells/models/surface_calcium_energy_atp_transport_excision.py` | `cfc49f68e9d52aa511ccbc56bf1ddd70b3db2359aa687b66423425d884112410` |
| `src/cells/core/calcium_energy_atp_transport_tissue_excision.py` | `24e25248fc30b00030d91182ab28721525531b42ac719dfa26e17fa3d3ec511e` |
| `validation/tissue/calcium_energy_atp_transport_excision_reference.py` | `68c19f6f49196a98d9b4f7837530581537e4a0eeacad2a569450a12ecb974e3e` |
| `validation/tissue/calcium_energy_atp_transport_excision_fixtures.py` | `fe0c400e88c2e8823d2499695de079ed846844fd72b2cdb364d7d21ef6cb2542` |
| `tests/unit/test_surface_calcium_energy_atp_transport_excision.py` | `b55bedcc0b06398cfa026bbff7795776b7dba25923008be6a686222884caed38` |
