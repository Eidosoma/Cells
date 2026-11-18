# Self-replicator selection replication

**The paper.** K. Liu, O. Markovitch, C. van Ewijk, Y. K. Knelissen, A. Kiani, M. Eleveld, W. H. Roos
and S. Otto, "Selection for photocatalytic function through Darwinian evolution of synthetic
self-replicators", *Nature Catalysis* 8, 1000–1009 (2025),
doi:[10.1038/s41929-025-01409-3](https://doi.org/10.1038/s41929-025-01409-3) ("the paper").
- **Access.** It is a subscription article. Its text is never reproduced here: this note
  paraphrases it and cites by location.
- **Read with it,** all free to download from the publisher's article page:
  - the Supplementary Information ("the SI"): 134 pages, with Supplementary Figs. 1–126, the model
    discussion (its section 16) and Supplementary Tables 1–6;
  - Supplementary Data File 1, the SI figures' source data;
  - the Source Data for Figs. 2–5.

  Together these are "the workbooks".
- **The authors' kinetic-model code** ("the code"): O. Markovitch, "Simulating replication with
  mutations under tuneable photocatalytic cofactor function", Zenodo record 15104674, 4 February
  2025 (concept doi:[10.5281/zenodo.15104673](https://doi.org/10.5281/zenodo.15104673)).
  - It is one MATLAB file, `FAMonomers5d.m`, under CC BY 4.0.
  - It is never copied into Cells. §5.1 says why it was not run.

**Status: a replication note, its criteria registered before any run.** First task of a new
track, 18 November 2026.
- Docs only: nothing in `src/`, `tests/` or `validation/` changes.
- Development work, not judged (D138; the question is §6).
- Branch `self-replicator-replication`, from main 0a91d426.

**Sources of numbers.** Each number below says where it comes from:
- **printed** in the paper's text or captions, or the SI's text and tables;
- **from the workbooks**, by sheet;
- **read** off a plotted figure;
- **derived** here (**S**: this note's own arithmetic, with the script that generated it);
- **from the code** (it was not run, §5.1).

**Evidence.** The scripts that read the workbooks use the standard library alone, run with
`python -I`, and write their outputs beside them:
- `/mnt/workspaces/Cells/self-replicator-selection-20261118/`, in `scripts/` and `results/`;
- the downloads in `downloads/<name>/`.

Nothing from the downloads is committed.

**The user's terms (D220).** The user asked for this replication. The article's text stays out of
the repository: it is paraphrased and cited, and its numbers are given as read. The authors'
kinetic model runs out of process, as a reference, only if its licence allows.
- D186 and D201 cover open and free-to-read papers.
- This article is a subscription one, though its SI and workbooks are free to download.
- D220 settles its numbers.

**In short.**
- **The paper.** Two systems of synthetic self-replicating macrocycles run in a lit, stirred flow
  reactor. A dye that binds the replicators' fibres speeds the making of their precursors, and the
  more active mutants win: hexamers over trimers (2 + 3), and 1-rich over 4-rich hexamers (1 + 4).
- **The data** (§1.5). In every paired run, the bound cofactor's readout exceeds the control's.
  - E = 1.57–4.11 for 2 + 3 (n = 6), and 1.41–2.90 for 1 + 4 at a 7:3 feed (n = 7).
  - At a 6:4 feed, E = 1.12–1.25 (n = 2). One run was made at a higher flow.
- **The paper's inconsistencies** (§1.8). Among them:
  - one of Fig. 4e's six repeats ran at another flow rate;
  - five steady-state panels match no row of their own time series;
  - the SI's model equations and the code differ in two places.
- **The targets** (§2), registered before any run (commit 3c9572bf), with three amendments made
  before any run (§2.6):
  - orderings, with factor bands on s = ln E anchored on the worst paired repeat;
  - what is calibrated (C1–C6) against what is predicted (T0–T5, T8);
  - planted controls P1–P3;
  - criteria M0–M6 for the authors' model.
- **The reference** (§5).
  - The authors' code (CC BY 4.0, MATLAB) was not run: installing Octave was refused by the
    session's permission system. The SI's plotted model outputs stand in for it.
  - The model is not admissible in Cells' origin-of-life family (half orders, irreversible steps,
    no oxidant). So Cells' first model is its own: R0, three hexamer types in stacks under flow
    in the dark, then R1 with light.
- **The engine** (§3, §4).
  - Six general features: a linear-stack geometry kind, side places, light with a photon
    potential, continuous flow, stack breaks and a ring family.
  - 15–23.5 agent-days with their references. The whole replication is 23.5–36, after OL3
    (D212).
- **Questions** (§7.3): nine open for the lead, eight of them on physics (D220 answers a tenth),
  and four for the user.

**Engine models run: none.** Docs only. The milestones in §7 name the models they would run. The
authors' model was not run (§5.1).

## 1. What the paper shows

### 1.1 The chemistry (main text, Fig. 1)

- **Building blocks.** Each is an aromatic dithiol carrying a short peptide (the Methods list the
  sequences).
  - 2 differs from 1 by an ornithine in place of the outer lysine.
  - 3 carries 1's peptide in inverted order. In a mixed stack, its hydrophobic and hydrophilic
    residues would then fall out of register with 1's.
  - 4 carries a naphthylalanine where 1 has phenylalanine.
- **Precursors.** Oxidising the thiols gives small disulfide rings: for 1, mainly the trimer 1₃
  and the tetramer 1₄.
  - The rings swap building blocks by thiol–disulfide exchange, so the mixture is a dynamic
    combinatorial library.
- **Replicators.** A ring size whose rings stack through β-sheets forms fibres. That is the hexamer
  for 1 and 2, and the trimer for 3 and 4.
  - **Growth.** Precursors bind along a fibre's sides and are used where the fibre grows, at its
    ends. That growth is the replication.
  - **Fragmentation.** Stirring breaks long fibres, which exposes more ends and makes growth
    exponential.
  - **Protection.** Rings inside a stack are protected from exchange, which keeps the system away
    from equilibrium.
- **Protometabolism** (Fig. 1c).
  - A replicator binds the dye thioflavin T (ThT), which binds β-sheet assemblies.
  - Bound and irradiated, ThT makes singlet oxygen (¹O₂) more efficiently than free ThT does.
  - ¹O₂ speeds the oxidation of the dithiol building blocks into precursors, which bind the
    fibres.
- **Locality.** ¹O₂ lives about 3.5 µs in water (printed; the paper's ref. 41). So, the paper
  argues, it oxidises building blocks near the fibre that made it, and is unlikely to reach a
  neighbouring fibre (SI Table 1 and Supplementary Fig. 101). §1.8, item 11 questions the fibre
  spacing behind that.

### 1.2 The activities: what bound ThT does

| Quantity | Value | Source |
| --- | --- | --- |
| ¹O₂ from 1₆–ThT, against 1₃/1₄–ThT and against ThT alone | The probe's fall, fitted by least squares: 0.049, 0.014 and 0.0033 per h, ratios 3.6 and 14.7. The text gives no number | Supplementary Fig. 96d; derived (**S**) |
| Oxidation of 1 in 2 h (µM; each the mean of two repeats) | 25.6 (1₆ + ThT, light); 14.9 (1₃/1₄ + ThT, light); 4.3 (ThT, light); 4.6 (1₆, light); 4.8 (1₆ + ThT, dark); 4.4 (1₆, dark) | Fig. 2a, from the workbook |
| The same as ratios | The text: about two times that of 1₃/1₄–ThT and about four times that of ThT alone. The workbook: 1.71 and 5.99, and 2.03 against 1₃/1₄–ThT once the dark mean (4.57) is subtracted | Fig. 2a; derived (**S**) |
| Replication of 1₆ under light with ThT | About nine times faster than without light, ThT or both: 2.67 against 0.29, 0.29 and 0.31 %/h | Printed, Supplementary Fig. 99 |
| ¹O₂: 2-rich hexamers against 3-rich trimers (2 + 3 system) | 2.6 times | Printed, Supplementary Fig. 97. Derived (**S**): 2.61 from the probe's fall at 3 h, 2.65 from the fitted slopes |
| ¹O₂: 1-rich hexamers (n ≥ 4) against 4-rich (n ≤ 4) | 2.8 times | Printed, Supplementary Fig. 98. Derived (**S**): 2.81 from the fitted slopes, 2.98 from the fall at 3 h |
| Precursors bound to 1₆ fibres during photo-growth | Trimers and tetramers: 79% bound before irradiation, 61% at 2 h, 76% at 4 h, 83–84% at 6 h and 90% at 8 h. Pentamers 19–47%; monomer 8–34% | Fig. 2c, the workbook's per-repeat blocks (n = 3); derived (**S**) |
| ¹O₂ diffusion | τ = 3.5 µs. √(6Dt), with D = 2 × 10⁻⁵ cm²/s, gives 200 nm at τ (36.8% left), 289 nm at 2τ (13.5%) and 355 nm at 3τ (5.0%) | Printed, SI Table 1 |

The derived values are `results/activity_readouts.json`, from `scripts/activity_readouts.py`.

**HS-AFM** (Fig. 2d,e; Supplementary Videos 1–3; Supplementary Fig. 126).
- Under a 450 nm LED, precursor aggregates form on 1₆–ThT fibres in 2.31 mM 1, and are then used
  up while the fibre lengthens.
- The light went on at about 535 s in Video 1, and at 140 s in Video 3.

**The control** is the sensitiser Ru(bpy)₃ (tris(2,2′-bipyridyl)ruthenium(II)). It also makes
¹O₂, but does not bind fibres (printed; ref. 47).
- **Concentration.** It is fed at 4.0 µM, a tenth of ThT's 40 µM.
- **Filter.** A long-pass filter above 400 nm for Ru(bpy)₃, against 435 nm for ThT. The lamp is a
  10 W, 12 V halogen lamp run at 6 V (Methods).

### 1.3 The two systems

**2 + 3: trimers against hexamers.**
- **Alone,** 2 forms hexamer fibres (2₆) and 3 forms trimer fibres (3₃).
- **Mixed and stirred** (2:3, molar), 3-rich trimers come first (2₂3₁, 2₁3₂, 3₃), then 2-rich
  hexamers (2₆, 2₅3₁, 2₄3₂) (Supplementary Figs. 2c and 75).
- **Both sets are replicators.** Each set's seeds promote its own growth (Supplementary Figs. 76 and
  77).
- **Each set promotes the other's.** The trimers promote the hexamers (Supplementary Fig. 79), and
  the hexamers the trimers, more weakly (Supplementary Fig. 80). So the two ring sizes are
  mutants of each other.
- **β-sheets.** 2₆ fibres show a β-sheet CD minimum at 216–218 nm, and 3₃ fibres do not
  (Supplementary Fig. 90).

**1 + 4: mutants among the hexamers.**
- **4 alone** forms trimer fibres (4₃), with no β-sheet CD signature (Supplementary Fig. 91) and
  little ThT fluorescence enhancement (Supplementary Fig. 94).
- **4 and 1 mixed at 1:2** give 4-rich hexamers first (1₂4₄, 1₃4₃), then 1-rich ones (1₄4₂,
  1₅4₁, 1₆) (Supplementary Figs. 3e and 81).
- **Replication and cross-catalysis.**
  - The hexamers are self-replicators (seeding, Supplementary Fig. 82).
  - 1₆ and 1ₙ4₆₋ₙ (n ≤ 4) promote one another (Supplementary Fig. 84a–d).
  - Seeds of a set's own kind work better than seeds of another composition, so replication has
    some fidelity (Supplementary Fig. 84e,f).
- **The mutants are the hexamer compositions 1ₙ4₆₋ₙ;** five are observed, n = 2 to 6.

### 1.4 The flow reactor

Methods; Figs. 4 and 5; Supplementary Figs. 103–120.

| | 2 + 3 (Fig. 4) | 1 + 4 (Fig. 5) |
| --- | --- | --- |
| Reactor | 500 µL in an HPLC vial; stirred at 1,200 rpm; room temperature; irradiated; borate buffer, 50 mM, pH 8.2 | The same |
| Seeds | Premade trimers and hexamers, 0.20 mM in building blocks | Premade hexamers, 0.20 mM in building blocks: rich in n ≤ 4 (Fig. 5; Supplementary Figs. 118–120), rich in n ≥ 4 (Supplementary Figs. 111–114), or statistical, centred on 1₄4₂ (Supplementary Figs. 115–116) |
| Syringe 1 | 2 and 3 at 1:1, 2.0 mM in all | 1 and 4 at 7:3 (about 0.7:0.3), 0.40 mM in all. Exceptions: about 0.6:0.4 (Supplementary Figs. 111–112); 1.0 mM (Supplementary Fig. 120) |
| Syringe 2 | ThT 40 µM, or Ru(bpy)₃ 4.0 µM | The same. Supplementary Fig. 120: 100 µM and 10 µM |
| Rates per syringe, and outflow (µL/h) | 8 and 16 (Fig. 4; Supplementary Figs. 105–108); 10 and 20 (Supplementary Fig. 109); 15 and 30 (Supplementary Fig. 110) | 10 and 20 |
| Dilution rate and residence time (derived, **S**) | 0.032 per h and 31.3 h; 0.040 per h and 25 h; 0.060 per h and 16.7 h | 0.040 per h and 25 h |
| What the feed holds the reactor at (derived, **S**) | 1.0 mM in building blocks, five times the seeds; ThT 20 µM, or Ru(bpy)₃ 2.0 µM | 0.20 mM in building blocks, the seeds' level; ThT 20 µM, or Ru(bpy)₃ 2.0 µM. Supplementary Fig. 120: 0.50 mM, and 50 or 5 µM |
| Readout | UPLC peak areas at 254 nm, as % of the total; the dynamic steady state as bars (panels e and f) | The same |
| Repeats | Fig. 4e's n = 6: Fig. 4 and Supplementary Figs. 105–109 (Supplementary Fig. 109 ran at 10 µL/h). One run at 15 µL/h | Fig. 5e's n = 3: Fig. 5 and Supplementary Figs. 118–119. One run for each other condition |

### 1.5 The results

The readouts are computed from the workbooks' time series, each run's last row, by
`scripts/flow_readouts.py` (`results/flow_readouts.json`). Where an authors' bar panel differs,
its value is given beside (§1.8, item 3).

**2 + 3.**
- R₂₃ is the summed peak area of the hexamers (2₆, 2₅3₁, 2₄3₂) over that of the trimers (2₂3₁,
  2₁3₂, 3₃): Fig. 4e's measure.
- E = R(ThT)/R(Ru(bpy)₃), within one run's pair.
- s = ln E is the selection strength.

| Run | Syringe rate | R₂₃, ThT | R₂₃, Ru(bpy)₃ | E | s |
| --- | --- | --- | --- | --- | --- |
| Fig. 4 | 8 µL/h | 1.128 | 0.422 | 2.67 | 0.98 (panels: 1.142, 0.422, 2.71) |
| Supp. Fig. 105 | 8 µL/h | 1.031 | 0.655 | 1.57 | 0.45 (panels: 1.094, 0.640, 1.71) |
| Supp. Fig. 106 | 8 µL/h | 0.966 | 0.558 | 1.73 | 0.55 |
| Supp. Fig. 107 | 8 µL/h | 1.712 | 0.417 | 4.11 | 1.41 |
| Supp. Fig. 108 | 8 µL/h | 1.531 | 0.421 | 3.64 | 1.29 (panels: 1.476, 0.421, 3.51) |
| Supp. Fig. 109 | 10 µL/h | 1.018 | 0.552 | 1.84 | 0.61 |
| Supp. Fig. 110 | 15 µL/h | 0.278 | 0.144 | 1.94 | 0.66 |

- **Every ThT run exceeds every control run** at 8–10 µL/h: R₂₃ is 0.966–1.712 with ThT and
  0.417–0.655 with Ru(bpy)₃.
- **E is 1.57–4.11, with a geometric mean of 2.42.** Fig. 4e's printed statistic: P = 0.00017,
  n = 6.
- **With ThT, hexamers and trimers are comparable** (R₂₃ about 1). With Ru(bpy)₃ the trimers
  outnumber the hexamers.
- **At 15 µL/h (one run),** R₂₃ falls in both arms: to 0.29 of the lowest 8–10 µL/h value with
  ThT, and to 0.35 with Ru(bpy)₃. ThT stays above the control (E = 1.94).

**1 + 4.**
- R₁₄ is the peak area of 1₆ over that of 1₄4₂: Fig. 5e's measure.
- f₁ is the fraction of building block 1 in the hexamers, from the same last rows. Each hexamer's peak area is weighted by
  n/6, with the peak area taken to be proportional to the building-block amount (**S**, an
  assumption; the paper gives no response factors).
- "n ≥ 5" is the share of 1₆ and 1₅4₁ among the hexamers.

| Run | Feed; seeds | R₁₄, ThT | R₁₄, Ru(bpy)₃ | E | s | f₁, ThT / Ru(bpy)₃ | n ≥ 5, ThT / Ru(bpy)₃ | Mode, ThT / Ru(bpy)₃ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Fig. 5 | 7:3; n ≤ 4 | 0.613 | 0.212 | 2.90 | 1.06 | 0.757 / 0.665 | 0.55 / 0.33 | 1₅4₁ / 1₄4₂ |
| Supp. Fig. 118 | 7:3; n ≤ 4 | 0.424 | 0.256 | 1.66 | 0.50 | 0.728 / 0.680 | 0.47 / 0.36 | 1₅4₁ / 1₄4₂ |
| Supp. Fig. 119 | 7:3; n ≤ 4 | 0.352 | 0.249 | 1.41 | 0.34 | 0.712 / 0.683 | 0.43 / 0.36 | 1₄4₂ / 1₄4₂ |
| Supp. Fig. 113 | 7:3; n ≥ 4 | 0.547 | 0.243 | 2.26 | 0.81 | 0.726 / 0.663 | 0.49 / 0.32 | 1₅4₁ / 1₄4₂ |
| Supp. Fig. 114 | 7:3; n ≥ 4 | 0.432 | 0.262 | 1.65 | 0.50 | 0.726 / 0.691 | 0.47 / 0.39 | 1₅4₁ / 1₄4₂ |
| Supp. Fig. 115 | 7:3; statistical | 0.407 | 0.195 | 2.09 | 0.74 | 0.721 / 0.649 | 0.45 / 0.29 | 1₄4₂ / 1₄4₂ |
| Supp. Fig. 116 | 7:3; statistical | 0.445 | 0.223 | 2.00 | 0.69 | 0.720 / 0.647 | 0.45 / 0.30 | 1₄4₂ / 1₄4₂ |
| Supp. Fig. 120 | 7:3 at 1.0 mM; n ≤ 4 | 0.394 | 0.259 | 1.52 (panels: 1.42) | 0.42 | 0.730 / 0.692 | 0.48 / 0.39 | 1₅4₁ / 1₄4₂ |
| Supp. Fig. 111 | 6:4; n ≥ 4 | 0.193 | 0.171 | 1.12 | 0.12 | 0.662 / 0.632 | 0.32 / 0.27 | 1₄4₂ / 1₄4₂ |
| Supp. Fig. 112 | 6:4; n ≥ 4 | 0.214 | 0.186 | 1.15 (panels: 1.25) | 0.14 | 0.673 / 0.645 | 0.33 / 0.28 | 1₄4₂ / 1₄4₂ |

- **At 7:3 and 0.40 mM** (seven runs), every ThT run's R₁₄ (0.352–0.613) exceeds every control
  run's (0.195–0.262).
  - E is 1.41–2.90, with a geometric mean of 1.95. Fig. 5e's printed statistic, on its three
    runs: P = 0.047.
- **The control's mode is 1₄4₂ in every run,** and is like the closed-vial batch's distribution
  (Supplementary Fig. 81d).
  - With ThT the mode is 1₅4₁ in five of eight runs at 7:3 (Supplementary Fig. 120 included) and
    1₄4₂ in three. The mode is not robust.
- **The n ≥ 5 share** is higher with ThT in every pair: by 0.065–0.216 at 7:3, and by 0.051–0.065
  at 6:4.
- **At 6:4** (two runs), E is 1.12–1.25, below every run at 7:3. The paper says selection is
  substantially weaker (Supplementary Figs. 111–112).
- **The two descriptive measures do not separate 6:4 from 7:3.**
  - f₁'s difference between the arms is 0.029–0.092 at 7:3 and 0.028–0.030 at 6:4.
  - The n ≥ 5 differences meet at 0.065.

**Timescales** (printed).
- **2 + 3.** The replicators fall during the first turnover, which the text gives as about 24 h
  (§1.8, item 1). They recover modestly from 24 to 80 h, and hold a steady state from 80 to 150 h.
- **1 + 4.** The replicators fall for the first 10 h. Then the 1-rich mutants (1₆, 1₅4₁, 1₄4₂)
  rebound while the 4-rich ones (1₃4₃, 1₂4₄) keep falling, and a steady state follows after about
  50 h.
  - In the workbook, 1₆ still rises from 10.25% at 45 h to 12.46% at 94 h.
- **Against the residence time** (**S**): about 2.6 residence times for 2 + 3 and 2 for 1 + 4.
  That is close to the chemostat's own clock, so the paper's timescales mostly test the dilution
  rate.

### 1.6 The retention experiment (Fig. 3; Supplementary Fig. 102; workbook "fig 3c")

**The question.** Do fibres keep the precursors bound to them long enough to grow from them? If
bound precursors moved between fibres much faster than replication, every fibre would gain
equally from any fibre's activity, and no selection could follow (the paper's argument).

**The design.**
- 1′ carries a leucine labelled with six ¹³C and one ¹⁵N, 7 Da per building block (Methods).
- **Separate arm.** 1₆ fibres (1.0 mM in 1) were incubated for 20 min with unlabelled precursors
  (1₃/1₄, 20 mol%), and 1′₆ fibres with labelled ones (1′₃/1′₄), separately. The two were then
  mixed.
- **Mixed arm** (the control). All four were mixed at once.
- **Then,** in both arms, a little TCEP freed some monomer and so started the exchange. After
  8 h most precursor had become hexamer.
- **The readout** is mass spectrometry. [M+4H]⁴⁺ peaks at m/z 1138 (1₆) and 1148 (1′₆), with the
  mixed hexamers 1ₙ1′₆₋ₙ between them (Supplementary Fig. 102).

**The numbers** (n = 4 per arm; printed P = 0.043, one-way ANOVA).

| New growth from 10 nmol of precursor (nmol) | Separate arm | Mixed arm |
| --- | --- | --- |
| Mixed hexamers | 8.71, 7.22, 7.46, 8.30 | 10.62, 8.81, 8.46, 9.39 |
| Pure hexamers (consumed precursor less mixed growth) | 1.29, 2.78, 2.54, 1.70 | about 0, 1.19, 1.54, 0.61 |
| Pure share of new growth (derived, **S**) | 0.21 (0.13–0.28) | 0.08 (0–0.15) |

**Reference points** (**S**).
- Building blocks scrambled at random between two equal pools give a pure share of 2 × 2⁻⁶ =
  0.031.
- Complete retention with no scrambling gives 1.
- The separate arm's lowest repeat (1.29) lies below the mixed arm's highest (1.54).
- **The paper's reading:** retention is partial. New fibre surface made during growth can also
  take precursors from solution.

### 1.7 The kinetic model (SI section 16; the code)

**The model** (SI Tables 2–4).
- **Species.**
  - two building blocks, A and B;
  - trimers A₃, A₁.₅B₁.₅ and B₃, each "bound near" each hexamer type;
  - three assembled hexamers: A₆, A₃B₃ and B₆.
- **Oxidation** (reactions 1–9). Monomers give bound trimers at kox[A] and kox[B]. The mixed
  trimer forms at 3·kox·[A]^½[B]^½ (a symmetry factor of 3).
- **Replication** (reactions 10–21). Two bound trimers convert into a hexamer y, catalysed by the
  hexamer x they are bound near. A weight from x's row of a mutation matrix scales the rate.
- **Flow** (reactions 22–24). Inflow of A and B, and outflow of every species.
- **Implicit or absent:** fibre breakage is implicit, nucleation is neglected, and there are no
  fibre lengths.
- **Constants** (SI Table 3): kox = 0.1 per h; kelong = 10³ per mM per h; inflow 0.3 × 10/500 =
  0.006 mM/h for each of A and B; outflow 20/500 = 0.04 per h.
- **Mutation weights** (SI Table 4). A₆'s row is (0.9, 0.1, 0), A₃B₃'s is (0.2, 0.6, 0.2) and B₆'s
  is (0, 0.1, 0.9).
- **Solver and horizon:** MATLAB's `ode15s`, over 100 h.

**The two claims** (main text; SI section 16).
1. **A factor of 2 suffices.** A 2-fold rise of the oxidation rate constants near A₆ (reactions 1–3)
   makes A₆ about 1.5 times B₆ (Supplementary Fig. 122).
   - The SI calls this in accordance with the experiment's 1.4-fold rise of [1]/[4] in the
     replicators (SI Table 5: 2.31 with the control, 3.27 with ThT).
2. **Raised mutation rates do not reproduce the shift.**
   - With extreme mutation rates and no cofactor (SI Table 6), A₆/B₆ stays below that value
     (Supplementary Fig. 123).
   - A grid of B₆'s mutation against the cofactor factor shows the same trend (Supplementary
     Fig. 124).
   - **The claim's range.** It is shown for SI Table 6's rates, where A₆/B₆ is still above 1
     (about 1.245, read), only lower than the bias-2 case. Fig. 124's own no-cofactor column
     reads about 1.6–1.8 at B₆ mutation 0.9, and about 2.5–2.8 at 1.0 (read), above Fig. 122's
     1.55. So the negative claim holds only below a B₆ mutation of about 0.9.
   - A modest cofactor suffices even under high A₆ mutation (Supplementary Fig. 125).

**The code differs from the SI's equations in two ways:**
- **Oxidation.** The oxidation rate into each hexamer h's food carries a factor (1 + x_h), where
  x_h is h's share of all hexamers. SI Table 2 has no such factor.
- **Elongation.**
  - The code multiplies the elongation rate by x_h, h's share, where SI Table 2 prints [h], its
    concentration.
  - SI Table 3's unit for kelong, per mM per h, fits the code's form. The printed form would need
    per mM² per h.

**Beyond the two equations:**
- **Fixed in the code.** Only kox, kelong, the oxidation bias per hexamer and the mutation matrix
  are its arguments. Fixed are:
  - the inflow at 1:1, not the experiment's 7:3;
  - the outflow at 0.04 per h, the 1 + 4 reactor's;
  - the seeds: 0.20 mM in building blocks, 80% in A₃B₃ and 10% each in A₆ and B₆;
  - the 100 h horizon.
- **The figure's name.** The code's description names the bias-2 default as giving "Figure S123".
  The published SI shows that case as Supplementary Fig. 122.

### 1.8 Where the paper is ambiguous or inconsistent

1. **The 2 + 3 reactor's turnover.** The text gives about 24 h. Fig. 4's rates (16 µL/h out of
   500 µL) give 31 h (**S**). The Methods give 8–15 µL/h per syringe with a 30 µL/h outflow, the
   range across Supplementary Figs. 105–110.
2. **Fig. 4e's six repeats include Supplementary Fig. 109,** which ran at 10 µL/h, not Fig. 4's
   8 µL/h.
3. **Steady-state bars against the time series** (`results/panel_consistency.json`, from
   `scripts/panel_consistency.py`).
   - Fig. 4c is the 104 h row, not the last (151 h). Supplementary Fig. 105's bars are its 100 h
     row; its series runs to 110 h.
   - Five panels match no row of their own series:
     - Supplementary Fig. 108e, by 0.76;
     - 119e, by 1.0;
     - 120e, by 0.37;
     - 112f, which repeats Supplementary Fig. 111's control bars exactly;
     - 120f, whose nearest row is 71 h, by 3.26.
   - Fig. 5d's 1₂4₄ bar is 5.27, where Fig. 5b's 94 h row has 6.27.
4. **Fig. 2a.**
   - The text's factors of about two and about four are 1.71 and 5.99 in the workbook (§1.2).
   - The caption gives the average of two experiments. The Methods give three samples, with
     standard deviations. The workbook holds two.
5. **Fig. 2c's workbook.** Its summary columns headed trimer, tetramer and pentamer hold the
   tetramer's, pentamer's and trimer's per-repeat means.
6. **SI Table 5.** Its 76.6% and 69.8% of 1 in the replicators ("from Fig. 5c and d") are not
   reproduced by weighting each hexamer's peak area by its composition.
   - That gives 75.7% and 67.0% (**S**), or 66.5% with Fig. 5b's 6.27. The table's method is not
     stated.
   - Its [1]/[4] ratio change, 1.42, becomes 1.53 (**S**).
7. **What SI section 16.2 compares.** It sets the experiment's 1.4-fold rise of [1]/[4] beside the
   model's input bias of about 2, not beside the model's own output for that readout (§2.5, M5).
8. **SI Table 2's printing.**
   - Elongation is printed with the hexamer's concentration (§1.7).
   - Reaction 20's product is printed as 2·A₃B₃, where the table's pattern gives B₆ + A₃B₃.
9. **SI Fig. 124's caption** says its point at B₆ mutation 0.5 and cofactor 1 is Supplementary
   Fig. 123.
   - Fig. 123 uses SI Table 6, which also puts A₃B₃'s row at thirds.
   - Fig. 124 keeps SI Table 4's other rows.
10. **SI Figs. 124 and 125's bottom rows share their parameters** (SI Table 4 with cofactor X). At
    X = 4 their colours read about 2.3–2.5 (Fig. 124, on a scale of 1–4) and about 2.7 (Fig. 125,
    on a scale of 1–3).
11. **The fibres' spacing.**
    - **The SI's value.** Supplementary Fig. 101's workbook gives a radius per fibre of 715 nm at
      0.2 mM, for 100 nm fibres.
    - **This note's.** The stated parameters are 500 µL, 100 nm fibres and 0.5 nm per macrocycle.
      With one hexamer per 0.5 nm layer, a fibre holds 1,200 building blocks, there are 5.0 × 10¹³
      fibres, and the radius is 134 nm (**S**).
    - **The difference.** The SI's value implies about 1.8 × 10⁵ building blocks per fibre, about
      150 times more. The fibres' cross-section is not stated.
    - **Against ¹O₂.** Its diffusion length in one lifetime, 200 nm (SI Table 1), lies between
      the two. So the locality argument rests on a fibre density that the paper does not measure.

### 1.9 What the paper does not show

- **No elementary rate constants.** None is given for oxidation by ¹O₂, precursor binding and
  unbinding, end growth, fragmentation, exchange or ThT binding; only relative activities and
  ratios.
- **Locality: no independent measurement.** Which fibre captures a precursor made by another
  fibre's ¹O₂ is argued by estimate (SI Table 1, Supplementary Fig. 101). Retention after binding
  (Fig. 3) is measured, and is partial.
- **The two arms are not shown to be matched.**
  - The sensitisers differ in concentration (40 against 4.0 µM fed) and in filter, and their
    total ¹O₂ production in the reactor is not reported.
  - ThT's bound fraction under flow is not reported.
  - Whether either sensitiser was present at time 0 is not stated.
  - The light's intensity is given only as the lamp's voltage and filter.
- **Molar amounts.** The readouts are relative UV peak areas, with no response factors. The paired
  ratio E cancels them.
- **Fibres themselves.** No fibre lengths, number densities or breakage rates are given for the
  flow conditions. The composition of single fibres is not given, so whether a fibre's
  composition is inherited through breakage is not measured.
- **Small samples.** The flow-rate effect rests on one run per arm at 15 µL/h, and the 6:4 effect
  on two runs, one with a duplicated control panel.
- **The model** is described in the SI as highly simplified, and it is limited in four ways:
  - **Its steps:** an irreversible ODE with half-order steps, non-integer stoichiometry
    (A₁.₅B₁.₅) and an oxidation that names no oxidant;
  - **Its structure:** no fibres, lengths or breakage, and three hexamer types;
  - **Its scope:** it models the 1 + 4 claims only, at a fixed 1:1 inflow. It does not model the
    2 + 3 system, the inflow ratio, the flow rate or retention;
  - **Its constants:** they were chosen to reproduce the observed behaviour (SI
    section 16.1), so its agreement is not a prediction.
  - **Its negative claim** (mutation alone does not give the shift) holds only within a range:
    below a B₆ mutation of about 0.9 in Fig. 124, and for SI Table 6's rates (§1.7).
- **Evolution beyond the fed set.** The mutant set is fixed by the building blocks fed, so no
  mutant can arise beyond those compositions.

## 2. The targets, registered before any run

This section is fixed before any Cells run and before the authors' model is run (§2.5). A later
change is a dated amendment with its reason.

### 2.1 Readouts

- **Primary: the paired enhancement E and the selection strength s = ln E.**
  - E is R₂₃ or R₁₄ with the bound cofactor over the same with the unbound control, taken within
    one run's pair of arms.
  - E cancels the readout's response factors, and s is additive in selection.
- **Cells' readouts are building-block amounts per replicator species.** The paper's peak areas
  are read as proportional to them, an assumption that the paired E cancels.
- **Steady state.**
  - Readouts are taken at the paper's sampling time for the condition (the authors' panel time,
    94–151 h), and as the mean over the last 10 h.
  - A Cells run is called steady if its readouts change by less than 5% over its last residence
    time. Otherwise it is reported as not steady.
