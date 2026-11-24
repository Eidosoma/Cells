# FR-45's code-blind references: notes

The references for `fr45-site-competition-v1`, built from the registered spec alone:
`validation/fr45/spec/SPEC.md`, `CRITERIA.md`, `AMENDMENT-2026-11-24.md` and
`NOTE-2026-11-24.md`. No engine code, test, output or other `validation/` code was read, and no
engine module is imported. The spec copy a run reads is checked against its sums file at run
time.

## What the package computes

| Quantity | Method that writes the value | Second method |
| --- | --- | --- |
| R-eq, the finite-volume equilibrium (SPEC §3.1) | an isotone Kleene enclosure from R = 0 and R = S | damped Newton; for a set with two ligands alone, Wang's trigonometric root (derived here, branch chosen by check) |
| R-ode, the trajectories (§3.2) | Taylor series in decimal at 70 digits (order 40, local tolerance 1e-58 of each amount's scale), rounded once | DOP853 in binary64 at rtol 1e-12 and 1e-13 (the `tolerance_gap`), restarted at each observation time |
| R-dG, G, heats, B_H (§3.3) | SPEC §1.3's G in decimal on method B's states | the same G on method A's states |
| W4's closed form | the 2×2 matrix exponential in decimal | R-ode, which carries the depletion |
| W5's loads and verdicts (§3.6) | exact rationals | plain binary64 |
| The plants (§3.5) | planted runs or planted accounting on method B | the same on method A |

Quantities that are exact functions of the binary64 inputs (the anchors, the C1, C2a and C5
tolerances, the supplied amounts, W5's loads) are computed with `Fraction` and rounded once. A
C5 tolerance that is a genuine binary64 tie showed why. Method A's inputs (its start, its atol
scales and the wash map) are exact in the same way, so method A does not depend on the decimal
precision.

## The rulings applied

- **AMENDMENT §1, the 13 answers:**
  1. The package is here and the outputs are under `outputs/`.
  2. `value` is the Taylor solution rounded once. `tolerance_gap` is |DOP853(1e-12) − DOP853(1e-13)|. The requirement that the Taylor value lie within `tolerance_gap` + 1e-12 of the pair's scale of DOP853(1e-13) is checked at every trajectory value and heat, and recorded in `accuracy.json`.
  3. Only amounts a law moves appear (`fr45ref_model.System`).
  4. s_node is taken over the trajectory amounts.
  5. E is the sum of the term magnitudes.
  6. B_H is applied literally.
  7. C4a, C5 and C9 include the start row. The heat intervals start at 0. C3c covers the wash's interval, with its E taken over the post-wash state and the next row; C3a and C3b leave that interval out.
  8. C2b's `x_root` is W1's root.
  9. C9's and C4b's state-dependent tolerances are written as `tolerance_terms`: the terms the inputs fix, plus R-ode's state terms marked `_information`.
  10. W1p and W4 carry `equilibrium` and `distance_at_horizon` as information. W5's sections are null or empty.
  11. The pairs follow §3's table (`fr45ref_writer.CRITERIA`).
  12. The JSON shapes are as registered.
  13. Plant distances for non-numeric bounds are as accepted.
- **AMENDMENT §2.1:** C3a, C3b and C3c are judged in W1, W2, W3 and W6. W1p carries C3b only for P3 and P6.
- **AMENDMENT §2.2:**
  - C3b's −ΔG uses `fr45ref_free_energy.G`, the one function exposed for the judge.
  - P3's and P6's distances under C3a stay in the file, marked `information: true`.
- **NOTE-2026-11-24:** C4b and C6 act on the 4.0 s row, the state the wash acts on (`W2_WASH_ALONE_TIME`). P5's C6 sizing uses the same state.

## Precision

The working precision is 70 digits. The first, 50-digit profile is kept as `--profile
reference50`. At 50 and 70 digits the written values of the eight files are bitwise identical,
apart from two kinds of entry:
- the seven Wang gaps, which measure the two routes' disagreement at the working precision and
  so shrink with it by construction;
- W1eq's three near-zero heats, which 50 digits resolve to 13 to 16 significant digits and 70
  digits to at least 30.

The regeneration check reruns this comparison and records it in `outputs/regeneration.json`
under `precision_50_vs_70_digits`.

## The judge's free energy

```python
import sys; sys.path.insert(0, "validation/fr45/references")
from fr45ref_free_energy import G
heat = float(G("W2", "well", amounts_start) - G("W2", "well", amounts_end))
```

`amounts` holds every amount at the node, named as in the trajectory. The result is a decimal
at 70 digits.

## How to run

All runs use the venv's Python with BLAS pinned to one thread. `<copy>` is the spec copy's
directory, which holds `validation/fr45/spec/` and its sums file.

```sh
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
# the reference files, from a clean checkout (it refuses a dirty one)
PYTHONHASHSEED=0 taskset -c 6 python validation/fr45/references/run_references.py \
    --spec-root <copy>/spec --spec-sums <copy>/SHA256SUMS-...txt --spec-label <label> --out <new dir>
# the bitwise regeneration: seeds 0, 1 and 2 on two CPUs, the format sample, and 50 against 70 digits
python validation/fr45/references/regeneration_check.py --spec-root <copy>/spec \
    --spec-sums <copy>/SHA256SUMS-...txt --spec-label <label> --root <new dir> --cpus 6,7
# the self-check: a few seconds, no engine import; it rewrites the format sample byte for byte
python -m pytest validation/fr45/references/test_references.py -q
```

- The file format is described in `fr45ref_writer.py`'s docstring.
- `format_sample_INVENTED.json` shows every section on invented inputs.
- `outputs/` holds the eight reference files, `accuracy.json` (each quantity's two methods,
  normalised as CRITERIA.md normalises), `regeneration.json` and the generating run's
  `run.log`. The log holds the seed, the CPU and timings, so it is not part of the bitwise
  comparison.
