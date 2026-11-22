# Vesicle pores, Phase A: the declared laws (FR-31)

*Status: draft, 22 November 2026, by the OL builder (D287), for the lead's review and the tag
`pores-sheet-<date>`. It carries the lead's rulings of 22 November 2026: on η_m's absolute scale
(§7), the scored tolerance (§8), held-out set 2 and its scoring (§8), the extrapolation rule (§4)
and Tanaka et al. cited only (§4, §11). Nothing here is registered. §11 lists the sources still to
be read before the tag.*

**What this sheet is.**
- **Its laws.** It states Phase A's laws in physical terms only: rupture under a held tension, a
  line-tension nucleation hazard per membrane area, and the held tension as a declared boundary. A
  code-blind agent can write the references from it alone.
- **Its data.** The six points of `lean/checks/data/karal2015_rupture_rates.json` (Karal and
  Yamazaki 2015, Fig. 2a: 25 and 32 °C, 7.0, 7.5 and 8.0 mN/m) are fit rows. They are reported as
  a disclosed comparison with no pass or fail (D287).
- **Its blind test.** The held-out set is the same figure's other temperature columns. A sealed
  extractor reads them after this sheet and its test rule (§8) are tagged. The Lean lane has
  viewed the figure (D287). No Cells agent opens the paper, the figure or the papers in §11's last
  list before then.
- **Its design.** docs/VESICLE_PORES_DESIGN.md, with the user's decisions and the lead's rulings in
  D287.

**Words used.**
- **Declared:** a form or value this sheet sets. **Declared, uncited:** a declared value with no
  source; it is ours.
- **Cited:** read in a source. §11 says how each was read: directly in the full text, or through a
  summariser of its page.
- **Derived:** computed here from declared and cited values.
- **Pending:** to be read before the tag (§11).

## 0. Conventions

- **Units.** Tension σ in N/m (the data in mN/m), line tension Γ in N (pN), temperature T in K,
  rates in s⁻¹, areas in m², a membrane's surface viscosity η_m in Pa·s·m.
- **Constants.** k_B = 1.380649 × 10⁻²³ J/K and N_A = 6.02214076 × 10²³ mol⁻¹, exact (SI 2019);
  R = N_A·k_B.
- **The read temperatures.** The data file places the two columns at 10⁶/T ≈ 3356 and 3279 (T in
  K). So T₂₅ = 10⁶/3356 K = 297.97 K and T₃₂ = 10⁶/3279 K = 304.97 K (derived). These are used, not
  25 and 32 °C.
- **One composition.** Every parameter below is per lipid composition, here pure DOPC (D287: one
  line tension per composition).

## 1. The pore's energy and the barrier

A circular pore of radius r in a membrane at tension σ (cited: Evans and Smith 2011, §3.1 and
Appendix B.2; Farago and Santangelo 2005, Eqs. 1–3; Litster 1975 pending):

    E(r) = 2πrΓ − πr²σ

- The edge costs 2πrΓ. The tension's term, −πr²σ, is the mechanical work of dilation as the hole
  opens (Evans and Smith's words).
- The barrier is at r_c = Γ/σ, with height E_c = πΓ²/σ.
- Beyond r_c the pore is unstable and "will grow without bound and, ultimately, will rupture the
  membrane" (Farago and Santangelo).
- **The thermal tension scale:** σ_β = πΓ²/(k_B·T) (Evans and Smith). So E_c/k_BT = σ_β/σ.

## 2. The rupture law

**Per vesicle, at a held tension σ and temperature T** (declared form):

    k_v(σ, T) = A · j(σ, T)
    j(σ, T)   = n_s · (σ_β·σ)^(1/2) / ζ(T) · exp(−σ_β/σ)

**Where it comes from.**
- **The single-site rate is Evans and Smith's (B.2.1),** read directly: k_hole = k*₀·(σ/σ_β)^(1/2)·
  exp(−σ_β/σ), with the attempt frequency k*₀ = σ_β/ζ.
  - It is Kramers' overdamped (Smoluchowski) escape rate over the cavitation landscape of §1:
    k = (D/l₀l_ts)·exp(−E_b/k_BT), with D = k_BT/ζ.
  - The confinement near r = 0 is l₀ ≈ k_BT/(2πΓ), and the barrier's thermal width is
    l_ts ≈ (k_BT/σ)^(1/2), valid when σ_β ≫ σ (their Appendix B.1–B.2).
  - k*₀·(σ/σ_β)^(1/2) = (σ_β·σ)^(1/2)/ζ.
- **The damping is the membrane's.**
  - Evans and Smith: "fluctuations in hole radius r drive radially divergent collective flows
    impeded by a surface-shear viscosity η", and integrated over the membrane, ζ = 4π·η_m.
  - Water's friction does not take over at this size. Ryham, Berezovik and Cohen 2011 (read
    directly) give the ratio of aqueous to membrane friction on a pore as F_s/F_m = 13.475·r, with
    r in µm, for water (1 cP) and a lipid viscosity of 1 P. Aqueous friction dominates only above
    r ≈ 74 nm.
  - At the barrier, r_c = Γ/σ is about 1–2 nm for Γ ≈ 10 pN and σ ≈ 7 mN/m (derived). There the
    ratio is about 0.02, so the membrane's viscosity sets ζ.
