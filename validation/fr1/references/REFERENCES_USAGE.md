# Using FR-1's references: the closed compartment (interface only)

How to run the independent references for FR-1's items C3 to C11, and how to read their outputs
without reading their source.
- **Sources:** `docs/CLOSED_COMPARTMENT_DESIGN.md` Appendix A.2–A.10 (with the relative-displacement
  wording of 4adb6fed), and the FR lane's `reference_inputs.json`, copied unchanged beside this
  note.
- **Not read:** the engine (`src/`), the compartment's tests and fixtures, and the FR owner's
  branch beyond the inputs file.
- **Registered design:** `README.md` and `designs/`.

**Environment.** `/mnt/workspaces/Cells/venv-cpu/bin/python`, on the CPU. The references are
deterministic and use NumPy, SciPy and the standard library only. Nothing imports `cells`.
Together they take about 15 s of one CPU:

| Call | Time |
| --- | --- |
| `closed` | at most 0.2 s |
| `step_map` | at most 0.15 s per rung |
| `linear` | 0.5 s each for C6 and C7, 4 s for C8 |
| `energy` | at most 2 s per world |

```python
import json
from validation.fr1.references import api

inputs = json.load(open("validation/fr1/references/reference_inputs.json"))
W = inputs["R_closed"]["worlds"]

c3 = api.closed(W["C3_flux"])                                      # R_closed
rung = api.step_map(inputs["R_step_map"]["worlds"]["0.001"])       # R_step_map
c6 = api.linear(inputs["R_linear"]["worlds"]["C6_load_and_degrade"])   # R_linear
v = api.capacitor(inputs["R_capacitor"]["network"], q_i_C, q_j_C)      # R_capacitor
e = api.energy(inputs["R_energy"]["worlds"]["flux_export RK4"], inputs["constants"])
G = api.free_energy({"cell_0": n_c, "ecs_0": n_o}, {"cell_0": 1.0, "ecs_0": 0.1}, 310.0)
```

**Arguments** are the inputs file's own world blocks, as a plain `json.load` returns them.

**Refusals raise `ValueError`,** naming the problem. They cover:
- a declared rate (κ, a or b) that differs from its parameters by more than a relative 1e-14;
- a schedule that does not start at t = 0 or changes;
- record times that do not start at 0 or do not increase;
- a flux law that would empty its source within the record times;
- a step-map rung whose record times are not equally spaced multiples of dt;
- a constants block that is not the exact SI values.

**Time.** Every reference is exact in time: it does not depend on the world's dt or solver. The
exception is the step map, which is the engine's discrete map at the rung's dt.

## `api.closed(world)`: C3, C4, C5 and the C11 worlds (A.2, A.3, A.5)

| Key | Layout | Meaning |
| --- | --- | --- |
| `times_s` | [T] | The record times, t = 0 included |
| `form` | str | `A.2 flux`, `A.2 first-order`, `A.3`, `A.3 with a = 0` (an import alone) or `A.5` |
| `amount_fmol` | {node: [T]} | S at each node (`cell_0`, `ecs_0`) |
| `floor_fmol` | {node: [T]} | The second method's difference + ½ ulp |
| `x_eq` | float | A.3 only: b/(a + b) |
| `a_per_s`, `b_per_s` | float | A.3 only: the export's k_e and the import's κ, as declared |

## `api.step_map(world)`: one rung of R_step_map (A.4)

| Key | Layout | Meaning |
| --- | --- | --- |
| `times_s`, `steps` | [T] | The record times, and their step indices at the rung's dt |
| `x` | [T] | n_c/N, iterated from x(0) |
| `amount_fmol` | {node: [T]} | The cytosol's and the compartment's S under the map (50-digit decimals) |
| `floor_fmol` | {node: [T]} | The float64 moved-form iteration's difference + ½ ulp of N |
| `rounding_allowance_fmol` | float | 4 ulps of N per stage to the last record: the registered "to rounding" |
| `x_star`, `x_eq` | float | α(1 − β)/(1 − α²β), with α = e^{−a h/2}, β = e^{−b h}, h = dt/2; and b/(a + b) |
| `splitting` | dict | `relative_displacement` x*/x_eq − 1; `absolute_displacement` x* − x_eq; `leading_term` −a(a + 2b) dt²/96; `relative_over_leading` |

## `api.linear(world)`: C6, C7, C8 (A.6–A.8)

| Key | Layout | Meaning |
| --- | --- | --- |
| `times_s`, `nodes`, `species` | | As declared |
| `amount_fmol` | {node: {species: [T]}} | Every row; rows that never change (C7's cytosolic P) are their constants |
| `floor_fmol` | {node: {species: [T]}} | |
| `cleared_fmol`, `cleared_floor_fmol` | [T] | C6 only: the integral of k n_o |
| `moiety_fmol` | [T] | C7 only: the cytosol's S + the compartment's S + P |

## `api.capacitor(network, q_i_C, q_j_C)`: A.9

The arguments are R_capacitor's `network` and the charges of the owner (node i) and of the
compartment (node j), in C, each a scalar or an array of one shape.

| Key | Layout | Meaning |
| --- | --- | --- |
| `V_b_V` | [n] | φ_i − φ_j: equal to −q_j/C_b, so 0 for a silent compartment |
| `V_pm_V` | [n] | φ_i − φ_b: equal to (q_i + q_j)/C_pm |
| `floor_V` | [n] | |exact rational − NumPy| + ½ ulp |

## `api.energy(world, constants)` and `api.free_energy(amounts, volumes, temperature_K)`: A.10

`energy` takes a two-node world (R_closed's or R_energy's) and follows its reference trajectory
(`api.closed`).

| Key | Layout | Meaning |
| --- | --- | --- |
| `dG_pJ` | [T] | Σ over the nodes the law touches of G(n(t)) − G(n(0)) (pJ), with G = RT Σ n (ln(n/V) − 1), RT = 1e-3 R T pJ/fmol (exact SI R), ln of the mM number |
| `dG_floor_pJ` | [T] | The float64 evaluation's difference + ½ ulp |
| `dG_by_node_pJ` | {node: [T]} | Each node's part |
| `amount_fmol`, `floor_fmol` | {node: [T]} | The trajectory, as `api.closed` gives it |

`free_energy` returns G (pJ) for any amounts and volumes, at a temperature in K.

## Registered values and power

`designs/fr1_reference_values.json` holds the outputs above on the registered inputs. Long arrays
keep every k-th record and the last (`{"every": k, "values": [...]}`), and each floor keeps its
largest value. `designs/fr1_reference_design.json` holds the settled readings, the claims, each
control's deviation (`power`), the zero-power cases and the notes.
`OPENBLAS_NUM_THREADS=1 python -m validation.fr1.references.design --check` regenerates both and
compares them (exit 0 when they agree).
