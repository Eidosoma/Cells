# BIO-003: close the first endpoint pilot

2026-09-09, D044 / R008. **Pilot closed as a descriptive comparison.
Biological acceptance remains not assessable.** No dynamic cell-model
validation, new fit or production extension is claimed.

## Preserved result

The [BIO-002 calculation](BIO002_CONDITIONED_VOLTAGE.md) fitted C1/C2 only and
predicted C3 at -14.59 mV versus an approximate -18 mV figure reading: +3.41 mV
signed discrepancy, compared with -21 mV for the unchanged-C1 baseline. Its
[-18.32, -11.20] mV reading-bound prediction range is not a confidence interval.
The original protocol, dataset, code, artifacts and curation/result reports
remain unchanged. C3 was not used for retuning; C4/C5 remain quarantined.

Closing the pilot means its agreed descriptive calculation and bounded
evidence review are complete. It does not turn an unresolved biological question
into a pass, a failed numerical test, or a claim that Cells reproduces BETSE.

## Bounded evidence review

Reviewed the source article's Figure 3 caption, cell-culture, electrophysiology
and statistics sections; enumerated the original supplementary ZIP; extracted
the complete one-page supplement's text and visually inspected that page.
The [source attachment](../data/reviews/bio003_2026-09-09/README.md) retains the
unmodified article XML and supplement with their provenance and license.
The article is [Bonzanni et al. 2020](https://doi.org/10.1242/bio.048553).

| Open question | Evidence found | Closeout consequence |
| --- | --- | --- |
| Numerical endpoint uncertainty | Figure 3 labels mean/SEM and gives cell/experiment counts. Methods describe reporting across independent experiments but do not supply a C1-C3 numerical table or sufficiently specify aggregation/dependence for this analysis. | SEM remains untranscribed, not zero. A digitized error bar would still not recover experiment-level grouping; no confidence interval or biological cutoff is created. |
| Additional source data | The supplementary ZIP contains 20 images and one PDF. Figure S1 compares temperatures and dye-signal stability; the PDF has no embedded files. | No C1-C3 numeric summaries or raw/grouped recordings recovered from this package. No new values or substitute evaluation targets are extracted. |
| Recording boundary | Methods confirm whole-cell I/0 recording at 25 C and an intracellular-like pipette recipe. | This supports zero applied current, not measured fixed free intracellular ions, absence of dialysis, or a calibrated membrane/pump model. |
| Coupled versus isolated cell | RPTEC culture was seeded at 50% density and grown for three days before experiments; the inspected methods do not establish absent electrical coupling. | A measured cell cannot automatically be treated as junction-free. No contact parameters are inferred. |
| Temperature/time-course evidence | Figure S1 reports no significant temperature difference and follows optical dye signal over time. | Lack of a significant difference is not equivalence. Dye stability is not the electrical recovery trajectory required to validate our dynamics. |
| C4/C5 recipe conflict | Bounded title/DOI/correction searches found no resolving source. | Retain both published values and exclusions; no silent repair and no claim that no correction exists anywhere. |

The review did not establish fixed intracellular composition, condition-invariant
relative permeabilities, or negligible pump, divalent-ion and intercellular
currents. Those remain declared assumptions of the comparator. Recovering error
bars alone would not validate those mechanisms or identify physical parameters
from two fitted endpoints.

## Decision and stopping rule

Close BIO-001 through BIO-003 as a **completed descriptive pilot**, with
`biological_acceptance: not_assessable`. Do not keep extending this dataset
search, add missing physiology to force agreement, or choose a retrospective
acceptance threshold from the observed C3 discrepancy. The next active task
returns to architecture under the user's direction.

Reopening requires new evidence or a separately scoped benchmark: for example,
numerical experiment-level summaries plus adequate recording-boundary metadata,
or a better-supported dataset for dynamic-cell testing. Any revised extraction
gets a new dataset version. If C3 guides a new model, it is development data and
new evaluation data are required. No author contact, external coordination or
further research campaign is implicitly scheduled.

## Architecture lessons retained

- A maintained bath, finite reservoir and recording apparatus are different
  boundaries; each must declare support, state and exchange accounting.
- Species identity and valence must be explicit. Spectator/background charge
  is distinct from a transported species, not a chloride correction.
- A conditioned endpoint relation is a separate fidelity level from a dynamic
  ionic cell. It cannot provide invented ion inventories, recovery kinetics or
  transport fluxes to another component.
- Parameter fit, numerical correctness, source-model correspondence and
  experimental agreement need separate status fields.

These lessons inform the [BETSE capability roadmap](../docs/BETSE_CAPABILITY_ROADMAP.md)
and [multiscale execution design](../docs/MULTISCALE_EXECUTION_ARCHITECTURE.md).
They do not require all BETSE mechanisms to be implemented before the next
small engineering fixture.

## Verification and preservation

The 63 BIO-001/BIO-002 targeted tests were rerun with warnings treated as errors:
all pass (0.16 s). No additional biological experiment or full regression was
run. The previous 2,178-test full-suite result remains historical.
The [machine-readable closeout](bio-003-closeout.json) pins the original
analysis and the reviewed source files. Before/after checks cover all 39
production source files, package/dependency definitions, the six dataset files,
and the original pilot specifications, code, tests and artifacts.

All 62 protected file identities match their pre-work hashes. The original
BIO-002 receipt's four payloads, four calculation sources and six dataset
identities also match. For the closeout/architecture update, checks pass across
13 Markdown documents, 616 local links and 29 tables; the capability inventory
has 17 unique families and its six reviewed-source hashes match. Lint and
scoped whitespace checks pass. These are integrity/design checks, not new
scientific or GPU acceptance tests.

No production code, old acceptance report, numerical gate, E02 resource policy
or continuing-exploration file was changed. No BETSE run, new scientific fit,
GPU setup, optimization or long E02 trajectory was launched. The temporary PDF
reader is not part of the simulator environment or dependency lock.
