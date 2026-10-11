"""Check saved native trajectories, independent ODEs and production Cells runs."""

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fresh_rerun"))
import common as u  # noqa: E402

cells_bridge = u.private("held_open_cells_bridge", Path(__file__).with_name("cells_bridge.py"))
ref = u.private("held_open_reference", Path(__file__).with_name("reference.py"))


def bound(value, limit, message):
    if not np.isfinite(value) or value > limit:
        raise ValueError(f"{message}: {value:.12g} > {limit:.12g}")


def check_accounting(values, tol, energy_key):
    for k in ("material_fmol", "local_transfer_fmol"):
        bound(values[k], tol[k], k)
    if energy_key is not None:
        bound(values["energy_pJ"], tol[energy_key], "energy balance")
    bound(-values["minimum_dissipation_increment_pJ"], 1e-12, "negative dissipation")


def check_errors(errors, tol, prefix):
    for key in ("voltage_V", "amount_fmol", "transfer_fmol", "energy_pJ"):
        tolerance = prefix + (
            "amount_fmol" if key == "transfer_fmol" and prefix != "native_" else key
        )
        bound(errors[key], tol[tolerance], prefix + key)


def check_native_voltage_boundaries(trace, ion_count):
    # Pinned BETSE sim_toolbox.electroflux mutates its voltage argument in
    # place with FLOAT_NONCE = 1e-25, even at zero membrane permeability.
    # One membrane call precedes the first observed update_gj; all moving
    # ions have made that call by the update_all_concs observation. Replay
    # sequential additions exactly rather than relaxing a continuity limit.
    expected = np.concatenate((trace["initial_vm"][None], trace["after_vm"][:-1]))
    for i in range(ion_count):
        expected += 1e-25
        if i == 0:
            np.testing.assert_array_equal(trace["before_vm"], expected)
    np.testing.assert_array_equal(trace["transport_vm"], expected)
    previous_average = np.concatenate((trace["initial_vm_ave"][None], trace["after_vm_ave"][:-1]))
    # electroflux receives the membrane array, not the cell-average array.
    np.testing.assert_array_equal(trace["before_vm_ave"], previous_average)
    np.testing.assert_array_equal(trace["transport_vm_ave"], previous_average)


