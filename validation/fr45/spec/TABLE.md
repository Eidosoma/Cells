# FR-45's engine table: the contract

**Dated 26 November 2026,** before the binding tag and before any engine run of a registered world. The registration
never defines the engine's table, so the lead ruled that a dated contract fixes it before the binding tag, from the
spec's text (the lead's first rulings, Q5: `/mnt/workspaces/Cells/fr45-readings-20261126/RULINGS-1-2026-11-26.md`).

- **What it binds.** The exporter, which writes the table from the engine's runs, and the judge
  (`validation/fr45/judge.py`), which reads it. Both are the build's (PROTOCOL:129; AMENDMENT-1:103).
- **Its sources.** The protocol and the six spec files at `fr45-site-competition-v1-amendment-3-2026-11-24`, the
  references' notes at `fr45-references-v2-2026-11-24`, and the key names (never the values) of the references'
  outputs. Line numbers cite those files as this branch holds them: PROTOCOL is `docs/FR45_SITE_COMPETITION_PROTOCOL.md`,
  AMENDMENT-1 is `AMENDMENT-2026-11-24.md`, AMENDMENT-2 is `AMENDMENT-2-2026-11-24.md`, and NOTES is
  `validation/fr45/references/NOTES.md`.
- **It fixes formats, not tests.** No criterion, band, class, world, input, plant or scoring rule changes. Where the
  text is silent on a format, the contract takes the reading that cannot make a pass easier and marks it **(silent: the
  stricter reading)**. §13 settles the reader's readings 8, 9, 10 and 13 this way.
- **What each side reads.**
  - The exporter reads SPEC.md's inputs, and W1eq's start from the references' file (§3).
  - The judge reads this file, the table, the references' files and their G function (CRITERIA:76; NOTES:178-186),
    and `agreement.py` (CRITERIA:29).
  - A key the judge needs that is not here is asked for through the lead and added by a dated change to this file,
    never taken from the other side's code. Extra keys are allowed and ignored, except in `inputs` (§4.1).

## 1. Files and number form

- **The table** is `table/table.json`, one file for the judged run, with `table/SHA256SUMS` (one line: the sha256, two
  spaces, `table.json`).
  - The lead records its sha256 before the judge opens it.
  - The judge does not read a table whose sha256 departs from that line or from the lead's record, or equals the format
    sample's (§12). It reports such a table to the lead.
- **The exporter forms nothing.** Every number is the engine's own. It is read from the engine's saved state, books,
  records or step report, or returned by the engine's own functions (the wash's event map, `quantities`) called on a
  saved state.
  - No difference, sum, ratio, recomputed quantity, tolerance or verdict is written. The judge forms those.
- **Strict JSON** (RFC 8259): no NaN or infinity, and no key twice in one object.
  - Floats are written in Python's `repr` form, so each parses to the engine's binary64 value, the sign of zero
    included. "Bit for bit" (CRITERIA:61, 82) compares the 64-bit patterns.
  - An integer is a JSON integer. A float with no fraction is accepted where an integer is asked, a string never.
- **Order is not a contract,** except in `rows` (step order) and `operators` (declared order). Runs are matched by name.
- **`null`** stands only where this file allows it.

## 2. The top level: every key required

| Key | Type |
| --- | --- |
| `kind` | the string `fr45 site-competition engine table, version 1` |
| `protocol` | the string `fr45-site-competition-v1` (PROTOCOL:5) |
| `runs` | object: run name (§3) to its entry (§4) |
| `missing` | list of run names (§3) for which no run record was found |
| `units` | object, exactly §9's |

A name is in `runs` or in `missing`, never both. A run named in neither is missing. How a missing run is scored is the
lead's (the reader's reading 11).

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

The criteria each run serves are the registration's (PROTOCOL:105-116; CRITERIA:72-86, 119-129). This table only names
the runs.

- **The honest `W1p` and `W3p` runs are asked for** (silent: the stricter reading).
  - The protocol gives W1p only the plants (PROTOCOL:109), and W3p has no reference file (SPEC:182). C5 and C10 name
    every world and every run (CRITERIA:81, 86).
  - Whether a criterion judges these two runs is the reader's reading 7, the lead's. The contract only makes them exist,
    so either ruling can be applied.
