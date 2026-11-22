# Single-ribosome translation timing: a desk note on FR-40 (D286)

*22 November 2026, by the gene-regulation references' author. This is a desk note: nothing was run.*

**Code-blind.** It reads only:
- the equation sheet `docs/TEMPLATED_POLYMERISATION_LAWS.md` at tag `gr1-sheet-fr38-erratum-a-2026-11-22`, whose §2 and §4.1–§4.3 are unchanged since `gr1-sheet-2026-11-20`;
- FR-40 and the Lean lane's evidence note `lean/claims/incoming/translation-release-evidence.md`, both at e551172b;
- the paper, Yan et al. 2016, *Cell* 165:976–989, PMC4889334: its main text and figure legends, and the text of its Supplemental Experimental Procedures, extracted from the PDF.

No engine code was read, including the source lines the evidence note links. The paper is paraphrased, and its numbers are cited with pages.

## The observation

**The reporter.**
- SunTag24x-Kif18b-PP7²⁴ˣ, 1,462 codons (supplement p. 4).
- The SunTag array is at the N-terminus: 23 codons before it, 24 SunTag peptides, then 6 codons before Kif18b (supplement p. 10).
- The 5′ leader is the Emi1 5′ UTR_long. It represses initiation, so a single ribosome can be seen decoding an mRNA (Figure 7).

**The cells and imaging.**
- U2OS cells at 36–37 °C (main text, methods).
- Images every 30 s (Movie S7, related to Figure 7).

**The interval** (supplement pp. 4–5).
- It runs from the first frame in which GFP is reliably detected above background to the frame where the signal disappears at release.
- Only tracks shorter than 12 min were included.
- The mean is **406 s over n = 44** single-ribosome events.
- No uncertainty is given for the mean. Figure 7D shows the single-ribosome rates as a mean ± SD only graphically.

**The paper's speed from this interval.**
- The detection threshold is placed at codon 245, which leaves 1,462 − 245 = 1,217 codons in the interval.
- 1,217/406 s = 3.0 codons/s.
- That speed is computed from the 406 s itself, so it cannot predict it.

## 1. What the sheet's laws predict for this interval

**The laws.**
- §4.2 cuts a chain of L residues into m stages of r = L/m residues.
- A complex leaves each stage at rate κφ = vφ/r, independently of every other complex. There is no traffic, queuing or pausing (§7, item 4).
- §4.3 releases the chain at the last stage's exit.
- Initiation (§4.1) is not involved once the ribosome is on the chain.

**The interval from detection to release.** A ribosome detected as it leaves stage j_d, at codon d = j_d r, reaches release after the remaining m − j_d stages.
- Its time is Erlang(m − j_d, vφ/r).
- **Mean:** (L − d)/(vφ). It falls as 1/v, grows with L − d, and falls with φ.
  - φ is the product of the draws' saturation and the per-residue affinity factor. The sheet's A1 has φ_tl = 0.986.
  - Timing alone measures only the product v_eff = vφ.
- **SD:** the mean divided by √(m − j_d). The coefficient of variation is √(r/(L − d)), so the spread is set by the declared stage count, not by any other parameter.

**The stage structure meets this reporter in a definite way.**
- §2 requires m to divide L. Here L = 1,462 = 2·17·43, so m ∈ {1, 2, 17, 34, 43, 86, 731, 1,462}.
- Since gcd(245, 1,462) = 1, codon 245 is a stage boundary only for r = 1 (m = 1,462). Coarser stages put detection at the nearest boundary.

| m | r (codons) | Detection boundary | Stages from detection to release | Coefficient of variation |
| ---: | ---: | --- | ---: | ---: |
| 1,462 | 1 | 245 | 1,217 | 0.029 |
| 86 | 17 | 238 | 72 | 0.118 |
| 43 | 34 | 238 | 36 | 0.167 |
| 17 | 86 | 258 | 14 | 0.267 |

**The per-codon reading.**
- For one ribosome, m = L is the physically natural reading: one stage per codon, the elementary step of §4.2's biased walk.
- It predicts a spread of about 3 %, an SD of about 12 s at 400 s.
- Any broader spread in Figure 7D is heterogeneity or pausing, which the law does not contain. It is a finding about the law's homogeneity, not a reason to choose a smaller m.

