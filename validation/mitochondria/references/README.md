# Beard 2005 mitochondrion: independent reference (R1)

An independent reference for the isolated cardiac mitochondrion of Beard 2005, as
corrected in 2006. It is R1 in `docs/MITOCHONDRIA_DESIGN.md` §5.3 (D193 (A), D210).
It holds the model as data, a stiff integrator, an exact steady-state solve, the paper's
published results, and a thermodynamic audit. It was built before any engine code for
mitochondria existed.

**Independence.** This code was written from the two papers alone. No engine code was read
(`src/`), no engine test, no CellML or SBML file, and no author code. Its inputs were:
- both papers, read from PLOS. Every equation and both Table 1s were read from the PDF, the
  version of record, as typeset images. The XML supplied the text.
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
`digitize.py` read them at run time from PLOS, or from a local download kept outside the
repository. Only bare numbers are committed, each with its citation (D227).

## Files

| File | What it holds |
| --- | --- |
| `beard2005_model.json` | The model as data. It has 17 states, 21 fluxes and Eq. 22 as an exact stoichiometry. All 35 Table 1 parameters carry their printed 2005 and 2006 strings, units, class, equations and sensitivity. It also holds the text's standard energies, the protocols, and every disagreement Q01–Q28, each with its resolution and, where it matters, a switch. |
| `model.py` | A checked expression compiler (float, and 50-digit `decimal`). It finds Eq. 22's invariants as an exact left null space. It runs Radau integration, and a `decimal` Newton steady state with the invariants imposed. |
| `reproduce.py` | The published protocols: [Pi]e sweeps at [ADP]e 0 and 1.3 mM, both models, and the low-oxygen numbers. Arms are named switches. |
| `audit.py` | Each process's Gibbs energy from the paper's own standard energies; the zero, sign and form checks; dissipation, charge and proton bookkeeping at the reported states. |
| `digitize.py`, `published_targets.json` | The published model curves of Figs. 2–5, read from the article's rasters with pixel uncertainties, and the text's numbers. |
| `sources.py` | Table 1, re-read from both XMLs: all 140 cells match the model file. |
| `proposal.json` | Proposed comparison rows, bands and plants for a first engine milestone. It is a proposal, not a registration. |

Tests: `tests/unit/test_mito_references_integrity.py` (fast, about 2 s) and
`tests/unit/test_mito_references_reproduction.py` (heavier; tier 3 by measurement).

## Running

```
PY=/mnt/workspaces/Cells/venv-cpu/bin/python
$PY -m validation.mitochondria.references.sources --local <download dir> --out <workspace dir>
$PY -m validation.mitochondria.references.digitize <article PDF> --out <workspace json>
$PY -m validation.mitochondria.references.reproduce --arms all --out <workspace dir>
$PY -m validation.mitochondria.references.audit --repro <that dir> --out <workspace json>
```
