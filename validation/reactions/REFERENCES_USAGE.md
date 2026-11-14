# Using the D152 reaction references (interface only)

How to feed the independent references for `local_species_reactions@1` and read their outputs,
without reading their source. They were written from Appendix A of
[SHARED_INVENTORY_REACTIONS_DESIGN.md](../../docs/SHARED_INVENTORY_REACTIONS_DESIGN.md), with §2.2,
§3.1–§3.4, §4.2 and §6.2–§6.4, and from textbooks. Their author never read the operator's code,
its tests or the design's prototype. Where a convention below is a reading of the design, it is
listed under [Readings](#readings-of-the-design-taken-here); disagreements go to the lead.

| Module | What it gives |
| --- | --- |
| `validation/reactions/network_reference.py` | The network declaration, rate laws and factors, the SSPRK(3,3) half-step with its stage condition, the node classes and bookings (the per-route hybrid), free energies, moieties, and a 50-digit evaluator of ΔG |
| `validation/reactions/dissipation_reference.py` | The exact node kinetics with their true heat and work (DOP853), passive equilibria, and the closed forms (turnover, Michaelis–Menten depletion, the passive ratio) |
| `validation/reactions/chain_reference.py` | The zero-flux chain's modes and eigenvalues, exact mode-wise propagation of linear networks, the engine order's linear step map, and a DOP853 integration of the nonlinear semi-discrete system |
| `validation/reactions/turing_reference.py` | MG0c: Schnakenberg as four mass-action reactions, the dispersion relation, d_c, the band, the fastest mode, the domain modes and the staircase |
| `validation/reactions/reference_crosschecks.py` | A driver that re-derives the design's development numbers and the tolerance evidence below (`--out DIR`; about 70 s) |

Self-tests: `tests/unit/test_reaction_references.py` (tier 1, about 6 s under the tier tool),
which also checks that nothing in this folder imports `cells`.

## Conventions

- **Units** (@3's): amounts fmol, volumes pL, concentrations mM (= fmol/pL), time s, energies pJ,
  diffusivities m²/s, lengths m. **RT is an input** in pJ/fmol: `nr.rt_pJ_per_fmol(R, T)` gives
  1e-3 R T for R in J/(mol K). Pass the engine's own value; 2.5773 (310 K) is used in the tests
  for orientation only.
- **`h` is the half-step, dt/2.** Every `h_s` argument of the node references is the length of
  one operator half-step, not the composite's dt. `chain_reference.strang_mode_map` and
  `transport_polynomial` take the full `dt_s`.
- **Axes.** Amounts are `[species, node]`, per-reaction arrays `[reaction, node]`, stage arrays
  `[stage, ...]` with stages Y1, Y2, Y3, and records `[record, ...]`. A 1-D amounts array is one
  node and comes back with a node axis of length 1. Species and reactions follow the order of the
  `Network` declaration.
- **Nodes.** The references do not distinguish cells from finite outside nodes. Concatenate the
  engine's cell and outside nodes along one node axis, with their declared volumes.
- **Routes.** The engine's flat route axis is a set of (reaction r, node i) pairs. Pass
  `sites[r, i] = True` where route (r, i) exists (default: every reaction at every node) and
  `multipliers[r, i] = m_r` at that site (`[R]` broadcasts). A route that is not sited is treated
  exactly as a multiplier of 0.
- **Inputs are never modified**; all outputs are new arrays.

## Declaring a network

```python
import math
from validation.reactions import network_reference as nr
net = nr.Network(
    species=(nr.Species("E", 0.0, {"E": 1}), nr.Species("S", 0.0, {"S": 1}),
             nr.Species("C", math.log(1e-3), {"E": 1, "S": 1}), nr.Species("P", 0.0, {"S": 1})),
    reactions=(nr.Reaction("bind", "passive", {"E": 1, "S": 1}, {"C": 1}, k_f_per_s=1e3),
               nr.Reaction("cat", "mass_action", {"C": 1}, {"E": 1, "P": 1}, rate_constant=1.0)),
    c0_mM=1.0)
```

| Class | Field | Units | Meaning |
| --- | --- | --- | --- |
| `Species` | `name` | – | Unique name. |
| | `mu0_RT` | – | Standard potential μ°/RT at c0 (default 0). |
| | `moieties` | – | `{moiety: integer count}`; `None` (default) means the species is its own moiety. |
| `Reaction` | `name`, `law` | – | `law`: `"mass_action"`, `"michaelis_menten"`, or `"passive"` (alias `"ideal_detailed_balance_mass_action@1"`). |
| | `reactants`, `products` | – | `{species: integer coefficient}`; an empty side is a source or a sink. |
| | `rate_constant` | mM^(1−q) s⁻¹ | mass_action's k, q = Σ α ≤ 3. |
| | `k_f_per_s` | s⁻¹ (at c0) | passive's k_f. |
| | `k_cat_per_s` with `catalyst` | s⁻¹ | michaelis_menten with a catalyst E (read, never a reactant or product). |
| | `V_max_mM_per_s` | mM/s | michaelis_menten without a catalyst. |
| | `K_M_mM` | mM | michaelis_menten's K_M; reactants must be exactly `{S: 1}`. |
| | `factors` | – | A tuple of `Factor`, on driven laws only. |
| `Factor` | `kind`, `species`, `K_mM`, `n` | –, –, mM, – | `"hill_activation"` x^n/(K^n + x^n) or `"hill_inhibition"` K^n/(K^n + x^n), x the species' concentration. |
| `Network` | `species`, `reactions`, `c0_mM` | –, –, mM | c0, the standard concentration (default 1 mM). |

`nr.compile_network(net)` validates and raises `nr.DeclarationError` for: unknown species;
non-integer or negative coefficients; Σ α > 3 (any law) or Σ β > 3 (passive); a reaction that is
not moiety-balanced and is neither a pure source (every ν ≥ 0) nor a pure sink (every ν ≤ 0); a
passive reaction that is open, has factors or changes nothing; michaelis_menten reactants other
than `{S: 1}`, a written catalyst, `k_cat` without a catalyst or `V_max` with one; non-positive
K_M, Hill K or n, k_f or c0; negative rate constants. These are the reference's own domain
checks. The engine's other refusals (charge, permeability, sites, schedules, the 7-species cap)
are not modelled. Every function accepts a `Network` or its compiled form; `compiled.role` gives
`"closed"`, `"source"` or `"sink"` per reaction.

## Node kinetics and bookings: `network_reference` (`nr`)

### `nr.rates(net, amounts_fmol, volumes_pL, multipliers=None, sites=None) -> Rates`

All fields are `[R, N]` except `consumption_rate`.

| Field | Units | Meaning |
| --- | --- | --- |
| `net` | fmol/s | J_r; passive routes in Appendix A's stable form (the engine's `reaction_rate_fmol_per_s`). |
| `forward`, `reverse` | fmol/s | J⁺ and J⁻ on passive routes; on driven routes J and 0. Exactly 0 where m = 0. |
| `affinity` | – (units of RT) | A_r = Σ α ln a − Σ β ln a − Σ ν μ°/RT on passive routes, 0 on driven ones (the engine's `reaction_affinity_RT`). It is reported whatever m is. |
| `factor` | – | F_r, the product of the route's Hill factors (1 if none). |
| `consumption_rate` | s⁻¹ | L_s `[S, N]`, the consumption per amount written with unidirectional fluxes. |
| `affinity_terms` | – | Σ α \|ln a\| + Σ β \|ln a\| + \|Σ ν μ°/RT\| on passive routes, 0 on driven ones: the scale of A's rounding. |

### `nr.half_step(net, amounts_fmol, volumes_pL, h_s, RT_pJ_per_fmol, multipliers=None, sites=None, theta=0.5) -> HalfStep`

One SSPRK(3,3) half-step of length h at every node, with its checks and bookings.

| Field | Shape, units | Meaning |
| --- | --- | --- |
| `start`, `end` | [S, N] fmol | n, and the candidate n′ = n + δ. At an idle node `end` is the start array's values, bitwise. |
| `accepted` | [S, N] fmol | `end` if `admitted`, else `start` (the composite keeps the start state). |
| `delta` | [S, N] fmol | δ = ν Δξ, computed once (Δn = ν Δξ by construction). What holds bitwise is `end == start + delta`. In floats `end − start` differs from δ by up to ε × `end`. |
| `extents` | [R, N] fmol | Δξ_r = h (J(Y1) + J(Y2) + 4 J(Y3))/6; 0 at idle nodes. |
| `gross_extents` | [R, N] fmol | h Σ_k b_k (J⁺ + J⁻)(Y_k), the scale for comparing extents (equal to Δξ on driven routes). |
| `stages` | [3, S, N] fmol | Y1 = n, Y2, Y3. |
| `stage_net`, `stage_forward`, `stage_reverse`, `stage_affinity` | [3, R, N] | J, J⁺ (or J), J⁻ (or 0) and A at each stage. |
| `end_net`, `end_affinity` | [R, N] | J and A at n′. |
| `hL` | [3, N] | h max_s L_s(Y_k) per stage and node (0 at idle nodes). |
| `hL_max`, `hL_argmax`, `L_max` | float, (stage, node), s⁻¹ | The largest h L, where it occurred, and hL_max/h. A step of dt ≤ 1/L_max would pass at these states. |
| `stage_condition_ok` | bool | h L ≤ θ (inclusive) at every stage of every non-idle node. |
| `positive_ok`, `finite_ok` | bool | Every species at every non-idle node > 0 (finite) at Y1, Y2, Y3 and n′; rates and h L finite. |
| `admitted` | bool | All three flags. A refused step's booking fields describe the refused candidate (diagnostic only). |
| `node_class` | [N] str | `"idle"`, `"driven"`, `"passive"` or `"mixed"`, from the multipliers (m > 0 on a sited route). |
| `non_reversing` | [R, N] bool | The branch test on passive routes at non-idle nodes: sign J(Y1) = sign J(Y2) = sign J(Y3) = sign A(n′), all nonzero. It is reported at passive-only nodes too, where it does not select anything. |
| `branch` | [R, N] str | Passive routes: `"share"` or `"quadrature"` at mixed nodes, `"node"` at single-class nodes (booked through the node's ΔG), `"idle"` at idle nodes. Driven routes: `""`. |
| `sign_margin` | [R, N] | min \|A\| over the three stages and the end (passive routes; NaN elsewhere). Treat the branch as rounding-ambiguous below 1e-10. |
| `heat_share`, `heat_quadrature` | [R, N] pJ | Both candidate heats of every passive route at every non-idle node: −Δξ_r Σ_s ν_sr μ̄_s, and h Σ_k b_k RT J_r A_r with b = (1/6, 1/6, 2/3). |
| `route_heat` | [R, N] pJ | The booked H_r at mixed nodes (the selected candidate), 0 elsewhere. |
| `mu_bar` | [S, N] pJ/fmol | μ̄_s, the divided-difference potentials (Appendix A's stable form, series below \|x\| = 1e-6). |
| `heat`, `work` | [N] pJ | H and W: driven only W = ΔG, H = 0; passive only H = −ΔG, W = 0; mixed H = Σ_passive H_r, W = ΔG + H; idle 0. |
| `delta_G` | [N] pJ | ΔG_i in the increment form: `chemical + standard_species`. |
| `chemical` | [N] pJ | RT Σ_s [δ_s (ln(n_s/V) − 1) + (n_s + δ_s) log1p(δ_s/n_s)]. |
| `standard` | [N] pJ | The booked standard term Σ_r ΔG°′_r Δξ_r, ΔG°′_r = Σ_s ν_sr μ°′_s. |
| `standard_species` | [N] pJ | Σ_s μ°′_s δ_s, μ°′_s = RT (μ°_s/RT − ln c0); equal to `standard` to rounding. |
| `delta_G_terms` | [N] pJ | The sum of the absolute values of ΔG's terms, the scale for rounding checks of ΔG and the standard term. |
| `heat_terms` | [N] pJ | The rounding scale of H; W's is `heat_terms + delta_G_terms`. At a mixed node it sums, over the passive routes, \|Δξ_r\| Σ_s \|ν_sr μ̄_s\| + RT G_r T_r A_r, where G_r is `gross_extents`, T_r the largest `affinity_terms` and A_r the largest \|A\| over the stages and the end. It covers either branch, including near equilibrium, where H is of order A² but its rounding is of order A. At a passive-only node it is `delta_G_terms`. |
| `ledger_residual` | [N] pJ | chemical + standard + H − W. |

### `nr.run_half_steps(net, amounts_fmol, volumes_pL, h_s, count, RT_pJ_per_fmol, multipliers=None, sites=None, theta=0.5) -> HalfStepRun`

`count` consecutive half-steps with nothing between them: a single-node world without transport,
where the engine's P(dt/2) I(dt) P(dt/2) is two half-steps per dt. `multipliers` may be a callable
`k -> [R] or [R, N]` for half-step k (from 0), which is how a class switch or a mid-run switch-on
is scheduled. The run stops at the first refusal (`refused_at`, `refusal`). Fields are `times`
[taken + 1], `amounts` [taken + 1, S, N], cumulative `extents`, `heat`, `work`, `standard` and
`chemical`, `step_heat` [taken, N], and `branches` (one `[R, N]` array per half-step).

### Free energy, moieties

- `nr.standard_potentials_pJ(net, RT)` [S]: μ°′_s.
- `nr.free_energy_pJ(net, amounts, volumes, RT)` [N]: G_i = RT Σ n (ln(n/V) − 1) + Σ μ°′ n. Use
  it only for whole values. For changes, use the increment form.
- `nr.free_energy_change(net, start, delta, volumes, RT)`: a dict of [N] arrays, `delta_G`,
  `chemical`, `standard` and `terms`.
- `nr.divided_difference_potentials(net, start, delta, volumes, RT)` [S, N]: μ̄.
- `nr.moiety_totals(net, amounts)` [Q, N], and `nr.moiety_change_from_extents(net, extents)`
  [Q, N] = Σ_open (M ν_r) Δξ_r. Moieties are ordered as `compile_network(net).moieties`.

### 50 digits: `nr.exact_energy_change(net, start_fmol, volumes_pL, RT, *, delta_fmol=None, end_fmol=None, extents_fmol=None, digits=50) -> ExactEnergy`

Python's `decimal`, with every float input taken exactly (`Decimal(float)`). Give exactly one of:
- `delta_fmol`, the engine's own δ (its increment change). **This is the form for a
  rounding-level check of the engine's ΔG**, since it is the exact value of the formula at the
  engine's inputs;
- `end_fmol`, where δ = end − start is taken exactly. fl(n + δ) has already lost δ's low bits at
  about ε n/|δ|, so this checks the stored end state, not the booking;
- `extents_fmol` alone, where δ = ν Δξ exactly.

With `extents_fmol` (alone or beside the others) it also returns `standard_routes`, the exact
Σ_r ΔG°′_r Δξ_r. The fields are lists of `Decimal` per node (`delta_G`, `chemical`,
`standard_species`, `standard_routes`, `terms`) and float arrays (`*_float`).
`nr.exact_free_energy(net, amounts, volumes, RT, digits=50)` gives G_i as Decimals. Do Decimal
arithmetic on these values inside `decimal.localcontext()` with `prec ≥ 60`, because Python's
default context keeps 28 digits.

## The exact node kinetics: `dissipation_reference` (`dr`)

### `dr.integrate_node(net, amounts_fmol, volumes_pL, RT, times_s, multipliers=None, sites=None, rtol=1e-13, atol_log=None, atol_extent_fmol=None, atol_energy_pJ=None, continue_from=None) -> NodeTrajectory`

This integrates dn/dt = ν J(n) at each node independently, with dH/dt = RT Σ_passive J A and
dW/dt = Σ_driven J (ν · μ), μ = RT ln(n/V) + μ°′, and the extents dξ/dt = J. It uses DOP853 in
the log-amounts.
- **Records.** Every record time is a step endpoint (the integration runs segment by segment,
  never through an interpolant).
- **Multipliers** are constant within a call. For a switch, call again with
  `continue_from=previous` (`amounts_fmol=None`). Times stay absolute and the records continue
  cumulatively.
- **Returns** `times`, `amounts` [T, S, N], `extents` [T, R, N], `heat` and `work` [T, N],
  `delta_G` [T, N] (G(n(t)) − G(origin), increment form), `closure` = W − H − ΔG (the
  integration's own balance), `origin`, `rtol` and `evaluations`.
- **What H means.** H is the true heat of the exact flow. At a passive-only node it equals −ΔG;
  at a driven-only node it is 0 and W = ΔG.
- **Tolerances.** The defaults are atol 1e-13 on ln n (relative accuracy) and
  rtol · 1e-3 · max n (extents) and rtol · 1e-3 · RT · max n (energies). Pass smaller values for
  a world whose heats are far below RT × its largest amount.

### Equilibria and closed forms

- `dr.passive_equilibrium(net, amounts_fmol [S], volume_pL, RT=None) -> Equilibrium`. This is
  the minimiser of G over n0 + span(ν_passive), the equilibrium of the passive reactions alone,
  as at a node whose driven routes are off. It returns `amounts`, the residual `affinities` (about
  1e-16), `equilibrium_constants` K_r = exp(−Σ ν μ°/RT) in activities, `log_quotient`
  (Σ ν ln a = ln K_r), `delta_G` = G(eq) − G(start) (increment form; `nan` without RT) and
  `iterations`. A closed passive relaxation's total heat is −`delta_G`.
- `dr.equilibrium_constants(net)` [R]; `dr.passive_equilibrium_ratio(mu0_A_RT, mu0_B_RT)` is
  c_B/c_A for A ⇌ B at a common c0.
- `dr.turnover_amount(n0, P, k, t)`: n0 e^{−kt} + (P/k)(1 − e^{−kt}), with P in fmol/s, k in
  s⁻¹ and t in s (array or scalar).
- `dr.michaelis_menten_substrate(S0_mM, K_M_mM, V_max_mM_per_s, t)`: S(t) from
  K_M ln(S0/S) + (S0 − S) = V_max t, solved by Lambert W and refined by Newton. With a catalyst
  at constant c_E, V_max = k_cat c_E.

## The zero-flux chain: `chain_reference` (`cr`)

The chain has N nodes of one volume V at spacing h. Its faces have κ = D A/h with A = V/h, so
dn_s,i/dt = Σ_r ν_sr J_r + (D_s/h²)(n_s,i+1 − 2 n_s,i + n_s,i−1), with one face at each end. For
the engine's chain this means a face area of V/h and a face length of h: probe 1's and MG0c's
worlds (1e-10 m²) have exactly that.

| Function | Inputs | Output |
| --- | --- | --- |
| `mode_basis(N)` | – | C [N, N], C[n, i] = cos(nπ(i + ½)/N). |
| `chain_eigenvalues(N, spacing_m)` | h (m) | λ_n = (4/h²) sin²(nπ/(2N)) [N] (m⁻²). |
| `chain_laplacian(N, spacing_m)` | | The zero-flux Laplacian [N, N] (m⁻²), whose eigenvalues are −λ_n. |
| `mode_coefficients(field)` | [..., N] | a [..., N]: a_0 is the mean; a_n = (2/N) Σ_i f_i C[n, i] for n ≥ 1. |
| `field_from_modes(a)` | [..., N] | f_i = Σ_n a_n C[n, i]. |
| `dominant_mode(field, species=0)` | [S, N] or [N] | argmax over n ≥ 1 of \|a_n\| for that species row. Pass the deviation from uniform, or the field itself (a_0 is excluded). |
| `fit_growth_rate(times, amplitudes)` | s, any | (slope of ln\|a\| in s⁻¹, RMS residual in ln). |
| `linear_rates(net, multipliers=None)` | multipliers [R] | (K [S, S] in s⁻¹, p [S] in mM/s) with dc/dt = K c + p. Valid for mass action of order 0 or 1 and A ⇌ B passive routes without factors; otherwise it raises ValueError. |
| `mode_propagator(K, D, lam, t)` | D [S] m²/s, λ m⁻², t s | expm[(K − λ diag(D)) t] [S, S]. MG0c's 2×2 propagator is `mode_propagator(k * J, (D_U, D_V), λ_n, t)`. |
| `propagate_modes(K, D, N, h, a0, t, source=None)` | a0 [S, N] | Exact coefficients at t. `source` [S] (field units per second) enters mode 0 only. |
| `propagate_field(K, D, h, f0, t, source=None)` | f0 [S, N] | The exact field at t. It is linear, so amounts or concentrations both work, with the source in the same units per second. |
| `full_propagator(K, D, N, h, t)` | | The whole system's expm [S N, S N], species-major, as a cross-check. |
| `half_step_linear_map(K, h_s, source=None)` | h = dt/2 | (M, q): SSPRK(3,3)'s affine map c′ = M c + q for linear kinetics. |
| `transport_polynomial(D, lam, dt_s)` | full dt | diag(1 − x + x²/2), x = dt D λ: @3's species transport under ARS(2,2,2) (Appendix A). |
| `strang_mode_map(K, D, lam, dt_s, source=None)` | full dt | (M, q) of one composite step P(dt/2) I(dt) P(dt/2) on one mode; pass `source` only for mode 0. This is the engine's expected discrete map for linear networks, not an exact solution. |

### `cr.integrate_chain(net, amounts_fmol [S, N], volume_pL, spacing_m, diffusivities [S], times_s, multipliers=None, RT_pJ_per_fmol=None, rtol=1e-12, atol=None) -> ChainTrajectory`

The semi-discrete system above, for any declared network, by DOP853.
- **Records** are step endpoints at the requested times (from t = 0).
- **Multipliers** are constant, `[R]` or `[R, N]`.
- **With RT** it also integrates each node's reaction heat and work, as for `integrate_node`
  (face heat is @3's and is not included).
- **`atol`** is absolute on the amounts scaled by each species' largest start amount (default
  1e-3 rtol).
- **Returns** `times`, `amounts` [T, S, N], `heat` and `work` [T, N] (or `None`), `rtol` and
  `evaluations`.
- **Cost.** About 0.7 s per 100 simulated seconds for MG0c at N = 12 on one core. Longer and
  wider runs (Q6) belong in a detached unit.

## MG0c: `turing_reference` (`tu`)

The functions are unit-agnostic. Pass one consistent system: either non-dimensional (J from
`schnakenberg_jacobian`, D_u = 1, D_v = d, lengths in ℓ, rates in units of k) or dimensional (k J
in s⁻¹, D in m²/s, lengths in m).

| Function | Output |
| --- | --- |
| `schnakenberg_uniform_state(a, b)` | (u0, v0) = (a + b, b/(a + b)²). |
| `schnakenberg_jacobian(a, b)` | J [2, 2], non-dimensional (time 1/k). |
| `schnakenberg_rate_constants(a, b, k, c_star_mM)` | `{name: (value, units)}` for `production_U` (a k c*, mM/s), `decay_U` (k), `production_V` (b k c*), `autocatalysis` (k/c*², mM⁻² s⁻¹). |
| `schnakenberg_network(a, b, k, c_star_mM, names=("U", "V"), moiety="M", c0_mM=1.0)` | The four driven mass-action reactions as a `Network`: U and V share one moiety, so the roles are (source, sink, source, closed). |
| `schnakenberg_uniform_amounts(a, b, c_star_mM, volume_pL)` | [2] fmol. |
| `dispersion_eigenvalues(J, D_u, D_v, k2)` | Both eigenvalues of J − k² diag(D) [..., 2] (complex). |
| `growth_rate(J, D_u, D_v, k2)` | σ(k²), the largest real part, in a closed form that stays accurate near the band edges. |
| `critical_ratio(J)` | d_c = ((√det J + √(−f_v g_u))/f_u)². |
| `band_edges(J, D_u, D_v)` | (k²_low, k²_high), or `None`. |
| `fastest_growing(J, D_u, D_v)` | (k²*, σ_max) from the stationarity quadratic, a closed form. |
| `turing_analysis(J, D_u, D_v)` | A dict: `trace`, `determinant`, `stable_without_diffusion`, `turing_inequality` (lhs, rhs), `diffusion_driven_instability`, `critical_ratio`, `band`, `k2_fastest`, `sigma_max`, `wavelength`. |
| `domain_modes(J, D_u, D_v, length, spacing=None, n_max=None)` | A dict of arrays over n = 1..n_max: `n`, `k2_continuum` (nπ/L)², `k2_discrete` λ_n, `sigma_continuum`, `sigma_discrete` (NaN without spacing). With spacing, N = L/h must be an integer and n_max = N − 1. |
| `admissible_unstable_modes(...)`, `fastest_admissible_mode(...)` | The modes with σ_n > 0, and their argmax (`None` if there are none); discrete if `spacing` is given. |
| `staircase(J, D_u, D_v, lengths, spacing=None)` | [(L, fastest admissible mode or None)]. |

What the self-tests confirm against §6.4, at a = 0.1, b = 0.9, d = 10:
- (u0, v0) = (1, 0.9), and J = [[0.8, 1], [−1.8, −1]] both from the formula and from the four
  mass-action declarations;
- d_c = 8.5676 and the band (0.2, 0.5);
- σ_max = 0.057191 at k̃² = 0.318545, a wavelength of 11.133 ℓ, an e-fold of 174.9 s and a
  wavelength of 111 µm;
- the domain table at h = ℓ/2 (modes and σ_n);
- the staircase;
- the subcritical control (d = 8, every σ_n < 0 on every domain);
- probe 2's B1 eigenvalues on L/ℓ = 11.

## Recommended comparisons and tolerances

The measurements are from `reference_crosschecks.py` at commit 5fd695b
(`/mnt/workspaces/Cells/reaction-references-20261114-01/crosschecks-3/`). ε = 2.2e-16.

The second implementation (the "variant") differs from the reference in its evaluation orders:
- exp-log mass action, against the reference's product of powers;
- the passive net rate as J⁺ − J⁻, against the expm1 form;
- Shu–Osher stages, against Butcher stages;
- its own groupings of ΔG, μ̄, the share and the quadrature.

| Comparison | Tolerance | Why |
| --- | --- | --- |
| Half-step end amounts against `half_step(...).end` | 1e-12 relative, per species and node | The same formulas. The variant differed from the reference by at most 4.7 ε (57 admitted random trials over every law). |
| Extents against `.extents` | 1e-12 × `gross_extents` | Near equilibrium a passive route's net extent is a small difference of gross fluxes. The variant differed by at most 42 ε of `gross_extents`. |
| Δn = ν Δξ and moiety changes | bitwise if the engine forms Δn as ν Δξ once; otherwise 4 ε Σ\|ν Δξ\| | By construction. |
| ΔG (that is, W − H at every node) | 1e-12 × `terms` from `exact_energy_change(delta_fmol=engine δ)` (§3.4 item 4) | This reference's float increment form is within 1.06 ε of the 50-digit value, and the variant within 2.7 ε of `delta_G_terms`. 1e-12 is the note's bar. |
| Standard term | 1e-12 × `terms`, against `standard_routes` from `exact_energy_change(extents_fmol=engine Δξ)` | As for ΔG. |
| Single-class H and W | as ΔG; W = 0 or H = 0 exactly | The booking is ±ΔG. |
| Mixed-node H against `.heat` | 1e-12 × `heat_terms` | Measured over 932 mixed nodes from 233 admitted of 240 trials. Half the trials started every passive route within about 1e-6 of its equilibrium, and half were at h L ≈ 0.4. There were 479 routes on the quadrature and no branch disagreements. H differed by at most 0.38 ε of `heat_terms`. Do not use \|H\| as the scale: against \|H\| the same differences reach 4.4e-11, because near equilibrium H is of order A² while its rounding is of order A. |
| Mixed-node W | 1e-12 × (`heat_terms` + `delta_G_terms`) | W = ΔG + H. The variant differed by at most 6.9 ε of that scale. |
| The branch per passive route | must equal `.branch` wherever `sign_margin` > 1e-10 | The selection is a sign test. Where \|A\| is within rounding of 0 (a state built exactly at the selection), either branch is correct, and the node's H may then match either candidate (`heat_share` or `heat_quadrature`). |
| Refusals | `admitted`, `stage_condition_ok` and `positive_ok` must agree wherever \|hL_max − θ\| > 1e-12 θ | An inclusive comparison at the bound is decided by rounding. For example, probe 2c's h(k_f + k_r) = 0.55 sits exactly at h L = 1/2, and this reference refuses it at h L = 0.5000000000000001. Test either side, not at equality. |
| Idle nodes, and zero multipliers everywhere | bitwise against the start | The start is selected. |
| H and W against `integrate_node` (dt studies, onset and crossing cases) | judge the engine's error; the reference's own error is ≤ 1e-12 relative | Between rtol 1e-11 and 1e-13, H agreed to 6e-13, and the closure was ≤ 5e-17 pJ. For a pinned tolerance, run at two rtols. |
| Closed forms (turnover, Michaelis–Menten, equilibria) | rounding (Michaelis–Menten: a few ε × (1 + V_max t/K_M), the problem's own conditioning) | Analytic. |
| Linear chain against `propagate_modes` | the engine's second-order error; the reference is exact to about 1e-14 | Mode-wise expm agreed with the full matrix exponential to ≤ 1e-13 of the field (B4 measured 2.5e-14). |
| The engine's linear worlds against `strang_mode_map` iterated k times | about 1e-12 × max\|a\| per step, accumulating at most about k ε (for example 1e-10 for 10⁴ steps) | The engine's own discrete map, if its order is P(dt/2) I(dt) P(dt/2) and the transport is Appendix A's polynomial. A mismatch above rounding is an implementation or composition finding, not a discretisation error. |
| MG0c Q1 (single-mode starts) against `mode_propagator` | the engine's second-order error, pinned from the dt study | Exact for the linearised system. Against the nonlinear chain at amplitude 1e-7, on L/ℓ = 11 for n = 1–6 at 3/\|Re λ\|, the difference was ≤ 1.2e-8 of the mode at rtol 1e-13 (≤ 1.4e-7 at 1e-12, which is the integrator's floor). The prototype's smallest dt error was 2e-6. |
| MG0c Q6 (the nonlinear pattern) against `integrate_chain` | the engine's error (4.8e-4 to 3e-5 of c* in the prototype) | At rtol 1e-12 the reference's error is many orders below that; confirm at 1e-13 for the judged run. |
| σ_n, d_c, the band, the staircase | exact (closed forms, about 1e-15) | Q3's fitted growth rate is limited by the fit and the run, not by σ_n. |

## Readings of the design taken here

1. **Node class.** A node's class in a step comes from its multipliers only: m > 0 on a sited
   route. A driven route with m > 0 whose Hill factor underflows still makes the node driven.
2. **Idle nodes.** An idle node returns its start values, books zeros, and is not checked for
   positivity or for the stage condition, since it takes no stages.
3. **δ.** δ_s is the computed ν Δξ. It is used in ΔG's increment form and in μ̄, and the
   candidate end state is n + δ.
4. **A refused step** reports `admitted = False` and `accepted = start`. Its bookings are
   diagnostic only.
5. **Positivity.** The domain is positive, finite amounts of every declared species at every
   non-idle node. The check covers every species of those nodes at Y1, Y2, Y3 and n′.
6. **The stage condition** is inclusive (h max L = θ passes) and is evaluated at Y1, Y2 and Y3.
7. **Mixed-node heat.** H at a mixed node sums every passive route sited there, including routes
   with m = 0. Such a route's J, J⁺ and J⁻ are exactly 0 by selection, it takes the quadrature
   branch (a zero sign), and it contributes exactly 0.
8. **The standard term** is booked in route form, Σ_r ΔG°′_r Δξ_r (Appendix A's "standard term
   gains"). ΔG uses the species form; the two agree to rounding.
9. **Molecularity.** Σ α ≤ 3 for every law, and Σ β ≤ 3 for the passive law.
10. **michaelis_menten** declares reactants `{S: 1}` exactly. Its catalyst is named separately and
    may not be a reactant or product.
11. **Hill factors.** x is the factor species' concentration (mM), and K is in mM.
12. **Multipliers** are m ≥ 0, with no upper bound (§2.1).
13. **"First step" in the probe tables** is the first half-step. Under that reading, probes 2d
    and 2g reproduce to the quoted digits.
14. **The trace-sensitivity values** (§3.3's table, §3.4 guard 5, probe 2g's −1.3e-3 and
    −1.4e-7) are relative changes of the whole heat, not pJ. Under that reading they reproduce:
    −6.27e-5 and −6.32e-5; −2.21e-2 and −2.21e-2; −1.32e-3 and −1.38e-7.
15. **Mode normalisation.** a_0 is the mean and a_n = (2/N) Σ f_i cos(nπ(i + ½)/N). "Dominant" is
    argmax |a_n| over n ≥ 1 of one species row (default the first, U).
16. **The chain** has uniform node volumes, with κ/V = D/h².
17. **The passive equilibrium** is taken over the stoichiometric class of the passive reactions,
    which can be finer than the declared moieties.

## Known limits

- No transport inside the node references, and no other writers. Turnover or exchange on a node
  can be emulated as declared source or sink reactions, which is what version 1 requires anyway
  for reacting rows.
- Amounts are plain floats, not @3's anchor + increment. A species driven below about ε × its
  anchor stalls on the engine (§4.4) but keeps decaying here.
- One sub-step (m = 1), as in version 1. There is no stiff door.
- Multipliers are constant within each call. Schedule changes go through `run_half_steps`
  callables or `integrate_node(continue_from=...)`.
- The chain has uniform volumes and constant multipliers. Its node heat and work are the
  reactions' only.
- The 7-species cap and the engine's definition-time refusals outside the network itself are not
  modelled.
- `integrate_node` integrates each node separately, which suits a few nodes. For many coupled
  nodes use `integrate_chain`.
- The design's prototype worlds B5, B6, B8, probe 2d's "smooth mixed world" and B4's chain
  parameters are not specified fully, so they are not re-derived. The cross-check driver records
  what is.
