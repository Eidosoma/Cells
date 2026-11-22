# Vesicle pores: rupture under a held tension, and pores that reseal (FR-31, FR-39)

A desk note for D286 (22 November 2026), shared by FR-31 and FR-39. No code. It proposes one
mechanism for both requests (§1), a registered test of FR-31's rupture law (§2), the engine's shape
(§3), and a price with the user's decisions (§4). §5 says how each source was checked.

## 1. The physics, as one mechanism

**The chain.** A tense bilayer opens a pore by a thermally activated step. While the pore is open,
the lumen leaks through it and the tension relaxes. If the tension falls far enough, the pore's line
tension closes it, and the vesicle survives with part of its cargo. If not, the pore grows without
bound: rupture.
- A held tension (a micropipette) keeps σ up, so the first pore is a rupture. That is FR-31.
- A free, osmotically swollen vesicle relaxes through its pore and reseals (FR-39). Then it swells
  again: the swell–burst–reseal cycles of Oglęcka et al. 2014, modelled by Chabanon et al. 2017.
- The evidence for a hazard rather than a threshold (FR-31's text): under a held tension, vesicles
  go on failing over time. A fixed rupture tension cannot produce that.

### 1.1 The state and the tension

- **The state.** Each vesicle has its counts in the membrane and the lumen, as now. While a pore is
  open, it also has the pore's radius r.
- **The tension σ** comes from one of three sources, declared per world:
  - **Osmotic** (today's `cells.osmotic_lumen@1`). The membrane is inextensible. σ = Δp·R/2 from
    the lumen's osmotic excess at the sphere's volume, and σ = 0 while the vesicle is floppy. With a
    pore of radius r, the membrane covers only 4πR² − πr², so the sphere holds more and σ falls.
  - **Elastic** (new, optional). σ = K·(A − A₀)/A₀ with A = 4πR² − πr². This is Chabanon's form,
    with an effective modulus that folds the unfolding of thermal undulations into stretching. As a
    free-energy term, ½K·A₀·ε², stretching enters F.
  - **Held** (new: FR-31's pipette). σ is declared and held by a boundary, whatever the counts.
- **No geometry law gives a held tension today.** `lumen.py`'s σ comes only from osmotic excess on a
  fixed area, and `cells.prescribed_shell@1` refuses a tension (§4, decision 3).

### 1.2 Opening: the rupture law

The pore opens at a hazard k(σ, T) per vesicle. Each candidate's form is fixed before any fit:

| Law | Form | Parameters per temperature | How it is fixed before fitting | Source |
| --- | --- | --- | --- | --- |
| Line-tension nucleation (classical) | ln k = ln ν − πΓ²/(σ·k_BT): ln k linear in 1/σ | ν, the attempt rate per vesicle; Γ, the line tension | The form is declared. Both parameters come from the two end tensions, exactly, so nothing is left free for the middle | Litster 1975; the source group's own analysis (Karal and Yamazaki 2015; Karal, Levadnyy and Yamazaki 2016), which adds a tension-independent term to the activation energy. At one temperature that term folds into ν |
| Exponential (Bell type) | ln k = ln k₀ + σ·Δa/k_BT: ln k linear in σ | k₀; Δa, an activation area | As above | Bell 1978. It is the form behind log-linear interpolation |
| Line-tension nucleation, Γ from elsewhere | As the first row | ν only | Γ's source is declared before the fit, for example edge tensions from pore closure (Karatekin et al. 2003). ν comes by least squares on the two ends, which overdetermine it | As the first row |

**What is left out of the registered test.** Two end points cannot fix a form with more parameters
than that, such as multi-step rupture kinetics (Evans et al. 2003; Evans and Smith 2011; their forms
from memory). Nor is any form that bends upward in σ offered (§2.1).

**Prior grounds, independent of the middle values.** Line-tension nucleation shares Γ with the open
pore's dynamics: a pore shrinks while σr < Γ. That makes FR-31 and FR-39 one mechanism. Its barrier,
πΓ²/σ, is a difference of F between two states where σ comes from F, and that difference less a held
boundary's work where σ is held, so it fits the event-pair contract either way (§3.3). The
exponential law names an activation area, not a state of F.

**Per vesicle or per area.** Karal and Yamazaki's rates are per vesicle, at their vesicles' size.
Applied to other sizes, the hazard must scale somehow. Nucleation sites scale with area, which
suggests k = j(σ)·A (from memory). This is a declared choice (§4, decision 5).

### 1.3 The open pore

For r > 0, the pore follows deterministic laws. Chabanon et al. 2017 state these laws with Langevin
noise in the radius, which the deterministic representation drops. Their parameter table was not
seen (§5), so only the forms are given here, in words:
- **The radius.** A friction balance: (membrane drag + aqueous drag growing with r) × d(2πr)/dt
  = 2π(σr − Γ). The friction forms are Ryham, Berezovik and Cohen 2011 (aqueous viscosity
  dominates) and Aubin and Ryham 2016.
- **The volume.**
  - Water enters through the membrane at a rate set by its permeability and by the difference
    between the osmotic and Laplace pressures.
  - Liquid leaves through the pore at πr²·v_L, where v_L = Δp_L·r/(3πη) and Δp_L = 2σ/R. Chabanon
    cite Aubin and Ryham 2016 and Happel and Brenner 1983 for v_L. It is the leak-out of
    Brochard-Wyart, de Gennes and Sandre 2000 (from memory): the flow through a hole of radius r.
- **The solutes.**
  - Leak-out carries the lumen's concentration out, so by itself it does not dilute the lumen.
  - Diffusion through the pore does dilute it. Chabanon's term is proportional to the pore's area,
    the concentration difference and 1/R. The alternative is an aperture's access law, ∝ D·r·Δc
    (from memory). The two scale differently with r, so this is a declared choice.
- **Cargo.** Each lumen species leaks by the same laws with its own D, so a large cargo leaks
  slower.

### 1.4 Resealing and rupture

- **Resealing.** The pore closes when σr < Γ for long enough that r reaches 0, or a declared
  minimum radius about the bilayer's thickness. The vesicle keeps what is left of its lumen. In
  FR-39's evidence (Oglęcka et al. 2014, Fig. 5) each closure comes within about 1 s.
- **Rupture.** If σr > Γ persists, because the tension is held or the leak is too slow to relax it,
  r grows to a declared terminal size and the vesicle ends. That is the existing release.

### 1.5 Energy

Every step books q = −ΔF + w, as now:
- **Opening.** Where σ comes from F (the osmotic and elastic sources), F rises by the barrier and
  the bath supplies it, so q = −ΔF* < 0.
- **Under a held tension,** the vesicle's F rises only by the edge energy 2πrΓ, and the boundary
  does work: w = σ·d(πr²) as the pore's area grows, at opening (σπr*²) and on the way to rupture.
  The hold is then a work source, with a declared payer and a work column, as a shear's work is
  (§4, decision 3).
- **The open pore.** Its flow runs downhill. Over each sub-step q = −ΔF, and friction dissipates it.
- **Leaked molecules.** They move from the lumen to the pool, or to a held place's reservoir with
  its reservoir work, and are booked as the release books them.
- **Rupture.** The existing release (`runner._release`, `population._release`), with the pore's
  edge energy released too.
- **Resealing.** The edge energy returns to 0. The episode's total is −(F_after − F_before) + w.

### 1.6 One mechanism, not one parameter set

Karal and Yamazaki's vesicles are pure DOPC. Oglęcka's are POPC, sphingomyelin and cholesterol, and
they phase-separate. A Γ or ν fitted on one does not carry to the other, so each world declares its
own values, with sources.

## 2. The registered test (FR-31)

### 2.1 What is already known: the disclosure

- **The middle values were read before registration.** The Lean lane and the lead read the 7.5 mN/m
  rates before any law was registered (FR-31, D286).
- **The sign of the error needs no fit.** At both temperatures the read middle lies below the chord
  in (σ, ln k): log-linear interpolation over-predicts it by 14% at 25 °C and 21% at 32 °C. So any
  form fitted through the ends that is linear or concave in σ over-predicts. The line-tension law,
  ln k = ln ν − b/σ, is concave in σ.
- **This note's author fitted both two-parameter forms on the read values while writing it,**
  before any form was fixed. The recommendation in §4 was written knowing these numbers:

| T | Form | Fitted on 7.0 and 8.0 mN/m | ln k predicted at 7.5 | ln k read | Over-prediction | Combined SEs (descriptive) |
| --- | --- | --- | --- | --- | --- | --- |
| 25 °C | Exponential | Δa ≈ 7.2 nm² | −5.061 | −5.192 | +14.1% | 2.7 |
| 25 °C | Line tension | Γ ≈ 11.4 pN, ν ≈ 3.4 × 10³ s⁻¹ | −5.002 | −5.192 | +20.9% | 3.9 |
| 32 °C | Exponential | Δa ≈ 7.1 nm² | −4.620 | −4.812 | +21.2% | 5.3 |
| 32 °C | Line tension | Γ ≈ 11.3 pN, ν ≈ 3.2 × 10³ s⁻¹ | −4.563 | −4.812 | +28.3% | 6.9 |

- **How the table was computed.**
  - T is from the extraction's 10⁶/T readings: 297.97 K and 304.97 K.
  - The SE of each ln k is half its bar's cap spread. The two ends' SEs are propagated through the
    form, and the middle's is added in quadrature.
  - There are three experiments per setting, and the digitising error is not in the bars. So these
    multiples describe the gap; they are not tests.
- **A form that bends upward in σ, adopted now, would be fitted to the middle,** so this note offers
  none.

### 2.2 The procedure to register

1. The user fixes the form (§1.2) and the tolerance rule (§2.3) in writing, before the engine runs.
2. The engine's law (`cells.pore_nucleation@1`, §3) is declared with that form. Its two parameters
   per temperature are solved from the two end tensions' ln k (the extraction's centres), and from
   nothing else.
3. The engine evaluates k at 7.5 mN/m at each temperature and compares it with the read middle by
   the declared rule. Both temperatures are reported, and neither is dropped.
4. **An implementation check,** separate from the law's verdict. A cohort of N vesicles is held at
   the tension (§3), with first-rupture times drawn on the pore stream. The rate's
   maximum-likelihood estimate (events over total time at risk) is compared with k at a declared
   statistical tolerance. This qualifies the event, not the law.
5. The verdict and this disclosure go into PROGRESS and FR-31 together.

### 2.3 The tolerance rule: the user's choice

The candidate rules' outcomes follow from §2.1, so the choice is made in the open:

| Rule | Exponential, 25 / 32 °C | Line tension, 25 / 32 °C |
| --- | --- | --- |
| Within 2 combined SEs | fail / fail | fail / fail |
| Within 4.30 combined SEs (t at 0.975 with 2 degrees of freedom) | pass / fail | pass / fail |
| Within 25% in rate | pass / pass | pass / fail |
| Better than log-linear interpolation | — | fail / fail |

### 2.4 A blind alternative

As far as this note knows, two candidates have not yet been compared with any law. Only the first
could be blind:
- **Fig. 2a's other temperature columns.** The extraction read "the two common temperature columns",
  which suggests the figure has others. This note's author has not opened the paper or the figure.
  If nobody has read the other columns, a blind test is possible: fix a form and a temperature law
  now, fit them on the four end points already read, and predict those columns. The temperature law
  could be, for example, the line-tension law with ν and Γ linear in T, or the source's
  activation-energy form.
- **The same paper's 12 °C survival** (FR-31: 50% at 92 s, 12.5% at 268 s). FR-31 prints these
  values, so they have been read, as the middle values were; they are not blind. If its tension is
  one of the three registered ones, the same fit can still predict it across temperature.

## 3. Engine shape

### 3.1 A new kind of law: an assembly hazard

The interfaces today (`interfaces.py`) are a reaction law, a rate factor, a free-energy term, a
geometry law, a population structure and an operator at scheduled events. A pore opens at an
unscheduled time, at a rate set by the state, so it needs one more interface:
`cells.assembly_hazard@1`. It reads the vesicle's state (σ, area and T), gives a rate, and names
its stream and its outcome operator.

The proposed laws, all with neutral names:
- `cells.pore_nucleation@1`: §1.2's law, its form and parameters declared with sources;
- `cells.pore_episode@1`: the open pore's deterministic dynamics and its fate (§1.3–1.4);
- `cells.tension_hold@1` (a boundary) and `cells.area_elasticity@1` (a free-energy term), each
  optional.

The hazard is off by default. A world that declares none of these laws runs as today, bit for bit.

### 3.2 The clock: competing in physical time

- **The clock.** Each vesicle carries an integrated hazard H(t) = ∫k(σ)dt and a threshold E = −ln u.
  The pore fires when H reaches E, as in the next-reaction method for time-dependent rates (Anderson
  2007, from memory).
- **Its stream.** u comes from a new stream domain, `pore`. Its carrier word is the vesicle's key
  and its counter is the vesicle's pore draws. Number 7 is the next free domain; 4 stays reserved
  for labels.
- **Exact events.** Between events σ is constant, because it is a function of the counts. So H is
  piecewise linear and the crossing time is exact. A chemistry draw that would land after the
  crossing is discarded and counted, as at a scheduled stop (the OL3 clock rule).
- **When chemistry is idle.** Today a state whose rates are all zero ends `inert` and is held to the
  horizon. The device kernel decides this (`kernel.py`, its status at line 549). A world that
  declares pores keeps the clock running, so its kernel loop changes; no other world's does.
- **Paired runs.** The pore draws on its own stream. So a world with pores and the same world
  without them share every chemistry draw until the first pore event. That gives OL9's matrix
  pairing for free.
- **OL6, deterministic.** H is integrated alongside the rate equations, and the crossing is solved,
  not snapped to a step.

### 3.3 The event-pair contract: a ruling needed

Every step today is a pair whose rates keep ln a⁺ − ln a⁻ = −ΔF + w (`interfaces.py`, U2 and D199).
FORMAT_OL2 exempts one case: a pair whose end state lyses has no reverse and is not checked.
- **Opening, under the line-tension law, is the forward of a pair.** Closed goes to a pore at the
  critical radius r* = Γ/σ, at rate ν·e^(−πΓ²/(σ·k_BT)). Its reverse is the collapse from r* at
  rate ν.
  - Where σ comes from F (osmotic or elastic), πΓ²/σ = F(r*) − F(closed), to leading order in r*/R,
    and w = 0.
  - Under a held tension, F(r*) − F(closed) = 2πr*Γ only, and the boundary does w = σπr*². The pair
    then reads −ΔF + w with w ≠ 0, and the hold is a declared work source.
  - Either way the pair keeps the contract.
- **The open pore's growth, leak and resealing are a downhill deterministic flow,** with q = −ΔF per
  sub-step. Resealing is not a stochastic reverse event.
- **Rupture is one-way,** like lysis. It falls under the existing exemption.
- **Under the exponential law, opening would be a one-way rate,** because that law has no state of F
  for its activated defect. That would be a second exemption.

Which of these holds is the lead's ruling (§4, decision 4).

### 3.4 Fates and the existing release

- **A rupture is a lysis.** It goes through the existing release: molecules to their pool places,
  the closure cost released, q = −ΔF + w, and reservoir work for held places. The end reason stays
  `lysed`, with a cause: `pore` or `threshold`.
- **A resealed vesicle continues its life,** its counts reduced by what leaked.
- **Records** add `pore_events`. Each gives the time, slot, key, duration, peak radius, the leaked
  counts by pool place, the heat and reservoir work, and the fate.

### 3.5 Representations

- **Size.** Karal's and Oglęcka's vesicles are giant, micrometres across. One of radius 10 µm holds
  about 4 × 10⁹ lipids at about 0.7 nm² per lipid per leaflet (an area from memory). That is far
  beyond exact events.
- **OL6's deterministic representation** (engine design §1.2 (d)) carries the counts as continuous
  amounts. Opening stays stochastic, on the hazard clock. The open pore is a deterministic
  sub-dynamics, and a fast one.
- **Exact-event worlds** (small vesicles). Opening and rupture work as above. A transient pore's
  leak at exact counts would be many discrete transfers within one episode. So this note proposes
  rupture only in exact-event worlds, unless the user wants the episode as a host action:
  instantaneous, with its duration recorded and checked against the chemistry's and the schedules'
  times.
- **FR-31's registered test needs neither.** A held-tension world has no chemistry to represent,
  only the clock and the law, so it can run before OL6.

### 3.6 Interactions

- **FR-20's same-time rule.**
  - A replacement or withdrawal stands alone in time, and a lysis at its time is refused, because
    relations have no order between same-time events (`division.py`, `population.py`).
  - A pore event is drawn in continuous time, so a tie is improbable but possible. It is refused the
    same way.
  - A pore that is open across a scheduled stop needs a rule. Proposed: stops act on the state as it
    stands, and a shear refuses a vesicle with an open pore, as a new outcome.
- **FR-22's checkpoints.**
  - The host document adds each living vesicle's E, H and pore counter, and any open pore's state.
  - A cut at a pore event, or during an open pore, is refused, as a cut at a lysing event is.
  - A restart is then bitwise.
- **F12's extinction.**
  - F12 scores fission boundaries. Extinction is absorbing, and is neither a fission nor a break
    (`validation/assembly_lineages_v2/f12.py`).
  - A rupture is an extinction, as a lysis is now.
  - A resealed pore is neither. Its cargo loss shows only in the counts at the next boundary.
- **OL5's registered lysis rule.** The rule that an event whose end state has σ > σ_max lyses stays
  as registered, in every world. In a world that declares pores, the user decides whether σ_max
  stays as a ceiling beside the hazard. Proposed: it stays, so the registered rule is unchanged.

### 3.7 What stays bitwise

Every world that declares no pore law stays bitwise. That covers:
- OL1–OL5's registered sets and OL5's judged runs;
- @1's sets;
- G1, which has no assembly-lineage world among its 113;
- crossrev's sets and FR's set.

The evidence for this is priced in §4: the invariance gate's five steps, and an explicit
before-and-after compare of OL5's runs2 by the probe driver. That compare takes about 9 minutes, and
no gate runs OL5's runs2 today.

## 4. Price, and what the user must decide

**The price,** in agent-days (S, estimates). It excludes OL6 (3–5 in the engine design's §8), any
independent references for the pore laws in OL5's style (another 3–5), the second builder's time,
and the user's and the Lean lane's time on data.

| Phase | Content | Agent-days |
| --- | --- | --- |
| A. FR-31 | The hazard interface; `cells.pore_nucleation@1` in both forms; `cells.tension_hold@1` with its payer and work column; the clock in the single-lineage and population kernels, idle chemistry included; stream domain 7; rupture through the release; records, relations and the diagnostic record; refusals (same time, checkpoint cuts); test rows; the gate, the invariance gate and the runs2 compare | 3.5–5.5 |
| A′. The registered test | The registration text, the engine's prediction, the cohort check and PROGRESS | 0.5–1 |
| B. FR-39 | `cells.pore_episode@1` (radius, volume, solute and cargo leak, resealing, rupture); `cells.area_elasticity@1`; the episode's ledger; the stop rules; records; how F12 and relations read it; the deterministic episode qualified against exact events at sizes both can run | 5–8, after OL6 |
| B′. FR-39's comparison | Oglęcka 2014's Fig. 5 (closures within about 1 s) and Chabanon 2017's Fig. 4 (stepwise loss), registered before any value is read | 2–3 |

**Decisions for the user:**
1. **The rupture law's form, and the tolerance rule (§2.3),** decided knowing §2.1. Proposed: the
   line-tension law, on §1.2's prior grounds. The author wrote this proposal after computing §2.1.
2. **Run the disclosed, non-blind test as it stands,** or look for a blind one first (§2.4).
3. **A held tension as a declared boundary** (`cells.tension_hold@1`). Pipette experiments need it.
   Is it general enough, under the rule that features are general and never built for one
   experiment? Any experiment at a held tension could use it. It is a work source: under U2 (D199)
   a declaration that is not passive names a declared source of free energy, so the hold needs a
   payer and a work column, as a shear's work has (`source:shear/<index>`, `shear_work_kT`).
4. **The pair contract (§3.3):** opening as a pair under the line-tension law, or a one-way opening
   as a second exemption. This is the lead's ruling.
5. **The hazard per vesicle or per area** (§1.2).
6. **Γ shared between opening and the open pore's dynamics,** as one mechanism (§1.6 still applies),
   or each with its own source.
7. **Exact-event worlds:** rupture only, or transient pores as a host action (§3.5).
8. **σ_max beside the hazard** (§3.6).
9. **The order:** Phase A before OL6, which §3.5 shows is possible.

## 5. Sources, and how each was checked

**Confirmed this session:**
- Chabanon M, Ho JCS, Liedberg B, Parikh AN, Rangamani P (2017). Pulsatile lipid vesicles under
  osmotic stress. *Biophys J* 112:1682–1691, doi:10.1016/j.bpj.2017.03.018, PMC5406380.
  - Its equations reached this note through a summary of the article. One equation's grouping was
    reconstructed there, and the parameter table (Table S1) was not seen.
  - So §1.3 gives forms in words and no values.
- Oglęcka K, Rangamani P, Liedberg B, Kraut RS, Parikh AN (2014). Oscillatory phase separation in
  giant lipid vesicles induced by transmembrane osmotic differentials. *eLife* 3:e03695.
  - The title and authors come from a search.
  - The article page did not load, so Fig. 5's details rest on FR-39's text.
- Karal MAS, Yamazaki M (2015). Communication: activation energy of tension-induced pore formation
  in lipid membranes. *J Chem Phys* 143:081103, doi:10.1063/1.4930108.
  - Confirmed by the data file's DOI.
  - Its analysis, an activation energy with a tension-independent term, is from a search tool's
    summary, which drew on the repository PDF's text.
  - No rate values reached this note's author, and the figure was not viewed (§2.4).
- Karal MAS, Levadnyy V, Yamazaki M (2016). *Phys Chem Chem Phys* 18:13487. From a search result.

**Cited by Chabanon et al., not opened here:**
- Litster 1975: classical nucleation.
- Evans, Heinrich, Ludwig and Rawicz 2003, and Evans and Smith 2011: rupture kinetics and their
  dependence on loading rate.
- Ryham, Berezovik and Cohen 2011, and Aubin and Ryham 2016: pore friction.
- Idiart and Levin 2004: the fixed lytic tension that a hazard replaces.
- Evans and Rawicz 1990: the modulus.
- Happel and Brenner 1983: the leak-out.

**From memory, to check before registration:**
- Bell 1978 (*Science* 200:618);
- Brochard-Wyart, de Gennes and Sandre 2000 (*Physica A* 278:32);
- Karatekin et al. 2003 (*Biophys J* 84:1734);
- Anderson 2007 (*J Chem Phys* 127:214107);
- the aperture access law;
- the area per DOPC lipid.

**The data:** `lean/checks/data/karal2015_rupture_rates.json`, merged at 81916b5d and read only.
