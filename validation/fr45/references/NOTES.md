# FR-45's code-blind references: notes

These are the references for `fr45-site-competition-v1`, built from the registered spec alone:
`validation/fr45/spec/SPEC.md`, `CRITERIA.md`, `AMENDMENT-2026-11-24.md`,
`NOTE-2026-11-24.md` and `AMENDMENT-2-2026-11-24.md`, with
`docs/FR45_SITE_COMPETITION_PROTOCOL.md`, at the amendment-2 tag (ff99fead).
- No engine code, test, output or other `validation/` code was read.
- No engine module is imported.
- The spec copy a run reads is checked against its sums file at run time.

## What the package computes

| Quantity | Method that writes the value | Second method |
| --- | --- | --- |
| R-eq, the finite-volume equilibrium (SPEC §3.1) | an isotone Kleene enclosure from R = 0 and R = S | damped Newton. For a set with two ligands alone, also Wang's trigonometric root (derived here, branch chosen by check). Where every population on a lone set shares one K·V (W7, whose two K are 12 mM, and W7s), also the pooled quadratic |
| θ by the user's formula (§3.1, amendment 2) | (c_b/K_b)/(1 + Σ_j c_j/K_j) from the root's free concentrations, beside B_b/S_s from the root | the formula from Newton's root; the gap at the written binary64 values |
| R-ode, the trajectories (§3.2) | Taylor series in decimal at 70 digits (order 40, local tolerance 1e-58 of each amount's scale), rounded once | DOP853 in binary64 at rtol 1e-12 and 1e-13 (the `tolerance_gap`), restarted at each observation time |
| R-dG, G, heats, B_H (§3.3) | SPEC §1.3's G in decimal on method B's states | the same G on method A's states |
| W4's closed form | the 2×2 matrix exponential in decimal | R-ode, which carries the depletion |
| W5's loads and verdicts (§3.6) | exact rationals | plain binary64 |
| W7's start as SPEC.md states it | plain binary64 on the declared start | exact rationals |
| The plants (§3.5) | planted runs or planted accounting on method B | the same on method A |

**Exact inputs.** Quantities that are exact functions of the binary64 inputs are computed with
`Fraction` and rounded once:
- the anchors;
- the C1, C2a and C5 tolerances;
- the supplied amounts;
- W5's loads.

A C5 tolerance that is a genuine binary64 tie showed why. Method A's inputs (its start, its atol
scales and the wash map) are exact in the same way, so method A does not depend on the decimal
precision.

## The rulings applied

**AMENDMENT-2026-11-24 §1, the 13 answers:**
1. The package is here and the outputs are under `outputs/`.
2. `value` and the convergence requirement:
   - `value` is the Taylor solution rounded once.
   - `tolerance_gap` is |DOP853(1e-12) − DOP853(1e-13)|.
   - The Taylor value must lie within `tolerance_gap` + 1e-12 of the pair's scale of
     DOP853(1e-13). This is checked at every trajectory value and heat, and recorded in
     `accuracy.json`.
3. Only amounts a law moves appear (`fr45ref_model.System`).
4. s_node is taken over the trajectory amounts.
5. E is the sum of the term magnitudes.
6. B_H is applied literally.
7. The rows and intervals:
   - C4a, C5 and C9 include the start row.
   - The heat intervals start at 0.
   - C3c covers the wash's interval, with its E taken over the post-wash state and the next row.
   - C3a and C3b leave that interval out.
8. C2b's `x_root` is W1's root.
9. C9's and C4b's state-dependent tolerances are written as `tolerance_terms`: the terms the
   inputs fix, plus R-ode's state terms marked `_information`.
10. W1p and W4 carry `equilibrium` and `distance_at_horizon` as information. W5's sections are
    null or empty.
11. The pairs follow §3's table (`fr45ref_writer.CRITERIA`).
12. The JSON shapes are as registered.
13. Plant distances for non-numeric bounds are as accepted.

**AMENDMENT §2.1:** C3a, C3b and C3c are judged in W1, W2, W3 and W6. W1p carries C3b only, for
P3 and P6.