- **W1eq's start** is written by the references from W1's root (SPEC:123-126, 279). So the driver reads it at run time
  from the tagged `validation/fr45/references/outputs/reference_W1eq.json`:
  - each population's `world.populations[].initial_occupancy`, matched by `id`;
  - each free amount's `world.free_amounts[].n`, matched by `ligand` and `node`.

  Everything else is W1's (SPEC:130-132). The run's `inputs` echo the start, and the judge compares the echo with the
  file bit for bit.
- **P5's runs** are full planted runs of W2 and W7. C4a reads their rows (NOTES:103-104), and C6 their own `event_map`
  (§6).

## 4. A run's entry: one shape for every run

Every entry holds every key below, for honest, plant and refused runs alike.

| Key | Type and meaning |
| --- | --- |
| `status` | `"completed"` or `"refused"` |
| `world` | string: the run's world (§3) |
| `plant` | null in an honest run; else `{"id", "patch", "change"}`: the plant (`P1` to `P9`), the scoped patch's path under `validation/` (CRITERIA:111-112), and one line naming what it changes |
| `dt_s` | number: the step the engine ran |
| `steps` | integer: the steps completed: the last row's `step`, or the steps before a refused one |
| `backend` | `"numpy"` or `"compiled"`: the backend the run's steps used |
| `rows` | list of rows (§5), in step order |
| `capacities` | object, set → fmol: each set's capacity S_s as the engine holds it (SPEC:48), one-population sets included |
| `events` | list of the run's events (§6); empty in a world without a wash |
| `event_map` | list of the wash's event map applied alone to saved states (§6); empty in a world without a wash |
| `step_report` | the engine's report of the first step (§7) in W5's two runs; null in every other run |
| `refusal` | null in a completed run; else `{"kind", "name", "message", "step", "time_s"}` (§7) |
| `checks` | the engine's own ledgers and host checks, as it reports them at the end of the run (recorded, never judged) |
| `operators` | list of strings: the model and operator IDs the run's definition declares, in declared order, in today's spellings (§9) |
| `inputs` | the world as the engine parsed it (§4.1) |
| `definition` | the engine's own declaration of the world, as run (recorded, never judged) |
| `source` | provenance (§10) |
| `record`, `record_sha256` | the run's own record file, by its path relative to `table/`, and its sha256 (64 hex digits); recorded, never judged |

- **A completed run** carries every registered row of its world (§5.1) and, in W2's and W7's runs, every event-map
  entry (§6).
- **A refused run** keeps the rows, events and event-map entries it has; any list may be short.
  - A run refused before its definition was parsed holds null in `inputs`, `definition` and `checks`, an empty
    `operators` and `capacities`, and no row.
  - Only such a run holds those nulls.

### 4.1 `inputs`

Read back from the definition the engine parsed and ran, never copied from SPEC.md. Exactly these keys:

| Key | Type |
| --- | --- |
| `world` | string |
| `constants` | `{"sites_per_fmol", "temperature_K", "RT_pJ_per_fmol"}`: N_f, T and RT as the engine uses them (SPEC:34-40) |
| `nodes` | list of `{"id", "kind", "volume_pL"}`; `kind` is `"node"` or `"cell"` |
| `patches` | list of `{"id", "inside", "outside"}` (W3, W3p, W6); empty in the others |
| `ligands` | list of strings |
| `free_amounts` | list of `{"ligand", "node", "n_fmol", "declared"}`: every ligand at every node and cell, as the engine parsed it. `declared` is false for a trace (SPEC:104-106) |
| `sets` | list of `{"id", "shared", "owner", "face", "faces", "copies", "sites_per_copy", "accessible_fraction"}`, described below |
| `populations` | list of `{"id", "set", "ligand", "k_on", "k_off", "initial_occupancy"}` |
| `wash` | null, or `{"time_s", "node", "fraction", "buffer_mM"}`, with `buffer_mM` an object ligand → mM (W2 and W7: SPEC:152, 225) |
| `dt_s`, `observation_times_s`, `horizon_s` | number, list of numbers, number |

