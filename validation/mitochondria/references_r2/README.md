# R2: MT-1b's judged reference, a fresh code-blind integration (D280)

R2 integrates MT-1b's declared equations on its own stiff integrator. The engine's MT-1b worlds are
judged against its outputs (`docs/MITOCHONDRIA_DESIGN.md`, the MT-1b draft and the face note's
section 6). It reproduces no published model; that is MT-2's.

## Independence

R2 was written from the declared documents alone, each read at its tag with `git show`:

| Document | Tag | What R2 takes from it |
| --- | --- | --- |
| `docs/MITOCHONDRIA_LAWS_APPENDIX.md` | `mito-laws-appendix-2026-11-20b` | Sections 0-10: frame B, the nine laws, their parameters (Table 1 (2006), with Pi control), the potentials, the band terms |
| `docs/MITOCHONDRIA_DESIGN.md` | `mito-mt1b-face-design-2026-11-22` | Section 7's protocol, the MT-1b draft (worlds, readouts, bands), the face note (the outer membrane per form) |
| `docs/MITOCHONDRIA_DESIGN.md` | `mito-mt1b-declaration-erratum-2026-11-22` | The world declaration (G1-G7), the face note's section 6 erratum and G5's erratum (the I_NP rule): the declaration of record |

R2 did not read engine code (`src/cells`), the mitochondria lane's builder branches, engine output,
`validation/mitochondria/beard2005_cardiac.py`, the source papers, or MR1's code and data (only its
README). Nothing here imports `cells`. The code uses NumPy, SciPy and the standard library's
`decimal`. Every number R2 integrates is in `declaration.json`, with its place in those documents.

## The model

Frame B (appendix section 0), per litre of mitochondria, at 298.15 K with exact SI R and F:
- **Places:** the matrix N and the IMS P are finite nodes. The held bath e has a declared free pH
  and speciation (option (a)). World (d) adds a finite O2 node. Concentrations are per litre of
  that compartment's water (W_x = 0.6435, W_i = 0.0715).
- **Rows:**
  - N: H (total), K, Mg (total), ATP, ADP, Pi, NADH, NAD, QH2, Q, O2.
  - P: H, K, Mg, ATP, ADP, AMP, Pi, O2, c2+, c3+.
  - dPsi = phi_P - phi_N.
  - Each row's valence is its base form's (design section 1.3).
- **The closure:** rapid equilibrium at N and P.
  - H+ binds HPO4 2- (k_dH), and at N the one-site buffer B_x (pK 7.10, 40 mM; G1).
  - Mg2+ binds ATP4- and ADP3-. Nothing binds AMP.
  - The free H+ and Mg2+ come from the totals by a safeguarded Newton in ln x, converged to
    rounding at every evaluation.
- **The laws:** the nine declared laws, each J = S (1 - e^x), exactly as the appendix declares them:
  - complex I;
  - complex III with phosphate control (Eq. 24 restored as phi_Pi x Eq. 7);
  - complex IV per O2 (half the printed per-pair flux);
  - synthesis, balanced in frame B;
  - the exchange (theta_P + theta_N = 1);
  - the phosphate carrier, balanced;
  - the K+/H+ exchange;
  - the held-pair supply (S_red/S_ox = 10^-0.10 r);
  - the IMS kinase in base forms, with the source's rate.
- **Other routes:**
  - The leak (Eq. 19 as G1 quotes it, P = X_Hle RT/F) and the uncoupler patch (30 times the leak,
    availability 0 or 1) are constant-field H+.
  - O2 crosses the inner membrane by neutral permeation, P_O2 A_IM (G6 (ii)).
  - Passive K+ and Mg2+ across the inner membrane are absent (G1).
- **The outer membrane:** each form of ATP, ADP, AMP and Pi, the free H+, K+ and Mg2+, and O2
  move by log-mean electrodiffusion.
  - J_f = gamma p [(c_e - c_P) + z_f v L(c_e, c_P)]: p_A for the adenylates, p_Pi for the rest
    (G4, G6).
  - v = F(phi_e - phi_P)/RT is set by zero net outer-membrane current, in closed form,
    v = -sum z_f G_f (c_e - c_P)/sum z_f^2 G_f L_f (G5).
  - The bath's supply is valued at each row's free potential (option (a)).
- **dPsi:** C_IM dPsi/dt = sum_k q_k J_k, with C_IM = 6.75e-6 mol (L mito)^-1 mV^-1.

**Ledgers.** These are quadrature states in the same integration:
- each process's dissipation, -J x (in RT), with the face per form;
- the held pair's work;
- the bath's supply;
- the outer membrane's inflow per row;
- complex IV's O2 and the supply's turnovers.

Three checks close on them:
- **Material:** NAD, Q, cytochrome c, the matrix adenylates and Mg2+, the IMS adenine and Mg2+,
  K+, phosphorus, electrons and O2. Each is judged against the magnitude of its own terms.
- **Charge:**
  - the matrix's inventory I_N = C_IM dPsi + W_x sum_N z c;
  - the matrix-plus-IMS row charge I_NP;
  - zero net outer-membrane current at every state.
- **Energy:** A(t) - A(0) + D(t) - W(t) = 0, where:
  - A is the free energy of every form at N, P (and the O2 node), plus C_IM f dPsi^2/2;
  - D is the total dissipation;
  - W is the held pair's and the bath's supply.

## Readings taken