**AMENDMENT §2.2:**
- C3b's −ΔG uses `fr45ref_free_energy.G`, the one function exposed for the judge.
- P3's and P6's distances under C3a stay in the file, marked `information: true`.

**NOTE-2026-11-24:** C4b and C6 act on the 4.0 s row, the state the wash acts on
(`W2_WASH_ALONE_TIME`). P5's C6 sizing uses the same state.

**AMENDMENT-2-2026-11-24, the user's acceptance targets:**
- **The two worlds.** W7 and W7s are transcribed from SPEC.md §2 and row-checked against it.
  - The check includes the facts SPEC.md states about W7's start: S = 6.0 fmol; B = 2.0 and
    1.0 fmol and R = 3.0 fmol; both K 12 mM, with detailed balance at the start; both net fluxes
    0.0 in binary64; and the map on the start removing 4.0 and 2.0 fmol and supplying 4.0 fmol
    of L2.
  - `fr45ref_build.stated_start_checks` tests each fact on the declared start and stops the run
    if one fails. They hold (`accuracy.json`, W7's `start`).
  - W7s has one ligand: L2 is absent.
- **R-eq's totals.**
  - W7's are the post-wash totals: R-ode's state at 1.0 s through the map. Wang's root applies.
  - W7s's are the start's.
  - Both also have the pooled quadratic, so each has three routes.
- **C2b on W7.**
  - It covers W7's rows before its wash, 0.5 and 1.0 s (`W7_C2B_TIMES`).
  - It compares them with "its start, its own root": R-eq at W7's start's totals, solved like
    every other root.
  - That root must round to the declared start, or the run stops. It does, so C2b's `value` is
    the example.
  - R-ode's rows at 0.5 and 1.0 s round to the example as well (information in `accuracy.json`).
- **θ.**
  - W7's and W7s's `equilibrium.theta` holds {population: {formula, root, gap}} at R-eq's root.
  - The two agree to the working precision. The format sample carries θ too.
- **C4b and C6** act on W7's start (0.0 s, the example as declared) and on its 1.0 s wash row
  (`W7_WASH_ALONE_TIMES`). The format sample carries that shape.
- **P5 on W7 is sized under C6 and C4a**, by the coordinator's ruling of 24 November 2026:
  - **Why:** CRITERIA.md's plant row, as amendment 2 amended it, names C6 and C4a for W2 and
    W7. It governs over the narrower per-world table in amendment 2's §3, which names C6 only.
  - **The record:** the coordinator records the ruling, citing both passages, in the decision
    log.
  - **The entries:** C6 has one entry per state (0.0 and 1.0 s), so a tie between the states
    cannot hide one. C4a comes from a full planted W7 run, as in W2.
- **The pairs and the judge's G.** The pairs follow amendment 2's §3 table. `fr45ref_free_energy.G`
  covers W7 and W7s.
- **W1 to W6 are unchanged.** Regenerated under amendment 2, the eight earlier files are
  byte-identical to the tag `fr45-references-2026-11-24`'s, apart from `provenance`.
  - Their entries in `accuracy.json` are identical too, except for two added records for W2:
    each ligand's books across the wash, and a second route for P5's C6 sizing.
  - The writer is version 2, and the schema string is unchanged.

## W7s's late heats lie below the working precision

W7s's horizon is 280 time constants of its slowest mode (23.3 /s). The protocol sizes every
horizon to reach at least e^-30 of its slowest mode, and W7s reaches e^-280. So its heats from
3 s on are far below what 70-digit G values (about 30 pJ) resolve, which is about 1e-68 pJ.

The exact sizes below are estimates. W7s relaxes along one reaction coordinate, so near its
root a heat decays as e^(-2·23.3 t). The table calibrates that decay on the 2 to 3 s heat,
which is resolved to about 26 digits; the same calibration gives the 3 to 5 s heat as 2.0e-62.

| Interval | Exact size (estimated) | Written |
| --- | --- | --- |
| 3 to 5 s | about 2e-62 pJ | to about 7 significant digits |
| 5 to 8 s | about 6e-103 pJ | ±1e-68 pJ, one unit in G's last digit |
| 8 to 12 s | about 1e-163 pJ | ±1e-68 pJ; one of the two late heats is negative |

- `accuracy.json` lists these intervals under W7s's `heats_below_binary64_resolution`.
- **The distance at the horizon** is written as about 7e-62 fmol. That is the integrator's
  floor; the exact solution's distance is near 1e-122 fmol.
- **No criterion can see either.** Each is more than 50 orders of magnitude below its band:
  - C3a's B_H is 7.4e-4 pJ in those intervals;
  - C2a's band is 8e-9 fmol.
- They are written as computed, not rounded. W7's heats, including its two near-zero ones before
  the wash, are resolved to more than 30 digits.

## Precision

The working precision is 70 digits. The first, 50-digit profile is kept as
`--profile reference50`.

At 50 and 70 digits the written values of the ten files are bitwise identical, apart from the
entries below, 42 in all. The regeneration check reruns this comparison and records it in
`outputs/regeneration.json` under `precision_50_vs_70_digits`.
- **The gaps between two routes that agree to the working precision.** They shrink with it by
  construction:
  - the eight Wang gaps: W1, W1eq, W1p, W2, W3's set C, W4, W6 and W7;
  - the three θ gaps: W7's two and W7s's one.
- **Near-zero heats, which 50 digits resolve to fewer digits than binary64 needs:**
  - W1eq's three;
  - W7's two before its wash, with their C3a values. W7's start is its own root to rounding;
  - W7s's four from 2 s on, with their C3a values.
- **Two distances at the horizon:**
  - W7's, at 52 time constants: 50 digits resolve its 3e-24 fmol to about 16 digits;
  - W7s's, below either profile's integrator floor.
- **W7's start-row entries that read the start in binary64:** C9's moiety term at 0.0 s and
  P5's C6 sizing at 0.0 s.
  - W7's start sits on binary64 ties. occupancy·S is 2 − 2^-53 and 1 − 2^-54 fmol exactly: the
    midpoints between binary64 neighbours, which round (ties to even) to the declared 2.0 and
    1.0 fmol.
  - 70 digits hold these 54-digit products exactly.
  - 50 digits cannot, and round B_L2 below its tie, to 1 − 2^-53.

## The judge's free energy

```python
import sys; sys.path.insert(0, "validation/fr45/references")
from fr45ref_free_energy import G
heat = float(G("W2", "well", amounts_start) - G("W2", "well", amounts_end))
```

- `amounts` holds every amount at the node, named as in the trajectory.
- The result is a decimal at 70 digits.
- Every world is known, W7 and W7s included.

## How to run

**Setup.** Every run uses the venv's Python with BLAS pinned to one thread. `<copy>` is the spec
copy's directory: it holds `validation/fr45/spec/`, the protocol under `docs/`, and their sums
file. The copy of amendment 2 is
`/mnt/workspaces/Cells/fr45-references-v2-20261124/spec`, with
`SHA256SUMS-fr45-spec-ff99fead.txt` beside it.

```sh
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
# the reference files, from a clean checkout (it refuses a dirty one)
PYTHONHASHSEED=0 taskset -c <cpu> python validation/fr45/references/run_references.py \
    --spec-root <copy>/spec --spec-sums <copy>/SHA256SUMS-...txt --spec-label <label> --out <new dir>
# the bitwise regeneration: seeds 0, 1 and 2, the format sample, and 50 against 70 digits
python validation/fr45/references/regeneration_check.py --spec-root <copy>/spec \
    --spec-sums <copy>/SHA256SUMS-...txt --spec-label <label> --root <new dir> --cpus <a>,<b>
# the self-check: about a second, no engine import; it rewrites the format sample byte for byte
python validation/fr45/references/test_references.py
```

- **CPUs.** The regeneration check's two CPUs may be one: each run writes its own numbered
  directory.
- **The file format** is described in `fr45ref_writer.py`'s docstring.
- **`format_sample_INVENTED.json`** shows every section on invented inputs, including θ and the
  event map alone on the start and on the wash row.
- **`outputs/`** holds:
  - the ten reference files;
  - `accuracy.json`: each quantity's two methods, normalised as CRITERIA.md normalises;
  - `regeneration.json`;
  - the generating run's `run.log`. The log holds the seed, the CPU and timings, so it is not
    part of the bitwise comparison.
