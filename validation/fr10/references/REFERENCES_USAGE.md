# Using FR-10's references: R-faces, R-ion and R-records (interface only)

How to run the independent references for FR-10's scheduled bath composition, and how to read
their outputs without reading their source.
- **Sources:** `docs/BATH_SCHEDULE_DESIGN.md` Appendix A, §2.2 and §2.3, and the FR lane's
  `reference_inputs.json`, copied unchanged beside this note.
- **Not read:** the engine (`src/`), the operator's tests and fixtures, and the FR owner's branch
  beyond the inputs file.
- **Registered design:** `README.md` and `designs/`.

**Environment.** `/mnt/workspaces/Cells/venv-cpu/bin/python`, on the CPU, single-threaded. The
references are deterministic and use NumPy, SciPy and the standard library only. Nothing imports
`cells`.

| Call | CPU time (one core) |
| --- | --- |
| `faces.reference` | about 0.05 s |
| `ion.reference` | about 4 s (Radau dominates) |
| `records.event_records` | about 0.01 s per world |
| `records.reconciliation_K` | about 0.05 s for 301 records |

## Calling them

```python
import json
from validation.fr10.references import faces, ion, records

inputs = json.load(open("validation/fr10/references/reference_inputs.json"))

f = faces.reference(inputs["R_faces"])                       # R-faces, W1
i = ion.reference(inputs["R_ion"], inputs["constants"])      # R-ion, W2
w1 = records.event_records(inputs["R_records"]["worlds"]["W1"], inputs["constants"])
K3 = records.reconciliation_K(inputs["R_records"]["worlds"]["W3"], times_s, {"S": S_fmol},
                              inputs["constants"])
```

- **The arguments** are the inputs file's own blocks, as a plain `json.load` returns them.
  `inputs["constants"]` is checked: each of `avogadro_per_mol`, `elementary_charge_C` and
  `boltzmann_J_per_K` must be the exact SI value, or the call raises `ValueError`. The references
  then use the exact values, F = N_A e and R = N_A k_B. The argument may also be omitted, which
  gives the same exact constants.
- **Refusals** raise `ValueError`, naming the problem. They cover an event at or before t = 0;
  times that do not increase; a nonpositive concentration, volume or conductance; species that
  differ between the bath, the cell and the valences; a node with no path to the bath; and an
  event time missing from K's record times.

## `faces.reference(block)`: R-faces (A.2, B1)

