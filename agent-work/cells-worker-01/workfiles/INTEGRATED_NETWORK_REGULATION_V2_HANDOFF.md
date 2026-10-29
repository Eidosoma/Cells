# Live chemical/fuel availability for channels and junctions

The new sibling model `resolved_calcium_energy_regulated@2` extends the existing
Na/K integration to existing shared-channel populations and resolved junctions.
All 38 parent physical state fields, catalog laws, intrinsic gates, permeability,
material/charge/energy ledgers and signed pump/fuel transfers remain parent-owned.
Dimensionless factors have no added ATP cost or physical inventory.

The separate protocol is justified by the new field/availability feedback and
ambiguous native junction sampling: it records the chosen owner mapping, strict
factor domain and unsupported controls rather than claiming native solver parity.
`validation/regulation/integrated_network_regulation_v2_protocol.json` owns the
scope and tolerances; the result receipt owns test/resource status.

Each rule names `kind` (`nak`, `channel`, or `junction`), an existing `target_id`,
`sample_cell_id`, `sample_exterior_id` and `fuel_pool_id`, plus frozen native
factor configuration. A membrane consumer must sample its actual inside/outside
and a pool belonging to that cytosol. Na/K must use its existing pump pool.
Junctions explicitly name either endpoint and that endpoint's fuel pool, with
`sample_exterior_id: null`; no edge/exterior mapping is inferred. Ordered writes
replace factors on overlapping targets, including opposite endpoint rules.
Every active raw factor must be finite in [0,1], even when shadowed or off.
The final factor multiplies the held scheduled availability exactly once.

The source Na/K/GJ `max effect * alpha` and channel `alpha` equations are reused,
including direct/independent terms and actual inhibitor-floor precedence. The
new composition uses current free cytosol/store chemistry, exterior and finite
ATP/ADP/Pi amount/volume at each common stage. It does not reproduce native SIM
lag or native `core.modulator` plus outer DChan action. Native channel class/type
labels are factor-generation metadata, not construction or isoform equivalence.
Physical channels remain the target's already declared parent population/law.

Channel rules require zero native `max Dm`, no native conductivity, `apply to:
all`, and active INIT defaults: capacities/profile and phase dispatch are not
part of this factor-only SIM integration. Inhibitor floors must be in [0,1].
Nonzero charged voltage-Hill coefficients are rejected because they would need
a coupled field/regulation closure; neutral or source-ignored stars retain source
semantics. Junction environment-zone terms and all exterior fuel terms are
rejected. Dedicated calcium-channel targets are outside this @2 consumer scope.

The new independent reference resolves owners and controls from raw IDs, applies
80-digit Decimal frozen source factors, then delegates complete field/chemistry/
fuel/ledger equations to the independent parent reference. A clean standalone
oracle proves Cells/JAX/pytest imports are absent before and after integration.
The host family covers full 63-population stages and a full 63-population
5-us coupled transient with off-grid schedule changes, three refinements,
physical domain/conservation checks and an exact in-memory split. No new compiled
or public execution qualification is claimed.

All @1 sources and evidence stay frozen. The active @1 public job has not been
polled. Shared dispatch and PROGRESS are Chief-owned. The separate four-file
`integrated_network_regulation_v2_dispatch.patch` is prepared and unapplied;
its JSON records exact shared before/after hashes. It selects @2 before its HCN
parent and delegates scheduling to the new parent-projection helper. Chief may
need to rebase context after concurrent changes and owns public integration.
No automatic follow-up, regression or qualification jobs are scheduled.
