"""Score a separately supplied Panama intermediate-K extraction against the frozen 5.4 mM fit.

Input is JSON with keys "10" and "20". Each contains [mV, relative current] rows on the
5 mV grid. An unreadable ordinate may be null. The calibration file has no evaluation rows.
"""

import argparse
import json
import math
from pathlib import Path

from cells.laws.channels.open_channel_block import reversal_potential

ANCHOR = Path(__file__).with_name("data") / "panama2006_external_k_anchor.json"


def half_crossing(rows):
    """A unique descending half crossing bracketed by adjacent readable grid samples."""
    above, exact, below = [], [], []
    previous = -math.inf
    for v, y in rows:
        if not (-120 <= v <= 60 and v % 5 == 0 and previous < v):
            raise ValueError("Expected increasing 5 mV grid voltages within [-120, 60]")
        previous = v
        if y is None:
            continue
        if not (math.isfinite(y) and y > 0):
            raise ValueError("Expected positive finite relative currents on the log ordinate")
        if y > 0.5:
            above.append((v, y))
        elif y < 0.5:
            below.append((v, y))
        else:
            exact.append(v)
    if not above or not below or len(exact) > 1:
        return None
    (lo, a), (hi, b) = above[-1], below[0]
    if exact:
        v50 = exact[0]
        if v50 - lo != 5 or hi - v50 != 5:
            return None
    else:
        if hi - lo != 5:
            return None
        v50 = lo + (hi - lo) * (0.5 - a) / (b - a)
    return v50, lo, hi


def score(external_k, rows, anchor):
    cal = anchor["calibration"]
    temp, ci = anchor["temperature_K"], anchor["internal_K_mM"]
    ref_shift = float(
        1000
        * (
            reversal_potential(ci, external_k, 1, temp)
            - reversal_potential(ci, cal["fit_external_K_mM"], 1, temp)
        )
    )
    result = dict(
        external_K_mM=external_k,
        concentration_shift_mV=ref_shift,
        absolute_voltage_shift_mV=0.0,
        closer="unresolved",
    )
    crossing = half_crossing(rows)
    if crossing is None:
        return result
    v50, lo, hi = crossing
    anchor_lo, anchor_hi = cal["fit_half_bracket_mV"]
    shift = v50 - cal["fit_half_voltage_mV"]
    # Two graph readings, each with approximately 1 mV horizontal reading uncertainty.
    interval = [lo - anchor_hi - 2, hi - anchor_lo + 2]
    midpoint = ref_shift / 2  # At both reserved K levels the concentration shift is positive.
    if interval[0] > midpoint:
        result["closer"] = "concentration reversal"
    elif interval[1] < midpoint:
        result["closer"] = "absolute voltage"
    result.update(
        half_voltage_mV=v50,
        half_bracket_mV=[lo, hi],
        observed_shift_mV=shift,
        shift_sensitivity_mV=interval,
        error_concentration_mV=shift - ref_shift,
        error_absolute_voltage_mV=shift,
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("extraction", type=Path, help="independently supplied two-level JSON")
    curves = json.loads(parser.parse_args().extraction.read_text())
    if set(curves) != {"10", "20"}:
        parser.error("Supply both reserved external K levels, 10 and 20 mM")
    anchor = json.loads(ANCHOR.read_text())
    print(
        json.dumps([score(k, curves[str(k)], anchor) for k in (10, 20)], indent=2, allow_nan=False)
    )
