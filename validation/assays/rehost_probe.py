"""G0 re-host probe: the two-task fixture and its schedules on resolved_tissue@2 (RK4).

Validation-side adapter only (no engine change). It takes the raw definition dict that
an assay builds (two_task / unstimulated_readout ``definition``), reads only geometry,
kinetic constants, initial concentrations and the per-patch pump/channel/junction
availability schedules, and builds a Cells resolved_tissue@2 definition: resolved
capacitor field, Kv1.5 m/h channel per patch, kinetic Na/K pump, physical-time junction
gate. Nothing of the BETSE update order is recreated.

Approximations, all declared in the run record:
* Ca, P and M do not move (BETSE basic profile); they enter as fixed charge.
* Initial patch voltages are taken from a saved observation of the old fixture (the fixture
  is a synthetic concentration gradient, not a rest state); capacitor charges follow.
* Interior sites hold the fixture's exterior amounts; ring sites are reservoirs at the
  fixture's boundary potentials. Face electrodiffusion uses the fixture's free diffusivity.
* Junction area is the patch membrane area; one junction per partner pair.
"""

import copy
import hashlib
from pathlib import Path

import numpy as np

from cells.processes.electrochemistry import CHARGE_PER_FMOL

MOBILE = ("Na", "K", "Cl")
VM0_SOURCE = Path(
    "/mnt/workspaces/Cells/two-task-readout-20261012-01/evidence/cpu/assay-world-10000.npz"
)
CHANNEL_ID = "kv1p5_mh@1"


def initial_patch_voltage(path=VM0_SOURCE):
    data = np.load(path)
    sha = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return np.asarray(data["observed__vm"][0], dtype=float), sha


def _schedule(times, values):
    """Collapse repeated availabilities; keep the first entry at t=0."""
    out, last = [], None
    for t, v in zip(times, values, strict=True):
        if last is None or v != last:
            out.append({"time": float(t), "availability": float(v)})
            last = v
    return out


