"""Write `values.json`, or with `--check` make it again and compare.

    python write_values.py [--jobs N]          write
    python write_values.py --check [--jobs N]  make every number again; exit 1 at the first difference

Every published number is made by decimal arithmetic alone, so the file should be the same on every machine, to the byte.
Both modes run the store world 36 times (two variants, 17 controls and none). `--jobs` processes share that work.
"""

import argparse
import json
import multiprocessing
import sys
from pathlib import Path

if __package__:
    from . import api
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import api


def dump(value, indent=0):
    """JSON text with each list of numbers on one line."""
    pad = " " * (indent + 1)
    if isinstance(value, dict):
        if not value:
            return "{}"
        items = [f"{pad}{json.dumps(key)}: {dump(item, indent + 1)}" for key, item in value.items()]
        return "{\n" + ",\n".join(items) + "\n" + " " * indent + "}"
    if isinstance(value, list):
        if all(not isinstance(item, (dict, list)) for item in value):
            return "[" + ", ".join(json.dumps(item, allow_nan=False) for item in value) + "]"
        return "[\n" + ",\n".join(pad + dump(item, indent + 1) for item in value) + "\n" + " " * indent + "]"
    return json.dumps(value, allow_nan=False)


def _store_world(task):
    variant, control = task
    return api.store_world(variant, control, compute=True)


def document(jobs):
    """Every output on the inputs."""
    _forms, world = api._modules()
    names = [None] + world.control_names(api._inputs())
    tasks = [(variant, control) for variant in api.VARIANTS for control in names]
    if jobs > 1:
        with multiprocessing.get_context("fork").Pool(jobs) as pool:
            solved = pool.map(_store_world, tasks, chunksize=1)
    else:
        solved = [_store_world(task) for task in tasks]
    worlds = {variant: {} for variant in api.VARIANTS}
    for (variant, control), result in zip(tasks, solved):
        worlds[variant]["none" if control is None else control] = result
    last = api._inputs()["store_world"]["times_s"][-1]
    return {
        "schema": "calcium_store_references@1",
        "what": "Independent reference values for validation/calcium_store/reference_spec; see README.md beside this file. "
        "Every number is a double rounded once from the working precision.",
        "made_by": {
            "kernel_states_and_initial_rates_digits": api.KERNEL_DIGITS,
            "material_block_digits": api.BLOCK_DIGITS,
            "store_world": {"integrator": "extrapolated midpoint, decimal", **world.SETTINGS},
        },
        "units": api.units(),
        "store_world": worlds,
        "initial_rates": {variant: api.initial_rates(variant, compute=True) for variant in api.VARIANTS},
        "material_block": {
            variant: {repr(float(time)): api.material_block(variant, time, compute=True) for time in (0.0, last)}
            for variant in api.VARIANTS
        },
        "pump_states": api.pump_states(compute=True),
        "exchanger_states": api.exchanger_states(compute=True),
        "symport_states": api.symport_states(compute=True),
    }


def differences(old, new, path=""):
    """The paths at which two documents differ."""
    if isinstance(old, dict) and isinstance(new, dict):
        for key in list(old) + [key for key in new if key not in old]:
            if key not in old or key not in new:
                yield f"{path}/{key}: in one only"
            else:
                yield from differences(old[key], new[key], f"{path}/{key}")
    elif isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        for i, (a, b) in enumerate(zip(old, new)):
            yield from differences(a, b, f"{path}/{i}")
    elif type(old) is not type(new) or old != new:
        yield f"{path}: {old!r} is stored, {new!r} is made"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--to", type=Path, default=api.VALUES, help="write here instead (a comparison of two runs)")
    arguments = parser.parse_args()
    made = document(arguments.jobs)
    text = dump(made) + "\n"
    if arguments.check:
        stored = arguments.to.read_text(encoding="utf-8")
        if stored == text:
            print(f"{arguments.to.name}: the same, to the byte ({len(text)} bytes)")
            return 0
        found = list(differences(json.loads(stored), json.loads(text)))
        print(f"{arguments.to.name}: {len(found)} differences (or the layout alone, if none)")
        for line in found[:40]:
            print(line)
        return 1
    arguments.to.write_text(text, encoding="utf-8")
    print(f"wrote {arguments.to} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
