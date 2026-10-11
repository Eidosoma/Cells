# BIO-002: a conditioned electrical endpoint comparator

2026-09-09, D043. This implements the small descriptive calculation selected
in [BIO-001](BIOLOGICAL_BENCHMARK_001.md), not a production cell model or a new
biological validation claim. The [fixed protocol](../configs/reference/bio002_conditioned_voltage_v1.json)
is written before calculation and retains the prior dataset and split unchanged.
All outcomes were already visible during curation; this is not blinded or
prospective validation.

## Measurement-boundary approximation

The measured quantity in the [source study](https://doi.org/10.1242/bio.048553)
is voltage in whole-cell, zero-applied-current recording. Zero applied current
does not mean a prescribed voltage, closed cell, or absence of intracellular
dialysis. This reference conditions on fixed but unknown internal ionic
composition, fixed relative permeabilities and temperature across C1-C3.
It does not evolve intracellular amounts, model an electrode current, or set
internal free-ion values from the pipette recipe. There is no voltage anchor
retuned to C3.

The external Na/K/Cl values remain as transcribed. Ca at 1.8 mM and Mg at 1 mM
supply 5.6 mM positive charge equivalents in bath bookkeeping. They carry no
modeled membrane current in this approximation. This records omitted current
paths explicitly, not proof that these ions lack biological effects. The recipe
check is salt stoichiometry, not a complete buffer/activity/speciation calculation.
Pump and intercellular currents are also omitted, not experimentally ruled out.

These assumptions produce an electrical endpoint comparator, not a stationary
whole-cell ion-homeostasis solution. Fixed internal concentrations may require
external support even when net electrical current is zero. There are no time
steps, recovery rates, volume/capacitance estimates, metabolism or inheritance
in this calculation. The production model and its charge checks stay unchanged.

## Equation and what it identifies

For monovalent passive constant-field currents at zero net current:

```text
V = V_T log[(P_K K_o + P_Na Na_o + P_Cl Cl_i)
           / (P_K K_i + P_Na Na_i + P_Cl Cl_o)]
V_T = k_B T / e
```

Here concentrations share a unit and V/V_T is dimensionless. In the selected
series, `Na_o + K_o = S = 145.4 mM` and `Cl_o = 151 mM`. With denominator D
fixed, the equation reduces to:

```text
exp(V / V_T) = a + b K_o
a = (P_Na S + P_Cl Cl_i) / D
b = (P_K - P_Na) / D
```

Thus `a` is dimensionless and `b` is in mM^-1. Two endpoints can identify these
two **effective curve coefficients**, not all permeabilities, intracellular ions,
pump rates, cell geometry or a unique cell mechanism. A positive fitted curve
does not establish a physically admissible decomposition into those quantities.
No biological parameter decomposition is asserted or optimized here.

Implementation uses mV for observed/predicted voltage and
`V_T_mV = 1000 k_B T / e` with SI defining constants. It solves a and b from
C1/C2 only. C3 contributes its potassium concentration to prediction, never its
observed voltage to fitting. A separate comparison then attaches the C3 reading.
The supported dose domain is 5.4 to 65.4 mM. Both coefficients must be finite,
and the logarithm argument must stay strictly positive over this interval.
No slope-sign filter, clipping, inferred biological prior or model selection
based on C3 is allowed.

## Reading-bound sensitivity, not statistical inference

Use each fitted voltage's curator-assigned +/-2 mV reading bound from BIO-001.
Enumerate all four corners of the C1/C2 reading box and refit the same two-point
equation at each corner. If any corner is numerically invalid or makes the
logarithm argument nonpositive in the declared dose domain, refuse the analysis;
do not discard that corner, truncate its range or insert a voltage floor.

For `t = (K - K1) / (K2 - K1)`, the exponentiated prediction is:

```text
z(K) = (1-t) exp(V1/V_T) + t exp(V2/V_T)
```

It is affine in the two exponentiated fitted voltages; their exponentials and
the final logarithm are monotone. Its extrema over the reading box therefore
occur at corners, including extrapolation where one weight is negative.
For the change from C1, use **the same perturbed C1 value** in the fit and in
the subtraction. The ratio `z(K)/exp(V1/V_T)` depends monotonically on V2-V1
where valid, so corner enumeration also bounds this correlated change.
Do not subtract independent marginal intervals for a shared baseline.

Allow the C3 reading its own +/-2 mV box for descriptive residual bounds.
The signed residual is prediction minus the measured reading. Its box range
is `[prediction_low - measured_high, prediction_high - measured_low]`.
The no-response comparator predicts the C1 voltage and zero voltage change;
its own C1 reading bound is propagated too.

These are full-box worst-case sensitivity ranges under assigned reading bounds,
not Gaussian errors, sampled parameter distributions, SEMs or confidence
intervals. Source measurement uncertainty and experiment-level dependence remain
unknown. The boxes do not establish independence of random measurement errors.
Overlapping ranges cannot be relabeled as biological acceptance.

## Verification and output contract

Keep the pure algebra separate from the dataset adapter and report renderer.
Test synthetic responses, fit/evaluation separation, invalid inputs/domains,
the extrapolation corner ordering and shared-baseline sensitivity. Independently
check the central result and all four corners with a 60-digit Decimal calculation
using the weighted-exponential expression above, not the fitted-coefficient
implementation. The absolute numerical agreement target is 1e-10 mV; it is
not a biological error criterion or a formal interval-arithmetic certificate.

The adapter first checks the original dataset's integrity and exact hashes,
split and recipe/background-ion arithmetic. It archives the fixed protocol,
records source/runtime identities and writes only to a new output directory.
There is no overwrite, automatic retry, new dependency or source-data mutation.

Outputs are an analysis JSON, a condition-by-condition CSV and a small SVG
comparison plot, plus a protocol copy. The plot distinguishes C1/C2 fitting
from C3 evaluation and labels the displayed ranges as reading sensitivity.
The final analysis reports numerical checks, a, b, predicted and approximate
measured C3 voltage, signed/absolute discrepancy, change from C1, the no-response
comparator, all four fit corners and the propagated ranges.

`model_fit` is performed in this new analysis; the original BIO-001 manifest's
no-fit/no-run claims remain historical curation-slice metadata and are not edited.
`trajectory_integration` remains false and `biological_acceptance` remains
`not_assessable`. A favorable descriptive error cannot close that gate.

## After this slice

Review experimental uncertainty and the measurement-boundary approximation
before quantitative biological acceptance. Do not tune new mechanisms to C3 and
continue calling it untouched evaluation data. A production extension needs its
own identified boundary/model and numerical qualification. Optimization, GPU work
and long E02 execution remain paused/deferred under D042.
