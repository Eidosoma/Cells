"""FR-4's and FR-5's independent references, run on the declared worlds and from a start extract.

The FR-4/FR-5 runbook's step 4, and the qualification generator's `reference` parts
(validation/tissue/compartment_ph_qualification.py). The references (validation/compartment_ph:
ph_reference, R-closure and R-kinetic; transfer_reference, R-transfer) are used through their usage
note's API only (validation/compartment_ph/REFERENCES_USAGE.md): ph.World, Node, Buffer, Pump,
Constants and ph.integrate; tr.Start, TransferWorld, CargoRoute, Damage, Window, Condition and
tr.integrate. Nothing here changes them.

* **The worlds** are built from the engine's declared parameters
  (validation/compartment_ph/parameters: World, ARM_T, ARM_R), so the reference integrates the same
  declared values the engine's definitions carry (exact geometry and constants). The references'
  own transcriptions of §13 (ph.acceptance_world; transfer_arms_crosschecks.ARMS and its damage
  rates; tr.steady_start's X) are checked against them first (`consistency`): geometry within
  1e-5 relative (they typed six digits), the pump's capacity within 1e-4 (typed 8.3027e-3), the
  constants within 1e-9, every other value exactly. A disagreement refuses the stage.
* **FR-5's start** is the start extract (validation/compartment_ph/definitions.read_start): FR-4's
  engine checkpoint at 1800 s, passed as tr.Start(Heq_fmol, ions_fmol, X_fmol), each a (cytosol,
  lumen) pair, the ions as {Na, K, Cl} fmol (the usage note's `steady_start`); X at its declared
  start amounts, the same products of volume and concentration as definitions.fr5_world's. The
  stage refuses unless the reference's row 0 reproduces the extract's pH_c, pH_L and V_b within
  START_TOLERANCE: rounding, about 1e-15 in pH and 4e-14 V for V_b here (eps x sum |z n| x
  F 1e-15 / C_b), with a margin of about 25 x.
* **Records** every 1 s on the engine's grid (keyed by integer second): FR-4's 901 rows, FR-5's
  401. Each world also runs at rtol 1e-12 (the floor: the reference's own term).

Series (the names the engine's readouts carry too; units fmol, mM, V, pJ; transfers c to L):
pH_L, pH_c, V_b, Heq_L, Heq_c, K_L, K_c, cycles, work_pJ, heat_pJ, stored_change_pJ,
energy_residual_pJ, energy_flows_pJ (work plus heat), and for FR-5: X_L, X_c, d, f,
moved_X_transfer, moved_X_pore, moved_H_pore and heat_<route>_pJ.

Usage:
  python -m validation.tissue.compartment_ph_reference_stage fr4 --out DIR [--end S]
  python -m validation.tissue.compartment_ph_reference_stage fr5 --start START_JSON --out DIR
      [--arms T R] [--end S]
  python -m validation.tissue.compartment_ph_reference_stage self-check --out DIR
`self-check` checks the tools before the engine runs: a start extract from the reference's own
state at 1800 s (producer "reference_self_check", never a judged start), FR-5's references from
it, and the judge's arithmetic on their records, which must reproduce the references' readout
(arm T's ratio about 13.69 with its crossings near 73.081 and 326.882 s; arm R's release about
0.8736 with its crossings near 113.081 and 366.882 s). Each command writes DIR/<name>.json into a
new DIR.
"""

import argparse
import inspect
import json
import math
import sys
import time
from pathlib import Path

from validation.compartment_ph import definitions as defs
from validation.compartment_ph import ph_reference as ph
from validation.compartment_ph import transfer_arms_crosschecks as references_arms
from validation.compartment_ph import transfer_reference as tr
from validation.compartment_ph.parameters import ARM_R, ARM_T, F, R, World

RTOL, FLOOR_RTOL = 1e-11, 1e-12  # the references' declared rtol, and their floor's
START_TOLERANCE = dict(pH_c=1e-11, pH_L=1e-11, V_b_V=1e-11)
ARMS = {"T": ARM_T, "R": ARM_R}
CONTROLS = {"T": "f_equals_1", "R": "d_equals_0"}
START_TIME_S = 1800.0
READOUT = dict(  # the references' readout (931fb38a), for the self-check's report only
    T=dict(ratio=13.69, up_s=73.081, down_s=326.882),
    R=dict(released=0.8736, up_s=113.081, down_s=366.882))
