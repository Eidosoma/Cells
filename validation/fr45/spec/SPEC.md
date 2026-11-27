# FR-45's reference spec: the worlds and what the references compute

This folder is for the code-blind references agent of FR-45's qualification
(`docs/FR45_SITE_COMPETITION_PROTOCOL.md`; D327).

**Rules for the references:**
- **Code-blind.** Do not read `src/`, `tests/` or any engine module. Read only this folder and the
  protocol document.
- **Value-silent.** This spec states every input, and no result. Compute every result here.
- **Deterministic regeneration.** The writer's output must be bitwise the same under at least two
  other `PYTHONHASHSEED` values, shown before a head is reported.
- **The writer** (§5) writes the file the judge reads. The judge is first run on a file this writer
  writes on invented inputs, before any engine run.

## 0. Units: every declared count

- **The one declared count is copies,** N: a number of site-bearing units on one owner. With it
  come sites per copy, ν, an integer (sites per copy), and the accessible fraction α (1).
- **No other quantity is a count.** Every amount is in fmol, not a number of molecules or sites. A
  number of sites is S·N_f.
- **The units of every other quantity:**

  | Quantity | Unit |
  | --- | --- |
  | Amounts: free ligand n, free sites R, bound B, capacity S | fmol |
  | Volumes V | pL |
  | Concentrations c = n/V | mM (= fmol/pL) |
  | Association k_on | per mM per s |
  | Dissociation k_off | per s |
  | Dissociation constant K = k_off/k_on | mM |
  | Times | s |
  | Free energies and heats | pJ |

- **Constants:**
  - N_f = 602,214,076 sites per fmol, exact (N_A × 10⁻¹⁵ mol, SI 2019);
  - the gas constant R = N_A·k_B, with N_A = 6.02214076 × 10²³ per mol and k_B = 1.380649 × 10⁻²³ J/K
    (both exact);
  - the temperature T = 310 K;
  - RT = 10⁻³·R·T pJ/fmol;
  - the standard concentration is 1 mM.

## 1. The model

### 1.1 Sites, sets and populations

