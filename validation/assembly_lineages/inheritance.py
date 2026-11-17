"""Inheritance across fission boundaries, and the F12 break-and-renewal event (analysis).

Analysis, not engine physics (GARD_DESIGN §1.6 and §5.4; ORIGIN_OF_LIFE_ENGINE_DESIGN §5.1): it
reads a lineage's saved counts and fission table. The engine's own H (fission_similarity) is
floating point and diagnostic here; inheritance is decided from the integer counts.

Source: the Plastic Heredity preprint, v5.0 (Zenodo 10.5281/zenodo.22143269, CC BY 4.0), sections
"Compositional similarity and boundary inheritance" and "F12 break-and-renewal endpoint" (the
endpoint internally named JOINT_BREAK_RUN3), and Appendix F's restored-future rules, as read for
this module; numbers cited under D186. In the preprint's words:
- inheritance at a boundary is "strict similarity between the pre-fission parent and the selected
  daughter", I_t = 1{H(P_t, D_t) > 0.9}, so H = 0.9 is a break;
- F12 is: "within the next twelve fissions, observe an inheritance break and, strictly after that
  break, certify three consecutive inherited fissions", in plain language "break ... inherit,
  inherit, inherit" within the twelve-fission window; "a break without a later three-run, or a
  three-run without an earlier break, scored zero";
- in a restored future, "an event certified before later extinction remained positive, while
  extinction before certification was absorbing and negative. Extinction itself was neither a
  fission nor an inheritance break."

**Inheritance, decided exactly.** For count vectors P and D (non-negative integers, so P.D >= 0),
H > 9/10 exactly when 100 (P.D)**2 > 81 (P.P)(D.D). Python integers make that exact, so no rounding
moves a boundary at the threshold. A boundary whose selected daughter is empty is not a boundary:
the lineage is extinct there, and its sequence of marks ends.

**The F12 reading, with its choices declared as parameters** (the preprint's values the default):
- `window` = 12: the boundaries of the first twelve fissions after the state;
- `run` = 3: three consecutive inherited boundaries;
- `min_gap` = 0: boundaries strictly between the break and the run's first boundary. The run
  starts strictly after the break, so at gap 0 it starts at the very next boundary. The preprint's
  "break ... inherit, inherit, inherit" and "at least one break followed strictly later by three
  consecutive inherited fissions" set no gap, and between the two any boundary may stand, a break
  included (the last break before the run is then a qualifying break). This is the one reading
  this module had to choose: 0, not 1, because "strictly after" excludes only the break's own
  boundary, which cannot be inherited anyway;
- the whole run lies in the window: its last boundary is at most `window`;
- a shorter sequence (a future that went extinct first) is scored on what it has: positive if
  the event is certified within it.
`certified_at` is the boundary (1-based) that completes the first qualifying run, or 0.

**The table** over all 2**window sequences (4,096 for twelve): row i holds boundary j (1-based) in
bit (window - j) of i, so boundary 1 is the most significant bit. Row 0b011100000000 (1792) reads
"break, inherit, inherit, inherit", then eight breaks: certified at boundary 4. The sequences are
stored beside the verdicts, so no reader needs the bit order to check them. The predicate is not
symmetric under reversal: 0b111011011011 (a run, then breaks with no run after) is zero, and its
mirror 0b110110110111 is certified at boundary 12.
"""

import json
from pathlib import Path

import numpy as np

THRESHOLD = (9, 10)  # H > 9/10, strictly.
WINDOW, RUN, MIN_GAP = 12, 3, 0
SOURCE = {
    "source": "Plastic Heredity preprint v5.0, Zenodo 10.5281/zenodo.22143269",
    "place": "'Compositional similarity and boundary inheritance'; 'F12 break-and-renewal "
    "endpoint' (JOINT_BREAK_RUN3); Appendix F, restored futures and extinction",
    "licence": "CC BY 4.0; numbers cited under D186",
}
TABLE_FORMAT = "cells.assembly_lineages.f12_table@1"


def inherited(parent, daughter, threshold=THRESHOLD):
    """True if H(parent, daughter) > threshold, decided in exact integer arithmetic; None if
    either is empty (no boundary)."""
    p = [int(v) for v in np.asarray(parent).ravel()]
    d = [int(v) for v in np.asarray(daughter).ravel()]
    if len(p) != len(d) or any(v < 0 for v in p + d):
        raise ValueError("Counts are non-negative integers of one length")
    pp, dd = sum(v * v for v in p), sum(v * v for v in d)
    if pp == 0 or dd == 0:
        return None
    pd = sum(a * b for a, b in zip(p, d, strict=True))
    num, den = threshold
    return den * den * pd * pd > num * num * pp * dd