def resolved_definition(raw, *, dt, vm0, solver="rk4", extra_steps=8):
    """resolved_tissue@2 definition from a two-task style raw definition dict."""
    m, e = raw["model"], raw["experiment"]
    t = m["tissue"]
    species = m["species"]
    z = dict(zip(species, t["valence"], strict=True))
    index = {s: species.index(s) for s in MOBILE}
    owner = np.asarray(t["cell_owner"])
    site = np.asarray(t["outside_owner"])
    partner = np.asarray(t["partner"])
    area = np.asarray(t["membrane_area"], dtype=float)
    cvol_pL = np.asarray(t["cell_volume"], dtype=float) * 1e15
    spacing, height = float(t["spacing"]), float(t["height"])
    rows, cols = np.asarray(t["boundary_values"]).shape
    nsites = rows * cols
    cap_density = float(t["capacitance_density"])
    cell_c = np.asarray(m["initial"]["cell_concentration"], dtype=float)
    out_c = np.asarray(m["initial"]["outside_concentration"], dtype=float)
    boundary = np.asarray(t["boundary_concentration"], dtype=float)
    boundary_v = np.asarray(t["boundary_values"], dtype=float).ravel()
    ring = np.zeros((rows, cols), bool)
    ring[[0, -1], :] = ring[:, [0, -1]] = True
    ring = ring.ravel()
    site_pL = spacing**2 * height * 1e15
    q_patch = cap_density * area * np.asarray(vm0)  # inside-positive capacitor charge, C

    def mobile(amounts):
        return sum(z[s] * amounts[s] for s in MOBILE)

    cells = []
    for i in range(len(cvol_pL)):
        amt = {s: float(cell_c[index[s], i] * cvol_pL[i]) for s in MOBILE}
        q = float(q_patch[owner == i].sum())
        cells.append(
            dict(
                id=f"cell_{i}",
                volume_pL=float(cvol_pL[i]),
                initial_amount_fmol=amt,
                fixed_charge_equivalent_fmol=q / CHARGE_PER_FMOL - mobile(amt),
                initial_charge_C=q,
            )
        )
    sites = []
    for k in range(nsites):
        if ring[k]:
            amt = {s: float(boundary[index[s]] * site_pL) for s in MOBILE}
            q = 0.0
        else:
            amt = {s: float(out_c[index[s], k] * site_pL) for s in MOBILE}
            q = -float(q_patch[site == k].sum())
        sites.append(
            dict(
                id=f"site_{k}",
                volume_pL=site_pL,
                initial_amount_fmol=amt,
                fixed_charge_equivalent_fmol=q / CHARGE_PER_FMOL - mobile(amt),
                initial_charge_C=q,
                reservoir=bool(ring[k]),
                boundary_potential_V=float(boundary_v[k]),
            )
        )
    pump = {k: np.asarray(v, dtype=float) for k, v in m["pump"].items()}
    perm = np.asarray(t["membrane_permeability"], dtype=float)
    membranes, channels = [], []
    for p in range(len(area)):
        membranes.append(
            dict(
                id=f"membrane_{p}",
                inside=f"cell_{owner[p]}",
                outside=f"site_{site[p]}",
                area_m2=float(area[p]),
                capacitance_F=float(cap_density * area[p]),
                permeability_m_per_s={s: float(perm[index[s], p]) for s in MOBILE},
                law="constant_field@1",
                pump=dict(
                    id=f"pump_{p}",
                    law="nak_atp_mass_action_positive@1",
                    roles={"sodium": "Na", "potassium": "K"},
                    stoichiometry={"Na": -3, "K": 2},
                    capacity_fmol_per_s=float(pump["capacity_fmol_s"][p]),
                    km_na_mM=float(pump["km_na_mM"][p]),
                    km_k_mM=float(pump["km_k_mM"][p]),
                    km_atp_mM=float(pump["km_atp_mM"][p]),
                    metabolism=dict(
                        kind="maintained_chemical_reservoirs@1",
                        atp_mM=float(pump["atp_mM"][p]),
                        adp_mM=float(pump["adp_mM"][p]),
                        pi_mM=float(pump["pi_mM"][p]),
                        delta_g0_J_per_mol=float(pump["delta_g0_J_mol"][p]),
                    ),
                ),
            )
        )
        channels.append(
            dict(
                id=f"channel_{p}",
                membrane_id=f"membrane_{p}",
                species_id="K",
                kinetic_law=CHANNEL_ID,
                max_permeability_m_per_s=float(m["channel_permeability"][p]),
                abundance=1.0,
                initial_gate=[float(m["initial"]["m_gate"][p]), float(m["initial"]["h_gate"][p])],
            )
        )
    jperm = np.asarray(t["junction_permeability"], dtype=float)
    pairs = [(p, int(partner[p])) for p in range(len(area)) if p < partner[p]]
    junction_gate = m["junction"]
    junctions = [
        dict(
            id=f"junction_{a}_{b}",
            sender=f"cell_{owner[a]}",
            receiver=f"cell_{owner[b]}",
            area_m2=float(0.5 * (area[a] + area[b])),
            permeability_m_per_s={s: float(jperm[index[s], a]) for s in MOBILE},
            law="constant_field@1",
            gate=dict(
                law="betse_rate_junction_relaxation@1",
                threshold_voltage_V=float(junction_gate["threshold_voltage_V"][a]),
                minimum_open_fraction=float(junction_gate["minimum_open_fraction"][a]),
                initial_gate=float(m["initial"]["junction_open"][a]),
            ),
        )
        for a, b in pairs
    ]
    diff = np.asarray(t["diffusivity"], dtype=float)
    grid = np.arange(nsites).reshape(rows, cols)
    senders = np.r_[grid[:, :-1].ravel(), grid[:-1, :].ravel()]
    receivers = np.r_[grid[:, 1:].ravel(), grid[1:, :].ravel()]
    faces = []
    for a, b in zip(senders, receivers, strict=True):
        if ring[a] and ring[b]:
            continue
        faces.append(
            dict(
                id=f"face_{a}_{b}",
                sender=f"site_{a}",
                receiver=f"site_{b}",
                area_m2=spacing * height,
                length_m=spacing,
                diffusivity_m2_per_s={
                    s: float(0.5 * (diff[index[s]].ravel()[a] + diff[index[s]].ravel()[b]))
                    for s in MOBILE
                },
                law="logmean_electrodiffusion@1",
            )
        )
    # Schedules: the assay's per-patch change arrays at their (physical) times.
    changes = e["changes"]
    times = [c["time"] for c in changes]
    pump_c = [
        dict(pump_id=f"pump_{p}", schedule=_schedule(times, [c["pump"][p] for c in changes]))
        for p in range(len(area))
    ]
    chan_c = [
        dict(
            channel_id=f"channel_{p}", schedule=_schedule(times, [c["channel"][p] for c in changes])
        )
        for p in range(len(area))
    ]
    junc_c = [
        dict(
            junction_id=f"junction_{a}_{b}",
            schedule=_schedule(times, [c["junction"][a] for c in changes]),
        )
        for a, b in pairs
    ]
    mem_c = [
        dict(membrane_id=f"membrane_{p}", schedule=[{"time": 0.0, "availability": 1.0}])
        for p in range(len(area))
    ]
    end = float(e["end_time"])
    steps = int(round(end / dt))
    return dict(
        schema_version=1,
        model=dict(
            id="resolved_tissue@2",
            temperature_K=float(t["temperature"]),
            species=[dict(id=s, valence=int(z[s])) for s in MOBILE],
            cells=cells,
            extracellular=sites,
            membranes=membranes,
            junctions=junctions,
            faces=faces,
            closure=dict(
                law="resolved_capacitor_components_current_continuity@1", gauge_reference=None
            ),
            channels=channels,
        ),
        experiment=dict(
            end_time=end,
            observation_times=[float(x) for x in e["observation_times"]],
            membrane_controls=mem_c,
            junction_controls=junc_c,
            channel_controls=chan_c,
            pump_controls=pump_c,
        ),
        execution=dict(
            dt=float(dt),
            capacity=len(cells),
            extracellular_capacity=len(sites),
            membrane_capacity=len(membranes),
            edge_capacity=len(junctions),
            face_capacity=len(faces),
            channel_capacity=len(channels),
            backend="cpu",
            jit=True,
            precision="float64",
            solver=solver,
            field_solver="capacitive_reduction_gauged_damped_newton@1",
            max_steps=steps + extra_steps,
            max_trace_bytes=2**36,
            material_balance_atol_fmol={s: 2e-11 for s in MOBILE},
        ),
    )


