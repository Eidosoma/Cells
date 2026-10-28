# Remaining pinned potassium-channel catalog

This standalone component covers Kv2p1, Kv2p2, Kv3p1, Kv3p2, Kv3p3, Kv3p4,
K_Fast, KLeak and Kir2p1 from BETSE v1.5.0, commit
`5269a714aa2593ed2a6708c4516289977d8ae1a2`. Existing Kv1 and Kir2.1 sources
remain unchanged. The accepted Kir2.1 kinetics and opening are reused exactly.
Shared tissue integration and GPU qualification are separate work.

## Component interface

| Source class | Law ID | Code | Opening | Native time unit |
| --- | --- | ---: | --- | --- |
| Kir2p1 | `betse_kir2p1_mh2@1` | 1 | m h^2 | ms |
| Kv2p1 | `betse_kv2p1_mh@1` | 24 | m h | ms |
| Kv2p2 | `betse_kv2p2_mh@1` | 25 | m h | ms |
| Kv3p1 | `betse_kv3p1_m@1` | 26 | m | ms |
| Kv3p2 | `betse_kv3p2_m2@1` | 27 | m^2 | ms |
| Kv3p3 | `betse_kv3p3_m2h_source_tau@1` | 28 | m^2 h | ms |
| Kv3p4 | `betse_kv3p4_mh@1` | 29 | m h | ms |
| K_Fast | `betse_k_fast_mh@1` | 30 | m h | ms |
| KLeak | `betse_kleak_always_open@1` | 31 | 1 | s |

`PAD_CODE=-1` is a separate neutral sentinel in this standalone
component. Code zero is invalid here and retains its existing shared-catalog
meaning. Future shared composition selects these potassium laws explicitly.

The API is `POTASSIUM_LAWS`, `LAW_CODES`, `LAW_PERMEABILITIES`,
`GATE_POWERS`, `PAD_CODE`, `kinetics`, `initial_gates`, `opening`, `rhs`,
`valid_codes` and `domain_valid`. Voltages and law codes have explicit final
population axes; gates, targets and time constants have
`[..., 2, population]` axes, ordered m/h. Independent leading world axes
broadcast. Inputs use volts and returned time constants use seconds.
The declared computational domain is -0.120 through +0.060 V, with finite
gates in [0,1]. Padding requires zero voltage/gates, returns zero opening/RHS
and neutral one-second time constants. Invalid active data are rejected.

## Source semantics

The inherited `VgKABC.init` converts volts to millivolts, defaults `v_corr`
to zero, and initializes gates at their source targets. `run` recalculates
targets/time constants before `ChannelsABC.update_mh` uses backward Euler:

```
g_next = (tau*g + p.dt*time_unit*g_inf) / (tau + p.dt*time_unit)
```

Continuous-time `dg/dt=(g_inf-g)/tau_seconds` is a distinct clock. Native
initialization, finite-step updates and continuous gate refinement have
separate captures. Auxiliary h gates for Kv3p1/Kv3p2 retain target one and
tau 1 ms although their exponent is zero. KLeak retains two one-second
auxiliary gates, both initialized to one, and always-open probability.
No temperature or Q10 scaling is inferred. Stored nominal `vrev` values are
metadata; this gating component does not impose them as ionic reversal values
or invent thermodynamic gate energy.

The nine inspected classes contain smooth sigmoid/Gaussian/exponential
functions, without a removable exponential-quotient singularity. Tests around
their transition centers and domain edges therefore check continuity and
accuracy; they do not invent native singular failures or a regularization law.

## Kv3.3 source discrepancy

The pinned Kv3p3 source stores `vrev=+82 mV` with an upstream FIXME. This is
retained as evidence and omitted from the gating/ionic-reversal contract.
Its inactivation target has a 0.25 baseline, and its source time constant is

```
tau_h_seconds = 0.199786728 + 2.776119438*exp(-V_mV/7.309565)
```

At -80 mV this is **157,254.229 seconds**; twelve time constants span
**21.8409 days of model time**. At the -120-mV domain edge it grows still
larger. The `source_tau` law name preserves those coefficients explicitly;
there is no inferred unit repair or biological calibration. The source's
[Desai et al. citation](https://pmc.ncbi.nlm.nih.gov/articles/PMC2494927/)
provides experimental context, not validation of this extrapolation. K_Fast's
source cites [Korngreen and Sakmann](https://pubmed.ncbi.nlm.nih.gov/10856117/).

## Adequate-duration verification

Depolarization/recovery clamps run to twelve slow time constants at each
held voltage, including the literal long Kv3p3 recovery horizon. Independent
exact solutions and geometric clocks resolve the fast gate and then span the
slow response with logarithmic sample growth. Refining each native clock
interval by 2/4/8 distinguishes first-order backward-Euler convergence from
continuous-time histories. The physical horizon is not shortened for runtime.

Each continuous gate is also integrated over twelve of its own time constants
at 32/64/128 RK4 steps, with its independent companion at its exact fixed point.
Full two-gate exact clamp/recovery solutions check the RHS and opening. These
are selected component-law/clock contracts, without a coupled tissue,
biological fit or long-lived physical-state qualification claim.

The independent scalar Decimal implementation imports no production/NumPy/JAX
helpers. The native probe executes actual pinned class/update ASTs and stores
source files only outside the repository. Installed and checkout files match:

| File | SHA-256 |
| --- | --- |
| `betse/metadata.py` | `6a09cc83d58ec6c1ea4b5a4c11fa0eb46d3b84518309a0495ddc7d61610ce8a1` |
| `betse/science/channels/vg_k.py` | `89412aff6163dfe4ccf61afb82418a788ff8e10fbe2ec8cda24c498316b4842f` |
| `betse/science/channels/channelsabc.py` | `ed3e6395ec844108be7b585fd1007a9e22e899ff13df964fc1a3b14e5bf944d4` |

Receipts, scoped claims and preserved failures belong in the worker's
[work log](../agent-work/cells-worker-01/WORK_LOG.md).

The first host run passed 144 contracts, including all 36 isolated-gate RK4
refinements with observed order about 4.11. Actual native-source captures passed
nine initialization/update groups, nine correction groups, seventeen smooth
transition groups and nine refined clamp/recovery groups. Kv3p3's recovery
segment spans 1,887,050.752 seconds of model time, plus 35.711 seconds for
depolarization. The complete source probe computed in about four wall seconds.
Native backward-Euler errors decrease on refinement; finite native and
continuous clocks are not asserted identical.
