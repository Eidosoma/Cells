# BIO-001: experimental benchmark curation

2026-09-09, D042 / R007. **Specification and provisional dataset completed;
biological validation not performed.**

## Delivered

- [Benchmark specification](../docs/BIOLOGICAL_BENCHMARK_001.md): scope,
  retrospective fitting/evaluation boundary, model compatibility, numerical and
  biological acceptance distinctions, and the next descriptive calculation.
- [Dataset card and files](../data/biology/bonzanni2020_rptec_v1/README.md):
  Bonzanni et al. 2020 RPTEC/TERT1 conditions, original licensed Figures 2/3,
  source hashes/locators, coarse voltage readings and explicit unknowns.
- [Offline checker](../scripts/check_biological_benchmark.py) and
  [15 tests](../tests/unit/test_biological_benchmark.py): schema/value witnesses,
  recipe arithmetic, source-asset identity, units, split and exclusion retention,
  uncertainty claims, and rejection of premature result claims.
- Updated project priority, task board, scientific basis, architecture notes,
  experiment programme, roadmap and decision D042. Existing dirty-worktree
  changes and historical research artifacts were preserved.

## Scientific and data-quality findings

The [selected paper](https://doi.org/10.1242/bio.048553) provides a direct
electrical endpoint series and cell/experiment counts. Only C1-C3 have mutually
consistent Figure 2A/2B recipes. C4/C5 report potassium concentrations differing
by 10 mM between panels; both values remain in the dataset and neither condition
is fit or scored. These exclusions precede any Cells fitting and are not based
on model performance.

The three retained approximate voltages are -39, -24 and -18 mV, read visually
to the nearest 1 mV. The +/-2 mV reading bound is curator-assigned, not biological
uncertainty. Published SEM values are not transcribed and raw experiment-level
records are not retained. Consequently no quantitative biological pass/fail
threshold or prediction confidence interval is justified yet. The split is
C1/C2 fitting, C3 retrospective evaluation; it is not blinded.

This is a zero-applied-current whole-cell recording, with a pipette boundary
and unestablished culture connectivity. The surrounding solution includes Ca
and Mg. The current Na/K/Cl-only model's bath charge check would reject the
unchanged three-ion projection: the missing positive charge is 5.6 mM equivalents.
Changing the measured chloride would conceal the problem. A future explicit
background-ion/measurement-boundary contract is necessary before claiming
production correspondence.

The [Costa oocyte lead](https://pmc.ncbi.nlm.nih.gov/articles/PMC1189096/)
remains useful, but its primary abstract identifies non-equilibrium chloride
and proposes inward uphill transport. Our current isolated cell has only
passive chloride transfer. A future stationary-homeostasis comparison must
address that model gap. Original scanned methods/tables were not fully reviewed;
no oocyte parameter preset or BETSE reproduction was produced.

## Verification actually run

```bash
.venv/bin/python scripts/check_biological_benchmark.py
.venv/bin/python -m pytest -q -W error tests/unit/test_biological_benchmark.py
.venv/bin/ruff check scripts/check_biological_benchmark.py tests/unit/test_biological_benchmark.py
.venv/bin/ruff format --check scripts/check_biological_benchmark.py tests/unit/test_biological_benchmark.py
```

The checker passes for two source figures, five input conditions and three
approximate endpoints. It reports C4/C5 charge discrepancies of +10 mM
equivalents, with C1-C3 discrepancies zero when divalent ions are counted.
The current dataset remains `biological_acceptance: not_assessable`;
`model_fit` and `numerical_simulation` are both `not_run`.

All **15 targeted tests pass** (initial run: 0.08 s); lint and formatting pass.
These are curation-contract tests, not additional experiments or an independent
validation of manual digitization. All **39 production source files** have
identical before/after SHA-256 hashes; package/dependency files were not edited.
The previous 2,178-test full regression was not rerun for this data/docs slice
and is not relabeled as a current full-suite result.
Documentation checks cover 10 affected Markdown files and 552 local links,
with no missing targets or unclosed code fences. Scoped whitespace checks pass.

No production model, numerical solver, source equation, archived acceptance
report, E02 budget, GPU environment or continuing exploration was changed.
No fitting, optimization benchmark, long simulation, or external message was run.

## Next step

BIO-002: specify the conditioned electrical-response approximation and compute
a small descriptive C1/C2-only comparator with a C3 prediction, explicit reading
uncertainty and a no-response baseline. Do not identify individual mechanisms
from two fit points or present that comparator as a validated free cell.
Recover/review measurement uncertainty and boundary assumptions before any
quantitative biological acceptance or production-model extension.
Long E02 qualification stays unfinished/deferred, with its gates unchanged.