def cell_voltage(raw, voltage_V, readout_cell_ids):
    """Area-weighted voltage per named cell (same weights as VoltageReadout)."""
    owner = np.asarray(raw["model"]["tissue"]["cell_owner"])
    area = np.asarray(raw["model"]["tissue"]["membrane_area"])
    voltage = np.asarray(voltage_V)
    cols = []
    for cid in readout_cell_ids:
        mask = owner == cid - 1
        cols.append(voltage[..., mask] @ (area[mask] / area[mask].sum()))
    return np.stack(cols, axis=-1)


def with_dt(definition, dt):
    d = copy.deepcopy(definition)
    d["execution"]["dt"] = float(dt)
    d["execution"]["max_steps"] = int(round(d["experiment"]["end_time"] / dt)) + 8
    return d


# --- G0 driver -------------------------------------------------------------------------

READOUT_CELLS = (1, 2, 3, 4, 5, 6, 7)
READOUT_US = (40, 48, 64)


def shorten(raw, end_s):
    """Same schedule truncated at end_s (stability sweeps only)."""
    d = copy.deepcopy(raw)
    d["experiment"]["end_time"] = end_s
    d["experiment"]["observation_times"] = [end_s]
    d["experiment"]["changes"] = [c for c in d["experiment"]["changes"] if c["time"] < end_s]
    return d


