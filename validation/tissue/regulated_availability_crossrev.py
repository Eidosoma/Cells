"""The coupling operator's own crossrev world set (cells.operator.species_regulated_availability@1; design §1.10,
claim 1, and its batch signature): programs and bindings.

The set is recorded with validation/tissue/composite_crossrev's own tracing and records (_setup,
_traced, const_record, check_constants), in its file format, so composite_crossrev's compare checks
two revisions' outputs, as validation/tissue/species_reactions_crossrev.py does for D152. Its first
record is made at landing. The worlds are compositions version 1 admits
(regulated_availability_fixtures): the shared coupled structure (junction and channel targets),
the moving world (D150's turnover, a state of Na with a crossing level, a switch and a write), the
small two-cell world, the operator declared idle, and value twins of the first two.

`check` tests the promise (§1.10): the operator's per-world parameters (K, n, b, k_on, k_off, θ,
s0, the switches and the written values) are layout, state or control bindings, never closed-over
constants.
* Two value twins: a world and its copy with every one of the operator's parameters changed, the
  structure the same. Their traced programs must be identical in text and in every closed-over
  constant, and only the operator's parameter arrays may differ in their bindings.
* No nonzero parameter row of a world coincides with a closed-over constant of its own world's
  programs (dtype, shape and bytes).

Usage (PYTHONPATH at the revision under test; WORLD names restrict jaxprs and bindings):
  python -m validation.tissue.regulated_availability_crossrev jaxprs DIR [WORLD ...]
  python -m validation.tissue.regulated_availability_crossrev bindings DIR [WORLD ...]
  python -m validation.tissue.regulated_availability_crossrev check DIR
  python -m validation.tissue.composite_crossrev compare A B
"""

import copy
import json
import sys
from pathlib import Path

import numpy as np

from validation.tissue import composite_crossrev as crossrev
from validation.tissue import regulated_availability_fixtures as rf
from validation.tissue import species_reactions_crossrev as base  # Its record readers.

PARAMETER_FIELDS = (
    "layout.regulatory_on_rate",
    "layout.regulatory_off_rate",
    "layout.regulatory_level",
    "layout.regulatory_input_half_saturation_mM",
    "layout.regulatory_input_coefficient",
    "layout.coupling_route_half_saturation_mM",
    "layout.coupling_route_coefficient",
    "layout.coupling_route_basal",
    "state.regulatory_state",
    "state.coupling_enabled",  # The switches' values at time 0, copied into state.
    "control.coupling_switch",
    "control.regulatory_write_value",
)
# Every twin moves these (the shared structure's couplings are state fractions with b = 0 and
# frozen rates, so its twin moves s0, the switches and the written value only).
REQUIRED_MOVES = {
    "coupling_dynamic_values": (
        "layout.regulatory_on_rate",
        "layout.regulatory_off_rate",
        "layout.regulatory_level",
        "layout.regulatory_input_half_saturation_mM",
        "layout.regulatory_input_coefficient",
        "layout.coupling_route_half_saturation_mM",
        "layout.coupling_route_coefficient",
        "layout.coupling_route_basal",
        "state.regulatory_state",
        "control.regulatory_write_value",
    ),
    "coupling_shared_values": ("state.regulatory_state", "control.coupling_switch"),
}
TWINS = {"coupling_dynamic_values": "coupling_dynamic", "coupling_shared_values": "coupling_shared"}
END = 0.03


def block(raw):
    return next(b for b in raw["model"]["operators"] if b["law"] == rf.LAW)


def changed(raw, scale):
    """raw with every one of the operator's parameters changed (a value twin)."""
    out = copy.deepcopy(raw)
    op = block(out)
    for state in op["states"]:
        state["on_rate_per_s"] *= scale
        state["off_rate_per_s"] *= scale
        if state["crossing_level"] is not None:
            state["crossing_level"] *= 0.9
        initial = state["initial"]
        state["initial"] = (
            {c: v * 0.9 for c, v in initial.items()} if isinstance(initial, dict) else initial * 0.9
        )
        for item in state["inputs"]:
            item["half_saturation_mM"] *= scale
            item["hill_coefficient"] *= 1 + 0.1 * (scale - 1)
    for coupling in op["couplings"]:
        if "half_saturation_mM" in coupling:
            coupling["half_saturation_mM"] *= scale
            coupling["hill_coefficient"] *= 1 + 0.1 * (scale - 1)
        coupling["basal"] = coupling["basal"] * 0.5 if coupling["basal"] else 0.0
    for entry in out["experiment"]["coupling_controls"]:
        entry["schedule"][0]["enabled"] = 1 - entry["schedule"][0]["enabled"]
    for entry in out["experiment"]["regulatory_writes"]:
        entry["value"] *= 0.9
    return out


def coupling_worlds():
    """The set (module docstring)."""
    shared = rf.shared_structure(on=("a", "k"), s0=(0.5, 0.25), end=END)
    dynamic = rf.dynamic_world(end=END)
    return dict(
        coupling_shared=shared,
        coupling_shared_values=changed(shared, 1.7),
        coupling_dynamic=dynamic,
        coupling_dynamic_values=changed(dynamic, 1.3),
        coupling_pair=rf.pair_world(end=END),
        coupling_idle=rf.with_coupling(rf.sheet(end=END)),
    )


def selected(names=()):
    worlds = coupling_worlds()
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
    from cells.definitions.specs import parse_spec
    from cells.execution.schedule import control_values
    from cells.registry.models import get_model

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


def check(directory):
    """The promise on saved outputs (module docstring). Writes check.json; True when it holds."""
    directory = Path(directory)
    report, ok = {"worlds": {}, "twins": {}}, True
    saved = {path.stem: np.load(path) for path in sorted(directory.glob("*.npz"))}
    for name in coupling_worlds():
        if name not in saved:
            report["worlds"][name], ok = "MISSING bindings", False
            continue
        arrays, closed, entry = saved[name], base._closed(directory, name), {}
        for key in PARAMETER_FIELDS:
            if key not in arrays.files:
                entry[key], ok = "MISSING", False
                continue
            rows = base._candidates(arrays[key])
            hits = [r for r in rows if base._digest(r) in closed]
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
            for kind in base.KINDS
        }
        consts = {
            kind: json.loads((directory / f"{original}.{kind}.consts.json").read_text())
            == json.loads((directory / f"{twin}.{kind}.consts.json").read_text())
            for kind in base.KINDS
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
            and set(REQUIRED_MOVES[twin]) <= set(moved)
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
