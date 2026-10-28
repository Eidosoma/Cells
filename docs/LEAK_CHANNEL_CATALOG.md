# Chloride and mixed-cation leak components

The component independently expresses the pinned BETSE v1.5.0 ClLeak,
CatLeak and CatLeak2 laws, commit
`5269a714aa2593ed2a6708c4516289977d8ae1a2`. All three are **always open**;
they are not voltage-dependent gates. Their auxiliary m/h targets are one,
time constants are **one second**, powers are 0/0, and native initialization
sets both gates to one. The selected source assigns no fixed reversal voltage.
No temperature scaling, ionic flux, fixed direction, reversal potential or
biological fit is added here.

| Law ID | Code | Ordered source ion weights |
| --- | ---: | --- |
| `betse_clleak_always_open@1` | 32 | Cl=1 |
| `betse_catleak_na_k@1` | 33 | Na=1, K=1, **Ca=0** |
| `betse_catleak2_na_k_ca@1` | 34 | Na=1, K=1, Ca=1 |

CatLeak preserves its zero-Ca metadata and has no calcium permeability. These
are independent ion permeability weights, not a stoichiometric cotransport
cycle. `PAD_CODE=-1` is the standalone neutral sentinel; shared code zero keeps
its existing meaning and is invalid in this component.

## Array and control contract

`kinetics`, `initial_gates`, `opening`, `rhs`, `valid_codes` and `domain_valid`
use the delivered two-gate/population API. Voltage/codes are `[...,population]`;
gates/targets/tau are `[...,2,population]`, ordered m/h. Leading independent
world axes broadcast. Input voltage is in V; time constants are in seconds.
The computational voltage bound is [-0.120,+0.060] V, without a biological
range or voltage-dependence claim. Auxiliary gates remain finite within [0,1]
even though opening ignores them. Padding requires zero voltage, gates and
availability, with zero opening/RHS and neutral one-second tau.

`LAW_PERMEABILITIES` retains each source's ion order and explicit zero.
`SPECIES=(Cl,Na,K,Ca)` and `SPECIES_VALENCE` define the canonical helper axes.
`permeability_weights(codes,availability)` returns dimensionless
`[...,4,population]` coefficients. **One** [0,1] availability multiplier scales
all routes of each population together. CatLeak's calcium coefficient remains
zero for every valid control. The unchecked pure helper requires
`permeability_domain_valid`; `domain_valid` also accepts an optional
availability argument and reuses that strict predicate. Nonfinite/out-of-range
controls, booleans, malformed axes and nonzero padding controls are rejected.
Control helpers preserve the final population count declared by the code array;
extra independent worlds use leading axes, for example `[world,1]` when a
single population has different controls in several worlds.

Closing conductance changes permeability multipliers, while auxiliary gates
continue their one-second relaxation. A blocked population still requires
valid auxiliary state and declared computational voltage. Tissue composition
owns membrane/species binding and electrochemical flux/reversal calculations.

## Native targeting and clock

The actual Cl base defaults to `targets=None`; cation leaks default to
`cells.mem_i` and always scatter their opening into a full membrane array.
Explicit reordered, empty and duplicate target arrays are captured separately.
The native scatter **assigns** target entries, so duplicate indices do not add
opening probabilities. This is source-container evidence and does not define
duplicate physical populations in Cells.

Cl.run includes `v_corr`; Cation.run omits it, although initialization reads a
correction. The selected constant leak equations are unaffected. Source probes
record the actual voltage arguments by forwarding to the unmodified method.
The inherited native clock uses backward Euler with `time_unit=1`:

```
g_next = (g + dt_seconds) / (1 + dt_seconds)
```

The continuous component uses `dg/dt=1-g`. Initialization, native finite-step
updates and continuous relaxation are separate claims. Perturbed auxiliary
states (0.2,0.7) and (0.8,0.3) recover for twelve time constants, with native
2/4/8 clock refinement and independent exact solutions. Isolated continuous
gates use 32/64/128 RK4 refinement over twelve seconds. Opening remains one
throughout; these are auxiliary-clock tests, not invented voltage gating.

## Source binding and verification scope

The independent scalar Decimal reference imports no production/NumPy/JAX
helpers. Native probes execute actual pinned class/update ASTs and retain
upstream files only in external evidence. Installed files match the checkout:

| File | SHA-256 |
| --- | --- |
| `betse/metadata.py` | `6a09cc83d58ec6c1ea4b5a4c11fa0eb46d3b84518309a0495ddc7d61610ce8a1` |
| `betse/science/channels/vg_cl.py` | `e61db1f403f725fe72e3daa03419230a81a7bef5b527f8a3205a03f33965b4fe` |
| `betse/science/channels/cation.py` | `b05b4adca8e7876c2cf109988892f6c01dfa29d3225be3bf5dc3d82f182df1fa` |
| `betse/science/channels/channelsabc.py` | `ed3e6395ec844108be7b585fd1007a9e22e899ff13df964fc1a3b14e5bf944d4` |

Coverage includes exact constant opening, metadata/control ownership, actual
independent-world broadcasts, population reordering, strict padding/domains,
source target scatter and physically adequate auxiliary clocks. Coupled tissue
trajectories and GPU qualification remain coordinator-owned work. Receipts
and any failed evidence are linked from the worker's
[work log](../agent-work/cells-worker-01/WORK_LOG.md).

The first host run passed 63 contracts. Actual source probes passed twelve
target/initialization/clock cases and six twelve-second auxiliary-recovery
groups at 2/4/8 native-clock refinement. All six continuous RK4 cases show
order about 4.11. Native duplicate targets retain assignment semantics, and
the CatLeak zero-calcium coefficient stays explicit throughout the control
tests. These results validate the selected population metadata/clocks.
