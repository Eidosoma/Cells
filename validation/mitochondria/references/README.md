# Beard 2005 mitochondrion: independent reference (R1)

This is R1 of `docs/MITOCHONDRIA_DESIGN.md` §5.3 (D193 (A), D210): an independent reference
for the isolated cardiac mitochondrion of Beard 2005, as corrected in 2006. It was built
before any engine code for mitochondria existed.

**Independence.** The code was written from the two papers alone. No engine code (`src/`),
engine test, CellML or SBML file, or author code was read. Its inputs were:
- both papers, read from PLOS. Every equation and both Table 1s were read from the PDF, the
  version of record, as typeset; the XML supplied the text;
- `docs/MITOCHONDRIA_DESIGN.md`;
- decisions D193, D210 and D227;
- the 16 November legibility check, re-verified here.

Nothing imports `cells`. The code uses NumPy, SciPy and the standard library's `decimal`
and `fractions`.

## Sources (CC BY; numbers cited, nothing copied)

- **B05:** Beard DA (2005). A biophysical model of the mitochondrial respiratory system and
  oxidative phosphorylation. *PLoS Comput Biol* 1(4): e36. doi:10.1371/journal.pcbi.0010036.
  Creative Commons Attribution License, per the article's own statement.
- **B06:** Beard DA (2006). Correction. *PLoS Comput Biol* 2(1): e8.
  doi:10.1371/journal.pcbi.0020008. Creative Commons Attribution License. It replaces Table 1.

The papers' text, figures and tables are not in the repository. `sources.py` and
`digitize.py` read them at run time, from PLOS or from a local download kept outside the
repository. Only bare numbers are committed, each with its citation (D227).

## Files

| File | What it holds |
| --- | --- |
| `beard2005_model.json` | The model as data. It has 17 states, 21 fluxes and Eq. 22 as an exact stoichiometry. All 35 Table 1 parameters carry their printed 2005 and 2006 strings, units, class, equations and sensitivity. It also holds the text's standard energies, the protocols, and every disagreement (Q01–Q28), each with its resolution and, where it matters, a switch. |
| `model.py` | A checked expression compiler (float, and 50-digit `decimal`). It finds Eq. 22's invariants as an exact left null space. It runs Radau integration, and a `decimal` Newton steady state with the invariants imposed. |
| `reproduce.py` | The published protocols. Named arms each change one switch or input. It also holds an ADP-step time course. |
| `audit.py` | Each process's Gibbs energy from the paper's own standard energies; zero, sign and form checks; dissipation, charge and proton bookkeeping at the reported states. |
| `digitize.py`, `published_targets.json` | The published model curves of Figs. 2–5, read from the article's rasters with pixel uncertainties, and the text's numbers. `digitize.py --targets` regenerates the file. |
| `sources.py` | Table 1, re-read from both XMLs: all 140 cells match the model file. |
| `proposal.json` | Proposed comparison rows, bands and plants for a first engine milestone. It is a proposal, not a registration. |
| `xf1_scaling.py`, `xf1_scaling.json`, `xf1_scaling.md` | The F1F0 activity X_F1 scaled down (x1/30 to x1/9000) and up (x10, x100) on the published arm and on frame B with Eq. 24 restored. For each scale: fit, departures, and whether the steady state exists and is unique; also the largest scale-down within 10% of each arm's fit. |
| `repairs.py`, `repairs_table.json`, `repairs_table.md` | MR1's candidate repairs of Eqs. 1, 11, 16 and 24, set beside the engine appendix's. Each is checked for consistency in two frames, fitted to the published curves, and measured for its departure from the published arm. For the user's ruling; nothing is registered. |

Tests: `tests/unit/test_mito_references_integrity.py` (fast, about 2 s) and
`tests/unit/test_mito_references_reproduction.py` (heavier, about 75 s on a shared core;
its tier is set by measurement).

## Running

```
PY=/mnt/workspaces/Cells/venv-cpu/bin/python
$PY -m validation.mitochondria.references.sources --local <download dir> --out <workspace dir>
$PY -m validation.mitochondria.references.digitize <article PDF> --out <json> --targets <json>
$PY -m validation.mitochondria.references.reproduce --arms all --out <workspace dir>
$PY -m validation.mitochondria.references.audit --repro <that dir> --out <workspace json>
```
