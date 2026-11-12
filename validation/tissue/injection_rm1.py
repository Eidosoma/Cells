"""First acceptance of electrode_current_injection@1: Rm1 on the uncleaved egg (PROPOSED).

docs/PUMP_COMPOSITE_V2_DESIGN.md §4.1. The engine egg is R-full's own uncleaved egg:
cleft_egg_reference.build(declared inputs, default values, p_old = the record's p_old_m_s)
from validation/division/j1_declared_inputs.json and j1_prediction_of_record.json, written
as a resolved_pump_tissue@3 definition. Only egg_scale_smoke's skeleton is reused (cell, held
bath, one old membrane). The pulse Rm1 is a large-signal chord, so R-full calibrates P_old on
it; egg_scale_smoke's small-signal P would put a perfect engine about 1 kOhm off.

One electrode follows J1's registered protocol (rm_definition): +/-3e-8 A pulses of 1.2 s
every 10 s, alternating from t = 0, carried by K and Cl in R-full's own fractions (Pulses
carrier_K and carrier_Cl, read from the same declared field).
Rm1 = (|dV_0| + |dV_1|) / (2 x 3e-8 A), with dV_k = V(t_k + 1.0 s) - V(t_k).

Acceptance (the lead registers it before the judged run):
|Rm1 - rm1_ohm of the record| <= 3 x (engine step term + R-full's reference term).
* Engine step term: |Rm1(1 ms) - Rm1(0.5 ms)|, from this development dt study.
* Reference term: R-full's Rm1 under its record's integrator variants (Radau rtol 1e-8, BDF,
  LSODA), maximum deviation from the record.

Actions:
  compare --output FILE          the engine definition against R-full's egg, field by field
  study --dt S --output FILE     a development engine run, giving Rm1 and its V samples
  reference --output FILE        R-full's Rm1 reference term
  judge --output FILE            the judged run: a registered protocol (status beginning
                                 "registered") and a clean execution snapshot only
"""

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    for entry in (ROOT / "src", ROOT):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))

LAW = "electrode_current_injection@1"
STATUS = "PROPOSED first acceptance of electrode_current_injection@1; not judged."
RECORD = ROOT / "validation/division/j1_prediction_of_record.json"
PROTOCOL = ROOT / "validation/tissue/injection_rm1_protocol.json"


def rfull():
    """(R-full's uncleaved egg with the record's P_old, the record, the declared inputs)."""
    from validation.division import cleft_egg_reference as ref

    d = ref.load_declared()
    record = json.loads(RECORD.read_text())
    egg = ref.build(d, ref.scalar_values(d), p_old=float(record["p_old_m_s"]))
    return egg, record, d


