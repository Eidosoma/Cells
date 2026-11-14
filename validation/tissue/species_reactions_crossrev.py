"""The shared-inventory reactions operator's own crossrev world set (D152 version 1; design §2.3,
§6.5 and the lead's ruling Q11 (b)): programs and bindings.

The set is recorded with validation/tissue/composite_crossrev's own tracing and records (_setup,
_traced, const_record, check_constants), in its file format, so composite_crossrev's compare checks
two revisions' outputs, as validation/tissue/secreted_species_crossrev.py does for D150. The worlds
are compositions version 1 admits: the enzyme network with faces and face-free, its idle copy at
zero multipliers, the per-site schedule world, the two-factor world with padded slots, and C2's
mixed heredity chain.

`check` tests the promise (§2.3; ruling Q11 (b)): per-world law parameters (k, k_cat, V_max, K_M,
k_f, the Hill K and n, mu°/RT, c0) are layout bindings and the multipliers control arrays, never
closed-over constants.
* Two value twins: a world and its copy with every law parameter, every standard potential, c0
  and every multiplier changed, the structure the same. Their traced programs must be identical in
  text and in every closed-over constant, and only the parameter layout arrays and the multiplier
  control arrays may differ in their bindings (the rates, potentials, c0 and multipliers must).
* No nonzero parameter or multiplier row (and no 0-d c0) of a world coincides with a closed-over
  constant of its own world's programs (dtype, shape and bytes).

Usage (PYTHONPATH at the revision under test; WORLD names restrict jaxprs and bindings to those
worlds):
  python -m validation.tissue.species_reactions_crossrev jaxprs DIR [WORLD ...]
  python -m validation.tissue.species_reactions_crossrev bindings DIR [WORLD ...]
  python -m validation.tissue.species_reactions_crossrev check DIR
  python -m validation.tissue.composite_crossrev compare A B
"""

import copy
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from validation.tissue import composite_crossrev as crossrev
from validation.tissue import species_reactions_fixtures as rfx

KINDS = ("checked_step", "rhs", "device_checks")
PARAMETER_FIELDS = (
    "layout.reaction_rate_constant",
    "layout.reaction_saturation_mM",
    "layout.reaction_factor_half_saturation_mM",
    "layout.reaction_factor_coefficient",
    "layout.reaction_standard_mu_RT",
    "layout.reaction_standard_concentration_mM",
    "control.reaction_multiplier",
)
# Every twin moves these (a network without factors or Michaelis-Menten routes has nothing to
# move in the factor and saturation arrays, whose padding is fixed).
REQUIRED_MOVES = (
    "layout.reaction_rate_constant",
    "layout.reaction_standard_mu_RT",
    "layout.reaction_standard_concentration_mM",
    "control.reaction_multiplier",
)
RATE_KEYS = ("rate_constant", "forward_rate_per_s", "catalytic_rate_per_s", "max_rate_mM_per_s")
# {twin: original}: every parameter, potential, c0 and multiplier of the original changed.
TWINS = {"reactions_enzyme_values": "reactions_enzyme", "reactions_mixed_values": "reactions_mixed"}


def changed(raw, scale):
    """raw with every law parameter, standard potential, c0 and multiplier changed (the same
    structure: a value twin)."""
    out = copy.deepcopy(raw)
    block = next(b for b in out["model"]["operators"] if b["law"] == rfx.REACTIONS)
    block["standard_concentration_mM"] *= scale
    for entry in block["species"]:
        entry["standard_mu_RT"] = entry["standard_mu_RT"] * scale + 0.1
    for reaction in block["reactions"]:
        for key in (*RATE_KEYS, "saturation_mM"):
            if key in reaction:
                reaction[key] *= scale
        for factor in reaction["factors"]:
            factor["half_saturation_mM"] *= scale
            factor["hill_coefficient"] *= 1 + 0.1 * (scale - 1)
    for entry in out["experiment"]["reaction_controls"]:
        for change in entry["schedule"]:
            change["multiplier"] = change["multiplier"] * scale + 0.05
    return out


def per_site():
    """The enzyme network with its removal at both nodes: the reaction's schedule (a change at
    2 ms) and ecs_0's own (off, then on at 1 ms)."""
    raw = rfx.enzyme_network(end=0.004)
    block = raw["model"]["operators"][0]
    next(r for r in block["reactions"] if r["id"] == "removal")["sites"] = {
        "cells": "all",
        "outside": ["ecs_0"],
    }
    raw["experiment"]["reaction_controls"] = [
        c for c in raw["experiment"]["reaction_controls"] if c["reaction_id"] != "removal"
    ] + [
        dict(
            reaction_id="removal",
            site=None,
            schedule=[dict(time=0.0, multiplier=1.0), dict(time=0.002, multiplier=0.5)],
        ),
        dict(
            reaction_id="removal",
            site="ecs_0",
            schedule=[dict(time=0.0, multiplier=0.0), dict(time=0.001, multiplier=2.0)],
        ),
    ]
    return raw


def padded():
    raw = rfx.two_factor_network(c0=0.5, end=0.004)
    raw["execution"]["capacity"] += 1
    raw["execution"]["extracellular_capacity"] += 1
    return raw


