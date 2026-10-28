# Legacy calcium- and voltage-activated potassium equation

`betse_cagpotassium_numeric_mM_scale@1` independently expresses the pinned
BETSE v1.5.0 function `betse.science.tissue.channels_o.cagPotassium`, commit
`5269a714aa2593ed2a6708c4516289977d8ae1a2`. It is a **legacy function**;
inspection found no call site in the pinned Python checkout. It is not a
current-runtime channel class, a BK/SK physiological fit or a whole-tissue
BETSE parity claim. The source docstring calls it a high-conductance calcium
activated “SK channel”; this component uses the function's explicit identity
without assigning a molecular channel subtype.

The gate reads current free cytosolic calcium, voltage and temperature. It
transports only potassium when composed with ionic flux. Sensing calcium does
not consume it. The equation has **zero channel state** and no relaxation tau,
binding inventory, ATP cost or prescribed calcium dynamics.

## Literal source equation and calcium scale

For C in the source's numeric intracellular concentration units:

```text
r = (1+1e6*C/10.22)/(1+1e6*C/.89)
P = 1/(1+6182*r^4*exp(-1.64*F*V/(R*T)))
```

V is volts and T is kelvin. The configured custom calcium concentration is
labelled mmol/L, becomes `parameters.cell_concs`, and is assigned directly
into `sim.cc_cells`. The component therefore explicitly accepts **numeric
mM** C and retains the literal **1e6 multiplier**. It makes no inferred
micromolar correction. The constants and this operational convention remain
bound to the legacy source rather than biological calibration.

Stable evaluation uses the algebraically identical bounded ratio:

```text
r = (.89/10.22) * (C+10.22e-6)/(C+.89e-6)
L = ln(6182) + 4 ln(r) - 1.64*F*V/(R*T)
P = exp(-logaddexp(0,L))
```

The numerator/denominator quotient is evaluated before its prefactor. It
avoids overflowing `1e6*C` and preserves finite nonnegative inputs, including
C=0. Positive offsets are the source constants after exact algebra, rather
than concentration floors. Raw source overflow at an extreme finite C is
recorded separately from this algebraic limit.

At zero calcium r=1 and **basal opening is positive**; the source does not
force calcium-free closure. At large calcium r approaches .89/10.22. Within
the computational domain, opening increases with C and V and remains in
(0,1). The voltage coefficient 1.64 belongs to this opening equation. Potassium
transport still has its ordinary valence +1; this coefficient is not an ionic
stoichiometry or an added gating-charge state.

## Per-population API and owner dependency

`LAW_ID`, `LAW_CODE=39`, `LAW_CODES`, `LAW_PERMEABILITIES`, `SENSED_SPECIES`,
`TRANSPORTED_SPECIES` and `GATE_STATE_COUNT=0` define metadata. Code 39 is used
by the [new tissue/calcium/finite-fuel compositions](TISSUE_RETURN_CURRENT.md#calcium-sensitive-potassium-with-the-shared-catalog).
Older catalog identities keep their previous meanings. `PAD_CODE=-1` is the
standalone neutral sentinel; tissue models use their own inactive-slot rules.

`opening(voltage,calcium_free_mM,temperature_K,law_codes)` is an unchecked
instantaneous probability. `effective_opening(...,availability)` multiplies
that probability by **one** explicit [0,1] control per K population.
`domain_valid` accepts the same inputs and optional availability; omitted
availability means one for active populations and zero for padding.

V/codes have explicit `[...,population]` axes. Scalar or leading-world Ca,
temperature and controls broadcast while preserving the final population count
declared by codes. Independent single-population worlds use `[world,1]`.
No artificial m/h gates, initial state or RHS are introduced.

The composing model must gather each membrane's **current free cytosolic Ca
amount / current cytosolic volume** at every stage. In fmol/pL this gives mM.
Several membranes may read the same cytosolic owner. Bound calcium, total
calcium, initial calcium, ER calcium and outside calcium are different inputs.
The component mutates none of them and does not scatter Ca or K amounts.
K flux, electrochemical reversal, charge, work/heat, conservation and
checkpoint ownership belong to the composing model.

The explicit computational bounds are −0.120 through +0.060 V, finite C>=0,
200 through 400 K, integer codes and finite controls in [0,1]. Temperature
enters the actual source equation rather than an inferred Q10 adjustment.
These bounds are numerical scope, without experimental fitting. Blocked
populations still require valid physical inputs. Numeric booleans, unknown
codes, malformed axes, unsafe broadcasts and nonfinite data are rejected.
Raw declarations are checked before an empty axis can discard invalid values.

Padding requires V=Ca=availability=0 and T=298.15 K, with opening zero.
Empty populations are supported explicitly. Physical inputs are never clipped,
floored or repaired. Predicate-only neutral arithmetic is used after rejection
conditions are retained; unchecked kernels require validation before use.

## Native container evidence remains separate

The actual legacy function gathers:

```text
sim.cc_cells[sim.iCa][cells.mem_to_cells][dyna.targets_cagK]
```

It then combines that **selected** calcium array with the **full** `sim.vm`
and assigns the entire `sim.Dm_cag[sim.iK]` row. It does not scatter the target
subset. Consequently, non-singleton subsets and empty targets can fail shape
broadcasting, a singleton calcium selection can affect every voltage slot,
and full reordered/duplicate targets can pair different owners with the
original voltage order. Captures preserve these behaviors and the two subset
failures. They also confirm that calcium and non-K coefficient rows remain
unchanged.

The component's per-population inputs are explicitly paired by its caller.
Successful scalar/full-identity source checks do not relabel this interface as
corrected native target-container parity. Whole legacy-function use and the
Cells model composition remain separately identified.

## Independent checks and the absence of a channel clock

The [protocol](../validation/channels/calcium_activated_potassium_protocol.json)
binds source files, operational units and numerical budgets. The separate
[80-digit Decimal oracle](../validation/channels/calcium_activated_potassium_reference.py)
uses the literal unscaled source quotient and analytic Ca/V/T derivatives;
it imports no Cells, NumPy or JAX helpers. The actual function AST is executed
unchanged in native probes, with full source copies only in external evidence.
The inventory retains the inspected source-file hashes and call-site search.

Checks cover zero/basal and saturation limits, Ca/V/T combinations, current
owner inputs, immutable concentrations, controls, actual independent-world
broadcasts, ordering, padding, empty arrays and strict domains. Source function
SHA-256 is `ee6f9c538661f42d72e01afc6d01530dcfa1a9cbf1af9945d7227842827e7251`;
the protocol also binds metadata, units/configuration and concentration setup.

Ca, voltage and control steps are evaluated on both sides of their boundaries.
A declared **external manufactured calcium input** has a one-second pulse and
a two-second exponential input decay sampled over twelve input time constants
(24 seconds). The gate is evaluated algebraically at every sample. This is
not native calcium dynamics, a channel settling experiment, or a coupled
depletion/recovery qualification. No relaxation clock is invented to meet a
duration target.

Host checks select `tests/unit/test_calcium_activated_potassium.py -k 'not jax'`.
Two separate CPU JAX prototypes select `-k jax` after coordinator clearance.
Inputs, receipts, source/container failures and array evidence are linked from
the worker's [log](../agent-work/cells-worker-01/WORK_LOG.md). Shared integration
has its own [model guide](TISSUE_RETURN_CURRENT.md#calcium-sensitive-potassium-with-the-shared-catalog)
and [current evidence](../PROGRESS.md). Longer coupled tissue histories and GPU
qualification remain separate work.
