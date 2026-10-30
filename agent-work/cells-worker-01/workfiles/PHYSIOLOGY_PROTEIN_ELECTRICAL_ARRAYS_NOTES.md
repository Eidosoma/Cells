# Array electrical protein endpoint diagnostics

New worker numerics/reference/unit files only. All prior modules stay frozen;
Chief owns loop/schedule/state and work-ledger publication. Bounded CPU7 checks
are authorized; GPU and fuel interval compilation retries remain deferred.

`evaluate(before_endpoint, after_endpoint, requested_material_charge_change_C,
*, implementation, xp=jnp)` consumes frozen ArrayEndpoint provider records.
The direct requested increment is a separate padded physical-node vector:
subtracting their stored common-reference protein increments can lose it.
The caller admits the projection, common electrical reference, geometry and
protein material; Coulomb cancellation alone does not prove material balance.

Complete numeric state, current P, all original layout anchors and controls
must match across endpoints. Check both snapshots' source association,
original domains, actual charged-rate flags, matrix/edge charge closure,
Vm/phi relation, fixed clamp/gauge values, and component-current closure
recomputed from supplied potentials with original passive transport laws.
No new field solve, time step, random draw or state publication is performed.
Provider records are numerical source association, not authentication.

Actual material charge uses the charged RHS grouping `(anchor+protein)+ions`;
retain and check the saved grouping residual against `(anchor+ions)+protein`.
Keep actual represented charge difference, stored-reference increment
difference, direct requested change and every corresponding roundoff separate.
Never replace one with another or repair the original anchors.

At fixed original capacitance matrix K and fixed potentials on reservoirs:

    dphi = phi_after - phi_before
    Ucap change = .5e12 sum C dVm (Vm_after+Vm_before)
    dQelectrode = where(reservoir, (K dphi)_outside - dQmaterial_outside, 0)
    Wclamp = 1e12 sum boundary_V dQelectrode
    Ucap change - Wclamp - 1e12 midpoint(phi) dot dQmaterial = residual.

Keep per-patch energies, every reservoir charge/work, original matrix versus
edge assembly differences and reconstructed endpoint electrode differences.
Propagate the frozen host electrical identity's original charge budgets and
128-eps arithmetic bound, including baseline charge magnitudes. Keep gauge
coefficient `-sum(dQelectrode)` and all raw residuals. No field tolerance is
enlarged to match requested/material stock resolution.

This is only an electrical endpoint diagnostic. Protein chemical energy,
external drive, heat, stochastic/holding work, attainable minimum and complete
protocol acceptance belong elsewhere and are not inferred.

## Qualified scope

All29 checks pass:27 NumPy checks and two CPU JAX compiled/vmapped cases
(passive and calcium, two worlds each, actual NumPy provider records). The
28 endpoint forms compare all frozen host electrical fields and independent
full-node fields/charge/energy results. A fresh process denies Cells/JAX
imports and exactly replays all28 saved reference answers; its largest
numerical comparison consumes0.003944305 of the predeclared budget.

CPU7 phases took10.31/2.77/13.09/18.38s. Sampled peak RSS868089856B,
observed process high-water870584320B; host reserve stayed>=21644828672B.
All56 protected files and the three new source hashes remain exact. The
composite host-bound comparison accounts only for the measured change of
its edge/matrix assembly-energy term; field/current/arithmetic gates were
not enlarged. Compiled scope excludes an endpoint field solve.

Machine-readable receipt:
`/mnt/workspaces/Cells/physiology-protein-electrical-arrays-tests-20261030-01/result.json`
SHA256 `f3bb2aa2abf7cbc2dd2af9d68db198a0afe662fd4ac20c19397a631c50f20697`.
Inputs, private source, denied-import replay, per-case evidence, resource
records and command logs live beside it. The first launch review timed out
before starting; the permitted retry ran once without a numerical failure.
No further computation is active or queued. Chief owns shared verification
and integration; no mutable loop/calendar/schedule file was pinned or edited.
