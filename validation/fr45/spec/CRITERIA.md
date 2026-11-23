# FR-45's criteria, bands and plants

These are fixed before any engine run (`docs/FR45_SITE_COMPETITION_PROTOCOL.md`; D327).
- "The reference" is the references agent's file (SPEC.md §5).
- "The engine" is `site_occupancy@1` with FR-45's site sets, beside `scheduled_compartment_wash@1`
  in W2, run by `resolved_pump_composite@1` over `resolved_pump_tissue@3`.
- The pair rule is `validation/assembly_lineages_v2/agreement.py`, FR-47's (D323).

## Units

The one declared count is **copies**, a number of site-bearing units. Every amount is in **fmol**,
every volume in **pL**, every concentration in **mM**, every time in **s**, and every free energy or
heat in **pJ** (SPEC.md §0).

## The bands

- **Every criterion is deterministic.** Nothing is drawn, so there are no z bands. A criterion
  passes or fails.
- **One condition makes a criterion inconclusive: the reference's own convergence.**
  - If R-ode's two tolerances differ at a compared pair by more than 10⁻¹⁰ of its scale, the pair
    is not judged.
  - The lead resizes the world before the tag, never after a run.
- **Symbols:**
  - ε = 2⁻⁵² (binary64);
  - k_t = t/dt, the engine's steps to time t;
  - an amount's anchor a_x is its declared start value: B₀ = (occupancy)·S, R₀ = S − ΣB₀, and n₀
    the declared free amount.
- **The scales s_y:**
  - for an observable: its largest |reference value| over the start and the observation times;
  - for a heat: its node's largest |G term| (each pool's RT·n·(ln c − 1) and each set's terms),
    over the start and the times.

## The pair rule, classified from the reference before the run

| Class | The rule |
| --- | --- |
| `constant` | Every engine value equals the reference's (or, for `"unchanged"`, the engine's own value before the operation) bit for bit (`agreement.judge_constant`) |
| `derived` | A constant reached by two routes of different arithmetic: within the tolerance below, computed from the arithmetic, never fitted (`agreement.judge_derived`) |
| `band` | A trajectory value, which carries the engine's integration error: within C1's band. Not a zero-uncertainty pair |
| `spread` | None in FR-45: nothing is drawn |

No pair is excluded after the run, and no class changes after it.

## The criteria

| | Compares | Class | Test |
| --- | --- | --- | --- |
| C1 | Every free amount, R_s and B_b at every observation time (W1, W2, W3, W6), against R-ode | band | \|y_e − y_ref\| ≤ 10⁻⁶·s_y |
| C2a | The state at the horizon (W1, W2, W3, W6) against R-eq's root | derived | \|x_e(T) − x_eq\| ≤ r_T + 8ε·(\|a_x\| + \|x_eq\|), with r_T the reference's own distance at the horizon. The derivation: the scheme's fixed point is the equilibrium itself (§2.1 of the protocol), and an anchored amount resolves ε·(\|a\| + \|x\|) |
| C2b | W1eq's state at every observation time against its start, the root | derived | \|x_e(t) − x_root\| ≤ 16ε·max(\|x_root\|, \|a_x\|). The derivation: the declared start rounds once, and the scheme adds increments of the order of that rounding's rates |
| C3a | The engine's heat at each node over each interval between observation times (none across W2's wash), against R-dG | band | \|H_e − H_ref\| ≤ B_H, with B_H = 2·Σ_x (\|μ°_x\| + RT·(\|ln(x/x₀)\| + 1))·10⁻⁶·s_x, over the node's pools and sites at both ends (x₀ is V·1 mM for a pool and S for a site; μ° is 0 for pools and free sites), + 16ε·E. That is C1's band carried through G's derivatives, plus E, the interval's G terms' magnitudes |
| C3b | The same heats, against −ΔG of the engine's own saved states (§1.3's formula, on the judge's side) | derived | ≤ 16ε·k·E, with k the interval's steps |
| C3c | The sign: each node's cumulative heat never falls | derived | By more than 16ε·E between consecutive rows |
| C4a | Each ligand's books in W2, at every row: free + bound + collected − supplied | derived | Against the declared total N_l, within 16ε·(k_t + 1)·M_l, with M_l the row's free + bound + collected + supplied |
| C4b | W2's wash alone (its event map in NumPy and compiled, on the engine's saved state at 5.0 s): each free amount, and the sample and supply records | derived | Free amounts against (1 − f)·n + f·V·c_buf, within 4ε·(\|a_n\| + \|n\| + f·V·c_buf). Records against f·n and f·V·c_buf, within 2ε of each |
| C4c | W2's removed and supplied amounts against the reference's | band | Removed within f·10⁻⁶·s_n; supplied as C4b |
| C5 | Every set's R_s + Σ B_b at every row (every world) | derived | Against S_s, within 16ε·(k_t + 1)·S_s |
| C6 | W2's bound sites across the wash alone: every R_s and B_b before and after the event map, applied to the engine's saved state at 5.0 s, in NumPy and compiled | constant | `"unchanged"`: bit for bit. Saved rows are not used, since binding resumes within the step (D327) |
| C7 | W5's first step | constant | Refused by the stage condition: the engine's step report gives h·max L above 1/2 |
| C8 | W4's error e(dt), the largest \|y_e − y_ref\|/S over its observables and times, at dt = 0.1, 0.05 and 0.025 s | band | e(0.1)/e(0.05) ≥ 6 and e(0.05)/e(0.025) ≥ 6 (third order gives 8), and e(0.025) ≤ 10⁻⁶ |
| C9 | The R3 quantity `site_occupied_fraction` of every population at every saved row (W1, W3, W6), from the engine's `quantities` on the saved state | derived | Against B_b/S_s of the same state, within \|R_s + ΣB − S_s\|/S_s + 4ε |
| C10 | Every run of every world closes its own ledgers and passes its host checks on every row | constant | The run completes; the runner raises otherwise. W5 is the exception: its refusal is C7 |

## The plants

**Fixed now:**
- **Process.** Each plant runs in its own process, as a scoped patch under `validation/`, never in
  `src/`, on the plant's own world.
- **Scoring.** A plant is caught when its criterion fails, or when its run is refused by its own
  books or checks.
- **Sizing.** Each plant's effect is sized by the references before any run (SPEC.md §3.5), in units
  of its criterion's bound. Each (plant, criterion) entry names its compared quantity of largest
  distance.

| Plant | Mechanism | World | Caught by |
| --- | --- | --- | --- |
| P1 | Unshared sites: each population binds its own S_s, as if alone | W1p | C1 |
| P2 | The two populations' k_off crossed | W1p | C1 |
| P3 | Today's one-ligand lattice reused per population: each population's free sites taken as S_s − B_b in G_site | W1p | C3b, or refused by the dissipation check |
| P4 | The free-site load per population (its own k_on·c), not summed over the set | W5 | C7: the plant admits the step |
| P5 | The wash scales the bound material by (1 − f) | W2, the wash alone | C6, C4a |
| P6 | The set's ΔG_R counted once per ligand pool it binds | W1p | C3b, or refused by the energy ledger |
| P7 | A set's dR from its first population only | W3p | C5, C1 |
| P8 | The moiety checked per population (R_s + B_b = S_s for each b) | W1p | C10: refused by its own ledger |
| P9 | θ_b = B_b/(B_b + R_s) | W1p | C9 |
