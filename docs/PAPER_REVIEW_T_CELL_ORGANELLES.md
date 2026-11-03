**T cell organelle coordination and Cells test planning — reviewed 3 November 2026**

Akaash Kumar, Jane C. Stinchcombe and Gillian M. Griffiths, *Systems-level
imaging reveals assembly and synaptic delivery of a multi-organelle ensemble
during T cell killing*. [bioRxiv v1](https://www.biorxiv.org/content/10.64898/2026.10.30.763224v1),
posted **2 November 2026**, not certified by peer review; CC BY 4.0.
[Main PDF and methods](https://www.biorxiv.org/content/10.64898/2026.10.30.763224v1.full.pdf).

**Use this as a future benchmark for coordinated intracellular behaviour.**
Its strongest lesson for Cells is to test chemical activation, spatial assembly
and directed delivery separately. Matching bulk calcium or a final organelle
position cannot establish the whole response. Basic BETSE parity remains the
immediate milestone; these notes add no requirement to repair the known
flux-inverse defect or build a T-cell model before the demonstration.

## Findings and evidence limits

The experiments use primary mouse OT-I cytotoxic T lymphocytes and
OVA-pulsed EL4 targets. Fixed multispectral Airyscan imaging, live volumetric
imaging and electron tomography provide complementary spatial and temporal
evidence. The authors call the coordinated response COMET.

| Finding | Interpretation for testing |
| --- | --- |
| Early perinuclear ER/nuclear polarization precedes distal organelle clustering and delivery around the nucleus to the synapse. ER first arrival is near 100 s; compaction develops from roughly 120 s. | Compare event order and distributions, not a hard-coded three-state timer. A small first-arriving volume differs from arrival of the whole ensemble. Figure 3; Results, lines 254–323. |
| Contact trajectories change selectively: Golgi–lysosome contact increases strongly, while some ER-associated contacts decrease. Some contacts form away from the synapse. | Match pair-specific time courses and location, not just total contact or a final packed configuration. Common motion alone does not establish persistent binding. Figure 4; lines 324–384. |
| Thapsigargin recruits mitochondria and lysosomes toward the centrosome without reproducing directed relocation toward the cell front. | This supports a separable assembly response. It does not isolate calcium from every consequence of ER-pump inhibition, prove necessity, or establish the targeting mechanism. Figure 5e–h; lines 428–447. |
| ER G-CEPIA1er fluorescence falls and partially recovers before/during clustering. | It is uncalibrated relative fluorescence, with no photobleaching correction. A 50% fluorescence decrease must not become a 50% loss of ER calcium in our model. Figure 5a–b; Methods, lines 890–905. |

Figures 3–4 summarize **6 cells from 3 independent experiments**. The
thapsigargin comparison uses **5 cells per condition from 3 experiments**,
averaging organelle distances within each cell before a two-sided unpaired
Welch test. It is not five paired before/after trajectories; the illustrated
before/after cell is separate from that quantitative comparison. Methods give
a 5–10 minute measurement window, while Figure 5's legend says 6 minutes;
recover the actual timestamps before reproduction. The three distance
comparisons report p=0.0456, 0.0407 and 0.0117. Matching these p-values is not a
simulation acceptance criterion. Preserve the experiment/mouse hierarchy and
identify cells reused across panels; multiple endpoints on the same cells are
not independent replications.

Optical masks define proximity at **120 nm for Airyscan and 250 nm for
spinning-disk data**. Electron tomography shows selected membrane appositions
below 30 nm; it does not certify every optical contact in every live frame.
MAPPER marks close ER–plasma-membrane apposition, not an active STIM1–ORAI1
complex or calcium current. Preserve these distinctions when converting images
into model edges (Figure 2; Methods, lines 836–861; Discussion, lines 499–521).

The authors leave molecular contact-site perturbations for future work. Faster
response to a second target and filtering of weak target engagements are
discussion predictions, not demonstrated outcomes (lines 522–534). They could
become later priming tests, but do not establish inherited or reconstructed
behaviour.

## Proposed observation tests

These are known-answer tests to implement for a future image/trajectory
observer, not new simulation passes. Freeze the authors' script and segmentation
settings before reproducing their metrics: details such as the contact-distance
boundary convention and quantile interpolation still need the code.

| Proposed test | Definition and failure cases |
| --- | --- |
| Physical geometry and masking | Use 3D Euclidean distances with all voxel spacings in physical units. Test anisotropic voxels, translation, matched axis/spacing permutations, target exclusion and an absent synapse. A maximum-intensity projection is not a 3D distance measurement. Do not fabricate a synapse when the masks do not overlap. |
| Directed and symmetric contact measures | The paper uses `f(A→B) = count(A ∩ N_d(B)) / count(A)` and `V_AB = [count(A ∩ N_d(B)) + count(B ∩ N_d(A))] × voxel_volume`. Require `V_AB = V_BA`, but not equal directed fractions. Known-overlap fixtures must retain both contributions: this is not a union volume or membrane area. Empty denominators need an explicit undefined result. Methods, lines 846–868. |
| Contact normalization | Preserve raw `V_AB`, then the per-cell ratio `V_AB(t)/V_AB(0)`. One means the initial level, not zero contact. An absent baseline remains undefined; do not add an epsilon. Within-pair time z-scores cannot rank absolute abundance across pairs, and constant trajectories need explicit handling. Methods, lines 869–881. |
| First arrival and censoring | Count segmented volume at distance **≤500 nm** from the current synaptic mask. Arrival is the first sampled time at which this volume **exceeds 0.2 µm³**. Test exact-threshold versus just-above volumes, fragments, missing frames and non-arrivals. Keep non-arrivals censored, not zero or the movie end. Preserve cadence and interval uncertainty. Methods, lines 824–835. |
| Clustering versus targeting | Reproduce the IQR of voxel distances from each organelle mask's **own centroid**. Separately measure distance to the centrosome and synapse. Translation of a compact object preserves IQR while changing those distances. A thin shell can have small radial IQR without central concentration; include that counterexample and retain radial distributions. Methods, lines 818–823 and 919–927. |
| Imaging and reconstruction | Forward-render known independent and associated objects through a declared PSF, registration error, mixing matrix and photon noise. Check false contacts, crosstalk and event order after reconstruction. Challenge matrix/PSF mismatch and brightness variation as well as the paper's matched forward/unmixing simulation. Preserve separate microscope pipelines; the conventional MAPPER/actin and G-CEPIA1er recordings do not use multispectral reconstruction. Methods, lines 673–691 and 732–785. |

Save masks/tracks, physical spacings, acquisition times, thresholds, cell and
experiment identities, denominators and failure flags with the metrics. Keep
time zero at first target contact, which is not an independent measurement of
TCR activation. Realigning all traces to successful docking would conceal
timing errors and exclude unsuccessful encounters. Retain total organelle
volume alongside first arrival: the fixed volume threshold can favor larger
compartments and does not measure docking.

## Proposed mechanistic comparison

A future model needs separate chemical and spatial state: cytosol/ER calcium
and buffers; cell, nucleus and synapse geometry; a centrosome; and independently
tracked organelle compartments. Motion and coupling require explicit laws.
Do not encode the reported stage sequence as the mechanism and then count its
reproduction as a prediction.

| Comparison | Outcome and interpretation |
| --- | --- |
| Target engagement versus matched migration | Compare ER approach, clustering, centroid motion, contact trajectories and arrival-time spread. Secretion and killing require a separate functional model; location alone cannot establish them. |
| ER-pump perturbation versus vehicle without a target | Compare clustering and centrosome distances separately from directed relocation. The paper uses 0.6 µM thapsigargin and 0.06% DMSO; these exposures are not direct settings for a synthetic pump-availability parameter. |
| Assembly coupling disabled versus directional coupling disabled | Test separate loss of clustering and delivery under matched initial state/stimulus. These are our proposed ablations, not controls established by the paper. |
| Independent cargo motion or passive crowding versus coupled assembly | Compare joint arrival distributions, relative motion, pair-specific contacts and distance–time maps under matched occupancy and shape. These are competing-model/null tests; all-contact increases alone are insufficient. |

Different pairwise contact changes alone do not rule out geometric compaction:
fixed distance thresholds can respond nonlinearly to different starting
separations. Retain organelle identities, contact dwell/reformation and relative
velocities after removing whole-cell motion. For calcium causality, a later
experimental panel should distinguish ER-store depletion from cytosolic calcium
elevation and extracellular influx, while measuring viability, motility and
function. Those stronger interventions are proposed work, not paper results.

Keep conservation independent of the spatial score: calcium moves between owned
stores, internal transfer does not create plasma charge, and a proximity edge
cannot itself create ion flux or ATP. Motors, remodelling and energy-dependent
contacts need declared energy sources and exchange laws. The paper does not
supply universal rate constants for them. Include timestep/observation
refinement and split-run restart checks so sampling cannot manufacture event
ordering.

## Fit with the current checkout

Cells has useful chemical/accounting building blocks, but these are not a
spatial CTL model:

- [Resolved calcium tests](../tests/unit/test_surface_calcium.py) cover internal
  chemistry/charge ownership, independent stage rates, refinement and restart.
- [Finite-energy tests](../tests/unit/test_surface_calcium_energy.py) cover owned
  fuel, pump coupling and explicit regeneration.
- [Mitochondrial composition](../src/cells/models/surface_calcium_energy_mitochondria.py)
  and its [tests](../tests/unit/test_surface_calcium_energy_mitochondria.py) retain
  separate inventories, charge/countercharge, controls and checkpoints. The
  [compartment definition](../src/cells/core/surface_calcium_energy_mitochondria_spec.py)
  has amounts, area, volume and diffusivity, but no organelle position,
  centrosome or trafficking law. Passive transport is not a calibrated
  reproduction of these CTLs' calcium mechanism.

Reuse these accounting contracts where appropriate. Do not reinterpret a
whole-cell mitochondrial compartment, tissue mesh or electrical gap junction as
an intracellular contact graph. Current qualification status remains in
[PROGRESS.md](../PROGRESS.md).

## Data and next steps

The paper makes data/code available **on reasonable request**, rather than
linking a reproducible archive (Methods, lines 934–936). Before setting numerical
acceptance bands, obtain original movies/timestamps, per-cell/experiment
metadata, voxel sizes/transforms, single-label controls, mixing matrices,
segmentation training/settings, masks/tracks, analysis scripts and exclusions.
Resolve treatment timing, reporter calibration/bleaching limitations, and which
panels are representative rather than population summaries. Supplementary
Table 1, figures and videos remain to be retrieved. Check those materials for
antigen-negative encounters, illumination/reporter-matched killing controls,
selection rules and blinded analysis; these are not established by the supplied
main text.

Hold out entire independent experiments where possible, rather than frames or
organelles from cells used in fitting. Retain cell trajectories and
experiment-level uncertainty: frames, voxels and organelles are repeated
measurements. Compare effect sizes and distributions rather than headline
p-values. The small samples do not justify narrow tolerances around approximate
figure values.

**First follow-up after the BETSE demonstration:** curate data/code and build
one observer test suite covering geometry, contact normalization, arrival and
clustering. A later coherent extension can add one cell's spatial organelle
dynamics and the perturbation panel above. This review adds notes only: no model
changes, test execution, fitting or scientific acceptance.

Review provenance: the downloaded main PDF contains 16 physical pages with
Figures 1–5, methods and references; its printed denominator is 28.
Supplementary material and raw data were not reviewed. The
[local source record](/mnt/workspaces/Cells/preprint-2026-10-30-763224-v1-review-20261103-01/review-inputs.json)
retains the exact v1 PDF/metadata hashes and consulted code files.
