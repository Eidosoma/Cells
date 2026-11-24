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

## Notes

- 24 November 2026: a reader and mapping were written by the builder under the lead's mistaken
  brief (which combined the builder's and the judge's roles), retired unused, and never tagged.
