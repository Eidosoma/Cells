# Scientific basis and research updates

Initial review: 2026-09-07. This document distinguishes results reported by the
source programmes from hypotheses and Cells experiments. The following paragraphs
retain the successive review scopes; current implementation is tracked in
[Progress](../PROGRESS.md). M1b verified the pinned isolated regulatory equations
and E/M source cases in Cells (R003), not coupled contact, PH, organ or paper-table
results at that stage. M1c-a added a synthetic passive-contact check in its
[own contract](PASSIVE_CONTACT.md); it is not a new upstream research finding.
R004 adds the accepted BETSE/software architecture review and a physical
one-cell specification, not a new biological or continuing-exploration result.
R005 adds a bounded native contact-function capture, the explicit physical/source
model distinction, and a document check-in on completed H3/H4 results. It does
not establish coupled source trajectories or rerun the continuing experiments.
Subsequent NUM-004/MODEL-005 qualify the bounded nominal pair separately.
R006 now selects a longer switching protocol, without running it or implying
whole-assay coverage from the earlier short numerical panel.
R007 begins a separate experimental-data benchmark with provisional endpoint
readings and explicit source/model compatibility gaps, not a biological result.
BIO-002 subsequently adds a descriptive Cells endpoint calculation under those
limitations, not a new literature review or validated production-cell result.
R008 closes that pilot after supplementary/methods review without biological
acceptance. R009 returns to architecture: a pinned BETSE capability inventory
and future parallel-GPU/multiscale contracts, not executed source parity.
R010 adds the first pinned membrane-channel rate/source review and independent
gate contract, not a calibrated channel or coupled production trajectory.
R011 reviews bulk electrodiffusion, membrane charge and scalable field-solver
design for SPEC-009; it is not new biology or executed upstream solver evidence.

## Calibration across the Cells stack

Direction and resource review: **2026-10-12**, with the cortical-learning
validation candidate added **2026-10-24**. Cells' scientific scope is the
coupling of molecular assembly, regulation, bioelectricity, chemistry and future
metabolism, mechanics and turnover within cells, tissues and organs. BETSE is
inspiration and a calibration/verification instrument for the bioelectric layer;
BITSEY provides a related regulatory/ionic reference. Coverage of those simulators
is an engineering milestone within the broader research programme.

