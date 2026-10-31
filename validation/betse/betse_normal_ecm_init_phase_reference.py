"""Fresh stdlib INIT setup/NaK/material/gate/GRN/mechanics/field conditionals.

Independent arithmetic starts from each archived actual incoming parent. There
is no independently carried phase trajectory or inherited qualification credit.
"""

import copy
from decimal import Decimal, localcontext

from validation.betse import betse_mechanics_join_reference as mechanics
from validation.betse import betse_normal_ecm_catalog_join_reference as catalog
from validation.betse import betse_normal_ecm_event_join_reference as network
from validation.betse import betse_normal_ecm_init_phase_reference_models as models
from validation.betse import betse_normal_pump_join_reference as pump

d, numbers, serial = catalog.d, catalog.numbers, catalog.serial


def encoded(value):
    if isinstance(value, Decimal):
        return dict(decimal=str(value))
    if isinstance(value, dict):
        return {k: encoded(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [encoded(v) for v in value]
    return value


def retain_raw(retain, mode, value, precision):
    if retain is not None:
        retain(
            mode + "-decimal-" + str(precision), dict(precision=precision, payload=encoded(value))
        )


def phase_clock(raw):
    """Independent binary64 count/linspace/sampling reconstruction, including N0/N1."""
    count = int(raw["init_total_s"] / raw["init_dt_s"])
    end = count * raw["init_dt_s"]
    labels = (
        []
        if count == 0
        else [0.0]
        if count == 1
        else [i * (end / (count - 1)) for i in range(count)]
    )
    if count > 1:
        labels[-1] = end
    stride = raw["init_sampling_s"] / raw["init_dt_s"]
    sample = []
    index = 0
    while index < count - stride:
        index = int(index + stride)
        sample.append(index)
    return dict(source_times_s=labels, call_index=0, material_dt_sum_s=0.0), sample


def setup_equations(inputs):
    raw = inputs["setup_return"]
    initial, u, level = (
        numbers(raw["static_diffusion_before"]),
        numbers(raw["static_uniforms"]),
        d(raw["static_level"]),
    )
    potassium = inputs["ion_ids"].index("K")
    current = copy.deepcopy(initial)
    current[potassium] = [
        (1 + level * draw) * value for draw, value in zip(u, initial[potassium], strict=True)
    ]
    return dict(
        Dm_base=initial,
        Dm_scheduled=[[Decimal(0) for _ in row] for row in initial],
        Dm_cells=current,
        channel_noise_factor=u,
        factor=[1 + level * draw for draw in u],
        setup_draw_count=1,
        event_fire_calls=0,
        dynamic_noise_calls=0,
        RNG_algorithm_credit=False,
        source_phase="INIT",
        legacy_run_sim=False,
    )


def nak_equations(inputs, refinement):
    """Reuse the independent pump equations per ECM face with its actual outside gather."""
    raw = inputs["definition"]
    cd = raw["environment_geometry_definition"]["current_definition"]
    geom = catalog.geometry(
        raw["environment_geometry_definition"], precision=100 if refinement == 1 else 160
    )
    v = numbers(inputs["values_before"])
    names, mapping = cd["ions"]["ids"], geom["membrane_to_grid"]
    m = len(v["voltage_V"])
    flux = [[Decimal(0)] * m for _ in names]
    proxy, gross, proxy_gross, arithmetic = [], [[Decimal(0)] * m for _ in names], [], None
    for j, site in enumerate(mapping):
        params = inputs["parameters"]
        declaration = dict(
            pump_definition=dict(
                sodium_id="Na",
                potassium_id="K",
                maintained={k: params[k] for k in ("cATP", "cADP", "cPi")},
                kinetics={k: params[k] for k in ("KmNK_Na", "KmNK_K", "KmNK_ATP", "deltaGATP")},
            ),
            pump_packet=dict(
                alpha_NaK=inputs["packet"]["alpha_NaK"],
                block=[inputs["packet"]["block"][j]],
                rho_pump=[inputs["packet"]["rho_pump"][j]],
            ),
            definition=dict(
                ions=dict(ids=names),
                geometry=dict(boundary=[inputs["boundary"][j]]),
                parameters=dict(
                    F_C_mol=cd["parameters"]["F_C_mol"],
                    R_J_mol_K=raw["parameters"]["R_J_mol_K"],
                    cluster_open=inputs["cluster_open"],
                ),
            ),
            incoming_rate_proxy_mol_m2_s=[
                inputs["incoming_rate"]["value"][j] if inputs["incoming_rate"]["present"] else 0.0
            ],
        )
        values = dict(
            membrane_mol_m3=[[row[j]] for row in v["membrane_mol_m3"]],
            bath_mol_m3=[row[site] for row in v["environment_mol_m3"]],
            voltage_V=[v["voltage_V"][j]],
            membrane_flux_mol_m2_s=[[Decimal(0)] for _ in names],
        )
        incoming_gross = {
            k: [[abs(x) for x in row] for row in value]
            if value and isinstance(value[0], list)
            else [abs(x) for x in value]
            for k, value in values.items()
        }
        answer = pump.pump_phase(
            declaration,
            values,
            incoming_gross,
            dict(runtime_temperature_K=inputs["runtime_temperature_K"]),
            refinement,
        )
        for i in range(len(names)):
            flux[i][j] = answer["values"]["storage_after_mol_m2_s"][i][0]
            gross[i][j] = answer["flux_gross"][i][0]
        proxy.append(answer["values"]["rate_proxy_after_mol_m2_s"][0])
        proxy_gross.append(answer["proxy_gross"][0])
        if answer["arithmetic"] is not None:
            if arithmetic is None:
                arithmetic = {key: [] for key in answer["arithmetic"]}
            for key, values in answer["arithmetic"].items():
                arithmetic[key].extend(
                    [j]
                    if key == "zero_denominator_indices" and values
                    else []
                    if key == "zero_denominator_indices"
                    else values
                )
    return dict(
        arithmetic=arithmetic,
        applied_flux=flux,
        raw_rate_proxy=proxy,
        flux_gross=gross,
        proxy_gross=proxy_gross,
    )


def evaluate(inputs, *, refinement, retain):
    if refinement not in (1, 2):
        raise ValueError("Require the two predeclared independent precision forms")
    precision = 100 if refinement == 1 else 160
    mode = inputs.get("mode")
    with localcontext() as context:
        context.prec = precision
        if mode == "setup":
            answer = setup_equations(inputs)
            retain_raw(retain, mode, answer, precision)
            result = serial(answer)
        elif mode == "nak":
            answer = nak_equations(inputs, refinement)
            retain_raw(retain, mode, answer, precision)
            result = serial(answer)
        elif mode == "channels":
            answer = models.channel_sequence(inputs, refinement=refinement)
            retain_raw(retain, mode, answer, precision)
            result = serial(answer)
        elif mode == "material":
            adapted = copy.deepcopy(inputs)
            # The outgoing model flux is never fed back as its own reference.
            predicted = nak_equations(inputs["nak_before"], refinement)
            adapted["steps"][0]["supplied_pump_membrane_flux_mol_m2_s"] = predicted["applied_flux"]
            adapted["calcium"]["Ca_index"] = inputs["definition"][
                "environment_geometry_definition"
            ]["current_definition"]["ions"]["ids"].index("Ca")
            result = models.material_model(
                adapted,
                refinement=refinement,
                retain_decimal=lambda value: retain_raw(retain, mode, value, precision),
            )
        elif mode == "mechanics":
            result = mechanics.evaluate(
                {k: inputs[k] for k in ("definition", "initial", "steps")},
                refinement=refinement,
                retain=retain,
            )
        else:
            # Common field, calcium, chemistry and cold constructor equations;
            # no source namespace is patched or old answer file reused.
            result = network.evaluate(inputs, refinement=refinement)
            if mode == "cold_initialization":
                result["clock"], result["sample_indices"] = phase_clock(inputs["time_profile"])
    result.update(
        mode=mode,
        decimal_precision=precision,
        carried_reference_forms=0,
        fresh_conditional_reference=True,
        independent_trajectory=False,
        physical_global_conservation_credit=False,
        source_phase="INIT",
        legacy_run_sim=False,
    )
    return result


def main():
    import argparse
    import builtins
    import hashlib
    import importlib.abc
    import json
    import sys
    from pathlib import Path

    from validation.betse.betse_normal_channel_join_runtime import inventory
    from validation.betse.betse_normal_ecm_init_phase_capture import record_failure

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--refinement", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    blocked = {"cells", "betse", "numpy", "scipy", "jax", "jaxlib"}
    original = builtins.__import__

    def guarded(name, *values, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("Independent event/mechanics reference import denied: " + name)
        return original(name, *values, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError(
                    "Independent event/mechanics reference import denied: " + fullname
                )

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    retained = args.output.parent / ("raw-reference-" + str(args.refinement))
    completed_retained = []

    def retain(name, value):
        retained.mkdir(parents=True, exist_ok=True)
        with (retained / (name + ".json")).open("x") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
        completed_retained.append(name)

    def file_record(path):
        if not path.exists():
            return dict(path=str(path), present=False)
        if path.is_symlink() or not path.is_file():
            raise ValueError("Failure evidence must be a regular file: " + str(path))
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        return dict(path=str(path), present=True, bytes=path.stat().st_size, sha256=digest)

    def raw_records():
        return dict(
            completed_names=list(completed_retained),
            files=[file_record(path) for path in sorted(retained.iterdir())]
            if retained.exists()
            else [],
            incomplete_files_are_not_completed_forms=True,
        )

    def retain_failure(payload):
        payload.update(worker_kind="independent_INIT_reference", scientific_credit=0)
        failure_path = args.output.with_name(args.output.name + ".failure.json")
        with failure_path.open("x") as stream:
            json.dump(payload, stream, indent=2, allow_nan=False)
            stream.write("\n")

    stage = "input"
    try:
        incoming = json.loads(args.inputs.read_text())
        stage = "evaluate"
        result = evaluate(incoming, refinement=args.refinement, retain=retain)
        stage = "runtime"
        loaded = [n for n in sys.modules if n.split(".")[0] in blocked]
        assert not loaded
        result.update(
            production_imports_denied=True, loaded_production_modules=loaded, runtime=inventory()
        )
        stage = "result_write"
        with args.output.open("x") as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write("\n")
    except Exception as error:
        record_failure(
            error,
            stage=stage,
            readers=dict(
                inputs=lambda: file_record(args.inputs),
                output=lambda: file_record(args.output),
                refinement=lambda: args.refinement,
                raw_reference_records=raw_records,
                runtime=inventory,
                loaded_production_modules=lambda: sorted(
                    n for n in sys.modules if n.split(".")[0] in blocked
                ),
            ),
            retain=retain_failure,
        )
        raise


if __name__ == "__main__":
    main()
