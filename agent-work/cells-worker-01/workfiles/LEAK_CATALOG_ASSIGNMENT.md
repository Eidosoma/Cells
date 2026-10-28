# Chloride and mixed-cation leak components

Start after the potassium catalog has its stable handoff. The user authorized
parallel feature development with adequate CPU checks and deferred GPU runs.
The coordinator owns shared tissue integration and the coupled response panel.

Own new `src/cells/processes/leak_channels.py`,
`tests/unit/test_leak_channels.py`,
`validation/channels/leak_channels_reference.py`,
`validation/channels/leak_channels_protocol.json`,
`docs/LEAK_CHANNEL_CATALOG.md`, and your worker-local log/workfiles only.
Do not alter delivered catalogs, models, schema, registry or PROGRESS.

Inspect actual pinned BETSE v1.5.0 commit
`5269a714aa2593ed2a6708c4516289977d8ae1a2`, `vg_cl.py`, `cation.py` and inherited
channel updates. Cover ClLeak, CatLeak and CatLeak2, including native targeting,
ion ordering, relative permeabilities, initialization and auxiliary gate clocks.
Implement independently rather than copying upstream source. Retain external
actual-source captures with source hashes and exact inputs/outputs.

The coordinator reserves codes 32--34, respectively, for these proposed laws:
`betse_clleak_always_open@1`, `betse_catleak_na_k@1`, and
`betse_catleak2_na_k_ca@1`. Standalone padding is -1; shared code zero keeps its
existing meaning. Use the sodium/potassium two-gate/population/leading-world
API. If inspection agrees, proceed without another approval for these IDs.
Report any discrepancy first. The inspected chloride permeability is Cl=1;
CatLeak has ordered Na/K/Ca weights 1/1/0, and CatLeak2 has 1/1/1. Preserve the
zero Ca metadata rather than suggesting CatLeak transports calcium. Each
population has one availability multiplier shared by its declared ion routes.
Flux and reversal potentials remain owned by the tissue electrochemistry.

The inspected laws have opening powers 0/0 and gate targets/time constants
1/1 second. Preserve auxiliary gates and strict domains even though opening is
one. A source leak is not voltage-dependent gating. Computational voltage
domain may reuse [-0.120, 0.060] V without claiming biological calibration.
Check exact constant opening, real leading-world broadcast, padding, ordering,
native target scatter/clock and long enough auxiliary-gate recovery. Do not
manufacture a kinetic parameter fit. Source and independent reference checks
remain separate from tissue trajectories and later GPU qualification.

Use bounded CPU7 host checks first, one BLAS thread, at most 1 GiB charged
memory and individual RSS, at least 8 GiB host reserve. Outputs under
`/mnt/workspaces/Cells`. Jobs expected under ten minutes may use a watcher;
longer jobs must detach with durable result/failure artifacts and no automatic
polling. Ask the coordinator before a small compiled CPU pass. No GPU,
unrelated sweep or automatic follow-up audits. Hand off stable files and scoped
evidence when finished.
