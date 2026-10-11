# REF-003a: first executed BETSE passive-law comparison

2026-09-12, D065. **Pass — bounded instantaneous component correspondence.**
No BETSE whole-cell trajectory, published biological benchmark, tissue, organ
or GPU validation is claimed. Cells production remains unchanged at development
0.15.0.dev0; stable production remains 0.14.0.

## Result

The [registered capture](../runs/ref-003a-2026-09-12/contact-01/verification.json)
completed in **4.681 seconds**. All **54 probes / 1047 tolerance comparisons /
15 exact-blocking checks pass**. The separate [saved-data audit](ref-003a-audit-01.json)
also passes, authenticating ten payloads and replaying the physical comparisons
without upstream, production or trajectory calls.

The maximum paired BETSE-versus-compiled-Cells amount-rate difference is
**2.220446049250313e-16 fmol/s** when F/R constants match. The largest normalized
error across all registered comparisons is **0.0000310074**, against a limit of
1. All three Cells paths (NumPy, eager JAX, compiled JAX) agree with the paired
reference and independent 70-digit arithmetic within the frozen limits.

The actual upstream module was imported from the isolated installed BETSE
v1.5.0 distribution. All **332 installed Python files** match the clean pinned
checkout. No function extraction, equation rewrite, dependency stub or production
patch was used. The function receives an explicitly declared `F`/`R` parameter
carrier; this is not a loaded BETSE Simulator or full configuration.

## The parameter difference we found

The source-declared profile uses `F=96485`, `R=8.314`; Cells uses
`F=96485.33212331001`, `R=8.31446261815324`. We retain both profiles and do not
silently equate them. The assignments are in the pinned
[parameter source](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/parameters.py).

At the synthetic -40 mV probe:

| Ion | Cells inward rate, fmol/s | BETSE source-constant rate minus Cells, fmol/s |
| --- | ---: | ---: |
| Na+ | 0.27443138243148035 | +8.5456368e-6 |
| K+ | -0.10545648872822985 | +6.3156652e-6 |
| Cl- | 0.016261781324682603 | -1.5413128e-6 |

Across the full panel, including deliberately nonphysiological domain stress
points, the maximum native-constant difference is **0.000716196 fmol/s**.
Independent arithmetic predicts that difference from the constants; the largest
remaining residual is **1.77635684e-15 fmol/s**. Native-constant cross-differences
are reported, not mislabeled as a same-parameter pass/fail test.

The [upstream transport implementation and concentration update](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/sim_toolbox.py)
establish the inward orientation and area conversion. With `rho=1`, `Dc/d`
maps to permeability; its flux density becomes total fmol/s by multiplying by
membrane area and dividing by `1e-15`. Currents in this report are derived from
the species amount rates, not independently exported BETSE current observations.
The capture also records the small in-place voltage perturbation in eighteen
inputs per upstream profile; fresh input arrays prevent it reaching Cells.

## Engineering evidence and limits

- [Prospective protocol](../validation/betse/protocol.json): voltages, concentrations,
  unit conventions, profiles, absolute/relative limits and execution budgets were
  fixed before numerical capture. There was one formal attempt, which passed.
- [Adapter checks](ref-003a-checks-01.xml): **52 passed** with warnings treated as
  errors. Forty-two test the checker/analytic limits; ten audit actual artifacts
  and reject rehashed sign, amount/current-unit, constant, input-mutation, backend,
  source, dependency and dtype corruptions. Synthetic checker fixtures are not
  counted as executed BETSE evidence.
- The initial lint check found two loop-binding and two import-order issues;
  these were corrected before capture. Both 42-test preflights passed; their
  [first](ref-003a-preflight-01.xml) and [second](ref-003a-preflight-02.xml) receipts
  are retained. No failed numerical trial or changed tolerance is hidden.
- [Preservation](ref-003a-preservation.json) authenticated all 912 CORE-010 payloads,
  its 352-file source capsule, the independent audit, closeout and 4190-test matrix
  before edits. The new adapter lives outside the production package and frozen
  implementation set; no existing production, solver, fixture or test was changed.
- [Reproduction guide](../validation/betse/README.md) and [separate lock](../validation/betse/requirements-lock.txt)
  describe the optional reference environment. Current dependencies are pinned;
  they are not presented as the historical paper's environment.

The [slice closeout](ref-003a-closeout.json) binds the actual packet, independent
audit, test receipt, code quality and final source-preservation checks. Historical
CORE-010 receipts and scientific payloads are not overwritten by the status updates.

The 4.681-second figure includes reference/Cells worker startup, JAX compilation,
recording and checks for these tiny probes. It is **not** simulation throughput,
an optimization result, a BETSE-versus-Cells speed comparison or a GPU prediction.

## Next bounded task: REF-003b

Align a fixed-volume, maintained-bath passive cell in the two full simulators.
First inspect and specify BETSE's geometry, charge-to-voltage closure and
initialization against Cells' existing one-cell model. Establish an equivalent
configuration before integrating; matching a flux function does not settle these
system-level choices. Preserve the synthetic pump boundary and disable unmatched
mechanisms. Then register a short trajectory, timestep refinement and permeability
perturbation. No such trajectory or long follow-on job has been launched.
