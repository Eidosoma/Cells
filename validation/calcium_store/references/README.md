# Calcium store: the independent references

Reference values for `../reference_spec`, written 25 November 2026.

**What was read.** `SPEC.md` and `inputs.json`, whole. Of the rest of the repository nothing: no engine source, no test, no
design note, no run output, no history. (The project's working rules and the usage of its job script were seen; they say nothing
of this model.) Nothing here imports `cells`. Questions went to the lead and their answers are below.

**What it runs on.** Python's standard library (`decimal`, `fractions`) and NumPy. SciPy is used by `accuracy_study.py` only.
mpmath is not installed where this was made, so the high precision is `decimal`'s. Made with Python 3.13.5 (libmpdec 2.5.1),
NumPy 2.5.3 and SciPy 1.18.1 on Linux x86_64.

## The files

| File | What it holds |
| --- | --- |
| `values.json` | every output, as doubles rounded once; a test reads it and runs no integrator |
| `api.py` | `store_world(variant, control=None)`, `initial_rates(variant)`, `material_block(variant, time)`, `pump_states()`, `exchanger_states()`, `symport_states()`, and `controls()`, `units()`; they read `values.json`, or with `compute=True` make the numbers again |
| `forms.py` | the closed forms of SPEC sections 2.1 to 2.7 and the outputs of section 5, in decimal |
| `world.py` | the store world of section 3: equations, observables, controls, material block, in decimal |
| `integrators.py` | the two decimal integrators, one explicit and one implicit |
| `write_values.py` | writes `values.json`; `--check` makes it again and compares it to the byte |
| `second_route.py` | a second derivation of everything, which makes no published value |
| `accuracy_study.py`, `accuracy.json` | what was measured: the comparisons, the known limits, the tolerance study, per observable |

Run them from anywhere with `python -I -B .../write_values.py --check --jobs 4` (about 4 minutes of one processor) and
`python -I -B .../accuracy_study.py --jobs 4` (about 9).

**Names.** A key's ending is its unit, and `units()` states the signs. In the file, `store_world` is by variant and then by
control, `"none"` for none. Each case has `times_s`, `amounts_fmol`, `V_m_V`, `V_b_V`, `m`, `h`, `transfers_fmol`, `heats_pJ`,
`works_pJ`, `capacitor_energy_pJ` and `free_energy_pJ`; the change since t = 0 of the amounts, the voltages and the two energies
(`amount_changes_fmol`, `V_m_change_V`, ...), because a double of the whole value can be coarse; and the totals of heat and work.
The patches' own permeabilities are the movers `plasma_permeability` and `bounding_permeability`; the others have SPEC's names. A
mover with several species or sites has its heat for each and their `total`. A control is `"release_sign"`,
`"pump_without_voltage"` or `"constants_one_percent: <the constant as inputs.json writes it>"`.

## Method

**Kernel states.** The closed forms in 60 digits, with the derivatives by hand, rounded once to a double. e^x - 1 and ln(1 + x)
are taken in raised precision, so a small x keeps its digits.

**The store world.** The unknowns are the movers' transfers since t = 0, the two gates, and each mover's heat and work. The
amounts are the initial ones plus whole numbers of transfers. The voltages are the declared ones plus the charge moved over the
capacitance. So matter and charge are conserved exactly and a change of 1e-6 fmol in 300 fmol keeps its digits. All movers act
together; there is no splitting. The integrator is the midpoint rule, extrapolated over 12 columns (order 24), in 40 digits,
with steps of 1 ms. It uses decimal operations only, so the file does not depend on the machine's linear algebra or its
elementary functions.

**The material block.** The slopes of the laws by hand, at the 40-digit solution. Every column sums to zero over the calcium
rows and over the sodium rows, so two eigenvalues are exactly 0 and the other three are the roots of a cubic, taken in 60 digits.

**The second route** (`second_route.py`) starts from one idea instead of SPEC's list: a mover is a set of moves and a one-way
forward rate; its free energy is the sum of its moves' electrochemical potentials, plus the fuel's; J = forward (1 - e^gap) and
heat = -RT gap J. The kernel states and the rates at t = 0 are in exact fractions with their own exponential and logarithm (420
bits, integers) and derivatives by dual numbers; a symport's J has no exponential in it at all. The store world is in doubles,
with the amounts as unknowns and the potentials of the nodes, for SciPy's integrators. It shares no code with the first.

