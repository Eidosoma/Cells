# Using the core-seams references (seams A and C): interface only

This note says how to build test laws from the registered inputs, how to call the references, and
how to read their outputs without reading their source.
- **Sources:** CORE_SEAMS_DESIGN §3, §5, §16, §17 and §19.
- **Inputs:** `reference_inputs.json` beside this note, written by `worlds.py` and registered.
- **Registered design:** `README.md` and `designs/`.
- **Rule (§19 item 1):** the engine builds its synthetic test laws from the inputs (states, edges,
  rate expressions and constants), never from the values.

**Environment.** Use `/mnt/workspaces/Cells/venv-cpu/bin/python` on the CPU. The references are
deterministic. They use the standard library's `decimal` and `fractions` (60 digits), with NumPy
for the registered draws, and nothing imports `cells`. One state takes milliseconds; the whole
design takes about a minute: `python -m validation.core_seams.references.design --check`.

```python
import json
from validation.core_seams.references import api

inp = json.load(open("validation/core_seams/references/reference_inputs.json"))
A = inp["seam_a"]
law = next(l for l in A["laws"] if l["id"] == "d2_slip_exchanger")
rec = api.cycle_state(law, A["populations"][law["id"]], A["registry"],
                      A["states"][law["id"]][0], A["volumes_pL"])
C = inp["seam_c"]
s = C["systems"]["S4"]
st = C["manufactured_states"]["S4"][0]
out, _sp, _sy = api.binding_state({"ligands": s["ligands"], "binders": s["binders"]},
                                  C["registry"], st["totals"], s["volume_pL"])
```

## Conventions (`reference_inputs.json` → `conventions`, `units`, `constants`)

**Units:**
- fmol, pL, mM (= fmol/pL), V, s, J/mol;
- energy in pJ (1 fmol × 1 J/mol = 1e-3 pJ);
- current in pA (1 fmol e/s = F × 1e-3 pA);
- conductance in pS.

The constants are the exact SI values, F = N_A e and R = N_A k_B, and T = 310 K.

**Potentials:**
- activity a = c/c° with c° = 1000 mM;
- μ̃ = μ° + RT ln a + z F φ_e;
- ΔG_m = Σ ν_{s,e} μ̃_{s,e} over the mode's rows (species s at law end e, N or P). ν is the change
  of each row per forward cycle.
- No law carries a ΔG° of its own.

**Host:**
- A population lies on a patch with ends a (its cell) and b (the outside node), and V = φ_a − φ_b.
- `orientation.N` names the host end that is N. Every registered population has N = a except
  amendment 1's `d2_slip_exchanger_Nb`, which has N = b: its law reads N at b, and
  φ_N − φ_P = φ_b − φ_a.
- Concentrations are the free values a stage read gives: a buffered node's free form, or an
  unbuffered row's concentration.

## Seam A's inputs (`seam_a`)

| Key | Meaning |
| --- | --- |
| `registry` | `temperature_K`, `standard_concentration_mM`, `species` {valence, mu0_RT}, `moieties` {name: {species: content}} |
| `laws` | The laws the engine runs (below). `planted_laws`: the Wegscheider plants, each built on the base law its id begins with (`plant_states` maps it). `parse_plants`: modes to refuse, and one control |
| `states` | {law id: [host states]}. Each has `phi_V` {a, b}, `c_mM` {a: {...}, b: {...}} and a `tag` (`random_k`, `near_<cycle>_<ΔG/RT>`, `far_*`, `static_head_*`, `band*`, `unit_activity_zero_voltage`) |
| `populations` | {law id: {capacity_fmol_per_s, availability, orientation, held_rows}} |
| `volumes_pL` | {a: 2.0, b: 0.25}, for the material slopes |
| `generic_states` | {diagram id: d + 1}. The first d + 1 states of that law are its generic set, of full rank in (1, ln a, ψ) |
| `amendments` | The dated amendments: amendment 1 added `ff_neutral_n1` (finite fuel: no `held_rows`, so ATP, ADP and Pi are moved rows) and `d2_slip_exchanger_Nb` (N = b) |

**Diagram laws** (`kind: "diagram"`) have these fields:
- `states`: names;
- `edges`: each with `from`, `to`, `fwd` and `bwd`. A rate is α = k0_per_s × Π a_{s,e}^order ×
  exp(ζ ψ), with ψ = F(φ_N − φ_P)/RT. `orders` are [species, end, order], and ζ_fwd − ζ_bwd is the
  charge the edge moves N → P;