- **A set's keys:**
  - `shared` is false for a one-population set, which is its population's own sites (SPEC:53; PROTOCOL:55).
  - `owner` is a node or a patch. `face` is `"inside"` or `"outside"` for a patch's set, and null for a node's.
  - `faces` is the facing node or cell (SPEC:55-58).
- **W6's patch** `specimen_face` needs a cell inside it, which SPEC does not name (SPEC:210). It is `specimen`, as in W3
  (SPEC:178), and holds only traces.
- **The judge compares `inputs` with the registered inputs** of SPEC §2 bit for bit: "Every number below is a binary64
  literal as written" (SPEC:104).
  - An extra, missing or different key or value means the run is not the registered world.
  - `constants.sites_per_fmol` and `temperature_K` are compared exactly (SPEC:35, 38). `RT_pJ_per_fmol` is recorded,
    since SPEC gives RT as a formula, not a literal (SPEC:36-39).
  - A trace (`declared` false) is information.

## 5. The rows

A row is the engine's saved state after `step` steps. Row 0 is the start, before any step (SPEC:251-254). The saved
rows are the start and every observation time (AMENDMENT-1:41-43), and in W5, which has none, the horizon.

| Key | Type and meaning |
| --- | --- |
| `step` | integer: the steps completed, 0 at the start |
| `time_s` | number: the engine's own clock at the row |
| `amounts` | object, observable → fmol: `n:<ligand>@<node>` for every ligand of `inputs.ligands` at every node and cell, `R:<set>` for every set and `B:<population>` for every population (SPEC:368-369). An amount the reference's trajectory leaves out, because no law moves it, is information (AMENDMENT-1:23-29) |
| `records` | object, `<ligand>@<node>` → `{"collected", "supplied"}` in fmol: the wash's own records for every ligand at the washed node, as the engine holds them at the row (zero before the event). Empty in a world without a wash |
| `site_heat_pJ` | object, facing node → pJ: the engine's cumulative site heat at that node since t = 0 (§5.2) |
| `site_occupied_fraction` | object, population → number: the engine's `quantities` on this row's state (§5.3) |

- **`R:<set>` of a one-population set** (W3's `B`, W7s's `matrix`) is the engine's own free sites for that population,
  as its state or readout gives them. The exporter never forms S − B.
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
- **The row's clock is checked.** Its `time_s` equals t within 10⁻¹²·t, and is 0.0 at step 0.
  - A clock summed step by step stays within about 4·10⁻¹³·t over these runs. Neighbouring rows are at least dt apart.
    So this tolerance admits the clock's rounding and no other row.
  - A row whose clock departs is not the registered row.
- **Why this is the stricter reading.** The compared values are the state after k steps under either reading.
  - Matching by step, with the clock checked, pairs no row that matching by time could not, and it also refuses a clock
    that has left the grid.
  - Matching by exact equality of clock and t would refuse a summed clock's rows for their rounding alone. That would be
    a format fault, not a test.
- **Every registered row, and no other.** A completed run holds exactly its world's rows. A refused run holds those
  saved before its refusal.
- **The wash rows.** W2's row at 4.0 s (step 320) and W7's at 1.0 s (step 400) hold the state the wash acts on
  (SPEC:158-159, 233-234).
  - The wash is applied after that row is saved, at the start of the next step.
  - The next row is the first after it.
- **The tolerances are not changed here.** How they take k_t (CRITERIA:47) and C3b's k is the lead's (§14).

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

### 5.3 `site_occupied_fraction` (reading 13)

- **It is the engine's R3 quantity of that name** (CRITERIA:85), as the engine's `quantities` returns it.
  - The exporter calls `quantities` in the run's own process, with the run's backend, on the row's saved state: the
    state whose `amounts` the row holds.
  - It is the quantity that `cells.operator.species_regulated_availability@2` reads (PROTOCOL:34, 50, 141).
