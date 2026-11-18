# Self-replicator selection replication

**The paper.** K. Liu, O. Markovitch, C. van Ewijk, Y. K. Knelissen, A. Kiani, M. Eleveld, W. H. Roos
and S. Otto, "Selection for photocatalytic function through Darwinian evolution of synthetic
self-replicators", *Nature Catalysis* 8, 1000–1009 (2025),
doi:[10.1038/s41929-025-01409-3](https://doi.org/10.1038/s41929-025-01409-3) ("the paper").
- **Access.** It is a subscription article. Its text was read from a private copy outside the
  repository and is never reproduced here: this note paraphrases it and cites by location.
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
  - It is never copied into Cells; §5 says how it was run.

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
- **from the code**, or **from its run** (§5).

**Evidence.** The scripts that read the workbooks use the standard library alone, run with
`python -I`, and write their outputs beside them:
- `/mnt/workspaces/Cells/self-replicator-selection-20261118/`, in `scripts/` and `results/`;
- the downloads in `downloads/<name>/`.

Nothing from the downloads is committed.

**Numbers from a subscription article.** D186 and D201 allow cited numbers from open and
free-to-read papers. This article is neither, though its SI and workbooks are free to download.
The lead's brief directs numbers as read, with their locations. §7 asks the lead to confirm that
(question L9).

**Engine models run: none.** Docs only. The milestones in §7 name the models they would run. The
authors' model was run out of process, as a reference (§5).

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
- **Locality.** ¹O₂ lives about 3.5 µs in water (printed; the paper's ref. 41). It therefore
  oxidises building blocks near the fibre that made it, and is unlikely to reach a neighbouring
  fibre (SI Table 1 and Supplementary Fig. 101; §1.8, item 11).

### 1.2 The activities: what bound ThT does

| Quantity | Value | Source |
| --- | --- | --- |
| ¹O₂ from 1₆–ThT, against 1₃/1₄–ThT and against ThT alone | The probe's fall, fitted by least squares: 0.049, 0.014 and 0.0033 per h, ratios 3.6 and 14.7. The text says only "more efficiently" | Supplementary Fig. 96d; derived (**S**) |
| Oxidation of 1 in 2 h (µM; each the mean of two repeats) | 25.6 (1₆ + ThT, light); 14.9 (1₃/1₄ + ThT, light); 4.3 (ThT, light); 4.6 (1₆, light); 4.8 (1₆ + ThT, dark); 4.4 (1₆, dark) | Fig. 2a, from the workbook |
| The same as ratios | The text: about twice that of 1₃/1₄–ThT and about four times that of ThT alone. The workbook: 1.71 and 5.99, and 2.03 against 1₃/1₄–ThT once the dark mean (4.57) is subtracted | Fig. 2a; derived (**S**) |
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
   - The text's "about twice" and "about four times" are 1.71 and 5.99 in the workbook (§1.2).
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
  - **Its constants:** they were chosen to reproduce the observed behaviour (SI Table 3's
    heading), so its agreement is not a prediction.
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
| C1 | Activity ratios of the bound cofactor: hexamer against trimer stacks, 2.6; 1-rich against 4-rich hexamers, 2.8; bound against unbound | Supplementary Figs. 96–98; Fig. 2a (§1.2) |
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
| **T5** | 1 + 4 at 7:3: the control centres on 1₄4₂, and ThT shifts weight to n ≥ 5 | Control mode 1₄4₂ in 8 of 8 runs; the n ≥ 5 share higher with ThT by 0.065–0.216 | Both hold | The difference lies in [0.033, 0.43] | P1 | The paper's data |
| **T6** | The approach to steady state | 2 + 3: 80–150 h (about 2.6 residence times); 1 + 4: about 50 h (2) | Within 1.5–5 residence times | — | — | Descriptive |
| **T7** | Retention: separately loaded fibres grow more pure hexamers, partly | Pure share 0.21 against 0.08 (n = 4, overlapping) | Separate > mixed, and separate < 0.5 | — | Bound precursors exchanged freely: the shares become equal | Calibration of C6. The paper's data |
| **T8a** | A 1-rich/4-rich activity ratio of 2, rather than the measured 2.8, still passes T2 | The authors' claim (Supplementary Fig. 122) | T2's O | T2's F | — | The authors' model, in kind |
| **T8b** | A cofactor that only lowers the 4-rich stacks' fidelity, with equal activity, does not pass T2 | The authors' claim (Supplementary Figs. 123–124) | T2's O fails, or s < 0.172 | — | — | The authors' model, in kind |

**The planted controls,** each of which must hold for the criteria to have teeth (D187):
- **P1, equal activity.** The bound cofactor activates every stack composition alike, at the same
  total oxidation as the control. Expected: |s| ≤ 0.1, below T1's and T2's lower F bounds (0.227
  and 0.172).
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
