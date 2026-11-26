# Using FR-6's A5″ references (interface only)

How to run the independent references for A5″ (a channel driven through a regulatory state with
a per-cell prior) and read their outputs without reading their source.

**Environment:** `/mnt/workspaces/Cells/venv-cpu/bin/python`, on the CPU. They are deterministic and
use NumPy, SciPy and the coupling references only; nothing imports `cells`.

| Call | Time |
| --- | --- |
| `a5pp.reference` | about 1 s |
| `a5pp.floor` | about 3.5 s |
| `a5pp.controls` | about 8 s |
| `a5pp.stand_in` | 0.3 to 2.2 s per dt |

```python
import json
from validation.fr6.references import a5pp

inputs = json.load(open("validation/fr6/references/reference_inputs.json"))
world = inputs["worlds"]["a5pp_prior"]
ref = a5pp.reference(world, inputs["constants"])
floor = a5pp.floor(world, inputs["constants"])
```

## The inputs (`reference_inputs.json`)

- **The top level:** `units`, `constants` (exact SI), `conventions` and `dt_ladder_s`.
- **The world** `a5pp_prior` holds:
  - `species` (valences), `bath_mM` and `bath_potential_V`;
  - two `cells`, each with `volume_pL`, `mM`, `initial_V`, a `patch` (`area_m2`, `capacitance_F`,
    `leak_permeability_m_per_s`), a `population` (`cells.channel.kleak_always_open@1`, `permeability_m_per_s`,
    `relative`, `abundance`, `opening`, `schedule`), `regulator_X` (`initial_mM`, turnover
    `segments`) and `state_s1_initial` (s₀);
  - `state_s1` (`cells`, the Hill `input`, `k_on_per_s`, `k_off_per_s`), the `couplings`
    (`state_fraction`, `basal`), `end_s` and `record_times_s`.

## `a5pp.reference(world, constants)`

| Key | Layout | Meaning |
| --- | --- | --- |
| `times_s` | [T] | The record times, t = 0 included |
| `cells` | ["a", "b"] | The order of the cell axis |
| `V_V` | [T, cell] | Each cell's potential (the bath at 0 V) |
| `amounts_fmol` | [T, cell, species] | Na, K and Cl in the world's order |
| `s` | [T, cell] | The regulatory state s1 |
| `a_eff` | [T, cell] | The population's effective availability, a_sched × (0.1 + 0.9 s1) |
| `V0_V`, `background_fmol` | {cell: float} | The start: −60 mV, and the background charge that gives it |

## `a5pp.floor(world, constants)`

The reference's own error, by `cells_reference.floor`: the maximum differences of V, the amounts,
s, U, F, a_eff and the currents between rtol 1e-10 and 1e-12.

## `a5pp.controls(world, constants)` and `a5pp.stand_in(world, dt, constants)`

`controls` gives each planted control's maximum deviation (V_V, amounts_fmol, s) from the
reference. `stand_in` gives the honest second-order stand-in's V_V, amounts_fmol and s at the
record times for one dt.

## Registered values and design

- `designs/fr6_a5pp_values.json` holds `reference` on the registered world.
- `designs/fr6_a5pp_design.json` holds:
  - the reuse statement and the claims;
  - the floor;
  - the controls, and the stand-in's errors and orders per dt;
  - the margins and `caught_at_margin_10`;
  - the zero-power and not-covered lists.
- `OPENBLAS_NUM_THREADS=1 python -m validation.fr6.references.design --check` regenerates both and
  compares them (about 20 s).