- **It is never a value kept from inside a step,** since a step's stages are not the saved state.
- **It is never formed by the exporter** from the row's amounts (reading 13; silent: the stricter reading). B_b/S_s
  formed so would make C9 compare that ratio with itself. It would also hide P9, which changes the engine's quantity
  (CRITERIA:129).
- **Every row of every run carries it,** W1p's included: P9 is caught on W1p by C9 (CRITERIA:129).
- **The judge forms the rest.** C9's B_b/S_s and its moiety term |R_s + ΣB − S_s|/S_s come from the same row's
  `amounts` and the run's `capacities` (AMENDMENT-1:54-55).

## 6. The wash: its event, and its map alone

**`events`,** in W2's and W7's runs and their plant runs: one entry per event the engine applied.

| Key | Type and meaning |
| --- | --- |
| `kind` | `"wash"` |
| `operator` | `cells.operator.scheduled_compartment_wash@1` |
| `node` | string: the washed node |
| `after_step` | integer: the steps completed when it was applied: 320 in W2, 400 in W7 (§5.1) |
| `time_s` | number: the engine's clock when it was applied |
| `collected`, `supplied` | object, ligand → fmol: the amounts this event booked, from the engine's own record of the event |

- C4c reads `collected` and `supplied` (CRITERIA:80).
- `time_s` equals the wash's time within 10⁻¹²·t, as a row's clock does (§5.1).
- An event at another step than §5.1's means the run is not the registered world.

**`event_map`,** in the same runs: the wash's event map applied alone to saved states (CRITERIA:79, 82; PROTOCOL:44;
DECISIONS:10367-10368).

| Key | Type and meaning |
| --- | --- |
| `state_step` | integer: the row whose saved state the map is applied to: 320 in W2; 0 and 400 in W7 |
| `variant` | `"numpy"` or `"compiled"`: the engine's NumPy implementation of the map, or its compiled one |
| `node`, `fraction`, `buffer_mM` | the map's parameters as the engine passed them; they equal `inputs.wash` |
| `before` | `{"amounts", "records"}`: the state passed to the map, read from it before the call, in a row's shapes (§5) |
| `after` | `{"amounts", "records"}`: the state the map returns, in the same shapes |

- **A completed W2 run holds two entries** (step 320, each variant). **A completed W7 run holds four** (steps 0 and
  400, each variant).
  - Both variants are separate entries, and neither is optional.
  - How a missing variant is scored is the reader's reading 4, the lead's.
- **The map acts on the run's own saved state.** `before` equals that row's `amounts` and `records` bit for bit. A
  departure means the map was not applied to the saved state.
- **No saved row is compared across the wash** (CRITERIA:82).
  - C6 compares every `R:` and `B:` of `after` with `before`.
  - C4b compares `after`'s free amounts and records with SPEC:96-100's map.
  - The judge forms the event's records as `after` less `before`. `before` holds zero records in every registered state.
- **P5's runs** hold the planted map's entries in the same shape, on their own saved states (§8).

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
- **C7 reads the report so** (reading 10; silent: the stricter reading). The honest W5 run is refused by the stage
  condition at its first step:
  - `status` is `"refused"`, `refusal.kind` is `"stage"`, `refusal.step` is 1, and no row follows the start;
  - its `step_report` has `verdict` `"refused"`, and its own `h_max_load` exceeds `limit`.

  A refusal of another kind, at another step, or without the report does not meet "Refused by the stage condition: the
  engine's step report gives h·max L above 1/2" (CRITERIA:83). W5's refusal can come only from the stage condition
  (PROTOCOL:166-167).
- **P4's run reads from the same key.** "The plant admits the step" (CRITERIA:124) is its `verdict` `"admitted"`.
- **`loads`, `sums` and `max_load` name the limiting load.** They are recorded. Whether the judge checks them is the
  lead's.

**`status` and `refusal`.** A run completes, or the engine refuses it: "The run completes; the runner raises otherwise"
(CRITERIA:86).

| Key | Type and meaning |
| --- | --- |
| `kind` | one of the five kinds below, set by the exporter from what the engine raised. The exporter's README lists the mapping |
| `name` | string: the engine's name of the condition, ledger, check or rule that refused |
| `message` | string: the message as the engine raised it |
| `step` | integer: the step being taken, counted from 1; null at parse |
| `time_s` | number: that step's start on the engine's clock; null at parse |

