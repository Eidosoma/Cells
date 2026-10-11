# Source-compatible EMT pair: complete model contract

SPEC-003 / D024, 2026-09-08. This document preserves the original design and
instantaneous-reference contract. Subsequent [NUM-004 qualification](SOURCE_EMT_PAIR_NUMERICS.md)
now validates the bounded independent trajectories and corresponding refined
native paths. MODEL-005 now implements [bitsey_emt_pair@1](SOURCE_EMT_PAIR.md) in
Cells 0.7.0 against those frozen references. The original provisional identity
was `bitsey_emt_pair@1-design`; its reference JSON remains a numerical input,
not a runnable Cells configuration. See the
[source map](SOURCE_COUPLING_MAP.md), [design evidence](../reports/SPEC003_DESIGN_CHECK.md)
and [progress](../PROGRESS.md).

Selected source-assay adapters and longer switching protocols remain separate
deliverables. Matching these instantaneous equations alone is necessary, not
sufficient, for those claims. [Production acceptance](../reports/MODEL005_ACCEPTANCE.md)
records the completed bounded engineering gate.

## Scope and source identity

Pin BITSEY revision `b2cb370aaecbc8299f259bc4251d5396c81f19a6`, its executable
`sim.py`, `sim_toolbox.py`, `GRN_miRNA.py` and `GJ_lib.py`, and the reviewed setup in
`zombie.py`. The native fixture records eight upstream file hashes. No upstream
implementation is vendored; reuse terms remain unresolved. The capture only
imports the reusable source modules in an isolated subprocess, never `zombie.py`
or the continuing exploration's dispatch scripts.

Specify two equal, fixed-volume cells, one oriented contact, one maintained ionic
bath, Na/K/Cl leaks, the source Na/K pump, three regulatory coordinates, and
optional **algebraic** junction gating. Default local regulation is the pinned
non-iterative binding approximation, fixed Snail 72, no forced miRNA target,
effective miRNA transport valence -1, and medium-size miRNA gate selectivity.

Two profiles are explicit data choices: ungated contact and a selected source
algebraic contact. These are not equivalent to all “Levin tests.” In particular,
the cancer pilot's endogenous K-channel expression and expression-based contact
isolation/overexpression are **not** in this first profile. The memory harness's
default ungated mechanism is closer, but its preparation, topology, challenges,
timing, and donor-removal operations still require separate corresponding cases.

## Complete state and the source packet

The native network packet has 17 rows, but only six evolve per cell in this
profile. Do not integrate an arbitrary source array as though every row were a
molecular inventory.

| Role | Source names | Proposed production ownership |
| --- | --- | --- |
| Evolving ions | `Na`, `K`, `Cl` | Ionic concentration array `[3, cell_capacity]`, mol/m³ |
| Evolving regulation | `miR200_total`, `Zeb_mRNA_total`, `ZEB_prot` | Separate array `[3, cell_capacity]`, source-scaled regulatory coordinates |
| Fixed charged context | `P` | Per-cell immutable concentration, mol/m³, charge valence -1 |
| Fixed regulatory input | `snail` | Per-cell immutable source-scaled input, 72 in the panel |
| Inert legacy context | `ST` | Preserved per-cell adapter context; zero slope and no reads driving this profile |
| Derived plotting caches | `miR200_free`, `bound0` through `bound6` | Reconstruct from regulation at every stage/observation; not integrated or independent memory |
| Derived electrical/contact values | Voltage, voltage difference, junction scales | Pure readouts of current state and layout; no separate voltage or gate ODE |

The independent calculator packs the six primary rows together for comparison;
this does not erase their different unit types. A production layout should keep
those types separate, use stable cell/contact IDs, explicit endpoints and masks,
and resolve row mappings on the host. The bounded first profile has two cells
and one edge; that is not the engine's universal cell-count constraint.

`Zeb_mRNA_free` is an alias of `bound0`, not an eighteenth row. The source returns
zero RHS entries for all plotting-cache rows **while overwriting their values**.
Those zeros are a source storage convention, not the time derivatives of the
reconstructed binding concentrations. Our pure RHS must recompute readouts and
leave its input state untouched. The fixture starts with deliberately stale but
finite caches to verify refresh ordering; it does not authorize NaN imports.

## Coordinates, constants and complete equations

Keep the whole compatibility model on **source nominal time**. Ionic variables
retain their source numerical mol/m³ convention and geometric/electrical
constants. Regulatory coordinates have no established mol/m³ or fmol conversion;
the coupled clock has no established experimentally calibrated seconds mapping.
Do not attach the isolated nominal-time GRN to the physical pair's SI clock.

