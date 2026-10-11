# A biological benchmark alongside source correspondence

2026-09-16, D107; numerical status updated 2026-09-17, D121–D122.
Candidate-data preparation, not biological acceptance or a
runnable simulation configuration. Keep this separate from both the earlier
descriptive BIO-003 pilot and the completed short BETSE channel comparisons.

## First candidate and an important discrepancy

BETSE's [2016 paper, section 3.1.1 and Table 2](https://www.frontiersin.org/journals/bioengineering-and-biotechnology/articles/10.3389/fbioe.2016.00055/full)
compares a 30-minute simulation of 35 uncoupled cells to Xenopus oocyte values.
The table provides Na/K/Cl permeability inputs and concentration/voltage
comparisons. This is a useful first candidate, not a guarantee of validation.

The [original Costa et al. (1989) abstract](https://pmc.ncbi.nlm.nih.gov/articles/PMC1189096/)
reports Na/K/Cl permeability estimates of 0.544/1.741/0.149 nm/s, converted from
cm/s. BETSE's table uses 0.537/1.765/0.138 nm/s. **Preserve both records; do not
merge them.** The original abstract also supplies concentration uncertainties
and sample counts, and proposes inward uphill chloride transport.

Engineering implication: a passive-Cl plus Na/K-pump model may lack a mechanism
needed for this preparation. A matching mean voltage would not resolve that
gap. At true steady state with only passive Cl transport, Cl has to approach
its electrochemical equilibrium; a measured sustained offset needs an explicit
transport/reaction mechanism or a defensible non-steady-state explanation.
Do not add a fitted chloride source just to pass the benchmark.

The [candidate record](../validation/betse/biological_candidates/xenopus_costa_1989.json)
keeps source-specific values, units, roles, uncertainty metadata and unresolved
questions. Original full methods/tables have **not yet been reviewed**; the
abstract's plus/minus values must not be assumed to mean SD, SEM or confidence
limits. No pass/fail biological tolerance or calibration is set from them yet.

## Preparation before a biological run

1. Review the original methods/tables and reconcile the permeability difference:
   pooled estimates versus a particular condition, transcription or another
   explanation. Record exact page/table provenance and permitted data use.
2. Establish cell stage, temperature, membrane area/capacitance, solution recipe,
   activity assumptions, maintained versus finite bath, pump level/metabolism,
   background charge and other transporters. Resolve chloride handling explicitly.
3. Separate independently measured inputs, initial conditions, any calibrated
   parameters and held-out outcomes. An inside concentration used to initialize
   a run is not an independent prediction merely because the endpoint matches it.
4. Select the preparation/relaxation and steady-state criteria before the full
   run: amount-rate and current residuals plus a stable observation window, not
   only an elapsed time or a flat-looking voltage plot.
5. Preregister uncertainty-aware voltage, ion-concentration and current outcomes,
   followed by an independently measured perturbation where data allow. Ion
   substitution, pump inhibition and bath changes are candidate interventions,
   not yet specified experiments or fitted targets.

The published BETSE *simulated* extracellular concentrations differ from its
experimental comparison column. Neither simulated endpoints nor intracellular
targets should silently become clamped bath inputs. Historical BETSE paper
reproduction, pinned modern-source comparison and original-data evaluation are
three distinct tasks.

## Numerical and resource gates

The bounded millisecond comparisons do not qualify ionic relaxation over many
minutes. The [refined 1 ms pump–leak pilot](../reports/REF005C_PUMP_PILOT_CLOSEOUT.md)
is now independently closed, but not biologically calibrated. The
[longer-duration plan](BETSE_PUMP_RELAXATION_PLAN.md) qualifies recording, then
proposes a separate 10 ms numerical extension and reference-led relaxation.
Measure stiffness, positivity and solver/refinement error on explicit windows.
Consider a dedicated equilibrium solve and/or an appropriate stiff integrator
only with independent residual and trajectory checks. Do not choose a larger
timestep because a long run is expensive.

Budget long captures before launch, with bounded observation output and complete
restart state. Detach them and return control; no automated polling or campaign.
Biological confidence requires agreement across observables and held-out
conditions, not just passing a simulator-to-simulator tolerance.
