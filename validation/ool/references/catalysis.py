"""Row OL1-3: catalysis is kinetic only.

Claim (§2.4, §7.1). A catalyst lowers the transition state, so it raises both directions' rates
by the same factor and moves no equilibrium.

Two references, each with its planted control:
1. **(3a) The closed world's stationary law does not depend on the catalysts.** The registered
   closed world, with its catalysts and with every catalyst removed, must each relax to
   exp(-F)/Z (``closed_world.check_closed_world``), so the two laws coincide. Planted: catalysis
   in the forward direction only (``forward_only_catalysis``), whose stationary law departs
   (total variation 0.30 in ``ol1_wa_closed``; README.md).
2. **(3b) A uniform factor rescales time.** Two runs of the closed world under one stream
   identity, the second with every forward rate constant doubled (a uniform ddG of ln 2 on
   every channel, both directions), must fire the identical channel sequence at exactly half
   the times. Doubling is exact in binary floating point, so the comparison is bitwise:
   tau = -ln(u1)/a0 halves exactly, and u2 a0 and every prefix sum double exactly. Planted: the
   factor on forward channels only, which changes the sequence (caught at the first event where
   a reverse channel competes).
"""

from __future__ import annotations

import numpy as np

from .common import CheckResult


def check_time_rescaling(base: dict, scaled: dict, factor: float = 2.0) -> CheckResult:
    """base/scaled: dicts with event_channel and event_time arrays from runs sharing a stream."""
    c0, c1 = np.asarray(base["event_channel"]), np.asarray(scaled["event_channel"])
    t0, t1 = np.asarray(base["event_time"], float), np.asarray(scaled["event_time"], float)
    detail = dict(events_base=int(c0.size), events_scaled=int(c1.size), factor=factor)
    if c0.size == 0:
        return CheckResult("uniform_factor_rescales_time", False, dict(detail, problem="the base run has no events"))
    n = min(c0.size, c1.size)
    differ = np.nonzero(c0[:n] != c1[:n])[0]
    if differ.size:
        return CheckResult("uniform_factor_rescales_time", False,
                           dict(detail, problem="channel sequences differ", first_difference=int(differ[0])))
    if c0.size != c1.size:
        return CheckResult("uniform_factor_rescales_time", False,
                           dict(detail, problem="the runs fire different numbers of events within the horizon"))
    bitwise = bool(np.array_equal(t0, t1 * factor))
    worst = float(np.max(np.abs(t0 - t1 * factor) / np.maximum(np.abs(t0), 1e-300)))
    return CheckResult("uniform_factor_rescales_time", bitwise, dict(detail, bitwise=bitwise, max_rel_time_error=worst))
