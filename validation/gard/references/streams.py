"""Row 9. Streams: replay, batch-partition invariance, independence of branches, and
restart, written as checks over saved records.

Claim: a run's randomness is a pure function of its declared stream identity and
counters. So:
1. Bitwise replay on one backend. Two runs with the same world, law, stream identity and
   backend have bitwise-identical arrays.
2. Batch-partition invariance. A world run alone and the same world run inside a batch
   (any partition of the batch) have bitwise-identical arrays.
3. Independence of branches. Futures launched from one landmark with distinct branch
   keys must not share randomness. For independent streams, two branches repeat the same
   first L events with probability at most (max_j p_j)^L. That is below 1e-20 for
   L = 50 in GARD worlds. Any repeat of a branch's first ``PREFIX`` events therefore
   flags a reused key. So does any repeat of its event or partition uniforms, when the
   diagnostic records exist. Partition streams are keyed by the parent's carrier key, so
   branches from one landmark must not share carrier keys. Distinct declared identities
   are required too.
4. Restart. A run restarted from a checkpoint (mid-growth, or across a fission) matches
   the uninterrupted run bitwise on every array from the checkpoint on.

What the harness needs: a reference bundle and its replay; a solo bundle and a batched
one; at least two branch bundles from one landmark; and restarted bundles, each declaring
``restart.row``, ``restart.event`` and ``restart.fission`` in run.json. The identity
fields replays must share are ``records.IDENTITY_FIELDS``. Branches must carry the
diagnostic event and partition uniforms.

Planted control: a reused key. Two branches that share a stream must be caught.
"""

from __future__ import annotations

import numpy as np

from .common import CheckResult

PREFIX = 50
ROW_AXIS_ARRAYS = ("row_time", "row_event", "assembly_count", "joined_total", "left_total", "discarded_total",
                   "exchange_heat_kT", "fission_work_kT", "discarded_free_energy_kT", "log_weight",
                   "ledger_residual_kT", "occupant", "generation")
EVENT_AXIS_ARRAYS = ("event_time", "event_channel", "event_uniforms")
FISSION_AXIS_ARRAYS = ("fission_time", "fission_slot", "fission_parent", "fission_daughters", "fission_followed",
                       "fission_split", "fission_similarity", "fission_partition_counter",
                       "continuation_uniform")


def _bitwise_equal(a: np.ndarray, b: np.ndarray) -> bool:
    a = np.asarray(a)
    b = np.asarray(b)
    return a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()


def compare_arrays(a: dict, b: dict) -> dict:
    names = sorted(set(a) | set(b))
    only_a = [n for n in names if n not in b]
    only_b = [n for n in names if n not in a]
    differ = [n for n in names if n in a and n in b and not _bitwise_equal(a[n], b[n])]
    return dict(only_in_first=only_a, only_in_second=only_b, differ=differ)


def check_bitwise_replay(arrays_a: dict, arrays_b: dict, identity_a: dict, identity_b: dict,
                         raw_a: dict | None = None, raw_b: dict | None = None,
                         name: str = "bitwise_replay") -> CheckResult:
    """Arrays bitwise equal and the identity fields equal; other differing raw fields listed.

    ``identity_*`` map canonical identity names to values (``RunView.identity()``). A field
    declared by neither run cannot be compared; it is listed as absent rather than passed.
    """
    cmp = compare_arrays(arrays_a, arrays_b)
    names = sorted(set(identity_a) | set(identity_b))
    absent = [k for k in names if identity_a.get(k) is None and identity_b.get(k) is None]
    identity_differs = [k for k in names if k not in absent and identity_a.get(k) != identity_b.get(k)]
    other_differs = []
    if raw_a is not None and raw_b is not None:
        other_differs = sorted(k for k in set(raw_a) | set(raw_b) if raw_a.get(k) != raw_b.get(k))
    passed = (not cmp["only_in_first"] and not cmp["only_in_second"] and not cmp["differ"]
              and not identity_differs)
    return CheckResult(name, bool(passed), dict(arrays=len(set(arrays_a) | set(arrays_b)),
                                                identity_fields_differ=identity_differs,
                                                identity_fields_absent=absent,
                                                raw_run_fields_differ=other_differs, **cmp))


