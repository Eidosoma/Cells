# FR-45's engine table: the contract

**Dated 26 November 2026, and changed five times on 27 November 2026** (the next five sections), before the binding
tag and before any engine run of a registered world. The registration never defines the engine's table, so the lead
ruled that a dated contract fixes it before the binding tag, from the spec's text (the lead's first rulings, Q5:
`/mnt/workspaces/Cells/fr45-readings-20261126/RULINGS-1-2026-11-26.md`). The lead's second rulings,
`RULINGS-2-2026-11-27.md` in the same folder ("RULINGS-2"), rule on the readings this file left open and on its fresh
review (`/mnt/workspaces/Cells/fr45-contract-review-20261127/REVIEW.md`).

- **What it binds.** The driver, which builds and runs the worlds; the exporter, which writes the table from the
  engine's runs; and the judge (`validation/fr45/judge.py`), which reads it. All three are the build's (PROTOCOL:129;
  AMENDMENT-1:103).
- **Its sources.**
  - The protocol and the six spec files at `fr45-site-competition-v1-amendment-3-2026-11-24`, and the references'
    notes at `fr45-references-v2-2026-11-24`.
  - The key names, never the values, of the references' outputs. They come from the lead's census
    (`CENSUS-2026-11-27.txt`), the references' format note (`REFERENCE-FORMAT-NOTE-2026-11-27.txt`), both beside
    RULINGS-2, and the references' invented file, `format_sample_INVENTED.json`. The lead confirmed W1eq's key paths by
    key names (RULINGS-2 §3, item 2) [W8].
  - RULINGS-1 and RULINGS-2.
  - Line numbers cite those files as this branch holds them: PROTOCOL is `docs/FR45_SITE_COMPETITION_PROTOCOL.md`,
    AMENDMENT-1 is `AMENDMENT-2026-11-24.md`, AMENDMENT-2 is `AMENDMENT-2-2026-11-24.md`, and NOTES is
    `validation/fr45/references/NOTES.md`.
- **It fixes formats, not tests.** No criterion, band, class, world, input, plant or tolerance changes. This file
  changes no scoring rule; it applies RULINGS-2's readings of them, as ruled (§8.2) [W-h]. Where the text is silent on
  a format, the contract takes the reading that cannot make a pass easier and marks it
  **(silent: the stricter reading)**. §13 settles the reader's readings 8, 9, 10 and 13 this way. Where RULINGS-2
  rules, the contract applies the ruling and names it (the next section).
- **What each side reads.**
  - The driver builds each world from SPEC.md's inputs, and W1eq's start from the references' file (§3). The exporter
    reads back only what the engine parsed and ran (§4.1) [S4]. The driver never builds a world from the
    expected-inputs file (§12.2), so that the echo compares two transcriptions of SPEC [E1]. The exception is the
    host entities' structure and constraints, which SPEC does not give: this file (§4.1) and the expected-inputs
    file hold them, and the host-entity addendum their values [WD1; §9.6].
  - The judge reads this file, the table, the expected-inputs file (§12.2), the references' files and their G
    function (CRITERIA:76; NOTES:178-186), and `agreement.py` (CRITERIA:29).
  - The judge imports the standard library, NumPy, the registered `agreement.py` and the references' `G`, and nothing
    else: nothing from `src/`, and no other module of the references [Q4b, Q4c].
- **How this file may change** [Who c].
  - *Before the binding tag,* by a dated change, through the lead. A key the judge needs that is not here is asked for
    through the lead and added so, never taken from the other side's code. After the tag, a missing key enters only
    as "Who c"'s erratum, before any run of a registered world [W-g].
  - *After the binding tag,* only by "Who c"'s two kinds, each dated, disclosed, hashed by the lead, and made before any
    run of a registered world: (1) the addenda this file calls for, listed in §14.1, the host-entity addendum among
    them [§8.1, §9.6]; (2) an erratum where a judge must change (D371, DECISIONS:12279).
  - *After a run,* nothing changes. A registered world's first run is in the judged run. The builder develops and
    tests on invented worlds, such as the format sample's (§12.1) [Who c]. A parse-only pass of a registered world,
    a definition check with no step, is not a run, and is allowed before the judged run [§8.6]; but none of W1eq is
    made, since it would read the references' W1eq start [§9.2, WF5].
- **Extra keys** are allowed and ignored, except in `inputs` (§4.1). An object keyed by data (by observable, ligand,
  node, set or population) holds exactly the members this file names; a missing, extra or duplicated member is a fault
  (§11.2) [B2].

## Dated change, 27 November 2026

Made before the binding tag, by an agent who has seen no reference value, applying RULINGS-2. No criterion, band,
plant, tolerance or class changes.

**The marks.** A mark in square brackets names what a change applies:
- [§1] is RULINGS-2's §1: its two rules and the verdict keys;
- [P-b], [5a], [7a], [12b], [Q4b] or [Who c] is a row of RULINGS-2's §2;
- [item 4] is an item of RULINGS-2's §3, which rules the eight items this file's §14 left open;
- [B2], [S8] or [W13] is a finding of the review, as RULINGS-2's §4 rules it;
- [E1] to [E14] mark this change's own format sentences, where a ruling leaves the form open. Each takes the reading
  that cannot make a pass easier, and §15 lists them for the lead.

**What changed:**
- **The header:** the driver's sources [S4, E1]; the judge's imports [Q4b, Q4c]; how this file may change [Who c];
  objects keyed by data are complete [B2].
- **§1:** a unit conversion after the tag [Who c]; a value that is not finite [§1, E2].
- **§2:** a missing run, and a plant with no run [11a, 11b].
- **§3:** the honest W1p and W3p runs [7a, 7c, S12]; W1eq's start [item 2, W8, Who c].
- **§4:** `status` against `refusal` [S13]; `backend` [B5]; `capacities` [S8, E13]; the new `free_sites` [item 6]; the
  count of `events` [B2]; `checks`, which C10 now reads [B3, E3]; `refusal` gains `raised` and `book` [B4, E4]; W5's
  null report at parse [W3].
- **§4.1:** `permeabilities`, `multipliers` and `charges` [S6, E9]; one-population sets [S10]; W2's L2 [E7]; W7s's
  ligands [S11]; compartments SPEC does not name [item 7, W10]; the echo against the expected-inputs file, its closed
  list of exceptions, and traces [S5, W10, W11]; the cross-check against the references' echo [S5, E11].
- **§5:** every keyed member [B2]; the tolerances are the file's [item 3]; G's amounts [S3, Q4a]; C9's quantity
  [Q6f, Q6g].
- **§6:** exactly one event [B2]; both variants judged, and a missing one [4a, 4b]; the map in the run's own process
  [W13].
- **§7:** the report's fixed values, and C7 against 1/2 [B7]; W5's limiting load [S2]; the refusal mapping [B4]; P4
  [W14].
- **§8:** P7 on W3p [7b]; `inputs_changed` and key paths [B6, E6]; P5's patch [item 8]; a new §8.2, how a plant is
  caught [§1, P-a, P-b, P-c, P-d, 7d, 11b, E12].
- **§9:** G's amounts [S3]; the wash in W7 [Q6b, W7]; `operators` exactly [S7]; a new model ID [Q6d].
- **§10:** CPU and binary64 [B5, S13, E5]; `external_modules` [W9]; the blobs the judge checks [S14, Q3].
- **§11:** entries come from the registration [B2]; how the classes reach `agreement.py` [5a, 5b, 5c, 5d, 6, §1];
  every key each criterion reads [W4, W5, W6, E13, E14]; a new §11.1, every value this file fixes [S13]; a new §11.2,
  faults and how they are scored [§1, item 4, B1, B2, S9, E8].
- **§12:** who writes the format sample, its path, names and numbers, and what a fault in it stops [item 1, W2, W12,
  E10]; the expected-inputs file [S5]; the order at the judged run [12b, S5, S14].
- **§13:** reading 10's row [B7, S2].
- **§14:** "Ruled": a pointer to RULINGS-2 §3, item 3's corrected intervals [W1], and the addenda still owed [Who c].
- **§15:** this change's disclosures, and its list of [E] marks.

## Second dated change, 27 November 2026

Made before the binding tag, by the same agent, applying RULINGS-2's §7, "Amendment of 27 November, after the second
read". §7 accepts every finding of the second review (`/mnt/workspaces/Cells/fr45-contract-review-20261127/REVIEW-2.md`,
its §2). No criterion, band, plant, tolerance or class changes.

**The marks.** [N1] and [N2] are the second review's blocking findings, [S-a] to [S-g] its should-fix findings and [W-a]
to [W-i] its wording findings, each as §7 rules it. [§7] marks §7's one item that has no finding number: the
cross-check gains `free_amounts[].declared`.

**What changed:**
- **The readings confirmed.** §7 confirms the first change's E marks as applied. E5 stands as B5's reading [W-e]. S8's
  sentence now reads "every S the judge forms from the engine's state comes from `capacities`" [W-d]. E8 gains S-c's two
  cases, and E12 gives way to S-e.
- **The header:** this file changes no scoring rule, and applies RULINGS-2's readings of them [W-h]; after the tag, a
  missing key enters only as "Who c"'s erratum [W-g].
- **§1:** the units are confirmed before the tag, and a conversion found after it is a registration change [S-d].
- **§3:** the honest baselines are pass conditions through the plants [S-a].
- **§4:** `plant.patch` is a path from the checkout's root [W-a]; S8's sentence [W-d]; when a refused W2 or W7 run holds
  its event [W-b]; the checks are listed by world and cadence [S-b]; the free-site form is confirmed [N2].
- **§4.1:** traces are the binary64 product [W-f]; W7s's L2 in `ligands`, `free_amounts` and `charges` [S-g]; the
  multipliers and permeabilities are confirmed [N2]; the cross-check gains `declared` [§7].
- **§7:** the mapping covers what the plants' patches can raise [N1].
- **§8:** the patches' scope is confirmed before they are hashed [N1]; P-d's "same entry", and the report of a failed
  baseline [S-a]; P8's book comes from the mapping [S-e]; P4's entry is its whole report [W-i].
- **§9:** a new model ID is a registration change [S-d].
- **§11.2:** a fault of the top level, and of a record's hash [S-c].
- **§12.3:** the lead's comparison of the exporter's table with the sample comes before the runs [W-c].
- **§14.1:** the units' confirmation, owed before the tag [S-d]; the contents of the list of checks [S-b]; registration
  changes, not addenda [S-d]; the reviewers' confirmations, as records [N1, N2].
- **§15:** this change's disclosures, and the E marks as confirmed.
- **The format sample:** `INVENTED-W1p-P3~check`, refused by the dissipation check, and `INVENTED-W6~check`, an honest
  run refused by a host check [S-f]; `plant.patch` from the checkout's root [W-a]; the README's runs, book forms and
  checks [S-f, S-b]. Its `SHA256SUMS` is regenerated. The expected-inputs file is unchanged.
- **Not adopted** (§7, under N1): an identity check of a planted quantity against the references' `planted` value.

## Third dated change, 27 November 2026

Made before the binding tag, by the same agent, applying RULINGS-2's §8, "Amendment of 27 November, after the source
check and the third read". The third read is `/mnt/workspaces/Cells/fr45-contract-review-20261127/REVIEW-3.md`. No
criterion, band, plant, tolerance or class changes.

**The marks.** [§8.1] to [§8.8] are §8's eight ruled items, and [§8] its findings confirmed from `src/`. [N3], [X1],
[Y1] and [Y2] are the third read's findings. Its X2, the sample's stall risk, is marked [X2-r], to keep it apart from
D224's check X2, which §8.7 calls X2. [E15] to [E21] mark this change's own format sentences, listed in §15.

**What changed:**
- **The header:** a parse-only pass is not a run [§8.6].
- **§1:** the units are confirmed from `src/` [S-d; §8].
- **§4:** `backend` is `"compiled"` [B5; §8.2]; free sites are state [§8]; the event rule's wash-row case [Y2]; E3 is
  withdrawn, and no check records a mode [§8.3]; the execution record, compared run by run [§8.2, N3].
- **§4.1:** the bath form's host entities, with their names, volumes, traces and permeabilities [§8.1, E17, E18]; the
  new `capacitor_components` [§8.1, E17]; ions out of every ligand-only key [§8.1, E16]; the host entity values
  [§8.1, E15]; `multipliers` as exactly `site_binding_multiplier` [§8.5]; W7s's L2 across the host [S-g]; the
  exception list names the host entities and governs where the expected file says less [§8.1, X1]; the cross-check
  leaves the host out [E20].
- **§5 and §6:** ions are in no row key and not in the event map [§8.1, E16]; one-population sets' names [§8.4].
- **§7:** W5's refusal in either host form [§8]; the windowed driver [§8.6]; the stage identification [§8.6].
- **§8:** a plant run's `definition` [§8.2]; a faithful P3 [§8].
- **§9:** the host's names [§8.1]; the fixed name map [§8.4]; Y1's wording [Y1].
- **§10:** what `jax_platforms` records [§8.2, E19]; the execution record is recorded before the run [§8.2].
- **§11:** C10 reads no mode [§8.3]; §11.1 gains item 13, the execution record and host entity values, as a fault of
  the run's identity [§8.2, N3].
- **§12:** the sample's host form and execution block, and its refusal causes [§8.1, §8.2, §8.8, X2-r]; the expected
  file's host choices and exact multipliers [§8.1, §8.5]; a parse-only pass before the runs [§8.6].