**The kinds:**
- `stage`: the stage condition refused a step (SPEC:74-79; CRITERIA:83).
- `check`: one of the run's own books, ledgers or host checks failed at a row or a step. These are the moiety and energy
  ledgers, the dissipation check and the host checks (CRITERIA:86, 113-114, 123, 126, 128).
- `definition`: at parse, a declaration the engine could not read or does not support. Version 1's refusals by name are
  among them (PROTOCOL:52-56).
- `domain`: a value outside a declared domain, by name, at parse or at run time, such as initial occupancies over 1
  (PROTOCOL:57).
- `harness`: anything the engine did not raise: the driver, the exporter, memory, a crash, a time limit.

The kinds stay apart. A `harness` refusal is never a run's "own books or checks" (CRITERIA:113-114).

## 8. The plant runs

- **Each plant runs in its own process,** as a scoped patch under `validation/`, never in `src/`, on the plant's own
  world (CRITERIA:111-112).
  - Its entry has the honest shape, and its `plant` names the plant, the patch and what it changes.
  - Its `world`, `dt_s`, `inputs`, `operators` and `definition` equal those of its world's honest run.
- **What each plant's criterion reads** (CRITERIA:119-129):

| Plant | Run | Keys |
| --- | --- | --- |
| P1, P2 (C1) | `W1p-P1`, `W1p-P2` | `rows[].amounts` |
| P3 (C3b, or refused by the dissipation check); P6 (C3b, or refused by the energy ledger) | `W1p-P3`, `W1p-P6` | `rows[].site_heat_pJ` and `amounts`; `status` and `refusal` |
| P4 (C7) | `W5-P4` | `step_report` |
| P5 (C6, C4a) | `W2-P5`, `W7-P5` | `event_map` (C6); `rows[].amounts` and `records` (C4a); `status` and `refusal` |
| P7 (C5, C1) | `W3p-P7` | `rows[].amounts`; `capacities` |
| P8 (C10: refused by its own ledger) | `W1p-P8` | `status` and `refusal` |
| P9 (C9) | `W1p-P9` | `rows[].site_occupied_fraction` and `amounts`; `capacities` |

- **P5's patch changes the wash wherever the engine implements it:** its NumPy and compiled maps, and the run's own
  event. CRITERIA:125 names the wash's mechanism, not one of its forms.
  - P5's `event_map` is the planted map alone on the run's own saved states (step 320 in W2; 0 and 400 in W7), in each
    variant.
- **A plant's scoring** is CRITERIA:113-114, with the lead's ruling on reading 2. The contract adds nothing to it.

## 9. Units, names and IDs

- **`units`** is exactly `{"amount": "fmol", "volume": "pL", "concentration": "mM", "k_on": "per mM per s", "k_off":
  "per s", "time": "s", "heat": "pJ", "fraction": "1", "load": "per s", "copies": "copies"}` (SPEC:15-32;
  CRITERIA:31-35). A key's suffix (`_s`, `_pJ`, `_fmol`, `_mM`, `_pL`, `_K`) repeats its unit.
- **Names are the spec's** (SPEC §2), never the engine's indices:
  - the nodes `well` and `vat`, the cell `specimen` and the patch `specimen_face`;
  - the ligands `L1` to `L5`, and the sets and populations as SPEC.md names them.
- **Observables** are `n:<ligand>@<node>`, `R:<set>` and `B:<population>`, the reference's own names (SPEC:368-369). So a
  row's amounts at a node go to the references' G as they stand (NOTES:184). A pool or a record is `<ligand>@<node>`.
