# Four additional pinned calcium-channel classes

This standalone component covers BETSE v1.5.0 `Ca_L2`, `Ca_L3`, `Cav_G` and
`CaLeak` at commit `5269a714aa2593ed2a6708c4516289977d8ae1a2`. The selected
class and inherited gate equations use voltage only. They contain no
calcium-concentration input, ligand binding or dynamic calcium-dependent
inactivation. All four declare relative Ca permeability one.

| Law ID | Future code | Source m/h powers | Important distinction |
| --- | ---: | --- | --- |
| `betse_ca_l2_m2h@1` | 35 | 2/1 | Unshifted targets, fixed 10/59-ms tau |
| `betse_ca_l3_shift15_m2h@1` | 36 | 2/1 | Native V−15-mV shift, fixed 10/59-ms tau |
| `betse_cav_g_m2h_regularized@1` | 37 | 2/1 | Analytic rate limit at −27 mV |
| `betse_caleak_always_open@1` | 38 | 0/0 | Always open, one-second auxiliary clocks |

The numbers are reserved standalone identities for later integration. The
shared catalog, existing models and shared code zero retain their meanings.
`PAD_CODE=-1` is the neutral sentinel for this component.

## Source aliases, shifts and temperature

`Ca_L2` shares **targets only** with the accepted Cav1p3; its constant time
scales differ from Cav1p3's voltage-dependent ones. Its target midpoints are
−30 mV for m and −80 mV for h, with slopes −6/+6.4 mV. `Ca_L3` applies the
source's 15-mV subtraction to both targets, moving their midpoints to −15 and
−65 mV. Its slope values remain unchanged despite upstream prose describing
a broader activation peak. Neither class is a complete existing kinetic alias.
In particular, Cav1p2 has a different 10-mV shift and voltage-dependent taus.

The three gated classes set `Texpt=36` °C and `qt=1`; CaLeak sets `Texpt=23`
°C and `qt=1`. No active Q10 equation uses those experimental labels. They
are retained as source metadata. A later tissue choice of 298.15 K does not
refit the channels to that temperature. This interface takes no temperature
argument and adds no inferred scaling.

Nominal source `vrev` is 131 mV for the three gated classes and 30 mV for
CaLeak. These values are recorded rather than imposed on ionic flux; actual
reversal potentials belong to the composing electrochemistry.

CaLeak's upstream description says “substance-modulated,” but the selected
methods and inherited gate update supply no ligand equation. Its gate
opening is identically one. A composing model may apply its explicitly owned
conductance control; this component does not infer ligand dependence.

## Cav_G analytic limit

The source activation rate, in inverse milliseconds, is:

```text
alpha_m = .055*(-27-V_mV)/(exp((-27-V_mV)/3.8)-1)
beta_m  = .94*exp((-75-V_mV)/17)
alpha_h = .000457*exp((-13-V_mV)/50)
beta_h  = .0065/(exp((-V_mV-15)/28)+1)
```

Targets are alpha/(alpha+beta); tau is 1/(alpha+beta) milliseconds. At −27 mV
the raw alpha_m expression is 0/0. The named regularized law uses
`.055*3.8*x/expm1(x)`, with `x=(-27-V_mV)/3.8`, and its analytic limit
**0.209/ms**. The existing differentiable Bernoulli helper evaluates that
limit without moving the input voltage. No concentration or gate floor is
introduced.

Actual pinned initialization, calculation and run failures at the singular
voltage are saved separately, including raw nonfinite arrays. Nearby binary
inputs retain a source-conditioning diagnostic. These are upstream defect
records; successful regularized limits do not claim that native source runs
pass at the singularity.

## Array, domain and native-clock contract

`CALCIUM_EXTRA_LAWS`, `LAW_CODES`, `LAW_PERMEABILITIES` and `GATE_POWERS` define
metadata. `kinetics(voltage,law_codes)` returns targets and tau; `initial_gates`
returns those targets. Voltage/codes have `[...,population]` axes;
gates/targets/tau have `[...,2,population]` axes, in m/h order. Independent
leading worlds broadcast. Voltage is V and tau is seconds.

`opening(gates,law_codes)` is m²h for codes35--37, one for CaLeak and zero for
padding. `rhs(gates,voltage,law_codes)` expresses continuous relaxation
`dg/dt=(target-g)/tau_seconds`. Gate energy, gating charge, ionic transfer,
conductance controls and model state ownership are not added here.

The computational domain is −0.120 through +0.060 V, with finite gates in
[0,1], integer codes and positive finite tau. It is not a biological
calibration. `domain_valid` rejects malformed gate/population axes, booleans,
unknown codes and invalid inputs. CaLeak auxiliary state remains strict even
though its opening ignores the gates. Active physical inputs are never
clipped or repaired. Kernels are unchecked and require domain validation.
Declared inputs are checked before broadcasting, so an empty population axis
cannot erase an invalid code, nonfinite value or out-of-domain gate/voltage.

Padding has V=gate=target=RHS=opening=0 and tau=1 second. Empty population
axes are explicit. The native inherited updater is backward Euler,
`g_next=(tau*g+dt*target)/(tau+dt)`, whereas the component exposes a
continuous ODE. The source gated classes divide native millisecond taus by
1000; CaLeak's native `time_unit=1` makes its auxiliary tau **one second**.
The native outer correction `v_corr` is in mV and precedes Ca_L3's own shift.
Default, reordered, empty and duplicate native target arrays are captured;
their scatter assigns entries, with the last duplicate winning.

## Independent evidence and adequate physical duration

The [protocol](../validation/channels/calcium_catalog_extra_protocol.json)
binds source hashes, clock distinctions and tolerances. The independent
[80-digit Decimal reference](../validation/channels/calcium_catalog_extra_reference.py)
imports no Cells, NumPy or JAX code. It expresses native millivolt equations
separately and uses the exact scalar limit at the singularity. Compiled
derivatives are compared against 80-digit centered differences.

Actual-source probes execute unchanged class/update ASTs in a minimal
namespace; upstream copies live only in external evidence. They compare
initialization, ordinary updates, native target scatter and voltage correction.
The installed and pinned-checkout `vg_ca.py` match SHA-256
`843d83f969ec53ba9322504f6ef0f699171c3c7c6e2caf03784de5bb17171dd6`.
The protocol also binds metadata and inherited updater files.

Clamps step from −80 mV to zero and back. Each phase lasts twelve times its
slowest gate tau. Native backward-Euler traces refine at 2/4/8 subdivisions
of an independent geometric grid. All sixteen isolated continuous gate
experiments run twelve of that gate's time constants at 32/64/128 RK4 steps,
holding the companion at its exact fixed point. This supports gate-equation
accuracy without a coupled-timestep claim. CaLeak starts a separate
manufactured auxiliary perturbation and relaxes for twelve seconds per
phase; opening remains one throughout.

Host checks select `tests/unit/test_calcium_catalog_extra.py -k 'not jax'`.
Two separate CPU JAX prototypes select `-k jax` after coordinator clearance.
Receipts, arrays and preserved failures are linked from the worker's
[work log](../agent-work/cells-worker-01/WORK_LOG.md). Coupled tissue histories,
experimental calibration, explicit ligand laws and GPU qualification remain
separate work.