ROUTE_HEATS = dict(pump="heat_pump_pJ", leak_H="heat_proton_leak_0_pJ",
                   pore_H="heat_proton_pore_0_pJ", ion_K="heat_bounding_0_K_pJ",
                   X_transfer="heat_cargo_transfer_0_pJ", X_pore="heat_cargo_pore_0_pJ")


# ------------------------------------------------------------------------ the worlds


def base_world(world=None, *, P_K=None, lumen_k_on=None):
    """R-closure's world (ph.World) from the engine's declared parameters.World."""
    w = world or World()

    def node(volume, conc, buffer, k_on):
        return ph.Node(volume, conc["pH"], {i: conc[i] for i in ph.IONS},
                       (ph.Buffer(buffer.total_mM, buffer.base_valence,
                                  buffer.mu_acid_minus_base_RT, k_on),))

    p_k = w.counterion_k_m_s if P_K is None else P_K
    fuel = w.fuel_mM
    return ph.World(
        constants=ph.Constants(F, R, w.temperature_K, w.standard_concentration_mM),
        cytosol=node(w.owner[0], w.cytosol_mM, w.cytosol_buffer,
                     w.cytosol_buffer.k_on_per_mM_s),
        lumen=node(w.lumen_volume_pL, w.lumen_mM, w.lumen_buffer,
                   w.lumen_buffer.k_on_per_mM_s if lumen_k_on is None else lumen_k_on),
        patch_area_m2=w.patch_area_m2,
        patch_capacitance_F=w.patch_capacitance_F,
        plasma_capacitance_F=w.specific_capacitance_F_m2 * w.owner[1],
        permeability_m_s={"K": p_k} if p_k > 0 else {},
        proton_permeability_m_s=w.proton_leak_m_s,
        pump=ph.Pump(n=w.pump_n, capacity_fmol_per_s=w.pump_capacity_fmol_s,
                     K_H_mM=w.km_proton_mM, K_ATP_mM=w.km_atp_mM, ATP_mM=fuel["ATP"],
                     ADP_mM=fuel["ADP"], Pi_mM=fuel["Pi"],
                     dG0_prime_J_per_mol=w.delta_g0_prime_J_mol))


def tr_start(extract, dw):
    """tr.Start from the extract: (cytosol, lumen) H_eq, {Na, K, Cl} and X (declared)."""
    cell = extract["nodes"][defs.CELL]["amounts_fmol"]
    lumen = extract["nodes"][defs.LUMEN]["amounts_fmol"]
    return tr.Start(
        Heq_fmol=(cell["H"], lumen["H"]),
        ions_fmol=({i: cell[i] for i in ph.IONS}, {i: lumen[i] for i in ph.IONS}),
        X_fmol=(dw.cargo_cytosol_mM * dw.base.owner[0],
                dw.cargo_lumen_mM * dw.base.lumen_volume_pL))


def arm_world(start, dw, control=None):
    """R-transfer's world for one arm (parameters.ARM_T or ARM_R), or its control."""
    t0, t1 = dw.injury_window_s
    damage = tr.Damage() if control == "d_equals_0" else tr.Damage(
        k_inj_per_s=dw.injury_rate_per_s, k_res_per_s=dw.resealing_rate_per_s,
        injure=(tr.Window(t0, t1),), reseal=(tr.Window(t1, math.inf),))
    routes = [tr.CargoRoute("transfer", dw.cargo_transfer_m_s,
                            conditioned=control != "f_equals_1")]
    if dw.pore_cargo_m_s > 0:
        routes.append(tr.CargoRoute("pore", dw.pore_cargo_m_s, damaged=True))
    return tr.TransferWorld(base=base_world(dw.base), start=start, cargo_routes=tuple(routes),
                            proton_pore_m_s=dw.pore_proton_m_s,
                            condition=tr.Condition(dw.ph50, dw.ph_slope), damage=damage)


def _close(ours, theirs, rel):
    return abs(ours - theirs) <= rel * max(abs(ours), abs(theirs))


