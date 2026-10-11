# NUM-010: short spatial extracellular trajectory qualification

2026-09-11, D060. Prospective numerical protocol, before panel integration.
[SPEC-009](SPATIAL_EXTRACELLULAR_SPEC.md) owns the unchanged passive physical
subset. The [numerical panel](../configs/reference/spatial_extracellular_trajectories_v1.json)
pins definitions, controls, methods, tolerances and resource limits. Production
stays 0.14.0. Results and failed attempts belong in separate receipts.

## Fourteen synthetic cases

Inherit all eight SPEC-009 definitions without changing their physical inputs.
Add a blocked-cell binary salt case, membrane block/release and a 0.1 ms membrane
pulse, all using the same inherited binary definition. The single-outside case
also has a nonzero-history block/release interval. Horizons are 0.03–0.3 s.

Three further pure-bulk cases discretize the same closed 20 micrometre line
using 8, 16 and 32 equal finite volumes. They have the same cross-section,
diffusivities, total volume and analytic initial concentration profile. The
stored concentrations are **cell averages**, not point samples. This is a
one-dimensional orthogonal-grid refinement check, not arbitrary-mesh validation.

Only membrane availability changes. Bulk faces retain positive charged
conductivity and a connected graph: switching barriers and disconnected field
domains remain outside SPEC-009. Existing pumps, channel gates and junctions
remain available in their old production families but are not silently added
to this passive spatial qualification.

## Complete state and independent equation paths

Integrate all five fields explicitly in both paths:

1. Every compartment's species-amount increment, anchored to its original amount.
2. One signed species-transfer history per membrane.
3. One signed species-transfer history per bulk face.
4. One dissipated-energy history per membrane, in pJ.
5. One dissipated-energy history per bulk face, in pJ.

Histories are not inventories. No compartment is reconstructed as a total-minus-
remainder, and no ion, voltage or accepted state is projected or clipped.
Membrane/outside potentials are reconstructed at each actual stage and observation.
The selected gauge is the last compartment's potential zero; it is not an electrode.

The RK4 candidate uses the frozen SPEC-009 capacitance-component field solve and
Bernoulli GHK arithmetic. The Radau/BDF path independently assembles outside-node
current continuity and uses hyperbolic membrane flux. Literal endpoint scattering,
individual dissipation and complete-state packing are independently compared
before integration. Neither path uses production Cells/JAX dynamics.

## Conservation-tangent implicit linearization

Extend NUM-009 v2's general idea to **both** species totals and capacitance-component
charge. For N compartments, let G = 11ᵀ/N, H be the block-average projector on
capacitance components (including isolated bulk nodes), and Z = zzᵀ/(zᵀz).
On the compartment-major amount coordinates use

```text
T = I - G ⊗ I_species - H ⊗ Z + G ⊗ Z.
```

G and H commute and GH = G. Thus T is the symmetric orthogonal projector onto
directions preserving each species total and each capacitance-component charge.
On histories the Jacobian columns are zero because the physical RHS never reads
them. The supplied Newton matrix approximates Df T, **not** an unconstrained
ambient Jacobian. For a physical correction v, T v = v; no solver state, residual,
RHS or dense polynomial is projected. Actual drift still has to pass the charge
and material gates. This is a small dense CPU reference technique, not a GPU design.

Use central differences with nominal step cbrt(eps64) max(abs(increment), 0.001 fmol).
Before probing, bound that direction against all positive amounts and the affine
membrane |z F V / RT| <= 50 domain. Use at most one quarter of the nearest bound.
If the central step is less than a tenth of nominal, take two second-order
one-sided probes with the same quarter-bound rule. Count every base and probe
RHS against the attempt budget; refuse invalid or unrepresentable probes.

## Methods, events and observations

Use pinned Python 3.13.5, NumPy 2.5.3 and SciPy 1.18.1, one CPU and single-thread
numeric libraries. Radau and BDF use rtol 1e-11, atol 1e-13 and maximum step
0.005 s; refined Radau uses 1e-12, 1e-14 and 0.0025 s. Local solver tolerances are
not physical trajectory-error bounds. Callable Jacobians are supported by the
official [Radau](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.Radau.html)
and [BDF](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.BDF.html)
APIs; installed dense-output implementations are inspected and pinned separately.

Candidate RK4 steps: 4, 2, 1, 0.5, 0.25, 0.125 and 0.0625 ms. This newly tested
ladder deliberately includes steps that may be unstable on the finest spatial
grid. Retain rejected coarse trials and completed accuracy failures. Select the
coarsest all-case pass whose next-finer step also passes and meets refinement
checks. The finest candidate alone cannot qualify; do not extend the ladder
after seeing results. A finer spatial grid can impose a smaller explicit step,
independently of CPU/GPU placement.

Split both paths at every right-continuous, ID-bound control event. The candidate
mesh is the zero-anchored regular grid plus events/endpoints, independent of
observations. All RK stages and the right-end slope use the incoming interval's
held control. A final-time control changes readouts only, not the arriving state.

