# The worlds, and what the references compute

Read `README.md`'s rules first. `inputs.json` governs the numbers.

## 0. Units

Amounts in fmol, volumes in pL, concentrations in mM (= fmol/pL), flows and permeances in pL/s,
energies in pJ (1 kJ/mol × 1 fmol), times in s, temperature 298.15 K (a bench, and only a scale for
RT). Every declared real is a decimal literal, and both sides use its nearest double. Read each as the
exact value of that double. A trace is 10⁻¹² mM: the concentration of a species where nothing else is
declared.

**Every event, switch, restart and output time is a multiple of the coarsest step of its runs,** the
retry's included.

**Names.** Wells are `1` and `2`. Nodes are `A` … `D` and `S`, the inlet `I`, the collector `K`. T and U
are the tracers. Holders, links and faces are as LAWS.md defines them.

## 1. The worlds

Each world is a single embedding of LAWS.md's equations. Anything else in the engine's world (ions, a
quiescent cell) is held: equal ion levels at every node, and permeability zero for all else. The engine
side confirms that, and the references never see it.

**Arm 1, two wells, one step.** Worlds `<volumes>-<background>`.

| Part | Values | Why |
| --- | --- | --- |
| Volumes and PA | `eq`: 2 and 2 pL, PA = 0.125. `r4`: 5 and 20 pL, PA = 0.5 | k = 1/8 s⁻¹ in both, so kh is dyadic. 4:1 separates a rate from V₁ alone |
| Background | `lo` 0.015625, `mid` 1, `hi` 16 mM in well 2; well 1 is 3 mM above | Δc is fixed, so the transfer does not change with the background and the heat does |
| `tr` | 4 and 10⁻¹² mM, `eq` only | An empty well: the onset limit |
| Steps | Exact heat: 2, 1, 1/2, 1/4 s (kh = 1/4 to 1/32). Default heat: 8 z_def/2^j, j = 0 … 5 | Five halvings give T4's ladder its reach. z_def is §6's placeholder |

`eq-mid` holds 8 and 2 fmol, the request's amounts.

**Arm 2, diffusion, an exchange, diffusion.** Worlds `N-buffered`, `N-clean` and `N-none` (no
exchange). Two 2 pL wells, PA = 1/64, so k = 1/64 s⁻¹ and the horizon is 48 s.
- **The start** is 5 ± 3e^(1/4) fmol (as doubles), so the exact solution holds 8 and 2 fmol at 16 s, the
  request's state just before the withdrawal.
