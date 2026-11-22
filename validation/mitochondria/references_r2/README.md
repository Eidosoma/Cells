# R2: MT-1b's judged reference, a fresh code-blind integration (D280)

R2 integrates MT-1b's declared equations on its own stiff integrator. The engine's MT-1b worlds are
judged against its outputs (`docs/MITOCHONDRIA_DESIGN.md`, the MT-1b draft and the face note's
section 6). It reproduces no published model; that is MT-2's.

## Status

- **Outputs.** The committed `interface.json` and `RECEIPT.json` are the run of record of commit
  989959fe, against the world declaration's erratum 2 (tag
  `mito-mt1b-declaration-erratum-2-2026-11-22`). The results and findings below are that run's.
- **The previous run of record** (61779e22, against the declaration before erratum 2) is kept in
  its run folder. Its findings led to erratum 2.

## Independence

R2 was written from the declared documents alone, each read at its tag with `git show`:

| Document | Tag | What R2 takes from it |
| --- | --- | --- |
| `docs/MITOCHONDRIA_LAWS_APPENDIX.md` | `mito-laws-appendix-2026-11-20b` | Sections 0-10: frame B, the nine laws, their parameters (Table 1 (2006), with Pi control), the potentials, the band terms |
| `docs/MITOCHONDRIA_DESIGN.md` | `mito-mt1b-face-design-2026-11-22` | Section 7's protocol, the MT-1b draft (worlds, readouts, bands), the face note (the outer membrane per form) |
| `docs/MITOCHONDRIA_DESIGN.md` | `mito-mt1b-declaration-erratum-2026-11-22` | The world declaration (G1-G7), the face note's section 6 erratum and G5's erratum (the I_NP rule) |
| `docs/MITOCHONDRIA_DESIGN.md` | `mito-mt1b-declaration-erratum-2-2026-11-22` | Erratum 2, the declaration of record for this run: the leak's h_P, 1 pM traces, the floored bands, W3(d)'s window and timing, the judged weight |

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

The lead confirmed or ruled every reading on 22 November 2026; the world declaration and its two
errata record them:
- **The leak's and the uncoupler's P-side H+ (ruled, erratum 2 item 1).**
  - G1 prints Eq. 19 with H_e, the external H+. Both read the IMS's own free H+, h_P, following
    appendix 0: "Here every P-side quantity is the IMS's own".
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
- **W3(d)** (erratum 2, item 4):
  - state 4 runs on the held bath's O2 for 0-60 s;
  - from the ADP step at 60 s, the finite O2 node supplies O2;
  - all of (d)'s judged readouts are excluded from scoring while the matrix's free O2 is below
    1e-3 x P50. With P50 = 0.373 uM that is 0.373 nM, which the erratum prints rounded as 0.37 nM.
- **Bands** (erratum 2, item 3): band = max(relative band x |value|, floor) for the concentration
  readouts, with each floor at 0.1% of its pool. R2 reads the O2 flux's band as having no
  absolute floor: item 3 floors concentration readouts, and item 4's window covers the flux's
  vanishing tail.
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

**World (d):** state 4 on the held bath's O2 for 0-60 s. Then the ADP step at 60 s, held to 240 s,
with O2 from the finite node (6.3 nL per pL, 26 uM at 60 s).

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
  - atol = rtol x the smallest declared trace (1 pM) for every concentration, so the control is
    relative above it, trace rows included (erratum 2, item 2);
  - atol = rtol x 1 mV for dPsi;
  - the ledger states are quadratures outside the error control (atol 1). Their Jacobian columns
    are exactly zero, so their accuracy is that of the physical steps, and the energy ledger's
    closure measures it.
- **Convergence evidence:** see the next section.

## Results (run of record)

**The run.**
- **Code:** commit `989959fe5012`, frozen as a clean snapshot (patch digest of the empty diff).
- **Where:** on CPU 7, under `scripts/run_detached.sh`.
- **Cost:** 1353 s of wall time and 1353 s of CPU.
- **Receipt:** `RECEIPT.json`, which also gives the run folder under /mnt/workspaces/Cells.