All constants, bath values and effective diffusion coefficients are frozen in the
[14-case panel](../configs/reference/source_emt_pair_panel_v1.json).
In particular `F=96485`, `R=8.314`, `q=1.602e-19`, `kb=1.3806e-23`, `T=310`,
radius `r=5e-6 m`, specific capacitance `cm=0.05 F/m²`, membrane thickness
`tm=7.5e-9 m`, and contact length `L=1e-7 m`. Preserve `F/R` for GHK/pump and
`q/kb` for drift; their separately rounded values are not exactly equal.
This profile does not permit changing temperature while leaving the source's
cached `F/(R*T)` factor stale.

Let `A=4*pi*r²`, `Vcell=4*pi*r³/3`, `z=(1,1,-1)`, ionic concentrations `c`,
regulation `(u,m,zeta)`, and fixed negative-ion concentration `P`. Then:

```text
Vm_i = F * Vcell / (A*cm) * (c_Na,i + c_K,i - c_Cl,i - P_i)
delta_v_e = Vm_from - Vm_to
```

All regulatory rows, including the free-miRNA proxy, have **zero charge weight in
this closure**. Changing them cannot directly change voltage or ionic slopes in
this profile. Voltage does change miRNA transport. Endogenous regulation-to-ion
feedback would require an additional declared mechanism, not an assumed effect.

Membrane leakage is inward-positive. Preserve the literal all-element source
regularizer `epsilon=1e-25`, including at zero voltage:

```text
x_s,i = z_s*Vm_i*F/(R*T) + epsilon
j_leak,s,i = a_leak,s,i * (Dmem_s,i/tm)
             * x_s,i * (c_bath,s*exp(-x_s,i) - c_s,i) / (-expm1(-x_s,i))
```

For the source pump, with fixed ATP/ADP/Pi context:

```text
omega = (ADP*1e-3)*(Pi*1e-3)*(Na_out*1e-3)^3*(K_in*1e-3)^2
        / ((ATP*1e-3)*(Na_in*1e-3)^3*(K_out*1e-3)^2)
Keq = exp((-deltaGATP + F*Vm)/(R*T))
MM = [a/(1+a)]*[b/(1+b)]*[d/(1+d)]
     where a=(Na_in/Km_Na)^3, b=(K_out/Km_K)^2, d=ATP/Km_ATP
j_cycle = eligible * a_pump * alpha_NaK * MM * (1 - omega/Keq)
j_pump = (-3, +2, 0) * j_cycle
eligible_i = any(Dmem_s,i > 0)  # BASE coefficients, before IC controls
```

`deltaGATP=-37000`, ATP/ADP/Pi `1.5/0.15/0.15`, `alpha_NaK=1e-7`, and half-
saturation parameters `12/0.2/0.5` retain the source values. The source substitutes
`1e-15` for an exactly zero activity-product denominator. The bounded design
window below excludes that singular ionic regime; no zero-denominator parity is
claimed. Pump reversal is not clipped. Setting all base permeabilities to zero
disables the pump; setting all prescribed leak multipliers to zero does not.

Local regulation reuses the independently expressed
[isolated equations and binding approximation](EMT_REFERENCE.md):

```text
H(v; K,n,lambda) = (1 + lambda*(v/K)^n) / (1 + (v/K)^n)
u_free_proxy = u
bound_k = m * (u/40)^k / (1 + u/40)^6, k=0..6   # per binding configuration
du_local = 6*H(snail;72,2,0.4)*H(zeta;100/9,3,0.1) - 0.05*u
dm_local = (5/12)*H(snail;72,2,10)*H(zeta;25/9,2,15) - 0.5*m
dzeta_local = (1/6)*sum_k choose(6,k)*bound_k*L_k - 0.1*zeta
L = (1, 0.5, 0.2, 0.02, 0.02, 0.02, 0.02)
```

`sum choose(6,k)*bound_k = m`, but the free proxy plus bound miRNA is not equal
to the preserved total-miRNA primary coordinate. That is the selected source
approximation, not physical RNA mass conservation. Do not “repair” it silently.

For each transported row, contact flux is positive from endpoint `from` to `to`:

```text
x = z_transport*q*delta_v/(kb*T)
c_donor = c_from if x >= 0 else c_to
j_raw = (Dgj/L) * (c_from - c_to + x*c_donor)
```