def native_values(c, row, trace, protocol, *, gate_by_species=None):
    """Every step keeps native face lag, full-dt concentration update and charge closure."""
    tol = protocol["tolerances"]
    n, dt = row["steps"], row["dt_s"]
    ids, owners, pairs = c["indices"], c["owners"], c["faces"]
    a, b = pairs.T
    u.need(
        trace["after_cc_cells"].shape[0] == n and round(protocol["duration_s"] / dt) == n,
        "Native step count mismatch",
    )
    np.testing.assert_array_equal(trace["native_labels_s"], np.linspace(0, n * dt, n))
    np.testing.assert_array_equal(trace["species_order"], np.broadcast_to(ids, (n, len(ids))))
    np.testing.assert_array_equal(trace["before_cc_cells"][0], trace["initial_cc_cells"])
    np.testing.assert_array_equal(trace["before_cc_cells"][1:], trace["after_cc_cells"][:-1])
    check_native_voltage_boundaries(trace, len(ids))
    lagged = np.concatenate((trace["initial_cc_cells"][None], trace["before_cc_cells"][:-1]))
    np.testing.assert_array_equal(trace["before_cc_at_mem"], lagged[:, :, owners])
    np.testing.assert_array_equal(trace["after_cc_at_mem"], trace["before_cc_cells"][:, :, owners])
    for boundary in ("before", "transport", "after"):
        for field in ("cc_env", "Phi_b"):
            np.testing.assert_array_equal(
                trace[boundary + "_" + field],
                np.broadcast_to(trace["initial_" + field], trace[boundary + "_" + field].shape),
            )
        np.testing.assert_array_equal(
            trace[boundary + "_cc_cells"][:, c["immobile"]],
            np.broadcast_to(
                trace["initial_cc_cells"][c["immobile"]],
                trace[boundary + "_cc_cells"][:, c["immobile"]].shape,
            ),
        )
        np.testing.assert_array_equal(trace[boundary + "_fluxes_mem"], 0)
        u.need(
            np.min(trace[boundary + "_cc_cells"]) > 0
            and all(np.isfinite(v).all() for v in trace.values()),
            "Native domain/nonfinite trace",
        )
    gate = np.zeros(len(owners))
    gate[a] = gate[b] = c["opening"]
    if gate_by_species is None:
        np.testing.assert_array_equal(
            trace["transport_gjopen"], np.broadcast_to(gate, (n, len(gate)))
        )
    density = trace["transport_fluxes_gj"][:, ids]
    flux = density[:, :, a] * c["face_area_m2"][a] * 1e15
    bound(
        ref.maximum(flux + density[:, :, b] * c["face_area_m2"][b] * 1e15),
        tol["native_flux_fmol_s"],
        "Reciprocal face transfer",
    )
    boundary = np.flatnonzero(c["partners"] == np.arange(len(owners)))
    np.testing.assert_array_equal(density[:, :, boundary], 0)
    first_face = np.asarray([np.flatnonzero(owners == i)[0] for i in range(len(c["volume_pL"]))])
    previous = trace["before_cc_at_mem"][:, ids][:, :, first_face]
    potential = trace["before_vm_ave"]
    law = c if gate_by_species is None else c | {"opening": gate_by_species}
    expected_flux, power = ref.edge_rates(law, previous, potential)
    bound(ref.maximum(flux - expected_flux), tol["native_flux_fmol_s"], "Native flux law")
    predicted = trace["before_cc_cells"][:, ids] + dt * (flux @ c["incidence"].T) / c["volume_pL"]
    bound(
        ref.maximum(trace["after_cc_cells"][:, ids] - predicted),
        tol["native_update_mM"],
        "Native full-dt conservative update",
    )
    delta = np.concatenate(
        (
            np.zeros_like(c["initial_amount_fmol"])[None],
            (trace["after_cc_cells"][:, ids] - trace["initial_cc_cells"][ids]) * c["volume_pL"],
        )
    )
    transfer = np.concatenate(
        (np.zeros_like(c["permeability_m_s"])[None], np.cumsum(flux * dt, axis=0))
    )
    # Reconstruct native left-endpoint dissipation without modifying its physics.
    mu = c["R"] * c["temperature_K"] * np.log(
        previous[..., c["receivers"]] / previous[..., c["senders"]]
    ) - (
        c["valence"][:, None]
        * c["F"]
        * (potential[..., c["senders"]] - potential[..., c["receivers"]])[..., None, :]
    )
    power = -1e-3 * np.sum(flux * mu, axis=-2)
    dissipated = np.concatenate((np.zeros((1, len(c["opening"]))), np.cumsum(power * dt, axis=0)))
    potential = np.concatenate((trace["initial_vm_ave"][None], trace["after_vm_ave"]))
    bound(
        ref.maximum(potential - ref.voltage(c, delta)),
        tol["charge_voltage_V"],
        "Native charge closure",
    )
    checks = ref.accounting(c, delta, transfer, dissipated)
    # All steps must conserve material. Native energy accuracy is tested on
    # the finest step below; coarser energy errors remain visible evidence.
    check_accounting(checks, tol, None)
    values = np.concatenate(
        (delta.reshape((n + 1, -1)), transfer.reshape((n + 1, -1)), dissipated), axis=-1
    )
    return np.arange(n + 1) * dt, values, checks


def refinement(errors, protocol, prefix):
    floor = protocol["tolerances"][prefix + "refinement_floor_V"]
    ratio = protocol["tolerances"]["refinement_ratio_max"]
    for coarse, fine in zip(errors[:-1], errors[1:], strict=True):
        bound(fine["voltage_V"], ratio * coarse["voltage_V"] + floor, prefix + "voltage refinement")


