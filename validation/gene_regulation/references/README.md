# Gene regulation, option A: the code-blind references (G2)

These references were written from one source alone: the equation sheet
`docs/TEMPLATED_POLYMERISATION_LAWS.md` at tag `gr1-sheet-2026-11-20`. They do not read engine code
(`src/`), the sheet's own check (`validation/gene_regulation/sheet_check.py`) or the design note.
Every declared value is transcribed by hand in `sheet.py`. Nothing here imports the engine.

The sheet's §6 lists what the references compute, and this folder computes exactly that.
- **Arms:** A1 and A1-M as the sheet declares them: A1, the seven polymerase-limited worlds, the
  two-gene world and the seven ribosome-limited worlds.
- **A2:** left out, since it is development only (§5.5).
- **Potential sets:** every result is a function of the four symbols ΔG′°_ATP, E_pd, E_pep and
  E_rc/RT, run at the 50 sets of §5.6. No potential-set version is named.

## Files

| File | What it holds |
| --- | --- |
| `sheet.py` | The declared values (§0, §1.4, §5.1, §5.2, §5.3, §5.6, §6) and the 50 potential sets |
| `model.py` | The worlds and their full ODE (§4.7, assembled column by column), §6's readouts and §4.8's identities |
| `closed_forms.py` | §5.1's and §5.2's closed forms in decimal arithmetic, and §5.3's derived values |
| `noise.py` | R-noise: the exact stochastic simulation and its deterministic mean |
| `plants.py` | The sheet's eight plants, five of the references' own, and how each is compared |
| `run.py`, `assemble.py` | The driver and the writer of `interface/` |
| `checks.py` | Recomputations over `interface/`, used by `tests/unit/test_gene_regulation_references.py` |
| `interface/*.json` | The outputs (below) |

## What each reference computes

**The worlds** (§5.1, §5.2), with initial states, schedules, horizons and output grids as declared:
- A1 runs 0 to 21,600 s with outputs every 60 s. Its X switches off at t_off = 10,800 s, where the
  solver restarts.
- The seven polymerase-limited worlds and the two-gene world run 0 to 3,600 s, with outputs every
  30 s.
- The seven ribosome-limited worlds run 0 to 600 s, with outputs every 10 s. Their mRNA is held
  and written by nothing.

**The readouts** (§6), at every output, in §0's units:
- every row's amount, X's included;
- each pool's free machines F_q, each stage's complexes C_ρ,j, E_ρ and the residues in transit W_ρ;
- the cumulative extents ∫J_I, ∫S, ∫Q, ∫D and ∫J_C (the last signed);
- G(t) − G(0) and the five heat classes, in pJ;
- each move's ΔG in kJ/mol;
- u(t) in A1, and J̄ over the final window in A1-M.

**R-chain** (§5.1):
- A1's full ODE over both phases, the judge of A1's trajectories.
- §5.1's phase-1 limit, with every factor frozen at A1's start and the machines abundant. It is
  computed two ways:
  - the whole state y(t) = e^(At)(y(0) + A⁻¹b) − A⁻¹b, with e^(At) by scaling and squaring its
    Taylor series;
  - n_R and E_tx also by §5.1's own formulas through P(j, y).
- The steady states n_R*, n_P*, E_tx* and E_tl*.
- The gap: the largest |closed form − ODE| over the outputs on [0, t_off), divided by the limit's
  steady state. It is reported against ε_A1 = 2 × 10⁻³ at every set.

**R-share** (§6): the full ODE of the two-gene world and of the fourteen one-gene A1-M worlds, the
ribosome-limited ones included (reading 2). It is the judge of their trajectories.

**R-machine** (§5.2):
- J*_g = λ_g M/(1 + Σ_h λ_h τ₀,h), E*_g = J*_g τ₀,g and F* = M/(1 + Σ_h λ_h τ₀,h), with τ₀ frozen
  at each world's start.
- These are compared with R-share's J̄ over the final window and its E and F at t_end, relative,
  against ε_M = 2 × 10⁻⁴.

**R-account** (§3.4, §4.8), on every world's judged trajectory:
- the residual of every identity: the machines per pool, the residues per route, each product, the
  four moieties of §1.4 and G's identity;
- two definitions besides: W_ρ = r_ρ Σ_j (j − 1) C_ρ,j (§1.2) and E_ρ = Σ_j C_ρ,j;
- each move's ΔG at the outputs, from §3.4's formulas;
- the heat classes:
  - each rate is checked at the outputs to be non-negative;
  - each class is checked at every accepted step to be non-decreasing;
