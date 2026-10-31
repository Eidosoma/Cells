"""Fixed inherited mechanics budgets and explicit full-buffer comparisons."""

import math
import struct
from copy import deepcopy


def numeric(value):
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (tuple, list)):
        rows = [numeric(item) for item in value]
        shape = rows[0][0] if rows else ()
        if any(row[0] != shape for row in rows):
            raise ValueError("Ragged output")
        return (len(rows), *shape), [item for row in rows for item in row[1]]
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Require finite complete numeric output")
    return (), [float(value)]


def flat(value, prefix="", *, native=False):
    if hasattr(value, "_asdict"):
        value = value._asdict()
    if hasattr(value, "tolist"):
        return {prefix: value.tolist()}
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if native and key == "interpolation":
                continue
            result.update(flat(item, prefix + ("." if prefix else "") + key, native=native))
        return result
    if isinstance(value, (tuple, list)):
        if any(isinstance(item, dict) for item in value):
            result = {}
            for index, item in enumerate(value):
                result.update(flat(item, prefix + "." + str(index), native=native))
            return result
        return {prefix: value}
    return {prefix: value} if type(value) in (int, float) else {}


def budget(name, target):
    if "interpolation" in name or name.startswith("operators."):
        absolute = 2e-14
    elif any(
        key in name
        for key in (
            "osmo_P_",
            "pressure_gradient",
            "gPxc",
            "gPyc",
            "osmotic_pressure_Pa",
            "delta_pressure_Pa",
        )
    ):
        absolute = 3e-9
    elif "display_" in name or "sample.vertices_m" in name or "sample.cell_centres_m" in name:
        absolute = 3e-17
    elif any(
        key in name
        for key in (
            ".PP",
            "PP_native",
            "u_osmo",
            "div_u_osmo",
            "water_velocity",
            "divergence_per_s",
            # Inherited deformation protocol treats this as an auxiliary,
            # not a displacement in metres (test_betse_deformation.close).
            "divergence_numeric",
        )
    ):
        absolute = 3e-14
    else:
        absolute = 3e-20
    return absolute + 8e-12 * abs(target)


def compare(actual, expected, *, native=False):
    observed, target = flat(actual, native=native), flat(expected, native=native)
    fields = []
    if observed.keys() != target.keys():
        raise ValueError(
            "Missing/extra complete output fields: " + str(sorted(set(observed) ^ set(target)))
        )
    maximum = 0.0
    for name in sorted(target):
        a_shape, a = numeric(observed[name])
        b_shape, b = numeric(target[name])
        if a_shape != b_shape:
            raise ValueError("Output axes changed: " + name)
        errors = [abs(x - y) / budget(name, y) for x, y in zip(a, b, strict=True)]
        fraction = max(errors, default=0.0)
        maximum = max(maximum, fraction)
        fields.append(
            dict(
                field=name,
                shape=list(a_shape),
                maximum_error_over_budget=fraction,
                full_binary64_bytes_equal=b"".join(struct.pack(">d", v) for v in a)
                == b"".join(struct.pack(">d", v) for v in b),
            )
        )
    return dict(
        fields=fields,
        numeric_columns=len(fields),
        maximum_error_over_budget=maximum,
        relative=8e-12,
        carried_allowance=False,
    )


def assert_compare(report, *, resolution=False):
    assert report["maximum_error_over_budget"] <= (0.1 if resolution else 1.0)


def stages(history):
    return [[frame["stage"] for frame in row["frames"]] for row in history]


def assert_controls(inputs, history):
    initial = inputs["initial"]
    policy = inputs["definition"]["policy"]

    def identical(a, b):
        shape_a, values_a = numeric(a)
        shape_b, values_b = numeric(b)
        return shape_a == shape_b and b"".join(
            struct.pack(">d", value) for value in values_a
        ) == b"".join(struct.pack(">d", value) for value in values_b)

    for row in history:
        assert row["auxiliaries"]["flow"] is None
        for key in ("u_cells_x", "u_cells_y", "u_env_x", "u_env_y"):
            assert identical(row["carried_cache"][key], initial[key])
        if not policy["deformation"]:
            assert identical(row["candidate"]["d_cells_x"], initial["d_cells_x"])
            assert identical(row["candidate"]["d_cells_y"], initial["d_cells_y"])
        if not policy["deform_osmo"]:
            assert identical(row["candidate"]["PP"], initial["PP"])


def corrupt(history, case):
    rows = deepcopy(history)
    if case == "wrong-PP":
        rows[0]["candidate"]["PP"][0] += 1e-6
    elif case == "wrong-displacement-axis":
        row = rows[0]["candidate"]
        row["d_cells_x"], row["d_cells_y"] = row["d_cells_y"], row["d_cells_x"]
    elif case == "changed-disabled-flow":
        rows[0]["candidate"]["u_cells_x"] = 1.0
    elif case == "stale-second-display-centres":
        rows[1]["carried_cache"]["display_centres_m"] = deepcopy(
            rows[0]["carried_cache"]["display_centres_m"]
        )
    elif case == "wrong-osmotic-dt":
        rows[0]["auxiliaries"]["osmotic"]["PP_native"] = [
            value * 1e6 for value in rows[0]["auxiliaries"]["osmotic"]["PP_native"]
        ]
        rows[0]["candidate"]["PP"] = [value * 1e6 for value in rows[0]["candidate"]["PP"]]
    else:
        raise ValueError("Unknown mechanical corruption")
    return rows