Other references already shape the implementation. The
[protein-cage model](CAPSID_ASSEMBLY.md) follows the stochastic description in
[Asor et al. (2026)](https://www.nature.com/articles/s41586-026-10948-z), whose
study measures individual assembly histories using mass photometry. Cells has
not fitted its rates or validated its extended assembly-to-cell coupling against
those measurements. A future benchmark should compare intermediate populations
and assembly-time distributions under matched concentrations and preparation,
including the measurement window and the distinction between surface and bulk
kinetics.

The [reaction-network model](COMPARTMENT_REACTIONS.md) uses the ideal chemical
thermodynamics described by [Rao and Esposito (2016)](https://journals.aps.org/prx/abstract/10.1103/PhysRevX.6.041064).
The [electrodiffusion review](#r011-spatial-extracellular-closure-and-solver-separation)
draws on Solbrå et al., Sætra and Mori, and related energy/field-solver work.
These support equations, accounting and numerical design. Synthetic verification
parameters and source-model agreement do not establish measured cell physiology.

### Candidate resources for whole cells and organs

The resources below are a selection plan, not imported datasets or calibrated
Cells models. This review checked primary resource descriptions and the existing
paper notes; no dataset adapter, parameter fit or new biological run was made.

| Resource | Intended use in Cells | What remains to qualify |
| --- | --- | --- |
| [Physiome Model Repository / CellML](https://physiomeproject.org/data-repositories/physiome-model-repository) and [BioModels](https://www.ebi.ac.uk/training/online/courses/biomodels-quick-tour/what-is-biomodels/) | Locate published electrophysiology, signalling, metabolic and physiological models; reproduce selected equations and then return to their experimental sources. | Pin individual model versions, curation status, units, conditions and numerical protocols. Repository inclusion is not validation for every cell type, and models are not raw measurements. |
| [BioNumbers](https://bionumbers.hms.harvard.edu/aboutus.aspx) | Find literature constraints on cell size, molecular abundance, concentrations and characteristic times; use appropriate ranges to constrain model choices. | Read the cited original measurement, species, compartment and uncertainty. A literature number is not a universal default. |
| [Corrected Beard mitochondrial model and primary measurement leads](PAPER_REVIEW_MITOCHONDRIA.md) | Start energetic coupling with isolated-mitochondria comparisons, then ATP supply/demand, oxygen consumption, membrane potential and calcium responses. | Reproduce corrected equations/parameters and identify fitting versus independent data before integrating an energy module. Existing maintained ATP pools are not a metabolism model. |
| [Clawson et al. cortical culture learning, bioRxiv v1 (2026)](PAPER_REVIEW_CORTICAL_LEARNING.md) | Future wet-lab validation of burst-origin learning, persistence between sessions and error recovery; compare task function alongside ordinary electrical activity. | Planned, not implemented or validated. Obtain paper-linked recordings/code, reconcile age and preparation confounds, and qualify neural connectivity, synapses, slow plasticity and the electrode observation model. Keep source controls and proposed yoked controls distinct. [Experiment queue](EXPERIMENTS.md#cortical-culture-learning-and-error-recovery). |
| [Karr et al., whole-cell modelling (2012)](https://pubmed.ncbi.nlm.nih.gov/22817898/) | A prospective design reference for coupling cellular processes and grounding them in multiple data sources. | This is a bacterial model; it supplies neither an animal-cell parameter set nor validation of Cells. Only the publication overview was reviewed here. |
| [Human Protein Atlas](https://www.proteinatlas.org/about/introduction) | Constrain which proteins and compartments belong in a selected cell/tissue model, using expression and localization evidence. | Distinguish measured staining/proteomics from inferred expression, and relative signal from absolute abundance. Localization does not supply kinetic constants. |
| [CCI-seq](PAPER_REVIEW_CCI_SEQ.md), [Human Cell Atlas](https://data.humancellatlas.org/), [HuBMAP](https://portal.hubmapconsortium.org/) and [Human Reference Atlas](https://humanatlas.io/asctb-tables) | Select cell types, heterogeneity, neighbourhoods and anatomical placement for tissue/organ definitions; compare predicted organisation with observed samples. | Select matching species, tissue, developmental state and samples. RNA counts or clump membership do not specify electrical junctions; reference anatomy is not a functional organ model. |
| Organ-specific primary experiments and, where suitable, [PhysioNet](https://physionet.org/about/) recordings | Compare whole-system responses: electrical signals, pressure/volume/flow, solute transport, oxygen use, deformation and recovery after intervention. PhysioNet is a source of candidate physiological recordings, not all of these measurements. | Choose the organ and experimental task first, then a compatible dataset and measurement model. For example, extracellular ECG cannot be compared directly with a single cell's membrane voltage. |

For mechanics, growth and body shape, we still need selected primary measurements
of force/deformation, stiffness, volume changes, cell motion and turnover in the
chosen tissue. An anatomical mesh alone cannot supply those laws. The first organ
and species remain open; the human resources above are appropriate only for
compatible human targets. Other organisms need their own measurements.

### Turning references into calibration and validation

Begin with one cell type or small functional tissue unit and one measured
response. Keep independently measured inputs, fitted parameters and held-out
outcomes separate. Record preparation, bath/nutrient conditions, temperature,
geometry, units, replicate identity, uncertainty and the observation process.
Check both time courses and responses to interventions before transferring
parameters to a larger coupled model. Numerical/source agreement, CPU/GPU
agreement and biological prediction remain separate evidence.

The existing biological work retains its limits: the
[Bonzanni/RPTEC pilot](../reports/BIO003_PILOT_CLOSEOUT.md) closed as descriptive
without biological acceptance, and the
[Costa/Xenopus candidate](BETSE_BIOLOGICAL_BENCHMARK_PLAN.md) still needs original
methods and boundary-condition reconciliation. Neither is a completed whole-cell
calibration. These are useful starting lessons for the next measured-data target.

For organs, validate both the component physiology and the assembled function
against withheld conditions. Atlas agreement tests organisation; transport,
energetics and mechanics require functional measurements as well. The
[organ-selection plan](MULTISCALE_DESIGN.md#selecting-the-first-organ-later)
therefore chooses a tractable function and sufficient evidence before increasing
anatomical scale. Full stacks and reduced models must preserve the responses
relevant to the Plastic Heredity and Forms experiments.

## BETSE and BITSEY as complementary references

**BETSE** calibrates and verifies the bioelectric layer within the broader Cells
simulations; its [capability inventory](BETSE_CAPABILITY_ROADMAP.md) defines the
comparison scope. **BITSEY** supplies the coupled regulatory/ionic reference and
the cellular model used for our transmission and replacement extensions in
*How Forms Become Reconstructible*. Both are active reference choices.

BITSEY is a simplified BETSE-derived simulator. Its
[own README](https://gitlab.com/grodstein/bitsey/-/blob/b2cb370aaecbc8299f259bc4251d5396c81f19a6/README.md)
describes the relationship, and [Grodstein, McMillen and Levin (2023), section 2.5](https://www.frontiersin.org/journals/cell-and-developmental-biology/articles/10.3389/fcell.2023.1087650/full)
explains the faster, reduced model with uniform concentrations within each cell.
Inspection of the pinned [core](https://gitlab.com/grodstein/bitsey/-/blob/b2cb370aaecbc8299f259bc4251d5396c81f19a6/sim.py)
on 12 October confirms its own NumPy/SciPy execution and local transport helpers;
the inspected Python sources do not import BETSE as a runtime dependency.
Cells targets scientific feature parity with both, verified separately. Their
shared ancestry does not make their model assumptions, clocks or feature sets
interchangeable, or provide independent biological validation.

Cells already implements [isolated BITSEY regulation](EMT_REFERENCE.md) and a
bounded [two-cell regulatory/ionic model](SOURCE_EMT_PAIR.md). Independent
[graph](SOURCE_EMT_GRAPH_REFERENCE.md), [preparation](SOURCE_PREPARATION_REFERENCE.md)
and [long-path reference work](SOURCE_GRAPH_PATHS_REFERENCE.md) provide further
building blocks. These comparisons do not yet reproduce the complete Forms
lineage experiments. The [replication plan](ROADMAP.md#bitsey-replication) starts
with corrected clocks (P10R) and the freshly prepared editable lineage (P11),
then extends the assays with CPU/L4 verification.

The targeted source review on **2026-10-12** used Forms **v0.17, 10 October 2026**,
especially section 5.2 and methods C.7/C.9, plus the continuing exploration's
P10R/P11 protocols and P11/P32 reports. The native reference remains
[BITSEY revision b2cb370](https://gitlab.com/grodstein/bitsey/-/tree/b2cb370aaecbc8299f259bc4251d5396c81f19a6).
The lineage experiments extend that model; they are not the original cancer
paper's table experiments. Nominal BITSEY clocks and scaled regulatory
coordinates retain their source meanings rather than becoming calibrated
physical quantities through agreement with BETSE.

Local source provenance, relative to the external `Random-Replications` research
tree (not bundled with Cells):

- Forms: `WhereDoFormsComeFrom/PRE_PRINT_PAPER_DRAFT_V0.17.md`.
- Continuing BITSEY studies:
  `PlasticHeredity/NewIdeas/preprints/ingressing-minds-v-ruliad-paper-ideas/levin-cancer-gj-exploration/`;
  specifically `PAPER_CONTACT_CLOCK_RECOVERY_PROTOCOL.md`,
  `PAPER_EDITABLE_LINEAGE_PROTOCOL.md`, `PAPER_EDITABLE_LINEAGE_RESULTS.md` and
  `PAPER_CONVERGED_PAUSE_BOUNDARY_RESULTS.md`.

P32's reported completion on **12 October** is subsequent to that manuscript
version. This review uses its report as a future replication lead; it does not
rerun the study or audit its raw arrays. The corrected experiments and preserved
numerical failures keep separate identities.

## Subsequent research and model reviews

The source catalogue began with the September baseline. Later reviews are
recorded separately so a newer manuscript or mechanism does not silently replace
an earlier source version. The navigation review on **2026-10-11** did not repeat
the underlying literature searches or experimental analyses. Individual dated
reviews below record their own scope.

The Forms preprint is now titled *How Forms Become Reconstructible*. The September
orientation below retains the title used at that review.

| Reviewed material | Maintained entry point | Scope |
| --- | --- | --- |
| Plastic Heredity v5.0 and Where Do Forms Come From? v0.11, September orientation | [Recorded orientation](../PROGRESS.md) | Later research context; manuscripts belong to the external research tree and do not overwrite S01's v2.3 review |
| How Forms Become Reconstructible v0.17 and continuing BITSEY studies, reviewed 2026-10-12 | [Complementary references](#betse-and-bitsey-as-complementary-references) and [replication plan](ROADMAP.md#bitsey-replication) | Targeted lineage-method review; P10R/P11 are initial replication targets, with the later P32 report retained separately; no new Cells assay result |
| Asor et al. protein-cage assembly, reviewed 2026-09-19 | [Assembly model and source](CAPSID_ASSEMBLY.md) | Experimentally motivated stochastic model with prescribed geometry; implementation and cell coupling do not constitute a biological fit |
| CCI-seq, reviewed 2026-10-08 | [Paper review](PAPER_REVIEW_CCI_SEQ.md) | Tissue neighbourhood measurements as future observational inputs; association is not an inferred electrical conductance |
| Mitochondrial biology, reviewed 2026-10-10 | [Literature note](PAPER_REVIEW_MITOCHONDRIA.md) | Proposed energy, calcium and inheritance mechanisms; no mitochondrial simulator implementation or new experimental result |
| Quantum birthmarks, reviewed 2026-10-11 | [Literature note](PAPER_REVIEW_QUANTUM_BIRTHMARKS.md) | Quantum theory/simulation motivates proposed classical history, carrier and readout tests; no biological mechanism or simulator implementation follows from the analogy |
| Hazan and Levin channel compensation, reviewed 2026-10-13 | [Paper and source review](PAPER_REVIEW_CHANNEL_COMPENSATION.md) | Computational recovery, robustness and GPU search methods; pinned-code checks distinguish intervention constraints and integration throughput from biological rescue and whole-job performance |
| Clawson et al. cortical culture learning, reviewed 2026-10-24 | [Wet-lab review and validation plan](PAPER_REVIEW_CORTICAL_LEARNING.md) | Full v1 text and embedded supplement reviewed; prospective learning/recovery benchmark with source limitations, data-access prerequisites and no new Cells biological result |

## Current sources

This catalogue retains the original review IDs and versions. External research
files are identified by their original research-tree paths as provenance text;
those paths are not links into the standalone Cells checkout. Local Cells notes
and published sources remain linked. The historical path-discovery record does
not describe the current checkout location.

| ID | Source | Use in Cells |
| --- | --- | --- |
| S01 | Plastic Heredity v2.3 (original research-tree path: `../../../../PRE_PRINT_PAPER_DRAFT_V2.3.md`) | Process endpoints, interventions, cross-model evidence, and carrier hypothesis |
| S02 | Exploration overview (original research-tree path: `../../../preprints/ingressing-minds-v-ruliad-paper-ideas/levin-cancer-gj-exploration/README.md`) | Entry point to the continuing Levin-derived programme |
| S03 | Starting point (original research-tree path: `../../../preprints/ingressing-minds-v-ruliad-paper-ideas/levin-cancer-gj-exploration/STARTING_POINT.md`) | Original cancer model, source provenance, and modelling assumptions |
| S04 | PH evidence ledger (original research-tree path: `../../../preprints/ingressing-minds-v-ruliad-paper-ideas/levin-cancer-gj-exploration/PH_EVIDENCE_LEDGER.md`) | Reported results and their experimental limits |
| S05 | Commitment components (original research-tree path: `../../../preprints/ingressing-minds-v-ruliad-paper-ideas/levin-cancer-gj-exploration/COMMITMENT_COMPONENTS_RESULTS.md`) | Same-label state differences and causal component interventions |
| S06 | H2 rewriting (original research-tree path: `../../../preprints/ingressing-minds-v-ruliad-paper-ideas/levin-cancer-gj-exploration/REWRITE_TRADEOFF_RESULTS.md`) | Group context, retained rewriting, and failed onward transfer |
| S07 | Post-robustness programme (original research-tree path: `../../../preprints/ingressing-minds-v-ruliad-paper-ideas/levin-cancer-gj-exploration/POST_ROBUSTNESS_PROGRAMME.md`) | Reliability, conditional benefit, and autonomous-renewal extensions |
| S08 | Bounded pilot (original research-tree path: `../../../preprints/ingressing-minds-v-ruliad-paper-ideas/levin-cancer-gj-exploration/PILOT_RESULTS.md`) | Source behaviour, numerical sensitivity, and reported CPU timings |
| S09 | Strict-eight atlas identifiability (original research-tree path: `../../../preprints/strict-8-paper-preparations/codex.reconstructionsAndStressTesting/fableAtlasIdentifiabilityR20_5/results/IDENTIFIABILITY_REPORT.md`) | Colliding form labels and limits on lineage-specific routing claims |
| S10 | Ingressing/Ruliad law audit (original research-tree path: `../../../preprints/ingressing-minds-v-ruliad-paper-ideas/codex.lawsConfirmation/LAW_LEDGER.md`) | Later corrections and model-specific claim limits |
| S11 | CA reconstruction and writeback programme (original research-tree path: `../../../preprints/ingressing-minds-v-ruliad-paper-ideas/codex.reconstructionsAndStressTesting/README.md`) | Expression, observability, local writing, and renewal are separate tests |
| S12 | AI-3 learning-geometry dissection (original research-tree path: `../../../preprints/ai-3-ideas/GRAM_DISSECTION_READOUT.md`) | Matched present function with different future learning; bounded mechanism evidence |
| S13 | AI-2 interface-adapter results (original research-tree path: `../../../preprints/ai-2-ideas/README.md`) | Recipient/representation compatibility and repaired body-to-writer translation |
| S14 | AI-8 WSC deterministic entrance (original research-tree path: `../../../preprints/ai-8-new-frontier/DLM2_WSC_V1_FINAL_2026-08-27.md`) | Separate reconstruction histories, common errors, and limited information access |
| S15 | AI-11 research charter (original research-tree path: `../../../preprints/ai-11-rl-frontier/RESEARCH_CHARTER.md`) | Declared boundary, carrier, reader/writer, and cost contracts; design rather than result evidence |
| S16 | AI-4 two-byte memory result (original research-tree path: `../../../preprints/ai-4-ideas/Q31_Q4A_TWO_BYTE_ACTIVE_FOSSIL_RESULT_RECEIPT.md`) | Analytical memory benefit versus full reader/writer observation costs |
| S17 | AI-5 refresh closeout (original research-tree path: `../../../preprints/ai-5-ideas/SCHEDULED_REFRESH_V1O_CLOSEOUT.md`) | Single-episode failure analysis of proposed, refused, and installed refresh operations |
| S18 | [Levin software directory and primary-source review](BETSE_DESIGN_REVIEW.md) | R004: BETSE/Calculion interface and physics lessons, experimental evidence tiers, and other reference candidates; dated code identifiers and external citations retained in the review |
| S19 | H3 reliability confirmation (original research-tree path: `../../../preprints/ingressing-minds-v-ruliad-paper-ideas/levin-cancer-gj-exploration/RELIABILITY_CONFIRMATION_RESULTS.md`) | R005: source-reported finite, externally managed group relay under held-out kicks; recovery provenance and ordinary controls |
| S20 | H4 changing environments (original research-tree path: `../../../preprints/ingressing-minds-v-ruliad-paper-ideas/levin-cancer-gj-exploration/CHANGING_ENVIRONMENT_RESULTS.md`) | R005: source-reported environment-dependent score and assigned-cost tradeoffs, not calibrated fitness or autonomous reproduction |
| S21 | [Bonzanni et al. 2020](https://doi.org/10.1242/bio.048553) and [curated data](../data/biology/bonzanni2020_rptec_v1/README.md) | R007/BIO-001: RPTEC endpoint pilot, recording metadata and unresolved source/uncertainty boundaries |
| S22 | [Costa et al. 1989](https://pmc.ncbi.nlm.nih.gov/articles/PMC1189096/) | R007: primary abstract review of the BETSE oocyte lead; chloride-homeostasis and voltage-clamp compatibility warnings, not a scanned-table reproduction |
| S23 | [Bonzanni source-review attachment](../data/reviews/bio003_2026-09-09/README.md) | R008/BIO-003: hash-verified XML methods and complete one-page Figure S1; no new numerical endpoint extraction |
| S24 | [Pinned BETSE capability sources](BETSE_CAPABILITY_ROADMAP.md#primary-source-baseline) | R009: v1.5.0 overview/configuration, chemistry template, flow, membrane redistribution, ER and source-tree inventory; architectural requirements, not executable parity |
| S25 | [JAX distributed arrays](https://docs.jax.dev/en/latest/sharded-computation.html), [manual parallelism](https://docs.jax.dev/en/latest/notebooks/shard_map.html), [multi-controller execution](https://docs.jax.dev/en/latest/multi_process.html) | R009: candidate array-sharding/collective tools and process-order constraints; no GPU implementation or speed claim |
| S26 | [Pinned BETSE Kv1p5 channel source](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/channels/vg_k.py) and [gate updater](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/channels/channelsabc.py) | R010: continuous activation/inactivation equations, voltage/time units and source-discretization boundary; [SPEC-006](VOLTAGE_GATED_CHANNEL_SPEC.md), no native execution |
| S27 | [Philipson et al. 1991](https://pubmed.ncbi.nlm.nih.gov/1986382/) | R010: source-cited primary abstract, heterologous expression and slow-inactivation lead; no coefficient-level calibration or digitized trace |
| S28 | [Solbrå et al. 2018](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1006510) | R011: diffusion/drift distinction, bulk electroneutral closure and membrane capacitive-current accounting |
| S29 | [Sætra and Mori 2024](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1012114) | R011: compartmental ionic networks, charge-capacitor relations and reference-potential choice |
| S30 | [Mori, Liu and Eisenberg 2011](https://arxiv.org/abs/1101.5193) | R011: energy-structured electrodiffusion/water-flow model; reviewed abstract, not implementation or water-flow validation |
| S31 | [Benedusi et al. 2024](https://epubs.siam.org/doi/10.1137/24M1644717) | R011: KNP-EMI solver abstract and publication metadata; IMEX, mixed finite elements and AMG-preconditioned GMRES, CPU-core rather than GPU evidence |

S01 is manuscript version 2.3, whose stated evidence cutoff is 2026-08-24.
The September exploration is a later programme and should remain identifiable
as a separate source of evidence.

The upstream BITSEY revision reported by the exploration is
`b2cb370aaecbc8299f259bc4251d5396c81f19a6`. Its ignored `upstream/bitsey`
checkout was absent from the local exploration directory at the initial review.
R003 obtained a separate pinned checkout for the completed isolated comparison.
Upstream implementation redistribution terms remain unresolved; no source code
was vendored into Cells. The exploration also records unresolved
paper-table provenance; its successful bounded reruns do not constitute a full
reproduction of the original cancer paper.

## Findings that shape the design

| Reported observation | Consequence for Cells |
| --- | --- |
| Local parent-daughter resemblance can resume while composition continues to drift. | Measure adjacent continuity, episode coherence, and return to an old state separately. |
| F12 requires a break before renewal; higher F12 is not intrinsically better maintenance. | Provide resistance, recovery, duration, and renewal readouts instead of a universal heredity score. |
| Engineered CA and Wagner carriers can be written, transmitted, read, and renewed. | Represent carrier mechanisms explicitly, including their costs, transmission, and disabling controls. |
| Different complete cell states can share an E/M label but differ in commitment. | Preserve primary biochemical state; calculate phenotype labels through observers. |
| Contact history and pulse spacing affect commitment. | Preserve evolving donors, recipients, elapsed time, and delivered flux where available. |
| In H2, a single acquired-state cell can retain an E rewrite yet fail E transmission; matched pairs resist rewriting. | Distinguish exposure-group size, transmission-group size, and recipient context. |
| Ordinary same-state donors can also transmit. | Retain ordinary-state controls when testing acquisition history. |
| Replacement of cell identities in scripted relays does not establish autonomous division or material renewal. | Add growth, partition, resources, contact formation, and ancestry as declared model extensions. |
| Phi-r responses depend on the measurement contract and lack a shared established control gradient. | Treat information measures as optional observers with explicit definitions and simpler comparators. |

The native Levin-derived regulatory model is deterministic. Initial variation,
externally imposed shocks, continuous stochastic chemistry, and inherited kinetic
changes are different model or assay choices. Each must be named when introduced.

The preprint's GARD catalytic matrix and reservoir are fixed environmental
constraints. They should not be relabelled as an assembly-written carrier.
Likewise, a label-level history effect in a deterministic model must reside in
complete state, parameters, structure, or environment. A hypothetical slow memory
variable is an explicit extension, not a default explanation for every effect.

The carrier-threshold hypothesis motivates varying memory capacity, bottleneck
width, disturbance, and horizon while holding base dynamics fixed. The engineered
CA and Wagner results establish sufficiency in their respective models; native
break-and-renewal was observed before those carriers were added.

## R002: broader ideas review and accepted design implications

On 2026-09-07 the user opened the previously deferred strict-eight,
ingressing-minds/Ruliad, and AI branches for design review, then accepted the
recommended refinements. The review covered branch summaries, selected direct
mechanism/follow-up reports, and later audits, including S09-S17. It did not
rerun the experiments, audit every artifact, or establish biological generality.

| Reported evidence or source principle | Cells implication | Limit retained |
| --- | --- | --- |
| S09 finds substantial overlap between correct and alternative form atlases. | Use calibrated, versioned observers and trajectory/challenge signatures; do not require a fixed finite catalogue. | R20's rehoming claim remains unestablished; the identifiability analysis is post-hoc. |
| S12 localises a future-learning difference under matched current function to task-relative geometry. | Allow explicit dynamic responsiveness and test histories with common future challenges. | Development evidence in a minimal learner, not biological heredity or a reason to add hidden state arbitrarily. |
| S11 reports an observable local historical signal without successful tested successor writing. | Separate analyst decoding, biological reading, expression, and writeback. | Information presence does not establish usable or renewable memory. |
| S13 reports fresh-family benefit from an engineered writer-side translation. | Test recipient and representation compatibility; use explicit adapters only where modelled. | A successful supplied translator does not show spontaneous discovery or universal portability. |
| S14 preserves more independent reconstruction paths when shared somatic decisions cannot enter writing. | Permit different communication/writing access and common versus independent disturbance tests. | Deterministic engineered entrance evidence, not confirmation of biological renewal or a universal germline law. |
| S15 explicitly separates public rules, lived state, and passed cargo. | Specify biological boundaries independently of complete restart state. | A research charter is a design source; strict AI erasure is not a cell-division model. |
| S16 reports analytical memory benefits alongside a negative conservative observation-cost ledger. | Count reader/writer sensing, shared machinery, reconstruction, and collateral costs separately from payload. | Designed analytic schedule world; no physical biological experiment. |
| S17 shows that a guard can refuse refresh and an accepted refresh can later cause harm. | Record proposed, rejected, accepted, and installed operations separately. | A single-episode forensic result, not a population-wide refresh law. |

S10 is essential to interpretation: many original laws were narrowed to bounded
claims. L09's triangle formulation is marked refuted as written while a bounded
restoration result is retained; universal timescales and biological conclusions
are not established by those model runs. Cells will test candidate mechanisms
and trade-offs rather than encode the early summaries as constraints.

The consequences are recorded in D008-D009, the architecture contracts, and the
E04/E09-E12 assays. The separate whole-organ, multi-organ, one-cell-first, and
future computational-multiscale requirements come from the user, not from a claim
that these source experiments already demonstrate organ simulation.

## Operational distinctions to retain

- Acquisition: a cue changes a cell or collective.
- Retention: the change persists after the cue is removed.
- Commitment: the state at cue removal leads to a retained outcome, potentially
  before that outcome is visible in a coarse label.
- Transmission: changed carriers causally alter fresh recipients.
- Renewal: new carriers maintain the relevant transmissible organisation.
- Rewriting: changed content replaces earlier content; report its retention and
  onward transmission separately, including rewrites that fail renewal.
- Autonomous renewal: declared growth and turnover rules generate successors
  without an experimenter supplying prepared successful carriers.
- Adaptive benefit: an independently defined environment and performance measure
  show a benefit after accounting for resources and costs.

For fidelity to S01, its GARD F12 definition uses a strict inheritance threshold
`H > 0.9`; equality is a break. It requires a break followed strictly later by
three inherited fissions within twelve fissions. This is a source-specific
measurement contract. Its transfer to tissue data requires a specified observer
and a justified definition of a lineage boundary.

## Questions for Cells

1. Where does durable memory reside: intracellular regulation, communication
   structure, a maintained collective, extracellular conditions, or combinations?
2. How do group size, connectivity, and bottleneck severity alter retention,
   rewriteability, and onward transmission?
3. Can division and turnover maintain a contact-acquired state without scripted
   placement of every successor?
4. When do inherited states help in changing environments, and when does stale
   memory impose a cost?
5. Which reduced state descriptions preserve predictive and intervention behaviour
   across scales?

These are research questions. The initial architecture does not encode desired
answers or treat engineered memory as evidence of its spontaneous origin.

## Working with the continuing exploration

An existing agent continues the Levin-derived research. Cells can check its
documents as work proceeds; no check-in schedule or automatic synchronisation
has been established.

For each substantive check-in, record the date, source version or hashes, completed
findings, unresolved questions, and implications for Cells. Import reviewed model
or assay snapshots with their controls and numerical settings. Preserve earlier
Cells runs under the versions that produced them.

At the initial review, the source overview reported H1/H2 completed and an H3
launch, with H4/H5 still designs. A live H3 completion status was not independently
checked. R005 below subsequently reviews completed H3/H4 reports; the earlier
entries remain historical snapshots. The source programme's execution permissions
and job schedule do not define Cells tasks.

| Check-in | Date | Material reviewed | Cells consequence |
| --- | --- | --- | --- |
| R001 | 2026-09-07 | S01-S08 and selected experiment runners | Initial state/communication/lineage architecture and reference-assay plan |
| R002 | 2026-09-07 | Targeted strict-eight, ingressing/Ruliad, and AI review; key sources S09-S17 | Accepted boundary/access, observer/challenge, compatibility, and full-cost refinements; no Cells runs |
| R003 | 2026-09-08 | Pinned BITSEY GRN/simulator source; exploration starting-point, smoke report, overview, evidence ledger | M1b isolated regulatory implementation and source comparisons; no newly adopted H3 result |
| R004 | 2026-09-08 | External BETSE/software review: primary papers, BETSE v1.5.0, selected Calculion source, related repositories | D018: explicit membrane/bath/charge/energy/preparation contracts; one-cell specification and instantaneous design checks; no upstream or biological rerun |
| R005 | 2026-09-08 | Pinned contact/gating source and native instantaneous probes; memory/pilot adapters; completed H3/H4 result reports | D021/SPEC-002: physical stateful versus source-algebraic gates, explicit charge/units/transport mismatches, and full-state/control/support requirements; no research-lane rerun |

R003 establishes an actual clean checkout of BITSEY revision
`b2cb370aaecbc8299f259bc4251d5396c81f19a6` under Cells' ignored upstream directory.
The source's three-variable isolated regulatory subsystem, simple binding
approximation, scaling and native Euler settings are recorded in
[Isolated regulatory reference](EMT_REFERENCE.md). Native E/M helper runs and
36 derivative probes were captured without modifying source. Cells independently
expresses those equations and verifies them against those captures and independent
CPU solvers; [M1b acceptance](../reports/M1B_ACCEPTANCE.md) is Cells evidence,
not a new exploration-lane PH result. Paper-table mapping, physical-time
correspondence, and upstream implementation redistribution terms remain open.
No continuing-agent experiment was launched, stopped, or modified.

R004 is an external literature/software check-in, not a status update from the
continuing agent. [BETSE design review](BETSE_DESIGN_REVIEW.md) preserves the
reviewed source identifiers, experimental evidence and mismatches, and limits
on reuse. The accepted [one-cell physical contract](BIOELECTRIC_CELL_SPEC.md)
is an independently specified engineering fixture; its parameters and pump law
are not claimed as a source reproduction. The subsequent
[NUM-002 qualification](../reports/NUM002_REFERENCE.md) verifies independent
CPU trajectories and a bounded numerical candidate, not a new source result.
The subsequent [MODEL-003 production acceptance](../reports/MODEL003_ACCEPTANCE.md)
is Cells engineering evidence, not new source or continuing-agent results.
Wider unreviewed preprints remain deferred.

### R005: completed exploration findings and design consequences

This check-in read S19/S20 as **source-reported results**. Cells did not rerun
their independent auditors or simulations, and does not count their checks as
Cells test results. No continuing-agent job was started, stopped, or modified.

S19 reports H3 completion at 2026-09-07 17:50:27 UTC: 39 cases and 79,113 checks.
Five pair families retained their E/M group-level relay through 12 externally
managed handovers, including no-shock and new 10%/25% kick schedules; four finer
numerical cases agreed. Ordinary E/M pairs were also effective. The result is
finite renewal under the supplied protocol, not spontaneous pair formation or
autonomous birth. Its final receipt is composite: 38 original completed cases
plus one recovered case after a time cap. That recovery is not another replicate.

S20 reports H4 completion at 2026-09-08 00:44:54 UTC: 76 cases, 112,544 checks,
four historical reproductions and eight finer-numerical comparisons. Four
policies contrast inheritance plus cue, inheritance only, cue only, and neither.
Assigned state-match scores exclude bootstrap epoch one. Rewriting plus
inheritance averaged 90% versus cue-only 80% in the slow-change world, but tied
cue-only at 80% in rapid changes; in the misleading-cue world it tied the neither
control at 50%. The slow-change advantage came from two cue schedules: one tie
and one 20-point advantage. Paired founder polarities are not independent worlds.
An assigned parent-contact cost of 0.10 removed that mean advantage; this is a
dimensionless policy-cost sensitivity, not measured ATP consumption or fitness.

For Cells, retain complete state/history and phase provenance, independently
scheduled contact/cue controls, ordinary-state baselines, held-out environments,
failed-state continuation, and explicit externally supplied carriers. Record
assigned protocol costs separately from integrated flux/energy and actual
resource depletion. These findings do not require a new special-purpose engine
mechanism. They particularly do not justify inventing gate memory in the
source-compatible model. [The source map](SOURCE_COUPLING_MAP.md) distinguishes
the reviewed ungated memory harness from voltage-gated cancer-isolation cases.

The reviewed exploration log also described an H4b launch. No completed H4b
finding is adopted here, and no live job status is inferred from that handoff.

| R005 reviewed file | SHA-256 |
| --- | --- |
| S19 H3 result document | `3a5abb5a9a9e2560503732697949389a356419a78f57d3287b7c36794b295821` |
| S20 H4 result document | `bc233bcbe7dd3c1d720a62e58f3c4a27ee4fce6b3130e22b98816920b3745ab7` |
| `scripts/run_memory_probe.py` in the exploration | `132db17a953f930d8085d554b0587015c40d60a60fe672d3e68864a4fb5f9e73` |
| `scripts/run_pilot.py` in the exploration | `4d029b5ac660258592475b406401c9db1f8f62b5f8c65642c1f1f678203077d5` |

These hashes identify reviewed documents/adapters, not an archive or an independent
validation of their reported results. The separate Cells-native contact capture
and 709 instantaneous source/physical checks are recorded in
[SPEC-002 evidence](../reports/SPEC002_DESIGN_CHECK.md).

### R006: selected switching protocol review

2026-09-08. Read the completed pilot and memory-probe protocols/results and the
pinned native setup code to choose [E02-SW1](E02_SWITCHING_PROTOCOL.md). This is
a targeted source-protocol review, not new exploration outcomes. No continuing
job, native simulation or source auditor was launched, stopped or modified.
No completed H4b finding or live job status is inferred from a launch handoff.

The pilot reports two-neighbour thresholds near `1.13e-15` E→M and `1.005e-15`
M→E. Its original grouped run timed out; the separately recorded follow-up
completed the missing direction. This motivates a three-cell star and fixed
`2e-15` miRNA transport, not a promise that independent Cells trajectories
will switch. The memory-probe report's stable regulation with continuing K/Cl
drift motivates explicit preparation residuals and nonstationarity reporting.

Native `surround_flip_sims` disables miRNA, retains ionic routes, uses its last
plotting sample and does not freshly reset ions between the two directions.
Its predicate compares all cells' packet rows 4 onward against a prepared donor,
not only phenotype labels. E02-SW1 documents its deliberate fresh preparation,
exact-clock and observer differences. It is not historical threshold replication.
The reusable engineering consequence is fixed-graph composition, not a special
switching term or donor clamp. The current pair cannot represent the third cell.

The [frozen JSON](../configs/reference/e02_switching_protocol_v1.json) records
all four reviewed document hashes, the native fixture/source pin and production
baseline. [Design evidence](../reports/SPEC004_PROTOCOL_CHECK.md) verifies them
read-only. These hashes identify reviewed evidence; they do not independently
validate the source-reported scientific outcomes or archive upstream code.

### R007: first experimental one-cell benchmark review

2026-09-09. Reviewed the primary Costa abstract, BETSE's reported comparison,
and the Bonzanni 2020 article XML, Figures 2/3 and supplementary-file inventory.
Public API access supplied the latter after browser-rendered PMC pages returned
an access challenge; no raw recordings, private data or author correspondence
were obtained. The source figures are retained with attribution and hashes in
the [data card](../data/biology/bonzanni2020_rptec_v1/README.md).

The selected [BIO-001 specification](BIOLOGICAL_BENCHMARK_001.md) records
C4/C5's 10 mM potassium disagreement and uses only C1-C3. Their coarse voltage
readings are endpoint summaries, not a recovery trajectory. Whole-cell recording,
unestablished culture coupling, divalent bath ions and uncertain free internal
ions prevent an automatic match to our isolated synthetic cell. Numerical SEM
remains untranscribed. No fit, simulation or biological success follows from
passing the data-integrity checks. R007/D042 changes the immediate priority;
it neither modifies the continuing exploration nor closes the long E02 gate.

BIO-002 follow-through, D043: the [conditioned endpoint calculation](../reports/BIO002_CONDITIONED_VOLTAGE.md)
fits two effective coefficients to C1/C2 and predicts C3 at -14.59 mV versus
its approximate -18 mV reading. Reading-bound sensitivity is [-18.32, -11.20]
mV, not a confidence interval or biological acceptance test. This is a Cells
calculation from the unchanged R007 data, not a new source finding or a claim
that the production cell matches whole-cell recordings. Uncertainty and
recording-boundary review remain BIO-003's next gate; C3 is not retuned.

### R008: bounded endpoint-pilot closeout

2026-09-09, D044. Rechecked BIO-001's original XML and supplement-package
identities. Read the cell-culture, electrophysiology and statistics sections
and Figure 3 caption; enumerated the package and extracted/visually reviewed
all of Figure S1's one-page PDF. It contains temperature comparisons and optical
signal stability, not C1-C3 numeric means/SEMs or experiment-level grouping.
The methods do not resolve the comparator's fixed-internal, omitted-current
or isolated-cell assumptions. Bounded correction/data searches located no
resolving source, not proof of global absence. No author contact occurred.

The [pilot is closed as descriptive](../reports/BIO003_PILOT_CLOSEOUT.md), with
the original fit/prediction unchanged and biological acceptance unestablished.
No new endpoint, SEM, time constant or physiological mechanism is inferred.
Future model changes informed by C3 require new evaluation data. This evidence
review closes the scoped task without blocking architecture on indefinite data
recovery or erasing the limitations.

### R009: BETSE capability and parallel multiscale architecture

2026-09-09, D045. Revisited BETSE v1.5.0 at commit
`5269a714aa2593ed2a6708c4516289977d8ae1a2`: overview, main configuration,
network template, active flow and membrane redistribution routines, ER structure,
and the pinned source-tree inventory. The [capability roadmap](BETSE_CAPABILITY_ROADMAP.md)
records source locators/hashes and 17 feature families, with current Cells gaps
and qualification steps. Specialized module presence is not evidence that every
option is reachable, correct or biologically validated; no BETSE environment
was installed or executed and no upstream code was vendored into Cells.

Our architectural inference is to expand species/compartment/surface ownership
and provide separate reaction, transport, constraint, geometry and solver
interfaces. The flow source specifically uses Stokes-style/electroosmotic
approximations; it does not supply a general turbulent organ-flow model. Source
parity must match named assumptions and parameters, not implementation accidents.

Official JAX documentation supports considering explicit array sharding and
manual collectives, with compatible collective order across participating
processes. The [execution design](MULTISCALE_EXECUTION_ARCHITECTURE.md) adds our
own tissue-specific ownership, halo/flux, multirate, reduced-state and checkpoint
requirements; JAX does not supply those scientific semantics automatically.
Future GPU claims require measured accuracy and complete runtime/communication
costs. No code, solver, hardware or whole-organ outcome is established by R009.

### R010: first membrane-channel source review

2026-09-09, D049 / SPEC-006. Read the pinned potassium-channel base and `Kv1p5`
rate methods, full channel updater and license; hashes are in the
[frozen panel](../configs/reference/voltage_gated_channel_v1.json). Review of the
cited primary abstract is limited to qualitative experimental context, not a
reconstruction of every fitted rate coefficient. No BETSE environment, upstream
source copy, experiment trace extraction or continuing-exploration job was created.

Our design choice is a K-bound channel with independent activation and
inactivation, not an instantaneous conductance. [Independent checks pass](../reports/SPEC006_DESIGN_CHECK.md)
on analytic prescribed-voltage gate responses and instantaneous ionic coupling.
Different hidden gate states can produce the same current open fraction but
different later responses; this is an engineering state-sufficiency witness,
not a PH or biological-memory result. The two timescales require new coupled
numerical qualification, and a voltage input for a standalone gate does not
supply a whole-cell electrode or change amount-owned charge closure.

### R011: spatial extracellular closure and solver separation

2026-09-11, D059 / SPEC-009. Reviewed the primary KNP paper's theory and
implementation discussion (S28), the compartmental network's charge/gauge
methods (S29), the energy-model abstract (S30), and the scalable KNP-EMI abstract
and publication metadata (S31). Access was via the primary paper pages above;
no upstream code was installed, vendored or executed. No continuing-exploration
job or biological dataset was changed.

Our architectural inference is to use bulk-electroneutral current continuity
with explicit membrane capacitance for the first coarse spatial outside,
reserving Poisson–Nernst–Planck as a different fidelity option. A membrane-free
bulk volume and a binary-salt diffusion-potential witness expose two otherwise
easy modeling mistakes: invented capacitance and independently grounded outside
compartments. The capacitance-component decomposition, log-mean face rule and
data-defined fixture panel in the [new contract](SPATIAL_EXTRACELLULAR_SPEC.md)
are our design, not a claimed reproduction of any paper or BETSE.

The [independent arithmetic result](../reports/SPEC009_DESIGN_CHECK.md) verifies
this bounded discrete closure, not biological plausibility, mesh convergence,
ODE accuracy or accelerator speed. For later GPU work, reserve a coupled sparse
field-solver interface and explicit stage communication. A published CPU scaling
result does not establish Cells GPU scaling or require adopting its software stack.

Numerical follow-through, D060 / [NUM-010](../reports/NUM010_REFERENCE.md): the
separately frozen fourteen-case short-trajectory panel and independent saved-data
audit pass. Binary ambipolar relaxation matches an analytic reduction, and
8/16/32-volume refinement reduces the sealed-line continuum concentration error
to 0.0059 mM. A 0.125 ms explicit step with passing 0.0625 ms refinement survives
the finest grid; seven coarser trials are rejected and two complete but fail
accuracy. These are our synthetic numerical checks, not upstream software
execution, a reproduction of biological measurements or new empirical support
for the Plastic Heredity hypotheses.

D061 / [CORE-010 development integration](SPATIAL_EXTRACELLULAR.md) implements
the same passive equations and ownership in CPU/JAX, with independent comparison
against those frozen trajectories. This is engineering evidence only: there is
no added physiological mechanism, new external experiment, biological confirmation
or BETSE-parity result. Full production artifact/replay acceptance is still open.

Hashes captured for key reviewed documents in R001:

| Source | SHA-256 |
| --- | --- |
| S01 | `c0a80cdcda6373708639a25bfb535a8df979a8b7b820a09f3ff37b78aea686d0` |
| S04 | `8a7e34b9715d0a925d1380050b88d57d5ba17a220ad37d4afab29cd5395aa1d3` |
| S06 | `e3e6a4a13446981ceb84f10c24fc1595f3920fbc5046c2c9503517a862376d04` |
| S07 | `7d51ae0bcc825706c7a75381e6cb2b74a250eed2d64061e9320d201f69483fc4` |

These R001 hashes identify the reviewed contents; they do not archive a copy or
prove the reported results. R002 is a dated document review, not an immutable
archive of the live source programmes. Pin source versions/fixtures before an
executable import. The targeted wider review is complete for this design pass;
unreviewed parts of `../../preprints` remain deferred.
