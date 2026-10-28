# Fixed-volume tissue cotransport

`resolved_cotransport@1` extends `resolved_energy@1` with the manufactured
reversible KCC/NKCC component. Fixed geometry, finite ATP pools, regeneration,
channels and existing ionic laws retain their meaning. Cotransport adds no ATP
reaction and no direct capacitive current. This extension makes no native
BETSE named-transporter parity or fitted-isoform claim; see the component
[physical/source contract](COTRANSPORT.md).

## Public interface

`model.cotransporters` is an explicit ordered list, including empty:

```json
{"id":"kcc_0","membrane_id":"membrane_0","law":"kcc_reversible_tanh@1",
 "roles":{"potassium":"K","chloride":"Cl"},"capacity_fmol_per_s":2.0}
```

An NKCC row uses `nkcc_reversible_tanh@1` and additionally binds `roles.sodium`.
All roles must name distinct actual species with the correct +1/+1/-1
valences. Species IDs may be renamed and reordered. The owning membrane
supplies the inside cell and finite outside compartment; there are no duplicate
owner, temperature, geometry or ATP fields on the route.

Existing named channel laws retain their canonical ion-ID restrictions. The
renamed-species fixture exercises finite pumps and cotransport with channels
absent; it preserves those older channel source contracts. The layout stores
the schema's integer cotransport valences explicitly and checks agreement
with the older ionic layout's floating-point valences.

`experiment.cotransport_controls` has exactly one schedule per route:

```json
{"cotransport_id":"kcc_0","schedule":[{"time":0.0,"availability":1.0}]}
```

`execution.cotransport_capacity` declares the padded route axis.
`SurfaceCotransportModel` extends `surface_energy_spec.SurfaceEnergyModel`.
New frozen dataclasses are `CotransportRoles`, `Cotransporter`, `Execution`,
`Experiment` and `Change`; `Experiment.cotransports` stores ordered schedules,
and `Change.cotransport` stores availability tuples. `Control` fields are, in
order, `membrane`, `junction`, `channel`, `pump`, `regeneration`, `cotransport`.
The accepted EventGrid unions all six independent, right-continuous clocks.

`energy_spec(spec)` returns exact finite-energy model/experiment/execution
types, removing only cotransport declarations. `initial_ionic_spec(spec)`
delegates through that projection. `parse` and `to_dict` preserve all new
declarations and call the new model's deferred definition check.

All 23 finite-energy state fields remain, with three additions:

| Field | Axes |
| --- | --- |
| `cotransport_cycles_fmol` | cotransport_slot |
| `cotransport_transferred_fmol` | species, cotransport_slot |
| `cotransport_dissipated_energy_pJ` | cotransport_slot |

The complete state has 26 fields. Batch capacities add
`cotransport_capacity`. Positive cycles move all bound species inward. Signed
transfer is `nu*cycles`; the finite outside loses exactly the material gained
by the cell. Multiple routes can share a patch or pool and are accumulated
once. Availability zero does not remove active substrate-domain requirements.

## Physical accounting

At each stage the delivered component evaluates
`A=RT*sum(nu*log(c_out/c_in))`, `J=C*a*tanh(A/(2RT))` and heat `1e-3*J*A`.
The implementation uses log differences. Matching material changes are added
to the existing ionic derivative; direct charge, capacitive rate and ATP
reaction derivatives retain their existing values at that same state. The
next stage evaluates every shared ionic law from the altered concentrations.

The combined chemical-energy derivative includes the new material rates, and
the heat appears exactly once. Local material reconstruction includes the
new signed transfer with the correct inward sign relative to the older
outward-positive membrane ledger. Independent route-cycle/transfer residuals
detect compensating corruption that global conservation alone would miss.
Existing ionic, field, finite-pool and energy tolerances remain unchanged.

The initial timestep check retains the inherited five-clock energy/ionic
ceilings and the full six-clock accepted grid. It additionally bounds gross
initial cotransport of any ionic owner to 5% per nominal step, counting opposing
routes without cancellation. Every actual integration stage still requires
strict positive substrates and valid current controls; this initial guard is
not a depletion-boundary continuation law.

## Initial verification

The new schema/stage selectors are `tests/unit/test_surface_cotransport_spec.py`
and `tests/unit/test_surface_cotransport.py`. Host checks select `-k 'not jax'`;
the two small compiled prototypes select `-k jax` only after the Chief's
resource handoff. The scalar tissue reference imports the delivered independent
finite-energy and Decimal cotransport references, reconstructs raw roles and
owners itself, and supplies a six-clock segmented DOP853 implementation for
later coordinator-owned trajectories. It imports no production model, schema
or JAX helpers.

Full 26-field derivative comparisons cover eight manufactured arms with
compact/padded layouts, additional actual clock transitions and a changed live
ionic state. Existing stage budgets remain `3e-12 + 3e-10*abs(reference)` for
material/energy/gates and `3e-23 + 3e-10*abs(reference)` for charge derivatives;
the independent/production stage energy residual bound is `2e-8 pJ/s`.
Potential comparisons retain `3e-13 V + 3e-10*abs(reference)`.

The closed finite-extent test uses an independently evaluated ionic free-energy
change to construct positive heat, then checks local inventories and the full
combined energy identity. Its stored nonzero transfer history also exercises
the complete observer and total membrane flux. Compensating route corruption
keeps patch/global totals unchanged while failing individual route evidence.
These are manufactured state/stage contracts; they do not constitute a
numerical trajectory, step-refinement, biological or GPU qualification claim.

The worker owns only the new spec/model/configuration, fixtures/reference,
schema/stage tests and this guide. The Chief owns shared hooks, execution,
replay, trajectory/refinement and full CPU/L4 qualification. All generated
evidence belongs outside the checkout, linked from the worker's
[work log](../agent-work/cells-worker-01/WORK_LOG.md).