- **Seeds.** Stochastic Cells runs take at least three seeds per arm, the paper's n for Fig. 5e,
  and each pair is reported.
- **Descriptive only** (§1.5): the mode, f₁, and the n ≥ 5 share's separation of 6:4 from 7:3.

### 2.2 How a target passes

- **O, the ordering:** the direction the paper reports, which must hold for the mean over seeds
  and for every seed.
- **F, the factor band, for an enhancement:**
  - s lies within [s_worst/2, 2·s_best], with s_worst and s_best the data's weakest and strongest
    paired repeats;
  - that is a factor of 2 on the selection strength, anchored on the worst repeat and not on the
    headline.
- **F for a quantity that is not a selection strength** is a factor of 2 on the data's range of
  that quantity itself: T0's speed-up, and T5's difference of shares.
- **Replicated** means O and F both hold. **Partial** means O holds and F does not.
- **Orderings only** where the data have one or two runs per condition. A magnitude band on n ≤ 2
  is not warranted.

### 2.3 What is calibrated and what is predicted

**Calibrated:** each input from a separate measurement in the paper.

| ID | Input | From |
| --- | --- | --- |
| C1 | Activity ratios of the bound cofactor: hexamer against trimer stacks, 2.6; 1-rich against 4-rich hexamers, 2.8; bound against unbound. Each is ¹O₂ per building block of stack at a fixed total ThT (20 µM with 0.20 mM of fibres), so it fixes the product of the bound amount and the yield per bound dye, which the data do not separate (amended, §2.6) | Supplementary Figs. 96–98; Fig. 2a (§1.2) |
| C2 | The dark oxidation rate: 4.4–4.75 µM of 1 per 2 h at 0.20 mM | Fig. 2a |
| C3 | The dark replication rate: 0.29–0.31 %/h | Supplementary Fig. 99b–d |
| C4 | The bound fraction of precursors: about 79% of trimers and tetramers before irradiation | Fig. 2c |
| C5 | The control arm's steady state at the base condition, for the intrinsic replication, fidelity and cross-catalysis constants | Figs. 4–5's Ru(bpy)₃ arms, with the batch libraries (Supplementary Figs. 75, 81) |
| C6 | Inter-fibre exchange of bound precursors, or the locality fraction | Fig. 3c (T7) |

