"""Carrier keys, lives and run qualifiers: the family's relationship keys, frozen (D202).

These rules are fixed before any bundle is shared (D202; docs/RELATIONSHIPS_DESIGN.md §1.2–§1.4).
A run states them in run.json (`keys`, `lives`), and a test pins every constant below.

**Keys: a counter per sub-lineage.** A carrier key is an int64, s * 2**32 + c, written `s:c`: a
sub-lineage s and a count c within it.
- The founder holds `0:0` and starts sub-lineage 0's counter at `0:1`. (A world of several
  founders would give founder i `i:0`; this family's worlds have one.)
- At a fission both daughters take their keys from the parent's counter, the first daughter the
  lower: daughters `s:c` and `s:c+1`, and the counter moves to `s:c+2`. A daughter that is not
  followed still takes its key.
- The followed daughter (the continuation rule's pick, continuation.py) continues the counter.
  Each other daughter that lives on (it holds a molecule) starts a new sub-lineage s' for its own
  descendants, whose keys then run from `s':1`. Its own key stays the one its parent's counter
  gave it. A daughter that holds no molecule is extinct at its birth and takes no sub-lineage.
- New sub-lineages are numbered from 1 (after the one founder's 0) in the order (generation,
  parent key, daughter index), once every life of the previous generation has ended. The order
  depends on no horizon, budget, lane, batch or scheduling: a daughter at the horizon that holds a
  molecule takes its number as it would in a longer run, so horizons G and G + 1 give the same keys
  up to generation G.
- In single-lineage mode only sub-lineage 0 exists: no other daughter lives on. So its keys are the
  lineage counter's (the lane's next_carrier), bitwise as before the rule was written, and in
  every-descendant mode the followed path holds the same keys at every depth, since no other life
  draws on sub-lineage 0's counter.
- An assembly's random streams fold both 32-bit words of its key (streams.py), so lives of other
  sub-lineages draw from distinct streams.

**Ids** (cells.relations@1's form, so the family's rows go to its writer unchanged). A carrier's id
is `carrier:a<key>`, the int64 key in decimal (`carrier:a4294967297` is the key 1:1): an id's name
holds no ':'. Ids are unique within a run; across runs a carrier is the pair (world, id), the
world being the run qualifier (the relations tables' world column). A fission's event is
`event:fission/<its fission-table row>`, and a last leave's extinction
`event:extinction/<key>/<the lineage path's event count>` (the key keeps it unique among lives
of one every-descendant run, whose path counts can coincide).

**The run qualifier** is the SHA-256 of the JSON (keys sorted) of {definition fingerprint,
start}, as cells.relations@1 computes it, and of the run's stop when it stopped before its end:
- start is `fresh`, or for a run from a checkpoint {"checkpoint": its digest, "time": its time},
  the digest being the checkpoint's own (definition, clock and lane state, never a manifest that
  holds times of day);
- stop is {"events": e, "fissions": k}, the lane's clock where it stopped (an exact stop, or a
  batch's pause between device calls). A stopped run's records end its living life at the stop
  where the whole run's go on, so one (world, id) never names two rows. The clock is the world's
  own, so the qualifier does not depend on the batch that paused it.
It qualifies ids only and enters no stream fold: an assembly's streams depend on (seed,
environment, lineage, branch, carrier key, domain, counter) alone, so a restart continues
bitwise under a new qualifier. The definition's fingerprint holds the stream words, so two runs
that differ only by seed have different qualifiers. Two runs with one qualifier are the same
declared computation: replicas, not different entities.

**life_sublineage** is the sub-lineage whose counter the life's own daughters draw from: the
founder's own s; for the followed daughter, its parent's; for a daughter that opens a new one,
that new s'; -1 for an unfollowed daughter, or one born with no molecule. It is not the high word
of the life's key.

**Lives: one row per birth and end** (docs/RELATIONSHIPS_DESIGN.md §1.2), with the end reasons
below. An unfollowed daughter's life ends `not_followed`, which is not `extinct`: the run stopped
following it, and it held molecules. A daughter with no molecule ends `extinct` at its birth,
followed or not.
"""

import hashlib
import json

WORD = 2**32
FOUNDER = 0  # `0:0`
SPELLING = "s:c, with key = s * 2**32 + c"
ID_FORM = "carrier:a<key>, the int64 key in decimal"
EVENT_FORMS = {
    "fission": "event:fission/<fission-table row>",
    "extinction": "event:extinction/<key>/<lineage path event count>",
}

BIRTH_KINDS = ("founder", "division", "continued")
END_REASONS = ("divided", "extinct", "not_followed", "censored")
# Why a censored life's record ends: the horizon (the fission or generation limit), the growth
# event guard, a stalled total rate (a refusal), the every-descendant life budget, or a declared
# stop (a checkpoint, from which a later run continues it).
CENSORED_BY = ("horizon", "event_limit", "stalled", "budget", "stop")
TEXT = "<U12"  # The fixed-width string columns (loaded without pickle).