- **IDs are in today's spellings.** The registration's prose is read through the ID table (D345;
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

- **`operators`:**
  - It holds, in every run, `cells.model.resolved_pump_composite@1`, `cells.model.resolved_pump_tissue@3` and
    `cells.operator.site_occupancy@1`. In W2's and W7's runs it also holds
    `cells.operator.scheduled_compartment_wash@1` (PROTOCOL:23-24; CRITERIA:78-82 name the wash on W7 too).
  - It never holds `cells.operator.site_occupant_replacement@1` (PROTOCOL:33, 54).
  - If the widened model takes a new ID under D148 (DECISIONS:4882-4883), that ID enters here by a dated change.

## 10. Provenance

`source`, in every run. Every key is required, and none is null or an empty string.

| Key | Type |
| --- | --- |
| `engine_revision` | string: the 40-hex commit the run's snapshot was made from |
| `checkout_dirty` | boolean |
| `snapshot` | string: the frozen snapshot's path |
| `snapshot_patch_sha256` | string: 64 hex digits, the sha256 of the snapshot's dirty patch, an empty patch included |
| `python`, `numpy`, `scipy`, `jax`, `jaxlib` | strings: versions |
| `jax_enable_x64` | boolean |
| `blas_threads` | integer |
| `machine` | string |

- **Run provenance** is the revision, the dirty diff and the frozen snapshot (AGENTS.md).
- **The judged run** comes from a clean snapshot of main (PROTOCOL:127-128).
  - Every run in the table has the same `engine_revision` and `snapshot`, and `checkout_dirty` false.
  - The lead records that revision with the run's inputs before the run.
- **The references' files** that the driver reads (W1eq's start) and that the judge reads are the snapshot's.

## 11. What each criterion reads

The worlds and times are the registration's (CRITERIA:72-86; AMENDMENT-1 §3; AMENDMENT-2 §3). This table names the keys
only.

| Criterion | Keys |
| --- | --- |
| C1 | `rows[].amounts` at the observation times |
| C2a | the last row's `amounts` |
| C2b | W1eq's rows; W7's rows at steps 200 and 400; `inputs` |
| C3a, C3b | `rows[].site_heat_pJ` and `step`, with C3b's G called on `rows[].amounts` at both ends. Neither spans W2's steps 320 to 321 or W7's 400 to 401 |
| C3c | `rows[].site_heat_pJ` between every pair of consecutive rows, the wash's included |
| C4a | `rows[].amounts`, `records` and `step` |
| C4b | `event_map`, and the start row for the engine's anchor (AMENDMENT-1:55) |
| C4c | `events[].collected` and `supplied` |
| C5 | `rows[].amounts` (`R:`, `B:`) and `step`; `capacities` |
| C6 | `event_map[].before` and `after` (`R:`, `B:`) |
| C7 | `W5`'s `status`, `refusal` and `step_report`; `W5-P4`'s `step_report` |
| C8 | the three W4 runs' `rows[].amounts` (`R:`, `B:`); `capacities` |
| C9 | `rows[].site_occupied_fraction` and `amounts`; `capacities` |
| C10 | every run's `status` and `refusal` (`checks` is recorded) |
| Every run's identity | `inputs`, `operators`, `source`, `dt_s`, `steps`, `rows[].step` and `time_s`, `events[].after_step`, `event_map[].before` |

## 12. The format sample

- **What it is:** a table in this contract's shapes, on invented worlds. It holds none of SPEC.md's numbers, and every
  number in it is meaningless. It covers:
  - a completed run of each shape a registered world has: a node-owned set with two ligands; a start read from a file;
    a wash, with its event and its map on the start and on the wash row in both variants; a cell with both patch faces;
    one world at three steps; a one-population set;
  - W5's two shapes, refused by the stage condition and admitted;
  - a refused run of each kind, a plant run of each shape in §8, and a non-empty `missing`.

  Beside it, a README lists every key and type to the leaf.
- **Its hashes:** the lead records the sha256 of each of its files in a dated note in this folder, before the binding
  tag.
- **Who writes it before the tag** is the lead's to rule (§14). The registration orders the tag before the build
  (PROTOCOL:182-183), so the builder's exporter does not yet exist then.
- **The judge reads it** before the judged run, with the code that will read the table, in a structure-only mode: keys,
  nesting and types, no number.
  - It must find no fault, and it reports the entry kinds it found.
  - This sample is the engine table's. The references' `format_sample_INVENTED.json` is the file the judge reads first
    (PROTOCOL:129-130).
