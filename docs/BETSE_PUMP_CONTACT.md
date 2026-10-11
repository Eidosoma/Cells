# REF-005a: substrate-dependent Na/K pump source contact

2026-09-16, D107. Validation-only first step toward a realistic production
pump–leak model. Not a production feature, coupled trajectory or biological
qualification. The [realism baseline](BETSE_REALISM_AND_NEXT_STEPS.md) remains the
larger objective.

## Distinct mechanisms, not fitted equivalence

Cells' accepted physical pump is a bounded phenomenological reversible law:
capacity times `tanh(-cycle_free_energy / (2 R T))`. It preserves stoichiometry
and energy accounting, but does not implement BETSE's substrate-dependent
saturation kinetics. Keep it available under its existing identity.

Read the pinned [BETSE pump](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/sim_toolbox.py#L71),
[parameters](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/parameters.py#L1064)
and [driver](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/sim.py#L1190).
This is BETSE 1.5.0, not the distinct BITSEY-derived nominal mechanism already
in Cells. The latter has different metabolic constants and an additional
diffusivity condition; it is not a shortcut to physical BETSE parity.

For the forward cycle (three Na out, two K in, one ATP hydrolysed), define:

```
Q = ((ADP/1000)*(Pi/1000)/(ATP/1000)) * (Na_out/Na_in)^3 * (K_in/K_out)^2
A = deltaG0 + R*T*ln(Q) - F*Vm                         [J/mol of cycles]
s = Na_in^3/(KmNa^3+Na_in^3) * K_out^2/(KmK^2+K_out^2) * ATP/(KmATP+ATP)
j = alpha * availability * s * (1 - exp(A/(R*T)))     [mol cycles/m²/s]
Na_in_rate = -3 * area * j * 1e15                    [fmol/s]
K_in_rate  =  2 * area * j * 1e15                    [fmol/s]
I_in      = -F * area * j                            [A]
```

Concentrations are mM = mol/m³; the metabolic quotient uses the explicit 1 M
standard state. `Vm` is inside minus outside. Default source ATP/ADP/Pi are
1.5/0.1/0.1 mM, KmNa/KmK/KmATP 12/0.2/0.5 mM, deltaG0 −37,000 J/mol.
The source comment on deltaG0 is dimensionally misleading; the equation requires
J/mol, not J/(mol K). Area converts density to amount; it is not an argument to
the native pump function. A fixture alpha of 1e-7 mol cycles/m²/s is not a fit.

The independent Decimal reference uses reaction free energy. A validation-only
NumPy/JAX candidate uses log activities and `expm1`, with explicit parameters
and no state mutation. One future named production law can implement this
contract; it does not make fixed ATP into a dynamic metabolism model.

## Source details that must survive the comparison

- The third native return is **outward Na density, three times cycle density**,
  not ATP turnover. Test this explicitly before interpreting its exported name.
- `met` is accepted but unused: ATP/ADP/Pi are read from parameters. Record that
  fact; a future dynamic chemical owner must be explicitly connected.
- The driver multiplies Na/K fluxes by `rho_pump` and can zero boundary faces;
  the third exported value is not modified in the same way. Whole-cell work
  must measure actual transport, not infer it from that export.
- The source replaces a zero denominator with 1e-15. The positive-domain
  candidate rejects zero substrates and nonfinite input instead of adopting
  this guard as biology. Depletion behaviour needs a separately specified law.
- Source F/R and Cells F/R are separate profiles. Compare equal constants to
  equal constants; do not count their expected difference as a numerical error.

## First bounded executable panel

Use prescribed states, not a BETSE world or a Cells ODE. Register source hashes,
all fixture values and tolerances before either worker. Separate interpreters
call the actual unmodified native function and the validation array prototype
(NumPy, eager JAX, compiled JAX, CPU/float64).

Include voltage and temperature changes, individual substrates and Michaelis
constants, complete/partial block, zero capacity, area/capacity scaling and
forward/stall/reverse stress states. The approximately −0.3 V stall fixtures
are mathematical probes, not a physiological voltage claim. Compare Na/K/third
amount rates, signed cycle density and current against 80-digit arithmetic;
check stoichiometry, free-energy dissipation, input immutability and ignored
`met` explicitly. Unit tests must reject negative/zero substrates, invalid
areas, bad availability, nonfinite values and excessive exponential drive.

Numerical budgets fixed before capture: amount rates `2e-12 fmol/s + 2e-11*|ref|`,
current `2e-22 A + 2e-11*|ref|`, cycle density
`2e-18 mol/m²/s + 2e-11*|ref|`. Exact zero transport is required for zero capacity
or availability. These numerical budgets are not biological error tolerances.
Record all comparison rows, not just a success flag. A successful capture stays
pending independent saved-data review; no automatic audit or follow-up.

## Production route after contact

1. Review saved source-contact evidence and freeze a separately named kinetic
   law with units, domain and depletion policy. Preserve the synthetic pump.
2. Add it to existing conservative membrane/finite-outside operators through
   explicit species and energy ports. One cycle creates −3/+2 inside and +3/−2
   outside amounts; charge comes from that same transfer, not a second current.
   Fixed metabolic pools imply a declared external chemical reservoir/work term.
3. Check an independent pump-only reference, then pump plus passive leak, full
   stage-consistent state, positivity, refinement, restart and NumPy/JAX parity.
   Pinned BETSE driver preparation/ordering needs its own small preflight.
4. Run a preregistered short coupled comparison, then qualify longer relaxation
   and biological perturbations. Do not extrapolate the old 2 ms gate benchmark
   or its timestep to minutes-long ionic equilibrium.

All source-specific lifecycle compatibility remains outside production. The
kinetic kernel is batched and pure; inventories, solver stages and device
placement belong to the existing engineering layers. No GPU speed claim or
full pump–leak acceptance follows from this first component panel.
