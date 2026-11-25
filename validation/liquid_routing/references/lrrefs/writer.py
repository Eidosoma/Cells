"""The files: their keys, their bytes, and nothing else. Run times go to a folder of their own."""

import hashlib
import json
import os
import time

from . import arms, invented, plans
from .arith import K_B_TEXT, N_A_TEXT, set_precision
from .world import Inputs

KIND = "liquid-routing reference, version 1"
BUILDERS = {1: arms.arm1, 2: arms.arm2, 3: arms.arm3, 4: arms.arm4, 5: arms.arm5, 6: arms.arm6}


def is_scalar(value):
    return not isinstance(value, (dict, list, tuple))


def dump(value, indent=0):
    """Deterministic JSON: sorted keys, one key to a line, a list of scalars on one line."""
    pad, inner = " " * indent, " " * (indent + 1)
    if isinstance(value, dict):
        if not value:
            return "{}"
        body = ",\n".join(f"{inner}{json.dumps(k)}: {dump(v, indent + 1)}" for k, v in sorted(value.items()))
        return "{\n" + body + "\n" + pad + "}"
    if isinstance(value, (list, tuple)):
        if all(is_scalar(v) for v in value):
            return "[" + ", ".join(json.dumps(v, allow_nan=False) for v in value) + "]"
        body = ",\n".join(f"{inner}{dump(v, indent + 1)}" for v in value)
        return "[\n" + body + "\n" + pad + "]"
    return json.dumps(value, allow_nan=False)


def document(arm, inputs, blocks, revision):
    return {
        "arm": arm,
        "cases": blocks.cases,
        "checks": blocks.checks,
        "constants": {"N_A": N_A_TEXT, "k_B": K_B_TEXT},
        "events": blocks.events,
        "inputs_sha256": inputs.sha256,
        "kind": KIND,
        "planted_series": blocks.planted_series,
        "plants": blocks.plants,
        "plants_reported": blocks.plants_reported,
        "provenance": {"revision": revision, "sha256_of_this_file_excluded": True},
        "reported": blocks.reported,
        "worlds": blocks.worlds,
    }


def write(path, content):
    data = content.encode("ascii")
    with open(path, "wb") as handle:
        handle.write(data)
    return hashlib.sha256(data).hexdigest()


class Clock:
    """Wall and processor seconds of one file's computation, written apart from the references."""

    def __init__(self, out, name):
        self.out, self.name, self.marks = out, name, {}
        self.wall, self.cpu = time.perf_counter(), time.process_time()

    def mark(self, label):
        self.marks[label] = {"wall_s": round(time.perf_counter() - self.wall, 2), "cpu_s": round(time.process_time() - self.cpu, 2)}
        print(f"{self.name}: {label}: {self.marks[label]}", flush=True)

    def close(self):
        folder = os.path.join(self.out, "run_times")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, f"{self.name}.json"), "w", encoding="ascii") as handle:
            json.dump(self.marks, handle, indent=1, sort_keys=True)
            handle.write("\n")


def write_invented(out, revision):
    """`inputs_invented.json` and `reference_invented.json` (arm 0): every invented world in one file."""
    set_precision()
    clock = Clock(out, "invented")
    inputs_path = os.path.join(out, "inputs_invented.json")
    write(inputs_path, invented.text())
    inputs = Inputs(inputs_path)
    whole = arms.Blocks()
    for arm in sorted(BUILDERS):
        if arm in (1, 2):
            whole.merge(BUILDERS[arm](inputs, plans.INVENTED, label=f"inv- arm {arm} (explicit stages)"))
        else:
            whole.merge(BUILDERS[arm](inputs, plans.INVENTED))
        clock.mark(f"to the end of arm {arm}")
    write(os.path.join(out, "reference_invented.json"), dump(document(0, inputs, whole, revision)) + "\n")
    clock.close()


def write_registered(out, inputs_path, revision, which=None):
    """`reference_arm<k>.json` for the registered inputs."""
    set_precision()
    for arm in which or sorted(BUILDERS):
        inputs = Inputs(inputs_path)         # read afresh, so that no arm depends on what another computed
        clock = Clock(out, f"arm{arm}")
        blocks = BUILDERS[arm](inputs, plans.REGISTERED)
        write(os.path.join(out, f"reference_arm{arm}.json"), dump(document(arm, inputs, blocks, revision)) + "\n")
        clock.mark("whole")
        clock.close()