- **§14.1:** the units done [§8]; the stage identification under the mapping [§8.6]; the backend settled [§8.2]; the
  host entity values, a sixth addendum [§8.1]; the execution record, a record [§8.2]; X2 (D224), an open registration
  question [§8.7].
- **§15:** E3 withdrawn, E5 settled, E9 superseded; this change's disclosures.
- **The format sample:** the bath form in every invented world; `backend` `"compiled"`; `multipliers` as
  `site_binding_multiplier`; an execution block in `definition`, which holds no check modes [§8.1 to §8.5]. The honest
  host-check refusal `INVENTED-W6~check` is replaced by `INVENTED-W3p-P7~check`, whose planted patch causes it, and
  `INVENTED-W1p-P3~check` gets a patch of its own [§8.8, X2-r, E21]. Its `SHA256SUMS` is regenerated.
- **The expected-inputs file:** its host entities, host choices and capacitor components; exact multipliers; W6's cell
  named `host_cell`; X1's clause in its rules, and the W7s note's `charges` member [§8.1, §8.5, X1].

## Fourth dated change, 27 November 2026

Made before the binding tag, by the same agent, applying RULINGS-2's §9, "Amendment of 27 November, after the fourth
read". The fourth read is `/mnt/workspaces/Cells/fr45-contract-review-20261127/REVIEW-4.md`. No criterion, band, plant,
tolerance or class changes.

**The marks.** [§9.1] to [§9.7] are §9's seven items. [N4], [WF1] to [WF6] and [WD1] to [WD3] are the fourth read's
findings, as §9 accepts them. [E22] to [E27] mark this change's own format sentences, listed in §15.

**What changed:**
- **The header:** the driver's exception for the host [WD1]; no parse-only pass of W1eq [§9.2, WF5].
- **§3:** W1eq has no parse-only pass [§9.2, WF5].
- **§4:** the new `driver` key [§9.5, WF4, E23]; the execution record's source, its literal fields, and W1eq's
  comparison with W1's record [§9.1, N4; §9.2, WF5; E22]; the solver in today's spelling [§9.3, WF6]; one rule for a
  plant run's `definition` [§9.4, WF1, E24]; `definition` holds no host value the judge reads [§9.6].
- **§4.1:** the host's structure and constraints, fixed at the tag, and its values, moved to the host-entity addendum
  [§9.6, WF2, WF3, E25, E26, E27]; the new `host_values` [§9.6, E25]; the matching keys of `multipliers` and
  `capacitor_components` [WD2]; the host exception [§9.6].
- **§8.1:** a plant run's `definition` points to §4's rule [§9.4, WF1].
- **§9:** the solver's ID [§9.3, WF6].
- **§11:** item 10 compares the host values with the addendum; item 13 holds the literal fields and the plant rule;
  item 14, `driver`, is new; both join the run's identity [§9.1, §9.4, §9.5, §9.6].
- **§12:** `driver.window_steps` is a format constant; the sample covers `host_values` and `driver`; the expected file
  marks the host's values as the addendum's; the parse-only passes feed the record and the addendum [§9.1, §9.5,
  §9.6].
- **§14.1:** item 4 names where a declared change sits in `definition` [E24]; item 6 is the host-entity addendum
  [§9.6]; the execution record's source [§9.1, N4].
- **§15:** E1, E15 and E18 amended; this change's disclosures.
- **The format sample:** the solver in today's spelling; `driver` in every run; `inputs.host_values`; no host values in
  `definition` [§9.3, §9.5, §9.6]; the README's note on the invented patches [WD3]. Its `SHA256SUMS` is regenerated.
- **The expected-inputs file:** each host volume, host trace and `host_values` marked "from the host-entity addendum"
  in place of a literal; the matching keys [§9.6, WD2].

## Fifth dated change, 27 November 2026

Made before the binding tag, by the same agent, applying the lead's addition to RULINGS-2 §9.6, marked [§9.6+]. SPEC
registers no area or capacitance for any patch: not `specimen_face`, and not the host patches. So every patch's area
and capacitance joins the host-entity addendum, registered patches included, which covers `specimen_face` in W3, W3p
and W6. They are recorded in `inputs.host_values`, compared with the addendum in every run, and a plant run takes its
honest run's. No criterion, band, plant, tolerance or class changes.

**What changed:** §4.1's `host_values` and the addendum's values; a new line in the exception list; §14.1's item 6; E25
in §15; the format sample's `host_values`, its README, and its `SHA256SUMS`; and the expected-inputs file's
statement of the addendum's values [§9.6+].

## 1. Files and number form

- **The table** is `table/table.json`, one file for the judged run, with `table/SHA256SUMS` (one line: the sha256, two
  spaces, `table.json`).
  - The lead records its sha256 before the judge opens it.
  - The judge does not read a table whose sha256 departs from that line or from the lead's record, or equals the format
    sample's (§12.1). It reports such a table to the lead.
- **The exporter forms nothing.** Every number is the engine's own. It is read from the engine's saved state, books,
  records or step report, or returned by the engine's own functions (the wash's event map, `quantities`) called on a
  saved state.
  - No difference, sum, ratio, recomputed quantity, tolerance or verdict is written. The judge forms those.
  - This assumes that the engine holds amounts, volumes, concentrations, times and heats in SPEC §0's units (§9).
    A reviewer who is not the builder confirmed this against `src/` before the binding tag: the engine holds SPEC
    §0's units natively on these worlds' path, and no conversion rule is needed (§14.1) [S-d; §8]. A conversion
    found after the tag would be a registration change, not an addendum [S-d].
- **Strict JSON** (RFC 8259): no NaN or infinity, and no key twice in one object.
  - Floats are written in Python's `repr` form, so each parses to the engine's binary64 value, the sign of zero
    included. "Bit for bit" (CRITERIA:61, 82) compares the 64-bit patterns.
  - An integer is a JSON integer. A float with no fraction is accepted where an integer is asked, a string never.
  - **A value that is not finite** cannot be written. The exporter writes `null` in its place, at that leaf; this is
    the one null allowed where a number is asked. The judge reads it as a non-finite engine value: an honest pair that
    holds it fails, and a plant entry that holds it cannot be formed, so it is not caught (§11.2) [§1, E2].
- **Order is not a contract,** except in `rows` (step order) and `operators` (declared order). Runs are matched by
  name.
- **`null`** stands only where this file allows it.

## 2. The top level: every key required

| Key | Type |
| --- | --- |
| `kind` | the string `fr45 site-competition engine table, version 1` |
| `protocol` | the string `fr45-site-competition-v1` (PROTOCOL:5) |
| `runs` | object: run name (§3) to its entry (§4) |
| `missing` | list of run names (§3) for which no run record was found |
| `units` | object, exactly §9's |

- A name is in `runs` or in `missing`, never both. A run named in neither is missing.
- **A missing run** does not complete, so C10 fails, and so does every criterion it feeds [11a]. A plant whose run is
  missing is not caught, so the protocol fails: a refusal by its own books or checks is a run's outcome, and a run
  never made has none [11b].

## 3. The runs

| Run name | World | Plant | dt (s) |
| --- | --- | --- | --- |
| `W1` | W1 | — | 0.008 |
| `W1eq` | W1eq | — | 0.008 |
| `W2` | W2 | — | 0.0125 |
| `W3` | W3 | — | 0.004 |
| `W4-dt0.08`, `W4-dt0.04`, `W4-dt0.02` | W4 | — | 0.08, 0.04, 0.02 |
| `W5` | W5 | — | 0.1 |
| `W6` | W6 | — | 0.00625 |
| `W7` | W7 | — | 0.0025 |
| `W7s` | W7s | — | 0.0025 |
| `W1p`, `W3p` | W1p, W3p | — | 0.008, 0.004 |
| `W1p-P1`, `W1p-P2`, `W1p-P3`, `W1p-P6`, `W1p-P8`, `W1p-P9` | W1p | P1, P2, P3, P6, P8, P9 | 0.008 |
| `W5-P4` | W5 | P4 | 0.1 |
| `W2-P5`, `W7-P5` | W2, W7 | P5 | 0.0125, 0.0025 |
| `W3p-P7` | W3p | P7 | 0.004 |

The criteria each run serves are the registration's (PROTOCOL:105-116; CRITERIA:72-86, 119-129), as RULINGS-2 rules
them (§8.2, §11). This table only names the runs.

- **The honest `W1p` and `W3p` runs** [7a, 7c; item 5].
  - *Criteria:* C5 and C10 judge them, since C5 and C10 name every world but W5 and every run but W5's refusal
    (CRITERIA:81, 86; AMENDMENT-1:122, 126).
  - *Baselines:* their other entries (W1p's C1, C3b and C9; W3p's C1) are the plants' honest baselines (§8.2, [P-d]).
    They are not criteria. They are pass conditions through the plants, and can only make a pass harder (§8.2)
    [S-a].
  - *Pairs:* none is classified anew (PROTOCOL:93). W1p's are its reference file's, which holds C1, C3b, C5, C9 and C10
    pairs. W3p's are W3's at W3p's times (SPEC:182), with W3's tolerances, so C1's band there takes W3's s_node
    [7a, S12].
- **W1eq's start** is written by the references from W1's root (SPEC:123-126, 279). So the judged run's driver reads it
  at run time from the tagged `validation/fr45/references/outputs/reference_W1eq.json` [item 2]:
  - each population's `world.populations[].initial_occupancy`, matched by `id`;
  - each free amount's `world.free_amounts[].n`, matched by `ligand` and `node`.

  The lead confirmed these paths by key names, and the references' invented file holds a start at the same paths, so
  the builder develops the read path on that file [item 2, W8]. Everything else is W1's (SPEC:130-132). The run's
  `inputs` echo the start, and the judge compares the echo with the file bit for bit. W1eq is never run before the
  judged run [Who c]. No parse-only pass of it is made before the judged run either, since one would read the
  references' start [§9.2, WF5].
- **P5's runs** are full planted runs of W2 and W7. C4a reads their rows (NOTES:103-104), and C6 their own `event_map`
  (§6).

## 4. A run's entry: one shape for every run

Every entry holds every key below, for honest, plant and refused runs alike.