def reaction_worlds():
    """The set (module docstring)."""
    enzyme = rfx.enzyme_network(end=0.004)
    mixed = rfx.mixed_chain(1e-3, end=0.01)
    return dict(
        reactions_enzyme=enzyme,
        reactions_enzyme_values=changed(enzyme, 1.7),
        reactions_face_free=rfx.enzyme_network(faces=False, end=0.004),
        reactions_idle=rfx.enzyme_network(
            dict.fromkeys(("binding", "catalysis", "conversion", "supply", "removal"), 0.0),
            end=0.004,
        ),
        reactions_per_site=per_site(),
        reactions_padded=padded(),
        reactions_mixed=mixed,
        reactions_mixed_values=changed(mixed, 1.3),
    )


def selected(names=()):
    worlds = reaction_worlds()
    unknown = set(names) - set(worlds)
    if unknown:
        raise SystemExit(f"Unknown worlds {sorted(unknown)} (the set has {sorted(worlds)})")
    return {k: v for k, v in worlds.items() if not names or k in names}


def jaxprs(directory, names=()):
    """composite_crossrev.jaxprs on this set: each program's text and constant record."""
    import jax

    jax.config.update("jax_enable_x64", True)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, raw in selected(names).items():
        for kind, closed in crossrev._traced(*crossrev._setup(raw)).items():
            (directory / f"{name}.{kind}.txt").write_text(str(closed))
            (directory / f"{name}.{kind}.consts.json").write_text(crossrev.const_record(closed))
        print(name, flush=True)


def bindings(directory, names=()):
    """composite_crossrev.bindings on this set: every bound state, layout, control (at every
    schedule time) and device-check array."""
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.core.schedule import control_values
    from cells.core.specs import parse_spec
    from cells.models.registry import get_model

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, raw in selected(names).items():
        spec = parse_spec(raw)
        model = get_model(spec.model)
        state, layout = model.initial_values(spec)
        times = sorted({0.0, *(c.time for c in spec.experiment.changes), spec.experiment.end_time})
        arrays = {}
        for prefix, tree in (
            ("state.", state),
            ("layout.", layout),
            ("control.", control_values(spec, times)),
        ):
            for key, value in tree._asdict().items():
                arrays[prefix + key] = np.asarray(value)
        for key, value in crossrev.check_constants(model, spec):
            arrays["check." + key] = value
        np.savez(directory / f"{name}.npz", **arrays)
        print(name, len(arrays), flush=True)


def _digest(array):
    array = np.ascontiguousarray(array)
    return str(array.dtype), list(array.shape), hashlib.sha256(array.tobytes()).hexdigest()


def _closed(directory, name):
    rows = []
    for kind in KINDS:
        rows += json.loads((directory / f"{name}.{kind}.consts.json").read_text())["consts"]
    return [(r["dtype"], r["shape"], r["sha256"]) for r in rows]


def _candidates(array):
    """The whole array, and each nonzero row of a 1-D or 2-D one (a 0-d array is itself)."""
    array = np.asarray(array)
    out = [array] if np.any(array) else []
    if array.ndim >= 1:
        out += [r for r in array if np.any(r)]
    if array.ndim == 2:
        out += [r for r in array.T if np.any(r)]
    return out


def check(directory):
    """The promise on saved outputs (module docstring). Writes check.json; True when it holds."""
    directory = Path(directory)
    report, ok = {"worlds": {}, "twins": {}}, True
    saved = {path.stem: np.load(path) for path in sorted(directory.glob("*.npz"))}
    for name in reaction_worlds():
        if name not in saved:
            report["worlds"][name], ok = "MISSING bindings", False
            continue
        arrays, closed, entry = saved[name], _closed(directory, name), {}
        for key in PARAMETER_FIELDS:
            if key not in arrays.files:
                entry[key], ok = "MISSING", False
                continue
            rows = _candidates(arrays[key])
            hits = [r for r in rows if _digest(r) in closed]
            if hits:
                entry[key], ok = "a bound row COINCIDES with a closed-over constant", False
            else:
                entry[key] = f"bound; {len(rows)} nonzero arrays and rows, none a closed constant"
        report["worlds"][name] = entry
    for twin, original in TWINS.items():
        a, b = saved[original], saved[twin]
        texts = {
            kind: (directory / f"{original}.{kind}.txt").read_text()
            == (directory / f"{twin}.{kind}.txt").read_text()
            for kind in KINDS
        }
        consts = {
            kind: json.loads((directory / f"{original}.{kind}.consts.json").read_text())
            == json.loads((directory / f"{twin}.{kind}.consts.json").read_text())
            for kind in KINDS
        }
        differ = sorted(
            k
            for k in set(a.files) | set(b.files)
            if k not in a.files or k not in b.files or a[k].tobytes() != b[k].tobytes()
        )
        stray = [k for k in differ if k not in PARAMETER_FIELDS]
        moved = [k for k in PARAMETER_FIELDS if k in differ]
        holds = (
            all(texts.values())
            and all(consts.values())
            and not stray
            and set(REQUIRED_MOVES) <= set(moved)
        )
        ok &= holds
        report["twins"][twin] = dict(
            original=original,
            texts_identical=texts,
            constants_identical=consts,
            bindings_that_differ=differ,
            differing_beyond_the_parameters=stray,
            parameters_that_differ=moved,
            holds=holds,
        )
    report["verdict"] = "holds" if ok else "FAILS"
    (directory / "check.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps(report, indent=1, sort_keys=True))
    return ok


if __name__ == "__main__":
    action, target, *worlds = sys.argv[1:]
    if action == "jaxprs":
        jaxprs(target, worlds)
    elif action == "bindings":
        bindings(target, worlds)
    elif action == "check":
        sys.exit(0 if check(target) else 1)
    else:
        raise SystemExit(f"Unknown action {action!r} (jaxprs, bindings or check)")
