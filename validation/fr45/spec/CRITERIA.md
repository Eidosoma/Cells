# FR-45's criteria, bands and plants

These are fixed before any engine run (`docs/FR45_SITE_COMPETITION_PROTOCOL.md`; D327).
**Amended 24 November 2026, before the tag** (`AMENDMENT-2026-11-24.md`):
- C3's worlds are named, and W4 leaves C3;
- C3b's free energy is the references' own;
- C3c covers the wash's interval;
- each criterion's worlds and amounts are registered there (its §3);
- no band is changed.

**Amendment 2 the same day** (`AMENDMENT-2-2026-11-24.md`), the user's acceptance targets: W7, the
user's example washed, and W7s, its single-ligand limit, enter the criteria its §3 names. Their
honest margins are below. No band is changed.

**Corrected the same day** (`NOTE-2026-11-24.md`): C4b and C6 read the engine's saved state at
4.0 s, the row the wash acts on, as the amendment's §3 registers. The rows' earlier 5.0 s was a
leftover from the first draft.

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
- **The scales:**
  - s_node, for an amount: the largest |reference value| of any amount at its facing node (that
    node's pools and the sets facing it), over the start and the observation times. The engine's
    error follows the subsystem's binding extents, not one amount's own size;
  - S, for C8: the set's capacity;
  - E, for a heat: its interval's G terms' magnitudes at both ends.

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
| C1 | Every free amount, R_s and B_b at every observation time (W1, W2, W3, W6; W7 and W7s, amendment 2), against R-ode | band | \|y_e − y_ref\| ≤ 10⁻⁶·s_node |
| C2a | The state at the horizon (W1, W2, W3, W6; W7 and W7s, amendment 2) against R-eq's root | band | \|x_e(T) − x_eq\| ≤ 10⁻⁹·s_node. A band, not a derived pair: the engine relaxes to the equilibrium of its own totals, which carry C4a's and C5's rounding, and the trajectory's decayed error remains. C2b is the derived check of the fixed point |
| C2b | W1eq's state at every observation time, and W7's at its rows before its wash (0.5 and 1.0 s; amendment 2), against its start, the root | derived | \|x_e(t) − x_root\| ≤ (2 + 3·k_t·h·L)·4ε·max(\|x_root\|, \|a_x\|), with h = dt/2 and L the largest load at the start. The derivation: the declared start rounds once (2). Each step's three stages evaluate rates whose rounding is a few ε of the largest one-way flux, so a step moves a pool by at most about 3·h·L·ε·x, with no credit for the contraction |
| C3a | The engine's heat at each node over each interval between observation times from t = 0 (none across W2's or W7's wash), against R-dG; W1, W2, W3 and W6 (amended 24 November), and W7 and W7s (amendment 2) | band | \|H_e − H_ref\| ≤ B_H, with B_H = 2·Σ_x (\|μ°_x\| + RT·(\|ln(max(x, δ)/x₀)\| + 1))·δ, + 16ε·E. The sum runs over the node's pools and sites at both ends, with δ = 10⁻⁶·s_node, C1's band. x₀ is V·1 mM for a pool and S for a site, and μ° is 0 for pools and free sites. max(x, δ) keeps the bound finite where an amount starts at zero. That is C1's band carried through G's derivatives |
| C3b | The same heats, against −ΔG of the engine's own saved states, with SPEC.md §1.3's G computed by the references' own function, not a judge-side copy (amended 24 November) | derived | ≤ 16ε·k·E, with k the interval's steps |
| C3c | The sign: each node's cumulative site heat never falls, over every interval, the wash's included; W1, W2, W3 and W6 (amended 24 November), and W7 and W7s (amendment 2) | derived | By more than 16ε·E between consecutive rows |
| C4a | Each ligand's books in W2 and W7 (amendment 2), at every row: free + bound + collected − supplied | derived | Against the declared total N_l, within 16ε·(k_t + 1)·M_l, with M_l the row's free + bound + collected + supplied |
| C4b | W2's wash alone (its event map in NumPy and compiled, on the engine's saved state at 4.0 s, the row the wash acts on): each free amount, and the sample and supply records (corrected 24 November). W7's likewise, on its saved states at 0.0 s (the user's example as declared: 4.0 fmol of L1 and 2.0 of L2 removed) and at 1.0 s, its wash row (amendment 2) | derived | Free amounts against (1 − f)·n + f·V·c_buf, within 4ε·(\|a_n\| + \|n\| + f·V·c_buf). Records against f·n and f·V·c_buf, within 2ε of each |
| C4c | W2's and W7's (amendment 2) removed and supplied amounts against the reference's | band | Removed within f·10⁻⁶·s_node; supplied as C4b |
| C5 | Every set's R_s + Σ B_b at every row (every world) | derived | Against S_s, within 16ε·(k_t + 1)·S_s |
| C6 | W2's bound sites across the wash alone: every R_s and B_b before and after the event map, applied to the engine's saved state at 4.0 s, the row the wash acts on, in NumPy and compiled (corrected 24 November). W7's likewise, on its saved states at 0.0 s and 1.0 s: all 6 fmol of sites keep their occupancy (amendment 2) | constant | `"unchanged"`: bit for bit. Saved rows are not used, since binding resumes within the step (D327) |
| C7 | W5's first step | constant | Refused by the stage condition: the engine's step report gives h·max L above 1/2 |
| C8 | W4's error e(dt), the largest \|y_e − y_ref\|/S over R and the B_b at its times, at dt = 0.08, 0.04 and 0.02 s | band | e(0.08)/e(0.04) ≥ 6 and e(0.04)/e(0.02) ≥ 6 (third order gives 8), and e(0.02) ≤ 10⁻⁶. The free amounts, near 10⁶ fmol, are left out: their binary64 spacing alone is about 10⁻⁷ of S |
| C9 | The R3 quantity `site_occupied_fraction` of every population at every saved row (W1, W3, W6; W7 and W7s, amendment 2), from the engine's `quantities` on the saved state | derived | Against B_b/S_s of the same state, within \|R_s + ΣB − S_s\|/S_s + 4ε |
| C10 | Every run of every world closes its own ledgers and passes its host checks on every row | constant | The run completes; the runner raises otherwise. W5 is the exception: its refusal is C7 |

## Honest margins, checked before the registration

A dry run of an honest emulation of the scheme, on neighbouring inputs (every constant and amount
a few percent from the registered ones, never the registered inputs themselves; the protocol's
§7), reached at most these fractions of each tolerance:

| Criterion | Largest fraction of its tolerance |
| --- | --- |
| C1 | 0.17 |
| C2a | 3.6·10⁻³ |
| C2b | 0.10 |
| C3a | 10⁻³ |
| C5 | 2·10⁻³ |
| C8 | ratios 8.35 and 8.17; e(0.02) is 2·10⁻⁷ of S |
| W7 (amendment 2) | C1 0.124; C2a 0.039; C3a and C5 negligible |
| W7s (amendment 2) | below W7's |

C2a's earlier derived form, 8ε at the horizon, failed the honest emulation at up to 141 times its
tolerance, which is why it is a band.

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
| P5 | The wash scales the bound material by (1 − f) | W2 and W7 (amendment 2), the wash alone | C6, C4a |
| P6 | The set's ΔG_R counted once per ligand pool it binds | W1p | C3b, or refused by the energy ledger |
| P7 | A set's dR from its first population only | W3p | C5, C1 |
| P8 | The moiety checked per population (R_s + B_b = S_s for each b) | W1p | C10: refused by its own ledger |
| P9 | θ_b = B_b/(B_b + R_s) | W1p | C9 |