Use ionic `z_transport=(1,1,-1)` and free-miRNA proxy `z_transport=-1`.
The latter flux contributes to **total miRNA**, never to an independently
evolving free row. At zero drift the donor choice is immaterial. P, Snail, ST,
mRNA, protein and binding complexes have no transport routes in this profile.

Optional algebraic gating, with parameters attached to the oriented edge:

```text
o = 1 / (1 + exp(A1*(-delta_v - V01)) + exp(A2*(delta_v - V02)))
scale_ions = Gmin + (Gmax - Gmin)*o
scale_miRNA = Gmax*o  # zero residual for medium-size source miRNA
j_ions = a_ion_contact * scale_ions * j_raw_ions
j_miRNA = a_mirna_contact * scale_miRNA * j_raw_miRNA
```

Ungated scales equal one. There is no gate relaxation time or stored gate state.
`Gmax` is a conductance multiplier, not a probability; the 45/45 parameters use
1.56. Reversing a heterotypic edge while retaining the same physical hemichannels
requires swapping `(A1,V01)` with `(A2,V02)`. Reversing endpoints alone is a
different model, not an identity transformation.

Finally, accumulate all mechanisms from the same stage state:

```text
dc_ions/dt = (A/Vcell) * (j_leak + j_pump + signed_contact_scatter(j_ions))
du/dt = du_local + (A/Vcell) * signed_contact_scatter(j_miRNA)
dm/dt = dm_local; dzeta/dt = dzeta_local
dP/dt = dSnail/dt = dST/dt = 0
```

All source surface fluxes are normalized to the **whole cell membrane area**,
including junction fluxes. Do not apply an extra contact-area fraction. For
miRNA the numerical surface flux has units of regulatory coordinate times length
per nominal time; multiplying by `A/Vcell` restores coordinate per nominal time.
It must not be labeled mol/s or electrical current.

## Controls, history and reusable engine boundaries

Keep prescribed leak multipliers `[3, membrane_capacity]`, pump multipliers
`[membrane_capacity]`, ionic-contact and miRNA-contact multipliers
`[edge_capacity]` independent. This first panel bounds them to `[0,1]` and holds
them piecewise constant. Gate amplitudes are intrinsic model parameters, not
those inhibition controls. Event readouts are right-continuous; integration
splits at events, carries state exactly, and uses interval-held controls.

The complete future production checkpoint must retain dynamic concentrations,
fixed context/layout, initial accounting anchors, time/numerical continuation,
and diagnostic histories. Proposed separate history arrays are:

- Inward leak contribution `[3, membrane_capacity]` and signed pump-cycle
  contribution `[membrane_capacity]`, in ionic concentration-equivalent units.
- Oriented ionic-contact transfer `[3, edge_capacity]`, in the same ionic units.
- Local regulatory contribution `[3, cell_capacity]` and oriented miRNA-contact
  transfer `[edge_capacity]`, in separately labeled source regulatory units.