def definition(dt=1e-3):
    """The engine egg (R-full's) with one electrode and pulses 0 and 1, as a composition."""
    from cells.core import pump_composite_spec as cs
    from cells.processes.electrochemistry import CHARGE_PER_FMOL
    from validation.division import cleft_egg_reference as ref
    from validation.tissue import egg_scale_smoke as smoke

    egg, _, d = rfull()
    rm, p = d["rm_definition"], egg.pulses

    def grid(t):  # Every scheduled time an exact multiple of dt.
        return round(t / dt) * dt

    end = grid(p.onset(1) + p.sample_s + 0.8)
    raw, _ = smoke.egg_definition(end_time=end, dt=dt, anchor="consistent", observe_every=1.0)
    model = raw["model"]
    ids, z = list(ref.SPECIES), dict(zip(ref.SPECIES, ref.Z, strict=True))
    volume_pL = egg.cytosol_volume_m3 * 1e15
    inside = {s: c * volume_pL for s, c in zip(ids, egg.cytosol_mM, strict=True)}
    _, _, v0 = ref.initial_state(egg)  # R-full's zero-current potential.
    # The background as egg_scale_smoke forms it, with the engine's charge per fmol.
    background = egg.old_capacitance_F * v0 / CHARGE_PER_FMOL - math.fsum(
        z[s] * inside[s] for s in ids
    )
    model["temperature_K"] = egg.temperature_K
    model["species"] = [dict(id=s, valence=z[s]) for s in ids]
    cell = model["cells"][0]
    cell.update(
        volume_pL=volume_pL,
        initial_amount_fmol=inside,
        fixed_charge_equivalent_fmol=background,
        initial_charge_C=CHARGE_PER_FMOL
        * math.fsum((background, *(z[s] * inside[s] for s in ids))),
    )
    bath = model["extracellular"][0]
    bath_mM = dict(zip(ids, egg.bath_mM, strict=True))
    bath.update(
        initial_amount_fmol={s: c * bath["volume_pL"] for s, c in bath_mM.items()},
        fixed_charge_equivalent_fmol=-math.fsum(z[s] * bath_mM[s] * bath["volume_pL"] for s in ids),
    )
    membrane = model["membranes"][0]
    membrane.update(
        area_m2=egg.old_area_m2,
        capacitance_F=egg.old_capacitance_F,
        permeability_m_per_s={s: egg.p_old * w for s, w in zip(ids, egg.old_relative, strict=True)},
    )
    raw["experiment"]["observation_times"] = [
        grid(t) for k in (0, 1) for t in (p.onset(k), p.onset(k) + p.sample_s)
    ]
    out = cs.frozen_definition(raw)
    carriers = dict(rm["injected_carrier_fractions"])
    assert (carriers["K"], carriers["Cl"]) == (p.carrier_K, p.carrier_Cl)  # Same declared field.
    out["model"]["operators"] = [
        dict(law=LAW, electrodes=[dict(cell_id=cell["id"], carriers=carriers)])
    ]
    schedule = [
        dict(time=grid(t), current_A=current)
        for k in (0, 1)
        for t, current in (
            (p.onset(k), p.sign(k) * p.amplitude_A),
            (p.onset(k) + p.duration_s, 0.0),
        )
    ]
    out["experiment"]["injection_controls"] = [dict(cell_id=cell["id"], schedule=schedule)]
    return out


def compare(raw):
    """Field-by-field differences of the engine definition from R-full's egg (empty: none)."""
    from validation.division import cleft_egg_reference as ref

    egg, _, _ = rfull()
    model, ids = raw["model"], list(ref.SPECIES)
    cell, bath, membrane = model["cells"][0], model["extracellular"][0], model["membranes"][0]
    volume = cell["volume_pL"]
    rows = dict(
        temperature_K=(model["temperature_K"], egg.temperature_K),
        cytosol_volume_m3=(volume * 1e-15, egg.cytosol_volume_m3),
        cytosol_mM_activity_basis=(
            [cell["initial_amount_fmol"][s] / volume for s in ids],
            list(egg.cytosol_mM),
        ),
        bath_mM_activity_basis=(
            [bath["initial_amount_fmol"][s] / bath["volume_pL"] for s in ids],
            list(egg.bath_mM),
        ),
        old_area_m2_folded=(membrane["area_m2"], egg.old_area_m2),
        old_capacitance_F=(membrane["capacitance_F"], egg.old_capacitance_F),
        permeability_m_s=(
            [membrane["permeability_m_per_s"][s] for s in ids],
            [egg.p_old * w for w in egg.old_relative],
        ),
        old_relative=(
            [membrane["permeability_m_per_s"][s] / egg.p_old for s in ids],
            list(egg.old_relative),
        ),
    )
    out = {}
    for name, (engine, reference) in rows.items():
        a, b = (list(v) if isinstance(v, list | tuple) else [v] for v in (engine, reference))
        worst = max(abs(x - y) / max(abs(y), 1e-300) for x, y in zip(a, b, strict=True))
        out[name] = dict(engine=engine, rfull=reference, max_relative_difference=worst)
    return out


def rm1_from(voltages, amplitude):
    v0, v0b, v1, v1b = voltages
    return (abs(v0b - v0) + abs(v1b - v1)) / (2 * amplitude)


