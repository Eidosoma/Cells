# BIO-001: first experimental voltage-response benchmark

2026-09-09, D042 / R007. **Specification and provisional data only.**
Production remains Cells 0.10.0. No model fitting, new trajectory, optimization,
GPU work, BETSE execution, or long E02 study is part of this slice.

## Question and selected scope

Can a declared one-cell electrical model predict a voltage endpoint after an
increase in external potassium and a simultaneous decrease in sodium, using
parameters determined from other conditions?

Start with the RPTEC/TERT1 data in
[Bonzanni et al. (2020)](https://doi.org/10.1242/bio.048553), Figures 2 and 3C.
The [versioned data card](../data/biology/bonzanni2020_rptec_v1/README.md) contains
the source figures, input transcription, approximate voltage endpoints,
recording metadata, provenance and known uncertainty gaps.
This is a one-cell **measurement** in a cultured population, not evidence that
the measured cell was isolated from every neighbour. It does not select a kidney
as our future organ or imply that a whole renal cell has been modeled.

The first test is deliberately an endpoint dose response. The source does not
provide a numerical recovery time course in the inspected materials. No recovery
rate, memory, heredity, cancer reprogramming, or organ function is tested here.

## Candidate review and selection

| Candidate | Useful evidence | Limitation / decision |
| --- | --- | --- |
| [Costa et al. 1989](https://pmc.ncbi.nlm.nih.gov/articles/PMC1189096/), used by [BETSE 2016](https://doi.org/10.3389/fbioe.2016.00055) | Measured oocyte ions and inferred permeabilities; informative resting-state comparison | Primary abstract describes voltage-clamp ion substitutions, permeable substitute ions and non-equilibrium chloride; not a drop-in passive-Cl resting-cell validation. Retain as a future mechanism/steady-state challenge. Original scanned methods/tables not fully reviewed here. |
| Bonzanni et al. 2020, RPTEC/TERT1 | Defined solution series with direct electrical endpoints, cell/experiment counts and an accessible CC-BY figure source | Select C1-C3 as a provisional pilot. C4/C5 have conflicting input values; numerical SEM and recording-boundary qualification remain open. |

Costa's abstract reports intracellular chloride 37.7 mM and a chloride
equilibrium potential near -28 mV, with proposed inward uphill transport.
Our `bioelectric_cell@1` has no active chloride pathway. At a true full-state
steady state with nonzero passive chloride permeability, its only chloride
flux must vanish, requiring `V = E_Cl`. Matching one transient voltage would
not establish stationary ion homeostasis. This is a model-adequacy warning,
not a claim that a specific extra transporter has been identified.

## Data-quality and fitting boundaries

Figure 2A and 2B agree for C1-C3. The explicit divalent salts must be counted
when translating the recipe: chloride includes two equivalents from each
CaCl2 and MgCl2. C4/C5 disagree by 10 mM in reported potassium and are
quarantined. No choice of the more convenient column is permitted.

| Role | Conditions | Permitted use |
| --- | --- | --- |
| Fitting | C1, C2 | Determine at most two effective response coefficients in the first pilot; diagnose non-identifiability |
| Evaluation | C3 | Predict the higher-potassium condition without condition-specific retuning |
| Quarantined | C4, C5 | Preserve conflicting inputs; no fitting, scoring or substitute voltage target |

This is **retrospective held-out-from-fitting evaluation**. All figure outcomes
were visible during curation. It is not blinded, prospective, or external-study
validation. The data must not be repeatedly used to select models and then
reported as untouched validation. Any later use of C3 for model selection
changes it to development data and requires a new evaluation dataset.

The endpoint means are visually read to the nearest 1 mV with a conservative
curator reading bound of +/-2 mV. The published SEM bars are not transcribed;
the statistical uncertainty is unknown, not zero. The displayed scatter is
not reconstructed into invented raw records. Cell counts do not replace
experiment-level replication or establish the covariance between conditions.

## What the existing model can and cannot represent

| Interface / assumption | Existing Cells capability | Benchmark requirement |
| --- | --- | --- |
| Na/K/Cl passive exchange | Dimensioned GHK-like flux, voltage/charge accounting | Reuse the constitutive mechanism after a justified experimental-boundary mapping |
| External solution | Maintained Na/K/Cl-only bath; zero net charge required over those three ions | C1-C3 include 1.8 mM Ca and 1 mM Mg. Their omitted positive charge is 5.6 mM equivalents; do not alter measured chloride to satisfy the old schema. A versioned background-ion/expanded-bath contract is needed. |
| Recorded electrical condition | Free voltage determined by amounts and fixed anchors; no electrode interface | Source uses whole-cell recording at zero applied current, not voltage clamp. Define the electrode/pipette boundary and whether dialysis can be approximated. |
| Intracellular composition | Explicit amounts and fixed volume | Pipette recipe is not measured free cytosolic Na/K/Cl. Buffers, counterions, chelation and dialysis must remain explicit uncertainties. |
| Pump | Reversible synthetic 3Na-out/2K-in reference law | No biological kinetic calibration follows from the paper or from fitting a voltage curve |
| Geometry and time | Explicit area, volume, capacitance; bounded qualified timesteps | Endpoints do not identify these quantities or validate recovery dynamics. New parameter regimes need new reference/refinement checks. |
| Neighbours | Isolated physical-cell model | Coupling status of the cultured measured cell is not established; quantify/declare an isolated-cell approximation before interpreting it |

Merely replacing initial voltage with the observed endpoint would make that
endpoint an input, not a prediction. Do not independently reset voltage or
fixed charge for each evaluation condition to manufacture agreement.
Changing the bath or measurement boundary is not an excuse to bypass existing
electroneutrality, positivity, accounting or restart checks.

## Smallest next calculation, before a production extension

BIO-002 should first specify a reusable **conditioned electrical-response
reference**, including zero applied current and the fate of intracellular ions.
It is a measurement-boundary approximation, not a new organ or assay-specific
branch in the engine. No current model identity may silently acquire a pipette
reservoir, spectator ions or a replacement pump.

A useful simplest comparator is the passive constant-field voltage relation
with fixed intracellular activities/concentrations, temperature and relative
permeabilities. In this selected series, external `Na + K = 145.4 mM` and
`Cl = 151 mM`. Under those assumptions:

```text
exp(V / V_T) = a + b K_external
V_T = R T / F
```

Here `a` is dimensionless and `b` has units mM^-1. They are two effective curve
coefficients, not uniquely identified pump rates, individual permeabilities or
intracellular concentrations. This follows by substituting the fixed external
cation sum into the monovalent GHK voltage equation. A fitted positive curve
alone does not establish a physically admissible decomposition into mechanisms.
The approximation omits pump current and state changes; compare its limits
explicitly with any later mechanistic candidate, not as Cells' new cell law.

Use C1/C2 only for this comparator and C3 for one retrospective extrapolation.
Include the unchanged-C1 voltage as a no-response comparator. Keep the model,
parameter bounds, units and uncertainty propagation fixed before calculating
the evaluation prediction. Do not fit capacitance, volume, absolute transport
rates, intracellular ions and pump parameters from two endpoints.

## Acceptance and reporting

Three different statuses must remain separate:

1. **Dataset integrity:** source assets and locators exist; values, units,
   recipe arithmetic, roles and known exclusions are consistent. The offline
   checker verifies this bounded machine-readable contract, not the accuracy
   of the manual visual extraction against biological ground truth.
2. **Numerical correctness:** an eventual candidate meets its independently
   specified refinement and accounting tests in the chosen regime. Existing
   synthetic-cell qualification cannot simply be reused for fitted biology.
3. **Biological agreement:** uncertainty-aware held-out prediction, not just
   successful integration or a good fit to C1/C2.

For the first descriptive calculation, report predicted and approximate measured
C3 voltage, signed/absolute error in mV, change from C1, the no-response comparator,
and sensitivity to the +/-2 mV input-reading bounds. Do not report an experimental
confidence interval from that digitization bound. Report numerical and biological
errors separately, and retain failures.

**No numerical biological pass threshold is approved yet.** Recover/review SEM
or raw experiment-level summaries, establish dependence, and qualify the boundary
approximation before setting an acceptance interval. At that point propagate
measurement and parameter uncertainty and freeze a scientifically justified
error criterion before evaluating the candidate. Until then report
`not_assessable`, not pass. Data extraction/curation and a descriptive comparator
can still be completed without claiming validation.

Completion of BIO-001 means this specification, the provisional dataset and
offline integrity tests exist. It does not mean the future BIO-002 calculation
or a biologically validated one-cell preset has been delivered.

## Work kept separate

Optimization and GPU work are paused by the user's direction. NUM-005c2 remains
unfinished and deferred pending a separate resource decision; no long E02 run,
budget change, weakened check or production-graph promotion is authorized here.
Later progression remains measured two-cell communication, a tiny network,
and withdrawal/memory experiments, each with its own evidence requirements.