- **Per membrane area** (D287). Evans and Smith's rate is for one nucleation site, the vesicle as a
  whole.
  - The sheet takes independent sites at a density n_s per area (declared), so a vesicle of area A
    has k_v = A·j.
  - The electroporation theory's per-area pore creation rate is the cited basis (Weaver and
    Chizmadzhev 1996; Neu and Krassowska 1999; both pending).
- **Rupture follows opening.** Under a held tension a pore past r_c grows to rupture (§1). So the
  first-rupture rate of a held vesicle is k_v.
  - Pending Zhelev and Needham 1993. Under a pipette, a pore can be stabilised as the vesicle
    loses volume and the tension relaxes. The sheet's claim holds only where the hold keeps σ
    fixed.
  - This is the data's observable: "complete aspiration of an individual vesicle marks rupture",
    and the "mean fitted rate of first rupture per intact vesicle per second" (the data file).
- **The law's domain** (declared):
  - σ_β ≫ σ, as Evans and Smith's width needs. The engine refuses a hold with σ > σ_β/4
    (declared, uncited).
  - The precursor regime of Evans and Smith's Appendix B.3, which sets the rate at high tensions,
    is not in this law.

**The engine's parameters.** Per composition, three are declared:
- ν_A, a prefactor scale;
- Γ;
- E_A, from §4.

Then:

    j(σ, T) = ν_A · σ^(1/2) · T^(−3/2) · exp(−E_A/(R·T)) · exp(−πΓ²/(σ·k_B·T))

- ν_A gathers n_s, π^(1/2), Γ, k_B^(−1/2), the 4π of ζ and η_m's scale (§4). It has units of
  m⁻²·s⁻¹·(N/m)^(−1/2)·K^(3/2).
- §8 fits ν_A and Γ. E_A is cited.

## 3. The held tension: a declared boundary (`cells.tension_hold@1`)

- **The declaration.** A tension σ_hold, in N/m, held by the boundary over a declared interval,
  whatever the vesicle's counts.
- **One tension per world in Phase A** (declared). A world with a hold refuses
  `lumen_volume: osmotic`, so the hazard reads σ_hold and nothing else. OL5's σ_max rule then
  never fires there: a declared lumen has no osmotic tension.
- **Its physical basis: a micropipette.**
  - The suction pressure ΔP sets σ = ΔP·R_p/[2(1 − R_p/R_v)] by mechanical equilibrium, with R_p
    the pipette's radius and R_v that of the vesicle's outer segment (Evans and Smith, Appendix A;
    Kwok and Evans 1981 pending).
  - "Tension clamps … held fixed until rupture" are the experiment this boundary represents (Evans
    and Smith, §2.3).
- **The work.**
  - At a held σ, the boundary does work σ·dA as a pore's area grows by dA. The vesicle's own F
    rises only by the edge energy.
  - At opening to r_c the hold supplies w = σ·πr_c² = πΓ²/σ. The vesicle's F rises by 2πr_cΓ less
    the pore's positional entropy (§7).
- **The source** (U2, D199). The hold is a work source and not passive. It names a payer and books
  a work column, as a shear's work does.
