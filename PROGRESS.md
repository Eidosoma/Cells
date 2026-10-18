# Progress

Last updated: 2026-10-18 UTC.

This is the source of current implementation status. Milestone definitions live
in [Roadmap](docs/ROADMAP.md), scientific updates in
[Scientific basis](docs/SCIENTIFIC_BASIS.md), and design choices in
[Decisions](docs/DECISIONS.md).

## Current position

- **Local flank-channel pilot running (18 October).**
  [Launched detached at 11:34:46 UTC](/mnt/workspaces/Cells/two-task-local-channel-20261018-01/launch.json),
  worker **1156416**, with **1,038 frozen source files**. The single
  [startup check](/mnt/workspaces/Cells/local-channel-development-20261018-01/startup.json)
  confirmed the CPU phase running, empty stderr and no failure artifact.
  The L4 phase follows CPU qualification. Estimated total runtime is **6–8 hours**
  (**17:35–19:35 UTC**), within a **10-hour cap**; completion is still pending.
  The [execution protocol](validation/assays/source_order_long/local_channel_protocol.json)
  and [CPU/L4 harness](tests/unit/test_local_channel.py) retain all five conditions,
  the fixed margins and numerical checks, both GPU utilization measures and
  per-arm timings. No automatic polling, retry or follow-up.

  The [saved-calibration analysis](/mnt/workspaces/Cells/channel-compensation-diagnosis-20261018-01/result.json)
  finished in **4.9 s**, after **eight passing analytic/isolation checks**.
  It reads **3,240 named calibration arrays** from the completed CPU/L4 pilot,
  reproduces all archived geometry scores exactly and gives **zero CPU/L4
  diagnostic difference**. [Inputs](/mnt/workspaces/Cells/channel-compensation-diagnosis-20261018-01/inputs.json),
  [completion](/mnt/workspaces/Cells/channel-compensation-diagnosis-20261018-01/completion.json)
  and the [diagnostic code](validation/assays/channel_compensation_diagnostic.py)
  preserve provenance. No new simulation, held-out response, reader or observation
  schedule entered this diagnosis; full trajectory archives were not re-audited.

  **Location and source order share the same limiting joint pair**, labels
  **[0,1] versus [1,0]**; these are not two independent failures. At the finest
  sham timestep, **92.57%** of that pair's squared separation is at **320 us**,
  and cells **3/5 contribute 62.42%**, cells **2/6 35.98%**, and cell **7 1.60%**.
  At strength **0.4**, the location/order effect vectors have cosine **0.842**;
  their opposed-label difference has half-distance **1.9380 nV**, already below
  the **2-nV** margin before allowing different fitted strengths. The closest
  fitted pair is **0.429292 versus 0.4**, with half-distance **1.921477 nV**.
  Feature contributions locate the observed separation, not causal channel
  sensitivities; factorial interactions can also reflect the joint cue encoding.

  Uniform channel changes move the 15-feature no-cue vector by about **301 µV
  in L2 norm**, while the largest joint cue-relative change is **0.0564 nV**.
  The uniform decrease changes the joint separation score by **−0.00629,
  −0.00344, +0.00561 nV** across the three timesteps; its direction is not stable.
  The increase gives **−0.00899, −0.000340, −0.000614 nV**. These finite-step
  comparisons are not continuum error bounds. The
  [summary](/mnt/workspaces/Cells/channel-compensation-diagnosis-development-20261018-01/diagnosis-summary.json)
  retains all conditions and keeps background shifts separate from cue effects.

  The [plan](validation/assays/source_order_long/local_channel_plan.json) and
  [input builder](validation/assays/local_channel_design.py) specify **five
  calibration conditions**: sham, **±10% Kv1p5 permeability on cells 2/6**, and
  **±10% on cells 3/5**. These are the opposite flanks beside sources 1 and 4;
  both source cells, shared central cell 7 and **0.9× junction coupling** remain
  fixed. Both signs and both flanks are included because uniform perturbations
  do not identify local effects. Slightly unequal flank membrane areas are recorded;
  equal relative permeability changes are not equal absolute channel capacities.

  [Preparation](/mnt/workspaces/Cells/local-channel-design-20261018-01/preparation.json)
  records **33 passing input checks in 33 s**, clean lint, **360 authenticated
  archived inputs**, and **1,800 CPU/GPU input variants** matching those inputs
  except for the declared flank channels. All **1,030 frozen pilot sources** remain
  unchanged. Registered work is **900 worlds / 4,300,800 world-steps per backend**,
  equally allocated across five arms, using the existing support, margins,
  reader views and numerical requirements. These remain calibration cases in
  one synthetic tissue; backend/timestep repeats are numerical checks, and no
  held-out cases enter this pilot.

  [Harness preparation](/mnt/workspaces/Cells/local-channel-development-20261018-01/launch-preparation.json)
  records **50 passing host checks in 71 s**, clean lint and exact reproduction
  of the archived CPU sham calibration through the new harness. The original
  unperturbed CPU reader remains fixed; the completed uniform-channel sham is
  the historical reference. [Checks](/mnt/workspaces/Cells/local-channel-development-20261018-01/checks.json)
  bind **90 test nodes per backend**: expected **85 CPU passes plus five GPU-only
  skips**, **90 L4 passes**, and **176 required reports** overall. They also retain
  a corrected verification-driver report-count assumption and its failed record;
  no simulation or host test failed during preparation. Full prior-archive
  authentication runs inside the detached worker before simulation. The earlier
  input preparation retains its original pre-launch status.

- **Channel-compensation pilot completed at 22:14:11 UTC on 17 October.**
  **CPU: 51 passed and three expected GPU-only skips; L4: all 54 passed.**
  The [result](/mnt/workspaces/Cells/two-task-channel-compensation-20261017-01/result.json)
  and [completion](/mnt/workspaces/Cells/two-task-channel-compensation-20261017-01/completion.json)
  record **6,260 evidence entries, 106 required reports and 1,030 frozen sources**.
  The worker has exited, stderr is empty and no failure artifact is present.
  Launch-to-completion took **4 h 00 min 07 s**, including **3 min 29 s** of final
  archive hashing after the numerical suites finished at **22:10:42 UTC**.

  **Neither tested channel adjustment improves the predeclared separation score;
  the unchanged-channel sham remains selected.** The
  [plan](validation/assays/source_order_long/channel_compensation_plan.json) and
  [protocol](validation/assays/source_order_long/channel_compensation_protocol.json)
  hold junction permeability at **0.9×**, testing **0.9× and 1.1× Kv1p5 maximal
  permeability in remote cells 2,3,5,6,7**, against a **1.0× sham**. Cue-source
  channels, initial states, timing, observations and the margin remain fixed.
  The [selection](/mnt/workspaces/Cells/two-task-channel-compensation-20261017-01/evidence/gpu/channel-compensation-selection.json)
  gives identical CPU/L4 primary scores: **1.921477 nV sham, 1.919229 nV lower,
  1.916530 nV higher**, all below the fixed **2-nV** criterion. The limiting
  calibration-curve comparison concerns location in the joint arm. This tests
  two uniform channel changes in one synthetic tissue; it does not rule out
  other channel interventions or establish biological recovery.

  On the **12 joint calibration cases**, raw frozen-source readings resolve both
  tasks in **0/12 sham, 3/12 lower, 0/12 higher**. The separately labelled
  reference-assisted view gives **8/12**, and condition-calibrated readings
  **9/12**, for every condition. These counts agree at all three timesteps on
  CPU/L4. The limited raw-reader gain does not meet the predeclared selection
  objective. No-cue/disconnected controls remain unresolved; all 24 primary joint
  task scores per condition and reader view meet finest-step stability checks.
  **No held-out cases were evaluated**, and no candidate advances to fresh-case
  confirmation. The intervention is present from initialization, not a recovery
  process after damage; backend/timestep repetitions are numerical checks.

  Each backend completed **540 worlds / 2,580,480 world-steps**, equally planned
  across five arms. CPU/L4 comparisons passed **6,548,199,120 state/field scalar
  comparisons** at unchanged tolerances, with exact reader-score/decision agreement
  and zero paired-contrast differences. Conservation/domain, full recordings and
  restart/reordering/partition checks passed. Sham histories reproduce the archived
  weaker-coupling calibration bitwise across **840 window comparisons per backend**;
  each changed-channel condition matches **180 initial states per backend**.

  **Whole L4 phase: 28.98% GPU busy and 9.90% measured SM-active**, with over
  **99.9999% busy coverage and 100% SM coverage**, across **1.902 GPU-hours**.
  These averages include compilation, host checks and archive handling. Aggregated
  arm execution times were **419–428 s**; batch totals were **911–1,012 s**,
  including **416–517 s** of archive handling per arm. Artifacts/cache occupy
  **28.14 GB**, and peak child RSS was **1.65 GB**.

  [Launch preparation](/mnt/workspaces/Cells/channel-compensation-development-20261017-01/launch-preparation.json)
  binds the preceding 30 passing host checks and three final source-binding checks.
  The [completion review](/mnt/workspaces/Cells/channel-compensation-development-20261017-01/completion-status-20261018.json)
  verified all 106 required reports against the completion manifest, exact test
  inventories/skips, metric records and all 1,030 unchanged frozen sources.
  This status review did not repeat the full archive audit or launch a follow-up.

- **Weaker-coupling diagnosis completed on 17 October.**
  The [saved-feature diagnosis](/mnt/workspaces/Cells/coupling-transfer-diagnosis-20261017-01/result.json)
  completed in **40 s**, replaying all three reader views at three timesteps for
  the primary and two comparator panels. Saved CPU/L4 diagnoses agree exactly.
  [Inputs](/mnt/workspaces/Cells/coupling-transfer-diagnosis-20261017-01/inputs.json),
  the [reproduction script](/mnt/workspaces/Cells/coupling-transfer-diagnosis-20261017-01/analyze.py)
  and [completion](/mnt/workspaces/Cells/coupling-transfer-diagnosis-20261017-01/completion.json)
  retain the completed lower-coupling subset and every inspected case. This was
  a host analysis of saved responses while the full coupling campaign continued;
  it ran no simulations and does not accept the whole campaign.

  All four unresolved **reference-assisted** joint cases use strength **0.403125**,
  and their own-source-curve projections hit the **0.4 calibration endpoint**.
  Their unresolved task scores fall **0.119–0.512 nV** below the fixed 2-nV margin;
  the largest corresponding finest-step change is **0.0159 nV**. However,
  **target recalibration still leaves five cases unresolved**, with interior
  own-curve projections: deficits **0.0584–0.0694 nV**, versus finest-step changes
  no larger than **0.00216 nV**. Calibration-edge effects are present, but
  recalibration alone has not restored sufficient separation in this assay.
  These finite-step comparisons are not continuum error bounds. Raw transfer,
  reference assistance, recalibration and true-label/strength oracle probes
  remain separate; none supplies fresh cases or changes the original outcomes.

  Initial [input preparation](/mnt/workspaces/Cells/channel-compensation-design-20261017-01/preparation.json)
  records **21 passing host checks in 25 s**, clean lint and **1,080 validated
  CPU/GPU input variants**. These are input checks, not new backend simulations.
  [Harness preparation](/mnt/workspaces/Cells/channel-compensation-development-20261017-01/preparation.json)
  records **30 passing host checks in 91 s**, clean lint, **540 generated CPU
  inputs checked against their archived counterparts**, and all **1,024 existing
  frozen sources unchanged**. The resulting pilot is now complete, as recorded
  above; these preparation records retain their original pre-launch status.

- **Coupling-transfer study completed at 17:42:06 UTC on 17 October.**
  **CPU: 36 passed and two expected GPU-only skips; L4: all 38 passed.**
  Numerical suites finished at **17:29:52 UTC**; final archive hashing took
  another **12 min 14 s**. Total launch-to-completion time was **6 h 11 min**.
  The [result](/mnt/workspaces/Cells/two-task-source-order-coupling-transfer-20261017-01/result.json)
  and [completion](/mnt/workspaces/Cells/two-task-source-order-coupling-transfer-20261017-01/completion.json)
  bind **15,060 evidence entries, 72 required reports and 1,024 frozen sources**.
  The worker has exited, stderr is empty and no failure artifact is present.

  **The primary unassisted transfer fails: 0/32 joint cases resolve both tasks
  at either coupling strength**, on both CPU and L4 at all three timesteps.
  The [protocol](validation/assays/source_order_long/coupling_transfer_protocol.json)
  changed only junction permeability to **0.9× or 1.1×**, holding the archived
  source calibration, cue doses, observation support and **2-nV margin** fixed.
  The no-cue voltage vector shifts by about **13.85 µV in L2 norm**. The separately
  labelled shared-reference-assisted diagnostic gives **28/32 at 0.9× and 32/32
  at 1.1×**; target-condition recalibration gives **27/32 and 32/32**, respectively.
  These outcomes agree on CPU/L4 at all three timesteps and do not replace the
  failed primary transfer. Reference-assisted finest-step stability passes all
  64 joint task scores per condition. All 64 raw stronger-coupling scores miss
  that diagnostic despite unchanged decisions; the failures remain recorded.

  Each backend completed **1,320 worlds / 6,307,840 world-steps**, equally planned
  across five arms. The [lower](/mnt/workspaces/Cells/two-task-source-order-coupling-transfer-20261017-01/evidence/gpu/source-order-coupling-lower-cpu-gpu.json)
  and [higher](/mnt/workspaces/Cells/two-task-source-order-coupling-transfer-20261017-01/evidence/gpu/source-order-coupling-higher-cpu-gpu.json)
  comparisons passed **16,006,708,960 state/field scalar comparisons combined**,
  at unchanged tolerances, with exact frozen-reader decision agreement and zero
  paired-contrast backend differences. Conservation/domain, full recordings,
  restart/reordering/partition and historical checks passed. Disconnected histories
  reproduce the source; connected cases share initial states but can evolve
  differently immediately. These reuse the same 32 joint input cases per condition
  for paired parameter transfer, not fresh-strength validation or independent
  biological replication. No broader BETSE equivalence or biological claim follows.

  **Whole L4 phase: 44.34% GPU busy and 15.04% measured SM-active**, with over
  **99.9999% busy coverage and 100% SM coverage**, across **2.890 GPU-hours**.
  These averages include compilation, host comparisons and archive handling;
  per-arm timings remain in the panel reports. Artifacts/cache occupy **69.08 GB**
  and peak child RSS was **1.77 GB**. The
  [completion review](/mnt/workspaces/Cells/source-order-coupling-transfer-development-20261017-01/completion-status-20261017.json)
  checked all 72 required reports against the completion manifest, exact test
  inventories/skips and all 1,024 unchanged source files. This status review did
  not repeat the full archive audit or launch another simulation. The weaker
  condition's diagnosis and completed channel-compensation pilot are recorded above.

- **Fresh-strength pulse confirmation completed at 20:02:20 UTC on 16 October.**
  **The primary target is met: 32/32 fresh joint cases correctly resolve both
  location and source order**, with matched calibration at all three timesteps
  on CPU and L4. The [readouts](/mnt/workspaces/Cells/two-task-source-order-pulse-confirmation-20261016-01/evidence/gpu/source-order-pulse-confirmation-readouts.json)
  retain every case, control and comparator. Primary **128/160/320-us** and
  spanning **128/256/512-us** observations both give **32/32**; late-only
  **320/384/512 us** gives **23/32**, with nine paired gains and no regressions
  for primary versus late-only. Single-task arms give **16/16 each**; no-cue,
  disconnected and input-only readers remain unresolved.

  The weakest primary score is **2.139881 nV**, **0.139881 nV above the fixed
  2-nV margin**. All 64 joint task scores meet the declared finest-step stability
  checks; the largest finest-step change is **0.015210 nV**, without a continuum
  error bound. The [protocol](validation/assays/source_order_long/pulse_confirmation_protocol.json)
  froze **104-us onset separation**, second pulse **112–120 us**, unchanged dose,
  five remote cells and 15 features before simulating eight new strengths
  **0.403125–0.796875**. Only **0.4/0.6/0.8** fitted readers. This confirms strength
  interpolation in one synthetic tissue. The earlier **29/32** remains a
  separate cohort; backend/timestep repetitions are numerical checks, not
  independent biological cases or a paired estimate of the pulse-timing effect.

  **CPU: 16 passed and one expected GPU-only skip; L4: 17 passed.** Each backend
  completed **660 worlds / 3,153,920 world-steps**, with equal work across five
  arms. The [result](/mnt/workspaces/Cells/two-task-source-order-pulse-confirmation-20261016-01/result.json)
  and [completion](/mnt/workspaces/Cells/two-task-source-order-pulse-confirmation-20261016-01/completion.json)
  record **7,535 evidence entries, 33 required passing reports and 1,021 frozen
  sources**. The [CPU/L4 comparison](/mnt/workspaces/Cells/two-task-source-order-pulse-confirmation-20261016-01/evidence/gpu/source-order-pulse-confirmation-cpu-gpu.json)
  passed **8,003,354,480 scalar comparisons** at unchanged tolerances, with exact
  reader-decision agreement. Conservation/domain, bitwise restart/reordering/
  partition, **1,672 historical window comparisons**, **117,576 feature scalars**
  and **90 calibration readers** passed. All 220 paired contrasts missing the
  finest-step stability criterion belong to disconnected controls below the
  declared signal floor; active-arm contrasts meet it.

  Total elapsed time was **4 h 33 min**, exceeding the **3–4 h** estimate.
  **Whole L4 phase: 28.20% GPU busy and 9.67% measured SM-active**, with over
  **99.99% coverage**, across **2.248 GPU-hours** including compilation, host
  checks and archive handling. Per-arm kernel execution was **537–584 s**;
  total batch time was **1,211–1,512 s**, including **557–880 s** in archive
  handling. The CPU/L4 comparison took **19 min 17 s**. Artifacts/cache occupy
  **34.51 GB** and peak child RSS was **1.77 GB**.

  [Preparation](/mnt/workspaces/Cells/source-order-pulse-confirmation-development-20261016-01/preparation.json)
  retains nine passing preflight checks. The
  [completion status](/mnt/workspaces/Cells/source-order-pulse-confirmation-development-20261016-01/completion-status-20261017.json)
  binds the reviewed reports and records per-case minima, controls, timings and
  scope; no full archive audit or new simulation was run for this status check.
  That worker has exited. Its passing cohort and archived readers remain frozen
  as the reference for the paired coupling-transfer study recorded above.

- **Pulse-spacing calibration completed at 13:55:22 UTC on 16 October**, in
  **1 h 22 min** including finalization. **CPU: 16 passed and one expected
  GPU-only skip; L4: 17 passed.** The
  [result](/mnt/workspaces/Cells/two-task-source-order-pulse-spacing-20261016-01/result.json)
  and [completion](/mnt/workspaces/Cells/two-task-source-order-pulse-spacing-20261016-01/completion.json)
  record **2,096 evidence entries and 34 required passing reports**, with
  **1,018 frozen sources**. Each backend completed **180 calibration worlds and
  860,160 world-steps**, following the
  [protocol](validation/assays/source_order_long/pulse_spacing_protocol.json).
  [Preparation](/mnt/workspaces/Cells/source-order-pulse-spacing-development-20261016-01/preparation.json)
  retained 10 passing checks, clean lint and full baseline authentication.

  **The later second pulse improves fitted calibration separation:** the fixed
  **128/160/320-us** primary score rises **1.953404 → 2.133483 nV (+9.219%)**,
  placing the minimum across both tasks, relevant arms and all three timesteps
  **0.133483 nV above the unchanged 2-nV margin**. CPU and L4 scores and choices
  agree exactly. The
  [selection](/mnt/workspaces/Cells/two-task-source-order-pulse-spacing-20261016-01/evidence/gpu/source-order-pulse-spacing-selection.json)
  freezes **104-us onset separation**, moving the second pulse from **104–112
  to 112–120 us** at unchanged width, per-source dose, observation support and
  reader. Comparator scores rise **1.854889 → 2.026129 nV** for spanning
  observations and **1.447416 → 1.590572 nV** for late-only observations; neither
  enters selection. **No held-out cases were evaluated: the prior 29/32 result
  remains unchanged.** Fitted-curve geometry is not a continuum or noise bound.

  The [CPU/L4 comparison](/mnt/workspaces/Cells/two-task-source-order-pulse-spacing-20261016-01/evidence/gpu/source-order-pulse-spacing-cpu-gpu.json)
  passed **2,182,733,040 state/field scalar comparisons** at unchanged tolerances.
  Conservation/domain, bitwise restart/reordering/partition, **480 historical
  window comparisons** and **38,340 unchanged feature scalars** passed. No-cue
  and disconnected calibration readers remain unresolved. All 57 paired
  contrasts missing the finest-step stability criterion belong to disconnected
  controls below the declared reader scale; active-arm contrasts meet it.

  **Whole L4 phase: 28.63% GPU busy and 9.65% measured SM-active**, both with
  **over 99.95% coverage**, across **0.651 GPU-hours**. These include compilation,
  host checks and archive handling. Per-arm kernel execution was **131–133 s**;
  total batch time was **266–365 s**, including **114–205 s** in archive handling.
  The [completion status](/mnt/workspaces/Cells/source-order-pulse-spacing-development-20261016-01/completion-status-20261016.json)
  binds the reviewed reports and records scores, checks and timings; it does
  not rerun the full archive audit. That worker has exited. The fresh-strength
  confirmation of this frozen timing is recorded above.

- **Selected-schedule diagnosis completed at 11:58:37 UTC on 16 October**, in
  **6 min 1 s**. The
  [result](/mnt/workspaces/Cells/two-task-source-order-selected-diagnosis-20261016-01/result.json)
  and [completion](/mnt/workspaces/Cells/two-task-source-order-selected-diagnosis-20261016-01/completion.json)
  authenticate **7,535 evidence files, 1,012 unchanged sources and 33 required
  passing reports**. All six panels, seven reader modes, fixed shuffles, both
  paired comparisons and reference-transfer reports replay exactly. CPU and
  saved L4 diagnoses are identical. No simulation or new reader candidate ran.

  **The three unresolved cases compete with opposite source order at a
  different strength, at the same location.** Supplying true strength as a
  diagnostic probe resolves **32/32**; supplying true location leaves **29/32**.
  Moving observations onto their known fitted curve gives **29/30/30** resolved
  cases across the three timesteps. That probe uses unavailable true labels and
  strength; it does not improve the accepted **29/32** result. Its extra finest-step
  case clears the margin by only **0.000104 nV**. The actual weakest-case deficit
  is **0.007081 nV**, against a finest-step score change of **0.006029 nV**;
  numerical sensitivity remains relevant, without a continuum-accuracy claim.
  The other two deficits are **0.045746 and 0.012165 nV**, with corresponding
  step changes **0.003175 and 0.003941 nV**.

  The gain is source-order 1 at strength **0.409375**: its incumbent-to-selected
  score rises **1.977897 → 2.040669 nV**. The regression is source-order 1 at
  **0.509375**: **2.046131 → 1.987835 nV**. Both have location 0, and both paired
  outcomes persist across all three timesteps. The timing change trades which
  cases clear the margin; it does not resolve the remaining strength ambiguity.

  The diagnosis motivated the
  [pulse-spacing plan](validation/assays/source_order_long/pulse_spacing_plan.json);
  its implementation and launch are recorded above. It tests a physical
  encoding change at unchanged dose, without guaranteeing full resolution.

  The [implementation](validation/assays/source_order_selected_diagnostic.py)
  reuses the existing geometry and timestep probes, adding identity-checked
  gain/regression summaries. [Preparation](/mnt/workspaces/Cells/source-order-selected-diagnosis-development-20261016-01/preparation.json)
  records **29 passing targeted checks**, clean lint and the preserved initial
  test-fixture failure. The
  [completion review](/mnt/workspaces/Cells/source-order-selected-diagnosis-development-20261016-01/completion-review.json)
  retains per-case scores, competing strengths, timestep sensitivity and source
  bindings. This saved-response diagnosis itself used no GPU workload and has
  no utilization measurement.

- **Fresh-strength confirmation completed at 18:23:03 UTC on 15 October**, in
  **3 h 39 min** including finalization. **CPU: 16 passed and one expected
  GPU-only skip; L4: 17 passed.** The
  [result](/mnt/workspaces/Cells/two-task-source-order-selected-20261015-01/result.json)
  and [completion](/mnt/workspaces/Cells/two-task-source-order-selected-20261015-01/completion.json)
  record **7,535 evidence entries**, following the
  [protocol](validation/assays/source_order_long/selected_protocol.json) and
  [registration](/mnt/workspaces/Cells/two-task-source-order-selected-20261015-01/registration.json)
  freezing **1,012 sources**. Each backend completed **660 worlds and 3,153,920
  world-steps**. The
  [CPU/L4 comparison](/mnt/workspaces/Cells/two-task-source-order-selected-20261015-01/evidence/gpu/source-order-selected-cpu-gpu.json)
  passed **8,003,354,480 scalar comparisons** at unchanged tolerances, with
  exact decision agreement. Conservation/domain, bitwise replay, restart,
  reordering, partition and historical-reproduction checks passed.

  **Confirmed outcome:** **128/160/320-us observations resolve both tasks in
  29/32 fresh joint cases**, matching **29/32** for **128/256/512 us** on the
  same cohort, with **one gain and one regression**. Late-only **320/384/512 us**
  gives **20/32**; selected versus late-only has **nine gains and no regressions**.
  Both backends agree across all three timesteps. Location resolves **32/32**,
  single-task arms resolve **16/16 each**, and no-cue/disconnected readers remain
  unresolved. The three remaining source-order cases have correct forced
  predictions but finest-step score magnitudes of **1.954–1.993 nV**, below the
  unchanged **2-nV margin**. Finest-step scores and decisions meet stability
  checks. The **32/32 joint target remains unmet**: the calibration geometry
  gain did not increase this cohort's resolved count. Eight new strengths
  **0.409375–0.790625**, the same five remote cells and the same 15-feature budget
  keep this comparison separate from the earlier frozen cohort.

  **Whole L4 qualification phase:** **33.51% GPU busy, 11.40% measured SM-active**,
  both with **over 99.98% coverage**, over **1.906 GPU-hours**. These averages
  include compilation, archive handling and host checks. Per-arm kernel
  execution was **467–486 s**; total batch time was **918–1,204 s**, including
  **381–660 s** in archive handling. The CPU/L4 comparison alone took
  **21 min 33 s**. These are single-L4 measurements, without a multi-GPU scaling
  claim. Recorded artifacts/cache occupy **34.51 GB**, and peak child RSS was
  **1.70 GB**.

  [Completion status](/mnt/workspaces/Cells/source-order-selected-development-20261015-01/completion-status-20261016.json)
  records the requested review, report-to-manifest bindings, outcomes, timings
  and utilization; it does not rerun the archive audit. The
  [preflight](/mnt/workspaces/Cells/source-order-selected-development-20261015-01/preparation.json)
  retained **nine passing checks** and the prior evidence/source authentication.
  The worker has exited and the L4 is idle. The completed saved-response
  diagnosis and next experimental design are recorded above.

- **Calibration-only observation-schedule study completed at 14:15:44 UTC on
  15 October**, in **4 min 32 s**, following **32 passing targeted checks** and
  a clean lint check. The
  [result](/mnt/workspaces/Cells/two-task-source-order-observation-design-20261015-01/result.json),
  [frozen selection](/mnt/workspaces/Cells/two-task-source-order-observation-design-20261015-01/selection.json)
  and [completion](/mnt/workspaces/Cells/two-task-source-order-observation-design-20261015-01/completion.json)
  bind the comparison to **7,533 authenticated evidence files, 1,004 unchanged
  sources and 31 required passing reports**. Both saved backends independently
  select **128/160/320 us** from all **35 schedules**, with identical candidate
  reports and no tie. Each backend loads **720 calibration arrays**, with
  **zero held-out response arrays decoded or evaluated**.

  The worst opposite-label fitted-curve half-distance improves from
  **1.854889 nV** for 128/256/512 us to **1.953404 nV** (**5.31%**); late-only
  320/384/512 us gives **1.447416 nV**. This uses the same five remote cells,
  15 features, calibration strengths and **2-nV reader margin**. The limiting
  pair is joint source order at location 0: strength **0.4** competes with
  opposite-order strength **0.47117**, at the coarsest timestep. The selected
  schedule's joint-order minimum remains **1.953–1.955 nV** across timesteps,
  below the margin. Thus this is a reproducible geometric improvement, without
  full-range fitted-curve separation or a new confirmed accuracy result.
  Calibration-only no-cue/disconnected controls remain unresolved throughout;
  their largest absolute score is **0.001500 nV** and they do not enter ranking.

  [Preparation](/mnt/workspaces/Cells/source-order-observation-design-development-20261015-01/preparation.json)
  covers closed-segment geometry, time/cell identity, the 35-schedule grid,
  fixed ties, backend disagreement reporting and unchanged rankings when
  held-out arrays and metadata are removed or made inaccessible. The
  [implementation](validation/assays/source_order_observation_design.py)
  uses saved observed voltages, avoiding the legacy reconstruction helper.
  [Inputs](/mnt/workspaces/Cells/two-task-source-order-observation-design-20261015-01/inputs.json),
  [log](/mnt/workspaces/Cells/source-order-observation-design-development-20261015-01/analysis.log)
  and [completion review](/mnt/workspaces/Cells/source-order-observation-design-development-20261015-01/completion-review.json)
  retain the rule, code, checks and selected-schedule binding. No simulation or
  new GPU workload ran; there is no new utilization measurement.

  The separate CPU/L4 confirmation on new strengths, including weak cues near
  0.4, is recorded above. The existing **29/32 versus 20/32** result and all
  unresolved cases remain unchanged. The geometric gain does not promise that
  every fresh case will clear the margin.

- **Saved-response diagnosis completed at 13:40:33 UTC on 15 October**, in
  **5 min 25 s**. The
  [result](/mnt/workspaces/Cells/two-task-source-order-spanning-diagnosis-20261015-01/result.json)
  and [completion](/mnt/workspaces/Cells/two-task-source-order-spanning-diagnosis-20261015-01/completion.json)
  authenticate **7,533 evidence files, 1,004 unchanged sources and 31 required
  passing reports** from the fresh-strength experiment. All five observation
  panels, seven reader modes, fixed shuffles, paired comparisons and
  reference-assisted reports replay exactly. CPU and saved L4 diagnoses are
  identical. The [diagnostic](validation/assays/source_order_spanning_diagnostic.py)
  uses saved voltage features; no simulation or new reader candidate ran.

  **All three unresolved cases compete with the opposite order at the same
  location but a different strength.** Supplying true strength as a diagnostic
  probe resolves **32/32**, while supplying true location leaves **29/32**, at
  every timestep. Moving each response onto its known calibration curve also
  leaves **29/32**. At the finest step, the three true-curve scores remain
  **1.889–1.945 nV**, below the unchanged **2-nV margin**. The finest-step score
  changes are **0.0017–0.0080 nV**, compared with margin deficits of
  **0.0649–0.1149 nV**. These probes support improving separation of order from
  unknown strength; they do not provide a new decoder result or a continuum
  bound. The accepted **29/32 versus 20/32** comparison remains unchanged.

  The [declared study plan](validation/assays/source_order_long/calibration_observation_plan.json)
  fixes **35 three-time schedules** drawn from seven already-recorded times
  after both cues. It ranks them using **calibration cases only**, by the
  worst separation of opposite-label fitted curves across tasks and timesteps,
  retaining the same five remote cells, 15 features and margin. The schedule
  must be frozen before any later evaluation analysis; another confirmation
  requires new strengths, including weak cues. The
  [plan check](/mnt/workspaces/Cells/source-order-spanning-diagnosis-development-20261015-01/design-plan-check.json)
  verified the candidate grid, feature budget and evidence bindings. The
  implementation, independent checks and comparison are recorded above.

  [Preparation](/mnt/workspaces/Cells/source-order-spanning-diagnosis-development-20261015-01/preparation.json)
  records **23 passing checks and one legacy reconstruction failure**: the old
  `unstimulated_diagnostic.voltage_history` helper still uses pre-repair charge
  arithmetic and differs from the current field by up to **4.52e-13 V** in its
  exact-equality test. This analysis uses recorded voltage features directly
  and does not call that helper. The failed evidence is preserved; updating
  the helper remains a separate maintenance item.

- **Fresh-strength confirmation passed CPU/L4 validation at 21:36:09 UTC on
  14 October; evidence finalization completed at 21:39:00 UTC**, after
  **2 h 28 min 36 s** from launch. The
  [run](/mnt/workspaces/Cells/two-task-source-order-spanning-20261014-01/launch.json)
  froze **1,004 sources and 16 checks per backend** under the
  [execution protocol](validation/assays/source_order_long/spanning_protocol.json).
  CPU passed **15 checks with one expected GPU-only skip** in **1 h 00 min 54 s**;
  L4 passed **all 16 checks** in **1 h 24 min 41 s**. Both completed **660 worlds
  and 3,153,920 world-steps**, with **630,784 world-steps per arm**. The
  [result](/mnt/workspaces/Cells/two-task-source-order-spanning-20261014-01/result.json)
  and [completion](/mnt/workspaces/Cells/two-task-source-order-spanning-20261014-01/completion.json)
  are present, no failure artifact was issued, and the worker has exited.

  **The new-strength result confirms an improvement, with three cases still
  unresolved.** Early/late observations at **128/256/512 us** resolve both tasks
  in **29/32 cases**, versus **20/32** for late-only **320/384/512-us** observations:
  **nine gains, zero regressions**, at all three timesteps on both backends.
  Location resolves **32/32**. Both panels use the same trajectories, 15 remote
  voltages, calibration and **2-nV margin**. All forced joint predictions are
  correct, but worlds **432030, 432031 and 432041** have order-score magnitudes
  **1.885–1.935 nV** at the finest step, below the required margin. These are weak
  cues at strengths **0.41875 and 0.46875**; the all-32-cases target remains unmet.
  Finest-step score/decision stability passes. Single-task controls each resolve
  **16/16**, while no-cue and disconnected controls remain unresolved. This is
  deterministic strength generalization in the same synthetic tissue.

  The [CPU/L4 comparison](/mnt/workspaces/Cells/two-task-source-order-spanning-20261014-01/evidence/gpu/source-order-spanning-cpu-gpu.json)
  passes for **8,003,354,480 scalar values**, with unchanged tolerances and exact
  reader-decision agreement. Each backend passes **1,672 bitwise history
  comparisons**, **97,980 exact feature values**, **75 unchanged calibration
  readers**, and restart/reordering checks. Maximum material error remains below
  **0.007 of budget**. Production physics is unchanged; accepted native BETSE
  evidence remains the calibration reference. The
  [requested status review](/mnt/workspaces/Cells/source-order-spanning-development-20261014-01/status-20261015-132059.json)
  authenticated result/registration bindings and **40 summary files**, including
  **31 required passing reports**; it did not repeat the full archive comparison.

  Whole L4-phase averages were **45.47% GPU-busy** and **15.37% measured
  SM-active**, with approximately **100% and 99.97% coverage**, over **1 h 24 min
  43 s** (**1.4120 GPU-hours**). These include compilation, host checks and archive
  I/O. GPU execution time per arm was closely matched at **452.88–453.09 s**;
  total arm times were **13 min 06 s–16 min 09 s**, with additional archive/check
  time in the no-cue arm. These are sequential L4 measurements, not concurrent
  multi-GPU results. The saved-response diagnosis is recorded above.

  [Preparation](/mnt/workspaces/Cells/source-order-spanning-development-20261014-01/preparation.json)
  completed **eight distinct checks** without simulating fresh responses.
  Seven passed initially; the resource check found the **119.26-GiB uncompressed
  archive estimate** exceeded the provisional 96-GiB cap. The
  [recorded correction](/mnt/workspaces/Cells/source-order-spanning-development-20261014-01/resource-revision.json)
  raises the cap to **144 GiB**, with about **408 GiB free** before launch.
  The [targeted recheck](/mnt/workspaces/Cells/source-order-spanning-development-20261014-01/preflight-02/pytest.xml)
  passed; the original failed log and check remain preserved. Complete unchanged
  calibration/null histories, common pre-cue histories, CPU/L4 agreement,
  conservation and bitwise restart/reordering checks are required in the run.
  Outputs stay under `/mnt/workspaces/Cells`; no automatic follow-up is scheduled.

- **Saved-response diagnosis completed at 17:50:11 UTC on 14 October** in
  **6 min 21 s**, following **24 targeted checks**. The
  [result](/mnt/workspaces/Cells/two-task-source-order-long-diagnosis-20261014-01/result.json)
  and [completion](/mnt/workspaces/Cells/two-task-source-order-long-diagnosis-20261014-01/completion.json)
  bind the analysis to the accepted precision repair: **4,887 evidence files**,
  **998 unchanged sources** and **69 required passing reports** authenticated.
  All four original readout panels and reference-assisted reports replay
  exactly; CPU and saved L4 diagnostic results are also identical. No new
  simulation or GPU workload ran.

  **The remaining late-only ambiguity is between source order and cue strength.**
  All eight unresolved order cases compete with the opposite order at the same
  location but another strength. Supplying the true location still resolves
  **8/16**; supplying the true strength resolves **16/16**, at every timestep.
  Moving observations onto their known calibration curves still resolves only
  **8/16**, so interpolation error does not explain the missing cases. These
  are diagnostic probes using unavailable information, not new reader results.

  One explicitly exploratory panel at **128/256/512 us**, using the same **15
  remote-cell voltages**, unchanged reader and **2-nV margin**, resolves both
  tasks in **15/16 cases** on all three timesteps and both saved backends.
  Location resolves **16/16**; single-task controls resolve **8/8** each; no-cue
  and disconnected controls remain unresolved. World **412031** still fails
  the margin, with finest-step order score **1.858 nV**. All original cases,
  shuffles and the original **8/16 late-only primary result** remain recorded.
  This improvement on already-inspected cases is not a fresh confirmation.

  The [saved confirmation design](validation/assays/source_order_long/spanning_confirmation_plan.json)
  fixed eight new strengths across both calibration intervals, including weak
  cues near 0.4, before generating any of their responses.
  [Design checks](/mnt/workspaces/Cells/source-order-long-diagnosis-development-20261014-01/confirmation-plan-check.json)
  verified the disjoint strengths, identities, counts and evidence bindings
  without simulating responses. Its implementation, resource-cap correction
  and launch are recorded above; the saved design remains unchanged.

- **Charge-precision repair passed full CPU/L4 validation at 14:47:59 UTC on
  14 October**, after **2 h 28 min 43 s**; evidence finalization completed at
  **14:50:45 UTC**. The detached
  [run](/mnt/workspaces/Cells/two-task-source-order-precision-20261014-01/launch.json)
  launched at **12:19:15 UTC**, freezing **998 sources and 35 checks per backend**.
  CPU passed **34 checks with one expected GPU-only skip** in **1 h 15 min 56 s**;
  L4 passed **all 35 checks** in **1 h 12 min 35 s**. Both completed all **420
  assay worlds**, or **2,007,040 world-steps per backend**. The previously failing
  [CPU/L4 comparison](/mnt/workspaces/Cells/two-task-source-order-precision-20261014-01/evidence/gpu/source-order-long-cpu-gpu.json)
  now passes for **5,093,043,760 scalar values**, with unchanged tolerances.
  [Result](/mnt/workspaces/Cells/two-task-source-order-precision-20261014-01/result.json)
  and [completion](/mnt/workspaces/Cells/two-task-source-order-precision-20261014-01/completion.json)
  are present; no failure artifact was issued. The
  [requested status review](/mnt/workspaces/Cells/source-order-long-numerics-20261014-01/status-20261014-173500.json)
  verified the result/registration bindings and **75 completed JSON report
  hashes**. It did not repeat the completed runner's full archive comparison.

  All **18 native BETSE reference comparisons passed on each backend**:
  **64,038,912 values per backend**, with maximum error **0.3086 of budget on
  CPU** and **0.3090 on L4**. The corresponding **64,092,516 CPU/L4 values**
  also pass. The primary scientific result remains **16/16 location cases**
  and **8/16 source-order/both-task cases** above the unchanged margin at all
  three timesteps on both backends. All **960 matched/frozen reader comparisons**
  have identical CPU/L4 scores and decisions. Longer observation has therefore
  not met the combined-task target, despite successful numerical validation.
  The completed diagnosis and controlled follow-up design are recorded above.

  All **980 older prefix-window comparisons** and **89,460 earlier feature
  values per backend** pass their physical tolerances; they are no longer
  bitwise identical. Earlier reader-decision changes are confined to the
  disconnected control (**29 CPU and 28 L4 comparison groups**); the earlier
  primary joint decisions remain unchanged. New restart, windowing, reordering
  and partition checks pass bitwise. Maximum material error remains below
  **0.007 of budget**.

  Whole L4-phase averages were **34.10% GPU-busy** and **11.68% measured
  SM-active**, both with approximately **100% coverage**, over **1 h 12 min 39 s**
  (**1.2107 GPU-hours**). The
  [telemetry](/mnt/workspaces/Cells/two-task-source-order-precision-20261014-01/gpu-metrics/result.json)
  includes compilation, host verification and archive I/O; no single warmed
  interval is defined. Sequential GPU arm totals range from **10 min 11 s to
  11 min 26 s**; these are not measurements of concurrent multi-GPU execution.

  The [archive audit](/mnt/workspaces/Cells/source-order-long-numerics-20261014-01/full-archive-audit.json)
  compared **5,093,043,760 scalar values** and authenticated **4,760 archive
  inputs**. Failures were confined to the activation gate in **30 of 420 worlds**;
  every other state/field passed its existing tolerance. The first failure was
  joint world **412043**, at **473.25 us** with **0.125-us** steps. The worst gate
  discrepancy was **1.1059 times its allowed error**. Higher-precision replay
  and focused experiments traced this to cancellation in the ionic charge sum
  driving voltage; changing the gate recurrence alone did not resolve it.

  [Compensated charge summation](src/cells/numerics/betse_spatial.py) now sums
  signed concentrations before multiplying by Faraday's constant, with compiler
  barriers retaining the cancellation residuals. This is the same physical
  equation; no physical parameter, control, gate law, clock, state or tolerance
  changed. It is the **only production file changed**. In three representative
  failing worlds, every corrected CPU/L4 state/field comparison passed; the
  largest gate discrepancy fell below **0.5% of its allowed error**. A difference
  from one already-failed original L4 history remains explicitly recorded.

  [Preparation](/mnt/workspaces/Cells/source-order-long-numerics-20261014-01/preparation.json)
  passed **10 checks in 3 min 54 s**, including independent **80-digit Decimal**
  charge answers, compiled cancellation cases, assay input/resource checks and
  evidence authentication. A corrected 512-us native BETSE comparison passed
  for **6,098,944 values**, with maximum error **0.2711 of budget**. The full run
  compared against all 18 authenticated native captures using unchanged tolerances.

  The [repair protocol](validation/assays/source_order_long/precision_protocol.json)
  retains the same assay cases, pulses, observations, reader and **2-nV margin**.
  Older accepted 256-us prefixes must satisfy their existing physical tolerances;
  exactness and every earlier reader-decision difference are reported separately.
  New restart/reorder/partition checks remain bitwise. Original failed evidence
  stays frozen. Both GPU-busy and measured SM-active, their coverage and arm
  timings are recorded. Outputs remain under `/mnt/workspaces/Cells`; the worker
  has exited and no automatic follow-up is scheduled.

- **512-us source-order follow-up failed its final CPU/L4 comparison at
  01:06:00 UTC on 14 October**, after **2 h 3 min 30 s**. CPU passed **14
  tests with one expected GPU-only skip** in **58 min 55 s**. L4 completed all
  **420 simulation worlds**, then finished with **14 passed, one failed** in
  **1 h 4 min 23 s**. The
  [failure artifact](/mnt/workspaces/Cells/two-task-source-order-long-20261013-01/failure.json),
  [pytest failure](/mnt/workspaces/Cells/two-task-source-order-long-20261013-01/gpu.stdout.log)
  and [requested status verification](/mnt/workspaces/Cells/source-order-long-development-20261013-01/failed-status-20261014-01.json)
  preserve the outcome. **No result/completion certificate was issued.**

  The first reported mismatch is the dimensionless channel activation variable
  `active__m_gate`: **1,184 of 30,750 values** in the reported chunk exceed
  `atol=2e-13, rtol=2e-12`, with maximum absolute discrepancy among those
  violations **7.54674101e-13**. The comparison stopped there; this is not a
  full-archive maximum from that stopped comparison. The subsequent complete
  audit, diagnosis and correction are recorded above. Tolerances and the frozen
  failed evidence remain unchanged.

  **Preliminary scientific result:** at the later observations, location clears
  the unchanged margin in **16/16** joint cases, but source order and both tasks
  together clear it in **8/16**, on both backends at all three timesteps. Forced
  predictions are correct for all 16; eight source-order scores remain below
  the required margin. Score stability and decisions agree across the finest
  timesteps. Thus longer observation alone has not met the combined-task target;
  the earlier primary resolved both tasks in 11/16 at the finest step. Single-task
  controls still resolve **8/8** each. Both backends reproduced all **980 old
  history-window comparisons bitwise**, all **89,460 earlier feature values**
  exactly, and the complete earlier reader reports. Material error remains below
  **0.007 of budget**. These partial scientific reports survive the failed final
  acceptance check; complete CPU/L4 agreement is not certified.

  Whole L4-phase averages were **35.80% GPU-busy** and **13.00% measured SM-active**,
  both with **100% coverage**, over **1 h 4 min 28 s** (**1.0745 GPU-hours**).
  [Telemetry](/mnt/workspaces/Cells/two-task-source-order-long-20261013-01/gpu-metrics/result.json)
  includes compilation, host verification and archive I/O; no single warmed
  interval is defined. That worker exited without an automatic retry.

  The experiment launched at **23:02:29 UTC on 13 October**. Its
  [registration](/mnt/workspaces/Cells/two-task-source-order-long-20261013-01/registration.json)
  froze **994 source files and 15 checks**. The status verification confirmed
  those sources unchanged, both test inventories, all **28 earlier passing
  reports** unchanged and the telemetry hashes. It did not repeat the full
  state-archive comparison. The earlier
  [in-progress snapshot](/mnt/workspaces/Cells/source-order-long-development-20261013-01/status-20261014-010344.json)
  remains preserved.

  The [protocol](validation/assays/source_order_long/protocol.json) fixes new
  primary observations at **320/384/512 us**, with the same pulses, per-source
  doses, strengths, reader, **15 unstimulated-cell voltages** and **2-nV margin**.
  It asks whether longer observation separates the previously overlapping
  responses. These are reused cases in a paired follow-up, not fresh holdouts.
  Complete histories and restart/partition checks extend through 512 us.
  Scientific resolution remains separate from numerical acceptance.

  [Preparation](/mnt/workspaces/Cells/source-order-long-development-20261013-01/preparation.json)
  passed **seven host checks in 1 min 40 s**, including predecessor authentication,
  exact physical inputs/doses, resource bounds and synthetic reader/archive checks.
  All **991 preceding sources** remain unchanged; no response simulation ran
  before registration. Each backend has **2,007,040 world-steps**, equally divided
  across five arms (**401,408 each**). Actual arm timings, both utilization
  measurements, complete state archives and failure logs remain under
  `/mnt/workspaces/Cells`.

- **512-us dynamic-junction qualification completed at 21:24:26 UTC on 13 October**,
  after **2 h 44 min 29 s**; evidence finalization finished at **21:24:37 UTC**.
  The [result](/mnt/workspaces/Cells/betse-junction-runtime-20261013-02/result.json),
  [completion](/mnt/workspaces/Cells/betse-junction-runtime-20261013-02/completion.json)
  and [completed-status check](/mnt/workspaces/Cells/junction-runtime-512-development-20261013-01/completed-status.json)
  preserve the outcome. CPU passed **365 tests with two expected GPU-only skips**
  in **2 h 4 min 5 s**; L4 passed **all 367** in **39 min 48 s**. No failure
  artifact or worker/test stderr output was produced. The read-only completion
  check verified **378 evidence hashes, 991 frozen/current sources and 104
  required passing reports**, including the test inventories and telemetry.

  All **18 native BETSE observed/bare pairs** completed. Each backend passed
  **64,038,912 native state/field comparisons** through 512 us, with unchanged
  physical tolerances; maximum error was **0.3922 of budget** across CPU/L4.
  Material error stayed below **0.007 of budget**. The direct CPU/L4 comparison
  passed for **64,092,516 scalar values**. All twelve original 64-us and eighteen
  256-us ordinary-runtime prefixes were **bitwise identical** on each backend.
  Native trace prefixes also matched bitwise, excluding the duration-dependent
  native sample labels; completed-step controls remained exact. All fourteen
  state arrays passed disk restart, windows, changed-future branches and world
  reordering/partition checks, including **64/256-to-512-us continuations**.

  **The configured dynamic-junction runtime is now qualified through 512 us**
  for these six fixed synthetic cases at **1/0.5/0.25-us timesteps**. This retains
  BETSE's per-moving-ion junction clock, maintained ATP/ADP/Pi and one Kv1p5
  population; it adds no longer-time, spatial-convergence or new temporal-order
  claim. Half-block remains the timestep-dependent native prescription. The
  [preparation](/mnt/workspaces/Cells/junction-runtime-512-development-20261013-01/preparation.json)
  preserves 62 passing host checks, the CPU smoke, and the initial rejected
  padded-storage estimate and its correction. Physics and tolerances are unchanged.

  Whole L4-phase averages were **1.69% GPU-busy** and **0.573% measured SM-active**,
  with **99.99997% / 100% coverage** respectively, over **40 min 4 s**. These
  include compilation, host verification, restart/I/O checks and idle intervals;
  no single warmed interval is defined. GPU-phase use was **0.6677 GPU-hours**.

- **Saved-data source-order diagnosis completed at 17:47:35 UTC on 13 October**,
  after **3 min 22 s** on CPUs 4/5 with an attached watcher. The
  [result](/mnt/workspaces/Cells/two-task-source-order-diagnosis-20261013-01/result.json),
  [completed-status check](/mnt/workspaces/Cells/source-order-diagnosis-development-20261013-01/completed-status.json)
  and [diagnostic figure](/mnt/workspaces/Cells/source-order-diagnosis-development-20261013-01/source-order-diagnosis.png)
  preserve the findings. The
  [preparation](/mnt/workspaces/Cells/source-order-diagnosis-development-20261013-01/preparation.json)
  passed **39 checks: 11 new known answers and 28 inherited checks**. Full
  predecessor authentication verified **989 sources, 2,853 evidence hashes and
  29 passing reports**. All preceding sources and the two diagnostic sources
  remain unchanged. No simulation or GPU workload ran.

  **The joint task is limited by overlapping remote responses.** At the finest
  timestep, the mean location and order contrasts have cosine similarity
  **0.9596–0.9598**. Reversing both labels can therefore produce similar
  observations. Four weak cases (**412031/32 and 412041/42**) have a nearest
  competing curve with both labels reversed. The weakest pair, **412031/32**,
  is separated by only **3.371 nV L2** across the 15 primary features, below
  the **4-nV necessary separation** for both opposite-label cases to clear
  this reader's 2-nV margin. It remains below that condition at all three
  timesteps. Pair distance is a necessary condition, not a sufficient decoder.

  Strength ambiguity also matters. Supplying true strength in an oracle probe
  resolves **14/16 for each task**; supplying the true other label resolves
  **16/16 location and 13/16 order**. These probes use withheld information and
  are not replacement readers. Moving observations onto their known calibration
  curves changes finest-step scores by at most **0.0168 nV**, leaving the
  **12 location / 11 order** counts unchanged. Case **412052** retains a weak
  order score with a same-location, different-order/strength competitor.

  The borderline case **412051** remains timestep-sensitive after no-cue
  reference subtraction. Its middle-to-finest feature drift falls from
  **49.463 nV** to **0.03152 nV L2**, but the signed score magnitude still moves
  **1.997535 → 2.005961 nV** across the unchanged threshold. The existing
  **11/16 joint**, and **10/16 joint at every timestep**, result remains fixed.
  All original readers, shuffles and reference transfers replay with **zero
  numeric difference** within each backend. Reconstructing **84 joint
  trajectories per backend** reproduces patch observations exactly and reader
  features within **6.94e-18 V**. CPU/L4 diagnostic counts and case identities agree.

  **A longer observation window is now a supported follow-up hypothesis for
  this source-order task:** the crossed-label remote contrast grows
  **2.667–2.686 times from 192 to 256 us**, and its largest saved value occurs
  at the 256-us endpoint. This describes the observed interval; it does not
  establish growth beyond it. The method and limitations are in
  [the assay document](docs/TWO_TASK_READOUT_ASSAY.md#location-allocation-and-source-pulse-order).
  This motivates the **512-us runtime qualification above**, followed by a paired
  source-order experiment with fixed later observations, unchanged pulses/doses
  and the same margin. That experiment has not yet launched.

- **Location and source-pulse order completed at 17:10:35 UTC on 13 October**,
  after **65 min 6 s**; evidence finalization finished at **17:11:30 UTC**.
  The [result](/mnt/workspaces/Cells/two-task-source-order-20261013-01/result.json),
  [completion](/mnt/workspaces/Cells/two-task-source-order-20261013-01/completion.json)
  and [completed-status check](/mnt/workspaces/Cells/source-order-development-20261013-01/completed-status.json)
  preserve the outcome. CPU acceptance passed **14 tests with one expected
  GPU-comparison skip in 31 min 30 s**; L4 passed **all 15 in 33 min 25 s**.
  No failure artifact or stderr output was produced. All **989 current and
  frozen sources**, **29 required reports**, XML inventories and telemetry
  hashes passed the status check. Completion binds **2,853 evidence files**;
  this status check did not re-read the full state archives.

  **Scientific target remains unmet.** Both backends give correct forced
  choices for both labels in **16/16** primary cases. At the fixed **2-nV**
  margin, **12/16 location**, **11/16 source-order**, and **11/16 jointly** are
  correct and resolved. Only **10/16** pass both tasks at every tested timestep.
  Borderline case **412051** changes from **1.997535 nV** at the middle timestep
  to **2.005961 nV** at the finest for both tasks. Scores meet the declared
  change limits, but these resolution decisions change. The two single-task
  arms each resolve **8/8**; disconnected and no-cue primary readouts resolve
  none. Combining the tasks remains the weak point. This is the new
  [source-order task](docs/TWO_TASK_READOUT_ASSAY.md#location-allocation-and-source-pulse-order),
  preserving the preceding common early/late classification as a separate result.

  Numerical acceptance covers **420 worlds and 1,003,520 world steps per
  backend**, with equal steps per arm. The CPU/L4 comparison passed for
  **2,547,081,320 scalar values** with unchanged tolerances. All **580**
  historical comparisons per backend were bitwise equal, including **120**
  unchanged full worlds and **300** common prefixes; unchanged features and
  restart/reordering/partition replay also passed. Conservation remained
  within budget. Primary decisions and joint shuffle metrics agree across
  backends. One forced label differs in an alternative disconnected-arm
  centroid reader, and two disconnected contrast stability flags differ;
  these nonprimary discrepancies remain explicit in the saved comparison.

  Baseline subtraction leaves matched distances, scores and decisions
  **exactly unchanged** at all three timesteps on both backends. All nine
  reference-assisted timestep transfers agree in CPU/L4 decisions; they
  resolve **10 or 11 joint cases**, supplying target-timestep no-cue information.
  They do not complete the primary target. The
  [preparation](/mnt/workspaces/Cells/source-order-development-20261013-01/preparation.json)
  fixed the new evaluation strengths before response simulation and passed
  seven checks; all **986 predecessor assay and diagnostic sources** remain
  unchanged.

  Whole L4-phase utilization was **34.65% GPU-busy** and **12.53% measured
  SM-active**, with **99.99999% / 99.9355% coverage**, respectively. These include
  compilation, host checks and idle intervals; no single warmed interval is
  defined. GPU-phase use was **0.5578 GPU-hours**. The L4 is now idle.

  The saved-data diagnosis above follows up the five unresolved joint cases
  and the shared timestep-borderline case.

- **No-cue baseline transfer diagnosis completed at 14:49:26 UTC on 13 October**,
  after **2 min 46 s**, with an attached watcher. The
  [result](/mnt/workspaces/Cells/two-task-baseline-transfer-20261013-01/result.json)
  and [completed-evidence check](/mnt/workspaces/Cells/baseline-transfer-development-20261013-01/completed-status.json)
  preserve all nine timestep transfers on CPU and L4 saved data. The
  [preparation](/mnt/workspaces/Cells/baseline-transfer-development-20261013-01/preparation.json)
  passed **seven known-answer checks**. All **982 assay sources**, the preceding
  diagnosis's **two sources**, and the **two new diagnostic sources** match their
  saved hashes; predecessor authentication verified **2,849 evidence hashes and
  25 passing reports**. No simulation or GPU workload ran.

  **Shared background drift accounts for almost all of the apparent timestep
  change in the joint evaluation features.** Between **0.125 and 0.0625 us**,
  the no-cue background changes by **49.487 nV L2**. Raw joint-case drift is
  **49.464–49.520 nV L2**; subtracting the reference leaves **0.02129–0.06203 nV**,
  reducing its norm by **99.875–99.957%**. Both backends give these same ranges.
  The reference is calibration control **314000** at each timestep; all **28
  duplicate no-cue controls** match exactly. Stimulated responses, strengths
  and evaluation labels do not fit the reference.

  Reference-assisted transfer gives **16/16 correct forced choices for both
  tasks in every timestep combination**, and **16/16 resolved location cases**.
  For a coarsest-step reader applied to finest-step data, cases with both tasks
  correct and resolved improve from **3/16 to 8/16**. Timing remains **8 or 9/16**
  across transfers: borderline case **312043** scores **1.998862 nV** with the
  coarsest reader and **2.002869 nV** with the middle-step reader on finest data.
  These comparisons use a target-timestep no-cue control, not transfer without
  target-domain information. Joint transfer counts and borderline scores agree
  on CPU and L4; all control-arm outcomes remain in the result.

  Matched calibration is **exactly invariant**: distances, scores and decisions
  are unchanged for all five arms at all three steps on both backends. Original
  matched/frozen-coarse reports also replay with **zero numeric difference**.
  Therefore the original primary result stays **16/16 location and 9/16 timing**,
  with only **eight timing cases** resolved at every tested step. This diagnoses
  numerical background drift; it does not solve timing/strength ambiguity or
  establish a continuum bound. The
  [method and checks](docs/TWO_TASK_READOUT_ASSAY.md#wider-cue-separation-at-fixed-dose)
  document that distinction. The source-order experiment above follows this
  diagnosis; this early/late classification remains an incomplete result.

- **Saved-data timing diagnosis completed at 14:19:00 UTC on 13 October**,
  after **4 min 6 s** on CPUs 4/5. The
  [result](/mnt/workspaces/Cells/two-task-cue-separation-diagnosis-20261013-01/result.json)
  and [completed-evidence check](/mnt/workspaces/Cells/cue-separation-diagnosis-development-20261013-01/completed-status.json)
  bind the saved inputs, diagnostic sources and reconstructed histories.
  All **982 predecessor sources and two diagnostic sources** remain unchanged;
  [preparation](/mnt/workspaces/Cells/cue-separation-diagnosis-development-20261013-01/preparation.json)
  passed **21 host checks**. The diagnosis authenticated the preceding run's
  **2,849 evidence hashes and 25 required reports**. No failure artifact or
  stderr output was produced.

  **Timing is strongly confounded with cue strength in this encoding.** On both
  backends, all eight evaluation timing pairs exceed the necessary **4-nV**
  separation, with feature distances **5.573–12.571 nV**. Nevertheless,
  **83.96–95.69% of squared timing contrast** lies along the opposing curve's
  local strength direction. The closest wrong-timing curve always keeps the
  correct location label. Its projection reaches a calibration-segment endpoint
  in **14/16 cases**, so the restricted calibration range also matters.
  Removing the same-strength calibration residual in an oracle probe changes
  scores by at most **0.02381 nV** and still resolves only **9/16** timing cases.
  Known labels and strengths enter these probes only; they are not new readers.

  The timing contrast peaks around **111.375–112.750 us**, near the late cue's
  end, and decreases **1.11–2.57%** between 192 and 256 us. This observed interval
  supplies no evidence that simply waiting longer will resolve timing. The
  **seven unresolved cases and one timestep-borderline case remain unchanged**;
  only **eight timing cases** clear the margin at all three tested steps.

  The borderline case **312043** moves from **1.99423 to 2.00186 nV** between
  the finest steps. Its voltage-feature change is **49.477 nV L2**. Holding the
  earlier reader fixed changes its score by **-6.33191 nV**; changing calibration
  then contributes **+6.33953 nV**. Reversing the order gives **+0.206615** and
  **-0.198988 nV**. Both paths yield the same **+0.007626 nV** net change.
  Matched-calibration score stability therefore does not establish fixed-reader
  transfer across timesteps, and neither decomposition is a continuum bound.

  All seven original reader modes, shuffles and matched/frozen reports across
  three panels and three timesteps reproduce with **zero numeric difference**
  within each backend. Reconstruction covers **84 joint histories per backend**:
  saved patch voltages match exactly; area-weighted reader features differ by
  at most **6.94e-18 V**, within the inherited replay tolerance. The
  [method](docs/TWO_TASK_READOUT_ASSAY.md#wider-cue-separation-at-fixed-dose)
  describes these post-hoc limits. No new simulation or GPU workload ran;
  the L4 remains idle and the original scientific target remains unmet.

  **Next: use the saved no-cue controls to measure shared background drift and
  test fixed-reader transfer after referencing that baseline.** This diagnostic
  must preserve matched-reader scores and cannot itself remove timing/strength
  ambiguity. A new cue/readout experiment must be specified separately before
  claiming better timing discrimination. The subsequently authorized baseline
  transfer diagnosis is completed above.

- **The fixed-dose cue-separation assay completed at 05:25:05 UTC on 13 October**,
  after **57 min 48 s**; evidence finalization finished at **05:26:05 UTC**.
  The [result](/mnt/workspaces/Cells/two-task-cue-separation-20261013-01/result.json)
  records **12 CPU passes / one expected GPU-comparison deferral** and
  **13 L4 passes**, with **420/420 worlds complete on each backend** and no
  failures or errors. CPU tests took **24 min 45 s**, L4 tests **32 min 54 s**.

  The [completed-evidence check](/mnt/workspaces/Cells/cue-separation-development-20261013-01/completed-status.json)
  authenticates **2,849 evidence hashes**, all **25 required passing reports**
  and **982 unchanged current sources**, including all **141 production files**.

  **Both backends confirm improved timing, but the complete two-task target
  remains unmet.** At the fixed primary finest-step endpoint, location resolves
  **16/16 cases** and timing **9/16**, up from **0/16 timing cases** in the prior
  assay. Both tasks give **16/16 correct forced choices**. Location scores span
  **2.399–8.479 nV** and timing **1.009–5.958 nV** against the fixed **2-nV margin**.
  Eight timing cases clear the margin at both finest steps; one borderline case
  moves from **1.9942 to 2.0019 nV**, changing resolved status without changing
  its predicted label. Score-stability limits pass, but finest-step decision
  agreement does not. The earlier panels cannot replace the primary endpoint.

  [CPU/L4 comparison](/mnt/workspaces/Cells/two-task-cue-separation-20261013-01/evidence/gpu/cue-separation-cpu-gpu.json)
  passes across **2,547,081,320 values** with unchanged physical tolerances.
  Primary joint decisions and all **288 shuffle comparisons** agree. Overall
  exact decision agreement is **false**: some forced labels in disconnected
  controls differ at scores below **0.00051 nV**, remaining unresolved on both
  backends. Three near-zero disconnected timing contrasts also differ in their
  relative-stability flags. These differences remain in the report. The largest
  decoder-score discrepancy is **0.000610 nV**, and the worst paired-contrast
  discrepancy uses **0.227%** of its physical allowance.

  All **812 historical window/prefix comparisons per backend** are bitwise,
  covering **294 unchanged full worlds** and **126 changed-world common prefixes**
  across the three timesteps. Unchanged features and unchanged-arm reader reports
  reproduce exactly. Controls, conservation/domain checks and replay of all
  **14 state arrays** pass, including a disk restart at **103.9375 us** across
  the delayed on/off events with **257-step** windows. The largest material
  residual uses **0.653%** of its allowance.

  [GPU measurements](/mnt/workspaces/Cells/two-task-cue-separation-20261013-01/gpu-metrics/result.json)
  cover **1,976.39 s / 0.5490 GPU-hours**: mean GPU-busy **35.123%** and measured
  SM-active **12.727%**, with **99.99996% / 99.94965%** coverage respectively.
  These whole-phase averages include compilation, host checks and idle time;
  there is no separate warmed-throughput interval. Peak worker RSS was
  **1.419 GiB** and retained artifacts/cache **10.069 GiB**, within limits.

  The [protocol](validation/assays/cue_separation_protocol.json) changes only
  the late pulse in **42 of 140 inspected case inputs**, from **24–32 us to
  104–112 us**, preserving the early **8–16-us** cue, each source's integrated
  dose and the reader algorithm. Primary observation times stay **160/192/256 us**,
  with **15 unstimulated-cell features**. Every arm has the same **200,704
  world-step** budget per backend. Earlier panels contain pre-late-cue samples
  and remain descriptive comparisons. The
  [method](docs/TWO_TASK_READOUT_ASSAY.md#wider-cue-separation-at-fixed-dose)
  records these limits; these are synthetic results on inspected strengths.
  [Preparation](/mnt/workspaces/Cells/cue-separation-development-20261013-01/preparation.json)
  preserves five passing host checks and the temporary-directory failure/retry.

  **Next: diagnose the seven unresolved timing cases and the borderline case
  using saved trajectories before choosing another intervention.** Keep this
  endpoint, scores and failed scientific target frozen. The L4 was idle at
  closeout. The subsequently authorized saved-data diagnosis is recorded above.

- **The longer-observation assay completed at 03:49:55 UTC on 13 October**,
  after **1 h 5 min 55 s**; evidence finalization finished at **03:50:57 UTC**.
  The [result](/mnt/workspaces/Cells/two-task-long-observation-20261013-01/result.json)
  records **11 CPU passes / one expected GPU-comparison deferral** and
  **12 L4 passes**, with **420/420 worlds complete on each backend** and no
  failures. The [registration](/mnt/workspaces/Cells/two-task-long-observation-20261013-01/registration.json)
  binds **979 sources, 12 test nodes per backend and 23 required reports**.
  The [completed-evidence check](/mnt/workspaces/Cells/long-observation-development-20261013-01/completed-status-20261013T040626Z.json)
  authenticates **2,841 evidence hashes**, all **23 passing reports** and
  **979 unchanged current sources**, including all **141 production files**.

  **Longer observation resolves location, but the two-task target remains unmet.**
  On both CPU and L4, the short/middle/long panels resolve **0/12/16 of 16
  location cases**, while timing remains **0/16** throughout, at every tested
  timestep. At the finest step, primary long-panel location scores are
  **4.121–8.476 nV** and timing scores **0.092–0.457 nV**, against the unchanged
  **2-nV margin**. Both tasks give correct forced choices in all 16 cases;
  timing does not clear the margin. Primary finest-pair score stability and
  decisions pass the registered criteria. These are synthetic results on
  previously inspected cases, not fresh generalization or biological validation.

  [CPU/L4 comparison](/mnt/workspaces/Cells/two-task-long-observation-20261013-01/evidence/gpu/long-observation-cpu-gpu.json)
  passes across **2,547,081,320 values** with unchanged physical tolerances;
  decoding decisions and all **288 shuffle comparisons** agree exactly.
  The worst paired-contrast discrepancy uses **0.227%** of its allowance.
  All **140 original 64-us prefixes per backend** reproduce bitwise, with exact
  historical reader/shuffle reports. Controls, conservation/domain checks and
  long disk/window/reorder/partition replay of all **14 state arrays** pass.
  The largest material residual uses **0.653%** of its allowance.

  The [protocol](validation/assays/long_observation_protocol.json) keeps the
  same **140 cue cases**, doses, tissue, initial state and reader algorithm,
  at **0.25/0.125/0.0625-us** timesteps through **256 us**. Each backend executes
  **1,003,520 world-steps**, equally divided among five arms. Each observation
  panel has **15 unstimulated-cell features**: primary **160/192/256 us** and
  comparison **40/48/64 us** / **80/96/128 us**. Matched and frozen-coarse
  calibration and all inherited reader modes remain reported. The
  [method](docs/TWO_TASK_READOUT_ASSAY.md#longer-observations-with-the-same-cues)
  separates numerical acceptance from the scientific outcome.

  [GPU measurements](/mnt/workspaces/Cells/two-task-long-observation-20261013-01/gpu-metrics/result.json)
  cover **1,913.22 s / 0.5314 GPU-hours**: mean GPU-busy **36.009%** and measured
  SM-active **13.136%**, with **99.99984% / 100%** coverage respectively.
  These whole-phase averages include compilation, host checks and idle time;
  there is no separate warmed-throughput interval. Peak worker RSS was
  **1.412 GiB** and retained artifacts/cache **10.068 GiB**, within limits.
  [Preflight and development evidence](/mnt/workspaces/Cells/long-observation-development-20261013-01)
  retain the five passing preparation checks and earlier failed evidence.

  **Next: separately test greater cue-timing separation at fixed dose.** Waiting
  longer improved location but did not resolve timing. Keep this result and
  the decision margin frozen. The L4 was idle at closeout; no follow-up job
  was launched or scheduled automatically. The subsequently authorized
  cue-separation assay is now completed above.

- **The 256-us ordinary dynamic-junction qualification completed at 02:11:52 UTC
  on 13 October**, after **42 min 41 s**. The
  [result](/mnt/workspaces/Cells/betse-junction-runtime-20261013-01/result.json)
  records **356 CPU passes / two expected GPU deferrals** and **358 L4 passes**,
  with no failures or errors. The
  [completed-evidence check](/mnt/workspaces/Cells/betse-junction-runtime-development-20261013-01/completed-status-20261013T022050Z.json)
  authenticates **976 unchanged sources, 168 evidence hashes and 98 passing
  reports**, including the frozen test inventory and GPU counter records.

  All **18 long junction trajectories pass on both backends**, including
  **32,019,456 values per backend** against each of the saved native and component
  targets. The worst native discrepancy uses **18.38% of its tolerance on CPU**
  and **22.39% on L4**. All **12 original 64-us prefixes per backend** are bitwise
  unchanged; long disk/window/world replay and the 64-to-256-us continuation pass.
  Direct CPU/L4 agreement passes across **32,073,060 junction-runtime values**,
  plus **17,994,704 values** from the existing active runtime. All shared
  regressions pass. The largest material residual uses **0.653% of its registered
  physical/roundoff allowance**.

  The [updated runtime protocol](validation/betse/spatial_active/junction_runtime_protocol.json)
  covers all **six cases at three timesteps** through **256 us**, comparing
  complete ordinary state/field histories directly with authenticated saved
  BETSE captures and the completed array component. It also checks the twelve
  original **64-us** prefixes, all **14 state arrays** through long restarts,
  windows, branches and independent-world replay, and existing shared regressions.
  Production changes are limited to the parser horizon and summary wording;
  numerical kernels, physical tolerances and the **64-us example** are unchanged.

  [Preflight](/mnt/workspaces/Cells/betse-junction-runtime-development-20261013-01/preparation.json)
  passed **31 host checks** and a **36.66-s CPU probe**; earlier resource-estimate
  failures remain preserved. Five deliberately corrupted native comparisons are
  rejected on both backends. Peak worker RSS was **3.74 GiB** and retained
  artifacts/cache **0.471 GiB**, within unchanged limits.

  The [GPU measurements](/mnt/workspaces/Cells/betse-junction-runtime-20261013-01/gpu-metrics/result.json)
  cover **1,411.76 s / 0.3922 GPU-hours**: mean GPU-busy **1.178%** and measured
  SM-active **0.4866%**, with **99.99994% / 100%** coverage respectively. These
  whole-phase averages include compilation, host checks and idle time; there is
  no separate warmed-throughput interval. The L4 was idle at closeout.

  The subsequently authorized longer-observation assay is now completed above.
  This runtime result does not change the earlier unresolved readout outcome;
  no follow-up was launched at the runtime closeout itself.

- **Saved-trajectory diagnosis completed at 00:20:56 UTC on 13 October**,
  using **26.01 s** of CPU analysis and no new simulations. The
  [result](/mnt/workspaces/Cells/two-task-unstimulated-diagnosis-20261013-01/result.json)
  authenticates the preceding run's **974 unchanged sources, 591 evidence
  hashes and 19 passing reports**, then examines all 140 saved worlds on each
  backend. Original readouts and their failed primary margin target remain frozen.

  **The remote observations are too close for both members of any tested pair
  to clear the current margin.** Across the eight held-out joint pairs per task,
  three-time feature distances are **1.258–3.528 nV for location** and
  **0.951–2.166 nV for timing**. Both are below the necessary **4-nV separation**
  for two opposite-label decisions to exceed the fixed reader's **2-nV margin**.
  The [diagnostic](validation/assays/unstimulated_diagnostic.py) records this as
  a necessary pair condition, not a sufficient decoding or sensing criterion.

  The [time-course figure](/mnt/workspaces/Cells/two-task-unstimulated-diagnosis-development-20261013-01/figures/signal-propagation.png)
  shows different trends: unstimulated-cell location contrasts grow **44–80%**
  from **48 to 64 us** in all eight pairs, while timing is nearly flat
  (**0.9924–0.9988 times** its 48-us magnitude). These are descriptive trends
  at the saved timestep, not a convergence certificate or an extrapolation.
  Timing also overlaps the strength-response direction: **82.8–93.8%** of its
  squared contrast norm lies along the alternative curve's local strength tangent.
  Calibration residuals are only **0.0035–0.0457 nV**; removing each point's
  known-strength residual changes timing scores by at most **0.0227 nV** and
  leaves **0/16 resolved** for both tasks. These known-label probes do not
  replace the original predictions.

  All **seven reader modes and 32 shuffles** reproduce exactly on both backends.
  Reconstructed patch voltages match all archived observation samples exactly;
  area-weighted reader reconstruction differs by at most **3.47e-18 V**.
  Full reconstructed CPU/L4 voltage histories differ by at most **5.94e-13 V**.
  The **28 disconnected pairs** remain exactly zero at the original observation
  times; tiny unsampled differences reach only **2.95e-13 V** and do not establish
  resolved transport. All 28 no-cue pairs remain zero throughout.
  [Seven known-answer checks](/mnt/workspaces/Cells/two-task-unstimulated-diagnosis-development-20261013-01/checks-01.log)
  passed in **4.07 s**; peak analysis RSS was **250 MiB**. Full histories,
  geometry, inputs, source snapshots and checks are linked from the
  [method](docs/TWO_TASK_READOUT_ASSAY.md#diagnosing-weak-unstimulated-signals)
  and [development evidence](/mnt/workspaces/Cells/two-task-unstimulated-diagnosis-development-20261013-01).

  **The recommended runtime extension is now completed above**, bringing the
  qualified **256-us array component** into ordinary execution with native
  comparisons and 64-us prefix checks. Longer observation is justified for investigating location
  propagation, but the current data do not support assuming it will fix timing.
  A later timing experiment should separately test cue separation at fixed dose.
  No follow-up was launched at the diagnosis closeout; the runtime qualification
  above was subsequently authorized.

- **Unstimulated-cell qualification completed at 23:20:15 UTC on 12 October**
  after **14 min 27 s**. The
  [result](/mnt/workspaces/Cells/two-task-unstimulated-20261012-01/result.json)
  records **nine CPU passes / one expected GPU deferral** and **ten L4 passes**,
  with no failures or errors. The
  [completed-evidence check](/mnt/workspaces/Cells/two-task-unstimulated-development-20261012-01/completed-status-20261012T234817Z.json)
  authenticates **974 unchanged sources, 591 evidence hashes and 19 passing
  reports**. At that closeout the GPU was idle and no new computation was launched.

  **The primary scientific target was not met.** Reading only unstimulated
  cells **2, 3, 5, 6 and 7** gives both labels correct in **16/16 forced choices**,
  but **0/16 clear the unchanged 2-nV margin** on either task. The
  [reader results](/mnt/workspaces/Cells/two-task-unstimulated-20261012-01/evidence/gpu/unstimulated-readouts.json)
  give location scores of **0.576–1.760 nV** and timing scores of
  **0.174–1.002 nV**. The all-cell comparator still passes **16/16**, with
  timing scores **8.263–19.848 nV**. Final-time-only restricted reading gets
  both labels correct in **15/16** forced choices, with none resolved.

  With junctions disconnected, all **28 saved primary observation vectors**
  are identical across strengths and labels, and both task scores are zero.
  This is consistent with a small junction-mediated cue on this panel; it does
  not establish robust remote decoding or biological sensing. No-cue and both
  restricted input-only readers also remain unresolved.

  The [CPU/L4 comparison](/mnt/workspaces/Cells/two-task-unstimulated-20261012-01/evidence/gpu/unstimulated-cpu-gpu.json)
  passes across **363,815,480 state/field values** using existing tolerances.
  All task scores and decisions agree exactly across **56 mode/arm/task
  comparisons**, as do the 32 shuffled joint metrics. All **60 calibration
  worlds** reproduce bitwise on each backend; conservation/domain controls and
  fourteen-array replay pass. Material residual uses less than **0.649%** of
  its budget. Peak child RSS is **1.40 GiB**; artifacts/cache occupy **1.39 GiB**.

  The [protocol](validation/assays/unstimulated_readout_protocol.json) fixes
  calibration and evaluation at **0.0625 us**, with the **64-us** horizon and
  fresh strengths **0.4375/0.5625/0.6375/0.7625**. Following
  [four passing preflight checks](/mnt/workspaces/Cells/two-task-unstimulated-development-20261012-01/preparation.json),
  **140 worlds per backend** executed equally **28,672 panel steps per arm**.
  The [GPU measurements](/mnt/workspaces/Cells/two-task-unstimulated-20261012-01/gpu-metrics/result.json)
  cover **445.69 s**: GPU busy **23.441%**, SM-active **8.517%**, with
  **99.999% / 99.781% coverage**, using **0.1238 GPU-hours**. These include
  compilation and host checks; there is no single warmed interval. Summed
  execution per arm is **21.62–22.06 s**, excluding compilation and host work.

  This result motivated the saved time-course and response-geometry diagnosis
  above. The completed qualification scheduled no automatic follow-up.

- **Distributed-cue timestep qualification completed at 19:52:06 UTC on
  12 October**, after **19 min 37 s** of recorded execution. The
  [result](/mnt/workspaces/Cells/two-task-distributed-timing-20261012-01/result.json)
  records **11 CPU passes / one expected GPU deferral** and **12 L4 passes**,
  with no failures or errors. The
  [completed-evidence check](/mnt/workspaces/Cells/two-task-distributed-timing-development-20261012-01/completed-status-20261012T224442Z.json)
  authenticates **971 unchanged sources, 1,149 evidence hashes and 17 passing
  reports**, plus the reused coarse panel's **968 sources and 587 evidence
  hashes**. At that status check the GPU was idle and no new job was launched.

  **The declared primary stability target passed on both backends.** With
  calibration matched to the timestep, both labels remain correct and resolved
  in **16/16 joint cases at 0.25, 0.125 and 0.0625 us**. The
  [reader results](/mnt/workspaces/Cells/two-task-distributed-timing-20261012-01/evidence/gpu/distributed-timing-readouts.json)
  give finest-step timing scores of **8.026–20.174 nV**, above the unchanged
  **2-nV** margin. The largest timing-score change between the two finest steps
  is **0.01837 nV**; all joint task scores meet the declared **2-nV / 10%**
  drift limits with unchanged decisions. Final-time-only reading also passes
  **16/16** at all steps; the two single-task arms retain **8/8**.

  **Fixed original calibration does not retain the same robustness.** With
  the 0.25-us curves held fixed, three-time joint timing stays correct in all
  sixteen forced choices but falls to **13/16 resolved** at the finest step;
  its finest-step score range is **1.049–11.011 nV**. Final-time-only timing
  drops to **7/16 resolved**. All sixteen fixed-reader timing comparisons fail
  the declared finest-step score-drift criterion in each voltage mode. This
  exposes sensitivity to timestep-dependent response shifts; the positive
  matched-calibration result is not a certificate of calibration transfer.

  All **35 active timing contrasts** meet the original-to-finest and
  finest-pair stability limits and exceed the declared signal floor; all
  **28 null pairs** remain exactly zero. The
  [contrast report](/mnt/workspaces/Cells/two-task-distributed-timing-20261012-01/evidence/gpu/distributed-timing-contrasts.json)
  gives a maximum finest-pair relative change of **0.1609%**. No pair resolves
  convergence order under the inherited comparison allowance. These are
  tested-step results, not a continuum error bound. Disconnected reading also
  retains **16/16** with matched calibration, so a need for junction
  communication remains unestablished.

  The [CPU/L4 comparison](/mnt/workspaces/Cells/two-task-distributed-timing-20261012-01/evidence/gpu/distributed-timing-cpu-gpu.json)
  passes across **545,993,840 new state/field values** with existing physical
  tolerances. All decisions agree across **96 task/mode/arm/level comparisons**;
  the largest reader-score difference is **0.0002341 nV**. There are no paired
  contrast or reader-stability classification disagreements, although numerical
  summaries are not all bitwise identical. Fourteen-array restart, reorder,
  partition and streamed-window replay pass bitwise. Material residual uses
  less than **0.649%** of its error budget; null and disconnected controls pass.

  The [protocol](validation/assays/distributed_timing_protocol.json) and
  [method](docs/TWO_TASK_READOUT_ASSAY.md#refining-the-distributed-cue) preserve
  cues, doses, physical timing, model, horizon, reader algorithm and margins.
  **140 coarse worlds per backend** are authenticated and reused, with both
  saved voltage-reader reports reproduced exactly. **280 new worlds per
  backend** execute **215,040 panel steps**, equally **43,008 per arm**. This
  audits inspected cases rather than adding fresh scientific holdouts. The
  [preflight](/mnt/workspaces/Cells/two-task-distributed-timing-development-20261012-01/preparation.json)
  retains five passing checks, 105 allocation plans and source/style/link
  verification. Streaming kept peak child RSS at **1.44 GiB** and artifacts/cache
  at **2.10 GiB**, within the registered **8-GiB / 12-GiB** bounds.

  The [GPU measurements](/mnt/workspaces/Cells/two-task-distributed-timing-20261012-01/gpu-metrics/result.json)
  cover **619.42 s**: GPU busy **24.306%**, measured SM-active **8.930%**, with
  **99.9999% / 99.807% coverage**, using **0.1721 GPU-hours**. These include
  compilation and host checks; no single warmed interval is defined. Summed L4
  execution time per arm is **32.04–33.29 s**, excluding compilation and host
  work. This remains a single-GPU correctness run, not a throughput qualification.

  This result motivated the unstimulated-cell experiment above, with calibration
  explicitly tied to its chosen timestep. The completed audit did not schedule
  an automatic follow-up.

- **75/25 distributed-cue qualification completed at 18:30:19 UTC on
  12 October**, after **5 min 43 s** of recorded execution. The
  [result](/mnt/workspaces/Cells/two-task-distributed-20261012-01/result.json)
  records **seven CPU passes / one expected GPU deferral** and **eight L4
  passes**, with no failures or errors. The
  [completed-evidence check](/mnt/workspaces/Cells/two-task-distributed-development-20261012-01/completed-status-20261012T184631Z.json)
  authenticates **968 unchanged sources, 587 evidence hashes and 15 required
  passing reports**. At that closeout the GPU was idle; the completed run
  scheduled no automatic follow-up.

  **The primary target passed on both backends:** both location and timing are
  correct and resolved in **16/16 fresh joint cases**. The
  [readout results](/mnt/workspaces/Cells/two-task-distributed-20261012-01/evidence/gpu/distributed-readouts.json)
  give timing scores of **8.025–20.178 nV**, above the unchanged **2-nV** margin;
  location scores are **5.210–9.987 uV**. Both single-task arms pass **8/8**.
  Final-time-only joint reading also passes **16/16**, with timing scores of
  **4.640–11.666 nV**. The earlier one-cell failures remain frozen; different
  held-out strengths prevent a matched estimate of the allocation's effect.

  **Disconnected reading also passes 16/16**, with timing scores of
  **8.119–20.441 nV**. Thus these observations do not establish that junction
  communication is necessary: the reader still sees both stimulated source
  cells, and other physical routes remain. Input-history reading passes;
  current-input and no-cue controls remain unresolved. At the **1-uV** margin,
  timing remains unresolved in every joint case. The balanced centroid
  comparator gets timing **8/16** correct. This is synthetic decodability using
  one passive external reader, not biological sensing or polycomputing.

  The [CPU/L4 comparison](/mnt/workspaces/Cells/two-task-distributed-20261012-01/evidence/gpu/distributed-cpu-gpu.json)
  passes across **91,359,800 state/field values** under existing physical
  tolerances. Every reported task score and decision agrees exactly across
  **48 task/mode/arm comparisons**, as do all **32 shuffled joint metrics**.
  All **24 unchanged calibration worlds** reproduce bitwise on each backend;
  fourteen-array restart, partition, window and reorder replay pass. Material
  residual uses less than **0.649%** of its error budget.

  The [protocol](validation/assays/distributed_cue_protocol.json) and
  [method](docs/TWO_TASK_READOUT_ASSAY.md#distributed-source-cue) fix the
  **75/25** allocation and fresh strengths **0.425/0.575/0.625/0.775** while
  preserving total dose, physical timing, model, **0.25-us** step, **64-us**
  horizon and reader. Calibration remains **0.4/0.6/0.8**. All **140 worlds
  per backend** use equal solver work across arms: **7,168 steps per arm**.

  The [preflight](/mnt/workspaces/Cells/two-task-distributed-development-20261012-01/preparation.json)
  records **two passing checks in 19.20 s**, independently verifying every
  source's dose and physical timing without simulating fresh responses. It
  authenticates the completed prerequisite's **963 sources, 587 evidence
  hashes and 15 passing reports**. All **35 batch plans** fit the limits:
  **929.31 MiB** maximum working estimate and **1.39 GiB** retained arrays.
  Ruff, formatting, 21 local method links and diff checks pass. Actual peak
  child RSS was **2.07 GiB**, with **392 MiB** of artifacts/cache, within bounds.

  The [GPU measurements](/mnt/workspaces/Cells/two-task-distributed-20261012-01/gpu-metrics/result.json)
  cover **186.41 s**: GPU busy **17.035%**, measured SM-active **5.082%**, with
  **99.998% / 100% coverage**, using **0.0518 GPU-hours**. These averages include
  compilation and host checks; no single warmed interval is defined. Summed
  L4 execution time per arm was **5.17–5.49 s**, excluding compilation and host
  work. This is a single-GPU correctness run, not a throughput qualification.

  The completed timestep audit above addresses stability for the changed cue.
  A separately declared readout restricted to unstimulated cells remains the
  next proposed experiment, to test whether signals reach cells outside the
  directly stimulated sources. That experiment has not been launched.

- **Saved template-margin diagnosis completed at 17:23:13 UTC on
  12 October.** The
  [diagnostic result](/mnt/workspaces/Cells/two-task-template-diagnosis-20261012-01/result.json)
  authenticates **963 unchanged sources, 587 evidence hashes and 15 passing
  reports**, then reproduces all **six original reader modes and 32 shuffles**
  exactly on each saved backend. The
  [inputs/source hashes](/mnt/workspaces/Cells/two-task-template-diagnosis-20261012-01/inputs.json)
  and [verification](/mnt/workspaces/Cells/two-task-template-diagnosis-development-20261012-01/verification.json)
  retain seven passing known-answer checks, completion hashes and method-link
  checks. This was short CPU analysis of saved evidence; no simulation or GPU
  job was launched.

  **Strength/timing overlap is the main limitation in the sampled joint
  response geometry.** Between **97.25% and 99.97% of the squared norm** of the
  matched early/late voltage difference lies along the alternative timing
  curve's local strength direction. Allowing strength to vary leaves only
  **1.06–2.70 nV** perpendicular separation, consistent with the reader's
  **0.526–1.345-nV** half-gap scores. The alternative timing curve can closely
  imitate each observation by shifting inferred strength by **0.00022–0.00368**;
  no endpoint clipping is involved.

  The same-strength calibration approximation residual is **0.038–0.090 nV**.
  Moving observations exactly onto their true fixed calibration curves changes
  timing scores by at most **0.0055 nV**; **0/16** then exceed the unchanged
  **2-nV** margin. This diagnostic does not correct the opposite physical curve
  or certify unobserved interpolation error. Timing-only inputs retain much
  larger perpendicular separation (**28.96–48.43 nV**) and still pass **8/8**;
  disconnected joint inputs retain only **0.023–0.379 nV**. The primary voltage
  summaries agree exactly between CPU/L4; not every secondary diagnostic value
  is bitwise identical. Null responses stay unresolved. Known strengths and
  paired labels are diagnostic information only; the frozen failed primary
  target remains unchanged. The
  [method](docs/TWO_TASK_READOUT_ASSAY.md#diagnosing-weak-template-margins)
  explains this distinction and how to reproduce the analysis.

  This diagnosis motivated the separately frozen **75/25 distributed-cue**
  experiment above: a fixed midpoint between the one-cell joint cue and the
  successful **50/50** timing-only cue. The diagnostic itself launched no
  simulation or automatic follow-up.

- **Fresh-strength template qualification passed at 16:04:33 UTC on
  12 October**, after **3 min 39 s** of recorded execution. The
  [result](/mnt/workspaces/Cells/two-task-templates-20261012-01/result.json)
  records **17 CPU passes / one expected GPU deferral** and **18 L4 passes**,
  with no failures or errors. The
  [completed-evidence check](/mnt/workspaces/Cells/two-task-templates-development-20261012-01/completed-status-20261012T170713Z.json)
  authenticates **963 frozen sources, 587 evidence hashes and 15 required
  passing reports**; all 963 current registered files match. The
  [registration](/mnt/workspaces/Cells/two-task-templates-20261012-01/registration.json)
  retains all 18 tests per backend. The
  [CPU/L4 comparison](/mnt/workspaces/Cells/two-task-templates-20261012-01/evidence/gpu/templates-cpu-gpu.json)
  passes across **91,359,800 state/field values**, with exact agreement of every
  reported decision across 48 task/mode/arm comparisons and all 32 shuffled
  joint metrics. Forty historical calibration worlds reproduce bitwise;
  fourteen-array restart, partition, window and reorder replay pass. Material
  residual uses less than **0.652%** of its error budget.

  **The primary joint correct-and-resolved target was not met.** The
  [readout results](/mnt/workspaces/Cells/two-task-templates-20261012-01/evidence/gpu/templates-readouts.json)
  choose both labels correctly in **16/16 fresh joint cases**, but timing is
  unresolved in **all sixteen**: its absolute score is **0.526–1.345 nV**, below
  the unchanged **2-nV** margin. Location is correct and resolved in all sixteen.
  Each single-task arm succeeds in **8/8** unique cases, including resolved
  timing. The balanced centroid comparator gives joint timing **8/16**; the
  template reader improves forced-choice accuracy without meeting the declared
  resolution criterion. Final-time-only joint reading also gives **16/16**
  correct choices with unresolved timing.

  Earlier-input history recovers both joint labels correctly and resolved in
  **16/16**; no-cue and current-input controls remain unresolved. Disconnected
  three-time reading also chooses both labels correctly in **16/16**, with
  unresolved timing, so these scores do not establish a need for the junction
  route. The saved-data diagnosis above separates strength/timing overlap from
  sampled calibration approximation error. The fixed margin and frozen results remain
  unchanged; no new biological or polycomputing claim follows.

  The [protocol](validation/assays/template_readout_protocol.json) fixes a
  calibrated response-curve reader, using all location/timing combinations at
  strengths **0.4/0.6/0.8**, before evaluating fresh strengths
  **0.45/0.55/0.65/0.75**. Prediction receives observations only. It tests strength
  interpolation; the original unseen-combination failure remains unchanged.
  The [method](docs/TWO_TASK_READOUT_ASSAY.md#fresh-strength-interpolation-with-calibrated-response-curves)
  retains balanced centroid, final-time, margin-sensitivity, input-history,
  no-cue, disconnected and label-shuffle comparisons. All scientific outcomes,
  including failure and abstention, are reported separately from numerical
  qualification. No fresh evaluation simulation or response inspection took
  place during development.

  **140 worlds per backend** use the unchanged physical cues, **64-us** horizon
  and finest previously verified **0.25-us** step, with **7,168 solver steps per
  arm**. The
  [preflight](/mnt/workspaces/Cells/two-task-templates-development-20261012-01/preparation.json)
  records **12 passing checks**, all **35 batch plans**, **929.31 MiB** maximum
  batch working estimate and **1.39 GiB** retained-array estimate. The completed
  prerequisite's **960 sources and 987 evidence hashes** authenticate unchanged.
  Ruff, formatting, local method links and diff checks pass. Bounds remain
  **40 minutes / 8 GiB worker RSS / 2 GiB artifacts/cache / 0.2 GPU-memory
  fraction**.

  The [GPU measurements](/mnt/workspaces/Cells/two-task-templates-20261012-01/gpu-metrics/result.json)
  cover the **124.77-s GPU phase**: GPU busy **21.154%**, measured SM-active
  **7.653%**, with **99.9995% / 99.183% coverage**, using **0.0347 GPU-hours**.
  These averages include compilation and host checks; no single warmed interval
  is defined. Summed L4 execution time per arm was **4.84–5.02 s**, excluding
  compilation and host work. This is a single-GPU qualification, not a
  multi-GPU utilization result. At that closeout the GPU was idle; this run
  launched no automatic follow-up.

- **CPU/L4 timing-refinement qualification passed at 15:35:20 UTC on
  12 October**, after **5 min 23 s** of recorded execution. The
  [result](/mnt/workspaces/Cells/two-task-timing-refinement-20261012-02/result.json)
  records **14 CPU passes / one expected GPU deferral** and **15 L4 passes**,
  with no failures or errors. The
  [completed-evidence check](/mnt/workspaces/Cells/two-task-timing-refinement-development-20261012-02/completed-status-20261012T154315Z.json)
  authenticates **960 frozen sources, 987 evidence hashes and 15 required
  passing reports**; all 960 current registered files still match. The
  [registration](/mnt/workspaces/Cells/two-task-timing-refinement-20261012-02/registration.json)
  retains the unchanged 15-test inventory per backend. The
  [CPU/L4 comparison](/mnt/workspaces/Cells/two-task-timing-refinement-20261012-02/evidence/gpu/timing-cpu-gpu.json)
  passes across **91,746,400 state/field values in 240 worlds per backend**.
  Fine-step reorder, partition, window and snapshot replay remain bitwise across
  fourteen state arrays. Material residual uses less than **0.652%** of its
  error budget.

  All **20 cue pairs** meet the declared timing-stability limits and exceed the
  declared synthetic reader floor; all **16 null pairs** remain exactly zero.
  CPU/L4 paired contrasts agree exactly. The largest **0.5-to-0.25-us** relative
  change is **0.111%**; original 1-us contrasts also meet the limits. The
  [contrast results](/mnt/workspaces/Cells/two-task-timing-refinement-20261012-02/evidence/gpu/timing-contrasts.json)
  establish stability at the tested timesteps, not convergence order, continuum
  accuracy or biological sensor resolution. **The original two-task decoding
  failure remains unchanged.** The revised reader and calibration design is
  registered in the fresh-strength assay above.

  The historical comparison now reuses the **existing field-specific physical
  tolerances**, retaining exact-agreement counts and every differing field.
  **Within-run replay remains bitwise**; physics, scientific stability criteria
  and numerical allowances are unchanged. The
  [repair preflight](/mnt/workspaces/Cells/two-task-timing-refinement-development-20261012-02/preparation.json)
  records **nine passing tests**, saved CPU/L4 comparisons over **13,283,360
  values each**, and **nine rejected corruption controls**, including an exact
  replay changed by one floating-point step. Ruff, formatting and diff checks
  pass. In this retry, historical CPU and L4 full histories also happen to match
  their original evidence bitwise. The failed run below remains intact.

  The [GPU measurements](/mnt/workspaces/Cells/two-task-timing-refinement-20261012-02/gpu-metrics/result.json)
  cover the **189.61-s GPU phase**: whole-phase GPU busy **13.201%**, measured
  SM-active **4.993%**, with **99.999% / 100% coverage**, using **0.0527 GPU-hours**.
  These include compilation and host checks; no single warmed throughput
  interval is defined. The fresh-strength follow-up was launched separately
  on the user's subsequent instruction.

- **The first timing-refinement run stopped at 14:37:37 UTC on 12 October**, after
  **3 min 41 s**. The [failure](/mnt/workspaces/Cells/two-task-timing-refinement-20261012-01/failure.json)
  preserves **14 CPU passes / one expected GPU deferral** and **10 L4 passes /
  one failure**. All **240 L4 worlds** were saved before the historical coarse
  comparison rejected small differences from the previous GPU run. Its first
  failing field was accumulated membrane transport, differing by up to
  **4.25e-19 fmol** in the first world. The qualification is **incomplete**;
  the four later L4 checks were not executed. The corrected retry is recorded
  above.

  A [read-only failure review](/mnt/workspaces/Cells/two-task-timing-refinement-development-20261012-01/failure-review.json)
  authenticates the completed predecessor and **all 960 unchanged registered
  sources**. All **13,283,360 state/field values** across the eighty historical
  coarse GPU comparisons meet the **existing physical tolerances**; all eighty
  voltage readout vectors are bitwise identical. Small differences also occur
  in gates and other ledgers, with maxima retained by field. Their compiler or
  runtime cause is not established by this review.

  Reconstructing timing contrasts from the saved panels gives **exact CPU/L4
  agreement**: all **20 cue pairs** meet the declared stability limits and all
  **16 null pairs** are exactly zero. The largest 0.5-to-0.25-us relative change
  is **0.111%**; original 1-us contrasts also meet the limits. This post-stop
  diagnosis does not replace the unexecuted L4 contrast, control, fine replay
  and full CPU/L4 comparison checks, or establish two-task decoding success.

  The [GPU measurements](/mnt/workspaces/Cells/two-task-timing-refinement-20261012-01/gpu-metrics/result.json)
  cover the **115.27-s GPU phase**: whole-phase GPU busy **22.126%**, measured
  SM-active **7.525%**, with **99.999% / 100% coverage**. These include compilation
  and host checks; no single warmed throughput interval is defined.
  The [launch receipt](/mnt/workspaces/Cells/two-task-timing-refinement-20261012-01/launch.json)
  records the detached worker started at **14:33:55 UTC**. The initial
  [launch check](/mnt/workspaces/Cells/two-task-timing-refinement-development-20261012-01/launch-check.json)
  observed the CPU phase running at **14:34:17 UTC**, with no failure artifact.
  The [registration](/mnt/workspaces/Cells/two-task-timing-refinement-20261012-01/registration.json)
  freezes **960 sources and 15 tests per backend**; all **955 original assay
  sources** remain unchanged at launch.

  The [protocol](validation/assays/timing_refinement_protocol.json) repeats all
  eighty worlds at **1/0.5/0.25-us** steps, for **240 worlds and 35,840 solver
  steps per backend**, with identical physical cues and the same **64-us**
  horizon. It compares paired early/late voltage differences at the original
  readout times, retains null/disconnected controls, reproduces the original
  coarse evidence and checks fourteen-array replay at the finest step.
  Stability requires both a **2-nV absolute** and **10% relative** change limit;
  signal resolution is reported separately. These are declared synthetic
  diagnostics, not biological precision or a new decoding claim. A passing
  numerical suite need not imply a stable timing signal.

  [Preflight and preparation](/mnt/workspaces/Cells/two-task-timing-refinement-development-20261012-01/preparation.json)
  record **nine passes**, all sixty batch plans, **929.31 MiB** maximum batch
  working estimate and **1.42 GiB** retained-array estimate. The initial host
  preflight failure is preserved there: the new test incorrectly assumed all
  static junction masks were one, whereas the frozen geometry blocks exterior
  patches. The correction requires the unchanged binary mask; no physics,
  criteria or prior evidence changed. Ruff, formatting and diff checks pass.
  Limits are **40 minutes**, **8 GiB worker RSS**, **2 GiB artifacts/cache**,
  **1 GiB per batch** and **0.2 GPU-memory fraction**. The existing runner records
  GPU-busy and measured SM-active coverage and saves completion/failure evidence.
  No automatic follow-up is scheduled.

- **Two-task encoding/timing diagnosis completed, 12 October.** The
  [saved-data diagnostic](validation/assays/two_task_diagnostic.py) authenticates
  **955 unchanged sources, 345 evidence hashes and 13 required passing reports**.
  It reproduces all five original CPU and L4 readout reports exactly, including
  scores and fitted means. The
  [diagnostic result](/mnt/workspaces/Cells/two-task-diagnosis-20261012-01/result.json)
  preserves every diagnostic split, prediction and paired voltage contrast;
  [inputs and source hashes](/mnt/workspaces/Cells/two-task-diagnosis-20261012-01/inputs.json)
  identify the already-inspected evidence. This was short CPU analysis of saved
  data, with no simulation or GPU job.

  The earlier-input failure comes from the **reader/split geometry**: omitting
  a location–timing combination leaves its pulse on an unseen feature, and the
  opposite class's averaged centroid is closer. This is reproducible with a
  perfect one-hot input; the existing positive oracle used a different,
  factorized encoding. Using all four combinations for calibration while still
  withholding strengths recovers both input labels in **8/8** cases. Summing
  input deficits over time or cells also gives **8/8** with the original
  combination holdouts, using different feature supports. These are post-hoc
  encoding diagnostics, not a repaired scientific result.

  With balanced calibration, tissue voltage still gives location **8/8** and
  timing **4/8**, on both saved backends; disconnected results match. No-cue and
  current-input controls remain unresolved. Across the joint panel, timing
  contrasts have **5.7–169 nV** Euclidean magnitude over the 21 voltage features,
  versus **20.7–41.5 uV** for location and **11.5–17.3 uV** for strength. Timing
  is weak and mixed with larger effects; this motivated the timing-refinement
  check above before interpreting it physically. **The original two-task
  objective remains unproved.**

  [Six known-answer checks](/mnt/workspaces/Cells/two-task-diagnosis-development-20261012-01/unit.xml)
  pass, covering the omitted-input failure, calibration isolation, fixed input
  marginalization, nulls, known paired effects and altered-result rejection.
  The separately registered timing-refinement follow-up is recorded above;
  a revised assay and fresh evaluation inputs remain later work. This saved-data
  analysis launched no simulation. The
  [diagnostic method](docs/TWO_TASK_READOUT_ASSAY.md#diagnosing-an-encoding-or-readout-failure)
  explains the scope and reproduction command.

- **Broader Cells scope and calibration resources documented, 12 October.**
  The README now leads with integrated cells, tissues and organs, placing BETSE
  in its bioelectric-layer role. The
  [calibration plan](docs/SCIENTIFIC_BASIS.md#calibration-across-the-cells-stack)
  distinguishes existing assembly/chemistry/electrodiffusion references from
  future physiology, molecular, atlas and organ-function resources. New resource
  descriptions were reviewed; datasets and models were not imported or fitted.
  The [documentation/source checks](/mnt/workspaces/Cells/calibration-resources-docs-20261012-01/verification.json)
  retain the review scope and unchanged simulation sources. Completed simulation
  evidence is unchanged.

- **BETSE and BITSEY reference roles clarified, 12 October.** The README and
  design entry points now identify both references and make scientific feature
  parity with both an explicit target. BITSEY's BETSE ancestry and separate
  execution core were checked against the pinned source and the authors' paper;
  coverage must be verified separately. The broader BITSEY feature inventory
  remains open beyond the first Forms replication target. The
  [BITSEY replication plan](docs/ROADMAP.md#bitsey-replication) builds on existing
  regulation, pair and independent graph work, starting with corrected clocks
  (P10R) and the editable lineage (P11), with CPU/L4 verification. The
  [source review](docs/SCIENTIFIC_BASIS.md#betse-and-bitsey-as-complementary-references)
  distinguishes Forms v0.17 from the later P32 report. This was documentation
  only; no simulation or frozen result changed. The
  [documentation checks](/mnt/workspaces/Cells/bitsey-reference-docs-20261012-01/verification.json)
  record link checks and unchanged registered simulation sources; the
  [relationship and parity clarification checks](/mnt/workspaces/Cells/bitsey-betse-relationship-20261012-01/verification.json)
  retain the subsequent source inspection and documentation checks.

- **CPU/L4 two-task assay qualification passed at 11:21:19 UTC on
  12 October**, after **2 min 5 s**. The
  [result](/mnt/workspaces/Cells/two-task-readout-20261012-01/result.json) records
  **14 CPU passes / one declared GPU deferral** and **15 L4 passes**, with no
  failures or errors. The [completed-evidence check](/mnt/workspaces/Cells/two-task-readout-development-20261012-01/completed-status-20261012T124850Z.json)
  authenticates **955 frozen sources, 345 evidence hashes and 13 required
  passing reports**; all 955 current files, including 141 production modules,
  match. The [CPU/L4 comparison](/mnt/workspaces/Cells/two-task-readout-20261012-01/evidence/gpu/assay-cpu-gpu.json)
  passes across **13,283,360 state/field values** from **80 worlds per backend**,
  with exact agreement of all reported decoder decisions. Fourteen-array
  restart, window/partition/reorder replay, observer neutrality and controls
  pass. Maximum material residual uses less than **0.625%** of its error budget.

  **The two-task scientific objective is not demonstrated.** The frozen
  [readout results](/mnt/workspaces/Cells/two-task-readout-20261012-01/evidence/gpu/assay-readouts.json)
  recover location in **8/8 held-out joint cases**, but timing in **0/8**, so
  joint success is **0/8**. Single-task results are location **4/4** and timing
  **2/4**. Final-time-only reading gives the same accuracies. Disconnected
  junctions give the same joint-task scores, so this result does not establish
  a need for that route. No-cue and current-input baselines have no resolved
  decisions. The earlier-input baseline succeeds on each task alone but also
  fails both joint holdouts (**0/8 each**). This prompted the saved-data diagnosis
  above, which separates the encoding/readout issue from the unresolved physical
  timing question. These are small deterministic tests,
  without biological validation, a causal consumer or a polycomputing claim;
  the [protocol](validation/assays/two_task_protocol.json) and completed results
  remain frozen rather than retuned to improve scores.

  The **72.04-s GPU phase** used **0.0200 GPU-hours**: whole-phase GPU busy
  **6.843%**, measured SM-active **2.032%**, with **99.999% / 100% coverage**.
  These include compilation and host checks; no single warmed interval exists.
  Each arm executed **1,024 solver steps**; summed L4 execution times were
  **0.709–0.773 s per arm**, excluding compilation/host work. Peak child RSS
  was **1.41 GiB**, artifacts/cache **78.37 MiB**. The
  [registration](/mnt/workspaces/Cells/two-task-readout-20261012-01/registration.json)
  retains the 40-minute / 8-GiB RSS / 2-GiB artifacts / 0.2 GPU-memory limits.
  The [earlier memory-planning failure](/mnt/workspaces/Cells/two-task-readout-20261011-01/failure.json)
  remains intact: its 256-MiB batch allowance was below the 258.53-MiB estimate.
  The [repair preflight](/mnt/workspaces/Cells/two-task-readout-development-20261012-01/fix-verification.json)
  verified all 20 batch/window plans under 512 MiB and nine passing checks,
  without changing physics, decoder settings, splits or numerical tolerances.
  Subsequent diagnosis and timing refinement are recorded above.

- **Quantum birthmarks reviewed, 11 October.** The
  [research note](docs/PAPER_REVIEW_QUANTUM_BIRTHMARKS.md) checks the Phys.org
  account against the PRX paper and records proposed extensions to E04/E09/E11/E12
  and the planned two-task assay: matched-history comparisons, causal carrier
  tests, reader controls and preserved behaviour under coarse graining. It
  distinguishes quantum theory/simulation from biological measurements and
  prevents logs, accounting ledgers or observer buffers from masquerading as
  physical memory. [Sources and documentation checks](/mnt/workspaces/Cells/quantum-birthmarks-review-20261011-01/verification.json)
  record seven local link/anchor checks and all **948 unchanged code/configuration/
  validation files**. This was documentation-only; no simulation or job was changed.

- **Long dynamic-junction qualification passed at 22:53:05 UTC on
  11 October**, after **68 min 44 s**. The
  [result](/mnt/workspaces/Cells/betse-spatial-junction-refinement-20261011-01/result.json)
  records **42 CPU passes / one declared GPU deferral** and **43 L4 passes /
  no skips**, with no failures or errors. The
  [completed-evidence check](/mnt/workspaces/Cells/betse-spatial-junction-refinement-development-20261011-01/completed-status-20261011T230327Z.json)
  authenticates **950 frozen sources, 314 evidence hashes, 65 required passing
  reports**, both test inventories and raw GPU metrics. All **950 registered
  current files**, including **139 production modules**, remain unchanged.
  The [protocol](validation/betse/spatial_active/junction_refinement_protocol.json)
  covers six unchanged cases through **256 us**, at **1/0.5/0.25-us** steps.
  All **18 native trajectory comparisons per backend** pass across
  **61,221,888 scalar values each**, using at most **23.80% CPU / 25.29% L4**
  of the existing error budget. Direct
  [CPU/L4 agreement](/mnt/workspaces/Cells/betse-spatial-junction-refinement-20261011-01/evidence/gpu/long-junction-cpu-gpu.json)
  passes across **59,243,520 values**. All five native/Cells temporal-refinement
  cases pass, as do original 64-us prefixes, fourteen-array replay through nine
  disk cuts and changed windows, independent-world reorder/partition, effects
  and corruption controls. Half blocking remains a separate step-sensitivity
  result: multiplying stored opening after every moving-ion update changes the
  prescribed blocking rate when dt changes; no fixed-law refinement is claimed.
  The [preparation receipt](/mnt/workspaces/Cells/betse-spatial-junction-refinement-development-20261011-01/preparation.json)
  retains both authenticated prerequisites and **12 bounded preflight passes**.
  The [registration](/mnt/workspaces/Cells/betse-spatial-junction-refinement-20261011-01/registration.json)
  retains the **90-minute / 12-GiB RSS / 4-GiB artifacts-cache / 0.2 GPU-memory**
  limits. Peak child RSS was **7.02 GiB**, artifacts/cache **594.74 MiB**.
  The **1493.18-s GPU phase** used **0.4148 GPU-hours**: whole-phase GPU busy
  **0.693%**, measured SM-active **0.242%**, both with **100% coverage**.
  These include compilation, host checks and idle intervals; no single warmed
  throughput interval was defined. This closes the longer array component only;
  ordinary junction configuration remains limited to 64 us, and native mixed
  pump/channel/junction events remain later work. No biological, spatial-
  convergence or multi-GPU claim follows. The
  [roadmap](docs/ROADMAP.md#m2-and-m3-implementation-slice) places the first small
  two-task readout assay next. No follow-up job was launched.

- **Ordinary dynamic-junction runtime qualification passed at 18:25:06 UTC
  on 11 October**, after **28 min 28 s**. The
  [result](/mnt/workspaces/Cells/betse-junction-runtime-20261011-02/result.json)
  records **347 CPU passes / two declared GPU deferrals** and **349 L4 passes /
  no skips**, with no failures or errors. The
  [completed-evidence check](/mnt/workspaces/Cells/betse-junction-runtime-development-20261011-02/completed-status-20261011T185921Z.json)
  authenticates **947 frozen sources, 138 evidence hashes, 80 required passing
  reports**, both test inventories and raw GPU counters. All **139 production
  modules** match the completed run. The retry launched at **17:56:37 UTC**. The
  [initial attempt](/mnt/workspaces/Cells/betse-junction-runtime-20261011-01/failure.json)
  stopped at **17:40:14 UTC**, after **31 CPU passes**. The first full-history
  comparison rejected boundary-potential shapes **[64,10,10] versus [64,100]**:
  the configured observer retains grid axes while the frozen reference flattens
  boundary and exterior potentials. The test adapter now uses that reference's
  C-order flattening for those two potentials, preserving electric-field grid
  axes. The [failure review](/mnt/workspaces/Cells/betse-junction-runtime-development-20261011-02/failed-run-review.json)
  authenticates all **947 frozen sources** and confirms that only this test file
  changed; all **139 production modules**, tolerances, protocol and test
  inventory remain unchanged. Failed evidence is preserved; GPU had not started.
  The [targeted checks](/mnt/workspaces/Cells/betse-junction-runtime-development-20261011-02/preflight.xml)
  passed **13 tests in 25.29 s**: all twelve **64-us** junction histories at
  **1/0.5-us** steps, plus the three legacy **256-us** scheduled pump/channel
  histories. These passed **3,430,656 / 4,528,128 state/field scalar comparisons**,
  respectively. The [preparation receipt](/mnt/workspaces/Cells/betse-junction-runtime-development-20261011-02/preparation.json)
  binds those checks and the completed component prerequisite. Ruff, formatting
  and `git diff --check` pass.
  The [configuration](configs/betse_spatial_junction.json) preserves **fourteen
  state arrays**, explicit moving-ion order, and reciprocal junction controls
  alongside pump/channel controls in the CLI, snapshots, windows and independent
  worlds. The unchanged [protocol](validation/betse/spatial_active/junction_runtime_protocol.json)
  passed its **349-test inventory per backend**, including all **80 required
  evidence reports**. Qualification covered disk cuts beside interventions, window changes,
  future branching, corrupt snapshots, domain failure retention, world
  reorder/partition/resume and existing shared-runner regressions.
  Limits were **90 minutes**, **12 GiB worker RSS**, **4 GiB artifacts/cache**
  and **0.2 GPU memory fraction**. Peak child RSS was **3.64 GiB** and
  artifacts/cache **274.13 MiB**. The **962.82-s GPU phase** used **0.2674
  GPU-hours**: whole-phase GPU busy **1.264%**, measured SM-active **0.273%**,
  with **100.00% / 99.88% coverage**, respectively. These include compilation,
  host checks and idle intervals; no single warmed interval was defined. The
  [registration](/mnt/workspaces/Cells/betse-junction-runtime-20261011-02/registration.json)
  freezes **947 sources**; the
  [launch check](/mnt/workspaces/Cells/betse-junction-runtime-development-20261011-02/launch-check.json)
  confirms the controller and CPU phase, without a failure artifact at that
  check. This closes ordinary runtime integration for the declared **64-us**
  junction histories, including complete snapshots and shared execution. The
  longer/refined coupled junction comparison is now recorded above; combined
  pump/channel/junction interventions remain subsequent work.
  Mixed-control mapping alone does not establish native mixed-intervention
  correspondence. No longer dynamic-junction, spatial-convergence, biological
  or multi-GPU claim follows; no automatic polling or follow-up is scheduled.

- **Multiscale architecture reviewed, 11 October.** The
  [execution architecture](docs/MULTISCALE_EXECUTION_ARCHITECTURE.md) now maps
  existing code to remaining interfaces and adds a primary-source review of
  polycomputing: shared physical state, overlapping functional groups, explicit
  readouts/consumers and joint-task causal tests. It also updates stochastic
  assembly, bidirectional event-coupling requirements and the 4–16-GH200 design.
  Historical sections are preserved in collapsible notes.
  [Review sources and checks](/mnt/workspaces/Cells/multiscale-architecture-review-20261011-01/verification.json)
  record this documentation-only change; no new experiment was launched.

- **README research purpose added, 11 October.** An
  [early section](README.md#why-we-are-building-cells) now makes testing *Plastic
  Heredity* and *How Forms Become Reconstructible* in increasingly realistic
  cell/tissue models a central goal. A matching [conceptual infographic](docs/assets/cells-research-goals.png)
  presents questions, models, interventions and measurements as research goals.
  [Prompts](docs/assets/readme-image-prompts.json) and
  [documentation checks](/mnt/workspaces/Cells/readme-forms-title-20261011-01/verification.json)
  preserve the asset provenance and distinguish this wording update from a new
  experiment or scientific qualification.

- **Documentation navigation and coverage refreshed, 11 October.** The README
  now links seven core guides and the [docs index](docs/README.md). Main design
  introductions and the [BETSE inventory](docs/BETSE_CAPABILITY_ROADMAP.md) reflect
  the recorded spatial, calcium, assembly and CPU/L4 work. Superseded roadmaps
  remain in [dated snapshots](docs/history/); source contracts and acceptance
  reports retain their scientific scope. GPU reporting still distinguishes busy
  time, measured SM-active and coverage while optimization is parked. This is a
  documentation review, with no new literature search, scientific qualification
  or active-job status check.

- **Spatial dynamic-junction qualification passed at 17:03:49 UTC on
  11 October**, after **13 min 35 s**. The
  [result](/mnt/workspaces/Cells/betse-spatial-junction-20261011-01/result.json)
  records **38 CPU passes / one declared GPU deferral** and **39 L4 passes /
  no skips**, with no failures or errors. The
  [completed-evidence check](/mnt/workspaces/Cells/betse-spatial-junction-development-20261011-01/completed-status-20261011.json)
  authenticates **941 frozen sources, 208 evidence hashes, 37 required passing
  reports**, both test inventories and raw GPU counters. All **137 production
  modules** matched the completed run before runtime integration began.
  The [component](src/cells/numerics/betse_junction.py) preserves pinned BETSE's
  full-timestep gate update per moving ion and blocking of the stored opening;
  the separate physical-time law is unchanged. Six **64-us** cases at **1 and
  0.5 us** cover coupled transport, reversed ion order, half blocking,
  block/release, disconnection and one connected pair. Each backend passed
  **6,559,488 native scalar comparisons**, using at most **14.61% CPU / 27.59%
  L4** of the existing error budget. Cross-device checks covered **6,347,520
  values**. All **fourteen state arrays** survived disk restoration, changed
  windows and independent-world reorder/partition exactly; deliberate timing,
  gate and material corruptions were rejected.
  The **317.47-s GPU phase** used **0.0882 GPU-hours**: whole-phase GPU busy
  **0.164%**, measured SM-active **0.129%**, with **100.00% / 99.65% coverage**.
  These include compilation, host checks and recording; no warmed interval was
  identified. Peak child RSS was **2.00 GiB**, artifacts/cache **93.89 MiB**.
  This closes the short array component. The subsequent ordinary configuration,
  complete snapshot and shared-runner qualification is recorded above.
  No longer-time, spatial-convergence, biological or multi-GPU claim follows.

- **Long scheduled BETSE intervention qualification passed at 15:34:53 UTC
  on 11 October**, after **40 min 12 s**. The
  [result](/mnt/workspaces/Cells/betse-spatial-intervention-refinement-20261011-02/result.json)
  and [completion receipt](/mnt/workspaces/Cells/betse-spatial-intervention-refinement-20261011-02/completion.json)
  confirm **63 CPU passes / one declared GPU deferral**, then **64 L4 passes /
  no skips**, with no failures or errors. The
  [registration](/mnt/workspaces/Cells/betse-spatial-intervention-refinement-20261011-02/registration.json)
  freezes **935 sources and 64 tests**. The
  [16:14 UTC verification](/mnt/workspaces/Cells/betse-spatial-intervention-refinement-development-20261011-02/completed-status-20261011T161452Z.json)
  authenticates **314 completion evidence hashes**, all **935 frozen sources**,
  four raw GPU metric hashes and all **65 required passing reports**. All
  current registered sources, including **136 production modules**, match.
  The completed **419-test CPU/L4 prerequisite** below remains authenticated,
  including all **931 prior source files**.
  Six unchanged pump/channel schedules through **256 us**, at **1, 0.5 and
  0.25 us** steps, give **18 native-matched histories per backend**. Each backend
  passes on **59,931,648 native-comparison values**, using at most **15.34% CPU /
  25.28% L4** of the existing error budget. Direct
  [CPU/L4 agreement](/mnt/workspaces/Cells/betse-spatial-intervention-refinement-20261011-02/evidence/gpu/long-intervention-cpu-gpu.json)
  passes on **57,953,280 values**. All six native/Cells temporal-refinement cases
  pass on each backend, with **634 resolved field/checkpoint comparisons** per
  panel and ratios **1.99898–2.00320**. Original 64-us native and Cells state/rate
  prefixes remain bitwise identical; derived readouts retain their tolerances.
  All thirteen state arrays replay bitwise through **13 fine-step disk restarts**,
  changed windows, terminal continuation, mixed-timestep world reordering and
  partitions, and saved **64-to-256-us horizon extension**. Block/release effects
  and deliberate control/material/gate corruption checks pass.
  The corrected batch test declares **6 GiB**, covering the conservative
  **4,438,032,704-byte (4.13 GiB)** estimate for its full padded histories. The
  [host plans](/mnt/workspaces/Cells/betse-spatial-intervention-refinement-development-20261011-02/evidence/cpu/long-intervention-resource-plan.json)
  accept full, reordered, individual and windowed batches and still reject the
  original 1 GiB allowance. Actual peak worker RSS is **7.13 GiB**, below the
  unchanged **12 GiB limit**. The
  [L4 batch report](/mnt/workspaces/Cells/betse-spatial-intervention-refinement-20261011-02/evidence/gpu/long-intervention-worlds.json)
  records host/device array sizes and compiler memory separately from estimates.
  [Three focused checks](/mnt/workspaces/Cells/betse-spatial-intervention-refinement-development-20261011-02/focused.xml)
  pass in **3.59 s**; Ruff and diff checks pass. The
  [preparation receipt](/mnt/workspaces/Cells/betse-spatial-intervention-refinement-development-20261011-02/preparation.json)
  verifies that only the long test and its protocol changed from the failed
  attempt; production code and scientific criteria are unchanged, and the
  failed attempt's **935 frozen sources and 33 recorded evidence hashes** remain
  intact. The
  [protocol](validation/betse/spatial_active/intervention_refinement_protocol.json)
  retains the 90-minute cap and GPU-busy/SM-active recording. The **875.32-s L4
  phase** used **0.2431 GPU-hours**, averaging **1.432% GPU-busy / 0.485% measured
  SM-active**, with **99.9997% / 99.8772%** coverage. These averages include
  compilation and host checks; no fully warmed throughput interval is defined.
  Artifacts/cache total **607.70 MiB**; controller, CPU and GPU stderr are empty.
  The controller has exited and the L4 is idle. No follow-up job was started.
  This panel does not establish spatial convergence, biological recovery,
  new mechanisms, assembly coupling or multi-GPU throughput.

- **The first long scheduled attempt failed at 13:27:33 UTC on 11 October:**
  **47 CPU passes / one failure** after **35 min 42 s**. The
  [failure](/mnt/workspaces/Cells/betse-spatial-intervention-refinement-20261011-01/failure.json)
  and [status receipt](/mnt/workspaces/Cells/betse-spatial-intervention-refinement-development-20261011-01/failed-status-20261011T142147Z.json)
  are preserved. All **18 native CPU comparisons** passed on **59,931,648 values**,
  using at most **15.34%** of the error budget. All six native/Cells refinement
  checks passed, with resolved ratios **1.99901–2.00320**. Original state/rate
  prefixes and all thirteen state arrays through **13 fine-step disk restarts**,
  changed windows and terminal continuation replayed bitwise. **27 CPU reports
  passed** before the mixed-world planner rejected the test's insufficient
  **1 GiB** allowance. It stopped before batch allocation; **15 CPU tests and
  all L4 checks were unrun**. The successful run above corrects that test budget.

- **Scheduled BETSE pump/channel intervention qualification passed at
  02:26:41 UTC on 11 October**, after **53 min 39 s**. The
  [result](/mnt/workspaces/Cells/betse-spatial-interventions-20261011-02/result.json)
  and [completion receipt](/mnt/workspaces/Cells/betse-spatial-interventions-20261011-02/completion.json)
  confirm **415 CPU passes / four declared GPU deferrals**, then **419 L4
  passes / no skips**, with no failures or errors. The
  [registration](/mnt/workspaces/Cells/betse-spatial-interventions-20261011-02/registration.json)
  freezes **931 source files and 419 tests**, including all **381 previous
  runtime/native/shared-runner tests**. The
  [04:33 UTC verification](/mnt/workspaces/Cells/betse-spatial-interventions-development-20261011-02/completed-status-20261011T043321Z.json)
  authenticates **502 completion evidence hashes**, **931 frozen sources**,
  four raw GPU metric hashes and all **130 required passing evidence reports**.
  All **136 production modules** match the frozen run.
  Twelve scheduled histories agree with native BETSE on **6,421,248 values per
  backend**, using at most **14.60% CPU / 21.69% L4** of the existing error
  budget. [CPU/L4 agreement](/mnt/workspaces/Cells/betse-spatial-interventions-20261011-02/evidence/gpu/intervention-cpu-gpu.json)
  passes on **6,209,280 scheduled values**, alongside the inherited panels.
  All thirteen state arrays replay bitwise through before/at/after-event disk
  restart, changed windows and mixed static/scheduled worlds; world reordering,
  a completed world, future-only branching and deliberate corruption checks pass.
  Blocked transport is zero, intrinsic gates continue, release restores transport,
  neutral schedules preserve static histories, and terminal events add no step.
  The mixed-world test now uses each world's accepted `result.times` instead of
  rounded decimal literals. Its [focused disk/restart check](/mnt/workspaces/Cells/betse-spatial-interventions-development-20261011-02/focused-check.json)
  passes in **23.53 s** on **122,696 state values**; Ruff and diff checks pass.
  [Retry preparation](/mnt/workspaces/Cells/betse-spatial-interventions-development-20261011-02/preparation.json)
  confirms the production modules, protocol, tolerances and test inventory were
  unchanged from the first attempt; only checkpoint selection in that test changed.
  The first attempt's [failure](/mnt/workspaces/Cells/betse-spatial-interventions-20261011-01/failure.json)
  and [status receipt](/mnt/workspaces/Cells/betse-spatial-interventions-development-20261011-01/failed-status-20261011T012722Z.json)
  remain intact: **35 CPU passes, one failure and 383 unrun tests** after
  **7 min 45 s**, without starting L4.
  The [GPU example](configs/betse_spatial_interventions.json) blocks both
  pump/channel routes at **16 us**, restores them at **40 us**, and ends at
  **64 us**. The [protocol](validation/betse/spatial_active/intervention_protocol.json)
  qualifies pump-only, channel-only, combined, regional, staggered and neutral
  schedules at **1 and 0.5 us** timesteps. Explicit per-patch fractions take effect
  at completed fixed-step boundaries. Native observed/bare captures share the
  declared input hook; native methods, clock labels, numerical kernels and
  physical tolerances are unchanged. This qualifies prescribed FULL INIT inputs;
  native built-in SIM events, inhibitor chemistry, biological recovery and
  assembly-driven inputs remain outside this result. Static runs retain their
  earlier **256 us** qualification; scheduled runs are qualified through **64 us**.
  Across the **1,545.14 s** GPU phase (**0.42921 GPU-hours**), mean GPU-busy is
  **0.46365%** and measured SM-active **0.14354%**, with **99.99995% / 100%**
  coverage. These whole-suite averages include compilation and host checks;
  no single warmed throughput interval is defined. Peak child RSS is **3.66 GiB**
  and artifacts/cache total **402.4 MB**. Controller/backend stderr are empty,
  no failure artifact is present, the controller has exited and the L4 is idle.
  No follow-up job was started. The next BETSE step is longer scheduled
  intervention horizons with timestep refinement against native trajectories;
  broader mechanisms, assembly-driven controls and remote GPU throughput remain
  separately unqualified.

- **Ordinary BETSE runtime qualification passed at 00:01:41 UTC on
  11 October**, after **42 min 9 s**. The
  [result](/mnt/workspaces/Cells/betse-spatial-runtime-20261010-02/result.json)
  and [completion receipt](/mnt/workspaces/Cells/betse-spatial-runtime-20261010-02/completion.json)
  confirm **378 CPU passes / three declared GPU deferrals**, then **381 L4
  passes / no skips**, with no failures or errors. The
  [registration](/mnt/workspaces/Cells/betse-spatial-runtime-20261010-02/registration.json)
  freezes **925 source files and 381 tests**, including the earlier 86-test
  native panel and **249 shared-runner regression tests**. The
  [00:14 UTC status verification](/mnt/workspaces/Cells/betse-spatial-runtime-development-20261010-02/completed-status-20261011T001413Z.json)
  authenticates **302 completion evidence hashes**, **925 frozen sources**,
  four raw GPU metric hashes and **91 required passing evidence records**.
  All **136 production modules** match the frozen run. Twelve configured
  histories agree with the qualified predecessor on **17,948,672 state
  values per backend** within the registered tolerances; all twelve L4
  histories also match bitwise. [CPU/L4 agreement](/mnt/workspaces/Cells/betse-spatial-runtime-20261010-02/evidence/gpu/runtime-cpu-gpu.json)
  passes on **17,994,704 runtime values**, alongside the earlier native
  panels. All thirteen state arrays replay bitwise through disk restart,
  changed windows, horizon extension, world reordering and partitions.
  CLI execution and rejected-trial state retention pass on both backends.
  Controller and backend stderr are empty, no failure artifact is present,
  the controller has exited and the L4 is idle. No follow-up job was started.
  The test wrapper now accepts and forwards
  the optional checked-step argument, retaining its parameter-preparation and
  compilation-reuse assertions. Its [focused regression](/mnt/workspaces/Cells/betse-spatial-runtime-development-20261010-02/focused.xml)
  passes in **2.87 s**; Ruff and diff checks also pass. The
  [retry preparation](/mnt/workspaces/Cells/betse-spatial-runtime-development-20261010-02/preparation.json)
  verifies all **136 production modules**, the protocol, tolerances and test
  inventory are unchanged from the failed attempt; only that wrapper differs.
  The first attempt's [failure](/mnt/workspaces/Cells/betse-spatial-runtime-20261010-01/failure.json)
  and frozen evidence remain intact: **215 CPU passes, three declared deferrals,
  one failure and 162 unrun tests** after **19 min 10 s**, without starting L4.
  Its [status receipt](/mnt/workspaces/Cells/betse-spatial-runtime-development-20261010-01/failed-status-20261010T231229Z.json)
  records all **45 new runtime CPU tests** and **44 required CPU evidence
  reports** passing, including twelve complete-state comparisons on
  **17,948,672 values** and bitwise disk/window/world replay. The new
  [configuration](configs/betse_spatial_active.json) registers the existing
  `betse_spatial_nak_kv1p5@1` kernel with the ordinary run, complete snapshot,
  restart, bounded-window and independent-world paths. Explicit
  `betse_ordered_euler@1` dispatch preserves the native update order and
  fixed timestep; the qualified numerical kernel files are unchanged.
  Thirteen state arrays and all six native species are retained, including
  the fixed Ca/P/M charge contributions. This first version supports static
  controls, accepted-step observations and horizons through **256 us**.
  The [runtime protocol](validation/betse/spatial_active/runtime_protocol.json)
  addresses serialization, solver-dispatch and shared-runner risks by
  authenticating the completed predecessor, comparing twelve full histories
  to its saved CPU/L4 states, and checking disk/window/world replay, different
  world clocks, completed-world retention and numerical refusal. All
  **91 required evidence records** pass across both backends. The
  [25 host checks](/mnt/workspaces/Cells/betse-spatial-runtime-development-20261010-01/host-preflight-02.xml)
  and [four bounded CPU smoke checks](/mnt/workspaces/Cells/betse-spatial-runtime-development-20261010-01/compiled-preflight-01-result.json)
  pass; the latter cover eight-step reference agreement, failed-state
  retention, eager/compiled agreement and the existing guarded batch path.
  [Preparation evidence](/mnt/workspaces/Cells/betse-spatial-runtime-development-20261010-01/preparation.json)
  binds the final inputs/sources; the initial export's rejected three-species
  inventory is [preserved](/mnt/workspaces/Cells/betse-spatial-runtime-development-20261010-01/export-attempt-01-failure.json).
  Static/initial arrays now match the six-species native capture bitwise.
  Logs and result/failure artifacts remain under the
  [run directory](/mnt/workspaces/Cells/betse-spatial-runtime-20261010-02).
  The GPU phase lasted **1297.79 s / 0.36050 GPU-hours**, averaging
  **0.4258% GPU-busy** and **0.1429% measured SM-active**, with
  **99.99989% / 99.91121% coverage**, respectively. These whole-phase
  averages include compilation and host correctness checks; no warmed
  throughput interval is defined. Peak child RSS was **3.43 GiB**, with
  **313.3 MB** of artifacts/cache. No automatic retry or follow-up is scheduled.
  Broader native mechanisms, scheduled controls in this compatibility model,
  spatial convergence and remote multi-GPU execution remain open.

- **Longer active BETSE qualification passed at 21:23:56 UTC on
  10 October**, after **44 min**. The
  [result](/mnt/workspaces/Cells/betse-spatial-active-refinement-20261010-01/result.json)
  and [completion receipt](/mnt/workspaces/Cells/betse-spatial-active-refinement-20261010-01/completion.json)
  confirm **126 CPU passes / three declared GPU deferrals**, then **129 L4
  passes / no skips**, with no failures or errors. The
  [registration](/mnt/workspaces/Cells/betse-spatial-active-refinement-20261010-01/registration.json)
  freezes **919 source files and 129 tests**, retaining the earlier active
  and passive panels. The [22:24 UTC status check](/mnt/workspaces/Cells/betse-spatial-active-refinement-development-20261010-01/completed-status-20261010T222451Z.json)
  authenticates **443 completion evidence hashes**, **919 frozen sources**,
  four raw GPU metric hashes and **95 required passing evidence records**.
  All **134 production modules** match both the frozen run and its completed
  predecessor. No failure artifact is present, controller/test stderr is
  empty, the controller has exited and the L4 is idle. No follow-up job was
  started. The
  [protocol](validation/betse/spatial_active/refinement_protocol.json) extends
  the pump-only, channel-only, coupled and partial-availability cases from
  **64 to 256 us**, at **1, 0.5 and 0.25 us** steps. Twelve longer native
  trajectory comparisons pass on **39,954,432 values per backend**, including
  **3,870,720 active comparisons**; the largest long-trajectory error uses
  **25.28%** of its budget. [CPU/L4 agreement](/mnt/workspaces/Cells/betse-spatial-active-refinement-20261010-01/evidence/gpu/long-active-native-cpu-gpu.json)
  passes on **38,635,520 longer-history values**, in addition to both earlier
  panels. Native and Cells temporal refinement pass separately at **64, 128
  and 256 us**: resolved differences shrink by **1.9865–2.0045 times** when
  the timestep is halved. Membrane voltage and the activation gate resolve
  in every case; fields below comparison resolution make no order claim.
  Original **64-us native and Cells state/rate prefixes match bitwise**;
  derived field readouts meet their registered tolerances. All **thirteen
  state arrays** replay bitwise through disk restart, changed windows, world
  reordering and partitions. Deliberate **1e-6 fmol** reservoir, stencil,
  pump-cycle and channel-ledger corruptions are rejected. Physical laws and
  tolerance floors remain unchanged. The GPU phase lasted **879.51 s /
  0.24431 GPU-hours**, averaging **0.6995% GPU-busy** and **0.1875% measured
  SM-active**, with **99.99990% / 100% coverage**, respectively. These
  whole-phase averages include compilation and host correctness checks; no
  warmed throughput interval is defined. Peak child RSS was **5.46 GiB**,
  with **476.6 MB** of artifacts/cache. This validates temporal refinement
  for the declared synthetic native compatibility cases, with maintained
  ATP/ADP/Pi and one Kv1p5 population. Broader native mechanisms, spatial
  convergence, ordinary registry integration and remote multi-GPU execution
  remain open. No automatic retry or follow-up is scheduled.

- **Active Na/K pump + Kv1p5 spatial BETSE qualification passed at
  18:58:50 UTC on 10 October**, after **11 min 28 s**. The
  [result](/mnt/workspaces/Cells/betse-spatial-active-20261010-01/result.json)
  and [completion receipt](/mnt/workspaces/Cells/betse-spatial-active-20261010-01/completion.json)
  confirm **84 CPU passes / two declared GPU deferrals**, followed by
  **86 L4 passes / no skips**, with no failures or errors. The
  [registration](/mnt/workspaces/Cells/betse-spatial-active-20261010-01/registration.json)
  freezes **916 source files and 86 tests**, including the earlier 47-test
  passive suite. The [20:17 UTC status check](/mnt/workspaces/Cells/betse-spatial-active-refinement-development-20261010-01/completed-prior-status-20261010T201727Z.json)
  authenticates **241 completion evidence hashes**, **916 frozen sources**,
  four raw GPU metric hashes and **54 required passing evidence records**;
  all **134 production modules** match the frozen run. No failure artifact
  is present, controller/test stderr is empty, the controller has exited and
  the L4 is idle. No follow-up computation was started. The
  [protocol](validation/betse/spatial_active/protocol.json) covers six synthetic
  cases through **64 us**, at **1 and 0.5 us** steps: disabled, pump-only,
  channel-only, combined, fully blocked and partial availability. Twelve
  fresh observed/bare native pairs pass neutrality; native trajectory
  comparisons cover **6,421,248 values per backend**, including **622,080
  active comparisons**. The largest error uses **27.58%** of its budget.
  [CPU/L4 agreement](/mnt/workspaces/Cells/betse-spatial-active-20261010-01/evidence/gpu/active-native-cpu-gpu.json)
  passes on **6,209,280 active-panel values**, plus **500,160** earlier passive
  values. Independent Decimal pump/flux laws, gates and material checks pass.
  All **thirteen state arrays** replay bitwise across disk restart, changed
  windows, world reordering and partitions. Disabled/blocked controls reduce
  exactly to the passive case; damaged gates, missing/doubled transfers and
  wrong channel input order are rejected. Physical tolerance floors are
  unchanged. The GPU phase lasted **264.42 s / 0.07345 GPU-hours**, with
  **0.5203% GPU-busy** and **0.1203% measured SM-active**, at **99.9985% /
  99.5549% coverage**. These whole-phase averages include compilation and
  host correctness checks; no warmed throughput interval is defined. Peak
  child RSS was **1.85 GiB**, with **92.9 MB** of artifacts/cache. This is
  bounded native compatibility with maintained ATP/ADP/Pi and one Kv1p5
  population. Active temporal refinement, broader native mechanisms,
  ordinary registry integration and remote multi-GPU execution remain open.

- **Extended passive BETSE trajectory/refinement qualification passed at
  16:49:48 UTC on 10 October**, after **14 min 17 s**. The
  [result](/mnt/workspaces/Cells/betse-spatial-refinement-20261010-01/result.json)
  and [completion receipt](/mnt/workspaces/Cells/betse-spatial-refinement-20261010-01/completion.json)
  confirm **71 CPU passes / two declared GPU deferrals**, then **73 L4 passes
  / no skips**, with no failures or errors. The
  [registration](/mnt/workspaces/Cells/betse-spatial-refinement-20261010-01/registration.json)
  freezes **910 source files and 73 tests**, including the earlier 47-test
  suite. The [17:41 UTC audit](/mnt/workspaces/Cells/betse-spatial-refinement-development-20261010-01/completed-status-audit.json)
  verifies **249 completion evidence hashes**, **910 frozen-source hashes**,
  four raw metric hashes and **62 required passing evidence records**. Current
  registered sources match the frozen run; all **133 production modules**
  remain unchanged from the earlier qualification. No failure artifact is
  present; controller stderr is empty, the controller has exited and the L4
  is idle. No follow-up job was started. The
  [protocol](validation/betse/spatial_trajectory/refinement_protocol.json)
  qualifies four passive native cases through **256 us / 32 times the earlier
  duration**, at **1, 0.5 and 0.25 us** steps. Both backends pass all twelve
  complete native trajectory comparisons (**36,083,712 values each**); the
  largest error uses **25.29%** of its comparison budget.
  [CPU/L4 agreement](/mnt/workspaces/Cells/betse-spatial-refinement-20261010-01/evidence/gpu/extended-native-cpu-gpu.json)
  passes on **37,345,280 values**, in addition to the original short panel.
  Original 8-us native prefixes match bitwise. Native and Cells temporal
  refinement pass at **64, 128 and 256 us**: resolved differences shrink by
  **1.9987–2.0074 times** when the timestep is halved. All **nine state fields**
  pass exact disk restart, changed windows, mapped world reordering and
  partitions. Accumulated material residuals reach **4.17e-11 fmol**; physical
  floors are unchanged, with separately reported inventory-scaled
  `gamma_(32*steps)` bookkeeping allowances and a **6e-17 s** clock bound.
  Native per-update tolerances remain unchanged; deliberate **1e-6 fmol**
  ledger corruptions are rejected. CPU tests took **621.26 s** and L4 tests
  **224.63 s**. The instrumented GPU phase lasted **228.20 s / 0.06339
  GPU-hours**: **1.9059% GPU-busy**, **0.6033% measured SM-active**, with
  **99.99935% / 99.52982% coverage**, respectively. These averages include
  compilation and host correctness checks; no warmed throughput interval is
  defined. Peak child RSS was **4.15 GiB**, with **169.3 MB** of artifacts/cache.
  **Next: native whole-tissue comparisons with active pumps/channels.**
  Spatial convergence, ordinary registry integration and remote multi-GPU
  execution remain open; no biological calibration or energy-balance claim
  is made for this passive compatibility component.

- **Native passive BETSE trajectory CPU/L4 qualification passed at
  16:01:53 UTC on 10 October**, after **2 min 43 s**. The
  [result](/mnt/workspaces/Cells/betse-spatial-trajectory-20261010-02/result.json)
  and [completion receipt](/mnt/workspaces/Cells/betse-spatial-trajectory-20261010-02/completion.json)
  confirm **46 CPU passes / one declared GPU deferral**, then **47 L4 passes
  / no skips**, with no failures or errors. The
  [registration](/mnt/workspaces/Cells/betse-spatial-trajectory-20261010-02/registration.json)
  freezes **907 source files and 47 tests**. The
  [16:13 UTC audit](/mnt/workspaces/Cells/betse-spatial-trajectory-development-20261010-02/completed-status-audit.json)
  verifies all **49 completion evidence hashes**, **907 frozen-source hashes**,
  four raw metric hashes and **23 required passing evidence records**. At that check,
  the source matched the frozen run. No failure artifact is present; stderr is
  empty, the controller has exited and the L4 is idle. No follow-up job was
  started. [CPU/L4 agreement](/mnt/workspaces/Cells/betse-spatial-trajectory-20261010-02/evidence/gpu/native-spatial-trajectory-cpu-gpu.json)
  passes on **500,160 complete trajectory values**. Both backends pass all
  eight native comparisons (**483,264 values each**); the largest error uses
  **14.74%** of its tolerance budget. All **nine state fields** pass exact
  disk restart, changed integration windows, world reordering and partitions.
  Invalid-state and corrupted-evidence controls pass. CPU tests took **68.04 s**
  and L4 tests **84.29 s**. The instrumented GPU phase lasted **87.75 s /
  0.02438 GPU-hours**: **0.2541% GPU-busy**, **0.05693% measured SM-active**,
  with **99.99900% / 98.93222% coverage**, respectively. These averages include
  compilation and host correctness checks; no single warmed throughput
  interval is defined. Peak child RSS was **1.21 GiB**, with **13.7 MB** of
  artifacts/cache. The separate `betse_spatial_passive@1`
  [protocol](validation/betse/spatial_trajectory/protocol.json) covers four
  seven-cell/30-patch/10-by-10-grid cases at two timesteps over **8 us**,
  including lagged membrane state, fields, fluxes and separate boundary-reset/
  grid-stencil ledgers. Longer native-matched trajectories and timestep
  refinement have now passed above. Active native tissue comparisons, ordinary model-
  registry integration and remote multi-GPU execution remain open.

- The previous native trajectory run
  [failed](/mnt/workspaces/Cells/betse-spatial-trajectory-20261010-01/failure.json)
  at **15:36:54 UTC on 10 October**, after **2 min 44 s**: **46 CPU passes / one declared
  deferral**, then **46 L4 passes / one failure**. The final CPU/GPU test
  raised `TypeError` while NumPy formatted an array-valued tolerance. The
  correction compares membrane/junction fluxes in fmol/s with the same scalar
  physical tolerance. A [saved-array replay](/mnt/workspaces/Cells/betse-spatial-trajectory-development-20261010-02/preflight.json)
  passes **500,160 CPU/L4 values** and rejects corrupted membrane and junction
  fluxes; the fresh completed qualification above also passes the corrected test.
  Only the test helper changed; all **133 production modules**, the protocol
  and numerical tolerances are unchanged from the failed run. All evidence is preserved. The
  [status audit](/mnt/workspaces/Cells/betse-spatial-trajectory-development-20261010-02/status-audit.json)
  verifies **907 frozen-source hashes**, four raw metric hashes and **22
  required passing evidence records**.
  Previous whole-phase [GPU metrics](/mnt/workspaces/Cells/betse-spatial-trajectory-20261010-01/gpu-metrics/result.json)
  were **0.1371% GPU-busy** and **0.05763% SM-active**, with **99.99901% / 100%**
  coverage over **85.67 s**, including compilation and host checks. Earlier
  [development evidence](/mnt/workspaces/Cells/betse-spatial-trajectory-development-20261010-01/preflight.json)
  preserves the initial batch-wrapper failure and its passing replay fix.

- **Resolved calcium/IP3/assembly passed CPU/L4 qualification at 14:55:50 UTC
  on 10 October**, after **2 h 16 min 9 s**. The
  [result](/mnt/workspaces/Cells/surface-calcium-20261010-02/result.json)
  and [completion receipt](/mnt/workspaces/Cells/surface-calcium-20261010-02/completion.json)
  confirm **152 CPU passes / one declared GPU deferral**, then **153 L4 passes
  / no skips**, with no errors or failures. The
  [registration](/mnt/workspaces/Cells/surface-calcium-20261010-02/registration.json)
  binds **902 source files and 153 tests**. On the 14:59 UTC status check,
  all **83 receipt evidence hashes**, **902 frozen-source hashes**, four raw
  GPU metric hashes and **55 required passing evidence records** verified.
  No failure artifact is present; stderr is empty and the controller has
  exited. The L4 is idle; no follow-up job was started.
  [CPU/L4 agreement](/mnt/workspaces/Cells/surface-calcium-20261010-02/evidence/gpu/resolved-calcium-cpu-gpu.json)
  passes on **119,190 saved state/readout values**, including coupled assembly,
  with separate charge/current/voltage tolerances and exact discrete state.
  All four independent **2-ms trajectories** pass; worst complete-state error
  uses **49.60%** of its tolerance budget. Refinement, all **34 ionic state
  fields**, complete restart, world partition/reordering, ensemble endpoints,
  planning and aggregation pass. The
  [assembly reference](/mnt/workspaces/Cells/surface-calcium-20261010-02/evidence/gpu/resolved-calcium-assembly-reference.json)
  passes at **2.013% of its state tolerance budget**. The
  [assembly replay and ligand response](/mnt/workspaces/Cells/surface-calcium-20261010-02/evidence/gpu/resolved-calcium-assembly-replay.json)
  passes bitwise restart/window/partition checks; the IP3 perturbation changes
  calcium by **7.04e-5 fmol** while all pool/event fields remain unchanged.
  The instrumented GPU phase took **91 min 11 s / 1.5197 GPU-hours**. Mean
  **GPU-busy was 0.3490%**, and measured **SM-active was 0.005391%**, with
  **99.99986% / 99.98258% coverage**, respectively. These averages include
  compilation and host correctness checks; no single fully warmed interval
  is defined. Peak child RSS was **12.05 GiB**, within the **16 GiB** bound.
  Qualification covers the declared synthetic, closed finite exterior cases.
  Held-bath calcium, native whole-BETSE tissue/field equivalence and remote
  multi-GPU execution remain open; no biological calibration is claimed.
  The test fix replaces the coupled-state-only helper with the existing
  pool-compatible comparator for the IP3 perturbation. All **19 pool fields**
  still require identical shape, dtype and raw bits. The
  [bounded preflight](/mnt/workspaces/Cells/surface-calcium-development-20261010-02/preflight.json)
  accepts the saved pool state, rejects a one-bit change in every field and
  rejects shape/type changes. Existing sixteen-GPU planning and saved-report
  aggregation checks also pass. Only `tests/unit/test_surface_calcium.py`
  differs from the prior frozen source; all **132 production modules**, the
  qualification protocol and numerical tolerances are unchanged. Prior failed
  evidence remains untouched. The completed run now verifies the full
  assembly ligand-response comparison on both CPU and L4.

- **Previous resolved calcium/IP3/assembly attempt stopped at 01:08:18 UTC on
  10 October**, after **54 min 4 s**, with a test-helper error. Checked at
  **11:52:52 UTC**: controller and worker have exited; **the L4 phase never
  started**, and the device is idle. The
  [CPU report](/mnt/workspaces/Cells/surface-calcium-20261010-01/cpu.xml)
  records **97 passes, one declared GPU deferral and one failure**; 54 of the
  153 registered tests were not reached. The
  [failure artifact](/mnt/workspaces/Cells/surface-calcium-20261010-01/failure.json)
  and [traceback](/mnt/workspaces/Cells/surface-calcium-20261010-01/cpu.stdout.log)
  identify `same(reduced.pool, state.pool)` in the assembly ligand-response
  test: the helper expects a complete coupled state, but receives `PoolState`,
  raising `AttributeError` before comparing its fields. This is a test API
  mismatch; the unchanged-event comparison and subsequent calcium-response
  assertion were not reached in that run. The correction and fresh run are
  recorded above.
  The [launch receipt](/mnt/workspaces/Cells/surface-calcium-20261010-01/launch.json)
  and [registration](/mnt/workspaces/Cells/surface-calcium-20261010-01/registration.json)
  preserve **902 frozen files and 153 tests** from the 00:14:12 UTC launch.
  No result/completion artifact is present. All
  four **2-ms independent CPU trajectory comparisons now pass**, including
  the previously failing initial reference probe. The worst complete-state
  comparison uses **49.60% of its tolerance budget** in the
  [release arm](/mnt/workspaces/Cells/surface-calcium-20261010-01/evidence/cpu/resolved-calcium-trajectory-release.json).
  [Timestep refinement](/mnt/workspaces/Cells/surface-calcium-20261010-01/evidence/cpu/resolved-calcium-refinement.json)
  passes: maximum errors fall from **5.10e-12 to 3.19e-13 to 2.00e-14** as
  the step is halved twice. [Complete restart](/mnt/workspaces/Cells/surface-calcium-20261010-01/evidence/cpu/resolved-calcium-restart.json)
  passes bitwise across all **34 state fields**, including disk/fresh-process
  continuation, terminal restart, future branches and changed windows.
  [World partition/reordering](/mnt/workspaces/Cells/surface-calcium-20261010-01/evidence/cpu/resolved-calcium-partition.json)
  now passes bitwise, including independent restart at 1 and 2 ms.
  [Ensemble execution](/mnt/workspaces/Cells/surface-calcium-20261010-01/evidence/cpu/resolved-calcium-ensemble.json)
  passes complete-state and patch-voltage checks; its timings show **356 s
  compilation versus 1.73 s execution**. The
  [two-world assembly run](/mnt/workspaces/Cells/surface-calcium-20261010-01/evidence/cpu/resolved-calcium-assembly.json)
  completed 2 ms with **nine committed events**. The
  [independent assembly trajectory](/mnt/workspaces/Cells/surface-calcium-20261010-01/evidence/cpu/resolved-calcium-assembly-reference.json)
  passes, using **2.013% of its complete-state tolerance budget**.
  Assembly replay/ligand-response qualification, the remaining shared
  regressions and all L4 checks remain incomplete.
  Logs and result/failure artifacts are under the
  [previous run directory](/mnt/workspaces/Cells/surface-calcium-20261010-01).
  GPU-busy and measured SM-active counters retain per-counter coverage.
  No automatic polling, retry or follow-up audit is scheduled. The
  [protocol](validation/tissue/surface_calcium_protocol.json) tests independent
  trajectories, conservation/energy, all **34 complete state arrays**, replay,
  assembly event coupling and CPU/L4 agreement. **Qualification remains incomplete.**
  The earlier blocker was cancellation in the independent reference's logarithmic
  means near equal concentrations: its field-current and transport evaluations
  disagreed. Both now use a stable scalar `log1p` formula, independently of
  production's atanh/series implementation. The
  [reproduced failure](/mnt/workspaces/Cells/surface-calcium-development-20261010-01/reference-initial-step-failure.json)
  and [fixed-state check](/mnt/workspaces/Cells/surface-calcium-development-20261010-01/reference-initial-step-fixed.json)
  show current disagreement falling from **8.01e-21 A to 2.02e-28 A**;
  the fixed node-current residual is **8.08e-28 A**. All **132 production
  modules and numerical tolerances are unchanged** from the 9 October failed run.
  [21 new reference checks](/mnt/workspaces/Cells/surface-calcium-development-20261010-01/reference-tests.xml)
  pass against 90-digit Decimal arithmetic and small initial probes in all
  four calcium arms; [29 related stage checks](/mnt/workspaces/Cells/surface-calcium-development-20261010-01/stage-tests.xml)
  also pass. These bounded checks do not establish complete trajectory parity.
  The previous run stopped at **18:41:32 UTC on 9 October**, after **5 min 15 s**:
  [66 CPU passes and one setup error](/mnt/workspaces/Cells/surface-calcium-20261009-01/cpu.xml),
  before GPU execution. Its [failure artifact](/mnt/workspaces/Cells/surface-calcium-20261009-01/failure.json)
  and [traceback](/mnt/workspaces/Cells/surface-calcium-20261009-01/cpu.stdout.log)
  remain untouched. All four production **2-ms CPU trajectories** were saved
  with passing internal checks; independent trajectory agreement was not reached.
  The new `resolved_calcium@1` model gives each cell one finite cytosol/ER store;
  free calcium drives transport while binding/ER exchange cannot spuriously
  charge plasma capacitors. It includes IP3 release, Cav1.2, PMCA/NCX and
  cell-owned assembly control of multiple Kv1.5 patches. **Closed finite
  exterior only**: held-bath calcium needs a separate input/loss bound.
  [Ordinary](configs/resolved_calcium_tissue.json) and
  [assembly](configs/assembly_resolved_calcium_tissue.json) GPU examples are
  synthetic, not calibrated tissue measurements. The
  [development evidence](/mnt/workspaces/Cells/surface-calcium-development-20261009-01)
  contains **67 passing host checks**, guarded-JAX tracing and independent
  evolved-stage comparisons. An initial chemical-event grid failure was fixed
  and its log preserved; an ad hoc absolute-only rate assertion is retained
  alongside the passing predeclared absolute-plus-relative comparisons.
  [Source comparison](/mnt/workspaces/Cells/surface-calcium-development-20261009-01/source-changes.json)
  against the preceding frozen run shows two new production modules, eight
  changed adapters/accounting modules and 122 unchanged files. No new native
  whole-BETSE equivalence or Jupiter execution is claimed.

- **Future planning, 10 October:** the [mitochondria literature note](docs/PAPER_REVIEW_MITOCHONDRIA.md)
  records experimental evidence, corrections to the essay's interpretation,
  and proposed finite-energy, ER/calcium and inheritance extensions. It also
  identifies a mitochondrial reference model and its parameter-table correction.

- **8 October priority: park further GPU utilization optimization and return
  to simulator capabilities.** Future GPU runs should report both **GPU busy
  time and measured SM-active percentage**, for the whole run and after warmup,
  with per-device coverage. Keep throughput, allocated GPU/node time and arm
  finish gaps alongside them; missing counters are explicitly unavailable,
  never zero. The matched benchmark runners and the new component qualification
  mode collect both metrics. Carry that monitoring into any other runner before
  its next GPU run. Cross-region tissue coupling and its calcium/IP3/assembly
  composition now pass the bounded numerical qualifications below. Native full
  BETSE tissue comparison remains open.

- **Resolved pumps and intrinsic channel/junction kinetics passed CPU/L4
  qualification at 17:38:42 UTC on 9 October**, in **74 min 23 s**:
  **124 CPU passes / one declared GPU deferral**, then **125 L4 passes / no
  skips**. The [result](/mnt/workspaces/Cells/surface-kinetic-20261009-01/result.json)
  and [completion receipt](/mnt/workspaces/Cells/surface-kinetic-20261009-01/completion.json)
  agree with the [frozen registration](/mnt/workspaces/Cells/surface-kinetic-20261009-01/registration.json).
  All 59 receipt evidence hashes, 893 frozen-source hashes and raw GPU-metric
  hashes check. No failure artifact is present; stderr is empty. The controller
  has exited. The [CPU/L4 comparison](/mnt/workspaces/Cells/surface-kinetic-20261009-01/evidence/gpu/resolved-kinetic-cpu-gpu.json)
  passes on **17,284 saved state/readout values**, with separate charge, current
  and voltage tolerances. All four independent **2-ms** trajectory comparisons
  pass, with maximum state error using **11.88% of the tolerance budget**.
  [Refinement](/mnt/workspaces/Cells/surface-kinetic-20261009-01/evidence/gpu/resolved-kinetic-refinement.json),
  [complete restart](/mnt/workspaces/Cells/surface-kinetic-20261009-01/evidence/gpu/resolved-kinetic-restart.json)
  and [world partition/reordering](/mnt/workspaces/Cells/surface-kinetic-20261009-01/evidence/gpu/resolved-kinetic-partition.json)
  pass, including bitwise replay of all nineteen fields. Ensemble execution,
  future control branches, windows and shared schema/checkpoint regressions pass.
  [The new model](src/cells/models/surface_kinetic.py), `resolved_tissue@2`, adds
  patch-local Kv1.5 m/h gates, evolving junction conductance and maintained-pool
  Na/K ATPases to the resolved electrical law. **Nineteen complete state arrays**
  retain gates, separate channel/pump transfers, dissipation and metabolic work.
  Electrode and reservoir source rates include the added transport. The
  [example](configs/resolved_kinetic_tissue.json) selects the GPU backend.
  The [protocol](validation/tissue/surface_kinetic_protocol.json) also checks
  independent compact/padded rates, forward/reverse pump work, patch ownership,
  blocking without gate resets, shared-patch channels, passive reduction and all
  nineteen corruption controls. The [host preflight](/mnt/workspaces/Cells/surface-kinetic-development-20261009-01/host-tests-02.xml)
  passed 63 tests, and the [short-step checks](/mnt/workspaces/Cells/surface-kinetic-development-20261009-01/short-step-preflight-01.json)
  also passed. The
  [prelaunch record](/mnt/workspaces/Cells/surface-kinetic-development-20261009-01/prelaunch-01.json)
  confirms **124 of 128 previous production files unchanged**; four dispatch
  files changed and two model/schema files were added. Qualified field and
  process laws are unchanged; Ruff and whitespace checks pass. Artifacts/cache
  total **143.22 MB**, with peak child RSS **7.801 GB**, within the registered
  **3-hour / 2-GiB artifact-cache / 10-GiB RSS** limits. The GPU phase took
  **51 min 49 s / 0.86362 L4 GPU-hours**, averaging **0.07563% GPU busy /
  0.002027% measured SM-active**, with **99.99996% / 100% coverage**. These
  averages include compilation and host checks; no single warmed interval or
  throughput claim is inferred. Calcium/IP3/assembly composition with this
  resolved field is now under qualification above. Native full-tissue BETSE equivalence and Jupiter execution
  remain open. No automatic follow-up is scheduled.

- **Resolved evolving tissue passed CPU/L4 qualification at 14:55:17 UTC on
  9 October**, in **62 min 2 s**: **133 CPU passes / two declared GPU deferrals**,
  then **135 L4 passes / no skips**. The
  [result](/mnt/workspaces/Cells/surface-tissue-20261009-01/result.json) and
  [completion receipt](/mnt/workspaces/Cells/surface-tissue-20261009-01/completion.json)
  are present; their result/registration hash links check against the
  [frozen registration](/mnt/workspaces/Cells/surface-tissue-20261009-01/registration.json).
  All four independent trajectory comparisons pass on CPU and L4, with maximum
  state error using **8.85% of its registered tolerance budget**. The
  [CPU/L4 comparison](/mnt/workspaces/Cells/surface-tissue-20261009-01/evidence/gpu/resolved-cpu-gpu.json)
  passes on **13,008 saved state/readout values**, with separate charge, current
  and voltage tolerances. The repeated field comparison passes on another
  **4,977 physical values**. The
  [refinement check](/mnt/workspaces/Cells/surface-tissue-20261009-01/evidence/gpu/resolved-refinement.json),
  [complete restart checks](/mnt/workspaces/Cells/surface-tissue-20261009-01/evidence/gpu/resolved-restart.json)
  and [world partition/reordering checks](/mnt/workspaces/Cells/surface-tissue-20261009-01/evidence/gpu/resolved-partition.json)
  pass, including bitwise replay of all twelve fields. Both new and prior
  kinetic-model ensemble checks pass. No failure artifact is present; stderr
  is empty. The controller has exited and the L4 is idle.
  The new [registered model](src/cells/models/surface_tissue.py),
  `resolved_tissue@1`, advances finite ionic inventories through multiple membrane
  patches with the qualified same-stage charge/return-current field. Twelve
  complete state arrays retain route transfers, reservoir supply, dissipation,
  electrode charge and both source works. Reservoir concentrations/voltages are
  held; membrane/junction availability is scheduled, with actual-control guards
  at every RK4 trial and endpoint. The [synthetic example](configs/resolved_tissue.json)
  selects the L4 backend. Ordinary snapshots, scalar/batch windows and ionic-world
  ensembles use this model; ensemble voltages explicitly identify membrane patches.
  The [trajectory protocol](validation/tissue/surface_dynamics_protocol.json)
  collects **135 checks per phase**, with two declared CPU GPU-only deferrals:
  four **2-ms** open/closed/clamped/release arms versus independent full-node
  roots, Decimal transport and segmented DOP853; three timesteps; complete disk,
  fresh-process and terminal restart; future branches; changed windows; world
  splitting/reordering and independent clocks. It also repeats the field suite,
  shared schema/checkpoint checks and a short previous kinetic-tissue ensemble.
  [Initial independent rate checks](/mnt/workspaces/Cells/surface-tissue-development-20261009-01/preflight-01.json)
  pass all four arms. **38 quick host checks passed** in
  [3.44 seconds](/mnt/workspaces/Cells/surface-tissue-development-20261009-01/host-tests-01.xml).
  [Three-step host preflights](/mnt/workspaces/Cells/surface-tissue-development-20261009-01/short-step-preflight-01.json)
  pass all four arms: material residual at most **2.08e-20 fmol**, capacitor
  charge residual **5.05e-29 C**, energy residual **2.03e-14 pJ**, with nonzero
  clamped electrode charge/work. The
  [prelaunch record](/mnt/workspaces/Cells/surface-tissue-development-20261009-01/prelaunch-01.json)
  confirms **122 of 126 previous production files unchanged**; changes are limited
  to four registration/control/ensemble dispatch files, plus two new model/schema
  files. Qualified transport and field laws are unchanged. Ruff and whitespace
  checks pass. Artifacts/cache total **127.71 MB**; peak child RSS was **6.417 GB**,
  within the **90-minute / 2-GiB artifact-cache / 8-GiB RSS** limits. The GPU phase
  took **39 min 28 s / 0.65784 L4 GPU-hours**, averaging **0.08920% GPU busy /
  0.006553% measured SM-active**, with **99.99999% / 100% counter coverage**.
  These include compilation and host correctness work; no single warmed interval
  or throughput claim is inferred. Held passive boundaries, accepted-grid observations and
  the **256-node dense bound** remain explicit. Composition with intrinsic
  kinetics/pumps and calcium/IP3/assembly, and native full-tissue equivalence
  remain open. Next: integrate the existing pumps and intrinsic channel/junction
  kinetics with this resolved electrical law, then calcium/IP3/assembly.
  No automatic follow-up is scheduled.

- **Coupled resolved-surface field passed CPU/L4 qualification at 13:28:56 UTC
  on 9 October**, in **7 min 11 s**: **33 CPU passes / one declared GPU
  deferral**, then **34 L4 passes / no skips**. The
  [result](/mnt/workspaces/Cells/surface-field-20261009-02/result.json) and
  [completion receipt](/mnt/workspaces/Cells/surface-field-20261009-02/completion.json)
  are present; their result/registration hash links check. The
  [registered retry](/mnt/workspaces/Cells/surface-field-20261009-02/registration.json)
  used the existing detached runner with frozen inputs. Its
  [CPU/L4 comparison](/mnt/workspaces/Cells/surface-field-20261009-02/evidence/gpu/field-cpu-gpu.json)
  passes on **4,977 physical values** at the registered tolerances. Four worlds
  replay bitwise when split into two pairs or reordered through the production
  `lax.map` execution path; the
  [batch evidence](/mnt/workspaces/Cells/surface-field-20261009-02/evidence/gpu/batch-partitions.json)
  also checks direct `vmap` within the original physical tolerances. The
  [first run](/mnt/workspaces/Cells/surface-field-20261009-01/failure.json)
  failed at **13:01:29 UTC on 9 October**, after **6 min 39 s**: **33 CPU
  passes / one declared GPU deferral**, then **32 L4 passes** before the
  partition-replay check failed. Direct `vmap` with four worlds versus two
  pairs changed the first differing voltage field by at most **4.34e-19 V**.
  That first run remains failed; its source snapshot, outputs and logs are
  preserved. Exact replay now uses `lax.map`, as the existing production batch
  runner does. Direct `vmap` remains checked against mapped and repartitioned
  results using the original physical tolerances, with independent accounting
  and all outputs/differences retained. The
  [prelaunch comparison](/mnt/workspaces/Cells/surface-field-development-20261009-02/prelaunch-01.json)
  confirms all **126 production files**, numerical tolerances, resource limits
  and test identities are unchanged; only the batching test's execution/checks
  changed. All **4,977 saved CPU/L4 physical values** from the first run compare
  within the original bounds. The new
  [component](src/cells/numerics/surface_field.py) solves finite-node capacitor
  charge constraints and floating-component return currents from the same stage
  and actual controls. Reservoirs impose held concentrations and voltages, with
  separate electrode charge, current and work. Closed geometries retain one
  gauge without adding an electrode. Incompatible charge, invalid domains and
  exhausted roots are rejected; no charge repair or regularization is used.
  The [protocol](validation/tissue/surface_field_protocol.json) has **34 checks
  per phase**, including one declared CPU deferral. Eleven cases cover open,
  closed, partially/fully clamped, blocked and equilibrium states; one-owner
  reduction, subdivision, padding, divalent ions and actual native topology.
  An independent full-node root and scalar laws check the production reduced
  solve, every finite-node charge/charge-rate constraint, current balance,
  material supply and chemical-plus-capacitor energy including both sources.
  The [first preflight](/mnt/workspaces/Cells/surface-field-development-20261009-01/preflight-01.json)
  passes five NumPy field cases. The
  [compiled CPU/native-geometry preflight](/mnt/workspaces/Cells/surface-field-development-20261009-01/device-preflight-01.json)
  passes the existing tissue-law reduction, independent energy derivatives,
  deliberate wrong-field/source-ledger rejection and the seven-cell, 30-surface,
  100-outside topology. Its local charge-rate residual is **2.21e-27 A** and
  energy residual **1.02e-16 pJ/s**. All **125 previous production sources** are
  unchanged; one new field component is added. Five invalid-definition tests
  and Ruff checks pass. The native geometry uses explicit manufactured
  compatible charge and synthetic conservative outside coefficients; native
  full-field equivalence remains open. This bounded dense component supports
  up to **256 total cell/outside nodes**, with independent-world batching;
  evolving-model registration, trajectories, dynamic boundary schedules and
  calcium/IP3/assembly composition remain next. The
  [electrical contract](docs/TISSUE_RETURN_CURRENT.md) states the charge/current
  equations and source-power identity. The successful retry's GPU phase recorded
  **0.05934% busy / 0.03879% measured SM-active**, with **99.9984% / 100%
  coverage**, over **232.98 seconds / 0.06472 L4 GPU-hours**. Artifacts/cache
  total **20.24 MB**; peak child RSS was **1.650 GB**. These small correctness
  checks include compilation and host work; no warmed interval or throughput
  claim is inferred. The failed run's GPU phase recorded
  **0.08268% busy / 0.04102% measured SM-active**, with **99.9995% / 99.5788%
  coverage**, over **216.10 seconds / 0.06003 L4 GPU-hours**. The retry stayed
  within its combined **30-minute**, 1 GiB artifact/cache and 6 GiB child-RSS
  limits. The evolving model above now integrates this field and has passed
  trajectory/refinement/restart/batch qualification. Both controllers have exited.

- **Resolved membrane surfaces and reservoir transport passed CPU/L4
  qualification at 23:02:17 UTC on 8 October**, in **86.64 seconds**:
  **33 CPU passes / one declared GPU deferral**, then **34 L4 passes / no
  skips**. The [result](/mnt/workspaces/Cells/surface-transport-20261008-01/result.json)
  and [completion receipt](/mnt/workspaces/Cells/surface-transport-20261008-01/completion.json)
  are present; their result/registration hash links check. The
  [registered run](/mnt/workspaces/Cells/surface-transport-20261008-01/registration.json)
  uses the existing detached component runner with frozen sources and durable
  result/failure artifacts under `/mnt/workspaces`.
  [Production code](src/cells/numerics/surface_transport.py) gives each membrane
  patch its own outside owner, area, capacitance, permeability and voltage while
  retaining one equipotential cell interior. It returns patch/outside capacitor
  charges, GHK membrane/junction and conservative logmean outside-face rates,
  finite-owner rates, signed reservoir supply and explicit boundary resets.
  The [protocol](validation/tissue/surface_protocol.json) has **34 checks per
  phase**, with one declared CPU deferral. Nine synthetic cases exercise
  independent scalar/Decimal laws, material and electrochemical port-power
  accounting, patch subdivision, reversal, gauge changes, neutral species,
  padding, blocking, isolated routes, invalid domains and batched-world replay.
  The prior native capture supplies seven cells, 30 membrane patches, 100 grid
  sites and 36 boundary reservoirs; its membrane/junction inputs are compared
  without averaging patch voltages. Its 180 graph faces use explicitly synthetic
  conservative coefficients, not BETSE's finite-difference stencil.
  The [CPU/L4 comparison](/mnt/workspaces/Cells/surface-transport-20261008-01/evidence/gpu/surface-cpu-gpu.json)
  passes on **2,712 saved values**, with `rtol=3e-10` and registered unit-specific
  absolute tolerances. The
  [native surface comparison](/mnt/workspaces/Cells/surface-transport-20261008-01/evidence/gpu/native-surfaces.json)
  passes on **1,008 membrane/junction flux values**, with maximum error
  **3.47e-18 fmol/s**. Seven independent worlds replay bitwise when split into
  groups of three and four. Corrupted cell transfers, reservoir supply and patch
  charges are rejected.
  The [preflight](/mnt/workspaces/Cells/surface-transport-development-20261008-01/preflight-01.json)
  passes eight NumPy physical cases, a JIT CPU case and native first-step fluxes:
  material residual at most **6.94e-18 fmol/s**, with native flux error at most
  **4.34e-19 fmol/s**. Eight malformed-layout tests and Ruff checks pass.
  [Additional prelaunch checks](/mnt/workspaces/Cells/surface-transport-development-20261008-01/prelaunch-01.json)
  cover the isolated-route case and all **124 unchanged prior production
  sources**. Its material residual is **1.04e-17 fmol/s** and electrochemical
  port-power residual **4.44e-16 pJ/s**; one production component is added.
  The explicit voltage comparison measures the capacitance-weighted boundary
  correction: native ionic-charge voltage and resolved patch charge differ by
  up to **91.18 microvolts** in this witness. This is a supplied-field component,
  not a new registered evolving model or full BETSE trajectory equivalence.
  The field qualification above now covers coupled patch countercharges,
  return currents and held electrical reservoir conditions; integration into
  an evolving model remains next under the
  [contract](docs/TISSUE_RETURN_CURRENT.md).
  Whole GPU-phase busy time was **0.05197%**, measured SM activity **0.003144%**,
  with **99.9996% / 100% coverage**, over **41.16 seconds / 0.01143 L4 GPU-hours**.
  These small correctness checks include compilation and host work; no single
  warmed interval is available and no throughput conclusion follows. Artifacts
  and cache total **12.39 MB**; peak child RSS was **1.096 GB**. The controller
  has exited and the L4 is idle. No automatic follow-up is scheduled.

- **Native BETSE spatial contact passed CPU/L4 qualification at 22:17:17 UTC
  on 8 October**, in **77.35 seconds**: **16 CPU passes / one declared GPU
  deferral**, then **17 L4 passes / no skips**. The
  [result](/mnt/workspaces/Cells/betse-tissue-contact-20261008-01/result.json) and
  [completion receipt](/mnt/workspaces/Cells/betse-tissue-contact-20261008-01/completion.json)
  are present; their result/registration hash links check. The
  [registered run](/mnt/workspaces/Cells/betse-tissue-contact-20261008-01/registration.json)
  uses the existing detached component runner with a new
  [protocol](validation/betse/tissue_contact/protocol.json): **16 native runs /
  eight observed-bare pairs**, four synthetic **8-microsecond** cases at
  **1 / 0.5 microsecond** steps, on seven cells, 30 membrane faces and a
  10-by-10 extracellular grid. **17 checks per phase** cover source-bound
  geometry/lifecycle, independent update accounting, observer neutrality,
  deliberate corruption rejection, Decimal GHK correspondence and production
  CPU/L4 transport laws. The
  [shared-law comparison](/mnt/workspaces/Cells/betse-tissue-contact-20261008-01/evidence/gpu/native-spatial-shared-laws.json)
  passes on **17,280 native transport values**, with maximum native/L4 error
  **5.21e-18 fmol/s**; the
  [CPU/L4 comparison](/mnt/workspaces/Cells/betse-tissue-contact-20261008-01/evidence/gpu/native-spatial-cpu-gpu.json)
  passes at `atol=2e-11 fmol/s`, `rtol=3e-10`. Independent native-update
  accounting bounds membrane/junction material residuals to **1.06e-13 fmol**
  and reservoir/stencil residuals to **1.12e-12 fmol**. All eight observed/bare
  final states and histories are bitwise equal, and four deliberate corruptions
  are rejected. The
  [preflight](/mnt/workspaces/Cells/betse-tissue-contact-development-20261008-01/device-preflight-01.json)
  confirms all **124 qualified production source files** remain unchanged;
  host protocol/stencil tests, Ruff and whitespace checks also pass.
  Native spatial mode differs from Cells' current tissue law: it uses reservoir
  boundaries, multiple membrane/outside owners per cell and a screened field.
  The witness measures **182 microvolts of within-cell membrane-voltage spread**.
  The [comparison contract](docs/TISSUE_RETURN_CURRENT.md) keeps these differences
  explicit, including native boundary-derivative signs and drift constants.
  This panel targets native update semantics and shared transport laws, not
  full tissue trajectory equivalence, a convergence ladder or biology.
  The first [recorder failure](/mnt/workspaces/Cells/betse-tissue-contact-development-20261008-01/smoke-01/failure.json)
  and [reference boundary-sign failure](/mnt/workspaces/Cells/betse-tissue-contact-development-20261008-01/reference-preflight-01.log)
  remain preserved; corrections changed validation code only. Whole GPU-phase
  sampled busy time was **0%**, measured SM activity **0.00009569%**, with
  **99.967% / 100% coverage**, over **12.11 seconds / 0.003364 L4 GPU-hours**.
  Physical GPU placement is checked; coarse busy sampling does not resolve
  these tiny kernels. No throughput conclusion or single warmed interval is
  available. Artifacts/cache total **22.23 MB**; peak child RSS was **0.977 GB**.
  The resolved-surface component above advances membrane ownership, reservoir
  exchange and explicit voltage correspondence; matched tissue trajectories
  remain open. No automatic follow-up is scheduled.

- **Cross-region calcium/IP3/assembly passed CPU/L4 qualification at
  21:29:39 UTC on 8 October**, in **47 min**: **66 CPU passes / two declared
  GPU deferrals**, then **68 L4 passes / no skips**. The
  [result](/mnt/workspaces/Cells/tissue-calcium-20261008-02/result.json) and
  [completion receipt](/mnt/workspaces/Cells/tissue-calcium-20261008-02/completion.json)
  are present; their result/registration hash links check. The new
  [spatial_calcium@5 composition](src/cells/models/tissue_calcium.py)
  combines owned free/bound calcium, ER storage, PMCA/NCX, CaV1.2 and finite IP3
  with the qualified tissue field. Existing assembly event clocks use its
  actual-control RK4 guard; complete snapshots retain all 25 ionic/chemical
  state fields and pending random events. Observations require accepted
  boundaries, including chemical interventions. Ordinary world batching and
  the existing 16-GPU task planner recognize the model.
  Four synthetic two-cell, three-outside, **2-ms** cases pass independent
  adaptive chemistry/field references, complete material/charge/energy
  accounting, three-step refinement, IP3 branches and changed windows. Complete
  restart, fresh-process restart and world partition replay are bitwise on each
  backend, including assembly's pending events. Independent assembly event
  references and ligand-response checks pass. The
  [CPU/L4 comparison](/mnt/workspaces/Cells/tissue-calcium-20261008-02/evidence/gpu/calcium-cpu-gpu.json)
  passes on **157,168 complete-state scalars** with state `atol=3e-13`,
  `rtol=3e-10` and voltage `atol=3e-11 V`; the field panel also passes on
  **370 physical values**. Refinement reduces the maximum chemical error from
  **1.84e-12** to **1.09e-13** to **6.64e-15 fmol**. The
  [protocol](validation/tissue/calcium_protocol.json) and
  [registration](/mnt/workspaces/Cells/tissue-calcium-20261008-02/registration.json)
  retain all 68 checks per phase, unchanged tolerances and resource limits.
  Whole GPU-phase busy time was **0.85125%**, measured SM activity **0.013107%**,
  with **99.999% / 99.952% coverage**, over **31 min 46 s / 0.5294 L4 GPU-hours**.
  These small correctness checks include compilation and host work; no single
  warmed interval is available and no throughput conclusion follows. Artifacts
  and cache total **88.95 MB**; peak child RSS was **5.78 GB**. This is numerical
  qualification of the declared fixture, with one-way assembly control of
  potassium-channel availability. Native full BETSE tissue trajectories,
  biological calibration and actual multi-GPU scaling remain open.
  The [first failure](/mnt/workspaces/Cells/tissue-calcium-20261008-01/failure.json)
  remains preserved: after 32 CPU passes, a corruption test mixed JAX and NumPy
  state fields and hit unsupported `jnp.take(mode='raise')`. Its GPU phase never
  started. The corrected test converts the whole state to NumPy as production
  validators do, checks the valid state, then requires each corruption to raise
  `NumericalError`. The
  [saved-checkpoint preflight](/mnt/workspaces/Cells/tissue-calcium-development-20261008-01/host-conversion-preflight-01.json)
  passes the actual test for both NumPy and JAX CPU states; inventory and energy
  corruptions raise their expected `NumericalError`s. All **124 production
  source files**, scientific inputs, tolerances, protocol and 68 test identities
  are unchanged between the frozen runs; only this test file differs. Ruff,
  formatting and whitespace checks pass. Earlier preflight retains the four
  older families' [byte-identical definitions, fingerprints, initial states,
  layouts and rates](/mnt/workspaces/Cells/tissue-calcium-development-20261008-01/legacy-comparison.json).
  Controller **2096934** has exited; the L4 is idle. No follow-up job was launched.

- **Evolving cross-region tissue passed CPU/L4 qualification at 18:46:55 UTC
  on 8 October**, in **26 min 53 s**: **89 CPU passes / two declared GPU
  deferrals**, then **91 L4 passes / no skips**. The
  [result](/mnt/workspaces/Cells/tissue-model-20261008-02/result.json) and
  [completion check](/mnt/workspaces/Cells/tissue-calcium-development-20261008-01/tissue-completion-check.json)
  verify frozen sources, evidence and raw telemetry. The new
  [spatial_extracellular@3 model](src/cells/models/tissue.py) couples finite
  inventories, kinetic pumps/channels and physical-time junction gates to
  same-stage extracellular return currents. Four synthetic two-cell,
  three-outside, 2-ms cases pass independent adaptive references, conservation,
  three-step refinement, complete/fresh-process restart, future branches,
  changed windows and independent-world partition replay. **6,636 saved CPU/L4
  state values** agree within registered tolerances; restart and partition
  replay are bitwise on each device. Observations require accepted timesteps.
  Whole GPU-phase busy time was **0.08246%**, measured SM activity **0.003203%**,
  with **99.999% / 100% coverage**, over **0.302 L4 GPU-hours**. These small
  correctness tests include compilation and host work, so they establish no
  throughput claim; a single warmed interval is explicitly unavailable.
  The [first failure](/mnt/workspaces/Cells/tissue-model-20261008-01/failure.json)
  remains preserved: its batching test budget was 40 instead of the planner's
  conservative 44 slots. The corrected retry changed only that test allowance;
  all 122 production source files, timesteps and tolerances were unchanged.
  [Earlier preflight evidence](/mnt/workspaces/Cells/tissue-model-development-20261008-01)
  includes frozen-source compatibility and retained retired-VM capture failures.
  Cross-region calcium/IP3/assembly qualification also passed, as recorded
  above. Native full BETSE tissue trajectories and multi-GPU scaling remain open.

- **Cross-region electrical component passed CPU/L4 qualification at
  17:01:36 UTC on 8 October**, in **79.59 seconds**: **33 CPU passes / one GPU
  deferral**, then **34 L4 passes / no skips**, including agreement on **370
  physical values**. The
  [return-current solver](src/cells/numerics/tissue_field.py) couples junction
  current to its extracellular return path at the same instant. The
  [result](/mnt/workspaces/Cells/tissue-field-20261008-01/result.json),
  [protocol](/mnt/workspaces/Cells/tissue-field-20261008-01/component-protocol.json)
  and [completion check](/mnt/workspaces/Cells/tissue-model-development-20261008-01/component-completion-check.json)
  verify frozen inputs, 853 source files and 57 evidence files. Whole GPU-phase
  busy time was **0.1425%**, measured SM activity **0.01835%**, both with **100%
  coverage** over 40.79 seconds / 0.01133 L4 GPU-hours. These tiny correctness
  checks include compilation and host checks; no throughput conclusion follows.
  A fully warmed interval is explicitly unavailable because different kernels
  compile throughout. The independent reference, conservation, gauge, padding,
  blocking and failure checks pass in the declared instantaneous regime.
  The [first reference preflight failure](/mnt/workspaces/Cells/tissue-field-development-20261008-01/reference-preflight.log)
  exposed insufficient Newton stopping margin for independent local charge
  accounting; the solver now targets 1% of the unchanged residual bound.
  Logs and test XML remain in the
  [development directory](/mnt/workspaces/Cells/tissue-field-development-20261008-01).
  Evolving tissue qualification is separate from this component result. The
  [electrical contract](docs/TISSUE_RETURN_CURRENT.md) states the assumptions.

- **Development priority clarified on 22 September: expand and verify the
  simulation stack on CPU/L4 before investing further in JUPITER deployment.**
  The eventual 16-GH200 target remains an architecture constraint; multi-node
  execution and scaling measurements follow representative, qualified models.
  The **100-ms pump/BETSE timestep refinement** and the **20-ms spatial
  pump/channel/junction panel on CPU/L4** are now qualified in their bounded
  regimes. The spatial cluster preserves stage-consistent coupling,
  charge/material/energy accounting and the old model identities; independent
  references, complete restart checks and CPU/L4 agreement all pass. Its two
  cells share one local extracellular owner, with transport through three
  outside regions. The bounded L4 batch-size profile has also completed and
  meets the advisory utilization target: **88.08% whole-job GPU busy time**.
  Cross-region junction coupling, native BETSE spatial parity and multi-GPU
  scaling remain open. **Assembly-regulated interacting cells passed their
  corrected CPU/L4 qualification at 16:37:23 UTC on 27 September**: 53 CPU
  tests passed with three explicit GPU deferrals, followed by all 57 GPU tests.
  Exact restart and partition replay now pass on both devices. Its first
  failed qualification is preserved. The combined model's larger L4 profile
  **completed at 17:38:26 UTC**: all 768 worlds passed, with **87.69% whole-job
  GPU busy time**, **93.24% after warm-up**, and worker finishes **1.87 seconds
  apart**. **Closed compartment chemistry with synthetic finite calcium
  buffering passed its CPU/L4 qualification at 19:50:42 UTC**, in **94.70
  seconds**: 119 CPU passes plus one GPU deferral, followed by all 120 checks
  in the GPU phase. The **finite cytosol/ER model passed CPU/L4 qualification
  at 20:28:29 UTC**, in **503.61 seconds (8 min 24 s)**, with
  buffering, capacitive charge, passive transport, a named BETSE calcium pump
  and calcium-dependent release: **148 CPU passes / two GPU deferrals**,
  followed by **150 GPU-phase passes / no skips**. **Spatial calcium and its
  assembly connection passed CPU/L4 qualification at 23:25:49 UTC on
  27 September**, in **1718.20 seconds (28 min 38 s)**: **186 CPU passes / three
  GPU deferrals**, then **189 GPU-phase passes / no skips**. The earlier failed
  reference-helper run remains preserved. The combined model's independent
  references, accounting, complete restart/partition replay and CPU/L4 agreement
  now pass in the registered synthetic two-cell, 20-ms regime. The first
  **combined calcium/assembly L4 throughput profile completed at 01:17:12 UTC
  on 28 September**, in **15 min 13 s**: all **192 worlds / 14 tasks** passed,
  with **85.34% whole-job GPU busy time**, **89.89% after warm-up** and workers
  finishing **32.60 seconds apart**. The advisory utilization target is met.
  **Plasma calcium extrusion/exchange and assembly (`spatial_calcium@2`) passed
  CPU/L4 qualification at 00:17:17 UTC on 29 September.** The GPU retry finished
  in **32 min 45 s**, with **233 passes / no skips**, using the authenticated
  **229-pass / four-GPU-deferral CPU phase** from the first attempt. The original
  timeout is preserved. Native PMCA function correspondence, synthetic reversible
  NCX, independent trajectories, complete replay and CPU/L4 agreement pass in
  the registered two-cell, 20-ms regime. **The expanded model's L4 throughput
  profile completed at 02:58:50 UTC on 29 September**, in **12 min 24 s**:
  all **128 worlds / six tasks** passed, with **77.58% whole-job GPU busy
  time**, **88.82% after warm-up** and workers finishing **0.14 seconds apart**.
  Both utilization and balanced completion targets were met on this L4 run.
  Native full BETSE trajectories and GH200 scaling remain open.
  **Voltage-gated calcium entry and assembly (`spatial_calcium@3`) passed
  CPU/L4 qualification at 05:36:03 UTC on 30 September**, in **74 min 32 s**:
  **271 CPU passes / five explicit GPU deferrals**, followed by **276 GPU
  passes / no skips**. Native CaV1.2 gate-law checks, independent references,
  timestep refinement, accounting and complete restart/partition replay pass
  in the registered two-cell, 20-ms regime. The first trace-budget failure is
  preserved. The fresh retry changed only the scalar trace allowance to
  **1280 MiB** and added preflight for every refinement grid; scientific
  equations, timesteps and tolerances are unchanged. **Storage was restored
  before the next run:** at 17:37 UTC root had **66 GiB** and `/mnt/workspaces`
  **497 GiB** available. **The expanded model's L4 throughput profile completed
  at 17:52:37 UTC on 30 September**, in **11 min 7 s**: all **128 worlds / six
  tasks** passed, with **88.38% whole-job GPU busy time**, **95.96% after
  warm-up**, and workers finishing **2.33 seconds apart**. Both utilization
  and balanced completion targets were met. Saved checkpoints, accounting,
  arm aggregates and telemetry verify. **Finite IP3 control of ER calcium
  release and assembly (`spatial_calcium@4`) passed CPU/L4 qualification at
  20:03:34 UTC on 1 October.** The complete GPU retry passed **all 311 checks /
  no skips** in **46 min 1 s**, using the verified **305-pass / six-GPU-deferral
  CPU phase** from the first attempt. The original three-hour timeout is
  preserved. Native IP3-factor correspondence, independent trajectories,
  refinement, accounting, complete replay and CPU/L4 agreement pass in the
  registered synthetic two-cell, 20-ms regime. Scientific inputs and tolerances
  are unchanged. **The IP3/assembly L4 throughput profile completed at
  22:53:19 UTC on 1 October**, in **15 min 54 s**: all **128 worlds / six
  tasks / 204,800 world steps** passed. Saved checkpoints, scientific summaries,
  accounting, arm aggregates and telemetry verify. With one persistent worker
  and two CPU cores, GPU busy time was **44.82% whole-job / 49.41% after the
  first worker warm-up**, below the advisory 70% target. That warm interval
  still includes compilation of the second batch shape. Throughput was
  **483.05 worlds/L4 GPU-hour**; the batch arms finished **98.47 seconds apart**.
  This single-worker run does not measure concurrent-worker balance.
  **The instrumented replay completed at 21:19:32 UTC on 2 October**, in
  **17 min 37 s**. All **128 worlds / 52,736 saved state scalars** match the
  preceding run bit for bit. Worker peak RSS was **5.69 GiB**, with a sampled
  process-tree peak of **5.79 GiB**. The traces show hundreds of thousands of
  very short GPU operations, while untraced execution keeps about one CPU
  core busy. This motivated the two-worker comparison with measured memory
  headroom.
  The instrumented run's **40.39% whole-job GPU busy time** includes substantial
  tracing overhead and is not an uninstrumented speed comparison.
  **The two-worker comparison completed at 22:13:34 UTC on 3 October**, in
  **11 min 51 s**. All **128 worlds / 52,736 saved state scalars** match the
  single-worker baseline bit for bit. GPU busy time was **83.94% whole-job /
  90.95% after both workers warmed**, meeting the advisory duty-cycle target.
  **Actual SM-active utilization and achieved occupancy were not measured.**
  Throughput rose **34.19%**, to **648.23 worlds/L4 GPU-hour**, with workers
  finishing **0.88 seconds apart**. Sampled combined process-tree RSS peaked
  at **3.43 GiB**; the memory guard never triggered. This is one local L4
  comparison, including compilation, checks and lightweight resource monitoring.
  **The hardware-counter replay completed at 23:47:28 UTC on 3 October**, in
  **13 min 12 s**, with exact agreement for all **128 worlds / 52,736 saved
  state scalars**. Actual **SM-active utilization was only 0.720% whole-job /
  0.822% after warm-up**, despite **76.35% / 87.49% GPU busy time**. Measured
  SM occupancy was **0.0195% / 0.0210%**; all counters had **100% coverage**.
  The advisory GPU busy-time gate does not establish effective hardware use.
  **The CPU/L4 parallel-world screen completed at 18:12:07 UTC on 4 October,
  in 38 min 11 s.** The candidate retaining scalar extracellular-field evaluation
  passed all exact L4 comparisons, including restart and partition replay.
  Ordinary batching changed 13 of 1236 state scalars by one or two ULPs and was
  rejected. Both CPU candidate runs exceeded their 600-second run budgets, so
  CPU/L4 agreement remains unevaluated and neither candidate is fully qualified.
  Production defaults are unchanged. The scalar reference path and earlier
  tiny-kernel traces are consistent with low parallelism; no qualified speedup
  or improved SM utilization is yet measured.
  **The narrower CPU/L4 candidate screen completed at 21:49:05 UTC on 4 October,
  in 39 min 19 s.** Both devices completed without timeouts; conservation, complete
  disk restart, changed-window replay, world partitioning and CPU/L4 agreement
  passed. Exact scalar-reference parity failed on **four CPU / 16 L4 values**,
  by one to three ULPs. The candidate remains unqualified and production unchanged.
  Protecting only the dense field solve reduced diagnostic L4 execution time to
  **42.38 seconds** from **102.24 seconds** for whole-field protection, but this
  is not a qualified throughput or SM-utilization result. The remaining work is
  to isolate the full-trajectory rounding differences before another qualification.
  **The CPU/L4 rounding diagnostic completed at 13:05:11 UTC on 5 October,
  in 10 min 11 s.** Both paths reproduce their preceding screen endpoints
  exactly. Their first differences occur at **tick 1 (12.5 microseconds)** on
  both devices. Standalone field probes agree exactly, while complete rate
  evaluations and integrated states expose rounding differences. The saved
  first-step case now supports isolating the responsible arithmetic; the
  precise cause and a qualified optimization remain open.
  **The saved-step operator diagnostic completed at 18:54:03 UTC on 5 October,
  in 48 min 13 s.** L4 protection of the dense solve plus field sums matches
  all six saved reference steps exactly, as does whole-field protection.
  Logarithmic-mean protection does not. CPU batching retains calcium/chemistry
  differences with every tested strategy; the verified scalar CPU path remains.
  **The complete GPU solve-plus-sums screen passed at 19:32:40 UTC on
  5 October, in 6 min 6 s.** All **1600 physical ticks / 1,978,836 saved state
  scalars** match the scalar GPU trace bit for bit. Complete checkpoint reload,
  changed-window restart, world partitioning and scalar CPU/GPU agreement pass.
  This qualifies the registered three-world, 20-ms screen for larger-batch work.
  Production defaults and tolerances remain unchanged. Larger-batch qualification,
  throughput and actual SM utilization are next; no performance gain is yet measured.
  Native full BETSE trajectories and GH200 scaling remain open.

  The new one-way assembly/channel cluster retains explicit per-cell material
  ownership. The new reaction model uses the ordinary float64 CPU/GPU solver,
  scalar/batch windows and complete checkpoints. The ER model composes those
  reactions with membrane transport at every solver stage. The new spatial
  calcium family composes owned cytosol/ER stores with plasma calcium transport,
  junctions, the extracellular field and assembly-controlled potassium channels.
  Versions `@1` through `@4` have completed their bounded combined numerical qualifications.
  New feedback laws remain declared hypotheses until separately supported. Water/volume,
  mechanics and lifecycle stay in the capability backlog. Utilization tuning
  accompanies representative working models and retains every numerical check.
  Frozen evidence remains unchanged.

- **Matched full-batch width-32/64 benchmark completed at 14:53:22 UTC on
  8 October**, in **43 min 39 s / 0.72763 allocated L4 GPU-hours**. The
  [result](/mnt/workspaces/Cells/ip3-tile-pair-20261008-01/result.json),
  [read-only completion check](/mnt/workspaces/Cells/ip3-tile-pair-development-20261008-01/completion-check-20261008.json),
  [registration](/mnt/workspaces/Cells/ip3-tile-pair-20261008-01/registration.json),
  [definition](/mnt/workspaces/Cells/ip3-tile-pair-20261008-01/definition.json) and
  [task plan](/mnt/workspaces/Cells/ip3-tile-pair-20261008-01/plan.json)
  verify **1024 worlds per configuration / 16 full 64-world tasks / 20 ms**.
  Width 32 ran first, then width 64, with separate cold compilation caches,
  two persistent workers on CPU cores **4 and 5**, and matching L4, seeds,
  world IDs, physics, numerical checks, task order and hardware counters.
  Two equal scheduling groups share one physical condition and use disjoint
  IDs: **1024 distinct worlds / 2048 world executions**. The ordinary ensemble
  queue, profiling worker, checkpoint codec, resource guard and DCGM sampler
  were reused. All **1024 matched endpoints / 421,888 state scalars** agree
  bit for bit; each width also reproduces **128 scalar GPU reference endpoints /
  52,736 scalars** exactly. Full-trajectory evidence remains bounded to the prior
  65-world qualification. All **119 production files, eight frozen drivers and
  30 evidence artifacts per phase** pass completion verification.
  **Width 32 is faster in this comparison:** **1175.05 s / 3137.24 worlds per
  GPU-hour**, versus **1424.32 s / 2588.18** at width 64, whose throughput is
  **17.5% lower**. Whole-job GPU busy time is **77.64% / 74.18%** for widths
  32 / 64; after both workers warm, it is **83.21% / 82.06%**. Both meet the
  advisory 70% busy target. Actual whole-job SM activity is **1.032% / 0.845%**,
  rising to **1.099% / 0.930%** after warmup; all four hardware counters have
  **100% coverage**. Thus the busy target does not establish broad SM use.
  Worker finish gaps are **13.13 s / 0.48 s**, with similar arm finish gaps.
  Initial per-worker compilation takes about **75 s / 131 s**; later tasks
  reuse compilation. Sampled process-tree RSS peaks at **3.91 / 3.87 GiB**,
  with at least **18.30 / 17.99 GiB** host memory available. No memory guard,
  failure artifact or nonempty stderr log is present.
  **80 distinct preflight tests passed** across the initial 78-check run and
  final 16-check pair suite
  ([receipts](/mnt/workspaces/Cells/ip3-tile-pair-development-20261008-01/preflight-checks.json));
  both qualifications and the complete plan passed
  [reference/source verification](/mnt/workspaces/Cells/ip3-tile-pair-development-20261008-01/reference-preflight.json).
  This is one ordered L4 comparison; no general speedup or multi-GPU scaling
  claim is implied. Production defaults remain unchanged. Controller **1956135**
  has exited and the L4 is idle. Width 32 remains the measured candidate for
  this workload; further kernel/CPU optimization is parked under the priority above.
  A [saved-timing review](/mnt/workspaces/Cells/ip3-tile-pair-development-20261008-01/logging-overhead-review-20261008.json)
  finds width-32 callback/status/logging costs **0.070%** of summed worker-task
  wall time, host transfers **1.04%**, final validation/summary **0.89%**, and
  checkpoints **0.95%**. There are **1616 window log lines / 203 KB** per width;
  full GPU tracing was disabled. **90.34%** of width-32 task time is inside
  dispatch/device execution/synchronization, which does not isolate GPU arithmetic.
  Small worlds and the retained sequential solve/reduction wrappers are leading
  explanations for low SM activity; their individual costs and indirect sampler
  overhead still need measurement. This review reads saved evidence only.
  No automatic follow-up job is scheduled.

- **64-world GPU tile qualification passed at 12:34:28 UTC on 8 October**,
  in **802.59 seconds (13 min 23 s)**. The
  [result](/mnt/workspaces/Cells/ip3-width64-20261008-01/result.json),
  [read-only completion check](/mnt/workspaces/Cells/ip3-width64-development-20261008-01/completion-check-20261008.json) and
  [registration](/mnt/workspaces/Cells/ip3-width64-20261008-01/registration.json)
  verify **119 production files, seven frozen helpers and 33 evidence artifacts**.
  The same membrane-sum wrapper and batching code pass at width **64** across
  **65 worlds / 20 ms / 1600 ticks**: one full tile plus one partial tile with
  one real world. All **48 state fields / 42,874,780 trajectory scalars** match
  the authenticated scalar GPU trace bit for bit, with no transient difference.
  Complete disk roundtrip, seven-tick-window restart and **32 + 33** world
  partition replay pass; their retained states and checkpoint provenance were
  checked directly. Recorded per-window comparisons pass for **51 half-run,
  116 resumed and 101 + 101 partition windows**. Fresh scalar CPU endpoints
  exactly reproduce the prior CPU reference. All **26,780 CPU/GPU endpoint
  scalars** pass unchanged **rtol=3e-10 / atol=3e-13**, maximum absolute
  difference **3.886e-16**, with exact integer and boolean states.
  Ordinary stage, domain and conservation checks pass. Sampled process-tree
  RSS peaks at **2.98 GiB**, with **18.87 GiB** host memory available at minimum.
  All stderr logs are empty and no failure artifacts are present.
  **132 preflight tests passed in 22.36 seconds**
  ([report](/mnt/workspaces/Cells/ip3-width64-development-20261008-01/preflight.xml));
  [reference/source verification](/mnt/workspaces/Cells/ip3-width64-development-20261008-01/reference-preflight.json)
  and [static checks](/mnt/workspaces/Cells/ip3-width64-development-20261008-01/preflight-checks.json)
  also pass. Controller **1921087** has exited. The matched benchmark above
  now measures width 64: it retains numerical agreement but has lower throughput
  than width 32 on this workload. Production defaults
  remain unchanged; no general model, CPU-batching or GH200 scaling claim is made.

- **Qualified candidate throughput/SM benchmark completed at 11:32:25 UTC on
  8 October**, with a **284.08-second measured campaign (4 min 44 s)**. The
  [result](/mnt/workspaces/Cells/ip3-parallel-sm-20261008-01/result.json),
  [completion check](/mnt/workspaces/Cells/ip3-parallel-sm-development-20261008-01/completion-check-20261008.json) and
  [registration](/mnt/workspaces/Cells/ip3-parallel-sm-20261008-01/profile-registration.json)
  verify all **128 worlds / six tasks / 20 ms**: **52,736 saved state scalars**
  match the scalar baseline bit for bit, with authenticated candidate checkpoint
  and task provenance. All **119 production files, five candidate helpers and
  18 evidence artifacts** pass the read-only completion check. Against the earlier
  [scalar counter run](/mnt/workspaces/Cells/ip3-calcium-sm-20261003-01/result.json),
  with matching device, DCGM installation, fields and sampling period, measured
  time falls from **792.18 to 284.08 seconds** and throughput rises from
  **581.69 to 1,622.07 worlds per allocated L4 GPU-hour**, an observed **2.79×**
  improvement in this single paired-workload comparison. Actual SM activity is
  **0.784% whole-job / 1.331% after warm-up**, versus **0.720% / 0.822%**;
  warm occupancy rises from **0.0210% to 0.0551%**. All four hardware counters
  have **100% valid coverage**. GPU busy time is **48.33% whole-job / 84.34%
  after warm-up**; the whole-job advisory 70% target is not met. Initial
  compilation takes about **118 seconds per worker**, and both workers are warm
  **122.65 seconds** into the shorter campaign. Compilation is now a large share
  of total time. Worker and arm finish gaps are both **2.00 seconds**. Sampled
  process-tree RSS peaks at **4.08 GiB**, with **18.91 GiB** host memory available
  at minimum; no memory guard, failure artifact or stderr error occurred.
  Two persistent workers on cores **4 and 5** reused the 32-world candidate
  across tasks through the ordinary queue, callbacks, checks and checkpoint codec.
  **56 preflight tests passed in 2.66 seconds**
  ([report](/mnt/workspaces/Cells/ip3-parallel-sm-development-20261008-01/preflight.xml));
  [reference/source verification](/mnt/workspaces/Cells/ip3-parallel-sm-development-20261008-01/reference-preflight.json)
  and static checks passed. The initial direct-script invocation failed before
  computation because of an import path; its
  [failure receipt](/mnt/workspaces/Cells/ip3-parallel-sm-development-20261008-01/launch-preflight-failure.json)
  is retained, and module invocation completed successfully. Timing includes
  counter/observer overhead; trajectory qualification remains bounded to
  65 worlds, with additional endpoint checks here. Production defaults remain
  unchanged, and this does not establish GH200 or multi-GPU scaling. Controller
  **1902123** has exited. Wider parallel-batch qualification passed above;
  longer workloads remain the next performance measurement to spread compilation
  cost and assess actual SM activity.

- **Complete membrane-energy-sum GPU qualification passed at 21:05:19 UTC on
  7 October**, in **719.07 seconds (11 min 59 s)**. The
  [result](/mnt/workspaces/Cells/ip3-energy-screen-20261007-01/result.json) and
  [read-only completion check](/mnt/workspaces/Cells/ip3-energy-screen-development-20261007-01/completion-check-20261008.json)
  verify **119 unchanged production files, seven helpers and 33 evidence artifacts**.
  The [registration](/mnt/workspaces/Cells/ip3-energy-screen-20261007-01/registration.json)
  binds the exact membrane-sum wrapper that passed the saved-step diagnostic.
  All **65 worlds, 20 ms / 1600 ticks**, covering two full 32-world tiles and a
  partial tile, match the authenticated scalar GPU trajectory bit for bit:
  **48 fields / 42,874,780 state scalars**, including all energy ledgers, with
  no transient differences. The complete trace and saved endpoints were compared
  directly at review. Complete disk roundtrip, seven-tick-window restart and
  partitions **32 + 33** are exact; recorded comparisons pass at all **51 half-run,
  116 resumed and 101 + 101 partition output windows**. Checkpoint provenance
  verifies both the batching implementation and energy-wrapper hashes.
  Fresh scalar CPU execution exactly reproduces all 65 prior reference endpoints.
  CPU/GPU agreement passes for **26,780 scalars**, maximum absolute difference
  **3.886e-16**, under unchanged **rtol=3e-10 / atol=3e-13** with exact integer
  and boolean states. Stage/domain/conservation checks pass; maximum reported
  energy residual is **1.775e-13 pJ**. **116 preflight tests passed in 16.83 seconds**
  ([report](/mnt/workspaces/Cells/ip3-energy-screen-development-20261007-01/preflight.xml));
  static checks and the [reference preflight](/mnt/workspaces/Cells/ip3-energy-screen-development-20261007-01/reference-preflight.json)
  also pass. Both phases completed within their budgets with empty stderr and no
  failure artifacts. Sampled process-tree RSS peaked at **2.96 GiB**, with at least
  **19.13 GiB** host memory available. Full GPU compilation/execution took
  **51.77 / 159.42 seconds** in this instrumented qualification; representative
  throughput and actual SM utilization remain unmeasured for this candidate.
  Controller **1639742** has exited. The candidate is eligible for the separately
  registered throughput/SM measurement above. Scalar CPU
  execution and production defaults remain unchanged; this does not establish
  general model or GH200 qualification.

- **GPU energy-rounding diagnostic completed at 17:18:25 UTC on 7 October**,
  in **542.92 seconds (9 min 3 s)**. The
  [result](/mnt/workspaces/Cells/ip3-energy-20261007-01/result.json) and
  [read-only completion check](/mnt/workspaces/Cells/ip3-energy-development-20261007-01/completion-check-20261007.json)
  verify **119 unchanged production files, seven helpers and 440 evidence artifacts**.
  Direct comparisons cover **105 saved-step cases / 2,811,900 complete after-state
  scalars**, with every saved input checked against its authenticated trace.
  All **65 worlds** remain present at **15 selected ticks: 1, 5, 6, 8, 15, 20,
  49, 59, 73, 80, 197, 265, 1288, 1289 and 1600**. These cover each affected
  world's first difference, the maximum-ULP case, recovery and endpoint.
  Scalar and original batched paths reproduce their own saved states exactly.
  Starting from identical scalar inputs, the original candidate exposes energy
  differences at **nine selected ticks**. **All four experimental protections
  pass all 15 complete-state comparisons bit for bit**: the membrane energy sum,
  full leak/pump energy rate, combined membrane energy rate and complete guarded
  RK4 operation. The **narrowest successful change is the membrane energy sum**
  (`parallel_scalar_membrane_sum`), retaining the existing scalar-field solve/sums
  protections and original equations. This establishes saved-step agreement,
  without proving a unique compiler cause or complete-trajectory acceptance.
  Domain and conservation checks pass; maximum reported energy residual is
  **1.769e-13 pJ**. Before/after states and all 12 compiler-text files are retained.
  **106 preflight tests passed in 15.68 seconds**
  ([report](/mnt/workspaces/Cells/ip3-energy-development-20261007-01/preflight-02.xml));
  the [reference preflight](/mnt/workspaces/Cells/ip3-energy-development-20261007-01/reference-preflight.json)
  also passes. The job finished within its budgets with empty stderr; sampled
  process-tree RSS peaked at **2.69 GiB**, with at least **19.86 GiB** host memory
  available. Controller **1569916** has exited and L4 is idle. Next: complete
  65-world trajectory, disk restart, changed-window and partition qualification
  with the narrow membrane-sum protection, then throughput/SM measurement if it
  passes. Production defaults are unchanged; no follow-up job was launched.

- **Larger GPU qualification completed at 10:30:52 UTC on 7 October, but was
  rejected for transient exact-reference differences**, in **1691.38 seconds
  (28 min 11 s)**. The [result](/mnt/workspaces/Cells/ip3-larger-20261007-01/result.json)
  and [read-only completion check](/mnt/workspaces/Cells/ip3-larger-development-20261007-01/completion-check-20261007.json)
  verify **119 unchanged production files, seven helpers and 41 evidence artifacts**.
  The [registration](/mnt/workspaces/Cells/ip3-larger-20261007-01/registration.json)
  binds the passed three-world screen and qualified scalar checkpoints for
  **65 worlds (IDs 0–64), 20 ms / 1600 ticks**, with two full 32-world GPU tiles
  and a partial tile. Direct comparison of all **42,874,780 trajectory scalars**
  found **1622 differing values**, solely in `ionic_dissipated_energy_pJ`:
  **one to two ULPs**, maximum absolute difference **8.674e-19 pJ**, affecting
  **nine worlds / 1276 tick states**. The first difference is at **tick 6
  (75 microseconds), world 12**; the last is at **tick 1288 (16.1 ms)**.
  All other state fields agree bit for bit throughout. Every final state agrees
  exactly, including complete disk roundtrip, seven-tick-window restart and
  partitions **32 + 33**. Half/restart/partition output-window comparisons also
  retain transient differences in the same energy field. These reject strict
  trajectory parity despite endpoint agreement; tolerances were not relaxed.
  Fresh scalar GPU endpoints reproduce the qualified campaign exactly, and the
  CPU reference reproduces the prior three-world subset. CPU/GPU agreement passes
  for all **26,780 endpoint scalars**, maximum absolute difference **3.886e-16**
  under unchanged **rtol=3e-10 / atol=3e-13**, with exact integer/boolean states.
  Ordinary domain/accounting checks pass; maximum reported energy residual is
  **1.775e-13 pJ**. **90 preflight tests passed in 13.45 seconds**
  ([report](/mnt/workspaces/Cells/ip3-larger-development-20261007-01/preflight-02.xml));
  the initial fixture failures and [reference preflight](/mnt/workspaces/Cells/ip3-larger-development-20261007-01/reference-preflight.json)
  remain preserved. Both phases finished within their registered budgets, with
  empty stderr and no execution failure artifacts. Sampled process-tree RSS
  peaked at **3.16 GiB**, with at least **18.61 GiB** host memory available.
  Controller **1441950** has exited and L4 is idle. Instrumented scalar/candidate
  GPU execution took **498.54 / 210.30 seconds**; the rejected candidate has no
  qualified throughput or SM-utilization result. Next: isolate the energy-ledger
  rounding using the saved states, then repeat the strict qualification after a
  supported fix. Production defaults are unchanged; no follow-up job was launched.

- **Complete GPU solve-plus-sums screen passed at 19:32:40 UTC on 5 October**,
  in **365.80 seconds (6 min 6 s)**. The
  [result](/mnt/workspaces/Cells/ip3-gpu-screen-20261005-01/result.json) and
  [completion check](/mnt/workspaces/Cells/ip3-gpu-screen-development-20261005-01/completion-check-20261006.json)
  verify **119 unchanged production files, seven helpers and 30 evidence artifacts**.
  The [registration](/mnt/workspaces/Cells/ip3-gpu-screen-20261005-01/registration.json)
  binds the completed GPU witness checks, identical physical inputs and unchanged
  candidate code.
  Execution roles are explicit: **scalar CPU reference / 32-lane GPU candidate**.
  The fresh CPU endpoint exactly reproduces its authenticated reference.
  The three-world **20-ms / 1600-tick GPU trajectory** saved all 1601 complete
  states: **1,978,836 state scalars match the scalar GPU trace bit for bit**, with
  no transient differences. Complete disk roundtrip, seven-tick-window restart
  and partitions of one and two worlds are exact. Recorded comparisons also
  pass at all **51 half-run, 116 resumed and 101 + 101 partition windows**;
  the retained full trace and replay endpoints were compared directly at review.
  Scalar CPU/GPU agreement passes for all **1236 endpoint scalars**, with maximum
  absolute difference **3.331e-16** under unchanged **rtol=3e-10 / atol=3e-13**
  limits and exact integer/boolean states. Ordinary stage/accounting checks pass;
  maximum reported energy residual is **1.486e-13 pJ**.
  **76 focused tests passed in 9.83 seconds**
  ([report](/mnt/workspaces/Cells/ip3-gpu-screen-development-20261005-01/preflight.xml));
  [reference preflight](/mnt/workspaces/Cells/ip3-gpu-screen-development-20261005-01/reference-preflight.json)
  authenticated both complete traces, their initial states and physical tick grids.
  Static checks pass. Both phases completed within **1200-second run budgets /
  45-minute phase caps**, without failure artifacts or stderr output. Sampled
  process-tree RSS peaked at **2.36 GiB**, with at least **19.97 GiB** host memory
  available. Controller **759323**, CPU child **759326** and L4 child **759607**
  have exited; L4 is idle. Full GPU compilation took **52.03 seconds**, and
  instrumented execution **46.11 seconds**; these timings do not establish
  representative throughput or SM use. The candidate is eligible for larger-batch
  qualification. Acceptance is limited to the registered three-world GPU screen;
  CPU batching and production defaults remain unchanged. No follow-up job was launched.

- **Saved-step operator diagnostic completed at 18:54:03 UTC on 5 October**,
  in **2893.22 seconds (48 min 13 s)**: **39 min 41 s CPU / 8 min 25 s L4**.
  The [result](/mnt/workspaces/Cells/ip3-step-20261005-01/result.json) and
  [completion check](/mnt/workspaces/Cells/ip3-step-development-20261005-01/completion-check-20261005.json)
  verify **119 unchanged production files, seven helpers and 322 evidence
  artifacts**, including **72 saved-step cases / 88,992 endpoint scalars**.
  The [registration](/mnt/workspaces/Cells/ip3-step-20261005-01/registration.json)
  binds the completed rounding trace, identical physical inputs and the unchanged
  baseline candidate. Both devices' reference and original candidate exactly
  reproduce their respective saved steps at ticks **1, 2, 13, 59, 323 and 1600**.
  Experiments advance from identical reference inputs and compare all state bits,
  including the later CPU calcium/chemistry witnesses and final step.
  **L4 dense-solve-plus-field-sums and whole-field protection match all six
  reference steps exactly.** Solve-only and solve-plus-logarithmic-mean protection
  still differ at ticks 1 and 2. CPU has no fully matching strategy: logarithmic-
  mean protection removes its first-step mismatch, and whole-field protection
  removes the field mismatches, but calcium-channel energy (tick 2), ER transfer/
  chemistry (tick 59) and reaction energy (tick 323) still differ by one to five
  ULPs. All strategies retain the original scientific equations and tolerances.
  Complete before/after arrays, ordinary stage/accounting reports and lowered/
  optimized compiler text are saved. Compiler capture leaves function outputs
  unchanged; JIT caches were cleared between strategies. Ordinary checks completed,
  with maximum reported energy residual **1.486e-13 pJ** across saved endpoints.
  **67 focused tests passed in 20.06 seconds**, followed by **14 passes in
  2.22 seconds** after tightening witness validation
  ([reports](/mnt/workspaces/Cells/ip3-step-development-20261005-01/static-checks.json)).
  Full-model [lowering preflight](/mnt/workspaces/Cells/ip3-step-development-20261005-01/lowering-preflight.json)
  passed at tile widths **4 CPU / 32 L4**. The existing detached runner retains
  **1200-second run budgets, 45-minute phase caps**, resource monitoring and
  durable failures. Sampled process-tree RSS peaked at **10.23 GiB**, with at least
  **11.12 GiB** host memory available. Controller **732990**, CPU child **732992**
  and L4 child **744716** have exited; L4 is idle. CPU stderr contains slow-
  compilation warnings; GPU/controller stderr are empty and no failure artifact
  is present. Selected-step agreement cannot establish full-trajectory parity,
  the precise compiler cause or improved throughput/SM use. Next screen the
  complete 20-ms GPU solve-plus-sums trajectory, restart and partition replay
  against the verified scalar CPU/GPU paths. CPU batching remains unqualified;
  the verified scalar CPU path remains available. Production defaults are
  unchanged and no follow-up job was launched.

- **CPU/L4 rounding diagnostic completed at 13:05:11 UTC on 5 October**,
  in **610.59 seconds (10 min 11 s)**. The
  [result](/mnt/workspaces/Cells/ip3-rounding-20261005-01/result.json) and
  [completion check](/mnt/workspaces/Cells/ip3-rounding-development-20261005-01/completion-check-20261005.json)
  verify **119 unchanged production files, six helpers and 48 evidence artifacts**.
  The [registration](/mnt/workspaces/Cells/ip3-rounding-20261005-01/registration.json)
  binds the preceding screen, identical candidate code and physical inputs,
  **four CPU lanes / 32 L4 lanes**, **1200-second run budgets**, and **45-minute
  phase caps**. Only the observation window changed to one physical tick.
  Both original and candidate paths saved all **1601 complete states** for the
  same three worlds; all four endpoints exactly reproduce their respective
  preceding screen endpoints. Saved before/after states, first differences and
  isolated probe comparisons were checked directly against the arrays.
  **First divergence is tick 1 (12.5 microseconds) on both devices:** CPU changes
  six face-energy values by up to two ULPs; L4 changes 15 outside-amount,
  face-transfer and face-energy values by one ULP. The CPU trace also reveals
  transient calcium-channel, ER-transfer and reaction-ledger differences that
  endpoint-only comparison missed. All **189 standalone field values** match
  before and after tick 1 on both devices. Full rate-equation probes differ in
  energy fields on L4 and calcium-channel fields on CPU after tick 1.
  This localizes the first differing step; it does not establish which arithmetic
  operation or compiler transformation causes it. Next use the saved first-step
  case to identify and test a narrow correction before full qualification.
  Ordinary stage/accounting checks completed; the largest reported energy
  residual across the four endpoints was **1.486e-13 pJ**. Scientific inputs
  and tolerances remain unchanged.
  **53 focused checks passed in 11.80 seconds**
  ([report](/mnt/workspaces/Cells/ip3-rounding-development-20261005-01/preflight-02.xml)).
  The initial-state L4 [preflight probe](/mnt/workspaces/Cells/ip3-rounding-development-20261005-01/probe-02/probe-receipt.json)
  and static checks passed. The first probe's receipt-name collision remains in its
  [failure artifact](/mnt/workspaces/Cells/ip3-rounding-development-20261005-01/probe-preflight-failure.json);
  the corrected preflight used a separate receipt filename. Sampled process-tree
  RSS peaked at **10.30 GiB**, with at least **12.27 GiB** host memory available.
  Controller **604953**, CPU child **604959** and L4 child **609085** have exited;
  L4 was idle at review. CPU stderr contains a slow-compilation warning; GPU and
  controller stderr are empty. The diagnostic reproduced the rejected candidate;
  it does not qualify it or measure throughput/SM improvement. Production defaults
  are unchanged and no follow-up job was launched.

- **Narrower parallel-field screening completed at 21:49:05 UTC on 4 October**,
  in **2358.88 seconds (39 min 19 s)**. The
  [result](/mnt/workspaces/Cells/ip3-parallel-20261004-02/result.json) and
  [read-only completion check](/mnt/workspaces/Cells/ip3-parallel-development-20261004-02/completion-check-20261005.json)
  verify **119 unchanged production files**, five frozen helpers and **36 evidence
  artifacts**. Both devices completed the full, half, restart and partition runs
  within the registered wall budgets. Full-state disk roundtrip, seven-tick-window
  restart and partitions of one and two worlds were bitwise exact on both devices.
  CPU/L4 agreement passed for all **1236 scalars**, with maximum absolute difference
  **3.331e-16**, using the unchanged **rtol=3e-10 / atol=3e-13** limits and exact
  integer/boolean states. Stage/accounting checks passed; maximum energy residual
  across both devices and all saved endpoints was **1.476e-13 pJ**.
  **The candidate is rejected under the exact scalar-reference requirement:**
  CPU differs in four chemical-amount/face-energy values by one ULP; L4 differs
  in 16 outside-amount/face-transfer/face-energy values by up to three ULPs.
  Restart and partition reproducibility are intact, but the complete trajectories
  do not reproduce the original reference bits. No tolerance was relaxed.
  The [registration](/mnt/workspaces/Cells/ip3-parallel-20261004-02/registration.json)
  selects `parallel_scalar_linear`: only the dense field solve retains scalar
  batching, while the remaining original field algebra can run across worlds.
  A short L4 [field probe](/mnt/workspaces/Cells/ip3-parallel-development-20261004-02/field-preflight.json)
  matched all **630 field values at ten sampled inputs** bit for bit. Ordinary
  batching reproduced field differences; protecting the linear solve alone, or
  the solve plus sums, removed those differences in this limited probe. The
  smaller change was selected for full-trajectory screening. The subsequent
  full-trajectory mismatch shows the limit of that standalone probe; it does not
  qualify integrated trajectories or establish a speedup.
  **42 focused tests passed in 16.96 seconds**
  ([report](/mnt/workspaces/Cells/ip3-parallel-development-20261004-02/preflight.xml));
  full-model [lowering checks](/mnt/workspaces/Cells/ip3-parallel-development-20261004-02/lowering-preflight.json)
  passed at both tile widths. Static checks pass. The
  [startup check](/mnt/workspaces/Cells/ip3-parallel-development-20261004-02/launch-check.json)
  authenticated **119 unchanged production files**, five frozen helpers and
  the unchanged three-world, 20-ms physical definition. Only its per-run resource
  allowance changes from **600 to 1200 seconds**. Fixed tile widths are **4 CPU /
  32 L4**; smaller CPU padding addresses the preceding expensive CPU runs.
  Exact scalar agreement, complete disk restart with seven-tick windows,
  partitions of one and two worlds, stage/accounting checks and the existing
  CPU/L4 tolerances remain required. Each sequential phase has a **45-minute cap**.
  Full-run diagnostic execution took **18.66 seconds CPU / 42.38 seconds L4**,
  with compilation taking **554.78 / 92.31 seconds**, respectively. L4 execution
  was **102.24 seconds** in the previous whole-field-protected experiment.
  This small padded three-world comparison is not a representative throughput
  measurement, and exact-reference acceptance failed; no SM counters were collected.
  Sampled process-tree RSS peaked at **12.58 GiB**, with at least **7.73 GiB**
  host memory available. Prelaunch memory requires **14 GiB plus 4 GiB reserve**;
  resource sampling is not an enforced RSS cap. Controller **325957**, CPU child
  **325959** and L4 child **335071** have exited; the L4 was idle at review.
  CPU stderr contains the compiler's slow-compilation warning; GPU and controller
  stderr are empty. All evidence and production defaults remain unchanged.
  No follow-up job was launched. Next work should isolate the rounding changes
  within the full integration path before another full qualification run.

- **Parallel-world candidate screening completed at 18:12:07 UTC on 4 October**,
  in **2290.72 seconds (38 min 11 s)**. The
  [result](/mnt/workspaces/Cells/ip3-parallel-20261004-01/result.json) and
  [read-only completion check](/mnt/workspaces/Cells/ip3-parallel-development-20261004-01/completion-check-20261004.json)
  verify **119 unchanged production files**, five frozen validation helpers and
  **40 evidence artifacts**. Neither candidate passed the complete CPU/L4 screen.
  The [registration](/mnt/workspaces/Cells/ip3-parallel-20261004-01/registration.json)
  binds the completed two-worker IP3 campaign and **three worlds with IDs 3–5
  over 20 ms**.
  Two experimental variants process fixed **32-world tiles**: ordinary batching,
  and batching with scalar extracellular-field evaluation to address the earlier
  one-ULP energy-ledger mismatch. Complete duplicate padding worlds are discarded.
  Production defaults, physical inputs, timesteps and tolerances are unchanged.
  **The scalar-field candidate passed every L4 exact check:** all **1236 state
  scalars** matched the saved qualified reference, ordinary disk checkpoint
  roundtrip, restart with seven-tick windows, and partitions of one and two worlds.
  Ordinary stage/accounting checks passed; maximum energy residual was
  **1.486e-13 pJ**. These saved comparisons were independently recomputed.
  **Ordinary batching was rejected:** 13 scalars in extracellular amounts,
  face transfer and face energy differed from the reference by **one or two
  ULPs**. Its restart and partition checks passed, but exact scalar parity did not.
  **Both CPU candidates hit the inherited 600-second per-run limit** after
  reaching **512 / 880 of 1600 ticks**, respectively. Preserved partial states
  contain no assembly or ionic fault flags. The unchanged CPU reference completed
  all ticks and accounting checks in **62.33 seconds**. Missing candidate CPU
  endpoints prevent the registered CPU/L4 comparison; GPU success does not
  substitute for that missing evidence.
  Diagnostic full-run L4 execution took **4.71 seconds** for ordinary batching
  and **102.24 seconds** with scalar field evaluation, excluding compilation
  (**86.33 / 102.24 seconds**, respectively). These three-world runs pad to
  32 lanes; they are not a representative throughput or SM-utilization benchmark.
  The field calculation's execution cost and CPU validation budget need resolving
  before broader qualification and performance measurement.
  **18 focused tests passed in 11.43 seconds**
  ([report](/mnt/workspaces/Cells/ip3-parallel-development-20261004-01/preflight.xml));
  both actual IP3 candidates also passed a
  [lowering preflight](/mnt/workspaces/Cells/ip3-parallel-development-20261004-01/lowering-preflight.json)
  without numerical integration. Static checks pass. The
  [startup check](/mnt/workspaces/Cells/ip3-parallel-development-20261004-01/launch-check.json)
  verified frozen hashes, controller **259809**, CPU child **259835**, affinity
  **4–5**, and the scalar-reference phase. Both sequential phases finished within
  their **45-minute** caps. Sampled process-tree RSS peaked at **10.30 GiB**,
  with at least **9.21 GiB** host memory available; prelaunch allowances were not
  an enforced RSS limit. Controller and children have exited and the L4 was idle
  at review. Logs, CPU failures, partial states and all result artifacts remain
  preserved. No follow-up job was launched.

- **IP3/assembly L4 hardware-counter replay completed at 23:47:28 UTC on 3 October**,
  in **792.18 seconds (13 min 12 s)**. The
  [result](/mnt/workspaces/Cells/ip3-calcium-sm-20261003-01/result.json),
  [counter summary](/mnt/workspaces/Cells/ip3-calcium-sm-20261003-01/gpu-counter-summary.json)
  and [read-only completion check](/mnt/workspaces/Cells/ip3-calcium-sm-development-20261003-01/completion-check-20261004.json)
  verify all **128 worlds / six tasks / 204,800 world steps**, with no missing
  or failed task or abnormal exit. Every saved field, shape, dtype and raw bit
  matches the preceding two-worker campaign: **52,736 state scalars** in total.
  All **119 production files**, observer/runtime hashes, **18 evidence artifacts**,
  arm aggregates and telemetry verify. Maximum energy residual remains
  **1.774e-13 pJ**, below the unchanged **1e-9-pJ** limit.
  Actual **SM-active was 0.7198% whole-job / 0.8219% after warm-up**;
  **SM occupancy was 0.01954% / 0.02100%**, and **DRAM activity 0.08461% /
  0.09432%**. The **792 counter samples** all have valid status; coverage is
  **100%** in both intervals. Ratio-to-percent conversion and time weighting
  were independently recomputed from raw values. GPU busy time was much higher:
  **76.35% whole-job / 87.49% after warm-up**, consistent with DCGM engine activity
  at **76.30% / 87.40%**. The **70% busy-time gate passes; SM utilization is low**.
  These counters, the earlier tiny-kernel traces and the scalar-world `lax.map`
  path support investigating parallel world execution, with fixed reduction
  order and all numerical/replay guarantees retained. They do not isolate every
  bottleneck or establish an achievable speedup.
  Workers finished **1.01 seconds apart**. Sampled process-tree RSS peaked at
  **3.85 GiB**, with at least **16.75 GiB host memory available**; the guard never
  triggered. Throughput was **581.69 worlds/L4 GPU-hour**. Elapsed time was
  **11.44% greater** than the uninstrumented two-worker run; this single comparison
  includes measurement overhead and run variation, not a controlled overhead estimate.
  Controller **4140715**, workers **4140740 / 4140742**, and the counter sampler
  have exited. Both stderr logs are empty and the L4 was idle at review.
  The
  [registration](/mnt/workspaces/Cells/ip3-calcium-sm-20261003-01/profile-registration.json)
  reuses the existing two-worker preparation and compares against the completed
  two-worker campaign. All **128 worlds / six tasks / 204,800 world steps**,
  **119 production files**, numerical checks and full checkpoints are unchanged.
  The [launch check](/mnt/workspaces/Cells/ip3-calcium-sm-development-20261003-01/launch-check.json)
  verifies frozen source, observer/runtime hashes, both workers and valid counters.
  DCGM **4.7.0** was extracted under `/mnt/workspaces/Cells/tools`, with package
  checksums and an [installation receipt](/mnt/workspaces/Cells/tools/dcgm-4.7.0/installation.json).
  Only the isolated sampler uses profiling privileges; no system service or
  driver change was required. It records **SM-active (1002), SM occupancy (1003),
  graphics-engine activity (1001) and DRAM activity (1005)** at one-second
  intervals, using a supported set without multiplexing. Device-level activity
  and occupancy include stalled warps; they are not arithmetic efficiency.
  Raw timestamps/statuses are preserved. Completion requires **98% valid
  coverage** for both whole-job and post-warm-up summaries and bitwise checkpoint
  agreement. Missing or invalid counters are not interpreted as zero activity.
  **40 observer/reporting checks passed in 1.46 seconds**
  ([report](/mnt/workspaces/Cells/ip3-calcium-sm-development-20261003-01/preflight-03.xml));
  lint passed. A brief synthetic GPU load demonstrated responsive hardware
  counters with complete coverage. Its initial metadata-parser failure was fixed;
  the [saved-data check](/mnt/workspaces/Cells/ip3-calcium-sm-development-20261003-01/live-preflight-review.json)
  passes, and the original failure is retained. These preflight readings are
  not Cells performance results. The run retained the ordinary **16-GiB
  process-tree / 4-GiB host-reserve guard**, **1800-second campaign cap** and
  independent **1980-second sampler cap**. The sampler shut down normally.
  DCGM logged absent optional NVSwitch discovery support; the requested GPU
  profiling module initialized successfully and every recorded counter status
  is valid. [Run outputs](/mnt/workspaces/Cells/ip3-calcium-sm-20261003-01)
  retain all logs and artifacts. No new simulation, follow-up profiling run
  or Jupiter submission was launched during this completion review.

- **IP3/assembly two-worker L4 comparison completed at 22:13:34 UTC on 3 October**,
  in **710.86 seconds (11 min 51 s)**. The
  [result](/mnt/workspaces/Cells/ip3-calcium-two-worker-20261003-01/result.json) and
  [completion artifact](/mnt/workspaces/Cells/ip3-calcium-two-worker-20261003-01/completion.json)
  record all **128 worlds / six tasks / 204,800 world steps** completed, with no
  failed tasks or abnormal worker exit. The
  [read-only completion check](/mnt/workspaces/Cells/ip3-calcium-two-worker-development-20261003-01/completion-check-20261003.json)
  authenticates **119 unchanged production files**, the frozen observer,
  registrations, 14 observer artifacts and full checkpoints. All **52,736 saved
  state scalars**, including shapes, dtypes and raw bits, match the single-worker
  baseline exactly; arm aggregates and telemetry recompute exactly. Scientific
  checks pass, with zero assembly material residual and maximum ionic energy
  residual **1.774e-13 pJ**, below the unchanged **1e-9-pJ** limit.
  GPU busy time was **83.94% whole-job / 90.95% after both workers warmed**,
  with **99.80% / 100%** telemetry coverage. This meets the advisory **70% GPU
  busy-time target**, but **SM-active utilization and achieved occupancy were
  not captured**. The earlier traces provide theoretical occupancy and kernel
  events, not measured SM activity; their many small kernels do not establish
  hardware saturation. The completed replay above now measures low SM activity.
  Throughput was **648.23 worlds/L4 GPU-hour**, compared with **483.05** for the
  same worlds on one worker: **34.19% greater throughput / 25.48% less wall time
  and allocated GPU time**, using **0.19746 L4 GPU-hours**. Worker and arm finish
  gaps were **0.877 / 0.873 seconds**. This single local comparison includes cold
  compilation and observation costs; it does not establish GH200 scaling.
  Worker peak RSS was **1.607 GiB each**; sampled combined process-tree RSS
  peaked at **3.43 GiB**, with at least **17.00 GiB host memory available**.
  There were **687 resource samples**, maximum gap **1.19 seconds**. The guard
  never triggered. Controller **4109378** and workers **4109389 / 4109391** have
  exited; stdout/stderr are empty and the L4 was idle at review.
  The
  [preparation](/mnt/workspaces/Cells/ip3-calcium-two-worker-preparation-20261003-01/preparation.json)
  authenticates the completed qualification and the preceding memory diagnostic.
  Its memory allowance is **8 GiB per worker**: the larger measured peak,
  **5.79 GiB**, plus 25%, rounded up to the next GiB. With the unchanged
  **4-GiB reserve**, **20 GiB** is required; **24.42 GiB** was available at launch.
  Defaults remain conservative unless matching completed memory evidence is
  explicitly supplied. The
  [registration](/mnt/workspaces/Cells/ip3-calcium-two-worker-20261003-01/profile-registration.json)
  and [launch check](/mnt/workspaces/Cells/ip3-calcium-two-worker-development-20261003-01/launch-check.json)
  bind **119 unchanged production files**, the frozen observer, and the
  same worlds and tasks as the original single-worker profile. Physics,
  timestep, per-cell streams, task definitions and ordering
  are unchanged; the execution resources are two workers with one CPU core
  each and an **1800-second / 0.5 L4 GPU-hour campaign cap**. Fresh caches
  retain compilation costs in allocation-wide timing.
  The existing observer driver now supports this comparison without GPU traces.
  It records per-window counters, CPU/RSS samples, throughput, utilization,
  worker/arm finish gaps, and exact checkpoint comparison against the original
  untraced single-worker run. Its memory guard requests the ordinary controller's
  checkpoint pause if combined process-tree RSS exceeds **16 GiB**, available
  host memory falls below **4 GiB**, or sampling fails. This is a sampled
  cooperative guard, not an instantaneous RSS cap; existing bounded pause and
  failure handling is retained.
  **79 preparation, observer and scheduler checks passed in 23.14 seconds**
  ([test report](/mnt/workspaces/Cells/ip3-calcium-two-worker-development-20261003-01/preflight.xml));
  lint passed. Results and logs remain in
  [the run directory](/mnt/workspaces/Cells/ip3-calcium-two-worker-20261003-01).
  No new simulation, follow-up profiling run or Jupiter submission was launched
  during this completion review.

- **IP3/assembly L4 diagnostic replay completed at 21:19:32 UTC on 2 October**,
  in **1056.82 seconds (17 min 37 s)** of campaign time. The
  [result](/mnt/workspaces/Cells/ip3-calcium-profile-20261002-01/result.json) and
  [completion artifact](/mnt/workspaces/Cells/ip3-calcium-profile-20261002-01/completion.json)
  record all **128 worlds / six tasks** completed, with no failed tasks or
  abnormal worker exit. The
  [read-only completion review](/mnt/workspaces/Cells/ip3-calcium-profile-development-20261002-01/completion-check-20261003.json)
  verifies the frozen sources, 18 observer artifacts and campaign checkpoints;
  all **52,736 saved state scalars**, including their shapes, dtypes and raw
  bits, match the preceding run exactly. Controller **3647315** and worker
  **3647322** have exited; stdout/stderr are empty and the L4 is idle.
  Worker peak RSS was **5.69 GiB**, versus the conservative 16-GiB allowance.
  The sampled process-tree peak was **5.79 GiB**; at least **15.74 GiB** of
  host memory remained available. There are **1038 resource samples**, with
  a maximum gap of **1.10 seconds**. Peaks include profiler overhead; sampled
  process-tree RSS can miss short-lived children and is not a two-worker bound.
  The two traces contain **471,176 / 930,168 GPU operations** at batch sizes
  **16 / 32**, respectively, across two integration windows each. Counts include
  compute and copies; median device-event duration is **1.216 microseconds**.
  Frequent command-buffer executions and device/host copies, together with
  approximately one busy CPU core during untraced completed-window intervals,
  are consistent with dispatch/control overhead. They do not establish a sole
  bottleneck or measure uninstrumented idle time. GPU busy time was
  **40.39% whole-job / 43.65% after initial warm-up**, below the advisory target;
  trace export alone took **82.18 seconds**. This instrumented timing is not
  a speedup or regression claim. These observations motivated the completed
  two-worker comparison above, with identical science and adequate memory headroom.
  No new simulation, regression or Jupiter job was launched during this review.
  The [preparation](/mnt/workspaces/Cells/ip3-calcium-profile-preparation-20261002-01/preparation.json)
  reauthenticates the completed qualification. The
  [profile registration](/mnt/workspaces/Cells/ip3-calcium-profile-20261002-01/profile-registration.json)
  and [launch check](/mnt/workspaces/Cells/ip3-calcium-profile-development-20261002-01/launch-check.json)
  bind **119 unchanged production files**, the frozen observer driver and the
  preceding profile's identical **128 worlds / six tasks / 204,800 world steps**.
  The ordinary ensemble runner retains every numerical check and full checkpoint.
  One-second process-tree samples record RSS, CPU time and host memory; worker
  receipts retain lifetime peak RSS. JAX/CUPTI traces capture windows **3–4**
  after two completed windows of the first task at batch sizes **16 and 32**.
  The diagnostic's completion check passed for all checkpoint fields, shapes,
  dtypes and raw bits against the preceding profile. Production equations,
  timestep, seeds, task ordering and resource settings are unchanged.
  **29 focused observer/scheduler checks passed in 0.76 s**
  ([test report](/mnt/workspaces/Cells/ip3-calcium-profile-development-20261002-01/preflight.xml));
  lint passed. A [small tracing preflight](/mnt/workspaces/Cells/ip3-calcium-profile-development-20261002-01/trace-preflight.json)
  captured actual L4 kernel events. Available host memory at launch was
  **24.56 GiB**, against **22 GiB** required: the existing 16-GiB worker
  allowance, 4-GiB reserve and an extra 2 GiB for tracing. These are prelaunch
  allowances, not enforced RSS limits. The campaign used CPU cores **4/5** and
  retained its **3600-second cap**, starting at **21:01:54 UTC**. Instrumentation
  overhead is explicit; this diagnostic did not itself measure concurrent-worker
  memory or throughput.
  Logs and result/failure artifacts remain in
  [the run directory](/mnt/workspaces/Cells/ip3-calcium-profile-20261002-01).
  No automatic polling, subsequent experiment or Jupiter submission is scheduled.

- **IP3/assembly L4 throughput profile completed at 22:53:19 UTC on 1 October**,
  in **953.93 seconds (15 min 54 s)**. The
  [result](/mnt/workspaces/Cells/ip3-calcium-throughput-20261001-01/result.json) and
  [completion artifact](/mnt/workspaces/Cells/ip3-calcium-throughput-20261001-01/completion.json)
  record **128 completed worlds / six tasks / 204,800 world steps**, with no
  missing or failed tasks, no abnormal worker exit and empty stderr.
  Controller **2606081** and worker **2606086** have exited; the L4 is idle.
  The [read-only completion check](/mnt/workspaces/Cells/ip3-calcium-throughput-development-20261001-01/completion-check-20261002.json)
  authenticates the preparation, qualified parent, all **119 frozen production
  files**, task results and complete checkpoints. The existing checkpoint
  loader validates saved state; scientific summaries and arm aggregates
  recompute exactly without advancing simulations. Assembly material residual
  is **zero** and maximum ionic energy residual is **1.774e-13 pJ**, below
  the unchanged **1e-9-pJ** limit.
  Recomputed GPU busy time is **44.82% whole-job / 49.41% after the first
  worker warm-up**, with **99.74% / 100% telemetry coverage**. Both are below
  the advisory **70%** target; numerical qualification remains passed.
  The warm interval includes compilation of the second batch shape.
  Throughput is **483.05 worlds/L4 GPU-hour**, using **0.26498 L4 GPU-hours**.
  Batch arms finished **98.47 seconds apart**. One worker cannot establish
  concurrent-worker balance. Task timings total **156.80 s compilation**,
  **772.23 s execution**, **10.61 s host transfer** and **3.05 s checkpoint
  writing**. Checkpoint writing is a small part of this run; the cause of
  idle time within execution is not yet established.
  The [preparation](/mnt/workspaces/Cells/ip3-calcium-throughput-preparation-20261001-01/preparation.json)
  used 64 independent worlds at each batch size **16 and 32**. The
  **12.5-us timestep, 20-ms horizon, 16-tick windows**,
  physical parameters, cell random streams, complete checkpoints and numerical
  checks are unchanged. Batch arms use disjoint world IDs, so their timings
  are separate cost samples rather than paired speedup estimates.
  The existing preparation now accepts `--family ip3` and an explicit worker
  count; **24 bounded preparation tests passed** in
  [14.03 seconds](/mnt/workspaces/Cells/ip3-calcium-throughput-development-20261001-01/preflight.xml),
  with lint passing. No production solver or scheduler code changed.
  Host memory available at preparation was **22.19 GiB**. The IP3 allowance
  is **16 GiB per worker plus a 4-GiB reserve**, conservatively covering the
  completed qualification's 14.84-GiB peak. One worker fits the **20-GiB**
  prelaunch requirement; two would require **36 GiB**. The single worker uses
  both allocated CPU cores and a **3600-second / one L4 GPU-hour cap**.
  These are prelaunch host allowances, not enforced RSS limits. GPU preallocation
  is off, with a **0.2** allocator fraction. Planned output is **888,930,304 bytes**
  under a 2-GiB limit, plus a 256-MiB cache allowance and 4-GiB disk reserve.
  The [launch command](/mnt/workspaces/Cells/ip3-calcium-throughput-development-20261001-01/launch-command.json),
  [registration](/mnt/workspaces/Cells/ip3-calcium-throughput-20261001-01/registration.json)
  and [launch verification](/mnt/workspaces/Cells/ip3-calcium-throughput-development-20261001-01/launch-check.json)
  preserve the detached launch at **22:37:27 UTC**, task plan and CPU affinity
  **4/5**. Timing samples include compilation and I/O; the batch-32 upper-middle
  cost includes its first compilation, so it does not establish a batch-size
  speedup. Next work is execution profiling and actual per-worker host-memory
  measurement before a bounded concurrency or larger-batch experiment.
  No follow-up simulation, regression or Jupiter submission was launched.

- **IP3/calcium/assembly GPU retry passed at 20:03:34 UTC on 1 October**,
  in **2761.13 seconds (46 min 1 s)**. The
  [result](/mnt/workspaces/Cells/ip3-calcium-20261001-02/result.json) and
  [completion artifact](/mnt/workspaces/Cells/ip3-calcium-20261001-02/completion.json)
  record **311 GPU passes / no skips / no failures**, including all 35 IP3
  checks and the entire previous regression panel. Controller **2437800** and
  the GPU test process have exited; the L4 is idle at **0% / 0 MiB**.
  The retry launched at 19:17:32 UTC. Its
  [registration](/mnt/workspaces/Cells/ip3-calcium-20261001-02/registration.json)
  binds the original frozen simulation, tests, inputs and native sources to
  the [completed CPU phase](/mnt/workspaces/Cells/ip3-calcium-20261001-01/cpu.xml):
  **305 passes / six expected GPU-only deferrals**. Only the qualification
  runner changed. Its CPU-reuse path now covers plasma, CaV and IP3 panels,
  checks each family's exact deferrals and scalar/assembly evidence, and
  supports a separately registered GPU retry wall allowance. The
  [bounded runner preflight](/mnt/workspaces/Cells/ip3-calcium-development-20261001-01/retry/preflight-result.json)
  passed **82 tests** and lint. Parent authentication verified **372 frozen
  source files** and **111 CPU evidence files**. The runner's
  [CPU reuse receipt](/mnt/workspaces/Cells/ip3-calcium-20261001-02/cpu-reuse.json)
  confirms unchanged CPU runtime and a fresh full GPU panel.
  All **311 GPU checks** ran again, with an explicit **14,400-second** retry
  allowance instead of sharing the original three-hour budget with the CPU
  phase. The [scientific protocol](/mnt/workspaces/Cells/ip3-calcium-20261001-02/chemistry-protocol.json)
  remains byte-identical to the parent, including numerical tolerances,
  **16 GiB child RSS**, **1 GiB artifacts/cache** and **4 GiB reserve**.
  A separate copy of **1687 JAX cache files / 267,644,414 bytes**, plus the
  small CUDA cache, reduces repeated compilation without modifying the parent.
  The [completion check](/mnt/workspaces/Cells/ip3-calcium-development-20261001-01/retry/completion-check-20261001-2228.json)
  verifies **372 frozen source files**, **233 completion-bound artifacts**,
  **111 reused CPU evidence files**, both test reports and unchanged parent
  science. Peak child RSS was **14.84 GiB** and artifacts/cache **295.53 MiB**,
  within their registered bounds. The saved
  [IP3 CPU/L4 comparison](/mnt/workspaces/Cells/ip3-calcium-20261001-02/ip3-evidence/gpu/cpu-gpu.json)
  passes across **389,867 scalar values**, with maximum absolute difference
  **3.33e-16**. Independent DOP853/Radau solutions, 25/12.5/6.25-us refinement,
  complete restart and partitions, assembly event references and accounting
  pass. Refinement improves chemical errors by **20.73x** then **35.15x**;
  the largest IP3 assembly energy residual is **1.64e-13 pJ**, below the
  unchanged **1e-9 pJ** tolerance. [GPU logs](/mnt/workspaces/Cells/ip3-calcium-20261001-02/gpu.stdout.log)
  retain the complete run, with empty test and controller stderr.
  The original timeout is preserved. This closes the registered synthetic
  two-cell, 20-ms CPU/L4 qualification, with pinned native IP3-factor
  correspondence; full native BETSE trajectories and biological calibration
  remain separate. The subsequent L4 throughput/utilization profile for the
  expanded IP3/assembly model is recorded above; no Jupiter submission has been made.

- **Finite IP3/calcium/assembly qualification timed out at 05:43:20 UTC on
  1 October**, after **10,802.57 seconds**. The
  [failure artifact](/mnt/workspaces/Cells/ip3-calcium-20261001-01/failure.json)
  records the registered three-hour wall limit during the GPU phase; the
  controller and GPU test process have exited. The new `spatial_calcium@4` model
  reads each cell's finite free cytosolic IP3 at every RK4 stage and applies
  the pinned BETSE IP3 factor to the existing ER release route. A synthetic
  reversible IP3 buffer exercises changing ligand levels while retaining
  material, charge and energy accounting. The ordinary CPU/GPU solver,
  complete checkpoints, assembly connection and independent-world scheduler
  carry the new model. IP3 concentration/release readouts reach observations
  and ensemble summaries. Older model identities retain their behavior.
  The [focused preflight](/mnt/workspaces/Cells/ip3-calcium-development-20261001-01/preflight-result.json)
  records **20 focused CPU passes, two short CPU/reference intervention passes
  and one actual L4 native-factor pass**; lint also passes. Every registered
  refinement grid passed [trace/domain preflight](/mnt/workspaces/Cells/ip3-calcium-development-20261001-01/grids.json):
  the largest estimated trace is **1,372,835,616 bytes**, below the new
  **2 GiB** scalar trace allowance. The
  [registration](/mnt/workspaces/Cells/ip3-calcium-20261001-01/registration.json)
  freezes source, pinned native functions and the
  [protocol](/mnt/workspaces/Cells/ip3-calcium-20261001-01/chemistry-protocol.json).
  It collected **311 checks per phase**: 35 IP3 checks and all 276 earlier
  checks. The [CPU report](/mnt/workspaces/Cells/ip3-calcium-20261001-01/cpu.xml)
  records **305 passes / six expected GPU-comparison deferrals / no failures**
  in **3947.05 seconds (65 min 47 s)**. GPU logs record **160 passes**:
  all 35 IP3, 43 CaV1.2, 44 plasma calcium and 31 spatial calcium checks,
  plus seven selected assembly checks. Timeout occurred while
  `test_one_cell_no_spatial_faces_reduces_to_previous_composition` was running;
  no GPU JUnit or overall completion artifact was produced. No test failure
  was recorded before timeout; neither backend wrote test stderr.
  IP3 full trajectories, DOP853/Radau agreement, refinement, complete restart/
  partitions and assembly event references passed on both devices. The saved
  [IP3 CPU/L4 comparison](/mnt/workspaces/Cells/ip3-calcium-20261001-01/ip3-evidence/gpu/cpu-gpu.json)
  passed across **389,867 scalar values**, with maximum absolute difference
  **3.33e-16**. The maximum IP3 assembly energy residual is **1.64e-13 pJ**,
  below the unchanged **1e-9 pJ** tolerance. Those partial results did not
  close the full GPU regression panel; the successful retry above now does.
  All scientific tolerances remain unchanged. Allowances are **three hours**,
  **16 GiB child RSS**, **1 GiB artifacts/cache** and a **4 GiB reserve**;
  the original 1.5–2 hour estimate was too short. Durable
  [CPU logs](/mnt/workspaces/Cells/ip3-calcium-20261001-01/cpu.stdout.log),
  GPU logs and terminal completion/failure artifacts remain under `/mnt/workspaces`.
  The [18:19 UTC status receipt](/mnt/workspaces/Cells/ip3-calcium-development-20261001-01/status-20261001-1819.json)
  verifies all **372 frozen source files**, the CPU report, GPU pass counts
  and saved IP3 evidence. The L4 was idle at **0% / 0 MiB** at that check.
  The subsequent CPU-evidence reuse and complete GPU retry are recorded above;
  this failed run and all scientific tolerances remain unchanged. The ligand buffer,
  rates and nominal −3 charge are synthetic engineering choices; full native
  BETSE trajectories, biological calibration and calcium/IP3 feedback on
  protein assembly remain outside this claim.

- **Gated calcium/assembly L4 throughput profile completed at 17:52:37 UTC on
  30 September**, in **666.59 seconds (11 min 7 s)**. The
  [result](/mnt/workspaces/Cells/gated-calcium-throughput-20260930-01/result.json)
  records all **128 worlds / six tasks / 204,800 world steps** completed, with
  no failed/missing tasks, abnormal worker exits or stderr. Whole-job GPU busy
  time was **88.38%**, with **99.79% telemetry coverage**; after both workers
  warmed it was **95.96%**, with complete coverage. Both pass the advisory
  **70% target**. Workers finished **2.328 seconds apart** (0.349% of campaign
  wall time); the arms' last tasks finished **2.327 seconds apart**. Allocation
  cost was **0.18516 L4 GPU-hours**, or **691.28 worlds per GPU-hour**. Controller
  **1229799** and workers **1229819 / 1229821** have exited; the L4 is idle.

  The [completion check](/mnt/workspaces/Cells/gated-calcium-throughput-development-20260930-01/completion-check-20260930-1913.json)
  authenticated **116 frozen production files**, the preparation/qualification
  links, all six task results and complete checkpoints. Existing loaders
  verified source/runtime/state identities, clocks, domain and conservation
  without advancing simulations. All saved scientific summaries, arm aggregates
  and telemetry figures recompute exactly. World IDs are complete and disjoint.
  Maximum energy residual was **1.88e-13 pJ**, global ion residual **1.82e-15
  fmol**, and assembly material residuals were zero. No new simulation or
  follow-up job was launched by this status check.

  The [registration](/mnt/workspaces/Cells/gated-calcium-throughput-20260930-01/registration.json)
  contains **64 worlds each** at batch sizes **16 / 32**, with two persistent
  workers pinned to CPUs **4 / 5** and sharing the L4. These are time-weighted
  NVIDIA busy measurements, not SM occupancy or multi-GPU efficiency. The saved
  cost profile includes compilation and I/O and uses the upper middle task
  sample: **9.96 s/world** for batch 16 and **10.83 s/world** for batch 32.
  Samples are unpaired and do not establish a batch-size speedup.

  The [prepared inputs](/mnt/workspaces/Cells/gated-calcium-throughput-preparation-20260930-02/preparation.json)
  retain the qualified **12.5-us timestep, 20-ms horizon, 16-tick windows**,
  observations, controls, calcium-channel state and numerical checks. Batch
  sizes use disjoint stochastic world IDs, so their timings are separate cost
  samples rather than paired speedups. The ordinary shared queue, complete
  checkpoints, telemetry and durable completion/failure artifacts are retained.
  Limits are **30 minutes / 0.5 L4 GPU-hours / 2 GiB artifacts**; conservative
  output sizing is **765.75 MiB**, with **256 MiB cache allowance** and a
  **4-GiB disk reserve**. Prelaunch host sizing allows **10 GiB per worker plus
  4 GiB reserve**; this is a sizing check, not an enforced RSS cap.

  The existing profile preparer now accepts `--family gated`. Its
  [input checks](/mnt/workspaces/Cells/gated-calcium-throughput-development-20260930-01/preparation-check.json)
  verify every task against the frozen parent, preserve all world/cell-stream
  identities, reject the wrong qualification family or timestep, and retain
  the earlier plasma profile mapping. All
  [18 CPU planning checks](/mnt/workspaces/Cells/gated-calcium-throughput-development-20260930-01/preflight.xml)
  pass, including the new model's identity through offline 16-GPU planning.
  Lint, formatting and whitespace checks pass. The
  [launch command](/mnt/workspaces/Cells/gated-calcium-throughput-development-20260930-01/launch-command-02.json)
  retains the earlier parser refusal: `launch` was corrected to the existing
  `run --detach` subcommand before any computation started. No automatic
  polling or follow-up job is scheduled.

- **Gated calcium/assembly retry passed at 05:36:03 UTC on 30 September**,
  after **4472.38 seconds (74 min 32 s)**. The
  [registration](/mnt/workspaces/Cells/gated-calcium-20260930-01/registration.json)
  and [result](/mnt/workspaces/Cells/gated-calcium-20260930-01/result.json)
  record fresh CPU and L4 phases: **271 CPU passes / five GPU deferrals** in
  **25 min 47 s**, then **276 GPU passes / no skips** in **47 min 48 s**.
  All five deferred comparisons passed on the L4. Controller **619480** has
  exited; no failure artifact exists and all stderr logs are empty.

  The [completion check](/mnt/workspaces/Cells/gated-calcium-development-20260930-01/completion-check-20260930-0614.json)
  authenticates **365 frozen source files / 193 completion artifacts**, matches
  all **116 current production files**, verifies collection/execution order and
  preflight binding, and rechecks **1,016,502 saved CPU/L4 scalar values** at
  unchanged tolerances. Maximum absolute difference is **3.89e-16** across the
  combined panel. The new model's refinement error improves **20.74× / 33.66×**
  as the step halves; its scalar/assembly energy residual is at most
  **1.78e-13 pJ**, with exact assembly material accounting. Independent
  trajectories, complete restart and partition replay pass. Peak child RSS was
  **10.60 GiB** within **12 GiB**; artifacts/cache used **232.12 MiB** within
  **1 GiB**. This status check advanced no simulation and launched no follow-up.
  Sustained utilization for `@3`, native full BETSE trajectories, biological
  calibration and actual multi-GPU execution remain unqualified.

  Updating this status file encountered a full root filesystem and truncated
  `PROGRESS.md`. Its full history was recovered from the Git baseline plus
  **82 recorded successful patches**, then restored atomically with this update;
  the [recovery receipt](/mnt/workspaces/Cells/gated-calcium-development-20260930-01/progress-recovery/recovery.json)
  preserves the reconstruction and hashes. Frozen simulation evidence is
  unchanged. Space was subsequently restored and verified before the
  throughput run above.

  The [preparation receipt](/mnt/workspaces/Cells/gated-calcium-development-20260930-01/preparation.json)
  verifies that all **116 production files**, **165 scientific test files**,
  physics, timesteps and tolerances match the failed attempt. The only simulation
  input change is the scalar example's `max_trace_bytes`: **1024 → 1280 MiB**.
  The previous **365 source files / 25 result artifacts** remain unchanged.
  The registered three-hour, 12-GiB RSS and artifact/disk limits are unchanged.

  The existing launcher now checks the default and every registered refinement
  timestep with the ordinary host schedule/domain/budget checks before starting
  a worker. Its [saved preflight](/mnt/workspaces/Cells/gated-calcium-20260930-01/chemistry-preflight.json)
  records **265.28 / 527.61 / 1052.27 MiB** at **25 / 12.5 / 6.25 us**, all within
  the new allowance. Registration and final completion bind this receipt.
  All [24 launcher tests](/mnt/workspaces/Cells/gated-calcium-development-20260930-01/preflight.xml)
  pass, including reproduction of the original finest-grid failure, event-split
  grid sizing, refusal of unsafe timesteps/invalid ladders, unchanged input
  definitions and the existing CPU-reuse guards. Lint, formatting and whitespace
  checks pass. No solver or scientific test was changed for this correction.

- **The first gated calcium/assembly qualification failed at 04:38:44 UTC on
  29 September**, after **246.89 seconds (4 min 7 s)**. Its
  [failure](/mnt/workspaces/Cells/gated-calcium-20260929-01/failure.json) and
  [CPU report](/mnt/workspaces/Cells/gated-calcium-20260929-01/cpu.xml)
  record **35 passes / one failure / no skips**. The timestep-refinement test
  reached the finest **6.25-us / 3200-step** grid, where the conservative trace
  estimate exceeded the configured budget before integration. The controller
  stopped; no GPU phase, final result or completion artifact exists.

  The [30 September status check](/mnt/workspaces/Cells/gated-calcium-development-20260929-01/status-check-20260930.json)
  authenticated all **365 frozen source files**, the registration/protocol and
  saved failure evidence. Host-only sizing gives **265.28 / 527.61 / 1052.27
  MiB** for **25 / 12.5 / 6.25-us** steps, against the **1024-MiB** limit.
  All three grids pass schedule/domain preflight with a proposed **1280-MiB**
  allowance. This is a configured budget rejection, not an observed out-of-memory
  crash. No simulation was advanced and no configuration or frozen evidence was
  changed during the status check. That check identified the need to preflight
  every registered refinement timestep, now addressed by the retry above.

  The saved baseline passed numerical/accounting checks, with maximum energy
  residual **1.77e-13 pJ** and global ion residual **1.63e-15 fmol**. Both
  independent reference comparisons and their mutual agreement ran before the
  budget rejection; full refinement, remaining restart/assembly checks and the
  CPU/L4 panel are unfinished. The proposed change affects only resource sizing;
  equations, steps and numerical tolerances stay fixed. No retry was launched
  during that status check; the subsequently authorized retry is recorded above.

  The attempt launched at **04:34:36 UTC on 29 September**, detached as
  controller **126531**, which has exited. The
  [registration](/mnt/workspaces/Cells/gated-calcium-20260929-01/registration.json)
  and [launch check](/mnt/workspaces/Cells/gated-calcium-development-20260929-01/launch-check.json)
  bind the frozen implementation, examples, native sources and protocol.
  There are **43 new checks plus all 233 prior checks**: expected **271 CPU
  passes / five explicit GPU deferrals**, followed by **276 GPU passes**.
  Those are registered targets, not completed counts. No automatic polling or
  subsequent job is scheduled.

  The new [model and source scope](docs/PLASMA_CALCIUM.md#voltage-gated-calcium-entry-spatial_calcium3)
  uses BETSE's CaV1.2 targets/time constants, including the **−10 mV shift**
  and **m²h** opening. Calcium (+2) flux uses the current finite cytosol/outside
  concentrations and joins the existing shared solver stages, whole-cell charge
  ledger and chemical owners. Gate state, transfer and dissipation are retained
  in complete checkpoints and assembly/ensemble outputs. Availability controls
  merge with plasma and ER boundaries. Assembly still controls potassium
  channels; calcium feedback on protein rates remains open. The old model
  identities and numerical tolerances retain their meanings.

  The [preflight receipt](/mnt/workspaces/Cells/gated-calcium-development-20260929-01/preflight-check.json)
  links **30 passing fast CPU checks**, a separate **two-check timed-intervention/
  planner pass**, and an **actual L4 gate-law pass**. These panels overlap and
  are not a full qualification count. Initial assembly summaries and aggregation,
  16-GPU planning identity, lint, formatting and whitespace checks also pass.
  The first preflight's assembly example used observation times outside its
  required grid; that [failure](/mnt/workspaces/Cells/gated-calcium-development-20260929-01/preflight.xml)
  is preserved. Correcting the example's observation schedule resolved it;
  equations and tolerances were unchanged.

  The [protocol](validation/chemistry/gated_protocol.json) targets errors in
  gate units/signs/powers and calcium/charge/energy ownership. It includes
  independent DOP853/Radau trajectories, **25/12.5/6.25-us** refinement,
  blocked/zero-channel reduction, complete scalar/batch/window/assembly replay,
  independent assembly-event references and saved CPU/L4 comparisons. Energy
  tolerance remains **1e-9 pJ**. Gate correspondence does not establish native
  full trajectories or biological calibration; the native discrete gate updater
  and Cells' continuous RK4 system remain explicitly distinguished.

  The existing runner now accepts `--chemistry-case gated`. Resources are
  **three hours**, **12 GiB child RSS**, **1 GiB artifacts/cache**, a **4-GiB
  free-disk reserve**, and GPU allocator fraction **0.15**. The larger time/RSS
  budget accommodates the new family plus the earlier panel, which took about
  66 minutes across CPU/GPU and approached 8 GiB RSS. All outputs are under
  [/mnt/workspaces/Cells/gated-calcium-20260929-01](/mnt/workspaces/Cells/gated-calcium-20260929-01).

- **Plasma calcium/assembly L4 throughput profile completed at 02:58:50 UTC
  on 29 September**, in **744.25 seconds (12 min 24 s)**. The
  [result](/mnt/workspaces/Cells/plasma-calcium-throughput-20260929-01/result.json)
  records all **128 worlds / six tasks / 204,800 world steps** completed,
  with no failed/missing tasks or abnormal worker exits. Whole-job GPU busy
  time was **77.58%**, with **99.71% telemetry coverage**; after both workers
  warmed it was **88.82%**, with complete coverage. Both pass the advisory
  **70% target**. These are time-weighted NVIDIA busy measurements, not SM
  occupancy. Workers finished **0.141 seconds apart** (0.019% of campaign
  wall time); the two arms' last tasks finished **0.132 seconds apart**.
  Allocation cost was **0.20674 L4 GPU-hours**, or **619.14 worlds per GPU-hour**.
  Controller **84409** and workers **84413 / 84415** have exited; the L4 was
  idle at the **03:05 UTC** status check. No subsequent job was launched.

  The [completion check](/mnt/workspaces/Cells/plasma-calcium-throughput-development-20260929-01/completion-check-20260929-0305.json)
  authenticated all **113 frozen production files**, preparation/qualification
  links, all six task results and complete checkpoints. Existing checkpoint
  loaders verified source/runtime/state identities, clocks, domain and
  conservation without advancing simulations. All saved scientific summaries,
  arm aggregates and utilization figures recompute exactly. World IDs are
  complete and disjoint. Maximum energy residual was **1.93e-13 pJ** and
  global ion residual **2.18e-15 fmol**; assembly material residuals were zero.
  No failure, resource-stop or stderr output is present.

  The [registration](/mnt/workspaces/Cells/plasma-calcium-throughput-20260929-01/registration.json)
  contains **64 worlds each** at batch sizes **16 / 32**, with two persistent
  workers pinned to CPUs **4 / 5**, sharing the L4 and a dynamic queue. The run
  finished within its **30-minute / 0.5-GPU-hour cap**. The
  [launch check](/mnt/workspaces/Cells/plasma-calcium-throughput-development-20260929-01/launch-check.json)
  preserves the live-worker and preparation verification at **02:47 UTC**.

  The [cost profile](/mnt/workspaces/Cells/plasma-calcium-throughput-20260929-01/cost-profile.json)
  records **10.51 / 12.72 seconds per world** for batches **16 / 32**, using
  the runner's upper-middle task sample, including compilation and I/O. There
  are only four / two task samples and they use distinct stochastic worlds;
  these are not paired batch-speedup measurements. Across overlapping tasks,
  compilation summed to **207.25 s**, execution **1251.89 s**, host transfers
  **9.25 s** and checkpoint writes **2.30 s**; these sums are not wall time.

  The existing [matrix preparer](validation/ensemble/cluster_matrix.py) now
  accepts `--family plasma`. The
  [preparation](/mnt/workspaces/Cells/plasma-calcium-throughput-preparation-20260929-01/preparation.json)
  authenticates the completed CPU/L4 qualification, its frozen example and GPU
  assembly evidence, and requires all **113 production files** to match. The
  launched definition, plan and production hashes match that preparation.
  Physics, **12.5-us steps**, **20-ms horizon**, **16-tick windows**, observations,
  per-cell random streams and numerical/checkpoint checks are unchanged. The
  preparer checked all task definitions and complete, disjoint world IDs; lint,
  formatting and whitespace checks passed.

  Two batch sizes keep equal arm populations while fitting the disk reserve;
  the previous three-size / 192-world layout would exceed it for this model.
  The planned output bound is **733.75 MiB**, plus a **256-MiB cache allowance**
  and **4-GiB free-disk reserve**. Conservative host sizing requires **8 GiB
  per worker plus 4 GiB reserve** (20 GiB available); this is a prelaunch check,
  not an enforced RSS cap. The check passed with **20.65 GiB available**.
  GPU allocator fraction is **0.2 per worker**, and the inherited task cap is
  **600 seconds**. Production solver and scheduler code are unchanged.

  This completes the local throughput check of the qualified synthetic model;
  GH200 scaling, full native BETSE trajectories and biological calibration
  remain open. Outputs are under
  [/mnt/workspaces/Cells/plasma-calcium-throughput-20260929-01](/mnt/workspaces/Cells/plasma-calcium-throughput-20260929-01),
  with caches/logs under the corresponding development directory.

- **Plasma calcium GPU retry completed at 00:17:17 UTC on 29 September**,
  in **1964.63 seconds (32 min 45 s)**. The
  [result](/mnt/workspaces/Cells/plasma-calcium-20260928-02/result.json)
  records **233 GPU passes / no failures or skips** and authenticates reuse of
  the **229-pass / four-deferral CPU phase**. All formerly unfinished regressions
  have now passed. The GPU pytest phase itself took **1940.85 seconds**.
  Controller PID **25468** has exited; the L4 was idle at the 00:41 UTC status check.

  The [completion check](/mnt/workspaces/Cells/plasma-calcium-development-20260928-01/completion-check-20260929-0041.json)
  during the user's **00:41 UTC** status request authenticated **356 frozen
  source files**, all **152 completion artifacts**, both complete test reports,
  test identities/order and CPU reuse provenance. Every saved CPU/L4 comparison
  recomputes exactly: **665,107 scalar values** across chemistry, ER, spatial
  calcium and plasma/assembly, including **325,747** in the new family. Maximum
  absolute difference is **3.89e-16** at unchanged **3e-10 / 3e-13**
  relative/absolute tolerances. No stderr or failure artifact is present.

  Independent DOP853/Radau trajectories and **25/12.5/6.25-us** refinement pass;
  chemical-state errors improve by **20.72 / 32.94 times**. Plasma/assembly
  event references, blockers, complete checkpoint/window/partition replay and
  unchanged protein streams also pass. The plasma GPU baseline energy residual
  is **1.80e-13 pJ**. This qualifies the declared synthetic **20-ms** regime and
  positive-domain native PMCA equation, not native full trajectories or biology.

  Peak child RSS was **7.98 GiB**, only **24.67 MiB** below the registered 8-GiB
  ceiling; artifacts/cache used **153.42 MiB**. About **5.47 GiB** remains free
  on the workspace disk. The next bounded throughput profile needs its own
  memory/output sizing. No new simulation or follow-up job was launched during
  that status check; the later throughput launch is recorded above.

  The retry launched at **23:44:30 UTC on 28 September**. Its
  [registration](/mnt/workspaces/Cells/plasma-calcium-20260928-02/registration.json)
  binds the completed **229-pass / four-deferral CPU phase** from the first
  attempt. The interrupted GPU phase had no final XML report, so all **233 GPU
  tests** ran afresh, with per-test logs and a complete report. The attempt
  finished within the **30–60-minute estimate** and **75-minute cap**.

  The existing [runner](validation/assembly/qualify_cell.py) now accepts
  `--cpu-baseline` for this timeout recovery. The
  [launch check](/mnt/workspaces/Cells/plasma-calcium-development-20260928-01/continuation-launch-check.json)
  authenticated **356 frozen source files**, **72 copied CPU evidence files**,
  test identities/order, CPU affinity and registration. **Only the runner
  changed**; production physics, tests, inputs, native sources, protocol and
  tolerances are identical to the first attempt. CPU runtime equality is also
  required before the GPU phase. All **122 artifacts** from the prior status
  receipt remain unchanged. Original CPU reports and arrays are copied with
  explicit provenance; the old run is never written to.

  The [reuse checks](/mnt/workspaces/Cells/plasma-calcium-development-20260928-01/cpu-reuse-tests.xml)
  passed **15 tests in 1.12 seconds**, including rejection of altered physics,
  incomplete/failed reports, unexpected deferrals, changed test order and
  modified evidence. Lint, formatting and whitespace checks passed. Independent
  copies of **1191 JAX cache files / 117,165,587 bytes** and two CUDA cache files
  may avoid recompilation. The run retains CPUs **4 / 5**, the L4, **8-GiB child
  RSS**, **0.15 GPU allocator fraction**, **1.5-GiB total artifact/cache allowance**
  and the **4-GiB free-disk reserve**. Outputs are under
  [/mnt/workspaces/Cells/plasma-calcium-20260928-02](/mnt/workspaces/Cells/plasma-calcium-20260928-02).

- **Plasma calcium / assembly qualification timed out at 20:38:36 UTC on
  28 September**, after **4501.69 seconds**. The
  [failure artifact](/mnt/workspaces/Cells/plasma-calcium-20260928-01/failure.json)
  records the registered **75-minute wall limit**, not a numerical assertion
  failure. The [CPU suite](/mnt/workspaces/Cells/plasma-calcium-20260928-01/cpu.xml)
  completed in **2002.91 seconds (33 min 23 s)** with **229 passes / four
  explicit GPU deferrals**. The GPU log reports **67 passes / no failures**
  before termination: all **44 plasma/assembly tests**, then 23 prior spatial
  calcium tests. It was next executing the prior spatial calcium complete
  restart/window/partition test. **166 GPU tests remain unfinished**, and no
  final GPU XML, result or completion artifact exists.

  The [status check](/mnt/workspaces/Cells/plasma-calcium-development-20260928-01/status-check-20260928-2325.json)
  during the user's **23:25 UTC** request authenticated all frozen sources,
  checked CPU XML and ordered GPU progress, and verified every required new
  plasma evidence record. The saved
  [CPU/L4 comparison](/mnt/workspaces/Cells/plasma-calcium-20260928-01/plasma-evidence/gpu/cpu-gpu.json)
  recomputes exactly across **325,747 scalar values**, with maximum absolute
  difference **3.89e-16** at unchanged **3e-10 / 3e-13** relative/absolute
  tolerances. Independent DOP853/Radau references, timestep refinement and
  complete plasma/assembly replay passed. The baseline energy residual is at
  most **1.81e-13 pJ**. These are partial passing results within an **incomplete
  overall qualification**, not a new full acceptance result.

  Controller PID **4130941** has exited; the L4 is idle. The original run
  launched at **19:23:33 UTC**. Its
  [registration](/mnt/workspaces/Cells/plasma-calcium-20260928-01/registration.json)
  freezes **356 source files** and **233 tests per backend**: four CPU checks
  explicitly defer CPU/L4 comparison to the subsequent GPU phase, which permits
  no skips. The [launch check](/mnt/workspaces/Cells/plasma-calcium-development-20260928-01/launch-check.json)
  authenticated the frozen source, registration, test counts, CPU affinity and
  detached process. All failed and passing evidence remains untouched under
  [/mnt/workspaces/Cells/plasma-calcium-20260928-01](/mnt/workspaces/Cells/plasma-calcium-20260928-01).
  No follow-up job was launched during that status check. The later GPU retry
  with authenticated CPU reuse is recorded above. Numerical tolerances remain
  unchanged.

  [`spatial_calcium@2`](docs/PLASMA_CALCIUM.md) adds the positive-domain BETSE
  `pumpCaATP` equation and a separately named **synthetic reversible 3-Na/1-Ca
  exchanger**. The pinned native PMCA function ignores its `block` argument;
  Cells' availability control is explicitly separate. NCX stoichiometry has
  experimental support, but its kinetic law and example rates are uncalibrated.
  Both routes use the existing finite cytosol/outside inventories, stage voltage
  and assembly composition, with separate cycle, dissipation and PMCA work
  records. Native full-trajectory parity remains open.

  The [25-check preflight](/mnt/workspaces/Cells/plasma-calcium-development-20260928-01/preflight.xml)
  passed in **4.89 s**, including native pump correspondence, exchanger reversal
  and stall derivative, strict inputs, independent stage accounting, observation
  enclosure and 16-GPU planning. The independent physical energy derivative
  residual was **8.89e-15 pJ/s**. Two
  [short trajectory checks](/mnt/workspaces/Cells/plasma-calcium-development-20260928-01/smoke.xml)
  passed in **51.57 s**: disabling both routes reproduced `@1` exactly, while
  merged timed plasma/ER interventions agreed with the independent reference.
  Lint, formatting and whitespace checks passed.

  The [protocol](validation/chemistry/plasma_protocol.json) retains the **20-ms
  horizon**, **25/12.5/6.25-us refinement**, independent DOP853/Radau references,
  unchanged numerical tolerances, complete restart/partition checks, assembly
  event references and prior spatial/ER/chemistry regressions. The existing
  detached runner uses CPUs **4 / 5**, then the L4, with a **75-minute wall cap**,
  **8-GiB child RSS allowance**, **0.15 GPU allocator fraction**, **1.5-GiB
  artifact/cache allowance** and **4-GiB free-disk reserve**. The original
  roughly-one-hour estimate was too short; correctness qualification is not a
  utilization benchmark.
  Sustained GPU profiling follows separately after qualification.

- **Spatial calcium/assembly L4 throughput profile completed at 01:17:12 UTC
  on 28 September**, in **913.31 seconds (15 min 13 s)**; completion evidence
  verified during the user's **17:13 UTC** status request. The
  [result](/mnt/workspaces/Cells/spatial-calcium-throughput-20260928-01/result.json)
  records all **192 worlds / 14 tasks / 307,200 world steps** completed, with
  no failed or missing tasks, abnormal worker exits or stderr. Whole-job GPU
  busy time is **85.34%** with **99.86% telemetry coverage**; after both workers
  warm it is **89.89%** with complete coverage. Missing intervals count as zero.
  The **70% advisory target is met**. Local allocation cost is **0.25370 GPU-hours**,
  giving **756.81 worlds / 1,210,892.29 world steps per allocated GPU-hour**.

  Workers finish **32.60 seconds apart**, **3.57%** of total runtime. The
  [cost profile](/mnt/workspaces/Cells/spatial-calcium-throughput-20260928-01/cost-profile.json)
  records median task costs of **9.56 / 9.42 / 8.97 seconds per world** at batch
  sizes **8 / 16 / 32**, a **6.63% spread** including compilation, host work,
  I/O and contention. Batch 32 has the lowest observed median; these are
  unpaired timing samples from different world IDs. Summed compilation /
  execution / host-transfer / checkpoint time is **142.68 / 1,618.30 / 17.91 /
  2.33 seconds** across overlapping tasks.

  The [completion check](/mnt/workspaces/Cells/spatial-calcium-throughput-development-20260928-01/completion-check-20260928-1713.json)
  authenticates the registration, preparation, **110 frozen production files**,
  all **14 results and complete checkpoints**, every world ID and the final
  **20-ms** clocks. The existing checkpoint loader's source/runtime/checksum,
  shape, domain and conservation checks pass. Aggregation and both utilization
  intervals recompute exactly. Maximum energy residual is **1.99e-13 pJ** and
  global ion-balance residual **2.16e-15 fmol**; all per-cell assembly material
  residuals are zero. Controller PID **3797645** and workers **3797649 / 3797651**
  have exited; the L4 is idle and **5.8 GiB** remains free. No new simulation or
  follow-up job was launched.

  The run launched at **01:02:00 UTC** from the
  [launch](/mnt/workspaces/Cells/spatial-calcium-throughput-20260928-01/launch.json)
  and [registration](/mnt/workspaces/Cells/spatial-calcium-throughput-20260928-01/registration.json).
  Each batch-size arm used 64 worlds, with two persistent workers on CPUs
  **4 / 5** sharing the L4.

  The existing [matrix preparer](validation/ensemble/cluster_matrix.py) now
  accepts `--family calcium`. Its
  [preparation](/mnt/workspaces/Cells/spatial-calcium-throughput-preparation-20260928-01/preparation.json)
  authenticates the completed CPU/L4 qualification, its frozen example and GPU
  assembly evidence, and requires the same **110 production files**. The live
  production solver and scheduler are unchanged. Every task preserves the
  **12.5-us timestep, 20-ms horizon, 16-tick windows**, observations, physics,
  conservation/domain/energy checks and per-cell random streams. Preparation
  checked complete, disjoint world IDs and unchanged arm definitions; lint,
  formatting and whitespace checks passed. The launched definition, plan and
  frozen production hashes match the preparation.

  Resource limits were a **30-minute campaign cap** (at most
  **0.5 allocated L4 GPU-hours**), unchanged **600-second task cap**, **0.2 GPU
  allocator fraction per worker**, **1.30-GiB planned output bound**, **256-MiB
  cache allowance** and **4-GiB free-disk reserve**. The local numerical and
  utilization gate sets `ready_for_node_pilot=true`; GH200 deployment,
  multi-GPU scaling and biological validity remain unqualified.

  All outputs are under `/mnt/workspaces/Cells/spatial-calcium-throughput-20260928-01`;
  preparation and caches/logs use the matching `throughput-preparation` and
  `throughput-development` directories. No automatic follow-up benchmark,
  audit or JUPITER submission is scheduled. The next model work is plasma
  calcium extrusion/exchange, retaining this qualified L4 baseline.

- **Corrected spatial calcium/assembly CPU/L4 qualification passed at
  23:25:49 UTC on 27 September**, in **1718.20 seconds (28 min 38 s)**. The
  [result](/mnt/workspaces/Cells/spatial-calcium-20260927-02/result.json)
  records **186 CPU passes / three GPU deferrals**, followed by **189 GPU-phase
  passes / no skips**, including the deferred comparisons. There were no
  failures or stderr. Controller PID **3754382** has exited; the L4 was idle
  when this completion was checked.
  The
  [launch](/mnt/workspaces/Cells/spatial-calcium-20260927-02/launch.json),
  [registration](/mnt/workspaces/Cells/spatial-calcium-20260927-02/registration.json)
  and [completion](/mnt/workspaces/Cells/spatial-calcium-20260927-02/completion.json)
  retain the frozen run and the corrected empty-observation regression.

  Full-state independent DOP853/Radau references, timestep refinement,
  conservation/energy checks, interventions, public CLI, complete ionic and
  assembly restart/window/partition replay, aggregation and previous ER/chemistry
  regressions pass. CPU/L4 comparison covers **300,099 scalar values** across
  the ionic history and complete assembly final state, at `rtol=3e-10`,
  `atol=3e-13`, with integer/bool fields exact. The maximum absolute numerical
  difference is **2.23e-16**. Maximum chemical amount reference error is
  **2.23e-13 fmol**; halving the step improves it **20.73x**, then **33.24x**, to
  **6.68e-15 fmol**. Maximum baseline energy residual is **1.68e-13 pJ**, against
  **1e-9 pJ**. The assembly event reference now passes; blocking its channel
  coupling changes calcium by **1.20e-9 fmol** while preserving protein paths.
  This remains a synthetic one-way coupling hypothesis.

  The [completion check](/mnt/workspaces/Cells/spatial-calcium-development-20260927-01/completion-check-20260928-0050.json)
  verifies **349 frozen source files**, **102 completed artifacts**, suite counts
  and protocol, and recomputes the saved spatial calcium CPU/L4 comparisons.
  The run stayed within the unchanged **45-minute wall cap**, **6-GiB child RSS**,
  **1.5-GiB artifact/cache** and **4-GiB disk-reserve** limits: peak child RSS
  **4.66 GiB**, artifacts/cache **90.97 MiB**; **6.1 GiB** free at the status check.

  The qualification's 1,085 GPU samples average **5.03% GPU busy**, including
  compilation, CPU reference solves, I/O and small test cases; peak GPU memory
  was **784 MiB**. Sustained throughput/utilization for this combined calcium
  model remains unmeasured. The next performance step is bounded L4 batch-size
  and worker profiling; plasma calcium extrusion/exchange and IP3 release remain
  model extensions. Full native BETSE trajectories, biological calibration and
  real multi-GPU scaling remain open. The earlier failed run is preserved.
  No new simulation, regression or throughput job was launched on this status
  request.

- **Spatial calcium/assembly CPU/L4 qualification stopped at 22:11:23 UTC
  on 27 September**, after **389.56 seconds (6 min 30 s)**: **25 CPU passes,
  one failure; GPU phase not started**. The
  [failure](/mnt/workspaces/Cells/spatial-calcium-20260927-01/failure.json) and
  [CPU log](/mnt/workspaces/Cells/spatial-calcium-20260927-01/cpu.stdout.log)
  preserve the independent assembly reference's empty-observation error.
  Controller PID **3738129** has exited. `spatial_calcium@1` adds one buffered
  cytosol/ER pair per cell to
  the existing spatial ionic cluster. Plasma calcium uses passive GHK transport;
  Na/K pumps, potassium channels, junctions and finite outside regions remain
  stage-consistent. Chemical stores own free/bound ions; an independent
  whole-cell exchange ledger determines plasma voltage, so internal ER exchange
  cannot create outer-membrane charge. Both capacitor energies, reaction and
  transport dissipation, and both maintained metabolic work conventions enter
  the combined **1e-9-pJ** energy check. The
  [scientific contract](docs/SPATIAL_CALCIUM.md) and
  [protocol](validation/chemistry/spatial_protocol.json) address this ownership
  and energy-coupling risk.

  The [ionic example](configs/spatial_calcium_cluster.json) has two cells and
  three outside regions. The
  [assembly example](configs/assembly_regulated_calcium_cluster.json) uses the
  existing event-union solver: assembly changes potassium-channel availability,
  which can affect calcium through voltage and transport. Protein pools remain
  separately owned; calcium-dependent assembly rates are not introduced. The
  shared ensemble adapter now retains the actual physical-model identity and
  calcium summaries; planning preserves world IDs through four-node/16-GPU
  plans. Remote execution, scaling and sustained utilization remain unqualified.

  The completed CPU checks pass full-state independent DOP853/Radau comparison,
  timestep refinement, material/charge/energy accounting, four interventions,
  complete ionic restart/window/partition replay and the public CLI. Maximum
  baseline chemical amount error is **2.23e-13 fmol** and energy residual
  **1.66e-13 pJ**. The assembly baseline also completed two worlds and 22 events,
  but its independent event reference failed while sampling an interval with
  no requested observation times. The live helper now skips sampling such
  intervals while still integrating every interval. Its
  [focused regression](/mnt/workspaces/Cells/spatial-calcium-development-20260927-01/reference-empty-selection.xml)
  passes in **1.50 seconds**; lint passes. The
  [failure/fix check](/mnt/workspaces/Cells/spatial-calcium-development-20260927-01/failure-check-and-reference-fix.json)
  authenticates all **349 frozen source files** and records the preserved
  evidence and live fix. Assembly reference/replay/calcium-response/aggregation,
  remaining regressions and GPU agreement were still pending at this failure;
  the corrected qualification above completes those checks.

  [Development checks](/mnt/workspaces/Cells/spatial-calcium-development-20260927-01/development-checks.json)
  record **18 focused passes**, including ownership/schema/charge checks,
  ensemble planning and public CLI complete-artifact loading. The
  [short reference/assembly probe](/mnt/workspaces/Cells/spatial-calcium-development-20260927-01/reference-assembly-probe-02.json)
  agrees with independent scalar DOP853 and Radau equations, with maximum
  chemical amount error **2.90e-13 fmol**, energy residual **1.39e-13 pJ**, and
  exact assembly restart with changed windows. The initial 25-us probe missed
  an off-grid potassium comparison by **5.40e-12 fmol**; its failed log is
  retained. The coupled default is now **12.5 us**, with **25/12.5/6.25-us**
  refinement and unchanged numerical tolerances. The finest full-trace estimate
  is **814,212,896 bytes**; its initial 512-MiB budget refusal is retained, and
  the examples explicitly reserve **1 GiB** for traces within the unchanged
  **6-GiB child RSS**, **1.5-GiB artifact/cache** and **4-GiB disk-reserve** limits.

  The [launch](/mnt/workspaces/Cells/spatial-calcium-20260927-01/launch.json) and
  [registration](/mnt/workspaces/Cells/spatial-calcium-20260927-01/registration.json)
  identify frozen inputs for the established runner's `--chemistry
  --chemistry-case spatial` panel. It includes full-state independent references,
  refinement, interventions/component reductions, scalar/batch restart and
  partitions, assembly event references and calcium response, CPU/L4 agreement,
  and prior ER/chemistry plus selected assembly regressions. Three CPU comparisons
  defer to the GPU phase; no GPU skips are permitted. The full panel has a
  **45-minute wall cap**. No follow-up qualification was launched on this status
  request. The subsequent user instruction authorized the fresh frozen rerun
  recorded above, which completed in 28 min 38 s.
  This panel does not establish native BETSE lifecycle/trajectory parity,
  measured biology, IP3, calcium extrusion/exchange pumps or calcium feedback
  on assembly.

- **Finite ER/cytosol calcium passed CPU/L4 qualification at 20:28:29 UTC
  on 27 September**, in **503.61 seconds (8 min 24 s)**; completion evidence
  verified at **20:56 UTC**. The
  [result](/mnt/workspaces/Cells/er-20260927-01/result.json) records **148 CPU
  passes / two explicit GPU deferrals**, then **150 GPU-phase passes / no skips**,
  including both deferred comparisons. No failures or stderr occurred.
  `er_calcium@1` adds one finite compartment pair per independent world, existing
  buffer chemistry and GHK transport, charge-derived ER voltage, a named
  positive-domain BETSE pump, calcium-only release, and separate transfer,
  dissipation and maintained-metabolic-work ledgers. The synthetic
  [20-ms example](configs/er_calcium_buffered.json),
  [scientific contract](docs/ER_CALCIUM.md) and
  [protocol](validation/chemistry/er_protocol.json) keep its scope explicit.
  The source pump uses the native numeric mM quotient and one calcium per formal
  turnover; it does not claim a detailed two-Ca SERCA/proton model or finite ATP.

  Independent DOP853/Radau references, authenticated native pump/release
  functions, interventions, stall/equilibrium, material/charge/energy accounting,
  public CLI and prior chemistry/checkpoint regressions pass. CPU/L4 agreement
  covers **29,637 ER scalar values**, with maximum absolute difference
  **6.94e-18** at `rtol=3e-10`, `atol=3e-13`. Halving the timestep reduces amount
  error by **16.83x**, then **17.19x**, to **1.04e-14 fmol** on both devices.
  Maximum baseline energy residual is **1.05e-12 pJ** against **1e-9 pJ**.
  Complete restart, future-control branches, changed windows and partitions
  **1/2/3**, world IDs **17/31/90**, replay exactly. Native correspondence covers
  six forward/reverse pump points and 25 release points with harmonized constants.

  Failed development evidence is retained. A scalar ledger shape was corrected
  to the established one-route array representation; a test's control tuple
  indexing was fixed. The initial DOP853 reference missed the strict potassium
  comparison by **6.74e-12 fmol**. Radau plus production timestep refinement
  localized this to reference accuracy; reference solves now use `rtol=2e-13`,
  `atol=2e-17`, and a **50-us maximum internal step**, without relaxing production
  checks. An extra 6.25-us full-trace probe correctly refused its memory bound;
  the registered refinement remains **50/25/12.5 us**.

  The existing detached runner uses `--chemistry --chemistry-case er`. Frozen
  inputs include the pinned BETSE source functions. The run stayed within its
  **45-minute wall cap**, **4-GiB free-disk reserve**, **1.5-GiB artifact/cache
  allowance** and **6-GiB child RSS allowance**: peak child RSS was **1.76 GiB**,
  artifacts/cache **18.47 MiB**, with **6.4 GiB** free at the status check.
  Native BETSE lifecycle/trajectory
  parity, IP3, plasma-membrane/assembly integration, sustained GPU throughput and
  multi-GPU scaling remain outside this panel. No automatic follow-up is planned.

  The [launch](/mnt/workspaces/Cells/er-20260927-01/launch.json) and
  [registration](/mnt/workspaces/Cells/er-20260927-01/registration.json) identify
  the frozen run. The
  [completion check](/mnt/workspaces/Cells/er-development-20260927-01/completion-check-20260927-205659.json)
  authenticates **342 frozen files** and **61 completed artifacts**, suite counts
  and protocol, and recomputes stored CPU/GPU differences, reference agreement,
  refinement factors, native function correspondence and exact partition replay.
  [Development checks](/mnt/workspaces/Cells/er-development-20260927-01/development-checks.json)
  retain the 20 distinct preflight passes and development probes/failures.
  Controller PID **3701806** has exited; the L4 is idle. No further computation
  was launched. The next model extension is plasma-membrane calcium transport
  and coupling to the spatial ionic/assembly model, followed by its qualification.

- **Closed compartment chemistry passed CPU/L4 qualification at 19:50:42 UTC
  on 27 September**, in **94.70 seconds (1 min 35 s)**; verified during the
  user's **19:52 UTC** status request. The
  [result](/mnt/workspaces/Cells/chemistry-20260927-01/result.json) records
  **119 CPU passes / one explicit GPU deferral**, then **120 GPU-phase passes /
  no skips**, including the deferred comparison. No failures or stderr occurred.
  `compartment_reactions@1` provides named reversible reaction
  networks, independent fixed-volume inventories, finite moieties/charge and
  per-reaction extent/dissipation ledgers. Reverse rates derive from species
  standard potentials to enforce detailed balance. The
  [example](configs/calcium_buffer_compartments.json) is a synthetic 100-ms,
  two-compartment sequential calcium-buffer model; it adds no ER transport,
  calcium membrane current or feedback to existing ionic/assembly dynamics.
  The [scientific contract](docs/COMPARTMENT_REACTIONS.md) and
  [bounded protocol](validation/chemistry/protocol.json) explain the new law and
  independent thermodynamic/reference checks.

  Independent DOP853/Radau, analytic binding equilibrium, multimerization with
  a conserved catalyst, controls/isolation, padding/renaming, public CLI and
  old reaction/checkpoint regressions pass. CPU/L4 correspondence covers
  **9,624 scalar values** at `rtol=3e-10`, `atol=3e-13`; the maximum absolute
  difference is **1.73e-18** across the stored amount/extent/energy coordinates.
  Halving the timestep reduces amount error by **16.19x**, then **16.31x**, to
  **9.84e-15 fmol**. Maximum baseline energy residual is **2.16e-12 pJ** against
  the unchanged **1e-9 pJ** limit. Complete restart, future-control branches,
  changed windows and world partitions **1/2/3**, IDs **17/31/90**, replay exactly
  on both devices. This is a bounded numerical qualification, not native BETSE
  calcium parity, biological calibration or a sustained GPU utilization result.

  The [initial development probe](/mnt/workspaces/Cells/chemistry-development-20260927-01/initial-probe-02.json)
  agrees with independent DOP853 amounts to **1.60e-13 fmol**, with maximum
  energy residual **2.16e-12 pJ**. The
  [preflight](/mnt/workspaces/Cells/chemistry-development-20260927-01/preflight.xml)
  records **22 passes**, including strict definitions, local rates and public
  artifacts. The [batch probe](/mnt/workspaces/Cells/chemistry-development-20260927-01/batch-probe.json)
  verifies exact two-world window/scalar replay, complete cohort disk loading
  and the no-reaction reduction. These development checks preceded the full
  CPU/L4 panel. The initial missing observer import failure
  is retained in the development directory; it was corrected to use the
  existing `hermite_bounds` observer helper.

  The [launch](/mnt/workspaces/Cells/chemistry-20260927-01/launch.json) and
  [registration](/mnt/workspaces/Cells/chemistry-20260927-01/registration.json)
  record the **19:49:07 UTC** detached start, PID **3689559**, using the existing
  `validation/assembly/qualify_cell.py --chemistry` runner. The
  [completion check](/mnt/workspaces/Cells/chemistry-development-20260927-01/completion-check-20260927-195222.json)
  authenticates **333 frozen files** and **34 completed artifacts**, suite
  counts and protocol, and recomputes CPU/GPU differences, refinement factors,
  reference agreement and exact stored partition replay. Peak child RSS was
  **1.31 GiB** and retained artifacts/cache **6.98 MiB**; the **4-GiB disk reserve**
  remains intact. Complete logs and evidence remain in the run directory.
  [Development checks](/mnt/workspaces/Cells/chemistry-development-20260927-01/development-checks.json)
  bind the implementation, static checks and short probes. No follow-up job
  was launched during that status check. ER exchange is now qualified above;
  calcium-current/ionic feedback is next. The new family's shared ensemble
  adapter and JUPITER scaling remain later work.

- **Assembly-cluster L4 cost profile completed at 17:38:26 UTC on 27 September**,
  in **764.96 seconds (12 min 45 s)**; verified during the user's **19:14 UTC**
  status request. The
  [result](/mnt/workspaces/Cells/assembly-cluster-throughput-20260927-01/result.json)
  records **768 worlds / 18 tasks / 307,200 world steps completed**, with no
  failures, missing tasks or abnormal worker exits. All worlds reach **20 ms**.
  The **70% advisory utilization target is met**: **87.69% whole-job GPU busy
  time** with **99.78% coverage**, and **93.24% after both workers warm** with
  complete coverage. Missing telemetry intervals count as zero. This measures
  NVIDIA GPU busy time, not SM occupancy. Local allocation cost is **0.21249
  GPU-hours**, yielding **3,614.33 worlds / 1,445,731.53 world steps per GPU-hour**.

  Worker finishes are **1.87 seconds apart**. Mean task cost spans **1.819–2.227
  seconds/world** including compilation, host work, checkpoints and contention.
  Subtracting recorded compilation time gives **1.818–1.909 seconds/world**,
  a **4.96% spread**; this is descriptive accounting, not a paired speedup.
  The [cost profile](/mnt/workspaces/Cells/assembly-cluster-throughput-20260927-01/cost-profile.json)
  retains the scheduler's original median estimates including compilation/I/O.
  Summed compile / execute / checkpoint time is **96.34 / 1,408.37 / 4.93
  seconds** across overlapping tasks.

  The [completion check](/mnt/workspaces/Cells/assembly-cluster-throughput-development-20260927-01/completion-check-20260927.json)
  authenticates the registration/startup, prepared definition/plan and **102
  frozen production files**, all **18 results and complete checkpoints**, and
  every world ID and final clock. The existing checkpoint loader's source,
  runtime, checksum, domain and conservation checks pass. Aggregation and both
  utilization intervals recompute exactly. Maximum ionic energy residual is
  **1.67e-14 pJ** and global material residual **1.12e-15 fmol**; every per-cell
  assembly material residual is zero. Controller and workers have exited;
  the L4 is idle. No follow-up job was launched during this status check.

  The run launched at **17:25:41 UTC**, PID **3639866**, from the authenticated
  [preparation](/mnt/workspaces/Cells/assembly-cluster-throughput-preparation-20260927-01/preparation.json).
  Dynamic assembly, fixed-ring and fixed-open cases each used 128 worlds at
  widths **32 and 64**, with two persistent workers on CPUs **4/5** sharing the
  L4. The qualified **50-microsecond timestep, 32-tick windows, structures,
  rates, controls and checks were unchanged**. Dynamic arms use distinct
  random world IDs; fixed controls are deterministic replicas. The local
  numerical/utilization gate sets `ready_for_node_pilot=true`; GH200 deployment,
  multi-GPU scaling and biological validity remain unqualified. No automatic
  benchmark or JUPITER submission is scheduled.

- **Assembly-cluster CPU/L4 qualification completed in 808.39 seconds
  (13 min 28 s)**, at **16:37:23 UTC on 27 September**; verified on the user's
  next continuation. The
  [result](/mnt/workspaces/Cells/assembly-cluster-20260927-01/result.json) records
  **53 CPU passes / three GPU deferrals**, then **57 GPU passes / no skips**.
  Exact disk restart, changed windows and partition widths **1/2/3**, including
  nonzero world IDs, now pass on both devices. Independent event/spatial
  references, refinement, neighbour controls, simultaneous events, one-cell
  reduction, public checkpoints and per-cell aggregation pass. CPU/L4 agreement
  covers **496 scalar values** at the unchanged `rtol=3e-10`, `atol=3e-13`.

  The old failure reproduced in **38.22 seconds**: **one of 496 scalar values**
  differed, only in `ionic_face_dissipated_energy_pJ`, by **one ULP / 5.55e-17
  pJ**. The corrected kernel maps complete windows over independent worlds with
  `lax.map`, keeping per-world field/energy arithmetic scalar and cell events
  vectorized. Exact replay and all scientific tolerances remain unchanged.
  The former failed evidence and its regenerated endpoints remain preserved.

  The [completion check](/mnt/workspaces/Cells/assembly-cluster-development-20260927-01/completion-check-20260927.json)
  authenticates the startup registration, **330 frozen files**, **105 completed
  artifacts**, suite counts, and both task results/complete checkpoints in the
  **two-worker, four-world L4 queue**. Peak child RSS was **3.91 GiB** and retained
  run artifacts/cache **58.78 MiB**. The qualification controller exited without
  failure. The [development checks](/mnt/workspaces/Cells/assembly-cluster-development-20260927-01/development-checks.json)
  retain 19 fast preflight passes and static checks; the earlier
  [16:31 status receipt](/mnt/workspaces/Cells/assembly-cluster-development-20260927-01/status-check-20260927-1631.json)
  records the intermediate CPU-only progress.

  This is a bounded **20-ms, two-cell** numerical qualification, with one local
  extracellular owner, separate finite assembly pools and a declared one-way
  channel-control hypothesis. It does not establish native BETSE spatial
  parity, biological validity or multi-GPU scaling. Whole GPU correctness-phase
  busy time averaged **7.95%** including compilation and host checks; the
  **13.35-second** queue averaged **22.86%**, with insufficient telemetry coverage
  for the utilization gate. These short checks do not establish sustained
  throughput. The larger cost profile recorded above supplies that measurement;
  JUPITER remains later work. No job was automatically launched after qualification.

- **Assembly-cluster qualification stopped at 12:59:45 UTC on 25 September**,
  after **1,141.76 seconds (19 min 2 s)**; checked on the user's 27 September
  status request. The
  [failure](/mnt/workspaces/Cells/assembly-cluster-20260925-01/failure.json) and
  [CPU report](/mnt/workspaces/Cells/assembly-cluster-20260925-01/cpu.xml) record
  **51 passed, one failed, three explicitly deferred GPU-only tests**. No GPU
  phase or success/completion artifact exists. Its controller had exited and
  the L4 was idle at that status check. No retry or follow-up job was launched
  during that check; the user's subsequent continuation started the run above.

  The failed test first completed an exact disk roundtrip, continuation and
  changed-window replay, then compared a two-world batch with the same worlds
  run separately. The first bitwise mismatch is in
  `ionic_face_dissipated_energy_pJ`. The reported mismatch starts in the
  least-significant mantissa byte; batch-shape-dependent rounding is a plausible cause, not a
  confirmed diagnosis at that check. The separate one-world endpoint arrays
  were not saved then; the 27 September reproduction above now quantifies the
  complete mismatch. Standalone
  cell-pool independence assertions later in that test were not reached. The
  exact replay requirement and scientific tolerances remain unchanged.

  The independent event/spatial references, timestep refinement, matched
  ring/open neighbour controls, simultaneous grid-boundary events, one-cell
  reduction, public CLI checkpoints and per-cell scheduler aggregation passed
  on CPU. The
  [neighbour control result](/mnt/workspaces/Cells/assembly-cluster-20260925-01/cluster-evidence/cpu/neighbour-response.json)
  agrees with the reference: **-2.47 microvolts** in the receiving cell with
  junctions connected, **zero** with the receiver fully isolated or assembly
  coupling disabled. These are synthetic model results, not biological
  measurements. Baseline material and energy residuals are **3.87e-16 fmol**
  and **2.33e-15 pJ**. Passing these checks does not waive the failed replay gate.

  The [status check](/mnt/workspaces/Cells/assembly-cluster-development-20260925-01/status-check-20260927.json)
  authenticates the registration/launch against the startup receipt and all
  **329 frozen source files**, records the saved evidence hashes, and confirms
  the CPU test counts and absent GPU phase. The 27 September continuation above
  preserves and compares partition endpoints and tests a candidate correction
  to batch-dependent arithmetic. Only after the CPU/L4 qualification passes
  should this combined model receive a throughput/arm-balance profile. Further
  stack work remains reaction networks/calcium and broader BETSE spatial
  coverage; multi-GPU deployment follows qualified representative models.

  The run originally **launched at 12:40:42 UTC on 25 September**, detached as
  PID **2708861**.
  The [registration](/mnt/workspaces/Cells/assembly-cluster-20260925-01/registration.json)
  freezes **329 source/configuration/test files**, **55 CPU test cases** and
  **56 GPU test cases**. Three CPU cases are explicitly deferred GPU comparisons;
  all three were planned for the GPU phase. The suite includes the existing finite-pool
  and one-cell coupling regressions plus a real two-worker L4 queue. Numerical
  completion is rejected by the CPU failure. Its original estimate was
  **20–40 minutes**, with a **3,600-second** total limit.

  `assembly_regulated_cluster@1` combines cell-owned finite assembly pools with
  the qualified `spatial_extracellular@2` electrical cluster. The
  [example](configs/assembly_regulated_cluster.json) has two cells and three
  extracellular regions. Each cell has its own material balance and distinct
  seed derived from its explicit stream ID. The ionic solver advances to the
  next global grid point or the earliest event in either cell; preceding
  structures control the interval and simultaneous events commit together.
  The existing ionic laws and stage/domain/accounting tolerances are unchanged.
  Both cells still face the same local extracellular owner. Protein energetics
  and chemical feedback are outside this named one-way hypothesis.

  Complete cluster checkpoints retain every pool, pending event, spatial ionic
  state and per-cell exposure ledger. The public `assembly-cluster` CLI records
  requested grid observations and supports complete resume. The existing GPU
  queue accepts `assembly_cluster_ensemble@1`, reports cage/material outcomes
  separately for each cell, and keeps a whole interacting cluster as one
  independent world. The offline 16-GPU planner preserves world/stream IDs;
  remote execution and scaling remain unqualified. Dynamic window lengths
  reuse one compiled kernel across regular windows, observations and tails.

  The [protocol](validation/assembly/cluster_protocol.json) addresses the new
  risk of combining asynchronous assembly clocks with a shared electrical
  state. It tests independent scalar assembly histories plus independently
  implemented DOP853/Radau spatial references, **20-ms** trajectories at
  **100/50/25 microseconds**, exact disk/window/world-partition replay,
  simultaneous grid-boundary events, one-cell reduction, CPU/L4 agreement,
  corruption/fault rejection, CLI observations and actual queue execution.
  Same-material ring/open controls cover connected junctions, blocked junctions,
  a fully isolated receiver and disabled assembly coupling. Blocking a junction
  retains the shared-bath route, so it is not treated as complete isolation.

  [Development checks](/mnt/workspaces/Cells/assembly-cluster-development-20260925-01/development-checks.json)
  record **18 passing preflight tests** in **4.32 seconds**, valid resource bounds,
  lint/format/whitespace checks and the earlier small two-world CPU probe. That
  probe's maximum ionic energy residual is **1.30e-18 pJ**; it predates the dynamic
  window change and does not qualify the final kernel. The separate
  [control reference probe](/mnt/workspaces/Cells/assembly-cluster-development-20260925-01/control-reference-probe.json)
  predicts a receiver ring-minus-open voltage difference of **-2.47 microvolts**
  with junctions connected and **zero** with the receiver fully isolated.
  These are synthetic reference predictions, not production results or biological
  measurements. Initial lint failures and all development evidence are preserved.

  The [initial health check](/mnt/workspaces/Cells/assembly-cluster-development-20260925-01/launch-health.json)
  authenticates all frozen source files and the registration, and records the
  live controller with no startup failure. The run uses CPUs **4/5**, then the
  L4, retains a **4-GiB disk reserve**, and allows **1.5 GiB** for artifacts/cache
  and **6 GiB peak worker RSS**. GPU-phase telemetry is recorded; this correctness
  panel does not require 70% utilization. The previous spatial throughput result
  does not transfer automatically to the assembly-cluster workload. Logs and
  terminal completion/failure artifacts are under
  `/mnt/workspaces/Cells/assembly-cluster-20260925-01/`. No automated polling,
  follow-up benchmark, retry, audit or JUPITER submission is scheduled.

- **Spatial L4 batch-size profile completed at 11:16:51 UTC on 25 September**,
  in **798.48 seconds (13 min 18 s)**; completion verified during the user's
  **11:55 UTC** status request. The
  [result](/mnt/workspaces/Cells/spatial-throughput-20260925-01/result.json)
  records all **20 tasks / 512 worlds / 409,600 world steps completed**, with
  no missing tasks, failures or abnormal worker exits. Every world reaches the
  full **20-ms** horizon. Ordinary domain, conservation and checkpoint checks
  pass unchanged; maximum energy-balance error is **8.10e-15 pJ** and maximum
  global material residual **9.06e-16 fmol**.

  **The advisory 70% utilization target is met.** Whole-job time-weighted GPU
  busy time is **88.08%**, with **96.70% telemetry coverage** and missing
  intervals counted as zero. After both workers warm up, utilization is
  **93.81%**, with complete coverage. Allocation cost is **0.22180 GPU-hours**;
  throughput is **0.6412 worlds/s**, or **2,308.38 worlds / 1,846,702.58 world
  steps per allocated GPU-hour**. These are measurements for this synthetic
  spatial workload, not a matched speedup against the smaller qualification
  panel or a biological sample count.

  At matched batch sizes, baseline/pump-release mean task costs differ by only
  **1.35% (16 worlds)** and **0.71% (64 worlds)**. Across all four equal-count
  profiling arms, mean cost spans **2.925–3.100 seconds/world** (**5.96%** spread).
  The workers finish their last tasks only **1.92 seconds apart**. Timing includes
  compilation, host work, checkpoints and contention between the two workers;
  summed task durations overlap. Summed compile / execution / host-analysis /
  checkpoint times are **48.84 / 1,322.49 / 66.88 / 26.06 seconds**, respectively.
  The [cost profile](/mnt/workspaces/Cells/spatial-throughput-20260925-01/cost-profile.json)
  retains the runner's per-arm median estimates for later scheduling work.

  The [completion check](/mnt/workspaces/Cells/spatial-throughput-development-20260925-01/completion-check-20260925.json)
  verifies the root result and registration, prepared definition/plan, **95 frozen
  production files**, all **20 task results and enclosing checkpoints**, and
  **512 complete scalar checkpoint manifests, payload checksums, IDs, definitions
  and final clocks**. Utilization was recomputed from the saved telemetry and
  agrees exactly with both reported intervals. No failure artifact or stderr
  exists. The controller and both workers have exited; the L4 is idle. No
  follow-up job was launched. `ready_for_node_pilot=true` records the local
  numerical-completion/utilization gate; GH200 compatibility and multi-GPU
  scaling remain unqualified.

  The profile launched at 11:03 UTC, detached as PID **2651576**, using the
  existing ensemble scheduler. The
  [registration](/mnt/workspaces/Cells/spatial-throughput-20260925-01/registration.json)
  and [launch receipt](/mnt/workspaces/Cells/spatial-throughput-20260925-01/launch.json)
  bind **512 deterministic worlds across 20 tasks**: baseline and pump-release
  cases, each with **128 worlds at batch sizes 16 and 64**. Two persistent
  workers share the L4, using CPUs **4/5**. These replicas measure execution
  costs; they do not add stochastic samples or biological evidence.

  The [preparation receipt](/mnt/workspaces/Cells/spatial-throughput-preparation-20260925-01/preparation.json)
  authenticates the completed spatial qualification, selected finest-step GPU
  inputs and unchanged production sources. All task definitions and world IDs
  were checked before launch. Each world retains the qualified **25-microsecond
  timestep, 20-ms horizon, observations, physical parameters and controls**.
  Four equal **200-step windows** keep both batch sizes within the existing
  2-GiB working-array allowance. The original full-window proposal was refused
  during preflight; its logs remain in the
  [development directory](/mnt/workspaces/Cells/spatial-throughput-development-20260925-01/).
  The revised largest working-array estimate is **1.31 GiB** per task; the
  conservative output bound is **1.13 GiB**, retaining the 4-GiB disk reserve.
  Every ordinary domain, conservation and complete-checkpoint check remains
  active. No scientific code or tolerance changed. The reproducible generator
  is [spatial_matrix.py](validation/ensemble/spatial_matrix.py); lint, formatting
  and whitespace checks pass.

  The [initial health check](/mnt/workspaces/Cells/spatial-throughput-development-20260925-01/launch-health.json)
  verifies the registered definition/plan and **95 frozen production source
  files**, and records both live L4 workers with no failure receipt at startup.
  The runner records whole-job and warmed GPU utilization, per-task execution,
  host analysis and checkpoint costs, arm timing and allocated GPU-hours.
  The **70% utilization target remains advisory**; the guarded kernel still
  maps worlds sequentially within each worker, so larger batches do not imply
  vectorized GPU execution. Timing comparisons describe this shared-worker
  workload and include compilation and contention.

  The run completed within its **1,800-second / 0.5-GPU-hour budget**.
  Durable logs, checkpoints and terminal
  results/failures are under `/mnt/workspaces/Cells/spatial-throughput-20260925-01/`.
  No automatic retry, follow-up benchmark or JUPITER submission is scheduled.

- **Spatial CPU/L4 qualification passed at 17:58 UTC on 24 September**,
  in **443.43 seconds (7 min 23 s)**; completion verified on the user's
  **10:48 UTC, 25 September** status request. The
  [completed result](/mnt/workspaces/Cells/spatial-cluster-20260924-03/result.json)
  records **59 passing regression tests**, **12 independent DOP853/Radau
  reference solves**, **36 CPU/L4 trajectories** and **755,238 comparisons**.
  All **24 exact disk resumes**, **two pump-off branches** and batch ownership,
  scalar agreement and checkpoint checks pass. No tests failed or were skipped.
  All conservation, domain and CPU/GPU comparison limits pass unchanged.
  Maximum independent voltage error is **7.46e-15 V** and maximum energy
  balance error **9.77e-15 pJ**. All timestep-comparison errors are already below
  the registered **2e-11** refinement floor; this panel does not establish a
  measured convergence order beyond that floor.

  This status check authenticates the root completion/result/registration
  checksums, all **five phase receipts**, **572 phase files**, **seven pytest
  aliases**, **606 frozen source files**, both frozen input files and GPU
  telemetry. JUnit counts agree with the result. No current-run failure artifact
  or nonempty stderr log exists. All workers have exited and the L4 is idle;
  no follow-up job was launched. The earlier failed runs remain preserved.

  GPU utilization averaged **8.74%**, peaking at **69%**, over **203 one-second
  samples** covering the entire GPU phase, including compilation, host checks
  and snapshot writes. That phase took **200.94 seconds**, versus **106.44
  seconds** for CPU. This small correctness panel is not a throughput benchmark;
  larger batched workloads and utilization tuning remain unqualified. Peak
  worker RSS was **1.56 GiB**, within the 4-GiB limit; recorded artifacts total
  **33.15 MiB**, within the 768-MiB allowance. Qualification covers the synthetic
  **two-cell, three-region, 20-ms composition**. Biological calibration, native
  BETSE spatial parity, full BETSE equivalence and multi-GPU scaling remain open.

  The run launched at 17:50 UTC, detached as PID **2227292**, with a fresh
  [registration](/mnt/workspaces/Cells/spatial-cluster-20260924-03/registration.json)
  and [launch receipt](/mnt/workspaces/Cells/spatial-cluster-20260924-03/launch.json).
  The runner now records pytest's direct `*current` aliases separately from
  the hashes of real evidence files, following the existing file/link receipt
  convention. Links must target a matching numbered sibling test directory;
  links elsewhere in the evidence remain rejected. The comparison checks the
  complete file and alias inventories against their completion receipts.

  [Ten focused runner tests](/mnt/workspaces/Cells/spatial-cluster-development-20260924-03/tests.xml)
  passed in **0.15 seconds**. They cover receipt round trips, unexpected links,
  and changed, missing or added evidence. The
  [saved-artifact replay](/mnt/workspaces/Cells/spatial-cluster-development-20260924-03/artifact-replay.json)
  reproduces the original rejection, then successfully inventories all **24
  real files and four aliases** in the failed run without modifying them.
  Both earlier source snapshots remain intact. Only the spatial runner,
  its context helper and the new runner tests changed; production code,
  reference equations, inputs and scientific tolerances are unchanged.
  Lint and formatting checks pass.

  The completed panel used the same resume, branch, batch and numerical checks
  described below. Its
  [initial health receipt](/mnt/workspaces/Cells/spatial-cluster-development-20260924-03/launch-health.json)
  recorded startup and authenticated the frozen source and inputs. Durable logs
  and completion artifacts are under
  `/mnt/workspaces/Cells/spatial-cluster-20260924-03/`. No automatic follow-up
  campaign is scheduled.

- **The second spatial CPU/L4 run passed all 49 regression tests, then stopped while
  recording the regression artifacts at 13:20 UTC on 24 September**, after
  **99.48 seconds**; checked on the user's **15:22 UTC** status request. The
  [test result](/mnt/workspaces/Cells/spatial-cluster-20260924-02/regression/result.json)
  and [JUnit report](/mnt/workspaces/Cells/spatial-cluster-20260924-02/regression/tests.xml)
  agree: **49 passed, zero failures/errors/skips**, in **96.52 seconds**. The
  [failure receipt](/mnt/workspaces/Cells/spatial-cluster-20260924-02/regression/failure.json)
  identifies a runner bookkeeping failure: `u.inventory` rejects symbolic links,
  and pytest created four `*current` directory aliases inside its temporary
  output tree. All four aliases point to real test-output directories within
  this run. The previous observation-rate assertion now passes unchanged.
  Independent reference solves and full CPU/L4 trajectory phases **did not
  start**. Its controller and worker exited. No repair or retry was performed
  on that status request; the user's subsequent instruction authorized the
  runner correction and fresh run above. The completed BETSE refinement below
  remains qualified.

  This run launched at 13:18 UTC, detached as PID **2143629**, with a fresh
  [registration](/mnt/workspaces/Cells/spatial-cluster-20260924-02/registration.json)
  and [launch receipt](/mnt/workspaces/Cells/spatial-cluster-20260924-02/launch.json).
  Only the observation-rate test changed: its comparison now converts the
  final layout to NumPy, matching the host observation path. The
  [saved-data replay](/mnt/workspaces/Cells/spatial-cluster-development-20260924-02/replay-result.json)
  reproduces the original four failures at **1.42108547e-14**, then obtains
  **exact agreement in all 60 values** after conversion. The absolute **1e-14**
  test tolerance, production dynamics and all scientific limits are unchanged.
  Lint, formatting and diff checks pass. The
  [source check](/mnt/workspaces/Cells/spatial-cluster-development-20260924-02/source-check.json)
  verifies all **605 prior frozen source files** and confirms the test is the
  only source/input change from that snapshot; the failed run remains intact.

  The registered panel remains unchanged: **49 regression
  tests**, **12 independent reference solves**, **36 CPU/L4 trajectories**,
  complete disk resumes, branches and batch checks. Its
  [initial health receipt](/mnt/workspaces/Cells/spatial-cluster-development-20260924-02/launch-health.json)
  recorded the live controller at launch and authenticated the new frozen source.
  The original **15–25 minute** estimate no longer applies to this stopped run.
  Logs and completion/failure artifacts are under
  `/mnt/workspaces/Cells/spatial-cluster-20260924-02/`. No automatic retry or
  follow-up campaign is scheduled; acceptance remains pending.

- **The first spatial pump/channel/junction qualification stopped at its regression gate
  at 11:51 UTC on 24 September**, after **98.72 seconds**; checked on the user's
  12:43 UTC status request. **48 tests passed and one failed**. The
  [failure receipt](/mnt/workspaces/Cells/spatial-cluster-20260924-01/failure.json)
  and [test log](/mnt/workspaces/Cells/spatial-cluster-20260924-01/regression.stdout.log)
  preserve the failed evidence. The observation-rate consistency assertion in
  `test_compiled_runner_disk_restart_branch_and_observation_rates` differed by
  at most **1.42108547e-14**, against an absolute limit of **1e-14**, in four of
  60 values. Its preceding disk restart, branch-state and continued-face-transport
  assertions passed. Code inspection shows that this test passes a JAX layout
  to an `xp=np` RHS, while the observation path converts the layout to NumPy.
  The saved-data replay above subsequently confirmed this mixed-backend mismatch.
  The independent references and full CPU/L4 trajectories **did not start**.
  All workers from this failed run exited. No repair, retry or follow-up campaign
  was launched during the 12:43 UTC status check; the user's subsequent instruction
  authorized the correction and fresh run above. The completed BETSE refinement
  below remains qualified.

  The failed run launched at 11:50 UTC, detached as PID **2115527**. Its
  [registration](/mnt/workspaces/Cells/spatial-cluster-20260924-01/registration.json)
  and [launch receipt](/mnt/workspaces/Cells/spatial-cluster-20260924-01/launch.json)
  freeze **605 source files**, the protocol and all six input definitions.
  The new **spatial_extracellular@2** family combines the existing kinetic
  ATPase, Kv1p5 channels and physical-time junction gates with the spatial
  field/transport solver, all at the same RK4 stage on CPU or GPU. The
  [example configuration](configs/spatial_kinetic_cluster.json) contains two
  cells and three finite extracellular regions. All cells face the same local
  outside region; its neighbours exchange ions through three conductive faces.
  Junctions therefore remain within one capacitor component. Cross-region
  junctions require a different coupled field closure and are explicitly rejected.

  [Development checks](/mnt/workspaces/Cells/spatial-cluster-development-20260924-01/development-checks.json)
  record **21 passing fast tests**, independent initial-rate agreement within
  **7.11e-15**, and two-step compiled CPU and **L4 / cuda:0** smoke runs. Maximum
  energy-accounting residuals are **1.39e-17 / 1.56e-17 pJ**, respectively.
  Tests cover ownership, gauge/orientation invariance, the zero-face finite-bath
  limit, invalid charge/topology, padding and corrupted histories. Lint and
  diff checks pass; earlier lint failures are retained. The full frozen regression
  gate includes lifecycle/batch tests and the prior junction-family checks.

  The [protocol](/mnt/workspaces/Cells/spatial-cluster-20260924-01/protocol.json)
  addresses the new composition's electrical closure and energy-accounting risk:
  **12 independent DOP853/Radau solves** and **36 ordinary CPU/L4 trajectories**
  over **20 ms**, at **100 / 50 / 25 microseconds**. The six cases cover baseline,
  pump/channel/junction blocking and release, blocked membrane/junction transport,
  and the zero-face finite-bath limit. It also requires **24 complete disk resumes**,
  two pump-off branches, two heterogeneous batch worlds on each backend and
  complete batch snapshot round trips. All state fields and physical observations
  enter the comparison; normalized field residuals are bounded independently
  on each backend. Unit-aware current, charge, power and work tolerances are
  explicit. No conservation/domain tolerance in an existing family is relaxed.

  The existing ionic-world ensemble adapter now accepts this family, retaining
  stable world IDs, bounded windows and complete checkpoint ownership. This
  supports later scheduling work; **multi-GPU scaling is not qualified**.
  The detached runner records GPU utilization throughout its GPU phase, including
  compilation, host checks and snapshot writes; this small verification panel
  is not a throughput benchmark. Limits are **4 GiB worker RSS**, **128 MiB per
  file**, **768 MiB total artifacts** and a **4-GiB disk reserve**. Workers use
  CPUs 4/5 and the L4, with no JUPITER submission. The original registered
  estimate was **1,200 seconds**; this first attempt stopped after **98.72 seconds**.
  Durable logs and
  completion/failure receipts remain under `/mnt/workspaces/Cells/`.
  No automatic retry or follow-up campaign is scheduled. Full panel acceptance,
  native BETSE spatial parity and biological calibration remain unclaimed.

- **Full 512,000-step BETSE refinement passed at 04:31 UTC on 24 September**,
  in **58,941.25 seconds (16 h 22 min 21 s)**; completion verified on the
  user's 11:10 UTC status request. The
  [completed result](/mnt/workspaces/Cells/betse-long-pump-eighth-step-20260923-01/result.json),
  [registration](/mnt/workspaces/Cells/betse-long-pump-eighth-step-20260923-01/registration.json)
  and [launch receipt](/mnt/workspaces/Cells/betse-long-pump-eighth-step-20260923-01/launch.json)
  bind two sequential **100-ms captures at 0.1953125 microseconds**, observed
  and unobserved, followed by the existing independent comparison. All
  **140 frozen regression tests pass**. The run reuses the qualified
  Cells trajectories, disk restart and three independent 100-ms references;
  their production source snapshot is retained. It also authenticates the
  completed memory qualification and its matching 51,200-step / 10-ms prefix.

  **All 43 numerical constraint groups pass**, including energy closure at
  **6.1174646e-8 pJ**, below the unchanged **1e-7 pJ** limit. This clears the
  earlier 256,000-step energy-closure miss for the finer timestep. The
  **four-level timestep ladder qualifies**, with all three successive
  trajectory contractions passing (two required) and every finest numerical
  limit met. No scientific tolerance changed. Independent physics review makes
  **794,624,290 comparisons** over all 512,000 updates / 1,536,001 physical
  records. Recording checks preserve **3,923,973,134 exact scalar values**;
  observer neutrality passes **272,388,064 exact scalar comparisons**, and
  the matching 51,200-step prefix passes **392,091,251**.

  The observed and unobserved captures took **10,069.13** and **6,851.68
  seconds**; review took **41,892.37 seconds**. Native peak RSS was **11.98 GiB**
  and review peak **11.74 GiB**, within the 16-GiB allowance. Artifacts total
  **4,262,038,193 bytes**. The run's
  [input authentication](/mnt/workspaces/Cells/betse-long-pump-eighth-step-20260923-01/compare/input-check.json)
  covers **48,020 new native artifacts** and the reused parent evidence. This
  status check verifies the root registration/result hashes, all four current
  phase receipt links and their result files, **595 frozen source hashes**,
  four copied inputs and all six hashed review-result artifacts in the
  [progress log](/mnt/workspaces/Cells/betse-long-pump-eighth-step-20260923-01/compare/review-progress.jsonl).
  No current-run failure artifact or controller/review stderr exists. All
  run workers have exited; the L4 is idle and no follow-up job was launched.
  Qualification covers this **100-ms pump/leak transient and its timestep
  ladder**. Steady state, native recovery and full BETSE parity remain open.

  [Development checks](/mnt/workspaces/Cells/betse-eighth-step-development-20260923-01/development-checks.json)
  record **84 passing focused tests**, two eight-step native captures,
  **12,706 independent physics comparisons**, **8,320 observer-pair exact
  scalar comparisons** and **66,473 exact scalar comparisons** showing that
  the larger recording allowance preserves all recorded fields. Ordinary
  checkpoint round-trip checks pass. The reviewer now retains only the needed
  prefix histories after completing full-run checks, freeing the remaining
  histories before loading the short comparison row. Tests preserve all prior
  prefix comparisons and reject altered histories, raw calls and endpoints.
  A development script's temporary-directory lookup failure is preserved;
  its corrected read-only review passes without rerunning the native captures.

  The [fresh preflight](/mnt/workspaces/Cells/betse-eighth-step-development-20260923-01/resource-preflight.json)
  projects **15.70 GiB native / 15.77 GiB review peak RSS**, including **30%
  memory headroom**, and **6.30 GB of artifacts with 50% size headroom**.
  Limits are **16 GiB address space**, **2 GiB per file/stream**, **8 GiB total
  artifacts**, and **4-GiB memory/disk reserves**, rechecked before each large
  phase. Captures ran sequentially on CPUs 4 and 5; the native reference stage
  used no GPU. Estimated total duration was **14–17 hours** (registered estimate
  **59,392 seconds**). Timeouts are ten minutes for regression, six hours for
  the observed capture, three hours for the unobserved capture and 18 hours
  for review. The job freezes **595 source files** and preserves durable logs,
  progress and completion/failure artifacts. No automatic retry or subsequent
  campaign is scheduled. The completed evidence supports the bounded
  qualification above; it does not establish full BETSE parity.

- **BETSE memory and finer-prefix qualification passed at 00:53 UTC on
  23 September**, in **6,537.38 seconds (1 h 48 min 57 s)**; verified on the
  user's 23 September status request. The
  [completed result](/mnt/workspaces/Cells/betse-memory-prefix-20260922-01/result.json),
  [registration](/mnt/workspaces/Cells/betse-memory-prefix-20260922-01/registration.json)
  and [launch receipt](/mnt/workspaces/Cells/betse-memory-prefix-20260922-01/launch.json)
  bind the completed memory check before another 100-ms refinement.
  History checksum verification now uses bounded temporary buffers. An optional
  NumPy checkpoint writer avoids temporary serialization copies while keeping
  native histories and ordinary BETSE loading; the default writer is unchanged.

  **All 112 regression tests and all ten numerical constraint groups pass.**
  The observed/unobserved pair completes **51,200 steps / 10 ms / 0.1953125
  microseconds**, with **79,462,690 independent comparisons** covering every
  native update, conservation and energy accounting against three references.
  Energy closure is **4.546209e-8 pJ**, below the unchanged **1e-7 pJ** limit.
  [Recording equivalence](/mnt/workspaces/Cells/betse-memory-prefix-20260922-01/compare/prefix-writer-equivalence.json)
  reproduces the earlier qualified 25,600-step recording with **196,280,337
  exact scalar comparisons**, including every recorded field. Observer
  neutrality passes **27,242,464 exact scalar comparisons**. Ordinary checkpoint
  load/save/load checks preserve restored values and aliases.

  The **512,000-step synthetic checkpoint capacity check passes**, measuring
  **12.08 GiB peak RSS for writing** and **10.40 GiB for loading**. The 51,200-step
  independent review uses **1.21 GiB**. The largest full-run memory projection
  is **15.77 GiB including 30% headroom**, below the 16-GiB allowance. Synthetic
  storage is **not a numerical trajectory or a qualified 100-ms run**. These
  measurements and the checked prefix are inputs to the completed full
  refinement above.

  [Development evidence](/mnt/workspaces/Cells/betse-memory-development-20260922-01/development-checks.json)
  records **37 passing focused tests**, **66,473 exact scalar comparisons**
  between short old/new recordings, **12,706 independent physics comparisons**,
  exact restored object values/aliases and a small synthetic checkpoint
  write/load check. The fresh-process capture test caught and now prevents
  installing the writer before BETSE initializes its libraries. Earlier failed
  test attempts and diagnostic scripts remain preserved. The completed regression
  uses the earlier qualified production snapshot with current
  validation code; the production-reuse guard remains intact despite subsequent
  live ensemble-planning changes. This does not qualify those live production
  changes through old evidence.

  Workers ran **serially on CPUs 4 and 5**, with a **16-GiB address-space limit**,
  **2-GiB per-file / 6-GiB total artifact limits**, and **4-GiB memory and disk
  reserves** checked before each phase. Artifacts total **915,818,538 bytes**.
  This status check verifies both root receipts, **all nine phase receipts /
  6,483 linked artifacts**, **593 frozen source files**, four copied inputs and
  the parent/upstream receipt links. No failure artifact or unexpected stderr
  exists. All workers have exited and the L4 is idle; no follow-up job was
  launched. BETSE's existing default logs
  were also [preserved and redirected into the workspace](/mnt/workspaces/Cells/betse-memory-development-20260922-01/betse-log-location.json).
  The finer full run above clears the earlier 100-ms energy-closure miss.
  All scientific tolerances are unchanged; full BETSE parity remains unqualified.

- **Pump suppression/release panel passed on 22 September at 14:18 UTC;
  completion verified on the requested ETA check at 15:22 UTC.** The
  [launch receipt, PID 1189966](/mnt/workspaces/Cells/pump-recovery-20260922-01/launch.json)
  and [registration](/mnt/workspaces/Cells/pump-recovery-20260922-01/registration.json)
  freeze a **100-ms transient panel** using the authenticated seven-cell
  preparation: normal pumping, no-op switches, sustained blocking, full release
  and half-suppression/release. The completed work includes **15 independent reference
  solves and 30 ordinary Cells trajectories** across three timesteps on CPU and
  L4, with **20 saved-state restarts and eight branches** at intervention
  boundaries. Comparison retains the existing trajectory, conservation, energy
  and refinement tolerances, and checks all recorded state fields between CPU
  and GPU. This tests pump availability from the shared initial state;
  **equilibrium, complete recovery, native BETSE recovery and full BETSE parity
  remain unqualified**. The separate native refinement's completed result is
  recorded below.

  The [completed result](/mnt/workspaces/Cells/pump-recovery-20260922-01/result.json)
  passes **600,090 numerical comparisons**, CPU/L4 agreement, both successive
  refinement checks, all 20 disk restarts and eight branches. Total elapsed
  time was **425.31 seconds (7 min 5 s)**. Maximum reference differences are
  **1.3753e-14** in the retained state coordinates and **2.9258e-14 V** in voltage;
  maximum energy-accounting residual is **5.7954e-14 pJ**. This status check
  verifies the root receipts, four phase receipts, **183 linked phase artifacts**,
  **589 frozen source files** and both copied inputs. There is no failure artifact
  or unexpected stderr. The L4 is idle; no follow-up job was launched.

  [Development checks](/mnt/workspaces/Cells/pump-recovery-development-20260922-01/development-checks.json)
  record **44 distinct passing tests** and **589 matching source hashes**. The
  short CPU panel passes 15 trajectories, ten disk restarts, four branches and
  [62,370 independent comparisons](/mnt/workspaces/Cells/pump-recovery-development-20260922-01/cpu-reference-check.json).
  The [targeted L4 check](/mnt/workspaces/Cells/pump-recovery-development-20260922-01/gpu-control-probe/result.json)
  passes pump blocking/release, complete checkpoint serialization and 1,386
  independent comparisons; its largest CPU/GPU state difference is
  **2.1684e-19**. The first short GPU matrix hit its 55-second development limit
  after two completed baseline trajectories; that
  [incomplete result](/mnt/workspaces/Cells/pump-recovery-development-20260922-01/smoke/gpu/failure.json)
  is preserved. Full GPU restart/branch and 100-ms qualification subsequently
  passed in the detached panel above. An initial planner test fixture exceeded its output
  allowance; the corrected fixture passes without changing production limits.

  The new panel uses **CPUs 0–3**, checks a **2-GiB worker peak-RSS allowance**,
  sets an **8% GPU allocator fraction**, and limits artifacts to **1 GiB total /
  128 MiB per file**, retaining a 4-GiB disk reserve. Phase timeouts are five
  minutes for references, 15 minutes each for CPU and GPU, and two minutes for
  comparison. Logs and terminal completion/failure artifacts stay in the run
  directory. No automatic retry, follow-up campaign or ongoing polling is
  scheduled.

  **Offline deployment planning supports one to four JUPITER nodes, with four
  GH200s per node.** [Saved layouts](/mnt/workspaces/Cells/pump-recovery-development-20260922-01/jupiter-4-node-plan.json)
  preserve all 160 pump worlds across 40 tasks at 4, 8, 12 and 16 GPUs; tests
  also cover ionic and assembly model identities. Plans count the full allocated
  node/GPU hours, including idle GPUs and unequal finish times. With unmeasured
  task costs they explicitly omit runtime estimates. The
  [GPU ensemble guide](docs/GPU_ENSEMBLES.md) records the four-node target and
  requirements for future mechanisms. Actual multi-node execution and one
  connected tissue spanning GPUs still require implementation and qualification;
  no JUPITER jobs were submitted.

- **BETSE refinement completed at 21:10 UTC on 22 September; verified on the
  requested status check at 21:40 UTC.** The
  [completed result](/mnt/workspaces/Cells/betse-long-pump-quarter-step-20260922-01/result.json)
  passes **42 of 43 numerical constraint groups**, including all **36 Cells
  groups**, native/reference trajectories and Cells/native trajectories. The
  sole miss remains `native/energy_closure`: **1.087966e-7 pJ** against the
  unchanged **1e-7 pJ** limit, **8.80% above the allowance**. The error fell
  from **2.196858e-7 pJ**, with ratio **0.495237** and observed order **1.01381**.
  This is a completed diagnostic with a numerical miss, not acceptance.

  The three-level ladder now contains **two passing successive trajectory-error
  contractions**. The newest amount/energy/voltage ratios are
  **0.499974 / 0.499996 / 0.500129**, below the fixed 0.8 criterion. Its finest
  energy-closure result still fails, so **the timestep ladder and 100-ms native
  candidate remain unqualified**. Full BETSE parity, native recovery and steady
  state remain open. The separate CPU/L4 transient pump panel above is passed.

  The [registration](/mnt/workspaces/Cells/betse-long-pump-quarter-step-20260922-01/registration.json)
  and [launch receipt](/mnt/workspaces/Cells/betse-long-pump-quarter-step-20260922-01/launch.json)
  bind two sequential **256,000-step native captures over 100 ms at 0.390625
  microseconds**, on CPUs 4 and 5, reusing completed Cells trajectories, exact
  restart and three independent references. Both captures completed with
  unchanged native histories. Independent review performed **397,312,290
  numerical comparisons**. The
  [format check](/mnt/workspaces/Cells/betse-long-pump-quarter-step-20260922-01/compare/format-check.json)
  covers **1,961,989,134 exact scalar comparisons**; the
  [physical check](/mnt/workspaces/Cells/betse-long-pump-quarter-step-20260922-01/compare/physical-check.json)
  covers **256,000 steps / 768,001 physical records**.
  [Observer neutrality](/mnt/workspaces/Cells/betse-long-pump-quarter-step-20260922-01/compare/observer-pair.json)
  passes **256,001 common records / 136,196,064 exact scalars**; the
  [same-timestep 10-ms prefix](/mnt/workspaces/Cells/betse-long-pump-quarter-step-20260922-01/compare/prefix-check.json)
  passes **25,600 steps / 196,046,451 exact scalars**, excluding display labels.

  Total elapsed time was **36,583.18 s (10 h 9 min 43 s)**, including
  **24,805.88 s** of review. Native captures used about **10.52 GiB peak RSS**
  each; review used **11.92 GiB**. Recorded artifacts total **2.16 GB** within
  the registered 4-GiB allowance. There is no execution failure, review stderr
  is empty, and native stderr contains only the recorded disabled-cutting
  notices. This status check verifies both root receipts, all four phase
  receipts including reused Cells evidence, **24,058 linked phase artifacts**,
  **583 frozen sources**, four copied inputs, the refinement-parent receipts
  and the matching-prefix receipt. Controller and reviewer have exited; the
  L4 is idle. No follow-up job or regression was launched.

  [Development checks](/mnt/workspaces/Cells/betse-quarter-step-development-20260922-01/development-checks.json)
  retain **86 passing tests**, two short native captures and their
  [independent comparison](/mnt/workspaces/Cells/betse-quarter-step-development-20260922-01/independent-smoke.json),
  alongside the initial import-path failure. If first-order convergence
  continues, another timestep halving would project about **5.44e-8 pJ**;
  that is an extrapolation, not a measured pass. The prior
  [512,000-step feasibility check](/mnt/workspaces/Cells/betse-quarter-step-development-20260922-01/512000-step-feasibility.json)
  refuses the existing process/memory limits. A further native refinement needs
  memory work, fresh resource preflight and a matching 10-ms prefix; the
  qualification above now addresses that block. Scientific tolerances and all
  failed evidence remain unchanged; no further 100-ms run is scheduled.

- **Finer BETSE review completed on 21 September at 22:45 UTC: errors halve
  with timestep, but energy closure remains above the fixed limit. Checked
  22 September at 10:38 UTC.** The
  [completed result](/mnt/workspaces/Cells/betse-long-pump-half-step-20260921-01/result.json)
  passes **42 of 43 numerical constraint groups**, including all **36 Cells
  groups**, native/reference trajectories and Cells/native trajectories. The
  sole miss is `native/energy_closure`: **2.196858e-7 pJ**, against **1e-7 pJ**
  (**2.20 times the allowance**), down from **4.397156e-7 pJ** on the coarse run.
  The closure-error ratio is **0.499609**, giving observed order **1.00113** for
  this adjacent pair. Amount, trajectory-energy and voltage error ratios are
  **0.499990 / 0.499987 / 0.499983**; all pass the unchanged **0.8 contraction
  criterion**. This is one measured contraction, not three-level qualification.

  Both native runs completed **128,000 steps**, with unchanged histories and
  about **5.34 GiB peak RSS**. Their elapsed times were **4,537.25 s observed /
  3,203.59 s unobserved**. Independent review completed **198,656,290 numerical
  comparisons**. Its
  [format check](/mnt/workspaces/Cells/betse-long-pump-half-step-20260921-01/compare/format-check.json)
  covers **980,997,134 scalar values**, including **977,796,944 exact float64
  comparisons**. The
  [physical check](/mnt/workspaces/Cells/betse-long-pump-half-step-20260921-01/compare/physical-check.json)
  passes **128,000 steps / 384,001 physical records**, including source laws,
  material/charge accounting, stored histories and clock labels.
  [Observer neutrality](/mnt/workspaces/Cells/betse-long-pump-half-step-20260921-01/compare/observer-pair.json)
  passes **128,001 common records / 68,100,064 scalar comparisons**. The
  [matching prefix](/mnt/workspaces/Cells/betse-long-pump-half-step-20260921-01/compare/prefix-check.json)
  passes **12,800 steps / 98,024,051 exact scalar comparisons**. No execution
  failure or unexpected stderr was recorded; the energy-limit miss remains a
  scientific diagnostic, with no tolerance relaxation.

  Total wall time was **13,731.68 s (3 h 48 m 52 s)**, including **9,186.00 s**
  of independent review, with **6.01 GiB review peak RSS**. This status check
  verifies **583 frozen sources**, four copied inputs, both root receipt hashes,
  all four phase completion hashes and **12,058 linked phase artifacts**, plus
  the coarse-parent and prefix receipts. Both controller and reviewer have
  exited; no Cells job is running and the L4 is idle. No follow-up job or
  regression was launched.

  If the measured first-order scaling continues, one more halving projects
  **1.098429e-7 pJ**, still above the limit; two more project **5.492144e-8 pJ**.
  These are extrapolations requiring new runs, including resource preflight for
  larger captures/reviews. Further timestep refinement and full BETSE parity
  remain outstanding.

  The
  [registration](/mnt/workspaces/Cells/betse-long-pump-half-step-20260921-01/registration.json)
  and [launch receipt, PID 898509](/mnt/workspaces/Cells/betse-long-pump-half-step-20260921-01/launch.json)
  schedule **two native runs at 0.78125 microseconds**, half the previous step:
  **128,000 steps over 100 ms** in observed and unobserved modes, on **CPUs 4–5**.
  Capture and independent review are complete, using the
  completed Cells trajectories, exact restart and three reference solutions.
  There are **zero new Cells trajectories or reference solves**. All scientific
  protocol fields and the **1e-7 pJ energy-closure limit** are unchanged.

  [Development evidence](/mnt/workspaces/Cells/betse-half-step-development-20260921-01/development-checks.json)
  records **52 passing checks**, with no skips, plus two real eight-step native
  captures at the finer timestep. The
  [independent smoke review](/mnt/workspaces/Cells/betse-half-step-development-20260921-01/independent-smoke.json)
  passes **12,706 physical comparisons**, observer neutrality over **nine common
  records**, and **58,093 exact scalar comparisons** against the matching saved
  finer-timestep prefix. The full run binds the **12,800-step 10-ms prefix at the
  same timestep**, rather than the old coarse prefix. Tests cover exact label
  generation through 128,000 steps, capture/review clock agreement, resource
  overruns, Cells reuse and preservation of failed energy limits. Lint, formatting
  and whitespace checks pass; **583 frozen source hashes** match the tested code.

  The [resource preflight](/mnt/workspaces/Cells/betse-half-step-development-20260921-01/resource-preflight.json)
  projects **1.57 GiB total output**, **14.29 GiB concurrent native peak RSS** and
  **7.90 GiB review peak RSS**, including **50% artifact / 30% memory headroom**
  above twice the measured coarse costs. Existing **512-MiB file/stream caps**,
  **2-GiB output allowance**, **16-GiB per-process address-space cap** and
  **4-GiB disk reserve** remain; launch also checks a **4-GiB available-memory
  reserve**. BETSE still retains its histories. The runtime projection is
  **4.53 hours before timing headroom / 5.43 hours registered**: the initial estimate was
  **5–6 hours**, approximately **midnight to 01:00 UTC on 22 September**.
  Hard phase limits are **3 hours observed / 2.5 hours unobserved / 6 hours review**.

  The review retains the previous result and reports adjacent trajectory-error
  contraction and the uncorrected energy-error ratio/order. The halved timestep
  leaves energy closure above the fixed limit. Two timestep levels supply only
  one contraction; **three-level refinement and full BETSE parity remain open**.
  Durable logs, completion/failure artifacts and review phase/step progress stay
  under this run directory. No automatic retry or additional refinement is
  scheduled; the completed evidence remains preserved.

- **BETSE review completed at 17:49 UTC: all Cells checks pass, but the coarse
  native candidate misses the energy-closure limit. Checked 21 September at
  18:28 UTC.** The [completed result](/mnt/workspaces/Cells/betse-long-pump-review-20260921-01/result.json)
  passes **42 of 43 numerical constraint groups**, including all **36 Cells
  groups** across three timesteps and all three independent references, plus
  native trajectory and Cells/native trajectory comparisons. The sole miss is
  `native/energy_closure`: **4.397156e-7 pJ**, versus the unchanged **1e-7 pJ**
  limit (**4.40 times the allowance**). The 100-ms BETSE candidate at
  **1.5625 microseconds per step remains unqualified**. The review completed
  successfully as a diagnostic; it did not turn this numerical miss into a pass.

  All native source-law, material/charge, history and clock checks completed,
  with **99,328,290 independent numerical comparisons**. The
  [format check](/mnt/workspaces/Cells/betse-long-pump-review-20260921-01/compare/format-check.json)
  covers **490,501,134 scalar values**, including **488,900,944 exact float64
  comparisons**, all history digests and endpoint arrays. The
  [physics check](/mnt/workspaces/Cells/betse-long-pump-review-20260921-01/compare/physical-check.json)
  completed **64,000 steps / 192,001 physical records**, including source laws,
  conservation, stored histories and exact native clock labels.
  [Observer neutrality](/mnt/workspaces/Cells/betse-long-pump-review-20260921-01/compare/observer-pair.json)
  passes all **64,001 common records / 34,052,064 scalar comparisons**; the
  [physical prefix](/mnt/workspaces/Cells/betse-long-pump-review-20260921-01/compare/prefix-check.json)
  matches all **6,400 saved 10-ms steps / 49,012,851 scalar comparisons** exactly,
  excluding only registered display-clock labels.

  The [energy record](/mnt/workspaces/Cells/betse-long-pump-review-20260921-01/compare/native-points.json)
  has a final convex capacitor remainder of **4.392617e-7 pJ** and maximum
  residual after convex accounting of **6.000758e-10 pJ**. These diagnostics are
  consistent with a finite-timestep energy defect; refinement must test that
  inference. They do not replace the uncorrected closure criterion. The next
  numerical work is a finer native timestep and energy-error convergence check,
  retaining all existing tolerances and reusing the Cells/reference evidence.

  Total review wall time was **5,859.91 s (1 h 37 m 40 s)**, with **3.04 GiB peak
  RSS**, no execution failure and empty stderr. This status check reverified
  **583 frozen sources**, four copied inputs, both root receipt hashes, all four
  phase completion hashes, and all **6,058 linked phase artifacts** (6,048 reused
  simulation files plus 10 review files). Both controller and reviewer have
  exited; the L4 is idle. No retry, follow-up job or regression was launched.

  The [review registration](/mnt/workspaces/Cells/betse-long-pump-review-20260921-01/registration.json)
  and [launch receipt, PID 852758](/mnt/workspaces/Cells/betse-long-pump-review-20260921-01/launch.json)
  bind the saved simulations from the
  [pilot that timed out at 15:31 UTC](/mnt/workspaces/Cells/betse-long-pump-pilot-20260921-02/failure.json).
  Its review exceeded **9,000 s** without a numerical verdict; the exact phase
  reached is unknown because that attempt had no progress journal. Both
  **64,000-step native captures**, all **three Cells trajectories** and the
  **exact disk restart** remain intact. All **6,048 completed simulation artifacts**
  and the original source capsule reauthenticate. This run launches **zero new
  native simulations, Cells trajectories or reference solves**.

  The [short independent probe](/mnt/workspaces/Cells/betse-review-development-20260921-01/review-probe.json)
  identifies avoidable decoding: six separate history checks reread the complete
  trace. They now compare each stored sample during the existing physics pass,
  reducing that phase from **seven trace passes to one**. On the saved eight-step
  probe, physics review falls from **0.557 s to 0.315 s**, with identical **12,706
  comparisons**, error maxima, energy records and format coverage. This short
  probe is not a full-run speedup measurement. Prefix comparison now iterates
  the trace without materializing thousands of step records. All **70-digit
  arithmetic, physical/domain checks and scientific tolerances remain unchanged**.

  [Development checks](/mnt/workspaces/Cells/betse-review-development-20260921-01/development-checks.json)
  record **35 focused checks plus 11 compatibility checks passing**, with no
  skips, and passing lint/format/whitespace checks. Coverage includes changes to
  every linked history, missing/changed/extra evidence, comparison-only dispatch,
  prefix corruption and durable timeout/failure reporting. The **583 frozen
  source hashes** match the tested source inventory. The reviewer launched
  at **16:11 UTC on CPU 4**, with an initial **2–3-hour runtime estimate**, a **6-hour hard limit**,
  a **16-GiB address-space limit**, a **2-GiB output allowance** and a **4-GiB
  disk reserve**. Its fsynced
  [progress journal](/mnt/workspaces/Cells/betse-long-pump-review-20260921-01/compare/review-progress.jsonl)
  records phases, trace passes, step counts and peak memory; completed format,
  physics, energy, observer and prefix checks are saved separately. No automatic
  retry or follow-up job is scheduled. The **100-ms native candidate remains
  unqualified because of energy closure**; timestep refinement, stationarity,
  recovery and full BETSE parity are still outstanding.

  **GPU results, last checked at 15:52 UTC:** the five checkpoint identity checks now use a
  supported `finite_extracellular@2` model on both backends, with distinct gate
  states to check world ownership. Scalar and batch definitions are parsed before
  initialization. All **five CPU and five L4 checks pass**, with no skips;
  [development evidence](/mnt/workspaces/Cells/integrated-throughput-fixture-development-20260921-01/development-checks.json)
  includes restored GPU runtime identity, source/runtime-change rejection,
  complete scalar child restoration and corruption refusal. Focused lint,
  formatting and whitespace checks pass. Only the test fixture changed relative
  to the failed job's **313 verified frozen source files**.

  The [fresh qualification registration](/mnt/workspaces/Cells/integrated-ensemble-throughput-20260921-02/registration.json)
  launched at **13:51:45 UTC**, [PID 811706](/mnt/workspaces/Cells/integrated-ensemble-throughput-20260921-02/launch.json),
  on CPUs **0–3** and the L4. It scheduled all **12 CPU / 18 GPU checks**, then the
  registered **32,768 assembly–cell / 1,024 ionic world** profiles, with **16
  tasks per profile**. The
  [registration comparison](/mnt/workspaces/Cells/integrated-throughput-fixture-development-20260921-01/relaunch-registration-check.json)
  confirms identical profile definitions, plans and production sources. The
  [result](/mnt/workspaces/Cells/integrated-ensemble-throughput-20260921-02/result.json)
  completed at **14:08:12 UTC in 986.24 s**. All **12 CPU and 18 GPU checks pass**,
  with no skipped checks. Both profiles completed all **16 tasks**, with no
  failures or missing worlds. Earlier failed evidence remains intact.

  | Profile | Completed worlds | Wall time | Whole-job GPU busy | Warmed GPU busy |
  | --- | ---: | ---: | ---: | ---: |
  | Assembly–cell | 32,768 | 115.93 s | 2.01% | 2.72% |
  | Ionic | 1,024 | 253.90 s | 31.38%* | 37.59% |

  *Ionic whole-job telemetry covers **89.51%**, below the required **90%**; its
  utilization gate is `insufficient_telemetry`. The first sample arrives **26.62 s**
  after allocation accounting starts, and missing intervals count as zero.
  Both warmed intervals have complete telemetry coverage. Assembly–cell is
  `below_target`; **neither profile reaches the advisory 70% target**, and both
  retain `ready_for_node_pilot=false`.

  Observed throughput is **282.66 assembly–cell worlds/s** and **4.033 ionic
  worlds/s**. These are larger capacity workloads, not matched speedup estimates
  against the smaller pilot. Assembly–cell has **zero trimer material residual**;
  maximum ionic material residual is **6.94e-18 fmol** for assembly–cell and
  **1.63e-19 fmol** for ionic. Ring/open measured per-world costs differ by only
  **0.86%**, and the two assembly workers finish **0.83 s** apart.

  Checkpoint writing remains substantial: summed task compile / execution /
  checkpoint times are **65.79 / 6.82 / 73.18 s** for assembly–cell and
  **40.60 / 126.73 / 90.25 s** for ionic. These sums overlap across workers.
  Host validation/checkpoint costs and initial telemetry coverage are the next
  performance issues; no four-GPU efficiency claim follows from these local runs.
  The status check verifies **313 frozen source hashes**, the root result and
  **14 linked completion artifacts**, both profile registrations/definitions,
  and all **32 task-result and checkpoint-manifest hashes**. The L4 is idle.

  Both GPU qualification/profile runs are finished. The earlier failed attempts
  and all evidence remain saved; this BETSE rerun uses the CPU.

- **BETSE capture complete and independent comparison running; L4 capacity
  study stopped on a test-fixture error. Status checked 21 September, 13:06 UTC.** The
  [development receipt](/mnt/workspaces/Cells/integrated-throughput-development-20260921-01/development-checks.json)
  records **15 passing short checks**, focused lint/formatting and whitespace
  checks. The [resource preflight](/mnt/workspaces/Cells/integrated-throughput-development-20260921-01/preflight.json)
  checks every production grid, the restart point and both complete GPU plans.

  The pump pilot now derives execution limits from one shared registered
  definition and checks **2,000 / 4,000 / 8,000 steps before detaching**, then
  repeats the same preflight in its frozen worker. Estimated trace storage is
  **100.52 / 196.16 / 387.44 MiB**, within a **512-MiB** allowance. A regression
  check rejects the former 256-MiB limit on the finest grid. Scientific limits,
  timesteps and the 100-ms horizon are unchanged; the failed first attempt and
  its saved trajectories remain intact. The
  [fresh registration](/mnt/workspaces/Cells/betse-long-pump-pilot-20260921-02/registration.json)
  launched at **12:22:24 UTC**, [PID 786379](/mnt/workspaces/Cells/betse-long-pump-pilot-20260921-02/launch.json),
  on CPUs **4–5**, with an estimated **three-hour** runtime and the existing
  bounded phases, 2-GiB artifact allowance and 4-GiB disk reserve.

  Ionic cohort checkpoint publication now collects source/runtime identity once
  and rechecks it before publishing the enclosing manifest. Every world retains
  an ordinary complete scalar checkpoint and all state, domain and checksum
  checks. No identity cache crosses publications. Checks cover standalone child
  restoration, changed-source/runtime refusal, fresh identity on the next write,
  child corruption and the existing snapshot/mapping regression. Saved baseline
  timings confirm that JAX already reuses compiled kernels; the new profile uses
  one batch shape per model family to reduce initial compilation costs.

  The [L4 registration](/mnt/workspaces/Cells/integrated-ensemble-throughput-20260921-01/registration.json)
  launched at **12:22:50 UTC**, [PID 786464](/mnt/workspaces/Cells/integrated-ensemble-throughput-20260921-01/launch.json),
  on CPUs **0–3** and the L4. It schedules **12 CPU and 18 GPU checks** before
  two fixed profiles: **32,768 assembly–cell worlds / 16 tasks**, with equal
  ring/open arms and batches of **2,048**; and **1,024 ionic worlds / 16 tasks**,
  with batches of **64**. Assembly–cell uses a complete **200-tick window**.
  Physical rates, integration steps and the **20-ms horizon** come from the
  authenticated completed baseline. Larger samples make this a separate capacity
  study; its timings are not a matched stochastic speedup estimate.

  Both profiles use two persistent workers on one L4. Estimated per-task array
  working storage is **210.76 MB assembly–cell / 1.921 GB ionic**; conservative
  output bounds are **3.121 / 1.793 GB**. Qualification/profile runtime is
  estimated at **20–35 minutes**, capped at **one hour**. Full CPU/L4 qualification,
  utilization and throughput results are pending. **70% remains advisory**;
  Jupiter scaling remains unmeasured. Both jobs retain frozen sources, inputs,
  logs and result/failure artifacts under the linked workspace directories.
  No automatic status polling, retry or follow-up job follows this launch.

  **Requested status check:** all **three 100-ms Cells trajectories** and the
  **exact 50-ms disk restart** completed in **46.75 s**. Both native BETSE runs
  completed **64,000 steps**: observed capture took **2,287.13 s**, unobserved
  capture **1,621.46 s**, with peak RSS about **2.95 GB each**. The independent
  comparison started at **13:01:24 UTC** and was active at the status check,
  using about **1.57 GB RSS** and **97% of one CPU**. No comparison failure or
  terminal result had been written. Capture completion alone does not qualify
  the 100-ms numerical comparison. The original rough three-hour estimate points
  to about **15:20 UTC**; the reviewer has no finer progress counter.

  The [L4 job failed at 12:33:53 UTC](/mnt/workspaces/Cells/integrated-ensemble-throughput-20260921-01/failure.json),
  after **661.79 s**. All **12 CPU checks passed**; the GPU suite recorded
  **13 passes and five failures**. Every failure is in the newly added checkpoint
  identity tests: their `synthetic_pair()` uses a CPU-only model, and changing its
  backend to GPU is refused during specification validation, before the intended
  checkpoint test. The existing integrated GPU parity, checkpoint/restart,
  worker and pause/resume tests passed. This is an identified test-setup defect;
  the five intended GPU identity checks remain unqualified. The next correction
  is to use a supported ionic GPU fixture and retain every intended check.
  **Neither throughput profile started**, so there is no new utilization or
  speedup result. The L4 controller has exited and the GPU is idle.

  Status verification checked **583 BETSE / 313 integrated frozen source hashes**,
  all **6,048 completed BETSE phase artifacts**, frozen pump inputs and both GPU
  profile definitions. The active comparison and all failed evidence were left
  untouched. No source correction, rerun or follow-up benchmark was launched
  during this status check.

- **Integrated CPU/L4 qualification passed; 100-ms pump/leak pilot stopped at
  its Cells trace-storage guard. Status checked on 21 September.** The
  [development receipt](/mnt/workspaces/Cells/integrated-ensemble-development-20260921-01/development-checks.json)
  records **31 passing short checks**, focused lint/formatting and whitespace
  checks. The revised native reader also reproduces **12,706 independent
  physical comparisons and the original energy accounting exactly** on an
  eight-step saved capture. The two jobs launched at 11:08 UTC; their terminal
  results are recorded below.

  The [BETSE pilot registration](/mnt/workspaces/Cells/betse-long-pump-pilot-20260921-01/registration.json)
  freezes a **0.1-s pump/leak case**, two native observed/bare runs at
  **1.5625 us / 64,000 steps each**, three ordinary CPU Cells trajectories at
  **50/25/12.5 us**, and one complete-state disk restart at 50 ms. It reuses
  three authenticated independent DOP853/Radau reference trajectories. All
  source-law, material, charge, energy and numerical tolerances are unchanged.
  This is a **single-timestep resource/accuracy diagnostic**; native accuracy
  misses remain explicit results and cannot qualify a refinement ladder,
  recovery, stationarity or full BETSE parity.

  A retained-memory preflight projected **22.39 GB** for the original reader,
  exceeding its 16-GiB limit. The new reader reopens authenticated step/raw-call
  records and preserves every comparison while retaining histories. Its
  [preflight](/mnt/workspaces/Cells/long-pump-pilot-development-20260921-01/stream-memory-preflight.json)
  projects **3.18 GB with 2x headroom**; total long-review memory still needs
  measurement. The original preflight and development failures remain saved.
  [PID 763311](/mnt/workspaces/Cells/betse-long-pump-pilot-20260921-01/launch.json)
  uses CPUs **4–5**, with an estimated **three-hour** runtime, bounded phases,
  **2-GiB artifacts**, a **4-GiB disk reserve**, frozen sources and terminal
  result/failure artifacts. No automatic retry or follow-up is registered.

  The ensemble scheduler now supports **`ionic_ensemble@1`** and
  **`assembly_cell_ensemble@1`**, using the existing guarded ionic and coupled
  engines, complete checkpoints, stable world identities and the shared arm
  work queue. Ionic replicas are deterministic and report no assembly-event
  statistics. Added coupled timing measurements separate compilation, execution,
  transfers and checkpoint callbacks without changing the physical solver.
  The [integrated qualification registration](/mnt/workspaces/Cells/integrated-ensemble-pilot-20260921-01/registration.json)
  schedules **seven CPU and thirteen L4 checks**, including full-state parity,
  two workers, signal pause/resume and existing assembly-family regressions.
  On passing, the same registered job runs two fixed local profiles: **256
  ionic worlds / 20 tasks** and **4,096 assembly–cell worlds / 40 tasks**, with
  two workers on the L4. Batch-size arms use disjoint identities, so these are
  exploratory cost profiles rather than matched stochastic speedup estimates.

  [PID 763338](/mnt/workspaces/Cells/integrated-ensemble-pilot-20260921-01/launch.json)
  uses CPUs **0–3** and the L4, with an estimated **15–30 minutes** and a
  **one-hour cap**. Logs, parity states, qualification and profile results/failures
  are retained under the linked output directory. **70% utilization is advisory**;
  measured throughput and arm balance will guide further work. Four-GPU Jupiter
  scaling and multicell/turnover assembly coupling remain unqualified. Both jobs
  were launched detached; no automatic status polling follows this launch.

  **Requested status check:** the
  [integrated result](/mnt/workspaces/Cells/integrated-ensemble-pilot-20260921-01/result.json)
  completed at **11:20:54 UTC in 743.02 s**. All **seven CPU and thirteen L4
  checks passed**, including full-state parity, complete checkpoint restart,
  two-worker scheduling and signal pause/resume. Both profiles completed every
  task, with no failed or missing tasks. Assembly–cell completed **4,096 worlds /
  40 tasks in 86.11 s**, with zero trimer material residual; ionic completed
  **256 worlds / 20 tasks in 85.38 s**. Whole-job / warmed L4 busy percentages
  were **4.60% / 7.20% for assembly–cell** and **24.63% / 36.61% for ionic**.
  Both remain below the advisory 70% target and report `ready_for_node_pilot=false`.
  Saved timings show substantial compilation and checkpoint costs: summed
  assembly–cell task times were **129.33 s compile / 7.37 s execute / 11.17 s
  checkpoint**; ionic times were **40.52 / 25.17 / 37.27 s**. These sums overlap
  across workers and are not whole-job wall times. Larger work units, compilation
  reuse and checkpoint overhead are the next performance questions.

  The [pump pilot failure](/mnt/workspaces/Cells/betse-long-pump-pilot-20260921-01/cells/failure.json)
  occurred at **11:08:52 UTC**, after **31.06 s**. The **50-us and 25-us** Cells
  trajectories and the latter's exact restart were saved. Before the **12.5-us /
  8,000-step** trajectory, the production resource guard estimated
  **406,263,456 bytes (387.44 MiB)** against the pilot's **256-MiB** allowance.
  The previous preflight missed this finest-grid allowance mismatch. No native
  BETSE capture or independent long comparison started, so the 100-ms parity
  pilot remains incomplete. The next correction is to size the trace allowance
  from all three grids and check each before launch, retaining this failure and
  every scientific tolerance.

  Both controllers have exited and the L4 is idle. The requested status check
  verified **583 BETSE and 312 integrated frozen source hashes**, the integrated
  completion/result and **14 linked files**, both profile definitions and
  registrations, and all **60 task-result hashes**. No source fix, retry,
  regression or follow-up benchmark was launched during this status check.

- **Native dynamic-junction correspondence panel passed, 20 September;
  verified 21 September.** The
  [protocol](validation/betse/junction_native_coupled/protocol.json) runs the
  unmodified pinned BETSE FULL INIT driver with dynamic junctions and evolving
  voltage. Five cases cover one moving ion, Na/K/Cl, reversed ion order,
  disconnection and half blocking: **30 native captures / 15 observer pairs**,
  **30 CPU/L4 compatibility replays**, and **20 ordinary Cells trajectories /
  20 complete-state disk restarts**. The first four cases last **100 ms**;
  junction permeability has a declared **0.001 scaling** from the held-open
  mapping. Membranes are impermeable; pumps and membrane channels are disabled.

  The compatibility replay starts from initial conditions, retains the native
  membrane-concentration lag, and advances the stored gate once per moving ion.
  Independent continuous references use the measured native gate clock only
  for unblocked comparisons; production `finite_extracellular@3` keeps its
  physical-time law. Native repeated clocks and stored-state blocking are
  explicit model differences. Half blocking is a **3.125-ms diagnostic**, with
  **32/64/128 native steps** and shrinking response under refinement. A measured
  256-step probe found **5.3807e-12 fmol** material rounding residual; this short
  scope preserves the **2e-11 fmol** conservation limit. Long partial blocking,
  release and complete BETSE parity are not qualified by this panel.

  [Development evidence](/mnt/workspaces/Cells/betse-junction-native-coupled-development-20260920-01/development-checks.json)
  records **36 CPU checks and two L4 checks**, including 12 existing held-open
  regressions, corruption rejection, independent timestep-ladder checks, exact
  disk restart, and the complete comparison path on a saved native pair.
  CPU/GPU compatibility replay differs by at most **1.1102e-16** in the short
  network witness. Twelve resource-preflight grids fit within **150.20 MB** of
  estimated working storage. Focused lint, formatting and whitespace pass;
  no production Cells source was changed in this step.

  The [frozen panel](/mnt/workspaces/Cells/betse-junction-native-coupled-20260920-01/registration.json)
  launched at **21:39:44 UTC**,
  [PID 554722](/mnt/workspaces/Cells/betse-junction-native-coupled-20260920-01/launch.json),
  on CPUs 4–5, followed by CPU/L4 comparison. It authenticates five prerequisite
  receipts and retains sources, inputs, logs and terminal result/failure artifacts
  [under the fresh output directory](/mnt/workspaces/Cells/betse-junction-native-coupled-20260920-01).
  The registered limits are a **3,600-s native cap**,
  **1,200-s comparison cap**, **2-GiB artifact cap** and **4-GiB disk reserve**.
  GPU throughput/utilization and Jupiter scaling remain separate work.

  **Status verified at 22:14 UTC on the user's request:** all **30 native captures**
  completed at **21:54:37 UTC**, with **15 matching observed/bare pairs**. The
  comparison [failed at 21:56:44 UTC](/mnt/workspaces/Cells/betse-junction-native-coupled-20260920-01/failure.json),
  after **1,020.42 s** total, on `network_cl_k_na`, the reversed ion order, at
  the finest **24.4140625-us** step. Its CPU compatibility replay has maximum
  gate disagreement **5.59060575611e-10**, exceeding the registered **5e-10**
  limit. The cause is not established by this status check; no tolerance or
  source was changed. The saved CPU replay and native trajectory are retained.

  `single_na` and `network_nakcl` passed their complete comparisons, including
  **eight CPU/L4 production trajectories and eight exact disk restarts**.
  Reversed-order comparison stopped before its final GPU replay and production
  trajectories; disconnected and half-block comparisons were not reached.
  Native panel/row/preparation/trace hashes, all **577 frozen source files** and
  **five prerequisite receipts** verify. The controller has exited and the L4
  is idle. Full panel acceptance is **failed**. The next work is to diagnose the
  replay discrepancy and authenticate/reuse the native captures for a fresh
  comparison. No follow-up job or retry was launched during this status check.

  **Storage-rounding correction and rerun, on the user's next instruction.**
  The [diagnosis](/mnt/workspaces/Cells/betse-junction-native-coupled-replay-development-20260920-01/diagnosis.json)
  isolates the mismatch: native BETSE adds each increment to a full stored
  concentration, while the adapter accumulated small amount increments. Replaying
  saved flux with native concentration additions reproduces every recorded
  concentration exactly. Accumulated increments differ by up to **1.2790e-12 mM**,
  changing voltage and then the gate. The compatibility adapter now retains
  native initial concentrations directly and rounds each concentration increment
  before adding it, on CPU and L4. The previously failing gate error falls from
  **5.5906e-10** to **8.0781e-12**, below the unchanged **5e-10** limit.

  [Correction/reuse checks](/mnt/workspaces/Cells/betse-junction-native-coupled-replay-development-20260920-01/development-checks.json)
  pass **43 CPU checks and five L4 checks**, covering all 15 native case/grid
  combinations on CPU, all five finest-grid cases on L4, complete replay state
  and lag, unchanged physical definitions/reference equations, rejection of the
  original failure, and authenticated copying of all **30 captures / 197 files**.
  Maximum gate error is **8.2147e-12** on CPU and **8.1541e-12** on L4; maximum
  CPU/GPU disagreement is **4.4409e-16**. Production Cells, native capture,
  independent reference, protocol and tolerance sources remain unchanged.
  Focused lint, formatting and whitespace checks pass.

  The [fresh comparison-only run](/mnt/workspaces/Cells/betse-junction-native-coupled-20260920-02/registration.json)
  launched at **22:45:48 UTC**,
  [PID 573261](/mnt/workspaces/Cells/betse-junction-native-coupled-20260920-02/launch.json).
  It reuses the complete authenticated native panel and reruns all CPU/L4
  comparisons and production restarts with frozen corrected sources. The failed
  parent remains untouched. The **1,200-s comparison cap**, artifact limits,
  disk reserve, scientific protocol and numerical tolerances are unchanged.

  **Completed at 22:51:28 UTC on 20 September in 339.06 s; verified on the
  requested status check on 21 September.** The
  [result](/mnt/workspaces/Cells/betse-junction-native-coupled-20260920-02/result.json)
  passes all **five cases**, **30 CPU/L4 compatibility replays**, **20 ordinary
  Cells trajectories** and **20 exact complete-state disk restarts**. All
  **30 native captures / 15 observer pairs** were reused; no native simulation
  was repeated. Maximum native/replay gate disagreement is **8.2147e-12**, below
  the unchanged **5e-10** limit. Maximum compatibility CPU/GPU disagreement is
  **6.6614e-16**; production CPU/GPU disagreement is **1.1103e-16**. Production
  differences from independent DOP853/Radau references are at most
  **1.8819e-14 V** and **7.7705e-12** in gate state.

  Completion/result/registration hashes, **252 comparison artifacts**, **578
  frozen source files**, **197 reused native files**, **six parent receipts**
  and **five prerequisite receipts** verify. No failure artifact is present;
  both stderr logs are empty and the L4 is idle. This passes the registered
  dynamic-junction correspondence scope; native repeated gate clocks and
  stored-state blocking remain explicit model differences. Complete BETSE
  parity, long partial blocking/release, GPU throughput and Jupiter scaling
  remain unqualified. No follow-up job was launched during this status check.

- **Coupled physical-time junction model implemented; CPU/L4 panel passed,
  20 September.** The explicit `finite_extracellular@3`
  [composition](src/cells/models/junction_finite_extracellular.py) combines finite
  ion inventories, kinetic ATPase, membrane channels and
  `betse_rate_junction_relaxation@1`. All derivatives use the same RK4 stages;
  voltage follows ion charge and every junction transfer has one edge owner.
  Availability scales transport while intrinsic conductance continues evolving.
  Its [strict schema](src/cells/core/junction_finite_spec.py) and checkpoint layout
  own threshold/minimum conductance explicitly. Stage and cubic-observation
  checks enforce the gate's minimum conductance and 120-mV junction domain.
  A runnable [20-ms cluster example](configs/junction_finite_cluster.json)
  includes half blocking, full blocking and release.

  [Development evidence](/mnt/workspaces/Cells/betse-junction-coupled-development-20260920-01/development-checks.json)
  records **26 CPU checks and two L4 checks**. These include strict parsing,
  owned checkpoint parameters, blocked-state evolution, interior-domain rejection,
  exact complete-state disk restart with pump/channel/junction activity, and a
  **20-ms coupled trajectory against independent DOP853 and Radau equations**.
  Maximum CPU/reference voltage difference is **2.3722e-13 V**; saved short
  CPU/GPU trajectories differ by at most **1.1102e-16**. Four existing finite,
  kinetic and physical-graph definitions retain exactly matching fingerprints,
  initial states/layouts and initial derivatives against authenticated frozen
  preintegration sources. Focused lint, formatting and whitespace checks pass.

  The [registered one-second panel](/mnt/workspaces/Cells/betse-junction-coupled-20260920-01/registration.json)
  launched at **19:03:57 UTC**,
  [PID 512197](/mnt/workspaces/Cells/betse-junction-coupled-20260920-01/launch.json).
  Its [protocol](validation/betse/junction_coupled/protocol.json) uses the mapped
  seven-cell/twelve-edge native geometry, with an explicit **0.01 permeability
  scaling** to exercise gate/transport interaction. Single-edge, network and
  disconnected cases run at **100/50 us** on CPU and L4: **12 trajectories and
  12 disk restarts**, plus four-world heterogeneous batches, batch restart and
  partition checks on each backend. The long independent-reference cases have
  impermeable membranes and disabled pumps/channels; short batch witnesses also
  exercise active pump/channel/junction composition. This is a physical-model
  integration qualification, not a new timed native FULL-driver comparison.

  A storage preflight refused the short-test **256-MiB** allowance before any
  long simulation. The declared allowance is now **2 GiB**; all six full grids
  pass with a maximum estimated working storage of **1.444 GB**. Numerical
  parameters and tolerances are unchanged. The detached runner uses CPUs 4–5
  and the L4, with a **1,200-s comparison cap**, **2-GiB artifact cap** and
  **4-GiB free-disk reserve**. Frozen sources, inputs, logs and terminal
  [result/failure artifacts](/mnt/workspaces/Cells/betse-junction-coupled-20260920-01)
  are retained.

  **Completed at 19:07:10 UTC in 192.41 s; verified on the requested status check.**
  The [result](/mnt/workspaces/Cells/betse-junction-coupled-20260920-01/result.json)
  passes all **12 CPU/L4 trajectories and 12 exact complete-state disk restarts**.
  Maximum voltage/reference difference is **1.7273e-12 V**; maximum gate/reference
  difference is **2.0176e-9**, below **2e-8**. Maximum saved-state CPU/GPU
  disagreement is **2.2204e-16**. Both four-world batches pass pump/channel/junction
  composition and exact disk restart; partition differences are zero on CPU and
  **2.6470e-23** on L4. Completion/result/registration hashes, **133 comparison
  artifacts**, **570 frozen source files** and **four prerequisite receipts**
  verify. No failure artifact is present; the L4 is idle. No follow-up job is
  scheduled. Full timed native BETSE parity, GPU throughput, multi-GPU scaling
  and biological validation remain separate work.

- **Dynamic junction gate CPU/L4 qualification passed, 20 September.** The named
  [physical-time process](src/cells/processes/junction_gate.py),
  `betse_rate_junction_relaxation@1`, uses the pinned BETSE opening/closing rates
  with explicit intrinsic conductance and external availability. Its derivative
  advances once in physical time; its exact interval update applies only to
  held voltage. A separate
  [compatibility adapter](validation/betse/junction_gate/compatibility.py)
  reproduces native per-ion calling, class-only initialization and stored-state
  blocking. Those source behaviors are not silently made part of the physical
  law. The coupled build above uses this law with its own model identity.

  [Development checks](/mnt/workspaces/Cells/betse-junction-gate-development-20260920-01/development-checks.json)
  record **34 distinct passes**, including domain bounds, independent Decimal /
  DOP853 references, saved native primitives and prospective timestep refinement.
  The [256-gate CPU/L4 smoke run](/mnt/workspaces/Cells/betse-junction-gate-development-20260920-01/gpu-smoke/result.json)
  passes in float64 with exact gate-state disk restart and batch partitioning;
  maximum CPU/GPU disagreement is **1.1102e-16**, and maximum analytic error is
  **7.7716e-16**. Focused lint, formatting and whitespace checks pass.

  The [registered panel](/mnt/workspaces/Cells/betse-junction-gate-20260920-01/registration.json)
  launched at **18:16:23 UTC**,
  [PID 496428](/mnt/workspaces/Cells/betse-junction-gate-20260920-01/launch.json).
  Its [protocol](validation/betse/junction_gate/protocol.json) covers one second
  of clamping, half blocking, full blocking and release: **21 native routes**
  at three timesteps with one/three calls per step and six observed/bare pairs,
  plus **32,768 gates / 189 distinct parameter combinations** on CPU and L4.
  The detached runner freezes sources, authenticates the preceding junction
  receipts, and writes [logs and result/failure artifacts](/mnt/workspaces/Cells/betse-junction-gate-20260920-01).
  Native work uses CPUs 4–5 with a **300-s cap**; comparison has a **600-s cap**,
  with a **1-GiB artifact cap** and **4-GiB free-disk reserve**. This panel targets
  an isolated gate component, not coupled free-voltage behavior, production world restart,
  biological correspondence or GPU throughput. No automatic polling or follow-up
  job is scheduled.

  **First attempt failed; reference corrected on the user's next instruction.**
  The [failure](/mnt/workspaces/Cells/betse-junction-gate-20260920-01/failure.json)
  occurred at **18:16:27 UTC**, after **3.74 s**, before the large CPU/L4 checks.
  All six native captures and observed/bare pairs completed; the
  [native comparisons](/mnt/workspaces/Cells/betse-junction-gate-20260920-01/native-checks.json)
  passed with maximum adapter error **6.6613e-16** and finest clamp error
  **0.002059**, below **0.003**. The
  [reproduced reference failure](/mnt/workspaces/Cells/betse-junction-gate-development-20260920-02/ode-diagnosis.json)
  was a **7.8230e-11** dense-output error on the fastest heterogeneous route,
  exceeding the unchanged **5e-12** acceptance limit. The independent DOP853
  reference now limits steps to one eighth of the fastest relaxation time as
  well as one twentieth of each phase. Its relative/absolute tolerances,
  production gate and registered acceptance limits are unchanged.

  [Correction checks](/mnt/workspaces/Cells/betse-junction-gate-development-20260920-02/development-checks.json)
  pass **36 distinct tests**, including all 189 heterogeneous routes at 201
  sample times per phase, independent half-step refinement, and deliberate
  reference-error rejection with saved numerical diagnostics. Maximum dense
  reference error is **3.1031e-14**; the finer solve has **1.7764e-15** error.
  The fresh [frozen rerun](/mnt/workspaces/Cells/betse-junction-gate-20260920-02/registration.json)
  launched at **18:33:05 UTC**,
  [PID 501476](/mnt/workspaces/Cells/betse-junction-gate-20260920-02/launch.json),
  with the same panel and resource limits. Logs and terminal artifacts go to
  [the new output directory](/mnt/workspaces/Cells/betse-junction-gate-20260920-02).
  **Status verified at 18:34 UTC on the user's request:** the
  [completed component panel](/mnt/workspaces/Cells/betse-junction-gate-20260920-02/result.json)
  passed at **18:33:12 UTC**, after **6.53 s**. All six native captures / observed-
  bare pairs and **32,768 float64 gates on each of CPU and L4** pass. Gate-state
  disk restart and batch partitioning are exact on both devices. Maximum CPU/GPU
  disagreement is **2.2204e-16**; maximum analytic error is **1.9984e-15** on CPU
  and **1.8874e-15** on L4. The independent ODE comparison is within
  **1.3878e-14**, below the unchanged **5e-12** limit.
  Completion/result/registration hashes, all six native files, six comparison
  artifacts, **561 frozen source files** and three prerequisite receipts verify.
  Error logs are empty, no failure artifact exists, and the controller has exited.
  The L4 is idle. No follow-up job was launched during this status check.
  This isolated component result establishes neither coupled free-voltage
  behavior, GPU throughput nor full BETSE parity; the coupled build is recorded above.

- **BETSE free-voltage junction comparison passed, 20 September.** The
  [completed panel](/mnt/workspaces/Cells/betse-junction-trajectory-20260920-03/result.json)
  passes all eight cases for the registered **100-us held-open junction scope**;
  the final comparison completed at **17:40:17 UTC**. The
  [trajectory runner](validation/betse/junction_trajectory/run.py) reuses the
  existing detached launcher, pinned BETSE preparation and unmodified FULL INIT
  driver. The [protocol](validation/betse/junction_trajectory/protocol.json)
  registers **eight cases, 48 native runs / 24 observed-bare pairs, 16 production
  Cells trajectories and 16 disk-checkpoint restarts**. Cases cover one actual
  physical edge, the seven-cell network, disconnection, equal conditions,
  reversed gradients, chemical/electrical gradients and Boltzmann equilibrium.
  Na/K/Cl move through held-open junctions; membranes are impermeable, with pumps,
  channels, auxiliary chemistry and dynamic junction gating disabled. A declared
  one-time fixture sets concentration gradients and fixed protein charge. Voltage
  subsequently follows native charge accounting. This isolates conservative
  free-voltage transport before choosing a dynamic physical gate.

  The checker preserves native membrane-concentration lag and compares elapsed
  completed updates rather than interpreting native output labels as solver time.
  Independent DOP853/Radau references account for all mobile inventories,
  once-owned edge transfers and dissipated energy. The production bridge uses
  ordinary `finite_extracellular@2` definitions and the existing runner and disk
  checkpoint loader; a residual opening fraction of one makes transport
  independent of the existing generic gate. It does not qualify that gate as
  BETSE's dynamic law. No production simulator source is changed.

  The first
  [development witness failed before the time loop](/mnt/workspaces/Cells/betse-junction-trajectory-development-20260920-01/failure.json):
  the recorder requested `Phi_b` before BETSE's first voltage update created it.
  Setup recording now records the explicitly initialized fields; full observation
  starts after native voltage initialization. The
  [second witness records both native modes](/mnt/workspaces/Cells/betse-junction-trajectory-development-20260920-02/completion.json),
  with exactly matching captured final arrays/histories and initialization.
  Its [four-step mapping checks](/mnt/workspaces/Cells/betse-junction-trajectory-development-20260920-02/mapping-preflight.json)
  show maximum material residual **3.906e-14 fmol**, local transfer residual
  **2.188e-14 fmol**, and independent-reference voltage disagreement
  **6.084e-13 V**. Native 25-us stepping has **407.3 uV** trajectory error and
  **4.687e-5 pJ** energy defect, so it is not accepted.

  The [first development suite](/mnt/workspaces/Cells/betse-junction-trajectory-development-20260920-02/tests-01.xml)
  records **14 passes / one failure in 22.29 s**: production 25-us RK4 passed
  complete disk restart but missed the amount comparison limit
  (**5.167e-10 fmol** versus **2e-10 fmol**). The selected first panel retains
  the transport/initial conditions and all error limits, using **100 us** of
  physical time, native **97.65625 / 48.828125 / 24.4140625 ns** steps, and
  Cells **12.5 / 6.25 us** steps. Failed evidence is preserved.
  The [refined development suite passes all 15 checks in 15.29 s](/mnt/workspaces/Cells/betse-junction-trajectory-development-20260920-02/tests-02.xml),
  including analytic salt relaxation, equilibrium/reversal, native clock/lag/
  direction/material/charge corruption rejection, complete production mapping
  and exact disk restart. The [12.5-us production witness](/mnt/workspaces/Cells/betse-junction-trajectory-development-20260920-02/tests-02/test_production_trajectory_dis0/accuracy.json)
  has maximum voltage disagreement **9.781e-10 V**, amount disagreement
  **3.056e-11 fmol** and dissipation disagreement **3.437e-11 pJ**.

  [Development receipt and source hashes](/mnt/workspaces/Cells/betse-junction-trajectory-development-20260920-02/development-checks.json)
  retain both failed attempts. Focused lint and whitespace checks pass.
  The [full frozen panel](/mnt/workspaces/Cells/betse-junction-trajectory-20260920-01)
  was **launched at 15:53:57 UTC**,
  [PID 457489](/mnt/workspaces/Cells/betse-junction-trajectory-20260920-01/launch.json),
  on **CPUs 4–5**, with a 900-second native cap, 600-second comparison cap,
  1 GiB artifact cap and 4 GiB free-disk reserve. Its
  [registration](/mnt/workspaces/Cells/betse-junction-trajectory-20260920-01/registration.json)
  authenticates the preceding held-open and dynamic-lifecycle receipts.
  It uses no GPU. Full trajectory/refinement qualification remains pending;
  longer relaxation/recovery and dynamic-gate correspondence remain separate
  work. Existing frozen evidence and the assembly qualification are left
  untouched. No automatic follow-up or status polling is scheduled.

  **Status checked at 16:24 UTC on the user's request:** the controller
  [timed out after 900.24 s](/mnt/workspaces/Cells/betse-junction-trajectory-20260920-01/failure.json)
  at **16:08:58 UTC**. It saved **19 of 48 native runs**: all six runs each
  for `single_mixed`, `network_mixed` and `disconnected_mixed`, plus the first
  observed `network_equal` run. All **nine complete observer pairs** have
  matching saved final/history fingerprints and fixture records. The twentieth
  run was interrupted by the registered timeout; the complete native panel and
  comparison stage were not reached. No numerical exception is logged, but
  these captures do **not** establish trajectory/refinement acceptance. The
  native runtime was underestimated. Completed captures, partial setup and
  failure logs are preserved. The next implementation should resume missing
  rows into a fresh output, authenticate/reuse completed rows, and set the
  remaining runtime budget from measured capture costs without changing the
  physical protocol or error limits. No retry was launched on this status check.

  **Continuation launched at 16:39:16 UTC on the user's instruction:** the
  [resumable runner](validation/betse/junction_trajectory/resume.py) inventories
  **19 complete captures / 115 files**, verifies their native runtime, pinned
  source, preparation and trace hashes, and copies them into a fresh run. The
  interrupted twentieth row is rerun from preparation. Only orchestration code
  may differ from the parent; native physics/observation, production Cells,
  independent reference, physical protocol and tolerances must match. New rows
  record monotonic wall timings. The failed parent remains untouched.

  The [saved-data preflight](/mnt/workspaces/Cells/betse-junction-trajectory-resume-development-20260920-01/saved-native-preflight.json)
  passes the three complete cases, including all nine observer pairs, native
  refinement and material/local-transfer/energy checks against the independent
  references. Finest-step maximum voltage error is **3.693e-7 V**, amount error
  **1.152e-8 fmol**, and energy-balance residual **4.160e-8 pJ**. This preflight
  covers saved native data; the full Cells comparison remains pending.
  [All 19 resume checks pass in 0.74 s](/mnt/workspaces/Cells/betse-junction-trajectory-resume-development-20260920-01/tests-01.xml),
  including changed/missing scientific source, corrupt/partial captures, changed
  copy inputs and active-parent refusal. The
  [development receipt](/mnt/workspaces/Cells/betse-junction-trajectory-resume-development-20260920-01/development-checks.json)
  links the native environment verification and checks; focused lint and
  whitespace checks pass.

  The [fresh continuation, PID 469639](/mnt/workspaces/Cells/betse-junction-trajectory-20260920-02/launch.json),
  runs detached on CPUs 4–5: **29 new native captures**, followed by the existing
  complete 48-run / 24-pair comparison, 16 Cells trajectories and 16 disk
  restarts. Its [registration](/mnt/workspaces/Cells/betse-junction-trajectory-20260920-02/registration.json)
  records **1,428 s estimated remaining native work**, measured by step size and
  observer mode. It overrides the operational native timeout to **3,600 s**;
  the comparison cap stays **600 s**, artifact cap **1 GiB**, and free-disk
  reserve **4 GiB**. Expected total time is **25–35 minutes**. Durable native
  and comparison logs, per-row results and terminal completion/failure artifacts
  are written beneath this fresh output. Full panel qualification is pending;
  no automatic status polling or follow-up audit is scheduled.

  **Status checked at 17:02:54 UTC on the user's request:**
  [all 48 native captures are complete](/mnt/workspaces/Cells/betse-junction-trajectory-20260920-02/native/completion.json),
  finishing at **17:02:36 UTC** after about **23 min 19 s**. The 29 missing
  runs finished within the measured estimate. The panel and all result,
  preparation and observed-trace hashes verify; all **24 observed/bare pairs**
  have exactly matching final/history fingerprints and fixtures. All 19 reused
  capture inventories also match registration. The controller is now running
  the existing independent-reference / production Cells / disk-restart
  comparison. At this snapshot no complete case receipt or terminal result has
  been written, and comparison error logs are empty. Final numerical
  qualification remains pending; estimated remaining time is **5–10 minutes**
  within the registered 600-second comparison cap. The L4 is idle; this native
  reference and comparison run uses CPUs 4–5. No follow-up job was launched.

  **Status checked at 17:28:45 UTC on the user's request:** the comparison
  [stopped at 17:03:11 UTC](/mnt/workspaces/Cells/betse-junction-trajectory-20260920-02/failure.json)
  after **1,435.08 s total**, with all 48 native captures preserved. The first
  three cases (`single_mixed`, `network_mixed`, `disconnected_mixed`) passed the
  full reference/native/Cells checks, including **six production trajectories
  and six exact disk restarts**. The fourth case, `network_equal`, hit an exact
  membrane-voltage continuity assertion; the
  [comparison traceback](/mnt/workspaces/Cells/betse-junction-trajectory-20260920-02/comparison.stderr.log)
  reports a **1.0001494100754076e-25 V** difference.
  The pinned [native electroflux implementation](/mnt/workspaces/Cells/betse-v1.5.0/betse/science/sim_toolbox.py:52)
  explicitly adds `1e-25` to its voltage argument in place, even for the zero
  membrane-permeability call preceding junction observation. Read-only inspection
  confirms that every saved `network_equal` step at all three resolutions
  exactly matches the previous voltage plus that one native addition. The
  checker incorrectly expected unchanged voltage at this boundary. The next
  correction should model this exact native operation while retaining the
  physical error limits, then repeat the comparison against the saved captures;
  native simulations need not be repeated. No full acceptance receipt exists.
  The controller has exited, the L4 is idle, and no follow-up job was launched
  during this status check. Earlier remaining-time estimates no longer apply.

  **Checker corrected; comparison relaunched at 17:39:30 UTC.** The
  [voltage-boundary checker](validation/betse/junction_trajectory/check.py)
  now replays native `electroflux` additions exactly: one before the first
  junction observation, one per moving ion before concentration update, and no
  corresponding change to the separate cell-average voltage array. Physical
  tolerances, native execution, reference equations and production Cells are
  unchanged. The `--compare-from` option authenticates and copies a completed
  native panel into fresh output, records both checker source revisions, and
  executes no new BETSE simulations. Partial native resume continues to require
  matching checker sources.

  [Development checks](/mnt/workspaces/Cells/betse-junction-trajectory-offset-development-20260920-01/development-checks.json)
  cover all **24 observed voltage histories**, all three equal-case step
  resolutions, missing/doubled offsets, single-ULP corruption, and exact copying
  of all 48 native captures. The first suite records **73 passes / one import
  failure in 21.88 s**; the existing Cells mapping test lacked `PYTHONPATH=src`.
  Its [targeted rerun passes in 1.84 s](/mnt/workspaces/Cells/betse-junction-trajectory-offset-development-20260920-01/tests-02.xml),
  yielding **74 distinct passing checks**. Failed evidence is preserved; the
  production trajectory/restart test is deferred to the full detached panel.
  Focused lint, formatting and whitespace checks pass.

  [Comparison launch, PID 485949](/mnt/workspaces/Cells/betse-junction-trajectory-20260920-03/launch.json),
  [registration](/mnt/workspaces/Cells/betse-junction-trajectory-20260920-03/registration.json):
  all **eight cases / 48 saved native runs / 24 observer pairs**, followed by
  **16 Cells trajectories and 16 disk restarts**, on CPUs 4–5. Expected runtime
  is **2–5 minutes**, with the unchanged **600-second comparison cap**, **1 GiB
  artifact cap** and **4 GiB disk reserve**. Logs and terminal result/failure
  artifacts are written to the fresh run; earlier evidence remains untouched.
  **Completed successfully at 17:40:17 UTC in 46.98 s**, inspected at
  **17:51:23 UTC** on the user's status request. The
  [completion receipt](/mnt/workspaces/Cells/betse-junction-trajectory-20260920-03/completion.json)
  and [result](/mnt/workspaces/Cells/betse-junction-trajectory-20260920-03/result.json)
  verify, as do **136 comparison artifacts**, **553 registered source files**,
  all **48 native result/preparation/observed-trace chains**, and all reused
  capture inventories. All **eight cases**, **24 exact observed/bare pairs**,
  **16 Cells trajectories** and **16 exact disk restarts** pass. Numerical
  refinement, domain, material, charge, local-transfer and energy checks pass
  at their registered tolerances. Maximum finest-native voltage disagreement
  is **4.008e-7 V** (limit **2e-6 V**); maximum Cells voltage disagreement is
  **1.104e-9 V** (limit **2e-8 V**). Maximum finest-native material residual is
  **1.731e-12 fmol**, and energy-balance residual **4.775e-8 pJ**. Both error
  logs are empty; no failure artifact exists. This completes the bounded
  held-open free-voltage junction qualification. Dynamic-gate correspondence,
  longer relaxation/recovery and full BETSE parity remain separate work.
  The controller has exited and the L4 is idle. No follow-up job was launched.

- **Assembly-cell composition, dynamic junction lifecycle and persistent finite-pool
  ensembles, 20 September.** The new
  [assembly-regulated cell](src/cells/assembly_cell/kernel.py),
  `assembly_regulated_cell@1`, is available through `cells assembly-cell`.
  It composes the finite trimer/bond model with one `finite_extracellular@2`
  cell and its existing Kv1p5-derived channel. A declared cycle-presence rule
  selects channel availability; the ionic laws and intrinsic m/h kinetics are
  reused. Both component states remain on the selected device. Ionic RK4
  intervals split at each assembly event and at a fixed global grid, so an
  event's new structure controls only subsequent ionic evolution. Complete
  checkpoints contain both states, pending events, grid clock, exposure and
  component ledgers. Observations/resume require grid boundaries and the same
  source/runtime/backend. This is a one-way kinetic hypothesis with no protein
  energy law, chemical feedback, multiple-cell/shared-protein-pool coupling or
  biological validation; the [assembly guide](docs/CAPSID_ASSEMBLY.md) specifies
  the assumptions and commands.

  Coupled CPU development checks pass the independent event-split DOP853
  comparison, exact checkpoint/window/world-partition replay, and matched
  ring/open/disabled organization controls. The initial
  [development suite](/mnt/workspaces/Cells/assembly-cell-development-20260920-01/cpu.xml)
  recorded **three passes, one failure and one GPU-only skip in 229.79 s**.
  The failure was a test expecting `ValueError` when the existing ionic guard
  correctly raised `NumericalError` for a corrupted bath. The expectation is
  corrected; the failed log remains preserved. The subsequent
  [26 host/planner/checker checks pass in 2.03 s](/mnt/workspaces/Cells/assembly-cell-development-20260920-01/host.xml),
  including that corruption test. The final frozen
  [CPU/GPU qualification passes](/mnt/workspaces/Cells/assembly-cell-qualification-20260920-01/result.json),
  completing at **15:33:38 UTC in 1,175.68 s**, inspected on the user's status
  request at **16:24 UTC**. CPU records **five passes and one explicit GPU-only
  skip in 859.80 s**; the L4 environment records **six passes in 299.18 s**.
  Checks cover independent event/ODE histories and timestep refinement,
  organization/disabled controls, exact checkpoint/window/world-partition
  replay, corruption rejection, public CLI run/resume and CPU/GPU composition
  agreement. All **ten completion-linked artifact hashes** match, with no
  failure artifact and empty error logs. This qualifies the registered one-way
  cycle-dependent channel model and event/grid solver; it does not establish
  biological validity, chemical feedback, tissue behavior or high throughput.
  A [real L4 coupled smoke run](/mnt/workspaces/Cells/assembly-cell-development-20260920-01/gpu-smoke.json)
  passes for **64 worlds through 0.2 ms**, matching CPU voltage, channel transfer
  and exposure observations. Global ionic material residual is zero; maximum
  ionic-energy residual is **9.343e-16 pJ** and countercharge residual
  **1.657e-25 C**. Compilation takes **20.59 s**, execution **0.0223 s**;
  this short functional check is not a throughput qualification. The serialized
  complete smoke state and logs are retained. Focused lint, formatting and
  whitespace checks pass.

  The [native dynamic-junction preflight](/mnt/workspaces/Cells/betse-dynamic-preflight-20260920-01/check.json)
  passes **3,387 scalar comparisons**, maximum equation disagreement
  **2.221e-16**, and exact observed/unobserved driver equality. On the real
  eight-step FULL-driver fixture with Na/K/Cl and half blocking, the gate is
  called **24 times: three full-dt gate updates per outer timestep**. Native
  dynamic initialization writes class state without changing `sim.gjopen`;
  blocking scales the evolving stored gate. The instantaneous class instead
  retains `gj_min` under complete block. These source behaviors are distinct
  contracts, not production physical-time or biological equivalence. The
  [registered full panel](validation/betse/junction_dynamics/protocol.json)
  checks Na alone, Na/K/Cl and reversed ion order, each at full/half/zero block,
  with paired observed/bare drivers and separate initialization/block-release
  law probes. Existing frozen held-open evidence is unchanged.

  The ensemble scheduler now accepts `finite_bond_ensemble@1`, with model
  selection checked against every arm. Persistent GPU workers reuse kernels,
  retain complete finite-pool pause/resume state and report first passage to
  **all 20 sites and 30 bonds**, current cage counts, cage dwell and material
  totals. The old paper-model semantics remain separate. Both families pass
  the [two-worker launch/timing checks](/mnt/workspaces/Cells/assembly-cell-development-20260920-01/ensemble-gpu.xml)
  (**two checks, 8.22 s**); the new family also passes
  [signal pause and exact fresh-versus-resumed comparison](/mnt/workspaces/Cells/assembly-cell-development-20260920-01/pool-resume.xml)
  (**24.42 s**). The coupled cell family still has its own runner.

  Three bounded detached jobs were **launched at 15:13:59–15:14:01 UTC**:

  - [Dynamic BETSE panel](/mnt/workspaces/Cells/betse-dynamic-panel-20260920-01):
    [launch, PID 442046](/mnt/workspaces/Cells/betse-dynamic-panel-20260920-01/launch.json);
    18 native driver runs / nine observer pairs, plus isolated law probes;
    300-second native subprocess cap. No gate adapter is promoted automatically.
  - [Persistent finite-pool matrix](/mnt/workspaces/Cells/assembly-pool-matrix-20260920-01):
    [launch, PID 442052](/mnt/workspaces/Cells/assembly-pool-matrix-20260920-01/launch.json);
    [definition](/mnt/workspaces/Cells/assembly-pool-matrix-20260920-01.definition.json),
    12 arms / **1,572,864 worlds**, 300 simulated seconds; ring/open seeds share
    five attached and 50 free trimers, volume 5 fL and `k_on=1e7`; bond breaking
    is 1/10 per second and loop closure 100/1,000/10,000 per second. This tests
    sensitivity of the new kinetic hypothesis, without fitting the paper.
    Two persistent workers on one L4, 48 batches of 32,768 worlds, 512-event
    chunks, CPUs 0–3, advisory 70% utilization and a 900-second wall budget.
    Runtime estimates are initially unknown; shared batching preserves all
    scientific counts, and the completed cost profile will support later arm
    balancing. Conservative output bound is **8,086,618,112 bytes**, within
    the registered 8 GiB plus separate free-disk reserve.
  - [Coupled CPU/GPU qualification](/mnt/workspaces/Cells/assembly-cell-qualification-20260920-01):
    [launch, PID 442099](/mnt/workspaces/Cells/assembly-cell-qualification-20260920-01/launch.json);
    frozen code/configuration/tests, independent ODE/event/refinement comparisons,
    organization controls, exact restart/window/partition, corruption and CLI
    checks. CPUs 6–7; GPU checks wait for the matrix's terminal artifact so its
    utilization measures are attributable. The overall cap is 1,800 seconds,
    including the GPU wait. The completed qualification is recorded above.

  **Status checked at 15:20–15:21 UTC on the user's request:** the
  [dynamic BETSE panel passes](/mnt/workspaces/Cells/betse-dynamic-panel-20260920-01/result.json)
  in **94.01 s**, finishing at 15:15:33 UTC. All nine observer pairs are
  neutral and **16,587 scalar comparisons** pass, with maximum equation
  disagreement **2.221e-16**. The full panel confirms one gate advance per
  outer step with Na alone and three with either three-ion ordering. Native
  initialization can exceed unity under the registered probe parameters
  (dynamic maximum **1.063135**, instantaneous **1.005148**); this is recorded
  source behavior, not qualification of a physical production gate.
  Completion-linked registration and result hashes match.

  The [finite-pool matrix completes](/mnt/workspaces/Cells/assembly-pool-matrix-20260920-01/result.json)
  at **15:18:45 UTC**: all **48 batches / 1,572,864 worlds / 12 arms** reach
  300 simulated seconds in **286.48 s**, committing **5,869,722,635 events**.
  Every arm has **zero material residual**; there are no failed/missing tasks
  or abnormal worker exits. The completion-linked result, registration and
  all 48 task-result hashes match. Whole-job L4 busy utilization is
  **65.24%**, including startup, checkpoints and tail; after both workers warm
  it is **67.76%**. Telemetry covers **99.82%** of the full allocation, so this
  is a measured result below the advisory 70% target, not insufficient
  telemetry. Cost is **0.079578 allocated GPU-hours**, or **19.77 million
  completed worlds per allocated GPU-hour** for this workload. At `k_off=1`
  and `k_close=1000`, 78.76% of ring-seeded worlds and 49.15% of open-seeded
  worlds reach a complete cage; at `k_off=10` none do within the horizon.
  These are outcomes of the declared hypothetical kinetics, not fitted
  experimental measurements or evidence of heredity.

  Coupled qualification remains in its **CPU phase**, with one test reported
  passed, an active CPU test process, empty error logs and no terminal artifact
  at this check. Its GPU phase follows the CPU checks; the matrix prerequisite
  is now complete. No follow-up run or JUPITER submission was launched.

  **Still ahead:** choose and qualify a physical junction gate and any explicit
  native compatibility adapter; coupled/free-voltage junction trajectories;
  longer native/Cells relaxation and recovery; assembly feedback and material
  replacement assays; coupled-model multi-GPU scheduling and GH200/Arm
  qualification. No JUPITER job is submitted.

- **Finite-pool assembly and BETSE junction mapping, 20 September.** The new
  [finite-bond assembly family](src/cells/assembly_pool/spec.py),
  `finite_bond_assembly@1`, runs through `cells assembly-pool` on CPU/GPU.
  It tracks explicit bonds, a finite neutral-trimer pool and detached fragments;
  every existing bond can break, including cycle bonds, and complete cages can
  disassemble. Exact integer material balances and reaction/transfer ledgers
  accompany complete pending-event checkpoints, dwell and first-passage records.
  The paper-derived `capsid_graph@1` physics is preserved separately. Independent
  closure and whole-fragment dissolution rates are **new kinetic assumptions**;
  this is not a measured-mi3 fit, a thermodynamic model, or a heredity result.
  [Model assumptions and commands](docs/CAPSID_ASSEMBLY.md#finite-material-and-breakable-bonds)
  describe the retained root, prescribed geometry and coarse fragment treatment.

  [Frozen development-check registration](/mnt/workspaces/Cells/assembly-pool-checks-20260920-01/registration.json)
  and [receipts](/mnt/workspaces/Cells/assembly-pool-checks-20260920-01/checks.json):
  **26 CPU/checker checks pass in 10.78 s** (one explicit GPU-only check skipped),
  and **22 real L4 checks pass in 12.14 s**, with empty error logs. Checks cover
  independent scalar event histories across all four reaction classes, exact
  finite material, fragment return, pool exhaustion, nonabsorbing complete cages,
  CPU/GPU agreement, exact same-backend checkpoint/chunk/world-partition replay,
  corrupt state/checkpoints, bounded faults and public CLI run/resume. The
  production assembly sources and entrypoint match the checked frozen copy.
  Focused lint, formatting and whitespace checks pass. Initial smoke/development
  packets remain under
  [/mnt/workspaces/Cells/assembly-pool-development-20260920-01](/mnt/workspaces/Cells/assembly-pool-development-20260920-01).

  BETSE's pinned seven-cell seed contains **12 physical junctions, 24 directed
  junction faces and six boundary faces**. Partners are reciprocal; maximum
  relative partner-area difference is **2.422e-15**. The lower-index face supplies
  the once-owned Cells edge area; both native areas remain recorded and checked.
  The [three-species mixed-gradient preflight](/mnt/workspaces/Cells/betse-junction-preflight-20260920-01/check.json)
  passes native `update_gj` and one `update_all_concs` comparison against a
  70-digit Decimal constant-field oracle and the existing Cells selective-flux
  law. Maximum flux disagreement is **2.221e-16 fmol/s**, concentration update
  disagreement is **zero** in this fixture, and maximum material residual is
  **4.827e-15 fmol**. Checker tests reject changed partners, areas, flux signs and
  concentration updates. These are voltage-clamped entrypoint checks, not a
  freely evolving junction trajectory or dynamic-gate qualification.

  The [first seed probe failed during YAML loading](/mnt/workspaces/Cells/betse-junction-seed-20260920-01/failure.json),
  before simulation. Its flow-style writer was replaced with the existing
  block-style configuration convention; the
  [fresh second seed succeeds](/mnt/workspaces/Cells/betse-junction-seed-20260920-02/completion.json).
  Failed and successful evidence is preserved.

  Two bounded detached runs were **launched at 14:27:43–44 UTC**:
  [junction launch, PID 421669](/mnt/workspaces/Cells/betse-junction-panel-20260920-01/launch.json)
  and [assembly launch, PID 421678](/mnt/workspaces/Cells/assembly-pool-l4-20260920-01/launch.json).
  They comprise a **135-case native junction panel**
  (Na/K/Cl; chemical/electrical/mixed/equilibrium/equal fixtures; all/single/no
  edges; full/half/zero opening), and a **16,384-world L4 finite-pool run over
  30 simulated seconds**. The junction controller has a 300-second native cap;
  the assembly definition has a cooperative 600-second wall cap and its measuring
  controller a 660-second subprocess cap. The assembly wrapper reuses existing
  allocation-wide telemetry, includes startup/checkpoint/tail time, and reports
  useful throughput per allocated GPU-hour with an advisory 70% target.
  These new kinetics require their own timing; old-model throughput cannot be
  inherited. Run registrations and subsequent results are under
  [junction panel](/mnt/workspaces/Cells/betse-junction-panel-20260920-01) and
  [finite-pool GPU run](/mnt/workspaces/Cells/assembly-pool-l4-20260920-01).
  **Both runs completed successfully by 14:27:48 UTC**, checked on the user's
  status request at **14:45 UTC**. Twelve linked registration, result, native
  preparation/panel, telemetry and checkpoint artifacts authenticate against
  their saved digests. Neither run has a failure artifact; controller/assembly
  error logs are empty. BETSE records only its expected disabled-cut messages.

  The [full junction panel passes](/mnt/workspaces/Cells/betse-junction-panel-20260920-01/result.json)
  all **135 cases in 4.95 s**, with maximum native/Cells versus Decimal flux
  disagreement **2.221e-16 fmol/s**, **zero concentration-update disagreement**,
  maximum material residual **6.278e-15 fmol**, and minimum concentration
  **1.9356 mM**. This qualifies the held-open mapping and isolated concentration
  update for the registered fixture; dynamic gates and free-voltage trajectories
  remain unqualified.

  The [finite-pool L4 run completes](/mnt/workspaces/Cells/assembly-pool-l4-20260920-01/result.json)
  **16,384 worlds to 30 simulated seconds**, committing **693,189 events**:
  268,976 associations, 41,250 closures, 362,225 bond breaks and 20,738 fragment
  dissolutions. All **901,120 initial trimers** reconcile exactly: 883,528 free,
  17,266 attached and 326 in fragments; material residual is **zero**. No world
  formed a complete cage, and **15,545 / 16,384 (94.88%)** end at the retained
  root alone. These particular new kinetic assumptions favor disassembly;
  this is not experimental evidence or a fit to the paper.

  Whole measured GPU-job time is **3.827 s / 0.001063 allocated GPU-hours**;
  compilation takes **1.810 s**, synchronized kernel execution **0.0374 s**.
  The recorded mean busy fraction is **0.54%**, explicitly
  **insufficient telemetry** because the workload is shorter than the registered
  30-second minimum. There is no sustained-utilization or scaling qualification.
  A useful longer workload and amortized startup are needed before assessing the
  advisory 70% target for this family. At the status check both controllers have
  exited and the L4 is idle (**0% use, 0 MiB**). No follow-up run was launched.

  This finite-pool packet predates the assembly-cell and scheduler extensions
  above. Neutral trimers retain their own inventories and are never assigned
  an invented ionic valence. Native gate lifecycle and longer trajectories
  require their own evidence after this held-open panel.

- **Assembly host optimization and matched GPU benchmark, 20 September.**
  GPU utilization is now an **advisory target**, alongside scientific throughput
  per allocated GPU-hour. The matched matrix retains **70%**; a future workload
  can register a different positive target after measurement. Fresh completed
  campaigns report worlds/events per allocated GPU-hour; resumed campaigns
  leave those ratios unset until cumulative allocation cost is available.
  [GPU guide](docs/GPU_ENSEMBLES.md) records the reporting and accounting rules.

  The sampled host bottleneck was repeated graph/state validation, followed by
  compression. Host checks now group repeated graph/event questions, cache
  bounded immutable oracle answers and still validate every world's target,
  rates, clocks, inventories and observations. The internal run summary reuses
  its immediately validated state; public summary/checkpoint boundaries retain
  validation. Full checkpoints use faster lossless deflate with payload flush
  before manifest publication. Kernel equations, float64, random streams,
  event order, physical controls and numerical tolerances are unchanged.
  Reports now separate transfer, validation, summary, callback, checkpoint and
  observation costs from compilation and synchronized execution.

  On one saved **32,768-world** ring state, the same profiled validation,
  summary and checkpoint sequence falls from **3.179 s to 1.155 s (2.75×)**:
  [before](/mnt/workspaces/Cells/assembly-optimization-20260920-01/before.json),
  [after](/mnt/workspaces/Cells/assembly-optimization-20260920-01/after.json).
  Restored complete array bytes are identical, while the NPZ grows from
  **5,910,194 to 6,075,224 bytes (+2.8%)**. This is one host profile with
  profiler overhead, not a whole-GPU speedup or utilization result.
  [59 CPU/planner/CLI checks pass](/mnt/workspaces/Cells/assembly-optimization-20260920-01/cpu.xml)
  in **33.35 s**;
  [six real GPU checks pass](/mnt/workspaces/Cells/assembly-optimization-20260920-01/gpu.xml)
  in **35.42 s**, including scalar-oracle histories, saved continuation,
  partitioning, fault handling and interrupted ensemble replay;
  [five evidence-comparison checks pass](/mnt/workspaces/Cells/assembly-optimization-20260920-01/benchmark-checks.xml)
  in **1.67 s**, rejecting changed signed zero, dtype, missing state and world
  IDs while accepting different lossless compression. Error logs are empty;
  focused lint and whitespace checks pass.
  [Source-linked check receipts](/mnt/workspaces/Cells/assembly-optimization-20260920-01/checks.json)
  retain the profiles, checks and copied check sources.

  The [first paired attempt failed before simulation](/mnt/workspaces/Cells/assembly-throughput-pair-20260920-01/failure.json):
  its wrapper passed a GPU UUID to the older CLI's numeric visible-device
  selector. No baseline or candidate tasks ran. The failed packet is preserved.
  The corrected wrapper binds the registered UUID through `CUDA_VISIBLE_DEVICES`
  and passes visible index `0`; both actual CLI versions pass the
  [device-selection preflight](/mnt/workspaces/Cells/assembly-optimization-20260920-01/selector-fix/result.json),
  stopping at the intentional existing-output refusal before launching work.
  Lint and whitespace checks pass; simulation code and scientific inputs are unchanged.

  **Corrected paired throughput benchmark passed**, launched at
  **20 September 13:07:47 UTC**, with both simulations finished by **13:08:30 UTC**.
  The full benchmark and comparison took **45.74 s** on the L4 and CPUs **0–3**:
  [registration](/mnt/workspaces/Cells/assembly-throughput-pair-20260920-02/registration.json),
  [launch](/mnt/workspaces/Cells/assembly-throughput-pair-20260920-02/launch.json),
  [completion](/mnt/workspaces/Cells/assembly-throughput-pair-20260920-02/completion.json),
  [matched results](/mnt/workspaces/Cells/assembly-throughput-pair-20260920-02/result.json).
  The thin [comparison runner](validation/assembly/compare_throughput.py) ran
  the established ensemble launcher twice, sequentially, with frozen baseline
  and candidate packages, identical **27-arm / 884,736-world** definitions per
  implementation, the same GPU/CPU placement and separate initially empty
  compilation caches. All **27 task pairs / 884,736 worlds / 351,240,192 complete
  state-array bytes**, and the registered observations, match exactly. Baseline
  versus candidate elapsed time is **23.515 / 17.339 s**, yielding **1.356×**
  throughput and **26.3% less local allocated GPU time** for this workload.
  Per-implementation allocated GPU-hours are **0.006532 / 0.004816**.
  Whole-job busy-time samples are **28.54% / 29.54%**; after worker warmup,
  **36.91% / 46.95%**. Both windows are shorter than the required 30 s, so
  utilization remains **unqualified (`insufficient_telemetry`)**. These matched
  measurements replace comparison against the earlier concurrently loaded
  42-second run. This is one pair, not sustained throughput or four-GPU scaling.
  Completion/result hashes agree and error logs are empty. The L4 was idle at
  the requested **13:51 UTC** status check. No JUPITER submission was made.

  **Scientific direction:** BETSE's next gaps are matched longer native/Cells
  trajectories, all-ion stationarity and pump suppression/release, followed by
  native junction topology/transport/lifecycle correspondence. Broad parity
  also needs coupled tissue fields/barriers, more channel/transport families,
  intracellular chemistry/compartments, water/mechanics and experimental
  evaluation; the bounded 10 ms closeout does not cover those capabilities.
  The [assembly integration proposal](docs/CAPSID_ASSEMBLY.md#route-to-a-coupled-cell-model-proposed)
  connects finite neutral-protein pools and reversible structures to a named
  membrane process, with matched-material, cue-removal and turnover controls.
  Propensity changes need a qualified reaction-hazard clock; preserved event
  times from the fixed-rate model cannot simply be reused. No coupled assembly
  family, renewable-memory result or inheritance result is implemented here.

- **GPU execution, allocation efficiency and two new studies, 20 September.**
  Public `finite_extracellular@2` execution now supports GPU runs, windows,
  guarded batches and complete snapshots, retaining float64, RK4, domain and
  accounting checks. Explicit CPU selection still works in both environments;
  a missing CUDA plugin is an error for a GPU request. Other ionic schemas keep
  their existing device contracts. The new [ensemble guide](docs/GPU_ENSEMBLES.md)
  documents persistent workers, measured arm balancing, fixed scientific counts
  and world IDs, complete signal interruption/resume, portable scratch paths,
  and the prepared [one-node template](validation/ensemble/jupiter.sbatch).
  The efficiency target is **at least 70% mean use of each allocated GPU** over
  the whole job, including startup and tail. Warm-only utilization is reported
  separately. Slurm accounting starts at allocation start, counts physical GPUs
  rather than worker processes, and refuses omitted GPUs or multiple nodes.
  The first L4 matrix **missed the utilization target**; four-GPU efficiency
  remains unqualified (completed-study measurements below).

  **Verification:** [71 CPU/planner/schema/CLI checks pass](/mnt/workspaces/Cells/gpu-ensemble-checks-20260920-01/final-cpu.xml)
  in 33.61 s, with the two CUDA checks explicitly exercised in the GPU packet.
  Public L4 scalar/batch agreement, conservation, complete saved restarts and
  window equivalence pass. The final
  [two-worker and signal/resume checks pass](/mnt/workspaces/Cells/gpu-ensemble-checks-20260920-01/shutdown.xml)
  in 22.07 s, including exact final-state replay after an interrupted batch.
  [37 assembly compatibility checks pass](/mnt/workspaces/Cells/gpu-ensemble-checks-20260920-01/assembly-compat.xml)
  in 46.15 s, and the
  [real reference-worker smoke passes](/mnt/workspaces/Cells/gpu-ensemble-checks-20260920-01/final-reference.xml)
  in 4.37 s. Earlier failures remain in
  [the checks directory](/mnt/workspaces/Cells/gpu-ensemble-checks-20260920-01):
  the Wilson interval's zero-success endpoint, unwanted CUDA discovery in a
  CPU-only build, and a redundant stop signal arriving during worker teardown.
  The latter saved a valid checkpoint but correctly retained a failed process
  receipt; removing duplicate signal forwarding fixes the fresh replay.
  This is focused implementation verification, not a full historical regression.

  **BETSE reference study passed**, completed **20 September 11:58:54 UTC**
  in **189.98 s**, on CPUs **4–7**:
  [registration](/mnt/workspaces/Cells/betse-relaxation-20260920-01/registration.json),
  [launch](/mnt/workspaces/Cells/betse-relaxation-20260920-01/launch.json),
  [completion](/mnt/workspaces/Cells/betse-relaxation-20260920-01/completion.json),
  [results and reference gates](/mnt/workspaces/Cells/betse-relaxation-20260920-01/result.json).
  All **36 independent solves** pass: six controls × three solver settings
  × **0.1 and 1 s**, with explicitly larger adaptive maximum steps/work caps,
  1,001 common samples per solve, unchanged agreement/accounting tolerances,
  and residual/drift measurements for every cell and bath species. Each horizon
  passes **1,189,188** cross-solver comparisons; the largest voltage difference
  is **3.03e-13 V**. In the base pump–leak solve, the last tenth of the 1 s run
  still has maximum intracellular/bath concentration rates of
  **0.0672 / 0.0326 mM/s**, despite voltage drift of only **0.00291 mV**.
  [Per-row measurements](/mnt/workspaces/Cells/betse-relaxation-20260920-01/rows)
  scope longer relaxation; no stationary-state criterion was tested or
  qualified. This adds independent references, with **no native/Cells long
  trajectories, recovery or biological qualification**.

  **L4 assembly matrix completed**, **20 September 11:57:35 UTC**, in
  **42.22 s / 0.01173 local GPU-hours**, on CPUs **0–3** with two persistent
  workers sharing the one allocated L4:
  [definition](/mnt/workspaces/Cells/assembly-matrix-20260920-01.definition.json),
  [registration](/mnt/workspaces/Cells/assembly-matrix-20260920-01/registration.json),
  [completion](/mnt/workspaces/Cells/assembly-matrix-20260920-01/completion.json),
  [results](/mnt/workspaces/Cells/assembly-matrix-20260920-01/result.json).
  All **27 arms / 884,736 worlds** reached the **300 s** horizon, with
  **202,565,338 committed events**, zero faulted worlds and no failed/missing
  tasks or abnormal worker exits. At 17 nM and `k_off = 10 s^-1`, simulated
  shell completion is **14.9506% / 0.1434% / 0.0031%** for ring/open/single
  seeds; these are model predictions, not experimental validation.

  **Efficiency failed:** whole-job mean GPU busy time is **10.36%**, with
  **98.82% telemetry coverage**; after both workers warmed it is **12.98%**.
  Both fall below the **70%** target, so `ready_for_node_pilot` is false.
  [Telemetry](/mnt/workspaces/Cells/assembly-matrix-20260920-01/gpu-utilization.jsonl)
  and [measured arm costs](/mnt/workspaces/Cells/assembly-matrix-20260920-01/cost-profile.json)
  are retained. Task durations range **1.06–9.11 s**, including initial
  compilation; worker task-time totals are **37.71 / 38.13 s**, and their last
  tasks finish within **0.04 s**. Across both workers, summed task wall time is
  **75.84 s**, with **11.22 s compilation** and **11.86 s synchronized kernel
  execution**. The remaining time includes transfers, host checks, summaries
  and checkpoint handling; those components are not individually timed yet.
  This points to host/serialization overhead and short batches as the next
  profiling target, despite the well-matched worker tails. These overlapping
  process-time sums are not physical GPU busy time or billed GPU-hours.

  Status inspected **20 September 12:30 UTC**; both final result hashes match
  their completion receipts, both controller error logs are empty, and the L4
  is idle. No new simulations, regression/audit jobs, retries or JUPITER
  submissions were launched during this status check. Frozen source and
  evidence, including the 10 ms closeout, remain untouched.

- **CPU/GPU stochastic assembly implemented, 19 September.**
  [The assembly guide](docs/CAPSID_ASSEMBLY.md) documents `capsid_graph@1`,
  available through `cells assembly` and `python -m cells.assembly`.
  It implements the paper-described 20-site graph/Gillespie model with a
  maintained free-trimer bath, once-owned integer material transfers,
  reproducible per-world random streams, complete pending-event checkpoints,
  first-passage/dwell observations and explicit CPU/GPU placement. Presets
  compare a five-trimer ring, a five-trimer open chain and an anchored single
  trimer. Geometry and protection of closed loops are stated model assumptions;
  this is not calibrated biology, a finite bath, turnover or an ionic coupling.
  The original numerical families are unchanged; the existing CLI only adds
  dispatch to the new event family.
  [The matched check](/mnt/workspaces/Cells/assembly-smoke-20260919-02/completion.json)
  passes **3,072 CPU/GPU paired simulations** (three controls × 1,024 worlds),
  with **528,065 committed events per backend**, exact final discrete state and
  transfer counters, maximum clock/accumulated-time difference **7.1054e-15 s**,
  and exact saved GPU continuation for every world. The 30-second simulations
  use **115 nM free trimers**, `k_on = 1e7 M^-1 s^-1`, `k_off = 10 s^-1`.
  Full-shell counts are **1,019 / 235 / 176** for ring/open-chain/single controls,
  respectively, at that horizon; these are illustrative simulated results.
  The source, definitions, complete checkpoints, timing records and hashes are
  preserved in [the run directory](/mnt/workspaces/Cells/assembly-smoke-20260919-02).
  The check took **12.506 s**. Synchronized L4 kernel times are
  **0.126 / 0.148 / 0.152 s**, versus CPU **1.026 / 1.482 / 1.402 s**:
  **8.15–10.01×** on this batch size. CPU affinity was restricted to **4–5**;
  compilation, startup and file I/O are excluded from those kernel ratios.
  At 16 worlds the CPU kernel was faster; no multi-GPU or general scaling claim.
  The earlier [48-pair check](/mnt/workspaces/Cells/assembly-smoke-20260919-01/completion.json)
  and [its matching source](/mnt/workspaces/Cells/assembly-checks-20260919-01/source-smoke-01)
  remain preserved. **All 45 assembly tests pass / 29.33 s** after final
  source/runtime and artifact-budget hardening:
  [JUnit](/mnt/workspaces/Cells/assembly-checks-20260919-01/final.xml),
  [log](/mnt/workspaces/Cells/assembly-checks-20260919-01/final.stdout.log).
  Checks include 256 connected graphs per backend against an independent BFS
  oracle, full short event histories, 4,096-world waiting-time samples per
  backend, saved pending events, batch/chunk invariance, corruption/resource
  refusals, public commands, explicit GPU refusal and detached launch wiring.
  **Four existing CLI compatibility tests also pass** in
  [the earlier nine-test packet](/mnt/workspaces/Cells/assembly-checks-20260919-01/cli-01.xml).
  Lint and whitespace checks pass. This is focused development verification,
  not a full maintained regression or release promotion. Generated files are
  under `/mnt/workspaces/Cells`.
  The BETSE campaign and its frozen source/evidence were not checked or changed
  during this implementation.

- **Protein assembly paper reviewed, 19 September.** Asor et al., Nature,
  [doi:10.1038/s41586-026-10948-z](https://www.nature.com/articles/s41586-026-10948-z),
  connects weak reversible contacts, ring closure and stochastic waiting times
  to selective cage assembly. The supplement specifies a small 20-node
  Gillespie model: a candidate future CPU/GPU assembly benchmark and structural
  memory assay. Its prescribed geometry and irreversible closed-ring rule are
  explicit model assumptions; no heredity or Cells validation follows.
  [Review and concrete experiment suggestions](/mnt/workspaces/Cells/paper-reviews/s41586-026-10948-z/REVIEW.md),
  [source identities and scope](/mnt/workspaces/Cells/paper-reviews/s41586-026-10948-z/sources.json).
  No new simulations; the BETSE campaign and frozen evidence were left untouched.

- **Fresh 10 ms BETSE rerun passed; completion inspected 20 September.**
  The detached campaign finished **19 September 22:16:18 UTC**, after
  **4 h 54 min 6 s**, with status `fresh_10ms_numerical_review_pass`:
  [completion](/mnt/workspaces/Cells/ref-005e-fresh-20260919-01/completion.json),
  [final comparison](/mnt/workspaces/Cells/ref-005e-fresh-20260919-01/conclusion/comparison.json).
  All **18 independent native reviews / 235,200 updates**, **60 constraint
  groups** and **36 refinement groups** pass with no failed criteria and
  unchanged scientific tolerances. The saved Cells review independently decoded
  **24 trajectories**, checked **984 accounting states / 26,196 comparisons**,
  and verified **six checkpoint links and restart suffixes**. Six finest native
  observer pairs and six physical prefixes also pass. Accounting retains
  70-digit native and 60-digit Cells checks and exact raw clock labels.
  All **18 float64 L4 probe trajectories** pass CPU agreement and exact saved
  GPU continuation:
  [GPU results](/mnt/workspaces/Cells/ref-005e-fresh-20260919-01/gpu/gpu.json).
  This qualifies the bounded **10 ms pump–leak comparison**. Long relaxation,
  recovery, native junction topology, full BETSE parity and a public ionic GPU
  backend remain separate work; biological validation is not claimed.
  Frozen source, runtime identities and inputs are in
  [registration](/mnt/workspaces/Cells/ref-005e-fresh-20260919-01/registration.json);
  logs and approximately **1.55 GiB** of evidence remain in
  [the run directory](/mnt/workspaces/Cells/ref-005e-fresh-20260919-01).
  The status inspection matched the saved comparison and GPU-summary hashes to
  their completion receipts. No failure artifact was present. No new computation
  was launched during this status check; historical evidence is untouched.

- **Takeover on the L4 machine, 19 September.** The previous VM is shut down;
  its ignored `runs/` directory and environments are absent here. The author
  requested a fresh rerun instead of recovering the disk, allowed GPU and CPU
  execution, and directed generated files to `/mnt/workspaces`. Historical
  receipts below remain historical reports; the last clock-review outcome
  cannot be inferred from them. New code lives in
  [the fresh-run adapter](validation/betse/fresh_rerun/run.py), while environments,
  source snapshots, logs, arrays and result/failure artifacts live under
  `/mnt/workspaces/Cells`. No original simulator or frozen reviewer was edited.
  The new adapter reuses their numerical functions under a fresh registration;
  it neither invents missing receipts nor inherits old qualification.
  Python 3.13.5 and the pinned CPU/BETSE environments have been rebuilt;
  BETSE source and installed Python files match commit
  `5269a714aa2593ed2a6708c4516289977d8ae1a2`. A separate JAX 0.11.1/CUDA 13
  environment executes float64 on the **NVIDIA L4 / 23,034 MiB**. The host has
  eight logical CPUs and approximately 31 GiB RAM. Installation logs and the
  first GPU runtime receipt are in
  [bootstrap-20260919](/mnt/workspaces/Cells/bootstrap-20260919).
  The regenerated seven-cell/thirty-face baseline passes **12 native runs,
  48 observed updates and six observer pairs / 33.747 s**:
  [preparation](/mnt/workspaces/Cells/preparation-check-20260919-01/prepare/preparation.json),
  [completion](/mnt/workspaces/Cells/preparation-check-20260919-01/prepare/completion.json).
  Three checked CPU trajectories and three L4 trajectories pass at 1 ms.
  GPU–CPU full-state differences are at most **2.1684e-19**, and all three
  saved GPU restart suffixes match exactly. These are explicit device probes of
  the unchanged checked kernel, not public GPU checkpoint/backend support or a
  measured speedup. The new live native stream and
  unchanged independent decoder/70-digit physics checks pass **49,954
  comparisons** on a separate 32-update smoke:
  [smoke evidence](/mnt/workspaces/Cells/smoke-20260919-01).
  The focused harness suite passes **11 tests / 0.43 s**:
  [receipt](/mnt/workspaces/Cells/checks-20260919-03/fresh-rerun.xml).
  The initial test invocation's missing temporary-parent failure is preserved in
  [its log](/mnt/workspaces/Cells/checks-20260919-tests.stdout.log); it was a
  harness setup error, not a numerical result. The detached campaign above now
  supplies the fresh 10 ms qualification.

- **Scientific orientation.** Reviewed [Plastic Heredity v5.0](../../../PRE_PRINT_PAPER_DRAFT_V5.0.md),
  [Where Do Forms Come From? v0.11](../../../../WhereDoFormsComeFrom/MANUSCRIPT.md),
  the continuing [cellular exploration](../../preprints/ingressing-minds-v-ruliad-paper-ideas/levin-cancer-gj-exploration/README.md),
  [paper-local experiments](../../../../WhereDoFormsComeFrom/experiments/README.md),
  and selected adjacent non-AI/AI programme summaries. This is orientation,
  not an exhaustive or numerical re-audit of the wider tree. PH v5 retains v4's
  numerical results: local break-and-renewal, coherence, retention, recovery and
  renewable causal memory remain distinct endpoints. Forms v0.11 selects
  E001–E012 and cellular P12; later experiment results are separate from that
  manuscript. The later E018 failure and E019 timing result particularly motivate
  explicit reader/writer clocks and functional assays, beyond visual/state
  resemblance. Cellular P13 extends externally instructed switch-back; P14
  finds tissue correction also succeeds under sham. Those findings are not
  autonomous reproduction or biological validation of Cells. Preserve complete
  state and causal controls for acquisition, hold, replacement, rewriting and
  onward transmission. The bounded pump–leak comparison is now closed; native
  junction topology and long relaxation/recovery remain separate unfinished
  capabilities.

- **GPU/Jupiter direction.** Public GPU execution now covers the assembly family
  and `finite_extracellular@2`, including complete GPU checkpoints. The other
  ionic schemas retain their previous CPU/float64 contracts. The new
  [ensemble launcher](docs/GPU_ENSEMBLES.md) schedules independent assembly
  batches with fixed scientific counts, stable world IDs, runtime estimates,
  one or two persistent processes per GPU and full-allocation utilization.
  The target is at least **70% mean use on every allocated physical GPU**;
  warm-only numbers cannot qualify a poor full-job result. Local measurements
  precede four-GPU deployment and node-wide efficiency claims.
  Guarded cohorts use `lax.map`, and the extracellular field solver is dense.
  Useful scaling work therefore includes explicit device/runtime identity,
  measured batching while preserving domain guards, bounded output transfer,
  and eventually a qualified sparse field solve. Start with independent worlds
  per GPU; distributing one coupled tissue requires conservative same-stage
  exchange and separate verification. Existing
  [Jupiter tooling](../../preprints/ai-7-chief-adviser/jupiter/ONBOARDING.md)
  provides Slurm packing, receipts and budget accounting. Official
  [JUPITER configuration](https://apps.fz-juelich.de/jsc/hps/jupiter/configuration.html)
  specifies four **GH200** superchips, 96 GB GPU memory each and 288 Arm CPU
  cores per node. An Arm environment and measured parity are needed before
  deployment. No Jupiter job has been submitted. If the allocation is 5,000
  GPU-hours, four-GPU nodes provide 1,250 aggregate node-hours.

- The [clock-corrected review](validation/betse/pump_relaxation_clock/clock_job.py)
  launched detached **2026-09-18 15:39:19 UTC**, PID **3734150**, at
  `runs/ref-005e-clock-review-2026-09-18/review-01`. A narrow, private dependency
  adapter corrects only expected raw-label construction: divide once, multiply
  indices, force the endpoint, as in pinned NumPy `linspace`. Labels must now
  match **exact float64 bits**, including signed zero. All non-label comparisons
  pass through unchanged; no recorded values, physical elapsed clocks, simulator,
  scientific tolerance or frozen reviewer source is edited. The seven files of
  the failed review below are authenticated and bound into the new registration.
  **67 preflight checks pass / 53.03 s** (source-bound **53.390 s**, 37 inputs):
  the unchanged 50-check suite plus the exact failing record and all **6,400 saved
  labels / 12,800 physical-clock values** from that row, all **54,560 values** in
  five timestep grids at both 1 ms and 10 ms against pinned NumPy, one-ULP/signed-
  zero/endpoint corruption refusals, private dispatch and detached/source bindings.
  [Receipt](reports/ref-005e-clock-review-checks-01.xml),
  [software packet](runs/ref-005e-clock-review-2026-09-18/software-01/completion.json)
  `d70498d36657f5d85a09911fc975d544dcd80b27bd9351190489c4d2dc9f1a6f`.
  The full review remains **pending**: eighteen native rows / 235,200 updates /
  six finest observer pairs, all 24 Cells archives / six restarts and checkpoints,
  refinement and cross-engine checks; reuse the reviewed eighteen references.
  Native flux/energy accounting remains 70-digit and every-update; independent
  60-digit Cells accounting covers 984 common observations, not every accepted
  Cells step. Whole native rows are materialized: no constant-memory claim.
  [Registration](runs/ref-005e-clock-review-2026-09-18/review-01/registration.json)
  `cc866394e10b9d89c3e07d182b7b7ce3ae6535993efae4d24452dae70de22285`.
  Same CPUs 0–3, six-hour cap, 16 GiB address space, 64 MiB/file, 256 MiB artifacts
  and 1 GiB free reserve; rough **3–4 hour** runtime estimate. Durable per-row
  results and completion/failure artifacts. Launch acknowledgment only; no
  polling, automatic retry or follow-up. No new integrations, qualification
  promotion, biological, steady-state, full BETSE-parity or GPU claim.
- The [independent saved-result review](validation/betse/pump_relaxation_audit/review_job.py)
  **stopped after 81.477 s**, before completing its first native row. The retained
  [failure](runs/ref-005e-saved-review-2026-09-18/review-01/failure.json)
  (`0755a7007be4a356ca6d9c97df090136cedab4baebd15db75c71ff930d00e27a`)
  is a reviewer **raw display-label reconstruction** mismatch, not a completed
  physical/numerical rejection. At index **4,462** of the 6,400-update main-case
  row, the saved label is **0.006972964525707143 s**, while the old reconstruction
  gives **0.006972964525707141 s**: **1.73472e-18 s** exceeds its **1e-18 s** check.
  BETSE uses `linspace`, dividing once before multiplying indices; the reviewer
  multiplied before dividing. The saved label matches native operation order;
  both physical elapsed-clock values match `index * dt` at that record.
  No retry or remaining row ran automatically. Original sources, seven failure
  artifacts, the input chain and the numerical producer pass remain untouched;
  independent 10 ms qualification is still pending. The earlier **50-test /
  38.24 s** preflight missed this longer-horizon arithmetic edge case:
  [Receipt](reports/ref-005e-saved-review-checks-02.xml),
  [software packet](runs/ref-005e-saved-review-2026-09-18/software-02/completion.json)
  `3767cf279bd3d2ad1bb7adc9f50c2fe3f7f759041ec371462766a0fe1a94d297`.
  Its source capsule and the initial 46-test packet are also preserved.
- A [prospective pump-only range test](validation/betse/pump_relaxation_range/range_job.py)
  **passed at 2026-09-18 11:55:35 UTC / 512.646 s**: native **351.038 s**,
  comparison **72.844 s**, with the remainder in authentication/controller work.
  The pre-existing **1 ms** timestep range (**6.25 / 3.125 / 1.5625 µs**) also
  passes at **10 ms** for pump-only. Amount errors decrease through
  **5.62105e-11 / 3.71095e-11 / 2.49152e-11 fmol**; energy and voltage refinement
  pass. The finest observer pair matches **3,408,864 exact scalars / 6,401 records**,
  and all **2,706** native–Cells comparisons pass. Exactly three new native runs
  covered **11,200 updates**; reuse sixteen observed native rows, all 24 Cells
  trajectories, six loaded restarts and eighteen reference solves. All six
  controls now have a producer pass with **case-specific** native ranges; the
  other five retain their finer range. The original common-range campaign
  remains failed. No production, physics, tolerance or upstream-source change.
  [Comparison](runs/ref-005e-pump-range-2026-09-18/range-01/comparison.json),
  [completion](runs/ref-005e-pump-range-2026-09-18/range-01/completion.json)
  `ab812df589a62c0e6a79857ce6f50e809868c0e5c0b20098c33b7f5cea828cb4`;
  535 sealed payloads. The [27-test preflight](reports/ref-005e-pump-range-checks-01.xml)
  and source capsule remain preserved. Independent review is still required
  before case-specific 10 ms qualification; no biological or full-parity claim.
- The [saved-evidence bath diagnosis](runs/ref-005e-bath-diagnosis-2026-09-18/diagnosis-01/diagnosis.json)
  **completed at 2026-09-18 11:24:18 UTC / 194.955 s** without rerunning either
  simulator. All **44,800 updates / 4,032,000 bath float64 scalars** replay exactly.
  **80-digit Decimal accounting** separates addition, mean reduction, flux-product
  and output-conversion rounding. At the finest run's worst common-grid point
  (**1 ms, bath sodium**), the stored/reference error is **−2.06021e-10 fmol**;
  mean-reduction rounding contributes **−2.04969e-10 fmol**, per-face addition
  **−1.43416e-12 fmol**, and exact recorded-transfer/reference difference
  **+3.81932e-13 fmol**. Flux-product and output-conversion rounding are negligible
  there. Across the common grid, exact recorded-transfer/reference maxima halve:
  **1.52846e-11 / 7.64229e-12 / 3.82115e-12 fmol**. This identifies accumulated
  bath averaging as the dominant cause of the stored-amount refinement miss.
  These are diagnostic reconstructions, not corrected native trajectories or a
  changed original verdict. Cells' immutable-reference + amount-increment
  representation and all scientific tolerances remain unchanged; no qualification
  or parity promotion follows. All **ten sealed payloads** authenticate;
  [completion](runs/ref-005e-bath-diagnosis-2026-09-18/diagnosis-01/completion.json)
  `9620748cecd851edb8d3b8cbcc45a8eb30aca97031a5200998500182381350ad`.
  Worker peak RSS **175.64 MiB**, stderr empty. The
  [30-test preflight](reports/ref-005e-bath-diagnosis-checks-01.xml) and
  [source-bound software packet](runs/ref-005e-bath-diagnosis-2026-09-18/software-01/completion.json)
  remain preserved.
- The six-control **10 ms Cells–BETSE campaign completed with one numerical miss**
  at **2026-09-18 01:45:44 UTC / 8,114.120 s**: Cells **1,107.014 s**, native
  **5,616.805 s**, comparison **1,352.823 s**. All **24 Cells trajectories / six
  loaded 5 ms restarts / 81,300 Cells comparisons** pass; all six finest native
  absolute-accuracy checks, observer pairs and cross-engine comparisons pass.
  Five controls pass fully. **Pump-only amount refinement fails**:
  **2.49152e-11 / 5.67669e-11 / 2.06021e-10 fmol** at
  **1.5625 / 0.78125 / 0.390625 µs**, against the unchanged floor-aware contraction
  rule (floor **5e-11 fmol**, maximum ratio **0.8**). Energy and voltage refinement
  pass. No crash or weakened criterion; preserve all coarse and fine results.
  [Comparison](runs/ref-005e-matched-10ms-2026-09-17/campaign-01/comparison.json),
  [completion](runs/ref-005e-matched-10ms-2026-09-17/campaign-01/completion.json)
  (`b1370c34ba9875b2f3d2a52b90803773552cef9eea0169e01a262723c0573cfc`);
  all **18,385 sealed payloads** authenticate. Registration
  `4d62da1d279ecdc9b51ce06653e151e51e344dbe2ec0f93be5f892aad9293567`;
  [39-test preflight](reports/ref-005e-matched-10ms-checks-02.xml) and earlier
  32-test packet remain preserved. Eighteen reviewed reference solves and the
  pump+leak ladder were reused; twenty new native runs cover the other five controls.
  Native observer neutrality was checked at **six finest steps**, not at
  every new coarse step. Full 10 ms qualification and independent review remain
  pending; no biological, steady-state, GPU or full BETSE-parity claim follows.
- The [10 ms main-case native refinement](reports/REF005E_NATIVE_PROBE.md)
  **passed**, finishing **22:48:57 UTC / 2,556.711 s**. At **0.390625 µs**, energy
  closure is **9.10423e-8 pJ**, below the unchanged **1e-7 pJ** limit; all
  **2,306,707 finest-row comparisons pass**. Amount, energy and voltage errors
  contract by approximately one half per timestep halving. The observer pair
  matches **13,623,264 exact scalars**; the same-step physical 1 ms prefix matches
  **19,606,131**, excluding only horizon-dependent raw labels. All **3,403 sealed
  payloads** authenticate. [Results](runs/ref-005e-finer-native-2026-09-17/refinement-01/comparison.json),
  [completion](runs/ref-005e-finer-native-2026-09-17/refinement-01/completion.json)
  (`c27ad36b6f9496c1622cbea64f3ee1dc4ed5b20143407b2234b219ee8472854d`).
  Coarser numerical misses remain preserved. Comparison peak RSS is **8.40 GiB**;
  neither native retained histories nor offline one-row reconstruction is a
  constant-memory claim. This result alone does not qualify all six controls or
  Cells at 10 ms.
- D130 [closes the 1 ms live recording/window milestone](reports/REF005D_LIVE_CLOSEOUT.md).
  D129's independent review passed in **128.769 s**, finishing at **17:20:12 UTC**:
  **54,685,116 exact native comparisons**, eighteen observer pairs, and all
  registered saved Cells outputs/expected window receipts pass. Direct saved
  Cells evidence spans **14,028 arrays / 284,103 values**, including the separate
  probe. All **66 sealed payloads / 70 regular files / 21 reviewer inputs** and
  the full accepted/failure-preserving prerequisite chain authenticate.
  Completion: `769994fac30ba99e64bc5c3f998c49e9d1c747c3a2e9bbeb5fadd2c57febb647`.
  Unsaved windows remain receipt-based evidence; no native bounded-memory,
  longer-horizon, biological, full BETSE-parity or GPU claim follows.
  The next [R1-S0 reference-only study](reports/REF005E_REFERENCE_SCOPE_HANDOFF.md)
  prepares the **10 ms** extension: six existing preparations × three unchanged
  adaptive settings, 1,601 samples per solve, old-prefix agreement and sampled
  domain/accounting checks. No native/Cells run or selected native step ladder.
  **73 source-bound preflight checks pass / 17.83 s**, including two real 10 ms
  reference smokes. Formal R0 closeout completed at **18:25:18 UTC**; its receipt
  is `76fa3ab1706653530a5a3b5b234c2aaa5ff3193151024473d9b86872c14ed73d`.
  The study [launched detached](reports/REF005E_REFERENCE_SCOPE_LAUNCH.md) at
  **18:25:49 UTC**, PID **3514599**, under
  `runs/ref-005e-reference-scope-2026-09-17/scope-01`; registration
  `3a41f3bb4e51ab73c6894b810cd263a155c0476f85493aea7155fd47371892b2`.
  CPUs 0–3, 300 s worker / 600 s controller, 4 GiB worker address space,
  8 MiB per new file / 128 MiB new artifacts / 1 GiB free reserve. Launch
  acknowledgment only; no worker polling, automatic retry or follow-up campaign.
  The reference study subsequently **passed all eighteen solves in 53.065 s**,
  finishing **18:26:43 UTC**: solver/prefix agreement and registered domain/
  accounting checks pass. Its 24 sealed payloads authenticate; worker peak RSS
  is **202.11 MiB**. Completion:
  `3a7710f88c309b16c2cca9739282801fc2b3b9bad8bf61253add4c816404d29c`.
  This is reference success, not matched 10 ms or biological qualification;
  the focused saved-data review is part of the separately authorized probe above.
  [Junction and biological readiness](docs/BETSE_NEXT_GATES.md) stays explicit:
  record native reciprocal topology before choosing edges; review original
  methods/uncertainty before selecting experimental parameters or targets.
- D128's actual probe and full matrix **passed**, completing at **16:36:33 UTC**
  in **553.910 s** (36.037 s probe / 500.927 s matrix). The following is the
  historical D129 launch account; its completed review is recorded above.
  All 516 sealed payloads,
  520 regular files and 680 frozen inputs authenticate. The matrix covers
  24 baselines, 72 windows, eighteen disk recordings, six full/window restart
  pairs, six zero-length and two sparse controls; the probe is additional.
  Completion: `bb6448d1be688c1b3613e8580c3e365cc75a6a794fb6bab22f7fffa4612bf2c1`.
  This is producer acceptance, not yet independent live closure.
  D129 [launches the separate saved-evidence review](reports/REF005D_LIVE_AUDIT_LAUNCH.md):
  all 36 native streams against original JSON, eighteen observer pairs, direct
  saved Cells array/checkpoint checks and independently reconstructed expected
  receipts for unsaved window/restart/zero-length/sparse paths. Those last checks
  are receipt-based, not direct inspection of unsaved trajectories. Neither
  simulator runs; both earlier failed attempts and all production code stay
  unchanged. **97 preflight checks pass / 15.33 s**; source-bound execution
  **15.795 s**, with 21 reviewer/helper inputs and 285 sealed software files.
  Preserve both earlier software failures and their source capsules.
  Software completion: `66d8a0e4f7002171632adf3360929324af70d085859cbab8afaa1bc312005b92`.
  Launched detached **2026-09-17 17:18:03 UTC**, PID **3503584**, at
  `runs/ref-005d-live-audit-2026-09-17/audit-01`; registration
  `4b8cb8f0e4eb919c4930b40f2b7b8702ab8fd2bc96e45e39de6ca9d23da0eb55`.
  CPUs 0–3, 900 s, 4 GiB address space, 8 MiB per new file, 64 MiB new artifacts,
  1 GiB free reserve. Launch acknowledgment only; full independent verdict remains
  pending. No worker polling, automatic retry or longer-duration campaign.
- D128 fixes output ownership in a [separately registered shared-worker qualification](reports/REF005D_OUTPUT_LAYOUT_LAUNCH.md).
  The following is its historical launch account; its completed result is above.
  D127 stopped after **79.799 s**: native reuse authenticated and one Cells case
  passed all three windows, then baseline and full-window recording collided
  at the same `full/` path. Production correctly refused to overwrite it.
  Both earlier failed attempts and their source contexts remain unchanged;
  no partial Cells result is promoted or reused.
  New leaves are `baseline/`, `recordings/{full,observations,checkpoints}/` and
  `resumed/`. Check all case paths before computation and baseline hashes after
  recording. Reuse frozen D125 numerical checkers and ordinary public APIs;
  no solver, physics, timestep, duration, production or tolerance edit.
  **51 fast tests pass / 2.91 s**, with **3.402 s** source-bound execution and
  **680 frozen inputs**. The tests exercise the actual worker's filesystem
  sequence with explicitly stubbed physics; they are not numerical evidence.
  The first fast attempt remains **50 passes / one test-fixture failure**;
  isolate that test's phase directory without weakening symlink guards.
  Software completion:
  `c9018d72281e4e4d01126fa0f0236a101765535b815d9250206f8f4d1347733b`.
  One detached job first runs **one actual pump+leak / 25 µs compiled / 1 ms
  probe** through the same worker, including baseline writing, all three
  windows/disk policies and loaded full/window restart/zero-length checks.
  Only a complete, hash-bound passing probe permits the original **24-case /
  72-window / eighteen-recording** matrix with all six full/window restart
  suffixes, six zero-length and two sparse controls. Probe and matrix outputs
  stay separate; matrix cases run afresh. The **36 native runs/eighteen pairs**
  are reused after frozen hash-chain checks, not recomputed or re-audited.
  Bind all **964 native / 24 stopped-continuation files**; preserve both failures.
  CPUs 0–3, one BLAS thread, **120 s probe / 750 s matrix / 1,800 s total /
  16 GiB worker address space / 32 MiB per file / 512 MiB whole-job artifacts**,
  plus 1 GiB disk reserve. No polling, automatic retry or follow-up campaign.
  Actual probe/full-matrix acceptance and independent live review remain pending.
  Launched **2026-09-17 16:27:19 UTC**, PID **3493368**, at
  `runs/ref-005d-output-layout-2026-09-17/qualification-01`; registration SHA-256
  `1cd7694949963f6f8d80bb222b78c5a039eb4a8425c1d20b5674dd35d72d8b33`.
  The launcher authenticated both preserved packets, prerequisites and the
  passing source-bound receipt, froze 680 inputs and returned successfully.
  No worker status/completion poll or automatic follow-up was performed.
- D127 corrects the launch-specific notice classification in a
  [separately registered Cells-only continuation](reports/REF005D_LIVE_CONTINUATION_LAUNCH.md).
  This is the historical launch account; D128 above records its output-path
  failure and the separately authorized shared-worker correction.
  D126 stopped after **577.531 s**: all **36 native exact overlaps / eighteen
  observer pairs** reported success, then the controller rejected 72 known
  notices solely because their script prefix was `[live_job.py]`, not `[betse]`.
  Cells had not started. Preserve the original failure and frozen sources.
  The new adapter authenticates all **964 saved files / 58,017,037 bytes**,
  original 668 inputs/capsule, comparison/capture links and all compressed
  stream hashes before reusing the completed native work. No new native run or
  numerical re-audit. **54 new regression checks pass / 6.41 s**, with **7.273 s**
  source-bound software execution, including the installed script-launched
  formatter, actual saved notice regression, corruption/coverage refusals and
  Cells-only dispatch/process-group cleanup. All **674 current source inputs**
  match that receipt; original 79-test implementation remains unchanged.
  Software completion:
  `98bbe5d26b6d16c06aa1f245d0edc5a50b453ececec5d0dfa6e92326c006ba14`.
  Continue only the outstanding **24 Cells baselines / 72 window comparisons /
  eighteen disk outputs / six full and six window restarts / six zero-length /
  two sparse-observation controls**. Same 1 ms, physics, timesteps and thresholds;
  CPUs 0–3, 750 s Cells / 1,800 s total, 16 GiB Cells address space, 32 MiB/file,
  512 MiB new artifacts and 1 GiB free-space reserve. One detached launch,
  no polling, automatic retry or follow-up. Producer acceptance and independent
  live review remain pending; native histories are still not constant-memory.
  Launched **2026-09-17 15:39:10 UTC**, PID **3483482**, at
  `runs/ref-005d-live-continuation-2026-09-17/continuation-01`; registration SHA-256
  `0c06e8390acf07e0fbea47ebd2dd9a5d9dfbb63986f6534838d38fdcc735604b`.
  The launcher authenticated prerequisites, sealed the tested 674-input context
  and complete native reuse inventory, and returned successfully. No worker
  status/completion poll or automatic follow-up was performed.
- D126 closes the passed preflight and proceeds to the
  [full same-1 ms live/window qualification](reports/REF005D_LIVE_QUALIFICATION_LAUNCH.md).
  This is the historical launch account; D127 above records its logging-gate
  failure and separately authorized continuation without native recomputation.
  D125's detached preflight finished **2026-09-17 14:36:43.757 UTC / 77.511 s**;
  **79 tests pass / 54.27 s**, including both exact live native modes and actual
  Cells window/disk-policy/restart/zero-length/sparse-observation checks.
  All **235 sealed payloads / 239 regular files / 26 internal aliases / 668
  frozen source inputs**, the capsule and passing receipt authenticate.
  Completion: `b0ba23dc666ef5a4a328bb9be0f55bd009bb86cf14eb2893a7d2d790e168a224`.
  The campaign reuses exactly that tested implementation: **36 native runs /
  eighteen observer pairs / 24 Cells full runs / 72 window comparisons /
  eighteen disk-policy outputs / six loaded full and windowed restart suffixes**,
  plus zero-length and sparse-schedule controls. No production, physics,
  timestep, duration or tolerance edit; all earlier failures remain preserved.
  Unchanged limits: CPUs 0–3, **1,800 s total / 900 s native / 750 s Cells /
  32 MiB per file / 512 MiB aggregate / 8 and 16 GiB worker address space**,
  with 1 GiB free-disk reserve. Detach once, no polling or automatic follow-up.
  Native retained histories remain unbounded in duration; successful producer
  qualification still needs independent review before longer-horizon work.
  Launched **2026-09-17 15:07:05 UTC**, PID **3466859**, at
  `runs/ref-005d-live-recording-2026-09-17/qualification-01`; registration SHA-256
  `3eb0443fb6818e6fca6155315e74edbf3c0e16c2713bad6d5686853bca075665`.
  The launcher authenticated prerequisites, froze the unchanged 668-input
  context and passing receipt, and returned successfully. No worker status or
  completion polling was performed; full-matrix acceptance is pending.
- D125 [closes the offline recording gate](reports/REF005D_CODEC_CLOSEOUT.md)
  and implements [live recording / matched Cells windows](reports/REF005D_LIVE_HANDOFF.md).
  This is the historical implementation/launch account; D126 above records its
  passed preflight and separately authorized full-campaign step.
  D124 finished **2026-09-17 13:20:14.534 UTC / 191.565 s**: all **36 rows /
  54,685,116 exact scalar comparisons / zero failures**, including 54,512,738
  float64 bit comparisons and 708,120 negative zeros. All forty review payloads,
  fourteen frozen inputs/capsule members and the 133-test receipt authenticate.
  Offline evidence is **83.558× smaller**, without losing original values.
  Review completion: `b7cc5472783236f12ccec4e658374ba83c28dba11851543a4ebdca81e3fc883f`.
  The new adapter emits one pending update at a time; native histories/time
  arrays/pickles remain untouched, so **native process memory is not bounded**.
  Full-observer/storage-only runs must match all 36 accepted rows exactly.
  Cells uses its ordinary public full/window/checkpoint APIs: 24 full trajectories,
  72 window comparisons, eighteen disk-policy outputs, six loaded full/window
  restart suffixes, six zero-length continuations and two sparse schedule controls.
  Same 1 ms, geometry, chemistry, timesteps and scientific limits; no production
  edit or reference rerun. **76 fast checks pass / 5.55 s**, with three real
  smokes deselected. Both real native modes already match accepted 160-update
  rows exactly; a narrower real Cells window/restart smoke also passes. The
  expanded full preflight retains **75 passes / one 45-second Cells timeout**,
  not a numerical mismatch or accepted matrix. All receipts/partial evidence
  are preserved. Only that software-smoke cap changes to 120 s; a separate
  **79-test detached preflight** has 300 s overall / 240 s pytest / 256 MiB total /
  32 MiB per file, CPUs 0–3 and no automatic full campaign. The 36-row native /
  matched Cells campaign is implemented but **not launched**; it waits for the
  source-bound passing preflight and the user's next instruction.
  Preflight launched **2026-09-17 14:35:26 UTC**, PID **3460250**, at
  `runs/ref-005d-live-preflight-2026-09-17/detached-01`; registration SHA-256
  `1bc4ac469027156de3d84cbf1bd03cc7b259e9b44ab449795e5f894b467a5431`.
  The launcher authenticated the complete prior chain, froze its new source
  context and returned successfully. No worker completion/status polling was
  performed. Expected software receipt: `reports/ref-005d-live-checks-03.xml`;
  its passing status is not assumed at launch.
  Independent live review, broader release, 10 ms, biology and GPU remain separate.
- D124 launches the [independent offline codec review](reports/REF005D_CODEC_AUDIT_HANDOFF.md).
  This is the historical launch account; D125 above records independent closure.
  D123 finished **2026-09-17 12:27:44.797 UTC / 215.987 s**, with **36/36**
  original canonical rows reconstructed exactly. All 778 sealed payloads,
  fourteen source/helper/contract inputs, software/probe receipts and prior
  numerical evidence authenticate. Native JSON shrank from **1,509,951,698 to
  18,070,684 bytes**: **83.558× smaller / 98.803% saved**. Largest compressed
  file: 45,886 bytes; encoded chunk peak: 1,088,005 bytes. Converter RSS peaked
  at 548.68 MiB including complete legacy/decoded trees; no live-memory claim.
  Completion SHA-256:
  `9e5ea291c711deb6edbd6c674c8a7aaff033b932f4c8ef9388db40a4637fe379`.
  **133 review checks pass / 52.34 s**, including all twelve actual coarse
  controls/modes and a complete finest 640-update pump+leak row. The new decoder
  imports no producer codec/partitioner or simulator. It compares every original
  value/type/float64 bit directly, checks complete field/primitive coverage,
  and recomputes history/endpoint byte digests. Corruption, omitted fields,
  signed-zero changes, GC-disabled release and controller failures are tested.
  One detached review targets **36 rows / 6,720 observed updates / 13,404
  history samples / 20,196 records**. CPUs 0–3, **600 s / 4 GiB address space /
  4 MiB per output file / 32 MiB review artifacts**; 1 GiB free-disk reserve.
  No solver or physical-law rerun, production change, tolerance change, polling,
  automatic retry or follow-up. A passing review would close only the offline
  codec sub-gate: live recording, matched Cells windows/restarts and 10 ms remain.
  Launched **2026-09-17 13:17:02 UTC**, PID **3442589**, at
  `runs/ref-005d-codec-audit-2026-09-17/audit-01`; registration SHA-256
  `e6c8a6c884aa243db1b554448048b702b9c31f746add10d1c384a803948a03f3`.
  The launcher authenticated the completed packet and prior chain, froze
  **fourteen review/helper/contract inputs**, the passing 133-test receipt and
  all 782 capture files, and returned successfully. No worker status/completion
  polling or automatic follow-up was performed; independent closure is pending.
- D123 implements the [lossless native record layer](validation/betse/native_recording/README.md)
  and launches its [offline qualification](reports/REF005D_CODEC_HANDOFF.md).
  This is the historical launch account; D124 above records its producer result.
  **132 checks pass / 3.51 s**: all twelve saved short controls, exact float64/
  signed-zero handling, corrupt/incomplete/order/schema refusals, output quotas,
  detached controller/failure paths and buffer release with cyclic GC disabled.
  The final largest-row probe reconstructs **143,185,735 bytes** from
  **1,549,225 bytes** exactly: **92.424× smaller**. Peak encoded chunk is
  **1,087,999 bytes**; full offline load/write/decode/canonical comparison takes
  **38.519 s**, with **504.82 MiB** high-water RSS. That RSS includes old JSON
  and a full decoded tree, not bounded live BETSE memory or a simulator speedup.
  The full matrix targets all **36 saved rows / 6,720 observed updates /
  20,196 stream records**, with source-bound whole-row canonical comparisons.
  Caps: CPUs 0–3, **900 s / 4 GiB address space / 16 MiB per file / 32 MiB per
  stream / 512 MiB total**, with a 1 GiB free-disk reserve. New adapter/schema;
  no production/frozen-producer edit, simulator rerun or tolerance change.
  Offline completion/review, live observer neutrality, matched Cells window/
  restart checks and a separately scoped 10 ms run remain distinct gates.
  Long work is detached and user-polled; no automatic review, retry or follow-up.
  Launched **2026-09-17 12:24:08 UTC**, PID **3430589**, at
  `runs/ref-005d-offline-codec-2026-09-17/qualification-01`; registration SHA-256
  `092cd7db7dc3dd9d7d1378607a67ecf16687b249bdded1765eaeceef75529847`.
  The launcher authenticated the closed evidence and returned successfully;
  **fourteen source/helper/contract files**, the passing software receipt and
  final source-bound probe are frozen. No completion/status polling was
  performed and no full-matrix or live qualification is claimed at launch.
- D122 adds the [longer-duration pump plan](docs/BETSE_PUMP_RELAXATION_PLAN.md)
  and its explicitly non-runnable machine-readable proposal. **35 design/evidence
  checks pass / 7.25 s**; a bounded saved-data planning receipt authenticates
  the closed pilot without another simulation or independent-audit rerun.
  Next implementation is an offline lossless native-record codec and bounded
  sink, then live same-1 ms observer parity and matched Cells window/restart
  qualification. A separately registered **10 ms** candidate follows: 36 native
  / 24 Cells / 18 reference trajectories, six restarts and 41 common observations.
  Candidate grids and original scientific budgets are explicit, not prequalified
  at the longer horizon. Legacy recording projects to roughly **14.74 GiB** at
  10 ms; new runtime/artifact caps require measurements. Later steady-state and
  perturbation criteria, original-data work and GPU remain separate gates.
  **No long run, solver change, production edit or automatic follow-up launched.**
  Planning receipt: `runs/ref-005d-planning-2026-09-17/design-01`; completion
  SHA-256 `db57a5c3fb2219e7dd03b885485888d798b2cc63d9473ee639540bdd4a4142cb`.
- D121 [formally closes the refined 1 ms pump–leak pilot](reports/REF005C_PUMP_PILOT_CLOSEOUT.md).
  D120's independent review finished **2026-09-16 18:32:49 UTC / 337.048 s**:
  **203,274 acceptance comparisons / zero failures**, plus **10,610,676**
  live-law/transfer/conservation/evidence-link checks. All 6,720 native updates,
  20,178 physical records, 36 refinement groups, eighteen observer pairs,
  twelve exact overlap records and six complete Cells restarts/checkpoints pass.
  Twenty-three refinement groups are floor-limited, not measured-order evidence.
  All 641 capture inputs, 55 production modules, 444 capture payloads, eleven
  audit inputs and 22 audit payloads authenticate. The original six-miss attempt
  remains rejected and unchanged. Main finest native energy defect: **7.351e-8
  pJ**, below the unchanged 1e-7 pJ limit. No error correction or tolerance change.
  Terminal status: `bounded_refined_pump_pilot_independently_closed`; completion
  SHA-256 `e2e67df2b6118cdacfcbf4f23357a972bcb6ecae7d4eacad3f02956ab4369bc1`.
  The 2026-09-17 closeout checks saved identities only; no simulator or audit
  rerun, biological validation, full BETSE parity, release promotion or GPU claim.
- D120 launches the [independent refined-pilot review](reports/REF005C_AUDIT_HANDOFF.md).
  This is the historical launch account; D121 above records independent closure.
  D119 reports **616,806 comparisons / zero failures**, finishing in **501.812 s**;
  all 36 native runs, eighteen observer pairs, twelve exact overlap records and
  36 refinement groups pass the producer checks. Its main energy-balance defect
  is 7.351e-8 pJ, below the unchanged 1e-7 pJ limit. Independent closure was
  pending at launch. All 641 inputs, 55 production modules and 444 sealed payloads
  authenticate; the original 431-file failed attempt remains unchanged.
  **47 audit preflight checks pass / 30.06 s**, including all six short controls,
  a complete real 640-step record, malformed-evidence refusals and exact Cells
  restart/checkpoint links. One detached stdlib/70-digit audit targets all
  6,720 native updates, live laws, conservation, energy, clocks and producer-state
  links, alongside saved trajectory/reference/refinement gates. No simulator or
  reference reruns, production edits, corrected energy or relaxed tolerances.
  CPUs 0–3, **900 s / 32 MiB per file / 128 MiB audit artifacts**; no polling,
  retry or automatic follow-up. Longer relaxation, biology and GPU remain separate.
  Launched **2026-09-16 18:27:11 UTC**, PID **3286920**, at
  `runs/ref-005c-refined-pump-audit-2026-09-16/audit-01`; registration SHA-256
  `55f85fb313424311247f2174e2b1f034e3a01d27e148191a12114b726250ea9d`.
  The launcher returned successfully; eleven review/helper/handoff inputs and the
  passing software receipt are frozen. No completion/status polling or automatic
  follow-up was performed; independent acceptance is not claimed at launch.
- D119 launches the [explicit native refinement](docs/BETSE_PUMP_REFINEMENT.md):
  This is the historical launch account; D120 above records its producer result.
  **6.25 / 3.125 / 1.5625 µs**, unchanged 1 ms duration and six controls, with
  twelve exact overlap records. **46 preflight checks pass / 36.82 s**, including
  all eighteen actual native YAML loads, exact evidence-copy/worker-dispatch
  checks and reproduction of all six original failures without solver reruns.
  One detached campaign targets 36 native runs / 18 observer pairs /
  6,720 observed updates, reusing 24 Cells trajectories, eighteen independent
  references and six restarts in 213 byte-verified files. No Cells/reference
  solver reruns, physics edits, energy corrections or tolerance relaxation.
  Per-row evidence and complete numerical miss counts improve failure reporting.
  CPUs 0–3, one BLAS thread, **1,260 s total / 256 MiB per file / 2 GiB disk**;
  641 source/configuration/contract inputs are frozen at launch.
  [Handoff](reports/REF005C_REFINEMENT_HANDOFF.md). The user's explicit rule is
  retained: Cells must not reproduce upstream numerical errors. Producer results
  remain pending independent review; no polling, retry or automatic follow-up.
  Launched **2026-09-16 17:56:47 UTC**, PID **3280084**, at
  `runs/ref-005c-refined-pump-2026-09-16/refinement-01`; registration SHA-256
  `1dcfb80dc010bc694bf752caa0b72c0f97699e162f4aa3599bfc5258deec9c07`.
  The launcher returned successfully. No completion/status check was performed
  at launch; the later user-requested status check is recorded under D120.
- D118 [diagnoses the failed matched pilot](reports/REF005C_PILOT_FAILURE_DIAGNOSIS.md)
  without rerunning a simulator. The capture completed its 36 native / 24 Cells
  trajectories, then failed final comparison after **385.829 s**. The independent
  **41.424 s** saved-data diagnosis finds exactly **six misses in 203,274 checks**:
  two native energy-trajectory coordinates and four native energy-balance limits.
  **376,320 flux/transfer checks and all 36 refinement groups pass**; six complete
  checkpoint links and full-state restart suffixes verify. All 629 inputs and
  431 failed-attempt files are preserved. **33 diagnosis tests pass / 1.73 s**.
  The energy errors halve with native timestep; an independent convex-remainder
  calculation explains the main balance miss. **The original attempt stays rejected.**
  Next: separately register a 6.25 / 3.125 / 1.5625 µs native ladder with explicit
  recording bounds, unchanged physics/tolerances and preserved Cells/reference
  evidence. That diagnosis launched no new capture or production change; D119
  above is the separately user-authorized next attempt, not an automatic retry.
- D116 [independently closes the native pump–leak lifecycle](reports/REF005B_PUMP_LOOP_CLOSEOUT.md):
  **73,188 comparisons / 150 physical records / 48 observed updates / six exact
  observer pairs** pass in **1.877 s**, without simulator reruns. The original
  twelve-run capture finished in 29.314 s; all 613 frozen inputs, 55 production
  modules and 73 payload files authenticate. **26 audit checks pass**. Exactly
  24 known disabled-cut notices are accounted for; no warning-free claim.
  This closes preparation/transfer ownership, not coupled trajectory or biology.
- D117 prepares the [matched 1 ms pump–leak pilot](docs/BETSE_MATCHED_PUMP_PILOT.md).
  This is the historical preparation/launch account; D118 above records its rejection.
  **37 preflight checks pass / 24.07 s**, including a real compiled run and exact
  complete-checkpoint restart. Map measured native chemistry/geometry into the
  existing public model; retain full capacitance when masking transport area.
  One gated campaign covers 48 held states on three backends, 18 independent
  reference solves, 36 native runs / 18 observer pairs, 24 Cells trajectories
  and six restart suffixes, with registered timestep refinement. Production
  remains unchanged. [Handoff](reports/REF005C_MATCHED_PUMP_HANDOFF.md).
  Detached and user-polled; no trajectory pass, automatic review, retry or
  follow-up regression is claimed by preparation or launch.
  Launched **2026-09-16 16:29:02 UTC**, PID **3261836**, at
  `runs/ref-005c-matched-pump-2026-09-16/pilot-01`; registration SHA-256
  `2dc09a3d112b1f0efc3a03d0a43f9cc2a395078553881ba7a7cc33497dff269b`.
  The launcher returned successfully. All **629 inputs** and the passing
  software receipt are frozen. No completion/status polling or automatic follow-up.
- D114 [independently closes the bounded kinetic-family gate](reports/SPEC010_FAMILY_CLOSEOUT.md).
  **All 422 tests pass** (74 family + 348 targeted regressions), completing in
  **418.438 s**. The separate **3.601 s** stdlib/60-digit review reconstructs
  **3,256 reference comparisons, 1,944 physical records, 12 exact restart
  suffixes and 36 complete checkpoint links**. All 601 captured inputs,
  55 production modules and 292 result files authenticate. **24 audit checks
  pass**. Maximum energy residual is 3.782e-14 pJ; global material residual
  9.216e-19 fmol. No solver reruns or production changes. This closes the
  bounded 0.16.0.dev0 family scope, not a full release matrix/promotion,
  native coupled BETSE qualification, biology or GPU validation.
- D115 prepares [native pump–leak lifecycle contact](docs/BETSE_PUMP_LOOP_PREFLIGHT.md):
  six controls, including density scaling and boundary masking, each observed
  and unobserved. **29 preflight checks pass / 2.70 s**, including actual native
  configuration loading. One detached **12-run / 48-observed-step** capture is
  launched: eight 25 µs INIT updates on the supported seven-cell fixture.
  Distinguish BETSE's raw sodium-rate diagnostic from actual pump cycles;
  check applied pump/passive density and single shared-bath updates before a
  later matched Cells/BETSE trajectory. [Handoff](reports/REF005B_PUMP_PREFLIGHT_HANDOFF.md).
  This launch account is historical; D116 above now closes the native scope.
  No native pass was claimed before execution and review; no automatic polling,
  retry, follow-up audit or regression. Production and upstream remain unchanged.
  Launched **2026-09-16 15:41:13 UTC**, PID **3247939**, at
  `runs/ref-005b-pump-loop-2026-09-16/capture-01`; registration SHA-256
  `5d8a6285baec4182758eff0e407ff95e2580dce5db3a9718460384e45d70c6bf`.
  All **613 source/configuration/contract inputs** are frozen; the launcher
  returned successfully. No completion/status polling or automatic follow-up.
- The D113 launch account below is historical; D114 above now closes its
  bounded acceptance. Stable 0.14.0 and fully accepted development 0.15.0.dev0
  remain preserved, with historical source-identity suites routed to their
  original contexts rather than weakened for this new tree.
- D113 implements [the versioned kinetic finite-bath model](docs/KINETIC_FINITE_BATH_MODEL.md)
  as **0.16.0.dev0 / `finite_extracellular@2`**, following D112's design.
  Explicit ATP/ADP/Pi inputs, resolved species roles, ten additional layout
  leaves, same-stage conservative composition, pump stage checks and whole-cubic
  enclosures now run through the ordinary engine. No synthetic-pump substitution,
  new integrator or checkpoint-identity waiver. The
  [one-cell configuration](configs/kinetic_finite_cell.json) is runnable.
  **60 focused checks and 8 controller checks pass**: strict schema/layout,
  complete independent RHS, rounding/interior refusal, compiled observations,
  channels/junctions/events and exact pre-edit equivalence for fourteen v1 cases.
  [Handoff and receipts](reports/SPEC010_FAMILY_HANDOFF.md) retain exact scope.
  The broader **74 new-family + 348 existing-model = 422-test** job is launched
  as one detached attempt: twelve 10 ms trajectories against both saved
  independent solvers, twelve complete restart suffixes, fresh-process replay,
  branches, scalar/batch/cohort windows and regression. Full acceptance is
  pending, with no biological, native full-loop or GPU parity claim.
  Stable 0.14.0 and accepted development 0.15.0.dev0 remain preserved.
  Launched **2026-09-16 13:41:18 UTC**, PID **3224245**, at
  `runs/spec-010-family-2026-09-16/acceptance-01`; registration SHA-256
  `112c7158956bbfdffe57a44a122097dddf8babbcac1461b66e4722c52b7aa01d`.
  All **601 source/configuration/contract inputs** and six software receipts
  are frozen. Launcher returned successfully; no completion polling or automatic
  follow-up. No full-panel pass is claimed at launch.
- D113 [reviews D111's completed process gate](reports/SPEC010_PROCESS_CLOSEOUT.md):
  **930 comparisons and all 348 regression tests pass**, no warnings/skips/errors.
  Completion **2026-09-16 12:59:03 UTC / 242.505 s**; regression **232.639 s**.
  All 361 registered sources and payloads authenticated before edits, then
  **1,273 working-context files / 52 production modules** were archived and
  byte-verified at `runs/spec-010-family-2026-09-16/pre-integration-01`.
  D112's earlier 12:56 check correctly left the then-running inputs untouched;
  the subsequent terminal review now clears the process gate, not full model
  acceptance. Historical receipts and source guards were not rewritten.
- D110 [independently closes the coupled kinetic-pump candidate](reports/NUM011_COUPLED_CLOSEOUT.md).
  The six-case 10 ms capture passed in **21.908 s**: 4,070 comparisons, 30 groups,
  12 refinement groups and 12 restart suffixes, no warnings. Separate 60-digit
  accounting reviews **3,756 physical records** and every comparison/restart in
  **4.535 s** without solver reruns. All 20 audit checks pass; 14 capture files
  and 14 candidate inputs remain unchanged. Every refinement group is below the
  roundoff floor: no measured convergence-order or general timestep claim.
- D111 historical handoff (superseded by D113 above): adds the [named kinetic pump process](docs/KINETIC_PUMP_PROCESS.md) to
  `src/cells/processes/kinetic_pump.py`: numeric parameter/result pytrees,
  explicit metabolic drive, signed cycles, stable saturation and a checked
  per-route domain. **32 process tests / 10 gate tests pass**, including actual
  six-state three-backend contact smoke. The
  [handoff](reports/SPEC010_PROCESS_HANDOFF.md) preserves earlier test findings.
  No accepted file is edited: all 352 remain unchanged; the new module extends
  the whole-package source identity from 51 to 52 modules. This working tree is
  not the accepted 0.15.0.dev0 source context; old checkpoint identity checks
  remain strict, with the accepted archive preserved before the extension.
  Launch one detached **930-comparison process contact and 348-test targeted
  regression**, bounded to CPUs 0–3, 60 s contact / 600 s regression / 900 s total,
  32 MiB per file / 128 MiB artifacts. The new law is **not selectable through
  ordinary simulation configuration yet**. Versioned host/layout integration,
  runner acceptance, native full-loop correspondence, biology and GPU remain.
  Launched detached **2026-09-16 12:55:00 UTC**, PID **3212517**, at
  `runs/spec-010-pump-process-2026-09-16/qualification-01`; registration SHA-256
  `ae42471c0e2b6dc0ac97c31fb18f70fc02cd8883eab38420da4b2f8fe0ba13e9`.
  The launcher returned successfully. All 361 source/contract/report inputs and
  both final software receipts are frozen. No completion/status polling or
  automatic follow-up; full qualification/regression success is not yet claimed.
- D108 independently [closes the Na/K source contact](reports/REF005A_PUMP_CONTACT_CLOSEOUT.md):
  **1,240 reconstructed comparison rows / 248 raw density triplets**, zero
  mismatches in **0.163 s**, without either simulator or the old oracle. All
  15 capture files / 11 source inputs and accepted implementation remain
  unchanged. **17 audit tests pass in 0.53 s**. The original capture's 5.0625 s
  pass/pending-audit receipt stays intact; its narrow component scope is now closed.
- D109 implements the [kinetic pump integration contract and coupled numerical
  candidate](docs/KINETIC_PUMP_INTEGRATION.md), retaining distinct law identity,
  explicit maintained ATP/ADP/Pi support, conservative cell/bath ownership and
  chemical-work accounting. **37 focused tests pass in 5.92 s**, including actual
  four-step reference/NumPy/JAX smoke, complete restart and corruption checks;
  earlier failed/intermediate receipts remain in the
  [handoff](reports/NUM011_KINETIC_PUMP_HANDOFF.md).
  Six 10 ms cases yield 12 independent DOP853/Radau references, 24 NumPy/compiled-
  JAX trajectories and 12 restart suffixes. Candidate steps are 100/50 µs, not
  inherited production bounds. One detached capture is bounded to CPUs 0–3,
  240 s per worker / 600 s total / 16 MiB per file / 64 MiB artifacts.
  Source contact is closed; coupled numerical acceptance, production integration,
  native full-loop pump correspondence, biology and GPU remain separate gates.
  No production edits or automatic follow-up audit/regression.
  Launched detached **2026-09-16 12:14:01 UTC**, PID **3178097**, at
  `runs/num-011-kinetic-pump-2026-09-16/candidate-01`; registration SHA-256
  `127ddcba432198f05a5705687293054bfc7cdcbc3e34eec5720ce776c4aba9f2`.
  Launcher returned successfully. No completion/status polling was performed;
  the 14 bound source/contract/report inputs and final software receipt are frozen.
  Full-panel success was not claimed at launch. Later inspection and D110's
  independent review now close this bounded numerical candidate, as above.
- D107 makes **BETSE-level biological/physical realism the minimum detailed-model
  target**, not a claim based on selected tests. The
  [active staged plan](docs/BETSE_REALISM_AND_NEXT_STEPS.md) starts substrate-
  dependent Na/K pump contact, scopes junction transport/lifecycle comparison,
  and prepares a source-labelled Xenopus biological benchmark. The synthetic
  pump stays distinct. Original-data permeability differences and possible
  active chloride transport are open biological questions, not fitted-away
  discrepancies. Spatial/multiphysics, GPU and multiscale organ work remain
  explicit later gates; production is unchanged.
  The [pump handoff](reports/REF005A_PUMP_CONTACT_HANDOFF.md) records **70 passing
  checks in 16.19 s**, including actual three-state native/NumPy/eager-JAX/JIT-JAX
  smoke, and the retained stdout/JSON smoke-harness failure. Repository lint,
  formatting (722 files at final inspection) and whitespace checks pass. The full instantaneous
  panel has 31 states / two constant profiles / 1,240 comparisons and is bounded
  to CPUs 0–3, 45 s per worker / 150 s total / 32 MiB artifacts. A detached
  capture and independent review remain distinct from production pump support.
  Launched detached **2026-09-16 11:07:21 UTC**, PID **3127417**, at
  `runs/ref-005a-pump-contact-2026-09-16/capture-01`; registration SHA-256
  `152b7ff43ff946450ef9c96f034d4a25ed09e2982ffa50a6ceaf451de0178fc4`.
  Launcher returned successfully; no completion/status polling or automatic
  follow-up. The 11 bound source inputs and handoff are frozen; the broader
  realism/junction/biological plans remain living indexes. Capture subsequently
  passed in 5.0625 s and D108 closed its independent review, as recorded above;
  production pump support is not yet claimed.
- D106's [independent timed-release closeout](reports/REF004D_TIMED_RELEASE_CLOSEOUT.md)
  **passes in 387.772 s**, finishing **2026-09-16 10:24:42 UTC**. All
  **15,042,946 independent comparisons / 182 groups** reconstruct with zero
  column mismatches, all 16 refinement / 12 history-contrast groups pass,
  and all 48 checkpoints / 2,592 arrays authenticate. Preserve all 49 coarse
  misses and 3,265 original identity diagnostics. Ten audit files / 203 source
  inputs / 37 historical reports and all 555 capture files remain unchanged.
  This closes only the fixed seven-cell / 2 ms channel experiment; biology,
  full BETSE parity, native restart and GPU are not qualified. No simulator or
  reference rerun. Earlier pending-audit receipts below remain historical records.
- D105's [timed capture](reports/REF004D_TIMED_RELEASE_CAPTURE.md) passes in
  **1,004.27 s**, finishing **2026-09-16 09:38:14 UTC**. All **14,772,920 native
  boundary comparisons**, required comparisons, 16 refinement groups and 12
  history-contrast groups pass. **49 coarse diagnostic misses remain** (35 a /
  14 b). The independent D104 reference review closed before either worker.
  All 555 capture files and 194 source inputs remain unchanged; capture success
  was pending its separate independent audit, now closed above.
- D106 adds that [saved-data audit](docs/BETSE_CHANNEL_RELEASE_CLOSEOUT.md), under
  new user authorization. It reconstructs **15,042,946 numerical identities /
  182 groups**, full Cells state and both switch-side RHS arrays, all **48
  checkpoints / 2,592 arrays**, native control clocks and source-order arithmetic.
  Preserve 28,280 zero-flux means, all 3,265 original identity diagnostics and
  all 49 coarse misses. Authenticate/reuse the closed reference review; do not
  repeat it or rerun either simulator. The
  [handoff](reports/REF004D_RELEASE_AUDIT_HANDOFF.md) records **116 passing tests**
  (103 in 41.99 s; 13 in 43.13 s), retained earlier receipts and the bounded
  software timeout. Repository quality checks pass; **203 source inputs /
  37 historical reports** precede launch.
  One separate detached audit is bounded to CPUs 0–3, **1,800 s / 256 MiB total
  artifacts / 128 MiB per file**. Production, biological and GPU claims remain
  unchanged. No polling, automatic retry, regression or follow-up.
  Launched detached **2026-09-16 10:18:14 UTC**, PID **3114261**, at
  `runs/ref-004d-timed-release-audit-2026-09-16/audit-01`; registration SHA-256
  `a786544e970a7056f0efd1e122ef39bf8eb174fb0373149f15cb7abe1dc592fb`.
  The launcher returned successfully. No completion/status polling was performed;
  completion was not claimed at launch; the subsequent closeout is recorded above.
  New sources, contract and reports remain frozen.
- D105/REF-004d implements the [reference-gated timed comparison](docs/BETSE_CHANNEL_TIMED_RELEASE.md).
  First independently reconstruct all **1,485,380 saved reference comparisons**;
  only a hash-linked review pass permits the native and Cells workers. Retain the
  fixed 2 ms window, histories a/b, four conditions and existing error budgets.
  The registered panel is **48 native phases / 8,960 updates / 96 input
  applications / 24 observer pairs**, **32 Cells trajectories / eight release-
  boundary restarts**, and **48 checkpoints / 2,592 arrays**. Check actual elapsed
  input boundaries, separate left/right currents, complete state, exact no-op
  neutrality, refinement and 12 signed history-contrast groups. Native source-
  order bath averaging and the six pre-channel voltage-nonce additions stay
  validation-specific; production and GPU architecture are unchanged.
  [Handoff](reports/REF004D_TIMED_RELEASE_HANDOFF.md) records bounded software
  verification: **121 tests pass** (107 in 36.15 s; 14 in 29.33 s), including
  real four-step native/Cells smoke and control-aware complete checkpoints.
  Development failures and the foreground timeout remain. Repository quality
  checks pass; **194 source inputs / 30 historical reports**
  and unchanged accepted production authenticate. One detached job is bounded
  to CPUs 0–3, **1,800 s total / 480 s native / 600 s Cells / 512 MiB artifacts /
  128 MiB per file**. No reference reintegration, polling, retry, follow-up audit
  or regression. A capture pass remains pending a later independent audit.
  Launched detached **2026-09-16 09:21:29 UTC**, PID **3100871**, at
  `runs/ref-004d-timed-release-2026-09-16/capture-01`; registration SHA-256
  `a82235aa0940c3c237d947104231ad24dfe0d02d05d55991858ca41690953352`.
  The launcher returned successfully; no completion/status polling was performed.
- D104's actual [reference capture](reports/REF004D_RELEASE_REFERENCE_CAPTURE.md)
  **passes in 160.675 s**, finishing **2026-09-15 23:22:10 UTC**. All **24 paths /
  48 segments**, **1,250,740 physical/reference + 234,640 dense comparisons** and
  all eight signal decisions pass, with zero failures or worker warnings.
  The 34-file packet / 182 sources / 19 reports authenticate unchanged.
  Completion SHA-256: `ae670b6e1825c1677ccfd29d008b5036aca371ede5c83d1dba49d3bcc3d01b8f`.
  Its receipt stays `piecewise_reference_pass_pending_review`; D105 independently
  reviews the saved numerical columns before any full timed simulator run.
- D104/REF-004d implements the [independent piecewise reference](docs/BETSE_CHANNEL_RELEASE_REFERENCE.md)
  after D103's user-reviewed input closeout. The fixed candidate is two histories,
  four conditions and three solver settings: **24 paths / 48 segment integrations**
  over 2 ms. Baseline is unsplit; no-op and suppression/release split exactly at
  0.5 and 1 ms. Carry all 28 coordinates, keep gates evolving during zero transport,
  and save both sides of each current/derivative switch. Reuse the unchanged
  D099/D095 reference budgets and independent algebra, with analytic blocked-gate,
  dense replay, thermodynamic, no-op, convergence and prospective resolution gates.
  All **102 focused tests pass in 4.35 s**, including bounded one-cell / 2 µs
  reference paths, corruption, exact carry, signal rejection and detached-job
  success/failure/timeout guards. The earlier 79-pass / 4.53 s receipt remains.
  These software fixtures do not qualify the real seven-cell / 2 ms experiment.
  [Handoff](reports/REF004D_RELEASE_REFERENCE_HANDOFF.md) precedes one detached
  reference-only job: CPUs 0–3, **900 s total / 480 s worker / 256 MiB aggregate /
  128 MiB per file**. No native/Cells trajectory entry point, production changes,
  automatic polling, retry, audit, regression or GPU work. A reference pass remains
  pending saved-evidence review and does not qualify dynamic simulator response.
  Repository lint, formatting (686 Python files) and whitespace checks pass.
  Model-free authentication confirms **182 source inputs / 19 bound reports**,
  the ten-file D103 packet and unchanged **352 implementation files / 51 modules**.
  Launched detached **2026-09-15 23:19:29 UTC**, PID **3018977**, at
  `runs/ref-004d-release-reference-2026-09-15/reference-01`; registration SHA-256
  `d5aa23c0dca9621c120fe73426d1efdec88a48da88b8b063cd1e2b1ca1ffc39e`.
  The launcher returned successfully; no completion/status polling was performed.
- D103's actual [input closeout](reports/REF004D_RELEASE_INPUT_CLOSEOUT.md)
  **passes in 24.469 s**, finishing **2026-09-15 22:18:23 UTC**. All **916,176
  comparisons**, 144 phases / 288 updates / 288 input applications / 72 observer
  pairs and **1,776 exact source-order means** pass. All **104 original exact-guard
  rejections** remain; maximum rounding is one ULP / 5.9952e-15 fmol, within
  unchanged physical budgets. The ten-file review / 175 review inputs and all
  605 original capture files / 165 original inputs authenticate. Completion SHA-256:
  `a3660e211dbd5cd2e2e6389d8a0ff46d15019842dd620a4114016157af5152ad`.
  Only input/two-single-update scope is closed, not timed full-loop release,
  native restart, biology or GPU. No simulator or reference integrator was rerun;
  D102's failed receipt and old checker are unchanged.
- D103/REF-004d implements the [saved-input review](docs/BETSE_CHANNEL_RELEASE_REVIEW.md)
  after the user-requested investigation of D102's failure. Pinned BETSE performs
  shared-bath averaging even at zero flux; its NumPy reduction can change a
  uniform bath by one ULP. A separate checker reconstructs that operation exactly
  and accounts for the material residual within unchanged physical budgets.
  No captured values, old checker, native implementation or production source is
  changed. All **66 review tests pass in 10.66 s**, including **198 actual NumPy
  reduction probes**, eight saved case rows, exact one-ULP corruption rejection,
  original-failure reproduction, source-diff and model-import guards. The first
  63-pass/two-failure receipt remains; only sub-ULP corruption fixtures were
  corrected. [Handoff](reports/REF004D_RELEASE_REVIEW_HANDOFF.md).
  All **605 capture files / 165 frozen inputs** authenticate. The new **175-input
  capsule** precedes one detached full-panel review on CPUs 0–3, **180 s /
  64 MiB aggregate / 32 MiB per file**, checking 1,776 zero-flux means plus all
  original physical/input/observer checks. Repository quality checks pass.
  The actual review subsequently closed as recorded above; no simulator rerun,
  polling, automatic retry, reference solve, response trajectory or GPU work.
  Launched detached **2026-09-15 22:17:58 UTC**, PID **2949897**, at
  `runs/ref-004d-release-review-2026-09-15/review-01`; registration SHA-256
  `bbb923316e0bc057fc083dffceebf5fdecd97e811cbe30ac06b796beb91dc864`.
  The launcher returned without polling. A later user-requested status check
  authenticated the successful input/single-update closeout recorded above.
- D102/REF-004d implements the [actual native input preflight](docs/BETSE_CHANNEL_RELEASE_PREFLIGHT.md)
  in a new validation-only adapter, without production changes. All **71 focused
  tests pass in 14.01 s**, including two real native smoke cases with observer
  partners (**four phases / eight updates**), independent accounting, exact state
  preservation, artifact linkage, corruption and failure-path checks. The
  [handoff](reports/REF004D_RELEASE_PREFLIGHT_HANDOFF.md) preserves five earlier
  failing XML attempts and the 69-pass intermediate receipt; fixes are confined
  to new tooling, without changing scientific budgets or old evidence.
  The full panel is **144 fresh phases / 288 single updates / 288 input
  applications / 72 observer pairs**, not a 2 ms release trajectory. Each phase
  gets one active priming update, input queries with no intervening integration,
  and one probe update. The **165-input capsule** authenticates the old evidence
  chain before one detached **480 s / 256 MiB aggregate / 64 MiB per-file** job,
  CPUs 0–3. Lint, formatting (670 Python files) and whitespace checks pass.
  Its actual [failure report](reports/REF004D_RELEASE_PREFLIGHT_FAILURE.md) records
  **36.066 s native completion**, all 144 phases / 288 updates / 72 observer pairs
  and no warnings, followed by controller rejection at **52.782 s**. The exact
  no-transfer identity guard encountered a one-ULP K bath change during zero-flux
  averaging. The capture remains failed/not qualified; 605 files, all sources,
  numerical budgets and original receipts are preserved. D103 is the new
  saved-data review above, not a retry or rewrite of this checker.
  Launched detached **2026-09-15 19:52:33 UTC**, PID **2850555**, at
  `runs/ref-004d-release-preflight-2026-09-15/capture-01`; registration SHA-256
  `5d4f24d7c933ae637957905110ef792684c05d30f31d667da327ebc39a6bd52a`.
  The launcher returned without polling; the later user-requested status check
  found the retained rejection described above.
- D101/REF-004d completes the [suppression/release input design](docs/BETSE_CHANNEL_RELEASE_DESIGN.md)
  after the user-reviewed D100 closeout. Existing availability schedules and
  complete m/h state need **no production change**. Keep input application,
  intrinsic kinetics and observations separate; propose a native absolute
  `maxDm = baseline * availability` parameter input, not a built-in tissue event
  or drug model. All **107 focused tests pass in 11.88 s**, including **54 real
  NumPy/eager/JIT instantaneous probes** at six saved nonzero-history/initial
  states, independently reconstructed complete RHS, exact blocked transport,
  continuing gate rates, preserved ledgers, 24 candidate grids and corruption
  checks. Integration entry points are forbidden in the probes. The
  [software result](reports/REF004D_RELEASE_DESIGN_CHECK.md) records the evidence;
  no new trajectory, native dispatch, reference solve, detached job or automatic
  follow-up was launched in D101. D102 adds the native input/single-update
  preflight above; piecewise references and dynamic response remain later gates.
- D100's actual [paired-history closeout](reports/REF004C_PAIRED_HISTORY_CLOSEOUT.md)
  **passes in 240.629 s**, finishing **2026-09-15 16:28:00 UTC**. All
  **8,036,300 comparisons independently reconstruct**, zero numerical-column
  mismatches; six contrast/eight refinement groups, all 24 full checkpoints /
  1,296 arrays, four Cells restarts/four eager-JIT pairs and twelve observer pairs
  pass. All **21 coarse diagnostic misses** remain. The ten-file audit packet,
  152 audit inputs, 291 capture files / 143 capture inputs authenticate unchanged.
  Completion SHA-256:
  `e152d806f72f2571b150eb6751c59e1a3fc34ac8accf4bfeaaf4502d30348135`.
  This closes the fixed 2 ms paired numerical scope, not biological preparation,
  suppression/release, native restart, broad BETSE parity or GPU. No simulator
  rerun or production release change; original pending-audit receipts stay intact.
- D100/REF-004c implements the [independent paired-history audit](docs/BETSE_CHANNEL_HISTORY_CLOSEOUT.md)
  after the user-reviewed D099 pass. Frozen replay is accompanied by independent
  numerical columns for both histories, all native boundaries, complete Cells
  states, six contrast groups and eight refinement decisions. A distinct raw-byte
  checkpoint check supplements the capture's older value-level decoder, using
  D098-authenticated layouts and complete saved state. All **21 coarse diagnostic
  misses** remain rejected rows. No simulator/reference integration or production
  change; all 291 capture files and 143 capture sources remain frozen. The new
  audit binds a **152-input capsule**, uses CPUs 0–3 and is bounded to **900 s /
  256 MiB aggregate / 128 MiB per file**. Software verification precedes detached
  launch; actual audit completion remains a separate gate. No polling, automatic
  retry, follow-up regression or GPU job.
  All **137 audit-only tests pass in 16.56 s**. The first receipt retains
  29 passes / 99 common setup errors from hashing input rather than canonical
  checkpoint definitions; the corrected auditor's 128-pass / 15.64 s receipt
  remains. Expanded full-reference software replay hit its 55 s foreground cap
  and has a separate timeout record; full replay stays in the detached audit,
  while quick callback tests use explicitly bounded saved-reference slices.
  No numerical integration, capture criteria or old evidence changed. The
  [handoff](reports/REF004C_PAIRED_HISTORY_AUDIT_HANDOFF.md) binds every retained
  attempt and the final XML before one fresh detached audit.
  Repository lint, formatting (**656 Python files**) and whitespace checks pass;
  no production regression or numerical integration was rerun.
  Final read-only authentication passes for all **291 capture files**, **143
  captured source inputs**, **152 audit inputs** and **19 bound prior reports**.
  Launched detached **2026-09-15 16:23:59 UTC**, PID **2742400**, at
  `runs/ref-004c-paired-history-audit-2026-09-15/audit-01`; registration SHA-256
  `e4278a65dcfcd521ab46f589e56f6ee76e4585b4e0ffa91bd7ce2d60e74f698d`.
  The launcher returned without polling. The later user-requested status check
  confirmed the successful independent closeout recorded above.
- D099/REF-004c implements the [reference-gated paired-history pilot](docs/BETSE_CHANNEL_HISTORY_PILOT.md)
  after the user explicitly requested preparation closeout, paired references
  and detached coupled capture. One workflow completes twelve independent
  reference solves and checks convergence/domain/signal before either simulator
  starts. The candidate 2 ms window is not selected from initial-rate evidence.
  Conditional capture has **24 native runs / 4,480 updates**, **16 Cells
  trajectories**, four full-state resumes and signed a-minus-b contrasts.
  All **56 focused tests pass in 22.96 s**, including both actual eager/JIT
  histories, complete short restart, reference corruption and launch-gate guards.
  The earlier 46-pass / 12.99 s receipt remains. Repository lint, formatting
  (**646 Python files**) and whitespace checks pass. No full production
  regression was rerun. The [handoff](reports/REF004C_PAIRED_HISTORY_HANDOFF.md)
  binds a **143-input capsule** and passing XML before detached execution on
  CPUs 0–3, **1,200 s total / 512 MiB aggregate / 128 MiB per file**. No production
  changes, loosened per-trajectory criteria, polling, retry, automatic post-capture
  audit or GPU work. A raw pass still requires independent saved-data closeout.
  Launched detached **2026-09-15 15:47:09 UTC**, PID **2676647**, at
  `runs/ref-004c-paired-history-2026-09-15/capture-01`; registration SHA-256
  `9c539f504312e77e3d695e5a549e0e0d2a34d1801b128c57e23c81f4e128341b`.
  The later user-requested status check confirmed **391.917 s**, no warnings,
  twelve passing reference solves, **7,367,280 native accounting comparisons**
  and zero required trajectory, accounting, refinement or history-contrast
  failures. Four restart/four backend pairs, twelve observer pairs and all
  **24 complete checkpoints / 1,296 arrays** pass. All **21 coarse diagnostic
  misses** remain (a: fourteen, b: seven). The active reference contrast reaches
  about **-0.722 mV** at 2 ms; blocked voltage contrast is exactly zero.
  All 291 files / 143 source inputs authenticate. Completion SHA-256:
  `ec63dc8d69a9f4c5b9da93ddf64708e91fc708729eb0f52cb1d8899170bde690`.
  The [capture report](reports/REF004C_PAIRED_HISTORY_CAPTURE.md) retains
  `paired_capture_pass_pending_audit`; D100 is the separately authorized closeout.
- D098 closes the [saved history preparation](reports/REF004C_HISTORY_PREPARATION_CLOSEOUT.md)
  in **3.062 s**, without simulator or reference integration. All **2,442 saved
  comparisons replay exactly**, **1,404 alternate rate comparisons** pass, and
  **528 layout-array hashes** match the previously audited full checkpoints.
  All **12 review tests pass in 0.38 s**. The four-file review / 132-input capsule,
  15-file preparation and unchanged accepted 352 files / 51 production modules
  authenticate. Completion SHA-256:
  `109ea8856106fd40ee24a8a2ac0f172d55f9b74fa8493daba09c277b6d3f5d8b`.
  This closes initial-state/rate/grid readiness only, not paired trajectories,
  biology or GPU. Original pending-review receipts remain unchanged.
- D097/REF-004c adds the [equal-current, different-history preparation](docs/BETSE_CHANNEL_HISTORY_PREFLIGHT.md)
  after the user-reviewed D096 closeout. Paired data settings differ only in m/h,
  with active and transport-blocked controls. Actual Cells initial-state/RHS
  checks on NumPy/eager/JIT and fresh isolated native gate updates precede any
  coupled history trajectory. Production and all earlier evidence stay unchanged.
  All **49 focused tests pass in 7.50 s**, including actual eager/JIT initial
  rates with integration entry points forbidden, full-state and array-axis
  corruption, exact inactive padding and native-step comparator controls.
  The earlier 44-pass / 1.87 s receipt remains. Repository quality checks pass;
  the prior nine-file audit / 284-file capture authenticate unchanged. The
  [handoff](reports/REF004C_HISTORY_PREFLIGHT_HANDOFF.md) binds a **130-input
  capsule** before one detached **240 s / 64 MiB aggregate / 32 MiB per file**
  preparation, CPUs 0–3. Numerical execution status belongs to its actual
  receipts; no automatic integration, polling, retry, audit or GPU work follows.
  Launched detached **2026-09-15 14:53:08 UTC**, PID **2665497**, at
  `runs/ref-004c-history-preflight-2026-09-15/capture-01`; registration SHA-256
  `ef8e417788734edbacb2d0f05028bee5d97f770e65e7fd9d44ddadfaea522586`.
  The later user-requested status check confirmed **14.036 s**, **2,442
  comparisons**, zero failures and no warnings. The separate D098 review above
  closes this evidence; the original receipt remains
  `history_preflight_pass_pending_review`. Completion SHA-256:
  `8b673c1797f87bdb8a4f139c8e362f6cb2289634707eb01d321d571fa0d2f928`.
- D096/REF-004b implements the [independent coupled-pilot audit](docs/BETSE_CHANNEL_FEEDBACK_CLOSEOUT.md).
  Frozen replay is paired with separate mathematical reconstruction of native
  boundaries, reference readouts/dense polynomials, Cells full states, fresh
  currents, checkpoint contents, restart/backend comparisons and refinement
  decisions. The fourteen coarse diagnostic failures remain part of the evidence.
  The audit imports no simulator or numerical library and reruns no integration.
  All 284 capture files, 112 capture inputs and accepted production remain frozen.
  All **122 audit-only tests pass in 11.18 s**; original 157 pilot tests and all
  five pilot XML attempts stay hash-bound without rerunning integration.
  Repository lint, formatting and whitespace checks pass. The
  [handoff](reports/REF004B_FEEDBACK_AUDIT_HANDOFF.md) binds a **122-input capsule**
  before one detached audit under **900 s / 256 MiB aggregate / 128 MiB per file**,
  CPUs 0–3, without polling, retries or automatic follow-up. Launched detached
  **2026-09-15 13:19:57 UTC**, PID **2652530**, at
  `runs/ref-004b-feedback-audit-2026-09-15/audit-01`; registration SHA-256
  `8de505e9b6f1d076e82e07321c6b834baa8850b14ca4ece7297c7d5bb98b488d`.
  The user-requested status check confirmed **172.504 s**, **5,806,006 independent
  comparisons**, zero mismatches, **24 complete checkpoints / 1,296 arrays**,
  twelve observer pairs, four restart pairs and four eager/JIT pairs. All
  fourteen coarse diagnostic misses replay unchanged. All nine audit files,
  122 source inputs and 284 capture files authenticate; completion SHA-256
  `61e700cbddda5141f92443ba684bf344d14d09e1b3c9db12110d1a0a923a28b9`.
  The [closeout report](reports/REF004B_FEEDBACK_CLOSEOUT.md) qualifies only the
  fixed 2 ms four-control numerical pilot, not biology, broad BETSE parity or GPU.
- D095/REF-004b implements both the [independent continuous reference and gated
  coupled pilot](docs/BETSE_CHANNEL_FEEDBACK_PILOT.md). Three reference solves
  per control (base/tight DOP853 and Radau) must agree before native/Cells workers
  start. The fixed 2 ms panel has twelve native observer pairs (24 fresh runs),
  twelve compiled and four eager JAX trajectories, and four complete checkpoint
  resumes. Each engine evolves its own state. Production remains unchanged.
  Lossless compressed native traces preserve every boundary; fresh native flux
  is probed after the run on copies, separately from step-integrated current.
  All **157 focused tests pass in 50.23 s** (96 original / 61 new), including
  saved-reference gate checks, refusal to launch simulators on a failed gate,
  full production state/restart and strict constitutive readouts. Earlier
  software receipts remain; fixture corrections did not alter production,
  scientific inputs or error budgets. Repository lint/format/diff checks pass.
  The [handoff](reports/REF004B_FEEDBACK_PILOT_HANDOFF.md) records the passing XML
  and **112-input capsule** before one fresh detached capture, bounded to
  **900 s / 512 MiB aggregate / 128 MiB per file**, CPUs 0–3. Launched detached
  **2026-09-15 11:48:52 UTC**, PID **2631746**, at
  `runs/ref-004b-feedback-pilot-2026-09-15/capture-01`; registration SHA-256
  `1a479c2589d65a52146c3167f82952a8c83bd4ca359a6e42c931aac6183a065a`.
  The user-requested status check confirmed completion in **338.424 s**, no
  warnings, all **5,181,760 native identities** passing, **2,264 charge snapshots**,
  reference convergence and zero required trajectory/accounting/refinement
  failures. All twelve observer pairs, four restart pairs and four eager/JIT
  pairs pass. Fourteen diagnostic misses at the coarsest native step are
  preserved: seven active voltage and seven blocked gate rows. All 280 manifest
  files / 112 source inputs authenticate. Completion SHA-256:
  `28e985c8f1d49d7953b21382ad6a34b6f2989f23c5407a97118902f8391c8ceb`.
  The original receipt remains `capture_pass_pending_audit`; D096 is the
  separately requested saved-data closeout. No automatic audit or GPU work.
- D094/REF-004b implements the [independent preparation/readiness audit](docs/BETSE_CHANNEL_LOOP_CLOSEOUT.md).
  Exact frozen replay and separate 80-digit mathematics cover **all 74,092
  saved comparisons**, with complete byte, state, clock, ownership, charge and
  candidate-resource contracts. Software reconstruction passes with zero
  numerical failures. All **176 focused tests pass in 25.21 s** (96 original /
  80 new); the first 162-pass/eight-failure receipt is retained. Those eight
  failures were new tests expecting `RuntimeError` instead of the guard's
  actual `ValueError`, not numerical or rejection-guard failures. Repository
  lint/format/diff checks pass. The [handoff](reports/REF004B_LOOP_AUDIT_HANDOFF.md)
  binds a **101-input source capsule**, passing XML and the unchanged 74-file
  preparation. One detached saved-data audit was launched at
  `runs/ref-004b-loop-audit-2026-09-14/audit-01`, under **120 s / 64 MiB**,
  CPUs 0–3, with model imports forbidden and no simulator reruns, polling,
  retry or automatic follow-up. Launched **2026-09-14 23:01:47 UTC**, PID
  **2464599**, registration SHA-256
  `fa0d689f4f9d11a86839b5adb71e2d5ad75bfa103d30d640064f2f2af14c71aa`.
  The user-requested status check confirmed **5.541 s**, **74,092 independently
  reconstructed comparisons**, zero failures, 204 float64 array records and
  twelve complete readiness contracts. All nine audit files / 101 source inputs
  authenticate; completion SHA-256
  `8ec513d8171ebf3a6670ae270f66fed1821ff4caf66670076c3e4bc03ef5c391`.
  This closes preparation/readiness only. Production, old evidence and dynamic
  qualification stay unchanged; D095 is the separately requested next step.
- D093/REF-004b implements [full-loop preparation and observation](docs/BETSE_CHANNEL_LOOP_PREPARATION.md)
  and the [small feedback-pilot design](docs/BETSE_CHANNEL_FEEDBACK_DESIGN.md).
  The completed capture comprises eight fresh native INIT runs: four controls,
  observer-on/off partners, eight 25 µs updates each. A separately declared
  initial m/h fixture applies once after real native initialization in both
  modes; the step observer only copies state. It records gate-before-transfer,
  current export, ordinary update and voltage boundaries, with native labels
  distinguished from elapsed time. Twelve candidate Cells definitions exercise
  the existing parser, initial-state/RHS and resource guards, plus an independent
  continuous vector field. **No Cells trajectory or full dynamic panel runs in
  this preparation.** All **96 focused tests pass in 18.70 s**, including the
  complete Cells readiness worker without integration. Earlier 83-pass / 17.63 s
  and 95-pass / 18.04 s receipts remain. Repository lint/format and diff checks
  pass. The [D093 handoff](reports/REF004B_LOOP_PREPARATION_HANDOFF.md) binds a
  **94-input source capsule**, all nine D092 audit files, all 54 original capture
  files, and unchanged 352 accepted files / 51 production modules. One detached preparation
  is bounded to **240 s / 128 MiB**, CPU 0–3, float64, without polling, retry or
  automatic audit/follow-up, at `runs/ref-004b-loop-preparation-2026-09-14/capture-01`.
  Launched **2026-09-14 20:09:37 UTC**, PID **2427639**, registration SHA-256
  `e8ec5eb5e6274544bfced0dec64d77509c540d25e9222ed4703ace29e211cd27`.
  The user-requested status check confirmed **18.031 s**, no warnings and zero
  failures: **73,744 native boundary comparisons + 348 Cells initial-rate
  comparisons**, four matching observer pairs and twelve candidate definitions.
  The 74-file capture retains its original pending-audit receipt. Production and
  old evidence stay unchanged; saved-data closeout and dynamic qualification
  remain separate.
- D092's actual [independent closeout](runs/ref-004b-transport-audit-2026-09-14/audit-01/completion.json)
  **passed in 3.215 s**. All **37,068 comparisons** independently reconstruct,
  with **zero failures**, twelve definition contracts and two hidden-state
  controls. No simulator or prior audit was rerun. This qualifies only the
  bounded single-transfer contact, not coupled trajectories, biological realism,
  broad BETSE parity or GPU. Its nine-file packet and the original pending-audit
  capture receipt remain unchanged. D093 above is the separately requested next
  preparation, not an automatic continuation.
- Implemented D092/REF-004b's [independent single-transfer audit](docs/BETSE_CHANNEL_TRANSPORT_CLOSEOUT.md)
  after the user-reviewed D091 capture passed all **37,068 comparisons in
  21.272 s**, without warnings. Audit exact replay and a separate 80-digit
  reconstruction cover every numerical row; independent definition/charge/owner
  mapping and hidden-state checks accompany complete partial-record/provenance
  authentication. All **220 focused tests pass in 33.27 s** (152 original / 68
  new), with repository quality checks passing. Earlier 59-pass/seven-error and
  67-pass/one-failure software receipts remain: corrected a new null-channel
  representation check and a test's expected rejection boundary, not physics.
  All **54 capture files / 76 capture inputs**, accepted **352 files / 51
  production modules**, installed native source and both prior failures remain
  unchanged. The [handoff](reports/REF004B_TRANSPORT_AUDIT_HANDOFF.md) binds an
  **83-input capsule** and the passing XML before one detached saved-data audit
  at `runs/ref-004b-transport-audit-2026-09-14/audit-01`, under **120 seconds /
  64 MiB**. Launched at **2026-09-14 18:40:33 UTC**, PID **2413868**,
  registration SHA-256
  `770d9a6c4e7fb33666d3b8d3a057806ed0361fe8293e23f99b308f854822c787`.
  The later user-requested status check confirmed the successful closeout above.
  The audit forbids model
  imports and reruns no simulator or prior audit; no automatic polling, retry or
  follow-up. The [next coupled-pilot outline](docs/BETSE_CHANNEL_DYNAMIC_PILOT.md)
  was conditional design only, not a protocol or launch. Single-transfer closeout
  now passes; coupled trajectories, biology, broad
  BETSE parity and GPU remain unqualified.
- Implemented D091/REF-004b's [registered worker-environment correction](docs/BETSE_CHANNEL_RUNTIME_FIX.md).
  D090 executed all twelve native cases, then stopped after **7.084 s** at the
  Cells runtime guard: the launcher supplied `JAX_DISABLE_JIT=false`, while the
  accepted runtime records absence. No Cells transfer or comparison ran. The
  new launcher reproduces registered values/absences, including `XLA_FLAGS`,
  before importing JAX; strict identity and enabled-JIT checks stay unchanged.
  All **152 focused tests pass in 13.25 s** (107 original / 45 new). Five real
  worker startup probes pass in **4.589 s**: corrected startup reaches the input
  read, while explicit-false, empty-XLA, disabled-JIT and wrong-package controls
  are rejected. These probes execute no transport. All **51 D090 failure files**,
  70 prior source inputs, D089's 22-file failure and accepted 352 files / 51
  production modules remain unchanged. Repository quality checks pass.
  The [handoff](reports/REF004B_RUNTIME_FIX_HANDOFF.md) binds a **76-input capsule**,
  passing XML and 11-file startup packet before one fresh detached capture at
  `runs/ref-004b-runtime-fix-2026-09-14/capture-01`. Launched at **2026-09-14
  14:50:55 UTC**, PID **2348520**, registration SHA-256
  `90dc854e2a8b32a350127325d8a49a9c8a7159deb9c08e71fdd85c02b285a322`.
  The user-reviewed capture now passes all **37,068 comparisons in 21.272 s**,
  without warnings: twelve native updates and twelve matched transfers per
  Cells backend. Original status stays `capture_pass_pending_audit`; D092 above
  supplies the separately requested independent closeout.
  Same **300 seconds / 128 MiB**, twelve native cases and twelve
  matched transfers per NumPy/eager/JIT backend. No polling, automatic retry,
  audit or coupled-trajectory expansion; production and criteria unchanged.
  No new numerical, biological, broad BETSE-parity or GPU qualification.
- Implemented D090/REF-004b's [configuration-only correction](docs/BETSE_CHANNEL_SETUP_FIX.md):
  change native `biomolecules: null` to `[]`, preserving the original numerical
  protocol, Cells worker and comparator. All **107 focused tests pass in 7.00 s**
  (76 original / 31 new). The real BETSE YAML/type-contract check passes in
  **4.143 s**, confirming null rejection and empty-list acceptance in four
  configurations; it is not world/network initialization or transport evidence.
  All 22 failed-attempt files, 63 original capsule inputs, 393 earlier-source
  hashes and accepted 352 files / 51 production modules remain unchanged.
  Repository lint/format checks pass. The [handoff](reports/REF004B_SETUP_FIX_HANDOFF.md)
  binds a 70-input capsule and the passing native contract packet before one
  fresh detached capture at `runs/ref-004b-setup-fix-2026-09-14/capture-01`.
  Launched at **2026-09-14 13:31:26 UTC**, PID **2337052**, registration SHA-256
  `7b10286e2994965847fbf700ea8e5e33078a224391fd5062f62b6df63fe631e8`.
  The user-reviewed run stopped after **7.084 s**, after all twelve native cases
  but before any Cells transfer, on a launcher/runtime-identity mismatch.
  D091 above preserves this failure and supplies the environment-only successor.
  Same **300 seconds / 128 MiB**, CPU 0–3, float64 and twelve prescribed cases.
  Actual receipts establish execution state; no polling, automatic retry, audit
  or dynamic expansion. No coupled-trajectory, biological or GPU qualification.
- Implemented D089/REF-004b's [native channel transport preflight](docs/BETSE_CHANNEL_TRANSPORT_PREFLIGHT.md).
  Four native setup controls and three fresh states each check face-targeted
  Kv1p5 opening, permeability, direct ion transfer and separate current export.
  Cells uses its unchanged finite-bath RHS at the actual post-native-gate state;
  the adapter's single prescribed ledger update is **not an RK4 step or coupled
  trajectory**. All **76 focused software tests pass in 2.03 s**, and repository
  lint/format checks pass. All 352 accepted files / 51 production modules and
  isolated-channel evidence remain unchanged. The [handoff](reports/REF004B_TRANSPORT_PREFLIGHT_HANDOFF.md)
  precedes one detached attempt, with 63 source-capsule inputs, 393 earlier-source
  hashes, CPU 0–3, float64, **300 seconds / 128 MiB artifacts**. Actual launch and
  result receipts belong to `runs/ref-004b-transport-2026-09-14/capture-01`.
  Launched at **2026-09-14 10:11:12 UTC**, PID **2314542**, registration SHA-256
  `bde5e58153cbe955252bad47b216fad2b6a9cfa449691e3f8f2ac64b3a31dcbc`.
  The user-reviewed attempt stopped after **4.672 s** at empty-network setup:
  the adapter's null biomolecule value violated BETSE's sequence type contract.
  Three network-off cases completed; no channel-runner or Cells comparison ran.
  All 22 files and the original failure remain frozen; D090 above supplies the
  separately authorized correction, not a retrospective pass.
  No polling, retry, automatic audit or full-loop pilot. A raw pass still needs
  separate closeout; biology, general BETSE parity and GPU remain unqualified.
- Completed D088/REF-004a's [independent isolated-channel closeout](reports/REF004A_KV1P5_CLOSEOUT.md)
  in **0.979 s**, without importing or rerunning either simulator. All **11,266
  comparisons replay exactly** and are independently rebuilt with 80-digit
  arithmetic. All **102 tests pass in 2.58 s**: 63 original and 39 new checks.
  All 392 Python files pass quality checks. The 36 measured refinement ratios,
  12 roundoff-limited diagnostics and six hidden-history checks are preserved.
  All 13 capture files, 352 accepted implementation files / 51 production modules
  and earlier evidence remain unchanged. This qualifies only the registered
  isolated channel, not coupled cells, biology, general BETSE parity or GPU.
  The [coupled-channel plan](docs/BETSE_COUPLED_CHANNEL_PLAN.md) identifies native
  face-indexed gates, direct channel concentration updates and separate current
  accounting. **Next: small configuration/transport and single-update preflight**
  at 298.15 K using existing finite-bath components, before a dynamic pilot.
  No further job was launched at that closeout; D089 above is the separately
  requested next stage. Earlier passive input-sampling limits remain.
- D087/REF-004a starts the [isolated Kv1.5 channel comparison](docs/BETSE_VOLTAGE_GATE_CONTACT.md).
  Six prescribed-voltage protocols cover opening, closing, slow inactivation/
  recovery, event continuity and distinct hidden histories. Eighteen native and
  eighteen compiled-Cells trajectories use 1/0.5/0.25 ms steps; instantaneous
  kinetics and one shared RK4 step also exercise NumPy/eager/JIT. The 298.15 K
  engineering regime and different native/RK4 updates are explicit. A separate
  Decimal oracle checks each discretization and continuous-solution refinement.
  All **63 focused preflight tests pass in 1.11 s**; prior 41/62-pass receipts
  are retained. Initial native open fraction is explicitly derived, without a
  zero-time trajectory update. All 389 Python files pass lint/format checks. The
  [handoff](reports/REF004A_KV1P5_HANDOFF.md) precedes one detached capture,
  with a **180-second / 64 MiB artifact cap**, no polling, retry or automatic audit. Actual execution
  belongs to `runs/ref-004a-kv1p5-2026-09-13/capture-01`. This is not a whole-cell
  voltage clamp or coupled transport; production and earlier evidence stay frozen.
  That user-reviewed capture now passes all 11,266 comparisons in **11.971 s**,
  without warnings. D088 above supplies its separately requested closeout; its
  original pending-audit receipt and handoff remain unchanged.
- Completed D086/REF-003e1's [independent finer-response closeout](docs/BETSE_REFINED_RESPONSE_AUDIT.md).
  The user-reviewed D085 capture finished in **2239.322 s**, with **2,298,936
  required checks passing** and all **4173 diagnostic failures retained**.
  The new read-only audit replays the full 2,494,936 comparisons and independently
  rebuilds **1,121,904 surface checks / 132 scopes**, without rerunning either
  simulator. It keeps all failures in a complete linked ledger. First preflight:
  **94 passes / one test-exception expectation failure in 25.53 s**; the existing
  import guard correctly rejected the import. That receipt stays frozen. All
  **105 new tests now pass in 28.38 s**; all 385 Python files pass quality checks.
  The [handoff](reports/REF003E1_REFINED_AUDIT_HANDOFF.md) binds a 118-input capsule,
  1027-file baseline and unchanged 56-file continuation / 241-file resource failure.
  The user-reviewed [joint completion](runs/ref-003e1-refined-response-audit-2026-09-13/audit-01/completion.json)
  now passes in **249.644 s**, including **all 336 tests**, zero failures/errors/
  skips, all **2,298,936 required comparisons**, and the independently rebuilt
  surfaces. It qualifies only seven cells, 1 ms, matched constants, four conditions,
  6.25 µs held input and the registered CPU backends/subdivisions. All 4173
  diagnostic failures remain. No simulator was rerun or follow-up job launched.
  The original handoff, stage audit and all earlier evidence remain unchanged;
  native/forcing convergence, biology and GPU are still unqualified.
- Implemented D085/REF-003e1's [trace-budget continuation](docs/BETSE_TRACE_BUDGET_CONTINUATION.md).
  D084 stopped at the 16 MiB configured trace guard after **1830.727 s**,
  with all **16 native / 26 Cells runs** completed. This was not a measured
  out-of-memory event. Raise only the eight unexecuted 640-step definitions to
  **64 MiB**; the largest production reservation is **24.6415 MiB**. All
  **48 actual production timeline/resource checks** pass without integration.
  Reuse the original results directly: **666,108 internal checks pass**, zero
  failures, without inventing an old aggregate Cells worker receipt. All
  **47 continuation tests pass in 22.88 s**; all 380 Python files pass quality
  checks. The [handoff](reports/REF003E1_TRACE_RESUME_HANDOFF.md) binds a
  112-input capsule, 1013-file baseline and all 241 unchanged failure files.
  The separately launched **22 remaining Cells runs / 8480 steps** and unchanged
  comparison now finish in **2239.322 s**, with no new native execution. CPU 0–3,
  float64, **two-hour total / 1 GiB combined retained-plus-new artifact cap**.
  Actual receipts belong to `runs/ref-003e1-trace-resume-2026-09-13/capture-01`;
  its capture reports all required checks passing and 4173 diagnostic failures
  (150 coarse / 40 intermediate / 3983 across-hold). D086 above adds the now
  separately requested independent audit; no automatic polling or retry.
  Production, scientific criteria, all older sources/evidence and the 150
  coarse rejections stay unchanged; no new response/biology/GPU qualification.
- Implemented D084/REF-003e1's [two finer response panels](docs/BETSE_REFINED_RESPONSE_PANEL.md):
  16 new native / 48 new Cells runs at 12.5/6.25 µs, reusing the frozen 25 µs
  response explicitly. Production, criteria and all earlier adapters stay unchanged.
  Separate all-h internal/solver/backend gates, finest-held cross-engine gates,
  and diagnostic native integration/resampling versus Cells input sensitivity.
  Preserve every coarse rejection. The first software run reports **96 passes /
  four failures in 60.79 s**; fixes address a new checker variable collision,
  a comparison-count expectation and a test exception expectation. The failed
  receipt remains intact. All **24 targeted checks pass in 31.84 s**, including
  exact coarse arithmetic/surface overlap and late-grid corruptions; all 375
  Python files pass lint/format checks. The user-reviewed
  [software completion](runs/ref-003e1-response-refined-preflight-2026-09-13/checks-01/completion.json)
  now passes **114/114 tests**, no failures/errors/skips, in **95.688 s total**
  (64.15 s pytest). Its 106-input capsule and all manifested payloads verify;
  the software job launched no simulation. The user has approved freezing
  [response prelaunch](reports/ref-003e1-refined-response-prelaunch.json) and
  launching only the 16-native / 48-Cells capture detached, under the unchanged
  **3 h 15 min / 1 GiB** cap. Actual launch/completion/failure receipts live in
  `runs/ref-003e1-response-refined-2026-09-13/capture-01`; only those receipts
  establish execution state. That capture now has a preserved resource failure
  after 16 native / 26 Cells runs, before integration of the 27th Cells row;
  D085 above provides the separately authorized continuation. No automatic
  polling, retry or follow-up audit.
  The [historical implementation handoff](reports/REF003E1_REFINED_RESPONSE_HANDOFF.md)
  remains frozen.
  The 990-file baseline, 150 response / 16 audit / 1042 dispatch files and all
  accepted production remain preserved. No new response/convergence/biology/GPU
  qualification is claimed.
- Implemented D083/REF-003e1's [finer-input dispatch preflight](docs/BETSE_REFINED_DISPATCH_PREFLIGHT.md):
  eight fresh preparations at 12.5/6.25 µs, all four conditions, 960 direct
  dispatches and 345,600 prescribed diffusion-value checks. No transport,
  integration or Cells run is permitted. All **109 focused software tests pass
  in 36.21 s**, using saved initial states and fabricated event/receipt data.
  Reuse the frozen observer/fence; extend only clock mapping and variable-length
  checking. The [handoff](reports/REF003E1_REFINED_DISPATCH_HANDOFF.md) binds
  a separate 98-input capsule and a prospective 300-second worker / six-minute
  detached attempt, CPUs 0–3 and 256 MiB artifacts. Actual native results and
  launch receipts are separate. The user-reviewed
  [actual result](runs/ref-003e1-refined-dispatch-2026-09-13/preflight-01/completion.json)
  now passes in **116.002 s**, with all 960 dispatches / 345,600 diffusion checks,
  maximum scaled error 2.671e-15 and no warnings or integration. No automatic
  response or audit followed. The 979-file baseline, 150-file response, 16-file audit
  and all accepted production remain preserved. This is an input-application
  gate, not a finer response or convergence claim.
- Completed D082/REF-003e1's [saved-data failure audit](docs/BETSE_HELD_RESPONSE_AUDIT.md):
  the user-reviewed [joint closeout](runs/ref-003e1-response-audit-2026-09-13/audit-01/completion.json)
  finished in **50.390 s**, reproducing 345,576 comparisons and independently
  rebuilding all 147,312 surface checks. All 150 failures are shared-bath Na/K
  amount differences; 198,264 internal checks pass. The separate reporting
  correction leaves the numerical rejection intact. All **70 new tests pass**;
  the unchanged legacy suite reports **121 passes / one expected metadata-guard
  failure** from the recorded user `.gitignore` amendment, not an all-green suite.
  All original files remain intact and neither simulator was rerun. The finest
  saved constant-input baseline passes, with successive error ratios about 0.5;
  this does not establish pulse convergence. The historical
  [handoff](reports/REF003E1_RESPONSE_AUDIT_HANDOFF.md) stays frozen. D083 above
  starts the separately requested finer-input preflight, not response integration.
- D081/REF-003e1's [held-input response pilot](docs/BETSE_HELD_RESPONSE_PILOT.md)
  completed all eight native / 24 Cells runs in **715.769 s**, without warnings,
  then [rejected 150 of 345,576 comparisons](runs/ref-003e1-response-2026-09-13/capture-01/failure.json).
  Internal law/accounting checks report zero failures; coarse cross-engine
  shared-bath amount errors remain failures under the original criteria.
  Its scope is unchanged:
  eight native / 24 Cells runs, four input conditions, matched constants,
  fixed 25 µs holds and separate eager/JIT solver subdivisions over 1 ms.
  New control-aware capture and saved-data comparison preserve the original
  equations, runner, old adapters and numerical criteria. Controls, state,
  fresh rates and interval/cumulative transfer have separate checks. The
  [handoff](reports/REF003E1_RESPONSE_PILOT.md) binds focused software tests,
  an 88-file source capsule and prospective resources before detached launch.
  All **122 focused tests pass in 21.41 s**; 359 Python files pass quality
  checks. Earlier software receipts retain two corrected fixture/count issues;
  no model or physical criterion changed.
  Stage limits are 180/2100/180 s, total 42 minutes, CPUs 0–3 and 512 MiB
  artifacts. Native 25 µs baseline errors are already known: retain any
  comparison failure without relaxed criteria or automatic refinement.
  This is not native/forcing convergence, biology or GPU qualification.
  The capture and original prelaunch handoff remain frozen. D082 above now
  implements the separately requested saved-data audit/regression.
- Completed actual nonzero-event preflight, D080/REF-003e1: the
  [native result](reports/REF003E1_DISPATCH_PREFLIGHT.md) passes **four fresh
  preparations / 160 direct event dispatches in 24.463 s**, including 40
  nonzero targeted dispatches. All **57,600 diffusion-value checks** pass,
  maximum baseline-scaled control error 2.671e-15, with no Python warnings.
  Actual targets/modifiers and physical-state invariance pass; baseline and
  zero-amplitude dispatch records agree exactly. All **75 focused tests pass
  in 8.48 s**; 352 Python files pass quality checks. The 201-file attempt,
  80-file adapter capsule and 332 installed native Python hashes are retained.
  All previous evidence / 352 accepted files / 51 production modules remain
  unchanged. No transport or integration ran, and no response trajectory is
  qualified. D081 above implements the separately approved control-aware
  eight-native / 24-Cells pilot; D080 itself launched no response trajectory.
- Added held-intervention design/compiler, D079/REF-003e1: the
  [new input contract](docs/BETSE_HELD_INTERVENTION.md) specifies baseline,
  zero-amplitude, static-blocked and suppression/recovery conditions. Actual
  pinned-pulse/source-order arithmetic and unchanged Cells parser/schedule/grid
  probes check 1120 control samples and 36 schedule/grid configurations,
  with genuinely distinct subdivisions at each fixed hold interval, boundary
  sides and the retained final hold. All **80 focused tests pass in 14.14 s**;
  348 Python files pass quality checks. This is control-only,
  not actual nonzero event dispatch or integration. The proposed first pilot
  has eight native and 24 Cells runs, matched constants and a fixed 25 µs hold;
  D080 above now completes actual nonzero preparation/dispatch preflight. The
  [report](reports/REF003E1_CONTROL_DESIGN.md) records focused checks and preserves
  all previous evidence / 352 accepted files / 51 production modules. No capture
  is registered, no long job is launched and no biological/GPU claim is added.
- Completed independent expanded closeout, D078/REF-003e0: the user-polled
  [joint verdict](runs/ref-003e0-expanded-audit-2026-09-12/audit-01/completion.json)
  passes **1,232,616 numerical comparisons and 433 focused tests in 167.679 s**,
  with maximum normalized error 0.185990. This qualifies the seven-cell,
  1 ms, both-F/R, three-timestep **zero-amplitude SIM bridge**, not a nonzero
  response or biology. All 802 capture files, earlier evidence and production
  remain unchanged; neither simulator was rerun. The historical
  [handoff](reports/REF003E0_EXPANDED_AUDIT_HANDOFF.md) and standalone pending-
  regression audit receipt stay frozen. D079 above now starts control design
  for the separately requested nonzero response, without automatic expansion.
- Completed expanded capture, D077/REF-003e0: the user-polled
  [receipt](runs/ref-003e0-expanded-2026-09-12/capture-01/capture.json) reports
  **72 runs / 3360 observed steps passing in 203.562 s**, both F/R profiles and
  25/12.5/6.25 µs. All 36 observer pairs, 24 variant controls, 1120 enabled-target
  no-op dispatches and 12 original-pilot overlaps pass, with no Python warnings.
  All 798 payload hashes / 802 files verify; 644,923,963 bytes before the receipt
  stay within budget. The original [handoff](reports/REF003E0_EXPANDED_BRIDGE.md)
  remains frozen. All 352 accepted files / 51 production modules and earlier
  evidence are unchanged; no new Cells run. D078 above completes the separately
  approved independent audit/regression, not a new simulation or intervention.
- Completed independent pilot closeout, D076/REF-003e0: the user-polled
  [completion](runs/ref-003e0-loop-audit-2026-09-12/audit-01/completion.json)
  passes **88,956 independent numerical comparisons** and **165 focused tests**
  in **32.682 s**, with maximum normalized error 0.146996. All **142 pilot files**,
  the 58-file original capsule and earlier evidence remain unchanged. This
  qualifies only the matched-constant 25 µs, 1 ms, seven-cell passive/blocked
  SIM pilot, not expanded coverage or biology. No simulator was rerun and all
  352 accepted files / 51 production modules are unchanged. The historical
  [prelaunch handoff](reports/REF003E0_PILOT_AUDIT_HANDOFF.md) stays frozen;
  D077 above adds the separately approved expanded capture.
- Implemented the narrow full-loop pilot, D075/REF-003e0: the
  [prospective contract](docs/BETSE_FULL_LOOP_BRIDGE.md) specifies **12 native
  SIM runs / 240 observed steps**, at matched constants, 25 µs and 1 ms.
  Phase, default-profile and zero-amplitude-event controls have independent
  observed/unobserved partners. All **100 focused adapter tests pass in 7.45 s**;
  synthetic gates are not native evidence. The [handoff](reports/REF003E0_FULL_LOOP_PILOT.md)
  binds a fresh 120-second worker / 150-second total, CPUs 0–3 and 256 MiB
  artifact budget before the separately recorded detached launch. No new Cells
  run, old full suite, production change or qualification is added. The user-polled
  capture now reports **all 12 runs / 240 observed steps passing in 26.139 s**.
  D076 above completes the separate independent audit before broader coverage.
- Completed profile-bridge preparation, D074/REF-003e0 v2: all **six native
  preparations and 30 direct event dispatches pass in 17.360 s**. The
  [versioned result](reports/REF003E0_PROFILE_BRIDGE.md) separately checks
  profiles-off SIM, default-profile-on SIM, and enabled zero-amplitude Na/K/Cl
  events for passive and blocked cases. Starting values match retained INIT;
  physical setup and no-op dispatch arrays agree exactly across configurations.
  Partial state now persists before optional metadata checks. All **87 focused
  tests pass in 2.10 s**; 59 attempt files / 51 captured adapter-input files and
  332 installed native Python files are recorded. All 352 accepted files / 51
  production modules, the failed D073 attempt and older evidence are unchanged.
  No integration, trajectory qualification, full-suite rerun, biology or GPU claim.
  D075 above now implements the separate narrow full-loop pilot with exact
  controls and observation partners. D074 itself launched no trajectory.
- Implemented SIM bridge adapter/event observer, D073/REF-003e0, but the
  [first native preparation preflight failed](reports/REF003E0_PHASE_PREFLIGHT.md)
  after **9.491 s**: the profiles-off baseline has no resolved default tissue,
  contrary to the adapter's metadata assumption. Source inspection confirms
  that targeted events need the missing profile/target structures. The
  zero-amplitude row was not reached and no preparation result or trajectory
  was qualified. All **73 focused software/negative-evidence tests pass**;
  the six-file failed attempt is preserved and an early guard prevents rerunning
  the unamended candidate. D074 above now implements the separate versioned
  profile controls and partial-state persistence; its preparation passes without
  revising this first failure. No automatic retry or trajectory launch. All 352 accepted
  files / 51 production modules, old packets and D072 evidence stay unchanged.
- Completed intervention design, D072/REF-003e: the [source/control review](reports/REF003E_INTERVENTION_DESIGN.md)
  passes **38 focused tests in 3.67 s**, without integrating either model.
  BETSE schedules events only in SIM, while the accepted trajectory used INIT;
  its additive logistic permeability pulse is not an exact square block. An
  explicit raw/elapsed clock conversion matches the actual source control at
  280 points within 2.665e-15. Existing Cells right-continuous controls and
  off-grid event splitting pass control-only checks. The
  [staged design](docs/BETSE_INTERVENTION_PLAN.md) calls for a no-intervention
  SIM-from-neutral bridge first, then a matched held-drive suppression/recovery
  comparison with separate input and integration refinement. All 352 accepted
  files / 51 production modules, both old packets and the prior closeout remain
  unchanged. No capture is registered/launched, no old suite is rerun and no
  new trajectory, biology or GPU qualification is claimed. D073 above implements
  the separate bridge/observer and records its failed first preparation preflight.
- Completed bounded trajectory closeout, D071/REF-003d v2: the
  [independent audit](reports/REF003D_CLOSEOUT.md) reproduces all **435,144
  passing comparisons**, with maximum normalized error 0.559745 and unchanged
  criteria. The capture completed in **104.031 s** with 24 native and eight Cells
  runs, no warnings, and 1120 observed native steps. This qualifies only the
  registered **1 ms seven-cell passive/blocked finite-bath case**, not biology,
  an equilibrated cell or general BETSE parity. The audit imports neither model
  nor NumPy/JAX; extra export links and rehashed-corruption tests are separate
  from the frozen capture checker. All **325 adapter tests pass**, including
  49 new checks (91.26 s; future full suites should run detached). All 352 accepted
  files / 51 production modules, both 119-file packets and all 35 v2 captured
  sources remain unchanged. No simulation or full production matrix was rerun.
  D072 now specifies the separate phase/control gates for the next intervention;
  no follow-up panel is launched.
- Completed refined capture, D070/REF-003d v2: the
  [finer-step panel](reports/REF003D_TRAJECTORY_REFINEMENT.md) used native
  **25, 12.5 and 6.25 µs**, with unchanged physics, Cells runs and all tolerances.
  Eight repeated native runs and all eight Cells runs reproduce their previous
  numerical records exactly. Workers remained within 90-second limits, 180 seconds
  total, CPUs 0–3 and the declared 128 MiB storage cap. The dated launch report
  remains historical; D071 above supplies the audited result. Stable, biological,
  organ, GPU and family-wide parity claims remain unchanged.
- Rejected first external trajectory, D069/REF-003d v1: all 24 native and eight
  Cells runs completed without warnings in **79.695 seconds**, but 36 of 129,384
  checks failed on shared-bath Na/K amount increments in native refinement and
  matched-constant cross-comparisons. D070's [saved-data audit](reports/ref-003d-failure-audit.json)
  exactly reproduces that rejection without model imports or integration; all
  119 packet files are [preserved](reports/ref-003d-v2-preservation.json). Endpoint
  errors approximately halve with native timestep; small per-cell discrepancies
  add in the shared bath, with much smaller material residuals. Extrapolation is
  diagnostic, not acceptance. The original protocol, failed packet and
  [launch report](reports/REF003D_TRAJECTORY_LAUNCH.md) remain unchanged.
- Completed external closeout, D068/REF-003c: the [independent audit and evidence checks](reports/REF003C_CLOSEOUT.md)
  pass all **171 short adapter tests in 20.98 seconds**, including 43 new
  actual-packet tests. The audit reproduces all 19,691 comparisons without
  importing either simulator; geometry/runtime metadata have independent anchors,
  and the one-centre failure is explicitly checked as a rejection. No simulation
  was rerun. All 352 accepted implementation files / 51 production modules remain
  unchanged; the prior 4190-test production matrix is preserved, not rerun.
  D069 now implements the [REF-003d observer/trajectory adapter](docs/BETSE_PASSIVE_TRAJECTORY_PLAN.md)
  and its prospective short baseline/blocked panel. D068 launched no follow-up
  job and established no trajectory, biology, stable or GPU promotion.
- Completed alignment capture, D067/REF-003c: the [explicit seven-cell capture](reports/REF003C_CLUSTER_ALIGNMENT.md)
  passes **19,691 numerical checks in 18.666 seconds**, covering native
  initialization, charge closure, instantaneous rates and prescribed single
  updates. All seven cells / 30 native faces correspond to the unchanged Cells
  finite-bath family on NumPy, eager JAX and compiled JAX. All 25 new preflight
  tests pass; the previous 103 adapter tests / 4190-test production matrix were
  not rerun. The native one-centre SVG probe fails triangulation; the old one-cell
  protocol stays rejected, not silently relaxed. All 352 accepted implementation
  files / 51 production modules remain unchanged. D068 now completes the separate
  saved-data audit, actual-packet regression and short closeout above; REF-003d's
  short native/Cells trajectory now has the separate D069 adapter/protocol above.
  The alignment itself establishes no full trajectory, biology or GPU claim.
- Previous external preparation, D066/REF-003b1: [native configuration and seeding](reports/REF003B1_PREPARATION.md)
  execute, but the pinned single-cell preset produces **seven cells / 30 membrane
  faces**. The unchanged one-cell guard rejects the fixture before voltage/RHS
  comparison or integration. A separate saved-data diagnostic confirms the
  mismatch; all 103 short adapter tests pass, not numerical-alignment acceptance.
  Five short attempts and their source capsules are retained. The default general
  network is now explicitly disabled in protocol revision 2; geometry still needs
  resolution. All 352 accepted implementation files / 51 production modules and
  the prior REF-003a evidence remain unchanged. D067 now records a failed native
  one-centre geometry probe and the separately specified seven-cell fallback.
- Completed external component comparison, D065/REF-003a: the [actual BETSE passive-law contact](reports/REF003A_PASSIVE_CONTACT.md)
  passes 54 frozen probes, 1047 tolerance comparisons and 15 exact-blocking checks
  in 4.681 seconds. All 332 installed upstream Python files match pinned v1.5.0.
  Matched constants give a maximum compiled-Cells/BETSE difference of 2.22e-16
  fmol/s; native-constant differences are retained and independently explained.
  The separate read-only audit and all 52 adapter/artifact tests pass. No
  production equation, existing test or runtime dependency changed; all 352
  captured implementation files and 51 production modules remain unchanged.
  This is instantaneous component correspondence, not a BETSE trajectory or
  biological validation. REF-003c adds explicit seven-cell initialization and
  prescribed updates; D071 now closes the separate bounded short trajectory above.
- Completed follow-through, D064/CORE-010: the [detached closeout](reports/CORE010_CLOSEOUT_HANDOFF.md)
  passed all three stages at 22:31 UTC on September 11, in 2154.841 seconds.
  The independent full audit, all **4190 regression tests** across six source
  contexts (no failures/errors/skips), and development acceptance closeout pass.
  Its saved result was inspected on September 12 before starting REF-003a.
  Stable production remains 0.14.0; accepted development remains 0.15.0.dev0.
- Completed acceptance slice, D063/CORE-010: [resource amendment v2](reports/CORE010_ACCEPTANCE_V2.md)
  registers a fresh full panel under a two-hour wall limit, with unchanged CPU
  lanes, artifact limit, case definitions and all scientific requirements.
  All 106 new profile/byte-exact tests and 228 combined preflight checks pass.
  The fresh acceptance-02 capture passed in 4381.787 seconds: 57 scalar runs,
  12 streams, 53 comparisons and 912 payload files. All fourteen eager cases
  completed; the 352 captured files remain unchanged. The separate full audit,
  new matrix and development closeout now pass. The prelaunch check authenticates
  733 of 740 existing files unchanged and exactly seven planned edits.
  The first stopped capture, its protocol and all 51 production modules remain
  unchanged; stable 0.14.0 and development 0.15.0.dev0 are not promoted.
  The capture completed detached without being killed or restarted. The user
  authorized the completed closeout and subsequent staged BETSE work. Future
  long jobs retain logs/results and return control without assistant polling;
  see [long-run instructions](AGENTS.md).
- Previous acceptance slice, D062/CORE-010: [recorded development qualification](reports/CORE010_ACCEPTANCE.md)
  adds independent saved-state/readout/cubic audits and rehashed-corruption tests,
  with all **122 new preflight checks passing**. The [prospective panel](docs/SPATIAL_EXTRACELLULAR_ACCEPTANCE.md)
  stopped at its 3600-second wall budget under a 2-GiB registration with 346 captured source/
  protocol files. All fourteen compiled/refined/fresh-process restart runs and
  all four scalar/eight original-resumed cohort streams are recorded. All 1,022
  scalar-restart arrays [match bytes exactly](reports/core-010-restart-byte-audit.json).
  Ten of fourteen eager cases completed; three were interrupted and one unstarted.
  The [stopped receipt](reports/core-010-stopped-preservation.json) preserves 880
  files / 77,070,916 bytes. All 53 completed scalar and 12 stream runs pass their
  independent subset audits, including all ten completed eager cases and all
  166 scalar/24 cohort checkpoints. All **4084 regression tests pass** across six
  source contexts, with no failures, errors or skips. The [tooling closeout](reports/core-010-audit-tooling-closeout.json)
  records 703 of 707 pre-existing files unchanged and four intended status-document
  edits, none missing. Full acceptance remains open; a separately budgeted complete
  run is next. All 51 production modules remain unchanged at 0.15.0.dev0;
  stable production is 0.14.0.
- Completed development integration, D061/CORE-010: [passive spatial integration](docs/SPATIAL_EXTRACELLULAR.md)
  is implemented as `spatial_extracellular@1` in **0.15.0.dev0**. Accepted 0.14.0
  and NUM-010 were [authenticated and archived before edits](reports/core-010-preservation.json).
  Cell/outside/membrane/face axes and all transfer/energy histories are explicit;
  a separate same-stage field block uses edge-list ownership and bounded dense
  solve scratch. The shared RK4, runner, checkpoint writers and window/cohort
  engines are unchanged. All [156 expanded preflight tests](reports/core-010-preflight-06.xml)
  pass, including fourteen full trajectories at selected/refined steps and short
  execution paths. All **3962 regression tests pass** across current and five
  preserved contexts, with no failures, errors or skips. The [implementation report](reports/CORE010_IMPLEMENTATION.md)
  and [development closeout](reports/core-010-implementation-closeout.json) record
  652 of 668 old files unchanged; sixteen expected documentation/API/version edits,
  none missing. CLI restart and full-window examples reproduce every saved array.
  This is a development implementation, **not formal CORE-010 release acceptance**.
  The frozen full production capture, independent saved-data/corruption audit,
  fresh-process panel replay and release closeout remain the next gate.
- Latest completed numerical gate, D060/NUM-010: the [short spatial panel](reports/NUM010_REFERENCE.md)
  passes all fourteen cases / 140 attempts, selecting **0.125 ms RK4/cubic with
  passing 0.0625 ms refinement**. Seven rejected coarse trials and two completed
  accuracy failures remain recorded. All fourteen complete-state restarts are
  bitwise equal; the [read-only audit](reports/num-010-artifact-audit.json) verifies
  339 payloads / 21 sources and all numerical verdicts without ODE execution.
  Analytic salt relaxation and 8/16/32-volume spatial refinement pass. All 190
  preflight tests pass (105 new NUM-010 plus 85 SPEC-009), and all **3806 regression
  tests pass** across current 0.14.0 and four preserved source contexts, with no
  failures, errors or skips. The [closeout](reports/num-010-closeout.json) preserves
  628 of 638 existing files byte-for-byte, with ten documentation-only updates
  and none missing. All 48 production modules stay unchanged at 0.14.0; no GPU,
  biology, organ or BETSE-parity acceptance is claimed.
- Latest completed design slice, D059/SPEC-009: the [spatial extracellular contract](docs/SPATIAL_EXTRACELLULAR_SPEC.md)
  and [independent instantaneous reference](reports/SPEC009_DESIGN_CHECK.md) pass.
  One cell plus near/far outside volumes exercises diffusion potentials and a
  membrane-free bulk compartment. Eight synthetic definitions / 44 evaluations
  pass 1,016 comparisons against separate 70-digit arithmetic. All 85 new unit
  tests and 229 targeted tests including existing production/audit checks pass.
  Exact arithmetic replay and the 830-payload/256-file production audit pass.
  All 48 production modules remain unchanged at 0.14.0; ten existing documents
  are updated. The full historical matrix was not rerun: its 3616-test result
  below belongs to CORE-009. No spatial trajectory, timestep, mesh, biological,
  BETSE-parity or GPU acceptance is claimed. See [closeout](reports/spec-009-closeout.json).
- Latest completed production slice, D058/CORE-009: the separately versioned
  [finite-outside CPU/JAX family](docs/FINITE_EXTRACELLULAR.md) is implemented for
  0.14.0 and [passes formal acceptance](reports/CORE009_ACCEPTANCE.md). Accepted 0.13.0 was
  [authenticated and preserved](reports/core-009-preservation.json) before edits.
  All 150 targeted tests pass; earlier test-fixture/environment failures are retained.
  Fourteen eager/JIT reference cases, full restart/branch/window/cohort paths and
  exact earlier-model replay pass. The read-only audit verifies 830 payloads,
  256 captured files and all 235 scalar/21 cohort checkpoints. The first full
  matrix passed 3612/3614 but two historical subprocess checks lacked their local
  interpreter path. The [launcher correction](reports/core-009-regression-correction.json)
  leaves production/original tests unchanged. Final acceptance has been recaptured:
  all 25,654 numerical arrays exactly match the first run, and the corrected
  historical context passes all 256 tests. The complete second matrix passes
  **3616 tests** across current 0.14.0 and four preserved source contexts, with
  no failures, errors or skips. The [release closeout](reports/core-009-closeout.json)
  preserves 545 of 559 old files byte-for-byte; fourteen expected documentation/
  API/version edits, none missing. No GPU or biological promotion.
- Previous completed numerical gate, D057/NUM-009 v2: the [amended finite-outside reference](reports/NUM009_REFERENCE_V2.md)
  passes all fourteen short cases / 112 attempts at the reference gate, selecting
  **1 ms RK4/cubic with passing 0.5 ms refinement**. Every inventory is explicitly
  integrated; only implicit derivative probes use conservation-tangent directions.
  No physics, cases, tolerances or exact-blocking checks changed. All three
  junction-only references retain exactly zero outside state/dense coefficients,
  and general blocked-owner preflights retain nonzero frozen inventories exactly.
  Full block/release, sub-step pulse and both tiny-outside cases now have complete
  evidence; the synthetic outside-K depletion witness is 80.8057%.
  Nine completed coarse accuracy failures are retained. The audit authenticates
  242 payloads / 43 sources and exactly replays 251400 observations.
  All **168 targeted and 3466 regression tests pass** across four source contexts:
  2077 current, 971 preserved 0.10.0, 205 preserved 0.11.0 and 213 preserved
  0.12.0, with no failures, errors or skips in that matrix. Of 529 pre-existing
  files, 520 remain byte-identical and nine have documentation-only updates.
  The [first failed attempt](reports/NUM009_REFERENCE.md), its 31 sources and
  174 payloads remain unchanged and still audit as stopped/not qualified.
  Its 13 prospective complete-session tests have no completed v1 evidence;
  they remain explicitly unexecuted, with a maintained v2 replacement and
  original v1 preflight/stopped-evidence tests running. Production stayed 0.13.0
  during that reference-only slice.
- Previous completed design slice, D055/SPEC-008: the [finite extracellular-compartment contract](docs/FINITE_EXTRACELLULAR_SPEC.md)
  and independent scalar reference pass **10,671 instantaneous checks** on nine
  synthetic cases; all **88 targeted tests pass**. Outside inventories, opposing
  capacitor charge, closed ionic free energy, shared-outside feedback and the
  maintained-bath reduction are explicit. The [result](reports/SPEC008_DESIGN_CHECK.md)
  retains the corrected checker and interrupted first regression attempt; the
  final four-context regression matrix passes all **3298 tests**, with no failures,
  errors or skips. Saved-reference replay is exact except for the timestamp and
  the previous production audit passes again. The [closeout](reports/spec-008-closeout.json)
  records 484 of 493 pre-existing files unchanged and nine documentation-only
  updates, with none missing. All 46 production modules remain unchanged at
  0.13.0. That design slice alone claimed no trajectory or production family;
  NUM-009 v2 now supplies the separate numerical reference result above.
- Previous production slice, D054/CORE-008: [physical ionic graphs](docs/PHYSICAL_IONIC_GRAPH.md)
  are implemented and [accepted](reports/CORE008_ACCEPTANCE.md) as
  `physical_ionic_graph@1` in 0.13.0. All **114 new targeted tests and 3210
  regression tests pass**, with no failures, errors or skips across four source
  contexts. Twelve frozen cases pass compiled/eager execution; 37 scalar outputs,
  two window runs and four original/resumed cohorts pass reference/accounting and
  exact replay checks. The read-only audit authenticates 600 payloads/223 captured
  files, and all 162 scalar/16 cohort checkpoints load with complete state.
  Accepted 0.12.0 was archived before edits; earlier-model regression is exact,
  and old scientific/pilot evidence is preserved in the
  [closeout](reports/core-008-closeout.json). No GPU, organ, arbitrary-graph
  timestep, biological or deferred E02 result is promoted.
- Next scientific gate: qualify the full-loop SIM-phase/profile/event bridge
  before an intervention response. REF-003e0 v2 preparation now passes;
  REF-003d v2 is already closed for its bounded passive fixture. The original
  trajectory and D073 preparation failures stay rejected; no accuracy gate is relaxed.
  The [audited alignment](reports/REF003C_CLOSEOUT.md)
  is not full time integration; the original one-cell REF-003b remains deferred.
  Stable promotion is separate; retain earlier budget stops as stops.
  The NUM-010 ceiling is 0.125 ms, not the old finite-outside 1 ms bound; maintained
  baths remain unchanged and GPU execution is a separate qualification.
- Previous completed qualification, D053/NUM-008: [short coupled physical ionic graphs](reports/NUM008_REFERENCE.md)
  pass the frozen numerical qualification: twelve cases, 84 graph attempts and
  five independent component solves. The selected **2 ms RK4/cubic** has passing
  1 ms refinement, with complete charge/material/energy accounting, independent
  blocking/release, analytic all-off gates and a 0.1 ms junction pulse.
  The read-only audit authenticates 194 payloads/26 sources and exactly replays
  256283 sampled rows. All **99 new tests pass**; the earlier 1580-payload
  production audit passes again. All **3096 regression tests pass** across three
  source contexts, with no failures, errors or skips. Of 444 pre-existing files,
  433 remain byte-identical and eleven have documentation-only updates; none
  is missing. All 44 production modules and earlier scientific/pilot evidence
  are preserved in the [closeout](reports/num-008-closeout.json).
  Production remained unchanged at 0.12.0 in that slice. **CORE-008** now completes
  the separate CPU/JAX production and restart/branch/cohort acceptance gate against
  this reference. No old timestep bound, GPU, arbitrary-graph, organ or biological
  capability is promoted; the pilot and deferred E02 campaign stay closed/deferred.
- Previous completed design, D052/SPEC-007: the [physical ionic graph contract](docs/PHYSICAL_IONIC_GRAPH_SPEC.md)
  and independent instantaneous reference pass **14,116 checks** on eight frozen
  definitions; all **114 new tests pass**. One/disconnected-cell reductions,
  heterogeneous mono/divalent pairs and stars, one-owned edge transfer, global
  material/charge/power and complete history separation are checked.
  [Final regression and preservation checks](reports/SPEC007_DESIGN_CHECK.md) pass:
  all **2997 tests** across three source contexts, with no failures or skips.
  The previous 1580-payload production audit passes again; all 44 production
  modules and earlier scientific/pilot evidence are unchanged.
  Production remained 0.12.0; that instantaneous slice claimed no graph trajectory,
  selected graph timestep, GPU or biological result. NUM-008 and CORE-008 now
  complete the separate short-trajectory and bounded production gates.
- Previous accepted production result, D051/CORE-007: the [state-bearing CPU/JAX channel](docs/VOLTAGE_GATED_MEMBRANE.md)
  is implemented under `voltage_gated_membrane@1` in 0.12.0, with separate gate/channel
  axes, three independent control groups and complete channel transfer history.
  All 113 targeted tests and **2883 regression tests pass**, with no failures or
  skips in the complete current/0.10.0/0.11.0 source-context matrix.
  [Production acceptance](reports/CORE007_ACCEPTANCE.md) is complete: all fourteen
  cases in eager/JIT, 43 scalar outputs, two window runs and four original/resumed
  cohorts pass independent reference/readout and exact replay checks. The accepted
  evidence has 1580 payloads, 204 captured files and 488 scalar/54 cohort checkpoints.
  Two interrupted scheduling/evidence-budget attempts remain recorded; revised CPU
  lanes and a prospective 1 GiB artifact allowance preserve all scientific criteria.
  Accepted 0.11.0 was archived before edits and its 226 scalar/22 cohort snapshots
  load under the old sources; multispecies replay is exact. No implicit migration,
  biological validation, GPU, organ, multirate or deferred E02 result is claimed.
  SPEC-007, NUM-008 and CORE-008 now complete the separate physical ionic graph
  contract, short-trajectory qualification and bounded production gates.
- D050/NUM-007: the [coupled cell/channel protocol](docs/VOLTAGE_GATED_NUMERICS.md)
  now [passes independent numerical qualification](reports/NUM007_REFERENCE.md):
  14 cases, 98 attempts, **0.5 ms coupled RK4/cubic** selected with a passing
  0.25 ms refinement. Six completed coarse accuracy failures and one rejected
  gate stage are retained. The read-only audit authenticates 214 payloads/19
  sources and replays 947939 sampled rows without rerunning the solver. All 205
  targeted tests and **2770 regression tests pass**, including 100 new tests,
  with zero failures or skips across current/preserved-source contexts.
  All 41 production modules and prior evidence remained unchanged in that slice.
  CORE-007 now completes the separate production extension and acceptance gate.
- D049/SPEC-006: the [first state-bearing channel contract](docs/VOLTAGE_GATED_CHANNEL_SPEC.md)
  and [independent reference checks](reports/SPEC006_DESIGN_CHECK.md) pass: one
  pinned Kv1.5-style channel, two retained gates, independent abundance/availability,
  explicit ionic charge and separate transfer ownership. All 7528 checks and
  105 new tests pass. Seven prescribed-voltage gate protocols are analytic test
  inputs, not whole-cell voltage clamp or coupled trajectory qualification.
  The old 10 ms step is not inherited; NUM-007 coupled references/refinement must
  precede CORE-007 production. All **2670 regression tests pass** (1699 current,
  971 preserved-reference), with no failures or skips. All 41 production modules
  and packaging remain unchanged, and the existing
  [773-payload production audit passes again](reports/spec-006-core006-audit.json).
- Previous accepted production result, D048/CORE-006: the [multispecies CPU/JAX family](docs/MULTISPECIES_MEMBRANE.md)
  is implemented and [accepted in 0.11.0](reports/CORE006_ACCEPTANCE.md). All
  **2565 tests pass**, including 117 new model/serialized-audit tests, across
  current-production and preserved-reference contexts with no skips. Both
  eager/JIT modes pass all 14 frozen cases; 43 scalar outputs and four cohort
  outputs pass independent readout/reference auditing, exact restart/branch and
  complete cohort replay. All 78 older scalar trajectories, 1777 windows and
  ten batches/44 worlds remain exact. The accepted 0.10.0 source was archived
  before edits; all 948 accepted scalar and 99 cohort checkpoints load under it
  and source-pair replay is exact. Current loaders refuse silent migration.
  [Retained test-context attempts](reports/CORE006_ACCEPTANCE_ATTEMPTS.md) explain
  why historical NUM-005 tests use their own preserved source/CPU environment.
  Old model laws, numerical bounds and the closed pilot are unchanged. SPEC-006
  now supplies the separate channel reference; it does not alter this accepted model.
- D047/NUM-006: [multispecies CPU trajectory qualification](reports/NUM006_REFERENCE.md)
  is complete on 14 frozen cases and 84 attempts. The predeclared rule selects
  0.01 s RK4 with cubic observations on this narrow panel; both finer trials pass.
  The strengthened read-only audit checks 186 payloads/13 archived sources and
  exactly replays 547572 sampled rows. All 446 targeted tests pass, including 94
  new tests; 284 pre-existing file hashes, including 39 production sources, are
  unchanged at that stage. CORE-006 now completes the separate production
  acceptance against this reference. Old timestep limits and the closed pilot stay unchanged.
- D046/SPEC-005: the [multispecies membrane contract](docs/MULTISPECIES_MEMBRANE_SPEC.md)
  and independent scalar reference are complete. [All 1,546 instantaneous checks
  and 352 targeted tests pass](reports/SPEC005_DESIGN_CHECK.md), including 113 new
  tests. The Na/K/Cl reduction, synthetic divalent fixture, explicit background
  charge, pump roles and material/charge/energy accounting are checked. All 39
  production sources remained unchanged. NUM-006 now supplies the separately
  qualified trajectories required before CORE-006 production assembly.
- D045/ARCH-003: the [BETSE capability roadmap](docs/BETSE_CAPABILITY_ROADMAP.md)
  and [multiscale/parallel execution design](docs/MULTISCALE_EXECUTION_ARCHITECTURE.md)
  are delivered. Seventeen scientific capability families are mapped to staged
  extensions, not marked implemented. Future parallel GPU work distinguishes
  independent ensembles, one partitioned interacting world and later multi-host
  execution. [SPEC-005's first one-cell CPU reference](docs/MULTISPECIES_MEMBRANE_NEXT.md)
  and subsequent numerical qualification and production acceptance are delivered.
- D044/BIO-003: the [first endpoint pilot is closed as descriptive](reports/BIO003_PILOT_CLOSEOUT.md).
  The supplement adds no C1-C3 numeric summaries or experiment-level records;
  recording assumptions remain unqualified. The -14.59 mV prediction versus
  approximately -18 mV is preserved, not retuned or promoted to biological
  validation. All 63 targeted tests pass again; all 39 production sources and
  old pilot data/code/artifacts remained unchanged; production stayed 0.10.0 at that stage.
  GPU architecture planning is active; GPU implementation, optimization and
  long NUM-005c2 execution remain paused/deferred with all existing gates intact.
- Phase: M0, M1a, M1b, M1c-a, CORE-003/004/005/006/007/008/009 and PERF-001/002/003 complete; M1/M1c remain in progress.
- Selected stack: Python and JAX; CPU first, GPU subsequently.
- Long-term target: data-defined whole-organ models and later interacting organs.
- Future execution requirement: computational multiscale with large-GPU options;
  no hardware target or distributed implementation is selected.
- Simulator implementation: version 0.14.0, eleven accepted bounded CPU/JAX families including the finite extracellular family; independent worlds and bounded scalar/cohort windows.
- Cells executions: E00 pulse, unchanged resume, and rechallenge engineering
  examples completed; E01 isolated E/M regulatory references and restarts verified.
  E02's passive engineering prerequisite now passes active/blocked, release,
  pulse, conservation, independent-reference, and exact-replay checks.
  CORE-003 composes reversible local reactions with species-specific transport
  on data-defined fixed graphs; independent numerical and accounting checks pass.
  MODEL-003 adds one physical membrane/bath cell; MODEL-004 adds a selective
  physical pair with an evolving junction gate and complete exchange/energy history.
- Previous production milestone: CORE-005b / VERIFY-010 / PERF-003 / D029 extends bounded
  execution to independent-clock cohorts, with reused parameters, active masks,
  device carry and compiled widths. Whole-round checks precede output; complete
  cohort checkpoints retain every local clock, anchor and typed diagnostic ledger.
  **1057 tests pass**, including 75 new cohort-window checks. All 78 scalar
  trajectories/3511 arrays and 10 ordinary batches/44 worlds/2042 arrays remain
  exact; all 1777 scalar recording chunks remain exact. New cohort acceptance
  covers 20 original/restarted runs, 88 worlds, 254 serialized per-world windows
  and 69 complete cohort snapshots containing 306 scalar snapshots.
  Accepted 0.9.0 was archived before edits; all 342 accepted scalar snapshots and
  10 cohort wrappers load, old-source window replay is exact, and implicit
  migration is refused. A test-fixture event-cursor mismatch was correctly refused
  and retained; its correction changed no production guard or equation.
  See the [cohort window guide](docs/WINDOWED_WORLDS.md) and
  [acceptance/profile](reports/CORE005B_ACCEPTANCE.md).
  Sixteen isolated CPU workers compare 4/16-world graphs and nominal pairs.
  Width-256 cohort history buffers are about 3.9× smaller than full batches on
  these ten-unit horizons; calls are faster than sequential scalar windows, but
  full batches finish sooner. Width 32 saves more history at substantially higher
  host/checking cost; source-pair process RSS does not improve. Both policies stay.
  No new dependency, physical EMT calibration, full source-assay parity,
  paper-table, PH, organ or GPU result is claimed. NUM-004's original native S12
  timing failure and passing refinements remain separate historical evidence.
- Source-study design history: SPEC-004 / D030 / R006 freezes [E02-SW1](docs/E02_SWITCHING_PROTOCOL.md),
  two fresh 500-unit preparations and 14 deterministic 1000-unit conditions.
  The primary topology is one recipient with two evolving neighbours; pairs and
  isolated cells are controls. Stable labels are not full-state equilibrium.
  All **1086 tests pass**, including 29 new protocol checks. All 39 production
  source hashes remain unchanged; no longer trajectory or
  prepared packet has been generated. [Design evidence](reports/SPEC004_PROTOCOL_CHECK.md).
- Source-graph reference history: NUM-005a / D031 implements [independent fixed-graph
  composition](docs/SOURCE_EMT_GRAPH_REFERENCE.md), with 45 native derivative
  inputs, 17 pair settings and 18,499 arithmetic/structural checks. All 118 new
  tests and the full **1204-test suite pass**. Stars, chains, disconnected components, independent controls and
  complete passive ledgers are checked; this is not production graph support or
  long-time qualification. A diagnostic-adapter indexing error is retained and
  corrected without changing inputs, equations or tolerances.
- Source-preparation numerical history: NUM-005b/D032 qualifies both fresh 500-unit preparations
  with Radau, BDF and refined Radau. All six trajectories, 65,740 comparison times
  and preparation criteria pass; full E/M packets are hash-pinned. The separate
  audit checks 421 payloads, 20 archived sources and unchanged production.
  Stable sampled phenotype coexists with measurable ionic drift, not equilibrium.
  All **1243 tests pass**, including 39 new infrastructure tests.
  [Preparation evidence](reports/NUM005B_PREPARATION.md).
- Long source-study history: NUM-005c1/D033 [long implicit references](docs/SOURCE_GRAPH_PATHS_REFERENCE.md),
  with exact prepared-state imports and a lossless bounded recorder. All 44 new
  engineering tests and 39 preparation regressions pass. The one-hour scientific
  session stopped as registered: 24 complete trajectories, eight qualified cases,
  one retained partial attempt and 17 unstarted attempts. Six conditions remained;
  the independent subset audit and all **1287 tests pass**, including 44 new tests.
  [Session evidence](reports/NUM005C1_LONG_REFERENCE.md).
  D034's [explicit continuation](docs/SOURCE_GRAPH_CONTINUATION.md) stops at the
  unchanged reference-agreement gate after nine complete new trajectories:
  blocked and ionic-only qualify (ten total); miRNA-only disagrees at 0.2263
  against the 0.1 limit. Three conditions were not started. Old evidence is
  unchanged, the shared 1 GiB quota is retained, and no retry occurs. Read-only
  auditing and all **1314 tests pass**, including 24 new continuation tests and
  three saved-sample diagnostic tests. [Continuation evidence](reports/NUM005C1_CONTINUATION.md).
  D035 now authorizes [one tighter BDF diagnostic](docs/E02_BDF_REFINEMENT_A1.md),
  with unchanged inputs/error targets and all old evidence retained. It meets
  the diagnostic agreement limit: 0.00533 against 0.1. The independent dense,
  sample-identity and score audit passes, as do all **1337 tests**, including 23
  new refinement checks.
  The original qualification count stays ten until a
  separate policy decision. No remaining control or RK4 run is part of this
  amendment. [A1 evidence](reports/NUM005C1_A1_BDF_REFINEMENT.md).
  D036 now approves [A2 amended reference acceptance](docs/E02_REFERENCE_POLICY_A2.md),
  the adopted case's observers and nine paths for the final three controls.
  All 116 targeted tests pass, including 25 new panel checks. The registered
  41-source, one-worker scientific session completes in 1087.264 seconds: all
  14 amended-policy conditions have passing comparisons and observers. The
  independent audit passes all nine new curves, 188,834 comparison times and
  four new observer sets. All **1362 tests pass**, including 25 new A2 checks.
  NUM-005c1 is complete under A2; original failed evidence and production remain
  unchanged. [A2 evidence](reports/NUM005C1_A2_REFERENCE_PANEL.md).
  NUM-005c2 still owns RK4 selection and candidate-owned continuations before
  MODEL-006 and ASSAY-002. The current production pair cannot
  supply a three-cell star by padding or batching pairs.
  [Numerical plan](docs/E02_SWITCHING_NUMERICS.md).
  D037 / NUM-005c2a now passes [bounded checked RK4 engineering](reports/NUM005C2A_CANDIDATE_ENGINEERING.md):
  all twelve 5.12-unit profiles and the independent 1313-payload/48-source audit.
  Widths 16 and 256 produce identical ordered numerical evidence; maximum
  normalized error is 0.00354 against 1. All **1415 tests pass** in 612.40 seconds,
  including 53 new checks; all 169 targeted tests pass. Complete checked runtime and full evidence
  volume do not establish long-study feasibility: width-256 planning estimates
  are 12.70 hours and 11.47 GB. Optimize repeated diagnostics and specify compact
  auditable evidence before another long-study decision. No long candidate study
  or timestep selection is authorized in this slice; production stays unchanged.
  D038 / NUM-005c2b now passes [cached bounded readout profiles](reports/NUM005C2B_DIAGNOSTIC_OPTIMIZATION.md):
  twelve matched short runs, exact D037 integration/sample identity, and bitwise
  scalar equivalence for every saved readout. The expanded audit passes 266
  payloads and 55 archived sources. Complete checked time across six inputs
  falls from 38.72 to 21.06 seconds (1.84×); isolated readout time falls from
  17.90 to 0.21 seconds. These are single short observations, not universal speedups.
  All **1540 regression tests pass** in 619.79 seconds, including 125 new checks;
  all 335 targeted tests also pass. Aggregate artifacts are 803,085,279 bytes.
  The [compact-evidence proposal](docs/E02_COMPACT_EVIDENCE_DESIGN.md) is separate
  and unimplemented; current profiles retain full numerical evidence. The
  improved 7.09-hour/11.505-GB planning estimate still does not establish a
  long-study fit. Prototype lossless reconstruction/auditing next, with remaining
  stage/cubic runtime costs kept explicit. Production remains unchanged.
  D039 / NUM-005c2c now passes [lossless recording and reconstructed auditing](reports/NUM005C2C_LOSSLESS_EVIDENCE.md):
  all twelve short profiles, exact D038 trajectory/sample identity and bitwise
  scalar readouts. The independent audit checks 266 payloads and 62 archived
  sources. Basis recording saves 57.8% of compressed trajectory payloads and
  16.7% of complete profile evidence; checked/audited runtime is essentially
  unchanged. All **1707 regression tests pass** in 640.43 seconds, including
  167 new checks; all 384 targeted tests pass. Aggregate retained artifacts are
  821,019,434 bytes. No compact long-study policy is adopted, and short-rate
  estimates still do not establish a fit. Next prototype lossless reference-backed
  comparison records, now 83.4% of basis-profile evidence, with exact reconstruction
  and dependency auditing. Runtime remains a separate concern. Prior sources,
  production and resource limits stay unchanged.
  D040 / NUM-005c2d now passes [reference-backed comparison profiles and auditing](reports/NUM005C2D_COMPARISON_RECORDING.md):
  twelve short profiles, exact D039 trajectory/sample fingerprints and bitwise
  scalar readouts. Independent auditing checks 290 payloads and 68 archived
  sources. Comparison payloads shrink 98.5%, total profile evidence 80.6%, with
  a 4.2% increase in complete checked time on these single short observations.
  All **1903 regression tests pass** in 686.87 seconds, including 196 new checks;
  all 541 targeted tests pass. Aggregate retained artifacts are 831,126,114 bytes. Short-rate
  planning estimates are now 1.863 GB of new evidence and 7.84 checked hours
  plus 16.01 audit hours, still not a fit. Next profile/cache integration-side
  graph evaluation with exact probes and all checks retained. Trajectory
  storage remains a separate gate; no long policy, run or production change.
  D041 / NUM-005c2e now passes [immutable scalar evaluation profiles and auditing](reports/NUM005C2E_INTEGRATION_EVALUATION.md):
  twelve short profiles, 1,440 exact complete-RHS probes, 720 exact decomposed
  evaluations and independent recomputation of all 30,720 stored stage slopes.
  All D040 logical evidence and checks remain unchanged. Measured RHS time falls
  13.9%, checked time 2.9%, and checked-plus-audited time 0.9%; these are single
  matched observations. All **2178 regression tests pass** in 749.16 seconds,
  including 275 new checks; all 816 targeted tests pass. The 304-payload/74-source audit passes,
  with 834,874,394 aggregate bytes and production unchanged. Its recommended
  next validation/audit profiling is now paused by D042; storage and long-study
  fit remain separate unresolved gates.
  Retain scalar execution for small jobs.
  Independently batched experiments
  are not interacting organs; biological exchange still needs explicit interfaces.
  Longer selected E02 switching and memory/relay protocols require their own
  pinned preparation, boundary operations and numerical qualification.
  Endogenous cancer-expression mechanisms remain outside the first source profile.
  Consult completed exploration updates when needed,
  without assuming live findings or changing that agent's experiments.
  Selected longer E02 switching remains before M1 closeout. Larger profiles,
  vectorized guard semantics, organs and GPU execution remain later work.

## Milestone status

This table and the following task board preserve the early CPU-build snapshot.
Their "planned" and "in progress" labels are historical; the
[current position](#current-position) above records subsequent spatial, assembly
and GPU work. They are retained for provenance, not maintained as a second
current-status board.

| Milestone | Status | Evidence or next action |
| --- | --- | --- |
| M0: project foundation | Done | Initial design and expanded multiscale contracts recorded; DOC-002 complete |
| M1: executable CPU foundation | In progress | Eleven accepted bounded CPU/JAX families. CORE-009 adds explicit finite-outside inventories through the shared engine; fourteen reference cases, full replay/accounting, 150 new targeted and 3616 five-context regression tests pass. NUM-009 v2's 1 ms RK4/cubic bound is only for its short panel. BIO-001/002/003 remain descriptive; long source candidate/graph/assay gates are unfinished/deferred |
| M2: memory and relay assays | Planned | Complete checkpoints, branching, controls, and selected E03-E06 assays |
| M3: fixed 2D tissue | Planned | E07 and separate viewer |
| M4: GPU execution | Planned | D045 separates single-GPU qualification, multi-GPU ensembles/coupled partitions and later multi-host execution; architecture only so far, representative accuracy and scaling measurements required |
| M5: growth and turnover | Planned | Explicit physical model and E08 |
| M6: multiscale tissue unit | Planned | Fine/coarse interfaces, fields, numerical refinement, response and cost validation |
| M7: first whole-organ preset | Planned | Select simplest useful organ/function; define scope and validation before implementation |
| M8: coupled organ presets | Planned | Explicit exchange models and coupled-function checks; not independent batching |

## Task board

| ID | Task | Status | Evidence / dependency |
| --- | --- | --- | --- |
| BIO-001 | Select and document the first experimental one-cell benchmark | Done — specification and provisional data only | [Specification](docs/BIOLOGICAL_BENCHMARK_001.md), [data card](data/biology/bonzanni2020_rptec_v1/README.md), [curation report](reports/BIO001_DATASET_REVIEW.md); source figures, three approximate endpoints, two quarantined recipes, retrospective split and offline integrity checks; no fit or biological verdict |
| BIO-002 | Specify the measurement boundary and evaluate a small endpoint comparator | Done — descriptive comparison only | D043 [reference](docs/CONDITIONED_VOLTAGE_REFERENCE.md) and [result](reports/BIO002_CONDITIONED_VOLTAGE.md); C1/C2-only fit predicts C3 at -14.59 mV versus approximately -18 mV; reading bounds retained, 12 independent arithmetic checks and all 63 targeted tests pass; production/data unchanged, no biological acceptance |
| BIO-003 | Review experimental uncertainty and recording-boundary support | Done — pilot closed as descriptive | D044 [closeout](reports/BIO003_PILOT_CLOSEOUT.md) and licensed source attachment; full one-page supplement reviewed, no C1-C3 numeric summaries or experiment grouping recovered. Assumptions remain unqualified; 63 targeted tests pass, no retuning/biological acceptance. Reopen only for new evidence or a separately scoped benchmark |
| DOC-001 | Review scoped source material and record the initial design | Done | [Document index](README.md); local links, formatting, and status checked |
| DOC-002 | Incorporate R002, organ composition, and one-cell-first plan | Done | Nine documents; all 54 local link occurrences resolve; headings, tables, fences, whitespace, and status reviewed |
| ARCH-001 | Review engineering boundaries before source-assay expansion | Done | D016 and [engineering gate](docs/ENGINEERING_GATE.md); current code limits, reusable composition scope, and three-layer acceptance recorded; no package change |
| ARCH-002 | Adopt BETSE/software architecture lessons | Done | R004/D018 and [review](docs/BETSE_DESIGN_REVIEW.md); explicit membranes/bath, charge/energy, gates versus controls, preparation and fidelity boundaries; no new dependency |
| ARCH-003 | Map BETSE scientific coverage into the multiscale and parallel GPU architecture | Done — design only | D045/R009; [capability roadmap](docs/BETSE_CAPABILITY_ROADMAP.md), [execution architecture](docs/MULTISCALE_EXECUTION_ARCHITECTURE.md) and next-build brief. Pinned v1.5.0, 17 feature families, staged CPU-first work, independent versus interacting multi-GPU modes and later multi-host execution; no parity/runtime claim |
| SPEC-001 | Specify the first physical bioelectric cell | Done | [Contract](docs/BIOELECTRIC_CELL_SPEC.md), independent calculator and [74 instantaneous checks](reports/BIOELECTRIC_DESIGN_CHECK.md); no trajectory/production model claim |
| SPEC-002 | Specify stateful selective physical contact and its source boundary | Done | D021; [pair contract](docs/SELECTIVE_CONTACT_SPEC.md), [source map](docs/SOURCE_COUPLING_MAP.md), 709 instantaneous checks, 36 new tests; no production or coupled trajectory claim |
| SPEC-003 | Specify the complete source-compatible coupled model and reference inputs | Done | D024; [contract](docs/SOURCE_EMT_PAIR_SPEC.md), prepared full packets, frozen 14 cases/17 native settings, 3192 instantaneous checks and 65 new tests; production unchanged |
| SPEC-004 | Pin a selected longer E02 switching and preparation protocol | Done | D030/R006; [E02-SW1](docs/E02_SWITCHING_PROTOCOL.md), frozen two preparations/14 conditions, explicit observers and [independent plan](docs/E02_SWITCHING_NUMERICS.md); 29 new static checks and all 1086 tests pass, 39 production hashes unchanged; no trajectories or prepared outputs |
| SPEC-005 | Specify multispecies membrane assembly and an independent instantaneous reference | Done — design/reference only | D046 [contract](docs/MULTISPECIES_MEMBRANE_SPEC.md), frozen two-case panel and [result](reports/SPEC005_DESIGN_CHECK.md); 1546 instantaneous checks, 352 targeted tests including 113 new. Explicit charge, role-bound pump, species permutations and inactive divalent charge pass; 39 production files unchanged |
| SPEC-006 | Specify one state-bearing physical membrane channel and independent gate reference | Done — design/reference only | D049/R010 [contract](docs/VOLTAGE_GATED_CHANNEL_SPEC.md), [evidence](reports/SPEC006_DESIGN_CHECK.md); 7528 checks, seven analytic gate protocols, instantaneous ionic accounting and all 2670 regression tests pass, including 105 new. Two retained gates, independent mechanism/control ownership; no production channel, implicit clamp or biological calibration |
| SPEC-007 | Specify data-defined physical ionic graph composition | Done — design/reference only | D052 [contract](docs/PHYSICAL_IONIC_GRAPH_SPEC.md), [result](reports/SPEC007_DESIGN_CHECK.md); 14116 instantaneous checks/eight definitions and all 2997 regression tests pass, including 114 new. Shared bath, diagonal capacitance, local/edge ownership, pairs/stars and ledger-only cycle witness; production remains 0.12.0 and the 1580-payload prior audit passes again |
| SPEC-008 | Specify one finite extracellular compartment | Done — design/reference only | D055; [contract](docs/FINITE_EXTRACELLULAR_SPEC.md), [result](reports/SPEC008_DESIGN_CHECK.md). 10671 checks/nine definitions and all 3298 regression tests pass, including 88 new. Explicit outside inventories, floating capacitor-star charge, closed ionic energy, 1/volume response and exact maintained initial reduction. Corrected all-off assertions and prior evidence retained; no production or trajectory claim |
| NUM-006 | Qualify multispecies membrane trajectories in the new regime | Done — independent numerical qualification | D047 [protocol](docs/MULTISPECIES_NUMERICS.md) and [result](reports/NUM006_REFERENCE.md); 14 frozen cases, 84 attempts, passing Radau/BDF/refinement and 0.01/0.005/0.0025 s RK4. Select 0.01 s with cubic observations only for this panel. Revision-2 audit passes 186 payloads/547572 replayed rows; 446 targeted tests, production unchanged |
| NUM-007 | Qualify coupled multispecies cell plus state-bearing channel dynamics | Done — independent CPU numerical qualification | D050 [protocol](docs/VOLTAGE_GATED_NUMERICS.md), [result](reports/NUM007_REFERENCE.md); 14 cases/98 attempts, selected 0.5 ms RK4/cubic with passing 0.25 ms refinement, complete gate/channel histories and domain checks. Six accuracy failures/one rejected coarse stage retained; 214-payload/19-source audit replays 947939 rows; all 2770 regression and 205 targeted tests pass, including 100 new |
| NUM-008 | Qualify short coupled physical ionic graph trajectories | Done — independent CPU numerical qualification | D053 [protocol](docs/PHYSICAL_IONIC_GRAPH_NUMERICS.md), [result](reports/NUM008_REFERENCE.md); twelve cases/84 graph attempts plus five independent component solves, 2 ms RK4/cubic with passing 1 ms refinement. All histories, event timing, real-stage/cubic domains and energy checks pass; 194-payload/26-source audit replays 256283 rows. All 3096 regression tests pass, including 99 new; production remains 0.12.0 and old evidence is preserved |
| NUM-009 | Qualify short finite extracellular-compartment trajectories | Done — independent CPU numerical qualification | D057 [amendment](docs/FINITE_EXTRACELLULAR_NUMERICS_V2.md), [result](reports/NUM009_REFERENCE_V2.md); fourteen cases / 112 attempts, explicit inventories and conservation-tangent reference probes. Select 1 ms RK4/cubic with passing 0.5 ms refinement; synthetic outside-K depletion 80.8057%. Nine coarse accuracy failures retained; no rejected stages. Audit authenticates 242 payloads / 43 sources and replays 251400 rows; 168 targeted and 3466 regression tests pass. V1 failure/evidence and production unchanged |
| CORE-001 | Pin a Python/JAX CPU environment and package entry points | Done | Isolated .venv, [dependency lock](requirements-lock.txt), editable install, CLI and pip checks |
| REF-001 | Pin source and define the smallest isolated fixture contract | Done | Clean BITSEY checkout; E/M native helpers, 36 derivative fixtures, scaling/approximation/source hashes; [contract](docs/EMT_REFERENCE.md) |
| REF-002 | Resolve upstream implementation redistribution terms | Planned | No license file found in pinned tree; no code vendored. Resolve before any upstream code redistribution; independent equation implementation is separately documented |
| CORE-002 | Implement model/experiment/execution definitions and explicit state | Done | [Specifications](src/cells/core/specs.py), explicit array state, strict schema/domain tests; M1a subset |
| CORE-003 | Compose local reactions and graph transport on shared state | Done | reaction_transport@1; species/cell/edge axes, data-defined fixed graph, independent contacts, shared-stage contributions; [contract](docs/REACTION_TRANSPORT.md) and [acceptance](reports/CORE003_ACCEPTANCE.md) |
| CORE-004 | Execute explicitly independent worlds on the shared engine | Done | D027; [guide](docs/INDEPENDENT_WORLDS.md), compatible shapes with separate local clocks/parameters/IDs/controls, conservative compiled mapping, complete cohort replay, no cross-world exchange and aggregate preallocation guards |
| CORE-005a | Specify and implement single-world bounded windows and selectable recording | Done | D028; [contract](docs/WINDOWED_EXECUTION.md) and [acceptance](reports/CORE005A_ACCEPTANCE.md), lazy exact grid, shared checks, complete restart and incremental recording; all accepted scalar/cohort arrays unchanged |
| CORE-005b | Extend bounded windows to independently clocked cohorts | Done | D029; [guide](docs/WINDOWED_WORLDS.md) and [acceptance](reports/CORE005B_ACCEPTANCE.md), independent round clocks, prepared execution reuse, complete cohort restart, aggregate guards and shared incremental recording |
| CORE-006 | Implement a versioned multispecies membrane assembly through the shared engine | Done — bounded CPU/JAX acceptance | D048, Cells 0.11.0; [acceptance](reports/CORE006_ACCEPTANCE.md), 14 frozen cases in eager/JIT, 43 scalar and four cohort outputs, exact fresh-process replay/branch, 773-payload audit and 2565 passing tests including 117 new. All older scalar/window/batch regressions exact; 0.10.0 source and checkpoint replay preserved; no universal plugin framework |
| CORE-007 | Implement a versioned physical membrane-channel assembly | Done — bounded CPU/JAX production | D051, 0.12.0; [implementation](docs/VOLTAGE_GATED_MEMBRANE.md), [acceptance](reports/CORE007_ACCEPTANCE.md). All 113 targeted and 2883 regression tests pass. Fourteen cases in eager/JIT, 14 exact fresh-process restarts, branch and window/cohort checks pass; 1580 payloads, 204 captured files, 488 scalar/54 cohort checkpoints. Preserved 0.11.0 checkpoints/replay and old-model regressions pass; old timestep limits unchanged |
| CORE-008 | Implement and accept a new physical ionic graph family | Done — bounded CPU/JAX production | D054, 0.13.0; [guide](docs/PHYSICAL_IONIC_GRAPH.md), [evidence](reports/CORE008_ACCEPTANCE.md). Twelve cases in eager/JIT, 37 scalar outputs, two window runs, four original/resumed cohorts and complete replay/accounting pass. All 114 targeted and 3210 regression tests pass; 600 payloads/223 captured files, 162 scalar/16 cohort checkpoints. Accepted 0.12.0 and older scientific evidence preserved; old limits unchanged |
| CORE-009 | Implement a separately versioned finite extracellular family | Done — bounded CPU/JAX production | D058, 0.14.0; [guide](docs/FINITE_EXTRACELLULAR.md), [evidence](reports/CORE009_ACCEPTANCE.md), [closeout](reports/core-009-closeout.json). Fourteen cases, 43 scalar outputs, two windows, four original/resumed cohorts; all 150 targeted and 3616 regression tests pass. All 235 scalar/21 cohort checkpoints load. A retained historical launcher failure is corrected without production changes; all 25,654 rerun arrays are exact. Earlier evidence and physics remain preserved |
| SPEC-009 | Specify minimal spatial extracellular transport and electrical closure | Done — design/instantaneous reference only | D059/R011; [contract](docs/SPATIAL_EXTRACELLULAR_SPEC.md), [result](reports/SPEC009_DESIGN_CHECK.md). Eight definitions / 44 evaluations, 1016 independent Decimal comparisons, 85 new unit and 229 targeted tests pass. Charge-component/current closure, membrane-free bulk, one-owned faces and energy checked; production/evidence unchanged, no full-matrix rerun or trajectory claim |
| NUM-010 | Qualify short spatial extracellular trajectories and electrical constraints | Done — bounded CPU reference only | D060; [result](reports/NUM010_REFERENCE.md), [closeout](reports/num-010-closeout.json); 14 cases / 140 attempts, 0.125 ms with passing 0.0625 ms refinement, 14 bitwise restarts, analytic/spatial gates, 339 payloads / 21 sources, 190 preflight and 3806 regression tests pass; no inherited 1 ms bound |
| CORE-010 | Implement a separately versioned spatial extracellular family | Done — bounded development acceptance; no stable promotion | D061–D064; [v2 report](reports/CORE010_ACCEPTANCE_V2.md), [closeout](reports/core-010-v2-closeout.json). 57 scalar runs/12 streams independently audit; all 4190 six-context regression tests pass; 352 captured files/51 production modules unchanged. Accepted development 0.15.0.dev0, stable 0.14.0 |
| MODEL-001 | Implement the synthetic one-cell source/decay fixture | Done | [Model kernel](src/cells/models/source_decay.py); analytic E00 checks |
| NUM-001 | Implement and verify the first numerical method and pulse schedule | Done | Generic RK4, event-split grid, fourth-order refinement, off-grid/sub-step pulse checks |
| OBS-001 | Add read-only trajectories and a resolved run manifest | Done | Sampling independence, labelled interpolation, numeric artifacts, source/config hashes |
| RUN-001 | Add complete snapshots, restart, and controlled branching for M1a | Done | Exact restart at five boundaries, fresh-process CLI checks, compatible future branches; passive cell/edge extension verified in CONTACT-002 |
| VERIFY-001 | Complete first-version acceptance and inspectable examples | Done | [Acceptance](reports/M1A_ACCEPTANCE.md); 88 tests, three saved runs, all artifact hashes and replay checks |
| MODEL-002 | Add source-backed isolated regulation | Done | emt_mirna@1, model registry, fixed Snail, primary/derived split, 10000-unit E/M comparisons, refinement and exact restart |
| NUM-002 | Establish independent bioelectric trajectories and numerical domain | Done | [Numerical contract](docs/BIOELECTRIC_NUMERICS.md), [qualification](reports/NUM002_REFERENCE.md); 18-case panel, refinement, energy/accounting, control/observation checks, slow passive reference; bounded RK4/5 ms plus cubic observations, not production/JAX parity |
| NUM-003 | Qualify independent physical-pair trajectories and numerical domain | Done | [Numerical contract](docs/SELECTIVE_CONTACT_NUMERICS.md), [qualification](reports/NUM003_REFERENCE.md); 20 frozen cases, Radau/BDF/refinement, cubic interior/domain and independent native-state audit; RK4/1 ms candidate, not production/JAX acceptance |
| NUM-004 | Qualify complete source-compatible pair trajectories and observations | Done | D025; [contract](docs/SOURCE_EMT_PAIR_NUMERICS.md), [qualification](reports/NUM004_REFERENCE.md); 14 cases at RK4/0.01 nominal units plus half-step, 44 native paths and explicit release-clock refinement; original failure retained, production unchanged |
| NUM-005 | Qualify independent fixed-graph preparation and E02-SW1 trajectories | In progress | Composition, preparations, A2 long references and bounded short candidate engineering pass; runtime/storage work and full candidate qualification remain; no selected long-time production method |
| NUM-005a | Verify independent graph composition and native instantaneous witnesses | Done | D031; [reference](docs/SOURCE_EMT_GRAPH_REFERENCE.md), [evidence](reports/NUM005A_REFERENCE.md); 45 native cases, 17 pair settings, 18,499 checks, 118 new tests and 1204 total pass; native diagnostic-adapter failure retained; no integration |
| NUM-005b | Qualify bounded independent 500-unit preparation | Done | D032; [preparation evidence](reports/NUM005B_PREPARATION.md); six trajectories, 65,740 comparison times and frozen preparation criteria pass; complete packets hash-pinned, 421 payloads/20 archived sources audited. 39 new tests and 1243 total pass; ionic drift retained, no equilibrium or connected-path claim |
| NUM-005c | Qualify long E02-SW1 reference paths and numerical candidate | In progress | c1 long implicit references/readouts, then c2 registered RK4 study, selected/half-step trials and candidate-owned preparation continuations under unchanged budgets |
| NUM-005c1 | Qualify all 14 long implicit reference trios and retain readouts | Done under A2 | D036 [A2 evidence](reports/NUM005C1_A2_REFERENCE_PANEL.md); all 14 conditions/observers, independent auditing and 1362 tests pass. Ten original trios plus four using tighter BDF; original failed campaign remains unchanged. RK4/production gates remain separate |
| NUM-005c1-A1 | Diagnose the retained disagreement with one tighter BDF reference | Done — diagnostic only | D035 [A1 evidence](reports/NUM005C1_A1_BDF_REFINEMENT.md); required score 0.00533 versus unchanged 0.1 limit; 103,243 four-input comparison times and independent curve/grid/state/score audit pass. All 1337 tests passed, including 23 new checks. Original failure/count preserved in that diagnostic; A2 acceptance is a separate subsequent decision |
| NUM-005c1-A2 | Adopt amended accuracy policy, record observers and complete three remaining controls | Done | D036 [A2 evidence](reports/NUM005C1_A2_REFERENCE_PANEL.md); nine new paths, 188,834 new comparison times, 4028 new observer times, independent audit and all 1362 tests pass. Aggregate 715,966,189 bytes; no retry, original failure reclassification or production change |
| NUM-005c2 | Select and qualify the long-time candidate, including preparation sensitivity | Deferred by D042 — unfinished | c2a–c2e establish checked bounded execution, exact optimizations and lossless evidence, not a long-study resource fit. Optimization is paused; runtime/storage decisions remain necessary before the study, selected/half trials and candidate-owned continuations. No long candidate study or solver selection yet |
| NUM-005c2a | Build and benchmark bounded checked RK4 on short fixtures | Done — short engineering only | D037 [evidence](reports/NUM005C2A_CANDIDATE_ENGINEERING.md); twelve profiles, exact width/restart evidence, all 1415 tests including 53 new checks, 1313 audited payloads, 137.557-second session and 783,644,175 aggregate bytes. Current full evidence/runtime policy does not establish long-study feasibility |
| NUM-005c2b | Optimize bounded diagnostic readouts and specify compact-evidence options | Done — short engineering and design only | D038 [evidence](reports/NUM005C2B_DIAGNOSTIC_OPTIMIZATION.md); twelve short profiles, 1.84× aggregate checked-time ratio, exact numerical/readout evidence, 266-payload/55-source audit, all 1540 tests and 335 targeted tests pass, including 125 new checks. Compact options were design-only at this gate; c2c implements a selected prototype, production unchanged |
| NUM-005c2c | Prototype lossless evidence redundancy removal and reconstructed auditing | Done — short prototype only | D039 [evidence](reports/NUM005C2C_LOSSLESS_EVIDENCE.md); twelve profiles, exact full/basis decoding and complete committed restart, independent 266-payload/62-source audit, all 1707 tests and 384 targeted tests pass, including 167 new checks. Trajectory payloads shrink 57.8%, complete profile evidence 16.7%; runtime essentially unchanged. No compact long policy, budget change or long run |
| NUM-005c2d | Prototype lossless reference-backed comparison records | Done — short prototype only | D040 [evidence](reports/NUM005C2D_COMPARISON_RECORDING.md); twelve profiles, exact D039 logical arrays and scalar readouts, 290-payload/68-source dependency audit, all 1903 regression tests and 541 targeted tests pass, including 196 new checks. Comparison payloads shrink 98.5%, total profile evidence 80.6%; checked time increases 4.2%. No long policy, run or production change |
| NUM-005c2e | Profile/cache integration-side graph evaluation with unchanged checks | Done — short prototype only | D041 [evidence](reports/NUM005C2E_INTEGRATION_EVALUATION.md); twelve profiles and 304-payload/74-source audit pass, with all 30,720 stored stage derivatives independently exact. All 2178 regression tests and 816 targeted tests pass, including 275 new checks. RHS time falls 13.9%, checked time 2.9%, checked-plus-audited time 0.9%. No guard, evidence, production or long-policy change |
| NUM-005c2f | Profile validation and independent-audit costs without reducing coverage | Deferred — optimization paused | D041 proposal retained; D042/D045 keep this work paused. Any resumption must preserve all domain/exponent/accounting/blocked-history/extrema checks and independent verification. Trajectory storage and long-study registration remain separate gates |
| MODEL-003 | Implement the specified one-cell physical model | Done | bioelectric_cell@1; membrane/bath layout, charge-derived voltage, GHK leaks/reference pump, independent controls, checked stages, cubic observations and exact replay; [guide](docs/BIOELECTRIC_CELL.md) |
| MODEL-004 | Implement the qualified physical gated pair | Done | bioelectric_pair@1; reusable membrane/contact composition, full gate/transfer/diagnostic state, independent control PyTrees, checked RK4/1 ms, extrema-checked cubic observations, complete replay; [guide](docs/BIOELECTRIC_PAIR.md) |
| MODEL-005 | Implement the numerically qualified source-compatible pair | Done | bitsey_emt_pair@1; typed ionic/regulatory state and histories, source laws, pure EMT reuse, independent route controls, checked RK4/0.01 nominal units, exact event/replay semantics; [guide](docs/SOURCE_EMT_PAIR.md) |
| MODEL-006 | Extend qualified source-coordinate composition to fixed graphs | Planned | NUM-005; preserve 0.10.0, explicit new model identity, local processes once per cell, per-edge controls/ledgers and shared scatter; no assay-specific solver branches |
| REF-003 | Capture a bounded corresponding BETSE reference | Scoped passive and finest-held response independently closed | D064–D086; [plan](docs/BETSE_REFERENCE_PLAN.md), [joint held-response completion](runs/ref-003e1-refined-response-audit-2026-09-13/audit-01/completion.json). All 4173 diagnostic failures retained; no general waveform convergence or biology claim. Synthetic pump remains non-equivalent |
| REF-004a | Direct isolated voltage-gated channel contact | Independently closed in the registered isolated scope | D087–D088; [closeout](reports/REF004A_KV1P5_CLOSEOUT.md). 11,266 independently rebuilt checks, 102 tests, unchanged source/evidence. No coupled-cell, biology or GPU qualification |
| REF-004b | Couple the channel to cell/bath transport | Independently closed in the fixed 2 ms four-control scope | D089–D096; [closeout](reports/REF004B_FEEDBACK_CLOSEOUT.md). 5,806,006 independently reconstructed comparisons, zero mismatches, 24 complete checkpoints; fourteen coarse misses preserved. Not broad BETSE parity or biology |
| REF-004c | Test equal-current, different-history coupled responses | Independently closed in the fixed 2 ms scope | D097–D100; [closeout](reports/REF004C_PAIRED_HISTORY_CLOSEOUT.md). 240.629 s, 8,036,300 independent comparisons, zero mismatches; 24 complete checkpoints and 21 coarse misses preserved. Not biological memory or broader parity |
| REF-004d | Test channel suppression/release with preserved hidden state | Fixed 2 ms numerical scope independently closed | D101–D106; [timed closeout](reports/REF004D_TIMED_RELEASE_CLOSEOUT.md). 15,042,946 independent comparisons / 182 groups, zero mismatches; all 49 coarse misses and old rejected attempts retained. No biological, broader-family or GPU qualification |
| REF-005a | Substrate-dependent Na/K pump correspondence | Instantaneous source contact independently closed | D107–D108; [closeout](reports/REF005A_PUMP_CONTACT_CLOSEOUT.md). 1,240 comparisons / 248 raw triplets, zero mismatches; not a production mechanism or native whole-cell trajectory |
| SPEC-010 / NUM-011 | Conservative kinetic pump integration and coupled numerical gate | Six-case numerical scope independently closed; process kernel added | D109–D111; [coupled closeout](reports/NUM011_COUPLED_CLOSEOUT.md), [process contract](docs/KINETIC_PUMP_PROCESS.md). 4,070 comparisons / 3,756 physical records / 12 restarts; 32 process + 10 gate tests. Process qualification/regression pending; versioned configuration and ordinary-runner integration remain |
| REF-006 | Junction transport and dynamic gating correspondence | Source review and staged plan | D107; [junction plan](docs/BETSE_GAP_JUNCTION_PLAN.md). Held-open conservative transport first; init/state/blocking and per-ion gate-call semantics need actual lifecycle measurement |
| BIO-NEXT | Original experimental-data benchmark | Candidate records, not a runnable or accepted experiment | D107; [biological plan](docs/BETSE_BIOLOGICAL_BENCHMARK_PLAN.md). Original-versus-secondary permeability discrepancy, uncertainty definitions and chloride transport remain open |
| REF-003a | Execute a bounded unmodified BETSE passive-law comparison | Done — component only | D065; [result](reports/REF003A_PASSIVE_CONTACT.md). 54 probes, 1047 tolerance/15 exact-blocking checks, separate artifact audit, 52 passing adapter tests; 4.681 s capture. Native/matched constants separate; no production changes or trajectory |
| REF-003b | Align and compare one passive cell in both full simulators | Deferred — no matching native one-cell fixture | D066–D067; [preparation](reports/REF003B1_PREPARATION.md), [SVG finding/fallback](reports/REF003C_CLUSTER_ALIGNMENT.md). Native preset seeds seven cells; one-centre SVG fails triangulation. Seven-cell work has separate REF-003c/d identities; no relabelled one-cell acceptance |
| REF-003b1 | Verify native configuration, geometry and charge/transfer alignment | Recorded — one-cell fixture rejected | [Design](docs/BETSE_INITIALIZATION_ALIGNMENT.md), [diagnostic audit](reports/ref-003b1-preparation-audit.json). Original guard/criteria/capsules unchanged; 103 prior software/negative-evidence tests pass. One-cell voltage/RHS paths remain unexecuted |
| REF-003c | Compare explicitly seven cells: initialization, charge and prescribed updates | Done — bounded alignment only | D067–D068; [capture](reports/REF003C_CLUSTER_ALIGNMENT.md), [closeout](reports/REF003C_CLOSEOUT.md). 19,691 comparisons replay exactly; 171 short adapter tests including 43 actual-packet checks pass. Existing finite-bath model and all accepted sources unchanged. No full trajectory |
| REF-003d | Compare a short native seven-cell transient against Cells | Done — bounded v2 trajectory; v1 remains rejected | D069–D071; [plan](docs/BETSE_PASSIVE_TRAJECTORY_PLAN.md), [closeout](reports/REF003D_CLOSEOUT.md). All 435,144 v2 comparisons and 325 adapter tests pass; unchanged physics/criteria/Cells runs. Both 119-file packets and 35 captured v2 sources preserved. Selected native 6.25 µs / Cells 50 µs, 1 ms passive/blocked fixture only; no biology or family-wide parity |
| REF-003e | Specify corresponding native/Cells permeability intervention semantics | Design checks pass; no trajectory registered | D072; [design](docs/BETSE_INTERVENTION_PLAN.md), [review](reports/REF003E_INTERVENTION_DESIGN.md). 38 tests; SIM-only dispatch, raw/elapsed clock conversion, additive smooth pulse, right-continuous held controls and independent refinement axes |
| REF-003e0 | Bridge INIT-qualified preparation to SIM without intervention | V2 preparation passes; full-loop bridge pending | D073–D074; [retained failure](reports/REF003E0_PHASE_PREFLIGHT.md), [v2 result](reports/REF003E0_PROFILE_BRIDGE.md). Six preparations / 30 direct dispatches, four exact control comparisons, 87 passing focused tests. Default profile prerequisite explicit, partial state durable. No integration or full-loop observer qualification |
| REF-003e1 | Compare a native-step-held suppression/recovery response | Planned after e0 closeout | Preserve input law, explicitly map clocks, sample controls before integration, refine Cells within held intervals and refine forcing separately; not continuous forcing or an exact square block |
| VERIFY-002 | Complete M1b acceptance and preserve M1a artifacts | Done | [Acceptance](reports/M1B_ACCEPTANCE.md); 119 tests, source/solver comparisons, checked artifact hashes; archived 0.1.0 source |
| CONTACT-001 | Add two cells and one active/blocked contact through source validation | In progress | CONTACT-002 complete; CONTACT-003 source-selective E02 validation remains |
| CONTACT-002 | Implement and verify passive reciprocal exchange | Done | passive_pair@1, separate coupling module, cell/edge capacities and IDs, 69 unit cases, CLI integration, five saved runs; [acceptance](reports/M1C_A_ACCEPTANCE.md) |
| CONTACT-003 | Specify and validate source-selective bioelectric coupling | In progress | SPEC-003, NUM-004 and MODEL-005 accept the bounded first nominal profile. Longer selected E02 switching protocols still require qualification; physical pair and cancer-expression strategies are distinct profiles |
| VERIFY-003 | Complete M1c-a acceptance and preserve earlier versions | Done | 189 tests; pair matrix reference/refinement; complete synthetic/regulatory regressions; 0.2.0 source archive and old snapshot checks |
| VERIFY-004 | Verify composition, regress earlier models, and preserve 0.3.0 | Done | 270 tests; eight composition examples and 12 regression runs; 126 payload hashes and 33 snapshots audited; matrix/refinement/accounting/replay checks; archived 0.3.0 reverified and strict mismatch refusal retained |
| VERIFY-005 | Verify physical-cell production, regress four models, preserve 0.4.0 | Done | [Acceptance](reports/MODEL003_ACCEPTANCE.md); 447 tests, 18 pinned reference cases plus replay/branch, four earlier suites, archived 0.4.0 exact replay and strict mismatch refusal |
| VERIFY-006 | Verify physical-pair production, regress five models, preserve 0.5.0 | Done | [Acceptance](reports/MODEL004_ACCEPTANCE.md); 670 tests, 20 pinned cases plus exact replay/branch, all five earlier suites and 40 exactly unchanged trajectories; 62 runs/159 snapshots audited, archived 0.5.0 replay and strict mismatch refusal |
| VERIFY-007 | Verify nominal-pair production, regress six models, preserve 0.6.0 | Done | [Acceptance](reports/MODEL005_ACCEPTANCE.md); 852 tests, 14 frozen cases plus replay/branch, 62 prior trajectories/2663 arrays exactly unchanged; 78 new runs/204 snapshots audited, 159 archived snapshots verified and strict mismatch refusal retained |
| VERIFY-008 | Verify independent worlds and preserve scalar and archived behavior | Done | [Acceptance](reports/CORE004_ACCEPTANCE.md); 896 tests, 10 batch runs/44 worlds, frozen-source and independent branch references, all 78 prior scalar trajectories/3511 arrays unchanged; preserved 0.7.0 replay and 204 old snapshots verified |
| VERIFY-009 | Verify windows, serialized recording, existing scalar/cohort behavior and archived 0.8.0 | Done | [Acceptance](reports/CORE005A_ACCEPTANCE.md); 982 tests, 1777 serialized windows match all baseline state/readout rows, 78 scalar runs/10 batches exact, 434 old snapshots and archived replay pass |
| VERIFY-010 | Verify bounded cohorts, complete round replay and archived 0.9.0 | Done | [Acceptance](reports/CORE005B_ACCEPTANCE.md); 1057 tests, 20 cohort runs/88 worlds/254 serialized windows exact, unchanged scalar/full-batch regressions, 342 archived scalar snapshots/10 wrappers and exact old-source window replay; fixture refusal retained |
| VERIFY-011 | Verify fixed-graph source production and preserve pair/earlier models | Planned | MODEL-006; frozen independent references, graph permutation/reversal/degree and disconnected tests, complete scalar/cohort replay, seven-family regression and preserved 0.10.0 identity |
| ASSAY-001 | Reproduce a bounded positive/negative memory-relay subset | Planned | Bounded nominal production is accepted; pin longer E02/E03 protocols, preparation, full-state boundary operations and independent numerical qualification before a source-assay claim |
| ASSAY-002 | Execute and audit the frozen E02-SW1 switching panel | Planned | NUM-005, MODEL-006 and VERIFY-011; all 14 conditions, full preparation provenance and separate numerical/biological outcomes; not exact historical threshold reproduction |
| PERF-001 | Measure CPU graph and independent-world workloads | Done | [Profile](reports/CORE004_ACCEPTANCE.md#bounded-cpu-profile); 12 separate workers, 1/4/16-world 32-cell chains and nominal pairs, three warm samples, distinct kernel/full-call/output/memory scopes; no universal speedup or GPU claim |
| PERF-002 | Measure window memory scaling and CPU overhead | Done | [Profile](reports/CORE005A_ACCEPTANCE.md#bounded-cpu-profile); 12 workers, full/32/256-step policies, complete-trajectory digests exact; constant fixed-window history buffer, overhead/RSS limits and initial full-trace budget refusal retained |
| PERF-003 | Measure prepared cohort windows against full batches and sequential scalar windows | Done | [Profile](reports/CORE005B_ACCEPTANCE.md#bounded-cpu-profile); 16 sequential workers, 4/16-world graphs/pairs, complete-trajectory digests exact; width-256 cohorts use smaller buffers and finish faster than scalar windows, but not full batches; source RSS does not fall |
| GPU-001 | Qualify one-GPU execution on a representative CPU-validated workload | Planned — future implementation | D045 design only; hardware/precision, scalar/batch correctness, device-resident windows and end-to-end measurements. No GPU setup/run now and no need to wait for full BETSE parity |
| GPU-002 | Qualify multi-GPU independent ensembles and coupled spatial partitions separately | Planned — future implementation | GPU-001 plus partition reference cases; single-owned interface flux, stage-correct halos, global field/constraint solves, all-partition failure and checkpoint checks; fixed-work and fixed-work-per-device scaling |
| GPU-003 | Extend qualified partitions to multiple hosts | Planned — later | GPU-002; compatible collective order, explicit process/device setup, communication and common committed restart; hardware/network/fault-tolerance policy not selected |
| RES-001 | Check continuing exploration for new completed findings | Done | R005 reviews completed H3/H4; R006 rereads completed pilot/memory evidence and native setup for E02-SW1. Source-reported results, not rerun auditors or live H4b findings; hashes and limits recorded |
| SCALE-001 | Implement a validated fine/coarse tissue interface | Deferred | M6; contracts only until a detailed tissue reference exists |
| ORGAN-001 | Select and specify the simplest useful organ preset | Deferred | Before M7; no organ/species selected and no effect on M1a readiness |
| SCALE-002 | Select computational multiscale and large-GPU decomposition | Deferred | D012 and future note recorded; requires representative accuracy, work, memory, and transfer profiles |

Status vocabulary: Planned, Ready, In progress, Blocked, Done, Deferred.
Use Blocked for an active task that cannot proceed, with its exact dependency.
Use Done only when the named deliverable and its appropriate verification exist.

## Dependencies and uncertainties

| Item | Current understanding | Next handling |
| --- | --- | --- |
| First experimental benchmark | BIO-001/002/003 are closed as descriptive; the original prediction is preserved. The supplement review did not resolve statistical uncertainty or recording assumptions. | No active follow-up search or fit; reopen with new evidence or a separately scoped benchmark. A new model informed by C3 needs new evaluation data. This does not block architecture work or confer biological validation. |
| BITSEY reference checkout | Separate clean pinned checkout obtained under Cells' ignored upstream/bitsey; source captures completed. | Keep provenance fixed; no mutation of the ongoing exploration. |
| Source reuse and units | No license file found; regulatory comments and simulator disagree on hour/second labels. | No upstream code vendoring; explicit source-scaled/nominal-time units; resolve before physical or redistributed source claims. |
| Amount versus source coordinates | Passive pair and reaction/transport use fmol, pL, and seconds; EMT uses source-scaled/nominal-time units. | Do not wire these together without a separately validated physical/source mapping and selective coupling contract. |
| Physical-cell numerics | NUM-002 reference and MODEL-003 JAX pass the bounded RK4/5 ms plus cubic panel; no arbitrary-parameter guarantee. | Revalidate new regimes; investigate stiff/multirate methods from measured timescales, not a reused linear bound or GPU alone. |
| Selective physical pair | NUM-003 and MODEL-004 pass all 20 frozen cases at RK4/1 ms with cubic observations; production also checks cubic extrema, full gate/history replay and five-model regressions. | Retain source/physical distinction and bounded numerical scope; new regimes and reductions need independent qualification. |
| Source contact correspondence | SPEC-003, NUM-004 and MODEL-005 qualify the bounded first profile, prepared packets, 14 cases and JAX implementation. Native Euler overshoots phase boundaries; S12 needed further clock refinement. | Keep exact event splitting and source clock distinctions. Longer switching, memory/relay and additional cancer-expression mechanisms remain separate gates. |
| Observation accuracy and preparation | Physical cubic observations and exact replay now pass; a long passive reference retains a nonzero equilibrium residual. | Keep preparation as an explicit protocol with measured criteria; preserve earlier models' linear contracts. |
| BETSE/software references | R009/D045 adds a 17-family v1.5.0 capability inventory to R004; neither is an executed BETSE reference environment. | Follow the staged multispecies/kinetics/graph/field/compartment/mechanics plan; enumerate concrete mechanisms and corresponding cases before parity claims. Keep source, numerical and experimental evidence separate. |
| Source-paper correspondence | The exploration reports unresolved paper-table provenance. | Use explicitly identified source cases; preserve that limitation. |
| Continuing exploration | R005 reviews completed H3/H4 documents, not their raw audits; earlier entries remain dated snapshots. | Preserve full-state, ordinary controls and explicit support/cost distinctions. Check subsequent completed updates when needed; do not infer live status or launch its experiments. |
| GPU target | D045 explicitly targets future parallel GPUs, including coupled-world decomposition, but selects no hardware or speedup. | CPU-first fixtures, then GPU-001/002/003; keep physical fidelity, numerical method and placement separate and measure communication/output as well as arithmetic. |
| Independent-world execution | CORE-004 verifies homogeneous guarded mapping; CORE-005 adds bounded scalar/cohort windows with independent clocks and complete replay. | Vectorized guards and heterogeneous/distributed policies require separate qualification; independent worlds are not interacting organs. |
| Measured CPU costs | PERF-001/002/003 show mixed throughput, bounded history buffers and continued host/checking overhead. Width-256 cohorts beat sequential scalar windows here, but not full batches. | Keep both policies and measure representative regimes; no universal RSS or GPU speedup claim. |
| Wider ideas collection | Targeted strict-eight, ingressing/Ruliad, and AI review completed as R002. | Integrate the accepted implications; leave unreviewed branches deferred. |
| Organ target | User prefers the simplest useful organ, selected through data, with multiple organs possible later. | Choose species/function/scope before M7; start with one cell now. |
| Computational multiscale | Future spatial, temporal, and model-fidelity choices are distinct from device placement. | Retain modular interfaces now; choose reductions and GPU partitioning only from later profiles and validation. |

## Activity log

| Date (UTC) | Entry | Outcome / evidence |
| --- | --- | --- |
| 2026-09-17 | Closed the 79-test live/window preflight and authorized the prepared full same-1 ms campaign. | D126; [launch/closeout](reports/REF005D_LIVE_QUALIFICATION_LAUNCH.md). All 235 sealed preflight payloads and 668 tested inputs authenticate; reuse unchanged code, physics, timesteps and limits. Target 36 native runs plus 24 Cells baselines, 72 window paths and complete recorded restarts. Detached, user-polled; no automatic retry or independent follow-up. |
| 2026-09-17 | Closed offline recording and implemented the same-horizon live/window gate. | D125; [closeout](reports/REF005D_CODEC_CLOSEOUT.md), [handoff](reports/REF005D_LIVE_HANDOFF.md). Independent offline review: 36 rows / 54.7 million exact comparisons / zero failures. Live native smokes exactly preserve both accepted modes; public Cells window/restart smoke passes. Expanded preflight retains 75 passes and a software time-cap failure; 76 final fast checks pass. Prepare one detached 79-test preflight with an explicit 120 s Cells smoke allowance; no production/physics/tolerance change, full matrix, polling or automatic follow-up. |
| 2026-09-07 | Reviewed v2.3 and scoped Levin-derived materials; discussed architecture. | Research check-in R001; source findings distinguished from Cells results. |
| 2026-09-07 | User selected Python/JAX and accepted the overall direction. | D001-D007 recorded. |
| 2026-09-07 | Completed the initial documentation and tracking set. | Seven Markdown documents; local links, formatting, and internal status checked. No code or simulations started. |
| 2026-09-07 | Reviewed strict-eight, ingressing/Ruliad, and AI branches; user accepted design refinements. | R002 and D008-D009; scoped evidence and later corrections retained. |
| 2026-09-07 | User clarified whole-organ and multiple-organ goals, organ definitions as data, and one-cell-first implementation. | D010-D011; multiscale composition and first-build documents completed; roadmap extended through M8. |
| 2026-09-07 | User requested a future note on computational multiscale and large GPUs. | D012; spatial/temporal/fidelity choices, profiling, and decomposition noted; implementation deferred. |
| 2026-09-07 | Verified the expanded documentation and completed DOC-002. | Nine Markdown documents, 54 local link occurrences, formatting, and status checked. No simulator code, installs, scientific runs, or GPU jobs. |
| 2026-09-08 | Built Cells 0.1.0 in an isolated CPU environment. | M1a state/config/model/numerics/observers/CLI/snapshot modules, pinned dependencies, D013. Network permission was resolved before installation. |
| 2026-09-08 | Completed M1a verification and saved examples. | 88 tests passed with warnings as errors; lint/format/pip checks passed; exact unchanged replay and independent rechallenge verified. See acceptance report. |
| 2026-09-08 | User approved the next slice; pinned and inspected BITSEY without changing the exploration. | R003, native E/M helper captures and 36 derivative probes; reuse and time-unit limitations recorded. |
| 2026-09-08 | Implemented and verified Cells 0.2.0 isolated regulation. | D014, 119 passing tests, Radau/BDF comparison, fourth-order refinement, exact 5000-unit replay; [M1b acceptance](reports/M1B_ACCEPTANCE.md). |
| 2026-09-08 | Preserved the verified 0.1.0 source and old runs before package evolution. | Source archive plus strict source/runtime refusal; no implicit checkpoint migration. |
| 2026-09-08 | Implemented and verified Cells 0.3.0 passive contact after the user's next-step approval. | D015; 189 passing tests; five saved pair runs; matrix-reference/refinement, conservation, blocked/release, and exact-replay checks; [M1c-a acceptance](reports/M1C_A_ACCEPTANCE.md). |
| 2026-09-08 | Reverified earlier models and preserved 0.2.0 before package evolution. | Full synthetic/regulatory acceptance reruns under 0.3.0; archived 0.2.0 loads all four old final snapshots with valid payloads; current source refuses implicit migration. M1c-b and profiling remain next. |
| 2026-09-08 | User clarified that source-assay support must grow from Cells' own engineering, without rushing for test parity. | Reviewed existing state/model/coupling/schedule boundaries; D016 and engineering gate recorded. CORE-003 precedes source-selective implementation; 0.3.0 code, tests and artifacts unchanged. |
| 2026-09-08 | Implemented the approved CORE-003 engineering gate as Cells 0.4.0. | D017; reusable local/transport contributions, data-defined fixed graphs, independent contact controls; 270 tests and eight saved examples verified. Three faster test variants required timestep refinement to meet the unchanged accuracy target. |
| 2026-09-08 | Completed all earlier-model regressions and preserved the previous release. | 12 fresh 0.4.0 regression runs pass; 0.3.0 archived before source edits and its five historical pair runs reverified; strict cross-version refusal retained. [Acceptance](reports/CORE003_ACCEPTANCE.md); no GPU or ongoing research-lane jobs. |
| 2026-09-08 | User accepted the BETSE/software recommendations; recorded the review and next physical-cell design. | R004/D018, ARCH-002/SPEC-001; membrane/bath/charge/energy and preparation/fidelity boundaries adopted. Independent calculator passes 74 instantaneous checks; unchanged production suite passes 270 tests in 49.50 s. [Design-check report](reports/BIOELECTRIC_DESIGN_CHECK.md); NUM-002 next. No new production model, dependency, BETSE run, or GPU/research-lane job. |
| 2026-09-08 | Built and qualified the independent bioelectric CPU reference after the user's next-step approval. | D019/NUM-002; 18 short cases plus refinement and slow passive checks; 346 tests in 64.97 s. Linear observation error and two long-reference tolerance refinements retained, with targets unchanged. [Qualification](reports/NUM002_REFERENCE.md); 39 payloads and six archived reference sources verified; production's 22 source hashes unchanged. MODEL-003 ready, no new production/GPU/source-assay run. |
| 2026-09-08 | Implemented and verified the first physical JAX cell after next-step approval. | D020/MODEL-003/VERIFY-005; 447 tests in 125.51 s, 18 frozen-reference cases plus replay/branch, all four earlier suites; 40 manifests, 294 payloads and 87 snapshots audited. [Acceptance](reports/MODEL003_ACCEPTANCE.md); 0.4.0 source archived before edits and old replay verified. No new dependency, GPU or continuing-agent experiment. |
| 2026-09-08 | Completed the approved selective-contact design/source gate and checked completed exploration updates. | D021/SPEC-002/R005; 106 native source-correspondence plus 603 physical instantaneous checks; 483 tests in 114.93 s. [Evidence](reports/SPEC002_DESIGN_CHECK.md); 25 production source hashes unchanged. H3/H4 documents reviewed, not rerun; no coupled source integration, new dependency, GPU or continuing-agent job. NUM-003 next. |
| 2026-09-08 | Built and qualified the approved independent physical-pair reference. | D022/NUM-003; 20 frozen cases, 15 retained timestep trials, RK4/1 ms plus cubic candidate; 542 tests in 125.97 s. [Evidence](reports/NUM003_REFERENCE.md); 271 payload hashes, two eight-entry source capsules and 43812 native accepted states audited. All 25 production source hashes unchanged; no new dependency, production pair, source-assay, GPU or continuing-agent job. MODEL-004 ready. |
| 2026-09-08 | Implemented and verified the approved physical JAX pair. | D023/MODEL-004/VERIFY-006, Cells 0.6.0; 670 tests in 270.23 s, all 20 frozen cases, exact restart and independent future branch, five previous suites and all 40 prior trajectories unchanged. [Acceptance](reports/MODEL004_ACCEPTANCE.md); 62 runs, 504 payload hashes, 159 snapshots and 41-file implementation capsule verified. 0.5.0 preserved before edits with exact archived replay. No new dependency, source-assay claim, GPU or continuing-agent job. |
| 2026-09-08 | Completed the approved source-compatible complete-model design and frozen reference inputs. | D024/SPEC-003; 3192 instantaneous checks, 14 cases/17 native settings, prepared full E/M packets reused with exact source clocks, 735 tests. [Evidence](reports/SPEC003_DESIGN_CHECK.md); 28 production hashes unchanged. No source integration, version/dependency change, GPU or continuing-agent job. NUM-004 ready. |
| 2026-09-08 | Completed independent source-compatible coupled qualification. | D025/NUM-004; all 14 cases at RK4/0.01 nominal units and its half, 44 native paths/460227 accepted steps, explicit raw-cache and realized-clock audits. Original S12 timing failure and six 60-second timeouts retained; two event refinements pass unchanged targets. 783 tests; production's 28 hashes unchanged. [Evidence](reports/NUM004_REFERENCE.md); MODEL-005 ready. |
| 2026-09-08 | Implemented the approved nominal source-compatible JAX pair. | D026/MODEL-005/VERIFY-007, Cells 0.7.0; 852 tests in 300.08 s, all 14 frozen cases, exact full-state replay and independent branch; all 62 prior trajectories/2663 arrays unchanged. [Acceptance](reports/MODEL005_ACCEPTANCE.md); 78 runs, 642 payload hashes, 204 snapshots and 46-source capsule checked. Archived 0.6.0 replay/159 snapshots pass. First archive audit's out-of-scope development-snapshot failure retained; accepted scope corrected without relaxing identity. No new dependency, native/research-lane run or GPU job. CORE-004 and CPU profiling next. |
| 2026-09-08 | Implemented independent-world execution and measured bounded CPU workloads. | D027/CORE-004/VERIFY-008/PERF-001, Cells 0.8.0; 896 tests in 388.65 s, 10 batch runs/44 worlds, all 14 frozen source cases and independent branches pass. All 78 prior scalar trajectories/3511 arrays unchanged; 0.7.0 archived before edits with exact replay/204 old snapshots verified. Twelve separate CPU profile workers show mixed performance, not universal speedup. [Acceptance](reports/CORE004_ACCEPTANCE.md); no new dependency, native/research-lane or GPU job. CORE-005 memory/recording contract next. |
| 2026-09-08 | Implemented bounded single-world windows and selectable incremental recording. | D028/CORE-005a/VERIFY-009/PERF-002, Cells 0.9.0; 982 tests in 446.58 s, 78 scalar runs and 10 batches unchanged, all 1777 saved windows exact. Archived 0.8.0 replay and 434 old snapshots pass. Twelve CPU workers quantify smaller buffers with more overhead; initial 64 MiB full-trace profile refusal retained before a common 128 MiB comparison. [Acceptance](reports/CORE005A_ACCEPTANCE.md); no equation, dependency, native/research-lane or GPU change. Windowed cohorts next. |
| 2026-09-08 | Implemented bounded independent-clock cohorts and prepared execution reuse. | D029/CORE-005b/VERIFY-010/PERF-003, Cells 0.10.0; 1057 tests in 548.34 s, unchanged 78 scalar trajectories/10 batches, 20 cohort original/restart runs and 254 per-world windows exact. Archived 0.9.0's 342 scalar snapshots/10 cohort wrappers and old-source window replay pass. Acceptance-fixture event-cursor refusal retained, corrected without production changes. Sixteen isolated CPU workers show smaller history buffers and gains over scalar windows, not full batches or universal RSS gains. [Acceptance](reports/CORE005B_ACCEPTANCE.md); selected longer E02 protocol gate next. |
| 2026-09-08 | Froze the first longer switching protocol after reviewing completed source evidence and native setup. | D030/SPEC-004/R006; E02-SW1 needs a three-cell star, fresh 500-unit preparation and 14 controlled 1000-unit conditions. [Design evidence](reports/SPEC004_PROTOCOL_CHECK.md), 29 new tests and 1086 total pass in 569.54 s; nine payload hashes, 39 unchanged production sources, eight native sources and four reviewed documents verified. Cells remains 0.10.0; no prepared packets, graph implementation or long assay result. NUM-005 next. |
| 2026-09-08 | Implemented and checked the independent fixed-graph source reference. | D031/NUM-005a; 45 native derivative inputs, 17 pair reductions, 18,499 arithmetic/structural checks, 118 new tests and 1204 total pass in 560.96 s. [Evidence](reports/NUM005A_REFERENCE.md); 17 artifact hashes, 18-file acceptance capsule and retained 11-file failed-adapter archive checked. Correction changes one collector index only; inputs, equations and tolerances unchanged. All 39 production sources and nine SPEC-004 payloads unchanged. NUM-005b preparation next; no long trajectory or production graph claim. |
| 2026-09-08 | Qualified fresh isolated E/M preparation with bounded independent integration. | D032/NUM-005b; six exact 500-unit trajectories, 32,372 accepted steps and 65,740 comparison times pass. Full prepared packets are hash-pinned; separate audit checks 421 payloads, 20 source-capsule files and unchanged 39 production sources. All 1243 tests pass in 568.21 s, including 39 new tests. [Evidence](reports/NUM005B_PREPARATION.md); sampled regulatory phenotype is stable but ions still drift. NUM-005c ready; no connected run, RK4 selection, production/GPU/fluid change or continuing-agent experiment. |
| 2026-09-08 | Built the bounded long-reference layer and completed a capped E02 session. | D033/NUM-005c1; 24 exact 1000-unit trajectories and eight reference trios pass, with 516,406 comparison times. The one-hour cap retains one partial attempt and 17 unstarted attempts; six conditions remain. Independent audit checks 3218 payloads, 25 archived sources and all complete curves/readouts. [Evidence](reports/NUM005C1_LONG_REFERENCE.md); all 1287 tests pass in 580.39 s, including 44 new tests. Production remains 0.10.0; no RK4 selection or automatic continuation. |
| 2026-09-09 | Added the registered continuation and stopped at a genuine reference disagreement. | D034/NUM-005c1; nine new complete paths, two newly qualified conditions (ten total), reverse miRNA-only fails at 0.2263 versus 0.1; three controls unstarted. All nine paths pass independent domain/accounting audit; retained samples reproduce the discrepancy. [Evidence](reports/NUM005C1_CONTINUATION.md); 1314 tests pass in 571.90 s, including 27 new checks. Prior evidence and production unchanged; no automatic retry, tolerance relaxation or RK4 selection. |
| 2026-09-09 | Completed the approved single tenfold-tighter BDF diagnostic. | D035/A1; 17,704 accepted steps, 103,243 four-input comparison times, required score 0.00533 versus 0.1. Original BDF disagreement remains visible. Independent dense/grid/state/score audit and all 1337 tests pass in 584.77 s, including 23 new checks. [Evidence](reports/NUM005C1_A1_BDF_REFINEMENT.md); original count stays ten, production unchanged, no control continuation or RK4 selection. |
| 2026-09-09 | Adopted A2 accuracy policy and completed the long-reference panel. | D036/A2; ten original cases plus the explicitly adopted miRNA-only reference and three new controls: all 14 comparisons/observers pass. Nine new paths, 188,834 comparison times, 4028 observer times, 1087.264-second session and 715,966,189 aggregate bytes. Independent audit and all 1362 tests pass in 596.75 s, including 25 new checks. [Evidence](reports/NUM005C1_A2_REFERENCE_PANEL.md); original failure, prior sources and production preserved. Bounded candidate engineering/preflight next, no long RK4 study launched. |
| 2026-09-09 | Implemented and profiled bounded checked RK4 on short fixtures. | D037/NUM-005c2a; twelve profiles, 6144 accepted steps, 26,864 comparison samples and exact window/restart evidence. Independent audit checks 1313 payloads/48 sources; all 1415 tests pass in 612.40 s, including 53 new checks. [Evidence](reports/NUM005C2A_CANDIDATE_ENGINEERING.md); prior sources and production unchanged. Width-256 planning estimates of 12.70 hours/11.47 GB do not establish a long-study resource fit; optimize diagnostics and specify compact audited evidence next. No long candidate study or timestep selection. |
| 2026-09-09 | Implemented cached observation-axis readouts and profiled both policies with full evidence. | D038/NUM-005c2b; twelve matched short profiles and expanded audit pass: exact integration/sample evidence and bitwise scalar readouts. Checked time totals 38.72 s scalar versus 21.06 s batched. All 1540 tests pass in 619.79 s, including 125 new checks; all 335 targeted tests pass. [Evidence](reports/NUM005C2B_DIAGNOSTIC_OPTIMIZATION.md); 803,085,279 aggregate bytes, all prior sources and production unchanged. Compact-evidence proposal is unimplemented; lossless reconstruction/auditing is the recommended next slice, not long candidate selection. |
| 2026-09-09 | Implemented lossless full/basis recording with explicit committed restart and independent reconstruction auditing. | D039/NUM-005c2c; twelve short profiles and 266-payload/62-source audit pass with exact D038 evidence and scalar readouts. Trajectory payloads shrink 57.8%, total profile evidence 16.7%; checked/audited runtime is essentially unchanged. All 1707 tests pass in 640.43 s, including 167 new checks; all 384 targeted tests pass. [Evidence](reports/NUM005C2C_LOSSLESS_EVIDENCE.md); 821,019,434 aggregate bytes, prior sources and production unchanged. Reference-backed comparison records are the next proposed prototype; long-study resource fit remains unestablished. |
| 2026-09-09 | Implemented lossless reference-backed comparison records with explicit dependency-aware reading/restart. | D040/NUM-005c2d; twelve short profiles and 290-payload/68-source audit pass with exact D039 logical arrays and scalar readouts. Comparison payloads shrink 98.5%, total profile evidence 80.6%, with 4.2% more checked time in matched short observations. All 1903 tests pass in 686.87 s, including 196 new checks; all 541 targeted tests pass. [Evidence](reports/NUM005C2D_COMPARISON_RECORDING.md); 831,126,114 aggregate bytes, prior sources and production unchanged. Integration-side evaluation profiling/caching is proposed next; trajectory storage and long-study fit remain separate gates. |
| 2026-09-09 | Implemented immutable scalar reference evaluation with explicit restart identity and independent complete-stage checks. | D041/NUM-005c2e; twelve short profiles, 1440 complete-RHS probes, 720 decomposed evaluations and all 30720 stored stage derivatives are exact against frozen equations. The 304-payload/74-source audit, all 2178 regression tests (749.16 s) and 816 targeted tests pass, including 275 new checks. RHS time falls 13.9%, checked time 2.9%, checked-plus-audited time 0.9% in matched short observations. [Evidence](reports/NUM005C2E_INTEGRATION_EVALUATION.md); 834,874,394 aggregate bytes, prior sources and production unchanged. Next profile unchanged validation/audit costs; trajectory storage and long-study fit remain separate gates. |
| 2026-09-09 | Began a first experimental benchmark and paused optimization/GPU work. | D042/R007/BIO-001; [specification](docs/BIOLOGICAL_BENCHMARK_001.md), provisional RPTEC dataset and [curation report](reports/BIO001_DATASET_REVIEW.md). Three approximate endpoints, two quarantined input conflicts, original licensed source figures and a retrospective split; all 15 targeted integrity tests pass. All 39 production sources unchanged. No fit, trajectory or biological acceptance; BIO-002 measurement-boundary/comparator work next, long E02 qualification deferred without weakened gates. |
| 2026-09-09 | Completed the first conditioned electrical endpoint prediction. | D043/BIO-002; [result](reports/BIO002_CONDITIONED_VOLTAGE.md), fixed protocol, reusable pure algebra, CSV/JSON and SVG. C1/C2-only fit predicts C3 at -14.59 mV versus approximately -18 mV; 3.41 mV absolute discrepancy versus 21 mV for no response. Reading-bound prediction range [-18.32, -11.20] mV is not a confidence interval. All 63 targeted tests and 12 Decimal arithmetic checks pass; 39 production sources and six dataset files unchanged. Biological acceptance not assessable; BIO-003 uncertainty/boundary review next, optimization/GPU paused and long E02 gates intact. |
| 2026-09-09 | Closed the endpoint pilot after bounded supplementary and methods review. | D044/R008/BIO-003; [closeout](reports/BIO003_PILOT_CLOSEOUT.md), machine-readable status and original licensed XML/PDF attachment. No C1-C3 numeric summaries or experiment grouping recovered; recording assumptions remain unqualified. Pilot closed as descriptive, not biological validation; 63 targeted tests pass again, old pilot and production preserved, no refit or automatic continuation. |
| 2026-09-09 | Returned to architecture with BETSE-level scientific coverage and future parallel GPUs as explicit targets. | D045/R009/ARCH-003; [17-family roadmap](docs/BETSE_CAPABILITY_ROADMAP.md), [multiscale execution architecture](docs/MULTISCALE_EXECUTION_ARCHITECTURE.md) and [next-build brief](docs/MULTISPECIES_MEMBRANE_NEXT.md). Independent ensembles, coupled spatial partitions and later multi-host operation have distinct contracts. SPEC-005 is next on CPU; no parity claim, production change, GPU installation/run, optimization or long E02 campaign. |
| 2026-09-09 | Completed the first explicit multispecies membrane contract and independent scalar reference. | D046/SPEC-005; [frozen specification](docs/MULTISPECIES_MEMBRANE_SPEC.md), two synthetic cases and [1546-check receipt/result](reports/SPEC005_DESIGN_CHECK.md). All 352 targeted tests pass in 54.89 s, including 113 new; 219 pre-existing file hashes, including 39 production sources, are unchanged. A receipt source-path bug was corrected without changing physics/inputs/tolerances. NUM-006 trajectory qualification is next; no biological acceptance, new production model or GPU run. |
| 2026-09-09 | Qualified short multispecies trajectories and a production-method candidate. | D047/NUM-006; [result](reports/NUM006_REFERENCE.md), 14 cases/84 attempts in 69.882 s, 38264835 bytes, three passing implicit settings and three passing RK4 steps; selected 0.01 s with interval-held cubic observations. The strengthened read-only audit replays 547572 sampled rows and binds settings/tolerances to frozen sources without rerunning trajectories. All 446 targeted tests pass in 56.67 s, including 94 new; 284 old file hashes and 39 production sources unchanged. CORE-006 is next; no pilot, old timestep, GPU or E02 promotion. |
| 2026-09-09 | Implemented and accepted the data-defined multispecies CPU/JAX membrane. | D048/CORE-006, Cells 0.11.0; [acceptance](reports/CORE006_ACCEPTANCE.md), 14 cases in eager/JIT, 43 scalar outputs/four cohort outputs, 773 authenticated payloads, 60-file source capsule and 226 scalar/22 cohort snapshots. Full reference/readout/restart/branch/cohort checks pass in a 993.226 s bounded session; all 2565 tests pass (1594 current, 971 preserved-reference), including 117 new. Old 78 scalar trajectories/1777 windows/44 batched worlds remain exact; all 948 scalar/99 cohort old snapshots load under archived 0.10.0 and replay is exact. Retained test-context failures and interrupted first acceptance are documented, not erased. SPEC-006 is proposed next; no biological, organ, GPU or deferred E02 promotion. |
| 2026-09-09 | Specified and independently checked the first state-bearing physical membrane channel. | D049/R010/SPEC-006; [contract](docs/VOLTAGE_GATED_CHANNEL_SPEC.md), frozen two-assembly/seven-protocol panel and [7528-check result](reports/SPEC006_DESIGN_CHECK.md). All 2670 regression tests pass in 710.846 s of summed test-context time (1699 current, 971 preserved-reference), including 105 new; no failures or skips. Two explicit gate states, separate ionic transfer history and independent availability/abundance are retained. All 41 production modules, old reference code and pilot data remain unchanged; the 773-payload CORE-006 audit passes again. The old 10 ms step fails a held-gate stability diagnostic, so NUM-007 coupled qualification precedes CORE-007. No new production model, timestep selection, biological validation, GPU or E02 promotion. |
| 2026-09-09 | Qualified coupled cell/channel dynamics with complete hidden state and independent saved-evidence replay. | D050/NUM-007; [protocol](docs/VOLTAGE_GATED_NUMERICS.md), [result](reports/NUM007_REFERENCE.md); 14 cases/98 attempts in 196.401 s, 80191978 bytes, selected 0.5 ms RK4/cubic with passing 0.25 ms refinement. Six completed coarse accuracy failures and one rejected m=1.19438 stage are retained. The 214-payload/19-source audit reproduces 947939 sampled rows without rerunning an ODE solver. All 2770 regression tests pass (1799 current, 971 preserved-reference; 722.179 s summed test-context time), plus 205 targeted tests, including 100 new. Of 382 pre-existing files, 372 remain byte-identical and ten have documentation-only updates; all 41 production modules and old pilot/reference evidence are unchanged. CORE-007 production/replay/cohort acceptance is next; no biological, GPU or E02 promotion. |
| 2026-09-10 | Implemented and accepted the first state-bearing membrane channel through the shared CPU/JAX engine. | D051/CORE-007, Cells 0.12.0; [guide](docs/VOLTAGE_GATED_MEMBRANE.md), [acceptance](reports/CORE007_ACCEPTANCE.md). All 14 frozen cases pass in eager/JIT, with 43 scalar outputs, exact fresh-process restarts, two window runs and four original/resumed cohorts. Read-only audit checks 1580 payloads/204 captured files; all 488 scalar/54 cohort checkpoints load. All 2883 regression tests and 113 targeted tests pass. Two interrupted resource-planning attempts are retained; accepted verification is 1436.144 s and 546355382 bytes under revised prospective limits. Prior sources/checkpoints and scientific/pilot evidence are preserved. Physical ionic graph specification is next; no biological, GPU, organ or E02 promotion. |
| 2026-09-10 | Specified and independently checked physical ionic graph composition without changing production. | D052/SPEC-007; [contract](docs/PHYSICAL_IONIC_GRAPH_SPEC.md), [result](reports/SPEC007_DESIGN_CHECK.md). All 14116 checks/eight synthetic definitions and all 2997 regression tests pass, including 114 new; no failures or skips. Single/disconnected reductions, heterogeneous mono/divalent pairs and shared-recipient stars check one-owned edge transfer, weighted charge and separate power/history. Of 428 pre-existing files, 417 are unchanged and eleven have documentation-only updates; all 44 production modules, packaging and prior scientific/pilot evidence remain unchanged. The 1580-payload production audit passes again. NUM-008 short graph trajectories precede CORE-008; no graph timestep, GPU, organ, biological or E02 promotion. |
| 2026-09-10 | Qualified short coupled physical ionic graphs and retained complete numerical evidence. | D053/NUM-008; [protocol](docs/PHYSICAL_IONIC_GRAPH_NUMERICS.md), [result](reports/NUM008_REFERENCE.md), [closeout](reports/num-008-closeout.json). All twelve cases/84 graph attempts plus five independent component solves pass. Select 2 ms RK4/cubic with passing 1 ms refinement only for this short panel. The 194-payload/26-source audit exactly replays 256283 sampled rows; all 99 new and 3096 regression tests pass with no failures or skips. An initial preflight receipt-format failure was fixed before scientific execution and retained. Of 444 pre-existing files, 433 are unchanged and eleven have documentation-only updates; no production, packaging, prior reference or pilot evidence changed. The 1580-payload production audit passes again. CORE-008 CPU/JAX graph assembly is next; no old timestep, arbitrary-graph, GPU, organ, biological or E02 promotion. |
| 2026-09-10 | Implemented and accepted physical ionic graphs through the shared CPU/JAX engine. | D054/CORE-008, Cells 0.13.0; [guide](docs/PHYSICAL_IONIC_GRAPH.md), [acceptance](reports/CORE008_ACCEPTANCE.md), [closeout](reports/core-008-closeout.json). All twelve frozen cases in eager/JIT, 37 scalar outputs, two window runs, four original/resumed cohorts and earlier-model exact replay pass. The first formal session takes 453.536 s and 462687262 bytes; 600 payloads/223 captured files and all 162 scalar/16 cohort checkpoints authenticate. All 114 new targeted and 3210 regression tests pass across four source contexts, with no failures, errors or skips. Of 466 pre-existing files, 448 are unchanged and eighteen have expected documentation/dispatch/version/test-driver changes; earlier physics, shared engine and scientific/pilot evidence remain unchanged. Finite extracellular-compartment design is proposed next; no biological, GPU, organ, arbitrary-graph or E02 promotion. |
| 2026-09-10 | Specified and independently checked one finite shared extracellular compartment. | D055/SPEC-008; [contract](docs/FINITE_EXTRACELLULAR_SPEC.md), [result](reports/SPEC008_DESIGN_CHECK.md), [closeout](reports/spec-008-closeout.json). All 10671 instantaneous checks/nine cases and 3298 regression tests pass, including 88 new. Outside inventory, countercharge, full ionic energy and shared feedback are explicit. Checker correction and nonfinal attempts are retained. Production 0.13.0 and earlier evidence are unchanged; 484 of 493 old files are byte-identical, nine have documentation-only updates. NUM-009 short trajectories/depletion is next, before CORE-009; no production, timestep, biological, GPU, organ or E02 claim. |
| 2026-09-10 | Ran and audited the first frozen finite-outside qualification attempt; retained its stopping failure. | D056/NUM-009; [protocol](docs/FINITE_EXTRACELLULAR_NUMERICS.md), [result](reports/NUM009_REFERENCE.md), [attempt closeout](reports/num-009-attempt-closeout.json). 80 attempts/ten case ladders in 227.342 s and 77109196 bytes: nine reference passes, then an exact outside-increment invariant failure in the junction-only reference. Four 4 ms accuracy failures are retained; four cases remain unrun and no timestep is selected. Read-only audit authenticates 174 payloads/31 sources and replays 184240 rows. All 109 targeted tests pass; no full-matrix or biological acceptance. Production/evidence unchanged; a general reference-coordinate correction must precede a new frozen run. |
| 2026-09-10 | Qualified the amended finite-outside reference with explicit inventories and general conservation-tangent linearization. | D057/NUM-009 v2; [amendment](docs/FINITE_EXTRACELLULAR_NUMERICS_V2.md), [result](reports/NUM009_REFERENCE_V2.md), [closeout](reports/num-009-v2-closeout.json). Fourteen cases / 112 attempts in 297.692 s and 103601932 bytes; select 1 ms RK4/cubic with passing 0.5 ms refinement. Exact blocking and 80.8057% synthetic outside-K depletion pass; nine coarse accuracy failures retained. The 242-payload/43-source audit replays 251400 rows; all 168 targeted and 3466 maintained/historical regression tests pass. V1 sources/failure/evidence remain unchanged; its 13 prospective complete-session tests are explicitly unexecuted, with maintained v2 replacement coverage. Of 529 old files, 520 remain byte-identical and nine have documentation-only updates. Production stays 0.13.0; CORE-009 CPU/JAX assembly is next, not biological, GPU or organ promotion. |
| 2026-09-10 | Implemented and accepted finite extracellular inventories through the shared CPU/JAX engine. | D058/CORE-009, Cells 0.14.0; [guide](docs/FINITE_EXTRACELLULAR.md), [acceptance](reports/CORE009_ACCEPTANCE.md), [closeout](reports/core-009-closeout.json). Fourteen cases, 43 scalar outputs, two windows, four original/resumed cohorts and exact earlier-model replay pass. Final acceptance takes 631.734 s and 446951333 bytes; 830 payloads/256 captured files and all 235 scalar/21 cohort checkpoints authenticate. All 150 new targeted and 3616 final regression tests pass across five source contexts. The first matrix's two missing-interpreter failures are retained; a launcher-only correction leaves physics/original tests unchanged, and all 25,654 numerical arrays repeat exactly. Of 559 pre-existing files, 545 remain byte-identical and fourteen have expected documentation/API/version edits; none missing. Spatial extracellular transport/electrical-closure design is proposed next, without biological, GPU, organ, BETSE-parity or E02 promotion. |
| 2026-09-11 | Specified spatial outside transport and a coupled electrical closure without adding production physics. | D059/R011/SPEC-009; [contract](docs/SPATIAL_EXTRACELLULAR_SPEC.md), [result](reports/SPEC009_DESIGN_CHECK.md), [closeout](reports/spec-009-closeout.json). Eight synthetic definitions / 44 instantaneous evaluations pass 1016 independent 70-digit comparisons; all 85 new unit and 229 targeted tests pass. Arithmetic replay is exact; old production's 830-payload/256-file audit passes. All 48 production modules and old evidence remain unchanged at 0.14.0; ten documentation-only updates. No full-matrix rerun, spatial trajectory/timestep, GPU, organ, BETSE or biological promotion. NUM-010 reference qualification is next. |
| 2026-09-11 | Qualified short spatial trajectories, resolution and full-state reference restart without production changes. | D060/NUM-010; [result](reports/NUM010_REFERENCE.md), [audit](reports/num-010-artifact-audit.json), [closeout](reports/num-010-closeout.json). Fourteen cases / 140 attempts select 0.125 ms RK4/cubic with passing 0.0625 ms refinement; seven rejected coarse trials and two completed accuracy failures retained. All 14 bitwise restarts, analytic/spatial gates, 190 preflight and 3806 five-context regression tests pass. Audit verifies 339 payloads / 21 sources; 628 of 638 old files and all 48 production modules unchanged, ten documentation-only updates. CORE-010 is next; no GPU or biology promotion. |
| 2026-09-11 | Integrated the passive spatial CPU/JAX family, preserving the separate release gate. | D061/CORE-010 development; [report](reports/CORE010_IMPLEMENTATION.md), [closeout](reports/core-010-implementation-closeout.json). Version 0.15.0.dev0, separate cell/outside/membrane/face axes, same-stage bounded field block and unchanged shared engine. All 156 preflight and 3962 six-context regression tests pass; full CLI restart/window array replay and old evidence preservation pass. Formal captured production/audit acceptance remains open; no GPU, organ, BETSE or biological promotion. |
| 2026-09-11 | Added independent saved-production audits and preserved a bounded runtime stop. | D062; [report](reports/CORE010_ACCEPTANCE.md), [tooling closeout](reports/core-010-audit-tooling-closeout.json). All 122 new preflight and 4084 six-context regression tests pass; 53 completed scalar and 12 stream runs independently audit, with 1022 exact restart arrays, a 73-array exact future branch and 166 scalar/24 cohort checkpoints. Ten eager cases completed, three were interrupted and one unstarted at the one-hour limit. All 51 production modules and 703 of 707 existing files unchanged; four intended status-document updates. Full acceptance remains open; no automatic retry or stable promotion. |
| 2026-09-11 | Registered the v2 resource amendment and started a fresh full acceptance capture. | D063; [protocol](docs/SPATIAL_EXTRACELLULAR_ACCEPTANCE_V2.md), [report](reports/CORE010_ACCEPTANCE_V2.md), [prelaunch](reports/core-010-v2-prelaunch.json). All 106 new and 228 combined preflight tests pass. Two-hour cap, same CPU lanes/science/artifact limit; 352 captured files. The baseline authenticates 733 of 740 existing files unchanged and seven planned script/status edits. Prior stopped evidence and all 51 production modules unchanged; no full verdict yet. |
| 2026-09-12 | Executed native BETSE preparation and retained a model-geometry mismatch. | D066/REF-003b1; [result](reports/REF003B1_PREPARATION.md), [diagnostic](reports/ref-003b1-preparation-audit.json), [handoff](reports/ref-003b1-closeout.json). Requested one cell, obtained seven compartments / 30 faces. Guard stops before numerical alignment; all five short attempts retained, revision 2 explicitly disables the default network, no loosened numerical/cell-count gate. 103 short adapter tests pass. Existing 51 production modules, 352 accepted implementation files and REF-003a evidence unchanged; no trajectory, full matrix, GPU or biological claim. |
| 2026-09-12 | Tested native one-centre geometry, then registered and executed an explicit seven-cell comparison. | D067/REF-003c; [result](reports/REF003C_CLUSTER_ALIGNMENT.md). SVG loading succeeds but native triangulation fails; original one-cell guard stays rejected. Seven-cell initialization/charge/RHS/prescribed-update capture passes 19,691 comparisons in 18.666 s with no worker warnings; 25 new preflight tests pass. Availability-contract fixture error retained and fixed in the adapter, not production. Separate actual-packet audit/regression/closeout waits for user instruction; no full trajectory, stable, GPU or biological promotion. |
| 2026-09-12 | Completed the authorized seven-cell saved-data audit and short adapter closeout. | D068; [report](reports/REF003C_CLOSEOUT.md), [receipt](reports/ref-003c-closeout.json). All 171 tests pass in 20.98 s, including 43 actual-packet checks and model-import isolation. Three joint metadata gaps closed in a new evidence layer; frozen numerical capture/checker unchanged. 807/815 closeout-baseline files unchanged, eight intended document edits; all 352 accepted files / 51 production modules preserved. REF-003d observer/trajectory design recorded, not numerically registered or launched. |
| 2026-09-12 | Implemented the native FULL-loop observer, checked-RK4 adapter and prospective short-trajectory panel. | D069; [engineering/launch report](reports/REF003D_TRAJECTORY_LAUNCH.md). All 228 adapter tests pass in 24.234 s, including 57 new preflights. Explicit elapsed/native clocks, complete declared field sets, non-interference partners, independent accounting/refinement and 180 s / 64 MiB limits. Two actual JAX full-run backends, not an invented NumPy solver. No production changes; result review and separate saved-packet audit wait for user instruction. |

| 2026-09-12 | Implemented a separate SIM/event adapter and retained a failed native preparation preflight. | D073/REF-003e0; [report](reports/REF003E0_PHASE_PREFLIGHT.md), [next version](docs/BETSE_SIM_PHASE_BRIDGE.md). 73 focused software/negative-evidence tests pass. First native attempt fails at missing default-tissue metadata in 9.491 s; profiles-off baseline also lacks the target map for scheduled events. Zero-amplitude runtime not reached, no completed preparation or trajectory. Failure/capsule preserved; early guard blocks unchanged retry. All accepted sources and prior evidence unchanged; version the profile bridge before another native attempt. |

| 2026-09-12 | Passed the explicit profile/no-op preparation bridge with durable partial evidence. | D074/REF-003e0 v2; [result](reports/REF003E0_PROFILE_BRIDGE.md), [scope](docs/BETSE_PROFILE_BRIDGE_PREFLIGHT.md). Six native preparations / 30 direct dispatches pass in 17.360 s; four between-configuration checks preserve setup and dispatch bytes exactly. 87 focused tests pass in 2.10 s. 59 retained files, 51 captured sources, all 332 installed native Python files pinned; accepted 352 files / 51 production modules and first failure unchanged. No integration or trajectory launch; full-loop bridge protocol next. |

| 2026-09-15 | Closed initial-history preparation and implemented the requested reference-to-capture workflow. | D098–D099; [review closeout](reports/REF004C_HISTORY_PREPARATION_CLOSEOUT.md), [paired handoff](reports/REF004C_PAIRED_HISTORY_HANDOFF.md). Exact replay of 2,442 checks, 1,404 alternate rate checks and 528 authenticated layouts; 12 review / 56 paired tests pass. Prospective 2 ms reference signal gate precedes native/Cells capture, refinement and full-state restart. Production and previous evidence unchanged; detached, no polling or automatic post-capture audit. |

| 2026-09-15 | Implemented the independently checked paired-history closeout tooling. | D100; [capture result](reports/REF004C_PAIRED_HISTORY_CAPTURE.md), [audit handoff](reports/REF004C_PAIRED_HISTORY_AUDIT_HANDOFF.md). 137 audit-only tests pass in 16.56 s; canonical-definition checksum setup error and 55 s software timeout retained. Full native/reference reconstruction remains in the detached audit, with 21 coarse misses preserved, complete raw checkpoint bytes and six signed contrasts. Production and old evidence unchanged; no polling or automatic follow-up. |

| 2026-09-15 | Recorded the actual paired-history closeout and completed release-input design checks. | D100–D101; [paired closeout](reports/REF004C_PAIRED_HISTORY_CLOSEOUT.md), [release design result](reports/REF004D_RELEASE_DESIGN_CHECK.md). 8,036,300 independent comparisons pass with 21 coarse misses retained. All 107 new software tests pass, including 54 actual instantaneous CPU/JAX probes and 24 grids. Production and old evidence unchanged; no new trajectory, native dispatch, reference solve, detached job or automatic follow-up. |

| 2026-09-15 | Implemented actual native input application and separately checked single updates. | D102; [handoff](reports/REF004D_RELEASE_PREFLIGHT_HANDOFF.md). All 71 software tests pass in 14.01 s with real native smoke cases, observer pairs, independent equations, corruption and partial-failure checks. Earlier adapter/checker attempts retained; 165-input capsule for one detached 144-phase preflight. Production and old evidence unchanged; no polling or automatic response/audit expansion. |

| 2026-09-15 | Traced the retained native preflight rejection to zero-flux bath averaging and implemented a saved-data review. | D103; [failure report](reports/REF004D_RELEASE_PREFLIGHT_FAILURE.md), [review handoff](reports/REF004D_RELEASE_REVIEW_HANDOFF.md). 66 software tests pass, including 198 exact NumPy reduction probes and eight saved rows. All 605 capture files / 165 inputs preserved; 175-input capsule for detached full review. No data normalization, wider physical budgets, simulator rerun or automatic follow-up. |

## Updating progress

At the end of a meaningful work session, update the current position, affected
task rows, and milestone evidence. Add one concise activity entry with links to
the actual artifacts and verification. Record failed scientific hypotheses as
outcomes rather than leaving completed runs permanently in progress.

When implementation or experiments begin, record exact commands, environment,
resource limits, and result paths in the relevant artifact. Keep extensive
trajectories and logs outside this file; link to their manifests and reports.

## Run register

The first three entries are deterministic engineering fixtures using source_decay@1;
the M1b entries are isolated source-backed regulatory comparisons using emt_mirna@1.
M1c-a adds passive_pair@1 engineering transport and earlier-model regression runs.
CORE-003 adds reaction_transport@1 composition and fresh regressions of all three
previous models. MODEL-003 adds bioelectric_cell@1 and four-model regressions;
MODEL-004 adds bioelectric_pair@1 and five-model regressions; MODEL-005 adds the
distinct nominal bitsey_emt_pair@1 and six-model regressions.
These are engineering evidence, not new Levin-assay results.
These Cells runs use CPU float64, RK4, and no RNG. NUM-002 is instead a separate
NumPy/SciPy reference/method qualification using Radau, BDF, and an independent
RK4 probe, not a fifth production model or a Cells checkpoint run.
Existing exploration runs remain separate
source evidence; the source capture below is a native BITSEY comparison, not Cells.

| Run ID | Assay / operation | Status | Manifest / evidence |
| --- | --- | --- | --- |
| m1a-2026-09-08/pulse | E00, fresh 0-12 s pulse | Complete | [Manifest](runs/m1a-2026-09-08/pulse/manifest.json); saved 6 s checkpoint |
| m1a-2026-09-08/resumed | E00, unchanged continuation from 6 s | Complete | [Manifest](runs/m1a-2026-09-08/resumed/manifest.json); suffix exactly equals pulse |
| m1a-2026-09-08/rechallenged | E00, altered future source from 6 s | Complete | [Manifest](runs/m1a-2026-09-08/rechallenged/manifest.json); same initial state, different future |
| m1b-2026-09-08/source-reference | Native isolated helpers and derivative panel | Complete | [Capture](runs/m1b-2026-09-08/source-reference/reference.json); pinned source, separate environment, unchanged settings |
| m1b-2026-09-08/acceptance-final | E01, E/M regulation plus both unchanged restarts | Complete | [Verification](runs/m1b-2026-09-08/acceptance-final/verification.json); four run manifests and complete hashes |
| m1c-a-2026-09-08 | E02 passive prerequisite: active, blocked, resumed, released, pulse | Complete | [Verification](runs/m1c-a-2026-09-08/verification.json); five runs, conserved amount, exact replay, retained blocked topology |
| m1c-a-2026-09-08/synthetic-regression | E00 under 0.3.0 | Complete | [Verification](runs/m1c-a-2026-09-08/synthetic-regression/verification.json); pulse, resume, rechallenge and all hashes |
| m1c-a-2026-09-08/regulatory-regression | E01 under 0.3.0 | Complete | [Verification](runs/m1c-a-2026-09-08/regulatory-regression/verification.json); full source/solver/refinement/replay checks |
| core-003-2026-09-08/acceptance | Local reaction/graph transport: eight examples | Complete | [Verification](runs/core-003-2026-09-08/acceptance/verification.json); independent matrix, accounting, controls, release and exact replay |
| core-003-2026-09-08/synthetic-regression | E00 under 0.4.0 | Complete | [Verification](runs/core-003-2026-09-08/synthetic-regression/verification.json); pulse, resume, rechallenge and all hashes |
| core-003-2026-09-08/pair-regression | Passive E02 prerequisite under 0.4.0 | Complete | [Verification](runs/core-003-2026-09-08/pair-regression/verification.json); all five previous pair cases and numerical checks |
| core-003-2026-09-08/regulatory-regression | E01 under 0.4.0 | Complete | [Verification](runs/core-003-2026-09-08/regulatory-regression/verification.json); complete source/solver/refinement/replay checks |
| num-002-2026-09-08/qualification | Independent CPU bioelectric reference, not a registered Cells model | Complete | [Verification](runs/num-002-2026-09-08/qualification/verification.json); 18 short reference/method cases, refinement, passive limit, code capsule and payload hashes |
| model-003-2026-09-08/acceptance | One physical JAX cell under 0.5.0 | Complete | [Verification](runs/model-003-2026-09-08/acceptance/verification.json); 18 frozen-reference comparisons, exact resume, independently controlled branch, eager/JIT, hashes and snapshots |
| model-003-2026-09-08/composition-regression | Local reaction/transport under 0.5.0 | Complete | [Verification](runs/model-003-2026-09-08/composition-regression/verification.json); eight cases and matrix/refinement/replay checks |
| model-003-2026-09-08/synthetic-regression | E00 under 0.5.0 | Complete | [Verification](runs/model-003-2026-09-08/synthetic-regression/verification.json); pulse, replay and rechallenge |
| model-003-2026-09-08/pair-regression | Passive contact under 0.5.0 | Complete | [Verification](runs/model-003-2026-09-08/pair-regression/verification.json); five cases and independent matrix/refinement checks |
| model-003-2026-09-08/regulatory-regression | Isolated E01 under 0.5.0 | Complete | [Verification](runs/model-003-2026-09-08/regulatory-regression/verification.json); full source/solver/refinement/replay checks |
| spec-002-2026-09-08/native-contact | Instantaneous pinned BITSEY contact/gate probes | Complete | [Native capture](runs/spec-002-2026-09-08/native-contact/reference.json), identical retained [fixture](tests/fixtures/contact_source_probes.json); no integration or assay execution |
| spec-002-2026-09-08/design-check.json | Independent contact/source design calculator | Complete | [Verification](runs/spec-002-2026-09-08/design-check.json); 709 instantaneous checks and explicit source/physical counterexamples, not a pair trajectory |
| num-003-2026-09-08/study-01 | Independent pair timestep/refinement study | Complete | [Study receipt](runs/num-003-2026-09-08/study-01/verification.json); three frozen cases at five predeclared steps, seven passing and eight retained accuracy failures |
| num-003-2026-09-08/qualification | Independent physical-pair CPU reference and method candidate | Complete | [Qualification](runs/num-003-2026-09-08/qualification/verification.json); all 20 cases, three implicit methods/settings, RK4/1 ms and cubic observations, accounting and structural controls |
| num-003-2026-09-08/audit-accepted.json | Separate source/payload and native-state audit | Complete | [Audit](runs/num-003-2026-09-08/audit-accepted.json); 271 payload hashes, 43812 native accepted states, exact event carryover, domain/accounting checks; no new simulation |
| model-004-2026-09-08/acceptance | Physical gated JAX pair under 0.6.0 | Complete | [Verification](runs/model-004-2026-09-08/acceptance/verification.json); 20 frozen-reference cases, complete exact replay, independently controlled future branch and 41-file source capsule |
| model-004-2026-09-08/synthetic-regression | E00 under 0.6.0 | Complete | [Verification](runs/model-004-2026-09-08/synthetic-regression/verification.json); analytic pulse, resume and rechallenge |
| model-004-2026-09-08/pair-regression | Passive contact under 0.6.0 | Complete | [Verification](runs/model-004-2026-09-08/pair-regression/verification.json); five cases, matrix reference/refinement and replay |
| model-004-2026-09-08/composition-regression | Local reaction/transport under 0.6.0 | Complete | [Verification](runs/model-004-2026-09-08/composition-regression/verification.json); eight cases, accounting/refinement and exact replay |
| model-004-2026-09-08/regulatory-regression | Isolated E01 under 0.6.0 | Complete | [Verification](runs/model-004-2026-09-08/regulatory-regression/verification.json); source probes, full E/M trajectories and independent reference/refinement/replay |
| model-004-2026-09-08/physical-cell-regression | One physical cell under 0.6.0 | Complete | [Verification](runs/model-004-2026-09-08/physical-cell-regression/verification.json); 18 frozen cases, complete restart and independent branch |
| model-004-2026-09-08/release-audit.json | Final cross-suite artifact and regression audit | Complete | [Audit](runs/model-004-2026-09-08/release-audit.json); 62 runs, 504 payload hashes and 159 snapshots; 40 previous-model trajectories and 1189 arrays exactly unchanged |
| spec-003-2026-09-08/native-source-pair-02 | Complete instantaneous BITSEY pair RHS, 17 control settings | Complete | [Capture](runs/spec-003-2026-09-08/native-source-pair-02/reference.json), identical retained [fixture](tests/fixtures/source_pair_probes.json); complete prepared-state identity, stale-cache and parameter-restoration audits; no integration |
| spec-003-2026-09-08/design-check | Independent source-compatible design calculator | Complete | [Verification](runs/spec-003-2026-09-08/design-check/verification.json); 3192 checks, frozen panel, 12-file source capsule and unchanged 0.6.0 production identity |
| num-004-2026-09-08/study-01 | Independent nominal coupled timestep study | Complete | [Receipt](runs/num-004-2026-09-08/study-01/verification.json); three frozen cases, four steps each, all 12 pass; largest candidate 0.01 |
| num-004-2026-09-08/qualification-01 | Complete independent nominal pair panel | Complete | [Receipt](runs/num-004-2026-09-08/qualification-01/verification.json); 14 cases, three implicit methods/settings, 28 RK4 trials, full history and polynomial-domain checks |
| num-004-2026-09-08/independent-audit-01.json | Separate payload and saved-state accounting audit | Complete | [Audit](runs/num-004-2026-09-08/independent-audit-01.json); 201 payload hashes, 10808 implicit accepted states, 15 exact event carries, all stored RK4/comparison accounting and orientation control |
| num-004-2026-09-08/native-01 and native-02 | Initial native cohort and lower-overhead observer witness | Complete with retained failures | [Initial receipt](runs/num-004-2026-09-08/native-01/verification.json), [retry receipt](runs/num-004-2026-09-08/native-02/verification.json); six 60-second timeouts retained, S00-fine witness arrays byte-identical |
| num-004-2026-09-08/native-03 | Three longer fine native recaptures | Complete | [Receipt](runs/num-004-2026-09-08/native-03/verification.json); S01/S03/S04 fine pass at 180-second worker budget, no numerical setting change |
| num-004-2026-09-08/native-comparison-01 | Original 42 native paths versus realized and intended references | Complete with retained failure | [Receipt](runs/num-004-2026-09-08/native-comparison-01/verification.json); exact raw updates/caches and realized-state refinement pass; 13 full case gates pass, S12 intended-schedule RNA score 1.22326 fails |
| num-004-2026-09-08/native-event-refinement-01 | Two predeclared further S12 source-clock refinements | Complete | [Capture](runs/num-004-2026-09-08/native-event-refinement-01/verification.json); original inputs/equations/targets unchanged, both new native paths retained |
| num-004-2026-09-08/native-event-comparison-01 | S12 native-clock extension qualification | Complete | [Receipt](runs/num-004-2026-09-08/native-event-comparison-01/verification.json); both added levels meet unchanged state/timing targets; finest event at 0.13755, requested 0.137 |
| model-005-2026-09-08/acceptance-01 | Nominal source-compatible JAX pair under 0.7.0 | Complete | [Receipt](runs/model-005-2026-09-08/acceptance-01/verification.json); 14 frozen cases, full-state replay, independent branch, 46-file implementation capsule, 142 payloads and 47 snapshots |
| model-005-2026-09-08/previous-models-01 | Initial archive audit | Complete with retained failure | [Failure](runs/model-005-2026-09-08/previous-models-01/failure.json); incorrectly included development snapshots with different source. Strict refusal was correct; no solver, source law or tolerance changed |
| model-005-2026-09-08/previous-models-02 | All six prior suites under 0.7.0 and archived 0.6.0 replay | Complete | [Receipt](runs/model-005-2026-09-08/previous-models-02/verification.json); 62 trajectories/2663 arrays exactly unchanged, 500 payload hashes and 157 new snapshots; separately verified all 159 accepted archived snapshots |
| model-005-2026-09-08/release-audit.json | Final cross-suite artifact/source audit | Complete | [Audit](runs/model-005-2026-09-08/release-audit.json); 78 new runs, 642 payload hashes, 204 snapshots, 31 production hashes and 46 implementation-source files; test receipt verified |
| core-004-2026-09-08/acceptance-01 | Independent-world batch acceptance | Complete | [Receipt](runs/core-004-2026-09-08/acceptance-01/verification.json); 10 batches/44 world runs, 14 frozen source cases, full cohort replay, independently solved future branches, 50-file source capsule |
| core-004-2026-09-08/previous-models-01 | Six earlier scalar suites and archived 0.6.0 replay | Complete | [Receipt](runs/core-004-2026-09-08/previous-models-01/verification.json); 62 scalar runs and 2663 exactly unchanged arrays |
| core-004-2026-09-08/source-scalar-regression-01 | Nominal source-pair scalar suite under 0.8.0 | Complete | [Receipt](runs/core-004-2026-09-08/source-scalar-regression-01/verification.json); 14 frozen cases, exact replay and independent branch |
| core-005a-2026-09-08/acceptance-01 | 78 scalar/window regressions, 10 unchanged independent-world batches, archived 0.8.0 replay | Complete | [Receipt](runs/core-005a-2026-09-08/acceptance-01/verification.json); 1777 serialized windows, 5553 prior scalar/cohort arrays exact, 434 old snapshots restored |
| core-005a-2026-09-08/profile-01 | Initial long-graph CPU profile | Refused and retained | [Refusal](runs/core-005a-2026-09-08/profile-01/failure.json); three short workers pass, long full trace exceeds inherited 64 MiB array budget; logs and source capsule preserved |
| core-005a-2026-09-08/profile-02 | Full/32/256-step CPU memory/overhead comparison | Complete | [Receipt](runs/core-005a-2026-09-08/profile-02/verification.json); common declared 128 MiB reservation, 12 workers, identical complete-trajectory digests, measured buffer and RSS scopes |
| core-005b-2026-09-08/acceptance-01 | Initial cohort acceptance-fixture audit | Refused and retained | [Refusal](runs/core-005b-2026-09-08/acceptance-01/failure.json); wrong original/branch event cursor correctly refused; twelve earlier completed cohort runs excluded from final cohort totals, source capsule retained |
| core-005b-2026-09-08/acceptance-01/regression | Scalar/window/full-batch regressions and archived 0.8.0 replay | Complete, reused after re-audit | [Receipt](runs/core-005b-2026-09-08/acceptance-01/regression/verification.json); all 78 scalar trajectories/10 batches and 1777 scalar chunks exact; independent completion remains accepted despite later fixture error |
| core-005b-2026-09-08/acceptance-02 | Corrected cohort recording/restart acceptance and archived 0.9.0 replay | Complete | [Receipt](runs/core-005b-2026-09-08/acceptance-02/verification.json); 20 runs/88 worlds, 95 rounds/254 world windows, 69 complete cohort snapshots and 49-file capsule verified |
| core-005b-2026-09-08/profile-01 | Isolated full/scalar-window/cohort-window CPU comparison | Complete | [Receipt](runs/core-005b-2026-09-08/profile-01/verification.json); 16 workers, 4/16 worlds, full and 32/256-step policies, identical full-field trajectory digests and explicit memory/runtime scopes |
| core-005b-2026-09-08/release-audit.json | Final accepted-source/artifact/restart audit | Complete | [Audit](runs/core-005b-2026-09-08/release-audit.json); 370 saved current-version world records, 948 complete scalar snapshots/99 cohort wrappers, 4902 receipt payload hashes and unchanged 39 production sources; retained-attempt and old-source outputs excluded |
| core-004-2026-09-08/scalar-regression-audit.json | All previous 0.7.0 scalar trajectories compared directly | Complete | [Audit](runs/core-004-2026-09-08/scalar-regression-audit.json); 78 runs, 3511 exactly unchanged arrays, 642 payload hashes and 204 snapshots |
| core-004-2026-09-08/archived-07-audit.json | Preserved 0.7.0 source/snapshot audit and replay | Complete | [Audit](runs/core-004-2026-09-08/archived-07-audit.json); all 31 archived source hashes and 204 old snapshots, exact source-pair state/readout replay, strict current-source refusal |
| core-004-2026-09-08/profile-01 | Separate bounded CPU profiling | Complete | [Receipt](runs/core-004-2026-09-08/profile-01/verification.json); 12 sequential workers, 1/4/16-world graph and source-pair comparisons, all scalar/batch arrays equal, retained compile/host/kernel/output/memory measurements |
| core-004-2026-09-08/release-audit.json | Cross-suite final source/artifact audit | Complete | [Audit](runs/core-004-2026-09-08/release-audit.json); 206 saved current-version world runs and 434 scalar snapshots across acceptance/regressions/profiles, 34 production and 50 capsule sources; archived versions counted separately |
| num-005b-2026-09-08/preparation-01 | Six independent 500-unit preparations and immutable reference packets | Complete | [Receipt](runs/num-005b-2026-09-08/preparation-01/verification.json); 129 trajectory chunks, 258 comparison chunks, 505 observers per preparation, reference/phenotype/separation checks and [independent audit](reports/num-005b-audit.json). No connected E02 path or production candidate |
| num-005c1-2026-09-08/reference-01 | Registered 42-attempt long implicit panel | Session capped / incomplete | [Stopping receipt](runs/num-005c1-2026-09-08/reference-01/failure.json); 24 complete trajectories/eight qualified cases, one partial and 17 unstarted attempts. [Independent subset audit](reports/num-005c1-audit.json) passes; no full-panel, RK4 or production claim |
| num-005c1-2026-09-08/continuation-01 | Registered 18-attempt continuation with eight audited imports | Stopped / reference disagreement | [Stopping receipt](runs/num-005c1-2026-09-08/continuation-01/failure.json); nine new complete paths, two newly qualified cases, one failed comparison and nine unstarted attempts. [Independent audit](reports/num-005c1-continuation-audit.json) and [saved-sample localization](reports/num-005c1-disagreement.json) pass without promoting the failed trio. Aggregate artifacts remain below 1 GiB |
| num-005c1-a1-2026-09-09/bdf-tight-01 | Registered single BDF refinement with three immutable imports | Diagnostic agreement and audit pass | [Verification](runs/num-005c1-a1-2026-09-09/bdf-tight-01/verification.json), [audit](reports/num-005c1-a1-audit.json); 425.555-second session, required score 0.00533, 582,424,320 aggregate retained bytes. Original failure and qualification count unchanged; no automatic additional trial |
| num-005c1-a2-2026-09-09/panel-01 | Explicit A2 adoption, new observers and three remaining controls | Complete under A2 | [Verification](runs/num-005c1-a2-2026-09-09/panel-01/verification.json), [audit](reports/num-005c1-a2-audit.json); all 14 amended-policy conditions/observers qualify. Nine new paths, 1087.264-second session, 715,966,189 aggregate bytes, 1362 passing tests. Original failed campaign remains unchanged; no RK4 or production promotion |
| num-005c2a-2026-09-09/engineering-01 | Twelve short complete-path RK4 profiles at two recording widths | Complete — short engineering only | [Verification](runs/num-005c2a-2026-09-09/engineering-01/verification.json), [audit](reports/num-005c2a-audit.json); exact width/restart evidence, 6144 accepted steps, 783,644,175 aggregate bytes. No long-study resource fit or timestep selection |
| num-005c2b-2026-09-09/diagnostics-01 | Twelve matched scalar/batched diagnostic profiles with full evidence | Profiles and expanded audit pass | [Verification](runs/num-005c2b-2026-09-09/diagnostics-01/verification.json), [audit](reports/num-005c2b-audit.json); 113.854-second session, exact D037 numerical evidence and scalar readouts, 1.84× aggregate checked-time ratio, 803,085,279 aggregate bytes. No compact policy, long run or production change |
| num-005c2c-2026-09-09/evidence-01 | Twelve matched full/basis recording profiles with complete comparison evidence | Profiles and independent reconstruction audit pass | [Verification](runs/num-005c2c-2026-09-09/evidence-01/verification.json), [audit](reports/num-005c2c-audit.json); 99.366-second session, exact D038 evidence/scalar readouts, 57.8% trajectory and 16.7% total profile storage savings, 821,019,434 aggregate bytes. Checked/audited runtime essentially unchanged; no compact long policy, long run or production change |
| num-005c2d-2026-09-09/comparison-01 | Twelve full/backed comparison profiles with unchanged D039 trajectory recording | Profiles and independent dependency/reconstruction audit pass | [Verification](runs/num-005c2d-2026-09-09/comparison-01/verification.json), [audit](reports/num-005c2d-audit.json); 110.829-second session, exact D039 evidence/scalar readouts, 98.5% comparison payload and 80.6% total profile storage savings, 4.2% more checked time, 831,126,114 aggregate bytes. No compact long policy, long run or production change |
| num-005c2e-2026-09-09/evaluation-01 | Twelve frozen/cached scalar evaluation profiles with unchanged lossless recording | Profiles and independent every-stage audit pass | [Verification](runs/num-005c2e-2026-09-09/evaluation-01/verification.json), [audit](reports/num-005c2e-audit.json); 109.176-second session, exact D040 evidence and all 30720 complete stage derivatives, 2.9% less checked and 0.9% less checked-plus-audited time, 834,874,394 aggregate bytes. All 2178 tests pass; no guard, evidence, long-policy or production change |
| num-006-2026-09-09/reference-01 | Fourteen frozen one-cell multispecies cases, independent implicit references and RK4 refinement | Qualified — bounded reference only | [Verification](runs/num-006-2026-09-09/reference-01/verification.json), [audit revision 2](reports/num-006-audit-v2.json), [report](reports/NUM006_REFERENCE.md); 84 attempts, 69.882 s, 38264835 bytes, 0.01 s/cubic candidate selected. 446 targeted tests pass; old source/pilot results and production unchanged |
| core-006-2026-09-09/acceptance-01 | First new-production verification attempt | Interrupted — retained, excluded | [Stopping receipt](runs/core-006-2026-09-09/acceptance-01/failure.json), [explanation](reports/CORE006_ACCEPTANCE_ATTEMPTS.md); manually stopped before changing its captured test-context driver; no numerical comparison failure or reference change |
| core-006-2026-09-09/acceptance-02 | Complete frozen-panel multispecies CPU/JAX acceptance and old-model regressions | Complete — bounded engineering | [Verification](runs/core-006-2026-09-09/acceptance-02/verification.json), [read-only audit](reports/core-006-audit.json), [report](reports/CORE006_ACCEPTANCE.md); 43 scalar outputs/four cohort outputs, 773 payload hashes, 226 scalar/22 cohort snapshots, exact old regressions, 993.226 s and 209703893 artifact bytes |
| core-006-2026-09-09/release-audit.json | Final current-source/checkpoint and test-receipt audit | Complete | [Audit](runs/core-006-2026-09-09/release-audit.json); all 226 scalar/22 cohort accepted snapshots load, 41 production sources and 60 capsule files match, both passing test contexts authenticated; retained interrupted attempt excluded |
| num-007-2026-09-09/reference-01 | Fourteen frozen coupled cell/channel cases, independent references and candidate refinement | Qualified — bounded reference only | [Verification](runs/num-007-2026-09-09/reference-01/verification.json), [read-only audit](reports/num-007-audit.json), [report](reports/NUM007_REFERENCE.md); 98 attempts with six accuracy failures/one stage rejection retained, 196.401 s, 80191978 bytes, selected 0.5 ms RK4/cubic. 214 payloads/19 sources and 947939 replayed sampled rows pass; all 2770 regression tests pass, production unchanged |
| core-007-2026-09-10/acceptance-01 | Initial serial eager/JIT verification | Interrupted — retained, excluded | [Record](runs/core-007-2026-09-10/acceptance-01/failure.json), [explanation](reports/CORE007_ACCEPTANCE.md); 542.853 s and 14107599 bytes, three completed outputs; measured eager cost required revised CPU scheduling |
| core-007-2026-09-10/acceptance-02 | Four-lane eager verification with original evidence allowance | Interrupted — retained, excluded | [Record](runs/core-007-2026-09-10/acceptance-02/failure.json), [explanation](reports/CORE007_ACCEPTANCE.md); 420.650 s and 479163663 bytes, all JIT/restart/cohort/old-regression work passed; projected complete evidence exceeded 512 MiB, revised prospectively to 1 GiB |
| core-007-2026-09-10/acceptance-03 | Complete frozen-panel channel CPU/JAX acceptance and old-model regressions | Complete — bounded engineering | [Verification](runs/core-007-2026-09-10/acceptance-03/verification.json), [read-only audit](reports/core-007-audit.json), [report](reports/CORE007_ACCEPTANCE.md); 43 scalar outputs/two windows/four cohorts, 1580 payloads, 488 scalar/54 cohort checkpoints, 1436.144 s and 546355382 bytes |
| core-007-2026-09-10/release-audit.json | Final current-source/checkpoint, preserved-source and test-receipt checks | Complete | [Release audit](runs/core-007-2026-09-10/release-audit.json), [workspace closeout](reports/core-007-closeout.json); 44 production sources/204 capsule files, 542 current checkpoints, 291 archived members and all 2883 tests authenticated |
| core-008-2026-09-10/acceptance-01 | Complete frozen-panel physical ionic graph CPU/JAX acceptance and old-model regressions | Complete — bounded engineering | [Verification](runs/core-008-2026-09-10/acceptance-01/verification.json), [read-only audit](reports/core-008-production-audit.json), [report](reports/CORE008_ACCEPTANCE.md); 37 scalar outputs/two windows/four cohorts, 600 payloads, 162 scalar/16 cohort checkpoints, 453.536 s and 462687262 bytes. First formal attempt passes; earlier test-harness failures retained |
| core-008-2026-09-10/release-audit.json | Final current-source/checkpoint, preserved-source and four-context test-receipt checks | Complete | [Release audit](runs/core-008-2026-09-10/release-audit.json), [workspace closeout](reports/core-008-closeout.json); 46 production sources/223 captured files, all 178 current checkpoints, 318 archived members and all 3210 tests authenticated |
| core-009-2026-09-10/acceptance-01 | First finite-outside numerical/replay acceptance capture | Numerical pass — retained, superseded for release | [Verification](runs/core-009-2026-09-10/acceptance-01/verification.json), [correction record](reports/core-009-regression-correction.json); 686.208 s, 446950703 bytes. Its captured launcher predates the historical interpreter-path correction; not relabeled or counted in final accepted totals. No numerical failure or physics change |
| core-009-2026-09-10/acceptance-02 | Final captured finite-outside CPU/JAX acceptance and old-model replay | Complete — bounded engineering | [Verification](runs/core-009-2026-09-10/acceptance-02/verification.json), [audit](reports/core-009-production-audit-02.json), [report](reports/CORE009_ACCEPTANCE.md); 43 scalar outputs/two windows/four cohorts, 830 payloads, 235 scalar/21 cohort checkpoints, 631.734 s and 446951333 bytes. All 25,654 arrays exactly reproduce the first run |
| core-009-2026-09-10/release-audit.json | Final current-source/checkpoint, preserved-source and five-context test-receipt checks | Complete | [Release audit](runs/core-009-2026-09-10/release-audit.json), [workspace closeout](reports/core-009-closeout.json); 48 production sources/256 captured files, all 256 current checkpoints, 356 archived members and all 3616 final tests authenticated; failed first matrix retained |
| num-010-2026-09-11/reference-01 | Frozen short spatial reference, temporal/spatial refinement and complete-state restart | Reference and read-only audit pass | [Verification](runs/num-010-2026-09-11/reference-01/verification.json), [audit](reports/num-010-artifact-audit.json), [result](reports/NUM010_REFERENCE.md); 14 cases / 140 main attempts, 0.125 ms RK4/cubic plus passing 0.0625 ms refinement, 14 bitwise restarts, 339 payloads / 21 sources, 523.138 s and 42,701,619 bytes. Seven rejected trials and two completed accuracy failures retained; production unchanged |
| core-010-2026-09-11/acceptance-01 | Recorded spatial CPU/JAX development acceptance | Stopped on wall budget; not accepted | [Failure](runs/core-010-2026-09-11/acceptance-01/failure.json), [preservation](reports/core-010-stopped-preservation.json), [report](reports/CORE010_ACCEPTANCE.md). 53 completed scalar and 12 stream runs independently audit; 10/14 eager cases complete. All 880 files / 77,070,916 bytes retained, no automatic retry or production change |
| core-010-2026-09-11/acceptance-02 | Fresh full spatial panel under v2 resources | Complete — bounded development acceptance | [Verification](runs/core-010-2026-09-11/acceptance-02/verification.json), [report](reports/CORE010_ACCEPTANCE_V2.md). 4381.787 s, 57 scalar runs, 12 streams, 53 comparisons, 912 payloads; full audit/4190-test matrix/closeout pass separately. 352 captured files unchanged; no stable promotion |
| core-010-2026-09-11/closeout-01 | Separate v2 audit, six-context regression and development closeout | Complete — all three stages pass | [Verification](runs/core-010-2026-09-11/closeout-01/verification.json), [handoff](reports/CORE010_CLOSEOUT_HANDOFF.md). 2154.841 s, finished September 11 22:31 UTC; result inspected before BETSE work. No stable promotion |
| ref-003a-2026-09-12/contact-01 | Actual BETSE/Cells instantaneous passive-law comparison | Complete — bounded component correspondence | [Verification](runs/ref-003a-2026-09-12/contact-01/verification.json), [audit](reports/ref-003a-audit-01.json), [report](reports/REF003A_PASSIVE_CONTACT.md). 54 probes / 1047 tolerance comparisons / 15 exact-blocking checks, 4.681 s, ten payloads; 52 adapter tests pass. No trajectory, biological or GPU claim |
| ref-003b1-2026-09-12/alignment-01 through alignment-05 | Native one-cell preparation feasibility | Stopped — fixture rejected, not numerically qualified | [Report](reports/REF003B1_PREPARATION.md), [actual preparation](runs/ref-003b1-2026-09-12/alignment-05/native_preparation.json), [diagnostic audit](reports/ref-003b1-preparation-audit.json). Loader/asset issues retained; final native seed has seven cells / 30 faces with network disabled. Final stop 4.093 s; all 103 short adapter tests pass. No running job or full comparison |
| ref-003b1-2026-09-12/geometry-01 | Native import of one explicit SVG centre | Complete diagnostic — native seed failed | [Native result](runs/ref-003b1-2026-09-12/geometry-01/native_result.json), [completion](runs/ref-003b1-2026-09-12/geometry-01/completion.json). Configuration loads; native triangulation raises QhullError for insufficient points. 4.202 s; failure warning retained, no single-cell success or trajectory |
| ref-003c-2026-09-12/cluster-01 | Explicit seven-cell native initialization/charge/transport/update comparison | Complete — bounded alignment, independently audited | [Verification](runs/ref-003c-2026-09-12/cluster-01/verification.json), [closeout](reports/REF003C_CLOSEOUT.md). 19,691 comparisons, 18.666 s, 14 payloads; separate model-free audit/171 adapter tests pass. All seven cells / 30 faces, two constant profiles, three Cells backends; no full trajectory or automatic follow-up job |
| ref-003d-2026-09-12/trajectory-01 | Actual native FULL versus unchanged Cells checked-RK4 transient | Rejected — complete numerical failure, independently replayed | [Failure](runs/ref-003d-2026-09-12/trajectory-01/failure.json), [audit](reports/ref-003d-failure-audit.json). 79.695 s; all 32 runs complete, no warnings; 36/129384 failed shared-bath amount checks. All 119 files / 23,075,224 bytes retained, no relaxed criterion or relabelled pass |
| ref-003d-v2-2026-09-12/trajectory-01 | Native step refinement with unchanged Cells runs and original-overlap checks | Passed — independently closed D071 | [Closeout](reports/REF003D_CLOSEOUT.md). 104.031 s; all 435,144 comparisons pass with unchanged criteria, 24 native/eight Cells runs, 1120 observed steps. Both packets and captured sources preserved; bounded passive fixture only |
| ref-003e0-2026-09-12/preflight-01 | SIM-from-neutral preparation and prospective no-op event setup | Failed — missing default tissue with profiles disabled | [Finding](reports/REF003E0_PHASE_PREFLIGHT.md). 9.491 s, six retained files, zero completed preparation records; zero-amplitude row not reached. No integration/retry/trajectory qualification; explicit profile bridge required |
| ref-003e0-v2-2026-09-12/preflight-01 | Separate profiles-off/default-profile-on/zero-amplitude preparation controls | Passed — preparation only | [Result](reports/REF003E0_PROFILE_BRIDGE.md). 17.360 s; six independent preparations, 30 direct dispatches, four exact control comparisons, 59 files. No transport/integration, trajectory qualification or automatic follow-up |

Resolved configuration fingerprints, source/runtime identities, timings, and
parent checkpoint hashes are in the manifests and
[verification receipt](runs/m1a-2026-09-08/verification.json). Generated runs are
local and excluded from Git; regeneration commands and retained result constants
are in the acceptance report. No GPU job or ongoing research-lane experiment was
started by this implementation. Old checkpoints require their preserved version's
source and compatible runtime. Archive instructions and composition rerun commands
are in the [latest acceptance report](reports/CORE009_ACCEPTANCE.md).
