# Using FR-2's references: interface only

This note says how a comparison reads the registered values, without reading their source.

**Files:**
- Inputs: `reference_inputs.json`, the declared worlds frozen with their provenance, plus the two
  stress worlds.
- Values: `designs/membrane_trafficking_reference_values.json`.
- Plants, floors and primary comparisons: `designs/membrane_trafficking_reference_design.json`.

The registration is in `README.md`.

**Rule:** the engine builds its worlds from the declared inputs (its own fixtures) and the stress
worlds from `reference_inputs.json` → `stress_worlds`. It never builds them from the values.

**Environment:** `/mnt/workspaces/Cells/venv-cpu/bin/python` with `PYTHONPATH` at the checkout.
The values are deterministic 50-digit strings: read them with `decimal.Decimal`, or `float` for a
float64 comparison.

## Units and signs

**Units:**
- fmol, pL, mM (fmol/pL), m², F, V, s;
- energies in pJ: 1 fmol × 1 J/mol = 1e-3 pJ;
- charges in C.

**Constants:** the exact SI values, F = N_A e and R = N_A k_B, with CHARGE_PER_FMOL = F × 1e-15.

**Voltages and charges:**
- V = φ_inside − φ_outside.
- A free node's charge is its declared anchor plus CHARGE_PER_FMOL Σ z (n − n0).

**The electrode transfer** at a held node (`electrode_C`) is the change of its plates' charge:
- +dC V_k on retrieval from its patch;
- −dC V_b on recycling into it;

with V taken before the stage. This is the engine's `electrode_charge_transferred_C`, and §13
confirms the sign. `electrode_abs_C` is Σ over stages of |transfer|. It is meant for
`trafficking_image_charge_C` ("the absolute clamp transfer booked", §3), but that mapping is
unconfirmed: §13 did not say whether the absolute value is taken per stage or of the half-step's
sum. The two agree on one-direction half-steps.

**Supply and work:**
- `supplied_fmol` is the reservoir supply per held node and species (positive into the system).
  `supplied_charge_C` = CHARGE_PER_FMOL Σ z × supplied, and `electrode_plus_supplied_charge_C` is
  0.
- `moved_into_fmol` is the net amount of carriers moved into each outside node, held or free
  (`trafficking_carrier_fmol`).
- `W_res_pJ` = 1e-3 Σ supplied × (RT ln c_ref + z F φ_h), and `W_elec_pJ` = φ_h × transfer × 1e12.
- `W_carriers_pJ` = ΔG_chem − Σ supplied × RT ln c_ref × 1e-3 (`trafficking_work_pJ`).
- ΔG_chem = RT Σ n (ln(n/V) − 1), over the cells and the free outside nodes, with n/V in mM.

## Drives: `values["drives"][key]`

**The key** is `world:test`, the test being the declared test's name after `::`, for example
`held_bath_cell:test_retrieval_moves_only_the_pool_into_its_closed_form[held bath]`. A stress drive
is keyed `stress_held_bath:retrieval`, and so on.

**Drive-level fields:**
- `world`, `test`, `H_s` and `start` (the state before the first half-step);
- `N0_plus_R0`;
- `pool_patch`, `plasma_patch`, `pool_nodes`, `owner`, `outside` and `outside_held`;
- `half_steps`, a list holding one record per half-step, in order.

**Each half-step record:**

| Field | What it holds |
| --- | --- |
| `rates_m2_per_s` | the half-step's retrieval and recycling rates per route |
| `stages` | each stage's report: its routes (dA, dC, V_source, V_destination, the carriers, the closed-form heat, the first-order term, the heat share, the per-route carriers' work), its bookings, and its potentials after |
| `sums` | the half-step's totals, as the tests read them (below) |
| `after` | `potentials_V`, `voltages_V`, `patches` (area, capacitance), `amounts_fmol` (free outside nodes), `units`, `records` (keyed `route/population`) and `energy_pJ` |
| `potential_change_V` | φ after − φ before, per node |
| `max_abs_potential_V` | max\|φ\| before |
| `closed_forms` | for a one-direction, single-route half-step: `kind`, `dA_m2`, `dC_F`, `V_b_after_V` or `V_k_after_V`, `heat_pJ`, `electrode_C`, and on retrieval `R1_shift_V`, `R1_potentials_V`, `R1_potential_change_V`, `R1_V_b_after_V` and `no_valence_potentials_V` |
| `floors` | per storage model (`absolute_storage`, `increment_storage`): `potential_change_V`, `potential_after_V`, `voltage_before_V`, `voltage_after_V` and `heat_rel`. Then `T6`, per ΔG model (`naive_difference`, `stable_change`): `residual_pJ` and `W_carriers_pJ`. Then `units_rel` |
| `T3` | `N_plus_R_minus_N0_plus_R0`, `dA_sum_by_cell_m2`, `dC_sum_by_cell_F` |
| `plant_swapped_t_W_carriers_pJ` | the carriers' work with each route's two transference numbers swapped |

