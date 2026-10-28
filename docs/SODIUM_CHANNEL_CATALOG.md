# Pinned sodium-channel component catalog

This standalone component covers all seven concrete classes in BETSE v1.5.0
`science/channels/vg_na.py`, commit
`5269a714aa2593ed2a6708c4516289977d8ae1a2`. It retains the accepted NaV1.2
implementation unchanged. New tissue integration, GPU qualification and
biological fitting are separate work.

## Law and array contract

| Source class | Law ID | Component code | Opening | Time unit |
| --- | --- | ---: | --- | --- |
| Nav1p2 | `betse_nav1p2_m3h_regularized@1` | 2 | m^3 h | ms |
| Nav1p3 | `betse_nav1p3_m3h_regularized@1` | 18 | m^3 h | ms |
| NavRat2 | `betse_navrat2_m3h_regularized@1` | 19 | m^3 h | ms |
| NavRat1 | `betse_navrat1_m3h_regularized@1` | 20 | m^3 h | ms |
| NavRat3 | `betse_navrat3_m3h_regularized@1` | 21 | m^3 h | ms |
| NaLeak | `betse_naleak_always_open@1` | 22 | 1 | s |
| Nav1p6 | `betse_nav1p6_persistent_m@1` | 23 | m | ms |

Code zero is neutral padding in this sodium-only component. The accepted
shared catalog's existing code meanings remain unchanged; later composition
must select the sodium branch explicitly. Codes 18--23 are reserved here for
the six new sodium classes, leaving existing codes through 17 intact.

`kinetics(voltage, law_codes)` returns targets and time constants with shape
`[..., 2, population]`; voltage is in volts and time constants are in seconds.
Gate state has the same two-gate axis, ordered m/h. `initial_gates`, `opening`,
`rhs`, `domain_valid` and `valid_codes` form the public API.
Leading world axes broadcast independently with explicit population axes.
The computational voltage domain is -0.120 through +0.060 V, inclusive.
Active gate values must be finite and within [0,1], including an auxiliary
gate with exponent zero. Padding requires zero voltage and gate state and
produces zero opening/rates; neutral padding time constants are one second.

The source contains no temperature or Q10 scaling in these equations. The
component exposes none and makes no extension to another temperature.
The default inherited `v_corr` is zero; NaV1.2's internal 10-mV coefficient
shifts are retained separately. All source classes store a nominal 50-mV
`vrev`; this gating component does not use it as an imposed electrochemical
reversal potential or invent a channel free-energy law.

## Native clock and initialization

The inherited `VgNaABC.init` converts volts to millivolts, sets the default
voltage correction to zero and initializes from each class's m/h formulas.
Initial gates equal the declared steady targets. NaLeak initializes both
gates to one. Nav1p6 initializes m from its voltage sigmoid and h to one.
Its h gate remains a source-defined auxiliary relaxation variable with
target one and tau 1 ms, although opening ignores it. NaLeak has targets one
and tau 1 s for both gates, and opening ignores both gate states.

Native `run` recalculates voltage-dependent targets/time constants, then
`ChannelsABC.update_mh` executes

```
g_next = (tau*g + dt_native*g_inf) / (tau + dt_native)
dt_native = p.dt * self.time_unit
```

This is a backward-Euler relaxation for held voltage. The physical component
uses continuous-time `dg/dt=(g_inf-g)/tau_seconds`. Their finite-step histories
are distinct. Native gate updates and initialization are captured
separately from regularized continuous-time contracts.

## Source distinctions and singularities

NavRat1 and NavRat3 have identical inspected gate formulas but remain distinct
named classes. The source's Nav1p6 is a persistent m-only approximation. Its
source citation, [Smith et al. (1998)](https://pubmed.ncbi.nlm.nih.gov/9698304/),
is background rather than proof that this reduced gate law reproduces the
full experimental isoform. The Nav1p3 source cites
[Cummins et al. (2001)](https://pubmed.ncbi.nlm.nih.gov/11487618/).
This delivery validates the selected pinned equations and their implementation.

The following removable rate singularities receive analytic limits:

| Class | Voltage in V |
| --- | --- |
| Nav1p2 | -0.025, -0.040, -0.065000123 |
| Nav1p3 | -0.026 |
| NavRat2 | -0.038 |
| NavRat1 / NavRat3 | -0.035, -0.050, -0.075000123 |

NaLeak and Nav1p6 have no removable quotient singularity in these formulas.
Native failures at exact singular inputs remain source evidence. Finite native
values very close to a singularity can also lose accuracy by cancellation;
the independent Decimal regularized limits remain separate expected values.
No concentration floors, gate clipping or silent invalid-domain repair belongs
to this component.

| Inspected pinned file | SHA-256 |
| --- | --- |
| `betse/metadata.py` | `6a09cc83d58ec6c1ea4b5a4c11fa0eb46d3b84518309a0495ddc7d61610ce8a1` |
| `betse/science/channels/vg_na.py` | `6faa67bdc4bfd0ee35dc1cc0fd8dcd73a703ff58120d1b1968da94dac1fe8831` |
| `betse/science/channels/channelsabc.py` | `ed3e6395ec844108be7b585fd1007a9e22e899ff13df964fc1a3b14e5bf944d4` |

Each inspected installed file matches the pinned checkout. The executable
probe loads the actual installed class/update ASTs, records exact inputs,
native outputs and source hashes, and retains the upstream files only under the
external evidence directory. No upstream implementation is copied into this
repository. Per-run receipts and preserved failures belong in the worker's
[work log](../agent-work/cells-worker-01/WORK_LOG.md).

## Adequate-duration component checks

Clamp/recovery checks cover twelve slow time constants per held-voltage segment,
including second-scale Nav1p3 recovery and NaLeak relaxation. An independent
geometric clock resolves fast changes before spanning the slower gate; native
backward-Euler traces subdivide each interval by 2, 4 and 8 and converge toward
the independent exact held-voltage solution. Physical duration follows the law.

Continuous-time numerical refinement separately integrates each independent
gate over twelve of its own time constants using 32, 64 and 128 RK4 steps. The
other gate stays at its exact production fixed point, so its unrelated fast
mode does not restrict this isolated scalar convergence check. Depolarization
and recovery voltages are covered. Full two-gate clamp/recovery solutions also
check the RHS and opening directly. These component checks do not qualify a
coupled ionic trajectory or an action potential.

The first host run passed 113 contracts, including all 28 isolated-gate
refinements with observed order about 4.11. Native depolarization/recovery
protocols span 0.024--24 seconds depending on the class; Nav1p3 spans about
14.85 seconds. Their first-order backward-Euler errors decrease on refinement;
finite-step agreement with a continuous clock is not asserted. All eleven
tested native singularities failed with retained floating-point evidence,
while independent regularized contracts remain finite.