def run_case(raw, dt, vm0, *, readout_times_s=None):
    """Run one raw definition at dt; returns (record, cell voltages at the readout times)."""
    from time import perf_counter

    from cells.core.runner import run
    from cells.core.specs import parse_spec

    spec = parse_spec(resolved_definition(raw, dt=dt, vm0=vm0))
    started = perf_counter()
    result = run(spec)
    wall = perf_counter() - started
    obs = result.observations
    times = np.asarray(obs.times)
    volt = np.asarray(obs.membrane_voltage_V)
    pick = times if readout_times_s is None else np.asarray(readout_times_s)
    index = [int(np.argmin(abs(times - t))) for t in pick]
    assert np.allclose(times[index], pick, rtol=0, atol=1e-15)
    features = cell_voltage(raw, volt[index], READOUT_CELLS)
    steps = int(round(raw["experiment"]["end_time"] / dt))
    record = dict(
        dt_s=dt,
        steps=steps,
        wall_s=wall,
        wall_per_step_s=wall / steps,
        max_balance_error_fmol=float(result.diagnostics["max_balance_error_fmol"]),
        charge_residual_C_max=float(np.max(np.abs(np.asarray(obs.charge_residual_C)))),
        finite=bool(np.isfinite(volt).all()),
    )
    return record, features


def main(argv=None):
    import argparse
    import json

    import jax

    jax.config.update("jax_enable_x64", True)
    from validation.assays import two_task
    from validation.assays import unstimulated_readout as unstimulated
    from validation.betse.emulator.rehost import moved

    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["stability", "refine", "panel"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--dts", type=float, nargs="+", required=True)
    ap.add_argument("--end-us", type=float, default=64.0)
    ap.add_argument("--only", default="", help="case-name prefix filter")
    args = ap.parse_args(argv)
    base = json.load(open(moved("configs/betse_spatial_junction.json")))
    vm0, vm0_sha = initial_patch_voltage()
    tt, ur = two_task.protocol(), unstimulated.protocol()
    pick = lambda rows, arm: next(  # noqa: E731
        r
        for r in rows
        if r["arm"] == arm
        and r["preparation"] == "calibration_low"
        and r["location"] == 0
        and r["timing"] == 0
    )
    raws = {
        "two_task_joint": two_task.definition(base, pick(two_task.cases(tt), "joint"), "cpu", tt),
        "two_task_no_cue": two_task.definition(base, pick(two_task.cases(tt), "no_cue"), "cpu", tt),
        "unstim_joint": unstimulated.definition(
            base, pick(unstimulated.cases(ur), "joint"), "cpu", ur
        ),
        "unstim_no_cue": unstimulated.definition(
            base, pick(unstimulated.cases(ur), "no_cue"), "cpu", ur
        ),
    }
    if args.mode == "panel":
        rows = two_task.cases(tt)
        raws = {
            f"panel_L{loc}T{tim}": two_task.definition(
                base,
                next(
                    r
                    for r in rows
                    if r["arm"] == "joint"
                    and r["preparation"] == "calibration_low"
                    and r["location"] == loc
                    and r["timing"] == tim
                ),
                "cpu",
                tt,
            )
            for loc in (0, 1)
            for tim in (0, 1)
        }
    if args.mode == "stability":
        names = ["two_task_no_cue", "two_task_joint"]
        raws = {n: shorten(raws[n], args.end_us * 1e-6) for n in names}
    out = dict(vm0_source=str(VM0_SOURCE), vm0_sha256=vm0_sha, mode=args.mode, runs=[])
    for dt in args.dts:
        for name, raw in raws.items():
            if not name.startswith(args.only):
                continue
            entry = dict(case=name, dt_s=dt)
            try:
                times = None if args.mode == "stability" else [t * 1e-6 for t in READOUT_US]
                record, features = run_case(raw, dt, vm0, readout_times_s=times)
                entry |= record | dict(status="ok", features_V=features.tolist())
            except Exception as error:  # a refusal or instability is a result
                entry |= dict(status="failed", error=type(error).__name__ + ": " + str(error)[:300])
            out["runs"].append(entry)
            print(json.dumps({k: v for k, v in entry.items() if k != "features_V"}), flush=True)
            json.dump(out, open(args.out, "w"), indent=1)
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
