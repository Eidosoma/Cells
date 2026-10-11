"""Source-order bath reduction and independent accounting; standard library only.

Reduction ordering follows the BSD-licensed NumPy source in numpy_source/.
This is deliberately limited to the positive length-30 float64 bath vectors in
the frozen capture, not a general NumPy replacement or a new transport law.
"""

import math
import sys
from fractions import Fraction


def require(condition, message):
    if not condition:
        raise ValueError(message)


def mean30(values):
    require(isinstance(values, list) and len(values) == 30, "Mean requires 30 native faces")
    require(
        all(
            type(v) is float
            and math.isfinite(v)
            and sys.float_info.min * 32 < v < sys.float_info.max / 32
            for v in values
        ),
        "Mean requires positive normal float64 concentrations",
    )
    # Eight independent accumulators, balanced combination, then six tail adds.
    # See the n <= 128 branch in the pinned loops_utils.h.src, followed by the
    # sum/divide sequence in the installed numpy/_core/_methods.py:_mean.
    lanes = values[:8]
    for offset in (8, 16):
        for lane in range(8):
            lanes[lane] += values[offset + lane]
    total = ((lanes[0] + lanes[1]) + (lanes[2] + lanes[3])) + (
        (lanes[4] + lanes[5]) + (lanes[6] + lanes[7])
    )
    for value in values[24:]:
        total += value
    return total / 30.0


def uniform(values):
    require(isinstance(values, list) and len(values) == 30, "Wrong bath extent")
    require(
        all(type(v) is float and math.isfinite(v) and v > 0 and v == values[0] for v in values),
        "Invalid or nonuniform shared bath",
    )
    return values[0]


def moving_ions(guard):
    actual = {k: v for k, v in guard["numeric"].items() if k.startswith("sim/movingIons/")}
    expected = {f"sim/movingIons/{i}": {"kind": "int", "value": i} for i in range(6)}
    require(actual == expected, "Ordinary updater must visit the six recorded ion species")
    require(
        guard["opaque_metadata"]["sim/movingIons"] == {"type": "list", "length": 6},
        "Moving ion container differs",
    )


def remix_record(prefix, stage, species, before, after, geometry, ledger):
    original, actual = uniform(before), uniform(after)
    expected = mean30(before)
    # Exact source arithmetic is essential: no fitted ULP or concentration epsilon.
    require(after == [expected] * 30, "Zero-flux bath does not match source-order mean")
    exact = Fraction.from_float
    delta = exact(actual) - exact(original)
    volume = exact(geometry["effective_bath_volume_m3"])
    amount = float(delta * volume * 10**15)
    name = f"{prefix}/zero_flux_mean/{stage}/{species}"
    ledger.add(name + "/material_roundoff", amount, 0.0, "amount_fmol")
    # A second, order-independent mathematical bound on a 29-add sum + division.
    # This diagnoses representation error; it does not replace exact matching or
    # relax the original whole-step conservation budget.
    u = Fraction(1, 2**53)
    gamma = 30 * u / (1 - 30 * u)
    require(abs(delta) <= gamma * abs(exact(original)), "Mean roundoff exceeds arithmetic bound")
    record = {
        "id": name,
        "stage": stage,
        "species": species,
        "input_concentration_mM": original,
        "output_concentration_mM": actual,
        "source_order_mean_mM": expected,
        "ideal_uniform_mean_mM": original,
        "roundoff_concentration_mM": float(delta),
        "roundoff_amount_fmol": amount,
        "roundoff_ulps": float(abs(delta)) / math.ulp(original),
        "source_order_exact": True,
    }
    ledger.remix_records.append(record)


def check_zero_flux_boundaries(prefix, row, geometry, maximum, ledger):
    physical = {
        stage: data["physical"] for stage, data in row.items() if stage.startswith("after_")
    }
    channel, network, ordinary, final = (
        physical[s] for s in ("after_channel", "after_network", "after_ordinary", "after_voltage")
    )
    regions = ("inside_mM", "outside_mM", "at_membrane_mM")
    # Preserve the original exact-identity verdict, separately from the corrected
    # source-operation check. Never rewrite the original receipt as a pass.
    for stage in ("after_network", "after_ordinary"):
        changed = [k for k in regions if physical[stage][k] != channel[k]]
        if changed:
            ledger.original_guard_rejections.append(
                {
                    "id": prefix + "/" + stage,
                    "original_guard": "no_duplicate_exact_identity",
                    "changed_fields": changed,
                }
            )
    if maximum == 0:
        changed = [k for k in (*regions, "voltage_V") if final[k] != row["before"]["physical"][k]]
        if changed:
            ledger.original_guard_rejections.append(
                {
                    "id": prefix + "/blocked_final",
                    "original_guard": "blocked_exact_identity",
                    "changed_fields": changed,
                }
            )
    require(
        all(network[k] == channel[k] for k in regions),
        "Empty network double-transferred channel material",
    )
    require(
        all(ordinary[k] == network[k] for k in ("inside_mM", "at_membrane_mM")),
        "Ordinary update changed cell material despite zero flux",
    )
    for field in ("ordinary_density_mol_per_m2_s", "junction_density_mol_per_m2_s"):
        require(
            all(v == 0.0 for species in network[field] for v in species),
            "Nonzero ordinary or junction transport cannot be treated as remixing",
        )
    require(
        all(final[k] == ordinary[k] for k in regions),
        "Voltage update changed physical inventories",
    )
    for species in range(6):
        remix_record(
            prefix,
            "after_ordinary",
            species,
            network["outside_mM"][species],
            ordinary["outside_mM"][species],
            geometry,
            ledger,
        )
    if maximum == 0:
        before = row["before"]["physical"]
        require(
            all(channel[k] == before[k] for k in ("inside_mM", "at_membrane_mM")),
            "Blocked channel changed cell material",
        )
        for species in range(6):
            if species == 1:
                remix_record(
                    prefix,
                    "blocked_after_channel",
                    species,
                    before["outside_mM"][species],
                    channel["outside_mM"][species],
                    geometry,
                    ledger,
                )
            else:
                require(
                    channel["outside_mM"][species] == before["outside_mM"][species],
                    "Blocked K channel changed another bath species",
                )


def summary(records):
    require(len({r["id"] for r in records}) == len(records), "Duplicate mean evidence identity")
    changed = [r for r in records if r["input_concentration_mM"] != r["output_concentration_mM"]]
    return {
        "zero_flux_means": len(records),
        "nonidentical_zero_flux_means": len(changed),
        "maximum_roundoff_concentration_mM": max(
            (abs(r["roundoff_concentration_mM"]) for r in records), default=0.0
        ),
        "maximum_roundoff_amount_fmol": max(
            (abs(r["roundoff_amount_fmol"]) for r in records), default=0.0
        ),
        "maximum_roundoff_ulps": max((r["roundoff_ulps"] for r in records), default=0.0),
        "captured_values_changed": False,
        "physical_tolerances_changed": False,
    }
