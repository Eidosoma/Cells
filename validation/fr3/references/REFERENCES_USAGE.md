# Using FR-3's references: site occupancy (interface only)

How to run the independent references for FR-3's items Q1 to Q5 on the registered worlds, and
how to read their outputs without reading their source.
- **Sources:** `docs/SITE_OCCUPANCY_DESIGN.md` Appendix A (A.1–A.5) and §8.3.
- **Worlds:** `reference_inputs.json` beside this note, written by `worlds.py` and registered.
- **Not read:** the engine (`src/`), the operator's tests and fixtures, and the FR owner's
  branches.
- **Registered design:** `README.md` and `designs/`.

**Environment.** `/mnt/workspaces/Cells/venv-cpu/bin/python`, on the CPU. The references are
deterministic and use NumPy, SciPy and the standard library only; nothing imports `cells`.
`api.reference` takes 1 to 5 s per world: Radau, DOP853 and the ledger in decimals. All 25 worlds
take about a minute.

```python
import json
from validation.fr3.references import api

inputs = json.load(open("validation/fr3/references/reference_inputs.json"))
r = api.reference(inputs["worlds"]["q1_eps_1e-1"])
acc = api.accessibility({1.0: inputs["worlds"]["q4_alpha_1_low"],
                         0.5: inputs["worlds"]["q4_alpha_1_2_low"],
                         0.25: inputs["worlds"]["q4_alpha_1_4_low"]})
```

## The worlds (`reference_inputs.json`)

| Key | Meaning |
| --- | --- |
| `units`, `constants`, `conventions`, `ligand` | As the FR lane's files give them. The ligand is neutral and impermeant; its `trace_mM` is 1e-12, at or below 1e-6 K_d |
| `dt_ladder_s` | 1, 0.5 and 0.25 ms |
| `worlds.<id>.items` | The §8.3 items it serves (Q1–Q5) |
| `worlds.<id>.nodes` | `cell` or `finite_outside`, each with `volume_pL` and the ligand's `L_mM`, the trace included |
| `worlds.<id>.populations` | `owner` (`cell`, `orientation` outward or inward, `faces_node`), `copies`, `sites_per_copy`, `accessible_fraction`, `association_rate_per_mM_per_s`, `dissociation_rate_per_s`, `initial_occupancy`, `internalisation` (null or `{rate_per_s, destination: "cell"}`) |
| `worlds.<id>.site_controls` | Epochs `{time_s, binding: {population: m_b}, internalisation: {population: m_i}}`, each held from its time on |
| `worlds.<id>.record_times_s`, `end_s` | The records, t = 0 included |

Every world is face-free. A population's patch is the only link between its cell and the node
it faces: there is no face and no held bath, and none of the worlds has a bath schedule.

## `api.reference(world)`

Arrays are [T, nodes] or [T, populations], in the orders `nodes` (sorted) and `populations`
(declared).

| Key | Meaning |
| --- | --- |
| `times_s`, `nodes`, `populations`, `sites_fmol`, `K_d_mM` | The layout, S = α ν N / N_f, and K_d = k_off/k_on |
| `n_fmol` | The ligand's amount at each node (cells and finite nodes) |
| `B_fmol`, `R_fmol`, `occupancy` | The bound and free sites, and B/S |
| `internalised_fmol` | Each population's cumulative internalised amount |
| `heat_pJ`, `work_pJ` | A.3's heat and work along the path, from t = 0 |
| `<key>_floor` | |Radau − DOP853| + ½ ulp, for each of the six above |
| `ledger_residual_pJ` | Δ(Σ G_node) + Δ(Σ G_site) + H − W at each record: rounding of the nodes' free energy |
| `equilibrium` | For one closed node with binding only: R-eq's `c_mM` and `B_fmol`, and `heat_to_equilibrium_pJ` = G(start) − G(eq) |
| `riccati` | For one population on such a node: A.4's `B_fmol` and `n_fmol` (exact for the world), and `B_eq_fmol` (the depletion quadratic's r₋) |
| `depletion_term` | For one population: S/(V (K_d + c₀)), the fixed-c forms' distance from the world |
| `fixed_c` | The reference side's large-V limits: `association_B_fmol` and `dissociation_B_fmol` (binding only), or `internalisation_B_fmol` and `internalised_fmol` |
| `qss` | For one population with internalisation started at its quasi-steady occupancy: `n_fmol` by D150's saturable law, with `epsilon`, `K_M_mM`, `a_fmol_per_s` = k_int S, `b_fmol` = K_M V, and `relative_error_over_uptake` (R-ode against R-qss, over the uptake) |

## `api.accessibility({alpha: world})`

Q4's three worlds at one concentration. It returns `theta_ratio` {α: B_eq(α)/B_eq(1)}, by R-eq at
the true V, and `relaxation_rate_per_s` {α: k_on c_eq + k_off}.

## Registered values and power

- `designs/fr3_reference_values.json` holds `api.reference` on every world. Long arrays keep every
  k-th record and the last, and floors keep their largest value.
- `designs/fr3_reference_design.json` holds:
  - the claims;
  - the honest SSPRK(3,3) stand-in on the ladder (`power.ladder_stand_in`);
  - each planted control's deviation (`power.controls_fmol`) and the ceilings;
  - Q4's ratios with the (K) and (A) controls;
  - the order in ε;
  - the energy controls;
  - the readings and notes.
- `OPENBLAS_NUM_THREADS=1 python -m validation.fr3.references.design --check` regenerates every
  file and compares them, exit 0 when they agree. It takes about three minutes.