- the domain (§3.5): the largest per-residue affinity of every one-sided move, at every accepted
  step, against x_dom = −1.

**R-noise** (§6): Gillespie's direct method, in counts.
- The two worlds:
  - A1's phase 1 with the factors frozen and the machines counted;
  - the polymerase-limited world at T = 10, the control.
- The method:
  - 1,000 replicates per world;
  - each replicate has its own PCG64 stream, spawned from the recorded master seed 20261120;
  - two uniforms per event: the waiting time, then the reaction;
  - within a chain, the exiting stage is drawn in proportion to its complexes, the direct method
    over exits that share one rate.
- The deterministic mean of the same frozen system, from zero products:
  - at T = 10, the exact e^(At)y(0) in decimal arithmetic;
  - in A1, whose translation initiation is bilinear in N_R and f_rib, DOP853 at rtol 1e-13.
- The band |mean − det| ≤ 4.5 SE + 10/N is applied at every output and readout.
  - T = 10 is judged.
  - A1's gap is reported (§7, item 2).
- The replicates advance together, one event each per pass. `simulate_scalar` runs the same
  algorithm and stream one replicate at a time, and must give identical counts.

**The plants** (`plants.py`):
- The sheet's six A1 plants (§5.4) and A1-M's two (§5.2):
  - A1-M's plant 1 at its registered world, T = 5;
  - A1-M's plant 2 in every A1-M world.
- Five plants of the references' own, aimed at how the potentials enter: E_rc's sign, recharging's
  share, the degradation back term, the release's heat, and a per-chain elongation factor.
- §5.2's plant 1 at T = 10 and T = 100, where the sheet does not register it, reported for F's sign.
- Each plant is the exact edit it names and runs at the reference's tolerance at the 18 edge sets.
  It is compared with the reference at the same set:
  - the largest change in every readout, relative to its scale;
  - every identity on the plant's own trajectory;
  - the closed-form gaps against the unplanted closed forms;
  - each item the sheet names for it, with its margin.
- Margins:
  - a trajectory item's margin is its change over the references' own resolution, 10⁻⁹ of scale
    (reading 7), and the change is also given against ε_A1;
  - an identity's margin is its level over 10⁻¹²;
  - a closed-form item's margin is its gap over ε_A1 or ε_M.

## Method and precision

**The judge.** Each world's full ODE is solved by DOP853 (scipy 1.18.1) at rtol 2.5 × 10⁻¹².
- atol_i is rtol times state i's largest magnitude in a first solve at rtol 10⁻⁸.
- The states are deviations from the initial state, so a large row's small change keeps its
  digits. G(t) − G(0) is formed in the same deviation form.
- The solver restarts at every output, so each output is hit by a step and never interpolated.
- An explicit Runge–Kutta method conserves every linear invariant to rounding, so the identities
  are judged on this solve.

**Convergence** (§6). The same solve with rtol and atol 100 times tighter (2.5 × 10⁻¹⁴, just above
scipy's floor of 100 machine epsilons) changes no readout by more than 4.1e-10 of its scale (the
sheet allows 10⁻⁹). The worst case is pol T=1, set 44, C_tx_6. Every one of the 800 solves (50 sets × 16
worlds) is checked this way.