def consistency(world=None):
    """The declared parameters against the references' own transcriptions of §13 and §13.2."""
    ours, theirs = base_world(world), ph.acceptance_world()
    items = {}

    def item(name, a, b, rel=0.0):
        items[name] = dict(ours=a, references=b, ok=bool(a == b if rel == 0.0 else
                                                         _close(a, b, rel)))

    c, d = ours.constants, theirs.constants
    item("faraday", c.faraday_C_per_mol, d.faraday_C_per_mol, 1e-9)
    item("gas", c.gas_J_per_mol_K, d.gas_J_per_mol_K, 1e-9)
    item("temperature", c.temperature_K, d.temperature_K)
    item("c0", c.standard_mM, d.standard_mM)
    for name in ("cytosol", "lumen"):
        a, b = getattr(ours, name), getattr(theirs, name)
        item(f"{name}.volume", a.volume_pL, b.volume_pL, 1e-5)
        item(f"{name}.pH0", a.pH0, b.pH0)
        item(f"{name}.ions", a.ions_mM, b.ions_mM)
        item(f"{name}.buffer.total", a.buffers[0].total_mM, b.buffers[0].total_mM)
        item(f"{name}.buffer.valence", a.buffers[0].base_valence, b.buffers[0].base_valence)
        item(f"{name}.buffer.delta_mu", a.buffers[0].delta_mu0_RT, b.buffers[0].delta_mu0_RT,
             1e-14)
        item(f"{name}.buffer.k_on", a.buffers[0].k_on_per_mM_per_s,
             b.buffers[0].k_on_per_mM_per_s)
    item("area", ours.patch_area_m2, theirs.patch_area_m2, 1e-5)
    item("patch_capacitance", ours.patch_capacitance_F, theirs.patch_capacitance_F, 1e-5)
    item("plasma_capacitance", ours.plasma_capacitance_F, theirs.plasma_capacitance_F, 1e-5)
    item("P_K", ours.permeability_m_s, theirs.permeability_m_s)
    item("P_H", ours.proton_permeability_m_s, theirs.proton_permeability_m_s)
    for field in ("n", "K_H_mM", "K_ATP_mM", "ATP_mM", "ADP_mM", "Pi_mM", "dG0_prime_J_per_mol",
                  "availability"):
        item(f"pump.{field}", getattr(ours.pump, field), getattr(theirs.pump, field))
    item("pump.capacity", ours.pump.capacity_fmol_per_s, theirs.pump.capacity_fmol_per_s, 1e-4)
    x_mM = inspect.signature(tr.steady_start).parameters["X_mM"].default
    dummy = tr.Start(Heq_fmol=(1.0, 1.0), ions_fmol=({}, {}), X_fmol=(1.0, 1.0))
    for arm, dw in ARMS.items():
        spec = references_arms.ARMS[arm]
        item(f"{arm}.P_X", dw.cargo_transfer_m_s, spec["P_X"])
        item(f"{arm}.P_pore_X", dw.pore_cargo_m_s, spec["P_pore_X"])
        item(f"{arm}.P_pore_H", dw.pore_proton_m_s, spec["P_pore_H"])
        item(f"{arm}.window", tuple(dw.injury_window_s), tuple(spec["window"]))
        item(f"{arm}.pH50", dw.ph50, references_arms.PH50)
        item(f"{arm}.hill", dw.ph_slope, references_arms.HILL)
        item(f"{arm}.horizon", dw.horizon_s, references_arms.T)
        damage = references_arms.arm_world(dummy, **spec).damage
        item(f"{arm}.k_inj", dw.injury_rate_per_s, damage.k_inj_per_s)
        item(f"{arm}.k_res", dw.resealing_rate_per_s, damage.k_res_per_s)
        item(f"{arm}.X_mM", (dw.cargo_cytosol_mM, dw.cargo_lumen_mM), tuple(x_mM))
    return dict(ok=all(v["ok"] for v in items.values()), items=items)


def check_consistency(world=None):
    report = consistency(world)
    if not report["ok"]:
        bad = sorted(k for k, v in report["items"].items() if not v["ok"])
        raise SystemExit(f"Refused: the declared parameters disagree with the references' own "
                         f"transcription of §13 at {bad}: tell the lead")
    return report


# ------------------------------------------------------------------------ records


def record_times(end_s):
    if abs(end_s - round(end_s)) > 1e-9:
        raise ValueError("the references record every whole second")
    return [float(t) for t in range(0, round(end_s) + 1)]