def study(dt):
    """A development engine run: Rm1 and the V samples (run on CPU, not judged)."""
    import time

    import jax
    import numpy as np

    jax.config.update("jax_enable_x64", True)
    from cells.core.runner import run
    from cells.core.specs import parse_spec

    raw = definition(dt)
    spec = parse_spec(raw)
    started = time.perf_counter()
    result = run(spec)
    times = list(raw["experiment"]["observation_times"])
    v = np.asarray(result.observations.membrane_voltage_V)[:, 0]
    egg, record, _ = rfull()
    rm1 = rm1_from([float(x) for x in v], egg.pulses.amplitude_A)
    return dict(
        dt=dt,
        times=times,
        voltages_V=[float(x) for x in v],
        rm1_ohm=rm1,
        record_rm1_ohm=record["rm1_ohm"],
        difference_ohm=rm1 - record["rm1_ohm"],
        wall_s=time.perf_counter() - started,
        diagnostics={k: v for k, v in result.diagnostics.items() if k.startswith("max_")},
    )


def reference_term():
    """R-full's Rm1 under the record's integrator variants, against the record."""
    from validation.division import cleft_egg_reference as ref

    egg, record, d = rfull()
    pair = tuple(d["rm_definition"]["rm1_pulse_pair"])
    rows = {}
    for label, kwargs in (
        ("radau_rtol_1e-10", {}),
        ("radau_rtol_1e-8", dict(rtol=1e-8)),
        ("bdf_rtol_1e-10", dict(method="BDF")),
        ("lsoda_rtol_1e-10", dict(method="LSODA")),
    ):
        rm1 = ref.rm_at(egg, pair, **kwargs)[0]
        rows[label] = dict(rm1_ohm=rm1, d_rm1_ohm=rm1 - record["rm1_ohm"])
    variants = [r["d_rm1_ohm"] for k, r in rows.items() if k != "radau_rtol_1e-10"]
    return dict(
        record_rm1_ohm=record["rm1_ohm"],
        rows=rows,
        reference_term_ohm=max(abs(x) for x in variants),
    )


def judged_run_refusal(protocol, root=ROOT):
    """Why a judged run may not start (None: it may): an unregistered protocol, or a
    source that is not a clean execution snapshot (validation/source_snapshot.py)."""
    import hashlib

    status = protocol.get("status")
    if not (isinstance(status, str) and status.startswith("registered")):
        return "the Rm1 protocol is not registered (its status does not begin 'registered')"
    manifest = Path(root) / "SNAPSHOT.json"
    if not manifest.exists():
        return "a judged run comes from a clean execution snapshot of main, not a checkout"
    snapshot = json.loads(manifest.read_text())
    clean = snapshot.get("patch_sha256") == hashlib.sha256(b"").hexdigest()
    if snapshot.get("status") != "complete" or not clean:
        return "the execution snapshot is incomplete or carries uncommitted changes"
    return None


def judge(protocol_path=PROTOCOL):
    """The judged run of a registered protocol, at its judged dt, with its verdict."""
    protocol = json.loads(Path(protocol_path).read_text())
    refusal = judged_run_refusal(protocol)
    if refusal:
        raise SystemExit("Refused: " + refusal)
    result = study(protocol["judged_dt_s"])
    difference = result["rm1_ohm"] - protocol["reference_rm1_ohm"]
    snapshot = json.loads((ROOT / "SNAPSHOT.json").read_text())
    return dict(
        protocol=str(protocol_path),
        protocol_status=protocol["status"],
        source_revision=snapshot["git_revision"],
        rm1_ohm=result["rm1_ohm"],
        reference_rm1_ohm=protocol["reference_rm1_ohm"],
        difference_ohm=difference,
        tolerance_ohm=protocol["tolerance_ohm"],
        verdict="pass" if abs(difference) <= protocol["tolerance_ohm"] else "fail",
        run=result,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("compare", "study", "reference", "judge"):
        one = sub.add_parser(name)
        one.add_argument("--output", type=Path, required=True)
        if name == "study":
            one.add_argument("--dt", type=float, required=True)
    args = parser.parse_args(argv)
    if args.action == "compare":
        raw = definition()
        result = dict(status=STATUS, differences=compare(raw), definition=raw)
    elif args.action == "study":
        result = dict(status=STATUS + " Development dt study.", **study(args.dt))
    elif args.action == "reference":
        result = dict(status=STATUS, **reference_term())
    else:
        result = judge()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=1, default=float) + "\n")
    print(args.action, "written", args.output)


if __name__ == "__main__":
    main()