Common observations use 201 uniform times plus every event and quarter points
inside each control interval. Compare all candidate native endpoints as well as
these observations against the refined reference. Save complete native states
and the original dense representation: cubic Hermite for RK4, normalized power
for Radau, native Newton factors for BDF. Native queries return stored state
exactly; other queries replay the saved basis. Do not interpolate stored potentials.
Check the saved polynomial's endpoints separately, allowing only 64 float64 eps
times max(1, sum of absolute coordinate coefficients), so exact native lookup
cannot hide a mismatched dense representation.

## Acceptance limits

| Quantity | Candidate absolute difference | Reference-reference difference |
| --- | --- | --- |
| Every amount increment and signed interface history | 1e-7 fmol | 1e-8 fmol |
| Every compartment concentration | 1e-4 mM | 1e-5 mM |
| Every gauge-fixed compartment and membrane potential | 1e-6 V | 1e-7 V |
| Each interface dissipation history | 1e-6 pJ | 1e-7 pJ |

For each case, finer/coarser maximum observed concentration and potential error
must be <= 0.8, except below 1e-8 mM and 1e-10 V floors respectively. Endpoints
and observations must separately pass. These limits do not measure biological
uncertainty or establish accuracy outside this panel.

At actual RHS calls (including Jacobian probes), native states and observations,
require finite positive amounts/concentrations and membrane |z F V / RT| <= 50
even when blocked. Require capacitance-component and capacitor residuals <=
1e-20 C. Field current residual allowance is 1e-23 A + 2e-12 times the maximum
absolute diffusive/drift face-current term; save both the absolute residual and
normalized result, not just a linear solver success flag.

Independent inventory-versus-owned-history and global species residuals must be
<= 1e-10 fmol. Closed-system chemical-energy change plus membrane-capacitor energy
change and all dissipation histories must balance within 1e-6 pJ. Use anchored
log1p energy differences, count each capacitor once and introduce no bulk capacitor.
Each dissipation history may decrease by at most 1e-10 pJ. Blocked membrane
histories and their cell inventory must remain exactly constant, including
nonzero histories and off-grid dense observations; outside diffusion may continue.

Check whole RK4 cubic extrema of amounts, affine membrane voltage and linear
component-charge residuals, plus interval-constant blocked-owner polynomials.
Nonlinear field residuals are checked at actual stages/native/common observation
points, not rigorously bounded at every real time. Implicit dense domains are
likewise sampled; do not claim rigorous continuous error bounds.

## Analytic and spatial checks

The pure-bulk and blocked-cell binary examples must match the exact two-volume
ambipolar salt relaxation at reference limits, including the derived diffusion
potential. With K = A_face D_amb/(length * 1e-15) and D_amb = 2 D+ D-/(D+ + D-),
the concentration difference decays as exp[-K(1/Vu + 1/Vv)t], using volumes in pL.
The pure-bulk contrast must decrease by at least 10% by the final time.

For the line cases use c(x,0) = 100 + 20 cos(pi x/L) mM for both ions with sealed
ends. Its exact volume-average profile decays with rate D_amb pi²/L². Also
compare to the discrete eigenvalue 4 D_amb sin²(pi/(2N))/dx², separating temporal
error from spatial error. Refined-reference concentration errors to the continuum
must decrease by a factor <= 0.3 at each doubling and the 32-volume error must
be <= 0.02 mM. These cases test one smooth mode, not general tissue geometry.

For the selected RK4 step, restart every case at a saved native midpoint using
the same immutable definition, absolute clock, global grid and **all five fields**.
Require bitwise equal native/dense suffixes and observations. This validates a
reference continuation contract, not production checkpoint loading or exact BDF
restart without its internal method history. Future production I/O is CORE-010.

## Resources, provenance and stopping

At most fourteen cases / 140 main attempts; 100000 RHS calls and accepted steps
per attempt; 50000 inspected observations per attempt. Session wall cap 1800 s
and artifacts 512 MiB, including restart evidence. These are execution/output
caps, not OS memory guarantees. Preflights use short synthetic fixtures, not
hidden runs of the full scientific panel. Freeze complete source/configuration
identities and capture a source capsule before panel integration.

Use a new directory and refuse overwrites. Retain each attempt's native/dense
arrays, counters, trial-domain summary, settings and verdict. A rejected candidate
retains its completed prefix and offending time/stage/control/state; no suffix
is synthesized. A failed reference, failed analytic/spatial gate or exhausted
resource stops without retry, changed tolerance or automatic budget increase.
Reserve 1 MiB for the closing receipt. Retain accepted prefixes on other stopped
attempts whenever the remaining artifact allowance permits; if a prefix cannot
fit, record that explicit omission and its cause rather than exceeding the cap
or presenting the attempt as complete.

A read-only auditor must authenticate the capsule and every payload, reconstruct
observations, recompute conservation/control/energy, temporal and analytic/spatial
verdicts and the timestep selection, and check complete restart suffixes without
calling an ODE solver. Preserve SPEC-009, accepted production and all earlier
pilot/scientific evidence. No production, biological, organ or GPU promotion is
authorized by this numerical gate alone.
