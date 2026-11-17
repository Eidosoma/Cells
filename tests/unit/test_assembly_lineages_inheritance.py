"""Inheritance and the F12 event (validation/assembly_lineages/inheritance.py): analysis of saved
lineages, decided in exact integer arithmetic.

Each claim with a planted error it must catch (D187):
- H > 0.9 strictly, decided exactly: integer pairs whose cosine is exactly 9/10 are breaks, and
  a pair just above is inherited (planted: a non-strict threshold, H >= 0.9, which calls every
  exact pair inherited);
- the F12 table equals an independent predicate, a regular expression over the twelve-symbol
  string ("0", then later "111", within the window), on all 4,096 sequences (planted: a window of
  eleven, an off-by-one, and a gap of one boundary required after the break, each disagreeing on
  a row named here);
- marks end at an extinct boundary, and a short sequence is scored on what it has.
"""

import itertools
import math
import re

import numpy as np

from validation.assembly_lineages import inheritance as inh


def exact_ninths(limit=12, length=3):
    """Integer pairs (P, D) whose cosine is exactly 9/10."""
    out = []
    for p in itertools.product(range(limit), repeat=length):
        for d in itertools.product(range(limit), repeat=length):
            pp, dd = sum(v * v for v in p), sum(v * v for v in d)
            pd = sum(a * b for a, b in zip(p, d, strict=True))
            if pp and dd and 100 * pd * pd == 81 * pp * dd:
                out.append((p, d))
    return out


def test_inheritance_is_strict_and_exact():
    pairs = exact_ninths()
    assert len(pairs) > 100
    assert all(inh.inherited(p, d) is False for p, d in pairs)  # H = 0.9 is a break.

    # Planted: a non-strict threshold (H >= 0.9) calls every one of them inherited.
    def nonstrict(p, d):
        pp, dd = int(np.dot(p, p)), int(np.dot(d, d))
        return 100 * int(np.dot(p, d)) ** 2 >= 81 * pp * dd

    assert all(nonstrict(p, d) for p, d in pairs)
    # The floating-point cosine is diagnostic only: on these exact pairs it is not even one
    # value (one square root of the product gives 0.9, two give less for some).
    one = {np.dot(p, d) / math.sqrt(np.dot(p, p) * np.dot(d, d)) for p, d in pairs}
    two = {np.dot(p, d) / (math.sqrt(np.dot(p, p)) * math.sqrt(np.dot(d, d))) for p, d in pairs}
    assert one == {0.9} and min(two) < 0.9
    assert inh.inherited((3, 4), (3, 4)) is True and inh.inherited((1, 0), (0, 1)) is False
    assert inh.inherited((1, 2), (0, 0)) is None
    assert inh.inherited((0, 1, 1), (3, 4, 6)) is True  # Just above 9/10: inherited.


def regex_f12(row, window=12):
    """The independent predicate: a break, then strictly later three inherited in a row."""
    return re.search("0[01]*?111", "".join(str(int(v)) for v in row[:window])) is not None


def test_the_f12_table_equals_an_independent_predicate():
    sequences, event, at = inh.table()
    assert sequences.shape == (4096, 12) and event.shape == (4096,)
    expected = np.asarray([regex_f12(row) for row in sequences])
    assert np.array_equal(event, expected)
    assert int(event.sum()) == int(expected.sum())
    assert event[0b011100000000] and at[0b011100000000] == 4
    assert not event[0b111011011011]  # A three-run, then a break and no run after it ...
    assert event[0b110110110111]  # ... and its mirror: a break, then the run. Not symmetric.
    assert event[0b000000000111] and at[0b000000000111] == 12  # The last three boundaries.
    assert not event[0b111111111111] and not event[0]
    # Planted: a window of eleven (an off-by-one), and a run counted from the break's boundary.
    _, eleven, _ = inh.table(window=11)
    assert eleven.shape == (2048,)
    off = np.asarray([inh.f12(row, window=11) for row in sequences])
    assert not np.array_equal(off, event) and event[0b000000000111] and not off[0b000000000111]
    gap = np.asarray([inh.f12(row, min_gap=1) for row in sequences])
    assert not np.array_equal(gap, event) and event[0b011100000000] and not gap[0b011100000000]


def test_marks_end_at_extinction_and_short_sequences_score_their_prefix():
    parents = np.asarray([[4, 4], [4, 4], [4, 4]])
    daughters = np.asarray([[2, 2], [4, 0], [0, 0]])
    assert inh.marks(parents, daughters) == [1, 0]  # The third boundary is an extinction.
    assert inh.f12([0, 1, 1, 1]) and inh.certified_at([0, 1, 1, 1]) == 4
    assert not inh.f12([0, 1, 1])  # Extinct before certification: negative.
    split = np.asarray([[2, 2], [4, 0]])
    assert inh.lineage_marks(split, [0, 1], parents[:2]) == [1, 0]