- **The exchange** at 16 s takes half of well 1 and refills it with buffer: 1 mM T (`buffered`, so that
  the supplied amount is compared at full power) or the trace (`clean`, the request's target). **A row at an
  event's time is the state before it,** and the event acts at the start of the step that leaves it. This
  holds for the portions of arm 4 too.
- **Steps** 64 z_def/2^j s, j = 0, 1, 2, at most 2 s.

**Arm 3, flows.** T starts in one chamber and U in another, so one run holds two different answers.

| World | What | Why |
| --- | --- | --- |
| `F1`, `F2` | I → A → B → K and I → B → A → K, equal volumes (4 pL), Q = 0.5 | The request's two targets at one residence time (8 s) |
| `F3`, `F4` | The same with V_B = 10 pL | Rates come from Q/V, and the order matters |
| `F5` | Split and merge: A → B, C → D → K, unequal flows and volumes | A network that is not a chain |
| `F6` | A ring A → B → C → A with a side outlet | A network with a loop. It has complex rates |
| `F1L`, `F6L` | `F1` and `F6` with T in A labelled `tag` | Labels follow the liquid, exactly |
| `F7` | `F1` beside a node S no link touches, holding a ligand L and its sites | A bound species stays where it is |

U starts in B (`F1` to `F4`, `F6`), or in C (`F5`). The inlet carries every species at the trace. The
horizon is 16 s. Steps are 8, 1 and 1/8 s: one, eight and 64 to a residence time.

**Arm 4, the growing collector.** From zero volume.
- `G1`, `G2`: portions of 1 pL at 1 mM then 3 mM, and the reverse. `G3`, `G4`: 1, 3, 3 and 3, 3, 1 mM.
- `G5`: a flow of 0.25 pL/s whose inlet switches from 1 to 3 mM at 4 s, for 8 s. It ends with 1 pL of
  each, as `G1` does.

**Arm 5, the heat of each holder.** `F1`'s chain. `H1`: 2.5 mM in A, 1 mM in B, inlet 0.5 mM, so every
holder's inflow differs from its content. `H2`, `H3`, `H4`: B at ε = 10⁻⁹, 10⁻¹² and 10⁻¹⁵ mM, inlet at
ε. `H5`: every holder at 1 mM T and 2 mM U, inlet the same (a uniform stream). Steps 1/4, 1/8, 1/16 s,
32 to 128 to a residence time.

**Arm 6, a flow beside a face.** `J1`: A (4 pL) and B (6 pL) joined by a face (PA = 0.25 for T, 0 for U)
and by the flow I → A → B → K at 0.5. U sees the flow alone. Steps 1/2, 1/4, 1/8 s. `J0`: the same with
every flow off.

**Arm 7** has no reference: both sides are engine runs (CRITERIA.md §3.8).

## 2. The runs

`inputs.json` lists every registered run: its name, arm, world, heat, step, role and variant. `judged`
runs are compared, `support` runs are twins and restarts, `recorded` runs report an outcome, the
`expected stop` is meant to stop, and `plant` runs carry a declared change. The retry (CRITERIA.md §7)
adds runs by rule. A run's outputs are its world's times that its step divides, and t = 0.

## 3. What to compute

For every world, at every output and in every run's step where the quantity depends on the step:

1. **Arm 1:** m*(h), the exact levels, m_R(h), the scheme's levels, D(m*(h)), D(m_R(h)) and A(0), at
   every step.
2. **Arm 2:** n_T_1 and n_T_2 at the compare times (the two intervals' closed forms; at 16 s the state
   before the exchange), the exchange's four numbers (before, sample, supplied, heat), and the face's heat
   to each compare time, for the three worlds.
3. **Arms 3 to 6:** every n, V_K, supplied amount and label amount by the propagator. H_tot by §5's
   state function. Arm 5: every H_holder. Arm 6: H_face and H_tot.
4. **Arm 4:** for each portion its loss and the loss's two parts. The collector's n, V and cumulative
   loss at every output.
5. **The plants'** planted quantities and their sizes (CRITERIA.md §6), and **the placeholders' rule**
   (§6) once z_def is filled.

**Accuracy.** A propagator or closed form is correct to 40 digits. An integral (arms 5 and 6) is
correct to 10⁻¹² of its scale, by two quadratures of different kinds that agree to it (for example
tanh-sinh, and Gauss-Legendre on pieces graded toward each singular end), and by §5's sum identity.
Every value carries `accuracy`, its absolute bound.

## 4. The classes, from the model's structure

Every (world, series, time) entry carries a class, fixed before any engine run:
- **`E`,** equal to +0.0 bit for bit, where the model is zero by its structure: at t = 0 the collector's
  contents and volume, every heat, every supplied amount and every `tag` amount outside A; the first
  portion's loss; `J0`'s collector and router heat at every output.
- **`R`, `B`, `S`, `L`** for every other, by READOUTS.md's rule for its series.

No ruling assigns a class, and none changes after a run.

## 5. The plants and their sizes

For each plant of CRITERIA.md §6, at its named check's best entry: the honest reference, the planted
value, the distance, the expected honest tolerance (§6.2 there) and their ratio, the margin.

## 6. Placeholders, filled in one dated commit before the criteria tag

| ID | What | Filled from |
| --- | --- | --- |
| E1 | For each default-heat start: the largest kh at which one default step is inside the domain the engine will admit | the dt study on today's engine |
| E2 | For each default-heat start: the largest kh at which a default-heat run completes its energy check | the dt study |
| z_def | The largest power of two not above half the smallest E1 and E2 over the starts (arm 1's `eq-mid`, `eq-hi`, `r4-mid`, `r4-hi`, and arm 2's start and post-exchange states), and at most 1/32 | E1, E2 |
| S1 | A step at which the default-heat run from `eq-tr` is confirmed to stop | the dt study |
| L1 | The default heat's declared law, its one-step closed form and its bound | the dt study agent, with provenance |
| W7 | Arm 7's world pairs | the dt study's report |

**An edge decides which case runs at which step. It never sets a band, a class or a tolerance.**

## 7. The file

One JSON file per arm, `reference_arm1.json` to `reference_arm6.json`, bytes fixed by the values (sorted
keys, fixed separators, no timestamps):

```json
{"kind": "cells.liquid_routing.reference@1", "arm": 3,
 "inputs_sha256": "...", "constants": {"N_A": "6.02214076e23", "k_B": "1.380649e-23"},
 "worlds": {"F1": {"times_s": [0.0, 1.0],
   "series": {"n_T_A": {"class": ["R", "R"], "value": ["0", "0"], "accuracy": ["0", "0"]}}}},
 "cases": {"eq-mid|0.5": {"m_star": "...", "m_R": "...", "levels_exact": ["...", "..."],
   "levels_scheme": ["...", "..."], "D_star": "...", "D_R": "...", "A0": "..."}},
 "events": {"N-buffered": {"before": "...", "sample": "...", "supplied": "...", "heat": "..."},
   "G1": [{"volume_pL": "1", "loss": "0", "resident": "0", "arriving": "0"}]},
 "plants": [{"plant": "P4", "check": "n_U", "world": "F1", "time_s": 8.0, "step_s": 1.0, "honest": "...",
   "planted": "...", "distance": "...", "expected_tolerance": "...", "margin": "..."}],
 "planted_series": {"P2": {"F1": {"n_T_K": {"times_s": [1.0], "value": ["..."]}}}},
 "checks": [{"name": "...", "residual": "...", "bound": "...", "passes": true}],
 "provenance": {"revision": "...", "sha256_of_this_file_excluded": true}}
```

- Every number shown is a placeholder of the right type, not a value.
- `inputs_sha256` is the sha256 of `inputs.json` as read. Values are strings. Class, value and accuracy
  are parallel lists, and an `E` entry's accuracy is `"0"`.
- A `cases` key is `<world>|<step>`, the step as its `repr`.
- `planted_series` holds the series LAWS.md §11 defines, at the outputs and steps the checks name.
- The judge requires the registered keys, ignores keys it does not know, and treats a missing one as a
  fault.

## 8. The invented file

`reference_invented.json`, the same layout, for a small world of each kind (two wells with an exchange,
a chain with a label, a portion-fed collector, a flow beside a face) with your own volumes, flows,
times and concentrations, none of this folder's. It carries one `E` entry of each kind, one plant of
each kind and a `cases` block.

## 9. The checks to pass before the tag

Every one is computed in decimal, and its residual and bound are recorded in `checks`. All must pass:

1. **Equal volumes.** With the inlet and B exactly zero, one residence time of the equal-volume chain
   gives 1 − 2/e of the tracer collected forward and 1 − 1/e reversed, by the propagator and by the
   closed form, to 50 digits. m equal chambers in series give LAWS.md §4's form.
2. **Unequal volumes.** The closed form with a ≠ b agrees with the propagator to 50 digits, and tends
   to the confluent form as V_B → V_A (V_B = V_A(1 + 2⁻ᵏ), k = 10 … 40, at first order in 2⁻ᵏ).
3. **Conservation.** In every network's generator the columns of the nodes sum to zero (the inlet's column
   is its supply), and the amounts and volumes sum to the start plus the supplied.
