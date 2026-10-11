# First state-bearing physical membrane channel

SPEC-006 / D049, 2026-09-09. **Design and independent scalar reference**, not a
new production model. Cells stays at 0.11.0. This extends the ownership contract
of [SPEC-005](MULTISPECIES_MEMBRANE_SPEC.md), without modifying its frozen inputs,
the accepted multispecies model, numerical limits or previous evidence.

## Selected mechanism and source boundary

Select the two-gate parameterization in BETSE v1.5.0's `Kv1p5`, commit
`5269a714aa2593ed2a6708c4516289977d8ae1a2`. Its activation and inactivation states
make one channel sufficient to exercise distinct timescales and hidden history.
The [pinned potassium-channel source](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/channels/vg_k.py)
provides the rate expressions, first powers of both gates, volts-to-millivolts
conversion and zero voltage correction. Its declared reversal-voltage constant
is **not** adopted as a Cells transport law: permeation uses current ion amounts
and the maintained bath through the already specified constant-field law.

The [source gate updater](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/channels/channelsabc.py)
uses a voltage-held semi-implicit Euler update, not an exact exponential step.
We adopt the continuous kinetic equations; we do not promise identical native
discrete trajectories or silently replace our coupled integrator with that update.

The source cites [Philipson et al. (1991)](https://pubmed.ncbi.nlm.nih.gov/1986382/).
The reviewed primary abstract reports heterologous expression in Xenopus oocytes
and a voltage-dependent outward potassium current with slow inactivation.
That qualitative evidence does not establish the provenance/uncertainty of every
coefficient below, a calibrated temperature law, RPTEC applicability or the
validity of our chosen permeability. No paper trace is digitized or fitted here.

This is an independent equation implementation, with no BETSE install, import,
vendored source or native execution. The inspected source
[license](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/LICENSE)
is recorded with the reviewed byte identities in the frozen panel. A later native
comparison remains separate from these arithmetic checks.

## Continuous gate law and units

Named law: `betse_kv1p5_mh@1`. Voltage `V` is inside minus bath, in **volts**;
time is in **seconds**. There is no selectable unit string, voltage correction,
temperature factor, executable expression or implicit equilibrium initialization.

```text
sigmoid(x) = 1 / (1 + exp(-x))
m_inf(V) = sigmoid((V + 0.0060) / 0.0064)
h_inf(V) = sigmoid(-(V + 0.0253) / 0.0035)
tau_m(V) = 0.008330 - 0.1163 V       seconds
tau_h(V) = 1.620000 - 15.500 V       seconds
dm/dt = (m_inf(V) - m) / tau_m(V)
dh/dt = (h_inf(V) - h) / tau_h(V)
p_open = m h
```

These are the source formulas converted to SI time/voltage, with both gate
powers equal to one. The chosen engineering domain is **-0.120 <= V <= 0.060 V**,
not an experimentally established validity interval. It keeps the linear time
constants positive: tau_m is 1.352–22.286 ms and tau_h is 0.690–3.480 s.
Outside this interval refuse, including while inhibited. Do not extend linear
time constants by clipping, taking absolute values or adding a floor.

Both primary gates lie in [0, 1]. At each boundary the continuous derivative
points inward; at fixed V each gate relaxes monotonically to its own equilibrium.
Do not replace either gate by its equilibrium value, or store only their product:
two states with equal `m h` can have different derivatives and future responses.
An equilibrium calculation is an explicit preparation helper, not a restart rule.

This first physical reference fixes the bath temperature to **298.15 K** as an
engineering fixture. The empirical gate formula has no adopted Q10 or validated
temperature calibration. Other temperatures need a separately specified regime.
This restriction belongs to this assembly, not the general multispecies engine.

## Definition and separate ownership

Reference schema: `cells.voltage_gated_membrane_reference@1`.
Its exact root fields are `schema`, `assembly`, `channel`. `assembly` is an
explicit SPEC-005 reference definition; this is not a production-config loader.

| Channel field | Meaning |
| --- | --- |
| `id` | Stable mechanism ID distinct from cell, membrane, bath and pump IDs |
| `membrane_id` | Existing membrane on which the mechanism is installed |
| `species_id` | Explicit potassium-role binding to one declared +1 species; spelling is not chemical identity |
| `kinetic_law` | Exactly `betse_kv1p5_mh@1`; no arbitrary rate expressions |
| `max_permeability_m_per_s` | Nonnegative membrane permeability when both gates, abundance and availability are one |
| `abundance` | Nonnegative dimensionless multiplier of that reference permeability; not a molecule count or conductance in siemens |
| `initial_gate` | Explicit `m` and `h` in [0, 1], retained independently of initial voltage |

Unknown fields, duplicate JSON keys, missing/invalid bindings, mutable resolved
vectors, booleans as numbers and nonfinite inputs/derived coefficients fail.
The frozen examples retain SPEC-005's two species assemblies and add one K-bound
mechanism at synthetic permeability 1e-8 m/s and abundance 1. Neither is fitted.

Kinetics, abundance, membrane geometry and experimental availability have
different ownership. The channel's independent external control `u_ch` lies in
[0, 1] and only scales its permeation. It is not a drug concentration or a kinetic
block model. Baseline leak controls and pump control stay separate. With `u_ch=0`,
zero abundance or zero channel permeability, channel flux is exactly zero but
both gates remain present and evolve with V. If inhibiting current changes the
coupled voltage, that voltage can indirectly change gating; control-independence
of gate trajectories is asserted only under the same prescribed V history.

## Coupled rates and accounting contract

For the bound species k, add exactly one inward channel flux:

```text
P_eff = P_max abundance u_ch m h
J_ch = A P_eff / a [c_o,k B(x_k) - c_i,k B(-x_k)]
dn_s/dt = J_leak,s + nu_s r + delta_s,k J_ch
dL_s/dt = J_leak,s
dP_cycles/dt = r
dH_channel/dt = J_ch
dD_ionic/dt = -1e-3 [sum_s(J_leak,s mu_s) + r G_cycle + J_ch mu_k]  pJ/s
n_s - n_ref,s = L_s + nu_s P_cycles + delta_s,k H_channel
bath_exchange_s = -(L_s + nu_s P_cycles + delta_s,k H_channel)
I_in = q_f sum_s(z_s dn_s/dt)
C dV/dt = I_in
```

All constants, Bernoulli factors, concentrations, electrochemical potentials,
charge anchors and maintained-bath assumptions retain SPEC-005 definitions.
Baseline and channel transfers have **separate diagnostic ledgers**, even though
their amount contributions add. Channel flux is not a second membrane capacitor,
not an independent potassium inventory, and not transport over a cell-cell edge.
Turning off the mechanism must not erase prior exchange or gate state.

Amounts still own mobile charge; V is derived from the original charge anchors.
This phenomenological gate model **neglects gating charge, conformational energy,
protein turnover and gating-current capacitance**. The ionic/ideal-chemical plus
capacitor energy identity remains valid for its specified fluxes, since P_eff
is nonnegative, but is not a complete thermodynamic model of a channel protein.
Do not invent a gate-energy ledger from these empirical time constants.

The reference checks instantaneous material/charge/ionic-energy consistency,
zero/reversal/off limits, name/order invariance and old-law reduction. It does
not integrate the feedback-coupled amounts, gates and diagnostic histories.

## Exact isolated-gate test boundary

Protocol schema: `cells.kv1p5_gate_protocol@1`, with exact fields `schema`,
`initial_gate`, `end_time_s`, `voltage_steps`, `availability_steps` and
`sample_times_s`. Each step contains `time_s` and its `voltage_V` or `multiplier`.
Both schedules start explicitly at zero, are strictly increasing, and may
include a final-time setting. Samples are finite, strictly increasing and within
the horizon. No time is a physical-cell integration timestep.

On a voltage-held interval beginning at t0, use the analytic solution separately
for q=m,h:

```text
q(t) = q(t0) + (q_inf - q(t0)) [-expm1(-(t-t0)/tau_q)]
```

Only voltage-event anchors advance this reference history. Read-only sample
times and availability events do not create gate-integration steps. Gate state
is continuous at a voltage event; derivatives and availability readouts take
the new right-continuous setting. A final-time event changes those readouts but
has no preceding duration. The panel includes activation, inactivation,
deactivation/recovery, block/release, a 0.1 ms pulse, and equal-open-fraction
states with different histories. Binary64 arithmetic is checked against an
independent 70-digit Decimal expression in native millivolt/millisecond units.

Prescribed voltage here is an **isolated gate input**, not a supported whole-cell
voltage clamp. Clamping a charged cell requires an explicit electrode current,
electrode charge/work bookkeeping and boundary model. Do not override V while
continuing to claim the unmodified amount-owned charge closure.

## Production and multiscale boundary

Later production must evaluate amount and gate derivatives at the **same coupled
solver stage voltage**. An exact update at fixed V is not exact when V evolves;
Rush-Larsen, split updates or subcycling need their own convergence/accounting
tests. Every real trial stage and endpoint must retain positive ionic amounts,
gates in [0, 1] and the gate/ionic voltage domains. Dense observations must check
interior gate extrema as well as amounts and voltage, including unsampled
intervals; no gate clipping or dropped real-but-disabled state is allowed.
The existing 10 ms multispecies ceiling is not inherited or enlarged.
NUM-007 must select a new method/step for coupled reference cases before CORE-007.

The intended array ownership is gate state `[gate, channel_slot]`, one cumulative
transfer per channel slot, and immutable channel-to-membrane/species indices.
Parameters are aligned numeric leaves; a named law groups compatible kernels.
Different channel extents/types need explicit batch compatibility and memory
preflight. Inactive padding is sanitized before nonlinear operations; it is not
equivalent to a real but inhibited mechanism. This is an interface contract,
not an implemented heterogeneous-channel registry or GPU mode.

A complete future snapshot must retain both gates, channel transfer, existing
amount/exchange/energy histories, original charge anchors, stable binding and
kinetic identities, and all control cursors. Branches can change future input,
not recreate hidden states from V or m h. Reduced/multirate models must retain
or explicitly approximate the slow inactivation history and report its error.

Next gate: **NUM-007**, separately registered bounded coupled-cell implicit
references, event/interior-domain checks and candidate-method refinement. After
that, **CORE-007** may implement a new production identity and qualify JAX,
eager/restart/branch/cohort behavior against it. No channel catalog, physical
ionic graph, finite bath, GPU execution, organ preset, biological refit or long
E02 continuation is authorized by SPEC-006.