def check(directory):
    panel = u.read(directory / "native/panel.json")
    protocol = u.read(directory / "protocol.json")
    u.need(panel["protocol"] == protocol, "Native trajectory protocol differs")
    tol = protocol["tolerances"]
    expected = {
        f"{case['id']}/step-{i}/{mode}"
        for case in protocol["cases"]
        for i in range(len(protocol["native_steps_s"]))
        for mode in protocol["native_modes"]
    }
    u.need(
        len(panel["rows"]) == len(expected) and {r["path"] for r in panel["rows"]} == expected,
        "Native panel missing or duplicate rows",
    )
    rows = {}
    for record in panel["rows"]:
        path = directory / "native" / record["path"]
        u.need(u.sha(path / "result.json") == record["sha256"], "Native row changed")
        row = u.read(path / "result.json")
        u.need(row["hook_restored"] and row["native_pickle_present"], "Incomplete native lifecycle")
        u.need(
            u.sha(path / "preparation.json") == row["preparation_sha256"],
            "Native preparation changed",
        )
        u.need(
            all(
                v == (protocol["gj_surface_fraction"] if k == "gj_surface" else 0)
                for k, v in row["settings"].items()
            ),
            "Native inactive process settings changed",
        )
        if row["mode"] == "observed":
            u.need(u.sha(path / "trace.npz") == row["trace_sha256"], "Native trace changed")
        rows[record["path"]] = row
    reports = []
    for case in protocol["cases"]:
        c = None
        native_errors, native_accounting = [], []
        for i, dt in enumerate(protocol["native_steps_s"]):
            key = f"{case['id']}/step-{i}"
            observed, bare = (rows[key + "/" + mode] for mode in ("observed", "bare"))
            for r, mode in ((observed, "observed"), (bare, "bare")):
                u.need(
                    r["case"] == case and r["dt_s"] == dt and r["mode"] == mode,
                    "Native row identity changed",
                )
            u.need(
                observed["final"] == bare["final"] and observed["fixture"] == bare["fixture"],
                "Observer changes native final/history or preparation",
            )
            path = directory / "native" / key / "observed"
            with np.load(path / "trace.npz", allow_pickle=False) as archive:
                trace = dict(archive)
            bound_case = ref.bind(u.read(path / "preparation.json"), observed, trace, protocol)
            if c is None:
                c = bound_case
                out = directory / "comparison" / case["id"]
                out.mkdir(parents=True, exist_ok=False)
                u.write(
                    out / "mapping.json",
                    {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in c.items()},
                )
                reference = ref.integrate(c, protocol, "DOP853")
                independent = ref.integrate(c, protocol, "Radau")
                common = np.linspace(
                    0,
                    protocol["duration_s"],
                    round(protocol["duration_s"] / protocol["observation_step_s"]) + 1,
                )
                reference_agreement = ref.difference(
                    c, reference.sol(common).T, independent.sol(common).T
                )
                check_errors(reference_agreement, tol, "reference_")
                np.savez_compressed(
                    out / "references.npz",
                    times_s=common,
                    dop853=reference.sol(common).T,
                    radau=independent.sol(common).T,
                )
                reference_checks = ref.accounting(c, *ref.unpack(c, reference.sol(common).T))
                check_accounting(reference_checks, tol, "reference_energy_pJ")
            else:
                for k in c:
                    np.testing.assert_array_equal(bound_case[k], c[k])
            times, values, checks = native_values(c, observed, trace, protocol)
            errors = ref.difference(c, values, reference.sol(times).T)
            native_errors.append(errors)
            native_accounting.append(checks)
            np.savez_compressed(out / f"native-{i}-physical.npz", times_s=times, values=values)
        u.write(
            out / "native-checks.json",
            {
                "reference_agreement": reference_agreement,
                "reference_accounting": reference_checks,
                "native_errors": native_errors,
                "native_accounting": native_accounting,
            },
        )
        check_errors(native_errors[-1], tol, "native_")
        check_accounting(native_accounting[-1], tol, "native_energy_pJ")
        refinement(native_errors, protocol, "native_")
        cells_errors, cells_reports = [], []
        for i, dt in enumerate(protocol["cells_steps_s"]):
            times, values, report = cells_bridge.run(c, protocol, dt, out / f"cells-{i}", u.write)
            errors = ref.difference(c, values, reference.sol(times).T)
            check_errors(errors, tol, "cells_")
            checks = ref.accounting(c, *ref.unpack(c, values))
            check_accounting(checks, tol, "cells_energy_pJ")
            cells_errors.append(errors)
            cells_reports.append(report | {"accounting": checks})
        refinement(cells_errors, protocol, "cells_")
        end_delta, _, _ = ref.unpack(c, reference.sol(protocol["duration_s"]))
        change = ref.maximum(ref.voltage(c, end_delta) - c["initial_voltage_V"])
        if case["fixture"] in ("equal", "equilibrium") or case["topology"] == "disconnected":
            bound(change, tol["reference_voltage_V"], "Zero-drive/disconnected trajectory")
        else:
            u.need(
                change > tol["minimum_driven_voltage_change_V"],
                "Driven case has no resolved voltage response",
            )
        reports.append(
            {
                "case": case,
                "reference_agreement": reference_agreement,
                "reference_accounting": reference_checks,
                "native_errors": native_errors,
                "native_accounting": native_accounting,
                "cells_errors": cells_errors,
                "cells_runs": cells_reports,
                "voltage_change_V": change,
                "observer_pairs": len(protocol["native_steps_s"]),
            }
        )
        u.write(out / "checks.json", reports[-1])
        print(case["id"], "passes", flush=True)
    return {
        "status": "held_open_free_voltage_junction_trajectories_pass",
        "cases": reports,
        "native_runs": len(rows),
        "observer_pairs": len(rows) // 2,
        "cells_runs": len(reports) * len(protocol["cells_steps_s"]),
        "duration_s": protocol["duration_s"],
        "dynamic_gate_qualified": False,
        "full_betse_parity": False,
        "biological_validation": False,
        "scope": protocol["physical_scope"],
        "comparison_files_sha256": u.inventory(directory / "comparison"),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    u.write(args.output / "comparison-result.json", check(args.output))
