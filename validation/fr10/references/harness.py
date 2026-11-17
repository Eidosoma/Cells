"""The comparison harness: FR-10's references against saved run bundles (a skeleton).

    python -m validation.fr10.references.harness run --roles ROLES.json \\
        [--tolerances TOL.json] [--out REPORT.json]

It reads only saved bundles in the canonical layout (``bundles.py``), never engine source. When
the engine declares its own layout, ``engine_layout.py`` maps it onto the canonical one.

**Roles** (paths relative to ROLES.json):
- ``faces``: W1 bundles, one per dt of the registered ladder;
- ``ion``: W2 bundles, one per dt of the ladder;
- ``records_W1``, ``records_W2`` and ``records_W3``: one bundle each with the event records, the
  supply and K (a ``faces`` or ``ion`` bundle may serve).

**Rows:**
- ``faces`` and ``ion``: agreement with the exact reference at the registered record times, at
  each dt, within tau(dt); and the order: the error must fall at an observed order of at least
  ``ORDER_MIN`` per halving of dt while it stays above 100 times the reference's floor. W2's
  impermeant amounts must not change.
- ``records``: per event, the dose to rounding, dG_b within 1e-12 relative and a neutral step's
  charge to rounding.
- ``K``: the bundle's K against ``records.reconciliation_K`` of the bundle's own supply, to
  rounding; for W1 and W2 also against K of the reference supply, within the supply's tau.

**Tolerances.** tau(dt) comes from TOL.json, ``{"W1": {"<dt>": fmol}, "W2": {"<dt>": V}}``, or
defaults to the registered ceiling at that dt (``designs/fr10_reference_design.json``). A
tolerance above the ceiling has no power against the planted controls and is refused (status
2), as is one below ten times the reference's floor.

**Exit status:** 0 when every requested row passes; 1 when a check fails; 2 when a bundle, role,
array, column order or tolerance is missing or malformed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from . import faces, ion, records
from .bundles import BundleError, columns, need, read_bundle
from .common import (
    MIN_MARGIN,
    UNIT_ROUNDOFF,
    CheckResult,
    Constants,
    constants_from_block,
    jsonable,
    load_inputs,
)
from .design import DESIGN_FILE

ORDER_MIN = 1.5
DG_RTOL = 1e-12
TIME_ATOL_S = 1e-12


_CACHE: dict = {}


def _design() -> dict:
    return json.loads(DESIGN_FILE.read_text())


def _faces_reference(inputs: dict) -> dict:
    """The exact W1 solution, computed once per process for the registered inputs."""
    key = ("faces", json.dumps(inputs["R_faces"], sort_keys=True))
    if key not in _CACHE:
        _CACHE[key] = faces.solve(faces.parse(inputs["R_faces"]))
    return _CACHE[key]


def _ion_reference(inputs: dict) -> tuple:
    """(world, solution) for W2, computed once per process for the registered inputs."""
    key = ("ion", json.dumps(inputs["R_ion"], sort_keys=True))
    if key not in _CACHE:
        world = ion.parse(inputs["R_ion"], constants_from_block(inputs["constants"]))
        _CACHE[key] = (world, ion.solve(world))
    return _CACHE[key]


def _ceilings(design: dict, world: str, unit: str) -> dict:
    return {float(r["dt_s"]): float(r["ceiling"][unit]) for r in design["power"][world]["per_dt"]}


def _tolerance(tolerances: dict | None, world: str, dt: float, ceiling: dict, floor: float):
    if dt not in ceiling:
        raise BundleError(f"{world}: dt {dt} is not on the registered ladder {sorted(ceiling)}")
    if tolerances is None or world not in tolerances:
        tau = ceiling[dt]
    else:
        table = {float(k): float(v) for k, v in tolerances[world].items()}
        if dt not in table:
            raise BundleError(f"tolerances for {world} lack dt {dt}")
        tau = table[dt]
    if tau > ceiling[dt] * (1 + 1e-12):
        raise BundleError(f"{world} at dt {dt}: tolerance {tau} exceeds the registered ceiling "
                          f"{ceiling[dt]} and has no power")
    if tau < MIN_MARGIN * floor:
        raise BundleError(f"{world} at dt {dt}: tolerance {tau} is within ten floors ({floor})")
    return tau


def _rows_at(times: np.ndarray, want: np.ndarray, where) -> np.ndarray:
    idx = np.searchsorted(times, want - TIME_ATOL_S)
    ok = (idx < times.size) & (np.abs(times[np.minimum(idx, times.size - 1)] - want)
                               <= TIME_ATOL_S)
    if not np.all(ok):
        raise BundleError(f"{where}: the registered record time {want[~ok][0]} is not saved")
    return idx


def _ladder_order(errors: list, floor: float) -> CheckResult:
    pairs = []
    passed = True
    for (dt_a, e_a), (dt_b, e_b) in zip(errors, errors[1:], strict=False):
        if not np.isclose(dt_a / dt_b, 2.0, rtol=1e-9):
            raise BundleError(f"the ladder is not halving: {dt_a} then {dt_b}")
        resolved = e_b > 100 * floor
        order = float(np.log2(e_a / e_b)) if e_a > 0 and e_b > 0 else None
        ok = (not resolved) or (order is not None and order >= ORDER_MIN)
        passed &= ok
        pairs.append({"dt": [dt_a, dt_b], "errors": [e_a, e_b], "order": order,
                      "resolved": resolved, "passed": ok})
    return CheckResult("order", passed, {"order_min": ORDER_MIN, "pairs": pairs})


def check_faces(dirs: list, inputs: dict, design: dict, tolerances=None) -> list:
    ref = _faces_reference(inputs)
    floor = float(np.max(ref["floor_fmol"]))
    ceiling = _ceilings(design, "W1", "amount_fmol")
    results, errors = [], []
    for d in dirs:
        run, arr = read_bundle(d)
        if run["world"] != "W1":
            raise BundleError(f"{d}: a faces bundle must be W1")
        nodes = columns(run, "nodes", d)
        if nodes != ref["nodes"]:
            raise BundleError(f"{d}: nodes {nodes} differ from {ref['nodes']}")
        dt = float(run["dt_s"])
        tau = _tolerance(tolerances, "W1", dt, ceiling, floor)
        rows = _rows_at(need(arr, "time_s", d), ref["times_s"], d)
        amt = need(arr, "node_amount_fmol", d)[rows]
        err = float(np.max(np.abs(amt - ref["amount_fmol"])))
        sup_cols = columns(run, "species", d)
        sup = need(arr, "supply_fmol", d)[rows, sup_cols.index(ref["species"])]
        err_s = float(np.max(np.abs(sup - ref["supply_fmol"])))
        errors.append((dt, err))
        results.append(CheckResult(f"faces@{dt:g}", err <= tau and err_s <= tau, {
            "dt_s": dt, "tolerance_fmol": tau, "amount_error_fmol": err,
            "supply_error_fmol": err_s}))
    errors.sort(key=lambda x: -x[0])
    results.append(_ladder_order(errors, floor))
    return results


def check_ion(dirs: list, inputs: dict, design: dict, tolerances=None) -> list:
    const = constants_from_block(inputs["constants"])
    world, ref = _ion_reference(inputs)
    floor = float(np.max(ref["floor"]["V_m_V"]))
    ceiling = _ceilings(design, "W2", "V_m_V")
    p = world.permeant[0]
    results, errors = [], []
    for d in dirs:
        run, arr = read_bundle(d)
        if run["world"] != "W2":
            raise BundleError(f"{d}: an ion bundle must be W2")
        sp = columns(run, "species", d)
        dt = float(run["dt_s"])
        tau = _tolerance(tolerances, "W2", dt, ceiling, floor)
        rows = _rows_at(need(arr, "time_s", d), ref["times_s"], d)
        V = need(arr, "V_m_V", d)[rows]
        cell = need(arr, "cell_amount_fmol", d)[rows]
        err = float(np.max(np.abs(V - ref["V_m_V"])))
        # the permeant ion's amount, through the charge invariant: tau_V in volts of charge
        tau_n = tau * float(10 ** 15 * world.capacitance_F / const.faraday)
        err_n = float(np.max(np.abs(cell[:, sp.index(p)] - ref["amount_fmol"][p])))
        fixed = {s: float(np.max(np.abs(cell[:, sp.index(s)] - float(world.amounts0[s]))))
                 for s in world.species if s != p and s in sp}
        fixed_ok = all(v <= 2 * np.spacing(float(world.amounts0[s])) for s, v in fixed.items())
        errors.append((dt, err))
        results.append(CheckResult(f"ion@{dt:g}", err <= tau and err_n <= tau_n and fixed_ok, {
            "dt_s": dt, "tolerance_V": tau, "V_m_error_V": err, "tolerance_fmol": tau_n,
            "amount_error_fmol": err_n, "impermeant_change_fmol": fixed}))
    errors.sort(key=lambda x: -x[0])
    results.append(_ladder_order(errors, floor))
    return results


def check_records(d, world_name: str, inputs: dict) -> list:
    const = constants_from_block(inputs["constants"])
    world = inputs["R_records"]["worlds"][world_name]
    run, arr = read_bundle(d)
    if run["world"] != world_name:
        raise BundleError(f"{d}: expected world {world_name}, found {run['world']}")
    if "constants" in run:
        constants_from_block(run["constants"])
    sp = columns(run, "species", d)
    ref = records.event_records(world, const)
    t_ev = need(arr, "event_time_s", d)
    if t_ev.size != len(ref) or not np.allclose(t_ev, [e["time_s"] for e in ref], rtol=0,
                                                atol=TIME_ATOL_S):
        raise BundleError(f"{d}: event times {t_ev.tolist()} differ from the schedule")
    dose = need(arr, "dose_fmol", d)
    dG = need(arr, "dG_b_pJ", d)
    q = need(arr, "charge_C", d)
    z = records.valences(world)
    out = []
    for k, ev in enumerate(ref):
        bath = world["baths"][ev["bath"]]
        mag = max(abs(float(bath["volume_pL"]) * float(c)) for c in bath["declared_mM"].values())
        dose_ref = np.array([ev["dose_fmol"][s] for s in sp])
        dose_err = float(np.max(np.abs(dose[k] - dose_ref)))
        dose_tol = 8 * UNIT_ROUNDOFF * 2 * mag
        rel = abs(float(dG[k]) - ev["dG_b_pJ"]) / abs(ev["dG_b_pJ"])
        q_tol = 8 * UNIT_ROUNDOFF * float(const.faraday) * 1e-15 * \
            sum(abs(z[s]) * 2 * mag for s in sp)
        q_ok = abs(float(q[k]) - ev["charge_C"]) <= q_tol
        out.append(CheckResult(f"records_{world_name}@{ev['time_s']:g}",
                               dose_err <= dose_tol and rel <= DG_RTOL and q_ok, {
                                   "dose_error_fmol": dose_err, "dose_tolerance_fmol": dose_tol,
                                   "dG_relative_error": rel, "dG_rtol": DG_RTOL,
                                   "charge_C": float(q[k]), "charge_tolerance_C": q_tol}))
    return out


def check_K(d, world_name: str, inputs: dict, reference_supply=None, supply_tau=None) -> list:
    const = constants_from_block(inputs["constants"])
    world = inputs["R_records"]["worlds"][world_name]
    run, arr = read_bundle(d)
    sp = columns(run, "species", d)
    t = need(arr, "time_s", d)
    supply = need(arr, "supply_fmol", d)
    K_b = need(arr, "K_pJ", d)
    K = records.reconciliation_K(world, t, supply, const, species=sp)
    dmu = K["delta_mu_J_per_mol"]
    E = len(dmu) - 1
    mag = 1e-3 * sum(abs(v) for e in dmu for v in e.values()) * float(np.max(np.abs(supply)))
    tol = 64 * UNIT_ROUNDOFF * (E + 1) * mag + float(np.max(K["floor_pJ"]))
    err = float(np.max(np.abs(K_b - K["K_pJ"])))
    out = [CheckResult(f"K_{world_name}_own_supply", err <= tol, {
        "error_pJ": err, "tolerance_pJ": tol, "max_abs_K_pJ": float(np.max(np.abs(K_b)))})]
    if reference_supply is not None:
        rows = _rows_at(t, reference_supply["times_s"], d)
        Kr = records.reconciliation_K(world, reference_supply["times_s"],
                                      reference_supply["supply"], const)
        tol_r = 1e-3 * sum(abs(v) for e in dmu for v in e.values()) * 2 * supply_tau
        err_r = float(np.max(np.abs(K_b[rows] - Kr["K_pJ"])))
        out.append(CheckResult(f"K_{world_name}_reference_supply", err_r <= tol_r, {
            "error_pJ": err_r, "tolerance_pJ": tol_r}))
    return out


def run_roles(roles_path, tolerances=None, rows=None) -> tuple:
    """(status, report): run every requested row of a roles file."""
    roles_path = Path(roles_path)
    base = roles_path.parent
    try:
        roles = json.loads(roles_path.read_text())
        inputs = load_inputs()
        design = _design()
        results = []
        want = set(rows) if rows else {"faces", "ion", "records", "K"}

        def resolve(x):
            return [base / p for p in x] if isinstance(x, list) else base / x
        if "faces" in want:
            if "faces" not in roles:
                raise BundleError("role 'faces' is missing")
            results += check_faces(resolve(roles["faces"]), inputs, design, tolerances)
        if "ion" in want:
            if "ion" not in roles:
                raise BundleError("role 'ion' is missing")
            results += check_ion(resolve(roles["ion"]), inputs, design, tolerances)
        if "records" in want or "K" in want:
            fw = _faces_reference(inputs)
            iworld, iw = _ion_reference(inputs)
            fmol_per_V = float(10 ** 15 * iworld.capacitance_F / Constants().faraday)
            refs = {"W1": {"times_s": fw["times_s"], "supply": {"S": fw["supply_fmol"]}},
                    "W2": {"times_s": iw["times_s"], "supply": iw["supply_fmol"]}}
            for w in ("W1", "W2", "W3"):
                key = f"records_{w}"
                if key not in roles:
                    raise BundleError(f"role {key!r} is missing")
                d = resolve(roles[key])
                if "records" in want:
                    results += check_records(d, w, inputs)
                if "K" in want:
                    run, _ = read_bundle(d)
                    tau = None
                    if w in refs:
                        unit = "amount_fmol" if w == "W1" else "V_m_V"
                        ceil = _ceilings(design, w, unit)
                        tau = ceil.get(float(run["dt_s"]))
                        if w == "W2" and tau is not None:
                            tau *= fmol_per_V
                    results += check_K(d, w, inputs, refs.get(w) if tau else None, tau)
    except BundleError as exc:
        return 2, {"status": 2, "error": str(exc)}
    report = {"status": 0 if all(r.passed for r in results) else 1,
              "rows": [r.as_dict() for r in results]}
    return report["status"], jsonable(report)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--roles", required=True)
    r.add_argument("--tolerances")
    r.add_argument("--rows", help="comma-separated: faces, ion, records, K")
    r.add_argument("--out")
    args = ap.parse_args(argv)
    tol = json.loads(Path(args.tolerances).read_text()) if args.tolerances else None
    status, report = run_roles(args.roles, tol, args.rows.split(",") if args.rows else None)
    text = json.dumps(report, indent=1)
    if args.out:
        Path(args.out).write_text(text + "\n")
    print(text if status != 0 else json.dumps({"status": 0, "rows": len(report["rows"])}))
    return status


if __name__ == "__main__":
    sys.exit(main())
