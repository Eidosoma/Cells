# REF-005e R1-S0: source-bound software, R0 closeout and reference-study launch

2026-09-17, D130. Execute the [frozen reference-scoping contract](REF005E_REFERENCE_SCOPE_HANDOFF.md)
after closing the independently reviewed recording milestone. Production and
all accepted D119–D129 source contexts remain unchanged.

## Scope

Six original seven-cell finite-bath preparations, **10 ms**, three original
adaptive settings per preparation: **18 independent reference solves**. Save
1,601 dense samples and every accepted endpoint per solve. Check cross-solver
agreement, the 161-sample physical prefix, sampled domains and material/charge/
energy accounting. Record endpoint net ion and voltage rates without declaring
equilibrium. No native BETSE or Cells/JAX simulation is run.

New protocol identity and horizon/observation/restart metadata are explicit;
physics, reference settings and scientific limits are not changed. The original
30,000 RHS-call / 4,096 accepted-step caps remain fail-closed. Full matched 10 ms
qualification and a selected native ladder are not claimed by this study.

## Software development record

The first source-bound preflight retains **60 passes / two failures** in 16.13 s.
Both actual reference smokes failed on a reviewer type check: the integrator's
in-memory accounting contained NumPy scalar subclasses, while recomputation
used ordinary Python floats. The new wrapper now saves and independently reads
the JSON evidence before checking it, preserving float64 values and signed zero.
The existing equations, solver settings and all numerical limits stay unchanged.
Smoke stdout, stderr, trajectories and checks are now persisted explicitly.

The second packet records **63 passes in 15.97 s** / 16.320 s source-bound
execution. The final packet additionally tests explicit new protocol metadata,
resealed registration mutations and the complete actual 18-row dispatch with
clearly stubbed numerical work. The two real 10 ms reference smokes remain
separate numerical checks; the stubbed dispatch is not trajectory acceptance.

The final source-bound packet **passes all 73 checks in 17.83 s**; total
execution is **18.193 s**. It binds **38 source inputs, 47 sealed payloads and
eight internal pytest aliases**. Both real 10 ms smokes pass; neither earlier
software packet is deleted or overwritten.

- Software: `runs/ref-005e-reference-scope-2026-09-17/software-03/completion.json`
- Completion SHA-256: `6a0d9dff626bc0fccc0d5d2478aa9fc1446d9bce79b5e075a734307c70ac5e52`
- XML: `reports/ref-005e-reference-scope-checks-03.xml`
- XML SHA-256: `85a7ed5ce2afc05cf93cb814d12b3d3ea0793d884363d20eb01a4017b0c1dc81`

## Closeout and launch acknowledgments

R0 closeout completed **2026-09-17 18:25:18 UTC**, authenticating the reviewed
evidence and publishing five sealed payloads plus its completion receipt. It
performed no reference, native or Cells integration.

- Packet: `runs/ref-005d-live-closeout-2026-09-17/closeout-01`
- Completion SHA-256: `76fa3ab1706653530a5a3b5b234c2aaa5ff3193151024473d9b86872c14ed73d`
- Status: `r0_closed_r1_reference_scoping_ready`

The reference study was **launched detached at 18:25:49 UTC**, PID **3514599**.
The launcher authenticated the passing software, closeout and prerequisites,
froze the 38-input source context, and returned an acknowledgment.

- Run: `runs/ref-005e-reference-scope-2026-09-17/scope-01`
- Registration SHA-256: `3a41f3bb4e51ab73c6894b810cd263a155c0476f85493aea7155fd47371892b2`
- Acknowledgment: `launch.json`; durable logs: `runner.stdout.log`,
  `runner.stderr.log`, with separate reference-worker logs.

This records launch, **not a full-study result**. No worker status/completion
poll or automatic follow-up was performed. The next user-requested status check
should inspect the durable completion/failure evidence before proposing review.

## Operation and next gates

The closeout command authenticates the complete D129 review and prerequisite
chain without replaying any simulation or full numerical audit. It publishes a
separate closeout, measured-versus-projected recorder resource context and a
junction/biological readiness snapshot.

Then launch one detached reference study: CPUs 0–3, one BLAS thread, **300 s
worker / 600 s controller / 4 GiB worker address space / 8 MiB per new file /
128 MiB total new artifacts / 1 GiB free reserve**. Source/runtime/closeout
bindings are checked before and after. Durable logs and complete/failure receipts
are mandatory; no polling, automatic retry or follow-up campaign.

Junction work still needs a native reciprocal face/edge map before edge selection.
The biological candidate still needs original-methods, uncertainty and input/
held-out review; no new literature or fitted biological parameters are claimed.
After a passing reference study, its saved evidence needs review before an
explicit native timestep/resource probe and full matched campaign.