**`R1_shift_V`** is the closed form V_k dC/(C_k − dC). At a held bath, the owner's potential moves
by it. At a free node, the outside node moves by its negative (`R1_potential_change_V`).

**`sums`:**
- `dG_chem_pJ`, `dU_view_pJ`, `heat_dense_pJ`, `heat_closed_pJ`;
- `W_res_pJ`, `W_res_closed_pJ`, `W_res_without_phi_pJ`, `W_elec_pJ`, `W_elec_closed_pJ`;
- `W_carriers_pJ`;
- `electrode_C`, `electrode_closed_C`, `electrode_abs_C`;
- `supplied_fmol`, `supplied_charge_C`, `electrode_plus_supplied_charge_C`, `moved_into_fmol`;
- `heat_by_route_pJ` (§4's share), `W_carriers_by_route_pJ`;
- on the shared cleft, `cleft_dG_pJ` and `cleft_shares`;
- `residual_pJ`, `max_term_pJ` and `residual_band_pJ` (1e-9 max|term| + 1e-18 pJ).

## How each test compares

**T4.**
- On a retrieval half-step, compare every potential but the pools' with the start, and V_b′ with
  `closed_forms.V_b_after_V` (or `after.voltages_V[pool_patch]`; they agree at 60 digits).
- On a recycling half-step, compare V_k′ with `closed_forms.V_k_after_V`, and V_b with its start.
- Compare the single route's booked heat with `closed_forms.heat_pJ`.
- The band is max(the test's tolerance, 10 × the floor), with the floor under the engine's
  storage model. Until that model is known, use `absolute_storage`, the conservative one.
- The floors are in `design["floors_by_half_step"]["key #n"][model]` (n counts from 1).
  `design["floor_flags"][model]` lists where a floor exceeds its tolerance.
- The R1 variant: compare the owner's or the cleft's shift with `R1_potential_change_V`.

**T5.**
- `values["T5"]["cycle_operator"]["half_steps"][i]` holds N, R, A_k and A_b after each half-step,
  their closed forms, and the plants' relative deviations.
- `values["T5"]["both_directions"]["populations"]["kir_0"]` is the primary population (§13).
  `nav_0` is an extra. For n = 8, 16, 32 and 64 it holds:
  - the exact N and R at 4 ms, with the quadrature and Richardson checks;
  - `palindrome` and `lie`, each with N, R, `rel_error` and `ratio`.

  The engine's own N at n = 8 and 16 compares with `palindrome.N`, within its float64 floor (about
  1e-14 relative).
- `compiled_cycle.observations` and `batch[r].observations` hold, at each observation time, N, R,
  A_k, A_b, C_k, C_b and N + R.

**T6.**
- The per-half-step terms are the `sums`. Each engine booking is compared with its reference.
- The residual against `residual_band_pJ`.
- The carriers' work within the larger of 1e-6 relative and 1e-15 max|term|.
- Each of those bands is widened to 10 × its floor, under the engine's ΔG model. Until that model
  is known, use `naive_difference`, the conservative one.
- The floors are in `floors_by_half_step[...]["T6"]` and `hs["floors"]["T6"]`.
  `design["floor_flags"]["T6 naive_difference"]` and `design["floor_flags_carriers"]` list where
  they exceed the test's bands.
- On the two-route world, `W_carriers_by_route_pJ` and `cleft_shares`.

**T3.** Compare `N0_plus_R0` and the `T3` sums. They are 0 within 1e-45 here.

**T8.** For each Kir population, `values["T8"]["populations"][kir_i]` holds:
- `start_m2`, the start in m²;
- `start_superseded_units`, §12's superseded ½ × availability × N0, for the record only;
- `observations[j]`, with `factor_m2`, `start_times_A_over_A0_m2`, `A_over_A0`, `N`, `abundance`,
  `plant_no_coupling_m2` and `plant_no_retrieval_m2`.

**Plants.** `design["plants"][name]["rows"]` gives each case's deviation, its band and the margin,
which is their ratio. `weak_at` lists the cases below 10 bands. Each weak case is in the README's
zero-power list.
