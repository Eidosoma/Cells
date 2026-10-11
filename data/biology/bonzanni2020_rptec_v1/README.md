# Bonzanni 2020 RPTEC endpoint pilot, version 1

BIO-001, curated 2026-09-09. This is a **provisional, figure-derived summary
dataset**, not raw recordings, an executed Cells experiment, or biological
validation. The [benchmark specification](../../../docs/BIOLOGICAL_BENCHMARK_001.md)
defines its permitted use.

## Source and reuse

Bonzanni M, Payne SL, Adelfio M, Kaplan DL, Levin M, Oudin MJ (2020).
*Defined extracellular ionic solutions to study and manipulate the cellular
resting membrane potential*. Biology Open 9, bio048553.
[DOI](https://doi.org/10.1242/bio.048553),
[article](https://pmc.ncbi.nlm.nih.gov/articles/PMC6994931/).

The article and figures are distributed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The retained Figure 2
and Figure 3 JPEGs are unchanged originals retrieved from the public
[Europe PMC supplementary-files API](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC6994931/supplementaryFiles).
The CSVs are our transcription and approximate digitization; their changes and
limits are described below. Attribution is retained here and in the manifest.
No publisher affiliation, endorsement, or raw-data access is implied.

The article XML was read through the public
[full-text API](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC6994931/fullTextXML).
Its retrieval hash and the ZIP retrieval hash identify the examined responses;
only the two figure assets, not the complete article/ZIP, are retained here.
The package inventory contained figures/equation images and a supplementary PDF,
not a numerical per-cell data file. The supplementary PDF was not analyzed.
No correction resolving the Figure 2 discrepancy was found in the bounded
DOI/title/correction searches on the review date; this is not proof none exists.

## Files and measurement scope

- [manifest.json](manifest.json): provenance, recording context, split, and limitations.
- [conditions.csv](conditions.csv): all five recipes from Figure 2A and the
  separately reported ionic values from Figure 2B. Units are mM throughout.
- [voltage_endpoints.csv](voltage_endpoints.csv): only C1-C3, manually read from
  Figure 3C to the nearest 1 mV. Values are approximate, not author-supplied means.
- [Figure 2](sources/biolopen-9-048553-g2.jpg): input-table witness, 650 by 245 pixels.
- [Figure 3](sources/biolopen-9-048553-g3.jpg): endpoint/caption witness, 750 by 438 pixels.

The cell line is RPTEC/TERT1, not a whole kidney or an organ target selection.
The measurement is whole-cell, zero-applied-current patch recording at 25 C;
the article describes recording for at least 30 s or until steady state. These
are condition summaries, not samples along a shared 30-second trajectory.
Culture connectivity and per-cell pairing across conditions are not established.

The reported sample counts are cells / experiments: C1 52/9, C2 26/3, C3 20/3.
They must not be treated as 98 independent experiments. Figure 3 reports SEM,
but this first transcription does not extract its small error bars or establish
the experiment-level dependence. Empty SEM fields mean **unknown**, never zero.
The +/-2 mV digitization bound is a conservative curator-assigned reading bound,
not an SEM, confidence interval, or between-cell variability estimate. It covers
coarse visual reading of the mean lines against the 0 to -80 mV axis; no individual
scatter points were reconstructed. No second-reader extraction is claimed.

## An input discrepancy that must stay visible

Figure 2A gives KCl 100.4/135.4 mM in C4/C5, whereas Figure 2B gives K+
110.4/145.4 mM. Both reports are retained; neither is silently repaired.
The C1-C3 salt recipes agree with Figure 2B. Their chloride sum is
`NaCl + KCl + 2 CaCl2 + 2 MgCl2 = 151 mM`.
The C4/C5 Figure 2B numbers imply a +10 mM charge-equivalent residual when
combined with the unchanged divalent salts and reported chloride. These are
transcription/stoichiometry checks, not chemical-speciation calculations.

C4/C5 are **quarantined**, not fit, scored, or digitized as voltage targets.
Their exclusion is based on the input disagreement, not simulator fit quality.
The first retrospective pilot assigns C1/C2 to fitting and C3 to evaluation.
All plotted outcomes have been visible during curation: this is a
held-out-from-fitting condition, **not a blinded or prospective experiment**.

## Reproduction and next gate

From the Cells directory:

```bash
.venv/bin/python scripts/check_biological_benchmark.py
.venv/bin/python -m pytest -q tests/unit/test_biological_benchmark.py
```

These check files, conversions, roles and retained exclusions only. They do not
recover SEM, fit a model, simulate trajectories, or certify biology.
Quantitative biological acceptance remains unassessable until measurement
uncertainty and the experimental-boundary approximation are qualified.
