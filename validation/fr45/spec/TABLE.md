# FR-45's engine table: the contract

**Dated 26 November 2026, and changed on 27 November 2026** (the next section), before the binding tag and before any
engine run of a registered world. The registration never defines the engine's table, so the lead ruled that a dated
contract fixes it before the binding tag, from the spec's text (the lead's first rulings, Q5:
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
- **It fixes formats, not tests.** No criterion, band, class, world, input, plant, tolerance or scoring rule changes.
  Where the text is silent on a format, the contract takes the reading that cannot make a pass easier and marks it
  **(silent: the stricter reading)**. §13 settles the reader's readings 8, 9, 10 and 13 this way. Where RULINGS-2
  rules, the contract applies the ruling and names it (the next section).
- **What each side reads.**
  - The driver builds each world from SPEC.md's inputs, and W1eq's start from the references' file (§3). The exporter
    reads back only what the engine parsed and ran (§4.1) [S4]. The driver never builds a world from the
    expected-inputs file (§12.2), so that the echo compares two transcriptions of SPEC [E1].
  - The judge reads this file, the table, the expected-inputs file (§12.2), the references' files and their G
    function (CRITERIA:76; NOTES:178-186), and `agreement.py` (CRITERIA:29).
  - The judge imports the standard library, NumPy, the registered `agreement.py` and the references' `G`, and nothing
    else: nothing from `src/`, and no other module of the references [Q4b, Q4c].
- **How this file may change** [Who c].
  - *Before the binding tag,* by a dated change, through the lead. A key the judge needs that is not here is asked for
    through the lead and added so, never taken from the other side's code.
  - *After the binding tag,* only by "Who c"'s two kinds, each dated, disclosed, hashed by the lead, and made before any
    run of a registered world: (1) the addenda this file calls for, listed in §14.1; (2) an erratum where a judge must
    change (D371, DECISIONS:12279).
  - *After a run,* nothing changes. A registered world's first run is in the judged run. The builder develops and
    tests on invented worlds, such as the format sample's (§12.1) [Who c].
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
  - This assumes that the engine holds amounts, volumes, concentrations, times and heats in SPEC §0's units (§9). If it
    does not, the builder reports it to the lead before any registered run. A conversion rule then enters by a dated
    change before the binding tag; after the tag it is not among "Who c"'s listed addenda, so it needs the lead's
    ruling (§14.1) [Who c].
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
    They are not criteria, and count only through the plants.
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
  judged run [Who c].
- **P5's runs** are full planted runs of W2 and W7. C4a reads their rows (NOTES:103-104), and C6 their own `event_map`
  (§6).

## 4. A run's entry: one shape for every run

Every entry holds every key below, for honest, plant and refused runs alike.

