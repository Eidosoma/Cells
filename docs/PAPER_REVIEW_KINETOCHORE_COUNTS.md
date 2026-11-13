**Absolute kinetochore protein copy numbers by FCS-calibrated counting, and what
Cells can take from it — reviewed 13 November 2026**

Yasuhiro Hirano, Yusuke Takenoshita, Akira Kitamura, Toru Hirota and Tatsuo
Fukagawa, *Quantitative measurements of kinetochore protein copy numbers via
FCS-calibrated molecular counting*, *J. Cell Biol.* **226**(1): e202603185,
published online 11 November 2026 (collection date 4 January 2027), received
27 March, accepted 15 October 2026. **CC BY 4.0, open access.**
[Article](https://doi.org/10.1083/jcb.202603185),
[open-access full text](https://europepmc.org/articles/PMC13753873) (PMC13753873,
PMID 43012740). Osaka, JFCR Tokyo, Ochanomizu and Hokkaido. The authors declare
no competing interests, and JCB publishes the review history with the paper.

**Cells has no mitosis, chromosome, spindle or kinetochore model, and the
division stages S2–S5 are the physiology of cleavage — membrane insertion, the
cleft lumen and partition — not chromosome segregation. No gate in the current
plan covers this paper's subject, and it supplies no parameter for any qualified
model.** Three things in it are still worth having on file. First, it is a clean
worked example of the one datum the [closed molecular-to-physiology
loop](CURRENT_PLAN.md#gate-a-closed-molecular-to-physiology-loop) demands and
almost nothing in the literature supplies: **absolute copies of a functional unit
in a living cell, paired with a functional threshold** below which the cell fails.
Second, it carries a modelling constraint that would **falsify a naive mass-action
occupancy law** — binding sites stay unoccupied in the wild type although the free
pool is an order of magnitude larger than the bound pool. Third, as a template for
how the [protein catalogue](PROTEIN_CATALOGUE_PLAN.md) should record abundance
evidence: species, cell type, cell-cycle state, drug condition, temperature,
method and uncertainty, all of which change the number. Replication is covered
below; there is little to replicate, because the data are available only on
request.

## What the paper shows

The method is **FCS-calibrated molecular counting**, which the authors adopt
because kinetochore proteins barely move, so conventional fluorescence correlation
spectroscopy photobleaches them and its autocorrelation fit becomes unreliable.
The calibration is indirect and that is the point of it: HeLa cells transiently
expressing free EGFP or mScarlet are **mixed into the same dish and imaged in the
same field and focal plane** as chicken DT40 cells whose kinetochore protein has
been replaced, at its native promoter, with a fluorescent fusion. FCS in the HeLa
cells gives an absolute molecular number in the confocal volume; regressing that
against the image intensity at the measured point gives one conversion factor,
which converts voxel intensities in the DT40 image into copies per voxel; Imaris
segments each kinetochore and sums it. Linear regression over six independent
EGFP experiments gave R² = 0.9711, FCS signal-to-noise exceeded 25, and the
standard curves from HeLa and DT40 cells did not differ significantly.

**The measured copy numbers**, per mitotic kinetochore, as the mean of
per-experiment medians ± SEM over three to six independent experiments with at
least five cells each:

| Protein (complex) | Wild type | CENP-CΔ73 (no Mis12C site on CENP-C) | CENP-TΔ161–216 (no Mis12C site on CENP-T) |
| --- | --- | --- | --- |
| CENP-C (CCAN) | 25.8 ± 3.0 | — | — |
| CENP-T (CCAN) | 14.2 ± 1.8 | unchanged (intensity, Fig. S3 B) | — |
| CENP-N (CCAN) | 17.6 ± 2.6 | — | — |
| CENP-H (CCAN) | 16.5 ± 2.2 | — | — |
| CENP-O (CCAN) | 13.5 ± 1.3 | — | — |
| Dsn1 (Mis12C) | 22.4 ± 1.4 | 15.4 ± 1.3 | 26.8 ± 1.9 |
| Nuf2 (Ndc80C) | 35.0 ± 0.8 | 33.3 ± 4.4 | 39.6 ± 2.7 |

So the CCAN is roughly 1:1 across components at about 14–18 copies, **except
CENP-C at about twice that**, which reproduces two earlier studies by other
methods. The outer-kinetochore result is the paper's claim: removing the Mis12C
binding site from CENP-C drops Dsn1 by about 7 copies, removing it from CENP-T
changes Dsn1 not at all, and **Ndc80C is held at or above its wild-type level in
both mutants**, so the two loading routes are redundant. The double mutant is
lethal in earlier work, which the authors combine with these counts to argue that
roughly 15 Mis12C and more than 30 Ndc80C per kinetochore are what a functional
kinetochore needs. Unexpectedly, CENP-TΔ161–216 showed no growth or mitotic-index
defect.

**The two-pool measurement** is the part most transferable to modelling. By
conventional FCS in the mitotic cytosol, free EGFP-Dsn1 is 18.6 ± 0.4 nM and free
Nuf2-EGFP 68.6 ± 18.6 nM (11–13 measurements, two experiments), and FCCS shows the
two are mostly **not** in complex in the cytosol. With mitotic DT40 cell volumes of
636–2,208 µm³ (n = 18), that is of order 10⁴–10⁵ free molecules per cell, against
about 3,520 Dsn1 and 5,280 Nuf2 bound across roughly 160 kinetochores — **the
bound pool is an order of magnitude smaller than the free pool**, and the free
concentrations do not differ between wild type and either mutant.

**Measured versus inferred.** The distinction matters because the paper's
headline architecture is the inferred part.

| Measured | Inferred or modelled |
| --- | --- |
| Copies per kinetochore for the seven proteins above; free cytosolic concentrations; the FCCS cross-correlation; mitotic cell volumes; conversion factors and their regressions; the EGFP/mScarlet brightness and maturation comparisons; expression-level validation by western blot; growth curves and mitotic index of the CENP-TΔ161–216 strain; the fall in kinetochore Dsn1 under Aurora B inhibition with Nuf2 unchanged | **Which binding site each molecule occupies.** The occupancy ranges — Dsn1 at 0–15 on CENP-T and 7–26 on CENP-C, Nuf2 at about 13–33 on CENP-T and 2–26 on CENP-C — are bounds derived from differences between genotypes plus assumed stoichiometry (one Mis12C per Dsn1, one Ndc80C per Nuf2, two Ndc80C sites on CENP-T and one on CENP-C). The ~36 Ndc80C "prediction" is arithmetic from the measured counts, not an independent model. The number of molecules bound to CENP-T versus CENP-C in the wild type is explicitly stated to be beyond the method. The preferential loading onto CENP-T rests on earlier mutants. The "platform effect" of clustered Ndc80C and the shell–core interpretation of CENP-C's excess are offered as speculation. The ~8 Ndc80C per microtubule combines these counts with a microtubule number from a 2009 paper |

**Limits, as the authors state them and as we read them.**

- **Drug-arrested metaphase, at the wrong temperature.** Cells were arrested with
  nocodazole for 3 h, released into MG132, and measured at **25 °C**, having been
  shifted from DT40's usual 38.5 °C to 37 °C for at least two days beforehand so
  that EGFP maturation matched the HeLa standard. Each of those is defensible for
  the measurement and each moves it away from an unperturbed mitosis. Interphase
  was not measurable at all: kinetochores cluster and sister kinetochores are
  unresolvable.
- **Absolute numbers remain method-dependent.** They are somewhat lower than the
  same group's 2010 values; the authors attribute the difference to promoters
  (CMV then, native now) and to GFP-variant brightness. The stoichiometry is the
  robust part, not the absolute scale.
- **Fluorescent-protein artefacts are bounded, not eliminated.** EGFP brightness
  was temperature-dependent while mScarlet's was not, and an mScarlet-EGFP fusion
  read **1.2× more EGFP than mScarlet**, implying a dark mScarlet fraction that
  must be carried as a correction when colours are compared. Red channels needed
  photobleach detrending before fitting.
- **Kinetochore-to-kinetochore variation is substantial** and is reported as a
  real biological spread, from differing centromere sizes, with segmentation
  limits acknowledged. The headline numbers are means of per-experiment medians
  with SEM, which hide that distribution; the distribution is the more
  informative object.
- **Small replicate counts.** Three to six experiments per protein, and only two
  for the cytosolic concentrations. Normality was assumed and not tested.
- **One species, one line.** Chicken DT40, about 80 chromosomes. The paper itself
  cites 244 Ndc80C per human kinetochore, so these counts do not transfer across
  vertebrates even by stoichiometry.
- **No public data and no code.** "All data from this article are available from
  the corresponding author upon request." The only machine-readable extras are
  source-data files for three western-blot supplementary figures and two tables
  of strains and plasmids.

## Relevance to Cells, layer by layer

| Cells layer | Bearing | Why |
| --- | --- | --- |
| The protein catalogue | **Genuine, as a template and a standard** | The [catalogue](PROTEIN_CATALOGUE_PLAN.md) today records identity, products, assembly stoichiometry, coefficient provenance and an evidence status for 49 functional units; **abundance is not one of its fields**, and it lives in state on the functional-unit population row. This paper is a model of how an abundance record should read: copies per assembled structure, in a named species, cell type, cycle state, drug condition and temperature, by a named method with its uncertainty and its known artefacts. A kinetochore will not become one of our functional units, so the value is the standard, not the entry |
| The functional-unit population row and the closed molecular-to-physiology loop | **One reusable constraint, and a rare paired datum** | The [gate](CURRENT_PLAN.md#gate-a-closed-molecular-to-physiology-loop) asks for "a quantitative abundance-to-function relation"; this paper has one in the form a model can use — about 15 Mis12C and more than 30 Ndc80C per kinetochore, with the double mutant lethal. More useful still is the negative constraint: **a large free pool does not fill the available sites**. In the wild type, free Dsn1 and Nuf2 outnumber bound ones tenfold and sites on CENP-C or CENP-T are nonetheless left empty, while in either single mutant the remaining sites fill completely. A simple mass-action occupancy law over a finite site population would predict saturation in all three states and would be falsified here; whatever occupancy law Cells eventually writes for junction channels or pumps needs a mechanism for sites that are present but inaccessible |
| Division, stages S2–S5 (membrane insertion, cleft lumen, partition) | **Disjoint** | S2–S5 model the physiology and accounting of cleavage in the Xenopus egg; this paper is the chromosome-segregation machinery, which Cells does not represent at all. A copy number per kinetochore constrains nothing in membrane insertion, lumen filling or inventory partition. The [endogenous lifecycle](CURRENT_PLAN.md#gate-lifecycle-operators) (milestone 2) would one day need a mitosis model, and this would be one quantitative anchor for it, but building toward that from this paper alone is exactly what [D144](DECISIONS.md#d144-qualify-the-simulator-for-many-uses-not-one-experiment) forbids |
| Bioelectric layer (`resolved_pump_tissue@3`, channels, pumps, gap junctions and the formation law) | **None** | No voltage, current, conductance or junction measurement. The one structural parallel — a finite population of junction channels filled from a pool over time — is the occupancy constraint above, not a parameter |
| Water and volume | **None, beyond a scale reference** | The mitotic DT40 volumes (636–2,208 µm³, n = 18, by Imaris surface reconstruction) are a measured volume range for a different organism and cell type, recorded here for context only. Not a calibration target for `resolved_pump_water@1/@2` |
| The composite model and its operators | **No new operator today** | A site-occupancy operator is a candidate (ranked below), and it would belong to the functional-unit population row with the usual ownership and combination rules. Nothing in the paper changes the entity table |
| Mechanics (MG1 vertex model) | **None** | Kinetochore–microtubule force transmission is intracellular mechanics at the piconewton scale; MG1 is passive vertex mechanics of a cell sheet. The "platform effect" is a speculation about clustering under pulling forces, not a mechanical measurement |
| The planned gene-regulation layer | **None** | No transcription, no regulation, no expression time course. The strains replace proteins at native promoters precisely to keep expression constant |

**For the two preprints**, the bearing is slight and worth stating so plainly.
The centromere is the textbook case of organisation inherited through a mark
rather than a sequence — specified by the CENP-A histone variant, as the paper's
introduction notes — and a kinetochore is rebuilt each cycle from a free pool onto
that mark, which is a structural analogue of the question
[*Plastic Heredity*](https://doi.org/10.5281/zenodo.22143269) asks about carriers
and renewal. But this paper measures copy numbers in a single drug-arrested
metaphase state; it follows no cell through a cycle, tests no inheritance and
perturbs no mark, so it is context and not evidence. For
[*How Patterns Return*](https://doi.org/10.5281/zenodo.23327869) there is one
honest resonance: the same function is maintained at the same level through two
different underlying configurations, since Ndc80C stays above 30 copies whether it
arrives via CENP-T or via CENP-C. That is redundancy measured at the molecular
scale, and it should not be stretched into a claim about pattern or
reconstruction.

## What replicating it would mean

The user's framing is a "paper replication backlog", so it is worth separating
what could be replicated from what could not.

- **Wet-lab replication is out of scope.** The measurement is FCS on living DT40
  cells with CRISPR-edited fluorescent fusions. Cells is a simulator.
- **Data reproduction is not possible as the paper stands.** There is no deposit
  and no accession: data are available from the corresponding author on request,
  and the public machine-readable material is three western-blot source-data files
  and two strain and plasmid tables. Re-deriving the numbers from the figures
  would not be a replication, and requesting data from the authors is a decision
  for the user, not something to do unprompted.
- **Model reproduction is a few lines of arithmetic, not a simulation.** The
  paper's "model" is an architecture cartoon plus occupancy bounds obtained by
  subtracting genotypes. Reproducing it would run no Cells engine model, so it is
  tooling and needs the user's approval per paper
  ([D138](DECISIONS.md#d138-mg1-start-and-the-paper-backlog)); the lead's
  judgement is that it does not earn a slot, because the arithmetic is already
  transparent in the text and we would be checking subtraction.
- **What could be replicated inside Cells, eventually, is the constraint and not
  the paper:** a general site-occupancy model, fitted to the wild-type counts and
  asked to predict the two mutants' Dsn1 and Nuf2 counts. That is six measured
  numbers across three genotypes — a small but real held-out test, and the
  interesting outcome is the likely failure of the naive law, which is the finding
  worth carrying forward.

## What Cells could test, ranked against the current plan

| Rank | Candidate | Engine features needed | Gate | Judgement |
| --- | --- | --- | --- | --- |
| 1 | **Record the abundance-evidence standard** this paper exemplifies, and apply it when the catalogue gains an abundance field: copies per assembled structure with species, cell type, cycle state, condition, temperature, method, uncertainty and known fluorophore artefacts | None. Catalogue metadata only, and the catalogue does not change the physics | Closed molecular-to-physiology loop, via the catalogue | **Cheap and worth doing** when catalogue stage 3 starts. It is a documentation standard, not a model |
| 2 | **Carry the non-saturating occupancy constraint** into the design of any future site-occupancy law (junction channels, pump or channel populations): sites can be present, physically available by stoichiometry, and still unfilled against a tenfold larger free pool | A site-occupancy operator does not exist; it would need a free pool, a finite declared site population, an occupancy and exchange law, and a mechanism for inaccessible sites. Design first (D142), sourced from the literature (D136) | Closed molecular-to-physiology loop; it would serve the junction-channel population named as the provisional molecular-loop unit in D145 | **Log the constraint now, build nothing.** This paper is one of several cases such an operator would have to satisfy, and must not be the reason it is built (D144) |
| 3 | A held-out occupancy test against this paper's three genotypes | As rank 2, plus the kinetochore-specific site topology, which is not a general Cells entity | Closed molecular-to-physiology loop | **Not recommended as a target.** It would need kinetochore-specific structure in the engine to score six numbers from one species in one arrested state |
| 4 | Anything involving mitosis, chromosomes, spindle or segregation | A mitosis model: chromosomes, a spindle, attachment, checkpoint, force generation | Lifecycle operators, endogenous lifecycle (milestone 2), far out | **Park.** Not in the plan, not justified by this paper, and S2–S5 do not depend on it |

Against the live queue — the composite landing, the plan-validation fix, division
S4–S5, Cortés-Poza Phase 1, the gene-regulation layer — **everything here ranks
below everything there.** Nothing in this review competes for a slot; items 1 and
2 are a documentation standard and a recorded constraint.

## What not to do

- **Do not add a kinetochore, chromosome, spindle or mitosis model to
  `src/cells`** on the strength of this paper (D136, D144). It is one species, one
  cell line, one arrested state.
- **Do not reproduce the paper's own analysis or architecture model** without the
  user's approval for this paper (D138). It runs no engine model, so it is
  tooling, and a milestone that runs none needs explicit approval (AGENTS.md).
- **Do not request the data from the authors** unless the user asks, and keep the
  user's name, project and contact details out of any outside request either way.
- **Do not treat these counts as transferable parameters.** They are chicken DT40
  at 25 °C under nocodazole-release and MG132 arrest, with fluorescent fusions and
  a 1.2× green-versus-red maturation discrepancy; the paper's own human comparison
  differs by nearly an order of magnitude.
- **Do not quote the occupancy ranges as measurements.** They are bounds from
  genotype differences plus assumed stoichiometry, and the authors say the
  wild-type split is beyond the method.
- **Do not mistake "absolute" for "exact".** The method is theory-grounded, which
  removes the external standard, not the biology and photophysics around it; the
  authors' own earlier numbers differ.
- CC BY 4.0 permits reuse with attribution, so this review may quote and cite
  freely; even so it paraphrases and reproduces no figure.

## Open questions for the user

1. **Backlog or not?** The paper is rigorous and well matched to a gap in our
   evidence standards, but it touches no engine model and its data are
   request-only. The honest options are a logged row with the abundance standard
   and the occupancy constraint as its content, or no row at all.
2. **Should the catalogue gain an abundance field** when stage 3 starts, with the
   provenance fields this paper demonstrates? That is a catalogue-design decision
   the lead would otherwise take silently.
3. **Is a site-occupancy operator wanted** for the junction-channel population
   that D145 provisionally named as the molecular-loop unit — and if so, should
   the literature search for occupancy laws include this kind of
   inaccessible-site behaviour?
4. **Is mitosis anywhere in the plan?** Division milestone 2 implies it
   eventually. If it is firmly out of scope for now, this paper's rank 4 can be
   closed rather than parked.

## Provenance

Read in full: the complete open-access article from Europe PMC — abstract,
introduction, results and discussion, the full Materials and methods including
the FCS equations and fitting model, all five main and five supplementary figure
legends, the online supplemental material list, data availability,
acknowledgments and author contributions. Not read: the supplementary figure
images themselves, Tables S1 and S2 (strains and plasmids), the three western-blot
source-data files, and the published review history.

`rupress.org` refused WebFetch with HTTP 403 and was not pressed further; the
article page and publisher PDF were never retrieved. Metadata came from Crossref
(CC BY 4.0, version of record, online 11 November 2026) and Europe PMC (open
access, in PMC, supplement present). The full text was downloaded as JATS XML
from the Europe PMC REST API into its own empty directory, treated as untrusted
data, and flattened to text by a helper script held outside that directory and run
through `scripts/run_detached.sh` with `python3 -I` and the data path as an
argument.

Downloads, the XML SHA-256 and the access log are under
[/mnt/workspaces/Cells/paper-review-20261113-02](/mnt/workspaces/Cells/paper-review-20261113-02).
These notes introduce no model changes, no runs and no scientific acceptance.
Current status stays in [PROGRESS.md](../PROGRESS.md).