**Predicted** with no further fitting: T0–T5 and T8 below. A target whose input it also
calibrates is marked "calibration" and is not counted as a test.

### 2.4 The targets

| ID | Target | The data | O | F | Planted control | Judged by |
| --- | --- | --- | --- | --- | --- | --- |
| **T0** | Batch photo-replication: 1₆ grows faster under light with bound ThT than in the dark | 2.67 against 0.29–0.31 %/h, 8.6–9.2 times (Supplementary Fig. 99) | Faster | The speed-up lies in [4.3, 18.4], a factor of 2 on the data's range | No light: the dark rate (C3) | The paper's data |
| **T1** | 2 + 3: bound ThT raises the hexamer/trimer ratio above the control's | E 1.57–4.11 (n = 6) | E > 1 | s in [0.227, 2.83], so E in [1.25, 16.9] | P1, P2, P3 | The paper's data |
| **T2** | 1 + 4 at 7:3: bound ThT raises 1₆/1₄4₂ above the control's | E 1.41–2.90 (n = 7) | E > 1 | s in [0.172, 2.13], so E in [1.19, 8.4] | P1, P2, P3 | The paper's data. The authors' model only in kind (three types, 1:1 feed) |
| **T3** | 1 + 4: the 6:4 feed weakens the selection against 7:3 | s(6:4) 0.12–0.22, against 0.34–1.06 | s(6:4) < s(7:3) | — (n = 2) | — | The paper's data. Not the authors' model, whose feed is fixed |
| **T4** | 2 + 3: a higher flow (15 against 8 µL/h per syringe) lowers R₂₃ in both arms, and ThT stays above the control | R₂₃ to 0.29 (ThT) and 0.35 (control) of the lowest 8–10 µL/h value; E = 1.94 (n = 1) | Both fall; E > 1 | — (n = 1) | — | The paper's data |
| **T5** | 1 + 4 at 7:3: ThT shifts weight to n ≥ 5. The control centring on 1₄4₂ is calibration of C5, not a test (amended, §2.6) | The n ≥ 5 share higher with ThT by 0.065–0.216; control mode 1₄4₂ in 8 of 8 runs | The shift holds | The difference lies in [0.033, 0.43] | P1 | The paper's data |
| **T6** | The approach to steady state | 2 + 3: 80–150 h (about 2.6 residence times); 1 + 4: about 50 h (2) | Within 1.5–5 residence times | — | — | Descriptive |
| **T7** | Retention: separately loaded fibres grow more pure hexamers, partly | Pure share 0.21 against 0.08 (n = 4, overlapping) | Separate > mixed, and separate < 0.5 | — | Bound precursors exchanged freely: the shares become equal | Calibration of C6. The paper's data |
| **T8a** | A 1-rich/4-rich activity ratio of 2, rather than the measured 2.8, still passes T2 | The authors' claim (Supplementary Fig. 122) | T2's O | T2's F | — | The authors' model, in kind |
| **T8b** | With equal activity, a fidelity loss pinned to SI Table 6's rates (B-rich stacks replicate accurately half the time, mixed stacks a third of the time) gives a smaller shift than T8a's activity ratio of 2, in the same world and readout (amended, §2.6) | The authors' claim (Supplementary Fig. 123: about 1.245 against 1.55, read) | s(T8b) < s(T8a) | — | — | The authors' model, in kind |