RULE = {
    "spelling": SPELLING,
    "founder": "0:0, starting sub-lineage 0's counter at 0:1",
    "daughters": "both daughters take keys from the parent's counter, the first daughter the "
    "lower; a daughter that is not followed still takes its key",
    "counter": "the followed daughter continues its parent's counter",
    "sublineages": "each other daughter that holds a molecule starts a new sub-lineage s' for its "
    "descendants (their keys run from s':1); its own key is the one its parent's counter gave it; "
    "a daughter with no molecule takes no sub-lineage",
    "numbering": "new sub-lineages are numbered from 1, in the order (generation, parent key, "
    "daughter index), once the previous generation has ended; independent of horizon, budget, "
    "lane, batch and scheduling",
    "single_lineage": "only sub-lineage 0: the keys are the lineage counter's",
    "streams": "an assembly's streams fold both 32-bit words of its key",
    "id": ID_FORM,
    "across_runs": "the pair (world, id), the world being the run qualifier",
    "events": EVENT_FORMS,
    "qualifier": "SHA-256 of the sorted-key JSON of {definition fingerprint, start}, as "
    "cells.relations@1 computes it, with the run's stop ({events, fissions}: the lane's clock) "
    "when it stopped before its end; start is 'fresh' or {checkpoint: its digest (definition, "
    "clock and lane state), time: its time}; it qualifies ids and enters no stream fold",
    "life_sublineage": "the sub-lineage whose counter the life's own daughters draw from: the "
    "founder's own s; the followed daughter's parent's; a new s' for a daughter that opens one; "
    "-1 for an unfollowed daughter or one born with no molecule (not the key's high word)",
}
LIVES = {
    "birth_kinds": {
        "founder": "the lineage's founder",
        "division": "a daughter of a fission",
        "continued": "alive at the start of a run that continues a checkpoint (a restart or a "
        "branch); it keeps its key, and its parent is in the run the checkpoint came from",
    },
    "end_reasons": {
        "divided": "it split at a fission",
        "extinct": "it emptied: its last molecule left, or it was born with none",
        "not_followed": "a daughter the single lineage did not follow (it held molecules); its "
        "record ends at its birth",
        "censored": "alive when its record ended: see life_censored_by",
    },
    "censored_by": {
        "horizon": "the run's fission limit (single lineage) or generation limit (every "
        "descendant)",
        "event_limit": "one growth reached experiment.growth_event_limit",
        "stalled": "the total rate was not a finite positive number (refused, not repaired)",
        "budget": "the every-descendant life budget",
        "stop": "a declared stop, with a checkpoint a later run continues from",
    },
}


def key(sub, count):
    """The int64 key s * 2**32 + c."""
    if not (0 <= sub < 2**31 and 0 <= count < WORD):
        raise ValueError(f"A key's words are s in [0, 2**31) and c in [0, 2**32): {sub}, {count}")
    return sub * WORD + count


def words(value):
    """(s, c) of a key."""
    value = int(value)
    if value < 0:
        raise ValueError(f"A carrier key is non-negative: {value}")
    return value >> 32, value & (WORD - 1)


def spelled(value):
    """`s:c`."""
    s, c = words(value)
    return f"{s}:{c}"


def carrier_id(value):
    """`carrier:a<key>`, the key in decimal."""
    words(value)  # A non-negative key.
    return f"carrier:a{int(value)}"


def qualifier(fingerprint, start="fresh", stop=None):
    """The run qualifier (module docstring): cells.relations@1's for {fingerprint, start}, and
    the run's stop {events, fissions} when it stopped before its end."""
    if start != "fresh" and not (isinstance(start, dict) and set(start) == {"checkpoint", "time"}):
        raise ValueError('A start is "fresh" or {"checkpoint": digest, "time": t}')
    body = {"definition": fingerprint, "start": start}
    if stop is not None:
        if not (isinstance(stop, dict) and set(stop) == {"events", "fissions"}):
            raise ValueError('A stop is {"events": e, "fissions": k}')
        body["stop"] = stop
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def number_sublineages(births, first):
    """New sub-lineage numbers for daughters that start one: {(parent key, daughter index): s'}.

    births: (generation, parent key, daughter index) of every daughter that starts a sub-lineage
    in one generation (or several, which the order keeps apart); first: the first unused number."""
    ordered = sorted((int(g), int(p), int(d)) for g, p, d in births)
    if len(set(ordered)) != len(ordered):
        raise ValueError("A daughter starts at most one sub-lineage")
    return {(p, d): first + i for i, (_, p, d) in enumerate(ordered)}
