**Cortical culture learning as a future Cells validation — reviewed 24 October 2026**

Wesley Clawson, Caitlin Grasso, Sydney Palmer, Serena Meng, Nathan Wu, Trevor
Sullivan and Michael Levin, *Goal directed closed-loop training of network bursts
in cortical cultures produces improved performance and error correction over
days*. [bioRxiv v1](https://www.biorxiv.org/content/10.64898/2026.10.15.759184v1),
posted **16 October 2026**, not certified by peer review.

**Add this as a future experimental validation of adaptive tissue dynamics.**
It supplies measured neural behaviour for testing learning, persistence and
recovery, complementing BETSE's bioelectric reference role. It is not a completed
Cells validation or evidence that our present tissue model can learn. The
[validation inventory](SCIENTIFIC_BASIS.md#candidate-resources-for-whole-cells-and-organs)
and [experiment queue](EXPERIMENTS.md#cortical-culture-learning-and-error-recovery)
retain this target. Building and verifying the simulation stack remains the
immediate priority.

**What was measured, and how strongly**

These are wet-lab recordings from dissociated E18 rat cortical cultures on
high-density microelectrode arrays: **10 trained, 6 unstimulated and 6 damaged
cultures**. HAL delivered random electrical stimulation after an incorrectly
directed burst; correct bursts avoided stimulation. Daily baseline, training and
post-training phases each lasted 20 minutes. Learning was principally evaluated
during unstimulated baseline recordings across days.

| Reported result | Evidence boundary to preserve |
| --- | --- |
| Goal-side burst fraction increased within trained cultures (paired p=0.019). | The trained/control contrast was significant for only 23% of the 64 possible control-side assignments; median p=0.18. |
| Error-to-correct transitions improved (9 trained, 6 controls; two-sided p=0.026). | The strongest group comparison: significant under 72% of control-side assignments, median p=0.034. Correct-to-error change was not detected (p=0.43). |
| Gains accumulated mainly between sessions. | Within/across comparison p=0.002; the across-day trained/control comparison was p=0.056. A consolidation mechanism was not measured. |
| Origins shifted relative to peaks; direction diversity showed no detected change. | Origin-versus-peak change p=0.010 within trained cultures; raw origin shift versus controls p=0.26. |
| Damaged cultures kept bursting without a detected learning gain. | Healthy/damaged gain difference p=0.313; significance in one group alone does not establish a group difference. |

Source: [Results, Figures 2–6 and Tables T1–T2](https://www.biorxiv.org/content/10.64898/2026.10.15.759184v1.full.pdf).
Controls were younger and baseline dynamics differed; the performance contrast
did not survive baseline adjustment. There were no yoked stimulation controls.
Damage was accidental peripheral cell loss in a separate preparation. No proposed
memory carrier was directly measured. These limit causal and mechanistic claims.

**How Cells can learn from this**

The useful design lesson is to measure **what the system does, how it leaves an
error, and what changes its future behaviour** separately. A plausible voltage
trace or persistent bursting is insufficient evidence of adaptive function.
Likewise, our membrane-resealing observer measures a return to physical bands;
it does not measure learned burst-to-burst error correction. The paper's damage
comparison must not become a calibration of our synthetic membrane leak/closure
law.

For *Plastic Heredity* and *How Forms Become Reconstructible*, this motivates a
test of histories that leave similar present activity but different subsequent
responses. In a future model we could match baseline burst statistics, apply the
same new challenge, then selectively restore, freeze or exchange candidate slow
states. Compare acquisition, stimulus-free persistence, recovery and relearning.
Those are proposed causal experiments. Transmission to another tissue, rebuilding
a carrier and maintaining behaviour through turnover would need additional tests;
within-culture retention alone cannot establish heredity or reconstruction.

For polycomputing, separately monitor task improvement and other tissue functions
under the same intervention. A second analyst readout is not an independently
embodied task. Synaptic plasticity, intrinsic excitability, calcium regulation,
glial state and extracellular changes are competing model hypotheses, not
mechanisms identified by this paper. Start with explicit alternatives and
ablations rather than inserting a rule that directly moves bursts toward a
desired label.

**Proposed validation panel**

| Target | Comparison to implement | Controls and interpretation |
| --- | --- | --- |
| Observation and baseline dynamics | Reconstruct recorded burst detection, origin/peak positions, size, duration, intervals and spatial distributions before fitting learning. | Match culture age, preparation, electrode selection and recording noise. Compare synthetic electrode signals with recordings, not intracellular voltage directly. |
| Acquisition and persistence | Compare each culture's pre/post trajectory, first/last baseline and between-session changes; hold out entire cultures and later sessions. | Retain unstimulated, same-age preparations. Fit neither learning laws nor thresholds on held-out outcomes. |
| Error recovery | Estimate both conditional transition probabilities, time-weighted occupancy and dwell-time distributions. | Preserve transition counts and undefined denominators. A per-burst probability is not a recovery rate in seconds; occupancy and recovery are related, not independent replications. |
| Spatial specificity | Measure origin displacement and peak displacement separately, with direction diversity and initially aligned/opposed cultures. | Preserve the source's origin-minus-peak classifier; do not substitute a fixed left half of the dish. Test mirrored goals separately as a new prediction. |
| Feedback dependence | Compare closed-loop training with replay of the same pulses into a matched independent culture, randomized contingency, and no stimulation. | These are proposed stronger controls. Freeze the external controller; preserve timing, stimulus exposure and controller state so apparent learning cannot be supplied by a changing decoder. |
| Integrity and learning capacity | Compare matched spontaneous activity with future learning and recovery under explicit structural or plasticity perturbations. | Keep damage mechanisms distinct; quantify uncertainty before claiming loss or preservation of capacity. Bursting alone is not a sufficient health metric. |

The first biological comparison should be the complete recovery-transition
panel alongside ordinary activity and performance controls. Reproducing a
headline percentage or a p-value alone is not acceptance. Freeze effect-size
and uncertainty comparisons only after the data and observation process have
been curated; report model failures and competing explanations.

**Prerequisites and execution**

1. **Recover the source data and exact analysis.** Obtain per-culture/per-day
   burst tables, stimulation logs, electrode maps, exclusions, preparation/age
   metadata and the HAL/analysis revision. Reproduce the paper's summaries
   before fitting Cells. Keep the 64 alternative labels of six controls as
   sensitivity checks, not 64 independent controls. Resolve panel-specific
   inclusion rules, including Figure 6B's extra low-activity culture. Use
   culture-level uncertainty with preparation dependence retained; individual
   bursts are repeated measurements.
2. **Match observation and intervention semantics.** The
   [Methods](https://www.biorxiv.org/content/10.64898/2026.10.15.759184v1.full.pdf)
   distinguish online detection/blanking from offline extraction. Pin those
   windows and masks separately, including ties, missing recordings and eligible
   transitions. Match when a burst classification becomes available: a controller
   cannot use a future peak. Electrode stimulation voltage needs a physical
   coupling model; it is not a membrane-voltage clamp. Benchmark the observation
   pipeline on small known-answer traces first.
3. **Build the missing substrate.** A suitable neural-network model needs
   synaptic transmission, heterogeneous connectivity, spontaneous activity,
   calibrated stimulation/measurement and explicitly owned slow plasticity
   states. Existing channels, calcium, tissue fields and checkpoint machinery
   are ingredients, not a qualified cortical culture. Link fast electrical and
   slower adaptive dynamics through the
   [multiscale execution design](MULTISCALE_EXECUTION_ARCHITECTURE.md); reductions
   and skipped quiet intervals must preserve learning-relevant state and
   fluctuations. Millisecond qualification does not establish day-long accuracy.
4. **Verify execution, then evaluate biology.** Preserve tissue, plasticity,
   detector, controller and random-generator state across every session and
   checkpoint. Require independent short references, timestep/observation
   sensitivity and CPU/L4 agreement before a long study. Batch independent
   cultures and matched controls across GPUs; budget all arms, retain GPU-busy
   and SM-active telemetry, and balance measured costs for future Jupiter nodes.
   Numerical checks and device replays remain separate from biological cases.

**Source access and remaining gaps**

This review read the v1 full text and its embedded supplementary Figures S1–S5
and Tables T1–T2. It did not reanalyse raw recordings. The manuscript calls HAL
open source, but no paper-linked data deposit or exact code release was located
in the inspected text or bounded searches. A related
[HALnalysis repository](https://github.com/evan-kolberg/HALnalysis) is only a lead;
its correspondence to these cohorts and this analysis was not established.
Do not silently substitute it for the paper's source release. Data access and
provenance therefore remain prerequisites for a quantitative benchmark.

The official PDF, HTML, metadata and hashes are retained locally under
`/mnt/workspaces/Cells/paper-reviews/clawson-hal-20261024/`; the
[review record](/mnt/workspaces/Cells/paper-reviews/clawson-hal-20261024/review.json)
identifies source scope and documentation checks. The PDF SHA-256 is
`7e0b3b13e12240ecac9863a33cb1aac8cabbfaa1c33cd3b5019d67e0b48a0d74`.
These local source copies are not bundled in the repository. No simulation,
parameter fit or new validation result is produced by this review.