**The planted controls,** each of which must hold for the criteria to have teeth (D187):
- **P1, equal activity.** C1's product (bound amount times yield, per building block of stack) is
  equal for every stack composition, at the same total oxidation as the control (amended, §2.6).
  Expected: |s| ≤ 0.1, below T1's and T2's lower F bounds (0.227 and 0.172).
- **P2, pooled precursors.** The activities are unequal, but every photo-made precursor goes to
  the common pool instead of to the stack that made it. Expected: |s| ≤ 0.1. This is the retention
  claim's control: without retention, activity is not selected.
- **P3, inverted activity.** The 4-rich stacks (or the trimer stacks) take the higher activity.
  Expected: s < −0.1, so T1's and T2's O fail.

### 2.5 The authors' model: criteria for its run, fixed before it runs

The values marked as read come from SI Figs. 121–123's plots; this note's reading tolerance is
given with each.
- **M0, Supplementary Fig. 121.** Bias (1, 1, 1) with SI Table 4.
  - A₆/B₆ at 100 h is 1 within 10⁻³: the case is symmetric in A and B.
  - A₃B₃'s building-block fraction is 0.62 ± 0.02, and A₆'s and B₆'s are each 0.07 ± 0.01 (read).
- **M1, Supplementary Fig. 122.** Bias (2, 1, 1) with SI Table 4.
  - A₆/B₆ at 100 h is 1.55 ± 0.05 (read). The SI's text says about 1.5.
  - A₃B₃ is 0.60 ± 0.02, A₆ 0.08 ± 0.01 and B₆ 0.05 ± 0.01 (read).
