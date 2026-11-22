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

The first two items are R2's own readings and go to the lead with this delivery. The lead confirmed
or ruled every other reading on 22 November 2026, and the world declaration records it:
- **The leak's and the uncoupler's P-side H+ (R2's reading; not yet put to the lead).**
  - G1 prints Eq. 19 with H_e, the external H+. R2 reads it with the IMS's own free H+, h_P,
    following appendix 0: "Here every P-side quantity is the IMS's own".
  - It is material where the IMS departs from the bath. At the uncoupled plateaus pH_P sits
    0.009-0.019 above the bath's 7.10, so the dominant flux there differs by 2-4% between the two
    readings.
- **Smaller readings, all in `declaration.json` or the code:**
  - the trace check redoes the anchor and the start state at the smaller traces. That is where
    its changes at t = 0 come from;
  - the branches' ATP bath changes only ADP and ATP. Pi, Mg2+ (total), K+ and the free pH stay as
    declared, and AMP keeps its trace;
  - each step time is output twice, as the earlier segment's end (left limit) and the later
    segment's start (right limit);
  - errors are judged against the plateau bands at every output time, transients included.
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

## Results (run of record)

**The run.**
- **Code:** commit `61779e22529d`, frozen as a clean snapshot (patch digest of the empty diff).
- **Where:** on CPU 7, under `scripts/run_detached.sh`.
- **Cost:** 860 s of wall time and 582 s of CPU.
- **Receipt:** `RECEIPT.json`, which also gives the run folder under /mnt/workspaces/Cells.

**The start state** (G7 with G5's erratum).
- **Inventories:** I_N = 8.511855873611e-02 mol (L mito)^-1 and I_NP = 9.459225452897e-02.
- **Against the erratum's check value:** 4.24e-10 relative.
- **Anchor at [Pi]e = 1e-09 M:** I_N 8.511854542095e-02, pH_N 7.1418000000, outer potential 2.0e-16 mV.
- **Anchor at [Pi]e = 1e-12 M:** I_N 8.511855872281e-02, pH_N 7.1418000000, outer potential -3.7e-16 mV.
- **Anchor at [Pi]e = 1e-15 M:** I_N 8.511855873611e-02, pH_N 7.1418000000, outer potential -3.4e-16 mV.
- **The state at [Pi]e = 10 mM:**
  - dPsi 194.70436 mV; pH_N 7.072759; pH_P 7.100000; NADH 0.758661; cyt c reduced 0.113800.
  - O2 flux 1.933402e-04 mol s^-1 (L mito)^-1; K_N 0.159710 M; Pi_N 8.997263e-03 M; ATP_N 9.787370e-03 M.
  - Outer potential 9.6e-16 mV.
- **Held over 600 s at state 4:** worst 1.2e-11 of a band.

**Plateaus** at each segment's end. The drift is the worst judged readout's change over the last
10 s, over a tenth of its band. The Newton column is the worst judged distance from the algebraic
steady state with the same inventories, over the band.

| World | Segment | dPsi mV | pH_N | pH_P | NADH | cyt c red | O2 flux | outer mV | drift | Newton |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| a | state4_a | 194.7044 | 7.07276 | 7.10000 | 0.75866 | 0.11380 | 1.9334e-04 | 0.000 | 2.5e-11 | 4.2e-12 |
| a | state3 | 168.5937 | 7.09247 | 7.09604 | 0.35932 | 0.21299 | 1.6377e-03 | -0.266 | 4.1e-10 | 2.0e-12 |
| a | state4_b | 194.7044 | 7.07276 | 7.10000 | 0.75866 | 0.11380 | 1.9334e-04 | -0.000 | 4.0e-11 | 3.7e-12 |
| a | uncoupler | 100.8893 | 7.09698 | 7.10852 | 0.00000 | 0.07829 | 2.9911e-03 | 0.505 | 1.8e-09 | 1.1e-11 |
| a | inhibitor | 80.9753 | 7.09089 | 7.10718 | 0.81771 | 0.99999 | 0.0000e+00 | 0.426 | 1.3e-09 | 1.9e-11 |
| b | state4_a | 101.6904 | 7.09744 | 7.11948 | 0.00000 | 0.07859 | 2.9897e-03 | 1.152 | 1.7e-08 | 1.2e-11 |
| b | state3 | 99.7217 | 7.09737 | 7.11061 | 0.00000 | 0.07640 | 2.9898e-03 | 0.628 | 5.0e-10 | 8.0e-12 |
| b | state4_b | 101.6904 | 7.09744 | 7.11948 | 0.00000 | 0.07859 | 2.9897e-03 | 1.152 | 2.4e-08 | 2.4e-11 |
| c | state4_a | 194.7053 | 7.07276 | 7.10000 | 0.75867 | 0.11380 | 1.9332e-04 | -0.000 | 2.0e-11 | 1.3e-12 |
| c | state3 | 193.8766 | 7.07276 | 7.09092 | 0.75778 | 0.11408 | 1.9657e-04 | -0.537 | 1.1e-09 | 4.0e-12 |
| c | state4_b | 194.7053 | 7.07276 | 7.10000 | 0.75867 | 0.11380 | 1.9332e-04 | -0.000 | 5.7e-11 | 4.1e-12 |
| d | state4_a | 194.4632 | 7.07277 | 7.10003 | 0.75873 | 0.11776 | 1.9306e-04 | 0.002 | 1.4e+01 | - |
| d | state3_O2_exhaustion | 32.2835 | 7.09015 | 7.11925 | 0.81745 | 1.00000 | 7.7899e-11 | 1.139 | 4.2e+04 | - |

**Excursions** of each judged readout over each segment (max - min), as input for the
registration's transient bands ("a tenth of its excursion in the step"):

| World | Segment | dpsi_mV | pH_N | pH_P | NADH_fraction | cytc_reduced_fraction | O2_flux | K_N | Pi_N | ATP_N |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| a | state4_a | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| a | state3 | 26.11 | 0.01971 | 0.008644 | 0.3993 | 0.1001 | 0.001444 | 0.006901 | 0.002309 | 0.002673 |
| a | state4_b | 26.11 | 0.01975 | 0.009421 | 0.3993 | 0.09981 | 0.001444 | 0.006901 | 0.002351 | 0.002673 |
| a | uncoupler | 93.82 | 0.03332 | 0.01814 | 0.7587 | 0.2347 | 0.005061 | 0.008921 | 0.002625 | 0.009749 |
| a | inhibitor | 113.7 | 0.01848 | 0.01762 | 0.2256 | 0.8862 | 0 | 0.006541 | 0.001234 | 0.009781 |
| b | state4_a | 93.01 | 0.03732 | 0.01948 | 0.7587 | 0.2163 | 0.004118 | 0.009368 | 0.002973 | 0.00975 |
| b | state3 | 1.969 | 0.0002872 | 0.009085 | 1.598e-08 | 0.002189 | 5.882e-06 | 2.183e-05 | 5.087e-06 | 5.631e-06 |
| b | state4_b | 1.969 | 0.0002912 | 0.009086 | 1.598e-08 | 0.002189 | 5.53e-06 | 2.183e-05 | 5.087e-06 | 5.63e-06 |
| c | state4_a | 0.0009157 | 2.27e-07 | 1.69e-07 | 5.845e-06 | 4.367e-06 | 2.166e-08 | 7.99e-08 | 3.339e-08 | 2.267e-08 |
| c | state3 | 0.8287 | 0.0001007 | 0.009145 | 0.0009317 | 0.001903 | 8.677e-06 | 7.331e-06 | 3.82e-06 | 7.966e-06 |
| c | state4_b | 0.8287 | 0.0001019 | 0.009144 | 0.000931 | 0.00192 | 8.882e-06 | 7.327e-06 | 3.837e-06 | 7.961e-06 |
| d | state4_a | 0.2412 | 6.876e-06 | 2.615e-05 | 6.944e-05 | 0.003956 | 2.774e-07 | 2.513e-06 | 2.613e-07 | 5.867e-06 |
| d | state3_O2_exhaustion | 162.2 | 0.02519 | 0.02789 | 0.4577 | 0.8822 | 0.001636 | 0.008862 | 0.002992 | 0.009781 |

**The uncoupler and the inhibitor** (G1's stall check):
- **uncoupler:** dPsi 100.8893 mV, against the synthase's stall at 101.2561 mV (-0.3668). J_F1 = -2.6143e-04, J_ANT = -2.6143e-04: synthase reversed True.
- **inhibitor:** dPsi 80.9753 mV, against the synthase's stall at 85.5551 mV (-4.5798). J_F1 = -3.9474e-04, J_ANT = -3.9474e-04: synthase reversed True.

**Convergence.**
- Each Radau tolerance and BDF is compared with Radau at rtol 1e-12 over every output time of
  every world.
- The table gives the worst judged readout's error over its plateau band. That is the strictest
  scale: transient bands are larger.

Per world, the worst judged error over its band, with the readout where it sits:

| Run | World a | World b | World c | World d |
| --- | --- | --- | --- | --- |
| Radau 1e-06 | 1.0e-03 (ATP_N) | 1.0e-03 (O2_flux) | 7.6e-04 (O2_flux) | 2.2e+00 (O2_flux) |
| Radau 1e-07 | 1.0e-04 (O2_flux) | 9.5e-05 (O2_flux) | 8.3e-05 (O2_flux) | 1.9e-01 (O2_flux) |
| Radau 1e-08 | 1.1e-05 (O2_flux) | 1.4e-05 (O2_flux) | 7.2e-06 (O2_flux) | 2.6e-02 (O2_flux) |
| Radau 1e-09 | 9.8e-07 (O2_flux) | 1.4e-06 (O2_flux) | 7.9e-07 (O2_flux) | 3.5e-03 (O2_flux) |
| Radau 1e-10 | 8.9e-08 (O2_flux) | 9.8e-08 (O2_flux) | 9.7e-08 (O2_flux) | 6.9e-04 (O2_flux) |
| **Radau 1e-11 (delivered)** | **1.6e-08 (ATP_N)** | **1.9e-08 (ATP_N)** | **9.1e-09 (O2_flux)** | **3.5e-05 (O2_flux)** |
| BDF 1e-10 (a second method) | 3.1e-06 (O2_flux) | 2.3e-06 (ATP_N) | 2.7e-06 (O2_flux) | 1.1e-02 (O2_flux) |

- **The error falls about tenfold per decade of rtol.** The delivered run sits within 2e-8 of a band of
  the 1e-12 run in worlds (a)-(c).
- **BDF, an independent multistep method, agrees with it** within 3e-6 of a band in (a)-(c).
- **World (d)'s worst errors sit at its anoxic tail** (t = 236-240 s).
  - There O2 is about 5e-14 M, far below the 1e-9 M floor of relative control, and the O2 flux is
    about 1e-10 mol s^-1 (L mito)^-1.
  - Up to 150 s, before exhaustion, world (d)'s error is 3.6e-7 of a band (Radau 1e-11) and 3.1e-6
    (BDF 1e-10).
- **The start state's own error,** from taking [Pi]e = 0 as a limit:
  - the start state computed from the 1e-12 M limit's I_N lies 1.8e-7 of a band from the delivered
    one, which uses the 1e-15 M limit;
  - the 1e-9 M limit's lies 1.8e-4 of a band away.
  - So the limit is converged far below the bands.

**Ledgers** over every output time, per run part:
- each invariant's drift is taken over the magnitude of its terms;
- the energy residual (A - A_0) + D - W is taken over the dissipation D.

| World | Part | Worst invariant drift | Energy residual / dissipation |
| --- | --- | --- | --- |
| a | main | 7.2e-14 (charge_NP) | 1.3e-14 |
| a | uncoupler | 6.9e-14 (charge_NP) | 1.1e-14 |
| a | inhibitor | 1.1e-13 (charge_NP) | 1.5e-14 |
| b | main | 2.6e-13 (charge_NP) | 3.1e-15 |
| c | main | 4.6e-14 (charge_NP) | 1.2e-14 |
| d | main | 1.7e-14 (charge_NP) | 1.4e-14 |

**The trace check** (G3).
- Traces 1,000 times smaller, ADP_trace 1e-12, ATP_trace 1e-12, AMP_trace 1e-12 M: the whole chain again, from the start state.
- Worst judged change: 1.39e+00 of a band, so the check FAILS (it must stay below 0.1).

| World | Readout | Change / band | Where | At 1 nM | At 1 pM |
| --- | --- | --- | --- | --- | --- |
| a | ATP_N | 0.373 | inhibitor, t = 374.50 s | 5.92585e-06 | 5.92806e-06 |
| a | O2_flux | 0.112 | state4_b, t = 181.86 s | 0.000193524 | 0.000193502 |
| a | dpsi_mV | 0.102 | inhibitor, t = 375.00 s | 80.9753 | 80.9805 |
| a | cytc_reduced_fraction | 0.014 | inhibitor, t = 300.02 s | 0.174469 | 0.174462 |
| a | NADH_fraction | 0.011 | state4_b, t = 181.12 s | 0.745282 | 0.745287 |
| b | ATP_N | 0.135 | state4_a, t = 0.88 s | 0.00017487 | 0.000174893 |
| b | O2_flux | 0.112 | state4_a, t = 0.00 s | 0.00019334 | 0.000193319 |
| b | dpsi_mV | 0.026 | state4_a, t = 0.87 s | 114.534 | 114.535 |
| b | NADH_fraction | 0.011 | state4_a, t = 0.00 s | 0.758661 | 0.758667 |
| c | O2_flux | 0.112 | state4_a, t = 0.00 s | 0.00019334 | 0.000193319 |
| c | dpsi_mV | 0.020 | state4_a, t = 0.00 s | 194.704 | 194.705 |
| c | NADH_fraction | 0.011 | state4_a, t = 0.00 s | 0.758661 | 0.758667 |
| d | O2_flux | 1.391 | state3_O2_exhaustion, t = 240.00 s | 7.78988e-11 | 7.77904e-11 |
| d | ATP_N | 0.996 | state3_O2_exhaustion, t = 175.50 s | 8.30678e-07 | 8.2985e-07 |
| d | dpsi_mV | 0.562 | state3_O2_exhaustion, t = 221.50 s | 32.2849 | 32.2567 |
| d | cytc_reduced_fraction | 0.030 | state3_O2_exhaustion, t = 145.50 s | 0.814212 | 0.814197 |
| d | pH_P | 0.025 | state3_O2_exhaustion, t = 234.50 s | 7.11925 | 7.11926 |
| d | NADH_fraction | 0.024 | state3_O2_exhaustion, t = 151.00 s | 0.529093 | 0.529081 |
| d | Pi_N | 0.015 | state3_O2_exhaustion, t = 150.50 s | 0.00792162 | 0.0079215 |

## Findings for the registration

1. **The trace check fails at the declared 1 nM.** The worst change is 1.39 bands against the
   allowed 0.1 (G3). The run of record is therefore of record for the current declaration only. A
   re-declared trace needs this run repeated (about 15 minutes on one light CPU). The convergence
   ladder covers the 1 nM world only; the smaller-trace arm ran at the delivered tolerance alone.
   What the evidence shows:
   - **Established: an effect that scales with the trace.**
     - State 4's ADP trace sustains a phosphorylation flux of about 1e-4 of respiration.
     - It moves the state-4 O2 flux by 0.11 band in every world (at t = 0, between the two
       algebraic start states), and NADH and dPsi by 0.01-0.03 band.
     - A lower trace removes it: in a development check at 1 pM against 1 fM, world (c)'s worst
       fell to 0.006 band.
   - **Established: a relative band on a vanishing readout.** In world (d) after O2 is spent:
     - O2 flux moves 1.39 band, at about 1e-10 mol s^-1 (L mito)^-1;
     - ATP_N moves 1.0 band and dPsi 0.56 band;
     - at 1 pM against 1 fM, the O2 flux still moved 0.72 band.
     - No trace level fixes this. It needs an absolute floor on the band, or an excluded window,
       and the engine-against-R2 comparison meets the same issue there.
   - **Undetermined:**
     - **(a)'s inhibitor branch:** ATP_N moves 0.37 band and dPsi 0.10 band at t = 375 s, with the
       matrix ATP near 6 uM. At 1 pM against 1 fM its worst moved, to ATP_N 0.16 band 5 s into the
       branch.
     - **(b)'s early transient:** ATP_N moves 0.14 band at 175 uM, which is not near zero. Its
       1 fM arm failed (finding 7), so it was not tested.
     - The 1 fM arm runs six decades below the relative-control floor, with no convergence
       evidence of its own.
2. **W3(d)'s O2 runs out earlier than G7 states.** G7 states that O2 crosses the P50 (0.373 uM)
   near the run's end. In R2:
   - the 6.3 nL node supplies the state-3 flux until about 150 s;
   - the matrix O2 crosses 0.373 uM at 153.3 s;
   - for the last 75 s the organelle is anoxic, with dPsi held at 32.3 mV by the reversed synthase
     until the matrix ATP is spent.
   - **W3(d)'s 0-60 s segment fails the drift rule,** at 14 times a tenth of a band. Lengthening
     cannot fix it: under the accepted reading the O2 node is finite from t = 0, so state 4 drains
     it from the start. G7 lengthens a failing plateau before registration. The lead must either
     exempt (d)'s plateaus from the rule or start the node's depletion at 60 s.
3. **The uncoupler branch reverses the synthase at steady state,** with the ATP bath (G1 (i)). The
   uncoupled plateau's dPsi, 100.89 mV, is 0.37 mV below the synthase's stall at its
   concentrations, and J_F1 = -2.6e-4 mol s^-1 (L mito)^-1. The margin is small; the reversal is
   not.
4. **I_NP's consequences, as G5's erratum states them.**
   - The outer membrane's potential moves:
     - -0.27 mV at state 3;
     - +0.51 and +0.43 mV in the uncoupler and inhibitor branches;
     - +1.15 mV in control (b);
     - -0.54 mV in control (c)'s state 3.
   - K_P moves with it: 151.6 mM at state 3, 147.1 mM uncoupled, 143.4 mM in control (b).
   - In control (c), with the exchange off, the bath's ADP gathers in the IMS. pH_P falls to 7.091 at
     state 3, since the IMS must keep its charge.
5. **Plants were not run.**
   - P-a (shares 0.35 and 0.70) cannot be planted through `declaration.json`. R2 codes the exchange
     in its declared form, which stays balanced for any shares. That plant needs the printed
     two-fraction form, as its own switch.
   - P-b (X_ANT x 1.01) and P-c (the 2005 k_O2) can be planted as parameter overrides.
6. **What `interface.json` leaves out.**
   - Per time, it carries the total dissipation, the energy residual and the two charge drifts.
   - Per run part, it carries each invariant's largest drift and the energy closure.
   - It does not carry each process's dissipation or each material row's ledger over time. The run
     folder's `full.npz` holds every state at every output time, so both can be recomputed. They
     belong in the rerun a trace ruling forces.
7. **A limit of the integrator at very low traces.**
   - At 1e-15 M, an accepted trace row can undershoot to non-positive within atol. A Jacobian is
     then evaluated at an invalid state, and SciPy refuses it. This happened in world (b) at 1 fM,
     in the development check only.
   - The run of record (1 nM and 1 pM) never met it.
   - If a lower trace is declared, the concentration floor (1e-9 M) should scale with it before the
     rerun.

## Files

| File | What it holds |
| --- | --- |
| `declaration.json` | Every number R2 integrates, each with its place in the declared documents; the readings |
| `constants.py` | The appendix's derivations at 50 digits: K_base, m, the prefactor, Delta G deg_F, the potentials, the entries, the band terms. `check_printed()` compares them with the printed values |
| `model.py` | The world: rows, the closure, the laws, the face, the right-hand side with its ledgers, the Jacobian, the free energy, the invariants and the readouts |
| `steady.py` | Steady states by Newton in ln variables with the seven inventories imposed; the continuation in [Pi]e; the anchored start state |
| `protocol.py` | The schedule (G7), the integration with restarts, the output grid, the drift rule and the ledger closure |
| `run.py` | The full run: start state, four worlds, the tolerance ladder, BDF, the trace check; writes `interface.json`, `full.npz` and `RECEIPT.json` |
| `interface.json` | The run of record's outputs, copied byte for byte (compact JSON, 3.0 MB): every declared readout at G7's output times for each world, the start state and its anchor, the plateaus with the drift rule and the Newton check, the ledgers, the stall check, the convergence ladder and the trace check |
| `RECEIPT.json` | That run's receipt: the snapshot's Git revision (61779e22) and clean patch, the environment, times and the outputs' digests |

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
