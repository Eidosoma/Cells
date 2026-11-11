#!/usr/bin/env python3
"""Plain-BETSE general-network channel cases on the rung-1 mammal dense world (parity tooling).

Prepares the configs of judged cases and their leave-one-out cases from a JSON spec, as the
P4/P4b cases were prepared (parity-rung2-4-20261109-01, parity-p4b-channels-20261110-01):
``betse_reference_run.py prepare`` on the rung-1 base config with exact single-occurrence
text replacements, then the rung-1 seed pickle copied into INITS. A case with channels turns
the general network on, empties its biomolecules and replaces its channel block; a case
without channels keeps the network off (the base config's own setting). Named world changes
(extra exact replacements, e.g. a tissue diffusion constant) apply to a case and its
leave-one-out cases alike. No BETSE run and no Cells model here.

Spec (JSON):
  {"channels": {KEY: {"name", "class", "type", "max_dm", "init_active"}, ...},
   "worlds": {NAME: [[OLD, NEW], ...], ...},                      (optional)
   "cases": {CASE: {"channels": [KEY, ...], "world": NAME | null,
                    "leave_one_out": {CHANNEL_LABEL: [KEY, ...], ...}}}}
Leave-one-out case names are CASE without "-dense", then "-no-LABEL-dense". REF/CASE.cases
lists the case and its leave-one-out cases, one per line.

    python3 validation/betse/network_cases.py prepare --spec SPEC.json --ref REF_DIR
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNG1 = Path(
    "/mnt/workspaces/Cells/parity-rung1-20261108-01/betse-reference/default-world-mammal-dense"
)
BASE = RUNG1 / "inputs/config"
SEED = RUNG1 / "run/config/INITS/world_1.betse.gz"
BETSE_PYTHON = "/mnt/workspaces/Cells/venv-betse/bin/python"
NETWORK = ("  implement network: False  #", "  implement network: True   #")
NO_BIOMOLECULES = "  biomolecules: []  # P4: channels only, no biomolecules\n\n"
# Block boundaries in the rung-1 sim_config.yaml (the blocks P4 replaced, byte for byte).
BIOMOLECULES = ("  biomolecules:  # specify", "  #---")
CHANNELS = ("  channels:\n\n", "    # available channel types")


def block(channels):
    """The YAML channel block for [{"name", "class", "type", "max_dm", "init_active"}, ...]."""
    lines = ["  channels:", ""]
    for c in channels:
        lines += [
            f"    - name: {c['name']}",
            f"      channel class: {c['class']}",
            f"      channel type: {c['type']}",
            f"      max Dm: {c['max_dm']:.6e}",
            "      apply to: all",
            f"      init active: {c['init_active']}",
            "",
        ]
    return "\n".join(lines) + "\n"


def section(text, bounds):
    """The text from bounds[0] up to (not including) the next bounds[1]; exactly one start."""
    start, stop = bounds
    if text.count(start) != 1:
        raise ValueError(f"base config: {start!r} must occur exactly once")
    i = text.index(start)
    j = text.index(stop, i + len(start))
    return text[i:j]


def replacements(base_yaml, channels, world=()):
    """[(old, new), ...] for one case: the world change, then the network and channel block."""
    pairs = [tuple(p) for p in world]
    if channels:
        text = Path(base_yaml).read_text()
        pairs += [
            NETWORK,
            (section(text, BIOMOLECULES), NO_BIOMOLECULES),
            (section(text, CHANNELS), block(channels)),
        ]
    return pairs


def prepare(out, channels, world=(), *, base=BASE, seed=SEED, python=BETSE_PYTHON):
    """Prepare one case directory (out/inputs/config, out/inputs/channels.json)."""
    (out / "inputs").mkdir(parents=True, exist_ok=False)
    (out / "inputs/channels.json").write_text(json.dumps(channels, indent=1) + "\n")
    argv = [
        str(python), "-I", str(ROOT / "validation/betse/betse_reference_run.py"), "prepare",
        "--base", str(base), "--out", str(out / "inputs/config"),
    ]  # fmt: skip
    for old, new in replacements(Path(base) / "sim_config.yaml", channels, world):
        argv += ["--replace", old, new]
    subprocess.run(argv, check=True)  # writes out/inputs/config.prepare.json
    shutil.copy2(seed, out / "inputs/config/INITS/world_1.betse.gz")


def prepare_all(spec, ref, **kwargs):
    """Every case of the spec and its leave-one-out cases; returns {case: [names]}."""
    table, worlds, written = spec["channels"], spec.get("worlds", {}), {}
    for name, case in spec["cases"].items():
        world = worlds[case["world"]] if case.get("world") else ()
        names = [name]
        prepare(ref / name, [table[k] for k in case["channels"]], world, **kwargs)
        for label, rest in case.get("leave_one_out", {}).items():
            loo = f"{name.removesuffix('-dense')}-no-{label}-dense"
            prepare(ref / loo, [table[k] for k in rest], world, **kwargs)
            names.append(loo)
        (ref / f"{name}.cases").write_text("\n".join(names) + "\n")
        written[name] = names
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="prepare the cases of a spec")
    prep.add_argument("--spec", required=True)
    prep.add_argument("--ref", required=True, help="directory for the case directories")
    prep.add_argument("--base", default=str(BASE))
    prep.add_argument("--seed", default=str(SEED))
    prep.add_argument("--python", default=BETSE_PYTHON, help="interpreter for the prepare step")
    args = parser.parse_args(argv)
    ref = Path(args.ref)
    ref.mkdir(parents=True, exist_ok=True)
    written = prepare_all(
        json.loads(Path(args.spec).read_text()), ref, base=args.base, seed=args.seed,
        python=args.python,
    )  # fmt: skip
    print(json.dumps(written, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