- **M2, Supplementary Fig. 123.** Bias (1, 1, 1) with SI Table 6.
  - A₆/B₆ at 100 h is 1.245 ± 0.03 (read), and below M1's value: the SI's claim.
- **M3, Supplementary Fig. 124: a 13 × 10 grid.**
  - **The grid.** The cofactor factor X runs from 1 to 4 in steps of 0.25. B₆'s mutation Y runs
    from 0.1 to 1.0 in steps of 0.1. B₆'s row is (0, Y, 1 − Y), and the other rows are SI Table
    4's.
  - **Monotone.** A₆/B₆ does not fall as X rises at each Y, nor as Y rises at each X.
  - **Its corners.** (1, 0.1) equals M0's value, and (2, 0.1) equals M1's.
  - **(1, 0.5) is reported against M2's value.** The caption calls them equal. This note expects
    them to differ (§1.8, item 9).
- **M4, Supplementary Fig. 125: a 13 × 9 grid.**
  - **The grid.** X as in M3. A₆'s mutation Y runs from 0.1 to 0.5 in steps of 0.05.
  - **A₆'s row is (1 − Y, Y, 0),** and the other rows are SI Table 4's. That is this note's
    reading of the caption's "homologous" to Fig. 124.
  - **Monotone.** A₆/B₆ does not fall as X rises, nor rise as Y rises.
  - **Its bottom row equals M3's,** since the parameters are the same.
  - **The value at (4, 0.1)** is reported against both figures' colour readings (§1.8, item 10).
- **M5.** The model's own analogue of SI Table 5's readout: building blocks of A over B in A₆,
  A₃B₃ and B₆ at 100 h, with bias 2 against bias 1.
  - It is reported beside the table's 1.42.
  - This note expects about 1.09 from Supplementary Fig. 122a's plotted fractions, (0.08 + 0.30)/
    (0.05 + 0.30) (**S**), well below 1.42.
- **M6.** A₆/B₆'s relative change from 90 to 100 h, reported as the run's distance from a steady
  state.

**When the model counts as having run.**
- The function returns without error, with the code unmodified and called only through its
  arguments.
- M0's symmetry holds, and M1 and M2 hold within their reading tolerances.

A run that completes but fails M1 or M2 is reported as not reproducing the SI's figures, and its
numbers are not called the authors' reference.

### 2.6 Amendments before any run (18 November 2026)

Made after review, with nothing run: no Cells run exists, and the authors' model was not run
(§5.1). The registered text is commit 3c9572bf.
1. **T8b is pinned to SI Table 6's rates and becomes an ordering against T8a.**
   - **It was:** a fidelity-only cofactor "does not pass T2".
   - **The reason.** That set no size for the fidelity loss, and the SI's negative claim has a
     range (§1.7).
     - In the authors' model, Table 6's rates still shift A₆/B₆ (about 1.245), only less than the
       bias of 2 does (1.55).
     - Fig. 124 at B₆ mutation 0.9–1.0 exceeds 1.55 with no cofactor at all.
   - So an arm that destroyed fidelity would "fail" the old T8b without contradicting the
     authors.
2. **C1 fixes a product, and P1 is that product made equal.**
   - **The reason.** The activity ratios were measured on fibre–ThT mixtures at a fixed total ThT.
     Each is therefore the bound amount times the yield per bound dye, per building block of
     stack.
   - §3 gives the cofactor both a binding term and an activity factor. Calibrating both on C1
     would count it twice.
   - So C1 calibrates the product, and its split is declared (L1).
3. **T5's control half is calibration.**
   - **The reason.** C5 calibrates the control's steady state, so its centring on 1₄4₂ is not a
     prediction.
   - Only the ThT arm's shift toward n ≥ 5 is tested.

## 3. The mapping onto the engine, entity by entity

The engine is the origin-of-life family, `cells.assembly_lineages@2`:
- OL1's laws (landed; `ol1-landed-2026-11-18`);
- OL2's geometry and shared pool (in progress on `ol2-engine`);
- OL3's division, transfer and labels (designed: ORIGIN_OF_LIFE_OL2_OL3_CHECK.md and the design
  note's §0.2c–d).