**The start state** (G7 with G5's erratum).
- **Inventories:** I_N = 8.511897258107e-02 mol (L mito)^-1 and I_NP = 9.459266302585e-02.
- **Against the erratum's check value:** 4.86e-06 relative.
- **Anchor at [Pi]e = 1e-09 M:** I_N 8.511895711647e-02, pH_N 7.1418000000, outer potential 3.8e-16 mV.
- **Anchor at [Pi]e = 1e-12 M:** I_N 8.511897256562e-02, pH_N 7.1418000000, outer potential 4.0e-16 mV.
- **Anchor at [Pi]e = 1e-15 M:** I_N 8.511897258107e-02, pH_N 7.1418000000, outer potential 4.0e-16 mV.
- **The state at [Pi]e = 10 mM:**
  - dPsi 194.70538 mV; pH_N 7.072757; pH_P 7.100000; NADH 0.758667; cyt c reduced 0.113796.
  - O2 flux 1.933186e-04 mol s^-1 (L mito)^-1; K_N 0.159711 M; Pi_N 8.997248e-03 M; ATP_N 9.787392e-03 M.
  - Outer potential 8.0e-17 mV.
- **Held over 600 s at state 4:** worst 1.1e-11 of a band.

**Plateaus** at each segment's end. The drift is the worst judged readout's change over the last
10 s, over a tenth of its band. The Newton column is the worst judged distance from the algebraic
steady state with the same inventories, over the band.

| World | Segment | dPsi mV | pH_N | pH_P | NADH | cyt c red | O2 flux | outer mV | drift | Newton |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| a | state4_a | 194.7054 | 7.07276 | 7.10000 | 0.75867 | 0.11380 | 1.9332e-04 | 0.000 | 3.9e-11 | 4.5e-12 |
| a | state3 | 168.5936 | 7.09247 | 7.09604 | 0.35932 | 0.21299 | 1.6377e-03 | -0.266 | 3.4e-10 | 4.2e-12 |
| a | state4_b | 194.7054 | 7.07276 | 7.10000 | 0.75867 | 0.11380 | 1.9332e-04 | 0.000 | 3.6e-11 | 5.6e-12 |
| a | uncoupler | 100.8897 | 7.09698 | 7.10852 | 0.00000 | 0.07829 | 2.9911e-03 | 0.505 | 3.6e-09 | 7.4e-12 |
| a | inhibitor | 80.9805 | 7.09089 | 7.10718 | 0.81771 | 0.99999 | 0.0000e+00 | 0.426 | 4.6e-09 | 2.3e-12 |
| b | state4_a | 101.6904 | 7.09744 | 7.11948 | 0.00000 | 0.07859 | 2.9897e-03 | 1.152 | 1.7e-09 | 3.3e-12 |
| b | state3 | 99.7221 | 7.09737 | 7.11062 | 0.00000 | 0.07640 | 2.9898e-03 | 0.628 | 3.2e-10 | 8.8e-12 |
| b | state4_b | 101.6904 | 7.09744 | 7.11948 | 0.00000 | 0.07859 | 2.9897e-03 | 1.152 | 1.2e-09 | 8.2e-12 |
| c | state4_a | 194.7054 | 7.07276 | 7.10000 | 0.75867 | 0.11380 | 1.9332e-04 | -0.000 | 5.7e-11 | 3.6e-12 |
| c | state3 | 193.8765 | 7.07276 | 7.09092 | 0.75778 | 0.11408 | 1.9657e-04 | -0.537 | 2.5e-09 | 2.2e-11 |
| c | state4_b | 194.7054 | 7.07276 | 7.10000 | 0.75867 | 0.11380 | 1.9332e-04 | -0.000 | 3.2e-11 | 6.9e-13 |
| d | state4_a | 194.7054 | 7.07276 | 7.10000 | 0.75867 | 0.11380 | 1.9332e-04 | 0.000 | 3.9e-11 | 4.5e-12 |
| d | state3_O2_exhaustion | 32.2555 | 7.09015 | 7.11926 | 0.81745 | 1.00000 | 2.4544e-10 | 1.140 | 4.8e+04 | - |

**Excursions** of each judged readout over each segment (max - min), as input for the
registration's transient bands ("a tenth of its excursion in the step"):

| World | Segment | dpsi_mV | pH_N | pH_P | NADH_fraction | cytc_reduced_fraction | O2_flux | K_N | Pi_N | ATP_N |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| a | state4_a | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| a | state3 | 26.11 | 0.01971 | 0.008647 | 0.3994 | 0.1002 | 0.001444 | 0.006901 | 0.002309 | 0.002673 |
| a | state4_b | 26.11 | 0.01975 | 0.009423 | 0.3994 | 0.09981 | 0.001444 | 0.006901 | 0.002351 | 0.002673 |
| a | uncoupler | 93.82 | 0.03332 | 0.01814 | 0.7587 | 0.2347 | 0.005061 | 0.008921 | 0.002624 | 0.009749 |
| a | inhibitor | 113.7 | 0.01848 | 0.01762 | 0.2256 | 0.8862 | 0 | 0.006541 | 0.001234 | 0.009781 |
| b | state4_a | 93.02 | 0.03732 | 0.01948 | 0.7587 | 0.2163 | 0.004118 | 0.009368 | 0.002973 | 0.00975 |
| b | state3 | 1.969 | 0.0002871 | 0.009082 | 1.597e-08 | 0.002188 | 5.88e-06 | 2.18e-05 | 5.071e-06 | 5.63e-06 |
| b | state4_b | 1.968 | 0.0002911 | 0.009083 | 1.597e-08 | 0.002188 | 5.528e-06 | 2.18e-05 | 5.071e-06 | 5.629e-06 |
| c | state4_a | 9e-07 | 1e-09 | 0 | 5.9e-09 | 4.3e-09 | 2.16e-11 | 1e-10 | 3.3e-11 | 2.3e-11 |
| c | state3 | 0.8289 | 0.0001007 | 0.009147 | 0.000932 | 0.001903 | 8.68e-06 | 7.333e-06 | 3.821e-06 | 7.968e-06 |
| c | state4_b | 0.8289 | 0.0001019 | 0.009147 | 0.0009313 | 0.00192 | 8.885e-06 | 7.329e-06 | 3.838e-06 | 7.964e-06 |
| d | state4_a | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| d | state3_O2_exhaustion | 162.4 | 0.02519 | 0.02791 | 0.4579 | 0.8862 | 0.001637 | 0.008865 | 0.002994 | 0.009787 |

**W3(d)** (erratum 2, item 4):
- **P50:** the matrix O2 crosses 0.373 uM at 160.49 s; erratum 2 expected about 160.4 s.
- **The scoring window** (O2_N below 0.373 nM) opens at 189.20 s. It excludes 102 output times
  of world (d) from every score.

**The uncoupler and the inhibitor** (G1's stall check):
- **uncoupler:** dPsi 100.8897 mV, against the synthase's stall at 101.2566 mV (-0.3669). J_F1 = -2.6148e-04, J_ANT = -2.6148e-04: synthase reversed True.
- **inhibitor:** dPsi 80.9805 mV, against the synthase's stall at 85.5584 mV (-4.5779). J_F1 = -3.9477e-04, J_ANT = -3.9477e-04: synthase reversed True.

**Convergence.**
- Each Radau tolerance and BDF is compared with Radau at rtol 1e-12 over every output time of
  every world.
- The table gives the worst judged readout's error over its plateau band. That is the strictest
  scale: transient bands are larger.

| Run | World a | World b | World c | World d |
| --- | --- | --- | --- | --- |
| Radau 1e-06 | 1.1e-03 (O2_flux) | 1.0e-03 (O2_flux) | 5.0e-04 (O2_flux) | 5.5e-02 (O2_flux) |
| Radau 1e-07 | 9.8e-05 (O2_flux) | 9.5e-05 (O2_flux) | 8.3e-05 (O2_flux) | 6.4e-03 (O2_flux) |
| Radau 1e-08 | 1.1e-05 (O2_flux) | 1.4e-05 (O2_flux) | 1.0e-05 (O2_flux) | 3.3e-04 (O2_flux) |
| Radau 1e-09 | 1.0e-06 (O2_flux) | 1.4e-06 (O2_flux) | 1.4e-06 (O2_flux) | 1.5e-05 (O2_flux) |
| Radau 1e-10 | 1.1e-07 (O2_flux) | 1.3e-07 (O2_flux) | 7.4e-08 (O2_flux) | 7.5e-07 (O2_flux) |
| Radau 1e-11 | 7.9e-09 (O2_flux) | 1.1e-08 (O2_flux) | 1.1e-08 (O2_flux) | 4.4e-08 (O2_flux) |
| BDF 1e-10 | 2.8e-06 (O2_flux) | not run (see failed runs) | 2.7e-06 (O2_flux) | 2.8e-06 (O2_flux) |

**Ledgers** over every output time, per run part:
- each invariant's drift is taken over the magnitude of its terms;
- the energy residual (A - A_0) + D - W is taken over the dissipation D.

| World | Part | Worst invariant drift | Energy residual / dissipation |
| --- | --- | --- | --- |
| a | main | 3.4e-14 (charge_NP) | 2.8e-15 |
| a | uncoupler | 4.4e-14 (charge_NP) | 2.5e-15 |
| a | inhibitor | 8.2e-14 (charge_NP) | 4.7e-15 |
| b | main | 1.2e-13 (charge_NP) | 4.0e-15 |
| c | main | 8.5e-14 (charge_NP) | 2.7e-15 |
| d | main | 2.6e-14 (charge_NP) | 1.5e-15 |

**The trace check** (G3).
- Traces 1,000 times smaller, ADP_trace 1e-15, ATP_trace 1e-15, AMP_trace 1e-15 M: the whole chain again, from the start state, scored
  with erratum 2's floored bands and its window.
- Worst judged change: 2.45e-01 of a band, so the check FAILS (it must stay below 0.1).

| World | Readout | Change / band | Where | Declared traces | Traces / 1000 |
| --- | --- | --- | --- | --- | --- |
| a | dpsi_mV | 0.044 | inhibitor, t = 307.50 s | 80.9805 | 80.9826 |
| d | dpsi_mV | 0.245 | state3_O2_exhaustion, t = 189.00 s | 37.8396 | 37.8273 |
| d | O2_flux | 0.074 | state3_O2_exhaustion, t = 189.00 s | 7.38749e-06 | 7.38694e-06 |
| d | cytc_reduced_fraction | 0.015 | state3_O2_exhaustion, t = 152.50 s | 0.811304 | 0.811311 |
| d | NADH_fraction | 0.011 | state3_O2_exhaustion, t = 158.50 s | 0.541042 | 0.541047 |
| d | pH_P | 0.011 | state3_O2_exhaustion, t = 189.00 s | 7.11808 | 7.11809 |

- **At plateau ends alone:** worst 0.0438 of a band (passes).

**The classes left undetermined at 1 nM** (erratum 2, item 4):
- a_inhibitor_branch: worst dpsi_mV 0.0438 of a band at t = 307.50 s (80.9805 against 80.9826).
- b_first_2_s: worst O2_flux 0.000112 of a band at t = 0.00 s (0.000193319 against 0.000193319).

**Plants** (each the whole chain with its overrides; caught at 3 bands):

| Plant | What | Worst change / band | Where | Caught | At plateau ends |
| --- | --- | --- | --- | --- | --- |
| P-a | the exchange's shares at 0.35 and 0.70, in Eq. 14's printed two-fraction form | 186 | world d, O2_flux, state3_O2_exhaustion, t = 189.00 s | True | 3.45 (True) |
| P-b | the exchange's activity x 1.01 | 161 | world d, O2_flux, state3_O2_exhaustion, t = 189.00 s | True | 8.5 (True) |
| P-c | the 2005 k_O2, 1.0e-6 M (appendix 9: the 2005 PDF prints 1.0e-6 for k_O2) | 1.22e+03 | world d, cytc_reduced_fraction, state3_O2_exhaustion, t = 153.50 s | True | 236 (True) |

## Findings for the registration

1. **The trace check (1 pM against 1 fM, with erratum 2's floored bands and window).**
   - **It passes at plateau ends** (worst 0.044 band), and in worlds (a)-(c) at every output time.
   - **The two classes left undetermined at 1 nM now pass:**
     - (a)'s inhibitor branch: worst dPsi 0.044 band at t = 307.5 s. Its depleted ATP_N now
       sits under its 10 uM floor.
     - (b)'s first 2 s: 1.1e-4 band. It was an effect that scales with the trace.
   - **It fails only at world (d)'s last scored outputs before the window.**
     - dPsi moves 0.245 band at t = 189.0 s (37.840 against 37.827 mV). The window opens at
       189.2 s, during the anoxic collapse of dPsi.
     - The O2 flux moves 0.074 band there.
   - **Decision for the lead:** whether the window's opening needs a margin (an earlier threshold
     or a time margin), or whether dPsi in the anoxic collapse is judged on a transient band.
2. **W3(d).**
   - The matrix O2 crosses P50 at 160.49 s; erratum 2 expected about 160.4 s.
   - The window (O2_N below 0.373 nM) opens at 189.20 s and excludes 102 output times.
   - The 0-60 s plateau meets the drift rule (3.9e-11 of a tenth band).
3. **The plants are all caught, at plateau ends alone too.**

   | Plant | At plateau ends | Readout there |
   | --- | --- | --- |
   | P-c (the 2005 k_O2) | 236 bands | (a)'s state-3 cytochrome c reduced fraction |
   | P-b (X_ANT x 1.01) | 8.5 bands | (a)'s state-3 O2 flux |
   | P-a (shares 0.35 and 0.70, printed form) | 3.45 bands | (a)'s state-3 O2 flux |

   - P-a's margin is thin.
   - Over all output times, P-a's and P-b's worst sit at (d)'s window edge (t = 189 s) and in (a)'s
     inhibitor transient.
4. **The convergence ladder is monotone.**
   - The delivered rtol 1e-11 lies within 4.4e-8 of a band of the 1e-12 run, in every world.
   - BDF, a second method, agrees within 2.8e-6 of a band in worlds (a), (c) and (d).
   - On world (b), BDF crawls from t = 43.8 s (order 1, steps of about 1e-6 s) at the 1 pM floor of
     relative control. It is recorded over its 600 s CPU budget. Radau (L-stable) runs that world
     at every rung.
5. **The start state.**
   - I_N = 0.08511897258 mol (L mito)^-1 and I_NP = 0.09459266303.
   - Erratum 2's check value, 0.0851185587, was R2's anchor at 1 nM traces. The 1 pM traces move
     the anchor by 4.9e-6 relative.
6. **The uncoupled synthase is reported, not scored** (erratum 2, item 6). dPsi 100.890 mV is
   0.367 mV below its stall, 101.257 mV, and J_F1 = -2.61e-4 mol s^-1 (L mito)^-1.
7. **I_NP's consequences, as erratum 2's item 5 states them.**
   - The outer membrane's potential ranges from -0.54 mV (control (c), state 3) to +1.15 mV
     (control (b)).
   - K_P ranges over 143-153 mM.
   - pH_P falls to 7.091 in control (c)'s state 3.
8. **The ledgers close.**
   - Each invariant drifts at most 1.2e-13 of its terms.
   - The energy residual is at most 4.7e-15 of the dissipation, in every world.
   - World (d)'s O2 bookkeeping is one function of the state across its switch at 60 s
     (989959fe).

**Runs kept in /mnt/workspaces/Cells/mito-refs-r2-20261122:**
- run-61779e22529d: the first declaration's run of record.
- run-9161a49405ed: stopped at the BDF crawl; FAILURE.json.
- run-c027381bc8c4: complete, but superseded by (d)'s ledger fix; SUPERSEDED.json.
- The development runs.
- The test's measured tier row: tiers-989959fe5012/measured.json/measured.json (2.57 s, tier 1).

## Files

| File | What it holds |
| --- | --- |
| `declaration.json` | Every number R2 integrates, each with its place in the declared documents; the readings |
| `constants.py` | The appendix's derivations at 50 digits: K_base, m, the prefactor, Delta G deg_F, the potentials, the entries, the band terms. `check_printed()` compares them with the printed values |
| `model.py` | The world: rows, the closure, the laws, the face, the right-hand side with its ledgers, the Jacobian, the free energy, the invariants and the readouts |
| `steady.py` | Steady states by Newton in ln variables with the seven inventories imposed; the continuation in [Pi]e; the anchored start state |
| `protocol.py` | The schedule (G7), the integration with restarts, the output grid, the drift rule and the ledger closure |
| `run.py` | The full run: start state, four worlds, the tolerance ladder, BDF, the trace check; writes `interface.json`, `full.npz` and `RECEIPT.json` |
| `interface.json` | The run of record's outputs, copied byte for byte (compact JSON, 3.6 MB). It holds every declared readout at G7's output times for each world; each process's dissipation and each invariant's drift over time; the start state and its anchor; the plateaus with the drift rule and the Newton check; W3(d)'s P50 crossing and window; the stall check; the convergence ladder; the trace check and the plants |
| `RECEIPT.json` | That run's receipt: the snapshot's Git revision (989959fe) and clean patch, the environment, times and the outputs' digests |

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