- `cycles`: every Hill cycle of the diagram. Each has `edges` [edge id, ±1] in its + direction, and
  `nu` [species, end, ν];
- `rate_scale_per_s` ω: S_κ = j⁺_κ/ω, and the capacity k = N_carriers ω.

A cycle's flux is J_κ = k a S_κ (1 − e^{ΔG_κ/RT}), with J⁺ = k a S and J⁻ = J⁺ e^{ΔG/RT} (§16).

**Factored laws** (`kind: "factored"`) are the version-1 laws. Each carries its `law_id`, its
`parameters` and one mode with:
- `nu`;
- `saturation`: [{species, end, K_mM, hill}], giving S = Π [1 + (K/c)^hill]^-1;
- optionally `planted_S_offset`, which is subtracted from S.

**Net-flow laws** (`kind: "net_flow"`) are the guard's plants and control. A mode's flux is
J = a Σ_t k_t (1 − exp(ΔG_t/RT + ε_t ψ)) over its `flux_terms` (capacity_fmol_per_s, cycle_nu,
shift_psi). They expose no one-way fluxes.

## Seam C's inputs (`seam_c`)

| Key | Meaning |
| --- | --- |
| `registry.species` | Ligands {valence, mu0_RT} |
| `registry.binders` | {binder: {base_valence, forms: [{id, counts {ligand: n}, mu0_RT}]}}. The first form is the base. Counts are integers relative to the base and may be negative. A form's charge is z_base + Σ n z_L |
| `systems` | {S: {ligands, binders, volume_pL, designated (the form the plants act on), parts (S5's disjoint sets)}} |
| `manufactured_states` | {S: [{tag, free_mM, binders_mM, totals {ligands_fmol, binders_fmol}}]}. **The totals (doubles) are the inputs**; the free values are how they were made |
| `p1_nodes` | {P1a, P1b}: a system, `volume_pL`, the `ligand` a route draws, and its `totals` |
| `movers` | [{id, declares_base_forms, nu, expected}] for the forms check (§5.2) |

The equilibrium of form f is c_f = c_base β_f Π (x_L/c°)^{n_{L,f}}, with
ln β_f = μ°_base/RT + Σ n μ°_L/RT − μ°_f/RT. A ligand row holds the free ligand plus Σ n_{L,f} c_f V,
counted from each base form.

## Outputs

**`api.cycle_state(law, population, registry, host_state, volumes_pL)`**, as recorded in
`values.seam_a.laws.<id>.states[k]`:

| Key | Meaning |
| --- | --- |
| `modes.<cycle>` | `dG_RT`, `dG_RT_terms_abs` (Σ \|terms\| of ΔG/RT, for rounding bounds), `S`, `J_plus`, `J_minus` (= J⁺ e^{ΔG/RT}), `J` (fmol/s), `J_scale` (J⁺ + J⁻); for diagrams also `Pi_plus` and `Pi_minus` (per carrier, s^-L), `sigma_share` (Σ_κ/Σ) and `J_minus_diagram` (k a Π⁻ Σ_κ/(Σ ω)) |
| `edges.<id>` | Diagrams only: `alpha_fwd_per_s`, `alpha_bwd_per_s`, the one-way edge fluxes per carrier `oneway_fwd_per_carrier_per_s` (p_i α_ij) and `oneway_bwd_per_carrier_per_s`, and `net_fmol_per_s` for the population |
| `occupancy`, `carrier_scale_fmol` | Diagrams only: the steady-state probabilities, and k a/ω |
| `rows_fmol_per_s` | {"species@host end": Σ ν J} for moved rows |
| `held_supply_fmol_per_s` | The maintenance's supply per held row, −ν J |
| `heat_pJ_per_s`, `work_pJ_per_s` | −Σ J ΔG, and −Σ J ΔG over the held rows |
| `stored_standard_pJ_per_s` | Σ J ν μ°' over the moved rows, in @3's 1 mM frame: μ°' = μ° − RT ln c° (c° in mM) |
| `charge_a_to_b_fmol_per_s`, `current_a_to_b_pA` | The charge moved a → b |
| `guard_total_pJ_per_s` | Σ_m J_m ΔG_m, the population guard's quantity |
| `slopes` | `dJ_dV` per mode (fmol/(s V), host V); `conductance_pS` (∂I_{a→b}/∂V); `material` {"row": {row_self_slope_per_s (∂ row rate/∂ n_row), max_mode_slope_per_s (max_m \|ν ∂J_m/∂n_row\|)}}, both 1/s |

**`values.seam_a.wegscheider.<law>`** gives the reference's `verdict` and `reasons`, and per cycle:
- the exact affine residual r = r0 + Σ b_{s,e} ln a_{s,e} + b_ψ ψ (`r0`, `b`, `b_psi`, `b_psi_exact`);
- `structurally_zero`;
- `r0_over_terms_eps`;
- `residual_at_states`: the 50-digit r at the base law's states, in order.

**`values.seam_a.parse.<law or plant>.<mode>`**: `charge_sum`, `moiety_sums`, `n_q` and `admitted`.

**`api.binding_state(spec, registry, totals, V)`**, as recorded in `values.seam_c.systems.<S>.states[k]`:

| Key | Meaning |
| --- | --- |
| `x_mM`, `free_fmol`, `forms_mM` | The free ligands, and every form's concentration ({binder: {form: mM}}) |
| `residual_scale_fmol`, `residual_rel`, `totals_over_scale` | Amendment C2: V A_L, with A_L = x_L + Σ \|n\| c (the convergence scale); \|g_L\|/(V A_L); and \|T_L\|/(V A_L), which is 1 wherever every count is ≥ 0 |
| `conservation_rel` | Each row's reconstruction error (~1e-50) |
| `charge` | `species_fmol_e`, `totals_fmol_e` and their difference |
| `G_star_pJ` | Σ n (μ° + RT(ln(c/c°) − 1)) over the free ligands and every form |
| `potentials_J_per_mol` | ∂G*/∂T per row: the free ligand's, and each binder's free base form's |
| `own_terms_pJ`, `speciation_part_pJ` | Σ over the rows as single base-form species, and G* minus it (null where a total is ≤ 0). **Not the booked term** (§19 item 3) |
| `floor_input_rounding`, `floor_residual_1e-13` | {x: {ligand: \|δ ln x\|}, forms: {"binder\|form": \|δ ln c\|}}: from ½ ulp on every input, and from a residual \|g_L\| ≤ 1e-13 V A_L (amendment C2). Compare solutions against the second |
| `manufactured_dln` | The registered solution against the manufactured free ligands |
| `gradient_vs_differences_rel`, `newton_vs_bisection_rel` | Where computed (two states per system and every hard state) |
| `booked_term` | Amendment C1, the closure's booked term in both splits. It holds `E_c_pJ` (= G* − Σ_r T_r μ°′_r) and `S_c_pJ` (= E_c − Σ ideal_r, = `speciation_part_pJ`; null where a total is ≤ 0). It also holds `ideal_rows_pJ` and `ideal_total_pJ` (@3's RT T (ln(T/V) − 1); null at T ≤ 0), `standard_parts_pJ` and `standard_total_pJ` (T μ°′ with μ°′ = μ° − RT ln c°, c° in mM), `B4_term_pJ` (S_c + Σ_B T_B μ°′_B), `identity_residual_pJ`, `gradient_at3_J_per_mol` (∂E_c/∂T_r = RT ln(c_free/1 mM)), and `terms_abs_pJ`, for rounding floors. A world-level check: the closure's phase-1 term (S_c) plus @3's ideal terms on its rows equals `E_c_pJ` |
| `primal` | Amendment C1, the second route (`primal.py`): `max_abs_dln_vs_dual`, `certificate` (max formation \|ΔG/RT\|) and `iterations` |
| `E_c_gradient_vs_differences_abs_J_per_mol` | Where computed |

**`values.seam_c.systems.<S>.pairs`** (amendment C1): consecutive states (k, k + 1), each with
`dE_c_pJ`, `dS_c_pJ`, `floor_pJ` (8 eps of both states' terms) and `plants_pJ`. The plants are
G* booked whole, B4's formula on moved binders, and S_c alone with @3's ideal terms masked, each
the exact amount by which that booking misses ΔE_c.

**`values.seam_c.p1.<node>`** (amounts in fmol; divide by |J| for θ·dt in s):
- `n_free_fmol` and `stored_fmol`;
- `admissible_floor_fmol` (Σ T_B min n, which is negative with a form below its base);
- `dfree_dstored`;
- `threshold_free_fmol`, the point where today's predictor turns negative;
- `threshold_stored_fmol` (T − floor) and `threshold_linearised_free_fmol`, with their ratios to
  n_free;
- `ladder`: after drawing k × n_free, the equilibrated free amount, today's predictor and the
  linearised free amount.

**`seam_c.envelope`** (amendment C3, inputs). It gives `budget_pH` (1e-3, B4's) and
`planted_unreachable_binders`. Each case under `cases.<id>` gives:
- `ligands`, `binders`, `volume_pL`, the free values it was made from, and `totals`;
- `kon_per_mM_per_s`: [binder, ligand, k_on] for every (binder, ligand) pair;
- `drive_fmol_per_s`: [ligand or binder, rate]. A binder's drive adds its base form;
- `record_slow_times`, in units of the network's slowest relaxation time.

**`values.seam_c.envelope.cases.<id>`** holds:
- `species`, `closure_fmol`, and the `steps` with their `K_r_mM` and B4's `lambda_per_s`;
- `slowest_network_rates_per_s` and `min_step_rate_per_s`;
- `first_order_dln` {L: Δ ln x_L} and `first_order_pH`;
- `per_step_estimate_dln`, the plant: min over all steps, or over the ligand's own steps;
- `per_step_pH`, and `b4_formula_pH` for E0;
- `kinetic.rows`: per record time, `lag_dln`, `first_order_dln` at that state and `floor_dln`
  (|Radau − BDF|);
- `plants` {name: {L: relative deviation}} and `first_order_floor_rel`;
- `kinetic_vs_first_order_rel` at the last record.

`values.seam_c.envelope.reachability` {binder: verdict}.

**`values.seam_c.validity`** (amendment C4):
- **`systems.<S>`:** per registered state, `t_star_fmol`, `t_star_exact` (a rational),
  `lambda_star`, `per_ligand_fmol` (t at λ = e_L), `valid`, `per_ligand_valid` and
  `lp_t_star_fmol`.
- **`planted.<tag>`:** the same, with the `dual` and `primal` outcomes (solved, with `x_mM`, or
  refused, with a reason).

A state is valid iff t* > 0. The closure's validity report must agree, and the per-ligand floors
alone must not decide it.

**`values.seam_c.movers.<id>`** gives `verdict` and `reasons`. **`values.seam_c.parse`** gives
`form_valences` and the planted declared valence.

## Registered power

`designs/core_seams_reference_design.json` holds the power:
- **`power.A1_*` to `power.A7_*`** and **`power.C*`**. Each plant row records its largest margin
  over the states (its deviation in floors at each state), where that falls, its smallest, and
  `weak_at` (the states below ten floors).
- **`zero_power`**: each blind spot, why, and its remedy.
- **`readings`**: the findings.

**The floors:**
- **Seam A's J, rows, heat and work:** the honest float64 rounding (J⁺ + J⁻) × (ΔG/RT's terms + 8)
  eps, built from the recorded `J_scale` and `dG_RT_terms_abs`. It is absolute, because near
  equilibrium a relative floor does not exist. **A comparison of J near equilibrium needs an
  absolute tolerance built from those two fields**, not a relative one.
- **Seam A's one-way fluxes and slopes:** (terms + 8) eps, relative.
- **Seam C's free forms:** `floor_residual_1e-13`.

A tolerance has power where it lies below a plant's largest margin over ten floors, and above ten
floors. For seam A's rounding bands that is §19 item 2's.

**Zero cases: an absolute floor** (amendment F4). Compare every pair absolutely, |x − y| ≤ 10 τ,
with τ built from the computation's term sums, never relatively with the zero pairs skipped:
- **A slope** (`api.slope_pairs`) has τ = (terms + 8) u M/h, with u = ½ 10^(1 − PREC) and M the
  differenced function's magnitude. A neutral law's conductance has τ = 0 and must be exactly 0.
- **The diagram's two routes** (`api.method_agreement`) have floors from the trees' positive
  sums and from the elimination's running error bound (`exact.det_running`,
  `exact.solve_running`).
- **The basis against the Hill total** (`api.basis_signs`) has a floor from both totals' terms.

An engine comparison where the reference value is exactly 0 takes the same form with its own
rounding floor. A floor of exactly 0 demands exact equality. A plant whose deviation is
undefined at a state (a zero reference) is weak there and is listed.