## Decisions of the author that the lead accepted (25 November 2026)

Whoever writes the rows should use the same ones. The second to the fifth say what a planted control does.

1. A number of `inputs.json` is the double nearest to its literal, taken exactly: what a JSON reader hands on.
2. All 17 controls are given for both variants. One percent is 1.01 times the number, exactly. Without buffers the two binding
   constants move nothing.
3. The two capacitance controls: the fixed charges X_v are computed again, so the declared initial voltages and the initial
   amounts stay as they are.
4. `release_sign`: the turned J is used everywhere, in the amounts, the reported transfer and the heat. Its heat is then
   negative, and G + heat - work is still constant.
5. `pump_without_voltage`: x is without -n z psi in the rate and in the heat (-1e-3 RT J x with that x). The work is
   -1e-3 RT J x_fuel and the moved ions and their charge are as before, all with that J. G + heat - work then drifts, by the
   work against the voltage that this control leaves out: to +7.24e-5 pJ at 8 ms (+7.40e-5 without buffers).
6. J at V_stall and V_rev, and 1e-6 V either side, is at the exact real voltage, so J there is exactly 0. `near_V_stall` and
   `near_V_rev` hold the doubles nearest those three voltages and J at each, taken exactly.

## Other readings, taken without asking

7. The numbers in SPEC's text (0.010 V, 0.006, 1e-15, the SI constants) are exact decimals.
8. G and the fixed charges run over every row of every node: the constant rows too, and the buffer's rows where its reactions
   do not run.
9. `initial_rates` is given for both variants; without buffers the four reaction rates and their heats are 0. It also holds the
   gates' and the rows' rates and the fixed charges X_v.
10. The material block at the last time is at t = 0.008 s of the variant's own solution, with no control.
11. "J with V_NP changed" is J at V_NP + 0.1 V and at -V_NP. The law has no voltage, so it is J.
12. `in_domain` is decided on the exact x.

The six questions asked are the six decisions above. None is open.

## What was reached

Sizes are the largest found; `accuracy.json` has them per observable, per control and per setting.

**Kernel states** (47 pumps, 38 exchangers, 68 symports; 2,876 numbers): the two routes agree to 6e-41 of each number before
rounding, and 60 digits agree with 90 to the same. That is the measured floor of 60 digits. It is set by J at the doubles nearest
a stall or reversal voltage, where the two one-way rates cancel. The next is a pump's slope at N, 1.7e-42 (below); every other
output agrees to 1.1e-53 or better. Every double is the same by both routes and at both precisions. Wanted: 1e-13. The **rates
at t = 0** agree to 1.4e-58.

**The store world**, over both variants, as a part of each observable's largest change:

| Observable | explicit against implicit, decimal | against the second route in doubles (DOP853) |
| --- | --- | --- |
| amounts | 2.6e-27 | 4.3e-14 |
| V_m, V_b | 2.4e-27 | 2.5e-14 |
| m, h | 3.8e-33 | 1.2e-15 |
| transfers | 2.1e-27 | 2.1e-14 |
| heats | 5.4e-27 | 5.0e-14 |
| works | 1.2e-28 | 1.3e-15 |
| energies, totals | 5.5e-28 | 1.0e-14 |

Wanted: 1e-10, and 1e-9 for transfers, heats and work. Over all 36 cases with their controls the two columns are at most
6.8e-27 and 1.2e-13. The published value is then one rounding away: 1.1e-16 of itself.

**How it is known.** The error of each method falls as its order says, and a run beyond all of them (4 steps in 2 ms, 14
columns) agrees with the published settings to 3e-33. The first column is the implicit method's own error.