**A second method.** Radau IIA (scipy's, implicit and L-stable) runs at rtol 10⁻¹¹ at the 18 edge
sets.
- Its largest difference from the tight DOP853 solve is 1.5e-11 of the scale.
- Its identities reach 2.3e-13. Its Newton tolerance is scipy's default for that rtol, 2.2 × 10⁻⁴
  on the scaled increment's norm.

**The closed forms** are computed in Python's decimal arithmetic at 50 digits.
- At 70 digits they differ by at most 1.2e-44, relative.
- The matrix route and §5.1's scalar formulas for n_R and E_tx agree to 2.1e-67.
- The sheet asks for 10⁻¹².

**R-noise** is exact in law: the direct method, in integer counts.
- At T = 10 the deterministic mean is exact: e^(At)y(0) at 50 digits, unchanged at 70.
- A1's deterministic mean is a DOP853 solve at rtol 10⁻¹³. A solve at 10⁻¹¹ differs by 1.0e-12
  of the scale.

**§5.3.** All 33 typed derived values are reproduced to their last digit from the transcribed
declared values (`inputs.json`, `transcription_check`).

## The sheet's tolerances, and what was reached

| Sheet §6 | Tolerance | Reached |
| --- | --- | --- |
| ODE trajectories: a second solve 100× tighter | ≤ 10⁻⁹ of each readout's scale | 4.1e-10 |
| Closed forms | 10⁻¹² relative | 1.2e-44 |
| Identities (DOP853; scales of reading 1) | 10⁻¹² | 1.7e-14 (pol T=1, set 28, energy) |
| A1's limit (§5.1), every set | ε_A1 = 2 × 10⁻³ | largest gap 5.1e-4 (corner -25, -30, 0, 1) |
| A1-M's limit (§5.2), every set | ε_M = 2 × 10⁻⁴ | largest gap 5.1e-5 (rib n_R=100, corner -25, -30, 0, 1) |
| R-noise, T = 10 (judged) | 4.5 SE + 10/N at every output | 0 of 363 outside; largest ratio 0.74 |
| R-noise, A1 (reported) | the same band | 0 of 1086 outside; largest ratio 0.75 |
| The domain (§3.5) | per-residue affinity ≤ x_dom = −1 | largest -5.2120 (rib n_R=1, corner -25, -30, 0, -1, y_P at t = 1.47939 s) |
| Heats (§3.4) | non-negative and non-decreasing | smallest increment 2.0e-17 of its class; smallest rate 0 of its largest (some classes start at rest) |

## Readings

The lead accepted readings 1–8 on 20 November 2026.

1. **The identity scales (§6, "within 10⁻¹² of the conserved total").**
   - The machines and the moieties use their conserved total.
   - The residue identity uses r∫S at t_end, a product n(0) + ∫Q at t_end, and G's identity ΣH at
     t_end. G(0) is not used, since it depends on the moiety references that §3.1 cancels.
   - The identities are judged on the DOP853 solve. Radau's levels are reported beside its Newton
     tolerance.
   - An erratum candidate.
2. **R-share** includes the seven ribosome-limited worlds: R-machine needs their ODE.
3. **R-noise at T = 10** freezes the factors at that world's own start (N 5 mM): κ₀ =
   κ_tx·φ_tx(N 5 mM), and k₀_R at M 0.05 mM and the trace.
4. **R-noise's seed** is not declared. The master seed is 20261120, recorded. Each replicate's
   stream is `SeedSequence(20261120).spawn(2)[w].spawn(1000)[i]` with PCG64 (w = 0 for A1, 1 for
   T = 10). The SE uses ddof = 1.
5. **§5.4 plant 6** ("fails … the residue identity"): the references report what they find (below).
   It is an erratum candidate.
6. **§5.6's interior sample:** for each symbol in order, `random.shuffle` the 32 strata, then 32
   `random()` draws. The sheet does not fix the order of shuffles and draws, so the points differ
   from the lane's, and the interior maxima are compared loosely. The points are recorded in
   `inputs.json`. An erratum candidate.
7. **No engine tolerance is declared** (G6 registers it). A plant's change in a trajectory is
   reported against the references' resolution, 10⁻⁹ of the scale, and against ε_A1 for scale.
   - It counts as failing only above ten times that resolution, beyond the solver's noise.
   - Identities are judged against 10⁻¹², and closed forms against ε_A1 and ε_M.
8. **Minor readings:**
   - u multiplies transcription's initiation only (§5.3's λ_tx carries u₁ and β_tl does not).
   - In the two-gene world the heat classes sum over the genes.
   - "Test instances" means the numeric test instance and the same with Spirin's E_pep. Both have
     full trajectories.

The references' own readings, which needed no ruling:

9. Potentials other than the four use the test instance's convention (μ′°/RT = 0 for ADP, Pi, M
   and A) at every set. Every readout, G(t) − G(0) included, is independent of it (§3.1).
10. §6 lists the identity residuals among the readouts. The interface stores each one's level, its
    largest |residual| over its scale, because the residuals are rounding noise. Each residual can
    be recomputed from the stored trajectories, as `checks.py` does at both test instances.
11. The heats' rounding floor: each class's smallest step increment, over its t_end total, and its
    smallest rate at the outputs, over its largest, must be at least −10⁻¹². DOP853 has negative
    weights, so a rounding-level dip is possible in principle. The minima are reported.