| Key | Type and meaning |
| --- | --- |
| `status` | `"completed"` or `"refused"`; `"completed"` exactly when `refusal` is null [S13] |
| `world` | string: the run's world (§3) |
| `plant` | null in an honest run; else `{"id", "patch", "change", "inputs_changed"}`: the plant (`P1` to `P9`, as the run's name gives it), the scoped patch's path from the checkout's root, beginning `validation/` (CRITERIA:111-112) [W-a], one line naming what it changes, and the list of `inputs` key paths it changes (§8.1) |
| `dt_s` | number: the step the engine ran, §3's dt bit for bit |
| `steps` | integer: the steps completed: the last row's `step`, or the steps before a refused one; 0 in a run refused at parse |
| `backend` | `"compiled"`: the engine's implementation that the run's steps used, in every run, honest and planted. RULINGS-2 §8 settles B5's value, and a run whose `backend` departs is a fault [B5; §8.2]. Its arithmetic is binary64 on the CPU (the execution record below, §10) |
| `driver` | `{"window_steps"}`: the driver's record of how it ran the run. `window_steps` is 1 in every run, a run refused at parse included [§9.5, WF4; E23] |
| `rows` | list of rows (§5), in step order |
| `capacities` | object, set → fmol: each set's capacity S_s, one-population sets included. It is the engine's constant, set at parse from the declaration (SPEC:48), never from a state [S8] |
| `free_sites` | object, set → `"state"` or `"derived"`: how the engine holds that set's free sites R_s, as a state its steps update, or formed from S_s and the bound amounts [item 6] |
| `events` | list of the run's events (§6) |
| `event_map` | list of the wash's event map applied alone to saved states (§6); empty in a world without a wash |
| `step_report` | the engine's report of the first step (§7) in W5's two runs; null in every other run, and in a W5 run refused at parse [W3] |
| `refusal` | null in a completed run; else `{"kind", "raised", "book", "name", "message", "step", "time_s"}` (§7) [B4] |
| `checks` | object, or null before parse: every listed ledger and host check of the run, by its name (below) [B3] |
| `operators` | list of strings: the model and operator IDs the run's definition declares, in declared order, in today's spellings (§9) |
| `inputs` | the world as the engine parsed it (§4.1) |
| `definition` | object, or null before parse: the engine's own declaration of the world, as run. The judge compares its execution block and bounds with the execution record, and checks its literal fields (below) [§8.2, N3; §9.1, N4]. It holds no host value that the judge reads, since those are in `inputs` (§4.1) [§9.6], and it records no check's mode [§8.3] |
| `source` | provenance (§10) |
| `record`, `record_sha256` | the run's own record file, by its path relative to `table/`, and its sha256 (64 hex digits); recorded, and checked for type only |

- **`capacities`** [S8]. The judge checks each S_s against α·ν·N/N_f of the echoed inputs (§4.1), within 4ε·S, which
  covers two routes of three roundings each. Every S the judge forms from the engine's state comes from
  `capacities`, as for C9's B_b/S_s and its moiety term [S8, E13; W-d]. A pair that holds its own value or `scale`
  (C5's S_s, C8's S) is judged with the file's, as §11 says.
- **`free_sites`** [item 6]. At a `"derived"` set, C5 holds by construction. It still counts, because CRITERIA:81 covers
  every set, and the verdict names each such set. Requiring free sites as state is a design rule the registration does
  not make (SPEC:53). The engine's form for free sites is confirmed against `src/` before the judged run (§14.1) [N2].
  The source check found it: the engine holds free sites as state, not derived, so C5 is a real test [§8].
- **`events`** [B2]. A completed run of W2 or W7, honest or planted, holds exactly one event, after step 320 (W2) or
  400 (W7). A run of any other world holds none. A refused W2 or W7 run holds the event exactly when `refusal.step`
  is at least 321 (W2) or 401 (W7), the step whose start applies the wash, unless the refusal is the wash's own, or a
  check's at the wash row, before the wash [Y2].
  Otherwise it holds none, and so does a run refused at parse [W-b].
- **`checks`** [B3].
  - *The list:* fixed by a dated addendum before any registered run (§14.1). It gives, for each check, the worlds or
    declared operators that evaluate it, and its cadence: each step, or each saved row [S-b]. A reviewer who is not
    the builder confirms it against `src/` (§14.1) [N2].
  - *Its members:* every ledger and host check that the list gives for the run's world [S-b]. Each is keyed by its
    name in that list, as `{"failures": [...]}`: the engine's own record of each failure of that check,
    `{"step", "message"}`, with `step` the steps completed when it was recorded [E3].
  - *No mode* [§8.3]: every check on this path raises and has no other mode, so no check records a mode, and in a
    completed run each `failures` list is empty by construction. E3, the mode's record, is withdrawn.
  - *C10:* a completed honest run fails C10 if its `checks` is null, lacks a check listed for that run's world [S-b] or
    records a failure [B3; §8.3].
  - *Honest runs only:* on a plant run, a failure recorded without a refusal is not a catch [P-c].
- **The execution record** [§8.2, N3; §9.1, N4].
  - *Fixed now:* `execution.solver` is `cells.solver.imex_ars222_face_electromigration@1`, @3's solver in today's
    spelling [§9.3, WF6]; the execution block holds no `energy_check` (X2 is not selected, §14.1); `execution.dt` is
    the world's SPEC dt, `dt_s`; `field_solver` is the engine's default; every species' `material_balance_atol_fmol`
    is as the engine's species helper sets it (`inventory_species.py`'s floor), never declared otherwise; and
    `backend` is `"compiled"`, with `execution.jit` true, the execution block's `backend` `"cpu"`, float64, and
    `JAX_PLATFORMS=cpu` where a CUDA plugin is installed.
  - *Its source* [§9.1, N4]: a parse-only pass of every registered world but W1eq, made after the build and before
    any registered run, which gives one record per honest run (W4's three dt have one each). A parse-only pass is
    not a run (§8.6). N2's reviewer, who is not the builder, confirms against `src/` that the record holds the
    engine's defaults: the default `field_solver`, and each species' `material_balance_atol_fmol` at the species
    helper's floor. The lead hashes it, as a record and not a change (§14.1).
  - *W1eq* [§9.2, WF5]: no parse-only pass of W1eq is made before the judged run. Its execution block is compared with
    W1's record, its start apart, and so is any field that `inputs` fixes differently for W1eq, its observation
    times and horizon [E22].
  - *What the judge compares:* every honest and planted run's `definition` execution block, and its bounds, with its
    honest run's record.
  - *The literal fields* [§9.1, N4]: in every run the judge also checks these against this file: `execution.solver`,
    as above; `execution.dt` equal to the run's `dt_s`; `execution.jit` true; the execution block's `backend`
    `"cpu"`; no `energy_check` in the execution block; and `driver.window_steps` 1 [§9.5].
  - *A plant run's `definition`* [§9.4, WF1]: it is compared with its honest run's after the plant's declared
    `inputs_changed` (B6) is applied, as P2's crossed `k_off`, and any other difference is a fault of the run's
    identity. The B6 addendum names where each declared change sits in `definition`, P2's included (§14.1) [E24].
    A patch's change is code and lies outside `definition`; the patch review covers it (N1).
  - *A departure* is a fault of the run's identity (§11.1, §11.2).
- **A completed run** carries every registered row of its world (§5.1) and, in W2's and W7's runs, its one event and
  every event-map entry (§6) [B2].
- **A refused run** keeps the rows, events and event-map entries it has; any list may be short.
  - A run refused before its definition was parsed holds null in `inputs`, `definition` and `checks` and, in W5's
    runs, in `step_report` [W3]. It holds an empty `operators`, `capacities` and `free_sites`, and no row, event or
    map entry.
  - Only such a run holds those nulls.

### 4.1 `inputs`

Read back from the definition the engine parsed and ran, never copied from SPEC.md or from the expected-inputs file.
Exactly these keys:

| Key | Type |
| --- | --- |
| `world` | string |
| `constants` | `{"sites_per_fmol", "temperature_K", "RT_pJ_per_fmol"}`: N_f, T and RT as the engine uses them (SPEC:34-40) |
| `nodes` | list of `{"id", "kind", "volume_pL", "registered"}`; `kind` is `"node"` or `"cell"`; `registered` is false for a compartment SPEC §2 does not name, a host entity (below). A host compartment's `volume_pL` is the host-entity addendum's [§9.6] |
| `patches` | list of `{"id", "inside", "outside"}`: the registered `specimen_face` (W3, W3p, W6) and the host patches (below) [§8.1] |
| `ligands` | list of strings |
| `free_amounts` | list of `{"ligand", "node", "n_fmol", "declared"}`: every ligand of `ligands` at every node and cell, as the engine parsed it. `declared` is false for a trace (SPEC:104-106) |
| `sets` | list of `{"id", "shared", "owner", "face", "faces", "copies", "sites_per_copy", "accessible_fraction"}`, described below |
| `populations` | list of `{"id", "set", "ligand", "k_on", "k_off", "initial_occupancy"}`. `k_on` and `k_off` are the values the binding routes use [S6] |
| `wash` | null, or `{"time_s", "node", "fraction", "buffer_mM"}`, with `buffer_mM` an object ligand → mM (W2 and W7: SPEC:152, 225) |
| `permeabilities` | list of `{"patch", "ligand", "value"}`: each ligand's permeability on each patch, registered and host, in the engine's own unit; registered 0.0 (SPEC:59-61) [S6, E9; §8.1] |
| `multipliers` | list of `{"of", "name", "value"}`: exactly each population's binding multiplier, with `of` the population, `name` `"site_binding_multiplier"` and `value` its value; registered 1.0 (SPEC:62). The accessible fraction α and the internalisation control are not multipliers [S6; §8.5] |
| `charges` | object, ligand → integer: each ligand's valence, for every ligand of `ligands`; registered 0 (SPEC:59) [S6] |
| `capacitor_components` | list of `{"members", "held_by"}`: the host's capacitor components, as the engine's checker forms them: each one's compartments (`members`, compared as a set) and the held node that holds it. In every world there is one, `{bath, <its cell>, <its registered node>}`, held by `bath` [§8.1, E17] |
| `host_values` | `{"areas", "capacitances", "ion_permeabilities", "ion_amounts"}`: the host-entity addendum's values, as the engine parsed them, each the engine's own value. `areas` and `capacitances` are keyed by every patch, registered and host [§9.6+]; `ion_permeabilities` by host patch, then by ion; `ion_amounts` by compartment, every one, then by ion [§9.6, E25] |
| `dt_s`, `observation_times_s`, `horizon_s` | number, list of numbers, number |

- **`multipliers` and `permeabilities`** are checked against more than the exporter's word: before the judged run, a
  reviewer who is not the builder confirms against `src/` the multipliers the engine applies, and where its
  declaration holds permeabilities (§14.1) [N2]. `multipliers` is exactly each population's
  `site_binding_multiplier` [§8.5].
- **A set's keys:**
  - `shared` is false for a one-population set and true for every other. The registration's worlds decide the form
    (SPEC:53, 169, 244): a one-population set (W3's `B`, W7s's `matrix`) is declared as its population's own sites,
    with `shared` false [S10]. The engine names such a set after its population, and the exporter writes SPEC's set
    name through §9's fixed map [§8.4].
  - PROTOCOL:55 lists "a set named by fewer than two populations" among version 1's refusals. A refusal of W3 or W7s
    under it is a C10 failure, not a format fault [S10].
  - `owner` is a node or a patch. `face` is `"inside"` or `"outside"` for a patch's set, and null for a node's.
  - `faces` is the facing node or cell (SPEC:55-58).
- **W2's L2 is declared,** since SPEC gives its amount (SPEC:148), which equals its trace [E7].
- **W7s's registered `ligands` is `["L1"]`** [S11]. An engine that holds L2 there lists it at its trace (`declared`
  false). The echo then excepts its `ligands` entry and its `free_amounts` entries, in every compartment, as
  information; its `permeabilities` entries, on every patch, each 0.0; and its `charges` member, which must be 0 [S-g;
  §8.1].
- **The host entities** [§8.1, amending item 7].
  - *Why:* `cells.model.resolved_pump_tissue@3` needs at least one cell, one patch and a held capacitor component.
    Every world takes the bath form, which main's wash fixtures and tests already run.
  - *In W1, W1eq, W1p, W2, W4, W5, W7 and W7s:* a held bath node `bath`; a cell `host_cell` walled on it by the patch
    `host_wall` (inside `host_cell`, outside `bath`); and a contact patch `host_contact` on the registered node
    (inside `host_cell`, outside `well` or `vat`).
  - *In W3 and W3p:* `bath`, and `host_wall` from the registered cell (inside `specimen`, outside `bath`).
  - *In W6:* `bath`; the cell inside `specimen_face`, which SPEC does not name (SPEC:210), now named `host_cell`;
    and `host_wall` (inside `host_cell`, outside `bath`).
  - *Fixed at the tag, the structure* [§9.6, WF2]: the bath form's entities and their names; the patch orientations; and
    the capacitor component. Each host patch's inside is the world's cell: `host_cell`, or `specimen` in W3 and W3p
    [E26]. The wall's outside is `bath`, and the contact's outside is the registered node. The one capacitor
    component is `{bath, <its cell>, <its registered node>}`, held by `bath` (`capacitor_components`) [E17]. Each
    host compartment is in `nodes` with `registered` false, and the names are this file's choice [E18]. The source
    check ran this form, its case f, the wash fixtures' form.
  - *Fixed at the tag, the constraints* [§9.6, WF2, WF3]: every ligand has permeability 0.0 on every host patch;
    every ligand is at its trace in every host compartment (`declared` false, and information in the rows); ions are
    held at fixed amounts; and no ligand moves through a host entity. The trace is compared (SPEC:104-105) [item 7]: the
    binary64 product 1e-12 × that compartment's `volume_pL`, which the driver declares as that product, never as a
    typed literal [W-f].
  - *Nothing else:* a world holds no compartment or patch beyond its registered ones and these, unless the lead
    names one by a dated addendum before any registered run (§14.1) [item 7].
  - *The host-entity addendum's values* [§9.6, WF2, WF3]: the host compartments' volumes; every patch's area and
    capacitance, registered patches included, since SPEC registers none: `specimen_face`'s in W3, W3p and W6 as well
    as the host patches' [§9.6+]; the ions' amounts in every compartment; and the ions' permeabilities on the host
    patches. The
    addendum is "Who c" kind (1): recorded after the build and before any registered run, confirmed by the
    non-builder reviewer against the wash fixtures' form, and hashed by the lead (§14.1). It is kept per honest
    run, its values copied by machine from the parse-only pass (§4); W1eq takes W1's, and a plant run its honest
    run's [E27]. The echo carries them, in `nodes[].volume_pL` and `host_values`, and the judge compares them with
    the addendum.
- **Ions** [§8.1]. They are held at fixed amounts in every compartment (SPEC:59-61). They are not ligands, so every
  ligand-only key excludes them: `charges`, `free_amounts`, the rows' `amounts` and `records` (§5), and the event
  map (§6). So do `permeabilities`, `wash.buffer_mM`, and the event's `collected` and `supplied` [E16]. Their
  amounts in every compartment, and their permeabilities on the host patches, are the host-entity addendum's
  values, in `host_values` (above) [§9.6].
- **The echo** [S5]. The judge compares each run's `inputs` with that run's entry in the expected-inputs file (§12.2),
  bit for bit: "Every number below is a binary64 literal as written" (SPEC:104). It never compares with a copy of its
  own.
  - An extra, missing or different key or value means the run is not the registered world, which is a fault (§11.2).
  - Lists are compared as sets of members, matched by `id`, by `ligand` and `node` (free amounts), by `patch` and
    `ligand` (permeabilities), by `of` and `name` (multipliers) or by `held_by` (capacitor components) [WD2].
    `ligands` and `observation_times_s` are compared as sets of values, with no member twice. Numbers are compared as
    binary64 values.
  - `constants.sites_per_fmol` and `temperature_K` are compared exactly (SPEC:35, 38).
  - **A trace at a registered compartment is compared too,** against the binary64 product 1e-12 × the compartment's
    `volume_pL`, which the driver declares as that product [W11; W-f]. At every registered volume that product equals
    the decimal literal: 1e-12, 1e-06 and 0.001.
  - **The exceptions, a closed list.** The expected-inputs file marks each where it applies. Where a note in that
    file says less than this list, this list governs [X1].
    - `constants.RT_pJ_per_fmol` is recorded, since SPEC gives RT as a formula, not a literal (SPEC:36-39).
    - W1eq's start, its `populations[].initial_occupancy` and `free_amounts[].n_fmol`, is compared with the
      references' file instead (§3) [item 2].
    - The host entities (above) [§8.1]: `bath`, `host_cell`, `host_wall` and `host_contact`, as each world holds
      them. Their structure and constraints are compared with the expected-inputs file, never with SPEC, and they
      are not cross-checked. Their values, the host volumes, the traces those volumes give and `host_values`, are
      compared with the host-entity addendum, and the expected-inputs file marks each so [§9.6]. W6's cell, which
      the 26 November text left to the engine's own name and volume, now has this file's name [W10, item 7; §8.1],
      and its volume is the addendum's [§9.6].
    - `specimen_face`'s area and capacitance in W3, W3p and W6, which SPEC does not register: compared with the
      host-entity addendum, in `host_values`, in every run; a plant run takes its honest run's [§9.6+].
    - W7s's L2, if the engine holds it (above): its `ligands` entry, its `free_amounts` entries, its
      `permeabilities` entries, each 0.0, and its `charges` member, which must be 0 [S11; S-g; §8.1].
    - A key path that a plant run's `plant.inputs_changed` names, whose value is checked as §8.1 says [B6].