**Predicted means** at d = 245 and φ = 1:

| Speed | Source | Predicted interval |
| --- | --- | ---: |
| 3.1 codons/s | The paper's single-mRNA runoff (§3) | 393 s |
| 3.1/1.05 codons/s | The same, with its stated 5 % positional overestimate removed | 412 s |
| 3.5 codons/s | The paper's population runoff fit | 348 s |
| ≤ 2.73 codons/s | The runoff histogram's lower-edge bound (§3) | ≥ 446 s |

**The observation model also moves the predicted number.**
- **Truncation at 12 min.** Selecting tracks shorter than 720 s lowers the observed mean of an Erlang time whose mean is about 400 s:

  | Stages | Coefficient of variation | Change in the observed mean |
  | ---: | ---: | ---: |
  | ≥ 64 | ≤ 0.125 | 0 % |
  | 16 | 0.25 | −0.3 % |
  | 8 | 0.35 | −2.3 to −2.9 % |
  | 4 | 0.5 | −8.5 to −9.5 % |
  | 2 | 0.71 | −20 % |

  The per-codon law makes it negligible. A broad real spread would not.
- **The 30 s frames.** The start is the first frame above threshold, so it lags detection by 0–30 s. The paper does not say whether the end is the last frame with signal or the first frame without. Together these give a systematic offset of up to about 30 s (7 % of 406 s) whose sign depends on that convention.

## 2. The detection model

**What the paper states:**
- **The threshold.** Signal from a single ribosome was reliably detected at about 1/3 of the maximal single-ribosome intensity (supplement p. 4).
  - The maximum is the mean of the last 3 frames before release, with the 44 traces aligned at their last frame.
  - The threshold comes from aligning the same traces at their first detected frame.
- **The inference.** About 8 of the 24 SunTag peptides have been made at detection, placing the ribosome at codon 245 once the exit tunnel is allowed for. The runoff fit uses a 36-codon tunnel, with 23 codons before the array and 6 after it (p. 10).
- **The intensity model.** Each peptide adds one scFv-GFP once it emerges, so intensity rises linearly to a plateau (pp. 7–8).

**What follows from those statements but is not stated:**
- A SunTag repeat of about (245 − 23 − 36)/8 = 23.25 codons.
- Full intensity reached at about codon 617: the 23 leading codons, plus 24 repeats, plus the
  36-codon tunnel.

**What the paper leaves out:**
- **An uncertainty on the threshold** or on the 8 peptides. A band of 6 to 10 peptides moves d from 199 to 292 and L − d by ±3.8 %, about ±15 s at 400 s.
- **Event-to-event variation of the detection point.** The threshold sits against each cell's own background, but it is applied as one number.
- **The scFv-GFP binding kinetics and the peptides' accessibility after the tunnel.** The inference
  assumes each emerged peptide is bound at once. A binding delay t_b would put the ribosome v·t_b codons
  further along at detection than inferred, so the true L − d would be shorter.
- **The end point's frame convention** (above).
- **The per-event durations.** Only the mean is given in text.

**In the sheet's terms.** Detection is the exit of stage j_d, so d must be fixed from the construct and the intensity calibration before any timing is read. With r = 1, d = 245 is exact.

## 3. An independent speed

**Within the paper.** These come from the same cells, the same coding sequence and the same lab, but a different assay and a different 5′ leader.
- **Single-mRNA total runoff** (Figure S2E): 3.1 ± 0.14 codons/s; the ± convention is not stated.
  - It is 1,462 codons divided by the mean runoff time, less 60 s for the drug to enter.
  - It assumes the last ribosome sat at the start codon. The paper puts the resulting overestimate at about 5 % (supplement pp. 3–4).
- **Population runoff fit** (Figure 2): 3.5 ± 1.1 codons/s.
  - It is model-based: a linear fit between 40 % and 80 % of the normalised intensity, after a stalled fraction is subtracted.
  - It corrects for the 23 + 6 flanking codons and the 36-codon tunnel (p. 10).
- **The single-ribosome 3.0 codons/s** comes from the 406 s and is not independent.

**Outside the paper.** Named from memory and not read:
- ribosome-profiling runoff in mouse ES cells (Ingolia et al. 2011);
- other single-mRNA SunTag studies in human cells (2016).

