"""OL6 Protocol D, erratum 2's arithmetic for P-D1 (docs/OL6_PROTOCOL_D_ERRATUM_2.md; D304).

The erratum is the authority; this module is its registered arithmetic, tagged with it. It adds no
number. It reads only the registered closed form, limit_qualification.d0_stationary() (recorded as
`pd1_closed_form` in protocol_d.json), and D0's registered world (limit_qualification.D0), and it
judges with limit_qualification's own registered functions: scales, mean_error and criterion_b_at.

**P-D1's (d) side, in place of the refused (d) run.** The planted (d) run is D0 with min_count 1. At
each of D0's eight registered times it takes the closed form's rate-equation fixed point:
- n_A* is `fixed_point_n_A`;
- n_B* = (T - n_A*)/2 follows from D0's conservation law T = n_A + 2 n_B, with T = 12.
At the start it takes the founder, (n_A, n_B) = (4, 4), which is (d)'s own first row. So the scales
s_y follow §3's rule, the largest |y_d| over the founder and the registered times.

**The exact side** is D0's 256 exact replicas, on the first seed set, read at the registered times
by limit_qualification.observables, so A@pool and B@pool, each [256, 8].

**B** is criterion_b_at at n_k = n_min, with n_min from §6's rule over the protocol's worlds; when
that rule gives none, n_k = 98, the smallest value n_min can take, where the replica budget
c_r/sqrt(n_min) is largest. P-D1 is caught when B's replica part fails (spread_passes False). The
mean part is reported, as §8 registers.

Run with `PYTHONPATH=src:. JAX_ENABLE_X64=1`; `python -m validation.assembly_lineages_v2.
protocol_d_erratum_2 check` prints the (d) side and the scales, and runs nothing.
"""

import json
import sys

import numpy as np

from validation.assembly_lineages_v2 import limit_qualification as lq

N_MIN_FLOOR = 98  # §6: n_min's possible values run from 98 upward


def pd1_d_side(times=None):
    """(d, d_start): P-D1's (d) observables at D0's registered times, and at the start (the
    founder), as limit_qualification.observables returns them ({name: array})."""
    times = lq.D0["times"] if times is None else tuple(times)
    closed = lq.d0_stationary()
    n_a = float(closed["fixed_point_n_A"])
    n_b = (float(lq.D0["T"]) - n_a) / 2.0
    d = {"A@pool": np.full(len(times), n_a), "B@pool": np.full(len(times), n_b)}
    founder = lq.D0["founder"]
    d_start = {"A@pool": np.asarray([float(founder["A"])]),
               "B@pool": np.asarray([float(founder["B"])])}  # fmt: skip
    return d, d_start


def pd1_b(exact, n_min):
    """B for P-D1 against D0's exact replicas `exact` ({name: [M, T]} at the registered times):
    criterion_b_at's verdict, the n_k it used, and `caught` (its replica part fails)."""
    d, d_start = pd1_d_side()
    if set(exact) != set(d):
        raise ValueError(f"P-D1 reads A@pool and B@pool, not {sorted(exact)}")
    for name, values in exact.items():
        if np.asarray(values).shape[1] != len(d[name]):
            raise ValueError(f"{name}: one column per registered time ({len(d[name])})")
    n_k = N_MIN_FLOOR if n_min is None else n_min
    scale = lq.scales(d, d_start)
    errors = lq.mean_error(exact, d)
    verdict = lq.criterion_b_at(exact, d, errors, scale, n_k)
    return {**verdict, "n_k": n_k, "n_min_from_rule": n_min is not None, "scales": scale,
            "caught": not verdict["spread_passes"]}  # fmt: skip


def check():
    """The (d) side and the scales, from the closed form alone (nothing runs)."""
    d, d_start = pd1_d_side()
    scale = lq.scales(d, d_start)
    return {"d": {k: v.tolist() for k, v in d.items()},
            "d_start": {k: v.tolist() for k, v in d_start.items()},
            "scales": scale, "n_min_floor": N_MIN_FLOOR,
            "budget_at_floor": lq.C_SPREAD / N_MIN_FLOOR**0.5}  # fmt: skip


if __name__ == "__main__":
    if sys.argv[1:] != ["check"]:
        raise SystemExit("usage: python -m validation.assembly_lineages_v2.protocol_d_erratum_2 "
                         "check")
    print(json.dumps(check(), indent=1))