| Paper part | Physics | Cells today | Status |
| --- | --- | --- | --- |
| Building blocks 1–4, and the labelled 1′ | Peptide dithiols in buffer at pH 8.2, two thiols each | Species in the registry; pool places in @2 (OL1); the building-block core as a moiety (CORE_SEAMS_DESIGN §7.3) | Covered as species. The thiol and disulfide states need declaring (F6) |
| Precursors: small rings (1₃, 1₄, mixed rings) | Disulfide macrocycles of 3–4 building blocks, of every composition | Species with integer coefficients, at most three reactant molecules per step (D152), in a declared family as OL8's polymers are | Gap: a ring family (F6) |
| Replicators: the macrocycles whose compositions are the mutants | Rings that stack: seven hexamers 1ₙ4₆₋ₙ (n = 0–6); for 2 + 3, hexamers and trimers | Species in a stack's core place | The species are fine; the place is F1 |
| Fibres | One-dimensional stacks. Length from the count of stacked rings (0.5 nm per ring, Supplementary Fig. 101); two ends; sides | An assembly with a geometry kind on OL2's interface `cells.assembly_geometry@1`, whose only kind is `cells.bilayer_geometry@1` | **F1.** The design check's fit test already places a fibre "as a later geometry kind" (OL2/OL3 check §3.5) |
| End growth | Side-bound precursors convert, at an end, into a stacked hexamer, with some fidelity to the end | Phase exchange's encounters are `insertion_area` and `diffusion_radius`, with steps in a phase (`count_on_m`). Fidelity is a factor on m: OL1's `cells.transition_state_factor@1` | **F1** (an end-capture encounter) and **F2** (side-to-core steps at the ends). Fidelity needs no new law |
| Fragmentation under agitation | Stirring breaks a stack at one of its bonds; the two pieces' lengths sum to the parent's; the stirrer pays | OL3's `cells.shear_fission@1` (designed): vesicles, admitted at v ≤ k^(−1/2) at scheduled or Poisson shear events, split by C3x | **F5:** a stack's break rule |
| Precursor reservoirs on fibre sides | An adsorbed layer: binding in proportion to side area, unbinding from F, retention between fibres (Fig. 3) | Places are pool, membrane and lumen. There is no adsorbed place | **F2:** a side place on an assembly |
| The bound cofactor (ThT) | Binds β-sheet stacks with an affinity that depends on composition. Bound, it photo-oxidises: activity ratios 2.6 and 2.8 (C1) | A side-place species. Its binding term depends on the stack's composition (a free-energy term on OL1's hook `cells.free_energy_term@1`, reciprocal by the design note's E2 lesson). Its activity is a factor on m of the photo-step. C1 fixes only the product of binding and activity, so the split between them is declared (§2.6, L1) | Needs F2 and F3. The factor is OL1's |
| The unbound control (Ru(bpy)₃) | Free in solution; photo-oxidation in the bulk | A pool species catalysing the same photo-step in the pool | Needs F3 |
| Singlet oxygen's locality (about 3.5 µs, 200 nm) | A short-lived oxidant that acts near its source | Not a resolved species, since there is no space. Its locality becomes where the photo-step's product goes: the producing stack's side, or the pool | **A physics choice (L3).** The step is cross-phase (a pool monomer to a side product), and §0.2c rule 3 requires a geometric encounter for such steps (F2) |
| Light | The sensitiser absorbs, transfers energy to O₂ and oxidises; the lamp pays | The design note's §3.1 lists light as "later". §3.2 refuses a driven law without a source. The design's event domain is \|ΔF/k_BT\| ≤ 80 (§2.1). On main, OL1 enforces 80 k_BT only as the bound on a catalyst's ΔΔG‡ (`transition_state.py`); no check on an event's ΔF was found | **F3:** a photon source with a declared potential (below) |
| Dark oxidation by O₂ | Air oxidation, slow (C2) | Held O₂ (G1's held phase) and a reversible step with registry potentials | Covered in form (OL1, OL4). Its potentials are to be declared |
| Thiol–disulfide exchange | Thiolate attacks a disulfide, so rings swap building blocks: reversible and passive | `cells.stochastic_mass_action@1` (OL1) | Covered in form. The family and its potentials are F6 |
| Protected inner rings | Stacked rings take no part in exchange; ends and side-bound rings do | Steps are declared on places. No exchange step names the core place; only end steps touch it | Covered by declaration once F1 and F2 exist |
| The stirred flow reactor | Inflow of the feed at rate D·V, and outflow of everything at rate D: indiscriminate death | OL3's `cells.serial_transfer@1` (designed) is a discrete bottleneck. A held pool holds an activity, not a flow | **F4:** continuous flow |
| One finite pool for every fibre | Competition for building blocks | OL2's `cells.shared_pool@1` (in progress) | Covered by OL2 |
| The fibre population (5 × 10¹³ to 3 × 10¹¹ in 500 µL, §1.8 item 11) | Far too many to follow one by one | Lanes are worlds; K slots per world (64–256) | **A declared representative sub-volume** of K stacks (L7) |
| Isotope labels (1′) and the retention readout | Mass-resolved isotopologues; the readout counts pure and mixed hexamers, molecule by molecule | OL3's labels (§0.2c rule 17): an amount per label per place, read by no law | **Two readings** (below). No new feature beyond F6's family |
| Readouts (UPLC peak areas) | Relative peak areas at 254 nm | Analysis of the records, in `validation/` | Validation work |

**Light, and where the free energy comes from** (**S**, with standard values from memory).
- **The net reaction is already downhill in the dark.** Two thiols oxidised by O₂ to a disulfide
  release about 82 k_BT with water as the product, or about 39 k_BT with H₂O₂ (from E° of O₂ and of
  a cysteine-like disulfide, from memory). The light speeds a reaction that is already allowed.
  - So the selection is kinetic: the rate of precursor supply.
  - The replicators' distance from equilibrium is paid by four sources:
    - the oxidation (dithiol and O₂ against disulfide);
    - the stirring (shear work at each break);
    - the inflow (a source);
    - the lamp (photons, mostly dissipated).
  - These are the design note's §3.1 sources: a chemostat (O₂ held), a fuel-to-waste step, shear,
    a schedule, and light.
- **A visible photon carries 89–121 k_BT at 298 K,** across 540–400 nm (**S**: E = hc/λ).
  - That is 110 k_BT at ThT's filter edge (435 nm).
  - Singlet oxygen's excitation is 0.98 eV, 38 k_BT (from memory).
- **So one absorption event exceeds the design's event domain of 80 k_BT** (the design note's
  §2.1), and a one-step oxidation to water sits at its edge.
  - On main, OL1 enforces that bound only on a catalyst's ΔΔG‡ (`transition_state.py`), and no
    check on an event's ΔF was found.
  - Light needs the domain widened, or a stepwise path, before a photon step is admitted (L8).

**Labels against isotopologues.**
- **OL3's labels answer the retention claim directly.** Mark each stack's side-bound precursors
  with that stack's label. "How much of stack j's growth came from its own precursors" is then a
  label measure: whose material went where.
- **The paper's readout needs more.** It counts pure (1₆, 1′₆) against mixed (1ₙ1′₆₋ₙ)
  hexamers, a property of each molecule. A label is an amount per place, not a joint composition
  inside one molecule.
- **So the readout takes isotopologues as declared species:** 1 and 1′ with identical potentials
  and kinetics, giving the seven hexamers 1ₙ1′₆₋ₙ. Their identity is itself a planted check: the
  sum over labels must behave as one species.

## 4. What the engine lacks, as general features

None is specific to this paper (D136, D144).
- **The fibre is the second geometry kind,** after the bilayer.
- **Its general uses:**
  - the side place serves adsorption on any assembly;
  - light serves photochemistry;
  - flow serves any chemostat.
- **Each feature needs its own design section (D142),** references and qualification before a
  replication relies on it.

**The physics choices are questions for the lead (§7.3),** to be ruled into the design note's §0.2.

