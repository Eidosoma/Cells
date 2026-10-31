"""Fresh source-conditional event and mechanics references; inherited equations/budgets."""

from validation.betse import betse_mechanics_join_reference as mechanics
from validation.betse import betse_normal_ecm_event_join_reference as events


def evaluate(inputs, *, refinement, retain):
    if inputs.get("mode") != "mechanics":
        return events.evaluate(inputs, refinement=refinement)
    projected = mechanics.evaluate(
        {k: inputs[k] for k in ("definition", "initial", "steps")},
        refinement=refinement,
        retain=retain,
    )
    projected.update(
        mode="mechanics",
        decimal_precision=100 if refinement == 1 else 160,
        carried_reference_forms=0,
        independent_trajectory=False,
        physical_global_conservation_credit=False,
    )
    return projected


def main():
    import argparse
    import builtins
    import importlib.abc
    import json
    import sys
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

    def retain(name, value):
        retained.mkdir(parents=True, exist_ok=True)
        with (retained / (name + ".json")).open("x") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")

    result = evaluate(
        json.loads(args.inputs.read_text()), refinement=args.refinement, retain=retain
    )
    loaded = [n for n in sys.modules if n.split(".")[0] in blocked]
    assert not loaded
    result.update(
        production_imports_denied=True, loaded_production_modules=loaded, runtime=inventory()
    )
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