The block is the inputs file's `R_faces` layout: `finite_nodes`, `faces` (each with `between`,
`area_m2`, `length_m` and `<species>_diffusivity_m2_per_s`), `bath` (with `declared_mM` and
`events`, each event's composition being absolute) and `record_times_s`. The species is read from
the nodes' `<species>_mM` keys.

| Key | Layout | Meaning |
| --- | --- | --- |
| `times_s` | [T] | The record times, as given |
| `nodes` | [N] | The finite nodes, in the block's order (`["ecs_0", "ecs_1"]`) |
| `species` | str | The face species (`"S"`) |
| `amount_fmol` | [T, N] | Each node's amount (fmol): the exact solution, per epoch |
| `floor_fmol` | [T, N] | |primary − SciPy `expm`| + 16 ulps of the largest amount in play: the reference's own error bound |
| `amount_expm_fmol` | [T, N] | The second method's values |
| `supply_fmol` | [T] | S(t) = Σ_i (n_i(t) − n_i(0)), the bath's cumulative supply (fmol, out of the bath) |
| `supply_floor_fmol` | [T] | Its floor |
| `kappa_pL_per_s` | {face id: float} | κ = 1e15 D A / L |
| `rates_per_s` | [N] | The relaxation rates, the eigenvalues of V⁻¹L, ascending |
| `volume_pL` | [N] | The node volumes |

The solution does not depend on dt. A record at an event time returns the epoch's start, since
amounts are continuous.

## `ion.reference(block, constants)`: R-ion (A.3, B2)

The block is the inputs file's `R_ion` layout: `temperature_K`, `species` (the valences), `cell`
(`volume_pL`, `amounts_fmol` and `initial_charge_C`), `wall` (`area_m2`, `capacitance_F` and
`permeability_m_per_s`), `bath` and `record_times_s`. V_m(0) = initial charge / capacitance.

| Key | Layout | Meaning |
| --- | --- | --- |
| `times_s` | [T] | The record times |
| `V_m_V` | [T] | The cell's potential less the bath's (V) |
| `amount_fmol` | {species: [T]} | The cytosol's amounts (fmol): Na, K, Cl and S. Impermeant species are the inputs' values, exactly |
| `floor` | `{"V_m_V": [T], "amount_fmol": {species: [T]}}` | The larger of |DOP853 − Radau| and QUADPACK's time residual, plus ½ ulp |
| `V_m_radau_V` | [T] | The second method's V_m |
| `supply_fmol` | {species: [T]} | S_s(t) = n_s(t) − n_s(0), the cell's gain: the bath's cumulative supply to the cell (fmol, positive out of the bath) |
| `event_times_s` | [E] | The events, in order |
| `zero_current_V` | [E] | Reading (a): the zero-current constant-field potential at the cytosol's composition at each event, with the new bath (the Nernst potential with one permeant ion) |
| `zero_current_floor_V` | [E] | Its floor (decimal against a float64 root) |
| `limit_V` | [E] | Reading (b): the epoch's own limit, on the charge invariant; `None` with several permeant species |
| `limit_floor_V` | [E] | Its floor |
| `V0_V`, `rest_V_declared`, `rest_floor_V` | float | V_m(0), and the zero-current potential at the declared composition |
| `scalar_reduction` | bool | True when one ion is permeant (the scalar method is used) |

With several permeant species, the primary integrates the full state and readings (a) use the
GHK voltage equation for monovalent ions (otherwise a root).

## `records.event_records(world, constants)`: R-records per event (A.4, §2.2, B4)

`world` is one of `R_records["worlds"]` (W1, W2 or W3). It returns a list with one item per event,
bath by bath, in time order.

| Key | Meaning |
| --- | --- |
| `bath`, `time_s` | The bath and the event time |
| `dose_fmol` | {species: float}: dn_s = V_b (c′_s − c_s), exact in rationals and then rounded |
| `dose_exact` | {species: str}: the exact rational |
| `dG_b_pJ` | §2.2's free-energy change of the bath's content at V_b (pJ), in 50-digit decimals |
| `charge_C` | F · 1e-15 · Σ z_s dn_s (C): exactly `0.0` for a neutral step |
| `charge_exact`, `neutral` | The exact rational, and whether it is zero |
| `cumulative_dose_fmol`, `cumulative_dG_b_pJ` | Sums up to and including this event |
| `endpoint_dG_b_pJ` | G(held) − G(declared), in decimals: equals the cumulative dG_b |
| `floor` | `{"dG_b_pJ", "dose_fmol": {…}, "charge_C"}`: the float64 evaluation's difference plus ½ ulp |

## `records.reconciliation_K(world, record_times_s, supply_fmol, constants, bath=None, species=None)`: K(t) (A.5, §2.3)

- **`supply_fmol`** is the cumulative supply S_s at each record time: fmol, positive out of the
  bath into the tissue, zero at t = 0. Pass it as {species: [T]}, or as an array [T, S] with
  `species` naming its columns. A species left out contributes nothing.
- **Every event time must be a record time,** to 1e-12 s, or the call raises; nothing is
  interpolated. `bath` is needed only when the world has several baths.

| Key | Layout | Meaning |
| --- | --- | --- |
| `times_s` | [T] | As given |
| `K_pJ` | [T] | K(t) = 1e-3 Σ_{e ≥ 1, t_e ≤ t} Σ_s RT ln(c_s^e/c_s^0) (S_s(min(t, t_{e+1})) − S_s(t_e)), in decimals from the supplied doubles |
| `floor_pJ` | [T] | |decimal − the operator's float64 B form| + ½ ulp |
| `K_float64_pJ` | [T] | The B form: K = B + 1e-3 Σ_s (μ_s^now − μ_s^0) S_s, with B updated at each event |
| `event_rows` | [E] | The record index of each event |
| `delta_mu_J_per_mol` | [epochs] of {species: float} | μ_s^e − μ_s^0 = RT ln(c_s^e/c_s^0) (z F φ_b cancels) |

**K from the reference trajectories,** which checks the supply too:
- W1: `records.reconciliation_K(W1, f["times_s"], {"S": f["supply_fmol"]}, constants)`;
- W2: `records.reconciliation_K(W2, i["times_s"], i["supply_fmol"], constants)`.

## Registered values and power

`designs/fr10_reference_values.json` holds every output above on the registered inputs.
`designs/fr10_reference_design.json` holds the claims, the tolerance basis, each planted
control's deviation at each dt of the ladder (`power`) and the zero-power cases.
`python -m validation.fr10.references.design --check` regenerates both and compares them (exit 0
when they agree).
