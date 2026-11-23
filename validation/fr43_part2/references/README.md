# FR-43 part 2: the independent references

These are code-blind reference solutions for FR-43 part 2: two processes writing one shared pool,
at fixed volume (C2.3) and at changing volume (C2.6/C2.7 and C2.8). Each is computed from the
equations alone:
- `docs/TEMPLATED_POLYMERISATION_LAWS.md` §0–§2, §3.1, §3.2, §3.4 and §4.1–§4.8;
- the specification's LAWS.md and READOUTS.md, as amended on 23 November 2026;
- the declared worlds.

The code uses numpy, scipy and the standard library. Nothing here imports, runs or reads the engine,
and no engine output was seen. Readings of the specification and the declared-value checks are in
[NOTES.md](NOTES.md).

## Files

| Path | What it is |
| --- | --- |
| `fr43p2_reference.py` | The model: reading a world, the rate laws, the unsplit ODE, the readouts and the identities |
| `run_references.py` | Regenerates `out/*.json` |
| `test_fr43p2_reference.py` | The self-check (about 3 s on one core; it compiles no world) |
| `worlds/` | The specification's eight world files, verbatim |
| `out/` | The results: one file per world kind and case |

## Regenerating

From the repository root:

```
/mnt/workspaces/Cells/venv-cpu/bin/python validation/fr43_part2/references/run_references.py
/mnt/workspaces/Cells/venv-cpu/bin/python -m pytest -q validation/fr43_part2/references/test_fr43p2_reference.py
```

- `--cases C2.3-sink C2.6-swelling-cell ...` regenerates only those cases.
- `--summary` prints the results table below from `out/`.
- Each case takes 1–3 minutes on one core.
- The runner pins BLAS to one thread before numpy loads. So a regeneration on the same platform and
  library versions reproduces the files bitwise. A threaded OpenBLAS changes the step sequence in
  its last bits, and the results by about 1e-13 relative.