- **At rupture.** The rupture is a lysis, booked by the existing release (§6). The hold books no
  work for the pore's growth past r_c, which is not represented in an exact-event world (D287:
  rupture only there).

## 4. Temperature: the declared law (approved by the lead, 22 November 2026)

- **Γ is constant in T.** The reasons:
  - **Farago and Santangelo's correction (read directly).** It is ΔΓ = (b·k_BT/(π·l₀))·
    [ln(b·d_dB²·Γ/(k_BT·l₀)) − 2] (their Eq. 46). It rests on two undetermined constants, b ("of the
    order of unity") and l₀ ("of the order of the bilayer thickness"), and on the thermal de
    Broglie length d_dB. They give its size only as "10⁻⁷–10⁻⁶ dyn" (1–10 pN) for phospholipids at
    room temperature. No source fixes b and l₀ for DOPC.
  - **No measurement found.** A metadata search (Europe PMC, 22 November 2026) found no direct
    measurement of a pore edge tension against temperature.
  - **The classical theory** takes the edge energy as a material constant of the composition. Evans
    and Smith fit one ε per composition, at room temperature.
- **The damping's temperature: ζ ∝ η_m(T), with η_m(T) ∝ T·exp(E_A/(R·T)) and E_A = 27 kJ/mol.**
  - **The molecular-scale law.** DOPC's lipid lateral diffusion over 298–333 K has an apparent
    activation energy of 27 kJ/mol (Filippov, Orädd and Lindblom 2003, Table 1, pure DOPC; read
    directly).
  - **D to η_m.** Saffman and Delbrück's relation, D ∝ k_BT/η_m, gives η_m from D. Its slowly
    varying logarithm is neglected (declared; Saffman and Delbrück 1975 pending). Fitzgerald et
    al. 2023 (read directly) find that lipid and protein diffusion are well described through
    Saffman and Delbrück by surface viscosities of 2–4 × 10⁻¹⁰ Pa·s·m.
  - **Why the molecular scale.** The friction that damps a hole of nanometre radius acts at the
    molecular scale.
    - Fitzgerald et al. report that long-wavelength vesicle methods give membrane viscosities 20–40
      times the molecular-scale ones.
    - The molecular-scale law's range, 298–333 K, also covers both read temperatures.
- **Together.** The prefactor (σ_β·σ)^(1/2)/ζ goes as Γ·σ^(1/2)·T^(−1/2)/η_m(T). So the
  temperature enters as T^(−3/2)·exp(−E_A/RT) (derived, §2).
- **The disclosed alternative, not scored.** The long-wavelength law: η_m ∝ exp(B/T), fitted to
  DOPC GUVs over 13–23 °C by microinjection (Tanaka et al. 2025; cited only).
  - Its licence is CC BY-NC-ND, so its fitted value stays out of committed files (the lead's
    ruling, 22 November 2026).
  - The analysis takes B from the paper. It reports the alternative's predictions beside the
    scored ones, as a sensitivity, outside committed files.
- **The domain.** The scored law is declared for 298–333 K, E_A's range, read with 1 K of
  tolerance at each end (declared), so T₂₅ = 297.97 K is inside.
- **Outside it** (the lead's ruling, 22 November 2026), the law is extrapolated with the same E_A.
  - Each such point is flagged `extrapolated` in the record, and scored with the same tolerance,
    with no added allowance.
  - In-range and extrapolated verdicts are reported separately.
  - Held-out columns below 298 K are likely: FR-31 cites 12 °C survival from the same paper.

## 5. The area and the clock

- **The area A.** A = 4πR_v², with R_v the vesicles' radius. It is a declared input.
  - The sealed extractor reads the radii, or their range, from the paper's methods when it
    extracts (D287). Radii are not held out. Until then A stays symbolic.
  - **How A enters.** k_v = A·j, and the fit (§8) determines only the product A·ν_A.
  - Within one preparation A is the same at every temperature, so it cancels from every ratio
    k_v(σ, T)/k_v(σ′, T′). The blind prediction does not depend on it.
  - The engine's per-area ν_A does: ν_A = (A·ν_A)/A once R_v is read.
  - The data are cohort means over vesicles of several sizes, so a cohort's survival is a mixture
    of exponentials. The sheet uses the mean area. This is declared.
- **The clock** (cited: Anderson 2007, read directly: its Eq. 3, Definition 1 and §V).
  - Each vesicle carries the internal time H(t) = ∫₀ᵗ k_v(σ(s), T) ds and a threshold
    E = −ln u, a unit exponential. It fires when H reaches E.
  - u comes from the stream domain `pore` (7). The carrier word is the vesicle's key, and the
    counter is the vesicle's pore draws, from 0.
  - At a constant held tension H is linear, so the first-rupture time is E/k_v and the survival is
    exp(−k_v·t).
  - **Exact-event worlds.** σ is constant between events, so H is piecewise linear and the
    crossing is exact. A chemistry draw that would land after the crossing is discarded and
    counted, as at a scheduled stop.
  - **Idle chemistry.** The clock runs when no chemistry can fire. A world that declares a hold and
    the pore law does not end `inert`.
  - **The stream's identity** is recorded only by worlds that draw on it, as domains 5 and 6 are.

## 6. Fates

- **A rupture is a lysis.** It takes the existing release: the membrane's and the lumen's molecules
  to their pool places, the closure cost released, q = −ΔF + w, and reservoir work for held
  places.
- **Its record.** The end reason is `lysed`, with the cause `pore`. OL5's registered rule (σ > σ_max
  at an event's end state) stays in every world. In worlds with pores, it carries the cause
  `threshold` and its own count (D287).

## 7. The event pair (D287: opening is a pair; no second exemption)

The opening is one step between two states: closed, and an open pore at r_c.
- **Forward:** k_v, per vesicle.
- **Reverse:** P = (σ_β·σ)^(1/2)/ζ, the attempt rate at which a critical pore collapses.
- **The ratio:** ln(k_v/P) = ln(A·n_s) − σ_β/σ.
- **The contract** ln a⁺ − ln a⁻ = −(ΔF − w)/k_BT holds with:
  - ΔF = F(open) − F(closed) = 2πr_cΓ − k_BT·ln(A·n_s). That is the edge energy less the pore's
    positional entropy among the A·n_s sites.
  - w = σ·πr_c², the hold's work (§3).
  - Then −(ΔF − w)/k_BT = ln(A·n_s) − πΓ²/(σ·k_BT) (derived).
- **Where σ comes from F** (the osmotic or elastic sources of later phases), w = 0. The pore's area
  relief is then inside ΔF, to leading order in r_c/R_v.
- **In exact-event worlds** the open pore ruptures at once (§6), under the existing lysis exemption.
  So the reverse is never executed. The pair's rates are still those above, and the kernel's
  check evaluates them at probe states.
- **The absolute scale** (declared; the lead's ruling, 22 November 2026). P and ln(A·n_s) need
  η_m's absolute scale, which the fit does not give:

      η_m(T) = η₂₉₈ · (T/298.15 K) · exp[(E_A/R)·(1/T − 1/298.15 K)],   η₂₉₈ = 3 × 10⁻¹⁰ Pa·s·m

  - **Its source.** η₂₉₈ is the middle of Fitzgerald et al. 2023's molecular-scale range,
    2–4 × 10⁻¹⁰ Pa·s·m. That range fits lipid and protein diffusion through Saffman and Delbrück.
  - **What follows.** ζ(T) = 4π·η_m(T), and so P. n_s is derived from the fit once R_v is read:
    n_s = 4π·η₂₉₈·ν_A·exp(−E_A/(R·298.15 K)) / (π^(1/2)·Γ·k_B^(−1/2)·298.15 K).
  - **Its sensitivity.** P scales as 1/η₂₉₈ and A·n_s as η₂₉₈. So the opening's ΔF, and the heat
    booked at opening, move by k_BT times the logarithm of η₂₉₈'s factor.
  - **What does not depend on it:** the rate k_v, the fit, and the blind test's ratios in
    temperature and tension. The fit absorbs the scale.

## 8. The fit, and the blind test rule

**The fit rows.**
- The six points: (T₂₅, T₃₂) × (7.0, 7.5, 8.0 mN/m).
- Each has ln k_i from the data file. Its standard error is s_i = (ln_upper − ln_lower)/2, half its
  bar's cap spread; the bars are standard errors over three experiments.

**The model:**

    ln k_i = ln C + ½·ln σ_i − (3/2)·ln T_i − E_A/(R·T_i) − (π/(k_B·T_i·σ_i))·Γ²

with C = A·ν_A, and E_A = 27 kJ/mol fixed.

**The fit.**
- Weighted least squares in ln k, with weights 1/s_i², over (ln C, Γ²). The model is linear in the
  two.
- Γ is the positive root. A negative Γ² refuses the fit.
- **The covariance is the unscaled one,** (JᵀWJ)⁻¹, by the lead's ruling.
  - The in-sample misfit is known to be large (D287). Scaling the tolerance by it would loosen the
    test because the law misfits.
  - The Birge-scaled view, with the covariance scaled by max(1, χ²/4), is reported beside the
    verdict, unscored and labelled so.
- **Reported:** ln C, Γ, each point's residual in units of s_i, and χ². This is a disclosed
  comparison, with no pass or fail (D287).

**The held-out sets.**
- **Set 1: Fig. 2a's other temperature columns** (Karal and Yamazaki 2015). A test in temperature.
- **Set 2: Shibly et al. 2016** (*Biophys J* 111:2190–2201, PMC5112947; the lead's addition,
  22 November 2026). A test in tension: the law fitted at 7–8 mN/m, extrapolated down.
  - **Its conditions,** from the FR-31 search's record, which holds no results:
    - DOPC GUVs, 98 mM sucrose inside and glucose outside, in water with no buffer;
    - holds by micropipette after a 2-minute pre-hold at 0.5 mN/m, with rupture followed for up to
      6 minutes;
    - external tensions of 3.3, 3.8 and 4.3 mN/m at an osmotic difference of 2.8 mM, and 4.5, 5.0
      and 5.5 mN/m at 1.9 mM, with a control at no osmotic difference;
    - all at 25 ± 1 °C, with three experiments of 18–22 GUVs per condition.
  - The rates are tabulated in its Tables 1–2.
  - **How the osmotic condition enters.** The law reads the membrane's total tension,
    σ = σ_ex + σ_osm, and this sheet has no independent σ_osm.
    - Laplace's estimate, R·T·ΔC·R_v/2, gives tens of mN/m for R_v of order 10 µm (derived). That
      is far above the tensions at which these vesicles rupture.
    - So the stated difference does not fix σ_osm without the paper's own model, and the paper's
      estimate of it is a result.
    - **Points with no osmotic difference are scored two-sided,** at σ = σ_ex.
    - **Points under an osmotic difference are scored one-sided** (the lead's ruling, 22 November
      2026). A swelling osmotic condition only adds tension, σ_osm ≥ 0, so the read rate must lie
      at or above the law's prediction at σ_ex, less the tolerance (the rule below).
      - At stage 1 the extractor confirms from the paper's methods that the condition swells the
        vesicles. If it does not, these points are reported only.
    - **σ\*,** the tension at which the law gives each read rate, is reported, unscored. σ* − σ_ex
      is then the osmotic tension the law implies.
  - **Disclosure.** FR-31's entry quotes one survival count from Shibly et al.: 8 of 19 vesicles at
    40 s and 2 of 19 at 110 s.
    - The extractor identifies its condition, and that point is reported, not scored.
    - No Cells agent opens the paper; the sealed extractor reads it.

**The blind test, in two sealed stages** (accepted by the lead, 22 November 2026), for each
held-out set:
1. **Conditions.** The extractor reads the conditions only, and the vesicle radii for both sets:
   - set 1: each column's 10⁶/T position and its tensions;
   - set 2: the tensions, the osmotic differences, the temperature, and whether each osmotic
     condition swells the vesicles (from the methods).

   The fitted law's predictions, ln k_pred with its s_pred and s_T, are then computed, recorded and
   tagged. The references and the engine compute them independently, and must agree to 10⁻¹² in
   ln k.
2. **Values.** The extractor then reads each held-out point's rate and its standard error.

**The rule.** With the tolerance

    τ = t₀.₉₇₅,₂ · (s_read² + s_dig² + s_T² + s_pred²)^(1/2)

a held-out point scored two-sided passes when |ln k_pred − ln k_read| ≤ τ. Set 1's points and set
2's control points are scored this way. Set 2's swelling osmotic points are scored one-sided: they
pass when ln k_read ≥ ln k_pred(σ_ex) − τ.

The scored tolerance is fixed here, before either extraction (the lead's rulings, 22 November
2026):
- **t₀.₉₇₅,₂ = 4.303,** the two-sided 95% t value for three experiments per setting.
- **s_read,** the stated standard error of the point's ln k:
  - set 1: half the bar caps' spread;
  - set 2: from a tabulated rate k ± SE, s_read = SE/k.
- **s_dig,** the digitising error:
  - set 1: 0.03 in ln k, the vertical reading (declared, uncited);
  - set 2: 0 for tabulated values (declared).
- **s_T = |∂ln k/∂T|·δT,** the temperature's error.
  - ∂ln k/∂T = E_A/(RT²) + σ_β/(σT) − 3/(2T) (derived from §2 and §4). That is about 0.07 K⁻¹ at
    the fit rows.
  - Set 1: δT = 0.5 K, the column's position on the 10⁶/T axis (declared).
  - Set 2: δT = 1 K, the paper's stated 25 ± 1 °C.
- **s_pred,** the fitted law's own error at the point, from the unscaled covariance.
- **The verdicts.**
  - The law passes a held-out set when every scored point in it passes.
  - Each point's standardised difference is recorded either way.
  - Sets 1 and 2, and in-range and extrapolated points (§4), are reported separately.
- A failure is recorded, and the law ships as development status (D287).
- **Reported beside the verdict, unscored and labelled so:** the Birge-scaled view, and the
  disclosed alternative (§4).

**Disclosure.**
- The six fit rows' in-sample misfit: both classical forms fitted on the end tensions over-predict
  the read middle by 14–28% (D286, D287). This sheet's form, Evans and Smith's (B.2.1) with §4's
  temperature law, was declared before any fit with it.
- The author's earlier desk fits used the plain forms (VESICLE_PORES_DESIGN §2.1).

## 9. What the references compute

From this sheet alone, with the six fit rows and, later, the extractor's readings:
1. **The rate.** j(σ, T) and k_v = A·j at any (σ, T), from ν_A, Γ and E_A (§2, §4).
2. **The fit** (§8):
   - ln C and Γ², with their unscaled covariance;
   - χ², and each fit row's residual in units of s_i;
   - the Birge-scaled view, labelled unscored.
3. **The predictions** (§4, §8):
   - stage 1's ln k_pred, s_pred and s_T at each held-out condition of both sets, for the scored
     law;
   - the disclosed alternative's, outside committed files;
   - for set 2's osmotic points, σ* once the values are read.
4. **The survival law.** For a cohort at a constant hold, S(t) = exp(−k_v·t). A cohort's rate
   estimate is its events over its total time at risk. That estimate is the engine's
   implementation check, kept separate from the law's verdict.
5. **The pair identity.** ln(k_v/P) = ln(A·n_s) − σ_β/σ = −(ΔF − w)/k_BT, with §7's η₂₉₈.
6. **The hold's work at opening.** w = σ·πr_c² = πΓ²/σ, and the vesicle's ΔF (§3, §7).

## 10. What stays bitwise

- **Every world that declares neither a hold nor the pore law:**
  - OL1–OL5's registered sets and OL5's judged runs;
  - @1's sets;
  - G1, which has no assembly-lineage world;
  - crossrev's sets and FR's set.
- **The evidence:**
  - the invariance gate's five steps;
  - an explicit before-and-after compare of OL5's runs2 by the probe driver, which no gate runs.
- **OL5's registered lysis rule stays as registered** (§6).

## 11. Sources

**Read directly, in the full text, on 22 November 2026:**
- **Evans E, Smith BA (2011).** Kinetics of hole nucleation in biomembrane rupture. *New J Phys*
  13:095010, doi:10.1088/1367-2630/13/9/095010 (the publisher's open PDF). It gives:
  - §2.3: the tension clamps;
  - §3.1: the cavitation energy, the barrier and σ_β;
  - Appendix A: the pipette's tension;
  - Appendix B.1–B.2: Kramers' rate, (B.2.1), and ζ = 4πη.
- **Farago O, Santangelo CD (2005).** Pore formation in fluctuating membranes. *J Chem Phys*
  122:044901 (arXiv:cond-mat/0406149v1). Eqs. 1–3, 35–36 and 45–47, and the stated size of ΔΓ.
- **Ryham R, Berezovik I, Cohen FS (2011).** Aqueous viscosity is the primary source of friction in
  lipidic pore dynamics. *Biophys J* 101:2929–2938, doi:10.1016/j.bpj.2011.11.009 (PMC3244058, the
  page's text). It gives:
  - Eq. 1, C·η_s·r·r′ + 2η_m·r′ = σr − γ;
  - the leak-out, P·r³/(3η_s);
  - the friction ratio, F_s/F_m = 13.475·r.
- **Fitzgerald JE, Venable RM, Pastor RW, Lyman ER (2023).** Surface viscosities of lipid bilayers
  determined from equilibrium molecular dynamics simulations. *Biophys J*,
  doi:10.1016/j.bpj.2023.01.038 (PMC10111272, the page's text). It gives:
  - the 20–40-fold gap;
  - Saffman–Delbrück's description of lipid diffusion;
  - the molecular-scale range, 2–4 × 10⁻¹⁰ Pa·s·m, behind η₂₉₈ (§7).
- **Anderson DF (2007).** A modified next reaction method for simulating chemical systems with time
  dependent propensities and delays. *J Chem Phys* 127:214107 (arXiv:0708.0370v2). Eq. 3,
  Definition 1 and §V.

**Read directly in the PMC page's text, after a first reading through a summariser:**
- **Filippov A, Orädd G, Lindblom G (2003).** The effect of cholesterol on the lateral diffusion of
  phospholipids in oriented bilayers. *Biophys J* 84:3079, doi:10.1016/S0006-3495(03)70033-2
  (PMC1302869). Pure DOPC, E_A = 27 kJ/mol over 298–333 K (Table 1), by ¹H pulsed-field-gradient
  NMR at 30 wt % water.
- **Tanaka J, Haga K, Urakami N, Imai M, Sakuma Y (2025).** Temperature dependence of membrane
  viscosity of ternary lipid GUV with L_o domains. *Biophys J*, doi:10.1016/j.bpj.2025.01.024
  (PMC11897551; CC BY-NC-ND).
  - DOPC GUVs at 13–23 °C, η fitted as A·exp(B/T). It is cited only, and its values stay out of
    committed files.
  - Analysis only: the disclosed alternative.

**Pending: paywalled or scanned, requested from the user (D287):**
- Litster 1975, *Phys Lett A* 53:193;
- Taupin, Dvolaitzky and Sauterey 1975, *Biochemistry* 14:4771;
- Weaver and Chizmadzhev 1996, *Bioelectrochem Bioenerg* 41:135;
- Neu and Krassowska 1999, *Phys Rev E* 59:3471;
- Hänggi, Talkner and Borkovec 1990, *Rev Mod Phys* 62:251;
- Kramers 1940, *Physica* 7:284;
- Zhelev and Needham 1993, *BBA* 1147:89;
- Freeman, Wang and Weaver 1994, *Biophys J* 67:42;
- Kwok and Evans 1981, *Biophys J* 35:637;
- Moroz and Nelson 1997, *Biophys J* 72:2211.

**Pending: open, to fetch again:** Saffman and Delbrück 1975, *PNAS* 72:3111 (PMC432930), and
Evans, Heinrich, Ludwig and Rawicz 2003, *Biophys J* 85:2342 (PMC1303459).

**Not opened, to keep the test blind (D287):**
- Karal and Yamazaki 2015, *J Chem Phys* 143:081103;
- Karal, Levadnyy and Yamazaki 2016, *Phys Chem Chem Phys* 18:13487;
- Levadny et al. 2013, *Langmuir* 29:3848;
- Karal et al. 2015, *Phys Rev E* 92:012708;
- Shibly et al. 2016, *Biophys J* 111:2190, doi:10.1016/j.bpj.2016.09.043. It is now held-out
  set 2 (§8), read only by the sealed extractor. Its conditions here come from the FR-31 search's
  record, `/mnt/workspaces/Cells/fr31-search-20261122/candidates.md`, which holds no results.
- Akimov et al. 2017, *Sci Rep* 7:12509.

**The data:** `lean/checks/data/karal2015_rupture_rates.json`, merged at 81916b5d, read only.
