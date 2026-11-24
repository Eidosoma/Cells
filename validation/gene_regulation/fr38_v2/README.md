# FR-38's second registered comparison: the builder's tools

The registration is `docs/FR38_SECOND_COMPARISON_PROTOCOL.md` with the spec folder `spec/` (tag
`fr38-v2-spec-amendments-2026-11-24`: the criteria tag `fr38-v2-criteria-2026-11-24` with
amendments 1 and 2). The code-blind references are tagged `fr38-v2-references-2026-11-24` (D339).
Decisions: D334 (arms A and B decide FR-38's verdict; C and D carry their own) and D339.

The builder writes the worlds, `engine_run.py`'s exports for families C and D, the restart, the
plants' world data and host-side patches, and release_check's scoping (the protocol's §5). The
judge and the checker are other agents, with their own code.

| File | What it does |
| --- | --- |
| `worlds.py` | The engine's worlds from SPEC.md: AF, AN, C and D (`hold`) and B (`b`), each run's labelled form and unlabelled twin, the blanks, and the plants' world data (`PLANTS`). `check()` parses every registered definition with its initial values; nothing is compiled or run |
| `campaign.py` | The engine side's runs: one process per run, cold, from the registration's snapshot; the restart through snapshot files; P9's V0 patch; the launcher; and the table, which holds READOUTS.md §2's host-side quantities, the plants and the restart, built from the records alone and hashed |
| `smoke.py` | The end-to-end smoke on the references' invented inputs (no registered world). Its reading of the invented file is its own private helper |
| `../engine_run.py` | The exports, with family C's n_Mx and H_store, family D's V, H_water and W_bath, and G over their rows (current V in D, K and Y included) |
| `../release_check.py` | The net agreement of route 2's survival counts with the net reading, scoped to where e^(y_f) is small enough for its allowance (`net_scope`) |

## The builder's readings of SPEC.md

- **The blank.** H(0) = 0 and k_I = 0, every other input the p_sched run's. It is run once per
  machine option in AF, which CRITERIA.md §1 asks for, and once (returned) in AN, C and D. Each run
  takes the blank of its machine option where there is one, else the returned blank.
- **Run names.** The engine's runs carry SPEC.md §1.3's names. Blanks are named `blank <machine>`,
  and a twin is its labelled run's name plus ` unlabelled`.
- **The release** is marked at release ({"at": "release"}); P4 marks it at completion.
- **The labels.** R and R_s each carry `resyn`, `pool0`, `pre`, `win` and `post`, with `pool0` the
  cell's whole initial share. Each row's own schedule is `resyn` from 0. Transcription's source
  schedule sits on R, the chain's label source, and R_s shares its labels.
- **The degradations' cited standard free energy** is L mu°_M - mu°_fate in RT at 1 M in the hold
  worlds, which the registry checks against the potentials, and A1's cited value in B. No rate or
  booking reads it.
- **D.** Water is declared first. The held bath's K, Y and traces are all at 0.4 of §1.1's.
- **C.** The network is declared after the gene unit (FR-43 part 2A's order), and M and Mx carry
  the phosphorus and nucleoside moieties there.
- **The window policy:** 2400 steps for every run, so that the restart's join at 7200 s ends a
  window at h. The restart's record is the whole run's, from both parts.
- **The table's host-side quantities** (READOUTS.md §2):
  - the gross is (pre + win) + post;
  - route 2 is cohort.known_rate at the definition's k_f, with cohort.known_rate_error as g(ts);
  - the excess is the run's n minus its blank's at the same step;
  - route 1's survival is cohort.label_survival on the win class;
  - P1′'s planted route 2 is cohort.survivors, the net-rate form;
  - P6's planted G is G_minus_G0 less RT mu°_res L (H - H(0)).

## The engine's table (campaign.py `table`)

One JSON file per family, `table/table_<family>.json` (`table-retry/` for the retry), with their
sha256 in `table/SHA256SUMS`, built from the run records alone:
- `kind` (`cells.fr38_v2.engine_table@1`), `family`, `window_s`, `samples_s` and `missing` (the
  records not found).
- `rungs`, keyed by the step's `repr` (`"2.0"`, `"1.0"`, `"0.5"`). Each holds `dt_s` and `runs`,
  keyed by the engine's run names (README above). A run is either a refusal (`refused`,
  `refusal`, `definition`) or:
  - `t`, its output times;
  - `readouts`: READOUTS.md §1's series by name, with `released_present_gross_<fate>` added in
    labelled runs, and engine_run's other exports (`H_route_*`, `int_D_route_*`, `H_total`,
    `H_routes_sum`, `n_tx_release_*`, `label_H_*`), which READOUTS.md §4 leaves uncompared;
  - `route2`: per fate and sample time, `value` (cohort.known_rate at `k_per_s`) and
    `grid_error`;
  - `survival` (labelled runs): per fate and later sample time, `alive_t2`, `alive_ts` and
    `ratio`, null at a zero count;
  - `excess_over_blank` (runs with a blank): per fate, one value per output, with `blank`, the
    matched blank's name;
  - `checks` (engine_run's), `own_ledgers_at_end`, `steps`, `dt_s`, `definition`, `source`, and
    `record` with its `record_sha256`.
- `restart` (AN): the resumed run's record in the same form, with the checkpoint's identity.
- `plants`: each world-data plant's record in the same form, with `judged_as`. Also P1′ (in AN:
  per labelled run, route 2 by the net-rate form, each entry's `value` and `grid_error`) and P6
  (in AF: the p_sched returned run's `G_minus_G0` without the hold's standard term).

## Notes

- **D's swelling** (the protocol's §4 asks the builder to confirm it), by LAWS.md §4's law with
  SPEC.md §1.6's inputs, as arithmetic with no engine run: the cell crosses 2 V0 at 1998.6 s,
  inside the window [1800, 5400) s. V is 1.952 pL at 1800 s, 2.398 pL at 5400 s and 2.554 pL at
  14,400 s, and its equilibrium, 2.5625 pL, is inside the 3.0 pL bound. The gene unit's own
  change to the cell's osmolytes is about 1e-7 fmol/s, which this leaves out.
- **G's identity with water closes at second order,** not at rounding: water's bookings are
  second order (FR-43's C2.7). On the smoke's invented swelling cell it is 2.64e-5 pJ at 0.5 s and
  6.59e-6 pJ at 0.25 s (observed order 2.003), 5.1e-8 of the bookings' magnitude. CRITERIA.md C4
  holds family D's identity to the rounding form. Family C's closes at rounding (1.4e-14 pJ).
- 24 November 2026: a reader and mapping were written by the builder under the lead's mistaken
  brief (which combined the builder's and the judge's roles), retired unused, and never tagged.