| Case | Serves | Output |
| --- | --- | --- |
| C2.3, sink | `C2.3-sink-dt0p5` and `-dt0p25` | `out/C2.3-sink.json` |
| C2.3, sink, planted (spend_N's k × 1.01) | the same | `out/C2.3-sink-planted.json` |
| C2.3, source | `C2.3-source-dt0p5` and `-dt0p25` | `out/C2.3-source.json` |
| C2.3, source, planted (supply_N's k × 1.01) | the same | `out/C2.3-source-planted.json` |
| C2.6 and C2.7, the swelling cell | `C2.6-swelling-cell-dt0p01` and `-dt0p005` | `out/C2.6-swelling-cell.json` |
| C2.8, the swelling pair | `C2.8-swelling-pair-sink-dt0p01` and `-dt0p005` | `out/C2.8-swelling-pair-sink.json` |

The two files of one kind differ only in the engine's step, which this calculation does not use.

Each output holds:
- `times_s`;
- every READOUTS.md quantity, under its name and in its unit;
- `method`: the integrators, their tolerances, steps and run time, and every quantity's difference
  between the primary and each second method;
- `checks`: the identities' largest residuals;
- `provenance`: the git revision, any dirty paths, and the Python, numpy and scipy versions.

## The system

One ODE holds every state together, unsplit:
- the amount n_s of every species row of the cell (fmol);
- the gene unit's free machines F_pol and complexes C_1 … C_m (fmol);
- the volume V (pL), where water is declared;
- every cumulative book as a quadrature component: the extents ∫J_I, ∫S, ∫Q, ∫D, ∫J_C and the
  network's ∫J (fmol), and the heats and works (pJ).

Concentrations are c = n/V in mM, because 1 fmol/pL = 1 mM. RT is R T with R = N_A k_B. It is in
J/mol, in Pa m³/mol (the water law) and, times 10⁻³, in pJ/fmol.

### The gene unit (`templated_polymerisation@1`)

Potentials, per molecule, over RT (§0), with c° = 1000 mM, the operator's standard concentration:

    μ_s/RT = μ°_s/RT + ln(c_s / c°)           μ°_res = μ°_R / L_R  (§3.1, no concentration term)

Rates (§4.1–§4.5), with r = L/m residues per stage:
- initiation: J_I = k_I T c₁ F_pol, with c₁ = 10¹⁵/(N_A V) mM. There is no factor, so u = 1, and
  initiation moves no row.
- elongation: J_j = κ C_j φ, with κ = v/r and φ = Π_d [c_d/(K_d + c_d)] (1 − eˣ).
  - The draws D are those the chain declares, here N.
  - x = ΔG_tx/RT = μ°_res/RT + Σ_releases ν μ/RT − Σ_draws ν μ/RT. Here that is μ°_res + 2μ_Pi − μ_N.
  - S = Σ_j J_j is every stage exit, and Q = J_m is the releases.
- degradation: D = k_s n_R (1 − exp(ΔG_deg/(L RT))), with ΔG_deg = L μ_M − μ_R.
- recharging: J_C = V V_C Π_s [c_s/(K_s + c_s)] (1 − exp(ΔG_rc/(2RT))).
  - The saturations are on M and ATP.
  - ΔG_rc = μ_N + 2μ_ADP − μ_M − 2μ_ATP.

Equations of motion (§4.7):

    dF/dt = Q − J_I        dC_1/dt = J_I − J_1        dC_j/dt = J_(j−1) − J_j   (j = 2 … m)
    dn_N/dt = −r S + J_C (+ the network)               dn_Pi/dt = 2 r S
    dn_R/dt = Q − D        dn_M/dt = L D − J_C         dn_ATP/dt = −2 J_C        dn_ADP/dt = 2 J_C

The heat classes (§3.4), in pJ/s:
- H_tx' = RT [r S (−x) + Q (−ln a_R)]. Every stage exit books r(−ΔG_tx), and the last also books
  −ΔG_rel = −RT ln a_R.
- H_deg' = −D ΔG_deg.
- H_rc' = −J_C ΔG_rc.
- `gene_heat_pJ` is their sum.

The books of N (READOUTS.md, amended):
- gene_produced_N = ∫ max(J_C, 0);
- gene_consumed_N = r ∫S + ∫ max(−J_C, 0);
- their difference is ∫ (J_C − r S).

### The network (`local_species_reactions@1`)

With the network's potentials at its own c0 = 1 mM, and a = c/c0:
- driven mass action: J = m k V Π_s c_s^α_s.
  - spend_N: J = k V c_N c_X.
  - supply_N: J = k n_X.
  - It books work at the rate J ΔG_r and no heat. ΔG_r = Σ ν_s μ_s.
  - Its N goes to network_consumed_N for spend_N, or to network_produced_N for supply_N.
- the passive law: J = m V c0 k_f [a_A a_B − exp(μ°_C − μ°_A − μ°_B) a_C].
  - It books heat at the rate −J ΔG_r and no work.

### Water (`ideal_osmosis_linear_compliance_water@1`)

    Π = RT (Σ_s n_s + n_imp)/V        P = K (V/V_ref − 1) + P0        ψ = P − Π
    ψ_out = P_b − RT Σ_s c_b,s  (held)
    Q_w = 10¹⁵ A L_p a (ψ − ψ_out)  (pL/s, cell to bath)            dV/dt = −Q_w
    water's heat:  H_w' = 10⁻³ Q_w (ψ − ψ_out) ≥ 0
    the bath's work:  W_b' = 10⁻³ ψ_out (−Q_w), so W_b = 10⁻³ ψ_out (V − V0) exactly
    U(V) = 10⁻³ [K (V − V_ref)²/(2 V_ref) + P0 (V − V_ref)]   (= 0: K = P0 = 0)

### Free energy, and the identities used as checks

F(N, V) = Σ_s RT n_s [ln(n_s/V) − 1 + λ_s] runs over the species rows. λ_s = μ°_s/RT − ln c0 follows
READOUTS.md's rule (see NOTES.md).

Its derivatives are:
- ∂F/∂n_s = μ_s;
- ∂F/∂V = −10⁻³ Π;
- ∂U/∂V = 10⁻³ P;
- and §3.4 adds G_tr = μ°_res W_tx for the residues in transit, with W_tx = r Σ_j (j − 1) C_j.

Every move then changes F + U + G_tr by its own J ΔG, and water changes it by 10⁻³ ψ dV, which is
W_b' − H_w'. So the ODE satisfies, exactly:

    Δ(F + U + G_tr) = W_b + W_net − H_w − H_net − H_gene

The `checks` in each file report this identity's residual. They also report:
- C2.2's books identity, n_N(t) − n_N(0) = the gene unit's net books + the network's net books;
- §4.8's machine, residue and product identities;
- every declared moiety, with the residues in transit counted;
- the sign split's sum.

## Method and accuracy

- **The primary method.** scipy's `solve_ivp` with Radau (implicit Radau IIA, order 5) at rtol 1e-11.
  - atol is 1e-30 fmol (or pL) for the states and extents, so that the relative tolerance governs
    even the trace rows.
  - For the heats and works atol is 1e-20 pJ, because an integrand J ΔG starting at exactly 0 has
    roundoff in its last digits.
  - The Jacobian is by finite differences.
- **Sampling.** Each reported time is a step end: the run restarts at every reported time, and no
  dense output is used.
- **The recharging split.** A first pass locates J_C's sign changes as events, and a second pass adds
  them as step ends (see NOTES.md, reading 3).
- **The second methods.**
  - C2.3, which is stiff: Radau at rtol 1e-12, and BDF at rtol 1e-12, a different method family.
  - C2.6, which is not stiff: DOP853 at rtol 1e-13, an explicit Runge–Kutta method of order 8, and
    Radau at rtol 1e-12.
  - C2.8: its primary is Radau at rtol 1e-13, and its second methods are Radau at 1e-12 and BDF at
    1e-13.
- **Why C2.8's primary is tighter.**
  - C2.8 samples every second. From t = 1 s to t = 40 s, recharging and the stage exits run at
    3.3e-3 down to 1.4e-4 fmol/s each.
  - They cancel in the gene unit's judged net rate, J_C − r S, to between 3.3e-7 and 2.8e-10 fmol/s.
  - So that rate's absolute error is the fluxes' error, about rtol × 3e-3 fmol/s. Its pointwise
    relative error is 1e4 to 5e5 times the state's.
  - In CRITERIA.md's normalisation, by the rate's largest value of 8.07e-5 fmol/s at t = 0, its e
    at rtol 1e-11 was 1.5e-10 against Radau at 1e-13. Every other quantity was within 7e-14.
  - C2.3's samples come 30 s apart, when these fluxes are small, and there the same rate agrees to
    9.1e-12 at rtol 1e-11.
- **The accuracy measure** is e = max_i |q_second(t_i) − q_primary(t_i)| / max_i |q_primary(t_i)|,
  CRITERIA.md's normalisation.

## Results

Every file's `method.second[...].difference_from_primary` gives e per quantity, and
`method.largest_difference_e` gives the largest over the second methods. The table gives, per case:
- the primary method's steps;
- each second method's largest e, and the quantity it falls on;
- the largest identity residuals.

| Case | Primary steps | Second method: largest e (quantity) | Identities: largest residual |
| --- | --- | --- | --- |
| C2.3-sink | 10995 | Radau 1e-12: 9.1e-12 (`gene_rate_N_fmol_per_s`); BDF 1e-12: 3.1e-11 (`gene_state.releases.tx`) | books, machines, residues, products, moieties 5.8e-13 fmol; energy 2.2e-15 of scale |
| C2.3-sink-planted | 10973 | Radau 1e-12: 8.0e-12 (`gene_rate_N_fmol_per_s`); BDF 1e-12: 3.1e-11 (`gene_state.releases.tx`) | books, machines, residues, products, moieties 4.0e-13 fmol; energy 5.4e-15 of scale |
| C2.3-source | 11055 | Radau 1e-12: 3.5e-14 (`gene_rate_N_fmol_per_s`); BDF 1e-12: 3.0e-11 (`gene_state.releases.tx`) | books, machines, residues, products, moieties 5.8e-13 fmol; energy 1.3e-14 of scale |
| C2.3-source-planted | 11050 | Radau 1e-12: 6.9e-14 (`gene_state.releases.tx`); BDF 1e-12: 3.0e-11 (`gene_state.releases.tx`) | books, machines, residues, products, moieties 4.3e-13 fmol; energy 8.6e-15 of scale |

**C2.3's stated accuracy: e ≤ 3.1e-11 for every quantity.**
- For CRITERIA.md's judged quantities, the largest e over both second methods is:
  - n_N: 1e-20;
  - the gene unit's books: 2.0e-12;
  - the network's books: 1.4e-12;
  - the route rate: 2.3e-14.
- The worst differences fall on the releases and the stage-8 complexes, whose values are the
  smallest of the gene unit's state (about 1e-13 fmol). They come from BDF, the lower-order method.
- Radau at 1e-12 agrees with the primary to 9.1e-12 or better.
- One sign change of J_C is found in each case: at t = 0.047963 s in the sink and 0.047978 s in the
  source. The three methods place it within 4.1e-14 s of each other.

| Case | Primary steps | Second method: largest e (quantity) | Identities: largest residual |
| --- | --- | --- | --- |
| C2.6-swelling-cell | 2675 | DOP853 1e-13: 2.0e-14 (`water_heat_pJ`); Radau 1e-12: 1.9e-14 (`bath_water_work_pJ`) | energy 7.7e-15 of scale |

**C2.6 and C2.7's stated accuracy: e ≤ 2.0e-14 for every quantity.**
- The figures:
  - n_A, n_B: 2.8e-15;
  - n_C: 5.4e-15;
  - V: 9.4e-15;
  - F: 2.4e-15;
  - water's heat: 2.0e-14;
  - the bath's work: 1.9e-14;
  - the network's heat: 1.7e-14.
- This problem is not stiff, so the explicit DOP853 at 1e-13 is an independent check.
- C2.7's endpoint identity, F + U − F₀ − U₀ = work − heat, closes to 1.4e-11 pJ on every row. That
  is 7.7e-15 of the energy scale, 1865 pJ.
- V grows from 1 to 2.504 pL.
- The passive route reverses between t = 16 and 16.5 s: the dilution shifts A + B ⇌ C back towards
  A and B.

| Case | Primary steps | Second method: largest e (quantity) | Identities: largest residual |
| --- | --- | --- | --- |
| C2.8-swelling-pair-sink | 20399 | Radau 1e-12: 8.8e-12 (`gene_rate_N_fmol_per_s`); BDF 1e-13: 4.5e-12 (`gene_state.complexes.tx.stage_8`) | books, machines, residues, products, moieties 4.8e-13 fmol; energy 3.3e-15 of scale |

**C2.8's stated accuracy: e ≤ 8.8e-12 for every quantity.**
- For the judged quantities, the largest e over both second methods is:
  - n_N 1.1e-20, n_X 3.8e-14, n_W 2.1e-13 and V 9.5e-14;
  - the gene unit's books 9.3e-14, and the network's 2.1e-13;
  - the gene unit's rate 8.8e-12, and the network's 1.0e-20;
  - F 3.8e-14.
- The gene unit's rate is the largest only against Radau at 1e-12, whose own error it is. BDF at
  1e-13 agrees with the primary on that rate to 4.5e-12.
- Recharging runs backward until t = 0.048029 s.
- V grows from 1 to 2.5024 pL.
- The driven route's work changes sign with its ΔG. It is negative while N is plentiful, and
  slightly positive once N is spent, ending at −1.1105e-2 pJ. Its heat is 0.
