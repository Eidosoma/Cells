# The laws (read these, not code)

Every input is in SPEC.md. Read only the sections named here, and do not follow links out of them.
Where a document also holds measured or derived values, the equations are quoted here instead.

## 0. The sheet

Read `docs/TEMPLATED_POLYMERISATION_LAWS.md` (in the Cells repository, at this folder's revision).

**Sections to read:**
- §0 to §2: the conventions, the rows, pools and forms, the moieties, and the moves;
- §3.1, §3.2 and §3.4: the potentials, the reduction, and each move's ΔG;
- §4.1 to §4.8: the rate laws (initiation, elongation's stages, release, degradation, recharging,
  the regulator and its factor), the equations of motion and the identities;
- §5.1: only its table, "The initial state", "The schedule" and "The horizon", for arm B;
- §9.1 to §9.8 (amendment R): the hold, the release law, the machine options, p, free energy and
  heat, the domain, the equations of motion, and the cohort;
- §9.9: only its addendum on R2's rows and translation, for arm B;
- §9.12 (erratum A), readings 1 to 3 and 5 to 9;
- §9.14 (erratum C);
- §9.19 (erratum F);
- §9.22 (erratum I), which governs where it differs from any earlier text.

**Sections not to read:**
- §3.3's sources table;
- §5.1's closed forms and measured bound;
- §5.2 to §5.6, §6 and §9.10;
- §9.13, §9.15 to §9.18, §9.20 and §9.21;
- any document those sections link to.

**Notes on the sheet:**
- **The cited standard free energies** of routes (`standard_free_energy` on a degradation or
  transfer) are declarations, checked against the species potentials within a rounding band. No
  rate and no booking reads them. Every rate and booking reads the potentials of SPEC.md.
- **The degradation's per-residue affinity** is y_f = (L μ_M − μ_f)/(L RT). Here μ_M and μ_f are the
  chemical potentials of the monomer and of the fate row at their current concentrations:
  μ = μ° + RT ln(c/c°), with c° = 1 M. It returns L monomers of M per molecule lost.

## 1. The membership classes (erratum I), as the label owner follows them

FR-42's label owner splits a two-sided move into its one-way parts:
- a forward move leaves the row at the row's shares;
- an arrival enters at the label in force for its source.

For the fate rows here, the arrivals and their labels are:
- a release from the hold enters at transcription's label in force at the start of its step: `pre`,
  `win` or `post`;
- a degradation's re-synthesis (its backward one-way part, k_f n_f e^(y_f)) enters at the species'
  label in force, `resyn`;
- the forward loss k_f n_f leaves at the shares.

So each class obeys its own law, with Q_f the release into fate f and k_f the declared rate:

    pool0:  dP/dt      = − k_f P,                            P(0) = n_f(0)
    resyn:  dB/dt      = k_f n_f e^(y_f) − k_f B,            B(0) = 0
    pre:    dC_pre/dt  = Q_f 1[0 ≤ t < t1]  − k_f C_pre,     0 at t = 0
    win:    dC_win/dt  = Q_f 1[t1 ≤ t < t2] − k_f C_win,     0 at t ≤ t1
    post:   dC_post/dt = Q_f 1[t ≥ t2]      − k_f C_post,    0 at t ≤ t2

- The sum P + B + C_pre + C_win + C_post equals n_f at every time.
- The net tracker of erratum I, item 6, is dC̃/dt = Q_f 1[t1 ≤ t < t2] − k_f (1 − e^(y_f)) C̃, from
  0 at t1. It is for plant sizing only.

## 2. The release and the hold (§9.2–§9.3, quoted)

    Q^d = p(t) H / τ,   Q^s = (1 − p(t)) H / τ        (fmol/s)
    dH/dt = Q_c − Q^d − Q^s                             (Q_c: transcription's completions, §4.7)

- **The machine option.**
  - `returned`: the machine returns at completion.
  - `held`: it returns at release, so the engaged machines are E = Σ_j C_j + H, and the pool's free
    machines F = M_pol − E.
- **The release's ΔG** into fate f is RT ln(c_f/c°). Its heat class is H_rel,f = ∫ Q^f (−ΔG^rel_f) dt
  (§9.5).
- **p_sched** is the value in force at the start of each step, piecewise constant between 0 and
  2700 s and after. Your exact solution switches at 2700 s.

## 3. Family C: the D152 passive law, quoted

At the cell, of volume V (pL), with a_s = c_s/c0 and c0 = 1 mM the network's standard concentration:

    J = m V c0 k_f [ prod_s a_s^(alpha_s) − exp(sum_s nu_s mu°_s/RT) prod_s a_s^(beta_s) ]   (fmol/s)

- k_f is in s⁻¹ at c0, and μ°_s/RT are the network's declared potentials (SPEC.md §1.5).
- ν_s = β_s − α_s, and the route moves n_s by ν_s J.
- **A passive route books heat** H = −dG of its moves, and no work. Here dG is the moves' change in
  Σ n_s μ_s at the network's potentials and the cell's volume.
- **For M ⇌ Mx with equal potentials:** J = m V c0 k_f (a_M − a_Mx) = m k_f (n_M − n_Mx), with
  m = 1.

## 4. Family D: water, quoted, and the current volume

The law `ideal_osmosis_linear_compliance_water@1`:

    Pi = R T (sum_s n_s + n_imp) / V           ideal van 't Hoff; every species row counts
    P  = K (V / V_ref − 1) + P0                linear compliance (here K = 0, P0 = 0)
    psi = P − Pi
    Q  = 1e15 A L_p a (psi_cell − psi_out)     pL/s from the cell to the outside
    dV/dt = −Q                                 the cell's volume (pL)
    D  = 1e-3 Q (psi_cell − psi_out) >= 0      pJ/s dissipated: water's heat is its integral

- **The bath is held:** ψ_out = P_b − R T Σ_s c_b,s is fixed, with P_b = 0.
- **The bath's work.** The water a held bath exchanges is booked as supply, with work
  1e-3 ψ_out dS (pJ, with dS in pL the bath's supply to the cell).
- **The elastic energy** U(V) is 0 here.
- **Units:** R T in J/mol, so in Pa m³/mol; Π and P in Pa; V in pL.
- **The volume bounds** are 0.5 and 3.0 pL. A state outside them is refused, never clipped.
- **What counts as an osmolyte.**
  - Every species row counts through its amount n_s: K, Y, N, M, Pi, R and R_s.
  - The gene unit's free machines, complexes, residues in transit and hold are not species rows,
    so they are not osmolytes.
- **Every rate and booking reads the current volume.**
  - **The gene unit:** initiation's template concentration c_T = T × 10¹⁵/(N_A V) mM, every
    saturation, every potential and so every ΔG.
  - **The degradation** is first order in n_f and reads V only through y_f.
  - **The release** reads V only through its ΔG.

## 5. G − G(0), the free energy the comparison reads

    G(t) = RT · { sum_rows n_r [ mu°_r + ln( n_r / (V c°) ) − 1 ]  +  mu°_res (W_tx + L H) }

- **Units.** μ° are in RT units, RT in kJ/mol, n in fmol, V in pL and c° = 1000 mM, so G is in pJ.
- **The sum** runs over the gene unit's rows: N, M and Pi, and the fates R and R_s.
  - In family C add Mx.
  - In family D take every species row, K and Y included (they move only by dilution), at the
    cell's current V. K and Y carry μ° = 0 here, which cancels in G − G(0).
- **W_tx** is the residues in transit, r Σ_j (j − 1) C_j (§4.8).
- **L H** is the hold's residues, which carry the residue's standard term and no concentration
  term (§9.5).
- **Deviation form.** Form G − G(0) so that each row's contribution,
  n_r(t)[μ°_r + ln(n_r(t)/(V(t) c°)) − 1] − n_r(0)[μ°_r + ln(n_r(0)/(V(0) c°)) − 1], keeps its digits
  when the row barely moves.
- **Family D's energy identity** adds water's heat and the bath's work:
  G(t) − G(0) + U(V) − U(V₀) + Σ heats − W_bath = 0.
- **Arm B** reports G − G(0) over the gene unit's rows (X excluded), at its fixed volume.

## 6. Route 2's host form, for plant sizing only

The engine side's route 2 is this host form, applied to the engine's own release counter A_f on
the output grid. You use it only to size P1′, on your own counters.

    known_rate(t, A, k, t1, t2, ts) = sum over outputs i with t1 <= t_i < t2 of
        (A_{i+1} − A_i) · exp(−k (ts − t_{i+1})) · (1 − exp(−k h_i)) / (k h_i),   h_i = t_{i+1} − t_i

- **Its grid error** is |known_rate on every output − known_rate on every second output, t1, t2
  and ts always kept|.
- **The net-rate form of plant P1′** is the same sum with k replaced by each interval's net
  per-molecule rate, (D_{i+1} − D_i)/∫ n dt over the interval (the trapezoid). There D is the
  fate's net loss counter, and the survivors are carried interval by interval:
  S_{i+1} = S_i e^(−k_i h_i) + ΔA_i (1 − e^(−k_i h_i))/(k_i h_i), inside the window, and the
  same without ΔA_i after it.
