# Gate comparisons with voltage-error propagation

The mixed-control protocol v3 changes **native m/h acceptance**, while retaining
the original scalar tolerances and production code. The failed v2 run remains
failed. This note explains the change because a wider gate comparison without
an independent kinetic check could conceal a real defect.

The regional v2 case first differs in bulk K by one float64 increment at 61 us.
An 80-digit calculation shows that the voltage difference moves the channel
transfer across a rounding midpoint; both updates round correctly for their
fluxes. On identical concentrations the compensated Cells charge sum is closer
to the high-precision answer than the native scaled dot product. The diagnosis
and immutable evidence are linked from [PROGRESS.md](../../../PROGRESS.md).
That observation motivates this check; it does not supply a fitted allowance.

## Conditional bound

For either gate, write the implicit update as

`f(g,V) = (tau(V) g + dt s(V)) / (tau(V) + dt)`.

The target `s` is logistic with voltage width `k`; `tau = A - B V` is positive
throughout the registered domain `[-0.120, 0.060] V`. In seconds and volts:

| Gate | A | B | k |
| --- | ---: | ---: | ---: |
| m | 0.008330 | 0.1163 | 0.0064 |
| h | 1.620000 | 15.500 | 0.0035 |

For `g` in `[0,1]`, `|s'| <= 1/(4k)` and `|g-s| <= 1`. Differentiating gives

`df/dg = tau/(tau+dt)`

`df/dV = dt [(tau+dt) s' + tau' (g-s)] / (tau+dt)^2`.

On the interval between the two recorded voltages in step n, take

`a_max = tau_max/(tau_max+dt)`

`L = dt [1/(4k(tau_min+dt)) + B/(tau_min+dt)^2]`.

The mean-value theorem and the triangle inequality then give an exact-arithmetic
bound for two recurrences with the same initial gates:

`E_0 = 0; E_(n+1) = a_max E_n + L |V_cells,n - V_native,n|`.

`gate_roundoff.py` rounds the bound operations outwards with `nextafter`, including
the time-constant endpoints. Identical voltage histories produce zero allowance.
The bound consumes voltages, timestep and fixed law constants; it does not use
observed gate errors, fitted multipliers or a case-specific adjustment.

## Acceptance safeguards

1. Initial gates must match exactly. Input voltage histories must first pass the
   original voltage tolerance and domain/shape/clock checks.
2. Independently replay the native mV/ms recurrence from the initial gates using
   each history's own voltages. Compare the complete recorded gate history with
   its replay at the original gate tolerance. This is a separate cumulative
   kinetic check, not a one-step residual that could miss accumulated drift.
3. Require the actual native/Cells gate difference to be no greater than
   `original_gate_atol + original_gate_rtol * |native_gate| + E`.
   The two kinetic replay budgets are not added to this criterion.
4. Preserve original gate violations and error ratios alongside the accounted
   comparison, per-sample allowance, replay arrays and input voltages.

Every other state, field, rate, junction gate, conservation check, CPU/L4
comparison and bitwise restart criterion keeps its previous acceptance rule.
The shared comparators default to the original strict gate comparison; only the
explicit mixed-control v3 call supplies the allowance after replay checks pass.
Production trajectories never consume evolving native values.

Tests use an independent 80-digit V/s increment-form recurrence over equal,
slightly different and widely different voltage histories, including larger
timesteps. They also inject a gate error that fits inside the expanded native
budget but must fail the independent kinetic replay, plus wrong voltage and
wrong-clock histories. The archived failed regional case is a regression case,
not independent scientific replication.

## Limits and evidence reuse

This is **conditional propagation of a separately checked voltage discrepancy**.
It does not prove that all upstream discrepancies in a coupled trajectory are
roundoff, bound integration error, or certify the entire coupled system. The
original discrepancy has a demonstrated rounding mechanism; extending that
diagnosis to every case would require separate evidence. A v3 pass must be
reported with this revised gate criterion, not as a pass of v2 or bitwise BETSE
equivalence.

The eighteen completed observed/bare native pairs are reused under their frozen
v2 protocol. The new protocol binds the failed parent, original protocol,
complete native receipt and panel; every row and trace is authenticated and
observer neutrality is checked again. Physical inputs and all original scalar
tolerances must match. The full native update oracles still run on CPU, and
their results are reused on GPU only after the CPU suite has passed. The failed
parent and all native files remain untouched.
