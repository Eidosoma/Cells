"""The secreted-species operators' own crossrev world set (D150 version 1; design §7): programs
and bindings.

The set is recorded with validation/tissue/composite_crossrev's own tracing and records (_setup,
_traced, const_record, check_constants), in its file format, so composite_crossrev's compare checks
two revisions' outputs, as validation/division/division_crossrev.py does for S5. The worlds are the
compositions version 1 admits: each operator alone, both with a replacement newcomer, idle at zero
rate, the radial world of the guards and the mixed heredity chain.

`check` tests the design's promise (§7, "the constants-aware crossrev"): per-world rates and law
parameters (P, k, J, k_e, k_u, V_max, K_M) are control arrays, bindings, never closed-over
constants.
* Two value twins: a world and its copy with every rate and K_M changed. Their traced programs must
  be identical in text and in every closed-over constant, and only control arrays may differ in
  their bindings. A rate compiled in would show in one or the other: a scalar as a literal in the
  text, an array among the constants.
* No nonzero control row of the operators' fields coincides with a closed-over constant of its own
  world's programs (dtype, shape and bytes).

Usage (PYTHONPATH at the revision under test; WORLD names restrict jaxprs and bindings to those
worlds):
  python -m validation.tissue.secreted_species_crossrev jaxprs DIR [WORLD ...]
  python -m validation.tissue.secreted_species_crossrev bindings DIR [WORLD ...]
  python -m validation.tissue.secreted_species_crossrev check DIR
  python -m validation.tissue.composite_crossrev compare A B
"""

import copy
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from validation.tissue import composite_crossrev as crossrev
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import secreted_species_radial as radial

KINDS = ("checked_step", "rhs", "device_checks")
RATE_FIELDS = ("control.turnover_rate", "control.exchange_rate", "control.exchange_saturation_mM")
# {twin: original}: every rate and K_M of the original changed.
TWINS = {"species_both_values": "species_both", "species_mixed_values": "species_mixed"}


def both(scale=1.0):
    """Two cells and their nodes; replacement@1 with a template newcomer at 3 ms; exchange with
    every law; turnover at a cell and a node. scale multiplies every rate and K_M (a value twin)."""
    base = fx.world(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        nodes=(("ecs_0", 1.0), ("ecs_1", 1.0)),
        contacts=(
            ("contact_0", "cell_0", "ecs_0"),
            ("contact_1", "cell_1", "ecs_0"),
            ("contact_2", "cell_0", "ecs_1"),
        ),
        faces=(("face_0", "ecs_0", "bath", 1e-10, 1e-5), ("face_1", "ecs_1", "bath", 1e-10, 1e-5)),
        junctions=(("junction_0", "cell_0", "cell_1"),),
        end=0.01,
        concentrations_mM=dict(cell_0=1e-3, cell_1=2e-4, ecs_0=5e-4, ecs_1=3e-4),
    )
    template = fx.template(base, "cell_0", "T", s_mM=1.2e-3)
    raw = fx.with_replacement(base, [template], [(0.003, "cell_0", "T", "c0_new")])
    raw = fx.with_exchange(
        raw,
        [
            ("burst", "contact_0", "export", "flux"),
            ("secrete", "contact_2", "export", "first_order"),
            ("take_up", "contact_1", "import", "first_order"),
            ("sink", "contact_1", "import", "saturable"),
        ],
        [
            ("burst", "cell_0", [(0.0, 1e-7 * scale)]),
            ("secrete", "cell_0", [(0.0, 0.2 * scale), (0.002, 0.3 * scale)]),
            ("take_up", "cell_1", [(0.0, 1e-6 * scale)]),
            ("sink", "cell_1", [(0.0, 1e6 * scale, 5e-4 * scale)]),
        ],
        templates=[("T", {"burst": {"rate": 2e-7 * scale}, "secrete": {"rate": 0.1 * scale}})],
    )
    return fx.with_turnover(
        raw,
        [("produce", "cell_0", "production"), ("clear", "ecs_1", "clearance")],
        [("produce", "cell_0", [(0.0, 1e-6 * scale)]), ("clear", None, [(0.0, 0.5 * scale)])],
        templates=[("T", {"produce": 2e-6 * scale})],
    )


def idle():
    raw = copy.deepcopy(both())
    for entry in (*raw["experiment"]["turnover_controls"], *raw["experiment"]["exchange_controls"]):
        for change in entry["schedule"]:
            change["rate"] = 0.0
    for block in raw["model"]["operators"][1:]:
        for template in block["templates"]:
            template["rates"] = {
                k: (0.0 if not isinstance(v, dict) else dict(v, rate=0.0))
                for k, v in template["rates"].items()
            }
    return raw


def mixed(scale=1.0):
    return fx.chain_operators(
        fx.heredity_chain(secreted=True, end=0.01),
        secrete=0.1 * scale,
        produce=1e-4 * scale,
        clear=0.5 * scale,
        uptake=1e6 * scale,
        ku=1e-6 * scale,
    )


def radial_world():
    geometry = radial.Geometry(10e-6, 5e-6, 24)
    profile = radial.pre_formed(
        geometry, diffusivity=4e-10, clearance=1.0, c0_mM=1e-3, trace_mM=1e-15
    )
    return radial.world(
        geometry,
        diffusivity=4e-10,
        clearance=1.0,
        c0_mM=1e-3,
        trace_mM=1e-15,
        profile_mM=profile,
        dt=1e-3,
        end=0.01,
    )


def species_worlds():
    """The set (module docstring)."""
    turnover = fx.with_turnover(
        fx.secreting_cell(),
        [("produce", "cell_0", "production"), ("clear", "ecs_0", "clearance")],
        [("produce", "cell_0", [(0.0, 1e-6)]), ("clear", None, [(0.0, 0.5)])],
    )
    exchange = fx.with_exchange(
        fx.secreting_cell(),
        [("secrete", "contact_0", "export", "first_order")],
        [("secrete", "cell_0", [(0.0, 0.1)])],
    )
    return dict(
        species_turnover=turnover,
        species_exchange=exchange,
        species_both=both(),
        species_both_values=both(scale=1.7),
        species_idle=idle(),
        species_radial=radial_world(),
        species_mixed=mixed(),
        species_mixed_values=mixed(scale=1.3),
    )


def selected(names=()):
    worlds = species_worlds()
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


def check(directory):
    """The promise on saved outputs (module docstring). Writes check.json; True when it holds."""
    directory = Path(directory)
    report, ok = {"worlds": {}, "twins": {}}, True
    saved = {path.stem: np.load(path) for path in sorted(directory.glob("*.npz"))}
    for name in species_worlds():
        if name not in saved:
            report["worlds"][name], ok = "MISSING bindings", False
            continue
        arrays, closed, entry = saved[name], _closed(directory, name), {}
        for key in RATE_FIELDS:
            if key not in arrays.files:
                continue
            rows = [r for r in np.asarray(arrays[key]) if np.any(r)]
            hits = [r for r in rows if _digest(r) in closed]
            if hits:
                entry[key], ok = "a control row COINCIDES with a closed-over constant", False
            else:
                entry[key] = f"bound; {len(rows)} nonzero rows, none equal to a closed constant"
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
        stray = [k for k in differ if k not in RATE_FIELDS]
        moved = [k for k in RATE_FIELDS if k in differ]
        holds = all(texts.values()) and all(consts.values()) and not stray and bool(moved)
        ok &= holds
        report["twins"][twin] = dict(
            original=original,
            texts_identical=texts,
            constants_identical=consts,
            bindings_that_differ=differ,
            differing_beyond_the_rates=stray,
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