def marks(parents, daughters, threshold=THRESHOLD):
    """The lineage's inheritance marks (1 inherited, 0 a break), in order, ending at the first
    boundary with an empty selected daughter (extinction: neither a fission nor a break)."""
    out = []
    for p, d in zip(parents, daughters, strict=True):
        mark = inherited(p, d, threshold)
        if mark is None:
            break
        out.append(int(mark))
    return out


def lineage_marks(fission_split, fission_followed, parents):
    """Marks from a bundle's fission table: the selected daughter of fission k is the first
    daughter's counts (fission_split) or the parent less them, by fission_followed."""
    first = np.asarray(fission_split, dtype=np.int64)
    parents = np.asarray(parents, dtype=np.int64)
    followed = np.asarray(fission_followed)
    daughters = np.where(followed[:, None] == 0, first, parents - first)
    return marks(parents, daughters)


def certified_at(sequence, window=WINDOW, run=RUN, min_gap=MIN_GAP):
    """The boundary (1-based) completing the first run of `run` inherited boundaries that starts
    at least min_gap + 1 boundaries after a break, within the first `window` boundaries; 0 if
    none (the event is not certified)."""
    seq = [int(v) for v in list(sequence)[:window]]
    if any(v not in (0, 1) for v in seq):
        raise ValueError("Marks are 0 (a break) and 1 (inherited)")
    first_break = next((i for i, v in enumerate(seq) if v == 0), None)
    if first_break is None:
        return 0
    streak = 0
    for i in range(first_break + 1 + min_gap, len(seq)):
        streak = streak + 1 if seq[i] == 1 else 0
        if streak >= run:
            return i + 1
    return 0


def f12(sequence, window=WINDOW, run=RUN, min_gap=MIN_GAP):
    return certified_at(sequence, window, run, min_gap) > 0


def table(window=WINDOW, run=RUN, min_gap=MIN_GAP):
    """(sequences [2**window, window] int8, the event [2**window] bool, certified_at [2**window])
    over every complete sequence; boundary j (1-based) is bit (window - j) of the row index."""
    rows = np.arange(2**window, dtype=np.int64)
    shifts = np.arange(window - 1, -1, -1, dtype=np.int64)
    sequences = ((rows[:, None] >> shifts[None, :]) & 1).astype(np.int8)
    at = np.asarray([certified_at(s, window, run, min_gap) for s in sequences], dtype=np.int64)
    return sequences, at > 0, at


def parameters(window=WINDOW, run=RUN, min_gap=MIN_GAP, threshold=THRESHOLD):
    return {
        "window": window,
        "run": run,
        "min_gap": min_gap,
        "threshold": {"strictly_above": f"{threshold[0]}/{threshold[1]}"},
        "inheritance": "100 (P.D)^2 > 81 (P.P)(D.D) in exact integers (H > 9/10 strictly; "
        "H = 0.9 is a break); an empty selected daughter ends the sequence",
        "event": "a break, then strictly later (min_gap boundaries or more between) `run` "
        "consecutive inherited boundaries, all within the first `window` boundaries",
        "gap_reading": "the preprint sets no gap ('break ... inherit, inherit, inherit'), so "
        "min_gap = 0: the run may start at the boundary right after the break, and any "
        "boundaries may stand between",
        "short_sequences": "scored on their prefix: positive if certified within it",
        "source": SOURCE,
    }


def write_table(directory, window=WINDOW, run=RUN, min_gap=MIN_GAP):
    """f12_table.npz (sequences, f12, certified_at) and its descriptor f12_table.json."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    sequences, event, at = table(window, run, min_gap)
    np.savez(directory / "f12_table.npz", sequences=sequences, f12=event, certified_at=at)
    descriptor = {
        "format": TABLE_FORMAT,
        "arrays": {
            "sequences": {
                "axes": ["sequence", "boundary"],
                "dtype": "int8",
                "says": "1 inherited, 0 a break; column j is boundary j + 1 after the state; "
                "row i is the binary expansion of i, boundary 1 its most significant bit",
            },
            "f12": {"axes": ["sequence"], "dtype": "bool", "says": "the event, certified"},
            "certified_at": {
                "axes": ["sequence"],
                "dtype": "int64",
                "says": "the boundary (1-based) that completes the first qualifying run; 0 if "
                "the event is not certified",
            },
        },
        "parameters": parameters(window, run, min_gap),
        "count": int(event.sum()),
        "of": int(len(event)),
    }
    (directory / "f12_table.json").write_text(
        json.dumps(descriptor, indent=1, sort_keys=True) + "\n"
    )
    return descriptor