| Method | Setting (steps per 2 ms) | Largest difference |
| --- | --- | --- |
| extrapolated midpoint, explicit, 40 digits | 1 step, 6 / 8 / 10 / 12 columns | 3.5e-10 / 5.6e-15 / 3.3e-20 / 8.6e-26 |
| | 2 steps, 6 / 8 / 10 / 12 columns | 6.6e-14 / 6.1e-20 / 2.1e-26 / 3.3e-33 |
| Radau IIA, implicit, 40 digits | 2 steps, 3 / 5 / 7 / 9 stages | 2.3e-6 / 1.4e-12 / 1.7e-19 / 5.4e-27 |
| SciPy DOP853, second route | rtol 1e-6 / 1e-9 / 1e-12 / 2.3e-14 | 6.1e-9 / 1.7e-10 / 1.7e-13 / 6.1e-14 |
| SciPy Radau, second route | rtol 1e-6 / 1e-9 / 1e-12 | 1.5e-8 / 2.6e-12 / 2.0e-14 |
| SciPy BDF, second route | rtol 1e-6 / 1e-9 / 1e-12 | 1.7e-5 / 5.3e-8 / 5.2e-10 |
| SciPy LSODA, second route | rtol 1e-6 / 1e-9 / 1e-12 | 2.2e-6 / 3.6e-9 / 5.6e-12 |

**Made again.** `values.json` and `accuracy.json`, each under the hash seeds 1 and 2 with one BLAS thread: the same to the byte.
(Run with `python -s -P -B`, because `-I` does not read `PYTHONHASHSEED`.)

**Balances.** G + heat - work moves by at most 5e-36 pJ, at every time of the two variants and at the last time of every control
but `pump_without_voltage`. In the two variants matter moves by 1e-44 fmol, and the voltages from the charges and X_v differ from
the integrated ones by 7e-36 V. No mover's heat falls in any case but the release's under `release_sign`.

**The material block.** The slopes by hand agree with central differences in 60 digits to 1e-35, and with the second route's
differences in doubles to 3e-9, about what differences in doubles can reach. The eigenvalues agree with NumPy's to 1e-15 of the
largest.

**The fastest rates** are 445 1/s and 245 1/s, then 54, 51 and 40 1/s. By their size the first is the charging of the bounding
patch, the second the store's free buffer and the last the m gate; that naming is an estimate. No eigenvalue of the whole system
has a positive real part at t = 0 or at 8 ms.

**Known limits checked**, each in `accuracy.json`: no flux at the reversal potential, the plain diffusion limit at no voltage, the
two sides exchanged, half saturation, no cycle at the stall and the reversal voltages and its sign either side, no net flux at
equal concentrations (a symport's is exactly 0, the exchanger reverses at exactly 0 V), a reaction at equilibrium, and no
negative heat in any state or in the random draws. The integrators were tried on equations with known solutions.

## For whoever writes the rows

- **A double of a large amount does not hold 1e-10 of its own change.** Outside Cl holds 1.3e-8 of it, outside Na 1.1e-9, and G
  7e-10. Compare the changes, which are published as doubles of their own. All other amounts hold 8.5e-11 or better.
- **Near equilibrium a symport shows its inputs' rounding.** Reading the literals as decimals instead of doubles moves J by up
  to 6.2e-14 and the heat by 1.25e-13 of themselves, at 0.1% from equilibrium. So a band of 1e-13 on that heat is at its edge:
  a program in doubles loses at least as much. The exchangers and the pumps move by 6e-15 at most.
- **Some slopes are small differences of large terms.** The pump's dJ/dn at N in `random 0` is 2e-19 of the two terms the product
  rule gives, so a program in doubles that adds them has no digit of it. They cancel because far below K the backward rate of a
  reversed cycle does not depend on c_N. The same slope as n J+ (r + e^x) / ((1 + r) c_N V_N), with r = (K/c_N)^n, loses nothing
  and gives the published number. `beyond the domain, above` is at 2e-12 and `reversed by gradient and voltage` at 2e-4. For the
  exchanger the worst are d/dNa_P of `sodium saturating outside` at 3e-7 and d/dNa_N of `random 0` at 2e-5.
- **What each control moves**, in `accuracy.json` under `controls`: at least 4.4e-3 of some observable's largest change (the
  bounding permeability of K), most of them 1e-2 to 8e-2, and the two changes of a law 0.5 to 9. The only ones that move
  nothing are the binding constants without buffers.
- A numerical eigenvalue routine gives about 1e-15 of the largest where two eigenvalues are exactly 0.

## Not done, not checked

- No comparison with the engine. The equations are SPEC's; both routes share one reading of them.
- `values.json` was made on one machine. That it is the same to the byte elsewhere is argued from decimal arithmetic, not tried.
- Initial rates and material blocks are not given for the controls; SPEC asks for neither.