def _common(rows):
    return dict(
        pH_L=[r["pH_L"] for r in rows], pH_c=[r["pH_c"] for r in rows],
        V_b=[r["Vb"] for r in rows], Heq_L=[r["Heq_L"] for r in rows],
        Heq_c=[r["Heq_c"] for r in rows], K_L=[r["ions_L"]["K"] for r in rows],
        K_c=[r["ions_c"]["K"] for r in rows], cycles=[r["cycles"] for r in rows],
        work_pJ=[r["work_pJ"] for r in rows], heat_pJ=[r["heat_pJ"] for r in rows],
        stored_change_pJ=[r["stored_change_pJ"] for r in rows],
        energy_residual_pJ=[r["energy_residual_pJ"] for r in rows],
        energy_flows_pJ=[r["work_pJ"] + r["heat_pJ"] for r in rows])


def ph_series(run, times):
    return _common([run.at[t] for t in times])


def transfer_series(run, times):
    rows = [run.at[t] for t in times]
    out = _common(rows)
    out.update(X_L=[r["X_L"] for r in rows], X_c=[r["X_c"] for r in rows],
               d=[r["d"] for r in rows], f=[r["f"] for r in rows],
               moved_H_pore=[r["moved_fmol"]["H_pore"] for r in rows])
    for key in rows[0]["moved_fmol"]:
        if key.startswith("X_"):
            out[f"moved_{key}"] = [r["moved_fmol"][key] for r in rows]
    for key, name in ROUTE_HEATS.items():
        if key in rows[0]["heat_by_route_pJ"]:
            out[name] = [r["heat_by_route_pJ"][key] for r in rows]
    return out


def world_record(series, times, run, started):
    return dict(record_s=times, series=series, solver_steps=int(run.steps),
                seconds=time.perf_counter() - started)


# ------------------------------------------------------------------------ FR-4


def fr4_reference(world=None, *, end_s=None):
    """R-closure on FR-4's declared world (900 s), its floor, the P_K = 0 control (K1's reference
    side, reported) and R-kinetic with the lumen's k_on at 1e-3 /mM/s (K3: the closure departs)."""
    w = world or World()
    consistency_report = check_consistency(w)
    times = record_times(end_s or w.end_s)
    worlds = {}
    for name, built, kwargs in (
            ("declared", base_world(w), dict(rtol=RTOL)),
            ("floor", base_world(w), dict(rtol=FLOOR_RTOL)),
            ("control_k1", base_world(w, P_K=0.0), dict(rtol=RTOL)),
            ("kinetic_outside", base_world(w), dict(rtol=RTOL, kinetic=True,
                                                     k_on=(None, 1e-3)))):
        started = time.perf_counter()
        run = ph.integrate(built, times[-1], record=times, **kwargs)
        worlds[name] = world_record(ph_series(run, times), times, run, started)
    return dict(kind="reference", admitted=True, completed=True, record_s=times, worlds=worlds,
                consistency=consistency_report, rtol=RTOL, floor_rtol=FLOOR_RTOL)


# ------------------------------------------------------------------------ FR-5


def start_check(run, extract):
    """The reference's row 0 against the extract's readouts (refused beyond rounding)."""
    row = run.at[0.0]
    got = dict(pH_c=row["pH_c"], pH_L=row["pH_L"], V_b_V=row["Vb"])
    diff = {k: abs(got[k] - extract["readouts"][k]) for k in got}
    ok = all(diff[k] <= START_TOLERANCE[k] for k in diff)
    return dict(ok=ok, differences=diff, tolerance=START_TOLERANCE)


