"""Fresh conditional Decimal references for two source network owners; held/unrun."""

import copy
from decimal import localcontext

from validation.betse import betse_normal_ecm_catalog_join_reference as qualified
from validation.betse import betse_normal_ecm_init_phase_reference as raw_evidence
from validation.betse import betse_normal_ecm_molecule_dispatch_reference_models as models


def calcium_index(inputs):
    inputs = copy.deepcopy(inputs)
    names = inputs["definition"]["environment_geometry_definition"]["current_definition"]["ions"][
        "ids"
    ]
    inputs["calcium"]["Ca_index"] = names.index("Ca")
    return inputs


def evaluate(inputs, *, refinement, retain):
    if refinement not in (1, 2):
        raise ValueError("Require the two predeclared fresh forms")
    mode = inputs.get("mode")
    precision = 100 if refinement == 1 else 160
    with localcontext() as context:
        context.prec = precision
        if mode == "material":
            result = models.prefix_model(calcium_index(inputs), refinement=refinement)
            raw_evidence.retain_raw(retain, "material-prefix", result, precision)
            result = qualified.serial(result)
        elif mode == "commit":
            adapted = copy.deepcopy(inputs)
            adapted["material_inputs"] = calcium_index(adapted["material_inputs"])
            result = models.commit_model(adapted, refinement=refinement)
            raw_evidence.retain_raw(retain, "deferred-commit", result, precision)
            result = qualified.serial(result)
        else:
            result = qualified.evaluate(inputs, refinement=refinement)
            if mode == "cold_initialization" and inputs["owner_role"] == "molecules":
                result["owner_fields"].pop("reset_MT", None)
                result["owner_fields"].pop("recalc_fluid", None)
                result["owner_fields"]["savedMoM"] = (
                    "supplied_native_persistence_disabled/GeneralNetwork.betse"
                )
    result.update(
        mode=mode,
        decimal_precision=precision,
        carried_reference_forms=0,
        independently_carried_trajectory=False,
        fresh_conditional_reference=True,
        physical_global_conservation_credit=False,
        source_flags_inferred=False,
        inherited_channel_oracle_domains_unchanged=True,
    )
    return result


def main():
    import argparse
    import builtins
    import importlib.abc
    import json
    import sys
    import traceback
    from pathlib import Path

    from validation.betse.betse_normal_channel_join_runtime import inventory

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--refinement", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    blocked = {"cells", "betse", "numpy", "scipy", "jax", "jaxlib"}
    original = builtins.__import__

    def guarded(name, *values, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("Independent two-owner reference import denied: " + name)
        return original(name, *values, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("Independent two-owner reference import denied: " + fullname)

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    retained = args.output.parent / ("raw-reference-" + str(args.refinement))

    def retain(name, value):
        retained.mkdir(parents=True, exist_ok=True)
        with (retained / (name + ".json")).open("x") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")

    try:
        result = evaluate(
            json.loads(args.inputs.read_text()), refinement=args.refinement, retain=retain
        )
    except Exception as error:
        with (args.output.parent / ("reference-refusal-" + str(args.refinement) + ".json")).open(
            "x"
        ) as stream:
            json.dump(
                dict(
                    status="reference_refused",
                    type=type(error).__name__,
                    message=str(error),
                    traceback=traceback.format_exc(),
                    accuracy_credit=False,
                    oracle_domains_unchanged=True,
                    available_input_path=str(args.inputs),
                    runtime=inventory(),
                ),
                stream,
                indent=2,
                allow_nan=False,
            )
            stream.write("\n")
        raise
    loaded = [name for name in sys.modules if name.split(".")[0] in blocked]
    if loaded:
        raise ImportError("Forbidden module reached fresh reference process")
    result.update(
        production_imports_denied=True, loaded_production_modules=loaded, runtime=inventory()
    )
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
