# Synthetic arms folder

Written by `tools/make_run_fixture.py` for `tests/adapt_run.test.mjs`. It has the layout of the
turnover pre-screen's evidence folder (`arms/<arm>`), but every number is invented: no engine
ran, and nothing here is evidence. Do not edit by hand; change the tool and run it again.

- An arm is one run: it has no seed, its plan names no group, and nothing records a class.
- `synthetic-iso-s1.0` ran to its planned end; its newcomers arrive with no donor.
- `synthetic-donor-s1.0` records a refusal at 31 s and keeps its records to 30 s.
- `synthetic-iso-s1.0.killed` has no outcome, as a killed process leaves a folder.
