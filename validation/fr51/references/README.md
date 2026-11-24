# FR-51: the code-blind reference of `fr51-channel-block-v1`

This package is an independent reference for FR-51's registered protocol: a channel population's
constant-field (GHK) permeation and its weighted-mode open-channel block. It was written from
`spec/` alone. No engine code, engine test or engine output was read, and nothing here imports
`cells`. `spec/` is a byte-identical copy of the tag `fr51-channel-block-v1-registered-2026-11-23`.
The readings the spec needed are in `NOTES.md`.

## Files

| Path | What it is |
| --- | --- |
| `spec/` | The inputs: `README.md`, `LAWS.md`, `cases.json` |
| `fr51_spec.py` | Parses `cases.json`, keeping every number as its declared string |
| `fr51_route_a.py` | Route A: LAWS.md's closed forms in decimal arithmetic. The reported values are route A's |
| `fr51_route_b.py` | Route B: the second, independent route |
| `fr51_reference.py` | The generator and writer: both routes, their comparison, the JSON files, the provenance |
| `test_fr51_reference.py` | The self-check, about 5 s, with no engine import and no world |
| `results/<case id>.json` | One file per registered case |
| `format-sample/` | `invented_cases.json`, invented inputs, and the writer's output on them (`INVENTED_*.json`). The five invented cases show each layout of `results/`: free at unequal and at equal concentrations, a zero blocker with three modes, two modes under the reversal reference, and one mode with a units count |
| `NOTES.md` | The readings of ambiguous statements, and the check for inconsistent declared values |

## Running

Use the checkout's CPU environment, one thread, on a light core:

    export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
    PY=/mnt/workspaces/Cells/venv-cpu/bin/python
    taskset -c 6 $PY validation/fr51/references/fr51_reference.py                  # results/
    taskset -c 6 $PY validation/fr51/references/fr51_reference.py --format-sample  # format-sample/
    taskset -c 6 $PY validation/fr51/references/fr51_reference.py --out DIR        # a regeneration
    taskset -c 6 $PY validation/fr51/references/fr51_reference.py --spec FILE --out DIR
    taskset -c 6 $PY -m pytest -q -p no:cacheprovider validation/fr51/references/test_fr51_reference.py

- All 22 cases take about 1.5 minutes on one core, and the format sample about 10 s.
- Writing `results/` or `format-sample/` is refused while the checkout has dirty paths other than
  the files the writer produces. Any other `--out` must lie outside the repository.
- `--spec FILE` runs the writer on any spec file in `cases.json`'s schema, such as invented
  inputs. A file with `"invented": true` must name its cases `INVENTED_...`, and every output it
  gives says `"inputs": {"invented": true, ...}`.

## What each file holds

Each `results/<case id>.json`, and each format-sample file, has these fields:

- `kind`, `protocol`, `case_id`.
- `inputs`: `invented` (false for the registered cases, true for the format sample), the spec file,
  and a statement.
- `declared`: the case's declared values, with the abundance used and where it came from.
- `E_ion_V`: the case's Nernst potential, 50 significant digits.
- `u_at_reversal`: u at V = E_ion.
- `voltage_count`, `voltage_index` and `voltages_V`:
  - 364 voltages, as exact decimal strings;
  - the 361 grid voltages first, then E_ion, E_ion − 0.0005 and E_ion + 0.0005 at indices 361 to
    363.
- **The requested arrays over the voltages**, under the names in `cases.json`'s
  `requested_outputs` and in its units: `V_ref_V`, `J_free_fmol_s`, `I_free_A`, `dI_free_dV_S`,
  `theta_k`, `one_minus_theta_k`, `u`, `J_blocked_fmol_s`, `I_blocked_A`, `dI_blocked_dV_S`,
  `dJ_blocked_dc_o_fmol_s_per_mM` and `dJ_blocked_dc_i_fmol_s_per_mM`.
  - `theta_k[k][j]` is mode k, in declared order from 0, at voltage j.
  - A case without a block has the free arrays and `u`, exactly 1, only.
- `properties`: LAWS.md §2's two properties.
  - At reversal: the flux at E_ion against the largest flux, and its sign on either side.
  - For equal concentrations only: the line through zero.
- `method`: the two routes and their precision; the largest relative difference between them, for u
  and the currents and for the slopes, with the quantity and voltage of each maximum; the same
  measure for the reported strings; and `within_declared_accuracy`.
- `provenance`: the git revision, the dirty paths, the Python and libmpdec versions, and the
  generator.

Computed values have 30 significant digits, written as `d.ddd…e±N` and rounded half-even. A value
that is exactly 0 is written `"0"`.

## The two routes

**Route A** uses Python's `decimal` at 120 significant digits.
- It evaluates the forms LAWS.md writes:
  - J = 1e15 A P r a o v (c_i B(−x) − c_o B(x));
  - B′ for the slope;
  - each 1 − θ_k = K_k/(c_B + K_k) formed directly, and u = Σ w (1 − θ)/Σ w;
  - the analytic slopes of §4 and §5.
- Why 120 digits: E_ion carries 50 digits, so the flux at V = E_ion is at most about 2e-50 of its
  two terms. 120 digits leave about 70 correct digits there.

**Route B** shares only the parsed declarations with route A.
- It works in exact rationals, with its own binary exp and ln. Results are rounded to 640 bits
  (about 192 digits), and the `decimal` module is not used.
- Its algebra is the alternative one:
  - the classical one-exponential GHK form, with its own x = 0 limit;
  - K = exp(ln K(0) + a V_ref);
  - θ = 1/(1 + K/c_B);
  - u by the literal 1 − Σ w θ/Σ w.
- Every slope is a central difference of route B's own values. The step is 1e-50 V, or 1e-50 times
  the concentration, and E is recomputed from a perturbed concentration.

The generator requires both routes to give the same voltages and the same 50-digit E_ion. It
compares every other quantity at every voltage, in exact rational arithmetic. The declared accuracy
(spec README) is 1e-20 relative for u and the currents and 1e-15 for the slopes. Each file's
`within_declared_accuracy` tests the reported 30-digit strings against route B at those bounds.

## Reproducing

- Every output was generated at the clean commit recorded in its `provenance.git_revision`. Its
  `dirty_paths` was empty, leaving out only this writer's own outputs.
- No floating-point arithmetic, BLAS, set or hash ordering enters any value. So a run at that commit
  reproduces every file bitwise, under any `PYTHONHASHSEED` and on any core. The regeneration check
  ran at the generating commit.
- A run at a later commit differs only in `provenance.git_revision`.
