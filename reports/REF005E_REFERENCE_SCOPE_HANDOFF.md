# REF-005e R1-S0: 10 ms reference/domain scoping contract

2026-09-17, D130. User-authorized next step after R0 independent closure.
Freeze this contract with the new source context. Subsequent software/launch
results belong in a separate report. No production or frozen source edits.

## Purpose and unchanged science

Run the existing scalar independent equations for the **same six seven-cell
finite-bath preparations**, extending 1 ms to **10 ms**. Keep chemistry, geometry,
Na/K/Cl species, charge, temperature, maintained ATP/ADP/Pi and all transport
parameters unchanged. Do not substitute a maintained bath or fit biology.

Use all three original settings: DOP853 base (rtol 1e-10, atol 1e-14, 50 µs max
step), DOP853 tight (1e-12, 1e-16, 25 µs), Radau check (1e-11, 1e-15, 25 µs).
Six controls × three settings = **18 solves**. Retain **30,000 RHS calls / 4,096
accepted steps per solve** as fail-closed work caps. No automatic extension.

Save **1,601 samples at 6.25 µs**, plus every accepted endpoint. Cross-solver
amount/transfer agreement stays **1e-11 fmol**, energy **1e-10 pJ**, voltage
**1e-9 V**. Compare each solve's first 161 samples with its accepted 1 ms
counterpart under these same bounds. Adaptive prefixes need not be bitwise equal.
Neither native raw sample labels nor a changed-horizon time label is used as a
physical-time substitute.

Check all saved dense samples and accepted endpoints for positive concentrations,
finite state/rates, existing voltage/affinity domains and nonnegative dissipation
within the existing roundoff allowance. Material/charge/energy residual limits
stay **2e-11 fmol / 1e-20 C / 2e-8 pJ**. These are sampled-domain checks, not an
analytic guarantee between every sample. Preserve complete 59-coordinate
reference histories and endpoint inside/bath ion rates and voltage rates.
Endpoint rates are descriptive: no steady-state threshold or claim is introduced.

## Evidence, resources and execution

First authenticate and close the completed D129 recording review, all current
frozen sources, source-bound software and its prerequisite chain. Publish
measured 1 ms live-recorder costs separately from linear 10 ms planning estimates.
Those estimates are not measured future performance, an ETA or approval for the
full native campaign; native histories remain allocated.

A short source-bound software gate tests preserved science, coverage/corruption
refusals, old-prefix handling, two actual 10 ms reference smokes in isolated
processes, model-import exclusion, registration and detached timeout/failure
handling. The full matrix starts afresh; smoke results are not reused as rows.

Launch one detached reference-only job: CPUs 0–3, one BLAS thread, **300 s worker /
600 s controller / 4 GiB worker address space / 8 MiB per new file / 128 MiB total
new artifacts / 1 GiB free reserve**. Sources and prerequisites authenticate
before/after. Write durable logs, per-solve records and terminal completion/failure.
No polling, automatic retry or follow-up audit/campaign.

## What success does not establish

No native BETSE or Cells integration, selected native ladder, full 10 ms parity,
complete restart qualification at 10 ms, biological validation, equilibrium,
GPU result or whole-native bounded-memory claim. A passing reference study needs
separate saved-evidence review. Native timestep/resource scoping and ordinary
Cells windows/restarts then precede a fully registered matched campaign. The
native finest energy limit remains **1e-7 pJ**, irrespective of horizon.