The lead confirmed or ruled each reading on 22 November 2026, and the world declaration records it:
- **Parameters:** the Table 1 (2006) "with Pi control" column.
- **Binding:** the appendix's binding table plus B_x.
- **Absent routes:** Eq. 20 (passive K+).
- **dPsi** is free.
- **The face law and its zero-current potential:** R2's readings, confirmed. G5's erratum states
  the potential.
- **Option (a)'s valuation:** the bath's supply at the free potentials.
- **Areas:** A_IM = C/(1 uF cm^-2) exactly. The declaration prints 6.513e-8 m2 for 1 pL, rounded.
  P_O2 = 9.9e-5 m s^-1 as printed.
- **Controls (b) and (c)** run (a)'s main schedule (0-300 s) only. The branches are world (a)'s.
- **W3(d):** the O2 node is finite from t = 0.
- **The start state** (G7 with G5's erratum). R2 found a seventh conserved quantity:
  - The matrix-plus-IMS row charge, I_NP = W_x sum_N z c + W_i sum_P z c, is conserved by zero net
    outer-membrane current and no counter-ion.
  - With I_N, the matrix's charge inventory, it selects the steady state. Unanchored, it moves the
    start state by tens of bands.
  - The ruled rule:
    - I_N is set so that the state-4 steady state at [Pi]e -> 0 has pH_N = 7.1418;
    - I_NP is set by zero outer-membrane potential at that anchor, and again at the start (state 4,
      [Pi]e = 10 mM).
  - [Pi]e = 0 is taken as the limit of steady states at 1e-9, 1e-12 and 1e-15 M (Newton in ln
    variables, continued in [Pi]e). The engine computes its own start state from the same rule.

## The protocol (G7)

**World (a).**
- State 4 for 0-60 s.
- The ADP step to 1.3 mM for 60-180 s, then state 4 for 180-300 s.
- The uncoupler and inhibitor branches, 300-420 s, each from the 300 s state with the bath at
  ADP 0.5 mM and ATP 0.87 mM.

**Controls (b) and (c):** the uncoupler on, or the exchange off, from t = 0.

**World (d):** the O2 node (6.3 nL per pL, 26 uM), with the ADP step at 60 s held to 240 s.

**Outputs:** each segment's start (right limit), every 10 ms for 2 s, then every 0.5 s, and its
end (left limit).

**The drift rule:** each judged readout's change over a plateau's last 10 s, against a tenth of
its band.

## The integrator and its convergence

- **Method:** `scipy.integrate.solve_ivp` with Radau (implicit Radau IIA, order 5).
  - Each protocol segment is one call, so the solver restarts at every scheduled step.
  - Each segment runs in its own time, t - t0, since the right-hand side is autonomous. After the
    ADP step moves a trace row by many decades, the first steps can then fall far below the
    floating-point spacing of times near t0.
  - The Jacobian is by forward differences over the physical columns. The ledger columns are
    exactly zero.
  - Outputs come from the dense output at the declared times.
- **Tolerances:**
  - rtol = 1e-11 for the delivered run;
  - atol = rtol x 1e-9 M for every concentration, so the control is relative above 1e-9 M, trace
    rows included;
  - atol = rtol x 1 mV for dPsi;
  - the ledger states are quadratures outside the error control (atol 1). Their Jacobian columns
    are exactly zero, so their accuracy is that of the physical steps, and the energy ledger's
    closure measures it.
- **Convergence evidence:** see the next section.

RESULTS_PLACEHOLDER

## Files

| File | What it holds |
| --- | --- |
| `declaration.json` | Every number R2 integrates, each with its place in the declared documents; the readings |
| `constants.py` | The appendix's derivations at 50 digits: K_base, m, the prefactor, Delta G deg_F, the potentials, the entries, the band terms. `check_printed()` compares them with the printed values |
| `model.py` | The world: rows, the closure, the laws, the face, the right-hand side with its ledgers, the Jacobian, the free energy, the invariants and the readouts |
| `steady.py` | Steady states by Newton in ln variables with the seven inventories imposed; the continuation in [Pi]e; the anchored start state |
| `protocol.py` | The schedule (G7), the integration with restarts, the output grid, the drift rule and the ledger closure |
| `run.py` | The full run: start state, four worlds, the tolerance ladder, BDF, the trace check; writes `interface.json`, `full.npz` and `RECEIPT.json` |
| `interface.json` | The delivered outputs (copied from the recorded run) |
| `RECEIPT.json` | That run's receipt: the snapshot's Git revision, the environment, times and digests |

The fast test is `tests/unit/test_mito_r2_identities.py`, about 2 s of CPU. It checks:
- the declared constants;
- per-turnover material and charge;
- x two ways, within 64 eps M of the appendix's band terms;
- J x <= 0 and zero outer-membrane current;
- the pointwise energy identity;
- a 2 ms integration whose ledgers close.

## Running

Run from a frozen snapshot of the committed checkout, detached on a light CPU (AGENTS.md):

```
PY=/mnt/workspaces/Cells/venv-cpu/bin/python
$PY scripts/gates/freeze_snapshot.py <checkout> <snapshot dir> --require-clean   # or validation.source_snapshot.freeze on R2's files
scripts/run_detached.sh mito-r2 4G --cpus 7 --dir <snapshot dir> -- \
    $PY -m validation.mitochondria.references_r2.run --out <run dir>
```

`run.py --quick` runs the delivered tolerance only, as a check.
