"""Saved-column independent checks; no native or production numerical imports."""

import numpy as np

from validation.temperature import reference


def fraction(actual, expected, *, absolute, relative):
    value, target = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    if value.shape != target.shape or not np.isfinite(value).all() or not np.isfinite(target).all():
        raise ValueError("Incomplete/nonfinite temperature comparison columns")
    return float(np.max(abs(value - target) / (absolute + relative * abs(target)), initial=0))


def channel(row, protocol):
    name = row["class_name"]
    voltages = row["selected_voltage_V"]
    values = [
        reference.channel_step(
            name, float(v), protocol["native_step_s"], protocol["initial_update_gates"]
        )
        for v in voltages
    ]
    updated = row["updated"]
    count = len(voltages)
    maximum = 0.0

    def field(key):
        return np.broadcast_to(np.asarray(updated[key]), (count,))

    gate_tol = protocol["tolerances"]

    def gate(value, target):
        return fraction(
            value, target, absolute=gate_tol["gate_atol"], relative=gate_tol["gate_rtol"]
        )

    maximum = max(
        maximum,
        gate(field("_mInf"), [value["target"][0] for value in values]),
        gate(field("m"), [value["gates"][0] for value in values]),
    )
    if len(values[0]["target"]) == 2:
        maximum = max(
            maximum,
            gate(field("_hInf"), [value["target"][1] for value in values]),
            gate(field("h"), [value["gates"][1] for value in values]),
        )
    if name not in reference.ml.CLASSES or name in reference.ml.KINETIC:
        scale = float(np.asarray(updated["time_unit"]))
        if name in reference.ml.KINETIC:
            scale *= float(np.asarray(updated["Phi"]))
        for i, key in enumerate(("_mTau", "_hTau")[: len(values[0]["tau_s"])]):
            maximum = max(
                maximum,
                fraction(
                    field(key) / scale,
                    [value["tau_s"][i] for value in values],
                    absolute=gate_tol["tau_atol_s"],
                    relative=gate_tol["gate_rtol"],
                ),
            )
    opened = np.asarray([value["opening"] for value in values])
    if row["targets"] is not None:
        target = np.zeros(len(row["voltage_V"]))
        target[np.asarray(row["targets"], dtype=int)] = opened
    else:
        target = opened
    maximum = max(maximum, gate(np.asarray(updated["P"]), target))
    return dict(
        maximum_error_fraction=maximum,
        independent_scalar_points=count,
        target=[value["target"] for value in values],
        tau_s=[value["tau_s"] for value in values],
    )


def transport(row, protocol):
    expected = reference.transport(row)
    tol = protocol["tolerances"]
    pairs = [
        (row["electroflux"]["result"], expected["electroflux"]),
        (row["nernst_planck"]["planar"], expected["planar"]),
        (row["nernst_planck"]["vector"], expected["vector"]),
        (row["nernst_planck"]["special"], expected["special"]),
        (row["conductivity"], expected["conductivity"]),
    ]
    maximum = max(
        fraction(
            value, target, absolute=tol["flux_density_atol_mol_m2_s"], relative=tol["flux_rtol"]
        )
        for value, target in pairs
    )
    return dict(maximum_error_fraction=maximum, reference=expected)


def pumps(row, protocol):
    expected = reference.pumps(row)
    tol = protocol["tolerances"]
    maximum = max(
        fraction(
            row[key],
            expected[key],
            absolute=tol["flux_density_atol_mol_m2_s"],
            relative=tol["flux_rtol"],
        )
        for key in ("nak", "pmca", "serca")
    )
    return dict(maximum_error_fraction=maximum, reference=expected)


def legacy(row, protocol):
    expected = [
        reference.legacy_opening(*values, row["constants"])
        for values in zip(
            row["voltage_V"],
            row["calcium_free_numeric_mM"],
            [row["temperature_K"]] * len(row["voltage_V"]),
            strict=True,
        )
    ]
    tol = protocol["tolerances"]
    return dict(
        maximum_error_fraction=fraction(
            row["opening"], expected, absolute=tol["gate_atol"], relative=tol["gate_rtol"]
        ),
        reference=expected,
    )


def junction(row, protocol):
    expected = [
        [
            reference.electroflux(
                a, b, 1e-10, 1e-6, 1.0, v, row["configured_temperature_K"], row["constants"]
            )
            for a, b, v in ((12.0, 14.0, 0.035), (14.0, 12.0, -0.035))
        ]
    ]
    tol = protocol["tolerances"]
    return dict(
        maximum_error_fraction=fraction(
            row["flux"],
            expected,
            absolute=tol["flux_density_atol_mol_m2_s"],
            relative=tol["flux_rtol"],
        ),
        reference=expected,
    )


def reactions(rows, protocol):
    tol = protocol["tolerances"]
    expected = [
        reference.reaction_equilibrium(row["delta_g0_J_mol"], row["temperature_K"], row["R"])
        for row in rows
    ]
    return dict(
        maximum_error_fraction=fraction(
            [row["value"] for row in rows],
            expected,
            absolute=tol["scalar_atol"],
            relative=tol["scalar_rtol"],
        ),
        reference=expected,
    )