def fr5_reference(extract, *, arms=("T", "R"), end_s=None):
    """R-transfer from the extract for each arm, its control and its floor."""
    defs.check_start(extract)
    consistency_report = check_consistency()
    out = dict(kind="reference", admitted=True, completed=True, worlds={},
               consistency=consistency_report, rtol=RTOL, floor_rtol=FLOOR_RTOL,
               start=dict(extract_sha256=defs.start_sha256(extract),
                          producer=extract["producer"], time_s=extract["time_s"]),
               start_checks={})
    for arm in arms:
        dw = ARMS[arm]
        times = record_times(end_s or dw.horizon_s)
        start = tr_start(extract, dw)
        for name, control, rtol in ((arm, None, RTOL), (f"{arm}_control", CONTROLS[arm], RTOL),
                                    (f"{arm}_floor", None, FLOOR_RTOL)):
            started = time.perf_counter()
            run = tr.integrate(arm_world(start, dw, control), times[-1], record=times, rtol=rtol)
            check = start_check(run, extract)
            out["start_checks"][name] = check
            if not check["ok"]:
                raise SystemExit(f"Refused: the reference's row 0 ({name}) is not the extract's "
                                 f"start: {check['differences']}")
            out["worlds"][name] = world_record(transfer_series(run, times), times, run, started)
        out["record_s"] = times
    return out


def self_check_extract(world=None):
    """A start extract from R-closure's own state at 1800 s (producer "reference_self_check")."""
    w = world or World()
    started = time.perf_counter()
    run = ph.integrate(base_world(w), START_TIME_S, record=(START_TIME_S,), rtol=RTOL)
    r = run.at[START_TIME_S]
    declared = defs.fr4_world(w)
    nodes = {}
    for node in declared["model"]["cells"] + declared["model"]["extracellular"]:
        nodes[node["id"]] = dict(amounts_fmol=dict(node["initial_amount_fmol"]), charge_C=0.0)
    for node, suffix in ((defs.CELL, "c"), (defs.LUMEN, "L")):
        amounts = nodes[node]["amounts_fmol"]
        amounts["H"] = r[f"Heq_{suffix}"]
        amounts.update({i: r[f"ions_{suffix}"][i] for i in ph.IONS})
    c_b, c_p = w.patch_capacitance_F, w.specific_capacitance_F_m2 * w.owner[1]
    nodes[defs.LUMEN]["charge_C"] = -r["Vb"] * c_b
    nodes[defs.CELL]["charge_C"] = r["phi_c"] * c_p + r["Vb"] * c_b
    return defs.start_extract(
        producer="reference_self_check", nodes=nodes,
        readouts=dict(pH_c=r["pH_c"], pH_L=r["pH_L"], V_b_V=r["Vb"]), time_s=START_TIME_S,
        dt_s=None, source=dict(kind="reference", module="ph_reference", rtol=RTOL,
                               seconds=time.perf_counter() - started))


def self_check(out_dir):
    """The tools before the engine runs: the extract, FR-5's references, and the judge's arithmetic
    (crossings, mean rates, release) on the reference records against the references' readout."""
    from validation.tissue import compartment_ph_judge as judge

    extract = self_check_extract()
    references = fr5_reference(extract)
    report = dict(extract=extract, start_checks=references["start_checks"], arms={})
    for arm, dw in ARMS.items():
        part = references["worlds"][arm]
        part = dict(part, completed=True)
        budget = dw.x_budget_fraction * part["series"]["X_L"][0]
        a = dict(ph50=dw.ph50, injury_window_s=list(dw.injury_window_s),
                 conditioned_transfer="moved_X_transfer",
                 pore_transfer="moved_X_pore" if dw.pore_cargo_m_s > 0 else None)
        values = judge.claims(part, part, a, budget)["engine"]
        report["arms"][arm] = dict(claims=values, readout=READOUT[arm], budget_fmol=budget)
    path = Path(out_dir) / "self_check.json"
    path.write_text(json.dumps(dict(report, references=references), indent=1,
                               allow_nan=False) + "\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("fr4", "fr5", "self-check"))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--start", type=Path)
    parser.add_argument("--arms", nargs="+", default=["T", "R"], choices=["T", "R"])
    parser.add_argument("--end", type=float)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=False)
    if args.command == "fr4":
        result = fr4_reference(end_s=args.end)
    elif args.command == "fr5":
        if args.start is None:
            raise SystemExit("Refused: fr5 needs --start START_JSON (the engine's 1800 s extract)")
        result = fr5_reference(defs.read_start(args.start), arms=tuple(args.arms),
                               end_s=args.end)
    else:
        report = self_check(args.out)
        print(json.dumps({k: v for k, v in report["arms"].items()}, indent=1))
        return 0
    path = args.out / f"{args.command}_references.json"
    path.write_text(json.dumps(result, indent=1, allow_nan=False) + "\n")
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
