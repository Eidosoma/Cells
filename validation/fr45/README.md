# FR-45's tooling: driver, exporter, plants and judge

The tools that run FR-45's worlds through the engine (`cells.operator.site_occupancy@1`'s shared site sets, with
`cells.model.resolved_pump_composite@1`, `cells.model.resolved_pump_tissue@3` and, in W2 and W7,
`cells.operator.scheduled_compartment_wash@1`), write the engine table, and judge it. The contract is
`validation/fr45/spec/TABLE.md` at the binding tag; the criteria are its `CRITERIA.md`. The section numbers below
are TABLE's.

Until the lead schedules the execution record's parse-only passes, the tools run invented worlds only (run names
beginning `INVENTED-`); the driver refuses any other name unless the call is judged.

## Files

| File | What it does |
| --- | --- |
| `worlds.py` | Builds an engine definition from a run's `inputs` (§4.1): the registered node or cell, the bath form's host entities, the ligands at their traces, the site sets (shared sets as `site_sets`, a one-population set as its population's own sites), the binding multipliers and the wash. |
| `driver.py` | Runs one job in its own process: parses, runs in windows of one step (§7), saves the registered rows (§5.1), the wash's event and its map in both variants (§6), W5's step report (§7), and maps a refusal to its kind and book. Writes one run record. W1eq's start is read at run time from its reference file (§3). |
| `exporter.py` | Writes `table/table.json`, its `SHA256SUMS` and the run records (§1, §2). It forms nothing (§1). |
| `plants/p1.py` to `p9.py` | The nine plants (CRITERIA:119-129) as scoped patches, applied in the plant run's own process; P2 is planted by declaration (its `inputs_changed`, B6). |
| `plants/INVENTED_*.py` | Development-only plants on invented worlds: a P3 whose heat is booked negative (to exercise the dissipation check) and a P7 that also moves an ion (to exercise a host check). Never in a registered run. |
| `sample.py` | §12.3 step 5: the format sample's invented worlds through the driver and exporter, for the lead's comparison with the sample. |
| `judge.py` | The judge (below). One file, run by its path. |
| `rehearsal.py` | The dress rehearsal (below). Never in the judged run. |
| `d148_round.py` | The engine landing's D148 round (done). |

## The judge

`judge.py` imports the standard library, the registered `validation/assembly_lineages_v2/agreement.py` (loaded by
its path, after its blob is checked) and the references' G (`fr45ref_free_energy.G`, from the references' folder
on `sys.path`; its source is never read). It imports nothing from `src/` and nothing of the driver's, exporter's or
worlds'.

At the judged run, `judge` follows §12.3:

```
python -B validation/fr45/judge.py judge --table TABLE_DIR --references SNAPSHOT/validation/fr45/references \
    --expected SNAPSHOT/validation/fr45/spec/expected_inputs.json --out OUT --repo CHECKOUT --tag BINDING_TAG \
    --table-sha256 LEADS_RECORD --sample-sha256 SAMPLE_SHA256 \
    --addendum HOST_ADDENDUM --execution-record RECORD --checks-list CHECKS [--exclude PATH ...]
```

1. the reference files and `agreement.py` against the binding tag's blobs (S14); a departure stops it;
2. the structure-only pass over the reference files: each pair's form against the census's, its observable
   against its criterion's text, the constant words, the plant entries against the registration's (12b);
3. the expected-inputs file against the references' world echo, by §4.1's key map (S5); a departure stops it;
4. the table's sha256 against its `SHA256SUMS`, the lead's record and the sample's (§1); a departure stops it;
5. the judgement: every value §11.1 fixes, in every run, with each fault scoped as §11.2 says; every entry from the
   registration and the references' pairs (§11); each criterion's verdict; and each plant by §8.2. It writes
   `OUT/verdict.json`.

Steps 4 and 5 of §12.3 use the other commands: `structure` (the structure-only pass over a table), `compare` (a
table against the format sample, key by key and type by type) and `plant-rule` (each plant run against its honest
twin).

**The judge's readings**, where the contract leaves the form to the build:
- the refusal mapping (§7) is the judge's own, from `raised` and `name`: a check's name gives its book (`moiety
  ledger`, `energy ledger`, `dissipation check`, else `host check: <name>`), `stage condition` gives `stage`, the
  domain names give `domain`, and anything the engine did not raise is `harness`. The dated addendum fixes it
  before any registered run (§14.1 item 1);
- a refused W2 or W7 run whose refusal is at the step that applies the wash may hold the event or not (Y2's two
  exceptions cannot be told apart from the record alone); at any other step the count is §4's;
- an expected-inputs null is compared as a value, except `constants.RT_pJ_per_fmol` (recorded) and W1eq's start
  (compared with the references' file);
- C3a is inconclusive where the references' heat interval has a tolerance gap above 1e-10 of |G| at its two ends,
  a scale no larger than E; C4c's removed amount where the trajectory's gap at the wash's time is above 1e-10
  s_node; C8's ratios where any of W4's pairs is;
- C8's e(dt) is formed from every dt's pairs; the coarser dts' pairs (no tolerance) only feed it;
- the honest W1p's C1, C3b and C9 and W3p's C1 are the plants' baselines only, not entries of their criteria (§3).

**Owed before the judged run** (§14.1), and the judge's options that take them: the host-entity addendum
(`--addendum`; until then host volumes and `host_values` are listed as unchecked), the execution record
(`--execution-record`), the list of checks by world (`--checks-list`), the refusal mapping's addendum and the B6
paths. The verdict lists every check it could not make under `unchecked`.

## The dress rehearsal

`rehearsal.py` builds a NumPy and SciPy reference for the format sample's invented worlds, in the references'
format and the registered files' layout (W3p reads W3's file; a stand-in G module in the references' folder, ruling
6), runs the engine through the driver and exporter, and runs `judge.py judge` by its path on the result. The worlds
take the engine's constants and are re-timed to at most 6000 steps a run.

```
python -B -m validation.fr45.rehearsal SAMPLE_DIR OUT --cpus 6,7 [--stage runs|judge]
```

Run it from a frozen snapshot (`validation/source_snapshot.py`) of `src/cells`, `validation/fr45`,
`validation/tissue` and `agreement.py`, so that every run's provenance is one clean revision.

## Tests

`tests/unit/test_fr45_judge.py`: about 1 s, pure Python, no engine. `tests/unit/test_fr45_driver.py`: the seconds
its docstring states, an engine run per world in its own process.