- **At the judged run's snapshot,** the builder's exporter writes a table on the sample's invented worlds. The lead
  compares it with the recorded sample, key by key and type by type. A difference goes to this file's author before the
  judged run, never after.
- **What may never be taken from it:** a number, a list length, an order of keys or entries, or an equality between its
  numbers. No tolerance, scale or verdict depends on it.

## 13. The readings settled here

These are the reader's readings 8, 9, 10 and 13 (`/mnt/workspaces/Cells/fr45-readings-20261126/sentences.md`), each
marked silent there. Each is settled as a format, and none changes a criterion.

| Reading | The contract's row | Kind | Lines it rests on |
| --- | --- | --- | --- |
| 8. Row matching: by step count or by time | By step. The row at a registered time is the row whose `step` is that time's integer in §5.1, and its clock must equal t within 10⁻¹²·t (§5.1) | silent: the stricter reading | CRITERIA:47; SPEC:104, 158-159, 233-234, 368, 380, 390; PROTOCOL:165; AMENDMENT-1:41-44 |
| 9. C3a's engine heat: a cumulative difference, or an interval heat | A cumulative difference. There is one record: each facing node's cumulative site heat at each row, booked by the engine's binding routes and never formed from states. C3a's and C3b's interval heat is its change between the interval's rows, and C3c reads the same record (§5.2) | silent: the stricter reading | CRITERIA:75-77; AMENDMENT-1:44-49, 94-98, 101-104; PROTOCOL:45-46, 87-88; SPEC:307-311 |
| 10. C7: what the refusal must name and report | Refusal kind `stage`, at step 1, with no row after the start, and the engine's own `step_report`: h, every load at the first stage, the largest, h·max L, the limit and the verdict. C7 reads `refusal` and the report's own `h_max_load` and `verdict`. P4 reads the same `verdict` (§7) | silent: the stricter reading | CRITERIA:83, 124; SPEC:74-79, 339-347, 385; PROTOCOL:113, 166-167; AMENDMENT-1:72 |
| 13. C9 "from the engine's quantities on the saved state" | The exporter calls the engine's `quantities` on each row's saved state in the run's process, and exports `site_occupied_fraction` per population: never a value from inside a step, and never B/S formed by the exporter. Every row of every run carries it (§5.3) | silent: the stricter reading | CRITERIA:85, 129; AMENDMENT-1:41-43, 54-55; PROTOCOL:34, 50, 141 |

## 14. Open for the lead

1. **Who writes the format sample** before the binding tag (§12).
2. **W1eq's start is W1's root,** a reference result, held in the references' file (SPEC:123-126, 279). The contract has
   only the judged run's driver read it. A builder that ran W1eq before then would see it, so the builder develops on
   the sample's invented worlds.
3. **How a tolerance takes k_t, and C3b its k:** the steps of §5.1, or the binary64 quotients t/dt and
   (t₂ − t₁)/dt (CRITERIA:47, 76).
   - For k_t they differ only at W7's 1.0025 s, by 6·10⁻¹⁴.
   - For C3b's k they differ by at most 3·10⁻¹⁴, and only on the two intervals beside each wash: W2's 4.0 to 4.0125 s
     and 4.0125 to 5.0 s, and W7's 1.0 to 1.0025 s and 1.0025 to 1.5 s.
4. **How a contract fault is scored.** A fault is a missing or mistyped key, a null where none is allowed, or a
   departure of the echo, a row's step or clock, the wash's step, the map's `before`, the operators or the provenance.
   - The stricter reading is that no criterion that reads the entry can pass.
   - It is best ruled before the binding tag, before any result is seen, together with reading 11 (a missing run) and
     reading 4 (a missing variant).
5. **Reading 7, and part of reading 2.** Reading 7 covers the honest W1p and W3p runs, and C10 on plant runs. Reading 2
   leaves open whether a plant run refused with `stage`, `definition` or `domain` counts as "refused by its own books or
   checks".
6. **A one-population set's free sites** (W3's `B`, W7s's `matrix`). If the engine holds them as S − B, C5 holds there
   by construction.

## 15. Disclosures

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