Each would need a direct read, and each has other cells, reporters or conditions. None suits a few-percent prediction for this reporter.

**The sheet's own speed does not transfer.** Its only translation speed is A1's v_tl = 16 aa/s, declared inside a 12–21 aa/s range that §8 sources to Bremer and Dennis's E. coli rates.

**The paper's speed against its own histogram.**
- **The conflict.** 3.1 codons/s needs a mean corrected runoff of 1,462/3.1 = 7.86 min. The evidence note's graph readings of Figure S2E (152 sites) give at least 8.93 min from the bins' lower edges, which bounds the speed at no more than 2.73 codons/s.
- **What would reconcile them.** Each candidate gives a mean, at lower edges and at mid-bin:

  | Candidate | Lower edges | Mid-bin |
  | --- | ---: | ---: |
  | Leave out the open ≥ 18 min group (15 sites, perhaps stalled) | 7.94 min | 8.94 min |
  | Subtract the 60 s again (the caption says the plotted times already include it) | 7.93 min | 8.93 min |
  | Both | 6.94 min | 7.94 min |

  - No single candidate reaches 7.86 min unless the times sit near the bins' lower edges.
  - The text supports none of them.
  - The per-site runoff times, or the sample and correction actually used, would settle it.
- **If the histogram is right** (v ≤ 2.73 codons/s), the law predicts at least 446 s, 10 % above the observed 406 s.
  - Truncation cannot close that gap under the per-codon law.
  - Closing it would need detection near 13 peptides (d ≈ 354, about half the maximal intensity, not 1/3).
  - Or the leader-repressed single-ribosome events would have to run faster than the runoff ribosomes.

## 4. A registration plan

**Fixed and tagged before any reading:**
- **The reporter:** L = 1,462.
- **The detection point:** d, from the construct and the intensity calibration (23 + 36 + 23.25 k codons for k peptides), with a declared band for k. It is not taken from timing.
- **The law:** §4.2 with a declared stage count. The proposal is m = 1,462 (r = 1), so that d is a stage boundary and the spread is the per-codon walk's. φ is declared, either 1 or the world's.
- **The speed:** its value and source. **No candidate qualifies today** (§3).
- **The observation model:** tracks shorter than 12 min, 30 s frames with a declared end-point convention, n = 44.
- **The statistic:** the selected events' mean interval. The prediction is the model's E[T | T < 720 s] under the frame convention.

**What is compared.** The prediction against 406 s.

**The tolerance.** The root-sum-square of:
- the mean's standard error, which needs Figure 7D's SD or the events (SD/√44);
- the speed's uncertainty: the stated ±0.14 (convention unknown) and the one-sided 5 % positional bias;
- the detection band, ±3.8 % for 6 to 10 peptides;
- the frame convention, up to 7 %.

Before the standard error, that is roughly ±9–10 %. This is a coarse check.

**Validation or calibration.** As things stand this can only be a calibration.
- **Why.**
  - The only speeds tied to this reporter come from the same paper.
  - Its runoff speed disagrees with its own histogram by at least 13 %.
  - Its single-ribosome speed is computed from the 406 s.
  - Fitting v_eff = (L − d)/406 s returns the paper's 3.0 codons/s by construction, and tests nothing.
- **What would make it a validation.** Both of these:
  - an independent speed, fixed before reading, measured under matched conditions (U2OS, 36–37 °C, this coding sequence or a declared transfer). The runoff speed would qualify once reconciled from its per-site times;
  - d fixed from the intensity calibration alone.

  Even then it tests the law's kinematics, mean = (L − d)/v_eff, across two assays. That is as much a consistency check of the paper's measurements as of the law.

**Tests the law makes without v.**
- **The ratio of intervals between reporters** of different lengths with the same tag and leader, (L₁ − d)/(L₂ − d). It cancels v, but this paper (as read) has no such pair.
- **The spread.** The per-codon law predicts about 3 %. Figure 7D's SD, read as data, would test the law's homogeneity, and is expected to show more spread. That would be a recorded non-claim (§7), not a fitted m.

**For a later engine comparison** (after G3 and G4). A world with one template and one ribosome, released from stage j_d, gives the Erlang interval exactly. R-noise's direct method (§6) gives its distribution, and the ODE gives its mean. No run is needed for this note.
