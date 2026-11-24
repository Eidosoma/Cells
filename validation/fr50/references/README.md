# FR-50: the code-blind reference of `fr50-one-way-records-v1`

This package is an independent reference for FR-50's registered protocol. It gives the absolute
one-way fluxes and their cumulative records for each declared case:
- the kinds' passive routes and an ATP-driven transporter;
- @3's membrane route, a junction, an uncharged face, and a blocked channel population.

It was written from `spec/` alone. No engine code, engine test or engine output was read, and
nothing here imports `cells`. `spec/` is a byte-identical copy of the tag
`fr50-one-way-records-v1-registered-2026-11-23`. The readings the spec needed are in `NOTES.md`.

## Files

| Path | What it is |
| --- | --- |
| `spec/` | The inputs: `README.md`, `LAWS.md`, `cases.json` |
| `fr50_spec.py` | Parses `cases.json`, keeping every number as its declared string. A case's kind is its id's first part |
| `fr50_route_a.py` | Route A: LAWS.md's forms in decimal arithmetic at 120 digits. The reported values are route A's |
| `fr50_route_b.py` | Route B: exact rationals with their own exp and ln; Ussing's ratio and the net |
| `fr50_ode.py` | K2's Radau integration (SciPy), the README's ODE cross-check |
| `fr50_reference.py` | The generator and writer: the routes, their comparison, the JSON files, the provenance |
| `test_fr50_reference.py` | The self-check, about 2 s, with no engine import and no world |
| `results/<case id>.json` | One file per registered case (10) |
| `format-sample/` | `invented_cases.json`, invented inputs with one case of each kind, and the writer's output on them (`INVENTED_<case>.json`), in the results layout |
| `NOTES.md` | The readings of the spec, and the check of its declared values |

## Running

Use the checkout's CPU environment, one thread, on a light core:

    export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
    PY=/mnt/workspaces/Cells/venv-cpu/bin/python
    taskset -c 6 $PY validation/fr50/references/fr50_reference.py                  # results/
    taskset -c 6 $PY validation/fr50/references/fr50_reference.py --format-sample  # format-sample/
    taskset -c 6 $PY validation/fr50/references/fr50_reference.py --out DIR        # a regeneration
    taskset -c 6 $PY validation/fr50/references/fr50_reference.py --spec FILE --out DIR
    taskset -c 6 $PY -m pytest -q -p no:cacheprovider validation/fr50/references/test_fr50_reference.py

- All ten cases take about 4 s.
- Writing `results/` or `format-sample/` is refused while the checkout has dirty paths other than
  the files the writer produces. Any other `--out` must lie outside the repository.
- A spec file with `"invented": true` must name its cases `INVENTED_<kind>_...`, and each output
  says `"inputs": {"invented": true, ...}`.

## What each file holds

Every file has:
- `kind`, `protocol`, `case_id`, `case_kind`;
- `inputs`: `invented` (false for the registered cases), the spec file, and a statement;
- `declared`: the case's entry, as declared;
- `forward_direction`;
- the requested quantities, by kind (below);
- `checks`, `method`, and `provenance` (the git revision, the dirty paths, and the Python, NumPy,
  SciPy and libmpdec versions).

| Kind | Quantities |
| --- | --- |
| Steady routes (K1, E1, E2, E3, E4) | `forward_fmol_per_s`, `backward_fmol_per_s`, `net_fmol_per_s`, `prefactor_pL_per_s`, `record_times_s`, `F_fmol`, `B_fmol`; for E1 and E4 also `E_K_V` and `V_V`; for E4 also `u` |
| K4 | `dG_cyc_over_RT`, `S`, `J_plus_fmol_cycles_per_s`, `J_minus_fmol_cycles_per_s`, `net_fmol_cycles_per_s`, `record_times_s`, `F_fmol_cycles`, `B_fmol_cycles` |
| K4h | `dG_cyc_over_RT`, `S`, `J_plus_fmol_cycles_per_s`, `J_minus_fmol_cycles_per_s`, `J_minus_over_J_plus` |
| K2 | `a_pL_per_s`, `k_per_s`, `c_bar_mM`, `record_times_s`, `c_cell_mM`, `c_node_mM`, `F_fmol`, `B_fmol` |
| K3 | `evaluations`: per voltage, `V_V`, the two fluxes, `ratio_inward_over_outward` and `ratio_backward_over_forward` |
| E6 | `E_K_V`; `evaluations`: per availability and voltage, `V_V`, `availability`, `V_ref_V`, `u`, the two fluxes, both ratios, and `difference_forward_minus_backward_fmol_per_s` |

Computed values have 30 significant digits, written as `d.ddd…e±N` and rounded half-even. An
exact zero is written `"0"`. Times, voltages and V_ref are exact decimal strings.

## The routes

**Route A**, the reported values, uses LAWS.md's forms in decimal arithmetic at 120 digits:
- the table of §2, with B(x) = x/(e^x − 1);
- the transporter of §3, with ΔG_cyc/(R T) as the sum the law writes;
- u by §4;
- K2 by §5's closed form;
- each steady record as its flux times t.

**Route B** shares only the parsed declarations with route A. It works in exact rationals, with
its own binary exp and ln, results rounded to 640 bits.
- Each flux is recomputed from Ussing's ratio and the net, as the README asks:
  - the net comes from the one-exponential GHK form;
  - ρ = backward/forward comes from Ussing's ratio;
  - forward = net/(1 − ρ).
- Exactly at zero net (ρ = 1: K1, E2, E3 and K4), that recomputation is 0/0. The one-way fluxes
  then come from their direct forms in exact rationals, and ρ = 1 and the net = 0 are reported in
  `checks`.
- At E1's and E4's voltage, E_K rounded to 50 digits, the net is about 1e-50 of each flux, so the
  recomputation is well defined there.

**K2** also has Radau at rtol 1e-12 (the README's ODE check, held to 1e-10). Route B gives it the
Taylor series of the linear system's matrix exponential.

**The declared accuracy** is 1e-20 relative for the closed forms and 1e-10 for the integration.
Each file's `within_declared_accuracy` tests every route difference, and the reported strings'
rounding, against these.

## Reproducing

- Every output was generated at the clean commit recorded in its `provenance.git_revision`. Its
  `dirty_paths` was empty, leaving out only this writer's own outputs.
- The reported values come from decimal arithmetic, and Radau enters only K2's method block, at
  one thread.
- So a run at that commit reproduces every file bitwise, under any `PYTHONHASHSEED` and on any core.
  The regeneration check ran at the generating commit.
