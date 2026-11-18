"""Row OL1-6: streams, replay and branching.

Claim (§7.1). Runs are reproducible from their stream identity: a run repeated under the same
identity is bitwise equal in every saved array, and runs under different identities share no
uniforms and no event prefix. G1's stream tests carry the rest (restart, batch partition,
branches); this row re-runs the two cheapest checks on OL1's general-stoichiometry kernel,
because §7.1 asks for G1's tests to be re-run when the kernel changes.

Planted control: a reused key (two runs that declare different identities but draw the same
uniforms) is caught.
"""

from __future__ import annotations

import numpy as np

from .common import CheckResult


def check_replay(a: dict, b: dict, arrays=("event_channel", "event_time", "row_event", "counts", "heat", "work")) -> CheckResult:
    """Row OL1-6: two runs of one identity are bitwise equal in every saved array."""
    unequal = []
    for name in arrays:
        if name not in a or name not in b:
            unequal.append(f"{name} (missing)")
            continue
        x, y = np.asarray(a[name]), np.asarray(b[name])
        if x.shape != y.shape or x.dtype != y.dtype or x.tobytes() != y.tobytes():
            unequal.append(name)
    return CheckResult("bitwise_replay", not unequal, dict(unequal=unequal))


def check_distinct_streams(a: dict, b: dict, prefix: int = 50) -> CheckResult:
    """Row OL1-6: runs that declare different stream identities must not share their uniforms
    or their first ``prefix`` events (a reused key is caught)."""
    ua, ub = np.asarray(a.get("event_uniforms", [])), np.asarray(b.get("event_uniforms", []))
    ca, cb = np.asarray(a["event_channel"])[:prefix], np.asarray(b["event_channel"])[:prefix]
    ta, tb = np.asarray(a["event_time"])[:prefix], np.asarray(b["event_time"])[:prefix]
    same_trace = ca.size > 0 and ca.size == cb.size and np.array_equal(ca, cb) and np.array_equal(ta, tb)
    n = min(len(ua), len(ub))
    shared = bool(n and np.any(np.all(ua[:n] == ub[:n], axis=1)))
    return CheckResult("distinct_streams", not (same_trace or shared),
                       dict(same_prefix_trace=bool(same_trace), shared_uniforms=shared))