Each ledger integrates its corresponding RHS contribution with the same stage
evaluation. None feeds back. With equal fixed volumes, initial concentrations
plus these contributions reconstruct each primary row; contact totals cancel.
Ionic conversion to fmol is available through the declared volume, but there is
no analogous established physical conversion for the regulatory ledger. No
physical dissipation inequality is asserted for the source upwind approximation;
the [source map's counterexamples](SOURCE_COUPLING_MAP.md) remain applicable.

These histories were specified, not integrated, by SPEC-003. NUM-004 now verifies
them independently; MODEL-005 now implements typed production ownership and replay.
Reuse the generic staged runner, scatter, control PyTrees, observations, snapshots
and branch policy where appropriate. Do not reuse the physical flux law, dynamic
gate, pump, source-unit labels, or RK4 step bound merely because interfaces match.
No source assay name, target phenotype, or donor/recipient role belongs in a
generic numerical kernel.

Keep arrays and explicit dependency boundaries suitable for future batching and
GPU execution. This is not yet a performance benchmark, a multirate method, a
coarse-cell closure, or multi-organ support. Those remain separately measured and
validated extensions of the [multiscale architecture](MULTISCALE_DESIGN.md).

## Prepared inputs and the frozen small panel

The panel embeds **complete** numeric packets from the earlier isolated native
capture, whose SHA256 is
`17c75594bbe2bf59af64030f9b4346fe93e334a786c2c7685f6479cb63627596`.
The old receipt is read and matched exactly during native capture; no preparation
is rerun. E and M helpers requested 10000 nominal units but accepted through
10000.315 and 10000.27 respectively. Their last observations were earlier, at
9956.355 and 9960.305. Preserve all three notions of time.

The pair starts a **new phase at time zero** from those individually accepted
packets, including their slightly different ionic values, P and Snail. Append
explicitly inert ST=0, refresh plotting caches, and start new diagnostic ledgers
at zero with imported-state anchors. This is a documented import, not an exact
continuation of the source integrator or evidence of zero equilibrium residual.
The raw packets remain available alongside the reconstructed readouts.

The source's `E/M/X` threshold rule is a reporting function, never feedback.
Changing only a label or three GRN values cannot replace a full-cell transplant.
Future memory protocols that remove donors must preserve the selected cell's
complete state/context in a declared new-world operation; blocking its old edge
is not generally the same intervention.

| Cases | Initial context and comparison |
| --- | --- |
| S00–S03 | Prepared E/M: blocked, active, ionic-only and miRNA-only routes |
| S04 | Same prepared pair with algebraic 45/45 gating |
| S05–S07 | Constructed voltage-gradient seeds; heterotypic gate, endpoints reversed only, endpoints and hemichannels reversed |
| S08–S09 | Same gradient; zero base membrane permeability versus zero IC leak controls |
| S10 | E/M seeds at exactly zero initial voltage; nonnegative regulatory boundaries |
| S11 | Independent per-species/per-cell leak and pump controls |
| S12 | Prepared pair blocked then released at 0.137 |
| S13 | Gated gradient with miRNA/pump pulse at 0.137 and restoration at 0.274 |

Constructed seeds are explicitly not prepared equilibria. Native capture makes
17 instantaneous probes: all 14 initial cases plus three event control settings.
At an event it evaluates the **original case state**, not an invented evolved
state. NUM-004 subsequently verifies evolved event trajectories separately.

## Original numerical and production acceptance sequence

The design calculator checks an intentionally bounded input window: ionic
concentrations `[1e-6,1000]`, regulation and Snail `[0,1000]`, nonnegative finite
fixed context, `abs(Vm)` and `abs(delta_v)` at most 0.2 V, electrical exponents
at most 50, finite nonnegative diffusion and bounded prescribed controls. These
were guardrails for the design, not trajectory validation or clipping rules.
NUM-004 now checks the bounded evolving panel and interpolation interiors;
new regimes still require qualification before choosing a numerical method.

The panel freezes future horizons (1 or 10 nominal units), irregular observation
times, Radau/BDF reference tolerances and refinement, candidate RK4 steps, and
separate ionic/regulatory/voltage/scale/flux error targets **before integration**.
No candidate was accepted at the design stage. NUM-004 subsequently qualifies
0.01 nominal units for this panel; the original required sequence was:

1. Integrate the same complete primary system independently with both implicit
   methods and refinement. Verify full trajectories, event carryover, fluxes,
   reconstructed caches/voltage and the separate history accounting. Require
   reference disagreement below one tenth of the frozen candidate error targets.
2. Capture bounded native coupled trajectories with separately refined source
   settings. Record actual accepted and sampled clocks, any native overshoot,
   full packets and source mutations. Do not compare mismatched times or treat
   adaptive-Euler error as an equation discrepancy. Retain failed settings.
3. Qualify an explicit method only if checked stages, dense observations, domain,
   refinement and accuracy targets pass. Otherwise investigate an appropriate
   stiff method; a GPU or the physical pair's 1 ms step is not a substitute.
4. Preserve 0.6.0 before any production edit. Implement this profile through the
   shared engineering, with independent controls, complete restart/branch,
   identity/padding tests and all earlier-model regressions. Only then choose a
   specific exploration assay and pin its extra mechanisms and protocol.

The cancer voltage strategy's local expression factor, for example, is
`1 + 30*h/(1+h)`, where `h=(u/(0.001+m))^10`; it reads regulation and changes K
leakage. Neighbor effects and contact expression strategies add further reads.
Those source mechanisms need their own explicit profile and native checks; this
first profile does not reproduce them by tuning baseline conductances.

SPEC-004 now pins a separate [longer switching protocol](E02_SWITCHING_PROTOCOL.md).
It does not change this pair contract or its old prepared packets. Its fresh
500-unit preparation and primary two-neighbour star require their own independent
qualification and a general fixed-graph profile. Padding and independent-world
batching do not expand the current pair's communicating topology.