- **A site set** s has an owner (a node, or a cell's patch and one of its faces), copies N_s, sites
  per copy ν_s and accessible fraction α_s.
  - Its capacity is S_s = α_s·ν_s·N_s/N_f fmol.
  - Its free sites are R_s.
- **A population** b binds one ligand l(b) on one set s(b). It has k_on,b and k_off,b, and its
  bound amount is B_b.
  - Several populations on one set compete for its free sites.
  - A set with one population is that population's own sites.
- **The moiety:** R_s + Σ_{b on s} B_b = S_s for every set, at all times.
- **The facing node:**
  - a node-owned set faces its node;
  - a set on a patch's outside face faces the patch's outside node;
  - a set on a patch's inside face faces the patch's cell.
- **Every ligand** is neutral and impermeant. It moves only by binding. In the engine's worlds the
  ligands are embedded in a quiescent tissue: ions at fixed amounts, and zero permeability for
  every ligand. So their equations are exactly §1.2's.
- **Every multiplier is 1 throughout.**

### 1.2 The laws

For population b on set s, binding ligand l from the facing node i:

    J_b = k_on,b · c_l,i · R_s − k_off,b · B_b          (fmol/s; c_l,i = n_l,i / V_i)
    dB_b/dt = J_b
    dR_s/dt = −Σ_{b on s} J_b
    dn_l,i/dt = −Σ_{b binding l from i} J_b

- **Detailed balance:** at equilibrium, B_b / R_s = c_l,i / K_b for every population.
- **The engine integrates these equations** with an explicit third-order scheme at a fixed step dt.
  Its stage condition (§3.6) requires, at every stage, h·max L ≤ 1/2, with h = dt/2 and the
  unidirectional loads:
  - L_n of a pool (l, i): Σ_{b binding l from i} k_on,b · R_s(b) / V_i;
  - L_R of a set s: **Σ_{b on s} k_on,b · c_l(b),i**, summed over the set's populations;
  - L_B of a population b: k_off,b.

### 1.3 The free energy and the heat

- **The free energy of a set's sites:**

      G_site,s = Σ_{b on s} B_b · [μ°_b + RT·ln(B_b / S_s)] + RT·R_s·ln(R_s / S_s),   μ°_b = RT·ln(K_b / 1 mM)

  with 0·ln 0 = 0. R_s enters once per set.
- **The free energy of a node's free ligand:** G_pool = RT·n·(ln(c / 1 mM) − 1), per ligand and
  node, with c = n/V.
- **The world's G** is Σ_pools G_pool + Σ_sets G_site,s, over the ligands' rows and the sets.
- **The heat over an interval** without an event is H = G(start) − G(end). Binding only, so the
  sub-system is closed and passive, and H ≥ 0.

### 1.4 The wash (W2, W7)

At a wash of node i, fraction f with buffer concentrations c_buf (the event's map, applied at once):
- every ligand's free amount at i becomes (1 − f)·n + f·V_i·c_buf;
- removed: f·n;
- supplied: f·V_i·c_buf;
- every set's R and every population's B are unchanged.

## 2. The worlds

Every number below is a binary64 literal as written. A trace is 10⁻¹² mM: the free concentration
of a ligand wherever no amount is declared for it. Unless stated, a free amount is the ligand's at
the named node.

### W1: one node-owned set, two ligands, from empty sites

| Input | Value |
| --- | --- |
| Node `well` | V = 1.0 pL |
| Free L1, L2 at `well` | 1.6e-3 fmol, 0.9e-3 fmol |
| Set `matrix` (owner: node `well`) | N = 1445314.0 copies, ν = 1, α = 1.0 |
| Population `matrix_L1` | L1; k_on 1.2e3; k_off 0.9; initial occupancy 0.0 |
| Population `matrix_L2` | L2; k_on 5.0e2; k_off 0.15; initial occupancy 0.0 |
| dt | 0.008 s |
| Observation times | 0.2, 0.4, 0.8, 1.6, 3.2, 6.4, 12.8, 25.6, 51.2 s |
| Horizon | 51.2 s |

### W1eq: W1 started at its equilibrium

W1's totals placed at W1's R-eq root (§3.1). The references write the start:
- each population's initial occupancy B_b/S;
- each free amount n_l = N_l − Σ_{b binding l} B_b, with N_l W1's declared free amount (W1 starts
  with nothing bound).

| Input | Value |
| --- | --- |
| Everything else | as in W1 |
| Observation times | 0.8, 4.0, 8.0 s |
| Horizon | 8.0 s |

### W1p: W1 cut to 6.4 s, for the plants

| Input | Value |
| --- | --- |
| Everything else | as in W1 |
| Observation times | 0.2, 0.4, 0.8, 1.6, 3.2, 6.4 s |
| Horizon | 6.4 s |

### W2: bind, wash and unbind

| Input | Value |
| --- | --- |
| Node `well` | V = 1.0e6 pL (1 µL) |
| Free L1 at `well` | 50.0 fmol |
| Free L2 at `well` | at its trace: 1.0e-6 fmol |
| Set `matrix` (owner: node `well`) | N = 15055351900.0 copies, ν = 1, α = 1.0 |
| Population `matrix_L1` | L1; k_on 1.2e4; k_off 0.6; initial occupancy 0.5 |
| Population `matrix_L2` | L2; k_on 1.5e4; k_off 0.12; initial occupancy 0.0 |
| The wash | t = 4.0 s, node `well`, f = 0.5; buffer L1 1.0e-12 mM, L2 1.6e-4 mM |
| dt | 0.0125 s |
| Observation times | 2.0, 4.0, 4.0125, 5.0, 7.5, 10.0, 20.0, 40.0, 60.0, 75.0 s |
| Horizon | 75.0 s |

- L1 starts at its own equilibrium: its free concentration is its K.
- The row at 4.0 s holds the state the wash acts on. The wash is applied at the start of the step
  leaving 4.0 s, so 4.0125 s is the first row after it.

### W3: a set with three ligands, a second set at the same node, and a set inside a cell

| Input | Value |
| --- | --- |
| Node `well` | V = 1.0 pL; free L1 2.0e-3, L2 1.5e-3, L3 1.0e-3 fmol |
| Cell `specimen` | V = 1.0 pL; free L4 1.0e-3, L5 2.0e-3 fmol |
| Set `A` (owner: node `well`) | N = 2000000.0, ν = 2, α = 0.75 |
| Populations on `A` | `A_L1`: L1, k_on 2.0e3, k_off 2.0, occupancy 0.2. `A_L2`: L2, k_on 1.0e3, k_off 0.5, occupancy 0.1. `A_L3`: L3, k_on 2.0e3, k_off 0.4, occupancy 0.0 |
| Set `B` (owner: node `well`; one population) | N = 1000000.0, ν = 1, α = 0.6 |
| Population on `B` | `B_L2`: L2, k_on 3.0e3, k_off 0.3, occupancy 0.05 |
| Set `C` (owner: patch `specimen_face`, inside face, facing `specimen`) | N = 1500000.0, ν = 1, α = 1.0 |
| Populations on `C` | `C_L4`: L4, k_on 1.0e3, k_off 1.0, occupancy 0.0. `C_L5`: L5, k_on 2.0e3, k_off 0.4, occupancy 0.0 |
| dt | 0.004 s |
| Observation times | 0.1, 0.2, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 30.0 s |
| Horizon | 30.0 s |

- L2 binds both A and B from one pool.
- The patch `specimen_face` has `specimen` inside and `well` outside.

### W3p: W3 cut to 2 s, for the plants

W3's inputs, with observation times 0.1, 0.2, 0.5, 1.0 and 2.0 s and a horizon of 2.0 s. Its reference rows are W3's at those times, so it needs no file of its own.

### W4: fixed concentrations, and the engine's order

| Input | Value |
| --- | --- |
| Node `vat` | V = 1.0e9 pL (1 mL); free L1 1.2e6 fmol, L2 0.8e6 fmol |
| Set `matrix` (owner: node `vat`) | N = 1445314.0, ν = 1, α = 1.0 |
| Populations | `matrix_L1`: L1, k_on 1.2e3, k_off 0.9, occupancy 0.0. `matrix_L2`: L2, k_on 5.0e2, k_off 0.15, occupancy 0.0 |
| dt | three runs: 0.08, 0.04 and 0.02 s |
| Observation times | 0.4, 0.8, 1.2, 1.6 s |
| Horizon | 1.6 s |

### W5: the stage condition's edge

| Input | Value |
| --- | --- |
| Node `well` | V = 1.0 pL; free L1 1.0e-3, L2 1.0e-3 fmol |
| Set `matrix` (owner: node `well`) | N = 602.0, ν = 1, α = 1.0 |
| Populations | `matrix_L1`: L1, k_on 6.0e3, k_off 0.1, occupancy 0.0. `matrix_L2`: L2, k_on 6.0e3, k_off 0.1, occupancy 0.0 |
| dt | 0.1 s |
| Horizon | 1.0 s |

### W6: a set on a patch's outside face, from a partial occupancy

| Input | Value |
| --- | --- |
| Node `well` | V = 1.0 pL; free L1 1.5e-3, L2 1.0e-3 fmol |
| Set `D` (owner: patch `specimen_face`, outside face, facing `well`) | N = 1204428.0, ν = 1, α = 0.8 |
| Populations | `D_L1`: L1, k_on 1.5e3, k_off 0.75, occupancy 0.1. `D_L2`: L2, k_on 1.0e3, k_off 1.0, occupancy 0.05 |
| dt | 0.00625 s |
| Observation times | 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 25.0 s |
| Horizon | 25.0 s |

### W7: the user's example, washed (amendment 2, 24 November 2026)

| Input | Value |
| --- | --- |
| Node `well` | V = 1.0 pL |
| Free L1 (the example's A), L2 (its B) at `well` | 8.0 fmol, 4.0 fmol |
| Set `matrix` (owner: node `well`) | N = 3613284456.0 copies (S = 6.0 fmol), ν = 1, α = 1.0 |
| Population `matrix_L1` | L1; k_on 1.0; k_off 12.0; initial occupancy 0.3333333333333333 |
| Population `matrix_L2` | L2; k_on 0.25; k_off 3.0; initial occupancy 0.16666666666666666 |
| The wash | t = 1.0 s, node `well`, f = 0.5; buffer L1 1.0e-12 mM, L2 8.0 mM |
| dt | 0.0025 s (amendment 3) |
| Observation times | 0.5, 1.0, 1.0025, 1.5, 2.0, 3.0, 5.0, 8.0, 12.0 s (amendment 3) |
| Horizon | 12.0 s |

- **The start is the user's example:** B = 2.0 and 1.0 fmol, and R = 3.0 fmol.
  - Both K are 12 mM, so B_b/R_s = c_l/K_b holds at the start.
  - Both of §1.2's net fluxes are 0.0 in binary64.
- **The row at 1.0 s holds the state the wash acts on.** 1.0025 s is the first row after it
  (amendment 3).
- **§1.4's map on the start** removes exactly 4.0 fmol of L1 and 2.0 fmol of L2, and supplies
  4.0 fmol of L2.

### W7s: W7's single-ligand limit (amendment 2)

| Input | Value |
| --- | --- |
| Node `well` | V = 1.0 pL; free L1 8.0 fmol |
| Set `matrix` (owner: node `well`) | as W7 |
| Population `matrix_L1` | as W7, the set's only population |
| dt | 0.0025 s (amendment 3) |
| Observation times | 0.25, 0.5, 1.0, 1.5, 2.0 s (amendment 3) |
| Horizon | 2.0 s, 47 time constants of its slowest mode (amendment 3) |

- **L2 is absent.** It sits at its trace, moved by no law, so it is left out (amendment answer 3).

**The start of every world:**
- B_b = (initial occupancy)·S_s(b);
- R_s = S_s − Σ_{b on s} B_b;
- the free amounts as declared.

## 3. What to compute (every quantity, no values here)

### 3.1 R-eq: the finite-volume equilibrium

- **For each world's subsystem at its totals,** solve every set's free sites R_s and every
  population's B_b at equilibrium:
  - B_b = N_l(b) · R_s(b) / (K_b·V_i + R_s(b)) for a ligand that binds one population;
  - in general, the system of §1.2's detailed balance with each ligand's total and each set's
    moiety.
- **The totals:**
  - W1, W1eq, W3, W6 and W7s: the start's;
  - W2: the post-wash totals, the pre-wash state through §1.4's map at 4.0 s. Because that state
    comes from R-ode, R-eq of W2 rests on R-ode's state at 4.0 s.
  - W7 (amendment 2): the post-wash totals, R-ode's state at 1.0 s through §1.4's map.
- **Every root** to at least 15 significant digits, with its residual.
- **For one set with two ligands** (W1, W1eq, W6; W2 and W7 after the wash), also the
  trigonometric root of the cubic in the free-site variable (Wang 1995). Its gap from the bracketed
  root is reported.
- **For W7 and W7s (amendment 2),** each population's occupied fraction is also reported both ways.
  - By the user's formula, θ_b = (c_b/K_b)/(1 + Σ_j c_j/K_j), from the root's free
    concentrations, over the set's populations. W7s's sum has its one term.
  - As B_b/S_s from the root.
  - Their gap is reported: a check of the reference.
- **For W1eq,** the start of §2 from the root, written with `repr`.

### 3.2 R-ode: the trajectories and each ligand's balance

- **Amended 24 November 2026 (AMENDMENT-2026-11-24.md, answers 2 and 3):**
  - `value` is the 50-digit Taylor solution, written with `repr`.
  - At every reported pair it must agree with DOP853 at rtol 10⁻¹³ within `tolerance_gap` + 10⁻¹²
    of its scale. Otherwise the world is resized before the tag.
  - An amount that no law moves (a ligand's free amount at a node that no population binds it
    from) is left out of the trajectory and of every criterion.
- **Integrate §1.2** for W1, W1eq, W1p, W2 (with §1.4's map at 4.0 s), W3, W4, W6, W7 (with §1.4's
  map at 1.0 s) and W7s, at two
  tolerances (rtol 10⁻¹² and 10⁻¹³, absolute tolerance scaled to each amount).
- **Report at every observation time:** every free amount, every R_s and every B_b, with the gap
  between the two tolerances. A gap above 10⁻¹⁰ of the observable's scale (CRITERIA.md) is
  reported, not hidden.
- **Each ligand's balance:**
  - its total, free plus bound, at every observation time;
  - for W2 and W7, the wash's removed and supplied amounts of each ligand;
  - every R_s + Σ B_b.
- **The distance from R-eq at the horizon,** r_T = |x(T) − x_eq| per amount.
- **W4's closed form:** at fixed concentrations (the large-V limit), B(t) = B_eq + e^(A·t)·(B₀ − B_eq),
  with A = [[−(k₁c₁ + k₋₁), −k₁c₁], [−k₂c₂, −(k₂c₂ + k₋₂)]] and B_eq = −A⁻¹·S·(k₁c₁, k₂c₂).
  - Here k₁ and k₋₁ are matrix_L1's k_on and k_off, and k₂ and k₋₂ matrix_L2's.
  - Report it at the observation times, and its gap from R-ode, which carries the node's depletion.

### 3.3 R-dG: the shared-site heat

- **G** (§1.3) of R-ode's state at the start and at every observation time, per facing node: the
  node's pools plus the sets that face it.
- **Every interval's heat** H = G(t_k) − G(t_{k+1}), between consecutive times from the start. In
  W2 the interval across the wash (4.0 to 4.0125 s) is excluded, and in W7 the interval from 1.0 to
  1.0025 s (amendment 3).
- **The heat bound B_H of each interval** (CRITERIA.md, C3a). Its log terms take max(x, δ_x) in
  place of x, so an amount that starts at zero, such as an empty population, gives a finite
  bound.
- **The free-energy change at W2's and W7's washes** for the record, not judged: G just after
  §1.4's map minus G just before. The sets' part is zero.

### 3.4 The class of every zero-uncertainty pair

- **Classify each pair before any run,** by `validation/assembly_lineages_v2/agreement.py`'s rule
  (FR-47's): `constant`, `derived` or `spread`.
- **For a `derived` pair,** its tolerance, computed by CRITERIA.md's formula from this spec's
  inputs and R-ode's values.
- **No pair here is `spread`,** since nothing is drawn. Say so explicitly in the file.
- **The trajectory pairs carry integration error.** They are not zero-uncertainty pairs: they are
  judged by C1's band, and their class is `band`.
- **A `band` pair never reaches `agreement.judge`,** which raises on any class outside its own
  three. The judge applies C1's band to it directly.

### 3.5 The plants' predicted effects, before any run

- **For each plant** (CRITERIA.md), from the reference alone: the compared quantity as the plant
  would change it, and its distance from the honest value in units of the criterion's bound.
- **Each entry** names its compared quantity of largest distance.
- **Each entry is keyed (plant, criterion, world, time_s)** (amendment 3):
  - time_s is the state's time for a plant applied to a saved state: P5's 4.0 s on W2, and its 0.0
    and 1.0 s on W7, two entries;
  - time_s is null for a plant judged over a run.
- **W5 is a refusal world,** so its plant is sized by loads:
  - the four loads at the start, multiplied by h = dt/2: each pool's L_n, the set's L_R summed and
    per population, and each population's L_B;
  - the verdict each rule gives: refused when h·max L > 1/2.

### 3.6 W5's loads

The same loads as §3.5's, at W5's start, reported with the verdict under the summed rule and under
the per-population rule.

## 4. What the references never do

- run the engine;
- read an engine output;
- fit anything;
- round a reported value;
- report any value that this spec does not ask for.

## 5. The writer and its file

- **One JSON file per world:** `reference_W1.json`, `reference_W1eq.json`, `reference_W1p.json`,
  `reference_W2.json`, `reference_W3.json`, `reference_W4.json`, `reference_W5.json`,
  `reference_W6.json`, and (amendment 2) `reference_W7.json` and `reference_W7s.json`.
  - W7's and W7s's `"equilibrium"` also holds `"theta"`: {population: {formula, root, gap}}
    (§3.1).
- **Each file holds:**
  - `"world"`: this spec's inputs, echoed, with every capacity S_s;
  - `"equilibrium"`: {sets: {id: R}, populations: {id: B}, pools: {id: n}, residual, wang: {gap}
    where it applies};
  - `"trajectory"`: [{observable, time_s, value, tolerance_gap}, ...]. The observables are named
    `n:<ligand>@<node>`, `R:<set>` and `B:<population>`;
  - **Amended 24 November 2026 (answer 12):**
    - `"balances"` is {ligands: [...], sets: [...]};
    - `"heats"` is {intervals: [...], G: [...]};
    - `"spread"` is "none";
    - interval pairs carry `start_s` and `end_s`.
  - **The references also expose one function, G of a node's amounts per world (SPEC.md §1.3),**
    for the judge's C3b on the engine's saved states (the amendment's §2.2).
  - `"balances"`: [{ligand, time_s, total}, ...], [{set, time_s, sites}, ...]; for W2, `"wash"`:
    {ligand: {removed, supplied}};
  - `"heats"`: [{node, start_s, end_s, heat, bound}, ...] and [{node, time_s, G}, ...];
  - `"pairs"`: [{criterion, observable, time_s, class, value, tolerance}, ...]. `class` is one of
    `constant`, `derived` or `band`; a `constant` holds `value` or `"unchanged"`, and a `derived`
    holds its tolerance. With `"spread": "none"`;
  - `"distance_at_horizon"`: {observable: r_T};
  - W4: `"closed_form"`: [{observable, time_s, value, gap_from_ode}, ...];
  - W5: `"stage"`: {loads: {...}, verdict_summed, verdict_per_population};
  - `"plants"`: [{plant, criterion, world, time_s, compared, honest, planted, distance_in_bounds},
    ...], one per (plant, criterion, world, time_s) (amendment 3);
  - `"provenance"`: the references' revision, the writer's version, and the hash seeds of the
    regeneration check.
- **Floats** are written with `repr` (round-trip exact). **Times** are the inputs' floats.
- **The writer's own test** writes a file for invented inputs (other volumes, constants, counts and
  times). The judge must read that file before any engine run.
