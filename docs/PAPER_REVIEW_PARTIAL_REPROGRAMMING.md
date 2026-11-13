**Partial reprogramming across three human lineages, and what Cells can take from it

**Update, 13 November 2026 (D151).** The user: "we want to test all of this in the end". Every ranked candidate below is deferred, not closed; its prerequisite and gate stand as written, and any "park" or "not recommended" reads as "deferred".
— reviewed 13 November 2026**

Kaho Washizu, Xun Wang, Julia M. Draper, Shinya Yamanaka and Akira Kunitomi,
*Partial reprogramming reveals lineage-specific uncoupling of rejuvenation,
function, and recoverability in human cells*, bioRxiv v1, posted 12 November
2026, not certified by peer review; **CC BY-NC-ND 4.0**.
[Preprint](https://doi.org/10.64898/2026.11.09.764947),
[PDF](https://www.biorxiv.org/content/10.64898/2026.11.09.764947v1.full.pdf).
Gladstone Institute of Cardiovascular Disease, with CiRA and UCSF.

**This is a cell-state and epigenetics paper: it contains no bioelectricity, no
mechanics, no water or volume, and no division physics, so it adds no engine
feature and sets no numerical target for any qualified Cells model.** Its value
is a protocol lesson that the renewal assay can adopt at zero cost, and a
second-tier future benchmark for the planned gene-regulation layer. The lesson:
measure the state a cue actually produced rather than the cue schedule, confirm
the cue is gone before claiming retention, and score the retained mark and the
recovered function as separate outcomes, because the paper shows them coming
apart in opposite directions in different cell types. **No data or code are
available yet**: everything is promised "upon publication of the peer-reviewed
article" (Methods, Data and Code Availability), so nothing here can be run as a
held-out test today. This review proposes no runs and no code.

## What the paper shows

Primary human cells of three lineages were partially reprogrammed with a
traceable, reversible Sendai-virus OSKM system, sorted live into graded
intermediate states, released by switching the factors off, and then followed to
a recovery endpoint. The lineages were dermal fibroblasts (HDFs), CD8⁺ cytotoxic
T cells (CTLs) and aortic endothelial cells (HAECs), **four donors each, aged
48–63, both sexes** (Lonza and commercial PBMC sources; Methods, Experimental
Model).

The design has three parts that matter more to us than the biology:

1. **Depth is a measured state, not an exposure time.** GFP (KOS) and OFP (cMYC)
   reporters mark cells that received the factors; within the double-positive
   cells, two surface markers per lineage define three ordinal groups (Gr1–Gr3):
   CD13/SSEA5 for HDFs, CD8α/SSEA4 for CTLs, CD31/SSEA4 for HAECs. **Under one
   identical exposure the three lineages reach different states** (Figure 1D),
   which is the paper's argument against defining partial reprogramming by
   duration.
2. **Release is verified, not assumed.** Shifting 35 °C → 38 °C stops the
   temperature-sensitive vector. "Reporter clearance" is defined as GFP and OFP
   returning to the level of non-transduced cells, and it **takes 4–7 days after
   the shift and depends on both lineage and depth** (Figures 2A–2C). Endpoint
   assays begin only after clearance.
3. **Retention and function are scored separately,** with a functional challenge
   after release: scratch closure for HDFs (day 25), CD3/CD28 restimulation with
   IFN-γ and perforin output for CTLs (day 30), Matrigel tube formation for HAECs
   (day 21).

**The result is a double dissociation between the retained molecular mark and the
recovered function**, and ordinally matched states are not equivalent across
lineages:

| Lineage | Retained after release | Function after release |
| --- | --- | --- |
| HDF | Gr2 and Gr3 kept a significantly lower Horvath methylation age at day 25; Gr1 did not | Morphology and global transcriptome converged to control, but ECM/matrix-remodelling and contractile myofibroblast-like programs stayed elevated; Gr3 scratch closure significantly reduced and growth still impaired 20 weeks on; Gr2 closure not significantly different from control |
| CTL | The BLUP-clock reduction seen at sorting was **gone** by day 26 (also by Horvath and IntrinClock) | Only the shallowest state recovered: Gr2 and Gr3 failed to sustain expansion and Gr3 was lost; Gr1 outgrew controls over four weekly restimulations, had more CD28⁺ cells, and secreted more IFN-γ and perforin at day 30 |
| HAEC | Gr1 and Gr2 both kept a lower methylation age at day 21, numerically larger in Gr2 | Gr2 converted to a Gr1-like state within 3 days of the shift; both states matched control endothelial identity, expanded better than control, and improved all four cell-number-normalised tube-formation metrics |

**None of this tracked competence for full reprogramming.** iPSC derivation
efficiency was about 3% (CTL), 1% (HDF) and 0.02% (HAEC) — the paper states CTLs
were roughly 150-fold more efficient than HAECs — and yet HAECs, the least
competent, gave the only outcome in which all three measured benefits were
retained together, while CTLs recovered only from the shallowest state.

**The shared regulator.** Single-nucleus multiome profiling (10x ATAC + gene
expression; **78,269 HDF, 71,382 CTL and 48,202 HAEC** QC-passing nuclei) was
used to infer per-lineage gene regulatory networks with Pando. Intersecting
inferred transcription-factor edges across all three lineages left a compact core
containing the four OSKM factors (an internal positive control), a small
JUNB-associated component, and a module around **TOX**, an HMG-box factor with no
described role in human somatic reprogramming. TOX was transiently induced in the
deeper states, and transient induction reproduced in three public HDF-to-iPSC
datasets the authors reanalysed (GSE242424 with subseries GSE242423, GSE118258,
GSE221739). Knockdown (siRNA in HDFs and HAECs, shRNA in CTLs) sharply reduced
iPSC colony formation in all three lineages without reducing early SeV-OSKM
transcript abundance, and lowered the yield of every graded state; overexpression
in HDFs shifted the same pathways in the opposite direction but **did not**
improve colony formation. The authors therefore call TOX permissive rather than
sufficient. The downstream programs were mostly lineage-specific: Pando nominated
163, 185 and 219 candidate TOX targets with 24 shared by all three; requiring
knockdown support cut these to 109, 76 and 86 with **five** in common (COL25A1,
HTR7, MAP7, PIR, SYNE1).

**Measured versus modelled.** This separation matters for anything we would later
compare against.

| Measured | Modelled, inferred or hand-curated |
| --- | --- |
| Flow-cytometry marker fractions and reporter MFI over time; iPSC colony counts; expansion curves; scratch closure (% width change over 6 h); CD28⁺ fraction; IFN-γ and perforin concentrations (13-plex bead assay, technical triplicate); tube-formation junctions, segments, master segments and total master-segment length, normalised by a PrestoBlue-estimated cell number; qPCR; bulk RNA-seq counts; methylation-array β values; multiome counts | **DNA methylation age** (Horvath, BLUP, IntrinClock clock models applied to GenomeStudio AVG_Beta with normalisation disabled, and β = 0.5 imputed for missing IntrinClock CpGs); **module scores** (arithmetic means over hand-picked gene sets in Table S1, plotted as within-donor differences from control); **RNA velocity and latent time** (UniTVelo, Gr1 specified as root, scaled per cell type and explicitly not comparable across cell types); Leiden clusters and the selection of "representative" clusters; **Pando GRN edges**; the **surrogate TOX motifs** (SOX9 MA0077.1, SOX10 MA0442.2, TCF7L2 MA0523.1 — Pando has no TOX PWM, and these are shared with the exogenous SOX2); chromVAR deviation Z-scores; scPrinter/seq2PRINT sequence attribution; FIMO and JASPAR motif matches; consensus regulatory intervals; the four functional categories assigned to candidate genes |

**Limits, as the authors state them and as we read them.**

- **In vitro, four middle-aged donors per lineage**, no tissue or organismal
  context. Statistics are donor-level (n = 4) paired t-tests and
  repeated-measures ANOVA with Dunnett against control, in GraphPad Prism. Small
  n: effect directions are usable, narrow tolerances around figure values are not.
- **Two arms are missing by attrition, not by design.** HAEC Gr3 was too rare to
  culture and was excluded; CTL Gr3 was lost after day 11. The cross-lineage
  comparison is therefore not a full 3 × 3.
- **The ordinal groups are not a common scale.** Each lineage's Gr1–Gr3 come from
  a different marker pair and from flow gates the authors say can contain cells
  spanning groups. "Gr2 in HDFs" and "Gr2 in HAECs" are comparable only by rank,
  which is the paper's own point.
- **Clock ages are model outputs** and the authors note they are clock-, cell
  type- and culture-time-dependent; the Horvath clock did not track progression in
  CTLs at all, which is why two further clocks were introduced.
- **The TOX network is candidate-level throughout.** No TOX occupancy data; the
  motifs used are surrogates shared with exogenous SOX2; knockdown support was
  **directional only, with no statistical threshold**; "KD-supported candidate"
  therefore means nominated by inference and down after knockdown, nothing
  stronger. Some differential-expression tables are vendor-generated
  (Plasmidsaurus) and were used as provided.
- **The proliferation confound is partly, not wholly, addressed.** Reprogramming
  needs division and TOX knockdown attenuates proliferative programs; the authors
  argue from preserved cell yield without OSKM and from colony output not scaling
  with intermediate yield (siTOX #3 cut yields under 3-fold but colonies about
  8-fold). That is an argument, not an isolation of the mechanism.
- **One reagent caveat is open:** siTOX #2 reduced HAEC cell yield without OSKM;
  the authors attribute it to sequence-specific off-target toxicity but cannot
  exclude a depletion past a viability threshold.
- **No safety claim.** Factor clearance does not establish genomic stability or
  absence of tumorigenic potential, and the authors say so.

## Relevance to Cells, layer by layer

Mapped onto what exists today, with the gates from the
[current plan](CURRENT_PLAN.md).

| Cells layer | Bearing | Why |
| --- | --- | --- |
| Bioelectric layer (`resolved_pump_tissue@3`, channels, pumps, gap junctions and the delayed formation law) | **None** | No membrane potential, ionic current, conductance or junctional coupling is measured anywhere in the paper. Its markers (CD13, CD31, CD8α, SSEA4/5) are surface antigens, not transport proteins. mRNA for a channel remains a hint about identity, never an abundance or a conductance — the caution already recorded in [GRN_WETLAB_VALIDATION.md](GRN_WETLAB_VALIDATION.md) |
| Water and volume (`resolved_pump_water@1/@2`) | **None** | No volume, osmolarity or water measurement. The morphological "rounding" after factor withdrawal is shape and adhesion, not a volume-regulation datum, and must not be read as one |
| Cell replacement and turnover (E07-v1) | **Method, not data** | The paper's premise is the opposite route to E07-v1 stage B: resetting cell state *without* replacing the cells. What transfers is the three-part protocol above, and one empirical point for stage C — a lineage can converge to control in morphology and global transcriptome while a slow variable stays shifted, which is precisely the "matched visible state, different history" case the stage was built for ([E07_V1_DESIGN.md](E07_V1_DESIGN.md)) |
| The composite model and its operators | **No new operator** | The paper's state variables (chromatin accessibility, methylation, transcript abundance) have no owner in the plan's entity table. A future regulatory state would belong to the functional-unit population row (identity, abundance, internal state), not to compartments or membrane domains. Nothing here asks for a change to the ownership or combination rules |
| Division (S2–S5: membrane insertion, cleft lumen, partition) | **Weak, and not a target** | Reprogramming requires division, and the paper's expansion curves are its most quantitative lifecycle measurement — but they are population fold-expansion over weeks, several orders from the prescribed single-division physics of milestone 1 and outside even the endogenous lifecycle of milestone 2 ([gate: lifecycle operators](CURRENT_PLAN.md#gate-lifecycle-operators)). One honest connection: a mark that survives weeks of proliferation is inherited **through the carriers' own divisions**, which is the donor-copy route in [D139](DECISIONS.md#d139-cell-replacement-g2-rules), not arrival of unrelated newcomers |
| Mechanics (MG1 vertex model) | **None** | Scratch closure is collective migration on a substrate and tube formation is self-assembly in Matrigel. Both need migration, ECM and topology change; MG1 is passive vertex mechanics on fixed topology, and even the purse-string rung in the [Deb review plan](DEB_2026_MORPHOGENESIS_REVIEW_PLAN.md) is a closing ring, not a scratch assay. Do not read these assays as mechanics targets |
| The planned gene-regulation layer (heredity Stage D, parity P8) | **This is where it lands** | It supplies the structure of a cross-lineage perturbation test: one transcription factor removed in three regulatory contexts, with matched bulk RNA-seq, a shared pathway response (E2F targets, G2M checkpoint and MYC targets down; EMT and TGF-β up in all three) and largely lineage-specific gene-level responses. As a *benchmark* it ranks **below** the seven wet-lab-validated GRNs already listed, because the network is inferred from the same cells it describes, TOX has no motif of its own, and the target filter is directional. As a *held-out perturbation set* it is attractive once the deposit is public |
| The protein catalogue | **Identity only, so no** | The paper names proteins (TOX, the OSKM factors, COL25A1 and the module genes) but gives no stoichiometry, abundance or abundance-to-function relation, which is what the [catalogue plan](PROTEIN_CATALOGUE_PLAN.md) and the [closed-loop gate](CURRENT_PLAN.md#gate-a-closed-molecular-to-physiology-loop) require. One fact is worth keeping if transcription factors are ever catalogued: TOX is an architectural HMG-box factor thought to bind largely by DNA structure rather than sequence, which is the authors' own explanation for one shared input producing three different downstream programs |

## What it means for the two preprints

Both connections are analogies from a different system, and neither is evidence
for a claim in the preprints.

For [*Plastic Heredity*](https://doi.org/10.5281/zenodo.22143269), the paper is a
clean instance of its **first** question and silent on the second. An acquired
state is written by an external cue, the cue is removed and shown to be gone, and
the state's persistence is then measured: it persisted in HDFs and HAECs over the
14–18 days between sorting on day 7 and the endpoints on days 21 and 25, and had
vanished in CTLs by day 26. Where the cells divided — robustly in HAECs, partially
in HDF Gr2, barely in the growth-impaired HDF Gr3 — that persistence was
**mitotic**, carried by the cells' own descendants. No state is handed to
unrelated newcomers, so the paper says nothing about outliving its carriers. In E07-v1's terms it speaks to the donor-copy route and
not at all to the isolated-newcomer route. The useful transfer is negative and
methodological: a cue-written state can persist while every fast observable has
converged, so retention must be judged on the slow variable and not on the
appearance of the cell.

For [*How Patterns Return*](https://doi.org/10.5281/zenodo.23327869), the double
dissociation is the point: **function returned without the mark** (CTL Gr1
recovered identity and gained effector output, with no retained clock shift) and
**the mark persisted without full function** (HDF Gr2/Gr3 kept a lower
methylation age with incomplete proliferative recovery and persistent stromal
programs). Matching the present molecular state therefore neither guarantees nor
predicts which functions come back — consistent with the plan's existing note
that a reduced model must keep the slow variables that carry history. The paper
adds that **which** functions must return before recovery counts as complete is
itself lineage-specific. It makes no claim about patterns in space, repair of
form, or reconstruction, and we should not borrow its conclusions for those.

## What Cells could test, ranked against the current plan

Nothing here is a judged run, and item 1 is the only one actionable now.

| Rank | Candidate | Engine features needed | Gate | Judgement |
| --- | --- | --- | --- | --- |
| 1 | **Adopt the write–clear–challenge protocol rules** in the revised cue, release and turnover assay: (a) an explicit cue-clearance criterion, with the cue's effect measured back to baseline before any retention claim; (b) classify every run by the state measured at release rather than by the cue schedule; (c) report the retained slow variable and a post-release functional challenge as separate outcomes | **None.** E07-v1 already separates retention, newcomer conversion, spatial fidelity, transmissibility and physiological cost; a challenge can reuse `electrode_current_injection@1` or a second cue | [Coupled renewal](CURRENT_PLAN.md#gate-coupled-renewal) | **Do it.** Zero cost, lands exactly where the E07-v1 redesign is still the user's open decision (D145), and makes the assay's conclusions harder to fool |
| 2 | **A cross-lineage held-out perturbation test** for the gene-regulation layer: calibrate on one lineage, then predict the *direction* of the shared response to TOX loss (E2F/G2M/MYC down, EMT/TGF-β up) in the other two, judged only on the network's own nodes | The gene-regulation layer itself, which does not exist. No new physics | [Closed molecular-to-physiology loop](CURRENT_PLAN.md#gate-a-closed-molecular-to-physiology-loop), with the layer at position 6 of the D136 queue | **Log as second tier, behind the seven wet-lab-validated GRNs.** It is blocked on the public deposit, and it tests calibration transfer, not heredity |
| 3 | **A general slow, mitotically persistent regulatory state** for cells, if the engine ever needs one | A regulatory-state entity on the functional-unit population row, with conserved accounting and partition at division. The mechanism is **not** supplied by this paper, so it must be sourced from the literature before any design (D136) | Closed molecular-to-physiology loop | **Not now.** The paper is evidence that such a state exists and can persist for weeks, nothing more. Building it from this paper would be building for one experiment ([D144](DECISIONS.md#d144-qualify-the-simulator-for-many-uses-not-one-experiment)) |
| 4 | Reconstructing scratch closure or tube formation | Migration, ECM, growth and topology change: several rungs past MG1 and MG2 | [Integrated tissue unit](CURRENT_PLAN.md#gate-an-integrated-tissue-unit) | **Park.** Not justified by one paper, and the [morphogenesis ladder](MORPHOGENESIS_PLAN.md) order does not change |

The three public datasets the authors reanalysed (GSE242424 with subseries
GSE242423, GSE118258, GSE221739) are available today and could in principle check
the transient-induction claim independently, but that is reanalysis of other
people's data with their pipeline: it runs no Cells engine model, so it is tooling
and needs the user's approval ([D138](DECISIONS.md#d138-mg1-start-and-the-paper-backlog)),
and the lead's judgement is that it is not worth a slot.

## What not to do

- **Do not reproduce the paper's own analysis** — Pando, UniTVelo, scPrinter and
  seq2PRINT, chromVAR, methylclock, IntrinClock, FIMO. It is tooling, it runs no
  engine model, and per D138 and AGENTS.md it needs the user's explicit approval
  per paper. D137's approval covers Cortés-Poza Phase 0 only.
- **Do not add an epigenetic clock, a TOX model or a reprogramming model to
  `src/cells`.** That would be building for one experiment (D136, D144). If a
  general regulatory-state entity is ever wanted, it is designed first (D142) and
  sourced from the literature, not from this paper's inference.
- **Do not copy their code when it appears.** Its licence is unannounced; the
  preprint itself is CC BY-NC-ND 4.0, which permits no derivatives and no
  commercial use, so repo documents cite and paraphrase it (as this review does)
  and reproduce none of its text, tables or figures.
- **Do not turn module scores, clock ages, velocity latent times or Pando edges
  into physical quantities with tolerances.** They are derived scores over
  hand-picked gene sets and model outputs with disabled normalisation and imputed
  values; the gene sets themselves (Table S1) are not in the main PDF.
- **Do not treat the five shared candidate genes as a validated core.** They
  survive an inference step with surrogate motifs and a directional filter with
  no threshold.
- **Do not contact the authors for data.** Wait for the public deposit; no user or
  project details go into any outside request.
- **Do not open a milestone for this paper.** A milestone that runs no Cells
  engine model is tooling and needs the user's explicit approval (AGENTS.md).

## Open questions for the user

1. **Keep it in the backlog at all?** It supplies no engine feature and its data
   are embargoed until peer review. The alternative is to drop the row and revisit
   only if the published version appears with the deposit open.
2. **Should the revised E07-v1 adopt the three protocol rules in rank 1?** The
   redesign is still the user's open decision (D145), and this is the cheapest
   improvement in this review.
3. **For the post-release challenge, what counts as "function" for a Cells cell?**
   Candidates that exist today: response to a second cue, response to injected
   current, or volume regulation under an osmotic step. The paper's answer — that
   the right function is lineage-specific — argues for declaring it per cell type.
4. **Does the gene-regulation layer want a cross-lineage perturbation benchmark of
   this kind at second tier,** behind the wet-lab-validated GRNs, or should the
   layer's benchmark list stay as it is?
5. **Watch the DOI for the peer-reviewed version and the deposit, or leave it to
   the user to flag?**

## Provenance

Read: the v1 PDF in full — 67 pages, comprising the main text, all seven main
figure legends, the Methods, the supplementary figure legends S1–S7 and the
references. Not read: the supplementary figures themselves, **Table S1** (the
module gene sets), and the single-cell browser, trained models, GEO deposit and
code, all of which the paper defers to publication of the peer-reviewed article.
The bioRxiv HTML page refused two WebFetch attempts (HTTP 429, with Retry-After
of 106 s and 84 s) and was not pressed further; metadata came from the bioRxiv
API, and Europe PMC holds record PPR1366165 with no full text. The PDF was
retrieved directly and its text extracted locally through
`scripts/run_detached.sh`.

For weighing the claims: the work was supported by Altos Labs and CIRM; three
authors are co-inventors on a patent describing a method for rejuvenating human
somatic cells, and the senior author is an unpaid adviser to Altos Labs
(Declaration of Interests).

The downloaded PDF, its SHA-256, the extracted text and the access log are under
[/mnt/workspaces/Cells/paper-review-20261113-01](/mnt/workspaces/Cells/paper-review-20261113-01).
These notes introduce no model changes, no runs and no scientific acceptance.
Current status stays in [PROGRESS.md](../PROGRESS.md).
