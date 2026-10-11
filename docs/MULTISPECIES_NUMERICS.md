# Multispecies trajectory qualification protocol

NUM-006, 2026-09-09. This protocol precedes numerical evaluation. It extends
the [completed SPEC-005 contract](MULTISPECIES_MEMBRANE_SPEC.md) to short
trajectories, without changing any physical input, production model or prior
result. Completion status and measurements belong in the separate
[qualification report](../reports/NUM006_REFERENCE.md).

## Frozen cases and scope

[multispecies_trajectories_v1.json](../configs/reference/multispecies_trajectories_v1.json)
pins the byte identity of SPEC-005's physical panel. Resolve its Na/K/Cl and
divalent/background-charge assemblies without repairs or parameter changes.
For each, test baseline at 1 and 10 s, passive-only at 10 s, pump-only at 1 s,
all-off at 1 s, block/release at 2 s and a 1 ms pump pulse within 1 s: 14 cases.
The named `Ca` fixture remains an unbuffered synthetic +2 species, not calcium
signaling or a calibrated cell. No equilibrium or long-time physiology is claimed.

Profiles contain a uniform passive multiplier plus explicitly named blocked
species and an independent pump multiplier. Resolve these into species-ordered
control tuples on the host. Unknown or duplicate blocked IDs are errors, not
ignored entries. This profile shorthand is reference data, not a new production
configuration language. Controls start at zero and are strictly increasing.

Block/release separately interrupts the pump and a Na or Ca route, contains
an all-off interval [0.713, 1.307] s, and changes controls at the final time.
The pulse at [0.203, 0.204] s is shorter than every candidate's nominal step.
All event times belong to the integration grid. Final-time events change the
instantaneous readout, not the preceding evolution. Preserve all anchors and
signed material/cycle/dissipation ledgers across boundaries.

## Independent formulations and coordinates

The SciPy reference implements the symmetric hyperbolic constant-field law,
not SPEC-005's Bernoulli implementation or a Cells kernel:

```text
H(x) = x / [2 tanh(x/2)], H(0) = 1
J_s = A P_s u_s / a * [(c_o,s - c_i,s) H(x_s) - (c_o,s + c_i,s) x_s/2]
```

Resolve the pump's sodium/potassium roles by ID and compute its affinity law
independently. Evolve amount increments `delta_n = n - n_ref`, passive transfer
ledgers L, cycle ledger P and dissipation quadrature D in pJ. Voltage uses
increments directly. D is a numerical diagnostic, not new biological state.

The candidate is a separate scalar RK4 experiment using the existing independent
SPEC-005 Bernoulli evaluator and **absolute amounts** at stages. This tests both
the equation formulation and cancellation in the coordinate choice proposed
for production. No production/JAX code is imported. Save canonical increments
for comparisons, explicitly converting candidate absolute amounts back to
increments; never recenter its actual integrated state at an event.

## Reference and candidate settings

For every constant-control interval, carry the complete state into a fresh
Radau or BDF solve. Compare both (`rtol=1e-11`, `atol=1e-13`, maximum step 0.05 s)
with refined Radau (`rtol=1e-12`, `atol=1e-14`, maximum step 0.025 s). These are
local tolerances on mixed, explicitly scaled coordinates, not global guarantees.

Independently evaluate RK4 steps 0.01, 0.005 and 0.0025 s. The equality of one
trial step with a historical step is not inherited acceptance. Integrate on a
zero-anchored regular grid unioned with all events. Keep interval-held controls
at all four stages, including the right endpoint of the old interval.

Use read-only increment-form cubic Hermite observations with endpoint slopes
evaluated under that interval's controls. Return stored states exactly at
accepted times; do not choose integration steps from observation requests.
Build a shared comparison grid from every candidate endpoint and every quarter,
half and three-quarter point, including split intervals. Retain native accepted
reference states as well as common-grid observations.

## Predeclared limits