12. The domain is checked at the initial state and at every accepted step, not only at the
    outputs.
13. The held mRNA of the ribosome-limited worlds is taken to have A1's L_R = 1200. Only its
    constant contribution to two moiety totals depends on that.
14. §5.2's plant 1 is also run at T = 10 and T = 100, where the sheet does not register it, to
    show F's sign.

## §5.6 reproduced independently

The references recompute §5.6's measured bounds from their own solves. They never read the lane's
tool or its reports.

| Key | Sheet | References | Where (references) |
| --- | --- | --- | --- |
| A1 n_R | 2.5e-4 | 2.467e-4 | corner −25, −30, ·, +1 (E_pep has no effect) |
| A1 n_P | 5.1e-4 | 5.115e-4 | corner −25, −30, 0, +1 |
| A1 E_tx | 4.4e-4 | 4.385e-4 | corner −25, −30, −25, −1 |
| A1 E_tl | 3.85e-4 | 3.850e-4 | corner −25, −30, −25, +1 |
| A1-M J | 4.6e-5 | 4.619e-5 | ribosome-limited n_R = 100 at E_pep = 0 |
| A1-M E | 3.1e-5 | 3.108e-5 | polymerase-limited T = 1, corner −25, −30, −25, +1 |
| A1-M F | 5.1e-5 | 5.104e-5 | ribosome-limited n_R = 100 at E_pep = 0 |
| A1 interior | 5.0e-4 | 4.99e-4 | interior point 18 (reading 6's points) |
| A1-M interior | 5.1e-5 | 5.10e-5 | ribosome-limited n_R = 100, interior point 18 |
| ε_A1 | 2e-3 | 2e-3 | twice 5.115e-4, rounded up |
| ε_M | 2e-4 | 2e-4 | twice 5.104e-5, rounded up |
| x_max | −5.21 | −5.2120 | ribosome-limited n_R = 1 at E_pep = 0, t ≈ 1.5 s |

Every maximum agrees with the sheet's to within 1.3%, and both ε rules give the declared bounds.
- The ribosome-limited worlds barely depend on ΔG′°_ATP, E_pd and E_rc. The corners that differ
  only in those symbols tie there, so the corner named can differ from the sheet's.
- The tie decides the named corner in two places: the sheet names −40, −30, 0, ±1 for J, F and
  x_max, where the references name −25.

## The plants

The sheet's eight plants are each caught at all 18 edge sets. Margins are the smallest over the
sets.

| Plant | Edit | What fails (smallest change, margin) |
| --- | --- | --- |
| A1-1 | m_tx = 6 | The stage occupancies by 33% (3.3 × 10⁸). E_tx by 9.6 × 10⁻⁴ of its scale (9.6 × 10⁵), n_R by 8.4 × 10⁻⁵ (8.4 × 10⁴). Its closed-form gap stays inside ε_A1 (0.49 ε_A1) |
| A1-2 | v_tx = 40 | E_tx by 25% (2.5 × 10⁸), n_R by 1.7%; the closed-form gap is 125 ε_A1 |
| A1-3 | S_tl's fuel entries 0 | ATP by 2.7%, ADP by 21%, Pi by 4.0%; G's identity at 0.97 of ΣH (9.7 × 10¹¹) |
| A1-4 | Q_tx's F_pol entry 0 | F_pol + E_tx = M_pol at 0.11 (1.1 × 10¹¹) |
| A1-5 | u² in J^I_tx | n_R and n_P by 49% (4.9 × 10⁸) |
| A1-6 | S_tl's A entry −49 | The amino-acid moiety at 5.2 × 10⁻⁴ (5.2 × 10⁸), A by 5.2 × 10⁻⁴, G's identity at 1.8 × 10⁻³. **§4.8's residue identity holds**, at 2.0 × 10⁻¹⁵ |
| A1-M 1 | J^I = λ M_q, at T = 5 | J̄ by 50% of J* (2,500 ε_M) |
| A1-M 2 | the machine not returned, every A1-M world | F + E = M at 0.90 to 1.0 (≥ 9 × 10¹¹). J̄ by at least 86% of J* (≥ 4,300 ε_M) |

The references' own plants:

| Plant | Edit | Result |
| --- | --- | --- |
| own-1 | recharging reads −E_rc | Caught at every set: G's identity at ≥ 6.1 × 10⁻⁴; int_J_C by ≥ 14%, up to 190% at a corner |
| own-2 | recharging's share 1 | Caught: int_J_C by ≥ 0.41%, n_M by ≥ 0.17% |
| own-3 | the degradation back term dropped | Caught through protein degradation: int_D_P from 2.1 × 10⁻⁸ (margin 21) to 4.8 × 10⁻³ at E_pep = 0. Never resolvable for mRNA (≤ 5 × 10⁻¹²): e^(y_R) ≤ e^(−11.6) over the ranges |
| own-4 | the release's heat not booked | Caught: G's identity at ≥ 9.5 × 10⁻⁶ |
| own-5 | a per-chain factor (1 − e^(r x)) | **Not caught at most sets.** E_tx moves by 1.3 × 10⁻¹² at the weakest set and by 1.5 × 10⁻⁵ at corner −25, −30, −25, −1, where x_tx is least negative. A power limit of A's worlds (§4.2's x is −13 to −87 per residue) |
| A1-M 1 at T ≥ 10 | not registered by the sheet | F goes negative, as §5.2 says: −0.03 copies at T = 10 and −900 copies at T = 100 |