def check_batch_invariance(solo: dict, batched: dict, identity_solo: dict, identity_batched: dict,
                           raw_solo: dict | None = None, raw_batched: dict | None = None) -> CheckResult:
    return check_bitwise_replay(solo, batched, identity_solo, identity_batched, raw_solo, raw_batched,
                                name="batch_partition_invariance")


def check_restart(original: dict, restarted: dict, restart_row: int, restart_event: int,
                  restart_fission: int) -> CheckResult:
    """Arrays from the checkpoint on must equal the uninterrupted run bitwise.

    A restarted bundle may hold the whole history or only the part after its checkpoint.
    Its row arrays are compared from ``restart_row``, event arrays from ``restart_event``
    and fission arrays from ``restart_fission``. When the restarted bundle is complete,
    its earlier part is compared too.
    """
    differ = []
    missing = []
    for names, start in ((ROW_AXIS_ARRAYS, restart_row), (EVENT_AXIS_ARRAYS, restart_event),
                         (FISSION_AXIS_ARRAYS, restart_fission)):
        for n in names:
            if n not in original:
                continue
            if n not in restarted:
                missing.append(n)
                continue
            o = np.asarray(original[n])
            r = np.asarray(restarted[n])
            if r.shape[0] == o.shape[0]:
                tail_o, tail_r = o, r
            elif r.shape[0] == o.shape[0] - start:
                tail_o, tail_r = o[start:], r
            else:
                differ.append(f"{n}: length {r.shape[0]} fits neither the whole run nor its tail")
                continue
            if not _bitwise_equal(tail_o, tail_r):
                differ.append(n)
    return CheckResult("restart", not differ and not missing, dict(
        restart_row=restart_row, restart_event=restart_event, restart_fission=restart_fission,
        differ=differ, missing=missing))


def check_branch_independence(branches: list[dict], identities: list, prefix: int = PREFIX) -> CheckResult:
    """``branches`` holds each branch's arrays; ``identities`` their declared stream identities."""
    n = len(branches)
    if n < 2:
        return CheckResult("branch_independence", False, dict(error="need at least two branches"))
    ids = [repr(sorted(i.items())) if isinstance(i, dict) else repr(i) for i in identities]
    distinct_ids = len(set(ids)) == n
    repeats = []
    for a in range(n):
        for b in range(a + 1, n):
            ca = np.asarray(branches[a]["event_channel"])
            cb = np.asarray(branches[b]["event_channel"])
            L = min(prefix, ca.size, cb.size)
            same_events = L > 0 and np.array_equal(ca[:L], cb[:L])
            same_u = False
            if "event_uniforms" in branches[a] and "event_uniforms" in branches[b]:
                ua = np.asarray(branches[a]["event_uniforms"])
                ub = np.asarray(branches[b]["event_uniforms"])
                m = min(ua.shape[0], ub.shape[0], prefix)
                same_u = m > 0 and np.array_equal(ua[:m], ub[:m])
            same_p = False
            if "partition_uniforms" in branches[a] and "partition_uniforms" in branches[b]:
                pa = np.asarray(branches[a]["partition_uniforms"]).ravel()
                pb = np.asarray(branches[b]["partition_uniforms"]).ravel()
                m = min(pa.size, pb.size, prefix)
                same_p = m > 0 and np.array_equal(pa[:m], pb[:m])
            if same_events or same_u or same_p:
                repeats.append((a, b, bool(same_events), bool(same_u), bool(same_p)))
    partition_compared = all("partition_uniforms" in br for br in branches)
    return CheckResult("branch_independence", bool(distinct_ids and not repeats), dict(
        branches=n, distinct_identities=distinct_ids, prefix=prefix, repeated_pairs=repeats[:10],
        partition_stream_compared=partition_compared))