| Quantity | Candidate maximum absolute error | Reference-reference maximum |
| --- | --- | --- |
| Na/K/Cl amount and passive ledger | 1e-7 fmol | 1e-8 fmol |
| Synthetic Ca amount and passive ledger | 1e-9 fmol | 1e-10 fmol |
| Pump cycle ledger | 1e-7 fmol cycles | 1e-8 fmol cycles |
| Voltage | 1e-6 V | 1e-7 V |
| Dissipation quadrature | 1e-6 pJ | 1e-7 pJ |

The tighter divalent amount limit recognizes its much smaller initial pool;
it is chosen before calculation. Check candidate accepted points and Hermite
observations separately. Report maxima over the declared comparison points,
not rigorous continuous-time error bounds.

Material residuals `delta_n - L - nu P` must be within 1e-10 fmol per ordinary
species and 1e-12 fmol for Ca. Charge residual expressed as voltage must be
within 1e-8 V. The fixed-bath ideal chemical plus capacitor energy change,
plus D minus supplied pump work, must be within 1e-6 pJ. Compute energy change
using `log1p(delta_n/n_ref)` and a capacitor difference, avoiding subtraction
of large absolute energies. Signed bath exchange is `-(L + nu P)`.
D may not decrease by more than 1e-10 pJ between inspected ordered samples.
All-off state and disabled-route ledgers must be exactly unchanged within
their constant-control interval. A disabled divalent leak must not disable
other routes or remove its charge.

Check every actual RHS trial (including implicit Jacobian probes), accepted
state and compared observation for finite, positive amounts and
`abs(z F V/(R T)) <= 50`. For candidate cubic observations also inspect the
polynomial extrema of each amount and voltage over each complete interval.
This certifies the candidate polynomial's domain within floating arithmetic,
not its continuous-time solution error. Implicit dense-reference domain is
checked at native endpoints, solver trials and comparison points; no whole-
polynomial positivity proof is claimed for its adaptive interpolation.

Select only the coarsest step which passes **every** case and whose next-finer
trial also passes every case. Where a case's observed voltage error exceeds
1e-10 V, require the next-finer voltage error to be at most 0.8 times that
error. Below that floor do not demand meaningless ratios of roundoff. The
finest trial alone is not eligible without an additional declared refinement.
If no eligible step qualifies, report no candidate; do not change parameters,
targets or run an undeclared finer ladder. Preserve failures alongside successes.

## Bounded execution and artifacts

Use the existing CPU float64 NumPy/SciPy environment and one worker. The
scientific session is limited to 600 wall seconds, 128 MiB of artifacts,
100000 RHS calls and 100000 accepted steps per attempt, and 100000 comparison
points per case. Horizons are at most 10 s and there are exactly 14 declared
cases. These are work/output caps, not a claimed operating-system RAM limit.
The output allocation is separate from the unchanged, deferred E02 campaign.

Write only a new session directory. Freeze/capture protocol, resolved cases,
reference/checker/test sources and dependencies before integration. Retain
per-attempt native data, common-grid comparisons, checks, runtime and failures.
On a budget or domain failure, retain completed evidence and the stopping reason;
do not automatically restart, extend the campaign or mark it fully qualified.
An ordinary failed error comparison is recorded and the predeclared remaining
ladder may run, so the selection rule can be applied without hiding a coarse
failure. A read-only artifact audit must check source/payload identities,
case/sample correspondence and recompute numerical/accounting verdicts.

## Production and multiscale boundary

Passing this panel qualifies an independent numerical method on these exact
assemblies and schedules, not a parameter box or GPU implementation. CORE-006
must separately implement a new model identity and verify pure-array eager/JIT
execution, runtime guards, controls, observations and complete restart against
the frozen reference. Later stiff solvers, fine/coarse coupling, multiple
membrane potentials and distributed GPU work retain their own independent gates.
No BIO-002 refit, biological acceptance, source E02 promotion, optimization,
new dependency or production mutation is authorized by this protocol.
