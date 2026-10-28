# Remaining pinned potassium-channel catalog

The user authorized the next feature work with scientifically adequate CPU
validation. The sodium catalog is delivered; keep those files stable. The
coordinator owns its shared tissue integration and salt/water/energy trajectories.

Own only these new files and your existing worker log/workfiles:

- `src/cells/processes/potassium_catalog.py`
- `tests/unit/test_potassium_catalog.py`
- `validation/channels/potassium_catalog_reference.py`
- `validation/channels/potassium_catalog_protocol.json`
- `docs/POTASSIUM_CHANNEL_CATALOG.md`

Inspect pinned BETSE v1.5.0 commit
`5269a714aa2593ed2a6708c4516289977d8ae1a2`, `science/channels/vg_k.py`,
and inherited channel updates. Cover the remaining concrete classes outside
the delivered Kv1 catalog: Kv2p1, Kv2p2, Kv3p1, Kv3p2, Kv3p3, Kv3p4, K_Fast,
KLeak and Kir2p1. Reuse the accepted Kir2.1 implementation exactly for its
existing law; do not change existing potassium/Kv1 sources. Identify any
source discrepancy before defining new laws. No source implementation is
copied into Cells; native captures remain external evidence.

Send the proposed stable API, law IDs and code allocation early. Codes 0--23
already have shared or reserved meanings. New distinct laws may reserve codes
24 onward after coordination; padding must not redefine shared code zero.
Prefer the delivered sodium catalog's two-gate/population/leading-world API,
with volts, seconds, explicit gate powers and a stated computational domain.
Preserve degenerate/auxiliary gates and distinguish native initialization,
backward-Euler clocks and continuous-time kinetics. No inferred temperature
scaling or biological fit. Regularize removable singularities analytically;
reject invalid domains without silently clipping.

Use independent scalar/Decimal equations and separately executed actual pinned
source probes, preserving source hashes, exact inputs, outputs and source
failures. Check ordinary and near-singular voltages, initialization, gate
powers, real leading-world broadcasts, reordering, padding and domain failures.
Clamp/recovery horizons must cover the relevant slow time constants, with
analytic or independently integrated references and appropriate refinement.
Wall-time targets never justify shortening the scientific horizon.

Start with bounded CPU7 host checks, one BLAS thread, at most 1 GiB charged
memory and individual RSS, at least 8 GiB host reserve, outputs under
`/mnt/workspaces/Cells`. Expected under-ten-minute jobs may have a watcher;
longer jobs must be detached with durable result/failure artifacts and no
automatic polling. Ask the coordinator before a small compiled CPU pass.
No GPU qualifications, broad sweep or automatic follow-up audit.

Do not edit shared channel catalogs, models, schema, PROGRESS or delivered
sodium/cotransport/energy/water files. Hand off implementation, scoped evidence
and hashes; tissue composition and later batched GPU work remain separate.