- **The cross-check of the expected-inputs file** [S5]. Before any registered run (§12.3), the judge checks the
  expected-inputs file against the references' `world` echo (SPEC:365) wherever their keys overlap, since both
  transcribe SPEC independently. A departure stops the judge before anything is scored. The overlap is set out below,
  by the key names that the references' invented file and the lead's census show [E11; §7].

  | Expected-inputs key (this section's) | References' `world` key | Cross-checked |
  | --- | --- | --- |
  | `constants.sites_per_fmol`, `temperature_K` | `constants.N_f_sites_per_fmol`, `T_K` | equal |
  | `nodes[id=…].kind`, `volume_pL` | `nodes[id=…].kind`, `V` | equal, for every registered node of the expected file (`registered` true) [E20] |
  | `patches[id=…].inside`, `outside` | `patches[id=…].inside`, `outside` | equal, where the references list the patch, for each field that names a registered compartment [E20] |
  | `ligands` | `ligands` | the same members |
  | `free_amounts[ligand=…,node=…].n_fmol`, `declared` | `free_amounts[ligand=…,node=…].n`, `declared` | every entry the references list is in the expected file, with the same amount and the same `declared` [§7] |
  | `sets[id=…].copies`, `sites_per_copy`, `accessible_fraction`, `faces` | `sets[id=…]`, the same four keys | the same sets, equal |
  | `populations[id=…].set`, `ligand`, `k_on`, `k_off`, `initial_occupancy` | `populations[id=…]`, the same five keys | the same populations, equal |
  | the `faces` of the population's set | `populations[id=…].faces` | equal |
  | `dt_s` | `dt` | equal where `dt` is a number; where it is a list (W4), W4's three entries hold its members |
  | `observation_times_s`, `horizon_s` | `observation_times`, `horizon` | equal, where the references hold them |
  | `wash.time_s`, `node`, `fraction`, `buffer_mM` | `wash.t`, `node`, `f`, `buffer` | equal, with the same buffer members |

  - Each entry is checked against its world's file, `reference_<world>.json`. W3p reads W3's file, and W4's three
    entries read W4's.
  - Not cross-checked: W3p's times and horizon, which are SPEC:182's; W1eq's start, which is null in the expected file
    and compared at run time (§3); any other null of the expected file; and the host entities, which have no
    counterpart in the references, with every patch field that names one [E20]. The reviewer's independent
    transcription covers the host entries (RULINGS-2 §8).
  - Not cross-checked either, since the references' echo has no key of the same meaning or the form of its value is
    not known here: `world`, `nodes[].registered`, the sets' `shared`, `owner` and `face`, `permeabilities`,
    `multipliers`, `charges`, `capacitor_components` and `constants.RT_pJ_per_fmol`.

## 5. The rows

A row is the engine's saved state after `step` steps. Row 0 is the start, before any step (SPEC:251-254). The saved
rows are the start and every observation time (AMENDMENT-1:41-43). W5 has no observation time, so its runs also save the
horizon, for the record only (silent: the contract's choice; no criterion reads it).

| Key | Type and meaning |
| --- | --- |
| `step` | integer: the steps completed, 0 at the start |
| `time_s` | number: the engine's own clock at the row |
| `amounts` | object, observable → fmol: `n:<ligand>@<node>` for every ligand of `inputs.ligands` at every node and cell, `R:<set>` for every set and `B:<population>` for every population, and no other (SPEC:368-369) [B2]. An amount the reference's trajectory leaves out, because no law moves it, is information (AMENDMENT-1:23-29) |
| `records` | object, `<ligand>@<node>` → `{"collected", "supplied"}` in fmol: the wash's own records for every ligand of `inputs.ligands` at the washed node, as the engine holds them at the row (zero before the event) [B2]. Empty in a world without a wash |
| `site_heat_pJ` | object, facing node → pJ: the engine's cumulative site heat at each facing node of §5.2 since t = 0 [B2] |
| `site_occupied_fraction` | object, population → number: the engine's `quantities` on this row's state, for every population (§5.3) [B2] |

- **Ions** are in no row key: not in `amounts`, `records`, `site_heat_pJ` or `site_occupied_fraction` (§4.1)
  [§8.1]. A host compartment's ligand amounts are traces, and information.
- **`R:<set>` of a one-population set** (W3's `B`, W7s's `matrix`, named through §9's map [§8.4]) is the engine's own
  free sites for that population, as its state or readout gives them. The exporter never forms S − B. `free_sites`
  says which (§4) [item 6].
- **The two records.**
  - `collected` is the record the wash's event sets for the amount it removes: C4b's "sample" record, C4a's
    "collected", C4c's "removed".
  - `supplied` is the record it sets for the buffer's amount (CRITERIA:78-80; AMENDMENT-2:18-19).

### 5.1 The saved rows, by step (reading 8)

Each step below is t/dt of the inputs as written (SPEC:104), an integer for every registered time (PROTOCOL:165). The
steps are computed from SPEC.md's inputs alone.

| World | dt (s) | Saved rows: time (s) → step |
| --- | --- | --- |
| W1 | 0.008 | 0 → 0; 0.2 → 25; 0.4 → 50; 0.8 → 100; 1.6 → 200; 3.2 → 400; 6.4 → 800; 12.8 → 1600; 25.6 → 3200; 51.2 → 6400 |
| W1eq | 0.008 | 0 → 0; 0.8 → 100; 4.0 → 500; 8.0 → 1000 |
| W1p | 0.008 | 0 → 0; 0.2 → 25; 0.4 → 50; 0.8 → 100; 1.6 → 200; 3.2 → 400; 6.4 → 800 |
| W2 | 0.0125 | 0 → 0; 2.0 → 160; **4.0 → 320**; 4.0125 → 321; 5.0 → 400; 7.5 → 600; 10.0 → 800; 20.0 → 1600; 40.0 → 3200; 60.0 → 4800; 75.0 → 6000 |
| W3 | 0.004 | 0 → 0; 0.1 → 25; 0.2 → 50; 0.5 → 125; 1.0 → 250; 2.0 → 500; 4.0 → 1000; 8.0 → 2000; 16.0 → 4000; 30.0 → 7500 |
| W3p | 0.004 | 0 → 0; 0.1 → 25; 0.2 → 50; 0.5 → 125; 1.0 → 250; 2.0 → 500 |
| W4 | 0.08, 0.04, 0.02 | 0 → 0; 0.4 → 5, 10, 20; 0.8 → 10, 20, 40; 1.2 → 15, 30, 60; 1.6 → 20, 40, 80 |
| W5 | 0.1 | 0 → 0; 1.0 → 10, the horizon, reached only by a run whose first step is admitted |
| W6 | 0.00625 | 0 → 0; 0.25 → 40; 0.5 → 80; 1.0 → 160; 2.0 → 320; 4.0 → 640; 8.0 → 1280; 16.0 → 2560; 25.0 → 4000 |
| W7 | 0.0025 | 0 → 0; 0.5 → 200; **1.0 → 400**; 1.0025 → 401; 1.5 → 600; 2.0 → 800; 3.0 → 1200; 5.0 → 2000; 8.0 → 3200; 12.0 → 4800 |
| W7s | 0.0025 | 0 → 0; 0.25 → 100; 0.5 → 200; 1.0 → 400; 1.5 → 600; 2.0 → 800 |

- **Rows are matched by step** (reading 8; silent: the stricter reading).
  - Wherever the judge meets a registered time t (a reference entry's `time_s`, or an interval's `start_s` or `end_s`),
    the row at t is the row whose `step` is t's step above.
  - In binary64, t/dt is that integer at every registered time but one: at W7's 1.0025 s it is 400.99999999999994.
    Truncating it would land on the wash row, so a step is always the table's integer, never a truncated quotient.
- **The row's clock is checked.** Its `time_s` equals t within 10⁻¹²·t, and is 0.0 at step 0. The 10⁻¹² is the
  contract's own number, after FR-43 part 3's contract (its TABLE.md:79); SPEC states none.
  - A clock summed step by step stays within about 4·10⁻¹³·t over these runs. Neighbouring rows are at least dt apart.
    So this tolerance admits the clock's rounding and no other row.
  - A row whose clock departs is not the registered row.
- **Why this is the stricter reading.** The compared values are the state after k steps under either reading.
  - Matching by step, with the clock checked, pairs no row that matching by time could not, and it also refuses a clock
    that has left the grid.
  - Matching by exact equality of clock and t would refuse a summed clock's rows for their rounding alone. That would be
    a format fault, not a test.
- **Every registered row, and no other.** A completed run holds exactly its world's rows, each once. A refused run
  holds those saved before its refusal [B2].
- **The wash rows.** W2's row at 4.0 s (step 320) and W7's at 1.0 s (step 400) hold the state the wash acts on
  (SPEC:158-159, 233-234).
  - The wash is applied after that row is saved, at the start of the next step.
  - The next row is the first after it.
- **The tolerances are the file's** [item 3]. The references' file fixes every tolerance the judge applies to a
  derived or band pair, including each pair whose tolerance counts steps (the file's `dt_s` marks them). The
  exceptions are C9's and C4b's state terms, which take no k, and C8, whose e(dt) the judge forms by its row (§11). So
  the judge forms no tolerance from k_t or C3b's k, and their form changes nothing. If a tolerance ever had to be
  formed from them, it would take the smallest of the forms at each point (§14).

### 5.2 The heat (reading 9)

- **Its keys** are the facing nodes of the world's sets (SPEC:55-58, 307-308):
  - `well` in W1, W1eq, W1p, W2, W5, W6, W7 and W7s;
  - `well` and the cell `specimen` in W3 and W3p;
  - `vat` in W4.
- **Its value** is the engine's own accumulator, since t = 0, of the heat that its binding routes book at that node
  step by step.
  - This is R-dG's "shared-site heat" (PROTOCOL:45-46), in pJ, with dissipation positive.
  - The wash books nothing in it (AMENDMENT-1:46).
- **It is never formed from states.** A heat formed as G(start) − G(end) of the saved states would make C3b compare −ΔG
  with itself. C3b would then miss P3 and P6, which it is there to catch (AMENDMENT-1:94-98, 101-104).
- **One record serves C3a, C3b and C3c** (reading 9; silent: the stricter reading).
  - C3a's and C3b's heat at a node over an interval is this record's change between the interval's two rows, formed by
    the judge.
  - C3c reads the same record between consecutive rows (CRITERIA:75-77).
  - The table carries no separate interval heat.
- **Why this is the stricter reading.**
  - A booking cannot pass C3c on one record and C3a or C3b on another.
  - The difference carries the record's own rounding, so it cannot make C3a or C3b easier than a separately booked
    interval heat would.
- **C3b's −ΔG** is the references' `fr45ref_free_energy.G`, called on the engine's saved states, never a judge-side
  copy [Q4a]. It receives the row's amounts at the node as §9 names them [S3].

### 5.3 `site_occupied_fraction` (reading 13)

- **It is the engine's R3 quantity of that name** (CRITERIA:85), as the engine's `quantities` returns it.
  - The exporter calls `quantities` in the run's own process, with the run's backend, on the row's saved state: the
    state whose `amounts` the row holds.
  - It is the quantity that `cells.operator.species_regulated_availability@2` reads (PROTOCOL:34, 50, 141).
- **It is never a value kept from inside a step,** since a step's stages are not the saved state.
- **It is never formed by the exporter** from the row's amounts (reading 13; silent: the stricter reading). B_b/S_s
  formed so would make C9 compare that ratio with itself. It would also hide P9, which changes the engine's quantity
  (CRITERIA:129).
- **What C9 judges** [Q6f, Q6g]: the engine's `site_occupied_fraction` of each population, against B_b/S_s within C9's
  tolerance. On a shared set the build must give B_b/S_s, since B_b/(B_b + R_s) is P9. On a one-population set,
  B/(B + R) differs from B/S only by the moiety residual, which C9's tolerance carries.
- **Every row of every run carries it,** W1p's included: P9 is caught on W1p by C9 (CRITERIA:129).
- **The judge forms the rest.** C9's B_b/S_s and its moiety term |R_s + ΣB − S_s|/S_s come from the same row's
  `amounts` and the run's `capacities` (AMENDMENT-1:54-55; [5d, S8]).

## 6. The wash: its event, and its map alone

**`events`,** in W2's and W7's runs and their plant runs: one entry per event the engine applied, and in a completed
run exactly one (§4) [B2].

| Key | Type and meaning |
| --- | --- |
| `kind` | `"wash"` |
| `operator` | `cells.operator.scheduled_compartment_wash@1` |
| `node` | string: the washed node |
| `after_step` | integer: the steps completed when it was applied: 320 in W2, 400 in W7 (§5.1) |
| `time_s` | number: the engine's clock when it was applied |
| `collected`, `supplied` | object, ligand → fmol: the amounts this event booked, from the engine's own record of the event, for every ligand of `inputs.ligands`, and no ion [B2; E16] |

- C4c reads `collected` and `supplied` (CRITERIA:80).
- `time_s` equals the wash's time within 10⁻¹²·t, as a row's clock does (§5.1).
- An event at another step than §5.1's means the run is not the registered world.

**`event_map`,** in the same runs: the wash's event map applied alone to saved states (CRITERIA:79, 82; PROTOCOL:44;
DECISIONS:10367-10368).

| Key | Type and meaning |
| --- | --- |
| `state_step` | integer: the row whose saved state the map is applied to: 320 in W2; 0 and 400 in W7 |
| `variant` | `"numpy"` or `"compiled"`: the engine's NumPy implementation of the map, or its compiled one |
| `node`, `fraction`, `buffer_mM` | string, number, and object ligand → mM: the map's parameters as the engine passed them; they equal `inputs.wash` |
| `before` | `{"amounts", "records"}`: the state passed to the map, read from it before the call, in a row's shapes (§5), with no ion [§8.1] |
| `after` | `{"amounts", "records"}`: the state the map returns, in the same shapes |

- **A completed W2 run holds two entries** (step 320, each variant). **A completed W7 run holds four** (steps 0 and
  400, each variant). Each (`state_step`, `variant`) occurs once [B2].
  - Both variants are separate entries, and neither is optional.
  - *Both are judged* [4a]: on the honest runs each variant's entries are judged, and a fail in either fails the
    criterion, since CRITERIA:61's "every engine value" covers both (C4b, C6).
  - *A missing variant* [4b]: its entries cannot be formed. On an honest run its criterion fails; on a plant run they
    are not caught (§11.2).
- **The map acts on the run's own saved state,** in the run's own process: the exporter calls both variants there, on
  the saved state [W13]. `before` equals that row's `amounts` and `records` bit for bit. A departure means the map was
  not applied to the saved state.
- **No saved row is compared across the wash** (CRITERIA:82).
  - C6 compares every `R:` and `B:` of `after` with `before`.
  - C4b compares `after`'s free amounts and records with SPEC:96-100's map.
  - The judge forms the event's records as `after` less `before`. `before` holds zero records in every registered state.
- **P5's runs** hold the planted map's entries in the same shape, on their own saved states (§8.1).

## 7. W5's step report, and how a run ends

**`step_report`** (reading 10), in `W5` and `W5-P4`: the engine's own report of its first step, the step leaving t = 0.

| Key | Type and meaning |
| --- | --- |
| `step` | integer: 1 |
| `h_s` | number: h, as the engine used it (h = dt/2: SPEC:75) |
| `loads` | list of `{"kind", "id", "sums", "per_s"}`: every load the stage condition evaluated at the step's first stage, on the start state (SPEC:340-341), described below |
| `max_load` | `{"kind", "id", "sums", "per_s"}`: the largest of them |
| `h_max_load` | number: h·max L at that stage, as the engine computed it |
| `limit` | number: 0.5 (SPEC:75) |
| `verdict` | `"refused"` or `"admitted"`: the step's verdict (SPEC:342; CRITERIA:124) |

- **A load's keys** (SPEC:77-79):
  - `kind` is `"L_n"` for a pool (`id` `<ligand>@<node>`), `"L_R"` for a free-site load (`id` its set), or `"L_B"` for
    a population (`id` the population).
  - `sums` lists the populations whose terms the load adds. `per_s` is its value.
- **Its fixed values** [B7]. `step` is 1, `h_s` equals the run's `dt_s`/2, and `limit` equals 0.5, each bit for bit. A
  departure is a fault (§11.2). In binary64, 0.1/2 is the literal 0.05. At dt 0.1 s, W5 is refused at step 1 by the
  stage condition in either host form, and nothing refuses earlier (the source check, RULINGS-2 §8).
- **C7 reads the report so** (reading 10; silent: the stricter reading). The honest W5 run is refused by the stage
  condition at its first step:
  - `status` is `"refused"`, `refusal.kind` is `"stage"` as the judge maps it (below), `refusal.step` is 1, and no row
    follows the start;
  - its `step_report` has `verdict` `"refused"`, and its own `h_max_load` exceeds 1/2 (CRITERIA:83). C7 compares it
    with 1/2, never with the report's `limit` [B7];
  - **the limiting load** (open: the stricter reading) [S2]: in `W5`, `max_load` has `kind` `"L_R"`, `id` `"matrix"`
    and `sums` both populations, and it is the member of `loads` with the largest `per_s`. The references' own stage
    record names the same load as the largest (RULINGS-2 §4, S2).

  A refusal of another kind, at another step, or without the report does not meet "Refused by the stage condition: the
  engine's step report gives h·max L above 1/2" (CRITERIA:83). W5's refusal can come only from the stage condition
  (PROTOCOL:166-167).
- **P4's run reads from the same key** (silent: the stricter reading) [W14]. P4 is caught only by its `verdict`
  `"admitted"`, from its row "C7: the plant admits the step" (CRITERIA:124), and never by a refusal (§8.2) [P-c].

**`status` and `refusal`.** A run completes, or the engine refuses it: "The run completes; the runner raises otherwise"
(CRITERIA:86).

| Key | Type and meaning |
| --- | --- |
| `kind` | one of the five kinds below, set by the exporter by the mapping (below) |
| `raised` | string: the qualified class name of the exception that ended the run, as the engine raised it or, for `harness`, as the driver caught it; null only in a `harness` refusal that no exception ended, such as a time limit or a crash [B4, E4] |
| `book` | for kind `check`, one of `"moiety ledger"`, `"energy ledger"`, `"dissipation check"` or `"host check: <name>"`: the book that refused; null for every other kind [B4, E4] |
| `name` | string: the engine's name of the condition, ledger, check or rule that refused; for `harness`, the driver's name of what ended the run |
| `message` | string: the message as the engine raised it |
| `step` | integer: the step being taken, counted from 1; null at parse |
| `time_s` | number: that step's start on the engine's clock; null at parse |

**The windowed driver** [§8.6]. The driver runs in windows (`iter_windows`) with `window_steps` = 1. So a
refusal's `step` is exact, and the rows before a refusal are kept. This fixes what `refusal.step` means for C7's
step 1 and for the event rule's 321 and 401 (§4).

**The kinds:**
- `stage`: the stage condition refused a step (SPEC:74-79; CRITERIA:83).
- `check`: one of the run's own books, ledgers or host checks failed at a row or a step. These are the moiety and energy
  ledgers, the dissipation check and the host checks (CRITERIA:86, 113-114, 123, 126, 128). Its `book` names which.
- `definition`: at parse, a declaration the engine could not read or does not support. Version 1's refusals by name are
  among them (PROTOCOL:52-56).
- `domain`: a value outside a declared domain, by name, at parse or at run time, such as initial occupancies over 1
  (PROTOCOL:57).
- `harness`: anything the engine did not raise: the driver, the exporter, memory, a crash, a time limit.

**The mapping** [B4].
- A dated addendum fixes, before any registered run, the mapping from the engine's exceptions and check names to
  `kind` and `book` (§14.1). A reviewer who is not the builder confirms it against `src/`, and confirms that it covers
  every exception and check name that a plant's patch can raise [N1]. The lead then hashes it (§14.1).
- *The stage identification* [§8.6]. The build adds W5's first-stage report and a way to tell a stage refusal from
  other domain failures. The mapping then gives kind `stage` (§14.1, item 1).
- The judge applies the mapping itself to `raised` and `name`, never relying on the exporter's `kind` alone. A refusal
  that maps to no listed kind is `harness`. A `kind` or `book` that departs from the judge's mapping departs from a
  value this file fixes, so it is a fault (§11.2).
- The kinds stay apart. Only a refusal of kind `check` is a run's "own books or checks" (CRITERIA:113-114); `stage`,
  `definition`, `domain` and `harness` never are [P-c].

## 8. The plant runs

### 8.1 How a plant runs

- **Each plant runs in its own process,** as a scoped patch under `validation/`, never in `src/`, on the plant's own
  world (CRITERIA:111-112).
  - Its entry has the honest shape, and its `plant` names the plant, the patch and what it changes.
  - Its `world`, `dt_s`, `backend`, `inputs`, `operators` and `definition` equal those of its world's honest run, but
    for what its patch changes [B5]. The judge compares its `definition` with the honest run's as §4's execution
    record says [§9.4, WF1].
  - **P7** runs on W3p in its own process, against W3's rows at W3p's times [7b].
- **`plant.inputs_changed`** [B6].
  - It is empty, except where this file names it.
  - P2, if planted by declaration, lists exactly the two populations' `k_off`, `populations[id=matrix_L1].k_off` and
    `populations[id=matrix_L2].k_off`, each set to the other's registered value. The expected-inputs file holds the two
    values (§12.2).
  - Any other plant planted by declaration gets its list and values by a dated addendum before the judged run, taken
    from its mechanism's words alone (§14.1).
  - The judge checks each changed value.
- **The patches' scope** [N1]. Before the judged run, a reviewer who is not the builder confirms that each patch
  changes only what its row's mechanism names (CRITERIA:119-129). The lead then hashes the patches (§14.1).
- **Key paths** are written `<list>[id=<id>].<key>`, as `populations[id=matrix_L1].k_off` [B6]. A list whose members
  have no `id` names a member by its matching keys, as `free_amounts[ligand=L1,node=well].n_fmol` or
  `permeabilities[patch=specimen_face,ligand=L4].value`. A key outside a list is its dotted path, as `wash.fraction`
  [E6].
- **What each plant's criterion reads** (CRITERIA:119-129):

| Plant | Run | Keys |
| --- | --- | --- |
| P1, P2 (C1) | `W1p-P1`, `W1p-P2` | `rows[].amounts`; for P2, `plant.inputs_changed` and `inputs` |
| P3 (C3b, or refused by the dissipation check); P6 (C3b, or refused by the energy ledger) | `W1p-P3`, `W1p-P6` | `rows[].site_heat_pJ` and `amounts` |
| P4 (C7) | `W5-P4` | `step_report` |
| P5 (C6, C4a) | `W2-P5`, `W7-P5` | `event_map` (C6); `rows[].amounts` and `records` (C4a) |
| P7 (C5, C1) | `W3p-P7` | `rows[].amounts` |
| P8 (C10: refused by its own ledger) | `W1p-P8` | `status` and `refusal` |
| P9 (C9) | `W1p-P9` | `rows[].site_occupied_fraction` and `amounts`; `capacities` |

Every plant but P4 also reads `status` and `refusal` (`kind`, `raised`, `book`, `name`), since a `check` refusal can
catch it (§8.2) [P-c].

- **P5's patch changes the wash wherever the engine implements it:** its NumPy and compiled maps, and the run's own
  event [item 8]. This reads CRITERIA:125, which names the wash's mechanism, not one of its forms. With rows 4a and
  P-b, both variants must carry it and both must fail, so this cannot make a pass easier.
  - P5's `event_map` is the planted map alone on the run's own saved states (step 320 in W2; 0 and 400 in W7), in each
    variant.

### 8.2 How a plant is caught

This is CRITERIA:113-114, as RULINGS-1's reading 2 and RULINGS-2 rule it [item 5].
- **A plant run counts only toward its plant** [7d]. The criteria, C10 included, judge the honest runs; no criterion
  judges a plant run.
- **Its entries** [P-b]. A plant is caught on a criterion only when each of its registered entries for that criterion
  fails, one per (plant, criterion, world, time_s). For P5 these are its C6 entries at 4.0 s on W2 and at 0.0 s and
  1.0 s on W7, and its C4a entries on W2 and on W7.
  - *Variants:* an entry judged in both variants (C6) fails for the plant only when it fails in each.
  - *Over a run:* an entry with `time_s` null fails when its criterion fails on any formed pair of the run.
  - *With reading 2:* P5 needs both C6 and C4a, P7 both C5 and C1, and P3 and P6 either one of theirs.
  - *Information:* entries kept as information, such as P3's and P6's under C3a, never catch.
  - *Two runs:* P5 is caught only when it is caught on each of `W2-P5` and `W7-P5`.
- **Faults, gaps and values that are not finite** [§1, P-a]. On a plant run, an entry that is missing or cannot be
  formed is not caught, and neither is any entry touched by a contract fault (§11.2). A plant entry fails only where
  `agreement.py`'s `fails` is true. One whose engine value is not finite cannot be formed, so it is not caught,
  whatever `judge_constant` returns.
- **The honest baseline** [P-d]. A plant's entry is caught only where the same entry of its world's honest run passes:
  the honest W1p for P1, P2, P3, P6, P8 and P9; the honest W3p for P7; the honest W2 and W7 for P5; the honest W5 for
  P4. Where the honest entry fails or cannot be formed, the plant's entry is not caught. A catch by refusal needs the
  honest run to complete.
  - *The same entry* is the honest run's entry under the plant's key (plant, criterion, world, time_s), judged over
    all its pairs, never pair by pair [S-a].
  - *A failed baseline* is reported: a plant left uncaught because its baseline failed is reported as such, naming
    the entry [S-a].
  - *What it adds:* the baselines are pass conditions through the plants, which can only make a pass harder. P-d's
    "it adds no criterion" is read so [S-a].
- **Refusals** [P-c].
  - Only a refusal of kind `check` counts as the run's "own books or checks". The judge identifies it from `raised`
    and the book, which it maps itself from `raised` and `name` (§7). Where the plant's row names the check, the
    refusal must be that check: P3's the dissipation check (book `dissipation check`), P6's the energy ledger (book
    `energy ledger`), and P8's its own ledger (CRITERIA:123, 126, 128). P8's own ledger is the book that the mapping
    (§7) gives to the check P8's patch changes; `moiety ledger` is expected [E12; S-e]. Such a refusal catches the
    plant on that run, whatever its entries.
  - *P3* [§8]: a faithful P3 keeps the energy ledger closed, since the ledger uses the same G_site as the booking. So
    its catch is C3b or the dissipation check, never the energy ledger, and P-c stands as ruled. The patch review
    confirms that P3's patch is faithful: S_s − B_b in G_site, in both the booking and the ledger.
  - A refusal of kind `stage`, `definition`, `domain` or `harness` never counts, and neither does a `check` refusal by
    another book than the one the plant's row names. Such a run is caught only if a criterion its row names fails on
    the entries formed before the refusal [P-a, P-c].
  - **P4** is caught only by `step_report.verdict` `"admitted"` [W14]. Its entry is the whole step report: a null in
    it means the entry cannot be formed, so P4 is not caught [W-i].
  - **P8** is caught only by a `check` refusal from its own ledger. A P8 run that completes, or that ends any other way,
    is not caught; its C10 is never read as failing merely because the run did not complete.
- **A plant with no run** is not caught (§2) [11b].

## 9. Units, names and IDs

- **`units`** is exactly `{"amount": "fmol", "volume": "pL", "concentration": "mM", "k_on": "per mM per s", "k_off":
  "per s", "time": "s", "heat": "pJ", "fraction": "1", "load": "per s", "copies": "copies"}` (SPEC:15-32;
  CRITERIA:31-35). A key's suffix (`_s`, `_pJ`, `_fmol`, `_mM`, `_pL`, `_K`) repeats its unit.
- **Names are the spec's** (SPEC §2), never the engine's indices:
  - the nodes `well` and `vat`, the cell `specimen` and the patch `specimen_face`;
  - the ligands `L1` to `L5`, and the sets and populations as SPEC.md names them.

  The host entities take this file's names, `bath`, `host_cell`, `host_wall` and `host_contact` (§4.1) [§8.1, E18].
- **The fixed name map** [§8.4]. The engine names a set that is a population's own sites after the population. The
  exporter writes SPEC's set name through this map, and nowhere else: in W3 and W3p, the engine's `B_L2` is set `B`;
  in W7s, its `matrix_L1` is set `matrix`. The populations are SPEC's: `B_L2` is `B`'s one population (SPEC:170), and
  `matrix_L1` is W7s's set's only population (SPEC:244).
- **Observables** are `n:<ligand>@<node>`, `R:<set>` and `B:<population>`, the reference's own names (SPEC:368-369). A
  pool or a record is `<ligand>@<node>`.
- **What G receives** [S3]. For a node, the judge passes G the row's `n:` amounts at that node and the `R:` and `B:`
  amounts of the sets whose `faces` is that node (§4.1), keeping only names that the reference's trajectory holds.
  E and B_H run over the same names (AMENDMENT-1:24-26).
- **IDs are in today's spellings** [Q6e]. The registration's prose is read through the ID table (D345;
  `src/cells/registry/renamed_ids.py`). The rename note marks FR-45 "translated, with nothing to translate"
  (`docs/ID_HIERARCHY_DESIGN.md`:480).

| The registration's spelling (PROTOCOL:23-24, 30-34; CRITERIA:27-28) | Today's |
| --- | --- |
| `resolved_pump_composite@1` | `cells.model.resolved_pump_composite@1` |
| `resolved_pump_tissue@3` | `cells.model.resolved_pump_tissue@3` |
| `site_occupancy@1` | `cells.operator.site_occupancy@1` |
| `scheduled_compartment_wash@1` | `cells.operator.scheduled_compartment_wash@1` |
| `site_occupant_replacement@1` | `cells.operator.site_occupant_replacement@1` |
| `species_regulated_availability@2` | `cells.operator.species_regulated_availability@2` |

- **The solver** is written in today's spelling too: `cells.solver.imex_ars222_face_electromigration@1`, @3's solver,
  which RULINGS-2 §8.2 names by its old spelling (§4) [§9.3, WF6].

- **`operators`** [S7].
  - In every run it holds `cells.model.resolved_pump_composite@1`, `cells.model.resolved_pump_tissue@3` and
    `cells.operator.site_occupancy@1`.
  - In W2's and W7's runs it also holds `cells.operator.scheduled_compartment_wash@1` [Q6b, W7]. PROTOCOL:24, SPEC:225
    and CRITERIA:78-82 name the wash in W7 as in W2; CRITERIA:27-28's "in W2" is the wording from before amendment 2
    (AMENDMENT-2:8).
  - It holds exactly these, plus any operator the host tissue requires, which the lead names by a dated addendum before
    any registered run (§14.1).
  - It never holds `cells.operator.site_occupant_replacement@1` (PROTOCOL:33, 54) or an internalisation operator
    (PROTOCOL:33, 53).
  - **The model's ID** [Q6d]. `site_occupancy@1` is widened in place, as registered, which needs D148's four criteria.
    If they do not hold, the builder stops, and a new ID or an allowance is the user's choice (DECISIONS:4882-4883).
    A new ID is a registration change: if the user chooses one, the registration is amended and re-tagged before
    any run of a registered world, and this section changes in the same dated change, before the new binding tag
    [S-d; Y1].

## 10. Provenance

`source`, in every run. Every key is required, and none is null or an empty string.

| Key | Type |
| --- | --- |
| `engine_revision` | string: the 40-hex commit the run's snapshot was made from |
| `checkout_dirty` | boolean |
| `snapshot` | string: the frozen snapshot's path |
| `snapshot_patch_sha256` | string: 64 hex digits, the sha256 of the snapshot's dirty patch, an empty patch included |
| `python`, `numpy`, `scipy`, `jax`, `jaxlib` | strings: versions |
| `jax_enable_x64` | boolean: true in every run [B5, S13] |
| `jax_platforms` | string: the platform JAX reports for the run's process (`jax.default_backend()`): `"cpu"` in every run. The driver sets `JAX_PLATFORMS=cpu` where a CUDA plugin is installed, and elsewhere JAX's own default is the CPU [B5, E5; §8.2, E19] |
| `blas_threads` | integer |
| `machine` | string |
| `external_modules` | list of `{"name", "identity", "frozen"}`: each module installed from outside the checkout (AGENTS.md, D185): its import name, its identity computed at run time, and the path where the judged run freezes its files beside the snapshot; empty if there is none [W9] |

- **Run provenance** is the revision, the dirty diff and the frozen snapshot (AGENTS.md).
- **The judged run** comes from a clean snapshot of main (PROTOCOL:127-128).
  - Every run in the table has the same `engine_revision`, `snapshot` and `external_modules`, and `checkout_dirty`
    false.
  - Every run, honest and planted, uses the CPU backend in binary64: `jax_enable_x64` true and `jax_platforms` `"cpu"`
    [B5]. A departure is a fault (§11.2).
  - The lead records the revision, the runs' inputs and the execution record before the run (§4) [B5; §8.2].
- **The references' files** that the driver reads (W1eq's start) and that the judge reads are the snapshot's. Before
  reading them, the judge checks that the snapshot's files under `validation/fr45/references/`, and `agreement.py`,
  equal the binding tag's blobs; `agreement.py`'s is the registered blob (RULINGS-2 Q3). A departure stops the
  judgement [S14].

## 11. What each criterion reads

The worlds and times are the registration's (CRITERIA:72-86; AMENDMENT-1 §3; AMENDMENT-2 §3), as RULINGS-2 rules them.

- **Entries come from the registration** [B2]. The judge enumerates each criterion's compared entries from the
  registration and the references' pairs, never from the table. An entry the table lacks, or holds twice, is a fault
  (§11.2), never a skipped pair (CRITERIA:66).
- **How the classes reach `agreement.py`** [5a, 5b].
  - `derived`: `agreement.judge_derived(values, expected, tolerance)`, with the tolerance a finite non-negative float.
  - `band`: never reaches `agreement.judge` (SPEC:327-328). The judge applies the band directly.
  - `constant`: `agreement.judge_constant(values, expected)` where the constant is a number, as for C6's
    `"unchanged"` per element, with the engine's own value before the event map as the constant.
  - The two word constants, C7's `"refused"` and C10's `"completes"`: `judge_constant` converts to binary64, so it
    cannot take a word. For these two, the constant rule's exact equality applies to the outcome each row defines
    (CRITERIA:83, 86), read as §7 and the C10 row below read them.
  - *The verdict keys* [§1]. An honest pair passes only where `passes` is true, so a NaN or an infinity fails it
    (`judge_derived` gives a NaN both `passes` and `fails` false). The plant side is §8.2.
- **C3c is one-sided** [5c]. A fall of more than 16ε·E between consecutive rows fails (CRITERIA:77). Through
  `judge_derived`, `values` is the fall max(H_k − H_{k+1}, 0), `expected` is 0.0 and `tolerance` is the file's, so the
  call passes exactly when the fall is within it.
- **C4b's and C9's tolerances** [5d]. Answer 9 governs these two over SPEC:322-323.
  - C4b's pairs that hold a number and a tolerance are judged as written.
  - In pairs that hold `tolerance_terms`, the input-fixed terms come from the file. The judge forms the rest from the
    engine's saved state: C9's moiety term |R_s + ΣB − S_s|/S_s and its B_b/S_s, and C4b's free amount at the event, in
    both the expected value and the tolerance.
  - The anchor a_n is the declared start value (CRITERIA:48). R-ode's state terms in the file are information.
  - C5 bounds the engine's moiety residual on its own, so C9's self-computed term cannot excuse a residual that C5
    fails.
- **State terms that answer 9 does not name** [6]: C4a's M_l, and C3b's and C3c's E, are R-ode's. Each pair's
  tolerance is the one the file holds (SPEC:322-323, 380-382). C3c's E over the wash's interval is the references',
  taken over the post-wash state and the next row (NOTES:52).

| Criterion | Keys |
| --- | --- |
| C1 | `rows[].amounts` at the observation rows, by `step` |
| C2a | the row at the horizon's step (§5.1): its `amounts`. A run without that row fails C2a [W4] |
| C2b | W1eq's rows at steps 100, 500 and 1000, and W7's at steps 200 and 400: their `amounts` [W5] |
| C3a | `rows[].site_heat_pJ` at each interval's two rows, by `step`; no interval spans W2's steps 320 to 321 or W7's 400 to 401 |
| C3b | the same heats, and the `amounts` at both rows, passed to G per node (§9) |
| C3c | `rows[].site_heat_pJ` at every pair of consecutive rows, the wash's included [5c] |
| C4a | `rows[].amounts` and `records`, by `step` |
| C4b | `event_map[].before`, `after` and `fraction`, each variant; the declared free amounts of `inputs` for the anchor a_n [5d] |
| C4c | `events[].collected` and `supplied` |
| C5 | `rows[].amounts` (`R:`, `B:`), by `step`; `free_sites` [item 6] |
| C6 | `event_map[].before` and `after` (`R:`, `B:`), each variant [4a] |
| C7 | `W5`'s `status`, `refusal` and `step_report` (§7) |
| C8 | the three W4 runs' `rows[].amounts` (`R:`, `B:`) at W4's observation rows [item 3] |
| C9 | `rows[].site_occupied_fraction` and `amounts`; `capacities` [5d, S8] |
| C10 | every honest run's `status` and `refusal`, but W5's; in a completed run, also `checks` [B3, 7d; §8.3] |
| Every run's identity | every value §11.1 lists [S13] |

- **Which pairs hold what** [E14]. As the census shows, the file holds C3a's B_H as its tolerance, C4a's N_l and C5's
  S_s as their values, and C8's `scale` and `minimum` (item 3). So §11's rows name only what the judge reads from the
  table.
- **C8** [item 3]. The judge forms e(dt) = max |y_e − y_ref|/S over R and the B_b at W4's times, from the engine's
  rows, the file's values and its `scale`. It judges the finest dt's pairs against their tolerance and the two ratios
  against the file's `minimum`. No k enters.
- **C10** [B3, 7d]. A completed honest run meets "completes" when its `status` is `"completed"`, it holds every
  registered row, and its `checks` meets §4's rule [§8.3]. A refused honest run fails C10, W5's apart (C7).

### 11.1 Every value this file fixes [S13]

The judge checks each of these in every run. A departure is a fault (§11.2).
1. **The top level:** `kind`, `protocol` and `units` exactly (§2, §9); `runs` and `missing` hold §3's names, disjoint.
2. **The run:** `world` and `plant.id` as the run's name gives them (§3); `plant` null exactly in the honest runs;
   `status` `"completed"` exactly when `refusal` is null; `dt_s` §3's dt; `steps` as §4 defines it; `backend`
   `"compiled"` [B5; §8.2].
3. **The rows:** exactly §5.1's steps, in step order, each once; each `time_s` within 10⁻¹²·t, and 0.0 at step 0; every
   keyed object complete (§5) [B2].
4. **`capacities` and `free_sites`:** every set; each S_s within 4ε·S of α·ν·N/N_f [S8]; each form one of the two words
   [item 6].
5. **`events`:** §4's count; `kind` `"wash"`, `operator` the wash's ID, `node` the washed node, `after_step` 320 or 400,
   `time_s` within 10⁻¹²·t of the wash's time; `collected` and `supplied` complete [B2].
6. **`event_map`:** §6's entries, each (`state_step`, `variant`) once; `node`, `fraction` and `buffer_mM` equal to
   `inputs.wash`; `before` equal to its row bit for bit [B2].
7. **`step_report`:** present exactly in W5's two runs, but null at parse; `step` 1, `h_s` = `dt_s`/2 and `limit` 0.5,
   bit for bit [B7]; in `W5`, `max_load` as §7 [S2].
8. **`refusal`:** `kind` and `book` as the judge's mapping gives them from `raised` and `name` [B4]; `step` and `time_s`
   null exactly at parse.
9. **`operators`:** exactly §9's [S7].
10. **`inputs`:** the echo of §4.1 [S5]; its host values against the host-entity addendum [§9.6].
11. **`source`:** every key present, of its type; `engine_revision`, `snapshot` and `external_modules` the same in every
    run; `checkout_dirty` false; `jax_enable_x64` true; `jax_platforms` `"cpu"` [B5, W9].
12. **`record_sha256`:** 64 hex digits.
13. **`definition`:** its execution block and bounds equal its honest run's execution record; its literal fields
    equal this file's; and a plant run's `definition` equals its honest run's once its declared `inputs_changed` is
    applied (§4) [§8.2, N3; §9.1, N4; §9.4, WF1].
14. **`driver`:** `window_steps` 1 [§9.5, WF4].

### 11.2 Faults, and how they are scored [§1, item 4]

- **A fault** is any departure from a type, value or equality this file fixes (§11.1), including a missing, extra or
  duplicated row, event, map entry or keyed member [item 4, B2, S13].
- **Which entries a fault touches.** A fault touches every entry that reads the faulty key (§11's table, §8.1's). A fault
  of the run's identity (§11.1, items 2, 3, 4, 9, 10, 11, 13 and 14 [§8.2; §9.5]) means the run is not the registered
  world, so it touches every entry of the run [E8]. A fault of the table's top level (item 1) touches every entry of
  every run, and a fault of a run's record hash (item 12) touches every entry of its run [S-c].
- **On an honest run,** a criterion passes or fails, and inconclusive arises only from the references' convergence
  (CRITERIA:41-44; RULINGS-2 rows 1b, 1c). An entry that is missing, cannot be formed, or is touched by a fault cannot
  pass, and its criterion fails [§1, B1].
- **On a plant run,** that same entry is not caught (§8.2) [§1, P-a].
- **Why.** Each is the reading that cannot make a pass easier. A fault that failed a criterion on a plant run would catch
  the plant, which is the easier reading there [B1].
- **A `harness` refusal of an honest run** fails C10 and every criterion that reads that run [S9].
- **A re-run** is ruled before its table is opened, and the first table is kept beside it [S9].
- **Nothing is skipped** (CRITERIA:66).

## 12. The format sample, the expected-inputs file, and the order at the judged run

### 12.1 The format sample [item 1]

- **Who writes it.** An agent who is not the builder and has seen no reference value writes it by hand from this file,
  before the binding tag, and the lead hashes it [item 1]. Since the judge is the builder's own, only a sample that is
  not the builder's can expose a shared misreading.
- **Its path and form** [E10]. The folder `validation/fr45/spec/table_sample_INVENTED/` holds:
  - `table/table.json` and `table/SHA256SUMS`, laid out as §1 lays out the table;
  - `start_INVENTED-W1eq.json`, the invented file that its W1eq-shaped run reads its start from, at §3's paths;
  - `README.md`, which lists every key and type to the leaf, each run and what it shows, and the numbers below.
- **Its names** [E10].
  - Each run is named `INVENTED-` and the registered run name (§3) whose shape it takes, as `INVENTED-W1p-P8`. W4's
    three carry their own invented dt, as `INVENTED-W4-dt0.125`. A second run of one shape adds `~` and a refusal
    kind, as `INVENTED-W3~definition`.
  - Each world is named `INVENTED-` and the registered world's name. Its nodes, ligands, sets and populations have
    invented names.
  - The judge maps a sample run to its registered shape by its name.
  - The top level holds one extra key, `INVENTED`, a string, which every comparison skips.
- **Its numbers** [W2, E10]. It holds none of SPEC.md's input values, except the format constants this file fixes:
  - step 0, with its clock 0.0, at the start; the cumulative heat 0.0 at the start; the records 0.0 before the wash;
  - `step_report.step` 1, `limit` 0.5 and `driver.window_steps` 1 [§9.5];
  - the registered `permeabilities` 0.0, `multipliers` 1.0 and `charges` 0.

  Every other number in it is invented and meaningless, including its N_f, T and traces. The step counts of its
  invented runs (`rows[].step`, `steps`, `after_step`, `state_step`, `refusal.step`, a failure's `step`) count those
  runs' steps and are not input values.
- **What it covers:**
  - a completed run of each shape a registered world has: a node-owned set with two ligands; a start read from a file;
    a wash, with its event and its map on the wash row (W2's shape), and on the start and the wash row (W7's), in both
    variants; a cell inside a patch, with a set on its inside face (W3's) and one on a patch's outside face (W6's);
    one world at three steps; a one-population set; W7s's absent ligand held at its trace;
  - the bath form's host entities and capacitor component in every world, `backend` `"compiled"`, `multipliers` as
    `site_binding_multiplier`, and an execution block in `definition` [§8.1, §8.2, §8.5]; `host_values` and `driver`
    [§9.5, §9.6];
  - W5's two shapes, refused by the stage condition and admitted;
  - an unregistered compartment (§4.1), and a plant run whose `inputs_changed` is not empty;
  - a refused run of each kind, a plant run of each shape in §8.1, and a non-empty `missing`;
  - every key of 27 November: `raised`, `book`, `free_sites`, `permeabilities`, `multipliers`, `charges`,
    `jax_platforms` and `external_modules`.
- **Its hashes:** the lead records the sha256 of each of its files in a dated note in this folder, before the binding
  tag, with the expected-inputs file's (§12.2).
- **The judge reads it** before the judged run, with the code that will read the table, in a structure-only mode.
  - It checks keys, nesting, types, the nulls this file allows, the words it fixes (kinds, books, variants, verdicts,
    units, operator IDs, the plant ids) and the counts it fixes (one event; two or four map entries). It checks no other
    number, list length or equality between numbers [E10].
  - It must find no fault, and it reports the entry kinds it found.
  - The references' `format_sample_INVENTED.json` is a different file, the one the judge reads first
    (PROTOCOL:129-130).
- **The builder's exporter must match it** [item 1]. At the judged run's snapshot, the exporter writes a table on the
  sample's invented worlds, and the lead compares it with the recorded sample, key by key and type by type. The
  comparison is structural. A difference goes to this file's author before the judged run, never after.
- **Each refusal example's cause** is named in the sample's README: an invented input or a planted patch, never a
  changed bound [§8.8, X2-r].
- **A fault found in the sample** stops the binding tag or, at the judged snapshot, the judged run [W12, item 1].
- **What may never be taken from it:** a number, a list length, an order of keys or entries, or an equality between its
  numbers. No tolerance, scale or verdict depends on it.

### 12.2 The expected-inputs file [S5]

- **What it is:** `validation/fr45/spec/expected_inputs.json`, written from SPEC §2 by the agent who writes the format
  sample, before the binding tag. The lead hashes it with the sample.
- **What it holds:**
  - each honest run's `inputs` in §4.1's shape, derived fields included: W3p is W3's inputs with SPEC:182's times, and
    W4 has one entry per dt. A plant run's expected inputs are its world's honest run's (§8.1);
  - a `null` wherever §4.1's exceptions leave a value unfixed: W1eq's start, which it does not hold because the driver
    reads it at run time (§3; item 2), and RT;
  - the bath form's host entities in every world, with their structure and constraints, and each world's capacitor
    component [§8.1, §9.6];
  - at each host volume, each host trace and `host_values`, the marker "from the host-entity addendum" in place of a
    literal; the host traces follow the addendum's volumes [§9.6];
  - each population's `site_binding_multiplier`, at 1.0 [§8.5];
  - the two values of P2's crossed `k_off`, if P2 is planted by declaration (§8.1) [B6];
  - its own statement of these rules.
- **How it is used:** the judge compares each echo with it (§4.1), never with its own copy, after the cross-check
  against the references' echo (§4.1, §12.3).

### 12.3 The order at the judged run

- **Before the build** [12b]: the builder receives the census (keys, types and counts; no value) and writes the judge
  against it and against the references' invented file (SPEC:391-392).
- **At the judged run**, in this order:
  1. the judge checks the snapshot's references' files and `agreement.py` against the binding tag's blobs (§10) [S14];
  2. its structure-only pass over the registered reference files, before any registered engine run [12b]. A form the
     judge cannot map onto its criterion's text is reported then, so an erratum, if one is needed, comes before a
     registered run [12b, Who c];
  3. the cross-check of the expected-inputs file against the references' echo (§4.1) [S5]. A departure stops the judge
     before anything is scored;
  4. the structure-only pass over the format sample (§12.1), if it has not been made at this snapshot;
  5. the lead's comparison of the builder's exporter output on the sample's invented worlds with the sample, key by
     key and type by type (§12.1) [W-c];
  6. the runs, each registered world's first;
  7. the table's sha256 (§1), and then the judgement.
- **A parse-only pass** of a registered world, a definition check with no step, is not a run, and is allowed before
  step 6 [§8.6], but none of W1eq [§9.2, WF5]. The execution record and the host-entity addendum come from these
  passes (§4, §4.1) [§9.1, §9.6].
- No class or pair changes after a run (PROTOCOL:101; CRITERIA:66) [12b].

## 13. The readings settled here

These are the reader's readings 8, 9, 10 and 13 (`/mnt/workspaces/Cells/fr45-readings-20261126/sentences.md`), each
marked silent there. Each is settled as a format, and none changes a criterion.

| Reading | The contract's row | Kind | Lines it rests on |
| --- | --- | --- | --- |
| 8. Row matching: by step count or by time | By step. The row at a registered time is the row whose `step` is that time's integer in §5.1, and its clock must equal t within 10⁻¹²·t (§5.1) | silent: the stricter reading | CRITERIA:47; SPEC:104, 158-159, 233-234, 368, 380, 390; PROTOCOL:165; AMENDMENT-1:41-44 |
| 9. C3a's engine heat: a cumulative difference, or an interval heat | A cumulative difference. There is one record: each facing node's cumulative site heat at each row, booked by the engine's binding routes and never formed from states. C3a's and C3b's interval heat is its change between the interval's rows, and C3c reads the same record (§5.2) | silent: the stricter reading | CRITERIA:75-77; AMENDMENT-1:44-49, 94-98, 101-104; PROTOCOL:45-46, 87-88; SPEC:307-311 |
| 10. C7: what the refusal must name and report | Refusal kind `stage`, as the judge maps it, at step 1, with no row after the start, and the engine's own `step_report`: h (`dt_s`/2), every load at the first stage, the largest, h·max L, the limit (0.5) and the verdict. C7 compares the report's `h_max_load` with 1/2 and reads its `verdict`; in W5 the largest load is the set's summed L_R [B7, S2]. P4 reads the same `verdict` (§7) | silent: the stricter reading; the limiting load open, the stricter [S2] | CRITERIA:83, 124; SPEC:74-79, 339-347, 385; PROTOCOL:113, 166-167; AMENDMENT-1:72 |
| 13. C9 "from the engine's quantities on the saved state" | The exporter calls the engine's `quantities` on each row's saved state in the run's process, and exports `site_occupied_fraction` per population: never a value from inside a step, and never B/S formed by the exporter. Every row of every run carries it (§5.3) | silent: the stricter reading | CRITERIA:85, 129; AMENDMENT-1:41-43, 54-55; PROTOCOL:34, 50, 141 |

## 14. Ruled

The eight items this section left open on 26 November are ruled in RULINGS-2's §3
(`/mnt/workspaces/Cells/fr45-readings-20261126/RULINGS-2-2026-11-27.md`). This file applies them here:

| Item | Applied in |
| --- | --- |
| 1. Who writes the format sample | §12.1 |
| 2. W1eq's start | §3; §4.1, its exceptions |
| 3. k_t, and C3b's k | §5.1, the tolerances; §11, C8 |
| 4. How a contract fault is scored | §11.2 |
| 5. Reading 7, and the open part of reading 2 | §3; §8.2; §11, C10 |
| 6. A one-population set's free sites | §4, `free_sites` |
| 7. Compartments SPEC §2 does not name | §4.1 |
| 8. P5's patch in both forms of the map | §8.1 |

**Item 3's intervals, corrected** [W1]. The forms of C3b's k differ on two judged intervals only, both computed from
SPEC's inputs:
- W2's 4.0125 to 5.0 s: 79 steps, 78.99999999999999 as (t₂ − t₁)/dt, and 79.0 as t₂/dt − t₁/dt;
- W7's 1.0025 to 1.5 s: 199, 199.00000000000003 and 199.00000000000006.

The 26 November text also listed the wash's own intervals, which C3b never judges. For k_t the forms differ only at
W7's 1.0025 s, where t/dt is 400.99999999999994. No tolerance is formed from either (§5.1). If one ever had to be, it
would take the smallest form at each point (RULINGS-2 §3, item 3, the review's option d).

### 14.1 What is owed, and what may still change after the binding tag [Who c]

**Done before the binding tag** [S-d; §8]: a reviewer who is not the builder confirmed against `src/` that the
engine holds SPEC §0's units natively on these worlds' path, so no conversion rule is needed (§1; the lead's log).

**The addenda this file calls for** ("Who c"'s first kind). Each is dated, disclosed and hashed by the lead, and made
before any run of a registered world:
1. the refusal mapping, from the engine's exceptions and check names to `kind` and `book`, confirmed against `src/` by
   a reviewer who is not the builder (§7) [B4]. It includes the stage identification, which the build adds: W5's
   first-stage report, and the way to tell a stage refusal from other domain failures [§8.6];
2. the list of ledgers and host checks, giving for each its name, the worlds or declared operators that evaluate it,
   and its cadence (§4) [B3; S-b]. No check records a mode, since E3 is withdrawn [§8.3];
3. the backend every run uses (§4) [B5]: settled now as `"compiled"` [§8.2], so no addendum is owed;
4. the changed inputs of any plant planted by declaration other than P2 (§8.1) [B6], and, for every plant planted
   by declaration, P2's included, where each changed value sits in `definition` (§4) [§9.4, E24];
5. any compartment or patch beyond the registered ones and the bath form's (§4.1), and any operator the host tissue
   requires (§9) [item 7, S7];
6. the host-entity addendum: the host compartments' volumes, every patch's area and capacitance, registered patches
   included [§9.6+], the ions' amounts in every compartment and the ions' permeabilities on the host patches, kept per
   honest run (§4.1). It is
   recorded after the build and before any registered run, confirmed against the wash fixtures' form by the
   non-builder reviewer, and hashed by the lead [§8.1; §9.6].

**The erratum** ("Who c"'s second kind): an erratum where a judge must change (D371).

**Registration changes, not addenda** [S-d]. A unit conversion found after the tag (§1), and a new model ID (§9),
are changes of the registration: it is amended and re-tagged before any run of a registered world. "Who c" is
unchanged.

**Records, not changes.** Before the judged run:
- a reviewer who is not the builder confirms that each plant's patch changes only what its row's mechanism names
  (CRITERIA:119-129), and that the refusal mapping covers every exception and check name a patch can raise; the lead
  then hashes the patches (§7, §8.1) [N1];
- the same reviewer confirms against `src/` the list of checks, with each check's name, the worlds or operators that
  evaluate it and its cadence; the multipliers the engine applies, and where its declaration holds permeabilities;
  and the engine's form for free sites (§4, §4.1) [N2; §8.3];
- the execution record, the honest runs' `definition` execution block and bounds: from a parse-only pass of every
  registered world but W1eq, made after the build and before any registered run; confirmed by N2's reviewer
  against `src/` (the default `field_solver`, and each species' `material_balance_atol_fmol` at the species
  helper's floor); and hashed by the lead (§4) [§8.2, N3; §9.1, N4];
- the lead records the runs' inputs and revision (§4, §10).

**An open registration question** [§8.7]: X2 (D224), the user's. It blocks the judged run, not the binding tag.
- D224 makes X2 a check that registered and judged runs must select, each registration with its own cap. FR-45
  registers no cap.
- On FR-45's path X2 would count nothing: the ligands move in the site operator's half-steps, whose bookings are
  exact.
- The two routes: FR-45 is amended with a cap and re-tagged before any registered run, or the user waives X2 for it.
- Until the answer, the execution record has no `energy_check` (§4).

## 15. Disclosures

### 26 November 2026

- **What the author read:**
  - the registration's seven files, NOTES, the reader's `sentences.md` and `facts.md`, and the lead's first rulings;
  - FR-43 part 3's `TABLE.md`, the ID table and the rename note's FR-45 row;
  - of the references' outputs, key names and types, and the names of nodes, sets and observables.
- **A slip.** One inspection command printed values instead of keys, once, for four reference files:
  - `reference_W5.json`: `world`, `stage` and `plants`;
  - `reference_W7.json`: `world`, `equilibrium` with `theta`, `wash` and `plants`;
  - `reference_W1eq.json`: `world` and `equilibrium`;
  - `reference_W4.json`: `world`, `equilibrium` and `closed_form`.

  No trajectory, balance, heat, pair or distance at the horizon was shown. No number in this file comes from them.
  Every number here is SPEC.md's, or computed from its inputs alone (§5.1's steps and clock bound), or a format
  constant of this file.
- **One search of `src/`** for the quantity's name showed two engine lines. Nothing here rests on them.

### 27 November 2026 (the dated change)

- **Who made it:** an agent who has seen no reference value, which also wrote the format sample (§12.1) and the
  expected-inputs file (§12.2).
- **What it read:**
  - RULINGS-1 and RULINGS-2, the review, the lead's census and the references' format note;
  - the registration's seven files at the amendment-3 tag, and this file as of 26 November;
  - of the reader's `sentences.md`: its head and summary, its NOTES and decision-log quotes, and the readings' text; of
    `facts.md`: its head and summary;
  - the registered `agreement.py`, and FR-43 part 3's contract on main;
  - of the references' invented file, at `fr45-references-v2-2026-11-24`: its top-level keys, its `world`, its
    `INVENTED` note, its `schema` and its `units`. Its numbers are invented, and none of them is used here.
- **What it did not open:** any other file under `validation/fr45/references/`, any FR-45 judge folder or script, and
  `src/`.
- **What it ran,** each under `systemd-run --user --scope -q -p MemoryMax=4G taskset -c 23`: the binary64 checks of
  §5.1 and §14 on SPEC's inputs, the writers of the sample and the expected-inputs file, and their checks. They are in
  `/mnt/workspaces/Cells/fr45-contract-edit-20261127/tools/`.
- **Its numbers:** every number it adds is SPEC.md's, computed from its inputs alone (§14), or a format constant of
  this file.
- **The editor's own format sentences, for the lead** (each the reading that cannot make a pass easier):
  - [E1] The driver never builds a world from the expected-inputs file (the header). Amended by WD1: except the
    host entities' structure and constraints, which SPEC does not give.
  - [E2] A value that is not finite is written as `null`, which the judge reads as such (§1).
  - [E3] `checks` is `{"failures": [...]}` per listed check; the judge also checks the raising mode that `definition`
    records, at a place the addendum names (§4). The mode's part is withdrawn by RULINGS-2 §8.3.
  - [E4] `raised` is null only in a `harness` refusal that no exception ended; `book` is null for every kind but
    `check` (§7).
  - [E5] B5's "CPU backend" is recorded as `source.jax_platforms` `"cpu"`, beside `jax_enable_x64` true, and the
    lead's recorded `backend` (`"numpy"` or `"compiled"`) is the one every run uses (§4, §10). Confirmed [W-e], and
    settled by §8.2: `backend` is `"compiled"`.
  - [E6] Key paths for a list without `id` name the member by its matching keys (§8.1).
  - [E7] W2's L2 is declared: SPEC gives its amount, which equals its trace (§4.1).
  - [E8] A fault of the run's identity touches every entry of the run (§11.2). S-c adds a fault of the top level and
    of a record's hash.
  - [E9] `permeabilities` are in the engine's own unit; `multipliers` are keyed by `of` and the engine's `name`, so
    the expected-inputs file gives only their value (§4.1). Superseded for `multipliers` by §8.5: exactly each
    population's `site_binding_multiplier`.
  - [E10] The format sample's path, names, extra key and allowed constants, and what its structure-only pass checks
    (§12.1).
  - [E11] The cross-check's key map, and what it leaves out (§4.1). Since §7 it also compares `free_amounts[].declared`.
  - [E12] P8's own ledger is the moiety ledger, book `moiety ledger` (§8.2). Amended by S-e: the book is the one the
    mapping gives to the check P8's patch changes, and `moiety ledger` is expected.
  - [E13] S8's sentence is read with rows 5b and item 3: a pair that holds its own value or `scale` (C5's S_s, C8's S)
    is judged with the file's (§4). §7 amends S8's sentence to "every S the judge forms from the engine's state comes
    from `capacities`" [W-d].
  - [E14] W6 is applied under item 3: since the file holds C3a's B_H, C4a's N_l and C5's S_s, §11's rows name only what
    the judge reads from the table (§11).

### 27 November 2026, the second dated change

- **What it applies:** RULINGS-2's §7, which confirms the E marks above as applied (E5 by W-e, E13 by W-d), amends E8 by
  S-c and E12 by S-e, and accepts every finding of the second review.
- **What it read besides the first change's files:** RULINGS-2's §7, and the second review, `REVIEW-2.md`, whole,
  although its §2 holds the findings.
- **What it did not open:** any file under `validation/fr45/references/` beyond the invented file, any FR-45 judge folder
  or script, and `src/`.
- **What it ran,** under the same scope: the sample's writer and its two checks. The structure reader was first made to
  require S-f's two runs, all four forms of `book` and W-a's path, and it failed on the earlier sample as it should.
- **What it left alone:** the expected-inputs file. Its W7s note says less than S-g, since it does not name the `charges`
  member, but it does not contradict it, and this file governs (§4.1).

### 27 November 2026, the third dated change

- **What it applies:** RULINGS-2's §8, with its findings from `src/` and the third read's.
- **What it read besides the earlier files:** RULINGS-2's §8, and the third read, `REVIEW-3.md`, whole.
- **What it did not open:** any file under `validation/fr45/references/` beyond the invented file, any FR-45 judge folder
  or script, `src/`, and the readings folder's cross-check files.
- **What it ran,** under the same scope: the writers of the sample and the expected-inputs file, and their checks. The
  structure reader was first made to require the bath form, `"compiled"`, `site_binding_multiplier`, the execution
  block and each refusing twin's visible cause, and it failed on the earlier sample.
- **The editor's format sentences of this change** (each the reading that cannot make a pass easier):
  - [E15] The judge compares the host entity values in `definition` with their addendum (§4.1, §11.1). Superseded by
    §9.6: the host's values are in `inputs`, and the judge compares them with the host-entity addendum.
  - [E16] Ions are also out of `permeabilities`, `wash.buffer_mM` and the event's `collected` and `supplied`, so that
    an engine's ion entry there is no extra member (§4.1, §6).
  - [E17] The capacitor component's key, `capacitor_components`, and its form, `{"members", "held_by"}` (§4.1).
  - [E18] The host's names, `bath`, `host_cell`, `host_wall` and `host_contact`, and its volumes in the expected-inputs
    file (100.0 pL for `bath`, 0.01 pL for `host_cell`): host choices that RULINGS-2 §8 does not fix, made by the
    editor. The volumes are superseded by §9.6: they come from the host-entity addendum. The names stand, fixed at
    the tag.
  - [E19] `jax_platforms` records what JAX reports, so that a CPU-only machine, where `JAX_PLATFORMS` is unset, still
    records `"cpu"` (§10).
  - [E20] The cross-check leaves out the host entities and every patch field that names one, since the references hold
    none of them (§4.1).
  - [E21] The sample's host-check refusal is a plant run with a planted patch, since no invented input can trip a host
    check while ions are held and ligands are impermeant (§12.1; the README).

### 27 November 2026, the fourth dated change

- **What it applies:** RULINGS-2's §9, which accepts every finding of the fourth read.
- **What it read besides the earlier files:** RULINGS-2's §9, and the fourth read, `REVIEW-4.md`, whole.
- **What it did not open:** any file under `validation/fr45/references/` beyond the invented file, any FR-45 judge folder
  or script, `src/`, and the readings folder's cross-check files.
- **What it ran,** under the same scope: the writers of the sample and the expected-inputs file, and their checks. The
  structure reader and the expected file's check were first made to require `driver`, `host_values`, the solver's new
  spelling and the addendum's markers, and they failed on the earlier files.
- **The editor's format sentences of this change** (each the reading that cannot make a pass easier):
  - [E22] W1eq's execution block is compared with W1's record apart from its start and from the fields that `inputs`
    fixes differently for W1eq, its observation times and horizon, so that an honest W1eq cannot fail on them (§4).
  - [E23] The run's driver record is a new key of the table, `driver`, `{"window_steps"}`, present in every run (§4).
  - [E24] The B6 addendum names where each declared change sits in `definition`, P2's included, so that the judge can
    apply `inputs_changed` to `definition` from the table and the addenda alone (§4, §14.1).
  - [E25] The host values' key, `inputs.host_values`, and its form: `areas`, `capacitances` and `ion_permeabilities` by
    host patch, `ion_amounts` by compartment, each the engine's own value with no unit suffix (§4.1). Amended by §9.6+:
    `areas` and `capacitances` are keyed by every patch, registered and host.
  - [E26] In W3 and W3p the wall's inside is `specimen`, the world's own cell. §9.6 says that each host patch's inside is
    `host_cell`, which those two worlds do not hold (§4.1).
  - [E27] The host-entity addendum is kept per honest run, its values copied by machine from the parse-only pass; W1eq
    takes W1's, and a plant run its honest run's (§4.1).

### 27 November 2026, the fifth dated change

- **What it applies:** the lead's addition to RULINGS-2 §9.6, ruled on 27 November [§9.6+].
- **What it ran:** the sample's writer, the structure reader, the README's path check and the expected file's facts
  check. The structure reader was first made to require every patch's area and capacitance, and it failed on the
  earlier sample's runs that hold a registered patch.
