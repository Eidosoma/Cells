# Ideal fixed-inventory capacitive voltage transitions

This contract precedes implementation. Its concrete risk is silently replacing
fixed-voltage history anchors, or confusing held ionic power with the displacement
charge/work required when actual electrode potentials change.

## Named physical intervention

Law: `ideal_fixed_inventory_linear_capacitive_ramp@1`.
The ramp coordinate is a dimensionless path parameter, lambda in [0,1], not elapsed
biological time. Every ionic/chemical inventory, gate, geometric parameter,
temperature, ordinary numeric clock, schedule position and held control stays fixed.
Only explicitly bound actual reservoir potentials vary as
`b(lambda) = b_start + lambda * delta_b`. Unmapped reservoirs keep their declaration;
shared side/corner owners must receive consistent potentials. A numerical gauge
never becomes an electrode. No native BETSE transition correspondence is claimed.

This is an ideal reversible capacitive operation. Ionic currents reported by the
held adapter are diagnostic and are not integrated along this zero-duration
operator. It is not a claim that a finite-duration physical ramp suppresses
conduction or chemical dynamics. A later coupled ramp needs a distinct derived
law and qualification. No heat or thermal dynamics is invented here.

## Charge and work identity

For the fixed capacitor graph, solve its *incremental* linear constraints at
zero free-node charge increment and the declared reservoir `delta_b`.
Floating capacitor components may change common offsets in the physical field,
but patch voltage increments are independent of that numerical representative.
The actual held fields at both endpoints must admit the same inventory/gate state
and agree with these patch increments. No difference of two large absolute
capacitor charges is used as the displacement-current ledger.

For patch k, `delta_q_k = C_k * delta_vm_k`. Equal and opposite node charge
increments are accumulated once per patch. Non-electrode owners must retain zero
charge increment. Electrode e records `delta_Q_e` from its actual patch incidences.
Each electrode supplies
`delta_W_e = 1e12 * (b_start_e + delta_b_e/2) * delta_Q_e` pJ.
The stable capacitor change is
`delta_U = 0.5e12 * sum(C_k * delta_vm_k * (2*vm_start_k + delta_vm_k))`.
Require `delta_U = sum(delta_W_e)` within the registered work budget.

Keep the ordinary accepted checkpoint, original anchors and its original
material/charge/energy ledgers intact. Store displacement charge and external
work as separate, explicit per-electrode ledgers. Keep every accepted segment;
cumulative charge, per-owner work and capacitor changes use compensated `fsum`
of the segment contributions, not a net-endpoint replacement. Validate both the
full original ordinary history and the additional transition identities. Reverse
ramps should undo their own work; rectangular cycles can transfer work between
electrodes while total capacitor energy returns to its origin.

## Admission, records and restart

An immutable association owns the complete original numeric checkpoint, binding,
controls sampled at that original clock, initial/current side memories, explicit
ramp declarations, accepted segments and cumulative ledgers. A finite declared
segment capacity refuses before loss of evidence. No physical clock advances.
Failures retain the complete parent, declaration, stage and any raw preparation,
field or algebra proposal; no partial acceptance or automatic retry occurs.

Accepted physical IDs are `resolved_tissue@1`, `resolved_tissue@12`,
`resolved_open_calcium@1` and `resolved_open_calcium_energy@1`. Finite-only
`resolved_calcium@11`/`resolved_calcium_energy@5` keep their no-electrode/gauge
refusal. Their empty transition identity may be checked separately.

Durable archives retain a complete ordinary snapshot plus the complete transition
association, controls, side buffers, declarations and segment/cumulative arrays.
Bind source hashes, runtime identity, exact layouts and payload hashes; publish a
complete manifest last with fsync. Refuse changed sources, incomplete/corrupt
archives, malformed/resealed associations and existing destinations. Restart
must reproduce the next transition and all cumulative histories exactly.

## CPU qualification

Reuse the qualified held adapter, its native setter evidence, independent raw
owner/full-node oracles, and bounded runners. Independently assemble capacitor
constraints from raw named patches and solve incremental response with high
precision; independently reconstruct all work and cumulative owner histories.
Cover all four reservoir-capable IDs, initial/evolved original states, forward,
reverse and rectangular cycles, tiny increments with accumulated histories,
padding/order, corners, bad declarations, malformed parents, refusal diagnostics
and complete restart. A fresh process denies Cells/JAX imports for saved replay.

Registered budgets retain the held comparison scales: voltage `3e-13 V` absolute
plus `3e-10` relative, charge `3e-25 C` plus `2e-12` relative, and capacitor/work
`3e-14 pJ` plus `3e-10` relative. Keep all original ordinary domain, conservation,
5% turnover and held stage-energy (`1e-10 pJ/s`) checks unchanged. Algebra, source
setter correspondence, coupled ionic trajectories and biological validation are
separate claims.

CPU5, one BLAS/XLA thread, process-tree RSS <=1 GiB, host reserve >=8 GiB, 480 s
per phase. Capture sources/inputs and durable results/failures under
`/mnt/workspaces/Cells`. At >=10 minutes expected runtime, detach and return
without automatic polling. No follow-up audit/regression or GPU job is queued.