## Findings for the sheet's lane

1. **§5.4 plant 6.** §4.8's residue identity, r∫S = W + L∫Q, holds under the edit, at 2.0 × 10⁻¹⁵:
   W_tl still gains 50 per exit and loses 400 per release. The amino-acid moiety, A and G's
   identity fail. Reading 5; the lead has passed it to the lane as an erratum.
2. **§5.4 plant 1, for G6's judged tolerance.** On the 60 s grid, m_tx = 6 moves E_tx by only 9.6 ×
   10⁻⁴ of its scale and n_R by 8.4 × 10⁻⁵. Both are below ε_A1, and the closed-form gap does not
   catch it (0.49 ε_A1). The stage occupancies (33%) catch it.
3. **§5.2 plant 2's "J̄ falls to about 0".** At n_R = 1 (λ ≈ 0.004 s⁻¹ over 600 s) J̄ is still about
   14% of J*. The plant fails F + E = M and J̄ all the same.
4. **The identity scales (reading 1) and the interior sample's call order (reading 6)** are erratum
   candidates.
5. **Power.** E_rc's effect on the dynamics is small at the test instance (E_rc/RT = 0.049). The
   corners carry the power for how E_rc enters (own-1), and for the protein back term at E_pep = 0
   (own-3).

## Regenerating, and the registration's values

```
python -m validation.gene_regulation.references.run --out DIR
python -m validation.gene_regulation.references.run --out DIR --potentials G_ATP E_pd E_pep E_rc_RT
```

The first command regenerates everything. The second runs every stage at one named set of the four
symbols, refused outside §3.3's ranges.
- Run it from a source snapshot (`validation/source_snapshot.py`), detached
  (`scripts/run_detached.sh`).
- The committed interface came from revision `cea05359`, by snapshot, as one invocation of all
  stages, on one core: 1 h 15 min of CPU, with a 169 MB memory peak.
- `inputs.json` records every invocation's revision, selected status and patch hash.

## Interface files (6.2 MB)

| File | Contents |
| --- | --- |
| `inputs.json` | The transcribed declared values, the 50 potential sets (the interior points included), worlds, methods, tolerances, R-noise's seeds, §5.3's check and provenance |
| `trajectories_test_instances.json` | Every readout on the full output grids, every world, at both test instances (sets 0 and 1) |
| `trajectories_edge_sets.json` | The 16 corners: every 10th output of the rows, F, E, W, the extents, G − G(0), the heats and J̄ |
| `endpoints.json` | Every readout at t_end (and A1's at t_off) at the 32 interior points |
| `r_chain.json` | §5.1's closed forms on [0, t_off) at the test instance, the steady states and frozen factors at every set, the gaps, and §5.6 reproduced |
| `r_machine.json` | §5.2's closed forms, the ODE's J̄, E and F, and the gaps, every set and A1-M world |
| `r_account.json` | Identity levels (DOP853, and Radau at the edge sets), the heat minima and the domain maxima, every set and world |
| `r_noise.json` | Means, SEs, deterministic means and bands at every output, with both worlds' verdicts |
| `plants.json` | Every plant run: changes, identities, gaps and the named items' margins, with a summary per plant |
| `convergence.json` | The 100× check per solve, Radau against it, and the closed forms' and R-noise's precision |
