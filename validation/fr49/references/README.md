# FR-49: the code-blind reference of `fr49-compartment-compositions-v1`

This package is an independent reference for FR-49's registered protocol. It covers:
- World L: a labelled pulse carried into a compartment and cleared there;
- World B: ligand binding with depletion in a compartment;
- C1: labels at a washed well;
- C2: two ligands sharing one site pool.

It was written from `spec/` alone. No engine code, engine test or engine output was read, and
nothing here imports `cells`. `spec/` is a byte-identical copy of the tag
`fr49-compartment-compositions-v1-registered-2026-11-23`. The readings the spec needed are in
`NOTES.md`.

## Files

| Path | What it is |
| --- | --- |
| `spec/` | The inputs: `README.md`, `LAWS.md`, `cases.json` |
| `fr49_spec.py` | Parses `cases.json`, keeping every number as its declared string |
| `fr49_exact.py` | The high-precision routes, in decimal arithmetic. The reported values come from here |
| `fr49_ode.py` | The ODE integrations (SciPy Radau and DOP853, binary64), the README's cross-checks |
| `fr49_reference.py` | The generator and writer: all routes, their comparison, the JSON files, the provenance |
| `test_fr49_reference.py` | The self-check, about 5 s, with no engine import and no world |
| `results/<world>.json` | `L.json`, `B.json`, `C1.json`, `C2.json` |
| `format-sample/` | `invented_cases.json`, invented inputs for all four worlds, and the writer's output on them (`INVENTED_<world>.json`), in the results layout |
| `NOTES.md` | The readings of the spec, and the check of its declared values |

## Running

Use the checkout's CPU environment, one thread, on a light core:

    export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
    PY=/mnt/workspaces/Cells/venv-cpu/bin/python
    taskset -c 6 $PY validation/fr49/references/fr49_reference.py                  # results/
    taskset -c 6 $PY validation/fr49/references/fr49_reference.py --format-sample  # format-sample/
    taskset -c 6 $PY validation/fr49/references/fr49_reference.py --out DIR        # a regeneration
    taskset -c 6 $PY validation/fr49/references/fr49_reference.py --spec FILE --out DIR
    taskset -c 6 $PY -m pytest -q -p no:cacheprovider validation/fr49/references/test_fr49_reference.py

- All four worlds take about 30 s on one core; most of it is C2's two Taylor integrations.
- Writing `results/` or `format-sample/` is refused while the checkout has dirty paths other than
  the files the writer produces. Any other `--out` must lie outside the repository.
- `--spec FILE` runs the writer on any spec file in `cases.json`'s schema.
  - A file with `"invented": true` gives `INVENTED_<world>.json`.
  - Each such file says `"inputs": {"invented": true, ...}`.

## What each file holds

Every file has:
- `kind`, `protocol`, `world`;
- `inputs`: `invented` (false for the registered worlds), the spec file, and a statement;
- `declared`: the world's declared values;
- `quantities`: each name's unit and definition;
- `sample_times_s`: exact decimal strings;
- the requested arrays over the sample times;
- `method`, then `provenance`: the git revision, the dirty paths, and the Python, NumPy, SciPy and
  libmpdec versions.

Each world adds the following.
- **`L.json`:**
  - the arrays `n_O`, `n_C`, `x_O`, `x_C`, `base_O` (n_O − x_O), `base_C`, and the shares
    `share_x_O` (x_O/n_O) and `share_x_C`.
- **`B.json`:**
  - the arrays `B`, `n_L`, `c`;
  - `once`: `S`, `K_d`, `b`, `c*`, `B*`, `B1`, `B2`, `lambda`, `L_T`, `d`, with their units in
    `once_units`;
  - `root_branch`, and `checks`.
- **`C1.json`:**
  - `well`: x_W, b_W and n_W just before and just after the wash, and the shares x/n and b/n there;
  - World L's arrays, identical to `L.json`'s.
- **`C2.json`:**
  - the arrays `B1`, `B2`, `c1`, `c2`, `R`;
  - `once`: `c1*`, `c2*`, `B1*`, `B2*`, `R*`, `S`, `K_1`, `K_2`;
  - `checks.end_approaches_root`.

Every value has 30 significant digits, written as `d.ddd…e±N` and rounded half-even. An exact zero is
written `"0"`.

## The routes

| World | Reported route (high precision) | Second routes |
| --- | --- | --- |
| L | The augmented system's matrix exponential on each interval, by Taylor series with scaling and squaring, at 70 digits | The eigen closed form (Sylvester's formula) at 70 digits; Radau at rtol 1e-13 with its steps stopped at t₁ and t₂ |
| B | LAWS.md §3's closed forms at 60 digits | A Taylor-series integration at 50 digits; Radau at rtol 1e-12; each `once` value by a second route (S, K_d, L_T and b in exact rationals, then B₁,₂ = (s ∓ d)/2, λ = k_on d/V_C); B* from c* against B₁ from the quadratic |
| C1 | LAWS.md §4's arithmetic at 60 digits | The same in exact rationals |
| C2 | Transient: a Taylor-series integration at 50 digits, step 0.1 s. Root: one equation in R, by Newton at 70 digits | Radau at rtol 1e-12 and DOP853 at rtol 1e-13; the integrator at step 0.05 s; Newton on LAWS.md §5's two equations |

- The ODE routes use atol 1e-30, so their error control is relative in every component.
- C2's ODE routes integrate the free sites R as a state of their own.
- Every check route forms its own S and L_T from the declared values; none takes them from the
  reported route.
- World L's Radau is held to World L's declared 1e-13, the stricter of that and the ODE bound.

**The declared accuracy** (spec README) is:
- 1e-20 relative for the 30-digit quantities;
- 1e-10 for the ODE integrations;
- 1e-13 for World L's matrix exponentials.

Each file's `method` gives every route's largest difference against its bound. Its
`within_declared_accuracy` is the conjunction of those tests, and of the reported strings' own
rounding.

## Reproducing

- Every output was generated at the clean commit recorded in its `provenance.git_revision`. Its
  `dirty_paths` was empty, leaving out only this writer's own outputs.
- The reported values come from decimal arithmetic. The ODE routes enter only the method's
  differences, and are deterministic at one thread.
- So a run at that commit reproduces every file bitwise, under any `PYTHONHASHSEED` and on any core.
  The regeneration check ran at the generating commit.