| Key | Type and meaning |
| --- | --- |
| `status` | `"completed"` or `"refused"`; `"completed"` exactly when `refusal` is null [S13] |
| `world` | string: the run's world (§3) |
| `plant` | null in an honest run; else `{"id", "patch", "change", "inputs_changed"}`: the plant (`P1` to `P9`, as the run's name gives it), the scoped patch's path under `validation/` (CRITERIA:111-112), one line naming what it changes, and the list of `inputs` key paths it changes (§8.1) |
| `dt_s` | number: the step the engine ran, §3's dt bit for bit |
| `steps` | integer: the steps completed: the last row's `step`, or the steps before a refused one |
| `backend` | `"numpy"` or `"compiled"`: the engine's implementation that the run's steps used. Every run, honest and planted, uses the one the lead records with the runs' inputs before the judged run, and a run whose `backend` departs from that record is a fault [B5]. Its arithmetic is binary64 on the CPU (§10) |
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
| `definition` | object, or null before parse: the engine's own declaration of the world, as run. It is recorded, and the judge reads in it only each check's mode (below) [B3] |
| `source` | provenance (§10) |
| `record`, `record_sha256` | the run's own record file, by its path relative to `table/`, and its sha256 (64 hex digits); recorded, and checked for type only |

- **`capacities`** [S8]. The judge checks each S_s against α·ν·N/N_f of the echoed inputs (§4.1), within 4ε·S, which
  covers two routes of three roundings each. Where the judge forms a quantity from the engine's state that needs S
  (C9's B_b/S_s and its moiety term), S comes from `capacities`. A pair that holds its own value or `scale` (C5's S_s,
  C8's S) is judged with the file's, as §11 says [S8, E13].
- **`free_sites`** [item 6]. At a `"derived"` set, C5 holds by construction. It still counts, because CRITERIA:81 covers
  every set, and the verdict names each such set. Requiring free sites as state is a design rule the registration does
  not make (SPEC:53).
- **`events`** [B2]. A completed run of W2 or W7, honest or planted, holds exactly one event, after step 320 (W2) or
  400 (W7). A run of any other world holds none. A refused W2 or W7 run holds the event if the engine applied it
  before the refusal, and none otherwise.
- **`checks`** [B3].
  - *Its members:* every ledger and host check, from a list fixed by a dated addendum before any registered run
    (§14.1). Each is keyed by its name in that list, as `{"failures": [...]}`: the engine's own record of each failure
    of that check, `{"step", "message"}`, with `step` the steps completed when it was recorded [E3].
  - *The mode:* the driver runs each check in its raising mode, which `definition` records. The addendum names, for
    each check, where `definition` records its mode [E3].
  - *C10:* a completed honest run fails C10 if its `checks` is null, lacks a listed check or records a failure, or if
    `definition` does not record a listed check's raising mode [B3, E3]. If every check raises, nothing changes.
  - *Honest runs only:* on a plant run, a failure recorded without a refusal is not a catch [P-c].
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
| `nodes` | list of `{"id", "kind", "volume_pL", "registered"}`; `kind` is `"node"` or `"cell"`; `registered` is false for a compartment SPEC §2 does not name (below) |
| `patches` | list of `{"id", "inside", "outside"}` (W3, W3p, W6); empty in the others |
| `ligands` | list of strings |
| `free_amounts` | list of `{"ligand", "node", "n_fmol", "declared"}`: every ligand of `ligands` at every node and cell, as the engine parsed it. `declared` is false for a trace (SPEC:104-106) |
| `sets` | list of `{"id", "shared", "owner", "face", "faces", "copies", "sites_per_copy", "accessible_fraction"}`, described below |
| `populations` | list of `{"id", "set", "ligand", "k_on", "k_off", "initial_occupancy"}`. `k_on` and `k_off` are the values the binding routes use [S6] |
| `wash` | null, or `{"time_s", "node", "fraction", "buffer_mM"}`, with `buffer_mM` an object ligand → mM (W2 and W7: SPEC:152, 225) |
| `permeabilities` | list of `{"patch", "ligand", "value"}`: each ligand's permeability on each patch, in the engine's own unit; registered 0.0 (SPEC:59-61). Empty in a world without a patch [S6, E9] |
| `multipliers` | list of `{"of", "name", "value"}`: every multiplier the engine applies to a population's rates or a set's capacity, with `of` the population or set and `name` the engine's own name for it; registered 1.0 (SPEC:62). Empty if the engine applies none [S6, E9] |
| `charges` | object, ligand → integer: each ligand's valence, for every ligand of `ligands`; registered 0 (SPEC:59) [S6] |
| `dt_s`, `observation_times_s`, `horizon_s` | number, list of numbers, number |

- **A set's keys:**
  - `shared` is false for a one-population set and true for every other. The registration's worlds decide the form
    (SPEC:53, 169, 244): a one-population set (W3's `B`, W7s's `matrix`) is declared as its population's own sites,
    with `shared` false [S10].
  - PROTOCOL:55 lists "a set named by fewer than two populations" among version 1's refusals. A refusal of W3 or W7s
    under it is a C10 failure, not a format fault [S10].
  - `owner` is a node or a patch. `face` is `"inside"` or `"outside"` for a patch's set, and null for a node's.
  - `faces` is the facing node or cell (SPEC:55-58).
- **W2's L2 is declared,** since SPEC gives its amount (SPEC:148), which equals its trace [E7].
- **W7s's registered `ligands` is `["L1"]`** [S11]. An engine that holds L2 there lists it at its trace (`declared`
  false), and the echo treats that list entry and its amount as information.
- **Compartments SPEC §2 does not name** [item 7].
  - A world holds none, except W6's cell inside `specimen_face`, which SPEC does not name (SPEC:210), unless the lead
    names one by a dated addendum before any registered run (§14.1).
  - Each is listed in `nodes` with `registered` false, under the engine world's own name, with its volume recorded.
  - Its free amounts are traces. Each is compared with the trace, 10⁻¹² mM times the compartment's `volume_pL`
    (SPEC:104-105) [item 7]. In the rows they are information.
- **The echo** [S5]. The judge compares each run's `inputs` with that run's entry in the expected-inputs file (§12.2),
  bit for bit: "Every number below is a binary64 literal as written" (SPEC:104). It never compares with a copy of its
  own.
  - An extra, missing or different key or value means the run is not the registered world, which is a fault (§11.2).
  - Lists are compared as sets of members, matched by `id`, by `ligand` and `node` (free amounts) or by `patch` and
    `ligand` (permeabilities). `ligands` and `observation_times_s` are compared as sets of values, with no member
    twice. Numbers are compared as binary64 values.
  - `constants.sites_per_fmol` and `temperature_K` are compared exactly (SPEC:35, 38).
  - **A trace at a registered compartment is compared too,** against 10⁻¹² × the compartment's `volume_pL` [W11]. At
    every registered volume that product is exact in binary64.
  - **The exceptions, a closed list.** The expected-inputs file marks each where it applies.
    - `constants.RT_pJ_per_fmol` is recorded, since SPEC gives RT as a formula, not a literal (SPEC:36-39).
    - W1eq's start, its `populations[].initial_occupancy` and `free_amounts[].n_fmol`, is compared with the
      references' file instead (§3) [item 2].
    - W6's unregistered cell (above) [W10, item 7]. Its `nodes` entry has an `id` that names no registered
      compartment, `kind` `"cell"`, `registered` false and any positive `volume_pL`. Its `free_amounts` entries have
      `declared` false and are compared with the trace. The `patches` field that names it, `specimen_face`'s
      `inside`, holds its `id`.
    - W7s's L2, if the engine holds it (above) [S11].
    - `multipliers`, whose members are the engine's own: each member's `value` is 1.0 [S6, E9].
    - A key path that a plant run's `plant.inputs_changed` names, whose value is checked as §8.1 says [B6].
- **The cross-check of the expected-inputs file** [S5]. Before any registered run (§12.3), the judge checks the
  expected-inputs file against the references' `world` echo (SPEC:365) wherever their keys overlap, since both
  transcribe SPEC independently. A departure stops the judge before anything is scored. The overlap is set out below,
  by the key names that the references' invented file and the lead's census show [E11].

  | Expected-inputs key (this section's) | References' `world` key | Cross-checked |
  | --- | --- | --- |
  | `constants.sites_per_fmol`, `temperature_K` | `constants.N_f_sites_per_fmol`, `T_K` | equal |
  | `nodes[id=…].kind`, `volume_pL` | `nodes[id=…].kind`, `V` | equal, for every node with a name in the expected file |
  | `patches[id=…].inside`, `outside` | `patches[id=…].inside`, `outside` | equal, where the references list the patch and the expected file holds a name |
  | `ligands` | `ligands` | the same members |
  | `free_amounts[ligand=…,node=…].n_fmol` | `free_amounts[ligand=…,node=…].n` | every entry the references list is in the expected file, with the same amount |
  | `sets[id=…].copies`, `sites_per_copy`, `accessible_fraction`, `faces` | `sets[id=…]`, the same four keys | the same sets, equal |
  | `populations[id=…].set`, `ligand`, `k_on`, `k_off`, `initial_occupancy` | `populations[id=…]`, the same five keys | the same populations, equal |
  | the `faces` of the population's set | `populations[id=…].faces` | equal |
  | `dt_s` | `dt` | equal where `dt` is a number; where it is a list (W4), W4's three entries hold its members |
  | `observation_times_s`, `horizon_s` | `observation_times`, `horizon` | equal, where the references hold them |
  | `wash.time_s`, `node`, `fraction`, `buffer_mM` | `wash.t`, `node`, `f`, `buffer` | equal, with the same buffer members |

  - Each entry is checked against its world's file, `reference_<world>.json`. W3p reads W3's file, and W4's three
    entries read W4's.
  - Not cross-checked: W3p's times and horizon, which are SPEC:182's; W1eq's start, which is null in the expected file
    and compared at run time (§3); and any other null of the expected file.
  - Not cross-checked either, since the references' echo has no key of the same meaning or the form of its value is
    not known here: `world`, `nodes[].registered`, the sets' `shared`, `owner` and `face`, `free_amounts[].declared`,
    `permeabilities`, `multipliers`, `charges` and `constants.RT_pJ_per_fmol`.

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

- **`R:<set>` of a one-population set** (W3's `B`, W7s's `matrix`) is the engine's own free sites for that population,
  as its state or readout gives them. The exporter never forms S − B. `free_sites` says which (§4) [item 6].
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
| `collected`, `supplied` | object, ligand → fmol: the amounts this event booked, from the engine's own record of the event, for every ligand of `inputs.ligands` [B2] |

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
| `before` | `{"amounts", "records"}`: the state passed to the map, read from it before the call, in a row's shapes (§5) |
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
  departure is a fault (§11.2). In binary64, 0.1/2 is the literal 0.05.
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
  `kind` and `book` (§14.1). A reviewer who is not the builder confirms it against `src/`, and the lead then hashes it.
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
    for what its patch changes [B5].
  - **P7** runs on W3p in its own process, against W3's rows at W3p's times [7b].
- **`plant.inputs_changed`** [B6].
  - It is empty, except where this file names it.
  - P2, if planted by declaration, lists exactly the two populations' `k_off`, `populations[id=matrix_L1].k_off` and
    `populations[id=matrix_L2].k_off`, each set to the other's registered value. The expected-inputs file holds the two
    values (§12.2).
  - Any other plant planted by declaration gets its list and values by a dated addendum before the judged run, taken
    from its mechanism's words alone (§14.1).
  - The judge checks each changed value. The lead hashes the patch files before the judged run.
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
- **Refusals** [P-c].
  - Only a refusal of kind `check` counts as the run's "own books or checks". The judge identifies it from `raised`
    and the book, which it maps itself from `raised` and `name` (§7). Where the plant's row names the check, the
    refusal must be that check: P3's the dissipation check (book `dissipation check`), P6's the energy ledger (book
    `energy ledger`), and P8's its own ledger (CRITERIA:123, 126, 128). P8's own ledger is the moiety ledger its patch
    changes, book `moiety ledger` [E12]. Such a refusal catches the plant on that run, whatever its entries.
  - A refusal of kind `stage`, `definition`, `domain` or `harness` never counts, and neither does a `check` refusal by
    another book than the one the plant's row names. Such a run is caught only if a criterion its row names fails on
    the entries formed before the refusal [P-a, P-c].
  - **P4** is caught only by `step_report.verdict` `"admitted"` [W14].
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

  A compartment SPEC §2 does not name keeps the engine world's own name (§4.1).
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
    If they do not hold, the builder stops: a new ID or an allowance is the user's choice (DECISIONS:4882-4883), and
    it would change the registration, not only this file.

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
| `jax_platforms` | string: the JAX platform setting of the run's process: `"cpu"` in every run [B5, E5] |
| `blas_threads` | integer |
| `machine` | string |
| `external_modules` | list of `{"name", "identity", "frozen"}`: each module installed from outside the checkout (AGENTS.md, D185): its import name, its identity computed at run time, and the path where the judged run freezes its files beside the snapshot; empty if there is none [W9] |

- **Run provenance** is the revision, the dirty diff and the frozen snapshot (AGENTS.md).
- **The judged run** comes from a clean snapshot of main (PROTOCOL:127-128).
  - Every run in the table has the same `engine_revision`, `snapshot` and `external_modules`, and `checkout_dirty`
    false.
  - Every run, honest and planted, uses the CPU backend in binary64: `jax_enable_x64` true and `jax_platforms` `"cpu"`
    [B5]. A departure is a fault (§11.2).
  - The lead records the revision and the backend with the runs' inputs before the run (§4) [B5].
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
| C10 | every honest run's `status` and `refusal`, but W5's; in a completed run, also `checks` and the check modes in `definition` [B3, 7d] |
| Every run's identity | every value §11.1 lists [S13] |

- **Which pairs hold what** [E14]. As the census shows, the file holds C3a's B_H as its tolerance, C4a's N_l and C5's
  S_s as their values, and C8's `scale` and `minimum` (item 3). So §11's rows name only what the judge reads from the
  table.
- **C8** [item 3]. The judge forms e(dt) = max |y_e − y_ref|/S over R and the B_b at W4's times, from the engine's
  rows, the file's values and its `scale`. It judges the finest dt's pairs against their tolerance and the two ratios
  against the file's `minimum`. No k enters.
- **C10** [B3, 7d]. A completed honest run meets "completes" when its `status` is `"completed"`, it holds every
  registered row, and its `checks` and `definition` meet §4's rule. A refused honest run fails C10, W5's apart (C7).

### 11.1 Every value this file fixes [S13]

The judge checks each of these in every run. A departure is a fault (§11.2).
1. **The top level:** `kind`, `protocol` and `units` exactly (§2, §9); `runs` and `missing` hold §3's names, disjoint.
2. **The run:** `world` and `plant.id` as the run's name gives them (§3); `plant` null exactly in the honest runs;
   `status` `"completed"` exactly when `refusal` is null; `dt_s` §3's dt; `steps` as §4 defines it; `backend` the
   lead's record [B5].
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
10. **`inputs`:** the echo of §4.1 [S5].
11. **`source`:** every key present, of its type; `engine_revision`, `snapshot` and `external_modules` the same in every
    run; `checkout_dirty` false; `jax_enable_x64` true; `jax_platforms` `"cpu"` [B5, W9].
12. **`record_sha256`:** 64 hex digits.

### 11.2 Faults, and how they are scored [§1, item 4]

- **A fault** is any departure from a type, value or equality this file fixes (§11.1), including a missing, extra or
  duplicated row, event, map entry or keyed member [item 4, B2, S13].
- **Which entries a fault touches.** A fault touches every entry that reads the faulty key (§11's table, §8.1's). A fault
  of the run's identity (§11.1, items 2, 3, 4, 9, 10 and 11) means the run is not the registered world, so it touches
  every entry of the run [E8].
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
  - `step_report.step` 1 and `limit` 0.5;
  - the registered `permeabilities` 0.0, `multipliers` 1.0 and `charges` 0.

  Every other number in it is invented and meaningless, including its N_f, T and traces. The step counts of its
  invented runs (`rows[].step`, `steps`, `after_step`, `state_step`, `refusal.step`, a failure's `step`) count those
  runs' steps and are not input values.
- **What it covers:**
  - a completed run of each shape a registered world has: a node-owned set with two ligands; a start read from a file;
    a wash, with its event and its map on the wash row (W2's shape), and on the start and the wash row (W7's), in both
    variants; a cell inside a patch, with a set on its inside face (W3's) and one on a patch's outside face (W6's);
    one world at three steps; a one-population set; W7s's absent ligand held at its trace;
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
  sample's invented worlds, and the lead compares it with the recorded sample, key by key and type by type. A
  difference goes to this file's author before the judged run, never after.
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
    reads it at run time (§3; item 2), W6's unregistered cell, and RT. `multipliers` holds the one value every member
    must have;
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
  5. the runs, each registered world's first;
  6. the table's sha256 (§1), and then the judgement.
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

### 14.1 What may still change after the binding tag [Who c]

**The addenda this file calls for** ("Who c"'s first kind). Each is dated, disclosed and hashed by the lead, and made
before any run of a registered world:
1. the refusal mapping, from the engine's exceptions and check names to `kind` and `book`, confirmed against `src/` by
   a reviewer who is not the builder (§7) [B4];
2. the list of ledgers and host checks, each with where `definition` records its mode (§4) [B3, E3];
3. the backend every run uses (§4) [B5];
4. the changed inputs of any plant planted by declaration other than P2 (§8.1) [B6];
5. any compartment beyond W6's cell (§4.1), and any operator the host tissue requires (§9) [item 7, S7].

**The erratum** ("Who c"'s second kind): an erratum where a judge must change (D371).

**Not among them.** Two provisions of this file would act after the tag, but neither is of the two kinds as listed: a
unit conversion (§1) and a new model ID (§9). Each needs the lead's ruling, and a new ID changes the registration itself
(Q6d).

**Records, not changes.** Before the judged run the lead also records the runs' inputs, revision and backend (§4,
§10), and hashes the plants' patch files (§8.1).

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
  - [E1] The driver never builds a world from the expected-inputs file (the header).
  - [E2] A value that is not finite is written as `null`, which the judge reads as such (§1).
  - [E3] `checks` is `{"failures": [...]}` per listed check; the judge also checks the raising mode that `definition`
    records, at a place the addendum names (§4).
  - [E4] `raised` is null only in a `harness` refusal that no exception ended; `book` is null for every kind but
    `check` (§7).
  - [E5] B5's "CPU backend" is recorded as `source.jax_platforms` `"cpu"`, beside `jax_enable_x64` true, and the
    lead's recorded `backend` (`"numpy"` or `"compiled"`) is the one every run uses (§4, §10).
  - [E6] Key paths for a list without `id` name the member by its matching keys (§8.1).
  - [E7] W2's L2 is declared: SPEC gives its amount, which equals its trace (§4.1).
  - [E8] A fault of the run's identity touches every entry of the run (§11.2).
  - [E9] `permeabilities` are in the engine's own unit; `multipliers` are keyed by `of` and the engine's `name`, so
    the expected-inputs file gives only their value (§4.1).
  - [E10] The format sample's path, names, extra key and allowed constants, and what its structure-only pass checks
    (§12.1).
  - [E11] The cross-check's key map, and what it leaves out (§4.1).
  - [E12] P8's own ledger is the moiety ledger, book `moiety ledger` (§8.2).
  - [E13] S8's "every S the judge uses comes from `capacities`" is read with rows 5b and item 3: a pair that holds its
    own value or `scale` (C5's S_s, C8's S) is judged with the file's (§4).
  - [E14] W6 is applied under item 3: since the file holds C3a's B_H, C4a's N_l and C5's S_s, §11's rows name only what
    the judge reads from the table (§11).
