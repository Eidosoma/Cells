# Progress

Last updated: 2026-11-24 UTC.

This is the source of current implementation status. Milestone definitions live
in [Roadmap](docs/ROADMAP.md), scientific updates in
[Scientific basis](docs/SCIENTIFIC_BASIS.md), and design choices in
[Decisions](docs/DECISIONS.md). The complete status history up to 8 November
2026, with every earlier run summary and its evidence links, is preserved in
[the archived progress file](docs/history/PROGRESS_BEFORE_2026-11-08.md).

## Open FR and core work (24 November 2026, late)

Sources: [Decisions](docs/DECISIONS.md) D318 to D377, the [feature index](docs/FEATURE_REQUESTS.md) and the tags of 22 to
24 November.

- **Scheduled, from the morning of 25 November:**
  - **The law-ID rename** (D345, D346, D371). Everything live becomes `cells.<family>.<name>@major`; one scripted
    move with a committed mapping table, no aliases. Order: land what is gated, tag main, freeze the pre-rename
    snapshot (D369), then the rename's three read-only checks and the mapping, then the rename with its own gate,
    then re-merge the branches in flight. The family words are decided (D371); the design note comes before any
    script (D350).
  - **Legacy** (D346, D348, D369, D374). Everything actually used leaves legacy in canonical forms; relocation alone
    is ruled out as an end state. The calcium ensemble is kept and re-expressed (five engine features, about 16 to
    28 agent-days as a rough guess, candidate requests only). The physiology stack (17 drivers on five legacy BETSE
    IDs, 18 REF-era drivers) is retired in the approved deletion batch, which needs a dry run, a tag and a removal
    list the user approves. The plan is on `legacy-port-plan` (ef344334); the route (relocate first, re-express directly, or prune in
    place) and whether a CPU re-expression of the ensemble counts are the user's choice, with a dry run's evidence.
    BETSE parity stays on the live `resolved_pump_tissue@1` to `@3` ladder.
  - **Gate speed** (D358, decided by the user): refresh the scope map after each engine landing, record the 37 files
    with unmapped children, and narrow D229's always-run readers rule after a file-open check. The nightly full run
    stays the backstop.
- **Queued builds, in the order the decisions give:**
  - **FR-52** (high; D371, D375): cohort observations for integer units; an engine record at each event, chains in
    version 1, a split makes a new unit. Note on branch `fr52-design`; 4.25 to 5 agent-days, after the rename.
  - **FR-54 and FR-57** (high; D341, D362, D364): one `liquid_routing@1` operator that takes over the wash. Note
    `docs/LIQUID_ROUTING_DESIGN.md` (f66a4828, branch `fr54-57-design`); 8.25 to 10.5 agent-days, after the
    rename. The wash retires only after FR-49's World B and C1 and FR-45's W2 and W7 have run, or those runs are
    pinned to an earlier snapshot.
  - **FR-65** (high, part of FR-43; D365, D375): turnover beside a changing volume, with a lumen. Note `fr65-design`
    (df473a02); about 3.1 to 4.45 agent-days for the first build, 2 to 2.5 more for the volume-reading step.
  - **FR-64** (normal; D356, D361): one declared voltage shift on a channel population, with FR-63 (normal; D353)
    re-formed as a pH shift on it. Note `docs/VOLTAGE_SHIFT_DESIGN.md` (377a1b34, branch `fr64-design`); the build
    follows FR-51's follow-up and the rename.
  - **FR-53** (normal; D371, D370): a rounding allowance for global ledgers. Note `docs/LEDGER_ROUNDING_DESIGN.md`
    (774fdcd5); D370 corrects its premise for the pump-tissue family. FR-47's small `atol_count` ledger fix lands on
    its own.
  - **FR-55, FR-56** (normal; D344, D351): design notes first. **FR-58 to FR-62** (normal; D365): design notes after
    the high items. **FR-66** (medium; D372): a short design note.
  - **FR-39, FR-40, FR-41** (high, D286) and the architecture items (D299) are unchanged; no decision of 23 to 24
    November moves them.
- **Registrations and judged runs still to come:**
  - **FR-51's two-potassium registration** (D353, D355, D356, D361): waits on Lean's re-read of the 5.4 mM anchor
    (the request is with Lean through the user, D376). It is non-blind, and Panama's 10 and 20 mM levels are holdouts. It is written after FR-64's migration or pinned to
    FR-51's landed revision (955765ef).
  - **FR-38's second comparison** (D334, D339, D354, D367): the protocol, references and four amendments are tagged;
    the judge is built on branch `fr38-v2-judge` (4c98bd7a) and not yet tagged; the judged run waits for its tag,
    the builder's export table (§8) and the lead's go. The three uncovered readout controls go to a later
    registration, FR-38 v3 (D354).
  - **FR-45's judge** (D375, D376): written after the rename; W2 and W7 stay on the wash or are pinned.
  - **FR-49's World B and combination checks C1 and C2** (D331): after the site pairing and the wash narrowing;
    C4's four-way form by amendment once admission by species lands.
  - **GJ-N1's field** (D330, D337, D338): the upper end was launched on CPU 13 under amendment 2 (about 23 h, and
    45 to 73 h more if its half step is needed); the rest runs on a gate lane from 20:00 UTC. No field result is
    recorded in D318 to D376.
  - **FR-30** (D343, D344, D350, D366): parked as development-only, narrowly reopened for two phases at a declared
    voltage. Ek-Vitorín 2016 is undetermined by structure (D341, D342); its fit waits for an amendment adding a
    power check and multistart. The Revilla diagnostic lands by merge in the next no-src stack.
  - **Follow-ups:** the docstring-only batch (scope lines of D337, D340, D344, D351, D355, D356); FR-43 part 3's
    open items and the factor-width term (D328); FR-43's gaps 3 and 4 (D347: no registered criterion for part 1;
    turnover in a swelling cell is FR-65); the restart row at a source's switch-off and a per-solver support view
    (D349); a GPU-admission check of the plain `runner.run` against D187 (D372).
  - **Lean tips held** until Lean rewords and rebuilds its unpublished commits (D376); `lean-ready.sh` now runs
    before every Lean merge.
- **Open, unscheduled:** FR-1, FR-2, FR-3, FR-6, FR-11, FR-13, FR-14, FR-15, FR-16, FR-8's rung 2, F1 (after an
  MG0c rerun), crossrev renewal, and the Phase 0 runner's review. FR-17's stage 1 has landed (below); its GPU
  placement is closed (D336).
- **Deferred:** FR-26's L, FR-36. **Parked:** FR-29 (D268), FR-30 (above).

## Landed since 22 November (to 24 November 2026)

Each line gives the merge or tag commit, the tag, the decision and where the evidence is. Tags are named
`<name>-<date>`; tags marked "reg" are registrations, tagged before the engine side reads them.

- **22 November (unchanged from the earlier list):** FR-25's final verdict (D282: inconclusive, 30 of 32 pass,
  none failed); F2, an opt-in exact face heat; FR-33's first test; the OL5 precision fix and GARD @2's range
  fixes; FR-38's sheet, errata, references, reader and engine core; the near-event snap, stages 1 and 2 (D283);
  FR-42's first stage and @3's transport side (D289); FR-31's rupture Phase A (D287, blind test D298); MT-1b's
  world declaration with errata 1 to 3, its reference R2 and the runner fix. Run entries are below.
- **FR-43** (very high; D315, D328, D365, D372, D376).
  - Part 1, the 1,024-species capacity: bbc99163, `fr43-part1-merged-2026-11-23`. Part 3, the integer-unit
    population: 7fb0ad87, `fr43-part3-merged-2026-11-23` (D319, passed). Part 2A: c9687d68,
    `fr43-part2a-merged-2026-11-23`. Part 2B: 2ca07dcb, `fr43-part2b-merged-2026-11-24` (D324, passed). Part 3
    stays open until D152 reactions and the gene unit can co-write a moved row (D328).
  - Part 1's gaps: 14f19f9f, `fr43-part1-gaps-landed-2026-11-25` (the name is a day ahead; landed 23:34 UTC on
    24 November; D376). The 16-row control and the 256-row case are rows with plants; the CPU performance report is
    [PERFORMANCE.md](validation/fr43_part1/PERFORMANCE.md) with `performance.json` (D372). The 256-row case is
    in `tests/tier3_record.json` (04ddd25b).
- **FR-17, stage 1:** the sparse field solver `sparse_capacitive_reduction_gauged_damped_newton@1`, 8760d5b3,
  `fr17-stage1-merged-2026-11-24` (D317). D336's refusal of the composite on a GPU in the vector path: 72893c2a,
  `fr17-d336-landed-2026-11-24`, with D330's evidence driver and its closed record (D336, D338).
- **FR-38's second comparison, registered** (D334, D339, D354, D367): criteria 707014e4
  (`fr38-v2-criteria-2026-11-24`), spec amendments efb311fd, references 8bd81c7e (six files, 19,957,976 bytes,
  within the 20 MB limit), amendment 3 5859006b, amendment 4 b4af13df, sheet erratum I a55a2e12
  (`gr1-sheet-fr38-erratum-i-2026-11-24`; no decision number located). No engine run yet.
- **Fail-closed and rounding fixes, 23 November (validation only):** FR-38's retention-resolution and survival-rounding fixes
  (fd2bb88c, 4944314d), the cohort and release-check fail-closed fixes (275b508f, 1de0055b); decision numbers not
  traced.
- **FR-44:** a6f7a0f4, `fr44-landed-2026-11-24` (D327): the wash reports a typed exchange and labels are diluted
  exactly. **FR-49's judge erratum 1:** 26b70c6b, `fr49-compartment-compositions-v1-judge-erratum-1-2026-11-24`
  (`LABELS_ONLY` gains FR-44's field). **FR-49 parts H and L:** 7d021548, `fr49-expression-labels-merged-2026-11-24`
  (D331); registration d0f9af67, amendment 1 a21381c9, references 35c91d25, judge 0cfdffaa.
- **FR-45:** registration 6e92d0ec (`fr45-site-competition-v1-registered-2026-11-24`), references 8743aa02,
  amendments 1 ae25c28d, 2 ff99fead and 3 98cd33db (D375), references v2 b62ce23c (D376). No engine code for it is on
  main yet (D377); the judge comes after the rename.
- **FR-46 and FR-48:** d702f13a, `fr48-fr46-merged-2026-11-24` (D323).
- **FR-47:** references 426f5ab5, registration 231aae39, build ec7e8c7d (`fr47-merged-2026-11-24`), schedule
  supplement ff9a410e and its erratum 1 fb2b4e3f (D339, D350), the wall-marker fix 9d8c42be
  (`fr47-inert-wall-landed-2026-11-24`, D354). Independent check and supplement passed (D373); development-only
  status lifted.
- **FR-50, phase 1:** 1939563e, `fr50-phase1-landed-2026-11-24` (D363, D372); registration 3a6b56eb, amendment 1
  64e3b923, references 5a59b3c5, judge 3cec272b and erratum 1 a6e48ce9.
- **FR-51:** 955765ef, `fr51-landed-2026-11-24` (D327); registration 5f1f14b5, references 1360c925, judge 5b9b4c90.
  Follow-up, the slot refusal: f66fa681, `fr51-slot-refusal-landed-2026-11-24` (D360).
- **The charge-anchor fix:** 82c26ddd, `charge-anchor-landed-2026-11-24` (D333, D359): the anchor check holds to the
  rounding budget above its 1e-20 C floor. Lean's proof for it merged as 29d69f1d.
- **Lean merges** (unedited, `lean/` only; none touched here): 23 November 872dc2d2 and others in `git log --merges`;
  24 November d3655b0c (tip 8634e566), 29d69f1d, afc28d1d (FR-47 interval heat), 1b3bde45 (tip d5a2c138). One
  merge, 1b3bde45, went in without the privacy scan; the push stands, the waiting tips are held and reworded first,
  and a pre-merge check now runs (D376).
- **GJ-N1:** amendment 1 bbefb664 (`gj-n1-amendment-1-2026-11-23`), amendment 2 750076a7
  (`gj-n1-amendment-2-2026-11-24`, the field on CPUs). The field path d6d42b46 and the 1D line's engine table are
  hashed (D330, [SHA256SUMS](/mnt/workspaces/Cells/gap-junction-20261123/judged/line-01/SHA256SUMS)). The field is
  running or queued (see above).
- **OL6 Protocol G:** registered 16671ae4 (`ol6-protocol-g-registered-2026-11-23`); passed (D322). **Protocol D
  version 2:** registered eced4ef8 (`ol6-protocol-d-v2-registered-2026-11-24`, pinned at eced4ef8, D357); passed
  (D368). **XC0 version 2:** rule erratum 2, b477f433 (`xc0-erratum-2-2026-11-24`); passed (D359).
- **Speed-up, step 1:** the shared compile cache's scripts, 31fde682 (`speedup-cache-step1-merged-2026-11-23`,
  D321): tier seconds and gates stay cold by default; development runs may opt in.

## Judged comparisons since 22 November

Passes are as recorded; the failures stay on record beside any later pass.

- **Passed:**
  - OL6 Protocol G, both scopes (D322): 1,280 of 1,280 seeds at tier 1, 540 statistics at tier 2, plants caught.
    [Verdict](/mnt/workspaces/Cells/ol6-checker-20261123/verdict_protocol_g_both_scopes.json).
  - FR-43 part 3 (D319,
    [verdict](/mnt/workspaces/Cells/fr43-part3-20261123/evidence-52935908/compare/verdict.json)) and part 2's C2.3,
    C2.6/C2.7 and C2.8 (D324, [records](/mnt/workspaces/Cells/fr43-20261123/part2/registered-20261123/)).
  - The gap-junction replication's GJ-L1: 57 of 57 real entries, both plants caught (D325,
    [records](/mnt/workspaces/Cells/gap-junction-20261123/judged/)).
  - FR-49 World L (D331, [records](/mnt/workspaces/Cells/fr49-expression-labels-20261123/judged-0cfdffaa/)).
  - FR-50 phase 1, every criterion and all five plants (D363,
    [records](/mnt/workspaces/Cells/fr50-build-20261124/judged-4872266d/)).
  - FR-51, every criterion, none inconclusive, and all eleven reference-judged plants caught (D377,
    [records](/mnt/workspaces/Cells/fr51-build-20261124/judged-d3b3cf0b/)).
  - XC0 version 2: all claims C0 to C8 pass, disclosed as not blind on the diagnosed rows (D359,
    [record](/mnt/workspaces/Cells/xenopus-lane-20261119/xc0-erratum2-run/)).
  - OL6 Protocol D version 2, all seven worlds on the first seed set (D368,
    [verdict](/mnt/workspaces/Cells/ol6-protocol-d-v2-checker-20261124/verdict/verdict.json)).
  - FR-47: the frozen scorer and, separately, the schedule supplement (D373,
    [verdict](/mnt/workspaces/Cells/fr47-checker-20261124/judgement/verdict.json)).
- **Failed or inconclusive, kept on record:**
  - FR-38's first comparison (D313): R1 failed, R2 inconclusive. The failures are definitional, with no engine or
    reference defect found (D316). A later pass would sit beside it, never in place of it.
  - OL6 Protocol D's first registration (D318): failed on D6's criterion M alone (10.47 against 6), an arithmetic
    artifact. Version 2 passed on fresh seeds (D368).
  - FR-30's Revilla 1999 benchmark (D320): 4 of 6 comparisons, both misses at -80 mV; the law stays development-only.
    The later diagnostic is non-blind and decides nothing (D366).
  - XC0's first run (D329): C0 to C5 pass, C7 and C8 fail, C6 not testable. Diagnosed as rule-side definitions and
    an engine parse tolerance (D332); version 2 passed (D359). The fail stands.
  - FR-17's GPU qualification (D330, D335, D336): closed as failed. G1 and G6 pass under the deterministic flag, G2
    fails as declared (window 1 at 0.514 against the amended bound of 0.291), and the speed gain is about 1.5x,
    not about 3x. GPU device mode is not qualified; the field's longest points run on CPUs.

## Current position

- **16 November 2026.** The levels and the working order are in
  [CURRENT_PLAN](docs/CURRENT_PLAN.md#status-on-14-november-2026-and-the-working-order-d156)
  (D156, with D176's round). The runs below are newest first.
  - **Judged (numerically qualified, CPU only, each within its scope line):**
    - the coupling operator `species_regulated_availability@1` (47 of 47) and MG0c's reactions
      operator `local_species_reactions@1` (55 of 55);
    - D216's FR lane, each against code-blind independent references: FR-4 (21 of 21) and FR-5
      (51 of 51) on 17 November; FR-10's dose schedule (31 of 31) on 17 November; FR-1's closed
      compartment (44 of 44), FR-3's site occupancy (51 of 51) and FR-6's A5″, the channel target
      driven through a per-cell prior (18 of 18), on 18 November. Each is tagged
      `fr<n>-...-qualified-<date>`.
  - **Landed for development, not judged:** the phase start and failure records, Track E's M1
    development work, and independent references for the passive law.
    On 18 November: OL1's origin-of-life laws (`cells.assembly_lineages@2`), verified 6 of 6
    against OL5's code-blind references (run entry below; tag `ol1-landed-2026-11-18`).
    On 19 November: FR-2 version 1, `scheduled_membrane_trafficking@1` (merge 1bd35184). Its
    registered comparison against its code-blind references (run entry below): run 1, 770 of
    782 rows; run 2, after a blind references erratum, 782 of 782, which is weaker evidence
    after the failed run 1. The comparison landed on main (merge d2dc7b8c, tag
    `fr2-comparison-landed-2026-11-19`), so every row is checked in every gate.
  - **Landed (16 November):** D172's single restructure round (D176), as main ab267c39, tagged
    `d172-landed-2026-11-16`, with FR-4's kinds in it. Its gates are in the run entry "D172's round
    landed on main" below.
    The lanes built on it merged the same evening, each after its own gate: core-next, windows,
    fr45-next (FR-5's source kinds and refusals among them), the run-view writer, core-fixes and the
    test audit. The full verification of main a83d8f15 then passed (tiers 1+2, G1 113 of 113,
    crossrev's new record). The next steps are D194's order, starting with D188's moves.
    D188's move 2 landed on 18 November (merge d5d56d1b, tag `d188-move2-landed-2026-11-18`).
    The core-seams pass's code follows it. By 10:46 UTC on 19 November, seams A, C (stage 2) and
    D had landed, with Q2's presence gate, the lift, P1 and B1's last slice (run entry "The
    core-seams pass's morning landings" below).
  - **Proposed designs:** the FR-4/FR-5 physics note, the run view (D154), the module system, with
    its five decisions made (D185), and the human cardiac law set, with its choices made (D184).
    Decided on 16 November and built in D194's order: operator composition (option A, D191), GARD
    (D192) and mitochondria (D193).
    Proposed on 18 November, with options and questions for the user (D216):
    [FR-7's abundance to function and the closed loop's unit](docs/ABUNDANCE_TO_FUNCTION_DESIGN.md),
    [FR-2's membrane retrieval](docs/MEMBRANE_RETRIEVAL_DESIGN.md), and
    [FR-8's long-duration mode](docs/LONG_DURATION_MODE_DESIGN.md).
    The [OL2/OL3 design check](docs/ORIGIN_OF_LIFE_OL2_OL3_CHECK.md) (lipids in and out, and
    fission; D212), with the lead's rulings in
    [§0.2c](docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md#02c-the-leads-rulings-on-ol2s-and-ol3s-design-check-18-november-2026).
    Code follows D188's move 2.
  - **On the L4:** Q7's run-to-run nondeterminism at 825 nodes goes away under the deterministic
    flag (15 of 15 bitwise pairs, D181). Judged alone under the flag on 16 November, Q7 passed, and
    the landing's L4 block passed under it. The W1 full-tissue hold completed its 70-minute
    retention; its comparison with the predictions written before the run is still to do.
- **Single lead agent from 8 November**, with at most seven subagents on disjoint files (six from
  14 November, D155; seven the same evening, D171). Work continues on `main`, and milestones are
  tagged.

**Background: the reset of 8 November.**
- **Reset on 8 November: BETSE is an external reference, not part of the engine.**
  From 30 October the work drifted into re-hosting and transcribing BETSE inside
  `src/cells` (`betse_native_*`, about 110K lines; `betse_normal_*`, about 50K
  lines). The resulting end-to-end demonstration compared BETSE with BETSE; no
  Cells engine model ran in it. That track is superseded; its code was removed
  from the tree (stage A, below) and remains at tag `native-betse-frozen-2026-11-08`.
  Run evidence under `/mnt/workspaces/Cells` is untouched. The rule is in
  `AGENTS.md`.
- **Native demonstration outcome:** 15 actual launches (6–8 November) never
  reached tissue geometry. Every failure was in the provenance, observer, memory
  or wall-time layer. [Actual16](/mnt/workspaces/Cells/native-basic-end-to-end-20261105-01/actual-original-16/failure.json)
  stopped at its 1,800-second limit at 16:06:11 UTC, 20.5 minutes into phase
  construction. This track produced no numerical BETSE or Cells result.

## Plan: BETSE parity on CPU and L4, then JUPITER (from 8 November)

The order (gates and their evidence) is now
[docs/CURRENT_PLAN.md](docs/CURRENT_PLAN.md), adopted 12 November (D145).
This table stays as the status record of the 8 November plan.

Target: BETSE parity of the Cells engine, compared against output from plain
BETSE and run on CPU and the local L4. The JUPITER allocation (10,000 GH200
GPU-hours over about three months) follows; this session moves there when it
starts, and production design is deferred until parity is established.

| Step | Work | Status |
| --- | --- | --- |
| 1 | Plain BETSE reference outputs (default world; seven-cell fixture) | Done |
| 2 | Coverage map of default-world mechanisms, and the parity ladder | Done ([map](/mnt/workspaces/Cells/cells-betse-default-coverage-20261108-01/coverage.json)) |
| 3 | Cells run of BETSE's default world, compared with step 1 (physical route, D131) | Passed (pre-registered protocols D and F) |
| 3b | Parity rung 1: Cl/Ca ions plus the plasma-membrane Ca pump (`resolved_pump_tissue@2`) | v1 failed (one item); **v2 passed** (registered after attribution; weaker evidence) |
| 4 | The same comparison on the L4 GPU | Passed (CPU and L4 identical) |
| 5 | Further mechanism families from the parity ladder, on CPU and L4 | **P2 (ECM barriers), P3 (scheduled interventions, first subset) and P4 (general-network channels) passed** on CPU; **P4b (NaV1.2, Kir2.1, Na leak) passed** (four cases, NaV1.2 including the D-state voltage); **all 12 also pass on the L4** (registered L4 variants, tolerances unchanged; worst 0.996 of tolerance, P2 stage 1 cell K, as on CPU) |
| 6 | JUPITER environment and one-node pilot | Recipe and runbook ready; untested on site |
| 7 | Stage B: neutral names; physiology stack moved to `validation/betse` | **Done** (tag `stage-b-neutral-names-2026-11-09`) |
| 8 | Re-host the short decodability assays on Cells physics | G0 probe viable; channels next |
| 9 | First heredity experiment, E07-v1 ([design](docs/HEREDITY_FIRST_EXPERIMENT.md)) | Channel model (G1), batched worlds (G4), the ledger rounding fix and @3 device checks landed; @3 on the L4 is 2.28 ms per world-step at 256 worlds (tier 1 about 4,100 L4 GPU-hours execute-only, about 7,200 end to end); GH200 throughput unmeasured. **Pre-screens 7–8 (retention, rim renewal) are in doubt**: they start from the fully loaded stationary D composition (+31% osmolarity), while cue-written discs carry H composition and behave differently (W1 sheet check, pre-screen 9); the design choice waits on fresh-disc runs |
| 10 | Morphogenesis track ([plan](docs/MORPHOGENESIS_PLAN.md); D134) | **MG0a and MG0b passed** (MG0 complete); **MG1 (2-D vertex mechanics) passed v2** (57/57; weaker evidence after the failed v1, 52/57) and is landed on main |
| 11 | Optional long-horizon modes (D135): E fixed points and continuation, C projective integration | **E qualified**; **C qualification qual-01 failed** (absolute caps; accuracy against its own estimator passed); F2 not evaluable (no lingering scale found) |

## Runs

Per-run summaries for this plan are added here, newest first, each linking its
machine-readable inputs, results, checks and failures. Landings and judgements of 23 and 24
November are listed in the two sections near the top, one line each.

- **FR-31's rupture Phase A landed (22 November 2026).** Merge a9a67d06, tag
  `pores-phase-a-landed-2026-11-22`. `cells.pore_nucleation@1` under `cells.assembly_hazard@1`, and a
  held membrane tension as a declared work source (`cells.tension_hold@1`). The rupture clock runs on
  the host; the device kernel is untouched. The blind test on the registered predictions passed
  (D298; [score](/mnt/workspaces/Cells/review-check-20261121/pores/score.json)). Gate: crossrev 11 of
  11, tiers 634/0, G1 113 of 113, FR's set
  ([gate](/mnt/workspaces/Cells/pores-phase-a-20261122/gate-a94d6eaf/)).

- **MT-1b's code-blind reference R2 landed (22 November 2026).** Merge ca6fcf2c, tag
  `mito-r2-reference-landed-2026-11-22`, under the world declaration and its errata 1-3 (5ef76150).
  The trace check passes. Every plant is caught; P-b's 2.28 bands on the collapse rows alone and P-a's
  3.45 at plateau ends are recorded as weaknesses
  ([run of record and re-score](/mnt/workspaces/Cells/mito-refs-r2-20261122/)). The engine comparison
  is registered after the face build.

- **The dt ladder and the runner fix (22 November 2026).** 16 µs passes every check on MT-1b's world
  with explicit cycles, so the implicit block is dropped (D302;
  [evidence](/mnt/workspaces/Cells/mito-step0-20261122/)). The host path's closure re-solve is removed,
  bit-identical (b6da1b60, tag `binding-ledger-reuse-landed-2026-11-22`; 182.5 to 143.6 ms per host
  step). The half-step energy check is now the cost driver: about 300 CPU-h per 300 s world.

- **The near-event snap landed (22 November 2026).** Stage 1 (the clock, D283) and stage 2 (5337db54,
  tag `d283-snap-stage2-landed-2026-11-22`): every operator's grid check asks the clock's one predicate,
  within 4 ulps of k*dt, and the applied copy declares the time there. Gate: crossrev 11 of 11, tiers
  633/0, G1 113 of 113, FR's set
  ([gate](/mnt/workspaces/Cells/core-pass-at3-20261118/c-snap2/gate/)).

- **FR-42's transport side landed (22 November 2026).** Merge 48d09332, tag
  `fr42-at3-transport-landed-2026-11-22`: faces' and routes' one-way flows for labelled rows, with
  forward minus backward equal to the booked net at rounding. Gate: crossrev 11 of 11, tiers 633/0, G1
  113 of 113, FR's set ([gate](/mnt/workspaces/Cells/core-pass-at3-20261118/fr42/)).

- **The FR-24, FR-27 and FR-26 stack landed (21 November 2026).** Merges 260e2ed5 (FR-24, a site
  population's quantity as a rate source through the contract's R3), 5fc1364f (FR-27,
  `scheduled_compartment_wash@1`) and 87f1ebef (FR-26 as W, owned state across a cell replacement),
  tag `fr24-fr27-fr26-landed-2026-11-21`, gated once as a stack
  ([gate](/mnt/workspaces/Cells/operators-fr26-20261120/gate-b3ec7811/stack/)): passed, with FR's
  set. G3, gene regulation's moiety hook, followed (5f6053c4).

- **FR-8 rung 1: N2 with (a) landed (21 November 2026).** Merge 03fe5119, tag
  `fr8-n2-landed-2026-11-21`, ID `imex_ars222_implicit_conductances@1`: each membrane's and junction's
  slope conductance in @3's IMEX operator, and the junction gates by their exponential update. I3
  passed on the landed head, 13 of 13 rows
  ([records](/mnt/workspaces/Cells/core-pass-at3-20261118/n2/i3/out-1dfe76ae/)). Gate: crossrev 11 of
  11 identical, tiers 615/0, G1 113 of 113, FR's set.

- **FR-21 landed: the site step and the prescribed shell (21 November 2026).** Merges 4fb9922b (one-step
  binding to a declared site, with the requester's acceptance and FR-22's wash qualification) and
  41338949 (the prescribed shell; the requester's tested revision 9a1a95a5, after a review finding on
  the population probe). Both gated in full, with FR's set and the origin-of-life invariance.

- **Lean fixes landed (21 November 2026), each in place under D148:** the restricted cleft lumen's
  fill heat (2e456bbc), an empty membrane population's abundance (36217958) and membrane insertion's
  heat and image charges at extreme capacitance gains (cdfaed68, after the operators owner's review;
  every registered value bitwise). Evidence in the robustness lane's `*-20261120` folders.

- **Also landed overnight (20 and 21 November 2026):** FR-34's readouts (81a29442) and its example
  (bf7b50af, 1e762583); FR-30's series gates, unregistered (12c18db1); origin of life R4, break and
  renew (a40720a6); FR-28's design note (73115292); FR-29's desk evaluation (1aa82846, 051ab7f7).

- **Gene regulation G1 and G2 landed: option A's equation sheet and the code-blind references (20
  November 2026).** Merges 1f671104 and 4483efa8, tag `gr-g1-g2-landed-2026-11-20`, gated together
  as a stack ([gate](/mnt/workspaces/Cells/gene-regulation-20261120/stack-g1-g2/stack/)). No `src/`
  change. The lane is paused overnight (D255); finished work landed.

- **FR-33 landed: regional labelled-protein readouts (20 November 2026).** Merge ce2a3d9c, tag
  `fr33-region-readouts-landed-2026-11-20`. `validation/regions/`: the region export and a one-way
  cohort tracer, which refuses at setup the two-way movers it cannot see (a review finding), with
  the FR-7 lane's compartment-transfer example. Validation only. Light gate: tiers 616/0.

- **FR-20 landed: a pulse and washout for assembly populations (20 November 2026).** Merge
  3af9ce38, tag `fr20-washout-landed-2026-11-20`: `cells.pool_replacement@1`, with L1 (a
  transition-state factor on a step wholly off the membrane is refused). Q3 is a declared version-1
  limit. Gate: crossrev 11 of 11 identical, tiers 615/0, G1 113 of 113; FR's set and the
  origin-of-life invariance passed ([gate](/mnt/workspaces/Cells/ol3-engine-20261119/gate-e473df3c/)).

- **FR-29 and FR-7 data (20 November 2026).** Kettner et al. 2003 Fig. 3 read as bare values
  (a69f38ab, `validation/vacuole/`), the FR-29 design note (44b44e56) and D258. Ross et al. 2025's
  Kir2.1 variant tables (51dad6a6, D257): they cannot test current against abundance.

- **Mitochondria laws, head 2 landed (20 November 2026).** Merge cf8473de, tag
  `mito-laws-head2-landed-2026-11-20`: `held_reductant_supply@1`, adenylate kinase on beard2005@2
  and the host world test. All ten laws were compared against the registered code-blind references,
  every row in band. Gate: crossrev 11 of 11, tiers, G1 113 of 113, FR's set and the tier-3 files.

- **FR-23 landed: a timed bath dose beside binding sites on other nodes (20 November 2026,
  development).** Merge 4e3d1899, tag `fr23-landed-2026-11-20` (D244, option A). `site_occupancy@1`
  declares its outside reads scoped to the nodes its populations face, and a scheduled dose below a
  ligand's trace is refused. The development run
  ([evidence](/mnt/workspaces/Cells/operators-fr23-20261120/)) passed every criterion written before
  it: the arms bitwise up to the dose; the dose booked as the held content's change, bit for bit;
  bound material unchanged at the dose and rising after it. Gate: crossrev 11 of 11 identical, tiers
  613/0, G1 113 of 113, FR's set passed.

- **FR-8 rung 1, §6: N2 alone on H2's slow phase; a gain of 5, the registered 10 missed (20 November
  2026).** RUNG1 §10.19 on branch fr8-rung1, tag `fr8-rung1-n2c-registered-2026-11-20`
  ([records](/mnt/workspaces/Cells/fr8-rung1-20261119/stage-a/), `stage-a.json`).
  - **The run:** `imex_ars222_implicit_conductances_n2_alone@0` from 0 to 1790 s at 100 ms with X2,
    all 17,900 steps, at the engine of badc86ac.
  - **X2 passes with no refusal:** 8,030 steps counted, 3 held against a cap of 161, integration
    error at most 7.8e-4 against 2e-3.
  - **Against R3:** it passes the parity caps at all 180 rows (0.63 µV, 4.0e-5 relative), and fails
    the adequacy budgets in start-up, which is reported only. Today's integrator at 100 ms is refused
    at its first step.
  - **The miss:** N2 alone reaches 100 ms, a gain of 5 over today's 20 ms; D238's target of 10 needs
    200 ms, which N2 alone does not reach. From t = 0 the dissipation check refuses the third step,
    and after a 100 ms start-up X2's out-of-band count refuses it. 125 ms is not offered, since it
    would be a tuned rung.
  - **Next, registered as §10.20 before it runs:** N2 with C on the final ID. The arm is H2 from 0 to
    3600 s at 100 ms, with a 1 ms window around the cue, 38,079 steps. It predicts a step gain of
    about 94.5 over 1 ms, after the junction gate's update (a) and N2's landing.

- **FR-7 item 3: the releasing compartment, judged and passed (20 November 2026).** Under the
  registration `fr7-u2-compartment-registered-2026-11-20` (95b7b3e0), from a frozen snapshot of main
  439f54fd; tag `fr7-u2-judged-2026-11-20`
  ([verdict](/mnt/workspaces/Cells/fr7-loop-20261119/u2-compartment/judged-439f54fd/VERDICT.json),
  `passed: true`; RUN.txt beside it).
  - Both worlds ran 1,000,000 steps to 1000 s with no refusal.
  - **C2, a releasing compartment:** J1's t_clear 680 s (registered 680 s); J2, the compartment left
    out, 620 s (registered 620 s); the sealed compartment counted, 680 s (information).
  - **C5, release stopped at 300 s:** J1 460 s (registered 460 s); J2, the sealed compartment counted,
    not cleared (registered not cleared); the compartment left out, 460 s (information).
  - The brackets agree with R-clear's to about 1e-10, and c* is within 1e-8 of R-clear's exact rows on
    every row above D150's mean-field floor. The template's account closes to 8e-13 fmol and the
    chain's total is constant to 2e-17 fmol. The engine rows equal the development runs' exactly.
  - C5 took 11,561 s of wall time because its CPU was shared until about 19:15 UTC; the world was not
    the cause.

- **FR-8 rung 1: C, the fine-window executor, judged and passed (20 November 2026).** Under RUNG1
  §10.10, on H2 from 0 to 3600 s at 20 ms with a 1 ms window over [1799.98, 1802.0] s and X2 on
  (tag `fr8-c-judged-2026-11-20`; C landed at 54cb3195, the driver at fr8-rung1 e48c14b1).
  - **(a) Intervention reading:** H2's reading under the parity caps, with the event criteria,
    passes on all 3,831 rows.
    - Largest |ΔVm| 3.3 µV against 20 µV; |Δc|/c 1.4 × 10⁻⁶ against 2 × 10⁻⁴.
    - The peak is within 0.80 µV of the 74 µV criterion's reference, and the crossing within 2.2 µs.
  - **(b) X2:** passes with no refusal. 230 counted steps, median ratio 4.016, 2 held of 8.
  - **(c) Gain:** 19.8 in steps over 1 ms throughout (181,919 against 3.6 × 10⁶). The timed cost
    ratio, 13.6, is reported beside it.
  - **N2:** I3 passed by its rules on N2 alone (badc86ac). Its plant and cap controls never reach
    N2's implicit path, so §10.15 adds charged-world controls on H2 and W0, registered before §6 is
    read. D238 keeps the registered gain of 10.
  - **Records:** /mnt/workspaces/Cells/fr8-rung1-20261119/c-arm/.

- **FR-7's six chain worlds, F3 against R-chain and R-clear: judged, passed (20 November 2026).**
  From a frozen snapshot of main b9d6452d (tag `fr7-chains-judged-2026-11-20`), with main's own
  references interface.
  - **Every world passed:** 4,614 compared rows, none failed. The largest margin is 0.0055 of a band
    (W5's V at 20 s).
  - **Clearance:** every clearance row equals the registered row (260, 280, or 0 without a template),
    computed in the run.
  - **The references' power context holds:** no core row lacks a plant in any world.
  - **Records:** /mnt/workspaces/Cells/fr7-loop-20261119/judged-f3-b9d6452d/ (RUN.txt, VERDICT.json).
  - **Run time:** the worlds with maturation stages (m = 3) ran in 2,500–4,000 s on one shared light
    CPU after the optimization-barrier fix (`fr7-perf-landed-2026-11-20`). Without it, each had run
    past 9 CPU-hours unfinished.
  - **With F4's closed loop** (`fr7-rloop-judged-2026-11-20`), FR-7's first judged comparisons are
    complete.
- **Also landed today, after the morning entry:**
  - K3, chemistry at P (`kinds-k3-landed-2026-11-20`);
  - FR-7's optimization barrier (`fr7-perf-landed-2026-11-20`);
  - the lane check's fix for a unit without a control group (6affa4d2);
  - C, the fine-window executor (`fine-window-landed-2026-11-20`).
- **Registered today, before any engine output:**
  - the mitochondria appendix's second tag (`mito-laws-appendix-2026-11-20b`, D236's repairs);
  - MR1-MT2, the model-level reference (`mito-mr1-mt2-registration-2026-11-20`);
  - the component references (`mito-components-registration-2026-11-20`);
  - gene regulation's equation sheet (`gr1-sheet-2026-11-20`, option A).
- **Decisions:** D236 (Beard's repairs; FR-7's development chains stopped) and D237 (FR-20 to
  FR-22 at high priority).

- **FR-7's first closed loop, F4 against R-loop: judged, passed (20 November 2026).**
  - **The run:** from a frozen snapshot of main 90392025 (tag `fr7-rloop-judged-2026-11-20`), with
    main's registered interface (`fr7-references-landed-2026-11-20`; R-loop registered under D233 at
    d55e39b4 before any engine output).
  - **The arms:** both, closed and clamped. Every compared row is within its band; the clamped arm's
    largest is s at 0.42 of a band.
  - **The cut:** F*_engine is within its registered bound, -1.36e-7 against 2.82e-7.
  - **Clearance:** the clearance row equals the registered 260 s.
  - **Persistence:** all 30 rows pass; the rise in units at 560 s is 93.390 against 93.389.
  - **The pump rate,** read from the engine's own readouts, matches the cumulative pump_cycles
    ledger to 5.6e-9.
  - **Records:** /mnt/workspaces/Cells/fr7-loop-20261119/judged-90392025/f4/ (RUN.txt, f4_comparison.json).
  - **Still to come:** F3's six-world comparison against R-chain and R-clear is queued from the same
    snapshot.
- **Also landed this morning:**
  - `kinds-k124-landed-2026-11-20` (206d5c7b): K2's trapezoid, K4's proton readouts, and K1's moved
    fuel at closure nodes. The binder acceptance on main closes every ledger with a moved ATP
    binder row.
  - `binding-defer-landed-2026-11-20` (4ca478b8): a base-form move of a closure-held row with forms
    is judged by the closure's section 5.2 admission.
  - `fr7-comparisons-landed-2026-11-20` (90392025): FR-7's chain and loop mappers and comparisons.
  - `gate-tooling-landed-2026-11-20` (7c87943c): the fail-fast gate, stacked gates, the no-src scope
    map, the cache qualifier and the nightly tiers. The nightly timer is installed and runs at 02:30
    UTC.
  - Decision D235: FR-8 builds N2, then C; mitochondria on host P; gene regulation's option A.

- **The mitochondria engine groundwork and the X2 floor fix (20 November 2026, early morning).** Each
  was gated in full and passed the lead's merged check.
  - `monomial-kernel-landed-2026-11-20` (d9342fcf): the cycle kind's fourth kinetic form, `monomial`
    (K6's kernel).
    - Exact closed-form slopes; read roles; references to registry forms under the binding owner's
      three conditions; a one-sided domain x <= 80; k built at parse from a cited free energy.
    - An invariance trace of five general-layout worlds caught one jaxpr break before landing. Crossrev
      holds no general-layout world, which is a gate-tooling follow-up.
  - `binding-sets-followup-landed-2026-11-20` (11dc95c5): a named potential set requires its moieties,
    records and checks its proton buffers, and versions its derivation.
  - `kinds-seam-e-landed-2026-11-20` (e658a8fd): a monomial mode's cited rate constant emits its seam-E
    entry in kJ/mol form. k and the entry share one value.
  - `x2-floor-fix-landed-2026-11-20` (4802dc9a): the general binding closure's booked energy term is
    formed from increments through the closure's dual (D148: states bitwise).
    - It removes a rounding floor that failed X2's order condition in buffered worlds: R's median
      |e| falls from 9e-13 to 1.4e-17 pJ.
    - FR-8's worlds never met the floor.
  - **FR-8 rung 1's control** (from d03ca463; analysis registered). Largest passing steps under the
    parity caps:
    - H2's calm stretch, 20 ms, held by charge stability, also from the calm state at 1000 s (section
      10.8's probe);
    - H2 through the cue, 1 ms, by the location rule;
    - W0, 5 ms, by the junction-gate bound.
    - X2 refused nothing. Its sensitivity is shown at each world's largest step, and FR-3's plant is
      caught.
    - Cost per simulated second: H2 calm 0.020 s, H2 full 0.34 s, W0 0.32 s.
    - The choice between D232's rules is the user's.
  - **P1' (the @3 owner, on its branch):** both hosts are accurate in the delta-psi mode and give
    branch E under X2 with the floor fix. At the source's synthase activity, explicit steps cost
    1,000-30,000 CPU-hours per 300 s, and lowering the activity ruins the fit beyond 4-7 times. An
    implicit block or a rapid-equilibrium synthase is being priced for the user's host ruling.

- **The night's landings, 20 November 2026 (core, FR and the mitochondria groundwork).** Each was
  gated (tiers 1+2 with 0 changed, G1, crossrev, IDs, FR's set where it applies) and passed the lead's
  merged check against main.
  - `kir-ratio-landed-2026-11-20` (e3026388): the inward rectifier's sqrt(c_o/K_ref) formed
    overflow-safe, in place (D148). The Lean project found it; the equivalent declarations now agree
    bit for bit. d/dK_ref is undefined at split points, and the engine never takes it.
  - `kcc-step-bound-landed-2026-11-20` (2e2dc62f): the KCC step bound counts a finite outside node,
    summed per cell and per node. This closes a silent wrong-direction step, also found by the Lean
    project. Every registered world faces held baths and keeps its bits. The quotient-overflow fix
    stays held until its evidence covers every execution path.
  - `symporter-v2-landed-2026-11-20` (99bff0ed): `na2_anion_symport_diagram@1` (D228 item 1).
  - `fr15-p2-landed-2026-11-20` (ce39c904): `passive_constant_field_permeation@1` on the
    passive-routes kind. One file timed out under load; it passed on rerun.
  - `fr7-f3-landed-2026-11-20` (5dc63d38) and `fr7-pools-landed-2026-11-20` (549b1b6c): FR-7 F3, the
    producer's assembly rate as a B1' target; and declared initial units per maturation pool (W5).
  - `kinds-schedules-landed-2026-11-20` (ef76795e): the cycle kind's availability schedules
    (D228 item 5), and the population bound in log space (D148).
  - `mito-references-landed-2026-11-20` (bd29e2ae): MR1, the code-blind Beard 2005 reference.
    Six unrelated engine tests timed out under load; on rerun, five passed and one failed only by
    its CLI subprocess's timeout.
  - `binding-mito-landed-2026-11-20` (aa847046): B1's `beard2005@1` named potential set, B2's
    moieties, and FreeEnergyEntry's kJ/mol form with `dG_RT_offset` (F's, merged unedited).
  - **FR-7:** F4's engine run from the registered R-loop start drifts by at most 1e-10 relative over
    10 s. Its dosed closed arm peaks at N/N0 2.459, matching the reference's 2.46. F3's six-world
    comparison and F4's comparison are still running as development runs.
  - **Mitochondria (D234):** the laws' appendix is tagged `mito-laws-appendix-2026-11-20`.
    - The code-blind component references are built and await registration.
    - MR1's repair table shows Beard's printed Eq. 24 is a typo: the restored form is what the
      paper ran.
    - @3's P1′ finds both hosts accurate in the ΔΨ mode. At the source's synthase activity, explicit
      steps are out of reach, and X2's count rule shows a floor, being traced.
    - The host and the repairs are for the user's ruling.

- **The fourth review's fixes, FR-7 F2 and FR-7's references (19–20 November 2026).**
  - Merge a740b856, tag `review4-fixes-landed-2026-11-20`: the external review's four findings,
    each a recorded exception with a test row.
    - The composite's device checks split ledger magnitudes at the operators' count.
    - A bound that is not finite fails its ledger.
    - FR-8 rung 0's reader checks each arm's identity, step and grid.
    - @3's batch signature carries each kind's axis sizes.
    - Gates: tiers 595 files with 0 changed, crossrev 11 of 11, IDs +2, FR's set, R1 (274
      fingerprints equal); the lead's merged check on trial 2816efb0 (527 passed).
  - Merge 73d73bf8, tag `fr7-f2-landed-2026-11-20`: FR-7 F2 (development).
    - `species_regulated_availability@2` reads a population's abundance as its source.
    - `population_unit_turnover@1` states D232's scoped exception to D177.
    - Gates: tiers 597 files with 0 changed, G1 113 of 113, crossrev 11 of 11, IDs +21, FR's set,
      R1; the lead's merged check on trial a72e1f10 (271 passed).
  - Merge 9dd869c6, tag `fr7-references-landed-2026-11-20`: FR-7's code-blind references, R-chain,
    R-clear and R-loop. Each was tagged before any engine output (69932dfc, 1b257cf3, d55e39b4).
    - R-loop follows D233's five-fold template, with its floor-sensitivity table registered.
    - design.py's regeneration check was loosened after R-chain's tag; no registered value changed.
    - Gates (no src change): tiers 601 files with 0 changed, IDs +15.
  - Decisions D233 (FR-7's template ×5) and D234 (the roadmap's Option 2; gene regulation's design
    begins). docs/CORE_LAWS_ROADMAP.md landed docs-only (7ebfab70).
  - **Tagged, not yet landed:** the code-blind Beard 2005 mitochondria reference, MR1
    (`mito-references-model-2026-11-19`, a9aac583).
    - It reproduces the published curves to about digitisation precision.
    - Its audit finds Eq. 11 (F1F0) dissipating negatively at the paper's own state-3 points.
    - Its registration waits for the user's ruling on the declared departures.

- **Seam E's checks and F's cleanup (19 November 2026).**
  - Merge bd9881d5, tag `binding-item5-landed-2026-11-19`: the species registry checks every declared
    `FreeEnergyEntry` against its own sum of ν μ°/RT, within the form's band. Gates: tiers 594 files
    with 0 changed, G1 113 of 113, crossrev 11 of 11, IDs +11, FR's set; the lead's merged check on
    trial b50835af.
  - Merge 985c6a44, tag `f-energies-cleanup-landed-2026-11-19`: a bare 3-tuple from a
    standard_free_energies hook is now refused, since every hook returns FreeEnergyEntry. Gates:
    tiers 594 files with 0 changed, G1 113 of 113, crossrev 11 of 11, IDs +0; the lead's merged check
    on trial ee082f5d.

- **FR-15 S1: charged species in `local_species_reactions@1` (19 November 2026; in place under
  D148).** Merge ddb52790, tag `fr15-s1-landed-2026-11-19`. Reactions may involve charged species
  when every reaction conserves charge. A charged row stays impermeant on @3's routes unless it is a
  declared counter-ion covered by @3's own charge-relaxation bound, 100 times its material term.
  Charged turnover routes are deferred; exchange stays neutral. Gates: tiers 594 files with 0
  changed, G1 113 of 113, crossrev 11 of 11 identical (the D148 evidence), FR's set; IDs with one
  declared rename; X2 checked (admitted; no counted steps, so no power there); the lead's merged
  check on trial 29c44900.

- **R2, the view into `control_factors` for a factor operator's current reads (19 November 2026;
  @2 only; FR-7's F2 prerequisite).** Merge 6c501ab3, tag `r2-landed-2026-11-19`. A factor
  operator may declare a current read at the control view, and the composite passes C4's reader
  view to its hooks. No registered operator declares one, so no existing program changes. Gates:
  tiers 594 files with 0 changed, G1 113 of 113, crossrev 11 of 11, IDs +1, FR's set; the lead's
  merged check on trial 25128f4e.

- **The inward-rectifier route law `inward_rectifier_linear_driving_force@1` (19 November 2026;
  D228 item 2).** Merge 2db46727, tag `rectifier-landed-2026-11-19`. An instantaneous inward
  rectifier on the passive-routes kind: E_K-referenced rectification, √K_o scaling, coefficients in
  the route's declaration (unsourced today), weak rectifiers through V_h and s. Kir4.1 for the
  Xenopus lane's XC0 is its first use. Gates: tiers 594 files with 0 changed, G1 113 of 113,
  crossrev 11 of 11, IDs +5, FR's set; the lead's merged check on trial 4da4ec58.

- **FR-7 F1: the unit producer `population_unit_turnover@1` (19 November 2026; development, not
  judged).** Merge 7fb27a92, tag `fr7-f1-landed-2026-11-19`. A finite precursor is consumed at first
  order into channel units, through m maturation pools, with first-order removal of every unit into
  a booked sink. The half-step is the chain's exact solution, so the one material account closes by
  construction. It departs from D177 by holding removal inside the producer. Gates: tiers 593 files
  with 0 changed, G1 113 of 113, crossrev 11 of 11, IDs +40, FR's set; the lead's merged check on
  trial aa2ef4fa.

- **X2, the opt-in step-doubled energy check `step_doubled_energy@1` (19 November 2026; FR-18's
  criterion, D224).** Merge fd894b91, tag `x2-energy-check-landed-2026-11-19`. Selected by
  `spec.energy_check`, and required of registered and judged runs. Each window compares one step
  against two half steps, within the registered band. Qualification: 13 rows, each with its saved
  verdict; FR-3's planted energy error is refused at its step. Overhead about 1.22× per run
  without compile. Gates: pre-gate, tiers 593 files with 0 changed, G1, crossrev 11 of 11, IDs +9,
  FR's set; R1 differs only by the declared field default; the lead's merged check on trial
  050c8f17.

- **B1′, the operator rate route, on `species_regulated_availability@2` (19 November 2026; FR-7's
  part (a), D218; development, not judged).** Merge ee43b082, tag `b1prime-landed-2026-11-19`.
  Turnover's and reactions' rates may be scaled by a coupling factor F ∈ [b, 1], evaluated at the
  start of each target half-step, with a declared operating range refused when breached and the
  applied factor recorded exactly. @1 is untouched, so FR-6's judged result stands. Gates: tiers 593
  files with 0 changed, G1 113 of 113, crossrev 11 of 11 identical (coupling and acceptances), FR's
  set; IDs with the contract-enumerating file declared; the lead's merged check on trial 8a482a26.

- **The transporter's standard free energies as `FreeEnergyEntry` (19 November 2026; seam E,
  kinds follow-up 2).** Merge 4e6ca60e, tag `kinds-fu2-landed-2026-11-19`. Each entry names its
  cycle law and mode, and `CycleForm` gives its band from the form. Every kind on main now declares
  FreeEnergyEntry. Gates: the kinds owner's lane A, FR's set and tier 3; the lead's merged checks on
  trials 4361bf5a and 8d4e5f92 (stacked on the symporter's).

- **The electrogenic Na⁺-coupled anion symporter, version 1: `cells.na_anion_symport_factored@1`
  (19 November 2026; D228 item 1).** Merge 845ee670, tag `symporter-v1-landed-2026-11-19`. A
  fuel-free factored cycle law on the transporter (n_Na from 1 to 4), cited to Coady et al. 2007
  (abstract) for 2:1; the Xenopus lane's XC0 world needs it. Refused at a compartment's node, as
  stated. Gates: the kinds owner's lane A, FR's set and tier 3; the lead's merged checks on trials
  6875e1bb and 3c923f22.

- **The presence gate hosts channel and face slots (19 November 2026; the operators owner's
  GATED_SLOT_AXES follow-up).** Merge 79d0fc7c, tag `ops3-gated-slot-axes-landed-2026-11-19`. A kind
  with presence on channel populations or faces is admitted beside a closer, which closes those
  populations by their hosts; an own axis without `axis_hosts` stays refused. Gates: tiers 592
  files with 0 changed, G1, crossrev 11 of 11, IDs +0, FR's set; the lead's merged check on trial
  2daf2363.

- **The kind contract's array-axes check and `Kind.dispatch_masks` (19 November 2026; D228 item
  6).** Merge c545be8e, tag `f-axes-check-landed-2026-11-19`. Each kind field's array must match
  its declared axes where @3 binds it; fields empty by static dispatch are named. With the
  operators owner's three review changes and the proton leak's docstring correction. Gates: tiers
  591 files with 0 changed, G1, crossrev 11 of 11, IDs +1, FR's set; the lead's merged check on
  trial 8b595e5c.

- **Cl⁻ in @3's channel populations: the always-open chloride leak `cells.clleak_always_open@1`
  (19 November 2026; D228 item 3).** Merge 6ed4b280, tag `f-chloride-leak-landed-2026-11-19`. @3's
  valence table admits Cl⁻ at −1, and the planted test laws move to code 99. The Xenopus lane's
  Cl⁻-only patch needs it. Gates: tiers 590 files with 0 changed, G1, crossrev 11 of 11, IDs +3,
  FR's set; the lead's merged check on trial 7e125758.

- **The third external review's five findings, fixed (19 November 2026).** Merge 560da6a0, tag
  `review3-fixes-landed-2026-11-19`. Engine models touched: the transporter, passive routes, pH
  condition and proton buffer kinds; `surface_pump_v3`; `scheduled_membrane_trafficking@1`.
  - The general closure's proton is declared (proton_row), never inferred from a charge.
  - FR-2 version 1 holds one receiving pool per cell; two routes of one cell are refused.
  - @3's trace estimate counts every declared kind's saved rows, and an undercount is refused. FR's
    landing-set verdict reads the planner's estimate as information.
  - The transporter's probe reads the solver's own switch for its population-scaled fields.
  - FR-8 stage 0's judges get their observations, with the registration's amendment 5.
  - Gates: tiers 591 files with 0 changed, G1 113 of 113, crossrev 11 of 11, IDs +6, FR's set, R1
    274 of 274; the lead's merged check on trial c3171354.

- **FR-8 rung 0: the fine engine's order through a switch (19 November 2026). Registered verdict:
  "instrument not validated". Under a blind amendment, the weaker evidence: the cause is the
  pre-asymptotic transient.**
  - **Engine model it runs:** `resolved_pump_tissue@3` alone. Development, not judged.
  - **Evidence:** [the registration and results](validation/long_duration/RUNG0_20261119.md), the
    windows' inputs (`rung0_20261119.json`) and condensed results (`rung0_results_20261119.json`).
    Landed at 6cec0fc4, tag `fr8-rung0-landed-2026-11-19`.
  - **The registered verdict stands:** the slow-phase control had no power, so no cause is
    identified (§9.1).
  - **Under amendment 1** (§9.2), a powered control registered blind before the main windows were
    read: the instruments pass, and the order drop in stage 0's switch transient is (C), the
    pre-asymptotic transient. The observed orders climb toward 2 as the step halves; NaV activation
    goes from 1.26 at 1 ms to 1.98. The cue's discontinuity is not implicated.
  - **Provenance after the fact** (§9.5): the windows start from R3's saved state under the
    continuity design's rule (b). R3's digest was recorded afterwards, and all 43 importing arms
    start bitwise equal to R3's rows.
  - **Next:** rung 1 (N2 with the exponential junction-gate update, opt-in) after X2 lands.

- **FR-2 version 1 against its code-blind references (19 November 2026): run 1, 770 of 782 rows;
  run 2, after a blind erratum, 782 of 782, which is weaker evidence after the failed run 1.**
  - **Engine models it runs:** `scheduled_membrane_trafficking@1`, on `resolved_pump_composite@1`
    over `resolved_pump_tissue@3`.
  - **Evidence:**
    - branch `fr2-comparison` at 65d8c1e4, tag `fr2-comparison-run1-2026-11-19`;
    - the bands registered beforehand on `fr2-references-interface` (77fd8a17, interface file
      `comparison_bands.json`);
    - the run's per-test outcomes in
      `/mnt/workspaces/Cells/fr2-retrieval-v1-20261119/runs/cmp-first/junit.xml`.

    A timed second execution gave the same outcomes.
  - **The failures:** electrode transfer, electrode work and image charge at the held bath node, on
    four small recycling half-steps, at 1.2–9.2 times their bands (relative deviations 3.4e-14 to
    1.8e-13).
  - **The diagnosis, engine against engine:** an exact rational replay from the engine's own state
    accounts for each deviation as double-precision rounding of the held node's plate charges, about
    1.3e-12 C. Their difference is the transfer. The exact replay agrees with the references to about
    2e-31 C.
  - **The erratum:** the references agent audited the class blind, without seeing any result.
    It found its floor for the held-node checks assumed an engine product form it had never
    registered, and so did not follow from its registered model. It corrected the floor as a dated
    erratum (bf8bbb4d), carrying the registered potential floor through Q_h = ΣC·V.
    - 87 bands changed, 29 each for electrode transfer, electrode work and image charge, widened
      133–2236×.
    - No other row, tolerance, plant, criterion or band rule moved; the lead checked this.
  - **Run 2** (12:55 UTC, branch `fr2-comparison` at 71a044cc, tag `fr2-comparison-run2-2026-11-19`;
    outcomes in `runs/cmp-second/`): the engine is run 1's, plus the erratum's four reference
    files only.
    - All 782 engine values are bitwise equal to run 1's.
    - 1110 of 1110 tests pass: 782 of 782 rows, 3 of 3 criteria and 322 of 322 plants.
    - The largest margin is 0.0045 of its band, in the corrected class, and 0.0036 elsewhere.
    - **This is weaker evidence after the failed run 1:** its bands were corrected after run 1 failed.
  - **Landed** at d2dc7b8c (tiers-and-IDs gate at 97a9ca11; merged check on trial 9b24667a),
    with the references' interface bands and their erratum.
  - A kernel form that would avoid the cancellation is logged as an engine note for a later
    declared-freeze batch.

- **The core-seams pass's morning landings (19 November 2026, 03:56–10:46 UTC).** Twenty merges.
  Each merge's message records its gates. The merged checks and the tier folds are in
  `/mnt/workspaces/Cells/core-pass-kickoff-20261118/` (`replication-checks/`, `landings/`).
  - **Seams:**
    - seam A, the general cycle kind (ee30e5d9), with its comparison against the code-blind
      references;
    - seam C stage 2, the general rapid binding closure in whole worlds (aecbaed1), and its C4
      follow-up, mixed-sign binder forms admitted against the exact joint margin (4736d974);
    - seam D, heat bookings (6ca4a56f).
  - **Kinds beside closers:** Q2's presence gate (e4f84d4a); the kind contract's internal_axes and
    presence (266624d8); and the lift (b1ca8b68), which admits a kind beside a closer when every
    entity axis declares presence.
  - **The operators' lifecycle:**
    - items 1–3 (4a9a696a);
    - the composite's channel_targets, closing FR-8's settling gap (7d3f24ef);
    - B1's last slice, the role-driven lifecycle at division and retirement (3fd9c17c).
  - **P1** (9e181b08): the predictor for stage reads under a free-amount closure.
  - **The registry:**
    - the public cycle_changes reader (e1dc12d5);
    - the five Kv1 channel laws as @3's law homes (c7d570a0), with @3's Kv1 trigger (c1e5d3d0);
    - role_species (c08e6ea9).
  - **References registered before the outputs they judge:** amendment A2's erratum (9e005bb9);
    amendment C5, release steps in the binding envelope (8a9d7ae7); and FR-2's code-blind
    references (8c92f6ac).
  - **FR-2 version 1** (1bd35184; development, not judged).
  - **The viewer:** Version 44 (8e6d6c18).
  - **Tools:** `test_tiers.py fold` places a row that reached the cap in tier 3 (37855d1c).
  - **Refusals kept, with their fixes:**
    - seam A's merged checks refused twice. Trial 81a9fd5c failed 6 of Q2's tests, fixed by
      declaring the internal axes and presence. Trial 5a986c1f failed 2 of seam A's own tests,
      written before the lift landed, fixed by a test-only commit (90a4dd7e);
    - the binding owner's cb01a837 failed its tiers (A7's sum guard, and a too-wide water
      refusal), fixed at bae02d29;
    - item 4's bed34e3d failed the S5 staleness guard, fixed at 317f6e95.

- **The core-seams pass's next landings (18 November late evening to 19 November 2026).** Each
  merge's message records its gates. The merged checks and the tier folds are in
  `/mnt/workspaces/Cells/core-pass-kickoff-20261118/` (`replication-checks/`, `landings/`).
  - c78462e7: composition's M1, the fixed-read rule with closures' exact reach.
  - 5e2c78e9: the first external review's findings 1 and 4.
  - de7dfeb9: seam C's three reference amendments, registered before any output of the general
    closure.
  - e515b87b: refusal 4 version 1.3, the compartments admission judged by the moves at the
    compartment's node.
  - 09ac1743: B1's first two slices, the operators' energy roles and E's standard_free_energies
    hook.
  - d64fb664: @3's guard landing, with B1's @3 part, the run view's format items and the
    moved-rows guard.
  - 34cdd34b: F's registry hand-offs, the kind fields' axes and hosts, `forms` and seam A's
    `cycle` on cycle laws, and the general closure's fields on binding laws.
    - Gate on lane B: tiers 555 files, 0 changed; G1 113 of 113; crossrev 11 of 11; IDs
      additions only.
    - main was the gate's base, so the merge's tree is the gated head's.
    - It carries the second external review's finding 5: an ensemble adapter family's model ID
      works in either form through the launch path.
  - 51cd419f: the gate tools move into the repository (D220) as `scripts/gates/`.
    - FR's landing set's lane check charges by process, so a waiting unit no longer refuses it.
    - crossrev's set runner fails closed.
    - `test_tiers.py fold` folds a landing's rows onto main's record.
  - f5025e6f: FR-8's stage 0, the long-duration methods measured (development, not judged).
    - Results: `validation/long_duration/RESULTS_20261118.md`.
    - The method choice goes to the user as options.
  - 6bc32a01: the core-seams references' amendments F4 (finding 4's zero-slope fix), C4 (the
    closure's joint validity) and A2 (seam A's needs).
    - Its merged check refused on one load-sensitive tooling test, which passed idle. Since then
      the test waits for CPU time (39d51865).
  - **Each of these lands through a stacked trial.** The trial merges are checked side by side,
    and a landing's staged tree must equal its checked trial plus main's later paths
    (`tools/assert_landing_tree.py`).
  - **The landing check, version 2,** adds the test files changed on either side since the
    merge base to the replication and crossrev checks. Its self-test refused the unfixed F trial,
    where seven tests broke.

- **The core-seams pass's first landings (18 November 2026, evening).** Four branches merged into
  main. Every core head is checked again on its merge with main, because main's src/ moved between
  them (CORE_SEAMS §18, amended at 18:31 UTC).
  - **The references for seams A and C,** merged at 746a37ef: registered before either seam's first
    output (§19).
    - Gate: tiers 1+2 534 files, 0 changed; G1 113 of 113; crossrev 10 of 10; IDs additions
      only.
    - Evidence: `/mnt/workspaces/Cells/core-seams-references-20261118/gate-808d346f/`.
  - **@3's host table** (dd9758ef), merged at ea261379:
    - lane A: tiers 534 files, 0 changed; G1 113 of 113; crossrev 10 of 10;
    - FR's bitwise landing set passed;
    - the replication check: 55 of 55.
  - **crossrev's replication set,** merged at 460d766d: five quick worlds of the gap-junction
    replication (D219), whose baseline was recorded from src/ before any core head.
    - Gate: tiers 535 files, 0 changed; G1 113 of 113; crossrev 10 of 10; replication 55 of 55.
    - It was installed into the record of record at 21:18 UTC. Main's eleven sets are all
      identical.
    - The acceptances set (0a91d426) had been installed at 19:07 UTC.
    - Evidence: `/mnt/workspaces/Cells/crossrev-replication-20261118/install-460d766d/`.
  - **F's laws as modules** (8e11638a, which carries the step terms 8c2cb523), merged at 599b8610.
    - Lane A: tiers 534 files, 0 changed; G1 113 of 113; crossrev 10 of 10; IDs additions only.
    - FR's set passed at both heads.
    - Tier 3's test_surface_calcium_channels passed, 89 with 1 skipped.
    - The merged check: replication 55 of 55, and crossrev 10 of 10 against the record.
    - test_inner_laws.py moves to tier 1.
  - **Tier rows** are folded at each landing from the landing's own measured file onto main's
    current record. The merged-head checks and the folds are in
    `/mnt/workspaces/Cells/core-pass-kickoff-20261118/` (`replication-checks/`, `landings/`).

- **core-fixes carried across move 2 and landed (18 November 2026).** Merge 270825ab
  (core-fixes-m2 2d22a666): D3 and D4 (ff5ca5ff, 0a00ba6e) and G's item 1 (9b0d8baa).
  - **Carrying it.** Git placed the edits in the moved files. move2.json's apply then brought them
    to the new homes (c4881c6d), after a tool fix (06bcbba9) for merging a post-move main.
  - **One semantic fix:** seam F's step 1 had renamed `LAWS` to `VERSION_1_LAWS`.
  - **The gate:**
    - tiers 1+2: 533 files, 0 changed;
    - G1: 113 of 113;
    - crossrev: 9 of 9;
    - IDs: additions only;
    - FR's bitwise set passed, and R1's 274 definitions are all equal;
    - one count increase: the compartments test's fail-closed check gains a case for D4's new
      operator-contract method, as designed. Its tier row was re-measured at 149 (e16e26bb).
  - The core-seams pass's owners branched from it (CORE_SEAMS §18).
  - **Evidence:** `/mnt/workspaces/Cells/d188-m2-move-20261118/gate-2d22a666/`.
- **D188's move 2 landed on main (18 November 2026).** Merge d5d56d1b (d188-m2-prep e0a3e6a3),
  tagged `d188-move2-landed-2026-11-18`. The tree before it is tagged `pre-d188-move2-2026-11-18`.
  The evidence is in `/mnt/workspaces/Cells/d188-m2-move-20261118/`: the gate is `gate-e0a3e6a3/`,
  and the first gate is `gate-f8a09e59/`.
  - **What moved.** `scripts/source_moves.py apply scripts/moves/move2.json` moved 117 modules into
    the target folders, with no hand edits in the move commit (dd8a56f2):
    - `laws/`, with seven groups: channels, junctions, mechanics, pumps, reactions, routes and
      transport;
    - `kinds/`, `operators/`, `definitions/`, `execution/`, `registry/` and `records/`.

    Two folders dissolved: `processes/` (D198) and `core/`. The BLAS pin's one home is now
    `cells/__init__.py` (R6′). No law, kind, operator or model ID changed. `models/`, `numerics/`,
    `analysis/`, `assays/`, `assembly/`, `assembly_pool/` and `ensemble/` stay where they are.
  - **No checkpoint crosses the move (D195).** `cells.records.source_layout.MOVES` declares the move.
    Both loaders and the continuity probe refuse an older checkpoint and name the tag. GARD's
    frozen @1 lineage reader also refuses cleanly, without naming it. The user accepted that
    exception on 18 November, and `docs/GARD_DESIGN.md` §5.1 names the tag.
  - **The first gate, at f8a09e59, failed. That is disclosed here.**
    - Tiers 1+2 changed six test files.
    - R1's 274 saved definitions: 8 were refused at parse.
    - The tier-3 continuity acceptance test failed 1 of 13.
    - **The causes:**
      - the move's dotted-name rule had rewritten five strings that are recorded data, not live
        module references: a tissue-preparation provenance entry, FR-4/5's execution-path text,
        and three MG0c `engine_models` lines;
      - four files built moved paths from separate parts, which the text rules could not see.
    - **The fixes,** each in its own follow-up commit:
      - the five strings restored to their pre-move bytes, and marked with a new per-line
        `source-moves: keep` marker (bd36c331, c75c288e), so a later application of the map
        leaves them alone;
      - the four paths fixed (53bd4566).
    - **All 191 string-literal hunks the move made** in `src/` and `validation/` were reviewed and
      decided, with 5 recorded and restored.
  - **The landing gate, at e0a3e6a3:**
    - tiers 1+2: 528 files, 0 changed against the record;
    - G1: 113 of 113;
    - crossrev: 9 of 9 identical, head against base and against the record;
    - the collected IDs: the same tests through the map, 28 renamed;
    - R1's 274 definitions: every fingerprint equal, with all 1857 control arrays bitwise;
    - the 33 red files keep every outcome and failure line;
    - FR's bitwise set passed;
    - the pin holds for every module, 556 of 556;
    - the D195 refusal rehearsal holds;
    - the tier-3 continuity acceptance test: 13 of 13;
    - GARD's @1 invariance: the freeze test, 3 passed; the 12 part-1 references with 0
      differences; @1's 4,216 probe files with 0 arrays differing, JSON equal but for provenance;
      G2's rows, 10 PASS. This was run through an adapted copy of the reference tool, which
      imported a pre-move name;
    - OL1's probe set at the moved head against probes-3e39bcc5: 0 arrays differing, and JSON equal
      but for provenance and the file-hash index;
    - R1's guard; the tool's selftests, 50 and 32; and `verify` of the move commit: 0 problems.
  - **A weaker earlier record.** R1's original fingerprint harness recorded each digest's type, not
    its value. Its "274 identical" for move 1, and for R1 itself, therefore compared less than it
    says. The adapter in the move's evidence compares the values.
  - **The carry-overs:**
    - **packed-gpu-planner** carries cleanly with the map extended by its two modules. Its owner
      has a note.
    - **core-fixes** carries with one semantic fix: main renamed `LAWS` to `VERSION_1_LAWS` (seam F
      step 1). It lands next, with its own gate.
  - **Not covered by any gate:**
    - the BETSE evidence verifiers, which compare saved module paths and hashes, so source identity
      cannot survive the move;
    - the frozen release verifiers;
    - `reports/*.json` closeouts;
    - `validation/geometry`'s source maps.

    The two tier-3 pin tests now fail first at `src/cells/__init__.py`, where the frozen tier-3
    record has `src/cells/core/er_spec.py`. R6′ caused that, not the move. After the move, 103 of
    181 and 90 of 152 of their pinned paths are missing. Tier 3 is re-frozen later.
  - **The visualizer:** main's fixture script imports the new homes. 36 `visualizer/` files name
    moved modules, and CellsViz takes the rename list when it merges main.
- **OL1 landed: the origin-of-life laws, `cells.assembly_lineages@2` (18 November 2026).**
  Merges 3e6410fe (ol1-laws 3e39bcc5) and b4522c77 (OL5's references, ool-references a9f40130),
  tagged `ol1-landed-2026-11-18`. This is the foundation of D212's programme. It is the event-pair
  contract over places (pool, membrane, lumen), with OL1's four laws:
  - `cells.stochastic_mass_action@1`;
  - `cells.transition_state_factor@1`;
  - `cells.ideal_mixing@1`;
  - `cells.regular_mixing@1`.

  It follows the lead's rulings in ORIGIN_OF_LIFE_ENGINE_DESIGN §0.2a and §0.2b.
  - **Verified against code-blind references.** OL5 wrote `validation/ool/references`, registered
    before any engine output; its five amendments all came before it too. The references passed
    6 of 6 rows on the probe set at 3e39bcc5, with inputs pinned at ab3dd700:
    - local detailed balance: Kolmogorov 2.8e-14 over 483 cycles;
    - the closed world's stationary law: total variation 1.0e-15;
    - catalysis kinetic only: total variation 1.7e-15, and the rate-doubled pair bitwise rescaled;
    - mass action: forward form 1.9e-14; 16 large-system z-tests at |z| ≤ 2.26 against 4.003; the
      SSA replay exact; moieties conserved; 10 refusals;
    - ledgers: closure 1.4e-12 over 2,000 events;
    - streams: a bitwise replay.

    Four planted errors applied to the engine's own records were all caught.
  - **The first harness run failed one row on a record rule.** The ladder's stream identities
    repeated across rungs, though the row's physics parts passed. The references were not amended.
    Instead the driver was fixed, with a planted test (efb3c739), and the probe set regenerated.
    Both verdicts are kept.
  - **Rulings first.** Two of OL5's readings were ruled on the physics (bbcbec69) before the
    builder was asked what its kernel did:
    - `last_molecule: kept` zeroes only a step that changes the membrane's count. The kernel had
      zeroed every channel with an empty end state, freezing pool steps at such probe states. It
      was fixed in 622d87d4, with a planted test.
    - Rule 8's singular step is one and the same membrane species on both sides. It matched.
  - **The gates:**
    - lane A at 7688e9f4, whose src/ is identical to 3e39bcc5's: crossrev identical, G1 113 of 113,
      tiers 1+2 over 519 files with 0 changed, and IDs only OL1's new ones;
    - GARD's @1 invariance: the freeze test, the 12 part-1 references, @1's 4,216 probe files with
      arrays bitwise, and G2 10 of 10;
    - FR's bitwise landing set;
    - at the merged head b4522c77: OL1's and OL5's test files, 132 passed; test IDs 18,192 → 18,318,
      none missing, the 126 new ones all in their files.
  - **Scope:** the stochastic family with general stoichiometry over places, regular mixing,
    catalysis on the common state and exact ledgers. Geometry, an osmotic lumen and division come in
    OL2 and OL3. Nothing is judged under a registered protocol, and nothing is compared with
    experiment.
  - **Evidence:**
    - `/mnt/workspaces/Cells/ol1-laws-20261117/README.md`;
    - the verdicts in `/mnt/workspaces/Cells/ool-references-harness-20261118/` (`result/` and
      `result-3e39bcc5/`);
    - the merged-head check in `/mnt/workspaces/Cells/ol1-landing-20261118/`.
- **FR-6's A5″ judged: passed (18 November 2026, 03:39–03:47 UTC).** The registered protocol
  `fr6-a5pp-v1` was judged once from the clean snapshot of its registration commit 555d8771, on
  lane B (CPUs 8-11 and 24-27, under its lock). It takes FR-6's items 1 and 3 together: two cells'
  gate-free K-leak populations driven through `species_regulated_availability@1`'s regulatory
  state (`hill_regulated_two_state@1`) from a per-cell prior, s₀ = 0.1 and 0.8, under the same
  regulator dose. Its references are the code-blind FR references agent's
  (`validation/fr6/references`).
  - **18 of 18 judged criteria.** Examples:
    - V and the amounts against R-cell on 1, 0.5, 0.25 and 0.125 ms at order 2.03, 2.01 and 2.01,
      every pair resolved (3 of 3, at least 2 required); the errors fall from 6.1e-7 to 9.2e-9 V
      and from 2.0e-8 to 3.0e-10 fmol. Row 0 is the references' start within 1.2e-16 relative.
    - Each control at least 10 x the honest engine's error at the same rung, where it has power:
      the prior swapped, shared (a's, b's or their mean) or ignored at 4.7e3 x and more, the state
      bypassed at 8.9e3 x, the state's rates 1% off at 39 x (k_on) and 41 x (k_off).
    - The basal level x (1 + 1e-3), the references' control: 26 x in the amounts at 1 ms, and 27 x
      and 109 x in V at 0.25 and 0.125 ms. At the coupling rule's delta, 1e-4 (registered from the
      development run, 9.25e-5 rounded up): detected by the band, and 10.8 x in V at 0.125 ms.
  - **Reported, not judged:** V and the amounts use 0.59 to 0.65 of the dt² state budget derived
    from the references' stand-in; s and a_eff converge at order 2.00, every pair resolved.
  - **No harness failure:** all 15 parts are complete. Peak memory was 1.0 G of 3 G, and no part
    used more than 10.9% of its runtime limit.
  - **Against the rehearsal** (`pipeline/run-reh-6ecd4d9b`, on a registered dry-run copy on lane
    B): all 15 parts are bitwise equal, and so is the judged derivation.
  - **Scope:** `species_regulated_availability@1` with `hill_regulated_two_state@1` and D150's
    turnover as built at 555d8771: two pump-free 2 pL cells over 2 s, synthetic values, CPU only.
    Zero power: a state reading the other cell's regulator (both cells get the same dose) and the
    references' basal control in V at 1 and 0.5 ms. Not covered: gated channels (A5′), the
    routing door, leak and pump targets, any biological comparison.
  - **Evidence:** `/mnt/workspaces/Cells/fr6-a5pp-20261118/judged/run-555d8771/`
    (`verdict/verdict.json`, `reading.json`, `compare/`, `run.log`).
- **FR-3 judged: passed (18 November 2026, 03:20–03:32 UTC).** The registered protocol
  `fr3-site-occupancy-v1` was judged once from the clean snapshot of its registration commit
  1b838d75, on lane A (CPUs 0-3 and 16-19, under its lock). It is `site_occupancy@1`'s first
  judged acceptance, and its references are the code-blind FR references agent's
  (`validation/fr3/references`).
  - **51 of 51 judged criteria.** Examples:
    - Q1 to Q5 against R-ode at every record: the amounts within at most 0.10 of B_state (Q4's
      high-occupancy worlds; elsewhere at most 1.2e-4), the heat and the work within at most
      1.9e-3 of B_energy.
    - q1_fast's third order on 1, 0.5 and 0.25 ms: 3.04 and 3.02 in the cell's and the ECS's
      amounts and the bound sites, in the band [2.8, 3.2].
    - Q2's equilibrium, depletion quadratic and heat to equilibrium at 5.2e-5, 6.8e-8 and 1.0e-9
      of their tolerances; the Riccati form, wherever the references give it, at 0.10 of B_state.
    - Q4: B(alpha)/B(1) - alpha within 4.1e-5 of M_Q4 = 1e-3; the kinetic factor (K) departs by
      494 M_Q4 and the affinity factor (A) at 100 K_d by 490 M_Q4.
    - Q5: the closure, the guard of record, at most 0.11 of its rounding bound, the ledgers 0.09
      and the ligand's system total 0.33, with no heat violation; the background guard 11 x below
      B_state. The five plants are caught on exactly their rows, at 3.1e5 x (work) to 5.3e11 x
      (site free energy), and the engine refuses both material plants on its own.
    - The controls at 66 x (k_int) to 4.7e4 x (alpha ignored) their arms' budgets.
    - Q6: the restarts bitwise and K4's moved switch caught; the batch within 8.2e-15 of its scalar
      runs and bitwise reversed; idle, the twins, the signature and all 35 refusal classes.
  - **Reported, not judged:** the heat's and the work's orders on q1_fast, 1.97 and 1.99; the
    references' order in eps, 0.97 and 1.00; the affinity factor at 0.01 K_d, 2.5 and 1.9 M_Q4
    (zero power, the lead's ruling 5); the batch against its scalar runs, not bitwise. The
    engine's own energy check refuses the heat-sign and site-free-energy plants but not the work
    plant, which only the judge's closure catches (FR-18).
  - **No harness failure:** all 43 parts are complete. Peak memory was 1.2 G of 3 G, and no part
    used more than 12.9% of its runtime limit.
  - **Against the merged rehearsal** (`pipeline/run-reh-8b6d1279`, on a registered dry-run copy on
    lane A): all 43 parts are bitwise equal, and so is the judged derivation.
  - **Scope:** `site_occupancy@1` as built at 1b838d75, version 1's face-free first acceptance (one
    neutral, impermeant ligand; patch populations outward and inward; site-conserving
    internalisation; a static alpha; ARS(2,2,2) at 1 ms). Not shown: contact populations in a run,
    composition with D150's or D152's operators, faces, RK4, site occupancy beside a bath schedule
    (refused), the per-law R-dG test and the references' zero-power cases.
  - **Evidence:** `/mnt/workspaces/Cells/site-occupancy-fr3-20261118/judged/run-1b838d75/`
    (`verdict/verdict.json`, `reading.json`, `compare/`, `run.log`).
- **FR-1 judged: passed (18 November 2026, 00:57–01:08 UTC).** The registered protocol
  `fr1-closed-compartment-v1` was judged once from the clean snapshot of its registration commit
  05a8d193, on lane A (CPUs 0-3, under its lock). It is exchange's first judged acceptance, and
  its references are the code-blind FR references agent's (`validation/fr1/references`).
  - **44 of 44 judged criteria.** Examples:
    - C3 and C5 at rounding of their closed forms (at most 1.5e-2 and 7.9e-7 of the rounding
      budget). C4, C6, C7 and C8 against their references at most 3.5e-3 of B_split, at second
      order.
    - C4's engine equals the palindrome's step map at rounding at every rung, and the splitting
      term x*/x_eq - 1 is within 5.3e-6 of -a(a + 2b) dt^2/96.
    - C9 is silent and live in all six programs (S1 bitwise, S2 at 9.3e-6).
    - C10's work equals the free-energy change at rounding, and C6's energy matches R-energy with
      sum dn != 0. C11's from-trace rows are within 7.4e-10 of their bound.
    - C12: the restarts and the batch are bitwise. C13's plants are caught on exactly their rows,
      at 9.0e6 x (move) and 21 x (work); K3 at 4.3e4 x and 3.3e7 x. K1 is 667 x B_split, K2 903 x.
  - **No harness failure:** all 38 parts are complete. Peak memory was 1.3 G of 3 G, and no part
    used more than 6.1% of its runtime limit.
  - **Against the rehearsal** (`pipeline/run-5f6e857c`, on a registered dry-run copy on the timed
    lane): all 38 parts are bitwise equal, across D214's two boundary fixes (in the judged snapshot,
    not the rehearsal's).
  - **Scope:** `cell_owned_compartments@1` with exchange@1, turnover@1 and local_species_reactions@1
    as built at 05a8d193: the neutral first version, ARS at 1 ms and RK4 at 0.1 ms. V_b's
    orientation is not shown, and a dropped -1 in G has power only in C6.
  - **Evidence:** `/mnt/workspaces/Cells/closed-compartment-fr1-20261117/judged/run-05a8d193/`
    (`verdict/verdict.json`, `reading.json`, `compare/`, `run.log`).

- **Move 2's prerequisites on main (18 November 2026, early).** Merged from `d188-m2-prep` at
  013c4c07. The move itself waits for OL1's landing.
  - **D195 item 4:**
    - `io.load_snapshot`, `batch_io.load_batch_snapshot` and the continuity probe refuse a
      checkpoint whose recorded source map is from before a declared move, and name the tag where
      it restores (`cells.source_layout`).
    - GARD's frozen @1 lineage reader refuses any changed source without the tag (D195 amended).
  - **R6′:** the BLAS one-thread pin has one home, `cells/__init__.py`. Measured: 530 of 530
    modules pinned, and the planted control unpins all 47 sampled.
  - **The planner's classifier:** a family is active when the model table has its row. GARD's @1
    and OL1's @2 now classify active, where before GARD would have been drafted into `legacy/`.
  - **Also:** the four tool fixes, and layout-independent strings and tests for the move.
  - **The gate at 013c4c07:**
    - tiers 1+2, 508 files, 0 changed;
    - G1 113 of 113;
    - crossrev nine of nine, kinds included, against the band-renewed record;
    - collected IDs, the 19 added;
    - R1's guard, the selftests (42 and 32 checks) and FR's bitwise set, all passed;
    - FR-10's and FR-1's restart parts load current-layout checkpoints.
  - **For the next tier-3 diff:** two tier-3 pin tests that already fail now fail first at
    `src/cells/__init__.py` instead of `core/__init__.py`. That is a changed error, not a new
    failure.
  - Evidence: `/mnt/workspaces/Cells/d188-m2-prep-20261117/evidence/`.

- **BETSE's calcium references run out of process (18 November 2026, early).** This fixes the
  compliance finding from D211's inventory. Merged from `betse-reference-out-of-process` at
  a2a32ac3.
  - **The change:**
    - `validation/betse/calcium_functions_native.py` runs pumpCaER, pumpCaATP,
      EndoRetic.channels and Cav1p2 unmodified in venv-betse, as a child process;
    - the tests refuse a capture whose BETSE sources differ from their pins;
    - the three in-process exec helpers are deleted, and `qualify_cell.py` no longer copies BETSE
      files.
  - **Tests:** the four calcium tests keep their names and every original check. Each kernel is
    also held to an independent form of its law: the Decimal ER pump, the PMCA term, Cav1.2's
    kinetics and the ER release factor.
  - **Before and after:** the nine affected tier-3 files have the same 320 test IDs and the same
    outcomes. Tiers 1+2 show 0 of 513 files changed.
  - **On a trial merge with main:** all nine files pass, run one process per file. A first run of
    all nine in one process was killed at its 6 GB cap; no test failed.
  - Evidence: `/mnt/workspaces/Cells/betse-reference-20261117/` (`before/`, `after/`,
    `gate-a2a32ac3/`, `merged-check2/`).

- **FR-19's band follow-up on main (18 November 2026, early).** Merged from `passive-share-band` at
  7bfe0c68.
  - **The fix:** the passive routes' heat-share floor now bounds the rounding by
    (|μ̄_in| + |μ̄_out| + 2)·|m|. FR-19's |μ̄_in·m| + |μ̄_out·m| left a band near 1 mM.
    `test_passive_share_floor.py` now has 11 tests.
  - **The gate at cde5efd1:** crossrev, eight sets identical. The kinds set differs, by design,
    only in the three FR checked steps' floor terms (constants 12/12, bindings 3/3). G1 113 of 113;
    tiers 1+2 502 files, 0 changed; IDs, only the band's renamed tests; FR's bitwise set passed.
  - **The record's kinds texts** are renewed on main after this landing, as for FR-19. The
    superseded texts are kept, and crossrev's nine sets are rerun against the renewed record.
  - Evidence: `/mnt/workspaces/Cells/passive-share-band-20261117/gate-cde5efd1/` and
    `fr-landing-cde5efd1/verdict.json`.

- **D214's two core boundary fixes on main (18 November 2026, early).** Merged from
  `core-boundary-checks` at 13aaf72a.
  - **Fix 1a:** kinds write only their own resolved, declared fields: initial values, derivatives
    and control outputs, at the pump family's three merge points. `test_kind_foreign_writes.py` has
    19 tests.
  - **Fix 1b:** the vector windows' failure mask refuses, at admission, more checks than its dtype
    and shift hold. `test_vector_failure_mask.py` has 34 tests.
  - **The gate at 1aca2314:** crossrev 9 of 9 identical against the renewed record (the placement
    proof), G1 113 of 113, tiers 1+2 with 0 of 495 changed, collected IDs with 53 new and none
    missing, and FR's bitwise set passed.
  - **The targeted check at 13aaf72a,** for FR-10's pump-family worlds landed after that gate: FR-10's
    seven test files, the bath-schedule files, the door-S view and the continuity bypass, 0 changed.
    IDs show additions only.
  - Evidence: `/mnt/workspaces/Cells/core-boundary-checks-20261117/` (`gate-1aca2314/`,
    `fr-landing-1aca2314/`, `targeted-13aaf72a/`).

- **FR-10 judged: passed (17 November 2026, 23:45–23:50 UTC).** The registered protocol
  `fr10-dose-schedule-v1` was judged once from the clean snapshot of its registration commit
  407ba164, on lane A (CPUs 0-3, under its lock). Its references are the code-blind FR references
  agent's R-faces, R-ion and R-records (`validation/fr10/references`).
  - **31 of 31 judged criteria.** Examples:
    - W1 against R-faces is at most 0.92% of B1, and W2 against R-ion 0.80% of B2; row 0 is exact.
    - The orders are 2.003 to 2.011, and the energy residual over the flows is 5.8e-5 and 1.7e-5,
      falling at order 2.
    - The dose equals R-records' exactly at every event, and dG_b is within 4.5e-16 relative.
    - The operator's reconciliation term K equals R-records' K to 1.4e-10 of the reservoir-work
      bound. The compensation charge is 0.
    - Controls: K1 is 973 x B1 and K2 is 1000 x B2. Without the operator's term, the reservoir-work
      ledger is 2.1e4 x its bound after the event.
    - Restart, batch, idleness and all 13 refusal classes hold.
  - **No harness failure** (the harness-limit rule): all 19 parts are complete. Peak memory was
    0.92 G of 2 G, and no part used more than 6.9% of its runtime limit.
  - **Against the rehearsal** (`r2/run-ed2b8ee0`, on a registered dry-run copy): 18 parts are
    bitwise equal. The references part differs only in the path and sha256 of the W3 records it
    reads, which was expected and listed before launch.
  - **Disclosure, the launcher:** before the run, the launcher's dry-run check refused the protocol
    of record. That check is the run folder's `judge-run.sh`, run tooling outside the repo. It
    matched the phrase "a registered dry-run copy" in the lead's registration status. It was
    narrowed to the dry-run copy's own status prefix, "registered for the rehearsal only". Separately
    checked: the snapshot's protocol is the one of record, with its matching registration record.
    The judge and the engine were not touched.
  - **Scope:** `scheduled_bath_composition@1` as built at 407ba164. It covers neutral formula units
    only, held baths only, and steps only inside the measured region. It is judged under ARS at 1 ms
    and RK4 at 0.1 ms. The step rule bounds the face rate but not the membrane rate; the rehearsal
    found that the run-time energy guard holds there (R12's neighbour, disclosed).
  - **Evidence:** `/mnt/workspaces/Cells/bath-schedule-20261114-01/fr10-protocol/judged/run-407ba164/`
    (`verdict/verdict.json`, `reading.json`, `compare/`, `run.log`).

- **The gap-junction tissue line, dense records, and the sheet (17 November 2026, night).**
  Development, not judged (D138). Note §7.6, registered before these runs, merged from
  `gap-junction-replication` at 0471f7c3.
  - **Dense records** (`runs/dense-01`, D = 0, x2/2, x2 and 2·x2): about 370 log-spaced records per
    arm, the first one step in. Every end state is bitwise its earlier run (picks-02 and picks-01),
    so the records changed nothing. Each package carries the tumour cells, a species map, each
    arm's place against x2, and the cells' miR200, Zeb mRNA and ZEB protein in µM.
  - **The 9×9 sheet** (`runs/sheet-01`): an extension beyond the replication, not part of it.
    - Its setup: 4-neighbour junctions, a 3×3 tumour patch in the middle, the same seeds and
      protocol, and a coupled horizon of 2,000 s (a tenth of the line's).
    - The tumour holds at D = 0, x2/16 and x2/8, and the sheet normalises at x2/4, x2/2 and x2.
      No arm is still changing at 2,000 s.
    - So, at 2,000 s, the sheet's threshold lies between x2/8 and x2/4 (0.9–1.8e-15 m²/s), 4 to 8
      times below the line's. That is observed; why is not measured.
  - **The coupling ladder** (`runs/ladder-01`, ten line arms to 20,000 s, none refused):
    - below x2, the tumour holds (0.70 x2) or converts only partly (0.87 and 0.98 x2);
    - above x2, every arm normalises, sooner as coupling grows: first all-E record at 6,800 s at
      1.05 x2, down to 311 s at 6.97 x2. The times are as fine as the record spacing.
  - **The light gate:** tier 1 at 0471f7c3, 336 files, 0 changed. The ladder's commit b40b9169 is
    docs only.
  - Evidence: `/mnt/workspaces/Cells/gap-junction-20261117/runs/dense-01/`, `runs/sheet-01/` and
    `runs/ladder-01/`.

- **The gap-junction tissue threshold, rerun after FR-19's fix (17 November 2026, night).**
  Development, not judged (D138). Note §7.5, merged from `gap-junction-replication` at 15ba9bea.
  - **The search** (`runs/neither-02`, clean snapshot of main 1f4c740a): 37 points, none refused,
    monotone; the half-step rerun at dt 1/16 s gives the same outcomes on both sides.
  - **Its threshold:** x2 = 7.1777e-15 m²/s, bracket ratio 1.0002. That is 0.99968 of the value
    logged by BITSEY's saved run (7.18e-15, written by an earlier revision of its code), inside the
    0.95–1.05 band fixed before the run, so agreement is called.
  - **Against that log, point by point:** normalised-or-not agrees at all 16 shared points. The
    end-state lines are identical at 15 of 16; the 16th differs by one printed digit.
  - **FR-19's effect:** the first search had 5 of its first 8 points refused; this one had none.
  - **The tissue line's three arms** (`runs/picks-02`): at x2/2 the tumour holds (6 M, 19 E); at x2
    and 2·x2 the tissue normalises (25 E). They replace `picks-01` in the viewer.
  - Evidence: `/mnt/workspaces/Cells/gap-junction-20261117/runs/neither-02/` and `runs/picks-02/`.

- **D198's retire batch on main (17 November 2026, evening).** The merge of `retire-processes` at
  292aa967.
  - **Retired:**
    - 33 unreached source modules: the held charged-surface work law and its backend, conservative
      polygon geometry, fixed-polygon removal, stable mesh reconstruction, stable-seed control volumes,
      explicit finite-ECM partitions and their dynamics, and the rectangular environment kernels;
    - 64 validation modules;
    - 951 test IDs.

    Four BETSE-convention kernels moved to `validation/betse/`.
  - **Recovery:** tag pre-d198-retire-2026-11-17 holds every removed path.
  - **The two laws** (charged-surface work, and conduction J = σE) are to be rebuilt under D206 and
    D211. Their reference outputs are saved in `/mnt/workspaces/Cells/d198-retire-20261117/references/`.
  - **The gate on 292aa967:**
    - tiers 1+2, 490 files, 0 changed;
    - G1, 113 of 113;
    - collected IDs, main minus exactly 951;
    - FR's bitwise landing set, passed;
    - crossrev identical except the kinds set's three FR-19 texts, which are byte-identical to the
      superseded record.
  - **Evidence:** `/mnt/workspaces/Cells/d198-retire-20261117/gate-292aa967/`.

- **FR-19 fixed on main (17 November 2026, evening).** The merge of `passive-share-tolerance` at
  3d8e7b3b.
  - **The fix:** `passive_neutral_permeation@1`'s heat-share sign rule now has the raw-sum check's
    rounding floor. Shares within it are booked as computed. Every previously admitted step is bitwise
    unchanged.
  - **The gates:**
    - G1, 113 of 113;
    - tiers 1+2, 514 files, 0 changed;
    - FR's bitwise landing set, passed;
    - crossrev identical except the kinds set's three checked steps, which differ in the predicate
      only, by design. That record is to be renewed.
  - **D148:** the law keeps its ID.
  - **What it unblocks:** the gap-junction replication's previously refused tissue points complete,
    so the threshold search can be rerun from main.
  - **Evidence:** `/mnt/workspaces/Cells/passive-share-tolerance-20261117/`.

- **The gap-junction replication's first stage, on main (17 November 2026, evening; D207).** The merge
  of gap-junction-replication at cc759bed. Development work, not judged.
  - **What it replicates:** the model of J. Grodstein, J. Mathews and M. Levin, "Membrane voltage and
    connexin expression work together to enhance tumor growth and metastasis in cancer", bioRxiv,
    doi:10.64898/2026.09.02.748840 (made with BITSEY).
  - **On main:** the driver `validation/gap_junction_tissue/` and the note
    `docs/GAP_JUNCTION_CANCER_REPLICATION.md`.
  - **The linear model runs as written** (`local_species_reactions@1` with
    `passive_neutral_permeation@1` on junction routes), unqualified.
    - Against dense solves, the worst error is 1.0e-5 at dt and 2.5e-6 at dt/2: second order.
    - Its exact Norton-equivalent network, on @3's own routes, agrees to about 1e-14 and is its check.
  - **Figure 8:** the preprint's printed recursion departs from direct circuit analysis in two places.
    The engine's solve agrees with direct analysis, whose limit is 1.618 at equal conductances. An
    independent derivation checks this (`/mnt/workspaces/Cells/gap-junction-derivation-20261117/`).
  - **The tissue Tables 1–3 are not replicated;** they need FR-15 to FR-17.
    - A threshold search on the 1D line, against BITSEY's logged threshold, was stopped by an engine
      check (FR-19).
    - At the two coupling values that ran through, Cells' 25-cell end state equals BITSEY's saved log
      character for character. That is descriptive, not judged
      (`/mnt/workspaces/Cells/gap-junction-20261117/probes/neither-compare-01/`).
  - **Viewer packages** (dev-06, from 6729160b, on main through this merge):
    `/mnt/workspaces/Cells/gap-junction-20261117/runs/dev-06/viewer/`. There are 30 packages, and its
    `summary.json` holds 7 sweeps.
  - **Gate:** tiers 1+2 on cc759bed, 505 files, 0 changed. Evidence:
    `/mnt/workspaces/Cells/gap-junction-20261117/`.

- **FR-4 and FR-5 judged: both passed (17 November 2026, 16:12–18:34 UTC).** The registered protocols
  `fr4-acidification-v1` and `fr5-transfer-v1` were judged once from the clean snapshot of their
  registration commit 32a1d439, on lane B. Tags: fr4-v1-qualified-2026-11-17 and
  fr5-v1-qualified-2026-11-17.
  - **FR-4:** 21 of 21 judged criteria. Examples:
    - pH to 1.31e-12;
    - material 1.89e-6, charge 3.05e-5, energy 1.90e-8;
    - K2 caught at 3.276;
    - K3 refused at the definition with reason "envelope", as designed.
  - **FR-5:** 51 of 51. Examples:
    - arm T: X_L 2.77e-7 of its budget;
    - arm R: cargo 0.147 of its allowance, its one visible margin;
    - controls: 313.7 and 872 budgets.
  - **No harness failure** (D195's harness-limit rule): all 20 results are complete, peak memory was
    1.3–1.4G of 2G, and no unit used more than 29% of its runtime limit.
  - **Against the rehearsal, the full-horizon check across seam F:** identical verdicts and values.
    FR-4's 8 parts are bitwise equal. FR-5's 12 parts differ only in the start extract's identity, which
    was expected and listed before launch.
  - **Scope:** `cell_owned_compartments@1` as built at 32a1d439 (refusal 4 v1.2, refusal 5 v1.1).
  - **Evidence:** `/mnt/workspaces/Cells/d172-restructure-20261115-01/fr45/judged-20261117/run-32a1d439/`
    (`fr4/verdict/verdict.json`, `fr5/verdict/verdict.json`, `reading.json`, `fr4/compare/` and
    `fr5/compare/`).

- **GARD's G1, part 2, on main (17 November 2026, evening).** The merge of gard-g1-merge at 23f82dd7.
  - **What's on main:** `cells.assembly_lineages@1`'s three laws and two lineage operators, registered
    under `cells.exchange_law@1`, `cells.rate_factor_law@1` and `cells.lineage_operator@1`, and frozen.
    `cells.declarations@2` lists all five at main's head:
    - the laws `cells.reservoir_exchange@1`, `cells.gard_catalysis_single_event@1` and
      `cells.gard_catalysis_pair_consistent@1`;
    - the operators `cells.size_threshold_fission@1` and `cells.daughter_continuation@1`.

    Every bundle writes `cells.relations@1` tables.
  - **The gate on 23f82dd7:** tiers 1+2, 512 files, 0 changed; G1 113 of 113; crossrev's nine sets
    identical.
  - **The final probe set:** `/mnt/workspaces/Cells/gard-g1-part2-20261117/probes-c6dd5956/probes/`.
    Its roles.json is FINAL, with the standing "development run of the engine, not judged".
  - **The independent references (G2)** pass all ten rows on that set, with nothing tuned (report-5).
    They are on main since merge b3677b72, of gard-g2-references at 7bf68c24 (tiers 1+2, 515 files,
    0 changed).
  - **Standing (D192, D197):** these are development runs, not judged.
    - The single-event form is the preprint's, kept for comparison and declared driven.
    - The pair-consistent form is passive, and the default.

- **Combined landing (17 November 2026, evening).** main is at 3891b802, a fast-forward of the gated
  landing branch. It brings the relations writer, seam F's registry fixes, the documentation library
  with `cells.declarations@2`, and the removal of `agent-work/`.
  - **What landed:**
    - **`cells.relations@1`** (D200, D202): the general relationship tables, with a second consumer
      over four real worlds and an engine-free drawing script.
    - **Seam F's registry fixes:** the static model table and family operators.
    - **The library (D203):** the format page, the page tool, the drift test, the template, the
      glossary and three pilot pages.
    - **`agent-work/` is out of the repository.** It is in history at tag
      native-betse-frozen-2026-11-08.
  - **The gate** ran on snapshot-3891b802, which is clean:
    - crossrev's nine sets are identical;
    - G1 is 113 of 113;
    - tiers 1+2: 504 files, 0 changed;
    - test IDs: 39 new, all in the five expected files, with none missing and the same 5 collection
      errors as before.
  - **FR's bitwise landing checks** show no unexpected difference.
  - **Evidence:** `/mnt/workspaces/Cells/landing-20261117/` (`gate-3891b802/`, `fr-landing-3891b802/`).
  - **Also on main:** the molecular machines design with M1's build plan (D209). D198's retire batch is
    held (D206).

- **FR-4's and FR-5's protocols registered (17 November 2026, late afternoon), before any judged
  run.** Registration commit 32a1d439. The protocols are `fr4-acidification-v1` and
  `fr5-transfer-v1`.
  - **The basis:**
    - D195;
    - the rehearsal, which passed 21 of 21 and 51 of 51;
    - three dated pre-registration disclosures: the energy line settled while the study's values
      were known, the text levelled, and the harness-limit rule.
  - **The judged criteria and derivations are byte-identical to the rehearsed copies.**
  - **The harness-limit rule:** a part ended by its runtime limit or memory cap voids the run, which
    is relaunched once from the same snapshot. An engine refusal is a verdict.
  - **The registered state is tested.** The drafter refuses to redraft a registered protocol, and
    the lane's 45 tests pass in both states. The first attempt found and fixed this check.
  - **Next:** the judged run, from a clean snapshot of 32a1d439. It runs on lane B (CPUs 8–11) for
    about 3 h 10 min, and every judged part is compared against the rehearsal.

- **FR-4's and FR-5's rehearsals pass, on registered dry-run copies (17 November 2026,
  11:20–14:31 UTC).** They ran from snapshot-e79b4232 on CPUs 6, 7, 22 and 23
  ([evidence](/mnt/workspaces/Cells/d172-restructure-20261115-01/fr45/rehearsal-20261117/run-e79b4232/)). The protocols themselves stay proposed.
  - **FR-4 (`fr4-acidification-v1`):** 21 of 21 judged criteria pass. All 8 parts are bitwise
    equal to its dt study's.
  - **FR-5 (`fr5-transfer-v1`):** 51 of 51 judged criteria pass. Its 12 parts differ from the dt
    study's only in the start's extract identity, which was recorded before the launch as
    expected. The smallest margin is arm R's cargo ledger, at 0.147 of its allowance.
  - **The energy criterion,** settled before the rehearsal: the residual is at most 2e-3 at both
    1 ms and 0.5 ms, and must fall at second order. A dated disclosure records that the study's
    values were already known.
  - **Across seam F:** every check is bitwise, including a short run through the injury window.
    G1's 113 worlds hold no FR world, and crossrev holds FR-5 only in reduced form, so these checks
    are the evidence for FR-4's and FR-5's full worlds.
  - **The buffered-node predictor** (core-seams step 0 §8): FR-5's arms sit 21–42 times below it.
    FR-4's control K2 sits 1.8 times below it, at 1 ms.
  - **Next:** the protocol text is redrafted with no criterion changed, the lead registers both, and
    the judged runs follow from a fresh snapshot taken after seam F.

- **GARD's G2, the independent component references, merged into main (17 November 2026).**
  `validation/gard/references/`, from gard-g2-references 193eaf0d. Its writer never read the engine's
  code.
  - **Ten references,** each derived from the preprint (Appendix F) and the three original papers,
    each with a planted control it catches. Among them:
    - the closed form at β = 0;
    - time rescaling under uniform β;
    - local detailed balance;
    - the closed world's stationary law, which independently reproduces the design note's
      0.5793 and 0.15;
    - an exact SSA oracle;
    - the fission partition;
    - conservation;
    - the ledger;
    - streams;
    - the observers, including F12 over all 4,096 sequences.
  - **A harness** reads run bundles through one adapter function.
  - **Tests:** six files, 112 tests, all tier 1, measured on the timed lane.
  - **Not done yet:** the harness has not read a real engine bundle. Its reader adapts to G1's
    frozen format once part 2 produces the probe bundles.

- **GARD's G1, part 1, merged into main (17 November 2026, afternoon).** Branch gard-g1-merge
  96643762 ([evidence](/mnt/workspaces/Cells/gard-g1-20261117/), README inside).
  - **What it adds:** `cells.assembly_lineages@1`, a general stochastic assembly family (D197). It
    has:
    - the exact direct-method kernel with keyed streams, vmapped over lanes;
    - reservoir exchange;
    - size-threshold fission and daughter continuation;
    - a stochastic ledger that refuses a passive run whose books don't close;
    - self-describing run bundles, with a declared channel table and units.
  - **GARD itself is one comparison law set on it** (D192):
    - the preprint's single-event form, declared driven;
    - the pair-consistent form, passive and the default.

    The kernel's detailed-balance check admits only the second as passive.
  - **The gate:**
    - tiers 1+2: 489 files, none changed;
    - the results gate: 113 of 113 identical;
    - crossrev: all nine sets identical;
    - 8 new test files, 67 tests, each catching a planted error.
  - **Development run:** one lineage of 100 fissions on one CPU.
    - The pair-consistent ledger closes to within 2.9e-11 k_BT.
    - The single-event form reports 55.6 k_BT of cycle work with no source, as declared, about
      0.55 k_BT per fission.
    - Speed: 2.2×10⁴ events per second per lane, and up to 5.8×10⁴ with 16 lanes on one CPU.
  - **Next:** part 2 (keys, end reasons, the probe driver, checkpoints, branching, every descendant)
    and the general relationship tables (D202).

- **Seam F of the core-seams pass merged into main (17 November 2026, afternoon).** Branch
  core-seams-f 10a6bb19 ([evidence](/mnt/workspaces/Cells/core-seams-f-20261117/)).
  - **What it adds, all structure:**
    - **The law template:** `ChannelLaw`, `CycleLaw` (the same type as `PumpLaw`), `RouteLaw`,
      `BindingLaw` and `JunctionLaw`. Each carries its `host`, its provenance and a `Citation`,
      with units and signs declared. @3's ten laws now use it.
    - **A build-scoped law registry,** in which kinds find their laws by interface and host.
    - **Operators as a registry section.** `OPERATORS` is a view of the active section.
    - **`cells.modules`,** marked PROVISIONAL (D195).
    - **D185's declarations manifest,** FR-12: `python -m cells declarations --out FILE` writes
      `cells.declarations@1`. It covers 14 laws, 5 kinds and 19 operators, with legacy model IDs
      flagged.
  - **The gate:**
    - crossrev identical;
    - G1 113 of 113;
    - tiers 1+2: 485 files, none changed;
    - 16 planted errors caught.
  - **Still to come in F:** the per-law extractions and the built-ins' import guard, after move 2
    and the retire batch.

- **D188's move 1 landed on main (17 November 2026).** Merge 7bb8bf23, tagged
  `d188-move1-landed-2026-11-17`; the tree before it is tagged `pre-d188-move1-2026-11-17`
  ([evidence](/mnt/workspaces/Cells/d188-m1-20261117/gate-9b20034a/summary.txt)).
  - **What moved:** the 334 older-family modules went into `src/cells/legacy/`, done by
    `scripts/source_moves.py apply` with no hand edits.
    - The map is `scripts/moves/move1.json`, with its path table beside it.
    - It came after R5: the detached assembly worker now takes its root from the package.
  - **What didn't change:** no law, kind, operator or model ID; the test file paths; and the active
    modules, which wait for move 2.
  - **Verify:** 334 moved, 649 files rewritten, 0 problems, and a second apply is a no-op.
  - **The gates:**
    - collected IDs the same through the map (18,504);
    - crossrev identical;
    - G1 113 of 113, bitwise;
    - tiers 1+2: 481 files, none changed, with the 38 red files keeping every outcome;
    - a continuity resume across the move, admitted and bitwise;
    - R1's guard passes, and nothing outside `legacy/` imports it.
  - **Commands and docs:** the older CLIs run as `-m cells.legacy.*`. Code links in the docs follow
    the new paths.

- **D188's R2–R4 merged into main (17 November 2026), with the moves' tools.** Branch d188-r2r4
  8c41d7ec ([evidence](/mnt/workspaces/Cells/d188-r2r4-20261117/)).
  - **What changed:**
    - **R4:** one pinned law's root is taken from the package.
    - **R2:** 17 computed module paths name full modules.
    - **R3:** the extractions, moved verbatim into four new core modules.
    - **Also:** the AST-hash test reads through the committed maps; `output_bound` goes through a
      legacy hook; the planner gains its keep rule, reverse closure and package rule.
  - **The gate:**
    - collected IDs identical;
    - crossrev identical;
    - G1 113 of 113;
    - tiers 1+2: 480 files, none changed;
    - no pinned file changed.
  - **The re-run dry run of move 1:** 334 modules, verified with 0 problems.
    - The IDs are the same through the map.
    - The 18 tests that were red under the first dry run now pass.
    - crossrev is identical, and tiers 1+2 show none changed.
  - **Before move 1:** R5, the detached assembly worker's root (found by this lane; no green test
    saw it).

- **D188's R1 merged into main (17 November 2026): the legacy registration entry point.** Branch
  d188-r1 4a042ea2 ([evidence](/mnt/workspaces/Cells/d188-r1-20261117/)).
  - **What changed:**
    - The legacy halves of the six dispatch points moved verbatim into
      `cells/legacy/registration.py`: get_model, parse_spec with `_fine_dict`, control_values, the
      CLI and the ensemble.
    - Each core chain tries the active families first, then loads that module through one
      constant.
    - A guard test, with a planted control, keeps everything outside `legacy/` from importing it
      any other way.
  - **The gate:**
    - the collected IDs are main's plus the guard's 19;
    - crossrev's nine sets are identical;
    - G1 is 113 of 113 bitwise;
    - tiers 1+2: 480 files, none changed;
    - the 38 red files keep every outcome and failure line.
  - **Equivalence:**
    - the chains' statements are verbatim by AST, in base order;
    - first-match dispatch is unchanged over 15,372 cases, and planted reorders are caught;
    - 274 saved definitions parse, dispatch and give 1,857 control arrays, all bitwise.
  - **Known and accepted until the core-seams registration tables:** active worlds still load the
    legacy registration at run time through misses in `control_values` (and in parsing for
    reaction_transport@1). Each miss returns None, and the core answers.

- **D189's test retire merged into main (17 November 2026, early).** test-audit a676930b; the
  tree before it is tagged `pre-retire-2026-11-16` ([summary](/mnt/workspaces/Cells/test-audit-20261116-01/retire-fa19d80c/SUMMARY.json)).
  - **Retired:**
    - tier 3: 11 whole files (844 tests), and 23 cases in 4 files;
    - tiers 1 and 2: 40 whole files, and 788 cases in 38 files.
  - **The saving:** 5.5 core-hours per tier-3 run, and 2.0 minutes per tier 1+2 gate.
  - **Held instead, 8 rows, each with its reason.** Four tier-3 files run a coupling target, three
    files are needed by remaining tests, and three cases pass in a checkout with Git history. The
    L4 block runs no tests, so check (b) found nothing.
  - **Collection:** from 20,792 IDs to 18,482. That is exactly the 2,322 retired IDs fewer, plus 12
    added since. In the 38 edited files, all 1,731 remaining tests keep their outcomes.
  - **The records:**
    - the tiers now hold 327, 152 and 222 files;
    - tier 3's frozen record holds 218 files and 6,869 tests, naming D189 and the tag;
    - the tier tool records roots relative to the repository.
  - **The gate:** tier 1 with the BLAS pin merged, 327 files, none changed.
  - **Found by the gate:** a path-based read by a kept test. The file it reads was restored
    (351d7b6b).

- **The BLAS pin (D190) merged into main (17 November 2026, just after midnight UTC).** core-pin
  52dd5816 ([evidence](/mnt/workspaces/Cells/core-fixes-20261116/); probes in `/mnt/workspaces/Cells/core-pin-20261116/`).
  - **What it does:**
    - Every BLAS runs at 1 thread, from the first import of `cells.core` and again at each of the
      eight run entry points.
    - The counts are read back, and the run is refused otherwise (4.4 ms per call).
    - Run manifests record each library's version, kernel architecture and thread count.
  - **The environment:** threadpoolctl 3.8.0 was installed into venv-cpu and venv-gpu at 22:57 UTC on
    16 November. `pyproject.toml` declares it, with scipy 1.18.1.
  - **The effect:** the 825-node world gives the same bits on 1, 2 and 4 CPUs.
  - **crossrev was renewed once** (`record-cda5dc82`). Only the two S825 `field_capacitor_factor`
    bindings changed, and they equal the unpinned 1-CPU record exactly.
  - **The gate:**
    - G1: 113 of 113 identical;
    - tiers 1+2: 519 files, none changed;
    - the qualification and kinds sets: identical on the merged head.
  - **Found on the way:** a held legacy law pins `src/cells/__init__.py`'s content. So the import pin
    lives in `cells/core/__init__.py`, and D190's wording was amended.

- **FR-5's dt study: the development reading passes (16 November 2026, late evening).** Run
  dt5-a6639e79, from snapshot-a6639e79 on CPUs 8–11, 21:44–23:23 UTC
  ([verdict](/mnt/workspaces/Cells/d172-restructure-20261115-01/fr45/pipeline/dt5-a6639e79/reading/verdict.json),
  [summary](/mnt/workspaces/Cells/d172-restructure-20261115-01/fr45/pipeline/dt5-a6639e79/summary.log),
  [the start against 4b81a39c's](/mnt/workspaces/Cells/d172-restructure-20261115-01/fr45/pipeline/dt5-a6639e79/start-vs-4b81a39c.json)). This is
  development evidence: `fr5-transfer-v1` stays proposed and is not judged.
  - **Result:** every criterion, J1–J11, holds on both arms, so the declared 0.5 ms step stands.
    All 12 parts exited 0, with the expected step counts.
  - **The start** was re-run from the same snapshot. Its extract equals the earlier start's, leaf
    by leaf, apart from the source fields.
  - **Arm T (transfer):** the state errors at 0.5 ms are 2.8e-7 of the budget for X_L and 2.9e-9
    for pH. The crossings fall within 6e-8 s of the independent reference, and the planted
    control reads 314 × the budget.
  - **Arm R (release):** the X_L error is 3.3e-5 of the budget. The release in the window, 0.87363,
    equals the reference's, and the control reads 872 × the budget.
  - **Both arms:** energy residuals of 3.3e-11 and 2.1e-11, against 2e-3.
  - **The one visible margin:** arm R's cargo route ledger, at 0.147 of its allowance. Every other
    ledger ratio is at 1e-5 or below.
  - **Before registration:** the judge's F4 names the 1 ms rung for the energy residual, while the
    protocol's J7 reads 0.5 ms. Both pass here (1.3e-10 and 8.2e-11 at 1 ms).
  - **Costs:** 0.82–1.5 ms per step (spread unexplained), so runtime limits are sized from 1.5 ms.
  - **The judge's fix merged with fr45-next dac02715:** a part whose records end inside the injury
    window reads None for the release through the pore, rather than crashing.

- **The test audit (D187) merged into main (16 November 2026, late evening).** It ships its tools
  and the inventory ([evidence](/mnt/workspaces/Cells/test-audit-20261116-01/)). Nothing is retired by this merge.
  - **Tier 3's frozen record** (`tests/tier3_record.json`): D172's 229 files and 7,736 test IDs, with
    outcomes and normalized errors. The tier tool gains `collect`, `freeze` and `diff`, so a later
    tier-3 run is compared per test ID instead of re-running old code. The diff mode's 14 planted
    cases catch 12 of 12 mutants of the tool.
  - **The triage of tier 3:** 29.8 core-hours per run. 187 files pass. The rest are 23 harness
    limits, 11 stale tests, and possibly real defects F1–F8. F1, F3 and F6 have since been fixed in
    core-fixes.
  - **The legacy inventory** (`scripts/legacy_inventory.py`, D188 step 0): 111 families, of which 5
    are active, 4 are for the user to decide, and 102 are legacy. The modular path makes 42 imports
    into older modules.
  - **The retire list, proposed to the user:** `docs/TEST_AUDIT_RETIRE_LIST.md`. The firm list saves
    about 7.5 of tier 3's 29.8 core-hours per run.
  - **Gate:** tier 1 with its own tier tool, 365 files, none changed.

- **core-fixes merged into main (16 November 2026, late evening).** It fixes two of the test
  audit's findings ([evidence](/mnt/workspaces/Cells/core-fixes-20261116/)).
  - **F1, a real validation gap since 88866b60** (9 November, gauge option 2). A definition with a
    charged floating or gauge component was accepted at parse.
    - Runs refused it late, at step 0. The stationary analysis was fail-open: it reported 6.13e-7 V
      for a planted 1e-17 C.
    - The fix: a host-only neutrality check at the initial capacitor solve, refusing with
      ConfigError. It changes no program.
    - No registered world is affected. Of the 116, 7 have a representative, and every residual is
      exactly 0 C, so today's W1/W2 results stand.
    - It also closes F3: test_surface_excision goes from 40 of 43 to 43 of 43.
  - **F6, a crash since 9b6e85ed:** `schedule.py`'s UnboundLocalError for spatial_calcium@2–@5. The
    four files go from 44 failed and 45 errors to all passing, and move to tier 3 for their run
    time.
  - **Also:**
    - the kinds world set in `composite_crossrev` (D187 rule 2);
    - the design for allocation-independent linear algebra, proposed, which awaits the user.
  - **Checks:**
    - crossrev, 8 sets plus the kinds pair, identical;
    - G1: 113 of 113, bitwise;
    - tiers 1+2: 507 files, none changed;
    - quick checks on the merged heads, FR-5's charged starts included: none failed.

- **The run-view writer merged into main (16 November 2026, evening): run-view-d154,
  `cells.run_view@1`.** ([handoff](/mnt/workspaces/Cells/run-view-20261115-01/HANDOFF.md).)
  - **What it adds:**
    - the engine's writer of `view.json`. It reads the engine's own view declarations and record
      roles (`RECORD_DIAGNOSTICS`, `RECORD_REFERENCES`), keeps no per-model tables, and writes door
      S's merged view;
    - the loop block, with its closure measure: per record, over levels, amounts and rates, with
      diagnostics and cumulatives listed as not measured;
    - FR-11's first looping run: a planarian development run (not judged) that closes within
      2.76e-5 against a tolerance of 1e-4, bitwise the same before and after the adoption;
    - the cycle's admission probe, whose refusals went to the composition design;
    - a junction fixture at division.
  - **Gates:**
    - tiers 1+2 on b08af640: 508 files, none changed;
    - the re-check after windows landed: tier 1 (366 files) and seven tier-2 files, none changed;
    - the quick check on the merged head: none changed.
  - **Follow-up:** three format items from the visualizer's reader.

- **fr45-next merged into main (16 November 2026, evening): FR-4 and FR-5 on the landed core.**
  ([handoff](/mnt/workspaces/Cells/d172-restructure-20261115-01/fr45/transporter/HANDOFF.md).)
  - **What it adds:**
    - FR-5's source kinds, patch damage and a pH condition, on the routing door;
    - refusal 4 version 1.2 and refusal 5 version 1.1 for FR-1's compartments, so a charged lumen can
      resume from its own checkpoint;
    - FR-5's start part and engine records;
    - `fr5_quick_check` and `world_agreement`.
  - **Development evidence, not verdicts:**
    - **FR-4's dt study** (snapshot 3c10b833) passes J1–J7. pH, V_b, K_L and the cycles all class at
      rounding. pH is within 1.4e-12 of the independent reference at 1 ms. Energy converges at
      orders 2.02–2.04. The planted controls are caught.
      ([reading](/mnt/workspaces/Cells/d172-restructure-20261115-01/fr45/pipeline/dev-3c10b833-dt/reading/verdict.json)).
    - **FR-5's world agreement:** the development and declared worlds are bitwise equal over 400 s
      on both arms, 800,000 steps each, including arm R's release burst
      ([check](/mnt/workspaces/Cells/d172-restructure-20261115-01/fr45/pipeline/worlds-d82e1935/check.json)). FR-5 runs at 1.2–1.4 ms per step on quiet
      cores. An earlier "9 ms per step" was CPU starvation on a shared foreground CPU.
  - **Gates:**
    - tiers 1+2 on 32a72dab: 506 files, none changed;
    - the light re-check on 7f9bf71f: 371 files, none changed;
    - the admission-change files on the merged head 3bda393d.

- **windows-next-clean merged into main (16 November 2026, evening).** It brings the planner seams and
  opt-in device-resident row checks ([handoff](/mnt/workspaces/Cells/windows-next-20261116/HANDOFF.md)).
  - **What it adds:**
    - `window_arguments`, `WorldRefusal`, `MemoryRefusal` and the world-mode refusals;
    - `WindowPolicy(row_checks="device")`, which checks rows on the device and hands a window back to
      the host checks on any failure or any ratio above 1/2 (R3's margins);
    - the design note `docs/WINDOW_DEVICE_CHECKS_DESIGN.md`.
  - **The gate,** at 74ebb91b, with main merged in:
    - tiers 1+2: 510 files, none changed;
    - the vector set and 14 tier-3 files against c1's frozen rows: no change;
    - the continuity acceptance from a writable copy: 13 of 13;
    - crossrev: 8 of 8 sets identical.
  - **Speed against the host checks, on the same cores.**
    - **Both arms measured:**
      - the export: 4.8× at 80,000 steps, 1.4× at 8,000 (compile-dominated);
      - FR-4's 20 s pass: 3.7×;
      - the 825-node tissue: 1.05×.
    - **Long runs, device arm measured, host arm estimated** from the measured per-row host cost:
      - the export, 480,000 steps: about 9.4× (96.3 s against about 908 s);
      - FR-4, 900,000 steps: about 13.7× (453 s against about 6,220 s).

    Every run made in both modes is bitwise, and no window was handed back.
  - **Follow-up, fail-closed:** device mode is refused for a live retiring composition, until a planted
    dissipation test exists, and on a GPU backend, until a GPU measurement exists.

- **The visualizer merged into main (16 November 2026, evening): visualizer a4ef7492.**
  `visualizer/` only.
  - **What it adds:**
    - an "Origin of life" heading, with GARD as a model system. It plays an example run of
      invented numbers, marked as such, and its kernel finding is quoted only as the engine note's
      open finding, under review;
    - the Laws library's first phase;
    - cell types as first-class data;
    - the bacteria and phone fixes;
    - the builder split into part modules;
    - a GPU wrapper for the browsers that takes the shared `gpu.lock`.
  - **Checks:**
    - `npm test` on a clean copy: 511 passed, 2 skipped, 0 failed;
    - the BETSE-boundary and snapshot guards on the merged tree pass.
  - The branch's history holds an earlier wording of the kernel finding, corrected before the
    merge.

- **core-next merged into main (16 November 2026, evening).** It's the first lane built on D172's
  round to land ([handoff](/mnt/workspaces/Cells/core-next-20261116/HANDOFF.md)).
  - **What it adds:**
    - kinds' time-varying controls (gap 6);
    - the stored-energy rate and the `produced` ledger role (gap 2);
    - the routing door;
    - @3's and the kinds' own view declarations, and their record roles;
    - A7's allow-list fix;
    - insertion@2's gate at opening (item 4);
    - FR-5's raw-sum bound, derived from a rounding analysis;
    - ledger lists read from the model object (item 5).
  - **The gate,** at 5230f43b with main merged in:
    - **tiers 1+2:** 502 files, none changed;
    - **heavy:** 228 passed;
    - **crossrev:** identical in every set, apart from the intended changes, each recorded:
      item 4's onset select in the three insertion@2 division worlds, and the raw-sum bound's
      input term in the kind worlds;
    - **G1:** 113 of 113, bitwise;
    - **the in-place guard:** identical on 50 worlds.
  - **The raw-sum bound's teeth:** a planted sign flip is still refused, by about eleven orders of
    magnitude. FR-4's declared world is bitwise identical over 900 s with and without the fix.
  - **Found on the way:** the 825-node world's binding-time Cholesky is threaded by the linear
    algebra library, so its bits depend on the run's CPU count.
    - crossrev and G1 now log the count, and compare runs only at equal counts.
    - A design that removes the dependence is queued.

- **D172's round landed on main (16 November 2026, about 17:40 UTC).** Main ab267c39 merges candidate
  c1 = integration-d172 3c10b833 and is tagged `d172-landed-2026-11-16`.
  - **What lands:**
    - the inner model's declared laws, and dispatch per declared structure (`resolved_pump_tissue@3`);
    - the kind interface, with three built-in kinds (passive routes, a rapid proton buffer, the
      transporter);
    - the operators, with door S's scoped composition;
    - the species registry;
    - FR-1's compartments;
    - A7's fixed summation order (D182).
  - **The gates** (records in [RUN-c1.md](/mnt/workspaces/Cells/d172-restructure-20261115-01/endgame/RUN-c1.md)):
    - **results:** c0 bitwise on 113 of 113 worlds; c1 within A7's frozen tolerance file, with
      every physical field bitwise;
    - **crossrev:** c1 against c0, with constants and bindings identical in all eight sets;
    - **tiers 1+2:** 492 files, none changed;
    - **G2:** all 23 steps pass;
    - **the L4 block,** attempt 2: 103 pass, 0 fail, 28 report. W1, W2 and G2-Q1's Q1–Q7 pass, and
      all ten parity cases pass. The six cases judged in both attempts are identical;
    - **tier 3:** 229 files. 187 pass. All 42 non-passing files are classified
      ([table](/mnt/workspaces/Cells/d172-restructure-20261115-01/endgame/c1-3c10b833/tiers-3-table.md)), and none is the round's or A7's:
      - 23 pre-existing failures;
      - 16 pre-existing timeouts, whose 328 tail tests never ran in either tree (the heads-up said
        about 280; the audit's count is 328);
      - 2 stale tests from the round, fixed in the next commit with their masked checks
        verified;
      - 1 that passes when run alone.
  - **Privacy:** clean across the tree, the full history and the 157 commit messages. The merge
    differs from c1 only in docs, `visualizer/` and the root Markdown files.
  - **Not run as separate end-game steps, and owed (CURRENT_PLAN):**
    - G3's negative controls on the final candidate. These are planted changes that must fail the
      results gate. The round's per-commit contract tests ran in the tiers, and the results gate's
      planted-difference self-test exists;
    - G4's measurements of compile time, memory and end-to-end time.
  - **Open after the landing,** for D187's audit:
    - six pre-existing engine-side findings: the [anchor] refusal missing in surface_kinetic and
      surface_tissue, the cotransport/water energy failure, surface_excision's NumericalError, the
      fixed_step tracing trio, a behavioural assertion, and a missing MODEL_ID;
    - the never-run tails.

- **The visualizer merged into main twice, and the README brought to 16 November (16 November
  2026, the user's requests).** All three merges touch only `visualizer/` and `README.md`. No
  engine code reads `visualizer/`.
  - **df5b5cb3** (visualizer 39a20f75) adds:
    - the fruit fly and thale cress;
    - flagella and pili;
    - the quantity layers through flux in the Cell view;
    - the run-view reader and its note on what the layers need from the engine;
    - the published map through Version 16.

    The visualizer reported 428 tests passed and 1 skipped.
  - **7c023576** (visualizer 9b780f33) adds:
    - four screenshots for the README ([captions](visualizer/docs/screenshots/README.md));
    - the species tools sharing one module, each writing byte-identical files;
    - a research note on typical flux values. It keeps no number whose original is
      non-commercial.

    **Checks:**
    - `npm test` on a clean copy of 9b780f33 (Node, pinned to one CPU): 425 passed, 4 skipped,
      0 failed;
    - the BETSE-boundary guard and the D131 source-order guards on the merged tree: 5 passed and
      46 skipped, the skips all D131's
      ([log](/mnt/workspaces/Cells/visualizer-merge-20261116/guards.log));
    - the snapshot test, which enumerates every tracked file, on the merged tree: 24 passed
      ([log](/mnt/workspaces/Cells/visualizer-merge-20261116/source_snapshot.log)).
    - This is a smaller guard set than the 15 November merge's (68 passed).
  - **A fifth visualizer merge** (visualizer 35098c8e) adds:
    - two cell-view screenshots, now in the README: the human's generic cell with its planned
      nucleus, Golgi apparatus and ribosomes, and E. coli, which is proposed and not modelled;
    - the published page's revision stamp, corrected. A local, amended commit had been stamped;
    - a build guard that refuses a revision on no remote branch.

    **Checks:** `npm test` on a clean copy gave 443 passed, 2 skipped and 0 failed.
  - **A fourth visualizer merge** (visualizer 5830bfdf) adds:
    - the nucleus, the Golgi apparatus and the ribosomes, as planned parts of the map that are
      illustration only (by the user's decision of 16 November);
    - the replay's own clock and speeds;
    - the run-view reader at the writer's fd008813, with two engine-written fixtures;
    - the published pages' new links.

    **Checks:**
    - `npm test` on a clean copy (two CPUs): 443 passed, 2 skipped (both need adapted replays), 0
      failed;
    - the BETSE-boundary guard and the snapshot test on the merged tree: 29 passed
      ([log](/mnt/workspaces/Cells/visualizer-merge-20261116-b/guards.log)).
  - **A third visualizer merge** (visualizer c91d8cd2) brings the engine map and the
    layers-needs note to D183, so the human loop is shown as waiting for the human cardiac
    laws.
    - `npm test` on two CPUs: 427 passed and 2 skipped. Both skipped tests need adapted replays,
      which a clean checkout lacks.
    - The earlier run's two extra skips came from pinning to one CPU: one test needs two
      processors, and one skipped without need (now fixed).
  - **The README** (462469dd, from readme-update) has:
    - the status table as of 16 November, with the levels defined;
    - a new section, "The visualizer and its replays", with two of the screenshots;
    - corrections from the visualizer session, which ran the six build commands from a clean
      checkout.

    The advisor reviewed it. FR-11 is described as proposed, and its human loop waits for the
    human cardiac laws (D183). The restructure's "in progress" sentences flip at D172's landing
    (the list is in the round's LEAD-NOTES).

- **D172's end game, paused for a planned machine restart (16 November 2026, 10:33 UTC).** Records
  are under `/mnt/workspaces/Cells/d172-restructure-20261115-01/endgame/`, and the resume steps are
  in the round's `LEAD-NOTES.md`.
  - **c0 = integration-d172 22356272** (the integrated candidate before A7, main merged in):
    - G1 bitwise, 113 of 113 worlds;
    - crossrev identical in all eight sets;
    - tiers 1+2: 491 files, 0 changed.
  - **c1 = integration-d172 3c10b833** (c0 plus A7, D182):
    - crossrev against c0: constants and bindings identical in all eight sets, program texts
      changed by A7 as intended;
    - G1 under the frozen tolerance file: 113 of 113 within it, physical fields bitwise, and the
      same 31 bitwise and 82 moved worlds as the rehearsal;
    - tiers 1+2: 492 files, 0 changed.
  - **G2 at c1:** every registered small protocol re-run passes. That is Track R, D150, S3, Rm1,
    S5a, MG0b, MG0c, cell replacement and stationary E: 23 steps, every verdict read. E07-v1 is on
    hold (D181).
  - **L4 block at c1, under the deterministic flag:**
    - phase 1 is complete: W1, W2, G2-Q1 and the ten parity cases repeat bitwise, the backend terms
      are at most 4.2e-14 V, and every tolerance is unchanged. The ten parity CPU reruns are bitwise
      equal to their registered judged results;
    - the three flagged variants are registered;
    - W1's judged run C **passed**.
    - C's other items and the parity judged pass stopped for the restart before any verdict was
      written. They are re-attempted after it.
  - **Tier 3 at c1** was partial when stopped. It resumes for the remaining files, with every
    failure attributed against the tag and c0.

- **G2-Q1's Q7 passes on the L4 under the deterministic flag (16 November 2026;
  `resolved_pump_replacement@1`, `resolved_pump_tissue@3`).**
  - **The failure it answers.** On 14 November the composite's L4 judged run C passed W1, W2 and
    G2-Q1's Q1–Q6, and failed Q7. Q7 claims the replacement model without events equals @3
    bitwise on the 825-node world. The cause was the L4's own run-to-run nondeterminism: unflagged
    repeats differ by up to 1.9e-11 relative.
  - **The flag.** Under `--xla_gpu_deterministic_ops=true`, 15 of 15 repeats were bitwise across
    processes.
  - **The judged run.** Q7 was then judged alone under the flag, with the registered G2 variant,
    from a clean snapshot of main cfbe7122, at 03:06–03:10 UTC. It passed: every state field and
    observation is bitwise, every diagnostic equal, the replacement fields zero, and `XLA_FLAGS`
    is in the item record.
  - **Its scope.** The verdict holds in the declared flagged mode only (D168, D181). C's Q7
    failure stays C's verdict, because the protocol judges once and retries nothing. The unflagged
    mode's run-to-run term stays as measured.
  - **Records:** [record](/mnt/workspaces/Cells/composite-l4-agreement-20261114-01/record.json),
    [Q7](/mnt/workspaces/Cells/composite-l4-agreement-20261114-01/q7-judged/judged-q7/Q7.json),
    [determinism test](/mnt/workspaces/Cells/composite-l4-agreement-20261114-01/determinism/l4-20261115/analysis.json).
  - **The flagged block's amendment** for D172's 13-run L4 block is registered before its first run
    (`validation/tissue/l4_variants/flagged_block_amendment.json`).
  - **Also overnight:**
    - the summation GPU column settled A7's barrier placement (D182);
    - the W1 full-tissue hold completed its 70-minute retention (segment 4 ended 02:28 UTC). Its
      comparison with the predictions written before the run is development analysis, still to
      do.

- **D172's round on the evening of 15 November 2026: schema A landed on the integration branch,
  the core's kinds cleared, and FR-4's first development rung.** Evidence is under
  `/mnt/workspaces/Cells/d172-restructure-20261115-01/` (`integration/`, `core/c8`, `core/c9`,
  `fr45/pipeline/`).
  - **integration-d172 at 72f5c29e, schema A with the adapter work:**
    - the sharded results comparison is bitwise in 113 of 113 worlds;
    - the crossrev pair is identical in all eight sets, so schema A changes no program of today's
      worlds;
    - tier 1+2 at the merge is 356 and 120 files, none changed from the record.
    - The first gate on the branch had found two earlier regressions that per-merge test lists had
      missed. Both are fixed in the merge.
  - **The core's kinds on core-d172, at 2c780f9f,** cleared for integration by three regressions
    (134, 273 and 287 tests), tier 3 and three crossrevs identical in all eight sets. They are:
    - the proton buffer, `cells.rapid_proton_buffer@1`, with its term in @3's 1 mM convention;
    - the passive law, `cells.passive_routes@1`, with §7.5's exact booking and the proton leak law;
    - the kind seams: per-node stage terms with the stage's potentials, held rows with one writer,
      per-stage extrema, `KindRates.valid` and a public parsing surface.
    - Its advisor found and fixed a real bug in the exact booking's scope.
  - **FR-4 (development evidence, not judged; the protocols stay PROPOSED):**
    - the transporter kind, `cells.transporter@1`, drives FR-4's world with every ledger closed;
    - the 900 s rung at 1 ms agrees with the independent reference to 1.4e-12 pH at all 901
      records;
    - the reversed-pump control K2(b) runs its 900 s and tracks its own reference to 7.5e-11 pH. It
      is caught at the first record, 3.28 pH from the declared world, against the reference's
      effect recorded on main (81559119).
    - The device-checked vector path covers the same checks and agrees bitwise except two
      accumulators, at about 1e-13. It steps 7.5× faster, so a pass costs about 2.3 CPU-h. The
      protocols declare it by a dated pre-run correction.
  - **The end game's landing script:** its crossrev check and three other checks could pass bad
    records. They now require exact counts with exit 0, and 35 planted bad records are refused.
  - **Then, after midnight, integration-d172 at cd702afc.** The core's batch, the transporter and
    the composite's one-writer admission are merged:
    - an operator writing a kind's held row is refused;
    - an operator writing an exact-booked passive route's row is refused (version 1, fail-closed).
    - The results comparison is bitwise in 113 of 113 worlds, the crossrevs are identical in all
      eight sets, 23 targeted files pass, and tier 1+2 is 358/132 files with 0 changed.
    - The tier tool now forces `JAX_PLATFORMS=cpu`. Four JAX test files' old error rows came from
      its absence.
  - **The landing script for A7's c0 → c1 step:**
    - c0's crossrev must be identical to the post-batch record;
    - c1 keeps constants and bindings identical, while program texts may differ;
    - 75 checks are refused or accepted as designed.
  - **Next:** A7 after tonight's GPU column, then the compartment operator's refusal lifted for
    FR-4's kinds, then the end game.

- **A7's results-gate tolerance rehearsal: physical fields bitwise in all 113 worlds (15 November
  2026).** This is development evidence for the round's results gate
  ([note](/mnt/workspaces/Cells/d172-restructure-20261115-01/operators/summation/out/rehearsal/NOTE.md)).
  - **Setup:** the results baseline tool, unchanged, saved the tag's 113 worlds with A7's serial
    left fold installed, the barrier at every listed site. It ran in unit `cells-sum-rehearsal`
    on CPU 3, 17:33–18:53 UTC.
  - **Bitwise:** 31 of 113 worlds are identical. In the other 82, only ledger and diagnostic arrays
    moved: the reservoir work, junction, face and lumen heat, the energy-balance observations and
    the residual diagnostics. No amount, gate, potential, voltage, transfer, volume or D152 amount
    moved, and the one refusal matched in type and message.
  - **The tolerance file written before the run:** 108 of 113 worlds within tolerance. The five
    failures were missing or zero bounds on movements at rounding, at most 3.5e-18 pJ against
    2–6 pJ ledgers.
  - **The final file** (`a7-g1-tolerance.json`, 862 patterns) makes three changes after seeing the
    data, each named in the file. Each gives a zero or missing bound an absolute floor of
    16 eps × its own energy scale. Under it, all 113 worlds are within tolerance, and the closest
    approach is 0.27 of a bound. The lead accepted the changes, because no physical field gained
    a pattern.
  - **Next:** tonight's GPU column (`cells-sum-gpu`, after the hold's segment 4) decides the
    barrier's placement, then D182 records A7.

- **The L4 agreement driver gained a flagged mode, and D181 is recorded (15 November 2026).**
  Validation only. Tier 1 at the merge: 344 files, no changed outcome.
  - **The mode:** `composite_l4_agreement.py terms --mode flagged` takes one run and its confirming
    repeat, both under `--xla_gpu_deterministic_ops=true`. The backend term is measured under the
    flag, and the run-to-run term is exactly 0. A repeat that isn't bitwise stops the block.
  - **The unflagged path is unchanged.**
  - **Why:** Q7's analysis on the L4 showed the flag gives bitwise repeats of the 825-node tissue,
    15 of 15 pairs.
  - **D181:** E07-v1's re-run is held, and its worlds are covered by the results gate. The round's
    13-run L4 block runs under the flag.

- **The coupling operator's matched-arm export ran (15 November 2026, D177).** It is development
  evidence, with no registered or judged verdict
  ([EXPORT.md](/mnt/workspaces/Cells/coupling-export-20261115-01/EXPORT.md)).
  - **Setup:** the driver `validation/tissue/matched_arm_export.py` ran from a clean snapshot of main
    5c2b04d6, with `resolved_pump_composite@1` over `resolved_pump_tissue@3`,
    `scheduled_species_turnover@1` and `species_regulated_availability@1`.
  - **The 16 definitions** (four arms at four steps) were admitted and executed. Six fresh-process
    restarts and the 4- and 7-step windows are byte-identical on all 103 fields.
  - **Agreement:** the engine agrees with the refined independent reference to 2.9e-5 mV at 1 ms,
    and to 4.5e-7 mV at 0.125 ms.
  - **A finding: decimal record times are refused** at window planning, because an observation time
    must be an accepted integration boundary. The export uses the engine's grid times instead.
  - **Duration probes** at 0.125 ms: 1 s, 10 s and 60 s took 126 s, 680 s and 3481 s. At 60 s, 91% of
    the wall time is host-side window checks; the compiled step costs 0.46 ms. That is input to the
    round's inventory of host-side checks.
  - **The first viewer feed,** a development run of the secreted-species world through the shared
    output path, is in /mnt/workspaces/Cells/viewer-feed-20261115-01/.

- **A future FEP track proposed (15 November 2026; docs only; PROPOSED, not scheduled).** At the
  user's request ([proposal](docs/FEP_TRACK_PROPOSAL.md);
  [source log](/mnt/workspaces/Cells/fep-track-20261115-01/sources.json)).
  - **Claims discipline:** no result could prove the free-energy principle. A comparison harness
    would carry planted tests, and a pair with identical dynamics that must come out
    indistinguishable.
  - **Three deferred stages:**
    - chemotaxis in a well-mixed cell first;
    - anticipatory regulation, held with D145's gene-regulation hold;
    - collective tissue regulation, including islet calcium waves, which is Track E's coupling
      physics.
  - **Engine gaps:**
    - Stage 1a needs only general items: an allosteric factor, occupancy as a coupling source,
      output-dependent adaptation and an organism instance.
    - Motility, gene expression with delays, long durations, evolution and observation models are
      missing.
  - **Timing:** recommended after the D172 round and FR-4/FR-5, at about 20–28 agent-days. The
    decisions listed in the proposal are the user's.

- **The results baseline tool, the protocol scan and the matched-arm export driver landed (15
  November 2026).** Validation only.
  - **Gate:** tier 1 at eb9ca828: 344 files. Two tree-scanning guards changed, both on the new tools.
    - The export driver named a checkpoint's array file, which the continuity guard forbids. It
      now lists the checkpoint's files.
    - The baseline tool built free-offset worlds without D147's declaration. It is exempt, with its
      reason: its worlds run as their protocols declare them (G2-Q1's Q7 tissue as its judge runs
      it), and `--from` re-runs saved definitions verbatim.
    - The guards and the new tests reran on the fixed tree at df61c3f0: 77 passed
      ([log](/mnt/workspaces/Cells/d172-restructure-20261115-01/acceptance/land-guards-df61c3f0/guards.log)).
  - **`validation/results_baseline.py`, D176's results gate:**
    - It saves a defined world set's CPU outputs at a tag, and compares a later source's outputs
      bitwise or at a declared tolerance. Refusals must match exactly.
    - K1's padding exemption is opt-in, and off for D172's dispatch gate.
    - The baseline at tag `d172-base-2026-11-15` holds 113 worlds, 112 of which run
      ([baseline](/mnt/workspaces/Cells/d172-restructure-20261115-01/acceptance/baseline-44227075/)).
  - **`validation/protocol_models.py`:** lists the engine models each protocol names, for G2's
    scope.
  - **`validation/tissue/matched_arm_export.py` (D177):** the coupling operator's A5 world in four
    arms at four steps, with independent references, restarts and windows. It is a driver of the
    established runners. It adds no physics and gives no verdict.
  - **Packed GPU execution, a design point (proposed):** on the L4, 80–90% SM activity is reached at
    128 or more worlds of one structure (89% at 128, 93% at 256).
  - **15 self-tests** (10 and 5), tier 1.
  - **Also landed:** the inner-model note's revisions.
    - Finite fuel rows are the transporter's default, held rows the special case.
    - §7.5's monotone booking is a proposal awaiting a probe and the lead's ruling.
    - The plan is re-costed at about 14–18 days.

- **FR-5's and the finite-fuel case's independent references landed, with D177 and the FR-4/FR-5
  note's revisions (15 November 2026).** The references are in `validation/compartment_ph/` and were
  written code-blind ([usage](validation/compartment_ph/REFERENCES_USAGE.md);
  [evidence](/mnt/workspaces/Cells/independent-references-20261115-01/HANDOFF.md)). Tier 1 ran at
  b5954bf3: 342 files, no changed outcome. The later commits are docs only, apart from the
  visualizer merge (the next entry).
  - **R-transfer (FR-5)** runs the note's §13.2 from FR-4's steady state at 1800 s.
    - The first world showed neither of its claims: the cargo had crossed before the damage, and
      the condition never closed. The world was revised into two arms, with numeric claims.
    - **Arm T:** while pH_L is above pH₅₀, the conditioned transfer slows 13.7-fold; it does not
      stop. pH_L returns below pH₅₀ at 327 s.
    - **Arm R:** the pore releases 0.874 of the lumen's cargo inside the damage window. pH_L
      returns below pH₅₀ at 367 s.
    - Both controls clear 10 times the cargo budget (314 B and 872 B). Energy closes within
      4.2e-11 pJ.
    - The engine comparison must start the reference from the engine's own 1800 s checkpoint: the
      cargo moves about 0.06 B per 1e-3 pH of start offset.
  - **R-fuel (D176's finite-fuel case):** an ATP-driven pump moving a neutral solute, with
    stoichiometric regeneration.
    - With regeneration off for 200 s, ATP falls from 3.27 to 1.7e-4 mM, and the pump to 0.0018 of
      its held-fuel rate.
    - The pump is back within 1% two seconds after regeneration resumes.
    - The books close within 2.5e-11 pJ.
  - **11 self-tests** (6 and 5), tier 1.
  - **Also landed:**
    - D177, recording the user's decisions on a downstream user's requests;
    - the FR-4/FR-5 note's consistency fixes: B7 host-only, and one continuum label;
    - FR-5's revised §13.2: two arms, numeric claims confirmed by the references, and dt 0.5 ms.
    - FR-11, the user's request for looping replay packages of living cells for the viewer, with
      the user's choices;
    - D178, the user's ruling on the visualizer's placement predictions.

- **The visualizer merged into main again (15 November 2026, the user's request).** It adds the
  `visualizer` branch's commits since the 14 November merge, all under `visualizer/`, up to
  d0201f3a. Nothing outside `visualizer/` changed.
  - **What it adds:**
    - the species switch (human, planarian, Syn3A, *M. pneumoniae*);
    - each species' protein shelves: Syn3A's 455 proteins, *M. pneumoniae*'s 688, and the
      planarian's 18,882 in families;
    - the planarian bioelectric evidence audit;
    - the quantity layers' contract, and the visualizer's note on what the layers need from the
      engine. The lead's answers route requests 1–8 to the run-view writer in D172's round.
  - **Licence:** the user ruled that membrane-placement predictions read from UniProt and WormBase
    ParaSite may stay (D178).
  - **Gate:** the tree-scanning guards ran on the merge and passed: 68 passed and 46 skipped, the skips being the D131 ones
    ([log](/mnt/workspaces/Cells/visualizer-merge-20261115/guards.log)). No full tier gate ran for
    this part, because the tier runner collects `tests/` only. The visualizer reported 225 of its own
    226 tests passing, with 1 skipped, on a clean copy of 268ed6de.

- **FR-4's and the passive law's independent references landed (15 November 2026).** They are in
  `validation/compartment_ph/` and `validation/passive/` and were written code-blind
  ([FR-4 usage](validation/compartment_ph/REFERENCES_USAGE.md);
  [passive usage](validation/passive/REFERENCES_USAGE.md);
  [evidence](/mnt/workspaces/Cells/independent-references-20261115-01/HANDOFF.md)). Tier 1 at the
  merge 22d4251: 340 files, no changed outcome.
  - **FR-4's references** (R-closure and R-kinetic, Radau at rtol 1e-11) run the FR-4 note's
    acceptance world for 900 s.
    - The lumen acidifies from pH 7.2 to 5.096 against the gradient, and the cytosol stays within
      0.018 pH. The energy identity closes within 2.2e-11 pJ.
    - The kinetic system converges to the closure at first order in 1/k_on: the lumen's largest
      lag is 1.26e-2, 1.28e-4 and 1.28e-6 pH at k_on = 1e3, 1e5 and 1e7 mM⁻¹ s⁻¹.
    - With the counterion route removed (P_K = 0) the lumen stalls at pH 7.14. The route's effect
      is 2.04 pH units, 2,044 times the 1e-3 pH budget.
    - The declared outside case (the lumen's k_on at 1e-3) lags by up to 2.2 pH units and fails,
      as the note requires.
  - **A finding: the note's envelope did not imply its budget.** The check λ ≥ 10³ρ admitted k_on
    four orders of magnitude below the point where the 1e-3 pH budget holds (about 1.28e4).
    - The lag is (ρ/λ)(β/ln 10 − h)/(h ln 10). Its bound-to-free factor is about 1.5e4 at pH 7.2.
    - The FR-4 owner replaced the fixed ratio with this state-dependent check and a planted test
      (`fr45-physics`, 4f7e1a30). The check lands with FR-4's code on `integration-d172`; the
      note's revision lands on main with the next docs batch.
  - **The passive law's closed pair:** a closed form (floats and 50 digits) and Radau and DOP853
    integrations of any closed graph.
    - Flux and heat are exactly 0 at equal concentrations, and reversal is exactly antisymmetric.
    - Heat is non-negative and monotone; material is conserved within 3.8e-15.
    - The per-step heat is within 1.24 ε of its rounding scale over 5,000 random steps.
    - The core owner's conventions answer its three questions: a junction's PA is
      P·A·gate·availability, heat goes to the law's own field, and a trace is a start, never a
      zero.
  - **20 self-tests** (8 and 12), tier 1.

- **FR-3's independent site-occupancy references landed (15 November 2026).** They are in
  `validation/occupancy/` and were written code-blind
  ([usage](validation/occupancy/REFERENCES_USAGE.md);
  [evidence](/mnt/workspaces/Cells/independent-references-20261115-01/HANDOFF.md)). Tier 1 at the
  merge 66d248d: 338 files, no changed outcome.
  - **R-ode** integrates the full binding kinetics (Radau, rtol 1e-12, cross-checked by DOP853).
    - Against the saturable sink, the day-one guard converges at orders 0.980 and 0.998 in ε.
    - Its floor sits well below the engine errors to be judged.
  - **R-dG** re-implements the per-step bookings independently. Its ledger closes within 0.41 ε of
    scale, and its heat and work converge at second order.
  - **20 self-tests, tier 1.**

- **Track E, M1's development work landed (15 November 2026).** Validation only; no judged claim.
  Tier 1 at the merge 0385674: 337 files, no changed outcome
  ([evidence](/mnt/workspaces/Cells/excitable-tissue-m1-20261114-01/HANDOFF.md)).
  - **What landed:**
    - the sheet and probe drivers;
    - the conduction observables and the rule (b) importer (D170 ruling 5);
    - the PROPOSED qualification protocol (`validation/tissue/excitable_qualification_v1.json`);
    - the note and appendix revisions.
  - **The engine models run:** `resolved_pump_tissue@3`, the generic 0.01 F/m² cell A, and its
    fallback B, all development runs.
  - **On the 127-cell sheet both options carry a front:** s = 300 at 5 µs, and s = 1000 at 2.5 µs
    with a stronger, shorter stimulus.
    - A disc of weak cells delays the far column by up to 0.23 ms (s = 300). At low coupling the
      delay is set by load, not excitability: the active disc equals its passive twin.
    - Within the junction floor (s·r_gj ≥ 20) no arm blocks at s = 300. At s = 1000 two
      disc-boundary cells are passive at combined r = 0.02.
    - Block beyond a cluster needs coupling below the floor, which is `junction_ungated@1`'s domain.
  - **Margins:** the channel domain's is thin (+57.7 mV against +60) and the junction's wide
    (about 38 mV). The one-cell values match the independent references in 37 of 37 comparisons.
  - **A general finding:** an abrupt stimulus must keep strength × step ≤ 2e-12 m, or ramp its
    onset.
  - **Open:** the wave's own largest step (C5); C4's stimulus independence at s = 100; and the
    activation threshold, proposed at 0 with its sensitivity shown.
  - **M3's direction is the user's:** delay only within the floor, or block with the ungated
    junction law in the restructure round.

- **FR-1's and FR-3's four slowest test files split (15 November 2026)**, tests only, with every
  assertion kept. Each of the eight new files fits the 90 s cap, so FR-3's idle, stage and vector
  checks and FR-1's restart now run in the routine tier 2. Tier 1 and 2 at the merge e05619e: 449
  files, no changed outcome.

- **The G2 judge records the numerical environment (15 November 2026).** This is a record-only,
  validation-only change before today's L4 gap. `cell_replacement_judge.provenance()` now writes
  `XLA_FLAGS` and `JAX_DISABLE_JIT`, from `cells.io.runtime_identity()`, into every item record, so
  a Q7 run under the deterministic flag shows it. The verdict rule is unchanged: the 7 saved item
  records of L4 run C keep their verdicts. Tier 1 at the merge 541fad5: 335 files, no changed
  outcome.

- **The crossrev baseline of record is renewed at df5826f** (D148 criterion 4 for FR-1's contract
  change; it also covers item 3). All eight sets are identical to their records: base,
  qualification, injection, volume and division against baseline-da94f81; species and reactions
  against their da94f81 records; and coupling against its first record at f2ada38
  ([records](/mnt/workspaces/Cells/architecture-block-20261114-01/baseline-df5826f/)).

- **Phase start and failure records landed (item 3 of the architecture block, 15 November 2026).**
  Tier 1 and 2 at the merge 85346c8: 440 files, no changed outcome
  ([evidence](/mnt/workspaces/Cells/architecture-block-20261114-01/HANDOFF.md)).
  - **What it records:** `core/phases.py` gains a `Recorder` per run path (runner, batch, windows,
    vector windows).
    - Each marked phase writes `<phase>.start`.
    - Any exception leaving a path writes exactly one failure record (phase, type, seconds,
      message), then propagates unchanged.
    - Everything is at INFO, with no added device synchronisation.
  - **Checks:**
    - crossrev identical in all eight sets;
    - the four run paths bitwise before and after the change (92 arrays);
    - all seven run-path tier-3 files pass.
  - **The run-view writer note** (`docs/RUN_VIEW_DESIGN.md`, D154) lands as proposed. It is under
    the lead's review.

- **FR-1 milestone 1, FR-10 milestone 2 and FR-3 milestone 1 landed (15 November 2026).** Tier 1
  and 2 at the merge a917d72: 438 files, no changed outcome. The four files over the 90 s cap
  passed when run on their own. This is development code; each qualification comes later.
  - **FR-1, `cell_owned_compartments@1`** ([note](docs/CLOSED_COMPARTMENT_DESIGN.md) §12;
    [evidence](/mnt/workspaces/Cells/closed-compartment-m1-20261114-01/HANDOFF.md)).
    - **What it is:** a declared compartment with its own ID and role (no physics depends on the
      role in version 1), carried as a host-side identity map.
    - **How it enters:** a `DECLARATION_ONLY` marker in the contract that fails closed. A
      composition of declarations alone takes the empty-composition path.
    - **Silence:** S1–S3 hold on every row of the scalar, restart, RK4, windowed, vector-window and
      batch programs. The world is a live owner, with planted controls that break silence. S4 and
      S5 hold.
    - **Crossrev:** identical in the seven da94f81 sets, under D148's record written first.
  - **FR-10 milestone 2:** a dose step is admitted only where a measured passing point covers it in
    ratio and level, with the solver and face conditions measured. The probes covered neutral
    steps up and down, and K up and Na down for salt substitution. Everything else is refused, and
    the species cap is checked.
  - **FR-3, `site_occupancy@1`** ([note](docs/SITE_OCCUPANCY_DESIGN.md) §12;
    [evidence](/mnt/workspaces/Cells/site-occupancy-m1-20261115-01/HANDOFF.md)).
    - **What it does:** binding sites are owned by their own operator, with no field inputs, so an
      occupancy-only world never refreshes the field.
    - **Its integrator:** D152's SSPRK(3,3) with the per-route hybrid, reimplemented. It is
      recorded as one shared block for D172's round.
    - **Checks:** the face-free world at rounding, three negative controls, idle bitwise, restart
      and batch, and the stage condition's refusal.
  - **The composition matrix** now has 19 laws, with the new operators' refusals tagged.

- **MG0c judged: the reactions operator `local_species_reactions@1` (D152 v1) is numerically
  qualified within MG0c's scope (15 November 2026).** The protocol `mg0c-turing-v1` was registered
  at 5ab4326 (tag `mg0c-v1-registered-2026-11-15`), and one judged run was made from a clean
  snapshot of that commit ([verdict](/mnt/workspaces/Cells/shared-inventory-reactions-v1-20261114-01/judged-5ab4326a/combine/verdict.json);
  [launcher log](/mnt/workspaces/Cells/shared-inventory-reactions-v1-20261114-01/judged-inputs-5ab4326a/orchestrate.log)).
  - **The verdict passed:**
    - all 55 judged criteria (Q1–Q7 and the controls by parameter, every kept control caught);
    - all 10 judged guard files;
    - the combined verdict, whose snapshot revision is the registration commit.
  - **Every unit succeeded,** with no out-of-memory event. a ran 63 min (peak 2.6 GB), b 74 min
    (2.5 GB), q7 3 min, c 48 min, judge-guards 18 min (3.2 GB), then judge and combine.
  - **It is identical to the rehearsal** in all 10,502 compared non-timing values
    ([compare](/mnt/workspaces/Cells/shared-inventory-reactions-v1-20261114-01/judged-5ab4326a/compare-judged-vs-rehearsal.json)).
  - **The scope** is driven mass action of orders 0, 1 and 3 (Schnakenberg) at outside nodes, with
    @3's species transport on faces in the composite, on CPU. The items not judged are listed in
    the verdict.
  - **Disclosed in the protocol:** the development runs predate FR-9, and the 1e-2 control cutoff
    was set with the modes' sensitivities known.

- **MG0c (D152): the protocol after its rehearsal on main and the final check (15 November 2026).**
  It is still PROPOSED. Tier 1 at the merge e1cdc79: 329 files, no changed outcome.
  - **The rehearsal on main 58b6f14:** every judged entry ran on a registered dry-run copy, in its own
    unit on CPUs 5 and 7. The verdict was 55 of 55, and 10,103 values were identical to the
    development runs, apart from one count of control re-integrations.
  - **The redraft:**
    - runtime limits of about 3× the rehearsal plus 10 minutes;
    - the lanes as rehearsed, with judge-guards at a 5 GiB minimum cap;
    - the development runs restored as its basis;
    - the launcher alone enforces caps, CPUs and limits.
  - [Evidence](/mnt/workspaces/Cells/shared-inventory-reactions-v1-20261114-01/HANDOFF.md).
    Registration and one judged run follow.

- **The coupling operator `species_regulated_availability@1` is numerically qualified (judged,
  15 November 2026).** The protocol was registered at abe4ef5 (tag
  `coupling-v1-registered-2026-11-15`), and one judged run was made from a clean snapshot of that
  commit ([verdict](/mnt/workspaces/Cells/inventory-coupling-m4-20261114-01/judged/verdict/verdict.json); [log](/mnt/workspaces/Cells/inventory-coupling-m4-20261114-01/judged/judged.log)).
  - **The verdict passed:** all 47 judged criteria, with 16 reported. The verdict's source revision
    is the registration commit. The run took 1,378 s on one CPU and peaked at 0.98 GB.
  - **What was judged:** the order against the independent references, in the band [1.7, 2.3]
    fixed in advance.
    - A4, reciprocal feedback (R-feedback): V, the amounts and U, plus all six observables of the
      fast arm.
    - A5, a species setting a channel's availability (R-cell): V and the amounts.
    - A1, the factor values against R-fac's exact path.
    - All four controls were caught: the regulatory state at first order, a factor one step
      stale, and two basal-level δ controls.
  - **The judged run is bit for bit identical to the rehearsal** in every part and control
    ([compare](/mnt/workspaces/Cells/inventory-coupling-m4-20261114-01/judged/compare-to-rehearsal.json)).
  - **The scope:**
    - CPU only, in version 1;
    - A4 starts from the reference's state at 50 ms and sits at the explicit-rate bound's edge;
    - the horizons are 2 s and 1 s;
    - no pumps or gated channels;
    - A10 is out of scope.
  - **Disclosed:** the band, the judged observables, the registered δ and the rounding-scale rule
    were fixed with the development results in view.

- **The coupling operator's qualification protocol, after its rehearsal and the final check (15
  November 2026).** It is still PROPOSED. Tier 1 at the merge d8ee24a: 329 files, no changed outcome.
  - **The rehearsal on main 0448f9f:** the judged entries were refused while PROPOSED. The dry run
    reproduced the development run bit for bit, with the δ-controls at their registered δ by
    design, and its verdict passes with every control caught.
  - **The final check** (with the advisor):
    - a `register` path in MG0c's form, with the verdict from a registered copy identical to the
      rehearsal's;
    - the refusal tests are safe with the protocol registered;
    - D147: 0 free offsets in all nine worlds;
    - a runtime limit of 4,500 s, with the rerun-once rule for infrastructure endings;
    - the disclosures recorded.
  - [Evidence](/mnt/workspaces/Cells/inventory-coupling-m4-20261114-01/HANDOFF.md). Registration and
    one judged run follow.

- **The coupling operator's qualification protocol (milestone 4, PROPOSED) and the composition
  matrix landed (15 November 2026).** Validation, tests and docs only, during MG0c's `src/` hold.
  Tier 1 at the merge 200b796: 329 files, no changed outcome
  ([summary](/mnt/workspaces/Cells/inventory-coupling-m4-20261114-01/land-gate1-200b796c/summary.json)).
  - **The protocol** ([JSON](validation/tissue/regulated_availability_protocol.json);
    [note](docs/INVENTORY_COUPLING_DESIGN.md) §10;
    [evidence](/mnt/workspaces/Cells/inventory-coupling-m4-20261114-01/HANDOFF.md)):
    - **What is judged:** the order against the independent references, in a band of [1.7, 2.3]
      fixed in advance, with a minimum number of resolved pairs per rule. That is 47 judged
      criteria and 16 reported.
    - **The controls:** the regulatory state at first order, and a factor one step stale, both
      near order 1.0; plus basal-level δ controls. Every one is caught on the development run.
    - **The 1 ms errors** are a tier-3 regression guard, not judged.
    - **Version 1 runs on CPU only.** The scope line is recorded.
    - **Next:** the rehearsal on main, the final check with the advisor, registration and one
      judged run.
  - **The composition matrix:** all 17 operators, regenerated from their declarations by a tier-1
    test.
    - Real and nominal refusals are tagged. A nominal tag means disjoint slots, not that the pair
      is safe under today's adapter (D174).
    - Every definition rule cites its test. The composite's RK4 composition rule now has one.

- **Syn3A, the proposed minimal-cell track: the evidence audit (14 November 2026, the user's
  request).** This is an assessment only; no engine model ran
  ([note](docs/SYN3A_MINIMAL_CELL_TRACK.md);
  [evidence](/mnt/workspaces/Cells/syn3a-20261114-01/HANDOFF.md)).
  - **15 public resources checked at their primary sources,** and the user's brief's claims
    verified or corrected.
    - Pelletier 2021's data DOI does not resolve.
    - The 2026 membrane archive is molecular dynamics only; its wet-lab data are in the journal's
      source data.
    - The 2024 lipid-diet study used a labelled derivative strain.
  - **79 MB downloaded** into `/mnt/datasets/Cells/syn3a/`, with a manifest per source. The 4D
    model's outputs await the user's approval (D138).
  - **Proposed first milestone:** reconstituted-vesicle permeability, with fitting kept separate
    from prediction. The open questions are the user's.

- **The coupling operator's milestone 3, and Track E's independent references, landed (14
  November 2026).** Validation, tests and docs only, during MG0c's `src/` hold. Tier 1 at the merge
  8b7ad24: 326 files, no changed outcome ([summary](/mnt/workspaces/Cells/independent-references-20261114-01/land-gate1-8b7ad241/summary.json)).
  - **`species_regulated_availability@1` against the independent references (A4 and A5)**
    ([note](docs/INVENTORY_COUPLING_DESIGN.md) §9;
    [evidence](/mnt/workspaces/Cells/inventory-coupling-m3-20261114-01/HANDOFF.md)).
    - **A4, reciprocal feedback:** two cells, with a contact set by each cell's regulatory state.
      Observed order 2.0 in V, the amounts and U at dt 1 to 0.125 ms, against R-feedback at Radau
      rtol 1e-10. The fast arm gives 1.97–2.00.
    - **A5, a species setting a channel's availability:** order 2.00 in V and the amounts. The
      factor is exact to rounding.
    - **The record** run from a frozen snapshot reproduced the development errors bit for bit.
    - **Disclosed choices**, logged before the record run:
      - A4 starts from the reference's state at 50 ms and sits at the edge of the explicit-rate
        bound;
      - the horizons are 2 s and 1 s;
      - the worlds have no pumps or gated channels.
    - **Not registered:** the proposed 1 ms tolerances (twice the measured error). On this build
      they cannot fail, so they become regression guards. The judged item of the coming PROPOSED
      protocol is the order against the reference, on pairs at least 100 floors above it, with a
      control that breaks the order (the advisor's review).
  - **Track E's references (`validation/excitable/`)** were written by a separate agent that read
    no engine code ([usage](validation/excitable/REFERENCES_USAGE.md);
    [evidence](/mnt/workspaces/Cells/independent-references-20261114-01/HANDOFF.md)).
    - **What they cover:** the single cell with the declared laws and the pump; the passive cable
      and its linear limit; the strong-coupling limit; the chain protocols of the appendix's §8,
      including the mid-chain segment and the 0.01 F/m² cells.
    - **Self-tests:** 16, tier 1. At rtol 1e-11 every observable moves by 1e-11 or less.
    - **The blind check:** the entry-junction voltages at block sites match the engine's to 0.02
      mV, and the coupling-only arm reaches 120.6 mV at s·r_gj = 10, supporting the floor of 20
      (D170).
    - **The ambiguities it flagged in §8.4** go to Track E's appendix: the observation window of
      the far-end S1–S2 interval, the coupling for the capture runs, and APD measured from the
      stimulus end.
  - **The coupling references gained** `jac_sparsity` and `Run.integrate`. Their 44 self-tests
    are unchanged.

- **The visualizer merged into main (14 November 2026, the user's request).** It adds the
  `visualizer` branch's 45 commits, all under `visualizer/`: the three.js viewer with its replay
  and lenses, the run adapter, the planarian protein atlas from public sources, and their tests
  and fixtures. Nothing outside `visualizer/` changed.
  - **Gate:** the tree-scanning guards ran on the merge and passed: D147's drivers, the BETSE
    boundary, J2's bright line, the source-profile boundary, the continuity bypass and the
    source-order tests. That was 62 passed and 31 skipped, the skips being the existing D131 ones.
  - **No full tier gate ran.** The tier runner collects `tests/` only, so the visualizer's own
    tests are outside it.
  - [Log](/mnt/workspaces/Cells/visualizer-merge-20261114/guards.log). The visualizer session
    keeps developing on its branch.

- **Combined landing (14 November 2026):** FR-10's milestone 1, the coupling operator's
  milestone 2 and MG0c's revised protocol. Tier 1 and 2 at the merge f0e154a: 420 files, no
  changed outcome ([summary](/mnt/workspaces/Cells/inventory-coupling-m2-20261114-01/land-gate12-f0e154a0/summary.json)). The coupling operator's two tier-3 files
  passed at the merge ([logs](/mnt/workspaces/Cells/inventory-coupling-m2-20261114-01/land-tier3-f0e154a0-r2)).
  - **FR-10, `scheduled_bath_composition@1`, milestone 1**
    ([note](docs/BATH_SCHEDULE_DESIGN.md) §7;
    [evidence](/mnt/workspaces/Cells/bath-schedule-20261114-01/HANDOFF.md)). Development code;
    its qualification comes later.
    - **The engine models it runs:** the operator in the composite on `resolved_pump_tissue@3`.
    - **What it does:** dose events on the dt grid. The dose, its work and the compensating charge
      are the operator's own records, and the reconciliation term is its own ledger term.
    - **B3:** the energy ledger is at rounding on every row across an event, at most 2.6 ε of the
      flows. The control without the term fails from the first row after the event.
    - **B5:** with no event, a run is bitwise identical to the composition without the operator.
    - **Crossrev:** identical in the five 21fb714 sets.
    - **The staircase probe** (criterion written first):
      - a dose from nothing is admissible as stairs of 100× (six stairs of three face times);
      - a step between resolved levels is admissible at 10×, under ARS at 1 ms and RK4 at 0.1 ms;
      - the limit depends on the step's absolute size as well as its ratio.
    - **Milestone 2:** a definition-time refusal of oversized steps, `check_species_cap` with a
      world above 7 species, and FR-1's milestone 1 continues on the same branch.
  - **`species_regulated_availability@1`, milestone 2** ([note](docs/INVENTORY_COUPLING_DESIGN.md)
    §8; [evidence](/mnt/workspaces/Cells/inventory-coupling-m2-20261114-01/HANDOFF.md)).
    Development code; its qualification comes later.
    - **A2:** frozen input and retention are exact to rounding, and moving inputs converge at
      order 2.00. The crossing record brackets t* at every dt.
    - **A8:** restarts at eight times and snapshot round trips, in process and in a fresh process,
      are bitwise. Windowed runs equal a single scan bitwise.
    - **vmap:** three moving worlds match their own runs within 1e-12.
    - **RK4 ("split"):** the factored path equals the world without the operator, bitwise.
    - **A6:** locality held bitwise.
    - **Compositions:** with replacement@1, injection and D152.
    - **Nine species:** bitwise against every coupling switched off.
    - **The `factors` manifest entry** is omitted when empty. 58 of 67 crossrev field maps are
      byte-identical; the other 9 differ by that key only.
    - **Crossrev:** identical in all seven sets against main da94f81.
    - **The parser** moved into `species_common` in its own commit.
    - **Next, milestone 3:** A4 and A5 against the independent references, with A4's tolerance
      measured against the reference's floor on the engine's own world and registered before its
      judged run.
  - **MG0c (D152), the protocol revised after the lead's review, still PROPOSED**
    ([protocol](validation/morphogenesis/protocols/mg0c_turing_v1.json);
    [evidence](/mnt/workspaces/Cells/shared-inventory-reactions-v1-20261114-01/HANDOFF.md)).
    - It has 55 judged criteria and 165 registered control deltas. Every criterion a
      development run can evaluate passes.
    - The rulings applied:
      - Q7 as a batch of seeds;
      - the linearised map judged at 50 ms with an exact-propagator control;
      - controls kept by parameter at 10× their smallest caught δ, with 25 decaying-mode controls
        removed with reasons;
      - the amplitude defined as max |u − mean u| at 3000 s (0.432 c*);
      - D150's amendments carried over.
    - **Disclosed:** the 1e-2 control cutoff was set after the mode sensitivities were known, and
      the development runs predate FR-9.
    - **Next:** the rehearsal on main (CPUs 5 and 7, about 2.5 h), the final check, registration
      and one judged run. `src/` landings are held from the rehearsal to registration.

- **Track E (excitable tissue, D155): the design note accepted narrowly, for M1 and M2 on @3
  (D170, 14 November 2026)** ([note](docs/EXCITABLE_TISSUE_DESIGN.md);
  [evidence](/mnt/workspaces/Cells/excitable-tissue-20261114-01/HANDOFF.md)).
  - **Engine model run:** `resolved_pump_tissue@3`, with its five channel laws, the
    constant-field leaks and junctions, the pump and the junction gate.
  - **Probe 2 failed S1 as registered at 0.05 F/m²:** every perturbed segment blocked. So the
    acceptance condition, one cheap probe, failed.
  - **The acceptance rests on amendment 4** at candidate A (0.01 F/m²), which is post hoc but
    was written before its runs. S1–S4 were met.
    - Segment delays were 1.08–2.02 times the control, with block at combined 0.02 and 0.01.
    - Refinement was identical at 5 and 2.5 µs, and the energy residual at most 2.1e-4.
  - **The limits:**
    - the channel laws' +60 mV domain, against A's +56.65 mV at the chain's end cell;
    - the junction gate law's 120 mV domain at block sites (118.1 mV at s·r_gj = 10), so the floor
      s·r_gj ≥ 20 is provisional. The independent reference's junction voltages, computed
      blind, match the engine's to 0.02 mV, and it finds 10 unsafe in the coupling-only arm
      (120.6 mV);
    - `junction_ungated@1` named for the inner-model note.
  - **Landed:** the note, its equations appendix and the probe driver
    (`validation/tissue/excitable_probe.py`). Tier 1 at the merge 7bbda57: 323 files, no
    changed outcome ([summary](/mnt/workspaces/Cells/excitable-tissue-20261114-01/tiers/land-gate1-7bbda575/summary.json)).
  - **Next:** M1, when a slot frees. Its first development runs are the sheet's block-site
    voltages, the block threshold and the peaks at lightly loaded cells, with B's segment run as
    the fallback's evidence.

- **Track R's independent references landed (14 November 2026)** in `validation/coupling/`.
  They are R-fac, R-state, R-cell and R-feedback, written by a separate agent that read no engine
  code ([usage](validation/coupling/REFERENCES_USAGE.md);
  [evidence](/mnt/workspaces/Cells/independent-references-20261114-01/HANDOFF.md)).
  - **What they cover:** every factor law, side and basal combination; the two-state regulatory
    fraction (closed forms, adaptive integration, the crossing time t*); one cell with a gated
    K leak; and two cells whose shared junction is set by each cell's own regulatory state,
    integrated with the ions by Radau.
  - **Conventions:** reconciled with the coupling note's §7, the milestone 1 as built. Every
    engine-facing convention is an explicit input whose default is the as-built one.
  - **The floor** at the recommended settings (Radau, rtol 1e-10) against rtol 1e-12: s about
    2e-12, amounts about 2e-12 fmol, V ≤ 1.5e-12 V. `rc.floor` measures it on the engine's own
    world, where A4's tolerance is to be pinned.
  - **Self-tests:** `tests/unit/test_coupling_references.py`, 44 passed, tier 1, including a
    no-`cells`-import check; J2 still passes.
  - **Landing:** tier 1 at the merge 9d6b1bc, 323 files, no changed outcome
    ([summary](/mnt/workspaces/Cells/independent-references-20261114-01/tiers-r/land-gate1-9d6b1bcb/summary.json)).
- **The crossrev baseline of record is renewed at da94f81** (D148 criterion 4 for FR-9). All
  seven sets are identical to their earlier records: base, qualification, injection, volume and
  division against baseline-21fb714; species against b102da4; reactions against 5de1c96.
  Species and reactions are now records of their own, and the earlier records stay
  ([records](/mnt/workspaces/Cells/architecture-block-20261114-01/baseline-da94f81/)).

- **The architecture block's first items landed (14 November 2026):** D147 for composite
  definitions, the J2 bright line restored, and FR-9's species cap raised to 16 (D165)
  ([evidence](/mnt/workspaces/Cells/architecture-block-20261114-01/HANDOFF.md)).
  - **D147 for composites (D156):** a composite follows its inner model's field-solver policy.
    - It is enforced without changing `src`, since `declare()` would change no guard and no
      registered program.
    - It adds an operator-bearing case with free offsets, and the claim is narrowed to what was
      probed.
    - Tests: `test_field_solver_composite` (tier 1) and its runs (tier 2), and
      `test_field_solver_enforcement` (76 tests, tier 1).
  - **J2, found by the earlier D147 landing gate:** the enforcement test imported S3's cleft egg, a
    J1 source, beside partition sources. The cleft egg moved to its own module, with no exemption.
    J2: 27 passed.
  - **FR-9 / D165:** `species_common.MAX_SPECIES` from 7 to 16, a D148 in-place change to D150's
    shared code. The criteria and the stop rule were written first, in D150 §13.
    - Tier 1, `test_species_cap.py`: the cap admits a nine-species charged world. On its layout
      NumPy's pairwise order differs from the explicit species-order sum the ledgers use, and the
      explicit sum equals the compiled one bitwise.
    - Tier 2, `test_species_cap_runs.py`: 20 steps, with every host check on every accepted row.
      NumPy's order differs on 17 of 21 rows; explicit equals compiled on all.
    - The three refusal tests refuse 17 and admit 16. The coupling operator's cap test was updated
      at the merge.
    - D150's claim 3 stays reported. Worlds above 7 species are outside D150's judged scope, and
      above 16 needs another probe.
    - **Deviation, accepted:** D165 asked for a tier-1 guard world. The runner world is in tier 2,
      since compilation alone takes about 15 s.
  - **Gates:**
    - crossrev from a clean snapshot of a6d65bf: identical in all seven sets (base, qualification,
      injection, volume, division, species, reactions);
    - tier 1 and 2 at 44a164b: 403 files, no changed outcome;
    - tier 1 and 2 at the landing merge 2161f39: 414 files, no changed outcome
      ([summary](/mnt/workspaces/Cells/architecture-block-20261114-01/tiers/land-gate12-2161f396/summary.json)).
  - **Next:** the crossrev baseline renewed at the landing commit (D148 criterion 4), with records
    of their own for species and reactions; the operator matrix; the phase records; D154's writer
    note.

- **The coupling operator `species_regulated_availability@1` (D155/D156): milestone 1 landed
  (14 November).** This is development code; its qualification comes later
  ([note](docs/INVENTORY_COUPLING_DESIGN.md) §7;
  [evidence](/mnt/workspaces/Cells/inventory-coupling-v1-20261114-01/HANDOFF.md)).
  - **What landed:**
    - the operator and every refusal in §1.11;
    - the neutral Hill helper (`processes/hill_factors.py`), which matches D152's rates bit for bit
      on the host;
    - the junction and channel targets (CONTROL_FACTORS "junction" and "channel");
    - FR-6's per-cell prior condition (a per-cell `initial`, and writes at t = 0).
  - **The bitwise checks** on the seven-cell heredity sheet, over every @3 state field and every
    observation column:
    - M1: a factor equals the same availability scheduled, on junctions.
    - P1: the same on channels, at 1/2, 0 and 1. So the channel target is accepted into scope.
    - A3: identity, zero and multiple factors.
    - Idleness against the world without the operator.
  - **Crossrev:** main against the branch in all seven sets (base, qualification, injection,
    volume, division, species, reactions): identical.
  - **Landing:**
    - tier 1 and 2 at fbcec48: 407 files, no changed outcome;
    - tier 1 after merging main, at 9eafe05: 318 files, no changed outcome;
    - the eight new test files in the tier record: two in tier 1, six in tier 2.
  - **Next, milestone 2,** in progress: the regulatory state compiled; restart and windows; batches;
    compositions; the factors manifest entry; A4 and A5 against the independent references, which
    are being written.

- **Checkpoint continuity's GPU extension of case 1 landed (D153, design §13.4; 14 November).** GPU
  definitions are now admitted through the CPU-host probe, with `execution_device` patched, and the
  admission record notes the patch
  ([evidence](/mnt/workspaces/Cells/checkpoint-continuity-20261113-01/impl/gpu-ext/)).
  - **The code:** `src/cells/continuity.py`, which is host-only, with the probe, admission and
    verification tools.
    - A patched record also requires the probe's `jaxlib` to equal the resuming runtime's.
    - The `to` runtime is the checkpoint's own, checked exactly on the GPU host.
  - **A real L4 checkpoint:**
    - It was admitted on the CPU host: P, B and H identical, the cuda module identical (1,799,725
      characters).
    - It then resumed on the L4 for its remaining four rounds, through a replacement event.
    - The GPU-host loader checked the runtime and `jaxlib` exactly. Copies of the record with
      `jaxlib` or the GPU platform version changed were refused.
    - `verify_run` passed 17 of 17 checks, after a stand-in `inputs.json` for the probe's origin.
      That is a limit for checkpoints written outside `dev_run.py`, noted as a follow-up.
  - **Gates.**
    - Crossrev identical in all five sets.
    - Tier 1 and 2 at 266f5f1: 398 files, no changed outcome.
    - Tier 1 after merging main, at 0644752: 316 files, no changed outcome.
    - The new `test_continuity_gpu.py` (14 tests, 22.8 s) is added to the tier record at landing.
      It had been run by the agent, not by the gates.
- **The composite's L4 judged run C (14 November): W1 and W2 pass; G2-Q1 passes Q1–Q6 and fails Q7.**
  C ran once on the L4 under the GPU lock, from a clean snapshot of main at 265ed66, against the
  three registered backend variants. Every definition declared the GPU (117 min of GPU; nothing was
  refused or killed) ([evidence](/mnt/workspaces/Cells/composite-l4-agreement-20261114-01/c/)).
  - **W1:** 25 of 25 items pass. **W2:** 24 of 24 pass.
  - **G2-Q1:** Q1–Q6 pass. **Q7 fails.** Q7 judges replacement with no events against
    `resolved_pump_tissue@3` bitwise on the 825-node tissue. On the L4, almost every state field
    and diagnostic differs.
  - **The deviation reports:** |A − C| is 0 on every judged quantity of W1 (25), W2 (72) and G2
    (18). C reproduced the repeats A, B and D exactly.
  - **The diagnosis (development evidence, not judged):** one process ran two plain `@3` runs and
    one replacement run, which gives no terms under the three-repeat rule.
    - `@3` against `@3`, the identical program, already differs bitwise: 17 of 22 state fields, up
      to 1.6e-11 relative.
    - Replacement against `@3` shows the same scatter, the same fields at the same sizes.
    - So the failure is the L4's own nondeterminism at 825 nodes. Nothing in it is attributable to
      the wrapper at this resolution.
    - Three rounding-level residual diagnostics differ by up to 2.8× their own size.
  - **A process finding.** The variant carried an item with no tolerance site (Q7 is bitwise) on a
    world where the plan already said L4 repeats are not bitwise. So the variant method could not
    widen it.
  - **Status of the composition gate's GPU condition:** met for water (W1, W2) and for
    replacement's Q1–Q6; **open for Q7.**
  - **Next.**
    - In the next L4 gap (about 5 min, never applied to the hold, whose snapshots check the XLA
      flags), test whether this jaxlib has a deterministic execution setting under which `@3`
      repeats bitwise at 825 nodes across processes. If it does, Q7 is judged as registered.
    - Otherwise, a tolerance-based Q7 would be a new item, not a variant. It would need a judge
      change and its own rule, registered after attribution and labelled weaker evidence: repeats
      in separate processes with all pairs, per-field scales, residual diagnostics against their
      own bounds, and a planted wrapper effect as a judged control. Whether to allow it is the
      user's call (D148's last clause, by analogy).

- **D152 v1 milestone 3 landed: MG0c's driver, its development runs and a PROPOSED protocol
  (14 November).** Not registered, and no judged run
  ([protocol](validation/morphogenesis/protocols/mg0c_turing_v1.json); design §11.3;
  [evidence](/mnt/workspaces/Cells/shared-inventory-reactions-v1-20261114-01/HANDOFF.md)).
  - **The D147 check, before drafting:** every MG0c world has 0 free field offsets and declares
    @2, so the composite gap (D156) does not touch it.
  - **The compiled composition:** a face-free composition of D150's export with the reactions,
    plus turnover on a read row, replacement@1 with outside routes, and @3's faces.
    - Transport and reactions see the same material: it equals the split map to 3.9e-15, and is
      second order against the coupled exact solution.
    - Supply is counted once across writers, to at most 1.1e-16 of scale.
    - A rejected step restores every field bitwise, every writer's accumulators included.
    - Restart and batching are bitwise.
  - **The moved guards:**
    - §3.4 guard 2: the engine matches `strang_mode_map` at 0.008–0.021 of its rule, second
      order against exact;
    - idle claim 3: ion rows bitwise with the network active;
    - several sites with different multipliers, against the references.
  - **MG0c development runs** (Schnakenberg on zero-flux chains):
    - Q1: mode propagation, second order (ratios 3.98–4.55), with the dt rule at 0.44–0.46;
    - Q2: the no-mode domain decays at the predicted rate;
    - Q3: dominant modes 1, 2 and 3 on L/ℓ = 6, 11 and 16;
    - Q4: all 53 lengths match the discrete argmax;
    - Q5: every subcritical mode decays;
    - Q6: the nonlinear pattern against the SciPy integration, order 2.005;
    - Q7: the face-free world at 0.052 of rounding.
  - **The PROPOSED protocol** has 52 criteria and 76 registered control deltas. Its ten questions
    are for the lead's review with the advisor. The findings include that a batch of the domains
    cannot run, since the route node is in the batch signature; a batch of seeds on one domain is
    proposed.
  - **Landing:** tier 1 at the merge 4a689a9, 316 files, no changed outcome. No `src/` change since
    milestone 2.

- **The inventory-coupling design (D155 item 1, scoped by D156) is accepted (14 November).** The
  lead, with the advisor; docs only ([note](docs/INVENTORY_COUPLING_DESIGN.md), rulings in §6.3;
  [evidence](/mnt/workspaces/Cells/inventory-coupling-20261114-01/HANDOFF.md)).
  - **The operator.** `species_regulated_availability@1` sets factors on @3's junction
    availability; the channel target is pending its milestone 1.
    - Factors read concentration from @3's own amount rows, with a basal level, F ∈ [b, 1].
    - Ion sources enter only through a two-state regulatory state, whose half-steps read the ion
      before and after @3's step.
    - dt·(k_on + k_off) > 1 is refused at the definition.
  - **Checked in the code:** the effective control is computed once per step and held through
    @3's stages, as the external review said.
  - **Routing to other operators' controls and the event trigger** are named doors. Newborn
    integration comes in four named steps, after a reusable contact-maturation process.
  - **The 7-species cap probe (W4)**, read-only, from a clean snapshot at f7f0592:
    - The cap can rise to 16. Up to 16 species, in every composition D150 and D152 admit, no
      ledger, guard or promised idleness depends on NumPy's sum order. Every ledger sum is
      species-ordered.
    - Host and device checks, the face-free energy world, batches, restart and idleness hold at
      16.
    - D150's unpromised claim 3 departs at rounding in a 12-species chain, so it stays reported.
    - Raising the cap is a D148 change to `species_common`, with a guard world of 8 or more
      species, when a consumer needs it.

- **The composite's L4 agreement under the three-repeat rule: the variants are registered and C is
  next (14 November).** This ran in the L4 gap after hold segment 2, one GPU process at a time under a
  GPU lock ([evidence](/mnt/workspaces/Cells/composite-l4-agreement-20261114-01/)).
  - **The kernel profile (19.9 min on the L4).** On the GPU the narrow hypothesis holds: four
    kernel classes take 79% (E07) and 78% (hold) of device time at 6 worlds, and 53% at 256.
    - At 6 worlds most of a step is cuBLAS's batched triangular solve applied to single vectors.
      Cholesky is 11% at 6 worlds and 25% at 256.
    - On CPU it failed narrowly, at 45%.
  - **A blocker found and fixed before the runs.** The registered W1, W2 and G2 definitions declare
    `backend: cpu`, so an "L4" run would have computed on the CPU. The driver and the three judges
    gained `--backend gpu`, which sets the backend on a copy and leaves the default unchanged.
  - **The repeats A, B and D:** 101 min of GPU in total. All exited 0, and nothing was refused or
    killed.
    - The backend terms are at most 4.2e-14 V and 2.8e-14 fmol.
    - The run-to-run term is exactly 0: the three L4 repeats are bitwise identical on every judged
      quantity, unlike the hold's 825-node windows.
    - No stop rule fired. Tolerances widened only by rounding to one significant figure, by at
      most ×1.315.
  - **Registration.** The lead registered the three variants in the repo,
    `validation/tissue/l4_variants/`. Each is accepted by the judges' own check as a registered
    backend variant of its base protocol.
  - **Two of the external review's claims, checked read-only.**
    - The effective control is computed once per step and held through @3's stages (Track R's
      note).
    - The field refresh always computes new arrays before selecting, about 2 to 2k+3 times a step,
      by design under vmap. That is why the 64-node cap exists.
  - **Landing:** tier 1 at 322a0fa, 315 files, no changed outcome. No `src/` change.
  - **Next:** judged run C on the L4, about 1.6 h, then the deviation reports, then hold segment 3.

- **Secreted-species transport (D150 v1) is numerically qualified: every item of its registered
  protocol passed (14 November).** It was judged once, in series, from one fresh clean snapshot of
  main at f7f0592, whose in-scope content is the registration commit's. The lead launched each unit
  after checking headroom; there were no infrastructure endings and no refused arm
  ([verdict](/mnt/workspaces/Cells/secreted-species-v1-20261114-01/judged-f7f0592/combined/verdict.json)).
  - **Q1, against the exact finite-volume solution:** pass.
    - IMEX worst 0.468 of tolerance under the dt study, and 0.368 under the a priori splitting
      bound.
    - RK4 0.449 and 0.335.
    - The k and D controls are caught at 13.0–79.2× tolerance at their registered δ.
  - **Q2, against the continuum closed form** (the coarse shells, the amount, both supplies and
    the clearance): pass, worst 0.443–0.465. The planar-face control fails every quantity, at 28–248×.
  - **Q3, the orders:** pass. Every stop rule holds; space about 1.92 and time about 2.0.
  - **Q5, the guards of record:** all eight files pass, with the counts on record.
  - **Reported, not judged:** Q4 (Danckwerts, under the resolved-start rule), and the step map's
    agreement at 0.0055 (IMEX) and 0.095 (RK4) of its bound.
  - **Times and peaks:** judge 512 s, judge-q5 913 s, combine 1 s; peaks 1.79, 2.12 and 0.08 GB.
    memory.events was 0 throughout.
  - **Scope, as the qualified statement carries it:** @3's faces with exact radial conductances,
    and turnover's first-order clearance, with a held-bath source, in the composite.
    Exchange, turnover's production and the occupant rule entered only through Q5's test files.
  - **Tag:** `secreted-species-v1-qualified-2026-11-14`.

- **The secreted-species (D150 v1) protocol is registered (14 November).** The lead registered it
  after check 1 and the D147 check. No judged run had been made before registration
  ([evidence](/mnt/workspaces/Cells/secreted-species-v1-20261114-01/dryrun-1456a08/)).
  - **Check 1:** judge, judge-q5 and combine ran on a registered dry-run copy from a clean snapshot
    of main at 1456a08, with D152's operator included. All passed. 0 of 3,282 leaves differ from
    the earlier dry run, excluding wall times and source pointers.
  - **The D147 check:** `free_field_offsets` is 0 for all eight arms. They are composite
    definitions declaring field solver @2, which D147's automatic choice would keep, so the
    composite gap (D156) does not touch this run.
  - **Registration.** It was made through the generator (`register`). The leaf diff against
    1456a08's protocol shows the status changed and the 8-leaf registration record added, with
    nothing else touched. The guard now reads the record.
  - **Landing.**
    - Tier 1 at the registration commit f2785cb: 314 files, no changed outcome.
    - The merge 90cf2fd differs from f2785cb only in documentation (DECISIONS, CURRENT_PLAN,
      PROGRESS, the review notes and the paper reviews), so that gate stands.
  - **Next:** one fresh clean snapshot of main at 90cf2fd's landed commit, then judge, judge-q5
    and combine once each. The lead launches each unit after checking the slice's headroom
    (`rules.timing`).

- **The secreted-species protocol's rehearsal on main, and its final pre-registration amendments
  (14 November).** The protocol is still PROPOSED, with no judged run
  ([evidence](/mnt/workspaces/Cells/secreted-species-v1-20261114-01/HANDOFF.md): `rehearsal-6f339ab/`,
  `dryrun-0353b29/`).
  - **The rehearsal, from a clean snapshot of main at 6f339ab.**
    - All five crossrev sets and the species set are identical.
    - The development pipeline reproduced every frozen number bitwise: 1,212 protocol leaves,
      2,256 analysis leaves and 2,480 arm-record leaves.
    - A dry run of the Q1–Q3 judge on a registered copy passed every item and caught every
      control.
  - **Amendments before registration.**
    - A Q5 entry (`judge-q5`) and a `combine` entry now write one qualification verdict holding
      every item, the scope, the snapshot's revision and the unjudged step-map ratios.
    - The attempt rule counts a harness timeout, a runtime-limit kill or a Q5 file ended by a
      signal as an infrastructure ending, rerun once.
    - `rules.timing` sets runtime limits of about 3× the rehearsal's times. The judged units run
      without `--wait-headroom`: the lead launches each only when the slice has about 3 GB free.
    - Every judge entry was dry-run to a pass on a registered copy (judge 310 s, judge-q5 772 s,
      combine 0 s).
  - **Landing:** tier 1 at the merge 0698713: 314 files, no changed outcome. The tier-2 step-map
    guard passed 2 of 2.
  - **Next:** the advisor's check 1, which reruns judge, judge-q5 and combine on a registered
    dry-run copy from a clean snapshot of this main and compares them leaf by leaf with
    `dryrun-0353b29`. Then registration, through the generator, as a status-only change.

- **Reactions on the shared inventory (D152 v1): `local_species_reactions@1`, milestones 1 and 2,
  landed (14 November).** This is development code, with no judged run; MG0c's qualification is
  milestone 3 ([note](docs/SHARED_INVENTORY_REACTIONS_DESIGN.md) §11;
  [evidence](/mnt/workspaces/Cells/shared-inventory-reactions-v1-20261114-01/HANDOFF.md)).
  - **What landed.**
    - The operator and its declaration parser, with every refusal the note lists.
    - The contract parts, including the standard-potential term the operator owns.
    - The laws: mass action of orders 0–3, Michaelis–Menten with or without a catalyst, passive
      detailed balance, and Hill factors.
    - SSPRK(3,3) half-steps under the stage condition at θ = 1/2. dt·L > 1 is refused.
    - Exact ΔG bookings, the per-step node class, and the mixed-node hybrid.
  - **Against the independent references** (run through their usage note only):
    - the per-law ΔG test of record agrees within the references' tolerances over 4 world
      variants × 60 trials, with every law, class and branch reached;
    - whole compiled face-free runs agree to ≤ 7e-15 in amounts and ≤ 2.5e-16 of scale in
      energies;
    - the development figures are reproduced: the share at onset +0.33% in the first half-step,
      the background guard −6.32e-5 against the true −6.27e-5, and the reversal onset 5.4–5.6×
      at a 1e-12 mM trace.
  - **Guards.**
    - The face-free energy world stays within 0.26 of the rounding allowance on every booking
      path, and its three negative controls fail at the first row they touch.
    - C2: the shared bound is 0.35× the booking at µM and 409× at nM.
    - Benign padding: no NaN or infinity anywhere.
    - Identical programs across parameter twins. The batch signature refuses different
      structures.
    - Idleness is bitwise against the live half-step. Restart is bitwise, including through a
      snapshot.
    - Vector batches are bitwise against their reverse.
    - dt·L = 0.98 is admitted and 1.02 refused, with the state kept bitwise.
  - **Crossrev of record:** all five sets and D150's species set are identical. The reactions set
    has its first record.
  - **Landing checks.**
    - Tier 1 and 2 at the merge a4e2f7e: 397 files, no changed outcome.
    - D152's three tier-3 files pass: runs 6, guards 14, reference runs 18.
  - **For milestone 3:**
    - §3.4 guard 2, the transport world with the network;
    - a compiled composition with another writer;
    - idle claim 3, reported;
    - multi-site runs;
    - MG0c's driver and a PROPOSED protocol.

- **The checkpoint-continuity GPU probe (design §13.4): every question identical (14 November).** It
  ran in the L4 gap after hold segment 2 ended, as one GPU process under the GPU lock (about
  2 min, peak 1.5 GB), then the CPU part on CPU 3, from the frozen source `source-s1-e8cdda0`
  ([evidence](/mnt/workspaces/Cells/checkpoint-continuity-20261113-01/impl/gpu-probe/out/):
  `compare.json`, `queue.log`).
  1. A GPU cohort traces identically in two GPU-host processes: P0, P, B and H.
  2. A CPU-host trace, with `execution_device` patched, equals the GPU host's jaxprs, constants,
     bindings and host replay.
  3. The cross-lowered `cuda` StableHLO equals the GPU host's own lowering (1,799,725
     characters, identical).
  4. The overlap repeats bitwise on the CPU for a GPU definition.
  - **The decision §13.4 registered:** GPU definitions are probed on the CPU host and use no
    GPU time; the record notes the patch. This unblocks the GPU extension of case 1, which is
    to be built next.

- **E07-v1 follow-ups (14 November).** Both are descriptive or development work, and no verdict or
  class changed ([readout](/mnt/workspaces/Cells/e07-v1-judged-20261113-01/loss-positions.json),
  [1 ms check](/mnt/workspaces/Cells/e07-v1-dtcheck-20261114-01/HANDOFF.md)).
  - **Where losses sat,** over all 16 inheritance runs with any loss:
    - Of the 41 lost D copies, 33 were strays outside the disc, 8 sat on the rim, and none was
      interior.
    - Of the 21 lost founders, 20 were rim cells and 1 interior.
    - The erosion and small-bias classes therefore mix trimming of strays, which raises J, with
      rim erosion, which lowers it. Fast k3 s 1.0 seed 1 (ΔJ +0.044) is pure trimming.
  - **The s 1.0 control's collective falls at 1 ms.**
    - The same cells fell at the same records as at 5 ms: 6 at 436 s, 6 at 512 s and 2 at 514 s
      at 2 s resolution.
    - The D sets were identical at all 61 records, with |ΔVm| ≤ 0.21 µV.
    - A 5 ms rerun reproduced the judged run bitwise.
    - The falls are not a step-size artefact. It is still one run.
  - **The E07-v2 note** (still PROPOSED) carries the review fixes:
    - §2 leads with the pattern's fate;
    - fresh against long-held has its matched variables named, with a prediction;
    - 1-D chain screens come before the lesion arms only.
    - Its three questions are with the user.
  - **Landing.** The D147 guard exempts the two new scripts, with reasons: one is THRESHOLD_V
    only, and the other builds through e07_v1_run.build, which declares the solver. Tier 1 at
    23c979f: 310 files, no changed outcome.

- **Secreted-species v1 (D150), milestone 3 landed: the qualification protocol, PROPOSED
  (14 November).** It is not registered, and no judged run has been made
  ([protocol](validation/tissue/secreted_species_protocol.json); design §12.2;
  [evidence](/mnt/workspaces/Cells/secreted-species-v1-20261114-01/HANDOFF.md)).
  - **Scope.** The protocol judges @3's faces, with exact radial-shell conductances, and turnover's
    first-order clearance around a held-bath source: the held sphere with decay.
    - Q1: against the exact discrete solution, on the IMEX and RK4 arms. Two rules: the dt study,
      and an a priori bound by the splitting's leading term.
    - Q2: against the continuum closed form.
    - Q3: the observed orders, judged by stop rules only.
    - Q5: the guards of record, which are the RK4 face heat and the per-law ΔG tests, plus the
      runs, ions, definitions and refusal test files.
    - Exchange, production and the occupant rule enter only through Q5's test files.
  - **Judged controls.**
    - k and D put in error at a registered δ per rule and arm. In development every one was
      caught, at 13–79 times tolerance.
    - The planar-face arm against Q2. It fails at 28–248 times.
  - **Development.**
    - All eight arms pass every host check.
    - Q1 on IMEX reaches 0.47 of tolerance under the dt study and 0.37 under the splitting term;
      on RK4, 0.45 and 0.34.
    - Q2 reaches 0.44–0.47. The orders are 1.92–1.93 in space and 2.00–2.09 in time.
    - Pass fractions near 4/9 are structural for a second-order scheme; the controls are what
      show the test can fail.
    - The first-shell error equals the step map's fixed point to 5.8e-4 (reported).
  - **The review (the lead, with the advisor).**
    - Q1's claim is reworded to an a priori bound.
    - The controls are judged, and the scope is stated.
    - R-continuum is checked against the PDE itself: a fourth-order residual, both boundary
      conditions and the start.
    - The step map's agreement stays a tier-2 regression guard, not a judged item.
  - **Found and fixed in development.**
    - A radial-builder regrouping moved bindings by up to 5 ulp. The species crossrev caught it.
    - A refusal test would have failed once the protocol was registered.
  - **Landing:** tier 1 at the merge 780f5d9 310 files, no changed outcome; the new tier-2 step-map guard
    2 passed.
  - **Next:**
    - a rehearsal on main: all five crossrev sets and the species set from a clean snapshot, and
      a dry run of every judge entry;
    - the lead's final check with the advisor;
    - registration, then one judged run.

- **D152's independent references landed (14 November).** An agent that never read the operator's
  code or the design's prototype wrote them from the note's Appendix A and §6
  ([usage](validation/reactions/REFERENCES_USAGE.md);
  [evidence](/mnt/workspaces/Cells/reaction-references-20261114-01/), with the run of record
  `crosschecks-3/` at 5fd695b).
  - **What they are.**
    - The node kinetics and bookings: the SSPRK(3,3) half-step and its stage condition, the exact
      ΔG in floats and in 50-digit Decimal, the per-step node class and the mixed-node hybrid.
    - The exact dissipation integral (DOP853).
    - Closed-form linear reaction–diffusion on zero-flux chains.
    - MG0c's Turing references: the dispersion relation, the discrete mode propagators and the
      semi-discrete nonlinear integration.
  - **Independent reproduction.** Every fully specified development number in the design:
    - probes 2c, 2d, 2e/2f and 2g in every cell;
    - §6.4: d_c 8.5676, the band (0.2, 0.5), σ_max 0.05719, the domain table and the staircase.
  - **The tolerance basis.** Against a second float implementation, end amounts agree within
    4.7 ε. ΔG is within 1.06 ε of the 50-digit value, and mixed-node H within 0.38 ε of its terms'
    scale.
  - **Corrections to the note it found,** to be made through the engine branch's amendments:
    - the trace-sensitivity figures are relative changes of the whole heat, not pJ;
    - k̃² at σ_max is 0.3185;
    - Appendix A's RT uses R = 8.314; the references take RT as an input;
    - Q4's "both gaps" needs L/ℓ = 4 in the sweep.
  - **Checks.**
    - 44 self-tests in 5.8 s, tier 1, including a static check that the references import
      nothing from `cells`.
    - Tier 1 at the merge db8111b: 308 files, no changed outcome.
    - The tier record's merge conflict was resolved with the tier tool, re-measured on main's
      record.

- **E07-v1 judged (13–14 November): under donor-copy turnover the written disc did not renew.
  The pattern followed neutral copying closely, and 8 of 15 scored predictions held.**
  - **How it ran.** All 38 judged runs ran once each, from one clean snapshot of main at 4465b48,
    after the E1 numerics gate passed at 5 ms (|ΔVm| ≤ 5.7 µV). Every unit exited 0, and no E07
    process was killed. Scoring used the frozen scorer
    (`validation/tissue/e07_v1_score.py` at 6b6912b), covering 38 of 38 runs with every
    cross-check true
    ([evidence](/mnt/workspaces/Cells/e07-v1-judged-20261113-01/): `summary.json`,
    `scores.json`, `runs/*/seed*/outcome.json`, HANDOFF.md).
  - **The pattern's fate.** The renewal criterion B1 (J ≥ 0.8 through full founder turnover)
    was false in all 20 fast k1 runs and all 6 (b) runs, as predicted.
    - J at the judged record was 0.25–0.65 in fast k1, 0.49–0.59 in central k1 at 1.7
      turnovers, and 0.65–0.78 in fast k3 after one turnover.
    - The paired copy-only null gives similar values: in the whole-sheet fast k1 37-cell disc
      world, a median J of 0.50 (5–95%: 0.35–0.66) and P(B1) = 0.
  - **The deviation from neutral copying was far smaller than predicted.**
    - In all 30 inheritance runs (a), J was within about ±0.06 of its paired null (ΔJ −0.031 to
      +0.059). At s 1.0 the predicted range was −0.35 to −0.05.
    - At k1 with s 0.3 and 0.6, ΔJ was 0 in all but one run, with the D–H junction weight about
      0.02 of nominal.
    - 41 of 1,827 D copies were lost, which neutral copying cannot do. That makes the classes
      small bias and erosion at s 1.0 and in fast k3: erosion 3/3 at fast k3 s 1.0 and small
      bias 3/3 at s 0.6.
    - Several of those runs have ΔJ > 0, up to +0.044, so where the lost copies sat is not yet
      established. A descriptive readout is pending, and no mechanism is claimed.
    - 3 of 4,853 H copies converted to D, where none was predicted.
  - **The s 1.0 control.** With disc donors only, it lost 14 of 37 founders in two collective
    falls at the rim (6 at 440 s, 8 at 520 s); J was 0.784 at the judged record, minimum 0.649.
    The prediction was J ≥ 0.9 with no collective loss, at low confidence.
    - This is one run, at 5 ms. E1's segments did not cover it, so a 1 ms development check is
      pending.
    - At s 0.6 the control held J = 1 throughout.
  - **Naive isolated templates (b).** The sheet went all H within about one turnover at every τ
    from 40 to 300 s.
    - At s 0.6, recruitment of interior newcomers with five or more D neighbours fell with τ as
      predicted: 9/11, 5/10 and 1/7.
    - At s 1.0, conversions continued at 120 s and 300 s, beyond the predicted early-only
      recruitment.
    - tau* was 300 s at both s, a single draw.
  - **The verdicts.**
    - **Held (8 of 15):** E1; E3 at fast k1 s 0.3 and s 0.6; E4 at s 0.6; E5 at s 0.6; E6;
      validity; B1.
    - **Failed (7):** E3 at fast k1 s 1.0, central k1, fast k3 s 1.0, fast k3 s 0.6, and
      recruitment; E4 at s 1.0; E5 at s 1.0.
    - The design's §7 lists 14 rows; the scorer scores E4's two couplings separately.
  - **Disclosures** (HANDOFF):
    1. The verdicts rest on the scorer's ten readings. The lead accepted them before any
       outcome existed (17:41–17:55 UTC on 13 November, with no outcome on disk).
    2. The scored tau* follows E5's item, counting any converted interior newcomer. The
       driver's five-or-more-D count is supplementary; both give 300 s.
    3. E6's tolerances were set with the seed-101 dry-run values in view. Its A check tests the
       law's quoted constants, not the engine.
    4. Scoring ran from a scoring snapshot (1bfe041) and the loss readout from b351931. Both
       hold the execution snapshot's driver unchanged, with added files only.
    5. A few short jobs ran outside the CPU rule: a few seconds at nice 19, a once-a-minute
       poll, and dry runs on CPU 1.
    6. CPU 2's queue ran 2.6 h slower than CPU 3's, for an unestablished cause. This affects
       cost estimates only.
    7. The watcher restarted twice; no run was affected.
  - **Landing checks.**
    - Tier 1 at the merge f544ccc: 307 files. One outcome changed: `test_d147_drivers.py`.
    - That static guard flagged the three new scripts for importing `heredity_pilot` without
      declaring the field solver. The scorer and the loss readout import only `THRESHOLD_V`, and
      the challenge-build check builds held-bath sheets only.
    - They were added to its EXEMPT list with those reasons, as the guard provides; the frozen
      scorer is untouched. The file then passed 11 of 11, as recorded.
  - **Also landed.**
    - The scorer's tests.
    - The descriptive E4 loss readout (`validation/tissue/e07_v1_losses.py`), written after the
      outcomes; it scores nothing.
    - The E07-v2 challenge build check: four pairings admitted at definition time, nothing
      stepped.
    - The **PROPOSED** E07-v2 note ([E07_V2_DESIGN.md](docs/E07_V2_DESIGN.md)), for the lead's
      review with the advisor; nothing registered.

- **Secreted-species transport v1 (D150): milestones 1 and 2 landed (14 November).** This is
  development code; nothing is judged yet
  ([evidence](/mnt/workspaces/Cells/secreted-species-v1-20261114-01/HANDOFF.md); design §12 and
  §12.1).
  - **What landed.**
    - The operators `scheduled_species_turnover@1` and `scheduled_species_exchange@1`, and the
      inventory-species helper.
    - Two additive adapter functions for @3's per-species chemical term. No existing function
      changed.
    - A definition-time refusal of an inventory species with a membrane, junction or channel
      route of @3's.
    - The tests, a crossrev driver for the new operators, and a radial builder with exact shell
      conductances.
  - **Landing checks.**
    - Crossrev ran from a clean snapshot of 17d00b4 against baseline-21fb714 and was identical in
      all five sets: base 36, qualification 78, injection 6, volume 6 and division 27 programs.
    - The tier 1 and 2 gates at 806eec9: 388 files, no changed outcome. Tier 1 at the merge
      bbbc922: 306 files, no changed outcome.
      - The merge's first tier-1 attempt ran the system Python, which has no pytest, so every file
        failed to start. It is kept as `land-gate1-bbbc922-failed-system-python`; it is not a test
        result.
    - The tier-3 files pass: compiled runs 7/7, ion guards 3/3, energy and radial guards 6/6.
  - **Guards.**
    - Ion fields are bitwise unchanged with both operators active, in scalar runs, restarts, a
      vector batch and a replacement event.
    - Booked work matches the exact ΔG per law, computed independently in 50-digit Decimal.
    - Exchange's kind order, run as a palindrome, is second order.
    - The RK4 radial world's energy residual is 4.5e-14 pJ.
    - The IMEX radial world is second order in dt (ratio 4.05).
    - A stiff front run from a 1e-15 mM trace stays positive, with no step refused.
    - A thousandfold change of the trace moves the profile by 0.947 times that change.
  - **Findings.**
    - **The IMEX energy guard is coarse.** It sees a booking error only above about 2e-3 of the
      species' flows. A 1% face-heat error passes under IMEX at 0.89 of the bound and is refused
      under RK4. So RK4 and the per-law ΔG tests are the sensitive guards (design §7, amended).
    - **The radial errors are turnover's splitting:** dt²·k·(g − k·c_ss)/12 under RK4 and /4
      under ARS. That is negligible at morphogen rates.
    - **Anchored amounts** stall positive near ε × their anchor after kt ≈ 36 (design §1.3,
      corrected).
    - **S5's bridge.** The impermeability refusal blocks the bridge for inventory species until
      the queued D148 round for @3.

- **The shared-inventory reactions design (D152) is accepted (14 November).** The lead, with the
  advisor; docs only ([note](docs/SHARED_INVENTORY_REACTIONS_DESIGN.md), rulings in §9). Every probe
  ran on CPU through `run_detached.sh`
  ([evidence](/mnt/workspaces/Cells/shared-inventory-reactions-20261114-01/): HANDOFF.md,
  `sweep/SWEEP_SUMMARY.md`).
  - **Probe 1, the engine at ac5a251.**
    - MG0c's transport world runs, and its species-set step is admitted.
    - The species' transport is second order (ratios 4.00–4.01).
    - The ions are bitwise unchanged.
  - **The NumPy prototype** is development evidence only.
    - The half-step, the Strang composition and the bookings are second order (ratios 3.98–4.07).
    - The review corrected the stage condition for passive routes.
  - **Mixed-node heat.**
    - A stage quadrature overbooks a passive switch-on from a 1e-12 mM trace by 34–54% in the first
      step.
    - An average-vector-field share goes negative at crossings.
    - The adopted per-route hybrid does neither.
    - The known limit: a driven route that carries a trace species across a passive equilibrium
      within one half-step books 5.4–5.6 times that step's true heat at a 1e-12 mM trace. In the
      probed world that is 0.27–0.56% of the whole heat at 1 s.
  - **C3.** Second order holds up to dt·L ≈ 2 in three stiff worlds, so version 1 refuses
    dt·L > 1.
  - **C4, the engine at ac5a251.** A neutral species on a junction or membrane gets no rate bound
    from @3.
    - In species-only worlds it is refused loudly from x = 0.1.
    - Where other flows set the shared bound, it passes silently up to x = 1, with errors of 0.07%,
      2.3% and 13% at x = 0.1, 0.5 and 1.
    - The sweep found no config, test, registered or qualified world that declares such a species.
      A D148 round for @3 is queued after D150 v1.

- **S5a is qualified: every judged item passed (14 November).** Judged once each, in series, from a
  fresh clean snapshot of main at 7f9c473 (src identical to baseline-21fb714's), after the
  division crossrev matched that baseline. There were no infrastructure kills
  ([judged outputs](/mnt/workspaces/Cells/cell-division-s5-20261113-01/judged-s5j1/)).
  - **Q2, the event map against R-ops:** pass, under the registered rule (the third amendment).
    - The worst ratio is 1.98 eps × magnitude, against a limit of 64.
    - All 66 judged control entries are caught at or below 1e-9.
    - The construction checks are faithful in all 12 cases.
    - Ten near-zero cases were found in the judged sets. Spread 0.1 had none, so it is vacuous
      there.
    - Five readings of the three controls the third amendment exempts fall below 64 at 1e-9, at
      first order (observed against predicted 0.998–1.003). They are reported, not judged.
      Under the frozen rule they would have failed Q2.
  - **Q3, trajectories against R-tissue:** pass. 33 rows, the largest difference 0.445 of its
    tolerance.
  - **Q5, observed order:** pass. Every step term decreases for all 8 measurable components.
  - **Q1 and Q11, the egg-scale world:** pass. The replay is identical and the negative control
    fails.
  - **Q4 and Q6–Q9:** all 21 test files pass at the judged snapshot. Q10 is reported.
  - **What this qualifies:** partition, bridge closure, insertion@2 and lumen@2 in division
    worlds. Q7(b), S3's egg on @2, is deferred to its own registered variant.
  - [Protocol](validation/division/s5_protocol.json);
    [evidence and log](/mnt/workspaces/Cells/cell-division-s5-20261113-01/HANDOFF.md).

- **The S5 protocol is registered (14 November).** The lead registered
  `validation/division/s5_protocol.json` after the final review with the advisor. The JSON's
  registration diff is the status line only.
  - **Before registering:**
    - **The lead read the protocol.** The judged seeds sit in their slots and appear nowhere
      else. The changes since the freeze are the three disclosed amendments and one erratum.
      The threshold is unchanged.
    - **Two rules were added:**
      - an infrastructure kill is not a verdict, and is rerun once from the same snapshot;
      - a judged set with no near-zero draw is reported as untested there, not failed.
    - **A rehearsal on main** reproduced every frozen number. The egg is byte-identical across
      the merges, and the division crossrev matches baseline-21fb714. The rehearsal also found
      that Q2's judge read its seeds from the wrong path, which would have crashed the judged
      run; that is fixed and tested.
    - **A dry run of every judge entry** (Q2 with throwaway seeds, Q3, Q5 and the egg) reached
      and wrote its verdict, and the deterministic items matched the rehearsal exactly.
  - **Next:** the judged runs, once per item, from a clean snapshot of main. They run in
    series and `--oom-first`, so E07-v1's registered arms are protected.
  - **Gate:** tier 1, 303 files, no changed outcome
    ([gate](/mnt/workspaces/Cells/land-20261114d/)).
  - [Evidence and log](/mnt/workspaces/Cells/cell-division-s5-20261113-01/HANDOFF.md).

- **S5 protocol: the third and last control amendment, and the references' self-checks pinned
  (14 November).**
  - **The finding.** Three controls move charge in proportion to the patch charges: a_k, mismatch
    scale and transference. Their effect fades near 0 V while A.8's term does not, so under the
    frozen rule the seen-set preview failed on one near-zero draw.
  - **The amendment.**
    - The three are now judged on the fixed cases, and reported on the near-zero cases beside
      their first-order size.
    - The cause holds in all ten near-zero cases: observed against predicted is 0.99974–1.00040.
    - Parent charge, non-conservation, f and W stay judged everywhere, with margins of 174× or
      more.
    - The threshold, the seeds and the comparison rule are unchanged.
    - Both preview verdicts are recorded: fail under the frozen rule, pass under the amended
      one.
    - No judged state has been drawn. After registration, any control miss is a failed Q2.
  - **The references' own 64-eps self-checks** are pinned to the tight scale
    (`charge_term=False`). R-tissue uses R-ops' values only.
  - **Gate:** tier 1, 303 files, no changed outcome
    ([gate](/mnt/workspaces/Cells/land-20261114c/)).

- **The S5 protocol, frozen as PROPOSED, then R-ops' A.8 amendment (14 November).** They land
  as two merges in that order, so the freeze is on main before the new Q2 scale.
  - **The protocol** (`validation/division/s5_protocol.json`, built by `s5_protocol.py`) is
    PROPOSED, not registered. The S5 drivers refuse a judged run until it is registered from a
    clean snapshot. It fixes in advance:
    - **Q2's draws:** seen sets (development evidence) and judged sets with fresh seeds the lead
      assigned. The judged sets have never been run at either scale.
    - **Negative controls:** their targets, the 1e-9 threshold and the smallest-defect-caught
      statistic. Two amendments record findings:
      - ΔG is stationary at the correct split, so W can be reached only at second order. W
        gets its own free-energy control.
      - The bath's image charge moves only under a non-conserving defect, so it gets a
        non-conservation control.
    - **Q5 and Q10:** reported, not judged. Q5 keeps its stop rules.
    - **Q7(a):** the 19-cell sheet with idle division operators is bitwise.
    - **Q7(b):** deferred. S3's egg on @2 needs its own registered variant, so the @2
      operators count only in division worlds until it passes.
  - **R-ops' A.8 amendment.**
    - A cell's node-charge magnitude adds |Q̄| + 10⁻¹⁵ F Σ|zΔ|, carried through R-ops' own
      solve. `charge_term=False` gives the earlier magnitudes.
    - It loosens charges and potentials 70–160× on the usage example, and amounts barely.
    - On R-ops' own random states, which have large increments, it loosens them up to 1e9
      ([ratios](/mnt/workspaces/Cells/cell-division-s5-references-20261113-01/a8-ratios/a8_ratios.json)).
  - **Next:**
    1. the new-scale development pass: the seen sets under both scales, and every control;
    2. the advisor's review;
    3. registration and the judged runs.
  - **Gate:** tier 1 on the merged tree, 303 files, no changed outcome. The two new runs files
    pass uncapped: limits 4 tests, idle sheet 2 ([gate](/mnt/workspaces/Cells/land-20261114b/)).
  - [Evidence and log](/mnt/workspaces/Cells/cell-division-s5-20261113-01/HANDOFF.md).

- **Checkpoint continuity, first landing (D153; 14 November).** A checkpoint written under one
  source resumes under another only through a recorded admission. Refusal stays the default
  ([design](docs/CHECKPOINT_CONTINUITY_DESIGN.md)).
  - **Engine:**
    - `cells/continuity.py` verifies and binds records on the host;
    - `load_snapshot` and `load_batch_snapshot` take `continuity=`, and with `None` today's
      code path and messages are unchanged.
  - **Tools** (`validation/continuity/`):
    - `probe.py` compares programs, constants, StableHLO and bindings, replays the host
      side, and runs a bitwise CPU overlap;
    - `admit.py` and `verify_run.py`;
    - `dev_run.py` drives the first consumer.
  - **Scope:**
    - vector windows only, on CPU definitions with `jit: true`;
    - case 1 (source changed, programs unchanged) is admitted by the probe;
    - case 2 needs a D148 record, admitted by the lead;
    - cases 3 and 4 are refused.
  - **Evidence:**
    - an admitted resume across a source change is bitwise equal to the uninterrupted run
      and passes `verify_run` (17 checks);
    - a program edit is refused;
    - 100 tests pass: loaders 54, bypass guard 17, tools 18, acceptance 11.
  - **D148 for the landing:** crossrev on the landing tree (21fb714) is identical in all five
    sets: base, qualification, injection, volume and division. The renewed baseline of record is
    [baseline-21fb714](/mnt/workspaces/Cells/checkpoint-continuity-20261113-01/baseline-21fb714/baseline-of-record.json).
  - **Not yet:**
    - the GPU probe (§13.4), queued for the next L4 gap;
    - rule (b) records for four tools;
    - scalar snapshots, which answer "cannot decide".
  - [Evidence and log](/mnt/workspaces/Cells/checkpoint-continuity-20261113-01/HANDOFF.md).
- **Cell division S5a, qualification pending (14 November).** `isopotential_partition@1`,
  `cytoplasmic_bridge_closure@1`, `scheduled_membrane_insertion@2` and
  `restricted_cleft_lumen@2` land at S5a's 1691dc2, with closers and the contract's host-side
  liveness methods ([design](docs/CELL_DIVISION_S5_DESIGN.md)).
  - **Guards:**
    - crossrev is identical in every existing set (base, qualification, injection, volume);
    - S5's own set records E_ref, q_ref and `partition_birth_gate` as bindings;
    - the J2 bright line holds, including a fresh-process test that S5's crossrev tool never
      loads a J1 module.
  - **Development comparisons with the independent references, at this commit:**
    - **Q3**, trajectories after partition against R-tissue on the compact 1→2→4 world: each
      difference is about 4/3 of the engine's step term (Vm 1.13e-7 V against 8.5e-8 V),
      within 3 × (step + reference).
    - **Q5**, observed order 1.99–2.06.
    - **Q4:** the open-bridge limit holds to 1e-3, and the symmetric, asymmetric and
      isopotential limits hold in NumPy.
    - **Q1 and Q11** at egg scale, 120,000 steps through 1→2→4:
      - energy balance 4.2e-7;
      - charge at 0.0087 of its bound;
      - electrode charge error 3.4e-23 C.
    - **Q2 is open.** It sat within 64 eps × magnitude only under a 10% net-charge band, now
      withdrawn; near zero potential the ratio reached 860.6.
      - The cause is confirmed: rounding in charge formation from increments.
      - The lead's ruling adds an increment-form charge term to R-ops' magnitudes (A.8,
        pending in R-ops).
  - **Scope change:** S3's cleft egg on insertion@2 and lumen@2 (Q7b) is deferred to its own
    registered variant in S3's protocol family. Until it passes, the @2 operators count only
    in division worlds, and S3's egg stays on @1.
  - **Not yet:**
    - the registered protocol and its judged runs;
    - the second Q3 world, the closed-bridge limits and the PROPOSED protocol, which exist so
      far only on S5's branch.
  - **Gate:** tiers 1 and 2 on the combined tree with checkpoint continuity, 382 files, no
    changed outcome. The four slow new files also pass uncapped on the same tree: partition
    runs 11, division runs 5, bridge runs 1, continuity acceptance 11
    ([gate](/mnt/workspaces/Cells/land-20261114a/)).
  - [Evidence and log](/mnt/workspaces/Cells/cell-division-s5-20261113-01/HANDOFF.md).

- **Water plus replacement: `scheduled_cell_replacement@2`, the volume ledger (composite v2
  §2; 13 November).** @2 runs @1's event map unchanged, then:
  - gives the newcomer its volume: a template's declared volume, or for a donor copy the donor's
    (decision 10);
  - books removed and supplied volume in water's ledgers;
  - books water's dilution and elastic free-energy change in fields of its own.

  It refuses `law_steady` over water, and it refuses `[water, injection@1]` (injection's view
  conflict on volume).
  - **Guard A, outcome A under its registered rule:** no qualified program changed.
    - Crossrev with constants is identical to the baseline of record (36/36/12, 78/78/56,
      6/6/2).
    - All 58 forward worlds are identical in every field, ledger accumulators included.
    - The W1 and W2 judges are identical, step-map numbers included. Rm1 and G2-Q1 are
      identical apart from provenance strings.
    - 24 files (354 tests) pass, the frozen models' 130 included.
  - **Guard B passes:**
    - without events the composition equals water alone, bitwise;
    - with water closed it equals @1 on @1's fields, bitwise;
    - every ledger closes across events (energy within 1e-9 pJ, water within 1e-14 pL);
    - water's first flow after an event is analytic to 1e-12;
    - restart and vmap pass.
  - **Cost:** about 1.5 ms per step on the 127-cell sheet (water alone 4.3–5.5 ms, with @2
    6.0–7.0 ms); compile goes from 28 s to 44 s.
  - **Open:** `law_steady` over water, and an injection law that books dilution. Both wait for
    a consumer. All runs so far are development runs; no judged run uses @2 yet.
  - **Gate:** tiers 1 and 2 on the merged tree, 374 files, no changed outcome
    ([gate](/mnt/workspaces/Cells/land-20261113s/)). New files: `test_cell_replacement_v2.py`
    in tier 1, `test_cell_replacement_v2_runs.py` in tier 3.
  - [Evidence and log](/mnt/workspaces/Cells/composite-v2-s2-20261113-01/HANDOFF.md).

- **The S5 independent references, R-ops and R-tissue (13 November).** A separate agent wrote
  them from Appendix A and §10.1 of the [S5 design](docs/CELL_DIVISION_S5_DESIGN.md). It read no
  S5 engine code, and its read list is in the log.
  - **R-ops** (`validation/division/partition_reference.py`) is the division map (A.6) in NumPy.
  - **R-tissue** (`validation/division/cleft_tissue_reference.py`) generalises R-full to cells,
    clefts, contacts, bridges and lumens. It integrates with Radau at rtol 1e-10 and applies
    R-ops at each division.
  - **Results:**
    - R-tissue reproduces R-full on S3's egg at J1 to 6.4e-16 V (target 1e-10 V), and over all
      211 pulses to 1.0e-14 V;
    - R-ops' identities hold to 1.96 eps × magnitude on 200 random states;
    - the symmetric, isopotential and bridge-open and bridge-closed limits hold;
    - R-full is untouched.
  - **Status:** they are the references for S5's Q2–Q5, and nothing is judged yet.
  - **Gate:** tier 1 on the merged tree, 291 files, no changed outcome
    ([gate](/mnt/workspaces/Cells/land-20261113r/)). Of the new files, one is in tier 1, two in
    tier 2, and the J1 cross-check (about 110 s) in tier 3.
  - [Evidence and log](/mnt/workspaces/Cells/cell-division-s5-references-20261113-01/HANDOFF.md).

- **Crossrev now compares constants; earlier verdicts stand (13 November).** The
  checkpoint-continuity design found that `composite_crossrev.py` compared jaxpr text and
  bindings, but not the values of closed-over arrays or the device-check constants. A
  constant that only gates acceptance could have changed unseen.
  - The tool now records the dtype, shape and SHA-256 of every closed-over array, and the
    check constants. Scalars such as `NEWTON_TARGET` were already caught as full-precision
    literals in the text.
  - The retro-check from `8416a72` to main found every constant unchanged, so the D148,
    S2 and S3 crossrev verdicts stand.
  - The new baseline of record, with constants, is
    [crossrev-constants](/mnt/workspaces/Cells/cell-division-s3-20261113-01/crossrev-constants/baseline-of-record.json).
  - D148 states what crossrev compares. The D147 floor guard compares primitive counts,
    not constants, so it is rerun with constants before version 3 serves a run of record.
  - Tier 1 gate: 290 files, no changed outcome.
  - The proposed [checkpoint-continuity design](docs/CHECKPOINT_CONTINUITY_DESIGN.md)
    landed with it. Implementation waits for its probes and for the user's answer on
    AGENTS.md's attestation rule.

- **Field-solver limits: on CPU the hold step is mostly work on dense node-space matrices that
  are under 1% dense. The factorisation and solve kernels alone are just under half. An
  interface is proposed, with no code (13 November; `resolved_pump_tissue@3`,
  `capacitive_reduction_gauged_damped_newton@2`).**
  - **Hypothesis and test.** Most of a hold step is dense float64 node-space linear algebra:
    the IMEX operator's Cholesky every step, the capacitor and stage triangular solves, and
    the offset LU and products. It is falsified if these take under half the step at 825
    nodes on CPU.
  - **Result on CPU: falsified as stated, narrowly.** The measurement is the hold world's
    fused step on one core, each instruction's own time:
    - the four kernel classes take 45% of attributed time (Cholesky 25%, triangular solves 15%,
      LU 5%), or 33% of the 110 ms to ready;
    - adding the n × n assembly, copies and checks that dense matrices need, dense node-space
      work takes 70% (51% of time to ready);
    - the pieces compiled alone (75–81%) are an upper bound;
    - a first trace that summed nested events read 49% and is kept.
  - **Sparsity at 825 nodes.**
    - The free IMEX operator is 0.67% dense. Minimum degree gives a factor with 7,537
      nonzeros and about 1,800 times less factorisation work than the dense Cholesky.
    - The offset incidence is 0.40% dense, and the junction incidence is empty, so the
      Jacobian's junction product adds an exact zero.
    - At 254 nodes (the 127-cell sheet) every node-space operator is diagonal.
  - **Conditioning and drift.** The operator's condition number is 223 after Jacobi scaling.
    In the hold it moves at most 4.7 × 10⁻⁵ from t = 8 s to 1,206 s, and 3.3 × 10⁻¹⁰ over one
    200-step window.
  - **Design.**
    - **Interface.** One solver per field-solver ID covers the capacitor, IMEX and offset
      solves, in three phases: bind, prepare and solve. The existing residual checks are the
      acceptance test.
    - **Candidates.** Sparse direct with a bound ordering, PCG, and factor reuse at declared
      epochs (the composite note's R3 options (b) and (c)). Each is a new solver ID with
      tolerance-based qualification.
    - **Node bound.** Each ID would declare its own node bound in place of the 2,048-node
      dense limit.
    - **Ceilings.** By the L4 split no single piece gives 2×. On CPU, making all dense
      node-space work free gives about 2× to 3.4×.
    - **Next.** No code until the kernel profile has run on the L4 and GH200.
  - **Kernel profile plan.** About 15 min: traces of E07's world at 6 and 256 worlds and of the
    hold world at 6, then the pieces on the device and batched.
    - It reruns unchanged on GH200 and was smoke-tested on CPU.
    - Device-kernel attribution is untested on a GPU; the batched pieces are the fallback.
  - **The first pass's three hold steps refused** the hold's GPU backend on CPU. They are kept
    in `logs/` and were rerun with `--backend cpu`.
  - [Design note](docs/FIELD_SOLVER_INTERFACE_DESIGN.md),
    [summary](/mnt/workspaces/Cells/field-solver-limits-20261113-01/summary.json),
    [results](/mnt/workspaces/Cells/field-solver-limits-20261113-01/results/),
    [kernel profile plan](/mnt/workspaces/Cells/field-solver-limits-20261113-01/kernel_profile_plan.sh).
  - **Also landed:** the L4 agreement driver now takes three blind repeats (A, B, D)
    before a judged run, after a third L4 repeat exceeded one pair's spread by up to 6×.
    The definition-invariant waste found here is listed as a parked candidate for its own
    D148 round. Tier 1 gates: 289 files, no changed outcome.

- **Stage S3 judged: the engine's cleft egg agrees with R-full (13 November; registered
  protocol `486cc60`; verdict pass).**
  - **Engine models:** `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with
    `membrane_entity_state@1`, `scheduled_membrane_insertion@1`, `restricted_cleft_lumen@1`
    and `electrode_current_injection@1`.
  - **The run:** once, from a clean snapshot of main `4465b48` on CPU 4 (54 min, no OOM),
    with device checks passing on every row. It reproduces the 0.25 ms development run
    bitwise in every recorded number
    ([protocol](validation/division/cleft_egg_protocol.json),
    [evidence](/mnt/workspaces/Cells/cell-division-s3-20261113-01/judged/)).
  - **Engine − R-full at 0.25 ms,** against 3 × (step term + integrator-only reference term):

    | Quantity | Engine − R-full | Tolerance |
    | --- | --- | --- |
    | Em at J1 | +4.0e-10 V | 1.0e-9 V |
    | Rm at J1 | +7.8 Ω | 15.3 Ω |
    | Em at every pulse edge, 0–210 | at most 1.1e-7 V | 2.7e-7 V |
    | Lumen K at J1 | −9.5e-7 mM | 2.6e-6 mM |
    | Lumen Na at J1 | +7.6e-7 mM | 1.9e-6 mM |
    | Rm1 (reported only) | +18 Ω | 41 Ω |

    Each judged quantity is at 0.36–0.51 of its tolerance.
  - **The reference term** covers R-full's integrator variants only. It was chosen after the
    development data and disclosed as the stricter rule. The activation-area variant is
    reported as a sensitivity both models share.
  - **Crossrev baseline renewed at the landing commit (D148):** base 36/36 jaxprs and 12/12
    bindings, qualification 78/78 and 56/56, injection 6/6 and 2/2, all identical to the
    earlier runs.
    - The new baseline of record is
      [crossrev-landing](/mnt/workspaces/Cells/cell-division-s3-20261113-01/crossrev-landing/baseline-of-record.json).
    - `8416a72` stays the earlier record.
  - **Next in division:** S4–S5, partition and bridge closure, towards prescribed division
    (milestone 1).

- **Checkpoint continuity approved as tooling (13 November).** The user's words: "yes fix
  checkpoint continuty also". This approves the versioned checkpoint migration, which D145 listed
  as unapproved tooling; the public validation package is still unapproved.
  - **What refuses resumes today:** `io.load_snapshot` and `batch_io.load_batch_snapshot`
    refuse any change in the SHA-256 of every `.py` under `src/cells`, and any change in
    `runtime_identity`. That covers the package versions, `XLA_FLAGS` and, on GPU, the device
    kind, so an L4 checkpoint cannot resume on GH200. `runner.validate_checkpoint` also
    refuses a layout that differs from the declared model's.
  - **Already outside that rule** (corrected from the design's §7): 32 non-test files under
    `validation/` and `scripts/` name `state.npz`, but most only read or write saved bytes.
    - Three uses crossed an identity: `scripts/profile_dispatch.py` (held L4 states under
      other XLA flags), `field_floor_held.py` (version 3 on version-2 states), and E07-v1's
      import of the sheet70 start states, which crosses the D148 ledger fix.
    - The driver-owned resumes have no identity check: `e07_v1_run.py`, the turnover tool's
      `checkpoint.npz`, and `open_calcium_bath_trajectory_production.py`'s handoff.
  - **Plan:** a fresh agent writes the design only, in the slot the S3 agent frees, ahead of
    the one-execution-path work, since both own the checkpoint validation.
    - It keeps four cases apart:
      - **source changed, step program identical:** admitted;
      - **program changed, physical fields unchanged:** only with a D148 record;
      - **definition, layout, solver or model ID changed:** refused (D146, D147);
      - **runtime changed:** its own rule, with a move to GH200 judged by tolerance.
    - Refusal stays the default, and every migration is an explicit, recorded step.
    - Registered runs are unchanged, and the first consumer is a CPU development run.

- **Hold segment 2 continues on version 2. The L4 dispatch test rules out loop control
  (13 November).**
  - **The hold.** Segment 1 ended cleanly at 14:48 UTC: 6,000 windows and snapshot
    `t01206`, in 20.1 h. The restart rule gave no restart:
    - command buffers ran at 1.00× and masked loops at 0.22×;
    - the margin at the end of segment 1 is 0.21 of `NEWTON_TARGET` (at most 0.45 over the
      snapshots).
    - Segment 2 runs from `source-09` as `cells-w1-ft2-seg2`, from 15:48 UTC.
  - **The finding.** One six-world step takes 48 ms on the L4: 23 ms of field solve, 25 ms
    of the rest, and 9 ms more for the device checks. The rest and the checks run no loops.
    - Removing all host-blocked loop time would give at most 1.37×, under the 1.4×
      break-even.
    - The cost is device execution. The leading hypothesis is dense float64 node-space
      linear algebra per world, about 0.32 GFLOP per world-step: chiefly a Cholesky of the
      825-node IMEX operator every step. This is read from the code, not timed.
    - The L4 does not repeat bitwise, so an equivalence test there needs three or more
      repeats.
    - Version 3 accepted all 1,000 steps from t = 0 on the L4.
    - [Note](/mnt/workspaces/Cells/window-timing-20261112-01/l4-dispatch-note.md).
- **Combined landing: the S3 ledger fix (D148), stage S3's engine side and the phase markers
  (13 November).** Tier 1 + 2 gate: 369 files. The one changed outcome was the D147 driver
  guard catching the new D148 guard tool; it is now exempt with its reason and passes.
  - **The ledger fix.** `surface_tissue.capacitor_change` sums species in a fixed order, so
    @3's electrode ledger telescopes exactly at egg scale.
    - Physical fields are bitwise in all 58 guard worlds, and the judges' registered numbers
      are unchanged; only the electrode accumulator moves, by each world's former residual.
    - D148 records when an in-place fix to qualified code is admissible.
    - The crossrev baseline is renewed at this landing, and `8416a72` stays as the earlier
      record.
  - **`restricted_cleft_lumen@1`.** A restricted compartment filled from the bath as the
    membrane area grows. It books volume work and mixing heat, and reads lumen composition
    at the area of each saved time.
  - **The cleft-egg engine definition** is built from R-full's own egg; all 30 fields agree.
    - The development dt study gives, at 0.25 ms, engine − R-full of 4e-10 V in Em at J1,
      7.8 Ω in Rm at J1, and under 1e-6 mM in the lumen.
    - The S3 protocol uses an integrator-only reference term, chosen after the data and
      disclosed as the stricter rule. Its judged run follows.
  - **Phase markers.** Binding, plan validation, compile and the first window are reported as
    they happen, and timings are grouped into phases. This is host-only and bitwise.

- **Cell division S0b: the registered J1 combination round is parked (13 November;
  development, judged by its own registered criteria).** No eligible point passes, under
  either criterion form. Nothing is frozen and no C1 registration follows. R-full with the
  registered inputs stays the reference, and its J1 failure and the shared shape mismatches
  are recorded as unexplained. C1 and J2 stay held, and there is no third round
  ([registration](validation/division/j1_combination_round.md),
  [evidence](/mnt/workspaces/Cells/cell-division-s0b-20261111-01/j1-combination-01/)).
  - **What ran:** nine points on R-full, from a clean snapshot of main `6b77733`, in two
    units (66 CPU-min in total, no OOM). The null check reproduced the record to 2.3e-12 V.
    - A1 × A7a, with f calibrated at J1 at α 0, 0.5, 1 and 2 (f = 0.0193 throughout).
    - Seal × A7a and seal × A6c at α 0 and 1.
    - A6c × A7a at α 1.
  - **The front-loaded Rm fall fails at all nine points** (D5 0.85–0.98, against ≤ 0.66).
    It is the only criterion A1 × A7a fails at the marked α = 1.
  - **The early Em minimum** (T-D3) fails everywhere except A1 × A7a at α 0–1, where Em is
    still falling at J1.
  - **Pairings without A1 miss the J1 window.** Seal × A7a gives −16.5 mV and A6c × A7a
    −13.8 mV, both within 0.04 mV of their registered predictions. Seal × A6c gives −18.4 mV,
    0.9 mV more negative than its additive estimate and 0.3 mV short of the window.
  - **The two T-D7 forms** disagree at two points, both of which fail other criteria under
    both forms. No verdict depends on the form.
  - **Reported only:** cytosolic Na at J1 is 20.1–20.3 mM, against the measured
    22.4 ± 1.1 mM.
  - **Resuming** needs new measurements or the user's decision. One cosmetic runner bug:
    the null check's flag is written as 1.0 rather than true.

- **E07-v1 registered (13 November; renewal stage, option (c)).** Registered before any engine
  run: [design](docs/E07_V1_DESIGN.md) and
  [protocol](validation/tissue/e07_v1_protocol.json).
  - **The frame.** Donors are drawn without regard to state, over the whole sheet, and
    each run is judged against its paired copy-only null. Copying alone never passes B1
    (0 of 2,000 seeds), so a positive B1 needs recruitment. Disc-only donors are a
    control.
  - **The formation law** gives time-averaged junction abundance after the first
    turnover of only 0.20 (fast k1) and 0.15 (central k1). That is why fast k3 arms were
    added, and why junction weight is reported per run (E6).
  - **Judging.** Each run is classed and judged by 4080 s, the control's end. Censored
    runs are judged at their last valid record and never dropped. Arm (b) is
    threshold-finding.
  - **Scale:** 38 judged runs plus E1, about 50 core-hours.
  - **Execution:** one clean snapshot of main after the S3 ledger fix and the engine-run
    driver land.
  - Tier 1 gate: no changed outcome
    ([gate](/mnt/workspaces/Cells/land-20261113j/)).

- **User decisions of 13 November, taken on the lead's suggestions after the advisor's
  review.**
  - **D149:** `processes/source_electrochemistry.py` keeps the reference's four
    numerical conventions as a cited profile of `emt_mirna_pair@1`. This is an exception
    to AGENTS.md, for bitwise continuity of the recorded replication runs.
    `tests/unit/test_source_profile_boundary.py` confines the module to that model.
    Nothing is renamed. Tier 1 gate: 285 files, no changed outcome.
  - **J1:** a registered combination round. Its registration is being drafted, and
    nothing runs until the lead registers it. The round has:
    - an exit rule;
    - numeric criteria fixed before the runs;
    - a calibration datum per unknown;
    - a pairing without A1.
  - **E07-v1, option (c):** donor copies as the main route, and isolated newcomers with
    fast junction formation as a threshold-finding set.
    - Donors are drawn without regard to state; disc-only donors are a control.
    - A copy-only null comes first, and a design and registration draft follow.
    - Replacement over water (v2 §2) comes after the S3 fix lands.

- **G2-Q1's judge runs again as registered (13 November).** Its Q2 part had failed on the
  tree since `92a4eeb`, when replacement@1 became a thin composite module and stopped
  exporting `CHARGE_PER_FMOL`, which the judge reads. The thin module re-exports it, and Q2
  run as registered equals the recorded judged run. A tier-1 test,
  `tests/unit/test_judge_imports.py`, checks that every name the registered judges (G2-Q1,
  W1, W2, Rm1) import or read exists. Tier 1 gate: 284 files, no changed outcome.

- **Field-solve acceptance: a convergence test with no margin on the full tissue; new
  definitions with free field offsets declare solver version 3 (D147; 13 November).**
  - **The defect.** Version 2 accepts a field solve when the normalized residual is ≤ 0.01.
    On the W1 hold's 825-node tissue a converged root sits at 0.8–1.1 of that, at the
    rounding floor of the current balance. So acceptance depends on how XLA compiled
    the program.
    - From t = 0, the vectorized CPU program refuses at 0.085 s and 0.186 s, and scalar
      `jit` refuses at 0.45 s. The L4 accepted 0–6 s and more than 1,100 hold windows.
  - **Exposure.**
    - The W1, W2, G2-Q1 and sheet70/turnover worlds have no free field offsets (residual
      exactly 0), so their results don't depend on this.
    - The hold's tissue reaches 0.92–0.995 of the target from t = 0 (CPU), and 0.18–0.45
      at 8 s.
  - **Version 3** (`capacitive_reduction_gauged_damped_newton@3`, opt-in since 9 November)
    also accepts residuals within 1e3 ulps of the attainable floor. It accepts every edge
    state, with states bitwise equal to version 2's before them.
    - **Guards:**
      - crossrev on 41 worlds;
      - dumps of W1, W2, G2-Q1, Q5, Q6, W37 and the 825-node world equal under v3;
      - a solve held at 0.95 of the cap passes every row check and ledger, and moves
        the state by ≤ 5e-13.
    - Row checks and ledgers cannot see field residuals, so v3's safety rests on that
      state bound.
  - **D147:** a definition with free field offsets declares version 3. Version 2 and every
    qualified ID are unchanged, and a switch is a new definition. `heredity_pilot.py
    --field-solver auto|2|3` applies it (default `auto`), and `--field-solver 2` rebuilds
    `source-09`'s definitions exactly.
  - **The hold** stays on version 2. Its restart rule at the end of segment 1 is set by the
    L4 dispatch test (`scripts/profile_dispatch.py`).
  - Tier 1 + 2 gate: 359 files, no changed outcome
    ([gate](/mnt/workspaces/Cells/land-20261113e/)).
  - Evidence: [design note](docs/FIELD_FLOOR_ACCEPTANCE_DESIGN.md),
    [guards](/mnt/workspaces/Cells/field-floor-guards-20261113-01/summary.json),
    [driver](/mnt/workspaces/Cells/field-solver-driver-20261113-01/summary.json).

- **S3 prerequisites (a) and (b) resolved; the L4 driver takes runs split across GPU gaps
  (13 November).**
  - **(b) Injection books at the view.** A split part declaring `BOOKS_AT_VIEW` receives
    the composite's view in its half-steps when a field input is provided. Injection then
    books plate charges and the capacitor-energy change there, so insertion and injection
    compose. Without a field input the arithmetic is unchanged.
    - Guards: the analytic two-clamp image charge after insertion; every ledger closing;
      pulses across a masked furrow and its onset; restart mid-insertion; vmap.
    - Crossrev against `8416a72` identical, and the injection world set identical to
      `00672e8`, so the judged Rm1 stands.
  - **(a) The onset energy.** The furrow opens uncharged at bath composition, which is
    R-full's convention. Charging dissipates ½·C_on·Vm² whatever the access resistance.
    - At the egg's 6.6 µs access time no admitted step resolves this. The unbooked part is
      at most 3.1e-4 pJ, 7e-8 of the host energy bound, and tests pin it.
  - **(c) Open: an egg-scale electrode-ledger drift**, about half an ulp per step after the
    Na increment crosses 2¹⁶ fmol, seeded by the pulses. The mechanism is being pinned
    before any fix; S3's egg runs wait for it.
  - **S3 plan** (`docs/CELL_DIVISION_S3_PLAN.md`): the engine against R-full on the cleft
    egg. Draft; the lead's choices are a judged step of 0.25 ms, lumen K and Na judged, and
    Rm1 reported. Nothing has run.
  - Tier 1 + 2 gate: 357 files, no changed outcome
    ([gate](/mnt/workspaces/Cells/land-20261113d/)).

- **Composite v2 §3, stage S2: membrane state and insertion landed (13 November).**
  `membrane_entity_state@1` owns area and capacitance as state (R2 views).
  `scheduled_membrane_insertion@1` inserts membrane on a patch as a split process, with
  onset masks selected by value. Engine models: `resolved_pump_composite@1` over `@3`.
  - **Energy:** @3's capacitor term reads the declared C0 and arrays, so insertion's ledger
    terms add the correction. The total equals ½ΣCV² − ½ΣC0V0² to 1e-12 (one patch, and two
    clamps with plate charges). The one-patch analytic checks hold: V′ = VC/C′,
    H = ½q²ΔC/(CC′), ΔU = W − H.
  - **Guards:**
    - crossrev against `8416a72` identical, measured twice;
    - 17 saved runs bit-identical;
    - idle and rate 0 bitwise equal to the composition without the operators;
    - restart across onset and insertion bitwise, and a reversed vmap batch bitwise;
    - catalogue invariance holds, and every composite test file passes.
  - **Limits:**
    - Field-input providers are refused above 64 padded field nodes. The per-step
      refactorisation costs +7.5% on the egg and +48% at 825 nodes.
    - Every planned egg world fits (up to 16 cells, 47 nodes). The 825-node idle guard
      waits for option (b) or (c).
    - Insertion itself adds 15% per step on the cleft egg.
  - **Departures and open items:**
    - The new membrane's leak is its passive permeability. This departs from division
      design §6, because @3 needs law code 0 for inactive populations.
    - Water and replacement refuse to compose with membrane state (`CONFLICTS_VIEW`).
    - S3 prerequisites: the onset energy at a fast access (about ½C_f·Vm² unbooked), and
      injection booking its image charge at the view.
  - Tier 1 + 2 gate: 358 files, no changed outcome
    ([gate](/mnt/workspaces/Cells/land-20261113c/));
    [evidence](/mnt/workspaces/Cells/composite-v2-20261112-01/HANDOFF.md).

- **Energy roles declared, and the hold's window timing diagnosed (13 November).** Tier 1 + 2
  gate: 356 files, no changed outcome ([gate](/mnt/workspaces/Cells/land-20261113b/)).
  - **Energy roles** (completes v2 §1.1): heat and work fields are declared by name (the
    adapter's `HEAT_FIELDS` and `WORK_FIELDS`, and each operator's own). They reach
    `surface_pump.ledger_limits` through its new optional `flow_fields` argument; the
    default keeps suffix selection. For every registered composition the declared table
    equals the suffix selection, and the guards against `8416a72` are identical.
  - **Window timing** (read-only on the hold):
    - On the L4, 88% of the hold's wall time is inside the GPU dispatch call, about 53 ms
      per batch step for six worlds; host work is about 12%.
    - The 0.41 ms per step in `run.json` was the previous window's host tail, not device
      time.
    - Leading hypothesis, untested: the field solve's data-dependent `while_loop`s are
      driven from the host.
    - Segment 1 ends about 15:25–16:55 UTC: 20–22 h per 1,200 s segment and 71–77 h for
      the whole hold.
  - **Fix:** pump-family experiments keep their built `changes`. That takes the call from
    10.3 ms to 0.4 µs (and `event_index` from 10.3 ms to 1.3 µs), about 2% of a window.
    The jaxpr, a scalar run and a six-window vectorized run are bitwise identical. The
    hold stays on `source-09`.
  - [Evidence](/mnt/workspaces/Cells/window-timing-20261112-01/summary.json).

- **Heredity turnover under the literature newcomer rule: no disc renewed, and B1 failed
  in all 21 arms, as predicted (11–13 November; development pre-screen, not judged).**
  Driver `validation/tissue/heredity_turnover_literature.py` on
  `resolved_pump_replacement@1` (inner `@3`, IMEX ARS(2,2,2), dt 5 ms). 5 ms matches 1 ms
  within 9 µV, with identical D sets. [Summary](/mnt/workspaces/Cells/heredity-turnover-literature-20261111-01/summary.json),
  [log](/mnt/workspaces/Cells/heredity-turnover-literature-20261111-01/HANDOFF.md).
  - **Design:**
    - the five sheet70 discs that held 70 min, from their state 2 min after the cue;
    - only disc cells are replaced, oldest first, with residence 1, 3 or 10 times the
      formation time (fast 2 + 15, central 10 + 30, slow 20 + 60 min);
    - newcomers are isolated H templates or donor copies of a random neighbour (D139);
    - predictions were registered before any run.
  - **Isolated newcomers: none of 317 became D.**
    - Their junctions form only after their D neighbours have been replaced or pulled to
      H, and their Vm never rose above −68.9 mV (D starts at −39.4 mV).
    - Discs ended all H at 0.98 R (s 0.3), 0.59–0.96 R (s 0.6) and 0.23–0.81 R (s 1.0).
      At s 1.0 that was 15–59 min after the cue, against 70 min without turnover.
    - Stronger coupling made it worse.
  - **Donor copies: persistence by copying only.**
    - D copies stay D, but H cells from outside dividing into the rim erode it.
    - J after one and two turnovers was 0.73–0.89 and 0.51–0.58 at s ≤ 0.6, and 0.59
      and 0.43 at s 1.0 with k1. The disc was lost at k3 and k10.
    - Each disc had one seed.
  - **Predictions:** 26 registered items failed, listed in `summary.json`. Most are the
    predicted interior conversions, loss windows and donor J ranges.
  - **After the predictions were frozen,** a stress segment (formation tau 40 s, s 0.6,
    six D founder neighbours) converted newcomers at A 0.59–0.68. Conversion needs D
    neighbours that persist.
  - **Also:** no refusal, no D outside the disc, no osmotic censor (max excess 14.4%).
  - **Incidents:** out-of-memory kills stopped three arms (12 November 01:36 machine-wide;
    19:33 in cells.slice). Each was rerun from the same snapshot; the 19:33 rerun
    reproduced its completed run bitwise. The end-of-arm analysis peaks near 5 GB RSS, so
    cap longer arms at 6G or run the analysis separately.
  - **Engine gap:** replacement over the water inner model (G2 stage 3), needed for
    donor-copy arms beyond about 95 min of inherited loading.
  - **Next:** the E07-v1 redesign is the user's decision.

- **Composite v2 §1.1: bound step checks and @3's free-energy owner (13 November).** The
  composite binds its step checks to the definition. @3's bound checks run on each
  operator's `inner_check_spec` adjustment, then each operator's own checks run; water's and
  the symport's definition-only bounds are computed once.
  - Layout builds per clock are now constant (water@1 5, water@2 6, replacement@1 2), where
    before that many were built per chunk; no control tables are built.
  - @3's chemical and capacitor free energy are owned by `pump_composite_adapter`.
    Replacement and injection use it there, so injection's temporary import is gone.
  - Guards against snapshot `8416a72`: jaxprs 36/36 and 78/78 and bindings 12/12 and 56/56
    identical; 17 dumped worlds bit-identical; the eight composite, injection and
    step-check test files pass.
  - Tier 1 + 2 gate: 355 files, no changed outcome
    ([gate](/mnt/workspaces/Cells/land-20261113a/)).
  - **Next:** the declared energy-role table (built and guarded, lands next round), then S2
    membrane state (v2 §3), with field-input providers refused above 64 field nodes.

- **BITSEY-derived identifiers renamed to neutral names (D146; 12 November).** A pure
  rename: `bitsey_emt_pair@1` → `emt_mirna_pair@1`, its observer →
  `emt_mirna_pair_pure_readouts@1`, the parameter sets → `emt-mirna-pair-scaled-simple` and
  `emt-mirna-scaled-simple`, the units → `nominal_time_unit` and `scaled_coordinate`.
  - Ten runs are bitwise identical before and after. There are no aliases: old configs
    and checkpoints are refused. Frozen inputs keep their labels, and the source stays
    cited. The old names are at tag `bitsey-names-frozen-2026-11-12` (`67f9c43`).
  - Tier 1 + 2 gate: 355 files, no changed outcome, no OOM kill
    ([gate](/mnt/workspaces/Cells/land-20261112d/)).
  - BITSEY declares no licence, so its code may not be copied.
  - **Open:** the classification of `processes/source_electrochemistry.py` (the user's
    decision); BITSEY's species names and the `source_*` names; moving the five
    `scripts/capture_*` tools into `validation/bitsey/`.
  - Evidence: [audit and identity](/mnt/workspaces/Cells/bitsey-rename-20261112-01/),
    [tests after the rebase](/mnt/workspaces/Cells/bitsey-rename-20261112-02/).

- **Current injection: first acceptance passed (Rm1 on the uncleaved egg against R-full;
  12 November).** Engine models: `resolved_pump_composite@1` over `resolved_pump_tissue@3`
  with `electrode_current_injection@1`.
  - **Definition:** R-full's own uncleaved egg (its `build()` from
    `j1_declared_inputs.json` with the record's P_old), written as `@3`; J1's pulse protocol
    (±30 nA for 1.2 s every 10 s, K 0.4912 / Cl 0.5088); J1's Rm rule on pulses 0 and 1.
    Every field matches R-full's egg; the declared differences are activities used as
    concentrations, N_A·e against F (3.4e-11) and a 1.3e-16 volume rounding.
  - **Development dt study** (seen before registration): Rm1 is 852298.5 Ω at 1 ms and
    852073.9 Ω at 0.5 ms against R-full's 852000.0 Ω. The error is second order (ratio
    4.04) and extrapolates to within about 1 Ω of R-full.
  - **Registered** in
    [`injection_rm1_protocol.json`](validation/tissue/injection_rm1_protocol.json): pass
    when |Rm1(1 ms) − 852000.0 Ω| ≤ 3 × (step term 224.58 Ω + reference term 1.7e-6 Ω) =
    673.74 Ω. The judged run happens once, from a clean snapshot of main.
  - **Judged run: pass.** Rm1 = 852298.5 Ω, +298.5 Ω against the 673.74 Ω tolerance,
    from a clean snapshot of main at `2aa2793` (CPU 5, no OOM). It equals the 1 ms
    development run bit for bit, as expected on CPU.
  - Evidence: [development](/mnt/workspaces/Cells/composite-v2-20261112-01/rm1-dtstudy/),
    [judged](/mnt/workspaces/Cells/composite-v2-20261112-01/rm1-judged/judged.json).

- **Combined landing: the plan-validation fix, composite v2 §1.2–§1.4, the L4 agreement
  driver, `electrode_current_injection@1` and the J1 diagnostic code (12 November).** One
  tier 1 + 2 gate on the combined tree: 355 files, no changed outcome, no OOM kill
  ([gate](/mnt/workspaces/Cells/land-20261112b/)). New test files measured into the tier
  record: four in tier 1, `test_current_injection_runs.py` (81 s) and
  `test_division_diagnostic_record.py` (30 s) in tier 2, and the ring-model record test
  (about 150 s) in tier 3.
  - **Plan-validation fix.** `bind_step_checks(spec)` binds `resolved_pump_tissue@1`–`@3`'s
    step checks to their definition. The observation boundaries, the explicit, calcium and
    junction bounds, and the gated RK4 laws are evaluated once per definition rather than
    once per 1,024-step chunk; `core.grid.clock_checks` gives `checked_grid` and the
    projective clock admission the bound checks with no control tables. Other models keep
    `check_steps` per chunk.
    - Refusals, messages and their order are unchanged; the traced step, layouts, initial
      states and controls hash identically.
    - The 825-node clock check drops from 59.6 CPU-min to 6.9 s; on the L4 the W1 probe's
      plan validation takes 106 s.
    - All 29 related files pass at the fix head, the composite's tier-3 files included
      ([evidence](/mnt/workspaces/Cells/clock-validation-20261112-01/summary.json)). One
      failure, `test_numerical_refinement.py::test_legacy_hash_and_empty_omission` (a
      fingerprint literal), also fails on main before the fix; the tier record times that
      file out, so it carries no outcome.
    - **Open:** the composites (water `@1`, `@2`, replacement `@1`) still check per chunk,
      with 5, 6 and 2 layout builds; `pump_composite` adopts binding next (v2 §1.1).
  - **Composite v2 §1.2–§1.4 (D143).** Operators declare `REPLACES`, `VIEW_READS`,
    `ACCEPTS_WRITES` and `EVENT_REPLACES`, checked at registration and at composite build:
    writers follow the owners that accept their fields, view readers follow providers, and
    each observation column has one owner. Replacement is a declared chain in operator
    order, the last replacer owning the column; the reviewed one-replacer rule would have
    refused water@2 as qualified. Returned columns are checked against the declaration on
    every row, and the field-to-owner map is written to all three manifest writers.
    - Guards against snapshot `8416a72`: jaxprs 36/36 and 78/78 and bindings 12/12 and
      56/56 identical; 17 dumped worlds bit-identical; composite test files 59/59 and the
      frozen models' own files 130/130.
    - Not yet enforced: free-energy booking by events and split parts (needs §1.1).
      `ACCEPTS_WRITES` and `VIEW_READS` have no production user yet.
  - **L4 agreement driver** (`validation/tissue/composite_l4_agreement.py`). It runs each
    qualification's own engine functions (W1, W2, G2-Q1), measures the backend and
    run-to-run terms and writes PROPOSED variant protocols with the widening and stop
    rules. CPU dry runs give zero terms and the registered tolerances unchanged. Judged
    runs of G2-Q1, W1 and W2 now accept only the registered protocol or a registered
    backend variant of it. The L4 runs wait for the GPU.
  - **`electrode_current_injection@1`.** A scheduled current into a cell through declared
    carrier fractions (K 0.4912 / Cl 0.5088), both polarities, separate supply and removal
    bookings, and refusal when a cell cannot supply a carrier. It is split around the step
    (not coupled into RK4, so stationary analyses exclude it), and borrows the replacement
    law's free-energy terms until §1.1. Not yet accepted; its first acceptance (Rm1 on
    R-full's uncleaved egg) lands next.
  - [Composite evidence and log](/mnt/workspaces/Cells/composite-v2-20261112-01/HANDOFF.md).

- **Cell division S0b: J1 diagnostic arms on R-full. No single arm gives both J1's level
  and the registered time course; cause not isolated (12 November; development, not judged).**
  - **What ran:** the arms registered at `cfe0fa3`
    ([rationale](validation/division/j1_diagnostic_arms.md)), on R-full only, from a clean
    snapshot of branch commit `556b5eb` (merged with this entry). 3.9 CPU-hours in detached
    units on CPU 5, plus a one-point Radau check; every unit exited 0.
    [Evidence](/mnt/workspaces/Cells/cell-division-s0b-20261111-01/j1-diagnostic-01/):
    `g1/` (A1, A2, A4, A7a, A7b), `a3/`, `a6/`, `radau_check/`.
    - No engine run, and no C1 or J2 quantity. The only root searches are each curve's
      A/L → 0 end and A6's fits to each arm's own Em2 and Rm2; nothing targets J1's Em.
  - **Em at J1** (window −21.9 to −18.7 mV; record −12.795 mV, reproduced to 2.3e-12 V).
    Every calibrated point recalibrates on Rm1 and Rm2, so Rm at J1 is 488.00 kΩ throughout.

    | Arm | Em at J1 (mV) |
    | --- | --- |
    | A1 bath-facing fraction f, 0.01 to its end (0.0728) | −16.9 to −36.1 |
    | A2 furrow-zone conductance, to its end | −12.4 to −9.9 |
    | A3 ring lumen, calibrated (N = 1, 10, 20; w and bridge ranged) | −12.76 to −12.86 |
    | A4 old-membrane P_Cl/P_K, 0.03 to 0.12 | −12.6 to −11.9 |
    | A6 new-membrane rules and fits (all 14 fits converged) | −12.4 to −15.2 |
    | A7a access scaled with furrow depth, α 0.5 to 2 | −12.80 to −12.84 |
    | A7b late apposition, β 0.8 to 0.4 | −12.78 to −12.79 |
    | A8 (computed earlier) | −12.6 to −16.5 |

  - **A1 alone crosses the window**, at f ≈ 0.015–0.024 by interpolation. The curve is
    monotone from −13 to −36 mV at one Rm, so the crossing was expected and selects
    nothing; no f is adopted. Near it Em is still falling at J1 (D4 −0.05 to −0.08 mV) and
    Rm has no late rise (D7 −0.2 to −0.6 kΩ), against the registered p531 description.
  - **A7a is the only calibrated arm with a late Rm rise** (D7 +64, +130, +224 kΩ at α 0.5,
    1, 2), with a deeper, later Em minimum (8.7–9.7 min). Rm2 fixes the access at J1, so
    A3, A7a and A7b stay within 0.07 mV of the record there.
  - **Shared by every calibrated arm:** the Rm fall is front-loaded (D5 0.85–0.94, except
    A1 from f 0.03 and A2 from half its end); the Em minimum comes at 7–10 min; cytosolic
    Na at J1 is 20.0–20.2 mM against the measured 22.4 ± 1.1 mM.
  - **Without a rim restriction** (the geometric-access check) Rm at J1 is 104–108 kΩ,
    4.5–4.7× below Rm2. Its N = 10, w = 2.5 µm point **failed** (integration failure at
    insertion onset, 420–421 s); it is recorded in `a3_final.json` and not rerun.
  - **Fig. 2 values**, read after the runs from one egg and not registered targets: D2 ≈
    −10 mV, D3 ≈ 15 min and −19.5 mV, D4 ≈ +2.5 mV, D5 ≈ 0.46, D6 ≈ 0.64, D7 ≈ +80 kΩ.
  - **Deviations from the registration:**
    - A3 used BDF with a batched finite-difference Jacobian, not a declared sparsity
      pattern; the Radau check on the N = 10 default point agrees to 2e-13 V.
    - A3 used two undeclared numerics: a 1e-11 m² seed face per ring and a 1e-12 mM
      concentration floor in the log-mean flux.
    - The snapshot is of the branch commit, not main.
    - A1's curve ends at f = 0.0728 (root search), not the estimated 0.10.
    - The Radau check ran from a driver in the evidence folder; it is now the runner's
      `radau-check` group, not rerun.
  - **Code:** `validation/division/cleft_egg_reference.py` (extended; the null path is
    unchanged), `cleft_rings_reference.py` (A3), `j1_diagnostic_runner.py`; tests
    `tests/unit/test_division_diagnostic_*.py` (11 + 2 + 1 pass).
  - **Next:** the cleft-model choice is the user's (a registered combination round,
    freezing candidates for C1, or parking it). C1 and J2 stay held.

- **Heredity pilot W1, water arms: held discs also hold under water; the osmotically
  balanced start, not water itself, makes the marginal loss 3× earlier (11–12
  November; development, not judged).**
  - **What ran:** the sheet70 discs under `resolved_pump_water@1` and `@2` (KCC at
    red-cell capacity 4, s 1), dt 5 ms, plus a water-off control.
    - Predictions were written first.
    - There were no refusals and no volume censors.
    - The four arms killed by the 12 November crash were rerun.
    - [note](/mnt/workspaces/Cells/heredity-pilot-w1-20261110-01/sheet70w/NOTE-water-sheet-results.md),
      [summary](/mnt/workspaces/Cells/heredity-pilot-w1-20261110-01/sheet70w/summary-sheet-arms.json)
  - **Retention is as in fixed volume.** In both water models, 37-cell discs held 70 min
    at s 1.0, 0.6 and 0.3, and 19-cell discs held at s 0.6 and 0.3.
  - **The 19-cell disc at s 1.0 was lost at 345–348 s after the cue**, against 990.5 s
    in fixed volume (5 ms runs, 1 s records).
    - **Re-timed at 1 ms (12 November):** water1, water2 and the water-off control lose
      the disc in the same 1 s brackets as at 5 ms (347–348, 345–346 and 304–305 s), with
      per-cell Vm within 0.02 mV before the loss. Fixed volume at 1 ms lost it at 990.46 s,
      so the shift is 2.85× (water1) and the water-dynamics effect +14.1%. Snapshot
      `source-w1a-02` (`f42eaa4`);
      [comparison](/mnt/workspaces/Cells/heredity-pilot-w1-20261110-01/sheet70w/retiming-1ms.json).
  - **The cause is the start state.**
    - The declared heredity H is hypo-osmotic, 284 against 300 mOsm.
    - Under water each cell starts at its model's balanced stationary H: 0.942 V0, 1.7 mV
      more polarised, K 144 rather than 136 mM.
    - The water-off control (balanced start, `@3` at fixed volume) lost the disc at
      304–305 s.
    - So water dynamics move the loss by only about 14%, and the +1% swelling before the
      loss slightly delays it.
  - **Loss account, refined.**
    - Every disc loads Na after writing, from 6 to 10–11.6 mM by about 10 min, and drifts
      more polarised.
    - Na load does not separate lost from held discs. The drift does: just before
      collapse the most depolarised cell sat near −27 mV in the lost discs, against −20
      to −23 mV in the held ones.
    - Candidate carrier: Na-driven drift together with a small disc and strong coupling.
      Untested.
  - **Water matters for slow composition and volume.**
    - Solute loading is the same in every model: 11.7–12.5% content excess at 70 min.
    - Under water it shows as swelling from 0.94 to 1.03–1.06 V0.
    - Disc K is 7–8.5 mM lower than in fixed volume.
    - KCC at capacity 4 is invisible over 70 min, but caps stationary D at 1.47 V0 instead
      of 1.76.
  - **Predictions** held as written, except two:
    - the marginal loss came earlier under water, a direction not predicted;
    - the control lost its disc at 304 s, against a predicted 330–370 s.
  - **For the E07-v1 redesign** (the user's decision):
    - start from a balanced H;
    - use water2 for hour-scale renewal, with water1 and a higher KCC capacity as
      robustness arms;
    - s 0.6 with a 37-cell disc is safe for retention, though pre-screen 8 found renewal
      failing at every coupling that retains;
    - turnover results are pending.
- **Composite tissue model landed (12 November; D143).** `resolved_pump_composite@1` is
  `@3`'s own step plus declared operators ([PUMP_COMPOSITE.md](docs/PUMP_COMPOSITE.md)).
  `resolved_pump_water@1`, `@2` and `resolved_pump_replacement@1` are now thin
  compositions; none had to stay frozen.
  - **In-tree guards, all bitwise equal:**
    - the empty composition equals `@3` (9/9 cases, and the 825-node world);
    - water test worlds 15/15; replacement 17/17;
    - W1's six judged trajectories, its stationary states and a 60 s drift;
    - W2's 8 arms;
    - G2-Q1's 9 cases with device checks on every row;
    - W37; Q5 (2 step sizes); Q6 cohorts.
  - **Cross-revision guards** (frozen `8416a72` against the converted tree):
    - jaxprs with dt traced: 36/36 on the base worlds, 69/69 on the qualification worlds,
      78/78 at the head;
    - bindings at every step size used;
    - W2's judge on all 8 arms identical;
    - 17/17 saved runs bit-identical;
    - the frozen models' own tests, unmodified, 130/130 against the thin modules.
  - **Step studies:** W1's dt study and 6 of Q5's 8 worlds were not rerun. The argument
    for equality (dt-traced jaxprs, with bound shapes and bindings checked at every step
    size) is written into the evidence README with its limits.
  - **Gate:** tiers 1 and 2 at `3f7d93e`, 349 files, none changed. The composite's
    identity, water and replacement files are tier 3: 12–23 min each, and they need more
    than 3 GB in one process.
  - Integration grants no new acceptance. GPU agreement by tolerance is pending.
  - Evidence: `/mnt/workspaces/Cells/composite-s1-20261111-01/README.md` and
    `land-composite-20261112-01/`. Landed at `54a2ea0`.
- **Plan-validation fix accepted on the L4; full-tissue hold segment 1 started (12 November).**
  - **The fix:** `bind_step_checks(spec)` evaluates `@1`–`@3`'s definition-only
    step-check quantities once per definition, not once per 1,024-step chunk. The
    definition stays unchanged, and the traced code hashes identically before and after.
  - **On CPU,** the 825-node clock check drops from 59.6 min of CPU to 6.9 s:
    - layout builds from 8,240 to 2;
    - control tables from 4,120 to 0.
  - **The acceptance probe on the L4** (from `source-09`, main `efa8267` plus the fix,
    into `fulltissue-v2/`):
    - start, prepare and probe all exit 0;
    - the probe wrote 10 windows, with all six worlds at t = 8 s and no failed check;
    - plan validation took 106 s, against a 40+ min stall before; compile 210 s.
  - **Segment 1** (1,200 s of model time, snapshots every 300 s) has run from the same
    snapshot since 18:39.
    - The measured rate is 11.1 s per 200-step window of six worlds. That projects to
      about 18.5 h per segment and about 65 h for the whole hold on the L4.
    - GH200 arrives next week. Each 300-s snapshot is a point to reassess.
  - **Open findings:**
    - `run.json` reports 0.41 ms per batch step against 55 ms seen, so the per-window
      wall lies outside every recorded timing;
    - `experiment.changes` is recomputed on every access, at 13.6 ms each;
    - the composite and the models that wrap `@3` still rebuild per chunk. Their owner
      adopts the fix.
  - The fix lands after a rebase onto the composite.
  - Evidence: `/mnt/workspaces/Cells/clock-validation-20261112-01/summary.json`.
- **Out-of-memory crash and relaunch (12 November).**
  - **Cause:** at 01:36:13 UTC the composite S1 guard on the water@2 qualification
    worlds was 8.2 GB resident, mid-compile. It set off a machine-wide out-of-memory
    kill. systemd then stopped the whole terminal-session scope that held it, and with
    it the lead session, its agents and every detached job (setsid does not leave the
    cgroup). Nothing ran from 01:36 to 12:30.
  - **Cut short:** outputs are kept with the suffix `.killed-oom-20261112`.

    | Work | State at the crash |
    | --- | --- |
    | W1 water sheet arms | 8 of 12 finished. Killed: `water2-disc37-s0.6` at t = 4080 of 4200 s, and `water1-disc19-s0.6` and `water2-disc19-s0.3` about 30 min in. `water2-disc19-s0.6` never started |
    | W1 full-tissue cost probe | Started 23:25. It wrote no window in 2 h 10 min, against a measured 482 s compile at 64 worlds, so it never finished; cause unknown. The first segment never started |
    | Turnover pre-screen | 3 of 21 arms finished. 2 were killed and 16 never started |
    | J1 band | 4 of about 24 members done: the default and 3 one-at-a-time members, −12.67 to −12.89 mV |
    | J1-state step study | RK4 0.05 ms, rfull and compare missing |
    | 35-min egg smoke | Never started |
    | Composite S1 guards | `w2` killed; `scale` killed |

  - **Fix:** [`scripts/run_detached.sh`](scripts/run_detached.sh) runs each long job as
    its own systemd user unit in `cells.slice`.
    - Each unit has its own memory cap, and the slice caps the total at 16 GB.
    - `OOMPolicy=continue` keeps a queue going past one killed item.
    - A positive `OOMScoreAdjust` makes a Cells job the victim before the user's other
      services.
    - Tested: a unit over its cap is killed alone.
    - Subagents' long test runs go through it too.
  - **Relaunched from zero:** same snapshots and arguments; the new launchers record
    why. The band and the longsheet part have no resume.
    - The J1 band ([`queue_rerun.sh`](/mnt/workspaces/Cells/cell-division-s0b-20261111-01/rfull-band-01/queue_rerun.sh), CPU 5).
    - The J1 step-study remainder, then the smoke ([`queue_j1_rest.sh`](/mnt/workspaces/Cells/cell-division-s0b-20261111-01/static-cleft-steps-01/queue_j1_rest.sh), CPU 7).
    - Water queue A ([`launch6.sh`](/mnt/workspaces/Cells/heredity-pilot-w1-20261110-01/launch6.sh), CPU 0).
    - The composite `w2` guard alone, with 11 GB, to measure its peak.
  - **Started at 13:01**, after the `w2` guard passed with an 8 GB peak:
    - water queue B;
    - the turnover remainder ([`arms-rest.sh`](/mnt/workspaces/Cells/heredity-turnover-literature-20261111-01/arms-rest.sh)
      with `queues-rest.json`; `queues.json` unchanged);
    - the cost probe alone, with a 45-min limit and Python's fault handler.
  - **Finished by 13:00:** the J1 band, its arms and time course; the step-study
    remainder; the 35-min smoke (see the S0b entry below).
  - **Cost probe diagnosed: an engine performance bug, not a GPU hang.** Rerun alone on
    CPU 6 from 13:01, it again wrote no window. At 40 min a SIGABRT dumped its stack
    ([log](/mnt/workspaces/Cells/heredity-pilot-w1-20261110-01/logs/ft-costprobe.log),
    exit 134).
    - It sat in host-side plan validation. `_validate_window_plan` checks the whole
      declared clock, 4218 s at 1 ms, in chunks of at most 1024 steps.
    - For each chunk, `check_steps` recomputes bounds that depend only on the definition,
      through `initial_values`, which includes the 825-node field bind.
    - An engine fix, computing those bounds once per definition with no numerical change,
      is in progress. The GPU segment waits for it.
  - **A further fix:** the step study's `compare` part had written the J1 comparison over
    the activation one, because it used one file name for both starts.
    - Both are kept now: `compare.json` was regenerated from the same snapshot and inputs,
      and the J1 result is `compare_j1.json`.
    - The driver now writes one file per start (`45fc727`).

- **Cell replacement qualified and landed (11 November).** `resolved_pump_replacement@1`
  is an opt-in wrapper over `resolved_pump_tissue@3`.
  - **What it does:** scheduled newcomer events with waste and supply ledgers and
    lineage, with the literature-based delayed junction-formation law, and both
    newcomer kinds (isolated template and donor copy, D139).
  - **Judged run G2-Q1:** one run from a clean snapshot of `81d5de7`, with protocol and
    predictions byte-equal to main `2cd2b3a`
    ([evidence](/mnt/workspaces/Cells/cell-replacement-g2-20261111-01/qualification/judged-01/README.md)).
    All 7 items pass:

    | Item | Result |
    | --- | --- |
    | Ledgers | Worst energy residual 9.8e-7 of flows |
    | Event map against an independent operator | 0.0041 of tolerance |
    | Trajectories against an independent reference | 0.44 of tolerance, as second order predicts |
    | Fast-chain end states | Identical in all six cases |
    | Order | 2.05 and 2.07 (amendment A3) |
    | Restart and vmap | Bitwise, or within 9.5e-15 |
    | 825-node no-event equivalence | Bitwise |

  - **Caveats:** in Q4 only the end states discriminate, because the voltage ratio is
    1/3 by construction. Q5 mostly measures a newcomer relaxing on its own.
  - **Limits:** in-place swap only (no vacancy); the donor copy does not halve the
    parent; the water inner model and finite extracellular worlds are stage 3.
  - **Gate:** tier 1+2 from a clean snapshot of the merge `2f372c5` (337 files) changed
    one file, `test_betse_tissue_contact.py`. Its BETSE reference refused to start for
    lack of its 4 GiB disk reserve while the workspace disk was full. Rerun from the
    same snapshot after space was freed, it passes as recorded (16 passed, 1 skipped).
    The tier-3 and new files pass in full. The tier record adds the two new files
    (271/66/196, with `test_cell_replacement_vector.py` in tier 3: 85–101 s against the 90 s cap).
- **Parity on the L4: variants registered (11 November).** None of the 12 P2–P4b
  protocols allowed a GPU run, so each has a registered L4 variant built by
  `validation/betse/backend_variant.py`
  ([evidence](/mnt/workspaces/Cells/parity-l4-20261111-01/)).
  - **CPU against L4:** Vm up to 1.1e-14 V and cell ions up to 1.9e-13 relative.
    Bitwise CPU reruns confirm this is the backend alone.
  - **L4 run to run:** Vm up to 6.5e-16 V and cell ions up to 1.0e-14 relative.
  - Both terms are at least 1e5 below every tolerance, so no tolerance changed.
  - **Rehearsal:** a full-size run of the judged chain on a non-registered case passed
    (worst 0.60 of tolerance; not a verdict).
  - **Judged L4 runs: all 12 pass (11 November, 21:18–22:40 UTC).** Each protocol ran once
    from a clean snapshot of the registering commit `25d0fe9`, host on CPU 6
    ([margins](/mnt/workspaces/Cells/parity-l4-20261111-01/judged/margins.json)). All 24
    run and compare steps exited 0, and none was refused.

    | Protocol | Worst, fraction of tolerance |
    | --- | --- |
    | P2 stage 1 | 0.996 (cell K, as on CPU) |
    | P2 direct | 0.30 |
    | P3, four cases | 0.27–0.29 |
    | P4 | 0.29–0.31 |
    | P4b | 0.35–0.48 |

    - **Status line:** the registered variants differ from the drafts only in their status
      line. The drafts are kept beside them.
    - **What this establishes:** every parity rung so far now passes on CPU and on the
      L4.
- **MG1 qualified and landed (11–12 November).** `apical_vertex_mechanics@1`,
  `mechanical_equilibrium_analysis@1` and `junction_tension_inference@1` passed protocol
  v2.
  - **Judged run:** 57 of 57 criteria, run once (judged-02, 20:27–22:42 UTC) from a clean
    snapshot of `840488e`
    ([results](/mnt/workspaces/Cells/morphogenesis-mg1-20261111-01/judged-02/results/results.json),
    [margins](/mnt/workspaces/Cells/morphogenesis-mg1-20261111-01/judged-02/margins.json)).
    Re-judging the saved results reproduces the verdict.
  - **Weaker evidence by its own rules:** v2 follows the failed judged-01, and values were
    seen while diagnosing it (disclosed in v2).
  - **Tightest margins:**
    - the barrier vanishes at p0 = 3.82, 0.0081 above the window's 3.8119 lower bound;
    - Euler order 0.998;
    - I3 slopes 0.997–1.002 (noise 1e-9 to 1e-7);
    - small-cut recoil slope 0.999.
  - **Other values:** rigidity vanishes at p0 = 3.7224 for every r; 144 barrier paths, none
    failed (max |F| 9.8e-12).
  - **Gate:** tier 1+2 from a clean snapshot of the merge `90ceec5` (337 files) matches the
    record. The 9 new test files pass in full and enter the tier record (1 in tier 1,
    8 in tier 2; 272/74/196).
  - **Process slip, disclosed:** the merge was pushed at about 23:00 UTC together with
    J1's registration, before this gate finished at 23:48. The gate then passed with no
    changes, so nothing was reverted.
- **MG1 v2 registered; judged run under way (11 November).**
  - **The two failures were diagnosed:**
    - The barrier crash was a genuinely flat landscape where a compatible start
      loses compatibility. It is fixed with a trust-region Newton step and a
      force-residual polish.
    - I3's registered noise range was past the linear regime.
  - **v2:** the same 57 criteria and thresholds. Its noise levels come from a
    reference-only study and a rule fixed in advance. It discloses what was seen during
    diagnosis, and a pass is labelled weaker evidence.
  - **Dry run:** a full-scale run on non-registered inputs passed (144 barrier paths,
    none failed).
  - **Timing, disclosed:**
    - v2 was committed on main at `699e96d` (20:25:59 UTC);
    - the judged run started at 20:27:57 from a clean snapshot of `840488e`, which
      contains it (empty patch; protocol bytes equal main's);
    - the commit was pushed at about 21:17, after the run began.
- **Cell division S0b: J1 prediction of record and verdict; J1 fails on the reference (12 November; development).**
  - **J1's declared inputs** were registered at `d7a1797` before any model computed an
    Em.
  - **The reference:** R-full, an independent numpy/scipy model of the egg with its
    restricted cleft (`validation/division/cleft_egg_reference.py`; 17 tests pass).
    - It calibrates the old membrane on pulse Rm1 = 852 kΩ and the cleft access on pulse
      Rm2 = 488 kΩ.
    - It predicts **Em = −12.795 mV** at onset of second cleavage, under the defaults.
    - The prediction was committed at `7c1b70c` before any band member ran
      ([record](validation/division/j1_prediction_of_record.json)).
  - **Against the data:** the measured value is −20.3 ± 0.8 mV, so the default sits 7.5 mV
    (9.4 SE) above it.
  - **Verdict, 12 November: J1 fails on the reference (R-full) within the declared
    ranges.** There is no engine run yet, and the cause is not isolated
    ([verdict](/mnt/workspaces/Cells/cell-division-s0b-20261111-01/rfull-band-01/results/j1_verdict.json);
    declared inputs unchanged since `d7a1797`).
    - **The band:** one-at-a-time members, summed worst case, corners checked. It runs
      from −14.58 to −11.32 mV.
    - **Width:** W = 3.26 mV, with t = 0.18 µV. That is inside the 8-mV maximum, so J1 is
      judged.
    - **The miss:** the band lies wholly above the datum's ±2 SE window of −21.9 to
      −18.7 mV, and misses it by 4.1 mV.
    - **Largest shifts:** the new membrane's P_Na/P_K (0.42 mV) and the Rm2 and Rm1 targets
      (0.37 and 0.33 mV). No corner falls outside the summed band.
    - **In R-full at J1:** the lumen holds 29 mM K, against 0.55 mM in the bath, and
      21 mM Na, against 47 mM. The K potential across the new membrane is about −14 mV.
  - **Arms and limits (reported, not banded):**

    | Case | Em (mV) | Rm (kΩ) | Measured |
    | --- | --- | --- | --- |
    | Cation-selective rim | −16.5 | 488 (calibrated) | – |
    | Constant-field access | −12.6 | 488 (calibrated) | – |
    | 0.5 µm gap | −12.7 | 488 (calibrated) | – |
    | Bath-equivalent lumen (limit) | −69.4 | 125 | – |
    | Sealed lumen (limit) | −9.9 | 852 | – |
    | Exposed arm −VM | −54.4 | 309 | −60.0 ± 2.5 mV, 336 ± 31 kΩ |
    | Exposed arm +VM +CCB | −61.4 | 199 | −60.9 ± 3.4 mV, 165 ± 10 kΩ |

    - The exposed arms are the data the new-membrane rules came from, and they do not
      fit cleanly: +VM +CCB Rm is 3.4 SE from its mean, and −VM Em 2.2 SE.
    - Cytosolic Na at J1 is 20.1 mM; dL74 measured 22.4 ± 1.1 mM.
  - **What it means:** the declared model as a whole misses J1. Which assumption is wrong
    is not isolated.
    - The measured Em lies between two readings of the same Rm 488 kΩ. All new membrane
      behind a restricted lumen gives −12.8 mV; a bath-exposed patch gives −37 to −44 mV.
      A mix of the two can reach −20.3 mV, so a match alone proves nothing.
    - dLB74's 0.14 mm² "exposed to the outer medium" (p535) is not independent evidence.
      It is calculated from the same Rm series (1148 ± 104 kΩ, n = 17, the parallel
      reading of Rm2) as the bath-exposed reading.
    - The declared assumptions with independent evidence against them in the papers:
      - a uniform, constant old membrane; K83 measures 4–30 times more current in the
        old membrane beside the furrow;
      - a well-mixed lumen with one access path, for a furrow about 150 µm deep and
        2 µm wide;
      - no Ca²⁺ or Cl⁻ currents; K83 assigns old-membrane inward current to Na⁺, Ca²⁺
        and Cl⁻;
      - the new-membrane rules, given the exposed-arm misfit above.
    - **The time-course shape differs too** (reported, single traces). In R-full, Em
      steps to −15.2 mV at 8 min and then relaxes to −12.8 mV as the lumen fills with K.
      Rm falls mostly within 7–10 min (852 to 525 kΩ). dLB74 describes Em falling about
      10 mV gradually over 7–17 min, with Rm falling over the same period.
  - **Next (the user chose this with the advisor, 12 November):** a diagnostic on R-full.
    - The arm file is registered on main before any run. J1 is now a selection datum.
    - Each arm states its change, its source and what is recalibrated.
    - An arm that adds an unknown with no measurement of its own is reported as a curve
      of Em against that unknown at fixed Rm. No value is picked from Em.
    - Arms are compared on the time-course shape as well as on Em at J1.
    - No model computes J2 until a revised model is frozen. The revision comes back to
      the user with the results.
    - Composite S1 and the division operators continue unaffected.
  - **Rerun check:** the four band members finished before the crash were recomputed on
    the rerun and agree to every printed digit.
  - **Static cleft egg as a plain `@3` definition:**
    - **1 ms is refused** by @3's explicit-rate bound (dt × rate = 1.145); 0.5 ms and finer
      are accepted. The division work therefore needs about 0.5 ms or an implicit
      membrane–cleft term.
    - **Energy ledger:** with the whole 1.39 mm² patch switched on uncharged at once,
      the energy ledger fails at IMEX 0.5 and 0.25 ms (37% and 6.9% of flows) and nearly
      closes under RK4 at 0.1 ms. Whether gradual insertion stays within the bound is
      pending.
    - **From R-full's J1 state, over 2 s:** IMEX ARS(2,2,2) passes every check on every
      row at 0.5, 0.25 and 0.125 ms, and agrees with R-full to 3e-10, 1e-11 and 2e-12 V.
      The energy-ledger failure belongs to the switch-on transient.
    - **RK4 from the same state:** at 0.1 and 0.05 ms it agrees to 5e-13 V, but fails the
      electrode ledger on 19,511 and 38,761 rows (225 and 599 times its bound). This is
      consistent with the latent `@3` RK4 electrode rounding recorded on 11 November: the
      excess grows with the step count at the two step sizes run
      ([comparison](/mnt/workspaces/Cells/cell-division-s0b-20261111-01/static-cleft-steps-01/results/compare_j1.json)).
  - **Egg smoke to 35 min:** the uncleaved egg on `@3`, at IMEX 1 ms for 2100 s through
    the vector-window runner, is accepted.
    - Device checks passed on every row, and the worst ledger reached 5.3e-4 of its bound.
    - Wall time 228 s ([result](/mnt/workspaces/Cells/cell-division-s0b-20261111-01/smoke-35min-01/results/long.json)).
    - On a free core the band members took about 40 s instead of 8–17 min. Last night's
      long times were likely from sharing cores at nice 10 (not measured).
  - **Engine gaps:**
    - no current-injection control, so Rm cannot be run on the engine yet;
    - the explicit-rate bound at 1 ms;
    - the energy ledger in a stiff switch-on transient;
    - RK4 electrode-ledger rounding over long runs.
  - Evidence: `/mnt/workspaces/Cells/cell-division-s0b-20261111-01/`.
- **Cell division: design note (draft) and egg-scale smoke test (11 November).**
  [CELL_DIVISION_DESIGN.md](docs/CELL_DIVISION_DESIGN.md) answers D142. One composite
  pump-tissue model runs `resolved_pump_tissue@3`'s own step plus declared operators
  (water, replacement, division); new combinations are definitions, not model families.
  It is merged as a draft for review, before any model produced an Em for the first
  judged observable.
  - **Smoke test:** one Xenopus-egg-sized cell at rest, on `@3` and on
    `resolved_pump_water@1`, 60 s at 1 ms with host and device checks on every row
    ([evidence](/mnt/workspaces/Cells/cell-division-20261111-01/scale-smoke-01/)). It was
    accepted, with every ledger at most 1% of its bound; Vm −9.945 mV; fluxes equal an
    independent constant-field calculation to 8 digits.
  - **Scale:** the egg's volume is about 10⁶ times a heredity cell's, six orders of
    magnitude, not nine as first stated.
  - **Engine gaps found:**
    - `surface_tissue.check_definition` has an absolute 1e-20 C bound on the gap
      between the charge anchor and the inventory. An egg built like the heredity
      fixtures misses it by 1.2e-20 C, whereas one float64 step of its fixed background
      is 1.8e-19 C. It should scale with Σ|zFn|, as the running ledgers do. The same
      module also has an absolute energy floor (`ENERGY_ATOL_PJ`) to review. The fix
      lands separately, with the gate.
    - The pump-tissue family has no current-injection control. Rm must be the simulated
      response to dLB74's pulse protocol, because constant-field membranes rectify.
  - **Next (S0b, before any composer code):** an independent numpy reference of the
    cleft egg and J1's prediction of record; a static cleft-egg step study if it can be
    written as a plain `@3` definition; the pulse-response Rm; the smoke test to 35 min.
- **Cell division, stage 1 (11 November).** Verified data for the
  [cell-division plan](docs/CELL_DIVISION_PLAN.md) (D141):
  - Xenopus goes first;
  - the first judged observable is blastomere Em at 2 and 4 cells, with Rm from the
    same eggs as calibrator;
  - new cleavage membrane is low-resistance and mainly K-selective.

  Evidence: `/mnt/workspaces/Cells/cell-division-20261111-01/verification/`.
- **Heredity pilot W1, water arms (11 November; development, in progress).** The
  sheet70 discs are rerun under `resolved_pump_water@1` and `@2`, with predictions
  written first ([runs](/mnt/workspaces/Cells/heredity-pilot-w1-20261110-01/runs.jsonl)).
  - **Three of 12 arms done:** the 37-cell disc held for 70 min at s 1.0 (water, and
    water with KCC) and at s 0.3, with no refusal and no volume censor.
  - **Swelling:** disc cells swelled to 1.03–1.06 V0, about 12% over their start.
    Solute loading matches fixed volume, now taking the form of swelling.
  - **KCC effect:** small, as predicted.
  - **Running:** the 19-cell discs at s 1.0, under both water models.
- **Workspace disk (11 November).** `/mnt/workspaces` filled, which is what blocked the
  BETSE test above. At the user's direction, the AI scientist project folder
  `groups/35` (564 GB, 49,589 files) moved to
  `/mnt/datasets/workspaces-archive-20261111/groups/35`, leaving a symlink. It was
  checked file by file
  ([log](/mnt/workspaces/Cells/disk-move-20261111-01/move.log)), and 523 GB is now
  free.
- **Heredity pilot W1: the cue writes discs; fresh discs hold for 70 min (10–11
  November; development, not judged).** Driver `validation/tissue/heredity_pilot.py`
  on `resolved_pump_tissue@3`; evidence `/mnt/workspaces/Cells/heredity-pilot-w1-20261110-01/`.
  - **The cue:** an added Na leak at 9× each disc patch's leak for 2 s, through the
    engine's channel availability schedule. No engine gap.
  - **Full 825-node heterogeneous tissue at s 1.0 (replay):** 19- and 37-cell discs
    were written within 0.4 s and stayed fully D through the run, with no D outside.
    The default @3 refuses the cue step (junction-heat refusal, below). The
    opt-in junction-heat booking accepts it, with the energy ledger closing to about
    1e-7 of flows.
  - **Held-bath 127-cell sheet, cue-written discs, 70 min at dt 5 ms** (six arms,
    none refused, no D outside any disc;
    [summary](/mnt/workspaces/Cells/heredity-pilot-w1-20261110-01/sheet70/summary-six-arms.json)):
    - **Five held to 70 min:** 37 cells at s 1.0, 0.6 and 0.3, and 19 cells at s 0.6
      and 0.3.
    - **The 19-cell disc at s 1.0 was lost all at once,** 990.46 s (16.5 min) after
      the cue in a 1 ms replay, inside the 5 ms run's bracket. All 19 cells went to
      H within 0.12 s; no check failed and no step was refused.
    - **Before the loss it was drifting toward U, with K and M not loading** (Na
      loaded to 11.6 mM). Just before collapse its Vm was about −32 to −27 mV, with
      K 134.6 and M 11.2 mM (content excess 2.7–3.1%). A range of −37.8 to −30.6 mV
      quoted here earlier was sampled mid-collapse, 0.06 s before the first flip;
      corrected 12 November. The held discs had instead loaded to K about 146 and M
      about 22 mM by 70 min. So the loaded-composition limit from pre-screen 9 does
      not explain this loss; the small disc at strong coupling slid toward the
      unstable state before it could load. The mechanism is not yet identified.
    - **Predictions:** written beforehand, they predicted loss at s 1.0 for both
      sizes. The 19-cell prediction held; the 37-cell one was falsified.
    - **Osmotic excess** (against each cell's own start) passed 10% at 56–58 min in
      the held arms and peaked at 11.7–12.1% (censor 15%).
    - Held baths supply K without limit, so loading may be overstated.
  - **Control:** started from pre-screen 7's loaded disc with no cue, the driver
    loses the disc in 0.56–0.62 s, as pre-screen 7 does.
  - **L4 reproducibility:** runs on the L4 are not bitwise reproducible from run to
    run, with or without the junction-heat option (likely atomic scatter-adds).
    Bitwise restart on the GPU would need deterministic XLA ops, whose cost is
    unmeasured. One L4 refusal (pilot-03, 0.047 s) did not reproduce.
- **MG1 (2-D vertex mechanics) judged run: FAIL (11 November).** Protocol
  `mg1-vertex-mechanics-v1`, registered at `70f5456`. Run once on CPU from a clean
  snapshot of `db82f63` (the MG1 branch rebased on `70f5456`; empty patch; protocol
  bytes equal main's)
  ([results](/mnt/workspaces/Cells/morphogenesis-mg1-20261111-01/judged-01/results/results.json)).
  - **52 of 57 criteria pass:** the case-I ground state, the box stress, ordered-
    network rigidity, recoil after a junction cut, numerics (RK4 order about 4,
    Euler about 1), tension inference with known pressures, and the tyssue
    comparison.
  - **The barrier part failed** before judging: its contraction minimizer did not
    converge (`ConfigError`), so criteria B1–B4 have no values and count as failed.
  - **I3 (noise linearity of tension inference) failed** on its own values.
  - Per the outcome rules, thresholds are not changed. The causes are being
    diagnosed (development). Any rerun is a new judged run under a v2 protocol,
    with all 57 criteria, this run kept on record, and a pass labelled weaker
    evidence. I3's window will not be re-derived from engine output.
- **Osmotic water and volume qualified and landed (11 November).**
  - **`resolved_pump_water@1`:** osmotic water and compliant volumes on
    `resolved_pump_tissue@3`, through a Strang split around @3's own step.
    - With water off it is bitwise @3 on CPU (single cell, 7-cell sheet, 825-node
      tissue, vmap).
    - **W1 judge: 25 of 25 pass,** one run from `628a3d0`, against predictions P1–P6
      frozen from an independent numpy/scipy reference (`b0ff7e2`). Every trajectory
      sits at about 1/3 of its tolerance, i.e. the engine's own 1 ms step error. The
      engine converges on the reference at second order.
    - **Procedure:** the W1 tolerances were pinned on the agent's branch (`628a3d0`)
      before the run, but not publicly registered on main first. P5 is judged on
      volumes and concentrations only (its Vm is constant by construction), as
      decided before any judged result.
    - Predictions to compare later, not claims: with water, the heredity D state
      swells to 1.76 V0 (approved parameters).
  - **`resolved_pump_water@2`:** adds a KCC-type K⁺/anion symport
    (`k_anion_symport_mass_action@1`). Its stationary judge passed 24 of 24; D
    swells 1.1–1.5× instead of 1.76×.
  - **Global-charge bound:** the ledger now gets the per-step rounding allowance of
    the other running ledgers, with no trajectory change. Reduced sensitivity: a
    persistent supply-booking leak is caught only above about 2.5 eps × moved charge
    per step. Global-charge ratios recorded before and after are not comparable.
  - **Also:** an opt-in membrane-process hook in @3 (default off, unchanged), and
    volume blocks in `stationary_continuation_analysis@1` (existing IDs bitwise
    unchanged).
  - **Gate:** tier 1+2 from a clean snapshot of the merge (334 files, none changed).
    15 tier-3 and new test files pass in full.
  - **1 h drift of the D state** (3.6e6 steps at 1 ms, no refusal): volume moves by
    2e-16 pL, Vm by 4.3e-14 V and concentrations by 3e-14 mM. Every ledger stays at
    rounding (energy 7e-8 pJ).
  - Evidence: `/mnt/workspaces/Cells/water-volume-pump-20261110-01/` and
    `/mnt/workspaces/Cells/land-water-20261111-01/`.
- **In development on branches, not yet on main (11 November):**
  - **Cell replacement:** `resolved_pump_replacement@1` (G2), with a
    literature-based junction formation law (D139). Stage 1 is built and tested;
    the donor-copy template is being added.
- **Cortés-Poza (2026) Phase 0: reproduction with corrections and a plain baseline
  (11 November; tooling, D137, no Cells engine model).** The author's code at `2b53a08`
  (MIT) was run out of process, with the review's corrections and a plain
  bistable-chain baseline
  ([plan, Phase 0 results](docs/CORTES_POZA_2026_TEST_PLAN.md); evidence
  `/mnt/workspaces/Cells/cortes-poza-2026-phase0-20261111-01/`).
  - **Regeneration fidelity:** 1.00 only with the one-sided coded metric. Two-sided
    agreement is 0.63–0.93, below 0.95 in every run, and the plain chain recovers
    better.
  - **Full-model energy:** rises in 93% of steps, through the omitted dG/dt term.
  - **Memory switching curve:** a formula. Simulated, slow memory erases the
    patterns.
  - **Remark 4:** a 4× typo.
  - **Thresholds:** the nucleation and switching thresholds also appear in the plain
    chain.
  - **For Phase 1:** test bistability, pinning, nucleation and strength–duration
    switching in Cells against the plain baseline.
  - **Limits:**
    - N, seeds and grids that the paper does not give were chosen by us;
    - regeneration outcomes were identical across seeds, so each condition is
      effectively one trial;
    - the long-horizon controls used one seed;
    - the paper's figures were not seen.
- **Heredity pre-screen 9: newcomer rules under turnover (10–11 November;
  development, not judged).** Driver `validation/stationary/heredity_turnover.py`
  (`e06b104`), on `resolved_pump_tissue@3` sheets; 51 runs plus mechanism and
  frozen-composition checks, none refused.
  - **Control rule (open newcomer gates):** the rim stays H and the disc erodes or
    unzips; B1 fails at s 0.3 and 0.6, as predicted.
  - **Inherited gates:** gates to H neighbours carried across the replacement
    (state inheritance, against D133). They renew the rim only partly at s 0.6:
    J 0.811 after one turnover, 0.297 after two.
  - **91-cell disc at s 1.0** (homogeneous, inherit): J = 1.000 through two full
    turnovers, every newcomer converted. A heterogeneous 37-cell world at s 0.6
    fails B1 in the first turnover.
  - **Newcomer composition:** converted newcomers start at H composition and pull
    weaker. They load with τ 40–50 min, and junction conductance rises with ion
    content (×1.57 D–D).
  - **Fresh discs:** at fresh composition, discs are retained to about 3× stronger
    coupling in fast mode (19 cells to s 2.23, 37 cells to 3.10, against 0.766 and
    1.05 loaded).
  - Replacement is done by the driver (engine gap G2, next in the feature queue);
    the gate rate is not configurable (G6).
  - Evidence: [summary](/mnt/workspaces/Cells/heredity-design-20261108-01/prescreen-09-turnover/summary.md),
    `final.json`.
- **Caveat on heredity pre-screens 7–9 (10 November).** Every pre-screen starts
  from the stationary written disc, whose D cells carry the fully loaded slow
  composition (Na+K+M+P about 372–380 mM against 284 mM for H, +31% osmolarity, past
  E07-v1's 15% censor). A disc written by the cue starts with H composition; K and
  anions load with an effective time constant of 40–50 min (pre-screen 9's mechanism
  run). The sign of the effect is mixed: on the held-bath sheet, cue-written 19-cell
  discs at s 1.0 were still held after 20 s where pre-screen 7 predicts loss within
  1 s, while freshly converted cells are weaker neighbours for rim conversion
  (pre-screen 9). A control in W1's driver, started from pre-screen 7's loaded
  disc with no cue, loses the 19-cell disc at s 1.0 in 0.56–0.62 s (pre-screen 7:
  0.5–1 s), so the drivers agree and the starting composition explains the
  difference (development run). A frozen-composition stationary comparison of the
  mechanism (junction conductance rises with ion content in the constant-field law,
  ×1.57 on a D–D junction) is queued. Until they and the
  fresh-disc runs (70 min, with composition and osmotic excess) report, pre-screen
  7's retention thresholds, the "12 of 14 arms fail" reading and the
  stage-A-at-x0.3 recommendation are on hold.
- **Parity P4b, the heredity carrier channels, passes (10 November).** Two protocols,
  registered at `acd4ead` (a merge, so the derivation revision `6239c5d` stays
  reachable), judged once each from a clean snapshot of it on CPU, both phases
  judged, no refusals
  ([judged](/mnt/workspaces/Cells/parity-p4b-channels-20261110-01/judged-01/), `margins.json`).
  `resolved_pump_tissue@3` with NaV1.2, Kir2.1, Na leak and K leak populations against
  BETSE's general network (`Nav1p2`, `Kir2p1`, `NaLeak`, `KLeak`) on the rung-1
  mammal world.

  | Case | Verdict | Worst item | INIT Vm (tol.) | SIM Vm (tol.) |
  | --- | --- | --- | --- | --- |
  | h1: NaV1.2 + leaks in INIT, Kir2.1 on at SIM | pass | 0.41 (INIT ECM M) | 0.40 mV (2) | 0.94 µV (6) |
  | h2: Kir2.1 + leaks in INIT, NaV1.2 on at SIM | pass | 0.35 (SIM ECM Ca) | 0.47 mV (2) | 1.71 µV (20) |
  | kir-h: Kir2.1 alone, tissue Na leak ×0.2 (registered `bc86673`) | pass | 0.35 (SIM ECM M) | 0.30 mV (1) | 4.2 µV (40) |
  | nav-kleak: NaV1.2 + K leak at rest −21.2 mV (registered `f79cc30`; own order check fired, dt/100 terms) | pass | 0.475 (SIM ECM M) | 0.53 mV (2) | 0.39 µV (3) |

  - Each channel's effect over the observed error: NaV1.2 Vm 25 (INIT) and 3661 (SIM
    switch-on); Kir2.1 Vm 18 (INIT) and 1485 (SIM switch-on); cell Na and K 130–1800.
  - Formulation check first: Cells' `nav1p2_m3h_regularized@1`, `kir2p1_mh2@1` and
    `naleak_always_open@1` equal BETSE's classes to 5e-14 over −120…+60 mV (Cells
    uses the analytic limits where BETSE gives NaN at −25, −40 and −65.000123 mV).
  - INIT Vm sits at BETSE's own 10 ms step term (0.40 and 0.48 mV measured).
  - **Limits:**
    - **NaV1.2 voltages:** covered from 0 to −16.9 mV (h1), −27.9 to −34.2 mV (h2) and
      0 to −21.2 mV, resting at −21.2 mV (nav-kleak), which includes the heredity D
      state (−21.5 mV). Its lower window (−60 to −35 mV) and the unstable point
      (−39 mV) are not exercised.
    - **Kir2.1 voltages:** covered from 0 to −34.2 mV (h1, h2) and 0 to −91 mV
      (kir-h). kir-h rests at −91 mV, not at H; it passes −80 mV only on the way down
      in INIT, at BETSE's 10 ms steps.
    - **Kinetics:** almost untested. Only NaV1.2 h's lag enters (h2 SIM); τ_m and the
      Kir2.1 time constants are not tested.
    - CPU only, one geometry.
- **Latent RK4 electrode rounding in `resolved_pump_tissue@3` (11 November).**
  - **Where it shows:** under RK4, the electrode ledger integrates stage currents
    and does not see the rounding of large amount increments.
  - **When it trips:** in plain @3 increments stay small, so this is latent. After
    a whole-content swap in cell replacement, the gap random-walks past the bound
    (5.5e-24 against 2.2e-24 C in 51 steps).
  - **Not affected:** IMEX books the electrode from rounded states, so it telescopes
    exactly.
  - **Handling:** `resolved_pump_replacement@1` adds an allowance for replaced slots
    only. @3 itself is unchanged.
- **Known refusal in the pump family (10 November).** `resolved_pump_tissue@1`–`@3`
  refuse any step in which a junction's power falls by more than about 59%:
  ARS(2,2,2) books junction heat with weights (δ, 1−δ), δ = −0.707, so the booked
  increment goes negative and trips the strict dissipation check. It occurs at
  heterogeneous cue onsets (W1 pilot, 5.000→5.001 s) and on homogeneous sheets
  during disc loss. Stage powers are nonnegative analytically, so an in-step bound
  would never fire; that fix (option I) is withdrawn, and a single wrong-signed
  junction booking is never caught by the energy ledger.
  - **Fix landed 11 November (gap A):** an opt-in `"junction_heat_booking":
    "trapezoid_nonnegative@1"` on @3. Junction heat is booked as dt·(q_start +
    q_end)/2, with no extra field solve.
    - Default runs and fingerprints are unchanged. With the option, trajectories are
      bitwise the default's on CPU; only junction heat differs. The strict row tests
      are kept.
    - The cost is +0.45% on the L4 at 64 worlds.
    - With the option, the 5 ms collapse and the full-tissue cue step are accepted,
      with energy residuals of about 1e-7 of flows.
  - **Host-cost fix landed with it (gap B):** `held_controls` reads the schedule's
    change times once per call, so output is identical and the host overhead per
    world-step is gone.
  - **Gate:** tier 1+2 from a clean snapshot of `bd0a41d` (327 files, none changed).
    The tier-3 files touching @3 and the vector windows also pass, run in full
    (ledger rounding 41, @3 35 + 1 skip, device checks 45, junction heat 5, vector
    windows 8 + 1, v3 6 + 1).
  - **Seven E/C test files** (projective, projective runner, and five stationary-
    analysis files) were missing from the tier record, so the routine gate never
    ran them. All pass (47 tests) and are now in tiers 1 and 2. The new junction-heat
    test is in tier 3.
  - Evidence: `/mnt/workspaces/Cells/land-gapA-gapB-20261111-01/`.
- **Parity P3 (scheduled interventions, first subset) passes (10 November).**
  Four protocols, `validation/betse/protocols/physical_p3_*_dense.json`, registered at
  `95f30b5` on `resolved_pump_tissue@3` with the event adapter (`ac2e127`): pump
  block, Na mem ×10 and K mem ×10 on a 19-cell spot, and Na mem plus a full
  gap-junction block. BETSE's events are additive ("multiplier m" gives (1+m)×
  base); pump and junction blocks are global; the junction block maps only as a
  full step held to the end of SIM.
  - The event emulator reproduces plain BETSE to roundoff (SIM Vm 3.2e-13 V), and
    every case's INIT is bitwise rung 1's.
  - Verdict on SIM only; INIT is reported, not judged (event-free and already
    judged in rung 1 and P4; decided before any P3 INIT error was seen).
  - SIM Vm effect over tolerance: pump 197, Na 40, K 113, junction block 102. ECM
    does not move in 35 ms and is listed as non-discriminating.
  - Method: pinned (3 × measured terms); step terms at dt10 with a dt100 order
    check (observed order 0.996–1.086, window 0.9–1.1); no BETSE fine runs (step
    error through the emulator); within-cell patch spread measured by propagation
    instead of P4's heuristic.
  - **Judged once each** from a clean snapshot of `95f30b5`, CPU, 16 min; no refusals
    ([judged](/mnt/workspaces/Cells/parity-p3-interventions-20261110-01/judged-01/), `margins.json`):

    | Case | Verdict | Worst SIM item | SIM Vm error (tol.) | Vm error / raw term sum |
    | --- | --- | --- | --- | --- |
    | Pump block | pass | Vm 0.29 | 2.0 µV (7) | 0.92 |
    | Na mem ×10 | pass | Vm 0.27 | 107 µV (400) | 0.92 |
    | K mem ×10 | pass | ECM K 0.27 (non-discriminating) | 3.5 µV (30) | 0.50 |
    | Na mem + junction block | pass | Vm 0.29 | 14 µV (50) | 0.97 |

  - The measured term sums predict the Vm errors (0.92–0.97 of the raw sum in three
    cases), so the ×3 factor is the whole margin. Na mem's tolerance is wide because
    BETSE advances the junction gate once per ion per step (a 99 µV term).
  - The worst SIM cell Na, K, Cl and M errors are identical in all four cases: the
    offset carried from the shared INIT end, not the events (which move these ions
    10–100× their tolerances). So the cell-ion verdicts lean on the INIT end state,
    which is reported: worst INIT item cell Ca at 0.30 of tolerance, Vm 132 µV (500).
  - **Limits:** Cl mem is not judged (engine gap); sharp steps only, no ramps; the
    junction block only as a held full step; CPU only, one geometry, one 19-cell spot,
    35 ms SIM; all ECM entries non-discriminating.
  - Engine gaps (Cl/Ca mem, environment, temperature, ECM break, external voltage)
    are proposals on hold. Evidence: `/mnt/workspaces/Cells/parity-p3-interventions-20261110-01/`.
- **Device checks and batched worlds for `resolved_pump_tissue@3` landed (10 November).**
  `surface_pump_v3.device_checks` runs @3's own domain, ledger, bound and
  dissipation checks on the device through the shared `row_checks`, with the
  host's functions, names and messages; `ionic_worlds@1` admits @3 under the
  opt-in `world_batching="vmap"`. Host checks and trajectories are unchanged.
  - **Tests:** device and host give the same verdict and first message on 20
    seeded faults covering all 12 checks, at step 0 and 3.6e6; batched
    heterogeneous worlds match single-world runs to 1e-12 relative, and bitwise
    with rewrites disabled; a fault in one world stops vmap and `lax_map` at the
    same step. The four new or changed files are tier 3 (275–604 s each).
  - **Heredity tissue (825 nodes, 2580 channel populations):** host and device
    checks agree on 129 rows on CPU and on the L4 (largest diagnostic
    difference 3.5e-3 of the smallest bound); batched worlds agree with single
    worlds to 1.1e-15 V on the L4.
  - **L4 throughput per world-step:** 12.5 ms at 1 world, 2.64 ms at 64, 2.34 ms
    at 128 and 2.28 ms at 256 (execute only; @1 was 2.10 ms). End to end, with
    host observers every 128 steps, 4.0–4.5 ms. 256 worlds need a preallocated
    allocator on the L4 (on-demand allocation ran out of memory; both failures
    are kept).
  - **Cost:** E07-v1's tier 1 (1,786 world-hours) is about 4,100 L4 GPU-hours
    execute-only (2.28 ms) and about 7,200 end to end with observers (4.01 ms),
    against the design's assumed 560–840 (4.9–13×). The earlier @1 figure of
    6,800 below is end to end. GH200 throughput is the open number.
  - **Gate:** tier 1+2 passed on the branch (326 files; `test_projective_judge`
    then differed only because it predated amendment 2), and again on merged
    main `e79c0b7` from a clean snapshot (266 + 60 files, none changed).
  - Evidence: `/mnt/workspaces/Cells/device-checks-v3-20261109-01/` (gate,
    `study-01-cpu`, `study-01-gpu`, `study-02-gpu`) and
    `/mnt/workspaces/Cells/land-v3-device-20261110-01/`.
- **Projective (C) qualification qual-01: FAIL (9–10 November).** Protocol
  `projective-c-qualification-v1` with amendments 1 and 2, judged once from a
  clean snapshot of `ca70d4a` on CPU float64
  ([judgement](/mnt/workspaces/Cells/projective-c-20261109-01/qual-01/judgement.json)).
  Two cases pass, four fail, F2 is not yet evaluable.
  - **Fails only on the absolute caps** (|dVm| ≤ 20 µV, |dc|/c ≤ 2e-4, the parity
    tolerances), in Q1, Q2, F1 and A1. |dc|/c reaches 1.25e-3 (Q1, F1), 1.16e-3
    (Q2) and 1.53e-3 (A1). The worst entry is cytosolic Na (about 6 mM, |dc| about
    8 µM), over the cap from the first observation after the window opens (60 s).
    |dVm| stays within 20 µV except in A1 (62 µV).
  - **Passes:** pre-run burst growth (0.024 < 0.1), accuracy against the
    estimator allowance in every case (worst ratio 0.40–0.51), energy (defect at
    most 0.09 of its bound), conservation, and F1's fallback around the cue.
  - **Reading:** the per-jump tolerance of 1 µM, summed over 100–170 jumps,
    admits about 0.16 mM, while the cap admits about 1.2 µM at 6 mM Na. The
    error estimator was accurate, but the tolerance it was held to was looser
    than the caps. The verdict stands; a later qualification needs error control
    budgeted against the caps.
  - Reported speed-up: 2.2–3.5× fewer fine steps, 1.4–3.3× wall time.
  - **F2 (switch near the fold) is not evaluable:** the registered NaV1.2
    pre-scan (13 runs on the L4,
    [prescan.json](/mnt/workspaces/Cells/projective-c-20261109-01/qual-01/f2-prescan/prescan.json))
    selected no scale, so the judged pair was not launched. The D state survives
    1800 s at scale 0.72 (Vm −28.2 mV) and switches within 3 s at 0.71, so no
    point on the 1% grid lingers for the required 200–1200 s. A usable F2 needs a
    protocol change (a finer scale step or another starting state).
- **Heredity pre-screen 8: newcomer conversion next to the retention window
  (9–10 November; development, not judged).** Driver
  `validation/stationary/heredity_conversion.py` (`370ceb6`), on
  `resolved_pump_tissue@3` through `stationary_continuation_analysis@1` plus
  600 s forward runs; homogeneous sheets; 63 runs, none refused.
  - **No coupling renews the whole disc** (19, 37, 61, 91 cells). Corner rim
    newcomers never convert: they stay H up to s 0.7 and destroy the disc from
    s 1.0 or at the window edge. Centre newcomers convert everywhere in the
    window; mid-side ones only near s 0.5–1.0; outside newcomers never.
  - A 9-cell rim batch at s 0.2 stays H (disc holds 28 of 37 for 600 s); at
    s 0.7 the disc is lost in 0.5 s.
  - Rim newcomers are insulated by their closing junction gates (the design's
    self-insulation risk). Under oldest-first turnover the disc erodes, so B1 is
    predicted to fail at every retaining coupling; A1 and C1 are unaffected.
  - Closers: seed 3's cells 64 and 73 have no D state at their draws (low NaV with
    high Kir); 10% CV moves the 37-cell boundary by −6%.
  - Evidence: [summary](/mnt/workspaces/Cells/heredity-design-20261108-01/prescreen-08-conversion/summary.md),
    `final.json`.

- **Parity rungs P2 and P4 pass (9 November).** The five protocols were
  registered at `621e2be` and judged once each, from a clean snapshot of that
  commit, on CPU
  ([evidence](/mnt/workspaces/Cells/parity-rung2-4-20261109-03/), `margins.json`).
  Tolerances use the pinned method (3 × the sum of measured terms), with no
  provisional terms. Each protocol lists its non-discriminating quantities, and
  no claim rests on those.
  - **P2 stage (i)**, the verdict: `resolved_pump_tissue@2` (field solver @3)
    against the BETSE-order emulator with Cells' harmonic faces, at BETSE dt/100.
    The reference is first order: observed order 1.00–1.01 over dt/10–dt/300.
    PASS. The barrier claim rests on:
    - ECM K: worst error 0.17 of tolerance, with the barrier effect 252× the error;
    - cell Na, K, M and Cl: effect 3–13× the error.
    Cell K passed with almost no margin: 0.984 (INIT) and 0.996 (SIM) of a
    2e-8 tolerance. The error is about 3.8× the raw term sum, at a
    tight-junction boundary cell.
  - **Attribution after the verdict** ([evidence](/mnt/workspaces/Cells/parity-rung2-4-20261109-04/attribution.json)):
    - The rung-1 convention set the exterior-field Boltzmann term to 0 for
      non-Ca cell ions. Measured by propagation through the reference
      emulator, it is 6.2e-8 for cell K, and 6.3e-7 for Na, 2.7e-7 for Cl and
      9.4e-9 for M.
    - With that term included, the cell-ion tolerances would be 10–100× wider,
      and cell K, Na, Cl and M would not discriminate the barrier.
    - **So P2's barrier claim rests on ECM K alone**, whose field term was
      already in the sum (effect 43× the tolerance, 252× the error). The verdict
      stands, but the cell-ion discrimination reported above is withdrawn.
    - The observed cell-K difference has the opposite sign to both measured
      field terms, so its mechanism is unidentified (open). A next step would
      drive the emulator's membranes with Cells' actual exterior concentrations.
    - **Method for later rungs:** no term is cut off by an absolute threshold.
      Every cell-ion field term is measured by propagation, at the cost of one
      emulator run. A term may stay unmeasured only under a recorded bound of at
      most 10% of the measured sum for the same quantity, phase and ion.
      Heuristic scalings follow the same rule: the X_ext concentration
      heuristic overstated the direct value 1600×.
  - **P2 stage (ii)**, the emulator against plain BETSE (tooling): PASS, worst 0.33.
  - **P2 direct**, Cells against BETSE: reported only; PASS, worst 0.30.
  - **P4 KLeak** (`resolved_pump_tissue@3` with channel populations, BETSE's
    general network): PASS, worst 0.29. The channel's effect is 46× the error on
    INIT Vm and 1.2e4× on SIM Vm.
  - **P4 Kv1p5+KLeak:** PASS, worst 0.31. Kv1p5's effect is 1.7e3× the error on
    SIM Vm.
- **MG0b bistable domain wall passes (9 November).** `resolved_pump_tissue@3`,
  unmodified (IMEX ARS(2,2,2), field solver @2, dt 1 ms, CPU, float64), ran on chains
  of resolved cells with Kir2.1, NaV1.2, leaks and gap junctions. The protocol
  `mg0b-domain-wall-v1` was registered beforehand (`f7e8b6b`), with its
  predictions set from theory and an independent reduced model before any
  engine run of the wall. The run used a clean snapshot of that commit
  ([results](/mnt/workspaces/Cells/morphogenesis-mg0-20261109-01/judged-02-mg0b/results/results.json),
  52 min). All 19 criteria pass, and re-judging the saved results gives the same verdict:
  - wall width against √G: fitted slope 0.521 (window 0.45–0.55; reduced 0.520);
    engine against reduced wall width 0.5–1.0% (allowed 5%); time step 1 and
    0.5 ms against 0.25 ms, profile to 1.2e-7;
  - pinning: below the predicted critical coupling the wall moves 0.06 cells
    (allowed 0.5); at 2× it moves +5.8 cells into H (reduced +5.7);
  - hysteresis: uncoupled loop 0.40 (reduced 0.425); a uniform chain matches
    one cell exactly; anchored loops narrow 0.30 → 0.125 → about 0 with
    coupling (reduced 0.35, 0.15, 0.0);
  - cut and restore: the written domain returns (Jaccard 1.0), the controls
    hold, no domain appears without a write;
  - energy balance 2.2e-5 relative (bound 2e-3); worst global charge 0.09 of
    its bound;
  - 36 registered theory and reduced-model values reproduced, largest
    relative difference 0.5%.
  Known weaknesses were recorded before the run (`lead_review`). B4 judges
  |shift|, but the observed shift has the predicted sign. B5 accepts equal widths,
  but the observed widths narrow strictly. At this coupling B6's return is close
  to guaranteed, so it tests the cut machinery, not memory. Limits: 1-D chain,
  junction gating held open, fixed volume, runs of 6–58 s.
- **Ledger rounding fix landed (9 November; `5ba4426`..`9f59fb0`).**
  - **What changed:**
    - The electrode increment is booked from the start and end charge states.
    - The running work and material ledgers' allowance is 2.5 eps × steps × magnitude (projective bursts and jumps included).
    - Component net charge is checked in the capacitor ledgers instead of in field convergence. The gauge component's rows take the world's summed increments.
    - Opt-in field solver `capacitive_reduction_gauged_damped_newton@3` accepts Newton at its rounding floor and is bitwise equal to @2 wherever @2 converges.
  - **Same trajectories:** trajectories are bitwise unchanged on 7 definitions, and the electrode charge moves by at most 7.5e-26 C.
  - **Now completes:** the 64k-step fine reference, the MG0b wall, the 30-minute relaxing @3 worlds, the 1-hour closed fixture (worst row 2e-4 of its bound) and the P2/P4 parity cases.
  - **Detection floors:** 1e-13 fmol on a floating component. On the gauge component, 3.1e-15 fmol after 5 steps and 2.3e-11 fmol after 1e5 steps.
  - **Gate:** tier 1+2 passed with 323 files unchanged, from a clean snapshot whose tree equals `9f59fb0`.
  - **New tests:** `test_ledger_rounding.py` and `test_field_floor.py` are in tier 3 (each runs about 6 min; both pass).
  - Evidence: `/mnt/workspaces/Cells/ledger-fix-20261109-01/`.
- **Heredity pre-screen 7: written discs at E07-v1's couplings (9 November;
  development, not judged).** This ran `resolved_pump_tissue@3` through
  `stationary_continuation_analysis@1` on hexagonal heredity sheets with held baths
  (F0 surrogate) and E07-v1's junctions. Driver: `validation/stationary/heredity_prescreen.py`
  (`83b92b1`).
  - With voltage-gated junctions, the 7-, 19- and 37-cell discs are stable at x0.3
    and have no stationary state at x1, x3 or x10. 61- and 91-cell discs hold at
    x1 (critical theta 1.909 and 2.257 against 1.657). With open junctions, no
    disc holds at any arm.
  - Uniform H is stable at every arm.
  - At x1 the written 19-cell disc is lost in 0.5–1 s, and the 37-cell disc in
    30–60 s.
  - Heterogeneity at 15% CV lowers the 37-cell critical coupling by 9–16%.
  - So 12 of E07-v1's 14 stage-A write arms, and most stage-B arms, would fail
    retention by construction. The choice is with the user (D133).
  - Evidence: [summary](/mnt/workspaces/Cells/heredity-design-20261108-01/prescreen-07-stationary/summary.md),
    `final.json`. Pre-screen 8 (newcomer conversion) is above.
- **Stationary-state analysis (E) qualified (9 November).**
  `stationary_continuation_analysis@1` (`890567b`, opt-in, D135) passed all 16
  criteria of the pre-registered protocol `stationary-analysis-e-v1`
  (`2b4dd5e`). The run used a clean snapshot of that commit, on CPU; the
  verdict came from `validation/stationary/judge.py`
  ([judgement](/mnt/workspaces/Cells/fixed-points-e-20261109-01/judged-01/judgement.json)).
  It ran `resolved_pump_tissue@1` and `@3` unmodified.

  | Target | Result | Agreement |
  | --- | --- | --- |
  | Default-world cell (`@1`) | −6.07376 mV, K 239.21 mM, 493 mOsm; stable, τ 0.259 s, 189 s and 16,661 s | 3.5e-14 V against the reduced model (budget 8.8e-12); eigenvalues 1.1e-11 /s |
  | Heredity cell (`@3`) | H −79.556 mV and D −21.518 mV stable; U −39.445 mV with one unstable mode | at most 6.6e-15 V |
  | MG0b cell, fast mode | folds at u = 0.3770832491 and 0.6794743372 | 1.2e-15 from the reduced folds |
  | 61-cell sheet, written 7-cell disc, fast mode | stable up to a fold at θ = 0.10467 g_H | 8.8e-9 from an independent graph model (budget 2.8e-7) |

  Reported, not judged (no reference exists): in slow mode the disc loses
  stability through a Hopf point at θ = 0.0701 g_H (period about 112 s).
  Diagnostic D1: a 2e5 s step-map run ends where the slowest mode predicts.
  Its qualified-runner probe was refused by the ledger-rounding issue, and it
  is repeated once the fix lands.

- **Projective mode (C) landed (9 November), not yet qualified.**
  `projective_forward_euler@1` (`ab27087`, opt-in, D135) runs bursts of the
  unchanged fine engine with checked extrapolated jumps. Its qualification
  protocol is committed (`3b906ca`) and waits on the ledger-rounding fix.
  Development runs over 30 s: error at most 0.42 of the allowance, 2.5× fewer
  fine steps during relaxation.

- **Stage B landed (9 November).**
  - Neutral names throughout `src/cells`: 7 modules and more than 65 law IDs
    renamed, the junction law merged and 4 mixed modules split.
  - The physiology stack moved to `validation/betse/physiology`.
  - Hash-pinned source manifests retired.
  - No BETSE-specific ID or import remains in `src`; the boundary test
    enforces it. The remaining text mentions are source citations, which are
    allowed, plus some leftover message wording, which is a follow-up.

  Tiers 1 and 2 ran from a clean snapshot of the rebased branch (`0736231`,
  [gate](/mnt/workspaces/Cells/stage-b-20261109-01/landing-01/gate-01/)).
  Three files differ from the record:
  - two polygon-preparation files now pass in full, 77 and 78 tests, because
    the hash pins they failed on were retired;
  - `test_default_world_adapter` grew to 19 tests in the rung-1 work and now
    takes about 220 s, so it belongs in tier 3.

- **Channel model and batched worlds landed (9 November).**
  - `resolved_pump_tissue@3` (`6853aa6`) adds Kv1.5, Kir2.1, NaV1.2 and K/Na
    leak populations to the IMEX pump family, with exponential gate updates.
    - The heredity cell reproduces the pre-screen states, H −79.556 mV and
      D −21.518 mV.
    - On 825 nodes on the L4, Vm agrees with the 0.25 ms run to 7.5 nV at 1 ms
      but not at 2 ms (145 µV); CPU and L4 agree.
    - [Evidence](/mnt/workspaces/Cells/pump-channels-20261109-01/).
  - Batched worlds (`5d61544`): `run_vector_windowed` vmaps worlds, with
    domain, ledger and dissipation checks on the device.
    - Bitwise equal to single worlds on CPU with compiler rewrites off;
      5.7e-16 V on the L4.
    - L4 throughput per world-step, 825 nodes at 1 ms: 26.7 ms one world at a
      time; 2.38 ms at 64 worlds; 2.10 ms at 256; 3.79 ms end to end with
      observations. SM active 80–94%.
    - The heredity plan assumed 0.47 ms on GH200; at the L4 rate, tier 1 would
      need about 6,800 GPU-hours. A GH200 measurement is now the deciding
      input. [Evidence](/mnt/workspaces/Cells/batched-worlds-20261109-01/).
  - Gate: [tiers 1 and 2](/mnt/workspaces/Cells/land-g1-g4-20261109-01/gate-02/).
    Three files differ, none because of these changes: two read-only fixture
    copies (fixed in `7ec5589`) and the adapter file above. The 68 new tests
    pass (one skipped).
  - **Found afterwards:** long runs and worlds with many held baths were
    refused by rounding in the conservation checks, not by physics errors.
    The fix is in progress: electrode charge is now booked consistently, and
    allowances derived from rounding grow with the step count. It blocks MG0b
    and hour-scale qualification.

- **MG0a morphogen gradient passes (9 November).** `reaction_transport@1`,
  unmodified, ran under the protocol `mg0a-gradient-v1`, committed beforehand
  (`e8ded03`). The run used a clean snapshot of that commit, on CPU in float64
  ([results](/mnt/workspaces/Cells/morphogenesis-mg0-20261109-01/judged-01/results/results.json)).
  The source is a large-volume reservoir cell (the model has no source term).
  The references are independent numpy/scipy solutions. All 12 criteria pass (13 judged entries; A6 has two parts):
  - profile against the exact discrete steady state: at most 4.6e-13
    relative on strips and 3.0e-14 on the Voronoi tissue, against 1e-9;
  - decay length against √(D/k) = 19.92 µm (Kicheva 2007 wing-disc values):
    +0.072%, as predicted by the discretisation error;
  - scaling slope 0.499 (registered window 0.495–0.505); refinement order
    1.99–2.00; RK4 time-step order 4.02–4.04, resolved above the reference
    floor;
  - mass and per-cell ledgers at most 1.1e-13 relative;
  - cut and restore returns the uncut profile within 1.8e-15; the
    cut-without-restore distal fragment decays to 8e-22.

  Two design changes made after development runs are recorded in the
  protocol; no physics threshold moved. The steady state is unique, so the cut
  tests the machinery, not memory. Engine gaps found by the driver: no source
  term, no excision contract, and a closed-world balance guard that does not
  grow with step count. The guard gap limited refinement to three levels.

- **Parity rung 1 v2 passes (9 November).** Attribution of the v1 failure
  ([summary](/mnt/workspaces/Cells/parity-rung1-20261108-01/attribution-01/summary.json)):
  - **Not the Ca pump.** With matched constants, Cells' Ca-pump law
    reproduces BETSE's `pumpCaATP` exactly.
  - **The cause.** The extracellular offset is equilibrium electromigration in
    Cells' own resolved exterior field (0.8 µV interior spread). It follows the
    Boltzmann response for every mobile ion, with r = 0.81–0.94 and signs set
    by valence.
  - **The v1 flaw.** The v1 field-law proxy was one-sided: it removed only
    BETSE's drift.

  The v2 protocols (`cecfb13`) add the field term |z|F·max|φ−⟨φ⟩|/RT, from
  blind Cells-only potentials, and were committed before the fresh judged runs
  ([results](/mnt/workspaces/Cells/parity-rung1-20261108-01/judged-02/)). All
  three runs pass from a clean snapshot of `cecfb13`:
  - D on CPU and on L4 (identical): Vm 132 µV against 400 µV in INIT, 1.82 µV
    against 7 µV in SIM;
  - F on L4: Vm 1.82 µV against 20 µV; cell Ca 1.2e-3 against 5e-3;
    extracellular Ca 4.42e-5 against 2e-4.

  F's first attempt was cut off by a session crash; it is preserved as
  `F-l4-interrupted-01` and was rerun from the same snapshot and protocol.
  Because the method was revised after a failure, this pass is weaker evidence
  than a first-time pass. The same field term leaves every rounded rung-0
  threshold unchanged.

- **Parity rung 1 (mammal ion profile): pre-registered FAIL (9 November).**
  `resolved_pump_tissue@2` was judged against plain BETSE's mammal-profile
  default world (Na, K, Cl, Ca, P, M plus the plasma-membrane Ca pump) under
  protocols committed beforehand (`82452a0`). The runs were from a clean
  snapshot of that commit.
  [Results](/mnt/workspaces/Cells/parity-rung1-20261108-01/judged-01/).
  - D (CPU and L4, identical) and F (L4) all **fail on one item**: SIM
    extracellular Ca, worst relative error 4.42e-5 against a tolerance of 2e-5.
  - Everything else passes:
    - Vm: F INIT 1.82 µV against 20 µV.
    - Cell concentrations, including Ca: F INIT 1.2e-3 against 5e-3.
    - INIT extracellular concentrations, including Ca at 4.42e-5 against 5e-5.
  - The Ca offset is steady: identical in INIT and SIM, and in D and F, so it
    is not BETSE's step error. The budget predicted 1.45e-5 (INIT) and 5.3e-6
    (SIM); the likely missing term is the new mechanism itself, the Cells Ca
    pump law against BETSE's `pumpCaATP`.
  - Next: attribute it with emulator variants, then pre-register a v2
    derivation and run it fresh. The v1 failure stays on record; nothing is
    retuned.

- **Fast test tiers (9 November).** Each test file was timed separately
  (`scripts/test_tiers.py`) under a standard environment: `JAX_ENABLE_X64=1`
  and per-file output and evidence roots, run in a clean worktree. Tiers are in
  `tests/test_tiers.json`.
  - Tier 1: 260 files, about 6 min on 4 cores, 6,251 passing tests.
  - Tier 2: 62 files, about 11 min, 2,659 passing tests.
  - Tier 3: 173 files exceed the 90 s cap and are run deliberately.
  - 73 tier-1 and 8 tier-2 files fail at baseline: stale hash pins, missing old
    evidence files, and one test still importing a deleted frozen module. The
    gate flags only changes from these recorded outcomes; cleaning them up
    belongs to stage B.
  - [Measurements](/mnt/workspaces/Cells/test-tiers-20261109-02/measure/measured.json),
    plus the first full pass under `test-tiers-20261108-01`.

- **Heredity design and re-hosting probe G0 (8–9 November).**
  - **E07-v1 design:** "write, release, replace", in [the design doc](docs/HEREDITY_FIRST_EXPERIMENT.md).
    Single-cell pre-screens find NaV1.2 window current plus Kir2.1 bistability
    (H −79.6 mV, D −21.5 mV). Tier-1 JUPITER cost is about 12,500 GPU-hours
    with today's sequential kernels and about 840 with 64-world batches, so
    batched worlds are on the critical path.
  - **G0 probe** ([summary](/mnt/workspaces/Cells/rehost-g0-20261108-01/summary.json)):
    two_task and unstimulated_readout on `resolved_tissue@2` (RK4).
    - Stable only at dt ≤ 62.5 ns.
    - The source-cell cue response is 6.62 µV, about 3,000× the 2 nV readout
      margin, and dt refinement changes it by under 1e-8 nV.
    - The old BETSE-order archive gives 6.632 µV (same direction, not parity).
    - Neighbour cells move only 0.5–1.1 nV, below the margin, so the old
      decodability results rest on few cells.
    - IMEX with channels is still needed for µs steps.

- **First BETSE parity of Cells' own physics: default world passes (8 November).**
  Model `resolved_pump_tissue@1` (IMEX ARS(2,2,2)) on BETSE's default world (222
  cells, 25×25 extracellular grid), judged against plain BETSE under protocols
  committed before the runs (`3c09891`). The runs were from `ba8694f` with a clean
  tree, and each named its protocol and geometry hashes.
  [Summary](/mnt/workspaces/Cells/default-world-parity-20261108-01/judged-01/summary.json).

  | Protocol | INIT Vm (tol.) | INIT cells | Interior ECM | SIM Vm | Verdict |
  | --- | --- | --- | --- | --- | --- |
  | D vs BETSE 10 ms, CPU = L4 | 131 µV (400) | 2.8e-6 (9e-6) | 3.9e-4 (2e-3) | 2.27 µV (7) | pass |
  | F vs BETSE 0.1 ms, L4 | 2.27 µV (20) | 1.0e-7 (4e-7) | 3.9e-4 (2e-3) | 2.27 µV (7) | pass |

  - Each difference matches its predicted budget term. D's INIT maximum is
    BETSE's own 10 ms step error (127–130 µV, at 0.33 s). With that removed (F),
    Cells and BETSE agree to 2.27 µV over a 22.8 mV INIT change, against a
    3.4 µV predicted budget (constants, field law, exterior potentials, BETSE's
    residual step). The 3.9e-4 ECM difference is the conservative-stencil term,
    a deliberate Cells model difference.
  - Health: 1 Newton iteration per field solve; global charge ≤3% of its bound.
    D took 4 min on the L4 and 7 min 22 s on CPU; F took 19 min 44 s on the L4.
  - **Limits of this claim.**
    - One seeded geometry and BETSE's default mechanisms only: four ions, leak,
      Na/K pump, gap-junction gating, extracellular electrodiffusion. No
      channels, networks or interventions.
    - SIM is nearly flat in BETSE (Vm moves 3 µV), so INIT carries the test.
    - venv is not compared, because the field models differ by design.
    - The next mechanism families follow the parity ladder in the coverage map.

- **Difference budget and first blind resolved run (8 November).**
  [Index](/mnt/workspaces/Cells/default-world-parity-20261108-01/index.json).
  - **Emulator-only budget** (dense default world; `difference_budget.json`):
    - BETSE's own 10 ms INIT step versus dt/100 differs by up to 130 µV in Vmem
      (at 0.34 s; 4.9 nV by the end of INIT; first order), 2.8e-6 in cell
      concentrations and 3.6e-5 in ECM concentrations.
    - BETSE's rounded constants versus CODATA give a steady 1.22 µV.
    - The ECM maximum sits on the boundary ring, which BETSE resets every step
      and the resolved model holds as reservoirs. Ring sites are excluded from
      judged ECM concentrations.
  - **Blind resolved run** (`resolved_pump_tissue@1`, ARS(2,2,2) at 1 ms, real
    geometry; BETSE histories not read):
    - It stopped near 2 s on the global-charge check. That bound is a fixed 3e-25 C,
      while reservoir supply accumulates about 1e-9 C, so float64 rounding
      (about 3e-16 relative) crosses it. A scaled bound is in progress.
    - Up to then everything held: 1 Newton iteration per window, material ledger
      within 3.6e-15 fmol, CPU vs L4 within 3e-15 V. About 90 ms per step on CPU
      and 60 ms on the L4.

- **Stage A: copied BETSE code removed from the engine (8 November).** 716 files
  deleted, 63 adapted, 1 added. Deleted: 243 `src` modules (the 207
  `betse_native_*`/`betse_normal_*`, 34 BETSE glue modules, and 2 BETSE-only
  processes); 233 validation files; 240 tests. Three engine seams were cut with
  no behavioural change: the mitochondria source label is now a literal of the
  same value, and the BETSE-mesh bridge in `conservative_polygon_geometry` and
  the BETSE grid-audit entry in `rectangular_environment` are removed.
  [Evidence](/mnt/workspaces/Cells/engine-cleanup-stage-a-20261108-01/verify/summary.json).
  - Polygon tests now use `tests/fixtures/conservative_polygon_generated.json`,
    exported once from the old generator; replayed geometry is identical.
  - Guards pinning edited files were re-pinned to a fixpoint (18 src, 35
    validation records); entries for deleted files were dropped, and all other
    entries are unchanged.
  - **Verification** against the unmodified tree:
    - test collection is identical apart from the adaptations, with the same 13
      pre-existing `runs/` errors;
    - imports of 1,675 modules are identical;
    - targeted tests (39 files) show 0 new failures, and 90 now pass that failed
      on a stale pin;
    - 115 fail on both sides with identical messages.
  - **Full suite not run:** the whole suite is too slow here (about 3% after 2.7
    hours; [stopped attempt](/mnt/workspaces/Cells/engine-cleanup-baseline-20261108-01/attempt-02-infeasible/NOTE.json)).
    A fast tiered gate is needed.
  - Remaining for stage B: BETSE-named engine modules and IDs, plus BETSE-side
    `*_native.py` tools and records in `validation/betse` that refer to deleted
    components.

- **`resolved_pump_tissue@1` at BETSE default-world scale (8 November).** New
  identity: resolved field + Na/K pump + physical-time junction gate
  (`junction_voltage_relaxation@1`), 200–400 K, no channels. The new field-solver
  version (Cholesky-factored, ≤2048 nodes) leaves the field law unchanged.
  [Index](/mnt/workspaces/Cells/resolved-tissue-scale-20261108-01/index.json),
  on a synthetic 825-node world with BETSE default coefficients.
  - **Stiffness:** with BETSE's real face conductances, explicit RK4 is only stable
    below about 69 ns (extracellular charge relaxation through faces against the
    patch capacitors). New IMEX solvers treat face electromigration implicitly:
    `imex_ars222_face_electromigration@1` (order 2.0 measured) and
    `imex_euler_face_electromigration@1`.
  - **Accuracy:** ARS(2,2,2) Vm error 13 nV at 1 ms over a 0.256 s INIT window and
    47 pV in SIM at 0.1 ms; material ledger ≤2.3e-16 fmol; capacitor-charge
    residual about 1e-28 C. Equivalence checks: factored vs dense field ≤1e-12;
    channel-free `resolved_tissue@2` 1.4e-14; CPU vs L4 within family bounds.
  - **Cost and limits:** INIT 5 s takes about 6.5 min on CPU and 2.5 min on the L4;
    face diffusion limits explicit stability to about 7 ms, and the identity
    enforces dt ≤ 3.4 ms. `tests/unit/test_surface_pump.py` passes 43, with 1
    L4-only skip on CPU.
  - **Energy bounds (condition met):** the IMEX energy-identity checks use
    relative bounds (2e-3 ARS, 2e-2 Euler) instead of the family's absolute 2e-8
    pJ, since neither scheme integrates the energy identity exactly. The residual
    converges at each scheme's order with no plateau (Euler 1.00, ARS 2.00; at
    825 nodes the largest ARS residual is 9.5e-7). A fast test asserts the order,
    and the RK4 path keeps the absolute bound
    ([study-03](/mnt/workspaces/Cells/resolved-tissue-scale-20261108-01/index.json)).
  - **Global-charge bound:** now 3e-25 C + 256·eps·(charge moved) rather than a
    fixed 3e-25 C, which float64 rounding crossed once reservoirs had supplied
    about 1e-9 C. The full 5 s INIT on real BETSE geometry completes (L4, 249 s)
    with a worst residual-to-bound ratio of 0.0125; an injected error of 10× the
    bound still fails (study-04).
  - Added to the ionic ensemble list; two windowed ensemble worlds reproduce the
    plain run's final state bitwise.

- **BETSE-order emulator out of the engine; comparison pipeline proven (8 November).**
  The seven BETSE-order modules (spatial, active, junction, specs, models) and
  their four configs moved to `validation/betse/emulator/`. The engine registry,
  spec and schedule entries are removed. [Index](/mnt/workspaces/Cells/default-world-parity-20261108-01/index.json).
  - The emulator matches plain BETSE to roundoff with BETSE's constants:
    Vmem ≤ 3.2e-13 V against a 22.1 mV INIT change (dense case), with
    concentrations ≤ 1.1e-14 relative, on both CPU and L4 (CPU vs L4 ≤ 2.5e-13
    V). This validates the extract → adapter → run → layout → comparator chain.
  - Standard (CODATA) constants alone change Vmem by 1.22 µV in INIT and 0.19 µV
    in SIM.
  - Assays and tests that ran this model through the engine runner are skipped
    with one reason (D131; last runnable at `432e62b`), not deleted. The
    re-hosting work list is `validation/betse/emulator/rehost_pending.json`.
    Every module-skipped test already had errors at HEAD (stale source-hash
    checks, native re-capture subprocesses).
  - The resolved-tissue adapter backend is written but not yet run. SIM must
    continue from the Cells INIT end state: BETSE's INIT end leaves up to
    5.9e-13 C on isolated extracellular squares, which the resolved closure
    does not admit.

- **L4 platform checks and JUPITER preparation (8 November).**
  [Index](/mnt/workspaces/Cells/jupiter-platform-20261108-01/index.json) of runs,
  inputs, results and failures.
  - GPU unit tests 33/33; integrated ensemble on GPU vs CPU 7/7; GPU
    integration (real pause/resume) 7/8.
  - **Known failure:** `test_signal_pause_and_exact_integrated_resume[ionic]` fails
    at ≤2.4e-15 relative when processes share the persistent JAX compilation
    cache, and passes with `JAX_ENABLE_COMPILATION_CACHE=false`; in-process
    pause/resume is bit-exact. Cross-process bitwise replay therefore needs the
    cache disabled.
  - Ensemble smoke (`spatial_extracellular@2`, 32 worlds): pause within 2.8 s of
    SIGUSR1, resume 32/32 bitwise equal to uninterrupted runs, 98 s, 0.02
    GPU-hours. GPU busy 84–89% but SM-active 0.5–0.6%: single-world `lax.map`
    kernels are latency-bound, so JUPITER needs vectorised worlds.
  - JUPITER recipe: `validation/ensemble/jupiter_env_setup.sh` (wheels only, all
    28 pins have aarch64 Python 3.13 wheels), `jupiter_check.py`, the reworked
    `jupiter.sbatch` and the [runbook](docs/JUPITER_RUNBOOK.md). Site details are
    unverified until access.
  - Runner gaps for later: workers are killed 55 s after a pause request;
    multi-node runs are separate campaigns that need distinct seeds; per-leg
    `allocated_gpu_hours` must not be summed within one job.

- **Plain BETSE reference outputs (8 November).** Unmodified BETSE v1.5.0 CLI,
  isolated HOME, CPUs 1–2; tools `validation/betse/betse_reference_run.py` and
  `betse_reference_extract.py`. [Index](/mnt/workspaces/Cells/betse-reference-20261108-01/index.json)
  of four cases, each with its run result, extract manifest and checks:
  - default world (headless_core): 226 cells, 1,298 membranes, 24×25 ECM grid;
    seed 11.1 s, INIT 11.8 s, SIM 9.6 s, peak 239 MiB;
  - dense default world (sampling = dt; 499 INIT / 349 SIM samples): its own
    unseeded geometry (222 cells, 25×25 grid);
  - dense run on the standard seed: histories bit-identical at all common
    samples, so dense sampling does not change dynamics;
  - seven-cell REF-003c configuration (YAML hash reproduced; new geometry).

  Comparison notes: sample k is the state after k+1 updates, and the end state
  is only in `*_final.npz`; BETSE uses F = 96485 and R = 8.314; geometry differs
  per run (unseeded RNG), so each comparison uses its case's own
  `geometry.npz`; INIT `P_cells_time` is an aliased series. Default-world SIM
  Vmem moves only about 3 µV, so the dense INIT is the informative comparison.
