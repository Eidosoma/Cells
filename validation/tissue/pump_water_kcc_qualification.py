"""Stationary qualification of resolved_pump_water@2 against the frozen W2 predictions.

For every arm of validation/tissue/pump_water_kcc_predictions.json (capacity x
steepness), the engine's stationary_continuation_analysis@1 on the arm's
resolved_pump_water@2 definition (pump_water_fixtures.with_symport on the
predictions' W1 heredity cell) is solved by Newton from each predicted state,
checked for step-map consistency, and classified by its dense spectrum. A
state is judged against its prediction with the bounds pinned in --protocol
(validation/tissue/pump_water_kcc_protocol.json, committed before the judged
run): volume, voltage, the route's cycle rate, step-map consistency and the
stability classification (the reference spectrum's sign).

Usage: python -m validation.tissue.pump_water_kcc_qualification --predictions FILE
       --protocol FILE --output DIR [--arms NAME ...]
"""

import argparse
import json
import time
import traceback
from pathlib import Path

import jax

jax.config.update("jax_enable_x64", True)

import numpy as np  # noqa: E402

from cells.core.specs import parse_spec  # noqa: E402
from validation.tissue import pump_water_fixtures as fixtures  # noqa: E402
from validation.tissue import pump_water_qualification as w1  # noqa: E402


def definition(predictions, arm):
    a = predictions["arms"][arm]
    return fixtures.with_symport(
        predictions["definition"],
        flux_mmol_L_h=a["flux_mmol_L_h"],
        steepness=a["parameters"]["steepness"],
    )


def guess(pb, reference):
    """Coordinates of a predicted state: its Na, K, M amounts, volume and steady gates."""
    from cells.analysis import stationary as sa
    from cells.models import surface_pump_v3

    base = sa._numpy(pb.base)
    ids = list(pb.spec.model.species_ids)
    volume = reference["volume_pL"]
    increment = np.array(base.amount_increment, dtype=float)
    for sid in ("Na", "K", "M"):
        k = ids.index(sid)
        increment[k, 0] = reference["concentration_mM"][sid] * volume - pb.p.amount_reference[k, 0]
    target, _ = surface_pump_v3.channel_kinetics(
        np.full(pb.p.channel_laws.shape, reference["membrane_voltage_V"]),
        np.asarray(pb.p.channel_laws),
        xp=np,
    )
    gate = np.where(np.asarray(pb.p.channel_gate_active), target, base.channel_gate)
    state = base._replace(
        amount_increment=increment,
        volume_increment_pL=np.array([volume - float(pb.p.volume[0])]),
        channel_gate=gate,
    )
    return pb.coordinates(state)


def judge_arm(predictions, arm, bounds):
    from cells.analysis import stationary as sa
    from cells.core.surface_pump_water_v2_spec import Control, control_values
    from cells.models import surface_pump_water_v2 as model

    spec = parse_spec(definition(predictions, arm))
    pb = sa.problem(spec)
    items = []
    for reference in predictions["arms"][arm]["states"]:
        item = dict(arm=arm, branch=reference["branch"])
        if not reference["converged"]:
            item.update(skipped="branch lost in the reference continuation", pass_=True)
            items.append(item)
            continue
        solution = sa.newton(pb, guess(pb, reference))
        item.update(converged=solution.converged, message=solution.message)
        if not solution.converged:
            item["pass_"] = False
            items.append(item)
            continue
        described = sa.describe(pb, solution.u)
        state, p, _ = pb.embed(solution.u)
        state, p = sa._numpy(state), sa._numpy(p)
        volume = float(p.volume[0] + state.volume_increment_pL[0])
        vm = described["membrane_voltage_V"]["membrane_0"]
        control = Control(*(v[0] for v in control_values(spec, [0.0])))
        cycles = float(model.readouts(state, control, p, xp=np).symport.cycles_fmol_s[0])
        consistency = sa.consistency(pb, solution.u)
        stability = sa.stability(pb, solution.u)
        reference_class = (
            "unstable" if reference["spectrum"]["leading_growth_rate_per_s"] > 0 else "stable"
        )
        errors = dict(
            volume_relative=abs(volume - reference["volume_pL"]) / reference["volume_pL"],
            voltage_V=abs(vm - reference["membrane_voltage_V"]),
            cycles_relative=abs(cycles - reference["route_cycles_fmol_s"])
            / abs(reference["route_cycles_fmol_s"]),
        )
        ok = (
            errors["volume_relative"] <= bounds["volume_relative"]
            and errors["voltage_V"] <= bounds["voltage_V"]
            and errors["cycles_relative"] <= bounds["cycles_relative"]
            and w1.consistent(consistency, bounds["step_map_correction"])
            and stability["classification"] == reference_class
        )
        item.update(
            volume_pL=volume,
            membrane_voltage_V=vm,
            route_cycles_fmol_s=cycles,
            errors=errors,
            classification=stability["classification"],
            reference_classification=reference_class,
            leading_growth_rate_per_s=stability["leading_growth_rate_per_s"],
            consistency=consistency,
            pass_=bool(ok),
        )
        items.append(item)
    return items


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--arms", nargs="*", default=[])
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    predictions = json.loads(Path(args.predictions).read_text())
    # A judged run takes the registered protocol or a registered backend variant of it; any
    # other file is marked a dry run (composite_l4_agreement.judged_protocol).
    from validation.tissue import composite_l4_agreement as agreement

    protocol, judged, acceptance = agreement.judged_protocol("w2", args.protocol)
    arms = args.arms or list(predictions["arms"])
    items = []
    try:
        for arm in arms:
            started = time.perf_counter()
            found = judge_arm(predictions, arm, protocol["stationary"])
            for item in found:
                item["seconds"] = time.perf_counter() - started
            items += found
            (out / "progress.json").write_text(json.dumps(items, indent=2, default=float) + "\n")
        result = dict(
            verdict="pass" if all(i["pass_"] for i in items) else "fail",
            dry_run=not judged,
            protocol=args.protocol,
            protocol_acceptance=acceptance,
            items=items,
        )
        (out / "w2-judge.json").write_text(json.dumps(result, indent=2, default=float) + "\n")
    except Exception:
        (out / "failure.json").write_text(
            json.dumps(dict(items=items, traceback=traceback.format_exc()), indent=2, default=float)
            + "\n"
        )
        raise


if __name__ == "__main__":
    main()