| Feature | What | Milestone | Files and owner (CORE_SEAMS_DESIGN §18; STEP0 §4.2) | Agent-days (**S**) |
| --- | --- | --- | --- | --- |
| **F1. A linear-stack geometry kind** | `cells.linear_stack_geometry@1`, on `cells.assembly_geometry@1`: length from the core's count, two ends, side area in proportion to length. An end-capture encounter (`exchange_encounter: end_capture`, extent ∝ the number of ends). An end cost, like the vesicle's C_close, entering only where the number of stacks changes | New item **OL10, stacks and flow**, after OL3 | The OL2/OL3 builder's: `models/assembly_lineages_v2/` (the geometry and exchange modules, which are on `ol2-engine` and not yet on main; world, spec, kernel, balance and records); `validation/assembly_lineages_v2/`; their tests; @2's rows in `registry/model_table.py` | 2.5–4 |
| **F2. Side places** | A third place kind on an assembly, beside membrane and lumen. A join from the pool with a side-area encounter, the leave from F. Side-locus steps, and side-to-core steps at the ends. A binding term that depends on the core's composition (a new law on OL1's free-energy hook). The photo-step's cross-phase encounter (L3) | OL10 | The OL2/OL3 builder's, as F1; `records/relations.py` for labels on side places | 2.5–4 |
| **F3. Light** | A held photon species with a declared potential. Absorption as an event, booked as lamp work (payer `source:light/<name>`). The design's event domain widened, or a stepwise path required, with the check made explicit (L8) | **OL4b**, with OL4 (energy) | OL4's builder (not yet seated). The photon's entry goes in `registry/species_registry.py` (the binding owner's). The payer goes in `records/relations.py` (the OL2/OL3 builder's) | 2–3 |
| **F4. Continuous flow** | A population operator. Poisson outflow per assembly and per pool molecule at a dilution rate D. Inflow of a declared feed as a source (`source:inflow/<feed>`, substrate), with a schedule for a change of feed. Slots freed by outflow. Generalises `cells.serial_transfer@1` from a discrete bottleneck to a continuous one | OL10 | The OL2/OL3 builder's: the population and transfer modules (planned names, from the OL2/OL3 check's §8, not files on main) and `streams.py` (a stream for flow in the `schedule` domain); `records/relations.py` (an end reason for washout, in the next relations version) | 1.5–2.5 |
| **F5. Stack breaks** | A break rule for `cells.shear_fission@1`: a rate per interior bond under declared agitation, the break point uniform over the bonds, the split by layers (lumped: hypergeometric at the drawn sizes), booked as shear work | OL10 | The OL2/OL3 builder's division module (a planned name, from the OL2/OL3 check's §8) | 1–1.5 |
| **F6. A ring family** | Building-block moieties; rings by size and composition, in capacity buckets (sizes 3–6 with two building blocks: 4 + 5 + 6 + 7 = 22 species); oxidation and exchange steps with registry potentials; isotopologues as declared twins | With **OL8** (its family machinery) | OL8's builder (not yet seated), with the binding owner for the family's registry declaration (`registry/species_registry.py`; the design note's R7) | 2.5–4 |
| **References** | F1–F6's component claims, each with a planted error, by an agent who never reads the engine (as OL5) | Beside OL10 and OL4b | OL5's `validation/ool/references` | 3–4.5 |
| **In all** | | | | **15–23.5** |

**Reference forms the components could be checked against** (**S**, all standard; for the
references agent to derive independently):
- the stack's length and end count from its counts;
- binding isotherms on a side;
- a chemostat's washout and steady state for one replicator, in closed form;
- the steady length distribution under constant per-bond breakage and end growth;
- the photon ledger's closure.

## 5. The reference

### 5.1 The authors' model was not run

- **Its licence allows it.** CC BY 4.0, from the Zenodo record's metadata: it may be run and
  cited, with attribution.
- **It was downloaded and read.** Its md5 matches the record's.
- **It is MATLAB** (`ode15s`), and neither MATLAB nor GNU Octave is installed.
- **The install was refused.** GNU Octave 10.3.0 was to come from conda-forge through micromamba,
  into the downloads folder, pinned to the light CPUs and started with no startup files. The
  session's permission system refused the command that would have extracted and run the
  downloaded micromamba binary (18 November 2026).
  - Nothing in it was executed.
  - As the brief requires, the refusal is reported and not routed round: no other installer or
    container was tried, and the code was not transcribed.
- **Criteria M0–M6 stay registered** (§2.5, committed at 3c9572bf before any run).
  - D220 approves the run itself.
  - What it waits for is an environment that the user, or the session's permissions, allow
    (§7.3, U3).
- **Meanwhile the reference is the SI's own plotted model outputs,** read with §2.5's tolerances.
  These are readings, not a run:

  | Case | Value at 100 h |
  | --- | --- |
  | Supplementary Fig. 121 | A₃B₃ 0.62 of the building blocks; A₆ = B₆ = 0.07 |
  | Supplementary Fig. 122 | A₆/B₆ about 1.55, still rising slightly |
  | Supplementary Fig. 123 | A₆/B₆ about 1.245 |
  | Supplementary Figs. 124–125 | The colour grids (§1.8, items 9–10) |

- **What a run could judge, and what not.** The code's fixed inflow (1:1), outflow (0.04 per h),
  seeds and 100 h horizon mean that an unmodified run gives references only for the two model
  claims (Supplementary Figs. 121–125).
  - It judges no target on the 2 + 3 system, the inflow ratio, the flow rate or retention: T0,
    T1, T3, T4, T5 and T7.
  - It bears on T2 and T8 only in kind.

### 5.2 Why Cells cannot reproduce the authors' model as written

- **Its oxidation steps are not elementary mass action.** They have half orders and a
  non-integer product (A₁.₅B₁.₅), and the 3A → A₃ step is written first order. D152's mass action
  takes integer coefficients and at most three reactant molecules.
- **Its steps are irreversible, and its oxidation names no oxidant.** §3.2 of the design note
  refuses a driven law without a source in this family. D199's U2, the lead's call, set one F for
  every law.
- **The code's rates depend on population shares** (x_h), not on one assembly's own counts and its
  pool.

So **the first Cells model is Cells' own admissible version, not a transcription.** Its comparison
with the authors' model is in kind: T8a and T8b, as orderings.

### 5.3 The smallest population model with mutants, and which comes first

**R0: three hexamer types in stacks, in flow, oxidised in the dark.** Cells' admissible form of
the authors' model, built from F1, F2, F4 and F5.
- **The pool:** building blocks A and B, finite and fed (F4); O₂ held.
- **Oxidation:** one building block and one O₂ give an activated unit and waste. Three units close
  a trimer, at most three molecules per step. The oxidant's form is L2's question.
- **The trimers** are A₃ and B₃ only. The mixed trimer is left out, a declared truncation, so that
  the hexamers are the authors' three. They sit in the pool and on stack sides (F2).
- **Stacks** (F1). Their cores count A₆, A₃B₃ and B₆.
  - An end turns two side trimers into a hexamer: A₃ + A₃ → A₆, A₃ + B₃ → A₃B₃, B₃ + B₃ → B₆.
  - Fidelity comes from the core's composition, as a factor on m (OL1's law).
- **Breaks** under stirring (F5) and **outflow** (F4).
- **Checks:**
  - the symmetric case gives A₆ = B₆, M0's analogue;
  - a chemostat's closed-form washout bounds the dilution rate.
- **Calibration:** it calibrates C3 and C5, in kind.

**R1: R0 plus light and the cofactor** (F3).
- **The photo-step.** One building block, O₂ and a held photon give an activated unit. It is
  catalysed by the side-bound sensitiser, with an activity per stack composition as a factor on m.
- **The two arms.**
  - **The ThT arm:** the product goes to the producing stack's side, its locality (L3).
  - **The control arm:** the same step catalysed in the pool, with its product in the pool.
- **The runs.**
  - An activity ratio of 2 on the A₆-rich stacks: T8a's analogue. A₆/B₆ is compared with
    Supplementary Fig. 122 in kind.
  - A run that changes fidelity only: T8b's analogue.
  - P1–P3.

**R0 comes first.** It needs no light, so it tests the stack kind, the sides, breaks and flow,
which every later world needs. **Then R1,** then:
- **R2, the 1 + 4 system:** trimers A₃, A₂B, AB₂ and B₃, the seven hexamers, 7:3 against 6:4.
  T2, T3, T5 and T8.
- **R3, the 2 + 3 system:** two stack kinds, trimer and hexamer, at three flow rates. T1 and T4.
- **R4, retention:** isotopologues and labels. T7.
- **R5, the batch photo-replication:** T0.

R2–R5 need F6's ring family; R0 and R1 need only its minimal subset.

## 6. What a judged comparison would need: a D138 question for the user

A judged comparison needs the user's approval and a registered protocol (D138). Proposed, for the
user to decide:
- **(a) Now: development only.**
  - Build §4's features as general engine features, each with its references and qualification.
  - Run R0–R5 as development work against §2's registered targets: reported, not judged.
- **(b) Then, a judged comparison against the paper's orderings.**
  - T0–T5 and T7, from the workbooks, with §2's O and F as the criteria. The protocol is drawn
    from §2 and registered before the judged runs, once R2 and R3 run.
  - **Recommended** as the reference for judgement.
- **(c) Against the authors' model's outputs:**
  - only T8a and T8b, and only in kind;
  - the model is not admissible in this family (§5.2), has three types and a fixed 1:1 feed;
  - it needs the model to run (§5.1, U3).

  **Recommended** as a reported reference, not judged.
- **(d) Against both,** with (c)'s numbers reported beside (b)'s verdicts.

## 7. The plan

### 7.1 Milestones, and their order against OL2 and OL3

| Milestone | Content | Engine models it runs | Needs | Agent-days (**S**) |
| --- | --- | --- | --- | --- |
| **SR0** Desk | This note; the lead's rulings and the user's answers on §7.3's questions | None (design) | — | Done; 0.5 for the amendments |
| **SR1** Reference | The authors' model run out of process against M0–M6 | None. It is tooling (D138; AGENTS.md), and D220 approves it as a reference since the licence allows | An environment (U3) | 0.5 |
| **OL10** Stacks and flow (new) | F1, F2, F4 and F5, behind OL2's invariance gate; tests and tier rows | `cells.assembly_lineages@2` with `cells.linear_stack_geometry@1`, `cells.phase_exchange@1` (`end_capture`), the side-binding law, `cells.shear_fission@1` (stack breaks) and the flow operator | OL3 landed | 8–13 |
| **OL4b** Light | F3 | The photon source, with `cells.stochastic_mass_action@1` | OL4 | 2–3 |
| **Ring family** | F6 | `cells.stochastic_mass_action@1` over the family | OL8's family machinery | 2.5–4 |
| **References** | F1–F6's component references | OL10's and OL4b's models against them | — | 3–4.5 |
| **SR2** R0 and R1 | Three types, dark then light, with P1–P3, T8a and T8b | All of the above, with `cells.transition_state_factor@1` and `cells.shared_pool@1` | OL10, OL4b | 2–3 |
| **SR3** R2–R5 | 1 + 4, 2 + 3, retention, batch | The same, with the ring family | F6 | 3–4.5 |
| **SR4** Judged, if approved | The protocol from §2, the judged runs and their analysis | The same | U1 | 2–3 |
| **In all** | | | | **23.5–36** |

**The order.**
- **Lipids come first (D212).** No code starts before OL3 lands.
  - F1, F2, F4 and F5 extend OL2's geometry interface and shared pool, and OL3's fission, streams
    and transfer.
  - Those are the OL2/OL3 builder's files (CORE_SEAMS_DESIGN §18). Building earlier would put two
    owners on them, or bend OL2's and OL3's invariance gates.
- **OL10 follows OL3,** by the OL2/OL3 builder, or by a second builder after a hand-off the lead
  rules.
