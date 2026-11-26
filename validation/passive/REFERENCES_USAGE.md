# Using the passive permeation law's closed-pair reference (interface only)

How to run the independent reference for `cells.route.passive_neutral_permeation@1` and read its outputs
without reading its source.
- **Sources:** it was written from [ARCHITECTURE.md](../../docs/ARCHITECTURE.md) ("Transport laws
  by physical contract") and [INNER_MODEL_V4_DESIGN.md](../../docs/INNER_MODEL_V4_DESIGN.md) §11,
  with §10.2 and §13.6, which change neither the equations nor the admissible worlds.
- **What was not read:** the engine (`src/`, `check_impermeant` included) and the Syn3A probes'
  records.
- **Readings** are listed below; disagreements go to the lead.

| Module | What it gives |
| --- | --- |
| `validation/passive/passive_reference.py` (`pr`) | The closed pair's closed form (float and 50 digits), its equilibrium, the per-step exact heat, and an independent integration of any graph of closed compartments |
| `validation/passive/passive_crosschecks.py` | The driver behind the measured numbers below (`--out DIR`; seconds) |

**Self-tests:** `tests/unit/test_passive_references.py`, 12 tests, tier 1, about 8 s (a
three-compartment chain on the default Radau included). They also check
that nothing here imports `cells` or `validation.tissue`.

## The law and the world

- **The law** is the constant-field route at valence 0, Fick's law:
  J = 1e15 · PA · (c_a − c_b), in fmol/s from a to b.
  - **PA** is P·A in m³/s. For a junction it is P_s · A_e · gate · availability (a reading; see
    below).
  - c = n/V, in mM (= fmol/pL = mol/m³).
  - The factor 1e15 converts mol to fmol. The constant-field flux PA ψ(x)(c_a − c_b e^−x) at x = 0
    is exactly this.
- **The closed world.** Two compartments are closed for the species when it passes only between
  them. Examples: two cells joined by a junction, each wall impermeant to it; or a cell and a
  face-free node.
  - "Absent from the bath" means a trace behind impermeant walls, so the bath never enters the
    equations.
- **Units:** fmol, pL, mM, s, and pJ for energies. **RT is an input** (pJ/fmol, 1e-3 R T). The
  standard potential is common to both sides and cancels in a closed pair.

## The closed pair: `pr.closed_pair(t, n_a0, n_b0, V_a, V_b, PA, rt=None)`

It returns a dict:

| Key | Meaning |
| --- | --- |
| `n_a`, `n_b`, `c_a`, `c_b` | Each compartment's amount and concentration at t. Each side is computed from its own non-negative terms, n₀ e^(−kt) − n_∞ expm1(−kt), so a trace side keeps its digits |
| `flux_fmol_per_s` | J at t, = 1e15 PA (c_a0 − c_b0) e^(−kt). Exactly 0 at equal concentrations |
| `k` | 1e15 PA (1/V_a + 1/V_b) (1/s); also `pr.rate_constant` |
| `c_eq`, `delta_a` | N/(V_a + V_b), and n_a − n_a0 formed stably |
| `heat_pJ`, `work_pJ` | With `rt`: the exact path's heat G(0) − G(t) in the increment form, and 0 |

The companions:
- `pr.exact_closed_pair(t, ..., rt, digits=50)` gives `n_a`, `n_b`, `flux` and `heat` as Decimals.
- `pr.equilibrium(n_a0, n_b0, V_a, V_b, rt)` gives equal concentrations, and the relaxation's total
  heat G(0) − G(eq).

## The per-step heat: `pr.step_heat(starts, deltas, volumes, rt)`

- **What it gives:** (heat, scale) for one step of a closed sub-system. The heat is −Σ of each
  compartment's free-energy increment, from the engine's own start amounts and changes. §11's exact
  booking puts this as heat, with no work.
- **The rounding scale:** the absolute values of the increment's terms. Compare the engine's
  booked heat within a few ε × scale.
- **In 50 digits:** `pr.exact_step_heat(...)`. An unchanged compartment contributes exactly 0.
- **No scheme is assumed.** §11 states none for this law. The reference never re-implements the
  engine's step, and states no order.

## Any graph of closed compartments: `pr.integrate(world, t_end, record=(), rtol=1e-12, method="Radau")`

```python
world = pr.World(rt_pJ_per_fmol=RT,
                 compartments={"a": pr.Compartment(volume_pL=2.0, amount_fmol=2.0),
                               "b": pr.Compartment(0.75, 7.5e-13)},  # a trace start
                 routes={"j": pr.Route("a", "b", PA_m3_per_s=3e-18)})
run = pr.integrate(world, t_end, record=(...))
```

- **What it integrates:** the amounts, each route's transferred amount, and the dissipation
  dH/dt = RT Σ_r J_r ln(c_a/c_b).
- **Tolerances:** each amount's absolute tolerance is rtol × 1e-6 × its own initial amount, so a
  trace keeps its relative accuracy.
- **A record** `run.at[t]` holds `n_fmol`, `c_mM`, `transferred_fmol`, `flux_fmol_per_s`,
  `heat_pJ`, `work_pJ` (0), `free_energy_change_pJ`, `closure_pJ` (H + ΔG, zero on the exact path)
  and `material_residual_fmol`.
- **The integrated heat is independent evidence for H.** Unlike FR-3's, no term cancels between H
  and ΔG here.

## Measured (`passive-crosschecks-03`, from snapshot `passive-snapshot-03`)

All against 50 digits, at t = 0.01/k to 3/k. Relative errors unless stated.

| Start ratio c_a0/c_b0 | Closed form: amounts; heat | Radau at 1e-12: amounts; heat; closure (of RT·N) | DOP853 at 1e-13: amounts; heat; closure |
| --- | --- | --- | --- |
| 1 (equal) | 0; 0 | 0; 0; 0 | 0; 0; 0 |
| 1 + 1e-8 | 2.2e-16; 4.0e-8, but **0.36 ε × the heat's rounding scale** | 8.9e-16; 6.7e-8; 1.7e-24 | 7.8e-16; 1.7e-7; 2.2e-24 |
| 1 + 1e-3 | 0; 1.9e-13 (0.13 ε × scale) | 8.9e-16; 1.1e-12; 2.5e-19 | 2.2e-16; 3.8e-13; 4.5e-20 |
| 1e2 to 1e12 (a trace start) | ≤ 3.3e-16; ≤ 2.3e-15 (≤ 0.76 ε × scale) | ≤ 4.2e-15; ≤ 7.1e-15; ≤ 1.3e-15 | ≤ 3.4e-15; ≤ 3.7e-14; ≤ 1.2e-14 |

- **Near equal starts, judge the heat on its rounding scale** (`heat_scale_pJ`), not relative to
  itself. The heat is second order in the gradient while its terms are first order, so a relative
  error grows as the gradient vanishes, while the error in ε × scale stays below 1.
- **The integrations' heat** is relative to a heat that, at 1 + 1e-8, is about 1e-17 of RT·N.
- **Material** is conserved within 3.8e-15 in every integration.

| Check | Result |
| --- | --- |
| Equal concentrations with unequal volumes (n/V equal in floats) | Flux exactly 0, heat exactly 0 |
| Reversal and swapping the compartments | Exact antisymmetry; heat monotone and non-negative |
| The per-step heat, 5,000 random steps from trace to large amounts | Within 1.24 ε × scale of 50 digits |
| R-tissue's static entry point on the coordinator's world (two cells, a junction, X at z = 0 permeant only there, a trace in the bath, the full electrical world around it) | X within 5.2e-14 of the closed form up to 3/k |

## Readings, answered by the core owner (its note's §7.4 (i))

1. **PA for a junction** is P_s · A_e · gate · availability. The gate evolves, so a closed-pair
   comparison starts the gate at its steady value or integrates it. On a membrane patch, PA is
   P · A · availability.
2. **The heat** goes to the law's own field, `passive_dissipated_energy_pJ`, never to the
   membrane's or the junction's; transfers go to `passive_transferred`. The reference's total is
   what that field is compared against.
3. **A trace is a start, never a zero,** now engine-wide: a row that does not apply at a node is a
   declared trace (registry `background`), and an exact zero is refused at the definition. The
   closed form and the integration refuse a zero amount too.

## Not built

- **The held-bath balance.** §11 asks for "the total balance includes the declared reservoir
  work", but states no sign convention or standard state for it, and the coordinator's scope was
  the closed pair.
- **Composition with water,** qualified separately (§11).

## Evidence

`/mnt/workspaces/Cells/independent-references-20261115-01/` (HANDOFF.md): `passive-crosschecks-03/`, the
record, from snapshot `passive-snapshot-03` (f4720aff). The runs from snapshots 01 and 02 are kept.
In run 02 the sweep key `{ratio:g}` let the 1 + 1e-8 row overwrite the ratio-1 row.
- The driver ran from a snapshot folder, not a checkout, so its `git_revision` field is empty, and
  the snapshot's SNAPSHOT.json carries the revision.
