**A transient Myc + cyclin T1 modRNA in the infarcted heart: relevance to Cells — reviewed 14 November 2026**

**The paper.** Boikova, A., Quaife-Ryan, G. A., Batho, C. A. P., Dahir, R.,
Cserne Szappanos, H., … Sinha, S., Hudson, J. E. & Wilson, C. H.
*A transient modified mRNA encoding Myc and cyclin T1 improves cardiac function
after myocardial injury.* **Nature Cardiovascular Research** (2026),
[10.1038/s44161-026-00910-7](https://doi.org/10.1038/s44161-026-00910-7).
Received 16 July 2025, accepted 8 October 2026, **published 9 November 2026**.
Open access, **CC BY 4.0**. No volume or article number is assigned yet; the
article page carried 5,117 accesses and 1 citation when read.

**Its predecessor.** Bywater, M. J., Burkhart, D. L., Straube, J., Sabò, A.,
Pendino, V., Hudson, J. E., Quaife-Ryan, G. A., Porrello, E. R., Rae, J.,
Parton, R. G., Kress, T. R., Amati, B., Littlewood, T. D., Evan, G. I. &
Wilson, C. H. *Reactivation of Myc transcription in the mouse heart unlocks its
proliferative capacity.* **Nature Communications** **11**, 1827 (2020),
[10.1038/s41467-020-15552-x](https://doi.org/10.1038/s41467-020-15552-x),
published 14 April 2020, CC BY 4.0. Bywater, Straube, Hudson, Quaife-Ryan,
Porrello and Wilson are authors on both.

**Why it is here.** The user, 14 November 2026: *"we'd like to be able to model
this in Cells soon"*, with the paper placed high in the backlog. "Soon" is the
priority, so §6 is the substance of this review and is written to be actionable
rather than complete.

**Notation.** **S** marks an inference by this reviewer, not a statement in
either paper. Everything unmarked is cited to a section, figure or
extended-data figure of the source.

---

**Verdict first.** Both papers were read in full from the publisher's HTML (§1).
The paper is a careful, well-controlled mouse study whose central result is a
**dose–localisation** result, not merely a potency result: the *same* genetic
intervention killed 7 of 8 mice when it acted across the whole heart and was
beneficial and non-lethal when restricted to roughly a tenth of the left
ventricle. That is the finding with the most purchase on Cells, because the
authors' own proposed mechanism for the lethality is **bioelectric** — reduced
`Scn5a` and `Gja1` in proliferating cardiomyocytes, and the disruption of
beating by cells that must disassemble sarcomeres to divide — and **they measured
no electrical quantity at all** (§2.11). Cells has gap junctions, membrane
voltage and generic voltage-gated channel laws, and it has division operators;
it has no cardiac action-potential model, no contractility and no scar.

Three things follow.
1. **There is a real version 0 that could run soon** (§6c), using only landed or
   next-to-land features, and it targets the spatial-restriction question rather
   than the paper's headline efficacy numbers. It would show something genuine
   and would not show regeneration, function or arrhythmia.
2. **The paper's headline readouts — LVEF, scar, survival — are out of reach and
   should not be promised.** They are organ-scale and need contractility,
   fibroblasts and a matrix the engine does not have (§6b). Chasing them would
   be the D144 mistake.
3. **The paper supplies two usable calibration targets**, which is rare in this
   backlog: a protein-pulse shape with timed measurements (§2.2) and a cited Myc
   protein half-life of 20–40 min. Both are generic kinetics, not cardiac
   parameters.

No simulator change, parameter fit, run or scientific acceptance follows from
this review. It adds notes and a plan only.

---

## 1. Access and what could not be read

Both versions of record were obtained in full as publisher HTML and converted to
text; every citation below is to that text. Nature's own page redirects to its
identity provider, so the fetch tool could not read it; `curl` with a cookie jar
retrieved the full article. The paper is **not in PMC**. URLs, dates, methods,
licences and the derived files are in the
[access log](/mnt/workspaces/Cells/paper-review-myc-cyclint1-20261114-01/ACCESS_LOG.md).

**Not read, and so not cited as read:**

- the **Supplementary Information PDF** (Supplementary Figs. 1–6), the
  **Reporting Summary**, the **Peer Review File**, and **Supplementary Tables
  1–5** (XLSX). These are separate downloads from the article page. Where the
  main text rests on one of them — notably the `Scn5a` and `Gja1` claim, which
  cites Supplementary Tables 1 and 2 — this review says so;
- the per-animal **Source Data** workbooks, so no number here was recomputed.
  Every value is as printed in the main text or a figure legend;
- the 2023 bioRxiv preprint and the first author's 2025 Cambridge thesis, which
  a search surfaced. Neither was fetched and neither is cited; only the two
  versions of record are used.

Neither paper deposits model or simulation code, so no external simulator or
code licence needed checking. Sequencing and proteomics deposits are named in
§2.10 and were not downloaded.

## 2. The paper, as data

### 2.1 The model systems, delivery, dose and timing

| Element | What was used |
| --- | --- |
| Mouse lines | `Tg(Myh6-Cre)1Jmk/J` (cardiomyocyte-specific Cre) and `Gt(ROSA)26Sor^tm3(CAG-MYC/ERT2)Gev` ("CMER", a tamoxifen-switchable MycER^T2 generated in the 2020 paper); `Gt(ROSA)26Sor^tm14(CAG-tdTomato)Hze` reporter; outbred **CD1** for all modRNA efficacy work (Methods, *Ethical approval and animal experiments*) |
| Cyclin T1 | `AAV9-cTnT-3xFLAG-mCCNT1-WPRE`, **1 × 10¹¹ GC in 100 µl, tail vein, at 4–5 weeks of age** — so cyclin T1 is a *sustained* background, not a pulse (Methods) |
| Myc activation | **1 mg tamoxifen** i.p. in 10% ethanol/corn oil (10 mg ml⁻¹), **twice over 48 h**; tissue at 48 h after the first injection (Methods) |
| Injury | **Permanent LAD coronary artery ligation**, lateral thoracotomy at the 4th intercostal space, 7-0 Prolene, just below the exit under the left atrium; MI verified by myocardial blanching (Methods, *Adult mouse MI*) |
| modRNA dose | **100 µg modRNA in 20 µl PBS + 40 µl Lipofectamine RNAiMAX**; 20 µl of the mix injected at **three sites in the ischaemic penumbra** (anterior superior, anterior inferior, posterior superior LV wall), during surgery immediately after MI (Methods) |
| The construct | **One** modRNA encoding **Myc and Ccnt1 separated by a T2A sequence** ("M-C"); N¹-methylpseudouridine replaces UTP; ARCA, CleanCap AG or CleanCap 3′ OMe caps (Fig. 5a; Methods, *ModRNA*). Mouse and human ORFs both built, with no significant functional difference in vitro (Extended Data Fig. 6a,b) |
| Function | Echocardiography, **Vevo 2100/3100**, MS550D 40 MHz, isoflurane 1.5%, **blinded to genotype and treatment**; EF from B-mode (three short-axis plus one parasternal long-axis) or M-mode (Methods, *Echocardiography*) |
| Cardiomyocyte counts | Whole heart fixed in 1% PFA overnight, dissociated in 0.5 U ml⁻¹ collagenase B over **~8 days**, counted on a **haemocytometer** (Methods, *fix dissociation of cardiomyocytes*) |
| Statistics | GraphPad Prism v9.0d; **blinded** for surgery, echo, histological area measurement and cell counting; *P* ≤ 0.05 significant (Methods, *Statistical analysis*). **No power calculation, pre-registration or multiplicity correction is stated, and several primary endpoints use one-tailed tests** (§4) |

Delivery is the hinge of the whole study, in two ways worth keeping in view.
**Cyclin T1 is chronic and Myc is pulsed** in every genetic arm: the AAV is given
four weeks ahead and is never withdrawn, so "transient" refers to Myc alone.
Only the M-C modRNA arm pulses both together. And **lipofectamine is not
translatable** — the authors say so plainly ("this method of delivery could not
be used in patients", Discussion).

### 2.2 The expression kinetics of the pulse

Three independent measurements, on three different reporters, at three scales.

| Measurement | System | Result |
| --- | --- | --- |
| **FLuc bioluminescence** (the modRNA platform's own kinetics) | CD1, MI + 100 µg FLuc modRNA i.c.; IVIS at 8 h, 1, 2, 3, 7 d; n = 4, 3, 4, 6, 5 | "Localized and 'pulse-like'", peaking early, with a **5.5-fold fall from 8 h to 48 h** (Fig. 4b). Imaging times in Methods are 6, 8, 24, 48 and 72 h |
| **Myc and cyclin T1 protein in vivo** | CD1, MI + 100 µg M-C or GFP modRNA; immunofluorescence and IHC on serial sections, n = 3 | Protein **present at 1 h and 4 h**; "we did not observe protein expression at **24 h** in heart tissue, while **GFP expression was maintained for at least 48 h**" (Fig. 6b; Extended Data Fig. 7a, which shows GFP at 30 min, 4 h, 24 h, 48 h and Myc/cyclin T1 at 4 h and 24 h) |
| **Protein in vitro** | hES cell-derived cardiomyocytes; immunoblot and LC–MS/MS at 1, 4, 18, 48 h (n = 3 per condition) | Transcript up at 1 h (*P* = 0.006, n = 4); protein at 1 h and 4 h (*P* = 0.029, n = 4); **diminished at 18 h and 48 h** (Extended Data Fig. 6c); abundance "transient and depleted by the 48-h time point" (Fig. 5e) |

Two further results pin the mechanism of the decay rather than just its rate.
**Proteasome inhibition (MG132) prolonged Myc expression** at 8 h and 24 h
(Extended Data Fig. 6d), so the short window is set by protein turnover, not by
mRNA loss. And the Discussion cites an **endogenous Myc half-life of "around
20 min to 40 min"**, degraded through the ubiquitin–proteasome pathway via E3
ligases such as FBXW7 — the authors' explanation for why the ectopic protein is
also short-lived, since they used the endogenous mouse sequence.

**Downstream response outlasts the protein.** Myc-responsive transcripts
(`SMPDL3B` *P* = 0.016, `GNL3` *P* = 0.028, `POLR3G` *P* = 0.012; n = 4) rise as
early as **1 h**, and translated Myc targets are **increased at 18 h and 48 h**,
with mTORC1, E2F-target and G2M-checkpoint signatures (Fig. 5d,g,h) — after the
driver protein is gone.

**What this does and does not show.** It establishes a pulse whose protein phase
is on the order of hours and whose consequences persist for days. It is **not** a
decay curve: the in vivo 24-h result is the *absence of staining* at a single
time with n = 3, not a fitted rate, and no time point lies between 4 h and 24 h
for Myc. **S** For modelling, the usable shape is "input over a few hours,
clearance with a ~20–40 min protein half-life, response integrated over days" —
and the separation between the chronic AAV cyclin T1 and the pulsed Myc in the
genetic arms matters more than either rate.

### 2.3 Cell-cycle markers: DNA synthesis, mitosis, cytokinesis

**Whole-heart genetic activation after MI, 48 h after tamoxifen** (Fig. 1b,c;
Extended Data Fig. 1), percentage of cardiomyocytes, border zone (BZ) versus
remote zone (RZ):

| Marker | Stage it reports | Control | BZ, Myc + cyclin T1 | RZ, Myc + cyclin T1 |
| --- | --- | --- | --- | --- |
| **Ki67** | general cell cycle | 0.2% (cre + oil) | **25.1%** | 6.2% |
| **P-H3** | mitosis | 0.5% (cre + oil) | **6.9%** | 2.9% |
| **Aurora B kinase** | interphase to cytokinesis | 1.4% (cre + oil) | **4.4%** | 0.6% |

n = 7 (cre + tam) against two controls, cre + oil n = 5 and no-cre + tam n = 3;
Aurora B n = 6 against n = 4. Two-way ANOVA with Šídák, **BZ versus RZ**: P-H3
*P* = 0.0021, Ki67 *P* < 0.0001; Aurora B, cre + tam versus cre + oil in the BZ
*P* = 0.0287. Extended Data Fig. 1a,b adds per-group one-way ANOVA with Tukey
(BZ Ki67 *P* = 0.0009 and 0.0007 against the two controls; RZ *P* = 0.0462 and
0.0195). Aurora B was scored by stage, including **symmetrical mid-bodies**, and
prometaphase and metaphase examples are shown (Fig. 1c; Extended Data Fig. 1c).

**The spatial result is the point.** The remote zone response (Ki67 6.2%, P-H3
2.9%) matches the undamaged heart of the 2020 paper, while the border zone is
about fourfold higher for Ki67. The authors read this as the infarct border
supplying "additional mitogenic stimuli" on top of Myc and cyclin T1
(Discussion), and §2.3's snRNA-seq ligand–receptor analysis is their evidence for
what those might be (§3).

**modRNA, in vivo** (Fig. 6h–j). EdU 12.5 mg kg⁻¹ i.p. at **8 h and 24 h** after
MI, hearts at 48 h: **EdU⁺ cardiomyocytes increased**, *P* = 0.011, n = 6;
**P-H3⁺ cardiomyocytes increased**, *P* = 0.0065, n = 6, both two-tailed
Mann–Whitney. Notably, the **total number of P-H3⁺ events was unchanged**
(NS, *P* = 0.3095) — the increase is in the cardiomyocyte share, not in overall
proliferation in the tissue. The Discussion compares magnitudes with other
mitogenic strategies: a ~20-fold Ki67 increase and ~14-fold P-H3 increase for
cyclin T1 + MycER^T2, and ~12-fold P-H3 for a single M-C modRNA dose, against
~4–5-fold (`Cpt1b` knockout), ~8-fold (`Pdk4` knockout, `Pkm2` modRNA) and
3-fold (malonate) in the cited literature.

**modRNA, in vitro** (Fig. 5i–m). In hES cell-derived cardiomyocytes at 48 h:
Ki67⁺ up (*P* < 0.0001; GFP n = 22, M-C n = 23), cross-sectional area **reduced**
(*P* = 0.0146), **cell number increased** (*P* = 0.035). In primary mouse
cardiomyocytes, P1: Ki67 *P* = 0.0004, BrdU *P* = 0.0033, Aurora B total
*P* = 0.0089, **Aurora B mid-body *P* = 0.0105** (n = 3 or 5, three litters);
P7: Ki67 *P* = 0.0061, BrdU *P* = 0.0445, Aurora B total *P* = 0.0123 (n = 3 or 4,
two litters) — and **Ki67 in non-cardiomyocytes also rose** at P7
(*P* = 0.0229), an early sign of the specificity problem in §2.10.

**Delayed activation, day 7–8** (Fig. 7g). Ki67 was found **exclusively within
tdTomato⁺ Cre-recombined cardiomyocytes**: 0.3% (cre + oil) versus **8.4%**
(cre + tam), 48 h after activation; two-way ANOVA with Fisher's LSD, tdTomato⁺ MC
versus control *P* = 0.0040, and MC tdTomato⁺ versus tdTomato⁻ *P* = 0.0028
(MC n = 10, control n = 7). This is the cleanest internal control in the paper:
the effect tracks the recombined cells, within the same heart.

**What the markers do and do not show.** Ki67, EdU and P-H3 report cycle entry,
DNA synthesis and mitosis. Aurora B at a symmetrical mid-body is evidence of
**attempted cytokinesis**, and is the strongest cytological claim made. None of
these demonstrates a completed division of a *particular* cell; that claim rests
on the counts (§2.4) and the pair tracking (§2.5). Cardiomyocyte
**polyploidy and multinucleation are the standing confound** in this field, and
the paper addresses it with PCM-1 nuclear identification, cell counts and the
CycleTrack assay rather than by measuring ploidy here; the 2020 predecessor did
report no discernible change in nucleation (Supplementary Fig. 9e there).

### 2.4 Cardiomyocyte counts

- **modRNA, day 5 after MI:** total heart cardiomyocyte number **increased**,
  unpaired two-tailed t-test *P* = 0.0176, n = 9 (Fig. 6k). The legend prints
  "*P* = 0. 0.0176", evidently a typographical error.
- **In vitro, 48 h:** cardiomyocyte number increased, *P* = 0.035 (Fig. 5k),
  with cell area *reduced* (*P* = 0.0146) — the combination expected of division
  rather than growth.
- **2020 predecessor:** in juvenile (15-day) hearts a **1.8-fold increase in
  cardiomyocyte number with no discernible change in cardiomyocyte size**
  (Fig. 7c,d there), and in adult hearts with ectopic cyclin T1, increased
  cardiomyocyte number at 72 h without measurable change in size or nucleation
  (Fig. 9c–e there, Mann–Whitney *P* = 0.0043).

The method is whole-heart fixation and an 8-day collagenase dissociation counted
on a haemocytometer (§2.1). **S** That counts cells recovered, so it is sensitive
to dissociation yield; blinding (stated for cell counting) protects against
scoring bias but not against a systematic yield difference between a
remodelling and a control heart. The day-5 timing is, however, early enough to
sit before most scar remodelling.

**Cross-sectional area is the companion measure, and it is consistently
unchanged in vivo**: Fig. 4h (one-way ANOVA with Tukey, NS, including tdTomato⁺
versus tdTomato⁻ cells) and Extended Data Fig. 9c (*P* = 0.8284). So the extra
left-ventricular muscle (§2.7) is not accounted for by bigger cells. The authors
make this explicit, and attribute preserved cell size to Myc coordinating
biomass accumulation alongside the cycle (Discussion).

### 2.5 The pair-tracking method

This is the paper's direct evidence for division, and it deserves its own
description because its logic is indirect.

**The method.** **CycleTrack** (cited as ref. 32) is a genetic strategy that
**permanently labels cardiomyocytes passing through G2/M**. tdTomato reporter
mice received systemic `AAV9-CyB-Cre` at 4–6 weeks of age — Cre under a cyclin B
element, so recombination marks a cell that reached G2/M — with `AAV9-CMV-Cre` as
the efficiency control. Mice were infarcted and injected with 100 µg M-C or GFP
modRNA, and hearts were taken **15 days** later (Fig. 6l,m).

**The readouts.**
- **RFP⁺ cardiomyocyte percentage:** higher after M-C (n = 4) than GFP (n = 7),
  **one-tailed Mann–Whitney *P* = 0.0545** (Fig. 6n). On a two-tailed test, or at
  *P* ≤ 0.05, this does **not** reach the paper's own threshold.
- **Singles versus doubles:** the fraction of RFP⁺ cardiomyocytes lying adjacent
  to **at least one other RFP⁺ cardiomyocyte** was **41.5% after M-C versus 5.5%
  after GFP**; mixed-effects analysis, *P* = 0.0077 for both the single and the
  double comparison (Fig. 6o). The authors call adjacency "a proxy for cell
  division".

**What it does and does not show.** The inference is that two neighbouring cells
that both passed G2/M are most simply explained as one cell's two daughters, and
the near-eightfold difference against the GFP control is a large effect on a
measure that does not depend on marker intensity. But it is explicitly a
**proxy**: adjacency is not lineage. **S** Two independent neighbouring cells
entering the cycle in a border zone with a shared local stimulus would produce
the same signal, and the paper's own §2.3 result — that the border zone supplies
extra mitogenic cues — is exactly the circumstance in which correlated,
non-clonal neighbour labelling is most likely. The honest reading is: strong,
consistent with division, and not a clonal demonstration. Note also that the
**stronger-looking result rests on the weaker overall labelling result**
(*P* = 0.0545), with n = 4 against n = 7 animals.

### 2.6 Left-ventricular function

Four separate cohorts, all echocardiographic, all blinded.

| Arm | Design | ΔEF% (change from pre-MI) | Key statistics |
| --- | --- | --- | --- |
| **Whole-heart genetic** (Fig. 1a cohort) | AAV9-Ccnt1, MI, tamoxifen d1–d2 | **none** | **No post-MI echo was possible** — 7/8 died (§2.8) |
| **Localised genetic**, early (Fig. 4c–e) | AAV9-Ccnt1 + MI + 100 µg Cre modRNA; tamoxifen d1, d2; echo d0, 3, 14, 28 | control **−23 ± 3%**, MC **−9 ± 3%** | ΔEF *P* = 0.0075 (two-tailed, n = 8 control, 14 MC). EF at 14 d *P* = 0.0193, 28 d *P* = 0.0016. Mixed-effects with Tukey: **controls fell** (d3→14 *P* = 0.0023, d3→28 *P* = 0.0007) while **MC did not** (both NS). n = 13 control, 15 MC, with 5 surgical deaths leaving baseline only |
| **modRNA**, 28 days (Fig. 6c,d) | CD1, MI + 100 µg M-C or FLuc; echo d0, 3, 6, 28 | FLuc **−37 ± 3%**, M-C **−26 ± 3%** | EF at 28 d *P* = 0.0301 (two-tailed t-test); ΔEF *P* = 0.0339 (two-tailed Mann–Whitney); n = 9 FLuc, 12 M-C |
| **modRNA**, 12 weeks (Fig. 7b,c) | CD1, MI + M-C or FLuc; echo d4, 4 wk, 12 wk | FLuc **−16.1 ± 6.1%**, M-C **−7.1 ± 6.7%** (day 4 → week 12) | **EF: two-way ANOVA with Tukey, 4 wk *P* = 0.0244, 12 wk *P* = 0.0038**; ΔEF *P* = 0.0006 (**one-tailed** unpaired t-test); n = 15 M-C, 12 FLuc |
| **Localised genetic**, delayed (Fig. 7f,i,j) | Tamoxifen on **d7 and d8**; echo d0, 3, 10, 22, 36 | control **−30 ± 12%**, MC **−14 ± 9%** | EF d22 *P* = 0.0221, d36 *P* = 0.0265 (**one-tailed**); ΔEF *P* = 0.0026 (**one-tailed**). Mixed-effects: MC improved d3→10 (*P* = 0.0349), control NS. n = 6 control, 11 MC after exclusions |

Supporting haemodynamics move the same way. Cardiac output and stroke volume
improved in the localised genetic arm (mixed-effects CO *P* = 0.0014, SV
*P* = 0.0017; at 28 d CO *P* = 0.0110, SV *P* = 0.0042) while %FS, ESV and EDV
were NS (Extended Data Fig. 5e); in the modRNA arm CO *P* = 0.0148, SV
*P* = 0.0110, %FS *P* = 0.0233 at 28 d (Extended Data Fig. 9a); at 12 weeks SV at
4 wk *P* = 0.0152 and posterior wall thickness *P* = 0.0016 (diastolic) and
*P* = 0.0057 (systolic) (Extended Data Fig. 9e). Relative heart weight (HW/TL)
rose at 28 days (*P* = 0.048, Extended Data Fig. 9b).

**What this does and does not show.** Four independent cohorts, blinded, with
consistent direction and an effect that survives to 12 weeks: this is a solid
functional claim. Two cautions. The genetic arms' effect (ΔEF −9% versus −23%) is
**larger** than the modRNA arm's (−26% versus −37%), and the authors say so and
attribute the gap to Myc's duration and to cardiomyocyte specificity
(Discussion). And the **delayed arm and the 12-week ΔEF rest on one-tailed
tests** (§4). The **mechanism** of the functional benefit is argued, not
measured: no measurement distinguishes new contractile tissue from altered
remodelling of existing tissue.

### 2.7 Scar

| Arm | Timing | Scar | Muscle |
| --- | --- | --- | --- |
| **Localised genetic**, early | 28 d | **Reduced**, *P* = 0.0217 (**one-tailed**), n = 8 control, 14 MC (Fig. 4f) | Increased, *P* = 0.0144 (one-tailed) |
| **modRNA** | 28 d | **No change**, *P* = 0.6016 (two-tailed Mann–Whitney), n = 9 FLuc, 12 M-C (Fig. 6f) | **Increased**, *P* = 0.0491 (Fig. 6g) |
| **Localised genetic**, delayed (tamoxifen d7–8) | 36 d | **No change**, *P* = 0.3237 (one-tailed), n = 8 MC, 4 control (Fig. 7k) | Increased, *P* = 0.0032 |

The Discussion puts numbers on the two genetic arms: early activation gave "a 14%
increase in ΔEF, a **6.5% reduction in the scar** and 16% increase in LV muscle";
delayed activation gave "a 16% increase in ΔEF%, **no reduction in the scar** and
17% increase in LV muscle". The authors' own interpretation: "once the scar is
formed, transient expression of pro-proliferative factors may not be able to
influence the area of the scar."

Scar also tracks function across the whole early cohort: **Spearman rank
correlation between scar% and EF%**, two-tailed *P* = 0.0080, slope
*Y* = −0.8048·*X* + 60.10 (Fig. 4g).

**What this shows.** Increased left-ventricular muscle area is the one
*structural* readout that is positive in **all three** arms, and it is not
explained by cell size (§2.4). Scar reduction happens only when the intervention
arrives early and acts through the genetic model. **S** So "muscle gained" and
"scar prevented" are separable in this dataset, and only the first is robust.

### 2.8 The lethality of global activation, and what killed the mice

The paper's most striking result, and the most relevant to Cells.

**The experiment.** Adult `Myh6-Cre;CMER` (n = 8) and Cre-negative CMER (n = 8),
AAV9-Ccnt1 at 4 weeks, MI at 8 weeks, tamoxifen on days 1 and 2 after MI.

**The outcome.** At **3 to 7 days after MycER^T2 activation, 88% (7 of 8)**
Cre-positive mice were "culled moribund or found dead", and **0 of 8**
Cre-negative controls were culled for deteriorating clinical signs. **Log-rank
(Mantel–Cox) *P* = 0.0008** (Extended Data Fig. 5a). No post-MI echocardiography
was possible.

**The crucial contrast:** the *same* genotype and treatment **without MI**
survived and was healthy for 28 days in the 2020 paper (100% survival of
Cre;CMER + AAV cyclin T1 + tamoxifen mice). So neither Myc + cyclin T1 alone nor
MI alone was lethal; the combination was.

**What was found at autopsy.** **No cardiac rupture.** High numbers of
proliferative cardiomyocytes in the border zone (Ki67, one-tailed t-test
*P* = 0.0059; Myc + cyclin T1 n = 6, control n = 7) and **increased left
ventricular muscle area** (one-tailed *P* = 0.0086) (Extended Data Fig. 5b,c).

**What the authors propose killed them** — and the wording is carefully
hypothetical:
1. "Uncontrolled proliferation across the heart led to an increase in left
   ventricular muscle, **which could cause** hypertrophic cardiomyopathy and lead
   to death";
2. "**However, sudden cardiac death may be due to** the increased levels of
   proliferating cardiomyocytes, which must undergo **dedifferentiation and
   sarcomere disassembly before cytokinesis**. **Any interruption of beating is
   likely to disrupt cardiac output or be an arrhythmogenic risk**";
3. supporting this, their transcriptional datasets "indicated **reductions in the
   sodium channel `Scn5a` and gap junction `Gja1` (encoding connexin 43)**, both
   of which have been genetically and functionally validated to cause arrhythmia
   in humans and mice" — citing Supplementary Tables 1 and 2, **which were not
   read here** (§1).

The section closes with the paper's own general lesson: "the magnitude and
location of proliferation initiated within a regenerating heart is likely to be a
key factor in determining the most efficacious regenerative therapy while
minimizing its side effects."

**What this does and does not show.** It shows, with a clean genetic control and
a strong *P* value, that **unrestricted** activation plus injury is lethal within
a week, and that the deaths were not from rupture. It does **not** establish the
cause of death. There was **no electrocardiography, no telemetry, no
post-mortem conduction study and no histology of the conduction system** (§2.11).
Hypertrophy and arrhythmia are offered as alternatives, not distinguished, and
the arrhythmia limb rests on two transcript-level observations in a
supplementary table. **S** This is precisely a question a bioelectric tissue
model can address and an echocardiogram cannot, and it is the reason this paper
is worth modelling at all (§6e).

### 2.9 Tumour follow-up

Two separate observations, in two different arms.

- **Localised genetic, 28 days:** "No tumors were observed in any organs at 28
  days following MI, cardiac Cre modRNA administration and transient MycER^T2
  activation" (Fig. 4 text). Rare tdTomato⁺ Cre-recombined cells were present in
  spleen and liver in numbers similar to controls (Extended Data Fig. 5f,
  two-way ANOVA NS).
- **modRNA, 12 weeks:** histology of **heart, liver, brain, pancreas, thymus,
  spleen, lung and kidneys** by haematoxylin and eosin **and Ki67** "indicated an
  absence of tumorgenicity" (Fig. 7 text). Mouse weight and organ weights did not
  differ (Extended Data Fig. 9f,g).
- **In vitro transformation (Fig. 7d,e):** NIH3T3 focus formation. Retroviral
  HRas^G12D transformed; Ras **plus retroviral Myc** increased foci
  (RV-Neg versus RV-Ras/Myc *P* < 0.0001; RV-Ras versus RV-Ras/Myc *P* = 0.0383);
  **Ras plus M-C modRNA did not** (RV-Ras/Myc versus M-C modRNA *P* = 0.0048;
  versus GFP modRNA *P* = 0.0074), n = 3 — despite M-C modRNA's *higher*
  transfection efficiency (Extended Data Fig. 9h, *P* = 0.0181). The authors
  conclude the transient insult "cannot cooperate with oncogenic HRas^G12D to
  transform cells".

**What this does and does not show.** Three independent lines of negative
evidence, including the right positive control, over a window of 12 weeks. The
authors state the limit themselves: FDA-standard carcinogenicity models such as
the **Tg-Ras (RasH2) mouse** "will be valuable to definitively rule out any
latent oncogenic risks" (Discussion). **S** Twelve weeks in a mouse is a short
latency window for a Myc-driven tumour, and the readout is histological, not a
lifespan study — so "no tumours observed in 12 weeks" is correct and is not
"non-oncogenic".

### 2.10 Specificity of the mRNA's expression

This is the clearest acknowledged weakness, and the authors report it against
their own interest.

- **Cell-type specificity: poor.** snRNA-seq of hearts 24 h after MI and M-C or
  GFP injection (n = 3 each; 10 cell clusters) found that **8% of upregulated
  differentially expressed genes overlapped in cardiomyocytes, fibroblasts,
  endothelial cells and monocytes, "indicating a lack of cell specificity of the
  modRNA"** (Extended Data Fig. 8g). In cardiomyocytes the changes — `Igf1r`,
  `Yap1`, `Cdc42`, G2M — significantly overlapped those seen with MycER^T2
  (Extended Data Fig. 8d–f).
- Consistent with this, M-C modRNA drove **BrdU incorporation in mouse embryo
  fibroblasts** in vitro (eGFP versus mouse M-C *P* < 0.0001, Extended Data
  Fig. 6b), and raised **Ki67 in non-cardiomyocytes** in P7 cultures
  (*P* = 0.0229, Fig. 5m).
- **Spatial specificity: good.** Cre modRNA recombined **~9% of the left
  ventricle** (Fig. 4a), with tdTomato over the cohorts at ~10% of cardiac tissue
  and no difference between arms (*P* = 0.6020, Fig. 4i).
- **Extracardiac leak: small but real.** Recombination was "extremely rare" in
  kidney, thymus and lung, and present in **0.14% of liver and 0.27% of spleen**
  cells (Extended Data Fig. 5d; two-way ANOVA with Šídák, spleen *P* = 0.0002,
  n = 5 versus 5).
- **Echo-guided delivery failed.** It "did not allow for efficient and robust
  cardiac delivery of mRNA" (Extended Data Fig. 10a), which is why the delayed
  arm had to use the genetic model rather than a second modRNA injection.
- In the genetic arms, by contrast, expression **is** cardiomyocyte-restricted
  by construction (Myh6-Cre; cTnT-driven AAV), and MycER^T2 and cyclin T1 were
  "exclusively expressed in cardiomyocytes" in the snRNA-seq (Fig. 2 text).

Deposits: ENA `PRJEB52314`; GEO `GSE248286` and `GSE297340`; ProteomeXchange
`PXD043114`. None was downloaded (§1).

### 2.11 Electrophysiology and arrhythmia: what is and is not there

**There is no electrophysiological measurement in this paper.** Searched the full
text for electrocardiography, telemetry, ECG, optical mapping, patch clamp,
action potential, calcium transient and conduction. The results:

- **Electrocardiography pads were used only to monitor heart and respiration rate
  during anaesthesia** for echocardiography (Methods, *Echocardiography*). No ECG
  trace, interval, rhythm or arrhythmia incidence is reported anywhere.
- **No telemetry, no optical mapping, no patch clamp, no calcium imaging, no
  conduction measurement and no conduction-system histology.**
- The arrhythmia discussion is entirely **transcriptional and inferential**:
  reduced `Scn5a` and `Gja1` (§2.8), and `Xirp2` among the CM2 markers
  "involved in cardiac conduction" (Fig. 3b). The cited supporting references are
  human and mouse genetic arrhythmia literature, not measurements in these mice.
- The authors are explicit that this is unfinished: "Another key concern raised by
  our continuous, systemic genetic model was the **downregulation of crucial
  electrophysiological genes**", mitigated in their view only because modRNA
  expression is transient and localised so "the window for potential
  electrophysiological disruption … is exceedingly narrow"; and **"Formal
  electrophysiological and mapping studies must be conducted in large animal
  models, such as pigs"** (Discussion). The conclusion lists "the arrhythmic
  safety profile" first among what further preclinical models must establish.
- The precedent they cite makes the stake clear: sustained AAV6 microRNA-199a in
  pigs "initially triggered cardiac repair … but eventually resulted in **lethal
  arrhythmias** and the formation of abnormal, hyper-proliferative cell clusters"
  (Discussion, ref. 35), whereas AAV9 `Sav` knockdown gave structural benefit
  with no lethality at 3 months (ref. 37).

**S This absence is the single largest opening for Cells.** The paper's own
proposed mechanism of death, its principal safety concern, and the failure mode
of the nearest competing therapy are all bioelectric, and none of them is
measured — in a study that otherwise measures a great deal.

## 3. The mechanism, as the two papers state it

**Myc needs a partner the adult heart does not have.** Myc is a bHLH–LZ
transcription factor that binds E-boxes as a heterodimer with **Max** and
controls cell-cycle progression, ribosome biogenesis and metabolism; its output
is context-dependent because Myc–Max binds **only open chromatin** (2026 Main,
refs 2–7).

**The limiting factor is P-TEFb, and within it cyclin T1.** The 2020 paper's
central finding is that Myc is **bound to DNA at open elements in both responsive
(liver) and non-responsive (heart) tissue** yet "fails to induce a robust
transcriptional and proliferative response in the heart" (2020 Abstract) — so the
block is **after** binding. **P-TEFb is CDK9 plus cyclin T1** (encoded by
`Ccnt1`); it phosphorylates **DSIF, NELF and serine 2 of the RNA Pol II
C-terminal domain**, releasing paused polymerase into **productive elongation**
(2020 Introduction). P-TEFb is itself held in an inactive complex with **7SK
snRNA, Larp7, MEPCE and HEXIM** (2020 Introduction). **Cyclin T1 is the factor
that controls P-TEFb levels in cardiomyocytes** (2026 Main, refs 5, 18, 19).

**Why adult cardiomyocytes lack the response.** "CDK9, Cyclin T1 and RNA PolII
all progressively **decrease during post-natal cardiac maturation**", so 15-day
juvenile hearts carry P-TEFb and Pol II at adult-liver levels while adult hearts
do not (2020, Fig. 6a and text). Consequently the juvenile heart is permissive —
acute Myc activation induced a panel of common Myc targets and 1,601 up- and
1,133 down-regulated genes, then mitosis and a **1.8-fold rise in cardiomyocyte
number without a change in cell size** (2020, Figs. 6, 7). In the adult, **AAV
`Ccnt1` restores permissiveness**: cyclin T1 in ~34% of cardiomyocytes raised
CDK9 and phospho-Pol II (S2), restored Myc target transcription, and a single
tamoxifen pulse produced mitosis, cytokinesis markers and increased cardiomyocyte
number at 72 h with no change in size or nucleation (2020, Figs. 8, 9) —
compatible with long-term survival and no histological abnormality at 28 days.
Pharmacological confirmation ran the other way: the CDK9 inhibitor **AZ5576**
blocked Myc-driven target transcription in liver (2020, Fig. 5b,c).

**Named programs and targets.**
- *Direct Myc-response transcripts used as readouts*: `Smpdl3b`, `Gnl3`,
  `Polr3g` (2026, Fig. 5d); `Cad`, `Bzw2`, `Pinx1`, `Polr3d`, `St6`, `Cdc25a`
  (2020, Figs. 5e, 6b, 8c).
- *Hallmark gene sets up*: **Myc targets, G2M checkpoint, E2F targets**;
  **down: myogenesis** (2026, Fig. 2f,g).
- *Metabolic and growth programs*: **mTORC1 signalling, glycolysis, oxidative
  phosphorylation** (2026, Fig. 3f) — the authors' explanation for why Myc both
  triggers the cycle and supplies "the capability for the demands of growth",
  preserving cell size (Discussion).
- *Cycle and cytokinesis genes marking the proliferative state*: S phase `Top2a`,
  `Mki67`; G2M `Cdk1`, `Ccnb2`; cytokinesis `Anln`, `Cenpa` (2026, Fig. 3c,d).
- *The cell-state trajectory*: four cardiomyocyte subclusters, with
  **Monocle 3 pseudotime running CM1 → CM2 → CM3** — mature ventricular
  (`Ryr2`, `Ttn`, `Fhl2`, `Myh6`) → a stress/conduction/ribosome-biogenesis state
  (`Nppb`, `Xirp2`, `Creb5`, `Grk5`) → a cycling state (`Top2a`, `Cenpp`,
  `Mki67`) (2026, Fig. 3a,b,e). CM3 reached **28.7%** of cardiomyocytes in
  Myc-expressing adult MI samples and **27.5%** in juveniles, against a figure
  printed as ">0.3%" and ">0.2%" in controls — **S** almost certainly meant as
  "<", but this review does not assume it. CM4 is an oxidative-metabolism state
  (`Cox5b`, `Cox6c`, `Ndufa1`, `Fabp3`) present in all cohorts.
- *The niche*: CellChat and NicheNet give a **pro-regenerative cross-talk**
  picture — **VEGF-A** from cardiomyocytes to endothelium, **IGF-1** from
  monocytes to cardiomyocytes, angiopoietin from monocytes and lymphocytes,
  **neuregulin** from adipocytes and epicardium, endocardial BMP, and `Ptprm` to
  endothelium; with `Nrg2`/`Nrg4` ligands and `Erbb4`/`Egfr` receptors up (2026,
  Fig. 3g; Extended Data Fig. 4b,c). This is the authors' candidate explanation
  for the border-zone excess in §2.3.

**The therapeutic logic that follows.** Regenerative species show "a transient
increase in short-lived Myc protein followed by a rapid burst of proliferation"
after damage (2026 Main, ref. 14), so the design goal is to **phenocopy that
pulse**: "careful titration of the treatment dose, timing, location and duration
… to elicit a 'physiologically normal' pulse of Myc expression". modRNA is chosen
because it is transient by construction, non-integrating and minimally
immunogenic, and because the platform is clinically established (the VEGF-A
modRNA AZD8601 phase 2 trial, NCT03370887, met its safety endpoint).

**S The mechanism, reduced to its modelling skeleton:** a *pulsed* activator and
a *separately supplied, chronic* elongation-competence factor must be **present in
the same cell at the same time** for the cell to enter the cycle; competence is a
slowly varying property set by developmental stage; and the local injury
environment supplies a third, spatially graded input. Three multiplicative
requirements, one of them spatial — which is a tractable shape for a model.

## 4. The authors' claims separated from what the data show

| The claim | Status | What the data support |
| --- | --- | --- |
| Myc + cyclin T1 drives adult cardiomyocyte cycle entry, mitosis and cytokinesis markers | **Supported** | Ki67 25.1%, P-H3 6.9%, Aurora B 4.4% with symmetrical mid-bodies, against 0.2/0.5/1.4% controls, n = 7 versus 5 + 3 (§2.3) |
| The response is **greater in the border zone** | **Supported** | BZ versus RZ *P* = 0.0021 (P-H3) and *P* < 0.0001 (Ki67); RZ matches the undamaged heart (§2.3) |
| **Sustained global expression is detrimental**; restriction prevents it | **Supported for the outcome** | 7/8 dead versus 0/8, log-rank *P* = 0.0008, with no lethality in the localised arm and no lethality of the same genotype without MI (§2.8) |
| …because of hypertrophic cardiomyopathy **or** an arrhythmogenic interruption of beating | **The authors' hypothesis, not shown** | No rupture, increased LV muscle and many cycling cardiomyocytes are all that was measured. **No electrical measurement of any kind** (§2.11). `Scn5a`/`Gja1` reduction is transcript-level, in a supplementary table not read here |
| modRNA gives **transient** Myc and cyclin T1 expression | **Supported, with a caveat** | Protein at 1 h and 4 h, absent at 24 h, n = 3; in vitro depleted by 48 h; MG132 extends it. **The platform is not transient** — GFP persisted ≥48 h and FLuc fell only 5.5-fold from 8 h to 48 h (§2.2) |
| M-C modRNA **improves cardiac function** after MI | **Supported** | Four cohorts, blinded; 28 d *P* = 0.0301, 12 wk *P* = 0.0038; consistent CO/SV (§2.6) |
| …and this is **regeneration, not cardioprotection** | **Well argued, partly shown** | The cardioprotection arm is a genuine negative: no change in cleaved caspase-3 or TUNEL at 4 h (Extended Data Fig. 9d) or at 48 h in the genetic arm (Fig. 1d). Positive evidence is cycle markers, +cardiomyocyte number at d5, CycleTrack doubles and +LV muscle. **No measurement shows the new cells contract or couple** |
| M-C modRNA drives **"proficient cell division and cardiac regeneration"** (Fig. 6 text) | **Overstated for "proficient"** | The division evidence is an adjacency proxy (41.5% versus 5.5%) resting on an overall labelling difference at *P* = 0.0545, n = 4 versus 7 (§2.5); plus a haemocytometer count at *P* = 0.0176 (§2.4). No clonal lineage tracing |
| Scar is reduced | **Only in one arm** | Reduced in the early localised genetic arm (*P* = 0.0217, one-tailed); **unchanged** in the modRNA arm (*P* = 0.6016) and in the delayed arm (*P* = 0.3237). The authors state this honestly (§2.7) |
| Increased LV muscle is new muscle, not hypertrophy | **Supported** | Cross-sectional area unchanged in both arms (NS; *P* = 0.8284) (§2.4) |
| **Long-term survival is improved** — "marginally improved", "a positive trend" | **Not shown** | Log-rank *P* = 0.2008, n = 20 versus 19, after excluding 3 deaths within 3 days. **S** A non-significant result described as a trend; the direction is favourable, the claim is not supported at the paper's own threshold (§2.9, §5) |
| Transient M-C is **not oncogenic** | **Supported within 12 weeks** | No tumours at 28 d and at 12 wk across eight organs; no Ras cooperation in NIH3T3 with the correct positive control. The authors themselves call for a RasH2 study (§2.9) |
| The therapy is **cardiomyocyte-specific** | **Not claimed, and contradicted for modRNA** | The authors report the lack of specificity themselves: 8% DEG overlap across four cell types, fibroblast BrdU, non-myocyte Ki67 (§2.10). Specificity holds only in the genetic arms |
| Delayed (day 7–8) treatment works | **Supported, on one-tailed tests** | ΔEF *P* = 0.0026, EF d22 *P* = 0.0221, d36 *P* = 0.0265, all one-tailed; n = 6 versus 11 after exclusions; Ki67 confined to recombined cells is a strong internal control (§2.3, §2.6) |

**Methodological notes, as a reviewer.**
- **One-tailed tests appear on several primary endpoints**: scar and muscle in
  Fig. 4f, ΔEF at 12 weeks (Fig. 7c), EF at days 22 and 36 and ΔEF in the delayed
  arm (Fig. 7i,j), scar and muscle at day 36 (Fig. 7k), Ki67 and LV muscle in
  Extended Data Fig. 5b,c, and stroke volume in Extended Data Fig. 10b. The
  statistics section states only that *P* ≤ 0.05 was significant; **no
  justification for one-tailed testing, no power calculation, no pre-registration
  and no multiplicity correction is given**, and many echo-derived measures are
  tested per cohort. Blinding is stated for surgery, echo, histological area
  measurement and cell counting, which is the right protection and a real
  strength.
- **Small n with exclusions** in the delayed arm: n = 6 control and 11 MC after
  excluding failed MIs (<10% EF fall at day 3) and failed Cre injections (no
  tdTomato at 36 days). The criteria are pre-stated and sensible, but the control
  group for scar and muscle is **n = 4**.
- **Internal discrepancies** worth noting rather than resolving: the text says
  "13 transcriptionally distinct cell clusters" while the Fig. 2c legend says
  "14 major cell types"; Fig. 6k prints "*P* = 0. 0.0176"; Fig. 7b's legend
  reports s.d. where most panels report s.e.m.; and the CM3 control fractions are
  printed as ">0.3%" and ">0.2%" where "<" is evidently meant (§3). **S** None
  changes an interpretation.
- **Biological caveats the paper cannot settle:** polyploidy and multinucleation
  are not measured in the 2026 paper; the dissociation-and-haemocytometer count
  is yield-sensitive (§2.4); lipofectamine delivery is not translatable, as the
  authors say; and permanent LAD ligation without reperfusion is a severe model
  that does not match reperfused human MI.

## 5. The pasted summary, claim by claim

The user supplied a third-party summary and asked for each claim to be checked.
All seven are **substantially right** — unusually good for a secondary source —
but four need a correction or a qualification, and one is right only in the arm
it came from.

| The summary's claim | Verdict | Correction or qualification |
| --- | --- | --- |
| **Expression gone by 24 h** | **Right, imprecise in two ways** | Correct for **Myc and cyclin T1 protein in heart tissue**: present at 1 h and 4 h, not observed at 24 h (Fig. 6b; Extended Data Fig. 7a). (a) It is the **absence of staining at one time point with n = 3**, not a decay curve; no Myc time point lies between 4 h and 24 h. (b) **The modRNA platform is not gone at 24 h** — GFP protein from the same delivery persisted **≥48 h**, and FLuc bioluminescence fell only **5.5-fold from 8 h to 48 h**. The short window is Myc's *protein* turnover (MG132 extends it; cited half-life 20–40 min), not mRNA clearance. **S** For a model this distinction is the whole point: the input lasts a day or more, the active protein does not |
| **41.5% vs 5.5% of labelled cardiomyocytes in adjacent pairs** | **Right** | Exact (Fig. 6o), mixed-effects *P* = 0.0077. Add the context: **CycleTrack** G2/M labelling via `AAV9-CyB-Cre`, hearts at **day 15**, **n = 4 M-C versus 7 GFP animals**, and the authors call adjacency "a proxy for cell division", not lineage. The **companion** measure — overall RFP⁺ percentage — was only **one-tailed *P* = 0.0545**, i.e. not significant at the paper's own threshold, so the pair fraction carries the claim (§2.5) |
| **LVEF change at 12 weeks, *P* = 0.0038** | **Number right, attribution wrong** | *P* = 0.0038 is the **EF% comparison at 12 weeks** (two-way ANOVA with Tukey; M-C n = 15, FLuc n = 12), not the *change* in EF. The **ΔEF%** (day 4 → week 12) is **−7.1 ± 6.7% versus −16.1 ± 6.1%, *P* = 0.0006 by a one-tailed unpaired t-test** (Fig. 7b,c) |
| **No significant scar reduction at 28 days** | **Right for the modRNA arm; wrong if generalised** | Correct for M-C modRNA: *P* = 0.6016 (Fig. 6f). But in the **early localised genetic arm scar *was* reduced at 28 days**, *P* = 0.0217 one-tailed, quantified in the Discussion as a **6.5% reduction** (Fig. 4f). The delayed genetic arm again showed none at day 36 (*P* = 0.3237). **LV muscle area increased in all three arms** (§2.7) |
| **7 of 8 mice dying with widespread genetic activation** | **Right** | 88% (7/8) culled moribund or found dead **3–7 days after MycER^T2 activation**, versus **0/8** Cre-negative; **log-rank *P* = 0.0008** (Extended Data Fig. 5a). Two things the summary omits and that matter: this was **with MI** — the same genotype and treatment **without** MI survived 28 days healthy in the 2020 study — and **no cardiac rupture** was found, so the cause of death is the authors' open hypothesis (§2.8) |
| **No tumours by 12 weeks** | **Right** | Two observations: no tumours in any organ at **28 days** (localised genetic arm) and absence of tumorigenicity by H&E **and Ki67** across **eight organs at 12 weeks** (modRNA arm), plus a negative NIH3T3 transformation assay with the right positive control. The authors add that an **FDA-standard RasH2 carcinogenicity model** is still needed (§2.9) |
| **Survival not significant** | **Right, and the paper's own wording is looser than its statistic** | **Log-rank *P* = 0.2008** over 12 weeks (M-C n = 20, FLuc n = 19), after excluding 3 deaths within 3 days of MI (2 FLuc, 1 M-C). The paper calls this "marginally improved" (Fig. 7 text) and "a positive trend toward improved long-term survival" (Discussion) — **S** stronger language than *P* = 0.2008 supports, and it is used in the Discussion to reassure about the electrophysiological concern (§2.11) |

**Nothing in the summary was fabricated**, and no number in it was wrong. The
corrections are about *which arm* and *which statistic*.

## 6. A modelling plan for Cells

"Soon" is the user's priority, so this section is ordered by what could start
rather than by what would be most complete. The governing rules are
[D136](DECISIONS.md#d136-experiments-drive-biologically-valid-engine-features)
(an experiment may reveal a missing mechanism; the engine gains a general model),
[D144](DECISIONS.md#d144-qualify-the-simulator-for-many-uses-not-one-experiment)
(never a feature built for one paper),
[D142](DECISIONS.md#d142-architect-new-features-cleanly) (design first) and
[D138](DECISIONS.md#d138-mg1-start-and-the-paper-backlog) (reproducing a paper's
own model or code is tooling needing the user's approval per paper).
Every stage below names the engine models it runs, as AGENTS.md's milestone rule
requires.

### 6a. What exists today that a model would use

| Piece the paper needs | What exists in `src/cells` | Status |
| --- | --- | --- |
| **A transient expression pulse** — scheduled production and first-order clearance of a species | `scheduled_species_turnover@1` (production at cells, clearance at nodes) and `scheduled_species_exchange@1` (secretion and uptake), both **landed 14 November 2026** under D150 v1, with their guards; crossrev identical in all five sets and no changed tier-1/tier-2 outcome | **Landed, not accepted.** Milestone 3 — comparison with the continuum closed forms, then the PROPOSED protocol — is still to come, and CURRENT_PLAN states plainly "integration grants no acceptance" |
| **Complex formation** — cyclin T1 + CDK9 ⇌ P-TEFb as reversible binding | `local_species_reactions@1`, one reaction network per composition, writing @3's neutral species rows, reusing the neutral detailed-balance kernel `mass_action.reversible_flux` unchanged | **Design accepted 14 November 2026** ([note](SHARED_INVENTORY_REACTIONS_DESIGN.md), rulings in §9). **Code has not landed**; it follows D150 v1's code, ~6 agent-days. First acceptance is **MG0c** (Turing patterning at the predicted wavelength), not this paper |
| **Division** | `isopotential_partition@1` and `cytoplasmic_bridge_closure@1`, with `scheduled_membrane_insertion@1/@2`, `restricted_cleft_lumen@2` and `membrane_entity_state@1` | **S5a qualified** (CURRENT_PLAN, 14 November): it passed its registered protocol against the independent references R-ops and R-tissue. Division is **prescribed**, not state-triggered |
| **Newborn cells' junction formation** | `delayed_first_order_junction_formation@1` (`processes/junction_formation.py`), E07's engine model for how a newcomer acquires coupling | In use in E07; the formation **shape is a modelling choice, not a fit** (CURRENT_PLAN, coupled-renewal robustness row) |
| **Cell replacement** | `scheduled_cell_replacement@1/@2`, and `resolved_pump_replacement@1` as the composite with replacement over `resolved_pump_tissue@3` | In use in E07-v1 |
| **The composite physiology** | `resolved_pump_composite@1`, with water and volume (`resolved_pump_water@1/@2`, `ideal_osmosis_linear_compliance_water@1`) | Water and volume **qualified and on main** (11 November); the composite's landing is the current gate |
| **Gap junctions and coupling** | `junction_voltage_relaxation@1`, `symmetric_opposing_relaxation@1`, junction gating (`junction_gate.py`), plus formation above | Qualified in the BETSE-parity track; junction abundance is **entity state**, so it can be set per contact. **Worth noting for this paper:** the opposing-gate law's steady voltage dependence is already sourced from a **cardiac** gap-junction measurement — Chen-Izu, Moreno & Spangler (2001), cited in [SELECTIVE_CONTACT_SPEC.md](SELECTIVE_CONTACT_SPEC.md) §"opposing-gate literature" — though the relaxation time is declared there as "our phenomenological model, not a reproduction of the full microscopic gating scheme" |
| **Voltage-gated channel laws** | A broad catalogue: `voltage_gates.py`, `sodium_channels`, `kv1_channels`, `cav_channels`, `hcn_channels` (`hcn1_m@1`, `hcn2_m@1`, `hcn4_m@1`), `potassium_channels`, `leak_channels`, `kinetic_pump`, `cotransport`, calcium handling (`er_calcium.py`, `calcium_atpase.py`, `ip3_release.py`, `plasma_calcium.py`), and a **Morris–Lecar family** (`morris_lecar_channels.py`) that includes `nav_ml_instantaneous@1`, `cav_l_ml_instantaneous@1`, `cav_t_ml_instantaneous@1`, `kir_ml_instantaneous@1`, `hcn2_ml_…@1` and `hcn4_ml_…@1` | **The ingredients of excitability exist as generic laws under neutral names.** See the next row for what does not |
| **An intracellular calcium store** | `er_calcium.py`: a BETSE-1.5-sourced ER pump (`SERCA`-like but, per its own header, "deliberately does not imply a two-Ca SERCA cycle") and an **instantaneous, activation- and inhibition-gated release law** `er_calcium_release@1`; plus `finite_calcium_pumps.py`, `calcium_atpase.py`, `ip3_release.py`, `plasma_calcium.py`, `calcium_gates.py`, `calcium_activated_potassium.py` | Present under neutral names. **S** The shape of a store-release feedback exists; cardiac **RyR2** kinetics and release-to-contraction coupling do not |
| **A cardiac action potential** | **Nothing.** Grepping `src/` for `Luo–Rudy`, `ten Tusscher`, `O'Hara`, `Beeler`, `Nav1.5`, `Scn5a`, "action potential", `ryanodine` and "excitation–contraction" returns **no match for any of them**. No ventricular or nodal action-potential model, no `Scn5a`-calibrated fast sodium current with the right inactivation, no `Ito`/`IKr`/`IKs`, no excitation–contraction coupling, and no conduction observables (activation time, conduction velocity, refractoriness, capture, block) | **Absent.** The closest are the Morris–Lecar family above — a generic excitable-membrane formulation carrying `nav_ml_instantaneous@1`, L- and T-type calcium, `kir_ml_instantaneous@1` and HCN2/HCN4 — and the BETSE-sourced HCN laws, whose own header notes they "do not implement cAMP modulation or a native update clock" |
| **Mechanics** | 2-D vertex mechanics (`vertex_mechanics.py`, `apical_vertex.py`, `mechanical_equilibrium.py`, `junction_tension_inference.py`). It **does** carry a perimeter-**contractility** parameter Γ_c ≥ 0 in the energy (`0.5 · Γ_c · perimeter²`), the standard vertex-model cortical term | MG1's v2 passed and landed. **S** But that is a *passive, static* cortical tension parameter, not active force generation: there is **no time-varying contraction, no calcium-to-force coupling, no stroke or pump measure, and no mechanosensitive channel** (the bone-mechanosensing review reached the same conclusion) |
| **Gene regulation** | `emt_mirna.py` / `emt_mirna_pair@1` is the nearest: regulatory equations with no ions, voltage or contacts, deliberately isolated | There is **no gene-regulation layer**. The GRN track is **held under D145**, with catalogue stage 3 and Cortés-Poza Phase 1 |
| **Scar, fibroblasts, cell types** | Cells have stable identity, membership and ancestry; `tissue_removal.py` and `fixed_polygon_removal.py` remove tissue; `finite_ecm_polygon_geometry.py` is a geometric cell/ECM partition | **No ECM with composition, no fibroblast population, no differentiated cell types, no scar.** The GZMK review reached the same conclusion for fibrosis |

**S The one-sentence summary of 6a:** Cells can already express *a timed
molecular pulse in a coupled, voltage-bearing, volume-regulating cell sheet whose
cells can be made to divide and whose newborns acquire junctions on a declared
law* — which is a surprisingly good match to the paper's *spatial* question, and
no match at all to its functional readouts.

### 6b. What is missing, each as a general feature

Each is stated as a feature Cells would want anyway (D144). None is to be built
for this paper.

1. **A regulated competence or cycle-entry gate.** The paper's mechanism is
   multiplicative: a pulsed activator × a chronic competence factor × a local
   injury cue → cycle entry. Cells has no object that converts molecular state
   into a per-cell decision. As a general feature this is "a slow, writable
   per-cell state, with a declared timescale, that gates an operator" — the same
   thing the GZMK review's item 6 and the coupled-renewal gate's "causal
   carriers" row want. **It touches the gene-regulation layer, which is held
   under [D145](DECISIONS.md#d145-the-current-plan-is-adopted-with-the-l4-now-and-gh200-next-week),
   and D151 explicitly does not lift that hold.** This is decision 1 in §6d.
2. **Division triggered by state.** CURRENT_PLAN's lifecycle gate has this as
   **milestone 2, the endogenous lifecycle** — "division triggered by growth or
   regulation; daughters with conserved inventories and identities; repeated
   births and deaths" — with named open decisions on reference anchors at birth,
   slot reuse and capacity, lineage across storage changes, conservation through
   topology changes and checkpoints at events. Today division is prescribed.
3. **Cardiomyocyte electrophysiology and conduction.** A calibrated excitable
   cardiomyocyte membrane (fast sodium current with inactivation, repolarising
   potassium currents, L-type calcium), propagation through gap junctions, and
   the observables that make it a conduction study: activation time, conduction
   velocity, refractoriness, capture and block. **S** This is the largest missing
   layer and the most valuable one, because it is generic excitable-tissue
   physics that Cells' channel catalogue, junctions and field solver are already
   shaped for — and because without it none of the paper's safety question is
   reachable.
4. **The electrical integration of newborn cells.** A newborn cell's junction
   formation law exists (`delayed_first_order_junction_formation@1`), but nothing
   declares how a *newly divided, dedifferentiated* cell's membrane differs while
   it matures. As a general feature: a declared maturation trajectory for a
   newborn cell's channel abundances and junction coupling, with the timescale
   as a parameter. This is the mechanism behind the paper's own hypothesis
   (§2.8).
5. **Active contractility.** A time-varying contraction driven by calcium, and a
   tissue-level pump measure. MG1 gives **passive** 2-D vertex mechanics with a
   static cortical-contractility parameter (§6a), which is not the same thing:
   nothing generates a beat. Without this, **ejection fraction is not definable
   in Cells**.
6. **Scar, fibroblasts and matrix.** A matrix entity owning composition with
   deposition and degradation accounts, a second cell type with its own model
   set, and a coupling from matrix amount to mechanics. The GZMK review ranked
   this last for the same reasons.
7. **Multiple cell types with different model sets.** Needed for 6, and for the
   paper's niche signalling (§3). Not on any current gate.
8. **Duration.** The paper's readouts run to **12 weeks**. At 1 ms, one simulated
   hour is 3.6 million steps (CURRENT_PLAN); 12 weeks is ~7 × 10⁹ steps.
   Long-time methods are an open gate deliverable and the projective mode
   **failed** its qualification. **S** Anything past a few simulated hours is out
   of reach, which is itself a reason to target the acute, hours-scale question.

### 6c. A staged path, smallest first

**Version 0 — the spatial-restriction effect in a passive coupled sheet.**
*The smallest model that tests something real, and it could start now.*

- **The question.** The paper's own general lesson is that "the magnitude and
  location of proliferation … is likely to be a key factor" (§2.8). Version 0
  asks the engine-shaped form of it: **for the same total number of affected
  cells, does it matter whether they are clustered or scattered?** Specifically —
  when a declared fraction *f* of cells in a coupled sheet transiently lose
  junction coupling and gain altered membrane conductance, how do the sheet's
  voltage field, its coupling structure and its recovery depend on *f* and on the
  spatial arrangement at fixed *f*?
- **Engine models it runs.** `resolved_pump_composite@1` on
  `resolved_pump_tissue@3` (the qualified pump–channel tissue with its junction
  laws), with `scheduled_species_turnover@1` supplying the timed pulse that
  drives the perturbation, and the existing junction abundance as the perturbed
  state. No new engine feature. The 127-cell sheet on CPU, the scale
  CURRENT_PLAN already names for coupled renewal.
- **What it would show.** Whether spatial arrangement, at fixed dose, changes the
  tissue-level bioelectric consequence — and if so, over what clustering scale
  and with what dependence on junction coupling. That is a *general* result about
  coupled tissue, reportable on its own terms, and it is the quantitative core of
  the paper's clinical insight.
- **What it would not show.** Not proliferation, not division, not regeneration,
  not ejection fraction, not scar, and **not arrhythmia** — a passive sheet has
  no propagation, so "conduction block" is not yet definable. It also would not
  reproduce any number in the paper.
- **Prerequisites and gate.** The composite's landing (today's commitments) and
  D150 v1's milestone 3. It sits naturally as a small case in the **composition**
  gate, reusing the coupled-renewal gate's 127-cell sheet. **S** It should be
  registered with a pre-declared readout, like any other.
- **Effort.** ~2–3 agent-days for the driver, world definitions and analysis, as
  a `validation/` experiment driver over unchanged engine models, plus CPU hours
  only.
- **Decisions it needs.** Only whether to spend the slot (§6d, decision 3). It
  needs **no** new engine feature and **no** D145 relief.

> **S The honest caveat on version 0.** It is a model of the paper's *principle*,
> not of the paper. Its value is that it is real, cheap, uses qualified physics
> and produces a general result; its limit is that nobody could call it a
> replication. If the user wants a replication, the answer is that the earliest
> one is version 3 and the full one is not reachable (§6d, decision 3).

**Version 1 — the pulse and the complex, as kinetics.**
- **Adds.** The mechanism of §3 as a reaction network: a **source** reaction for
  the pulsed activator, a **first-order sink** with a 20–40 min protein half-life
  (§2.2), a **chronic** competence species, and **reversible binding** of the
  competence factor with its kinase partner to form the active complex. The
  readout is the **time integral of the active complex per cell** — a dose, not a
  decision.
- **Engine models.** `local_species_reactions@1` (once coded and MG0c-qualified),
  over @3. **A hard constraint found in the design note:** a turnover route on a
  (species, node) that a reaction writes is **refused at the definition**, so the
  pulse's production and clearance must be declared **inside** the network as
  source and sink reactions, not through `scheduled_species_turnover@1`
  ([note](SHARED_INVENTORY_REACTIONS_DESIGN.md) §1.1). Version 1 of that operator
  is also **refused beside water and the lumen**, caps species at **7**, allows
  **neutral species only**, and refuses cell routes on replaced slots (§7, §9
  there). **S** So version 1 of *this* model cannot run with water and volume, and
  cannot combine the pulse with replacement — both are version-2 problems.
- **What it would show.** That the engine reproduces the paper's own kinetic
  separation: a driver present for hours, a response integrated over days, and a
  competence factor without which the integral stays near zero. Calibrated on
  §2.2's numbers, which are generic protein kinetics.
- **Prerequisites and gate.** D152's code and **MG0c's acceptance first** — this
  model is a *second consumer*, never the qualification case. Composition gate.
- **Effort.** ~2 agent-days on top of D152, assuming MG0c has landed.
- **Decisions.** Whether a comparison with the paper's measured kinetics counts
  as a per-paper comparison under D138 (§6d, decision 2).

**Version 2 — a minimal competence gate.**
- **Adds.** Feature 1 of §6b: the complex's integral becomes a slow, writable
  per-cell state that **gates something physical**, with retention and reset
  distinguished and its timescale declared.
- **Engine models.** Version 1's, plus the new gate operator.
- **What it would show.** The paper's multiplicative logic as a mechanism rather
  than an observable: cells enter a competent state only where pulse and
  competence overlap, and the spatial pattern of competence follows the delivery
  pattern. Still no division.
- **Prerequisites and gate.** **Needs D145's gene-regulation hold lifted or
  narrowed** (§6d, decision 1), and a design note first (D142). It belongs
  before the closed molecular-to-physiology loop.
- **Effort.** ~4–6 agent-days for the design note plus the operator and its
  guards, excluding qualification.
- **Decisions.** Decision 1, and which benchmark qualifies the gate — it should
  be one of the [GRN wet-lab](GRN_WETLAB_VALIDATION.md) models, most likely the
  yeast cell cycle, **not** this paper.

**Version 3 — state-triggered division and the integration of newborn cells.**
- **Adds.** Features 2 and 4: division triggered by the competent state, and a
  declared maturation trajectory for the newborn cell's channels and coupling.
- **Engine models.** `isopotential_partition@1`, `cytoplasmic_bridge_closure@1`,
  `scheduled_membrane_insertion@2`, `restricted_cleft_lumen@2`,
  `delayed_first_order_junction_formation@1`, over the composite, plus version
  2's gate.
- **What it would show.** **The first thing that is recognisably about this
  paper**: a localised pulse produces new cells in a border region, and the
  model reports whether and how fast they become electrically part of the sheet
  — plus the paired-daughter adjacency statistic that §2.5 measures, which the
  engine can compute *exactly* because it knows the lineage. **S** That makes
  version 3 a genuine test of the paper's own proxy: Cells can measure how often
  two adjacent cycling cells really are sisters.
- **Prerequisites and gate.** The **lifecycle gate's milestone 2** (endogenous
  lifecycle) with all its named open decisions; version 2.
- **Effort.** Large — milestone 2 is a gate in its own right, not a task.
- **Decisions.** Those already listed for milestone 2 in CURRENT_PLAN.

**Version 4 — excitability and conduction: the paper's open question.**
- **Adds.** Feature 3: a calibrated excitable cardiomyocyte membrane and
  propagation, with conduction observables.
- **Engine models.** A new cardiac excitable-membrane composition, built from the
  existing generic channel laws where they serve, over the junction and field
  machinery; plus version 3.
- **What it would show.** Whether a transient, spatially restricted population of
  cells with reduced sodium conductance and reduced coupling — the paper's
  `Scn5a`/`Gja1` observation — produces **conduction slowing, block or
  re-entry**, and how that depends on the fraction and the clustering. This is
  the question the paper raises, does not measure, and defers to pig studies
  (§2.11).
- **Prerequisites and gate.** A design note (D142) and its own qualification
  against independent references — the canonical excitable-tissue and
  propagation benchmarks, **not** this paper. Probably a new gate.
- **Effort.** Large; a feature track, comparable to water and volume.
- **Decisions.** Whether cardiac electrophysiology enters the engine-feature
  queue at all (§6d, decision 4).

**Version 5 — function and scar: not planned.**
Ejection fraction needs contractility; scar needs a matrix entity and
fibroblasts; both need multiple cell types, and the 12-week readouts need
long-time methods that do not exist. **This should not be promised**, and the
right statement to the user is that Cells will not produce an LVEF or a scar
fraction on any current gate.

| Version | Runs these engine models | Prerequisite | Gate | Effort | Needs from the user |
| --- | --- | --- | --- | --- | --- |
| **0** | `resolved_pump_composite@1` / `@3`, junction laws, `scheduled_species_turnover@1` | Composite landing; D150 v1 m3 | Composition | 2–3 agent-days, CPU only | A slot (decision 3) |
| **1** | + `local_species_reactions@1` | D152 code, **MG0c accepted** | Composition | ~2 agent-days | Decision 2 |
| **2** | + a competence-gate operator | **D145 hold lifted**; design note | Before the molecular loop | 4–6 agent-days | Decision 1 |
| **3** | + partition, bridge closure, insertion, junction formation | **Lifecycle milestone 2** | Lifecycle | A gate, not a task | Milestone 2's decisions |
| **4** | + a cardiac excitable membrane and conduction | A design note and its own references | New | A feature track | Decision 4 |
| **5** | + contractility, matrix, fibroblasts, long-time modes | Several gates | — | Not planned | — |

### 6d. The decisions the user must make

1. **Do we lift or narrow D145's gene-regulation hold for a minimal competence
   gate?** D145 holds the GRN track; D151 says explicitly that it does not lift
   that hold. Versions 2 onward need it.
   **Recommendation: narrow it, do not lift it.** Authorise *one* general
   operator — a slow, writable per-cell state with a declared timescale that
   gates an operator — designed first under D142, qualified against a GRN wet-lab
   benchmark (the yeast cell cycle), and explicitly **not** a transcription
   network. That gives versions 2–3 their prerequisite, serves the
   coupled-renewal gate's "causal carriers" row and the GZMK review's item 6, and
   keeps the full GRN track held. **S** Lifting the whole hold now would compete
   with the composite and the lifecycle gate for the same slots.
2. **Does a comparison with this paper's data need per-paper approval under
   D138?** D138 makes *reproducing a paper's own model or code* tooling needing
   approval per paper; this paper deposits **no model and no code** (§1), so
   there is nothing to reproduce and no reference solution to write.
   **Recommendation: no approval needed for versions 0–2**, which compare against
   *generic kinetics* (a protein half-life, a pulse shape) rather than against
   the paper's biological claims. Ask for approval at **version 3**, where the
   model would first be compared with a paper-specific result (the 41.5%/5.5%
   adjacency statistic). Flagging it now, early, is the cheap option.
3. **Which readouts do we target first?**
   **Recommendation: the spatial-restriction readout (version 0), not the
   efficacy readouts.** It is the one question where Cells has qualified physics
   and the paper has none, it needs no new feature, and it is honest about what
   it shows. The alternative — chasing ΔEF or scar — is unreachable (§6b item 5,
   6) and would be the D144 mistake. If the user wants something recognisably
   *of the paper* sooner than version 3, the next-best is version 1's kinetics,
   which at least calibrates on the paper's own measured numbers.
4. **Does cardiac electrophysiology enter the engine-feature queue?** This is the
   big one. It would be a feature track on the scale of water and volume, and it
   unlocks the paper's actual open question plus a large class of future work.
   **Recommendation: yes, but queued behind the current gates, and as general
   excitable-tissue physics — not as a "cardiac mode".** Cells already has the
   channel families, junctions and the field solver; what is missing is a
   calibrated composition and the conduction observables. **S** It is also the
   feature most likely to be wanted by several future papers at once, which is
   the D144 test for whether a feature is general.
5. **Species and organ scope.** The paper is mouse, with human hES
   cell-derived cardiomyocytes in vitro, in the left ventricle.
   **Recommendation: declare the model's cell type as a generic coupled
   excitable sheet, not "mouse left ventricle", for versions 0–2**, since the
   qualified channel parameters in Cells are mammalian but not cardiac and
   nothing would be gained by claiming a species. Decide species at version 4,
   where calibration actually binds — and note the paper's own evidence that
   mouse and human constructs behaved equivalently in vitro (Extended Data
   Fig. 6a,b), which weakens any argument for picking one early.
6. **One scope question worth settling early:** should the **protein catalogue**
   (stage 3, held) extend to **nuclear regulatory proteins** so that the
   activator, the competence factor and the complex can carry identity,
   stoichiometry and evidence? The catalogue today covers channels, pumps,
   transporters and junction channels; the GZMK review asked the same question
   for secreted proteases and ECM proteins.
   **Recommendation: decide it once, for both, when catalogue stage 3 opens** —
   not now, and not per paper.

### 6e. What Cells could uniquely add

Three things, in order of how distinctive they are.

1. **Whether newborn cardiomyocytes integrate electrically, and whether they
   create conduction heterogeneity or arrhythmia risk.** This is the paper's own
   proposed mechanism of death (§2.8), its principal stated safety concern, and
   the documented failure mode of the nearest competing therapy (lethal
   arrhythmias with sustained AAV6 microRNA-199a in pigs). **The paper measures
   nothing electrical** (§2.11) and defers the question to large-animal mapping
   studies. A bioelectric tissue engine with gap junctions, per-cell channel
   populations, a junction-formation law for newborn cells and exact knowledge of
   lineage is an unusually well-suited instrument for it — and the question is
   *general*: what does inserting immature, weakly coupled cells into a
   conducting sheet do? **S** This is the strongest scientific reason to take the
   paper, and it needs version 4.
2. **The spatial-restriction effect, quantified.** The paper has exactly two
   points on the dose–localisation axis: ~100% of cardiomyocytes (lethal) and
   ~9–10% of the left ventricle (beneficial). A model can sweep the fraction
   *and* the spatial arrangement at fixed fraction, and report where the
   transition lies and what sets it. That is the question the paper's own closing
   sentence poses and cannot answer with two groups of eight mice, and
   **version 0 can start on it with qualified physics**. It is also the one place
   where a model could say something *useful* about dosing rather than merely
   consistent.
3. **A test of the paper's own division proxy.** §2.5's central measurement
   assumes that adjacent labelled cells are sisters. In Cells, lineage is exact,
   so the model can compute the true sister fraction *and* the adjacency proxy
   under a known local stimulus, and report the proxy's bias. **S** That is a
   methodological contribution to the field's assay, available from version 3,
   and the kind of thing only a simulator can supply.

**S** A fourth, more speculative connection: the paper's CM1 → CM2 → CM3
trajectory is a *written, slowly relaxing cell state* that determines a later
fate, and the engine's coupled-renewal gate exists to ask whether such states
persist and renew. The honest position is that the paper supplies **no parameter**
for either preprint and should not be cited in support of them — the same ruling
the GZMK and partial-reprogramming reviews reached.

## 7. What not to do

- **Do not build a cardiac model, a "regeneration mode" or a Myc operator for
  this paper** (D144). Every feature in §6b is stated generally because it must
  be built generally: a competence gate, excitable-tissue physics, newborn-cell
  maturation.
- **Do not name a law, species or operator after Myc, cyclin T1, CDK9, P-TEFb,
  `Scn5a` or connexin 43.** Neutral names, per the
  [catalogue rule](PROTEIN_CATALOGUE_PLAN.md); labelling a generic law with a
  protein is a new scientific claim. The physics of a reversible binding or a
  first-order clearance is generic.
- **Do not promise ejection fraction, scar fraction or survival.** They need
  contractility, a matrix entity, fibroblasts and 12-week durations (§6b items 5,
  6, 8). Saying so plainly now is better than discovering it at a gate.
- **Do not treat the arrhythmia hypothesis as a result.** Reduced `Scn5a` and
  `Gja1` in a supplementary table are transcript levels; no conductance,
  conduction velocity or rhythm was measured (§2.11). If Cells models it, Cells
  is **generating** the hypothesis's first quantitative test, not reproducing a
  finding.
- **Do not take the adjacency statistic as a division rate.** 41.5% versus 5.5%
  is a proxy with a plausible non-clonal explanation in exactly the setting it
  was measured (§2.5), and the overall labelling difference behind it is
  *P* = 0.0545.
- **Do not fit a decay constant to the 24-hour result.** It is an absence of
  staining at one time point with n = 3, and no Myc measurement lies between 4 h
  and 24 h (§2.2). The citable kinetic number is the **20–40 min protein
  half-life**, which is the literature's, not this paper's measurement.
- **Do not put this physics in `validation/`.** A competence gate, excitability
  and newborn-cell maturation belong in `src/cells` as Cells models;
  `validation/` holds drivers, analysis, independent reference solutions and
  runners (AGENTS.md).
- **Do not use this paper as the qualification case for any feature.** MG0c
  qualifies D152's operator; a GRN wet-lab benchmark should qualify a competence
  gate; canonical propagation benchmarks should qualify excitability. This paper
  is a **consumer** and a motivation.
- **Do not download or reuse the authors' sequencing or proteomics data to fit
  anything** without the user's decision. The deposits are named in §2.10; they
  are expression data, not kinetic constants, and turning a differential
  expression into a rate is the error the CCI-seq review names.

## 8. Provenance

Both papers read in full from publisher HTML on **14 November 2026**; the 2026
paper via `curl` after Nature's identity-provider redirect defeated the fetch
tool, the 2020 paper the same way. Supplementary PDFs, Supplementary Tables 1–5
and the per-animal Source Data workbooks were **not** read, and no claim here
rests on them except where §2.8 says so explicitly. The paper is not in PMC. No
external simulator or code was obtained; neither paper deposits any. URLs,
dates, licences and the conversion method are in the
[access log](/mnt/workspaces/Cells/paper-review-myc-cyclint1-20261114-01/ACCESS_LOG.md);
notes and the converted text are in the same run folder. Current simulation and
qualification status stays in [PROGRESS.md](../PROGRESS.md) and the ordering in
[CURRENT_PLAN.md](CURRENT_PLAN.md). **This review adds notes and a plan only: no
simulator change, no parameter fit, no run and no scientific acceptance.**