- **OL4b goes with OL4,** beside OL6.
- **SR1 can run at any time once approved.** It is out of process and touches no engine file.
- **Elapsed:** about 10–16 working days after OL3 lands, with two builders and the references
  agent (**S**). No dates are given (D194).
- **Staffing:** within the cap of seven (D171), beside the core pass and the programme's other
  milestones.

### 7.2 How this relates to the user's experiment idea

The user's reading summary (`docs/originOfLifeIdeas/READ_SUMMARY_OOL.md` §4) proposes an
autocatalytic network in a growing, dividing compartment, with energy, inheritance, perturbation,
and recovery of functional organisation against random, scrambled and no-history controls. It names
this paper as a strong starting point. Against that idea:
- **The system.** The paper's unit is a fibre, not a compartment. Retention on fibre sides stands
  in for a compartment, and the authors name a compartment system as future work (Conclusions).
  - In Cells the same pieces compose with OL2's and OL3's vesicles: rings and stacks in a lumen,
    with light or fuel.
  - So the user's experiment reuses this replication's general features rather than needing new
    ones.
- **Energy:** light and O₂ here (F3); OL4's fuels in the vesicle worlds.
- **Inheritance:** a fibre's composition, carried through growth and breakage. The design note's
  heritability measures (§5.1) apply to stacks as to vesicles.
- **Perturbation and recovery** are not in the paper. Cells could add them as an extension beyond
  the replication (U4).
  - **Perturbations:** a dark interval, a pulse of the 6:4 feed, or a pulse of 4-rich seeds, then
    a return to the base condition.
  - **Controls:**
    - random seeds of the same total composition;
    - scrambled seeds, with compositions reassigned among stacks;
    - no-history seeds, which are fresh.
  - **The question:** does the 1-rich organisation return, and how much does that depend on
    history? That is the summary's measurement row.
  - It would be registered on its own, not as part of this replication.
- **Adamala's 2026 synthetic-cell preprint** (Gaut et al., bioRxiv,
  doi:10.64898/2026.07.01.735724; SpudCell in docs/SOTA_ORIGIN_OF_LIFE.md) was not read for this
  note.
  - It bears on compartments, growth and division with supplied machinery: OL2, OL3 and the
    Syn3A track, not this chemistry.
  - D199 makes it a candidate benchmark, raised only after its primary source is read.
  - This note does that reading for D199's other candidate, the Otto-type replicators.

### 7.3 Questions

**For the lead** (physics choices, to be ruled into the design note's §0.2):
1. **L1, light and the cofactor's activity.**
   - **The options for light:**
     - (a) absorption as an event pair, with a held photon at a declared potential;
     - (b) a lumped photo-oxidation, with a held activated oxidant whose activity the light sets;
     - (c) light as a declared rate, booked as lamp work.
   - **Recommended: (a).** The paper gives no irradiance, so the photon's potential and flux are
     declared and marked unsourced.
   - **The cofactor.** C1 fixes only the product of the bound amount and the yield per bound dye
     (§2.6). How should that product split? All in the yield, with binding equal; or a declared
     binding ratio from the fluorescence data (Supplementary Figs. 92–95)?
2. **L2, the oxidant chemistry.**
   - **The options:**
     - (a) one building block activated per oxidant, then ring closure;
     - (b) explicit thiols and disulfide bonds, with exchange;
     - (c) the authors' lumped monomers-to-bound-trimers.

     (c) is not admissible (§5.2).
   - **Recommended:** (a) for R0 and R1, and (b) for the full library (F6).
3. **L3, locality.**
   - **The options:**
     - (a) a declared fraction of each stack's photo-products delivered to its own side: 1 in R1,
       0 in P2, calibrated by T7;
     - (b) derived from ¹O₂'s diffusion length and the stacks' number density, which the paper
       does not measure (§1.8, item 11);
     - (c) spatial resolution, which is out of scope.
   - **Recommended:** (a), with (b) reported.
4. **L4, stack resolution.**
   - **The options:** lumped, with counts per core species and ends taking the stack's mean
     composition; or layered, with an ordered sequence, so that ends carry their own composition
     and a break passes on contiguous pieces.
   - **Recommended:** lumped first, and layered as a later token value.
5. **L5, fidelity.**
   - **The options:**
     - kinetic, a factor on m from the core's composition (OL1's law), which leaves the
       equilibrium alone;
     - thermodynamic, composition-dependent stacking energies (a regular-mixing term, reciprocal by
       E2's lesson), which is selection by stability;
     - both.
   - **Recommended:** kinetic first, and the thermodynamic form as an arm.
6. **L6, breaks.**
   - **The options:** a per-bond rate under declared agitation, one-way and booked as shear work;
     or with end-to-end rejoining from F.
   - **Recommended:** one-way first.
7. **L7, flow and scale.**
   - A representative sub-volume of K stacks, its share of the reactor declared, with Poisson
     outflow per assembly and per molecule.
   - The stack size declared, and varied over 1.2 × 10³ to 1.8 × 10⁵ building blocks (§1.8,
     item 11).
   - Slots sized by a preflight, since a full set stops the run (§0.2c rule 13).
8. **L8, the event domain.**
   - The design's |ΔF/k_BT| ≤ 80 (§2.1) is reached by visible photons (89–121 k_BT) and by a
     one-step O₂ oxidation to water (about 82 k_BT, from memory).
   - On main it binds only a catalyst's ΔΔG‡.
   - Widen it, or require stepwise forms? And should an event's ΔF be checked explicitly?

**For the lead** (process):

9. **L9, numbers from a subscription article: answered by D220.** The user's terms give its numbers
   as read, with their citations. This note keeps the question's number so that the references to
   it stay valid.
10. **L10, milestones and owners.**
    - **The proposal:** OL10 by the OL2/OL3 builder after OL3; OL4b with OL4's builder; F6 with
      OL8's builder and the binding owner; the replication's driver,
      `validation/self_replicator_selection/`, by this track.
    - **The index:** an index line in `docs/README.md` and a row in `docs/PAPER_BACKLOG.md`, which
      this note leaves to the lead.

**For the user:**
1. **U1, D138.** Development only now (recommended)? Then a judged comparison against the paper's
   orderings (T0–T5, T7) once R2 and R3 run, with the authors' model as a reported reference only
   (§6)?
2. **U2, scope and order.**
   - The replication after OL3 (lipids first, D212), at about 23.5–36 agent-days, with its
     features general (stacks, surfaces, light, flow)?
   - Or a first pass of R0 and R1 alone, about 16–25?
3. **U3, the authors' MATLAB code.**
   - **The run is approved.** D220 approves it as an out-of-process reference, since its licence
     (CC BY 4.0) allows. That is D138's approval for this paper. What remains is an interpreter.
   - **The install was refused.** The install of GNU Octave (GPL, run out of process only) under
     the downloads folder was refused by the session's permission system.
   - **The choice:** approve that install, or another route, or leave the model unrun, with its
     plotted outputs as the reference?
4. **U4, an extension beyond the replication.** Perturbation and recovery, as the reading
   summary's experiment (§7.2), registered on its own after the replication?

## Sources

**Fetching.**
- Plain requests with a generic client name, carrying no user details.
- Each download in its own folder under
  `/mnt/workspaces/Cells/self-replicator-selection-20261118/downloads/`, treated as untrusted and
  read with `python -I` or `pdftotext`.
- Nothing from them is committed.

| Source | Result |
| --- | --- |
| The paper, *Nat. Catal.* 8, 1000 (2025) | Read in full; not reproduced. The publisher's page marks it as not free to read |
| Its Supplementary Information (MOESM1), 134 pages | Read: sections 7–17, the captions of Supplementary Figs. 90–126, and the figure pages of Supplementary Figs. 114 and 121–125 |
| Supplementary Data File 1 (MOESM3) | Read: the sheets for Supplementary Figs. 96–101 and 104–120 |
| Source Data for Figs. 2–5 (MOESM7–MOESM10) | Read whole |
| Supplementary Videos 1–3; the Reporting Summary | Not downloaded |
| Zenodo record 15104674: metadata and `FAMonomers5d.m` | Read. CC BY 4.0. Not run (§5.1) |
| micromamba 2.10.0 (conda-forge) | Downloaded; not extracted or run, since the command was refused |

**Engine documents read:**
- AGENTS.md;
- `docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md` (the whole note);
- `docs/ORIGIN_OF_LIFE_OL2_OL3_CHECK.md`, `docs/SOTA_ORIGIN_OF_LIFE.md`, `docs/GARD_DESIGN.md` and
  `docs/RELATIONSHIPS_DESIGN.md` (§2, and the lead's review and rulings);
- `docs/DECISIONS.md`: D136–D138, D142, D144, D173, D186, D197–D201, D207, D208, D212, D215 and
  D220;
- `docs/GAP_JUNCTION_CANCER_REPLICATION.md`, this note's pattern;
- `docs/CORE_SEAMS_STEP0.md` §4.2 and `docs/CORE_SEAMS_DESIGN.md` §18–§19;
- `docs/originOfLifeIdeas/READ_SUMMARY_OOL.md`;
- `docs/PAPER_BACKLOG.md`.

**Cited from memory, not read for this note:**
- the standard redox potentials of O₂ and of cysteine-like disulfides;
- singlet oxygen's excitation energy;
- the photon energy E = hc/λ;
- the chemostat's washout.