4. **Time reversal.** e^(−Gt) e^(Gt) is the identity to 50 digits, and steps of h compose: P(h)^S =
   P(Sh) for every registered h.
5. **f-ladder.** H_ev − RT V f c φ(x/c) falls by 4 per halving of f (f = 2⁻⁴ … 2⁻¹², to within 2⁻⁴ of 4
   at the end), and equals −RT V f²(x − c)²/(2c) to leading order.
6. **Two wells.** §1's closed form equals the propagator of the two-well system. D(m) equals the integral
   of the affinity over m, and D′(0) = A(0). Arm 2's exact solution holds 8 and 2 fmol at 16 s to the
   declared doubles' rounding.
7. **R(z).** 0 ≤ R(z) − e^(−z) ≤ z³/6 at every registered z.
8. **Heat.** Σ H_holder = H_tot in every world of arms 5 and 6. A uniform stream loses nothing. The
   collector's second portion loses RT (3 ln 3 − 4 ln 2) (1 mM then 3 mM, 1 pL each), the first loses 0,
   and the order of two portions leaves the second's loss unchanged.
9. **Labels** sum to their species, and **arm 6 at Q = 0** is §1's two wells.
10. **Rounding counts.** A binary64 emulation of your own (exact half-steps, explicit stages, ideal
    mixing) stays inside LAWS.md §9's bounds on every network, with the largest fraction recorded. A
    fraction above 1 stops the work. It is never used to set a bound.
